"""Smoke tests for the 13×13 preflop chart widget (task #55).

Covers the five user-facing additions per the task spec:

1. Smoke: tab loads + 169 cells rendered (13x13 grid topology).
2. Click cell -> side panel renders the per-action breakdown.
3. Range string change re-renders the matrix (cell projection updates).
4. Iter count > 0 triggers a real solve dispatch (mocked binding).
5. Hand-class layout matches the standard Pio convention (AA top-left,
   suited above-diagonal, offsuit below).

Engine-bound tests mock ``_rust.solve_hunl_preflop_rvr`` so the wall
clock stays sub-second. The smoke is on the UI wiring, not on the Rust
solver (which is covered by ``crates/cfr_core/tests/preflop_rvr_smoke.rs``).
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
    """Override HOME so state.json lands in tmp_path; reset runner."""
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


# ---------------------------------------------------------------------------
# Smoke 1: tab loads + 169 cells rendered
# ---------------------------------------------------------------------------


async def test_preflop_chart_tab_loads_with_169_cells(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Tab loads, exposes the 169-cell grid topology, and the chart
    starts in the "no chart computed yet" state (empty/grey cells)."""
    await user.open("/")
    # The "Preflop Chart" tab marker is registered by ``ui/app.py``.
    tab_markers = user.find(marker="tab-preflop-chart").elements
    assert len(tab_markers) >= 1, "preflop chart tab not found in page"
    # The chart container is rendered even before any solve fires.
    display = user.find(marker="preflop-chart-display").elements
    assert len(display) >= 1, "preflop-chart-display marker missing"
    # 169 cells (13 rows x 13 cols).
    cells = user.find(marker="preflop-chart-cell").elements
    assert len(cells) == 169, f"expected 169 preflop-chart cells, got {len(cells)}"


# ---------------------------------------------------------------------------
# Smoke 2: click cell -> side panel shows breakdown
# ---------------------------------------------------------------------------


async def test_cell_click_renders_detail_panel(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Clicking a cell stashes the selected class onto state.prefs and
    re-renders the detail panel with the per-action breakdown."""
    from ui.state import get_state
    from ui.views import preflop_chart

    await user.open("/")
    state = get_state()
    # Inject a synthetic chart_result so the detail panel has data.
    state.runner.preflop_chart_result = {
        "per_class": {
            "AA": {"fold": 0.0, "call": 0.05, "open_3": 0.20, "all_in": 0.75},
            "72o": {"fold": 0.98, "call": 0.02},
        },
        "actions": ["fold", "call", "open_3", "all_in"],
        "iterations": 500,
        "wallclock_seconds": 1.2,
    }
    state.runner._mode = "preflop_chart"
    state.runner.status = "done"
    # Stash the selected class directly (bypasses click ergonomics).
    preflop_chart._set_selected_cell_label(state, "AA")
    await user.open("/")
    detail = user.find(marker="preflop-chart-detail").elements
    assert len(detail) >= 1, "preflop-chart-detail marker missing"
    # The detail rows include each action label from the chart_result.
    for label in ("fold", "call", "open_3", "all_in"):
        rows = user.find(marker=f"preflop-chart-detail-row-{label}").elements
        assert len(rows) >= 1, f"detail row for {label!r} not rendered"


# ---------------------------------------------------------------------------
# Smoke 3: range changes -> matrix refreshes (project_chart respects new state)
# ---------------------------------------------------------------------------


def test_range_change_reprojects_matrix() -> None:
    """``project_chart`` is the load-bearing projection. A change to
    ``runner.preflop_chart_result`` (driven by a new solve after a range
    edit) must surface immediately in the projected per-class summaries
    — no caching or memoization is allowed.
    """
    from ui.views import preflop_chart

    # Initial result: AA opens 100%.
    res1 = {"per_class": {"AA": {"open_3": 1.0}}, "iterations": 100}
    out1 = preflop_chart.project_chart(res1)
    assert "AA" in out1 and out1["AA"].dominant_label == "open_3"
    # New result (post range change): AA jams 100%.
    res2 = {"per_class": {"AA": {"all_in": 1.0}}, "iterations": 100}
    out2 = preflop_chart.project_chart(res2)
    assert out2["AA"].dominant_label == "all_in"
    assert out2["AA"].dominant_kind == "jam"


# ---------------------------------------------------------------------------
# Smoke 4: iter count > 0 dispatches to _rust.solve_hunl_preflop_rvr
# ---------------------------------------------------------------------------


async def test_solve_button_dispatches_rust_binding(
    user: User,
    isolated_state_dir: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clicking Solve with CUSTOM action sizes invokes
    ``_rust.solve_hunl_preflop_rvr`` (mocked here) with the iteration count
    + the edited action menu.

    The default ``(100BB, no-ante)`` spot is covered by the Premium-A
    blueprint asset, so a *default*-sizes click is correctly served from the
    blueprint and never touches Rust (the blueprint-vs-live fast path). To
    assert the LIVE dispatch this test edits the open sizes to a non-default
    value (``2.5,3.5,4.5``), which diverges from the FIXED menu the blueprint
    was solved against. Per U05 that divergence MUST bypass the blueprint and
    route to a live ``solve_hunl_preflop_rvr`` solve — which is exactly what
    we verify here."""
    calls: dict[str, Any] = {"count": 0, "args": None}

    def _fake_solve(
        config_json: str,
        equity_path: str,
        iterations: int,
        alpha: float,
        beta: float,
        gamma: float,
        opens: Any = None,
        mults: Any = None,
        p0_holes: Any = None,
        p1_holes: Any = None,
    ) -> dict[str, Any]:
        calls["count"] += 1
        calls["args"] = {
            "iterations": iterations,
            "opens": opens,
            "mults": mults,
        }
        # Minimal output the worker's projection can consume.
        return {
            "average_strategy": {
                # "AsAh" + suffix "||p|" (root SB decision)
                "AsAh||p|": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            },
            "iterations": iterations,
            "wallclock_seconds": 0.01,
            "decision_node_count": 1,
            "strategy_entry_count": 1,
            "hand_count_per_player": [1, 1],
            "backend": "rust_preflop_rvr",
        }

    # Inject the fake binding by adding it onto the _rust module attr.
    # Use SimpleNamespace so attribute access does NOT engage descriptor
    # protocol (a plain function on a class becomes a bound method and
    # adds an unwanted ``self`` arg).
    import poker_solver
    from types import SimpleNamespace

    fake_module = SimpleNamespace(solve_hunl_preflop_rvr=_fake_solve)
    monkeypatch.setattr(poker_solver, "_rust", fake_module, raising=False)

    # Force the LIVE solve path. The default spot (100 BB / 0 ante) is an
    # EXACT shard in the Premium-A blueprint bundle (assets/blueprints/
    # manifest.json, shipped after this test was written in commit
    # 1783bef), so ``_on_preflop_chart_solve`` would short-circuit on a
    # blueprint hit and never dispatch the live binding. This test
    # validates the *live* dispatch, so we stub the blueprint lookup to
    # miss (returns False => fall through to start_preflop_chart).
    from ui.state import SolveRunner

    monkeypatch.setattr(
        SolveRunner, "try_blueprint_preflop_chart", lambda self, **kw: False
    )

    await user.open("/")
    # Edit the open sizes to a NON-default value so the click diverges from
    # the blueprint's fixed menu (2/3/4/5bb) and is forced down the live Rust
    # path (U05). Without this the default-100BB spot is blueprint-covered and
    # Solve would (correctly) serve from the asset without touching Rust.
    opens_field = user.find(marker="preflop-chart-open-sizes")
    opens_field.clear()
    opens_field.type("2.5,3.5,4.5")
    # Click Solve directly (no need to navigate the tab — the button is
    # in the page DOM regardless of which tab is visible).
    user.find(marker="preflop-chart-solve-button").click()
    # Wait for the worker to land.
    deadline, waited, step = 4.0, 0.0, 0.1
    while waited < deadline and calls["count"] == 0:
        await asyncio.sleep(step)
        waited += step
    assert calls["count"] == 1, (
        f"expected solve_hunl_preflop_rvr called once; got {calls['count']}"
    )
    # Iteration count was forwarded.
    assert calls["args"]["iterations"] >= 1
    # The edited action menu made it through as parsed lists (not None).
    # ``opens`` reflects the custom value we typed; ``mults`` keeps the
    # pre-filled default list. Both arrive as lists, not None.
    assert isinstance(calls["args"]["opens"], list)
    assert isinstance(calls["args"]["mults"], list)
    assert calls["args"]["opens"] == [2.5, 3.5, 4.5]


# ---------------------------------------------------------------------------
# Smoke 5: standard chart layout (AA top-left, suited above diagonal, etc.)
# ---------------------------------------------------------------------------


def test_chart_layout_matches_standard_pio_convention() -> None:
    """Locks the canonical layout:
      * row 0, col 0 = AA
      * row 12, col 12 = 22
      * above-diagonal = suited (e.g. row 0 col 1 = AKs)
      * below-diagonal = offsuit (e.g. row 1 col 0 = AKo)
      * diagonal = pairs (e.g. row 5 col 5 = 99)
    """
    from ui.views import preflop_chart

    assert preflop_chart.hand_class_at(0, 0) == "AA"
    assert preflop_chart.hand_class_at(12, 12) == "22"
    assert preflop_chart.hand_class_at(0, 1) == "AKs"  # suited
    assert preflop_chart.hand_class_at(1, 0) == "AKo"  # offsuit
    assert preflop_chart.hand_class_at(5, 5) == "99"  # pair
    assert preflop_chart.hand_class_at(0, 12) == "A2s"
    assert preflop_chart.hand_class_at(12, 0) == "A2o"


# ---------------------------------------------------------------------------
# Smoke 6: action classification + color anchors (locks RYG palette)
# ---------------------------------------------------------------------------


def test_classify_action_and_dominant_color() -> None:
    """Locks the engine-label -> bucket mapping (fold/call/raise/jam) and
    the per-bucket color anchor."""
    from ui.views import preflop_chart

    assert preflop_chart.classify_action("fold") == "fold"
    assert preflop_chart.classify_action("call") == "call"
    assert preflop_chart.classify_action("check") == "call"
    assert preflop_chart.classify_action("all_in") == "jam"
    assert preflop_chart.classify_action("jam") == "jam"
    assert preflop_chart.classify_action("open_3") == "raise"
    assert preflop_chart.classify_action("raise_4") == "raise"

    # Pure-fold cell -> grey anchor; pure-raise -> red anchor.
    fold_summary = preflop_chart.aggregate_actions({"fold": 1.0})
    assert preflop_chart.cell_color_rgb(fold_summary)[0] < 150  # red channel low
    raise_summary = preflop_chart.aggregate_actions({"open_3": 1.0})
    # Red anchor (220, 60, 60): red channel high, green channel low.
    r, g, _ = preflop_chart.cell_color_rgb(raise_summary)
    assert r > g, "raise anchor should have R > G"


# ---------------------------------------------------------------------------
# Root "call" == limp: the OPEN chart labels SB-complete as "L"/limp, while
# facing-action charts keep "C"/call for a genuine call.
# ---------------------------------------------------------------------------


def test_root_call_renders_as_limp_facing_keeps_call() -> None:
    """At the OPEN/root node the SB's "call" action is a *limp* (completing
    the small blind), so the footer tag reads ``L`` and the tooltip says
    "limp (complete the SB)". A facing-action / call-vs-open node keeps ``C``
    and the raw "call" label.
    """
    from ui.views import preflop_chart

    # AA on the OPEN chart, call-dominant at 36% (limp).
    aa_root = preflop_chart.aggregate_actions(
        {"call": 0.36, "fold": 0.30, "raise_4": 0.34}
    )
    assert aa_root.dominant_kind == "call"
    # OPEN/root context -> "L" (limp), not "C".
    assert preflop_chart._cell_tag(aa_root, is_open_root=True) == "L36"
    # Facing-action context -> genuine "C" (call).
    assert preflop_chart._cell_tag(aa_root, is_open_root=False) == "C36"

    # Tooltip mirrors the relabel on the OPEN chart...
    root_tip = preflop_chart._tooltip_text("AA", aa_root, is_open_root=True)
    assert "limp (complete the SB)" in root_tip
    assert "call" not in root_tip  # the raw label is suppressed at the root
    # ...but a facing-action node still surfaces the raw "call" label.
    facing_tip = preflop_chart._tooltip_text("AA", aa_root, is_open_root=False)
    assert "call 36%" in facing_tip
    assert "limp" not in facing_tip

    # The non-call buckets are unaffected by the root relabel.
    fold_cell = preflop_chart.aggregate_actions({"fold": 1.0})
    assert preflop_chart._cell_tag(fold_cell, is_open_root=True) == "F100"
    raise_cell = preflop_chart.aggregate_actions({"open_3": 1.0})
    assert preflop_chart._cell_tag(raise_cell, is_open_root=True) == "R100"


def test_is_open_root_line_detection() -> None:
    """The root/open context is the SB's first decision (``"||p|"`` — no
    action tokens). Any node carrying a limp/bet/raise token is a
    facing-action line and must NOT be treated as the open root.
    """
    from ui.views import preflop_chart

    # Root forms: bare marker, normalized variant, and "nothing selected".
    assert preflop_chart._is_open_root_line("||p|") is True
    assert preflop_chart._is_open_root_line("|p|") is True
    assert preflop_chart._is_open_root_line(None) is True
    # Facing-action lines (limped pot, BB-vs-open, 3-bet) are NOT the root.
    assert preflop_chart._is_open_root_line("||p|c") is False  # limped pot
    assert preflop_chart._is_open_root_line("||p|b200") is False  # BB vs open
    assert preflop_chart._is_open_root_line("||p|b200r400") is False  # 3-bet


# ---------------------------------------------------------------------------
# Smoke 7: parse_size_list rejects garbage with ValueError
# ---------------------------------------------------------------------------


def test_parse_size_list_rejects_garbage() -> None:
    """Action-menu input control's parser must hard-fail on garbage so
    the UI can surface a notify; empty input is allowed (engine defaults)."""
    from ui.views import preflop_chart

    assert preflop_chart.parse_size_list("") == []
    assert preflop_chart.parse_size_list("   ") == []
    assert preflop_chart.parse_size_list("2,3,4") == [2.0, 3.0, 4.0]
    assert preflop_chart.parse_size_list("2.0, 2.5, 3") == [2.0, 2.5, 3.0]
    with pytest.raises(ValueError):
        preflop_chart.parse_size_list("2, garbage, 4")


# ---------------------------------------------------------------------------
# N5: header subtitle must agree with the grid + source badge
# ---------------------------------------------------------------------------


def _fake_chart_state(
    chart_result: dict[str, Any] | None,
    *,
    route_source: str | None = None,
    status: str = "idle",
    mode: str = "preflop_chart",
) -> Any:
    """Build a minimal AppState-shaped fake for ``_chart_subtitle``.

    ``available_preflop_lines() -> []`` keeps ``_line_chart_result`` on its
    root early-return so it hands back ``chart_result`` unchanged (which is what
    a single-node blueprint root looks like to the grid).
    """
    from types import SimpleNamespace

    route_info = None
    if route_source is not None:
        route_info = SimpleNamespace(source=SimpleNamespace(value=route_source))
    runner = SimpleNamespace(
        preflop_chart_result=chart_result,
        preflop_route_info=route_info,
        status=status,
        _mode=mode,
        available_preflop_lines=lambda: [],
    )
    return SimpleNamespace(runner=runner)


def test_chart_subtitle_empty_state_only_when_no_chart() -> None:
    """N5: "no chart computed yet" appears ONLY when the grid is empty.

    The subtitle's empty-state must be keyed on the SAME source of truth the
    grid paints from (``project_chart(_line_chart_result(state))``). Before the
    fix the subtitle was a one-shot label that never re-rendered, so it stayed
    on the empty-state text even after a blueprint solve populated the grid.
    """
    from ui.views import preflop_chart

    # No result at all -> genuine empty state.
    empty_state = _fake_chart_state(None, route_source=None, status="idle")
    assert preflop_chart._chart_subtitle(empty_state) == "no chart computed yet"

    # Running, still no result -> the "solving..." caption (not empty state).
    running_state = _fake_chart_state(None, route_source="live", status="running")
    sub = preflop_chart._chart_subtitle(running_state)
    assert "solving" in sub and "no chart computed yet" not in sub

    # Blueprint route: grid IS populated, iters/wall == 0 -> describe the route,
    # NEVER the empty-state text.
    blueprint_result = {
        "per_class": {"AA": {"all_in": 1.0}, "AKs": {"open_3": 1.0}},
        "iterations": 0,
        "wallclock_seconds": 0.0,
    }
    bp_state = _fake_chart_state(
        blueprint_result, route_source="blueprint", status="done"
    )
    bp_sub = preflop_chart._chart_subtitle(bp_state)
    assert "no chart computed yet" not in bp_sub, (
        f"N5 regression: blueprint chart still shows empty-state subtitle: {bp_sub!r}"
    )
    assert "Blueprint" in bp_sub, bp_sub

    # Live route with real iterations -> the iters/wallclock summary survives.
    live_result = {
        "per_class": {"AA": {"all_in": 1.0}},
        "iterations": 500,
        "wallclock_seconds": 12.3,
    }
    live_state = _fake_chart_state(live_result, route_source="live", status="done")
    live_sub = preflop_chart._chart_subtitle(live_state)
    assert "500 iters" in live_sub and "12.3s" in live_sub, live_sub
    assert "no chart computed yet" not in live_sub
