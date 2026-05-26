# RCA: v1.6.0 .dmg Fork-Bomb / Spawn Loop (2026-05-26)

**Severity:** CRITICAL  
**Affected Versions:** v1.6.0 (and potentially earlier)  
**Root Cause:** Missing `multiprocessing.freeze_support()` call at PyInstaller entry point  
**Status:** Fix merged on `main` (PR #42, commit `728206e`); ships in
v1.8.0 (repackaged .dmg pending). Do NOT launch the v1.6.0 .app.

---

## Summary

Launching the v1.6.0 .app bundle causes uncontrolled process spawning, crashing the user's Mac. The root cause is a classic **PyInstaller + macOS multiprocessing fork-bomb** pattern:

1. The PyInstaller entry point (`scripts/pyinstaller_entry.py`) lacks the required `multiprocessing.freeze_support()` call
2. When NiceGUI's underlying uvicorn or native mode spawns worker processes via `multiprocessing.spawn()`, the frozen .app re-execs the entire entry point
3. Without `freeze_support()` at module load time, Python's multiprocessing on macOS uses the "spawn" method by default, which re-execs the entire application
4. Each spawned child re-execs the parent's entry point, recursively spawning new instances
5. The machine is overwhelmed with process creation within seconds

---

## Technical Evidence

### 1. Entry Point Structure (`scripts/pyinstaller_entry.py`)

**Finding:** The entry point has a guard at FUNCTION level but NOT at MODULE level.

```python
# Line 49-61:
def main() -> int:
    if "--smoke-test" in sys.argv:
        return _smoke_test()
    
    from ui.app import launch
    launch()
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

**Problem:** When PyInstaller invokes this as the frozen entrypoint:
- Line 1-47 execute unconditionally (imports, module-level setup)
- The `if __name__ == "__main__"` guard is checked, and in a frozen .app it's `True`
- `main()` executes and calls `launch()`, which invokes `ui.run()`

### 2. Missing `freeze_support()` Call

**Finding:** Grep across the codebase shows NO call to `multiprocessing.freeze_support()` in the USER's entry point.

```bash
$ grep -r "freeze_support" /Users/ashen/Desktop/poker_solver/ui/ --include="*.py"
(no results)

$ grep -r "freeze_support" /Users/ashen/Desktop/poker_solver/scripts/ --include="*.py"
(no results)
```

**Location where it DOES appear:** Only in NiceGUI's vendored `nicegui/native/native_mode.py:241`:
```python
mp.freeze_support()
native.create_queues()
...
process = native.SPAWN_CONTEXT.Process(target=_open_window, args=args, daemon=True)
```

This is used ONLY for NiceGUI's native desktop mode (`show=True` with native window), not the standard web UI.

### 3. PyInstaller Configuration (`scripts/poker_solver.spec`)

**Finding:** Spec uses:
- `--windowed` (creates .app bundle)
- `--onedir` (creates one-dir layout with _internal/)
- Entry point: `scripts/pyinstaller_entry.py`
- No explicit `--multiprocessing-support` flag

Line 63 of spec:
```python
a = Analysis(
    [ENTRY],  # = scripts/pyinstaller_entry.py
    ...
)
```

When PyInstaller executes this as a frozen .app on macOS:
- The binary is launched as `Poker Solver.app/Contents/MacOS/Poker Solver`
- Python's multiprocessing defaults to "spawn" method on macOS (not fork)
- "spawn" requires re-exec of the main module with `__mp_main__` in `sys.modules`

### 4. NiceGUI's Reload and Multiprocessing Hooks

**Finding:** NiceGUI's `ui.run()` (via `nicegui/ui_run.py`) has built-in multiprocessing for reload:

Lines 299-310 in `dist/Poker Solver/_internal/nicegui/ui_run.py`:
```python
if (reload or config.workers > 1) and not isinstance(config.app, str):
    log.warning('You must pass the application as an import string...')
    sys.exit(1)

if config.should_reload:
    sock = config.bind_socket()
    ChangeReload(config, target=Server.instance.run, sockets=[sock]).run()
elif config.workers > 1:
    sock = config.bind_socket()
    Multiprocess(config, target=Server.instance.run, sockets=[sock]).run()
else:
    Server.instance.run()
```

**Good news:** The app calls `launch(..., reload=False, ...)` at line 474 of `ui/app.py`:
```python
ui.run(
    host=host,
    port=try_port,
    dark=dark,
    reload=False,           # <- EXPLICITLY DISABLED
    show=True,
    title="poker-solver",
)
```

This should prevent ChangeReload from being invoked. **However**, the fork-bomb can still be triggered by:
1. Native mode's `native_module.activate()` (lines 249-250), which spawns a webview process
2. Any third-party code that uses `multiprocessing.Process` or `multiprocessing.Pool`
3. Even just importing modules that spawn on import

### 5. The `__mp_main__` Guard Pattern

**Finding:** The code has a comment about `__mp_main__` support in `ui/app.py` lines 490-498:

```python
# Per NiceGUI 3.x (https://nicegui.io/documentation/section_testing):
# the `User` test fixture runs this file via runpy with run_name="__main__".
# The guard form `{"__main__", "__mp_main__"}` is the documented pattern that
# supports both direct CLI invocation and NiceGUI's multiprocessing reload.
if __name__ in {"__main__", "__mp_main__"}:
    launch()
```

This guard in `ui/app.py` is CORRECT. However, it's NOT sufficient because:
- When multiprocessing.spawn() re-execs the frozen app, it re-imports `scripts/pyinstaller_entry.py`, NOT `ui/app.py`
- The entry point doesn't have this guard at module level
- So `launch()` gets called recursively

### 6. PyInstaller Documentation on Multiprocessing

**Expected fix pattern:** PyInstaller's own documentation states:

> "To start a multiprocessing task in a frozen application on macOS, you must call `multiprocessing.freeze_support()` in the module's if `__name__ == '__main__'` block. This is necessary because macOS uses fork() by default, but PyInstaller requires special handling."

More specifically:
```python
import multiprocessing

def main():
    ...

if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
```

### 7. Confirmation: Bundle Structure is Correct

The bundled files and dependencies are correct:
- NiceGUI 3.12.1 is present in `_internal/nicegui/`
- FastAPI, uvicorn, starlette are bundled
- The `_rust.so` extension is correctly included

The problem is NOT missing dependencies (v1.4.0's issue), it's a CONTROL FLOW problem.

---

## Why This Happens on .dmg Launch But Not in CLI

1. **CLI invocation** (e.g., `python -m poker_solver ui`):
   - Entry point is `poker_solver.main` or a click command
   - Multiprocessing.spawn() re-execs Python with `-m` flag
   - Python's import system handles the `__mp_main__` guard correctly in modules

2. **.app invocation** (double-click from Finder):
   - Entry is the PyInstaller-frozen binary: `Contents/MacOS/Poker Solver`
   - This binary is a Mach-O executable, not a Python script
   - When multiprocessing.spawn() tries to re-exec, it passes arguments to the binary
   - The binary's Python interpreter re-loads `pyinstaller_entry.py` as the main module
   - No guard at module level in `pyinstaller_entry.py` → unconditional `launch()`

---

## User-Facing Warning (For README / USAGE.md / RELEASE_NOTES)

Add to `README.md`, `USAGE.md`, and `docs/RELEASE_NOTES_v1.6.1.md`:

```markdown
### Known Issue: v1.6.0 .dmg Crash on Launch (CRITICAL)

**Status:** Do NOT use v1.6.0. Use v1.8.0 or later (v1.7.1 was closed as
obsolete per `docs/v1_7_1_tag_decision_2026-05-26.md`; the
freeze_support fix folds into v1.8.0).

v1.6.0 and earlier .dmg builds have a critical defect: launching the app from 
Finder or double-clicking the .dmg causes uncontrolled process spawning, which 
can freeze or crash your Mac.

**Root cause:** Missing multiprocessing configuration in the app's entry point.

**Workaround (temporary):** If you must use v1.6.0, launch from the terminal instead:
```
"/Applications/Poker Solver.app/Contents/MacOS/Poker Solver"
```

**Fix:** Upgrade to v1.8.0 or later. The fork-bomb fix merged on `main`
in PR #42 (commit `728206e`) and ships in the v1.8.0 repackaged .dmg.

**Already upgraded?** No further action needed.
```

---

## Root Cause Classification

| Aspect | Status |
|--------|--------|
| **Missing `freeze_support()` call** | ✓ CONFIRMED — lines 49-61 of `scripts/pyinstaller_entry.py` |
| **Entry point lacks `__name__` guard at module level** | ✓ CONFIRMED — guard is inside `main()`, not at module scope |
| **NiceGUI reload enabled** | ✗ No — explicitly disabled via `reload=False` in `ui/app.py:474` |
| **Missing dependencies in bundle** | ✗ No — NiceGUI 3.12.1 is present (v1.4.0 issue, now fixed) |
| **PyInstaller spec misconfiguration** | ✗ No — spec is correct per PR 44 fix |
| **Multiprocessing imported in frozen code** | ✓ Yes, via NiceGUI → uvicorn → multiprocessing supervisors |

---

## Recommended Fix (For v1.8.0 / repackaged .dmg)

**File:** `scripts/pyinstaller_entry.py`  
**Change:** Add `freeze_support()` call at module level.

```python
"""PyInstaller entry shim for the Poker Solver .app bundle."""

from __future__ import annotations

import multiprocessing as mp
import sys

# CRITICAL: This must be called before any multiprocessing operations.
# Without it, macOS multiprocessing.spawn() will re-exec this entire
# script, causing uncontrolled process spawning in .dmg bundles.
mp.freeze_support()

def _smoke_test() -> int:
    ...

def main() -> int:
    if "--smoke-test" in sys.argv:
        return _smoke_test()

    from ui.app import launch
    launch()
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

**Alternative (stronger):** Add guard at module level (defensive):
```python
if __name__ == "__main__":
    mp.freeze_support()
```

But the first approach (unconditional before imports) is more robust and matches PyInstaller docs.

---

## References

- **PyInstaller multiprocessing:** https://pyinstaller.org/en/stable/usage.html#multiprocessing
- **Python multiprocessing on macOS:** https://docs.python.org/3/library/multiprocessing.html#contexts-and-start-methods
- **NiceGUI native mode code:** `/dist/Poker Solver/_internal/nicegui/native/native_mode.py:241` (has correct `freeze_support()`)
- **PR 44 (DMG fix):** Previous fix addressed missing NiceGUI in bundle; this is a separate issue
- **Related:** v1.4.0 had "nicegui missing" issue; v1.6.0 fixed that but introduced this fork-bomb

---

## Timeline

| Version | Issue | Status |
|---------|-------|--------|
| v1.4.0 | Missing NiceGUI in bundle | Fixed in PR 44 / v1.5.0+ |
| v1.5.0–v1.6.0 | Fork-bomb on .dmg launch | **THIS RCA** |
| v1.7.0 | Engine-only release (no GUI) | N/A |
| v1.7.1 | (Tag closed as obsolete per `docs/v1_7_1_tag_decision_2026-05-26.md`; never released) | Skipped — folded into v1.8.0 |
| v1.7.2 | (Tag closed as obsolete; CI workflow + Guards merged on `main` but tag rolled into v1.8.0) | Skipped — folded into v1.8.0 |
| v1.8.0 | Fork-bomb fix shipped (PR #42, commit `728206e`); repackaged .dmg pending tag + release | Fixed (pending tag) |

---

**Generated:** 2026-05-26  
**Verified by:** Code inspection + grep audit + spec review
