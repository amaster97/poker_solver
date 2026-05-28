"""NiceGUI page builder + ``ui.run`` launcher (PR 10a).

Composes the two-pane layout (Q1 LOCKED per ``pr10a_spec.md`` §0.1):

    +-----------------------------------------------------------------+
    | yellow Mock-mode banner (dismissible)                           |
    +-----------------------------------------------------------------+
    | header: title | spot label | status | [Lib] [theme] [hamburger] |
    +--------------------------------------+--------------------------+
    |                                      | ui.expansion             |
    |  RANGE MATRIX (centerpiece)          |   Spot input  (open)     |
    |  (Agent B's range_matrix.render)     |                          |
    |                                      | ui.expansion             |
    |  ----------------------------------  |   Run panel              |
    |  Combo inspector strip (Agent B)     |   (collapsed)            |
    |  (Q5: below matrix, full-width)      |                          |
    |                                      | ui.expansion             |
    |  ----------------------------------  |   Tree browser           |
    |  Decision tree (Agent B)             |   (collapsed)            |
    +--------------------------------------+--------------------------+

A single ``ui.timer(0.5, ...)`` polls ``state.runner`` and updates the run
panel's chart + readouts; the same timer also drives ``_maybe_flush_state``
for debounced persistence.

The worker thread NEVER touches NiceGUI; the polling timer is the ONLY
bridge between worker-state and UI updates (per ``pr10a_spec.md`` §6.1 +
NiceGUI mental model 7: do not block the asyncio loop).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from poker_solver.hunl import HUNLConfig, HUNLPoker, Street
from ui.state import (
    AppState,
    SolveSession,
    _maybe_flush_state,
    get_state,
    save_state,
)
from ui.views import (
    chained_tab,
    onboarding,
    preflop_chart,
    range_matrix,
    run_panel,
    spot_input,
    tree_browser,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ElementFilter markers (Agent C asserts on these):
#   'app-header', 'header-spot-label', 'header-status',
#   'library-button', 'theme-toggle', 'hamburger-menu',
#   'matrix-region', 'sidebar-spot-expansion', 'sidebar-run-expansion',
#   'sidebar-tree-expansion'.


def build_page() -> None:
    """The ``@ui.page('/')`` builder. Composes header + 2-pane layout.

    Registers a single ``ui.timer(0.5, _tick)`` that drives:
    - ``run_panel.refresh_progress(state)`` for chart + readouts updates,
    - ``_maybe_flush_state()`` for debounced atomic state.json writes.

    On first launch (``not state.prefs.onboarding_completed`` AND/OR
    state.json absent), opens the 3-step onboarding modal
    (``ui/views/onboarding.py``).
    """
    # Late import: nicegui must not be imported at module load (it is an
    # optional dep gated by the ``[ui]`` extra owned by Agent C).
    from nicegui import ui

    state = get_state()

    # The legacy "Mock mode" banner was removed once the real-solver
    # bindings shipped (v1.2.0). Production runs always route to the real
    # solver via ``SolveRunner._dispatch_solve``; the mock path is reserved
    # for smoke-test failure-mode injection (``mock_failure_mode='oom'``
    # etc.) and is unreachable from the UI. The ``mock_banner_dismissed``
    # pref field is retained on ``UIPrefs`` to keep legacy state.json files
    # backwards-compatible.

    # ----- Header -----
    with ui.row().classes("w-full items-center p-2 border-b").mark("app-header"):
        ui.label("poker-solver").classes("text-lg font-semibold")
        ui.separator().props("vertical")
        spot_label = _format_spot_label(state)
        ui.label(spot_label).classes("text-sm").mark("header-spot-label")
        ui.separator().props("vertical")
        status_label = ui.label(state.runner.status).classes("text-sm font-mono")
        status_label.mark("header-status")
        ui.space()
        ui.button(
            "Library",
            icon="folder",
            on_click=lambda: _open_library_stub(),
        ).props("flat").mark("library-header-button")
        _build_theme_toggle(state)
        ui.button(icon="menu").props("flat").mark("hamburger-menu")

    # ----- Tabs: Solver | Preflop Chart (task #55) | Chain solve (task #57) -----
    # The original two-pane layout lives inside the "Solver" tab so every
    # PR 10a/10b smoke test that looks up ``range-matrix-display`` etc.
    # still finds those markers on first page open (tab is open by
    # default). The "Preflop Chart" tab adds the 13x13 widget driven by
    # ``_rust.solve_hunl_preflop_rvr`` (PR #122). The "Chain solve" tab
    # wraps the chained orchestrator GUI (``ui/views/chained_tab.py``,
    # PR #148 / task #57).
    #
    # The Solver tab carries BOTH ``tab-solver`` (preflop-chart smoke)
    # and ``tab-solve`` (chained-tab smoke) markers so the two tests can
    # coexist after the dual merge.
    with ui.tabs().classes("w-full").mark("app-tabs") as tabs:
        solver_tab = ui.tab("Solver", icon="grid_view").mark(
            "tab-solver tab-solve"
        )
        preflop_chart_tab = ui.tab(
            "Preflop Chart", icon="leaderboard"
        ).mark("tab-preflop-chart")
        chained_tab_marker = ui.tab(
            "Chain solve", icon="link"
        ).mark("tab-chained")
    with ui.tab_panels(tabs, value=solver_tab).classes("w-full").mark(
        "app-tab-panels"
    ):
        with ui.tab_panel(solver_tab).mark("tab-panel-solver tab-panel-solve"):
            _render_solver_tab(state)
        with ui.tab_panel(preflop_chart_tab).mark("tab-panel-preflop-chart"):
            preflop_chart.render(
                state,
                on_solve=lambda: _on_preflop_chart_solve(state),
            )
        with ui.tab_panel(chained_tab_marker).mark("tab-panel-chained"):
            chained_tab.render(
                state,
                on_solve=lambda: _on_chained_solve(state),
            )

    # ----- The 500 ms poller (mental model 7: don't block the loop) -----
    # Track the last preflop_chart_result identity so we only refresh the
    # chart subtree when the worker actually publishes a new result.
    last_preflop_chart_id: list[int | None] = [None]
    # Track chained-solve completion so we only refresh the chained tab
    # when the result actually lands (one-shot per solve — refresh on
    # every tick would thrash the DOM grid).
    chained_state: dict[str, int | None] = {"last_id": None}

    def _tick() -> None:
        """Pump worker progress into the UI + flush debounced state."""
        try:
            run_panel.refresh_progress(state)
        except Exception:  # noqa: BLE001 -- never let the timer die
            logger.exception("run_panel.refresh_progress raised")
        # Also update the header status (cheap; just a label update).
        try:
            status_label.set_text(state.runner.status)
        except Exception:  # noqa: BLE001
            logger.exception("status label update failed")
        # Task #55: refresh the preflop chart widget when its worker
        # publishes a new result (identity change of
        # ``runner.preflop_chart_result``).
        try:
            current_id = id(getattr(state.runner, "preflop_chart_result", None))
            if current_id != last_preflop_chart_id[0]:
                last_preflop_chart_id[0] = current_id
                refresher = getattr(state.runner, "_preflop_chart_refresh", None)
                if callable(refresher):
                    refresher()
        except Exception:  # noqa: BLE001
            logger.exception("preflop chart refresh on tick raised")
        # Task #57: re-render the chained tab when a chained result lands.
        try:
            chained_result = getattr(state.runner, "chained_result", None)
            current_id_c = id(chained_result) if chained_result is not None else None
            if current_id_c != chained_state["last_id"]:
                chained_state["last_id"] = current_id_c
                refresh = getattr(state.runner, "_chained_refresh", None)
                if callable(refresh):
                    refresh()
        except Exception:  # noqa: BLE001
            logger.exception("chained tab refresh tick raised")
        # Debounced state.json flush.
        try:
            _maybe_flush_state()
        except Exception:  # noqa: BLE001
            logger.exception("_maybe_flush_state raised")

    ui.timer(0.5, _tick)

    # ----- Onboarding (3 steps; ``ui_mockups_and_debates.md`` §4) -----
    if not state.prefs.onboarding_completed:
        onboarding.show_modal(state)


def _render_solver_tab(state: AppState) -> None:
    """Render the original two-pane Solver layout (PR 10a Q1 LOCKED).

    Pulled out into a helper so the page builder can compose it inside
    a tab panel alongside the new "Preflop Chart" tab (task #55) and
    "Chain solve" tab (task #57).
    """
    from nicegui import ui

    with ui.row().classes("w-full no-wrap items-stretch"):
        # Center pane: matrix + (Agent B's) combo inspector strip + tree.
        # Agent B owns the actual range_matrix / tree_browser renders;
        # smoke tests assert `range-matrix-display`, `matrix-cell`,
        # `tree-browser`, etc. markers, which only exist once these
        # `render(state)` calls fire (PR 10a originally left them stubbed).
        with ui.column().classes("flex-grow p-2").mark("matrix-region"):
            range_matrix.render(state)
            ui.separator()
            tree_browser.render(state)

        # Right pane: collapsible sidebar with three expansion panels.
        with ui.column().classes("p-2 w-96").style("min-width: 320px"):
            # Spot input panel — open by default.
            with (
                ui.expansion(
                    "Spot Input",
                    icon="tune",
                    value=True,
                )
                .classes("w-full")
                .mark("sidebar-spot-expansion")
            ):
                spot_input.render(state)

            # Run panel — collapsed by default (per Q1: spot input
            # open, others closed).
            with (
                ui.expansion(
                    "Run Panel",
                    icon="play_arrow",
                    value=False,
                )
                .classes("w-full")
                .mark("sidebar-run-expansion")
            ):
                run_panel.render(
                    state,
                    on_solve=lambda: _on_solve(state),
                    on_pause=lambda: _on_pause(state),
                    on_stop=lambda: _on_stop(state),
                )

            # Tree browser slot — collapsed by default; same render
            # call is already fired in the matrix region's center
            # pane (this is just the sidebar expansion stub label).
            with (
                ui.expansion(
                    "Decision Tree",
                    icon="account_tree",
                    value=False,
                )
                .classes("w-full")
                .mark("sidebar-tree-expansion")
            ):
                ui.label(
                    "Decision tree renders inline below the matrix "
                    "(Q5 layout)."
                ).classes("text-gray-500 italic")


def _format_spot_label(state: AppState) -> str:
    """Compose the header's spot-summary label."""
    board = "".join(str(c) for c in state.current_spot.board) or "(preflop)"
    stacks = state.current_spot.stacks_bb
    if stacks[0] == stacks[1]:
        stack_text = f"{stacks[0]}BB"
    else:
        stack_text = f"{stacks[0]}/{stacks[1]}BB"
    street = state.current_spot.starting_street.name.lower()
    return f"{stack_text} {street} ({board})"


def _build_theme_toggle(state: AppState) -> None:
    """Build the Auto / Light / Dark toggle in the header."""
    from nicegui import ui

    options = ["auto", "light", "dark"]

    def _on_change(e: Any) -> None:
        state.prefs.dark_mode = str(e.value)
        save_state()
        # NiceGUI 2.x: ui.dark_mode().value accepts True/False/None.
        dark = {"auto": None, "light": False, "dark": True}[state.prefs.dark_mode]
        ui.dark_mode().value = dark

    ui.toggle(
        options,
        value=state.prefs.dark_mode,
        on_change=_on_change,
    ).props("flat dense").mark("theme-toggle")


def _open_library_stub() -> None:
    """Open the library dialog (stub — Agent C will fill the contents).

    The library_browser.py module exposes ``render(state)``; we just need
    to provide the modal shell here. Agent C owns the contents.
    """
    from nicegui import ui

    try:
        # Agent C may export ``show_modal`` or ``render``; try both.
        from ui.views import library_browser

        if hasattr(library_browser, "show_modal"):
            library_browser.show_modal(get_state())
            return
        with ui.dialog() as dialog, ui.card():
            library_browser.render(get_state())
            ui.button("Close", on_click=dialog.close)
        dialog.open()
    except (ImportError, ModuleNotFoundError):
        # Pre-Agent-C bootstrap: show a placeholder.
        with ui.dialog() as dialog, ui.card():
            ui.label("Library (stub — Agent C will wire).")
            ui.button("Close", on_click=dialog.close)
        dialog.open()


def _on_preflop_chart_solve(state: AppState) -> None:
    """Solve button handler for the preflop chart widget (task #55).

    Builds a preflop ``HUNLConfig`` from ``state.current_spot`` (stack
    + blinds) and dispatches to
    ``state.runner.start_preflop_chart(...)`` which calls
    ``_rust.solve_hunl_preflop_rvr`` (PR #122) on a daemon thread. The
    Rust binding emits a full preflop strategy dict keyed by hole-card
    pairs; the worker projects that into a per-class chart_result that
    ``ui/views/preflop_chart.py:project_chart`` consumes.

    Per-click parameters (open sizes, reraise multipliers, iterations)
    are read from ``state.runner._pending_preflop_chart_*`` which the
    input panel populates on click. Falls back to engine defaults when
    None.
    """
    from nicegui import ui

    spot = state.current_spot
    iterations = getattr(
        state.runner, "_pending_preflop_chart_iterations", None
    ) or 500
    open_sizes = getattr(state.runner, "_pending_preflop_chart_opens", None)
    reraise_mults = getattr(state.runner, "_pending_preflop_chart_mults", None)

    # Task #68 Phase 6: try blueprint first. When the user's
    # (stack_bb, ante) is covered by the Premium-A asset bundle (or
    # falls between two anchor depths), this returns instantly without
    # touching the Rust solver and stashes the chart_result + the
    # route_info badge directly. The polling timer in ``_tick`` picks
    # up the new ``preflop_chart_result`` identity and refreshes the
    # chart widget on the next tick.
    #
    # TODO(Phase 5): replace ``try_blueprint_preflop_chart`` with a
    # ``SolverRouter.solve(...)`` call once
    # ``poker_solver.solver_router.SolverRouter`` lands. For now we
    # consume the underlying ``BlueprintLoader`` + ``interpolate_strategy``
    # directly via ``ui.blueprint_router.BlueprintRouter``.
    try:
        blueprint_hit = state.runner.try_blueprint_preflop_chart(
            stack_bb=int(spot.stacks_bb[0]),
            ante=float(spot.ante),
        )
    except (RuntimeError, ImportError, OSError, ValueError) as exc:
        logger.exception("blueprint preflop chart lookup raised: %s", exc)
        blueprint_hit = False
    if blueprint_hit:
        # Refresh the chart widget so the badge + cells update on the
        # current frame; the polling timer would catch it on the next
        # tick anyway, but instant refresh feels snappier.
        refresher = getattr(state.runner, "_preflop_chart_refresh", None)
        if callable(refresher):
            try:
                refresher()
            except Exception:  # noqa: BLE001
                logger.exception("blueprint refresh raised")
        return

    # Build a clean preflop HUNLConfig:
    # - starting_street = PREFLOP
    # - initial_hole_cards = None (the Rust binding REQUIRES this to be
    #   None — see ``preflop_rvr.rs:1050-1056``)
    # - initial_pot = 0, initial_contributions = (0, 0): blinds are
    #   applied by the engine's tree builder.
    bb_cents = 100
    starting_stack_cents = max(1, int(spot.stacks_bb[0])) * bb_cents
    sb_cents = max(1, int(round(spot.sb_blind * bb_cents)))
    bb_blind_cents = max(1, int(round(spot.bb_blind * bb_cents)))
    ante_cents = max(0, int(round(spot.ante * bb_cents)))
    try:
        config = HUNLConfig(
            starting_stack=starting_stack_cents,
            small_blind=sb_cents,
            big_blind=bb_blind_cents,
            ante=ante_cents,
            starting_street=Street.PREFLOP,
            initial_board=(),
            initial_pot=0,
            initial_contributions=(0, 0),
            initial_hole_cards=(),  # = None for the binding
            preflop_raise_cap=spot.preflop_raise_cap,
            postflop_raise_cap=spot.postflop_raise_cap,
            bet_size_fractions=tuple(spot.bet_sizes_checked),
            include_all_in=spot.include_all_in,
            abstraction=None,
        )
    except ValueError as exc:
        ui.notify(
            f"Invalid preflop chart config: {exc}",
            type="negative",
            position="top",
        )
        return

    try:
        state.runner.start_preflop_chart(
            config,
            iterations=int(iterations),
            open_sizes_bb=list(open_sizes) if open_sizes else None,
            reraise_multipliers=list(reraise_mults) if reraise_mults else None,
        )
    except RuntimeError as exc:
        ui.notify(
            f"A solve is already running: {exc}",
            type="warning",
            position="top",
        )
        return
    except ImportError as exc:
        ui.notify(
            f"Preflop chart binding unavailable: {exc}",
            type="negative",
            position="top",
            timeout=6000,
            multi_line=True,
        )
        return


def _on_solve(state: AppState) -> None:
    """Solve button click handler.

    Builds an ``HUNLPoker`` + spawns the worker via
    ``state.runner.start(...)``. UI event handler is NOT awaited on solve
    completion (the worker runs in a background thread; progress polls via
    the ``ui.timer``).

    PR 24a §3.2: when ``spot.rvr_mode`` is set, routes through the
    range-vs-range aggregator. Hero / villain ranges are extracted via
    ``Spot.to_rvr_call_args()`` which already handles the
    ``hero_player``-driven swap.

    PR 24a §3.7: ``state.runner._pending_target_expl`` (set by the run
    panel's ``_wrap_solve``) is forwarded to ``SolveRunner.start`` so the
    tier-slider value reaches the engine.

    PR 24b §3.5/§3.6: ``state.current_spot.locked_strategies`` is threaded
    into ``SolveRunner.start``; ``villain_bet_bb`` is validated against
    the bettor's effective stack before solving; the push/fold ValueError
    is caught and re-surfaced as a notify with a remediation button that
    sets ``runner._pending_force_tree_solve=True`` and retries.
    """
    from nicegui import ui

    spot = state.current_spot
    # PR 24b §3.6: validate the facing-bet input before building the
    # config so the user sees an actionable error instead of an engine
    # ValueError. The bettor's effective stack is stack_bb minus the
    # half-pot they already put in over previous streets.
    if spot.villain_bet_bb > 0:
        bettor_idx = 0 if spot.bettor_is_p0 else 1
        bettor_stack_bb = float(spot.stacks_bb[bettor_idx])
        # The bettor's already-in chips = pot_half (their share of
        # pot_so_far) + bet. Effective remaining stack post-bet must be
        # non-negative.
        pot_half_bb = spot.pot_so_far_bb / 2.0
        if pot_half_bb + spot.villain_bet_bb > bettor_stack_bb:
            ui.notify(
                f"Villain bet ({spot.villain_bet_bb} BB) exceeds the "
                f"bettor's effective stack ({bettor_stack_bb} BB after "
                f"contributing {pot_half_bb} BB to the pot).",
                type="negative",
                position="top",
                timeout=6000,
                multi_line=True,
            )
            return

    try:
        config = spot.to_hunl_config()
    except ValueError as exc:
        ui.notify(
            f"Invalid spot configuration: {exc}",
            type="negative",
            position="top",
        )
        return

    # Edge case §6.4: push/fold dispatch at <= 15 BB. PR 10a surfaces the
    # warning; the actual dispatch happens via the existing
    # ``poker_solver.solve()`` route in PR 10b.
    if min(spot.stacks_bb) <= 15:
        ui.notify(
            f"{min(spot.stacks_bb)} BB stack: push/fold view recommended. "
            "Solving anyway. (PR 11 will offer a 'Switch to push/fold view' "
            "button here.)",
            type="warning",
            position="top",
            timeout=5000,
        )

    iterations = state.current_solve.iterations if state.current_solve else 1000
    backend = state.current_solve.backend if state.current_solve else "python"
    log_every = state.current_solve.log_every if state.current_solve else 50
    # PR 24a §3.7: pull the tier-slider target out of the
    # runner-side pending attribute. None means "use the default".
    target_exploitability = getattr(state.runner, "_pending_target_expl", None)
    # PR 24b §3.5: pull node-locks + force_tree_solve override from the
    # runner-side pending attributes. The locks live on the spot (so
    # they round-trip through state.json + library serialization); the
    # force_tree_solve flag lives on the runner (per-click escape hatch
    # set by the push/fold remediation notify button).
    locked_strategies = dict(spot.locked_strategies) if spot.locked_strategies else None
    force_tree_solve = bool(getattr(state.runner, "_pending_force_tree_solve", False))

    # ----- Range-vs-range branch (PR 24a §3.2) -----
    if spot.rvr_mode:
        try:
            rvr_config, hero_range, villain_range = spot.to_rvr_call_args()
        except ValueError as exc:
            ui.notify(
                f"Invalid RvR spot: {exc}",
                type="negative",
                position="top",
            )
            return
        if not hero_range or not villain_range:
            ui.notify(
                "Range-vs-range solve needs at least one hand class per side.",
                type="warning",
                position="top",
            )
            return
        rvr_game = HUNLPoker(config=rvr_config)
        try:
            state.runner.start(
                rvr_game,
                iterations=iterations,
                log_every=log_every,
                backend=backend,
                target_exploitability=target_exploitability,
                rvr_mode=True,
                rvr_hero_range=hero_range,
                rvr_villain_range=villain_range,
                rvr_hero_player=spot.hero_player,
                # Task #61: thread the solver-mode toggle through. Default
                # ``"blueprint"`` preserves the existing aggregator path;
                # ``"true_nash"`` dispatches to vector-form CFR.
                solver_mode=getattr(spot, "solver_mode", "blueprint"),
            )
        except RuntimeError as exc:
            ui.notify(f"Solve already running: {exc}", type="warning", position="top")
            return
        state.current_solve = SolveSession(
            spot=spot,
            iterations=iterations,
            log_every=log_every,
            backend=backend,
            started_at=state.runner.started_at,
            runner=state.runner,
        )
        return

    # ----- Concrete-vs-concrete branch (existing behaviour) -----
    game = HUNLPoker(config=config)
    try:
        state.runner.start(
            game,
            iterations=iterations,
            log_every=log_every,
            backend=backend,
            target_exploitability=target_exploitability,
            locked_strategies=locked_strategies,
            force_tree_solve=force_tree_solve,
        )
    except RuntimeError as exc:
        ui.notify(f"Solve already running: {exc}", type="warning", position="top")
        return

    state.current_solve = SolveSession(
        spot=spot,
        iterations=iterations,
        log_every=log_every,
        backend=backend,
        started_at=state.runner.started_at,
        runner=state.runner,
    )
    # PR 24b §3.5: reset the force_tree_solve escape after consuming it
    # so subsequent solves don't silently bypass the push/fold chart.
    # The notify-remediation button re-arms it per click.
    state.runner._pending_force_tree_solve = False


def _on_chained_solve(state: AppState) -> None:
    """Solve button click handler for the "Chain solve" tab (task #57).

    Routes through :func:`poker_solver.chained.solve_chained` via the
    ``solver_mode="chained"`` branch on ``SolveRunner.start``. The
    chained orchestrator requires a preflop config (empty board) and
    hero / villain ranges; we lift those from ``state.current_spot``
    using the same accessor (``to_rvr_call_args``) the RvR path uses,
    swapping out the engine config for a preflop-shaped one.

    Iteration count comes from
    ``state.runner._pending_chained_iterations`` (set by the chained
    tab's solve button); falls back to 500 if unset.
    """
    from dataclasses import replace as _dataclass_replace

    from nicegui import ui

    from poker_solver.hunl import Street

    spot = state.current_spot
    try:
        config = spot.to_hunl_config()
    except ValueError as exc:
        ui.notify(
            f"Invalid chained spot configuration: {exc}",
            type="negative",
            position="top",
        )
        return

    # The chained orchestrator only accepts preflop configs with
    # ``initial_hole_cards == ()``. ``Spot.to_hunl_config()`` picks
    # point-pair hole cards from the ranges — strip those out and pin
    # the street to preflop.
    config = _dataclass_replace(
        config,
        starting_street=Street.PREFLOP,
        initial_board=(),
        initial_hole_cards=(),
        initial_pot=0,
        initial_contributions=(0, 0),
    )

    hero_range = spot._range_hand_classes(spot.ranges[spot.hero_player])
    villain_range = spot._range_hand_classes(spot.ranges[1 - spot.hero_player])
    if not hero_range or not villain_range:
        ui.notify(
            "Chained solve needs at least one hand class per side.",
            type="warning",
            position="top",
        )
        return

    iterations = int(
        getattr(state.runner, "_pending_chained_iterations", 500) or 500
    )
    log_every = state.current_solve.log_every if state.current_solve else 50

    from poker_solver.hunl import HUNLPoker

    game = HUNLPoker(config=config)
    try:
        state.runner.start(
            game,
            iterations=iterations,
            log_every=log_every,
            solver_mode="chained",
            rvr_hero_range=hero_range,
            rvr_villain_range=villain_range,
            rvr_hero_player=spot.hero_player,
        )
    except RuntimeError as exc:
        ui.notify(f"Solve already running: {exc}", type="warning", position="top")
        return

    state.current_solve = SolveSession(
        spot=spot,
        iterations=iterations,
        log_every=log_every,
        backend="python",
        started_at=state.runner.started_at,
        runner=state.runner,
    )


def _on_pause(state: AppState) -> None:
    """Pause button click handler."""
    if state.runner.status == "running":
        state.runner.pause()
    elif state.runner.status == "paused":
        state.runner.resume()


def _on_stop(state: AppState) -> None:
    """Stop button click handler.

    Sets BOTH ``state.runner._stop_event`` AND ``ui.mock_solver._CANCEL_FLAG``
    so the worker exits within ONE snapshot interval (per ``pr10a_spec.md``
    §11 correctness #3 — gate for Agent C's smoke 5).
    """
    state.runner.stop()


def launch(
    port: int = 8080,
    host: str = "127.0.0.1",
    dark_mode: str = "auto",
) -> None:
    """Entry point called by ``poker-solver ui``.

    Registers the ``@ui.page('/')`` builder and calls ``ui.run``.

    - ``dark_mode``: ``"auto"`` (None = system follows), ``"light"`` (False),
      ``"dark"`` (True).
    - On ``OSError`` (port in use): tries 8081..8090, prints the chosen port
      (per ``pr10a_spec.md`` §12 risk 9). Binds only to 127.0.0.1; never
      0.0.0.0 in PR 10.
    """
    from nicegui import ui

    dark = {"auto": None, "light": False, "dark": True}[dark_mode]

    @ui.page("/")
    def _root_page() -> None:
        build_page()

    # Port-in-use fallback: try 8080..8090.
    last_exc: BaseException | None = None
    for try_port in range(port, port + 11):
        try:
            ui.run(
                host=host,
                port=try_port,
                dark=dark,
                reload=False,
                show=True,
                title="poker-solver",
            )
            return
        except OSError as exc:
            logger.warning("Port %d unavailable: %s", try_port, exc)
            last_exc = exc
            continue
    if last_exc is not None:
        raise last_exc


__all__ = ["build_page", "launch"]


# Per NiceGUI 3.x (https://nicegui.io/documentation/section_testing):
# the `User` test fixture runs this file via runpy with run_name="__main__".
# The guard form `{"__main__", "__mp_main__"}` is the documented pattern that
# supports both direct CLI invocation and NiceGUI's multiprocessing reload.
# Without this, `pytest tests/test_ui_smoke.py` errors out because
# `ui.run()` is never called and NiceGUI's `_startup()` raises RuntimeError
# ("You must call ui.run() to start the server.").
if __name__ in {"__main__", "__mp_main__"}:
    launch()
