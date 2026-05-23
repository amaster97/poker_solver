# PR 11 Agent B — macOS packaging (PyInstaller + codesign + notarize + .dmg)

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 11 Agent B.**
**Your scope:** the macOS packaging pipeline that takes the solver from "lives in `~/poker_solver/`" to "is an app on my Mac" — PyInstaller `.app` bundling, inside-out code signing, Apple notarization, DMG creation, and stapling. You own the entire signing/notarization toolchain plus an unsigned-fallback path that works without Apple Developer enrollment.
**Your contract:** produce `scripts/build_macos_dmg.sh` (~150 LOC), `scripts/sign_and_notarize.py` (~200 LOC), `scripts/entitlements.plist`, an `assets/poker_solver.icns` placeholder + `assets/README.md`, plus the `[project.optional-dependencies] distribution` group in `pyproject.toml`. Output: a notarizable `.app` and a stapled `.dmg`, with `--skip-signing --skip-notarization` for unsigned fallback.
**Your success criteria:** `./scripts/build_macos_dmg.sh --skip-signing --skip-notarization` produces a launchable unsigned `.app` + `.dmg` < 200 MB on M-series MacBook; the bundle imports `poker_solver._rust` successfully (the load-bearing smoke test); `sign_and_notarize.py` is callable from Python with explicit args; `--help` is useful; ALL existing tests still pass (your work is additive).
**File ownership:** you own `scripts/build_macos_dmg.sh`, `scripts/sign_and_notarize.py`, `scripts/entitlements.plist`, `assets/poker_solver.icns`, `assets/README.md`, plus the `[project.optional-dependencies] distribution` group in `pyproject.toml`. You may NOT modify any other file.

---

## Strict file ownership

**You own (create new):**
- `/Users/ashen/Desktop/poker_solver/scripts/build_macos_dmg.sh`
- `/Users/ashen/Desktop/poker_solver/scripts/sign_and_notarize.py`
- `/Users/ashen/Desktop/poker_solver/scripts/entitlements.plist`
- `/Users/ashen/Desktop/poker_solver/scripts/poker_solver.spec` (optional — PyInstaller spec file if you choose spec-driven over CLI-driven invocation; see §"PyInstaller invocation" below)
- `/Users/ashen/Desktop/poker_solver/assets/poker_solver.icns` (placeholder)
- `/Users/ashen/Desktop/poker_solver/assets/README.md` (how to regenerate the icon)

**You may modify (existing files, additive edits only):**
- `/Users/ashen/Desktop/poker_solver/pyproject.toml` — add the `[project.optional-dependencies] distribution = ["pyinstaller>=6.0"]` group. Do NOT add anything to default runtime deps (PyInstaller is opt-in via `pip install -e .[distribution]`). Spec §8.
- (Optional) `/Users/ashen/Desktop/poker_solver/README.md` — append a "Distribution / packaging" section documenting the build flow + Apple Developer enrollment + unsigned-fallback bypass. Only if the README exists; otherwise skip.

**You must NOT touch:**
- `poker_solver/library.py`, `poker_solver/library_schema.sql`, `poker_solver/__init__.py`, `poker_solver/cli.py` — Agent A
- `scripts/batch_solve.py` — Agent C
- Any test file (`tests/test_library*.py`) — Agent C
- Any other `poker_solver/*.py` — read-only references
- `ui/*` — gated on PR 10; out of scope

If you discover that an Apple/PyInstaller workflow conflicts with the spec, **do not silently change it**. Stop and write a short note to the orchestrator describing the conflict; the orchestrator will reconcile.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/pr11_spec.md`. Internalize §6 (entire macOS packaging section: §6.1 tool choice, §6.2 bundle contents, §6.3 PyInstaller invocation, §6.4 code signing, §6.5 notarization, §6.6 DMG creation, §6.7 unsigned fallback), §7 (files to create — your subset), §11 critical items 5+6 (DMG reproducibility, unsigned-fallback functional), §12 risks 12.1 (PyInstaller may miss `_rust.so` — your top risk), 12.3 (DMG size), 12.6 (Xcode CLT required), 12.7 (NiceGUI quirks), 12.8 (notarization rejections), §13 decisions 13.1, 13.6, 13.7, 13.8, 13.10.
2. **The PLAN (locked decisions):** `/Users/ashen/Desktop/poker_solver/PLAN.md`. "MacBook-only, no cloud spend"; the arm64-only target is the user's hardware.
3. **PyInstaller documentation:** https://pyinstaller.org/en/stable/usage.html (cited inline in spec §15). The load-bearing facts: `--windowed` creates `.app` on macOS; `--onedir` is recommended over `--onefile` for code-signed bundles; `--add-binary SOURCE:DEST` is required for native dynamic libraries (your `_rust.so`).
4. **Apple notarization docs:** https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution and https://developer.apple.com/documentation/security/customizing-the-notarization-workflow (cited inline in spec §15). The load-bearing facts: macOS 10.15+ requires notarization; `xcrun notarytool submit --wait` is the command; `xcrun stapler staple` embeds the ticket.
5. **The repo layout:** `ls /Users/ashen/Desktop/poker_solver/poker_solver/` — confirm the maturin-built `.so` lives at `poker_solver/_rust.cpython-313-darwin.so` (spec §6.2 point 3 + §12.1).
6. **Existing scripts directory pattern:** `ls /Users/ashen/Desktop/poker_solver/scripts/` — `check_pr.sh`, `generate_pushfold_charts.py`, `setup_references.sh`. Match the style (executable bash, leading shebang, `set -euo pipefail`, usage block at top).

## Default decisions LOCKED (do not deviate)

These are amendments / clarifications to the PR 11 spec; if the spec text differs, **these locked defaults win** because the user confirmed them in the brief:

- **Packaging tool: PyInstaller** (>= 6.0), not Briefcase, not Nuitka. Spec §6.1, decision 13.8.
- **Bundle architecture: arm64 only.** No universal2. PLAN.md hardware target is Apple Silicon. Decision 13.6.
- **DMG size target: < 200 MB.** Trim via `--exclude-module` (unittest, idlelib, turtle, tkinter). Spec §12.3.
- **Apple Developer enrollment: OPTIONAL.** The script supports `--skip-signing --skip-notarization` for unsigned `.app` + `.dmg`. Unsigned bypass documented: right-click → "Open", or `xattr -d com.apple.quarantine`. Decision 13.1, spec §6.7.
- **PyInstaller mode: `--onedir`** (NOT `--onefile`). Per PyInstaller docs: `--onefile` "requires unpacking on each run" and breaks code-signing of inner files. Decision 13.8.
- **DMG window styling: plain default DMG** (volume icon + Applications symlink). No custom background. Decision 13.7.
- **`create-dmg` tool: Homebrew formula** (`brew install create-dmg`), NOT sindresorhus npm package. Keeps toolchain in Homebrew, avoids Node dep. Decision 13.10.
- **Bundle identifier:** `com.poker_solver.app` (consistent with spec §6.3).
- **App name:** `Poker Solver` (with space, as a user-facing label; the binary path inside the bundle is `Poker Solver.app/Contents/MacOS/Poker Solver`).
- **Entry point:** `ui/main.py` (spec §6.3). If `ui/main.py` does not exist at build time (because PR 10 hasn't landed), the script must abort with a clear error: "ui/main.py not found — PR 10 (NiceGUI scaffold) is a prerequisite." Decision 13.13.

## Top risk to flag prominently (spec §12.1)

> **PyInstaller may fail to bundle the maturin-built Rust extension `poker_solver/_rust.cpython-313-darwin.so`.**

PyInstaller's static analysis finds Python imports via AST walking; it does **not** know that `from poker_solver import _rust` resolves to a `.so` file because the import is wired at C-API level by PyO3's `#[pymodule]` macro. The symptom is: the bundled `.app` launches successfully, then crashes on the first call into `_rust` (e.g., when `solver.py` checks if a Rust backend exists).

**Required mitigations (all of these, not just one):**

1. **Explicit `--add-binary` flag.** Pass `--add-binary "poker_solver/_rust.cpython-313-darwin.so:poker_solver"` to PyInstaller. The `:poker_solver` destination maps the file into the bundled `poker_solver/` package. Test that the source `.so` exists before invoking PyInstaller; if missing, abort with a clear error pointing the user at `maturin develop`.
2. **In-bundle smoke test step.** After `pyinstaller` succeeds (and BEFORE codesign, notarize, DMG), run the bundled binary headlessly with a script that does `from poker_solver import _rust; print(_rust)` and fail the build with a clear error message if the import fails. This catches the issue at build time, not at user install time.
3. **Document the failure mode** in `sign_and_notarize.py`'s troubleshooting section and in `assets/README.md`. The audit agent will intentionally omit `--add-binary` and verify your smoke test catches it (spec §17).

This risk is the single most important thing in your scope. Plan for it; don't paper over it.

## Public surface (other agents + downstream PRs depend on this)

### `scripts/build_macos_dmg.sh`

CLI:
```
./scripts/build_macos_dmg.sh [OPTIONS]

Options:
  --skip-signing          Skip code signing (produces unsigned .app + .dmg)
  --skip-notarization     Skip Apple notarization (still signs if --skip-signing not set)
  --version VERSION       App version string (default: read from poker_solver/__init__.py __version__)
  --apple-id EMAIL        Apple ID for notarization (or env APPLE_ID)
  --team-id TEAMID        Developer Team ID (or env TEAM_ID)
  --password PASSWORD     App-specific password (or env APP_SPECIFIC_PASSWORD)
  --identity NAME         Code signing identity (default: "Developer ID Application: ...")
  --output-dir PATH       Output directory (default: dist/)
  --no-smoke-test         Skip the post-build _rust import smoke test (dangerous; debug only)
  --help                  Show this help and exit
```

Pipeline (orchestrated in `build_macos_dmg.sh`):
1. **Pre-flight checks.** Verify `python` (3.13), `pyinstaller` (>=6.0), `xcrun` (Xcode CLT), `create-dmg` (Homebrew), the `_rust.so` file exists. Abort with clear error if any missing. Spec §12.6.
2. **Clean.** `rm -rf build/ dist/` if present.
3. **PyInstaller.** Invoke per §"PyInstaller invocation" below.
4. **In-bundle smoke test.** Run `dist/Poker Solver.app/Contents/MacOS/Poker Solver --smoke-test` (or invoke the bundled Python interpreter directly with a `-c` import). Fail the build if `_rust` doesn't import. Top-risk mitigation.
5. **Code sign (if not `--skip-signing`).** Delegate to `python scripts/sign_and_notarize.py sign-bundle ...`. Inside-out walk per spec §6.4.
6. **Notarize (if not `--skip-notarization`).** Delegate to `python scripts/sign_and_notarize.py notarize ...`. Spec §6.5.
7. **Staple.** Delegate to `python scripts/sign_and_notarize.py staple ...`.
8. **Build DMG.** `create-dmg` invocation per spec §6.6.
9. **Sign DMG (if not `--skip-signing`).** Same identity.
10. **Notarize DMG + staple DMG (if not `--skip-notarization`).** Apple wants both `.app` and `.dmg` notarized.
11. **Report.** Print final DMG path, size, and whether signing/notarization happened.

The script uses `set -euo pipefail` and exits non-zero on any failure. Each step prints a `[step N/11] <description>` banner so the user can see progress.

### `scripts/sign_and_notarize.py`

CLI sub-tools (so the python script is callable both from `build_macos_dmg.sh` and standalone):
```
python scripts/sign_and_notarize.py sign-bundle <bundle_path> --identity NAME --entitlements PATH
python scripts/sign_and_notarize.py notarize <zip_or_dmg> --apple-id EMAIL --team-id ID --password PWD
python scripts/sign_and_notarize.py staple <target>
python scripts/sign_and_notarize.py sign-inside-out <bundle_path> --identity NAME --entitlements PATH
```

Python API (for reuse from CI/future scripts):
```python
def sign_bundle(bundle_path: Path, identity: str, entitlements: Path) -> None:
    """Sign the outer .app bundle with codesign. Hardened Runtime, deep, force."""

def sign_inside_out(bundle_path: Path, identity: str, entitlements: Path) -> None:
    """Walk Contents/, sign every .dylib and .so with the same identity, then sign the outer .app.

    Spec §6.4: 'codesign --deep ... is unreliable on PyInstaller bundles.' We do an explicit
    find Contents -name "*.dylib" -o -name "*.so" walk and sign each file individually with
    --options runtime, then sign the outer .app.
    """

def notarize(target: Path, apple_id: str, team_id: str, password: str,
             timeout_minutes: int = 60) -> dict:
    """Submit target (.zip for .app, or .dmg) to Apple notarization.
    Blocks on --wait. Returns the notarization result dict.

    On failure, captures `notarytool log <submission-id>` JSON output to
    `dist/notarization_failure.log` for debugging. Spec §6.5.

    Raises:
        NotarizationError: if Apple rejects or the submission times out.
    """

def staple(target: Path) -> None:
    """xcrun stapler staple <target>. Embeds the notarization ticket
    so the .app validates offline. Spec §6.5."""
```

### `scripts/entitlements.plist`

Match spec §6.4 exactly:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.cs.allow-jit</key><true/>
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key><true/>
    <key>com.apple.security.cs.disable-library-validation</key><true/>
</dict>
</plist>
```

Justification (document at the top of the file as XML comments):
- `allow-jit` — NumPy / Python use JIT-like patterns. Safe per Apple docs.
- `allow-unsigned-executable-memory` — required for the Python interpreter on modern macOS.
- `disable-library-validation` — required because PyInstaller bundles dylibs from PyPI/maturin signed by other parties.

### `assets/poker_solver.icns` + `assets/README.md`

The `.icns` is a placeholder until the user supplies a real icon. Generate it from a 1024×1024 placeholder PNG via `iconutil` (documented in `assets/README.md`). A minimal `.icns` placeholder can be a single-color square; the goal is "the build pipeline doesn't break on a missing icon".

`assets/README.md` documents:
- The `iconutil` command to convert a `.iconset/` directory to `.icns`.
- The required iconset entries (16×16 through 1024×1024 in `@1x` + `@2x`).
- How to replace the placeholder with a custom icon.

### `pyproject.toml` distribution group

```toml
[project.optional-dependencies]
distribution = ["pyinstaller>=6.0"]
```

Install via `pip install -e .[distribution]`. Documented in `assets/README.md` or the script `--help`.

## PyInstaller invocation (spec §6.3, the load-bearing surface)

```bash
pyinstaller \
    --windowed \
    --onedir \
    --name "Poker Solver" \
    --osx-bundle-identifier "com.poker_solver.app" \
    --icon assets/poker_solver.icns \
    --add-binary "poker_solver/_rust.cpython-313-darwin.so:poker_solver" \
    --add-data "poker_solver/charts:poker_solver/charts" \
    --add-data "ui:ui" \
    --hidden-import "nicegui.elements" \
    --hidden-import "nicegui.functions" \
    --exclude-module "unittest" \
    --exclude-module "idlelib" \
    --exclude-module "turtle" \
    --exclude-module "tkinter" \
    --noconfirm \
    ui/main.py
```

You may prefer a `.spec` file (`scripts/poker_solver.spec`) over the CLI form. The `.spec` form is more readable when the arg list grows; pick whichever is clearer. If you use a `.spec` file, the `build_macos_dmg.sh` invocation is `pyinstaller scripts/poker_solver.spec`.

`--hidden-import` list: the initial entries above are guesses. Real list assembled empirically — when the smoke test fails with `ModuleNotFoundError: No module named 'X'`, add `--hidden-import X` and rebuild. Document the empirically-derived list in `assets/README.md` for posterity.

## Code signing (spec §6.4)

Per Apple docs (cited in spec §15): macOS notarization requires Hardened Runtime (`--options runtime`) on every signed binary. The inside-out walk is the load-bearing pattern because `codesign --deep` "claims to walk recursively but is unreliable on PyInstaller bundles" (spec §6.4).

Pseudo-code for `sign_inside_out`:
```python
def sign_inside_out(bundle_path: Path, identity: str, entitlements: Path) -> None:
    contents = bundle_path / "Contents"
    # Find every dynamic library and sign it.
    for so in itertools.chain(
        contents.rglob("*.dylib"),
        contents.rglob("*.so"),
    ):
        subprocess.run([
            "codesign", "--force", "--sign", identity,
            "--options", "runtime",
            "--entitlements", str(entitlements),
            str(so),
        ], check=True)
    # Sign the outer .app last (this is the "outside" of the inside-out).
    subprocess.run([
        "codesign", "--deep", "--force", "--sign", identity,
        "--options", "runtime",
        "--entitlements", str(entitlements),
        str(bundle_path),
    ], check=True)
```

Verify post-sign with `codesign --verify --deep --strict --verbose=2 "Poker Solver.app"` and `spctl --assess --type execute --verbose "Poker Solver.app"`.

## Notarization (spec §6.5)

```bash
ditto -c -k --keepParent "dist/Poker Solver.app" "Poker Solver.zip"
xcrun notarytool submit "Poker Solver.zip" \
    --apple-id "$APPLE_ID" \
    --team-id "$TEAM_ID" \
    --password "$APP_SPECIFIC_PASSWORD" \
    --wait
xcrun stapler staple "dist/Poker Solver.app"
```

On notarization failure, `notarytool log <submission-id>` returns JSON pointing at the problem binaries. Capture this to `dist/notarization_failure.log` for debugging.

The `$APP_SPECIFIC_PASSWORD` is generated at appleid.apple.com (user-provided, never committed). The script reads from environment variables `APPLE_ID`, `TEAM_ID`, `APP_SPECIFIC_PASSWORD` if not supplied via CLI flags. If neither is present and `--skip-notarization` is NOT set, abort with a clear error.

## DMG creation (spec §6.6)

```bash
brew install create-dmg  # one-time setup; the script should check and abort if missing.

create-dmg \
    --volname "Poker Solver" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 100 \
    --icon "Poker Solver.app" 175 190 \
    --hide-extension "Poker Solver.app" \
    --app-drop-link 425 190 \
    "Poker-Solver-${VERSION}-arm64.dmg" \
    "dist/Poker Solver.app"
```

The DMG itself is also signed and notarized (spec §6.6 line 456-460).

Output: `dist/Poker-Solver-<version>-arm64.dmg`. Drag-to-Applications install.

## Unsigned fallback (spec §6.7)

```bash
./scripts/build_macos_dmg.sh --skip-signing --skip-notarization
```

Output: an unsigned `.app` + unsigned `.dmg`. The build script's `--help` output documents two bypass methods:
1. **Right-click → "Open"** in Finder (bypasses Gatekeeper once per user).
2. **Permanent trust:** `xattr -d com.apple.quarantine "dist/Poker Solver.app"` to permanently mark trusted on this machine.

Both are mentioned in `assets/README.md` and the script's `--help`.

## Critical correctness items

### 1. Top risk: PyInstaller misses `_rust.so` (spec §12.1)

Already covered above. Smoke test step is mandatory. Audit agent will intentionally omit `--add-binary` and verify your smoke test catches it (spec §17).

### 2. Unsigned-fallback path is functional (spec critical item 6)

`./scripts/build_macos_dmg.sh --skip-signing --skip-notarization` must produce an `.app` that opens after right-click bypass. Test this on the user's M-series MacBook before reporting done.

### 3. DMG size < 200 MB (spec §12.3, target soft constraint)

Empirical estimate (spec §12.3): Python (~30 MB) + NumPy (~40 MB) + NiceGUI/uvicorn/starlette (~30 MB) + `_rust.so` (~5 MB) + other deps (~10 MB) + stdlib (~50 MB after exclusions) = ~165 MB. Within budget.

If exceeded, document the size in the build output and accept it (200 MB DMG download is not a UX dealbreaker). Soft constraint, not a hard failure.

### 4. DMG reproducibility (spec critical item 5)

Same source + same env → same unsigned PyInstaller payload bytes. Signed/notarized bytes differ on each run (Apple-side timestamps). Document this property in `build_macos_dmg.sh`'s docstring at the top.

Reproducibility test: build twice with `--skip-signing --skip-notarization`, then `shasum dist/.../*.so` — should match. (You don't need to write this test; just document the property and confirm it manually.)

### 5. License hygiene (spec §17 audit focus)

PyInstaller is GPL-with-exception. The exception covers bundled apps. Verify no new AGPL/GPL deps are introduced via PyInstaller's transitive deps. Audit agent will check this. Add a brief note in `assets/README.md` about the PyInstaller license exception.

### 6. Xcode Command Line Tools required (spec §12.6)

`xcrun notarytool` requires Xcode CLT. `build_macos_dmg.sh` checks for `xcrun` presence in the pre-flight section and aborts with a clear error if missing:
```
ERROR: xcrun not found. Install Xcode Command Line Tools:
  xcode-select --install
```

### 7. Inside-out signing hits every binary (spec §17 audit focus)

The walk finds every `.dylib` and `.so` in `Contents/`. Audit agent will sample the bundle and assert every dylib/so carries a signature. Make sure your walk uses `rglob`, not `glob`, so nested `Frameworks/` are covered.

### 8. `--help` is useful (spec §16 success criterion)

Every script must have a working `--help`. For `build_macos_dmg.sh`, use a simple `if [[ "$1" == "--help" ]]; then ... fi` block at the top, before `set -euo pipefail`'s strictness kicks in. For `sign_and_notarize.py`, use argparse with descriptions on every flag.

## Quality bar

- **Shell scripts pass `shellcheck`:** `shellcheck scripts/build_macos_dmg.sh` reports no errors. If `shellcheck` is not installed on the user's machine, skip this check but make the script clean by inspection.
- **Python scripts ruff + black clean:** `ruff check scripts/sign_and_notarize.py` and `black --check scripts/sign_and_notarize.py` clean.
- **mypy clean (not strict):** `mypy scripts/sign_and_notarize.py` reports no errors. (Strict mypy is library-internal only.)
- **No new runtime deps in `pyproject.toml`:** only the `distribution` optional-deps group. `pip install -e .` produces an unchanged environment.
- **All existing tests still pass.** Run `pytest -x` after your work lands. Packaging is purely additive; you should not break tests, but a typo in `pyproject.toml` could break installation — guard against this.
- **Code size budget: ~150 LOC** for `build_macos_dmg.sh`, ~200 LOC for `sign_and_notarize.py` per spec §7. Stay within budget; do not over-engineer.

## Reference-first rule

Before any technical claim, citation, or formula, check the local references. Never extrapolate from training data when a local authoritative source exists.

- PyInstaller usage: https://pyinstaller.org/en/stable/usage.html — cited inline in spec §15.
- Apple notarization: https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution — cited inline in spec §15.
- Apple notarization workflow customization: https://developer.apple.com/documentation/security/customizing-the-notarization-workflow — cited inline in spec §15.
- `create-dmg` (Homebrew formula): https://github.com/create-dmg/create-dmg — cited inline in spec §15. Decision 13.10 picks this over the sindresorhus npm package.

If a fact about Apple tooling differs from what you remember from training, prefer the cited Apple doc.

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Lint
shellcheck scripts/build_macos_dmg.sh || echo "shellcheck not installed; skipping"
ruff check scripts/sign_and_notarize.py
black --check scripts/sign_and_notarize.py
mypy scripts/sign_and_notarize.py

# 2. Scripts are executable
test -x scripts/build_macos_dmg.sh && echo "build script executable OK"

# 3. Help works
./scripts/build_macos_dmg.sh --help | head -30
python scripts/sign_and_notarize.py --help

# 4. Unsigned-fallback build smoke test (M-series MacBook only)
# NOTE: this requires pyinstaller installed via the distribution extras:
#   pip install -e .[distribution]
# And maturin develop has been run to produce poker_solver/_rust*.so
test -f poker_solver/_rust.cpython-313-darwin.so || echo "WARNING: _rust.so missing — run maturin develop first"

# Only run the full build if the prereqs above are met:
./scripts/build_macos_dmg.sh --skip-signing --skip-notarization 2>&1 | tail -40
test -d "dist/Poker Solver.app" && echo "unsigned .app produced OK"
ls -lh dist/*.dmg && du -sh dist/*.dmg

# 5. In-bundle _rust smoke test (the load-bearing risk mitigation)
# The build script should run this internally; verify it ran:
grep -q "_rust" dist/build.log 2>/dev/null && echo "smoke test logged" || echo "(check stdout from step 4)"

# 6. pyproject.toml changes
git diff pyproject.toml
# Should show ONLY the [project.optional-dependencies] distribution group added.

# 7. Full test suite must still pass
pytest -x 2>&1 | tail -20
```

If any of the above fails, fix the issue before reporting done. If a smoke test reveals a spec ambiguity, **stop and flag it** — do not silently work around it.

## Report back format

When done, write a concise report (≤300 words) covering:

1. Files created/modified with line counts.
2. Any spec amendment you made or contract drift you flagged (and why).
3. Verification command output (paste tails). Critical: confirm the unsigned-fallback DMG actually built and `_rust` imports inside the bundle.
4. DMG size in MB.
5. Any open question you couldn't resolve from the spec or PLAN — flag for human review.
6. License attributions (PyInstaller GPL-with-exception note).
