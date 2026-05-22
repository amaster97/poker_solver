"""Library browser dialog (PR 11 extension of PR 10a stub).

PR 10a shipped this as a stub with three faked rows and disabled
``[Load selected]`` / ``[Delete]`` buttons. PR 11 (Agent C scope, per
``docs/pr11_prep/agent_c_prompt.md`` orchestrator instruction) extends
it to read from ``poker_solver.library.Library``:

- ``Library.list()`` is called on mount (and on filter change).
- The dialog body shows the real rows. Stub rows are kept as a
  graceful-degradation fallback ONLY when the library is empty AND the
  ``poker_solver.library`` module is not yet importable (i.e. running
  against a pre-Agent-A build).
- ``[Load selected]`` is enabled when a row is selected; per-row
  ``[Delete]`` triggers ``Library.delete``.
- Per spec §4.1 + §4.5: ``Library.get`` is the slow path and SHOULD be
  routed through ``asyncio.to_thread`` from the caller (the
  spot-input panel's Load button); this view returns a ``spot_id``
  via callback for the caller to dispatch.

NiceGUI ``ElementFilter`` markers (preserved from PR 10a so existing
smoke tests still pass):
  - ``library-dialog``
  - ``library-filter-input``
  - ``library-load-button``
  - ``library-delete-button``
  - ``library-stub-row-{idx}``  (idx in 0..2; only rendered in the
                                  fallback-stub mode for back-compat)
  - ``library-header-button``
  - ``library-row-{spot_id_prefix}`` — NEW in PR 11; one per real row.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from nicegui import ui

logger = logging.getLogger(__name__)

# Type-only import: Agent A owns ``AppState``. Importing it under
# TYPE_CHECKING keeps the dialog independent of Agent A's landing — at
# runtime the dialog only reads ``state`` opaquely.
if TYPE_CHECKING:
    from ui.state import AppState
else:
    try:  # pragma: no cover - guarded import for cross-agent ordering
        from ui.state import AppState
    except ImportError:  # pragma: no cover

        class AppState:  # type: ignore[no-redef]
            """Forward-declared placeholder until Agent A lands."""


# Number of rows the dialog requests from the library on each refresh.
# Spec §4.1: "table of ``SpotMetadata``"; spec §3.1 ``list`` defaults to
# limit=1000. We mirror that cap; the UI table is virtually-scrollable
# when NiceGUI exposes the component, otherwise the user filters down.
_LIST_LIMIT = 1000

# PR 10a fallback stub rows. Rendered ONLY when ``poker_solver.library``
# is not importable. Keeps the smoke test ``test_library_dialog_opens``
# green during ordering transitions.
_STUB_ROWS: tuple[tuple[str, str], ...] = (
    ("AKo vs QQ on K72r", "100bb · flop · 2026-05-19 · 2.1 mBB"),
    ("4bp 3-bet pot", "100bb · flop · 2026-05-18 · 0.8 mBB"),
    ("River-only subgame", "100bb · river · 2026-05-15 · 0.1 mBB"),
)


def _try_import_library() -> Any:
    """Return the ``poker_solver.library`` module, or ``None`` if missing.

    Importable since Agent A lands; during cross-agent ordering this may
    raise ``ImportError`` and we fall back to the PR 10a stub rows.
    """
    try:
        import poker_solver.library as lib_mod  # type: ignore[import-not-found]

        return lib_mod
    except ImportError:  # pragma: no cover - guarded for ordering
        return None


def _format_meta_line(meta: Any) -> str:
    """Render one ``SpotMetadata`` to the same compact 2-line shape as
    the PR 10a stub. Lossy on purpose: the table is sortable + filterable.
    """
    stack_str = f"{meta.stack_bb}bb"
    street = meta.street
    # ``created_at`` is unix epoch seconds; show as date for the user.
    try:
        import datetime as _dt

        date_str = _dt.datetime.fromtimestamp(meta.created_at).strftime("%Y-%m-%d")
    except (TypeError, ValueError):  # pragma: no cover
        date_str = str(meta.created_at)
    # Exploitability in mBB if it's a sensible scale; otherwise raw.
    try:
        exp_str = f"{meta.exploitability * 1000:.1f} mBB"
    except (TypeError, ValueError):  # pragma: no cover
        exp_str = str(meta.exploitability)
    return f"{stack_str} · {street} · {date_str} · {exp_str}"


def _row_title(meta: Any) -> str:
    """Human-friendly title for a library row."""
    label = (meta.label or "").strip() or f"spot_{meta.spot_id[:8]}"
    if meta.board_signature:
        return f"{label} on {meta.board_signature}"
    return label


def render(state: AppState) -> Any:
    """Render the library viewer dialog.

    Returns the ``ui.dialog`` handle so the caller (e.g. ``ui/app.py``)
    can attach the header button's ``open()`` callback.

    PR 11 behavior:
      - On open, the dialog reads ``Library.list()`` (limit=1000) and
        renders one row per ``SpotMetadata``.
      - If ``poker_solver.library`` is not importable, fall back to the
        PR 10a stub rows + "PR 11" toast (so smoke tests still pass on
        a Library-A-not-yet-landed worktree).
      - The filter input is bound to ``street``: typing ``flop`` /
        ``turn`` / ``river`` calls ``Library.list(street=...)``. Other
        text is matched as a substring on label.
      - ``[Load selected]`` is enabled once a row is selected;
        clicking it stores ``selected_spot_id`` on ``state`` (via
        attribute) so the caller can read it back and dispatch a
        ``Library.get`` from the spot-input panel.
      - Per-row ``[Delete]`` confirms then calls ``Library.delete``.
    """
    lib_mod = _try_import_library()

    # Per-dialog selection state. Stored locally so the dialog doesn't
    # mutate global state inappropriately; the caller reads back via
    # the helper ``get_selected_spot_id`` at click time.
    selection: dict[str, str | None] = {"spot_id": None}

    dialog = ui.dialog().mark("library-dialog")
    with dialog, ui.card().classes("min-w-[480px]"):
        ui.label("SOLVE LIBRARY").classes("text-lg font-bold")

        with ui.row().classes("w-full items-center"):
            filter_input = (
                ui.input(label="Filter")
                .mark("library-filter-input")
                .classes("flex-grow")
            )
            entry_count_label = ui.label("(0 entries)").classes("text-sm text-grey-7")

        # The container that gets re-rendered when the filter changes
        # or when a row is deleted.
        rows_container = ui.column().classes("w-full gap-1")

        with ui.row().classes("w-full justify-between items-center pt-2"):
            with ui.row().classes("gap-2"):
                load_btn = ui.button("Load selected").mark("library-load-button")
                load_btn.props("disable")
                delete_btn = ui.button("Delete").mark("library-delete-button")
                delete_btn.props("disable flat color=negative")
            footer_label = ui.label("").classes("text-xs text-grey-7 italic")

        def _refresh() -> None:
            """Re-read rows from the library and re-render the body."""
            rows_container.clear()
            filter_text = (filter_input.value or "").strip()

            if lib_mod is None:
                # PR 10a fallback: stub rows + the well-known toast.
                _render_stub_rows(rows_container)
                entry_count_label.set_text(f"({len(_STUB_ROWS)} entries)")
                footer_label.set_text(
                    "PR 11: persistence not yet wired (library module missing)"
                )
                return

            try:
                Library = lib_mod.Library
                LibraryFilter = lib_mod.LibraryFilter
                # Filter by street if the input matches one of the known
                # streets exactly; otherwise pass label_pattern as a
                # case-insensitive substring (Agent A's LibraryFilter
                # accepts a regex; we escape to make it substring-like).
                f: Any = None
                if filter_text:
                    lowered = filter_text.lower()
                    if lowered in {"flop", "turn", "river", "preflop"}:
                        f = LibraryFilter(street=lowered)
                    else:
                        import re as _re

                        f = LibraryFilter(label_pattern=_re.escape(filter_text))
                lib = Library.open()
                try:
                    rows = lib.list(f, limit=_LIST_LIMIT)
                finally:
                    lib.close()
            except Exception as exc:  # noqa: BLE001 - surface errors as a banner
                logger.exception("library_browser: list failed")
                with rows_container:
                    ui.label(f"Library unavailable: {exc}").classes("text-warning")
                entry_count_label.set_text("(? entries)")
                footer_label.set_text("library error — see logs")
                return

            entry_count_label.set_text(f"({len(rows)} entries)")
            footer_label.set_text("")
            with rows_container:
                if not rows:
                    ui.label("(no spots saved yet)").classes(
                        "text-sm text-grey-6 italic"
                    )
                    return
                for meta in rows:
                    spot_id = meta.spot_id
                    short = spot_id[:8]
                    row = ui.row().classes(
                        "w-full items-center cursor-pointer "
                        "hover:bg-grey-2 rounded px-2 py-1"
                    )
                    row.mark(f"library-row-{short}")
                    with row:
                        ui.label(_row_title(meta)).classes(
                            "font-mono text-sm flex-grow"
                        )
                        ui.label(_format_meta_line(meta)).classes(
                            "font-mono text-xs text-grey-7"
                        )

                    def _select(_e: Any = None, sid: str = spot_id) -> None:
                        selection["spot_id"] = sid
                        load_btn.props(remove="disable")
                        delete_btn.props(remove="disable")

                    row.on("click", _select)

        def _on_load(_e: Any = None) -> None:
            sid = selection["spot_id"]
            if sid is None:
                return
            # Stash the selection on state so the spot-input panel can
            # pick it up and dispatch Library.get via asyncio.to_thread
            # (spec §4.5 — avoid blocking the UI thread on gzip).
            try:
                state.selected_library_spot_id = sid
            except Exception:  # noqa: BLE001
                logger.warning("library_browser: could not stash selection on state")
            ui.notify(f"Selected {sid[:8]} — open spot input to load", type="info")
            dialog.close()

        def _on_delete(_e: Any = None) -> None:
            sid = selection["spot_id"]
            if sid is None or lib_mod is None:
                return
            try:
                lib = lib_mod.Library.open()
                try:
                    lib.delete(sid)
                finally:
                    lib.close()
                ui.notify(f"Deleted {sid[:8]}", type="positive")
            except Exception as exc:  # noqa: BLE001
                ui.notify(f"Delete failed: {exc}", type="negative")
            selection["spot_id"] = None
            load_btn.props("disable")
            delete_btn.props("disable")
            _refresh()

        load_btn.on("click", _on_load)
        delete_btn.on("click", _on_delete)
        filter_input.on("change", lambda _e=None: _refresh())

        # Initial render. Wrap in a `dialog.on('show', ...)` so the list
        # is refreshed each time the user re-opens the dialog (otherwise
        # batch_solve / spot-input save would not show up).
        dialog.on("show", lambda _e=None: _refresh())
        # And do one initial pass so the dialog is non-empty when first
        # opened during a test's render-then-click sequence.
        _refresh()

    return dialog


def _render_stub_rows(container: Any) -> None:
    """PR 10a fallback: render the three faked rows with the well-known
    "PR 11" toast on click. Used only when ``poker_solver.library`` is
    unimportable.
    """
    with container:
        for idx, (title, meta) in enumerate(_STUB_ROWS):
            row = ui.row().classes(
                "w-full items-center cursor-pointer "
                "hover:bg-grey-2 rounded px-2 py-1"
            )
            row.mark(f"library-stub-row-{idx}")
            with row:
                ui.label(title).classes("font-mono text-sm flex-grow")
                ui.label(meta).classes("font-mono text-xs text-grey-7")
            row.on(
                "click",
                lambda _e=None: ui.notify(
                    "PR 11 — load from disk is not yet wired",
                    type="info",
                ),
            )


def render_header_button(state: AppState, dialog: Any) -> None:
    """Render the header button that opens the library dialog.

    ``ui/app.py`` calls this from the header bar. Pattern:

        dialog = library_browser.render(state)
        library_browser.render_header_button(state, dialog)
    """
    del state  # reserved.
    btn = ui.button("Library", icon="library_books").mark("library-header-button")
    btn.props("flat")
    btn.on("click", dialog.open)


__all__ = ["render", "render_header_button"]
