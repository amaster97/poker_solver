"""Range matrix display (13x13 hand-class grid + combo inspector strip).

Per ``pr10a_spec.md`` §4.4 (mockup), §0.1 (locked decisions Q2/Q5), and
``pr10_spec.md`` §7.3 (color blend formula).

Locked design contract:
  * Q2: hand-class label visible in cell upper-left ("AKs", "QQ", "72o"),
    numeric frequencies revealed on hover only.
  * Q5: combo inspector strip rendered BELOW the matrix (full width),
    never to the right (right sidebar is reserved for Agent A's
    spot/run/tree expansion panels).
  * §7.3: additive RGB color blend (red=fold / yellow=call / green=raise)
    in the Pio convention so player muscle-memory carries over.
  * §3.3: blocker-removed cells render with a slashed overlay; out-of-
    range cells render faded grey with an em-dash glyph.

The matrix is the visual centerpiece of the UI (see
``competitor_ui_deep_dive.md`` §Synthesis "Top 3 patterns to adopt" #1
and ``ui_design_principles.md`` §3.1). Two on-cell signals per cell:
color blend + 2-letter+pct tag (R/C/F xx%, MIX, or BLK).

The aggregation function ``cell_strategy_summary`` is the single
load-bearing correctness item per spec §11 (combo -> cell mapping
must have no off-by-one). Agent C's smoke 7 gates this contract.

NiceGUI patterns are taken from the in-repo guide where applicable;
the ``@ui.refreshable`` pattern follows the v2.x docs.
"""

from __future__ import annotations

import contextlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

import numpy as np

from poker_solver.card import RANKS, Card
from poker_solver.hunl import HUNLState
from ui.views._cards import board_html

if TYPE_CHECKING:
    # Agent A owns ``ui.state``; we consume the contract documented in
    # ``docs/pr10_prep/agent_b_prompt.md`` §"Agent A's exports you depend
    # on". TYPE_CHECKING-only import keeps this module importable in
    # isolation (mypy still sees the types).
    from ui.state import AppState, RangeWithFreqs


# -- Hand-class label utility -------------------------------------------------
# The labels match Pio / GTOW / Monker / DeepSolver convention exactly (see
# ``competitor_ui_deep_dive.md`` §Synthesis "Common patterns across all 4"
# #1). The 13x13 grid is row-major with row 0 = A and row 12 = 2; the same
# semantics are produced by Agent A's ``enumerate_hand_classes``. Suited
# combos sit above the diagonal (col > row), offsuit below (col < row),
# pairs on the diagonal.

# Ace-high-first rank ordering for the 13x13 grid.
_GRID_RANKS: tuple[str, ...] = tuple(reversed(RANKS))  # ('A', 'K', ..., '2')


def _rank_char(rank_value: int) -> str:
    """Map a 2..14 rank int to its display character."""

    return RANKS[rank_value - 2]


def _hand_class_for_combo(card1: Card, card2: Card) -> str:
    """Return the hand-class shorthand label that owns a combo.

    Mirrors the contract documented for Agent A's ``classify_combo``. The
    round-trip ``combo in enumerate_combos(_hand_class_for_combo(*combo))``
    is preserved.
    """

    r1, r2 = card1.rank, card2.rank
    s1, s2 = card1.suit, card2.suit
    if r1 == r2:
        return f"{_rank_char(r1)}{_rank_char(r2)}"
    hi, lo = (r1, r2) if r1 > r2 else (r2, r1)
    suffix = "s" if s1 == s2 else "o"
    return f"{_rank_char(hi)}{_rank_char(lo)}{suffix}"


def _hand_class_at(row: int, col: int) -> str:
    """Return the hand-class label at grid position ``(row, col)``.

    Grid layout (locked per spec §3.3 + ``pr10a_spec.md`` §4.4):
      * top-left = AA, bottom-right = 22.
      * pairs on the diagonal.
      * suited above-diagonal (col > row).
      * offsuit below-diagonal (col < row).
    """

    hi = _GRID_RANKS[row]
    lo = _GRID_RANKS[col]
    if row == col:
        return f"{hi}{lo}"
    if col > row:  # above-diagonal -> suited
        return f"{hi}{lo}s"
    return f"{lo}{hi}o"  # below-diagonal -> offsuit (high rank first)


def _enumerate_combos_for_class(hand_class: str) -> list[tuple[Card, Card]]:
    """Enumerate every card-pair owned by ``hand_class``.

    A pair "XX" has 6 combos; a suited "XYs" has 4; an offsuit "XYo" has
    12. Total across the 169 classes = 13*6 + 78*4 + 78*12 = 1326.
    Mirrors Agent A's ``enumerate_combos`` contract.
    """

    if len(hand_class) == 2:
        # Resolve rank via the canonical map; avoids ASCII traps.
        rv = _rank_str_to_int(hand_class[0])
        combos: list[tuple[Card, Card]] = []
        for s1 in range(4):
            for s2 in range(s1 + 1, 4):
                combos.append((Card(rv, s1), Card(rv, s2)))
        return combos

    hi = _rank_str_to_int(hand_class[0])
    lo = _rank_str_to_int(hand_class[1])
    suited = hand_class[2] == "s"
    combos = []
    if suited:
        for s in range(4):
            combos.append((Card(hi, s), Card(lo, s)))
    else:
        for s1 in range(4):
            for s2 in range(4):
                if s1 == s2:
                    continue
                combos.append((Card(hi, s1), Card(lo, s2)))
    return combos


def _rank_str_to_int(c: str) -> int:
    return RANKS.index(c.upper()) + 2


# -- Cell aggregation ---------------------------------------------------------


@dataclass
class CellSummary:
    """Per-cell aggregated strategy summary (color + tooltip + tag).

    Fields are aggregate probabilities across the surviving combos in a
    hand class, weighted by ``RangeWithFreqs.frequency_of(combo)``. When
    every combo of a class is blocked by the board the cell renders as
    ``blocked``; when total weight is 0 the cell renders as
    ``out_of_range`` (faded grey em-dash per spec §3.3).

    ``avg_weight`` (B10 Phase C) is the mean per-combo intensity across
    the surviving (non-blocker) combos in the class. All-1.0 ranges have
    ``avg_weight == 1.0``; a class with two combos at 1.0 and two at 0.0
    contributes ``avg_weight == 0.5``. The matrix renderer fades the
    cell color toward grey when this value drops below 1.0 so users can
    see fractional ranges at a glance.
    """

    fold: float = 0.0
    call: float = 0.0
    raise_: float = 0.0
    combo_count: int = 0
    blocked: bool = False
    empty: bool = False
    out_of_range: bool = False
    # True when ANY combo in the class is board-blocked, even if other
    # combos survive (smoke 15 / pr10a_spec.md §10.3 item 15).
    has_blocker: bool = False
    # B10 Phase C: avg per-combo weight across survivors; used by
    # ``cell_color`` to fade fractional ranges toward grey.
    avg_weight: float = 1.0


# Duck-typed snapshot interface (see prompt comment): ``infoset_key`` is
# computed off the underlying ``HUNLState``; the snapshot carries the
# state plus the ``player_to_act``. We accept ``HUNLState`` directly OR
# any object with ``.state`` + ``.player_to_act``.


def _snapshot_state(snapshot: object) -> HUNLState | None:
    if isinstance(snapshot, HUNLState):
        return snapshot
    state = getattr(snapshot, "state", None)
    if isinstance(state, HUNLState):
        return state
    # ``tree_browser.TreeNode`` carries the per-node game state under
    # ``state_snapshot`` (not ``state``). Selecting a decision-tree node
    # hands one of those nodes through ``_current_tree_snapshot`` so the
    # matrix can project that node's infoset — without this branch the
    # off-/on-path projection would silently fall back to the root state.
    node_snapshot = getattr(snapshot, "state_snapshot", None)
    if isinstance(node_snapshot, HUNLState):
        return node_snapshot
    return None


def _snapshot_player(snapshot: object) -> int:
    player = getattr(snapshot, "player_to_act", None)
    if isinstance(player, int):
        return player
    state = _snapshot_state(snapshot)
    if state is not None:
        return state.cur_player
    return 0


def _snapshot_legal_actions(snapshot: object) -> tuple[int, ...]:
    actions = getattr(snapshot, "legal_actions", None)
    if isinstance(actions, (tuple, list)):
        return tuple(int(a) for a in actions)
    state = _snapshot_state(snapshot)
    if state is None:
        return ()
    # Fall back to HUNLPoker if we have a state but no cached actions.
    from poker_solver.hunl import HUNLPoker

    return tuple(HUNLPoker(state.config).legal_actions(state))


def _aggregate_action_buckets(
    legal_actions: Sequence[int],
    probs: Sequence[float] | np.ndarray,
) -> tuple[float, float, float]:
    """Bucket a per-action strategy vector into (fold, call, raise) totals.

    The HUNL action enum (see ``poker_solver/action_abstraction.py``):
      * ACTION_FOLD = 0
      * ACTION_CHECK = 1, ACTION_CALL = 2 -> "call/check" bucket
      * ACTION_BET_* = 3..7, ACTION_RAISE_* = 8..12, ACTION_ALL_IN = 13
        -> "raise/bet" bucket
    The buckets line up with the Pio R/Y/G strategy palette (red=fold,
    yellow=call/check, green=raise/bet).
    """

    fold = call = rais = 0.0
    for action, p in zip(legal_actions, probs):
        if action == 0:
            fold += float(p)
        elif action in (1, 2):
            call += float(p)
        else:
            rais += float(p)
    return fold, call, rais


def cell_strategy_summary(
    hand_class: str,
    range_: RangeWithFreqs,
    board: Sequence[Card],
    strategy: dict[str, np.ndarray],
    tree_node_id: str,
    game_state_snapshot: object,
) -> CellSummary:
    """Compute the cell-aggregate strategy summary for one hand class.

    Per spec §7.2 pseudocode:
      1. enumerate every combo in ``hand_class``;
      2. filter out combos whose cards collide with the board;
      3. for each survivor, build its infoset key from the game-state
         snapshot and look up the strategy vector;
      4. aggregate fold/call/raise probabilities weighted by
         ``range_.frequency_of(combo)``, then normalize.
    """

    # ``tree_node_id`` is conceptually informative but unused at this
    # level — the strategy dict + state snapshot together fully specify
    # the infoset for each combo. Keep the argument so callers don't
    # have to special-case the root vs deeper nodes.
    del tree_node_id

    state = _snapshot_state(game_state_snapshot)
    player = _snapshot_player(game_state_snapshot)
    legal_actions = _snapshot_legal_actions(game_state_snapshot)

    board_cards = set(board)
    summary = CellSummary()
    combos = _enumerate_combos_for_class(hand_class)
    if not combos:
        summary.empty = True
        summary.out_of_range = True
        return summary

    total_weight = 0.0
    weighted_fold = weighted_call = weighted_raise = 0.0
    survivors = 0
    in_range_total = 0
    all_blocked = True
    survivor_weight_sum = 0.0  # B10 Phase C: track raw weights of survivors

    for combo in combos:
        weight = float(range_.frequency_of(combo))
        if weight <= 0.0:
            continue
        in_range_total += 1
        if combo[0] in board_cards or combo[1] in board_cards:
            summary.has_blocker = True
            continue
        all_blocked = False
        survivors += 1
        survivor_weight_sum += weight
        if state is None or not legal_actions:
            # No game-state context -> can only report combo count.
            total_weight += weight
            continue
        probs = _strategy_for_combo(strategy, state, combo, player, legal_actions)
        if probs is None:
            total_weight += weight
            continue
        f, c, r = _aggregate_action_buckets(legal_actions, probs)
        weighted_fold += weight * f
        weighted_call += weight * c
        weighted_raise += weight * r
        total_weight += weight

    if in_range_total == 0:
        summary.empty = True
        summary.out_of_range = True
        return summary
    if all_blocked:
        summary.blocked = True
        summary.combo_count = 0
        return summary
    summary.combo_count = survivors
    # B10 Phase C: mean per-combo weight across survivors. By construction
    # ``0 < survivor_weight_sum`` here (every survivor contributed
    # ``weight > 0``), so the divide is safe. All-1.0 ranges yield 1.0.
    if survivors > 0:
        summary.avg_weight = max(0.0, min(1.0, survivor_weight_sum / survivors))
    if total_weight > 0.0:
        summary.fold = weighted_fold / total_weight
        summary.call = weighted_call / total_weight
        summary.raise_ = weighted_raise / total_weight
    return summary


def _strategy_for_combo(
    strategy: dict[str, np.ndarray],
    state: HUNLState,
    combo: tuple[Card, Card],
    player: int,
    legal_actions: Sequence[int],
) -> np.ndarray | None:
    """Look up the strategy vector for one combo at the current node.

    Builds the infoset key via the canonical ``HUNLPoker.infoset_key``
    helper, substituting ``combo`` as the player's hole cards. Returns
    ``None`` when the strategy dict has no entry for the key (an unseen
    branch; the matrix renders the cell as if the combo were uniform).
    """

    from poker_solver.hunl import HUNLPoker

    # Replace the relevant hole card slot with the combo we're asking
    # about. The opponent's hole cards are irrelevant to the infoset
    # key (poker is hidden-info).
    hole_template: tuple[tuple[Card, Card], tuple[Card, Card]]
    existing = state.hole_cards
    if existing and len(existing) == 2:
        existing_player = existing[player]
        existing_opp = existing[1 - player]
        if player == 0:
            hole_template = (combo, existing_opp)
        else:
            hole_template = (existing_player, combo)
    else:
        # No hole cards in state — fabricate a placeholder for the
        # opponent. Two arbitrary unused cards suffice for the lossless
        # infoset path (opponent slot does not enter the key).
        placeholder = _placeholder_opponent_cards(state.board, combo)
        hole_template = (combo, placeholder) if player == 0 else (placeholder, combo)

    probe_state = state.__class__(
        hole_cards=hole_template,
        board=state.board,
        street=state.street,
        contributions=state.contributions,
        stacks=state.stacks,
        street_history=state.street_history,
        street_aggressor=state.street_aggressor,
        street_num_raises=state.street_num_raises,
        to_call=state.to_call,
        cur_player=state.cur_player,
        folded=state.folded,
        all_in=state.all_in,
        config=state.config,
        betting_tokens=state.betting_tokens,
        current_street_tokens=state.current_street_tokens,
        pending_board_deals=state.pending_board_deals,
    )
    key = HUNLPoker(state.config).infoset_key(probe_state, player)
    entry = strategy.get(key)
    if entry is None:
        return None
    arr = np.asarray(entry, dtype=float)
    if arr.shape[0] != len(legal_actions):
        return None
    return arr


def _placeholder_opponent_cards(
    board: Sequence[Card], combo: tuple[Card, Card]
) -> tuple[Card, Card]:
    """Return two arbitrary cards not used by ``board`` or ``combo``."""

    used = set(board) | set(combo)
    chosen: list[Card] = []
    for rank in range(2, 15):
        for suit in range(4):
            c = Card(rank, suit)
            if c in used:
                continue
            chosen.append(c)
            if len(chosen) == 2:
                return (chosen[0], chosen[1])
    # Fallback (deck always has enough; only triggered on a malformed
    # state with the full deck in use).
    return combo  # pragma: no cover


# -- Color blend --------------------------------------------------------------


def cell_color(summary: CellSummary) -> str:
    """Pio-convention additive RGB color blend.

    Per ``pr10_spec.md`` §7.3:
        r = fold*220 + call*220 + raise_*40
        g = fold*40  + call*200 + raise_*180
        b = fold*40  + call*40  + raise_*60
    Blocked / empty / out-of-range cells return the faded-grey sentinel.

    B10 Phase C: when ``summary.avg_weight < 1.0`` the cell saturates
    toward the faded-grey sentinel (``#3a3a3a``, ~``(58, 58, 58)``)
    proportionally — a fully grey cell at ``avg_weight == 0`` and the
    canonical Pio blend at ``avg_weight == 1.0``. All-1.0 ranges are
    bit-for-bit back-compatible with PR 10's locked palette.
    """

    if summary.blocked or summary.out_of_range or summary.empty:
        return "#3a3a3a"
    r = summary.fold * 220 + summary.call * 220 + summary.raise_ * 40
    g = summary.fold * 40 + summary.call * 200 + summary.raise_ * 180
    b = summary.fold * 40 + summary.call * 40 + summary.raise_ * 60
    # B10 Phase C: lerp toward the grey sentinel by (1 - avg_weight).
    # Clamp defensively in case a caller hands us a stale CellSummary
    # with an out-of-band value.
    intensity = max(0.0, min(1.0, summary.avg_weight))
    if intensity < 1.0:
        grey = 58.0  # matches the ``#3a3a3a`` blocked sentinel.
        r = r * intensity + grey * (1.0 - intensity)
        g = g * intensity + grey * (1.0 - intensity)
        b = b * intensity + grey * (1.0 - intensity)
    return f"rgb({int(r)},{int(g)},{int(b)})"


# Pure-Pio R/Y/G anchors used by the palette-audit smoke test.
# Per pr10a_spec.md §7.3:
#   fold  → red    (255, 0,   0)
#   call  → yellow (255, 255, 0)
#   raise → green  (0,   255, 0)
# Distinct from the `cell_color()` fade anchors above; the smoke test
# guards the convention surface so downstream consumers (export, image
# diff, doc screenshots) can rely on pure anchors.
DISPLAY_PALETTE: tuple[
    tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]
] = (
    (255, 0, 0),
    (255, 255, 0),
    (0, 255, 0),
)


def cell_rgb_for_action_freqs(
    fold: float, call: float, raise_: float
) -> tuple[int, int, int]:
    """Return the additive-Pio-blend RGB for a cell's action frequencies.

    Adapter exposed for the palette-audit smoke test (smoke 14). Uses the
    pure RYG anchors from ``DISPLAY_PALETTE`` rather than the fade anchors
    inside ``cell_color()`` — see module docstring + ``pr10a_spec.md`` §7.3.

    :param fold: probability mass on fold (0..1).
    :param call: probability mass on call (0..1).
    :param raise_: probability mass on raise (0..1).
    :returns: ``(r, g, b)`` int triple, each channel clamped 0..255.
    """
    red, yellow, green = DISPLAY_PALETTE
    r = fold * red[0] + call * yellow[0] + raise_ * green[0]
    g = fold * red[1] + call * yellow[1] + raise_ * green[1]
    b = fold * red[2] + call * yellow[2] + raise_ * green[2]
    return (
        max(0, min(255, int(round(r)))),
        max(0, min(255, int(round(g)))),
        max(0, min(255, int(round(b)))),
    )


def _cell_tag(summary: CellSummary) -> str:
    """Return the 2-letter + percentage tag rendered in the cell footer.

    Per ``pr10a_spec.md`` §4.4:
      * "R xx%" / "C xx%" / "F xx%" when the dominant action > 50%;
      * "MIX" when no action exceeds 50%;
      * "BLK" when every combo is board-blocked.
    """

    if summary.blocked:
        return "BLK"
    if summary.out_of_range or summary.empty:
        return ""
    pct_raise = int(round(summary.raise_ * 100))
    pct_call = int(round(summary.call * 100))
    pct_fold = int(round(summary.fold * 100))
    if summary.raise_ >= 0.5:
        return f"R {pct_raise}%"
    if summary.call >= 0.5:
        return f"C {pct_call}%"
    if summary.fold >= 0.5:
        return f"F {pct_fold}%"
    return "MIX"


def _tooltip_text(hand_class: str, summary: CellSummary) -> str:
    """Build the hover tooltip per spec §3.3 (numbers-always-visible-
    on-hover principle, locked in ``ui_design_principles.md`` §2.5)."""

    if summary.blocked:
        return f"{hand_class}: all combos blocked by board"
    if summary.out_of_range or summary.empty:
        return f"{hand_class}: out of range"
    return (
        f"{hand_class} ({summary.combo_count} combos): "
        f"{int(round(summary.raise_ * 100))}% raise · "
        f"{int(round(summary.call * 100))}% call · "
        f"{int(round(summary.fold * 100))}% fold"
    )


# -- NiceGUI rendering --------------------------------------------------------
# Pattern: ``@ui.refreshable`` wraps a view function so re-renders push a
# fresh DOM subtree on demand. Pattern from in-repo NiceGUI guide
# (mental model 8 — refreshable elements).


def _import_nicegui() -> Any:
    """Late import of NiceGUI so this module can be imported in tests
    without the ``[ui]`` optional extra installed."""

    from nicegui import ui as nicegui_ui

    return nicegui_ui


def _safe_state_field(state: AppState, attr: str, default: Any) -> Any:
    """Return ``getattr(state, attr)`` falling back gracefully to
    ``default``. We never depend on Agent A's exact field names beyond
    the contract surface; this guards against minor drift."""

    value = getattr(state, attr, None)
    if value is None:
        return default
    return value


def _current_range(state: AppState, player: int) -> RangeWithFreqs | None:
    spot = _safe_state_field(state, "current_spot", None)
    if spot is None:
        return None
    ranges = getattr(spot, "ranges", None)
    if ranges is None or len(ranges) <= player:
        return None
    result: RangeWithFreqs | None = ranges[player]
    return result


def _current_board(state: AppState) -> Sequence[Card]:
    spot = _safe_state_field(state, "current_spot", None)
    if spot is None:
        return ()
    board = getattr(spot, "board", ())
    return tuple(board)


def _current_strategy(state: AppState) -> dict[str, np.ndarray]:
    # Resolve the finished solve's strategy. A ``SolveSession`` carries no
    # ``result`` of its own (the result lives on the runner it references),
    # so we look on the session first (future-proof) then fall back to the
    # runner directly — including when ``current_solve`` is None, so the
    # matrix still projects whenever the runner holds a finished result
    # (mirrors how ``_resolve_tree`` builds the tree straight off the
    # runner). Without the unconditional runner fallback the node->matrix
    # projection went blank whenever ``current_solve`` wasn't set.
    solve = _safe_state_field(state, "current_solve", None)
    runner = _safe_state_field(state, "runner", None)
    result = getattr(solve, "result", None) if solve is not None else None
    if result is None:
        result = getattr(runner, "result", None)
    if result is None:
        return {}
    raw = getattr(result, "average_strategy", {})
    return {str(k): np.asarray(v, dtype=float) for k, v in raw.items()}


def _resolve_tree(state: AppState) -> object | None:
    """Best-effort retrieval of the live ``SolveTree`` for the current solve.

    Resolution order mirrors ``tree_browser._resolve_tree`` (the canonical
    builder): a pre-built tree parked on ``state.current_tree`` /
    ``state.current_solve.tree`` wins, otherwise we build (and reuse the
    runner-cached) tree from the finished solve result. We import the
    tree_browser resolver lazily so the matrix module stays importable in
    isolation (and to avoid a hard import cycle).
    """

    direct = _safe_state_field(state, "current_tree", None)
    if direct is not None:
        return direct
    solve = _safe_state_field(state, "current_solve", None)
    if solve is not None:
        embedded = getattr(solve, "tree", None) or getattr(
            solve, "current_tree", None
        )
        if embedded is not None:
            return embedded
    try:
        from ui.views.tree_browser import _build_tree_from_runner
    except Exception:  # noqa: BLE001 -- tree_browser optional in isolation
        return None
    try:
        return _build_tree_from_runner(state)
    except Exception:  # noqa: BLE001 -- never let resolution crash the matrix
        return None


def _current_tree_snapshot(state: AppState) -> object:
    """Return the game-state snapshot at the currently selected tree node.

    Selecting a decision-tree node sets ``state.current_tree_node_id``; this
    resolves that id against the live ``SolveTree`` and returns the matching
    :class:`tree_browser.TreeNode` (which carries ``state_snapshot`` /
    ``player_to_act`` / ``legal_actions`` — exactly the fields the snapshot
    helpers read). On-path and off-path (counterfactual) nodes resolve the
    same way: the tree materializes any node on its slash-path on demand.

    Falls back to the spot's starting state when no tree is materialized yet
    (PR 10a renders the matrix at the root by default)."""

    tree = _resolve_tree(state)
    node_id = _safe_state_field(state, "current_tree_node_id", "root")
    if tree is not None:
        try:
            return tree.get_node(str(node_id))
        except (KeyError, AttributeError, ValueError):
            # Stale node id (e.g. selected node from a previous solve) —
            # fall back to the root node so the matrix still projects
            # something coherent rather than going blank.
            try:
                return tree.get_node("root")
            except (KeyError, AttributeError, ValueError):
                pass
    spot = _safe_state_field(state, "current_spot", None)
    if spot is None:
        return None
    from poker_solver.hunl import HUNLPoker

    config = getattr(spot, "config", None) or getattr(spot, "hunl_config", None)
    if config is None:
        # ``Spot`` exposes the canonical builder as ``to_hunl_config()``;
        # the bare ``config`` / ``hunl_config`` attribute names never
        # existed, so without this the no-tree fallback always returned
        # ``None`` and the matrix rendered combo-count-only cells.
        to_config = getattr(spot, "to_hunl_config", None)
        if callable(to_config):
            try:
                config = to_config()
            except Exception:  # noqa: BLE001 -- malformed spot; bail out
                return None
    if config is None:
        return None
    return HUNLPoker(config).initial_state()


def _selected_player(state: AppState) -> int:
    """Return the player slot whose strategy the matrix is rendering.

    PR 24a §3.3 + §8 Q5: the orchestrator flagged this function as a
    suspected non-consumer of ``spot.hero_player``. Verified on
    `2026-05-23` against the v1.5.0 baseline: the original implementation
    read ``state.selected_player_for_input`` exclusively, ignoring
    ``spot.hero_player`` entirely. Status: **swap was NOT present in
    main; this commit adds it.**

    Semantics with the new ``spot.hero_player`` field:
      * ``hero_player == 0`` (default): no change; the matrix renders
        ``selected_player_for_input`` directly. This preserves backward
        compatibility for every test and existing workflow.
      * ``hero_player == 1``: swap. ``selected_player_for_input == 0``
        now resolves to ``1`` (hero on front tab); ``== 1`` resolves to
        ``0`` (villain on the back tab). This matches the v1.3.1
        ``range_aggregator.solve_range_vs_range`` ``hero_player=1``
        convention where hero is the BB / defender.
    """
    selected = int(_safe_state_field(state, "selected_player_for_input", 0))
    spot = _safe_state_field(state, "current_spot", None)
    hero_player = int(getattr(spot, "hero_player", 0)) if spot is not None else 0
    if hero_player == 1:
        return 1 - selected
    return selected


def _matrix_player(state: AppState, snapshot: object | None) -> int:
    """Return the seat whose range + strategy the matrix projects.

    The matrix shows *whose decision it is*: the player TO ACT at the
    currently-selected tree node (``snapshot.player_to_act``). The combo
    inspector, the 13x13 grid, and the header subtitle must ALL agree on
    this seat — otherwise the grid lights up the acting player's hand
    (e.g. P1's QQ) while the inspector reports the hero's combos (P0's
    AhKc), so the lit cell reads "QQ (0 combos)" (P3). Falling back to
    the input-tab selection (``_selected_player``) only when no node
    snapshot resolves keeps the pre-solve / chance-node view coherent.

    This is the single source of truth for the "matrix seat" so the three
    render paths can never drift apart again.
    """

    node_player = _snapshot_player(snapshot) if snapshot is not None else None
    if node_player is not None and node_player in (0, 1):
        return node_player
    return _selected_player(state)


def _show_frequencies(state: AppState) -> bool:
    prefs = _safe_state_field(state, "prefs", None)
    if prefs is None:
        return True
    return bool(getattr(prefs, "matrix_show_frequencies", True))


@dataclass
class _CellRender:
    """Internal helper: everything render() needs to draw one cell."""

    hand_class: str
    row: int
    col: int
    summary: CellSummary


def _build_grid_summaries(
    state: AppState,
) -> list[_CellRender]:
    board = _current_board(state)

    # PR 24a §3.2: range-vs-range overlay. When the active solve produced
    # a ``RangeVsRangeResult``, render its per-class strategy directly
    # instead of the concrete-vs-concrete infoset-keyed strategy. The
    # ``hero_player`` swap (above) already routes ``_selected_player`` to
    # hero's slot so the front-tab view stays "hero's strategy."
    rvr_result = _current_rvr_result(state)
    if rvr_result is not None:
        range_ = _current_range(state, _selected_player(state))
        return _build_grid_summaries_rvr(state, rvr_result, range_, board)

    strategy = _current_strategy(state)
    snapshot = _current_tree_snapshot(state)
    tree_node_id = str(_safe_state_field(state, "current_tree_node_id", "root"))

    # Project the strategy of the player who acts AT THE SELECTED NODE.
    # ``cell_strategy_summary`` already builds infoset keys for the
    # snapshot's ``player_to_act``; the displayed range must match that
    # same player or the per-combo strategy lookup queries one player's
    # range with the other player's infoset (incoherent cells when the
    # navigated node belongs to the opponent). ``_matrix_player`` is the
    # shared seat resolver used by the grid, the combo inspector, and the
    # header subtitle so the three never disagree (P3).
    grid_player = _matrix_player(state, snapshot)
    range_ = _current_range(state, grid_player)

    rendered: list[_CellRender] = []
    for row in range(13):
        for col in range(13):
            hand_class = _hand_class_at(row, col)
            if range_ is None:
                summary = CellSummary(out_of_range=True, empty=True)
            else:
                summary = cell_strategy_summary(
                    hand_class=hand_class,
                    range_=range_,
                    board=board,
                    strategy=strategy,
                    tree_node_id=tree_node_id,
                    game_state_snapshot=snapshot,
                )
            rendered.append(
                _CellRender(hand_class=hand_class, row=row, col=col, summary=summary)
            )
    return rendered


def _current_rvr_result(state: AppState) -> object | None:
    """Return the active ``RangeVsRangeResult`` if the spot is in RvR mode.

    Returns None when:
      * the spot is in concrete-vs-concrete mode (``rvr_mode == False``);
      * no solve has run yet (``runner.rvr_result is None``);
      * the solver is mid-run (``runner.status != 'done'``); we wait for
        the final aggregator output rather than show partial per-class
        data which would jump around as classes complete.

    Duck-typed return so the renderer doesn't need to import the
    dataclass directly (keeps module import surface narrow).
    """
    spot = _safe_state_field(state, "current_spot", None)
    if spot is None or not getattr(spot, "rvr_mode", False):
        return None
    runner = _safe_state_field(state, "runner", None)
    if runner is None:
        return None
    rvr = getattr(runner, "rvr_result", None)
    if rvr is None:
        return None
    status = getattr(runner, "status", "idle")
    # Only show once the aggregator has finished — partial mid-class
    # outputs would render half the matrix in stale state.
    if status not in ("done", "stopped"):
        return None
    return rvr


def _build_grid_summaries_rvr(
    state: AppState,
    rvr_result: object,
    range_: RangeWithFreqs | None,
    board: Sequence[Card],
) -> list[_CellRender]:
    """Render the matrix from a ``RangeVsRangeResult`` (PR 24a §3.2).

    Maps each hand class to an aggregated fold/call/raise summary by
    bucketing the per-class action labels back onto the RYG triple per
    the Pio convention:
      * ``fold``                -> fold bucket
      * ``check`` / ``call``    -> call bucket
      * ``bet_*`` / ``raise_*`` / ``all_in`` -> raise bucket
    Classes absent from ``per_class_strategy`` (skipped by the
    aggregator due to all-combo board-block) render as ``blocked``.
    Classes absent from the hero range render as ``out_of_range``.
    """
    per_class = getattr(rvr_result, "per_class_strategy", {})
    board_cards = set(board)
    rendered: list[_CellRender] = []
    for row in range(13):
        for col in range(13):
            hand_class = _hand_class_at(row, col)
            summary = CellSummary()
            in_range = False
            if range_ is not None:
                combos = _enumerate_combos_for_class(hand_class)
                for combo in combos:
                    if range_.frequency_of(combo) > 0.0:
                        in_range = True
                        if combo[0] in board_cards or combo[1] in board_cards:
                            summary.has_blocker = True
                        else:
                            summary.combo_count += 1
            if not in_range:
                summary.empty = True
                summary.out_of_range = True
                rendered.append(
                    _CellRender(
                        hand_class=hand_class, row=row, col=col, summary=summary
                    )
                )
                continue
            freqs = per_class.get(hand_class)
            if freqs is None:
                # Class was in the input range but the aggregator
                # skipped it (every combo blocked, or all reps timed
                # out). Mark blocked so the user sees a clear signal.
                summary.blocked = True
                rendered.append(
                    _CellRender(
                        hand_class=hand_class, row=row, col=col, summary=summary
                    )
                )
                continue
            fold = 0.0
            call = 0.0
            raise_ = 0.0
            for label, prob in freqs.items():
                if label == "fold":
                    fold += float(prob)
                elif label in ("check", "call"):
                    call += float(prob)
                else:
                    # bet_* / raise_* / all_in / unknown -> raise bucket
                    raise_ += float(prob)
            total = fold + call + raise_
            if total > 0.0:
                summary.fold = fold / total
                summary.call = call / total
                summary.raise_ = raise_ / total
            rendered.append(
                _CellRender(hand_class=hand_class, row=row, col=col, summary=summary)
            )
    return rendered


# Cell visual constants — single source of truth.
_CELL_PX: int = 54  # 13*54 ~= 700 px, meets 24px floor (spec anti-pattern §3.3)
# Theme-aware neutrals (F04): the cell LABEL/faded text reads via CSS vars
# (defined in ``ui/app.py``) so it stays legible in both light + dark. The
# CELL BACKGROUND blend (``cell_color``) is a semantic RYG/grey value locked
# by smoke tests and is intentionally left as-is.
_LABEL_COLOR: str = "var(--ps-cell-label)"
_FADED_COLOR: str = "var(--ps-faded)"


def _cell_style(summary: CellSummary) -> str:
    color = cell_color(summary)
    # F04: blocked / out-of-range / empty cells return the neutral grey
    # sentinel from ``cell_color`` (``#3a3a3a``, test-locked). That value is
    # a NEUTRAL, not a strategy color, so re-route it through the theme var
    # here — the only place it reaches the DOM — so the faded cell tracks the
    # active theme (light-grey on light, near-black on dark) and its tag text
    # stays legible. ``cell_color`` itself is untouched (unit-tested).
    if summary.blocked or summary.out_of_range or summary.empty:
        color = "var(--ps-faded)"
    elif summary.fold + summary.call + summary.raise_ <= 0.0:
        # F04 round 2: an IN-RANGE cell with no strategy mass (no solve yet,
        # or no strategy entry for this infoset) blends to rgb(0,0,0) in
        # ``cell_color`` — pure black, the default-range "MIX" look. That is
        # a NEUTRAL base fill, not a semantic strategy color, so re-route it
        # through ``--ps-cell-bg`` here (the only place it reaches the DOM):
        # black on dark (pixel-identical to before), pale on light so the
        # cell + its dark label/tag stay legible. SOLVED cells (any action
        # mass, incl. faded fractional ranges) keep their RYG blend untouched
        # — ``cell_color`` is still authoritative for those and unit-tested.
        color = "var(--ps-cell-bg)"
    text_color = _LABEL_COLOR
    extras = ""
    if summary.blocked:
        # Slashed diagonal pattern overlay per spec §3.3 + postflop-solver
        # convention (cited in ``competitor_ui_deep_dive.md`` §Honorable
        # mentions). Linear-gradient stripes are CSS-only — no third-party.
        extras = (
            "; background-image: repeating-linear-gradient(45deg, "
            "rgba(255,255,255,0.18) 0 4px, transparent 4px 8px)"
        )
        text_color = "var(--ps-cell-tag-blocked)"
    elif summary.out_of_range or summary.empty:
        text_color = "var(--ps-text-fainter)"
    return (
        f"width:{_CELL_PX}px;height:{_CELL_PX}px;background:{color};"
        f"color:{text_color};border:1px solid var(--ps-cell-border);"
        f"display:flex;flex-direction:column;justify-content:space-between;"
        f"padding:3px 4px;font-size:11px;cursor:pointer{extras}"
    )


def _on_cell_click(
    state: AppState, hand_class: str, refresh_inspector: Callable[[], None]
) -> Callable[..., None]:
    def handler(_event: object = None) -> None:
        # Persist the selected hand class on state for downstream views.
        prefs = _safe_state_field(state, "prefs", None)
        if prefs is not None:
            prefs.matrix_selected_hand_class = hand_class
        refresh_inspector()

    return handler


@dataclass
class _ComboRow:
    label: str
    fold: float
    call: float
    raise_: float
    blocked: bool
    ev_mbb: float
    reach: float
    infoset_key: str
    cards: tuple[Card, Card] | None = None


def _build_combo_rows(state: AppState, hand_class: str) -> list[_ComboRow]:
    # P3: the inspector must describe the SAME seat the grid lights up —
    # the player to act at the selected node — not always the input-tab
    # hero. Resolving the range against ``_selected_player`` while the
    # snapshot's strategy lookup used the node's ``player_to_act`` is what
    # produced the "QQ (0 combos)" mismatch (grid showed P1's QQ; inspector
    # queried P0's range, which holds AhKc not QQ). ``_matrix_player`` ties
    # the range, the strategy player, and the legal actions to one seat.
    snapshot = _current_tree_snapshot(state)
    player = _matrix_player(state, snapshot)
    range_ = _current_range(state, player)
    if range_ is None:
        return []
    board_cards = set(_current_board(state))
    strategy = _current_strategy(state)
    state_obj = _snapshot_state(snapshot)
    legal_actions = _snapshot_legal_actions(snapshot)

    rows: list[_ComboRow] = []
    for combo in _enumerate_combos_for_class(hand_class):
        weight = float(range_.frequency_of(combo))
        if weight <= 0.0:
            continue
        c1, c2 = combo
        label = f"{c1}{c2}"
        if c1 in board_cards or c2 in board_cards:
            rows.append(
                _ComboRow(
                    label=label,
                    fold=0.0,
                    call=0.0,
                    raise_=0.0,
                    blocked=True,
                    ev_mbb=0.0,
                    reach=0.0,
                    infoset_key="",
                    cards=combo,
                )
            )
            continue
        if state_obj is None or not legal_actions:
            rows.append(
                _ComboRow(
                    label=label,
                    fold=0.0,
                    call=1.0,
                    raise_=0.0,
                    blocked=False,
                    ev_mbb=0.0,
                    reach=weight,
                    infoset_key="",
                    cards=combo,
                )
            )
            continue
        probs = _strategy_for_combo(strategy, state_obj, combo, player, legal_actions)
        if probs is None:
            f, c, r = 0.0, 1.0, 0.0
            key = ""
        else:
            f, c, r = _aggregate_action_buckets(legal_actions, probs)
            from poker_solver.hunl import HUNLPoker

            key = HUNLPoker(state_obj.config).infoset_key(state_obj, player)
        rows.append(
            _ComboRow(
                label=label,
                fold=f,
                call=c,
                raise_=r,
                blocked=False,
                ev_mbb=0.0,  # Real EV plugs in when Agent A wires per-combo EV.
                reach=weight,
                infoset_key=key,
                cards=combo,
            )
        )
    return rows


def inspect_panel(state: AppState, hand_class: str) -> None:
    """Render the combo inspector strip below the matrix (Q5 locked).

    Per spec §3.3: list every surviving combo with a horizontal action
    bar, EV in mBB, reach probability, and a copyable infoset key
    (monospace). Combos blocked by the board appear as a "BLOCKED" row
    (anti-pattern §3.8 mitigation: dense numeric tables get color).
    """

    ui_mod = _import_nicegui()
    rows = _build_combo_rows(state, hand_class)
    with (
        ui_mod.element("div")
        .mark("combo-inspector-strip")
        .style(
            "padding:8px 12px;background:var(--ps-strip-bg);"
            "border-top:1px solid var(--ps-border-strong)"
        )
    ):
        ui_mod.label(f"Combo inspector — {hand_class} ({len(rows)} combos)").style(
            "font-weight:600;color:var(--ps-text);margin-bottom:6px"
        )
        if not rows:
            ui_mod.label("No combos in range").style("color:var(--ps-text-faint)")
            return
        for row in rows:
            marker = f"combo-inspector-row-{row.label}"
            with (
                ui_mod.row()
                .mark(marker)
                .style("align-items:center;gap:10px;padding:2px 0")
            ):
                if row.cards is not None:
                    ui_mod.html(board_html(list(row.cards), sep="")).style(
                        "width:64px"
                    )
                else:
                    ui_mod.label(row.label).style(
                        "font-family:Menlo,Consolas,monospace;width:64px;"
                        "color:var(--ps-text-dim)"
                    )
                if row.blocked:
                    ui_mod.label("BLOCKED — card on board").style(
                        "color:var(--ps-text-muted);font-style:italic"
                    )
                    continue
                # Horizontal stacked bar: red (fold) / yellow (call) /
                # green (raise) — Pio palette per spec §7.3.
                bar_width = 180
                rw = int(round(row.raise_ * bar_width))
                cw = int(round(row.call * bar_width))
                fw = max(0, bar_width - rw - cw)
                with ui_mod.element("div").style(
                    f"display:flex;width:{bar_width}px;height:12px;"
                    "border:1px solid var(--ps-border-soft)"
                ):
                    ui_mod.element("div").style(
                        f"width:{rw}px;background:rgb(40,180,60)"
                    )
                    ui_mod.element("div").style(
                        f"width:{cw}px;background:rgb(220,200,40)"
                    )
                    ui_mod.element("div").style(
                        f"width:{fw}px;background:rgb(220,40,40)"
                    )
                ui_mod.label(
                    f"R {int(round(row.raise_ * 100))}% · "
                    f"C {int(round(row.call * 100))}% · "
                    f"F {int(round(row.fold * 100))}%"
                ).style("color:var(--ps-text-mono);font-family:Menlo,Consolas,monospace")
                ui_mod.label(f"EV {row.ev_mbb:+.0f} mBB").style(
                    "color:var(--ps-accent-ev);font-family:Menlo,Consolas,monospace"
                )
                ui_mod.label(f"reach {row.reach:.3f}").style(
                    "color:var(--ps-accent-reach);font-family:Menlo,Consolas,monospace"
                )
                if row.infoset_key:
                    ui_mod.label(row.infoset_key).style(
                        "color:var(--ps-text-fainter);"
                        "font-family:Menlo,Consolas,monospace;"
                        "font-size:10px"
                    ).tooltip("infoset key — click to copy from devtools")


def render(state: AppState) -> None:
    """Render the 13x13 range matrix + combo inspector strip.

    Q2 locked: hand-class labels visible in cells (upper-left); numeric
    frequencies via hover tooltip + click-inspector. Q5 locked: combo
    inspector is a full-width strip BELOW the matrix (not to the side).

    The matrix is the visual centerpiece per §3 layout amendment.
    NiceGUI markers (Agent C asserts on these via ElementFilter):
      - ``range-matrix-display``     outer container
      - ``matrix-cell``              all 169 cells (smoke 6 asserts count)
      - ``matrix-cell-{cls}``        per-class marker
      - ``combo-inspector-strip``    inspector container
      - ``combo-inspector-row-{c}``  one per surviving combo
    """

    ui_mod = _import_nicegui()

    # Whole-matrix refreshable wrapper. Selecting a decision-tree node
    # (``tree_browser.on_tree_node_selected``) or loading an example spot
    # (``spot_input._on_load_preset``) mutates ``state`` then calls the
    # refresh hook registered below; re-running this body repaints the
    # grid + header against the new ``current_tree_node_id`` /
    # ``current_spot``. Without this the matrix only ever drew once at
    # page build (the on/off-path navigation + spot-load desync bugs).
    @ui_mod.refreshable  # type: ignore[untyped-decorator]
    def _matrix_body() -> None:
        _render_matrix_body(state, ui_mod)

    # Register the refresh callable on BOTH the runner (mirrors the
    # ``_tree_browser_refresh`` / ``_preflop_chart_refresh`` hook
    # convention) and ``state.matrix_refresh`` (the exact attribute name
    # ``tree_browser.on_tree_node_selected`` already looks up to drive the
    # matrix after a node click). Best-effort: never let hook registration
    # break the first render.
    refresh_callable = _matrix_body.refresh
    runner = _safe_state_field(state, "runner", None)
    if runner is not None:
        with contextlib.suppress(Exception):
            runner._range_matrix_refresh = refresh_callable  # noqa: SLF001
    with contextlib.suppress(Exception):
        state.matrix_refresh = refresh_callable  # type: ignore[attr-defined]

    _matrix_body()


def _render_matrix_body(state: AppState, ui_mod: Any) -> None:
    """Render the matrix body (refreshable inner pass of :func:`render`).

    Split out of :func:`render` so the ``@ui.refreshable`` wrapper re-runs
    JUST the grid + header + inspector when a node is selected or a spot is
    loaded, without re-registering the refresh hooks.
    """

    # Inner refreshable for the combo inspector so cell clicks can
    # re-render the strip without touching the matrix. Pattern from
    # the in-repo NiceGUI guide (mental model 8 — refreshable elements).
    @ui_mod.refreshable  # type: ignore[untyped-decorator]
    def _inspector_slot() -> None:
        prefs = _safe_state_field(state, "prefs", None)
        selected = getattr(prefs, "matrix_selected_hand_class", None) if prefs else None
        if selected is None:
            with (
                ui_mod.element("div")
                .mark("combo-inspector-strip")
                .style(
                    "padding:8px 12px;background:var(--ps-strip-bg);"
                    "border-top:1px solid var(--ps-border-strong);"
                    "color:var(--ps-text-faint)"
                )
            ):
                ui_mod.label("Click a cell to inspect its combos").style(
                    "font-style:italic"
                )
            return
        inspect_panel(state, str(selected))

    with (
        ui_mod.element("div")
        .mark("range-matrix-display")
        .style("background:var(--ps-panel-bg);padding:12px;border-radius:6px")
    ):
        with ui_mod.row().style(
            "align-items:center;justify-content:space-between;margin-bottom:6px"
        ):
            ui_mod.label("RANGE MATRIX").style(
                "font-weight:700;letter-spacing:0.05em;color:var(--ps-text-strong)"
            )
            ui_mod.label(_matrix_subtitle(state)).style(
                "color:var(--ps-text-muted);font-size:12px"
            )

        # Empty-state hint: until a solve publishes a strategy the cells show
        # only the input range (no action colors), so point the user at the
        # Solve button rather than leaving an unexplained blank grid.
        if not _has_solved_strategy(state):
            ui_mod.label(
                "No strategy yet — set a spot, then press Solve in the Run "
                "Panel to color the grid with the GTO strategy."
            ).mark("matrix-empty-hint").style(
                "color:var(--ps-text-faint);font-style:italic;"
                "font-size:12px;margin-bottom:6px"
            )

        with ui_mod.element("div").style(
            f"display:grid;grid-template-columns:repeat(13, {_CELL_PX}px);"
            "gap:2px;justify-content:center"
        ):
            for cell in _build_grid_summaries(state):
                # NiceGUI's `User.find(marker=...)` filter searches
                # `element._markers`, populated by `.mark(...)` (whitespace-
                # delimited per nicegui/element.py:342). The old form
                # `.props("data-marker=matrix-cell,matrix-cell-AKs")` set a
                # Quasar prop instead and never populated _markers, so all
                # five smoke tests that look up `matrix-cell` would assert 0.
                cell_marker = f"matrix-cell matrix-cell-{cell.hand_class}"
                cell_el_builder = (
                    ui_mod.element("div")
                    .mark(cell_marker)
                    .style(_cell_style(cell.summary))
                )
                if cell.summary.blocked or cell.summary.has_blocker:
                    # Smoke 15 (X2): blocker cells expose a `blocker-overlay`
                    # CSS class so the smoke test can assert on slashed
                    # overlay styling without scraping inline styles.
                    # ``blocked`` = fully blocked (no surviving combos);
                    # ``has_blocker`` = at least one combo blocked.
                    cell_el_builder = cell_el_builder.classes("blocker-overlay")
                with cell_el_builder as cell_el:
                    ui_mod.label(cell.hand_class).style(
                        "font-weight:600;font-family:'SF Pro',Inter,sans-serif"
                    )
                    if cell.summary.out_of_range:
                        ui_mod.label("—").style(
                            "align-self:center;font-size:18px;"
                            "color:var(--ps-text-fainter)"
                        )
                    else:
                        tag = _cell_tag(cell.summary)
                        if tag and _show_frequencies(state):
                            ui_mod.label(tag).style(
                                "font-family:Menlo,Consolas,monospace;"
                                "font-size:10px;align-self:flex-end;"
                                "color:var(--ps-cell-tag)"
                                if not (cell.summary.blocked)
                                else "font-family:Menlo,Consolas,monospace;"
                                "font-size:10px;align-self:flex-end;"
                                "color:var(--ps-cell-tag-blocked)"
                            )
                    ui_mod.tooltip(_tooltip_text(cell.hand_class, cell.summary))
                    cell_el.on(
                        "click",
                        _on_cell_click(state, cell.hand_class, _inspector_slot.refresh),
                    )

        # Legend (single line under the matrix). Locked principle 4:
        # strategy palette is RYG; input-matrix palette is white->blue
        # (rendered in Agent A's spot input view). The RYG swatches are
        # semantic (kept verbatim); the row text + neutral swatches read
        # via theme vars so the legend is legible on light backgrounds too.
        with ui_mod.row().style(
            "gap:14px;margin-top:6px;color:var(--ps-text-muted);font-size:11px"
        ):
            ui_mod.html(
                "<span style='color:var(--ps-act-raise)'>&#9632;</span> raise/bet"
            )
            ui_mod.html(
                "<span style='color:var(--ps-act-call)'>&#9632;</span> call/check"
            )
            ui_mod.html("<span style='color:var(--ps-act-fold)'>&#9632;</span> fold")
            ui_mod.html(
                "<span style='color:var(--ps-faded)'>&#9632;</span> out of range"
            )
            ui_mod.html(
                "<span style='color:var(--ps-text-muted)'>&#9740;</span> "
                "blocked by board"
            )

        # Combo inspector strip (BELOW the matrix per Q5 locked).
        _inspector_slot()


def _has_solved_strategy(state: AppState) -> bool:
    """True when a finished solve has published a strategy for the matrix.

    The 13x13 grid always paints something (the input range tinted by
    whatever strategy mass exists), so before any solve has run it shows
    in-range cells with no action colors and no obvious cue that the user
    must press Solve to populate them. This mirrors the tree-browser's
    "Solve to populate…" and the preflop-chart's "no chart computed yet"
    empty states: we check for either a concrete strategy dict or a
    finished range-vs-range result, and the renderer shows a one-line
    guidance banner when neither is present.
    """
    if _current_rvr_result(state) is not None:
        return True
    return bool(_current_strategy(state))


def _matrix_subtitle(state: AppState) -> str:
    """Compose the small caption to the right of the MATRIX heading.

    PR 24a §3.2 / §3.3: when ``spot.rvr_mode`` is set, surface the
    aggregator's ``position`` field ("aggressor" / "defender") so the
    user can disambiguate between c-bet frequencies and defense
    frequencies. The hero seat is also shown.
    """

    node_id = _safe_state_field(state, "current_tree_node_id", "root")
    spot = _safe_state_field(state, "current_spot", None)
    hero_player = int(getattr(spot, "hero_player", 0)) if spot is not None else 0
    # When a decision-tree node is selected, the "to act" player is the
    # node's ``player_to_act`` (so the header tracks the navigated node,
    # not just the input-tab selection). ``_matrix_player`` is the shared
    # seat resolver — header, grid, and inspector all read it (P3).
    snapshot = _current_tree_snapshot(state)
    player = _matrix_player(state, snapshot)
    if spot is not None and getattr(spot, "rvr_mode", False):
        position = "aggressor" if hero_player == 0 else "defender"
        return (
            f"RvR · hero P{hero_player} ({position}) · "
            f"viewing P{player} · node {node_id}"
        )
    return f"node {node_id} · player P{player} to act · hero P{hero_player}"


__all__ = [
    "CellSummary",
    "cell_strategy_summary",
    "cell_color",
    "inspect_panel",
    "render",
]
