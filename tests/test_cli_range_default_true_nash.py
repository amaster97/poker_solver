"""CLI default-route to true Nash on multi-combo villain ranges (PR follow-up to #61).

Verifies the 2026-05-27 dispatch refactor in ``_cmd_river``:

  - Single-combo villain range (e.g. ``QcQh``) — stays on the diagnostic
    fixed-hand path via ``solve_hunl_postflop`` (legacy ``action_N``
    positional output keys).
  - Multi-combo villain range, default — routes to
    ``solve_range_vs_range_nash`` (true joint Nash). Output preamble
    includes the ``Backend: true_nash`` tag and the engine's action labels
    (``fold`` / ``check`` / ``bet_75`` etc.) instead of positional keys.
  - ``--legacy-blueprint`` flag — forces the per-combo loop regardless of
    combo count; ``action_N`` keys + ``Mean game value`` line in output.
  - ``--walk-tree`` and ``--format=json`` (presentation modes) always run
    through the per-combo loop because the tree-walk formatters require a
    full ``SolveResult`` per villain combo.

These tests use a tiny iters count (10-20) to stay under a few seconds —
the Rust vector-form CFR is fast enough for that; the per-combo loop on
2-3 combos at 10 iters is also fast.

Spec source: 2026-05-27 follow-up brief to PR #61 (true Nash default for
range queries).
"""

from __future__ import annotations

import pytest

from poker_solver.cli import main

# A river board chosen so AhKd (hero) and several common villain pairs
# (QQ, JJ, TT, AKs, AKo) all have board-feasible combos with no overlap.
# Avoids A/K/T on the board so AKs / pairs both fit.
_BOARD = "As 7c 2d 9h 5s"
_HERO = "AhKd"  # As blocked, Kd off-board, no overlap with QQ/JJ/TT etc.


# ---------------------------------------------------------------------------
# Multi-combo villain range -> true Nash (default)
# ---------------------------------------------------------------------------


def test_river_multi_combo_routes_to_true_nash(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--villain-range QQ`` (6 combos, ~6 after card removal) defaults to
    true Nash via ``solve_range_vs_range_nash``. The output preamble shows
    the ``Backend: true_nash`` tag and the engine's action labels.
    """
    rc = main(
        [
            "river",
            "--board",
            _BOARD,
            "--hero",
            _HERO,
            "--villain-range",
            "QQ",  # 6 combos pre-filter
            "--iters",
            "10",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    # Preamble (shared with legacy path).
    assert "Board:" in out
    assert "Hero:" in out
    assert "Villain range:" in out
    assert "combos after card removal" in out
    # New-path-specific markers.
    assert "Backend:      true_nash" in out
    assert "range-vs-range Nash" in out
    assert "Backend reported: rust_vector" in out
    # Action labels emerge from the engine (post-projection); at least one
    # of the standard postflop labels must appear.
    assert any(
        lbl in out for lbl in ("check", "bet_33", "bet_75", "bet_100", "all_in")
    )
    # Legacy positional keys must NOT be present in the default-Nash output
    # (they only appear in the per-combo loop).
    assert "action_0" not in out
    assert "action_1" not in out
    # Legacy "Mean game value" line only emitted by the per-combo loop.
    assert "Mean game value" not in out


def test_river_two_combo_villain_routes_to_true_nash(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exactly 2 villain combos (boundary case) still routes to true Nash."""
    rc = main(
        [
            "river",
            "--board",
            _BOARD,
            "--hero",
            _HERO,
            "--villain-range",
            "QcQh,JcJh",  # 2 specific combos, no overlap
            "--iters",
            "10",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Backend:      true_nash" in out
    assert "2 combos after card removal" in out


# ---------------------------------------------------------------------------
# Single-combo villain range -> fixed-hand diagnostic path
# ---------------------------------------------------------------------------


def test_river_single_combo_stays_fixed_hand_path(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--villain-range QcQh`` (1 combo) stays on the diagnostic fixed-hand
    path via ``solve_hunl_postflop``; preserves legacy ``action_N`` keys
    and ``Mean game value`` line.
    """
    rc = main(
        [
            "river",
            "--board",
            _BOARD,
            "--hero",
            _HERO,
            "--villain-range",
            "QcQh",  # 1 specific combo
            "--iters",
            "10",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "1 combos after card removal" in out
    # Legacy fixed-hand markers.
    assert "Hero first-decision aggregate (average over villain combos)" in out
    assert "Mean game value (BB, P0 perspective)" in out
    # Positional keys (legacy fixed-hand emits action_0, action_1, ...).
    assert "action_0" in out
    assert "action_1" in out
    # Nash-path markers must be absent.
    assert "Backend:      true_nash" not in out
    assert "rust_vector" not in out


# ---------------------------------------------------------------------------
# --legacy-blueprint forces per-combo loop on multi-combo villain ranges
# ---------------------------------------------------------------------------


def test_river_legacy_blueprint_forces_per_combo_loop_on_multi_combo(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--legacy-blueprint`` opts in to the original PR 39 behavior even
    when the villain range has multiple combos: per-combo loop with
    positional ``action_N`` keys.
    """
    rc = main(
        [
            "river",
            "--board",
            _BOARD,
            "--hero",
            _HERO,
            "--villain-range",
            "QcQh,JcJh",  # 2 combos
            "--iters",
            "10",
            "--legacy-blueprint",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    # Should emit the LEGACY per-combo-loop output, not the true-Nash output.
    assert "Hero first-decision aggregate (average over villain combos)" in out
    assert "Mean game value (BB, P0 perspective)" in out
    assert "action_0" in out
    # True-Nash markers must be absent.
    assert "Backend:      true_nash" not in out
    assert "rust_vector" not in out


def test_river_legacy_blueprint_single_combo_unchanged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--legacy-blueprint`` on a single-combo range produces the same
    output as the default (no flag): the dispatch table treats single-combo
    as the fixed-hand path regardless of ``--legacy-blueprint``.
    """
    rc = main(
        [
            "river",
            "--board",
            _BOARD,
            "--hero",
            _HERO,
            "--villain-range",
            "QcQh",
            "--iters",
            "10",
            "--legacy-blueprint",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    # Same fixed-hand path output as the default single-combo case.
    assert "Hero first-decision aggregate (average over villain combos)" in out
    assert "Mean game value (BB, P0 perspective)" in out
    assert "action_0" in out
    assert "Backend:      true_nash" not in out


# ---------------------------------------------------------------------------
# Presentation modes (--walk-tree / --format=json/csv) -> per-combo loop
# ---------------------------------------------------------------------------


def test_river_walk_tree_uses_per_combo_loop_even_on_multi_combo(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--walk-tree`` requires a full ``SolveResult`` per villain combo, so
    it must route through the per-combo loop (NOT true Nash) even on a
    multi-combo villain range — otherwise the tree-walk formatters have no
    per-combo state to walk.
    """
    rc = main(
        [
            "river",
            "--board",
            _BOARD,
            "--hero",
            _HERO,
            "--villain-range",
            "QcQh,JcJh",
            "--iters",
            "10",
            "--walk-tree",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    # walk-tree emits per-combo headlines like "Villain combo QhQc — N on-path nodes".
    assert "Villain combo" in out
    assert "on-path nodes" in out
    # Should NOT be the Nash header (which is only emitted by _run_subgame_true_nash).
    assert "Backend:      true_nash" not in out


def test_river_format_json_uses_per_combo_loop_even_on_multi_combo(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--format=json`` (a v1.8.2 presentation mode) goes through the
    per-combo loop, same as ``--walk-tree``.
    """
    rc = main(
        [
            "river",
            "--board",
            _BOARD,
            "--hero",
            _HERO,
            "--villain-range",
            "QcQh,JcJh",
            "--iters",
            "10",
            "--format",
            "json",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    # JSON mode produces a top-level "combos" key with one entry per villain combo.
    import json as _json

    payload = _json.loads(out)
    assert "combos" in payload
    assert len(payload["combos"]) == 2
    # Each combo entry should have the per-combo tree nodes (proves we
    # went through the per-combo loop, not the Nash path).
    for combo_key, nodes in payload["combos"].items():
        assert isinstance(nodes, list)
        assert len(nodes) > 0


# ---------------------------------------------------------------------------
# subgame command — same dispatch logic must apply (task #51 generalized)
# ---------------------------------------------------------------------------


def test_subgame_river_multi_combo_routes_to_true_nash(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The ``subgame`` command shares ``_run_subgame_solve`` with ``river``,
    so the same multi-combo -> true Nash dispatch must apply.
    """
    rc = main(
        [
            "subgame",
            "--street",
            "river",
            "--board",
            _BOARD,
            "--hero",
            _HERO,
            "--villain-range",
            "QcQh,JcJh",
            "--iters",
            "10",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    # subgame command adds the "Street:" preamble line; otherwise same as river.
    assert "Street:       river" in out
    assert "Backend:      true_nash" in out
    assert "2 combos after card removal" in out


def test_subgame_river_legacy_blueprint_forces_per_combo_loop(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``subgame --legacy-blueprint`` honors the same backward-compat opt-in
    flag as ``river --legacy-blueprint``.
    """
    rc = main(
        [
            "subgame",
            "--street",
            "river",
            "--board",
            _BOARD,
            "--hero",
            _HERO,
            "--villain-range",
            "QcQh,JcJh",
            "--iters",
            "10",
            "--legacy-blueprint",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Street:       river" in out
    assert "Hero first-decision aggregate (average over villain combos)" in out
    assert "Mean game value (BB, P0 perspective)" in out
    assert "Backend:      true_nash" not in out
