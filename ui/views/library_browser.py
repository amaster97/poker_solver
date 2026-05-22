"""Library viewer stub for PR 10a — per ``pr10a_spec.md`` §4.6.

This is intentionally a stub: three faked rows, disabled
``[Load selected]`` and ``[Delete]`` buttons, and a "PR 11: persistence
not yet wired" banner. Clicking a stub row produces a toast directing
the user to PR 11.

The dialog and header-button render functions return enough handles for
Agent A's ``ui/app.py`` to wire the header button's ``open()`` callback.

NiceGUI ``ElementFilter`` markers (smoke test #8 asserts on these):
  - ``library-dialog``
  - ``library-filter-input``
  - ``library-load-button``
  - ``library-delete-button``
  - ``library-stub-row-{idx}``  (idx in 0..2)
  - ``library-header-button``   (Agent A's header bar binds; included
                                  here so smoke 8 finds either the binding
                                  in app.py or our own self-render path)
"""

from __future__ import annotations

from typing import Any

from nicegui import ui

# Type-only import: Agent A owns ``AppState``. Importing it under
# TYPE_CHECKING keeps the stub independent of Agent A's landing — at
# runtime the dialog only reads ``state`` opaquely.
try:  # pragma: no cover - guarded import for cross-agent ordering
    from ui.state import AppState
except ImportError:  # pragma: no cover

    class AppState:  # type: ignore[no-redef]
        """Forward-declared placeholder until Agent A lands."""


# The three faked rows shown in the stub (per ``pr10a_spec.md`` §4.6
# mockup). Order matters: tests address them by index via marker
# ``library-stub-row-{idx}``.
_STUB_ROWS: tuple[tuple[str, str], ...] = (
    (
        "AKo vs QQ on K72r",
        "100bb · flop · 2026-05-19 · 2.1 mBB",
    ),
    (
        "4bp 3-bet pot",
        "100bb · flop · 2026-05-18 · 0.8 mBB",
    ),
    (
        "River-only subgame",
        "100bb · river · 2026-05-15 · 0.1 mBB",
    ),
)


def render(state: AppState) -> Any:
    """Render the §4.6 library viewer dialog. STUB for PR 10a.

    Returns the ``ui.dialog`` handle so the caller (Agent A's
    ``ui/app.py``) can attach the header button's ``open()`` callback.

    The dialog body holds:
      - "SOLVE LIBRARY" header
      - Filter text field (no-op in stub)
      - Entry count ("(3 entries)")
      - Three faked stub rows (clickable → "PR 11" toast)
      - Disabled ``[Load selected]`` and ``[Delete]`` buttons
      - "PR 11: persistence not yet wired" banner
    """
    del state  # not yet consumed; reserved for PR 11 persistence wiring.

    dialog = ui.dialog().mark("library-dialog")
    with dialog, ui.card().classes("min-w-[480px]"):
        ui.label("SOLVE LIBRARY").classes("text-lg font-bold")

        with ui.row().classes("w-full items-center"):
            ui.input(label="Filter").mark("library-filter-input").classes("flex-grow")
            ui.label(f"({len(_STUB_ROWS)} entries)").classes("text-sm text-grey-7")

        with ui.column().classes("w-full gap-1"):
            for idx, (title, meta) in enumerate(_STUB_ROWS):
                row = ui.row().classes(
                    "w-full items-center cursor-pointer "
                    "hover:bg-grey-2 rounded px-2 py-1"
                )
                row.mark(f"library-stub-row-{idx}")
                with row:
                    ui.label(title).classes("font-mono text-sm flex-grow")
                    ui.label(meta).classes("font-mono text-xs text-grey-7")
                # Clicking a stub row emits a PR 11 toast (per §4.6 mockup).
                row.on(
                    "click",
                    lambda _e=None: ui.notify(
                        "PR 11 — load from disk is not yet wired",
                        type="info",
                    ),
                )

        with ui.row().classes("w-full justify-between items-center pt-2"):
            with ui.row().classes("gap-2"):
                load_btn = ui.button("Load selected").mark("library-load-button")
                load_btn.props("disable")
                delete_btn = ui.button("Delete").mark("library-delete-button")
                delete_btn.props("disable flat color=negative")
            ui.label("PR 11: persistence not yet wired").classes(
                "text-xs text-warning italic"
            )

    return dialog


def render_header_button(state: AppState, dialog: Any) -> None:
    """Render the header button that opens the library dialog.

    Agent A's ``ui/app.py`` calls this from the header bar. Pattern (per
    the prompt body):

        dialog = library_browser.render(state)
        library_browser.render_header_button(state, dialog)
    """
    del state  # reserved.
    btn = ui.button("Library", icon="library_books").mark("library-header-button")
    btn.props("flat")
    btn.on("click", dialog.open)


__all__ = ["render", "render_header_button"]
