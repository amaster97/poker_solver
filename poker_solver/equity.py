"""Equity calculator for Texas Hold'em.

Auto-dispatches between exact enumeration (when all hands are concrete and the
remaining board state space is small) and Monte Carlo sampling (otherwise).
Default MC iteration count targets ~0.1% standard error per hand.
"""

from __future__ import annotations

import itertools
import math
import random
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Union

from poker_solver.card import Card, full_deck
from poker_solver.evaluator import evaluate
from poker_solver.range import Range

HandSpec = Union[Sequence[Card], Range]

DEFAULT_ITERATIONS = 250_000
DEFAULT_ENUM_THRESHOLD = 100_000


@dataclass
class EquityResult:
    win: int = 0
    tie: int = 0
    lose: int = 0
    iterations: int = 0
    equity_sum: float = 0.0
    samples: list[list[Card]] = field(default_factory=list, repr=False)

    @property
    def win_pct(self) -> float:
        return self.win / self.iterations if self.iterations else 0.0

    @property
    def tie_pct(self) -> float:
        return self.tie / self.iterations if self.iterations else 0.0

    @property
    def lose_pct(self) -> float:
        return self.lose / self.iterations if self.iterations else 0.0

    @property
    def equity(self) -> float:
        return self.equity_sum / self.iterations if self.iterations else 0.0


def equity(
    hands: Sequence[HandSpec],
    board: Sequence[Card] | None = None,
    iterations: int = DEFAULT_ITERATIONS,
    rng: random.Random | None = None,
    max_attempts_multiplier: int = 10,
    enum_threshold: int = DEFAULT_ENUM_THRESHOLD,
) -> list[EquityResult]:
    """Compute equity exactly (enumeration) or by sampling (Monte Carlo).

    When all hands are concrete and the number of possible board runouts is
    at most ``enum_threshold``, all runouts are enumerated and the result is
    exact. Otherwise, ``iterations`` random runouts are sampled. The default
    iteration count yields a standard error of ~0.1% per hand.

    Args:
        hands: each element is either a 2-card sequence or a :class:`Range`.
        board: 0 to 5 known community cards (Cards). Missing board cards are
            either enumerated or sampled depending on the dispatch.
        iterations: target number of MC samples (ignored in enumeration path).
        rng: optional :class:`random.Random` instance for reproducibility.
        max_attempts_multiplier: cap on total MC attempts before giving up.
        enum_threshold: max runouts to enumerate; above this, MC is used.

    Returns:
        A list of :class:`EquityResult`, one per input hand, in the same order.
    """
    if len(hands) < 2:
        raise ValueError("Need at least two hands to compute equity")
    board_list: list[Card] = list(board or [])
    if len(board_list) > 5:
        raise ValueError(f"Board has {len(board_list)} cards (max 5)")
    if len(set(board_list)) != len(board_list):
        raise ValueError("Duplicate cards in board")

    deck = full_deck()
    cards_needed = 5 - len(board_list)

    if all(not isinstance(h, Range) for h in hands):
        concrete = _validate_concrete(hands, board_list)
        used = set(board_list)
        for hole in concrete:
            used.update(hole)
        remaining = [c for c in deck if c not in used]
        if math.comb(len(remaining), cards_needed) <= enum_threshold:
            return _enumerate_exact(concrete, board_list, remaining, cards_needed)

    rng = rng or random.Random()
    results = [EquityResult() for _ in hands]
    max_attempts = iterations * max_attempts_multiplier
    attempts = 0
    completed = 0

    while completed < iterations and attempts < max_attempts:
        attempts += 1
        used = set(board_list)
        sampled_hands: list[list[Card]] = []
        conflict = False
        for h in hands:
            if isinstance(h, Range):
                combo = h.sample_excluding(used, rng)
                if combo is None:
                    conflict = True
                    break
                sampled_hands.append(list(combo))
                used.add(combo[0])
                used.add(combo[1])
            else:
                hole = list(h)
                if len(hole) != 2:
                    raise ValueError(f"Hand must have 2 cards, got {len(hole)}")
                if hole[0] in used or hole[1] in used:
                    conflict = True
                    break
                sampled_hands.append(hole)
                used.add(hole[0])
                used.add(hole[1])
        if conflict:
            continue

        remaining = [c for c in deck if c not in used]
        if cards_needed > 0:
            rng.shuffle(remaining)
            drawn = remaining[:cards_needed]
        else:
            drawn = []
        full_board = board_list + drawn

        scores = [evaluate(hand + full_board) for hand in sampled_hands]
        best = max(scores)
        winners = [i for i, s in enumerate(scores) if s == best]

        if len(winners) == 1:
            w = winners[0]
            for i, r in enumerate(results):
                if i == w:
                    r.win += 1
                    r.equity_sum += 1.0
                else:
                    r.lose += 1
        else:
            share = 1.0 / len(winners)
            winner_set = set(winners)
            for i, r in enumerate(results):
                if i in winner_set:
                    r.tie += 1
                    r.equity_sum += share
                else:
                    r.lose += 1
        for r in results:
            r.iterations += 1
        completed += 1

    if completed == 0:
        raise RuntimeError(
            "Could not complete any iteration — hands and board likely conflict"
        )
    return results


def _validate_concrete(
    hands: Sequence[HandSpec], board: list[Card]
) -> list[list[Card]]:
    used = set(board)
    out: list[list[Card]] = []
    for h in hands:
        hole = list(h)  # type: ignore[arg-type]
        if len(hole) != 2:
            raise ValueError(f"Hand must have 2 cards, got {len(hole)}")
        if hole[0] in used or hole[1] in used:
            raise ValueError("Duplicate card between hand and board (or another hand)")
        out.append(hole)
        used.update(hole)
    return out


def _enumerate_exact(
    hands: list[list[Card]],
    board: list[Card],
    remaining: list[Card],
    cards_needed: int,
) -> list[EquityResult]:
    results = [EquityResult() for _ in hands]
    runouts: Sequence[Sequence[Card]]
    if cards_needed == 0:
        runouts = [()]
    else:
        runouts = itertools.combinations(remaining, cards_needed)
    for drawn in runouts:
        full_board = board + list(drawn)
        scores = [evaluate(h + full_board) for h in hands]
        best = max(scores)
        winners = [i for i, s in enumerate(scores) if s == best]
        if len(winners) == 1:
            w = winners[0]
            for i, r in enumerate(results):
                if i == w:
                    r.win += 1
                    r.equity_sum += 1.0
                else:
                    r.lose += 1
        else:
            share = 1.0 / len(winners)
            winner_set = set(winners)
            for i, r in enumerate(results):
                if i in winner_set:
                    r.tie += 1
                    r.equity_sum += share
                else:
                    r.lose += 1
        for r in results:
            r.iterations += 1
    return results
