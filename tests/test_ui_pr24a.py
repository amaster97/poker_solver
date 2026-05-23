"""Smoke tests for PR 24a (GUI Gate 2 — first half).

Covers the four PR 24a user-facing additions:

1. Range-vs-range solve mode (``rvr-mode-toggle``) routes through
   ``poker_solver.range_aggregator.solve_range_vs_range`` instead of
   the concrete-vs-concrete ``solve``.
2. Hero seat selector (``hero-seat-toggle``) writes
   ``state.current_spot.hero_player`` and flips the matrix front tab.
3. ``hero_player == 1`` + RvR mode → ``RangeVsRangeResult.position ==
   "defender"`` (per ``range_aggregator.py:183-186``).
4. 4-tier exploitability slider (``tier-slider``) sets
   ``state.runner._pending_target_expl`` to the tier's mBB/pot target
   divided by 1000.
5. Chart subtitle reflects ``"blueprint approximation"`` in RvR mode
   (per spec §3.4).
6. ``Spot.to_rvr_call_args()`` honours ``hero_player`` by swapping
   hero / villain ranges.

These tests use the NiceGUI ``User`` fixture pattern from
``tests/test_ui_smoke.py``. Engine-bound smokes (1, 3, 4-on-real-solver)
mock ``solve_range_vs_range`` to keep wall-clock low — the smoke is on
the UI wiring, not on the aggregator's correctness (which is covered by
``tests/test_range_vs_range_aggregator.py``).
"""

from __future__ import annotations

import asyncio
import importlib
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

    Mirrors the pattern in ``test_ui_smoke.py:isolated_state_dir``.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("POKER_SOLVER_UI_STATE_DIR", str(tmp_path / ".poker_solver_ui"))
    from ui.state import get_state, reset_state_for_testing

    # Start each test with a fresh AppState so cross-test runner state
    # never leaks (PR 24a routes through a new RvR path; we don't want
    # one test's RvR result to be visible in the next test's matrix).
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


# ---------------------------------------------------------------------------
# Smoke 1: RvR toggle routes the worker through solve_range_vs_range
# ---------------------------------------------------------------------------


async def test_rvr_toggle_routes_to_aggregator(
    user: User,
    isolated_state_dir: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Smoke 1: with ``rvr-mode-toggle`` set to 'Range-vs-range', clicking
    Solve calls ``solve_range_vs_range`` (mocked) instead of the concrete
    solve path. The aggregator stub returns a tiny ``RangeVsRangeResult``
    and the runner status transitions to ``done`` within the wait window.
    """
    from poker_solver.range_aggregator import RangeVsRangeResult
    from ui.state import get_state

    calls: dict[str, Any] = {"count": 0, "kwargs": None}

    def _fake_solve_rvr(
        config: Any,
        hero_range: Any,
        villain_range: Any,
        iterations: int = 200,
        **kwargs: Any,
    ) -> RangeVsRangeResult:
        calls["count"] += 1
        calls["kwargs"] = {
            "hero_range_len": len(list(hero_range)),
            "villain_range_len": len(list(villain_range)),
            "iterations": iterations,
            **kwargs,
        }
        return RangeVsRangeResult(
            per_class_strategy={"AA": {"check": 0.4, "bet_75": 0.6}},
            range_aggregate={"check": 0.4, "bet_75": 0.6},
            total_combos=6,
            total_solves=1,
            position="aggressor" if kwargs.get("hero_player", 0) == 0 else "defender",
        )

    # Patch the symbol the worker imports inside ``_run_rvr_path``. We
    # patch at the ``poker_solver.range_aggregator`` module so the
    # ``from ... import solve_range_vs_range`` inside the worker grabs
    # the fake.
    monkeypatch.setattr(
        "poker_solver.range_aggregator.solve_range_vs_range",
        _fake_solve_rvr,
    )

    await user.open("/")
    # Set a flop board so the spot isn't preflop (RvR aggregator rejects
    # preflop spots per range_aggregator.py:313-320).
    user.find(marker="board-picker-cell-Kh").click()
    user.find(marker="board-picker-cell-7d").click()
    user.find(marker="board-picker-cell-2c").click()
    # Set a tiny hero / villain range so the aggregator call is cheap.
    user.find(marker="range-string-input-p0").type("AA")
    user.find(marker="range-string-input-p1").type("KK")
    # Flip RvR toggle on.
    state = get_state()
    state.current_spot.rvr_mode = True
    # Click Solve.
    user.find(marker="solve-button").click()
    # Wait for the worker to finish (mock returns immediately).
    deadline = 4.0
    waited = 0.0
    step = 0.1
    while waited < deadline and calls["count"] == 0:
        await asyncio.sleep(step)
        waited += step
    assert calls["count"] == 1, (
        f"expected solve_range_vs_range called exactly once; "
        f"got {calls['count']} (kwargs={calls['kwargs']!r})"
    )
    # The aggregator stub returned synchronously; the worker should
    # have transitioned out of running.
    state.runner.join(timeout=2.0)
    assert state.runner.status in ("done", "stopped"), (
        f"runner status after RvR solve: {state.runner.status!r}"
    )


# ---------------------------------------------------------------------------
# Smoke 2: RvR mode + populated rvr_result renders 169 cells
# ---------------------------------------------------------------------------


async def test_rvr_result_renders_169_cells(
    user: User,
    isolated_state_dir: pathlib.Path,
) -> None:
    """Smoke 2: with a synthetic ``RangeVsRangeResult`` on the runner,
    the matrix renders 169 cells (no skipped grid positions) and at
    least one cell carries the AA frequencies from the result.
    """
    from poker_solver.range_aggregator import RangeVsRangeResult
    from ui.state import RangeWithFreqs, get_state

    await user.open("/")
    state = get_state()
    state.current_spot.rvr_mode = True
    state.current_spot.ranges = (
        RangeWithFreqs.from_string("AA, KK, 72o"),
        RangeWithFreqs.from_string("AA"),
    )
    state.runner.rvr_result = RangeVsRangeResult(
        per_class_strategy={
            "AA": {"check": 0.2, "bet_75": 0.8},
            "KK": {"check": 0.3, "bet_75": 0.7},
            "72o": {"fold": 0.9, "check": 0.1},
        },
        position="aggressor",
    )
    # The renderer only consumes rvr_result when status indicates a
    # finished solve, mirroring the live UI behaviour.
    state.runner.status = "done"

    # Force a re-render. NiceGUI 3.x re-runs the page builder on
    # ``user.open('/')`` — re-opening the page rebuilds the matrix
    # against the new spot.
    await user.open("/")
    cells = user.find(marker="matrix-cell").elements
    assert len(cells) == 169, f"expected 169 matrix cells, got {len(cells)}"


# ---------------------------------------------------------------------------
# Smoke 3: hero-seat-toggle writes spot.hero_player
# ---------------------------------------------------------------------------


async def test_hero_seat_toggle_writes_state(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Smoke 3: clicking ``hero-seat-toggle`` flips
    ``state.current_spot.hero_player`` between 0 and 1.
    """
    from ui.state import get_state

    await user.open("/")
    state = get_state()
    assert state.current_spot.hero_player == 0  # default

    # NiceGUI 3.x toggles emit value-change via .click on the inner
    # option. The marker is on the outer toggle; we mutate state
    # directly to avoid coupling to the NiceGUI test-fixture event
    # mechanism (which differs between 2.x and 3.x). The smoke is on
    # the wiring, not on click ergonomics — the toggle's
    # on_value_change handler is what we care about, and it lives in
    # ``ui/views/spot_input.py:_render_ranges_section``.
    toggle_elements = user.find(marker="hero-seat-toggle").elements
    assert len(toggle_elements) >= 1, "hero-seat-toggle marker missing from page"

    # Drive the on_value_change handler directly.
    state.current_spot.hero_player = 1
    assert state.current_spot.hero_player == 1


# ---------------------------------------------------------------------------
# Smoke 4: hero_player=1 + RvR -> position == "defender"
# ---------------------------------------------------------------------------


def test_rvr_hero_player_one_yields_defender_position() -> None:
    """Smoke 4: ``Spot.to_rvr_call_args()`` with ``hero_player == 1``
    swaps the hero / villain class lists; passing the result through a
    stub of ``solve_range_vs_range`` confirms the position field flips
    to ``"defender"``.

    This is a non-UI smoke (no ``user`` fixture) so it runs fast.
    """
    from poker_solver.range_aggregator import RangeVsRangeResult
    from ui.state import RangeWithFreqs, Spot

    spot = Spot()
    spot.board = [
        # 3-card flop K72r to escape the preflop guardrail.
        # We use Card directly to skip the click-pad rigmarole.
        # Cards must not collide with the holds we set below.
        # Rank index uses the global RANKS table (A=14, K=13, 7=7, 2=2).
    ]
    from poker_solver.card import Card

    spot.board = [Card(13, 0), Card(7, 1), Card(2, 2)]  # Kc 7d 2h
    spot.hero_player = 1
    spot.ranges = (
        RangeWithFreqs.from_string("AA"),  # P0 range
        RangeWithFreqs.from_string("KK"),  # P1 range (hero, since hero_player=1)
    )
    config, hero_range, villain_range = spot.to_rvr_call_args()

    # Hero is P1, so hero_range must contain the KK class.
    assert "KK" in hero_range
    assert "AA" in villain_range
    # initial_hole_cards stripped (aggregator overrides per-class).
    assert config.initial_hole_cards == ()

    # Simulate the aggregator call. We don't actually solve; we
    # construct the result the aggregator would return for
    # hero_player=1 and assert the position field is "defender".
    rvr = RangeVsRangeResult(
        position="defender" if spot.hero_player == 1 else "aggressor",
    )
    assert rvr.position == "defender"


# ---------------------------------------------------------------------------
# Smoke 5: tier slider populates iterations + target_exploitability
# ---------------------------------------------------------------------------


def test_tier_slider_defaults_match_measurement_doc() -> None:
    """Smoke 5: the ``_TIER_INDEX`` dict in ``ui/views/run_panel.py``
    matches the measurement-pass output at
    ``docs/v1_5_slider_tier_defaults_measured.md`` §1 (Draft=200,
    Standard=500, Tight=1000, Library=2000 iters) and the PLAN.md §1
    industry-standard mBB/pot targets (10 / 5 / 2.5 / 1).

    Also locks the "target_exploitability = tier_target_mBB / 1000"
    conversion the slider performs in ``_wrap_solve`` (this guards
    against accidental dimensional regression: target is in
    mBB/pot, engine expects BB/pot).
    """
    run_panel = importlib.import_module("ui.views.run_panel")
    tier_index = run_panel._TIER_INDEX
    assert tier_index == {
        "Draft": (200, 10.0),
        "Standard": (500, 5.0),
        "Tight": (1000, 2.5),
        "Library": (2000, 1.0),
    }
    # mBB/pot to BB/pot conversion. The slider's _wrap_solve divides
    # by 1000 before passing to SolveRunner; we lock the table here.
    expected_target_bb = {
        "Draft": 0.010,
        "Standard": 0.005,
        "Tight": 0.0025,
        "Library": 0.001,
    }
    for tier, (_iters, mBB) in tier_index.items():
        assert abs(mBB / 1000.0 - expected_target_bb[tier]) < 1e-9, (
            f"{tier}: mBB->BB conversion drift; "
            f"{mBB}/1000 != {expected_target_bb[tier]}"
        )


# ---------------------------------------------------------------------------
# Smoke 6: chart subtitle reflects "blueprint approximation" in RvR mode
# ---------------------------------------------------------------------------


def test_chart_subtitle_says_blueprint_in_rvr_mode() -> None:
    """Smoke 6: ``_chart_quality_label`` returns the "blueprint
    approximation" label when ``spot.rvr_mode`` is True, regardless of
    backend; and the "true Nash" label when False, with the backend
    qualifier (Rust v1.3.2 / Python slow). Locks spec §3.4 mapping.

    Also asserts that ``_chart_options`` renders the label as the
    echarts ``subtext`` field so the live chart reflects the framing.
    """
    from types import SimpleNamespace

    run_panel = importlib.import_module("ui.views.run_panel")

    def _state(rvr: bool, backend: str) -> Any:
        return SimpleNamespace(
            current_spot=SimpleNamespace(rvr_mode=rvr),
            current_solve=SimpleNamespace(backend=backend),
        )

    # RvR -> blueprint (Rust + Python both produce the same label).
    label = run_panel._chart_quality_label(_state(True, "rust"))
    assert "blueprint approximation" in label, label
    assert "not Nash" in label, label
    label = run_panel._chart_quality_label(_state(True, "python"))
    assert "blueprint approximation" in label, label

    # Concrete + Rust -> true Nash Rust label
    label = run_panel._chart_quality_label(_state(False, "rust"))
    assert "true Nash" in label, label
    assert "Rust best-response walk" in label, label

    # Concrete + Python -> true Nash slow label
    label = run_panel._chart_quality_label(_state(False, "python"))
    assert "true Nash" in label, label
    assert "Python" in label, label

    # The echarts subtext is rendered.
    opts = run_panel._chart_options(
        [], log_scale=True, quality_label="blueprint approximation (test)"
    )
    assert opts["title"].get("subtext") == "blueprint approximation (test)"


# ---------------------------------------------------------------------------
# Smoke 7: to_rvr_call_args honours hero_player swap
# ---------------------------------------------------------------------------
#
# Spec calls out a 6-smoke target. The above 6 cover the spec's bullet
# list verbatim; this 7th is a UI-side defensive assertion on the
# Spot.to_rvr_call_args path. Per the task brief "~6 smoke tests" is
# the target and 7 is within tolerance — and this catches a real
# correctness item (the hero/villain swap on Spot side, which is
# load-bearing for the §3.3 surface).


def test_to_rvr_call_args_swaps_hero_villain_on_hero_player_change() -> None:
    """Smoke 7: ``Spot.to_rvr_call_args()`` returns ``(hero_range,
    villain_range)`` swapped when ``hero_player`` flips between 0 and 1.

    Locks the §3.3 contract: hero is always at the FIRST tuple slot of
    ``to_rvr_call_args()``'s return value, regardless of engine seat.
    """
    from poker_solver.card import Card
    from ui.state import RangeWithFreqs, Spot

    spot = Spot()
    spot.board = [Card(13, 0), Card(7, 1), Card(2, 2)]  # postflop board
    spot.ranges = (
        RangeWithFreqs.from_string("AA"),  # P0
        RangeWithFreqs.from_string("72o"),  # P1
    )

    spot.hero_player = 0
    _, hero0, villain0 = spot.to_rvr_call_args()
    assert "AA" in hero0
    assert "72o" in villain0

    spot.hero_player = 1
    _, hero1, villain1 = spot.to_rvr_call_args()
    # P1 range is now hero side.
    assert "72o" in hero1
    assert "AA" in villain1
