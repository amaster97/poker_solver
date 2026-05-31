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
    """Clicking Solve with CUSTOM action sizes on a FULL range invokes the
    fast 169-class kernel ``_rust.solve_hunl_preflop_rvr_class169`` (mocked
    here) with the iteration count + the edited action menu.

    The default ``(100BB, no-ante)`` spot is covered by the Premium-A
    blueprint asset, so a *default*-sizes click is correctly served from the
    blueprint and never touches Rust (the blueprint-vs-live fast path). To
    assert the LIVE dispatch this test edits the open sizes to a non-default
    value (``2.5,3.5,4.5``), which diverges from the FIXED menu the blueprint
    was solved against. Per U05 that divergence MUST bypass the blueprint and
    route to a live solve.

    Fix 1b: a FULL-range live solve (both holes None) routes to the 169-class
    kernel (~30-60x faster), NOT the 1326-combo ``solve_hunl_preflop_rvr``.
    The class169 kernel takes per-class root-reach 169-vectors (None == full)
    in the last two positional slots instead of explicit holes, and emits
    ``"<class_label>||p|<history>"`` keys."""
    calls: dict[str, Any] = {"count": 0, "args": None, "legacy_count": 0}

    def _fake_solve_class169(
        config_json: str,
        equity_path: str,
        iterations: int,
        alpha: float,
        beta: float,
        gamma: float,
        opens: Any = None,
        mults: Any = None,
        root_reach_p0: Any = None,
        root_reach_p1: Any = None,
    ) -> dict[str, Any]:
        calls["count"] += 1
        calls["args"] = {
            "iterations": iterations,
            "opens": opens,
            "mults": mults,
            "root_reach_p0": root_reach_p0,
            "root_reach_p1": root_reach_p1,
        }
        # Minimal class-169-keyed output the worker's projection can consume:
        # "<class_label>||p|<history>" with empty history = root SB decision.
        return {
            "average_strategy": {
                "AA||p|": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            },
            "iterations": iterations,
            "wallclock_seconds": 0.01,
            "decision_node_count": 1,
            "strategy_entry_count": 1,
            "backend": "rust_preflop_rvr_class169",
            "hand_resolution": "class_169",
        }

    def _fake_solve_legacy(*_a: Any, **_k: Any) -> dict[str, Any]:
        # The 1326-combo kernel must NOT be called for a full range.
        calls["legacy_count"] += 1
        return {"average_strategy": {}, "iterations": 0, "wallclock_seconds": 0.0}

    # Inject the fake bindings onto the _rust module attr. Use SimpleNamespace
    # so attribute access does NOT engage descriptor protocol (a plain function
    # on a class becomes a bound method and adds an unwanted ``self`` arg).
    import poker_solver
    from types import SimpleNamespace

    fake_module = SimpleNamespace(
        solve_hunl_preflop_rvr_class169=_fake_solve_class169,
        solve_hunl_preflop_rvr=_fake_solve_legacy,
    )
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
        "expected solve_hunl_preflop_rvr_class169 called once; got "
        f"{calls['count']}"
    )
    # The slow 1326-combo kernel must NOT have been used for a full range.
    assert calls["legacy_count"] == 0, (
        "full-range live solve must use the fast 169-class kernel, not "
        f"solve_hunl_preflop_rvr (called {calls['legacy_count']}x)"
    )
    # Iteration count was forwarded.
    assert calls["args"]["iterations"] >= 1
    # The edited action menu made it through as parsed lists (not None).
    # ``opens`` reflects the custom value we typed; ``mults`` keeps the
    # pre-filled default list. Both arrive as lists, not None.
    assert isinstance(calls["args"]["opens"], list)
    assert isinstance(calls["args"]["mults"], list)
    assert calls["args"]["opens"] == [2.5, 3.5, 4.5]
    # Full range -> default (None) per-class root reach (combo-weighted in the
    # engine), NOT explicit holes.
    assert calls["args"]["root_reach_p0"] is None
    assert calls["args"]["root_reach_p1"] is None


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


# ===========================================================================
# Preflop Chart "Configure preflop solve" page — 5 coherent UI fixes.
# ===========================================================================


# ---------------------------------------------------------------------------
# Fix 1: color-code lines by actor — preflop_line_actor(suffix) -> "SB"/"BB".
# The engine's turn rule at ``||p|<tokens>``: root (no tokens) = SB; play
# alternates per token, so EVEN token count => SB acts, ODD => BB acts.
# ---------------------------------------------------------------------------


def test_preflop_line_actor_alternates_per_token() -> None:
    """SB at the root + on even token counts; BB on odd counts."""
    from ui.views import preflop_chart

    actor = preflop_chart.preflop_line_actor
    # Root / None -> SB (engine root cur_player == 0 == SB).
    assert actor(None) == "SB"
    assert actor("||p|") == "SB"
    assert actor("|p|") == "SB"  # normalized variant tolerated
    # The exact spec cases.
    assert actor("||p|") == "SB"  # 0 tokens
    assert actor("||p|b200") == "BB"  # 1 token
    assert actor("||p|b200r400") == "SB"  # 2 tokens
    assert actor("||p|A") == "BB"  # 1 token (facing root all-in)
    assert actor("||p|b200A") == "SB"  # 2 tokens
    assert actor("||p|b200r400A") == "BB"  # 3 tokens
    # A limp (call) token also counts toward alternation.
    assert actor("||p|c") == "BB"  # 1 token (BB after SB limp)
    # Undecodable grammar falls back to the root actor (SB).
    assert actor("||p|zzz") == "SB"


def test_preflop_line_actor_color_distinct_per_actor() -> None:
    """SB and BB map to two distinct theme-aware accents."""
    from ui.views import preflop_chart

    sb = preflop_chart.preflop_line_actor_color("SB")
    bb = preflop_chart.preflop_line_actor_color("BB")
    assert sb != bb
    assert sb.startswith("var(--ps-") and bb.startswith("var(--ps-")


# ---------------------------------------------------------------------------
# Fix 2: clearer labels — actor shown in the selector + "(vs all-in)" reworded.
# ---------------------------------------------------------------------------


def test_preflop_line_label_allin_phrase_override() -> None:
    """``preflop_line_label`` keeps its default output but accepts a reworded
    all-in phrase. The base (non-all-in) names are unchanged so existing
    callers/tests stay valid."""
    from ui.views import preflop_chart

    label = preflop_chart.preflop_line_label
    # Unchanged base labels (no all-in).
    assert label(None) == "Open (RFI)"
    assert label("||p|") == "Open (RFI)"
    assert label("||p|b200") == "BB vs open"
    assert label("||p|b200r400") == "3-bet"
    # Default all-in phrasing is preserved (back-compat).
    assert label("||p|A") == "Open (RFI) (vs all-in)"
    # Reworded phrasing for the selector: unambiguous call/fold framing.
    selector = label("||p|A", allin_phrase="— facing all-in (call/fold)")
    assert selector == "Open (RFI) — facing all-in (call/fold)"
    assert "(vs all-in)" not in selector


def test_line_options_show_actor_and_reworded_allin() -> None:
    """The line-selector options are prefixed with the acting player and use
    the reworded all-in phrase (no bare contradictory "(vs all-in)")."""
    from types import SimpleNamespace

    from ui.views import preflop_chart

    lines = ["||p|", "||p|b200", "||p|b200r400", "||p|A"]
    state = SimpleNamespace(
        runner=SimpleNamespace(available_preflop_lines=lambda: lines)
    )
    opts = preflop_chart._line_options(state)
    # Root line: SB decides.
    assert opts["||p|"].startswith("[SB] ")
    assert "Open (RFI)" in opts["||p|"]
    # BB-vs-open line: BB decides.
    assert opts["||p|b200"].startswith("[BB] ")
    # All-in line is reworded (call/fold framing), not the bare "(vs all-in)".
    allin_opt = opts["||p|A"]
    assert "facing all-in (call/fold)" in allin_opt
    assert "(vs all-in)" not in allin_opt


async def test_actor_badge_renders_decides_text(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """The grid header carries a "<SB|BB> decides" badge so whose strategy the
    grid shows is obvious at a glance. At the open/root the SB decides."""
    await user.open("/")
    # The badge element is marked ``preflop-chart-actor-badge`` and shows the
    # root actor (SB) text. ``User.should_see`` matches rendered text.
    user.find(marker="preflop-chart-actor-badge")
    await user.should_see("SB decides")


# ---------------------------------------------------------------------------
# Fix 5: iterations no-op clarity — blueprint route greys/annotates iterations.
# ---------------------------------------------------------------------------


def test_range_is_restricted_full_vs_subset() -> None:
    """A full 1326-combo range is NOT a restriction; a subset IS."""
    from ui.state import RangeWithFreqs
    from ui.views import preflop_chart

    full = RangeWithFreqs.full()
    assert preflop_chart._range_is_restricted(full) is False
    # A small hard range is a restriction.
    subset = RangeWithFreqs.from_string("AA, KK, AKs")
    assert preflop_chart._range_is_restricted(subset) is True
    # Empty range is not treated as a (live-forcing) restriction.
    empty = RangeWithFreqs.empty()
    assert preflop_chart._range_is_restricted(empty) is False


def test_next_solve_hits_blueprint_predictor() -> None:
    """The route predictor: default sizes + full ranges -> blueprint (iters
    ignored); a restricted range -> live (iters honored)."""
    from types import SimpleNamespace

    from ui.state import RangeWithFreqs, Spot
    from ui.views import preflop_chart

    # Default spot: full ranges, default (None) pending sizes -> blueprint.
    spot = Spot()
    runner = SimpleNamespace(
        _pending_preflop_chart_opens=None,
        _pending_preflop_chart_mults=None,
    )
    state = SimpleNamespace(current_spot=spot, runner=runner)
    assert preflop_chart._next_solve_hits_blueprint(state) is True

    # Restrict the hero range -> live path (iterations matter).
    spot.ranges = (RangeWithFreqs.from_string("AA, KK"), spot.ranges[1])
    assert preflop_chart._next_solve_hits_blueprint(state) is False


# ---------------------------------------------------------------------------
# Fix 4: wire Hero/Villain ranges into the solve.
# ---------------------------------------------------------------------------


def test_preflop_holes_from_range_full_returns_none() -> None:
    """A full range yields None (no restriction); a subset yields explicit
    [card_int, card_int] holes."""
    from ui import app
    from ui.state import RangeWithFreqs

    assert app._preflop_holes_from_range(RangeWithFreqs.full()) is None
    holes = app._preflop_holes_from_range(RangeWithFreqs.from_string("AA"))
    assert holes is not None
    # AA = 6 combos; each a 2-int list.
    assert len(holes) == 6
    assert all(len(h) == 2 and all(isinstance(c, int) for c in h) for h in holes)


async def test_restricted_range_forces_live_with_holes(
    user: User,
    isolated_state_dir: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A restricted Hero range must (a) bypass the blueprint and (b) thread
    non-None ``hero_holes`` into ``start_preflop_chart``."""
    from ui.state import RangeWithFreqs, SolveRunner, get_state

    captured: dict[str, Any] = {"called": 0, "kwargs": None}

    def _fake_start(self: Any, config: Any, **kwargs: Any) -> None:
        captured["called"] += 1
        captured["kwargs"] = kwargs

    monkeypatch.setattr(SolveRunner, "start_preflop_chart", _fake_start)

    # Track whether the blueprint was even consulted as a hit. The real
    # try_blueprint_preflop_chart must DECLINE (return False) for a restricted
    # range so we fall through to the live dispatch.
    real_try = SolveRunner.try_blueprint_preflop_chart
    bp_calls: dict[str, Any] = {"result": None}

    def _spy_try(self: Any, **kw: Any) -> bool:
        out = real_try(self, **kw)
        bp_calls["result"] = out
        return out

    monkeypatch.setattr(SolveRunner, "try_blueprint_preflop_chart", _spy_try)

    await user.open("/")
    state = get_state()
    # Restrict the Hero range to a hard subset (not the full deck).
    state.current_spot.ranges = (
        RangeWithFreqs.from_string("AA, KK, QQ"),
        RangeWithFreqs.full(),
    )

    from ui.app import _on_preflop_chart_solve

    with user.client:
        _on_preflop_chart_solve(state)

    # Blueprint declined (range bypass) -> live dispatch fired with holes.
    assert bp_calls["result"] is False, (
        "restricted range must bypass the blueprint (try returned "
        f"{bp_calls['result']!r})"
    )
    assert captured["called"] == 1, "live start_preflop_chart was not called"
    kwargs = captured["kwargs"]
    assert kwargs["hero_holes"] is not None, "hero_holes not threaded through"
    # AA+KK+QQ = 18 combos.
    assert len(kwargs["hero_holes"]) == 18
    # Villain was full, but the engine requires BOTH holes supplied or BOTH
    # omitted. Restricting only Hero coerces the full Villain side to the
    # complete 1326-combo enumeration (NOT None) so the engine call is legal.
    assert kwargs["villain_holes"] is not None, (
        "one-sided restriction must coerce the full side to explicit holes "
        "(both-or-neither invariant)"
    )
    assert len(kwargs["villain_holes"]) == 1326


# ---------------------------------------------------------------------------
# Fix 3: solve-button feedback notifies per route.
# ---------------------------------------------------------------------------


async def test_blueprint_hit_notifies(
    user: User,
    isolated_state_dir: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A blueprint hit surfaces a 'Loaded precomputed blueprint chart' toast."""
    from ui.state import SolveRunner, get_state

    # Force a blueprint hit regardless of asset coverage.
    monkeypatch.setattr(
        SolveRunner, "try_blueprint_preflop_chart", lambda self, **kw: True
    )

    await user.open("/")
    state = get_state()
    from ui.app import _on_preflop_chart_solve

    with user.client:
        _on_preflop_chart_solve(state)

    assert user.notify.contains("Loaded precomputed blueprint chart"), (
        f"blueprint-hit toast not emitted (messages: {user.notify.messages!r})"
    )


async def test_live_solve_notifies(
    user: User,
    isolated_state_dir: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A live dispatch surfaces a 'Solving live (... iters)' toast."""
    from ui.state import SolveRunner, get_state

    # Blueprint miss -> live path.
    monkeypatch.setattr(
        SolveRunner, "try_blueprint_preflop_chart", lambda self, **kw: False
    )
    # Stub the live start so no worker thread / Rust binding is needed.
    monkeypatch.setattr(
        SolveRunner, "start_preflop_chart", lambda self, config, **kw: None
    )

    await user.open("/")
    state = get_state()
    state.runner._pending_preflop_chart_iterations = 750
    from ui.app import _on_preflop_chart_solve

    with user.client:
        _on_preflop_chart_solve(state)

    assert user.notify.contains("Solving live"), (
        f"live-solve toast not emitted (messages: {user.notify.messages!r})"
    )
    assert user.notify.contains("750"), (
        f"live-solve toast missing iter count (messages: {user.notify.messages!r})"
    )


# ---------------------------------------------------------------------------
# Bug fix: one-sided range restriction must not produce the illegal
# (holes, None) shape that the engine rejects with
# "p0_holes and p1_holes must both be supplied or both omitted".
# ---------------------------------------------------------------------------


def test_coerce_holes_both_full_stays_none() -> None:
    """Both sides full -> (None, None): blueprint/full live path, unchanged."""
    from ui import app

    assert app._coerce_preflop_holes_both_or_neither(None, None) == (None, None)


def test_coerce_holes_one_sided_expands_full_side_to_1326() -> None:
    """Exactly one restricted side -> the full (None) side is replaced with the
    complete 1326-combo enumeration so BOTH are supplied. This is the bug fix:
    the engine rejects (holes, None) / (None, holes)."""
    from ui import app

    villain = [[8, 9], [8, 10]]  # 2 explicit combos
    # Hero full (None), Villain restricted.
    hero_out, villain_out = app._coerce_preflop_holes_both_or_neither(None, villain)
    assert hero_out is not None and villain_out is not None, (
        "neither side may be None when exactly one is restricted"
    )
    assert len(hero_out) == 1326, f"full hero side must be 1326 combos, got {len(hero_out)}"
    assert villain_out == villain, "restricted villain side must be preserved"
    # Card-int encoding matches _preflop_holes_from_range (every entry is a
    # 2-element list of ints in card_to_int's [8, 59] range).
    assert all(
        len(h) == 2 and all(isinstance(c, int) and 8 <= c <= 59 for c in h)
        for h in hero_out
    )
    # No duplicate combos in the full enumeration.
    assert len({tuple(h) for h in hero_out}) == 1326

    # Symmetric: Hero restricted, Villain full.
    hero = [[8, 9], [8, 10], [8, 11]]  # 3 explicit combos
    hero_out2, villain_out2 = app._coerce_preflop_holes_both_or_neither(hero, None)
    assert hero_out2 == hero
    assert villain_out2 is not None and len(villain_out2) == 1326


def test_coerce_holes_both_restricted_unchanged() -> None:
    """Both restricted -> both explicit subsets, passed through verbatim."""
    from ui import app

    hero = [[8, 9]]
    villain = [[10, 11], [12, 13]]
    assert app._coerce_preflop_holes_both_or_neither(hero, villain) == (hero, villain)


async def test_on_solve_one_sided_threads_both_holes(
    user: User,
    isolated_state_dir: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end through ``_on_preflop_chart_solve``: full Hero + restricted
    Villain(AA) must thread hero_holes=1326 (NOT None) and villain_holes=2 into
    ``start_preflop_chart`` — the exact shape the engine requires."""
    from ui.state import RangeWithFreqs, SolveRunner, get_state

    captured: dict[str, Any] = {"kwargs": None}

    def _fake_start(self: Any, config: Any, **kwargs: Any) -> None:
        captured["kwargs"] = kwargs

    monkeypatch.setattr(SolveRunner, "start_preflop_chart", _fake_start)
    # The full Hero side stays None pre-coercion, so the blueprint bypass check
    # depends only on the restricted Villain side. Force a blueprint miss so we
    # always reach the live dispatch where the holes are threaded.
    monkeypatch.setattr(
        SolveRunner, "try_blueprint_preflop_chart", lambda self, **kw: False
    )

    await user.open("/")

    state = get_state()
    # Hero full, Villain = AA only (2 ... actually 6 combos). This is the
    # user's reported case: villain restricted, hero left full.
    state.current_spot.ranges = (
        RangeWithFreqs.full(),
        RangeWithFreqs.from_string("AhAc, AdAc"),
    )

    from ui.app import _on_preflop_chart_solve

    with user.client:
        _on_preflop_chart_solve(state)

    kwargs = captured["kwargs"]
    assert kwargs is not None, "start_preflop_chart was not called"
    assert kwargs["hero_holes"] is not None, "full hero side must be coerced, not None"
    assert len(kwargs["hero_holes"]) == 1326
    assert kwargs["villain_holes"] is not None
    # AhAc, AdAc = 2 explicit combos.
    assert len(kwargs["villain_holes"]) == 2


def test_real_engine_one_sided_no_value_error() -> None:
    """REAL ENGINE: reproduce the user's path. A full Hero + restricted Villain
    range, after both-or-neither coercion, must call
    ``_rust.solve_hunl_preflop_rvr`` WITHOUT raising the
    'p0_holes and p1_holes must both be supplied or both omitted' ValueError.

    This is the empirical proof against the real binding (the original bug
    raised at ui/state.py:_run_preflop_chart_path). Runs at low iters
    (preflop @30 is fast/light).
    """
    import poker_solver._rust as _rust
    from poker_solver.hunl import HUNLConfig, Street, _serialize_hunl_config
    from ui.app import _coerce_preflop_holes_both_or_neither, _preflop_holes_from_range
    from ui.state import RangeWithFreqs

    # Full Hero -> None; restricted Villain(AA) -> explicit holes.
    hero_holes = _preflop_holes_from_range(RangeWithFreqs.full())
    villain_holes = _preflop_holes_from_range(RangeWithFreqs.from_string("AhAc, AdAc"))
    assert hero_holes is None, "full hero must convert to None pre-coercion"
    assert villain_holes is not None and len(villain_holes) == 2

    # The fix: coerce to the legal both-supplied shape.
    hero_holes, villain_holes = _coerce_preflop_holes_both_or_neither(
        hero_holes, villain_holes
    )
    assert hero_holes is not None and villain_holes is not None

    # Build the same preflop config the live worker builds (100BB toy).
    bb_cents = 100
    config = HUNLConfig(
        starting_stack=100 * bb_cents,
        small_blind=max(1, bb_cents // 2),
        big_blind=bb_cents,
        ante=0,
        starting_street=Street.PREFLOP,
        initial_board=(),
        initial_pot=0,
        initial_contributions=(0, 0),
        initial_hole_cards=(),
        abstraction=None,
    )
    config_json = _serialize_hunl_config(config)

    repo_root = pathlib.Path(__file__).resolve().parents[1]
    equity_path = repo_root / "assets" / "preflop_equity_169x169.npz"
    assert equity_path.exists(), f"equity table missing at {equity_path}"

    # The exact call that raised at ui/state.py:1540 — now with coerced holes.
    rust_out = _rust.solve_hunl_preflop_rvr(
        config_json,
        str(equity_path),
        30,  # iterations — low/fast
        1.5,  # alpha
        0.0,  # beta
        2.0,  # gamma
        None,  # open_sizes_bb
        None,  # reraise_multipliers
        hero_holes,
        villain_holes,
    )
    # The bug was a ValueError before reaching here; a returned result proves
    # the one-sided case is accepted by the real binding.
    assert rust_out is not None


# ---------------------------------------------------------------------------
# Fix 1a: a full / effectively-full range routes to the (instant) blueprint,
# never the catastrophically slow 1326-combo live kernel.
# ---------------------------------------------------------------------------


def test_effectively_full_range_routes_to_blueprint() -> None:
    """A near-full range (full minus a few combos) is NOT a restriction: it
    converts to None (blueprint route), not an explicit-hole live solve."""
    from ui import app
    from ui.state import RangeWithFreqs, _full_range_combos

    # Exactly full -> None (blueprint), as before.
    assert app._preflop_holes_from_range(RangeWithFreqs.full()) is None

    # Full minus 5 combos (1321) is still "effectively full" -> blueprint.
    near_full = RangeWithFreqs.full()
    for combo in _full_range_combos()[:5]:
        near_full.set_frequency(combo, 0.0)
    present = sum(
        1
        for c in near_full.base_range
        if near_full.frequency_of(c.cards) > 0.0
    )
    assert present == 1326 - 5, f"expected 1321 combos, got {present}"
    assert app._range_is_effectively_full(near_full) is True
    assert app._preflop_holes_from_range(near_full) is None, (
        "a near-full range must route to the blueprint, not a 1326-combo live "
        "solve"
    )

    # A genuine restriction (well below the threshold) is still live.
    real_subset = RangeWithFreqs.from_string("AA, KK, AKs")
    assert app._range_is_effectively_full(real_subset) is False
    assert app._preflop_holes_from_range(real_subset) is not None


def test_effectively_full_predictor_and_restricted_agree() -> None:
    """The route predictor (iter greying) and engine dispatch share one
    source of truth: a near-full range predicts a blueprint route."""
    from types import SimpleNamespace

    from ui.state import RangeWithFreqs, Spot, _full_range_combos
    from ui.views import preflop_chart

    spot = Spot()
    near_full = RangeWithFreqs.full()
    for combo in _full_range_combos()[:5]:
        near_full.set_frequency(combo, 0.0)
    spot.ranges = (near_full, RangeWithFreqs.full())
    runner = SimpleNamespace(
        _pending_preflop_chart_opens=None,
        _pending_preflop_chart_mults=None,
    )
    state = SimpleNamespace(current_spot=spot, runner=runner)
    # _range_is_restricted (predictor) must agree with the engine-side decision.
    assert preflop_chart._range_is_restricted(near_full) is False
    assert preflop_chart._next_solve_hits_blueprint(state) is True


async def test_full_range_default_spot_hits_blueprint_no_live(
    user: User,
    isolated_state_dir: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default full-range / default-sizes spot must serve from the
    blueprint and NEVER dispatch a (slow) live solve."""
    from ui.state import SolveRunner, get_state

    live_calls: dict[str, int] = {"count": 0}

    def _fake_start(self: Any, *a: Any, **k: Any) -> None:
        live_calls["count"] += 1

    monkeypatch.setattr(SolveRunner, "start_preflop_chart", _fake_start)

    await user.open("/")
    state = get_state()
    # Default spot: full ranges, default sizes, 100BB / no-ante.
    from ui.app import _on_preflop_chart_solve

    with user.client:
        _on_preflop_chart_solve(state)

    assert live_calls["count"] == 0, (
        "full-range default-sizes spot must hit the blueprint, not a live solve"
    )
    result = state.runner.preflop_chart_result
    assert result is not None, "blueprint route must populate a chart result"
    assert int(result.get("iterations", -1)) == 0, (
        "blueprint route reports 0 iterations (no live CFR), got "
        f"{result.get('iterations')}"
    )
    info = state.runner.preflop_route_info
    from ui.blueprint_router import SourceLabel

    assert getattr(info, "source", None) in (
        SourceLabel.BLUEPRINT,
        SourceLabel.INTERPOLATED,
    ), f"expected a blueprint route badge, got {info!r}"


# ---------------------------------------------------------------------------
# Fix 1b: a full-range LIVE solve uses the fast 169-class kernel. The mocked
# dispatch test above asserts the call; this proves the REAL engine round-trip
# (backend label + 169-class projection) at low/bounded iters.
# ---------------------------------------------------------------------------


def test_full_range_live_solve_uses_class169_real_engine() -> None:
    """REAL ENGINE: a full-range live solve through the worker projection uses
    ``solve_hunl_preflop_rvr_class169`` (backend label) and yields a 169-class
    chart. Bounded at 50 iters (class169 is ~0.3s for that)."""
    import poker_solver._rust as _rust
    from poker_solver.hunl import HUNLConfig, Street, _serialize_hunl_config
    from ui.state import SolveRunner

    config = HUNLConfig(
        starting_stack=100 * 100,
        small_blind=50,
        big_blind=100,
        ante=0,
        starting_street=Street.PREFLOP,
        initial_board=(),
        initial_pot=0,
        initial_contributions=(0, 0),
        initial_hole_cards=(),
        abstraction=None,
    )
    config_json = _serialize_hunl_config(config)
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    equity_path = repo_root / "assets" / "preflop_equity_169x169.npz"
    assert equity_path.exists()

    out = _rust.solve_hunl_preflop_rvr_class169(
        config_json, str(equity_path), 50, 1.5, 0.0, 2.0, None, None, None, None
    )
    assert out.get("backend") == "rust_preflop_rvr_class169"
    # The worker's class169 projection produces a full 169-class root chart.
    summary = SolveRunner._build_preflop_chart_summary(out, class169=True)
    per_class = summary["per_class"]
    assert len(per_class) == 169, (
        f"class169 projection must yield 169 classes, got {len(per_class)}"
    )
    # AA should mostly raise/open; 72o should mostly fold (sanity, not exact).
    assert "AA" in per_class and "72o" in per_class
    assert per_class["72o"].get("fold", 0.0) > 0.5


def test_class169_key_split_and_projection_unit() -> None:
    """Unit: ``_split_class169_key`` parses ``<class>||p|<history>`` and the
    projection keys cells by the class label directly (no hole aggregation)."""
    from ui.state import SolveRunner, _split_class169_key

    assert _split_class169_key("AA||p|") == ("AA", "||p|")
    assert _split_class169_key("AKs||p|b300") == ("AKs", "||p|b300")
    assert _split_class169_key("72o||p|cb200r600") == ("72o", "||p|cb200r600")
    # Malformed / non-class prefixes are rejected.
    assert _split_class169_key("ZZ||p|") == (None, "")
    assert _split_class169_key("no-separator") == (None, "")

    fake_out = {
        "average_strategy": {
            "AA||p|": [0.0, 0.0, 0.0, 1.0],
            "72o||p|": [1.0, 0.0, 0.0, 0.0],
        },
        "iterations": 10,
        "wallclock_seconds": 0.01,
        "decision_node_count": 2,
        "strategy_entry_count": 2,
    }
    summary = SolveRunner._build_preflop_chart_summary(fake_out, class169=True)
    pc = summary["per_class"]
    assert set(pc) == {"AA", "72o"}
    assert pc["72o"]["fold"] == 1.0
    assert pc["AA"]["open_3"] == 1.0


# ---------------------------------------------------------------------------
# Fix 2: the ante selector sets the spot ante AND keys the blueprint lookup.
# ---------------------------------------------------------------------------


async def test_ante_selector_present_in_panel(
    user: User,
    isolated_state_dir: pathlib.Path,
) -> None:
    """The 'preflop-chart-ante-select' control is rendered in the configure
    panel and starts at the spot's default (None / 0 bb)."""
    from ui.state import get_state

    await user.open("/")
    state = get_state()
    # Marker present (raises AssertionError inside find if absent).
    user.find(marker="preflop-chart-ante-select")
    assert float(state.current_spot.ante) == 0.0  # default None displayed


def test_ante_value_coercion_mapping() -> None:
    """The shipped ``_coerce_ante_bb`` (used by both the select's initial value
    and its change handler) maps each option to its BB value and rejects junk
    to 0.0 — so the selector can only ever set a valid blueprint shard cell."""
    from ui.views import preflop_chart

    assert preflop_chart._ANTE_OPTIONS == {
        0.0: "None (0 bb)",
        0.5: "Half (0.5 bb)",
        1.0: "Full (1.0 bb)",
    }
    assert preflop_chart._coerce_ante_bb(0.0) == 0.0
    assert preflop_chart._coerce_ante_bb(0.5) == 0.5
    assert preflop_chart._coerce_ante_bb(1.0) == 1.0
    # Out-of-set / junk -> 0.0 (None).
    assert preflop_chart._coerce_ante_bb(0.25) == 0.0
    assert preflop_chart._coerce_ante_bb("junk") == 0.0
    assert preflop_chart._coerce_ante_bb(None) == 0.0


async def test_ante_half_keys_blueprint_to_half_shard(
    user: User,
    isolated_state_dir: pathlib.Path,
) -> None:
    """Selecting Half ante routes the blueprint lookup to the anteHalf shard:
    ``try_blueprint_preflop_chart(ante=0.5)`` resolves the half-ante asset."""
    from ui.state import get_state

    await user.open("/")
    state = get_state()
    state.current_spot.ante = 0.5

    # The dispatch path passes float(spot.ante) to the router. Verify the
    # router resolves the HALF-ante shard for (100BB, 0.5).
    from ui.blueprint_router import (
        BlueprintRouter,
        SourceLabel,
        default_asset_dir,
    )

    router = BlueprintRouter.from_asset_dir(default_asset_dir())
    assert router is not None, "blueprint asset bundle must be present"
    assert router.has_exact_shard(100, 0.5), (
        "anteHalf 100BB shard must exist in the bundle"
    )
    info_half = router.lookup_chart(
        stack_bb=100, ante=float(state.current_spot.ante), action_history=""
    )
    assert info_half.source == SourceLabel.BLUEPRINT
    assert "half-ante" in info_half.confidence, (
        f"half-ante route confidence expected, got {info_half.confidence!r}"
    )
    # And the no-ante lookup resolves a DIFFERENT (anteNone) shard.
    info_none = router.lookup_chart(stack_bb=100, ante=0.0, action_history="")
    assert "no-ante" in info_none.confidence
    # The two ante cells must resolve to distinct precomputed charts.
    assert info_half.per_class != info_none.per_class, (
        "anteHalf and anteNone shards must differ"
    )


async def test_ante_selector_end_to_end_blueprint_route(
    user: User,
    isolated_state_dir: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: with Half ante on a full-range default-sizes spot, Solve
    serves the half-ante blueprint (no live solve) and threads ante=0.5 into
    the lookup."""
    from ui.state import SolveRunner, get_state

    seen: dict[str, Any] = {"ante": None, "live": 0}
    real_try = SolveRunner.try_blueprint_preflop_chart

    def _spy_try(self: Any, **kw: Any) -> bool:
        seen["ante"] = kw.get("ante")
        return real_try(self, **kw)

    monkeypatch.setattr(SolveRunner, "try_blueprint_preflop_chart", _spy_try)
    monkeypatch.setattr(
        SolveRunner,
        "start_preflop_chart",
        lambda self, *a, **k: seen.__setitem__("live", seen["live"] + 1),
    )

    await user.open("/")
    state = get_state()
    state.current_spot.ante = 0.5

    from ui.app import _on_preflop_chart_solve

    with user.client:
        _on_preflop_chart_solve(state)

    assert float(seen["ante"]) == 0.5, (
        f"ante=0.5 must be threaded into the blueprint lookup, got {seen['ante']!r}"
    )
    assert seen["live"] == 0, "half-ante full-range spot must hit the blueprint"
    info = state.runner.preflop_route_info
    assert info is not None and "half-ante" in info.confidence


# ===========================================================================
# Off-path greying: classes whose reach at the displayed node is ~0 (they
# folded out earlier on this line) store a meaningless strategy there, so the
# chart marks them "not in range" rather than painting a misleading 99% call.
# ===========================================================================

# A 13x13 grid's worth of canonical class labels (the universe the grid paints).
def _all_169_classes() -> list[str]:
    from ui.views.preflop_chart import hand_class_at

    return [hand_class_at(r, c) for r in range(13) for c in range(13)]


def _synthetic_by_line() -> dict[str, dict[str, dict[str, float]]]:
    """Hand-crafted per-line node map for the 4-bet line ``||p|b200r400r1000``.

    Deterministic (no live solve) so the precise per-class assertions don't
    drift with CFR convergence. Models a 200BB-style tree where the BB acts on
    this line and their only gating decision is the 3-bet node ``||p|b200``:
      * AA / KK / QJo 3-bet (``open_2``) some of the time  -> nonzero reach;
      * every other class flat-calls (``call`` 100%)         -> reach 0.

    The sibling raise tokens ``r400 < r500 < …`` must exist as keys so the
    token->label rank-mapping resolves ``r400`` to the smallest raise label
    (``open_2``). Their bodies are irrelevant to the BB's reach.
    """
    classes = _all_169_classes()
    raisers = {"AA", "KK", "QJo"}

    def node_b200(cls: str) -> dict[str, float]:
        if cls in raisers:
            return {
                "fold": 0.0,
                "call": 0.4,
                "open_2": 0.5,  # the 3-bet (r400) -> nonzero BB reach
                "open_3": 0.1,
                "open_4": 0.0,
                "open_5": 0.0,
                "all_in": 0.0,
            }
        return {
            "fold": 0.0,
            "call": 1.0,  # flat-calls the open -> never reaches the 4-bet node
            "open_2": 0.0,
            "open_3": 0.0,
            "open_4": 0.0,
            "open_5": 0.0,
            "all_in": 0.0,
        }

    root = {
        c: {"fold": 0.0, "call": 0.2, "open_2": 0.5, "open_3": 0.3} for c in classes
    }
    return {
        "||p|": root,
        "||p|b200": {c: node_b200(c) for c in classes},
        # Sibling raise tokens (existence drives the rank->label mapping).
        "||p|b200r400": {c: {"fold": 0.0, "call": 1.0} for c in classes},
        "||p|b200r500": {c: {"fold": 0.0, "call": 1.0} for c in classes},
        "||p|b200r600": {c: {"fold": 0.0, "call": 1.0} for c in classes},
        "||p|b200r700": {c: {"fold": 0.0, "call": 1.0} for c in classes},
        # The 4-bet line we display (its own strategy is what would mislead).
        "||p|b200r400r1000": {
            c: {"fold": 0.0, "call": 0.99, "open_2": 0.01} for c in classes
        },
    }


def _fake_grid_state(
    by_line: dict[str, dict[str, dict[str, float]]], selected_line: str
) -> Any:
    """Build an AppState-shaped fake whose grid renders ``selected_line``.

    Wires the runner accessors the grid + reach walk consume:
      * ``preflop_chart_result`` carries the ``_by_line`` map (reach source);
      * ``available_preflop_lines`` / ``preflop_chart_summary_for_line`` feed
        ``_line_chart_result`` (the displayed-node cell summaries);
      * ``preflop_chart_selected_line`` pins the displayed node.
    """
    from types import SimpleNamespace

    lines = sorted(by_line, key=lambda h: (len(h), h))
    result = {
        "per_class": by_line.get(lines[0], {}),
        "actions": ["fold", "call", "open_2", "open_3", "open_4", "open_5", "all_in"],
        "iterations": 100,
        "wallclock_seconds": 0.5,
        "available_lines": lines,
        "_by_line": by_line,
    }
    runner = SimpleNamespace(
        preflop_chart_result=result,
        preflop_route_info=None,
        status="done",
        _mode="preflop_chart",
        available_preflop_lines=lambda: lines,
        preflop_chart_summary_for_line=lambda ln: dict(by_line.get(ln, {})),
    )
    prefs = SimpleNamespace(
        preflop_chart_selected_line=selected_line,
        preflop_chart_selected_class=None,
    )
    return SimpleNamespace(runner=runner, prefs=prefs)


def test_reach_known_case_offpath_vs_inrange() -> None:
    """At the 4-bet node ``||p|b200r400r1000`` (BB facing a 4-bet), hands that
    flat-called the open carry reach ~0 (off-path) while the genuine 3-bet
    hands carry real reach mass."""
    from ui.views import preflop_chart as pc

    by_line = _synthetic_by_line()
    target = "||p|b200r400r1000"
    classes = _all_169_classes()
    reaches = {h: pc.reach(by_line, h, target) for h in classes}
    # No class should be incomputable here (fully specified tree).
    assert all(v is not None for v in reaches.values())
    total = sum(reaches.values())
    assert total > 0.0

    # Off-path: 82s / 72o flat-called -> reach exactly 0.
    for h in ("82s", "72o"):
        assert reaches[h] == 0.0
        assert (reaches[h] / total) < pc._OFF_PATH_REACH_FRACTION

    # In-range: AA / KK / QJo 3-bet -> reach well above the 0.5% threshold.
    for h in ("AA", "KK", "QJo"):
        assert reaches[h] > 0.0
        assert (reaches[h] / total) >= pc._OFF_PATH_REACH_FRACTION


def test_compute_off_path_marks_deep_line() -> None:
    """``compute_off_path`` flags 82s/72o off-path and the real 3-bet hands
    in-range for the 4-bet line."""
    from ui.views import preflop_chart as pc

    state = _fake_grid_state(_synthetic_by_line(), "||p|b200r400r1000")
    classes = _all_169_classes()
    off = pc.compute_off_path(state, classes, "||p|b200r400r1000")
    assert off["82s"] is True and off["72o"] is True
    assert off["AA"] is False and off["KK"] is False and off["QJo"] is False


def test_compute_off_path_root_uniform_nothing_greyed() -> None:
    """The root open node has uniform reach (1.0 for every class), so NOTHING
    is greyed there."""
    from ui.views import preflop_chart as pc

    state = _fake_grid_state(_synthetic_by_line(), "||p|")
    classes = _all_169_classes()
    off = pc.compute_off_path(state, classes, "||p|")
    assert not any(off.values()), "root node must not grey any class"


def test_compute_off_path_failsafe_missing_prior_node() -> None:
    """FAIL-SAFE: when a prior node along the line is missing from ``_by_line``
    (e.g. a partial live snapshot), reach is incomputable, so NOTHING is greyed
    — the chart renders normally."""
    from ui.views import preflop_chart as pc

    by_line = _synthetic_by_line()
    # Drop the BB's gating node so reach can't be computed for the deep line.
    del by_line["||p|b200"]
    state = _fake_grid_state(by_line, "||p|b200r400r1000")
    classes = _all_169_classes()
    # reach() returns None for the gated classes...
    assert pc.reach(by_line, "AA", "||p|b200r400r1000") is None
    # ...so compute_off_path greys NOTHING.
    off = pc.compute_off_path(state, classes, "||p|b200r400r1000")
    assert not any(off.values()), "missing prior node must disable greying"


def test_compute_off_path_failsafe_no_by_line() -> None:
    """FAIL-SAFE: a result with no ``_by_line`` map at all -> nothing greyed."""
    from types import SimpleNamespace

    from ui.views import preflop_chart as pc

    runner = SimpleNamespace(
        preflop_chart_result={"per_class": {"AA": {"call": 1.0}}},
        available_preflop_lines=lambda: ["||p|"],
        preflop_chart_summary_for_line=lambda ln: {"AA": {"call": 1.0}},
    )
    state = SimpleNamespace(
        runner=runner,
        prefs=SimpleNamespace(preflop_chart_selected_line="||p|"),
    )
    off = pc.compute_off_path(state, ["AA", "72o"], "||p|")
    assert off == {"AA": False, "72o": False}


def test_cell_tag_and_tooltip_off_path() -> None:
    """An off-path cell shows the em-dash tag (not F/C/R/J) and a 'not in
    range here' tooltip, regardless of the stored (meaningless) strategy."""
    from ui.views import preflop_chart as pc

    # Stored strategy says 'call 99%' — but the cell is off-path.
    summary = pc.aggregate_actions({"call": 0.99, "fold": 0.01})
    summary.label = "82s"
    assert pc._cell_tag(summary, off_path=True) == "—"
    # In-range path still renders the real tag.
    assert pc._cell_tag(summary, off_path=False).startswith("C")

    tip = pc._tooltip_text("82s", summary, off_path=True)
    assert "82s" in tip and "not in range here" in tip
    assert "call" not in tip.lower(), "off-path tooltip must not imply a real action"


async def test_grid_renders_off_path_cells_for_deep_line(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """End-to-end render: the deep 4-bet line marks 82s/72o cells off-path
    (``preflop-chart-cell-offpath`` marker + em-dash tag) while real 3-bet
    hands render a normal action tag."""
    from ui.state import get_state
    from ui.views import preflop_chart as pc

    await user.open("/")
    state = get_state()
    by_line = _synthetic_by_line()
    lines = sorted(by_line, key=lambda h: (len(h), h))
    state.runner.preflop_chart_result = {
        "per_class": by_line[lines[0]],
        "actions": ["fold", "call", "open_2", "open_3", "open_4", "open_5", "all_in"],
        "iterations": 100,
        "wallclock_seconds": 0.5,
        "available_lines": lines,
        "_by_line": by_line,
    }
    state.runner._mode = "preflop_chart"
    state.runner.status = "done"
    state.prefs.preflop_chart_selected_line = "||p|b200r400r1000"

    # Direct render-fn check: which classes does the grid mark off-path?
    off = pc.compute_off_path(state, _all_169_classes(), "||p|b200r400r1000")
    assert off["82s"] and off["72o"]
    assert not off["AA"] and not off["QJo"]

    await user.open("/")
    # The off-path cells carry the dedicated marker.
    offpath_cells = user.find(marker="preflop-chart-cell-offpath").elements
    assert len(offpath_cells) >= 1, "expected at least one off-path cell marker"
    # 82s / 72o cells exist (the per-class markers are always emitted).
    assert user.find(marker="preflop-chart-cell-82s").elements
    assert user.find(marker="preflop-chart-cell-72o").elements


def test_reach_real_engine_82s_72o_off_path_at_4bet() -> None:
    """REAL ENGINE: hands that fold/flat pre-3bet (82s, 72o) carry reach ~0 at
    the 4-bet node and are off-path.

    This is the convergence-ROBUST invariant: 82s/72o essentially never 3-bet,
    so their reach to a 4-bet node is orders of magnitude below the threshold
    regardless of iteration count (verified at 120 AND 400 iters). We do NOT
    assert on which premium hands are 'in range' there — that flips with CFR
    convergence at 200BB (memory: under-convergence makes deep-node strategies
    degenerate) — only that the never-3-bet hands are excluded.

    Uses the fast class169 kernel (~1.3s at 120 iters, 200BB).
    """
    import poker_solver._rust as _rust
    from poker_solver.hunl import HUNLConfig, Street, _serialize_hunl_config
    from ui.state import SolveRunner
    from ui.views import preflop_chart as pc

    config = HUNLConfig(
        starting_stack=200 * 100,
        small_blind=50,
        big_blind=100,
        ante=0,
        starting_street=Street.PREFLOP,
        initial_board=(),
        initial_pot=0,
        initial_contributions=(0, 0),
        initial_hole_cards=(),
        abstraction=None,
    )
    config_json = _serialize_hunl_config(config)
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    equity_path = repo_root / "assets" / "preflop_equity_169x169.npz"
    assert equity_path.exists()

    out = _rust.solve_hunl_preflop_rvr_class169(
        config_json, str(equity_path), 120, 1.5, 0.0, 2.0, None, None, None, None
    )
    by_line = SolveRunner._project_preflop_by_line(out, class169=True)
    target = "||p|b200r400r1000"
    assert target in by_line, "expected the 4-bet line to be reachable at 200BB"

    classes = _all_169_classes()
    reaches = {h: pc.reach(by_line, h, target) for h in classes}
    assert all(v is not None for v in reaches.values()), (
        "reach must be fully computable for a complete live solve"
    )
    total = sum(reaches.values())
    assert total > 0.0

    for h in ("82s", "72o"):
        norm = reaches[h] / total
        assert norm < pc._OFF_PATH_REACH_FRACTION, (
            f"{h} should be off-path at the 4-bet node; reach_norm={norm:.6f}"
        )

    # Sanity: SOME class must carry real reach (the line is genuinely reached).
    assert any(
        (reaches[h] / total) >= pc._OFF_PATH_REACH_FRACTION for h in classes
    ), "at least one class must be in-range at a reachable node"
