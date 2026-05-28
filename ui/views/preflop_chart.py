"""Preflop chart widget (task #55).

Renders a 13x13 hand-class matrix of preflop action frequencies driven by
the engine binding ``_rust.solve_hunl_preflop_rvr`` (PR #122). Each cell
is keyed by its canonical Pio-convention hand class label (AA, AKs, AKo,
... 22) using the standard chart layout — pairs on the diagonal, suited
above-diagonal, offsuit below-diagonal, AA top-left, 22 bottom-right.

Layout contract (mirrors ``ui/views/range_matrix.py:_hand_class_at``):

         A   K   Q   J   T   9   8   7   6   5   4   3   2
     A  AA  AKs AQs AJs ATs A9s A8s A7s A6s A5s A4s A3s A2s
     K  AKo KK  KQs KJs KTs K9s K8s K7s K6s K5s K4s K3s K2s
     ...
     2  A2o K2o Q2o J2o T2o 92o 82o 72o 62o 52o 42o 32o 22

Each cell aggregates the per-action probabilities at the root decision
node (the SB's first action preflop) across the 4..12 concrete combos
that share the class, weighted by the engine-reported reach. The cell
is colored by the dominant action:

    raise (open / bet)     -> red       (RGB 220, 60, 60)
    raise (3-bet+)          -> dark red  (RGB 160, 30, 30)  ["jam" intensity]
    call (limp / flat)      -> yellow    (RGB 220, 200, 40)
    fold                    -> grey      (RGB 100, 100, 100)
    all-in                  -> dark red  (RGB 140, 20, 20)

Intensity scales with the dominant action's probability — fully saturated
when the action is pure, faded toward neutral grey as it mixes. Hover
shows the full action breakdown; click opens a side panel with per-action
bars and the engine-reported reach/EV (when available).

ElementFilter markers (task #55 smoke tests assert on these):
  ``preflop-chart-display``       outer container
  ``preflop-chart-cell``           all 169 cells
  ``preflop-chart-cell-{cls}``     per-class marker
  ``preflop-chart-detail``         side panel (post-click)
  ``preflop-chart-solve-button``   trigger
  ``preflop-chart-iterations``    iteration count input
  ``preflop-chart-open-sizes``    open-size action menu input
  ``preflop-chart-reraise-mults`` reraise-multiplier action menu input

The widget is engine-driven via PR #122; the dispatch path lives in
``ui/state.py:SolveRunner._run_preflop_chart_path`` (this PR adds it).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from poker_solver.card import RANKS

if TYPE_CHECKING:
    from ui.state import AppState

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Layout constants
# -----------------------------------------------------------------------------

# Top-left = A, bottom-right = 2 (mirror of ``range_matrix._GRID_RANKS``).
_GRID_RANKS: tuple[str, ...] = tuple(reversed(RANKS))  # ('A', 'K', ..., '2')

# Cell size (pixels). 38 lets the full 13x13 grid fit in ~520 px wide so
# the chart sits comfortably next to a 400 px side panel on 1024+ wide
# displays. Smaller than ``range_matrix._CELL_PX = 54`` because preflop
# cells only need the label + a one-letter action tag.
_CELL_PX: int = 38

# Color anchors (RGB) per task #55 spec.
_COLOR_FOLD: tuple[int, int, int] = (100, 100, 100)
_COLOR_CALL: tuple[int, int, int] = (220, 200, 40)
_COLOR_RAISE: tuple[int, int, int] = (220, 60, 60)
_COLOR_JAM: tuple[int, int, int] = (140, 20, 20)
_COLOR_NEUTRAL: tuple[int, int, int] = (40, 40, 40)
_COLOR_EMPTY: tuple[int, int, int] = (28, 28, 28)


# -----------------------------------------------------------------------------
# Cell aggregation
# -----------------------------------------------------------------------------


@dataclass
class CellSummary:
    """Per-cell aggregate of root-action probabilities.

    Buckets carry the raw engine action labels so the side panel can
    show the full breakdown without re-aggregating. ``dominant_label``
    is the highest-probability action; ``dominant_kind`` is the
    fold/call/raise/jam bucket that drives the cell color.
    """

    label: str = ""
    actions: dict[str, float] = field(default_factory=dict)
    dominant_label: str = ""
    dominant_kind: str = "empty"  # fold | call | raise | jam | empty
    dominant_prob: float = 0.0
    combo_count: int = 0
    empty: bool = False


def classify_action(label: str) -> str:
    """Bucket an engine action label into fold / call / raise / jam.

    The engine emits labels matching the action menu wired up in
    ``crates/cfr_core/src/preflop_rvr.rs`` (open_*, raise_*, fold, call,
    check, all_in). The bucket determines the cell color:

      * ``fold`` -> grey (no action mass)
      * ``call`` / ``check`` -> yellow (limp / flat)
      * ``open_*`` / ``raise_*`` / ``bet_*`` -> red (aggressive non-jam)
      * ``all_in`` / ``jam`` -> dark red (jam intensity)
    """
    norm = label.strip().lower()
    if norm == "fold":
        return "fold"
    if norm in ("check", "call"):
        return "call"
    if norm in ("all_in", "allin", "jam", "shove"):
        return "jam"
    # open_*, raise_*, bet_*, reraise_*, 3bet, 4bet -> "raise" bucket
    return "raise"


def aggregate_actions(actions: dict[str, float]) -> CellSummary:
    """Aggregate a raw action-probability dict into a ``CellSummary``.

    Normalizes the input to sum to 1.0 (defensive — engines may emit
    slightly off-normalized vectors from discounting). When the input
    is empty or sums to zero, returns an ``empty=True`` summary that
    the renderer paints neutral grey.
    """
    if not actions:
        return CellSummary(empty=True)
    total = sum(float(v) for v in actions.values())
    if total <= 0.0:
        return CellSummary(empty=True)
    normed = {k: float(v) / total for k, v in actions.items()}
    # Find the dominant action.
    dominant_label = max(normed, key=lambda k: normed[k])
    dominant_prob = normed[dominant_label]
    return CellSummary(
        actions=normed,
        dominant_label=dominant_label,
        dominant_kind=classify_action(dominant_label),
        dominant_prob=dominant_prob,
    )


def hand_class_at(row: int, col: int) -> str:
    """Return the canonical hand-class label at grid (row, col).

    Mirrors ``ui/views/range_matrix._hand_class_at`` so the two widgets
    share the same row-major + suited-above-diagonal convention.
    """
    hi = _GRID_RANKS[row]
    lo = _GRID_RANKS[col]
    if row == col:
        return f"{hi}{lo}"
    if col > row:  # above-diagonal -> suited
        return f"{hi}{lo}s"
    return f"{lo}{hi}o"  # below-diagonal -> offsuit (high rank first)


def cell_color_rgb(summary: CellSummary) -> tuple[int, int, int]:
    """Compute the cell background color from a ``CellSummary``.

    The color is the dominant-action anchor faded toward neutral grey by
    (1 - dominant_prob). Pure-strategy cells render at full saturation;
    near-50/50 cells fade halfway toward neutral. Empty cells render at
    the empty anchor.
    """
    if summary.empty:
        return _COLOR_EMPTY
    if summary.dominant_kind == "fold":
        anchor = _COLOR_FOLD
    elif summary.dominant_kind == "call":
        anchor = _COLOR_CALL
    elif summary.dominant_kind == "jam":
        anchor = _COLOR_JAM
    else:
        anchor = _COLOR_RAISE
    p = max(0.0, min(1.0, summary.dominant_prob))
    # Linear blend: result = anchor*p + neutral*(1-p)
    r = int(round(anchor[0] * p + _COLOR_NEUTRAL[0] * (1.0 - p)))
    g = int(round(anchor[1] * p + _COLOR_NEUTRAL[1] * (1.0 - p)))
    b = int(round(anchor[2] * p + _COLOR_NEUTRAL[2] * (1.0 - p)))
    return (r, g, b)


def cell_color_css(summary: CellSummary) -> str:
    """Compute the cell background CSS color string."""
    r, g, b = cell_color_rgb(summary)
    return f"rgb({r},{g},{b})"


# -----------------------------------------------------------------------------
# Per-class chart projection from the engine result
# -----------------------------------------------------------------------------


def project_chart(
    chart_result: dict[str, Any] | None,
) -> dict[str, CellSummary]:
    """Project the engine's flat strategy dict into per-class summaries.

    ``_rust.solve_hunl_preflop_rvr`` returns a dict with key
    ``"average_strategy"`` mapping ``"{hole}{key_suffix}" -> [probs]``;
    only entries whose ``key_suffix`` corresponds to the SB's first
    decision (root) are relevant for the chart. The chart_result wrapper
    that the worker stashes onto ``state`` already filters down to the
    root node and bucketed labels — see
    ``ui/state.py:SolveRunner._build_preflop_chart_summary``.

    Expected ``chart_result`` shape (set by the worker):
        {
          "per_class": {
              "AA": {"open_3": 0.05, "all_in": 0.95, "fold": 0.0, "call": 0.0},
              "AKs": {"open_3": 0.30, "open_4": 0.55, "fold": 0.15},
              ...
          },
          "actions": ["fold", "call", "open_2", "open_3", "open_4", "open_5", "all_in"],
          "iterations": 500,
          "wallclock_seconds": 12.3,
        }
    """
    out: dict[str, CellSummary] = {}
    if not chart_result:
        return out
    per_class = chart_result.get("per_class", {})
    if not isinstance(per_class, dict):
        return out
    for hand_class, action_map in per_class.items():
        if not isinstance(action_map, dict):
            continue
        summary = aggregate_actions({str(k): float(v) for k, v in action_map.items()})
        summary.label = str(hand_class)
        out[str(hand_class)] = summary
    return out


# -----------------------------------------------------------------------------
# Side-panel data
# -----------------------------------------------------------------------------


@dataclass
class DetailRow:
    """One row in the per-action breakdown panel."""

    label: str
    probability: float
    bucket: str  # fold | call | raise | jam


def build_detail_rows(summary: CellSummary) -> list[DetailRow]:
    """Build the ordered detail-panel rows for a cell click.

    Rows are sorted by probability descending. Bucket info lets the
    panel reuse the cell-color palette for the bars (visual consistency).
    """
    out: list[DetailRow] = []
    if summary.empty:
        return out
    items = sorted(summary.actions.items(), key=lambda kv: -kv[1])
    for label, prob in items:
        out.append(
            DetailRow(
                label=label,
                probability=float(prob),
                bucket=classify_action(label),
            )
        )
    return out


# -----------------------------------------------------------------------------
# Input control defaults — match PR #122 engine defaults bit for bit
# -----------------------------------------------------------------------------

_DEFAULT_ITERATIONS: int = 500
_DEFAULT_OPEN_SIZES_BB: tuple[float, ...] = (2.0, 3.0, 4.0, 5.0)
_DEFAULT_RERAISE_MULTIPLIERS: tuple[float, ...] = (2.0, 3.0, 4.0, 5.0)


def parse_size_list(value: str) -> list[float]:
    """Parse a comma-separated float list (action-menu input control).

    Empty or whitespace-only input returns an empty list (caller should
    fall back to engine defaults). Raises ``ValueError`` on garbage so
    the UI can surface a notify; bad characters are NOT silently
    dropped.
    """
    if not value or not value.strip():
        return []
    out: list[float] = []
    for tok in value.split(","):
        tok = tok.strip()
        if not tok:
            continue
        out.append(float(tok))  # raises ValueError on garbage
    return out


# -----------------------------------------------------------------------------
# NiceGUI rendering
# -----------------------------------------------------------------------------


def _import_nicegui() -> Any:
    """Late import keeps this module importable in unit tests without
    the ``[ui]`` optional extra installed."""
    from nicegui import ui as nicegui_ui

    return nicegui_ui


def _selected_cell_label(state: AppState) -> str | None:
    """Return the hand class currently selected on the detail panel.

    Stashed on ``state.prefs.preflop_chart_selected_class`` so cell
    clicks survive page refreshes (the field is non-persisted; living
    on prefs is just a convenient slot — we do NOT add it to the
    state.json schema).
    """
    prefs = getattr(state, "prefs", None)
    if prefs is None:
        return None
    return getattr(prefs, "preflop_chart_selected_class", None)


def _set_selected_cell_label(state: AppState, label: str | None) -> None:
    prefs = getattr(state, "prefs", None)
    if prefs is None:
        return
    prefs.preflop_chart_selected_class = label  # type: ignore[attr-defined]


def _current_chart_result(state: AppState) -> dict[str, Any] | None:
    """Return the active preflop-chart engine result (if any)."""
    runner = getattr(state, "runner", None)
    if runner is None:
        return None
    return getattr(runner, "preflop_chart_result", None)


def _chart_status(state: AppState) -> str:
    runner = getattr(state, "runner", None)
    if runner is None:
        return "idle"
    mode = getattr(runner, "_mode", "")
    if mode == "preflop_chart":
        return str(getattr(runner, "status", "idle"))
    return "idle"


def render(state: AppState, on_solve: Callable[[], None] | None = None) -> None:
    """Render the preflop chart widget into the current NiceGUI slot.

    Composes:
      1. A left-side 13x13 cell grid (the chart proper).
      2. A right-side input panel (range / iterations / action menu)
         and per-cell detail breakdown.

    ``on_solve`` is invoked when the user clicks the "Solve preflop
    chart" button; the caller (``ui/app.py:_on_preflop_chart_solve``)
    is responsible for kicking off the worker via
    ``state.runner.start(...)``.
    """
    ui = _import_nicegui()

    # The chart and the detail panel both need to re-render when the
    # engine result lands. ``@ui.refreshable`` gives us a cheap way to
    # force a redraw from the polling timer in ``ui/app.py``.

    @ui.refreshable  # type: ignore[untyped-decorator]
    def _grid_slot() -> None:
        _render_grid(state)

    @ui.refreshable  # type: ignore[untyped-decorator]
    def _detail_slot() -> None:
        _render_detail_panel(state)

    # Task #68 Phase 6: source-indicator badge slot. The badge text is
    # rebuilt from ``state.runner.preflop_route_info`` on each refresh
    # tick; we expose it as a separate refreshable so the polling timer
    # in ``ui/app.py`` can update the badge without re-rendering the
    # full grid (the badge changes more often than the grid does).
    @ui.refreshable  # type: ignore[untyped-decorator]
    def _source_badge_slot() -> None:
        text = _route_info_badge(state)
        info = getattr(getattr(state, "runner", None), "preflop_route_info", None)
        color = _badge_color(info)
        ui.label(text).mark("preflop-chart-source-badge").style(
            f"color:{color};font-family:Menlo,Consolas,monospace;"
            "font-size:11px;padding:4px 0"
        )

    def _refresh_all() -> None:
        try:
            _grid_slot.refresh()
        except Exception:  # noqa: BLE001
            logger.exception("preflop chart grid refresh failed")
        try:
            _detail_slot.refresh()
        except Exception:  # noqa: BLE001
            logger.exception("preflop chart detail refresh failed")
        try:
            _source_badge_slot.refresh()
        except Exception:  # noqa: BLE001
            logger.exception("preflop chart source badge refresh failed")

    with (
        ui.element("div")
        .mark("preflop-chart-display")
        .style("background:#0f0f0f;padding:12px;border-radius:6px;width:100%")
    ):
        with ui.row().style(
            "align-items:center;justify-content:space-between;margin-bottom:8px"
        ):
            ui.label("PREFLOP CHART").style(
                "font-weight:700;letter-spacing:0.05em;color:#f5f5f5"
            )
            ui.label(_chart_subtitle(state)).mark("preflop-chart-subtitle").style(
                "color:#aaaaaa;font-size:12px"
            )
        with ui.row().style("align-items:flex-start;gap:14px;flex-wrap:nowrap"):
            with ui.element("div").style(
                f"min-width:{_CELL_PX * 13 + 30}px;flex:0 0 auto"
            ):
                _grid_slot()
                # Source badge sits directly under the chart grid so the
                # user sees the route on the same eye-line as the data.
                _source_badge_slot()
            with ui.element("div").style(
                "flex:1 1 320px;min-width:320px;max-width:480px"
            ):
                _render_input_panel(state, on_solve, _refresh_all)
                _detail_slot()
    # Stash refresh helpers on state so the polling timer in
    # ``ui/app.py`` can re-trigger them when the worker finishes.
    runner = getattr(state, "runner", None)
    if runner is not None:
        runner._preflop_chart_refresh = _refresh_all  # type: ignore[attr-defined]


def _chart_subtitle(state: AppState) -> str:
    """Compose the small caption to the right of the chart heading."""
    chart_result = _current_chart_result(state)
    status = _chart_status(state)
    if chart_result is None:
        if status == "running":
            return "solving... (chart will appear on completion)"
        return "no chart computed yet"
    iters = int(chart_result.get("iterations", 0))
    wall = float(chart_result.get("wallclock_seconds", 0.0))
    return f"{iters} iters · {wall:.1f}s · {status}"


def _route_info_badge(state: AppState) -> str:
    """Task #68 Phase 6: source-indicator badge for the chart widget.

    Reads ``state.runner.preflop_route_info`` (populated by either
    :meth:`SolveRunner.try_blueprint_preflop_chart` for blueprint /
    interpolated routes or by :meth:`SolveRunner.start_preflop_chart`
    for the live path) and renders a one-line label.

    Falls back to an "unrouted" placeholder when no route info is
    present yet (chart hasn't been triggered).
    """
    runner = getattr(state, "runner", None)
    if runner is None:
        return "[unavailable] no runner"
    info = getattr(runner, "preflop_route_info", None)
    if info is None:
        return "[unrouted] click Solve to populate"
    from ui.blueprint_router import describe_route

    return describe_route(info)


def _badge_color(info: Any) -> str:
    """Color-code the source badge so the route is scannable at a glance.

    Greens for instant blueprint hits, yellow for interpolated, white
    for live (which the user expects to take seconds), grey when no
    route has been chosen yet.
    """
    if info is None:
        return "#7a7a7a"
    from ui.blueprint_router import SourceLabel

    label = getattr(info, "source", None)
    if label == SourceLabel.BLUEPRINT:
        return "#9ad29a"
    if label == SourceLabel.INTERPOLATED:
        return "#e0d27c"
    if label == SourceLabel.LIVE:
        return "#e8e8e8"
    return "#7a7a7a"


def _render_grid(state: AppState) -> None:
    """Render the 13x13 cell grid."""
    ui = _import_nicegui()
    summaries = project_chart(_current_chart_result(state))

    with ui.element("div").style(
        f"display:grid;grid-template-columns:repeat(13, {_CELL_PX}px);"
        f"gap:2px"
    ):
        for row in range(13):
            for col in range(13):
                cls = hand_class_at(row, col)
                summary = summaries.get(cls, CellSummary(label=cls, empty=True))
                _render_cell(state, cls, summary)


def _render_cell(state: AppState, hand_class: str, summary: CellSummary) -> None:
    """Render a single matrix cell."""
    ui = _import_nicegui()
    color = cell_color_css(summary)
    tag = _cell_tag(summary)
    selected = _selected_cell_label(state) == hand_class
    border = "#ffffff" if selected else "#1f1f1f"
    cell_marker = f"preflop-chart-cell preflop-chart-cell-{hand_class}"

    def _on_click(_event: object = None, cls: str = hand_class) -> None:
        _set_selected_cell_label(state, cls)
        try:
            # The detail-slot refresher was stashed by render() — call
            # it via the runner attribute so we don't need to plumb the
            # ``ui.refreshable`` handle through this closure.
            runner = getattr(state, "runner", None)
            if runner is not None and hasattr(runner, "_preflop_chart_refresh"):
                runner._preflop_chart_refresh()
        except Exception:  # noqa: BLE001
            logger.exception("preflop chart cell click handler raised")

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
    """Return the per-cell 1-letter+pct footer tag."""
    if summary.empty:
        return ""
    kind = summary.dominant_kind
    pct = int(round(summary.dominant_prob * 100))
    letter = {"fold": "F", "call": "C", "raise": "R", "jam": "J"}.get(kind, "")
    if not letter:
        return ""
    return f"{letter}{pct}"


def _tooltip_text(hand_class: str, summary: CellSummary) -> str:
    """Build the hover tooltip for one cell."""
    if summary.empty:
        return f"{hand_class}: no chart data"
    parts = [hand_class]
    for label, prob in sorted(summary.actions.items(), key=lambda kv: -kv[1]):
        parts.append(f"{label} {int(round(prob * 100))}%")
    return " · ".join(parts)


# -----------------------------------------------------------------------------
# Input panel + detail panel
# -----------------------------------------------------------------------------


def _render_input_panel(
    state: AppState,
    on_solve: Callable[[], None] | None,
    refresh_after_change: Callable[[], None],
) -> None:
    """Render the right-side input controls."""
    ui = _import_nicegui()

    with (
        ui.element("div")
        .mark("preflop-chart-input-panel")
        .style(
            "background:#181818;padding:10px;border-radius:4px;"
            "border:1px solid #2a2a2a;margin-bottom:10px"
        )
    ):
        ui.label("Configure preflop solve").style(
            "font-weight:600;color:#f0f0f0;margin-bottom:8px"
        )

        spot = state.current_spot
        # Hero range
        hero_range_str = spot.ranges[0].to_string() or "AA-22, AKs-A2s, AKo-A2o"
        hero_input = (
            ui.textarea(label="Hero range", value=hero_range_str)
            .classes("w-full font-mono text-xs")
            .mark("preflop-chart-hero-range")
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
            refresh_after_change()

        hero_input.on_value_change(_on_hero_range_change)

        # Villain range
        villain_range_str = spot.ranges[1].to_string() or "AA-22, AKs-A2s, AKo-A2o"
        villain_input = (
            ui.textarea(label="Villain range", value=villain_range_str)
            .classes("w-full font-mono text-xs")
            .mark("preflop-chart-villain-range")
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
            refresh_after_change()

        villain_input.on_value_change(_on_villain_range_change)

        # Stack depth (BB)
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
                .mark("preflop-chart-stack")
            )

            def _on_stack_change(e: Any) -> None:
                val = max(1, int(round(float(e.value))))
                state.current_spot.stacks_bb = (val, val)
                refresh_after_change()

            stack_input.on_value_change(_on_stack_change)

            iter_input = (
                ui.number(
                    label="Iterations",
                    value=_DEFAULT_ITERATIONS,
                    min=1,
                    max=100000,
                    step=50,
                )
                .classes("w-28")
                .mark("preflop-chart-iterations")
            )

            def _on_iter_change(e: Any) -> None:
                val = max(1, int(round(float(e.value))))
                state.current_spot.preflop_chart_iterations = val  # type: ignore[attr-defined]

            iter_input.on_value_change(_on_iter_change)

        # Action menu inputs (open sizes / reraise multipliers per #32).
        opens_default = ",".join(f"{x:g}" for x in _DEFAULT_OPEN_SIZES_BB)
        opens_input = (
            ui.input(
                label="Open sizes (BB, comma-separated)",
                value=opens_default,
            )
            .classes("w-full font-mono text-xs")
            .mark("preflop-chart-open-sizes")
        )

        def _on_opens_change(e: Any) -> None:
            try:
                parse_size_list(str(e.value))
            except ValueError as exc:
                ui.notify(
                    f"Invalid open sizes (need comma-separated floats): {exc}",
                    type="negative",
                    position="top",
                )

        opens_input.on_value_change(_on_opens_change)

        mults_default = ",".join(f"{x:g}" for x in _DEFAULT_RERAISE_MULTIPLIERS)
        mults_input = (
            ui.input(
                label="Reraise multipliers (× prev bet)",
                value=mults_default,
            )
            .classes("w-full font-mono text-xs")
            .mark("preflop-chart-reraise-mults")
        )

        def _on_mults_change(e: Any) -> None:
            try:
                parse_size_list(str(e.value))
            except ValueError as exc:
                ui.notify(
                    f"Invalid reraise multipliers (need comma-separated floats): {exc}",
                    type="negative",
                    position="top",
                )

        mults_input.on_value_change(_on_mults_change)

        # Stash the parsed action menu on the spot so the dispatch
        # handler in ``ui/app.py`` can read them at click time.
        # Lazy attribute assignment keeps the dataclass unchanged.
        state.current_spot.preflop_chart_opens = opens_input  # type: ignore[attr-defined]
        state.current_spot.preflop_chart_mults = mults_input  # type: ignore[attr-defined]

        # Solve button.
        def _click_solve() -> None:
            if on_solve is None:
                ui.notify(
                    "Preflop chart dispatch is not wired (callback missing).",
                    type="warning",
                    position="top",
                )
                return
            try:
                opens = parse_size_list(opens_input.value)
            except ValueError as exc:
                ui.notify(
                    f"Open sizes invalid: {exc}",
                    type="negative",
                    position="top",
                )
                return
            try:
                mults = parse_size_list(mults_input.value)
            except ValueError as exc:
                ui.notify(
                    f"Reraise multipliers invalid: {exc}",
                    type="negative",
                    position="top",
                )
                return
            # Stash the parsed lists onto the runner so the dispatch
            # path can pick them up without re-parsing.
            runner = getattr(state, "runner", None)
            if runner is not None:
                runner._pending_preflop_chart_opens = (  # type: ignore[attr-defined]
                    opens or list(_DEFAULT_OPEN_SIZES_BB)
                )
                runner._pending_preflop_chart_mults = (  # type: ignore[attr-defined]
                    mults or list(_DEFAULT_RERAISE_MULTIPLIERS)
                )
                runner._pending_preflop_chart_iterations = (  # type: ignore[attr-defined]
                    int(round(float(iter_input.value)))
                )
            on_solve()
            refresh_after_change()

        ui.button(
            "Solve preflop chart",
            on_click=_click_solve,
            icon="bolt",
        ).props("color=primary").classes("w-full mt-2").mark(
            "preflop-chart-solve-button"
        )


def _render_detail_panel(state: AppState) -> None:
    """Render the side panel showing the per-action breakdown for the
    currently-selected cell."""
    ui = _import_nicegui()
    selected = _selected_cell_label(state)
    chart_result = _current_chart_result(state)
    summaries = project_chart(chart_result)
    summary = summaries.get(selected or "") if selected else None

    with (
        ui.element("div")
        .mark("preflop-chart-detail")
        .style(
            "background:#1b1b1b;padding:10px;border-radius:4px;"
            "border:1px solid #303030"
        )
    ):
        if selected is None:
            ui.label("Click a cell to see per-action breakdown").style(
                "color:#9a9a9a;font-style:italic"
            )
            return
        ui.label(f"Hand class: {selected}").style(
            "font-weight:600;color:#f0f0f0;margin-bottom:6px"
        )
        if summary is None or summary.empty:
            ui.label("No chart data for this class yet — run Solve.").style(
                "color:#a8a8a8;font-style:italic"
            )
            return
        rows = build_detail_rows(summary)
        for r in rows:
            with ui.row().style(
                "align-items:center;gap:8px;padding:3px 0;"
            ).mark(f"preflop-chart-detail-row-{r.label}"):
                # Action label
                ui.label(r.label).style(
                    "width:90px;color:#e8e8e8;font-family:Menlo,Consolas,monospace"
                )
                # Bar
                bar_width = 160
                fill_px = int(round(r.probability * bar_width))
                anchor_rgb = {
                    "fold": _COLOR_FOLD,
                    "call": _COLOR_CALL,
                    "raise": _COLOR_RAISE,
                    "jam": _COLOR_JAM,
                }.get(r.bucket, _COLOR_NEUTRAL)
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
                ui.label(f"{r.probability * 100:.1f}%").style(
                    "color:#cccccc;font-family:Menlo,Consolas,monospace;"
                    "width:60px;text-align:right"
                )

        # EV line (when the chart_result carries per-class EV; PR #122
        # currently does not, so we render a placeholder.)
        ev_map = chart_result.get("per_class_ev", {}) if chart_result else {}
        if isinstance(ev_map, dict) and selected in ev_map:
            ev_val = float(ev_map[selected])
            ui.label(f"EV: {ev_val:+.2f} mBB").style(
                "color:#9ad29a;font-family:Menlo,Consolas,monospace;"
                "margin-top:6px"
            ).mark(f"preflop-chart-detail-ev-{selected}")
        else:
            ui.label("EV: (not exported by engine in v1.x)").style(
                "color:#7a7a7a;font-style:italic;font-size:11px;margin-top:6px"
            )


__all__ = [
    "CellSummary",
    "DetailRow",
    "aggregate_actions",
    "build_detail_rows",
    "cell_color_css",
    "cell_color_rgb",
    "classify_action",
    "hand_class_at",
    "parse_size_list",
    "project_chart",
    "render",
    "_DEFAULT_ITERATIONS",
    "_DEFAULT_OPEN_SIZES_BB",
    "_DEFAULT_RERAISE_MULTIPLIERS",
]
