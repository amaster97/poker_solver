"""Run panel (PR 10a, Agent A).

Implements ``pr10a_spec.md`` §4.3 mockup:

- Bet-size checkboxes (33% / 75% / 100% / 150% / 200% / all-in). **Q4
  LOCKED defaults: 33 / 75 / 100 / all-in CHECKED; 150 / 200 unchecked.**
- Raise cap inputs (preflop 4, postflop 3).
- Iterations input. **Q3 LOCKED default: 1000** (NOT 2000).
- Target-exploitability toggle (opt-in; when active, iterations field
  becomes the max-iterations cap and a "target expl mBB/pot" field
  appears).
- Solve / Pause / Stop buttons. The engine is always Rust (the
  Python path is a silent test-only fallback inside the dispatch); the
  user never picks a backend.
- A determinate/indeterminate progress bar driven by the
  ``SolveRunner`` progress accessors.
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
  ``iterations-input``, ``solve-button``, ``pause-button``,
  ``stop-button``, ``expl-chart``, ``progress-iteration``, ``progress-status``,
  ``progress-bar``, ``target-exploitability-toggle``,
  ``target-exploitability-input``.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from typing import Any

from ui.state import (
    AppState,
    SolveInFlightError,
    SolveSession,
    save_state,
)

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
_DEFAULT_TIER: str = "Tight"

# Dev-only Concrete/Range-vs-range method toggle gate.
#
# Product decision (2026-05-30): "Concrete" = point-pair (fixes both
# players to one hole-card combo) is a dev/test artifact, NOT a real
# study mode. Production postflop is **Range-vs-range only**, so the
# Concrete/RvR toggle is hidden and ``rvr_mode`` is forced True. The
# toggle stays reachable behind this env var for developer / UI
# debugging (RvR is currently slow on this branch's engine), where it
# defaults to Concrete for fast iteration.
_CONCRETE_DEV_ENV_VAR: str = "POKER_SOLVER_DEV_CONCRETE"


def _concrete_dev_enabled() -> bool:
    """Return True when the dev-only Concrete/RvR method toggle is enabled.

    Reads ``POKER_SOLVER_DEV_CONCRETE`` from the environment at call time
    (page-build time, not import time) so tests can flip it per-case with
    ``monkeypatch.setenv`` / ``delenv``. Any non-empty value enables it.
    """
    return bool(os.environ.get(_CONCRETE_DEV_ENV_VAR, "").strip())


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

        # The flat checkboxes above are the PREFLOP / fallback opening menu
        # (used by any street without its own per-street override below).

        ui.separator()
        # ----- Per-street opening-bet menus (C1) -----
        # Each street can override the flat menu with its OWN opening-bet
        # sizes. Leaving a street with NO sizes checked means it inherits
        # the flat menu (the Spot field stays ``None``). These write
        # ``state.current_spot.{flop,turn,river}_bet_fractions``.
        ui.label("Per-street opening sizes (% pot)").classes("font-medium")
        ui.label(
            "Override the flat menu for a specific street. No boxes checked "
            "= inherit the flat menu above."
        ).classes("text-xs text-gray-600 dark:text-gray-400")
        for street_name in ("flop", "turn", "river"):
            active = _street_fractions(state, street_name)
            with ui.row().classes("gap-2 items-center"):
                ui.label(f"{street_name.capitalize()}:").classes(
                    "text-xs font-medium w-12"
                )
                for size, label in zip(_BET_SIZES, _BET_SIZE_LABELS):
                    checked = active is not None and size in active

                    def _toggle_street(
                        e: Any,
                        s: float = size,
                        st: str = street_name,
                    ) -> None:
                        _on_street_bet_toggle(state, st, s, bool(e.value))

                    scb = ui.checkbox(
                        label, value=checked, on_change=_toggle_street
                    )
                    scb.mark(f"{street_name}-bet-checkbox-{int(size * 100)}")

        ui.separator()
        # ----- Raise size (C2): MULTIPLIERS of the bet faced, NOT % pot -----
        # Writes ``state.current_spot.raise_size_xs``. Default (3.0,) = raise
        # to 3x the bet. Comma-separated for multiple raise sizes.
        with ui.row().classes("gap-2 items-center"):
            ui.label("Raise size (× the bet):").classes("text-xs font-medium")
            raise_input = ui.input(
                value=", ".join(
                    _fmt_x(x) for x in state.current_spot.raise_size_xs
                ),
                placeholder="3.0  (multiplier of the bet, comma-separated)",
            ).classes("w-48 text-xs")
            raise_input.mark("raise-size-input")

            def _on_raise_change(e: Any) -> None:
                _apply_raise_sizes(state, str(e.value))

            raise_input.on_value_change(_on_raise_change)

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
                "Each tier sets both an iteration ceiling and a target "
                "exploitability (mBB/pot). Higher tiers solve more "
                "precisely but take longer; in practice every tier "
                "converges to well below its mBB/pot label, so wall-clock "
                "time is the main trade-off."
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
        # ----- Backend: always Rust (v1.11 UI) -----
        # The Python engine was test-only; the user never chooses it. The
        # backend select control was removed here. The engine defaults to
        # Rust in state.py/solver.py (Python survives only as a silent
        # in-dispatch fallback when the Rust binding is unavailable). We do
        # NOT write ``backend="python"`` anywhere from this panel.

        # ----- Solve-mode toggle (RvR vs Concrete) (PR 24a §3.2) -----
        # Routes through ``poker_solver.range_aggregator.solve_range_vs_range_nash``
        # (true-Nash vector-form CFR, default since 2026-05-27) when set
        # to ``Range-vs-range``. The legacy blueprint path is available
        # via the opt-in checkbox below. See chart subtitle for the
        # method actually used.
        #
        # Product decision (2026-05-30): "Concrete" (point-pair) is a
        # dev/test artifact, not a real study mode. Production postflop is
        # **Range-vs-range only**, so the toggle is hidden in production
        # and ``rvr_mode`` is forced True (no "Concrete"/"point-pair" text
        # reaches the production DOM). The toggle is restored — defaulting
        # to Concrete for fast dev iteration — only when the dev env var
        # ``POKER_SOLVER_DEV_CONCRETE`` is set (see ``_concrete_dev_enabled``).
        if _concrete_dev_enabled():
            # Dev path: show the toggle, default selection = Concrete so
            # debugging is fast (RvR is slow on this branch's engine).
            state.current_spot.rvr_mode = False
            with ui.row().classes("gap-2 items-center"):
                ui.label("Solve mode:").classes("text-xs")
                rvr_toggle = ui.toggle(
                    ["Concrete", "Range-vs-range"],
                    value="Concrete",
                )
                rvr_toggle.mark("rvr-mode-toggle")
                ui.tooltip(
                    "Slower aggregator pass; honest framing — see Plan C Stage C1."
                )
                handles["rvr_toggle"] = rvr_toggle

                def _on_rvr_toggle(e: Any) -> None:
                    state.current_spot.rvr_mode = str(e.value) == "Range-vs-range"
                    save_state()

                rvr_toggle.on_value_change(_on_rvr_toggle)
        else:
            # Production path: no toggle. Postflop is Range-vs-range only;
            # force the effective default so the existing solve dispatch
            # (``Spot.to_rvr_call_args`` / ``solve_range_vs_range_nash``)
            # routes through RvR and never falls into the point-pair path.
            state.current_spot.rvr_mode = True
        save_state()

        # ----- Pluribus-blueprint opt-in checkbox (task #61) -----
        # True-Nash vector-form CFR is the default since 2026-05-27 (per
        # empirical bench: turn ~27× faster, blueprint flop impractical
        # at >27 min CPU on a tiny range). This checkbox opts back into
        # the legacy ``solve_range_vs_range`` Pluribus-blueprint
        # aggregator, which can still be faster on tiny river spots.
        # The label semantics are INVERTED from the pre-flip version:
        # checked => blueprint (legacy), unchecked => true_nash (default).
        with ui.row().classes("gap-2 items-center"):
            blueprint_checkbox = ui.checkbox(
                "Use Pluribus blueprint (legacy, faster on tiny river)",
                value=(
                    getattr(state.current_spot, "solver_mode", "blueprint")
                    == "blueprint"
                ),
            )
            # Marker is kept as ``true-nash-checkbox`` so existing tests
            # and external selectors (PR 10b UI snapshots) keep working.
            # The semantic flip is encoded in the on-change handler.
            blueprint_checkbox.mark("true-nash-checkbox")
            ui.tooltip(
                "Opt into the legacy Pluribus-blueprint aggregator "
                "(``solve_range_vs_range``). Default is true-Nash "
                "vector-form CFR (joint Nash + exploitability number). "
                "Blueprint can be faster on tiny river spots but is "
                "impractical on flop (>27 min CPU). See "
                "docs/aggregator_vs_true_nash_explainer.md."
            )
            handles["true_nash_checkbox"] = blueprint_checkbox

            def _on_blueprint_toggle(e: Any) -> None:
                # Inverted semantics: checking the box selects blueprint,
                # unchecking it returns to the new default (true_nash).
                state.current_spot.solver_mode = (
                    "blueprint" if bool(e.value) else "true_nash"
                )
                save_state()

            blueprint_checkbox.on_value_change(_on_blueprint_toggle)

        ui.separator()
        # ----- Solve / Pause / Stop -----
        # Discoverability (v1.11 UI): the Run Panel lives in a collapsed
        # footer accordion and the Solve button tested hard to find. Make
        # Solve the unmistakable primary action — large, full-width, raised
        # — while Pause/Stop stay compact and secondary. Light touch: only
        # the button emphasis changes, not the panel layout.
        ui.label("Primary action").classes(
            "text-xs font-medium uppercase tracking-wide text-gray-500"
        )
        solve_btn = ui.button(
            "Solve",
            icon="play_arrow",
            on_click=lambda: _wrap_solve(state, handles, on_solve),
        ).props("color=positive size=lg unelevated").classes("w-full font-bold")
        solve_btn.mark("solve-button")
        handles["solve_btn"] = solve_btn

        with ui.row().classes("gap-2 w-full"):
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
        # ----- Progress bar + running indicator (v1.11 UI) -----
        # Driven by ``refresh_progress`` via the 0.5 s poll. Determinate
        # when ``runner.progress_fraction`` is not None; indeterminate
        # "solving…" when ``is_running`` but the fraction is unknown
        # (e.g. target-exploitability run with no iteration cap); hidden
        # otherwise. ETA (mm:ss) appears beside it when derivable.
        with ui.column().classes("w-full gap-1").mark("progress-bar-container") as (
            progress_container
        ):
            progress_bar = ui.linear_progress(
                value=0.0,
                show_value=False,
            ).props("instant-feedback rounded").classes("w-full")
            progress_bar.mark("progress-bar")
            handles["progress_bar"] = progress_bar

            with ui.row().classes("items-center justify-between w-full"):
                progress_caption = ui.label("").classes("text-xs text-gray-600")
                progress_caption.mark("progress-caption")
                handles["progress_caption"] = progress_caption

                progress_eta = ui.label("").classes("text-xs font-mono text-gray-500")
                progress_eta.mark("progress-bar-eta")
                handles["progress_eta"] = progress_eta
        handles["progress_container"] = progress_container
        # Start hidden; ``refresh_progress`` reveals it while a solve runs.
        progress_container.set_visibility(False)

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
        # Clean, readable Iter / Wall / Expl / Status lines. The numeric
        # ETA lives next to the progress bar above; ``eta_label`` is kept
        # (empty) so the ``progress-eta`` conformance marker still resolves.
        with ui.column().classes("gap-1"):
            iter_label = ui.label("Iterations: 0").classes("text-xs font-mono")
            iter_label.mark("progress-iteration")
            handles["iter_label"] = iter_label

            wall_label = ui.label("Elapsed: 0.0 s").classes("text-xs font-mono")
            handles["wall_label"] = wall_label

            expl_label = ui.label("Exploitability: --").classes("text-xs font-mono")
            handles["expl_label"] = expl_label

            status_label = ui.label("Status: idle").classes("text-xs font-mono")
            status_label.mark("progress-status")
            handles["status_label"] = status_label

            eta_label = ui.label("").classes("text-xs font-mono italic text-gray-500")
            # Smoke 20 (X7): conformance marker retained for the long-solve
            # ETA. The live ETA now renders next to the progress bar; this
            # element stays present (empty) so the marker still resolves.
            eta_label.mark("progress-eta")
            handles["eta_label"] = eta_label

            # ----- Task #61: result method + exploitability readouts -----
            # Surface which engine path produced the displayed strategy
            # (concrete / blueprint aggregator / true-Nash vector CFR) and
            # the exploitability number when true-Nash mode is used. The
            # labels stay empty when no solve has run.
            method_label = ui.label("").classes("text-xs font-mono")
            method_label.mark("progress-method")
            handles["method_label"] = method_label

            nash_expl_label = ui.label("").classes("text-xs font-mono")
            nash_expl_label.mark("progress-nash-exploitability")
            handles["nash_expl_label"] = nash_expl_label


def refresh_progress(state: AppState) -> None:
    """Called by the ``ui.timer(0.5, ...)`` tick.

    Reads the ``SolveRunner`` progress accessors (``is_running``,
    ``current_iteration``, ``total_iterations``, ``progress_fraction``,
    ``elapsed_seconds``, ``eta_seconds``) plus ``status`` /
    ``expl_history``; drives the progress bar + readouts + chart and sets
    the solve/pause/stop button enabled-states.

    Progress bar policy (v1.11 UI):
      * ``progress_fraction`` is not None -> DETERMINATE bar at that value.
      * ``is_running`` but ``progress_fraction`` is None -> INDETERMINATE
        "solving…" bar (handles ``total_iterations is None`` with no
        divide-by-zero).
      * otherwise -> bar hidden.

    Per-tick fast path: if status is "idle" we only refresh the
    disabled-state + hide the bar.
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

    # Progress bar (drive on every non-idle tick; hide when idle).
    _update_progress_bar(handles, runner, status)

    if status == "idle":
        return  # no readouts to update

    # Readouts (clean, human-readable labels).
    handles["iter_label"].set_text(f"Iterations: {runner.current_iteration:,}")
    handles["wall_label"].set_text(f"Elapsed: {runner.elapsed_seconds:.1f} s")
    if runner.expl_history:
        last_expl = runner.expl_history[-1][1]
        handles["expl_label"].set_text(f"Exploitability: {last_expl:.3f} mBB/pot")
    handles["status_label"].set_text(f"Status: {_status_text(status)}")

    # Chart update.
    if runner.expl_history:
        _redraw_chart(handles, history=runner.expl_history, state=state)

    # Task #61: method-used + true-Nash exploitability surface.
    # ``nash_result`` is set only by the true-Nash vector-form path; when
    # present, surface the dataclass-reported exploitability + wall-clock.
    # The blueprint aggregator path leaves it None and we fall back to a
    # generic "blueprint aggregator" label; the concrete-vs-concrete path
    # surfaces "concrete (Python|Rust)". Per spec §3.4 (PR 24a) the chart
    # subtitle already names the method qualitatively; these labels are a
    # numeric companion.
    method_label = handles.get("method_label")
    nash_expl_label = handles.get("nash_expl_label")
    if method_label is not None and nash_expl_label is not None:
        nash_result = getattr(runner, "nash_result", None)
        rvr_result = getattr(runner, "rvr_result", None)
        spot = state.current_spot
        rvr_mode_on = bool(getattr(spot, "rvr_mode", False))
        solver_mode = str(getattr(spot, "solver_mode", "blueprint"))
        if status in ("done", "stopped") and nash_result is not None:
            wall_clock = float(getattr(nash_result, "wall_clock_s", 0.0))
            method_label.set_text(
                f"Method: true-Nash vector CFR  (wall {wall_clock:.2f} s)"
            )
            expl_val = float(getattr(nash_result, "exploitability", 0.0))
            nash_expl_label.set_text(
                f"Nash exploitability: {expl_val:.4f} (chips/hand)"
            )
        elif status in ("done", "stopped") and rvr_mode_on and rvr_result is not None:
            method_label.set_text("Method: Pluribus blueprint aggregator (legacy)")
            nash_expl_label.set_text("")
        elif status in ("done", "stopped") and not rvr_mode_on:
            method_label.set_text("Method: concrete")
            nash_expl_label.set_text("")
        elif status == "running":
            # Surface "would use true-Nash" while still solving so the
            # user sees the dispatch intent without waiting for the result.
            if rvr_mode_on and solver_mode == "true_nash":
                method_label.set_text(
                    "Method: true-Nash vector CFR (default; computing...)"
                )
            elif rvr_mode_on:
                method_label.set_text(
                    "Method: Pluribus blueprint aggregator (legacy)"
                )
            else:
                method_label.set_text("")
            nash_expl_label.set_text("")
        else:
            method_label.set_text("")
            nash_expl_label.set_text("")

    # Status-error surface: when runner.status == "error", show notify.
    if status == "error" and not handles.get("_error_shown"):
        _show_error(state, handles)
        handles["_error_shown"] = True
    if status != "error":
        handles["_error_shown"] = False


def _update_progress_bar(handles: dict[str, Any], runner: Any, status: str) -> None:
    """Drive the linear progress bar from the ``SolveRunner`` accessors.

    Policy (v1.11 UI):
      * ``progress_fraction`` is not None -> DETERMINATE bar at that value.
      * ``is_running`` and ``progress_fraction`` is None -> INDETERMINATE
        "solving…" bar (``total_iterations is None`` lands here; no
        divide-by-zero — ``progress_fraction`` returns None in that case).
      * otherwise (idle, or terminal with nothing to show) -> hidden.

    ETA (mm:ss) is shown beside the bar when ``runner.eta_seconds`` is
    available; the caption names the current phase.
    """
    container = handles.get("progress_container")
    bar = handles.get("progress_bar")
    caption = handles.get("progress_caption")
    eta_label = handles.get("progress_eta")
    if container is None or bar is None:
        return

    fraction = runner.progress_fraction  # float in [0,1] or None
    running = bool(runner.is_running)

    if fraction is not None:
        # DETERMINATE.
        container.set_visibility(True)
        bar.props(remove="indeterminate")
        bar.set_value(max(0.0, min(1.0, float(fraction))))
        if caption is not None:
            if status in ("done", "stopped"):
                caption.set_text("Complete")
            else:
                total = runner.total_iterations
                done = runner.current_iteration
                pct = int(round(fraction * 100))
                if total:
                    caption.set_text(f"Solving… {done:,}/{total:,} iters ({pct}%)")
                else:
                    caption.set_text(f"Solving… {pct}%")
    elif running:
        # INDETERMINATE — running but no known target (e.g. target-expl
        # early-exit with no iteration cap, or total_iterations is None).
        container.set_visibility(True)
        bar.props(add="indeterminate")
        bar.set_value(0.0)
        if caption is not None:
            caption.set_text("Solving…")
    else:
        # Idle / nothing to show.
        container.set_visibility(False)
        bar.props(remove="indeterminate")
        bar.set_value(0.0)
        if caption is not None:
            caption.set_text("")
        if eta_label is not None:
            eta_label.set_text("")
        return

    # ETA (mm:ss) when derivable; blank otherwise.
    if eta_label is not None:
        eta = runner.eta_seconds if status not in ("done", "stopped") else None
        eta_label.set_text(f"ETA {_format_mmss(eta)}" if eta is not None else "")


def _status_text(status: str) -> str:
    """Map a raw runner status to a clean, human-readable label."""
    return {
        "idle": "Idle",
        "running": "Running",
        "paused": "Paused",
        "done": "Done",
        "stopped": "Stopped",
        "error": "Error",
    }.get(status, status)


def _format_mmss(seconds: float | None) -> str:
    """Format a seconds count as ``mm:ss`` (e.g. ``2:05``); ``--:--`` if None."""
    if seconds is None or seconds < 0:
        return "--:--"
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    return f"{minutes:d}:{secs:02d}"


def _wrap_solve(
    state: AppState,
    handles: dict[str, Any],
    on_solve: Callable[[], None],
) -> None:
    """Read the tier slider / iteration inputs into state then invoke on_solve.

    PR 24a §3.7: the tier slider is the primary control; the ``Custom
    (advanced)`` expansion's ``iters_input`` + ``target_input`` are
    optional overrides. The tier slider's ``on_value_change`` already
    pushes the tier-recommended values into those inputs, so reading
    ``iters_input.value`` alone correctly captures both the tier default
    and any user override. The same logic applies to ``target_input``.

    v1.11 UI: the backend is always Rust — the user no longer picks an
    engine, so there is no toggle to read. ``SolveSession.backend`` is set
    to ``"rust"`` so ``ui/app.py`` forwards Rust to ``SolveRunner.start``
    (whose own default is already ``"rust"``). The Python path remains a
    silent in-dispatch fallback only.

    ``SolveInFlightError`` (a ``RuntimeError`` subclass) is caught around
    ``on_solve()`` so a genuine in-flight solve surfaces the friendly
    ``.message`` as a warning rather than a raw traceback string.
    """
    from nicegui import ui

    iters_input = handles.get("iters_input")
    target_input = handles.get("target_input")
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
    # Engine is always Rust now (v1.11 UI). We never write "python" here —
    # the Python path is a silent in-dispatch fallback only. ``ui/app.py``
    # reads ``state.current_solve.backend`` and forwards it to
    # ``SolveRunner.start`` (default also "rust").
    backend = "rust"
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

    # v1.11: no pre-solve tree-size guard. Flop solves are tractable on main's
    # fast engine and the marquee postflop path forces ``rvr_mode=True`` →
    # the bounded vector-form RvR aggregator. The GUI-branch oversized-solve
    # refusal (built against the old engine) is removed.

    # Invoke the caller's solve trigger. ``on_solve`` (ui/app.py) starts the
    # worker via ``SolveRunner.start``, which raises ``SolveInFlightError``
    # ONLY when a solve is genuinely running. Surface its friendly message
    # rather than any raw exception text.
    try:
        on_solve()
    except SolveInFlightError as err:
        ui.notify(err.message, type="warning")


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


_STREET_FIELD: dict[str, str] = {
    "flop": "flop_bet_fractions",
    "turn": "turn_bet_fractions",
    "river": "river_bet_fractions",
}


def _street_fractions(state: AppState, street: str) -> tuple[float, ...] | None:
    """Read the per-street opening-bet menu for ``street`` off the spot.

    Returns ``None`` when the street inherits the flat menu.
    """
    return getattr(state.current_spot, _STREET_FIELD[street])


def _on_street_bet_toggle(
    state: AppState, street: str, size: float, checked: bool
) -> None:
    """Toggle a size in/out of a per-street opening menu (C1).

    Writes ``state.current_spot.{flop,turn,river}_bet_fractions``. When the
    last checked size is removed, the street's field is reset to ``None`` so
    it inherits the flat menu again (``HUNLConfig`` treats ``None`` that
    way). The first time a size is checked for a street it seeds the menu
    from the empty set (a per-street override that is INDEPENDENT of the
    flat menu).
    """
    field_name = _STREET_FIELD[street]
    current = getattr(state.current_spot, field_name)
    sizes = set(current) if current is not None else set()
    if checked:
        sizes.add(size)
    else:
        sizes.discard(size)
    new_value: tuple[float, ...] | None = tuple(sorted(sizes)) if sizes else None
    setattr(state.current_spot, field_name, new_value)
    save_state()


def _fmt_x(x: float) -> str:
    """Render a raise multiplier without a trailing ``.0`` when integral."""
    return str(int(x)) if float(x).is_integer() else str(x)


def _apply_raise_sizes(state: AppState, raw: str) -> None:
    """Parse comma-separated raise MULTIPLIERS (× the bet) into the spot (C2).

    Writes ``state.current_spot.raise_size_xs``. Values are interpreted as
    raw multipliers of the bet faced (e.g. ``"2.5, 3"`` -> raise to 2.5x
    then 3x). Empty / unparseable / all-non-positive input leaves the
    existing value untouched (the engine requires a non-empty raise menu).
    """
    if not raw.strip():
        return
    try:
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        xs: list[float] = []
        for p in parts:
            v = float(p)
            if v <= 0.0:
                continue
            xs.append(v)
    except ValueError:
        return
    if not xs:
        return
    # Dedupe while preserving order; the engine treats raise slots
    # positionally so we keep the user's first-seen ordering.
    seen: set[float] = set()
    ordered: list[float] = []
    for v in xs:
        if v not in seen:
            seen.add(v)
            ordered.append(v)
    state.current_spot.raise_size_xs = tuple(ordered)
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

    Per PR 24a §3.4 + task #61 (default flipped 2026-05-27):
      * concrete + Rust  -> "true Nash (best-response walk)"
      * concrete + Python -> "true Nash (best-response walk (slow))"
      * RvR + ``solver_mode == "true_nash"`` (default) -> "true Nash RvR
                              (vector-form CFR, default; v1.7.0+; post-PR-114)"
      * RvR + ``solver_mode == "blueprint"`` (legacy opt-in) -> "blueprint
                              approximation (Pluribus-style aggregator,
                              legacy fast mode; not Nash)"

    Reads ``state.current_spot.rvr_mode``, ``state.current_spot.solver_mode``,
    and ``state.current_solve.backend`` (falling back to ``"python"`` when
    no solve has run yet — the chart is rendered at page-open with empty
    history so this default must be safe). The label is recomputed every
    ``_redraw_chart`` call.
    """
    rvr_mode = bool(getattr(state.current_spot, "rvr_mode", False))
    if rvr_mode:
        solver_mode = str(getattr(state.current_spot, "solver_mode", "blueprint"))
        if solver_mode == "true_nash":
            return "true Nash RvR (vector-form CFR, default; v1.7.0+; post-PR-114)"
        return (
            "blueprint approximation (Pluribus-style aggregator, "
            "legacy fast mode; not Nash)"
        )
    backend = "python"
    solve = state.current_solve
    if solve is not None:
        backend = str(getattr(solve, "backend", "python")).lower()
    if backend == "rust":
        return "true Nash (best-response walk)"
    return "true Nash (best-response walk (slow))"


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
    if isinstance(err, SolveInFlightError):
        # Genuine in-flight collision — show the friendly ``.message``, never
        # the raw internal exception text.
        ui.notify(err.message, type="warning", position="top")
        return
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
            "Locked strategies aren't supported with the short-stack "
            "push/fold preflop chart (≤15 BB). Switch to tree-builder mode "
            "to keep your locks.",
            type="negative",
            position="top",
            timeout=10000,
            multi_line=True,
        )

        def _retry_with_force_tree(_e: Any = None) -> None:
            state.runner._pending_force_tree_solve = True
            ui.notify(
                "Tree-builder mode enabled. Click Solve again to retry with "
                "your locked strategies.",
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
        # Generic fallback: keep it user-facing. Don't leak the internal
        # exception class name; a short, plain-language line plus the
        # underlying message is enough for the user to act on.
        ui.notify(
            f"The solve could not complete: {err}. "
            "Adjust the spot or iterations and try again.",
            type="negative",
            position="top",
            timeout=8000,
            multi_line=True,
        )


__all__ = ["refresh_progress", "render"]
