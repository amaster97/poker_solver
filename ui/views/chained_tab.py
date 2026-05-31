"""Chained orchestrator GUI tab — guided hole-card walkthrough (chain-solve "b").

Rebuilt 2026-05-30 (chain-solve "b" plan,
``docs/gui_audit/chain_solve_b_plan.md``) from a class-level matrix browser
into a **guided hole-card walkthrough**: "I have X/Y; walk preflop -> flop
(termination), showing at each street what I did / can do + the GTO rec +
the range."

Two-pane composition over :func:`poker_solver.solve_chained` (PR #121
Phase A):

  * LEFT pane — the 13x13 preflop matrix (``project_preflop``), with the
    hero's hand class HIGHLIGHTED. Read-only context for the walkthrough.

  * RIGHT pane — a STEPPER walkthrough:
      Screen 0 — config + 2-card hero hole-card picker -> "Solve chained".
      Screen 1 — preflop decision node(s): legal actions (walked off
        ``HUNLPoker``), the class-level GTO rec freqs
        (``result.query(hero_class, board=None)``, rendered as bars), and
        the 13x13 range. Pick an action -> advance until a flop-reaching
        terminal or a fold (terminate).
      Screen 2 — flop (Tier A): a 3-card board picker, then a synchronous
        ``solve_postflop`` on main's fast engine (no pre-solve tractability
        guard — flops are tractable in v1.11), then the class-level flop rec
        + range + route badge.
      Screen 3+ — turn/river (Tier B): "pending fast engine" placeholders,
        no compute.
      Termination — a summary strip of the walked path on a fold line.

**Honesty note (surfaced in the UI):** every strategy lookup is CLASS-level,
not combo-level. ``AhKh`` is treated as ``AKs`` for ALL recs (preflop AND
flop); board interaction (a flush draw on a two-heart flop) is NOT reflected.
Per-combo board-aware strategy is Phase B. The walkthrough banners this.

Walkthrough state is transient attrs on ``SolveRunner`` (mirrors the
``_chained_selected_*`` pattern), accessed via the ``_wt_*`` helpers below:
  ``_wt_hero_combo``  (Card, Card) | None  — hero's two hole cards
  ``_wt_tokens``      tuple[str, ...]       — action tokens walked so far
  ``_wt_step``        "preflop"|"flop"|"turn"|"river"|"done"
  ``_wt_flop``        list[Card]            — the 3 flop cards (Screen 2)

Reuse map (per the plan — reuse the LIGHT chained / preflop-chart
projections; do NOT reuse ``tree_browser`` / ``range_matrix``, which are
combo-level + keyed on ``runner.result`` which the chained path leaves
``None``):
  * preflop matrix: ``project_preflop`` + ``hand_class_at`` + ``CellSummary``.
  * freq bars: the bar block extracted into ``_render_freq_bars``.
  * flop rec+range: ``query`` / ``project_postflop`` / ``classify_action``.
  * picker grid: the shared ``_card_grid`` (hole + flop both use it).
  * hole -> class: ``classify_combo`` (state.py).

ElementFilter markers (smoke tests assert on these):
  ``chained-tab-display``            outer container
  ``chained-tab-grid``                left-pane preflop matrix container
  ``chained-tab-cell-{class}``        per-class grid marker
  ``chained-tab-stepper``             street breadcrumb / stepper
  ``chained-tab-step-{street}``       per-step nav chip (preflop/flop/turn/river)
  ``chained-tab-hole-picker``         hero 2-card picker container
  ``chained-tab-hole-cell-{card}``    per-card hole-picker button
  ``chained-tab-legal-action-{label}`` a legal action button at the cur node
  ``chained-tab-board-picker``       flop board picker
  ``chained-tab-board-cell-{card}``  per-card flop picker button
  ``chained-tab-clear-board``        clear flop button
  ``chained-tab-postflop-display``   right-pane flop strategy block
  ``chained-tab-postflop-row-{cls}`` per-action flop strategy row marker
  ``chained-tab-pending-engine``     Tier-B turn/river placeholder
  ``chained-tab-solve-button``       trigger button (preflop chained solve)
  ``chained-tab-iterations``         iteration count input
  ``chained-tab-status``             status indicator
  ``chained-tab-route-preflop`` / ``-route-postflop``  routing badges
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from poker_solver.card import RANKS, SUITS, Card

# PR #147 owns the canonical preflop grid primitives — re-export them here
# so the chained tab keeps a stable import surface (the chained-tab smoke
# tests import these helpers from ``ui.views.chained_tab`` directly).
from ui.views.preflop_chart import (
    _COLOR_CALL,
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
    from poker_solver.hunl import HUNLState
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

# Walkthrough streets, in order. "done" is the terminal pseudo-step (fold or
# end of the supported chain).
_WT_STREETS: tuple[str, ...] = ("preflop", "flop", "turn", "river")


# -----------------------------------------------------------------------------
# Chained-result projection (unchanged — reused by the matrix + flop screens)
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
    when the postflop solve is not yet cached and we cannot trigger it.
    """
    if result is None or action_sequence is None or board is None or len(board) != 3:
        return None
    try:
        from poker_solver.chained import _canonicalize_board

        cache_key = (action_sequence, _canonicalize_board(board))
    except (ValueError, ImportError):
        return None
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
# Runner-attached transient state
# -----------------------------------------------------------------------------


def _chained_result(state: AppState) -> ChainedSolveResult | None:
    runner = getattr(state, "runner", None)
    if runner is None:
        return None
    return getattr(runner, "chained_result", None)


def _runner(state: AppState) -> Any | None:
    return getattr(state, "runner", None)


def _hole_cards(state: AppState) -> list[Card]:
    """The hero's selected hole cards (0, 1, or 2 cards)."""
    runner = _runner(state)
    if runner is None:
        return []
    combo = getattr(runner, "_wt_hero_combo", None)
    if not combo:
        return []
    return list(combo)


def _set_hole_cards(state: AppState, cards: list[Card]) -> None:
    runner = _runner(state)
    if runner is not None:
        runner._wt_hero_combo = tuple(cards) if cards else None  # type: ignore[attr-defined]


def _hero_class(state: AppState) -> str | None:
    """Hero's hand class derived from the two hole cards (class-level)."""
    cards = _hole_cards(state)
    if len(cards) != 2:
        return None
    from ui.state import classify_combo

    try:
        return classify_combo(cards[0], cards[1])
    except ValueError:
        return None


def _wt_tokens(state: AppState) -> PreflopActionSequence:
    runner = _runner(state)
    if runner is None:
        return ()
    val = getattr(runner, "_wt_tokens", None)
    return tuple(val) if val else ()


def _set_wt_tokens(state: AppState, tokens: PreflopActionSequence) -> None:
    runner = _runner(state)
    if runner is not None:
        runner._wt_tokens = tuple(tokens)  # type: ignore[attr-defined]


def _wt_step(state: AppState) -> str:
    runner = _runner(state)
    if runner is None:
        return "preflop"
    return str(getattr(runner, "_wt_step", "preflop") or "preflop")


def _set_wt_step(state: AppState, step: str) -> None:
    runner = _runner(state)
    if runner is not None:
        runner._wt_step = step  # type: ignore[attr-defined]


def _wt_flop(state: AppState) -> list[Card]:
    runner = _runner(state)
    if runner is None:
        return []
    flop = getattr(runner, "_wt_flop", None)
    return list(flop) if flop else []


def _set_wt_flop(state: AppState, flop: list[Card]) -> None:
    runner = _runner(state)
    if runner is not None:
        runner._wt_flop = list(flop)  # type: ignore[attr-defined]


def _chained_status(state: AppState) -> str:
    runner = _runner(state)
    if runner is None:
        return "idle"
    mode = getattr(runner, "_mode", "")
    if mode == "chained":
        return str(getattr(runner, "status", "idle"))
    return "idle"


def format_action_sequence(seq: PreflopActionSequence) -> str:
    """Render an action token sequence as a human-readable label.

    The engine emits per-token strings (``"f"`` / ``"c"`` / ``"x"`` /
    ``"A"`` / ``"b{N}"`` / ``"r{N}"``); expand them with arrows.
    """
    if not seq:
        return "(start)"
    return " -> ".join(token_label(t) for t in seq)


def _slug(label: str) -> str:
    """Slugify a button label into a single-token marker suffix.

    NiceGUI's ``.mark()`` splits on whitespace, so a label like
    ``"raise to 200"`` would otherwise become three marker tokens. Collapse
    whitespace to underscores so ``chained-tab-legal-action-{slug}`` stays a
    single, assertable marker.
    """
    return "_".join(label.split())


def token_label(token: str) -> str:
    """Human-readable label for a single engine action token."""
    if not token:
        return "?"
    head = token[0]
    base = {
        "f": "fold",
        "c": "call",
        "x": "check",
        "A": "all-in",
        "b": "bet",
        "r": "raise",
    }.get(head, token)
    if head in ("b", "r") and len(token) > 1:
        return f"{base} to {token[1:]}"
    return base


# -----------------------------------------------------------------------------
# Preflop tree-walk helpers (forward enumeration of hero decision nodes)
# -----------------------------------------------------------------------------


def _build_walk_game(state: AppState) -> Any | None:
    """Build a ``HUNLPoker`` matching the chained solve's preflop config.

    Hole cards do NOT affect preflop action legality (legality depends only
    on stacks + contributions), so we walk with a placeholder pair — exactly
    like ``chained._enumerate_preflop_terminals``. Returns ``None`` when the
    spot can't be turned into a preflop config.
    """
    from dataclasses import replace as _dc_replace

    from poker_solver.card import Card as _Card
    from poker_solver.hunl import HUNLPoker, Street

    spot = state.current_spot
    try:
        config = spot.to_hunl_config()
    except (ValueError, AttributeError):
        return None
    placeholder = (
        (_Card.from_str("As"), _Card.from_str("Ah")),
        (_Card.from_str("Kd"), _Card.from_str("Kc")),
    )
    config = _dc_replace(
        config,
        starting_street=Street.PREFLOP,
        initial_board=(),
        initial_pot=0,
        initial_contributions=(0, 0),
        initial_hole_cards=placeholder,
    )
    return HUNLPoker(config)


def _advance_to_tokens(
    game: Any, tokens: PreflopActionSequence
) -> HUNLState | None:
    """Walk ``game`` from the initial state along ``tokens``.

    Returns the state reached after consuming every token, or ``None`` if
    the token path is not legal against the tree (defensive — should not
    happen for tokens produced by our own action buttons).
    """
    from poker_solver.chained import _last_token

    state = game.initial_state()
    for want in tokens:
        if game.is_terminal(state) or game.current_player(state) == -1:
            return None
        matched = None
        for action in game.legal_actions(state):
            new_state = game.apply(state, action)
            if _last_token(state, new_state) == want:
                matched = new_state
                break
        if matched is None:
            return None
        state = matched
    return state


def _legal_action_options(
    game: Any, walk_state: HUNLState
) -> list[tuple[str, str]]:
    """Return ``[(token, label)]`` for every legal action at ``walk_state``.

    Each token is what ``_last_token`` emits after applying the action — the
    same token alphabet ``continuation_ranges`` is keyed on, so picking an
    action and appending its token keeps the walk in sync with the
    orchestrator's terminal enumeration.
    """
    from poker_solver.chained import _last_token

    options: list[tuple[str, str]] = []
    for action in game.legal_actions(walk_state):
        new_state = game.apply(walk_state, action)
        token = _last_token(walk_state, new_state)
        if not token:
            continue
        options.append((token, token_label(token)))
    return options


# -----------------------------------------------------------------------------
# NiceGUI rendering
# -----------------------------------------------------------------------------


def _import_nicegui() -> Any:
    """Late import — keeps this module importable in unit tests without nicegui."""
    from nicegui import ui as nicegui_ui

    return nicegui_ui


def render(state: AppState, on_solve: Callable[[], None] | None = None) -> None:
    """Render the Chain solve tab — guided hole-card walkthrough.

    LEFT pane = the 13x13 preflop matrix (hero class highlighted). RIGHT
    pane = the stepper walkthrough. ``on_solve`` is invoked when the user
    clicks "Solve chained"; ``ui/app.py:_on_chained_solve`` kicks off the
    worker via ``state.runner.start(..., solver_mode="chained")``.
    """
    ui = _import_nicegui()

    @ui.refreshable  # type: ignore[untyped-decorator]
    def _grid_slot() -> None:
        _render_grid(state)

    @ui.refreshable  # type: ignore[untyped-decorator]
    def _right_pane_slot() -> None:
        _render_right_pane(state, on_solve, _refresh_all)

    @ui.refreshable  # type: ignore[untyped-decorator]
    def _routing_slot() -> None:
        _render_routing_indicator(state)

    def _refresh_all() -> None:
        for name, slot in (
            ("grid", _grid_slot),
            ("right-pane", _right_pane_slot),
            ("routing", _routing_slot),
        ):
            try:
                slot.refresh()
            except Exception:  # noqa: BLE001
                logger.exception("chained tab %s refresh failed", name)

    with (
        ui.element("div")
        .mark("chained-tab-display")
        .style(
            "background:var(--ps-panel-bg);padding:12px;border-radius:6px;width:100%"
        )
    ):
        with ui.row().style(
            "align-items:center;justify-content:space-between;margin-bottom:8px"
        ):
            ui.label("CHAIN SOLVE — WALKTHROUGH").style(
                "font-weight:700;letter-spacing:0.05em;color:var(--ps-text-strong)"
            )
            ui.label(_subtitle(state)).mark("chained-tab-status").style(
                "color:var(--ps-text-muted);font-size:12px"
            )
        # Class-level honesty banner (chain-solve "b" plan risk 2). Always
        # present so the user is never misled into reading combo-exact recs.
        ui.label(
            "Class-level only: your exact suits (e.g. AhKh) are treated as the "
            "hand CLASS (AKs) for every rec — board interaction like a flush "
            "draw is not modeled. Per-combo board-aware play is a later engine."
        ).style(
            "color:var(--ps-text-fainter);font-size:11px;font-style:italic;"
            "margin-bottom:6px;display:block;max-width:880px"
        )
        _routing_slot()
        with ui.row().style("align-items:flex-start;gap:14px;flex-wrap:nowrap"):
            with ui.element("div").style(
                f"min-width:{_CELL_PX * 13 + 30}px;flex:0 0 auto"
            ):
                _grid_slot()
            with ui.element("div").style(
                "flex:1 1 400px;min-width:380px;max-width:560px"
            ):
                _right_pane_slot()

    runner = getattr(state, "runner", None)
    if runner is not None:
        runner._chained_refresh = _refresh_all  # type: ignore[attr-defined]


def _subtitle(state: AppState) -> str:
    result = _chained_result(state)
    status = _chained_status(state)
    if result is None:
        if status == "running":
            return "solving... (walkthrough unlocks on completion)"
        return "no chained solve yet"
    preflop = result.preflop_result
    iters = int(getattr(preflop, "iterations", 0))
    wall = float(getattr(preflop, "wall_clock_s", 0.0))
    n_terms = len(result.continuation_ranges)
    return f"{iters} iters / {wall:.1f}s / {n_terms} flop-reaching terminals"


def _render_routing_indicator(state: AppState) -> None:
    """Routing badges (preflop + postflop) — one line under the header."""
    ui = _import_nicegui()
    runner = getattr(state, "runner", None)
    preflop_info = (
        getattr(runner, "chained_preflop_route_info", None)
        if runner is not None
        else None
    )
    postflop_info = (
        getattr(runner, "chained_postflop_route_info", None)
        if runner is not None
        else None
    )

    from ui.blueprint_router import SourceLabel, describe_route

    pre_text = (
        f"preflop: {describe_route(preflop_info)}"
        if preflop_info is not None
        else "preflop: [unrouted] click Solve chained"
    )
    post_text = (
        f"postflop: {describe_route(postflop_info)}"
        if postflop_info is not None
        else "postflop: [unrouted] reach + pick a flop to trigger"
    )

    def _color(info: object | None) -> str:
        if info is None:
            return "var(--ps-text-fainter)"
        label = getattr(info, "source", None)
        if label == SourceLabel.BLUEPRINT:
            return "var(--ps-accent-ev)"
        if label == SourceLabel.INTERPOLATED:
            return "var(--ps-accent-interp)"
        if label == SourceLabel.LIVE:
            return "var(--ps-text-dim)"
        return "var(--ps-text-fainter)"

    with (
        ui.element("div")
        .mark("chained-tab-route-indicator")
        .style(
            "display:flex;flex-direction:column;gap:2px;"
            "padding:4px 0;margin-bottom:6px;"
            "font-family:Menlo,Consolas,monospace;font-size:11px"
        )
    ):
        ui.label(pre_text).mark("chained-tab-route-preflop").style(
            f"color:{_color(preflop_info)}"
        )
        ui.label(post_text).mark("chained-tab-route-postflop").style(
            f"color:{_color(postflop_info)}"
        )


# -----------------------------------------------------------------------------
# Left pane — 13x13 preflop matrix (hero class highlighted)
# -----------------------------------------------------------------------------


def _render_grid(state: AppState) -> None:
    """Render the 13x13 preflop matrix; the hero's class is highlighted."""
    ui = _import_nicegui()
    summaries = project_preflop(_chained_result(state))
    hero_cls = _hero_class(state)

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
                _render_cell(state, cls, summary, highlighted=(cls == hero_cls))


def _render_cell(
    state: AppState, hand_class: str, summary: CellSummary, *, highlighted: bool
) -> None:
    """Render one matrix cell. ``highlighted`` marks the hero's hand class."""
    ui = _import_nicegui()
    color = cell_color_css(summary)
    tag = _cell_tag(summary)
    border = "var(--ps-cell-border-sel)" if highlighted else "var(--ps-cell-border)"
    border_w = "2px" if highlighted else "1px"
    cell_marker = f"chained-tab-cell chained-tab-cell-{hand_class}"

    style = (
        f"width:{_CELL_PX}px;height:{_CELL_PX}px;"
        f"background:{color};color:var(--ps-cell-label);"
        f"border:{border_w} solid {border};"
        f"display:flex;flex-direction:column;justify-content:space-between;"
        f"padding:2px 3px;font-size:10px;"
        f"font-family:'SF Pro',Inter,sans-serif"
    )
    with ui.element("div").mark(cell_marker).style(style):
        ui.label(hand_class).style(
            "font-weight:600;line-height:1;color:var(--ps-cell-label)"
        )
        if tag:
            ui.label(tag).style(
                "font-family:Menlo,Consolas,monospace;font-size:9px;"
                "align-self:flex-end;color:var(--ps-cell-tag)"
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
# Shared card-picker grid (hole + flop both use this)
# -----------------------------------------------------------------------------


def _card_grid(
    state: AppState,
    selected: list[Card],
    cap: int,
    on_toggle: Callable[[Card], None],
    marker_prefix: str,
    refresh_after_change: Callable[[], None],
) -> None:
    """Render a 4x13 suit-by-rank card-picker grid capped at ``cap`` cards.

    Each button carries the marker ``{marker_prefix}-{card}`` where ``card``
    is ``str(Card)`` (e.g. ``As``, ``7c``) — so the marker label and the
    actual ``Card`` always agree (the old board picker had a rank-inversion
    bug where the marker said one card and the toggle added another). The
    selected-card chip row sits above the grid.
    """
    ui = _import_nicegui()

    with ui.row().classes("gap-1 items-center min-h-6"):
        for card in selected:
            with ui.row().classes(
                "border rounded px-2 py-0 items-center gap-1 bg-gray-100 "
                "dark:bg-gray-800"
            ):
                ui.label(str(card)).classes("font-mono")

    with ui.grid(columns=13).classes("gap-1"):
        # Suits down (s, h, d, c), ranks across high->low so the label
        # matches ``str(card)`` exactly.
        for suit_idx in range(len(SUITS)):
            for rank_value in range(14, 1, -1):
                card = Card(rank_value, suit_idx)
                card_str = str(card)
                in_sel = card in selected

                def _on_click(_e: Any, c: Card = card) -> None:
                    on_toggle(c)
                    refresh_after_change()

                btn = (
                    ui.button(card_str, on_click=_on_click)
                    .props("flat dense")
                    .classes("font-mono")
                    .mark(f"{marker_prefix}-{card_str}")
                )
                if in_sel:
                    btn.style(
                        "background:var(--ps-selected-bg);"
                        "color:var(--ps-cell-border-sel)"
                    )

    _ = cap  # cap is enforced by the on_toggle closure


# -----------------------------------------------------------------------------
# Right pane — stepper walkthrough
# -----------------------------------------------------------------------------


def _render_right_pane(
    state: AppState,
    on_solve: Callable[[], None] | None,
    refresh_after_change: Callable[[], None],
) -> None:
    ui = _import_nicegui()
    result = _chained_result(state)

    # Screen 0 — config + hero hole-card picker. Always rendered (it is how
    # the user starts / restarts a walkthrough).
    _render_config_and_hole_picker(state, on_solve, refresh_after_change)

    if result is None:
        with (
            ui.element("div")
            .mark("chained-tab-postflop-display")
            .style(
                "background:var(--ps-strip-bg);padding:10px;border-radius:4px;"
                "border:1px solid var(--ps-border-strong)"
            )
        ):
            ui.label("Pick your two cards, then Solve chained to walk it.").style(
                "color:var(--ps-text-muted);font-style:italic"
            )
        return

    # Stepper / breadcrumb.
    _render_stepper(state, refresh_after_change)

    step = _wt_step(state)
    if step == "preflop":
        _render_preflop_step(state, refresh_after_change)
    elif step == "flop":
        _render_flop_step(state, refresh_after_change)
    elif step in ("turn", "river"):
        _render_pending_step(state, step)
    elif step == "done":
        _render_termination(state, refresh_after_change)
    else:
        _render_preflop_step(state, refresh_after_change)


def _render_config_and_hole_picker(
    state: AppState,
    on_solve: Callable[[], None] | None,
    refresh_after_change: Callable[[], None],
) -> None:
    ui = _import_nicegui()

    with (
        ui.element("div")
        .style(
            "background:var(--ps-input-bg);padding:10px;border-radius:4px;"
            "border:1px solid var(--ps-border-soft);margin-bottom:10px"
        )
    ):
        ui.label("Configure + start walkthrough").style(
            "font-weight:600;color:var(--ps-text);margin-bottom:8px"
        )

        spot = state.current_spot

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

        # Hero hole-card picker (2 cards). The picker mutates the runner's
        # transient ``_wt_hero_combo``; ``_on_chained_solve`` reads it.
        _render_hole_picker(state, refresh_after_change)

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


def _render_hole_picker(
    state: AppState, refresh_after_change: Callable[[], None]
) -> None:
    ui = _import_nicegui()
    cards = _hole_cards(state)
    hero_cls = _hero_class(state)

    with (
        ui.element("div")
        .mark("chained-tab-hole-picker")
        .style(
            "background:var(--ps-strip-bg);padding:8px;border-radius:4px;"
            "border:1px solid var(--ps-border-soft);margin-top:8px"
        )
    ):
        label = "Your hole cards (pick 2)"
        if hero_cls is not None:
            label = f"Your hole cards — class {hero_cls}"
        ui.label(label).style(
            "font-weight:600;color:var(--ps-text);margin-bottom:4px"
        )

        def _toggle_hole(card: Card) -> None:
            sel = _hole_cards(state)
            if card in sel:
                sel.remove(card)
                _set_hole_cards(state, sel)
                return
            if len(sel) >= 2:
                ui.notify(
                    "Two cards already picked; remove one first.",
                    type="warning",
                    position="top",
                )
                return
            sel.append(card)
            _set_hole_cards(state, sel)

        _card_grid(
            state,
            selected=cards,
            cap=2,
            on_toggle=_toggle_hole,
            marker_prefix="chained-tab-hole-cell",
            refresh_after_change=refresh_after_change,
        )

        def _clear_hole() -> None:
            _set_hole_cards(state, [])
            refresh_after_change()

        ui.button(
            "Clear cards", icon="clear", on_click=_clear_hole
        ).props("flat dense").mark("chained-tab-clear-hole")


def _render_stepper(
    state: AppState, refresh_after_change: Callable[[], None]
) -> None:
    """Breadcrumb / stepper: Preflop -> Flop -> Turn -> River + back."""
    ui = _import_nicegui()
    cur = _wt_step(state)
    # Determine the furthest reachable street so we don't let the user jump
    # ahead of where the walk actually is. Preflop is always available;
    # flop/turn/river depend on the walk having reached them.
    reached_flop = cur in ("flop", "turn", "river", "done") and bool(_wt_tokens(state))

    with (
        ui.element("div")
        .mark("chained-tab-stepper")
        .style(
            "display:flex;align-items:center;gap:6px;flex-wrap:wrap;"
            "margin-bottom:10px"
        )
    ):
        for street in _WT_STREETS:
            is_cur = street == cur
            is_reachable = street == "preflop" or (
                street == "flop" and reached_flop
            )
            bg = "var(--ps-selected-bg)" if is_cur else "var(--ps-input-bg)"
            opacity = "1.0" if is_reachable else "0.45"

            def _go(_e: Any = None, s: str = street) -> None:
                if s == "preflop":
                    # Rewind to the preflop root.
                    _set_wt_tokens(state, ())
                    _set_wt_flop(state, [])
                    _set_wt_step(state, "preflop")
                elif s == "flop" and reached_flop:
                    _set_wt_step(state, "flop")
                refresh_after_change()

            chip = (
                ui.button(street.capitalize(), on_click=_go)
                .props("flat dense")
                .mark(f"chained-tab-step-{street}")
                .style(
                    f"background:{bg};opacity:{opacity};"
                    "font-size:11px;text-transform:none"
                )
            )
            if not is_reachable:
                chip.props("disable")
            if street != _WT_STREETS[-1]:
                ui.label("->").style("color:var(--ps-text-fainter)")


def _render_freq_bars(
    state: AppState, freqs: dict[str, float], marker_prefix: str
) -> None:
    """Render an action -> probability bar block (reused preflop + flop)."""
    ui = _import_nicegui()
    for label, prob in sorted(freqs.items(), key=lambda kv: -float(kv[1])):
        bucket = classify_action(str(label))
        with ui.row().style("align-items:center;gap:8px;padding:3px 0").mark(
            f"{marker_prefix}-{label}"
        ):
            ui.label(str(label)).style(
                "width:90px;color:var(--ps-text-dim);"
                "font-family:Menlo,Consolas,monospace"
            )
            bar_width = 160
            fill_px = int(round(float(prob) * bar_width))
            anchor_rgb = {
                "fold": _COLOR_FOLD,
                "call": _COLOR_CALL,
                "raise": _COLOR_RAISE,
                "jam": _COLOR_JAM,
            }.get(bucket, _COLOR_NEUTRAL)
            anchor_css = f"rgb({anchor_rgb[0]},{anchor_rgb[1]},{anchor_rgb[2]})"
            with ui.element("div").style(
                f"width:{bar_width}px;height:12px;"
                f"background:var(--ps-track-bg);"
                f"border:1px solid var(--ps-border-soft);"
                f"position:relative"
            ):
                ui.element("div").style(
                    f"width:{fill_px}px;height:100%;background:{anchor_css}"
                )
            ui.label(f"{float(prob) * 100:.1f}%").style(
                "color:var(--ps-text-mono);font-family:Menlo,Consolas,monospace;"
                "width:60px;text-align:right"
            )


def _render_preflop_step(
    state: AppState, refresh_after_change: Callable[[], None]
) -> None:
    """Screen 1 — preflop decision node walkthrough."""
    ui = _import_nicegui()
    result = _chained_result(state)
    if result is None:
        return

    with (
        ui.element("div")
        .mark("chained-tab-step-panel chained-tab-postflop-display")
        .style(
            "background:var(--ps-strip-bg);padding:10px;border-radius:4px;"
            "border:1px solid var(--ps-border-strong)"
        )
    ):
        ui.label("Preflop").style(
            "font-weight:600;color:var(--ps-text);margin-bottom:4px"
        )

        hero_cls = _hero_class(state)
        if hero_cls is None:
            ui.label(
                "Pick your two hole cards above so we can show your "
                "class's GTO rec."
            ).style("color:var(--ps-text-muted);font-style:italic")
            return

        tokens = _wt_tokens(state)
        ui.label(f"Line so far: {format_action_sequence(tokens)}").style(
            "color:var(--ps-text-dim);font-family:Menlo,Consolas,monospace;"
            "font-size:11px;margin-bottom:6px"
        )

        game = _build_walk_game(state)
        if game is None:
            ui.label("Could not rebuild the preflop tree for this spot.").style(
                "color:var(--ps-text-error)"
            )
            return
        walk_state = _advance_to_tokens(game, tokens)
        if walk_state is None:
            ui.label(
                "The walked line is no longer legal — resetting to preflop."
            ).style("color:var(--ps-text-error)")
            return

        # If this line is a flop-reaching terminal, offer "deal the flop".
        if tokens in result.continuation_ranges:
            ui.label(
                "This line reaches the flop. Deal a board to continue."
            ).style("color:var(--ps-text);font-weight:600;margin:4px 0")

            def _to_flop(_e: Any = None) -> None:
                _set_wt_step(state, "flop")
                refresh_after_change()

            ui.button(
                "Deal the flop ->", on_click=_to_flop, icon="casino"
            ).props("color=primary").mark("chained-tab-legal-action-deal_flop")
            return

        # Terminal but NOT flop-reaching (fold / all-in run-out): terminate.
        if game.is_terminal(walk_state) or game.current_player(walk_state) == -1:
            ui.label(
                "This line ends preflop (a fold or all-in run-out) — no flop "
                "to walk."
            ).style("color:var(--ps-text-muted);font-style:italic;margin:4px 0")

            def _terminate(_e: Any = None) -> None:
                _set_wt_step(state, "done")
                refresh_after_change()

            ui.button(
                "See line summary", on_click=_terminate, icon="flag"
            ).props("flat").mark("chained-tab-legal-action-summary")
            return

        cur_player = game.current_player(walk_state)
        hero_player = int(getattr(state.current_spot, "hero_player", 0))
        is_hero_node = cur_player == hero_player

        if is_hero_node:
            ui.label(f"Your decision ({hero_cls}) — GTO rec:").style(
                "color:var(--ps-text);font-weight:600;margin:6px 0 2px"
            )
            try:
                rec = result.query(hero_cls, board=None)
            except (KeyError, ValueError):
                rec = {}
            if rec:
                _render_freq_bars(state, rec, "chained-tab-postflop-row")
            else:
                ui.label(
                    f"{hero_cls} has no preflop rec in this solve (it may be "
                    f"outside the hero range you solved)."
                ).style("color:var(--ps-text-muted);font-style:italic")
            ui.label("Your move:").style(
                "color:var(--ps-text-dim);font-size:11px;margin-top:6px"
            )
        else:
            ui.label("Villain to act — pick villain's action to advance:").style(
                "color:var(--ps-text-dim);font-size:11px;margin-top:6px"
            )

        options = _legal_action_options(game, walk_state)
        with ui.row().style("gap:6px;flex-wrap:wrap;margin-top:4px"):
            for token, label in options:

                def _pick(_e: Any = None, tok: str = token) -> None:
                    _set_wt_tokens(state, tokens + (tok,))
                    refresh_after_change()

                ui.button(label, on_click=_pick).props("flat dense").mark(
                    f"chained-tab-legal-action-{_slug(label)}"
                ).style("text-transform:none")

        if tokens:

            def _back(_e: Any = None) -> None:
                _set_wt_tokens(state, tokens[:-1])
                refresh_after_change()

            ui.button("Back", on_click=_back, icon="undo").props(
                "flat dense"
            ).style("margin-top:6px").mark("chained-tab-back")


def _render_flop_step(
    state: AppState, refresh_after_change: Callable[[], None]
) -> None:
    """Screen 2 — flop board pick + GUARDED solve + class-level flop rec."""
    ui = _import_nicegui()
    result = _chained_result(state)
    if result is None:
        return
    tokens = _wt_tokens(state)
    hero_cls = _hero_class(state)

    # Board picker.
    with (
        ui.element("div")
        .mark("chained-tab-board-picker")
        .style(
            "background:var(--ps-input-bg);padding:10px;border-radius:4px;"
            "border:1px solid var(--ps-border-soft);margin-bottom:10px"
        )
    ):
        ui.label("Flop board (pick 3)").style(
            "font-weight:600;color:var(--ps-text);margin-bottom:6px"
        )
        flop = _wt_flop(state)
        hole = _hole_cards(state)

        def _toggle_flop(card: Card) -> None:
            board = _wt_flop(state)
            if card in board:
                board.remove(card)
                _set_wt_flop(state, board)
                return
            if card in hole:
                ui.notify(
                    "That card is one of your hole cards.",
                    type="warning",
                    position="top",
                )
                return
            if len(board) >= 3:
                ui.notify(
                    "Flop is already 3 cards; remove one first.",
                    type="warning",
                    position="top",
                )
                return
            board.append(card)
            _set_wt_flop(state, board)

        _card_grid(
            state,
            selected=flop,
            cap=3,
            on_toggle=_toggle_flop,
            marker_prefix="chained-tab-board-cell",
            refresh_after_change=refresh_after_change,
        )

        def _clear() -> None:
            _set_wt_flop(state, [])
            refresh_after_change()

        ui.button("Clear board", icon="clear", on_click=_clear).props(
            "flat dense"
        ).mark("chained-tab-clear-board")

    # Flop strategy panel (guarded).
    with (
        ui.element("div")
        .mark("chained-tab-postflop-display")
        .style(
            "background:var(--ps-strip-bg);padding:10px;border-radius:4px;"
            "border:1px solid var(--ps-border-strong)"
        )
    ):
        ui.label("Flop strategy").style(
            "font-weight:600;color:var(--ps-text);margin-bottom:6px"
        )

        if hero_cls is None:
            ui.label("Pick your hole cards first.").style(
                "color:var(--ps-text-muted);font-style:italic"
            )
            return
        if tokens not in result.continuation_ranges:
            ui.label(
                "This preflop line does not reach the flop in the solve."
            ).style("color:var(--ps-text-muted);font-style:italic")
            return
        flop = _wt_flop(state)
        if len(flop) != 3:
            ui.label(
                f"Pick 3 flop cards above (currently {len(flop)}/3)."
            ).style("color:var(--ps-text-muted);font-style:italic")
            return

        # v1.11: no chained-flop tractability guard. The chained flop subgame
        # runs on main's fast engine (rayon + suit-iso + IE terminal eval), so
        # the GUI-branch ``chained_flop_too_large`` refusal — built against the
        # old engine where a wide flop hung for minutes in tree-build — is
        # removed.
        board_tuple = tuple(flop)
        try:
            rec = result.query(hero_cls, tokens, board_tuple)
        except (KeyError, ValueError) as exc:
            ui.label(f"Flop solve unavailable: {exc}").style(
                "color:var(--ps-text-muted);font-style:italic"
            )
            return
        except (RuntimeError, ImportError) as exc:
            logger.exception("chained flop solve raised: %s", exc)
            ui.label(
                "Couldn't solve this flop subgame right now. Try a different "
                "flop or preflop line; if it keeps happening, check the "
                "application logs for details."
            ).style("color:var(--ps-text-error)")
            return

        # Update the postflop route badge (polling tick picks up the change).
        from ui.blueprint_router import RouteInfo, SourceLabel

        runner = getattr(state, "runner", None)
        if runner is not None:
            runner.chained_postflop_route_info = RouteInfo(  # type: ignore[attr-defined]
                source=SourceLabel.LIVE,
                wall_time_s=0.0,
                confidence=f"live subgame ({len(tokens)}-token line)",
            )

        ui.label(
            f"{hero_cls} on {''.join(str(c) for c in board_tuple)} "
            f"after {format_action_sequence(tokens)}"
        ).style("color:var(--ps-text);font-weight:600;margin-bottom:6px")
        if rec:
            _render_freq_bars(state, rec, "chained-tab-postflop-row")
        else:
            ui.label(
                f"{hero_cls} is not in the flop continuation range (blocked by "
                f"the board or filtered out)."
            ).style("color:var(--ps-text-muted);font-style:italic")

        # Turn is Tier B.
        ui.label(
            "Turn / river are not yet chained on this engine."
        ).style("color:var(--ps-text-fainter);font-size:11px;margin-top:8px")

        def _to_turn(_e: Any = None) -> None:
            _set_wt_step(state, "turn")
            refresh_after_change()

        ui.button(
            "Turn (pending) ->", on_click=_to_turn, icon="hourglass_empty"
        ).props("flat dense").mark("chained-tab-legal-action-turn")


def _render_pending_step(state: AppState, street: str) -> None:
    """Screen 3+ — Tier-B turn/river placeholder. No compute."""
    ui = _import_nicegui()
    with (
        ui.element("div")
        .mark("chained-tab-pending-engine chained-tab-postflop-display")
        .style(
            "background:var(--ps-strip-bg);padding:14px;border-radius:4px;"
            "border:1px dashed var(--ps-border-strong)"
        )
    ):
        ui.label(f"{street.capitalize()} — pending fast engine").style(
            "font-weight:600;color:var(--ps-text);margin-bottom:6px"
        )
        ui.label(
            "Turn and river chaining is not yet implemented on this engine. "
            "The chained orchestrator (Phase A) only solves the flop subgame "
            "lazily; flop -> turn -> river chaining lands with the faster "
            "engine. Solve the flop above to study it for now."
        ).style("color:var(--ps-text-muted);font-style:italic")


def _render_termination(
    state: AppState, refresh_after_change: Callable[[], None]
) -> None:
    """Termination — summary strip of the walked path (fold / preflop end)."""
    ui = _import_nicegui()
    with (
        ui.element("div")
        .mark("chained-tab-postflop-display")
        .style(
            "background:var(--ps-strip-bg);padding:12px;border-radius:4px;"
            "border:1px solid var(--ps-border-strong)"
        )
    ):
        ui.label("Hand summary").style(
            "font-weight:600;color:var(--ps-text);margin-bottom:6px"
        )
        hero_cls = _hero_class(state)
        tokens = _wt_tokens(state)
        ui.label(f"Hero class: {hero_cls or '(none)'}").style(
            "color:var(--ps-text-dim)"
        )
        ui.label(f"Preflop line: {format_action_sequence(tokens)}").style(
            "color:var(--ps-text-dim);font-family:Menlo,Consolas,monospace"
        )
        last = tokens[-1] if tokens else ""
        if last == "f":
            ui.label("Result: a player folded — hand ends preflop.").style(
                "color:var(--ps-text);margin-top:4px"
            )
        else:
            ui.label("Result: line ended preflop (no flop reached).").style(
                "color:var(--ps-text);margin-top:4px"
            )

        def _restart(_e: Any = None) -> None:
            _set_wt_tokens(state, ())
            _set_wt_flop(state, [])
            _set_wt_step(state, "preflop")
            refresh_after_change()

        ui.button(
            "Walk again from preflop", on_click=_restart, icon="replay"
        ).props("flat").mark("chained-tab-restart")


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
    "token_label",
    "_DEFAULT_ITERATIONS",
]
