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
import re
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

# Ante selector options (Fix 2): BB-value -> user-facing label. The three
# values are exactly the precomputed blueprint shard cells (anteNone /
# anteHalf / anteFull). Insertion order is the dropdown order.
_ANTE_OPTIONS: dict[float, str] = {
    0.0: "None (0 bb)",
    0.5: "Half (0.5 bb)",
    1.0: "Full (1.0 bb)",
}


def _coerce_ante_bb(value: Any) -> float:
    """Map a selector value (or stored spot ante) to a valid ante-BB.

    Returns one of ``{0.0, 0.5, 1.0}`` (the blueprint shard cells); junk /
    out-of-set input falls back to ``0.0`` (None). Shared by the ante select's
    initial value and its change handler so the two never diverge.
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return v if v in _ANTE_OPTIONS else 0.0


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
# Preflop line (node) labels
# -----------------------------------------------------------------------------
#
# The engine emits strategy keys shaped ``"{hole_str}||p|<tokens>"``; the
# ``ui.state.SolveRunner.available_preflop_lines`` accessor returns the
# ``"||p|<tokens>"`` history suffix per reachable node. Token grammar
# (verified empirically against ``_rust.solve_hunl_preflop_rvr``):
#
#   ``||p|``                 root — SB's first decision           -> Open (RFI)
#   ``c``                    SB limps (call)
#   ``b<amt>``               a bet/open to <amt> (amt = BB * 100)
#   ``r<amt>``               a raise/re-raise to <amt>
#   ``A``                    facing an all-in (next actor folds/calls)
#
# The number of bet/raise tokens (``b``/``r``) is the "raise depth" and
# drives the poker line name. Standard HUNL counting: the open is the 1st
# bet, a re-raise is the 3-bet (3rd bet of the pot), the next is the 4-bet:
#
#   0 raises, no limp  -> Open (RFI)        (SB first-in decision)
#   leading ``c``      -> limped-pot variant (prefix "Limp:")
#   1 raise (``b``)    -> BB vs open        (BB facing the open)
#   2 raises (``r``)   -> 3-bet             (opener facing the re-raise)
#   3 raises (``r r``) -> 4-bet             (facing the 4-bet)
#   4+ raises          -> 5-bet+            (deep raise war)
#   trailing ``A``     -> append " (vs all-in)"
#
# If a suffix doesn't parse, we fall back to the raw suffix so the user can
# still select it rather than seeing nothing.

_LINE_TOKEN_RE = re.compile(r"c|b\d+|r\d+|A")
_ROOT_DEPTH_LABELS: dict[int, str] = {
    0: "Open (RFI)",
    1: "BB vs open",
    2: "3-bet",
    3: "4-bet",
}


def _line_body(suffix: str | None) -> str:
    """Strip the constant root marker (``||p|`` or normalized ``|p|``).

    Returns the post-marker token body (possibly empty for the root).
    Shared by :func:`preflop_line_label`, :func:`preflop_line_actor`, and
    :func:`_is_open_root_line` so they decode the suffix identically.
    """
    if suffix is None:
        return ""
    body = suffix
    if body.startswith("||p|"):
        body = body[len("||p|") :]
    elif body.startswith("|p|"):  # defensive: tolerate a normalized variant
        body = body[len("|p|") :]
    return body


def preflop_line_actor(suffix: str | None) -> str:
    """Return which player ACTS at node ``suffix`` — ``"SB"`` or ``"BB"``.

    Decodes the post-``||p|`` token body (``c``/``b<amt>``/``r<amt>``/``A``)
    and applies the engine's turn rule: the root (no tokens) is the SB's first
    decision, and play alternates with each token, so an EVEN token count means
    the SB acts and an ODD count means the BB acts. ``None`` / the bare root /
    an undecodable suffix all map to ``"SB"`` (the root actor).

    Engine-confirmed: the preflop root has ``cur_player == 0`` (SB).
    """
    body = _line_body(suffix)
    if body == "":
        return "SB"
    tokens = _LINE_TOKEN_RE.findall(body)
    # Undecodable grammar -> treat as the root actor so the badge still renders.
    if "".join(tokens) != body:
        return "SB"
    return "SB" if len(tokens) % 2 == 0 else "BB"


def preflop_line_label(
    suffix: str | None, *, allin_phrase: str = "(vs all-in)"
) -> str:
    """Map a raw Rust history suffix to a human-readable poker line name.

    ``suffix`` is an entry from
    ``ui.state.SolveRunner.available_preflop_lines`` (e.g. ``"||p|"`` for the
    root open, ``"||p|b200"`` for BB facing a 2bb open, ``"||p|b200r400"``
    for the opener facing a 3-bet). ``None`` or the bare root maps to
    "Open (RFI)".

    ``allin_phrase`` is appended (space-separated) when the line ends in an
    all-in token. It defaults to ``"(vs all-in)"`` (the historical wording);
    the line selector passes ``"— facing all-in (call/fold)"`` so the option
    reads unambiguously as "the actor's call/fold decision facing a shove"
    rather than the contradictory bare ``(vs all-in)``.

    Falls back to the raw suffix (wrapped) when the grammar can't be decoded
    so an unrecognized node is still selectable.
    """
    if suffix is None:
        return _ROOT_DEPTH_LABELS[0]
    body = _line_body(suffix)
    if body == "":
        return _ROOT_DEPTH_LABELS[0]

    tokens = _LINE_TOKEN_RE.findall(body)
    # Reject if the tokens don't reconstruct the body (unknown grammar).
    if "".join(tokens) != body:
        return f"Line: {suffix}"

    limp = bool(tokens) and tokens[0] == "c"
    facing_allin = bool(tokens) and tokens[-1] == "A"
    raise_depth = sum(1 for t in tokens if t and t[0] in "br")

    base = _ROOT_DEPTH_LABELS.get(raise_depth)
    if base is None:
        # 4+ raises: 4 raises -> 5-bet, 5 -> 6-bet, ...
        base = f"{raise_depth + 1}-bet"

    if limp and raise_depth == 0:
        # SB limped, no one has raised yet (BB's check/raise decision after
        # a limp), or SB's own decision facing nothing further.
        label = "Limped pot"
    elif limp:
        label = f"Limp: {base}"
    else:
        label = base

    if facing_allin:
        label = f"{label} {allin_phrase}"
    return label


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


def _available_lines(state: AppState) -> list[str]:
    """Return the available preflop action lines for the current result.

    Reads ``state.runner.available_preflop_lines()`` (sorted root-first).
    Returns ``[]`` when no result / no runner.
    """
    runner = getattr(state, "runner", None)
    if runner is None:
        return []
    getter = getattr(runner, "available_preflop_lines", None)
    if not callable(getter):
        return []
    try:
        lines = getter()
    except Exception:  # noqa: BLE001
        logger.exception("available_preflop_lines() raised")
        return []
    return list(lines) if isinstance(lines, list) else []


def _selected_line(state: AppState) -> str | None:
    """Return the currently-selected preflop line suffix (None = root).

    Stashed on ``state.prefs.preflop_chart_selected_line`` (non-persisted
    convenience slot, same pattern as the selected cell). Clamps to the root
    when the stored line is no longer available (e.g. after a re-solve with a
    different tree)."""
    prefs = getattr(state, "prefs", None)
    sel = getattr(prefs, "preflop_chart_selected_line", None) if prefs else None
    lines = _available_lines(state)
    if not lines:
        return sel  # nothing solved yet; keep whatever was stored
    if sel in lines:
        return sel
    return lines[0]  # default to root (sorted root-first)


def _set_selected_line(state: AppState, line: str | None) -> None:
    prefs = getattr(state, "prefs", None)
    if prefs is None:
        return
    prefs.preflop_chart_selected_line = line  # type: ignore[attr-defined]


def _is_open_root_line(suffix: str | None) -> bool:
    """True when ``suffix`` is the OPEN/root context (SB's first decision).

    The engine emits the root node as ``"||p|"`` (no action tokens after the
    constant ``||p|`` marker). At this node the SB has the option to *complete*
    the small blind — the engine labels that action ``"call"``, but in poker
    terms it is a **limp**, not a call. We use this to relabel ``call`` -> ``L``
    on the open chart while leaving genuine calls (facing a raise) as ``C``.

    ``None`` (nothing selected yet) is treated as the root, matching
    ``_selected_line``'s root-first default.
    """
    if suffix is None:
        return True
    return _line_body(suffix) == ""


def _line_chart_result(state: AppState) -> dict[str, Any] | None:
    """Return a chart_result-shaped dict for the SELECTED line.

    The grid + detail panel consume ``{"per_class": {...}, ...}``. The root
    line is already in ``preflop_chart_result["per_class"]``; for deeper
    lines we pull the per-class map via
    ``state.runner.preflop_chart_summary_for_line(line)`` and splice it onto
    a shallow copy so iteration/wallclock metadata still renders.

    Returns the unmodified root result when the selected line is the root or
    unavailable, ``None`` when there is no result at all.
    """
    result = _current_chart_result(state)
    if result is None:
        return None
    lines = _available_lines(state)
    sel = _selected_line(state)
    # Root (or single-line / unavailable) -> unchanged result.
    if not lines or sel is None or (lines and sel == lines[0]):
        return result
    runner = getattr(state, "runner", None)
    getter = getattr(runner, "preflop_chart_summary_for_line", None)
    if not callable(getter):
        return result
    try:
        per_class = getter(sel)
    except Exception:  # noqa: BLE001
        logger.exception("preflop_chart_summary_for_line(%r) raised", sel)
        return result
    if not isinstance(per_class, dict) or not per_class:
        # No data for this line — return a per_class-empty copy so the grid
        # paints neutral rather than silently showing the root range.
        spliced = dict(result)
        spliced["per_class"] = {}
        return spliced
    spliced = dict(result)
    spliced["per_class"] = per_class
    return spliced


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

    # N5: the header subtitle ("12 iters · 1.3s · done" / "Blueprint route" /
    # "no chart computed yet") must re-render on every solve, exactly like the
    # grid + source badge. It was previously a plain ``ui.label`` built once at
    # page-build time and never refreshed, so after a blueprint/interpolated
    # solve populated the grid and flipped the badge to "Blueprint · 100BB",
    # the subtitle stayed frozen on the stale empty-state text. Making it a
    # refreshable slot (driven by the same ``_refresh_all`` the grid/badge use)
    # ties it to the same source of truth.
    @ui.refreshable  # type: ignore[untyped-decorator]
    def _subtitle_slot() -> None:
        ui.label(_chart_subtitle(state)).mark("preflop-chart-subtitle").style(
            "color:var(--ps-text-muted);font-size:12px"
        )

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

    # Line/node selector: lets the user view deeper lines (BB vs open /
    # 3-bet / 4-bet) instead of only the open range. Refreshable so it
    # repopulates after a solve produces new lines.
    def _on_line_change(line: str | None) -> None:
        _set_selected_line(state, line)
        _refresh_all()

    @ui.refreshable  # type: ignore[untyped-decorator]
    def _line_selector_slot() -> None:
        _render_line_selector(state, _on_line_change)

    # Actor badge: a colored "<SB|BB> decides" chip directly above the grid so
    # the user can tell at a glance whose strategy the 13x13 grid is showing
    # for the currently-selected line. Refreshable so it tracks line changes.
    @ui.refreshable  # type: ignore[untyped-decorator]
    def _actor_badge_slot() -> None:
        _render_actor_badge(state)

    def _refresh_all() -> None:
        try:
            _subtitle_slot.refresh()
        except Exception:  # noqa: BLE001
            logger.exception("preflop chart subtitle refresh failed")
        try:
            _line_selector_slot.refresh()
        except Exception:  # noqa: BLE001
            logger.exception("preflop chart line selector refresh failed")
        try:
            _actor_badge_slot.refresh()
        except Exception:  # noqa: BLE001
            logger.exception("preflop chart actor badge refresh failed")
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
        .style(
            "background:var(--ps-panel-bg);padding:12px;"
            "border-radius:6px;width:100%"
        )
    ):
        with ui.row().style(
            "align-items:center;justify-content:space-between;margin-bottom:8px"
        ):
            ui.label("PREFLOP CHART").style(
                "font-weight:700;letter-spacing:0.05em;color:var(--ps-text-strong)"
            )
            _subtitle_slot()
        with ui.row().style("align-items:flex-start;gap:14px;flex-wrap:nowrap"):
            with ui.element("div").style(
                f"min-width:{_CELL_PX * 13 + 30}px;flex:0 0 auto"
            ):
                # Line/node selector sits above the grid so the user picks
                # which node (open / BB vs open / 3-bet / 4-bet) to view.
                _line_selector_slot()
                # Actor badge ("<SB|BB> decides") immediately above the grid,
                # colored per actor, so whose strategy the grid shows is
                # obvious at a glance.
                _actor_badge_slot()
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
    """Compose the small caption to the right of the chart heading.

    N5: the empty-state ("no chart computed yet") MUST agree with what the grid
    and source badge show. The grid paints from
    ``project_chart(_line_chart_result(state))`` and the badge from
    ``runner.preflop_route_info``; so we treat a chart as "present" exactly when
    that same projection is non-empty (covers blueprint, interpolated, AND live
    routes — every path that populates the grid sets ``preflop_chart_result``).
    Only when nothing has been computed do we show the genuine empty-state text.

    For a blueprint / interpolated route the engine reports ``iterations == 0``
    and ``wallclock_seconds == 0.0`` (no CFR was run), so the bare
    "0 iters · 0.0s" caption is misleading; surface the route source instead.
    The live path keeps the iters/wallclock summary.
    """
    chart_result = _current_chart_result(state)
    status = _chart_status(state)
    # Source of truth: does the grid actually have cells to paint?
    has_chart = bool(project_chart(_line_chart_result(state)))
    if not has_chart:
        if status == "running":
            return "solving... (chart will appear on completion)"
        return "no chart computed yet"
    iters = int((chart_result or {}).get("iterations", 0))
    wall = float((chart_result or {}).get("wallclock_seconds", 0.0))
    if iters <= 0:
        # Blueprint / interpolated route (no live CFR iterations) — describe the
        # route rather than report a misleading "0 iters · 0.0s".
        runner = getattr(state, "runner", None)
        info = getattr(runner, "preflop_route_info", None)
        source = getattr(info, "source", None)
        label = getattr(source, "value", None)
        if label:
            return f"{str(label).capitalize()} route"
        return "precomputed route"
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
        return "Unavailable · no runner"
    from ui.blueprint_router import SourceLabel, describe_route_badge

    info = getattr(runner, "preflop_route_info", None)
    badge = describe_route_badge(info)

    # Surface the custom-sizes consequence explicitly. The blueprint asset is
    # solved against the FIXED engine action menu (opens 2/3/4/5bb, reraise
    # ×2/3/4/5). The current dispatch keys the blueprint lookup on
    # (stack_bb, ante) ONLY — it does NOT pass the user's edited sizes — so:
    #   * if a LIVE solve is serving, the custom sizes ARE honored (good);
    #   * if a Blueprint/Interpolated route is serving, those custom sizes are
    #     being IGNORED — the chart reflects the default menu, not what the
    #     user typed. We must not let that be silent.
    bypass = _custom_sizes_bypass_label(state)
    if bypass is not None:
        source = getattr(info, "source", None)
        if source in (SourceLabel.BLUEPRINT, SourceLabel.INTERPOLATED):
            badge = f"{badge} · {bypass} ignored by blueprint (showing default menu)"
        else:
            # Live (or no route yet) — the live solve uses the custom sizes.
            badge = f"{badge} · {bypass} → live solve (blueprint bypassed)"
    return badge


def _custom_sizes_bypass_label(state: AppState) -> str | None:
    """Return a short label of WHICH sizes diverge from the engine defaults.

    e.g. ``"Custom open sizes"`` / ``"Custom reraise multipliers"`` /
    ``"Custom open sizes + reraise multipliers"``; ``None`` when defaults are
    in use. Reads the live open-size / reraise-multiplier input widgets
    stashed on ``state.current_spot`` at render time, falling back to the
    parsed pending lists on the runner when widgets aren't available.
    """
    from ui.blueprint_router import custom_sizes_bypass_note

    spot = getattr(state, "current_spot", None)
    runner = getattr(state, "runner", None)

    def _read(widget_attr: str, pending_attr: str) -> list[float] | None:
        widget = getattr(spot, widget_attr, None) if spot is not None else None
        raw = getattr(widget, "value", None) if widget is not None else None
        if isinstance(raw, str):
            try:
                return parse_size_list(raw)
            except ValueError:
                return None  # invalid input: don't claim a bypass
        pending = getattr(runner, pending_attr, None) if runner is not None else None
        if isinstance(pending, list):
            return [float(x) for x in pending]
        return None

    opens = _read("preflop_chart_opens", "_pending_preflop_chart_opens")
    mults = _read("preflop_chart_mults", "_pending_preflop_chart_mults")
    note = custom_sizes_bypass_note(
        open_sizes=opens,
        reraise_multipliers=mults,
        default_open_sizes=_DEFAULT_OPEN_SIZES_BB,
        default_reraise_multipliers=_DEFAULT_RERAISE_MULTIPLIERS,
    )
    if note is None:
        return None
    # custom_sizes_bypass_note returns "Custom <what> → live solve (...)";
    # strip the trailing clause so we can recompose the message with the
    # correct consequence for the actually-served route.
    return note.split(" → ", 1)[0]


def _badge_color(info: Any) -> str:
    """Color-code the source badge so the route is scannable at a glance.

    Greens for instant blueprint hits, yellow for interpolated, white
    for live (which the user expects to take seconds), grey when no
    route has been chosen yet.
    """
    if info is None:
        return "var(--ps-text-fainter)"
    from ui.blueprint_router import SourceLabel

    label = getattr(info, "source", None)
    if label == SourceLabel.BLUEPRINT:
        return "var(--ps-accent-ev)"
    if label == SourceLabel.INTERPOLATED:
        return "var(--ps-accent-warn)"
    if label == SourceLabel.LIVE:
        return "var(--ps-text-dim)"
    return "var(--ps-text-fainter)"


# Reworded all-in phrase shown in the line selector so "(vs all-in)" reads as
# the actor's call/fold decision facing a shove rather than a contradiction.
_SELECTOR_ALLIN_PHRASE = "— facing all-in (call/fold)"

# Theme-aware accents that distinguish the two actors at a glance. SB gets the
# cool/blue ``--ps-accent-reach``; BB gets the warm/amber ``--ps-accent-warn``.
# Both vars are defined for the dark AND light themes (ui/app.py CSS block).
_ACTOR_COLOR: dict[str, str] = {
    "SB": "var(--ps-accent-reach)",
    "BB": "var(--ps-accent-warn)",
}


def preflop_line_actor_color(actor: str) -> str:
    """Theme-aware accent color for an actor (``"SB"`` / ``"BB"``)."""
    return _ACTOR_COLOR.get(actor, "var(--ps-text)")


def _range_is_restricted(range_with_freqs: Any) -> bool:
    """True when ``range_with_freqs`` is a real restriction (not all-169).

    A restriction forces the live path (the blueprint asset is full-range
    only). Delegates to ``ui.app._range_is_effectively_full`` — the single
    source of truth for the full-vs-restricted decision — so the route
    predictor (iteration greying) and the engine dispatch
    (``ui.app._preflop_holes_from_range``) never disagree. A full (or
    effectively-full / empty) range is NOT a restriction; anything fewer is.
    """
    from ui.app import _range_is_effectively_full

    return not _range_is_effectively_full(range_with_freqs)


def _next_solve_hits_blueprint(state: AppState) -> bool:
    """Predict whether the NEXT Solve click would be served by the blueprint.

    The dispatch (``ui.app._on_preflop_chart_solve``) tries the blueprint
    first and only falls through to a live solve when a bypass is active:
    custom action sizes (``_custom_sizes_bypass_label``) OR a restricted
    Hero/Villain range. When NEITHER bypass applies the route attempts the
    blueprint (and the shipped Premium-A bundle covers the common depths), so
    the Iterations input is a no-op there. This drives the Fix-5 greying.

    Conservative: if either bypass is active we report ``False`` (live), so we
    never grey the Iterations input when it actually matters.
    """
    if _custom_sizes_bypass_label(state) is not None:
        return False
    spot = getattr(state, "current_spot", None)
    ranges = getattr(spot, "ranges", None) if spot is not None else None
    restricted = bool(ranges) and (
        _range_is_restricted(ranges[0]) or _range_is_restricted(ranges[1])
    )
    return not restricted


def _line_options(state: AppState) -> dict[str, str]:
    """Build the {suffix -> human label} option map for the line selector.

    Each label is prefixed with the acting player (``[SB]`` / ``[BB]``) so the
    user can tell whose strategy a line shows directly in the dropdown, and the
    all-in line is reworded via ``_SELECTOR_ALLIN_PHRASE`` so ``(vs all-in)`` no
    longer reads as a contradiction.

    Disambiguates collisions (two suffixes mapping to the same human label —
    e.g. multiple 3-bet sub-nodes) by appending the raw suffix so every
    option stays distinct and addressable.
    """
    lines = _available_lines(state)
    raw: list[tuple[str, str, str]] = [
        (ln, preflop_line_actor(ln), preflop_line_label(ln, allin_phrase=_SELECTOR_ALLIN_PHRASE))
        for ln in lines
    ]
    label_counts: dict[str, int] = {}
    for _, _actor, lab in raw:
        label_counts[lab] = label_counts.get(lab, 0) + 1
    options: dict[str, str] = {}
    for suffix, actor, lab in raw:
        if label_counts[lab] > 1:
            # Show the distinguishing token tail so duplicates are unique.
            tail = suffix[len("||p|") :] if suffix.startswith("||p|") else suffix
            options[suffix] = f"[{actor}] {lab}  ({tail or 'root'})"
        else:
            options[suffix] = f"[{actor}] {lab}"
    return options


def _render_actor_badge(state: AppState) -> None:
    """Render the colored "<SB|BB> decides" badge for the selected line.

    Makes whose strategy the grid shows unambiguous: at the open/root the SB
    decides; alternating per action thereafter (see :func:`preflop_line_actor`).
    The chip is tinted with the actor's theme-aware accent so SB vs BB reads at
    a glance, matching the ``[SB]``/``[BB]`` prefix in the line selector.
    """
    ui = _import_nicegui()
    actor = preflop_line_actor(_selected_line(state))
    color = preflop_line_actor_color(actor)
    full = "Small blind" if actor == "SB" else "Big blind"
    with (
        ui.element("div")
        .mark("preflop-chart-actor-badge")
        .style(
            "display:inline-flex;align-items:center;gap:6px;margin-bottom:6px;"
            f"padding:3px 10px;border-radius:10px;border:1px solid {color};"
            "background:var(--ps-strip-bg);font-size:11px;font-weight:700;"
            "letter-spacing:0.04em"
        )
    ):
        ui.element("div").style(
            f"width:8px;height:8px;border-radius:50%;background:{color}"
        )
        ui.label(f"{actor} decides").style(f"color:{color}")
        ui.label(f"({full} acts on this line)").style(
            "color:var(--ps-text-fainter);font-weight:400;letter-spacing:0"
        )


def _render_line_selector(
    state: AppState, on_change: Callable[[str | None], None]
) -> None:
    """Render the preflop line/node selector (dropdown).

    Lets the user switch the chart between the open range and deeper nodes
    (BB vs open / 3-bet / 4-bet / limped pots). Only renders meaningfully
    once a solve has produced more than the root line; before then it shows
    a quiet hint so the control's purpose is discoverable.
    """
    ui = _import_nicegui()
    options = _line_options(state)
    with (
        ui.element("div")
        .mark("preflop-chart-line-selector")
        .style("margin-bottom:8px;display:flex;align-items:center;gap:8px")
    ):
        ui.label("Line").style(
            "color:var(--ps-text-label);font-size:12px;font-weight:600;"
            "letter-spacing:0.03em"
        )
        if not options:
            ui.label("open only — solve to reveal deeper lines").style(
                "color:var(--ps-text-fainter);font-size:11px;font-style:italic"
            )
            return
        sel = _selected_line(state)
        if sel not in options:
            sel = next(iter(options))

        def _handle(e: Any) -> None:
            on_change(e.value)

        (
            ui.select(options=options, value=sel, on_change=_handle)
            .props("dense outlined options-dense")
            .style("min-width:220px;font-size:12px")
            .mark("preflop-chart-line-select")
        )
        if len(options) == 1:
            ui.label("(open only at this depth)").style(
                "color:var(--ps-text-fainter);font-size:11px;font-style:italic"
            )


def _render_grid(state: AppState) -> None:
    """Render the 13x13 cell grid (for the selected preflop line)."""
    ui = _import_nicegui()
    summaries = project_chart(_line_chart_result(state))
    # At the OPEN/root node the engine's "call" action is a *limp* (completing
    # the small blind), so the footer tag + tooltip read "L"/"Limp" there;
    # facing-action charts keep "C"/"Call" for a genuine call.
    is_open_root = _is_open_root_line(_selected_line(state))

    with ui.element("div").style(
        f"display:grid;grid-template-columns:repeat(13, {_CELL_PX}px);"
        f"gap:2px"
    ):
        for row in range(13):
            for col in range(13):
                cls = hand_class_at(row, col)
                summary = summaries.get(cls, CellSummary(label=cls, empty=True))
                _render_cell(state, cls, summary, is_open_root=is_open_root)


def _render_cell(
    state: AppState,
    hand_class: str,
    summary: CellSummary,
    *,
    is_open_root: bool = False,
) -> None:
    """Render a single matrix cell."""
    ui = _import_nicegui()
    color = cell_color_css(summary)
    # F04: empty cells fall back to a NEUTRAL grey anchor (``_COLOR_EMPTY``)
    # — re-route that to the theme var so an unsolved chart isn't dark-on-dark
    # in light mode. Non-empty cells keep their semantic fold/call/raise/jam
    # blend (``cell_color_rgb`` is unit-tested).
    if summary.empty:
        color = "var(--ps-faded)"
    tag = _cell_tag(summary, is_open_root=is_open_root)
    selected = _selected_cell_label(state) == hand_class
    border = "var(--ps-cell-border-sel)" if selected else "var(--ps-cell-border)"
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
        f"background:{color};color:var(--ps-cell-label);"
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
            "font-weight:600;line-height:1;color:var(--ps-cell-label)"
        )
        if tag:
            ui.label(tag).style(
                "font-family:Menlo,Consolas,monospace;font-size:9px;"
                "align-self:flex-end;color:var(--ps-cell-tag)"
            )
        ui.tooltip(_tooltip_text(hand_class, summary, is_open_root=is_open_root))


def _cell_tag(summary: CellSummary, *, is_open_root: bool = False) -> str:
    """Return the per-cell 1-letter+pct footer tag.

    On the OPEN/root chart (``is_open_root=True``) the engine's "call" action
    is a *limp* (completing the small blind), so it is tagged ``L`` rather than
    ``C``. Facing-action charts keep ``C`` for a genuine call.
    """
    if summary.empty:
        return ""
    kind = summary.dominant_kind
    pct = int(round(summary.dominant_prob * 100))
    call_letter = "L" if is_open_root else "C"
    letter = {"fold": "F", "call": call_letter, "raise": "R", "jam": "J"}.get(
        kind, ""
    )
    if not letter:
        return ""
    return f"{letter}{pct}"


def _tooltip_text(
    hand_class: str, summary: CellSummary, *, is_open_root: bool = False
) -> str:
    """Build the hover tooltip for one cell.

    On the OPEN/root chart the engine's "call" action is relabeled to
    "limp (complete the SB)" since completing the small blind is a limp, not a
    call; facing-action charts leave the raw "call" label untouched.
    """
    if summary.empty:
        return f"{hand_class}: no chart data"
    parts = [hand_class]
    for label, prob in sorted(summary.actions.items(), key=lambda kv: -kv[1]):
        pct = int(round(prob * 100))
        if is_open_root and label == "call":
            parts.append(f"limp (complete the SB) {pct}%")
        else:
            parts.append(f"{label} {pct}%")
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
            "background:var(--ps-input-bg);padding:10px;border-radius:4px;"
            "border:1px solid var(--ps-border-soft);margin-bottom:10px"
        )
    ):
        ui.label("Configure preflop solve").style(
            "font-weight:600;color:var(--ps-text);margin-bottom:8px"
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
            _sync_iter_route()
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
            _sync_iter_route()
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

        # Ante selector (None / Half / Full = 0 / 0.5 / 1.0 bb). The spot ante
        # feeds BOTH the blueprint router (it picks the matching precomputed
        # shard: anteNone / anteHalf / anteFull) AND the live HUNLConfig. Today
        # the panel had no ante control and the default ante is 0, so only the
        # no-ante chart was reachable here; this exposes all three.
        with ui.row().style("gap:8px;align-items:center"):
            current_ante = _coerce_ante_bb(getattr(spot, "ante", 0.0))
            ante_select = (
                ui.select(
                    options=dict(_ANTE_OPTIONS),
                    value=current_ante,
                    label="Ante",
                )
                .classes("w-40")
                .mark("preflop-chart-ante-select")
            )

            def _on_ante_change(e: Any) -> None:
                state.current_spot.ante = _coerce_ante_bb(e.value)
                # Editing the ante flips which blueprint shard is served (and
                # thus whether the iter input is a no-op) — re-sync the route.
                _sync_iter_route()
                refresh_after_change()

            ante_select.on_value_change(_on_ante_change)

        # Fix 5: when the next solve would be served from the (instant)
        # blueprint, iterations are ignored — grey the input + annotate so it
        # doesn't look broken. The annotation re-evaluates whenever the
        # range/size inputs change (those handlers call ``_sync_iter_route``).
        @ui.refreshable  # type: ignore[untyped-decorator]
        def _iter_hint_slot() -> None:
            if _next_solve_hits_blueprint(state):
                ui.label(
                    "Iterations ignored on the blueprint route — fixed. "
                    "Change bet sizes or ranges to solve live."
                ).mark("preflop-chart-iterations-hint").style(
                    "color:var(--ps-text-fainter);font-size:11px;"
                    "font-style:italic;margin-top:-4px;margin-bottom:4px"
                )

        def _sync_iter_route() -> None:
            """Grey/enable the Iterations input to match the predicted route."""
            blueprint = _next_solve_hits_blueprint(state)
            try:
                iter_input.set_enabled(not blueprint)
                # Visually grey when disabled so the no-op reads at a glance.
                iter_input.style(
                    "opacity:0.45" if blueprint else "opacity:1.0"
                )
            except Exception:  # noqa: BLE001
                logger.exception("preflop chart: iter route sync failed")
            try:
                _iter_hint_slot.refresh()
            except Exception:  # noqa: BLE001
                logger.exception("preflop chart: iter hint refresh failed")

        _iter_hint_slot()

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
            # Editing sizes may flip blueprint <-> live; re-grey iterations.
            _sync_iter_route()

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
            # Editing multipliers may flip blueprint <-> live; re-grey iters.
            _sync_iter_route()

        mults_input.on_value_change(_on_mults_change)

        # Stash the parsed action menu on the spot so the dispatch
        # handler in ``ui/app.py`` can read them at click time.
        # Lazy attribute assignment keeps the dataclass unchanged.
        state.current_spot.preflop_chart_opens = opens_input  # type: ignore[attr-defined]
        state.current_spot.preflop_chart_mults = mults_input  # type: ignore[attr-defined]

        # Now that the size widgets are stashed (so ``_custom_sizes_bypass_label``
        # can read them), set the initial Iterations greying to match the
        # predicted route. Subsequent edits re-sync via the change handlers.
        _sync_iter_route()

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
    chart_result = _line_chart_result(state)
    summaries = project_chart(chart_result)
    summary = summaries.get(selected or "") if selected else None

    with (
        ui.element("div")
        .mark("preflop-chart-detail")
        .style(
            "background:var(--ps-strip-bg);padding:10px;border-radius:4px;"
            "border:1px solid var(--ps-border-strong)"
        )
    ):
        if selected is None:
            ui.label("Click a cell to see per-action breakdown").style(
                "color:var(--ps-text-faint);font-style:italic"
            )
            return
        ui.label(f"Hand class: {selected}").style(
            "font-weight:600;color:var(--ps-text);margin-bottom:6px"
        )
        if summary is None or summary.empty:
            ui.label("No chart data for this class yet — run Solve.").style(
                "color:var(--ps-text-muted);font-style:italic"
            )
            return
        rows = build_detail_rows(summary)
        for r in rows:
            with ui.row().style(
                "align-items:center;gap:8px;padding:3px 0;"
            ).mark(f"preflop-chart-detail-row-{r.label}"):
                # Action label
                ui.label(r.label).style(
                    "width:90px;color:var(--ps-text-dim);"
                    "font-family:Menlo,Consolas,monospace"
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
                    f"background:var(--ps-track-bg);"
                    f"border:1px solid var(--ps-border-soft);"
                    f"position:relative"
                ):
                    ui.element("div").style(
                        f"width:{fill_px}px;height:100%;background:{anchor_css}"
                    )
                ui.label(f"{r.probability * 100:.1f}%").style(
                    "color:var(--ps-text-mono);font-family:Menlo,Consolas,monospace;"
                    "width:60px;text-align:right"
                )

        # EV line (when the chart_result carries per-class EV; PR #122
        # currently does not, so we render a placeholder.)
        ev_map = chart_result.get("per_class_ev", {}) if chart_result else {}
        if isinstance(ev_map, dict) and selected in ev_map:
            ev_val = float(ev_map[selected])
            ui.label(f"EV: {ev_val:+.2f} mBB").style(
                "color:var(--ps-accent-ev);font-family:Menlo,Consolas,monospace;"
                "margin-top:6px"
            ).mark(f"preflop-chart-detail-ev-{selected}")
        else:
            ui.label("EV: (not exported by engine in v1.x)").style(
                "color:var(--ps-text-fainter);font-style:italic;"
                "font-size:11px;margin-top:6px"
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
