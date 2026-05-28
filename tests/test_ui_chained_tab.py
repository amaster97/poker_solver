"""Smoke tests for the task #57 "Chain solve" GUI tab.

Covers the four task-#57 acceptance points:

  1. Smoke: the chained tab loads, both panes render, 169 cells visible.
  2. Clicking a preflop cell + selecting a 3-card flop triggers the
     postflop solve via ``ChainedSolveResult.solve_postflop``.
  3. Lazy cache: a second query on the same board returns instantly
     (the cache hit drops below a constant-time floor).
  4. Page-level render test: ``user.open("/")`` brings up the tab bar
     and both ``tab-solve`` + ``tab-chained`` markers exist.

Uses the NiceGUI ``User`` fixture pattern from ``tests/test_ui_pr24a.py``
and mocks ``solve_chained`` so the smoke is on the UI dispatch wiring,
not on the (already covered) orchestrator correctness.
"""

from __future__ import annotations

import asyncio
import pathlib
import time
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest

pytest.importorskip("nicegui")

# ruff: noqa: E402, I001  (post-importorskip imports must follow the skip)
from nicegui.testing import User

pytest_plugins = [
    "nicegui.testing.general_fixtures",
    "nicegui.testing.user_plugin",
]

pytestmark = [
    pytest.mark.ui,
    pytest.mark.nicegui_main_file("ui/app.py"),
]


@pytest.fixture
def isolated_state_dir(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[pathlib.Path]:
    """Override HOME so state.json lands in tmp_path; reset runner.

    Mirrors ``test_ui_pr24a.py:isolated_state_dir`` so the chained-tab
    smokes share the same fresh-singleton + runner-quiesce protocol as
    the rest of the UI suite.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("POKER_SOLVER_UI_STATE_DIR", str(tmp_path / ".poker_solver_ui"))
    from ui.state import get_state, reset_state_for_testing

    reset_state_for_testing()
    try:
        current = get_state()
        if current.runner.is_alive():
            current.runner.stop()
            current.runner.join(timeout=3.0)
        current.runner._stop_event.clear()
        current.runner._pause_event.clear()
    except Exception:  # noqa: BLE001
        pass
    yield tmp_path
    # Teardown so subsequent tests don't see a stale chained_result.
    import contextlib

    with contextlib.suppress(Exception):
        reset_state_for_testing()


def _fake_chained_result() -> Any:
    """Build a synthetic :class:`ChainedSolveResult` for the smoke tests.

    Mirrors the shape of a real Phase A solve on a 2x2 range: per-class
    preflop strategy for AA / KK, one flop-reaching terminal, an empty
    postflop cache. The orchestrator's ``solve_postflop`` is bypassed
    by patching the result's ``solve_postflop`` method to return a
    canned :class:`RangeVsRangeNashResult`.
    """
    from collections import OrderedDict

    from poker_solver.chained import ChainedSolveResult, ContinuationRanges
    from poker_solver.range_aggregator import RangeVsRangeNashResult

    preflop_result = RangeVsRangeNashResult(
        per_history_strategy={},
        per_class_strategy={
            "AA": {"all_in": 0.95, "fold": 0.05},
            "KK": {"all_in": 0.80, "fold": 0.20},
        },
        range_aggregate={"all_in": 0.875, "fold": 0.125},
        exploitability=0.01,
        iterations=30,
        wall_clock_s=1.2,
        decision_node_count=8,
        hand_count_per_player=(2, 2),
        memory_profile={},
        backend="python_chained_route_a",
        position="aggressor",
        warnings=[],
    )
    action_sequence = ("c", "x")  # SB limp / BB check (a flop-reaching terminal)
    continuation = ContinuationRanges(
        hero={"AA": 6.0, "KK": 6.0},
        villain={"AA": 6.0, "KK": 6.0},
        pot_chips=200,
        action_sequence=action_sequence,
    )
    result = ChainedSolveResult(
        preflop_result=preflop_result,
        continuation_ranges={action_sequence: continuation},
        # Production's cache supports LRU bookkeeping via OrderedDict
        # (``move_to_end`` / ``popitem(last=False)``). A plain dict
        # would silently fail on ``move_to_end`` during cache-hit reads.
        postflop_cache=OrderedDict(),
    )
    return result


def _fake_postflop_result() -> Any:
    """Synthetic flop-subgame result returned by the stubbed solve_postflop."""
    from poker_solver.range_aggregator import RangeVsRangeNashResult

    return RangeVsRangeNashResult(
        per_history_strategy={"flop_root_AA": [0.4, 0.6]},
        per_class_strategy={
            "AA": {"check": 0.4, "bet_75": 0.6},
            "KK": {"check": 0.5, "bet_75": 0.5},
        },
        range_aggregate={"check": 0.45, "bet_75": 0.55},
        exploitability=0.005,
        iterations=30,
        wall_clock_s=0.5,
        decision_node_count=4,
        hand_count_per_player=(2, 2),
        memory_profile={},
        backend="rust_vector",
        position="aggressor",
        warnings=[],
    )


# ---------------------------------------------------------------------------
# Smoke 1: page-level render — both tabs visible
# ---------------------------------------------------------------------------


async def test_page_loads_with_both_tabs(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """The page renders the tab bar with both ``tab-solve`` and
    ``tab-chained`` markers. The chained-tab content (grid + display)
    is materialized inside ``tab-panel-chained``.

    Per task #57 acceptance gate 4.
    """
    await user.open("/")
    assert user.find(marker="app-tabs").elements
    assert user.find(marker="tab-solve").elements
    assert user.find(marker="tab-chained").elements
    # Chained tab content rendered inside its tab panel — the outer
    # marker is always present (NiceGUI ``tab_panel`` element materializes
    # the content even when the tab is not the active value).
    assert user.find(marker="chained-tab-display").elements
    assert user.find(marker="chained-tab-grid").elements


# ---------------------------------------------------------------------------
# Smoke 2: chained tab grid renders 169 cells (covers all hand classes)
# ---------------------------------------------------------------------------


async def test_chained_tab_grid_renders_all_169_cells(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """The 13x13 grid emits one ``chained-tab-cell-{class}`` marker per
    hand class — 169 in total. Codifies the layout convention against
    accidental row/col swaps or off-by-one walks.

    Per task #57 acceptance gate 1 (smoke: both panes render).
    """
    await user.open("/")
    cells = user.find(marker="chained-tab-cell").elements
    # ``.mark()`` accepts a space-separated marker; the ``chained-tab-cell``
    # token matches every per-class cell.
    assert len(cells) == 169, (
        f"expected 169 chained-tab cells, got {len(cells)}"
    )

    # A few canonical anchor cells must exist (corners + diagonal).
    for hand_class in ("AA", "22", "AKs", "AKo", "72o", "JJ"):
        marker = f"chained-tab-cell-{hand_class}"
        anchor_cells = user.find(marker=marker).elements
        assert len(anchor_cells) >= 1, f"{marker} missing from grid"


# ---------------------------------------------------------------------------
# Smoke 3: solve button routes through solve_chained
# ---------------------------------------------------------------------------


async def test_chained_solve_button_routes_to_solve_chained(
    user: User,
    isolated_state_dir: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clicking ``chained-tab-solve-button`` calls
    ``poker_solver.chained.solve_chained`` (mocked) with hero / villain
    ranges from the spot and preflop iterations from the input.

    Per task #57 acceptance gate 1 (smoke: solve dispatch wiring).
    """
    from ui.state import RangeWithFreqs, get_state

    calls: dict[str, Any] = {"count": 0, "kwargs": None}

    def _fake_solve_chained(
        config: Any,
        hero_range: Any,
        villain_range: Any,
        **kwargs: Any,
    ) -> Any:
        calls["count"] += 1
        calls["kwargs"] = {
            "hero_range": list(hero_range),
            "villain_range": list(villain_range),
            **kwargs,
        }
        return _fake_chained_result()

    monkeypatch.setattr(
        "poker_solver.chained.solve_chained",
        _fake_solve_chained,
    )

    await user.open("/")
    state = get_state()
    state.current_spot.ranges = (
        RangeWithFreqs.from_string("AA, KK"),
        RangeWithFreqs.from_string("AA, KK"),
    )
    state.current_spot.stacks_bb = (50, 50)
    state.current_spot.board = []

    user.find(marker="chained-tab-solve-button").click()
    deadline = 4.0
    waited = 0.0
    while waited < deadline and calls["count"] == 0:
        await asyncio.sleep(0.1)
        waited += 0.1

    assert calls["count"] == 1, (
        f"expected solve_chained called exactly once; got {calls['count']}"
    )
    assert "AA" in calls["kwargs"]["hero_range"]
    assert "KK" in calls["kwargs"]["hero_range"]
    assert "AA" in calls["kwargs"]["villain_range"]
    state.runner.join(timeout=2.0)
    assert state.runner.status in ("done", "stopped"), (
        f"runner status after chained solve: {state.runner.status!r}"
    )
    assert state.runner.chained_result is not None


# ---------------------------------------------------------------------------
# Smoke 4: cell click + flop selection drives solve_postflop
# ---------------------------------------------------------------------------


async def test_cell_click_plus_flop_triggers_postflop_solve(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """With a populated ``runner.chained_result``, clicking a preflop
    cell then picking a 3-card flop triggers
    ``ChainedSolveResult.solve_postflop`` and the right pane renders the
    per-class postflop strategy rows.

    Per task #57 acceptance gate 2 (preflop click + flop -> postflop solve).
    """
    from ui.state import get_state

    await user.open("/")
    state = get_state()

    # Stash a synthetic result on the runner so the chained tab can
    # project it. ``runner.chained_result`` is what ``project_preflop``
    # reads (see ``ui/views/chained_tab.py:_chained_result``).
    result = _fake_chained_result()
    state.runner.chained_result = result  # type: ignore[attr-defined]
    state.runner._mode = "chained"  # type: ignore[attr-defined]
    state.runner.status = "done"

    # Patch the result's solve_postflop so we don't run the real Rust
    # vector-form CFR in a smoke test.
    postflop_calls: dict[str, Any] = {"count": 0}

    def _fake_solve_postflop(action_sequence: Any, board: Any) -> Any:
        postflop_calls["count"] += 1
        postflop_result = _fake_postflop_result()
        # Mirror production's cache key (PR #150): the cache is keyed on
        # the canonical board (suit-isomorphism class), not the raw tuple.
        # This fake replaces ``solve_postflop`` entirely via ``patch.object``,
        # so the only consumer of this write is incidental inspection —
        # but use the right shape so the test stays a fair stand-in.
        from poker_solver.chained import _canonicalize_board

        result.postflop_cache[
            (action_sequence, _canonicalize_board(board))
        ] = postflop_result
        return postflop_result

    with patch.object(result, "solve_postflop", _fake_solve_postflop):
        # Re-open so the page picks up the new runner state.
        await user.open("/")

        # Click the AA cell to select that class.
        user.find(marker="chained-tab-cell-AA").click()

        # Pick a 3-card flop. Use card strings that match the board
        # picker marker convention (rank + suit symbol).
        from poker_solver.card import SUITS

        # Pick a flop that does NOT block AA. Use 7c 5d 2h (no aces).
        _ = SUITS  # noqa: F841
        user.find(marker="chained-tab-board-cell-7c").click()
        user.find(marker="chained-tab-board-cell-5d").click()
        user.find(marker="chained-tab-board-cell-2h").click()

        # Re-open so the right-pane refreshable picks up the new board
        # selection. (The board picker mutates runner state via
        # ``_set_selected_board``; the right pane is gated on the
        # board having length 3 to trigger the solve.)
        await user.open("/")

        # The postflop strategy panel must have triggered the
        # lazy solve and rendered per-class rows.
        assert postflop_calls["count"] >= 1, (
            f"expected solve_postflop called >=1 time after flop selection; "
            f"got {postflop_calls['count']}"
        )
        # Per-class postflop rows materialized for the dominant labels.
        # The fake postflop result has AA: check 0.4 / bet_75 0.6, so the
        # bar rows for check + bet_75 must exist.
        check_rows = user.find(marker="chained-tab-postflop-row-check").elements
        bet_rows = user.find(marker="chained-tab-postflop-row-bet_75").elements
        assert len(check_rows) >= 1, "postflop check row missing"
        assert len(bet_rows) >= 1, "postflop bet_75 row missing"


# ---------------------------------------------------------------------------
# Smoke 5: lazy cache — second query on same board returns instantly
# ---------------------------------------------------------------------------


def test_lazy_cache_second_query_is_instant() -> None:
    """Second ``solve_postflop`` call with the same ``(action_seq, board)``
    returns the SAME object (identity check) and completes far below
    the wall-clock floor of the first call.

    This is a non-UI unit test on the result wrapper itself — the GUI
    just consumes the cache via
    ``ChainedSolveResult.postflop_cache``; the contract under test is
    that the cache exists and rounds the second hit to O(1).

    Per task #57 acceptance gate 3 (lazy cache).
    """
    from poker_solver.card import Card
    from poker_solver.chained import _canonicalize_board

    result = _fake_chained_result()
    action_sequence = next(iter(result.continuation_ranges.keys()))
    board = (Card(7, 0), Card(5, 1), Card(2, 2))  # 7c 5d 2h

    # Pre-populate the cache via a stubbed solve_postflop so we don't
    # run the real solver in unit tests. The smoke is on the cache-hit
    # path of the wrapper, not the cold-solve performance.
    #
    # PR #150 changed the cache key from the raw board tuple to
    # ``(action_sequence, _canonicalize_board(board))`` so two boards in
    # the same suit-isomorphism class share a single solve. This test
    # mirrors the production lookup by writing under the canonical key —
    # writing the raw tuple would silently miss on the production read
    # path and the wrapper would fall through to the real solver.
    first_result = _fake_postflop_result()
    canonical_key = _canonicalize_board(board)
    result.postflop_cache[(action_sequence, canonical_key)] = first_result

    # First fetch via the wrapper's public API — must return the cached
    # object verbatim. Time it as a sanity check (cache hit is well
    # below the 10 ms floor the orchestrator's test asserts on).
    t0 = time.perf_counter()
    fetched = result.solve_postflop(action_sequence, board)
    t_fetch = time.perf_counter() - t0

    assert fetched is first_result, (
        "cache hit must return the same object stored at write time"
    )
    # 10 ms floor is the same value used in
    # ``tests/test_chained_orchestrator.py::test_solve_postflop_caches_result``.
    assert t_fetch < 0.01, (
        f"cache hit took {t_fetch * 1000:.3f}ms; expected <10ms"
    )

    # A second call must continue to return the same object (idempotent).
    fetched_again = result.solve_postflop(action_sequence, board)
    assert fetched_again is first_result


# ---------------------------------------------------------------------------
# Smoke 6: SolveRunner accepts solver_mode="chained" and routes correctly
# ---------------------------------------------------------------------------


def test_solve_runner_accepts_chained_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The SolveRunner.start signature accepts ``solver_mode="chained"``
    and the worker dispatches to ``solve_chained`` (mocked) rather than
    the postflop / RvR / preflop branches.

    Per task #57 acceptance gate 1 (solver_mode chained branch wired).
    """
    from poker_solver.hunl import HUNLConfig, HUNLPoker, Street
    from ui.state import SolveRunner

    chained_calls: dict[str, Any] = {"count": 0, "kwargs": None}

    def _fake_solve_chained(
        config: Any,
        hero_range: Any,
        villain_range: Any,
        **kwargs: Any,
    ) -> Any:
        chained_calls["count"] += 1
        chained_calls["kwargs"] = {
            "hero_range": list(hero_range),
            "villain_range": list(villain_range),
            **kwargs,
        }
        return _fake_chained_result()

    monkeypatch.setattr(
        "poker_solver.chained.solve_chained",
        _fake_solve_chained,
    )

    config = HUNLConfig(
        starting_stack=5000,
        small_blind=50,
        big_blind=100,
        starting_street=Street.PREFLOP,
        bet_size_fractions=(),
        include_all_in=True,
        preflop_raise_cap=2,
    )
    game = HUNLPoker(config=config)
    runner = SolveRunner()
    runner.start(
        game,
        iterations=30,
        log_every=10,
        solver_mode="chained",
        rvr_hero_range=["AA", "KK"],
        rvr_villain_range=["AA", "KK"],
        rvr_hero_player=0,
    )
    # Wait for the worker to land. The fake solve_chained returns
    # immediately, so the worker should exit in well under a second.
    runner.join(timeout=5.0)

    assert chained_calls["count"] == 1, (
        f"expected solve_chained called exactly once; got {chained_calls['count']}"
    )
    assert chained_calls["kwargs"]["hero_range"] == ["AA", "KK"]
    assert chained_calls["kwargs"]["villain_range"] == ["AA", "KK"]
    assert chained_calls["kwargs"]["hero_player"] == 0
    assert runner.status == "done"
    assert runner.chained_result is not None  # type: ignore[attr-defined]


def test_solve_runner_rejects_invalid_solver_mode() -> None:
    """``solver_mode`` outside the accepted set raises ValueError early."""
    from poker_solver.hunl import HUNLConfig, HUNLPoker, Street
    from ui.state import SolveRunner

    config = HUNLConfig(
        starting_stack=5000,
        starting_street=Street.PREFLOP,
    )
    game = HUNLPoker(config=config)
    runner = SolveRunner()
    with pytest.raises(ValueError, match="solver_mode must be"):
        runner.start(
            game,
            iterations=30,
            log_every=10,
            solver_mode="not_a_real_mode",
            rvr_hero_range=["AA"],
            rvr_villain_range=["AA"],
        )


# ---------------------------------------------------------------------------
# Smoke 7: chained tab primitives — pure-Python projection sanity
# ---------------------------------------------------------------------------


def test_chained_tab_primitives_layout_and_color() -> None:
    """The ``hand_class_at`` / ``cell_color_rgb`` / ``aggregate_actions``
    helpers in ``chained_tab.py`` mirror the PR #147 conventions exactly:
    top-left = AA, bottom-right = 22, suited above diagonal, offsuit
    below; raise / call / fold / jam buckets pick the right anchor.

    Locks the layout contract so a future renderer swap can't silently
    re-row-major the grid.
    """
    from ui.views.chained_tab import (
        aggregate_actions,
        cell_color_rgb,
        classify_action,
        hand_class_at,
    )

    # Layout corners + a few diagonal anchors.
    assert hand_class_at(0, 0) == "AA"
    assert hand_class_at(12, 12) == "22"
    assert hand_class_at(0, 1) == "AKs"  # above diagonal -> suited
    assert hand_class_at(1, 0) == "AKo"  # below diagonal -> offsuit
    assert hand_class_at(6, 6) == "88"  # diagonal pair

    # Bucket mapping for the chart palette.
    assert classify_action("fold") == "fold"
    assert classify_action("check") == "call"
    assert classify_action("call") == "call"
    assert classify_action("all_in") == "jam"
    assert classify_action("jam") == "jam"
    assert classify_action("open_3") == "raise"
    assert classify_action("bet_75") == "raise"

    # Pure-strategy cells return a saturated dominant-bucket color
    # blended against the neutral anchor (38 dim cells at p=0.0; pure
    # at p=1.0). A 0.6/0.4 mix lands between the two — we just sanity
    # check the dominant kind survives.
    pure_raise = aggregate_actions({"open_3": 1.0})
    r, g, b = cell_color_rgb(pure_raise)
    assert r > g and r > b, (
        f"pure-raise cell should be red-dominant; got ({r}, {g}, {b})"
    )

    mixed = aggregate_actions({"open_3": 0.6, "fold": 0.4})
    assert mixed.dominant_label == "open_3"
    assert mixed.dominant_kind == "raise"
    assert abs(mixed.dominant_prob - 0.6) < 1e-9
