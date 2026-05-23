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
from poker_solver.hunl import HUNLConfig, HUNLPoker, Street
from poker_solver.range import Combo, Range, parse_range
from poker_solver.range_aggregator import HandClass, RangeVsRangeResult
from poker_solver.solver import SolveResult

if TYPE_CHECKING:
    from poker_solver.profiler.memory import MemoryReport

logger = logging.getLogger(__name__)

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


def enumerate_combos(hand_class: str) -> list[Combo]:
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
        out: list[Combo] = []
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
# Range helpers
# --------------------------------------------------------------------------- #


def _full_range_combos() -> list[Combo]:
    """All 1326 unordered combos as canonical (Card, Card) tuples.

    Cards within each combo are ordered (higher rank first; ties broken by
    suit ascending) to match ``Range.add``'s sort key.
    """
    out: list[Combo] = []
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
    """A ``poker_solver.Range`` with an added per-combo frequency layer.

    PR 10 needs per-combo float frequencies in ``[0.0, 1.0]``; ``Range`` is
    membership-only. We do NOT modify ``range.py`` — instead this class wraps
    a ``Range`` and adds a ``frequencies`` dict from (Card, Card) combos to
    a float in ``[0.0, 1.0]``.

    Semantics:

    - ``frequency_of(combo)`` returns ``frequencies[combo]`` if present,
      else ``1.0`` if combo in ``base_range``, else ``0.0``.
    - The range-INPUT matrix in ``ui/views/spot_input.py`` mutates
      ``frequencies[combo]`` when a cell is clicked or shift-clicked.
    - Agent B's strategy DISPLAY matrix reads
      ``state.current_spot.ranges[player].frequency_of(combo)`` for the
      per-cell aggregate (e.g., to size a "% of range" label).
    """

    base_range: Range = field(default_factory=Range)
    frequencies: dict[Combo, float] = field(default_factory=dict)

    def frequency_of(self, combo: Combo) -> float:
        """Return the frequency of ``combo``.

        Default 1.0 if combo is in ``base_range`` and absent from
        ``frequencies``; 0.0 otherwise.
        """
        if combo in self.frequencies:
            return self.frequencies[combo]
        if combo in self.base_range._combo_set:
            return 1.0
        return 0.0

    def set_frequency(self, combo: Combo, freq: float) -> None:
        """Set ``frequencies[combo] = freq`` (clamped to ``[0.0, 1.0]``).

        Adds ``combo`` to ``base_range`` if not already present.
        """
        clamped = max(0.0, min(1.0, freq))
        self.frequencies[combo] = clamped
        if combo not in self.base_range._combo_set:
            self.base_range.add(combo)

    @classmethod
    def from_string(cls, range_str: str) -> RangeWithFreqs:
        """Parse ``range_str`` via ``parse_range``; every combo at 1.0."""
        base = parse_range(range_str)
        freqs: dict[Combo, float] = {combo: 1.0 for combo in base.combos}
        return cls(base_range=base, frequencies=freqs)

    @classmethod
    def full(cls) -> RangeWithFreqs:
        """Construct a ``RangeWithFreqs`` containing all 1326 combos at 1.0."""
        base = _full_range()
        freqs: dict[Combo, float] = {combo: 1.0 for combo in base.combos}
        return cls(base_range=base, frequencies=freqs)

    @classmethod
    def empty(cls) -> RangeWithFreqs:
        """Construct an empty ``RangeWithFreqs``."""
        return cls(base_range=Range(), frequencies={})

    def to_string(self) -> str:
        """Render back to a comma-separated combo list.

        Lossy: combos with frequency < 1.0 lose their fractional weight.
        Round-trips ``RangeWithFreqs.from_string(rw.to_string())`` only for
        unit-weight ranges.
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


# --------------------------------------------------------------------------- #
# SolveRunner — the worker-thread orchestrator
# --------------------------------------------------------------------------- #


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

    def start(
        self,
        game: HUNLPoker,
        iterations: int,
        *,
        log_every: int,
        dcfr_kwargs: dict[str, Any] | None = None,
        backend: str = "python",
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

        Raises ``RuntimeError`` if a previous solve is still alive (call
        ``stop()`` + ``join()`` first).
        """
        if self.is_alive():
            raise RuntimeError(
                "SolveRunner.start() called while a solve is in flight; "
                "call stop() and wait until is_alive() is False first."
            )
        if rvr_mode and (rvr_hero_range is None or rvr_villain_range is None):
            raise ValueError(
                "rvr_mode=True requires rvr_hero_range and rvr_villain_range "
                "to be non-None lists of hand-class strings."
            )
        # Reset state for the new run.
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
                "locked_strategies": locked_strategies,
                "force_tree_solve": force_tree_solve,
            },
            daemon=True,
            name="poker-solver-ui-worker",
        )
        self._thread.start()

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
        return self._thread is not None and self._thread.is_alive()

    def join(self, timeout: float | None = None) -> None:
        """Block until the worker thread exits (or ``timeout`` seconds elapse)."""
        if self._thread is not None:
            self._thread.join(timeout=timeout)

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
        # `_run_with_probe`. The Rust backend doesn't yet support these
        # callbacks (PR 6 has no equivalent hook), so we fall back to the
        # Python backend in that case with a one-time warning.
        if Street.FLOP <= cfg.starting_street < Street.SHOWDOWN:
            from poker_solver.hunl_solver import solve_hunl_postflop

            if backend == "rust":
                logger.info(
                    "Rust backend does not support on_progress/should_stop "
                    "yet; falling back to Python tier for this solve."
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
    ) -> None:
        """Run the range-vs-range aggregator path (PR 24a).

        Dispatches to ``poker_solver.range_aggregator.solve_range_vs_range``.
        Progress is plumbed via the aggregator's ``on_progress(done, total,
        hand_class)`` callback so the UI's chart can show class-level
        completion as a coarse stand-in for exploitability (the aggregator
        does not expose a per-iter exploitability curve — every per-hand
        solve runs the underlying concrete solver to convergence).

        Honest framing per ``range_aggregator.py`` module docstring: this
        is a blueprint approximation, NOT a Nash range-vs-range solve.
        The chart subtitle in ``run_panel._chart_options`` reflects this
        (see PR 24a §3.4 "true Nash vs blueprint").
        """
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


def _load_or_default() -> AppState:
    """Construct the singleton, loading prefs from disk if available."""
    prefs = UIPrefs()
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
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load state.json (%s); starting from defaults", exc)
        # Back up corrupt file then proceed with defaults.
        if _STATE_FILE.exists():
            try:
                _STATE_FILE.rename(_STATE_DIR / "state.json.bak")
            except OSError:
                logger.exception("Failed to back up corrupt state.json")
    return AppState(
        current_spot=Spot(),
        current_solve=None,
        current_tree_node_id="root",
        selected_player_for_input=0,
        runner=SolveRunner(),
        prefs=prefs,
        state_path=_STATE_FILE,
    )


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

    PR 10a only persists ``prefs`` (per spec §9.2). Spots / ranges / library
    entries land in PR 11.
    """
    return {
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
