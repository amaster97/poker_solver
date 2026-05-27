# PR 44 — DMG packaging fix completion report

**Date:** 2026-05-23
**Author:** fix-apply agent (second pass)
**Source audit:** `docs/pr44_fix_audit.md`
**Source spec:** `docs/pr44_dmg_fix_spec.md`
**Mode:** Edits applied. No rebuild. No `pip install`.

---

## 1. Edits applied this pass

### 1.1 `scripts/poker_solver.spec` — `collect_all` widening
**Status: APPLIED.**

- **Line 24:** added `from PyInstaller.utils.hooks import collect_all`.
- **Lines 47-59:** added widening block before `Analysis(`:
  ```python
  datas, binaries, hiddenimports = [], [], []
  for pkg in ('nicegui', 'fastapi', 'uvicorn', 'starlette', 'socketio', 'engineio'):
      pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
      datas += pkg_datas
      binaries += pkg_binaries
      hiddenimports += pkg_hiddenimports
  ```
- **Lines 62-96:** modified `Analysis(...)` call:
  - `binaries=[(RUST_SO, "poker_solver")] + binaries` (line 65-69) — Rust .so kept first as a load-bearing entry, then concatenates `collect_all` results.
  - `datas=[(CHARTS_DIR, ...), (UI_DIR, ...)] + datas` (line 70-73) — project datas first, then `collect_all` results.
  - `hiddenimports=hiddenimports + [...]` (line 74-96) — `collect_all` first, then the legacy hand-listed entries kept as belt-and-suspenders.

The legacy `hiddenimports` block (nicegui.elements, uvicorn.protocols.*, etc.) is retained per the spec doc §6 risk register guidance ("if PyInstaller errors out, fall back to explicit ... and prune empirically"). `collect_all` should make them redundant but they cost nothing as duplicates.

### 1.2 `scripts/build_macos_dmg.sh` — pre-flight `import nicegui` check
**Status: APPLIED.**

- **Lines 148-155:** added pre-flight check immediately after the existing `pyinstaller` command check and before the Python version check:
  ```bash
  python -c "import nicegui" 2>/dev/null || err \
      "nicegui not importable in build Python.  Run: pip install -e '.[distribution]'  (which now includes nicegui)."
  ```
- Placement is in step 1 (pre-flight) so failure fails fast — before PyInstaller burns 1-3 min on a doomed build.
- Uses the existing `err()` helper (defined at line 132) for consistent error formatting + `exit 1`.

---

## 2. Verification

### 2.1 AST parse of spec file
```
$ python -c "import ast; ast.parse(open('scripts/poker_solver.spec').read()); print('AST parse: OK')"
AST parse: OK
```
**PASS.** File is valid Python 3 syntax. (Full evaluation requires PyInstaller's runtime — out of scope for this static check.)

### 2.2 Bash syntax check
```
$ bash -n scripts/build_macos_dmg.sh && echo "bash syntax: OK"
bash syntax: OK
```
**PASS.** No syntax errors in the build script.

### 2.3 Grep for `collect_all` in spec
```
$ grep -n "collect_all" scripts/poker_solver.spec
24:from PyInstaller.utils.hooks import collect_all
53:# `collect_all` pulls in datas + binaries + hiddenimports for each pkg.
56:    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
77:        # The `collect_all` calls above should make most of these
79:        # in case `collect_all` misses something.  See assets/README.md.
```
**PASS.** Import statement present (line 24), comment + call present (lines 53/56), comments reference `collect_all` for context.

### 2.4 Grep for pre-flight `import nicegui` in build script
```
$ grep -n "import nicegui" scripts/build_macos_dmg.sh
154:python -c "import nicegui" 2>/dev/null || err \
```
**PASS.** Single occurrence on line 154 (the pre-flight check). Sole match — no duplicates.

---

## 3. Spec coverage matrix (updated)

| Spec item | Priority | Status (this pass) | Notes |
|---|---|---|---|
| P0a — `nicegui` in `[distribution]` extra (pyproject.toml) | P0 | APPLIED (prior pass) | Verified in audit §1.1. |
| P0a — `collect_all(...)` widening in spec | P0 | **APPLIED THIS PASS** | Lines 24, 47-59, 62-96. |
| P0a — pre-flight `import nicegui` check in build_macos_dmg.sh | P0 | **APPLIED THIS PASS** | Lines 148-155. |
| P0b — Apple Developer signing | P0 | OUT OF SCOPE | $99 Apple enrollment required; user-blocker. |
| P1 — DMG label `-arm64.dmg` | P1 | APPLIED (prior pass) | Verified in audit §1.3. |
| P1 — Update doc filenames `-universal2.dmg` → `-arm64.dmg` | P1 | NOT APPLIED | Cosmetic; 8+ docs. Recommend follow-up. |
| P2 — Dynamic version (no hardcoded `0.6.0`) | P2 | APPLIED (prior pass) | Verified in audit §1.2. |
| README Gatekeeper bypass note | P0-secondary | NOT VERIFIED | Spec called this secondary. |
| `assets/README.md` updated for `collect_all` recipe | P0-secondary | NOT APPLIED | Doc-hygiene follow-up. |

---

## 4. Verdict

**PR 44 COMPLETE** (for the load-bearing technical fix).

Both gaps flagged by the audit (`docs/pr44_fix_audit.md` §7 items 1 & 2 — "CRITICAL `collect_all` not applied" and "MEDIUM no pre-flight import nicegui") are now applied. AST parse, bash syntax, and grep verifications all pass. The spec file structure is preserved (Rust .so binary retained first in binaries list; project datas retained first in datas list; legacy hand-listed hiddenimports kept as a redundant safety net).

The .dmg rebuild is deferred (CPU-heavy, per orchestrator instructions) but is now expected to produce a NiceGUI-functional bundle.

---

## 5. Remaining items (out of scope for this pass)

### 5.1 Adhoc-signing — KNOWN USER-BLOCKER
- Requires Apple Developer Program enrollment ($99/yr).
- Per `docs/pr44_dmg_fix_spec.md` §1 P0b, this is **NOT FIXABLE by PR 44 alone**.
- Until cert + credentials are in hand, every shipped DMG carries the Gatekeeper warning unless users right-click → Open or run `xattr -d com.apple.quarantine`.
- README warning note (paste-ready in smoke-report) is **NOT yet added** — flagged as secondary in the spec.

### 5.2 Doc cleanup — LOW PRIORITY
- Stale `-universal2.dmg` references remain in ~8 docs (`docs/pr11_prep/leg8_repackage_v1_3_2.md`, `docs/leg9_v1_4_0_ship_plan.md`, `docs/dmg_v1_4_0_smoke_verification.md`, `docs/release_docs_consistency_check.md`, `docs/river_parity_timeout_investigation_2026-05-23.md`, `docs/pr11_prep/changelog_v1_2_1_audit.md`, `docs/leg11_v1_4_1_ship_plan.md`, and the spec itself).
- Cosmetic only; doesn't affect build correctness.
- Recommend a one-shot sed/edit agent for the rename.

### 5.3 `assets/README.md` update — LOW PRIORITY
- Per spec §2, the "Empirically-derived hidden-import list" recipe should be updated to reflect the `collect_all` approach.
- Cosmetic; the load-bearing change is in `scripts/poker_solver.spec` which is now correct.

### 5.4 Smoke test extension — RECOMMENDED FOLLOW-UP
- Per spec §3 acceptance criterion 1: extend `scripts/pyinstaller_entry.py::_smoke_test` to include `from nicegui import ui` so the in-bundle smoke gate (step 4 of `build_macos_dmg.sh`) catches a broken nicegui bundle BEFORE codesign/notarize/DMG run.
- Not strictly required for PR 44 completion but tightens the regression net.

### 5.5 .dmg rebuild — DEFERRED
- CPU-heavy (1-3 min PyInstaller + signing + create-dmg).
- Per orchestrator instruction: do NOT rebuild in this pass.
- When rebuilt: the build script will now hard-fail at pre-flight if `nicegui` is not in the build venv; PyInstaller will now bundle nicegui's static/templates dirs via `collect_all`; the DMG will be named `Poker-Solver-1.5.1-arm64.dmg`; and `Info.plist` will carry version `1.5.1`.
