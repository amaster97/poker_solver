# PR 44 — v1.4.0 .dmg packaging fix spec

**Status:** SPEC (no edits made). Research + diagnosis pass only.
**Author:** triage agent, 2026-05-23
**Source defect report:** `docs/dmg_v1_4_0_smoke_verification.md`
**Touched files (read only during triage):**
- `scripts/poker_solver.spec`
- `scripts/build_macos_dmg.sh`
- `scripts/pyinstaller_entry.py`
- `ui/app.py`
- `pyproject.toml`
- `assets/README.md`
- `docs/pr11_prep/repackage_feasibility.md`
- `docs/pr11_prep/leg8_repackage_v1_3_2.md`
- `docs/leg9_v1_4_0_ship_plan.md`
- `poker_solver/__init__.py`
- `.venv/lib/python3.13/site-packages/` (inventory only)

---

## 1. Root causes in priority order

### P0 — `nicegui` not installed in the build venv (HARD BLOCKER; binary cannot launch)

**Evidence**
- `.venv/lib/python3.13/site-packages/` inventory: contains `pyinstaller`, `pyinstaller_hooks_contrib`, `numpy`, `psutil`, `maturin`, but **no `nicegui`, `fastapi`, `uvicorn`, `starlette`, `aiofiles`, `aiohttp`, `python-socketio`, `python-engineio`** (every NiceGUI runtime dep).
- `which pyinstaller` returns nothing on the user PATH; `pyinstaller` is only present at `.venv/bin/pyinstaller`. So `scripts/build_macos_dmg.sh` step 3 (`pyinstaller scripts/poker_solver.spec`) runs against `.venv` whenever the venv is activated, and against whichever Python is on `$PATH` otherwise.
- `nicegui` IS installed system-wide at `/Users/ashen/Library/Python/3.13/lib/python/site-packages/nicegui/` (v3.12.1) — a `python3 -m pip install --user` style location, not on `.venv`.
- `pyproject.toml` declares NiceGUI under `[project.optional-dependencies] ui = ["nicegui>=3.0,<4.0"]`, separate from `distribution = ["pyinstaller>=6.0"]`. The PR 11 build runbooks (`leg4_repackage_now.md`, `leg8_repackage_v1_3_2.md`) instruct `pip install -e ".[distribution]"` only — they never install the `[ui]` extra into the build venv.
- `scripts/poker_solver.spec` lines 48-69 already lists `hiddenimports=["nicegui", "nicegui.elements", "nicegui.functions", "uvicorn", "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto", "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto", "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto", "uvicorn.lifespan", "uvicorn.lifespan.on", "starlette", "starlette.routing"]`. None of this matters if the module is not importable at PyInstaller analysis time — hidden-imports are "include this module IF FOUND", they do not install missing packages.
- The bundle `find … -iname '*nicegui*'` returning zero matches is exactly the signature of "PyInstaller ran in a venv without nicegui installed": no nicegui dir, no warnings buried in the build log were honored.
- The 14.4 MB final DMG size is also consistent — a real NiceGUI bundle (FastAPI + uvicorn + nicegui + lxml + orjson) typically lands ~80-150 MB. 14 MB is too small for a working NiceGUI app.

**Fix (minimal)**
1. Make `[distribution]` depend transitively on `[ui]` so the build venv always has nicegui, OR add an explicit pre-flight check + install step in `scripts/build_macos_dmg.sh`. Recommended: BOTH (defense in depth).
2. **Edit `pyproject.toml`** — change `distribution` to either inline the deps or chain via PEP 735 self-reference:
   ```toml
   distribution = ["pyinstaller>=6.0", "nicegui>=3.0,<4.0"]
   ```
   (Inline rather than `poker_solver[ui]` self-ref to avoid the chicken-and-egg of needing the package to resolve its own extras during build.)
3. **Edit `scripts/build_macos_dmg.sh`** pre-flight (step 1, around line 140) — add a hard check:
   ```bash
   python -c "import nicegui" 2>/dev/null || err \
       "nicegui not importable in build Python.  Run: pip install -e '.[distribution]'  (which now includes the ui extra)."
   ```
4. **Edit `scripts/poker_solver.spec`** — broaden `hiddenimports` using PyInstaller's `collect_submodules` / `collect_all` helpers. NiceGUI 3.12.1 uses heavy runtime introspection (`nicegui.elements`, `nicegui.functions`, `nicegui.events`, `nicegui.tailwind`, `nicegui.app`, `nicegui.json`, `nicegui.testing`, etc.) plus `nicegui/static/` (JS/CSS bundles) and `nicegui/templates/` (Jinja) that are loaded by path at runtime. The existing list is too narrow; even with nicegui installed, the bundle would still crash on first `ui.run()` because of missing static assets. Recommended top of spec:
   ```python
   from PyInstaller.utils.hooks import collect_all, collect_submodules

   nicegui_datas, nicegui_binaries, nicegui_hiddenimports = collect_all("nicegui")
   fastapi_datas, fastapi_binaries, fastapi_hiddenimports = collect_all("fastapi")
   uvicorn_datas, uvicorn_binaries, uvicorn_hiddenimports = collect_all("uvicorn")
   starlette_datas, starlette_binaries, starlette_hiddenimports = collect_all("starlette")
   socketio_datas, socketio_binaries, socketio_hiddenimports = collect_all("socketio")
   engineio_datas, engineio_binaries, engineio_hiddenimports = collect_all("engineio")
   ```
   Then merge into `Analysis(...)`:
   ```python
   binaries=[(RUST_SO, "poker_solver")] + nicegui_binaries + fastapi_binaries + uvicorn_binaries + starlette_binaries + socketio_binaries + engineio_binaries,
   datas=[(CHARTS_DIR, "poker_solver/charts"), (UI_DIR, "ui")] + nicegui_datas + fastapi_datas + uvicorn_datas + starlette_datas + socketio_datas + engineio_datas,
   hiddenimports=nicegui_hiddenimports + fastapi_hiddenimports + uvicorn_hiddenimports + starlette_hiddenimports + socketio_hiddenimports + engineio_hiddenimports + [
       # Keep any project-specific hiddens here if needed.
   ],
   ```
   `collect_all` handles the static/templates dirs and the submodule tree in one call. The legacy hand-listed `uvicorn.protocols.http.auto` / `nicegui.elements` entries become redundant once `collect_all` is in place.

### P0 — Adhoc-signed instead of Developer ID signed + notarized (USER-BLOCKING; cannot self-resolve)

**Evidence**
- `docs/pr11_prep/repackage_feasibility.md` §2: "0 valid identities" from `security find-identity -v -p codesigning`. No `APPLE_ID` / `TEAM_ID` / `APP_SPECIFIC_PASSWORD` envs. No `Developer ID Application` cert in keychain.
- `scripts/build_macos_dmg.sh` defaults `SKIP_SIGNING` and `SKIP_NOTARIZATION` to 0 but the credentials check (lines 181-185) errors out unless credentials exist. The runbooks (`leg4_repackage_now.md`, `leg8_repackage_v1_3_2.md`) always pass `--skip-signing --skip-notarization` — that is the source of adhoc signing.
- Smoke verification §4-5 confirms exact symptoms: `adhoc` signature, no `TeamIdentifier`, `spctl --assess` rejected with exit 3, no stapled ticket.

**Fix**
- **NOT FIXABLE by PR 44 alone.** Requires Apple Developer Program enrollment ($99/yr) and the user to:
  1. Enroll at developer.apple.com.
  2. Install `Developer ID Application: <name> (<TEAMID>)` cert in keychain.
  3. Generate an app-specific password at appleid.apple.com.
  4. Export envs:
     ```bash
     export APPLE_ID="user@example.com"
     export TEAM_ID="ABCDE12345"
     export APP_SPECIFIC_PASSWORD="abcd-efgh-ijkl-mnop"
     ```
  5. Re-run `scripts/build_macos_dmg.sh` WITHOUT the `--skip-signing --skip-notarization` flags.
- **FLAGGED FOR USER:** if Apple enrollment is out of scope, PR 44's minimum bar is to bundle a clear README note (the smoke-report's §"Recommended README warning" is paste-ready) and rename the asset to remove the `universal2` lie (see P1 below).

### P1 — `universal2` label but arm64-only binary

**Evidence**
- `scripts/build_macos_dmg.sh` line 120: `DMG_NAME="Poker-Solver-${APP_VERSION}-universal2.dmg"` — filename is hardcoded `universal2`, regardless of what's actually built.
- `scripts/poker_solver.spec` line 104: `target_arch="arm64"` — PyInstaller is explicitly building a single-arch arm64 EXE.
- `assets/README.md` "Architecture: arm64 only" section explicitly says "The bundle targets Apple Silicon (M-series). The `target_arch=\"arm64\"` line in `scripts/poker_solver.spec` is load-bearing. Intel-Mac support is explicitly out of scope for v1.0.0."
- The `_rust.so` IS universal (`lipo -info` on `/Users/ashen/Desktop/poker_solver/poker_solver/_rust.cpython-313-darwin.so` shows both x86_64 and arm64 slices) — so the Rust extension is universal but the PyInstaller-bundled Python interpreter is arm64-only. The DMG filename was inherited from when the Rust .so universality was the headline; the Python side never followed.

So the spec/script are internally consistent (arm64 build, named universal2). The defect is **label vs. binary**.

**Fix — two options**
- **Option A (zero risk, recommended):** Stop lying. Change `DMG_NAME` in `scripts/build_macos_dmg.sh` from `Poker-Solver-${APP_VERSION}-universal2.dmg` to `Poker-Solver-${APP_VERSION}-arm64.dmg`. Update `leg4_repackage_now.md` already calls the artifact `-arm64.dmg` (line 66), so this aligns with one of the existing runbooks. The `leg8`/`leg9`/etc. plans that say `-universal2.dmg` should be updated to `-arm64.dmg`.
- **Option B (real fix, more work):** Actually build universal2. Requires:
  - `target_arch="universal2"` in `scripts/poker_solver.spec` line 104.
  - A universal2 Python framework (PyInstaller pulls slices from `sys.executable` — must be running a universal2 Python). The current `.venv` was created from `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13` per `.venv/pyvenv.cfg`; `file` it to confirm it's universal2.
  - Every transitive C-extension wheel must have x86_64 + arm64 slices. `numpy>=1.24`, `psutil>=5.9`, `lxml`, `pydantic-core`, `orjson`, `python-socketio`, plus the maturin-built `_rust.so` (already universal) all need universal2 binaries. NiceGUI 3.x's wheel deps include several with arch-specific binaries.
  - Cross-build invocation: `arch -x86_64 pyinstaller ...` from an arm64 host typically still produces single-arch output unless `target_arch=universal2` AND the underlying interpreter + extensions are universal.

Recommend Option A for PR 44 (a packaging-fix PR should not gold-plate scope into a cross-arch build expedition). Leave Option B as a follow-up ticket if Intel-Mac demand surfaces.

### P2 — `Info.plist` version stamp drift (0.6.0 vs v1.4.0)

**Evidence**
- `scripts/poker_solver.spec` lines 125-128: `version="0.6.0"`, `CFBundleShortVersionString = "0.6.0"`, `CFBundleVersion = "0.6.0"` — hardcoded.
- `poker_solver/__init__.py` line 192: `__version__ = "1.5.0"` (already past v1.4.0 toward v1.5.0).
- `pyproject.toml` line 7: `version = "1.5.0"`.
- `scripts/build_macos_dmg.sh` lines 114-117: derives `$APP_VERSION` from `__version__` in `poker_solver/__init__.py` and uses it for the DMG filename — but does NOT inject it into the spec. The spec's hardcoded `0.6.0` is what BUNDLE writes to `Info.plist`.

**Fix (minimal)**
- **Edit `scripts/poker_solver.spec`** lines 120-137 to read the version dynamically. PyInstaller execs the spec, so `os.environ.get("POKER_SOLVER_VERSION", ...)` or a direct read works:
  ```python
  import re
  version_match = re.search(
      r'__version__\s*=\s*[\'"]([^\'"]+)[\'"]',
      (REPO_ROOT / "poker_solver" / "__init__.py").read_text(),
  )
  APP_VERSION = version_match.group(1) if version_match else "0.0.0"

  app = BUNDLE(
      coll,
      name="Poker Solver.app",
      icon=ICON_PATH,
      bundle_identifier="com.poker_solver.app",
      version=APP_VERSION,
      info_plist={
          "CFBundleShortVersionString": APP_VERSION,
          "CFBundleVersion": APP_VERSION,
          ...
      },
  )
  ```
- Alternative: pass via env from `build_macos_dmg.sh` (`POKER_SOLVER_VERSION="$APP_VERSION" pyinstaller ...`) and read `os.environ["POKER_SOLVER_VERSION"]` in the spec. Equivalent.

---

## 2. Files to edit (summary)

| File | Edit | Priority |
|---|---|---|
| `pyproject.toml` | Add `nicegui>=3.0,<4.0` to `[project.optional-dependencies].distribution` | P0 |
| `scripts/poker_solver.spec` | Replace hand-listed `hiddenimports` with `collect_all("nicegui" / "fastapi" / "uvicorn" / "starlette" / "socketio" / "engineio")` merge | P0 |
| `scripts/poker_solver.spec` | Read `__version__` dynamically; remove hardcoded `0.6.0` | P2 |
| `scripts/build_macos_dmg.sh` | Pre-flight hard check: `python -c "import nicegui"` | P0 |
| `scripts/build_macos_dmg.sh` | Rename `DMG_NAME` to `${APP_VERSION}-arm64.dmg` (Option A) | P1 |
| `docs/pr11_prep/leg8_repackage_v1_3_2.md`, `docs/leg9_v1_4_0_ship_plan.md`, `docs/leg11_v1_4_1_ship_plan.md` | Update `-universal2.dmg` filename references to `-arm64.dmg` | P1 |
| `README.md` | Add macOS Gatekeeper bypass note (paste from smoke-report §"Recommended README warning") | P0 secondary (covers signing gap until Apple cert obtained) |
| `assets/README.md` | Bump `hiddenimports` recipe to reflect `collect_all` approach | P0 secondary |

No edits to `ui/app.py`, `scripts/pyinstaller_entry.py`, or any `poker_solver/*.py` — the runtime code is correct; this is a packaging-config bug.

---

## 3. Acceptance criteria

PR 44 ships when a fresh build artifact passes ALL of the following on a clean macOS check:

1. **Binary launches without ModuleNotFoundError.** `"/Volumes/Poker Solver/Poker Solver.app/Contents/MacOS/Poker Solver" --smoke-test` exits 0 (existing in-bundle smoke gate already covers `_rust`; extend to verify `nicegui` is importable: add `from nicegui import ui` to `_smoke_test` in `scripts/pyinstaller_entry.py`).
2. **`find` inside the .app bundle locates nicegui.** `find "/Volumes/Poker Solver/Poker Solver.app" -name nicegui -type d` returns at least one match (typically under `Contents/Resources/`).
3. **DMG mounts, .app structure intact.** Same as v1.4.0 (already passing — keep regression-free).
4. **`lipo -info` matches the filename claim.** Either:
   - DMG renamed to `-arm64.dmg` AND `lipo -info` reports `arm64` (Option A), OR
   - DMG remains `-universal2.dmg` AND `lipo -info` reports `arm64 x86_64` (Option B).
5. **`Info.plist` version matches the release tag.** `defaults read "/Volumes/Poker Solver/Poker Solver.app/Contents/Info" CFBundleShortVersionString` returns the same string as `git describe --tags --exact-match` (minus the `v` prefix).
6. **Bundle size within expected range.** ~80-150 MB (consistent with `repackage_feasibility.md` §5 "DMG size … 50-150 MB" envelope, bumped for NiceGUI + FastAPI + uvicorn now actually bundled). A 14 MB DMG indicates nicegui is still missing.
7. **(If user obtains Apple Developer ID)** `spctl --assess --verbose=4 --type execute /Volumes/Poker Solver/Poker Solver.app` exits 0 (`accepted`) and `xcrun stapler validate` confirms a stapled ticket. **PR 44 does NOT require this** — flagged separately as user-blocked.

---

## 4. Test plan for the PR

Local-only (no CI exists for packaging — confirmed `.github/workflows/` is absent).

```bash
# 1. Wipe + rebuild venv to mirror a clean machine
rm -rf .venv && python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[distribution]"
python -c "import nicegui, pyinstaller; print('deps OK')"

# 2. Rebuild Rust extension
maturin develop --release --target universal2-apple-darwin

# 3. Build the .dmg
bash scripts/build_macos_dmg.sh --skip-signing --skip-notarization

# 4. Acceptance gate
hdiutil attach "dist/Poker-Solver-$(grep __version__ poker_solver/__init__.py | cut -d\" -f2)-arm64.dmg"
"/Volumes/Poker Solver/Poker Solver.app/Contents/MacOS/Poker Solver" --smoke-test
find "/Volumes/Poker Solver/Poker Solver.app" -name "nicegui" -type d | head -3
lipo -info "/Volumes/Poker Solver/Poker Solver.app/Contents/MacOS/Poker Solver"
defaults read "/Volumes/Poker Solver/Poker Solver.app/Contents/Info" CFBundleShortVersionString
du -sh "/Volumes/Poker Solver/Poker Solver.app"
hdiutil detach "/Volumes/Poker Solver/"

# 5. Re-run the existing smoke verification protocol against the new DMG
# (steps 1-8 of docs/dmg_v1_4_0_smoke_verification.md)
```

A second-pass check on a co-worker's clean Mac (no `.venv`, no `pyenv` site-packages) is the gold standard but optional for PR 44 acceptance.

---

## 5. User-blocking items (flagged out of PR 44 scope)

- **Apple Developer Program enrollment** is required to reach signed + notarized distribution. Cost: $99/year. Without this, every shipped DMG carries the Gatekeeper warning unless the user manually right-clicks → Open.
- **Decision needed:** ship arm64-only forever (Option A — remove `universal2` from filename) vs invest in real universal2 (Option B — measurable build-time + bundle-size cost). PR 44 implements Option A by default; flag if Option B is preferred.

---

## 6. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| `collect_all("nicegui")` pulls in dev/test submodules that break PyInstaller analysis | Medium | Start with `collect_all`; if PyInstaller errors out, fall back to explicit `collect_submodules("nicegui") + collect_data_files("nicegui")` and prune empirically. The `assets/README.md` "Empirically-derived hidden-import list" recipe already documents this workflow. |
| Bundle size balloons past the spec's "<200 MB DMG" target | Medium | Audit with `du -sh dist/Poker\ Solver.app/Contents/{Frameworks,Resources}/*` after first build. If >200 MB, extend `excludes=` to drop NiceGUI's `nicegui/elements/lottie.py` JSON assets and other heavy optional features the app doesn't use. Per spec §12.3. |
| `collect_all("fastapi")` pulls in `fastapi.openapi.docs` which references CDN-hosted swagger-ui — works without offline but adds bytes | Low | Acceptable. App doesn't ship OpenAPI to end users. |
| Reading `__version__` from the spec via `Path.read_text()` fails on Windows builds | N/A | macOS-only build pipeline (`build_macos_dmg.sh`). No Windows path. |
| `pyinstaller_entry.py` `_smoke_test` extension to import nicegui pulls in a heavy import chain on every smoke run | Low | Run only when `--smoke-test` is passed. Trade ~0.5 s import time for hard guarantee. |

---

## 7. References (must read before implementing)

- PyInstaller hooks: https://pyinstaller.org/en/stable/hooks.html (`collect_all`, `collect_submodules`, `collect_data_files`)
- NiceGUI packaging notes: https://nicegui.io/documentation/section_pyinstaller (acknowledges PyInstaller hidden-import + datas requirement)
- Apple notarization: https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution
- Existing repo references already in code:
  - `scripts/poker_solver.spec` header
  - `scripts/build_macos_dmg.sh` lines 23-27
  - `assets/README.md` "Distribution / packaging" + "Empirically-derived `--hidden-import` list"
  - `docs/pr11_prep/repackage_feasibility.md`

---

## 8. Out-of-scope (deliberately not touched)

- Cross-platform packaging (Linux / Windows).
- Real universal2 binary (Option B above).
- CI/CD for packaging.
- DMG visual customization (background image, layout) — current `create-dmg` flags are fine.
- Migration from PyInstaller to `briefcase` / `py2app` / Nuitka. PR 11 already locked PyInstaller; alternatives are a separate epic.
