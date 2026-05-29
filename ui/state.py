"""Shared UI state, threading scaffold, and persistence (PR 10a).

This module is the trunk on which the rest of the UI hangs. It exports:

- Dataclasses: ``RangeWithFreqs`` (wraps ``poker_solver.Range`` with per-combo
  frequencies), ``Spot`` (board + ranges + stacks + tree config), ``SolveSession``
  (active solve metadata), ``UIPrefs`` (persisted user prefs), ``AppState``
  (aggregator passed to view ``render`` functions).
- ``SolveRunner``: the worker-thread orchestrator. Owns ONE background
  ``threading.Thread`` + ``_pause_event`` + ``_stop_event``. Worker invokes
  ``_solve_postflop_impl`` (= ``mock_solve`` in PR 10a, real ``solve_hunl_postflop``
  in PR 10b — one-line import swap per ``pr10b_spec.md``). UI thread NEVER
  calls worker code directly; progress flows via a ``ui.timer(0.5, ...)``
  reading ``SolveRunner`` attributes.
- Module-level singleton accessors: ``get_state()`` lazily loads from
  ``~/.poker_solver_ui/state.json``; ``save_state()`` debounces and atomically
  writes to that path.
- Hand-class enumeration helpers consumed by Agent B's matrix renderer:
  ``enumerate_hand_classes()`` (169 entries, row-major top-left=AA),
  ``enumerate_combos(label)``, ``hand_class_label(r1, r2, suited)``,
  ``classify_combo(c0, c1)``.

Threading model (load-bearing surface per ``implementation_challenges.md``):

- ``SolveRunner.start()`` spawns a daemon thread running ``_worker``.
- ``_worker`` calls ``_solve_postflop_impl(config, None, iterations, ...)``
  on a helper thread; the mock owns the per-snapshot loop and the
  ``_CANCEL_FLAG`` check. Per
  ``docs/pr10_prep/mock_signature_drift.md`` Option A, there is NO
  ``on_progress`` callback (the real ``solve_hunl_postflop`` has none);
  instead mock_solve publishes per-snapshot progress to the module-level
  ``_LATEST_PROGRESS`` buffer in ``ui.mock_solver``.
- The worker thread polls ``read_latest_progress()`` at ~50 ms cadence
  while the helper runs and updates ``self.iteration`` +
  ``self.expl_history`` + ``self.partial_report`` under ``self._lock``.
  The poll loop also (a) sets ``_CANCEL_FLAG`` if ``self._stop_event``
  is set so the next mock snapshot exits the loop, and (b) blocks while
  ``self._pause_event`` is set.
- Worker NEVER calls NiceGUI APIs. UI thread reads ``SolveRunner`` state
  via the 500 ms ``ui.timer`` (registered in ``ui/app.py``) which calls
  ``run_panel.refresh_progress(state)``.
- ``stop()`` sets BOTH ``self._stop_event`` AND ``ui.mock_solver._CANCEL_FLAG``
  (per ``pr10a_spec.md`` §7.5). Stop halts within one snapshot interval.

Persistence (``pr10a_spec.md`` §9.2):

- State lives at ``~/.poker_solver_ui/state.json``.
- Atomic write: write to ``state.json.tmp``, ``fsync``, ``os.rename`` to
  ``state.json``. Avoids corruption on crash mid-write.
- Debounced via a 500 ms in-memory window: ``save_state()`` marks dirty,
  the deferred flush coalesces multiple edits into one disk write.
- On load failure (corrupt JSON or version mismatch): warn, back up to
  ``state.json.bak``, start from defaults. Never crash.
- ``recent_spots`` capped at 10 (FIFO eviction). ``library_entries`` empty
  in PR 10a.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from poker_solver.card import RANKS, Card
from poker_solver.hunl import HUNLConfig, HUNLPoker, Street, _serialize_hunl_config
from poker_solver.range import Range, parse_range
from poker_solver.range_aggregator import (
    HandClass,
    RangeVsRangeNashResult,
    RangeVsRangeResult,
)
from poker_solver.solver import SolveResult

if TYPE_CHECKING:
    from poker_solver.profiler.memory import MemoryReport

logger = logging.getLogger(__name__)

# B10 Phase A: ``Combo`` is now a ``tuple`` subclass carrying a ``weight``
# attribute. The UI layer historically treated combos as bare 2-tuples;
# annotate that explicitly so type checks remain happy while runtime stays
# polymorphic across both forms (a ``Combo`` IS-A ``tuple[Card, Card]``).
# B10 Phase C completed the migration: ``RangeWithFreqs.frequencies`` is no
# longer stored on the wrapper; the canonical weight store lives in
# ``Range._weight``. ``frequency_of`` / ``set_frequency`` delegate to
# ``Range.weight`` / ``Range.set_weight``.
_CardPair = tuple[Card, Card]

# --------------------------------------------------------------------------- #
# Hand-class enumeration helpers
# --------------------------------------------------------------------------- #
#
# Canonical 13x13 grid convention per ``pr10a_spec.md`` §3.3:
#
#         A   K   Q   J   T   9   8   7   6   5   4   3   2
#     A  AA  AKs AQs AJs ATs A9s A8s A7s A6s A5s A4s A3s A2s
#     K  AKo KK  KQs KJs KTs K9s K8s K7s K6s K5s K4s K3s K2s
#     ...
#     2  A2o K2o Q2o J2o T2o 92o 82o 72o 62o 52o 42o 32o 22
#
# Internal coordinates use ``row``/``col`` in [0, 12], where row 0 is the
# A-row (top of grid) and col 0 is the A-column (left of grid). The rank
# at row/col ``i`` is ``14 - i`` (i.e., row 0 = Ace = rank 14, row 12 = 2 =
# rank 2). On-diagonal cells (row == col) are pairs; cells with col > row
# (visually to the right of the diagonal) are suited; col < row are offsuit.
#
# Agent B's display matrix and Agent C's smoke tests depend on this exact
# row/col convention. DO NOT change without coordinating across all three.

_RANK_FROM_GRID_INDEX: tuple[int, ...] = tuple(14 - i for i in range(13))


def hand_class_label(rank1: int, rank2: int, suited: bool) -> str:
    """Return the canonical hand-class label for two ranks + suited flag.

    Args:
        rank1: rank value in [2, 14] (Ace == 14).
        rank2: rank value in [2, 14].
        suited: ignored when ``rank1 == rank2`` (pairs are unsuited tokens).

    Returns:
        ``"AA"``, ``"AKs"``, ``"72o"``, etc. Higher rank always first.
    """
    if not (2 <= rank1 <= 14 and 2 <= rank2 <= 14):
        raise ValueError(f"ranks out of [2, 14]: {rank1}, {rank2}")
    hi, lo = max(rank1, rank2), min(rank1, rank2)
    hi_char = RANKS[hi - 2]
    lo_char = RANKS[lo - 2]
    if hi == lo:
        return f"{hi_char}{lo_char}"
    return f"{hi_char}{lo_char}{'s' if suited else 'o'}"


def enumerate_hand_classes() -> list[tuple[int, int, str]]:
    """Yield (row, col, label) for the 13x13 grid in row-major order.

    Row 0 is the A-row at the top; col 0 is the A-column at the left.
    Diagonal (row == col) is pairs; col > row is suited; col < row is offsuit.

    Returns 169 entries; ``[0] == (0, 0, "AA")``, ``[1] == (0, 1, "AKs")``,
    ``[12] == (0, 12, "A2s")``, ``[13] == (1, 0, "AKo")``, ...,
    ``[168] == (12, 12, "22")``.
    """
    out: list[tuple[int, int, str]] = []
    for row in range(13):
        for col in range(13):
            r_row = _RANK_FROM_GRID_INDEX[row]
            r_col = _RANK_FROM_GRID_INDEX[col]
            if row == col:
                out.append((row, col, hand_class_label(r_row, r_col, suited=False)))
            elif col > row:
                # suited: above/right of diagonal
                out.append((row, col, hand_class_label(r_row, r_col, suited=True)))
            else:
                # offsuit: below/left of diagonal
                out.append((row, col, hand_class_label(r_row, r_col, suited=False)))
    return out


def enumerate_combos(hand_class: str) -> list[_CardPair]:
    """Return the concrete (Card, Card) combos for a hand-class label.

    - Pair ``"XX"``: 6 combos (C(4, 2)), sorted by (suit_hi, suit_lo).
    - Suited ``"XYs"``: 4 combos (one per suit), sorted by suit.
    - Offsuit ``"XYo"``: 12 combos (4 * 3), sorted by (hi_suit, lo_suit).

    Each combo's cards are ordered (higher rank first); the inner tuple
    preserves that ordering. ``classify_combo`` is the inverse.
    """
    if not 2 <= len(hand_class) <= 3:
        raise ValueError(f"invalid hand class label: {hand_class!r}")
    rank_chars = hand_class[:2]
    r1_char, r2_char = rank_chars[0], rank_chars[1]
    if r1_char not in RANKS or r2_char not in RANKS:
        raise ValueError(f"invalid ranks in {hand_class!r}")
    r1 = RANKS.index(r1_char) + 2
    r2 = RANKS.index(r2_char) + 2
    hi, lo = max(r1, r2), min(r1, r2)
    if hi == lo:
        # pair: no suit suffix
        if len(hand_class) != 2:
            raise ValueError(
                f"pair token must not carry a suit indicator: {hand_class!r}"
            )
        out: list[_CardPair] = []
        for s1 in range(4):
            for s2 in range(s1 + 1, 4):
                out.append((Card(hi, s1), Card(hi, s2)))
        return out
    if len(hand_class) != 3:
        raise ValueError(f"non-pair token must carry s/o indicator: {hand_class!r}")
    suit_indicator = hand_class[2]
    if suit_indicator == "s":
        return [(Card(hi, s), Card(lo, s)) for s in range(4)]
    if suit_indicator == "o":
        return [
            (Card(hi, s1), Card(lo, s2))
            for s1 in range(4)
            for s2 in range(4)
            if s1 != s2
        ]
    raise ValueError(f"suit indicator must be 's' or 'o': {hand_class!r}")


def classify_combo(card1: Card, card2: Card) -> str:
    """Return the hand-class label of two cards.

    Inverse of ``enumerate_combos``. Used by Agent C's
    ``test_combo_to_cell_mapping_no_off_by_one`` property test.
    """
    if card1 == card2:
        raise ValueError(f"combo has duplicate card: {card1}")
    suited = card1.suit == card2.suit
    return hand_class_label(card1.rank, card2.rank, suited)


# --------------------------------------------------------------------------- #
# Preflop-chart helpers (task #55)
# --------------------------------------------------------------------------- #
# The Rust binding ``_rust.solve_hunl_preflop_rvr`` emits strategy keys of
# the form ``"{hole_str}{key_suffix}"`` where ``hole_str`` is the two-card
# pair in Rust's format (rank + suit chars, sorted ascending by card int).
# ``RANKS = "23456789TJQKA"``, ``SUITS = "shdc"`` per
# ``poker_solver/range_aggregator.py:_hole_string_rust``. The hole_str is
# exactly 4 characters; the suffix is everything after that.

_RANKS_RUST_ORDER: str = "23456789TJQKA"
_SUITS_RUST_ORDER: str = "shdc"


def _split_preflop_key(key: str) -> tuple[str | None, str]:
    """Split a Rust preflop key into (hole_str, history_suffix).

    Returns ``(None, "")`` when the key is malformed (doesn't start with
    a valid 4-char hole_str). Defensive — the engine emits well-formed
    keys but we tolerate noise so a bad key doesn't crash the chart.
    """
    if len(key) < 4:
        return (None, "")
    hole_str = key[:4]
    # Validate: 4 chars, rank/suit/rank/suit per RANKS_RUST_ORDER /
    # SUITS_RUST_ORDER.
    if not (
        hole_str[0] in _RANKS_RUST_ORDER
        and hole_str[1] in _SUITS_RUST_ORDER
        and hole_str[2] in _RANKS_RUST_ORDER
        and hole_str[3] in _SUITS_RUST_ORDER
    ):
        return (None, "")
    return (hole_str, key[4:])


def _hand_class_from_hole_str(hole_str: str) -> str | None:
    """Convert a Rust ``hole_str`` (e.g. "AsKh") to a hand-class label.

    Mirrors the inverse of ``poker_solver.range_aggregator._hole_string_rust``.
    Returns ``None`` on malformed input.
    """
    if len(hole_str) != 4:
        return None
    r1_char, s1_char = hole_str[0], hole_str[1]
    r2_char, s2_char = hole_str[2], hole_str[3]
    if (
        r1_char not in _RANKS_RUST_ORDER
        or r2_char not in _RANKS_RUST_ORDER
        or s1_char not in _SUITS_RUST_ORDER
        or s2_char not in _SUITS_RUST_ORDER
    ):
        return None
    r1 = _RANKS_RUST_ORDER.index(r1_char) + 2
    r2 = _RANKS_RUST_ORDER.index(r2_char) + 2
    suited = s1_char == s2_char
    if r1 == r2 and s1_char == s2_char:
        # Same card twice — malformed.
        return None
    return hand_class_label(r1, r2, suited)


def _action_labels_for_count(count: int) -> list[str]:
    """Build the default action-label list for a preflop tree.

    The Phase A engine emits actions in the canonical order
    ``fold, call/check, open_2, open_3, open_4, open_5, all_in``
    (per ``crates/cfr_core/src/preflop_rvr.rs``). Counts below the
    full menu drop the last entries; counts above add ``raise_*``
    placeholders. This is a best-effort label set that the chart can
    display; the engine's true labels live in the Rust binding and
    aren't currently exported.
    """
    canonical = [
        "fold",
        "call",
        "open_2",
        "open_3",
        "open_4",
        "open_5",
        "all_in",
    ]
    if count <= 0:
        return canonical
    if count <= len(canonical):
        return canonical[:count]
    # Pad with raise_N placeholders.
    extras = [f"raise_{i}" for i in range(count - len(canonical))]
    return canonical + extras


# --------------------------------------------------------------------------- #
# Range helpers
# --------------------------------------------------------------------------- #


def _full_range_combos() -> list[_CardPair]:
    """All 1326 unordered combos as canonical (Card, Card) tuples.

    Cards within each combo are ordered (higher rank first; ties broken by
    suit ascending) to match ``Range.add``'s sort key.
    """
    out: list[_CardPair] = []
    for r1 in range(2, 15):
        for s1 in range(4):
            for r2 in range(2, 15):
                for s2 in range(4):
                    if (r1, s1) == (r2, s2):
                        continue
                    if (r1, s1) < (r2, s2):
                        continue
                    c_hi = Card(r1, s1)
                    c_lo = Card(r2, s2)
                    # Range.add sorts by (-rank, suit). Match that ordering.
                    if c_hi.rank < c_lo.rank or (
                        c_hi.rank == c_lo.rank and c_hi.suit > c_lo.suit
                    ):
                        c_hi, c_lo = c_lo, c_hi
                    out.append((c_hi, c_lo))
    return out


def _full_range() -> Range:
    """Build a Range containing all 1326 combos (poker_solver.Range has no
    ``.full()`` factory in PR 1; rolled here)."""
    r = Range()
    for combo in _full_range_combos():
        r.add(combo)
    return r


# --------------------------------------------------------------------------- #
# Dataclasses
# --------------------------------------------------------------------------- #


@dataclass
class RangeWithFreqs:
    """A ``poker_solver.Range`` with per-combo frequency semantics.

    B10 Phase C migration: per-combo weights now live canonically inside
    ``Range._weight`` (added in B10 Phase A). ``RangeWithFreqs`` is a thin
    UI-facing facade that delegates ``frequency_of`` / ``set_frequency``
    to ``Range.weight`` / ``Range.set_weight``. The separate
    ``frequencies`` dict has been removed.

    Semantics (unchanged from pre-Phase-C):

    - ``frequency_of(combo)`` returns the underlying ``Range`` weight if
      the combo is present, else ``0.0``.
    - ``set_frequency(combo, freq)`` clamps ``freq`` to ``[0.0, 1.0]``
      and writes through to ``Range.set_weight``. Combos not yet in the
      base range are added.
    - The range-INPUT matrix in ``ui/views/spot_input.py`` mutates
      weights via ``set_frequency`` when a cell is clicked or
      shift-clicked.
    - Agent B's strategy DISPLAY matrix reads
      ``state.current_spot.ranges[player].frequency_of(combo)`` for the
      per-cell aggregate (e.g., to size a "% of range" label).
    """

    base_range: Range = field(default_factory=Range)

    def frequency_of(self, combo: _CardPair) -> float:
        """Return the frequency of ``combo``.

        Delegates to ``Range.weight(combo)``. Returns ``0.0`` when the
        combo is absent from the base range.
        """
        return self.base_range.weight(combo)

    def set_frequency(self, combo: _CardPair, freq: float) -> None:
        """Set the combo's frequency to ``freq`` (clamped to ``[0.0, 1.0]``).

        Delegates to ``Range.set_weight``. Adds ``combo`` to the base
        range if not already present.
        """
        clamped = max(0.0, min(1.0, freq))
        self.base_range.set_weight(combo, clamped)

    @classmethod
    def from_string(cls, range_str: str) -> RangeWithFreqs:
        """Parse ``range_str`` via ``parse_range``; every combo at 1.0."""
        base = parse_range(range_str)
        return cls(base_range=base)

    @classmethod
    def full(cls) -> RangeWithFreqs:
        """Construct a ``RangeWithFreqs`` containing all 1326 combos at 1.0."""
        base = _full_range()
        return cls(base_range=base)

    @classmethod
    def empty(cls) -> RangeWithFreqs:
        """Construct an empty ``RangeWithFreqs``."""
        return cls(base_range=Range())

    def to_string(self) -> str:
        """Render back to a comma-separated combo list.

        Lossy: combos with frequency < 1.0 lose their fractional weight.
        Round-trips ``RangeWithFreqs.from_string(rw.to_string())`` only for
        unit-weight ranges. (B10 Phase D will switch this to the
        weight-preserving ``Range.to_string`` once CLI plumbing lands.)
        """
        tokens: list[str] = []
        for combo in self.base_range.combos:
            if self.frequency_of(combo) <= 0.0:
                continue
            c0, c1 = combo
            tokens.append(f"{c0}{c1}")
        return ", ".join(tokens)


@dataclass
class Spot:
    """The poker spot being solved.

    Defines an ``HUNLConfig`` + two ranges + starting street + board state.
    The default constructor makes a 100 BB postflop spot on K72r (the
    ``flop_k72r_100bb`` mockup default per ``pr10a_spec.md`` §4.1) but with
    full ranges — the user immediately mutates.
    """

    board: list[Card] = field(default_factory=list)
    ranges: tuple[RangeWithFreqs, RangeWithFreqs] = field(
        default_factory=lambda: (RangeWithFreqs.full(), RangeWithFreqs.full())
    )
    stacks_bb: tuple[int, int] = (100, 100)
    sb_acts_first: bool = True  # P0 = SB = button per HUNL convention
    sb_blind: float = 0.5  # in BB
    bb_blind: float = 1.0
    ante: float = 0.0
    bet_sizes: tuple[float, ...] = (0.33, 0.75, 1.0, 1.5, 2.0)
    include_all_in: bool = True
    preflop_raise_cap: int = 4
    postflop_raise_cap: int = 3
    # Which bet sizes are checked (Q4 LOCKED: 33 / 75 / 100 / all-in default).
    # Stored explicitly because user may toggle 150% / 200% on.
    bet_sizes_checked: tuple[float, ...] = (0.33, 0.75, 1.0)
    # PR 24a: range-vs-range solve mode (v1.3.0 Plan C Stage C1 surface).
    # When True, ``SolveRunner.start`` routes through
    # ``poker_solver.range_aggregator.solve_range_vs_range`` instead of
    # the concrete-vs-concrete ``solve`` path. The point-pair fallback
    # warning at ``_pick_point_pair_hole_cards`` is suppressed in RvR
    # mode because hole-card selection is handled per-class by the
    # aggregator itself.
    rvr_mode: bool = False
    # Task #61: RvR solver-mode selector (post-PR-114 true-Nash unlock).
    # When ``rvr_mode`` is True, this field picks which engine entry the
    # worker routes through:
    #   * ``"true_nash"`` (default since 2026-05-27):
    #     ``poker_solver.range_aggregator.solve_range_vs_range_nash``
    #     (vector-form CFR — Brown's algorithm bit for bit). Yields a true
    #     joint Nash with an exploitability number. Per PR #114 the river
    #     path is now ~213× faster (interactive on river); empirical bench
    #     also shows turn ~27× faster than blueprint and flop is feasible
    #     where blueprint flop is impractical (>27 min CPU on tiny ranges).
    #   * ``"blueprint"`` (legacy opt-in fast mode for tiny river spots):
    #     the Pluribus-style
    #     ``poker_solver.range_aggregator.solve_range_vs_range`` aggregator.
    #     Fast per-spot, but produces per-class blueprint approximations,
    #     not a true joint Nash. See ``docs/aggregator_vs_true_nash_explainer.md``.
    # Ignored when ``rvr_mode`` is False (concrete solves don't go through
    # the aggregator at all).
    #
    # 2026-05-27 update: default flipped from "blueprint" to "true_nash"
    # per empirical bench (turn ~27× faster, blueprint flop impractical
    # at >27 min CPU on a tiny 3-class range). Blueprint remains opt-in
    # as a legacy fast mode for tiny river spots.
    solver_mode: str = "true_nash"
    # PR 24a: hero seat selector (v1.3.1 ``hero_player`` surface).
    # 0 = hero at P0 (SB seat / button — aggressor postflop sequencing);
    # 1 = hero at P1 (BB seat — defender). Mirrors the
    # ``range_aggregator.solve_range_vs_range`` ``hero_player`` parameter
    # default. For concrete-vs-concrete solves this swaps the rendered
    # row tab so hero's strategy lands on the front display tab; it does
    # not change the engine semantics for ``solve()`` (which is symmetric
    # in seat). For RvR solves it flips the
    # ``RangeVsRangeResult.position`` field between ``"aggressor"`` and
    # ``"defender"``.
    hero_player: int = 0
    # PR 24b §3.5: node-locking editor (v1.4.0 ``locked_strategies``
    # surface). Maps infoset key -> probability vector aligned to the
    # engine's legal-actions ordering at that node. Threaded into
    # ``poker_solver.solver.solve(..., locked_strategies=...)`` via
    # ``SolveRunner.start``. Empty dict is bit-identical to the v1.3
    # no-locks behaviour. Per ``poker_solver/solver.py:74-86`` the solver
    # raises ``ValueError`` when locks are non-empty AND the spot is a
    # ≤15 BB HUNL preflop config; the UI catches this and surfaces a
    # remediation button that retries with ``force_tree_solve=True``.
    locked_strategies: dict[str, list[float]] = field(default_factory=dict)
    # PR 24b §3.6: asymmetric ``initial_contributions`` (v1.4.1 facing-bet
    # subgame surface; PR 22 / ``docs/pr_proposals/v1_4_asymmetric_contributions.md``
    # Fix A landed the engine support). When ``villain_bet_bb > 0`` the
    # engine sees an asymmetric pot where one side has already put in
    # more chips than the other — the facing-bet player (lower
    # contribution side) acts first per the engine convention. Per the
    # engine post-fix the facing-bet side's ``to_call`` is computed
    # automatically from ``max(contributions) - min(contributions)``;
    # the UI just plumbs the seat assignment.
    #
    # ``pot_so_far_bb``: dead-money pot already in the middle BEFORE the
    # villain's bet (BB units). For a half-pot c-bet on the flop with a
    # 2 BB preflop pot: pot_so_far_bb=2.0, villain_bet_bb=1.0.
    # ``villain_bet_bb``: the bet size the bettor has put in (BB). When
    # zero (default), the engine sees a symmetric subgame and falls
    # back to the existing (bb, bb) contributions plumbing — preserving
    # every existing smoke.
    # ``bettor_is_p0``: True if P0 (SB / BTN) is the bettor (so P1
    # faces the bet); False if P1 faces. Default True matches the
    # common "BTN bets, BB defends" workflow.
    pot_so_far_bb: float = 0.0
    villain_bet_bb: float = 0.0
    bettor_is_p0: bool = True

    @property
    def starting_street(self) -> Street:
        """Derive from ``len(board)``.

        - 0 cards -> ``Street.PREFLOP``
        - 3 -> ``Street.FLOP``
        - 4 -> ``Street.TURN``
        - 5 -> ``Street.RIVER``

        Raises ``ValueError`` on 1 or 2 cards (invalid intermediate states).
        """
        n = len(self.board)
        if n == 0:
            return Street.PREFLOP
        if n == 3:
            return Street.FLOP
        if n == 4:
            return Street.TURN
        if n == 5:
            return Street.RIVER
        raise ValueError(f"invalid board length {n}: must be 0, 3, 4, or 5 cards")

    def to_hunl_config(self) -> HUNLConfig:
        """Build a ``HUNLConfig`` from this spot's fields.

        ``abstraction=None`` always in PR 10 (we visualize equilibrium
        strategies on the lossless engine; abstraction-aware visualization
        is a PR 11 concern).

        PR 10b: derives ``initial_hole_cards`` from ``self.ranges`` by
        picking the first valid combo per player that doesn't collide with
        the board or the other player's pick. This is the "point-pair"
        approximation per `pr10b_spec.md` Out-of-scope §1 (range-based
        chance dealing is a PR 9 follow-up). Without fixed hole cards the
        postflop chance node enumerates over C(52,2) * C(50,2) = 1.6M
        combos and the solve becomes intractable.
        """
        bb_cents = 100  # canonical 1 BB == 100 cents
        starting_stack_cents = self.stacks_bb[0] * bb_cents
        # For asymmetric stacks pick the larger (HUNLConfig has a single
        # ``starting_stack`` field; non-symmetric will need PR 11 work).
        if self.stacks_bb[0] != self.stacks_bb[1]:
            logger.warning(
                "Asymmetric stacks (%s) not fully supported; using P0 = %d BB",
                self.stacks_bb,
                self.stacks_bb[0],
            )
        sb_cents = int(self.sb_blind * bb_cents)
        bb_blind_cents = int(self.bb_blind * bb_cents)
        ante_cents = int(self.ante * bb_cents)
        starting_street = self.starting_street
        initial_board = tuple(self.board)

        # PR 10b: derive a single (point-pair) hole-card pair per player.
        # For preflop spots this still applies (subgame mode in PR 9).
        # If ranges are empty or fully blocked by the board, we fall back
        # to an empty tuple — which means the engine will enumerate over
        # all hole cards (slow). Production usage should always set at
        # least one valid combo per player.
        initial_hole_cards: tuple[tuple[Card, Card], tuple[Card, Card]] | tuple[()] = (
            self._pick_point_pair_hole_cards(initial_board)
        )

        if starting_street == Street.PREFLOP:
            initial_pot = 0
            initial_contributions: tuple[int, int] = (0, 0)
        elif self.villain_bet_bb > 0:
            # PR 24b §3.6: asymmetric facing-bet subgame (v1.4.1 surface).
            # ``pot_so_far_bb`` = dead-money pot already in the middle
            # BEFORE the bet; ``villain_bet_bb`` = the bet the bettor put
            # in. The bettor's contribution = pot_half + bet; the
            # facing-bet player's contribution = pot_half. The engine
            # honors the asymmetric initial_contributions per
            # ``docs/pr_proposals/v1_4_asymmetric_contributions.md`` Fix A
            # — ``to_call = max - min`` is derived; ``cur_player`` =
            # facing-bet side (lower contribution).
            pot_so_far_cents = int(self.pot_so_far_bb * bb_blind_cents)
            villain_bet_cents = int(self.villain_bet_bb * bb_blind_cents)
            pot_half_cents = pot_so_far_cents // 2
            # The "bettor" puts in pot_half + bet; the "facer" puts in
            # pot_half. Order maps onto seats via ``bettor_is_p0``.
            bettor_contrib = pot_half_cents + villain_bet_cents
            facer_contrib = pot_half_cents
            if self.bettor_is_p0:
                initial_contributions = (bettor_contrib, facer_contrib)
            else:
                initial_contributions = (facer_contrib, bettor_contrib)
            initial_pot = bettor_contrib + facer_contrib
        else:
            # Subgame: pot is whatever's been put in over the previous
            # streets. PR 10b derives an effective pot from the
            # "behind" stacks so the solve has a meaningful pot to work
            # with: behind_stack = stack_bb * 100; pot = (starting_stack -
            # behind) * 2 per player. Since the UI doesn't expose a
            # pot-size input separately, we set a single-BB ante-style pot
            # so the tree isn't degenerate. Per `pr10b_spec.md` §2: the
            # UI plumbs HUNLConfig from spot fields; ante is already
            # exposed. Use 2 * BB as a token pot when neither pot nor
            # contributions were configured.
            initial_pot = 2 * bb_blind_cents
            initial_contributions = (bb_blind_cents, bb_blind_cents)
        return HUNLConfig(
            starting_stack=starting_stack_cents,
            small_blind=sb_cents,
            big_blind=bb_blind_cents,
            ante=ante_cents,
            starting_street=starting_street,
            initial_board=initial_board,
            initial_pot=initial_pot,
            initial_contributions=initial_contributions,
            initial_hole_cards=initial_hole_cards,
            preflop_raise_cap=self.preflop_raise_cap,
            postflop_raise_cap=self.postflop_raise_cap,
            bet_size_fractions=tuple(self.bet_sizes_checked),
            include_all_in=self.include_all_in,
            abstraction=None,
        )

    def to_rvr_call_args(self) -> tuple[HUNLConfig, list[HandClass], list[HandClass]]:
        """Build the (config, hero_range, villain_range) tuple for RvR solves.

        Returns a ``HUNLConfig`` built like ``to_hunl_config()`` but with
        ``initial_hole_cards = ()`` (the aggregator overrides per-class)
        plus two lists of Pio-style hand-class strings extracted from
        ``self.ranges[0]`` and ``self.ranges[1]``. ``hero_range`` corresponds
        to ``self.ranges[hero_player]``; ``villain_range`` to the other
        seat. The aggregator's ``hero_player`` argument controls engine
        slot placement separately.

        Hand classes are derived from ``RangeWithFreqs.base_range``
        combos and deduplicated while preserving first-seen order so the
        13x13 matrix can later overlay the aggregator output deterministically.
        """
        config = self.to_hunl_config()
        # Replace initial_hole_cards with empty tuple so the aggregator
        # can override per-class. ``dataclasses.replace`` preserves every
        # other field.
        from dataclasses import replace as _replace

        config = _replace(config, initial_hole_cards=())
        hero_range = self._range_hand_classes(self.ranges[self.hero_player])
        villain_range = self._range_hand_classes(self.ranges[1 - self.hero_player])
        return config, hero_range, villain_range

    @staticmethod
    def _range_hand_classes(rw: RangeWithFreqs) -> list[HandClass]:
        """Extract a deduplicated list of Pio-style hand-class labels from a range.

        Walks the underlying ``base_range`` combos and converts each via
        ``classify_combo``; only includes combos with frequency > 0 (so
        a zeroed-out cell does not contribute). Preserves first-seen
        order so the matrix overlay is deterministic.
        """
        seen: set[HandClass] = set()
        out: list[HandClass] = []
        for combo in rw.base_range.combos:
            if rw.frequency_of(combo) <= 0.0:
                continue
            cls = classify_combo(*combo)
            if cls not in seen:
                seen.add(cls)
                out.append(cls)
        return out

    def _pick_point_pair_hole_cards(
        self, board: tuple[Card, ...]
    ) -> tuple[tuple[Card, Card], tuple[Card, Card]] | tuple[()]:
        """Pick one combo per player from ranges, avoiding board collisions.

        Returns ``()`` when either range is empty after blocker filtering,
        signalling the engine to enumerate over hole cards (slow path; the
        UI surfaces a warning when this happens).

        Selection strategy: first combo by deterministic iteration order
        (Range stores combos sorted by (-rank, suit)) that doesn't
        collide with the board or the other player's pick.
        """
        used: set[Card] = set(board)
        picks: list[tuple[Card, Card]] = []
        for player in range(2):
            range_obj = self.ranges[player].base_range
            chosen: tuple[Card, Card] | None = None
            for combo in range_obj.combos:
                c0, c1 = combo
                if c0 in used or c1 in used:
                    continue
                chosen = (c0, c1)
                used.add(c0)
                used.add(c1)
                break
            if chosen is None:
                # Range is empty or fully blocked. Return () to defer to
                # engine enumeration; the caller surfaces a warning.
                return ()
            picks.append(chosen)
        return (picks[0], picks[1])


@dataclass
class SolveSession:
    """A configuration + worker reference + result snapshot for one solve."""

    spot: Spot
    iterations: int
    log_every: int
    backend: str  # "python" or "rust"
    started_at: float  # ``time.time()``
    runner: SolveRunner


@dataclass
class UIPrefs:
    """Persisted user preferences."""

    dark_mode: str = "auto"  # "auto" | "light" | "dark"
    panel_widths: dict[str, int] = field(
        default_factory=lambda: {"left": 320, "bottom": 240}
    )
    matrix_show_frequencies: bool = True
    tree_reach_filter: float = 0.01  # Q6 LOCKED per ``pr10a_spec.md`` §0.1
    # Q7 banner can be dismissed AFTER first solve; remember dismissal.
    mock_banner_dismissed: bool = False
    # Onboarding gate (Risk 6: state.json absence is one signal; this flag
    # is the persistent one to prevent re-trigger when user clears history).
    onboarding_completed: bool = False
    # Chart axis preference (log default per spec §13 decision 8).
    chart_log_scale: bool = True
    # Task #55: preflop-chart selected cell (transient, NOT persisted to
    # state.json). Tracks which 13x13 cell the user last clicked so the
    # detail panel re-renders on page refresh. The field lives on
    # ``UIPrefs`` purely as a convenient slot — the serializer skips it
    # (see ``_serialize_state``).
    preflop_chart_selected_class: str | None = None
    # Task #55: also persist the matrix-selected hand class for the
    # postflop range-matrix combo inspector. The field already lived on
    # ``UIPrefs`` as a dynamic attribute set by
    # ``ui/views/range_matrix._on_cell_click``; declaring it here keeps
    # dataclasses.replace() happy when tests construct fresh prefs.
    matrix_selected_hand_class: str | None = None


# --------------------------------------------------------------------------- #
# SolveRunner — the worker-thread orchestrator
# --------------------------------------------------------------------------- #


# Terminal lifecycle states: the logical solve is finished and a new one may
# start (the worker thread may linger for a few ms before the OS reaps it,
# which is why the start() guard must NOT key off raw thread liveness alone).
_TERMINAL_STATUSES: frozenset[str] = frozenset({"idle", "done", "stopped", "error"})


class SolveInFlightError(RuntimeError):
    """Raised by ``SolveRunner.start*`` when a solve is *genuinely* running.

    Subclasses :class:`RuntimeError` so existing ``except RuntimeError``
    call sites in ``ui/app.py`` keep working unchanged. Carries a clean,
    user-presentable ``.message`` so the UI can surface a friendly banner
    instead of the raw internal "call stop() and wait..." string.
    """

    def __init__(self, message: str | None = None) -> None:
        self.message = message or (
            "A solve is already running. Stop it before starting a new one."
        )
        super().__init__(self.message)


# --------------------------------------------------------------------------- #
# Bug 3 — pre-solve tree-size guard (postflop memory wall)
# --------------------------------------------------------------------------- #
#
# A wide-range flop solve is uncancellable: the Rust engine builds the full
# postflop game tree (``HUNLTree::build``) BEFORE the iteration loop starts,
# and that build can run for many minutes on a flop (two remaining board cards
# => ~47 * 46 runouts, each carrying a full betting subtree across three
# streets). During the build ``iteration`` is legitimately 0 and ``should_stop``
# is never polled, so the UI shows "Iterations: 0 / Running" indefinitely and
# the Stop button does nothing. The memory wall here is fundamental (see the
# postflop-memory-wall memory note): we do NOT try to make wide flop solves
# converge. Instead we fail fast with an actionable message.
#
# The cost estimate below is intentionally a SIMPLE, CONSERVATIVE heuristic —
# its only job is to cleanly separate "interactive subgame" (river/turn, or a
# flop with very few bet sizes) from "will hang for minutes" (a flop with the
# default bet menu). It is deliberately easy to read and tune:
#
#   cost ~= board_runouts * (actions_per_node ** betting_plies)
#
# where ``board_runouts`` is the product of remaining-card choices across the
# remaining streets (the dominant multiplier), ``actions_per_node`` is the
# branching factor at a decision node, and ``betting_plies`` is a coarse proxy
# for how deep the per-runout betting subtree goes.
#
# TUNING: bump ``TREE_SIZE_BUDGET`` up to allow larger solves, or down to be
# stricter. The measured separation on an M-series mac: a flop with 3 bet
# sizes + all-in took >130 s just to BUILD the tree (loop never started),
# while a turn/river point-pair subgame is interactive (sub-second to a few
# seconds). The default budget is set comfortably below the flop cost and
# comfortably above the turn cost.

# Maximum estimated tree cost (unitless heuristic score) the UI will launch.
# Above this, ``SolveRunner.start`` refuses with :class:`SolveTooLargeError`.
TREE_SIZE_BUDGET: float = 5.0e6

# Approximate count of distinct next-card choices when a street's board card
# is dealt (52 - cards already on board/in hands). A coarse constant keeps the
# heuristic simple; the exact value (47 vs 45) does not change the verdict.
_CARDS_PER_BOARD_DEAL: int = 47

# Remaining board-card layers to enumerate from each starting street. Flop has
# two (turn + river), turn has one (river), river has none. This is THE
# dominant cost driver — each extra layer multiplies the tree by ~47x.
_REMAINING_BOARD_DEALS: dict[Street, int] = {
    Street.FLOP: 2,
    Street.TURN: 1,
    Street.RIVER: 0,
}

# Coarse betting-subtree depth proxy per remaining street (fold/call + raises
# up to the cap). Multiplied across streets-with-betting to get total plies.
_BETTING_PLIES_PER_STREET: int = 2


class SolveTooLargeError(RuntimeError):
    """Raised by ``SolveRunner.start`` when the estimated tree is too large.

    Subclasses :class:`RuntimeError` so the existing ``except RuntimeError``
    handlers in ``ui/app.py`` catch it without code changes. Carries a clean,
    user-presentable ``.message`` (Bug 3): the postflop tree-build for a wide
    flop spot hangs for minutes before the iteration loop even starts and is
    uncancellable, so we refuse it up front with concrete remediations.
    """

    def __init__(self, message: str | None = None, *, estimated_cost: float = 0.0):
        self.estimated_cost = estimated_cost
        self.message = message or (
            "This solve is too large to finish in reasonable time/memory. "
            "Narrow the ranges, reduce the bet sizes, or solve a turn/river "
            "subgame instead of the flop."
        )
        super().__init__(self.message)


def estimate_postflop_tree_cost(config: HUNLConfig) -> float:
    """Return a conservative, unitless cost estimate for a postflop solve.

    Heuristic (see the module comment above ``TREE_SIZE_BUDGET``):

        cost = board_runouts * (actions_per_node ** betting_plies)

    * ``board_runouts`` = ``_CARDS_PER_BOARD_DEAL ** remaining_board_deals`` —
      the product of next-card choices across the remaining streets. This is
      the dominant term: a flop (2 deals) is ~47x bigger than a turn, ~2200x
      bigger than a river.
    * ``actions_per_node`` = number of bet sizes + all-in + {fold, call} — the
      branching factor at a betting decision node.
    * ``betting_plies`` = ``_BETTING_PLIES_PER_STREET`` times the number of
      streets that still have a betting round (remaining_board_deals + 1).

    Preflop configs return ``0.0`` (the UI never routes preflop through this
    guard; the preflop chart path is a separate, bounded engine).

    The estimate is intentionally coarse and pessimistic for the flop — its
    only job is to separate "interactive subgame" from "uncancellable hang".
    """
    street = config.starting_street
    remaining_deals = _REMAINING_BOARD_DEALS.get(street)
    if remaining_deals is None:
        # Preflop / showdown / anything not in the postflop map: not our guard.
        return 0.0

    # Branching factor at a decision node: each checked bet size, optionally
    # all-in, plus fold and call/check.
    num_bet_sizes = len(getattr(config, "bet_size_fractions", ()) or ())
    actions_per_node = num_bet_sizes + (1 if config.include_all_in else 0) + 2

    # Number of streets that still have a betting round (current + each future
    # street reached by a board deal).
    betting_streets = remaining_deals + 1
    betting_plies = _BETTING_PLIES_PER_STREET * betting_streets

    board_runouts = float(_CARDS_PER_BOARD_DEAL) ** remaining_deals
    betting_subtree = float(actions_per_node) ** betting_plies
    return board_runouts * betting_subtree


def exceeds_tree_budget(
    config: HUNLConfig, *, budget: float = TREE_SIZE_BUDGET
) -> bool:
    """Return True iff the estimated postflop tree cost exceeds ``budget``.

    Thin predicate over :func:`estimate_postflop_tree_cost` so callers (and
    tests) can check the verdict without re-deriving the threshold.
    """
    return estimate_postflop_tree_cost(config) > budget


class SolveRunner:
    """Owns one background worker thread + cancellation flags + progress snapshot.

    Lifecycle (per ``pr10a_spec.md`` §6.1):

        idle -> running -> (paused -> running)* -> done | stopped | error

    Thread safety:
        Every cross-thread read goes through ``self._lock`` OR reads a single
        atomic field (int / str / float). ``self.expl_history`` is
        append-only from the worker; the UI thread reads its current length
        and slices ``[last_seen_len:]`` — do NOT mutate from the UI thread.
    """

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._pause_event: threading.Event = threading.Event()
        self._stop_event: threading.Event = threading.Event()
        self._lock: threading.Lock = threading.Lock()
        self.result: SolveResult | None = None
        self.iteration: int = 0
        self.expl_history: list[tuple[int, float]] = []  # (iter, expl_mBB_per_pot)
        self.status: str = "idle"  # idle | running | paused | done | stopped | error
        self.error: BaseException | None = None
        self.started_at: float = 0.0
        self.partial_report: MemoryReport | None = None
        # PR 24a: range-vs-range result snapshot (None when concrete solve).
        # Populated by the worker when ``start(...)`` is invoked with
        # ``rvr_mode=True``; the matrix renderer reads it to overlay
        # ``per_class_strategy`` onto the 13x13 grid instead of the
        # point-pair concrete strategy.
        self.rvr_result: RangeVsRangeResult | None = None
        # Task #61: true-Nash RvR result snapshot (None when concrete solve
        # or when ``solver_mode == "blueprint"``). Populated by the worker
        # when ``start(...)`` is invoked with ``rvr_mode=True`` AND
        # ``solver_mode="true_nash"``. The result carries an exploitability
        # number + per-class projection; ``ui/views/run_panel.py`` reads
        # ``exploitability`` and ``wall_clock_s`` to populate the result
        # readouts. The matrix renderer treats this dataclass duck-typed
        # the same as ``RangeVsRangeResult`` (both expose
        # ``per_class_strategy`` keyed by hand class).
        self.nash_result: RangeVsRangeNashResult | None = None
        # Task #57: chained orchestrator result snapshot (None when concrete
        # solve or RvR / blueprint paths). Populated by the worker when
        # ``start(...)`` is invoked with ``solver_mode="chained"``; consumed
        # by ``ui/views/chained_tab.py`` to render the 13x13 preflop chart
        # and lazily fetch the postflop subgame solves via
        # ``ChainedSolveResult.solve_postflop``. The forward-reference avoids
        # importing ``poker_solver.chained`` at module load — the chained
        # module is only needed inside ``_run_chained_path``.
        self.chained_result: Any | None = None
        # PR 24a §3.7: tier-slider plumbing. ``run_panel._wrap_solve``
        # sets these on each click; ``ui/app.py:_on_solve`` reads them
        # when calling ``start(...)``. Kept off ``SolveSession`` to avoid
        # widening that dataclass for one PR.
        self._pending_target_expl: float | None = None
        self._pending_tier_label: str = "Standard"
        # PR 24b §3.5: node-locking plumbing. ``ui/app.py:_on_solve``
        # reads these when calling ``start(...)``. ``_pending_force_tree_solve``
        # is set to True when the user clicks the remediation button on
        # the push/fold ValueError notify; the next solve retries with
        # the override.
        self._pending_locked_strategies: dict[str, list[float]] | None = None
        self._pending_force_tree_solve: bool = False
        # ETA-extrapolation fields (smoke 20 / pr10a_spec.md §6 edge #1).
        # Defaults are `None` so `compute_eta()` returns `None` when the
        # runner is idle; the worker sets them once it starts.
        self.start_time_monotonic: float | None = None
        self.current_time_monotonic: float | None = None
        self.target_iterations: int | None = None
        # Task #55: preflop chart binding. Populated by
        # ``_run_preflop_chart_path`` when ``start_preflop_chart(...)`` is
        # invoked. ``preflop_chart_result`` carries the engine's
        # ``solve_hunl_preflop_rvr`` output projected to a per-class
        # action-frequency dict (see
        # ``ui/views/preflop_chart.py:project_chart``).
        # ``_mode`` lets the UI render code distinguish which solve path
        # is in flight (so the polling timer doesn't claim a postflop
        # solve's expl history for the preflop chart).
        self.preflop_chart_result: dict[str, Any] | None = None
        self._mode: str = ""
        # Per-click action-menu plumbing for the preflop chart. The
        # input panel writes these on Solve; ``start_preflop_chart``
        # reads them.
        self._pending_preflop_chart_opens: list[float] | None = None
        self._pending_preflop_chart_mults: list[float] | None = None
        self._pending_preflop_chart_iterations: int | None = None
        # Task #68 Phase 6: blueprint-vs-live routing metadata. The
        # preflop chart + chained tab read these to render a "source"
        # badge under each chart so the user can see whether the
        # displayed strategy came from a precomputed asset (instant),
        # an interpolation across two anchor shards (instant), or a
        # live solve (seconds). ``preflop_route_info`` covers the
        # preflop chart; ``chained_preflop_route_info`` and
        # ``chained_postflop_route_info`` cover the chained tab's two
        # stages. The dataclass lives in ``ui.blueprint_router``.
        self.preflop_route_info: Any | None = None
        self.chained_preflop_route_info: Any | None = None
        self.chained_postflop_route_info: Any | None = None

    def start(
        self,
        game: HUNLPoker,
        iterations: int,
        *,
        log_every: int,
        dcfr_kwargs: dict[str, Any] | None = None,
        # v1.11 UI: default to the Rust production tier. ``"python"`` is no
        # longer a user-visible choice — it survives only as a SILENT
        # fallback inside the dispatch when the Rust binding is genuinely
        # unavailable (see ``_dispatch_solve`` / ``poker_solver.solver.solve``).
        # Callers may still pass ``backend="python"`` for tests; production
        # postflop solves are forced onto Rust regardless of this value.
        backend: str = "rust",
        memory_budget_gb: float = 14.0,
        target_exploitability: float | None = None,
        seed: int | None = None,
        # Test-injection hook: forwarded to ``mock_solve`` for failure-mode
        # exercise. Agent C's smoke tests pass these; production users
        # never see them.
        mock_latency_ms: int | None = None,
        mock_failure_mode: str | None = None,
        # PR 24a: range-vs-range mode. When set, ``rvr_hero_range`` and
        # ``rvr_villain_range`` MUST also be supplied; the worker routes
        # through ``poker_solver.range_aggregator.solve_range_vs_range``
        # using ``game.config`` (with ``initial_hole_cards = ()``) as the
        # template. ``hero_player`` flips the engine seat per
        # ``range_aggregator.solve_range_vs_range``.
        rvr_mode: bool = False,
        rvr_hero_range: list[HandClass] | None = None,
        rvr_villain_range: list[HandClass] | None = None,
        rvr_hero_player: int = 0,
        # Task #61: true-Nash solver-mode dispatch (post-PR-114 perf unlock).
        # When ``rvr_mode`` is True, ``solver_mode == "true_nash"`` routes the
        # worker through ``solve_range_vs_range_nash`` (vector-form CFR);
        # ``"blueprint"`` selects the legacy Pluribus aggregator path
        # (kept for tiny-river opt-in / backward compat). The value is
        # ignored when ``rvr_mode`` is False. Must be one of ``"blueprint"``
        # or ``"true_nash"``; any other value raises ValueError so
        # misconfigurations surface early. Default flipped to ``"true_nash"``
        # on 2026-05-27 per empirical bench.
        solver_mode: str = "true_nash",
        # PR 24b §3.5: node-locking. ``locked_strategies`` maps infoset
        # key -> probability vector aligned to the engine's legal-action
        # ordering at that node. Empty/None falls through to existing
        # behaviour. ``force_tree_solve`` escapes the push/fold
        # short-circuit when locks are set on a ≤15 BB preflop config
        # (see ``poker_solver/solver.py:74-86``).
        locked_strategies: dict[str, list[float]] | None = None,
        force_tree_solve: bool = False,
    ) -> None:
        """Spawn the worker thread.

        Raises :class:`SolveInFlightError` (a ``RuntimeError`` subclass with
        a friendly ``.message``) if a solve is *genuinely* running. A
        finished-but-not-yet-reaped worker thread is joined first and does
        NOT block a new start (see :meth:`_reap_finished_worker`).

        Raises :class:`SolveTooLargeError` (Bug 3) when the estimated postflop
        tree is too large to build in reasonable time/memory. The check runs
        BEFORE the worker thread is spawned (and before any tree-building) so
        an oversized flop fails fast with an actionable message instead of
        hanging uncancellably inside ``HUNLTree::build``. Only the concrete
        postflop path is guarded; the RvR aggregator and chained orchestrator
        manage their own subgame budgets.
        """
        self._reap_finished_worker()
        if self.is_running:
            raise SolveInFlightError()
        if rvr_mode and (rvr_hero_range is None or rvr_villain_range is None):
            raise ValueError(
                "rvr_mode=True requires rvr_hero_range and rvr_villain_range "
                "to be non-None lists of hand-class strings."
            )
        if solver_mode not in ("blueprint", "true_nash", "chained"):
            raise ValueError(
                f"solver_mode must be 'blueprint', 'true_nash', or 'chained'; "
                f"got {solver_mode!r}."
            )
        # Bug 3: refuse an oversized concrete postflop solve up front. The
        # flop tree-build hangs for minutes before the iteration loop starts
        # and is uncancellable; estimate the cost and bail with a clear,
        # actionable message rather than freezing the UI. The RvR / chained
        # paths run their own bounded subgames, and the mock path (smoke-test
        # injection via ``mock_latency_ms`` / ``mock_failure_mode``) never
        # builds a real tree — so we only gate the concrete, real-engine
        # postflop dispatch here.
        is_mock = mock_latency_ms is not None or mock_failure_mode is not None
        is_concrete_postflop = (
            not rvr_mode and solver_mode != "chained" and not is_mock
        )
        if is_concrete_postflop and exceeds_tree_budget(game.config):
            cost = estimate_postflop_tree_cost(game.config)
            raise SolveTooLargeError(
                "This flop solve is too large to finish in reasonable "
                "time/memory (the game tree would take minutes to build and "
                "cannot be cancelled mid-build). Narrow the ranges, reduce the "
                "checked bet sizes, or solve a turn/river subgame instead of "
                "the flop.",
                estimated_cost=cost,
            )
        # Reset state for the new run. Clearing the events here (not in the
        # worker) guarantees a clean slate even if a prior solve set stop/pause
        # and was reaped above without the worker clearing them.
        self._pause_event.clear()
        self._stop_event.clear()
        with self._lock:
            self.result = None
            self.iteration = 0
            self.expl_history = []
            self.status = "running"
            self.error = None
            self.started_at = time.time()
            self.partial_report = None
            self.rvr_result = None
            self.nash_result = None
            # Task #57: chained orchestrator result holder. Cleared on
            # every start so a previous chain solve never leaks into the
            # next click. The ``chained_tab`` view reads this attribute
            # directly to drive the 13x13 preflop chart + the lazy postflop
            # subgame display.
            self.chained_result = None
            # Task #68 Phase 6: clear stale chained route info so a
            # previous solve's badges don't appear under the next solve.
            self.chained_preflop_route_info = None
            self.chained_postflop_route_info = None
            # Stash the active mode so views can tell whether to project
            # their result holder (mirrors the preflop_chart pattern).
            self._mode = "chained" if solver_mode == "chained" else self.__dict__.get("_mode", "")
        config = game.config
        self._thread = threading.Thread(
            target=self._worker,
            kwargs={
                "config": config,
                "iterations": iterations,
                "log_every": log_every,
                "dcfr_kwargs": dcfr_kwargs,
                "backend": backend,
                "memory_budget_gb": memory_budget_gb,
                "target_exploitability": target_exploitability,
                "seed": seed,
                "mock_latency_ms": mock_latency_ms,
                "mock_failure_mode": mock_failure_mode,
                "rvr_mode": rvr_mode,
                "rvr_hero_range": rvr_hero_range,
                "rvr_villain_range": rvr_villain_range,
                "rvr_hero_player": rvr_hero_player,
                "solver_mode": solver_mode,
                "locked_strategies": locked_strategies,
                "force_tree_solve": force_tree_solve,
            },
            daemon=True,
            name="poker-solver-ui-worker",
        )
        self._thread.start()

    def try_blueprint_preflop_chart(
        self,
        *,
        stack_bb: int,
        ante: str | float | int,
        action_history: str = "",
    ) -> bool:
        """Try to populate the preflop chart from the blueprint asset (task #68 Phase 6).

        Looks up the chart via :class:`ui.blueprint_router.BlueprintRouter`.
        On a blueprint or interpolated hit, stashes:
          * ``self.preflop_chart_result`` — the per-class dict the chart
            widget already consumes.
          * ``self.preflop_route_info`` — the source/wall-time/confidence
            badge data.

        Returns ``True`` when the blueprint covered the request (caller
        should NOT trigger a live solve). Returns ``False`` when the
        blueprint has no coverage at this (stack, ante) and the caller
        must fall back to the live solve path
        (:meth:`start_preflop_chart`).

        This is a SYNCHRONOUS call — blueprint shard loads are tiny
        (~1-15 MB) and the lookup completes in microseconds once warm.
        No worker thread, no progress polling. The polling timer in
        ``ui/app.py`` still fires on the ``preflop_chart_result``
        identity change and refreshes the chart widget.
        """
        from ui.blueprint_router import (
            BlueprintRouter,
            SourceLabel,
            default_asset_dir,
        )

        router = BlueprintRouter.from_asset_dir(default_asset_dir())
        if router is None:
            with self._lock:
                # Surface a "live only" badge so the user understands why
                # the source row says "live" even before they click solve.
                self.preflop_route_info = None
            return False

        info = router.lookup_chart(
            stack_bb=int(stack_bb),
            ante=ante,
            action_history=action_history,
        )
        if info.source == SourceLabel.LIVE or not info.per_class:
            with self._lock:
                self.preflop_route_info = info  # carries the live hint
            return False

        # We have blueprint coverage — synthesize a chart_result the
        # preflop_chart widget already knows how to render.
        action_labels: list[str] = []
        for action_map in info.per_class.values():
            for k in action_map:
                if k not in action_labels:
                    action_labels.append(k)
        chart_result: dict[str, Any] = {
            "per_class": info.per_class,
            "actions": action_labels,
            "iterations": 0,
            "wallclock_seconds": float(info.wall_time_s),
            "decision_node_count": len(info.per_class),
            "strategy_entry_count": sum(
                len(m) for m in info.per_class.values()
            ),
            "source": info.source.value,
        }
        with self._lock:
            self.preflop_chart_result = chart_result
            self.preflop_route_info = info
            self.status = "done"
            self._mode = "preflop_chart"
            self.iteration = 0
            self.target_iterations = 1
            self.start_time_monotonic = time.monotonic()
            self.current_time_monotonic = self.start_time_monotonic
        return True

    def start_preflop_chart(
        self,
        config: HUNLConfig,
        *,
        iterations: int = 500,
        open_sizes_bb: list[float] | None = None,
        reraise_multipliers: list[float] | None = None,
        hero_holes: list[tuple[int, int]] | None = None,
        villain_holes: list[tuple[int, int]] | None = None,
        alpha: float = 1.5,
        beta: float = 0.0,
        gamma: float = 2.0,
    ) -> None:
        """Spawn the worker thread for the preflop-chart engine call (task #55).

        Dispatches to ``poker_solver._rust.solve_hunl_preflop_rvr`` (PR
        #122). The Rust binding solves the full HUNL preflop tree with
        all 1326 hole-card combos per player active and collapses each
        postflop runout to a single equity-leaf value per
        (hero_class, villain_class, suit_variant) via the precomputed
        169x169x3 table at ``assets/preflop_equity_169x169.npz``.

        Raises :class:`SolveInFlightError` if a solve is *genuinely* running
        (a finished-but-not-yet-reaped worker is joined first and does not
        block). Raises ``ImportError`` if the Rust extension was built
        without ``solve_hunl_preflop_rvr``.
        """
        self._reap_finished_worker()
        if self.is_running:
            raise SolveInFlightError()
        self._pause_event.clear()
        self._stop_event.clear()
        # Task #68 Phase 6: clear any stale blueprint route info; the
        # live-solve worker will populate ``preflop_route_info`` to LIVE
        # on success (so the chart's source badge says "live N iter")
        # and clear it on failure (so the badge falls back to the
        # router's pre-solve hint, if any).
        with self._lock:
            self.result = None
            self.iteration = 0
            self.expl_history = []
            self.status = "running"
            self.error = None
            self.started_at = time.time()
            self.partial_report = None
            self.rvr_result = None
            self.nash_result = None
            self.preflop_chart_result = None
            self._mode = "preflop_chart"
            self.target_iterations = iterations
            self.start_time_monotonic = time.monotonic()
            self.current_time_monotonic = self.start_time_monotonic
            # Surface "live" pre-emptively so the badge updates the
            # moment the user clicks Solve; the worker overwrites with
            # the final wall_time when it finishes.
            from ui.blueprint_router import RouteInfo, SourceLabel

            self.preflop_route_info = RouteInfo(
                source=SourceLabel.LIVE,
                wall_time_s=0.0,
                confidence=f"{iterations} iter rust_preflop_rvr (running)",
            )

        self._thread = threading.Thread(
            target=self._run_preflop_chart_path,
            kwargs={
                "config": config,
                "iterations": iterations,
                "open_sizes_bb": open_sizes_bb,
                "reraise_multipliers": reraise_multipliers,
                "hero_holes": hero_holes,
                "villain_holes": villain_holes,
                "alpha": alpha,
                "beta": beta,
                "gamma": gamma,
            },
            daemon=True,
            name="poker-solver-preflop-chart-worker",
        )
        self._thread.start()

    def _run_preflop_chart_path(
        self,
        *,
        config: HUNLConfig,
        iterations: int,
        open_sizes_bb: list[float] | None,
        reraise_multipliers: list[float] | None,
        hero_holes: list[tuple[int, int]] | None,
        villain_holes: list[tuple[int, int]] | None,
        alpha: float,
        beta: float,
        gamma: float,
    ) -> None:
        """Worker body for the preflop chart path (task #55).

        Calls ``_rust.solve_hunl_preflop_rvr`` and projects the flat
        ``average_strategy`` dict into a per-class action-frequency
        dict that ``ui/views/preflop_chart.py:project_chart`` consumes.

        The Rust binding does not stream per-iteration callbacks; we
        push a (0, iter) marker onto ``expl_history`` so the polling
        UI can show "running -> done" transitions.
        """
        try:
            from poker_solver import _rust as _rust_module  # type: ignore[import-untyped]
        except (ImportError, ModuleNotFoundError) as exc:
            with self._lock:
                self.error = ImportError(
                    "poker_solver._rust extension not available. "
                    "Rebuild via `maturin develop --release` from the project root."
                )
                self.status = "error"
            logger.exception("preflop chart: _rust import failed: %s", exc)
            return
        rust_solve = getattr(_rust_module, "solve_hunl_preflop_rvr", None)
        if rust_solve is None:
            with self._lock:
                self.error = ImportError(
                    "poker_solver._rust.solve_hunl_preflop_rvr not found. "
                    "Rebuild via `maturin develop --release` (PR #122 binding "
                    "required)."
                )
                self.status = "error"
            return

        # Equity table path: ship in assets/, repo-relative.
        from pathlib import Path as _Path

        repo_root = _Path(__file__).resolve().parents[1]
        equity_path = repo_root / "assets" / "preflop_equity_169x169.npz"

        try:
            config_json = _serialize_hunl_config(config)
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self.error = exc
                self.status = "error"
            logger.exception("preflop chart: config serialization failed")
            return

        # Push a starting marker.
        with self._lock:
            self.expl_history.append((0, float(iterations)))

        try:
            rust_out = rust_solve(
                config_json,
                str(equity_path),
                int(iterations),
                float(alpha),
                float(beta),
                float(gamma),
                list(open_sizes_bb) if open_sizes_bb else None,
                list(reraise_multipliers) if reraise_multipliers else None,
                hero_holes,
                villain_holes,
            )
        except (ValueError, RuntimeError, OSError) as exc:
            logger.exception(
                "preflop chart: solve_hunl_preflop_rvr failed with %s",
                type(exc).__name__,
            )
            with self._lock:
                self.error = exc
                self.status = "error"
            return
        except BaseException as exc:  # noqa: BLE001
            logger.exception(
                "preflop chart: solve_hunl_preflop_rvr raised unexpected exception"
            )
            with self._lock:
                self.error = exc
                self.status = "error"
            return

        # Project into a per-class chart dict.
        chart_result = self._build_preflop_chart_summary(rust_out)
        with self._lock:
            self.preflop_chart_result = chart_result
            self.iteration = int(chart_result.get("iterations", iterations))
            self.current_time_monotonic = time.monotonic()
            if self._stop_event.is_set():
                self.status = "stopped"
            else:
                self.status = "done"
            # Task #68 Phase 6: finalize the route info with the
            # real wall time so the badge displays the right number.
            from ui.blueprint_router import RouteInfo, SourceLabel

            wall_s = float(chart_result.get("wallclock_seconds", 0.0))
            iters = int(chart_result.get("iterations", iterations))
            self.preflop_route_info = RouteInfo(
                source=SourceLabel.LIVE,
                wall_time_s=wall_s,
                confidence=f"{iters} iter rust_preflop_rvr",
            )

    @staticmethod
    def _project_preflop_by_line(
        rust_out: dict[str, Any],
    ) -> dict[str, dict[str, dict[str, float]]]:
        """Project the full preflop output into a per-LINE, per-class summary.

        Unlike :meth:`_build_preflop_chart_summary` (which discards every
        node except the root open), this keeps EVERY action line the engine
        produced. Returns a nested mapping::

            { history_str -> { hand_class -> { action_label -> prob } } }

        where ``history_str`` is the action-line suffix from the Rust infoset
        key (``""`` is the root / SB open; deeper lines are non-empty, e.g.
        the BB's response after an open, a 3-bet node, etc.). Within a line,
        probabilities are averaged across the concrete combos that map to the
        same hand class (matching the root projection's class-level mean).

        This is the data source for :meth:`available_preflop_lines` and
        :meth:`preflop_chart_summary_for_line`; UI code (a later chart agent)
        consumes it to render deeper lines (BB-call / 3-bet / 4-bet) instead
        of only the open range.
        """
        average_strategy = rust_out.get("average_strategy", {})
        # history -> class -> (running sum of prob vectors, count)
        by_line: dict[str, dict[str, tuple[list[float], int]]] = {}
        for key, probs in average_strategy.items():
            if not probs:
                continue
            hole_str, hist = _split_preflop_key(str(key))
            if hole_str is None:
                continue
            cls = _hand_class_from_hole_str(hole_str)
            if cls is None:
                continue
            line_slot = by_line.setdefault(hist, {})
            prev = line_slot.get(cls)
            vec = [float(p) for p in probs]
            if prev is None:
                line_slot[cls] = (vec, 1)
            else:
                acc, cnt = prev
                if len(acc) == len(vec):
                    line_slot[cls] = ([a + b for a, b in zip(acc, vec)], cnt + 1)
                # else: ragged action counts within a class — keep the first.

        out: dict[str, dict[str, dict[str, float]]] = {}
        for hist, class_map in by_line.items():
            line_out: dict[str, dict[str, float]] = {}
            for cls, (acc, cnt) in class_map.items():
                n = len(acc)
                if n == 0 or cnt == 0:
                    continue
                labels = _action_labels_for_count(n)
                line_out[cls] = {labels[i]: acc[i] / cnt for i in range(n)}
            if line_out:
                out[hist] = line_out
        return out

    @staticmethod
    def _build_preflop_chart_summary(rust_out: dict[str, Any]) -> dict[str, Any]:
        """Project ``_rust.solve_hunl_preflop_rvr`` output into a chart summary.

        The Rust output's ``average_strategy`` dict maps
        ``"{hole_str}{key_suffix}" -> [probs]``. The ``key_suffix`` is
        the canonical infoset-key shape ``"||p|<history>"``; the root
        decision (SB's first action) is the entry whose ``<history>``
        is empty — i.e. the suffix ends with the player slot only.

        This returns the ROOT open range only (default behavior, unchanged).
        The full per-line projection (deeper BB-call / 3-bet / 4-bet nodes)
        is available via :meth:`_project_preflop_by_line` /
        :meth:`preflop_chart_summary_for_line`.

        Returns a chart_result dict with keys ``per_class``, ``actions``,
        ``iterations``, ``wallclock_seconds``, ``decision_node_count``,
        ``strategy_entry_count``, plus ``available_lines`` (sorted list of
        every history suffix the projection found, so the UI can enumerate
        deeper lines without re-projecting).
        """
        iterations = int(rust_out.get("iterations", 0))
        wallclock = float(rust_out.get("wallclock_seconds", 0.0))
        decision_count = int(rust_out.get("decision_node_count", 0))
        entry_count = int(rust_out.get("strategy_entry_count", 0))

        by_line = SolveRunner._project_preflop_by_line(rust_out)
        available_lines = sorted(by_line, key=lambda h: (len(h), h))
        # Root = shortest history line (the SB open decision).
        root_line = available_lines[0] if available_lines else ""
        per_class = by_line.get(root_line, {})

        # Derive the action-label list from the widest root entry.
        action_count_at_root = max(
            (len(m) for m in per_class.values()), default=0
        )
        action_labels = _action_labels_for_count(action_count_at_root)

        return {
            "per_class": per_class,
            "actions": action_labels,
            "iterations": iterations,
            "wallclock_seconds": wallclock,
            "decision_node_count": decision_count,
            "strategy_entry_count": entry_count,
            "available_lines": available_lines,
            # Full per-line projection so deeper lines (BB-call / 3-bet /
            # 4-bet) are reachable via preflop_chart_summary_for_line(line)
            # without re-running the solve. Keyed by history suffix.
            "_by_line": by_line,
        }

    def available_preflop_lines(self) -> list[str]:
        """Return every preflop action line the last chart solve produced.

        Lines are history-suffix strings from the Rust infoset keys, sorted
        by depth then lexically so the root (``""`` or shortest) comes first
        and deeper lines (BB-call / 3-bet / 4-bet) follow. Returns ``[]``
        when no preflop chart result is available.

        Consume the list, then call :meth:`preflop_chart_summary_for_line`
        with any entry to get that line's per-class strategy.
        """
        result = self.preflop_chart_result
        if not result:
            return []
        lines = result.get("available_lines")
        if isinstance(lines, list):
            return list(lines)
        return []

    def preflop_chart_summary_for_line(
        self, line: str | None = None
    ) -> dict[str, dict[str, float]]:
        """Return the per-class strategy for a specified preflop action line.

        ``line`` is one of the history suffixes from
        :meth:`available_preflop_lines` (e.g. ``""`` for the root SB open, or
        a deeper line for BB-call / 3-bet / 4-bet nodes). When ``line`` is
        ``None`` (the default) the ROOT open range is returned — identical to
        ``self.preflop_chart_result["per_class"]`` so existing callers are
        unaffected.

        Returns ``{ hand_class -> { action_label -> probability } }``. An
        unknown ``line`` (or no chart result) yields an empty dict.
        """
        result = self.preflop_chart_result
        if not result:
            return {}
        if line is None:
            return dict(result.get("per_class", {}))
        # Re-project lazily; the raw rust output isn't retained on the
        # runner, but the projection was stashed under "available_lines".
        # We rebuild from the cached per-line map if present, else fall back
        # to the root per_class for line == root.
        by_line = result.get("_by_line")
        if isinstance(by_line, dict):
            return dict(by_line.get(line, {}))
        # No cached per-line map (older result shape) — only root is known.
        available = result.get("available_lines") or []
        if available and line == available[0]:
            return dict(result.get("per_class", {}))
        return {}

    def pause(self) -> None:
        """Set the pause flag.

        Per ``pr10a_spec.md`` §6.1 / §7.5 caveat: ``mock_solve`` is a single
        call, so "pause" means the worker thread sleeps between snapshots.
        The mock checks ``_CANCEL_FLAG`` once per snapshot; for pause we
        toggle ``self._pause_event``. The user sees "pausing..." until the
        next snapshot lands; then ``status == 'paused'``.
        """
        self._pause_event.set()
        with self._lock:
            if self.status == "running":
                self.status = "paused"

    def resume(self) -> None:
        """Clear the pause flag."""
        self._pause_event.clear()
        with self._lock:
            if self.status == "paused":
                self.status = "running"

    def stop(self) -> None:
        """Set the stop flag.

        For real solves (PR 10b): cancellation is checked between solver
        chunks (granularity = `log_every` iterations); the worker exits
        within ONE chunk after `stop()` returns.

        For mock solves (smoke tests still on `mock_failure_mode`): also
        sets the mock module-level ``_CANCEL_FLAG`` so the mock's
        per-snapshot loop exits.

        Idempotent on idle.
        """
        self._stop_event.set()
        # Propagate to mock_solver's module-level flag for the mock path.
        # The real path uses `should_stop=lambda: self._stop_event.is_set()`
        # threaded into `solve_hunl_postflop` (PR 10b §3).
        try:
            from ui.mock_solver import _CANCEL_FLAG

            _CANCEL_FLAG.set()
        except (ImportError, ModuleNotFoundError):
            # mock_solver not available; the real path's should_stop hook
            # carries cancellation through the engine.
            pass

    def is_alive(self) -> bool:
        """Raw thread liveness. Prefer :attr:`is_running` for logic.

        A worker thread can briefly report ``is_alive() == True`` after the
        logical solve has reached a terminal status (``done``/``stopped``/
        ``error``) but before the OS reaps it. Gating ``start()`` on this
        caused the "Solve already running" false positive; the guard now
        keys off :attr:`is_running` instead.
        """
        return self._thread is not None and self._thread.is_alive()

    @property
    def is_running(self) -> bool:
        """True iff a solve is *logically* in flight (``running``/``paused``).

        This is the source of truth the UI should poll for the running
        indicator and the start() guard. It is independent of whether the
        underlying daemon thread object has been reaped yet.
        """
        return self.status in ("running", "paused")

    def _reap_finished_worker(self) -> None:
        """Join + drop a worker whose solve has reached a terminal status.

        Called at the top of every ``start*`` so a finished-but-not-yet-reaped
        thread never blocks a new solve. Safe to call when idle (no-op). We
        only join when the *logical* status is terminal so an actively
        running worker is never joined out from under itself.
        """
        thread = self._thread
        if thread is None:
            return
        if self.status in _TERMINAL_STATUSES:
            # Logical solve is done; reap the OS thread (short timeout — the
            # worker has already returned, this just collects the handle).
            thread.join(timeout=2.0)
            if not thread.is_alive():
                self._thread = None

    def join(self, timeout: float | None = None) -> None:
        """Block until the worker thread exits (or ``timeout`` seconds elapse).

        After a successful join (thread no longer alive) the internal handle
        is dropped so :meth:`is_alive` reports ``False`` and the next
        ``start*`` starts cleanly.
        """
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            if not self._thread.is_alive():
                self._thread = None

    # ------------------------------------------------------------------ #
    # Progress API (v1.11 UI) — read-only accessors for the run_panel
    # progress bar + running indicator + ETA. All are cheap, lock-free
    # reads of atomic int/str/float fields (or single-field snapshots).
    # ------------------------------------------------------------------ #

    @property
    def current_iteration(self) -> int:
        """Iterations completed so far in the active/last solve (>= 0)."""
        return self.iteration

    @property
    def total_iterations(self) -> int | None:
        """Target iteration count, or ``None`` when unknown.

        ``None`` when the runner is idle or the solve has no fixed target
        (e.g. target-exploitability early-exit with no iteration cap).
        """
        return self.target_iterations

    @property
    def elapsed_seconds(self) -> float:
        """Wall-clock seconds since the active solve started (0.0 when idle).

        Uses the monotonic clock while running; falls back to
        ``time.time() - started_at`` if the monotonic fields are unset.
        """
        start = self.start_time_monotonic
        if start is not None:
            now = self.current_time_monotonic
            if now is None or self.is_running:
                now = time.monotonic()
            return max(0.0, float(now) - float(start))
        if self.started_at:
            return max(0.0, time.time() - self.started_at)
        return 0.0

    @property
    def progress_fraction(self) -> float | None:
        """Completion fraction in ``[0.0, 1.0]``, or ``None`` when unknown.

        ``None`` when ``total_iterations`` is unknown. Returns ``1.0`` once
        the solve has reached a terminal status so the bar reads full even
        if the final iteration count undershot the target (early-exit).
        """
        if self.status in ("done", "stopped"):
            return 1.0
        target = self.target_iterations
        if target is None or target <= 0:
            return None
        return max(0.0, min(1.0, self.iteration / target))

    @property
    def eta_seconds(self) -> float | None:
        """Estimated seconds remaining, or ``None`` when not derivable.

        Thin alias over :meth:`compute_eta` (iteration-rate × remaining).
        ``None`` when idle, target unknown/reached, or no forward progress.
        """
        return self.compute_eta()

    def compute_eta(self) -> float | None:
        """Return the linear-extrapolation ETA in seconds, or None if N/A.

        Uses elapsed wall-clock (``current_time_monotonic`` -
        ``start_time_monotonic`` if both set, else ``time.time() -
        started_at``) divided by ``iteration`` to get iters/sec, then
        (target_iterations - iteration) / rate. Returns None when:

          * ``iteration <= 0``, or
          * elapsed wall-clock is zero, or
          * the target is missing / already reached.

        Per `pr10a_spec.md` §6 edge #1: the UI surfaces an ETA after 30s
        of forward progress so the user can decide whether to stop.
        """
        iters = self.iteration
        if iters <= 0:
            return None
        start = getattr(self, "start_time_monotonic", None)
        now = getattr(self, "current_time_monotonic", None)
        if start is not None and now is not None:
            elapsed = float(now) - float(start)
        else:
            elapsed = time.time() - self.started_at if self.started_at else 0.0
        if elapsed <= 0:
            return None
        target = getattr(self, "target_iterations", None)
        if target is None or target <= iters:
            return None
        rate = iters / elapsed  # iters per second
        if rate <= 0:
            return None
        return (target - iters) / rate

    def _worker(
        self,
        *,
        config: HUNLConfig,
        iterations: int,
        log_every: int,
        dcfr_kwargs: dict[str, Any] | None,
        backend: str,
        memory_budget_gb: float,
        target_exploitability: float | None,
        seed: int | None,
        mock_latency_ms: int | None,
        mock_failure_mode: str | None,
        rvr_mode: bool = False,
        rvr_hero_range: list[HandClass] | None = None,
        rvr_villain_range: list[HandClass] | None = None,
        rvr_hero_player: int = 0,
        solver_mode: str = "true_nash",
        locked_strategies: dict[str, list[float]] | None = None,
        force_tree_solve: bool = False,
    ) -> None:
        """The worker-thread body. Runs on a daemon ``threading.Thread``.

        NEVER calls NiceGUI APIs. Communicates with the UI via
        ``self.iteration``, ``self.expl_history``, ``self.status``,
        ``self.result``, ``self.error``, ``self.partial_report`` — all
        guarded by ``self._lock``.

        PR 10b dispatch composition (per `pr10b_spec.md` §3 + `solver.solve`):

          1. If `mock_latency_ms` or `mock_failure_mode` is set, route to
             the mock solver (smoke-test injection path; production users
             never set these). The mock owns its own failure-mode dispatch
             (`oom`, `cancelled`, etc.).
          2. Otherwise, route to `poker_solver.solver.solve()` which
             internally handles:
               - push/fold short-circuit at <=15 BB (PR 3.5)
               - HUNL postflop tree solve (PR 5/PR 6)
               - HUNL preflop (PR 9, currently `NotImplementedError`)
          3. Progress updates flow through the `on_progress` callback path
             added in PR 10b (`solve_hunl_postflop` and the mock both fire
             it once per `log_every` chunk).
          4. Cancellation flows through `should_stop` (the real solver) or
             `_CANCEL_FLAG` (the mock); both bind to `self._stop_event`.
        """
        # Populate timing fields used by compute_eta(). PR 10a's smoke 20
        # asserts on these; the real-solver path keeps them current so the
        # UI can render a live ETA without polling a separate timer.
        with self._lock:
            self.target_iterations = iterations
            self.start_time_monotonic = time.monotonic()
            self.current_time_monotonic = self.start_time_monotonic

        # ----- Progress + cancellation hooks (shared by real + mock paths) -----
        # `on_progress` fires from inside `solve_hunl_postflop._run_with_probe`
        # at each `log_every` chunk boundary. We push the (iter, expl) tuple
        # into `expl_history` and update `partial_report` so the UI's
        # `ui.timer(0.5, ...)` poller can refresh the chart + memory panel.
        def _on_progress(it: int, expl: float, report: Any) -> None:
            now = time.monotonic()
            with self._lock:
                self.iteration = it
                self.expl_history.append((it, expl))
                self.partial_report = report
                self.current_time_monotonic = now

        # `should_stop` is polled at each chunk boundary inside the real
        # solver. Returning True causes the loop to break cleanly and the
        # solver returns a partial result.
        def _should_stop() -> bool:
            # Pause: block here while paused, but keep checking stop.
            while self._pause_event.is_set() and not self._stop_event.is_set():
                time.sleep(0.05)
            return self._stop_event.is_set()

        # ----- Chained orchestrator path (task #57, #31 Phase C) -----
        # When ``solver_mode == "chained"``, route through
        # :func:`poker_solver.chained.solve_chained` (PR #121 Phase A).
        # Stashes the resulting :class:`ChainedSolveResult` on
        # ``self.chained_result`` so the chained_tab view can render the
        # 13x13 preflop chart and lazily fetch postflop subgames. Mock
        # injection still takes priority so smoke tests can synthesize
        # error paths regardless of solver_mode.
        if (
            solver_mode == "chained"
            and mock_latency_ms is None
            and mock_failure_mode is None
        ):
            self._run_chained_path(
                config=config,
                iterations=iterations,
                hero_range=rvr_hero_range or [],
                villain_range=rvr_villain_range or [],
                hero_player=rvr_hero_player,
            )
            return

        # ----- Range-vs-range path (PR 24a) -----
        # When ``rvr_mode`` is set, route through the Pluribus-blueprint
        # aggregator instead of the concrete-vs-concrete ``solve`` path.
        # Mock injection takes priority over RvR because smoke tests
        # exercise the mock path with synthetic configs regardless of
        # spot.rvr_mode.
        if rvr_mode and mock_latency_ms is None and mock_failure_mode is None:
            self._run_rvr_path(
                config=config,
                iterations=iterations,
                backend=backend,
                hero_range=rvr_hero_range or [],
                villain_range=rvr_villain_range or [],
                hero_player=rvr_hero_player,
                dcfr_kwargs=dcfr_kwargs,
                solver_mode=solver_mode,
            )
            return

        # ----- Mock path: smoke-test injection only -----
        use_mock = mock_latency_ms is not None or mock_failure_mode is not None
        if use_mock:
            self._run_mock_path(
                config=config,
                iterations=iterations,
                log_every=log_every,
                dcfr_kwargs=dcfr_kwargs,
                target_exploitability=target_exploitability,
                memory_budget_gb=memory_budget_gb,
                seed=seed,
                mock_latency_ms=mock_latency_ms,
                mock_failure_mode=mock_failure_mode,
            )
            return

        # ----- Real-solver path (PR 10b core) -----
        # `_dispatch_solve` (below) routes to push/fold / postflop / preflop
        # per the PR 10b §6 dispatch composition.
        try:
            # `poker_solver.solver.solve` handles the dispatch composition:
            # - <=15 BB preflop → push/fold chart (instantaneous)
            # - postflop → solve_hunl_postflop (with our on_progress hook)
            # - preflop > 15 BB → solve_hunl_preflop (PR 9; NotImplementedError
            #   until PR 9 lands)
            # We forward `on_progress` and `should_stop` to the postflop branch
            # via `dcfr_kwargs` so they reach `_run_with_probe`. For the
            # push/fold short-circuit path these hooks are no-ops because
            # chart lookup is non-iterative.
            kwargs: dict[str, Any] = {
                "backend": backend,
                "log_every": log_every,
                # Forwarded into `solve_hunl_postflop` via solver.solve's
                # **dcfr_kwargs splat (solver.py treats these as `_DIRECT_KEYS`).
                "target_exploitability": target_exploitability,
                "memory_budget_gb": memory_budget_gb,
                "seed": seed,
                # `on_progress` and `should_stop` are not in solver.solve's
                # _DIRECT_KEYS set, so they ride in the remainder dict that
                # gets passed as `dcfr_kwargs=` to solve_hunl_postflop. That's
                # not what we want — instead, route through solve_hunl_postflop
                # directly to avoid the dispatcher's kwargs sorting.
            }
            # Use the canonical dispatcher (`solver.solve`) for the push/fold
            # short-circuit and the preflop branch; for the postflop branch
            # we call `solve_hunl_postflop` directly so we can thread the new
            # `on_progress` + `should_stop` kwargs (not yet in solve()'s
            # signature; see PR 10b spec).
            result = self._dispatch_solve(
                game=HUNLPoker(config),
                iterations=iterations,
                on_progress=_on_progress,
                should_stop=_should_stop,
                locked_strategies=locked_strategies,
                force_tree_solve=force_tree_solve,
                **kwargs,
            )
        except MemoryError as exc:
            # MemoryError.args[1] is MemoryReport per hunl_solver.py contract.
            with self._lock:
                self.error = exc
                self.status = "error"
                if len(exc.args) > 1 and hasattr(exc.args[1], "total_gb"):
                    self.partial_report = exc.args[1]
            return
        except NotImplementedError as exc:
            # Preflop solver not yet wired (PR 9); or unsupported backend.
            with self._lock:
                self.error = exc
                self.status = "error"
            return
        except (ValueError, RuntimeError, OSError) as exc:
            # Config/setup errors (e.g. bad abstraction, malformed config,
            # equity oracle failure). Surfaced to the UI as a red notification
            # instead of crashing.
            logger.exception("Solve failed with %s", type(exc).__name__)
            with self._lock:
                self.error = exc
                self.status = "error"
            return
        except BaseException as exc:  # noqa: BLE001
            # Catch-all so the worker never silently dies.
            logger.exception("Solve worker raised unexpected exception")
            with self._lock:
                self.error = exc
                self.status = "error"
            return

        # Successful exit (or cooperative cancellation via should_stop).
        with self._lock:
            self.result = result
            if self._stop_event.is_set():
                self.status = "stopped"
            else:
                self.status = "done"
            # Iteration count + final report from the solver. For push/fold
            # the result is a non-HUNL SolveResult (no memory_report); skip
            # the partial_report update in that case.
            self.iteration = result.iterations
            mem_report = getattr(result, "memory_report", None)
            if mem_report is not None:
                self.partial_report = mem_report
            # Push the final exploitability into expl_history so the UI's
            # chart shows the converged value even when on_progress wasn't
            # called (e.g. log_every=None or push/fold short-circuit).
            if result.exploitability_history and (
                not self.expl_history
                or self.expl_history[-1][1] != result.exploitability_history[-1]
            ):
                self.expl_history.append(
                    (result.iterations, result.exploitability_history[-1])
                )

    def _dispatch_solve(
        self,
        *,
        game: HUNLPoker,
        iterations: int,
        on_progress: Any,
        should_stop: Any,
        backend: str,
        log_every: int,
        target_exploitability: float | None,
        memory_budget_gb: float,
        seed: int | None,
        locked_strategies: dict[str, list[float]] | None = None,
        force_tree_solve: bool = False,
    ) -> SolveResult:
        """Real-solver dispatch composition (PR 10b §6).

        Order matches `poker_solver.solver.solve`:
          1. push/fold short-circuit at <=15 BB preflop (PR 3.5).
          2. HUNL postflop (PR 5/PR 6) — calls `solve_hunl_postflop` directly
             so we can thread `on_progress` + `should_stop` (not yet in
             `solver.solve`'s signature).
          3. HUNL preflop (PR 9) — uses `solver.solve` which currently
             raises NotImplementedError on the Rust path; Python tier lands
             with PR 9 merge.

        PR 24b §3.5: ``locked_strategies`` is threaded into both the postflop
        and preflop branches. The push/fold short-circuit raises
        ``ValueError`` per ``poker_solver/solver.py:74-86`` if locks are
        non-empty (and ``force_tree_solve`` is False). When the UI surfaces
        the remediation button, it sets ``force_tree_solve=True`` so the
        push/fold branch is skipped and the tree-builder runs instead.
        """
        from poker_solver.pushfold import is_pushfold_mode, solve_pushfold
        from poker_solver.solver import solve as canonical_solve

        cfg = game.config
        # Normalize locks: empty dict and None are bit-identical to "no
        # locks" per solver.py:60-61. Drop empties so downstream guards
        # don't treat {} as "locked."
        if not locked_strategies:
            locked_strategies = None

        # 1. Push/fold short-circuit (≤15 BB preflop) — instantaneous chart
        # lookup; no progress callback or cancellation needed.
        # PR 24b: refuse locks here per solver.py:74-86 unless
        # ``force_tree_solve`` is set; the UI's notify-remediation
        # button flips that flag before the retry.
        if (
            cfg.starting_street == Street.PREFLOP
            and is_pushfold_mode(cfg.starting_stack, cfg.big_blind)
            and not force_tree_solve
        ):
            if locked_strategies:
                raise ValueError(
                    "locked_strategies is incompatible with the push/fold "
                    "chart short-circuit (≤15 BB HUNL preflop). The chart "
                    "is precomputed and non-trainable; locks would be "
                    "silently ignored. Use the 'Use tree-builder mode' "
                    "remediation button to retry with force_tree_solve=True."
                )
            return solve_pushfold(cfg)

        # 2. HUNL postflop — direct call so on_progress + should_stop reach
        # the solve loop.
        #
        # v1.11 UI: the postflop engine is an INTERNAL implementation detail
        # and is NOT user-selectable (the Python/Rust toggle was removed; the
        # ``backend`` argument no longer downgrades the UI engine — see
        # ``start()``'s default of "rust"). We now drive postflop on the FAST
        # Rust tier: the ``_rust.solve_hunl_postflop`` binding gained the two
        # load-bearing UI hooks (v1.11) —
        #   * live progress streaming (``on_progress`` → progress bar + ETA),
        #   * cooperative mid-solve cancellation (``should_stop`` → the Stop
        #     button, critical for ~90-min flop solves) —
        # by re-acquiring the GIL only at ``log_every`` checkpoints. The
        # Python reference engine survives ONLY as a silent fallback when the
        # Rust extension is genuinely unavailable (not built / wrong arch);
        # the word "Python" is never surfaced to the user as an engine choice.
        # ``solve_hunl_postflop_rust`` returns a byte-shape-identical
        # ``HUNLSolveResult`` so the decision tree + chart widget are
        # unaffected by the engine swap.
        if Street.FLOP <= cfg.starting_street < Street.SHOWDOWN:
            from poker_solver.hunl_solver import (
                rust_postflop_available,
                solve_hunl_postflop,
                solve_hunl_postflop_rust,
            )

            if rust_postflop_available():
                return solve_hunl_postflop_rust(
                    cfg,
                    abstraction=None,
                    iterations=iterations,
                    target_exploitability=target_exploitability,
                    memory_budget_gb=memory_budget_gb,
                    log_every=log_every,
                    seed=seed,
                    on_progress=on_progress,
                    should_stop=should_stop,
                    locked_strategies=locked_strategies,
                )
            logger.warning(
                "Rust postflop binding unavailable; falling back to the "
                "Python reference engine for this postflop solve (progress + "
                "Stop still work, but the solve will be much slower)."
            )
            return solve_hunl_postflop(
                cfg,
                abstraction=None,
                iterations=iterations,
                target_exploitability=target_exploitability,
                memory_budget_gb=memory_budget_gb,
                log_every=log_every,
                seed=seed,
                on_progress=on_progress,
                should_stop=should_stop,
                locked_strategies=locked_strategies,
            )

        # 3. Preflop > 15 BB. PR 9's `solve_hunl_preflop` is the future
        # home of this branch; not yet merged to main as of PR 10b. We
        # try to import it (so PR 10b is forward-compatible the day PR 9
        # lands), and otherwise raise a clean NotImplementedError that
        # the UI surfaces as a red error notification with remediation
        # text. We do NOT fall through to `canonical_solve()` because its
        # tail branch unconditionally constructs a `DCFRSolver(game,
        # **dcfr_kwargs)` whose dcfr_kwargs would carry
        # `target_exploitability`/`memory_budget_gb` and crash on
        # invalid-kwarg TypeError — masking the real "preflop not yet
        # wired" message we want surfaced.
        if cfg.starting_street == Street.PREFLOP:
            try:
                from poker_solver.preflop import (  # type: ignore[import-not-found,import-untyped]
                    solve_hunl_preflop,
                )
            except (ImportError, ModuleNotFoundError) as exc:
                raise NotImplementedError(
                    "HUNL preflop solver (PR 9) is not yet wired into this "
                    "build. For now: use a postflop spot (set board to 3+ "
                    "cards) or reduce stacks to <=15 BB to dispatch to the "
                    "push/fold chart."
                ) from exc
            # PR 24b: pass locks through to the preflop solver. Accepting
            # the kwarg via try/except keeps us forward-compat with PR 9
            # preflop builds that may not yet expose ``locked_strategies``.
            try:
                return solve_hunl_preflop(
                    cfg,
                    abstraction=None,
                    iterations=iterations,
                    target_exploitability=target_exploitability,
                    memory_budget_gb=memory_budget_gb,
                    log_every=log_every,
                    seed=seed,
                    on_progress=on_progress,
                    should_stop=should_stop,
                    locked_strategies=locked_strategies,
                )
            except TypeError:
                # Older preflop solver builds don't accept ``locked_strategies``.
                # Fall back to the no-locks call and log; the locks would
                # have been silently dropped. We do this rather than fail
                # because preflop is currently NotImplementedError on most
                # builds anyway.
                logger.info(
                    "solve_hunl_preflop doesn't accept locked_strategies; "
                    "dropping locks for this call."
                )
                return solve_hunl_preflop(
                    cfg,
                    abstraction=None,
                    iterations=iterations,
                    target_exploitability=target_exploitability,
                    memory_budget_gb=memory_budget_gb,
                    log_every=log_every,
                    seed=seed,
                    on_progress=on_progress,
                    should_stop=should_stop,
                )
        # Kuhn / Leduc / other Game protocols don't currently flow through
        # the UI but we keep the fallback for forward-compat with the CLI
        # path. These don't use on_progress/should_stop.
        return canonical_solve(
            game,
            iterations,
            backend=backend,
            log_every=log_every,
            locked_strategies=locked_strategies,
            force_tree_solve=force_tree_solve,
        )

    def _run_rvr_path(
        self,
        *,
        config: HUNLConfig,
        iterations: int,
        backend: str,
        hero_range: list[HandClass],
        villain_range: list[HandClass],
        hero_player: int,
        dcfr_kwargs: dict[str, Any] | None,
        solver_mode: str = "true_nash",
    ) -> None:
        """Run the range-vs-range path (PR 24a + task #61).

        When ``solver_mode == "blueprint"`` (legacy fast mode for tiny
        river spots): dispatches to ``poker_solver.range_aggregator.solve_range_vs_range``.
        Progress is plumbed via the aggregator's ``on_progress(done, total,
        hand_class)`` callback so the UI's chart can show class-level
        completion as a coarse stand-in for exploitability (the aggregator
        does not expose a per-iter exploitability curve — every per-hand
        solve runs the underlying concrete solver to convergence). Honest
        framing per ``range_aggregator.py`` module docstring: this is a
        blueprint approximation, NOT a Nash range-vs-range solve. The chart
        subtitle in ``run_panel._chart_options`` reflects this (see PR 24a
        §3.4 "true Nash vs blueprint").

        When ``solver_mode == "true_nash"`` (default since 2026-05-27;
        task #61, post-PR-114 unlock): dispatches to
        ``poker_solver.range_aggregator.solve_range_vs_range_nash``
        (vector-form CFR, joint Nash of the supplied ranges with an
        exploitability number computed at the end). Empirical bench shows
        turn is ~27× faster than the blueprint aggregator; flop is
        feasible (blueprint flop is impractical at >27 min CPU on a
        tiny 3-class range). The result lands
        on ``self.nash_result`` (vs ``self.rvr_result`` for the blueprint
        path); both expose ``per_class_strategy`` so the matrix renderer
        treats them the same.
        """
        if solver_mode == "true_nash":
            self._run_true_nash_rvr_path(
                config=config,
                iterations=iterations,
                hero_range=hero_range,
                villain_range=villain_range,
                hero_player=hero_player,
            )
            return

        from poker_solver.range_aggregator import solve_range_vs_range

        def _on_rvr_progress(done: int, total: int, hand_class: str) -> None:
            # Cooperative cancellation. The aggregator runs per-class
            # solves sequentially and re-enters ``on_progress`` between
            # each one; we can't interrupt the underlying ``solve()``
            # mid-call, but we can record cancellation here so the next
            # class starts the wind-down (we have no direct kill switch
            # past this point; the daemon thread will exit naturally).
            now = time.monotonic()
            with self._lock:
                self.iteration = done
                # Use ``done`` as a stand-in iteration axis; the chart
                # subtitle in ``run_panel._chart_options`` already calls
                # this out as "blueprint approximation", so we do NOT
                # claim a true exploitability value here. Push a coarse
                # signal so the chart shows live progress.
                self.expl_history.append((done, max(0.0, float(total - done))))
                self.current_time_monotonic = now
            # Pause: block here. We can't honor stop mid-class without
            # tearing down the worker; the user must wait one class.
            while self._pause_event.is_set() and not self._stop_event.is_set():
                time.sleep(0.05)

        # Populate timing fields used by ``compute_eta()``.
        with self._lock:
            self.target_iterations = len(hero_range)
            self.start_time_monotonic = time.monotonic()
            self.current_time_monotonic = self.start_time_monotonic

        try:
            rvr_result = solve_range_vs_range(
                config,
                hero_range,
                villain_range,
                iterations=iterations,
                backend=backend,
                hero_player=hero_player,
                on_progress=_on_rvr_progress,
                dcfr_kwargs=dcfr_kwargs,
            )
        except (ValueError, RuntimeError, NotImplementedError) as exc:
            logger.exception("RvR solve failed with %s", type(exc).__name__)
            with self._lock:
                self.error = exc
                self.status = "error"
            return
        except BaseException as exc:  # noqa: BLE001
            logger.exception("RvR solve worker raised unexpected exception")
            with self._lock:
                self.error = exc
                self.status = "error"
            return

        with self._lock:
            self.rvr_result = rvr_result
            self.iteration = len(hero_range)
            if self._stop_event.is_set():
                self.status = "stopped"
            else:
                self.status = "done"

    def _run_true_nash_rvr_path(
        self,
        *,
        config: HUNLConfig,
        iterations: int,
        hero_range: list[HandClass],
        villain_range: list[HandClass],
        hero_player: int,
    ) -> None:
        """Run the true-Nash vector-form RvR path (task #61).

        Dispatches to ``poker_solver.range_aggregator.solve_range_vs_range_nash``
        (PR 23 vector-form CFR) instead of the Pluribus-blueprint
        aggregator. Produces a joint Nash with an exploitability number;
        the river path is ~213× faster post-PR-114 (interactive on river
        though flop / turn may still be longer wall-clock).

        Progress: the vector-form solver does not stream per-iteration
        callbacks in v1.7.0 (see ``range_aggregator.solve_range_vs_range_nash``
        docstring); it fires ``on_progress`` once at start and once at
        end. We surface ``(0, iterations)`` -> ``(iterations, expl)`` on
        the chart so the user sees the solve kick off and finalize.

        Cancellation: the vector-form solver runs to completion before
        returning. ``self._stop_event`` is not honored mid-solve; this is
        a known limitation of the v1.7.0 binding. The daemon thread will
        exit naturally on return.
        """
        from poker_solver.range_aggregator import solve_range_vs_range_nash

        def _on_progress(done: int, total: int, phase: str) -> None:
            _ = phase  # vector-form labels: "solve_start" / "solve_done"
            now = time.monotonic()
            with self._lock:
                self.iteration = done
                self.current_time_monotonic = now

        # Populate timing fields used by ``compute_eta()``.
        with self._lock:
            self.target_iterations = iterations
            self.start_time_monotonic = time.monotonic()
            self.current_time_monotonic = self.start_time_monotonic

        try:
            nash_result = solve_range_vs_range_nash(
                config,
                hero_range,
                villain_range,
                iterations=iterations,
                hero_player=hero_player,
                on_progress=_on_progress,
            )
        except (ValueError, RuntimeError, NotImplementedError, ImportError) as exc:
            logger.exception("True-Nash RvR solve failed with %s", type(exc).__name__)
            with self._lock:
                self.error = exc
                self.status = "error"
            return
        except BaseException as exc:  # noqa: BLE001
            logger.exception("True-Nash RvR solve worker raised unexpected exception")
            with self._lock:
                self.error = exc
                self.status = "error"
            return

        with self._lock:
            self.nash_result = nash_result
            # Mirror onto ``rvr_result`` so the matrix renderer's
            # duck-typed ``per_class_strategy`` lookup (see
            # ``ui/views/range_matrix.py:_current_rvr_result``) finds the
            # true-Nash projection without an additional code path. Both
            # dataclasses expose the same ``per_class_strategy`` attribute.
            self.rvr_result = nash_result  # type: ignore[assignment]
            self.iteration = int(getattr(nash_result, "iterations", iterations))
            # Push the final exploitability onto the chart's expl_history
            # so the user sees the converged value (vector form does not
            # stream per-iter, so this is the single data point).
            expl_value = float(getattr(nash_result, "exploitability", 0.0))
            self.expl_history.append((self.iteration, expl_value))
            if self._stop_event.is_set():
                self.status = "stopped"
            else:
                self.status = "done"

    def _run_chained_path(
        self,
        *,
        config: HUNLConfig,
        iterations: int,
        hero_range: list[HandClass],
        villain_range: list[HandClass],
        hero_player: int,
    ) -> None:
        """Run the chained orchestrator path (task #57, #31 Phase C).

        Dispatches to :func:`poker_solver.chained.solve_chained` which:

          1. Solves the preflop range subgame via Route A blueprint
             aggregation (per-pair :func:`solve_hunl_preflop` calls;
             see ``poker_solver/chained.py``).
          2. Enumerates preflop terminal action sequences + derives
             per-player continuation ranges.
          3. Returns a :class:`ChainedSolveResult` whose
             ``solve_postflop(action_seq, board)`` method runs the
             postflop subgame lazily on demand.

        Stashes the result on ``self.chained_result`` so the
        ``chained_tab`` view can render the 13x13 preflop chart and
        trigger postflop subgames from the UI.

        Progress: the chained orchestrator currently emits per-stage
        callbacks (``"preflop"`` / ``"continuation"``). We use those to
        update ``self.iteration`` so the header's status indicator
        moves while the per-pair solves run. The expl_history axis is
        coarse (count of completed per-pair solves vs total) — the chart
        subtitle in ``chained_tab._subtitle`` already calls this out.

        Cancellation: the orchestrator runs the per-pair preflop solves
        synchronously and there is no per-solve interrupt point in
        Phase A. ``self._stop_event`` is honored between stages only;
        the daemon thread will exit naturally on return.

        Note: the chained orchestrator reuses ``rvr_hero_range`` /
        ``rvr_villain_range`` for hero / villain class lists (the
        worker dispatches via the same parameter slot to avoid widening
        ``start``'s signature for a third path). The ``rvr_mode`` flag
        is NOT set when this path runs — it is mutually exclusive with
        the chained dispatch, and the worker checks ``solver_mode``
        first.
        """
        from poker_solver.chained import solve_chained

        def _on_chained_progress(stage: str, done: int, total: int) -> None:
            _ = stage  # "preflop" / "continuation"
            now = time.monotonic()
            with self._lock:
                self.iteration = done
                self.target_iterations = total
                self.current_time_monotonic = now

        with self._lock:
            self.target_iterations = max(1, len(hero_range) * len(villain_range))
            self.start_time_monotonic = time.monotonic()
            self.current_time_monotonic = self.start_time_monotonic
            self._mode = "chained"

        try:
            chained_result = solve_chained(
                config,
                hero_range=hero_range,
                villain_range=villain_range,
                preflop_iterations=iterations,
                # Phase A defaults the postflop iter count to 500. The UI
                # exposes a single preflop-iter input for now; postflop
                # iters can be widened in a future PR if needed.
                postflop_iterations=500,
                hero_player=hero_player,
                on_progress=_on_chained_progress,
            )
        except (ValueError, RuntimeError, NotImplementedError, ImportError) as exc:
            logger.exception("Chained solve failed with %s", type(exc).__name__)
            with self._lock:
                self.error = exc
                self.status = "error"
            return
        except BaseException as exc:  # noqa: BLE001
            logger.exception("Chained solve worker raised unexpected exception")
            with self._lock:
                self.error = exc
                self.status = "error"
            return

        with self._lock:
            self.chained_result = chained_result
            self.iteration = int(
                getattr(chained_result.preflop_result, "iterations", iterations)
            )
            # Push the preflop exploitability into the chart history so
            # the run-panel chart has a finalize data point even though
            # the chained orchestrator does not stream per-iter.
            expl_value = float(
                getattr(chained_result.preflop_result, "exploitability", 0.0)
            )
            self.expl_history.append((self.iteration, expl_value))
            if self._stop_event.is_set():
                self.status = "stopped"
            else:
                self.status = "done"
            # Task #68 Phase 6: surface route info for the chained tab.
            # Today the chained orchestrator runs its own live solve for
            # the preflop stage via Route A aggregation (see
            # ``poker_solver/chained.py``); the postflop stage is a
            # live subgame. Both stages are LIVE — but the wall time +
            # iteration count make the badge useful so users see how
            # long each stage took. The blueprint-vs-live decision for
            # chained will land when ``chained.py`` learns to consume a
            # Premium-A asset directly (a Phase 4+ subplan follow-up).
            from ui.blueprint_router import RouteInfo, SourceLabel

            pre_wall = float(
                getattr(chained_result.preflop_result, "wall_clock_s", 0.0)
            )
            pre_iters = int(
                getattr(chained_result.preflop_result, "iterations", iterations)
            )
            self.chained_preflop_route_info = RouteInfo(
                source=SourceLabel.LIVE,
                wall_time_s=pre_wall,
                confidence=f"{pre_iters} iter Route A aggregator",
            )
            # Postflop is also live; we don't know its wall time until
            # the user triggers ``ChainedSolveResult.solve_postflop``
            # via the board picker. Pre-seed with a "live subgame"
            # placeholder so the badge renders BEFORE any postflop
            # solve has run.
            self.chained_postflop_route_info = RouteInfo(
                source=SourceLabel.LIVE,
                wall_time_s=0.0,
                confidence="live subgame (triggered per flop pick)",
            )

    def _run_mock_path(
        self,
        *,
        config: HUNLConfig,
        iterations: int,
        log_every: int,
        dcfr_kwargs: dict[str, Any] | None,
        target_exploitability: float | None,
        memory_budget_gb: float,
        seed: int | None,
        mock_latency_ms: int | None,
        mock_failure_mode: str | None,
    ) -> None:
        """Run the mock solver path (smoke-test injection only).

        Kept for PR 10a smoke tests that exercise `mock_failure_mode='oom'`,
        `'cancelled'`, `'long_latency'`. Production users never reach this
        branch — they go through `_dispatch_solve` (the real path).
        """
        try:
            # fmt: off
            from ui.mock_solver import (  # noqa: I001
                _CANCEL_FLAG,
                mock_solve as _mock_solve,
                read_latest_progress,
                reset_progress_buffer,
            )
            # fmt: on
        except (ImportError, ModuleNotFoundError) as exc:
            with self._lock:
                self.status = "error"
                self.error = exc
            return

        _CANCEL_FLAG.clear()
        reset_progress_buffer()

        # Run mock_solve on a helper thread; this worker thread polls the
        # module-level progress buffer and updates self.* under the lock.
        solve_result: dict[str, Any] = {"result": None, "exc": None}

        def _solve_in_helper() -> None:
            try:
                mock_kwargs: dict[str, Any] = {}
                if mock_latency_ms is not None:
                    mock_kwargs["mock_latency_ms"] = mock_latency_ms
                if mock_failure_mode is not None:
                    mock_kwargs["mock_failure_mode"] = mock_failure_mode
                extra_kwargs: dict[str, Any] = {
                    "log_every": log_every,
                    "dcfr_kwargs": dcfr_kwargs,
                }
                if seed is not None:
                    extra_kwargs["seed"] = seed
                extra_kwargs.update(mock_kwargs)
                solve_result["result"] = _mock_solve(
                    config,
                    None,
                    iterations,
                    target_exploitability,
                    memory_budget_gb,
                    **extra_kwargs,
                )
            except BaseException as e:  # noqa: BLE001
                solve_result["exc"] = e

        helper = threading.Thread(target=_solve_in_helper, daemon=True)
        helper.start()

        last_iter_seen = -1
        while helper.is_alive():
            if self._stop_event.is_set():
                _CANCEL_FLAG.set()
            while self._pause_event.is_set() and not self._stop_event.is_set():
                time.sleep(0.05)
            snapshot = read_latest_progress()
            if snapshot is not None and snapshot.iteration != last_iter_seen:
                last_iter_seen = snapshot.iteration
                with self._lock:
                    self.iteration = snapshot.iteration
                    self.expl_history.append(
                        (snapshot.iteration, snapshot.exploitability)
                    )
                    self.partial_report = snapshot.partial_report
                    self.current_time_monotonic = time.monotonic()
            time.sleep(0.05)

        helper.join()
        snapshot = read_latest_progress()
        if snapshot is not None and snapshot.iteration != last_iter_seen:
            with self._lock:
                self.iteration = snapshot.iteration
                self.expl_history.append((snapshot.iteration, snapshot.exploitability))
                self.partial_report = snapshot.partial_report

        worker_exc = solve_result["exc"]
        result = solve_result["result"]
        if worker_exc is None:
            with self._lock:
                self.result = result
                if self._stop_event.is_set():
                    self.status = "stopped"
                else:
                    self.status = "done"
        elif isinstance(worker_exc, MemoryError):
            with self._lock:
                self.error = worker_exc
                self.status = "error"
                if len(worker_exc.args) > 1 and hasattr(worker_exc.args[1], "total_gb"):
                    self.partial_report = worker_exc.args[1]
        elif isinstance(worker_exc, NotImplementedError):
            with self._lock:
                self.error = worker_exc
                self.status = "error"
        else:
            logger.exception(
                "Mock solve worker raised unexpected exception",
                exc_info=worker_exc,
            )
            with self._lock:
                self.error = worker_exc
                self.status = "error"


# --------------------------------------------------------------------------- #
# AppState aggregator + module-level singleton
# --------------------------------------------------------------------------- #


@dataclass
class AppState:
    """Aggregator passed to view ``render`` functions.

    Two browser tabs share this singleton (per spec §1 non-goal "no multi-
    tab state sync"). Don't try to support multi-tab in PR 10.
    """

    current_spot: Spot
    current_solve: SolveSession | None
    current_tree_node_id: str  # "root" by default; Agent B's tree updates this
    selected_player_for_input: int  # 0 or 1; which tab is active in spot_input
    runner: SolveRunner
    prefs: UIPrefs
    state_path: Path  # ~/.poker_solver_ui/state.json
    # Cross-view stash: library_browser writes the selected spot id here so
    # spot_input can pick it up and dispatch ``Library.get`` (spec §4.5).
    # ``None`` means "no library spot pending load".
    selected_library_spot_id: str | None = None


_STATE_DIR: Path = Path.home() / ".poker_solver_ui"
_STATE_FILE: Path = _STATE_DIR / "state.json"
_STATE_VERSION: int = 1

_state_singleton: AppState | None = None
_state_dirty: bool = False
_state_save_lock: threading.Lock = threading.Lock()
_state_last_save_at: float = 0.0
_STATE_DEBOUNCE_SEC: float = 0.5


def get_state() -> AppState:
    """Return the module-level singleton ``AppState``.

    Lazily initialized on first call; loads from
    ``~/.poker_solver_ui/state.json`` if present. On corrupt JSON or
    version mismatch: warns, backs up to ``state.json.bak``, starts fresh
    (never crashes — per ``pr10a_spec.md`` §9.2).
    """
    global _state_singleton
    if _state_singleton is None:
        _state_singleton = _load_or_default()
    return _state_singleton


def _migrate_legacy_freq_dict(
    rw: RangeWithFreqs, freq_dict: dict[Any, Any] | None
) -> None:
    """B10 Phase C: one-shot upgrade of legacy ``frequencies: {...}`` payloads.

    Pre-Phase-C ``RangeWithFreqs`` carried a sibling ``frequencies`` dict.
    When loading a state.json written by an older build, walk the dict
    and replay each entry through ``set_frequency`` (which now delegates
    to ``Range.set_weight``). Once migrated, the dict is dropped — the
    next save uses the canonical ``Range._weight`` store, so the legacy
    field never re-appears.

    The ``freq_dict`` argument is whatever the loader pulled out of the
    persisted JSON. Keys are encoded as 4-char strings (``"AsKs"``) or
    as 2-tuples-of-cards (older test fixtures); we accept both. Malformed
    entries are logged and skipped — never crash on bad input.
    """
    if not freq_dict:
        return
    for raw_key, raw_val in freq_dict.items():
        combo = _decode_combo_key(raw_key)
        if combo is None:
            logger.warning(
                "B10 migration: skipping malformed combo key %r", raw_key
            )
            continue
        try:
            weight = float(raw_val)
        except (TypeError, ValueError):
            logger.warning(
                "B10 migration: skipping non-numeric weight %r for %r",
                raw_val,
                raw_key,
            )
            continue
        rw.set_frequency(combo, weight)


def _decode_combo_key(raw: Any) -> _CardPair | None:
    """Decode a persisted combo key to a ``(Card, Card)`` tuple.

    Accepts:
      * 4-char hole strings (``"AsKs"``, ``"7d2c"``) — the JSON-native
        encoding.
      * 2-element list/tuple of card strings (``["As", "Ks"]``) — older
        debug fixtures.
      * Pre-parsed ``(Card, Card)`` tuples — defensive, in case callers
        pass live state.

    Returns ``None`` on any malformed input.
    """
    if isinstance(raw, str) and len(raw) == 4:
        try:
            c0 = Card.from_str(raw[:2])
            c1 = Card.from_str(raw[2:])
        except (ValueError, KeyError, IndexError):
            return None
        return (c0, c1)
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        c0_raw, c1_raw = raw
        if isinstance(c0_raw, Card) and isinstance(c1_raw, Card):
            return (c0_raw, c1_raw)
        if isinstance(c0_raw, str) and isinstance(c1_raw, str):
            try:
                return (Card.from_str(c0_raw), Card.from_str(c1_raw))
            except (ValueError, KeyError, IndexError):
                return None
    return None


def _load_or_default() -> AppState:
    """Construct the singleton, loading prefs from disk if available.

    B10 Phase C also runs a one-shot upgrade on any legacy ``frequencies``
    payload found under ``current_spot.ranges[*].frequencies``. The
    canonical weight store now lives in ``Range._weight`` — see
    ``_migrate_legacy_freq_dict``.
    """
    prefs = UIPrefs()
    current_spot = Spot()
    try:
        if _STATE_FILE.exists():
            with _STATE_FILE.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            version = data.get("version", 0)
            if version != _STATE_VERSION:
                raise ValueError(
                    f"state.json version mismatch: got {version}, expected {_STATE_VERSION}"
                )
            prefs_data = data.get("prefs", {})
            prefs = UIPrefs(
                dark_mode=prefs_data.get("dark_mode", "auto"),
                panel_widths=prefs_data.get(
                    "panel_widths", {"left": 320, "bottom": 240}
                ),
                matrix_show_frequencies=prefs_data.get("matrix_show_frequencies", True),
                tree_reach_filter=float(prefs_data.get("tree_reach_filter", 0.01)),
                mock_banner_dismissed=bool(
                    prefs_data.get("mock_banner_dismissed", False)
                ),
                onboarding_completed=bool(
                    prefs_data.get("onboarding_completed", False)
                ),
                chart_log_scale=bool(prefs_data.get("chart_log_scale", True)),
            )
            # B10 Phase C migration: walk any persisted ranges and
            # upgrade legacy ``frequencies: {...}`` payloads. We do not
            # yet persist full spots (PR 11 work), but the loader is
            # forward-compatible with both old (Phase A/B) and new
            # (Phase C) range encodings — see ``_apply_range_payload``.
            spot_data = data.get("current_spot")
            if isinstance(spot_data, dict):
                _apply_spot_payload(current_spot, spot_data)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load state.json (%s); starting from defaults", exc)
        # Back up corrupt file then proceed with defaults.
        if _STATE_FILE.exists():
            try:
                _STATE_FILE.rename(_STATE_DIR / "state.json.bak")
            except OSError:
                logger.exception("Failed to back up corrupt state.json")
    return AppState(
        current_spot=current_spot,
        current_solve=None,
        current_tree_node_id="root",
        selected_player_for_input=0,
        runner=SolveRunner(),
        prefs=prefs,
        state_path=_STATE_FILE,
    )


def _apply_spot_payload(spot: Spot, spot_data: dict[str, Any]) -> None:
    """Apply a persisted ``current_spot`` payload onto ``spot`` in place.

    Limited scope: only the per-player range weights are restored (the
    feature B10 Phase C ships). Other spot fields are left at their
    default and will be filled in by future PRs that persist them.

    The ranges payload is shaped as either:

    * **Pre-Phase-C (legacy)** — ``{"ranges": [{"frequencies": {key: w}}, ...]}``
      The legacy ``frequencies`` dict is walked and migrated via
      ``set_frequency``.
    * **Phase-C+ (canonical)** — ``{"ranges": [{"weights": {key: w}}, ...]}``
      Each entry is replayed via ``set_frequency`` (which writes through
      to ``Range._weight``).
    """
    raw_ranges = spot_data.get("ranges")
    if not isinstance(raw_ranges, (list, tuple)):
        return
    rebuilt: list[RangeWithFreqs] = []
    for entry in raw_ranges[:2]:
        if not isinstance(entry, dict):
            rebuilt.append(RangeWithFreqs.full())
            continue
        # Start from empty range; weights below seed it.
        rw = RangeWithFreqs.empty()
        # Legacy field — strip on next save.
        if "frequencies" in entry:
            _migrate_legacy_freq_dict(rw, entry.get("frequencies"))
        # Canonical (Phase C+) field — same encoding, future-proof name.
        if "weights" in entry:
            _migrate_legacy_freq_dict(rw, entry.get("weights"))
        rebuilt.append(rw)
    while len(rebuilt) < 2:
        rebuilt.append(RangeWithFreqs.full())
    spot.ranges = (rebuilt[0], rebuilt[1])


def save_state() -> None:
    """Mark the state dirty and schedule a debounced atomic save.

    Atomic-write semantics: writes to ``state.json.tmp``, ``fsync``,
    renames to ``state.json``. Coalesces multiple calls inside a 500 ms
    window into one disk write.

    Idempotent: safe to call from any view's on-change handler. The
    NiceGUI timer in ``ui/app.py`` calls ``_maybe_flush_state()`` every
    500 ms to do the actual disk write.
    """
    global _state_dirty
    with _state_save_lock:
        _state_dirty = True


def _maybe_flush_state() -> None:
    """If the state is dirty and the debounce window elapsed, flush to disk.

    Called every 500 ms by the ``ui.timer`` in ``ui/app.py``. Idempotent
    and side-effect-free when the dirty flag is clear.
    """
    global _state_dirty, _state_last_save_at
    with _state_save_lock:
        if not _state_dirty:
            return
        now = time.time()
        if now - _state_last_save_at < _STATE_DEBOUNCE_SEC:
            return
        if _state_singleton is None:
            _state_dirty = False
            return
        try:
            _STATE_DIR.mkdir(parents=True, exist_ok=True)
            payload = _serialize_state(_state_singleton)
            tmp = _STATE_FILE.with_suffix(".json.tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            tmp.replace(_STATE_FILE)
            _state_last_save_at = now
            _state_dirty = False
        except OSError:
            logger.exception("Failed to flush state.json")


def _serialize_state(state: AppState) -> dict[str, Any]:
    """Serialize ``AppState`` to a JSON-friendly dict.

    PR 10a only persists ``prefs`` (per spec §9.2). Spots / ranges /
    library entries are still pending PR 11, BUT B10 Phase C adds a
    minimal per-range ``weights`` payload so the per-combo intensity
    editor's edits survive a session round-trip. The legacy
    ``frequencies`` key is *never* emitted — the loader is forward-
    compatible with both, the serializer is canonical-only.
    """
    payload: dict[str, Any] = {
        "version": _STATE_VERSION,
        "prefs": {
            "dark_mode": state.prefs.dark_mode,
            "panel_widths": dict(state.prefs.panel_widths),
            "matrix_show_frequencies": state.prefs.matrix_show_frequencies,
            "tree_reach_filter": state.prefs.tree_reach_filter,
            "mock_banner_dismissed": state.prefs.mock_banner_dismissed,
            "onboarding_completed": state.prefs.onboarding_completed,
            "chart_log_scale": state.prefs.chart_log_scale,
        },
    }
    spot = state.current_spot
    if spot is not None:
        spot_payload = _serialize_spot_ranges(spot)
        if spot_payload is not None:
            payload["current_spot"] = spot_payload
    return payload


def _serialize_spot_ranges(spot: Spot) -> dict[str, Any] | None:
    """Serialize the per-player range weights only.

    Emits ``None`` when both ranges are full unit-weight (the implicit
    default) — keeps state.json small for the common case where the
    user hasn't yet edited any per-combo weight. The check is
    deliberately conservative: if EITHER range has any combo whose
    weight ``< 1.0``, emit the full payload for both ranges so the
    asymmetric case never silently loses data.
    """

    def _has_fractional(rw: RangeWithFreqs) -> bool:
        for combo in rw.base_range.combos:
            if rw.frequency_of(combo) < 1.0:
                return True
        return False

    if not any(_has_fractional(rw) for rw in spot.ranges):
        return None

    range_payloads: list[dict[str, Any]] = []
    for rw in spot.ranges:
        weights: dict[str, float] = {}
        for combo in rw.base_range.combos:
            c0, c1 = combo
            key = f"{c0}{c1}"
            weights[key] = rw.frequency_of(combo)
        range_payloads.append({"weights": weights})
    return {"ranges": range_payloads}


def reset_state_for_testing() -> None:
    """Reset the module-level singleton + dirty flag.

    Test-only helper. Smoke tests need a fresh state per test; production
    code never calls this.
    """
    global _state_singleton, _state_dirty, _state_last_save_at
    _state_singleton = None
    _state_dirty = False
    _state_last_save_at = 0.0


# --------------------------------------------------------------------------- #
# Mock-solver gateway (PR 10a only — PR 10b retargets to the real solver)
# --------------------------------------------------------------------------- #
#
# Per ``pr10a_spec.md`` §11 acceptance #7, ``ui.mock_solver`` MUST be imported
# in EXACTLY ONE file: this one. The three call sites that need preset
# metadata, preset materialization, and per-snapshot solving go through the
# accessors below. PR 10b's mechanical swap rewrites the import inside
# ``SolveRunner._worker``; these gateway helpers stay untouched.


def list_fixture_preset_ids() -> list[str]:
    """Return the 12 fixture preset IDs from ``ui.mock_solver``.

    Falls back to the canonical 12 IDs from ``pr10a_spec.md`` §7.4 if
    ``ui.mock_solver`` is not yet wired (PR 10a-pre-Agent-C bootstrap).
    """
    try:
        from ui.mock_solver import list_fixture_presets

        presets = list_fixture_presets()
        # FixturePreset.id is the canonical attribute name (see
        # ui/mock_solver_fixtures.py:35); the older `preset_id` lookup is a
        # legacy fallback that historically left preset markers stamped
        # with the full repr of the dataclass instead of the id string.
        return [str(getattr(p, "id", getattr(p, "preset_id", p))) for p in presets]
    except (ImportError, ModuleNotFoundError, AttributeError):
        return [
            "river_tiny_subgame",
            "flop_k72r_100bb",
            "flop_t87s_100bb",
            "flop_monotone_hhh",
            "flop_paired_q9q",
            "turn_kqj9_4_flush",
            "turn_t872_brick",
            "river_axxs_polar",
            "preflop_btn_vs_bb",
            "river_blocker_heavy",
            "shortstack_25bb",
            "deepstack_200bb",
        ]


def load_fixture_config(preset_id: str) -> HUNLConfig | None:
    """Materialize a fixture preset id into a ``HUNLConfig``.

    Returns None if ``ui.mock_solver`` is unavailable (PR 10a-pre-Agent-C
    bootstrap). Raises ``KeyError`` / ``ValueError`` if mock_solver is
    present but the preset is unknown — caller surfaces the notification.
    """
    try:
        from ui.mock_solver import load_fixture
    except (ImportError, ModuleNotFoundError):
        return None
    return load_fixture(preset_id)


__all__ = [
    "AppState",
    "HandClass",
    "RangeVsRangeResult",
    "RangeWithFreqs",
    "SolveRunner",
    "SolveSession",
    "Spot",
    "UIPrefs",
    "classify_combo",
    "enumerate_combos",
    "enumerate_hand_classes",
    "get_state",
    "hand_class_label",
    "list_fixture_preset_ids",
    "load_fixture_config",
    "reset_state_for_testing",
    "save_state",
]
