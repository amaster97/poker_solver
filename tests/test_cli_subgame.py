"""Task #51 — CLI tests for the new ``subgame`` command.

``subgame`` generalizes the v1.8.2 ``river`` command to flop/turn/river
via ``--street``. ``solve_hunl_postflop`` already supports all three
streets; this surface is a CLI dispatcher.

Note: lossless flop/turn solves are infeasible at nontrivial iters
(``tests/test_hunl_postflop_solve.py`` skips them). The flop/turn cases
here use ``--iters 0`` to short-circuit DCFR while still exercising the
full dispatch + config + print path. River uses ``--iters 20`` (mirrors
the existing PR 39 happy-path test).
"""

from __future__ import annotations

import json
import warnings

import pytest

from poker_solver.cli import main


def _run(argv: list[str]) -> int:
    """Run main() with UserWarnings (e.g. lossless-flop notice) silenced."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return main(argv)


def test_subgame_flop_solve_runs_to_completion(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``subgame --street flop`` accepts a 3-card board and dispatches."""
    rc = _run(
        [
            "subgame", "--street", "flop",
            "--board", "As 7c 2d",
            "--hero", "AhKd",
            "--villain-range", "QcQh",
            "--iters", "0",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Board:" in out
    assert "Street:       flop" in out
    assert "Hero:" in out
    assert "Villain range:" in out
    assert "1 combos after card removal" in out
    assert "Hero first-decision aggregate" in out
    assert "Mean game value" in out


def test_subgame_turn_solve_runs_to_completion(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``subgame --street turn`` accepts a 4-card board and dispatches."""
    rc = _run(
        [
            "subgame", "--street", "turn",
            "--board", "As 7c 2d Kh",
            "--hero", "AhTd",
            "--villain-range", "QcQh",
            "--iters", "0",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Street:       turn" in out
    assert "1 combos after card removal" in out
    assert "Hero first-decision aggregate" in out


def test_subgame_river_solve_runs_to_completion(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``subgame --street river`` runs a small river solve to completion.

    River-only solves are fast enough for 20 iters. Hero AhTd has top
    pair vs villain QQ underpair, so the value should be near +pot.
    """
    rc = _run(
        [
            "subgame", "--street", "river",
            "--board", "As 7c 2d Kh 5s",
            "--hero", "AhTd",
            "--villain-range", "QcQh",
            "--iters", "20",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Street:       river" in out
    assert "Hero first-decision aggregate" in out
    assert "Mean game value" in out


def test_subgame_walk_tree_on_flop(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--walk-tree`` works on a flop spot (v1.8.2 presentation knob compat)."""
    rc = _run(
        [
            "subgame", "--street", "flop",
            "--board", "As 7c 2d",
            "--hero", "AhKd",
            "--villain-range", "QcQh",
            "--iters", "0",
            "--walk-tree",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Villain combo QhQc" in out
    assert "on-path nodes" in out
    assert "P1 (QhQc)" in out
    assert "reach=" in out


def test_subgame_node_drilldown_on_turn(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--node ""`` drill-down works on a turn spot (root-history target)."""
    rc = _run(
        [
            "subgame", "--street", "turn",
            "--board", "As 7c 2d Kh",
            "--hero", "AhTd",
            "--villain-range", "QcQh",
            "--iters", "0",
            "--node", "",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Per-class strategy at history ''" in out
    assert "QQ" in out  # canonical class label for QcQh / QhQc


def test_subgame_format_json_on_flop(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--format json`` on flop emits parseable JSON with expected schema."""
    rc = _run(
        [
            "subgame", "--street", "flop",
            "--board", "As 7c 2d",
            "--hero", "AhKd",
            "--villain-range", "QcQh",
            "--iters", "0",
            "--walk-tree",
            "--format", "json",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["board"] == "As 7c 2d"
    assert payload["hero"] == "AhKd"
    assert payload["villain_range"] == "QcQh"
    assert payload["iterations"] == 0
    assert "mean_game_value_bb" in payload
    assert "QhQc" in payload["combos"]
    nodes = payload["combos"]["QhQc"]
    assert isinstance(nodes, list) and len(nodes) >= 1
    first = nodes[0]
    assert {"history", "player", "hole_label", "infoset_key", "reach_prob",
            "off_path", "actions"} <= set(first.keys())


def test_river_alias_backward_compat(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``poker-solver river ...`` keeps working with the legacy preamble.

    Task #51 requires the river alias to stay functional for existing
    scripts (USAGE.md §7a). The legacy output MUST NOT include the
    new ``Street:`` line — byte-for-byte backward-compat invariant.
    """
    rc = _run(
        [
            "river",
            "--board", "As 7c 2d Kh 5s",
            "--hero", "AhTd",
            "--villain-range", "QcQh",
            "--iters", "20",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Board:" in out
    assert "Hero:" in out
    assert "Villain range:" in out
    assert "Hero first-decision aggregate" in out
    assert "Mean game value" in out
    assert "Street:" not in out
