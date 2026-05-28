"""CLI integration tests for ``batch-solve --backend rust`` (W2.4 / #59).

Sarah's CSV-driven workflow hit the 180s CLI timeout on 1-row x iter=10
runs with the Python DCFR per-history solver. PR 114's ``TerminalCache``
landed a ~213x river speedup in the Rust vector backend
(``solve_range_vs_range_nash``); this PR exposes that path via the
existing ``batch-solve`` CLI surface.

Test plan (per #59 spec):
  1. 3-row CSV smoke -> all complete in <30s with rust backend (was
     >540s extrapolated on the python path).
  2. Backward compat: ``--backend python`` still drives the
     ``solve_hunl_postflop`` route used by PR 11 Agent C's overnight
     solves. Exercised via ``--dry-run`` to keep CI cost low.
  3. CSV output schema unchanged (the library round-trip writes the
     same ``spots`` table columns regardless of backend).
  4. Bad input row produces ``[ERROR]`` line + exit code 1, NOT a crash.

These tests subprocess into ``python -m poker_solver.cli`` so they
exercise the full CLI dispatch chain (``_cmd_batch_solve`` ->
``scripts.batch_solve.run`` -> per-row dispatch).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

# --------------------------------------------------------------------------- #
# Helpers (mirror tests/test_library_cli.py patterns so the env handling
# is consistent across the batch-solve test surface).
# --------------------------------------------------------------------------- #


def _cli_env(tmp_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["POKER_SOLVER_LIBRARY_PATH"] = str(tmp_path / "lib.db")
    return env


def _run_cli(
    args: list[str],
    *,
    tmp_path: Path,
    timeout: float = 60.0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "poker_solver.cli", *args],
        env=_cli_env(tmp_path),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _write_3row_rust_csv(path: Path) -> None:
    """Write a 3-row CSV with hero/villain range columns and small iter."""
    path.write_text(
        "name,starting_street,initial_board,stacks_bb,bet_sizes,"
        "abstraction_path,iterations,hero_range,villain_range\n"
        # Each row uses a tiny 2x2 range and iter=20 so total cost is
        # ~1-2s with the rust backend on the M-series host the CI matrix
        # uses; the budget of <30s is ample headroom.
        'row1_river,river,AsKc7dKh5s,10,0.5,,20,"AA,KK","AA,KK"\n'
        'row2_river,river,8h7h6c5s4d,10,0.5,,20,"AA,QQ","KK,JJ"\n'
        'row3_river,river,AhKh3c2d2s,10,0.5,,20,"AA,KK","QQ,JJ"\n'
    )


def _rust_backend_available() -> bool:
    """The rust dispatch path only works when the PyO3 extension is built.

    The shared module + the M-series wheel arch check are CLAUDE.md
    documented hazards; we skip cleanly rather than masking the broken
    state, but the test surfaces *should* exist on every host so the
    smoke runs in CI on the maturin-built leg.
    """
    try:
        from poker_solver import _rust  # noqa: F401
    except ImportError:
        return False
    return True


# --------------------------------------------------------------------------- #
# 1. Rust backend 3-row smoke: <30s wall time.
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(
    not _rust_backend_available(),
    reason="rust extension not built (run `maturin develop --release`)",
)
def test_batch_solve_rust_3row_under_30s(tmp_path: Path) -> None:
    """W2.4 acceptance: 3-row CSV with iter=20 completes in <30s.

    The pre-#59 ``solve_hunl_postflop`` per-history path needed ~180s
    per row even at iter=10, blocking Sarah's interactive flow. The
    rust vector path should land each row in ~0.5s on M-series, so a
    30s budget for 3 rows is a 20x safety margin against host-noise
    drift.
    """
    csv = tmp_path / "smoke.csv"
    _write_3row_rust_csv(csv)

    t0 = time.time()
    proc = _run_cli(
        ["batch-solve", "--input", str(csv), "--backend", "rust"],
        tmp_path=tmp_path,
        timeout=45.0,  # subprocess wall-clock ceiling > the 30s test budget
    )
    elapsed = time.time() - t0

    assert proc.returncode == 0, (
        f"rust batch-solve failed (rc={proc.returncode})\n"
        f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
    assert elapsed < 30.0, (
        f"rust batch-solve too slow: {elapsed:.2f}s >= 30.0s budget. "
        f"PR 114 ``TerminalCache`` was supposed to land ~213x on river — "
        f"check ``solve_range_vs_range_nash`` perf regression."
    )
    # Each row should be tagged with the rust backend on the [OK] line.
    assert proc.stdout.count("[OK]") == 3, (
        f"expected 3 [OK] rows; got stdout:\n{proc.stdout}"
    )
    assert "backend=rust" in proc.stdout, (
        f"per-row [OK] should announce backend=rust; got:\n{proc.stdout}"
    )


# --------------------------------------------------------------------------- #
# 2. Python backend still works (backward compat).
# --------------------------------------------------------------------------- #


def test_batch_solve_python_backend_dry_run_backward_compat(
    tmp_path: Path,
) -> None:
    """``--backend python`` (default) parses + dry-runs identical to PR 11.

    The dry-run path skips the actual solver call, so this test runs
    cheap on every CI leg (no rust extension needed). The point is to
    pin the backward-compat surface: legacy CSVs (no hero_range /
    villain_range columns) keep parsing, and the python path is still
    selected when ``--backend`` is omitted.
    """
    # Use the in-repo fixture so the test is consistent with the
    # existing ``test_cli_batch_solve_dry_run`` coverage.
    csv = (
        Path(__file__).parent.parent / "examples" / "tiny_csv.csv"
    )
    assert csv.exists(), f"fixture {csv!s} missing"

    # 2a: ``--backend python`` explicit.
    proc_explicit = _run_cli(
        ["batch-solve", "--input", str(csv), "--backend", "python",
         "--dry-run"],
        tmp_path=tmp_path,
        timeout=20.0,
    )
    assert proc_explicit.returncode == 0, proc_explicit.stderr
    assert "[DRY-RUN]" in proc_explicit.stdout

    # 2b: omit ``--backend`` => default is python (backward compat).
    proc_default = _run_cli(
        ["batch-solve", "--input", str(csv), "--dry-run"],
        tmp_path=tmp_path,
        timeout=20.0,
    )
    assert proc_default.returncode == 0, proc_default.stderr
    assert "[DRY-RUN]" in proc_default.stdout
    # Default should report backend=python in the dry-run line.
    assert "backend=python" in proc_default.stdout, (
        f"default backend should be python; got:\n{proc_default.stdout}"
    )


# --------------------------------------------------------------------------- #
# 3. CSV output schema unchanged: library round-trip writes the same
#    ``spots`` columns regardless of backend, so Sarah's downstream
#    tooling that reads via ``poker-solver library list`` keeps working.
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(
    not _rust_backend_available(),
    reason="rust extension not built (run `maturin develop --release`)",
)
def test_batch_solve_rust_library_schema_unchanged(tmp_path: Path) -> None:
    """Rust-backend rows land in the library with the same schema.

    The adapter (``_nash_to_solve_result``) wraps the
    ``RangeVsRangeNashResult`` so ``Library.put`` accepts it. After a
    rust-backend run, ``library list`` should see the spots and a
    re-run with the same CSV should produce ``[SKIP]`` (idempotency).
    """
    csv = tmp_path / "schema.csv"
    csv.write_text(
        "name,starting_street,initial_board,stacks_bb,bet_sizes,"
        "abstraction_path,iterations,hero_range,villain_range\n"
        'schema_row,river,AsKc7dKh5s,10,0.5,,20,"AA,KK","AA,KK"\n'
    )

    # First run: rows solve fresh.
    proc1 = _run_cli(
        ["batch-solve", "--input", str(csv), "--backend", "rust"],
        tmp_path=tmp_path,
        timeout=30.0,
    )
    assert proc1.returncode == 0, proc1.stderr
    assert "[OK]" in proc1.stdout

    # ``library list`` finds the spot.
    proc_list = _run_cli(
        ["library", "list"], tmp_path=tmp_path, timeout=10.0
    )
    assert proc_list.returncode == 0, proc_list.stderr
    assert "schema_row" in proc_list.stdout, (
        f"library list should show the rust-backend row; got:\n"
        f"{proc_list.stdout}"
    )

    # Re-run: idempotency — already-solved => skip.
    proc2 = _run_cli(
        ["batch-solve", "--input", str(csv), "--backend", "rust"],
        tmp_path=tmp_path,
        timeout=15.0,
    )
    assert proc2.returncode == 0, proc2.stderr
    assert "[SKIP]" in proc2.stdout, (
        f"second run should hit the idempotent skip; got:\n{proc2.stdout}"
    )


# --------------------------------------------------------------------------- #
# 4. Bad input row -> graceful error, not crash.
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(
    not _rust_backend_available(),
    reason="rust extension not built (run `maturin develop --release`)",
)
def test_batch_solve_rust_bad_row_graceful_error(tmp_path: Path) -> None:
    """A row with an empty hero_range surfaces ``[ERROR]`` + rc=1.

    The rust dispatch calls ``_resolve_ranges`` which raises
    ``ValueError`` on an explicitly empty range string; the per-row
    handler catches and continues to subsequent rows, then returns
    rc=1 because ``counts.error > 0``.
    """
    csv = tmp_path / "mixed.csv"
    # Three rows: row 1 OK, row 2 bad (empty hero_range when explicitly
    # provided as just whitespace), row 3 OK. The good rows still solve;
    # the bad one logs [ERROR] and the loop continues.
    csv.write_text(
        "name,starting_street,initial_board,stacks_bb,bet_sizes,"
        "abstraction_path,iterations,hero_range,villain_range\n"
        'good_a,river,AsKc7dKh5s,10,0.5,,20,"AA","KK"\n'
        # bad row: invalid hand label "ZZ" — should bubble through the
        # range parser as a ValueError from inside _resolve_ranges'
        # downstream call into solve_range_vs_range_nash.
        'bad_row,river,8h7h6c5s4d,10,0.5,,20,"ZZ","KK"\n'
        'good_b,river,AhKh3c2d2s,10,0.5,,20,"AA","KK"\n'
    )

    proc = _run_cli(
        ["batch-solve", "--input", str(csv), "--backend", "rust"],
        tmp_path=tmp_path,
        timeout=30.0,
    )
    # rc=1 per ``run()`` contract: any errors > 0 -> exit 1.
    assert proc.returncode == 1, (
        f"expected rc=1 from mixed batch (1 bad row); got {proc.returncode}\n"
        f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
    # The good rows still complete (graceful, not a crash).
    assert proc.stdout.count("[OK]") == 2, (
        f"expected 2 [OK] rows alongside the bad one; got:\n{proc.stdout}"
    )
    assert "[ERROR]" in proc.stdout and "bad_row" in proc.stdout, (
        f"bad row should surface as [ERROR] in stdout; got:\n{proc.stdout}"
    )


# --------------------------------------------------------------------------- #
# Marker so the test file is grouped with the other CLI integration
# tests (mirrors tests/test_library_cli.py at the bottom).
# --------------------------------------------------------------------------- #
pytestmark = pytest.mark.cli
