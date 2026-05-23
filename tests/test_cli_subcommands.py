"""PR 39: CLI ergonomics — tests for the three new wrapper subcommands.

Covers the happy path + an error path for each of ``pushfold``, ``river``,
and ``parity``. The tests invoke ``poker_solver.cli.main`` in-process via
``capsys`` rather than spawning a subprocess so we keep the wall-clock
budget tight (parity is the slow one — its happy path skips when Brown's
binary isn't built, mirroring the test_river_diff.py skip protocol).

Spec source: PR 39 brief. Library APIs already exist (PR 14 / PR 7), so
each test asserts only the CLI wrapper layer.
"""

from __future__ import annotations

import json

import pytest

from poker_solver.cli import main
from poker_solver.parity.noambrown_wrapper import find_brown_binary

# ---------------------------------------------------------------------------
# pushfold subcommand
# ---------------------------------------------------------------------------


def test_pushfold_happy_path_emits_frequency(capsys: pytest.CaptureFixture[str]) -> None:
    """Stock AA jam at 9 BB returns 1.0 (chart-validated; AA always shoves)."""
    rc = main(["pushfold", "--stack", "9", "--position", "sb_jam", "--hand", "AA"])
    assert rc == 0
    captured = capsys.readouterr()
    # Output format: "<hand> <position> <stack>BB: <freq>"
    assert "AA sb_jam 9BB:" in captured.out
    # AA jams 100% in every chart cell.
    assert "1.000000" in captured.out


def test_pushfold_json_round_trips(capsys: pytest.CaptureFixture[str]) -> None:
    """--json emits a parseable object with the expected keys."""
    rc = main(
        ["pushfold", "--stack", "8", "--position", "bb_call_vs_jam", "--hand", "AKs", "--json"]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stack_bb"] == 8
    assert payload["position"] == "bb_call_vs_jam"
    assert payload["hand"] == "AKs"
    assert 0.0 <= payload["frequency"] <= 1.0


def test_pushfold_error_path_out_of_range_stack(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Stack outside [2, 15] BB returns exit 2 with a readable error."""
    rc = main(["pushfold", "--stack", "50", "--position", "sb_jam", "--hand", "AA"])
    assert rc == 2
    captured = capsys.readouterr()
    assert "outside supported range" in captured.err or "outside" in captured.err


# ---------------------------------------------------------------------------
# river subcommand
# ---------------------------------------------------------------------------


def test_river_happy_path_aggregates_frequencies(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A tiny river spot with a 1-combo villain range completes and prints output.

    Use a small (1 combo) villain range + low iterations to stay under a few
    seconds — the per-combo solve uses ``solve_hunl_postflop`` which is
    deterministic at this size.
    """
    rc = main(
        [
            "river",
            "--board",
            "As 7c 2d Th 5s",  # No K on board so hero AhKh + villain QQ both fit
            "--hero",
            "AhKd",
            "--villain-range",
            "QcQh",  # single specific combo (no card overlap)
            "--iters",
            "20",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Board:" in out
    assert "Hero:" in out
    assert "Villain range:" in out
    assert "1 combos after card removal" in out
    assert "Hero first-decision aggregate" in out
    assert "Mean game value" in out


def test_river_error_path_hero_overlaps_board(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Hero hole that shares a card with the board exits 2 via main()'s ValueError handler."""
    rc = main(
        [
            "river",
            "--board",
            "As 7c 2d Kh 5s",
            "--hero",
            "AsKc",  # As is on board
            "--villain-range",
            "QQ",
            "--iters",
            "10",
        ]
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "error:" in err
    assert "overlaps" in err


# ---------------------------------------------------------------------------
# parity subcommand
# ---------------------------------------------------------------------------


def test_parity_error_path_unknown_fixture(capsys: pytest.CaptureFixture[str]) -> None:
    """Unknown fixture id exits 2 and lists available fixtures."""
    rc = main(["parity", "--fixture", "definitely_not_a_real_fixture_id"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "not found" in err
    # Lists the available fixture ids so the user knows what to retry.
    assert "Available:" in err


@pytest.mark.skipif(
    find_brown_binary() is None,
    reason="Brown's binary not built (scripts/build_noambrown.sh). "
    "Skipping parity happy-path; matches test_river_diff.py protocol.",
)
def test_parity_happy_path_runs_to_completion(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When Brown's binary is built, parity runs the smallest fixture cleanly.

    Reduced iters keeps the wall-clock under ~60s; we only assert the CLI
    wrapper renders the headline metrics — the per-action numeric diff is
    owned by ``tests/test_river_diff.py``.
    """
    rc = main(
        [
            "parity",
            "--fixture",
            "dry_K72_rainbow",
            "--iters",
            "50",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Fixture:" in out
    assert "Parity diff:" in out
    assert "Brown infoset keys:" in out
    assert "Overlap:" in out
