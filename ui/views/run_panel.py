"""Run panel (PR 10a, Agent A).

Implements ``pr10a_spec.md`` §4.3 mockup:

- Bet-size checkboxes (33% / 75% / 100% / 150% / 200% / all-in). **Q4
  LOCKED defaults: 33 / 75 / 100 / all-in CHECKED; 150 / 200 unchecked.**
- Raise cap inputs (preflop 4, postflop 3).
- Iterations input. **Q3 LOCKED default: 1000** (NOT 2000).
- Target-exploitability toggle (opt-in; when active, iterations field
  becomes the max-iterations cap and a "target expl mBB/pot" field
  appears).
- Backend toggle (Python / Rust; default Python per spec §13 decision 6).
- Solve / Pause / Stop buttons.
- Live exploitability chart (``ui.echart``, log Y-axis by default per
  spec §13 decision 8). Linear toggle exists.
- Progress readouts (iteration N/M, wall-clock, current expl, backend,
  status).

A ``ui.timer(0.5, ...)`` registered in ``ui/app.py`` drives
``refresh_progress(state)`` per tick — see that module for the timer.
This file declares the chart + readout placeholders + ``refresh_progress``
the timer calls.

ElementFilter markers (Agent C asserts on these):
  ``run-panel``, ``bet-size-checkbox-{pct}``, ``custom-bet-size-input``,
  ``iterations-input``, ``backend-toggle``, ``solve-button``, ``pause-button``,
  ``stop-button``, ``expl-chart``, ``progress-iteration``, ``progress-status``,
  ``target-exploitability-toggle``, ``target-exploitability-input``.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from ui.state import AppState, SolveSession, save_state

logger = logging.getLogger(__name__)


# Module-level handle map for refresh_progress. Maps state id -> dict of
# NiceGUI element handles. We can't store NiceGUI objects on AppState
# because they may live across page refreshes; this scoping is OK because
# AppState is a singleton.
_handles: dict[int, dict[str, Any]] = {}


# Bet sizes the UI exposes (Q4 LOCKED).
_BET_SIZES: tuple[float, ...] = (0.33, 0.75, 1.00, 1.50, 2.00)
_BET_SIZE_LABELS: tuple[str, ...] = ("33%", "75%", "100%", "150%", "200%")
_DEFAULT_CHECKED_BET_SIZES: tuple[float, ...] = (0.33, 0.75, 1.00)
# Q3 LOCKED default iterations.
_DEFAULT_ITERATIONS: int = 1000
# log_every cadence: chart points per 1000 iters (~20 snapshots feels live).
_DEFAULT_LOG_EVERY: int = 50

# PR 24a/PR 24b exploitability-tier slider defaults. Each tier maps to
# a recommended (iteration_count, target_mBB_per_pot) pair.
#
# Iteration counts are the **measured** convergence ladder per
# ``docs/v1_5_slider_tier_defaults_measured.md`` §1 (PR 24b §5 swap):
# - Draft = 200 iters (median 0.0036% pot reached on 15 measured fixtures)
# - Standard = 500 iters (median 0.0002% pot)
# - Tight = 1000 iters (median 0.00004% pot)
# - Library = 2000 iters (median 0.000004% pot)
#
# The DCFR + PR 8 SIMD perf stack converges 100x+ faster than the
# PLAN.md §1 industry-standard % pot targets imply on every measured
# fixture (15 spots: 12 river + 3 turn anchors). The iteration ladder
# is the operative wall-clock differentiator; the mBB/pot label is
# preserved as the user-facing nominal target per PLAN.md §1
# (measurement doc §8 Option A — under-promise / over-deliver, kept
# stable for v1.5).
#
# Per the no-extrapolate rule: the per-tier values are taken VERBATIM
# from the measurement doc §1 — no interpolation or smoothing.
_TIER_DEFAULTS: tuple[tuple[str, int, float], ...] = (
    # (label, iterations, target_mBB_per_pot)
    ("Draft", 200, 10.0),  # 1% pot
    ("Standard", 500, 5.0),  # 0.5% pot
    ("Tight", 1000, 2.5),  # 0.25% pot
    ("Library", 2000, 1.0),  # 0.1% pot
)
_TIER_LABELS: tuple[str, ...] = tuple(t[0] for t in _TIER_DEFAULTS)
_TIER_INDEX: dict[str, tuple[int, float]] = {
    label: (iters, target_mBB) for label, iters, target_mBB in _TIER_DEFAULTS
}
_DEFAULT_TIER: str = "Standard"


def render(
    state: AppState,
    on_solve: Callable[[], None],
    on_pause: Callable[[], None],
    on_stop: Callable[[], None],
) -> None:
    """Render the run panel into the current NiceGUI slot.

    Caller wraps this in a ``ui.expansion`` panel (per ``ui/app.py``).
    """
    from nicegui import ui

    handles: dict[str, Any] = {}
    _handles[id(state)] = handles

    with ui.card().classes("w-full").mark("run-panel"):
        # ----- Bet sizes (Q4 LOCKED) -----
        ui.label("Bet sizes (% pot)").classes("font-medium")
        with ui.row().classes("gap-2"):
            for size, label in zip(_BET_SIZES, _BET_SIZE_LABELS):
                checked = size in state.current_spot.bet_sizes_checked

                def _toggle_size(
                    e: Any,
                    s: float = size,
                ) -> None:
                    _on_bet_size_toggle(state, s, bool(e.value))

                cb = ui.checkbox(label, value=checked, on_change=_toggle_size)
                cb.mark(f"bet-size-checkbox-{int(size * 100)}")
        # All-in checkbox.
        ai_checked = state.current_spot.include_all_in

        def _toggle_all_in(e: Any) -> None:
            state.current_spot.include_all_in = bool(e.value)
            save_state()

        ui.checkbox(
            "all-in",
            value=ai_checked,
            on_change=_toggle_all_in,
        ).mark("bet-size-checkbox-allin")

        # Custom bet size input.
        with ui.row().classes("gap-2 items-center"):
            ui.label("Custom:").classes("text-xs")
            custom = ui.input(
                placeholder="0.5, 1.2 (pot fractions, comma-separated)",
            ).classes("w-64 text-xs")
            custom.mark("custom-bet-size-input")

            def _on_custom_change(e: Any) -> None:
                _apply_custom_bet_sizes(state, str(e.value))

            custom.on_value_change(_on_custom_change)

        ui.separator()
        # ----- Raise caps -----
        with ui.row().classes("gap-2 items-center"):
            ui.label("Raise caps:").classes("text-xs font-medium")
            ui.number(
                label="Preflop",
                value=state.current_spot.preflop_raise_cap,
                min=1,
                max=10,
                step=1,
                on_change=lambda e: _set_cap(state, "preflop", int(e.value or 4)),
            ).classes("w-20")
            ui.number(
                label="Postflop",
                value=state.current_spot.postflop_raise_cap,
                min=1,
                max=10,
                step=1,
                on_change=lambda e: _set_cap(state, "postflop", int(e.value or 3)),
            ).classes("w-20")

        ui.separator()
        # ----- Exploitability tier slider (PR 24a §3.7) -----
        # Replaces the single ``target-exploitability-input`` widget with a
        # 4-tier picker plus a read-only target label. The numeric iter
        # ladder (200/500/1000/2000) comes from the measurement pass at
        # ``docs/v1_5_slider_tier_defaults_measured.md``; the % pot label
        # is the PLAN.md §1 industry-standard nominal target. Both are
        # honest framings (measurement doc §8 Option A).
        ui.label("Exploitability tier").classes("font-medium")
        with ui.row().classes("gap-2 items-center"):
            tier_slider = ui.toggle(
                list(_TIER_LABELS),
                value=_DEFAULT_TIER,
            )
            tier_slider.mark("tier-slider")
            ui.tooltip(
                "Measured against the 12 PR 10a preset fixtures plus 3 "
                "turn-anchor subgames (see "
                "docs/v1_5_slider_tier_defaults_measured.md). Each tier "
                "sets both an iteration ceiling and a target "
                "exploitability (mBB/pot). Empirically each tier "
                "converges to well below its mBB/pot label on every "
                "measured spot; wall-clock is the operative differentiator."
            )
            handles["tier_slider"] = tier_slider

        # Read-only label that reflects the active tier's iter/target pair.
        # Updated in ``_on_tier_change`` and read by ``_wrap_solve``.
        default_iters, default_mBB = _TIER_INDEX[_DEFAULT_TIER]
        tier_target_label = ui.label(
            _format_tier_label(_DEFAULT_TIER, default_iters, default_mBB)
        ).classes("text-xs font-mono text-gray-600 dark:text-gray-400")
        tier_target_label.mark("tier-target-label")
        handles["tier_target_label"] = tier_target_label

        # ----- Iterations override (custom; advanced users) -----
        # Behind an expansion. Default value tracks the active tier; if
        # the user overrides it explicitly, that overrides the tier's
        # iteration count at solve time.
        with (
            ui.expansion("Custom (advanced)", icon="tune", value=False)
            .classes("w-full")
            .mark("custom-tier-expansion"),
            ui.row().classes("gap-2 items-center"),
        ):
            iters_input = ui.number(
                label="Iterations",
                value=default_iters,
                min=1,
                max=10_000_000,
                step=100,
            ).classes("w-32")
            iters_input.mark("iterations-input")
            handles["iters_input"] = iters_input

            target_input = ui.number(
                label="Target expl (mBB/pot)",
                value=default_mBB,
                step=0.1,
                min=0.0,
            ).classes("w-32")
            target_input.mark("target-exploitability-input")
            handles["target_input"] = target_input

        # Wire tier slider to refresh the read-only label + custom defaults.
        def _on_tier_change(e: Any) -> None:
            tier = str(e.value) if e.value else _DEFAULT_TIER
            iters, target_mBB = _TIER_INDEX.get(tier, _TIER_INDEX[_DEFAULT_TIER])
            tier_target_label.set_text(_format_tier_label(tier, iters, target_mBB))
            # Push the tier-recommended values into the custom inputs so a
            # solve click without expanding "Custom" uses them.
            iters_input.set_value(iters)
            target_input.set_value(target_mBB)

        tier_slider.on_value_change(_on_tier_change)

        ui.separator()
        # ----- Locked strategies expansion (PR 24b §3.5) -----
        # Lists every lock from ``state.current_spot.locked_strategies``
        # with a per-lock unlock button. Empty state shows a helper
        # label pointing at the tree-browser "Lock current node" button.
        locks_expansion = (
            ui.expansion("Locked strategies", icon="lock", value=False)
            .classes("w-full")
            .mark("locks-expansion")
        )
        handles["locks_expansion"] = locks_expansion

        with locks_expansion:
            locks_container = ui.element("div").classes("w-full")
            handles["locks_container"] = locks_container

            def _redraw_locks() -> None:
                _render_lock_list(state, locks_container)

            handles["redraw_locks"] = _redraw_locks
            _redraw_locks()

        ui.separator()
        # ----- Backend toggle (Python default) -----
        backend_toggle = ui.toggle(
            ["Python", "Rust"],
            value="Python",
        )
        backend_toggle.mark("backend-toggle")
        handles["backend_toggle"] = backend_toggle

        # ----- Solve-mode toggle (RvR vs Concrete) (PR 24a §3.2) -----
        # Routes through ``poker_solver.solve_range_vs_range`` when set to
        # ``Range-vs-range``. The Pluribus-blueprint aggregator is slower
        # per spot but honestly framed — see chart subtitle for the
        # "blueprint approximation" caveat.
        with ui.row().classes("gap-2 items-center"):
            ui.label("Solve mode:").classes("text-xs")
            rvr_toggle = ui.toggle(
                ["Concrete", "Range-vs-range"],
                value="Concrete",
            )
            rvr_toggle.mark("rvr-mode-toggle")
            ui.tooltip("Slower aggregator pass; honest framing — see Plan C Stage C1.")
            handles["rvr_toggle"] = rvr_toggle

            def _on_rvr_toggle(e: Any) -> None:
                state.current_spot.rvr_mode = str(e.value) == "Range-vs-range"
                save_state()

            rvr_toggle.on_value_change(_on_rvr_toggle)

        ui.separator()
        # ----- Solve / Pause / Stop -----
        with ui.row().classes("gap-2"):
            solve_btn = ui.button(
                "Solve",
                icon="play_arrow",
                on_click=lambda: _wrap_solve(state, handles, on_solve),
            ).props("color=positive")
            solve_btn.mark("solve-button")
            handles["solve_btn"] = solve_btn

            pause_btn = ui.button(
                "Pause",
                icon="pause",
                on_click=on_pause,
            ).props("flat color=warning")
            pause_btn.mark("pause-button")
            pause_btn.disable()
            handles["pause_btn"] = pause_btn

            stop_btn = ui.button(
                "Stop",
                icon="stop",
                on_click=on_stop,
            ).props("flat color=negative")
            stop_btn.mark("stop-button")
            stop_btn.disable()
            handles["stop_btn"] = stop_btn

        ui.separator()
        # ----- Live exploitability chart (log Y by default) -----
        chart_log_state = {"log": state.prefs.chart_log_scale}
        initial_quality_label = _chart_quality_label(state)
        chart = ui.echart(
            options=_chart_options(
                [],
                log_scale=chart_log_state["log"],
                quality_label=initial_quality_label,
            ),
        ).classes("w-full h-48")
        chart.mark("expl-chart")
        handles["chart"] = chart
        handles["chart_log"] = chart_log_state

        with ui.row().classes("items-center"):
            log_toggle = ui.checkbox(
                "Log scale",
                value=chart_log_state["log"],
            )
            # Smoke 17 (X4): conformance marker for the log↔linear toggle.
            log_toggle.mark("expl-chart-linear-toggle")

            def _on_log_toggle(e: Any) -> None:
                chart_log_state["log"] = bool(e.value)
                state.prefs.chart_log_scale = chart_log_state["log"]
                save_state()
                _redraw_chart(handles, state=state)

            log_toggle.on_value_change(_on_log_toggle)

        ui.separator()
        # ----- Progress readouts -----
        with ui.column().classes("gap-1"):
            iter_label = ui.label("Iter: 0").classes("text-xs font-mono")
            iter_label.mark("progress-iteration")
            handles["iter_label"] = iter_label

            wall_label = ui.label("Wall: 0.0 s").classes("text-xs font-mono")
            handles["wall_label"] = wall_label

            expl_label = ui.label("Expl: --").classes("text-xs font-mono")
            handles["expl_label"] = expl_label

            backend_label = ui.label("Backend: python").classes("text-xs font-mono")
            handles["backend_label"] = backend_label

            status_label = ui.label("Status: idle").classes("text-xs font-mono")
            status_label.mark("progress-status")
            handles["status_label"] = status_label

            eta_label = ui.label("").classes("text-xs font-mono italic text-gray-500")
            # Smoke 20 (X7): conformance marker for the long-solve ETA.
            eta_label.mark("progress-eta")
            handles["eta_label"] = eta_label


def refresh_progress(state: AppState) -> None:
    """Called by the ``ui.timer(0.5, ...)`` tick.

    Reads ``state.runner.iteration``, ``state.runner.status``,
    ``state.runner.expl_history``; updates the chart + readouts; sets
    the solve/pause/stop button enabled-states. Per-tick fast path:
    if status is "idle" we only refresh the disabled-state.
    """
    handles = _handles.get(id(state))
    if handles is None:
        return  # render() never called

    runner = state.runner
    status = runner.status

    # Update button enabled states.
    if status == "running":
        handles["solve_btn"].disable()
        handles["pause_btn"].enable()
        handles["stop_btn"].enable()
    elif status == "paused":
        handles["solve_btn"].disable()
        handles["pause_btn"].enable()  # toggles to resume
        handles["stop_btn"].enable()
    else:
        handles["solve_btn"].enable()
        handles["pause_btn"].disable()
        handles["stop_btn"].disable()

    if status == "idle":
        return  # no readouts to update

    # Readouts.
    handles["iter_label"].set_text(f"Iter: {runner.iteration:,}")
    wall = time.time() - runner.started_at if runner.started_at else 0.0
    handles["wall_label"].set_text(f"Wall: {wall:.1f} s")
    if runner.expl_history:
        last_expl = runner.expl_history[-1][1]
        handles["expl_label"].set_text(f"Expl: {last_expl:.3f} mBB/pot")
    handles["status_label"].set_text(f"Status: {status}")

    # Long-solve ETA (edge case §6.1): after 30 s, extrapolate from decay slope.
    if wall > 30.0 and len(runner.expl_history) >= 3:
        eta_text = _compute_eta(runner.expl_history, wall)
        if wall > 300.0:  # 5 min
            handles["eta_label"].set_text(
                f"\N{HOURGLASS} {eta_text} (large spots may take 30+ min)"
            )
        else:
            handles["eta_label"].set_text(eta_text)
    else:
        handles["eta_label"].set_text("")

    # Chart update.
    if runner.expl_history:
        _redraw_chart(handles, history=runner.expl_history, state=state)

    # Status-error surface: when runner.status == "error", show notify.
    if status == "error" and not handles.get("_error_shown"):
        _show_error(state, handles)
        handles["_error_shown"] = True
    if status != "error":
        handles["_error_shown"] = False


def _wrap_solve(
    state: AppState,
    handles: dict[str, Any],
    on_solve: Callable[[], None],
) -> None:
    """Read the tier slider / backend toggles into state then invoke on_solve.

    PR 24a §3.7: the tier slider is the primary control; the ``Custom
    (advanced)`` expansion's ``iters_input`` + ``target_input`` are
    optional overrides. The tier slider's ``on_value_change`` already
    pushes the tier-recommended values into those inputs, so reading
    ``iters_input.value`` alone correctly captures both the tier default
    and any user override. The same logic applies to ``target_input``.
    """
    iters_input = handles.get("iters_input")
    target_input = handles.get("target_input")
    backend_toggle = handles.get("backend_toggle")
    tier_slider = handles.get("tier_slider")
    # Resolve tier (for downstream logging only — the tier's iter +
    # target values are mirrored to the custom inputs).
    tier = (
        str(tier_slider.value)
        if tier_slider is not None and tier_slider.value
        else _DEFAULT_TIER
    )
    tier_iters, tier_target_mBB = _TIER_INDEX.get(tier, _TIER_INDEX[_DEFAULT_TIER])
    # Iterations: prefer the custom input (which the tier slider has
    # already populated). Falling back to the tier default keeps the
    # solve sane if the user manually cleared the input.
    iters = tier_iters
    if iters_input is not None and iters_input.value:
        try:
            iters = max(1, int(iters_input.value))
        except (TypeError, ValueError):
            iters = tier_iters
    # Target exploitability: same mirroring pattern. Convert mBB/pot to
    # the BB/pot units the engine consumes (target_exploitability is
    # passed to ``solve_hunl_postflop`` which uses BB units; the slider's
    # display unit is mBB/pot per PLAN.md §1).
    target_mBB = tier_target_mBB
    if target_input is not None and target_input.value is not None:
        try:
            target_mBB = float(target_input.value)
        except (TypeError, ValueError):
            target_mBB = tier_target_mBB
    target_expl = target_mBB / 1000.0
    backend = (
        str(backend_toggle.value).lower() if backend_toggle is not None else "python"
    )
    state.current_solve = SolveSession(
        spot=state.current_spot,
        iterations=iters,
        log_every=_DEFAULT_LOG_EVERY,
        backend=backend,
        started_at=time.time(),
        runner=state.runner,
    )
    # Store the target_exploitability on a runner-side attribute so the
    # caller's ``on_solve`` (ui/app.py:_on_solve) can pick it up. We
    # avoid widening SolveSession's dataclass for a single PR 24a-scoped
    # field; instead, the convention is "if state.runner._pending_target
    # is set, use it on the next start". The default-None semantics fall
    # through to existing behaviour.
    state.runner._pending_target_expl = target_expl
    state.runner._pending_tier_label = tier
    handles["backend_label"].set_text(f"Backend: {backend}")
    on_solve()


def _on_bet_size_toggle(state: AppState, size: float, checked: bool) -> None:
    """Toggle a bet size in/out of ``state.current_spot.bet_sizes_checked``."""
    current = list(state.current_spot.bet_sizes_checked)
    if checked and size not in current:
        current.append(size)
    elif not checked and size in current:
        current.remove(size)
    state.current_spot.bet_sizes_checked = tuple(sorted(current))
    save_state()


def _apply_custom_bet_sizes(state: AppState, raw: str) -> None:
    """Parse comma-separated pot fractions; merge into bet_sizes_checked.

    Pio-compatible syntax per spec §5 adopted #5: ``"0.5, 1.2"`` or
    ``"50, 120"``. Values > 5.0 are interpreted as percentages.
    """
    if not raw.strip():
        return
    try:
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        sizes: list[float] = []
        for p in parts:
            v = float(p)
            if v > 5.0:
                v /= 100.0
            if v <= 0.0:
                continue
            sizes.append(v)
    except ValueError:
        return
    merged = sorted(set(state.current_spot.bet_sizes_checked) | set(sizes))
    state.current_spot.bet_sizes_checked = tuple(merged)
    save_state()


def _set_cap(state: AppState, which: str, value: int) -> None:
    """Update preflop or postflop raise cap."""
    value = max(1, value)
    if which == "preflop":
        state.current_spot.preflop_raise_cap = value
    else:
        state.current_spot.postflop_raise_cap = value
    save_state()


def _chart_options(
    history: list[tuple[int, float]],
    *,
    log_scale: bool,
    quality_label: str = "",
) -> dict[str, Any]:
    """Build an echarts options dict for the exploitability curve.

    Y-axis log by default (Q3-adjacent: log Y scale per spec §13 decision 8).

    PR 24a §3.4: ``quality_label`` is rendered as the echarts ``subtext``
    field so the user can distinguish "true Nash" (concrete-vs-concrete +
    Rust BR walk) from "blueprint approximation" (RvR aggregator). The
    mapping is centralized in :func:`_chart_quality_label`.

    Note: ``echarts`` top spacing is widened from 30 to 50 px when a
    subtitle is present so the subtext doesn't overlap the plot area.
    """
    data = [[h[0], h[1]] for h in history]
    title_block: dict[str, Any] = {
        "text": "Exploitability (mBB/pot)",
        "textStyle": {"fontSize": 12},
        "left": "center",
    }
    grid_top = 30
    if quality_label:
        title_block["subtext"] = quality_label
        title_block["subtextStyle"] = {"fontSize": 10, "color": "#888"}
        grid_top = 50
    return {
        "title": title_block,
        "xAxis": {
            "type": "value",
            "name": "iter",
            "nameLocation": "middle",
            "nameGap": 24,
        },
        "yAxis": {
            "type": "log" if log_scale else "value",
            "name": "expl",
            "min": 1e-3 if log_scale else 0,
        },
        "series": [
            {
                "type": "line",
                "data": data,
                "showSymbol": False,
                "smooth": False,
            }
        ],
        "grid": {"left": 50, "right": 20, "top": grid_top, "bottom": 40},
    }


def _chart_quality_label(state: AppState) -> str:
    """Return the chart subtitle for the current solve mode + backend.

    Per PR 24a §3.4:
      * concrete + Rust  -> "true Nash (Rust best-response walk, v1.3.2)"
      * concrete + Python -> "true Nash (Python best-response walk, slow)"
      * RvR (any backend) -> "blueprint approximation (Pluribus-style
                              aggregator, v1.3.0; not Nash)"

    Reads ``state.current_spot.rvr_mode`` and ``state.current_solve.backend``
    (falling back to ``"python"`` when no solve has run yet — the chart
    is rendered at page-open with empty history so this default must be
    safe). The label is recomputed every ``_redraw_chart`` call.
    """
    rvr_mode = bool(getattr(state.current_spot, "rvr_mode", False))
    if rvr_mode:
        return "blueprint approximation (Pluribus-style aggregator, v1.3.0; not Nash)"
    backend = "python"
    solve = state.current_solve
    if solve is not None:
        backend = str(getattr(solve, "backend", "python")).lower()
    if backend == "rust":
        return "true Nash (Rust best-response walk, v1.3.2)"
    return "true Nash (Python best-response walk, slow)"


def _format_tier_label(tier: str, iterations: int, target_mBB: float) -> str:
    """Render the read-only tier-target label.

    Format: ``"Standard: 500 iters / target 5.0 mBB/pot"``. The mBB/pot
    is the nominal PLAN.md §1 target; the iters value is the measured
    convergence ladder per ``docs/v1_5_slider_tier_defaults_measured.md``.
    """
    return f"{tier}: {iterations} iters / target {target_mBB:.1f} mBB/pot"


def _redraw_chart(
    handles: dict[str, Any],
    *,
    history: list[tuple[int, float]] | None = None,
    state: AppState | None = None,
) -> None:
    """Re-render the chart with the current history + log/linear toggle.

    PR 24a §3.4: when ``state`` is supplied, the subtitle is recomputed via
    :func:`_chart_quality_label`. Callers should pass it on every redraw
    so the label flips correctly when ``spot.rvr_mode`` or ``backend``
    changes mid-session.
    """
    chart = handles.get("chart")
    if chart is None:
        return
    log_scale = bool(handles.get("chart_log", {"log": True})["log"])
    if history is None:
        history = []
    quality_label = _chart_quality_label(state) if state is not None else ""
    # NiceGUI 3.x: `EChart.options` is read-only; mutate the underlying dict
    # in place rather than reassigning the property (which raises
    # AttributeError under 3.x). The chart's update_method='update_chart'
    # will pick up the mutation on the next tick.
    new_options = _chart_options(
        history, log_scale=log_scale, quality_label=quality_label
    )
    chart.options.clear()
    chart.options.update(new_options)
    try:
        chart.update()
    except Exception:  # noqa: BLE001
        logger.debug("chart.update raised (NiceGUI 2.x compat)")


def _compute_eta(history: list[tuple[int, float]], wall: float) -> str:
    """Extrapolate ETA from the exploitability decay slope.

    Edge case §6.1: after 30 s, fit a line in log-expl vs iter space; the
    extrapolated iter at target=0.5 mBB/pot gives the remaining iters,
    which multiplied by wall/iter gives the remaining seconds.
    """
    if len(history) < 3:
        return ""
    try:
        import math

        last_iter = history[-1][0]
        last_expl = history[-1][1]
        first_iter = history[0][0]
        first_expl = history[0][1]
        if last_expl <= 0 or first_expl <= 0 or last_iter == first_iter:
            return ""
        # Slope in log-space (per iter).
        slope = (math.log(last_expl) - math.log(first_expl)) / (last_iter - first_iter)
        if slope >= 0:
            return ""  # not converging; can't extrapolate
        target = 0.5
        iters_to_target = (math.log(target) - math.log(last_expl)) / slope
        if iters_to_target <= 0:
            return "ETA: <1 s (target reached)"
        wall_per_iter = wall / last_iter if last_iter else 0.0
        eta_sec = wall_per_iter * iters_to_target
        if eta_sec < 60:
            return f"ETA: ~{int(eta_sec)} s to 0.5 mBB/pot"
        if eta_sec < 3600:
            return f"ETA: ~{int(eta_sec / 60)} min to 0.5 mBB/pot"
        return f"ETA: ~{eta_sec / 3600:.1f} h to 0.5 mBB/pot"
    except (ValueError, ZeroDivisionError):
        return ""


def _render_lock_list(state: AppState, container: Any) -> None:
    """Render the per-lock unlock-button list (PR 24b §3.5).

    Clears ``container``'s children and re-emits one row per lock. Each
    row shows the infoset key + the locked distribution as a compact
    string + an "Unlock" button. Empty state shows a helper label.
    """
    from nicegui import ui

    from ui.views.node_lock_editor import remove_lock

    container.clear()
    locks = state.current_spot.locked_strategies
    with container:
        if not locks:
            ui.label(
                "No locks set. Use 'Lock current node' in the tree browser "
                "to pin a strategy."
            ).classes("text-xs text-gray-500 italic").mark("locks-empty-label")
            return
        for key, dist in list(locks.items()):
            with ui.row().classes("items-center gap-2 w-full"):
                dist_str = " / ".join(f"{p * 100:.0f}%" for p in dist)
                ui.label(key).classes("font-mono text-xs flex-grow truncate")
                ui.label(dist_str).classes("font-mono text-xs text-gray-500")

                def _unlock(_e: Any = None, k: str = key) -> None:
                    if remove_lock(state, k):
                        ui.notify(
                            f"Unlocked {k}",
                            type="info",
                            position="top",
                            timeout=2000,
                        )
                        _render_lock_list(state, container)

                ui.button(
                    icon="lock_open",
                    on_click=_unlock,
                ).props("flat dense color=warning").mark(
                    f"unlock-button-{_lock_key_marker(key)}"
                )


def _lock_key_marker(key: str) -> str:
    """Sanitize an infoset key into an ElementFilter marker suffix.

    Replaces slashes and special chars with hyphens so the marker is
    selector-safe. Loosely a one-way slug; duplicate keys can collide
    on the marker but each lock has a unique key by definition.
    """
    safe = "".join(c if c.isalnum() or c == "-" else "-" for c in key)
    return safe[:48]  # cap length to keep marker readable


def _show_error(state: AppState, handles: dict[str, Any]) -> None:
    """Surface the worker error via ``ui.notify`` per honest-error principle."""
    from nicegui import ui

    err = state.runner.error
    if err is None:
        return
    name = type(err).__name__
    if isinstance(err, MemoryError):
        # Edge §6.5: dark-red status + system-protective framing + concrete
        # remediations + quick-action button.
        msg = (
            "Solve aborted to protect your system (memory budget exceeded). "
            "Remediations: (1) Reduce bet sizes (uncheck 150% / 200%), "
            "(2) Lower iterations, (3) Use a smaller subgame."
        )
        ui.notify(msg, type="negative", position="top", timeout=8000, multi_line=True)

        # Smoke 18 (X5): conformance gate — surface a marked quick-action
        # button so the OOM-remediation surface is exposed to the smoke
        # test. The button is a stub that just unchecks the bigger bet
        # sizes via the spot config; the real remediation surface lives
        # behind `state.current_spot.bet_sizes_checked`.
        def _reduce_bet_sizes(_e: Any = None) -> None:
            spot = state.current_spot
            spot.bet_sizes_checked = tuple(
                bs for bs in spot.bet_sizes_checked if bs <= 1.0
            )
            ui.notify(
                "Bet sizes reduced to <=100% pot; rerun solve.",
                type="info",
                position="top",
                timeout=3000,
            )

        ui.button(
            "Reduce bet sizes",
            on_click=_reduce_bet_sizes,
        ).props("flat dense").mark("oom-reduce-bet-sizes-button")
    elif isinstance(err, NotImplementedError):
        # Edge §6.3: notification with three remediations.
        ui.notify(
            f"Unsupported configuration: {err}. "
            "Try: (1) Set board to 3+ cards, (2) Lower stacks, (3) Use push/fold.",
            type="warning",
            position="top",
            timeout=8000,
            multi_line=True,
        )
    elif isinstance(err, ValueError) and "locked_strategies" in str(err):
        # PR 24b §3.5: push/fold + node-locking guard (solver.py:74-86).
        # Surface the engine ValueError with a "Use tree-builder mode"
        # remediation button that flips force_tree_solve=True and
        # retries on the next solve click.
        ui.notify(
            f"Node-locking is incompatible with the push/fold chart "
            f"short-circuit (≤15 BB HUNL preflop): {err}",
            type="negative",
            position="top",
            timeout=10000,
            multi_line=True,
        )

        def _retry_with_force_tree(_e: Any = None) -> None:
            state.runner._pending_force_tree_solve = True
            ui.notify(
                "force_tree_solve=True set; click Solve again to retry.",
                type="info",
                position="top",
                timeout=5000,
            )

        ui.button(
            "Use tree-builder mode",
            icon="account_tree",
            on_click=_retry_with_force_tree,
        ).props("flat dense").mark("force-tree-solve-button")
    else:
        ui.notify(
            f"Solve failed ({name}): {err}",
            type="negative",
            position="top",
            timeout=8000,
            multi_line=True,
        )


__all__ = ["refresh_progress", "render"]
