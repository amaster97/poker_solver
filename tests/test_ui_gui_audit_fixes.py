"""GUI-audit fix tests: example-spot load sync + tree-node -> matrix projection.

Covers two GUI fixes:

* **Fix 1 — example-spot load syncs the whole spot.** ``spot_input._spot_from_config``
  must copy board, BOTH players' ranges, stacks, and blinds from a fixture
  ``HUNLConfig`` (previously ranges were skipped and the UI never repainted,
  so the board chips + range matrix stayed on the old values).

* **Fix 2 — decision-tree node click drives the range matrix.** Selecting a
  tree node sets ``state.current_tree_node_id``; the range matrix must
  re-project the SELECTED node's per-combo strategy into the 13x13 grid
  (header tracks the node, cells repaint with that node's action
  frequencies), including for off-path / counterfactual nodes.

These are pure-logic tests (no NiceGUI ``User`` fixture needed): they drive
the projection helpers directly against a real (tiny) solve + ``SolveTree``.
A duck-typed ``SimpleNamespace`` stands in for ``AppState`` because every
helper under test reads state via ``getattr`` / ``_safe_state_field``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import ui.views.range_matrix as rm
from poker_solver.hunl import HUNLPoker, default_tiny_subgame
from ui.state import RangeWithFreqs, SolveRunner
from ui.views.spot_input import (
    _ranges_from_config,
    _spot_from_config,
    _trigger_spot_views_refresh,
)
from ui.views.tree_browser import SolveTree, on_tree_node_selected

# ---------------------------------------------------------------------------
# Shared fixtures: one real tiny-subgame solve reused across projection tests.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def solved_tiny() -> tuple[HUNLPoker, object, SolveRunner]:
    """Solve the deterministic AhKc-vs-QdQh river subgame once for the module.

    Returns ``(game, solve_result, runner)``. 300 iterations is plenty for
    this single-street point-pair spot to converge to a near-pure strategy.
    """
    cfg = default_tiny_subgame()
    runner = SolveRunner()
    runner.start(HUNLPoker(cfg), iterations=300, log_every=50)
    runner.join(timeout=30.0)
    assert runner.status == "done", f"solve did not finish: status={runner.status!r}"
    assert runner.result is not None
    return HUNLPoker(cfg), runner.result, runner


def _build_state(game: HUNLPoker, result: object, runner: SolveRunner) -> SimpleNamespace:
    """A minimal duck-typed ``AppState`` wired for the matrix projection path."""
    cfg = default_tiny_subgame()
    tree = SolveTree(game, result)
    spot = _spot_from_config(cfg)
    return SimpleNamespace(
        current_spot=spot,
        current_solve=None,  # exercise the runner-only strategy fallback
        current_tree=tree,
        current_tree_node_id="root",
        selected_player_for_input=0,
        runner=runner,
        prefs=SimpleNamespace(matrix_show_frequencies=True),
    )


def _nonempty_cells(
    state: SimpleNamespace,
) -> list[tuple[str, float, float, float]]:
    """(hand_class, fold, call, raise_) for every in-range, non-empty cell."""
    return [
        (
            c.hand_class,
            round(c.summary.fold, 3),
            round(c.summary.call, 3),
            round(c.summary.raise_, 3),
        )
        for c in rm._build_grid_summaries(state)
        if not c.summary.out_of_range and not c.summary.empty
    ]


# ---------------------------------------------------------------------------
# Fix 1 — example-spot load syncs board + ranges + stacks + blinds.
# ---------------------------------------------------------------------------


def test_spot_from_config_syncs_board() -> None:
    """The loaded spot's board matches the fixture's 5 river cards."""
    cfg = default_tiny_subgame()
    spot = _spot_from_config(cfg)
    assert "".join(str(c) for c in spot.board) == "As7c2dKh5s"
    assert len(spot.board) == 5


def test_spot_from_config_syncs_ranges_from_hole_cards() -> None:
    """Both players' ranges are synced to the config's concrete hole cards.

    The river_tiny_subgame fixture is AhKc (P0) vs QdQh (P1); after load
    each player's range must contain exactly that combo at weight 1.0 (the
    previous handler skipped range mutation entirely).
    """
    from poker_solver.card import Card

    cfg = default_tiny_subgame()
    spot = _spot_from_config(cfg)

    p0_combos = [
        c for c in spot.ranges[0].base_range.combos if spot.ranges[0].frequency_of(c) > 0
    ]
    p1_combos = [
        c for c in spot.ranges[1].base_range.combos if spot.ranges[1].frequency_of(c) > 0
    ]
    assert len(p0_combos) == 1
    assert len(p1_combos) == 1
    assert {p0_combos[0][0], p0_combos[0][1]} == {Card.from_str("Ah"), Card.from_str("Kc")}
    assert {p1_combos[0][0], p1_combos[0][1]} == {Card.from_str("Qd"), Card.from_str("Qh")}


def test_spot_from_config_syncs_stacks_and_blinds() -> None:
    """Stacks (BB) and blinds are derived from the fixture config."""
    cfg = default_tiny_subgame()
    spot = _spot_from_config(cfg)
    # 1000 stack / 100 (=1BB in cents) -> 10 BB each.
    assert spot.stacks_bb == (10, 10)
    assert spot.bb_blind == 1.0
    assert spot.sb_blind > 0.0


def test_ranges_from_config_preserves_previous_when_no_hole_cards() -> None:
    """A config without ``initial_hole_cards`` keeps the user's prior ranges."""
    prev = SimpleNamespace(
        ranges=(RangeWithFreqs.from_string("AA"), RangeWithFreqs.from_string("KK"))
    )
    no_hole_cfg = SimpleNamespace(initial_hole_cards=())
    ranges = _ranges_from_config(no_hole_cfg, prev)
    assert ranges[0] is prev.ranges[0]
    assert ranges[1] is prev.ranges[1]


async def test_trigger_spot_views_refresh_calls_registered_hooks() -> None:
    """``_trigger_spot_views_refresh`` fires the registered (de-duped) hooks.

    Now a coroutine: the helper awaits each hook's ``AwaitableResponse`` so the
    ``@ui.refreshable`` re-render completes INLINE (G3 fix). Plain non-awaitable
    hooks (as here) just fire once each and are not awaited.
    """
    calls: list[str] = []
    runner = SimpleNamespace(
        _spot_input_refresh=lambda: calls.append("spot"),
        _range_matrix_refresh=lambda: calls.append("matrix"),
    )
    state = SimpleNamespace(runner=runner, matrix_refresh=runner._range_matrix_refresh)
    await _trigger_spot_views_refresh(state)
    # Both distinct hooks fire; the duplicated matrix hook fires only once.
    assert calls == ["spot", "matrix"]


async def test_trigger_spot_views_refresh_swallows_hook_errors() -> None:
    """A raising hook must not bubble out (slot may be torn down mid-tab-switch)."""

    def _boom() -> None:
        raise RuntimeError("parent slot deleted")

    state = SimpleNamespace(
        runner=SimpleNamespace(_spot_input_refresh=_boom, _range_matrix_refresh=None),
        matrix_refresh=None,
    )
    # Must not raise.
    await _trigger_spot_views_refresh(state)


# ---------------------------------------------------------------------------
# Fix 2 — tree-node click drives the range-matrix projection.
# ---------------------------------------------------------------------------


def test_node_select_updates_current_tree_node_id(
    solved_tiny: tuple[HUNLPoker, object, SolveRunner],
) -> None:
    """Selecting a tree node records it on the state for the matrix to read."""
    game, result, runner = solved_tiny
    state = _build_state(game, result, runner)
    state.current_tree.expand("root")
    on_tree_node_selected(state, "root/1_check")
    assert state.current_tree_node_id == "root/1_check"


def test_node_select_drives_matrix_refresh_hook(
    solved_tiny: tuple[HUNLPoker, object, SolveRunner],
) -> None:
    """``on_tree_node_selected`` fires the matrix refresh hook so cells repaint."""
    game, result, runner = solved_tiny
    state = _build_state(game, result, runner)
    fired: list[int] = []
    state.matrix_refresh = lambda: fired.append(1)
    on_tree_node_selected(state, "root")
    assert fired, "node selection must trigger the range-matrix refresh hook"


def test_current_tree_snapshot_resolves_selected_node(
    solved_tiny: tuple[HUNLPoker, object, SolveRunner],
) -> None:
    """The matrix resolves the SELECTED node's snapshot, not always the root.

    Root is P1-to-act; its child ``root/1_check`` is P0-to-act. The snapshot
    (and hence the projected player) must follow the selected node.
    """
    game, result, runner = solved_tiny
    state = _build_state(game, result, runner)

    state.current_tree_node_id = "root"
    root_snap = rm._current_tree_snapshot(state)
    assert root_snap is not None
    assert rm._snapshot_player(root_snap) == 1

    state.current_tree.expand("root")
    state.current_tree_node_id = "root/1_check"
    child_snap = rm._current_tree_snapshot(state)
    assert child_snap is not None
    assert rm._snapshot_player(child_snap) == 0
    assert child_snap is not root_snap


def test_matrix_projects_distinct_strategy_per_node(
    solved_tiny: tuple[HUNLPoker, object, SolveRunner],
) -> None:
    """On-path navigation: each node projects its OWN per-combo strategy.

    * root (P1, QQ) checks the river -> call-bucket mass.
    * root/1_check (P0, AK) bets -> raise-bucket mass.

    The two grids must differ (the bug: clicking a node left the cells
    unchanged on the root projection).
    """
    game, result, runner = solved_tiny
    state = _build_state(game, result, runner)

    state.current_tree_node_id = "root"
    root_cells = _nonempty_cells(state)
    assert root_cells, "root projection produced no in-range cells"
    # Cell tuple is (hand_class, fold, call, raise_). P1 holds QQ and checks
    # the river -> mass in the call/check bucket (index 2), none folded.
    qq = next((c for c in root_cells if c[0] == "QQ"), None)
    assert qq is not None, f"expected a QQ cell at root; got {root_cells}"
    assert qq[1] == 0.0 and qq[2] > 0.5, f"QQ should check (call bucket) at root: {qq}"

    state.current_tree.expand("root")
    state.current_tree_node_id = "root/1_check"
    child_cells = _nonempty_cells(state)
    assert child_cells, "child projection produced no in-range cells"
    # P0 holds AKo; betting maps to the raise/bet bucket.
    ak = next((c for c in child_cells if c[0] == "AKo"), None)
    assert ak is not None, f"expected an AKo cell at root/1_check; got {child_cells}"
    assert ak[1] == 0.0 and ak[3] > 0.5, f"AK should bet (raise bucket) at child: {ak}"

    assert root_cells != child_cells, (
        "matrix projection did not change between root and child node"
    )


def test_matrix_projects_off_path_nodes(
    solved_tiny: tuple[HUNLPoker, object, SolveRunner],
) -> None:
    """Off-path (counterfactual) nodes still resolve + project a strategy.

    After P1 checks and P0 bets, P1 faces the bet at ``root/1_check/0_bet*``
    — a counterfactual decision for QQ. The snapshot must resolve (not None)
    and the grid must carry that node's per-combo strategy (QQ folds to the
    bet here), not fall back to the root projection.
    """
    game, result, runner = solved_tiny
    state = _build_state(game, result, runner)
    state.current_tree.expand("root")
    grandchildren = state.current_tree.expand("root/1_check")
    assert grandchildren, "expected off-path children under root/1_check"

    for node in grandchildren:
        on_tree_node_selected(state, node.id)
        snap = rm._current_tree_snapshot(state)
        assert snap is not None, f"off-path node {node.id} resolved to no snapshot"
        # P1 is to act again, facing P0's bet.
        assert rm._snapshot_player(snap) == 1
        cells = _nonempty_cells(state)
        assert cells, f"off-path node {node.id} produced no in-range cells"
        qq = next((c for c in cells if c[0] == "QQ"), None)
        assert qq is not None, f"expected QQ cell at off-path {node.id}; got {cells}"
        # Counterfactual: QQ folds to P0's bet -> fold-bucket mass (index 1),
        # NOT the check/call mass it showed at the root (proves the off-path
        # node projects its own strategy rather than the root's).
        assert qq[1] > 0.5 and qq[2] == 0.0, (
            f"QQ should fold (fold bucket) at off-path bet node: {qq}"
        )


def test_matrix_subtitle_reflects_selected_node(
    solved_tiny: tuple[HUNLPoker, object, SolveRunner],
) -> None:
    """The matrix header text tracks the selected node + its acting player."""
    game, result, runner = solved_tiny
    state = _build_state(game, result, runner)

    state.current_tree_node_id = "root"
    root_sub = rm._matrix_subtitle(state)
    assert "node root" in root_sub
    assert "player P1 to act" in root_sub

    state.current_tree.expand("root")
    state.current_tree_node_id = "root/1_check"
    child_sub = rm._matrix_subtitle(state)
    assert "node root/1_check" in child_sub
    assert "player P0 to act" in child_sub
    assert root_sub != child_sub
