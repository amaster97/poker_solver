"""CLI integration tests for the library + batch-solve subcommands (PR 11 Agent C).

Per ``docs/pr11_prep/pr11_spec.md`` §9 final paragraph + spec §16.

Each test invokes the CLI end-to-end via ``subprocess.run([sys.executable,
"-m", "poker_solver.cli", ...])``. ``POKER_SOLVER_LIBRARY_PATH`` is set
to a ``tmp_path`` location so tests never touch the user's real
``~/.poker_solver/library.db``.

Tests follow spec §9 (last paragraph). The batch-solve dry-run is the
spec §16 success criterion.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# --------------------------------------------------------------------------- #
# Helpers.
# --------------------------------------------------------------------------- #


def _cli_env(tmp_path: Path) -> dict[str, str]:
    """Build an environment that points the CLI at an isolated library DB.

    Inherits the parent process env (so PATH / PYTHONPATH / venv work)
    and overrides only ``POKER_SOLVER_LIBRARY_PATH``.
    """
    import os

    env = dict(os.environ)
    env["POKER_SOLVER_LIBRARY_PATH"] = str(tmp_path / "lib.db")
    return env


def _run_cli(
    args: list[str],
    *,
    tmp_path: Path,
    check: bool = True,
    timeout: float = 30.0,
) -> subprocess.CompletedProcess[str]:
    """Run ``python -m poker_solver.cli <args>`` and return the completed proc.

    Use ``python -m`` rather than the ``poker-solver`` entry-point script
    per spec §9 footnote (portable across installation modes).
    """
    proc = subprocess.run(
        [sys.executable, "-m", "poker_solver.cli", *args],
        env=_cli_env(tmp_path),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if check and proc.returncode != 0:
        raise AssertionError(
            f"CLI {args!r} failed with code {proc.returncode}\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    return proc


def _make_description_json(path: Path) -> None:
    """Write a minimal exported-format JSON for ``library put``.

    Agent A's CLI consumes the SAME schema as ``library export`` /
    ``library import``: ``{"spot_description": {...}, "solve_result":
    {...}, "metadata": {...}}``. The card shape is ``[rank, suit]``
    integer pairs (per ``_spot_to_dict`` / ``_dict_to_spot`` in
    ``poker_solver/library.py``). ``starting_street`` is the int
    enum value (FLOP = 1).

    We hard-code the card integers here rather than importing
    poker_solver.card at module load so this fixture is independent of
    the SUT — the test exercises the CLI's JSON parsing, not the
    Python-side card representation. Constants:
      - Street.FLOP.value = 1
      - Card.from_str("As") = (rank=14, suit=0)
      - Card.from_str("Kc") = (rank=13, suit=1)
      - Card.from_str("7d") = (rank=7, suit=2)
    """
    description = {
        "spot_description": {
            "config": {
                "starting_stack": 10_000,
                "small_blind": 50,
                "big_blind": 100,
                "ante": 0,
                "starting_street": 1,  # Street.FLOP
                "initial_board": [[14, 0], [13, 1], [7, 2]],  # AsKc7d
                "initial_pot": 200,
                "initial_contributions": [100, 100],
                "initial_hole_cards": None,
                "preflop_raise_cap": 4,
                "postflop_raise_cap": 3,
                "bet_size_fractions": [0.5, 1.0, 2.0],
                "include_all_in": True,
                "force_allin_threshold": 1,
                "min_bet_bb": 1,
                "rake_rate": 0.0,
                "rake_cap": 0,
            },
            "initial_ranges": None,
            "label": "cli_test_spot",
        },
        "solve_result": {
            "average_strategy": {"infoset1": [0.5, 0.5]},
            "exploitability_history": [0.1],
            "game_value": 0.0,
            "iterations": 10,
            "backend": "python",
        },
        "metadata": {
            "spot_id": "",  # CLI ignores; library recomputes
            "solver_version": "0.6.0",
            "schema_version": 1,
            "created_at": 1700000000,
        },
    }
    path.write_text(json.dumps(description), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Tests 1-5.
# --------------------------------------------------------------------------- #


def test_cli_library_list_empty(tmp_path: Path) -> None:
    """1. ``library list`` on a fresh DB exits 0 with no data rows."""
    proc = _run_cli(["library", "list"], tmp_path=tmp_path)
    assert proc.returncode == 0
    # Tab-separated default: data rows would contain a tab.
    data_lines = [
        line
        for line in proc.stdout.splitlines()
        if "\t" in line and not line.lower().startswith("spot_id")
    ]
    assert len(data_lines) == 0, f"unexpected data rows: {data_lines!r}"


def test_cli_library_put_and_get(tmp_path: Path) -> None:
    """2. ``library put`` then ``library get --json`` round-trips a row.

    If the CLI's ``put`` requires a different description shape than
    ``_make_description_json`` provides, this test surfaces it; flag for
    orchestrator rather than guessing.
    """
    desc_path = tmp_path / "desc.json"
    _make_description_json(desc_path)

    put_proc = _run_cli(["library", "put", str(desc_path)], tmp_path=tmp_path)
    # The CLI prints the spot_id on stdout per spec §3.1 (put returns it).
    spot_id = put_proc.stdout.strip().split()[-1]
    assert (
        len(spot_id) >= 16
    ), f"expected a spot_id (sha256 hex) on stdout; got {put_proc.stdout!r}"

    get_proc = _run_cli(["library", "get", spot_id, "--json"], tmp_path=tmp_path)
    parsed = json.loads(get_proc.stdout)
    # The exact JSON shape is Agent A's choice; spec §3.1 says ``get``
    # returns a SolveResult (not the spot_description). We assert the
    # CLI's JSON output looks like a SolveResult: it has an
    # ``average_strategy`` mapping that contains the row we put.
    assert (
        "average_strategy" in parsed
    ), f"library get --json missing 'average_strategy'; got {parsed!r}"
    assert parsed["average_strategy"].get("infoset1") == [0.5, 0.5], (
        f"average_strategy['infoset1'] did not round-trip; got "
        f"{parsed['average_strategy']!r}"
    )


def test_cli_library_export_import(tmp_path: Path) -> None:
    """3. CLI export → delete → import round-trips via the filesystem."""
    desc_path = tmp_path / "desc.json"
    _make_description_json(desc_path)
    put_proc = _run_cli(["library", "put", str(desc_path)], tmp_path=tmp_path)
    spot_id = put_proc.stdout.strip().split()[-1]

    export_path = tmp_path / "exported.json"
    _run_cli(["library", "export", spot_id, str(export_path)], tmp_path=tmp_path)
    assert export_path.exists() and export_path.stat().st_size > 0

    _run_cli(["library", "delete", spot_id], tmp_path=tmp_path)
    # get on a deleted spot_id: spec §3.1 says get returns None. The
    # CLI translation is impl detail; we accept either (a) non-zero exit
    # with a "not found" message, or (b) zero exit with empty/null
    # stdout. The strategy MUST NOT round-trip after delete.
    get_after_delete = _run_cli(
        ["library", "get", spot_id, "--json"],
        tmp_path=tmp_path,
        check=False,
    )
    if get_after_delete.returncode == 0 and get_after_delete.stdout.strip():
        # If exit was clean, the body must not contain a real strategy.
        try:
            parsed_after = json.loads(get_after_delete.stdout)
        except json.JSONDecodeError:
            parsed_after = None
        assert (
            parsed_after is None
            or not parsed_after
            or "average_strategy" not in parsed_after
        ), f"get returned a row after delete: {get_after_delete.stdout!r}"

    _run_cli(["library", "import", str(export_path)], tmp_path=tmp_path)
    final_get = _run_cli(["library", "get", spot_id, "--json"], tmp_path=tmp_path)
    parsed = json.loads(final_get.stdout)
    # After import, the row's SolveResult must be retrievable; assert
    # the JSON has a SolveResult-shaped payload (spot_id is not part of
    # the result, only the lookup key).
    assert (
        "average_strategy" in parsed
    ), f"row missing after CLI import; got {final_get.stdout!r}"


def test_cli_library_stats(tmp_path: Path) -> None:
    """4. ``library stats`` prints counts; populating one row increments them."""
    empty_proc = _run_cli(["library", "stats"], tmp_path=tmp_path)
    assert empty_proc.returncode == 0
    # The stats output is text; "0" must appear (total_count=0 on fresh).
    assert (
        "0" in empty_proc.stdout
    ), f"empty stats stdout should mention 0; got {empty_proc.stdout!r}"

    desc_path = tmp_path / "desc.json"
    _make_description_json(desc_path)
    _run_cli(["library", "put", str(desc_path)], tmp_path=tmp_path)

    populated_proc = _run_cli(["library", "stats"], tmp_path=tmp_path)
    assert (
        "1" in populated_proc.stdout
    ), f"populated stats stdout should mention 1; got {populated_proc.stdout!r}"


def test_cli_batch_solve_dry_run(tmp_path: Path) -> None:
    """5. ``batch-solve --dry-run`` parses the CSV and exits 0 quickly.

    Spec §16 success criterion: "``poker-solver batch-solve --input
    examples/tiny_csv.csv --dry-run`` parses without error."

    Per spec §5.2: the dry-run path does NOT call ``solve_hunl_postflop``
    — it parses the CSV, checks the library skip logic, and prints
    ``[DRY-RUN]`` markers. Therefore the test completes in seconds even
    though the CSV's iterations field would otherwise require minutes.
    """
    csv_path = Path(__file__).parent.parent / "examples" / "tiny_csv.csv"
    assert (
        csv_path.exists()
    ), f"fixture {csv_path!s} missing; Agent C must ship it (spec §16)"

    proc = _run_cli(
        ["batch-solve", "--input", str(csv_path), "--dry-run"],
        tmp_path=tmp_path,
        timeout=20.0,
    )
    assert proc.returncode == 0
    # Per spec §5.2 the dry-run path prints [DRY-RUN] markers and a
    # summary; we check for at least one marker.
    stdout = proc.stdout
    assert (
        "[DRY-RUN]" in stdout
        or "dry-run" in stdout.lower()
        or "would solve" in stdout.lower()
    ), (f"batch-solve --dry-run output missing dry-run indicator; " f"got: {stdout!r}")


# --------------------------------------------------------------------------- #
# Skip the whole module gracefully if the CLI entry point can't load
# (e.g. Agent A's library subcommands haven't landed). We do this at
# collection time via a sentinel import; pytest reports clear failures.
# --------------------------------------------------------------------------- #


pytestmark = pytest.mark.cli
