"""Chained orchestrator GUI tab (task #57, #31 Phase C).

Two-pane GUI wrapper around :func:`poker_solver.solve_chained` (PR #121
Phase A). Composes:

  * LEFT pane — 13x13 preflop matrix. Each cell renders the hero's
    first-decision action frequencies for that hand class, colored by
    the dominant action (fold = grey, call/check = yellow, raise = red,
    jam = dark-red). Clicking a cell selects that hand class for the
    right pane.

  * RIGHT pane — preflop terminal action sequence selector + flop board
    picker. When the user picks a flop, this pane triggers
    :meth:`ChainedSolveResult.solve_postflop` (lazy) and displays the
    hero's postflop strategy for the selected hand class.

The chart and the postflop strategy both pull from a single
:class:`ChainedSolveResult` object stashed on
``state.runner.chained_result`` by ``SolveRunner._run_chained_path``
(see ``ui/state.py``). The lazy postflop cache is owned by that result
object; repeat board picks on the same action sequence are O(1).

Layout contract (mirrors the locked ``range_matrix._hand_class_at``
convention):

         A   K   Q   J   T   9   8   7   6   5   4   3   2
     A  AA  AKs AQs AJs ATs A9s A8s A7s A6s A5s A4s A3s A2s
     K  AKo KK  KQs KJs KTs K9s K8s K7s K6s K5s K4s K3s K2s
     ...
     2  A2o K2o Q2o J2o T2o 92o 82o 72o 62o 52o 42o 32o 22

Once PR #147 (preflop_chart widget) lands on main, the per-cell helpers
``hand_class_at`` / ``cell_color_rgb`` / ``classify_action`` /
``aggregate_actions`` should be lifted into a shared
``ui/views/_preflop_grid.py`` module and imported here. For now this
tab carries a small copy of those primitives so it does not depend on
the unmerged #147.

ElementFilter markers (smoke tests assert on these):
  ``chained-tab-display``            outer container
  ``chained-tab-grid``                left-pane grid container
  ``chained-tab-cell-{class}``        per-class grid marker
  ``chained-tab-action-select``      preflop terminal action selector
  ``chained-tab-board-picker``       flop board picker
  ``chained-tab-board-cell-{card}``  per-card flop picker button
  ``chained-tab-clear-board``        clear flop button
  ``chained-tab-postflop-display``   right-pane postflop strategy block
  ``chained-tab-postflop-row-{cls}`` per-class postflop row marker
  ``chained-tab-solve-button``       trigger button (preflop chained solve)
  ``chained-tab-iterations``         iteration count input
  ``chained-tab-status``             status indicator
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from poker_solver.card import RANKS, SUITS, Card

# PR #147 (merged before this PR) owns the canonical preflop grid
# primitives — re-export them here so the chained tab keeps a stable
# import surface (the chained-tab smoke tests import these helpers from
# ``ui.views.chained_tab`` directly) without duplicating the
# implementation. This satisfies the PR #148 docstring TODO that said
# "once #147 merges these will be lifted into a shared module."
from ui.views.preflop_chart import (
    _COLOR_CALL,
    _COLOR_EMPTY,
    _COLOR_FOLD,
    _COLOR_JAM,
    _COLOR_NEUTRAL,
    _COLOR_RAISE,
    CellSummary,
    aggregate_actions,
    cell_color_css,
    cell_color_rgb,
    classify_action,
    hand_class_at,
)

if TYPE_CHECKING:
    from poker_solver.chained import (
        BoardTuple,
        ChainedSolveResult,
        PreflopActionSequence,
    )
    from ui.state import AppState

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Layout constants — mirror PR #147 / range_matrix conventions
# -----------------------------------------------------------------------------

# Top-left = A, bottom-right = 2 (mirror of ``range_matrix._GRID_RANKS``).
_GRID_RANKS: tuple[str, ...] = tuple(reversed(RANKS))  # ('A', 'K', ..., '2')

_CELL_PX: int = 38

_DEFAULT_ITERATIONS: int = 500
_DEFAULT_HERO_RANGE: str = "AA, KK, QQ, AKs, AKo"
_DEFAULT_VILLAIN_RANGE: str = "AA, KK, QQ, AKs, AKo"


# -----------------------------------------------------------------------------
# Chained-result projection
# -----------------------------------------------------------------------------


def project_preflop(result: ChainedSolveResult | None) -> dict[str, CellSummary]:
    """Project ``result.preflop_result.per_class_strategy`` to per-class summaries.

    Returns an empty dict when ``result`` is None; the renderer paints
    every cell at the empty anchor in that case.
    """
    out: dict[str, CellSummary] = {}
    if result is None:
        return out
    per_class = getattr(result.preflop_result, "per_class_strategy", {}) or {}
    for hand_class, freqs in per_class.items():
        if not isinstance(freqs, dict):
            continue
        summary = aggregate_actions({str(k): float(v) for k, v in freqs.items()})
        summary.label = str(hand_class)
        out[str(hand_class)] = summary
    return out


def project_postflop(
    result: ChainedSolveResult | None,
    action_sequence: PreflopActionSequence | None,
    board: BoardTuple | None,
) -> dict[str, CellSummary] | None:
    """Project the postflop strategy for ``(action_sequence, board)``.

    Returns ``None`` when the needed inputs are not in scope (no chained
    result, no action sequence, board not 3 cards). Returns an empty dict
    when the postflop solve is not yet cached and we cannot trigger it
    (the cell render path uses the empty dict as a "loading" placeholder
    that ``trigger_postflop_solve`` can fill on the next render pass).
    """
    if result is None or action_sequence is None or board is None or len(board) != 3:
        return None
    cache_key = (action_sequence, tuple(board))
    cached = result.postflop_cache.get(cache_key)
    if cached is None:
        return {}  # not yet solved; caller can decide whether to trigger
    out: dict[str, CellSummary] = {}
    per_class = getattr(cached, "per_class_strategy", {}) or {}
    for hand_class, freqs in per_class.items():
        if not isinstance(freqs, dict):
            continue
        summary = aggregate_actions({str(k): float(v) for k, v in freqs.items()})
        summary.label = str(hand_class)
        out[str(hand_class)] = summary
    return out


# -----------------------------------------------------------------------------
# State helpers — selection state lives on ``runner`` as transient attrs
# (mirrors the pattern in ``preflop_chart._selected_cell_label``).
# -----------------------------------------------------------------------------


def _chained_result(state: AppState) -> ChainedSolveResult | None:
    runner = getattr(state, "runner", None)
    if runner is None:
        return None
    return getattr(runner, "chained_result", None)


def _selected_class(state: AppState) -> str | None:
    runner = getattr(state, "runner", None)
    if runner is None:
        return None
    return getattr(runner, "_chained_selected_class", None)


def _set_selected_class(state: AppState, label: str | None) -> None:
    runner = getattr(state, "runner", None)
    if runner is not None:
        runner._chained_selected_class = label  # type: ignore[attr-defined]


def _selected_action_sequence(state: AppState) -> PreflopActionSequence | None:
    runner = getattr(state, "runner", None)
    if runner is None:
        return None
    val = getattr(runner, "_chained_selected_action", None)
    if val is None:
        return None
    return tuple(val)


def _set_selected_action_sequence(
    state: AppState, action_sequence: PreflopActionSequence | None
) -> None:
    runner = getattr(state, "runner", None)
    if runner is not None:
        runner._chained_selected_action = action_sequence  # type: ignore[attr-defined]


def _selected_board(state: AppState) -> list[Card]:
    runner = getattr(state, "runner", None)
    if runner is None:
        return []
    board = getattr(runner, "_chained_selected_board", None)
    if board is None:
        return []
    return list(board)


def _set_selected_board(state: AppState, board: list[Card]) -> None:
    runner = getattr(state, "runner", None)
    if runner is not None:
        runner._chained_selected_board = list(board)  # type: ignore[attr-defined]


def _chained_status(state: AppState) -> str:
    runner = getattr(state, "runner", None)
    if runner is None:
        return "idle"
    mode = getattr(runner, "_mode", "")
    if mode == "chained":
        return str(getattr(runner, "status", "idle"))
    return "idle"


def format_action_sequence(seq: PreflopActionSequence) -> str:
    """Render an action token sequence as a human-readable label.

    The engine emits per-token strings (``"f"`` / ``"c"`` / ``"A"`` /
    ``"b{N}"`` / ``"r{N}"``). The dropdown label expands them with
    arrows so the user can see the sequence at a glance.
    """
    if not seq:
        return "(empty)"
    return " -> ".join(seq)


# -----------------------------------------------------------------------------
# NiceGUI rendering
# -----------------------------------------------------------------------------


def _import_nicegui() -> Any:
    """Late import — keeps this module importable in unit tests without nicegui."""
    from nicegui import ui as nicegui_ui

    return nicegui_ui


def render(state: AppState, on_solve: Callable[[], None] | None = None) -> None:
    """Render the Chain solve tab into the current NiceGUI slot.

    Composes the two-pane layout: 13x13 preflop matrix on the left, the
    action-selector + board-picker + postflop-strategy panel on the right.

    ``on_solve`` is invoked when the user clicks the "Solve chained" button;
    the caller (``ui/app.py:_on_chained_solve``) is responsible for kicking
    off the worker via ``state.runner.start(..., solver_mode="chained")``.
    """
    ui = _import_nicegui()

    @ui.refreshable  # type: ignore[untyped-decorator]
    def _grid_slot() -> None:
        _render_grid(state)

    @ui.refreshable  # type: ignore[untyped-decorator]
    def _right_pane_slot() -> None:
        _render_right_pane(state, on_solve, _refresh_all)

    def _refresh_all() -> None:
        try:
            _grid_slot.refresh()
        except Exception:  # noqa: BLE001
            logger.exception("chained tab grid refresh failed")
        try:
            _right_pane_slot.refresh()
        except Exception:  # noqa: BLE001
            logger.exception("chained tab right-pane refresh failed")

    with (
        ui.element("div")
        .mark("chained-tab-display")
        .style("background:#0f0f0f;padding:12px;border-radius:6px;width:100%")
    ):
        with ui.row().style(
            "align-items:center;justify-content:space-between;margin-bottom:8px"
        ):
            ui.label("CHAIN SOLVE").style(
                "font-weight:700;letter-spacing:0.05em;color:#f5f5f5"
            )
            ui.label(_subtitle(state)).mark("chained-tab-status").style(
                "color:#aaaaaa;font-size:12px"
            )
        with ui.row().style("align-items:flex-start;gap:14px;flex-wrap:nowrap"):
            with ui.element("div").style(
                f"min-width:{_CELL_PX * 13 + 30}px;flex:0 0 auto"
            ):
                _grid_slot()
            with ui.element("div").style(
                "flex:1 1 360px;min-width:360px;max-width:520px"
            ):
                _right_pane_slot()

    # Stash refresh hook on the runner so the polling timer in ``ui/app.py``
    # can re-trigger after the worker finishes (mirrors preflop_chart).
    runner = getattr(state, "runner", None)
    if runner is not None:
        runner._chained_refresh = _refresh_all  # type: ignore[attr-defined]


def _subtitle(state: AppState) -> str:
    result = _chained_result(state)
    status = _chained_status(state)
    if result is None:
        if status == "running":
            return "solving... (chart will appear on completion)"
        return "no chained solve yet"
    preflop = result.preflop_result
    iters = int(getattr(preflop, "iterations", 0))
    wall = float(getattr(preflop, "wall_clock_s", 0.0))
    n_terms = len(result.continuation_ranges)
    return f"{iters} iters / {wall:.1f}s / {n_terms} flop-reaching terminals"


def _render_grid(state: AppState) -> None:
    """Render the 13x13 preflop matrix (left pane)."""
    ui = _import_nicegui()
    summaries = project_preflop(_chained_result(state))

    with (
        ui.element("div")
        .mark("chained-tab-grid")
        .style(
            f"display:grid;grid-template-columns:repeat(13, {_CELL_PX}px);gap:2px"
        )
    ):
        for row in range(13):
            for col in range(13):
                cls = hand_class_at(row, col)
                summary = summaries.get(cls, CellSummary(label=cls, empty=True))
                _render_cell(state, cls, summary)


def _render_cell(state: AppState, hand_class: str, summary: CellSummary) -> None:
    """Render one matrix cell."""
    ui = _import_nicegui()
    color = cell_color_css(summary)
    tag = _cell_tag(summary)
    selected = _selected_class(state) == hand_class
    border = "#ffffff" if selected else "#1f1f1f"
    cell_marker = f"chained-tab-cell chained-tab-cell-{hand_class}"

    def _on_click(_event: object = None, cls: str = hand_class) -> None:
        _set_selected_class(state, cls)
        runner = getattr(state, "runner", None)
        if runner is not None and hasattr(runner, "_chained_refresh"):
            try:
                runner._chained_refresh()
            except Exception:  # noqa: BLE001
                logger.exception("chained tab cell click refresh failed")

    style = (
        f"width:{_CELL_PX}px;height:{_CELL_PX}px;"
        f"background:{color};color:#f5f5f5;"
        f"border:1px solid {border};"
        f"display:flex;flex-direction:column;justify-content:space-between;"
        f"padding:2px 3px;font-size:10px;cursor:pointer;"
        f"font-family:'SF Pro',Inter,sans-serif"
    )
    with (
        ui.element("div")
        .mark(cell_marker)
        .style(style)
        .on("click", _on_click)
    ):
        ui.label(hand_class).style(
            "font-weight:600;line-height:1;color:#f5f5f5"
        )
        if tag:
            ui.label(tag).style(
                "font-family:Menlo,Consolas,monospace;font-size:9px;"
                "align-self:flex-end;color:#1a1a1a"
            )
        ui.tooltip(_tooltip_text(hand_class, summary))


def _cell_tag(summary: CellSummary) -> str:
    if summary.empty:
        return ""
    pct = int(round(summary.dominant_prob * 100))
    letter = {"fold": "F", "call": "C", "raise": "R", "jam": "J"}.get(
        summary.dominant_kind, ""
    )
    if not letter:
        return ""
    return f"{letter}{pct}"


def _tooltip_text(hand_class: str, summary: CellSummary) -> str:
    if summary.empty:
        return f"{hand_class}: no chart data"
    parts = [hand_class]
    for label, prob in sorted(summary.actions.items(), key=lambda kv: -kv[1]):
        parts.append(f"{label} {int(round(prob * 100))}%")
    return " / ".join(parts)


# -----------------------------------------------------------------------------
# Right pane — solve input + action selector + board picker + postflop strategy
# -----------------------------------------------------------------------------


def _render_right_pane(
    state: AppState,
    on_solve: Callable[[], None] | None,
    refresh_after_change: Callable[[], None],
) -> None:
    ui = _import_nicegui()

    with (
        ui.element("div")
        .style(
            "background:#181818;padding:10px;border-radius:4px;"
            "border:1px solid #2a2a2a;margin-bottom:10px"
        )
    ):
        ui.label("Configure chained solve").style(
            "font-weight:600;color:#f0f0f0;margin-bottom:8px"
        )

        spot = state.current_spot

        # Hero range
        hero_range_str = spot.ranges[0].to_string() or _DEFAULT_HERO_RANGE
        hero_input = (
            ui.textarea(label="Hero range", value=hero_range_str)
            .classes("w-full font-mono text-xs")
            .mark("chained-tab-hero-range")
        )

        def _on_hero_range_change(e: Any) -> None:
            from ui.state import RangeWithFreqs

            try:
                new_range = RangeWithFreqs.from_string(str(e.value))
            except ValueError as exc:
                ui.notify(
                    f"Invalid hero range: {exc}", type="negative", position="top"
                )
                return
            ranges = list(state.current_spot.ranges)
            ranges[0] = new_range
            state.current_spot.ranges = (ranges[0], ranges[1])

        hero_input.on_value_change(_on_hero_range_change)

        # Villain range
        villain_range_str = spot.ranges[1].to_string() or _DEFAULT_VILLAIN_RANGE
        villain_input = (
            ui.textarea(label="Villain range", value=villain_range_str)
            .classes("w-full font-mono text-xs")
            .mark("chained-tab-villain-range")
        )

        def _on_villain_range_change(e: Any) -> None:
            from ui.state import RangeWithFreqs

            try:
                new_range = RangeWithFreqs.from_string(str(e.value))
            except ValueError as exc:
                ui.notify(
                    f"Invalid villain range: {exc}",
                    type="negative",
                    position="top",
                )
                return
            ranges = list(state.current_spot.ranges)
            ranges[1] = new_range
            state.current_spot.ranges = (ranges[0], ranges[1])

        villain_input.on_value_change(_on_villain_range_change)

        # Iterations + stack depth
        with ui.row().style("gap:8px;align-items:center"):
            stack_input = (
                ui.number(
                    label="Stack (BB)",
                    value=float(spot.stacks_bb[0]),
                    min=1.0,
                    max=200.0,
                    step=1.0,
                )
                .classes("w-28")
                .mark("chained-tab-stack")
            )

            def _on_stack_change(e: Any) -> None:
                val = max(1, int(round(float(e.value))))
                state.current_spot.stacks_bb = (val, val)

            stack_input.on_value_change(_on_stack_change)

            iter_input = (
                ui.number(
                    label="Preflop iters",
                    value=_DEFAULT_ITERATIONS,
                    min=1,
                    max=100000,
                    step=50,
                )
                .classes("w-28")
                .mark("chained-tab-iterations")
            )

            def _on_iter_change(e: Any) -> None:
                val = max(1, int(round(float(e.value))))
                state.current_spot.chained_iterations = val  # type: ignore[attr-defined]

            iter_input.on_value_change(_on_iter_change)

        def _click_solve() -> None:
            if on_solve is None:
                ui.notify(
                    "Chained dispatch is not wired (callback missing).",
                    type="warning",
                    position="top",
                )
                return
            runner = getattr(state, "runner", None)
            if runner is not None:
                try:
                    runner._pending_chained_iterations = (  # type: ignore[attr-defined]
                        int(round(float(iter_input.value)))
                    )
                except (TypeError, ValueError):
                    runner._pending_chained_iterations = _DEFAULT_ITERATIONS  # type: ignore[attr-defined]
            on_solve()
            refresh_after_change()

        ui.button(
            "Solve chained",
            on_click=_click_solve,
            icon="bolt",
        ).props("color=primary").classes("w-full mt-2").mark(
            "chained-tab-solve-button"
        )

    _render_action_selector(state, refresh_after_change)
    _render_board_picker(state, refresh_after_change)
    _render_postflop_panel(state, refresh_after_change)


def _render_action_selector(
    state: AppState, refresh_after_change: Callable[[], None]
) -> None:
    """Preflop terminal action selector — drives which continuation is solved."""
    ui = _import_nicegui()
    result = _chained_result(state)
    options: dict[str, str] = {}
    sequences: list[PreflopActionSequence] = []
    if result is not None:
        sequences = sorted(result.continuation_ranges.keys(), key=lambda s: (len(s), s))
        for seq in sequences:
            key = "|".join(seq) if seq else "(empty)"
            options[key] = format_action_sequence(seq)
    if not options:
        options = {"(none)": "(no chained solve yet)"}

    selected_seq = _selected_action_sequence(state)
    if selected_seq is None and sequences:
        selected_seq = sequences[0]
        _set_selected_action_sequence(state, selected_seq)
    current_key = (
        "|".join(selected_seq) if selected_seq else next(iter(options.keys()))
    )

    with (
        ui.element("div")
        .style(
            "background:#181818;padding:10px;border-radius:4px;"
            "border:1px solid #2a2a2a;margin-bottom:10px"
        )
    ):
        ui.label("Preflop terminal action").style(
            "font-weight:600;color:#f0f0f0;margin-bottom:6px"
        )

        def _on_select(e: Any) -> None:
            key = str(e.value)
            if key == "(none)" or key == "(empty)":
                _set_selected_action_sequence(state, ())
            else:
                _set_selected_action_sequence(state, tuple(key.split("|")))
            refresh_after_change()

        select = (
            ui.select(
                options=options,
                value=current_key,
                on_change=_on_select,
            )
            .classes("w-full")
            .mark("chained-tab-action-select")
        )
        # Keep the dropdown reactive — values come from the chained result.
        _ = select


def _render_board_picker(
    state: AppState, refresh_after_change: Callable[[], None]
) -> None:
    """Flop board picker — 4x13 suit-by-rank grid, capped at 3 cards."""
    ui = _import_nicegui()

    with (
        ui.element("div")
        .mark("chained-tab-board-picker")
        .style(
            "background:#181818;padding:10px;border-radius:4px;"
            "border:1px solid #2a2a2a;margin-bottom:10px"
        )
    ):
        ui.label("Flop board (3 cards)").style(
            "font-weight:600;color:#f0f0f0;margin-bottom:6px"
        )

        # Selected-card chip row.
        board = _selected_board(state)
        with ui.row().classes("gap-1 items-center min-h-6"):
            for card in board:
                with ui.row().classes(
                    "border rounded px-2 py-0 items-center gap-1 bg-gray-100 "
                    "dark:bg-gray-800"
                ):
                    ui.label(str(card)).classes("font-mono")

        # 4x13 suit-by-rank grid.
        with ui.grid(columns=13).classes("gap-1"):
            for suit_idx, suit_char in enumerate(SUITS):
                for rank_idx, rank_char in enumerate(RANKS):
                    rank_value = 14 - rank_idx
                    card = Card(rank_value, suit_idx)
                    card_str = f"{rank_char}{suit_char}"
                    in_board = card in board

                    def _on_card_click(_e: Any, c: Card = card) -> None:
                        _toggle_board_card(state, c)
                        refresh_after_change()

                    btn = (
                        ui.button(
                            card_str,
                            on_click=_on_card_click,
                        )
                        .props("flat dense")
                        .classes("font-mono")
                    )
                    btn.mark(f"chained-tab-board-cell-{card_str}")
                    if in_board:
                        btn.style("background:#3b3b50;color:#ffffff")

        def _clear() -> None:
            _set_selected_board(state, [])
            refresh_after_change()

        ui.button(
            "Clear board",
            icon="clear",
            on_click=_clear,
        ).props("flat dense").mark("chained-tab-clear-board")


def _toggle_board_card(state: AppState, card: Card) -> None:
    """Toggle a card on the flop selection (max 3 cards)."""
    board = _selected_board(state)
    if card in board:
        board.remove(card)
        _set_selected_board(state, board)
        return
    if len(board) >= 3:
        ui = _import_nicegui()
        ui.notify(
            "Flop is already 3 cards; remove one before adding another.",
            type="warning",
            position="top",
        )
        return
    board.append(card)
    _set_selected_board(state, board)


def _render_postflop_panel(
    state: AppState, refresh_after_change: Callable[[], None]
) -> None:
    """Right-pane postflop strategy display.

    When the user has selected a hand class + action sequence + 3-card
    flop, this panel triggers (or fetches the cached) postflop solve via
    ``ChainedSolveResult.solve_postflop`` and renders the hero's strategy
    for the selected class. Otherwise it shows a friendly status hint.
    """
    ui = _import_nicegui()

    with (
        ui.element("div")
        .mark("chained-tab-postflop-display")
        .style(
            "background:#1b1b1b;padding:10px;border-radius:4px;"
            "border:1px solid #303030"
        )
    ):
        ui.label("Postflop strategy").style(
            "font-weight:600;color:#f0f0f0;margin-bottom:6px"
        )

        result = _chained_result(state)
        if result is None:
            ui.label("Run a chained solve to populate the preflop chart.").style(
                "color:#a8a8a8;font-style:italic"
            )
            return

        selected_class = _selected_class(state)
        if selected_class is None:
            ui.label("Click a preflop cell to select a hand class.").style(
                "color:#a8a8a8;font-style:italic"
            )
            return

        action_seq = _selected_action_sequence(state)
        if action_seq is None or action_seq not in result.continuation_ranges:
            ui.label("Pick a preflop terminal action above.").style(
                "color:#a8a8a8;font-style:italic"
            )
            return

        board = _selected_board(state)
        if len(board) != 3:
            ui.label(
                f"Pick 3 flop cards above (currently {len(board)}/3) to "
                f"trigger the postflop solve."
            ).style("color:#a8a8a8;font-style:italic")
            return

        board_tuple = tuple(board)
        cache_key = (action_seq, board_tuple)
        cached = result.postflop_cache.get(cache_key)
        if cached is None:
            # Trigger the lazy solve on demand. The Rust vector-form CFR
            # runs synchronously here — for production wall-clock this is
            # roughly seconds to tens of seconds; an async dispatch path
            # is a Phase B concern (issue #31 §3 future work).
            try:
                cached = result.solve_postflop(action_seq, board_tuple)
            except (KeyError, ValueError) as exc:
                ui.label(f"Postflop solve failed: {exc}").style(
                    "color:#e07070"
                )
                return
            except (RuntimeError, ImportError) as exc:
                logger.exception("chained postflop solve raised")
                ui.label(f"Postflop solve error: {exc}").style("color:#e07070")
                return

        per_class = getattr(cached, "per_class_strategy", {}) or {}
        if selected_class not in per_class:
            ui.label(
                f"{selected_class} not in postflop continuation range (it "
                f"may have been blocked by the board or filtered out)."
            ).style("color:#a8a8a8;font-style:italic")
            return

        freqs = per_class[selected_class]
        ui.label(
            f"{selected_class} on {''.join(str(c) for c in board_tuple)} "
            f"after {format_action_sequence(action_seq)}"
        ).style("color:#f0f0f0;font-weight:600;margin-bottom:6px")

        for label, prob in sorted(freqs.items(), key=lambda kv: -float(kv[1])):
            bucket = classify_action(str(label))
            with ui.row().style(
                "align-items:center;gap:8px;padding:3px 0;"
            ).mark(f"chained-tab-postflop-row-{label}"):
                ui.label(str(label)).style(
                    "width:90px;color:#e8e8e8;font-family:Menlo,Consolas,monospace"
                )
                bar_width = 160
                fill_px = int(round(float(prob) * bar_width))
                anchor_rgb = {
                    "fold": _COLOR_FOLD,
                    "call": _COLOR_CALL,
                    "raise": _COLOR_RAISE,
                    "jam": _COLOR_JAM,
                }.get(bucket, _COLOR_NEUTRAL)
                anchor_css = (
                    f"rgb({anchor_rgb[0]},{anchor_rgb[1]},{anchor_rgb[2]})"
                )
                with ui.element("div").style(
                    f"width:{bar_width}px;height:12px;"
                    f"background:#0a0a0a;border:1px solid #2a2a2a;"
                    f"position:relative"
                ):
                    ui.element("div").style(
                        f"width:{fill_px}px;height:100%;background:{anchor_css}"
                    )
                ui.label(f"{float(prob) * 100:.1f}%").style(
                    "color:#cccccc;font-family:Menlo,Consolas,monospace;"
                    "width:60px;text-align:right"
                )


__all__ = [
    "CellSummary",
    "aggregate_actions",
    "cell_color_css",
    "cell_color_rgb",
    "classify_action",
    "format_action_sequence",
    "hand_class_at",
    "project_postflop",
    "project_preflop",
    "render",
    "_DEFAULT_ITERATIONS",
]
