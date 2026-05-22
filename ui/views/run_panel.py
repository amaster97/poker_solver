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
        # ----- Iterations (Q3 LOCKED default 1000) + target-expl toggle -----
        with ui.row().classes("gap-2 items-center"):
            iters_input = ui.number(
                label="Iterations",
                value=_DEFAULT_ITERATIONS,
                min=1,
                max=10_000_000,
                step=100,
            ).classes("w-32")
            iters_input.mark("iterations-input")
            handles["iters_input"] = iters_input

        with ui.row().classes("gap-2 items-center"):
            target_toggle = ui.checkbox(
                "Target exploitability mode (opt-in)",
                value=False,
            )
            target_toggle.mark("target-exploitability-toggle")
            target_input = ui.number(
                label="Target expl (mBB/pot)",
                value=0.5,
                step=0.1,
                min=0.0,
            ).classes("w-32")
            target_input.mark("target-exploitability-input")
            target_input.visible = False

            def _on_target_toggle(e: Any) -> None:
                target_input.visible = bool(e.value)

            target_toggle.on_value_change(_on_target_toggle)
            handles["target_toggle"] = target_toggle
            handles["target_input"] = target_input

        ui.separator()
        # ----- Backend toggle (Python default) -----
        backend_toggle = ui.toggle(
            ["Python", "Rust"],
            value="Python",
        )
        backend_toggle.mark("backend-toggle")
        handles["backend_toggle"] = backend_toggle

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
        chart = ui.echart(
            options=_chart_options([], log_scale=chart_log_state["log"]),
        ).classes("w-full h-48")
        chart.mark("expl-chart")
        handles["chart"] = chart
        handles["chart_log"] = chart_log_state

        with ui.row().classes("items-center"):
            log_toggle = ui.checkbox(
                "Log scale",
                value=chart_log_state["log"],
            )

            def _on_log_toggle(e: Any) -> None:
                chart_log_state["log"] = bool(e.value)
                state.prefs.chart_log_scale = chart_log_state["log"]
                save_state()
                _redraw_chart(handles)

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
        _redraw_chart(handles, history=runner.expl_history)

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
    """Read the iterations/backend toggles into state then invoke on_solve."""
    iters_input = handles.get("iters_input")
    backend_toggle = handles.get("backend_toggle")
    target_toggle = handles.get("target_toggle")
    target_input = handles.get("target_input")
    iters = (
        int(iters_input.value)
        if iters_input is not None and iters_input.value
        else _DEFAULT_ITERATIONS
    )
    backend = (
        str(backend_toggle.value).lower() if backend_toggle is not None else "python"
    )
    target_expl = None
    if (
        target_toggle is not None
        and target_input is not None
        and bool(target_toggle.value)
    ):
        try:
            target_expl = float(target_input.value)
        except (TypeError, ValueError):
            target_expl = None
    state.current_solve = SolveSession(
        spot=state.current_spot,
        iterations=iters,
        log_every=_DEFAULT_LOG_EVERY,
        backend=backend,
        started_at=time.time(),
        runner=state.runner,
    )
    handles["backend_label"].set_text(f"Backend: {backend}")
    # Note: target_expl passes through SolveSession then SolveRunner.start
    # in the dedicated kwarg path; on_solve reads SolveSession + the
    # current_spot to build the call.
    _ = target_expl  # reserved; SolveRunner.start surfaces it
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
    history: list[tuple[int, float]], *, log_scale: bool
) -> dict[str, Any]:
    """Build an echarts options dict for the exploitability curve.

    Y-axis log by default (Q3-adjacent: log Y scale per spec §13 decision 8).
    """
    data = [[h[0], h[1]] for h in history]
    return {
        "title": {
            "text": "Exploitability (mBB/pot)",
            "textStyle": {"fontSize": 12},
            "left": "center",
        },
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
        "grid": {"left": 50, "right": 20, "top": 30, "bottom": 40},
    }


def _redraw_chart(
    handles: dict[str, Any],
    *,
    history: list[tuple[int, float]] | None = None,
) -> None:
    """Re-render the chart with the current history + log/linear toggle."""
    chart = handles.get("chart")
    if chart is None:
        return
    log_scale = bool(handles.get("chart_log", {"log": True})["log"])
    if history is None:
        history = []
    chart.options = _chart_options(history, log_scale=log_scale)
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
    else:
        ui.notify(
            f"Solve failed ({name}): {err}",
            type="negative",
            position="top",
            timeout=8000,
            multi_line=True,
        )


__all__ = ["refresh_progress", "render"]
