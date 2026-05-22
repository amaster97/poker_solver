"""PyInstaller entry shim for the Poker Solver .app bundle.

The PR 11 spec (§6.3 + decision 13.13) names ``ui/main.py`` as the
PyInstaller entry point. The actual launcher in this repo is
``ui.app.launch`` (PR 10a landed before PR 11 had a chance to rename),
so this thin shim bridges the gap without forcing a rename of ui/app.py
that would conflict with Agent A's file ownership.

A ``--smoke-test`` flag is added so the post-build verification step in
``scripts/build_macos_dmg.sh`` can confirm that the bundled
``poker_solver._rust`` native extension is importable from inside the
packaged .app — the load-bearing risk mitigation per spec §12.1.

Run paths:
    Poker Solver.app/Contents/MacOS/Poker\\ Solver
    Poker Solver.app/Contents/MacOS/Poker\\ Solver --smoke-test
"""

from __future__ import annotations

import sys


def _smoke_test() -> int:
    """Verify the bundled native extension imports.

    Exit 0 on success, 1 on failure. Prints diagnostics to stdout so the
    build script can ``tail`` and surface the error to the user.
    """
    try:
        from poker_solver import _rust  # type: ignore[attr-defined]  # noqa: F401

        print(f"[smoke] poker_solver._rust imported OK: {_rust!r}")
        # Touch a known symbol to confirm the .so is actually loaded
        # (not just a stub module that PyInstaller mocked up).
        attrs = [a for a in dir(_rust) if not a.startswith("_")]
        print(f"[smoke] _rust public symbols: {len(attrs)} found")
        if not attrs:
            print("[smoke] FAIL: _rust loaded but has no public symbols")
            return 1
        return 0
    except ImportError as exc:
        print(f"[smoke] FAIL: cannot import poker_solver._rust: {exc}")
        print("[smoke] Likely cause: PyInstaller --add-binary was not passed.")
        print("[smoke] Check spec §12.1 / agent_b_prompt.md top risk.")
        return 1


def main() -> int:
    if "--smoke-test" in sys.argv:
        return _smoke_test()

    # Normal launch: delegate to the NiceGUI app entry.
    from ui.app import launch

    launch()
    return 0


if __name__ == "__main__":
    sys.exit(main())
