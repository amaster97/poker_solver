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

from poker_solver.hunl import HUNLPoker
from ui.state import (
    AppState,
    SolveSession,
    _maybe_flush_state,
    get_state,
    save_state,
)
from ui.views import onboarding, run_panel, spot_input

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ElementFilter markers (Agent C asserts on these):
#   'mock-mode-banner', 'mock-mode-banner-dismiss',
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

    # ----- Yellow Mock-mode banner (Q7 LOCKED) -----
    if not state.prefs.mock_banner_dismissed:
        banner_row = (
            ui.row()
            .classes("w-full bg-yellow-200 dark:bg-yellow-800 p-2 items-center")
            .mark("mock-mode-banner")
        )
        with banner_row:
            ui.icon("warning", color="amber-9")
            ui.label(
                "Mock mode: solver outputs are hand-crafted fixtures (PR 10a). "
                "Switches to real solver in PR 10b."
            ).classes("text-sm")
            ui.space()

            def _dismiss_banner() -> None:
                state.prefs.mock_banner_dismissed = True
                save_state()
                # Banner removal requires page refresh; in NiceGUI 2.x we
                # cheap-trick this by hiding the row inline.
                banner_row.visible = False

            ui.button(
                "Dismiss",
                on_click=_dismiss_banner,
            ).props(
                "flat"
            ).mark("mock-mode-banner-dismiss")

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

    # ----- Two-pane layout (Q1 LOCKED) -----
    with ui.row().classes("w-full no-wrap items-stretch"):
        # Center pane: matrix + (Agent B's) combo inspector strip + tree.
        # Agent A reserves the slot but doesn't render the matrix contents.
        with ui.column().classes("flex-grow p-2").mark("matrix-region"):
            ui.label(
                "Range matrix renders here (Agent B's range_matrix.render)."
            ).classes("text-gray-500 italic")
            ui.separator()
            ui.label(
                "Combo inspector strip below (Agent B; Q5 LOCKED: below matrix)."
            ).classes("text-gray-500 italic")
            ui.separator()
            ui.label("Decision tree below (Agent B's tree_browser.render).").classes(
                "text-gray-500 italic"
            )

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

            # Run panel — collapsed by default (per Q1: spot input open, others closed).
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

            # Tree browser slot — Agent B fills the contents.
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
                    "Tree browser renders here (Agent B's tree_browser.render)."
                ).classes("text-gray-500 italic")

    # ----- The 500 ms poller (mental model 7: don't block the loop) -----
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
        # Debounced state.json flush.
        try:
            _maybe_flush_state()
        except Exception:  # noqa: BLE001
            logger.exception("_maybe_flush_state raised")

    ui.timer(0.5, _tick)

    # ----- Onboarding (3 steps; ``ui_mockups_and_debates.md`` §4) -----
    if not state.prefs.onboarding_completed:
        onboarding.show_modal(state)


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
    ).props(
        "flat dense"
    ).mark("theme-toggle")


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


def _on_solve(state: AppState) -> None:
    """Solve button click handler.

    Builds an ``HUNLPoker`` + spawns the worker via
    ``state.runner.start(...)``. UI event handler is NOT awaited on solve
    completion (the worker runs in a background thread; progress polls via
    the ``ui.timer``).
    """
    from nicegui import ui

    spot = state.current_spot
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

    game = HUNLPoker(config=config)
    iterations = state.current_solve.iterations if state.current_solve else 1000
    backend = state.current_solve.backend if state.current_solve else "python"
    log_every = state.current_solve.log_every if state.current_solve else 50

    try:
        state.runner.start(
            game,
            iterations=iterations,
            log_every=log_every,
            backend=backend,
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
