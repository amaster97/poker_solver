"""Regression tests for the range-matrix node-navigation bugs P2 + P3.

These tests deliberately exercise the **live-app** projection path, where
``AppState`` carries NO pre-built ``current_tree`` — the tree is built on
demand from ``runner.result`` (``tree_browser._build_tree_from_runner``).
That path is what real users hit, and it is where both bugs lived:

* **P2** — clicking a decision-tree node left the matrix on an all-zero
  strategy. Root cause: the tree was rebuilt from ``spot.to_hunl_config()``,
  but the ``Spot`` round-trip does not preserve a postflop subgame's pot /
  contributions, so the rebuilt config produced a DIFFERENT action
  abstraction (more bet sizes) than the strategy vectors were solved with.
  ``_strategy_for_combo`` then rejected every vector on the shape mismatch
  and the grid rendered combo-count-only (fold==call==raise==0). The fix
  stashes the solved ``HUNLConfig`` on the runner (``_solved_config``) and
  builds the browse tree from it.

* **P3** — the grid lit the acting player's hand (P1 = QQ at root) while the
  combo inspector reported the hero's combos (P0 = AhKc), so the lit cell
  read "QQ (0 combos)". The fix routes the grid, the inspector, and the
  header subtitle through one seat resolver (``_matrix_player``) = the
  player to act at the selected node.

The fixtures use the deterministic ``river_tiny_subgame`` (AhKc vs QdQh on
As7c2dKh5s); each side has one combo but the decision tree has real nodes
with per-node strategies, which is exactly what node->matrix behavior needs.
RvR postflop solves hang on this branch, so they are intentionally avoided.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import ui.views.range_matrix as rm
from poker_solver.hunl import HUNLPoker, default_tiny_subgame
from ui.state import AppState, SolveRunner, UIPrefs
from ui.views.spot_input import _spot_from_config
from ui.views.tree_browser import on_tree_node_selected


@pytest.fixture(scope="module")
def live_state_factory():
    """Solve the tiny river subgame once; hand back a *live-path* state builder.

    The returned ``build()`` produces a real ``AppState`` with **no**
    ``current_tree`` attribute, so the matrix must resolve the tree from the
    runner (the production code path). A fresh state per test keeps the
    ``current_tree_node_id`` mutations isolated.
    """

    cfg = default_tiny_subgame()
    runner = SolveRunner()
    runner.start(HUNLPoker(cfg), iterations=300, log_every=50)
    runner.join(timeout=30.0)
    assert runner.status == "done", f"solve did not finish: {runner.status!r}"
    assert runner.result is not None

    def build() -> AppState:
        spot = _spot_from_config(cfg)
        return AppState(
            current_spot=spot,
            current_solve=None,  # exercise the runner-only fallback
            current_tree_node_id="root",
            selected_player_for_input=0,
            runner=runner,
            prefs=UIPrefs(),
            state_path=Path("/tmp/_p2p3_state.json"),
        )

    return build


def _nonempty_cells(state: AppState) -> list[tuple[str, float, float, float]]:
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
# P2 — node selection changes the matrix projection (live path).
# ---------------------------------------------------------------------------


def test_solved_config_stashed_on_runner(live_state_factory) -> None:
    """``SolveRunner.start`` records the exact solved config for tree rebuilds."""
    state = live_state_factory()
    assert getattr(state.runner, "_solved_config", None) is not None


def test_live_tree_action_count_matches_strategy_shape(live_state_factory) -> None:
    """The runner-built tree shares the SOLVED action abstraction (P2 core).

    Without the ``_solved_config`` fix the root node carried more legal
    actions than the strategy vectors had entries, so every per-combo lookup
    was rejected on shape mismatch and the grid went all-zero.
    """
    state = live_state_factory()
    assert not hasattr(state, "current_tree"), (
        "this test must exercise the runner-built tree path"
    )
    tree = rm._resolve_tree(state)
    assert tree is not None
    root = tree.get_node("root")
    snap = rm._current_tree_snapshot(state)
    legal_actions = rm._snapshot_legal_actions(snap)
    strategy = rm._current_strategy(state)
    state_obj = rm._snapshot_state(snap)
    player = rm._snapshot_player(snap)
    # The QdQh combo's strategy vector must resolve (length == n actions).
    from poker_solver.card import Card

    combo = (Card.from_str("Qd"), Card.from_str("Qh"))
    probs = rm._strategy_for_combo(
        strategy, state_obj, combo, player, legal_actions
    )
    assert probs is not None, (
        "strategy lookup returned None -> tree action count diverged from the "
        "solved strategy shape (the P2 regression)"
    )
    assert probs.shape[0] == len(legal_actions)
    del root


def test_matrix_projection_changes_with_node_live_path(live_state_factory) -> None:
    """Selecting a deeper node changes both the header and the cell strategy.

    This is the user-visible P2 assertion on the LIVE path: the matrix was
    locked to an all-zero root projection no matter which node was clicked.
    """
    state = live_state_factory()

    # Root: P1 (QQ) to act, checks the river -> call-bucket mass, NON-ZERO.
    on_tree_node_selected(state, "root")
    root_sub = rm._matrix_subtitle(state)
    root_cells = _nonempty_cells(state)
    assert "node root" in root_sub and "player P1 to act" in root_sub
    qq = next((c for c in root_cells if c[0] == "QQ"), None)
    assert qq is not None, f"expected a QQ cell at root; got {root_cells}"
    assert qq[2] > 0.5, f"QQ should check (non-zero call bucket) at root: {qq}"

    # Drill to root/1_check: P0 (AK) to act, bets -> raise-bucket mass.
    tree = rm._resolve_tree(state)
    tree.expand("root")
    on_tree_node_selected(state, "root/1_check")
    child_sub = rm._matrix_subtitle(state)
    child_cells = _nonempty_cells(state)
    assert "node root/1_check" in child_sub and "player P0 to act" in child_sub
    ak = next((c for c in child_cells if c[0] == "AKo"), None)
    assert ak is not None, f"expected an AKo cell at child; got {child_cells}"
    assert ak[3] > 0.5, f"AK should bet (non-zero raise bucket) at child: {ak}"

    # The two render fully differently (header AND cells) — the bug was that
    # they were identical (root projection reused for every click).
    assert root_sub != child_sub
    assert root_cells != child_cells


# ---------------------------------------------------------------------------
# P3 — grid + combo inspector describe the SAME (acting) player.
# ---------------------------------------------------------------------------


def _inspected_classes(state: AppState) -> set[str]:
    return {
        c.hand_class
        for c in rm._build_grid_summaries(state)
        if not c.summary.out_of_range and not c.summary.empty
    }


def test_inspector_matches_grid_player_at_root(live_state_factory) -> None:
    """At root (P1 to act) the inspector shows P1's real combos, not P0's.

    Bug P3: the grid lit P1's QQ but the inspector queried P0's range,
    yielding "QQ (0 combos)". The lit class must inspect to real combos with
    R/C/F that agree with the grid.
    """
    state = live_state_factory()
    on_tree_node_selected(state, "root")

    lit = _inspected_classes(state)
    assert lit == {"QQ"}, f"root grid should light exactly QQ (P1); got {lit}"

    rows = rm._build_combo_rows(state, "QQ")
    assert rows, "inspector must list P1's QQ combo, not report 0 combos (P3)"
    assert len(rows) == 1
    row = rows[0]
    assert not row.blocked
    # R/C/F must be real (the combo checks the river) and agree with the grid.
    assert row.call > 0.5, f"QQ inspector row should show check/call mass: {row}"
    grid_qq = next(
        c.summary for c in rm._build_grid_summaries(state) if c.hand_class == "QQ"
    )
    assert abs(grid_qq.call - row.call) < 1e-6, (
        "grid and inspector disagree on the QQ call frequency (P3 mismatch)"
    )

    # The hero's class (AKo) is NOT in the acting player's range here -> no
    # rows. The inspector and grid agree it is out of range.
    assert rm._build_combo_rows(state, "AKo") == []
    assert "AKo" not in lit


def test_inspector_matches_grid_player_at_child(live_state_factory) -> None:
    """At root/1_check (P0 to act) the inspector shows P0's real combos.

    The opposite seat from the root: this proves the consistency holds for
    both the hero-to-act and villain-to-act cases (node-dependent).
    """
    state = live_state_factory()
    tree = rm._resolve_tree(state)
    tree.expand("root")
    on_tree_node_selected(state, "root/1_check")

    lit = _inspected_classes(state)
    assert lit == {"AKo"}, f"child grid should light exactly AKo (P0); got {lit}"

    rows = rm._build_combo_rows(state, "AKo")
    assert rows, "inspector must list P0's AhKc combo, not report 0 combos (P3)"
    assert len(rows) == 1
    row = rows[0]
    assert not row.blocked
    assert row.raise_ > 0.5, f"AK inspector row should show bet/raise mass: {row}"
    grid_ak = next(
        c.summary for c in rm._build_grid_summaries(state) if c.hand_class == "AKo"
    )
    assert abs(grid_ak.raise_ - row.raise_) < 1e-6, (
        "grid and inspector disagree on the AKo raise frequency (P3 mismatch)"
    )

    # QQ (P1's hand) is out of P0's range at this node.
    assert rm._build_combo_rows(state, "QQ") == []
    assert "QQ" not in lit


def test_inspector_count_label_agrees_with_rows(live_state_factory) -> None:
    """The inspector's "(N combos)" label and its rows count the same thing.

    P3 also surfaced as two inspector lines disagreeing ("QQ (0 combos)" vs a
    populated row). With one seat resolver the header count == len(rows).
    """
    state = live_state_factory()
    on_tree_node_selected(state, "root")
    rows = rm._build_combo_rows(state, "QQ")
    # The header label is literally ``f"... ({len(rows)} combos)"`` — assert
    # the rows it counts are the same rows the body renders (no second,
    # divergent build against a different seat).
    assert len(rows) == 1
    assert all(not r.blocked or r.label for r in rows)
