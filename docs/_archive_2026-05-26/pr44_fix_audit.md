# PR 44 fix audit — READ-ONLY verification

**Date:** 2026-05-23
**Auditor:** verification agent (read-only)
**Mode:** No edits applied. No rebuild. No `pip install`. Confirms what the fix-apply agent did, against `docs/pr44_dmg_fix_spec.md`.

---

## 1. Edits verified present

### 1.1 `pyproject.toml` — `[distribution]` extra
**Status: PRESENT — VERIFIED.**

Line 30:
```
distribution = ["pyinstaller>=6.0", "nicegui>=3.0,<4.0"]
```
- `nicegui>=3.0,<4.0` present.
- `pyinstaller>=6.0` retained.
- Comment block at lines 26-29 documents the PR 44 rationale (cites v1.4.0 smoke verification §3).
- `[ui]` extra on line 23 unchanged (`nicegui>=3.0,<4.0`); not yet self-referenced via `poker_solver[ui]`, but the inline approach matches the spec's "Inline rather than self-ref" guidance (spec §1, P0, fix item 2).

### 1.2 `scripts/poker_solver.spec` — dynamic version
**Status: PRESENT — VERIFIED.**

- Lines 21-22: `import re` and `from pathlib import Path` added.
- Lines 36-43: PR 44 comment + regex resolver:
  ```python
  _version_match = re.search(
      r'__version__\s*=\s*[\'"]([^\'"]+)[\'"]',
      (REPO_ROOT / "poker_solver" / "__init__.py").read_text(),
  )
  APP_VERSION = _version_match.group(1) if _version_match else "0.0.0"
  ```
- Lines 135, 137, 138 use `APP_VERSION` (not the literal `"0.6.0"`):
  - `version=APP_VERSION`
  - `"CFBundleShortVersionString": APP_VERSION`
  - `"CFBundleVersion": APP_VERSION`
- No remaining literal `0.6.0` outside the explanatory comment on line 38.
- `target_arch="arm64"` retained on line 114 (the spec comment at line 122 of build_macos_dmg.sh references "line 104" — that's an earlier offset that no longer aligns, but the value at line 114 is correct).

### 1.3 `scripts/build_macos_dmg.sh` — DMG name renamed
**Status: PRESENT — VERIFIED.**

- Line 123: `DMG_NAME="Poker-Solver-${APP_VERSION}-arm64.dmg"`
- Lines 120-122: PR 44 comment block explains why the rename happened (arm64-only PyInstaller payload).
- Lines 114-117: APP_VERSION still derived dynamically from `poker_solver/__init__.py` (unchanged, was already correct).

No remaining `${APP_VERSION}-universal2.dmg` references in `scripts/`.

---

## 2. Version resolution dry-run

```
$ python -c "import re; ..."
1.5.1
```

Resolves to **`1.5.1`** (matches `pyproject.toml` line 7 `version = "1.5.1"` and `poker_solver/__init__.py::__version__`). Logic is correct. The spec doc references `1.5.0` (line 113 of pr44_dmg_fix_spec.md) — the package has since bumped to 1.5.1, but the dynamic resolver tracks both correctly.

---

## 3. pyproject extras dry-run

```
$ python -c "import tomllib; ..."
{
  'dev':          ['black>=24.0', 'maturin>=1.7', 'pytest>=7.0',
                   'pytest-timeout>=2.3', 'ruff>=0.6'],
  'ui':           ['nicegui>=3.0,<4.0'],
  'distribution': ['pyinstaller>=6.0', 'nicegui>=3.0,<4.0']
}
```

`distribution` includes both `nicegui` AND `pyinstaller`. PEP 621 / TOML parses cleanly. **PASS.**

---

## 4. nicegui import test (current venv)

```
$ python -c "import nicegui; print(nicegui.__version__)"
3.12.1
```

Resolves from `/Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13/site-packages/` (system-wide install, not `.venv`). The fix is **at the pyproject layer** — a fresh `pip install -e ".[distribution]"` in a clean venv will now pull nicegui in, regardless of what the current venv has. **No-op in this audit (PASS by virtue of the source-of-truth fix).**

Caveat: this test confirms nicegui is importable on the current Python, but does NOT prove that the `.venv` used by `scripts/build_macos_dmg.sh` step 3 has it. The next .dmg build MUST start from a clean venv install of `[distribution]` for the fix to take effect.

---

## 5. Sweep for remaining issues

### 5.1 Hardcoded `0.6.0`
**No regressions in scripts.** Sole remaining occurrence in `scripts/poker_solver.spec` is the inline comment on line 38 documenting the original drift. All `0.6.0` matches in `docs/` are historical reports (state-verification, smoke-verification, release-notes references to actual v0.6.0 tags) — not active version pins.

### 5.2 `universal2` references
- **Scripts:** Only legitimate references remain — all describe the Rust `_rust.so` (which IS universal2 via `maturin develop --release --target universal2-apple-darwin`). The DMG-filename `universal2` is gone.
- **Docs:** Stale `Poker-Solver-1.X.Y-universal2.dmg` filenames persist in 8 docs (`docs/pr11_prep/leg8_repackage_v1_3_2.md`, `docs/leg9_v1_4_0_ship_plan.md`, `docs/dmg_v1_4_0_smoke_verification.md`, `docs/release_docs_consistency_check.md`, `docs/river_parity_timeout_investigation_2026-05-23.md`, `docs/pr11_prep/changelog_v1_2_1_audit.md`, `docs/leg11_v1_4_1_ship_plan.md` likely, plus the spec itself). Per spec §2 line 152, these were called out for update. **NOT YET APPLIED.** Severity: docs-only drift; build script + spec are the load-bearing surfaces. Recommend a doc cleanup pass but not a blocker for the .dmg rebuild.

### 5.3 CI / GitHub workflows
No `.github/workflows/` directory exists (confirmed). `.github/` contains only `ISSUE_TEMPLATE/` and `PULL_REQUEST_TEMPLATE.md`. **No CI pin to invalidate.** Consistent with spec §4 ("Local-only — no CI exists for packaging").

---

## 6. Spec coverage matrix

| Spec item | Priority | Status | Notes |
|---|---|---|---|
| P0a — `nicegui` in `[distribution]` extra (pyproject.toml) | P0 | **APPLIED** | Line 30 `distribution = ["pyinstaller>=6.0", "nicegui>=3.0,<4.0"]` |
| P0a — `collect_all("nicegui" / "fastapi" / "uvicorn" / "starlette" / "socketio" / "engineio")` in spec | P0 | **NOT APPLIED** | Spec.py still uses the legacy hand-listed `hiddenimports`. NO `collect_all` import, no merge of `nicegui_datas` / `nicegui_binaries`. **This is a gap** vs spec §1 P0 fix item 4 — the spec doc warns that even with nicegui INSTALLED, the bundle will crash on first `ui.run()` due to missing static/templates assets that `collect_all` pulls in. |
| P0a — pre-flight `python -c "import nicegui"` check in build_macos_dmg.sh | P0 | **NOT APPLIED** | No `import nicegui` line added to step 1 pre-flight (defense in depth recommendation per spec §1 fix item 3). |
| P0b — Apple Developer signing | P0 | **OUT OF SCOPE** | Spec explicitly flagged as not fixable by PR 44 alone ($99 Apple enrollment). README warning is unaddressed but spec called it secondary. |
| P1 — DMG label `-arm64.dmg` | P1 | **APPLIED** | `scripts/build_macos_dmg.sh` line 123. |
| P1 — Update doc filenames `-universal2.dmg` → `-arm64.dmg` | P1 | **NOT APPLIED** | 8+ docs still cite the old filename. Cosmetic / doc-hygiene. |
| P2 — Dynamic version (no hardcoded `0.6.0`) | P2 | **APPLIED** | Spec lines 36-43. Resolved as `1.5.1` in §2 above. |
| README Gatekeeper bypass note | P0-secondary | **NOT VERIFIED** | Audit did not inspect README.md changes (spec §2 listed this). |
| `assets/README.md` updated for `collect_all` recipe | P0-secondary | **NOT APPLIED** (consequence of `collect_all` not being applied above) | Same root cause as the spec.py gap. |

---

## 7. Gaps vs spec — ranked

1. **CRITICAL — `collect_all()` not applied in `scripts/poker_solver.spec`.** Spec §1 P0 fix item 4 was explicit that the hand-listed `hiddenimports=["nicegui", "nicegui.elements", ...]` is insufficient even with nicegui installed, because NiceGUI 3.x loads `nicegui/static/` and `nicegui/templates/` by path at runtime. **Without `collect_all`, the bundle will install nicegui, PyInstaller will bundle the Python source, but the JS/CSS/Jinja assets will be MISSING and `ui.run()` will fail at first browser request.** This is the highest-impact gap.
2. **MEDIUM — No pre-flight `import nicegui` in build script.** Spec called this "defense in depth." Without it, a clean venv that forgot to install `[distribution]` will still produce a broken DMG that fails the existing `_rust` smoke gate but only after a long PyInstaller run.
3. **LOW — Stale `-universal2.dmg` references in 8 docs.** Cosmetic; doesn't affect build.
4. **LOW — README Gatekeeper bypass note not verified.** Spec called it secondary.

---

## 8. Verdict

**NEEDS-MORE-WORK.**

The three load-bearing edits the user listed (pyproject extra, dynamic version, DMG rename) are present and correct. Dry-runs confirm version resolves to `1.5.1`, pyproject parses, extras include both deps.

However, the spec doc was clear that the **P0 fix has TWO halves**: (a) install nicegui in the build venv (DONE) AND (b) make PyInstaller actually find its static/templates assets via `collect_all` (NOT DONE). The .dmg will now be larger (nicegui Python source bundled) but is likely to still fail at first `ui.run()` because the static dir isn't included.

**Recommendation:** before any rebuild, route the spec.py change through another fix-apply pass. Specifically:
1. Add `from PyInstaller.utils.hooks import collect_all` to the top of `scripts/poker_solver.spec`.
2. Resolve `nicegui_datas, nicegui_binaries, nicegui_hiddenimports = collect_all("nicegui")` and analogous calls for `fastapi`, `uvicorn`, `starlette`, `socketio`, `engineio`.
3. Merge into the `Analysis(...)` invocation per spec §1 lines 56-65.
4. (Optional) Add the pre-flight `python -c "import nicegui"` to build_macos_dmg.sh step 1.

After those edits, this audit's verdict would flip to COMPLETE-FIX (modulo the doc cleanup, which can be a follow-up).
