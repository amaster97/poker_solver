"""Smoke tests for the task #61 GUI True-Nash RvR mode toggle.

Covers the three task-#61 acceptance points:

1. Default mode (``solver_mode == "blueprint"``) routes to
   ``solve_range_vs_range`` (Pluribus blueprint), preserving prior
   behaviour bit-for-bit.
2. ``solver_mode == "true_nash"`` routes to ``solve_range_vs_range_nash``
   (vector-form CFR — true joint Nash, with exploitability).
3. UI smoke: the page renders with the new ``true-nash-checkbox`` marker.

Uses the NiceGUI ``User`` fixture pattern from ``tests/test_ui_pr24a.py``
and mocks the engine call sites so the smoke is on the UI dispatch
wiring, not on the (already covered) engine correctness.
"""

from __future__ import annotations

import asyncio
import pathlib
from collections.abc import Iterator
from typing import Any

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

    Mirrors the pattern in ``tests/test_ui_pr24a.py:isolated_state_dir``.
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
    # Teardown: reset the AppState singleton so subsequent tests see a
    # clean Spot (default empty board). The pre-existing fixtures in
    # ``test_ui_pr24a.py`` / ``test_ui_pr24b.py`` skip teardown and leak
    # the K72r board into ``test_ui_smoke.py::test_board_picker_*``; we
    # avoid that footgun here.
    try:
        reset_state_for_testing()
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Smoke 1: default mode -> blueprint aggregator
# ---------------------------------------------------------------------------


async def test_default_solver_mode_routes_to_blueprint(
    user: User,
    isolated_state_dir: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With ``rvr_mode=True`` and default ``solver_mode`` (``"blueprint"``),
    clicking Solve calls ``solve_range_vs_range`` and NOT
    ``solve_range_vs_range_nash``.
    """
    from poker_solver.range_aggregator import RangeVsRangeResult
    from ui.state import RangeWithFreqs, get_state

    blueprint_calls: dict[str, Any] = {"count": 0}
    nash_calls: dict[str, Any] = {"count": 0}

    def _fake_blueprint(
        config: Any,
        hero_range: Any,
        villain_range: Any,
        iterations: int = 200,
        **kwargs: Any,
    ) -> RangeVsRangeResult:
        blueprint_calls["count"] += 1
        return RangeVsRangeResult(
            per_class_strategy={"AA": {"check": 0.5, "bet_75": 0.5}},
            range_aggregate={"check": 0.5, "bet_75": 0.5},
            total_combos=1,
            total_solves=1,
            position="aggressor",
        )

    def _fake_nash(*args: Any, **kwargs: Any) -> Any:
        nash_calls["count"] += 1
        raise AssertionError("nash path called when blueprint expected")

    monkeypatch.setattr(
        "poker_solver.range_aggregator.solve_range_vs_range",
        _fake_blueprint,
    )
    monkeypatch.setattr(
        "poker_solver.range_aggregator.solve_range_vs_range_nash",
        _fake_nash,
    )

    await user.open("/")
    state = get_state()
    # Flop K72r to escape the preflop guardrail; tiny range for speed.
    from poker_solver.card import Card

    state.current_spot.board = [Card(13, 0), Card(7, 1), Card(2, 2)]
    state.current_spot.ranges = (
        RangeWithFreqs.from_string("AA"),
        RangeWithFreqs.from_string("KK"),
    )
    state.current_spot.rvr_mode = True
    # Default: solver_mode is "blueprint".
    assert state.current_spot.solver_mode == "blueprint"

    user.find(marker="solve-button").click()
    deadline = 4.0
    waited = 0.0
    while waited < deadline and blueprint_calls["count"] == 0:
        await asyncio.sleep(0.1)
        waited += 0.1

    assert blueprint_calls["count"] == 1, (
        f"expected solve_range_vs_range exactly once; got {blueprint_calls['count']}"
    )
    assert nash_calls["count"] == 0, (
        f"expected solve_range_vs_range_nash NOT called; got {nash_calls['count']}"
    )
    state.runner.join(timeout=2.0)


# ---------------------------------------------------------------------------
# Smoke 2: true_nash mode -> vector-form solver
# ---------------------------------------------------------------------------


async def test_true_nash_mode_routes_to_vector_form(
    user: User,
    isolated_state_dir: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With ``rvr_mode=True`` and ``solver_mode="true_nash"``, clicking
    Solve calls ``solve_range_vs_range_nash`` (NOT the blueprint
    aggregator) and the resulting ``nash_result`` is stamped on the
    runner.
    """
    from poker_solver.range_aggregator import (
        RangeVsRangeNashResult,
        RangeVsRangeResult,
    )
    from ui.state import RangeWithFreqs, get_state

    blueprint_calls: dict[str, Any] = {"count": 0}
    nash_calls: dict[str, Any] = {"count": 0, "kwargs": None}

    def _fake_blueprint(*args: Any, **kwargs: Any) -> RangeVsRangeResult:
        blueprint_calls["count"] += 1
        raise AssertionError("blueprint path called when nash expected")

    def _fake_nash(
        config: Any,
        hero_range: Any,
        villain_range: Any,
        *,
        iterations: int = 500,
        hero_player: int = 0,
        on_progress: Any = None,
        **kwargs: Any,
    ) -> RangeVsRangeNashResult:
        nash_calls["count"] += 1
        nash_calls["kwargs"] = {
            "hero_range_len": len(list(hero_range)),
            "villain_range_len": len(list(villain_range)),
            "iterations": iterations,
            "hero_player": hero_player,
        }
        return RangeVsRangeNashResult(
            per_class_strategy={"AA": {"check": 0.3, "bet_75": 0.7}},
            range_aggregate={"check": 0.3, "bet_75": 0.7},
            exploitability=0.0123,
            iterations=iterations,
            wall_clock_s=0.42,
            decision_node_count=5,
            hand_count_per_player=(6, 6),
            backend="rust_vector",
            position="aggressor" if hero_player == 0 else "defender",
        )

    monkeypatch.setattr(
        "poker_solver.range_aggregator.solve_range_vs_range",
        _fake_blueprint,
    )
    monkeypatch.setattr(
        "poker_solver.range_aggregator.solve_range_vs_range_nash",
        _fake_nash,
    )

    await user.open("/")
    state = get_state()
    from poker_solver.card import Card

    state.current_spot.board = [Card(13, 0), Card(7, 1), Card(2, 2)]
    state.current_spot.ranges = (
        RangeWithFreqs.from_string("AA"),
        RangeWithFreqs.from_string("KK"),
    )
    state.current_spot.rvr_mode = True
    state.current_spot.solver_mode = "true_nash"

    user.find(marker="solve-button").click()
    deadline = 4.0
    waited = 0.0
    while waited < deadline and nash_calls["count"] == 0:
        await asyncio.sleep(0.1)
        waited += 0.1

    assert nash_calls["count"] == 1, (
        f"expected solve_range_vs_range_nash exactly once; "
        f"got {nash_calls['count']} (kwargs={nash_calls['kwargs']!r})"
    )
    assert blueprint_calls["count"] == 0, (
        f"expected blueprint aggregator NOT called; got {blueprint_calls['count']}"
    )
    state.runner.join(timeout=2.0)
    # The nash result should land on runner.nash_result and the
    # exploitability number is preserved.
    assert state.runner.nash_result is not None
    assert abs(state.runner.nash_result.exploitability - 0.0123) < 1e-9


# ---------------------------------------------------------------------------
# Smoke 3: page renders with the true-nash-checkbox marker
# ---------------------------------------------------------------------------


async def test_page_renders_with_true_nash_checkbox(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """The run panel renders the new ``true-nash-checkbox`` marker so the
    user can flip the solver-mode toggle. We don't assert on click
    ergonomics (NiceGUI 2.x vs 3.x event differences); the smoke is
    just that the widget exists on the page.
    """
    await user.open("/")
    elements = user.find(marker="true-nash-checkbox").elements
    assert len(elements) >= 1, (
        "true-nash-checkbox marker missing from page — run panel did not render it"
    )


# ---------------------------------------------------------------------------
# Smoke 4: SolveRunner.start validates solver_mode
# ---------------------------------------------------------------------------


def test_solve_runner_rejects_invalid_solver_mode() -> None:
    """``SolveRunner.start`` raises ValueError when ``solver_mode`` is not
    one of the two whitelisted values. Guards against silent misroute on
    typos (e.g. ``"truenash"`` -> would fall through to blueprint
    default without this check).
    """
    from poker_solver.card import Card
    from ui.state import RangeWithFreqs, Spot

    spot = Spot()
    spot.board = [Card(13, 0), Card(7, 1), Card(2, 2)]
    spot.ranges = (
        RangeWithFreqs.from_string("AA"),
        RangeWithFreqs.from_string("KK"),
    )
    config, hero, villain = spot.to_rvr_call_args()
    from poker_solver.hunl import HUNLPoker
    from ui.state import SolveRunner

    runner = SolveRunner()
    game = HUNLPoker(config)
    with pytest.raises(ValueError, match="solver_mode must be"):
        runner.start(
            game,
            iterations=10,
            log_every=10,
            rvr_mode=True,
            rvr_hero_range=hero,
            rvr_villain_range=villain,
            solver_mode="not_a_real_mode",
        )


# ---------------------------------------------------------------------------
# Smoke 5: chart subtitle reflects true_nash vs blueprint
# ---------------------------------------------------------------------------


def test_chart_subtitle_distinguishes_true_nash_from_blueprint() -> None:
    """``_chart_quality_label`` returns distinct subtitles for the two
    RvR modes so the chart's framing reflects which engine produced the
    displayed curve.
    """
    import importlib
    from types import SimpleNamespace

    run_panel = importlib.import_module("ui.views.run_panel")

    def _state(rvr: bool, solver_mode: str, backend: str = "python") -> Any:
        return SimpleNamespace(
            current_spot=SimpleNamespace(rvr_mode=rvr, solver_mode=solver_mode),
            current_solve=SimpleNamespace(backend=backend),
        )

    # Blueprint mode keeps the existing label.
    label_blueprint = run_panel._chart_quality_label(_state(True, "blueprint"))
    assert "blueprint approximation" in label_blueprint
    assert "true Nash RvR" not in label_blueprint

    # True-Nash mode flips the label.
    label_true_nash = run_panel._chart_quality_label(_state(True, "true_nash"))
    assert "true Nash RvR" in label_true_nash
    assert "vector-form CFR" in label_true_nash

    # Concrete mode is unaffected by solver_mode (it's only consulted
    # when rvr_mode is True).
    label_concrete = run_panel._chart_quality_label(_state(False, "true_nash"))
    assert "true Nash" in label_concrete
    assert "vector-form CFR" not in label_concrete
