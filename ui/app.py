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
import os
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


# Dev-gate (W1/W4): the Concrete/RvR method toggle is hidden in production
# (postflop is Range-vs-range only). Each of app.py / spot_input.py /
# run_panel.py reads the ``POKER_SOLVER_DEV_CONCRETE`` env var DIRECTLY through
# a tiny local helper rather than importing one another's helper — this keeps
# the dev-gate logic identical across the three modules with zero new
# cross-module imports (no import-cycle risk). Read at call time (not import
# time) so tests can flip it per-case with ``monkeypatch``.
_CONCRETE_DEV_ENV_VAR: str = "POKER_SOLVER_DEV_CONCRETE"


def _concrete_dev_enabled() -> bool:
    """True when the dev-only Concrete/RvR method toggle is enabled."""
    return bool(os.environ.get(_CONCRETE_DEV_ENV_VAR, "").strip())


def _is_postflop(spot: Any) -> bool:
    """True when ``spot`` is a postflop spot (flop / turn / river).

    Regression 1: ``rvr_mode`` (range-vs-range) is a POSTFLOP-only concept —
    ``poker_solver.range_aggregator.solve_range_vs_range_nash`` raises a
    ``ValueError`` for a preflop spot. A postflop spot has a dealt board of
    3 (flop), 4 (turn) or 5 (river) cards; a preflop spot has an empty board.
    Read ``len(spot.board) >= 3`` directly (mirrors ``Spot.starting_street``,
    which derives PREFLOP/FLOP/TURN/RIVER from the same board length) so the
    test fixtures that pass a duck-typed spot with a ``board`` list also work.
    """
    board = getattr(spot, "board", None) or ()
    return len(board) >= 3


def _is_slot_teardown_error(exc: BaseException) -> bool:
    """True for the tab-switch teardown ``RuntimeError``.

    NiceGUI raises ``RuntimeError: The parent slot of the element has been
    deleted`` when a refresher / element update fires after the slot it
    targets was torn down (e.g. rapid top-tab switching while the 0.5 s
    poller is mid-tick). We special-case this so the poller can swallow it
    quietly instead of spamming a full traceback every tick, while letting
    every other error surface loudly.
    """
    return isinstance(exc, RuntimeError) and "parent slot" in str(exc)


def _has_result(runner) -> bool:
    """True when the runner holds any solve-result payload.

    The matrix / tree panels render placeholders until one of these result
    snapshots is populated. The header status chip uses this to avoid showing
    a stale terminal status (``done`` / ``stopped`` left over from a previous
    session) after a page reload or RESET SPOT, when no solve has actually
    produced output this session.
    """
    return bool(
        getattr(runner, "result", None)
        or getattr(runner, "rvr_result", None)
        or getattr(runner, "nash_result", None)
        or getattr(runner, "chained_result", None)
        or getattr(runner, "preflop_chart_result", None)
    )


def _run_tick_step(label: str, fn: Any) -> None:
    """Run one poller sub-step, guarding the tab-switch teardown race.

    The 0.5 s ``_tick`` must never die (a dead timer freezes the whole UI).
    Real exceptions are logged with a full traceback; the expected
    parent-slot-deleted teardown ``RuntimeError`` (see
    :func:`_is_slot_teardown_error`) is downgraded to a single quiet debug
    line so a burst of tab switches doesn't flood the server log.
    """
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 -- never let the timer die
        if _is_slot_teardown_error(exc):
            logger.debug("%s skipped: target slot torn down (tab switch)", label)
        else:
            logger.exception("%s raised", label)


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

    # F04: inject the single theme-aware stylesheet (CSS custom properties
    # per Quasar body--light / body--dark) BEFORE any view renders so the
    # ``var(--ps-*)`` neutrals the views reference resolve on first paint.
    _inject_theme_stylesheet()

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
        # Spot label (issue #4): make it visibly editable + clicking it
        # scrolls to / opens the Stacks & Blinds controls in spot_input.
        refresh_spot_label = _build_spot_label(state)
        ui.separator().props("vertical")
        # Running indicator (issue #3): an unambiguous spinner+badge driven
        # by the runner state, replacing the bare status word. Returns a
        # ``refresh()`` closure the 500 ms poller calls each tick.
        refresh_status_indicator = _build_status_indicator(state)
        ui.space()
        ui.button(
            "Library",
            icon="folder",
            on_click=lambda: _open_library(),
        ).props("flat").mark("library-header-button")
        _build_theme_toggle(state)
        _build_overflow_menu(state)

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
    #
    # Task #68 Phase 6: also track ``chained_postflop_route_info``
    # identity so the routing badge under the chained tab updates the
    # moment the user's flop-pick lazy-solve finishes. Without this the
    # badge would only redraw when ``chained_result`` itself changes,
    # which is rarely.
    chained_state: dict[str, int | None] = {
        "last_id": None,
        "last_post_route_id": None,
    }

    def _tick() -> None:
        """Pump worker progress into the UI + flush debounced state.

        Tab-switch teardown race: this 0.5 s poller drives refreshers that
        re-render content living inside the (Solver / Preflop Chart / Chain
        solve) tab panels. When the user rapidly switches tabs, the slot a
        refresher targets can be torn down between ticks, and NiceGUI raises
        ``RuntimeError: The parent slot of the element has been deleted``.
        Each sub-block is wrapped via :func:`_run_tick_step`, which swallows
        that specific teardown ``RuntimeError`` with a quiet debug log (so it
        doesn't spam a full traceback on every tick) while keeping any other
        exception loud — and never lets the timer die.
        """
        # Self-terminate once the page client is gone: the timer can keep
        # firing after its page's slot tree was torn down (startup race /
        # tab switch / disconnect), which otherwise raises ``RuntimeError:
        # The parent slot of the element has been deleted``. Cancel and bail
        # before touching any element.
        try:
            from nicegui import context

            client = context.client
            if client is not None and not getattr(client, "has_socket_connection", True):
                timer.cancel()
                return
        except Exception:  # noqa: BLE001 -- context may be unavailable mid-teardown
            pass

        try:
            _run_tick_step("run_panel.refresh_progress", lambda: run_panel.refresh_progress(state))
            # Header running indicator (cheap; toggles a spinner + recolours a
            # status badge from the runner state). Lives in the header, which
            # survives tab switches, but guarded uniformly for safety.
            _run_tick_step("status indicator update", refresh_status_indicator)
            # Keep the header spot label (issue #4) in sync when the user edits
            # stacks / board in the spot-input panel (cheap text compare).
            _run_tick_step("spot label refresh", refresh_spot_label)

            # Task #55: refresh the preflop chart widget when its worker
            # publishes a new result (identity change of
            # ``runner.preflop_chart_result``).
            def _refresh_preflop_chart() -> None:
                current_id = id(getattr(state.runner, "preflop_chart_result", None))
                if current_id != last_preflop_chart_id[0]:
                    last_preflop_chart_id[0] = current_id
                    refresher = getattr(state.runner, "_preflop_chart_refresh", None)
                    if callable(refresher):
                        refresher()

            _run_tick_step("preflop chart refresh on tick", _refresh_preflop_chart)

            # Task #57: re-render the chained tab when a chained result lands.
            # Task #68 Phase 6: also re-render when the postflop route info
            # identity changes (the user just paid for a flop subgame solve).
            def _refresh_chained() -> None:
                chained_result = getattr(state.runner, "chained_result", None)
                current_id_c = id(chained_result) if chained_result is not None else None
                post_info = getattr(state.runner, "chained_postflop_route_info", None)
                current_post_id = id(post_info) if post_info is not None else None
                id_changed = current_id_c != chained_state["last_id"]
                post_changed = current_post_id != chained_state["last_post_route_id"]
                if id_changed or post_changed:
                    chained_state["last_id"] = current_id_c
                    chained_state["last_post_route_id"] = current_post_id
                    refresh = getattr(state.runner, "_chained_refresh", None)
                    if callable(refresh):
                        refresh()

            _run_tick_step("chained tab refresh tick", _refresh_chained)
            # Debounced state.json flush.
            _run_tick_step("_maybe_flush_state", _maybe_flush_state)
        except RuntimeError as exc:
            # Final backstop: a slot teardown that escaped the per-substep
            # guards (e.g. the timer fired mid-teardown) must not surface a
            # full traceback. Cancel the now-orphaned timer and swallow.
            if _is_slot_teardown_error(exc):
                logger.debug("_tick skipped: target slot torn down; cancelling timer")
                timer.cancel()
                return
            raise

    timer = ui.timer(0.5, _tick)
    # Cancel the poller as soon as the page client disconnects so it can't
    # keep firing against a torn-down slot tree.
    try:
        from nicegui import context

        context.client.on_disconnect(lambda: timer.cancel())
    except Exception:  # noqa: BLE001 -- no client / disconnect hook in some contexts
        pass

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
            spot_expansion = (
                ui.expansion(
                    "Spot Input",
                    icon="tune",
                    value=True,
                )
                .classes("w-full")
                .mark("sidebar-spot-expansion")
            )
            # Stash the handle so the header spot-label (issue #4) can
            # expand + scroll to the Stacks & Blinds controls inside it.
            _spot_input_anchor["expansion"] = spot_expansion
            with spot_expansion:
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
    """Compose the header's spot-summary label (plain text)."""
    board = "".join(str(c) for c in state.current_spot.board) or "(preflop)"
    stacks = state.current_spot.stacks_bb
    if stacks[0] == stacks[1]:
        stack_text = f"{stacks[0]}BB"
    else:
        stack_text = f"{stacks[0]}/{stacks[1]}BB"
    street = state.current_spot.starting_street.name.lower()
    return f"{stack_text} {street} ({board})"


def _spot_label_prefix(state: AppState) -> str:
    """The non-board portion of the header spot label, e.g. ``"100BB flop "``."""
    stacks = state.current_spot.stacks_bb
    if stacks[0] == stacks[1]:
        stack_text = f"{stacks[0]}BB"
    else:
        stack_text = f"{stacks[0]}/{stacks[1]}BB"
    street = state.current_spot.starting_street.name.lower()
    return f"{stack_text} {street} "


def _spot_label_board_html(state: AppState) -> str:
    """Header board portion as inline HTML: ``(`` + colored card symbols + ``)``.

    Preflop spots have no board, so this renders ``(preflop)``.
    """
    from ui.views._cards import board_html

    board = state.current_spot.board
    if not board:
        return "(preflop)"
    return "(" + board_html(list(board), sep="") + ")"


# Module-level holder for the Spot Input expansion element so the header's
# spot-label click (issue #4) can expand + scroll to the Stacks & Blinds
# controls. ``_render_solver_tab`` (this file) populates ``["expansion"]``
# with the ``ui.expansion`` it builds; the header reads it back. A dict (not
# a global) keeps the reference per-build and avoids a module-level cycle.
_spot_input_anchor: dict[str, Any] = {"expansion": None}


def _build_spot_label(state: AppState):
    """Header spot label, made affordant (issue #4).

    The label still reads e.g. ``"95BB flop (Jh8c7s)"`` but is now styled
    like a clickable affordance (underline-on-hover + edit icon + tooltip)
    and, on click, expands the "Spot Input" panel and scrolls the Stacks &
    "Blinds & ante" controls into view. Those controls live in
    ``ui/views/spot_input.py`` (owned by another agent); we only point at
    the expansion this file builds in ``_render_solver_tab``.

    Returns a ``refresh()`` closure so the 500 ms poller keeps the label
    text in sync when the user edits stacks/board elsewhere.
    """
    from nicegui import ui

    def _go_to_spot_input() -> None:
        exp = _spot_input_anchor.get("expansion")
        if exp is None:
            return
        # Make sure the panel is open, then scroll it into view. The
        # ``getElement(id)`` client helper (NiceGUI >= 2.9) resolves the
        # Vue component; ``.$el`` is its root DOM node.
        try:
            exp.value = True
        except Exception:  # noqa: BLE001
            logger.exception("could not expand spot-input panel")
        try:
            # ``getHtmlElement(id)`` (NiceGUI client helper) returns the
            # element's root DOM node directly, handling the ``c<id>``
            # prefix internally — no ``.$el`` indirection needed.
            ui.run_javascript(
                f"getHtmlElement({exp.id})?.scrollIntoView("
                f"{{behavior: 'smooth', block: 'start'}});"
            )
        except Exception:  # noqa: BLE001
            logger.exception("scroll-to spot-input failed")

    with ui.row().classes(
        "items-center gap-0 cursor-pointer rounded px-1 "
        "hover:bg-primary/10 hover:underline"
    ).mark("header-spot-label") as label_row:
        # Prefix (stacks + street) stays plain text; the board portion is
        # rendered as colored suit-symbol HTML (issue: real card graphics).
        # ``header-spot-label`` (the row marker) + the canonical aria-label on
        # each card span keep the text/marker contract intact.
        prefix_widget = ui.label(_spot_label_prefix(state)).classes(
            "text-sm underline decoration-dotted underline-offset-4"
        )
        board_widget = ui.html(_spot_label_board_html(state)).classes(
            "text-sm underline decoration-dotted underline-offset-4"
        )
        ui.icon("edit", size="14px").classes("opacity-60 ml-1")
    label_row.tooltip("Click to edit stack depth & blinds")
    label_row.on("click", lambda _e=None: _go_to_spot_input())

    def _refresh() -> None:
        prefix_widget.set_text(_spot_label_prefix(state))
        board_widget.set_content(_spot_label_board_html(state))

    return _refresh


def _build_status_indicator(state: AppState):
    """Header running indicator (issue #3).

    Replaces the bare status word with an unambiguous spinner + coloured
    badge driven by the read-only runner API (``is_running``,
    ``progress_fraction``, ``eta_seconds``, ``current_iteration``,
    ``total_iterations``, ``status``). NOTE: the full progress *bar* is
    owned by ``run_panel.py`` — this is intentionally just a compact header
    chip, no second bar.

    Returns a ``refresh()`` closure the 500 ms poller calls each tick.
    """
    from nicegui import ui

    # status -> (quasar colour, icon, human label). Idle is muted; running
    # gets a live spinner; terminal states get a clear colour + glyph.
    _STYLE: dict[str, tuple[str, str, str]] = {
        "idle": ("grey-5", "circle", "Idle"),
        "running": ("primary", "", "Running"),
        "paused": ("orange", "pause", "Paused"),
        "done": ("positive", "check_circle", "Done"),
        "stopped": ("grey-6", "stop_circle", "Stopped"),
        "error": ("negative", "error", "Error"),
    }

    with ui.row().classes("items-center gap-2").mark("header-status"):
        spinner = ui.spinner(size="18px").props("color=primary")
        badge = ui.badge("Idle").props("color=grey-5").classes("text-xs")
        detail = ui.label("").classes("text-xs text-grey-7 font-mono")

    def _refresh() -> None:
        runner = state.runner
        status = runner.status
        # Self-heal a stale terminal status after a reload / RESET SPOT: if the
        # runner reports a terminal state but holds no result payload, the
        # matrix / tree show placeholders, so the chip should read "Idle" too.
        if status in ("done", "stopped") and not _has_result(runner):
            status = "idle"
        color, icon, human = _STYLE.get(status, ("grey-5", "circle", status))
        running = bool(runner.is_running)
        # Spinner only while a solve is live (running OR paused).
        spinner.set_visibility(running)
        badge.set_text(human)
        badge.props(f"color={color}")
        # Compact detail: "1200/5000 · ETA 14s" while running; cleared
        # otherwise. Guards every field — the API may return None.
        parts: list[str] = []
        if running:
            total = runner.total_iterations
            cur = runner.current_iteration
            if total:
                parts.append(f"{cur}/{total}")
            elif cur:
                parts.append(f"{cur} it")
            frac = runner.progress_fraction
            if frac is not None and not parts:
                parts.append(f"{frac * 100:.0f}%")
            eta = runner.eta_seconds
            if eta is not None and eta >= 0:
                parts.append(f"ETA {_format_eta(eta)}")
        detail.set_text(" · ".join(parts))

    _refresh()
    return _refresh


def _format_eta(seconds: float) -> str:
    """Compact human ETA: ``9s`` / ``2m14s`` / ``1h03m``."""
    s = int(round(seconds))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m{s % 60:02d}s"
    return f"{s // 3600}h{(s % 3600) // 60:02d}m"


def _build_overflow_menu(state: AppState) -> None:
    """Header overflow (hamburger) menu (issue #1).

    DECISION: wired, not removed. The 3-bar button previously had no
    ``on_click`` and did nothing. Per "less is more", it now opens a small
    ``ui.menu`` with three genuinely useful, low-frequency actions that
    don't deserve permanent header real estate:

    - "Replay onboarding" — re-runs the 3-step ``ui/views/onboarding.py``
      modal (resets ``onboarding_completed`` so the idempotent guard
      doesn't no-op, then re-shows it).
    - "About poker-solver" — version + a one-line description.

    The button keeps its ``hamburger-menu`` marker so existing smoke tests
    still find it.
    """
    from nicegui import ui

    # A ``ui.menu`` nested inside the button opens on click (Quasar
    # default). Combined single ``with`` keeps ruff SIM117 happy.
    with (
        ui.button(icon="menu").props("flat").mark("hamburger-menu"),
        ui.menu().props("auto-close").mark("overflow-menu"),
    ):
        ui.menu_item(
            "Replay onboarding",
            on_click=lambda: _replay_onboarding(state),
        ).mark("overflow-replay-onboarding")
        ui.separator()
        ui.menu_item(
            "About poker-solver",
            on_click=_show_about_dialog,
        ).mark("overflow-about")


def _replay_onboarding(state: AppState) -> None:
    """Reset the onboarding flag and re-show the 3-step modal (issue #1).

    ``onboarding.show_modal`` is idempotent (no-op when
    ``onboarding_completed`` is True), so we clear the flag first, persist,
    then re-invoke it.
    """
    state.prefs.onboarding_completed = False
    try:
        save_state()
    except Exception:  # noqa: BLE001
        logger.exception("save_state during replay onboarding failed")
    onboarding.show_modal(state)


def _show_about_dialog() -> None:
    """Small About dialog with the package version (issue #1)."""
    from nicegui import ui

    try:
        import poker_solver as _pkg

        version = getattr(_pkg, "__version__", "unknown")
    except Exception:  # noqa: BLE001
        version = "unknown"

    with ui.dialog() as dialog, ui.card().classes("min-w-[320px]"):
        ui.label("poker-solver").classes("text-lg font-bold")
        ui.label(f"Version {version}").classes("text-sm font-mono text-grey-7")
        ui.separator()
        ui.label(
            "Heads-up no-limit hold'em GTO solver with a preflop chart, "
            "range-vs-range solves, and a save library."
        ).classes("text-sm")
        with ui.row().classes("w-full justify-end pt-2"):
            ui.button("Close", on_click=dialog.close).props("flat")
    dialog.open()


# F04 (light-mode legibility): a single theme-aware stylesheet, injected
# once per page build. Quasar flips ``body.body--light`` / ``body.body--dark``
# the instant the header AUTO/LIGHT/DARK toggle changes ``ui.dark_mode``, so
# scoping the CSS custom properties on those body classes gives an instant,
# re-render-free recolor. The view modules reference these vars from their
# inline ``.style(...)`` strings (e.g. ``background:var(--ps-panel-bg)``).
#
# DARK values are the pre-F04 hardcoded literals VERBATIM so dark mode stays
# pixel-identical (it is the default + already legible). LIGHT values are the
# legible inversions. The dark set is also placed on bare ``body`` as the
# fallback so an unclassed/transitional state still matches the documented
# dark default rather than flashing unstyled.
#
# Only NEUTRAL chrome (panel/strip backgrounds, borders, near-white vs near-
# black text, muted captions) is themed here. The SEMANTIC strategy colors
# (RYG action blend, white→blue range-input gradient) are computed in Python
# and locked by smoke tests (``cell_color``, ``DISPLAY_PALETTE``,
# ``INPUT_PALETTE``); they are saturated enough to read on both a near-black
# and a light-grey cell, so they are intentionally NOT overridden. The few
# semantic ACCENT text colors that washed out on white (EV green, reach blue,
# lock gold, truncation amber) get a per-theme var so they darken on light.
_THEME_STYLESHEET: str = """
body, body.body--dark {
  --ps-panel-bg: #0f0f0f;
  --ps-strip-bg: #1b1b1b;
  --ps-input-bg: #181818;
  --ps-track-bg: #0a0a0a;
  --ps-border-strong: #303030;
  --ps-border-soft: #2a2a2a;
  --ps-cell-border: #1f1f1f;
  --ps-cell-border-sel: #ffffff;
  /* In-range cell base fill for the no-strategy-mass ("unsolved MIX")
     state. ``cell_color`` blends to rgb(0,0,0) when fold=call=raise=0;
     dark mode keeps that pure-black look verbatim, light mode swaps in a
     pale fill so the cell + its dark label stay legible. SOLVED cells keep
     their semantic RYG blend (untouched). */
  --ps-cell-bg: #000000;
  --ps-text: #f0f0f0;
  --ps-text-strong: #f5f5f5;
  --ps-text-dim: #e8e8e8;
  --ps-text-muted: #aaaaaa;
  --ps-text-faint: #9a9a9a;
  --ps-text-fainter: #7a7a7a;
  --ps-text-mono: #cccccc;
  --ps-text-label: #cfcfcf;
  --ps-cell-label: #f5f5f5;
  --ps-cell-tag: #1a1a1a;
  --ps-cell-tag-blocked: #dadada;
  --ps-faded: #3a3a3a;
  --ps-accent-ev: #9ad29a;
  --ps-accent-reach: #a8c8e8;
  --ps-accent-lock: #d4a017;
  --ps-accent-warn: #d09a4a;
  /* Semantic action TEXT (tree badges + legend glyphs). Dark = the Pio RYG
     verbatim; light darkens them so yellow/green text clears white. The
     filled-cell blend (cell_color) is unaffected — these are text-only. */
  --ps-act-raise: rgb(40,180,60);
  --ps-act-call: rgb(220,200,40);
  --ps-act-fold: rgb(220,40,40);
  /* Chained-tab neutrals (light-mode follow-up): selection fill, error
     text, and the interpolated-route accent. Dark = the pre-fix literals
     verbatim so dark stays pixel-identical. */
  --ps-selected-bg: #3b3b50;
  --ps-text-error: #e07070;
  --ps-accent-interp: #e0d27c;
}
body.body--light {
  --ps-panel-bg: #fafafa;
  --ps-strip-bg: #f2f2f2;
  --ps-input-bg: #f4f4f5;
  --ps-track-bg: #e4e4e7;
  --ps-border-strong: #c4c4c4;
  --ps-border-soft: #d4d4d4;
  --ps-cell-border: #d4d4d4;
  --ps-cell-border-sel: #1a1a1a;
  --ps-cell-bg: #ececec;
  --ps-text: #1a1a1a;
  --ps-text-strong: #111111;
  --ps-text-dim: #222222;
  --ps-text-muted: #555555;
  --ps-text-faint: #6b6b6b;
  --ps-text-fainter: #8a8a8a;
  --ps-text-mono: #3a3a3a;
  --ps-text-label: #333333;
  --ps-cell-label: #1a1a1a;
  --ps-cell-tag: #1a1a1a;
  --ps-cell-tag-blocked: #444444;
  --ps-faded: #d8d8d8;
  --ps-accent-ev: #1f7a3d;
  --ps-accent-reach: #1e64dc;
  --ps-accent-lock: #9a6b00;
  --ps-accent-warn: #a85f12;
  --ps-act-raise: rgb(22,120,45);
  --ps-act-call: rgb(150,120,0);
  --ps-act-fold: rgb(200,30,30);
  --ps-selected-bg: #dbe4ff;
  --ps-text-error: #c0392b;
  --ps-accent-interp: #9a7d00;
}
"""


def _inject_theme_stylesheet() -> None:
    """Inject the F04 theme-aware CSS custom properties for this page.

    ``ui.add_css`` appends the block to the current page's ``<head>``.
    ``build_page`` runs once per ``@ui.page('/')`` request, so this adds
    exactly one copy per page load (a fresh head per request — no
    cross-request accumulation). Called before any view renders so the
    ``var(--ps-*)`` neutrals resolve on first paint rather than flashing
    unstyled.
    """
    from nicegui import ui

    ui.add_css(_THEME_STYLESHEET)


def _build_theme_toggle(state: AppState) -> None:
    """Build the Auto / Light / Dark toggle in the header."""
    from nicegui import ui

    options = ["auto", "light", "dark"]

    def _on_change(e: Any) -> None:
        state.prefs.dark_mode = str(e.value)
        save_state()
        dark = {"auto": None, "light": False, "dark": True}[state.prefs.dark_mode]
        ui.dark_mode().value = dark
        # NiceGUI 3.x: a fresh ``ui.dark_mode()`` created inside an event
        # handler does not reliably broadcast to the client, so the theme
        # only ever applied on page load via the persisted pref. Flip Quasar
        # directly here (verified: ``Quasar.Dark.set`` toggles live).
        _js = "'auto'" if dark is None else ("true" if dark else "false")
        ui.run_javascript(f"Quasar.Dark.set({_js})")

    ui.toggle(
        options,
        value=state.prefs.dark_mode,
        on_change=_on_change,
    ).props("flat dense").mark("theme-toggle")


def _open_library() -> None:
    """Open the real library-browser dialog.

    Root cause of the old "empty dialog" bug: ``library_browser.render``
    *builds and returns its own* ``ui.dialog`` (it calls ``ui.dialog()``
    internally and fills a ``ui.card`` with the filter input, rows, and
    Load/Delete buttons). The previous ``_open_library_stub`` wrapped that
    call inside *another* ``with ui.dialog() as dialog, ui.card():`` block
    and then opened the OUTER dialog — so the real content rendered into a
    second, never-opened dialog, and the dialog the user saw contained only
    the stray ``Close`` button. The fix is to open the dialog ``render``
    returns, not to re-wrap it.

    A new dialog is built on each click (cheap) so the row list reflects the
    current on-disk library; ``render`` also re-reads ``Library.list()`` on
    each ``show`` event, so re-opens stay fresh.
    """
    from nicegui import ui

    try:
        from ui.views import library_browser

        dialog = library_browser.render(get_state())
        dialog.open()
    except Exception:  # noqa: BLE001 -- never let a header click crash the page
        logger.exception("library_browser.render raised; showing fallback dialog")
        with ui.dialog() as dialog, ui.card().classes("min-w-[360px]"):
            ui.label("Solve Library").classes("text-lg font-bold")
            ui.label(
                "Saved solves will appear here. The library couldn't be "
                "loaded right now — see the application logs for details."
            ).classes("text-sm text-grey-7")
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
    except RuntimeError:
        ui.notify(
            "A solve is already running — stop it first, then start a new one.",
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
    # W1/W4: authoritative dev-gate at the decision point. In production
    # (dev-gate OFF) POSTFLOP is Range-vs-range ONLY, so force ``rvr_mode``
    # True here — BEFORE the ``if spot.rvr_mode:`` branch below — regardless
    # of how the spot was (re)built. ``_on_load_preset`` / ``_on_reset``
    # replace ``state.current_spot`` with a fresh ``Spot()`` whose
    # ``rvr_mode`` defaults False, and ``run_panel.render()`` (which used to be
    # the only place that forced it) never re-runs after such a rebuild; so
    # without this guard a preset load silently reverted prod to the Concrete
    # point-pair path. Forcing it at the dispatch point closes that gap.
    #
    # Regression 1: ``rvr_mode`` is a POSTFLOP concept. The range-vs-range
    # aggregator (``poker_solver.range_aggregator.solve_range_vs_range_nash``)
    # RAISES ``ValueError("...does not support preflop range-vs-range...")``
    # for a PREFLOP spot, so forcing RvR on the default 100BB preflop spot
    # made the Solve button error in production. Only force RvR for postflop
    # spots (3/4/5 board cards = flop/turn/river); preflop spots keep
    # ``rvr_mode=False`` and route through their existing non-RvR path (the
    # preflop chart / concrete preflop solve).
    if not _concrete_dev_enabled() and _is_postflop(spot):
        spot.rvr_mode = True
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
            f"Short stack ({min(spot.stacks_bb)} BB): a push/fold strategy is "
            "usually optimal here. Solving the full tree anyway.",
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
        except RuntimeError:
            ui.notify("A solve is already running — stop it first, then start a new one.", type="warning", position="top")
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
    except RuntimeError:
        ui.notify("A solve is already running — stop it first, then start a new one.", type="warning", position="top")
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
    except RuntimeError:
        ui.notify("A solve is already running — stop it first, then start a new one.", type="warning", position="top")
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
