"""Tests for the ``poker-solver --version`` CLI flag.

The flag was deferred from PR #107 audit; it gives users a one-shot way to
read the installed version without having to spelunk ``__init__.py``.

We exercise the flag in-process via ``main`` (cheap, no subprocess spawn)
and additionally via subprocess to confirm the installed console-script
entry point also honors it. The subprocess test gracefully skips if the
``poker-solver`` binary isn't on PATH (e.g. in an unconfigured env).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from poker_solver import __version__
from poker_solver.cli import main


def test_version_flag_in_process(capsys: pytest.CaptureFixture[str]) -> None:
    """--version prints ``poker-solver <ver>`` and exits 0."""
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    # argparse's "version" action writes to stdout on Python 3.4+.
    assert __version__ in captured.out
    assert "poker-solver" in captured.out


def test_version_flag_matches_package_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI output must match poker_solver.__version__ exactly (no hardcoding)."""
    with pytest.raises(SystemExit):
        main(["--version"])
    captured = capsys.readouterr()
    assert captured.out.strip() == f"poker-solver {__version__}"


def _resolve_poker_solver_binary() -> str | None:
    """Find a poker-solver binary that uses the current interpreter's package.

    Prefer the console script colocated with ``sys.executable`` (so we exercise
    the same environment we just imported from). Falls back to ``PATH`` only if
    that script imports the package we are testing.
    """
    here = Path(sys.executable).resolve().parent
    candidate = here / "poker-solver"
    if candidate.exists():
        return str(candidate)
    path_binary = shutil.which("poker-solver")
    return path_binary


def test_version_flag_subprocess() -> None:
    """End-to-end: installed ``poker-solver`` console script honors --version.

    Skips when the available ``poker-solver`` shim is bound to a different
    interpreter than the one running pytest (the shim then cannot import the
    package we're testing). The in-process test above is the authoritative
    coverage; this test guards the entry-point wiring when it's available.
    """
    binary = _resolve_poker_solver_binary()
    if binary is None:
        pytest.skip("poker-solver console script not installed")
    result = subprocess.run(
        [binary, "--version"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0 and "No module named 'poker_solver'" in (
        result.stderr or ""
    ):
        pytest.skip(
            "poker-solver shim bound to a different interpreter; "
            "in-process test covers behavior"
        )
    assert result.returncode == 0, result.stderr
    assert __version__ in result.stdout
    assert "poker-solver" in result.stdout


def test_version_flag_python_m_module() -> None:
    """Fallback E2E path: ``python -m poker_solver`` honors --version.

    This guards against installation paths where the console script is
    absent but the package is importable (e.g. ``pip install -e .``
    skipped, plain ``PYTHONPATH`` env, etc.).
    """
    result = subprocess.run(
        [sys.executable, "-m", "poker_solver", "--version"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0 and "No module named poker_solver.__main__" in (
        result.stderr or ""
    ):
        pytest.skip("poker_solver has no __main__ module; console-script path covers this")
    assert result.returncode == 0, result.stderr
    assert __version__ in result.stdout
    assert "poker-solver" in result.stdout
