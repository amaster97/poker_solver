"""Monte Carlo equity calculator for Texas Hold'em."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Union

from poker_solver.card import Card, full_deck
from poker_solver.evaluator import evaluate
from poker_solver.range import Range

HandSpec = Union[Sequence[Card], Range]


@dataclass
class EquityResult:
    win: int = 0
    tie: int = 0
    lose: int = 0
    iterations: int = 0
    equity_sum: float = 0.0
    samples: List[List[Card]] = field(default_factory=list, repr=False)

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
    board: Optional[Sequence[Card]] = None,
    iterations: int = 10_000,
    rng: Optional[random.Random] = None,
    max_attempts_multiplier: int = 10,
) -> List[EquityResult]:
    """Run a Monte Carlo equity simulation.

    Args:
        hands: each element is either a 2-card sequence or a :class:`Range`.
        board: 0 to 5 known community cards (Cards). Missing board cards are
            sampled uniformly at random for each iteration.
        iterations: target number of successful iterations to simulate.
        rng: optional :class:`random.Random` instance for reproducibility.
        max_attempts_multiplier: cap on total attempts (iterations *
            multiplier) before giving up — protects against impossible ranges.

    Returns:
        A list of :class:`EquityResult`, one per input hand, in the same order.
    """
    if len(hands) < 2:
        raise ValueError("Need at least two hands to compute equity")
    rng = rng or random.Random()
    board_list: List[Card] = list(board or [])
    if len(board_list) > 5:
        raise ValueError(f"Board has {len(board_list)} cards (max 5)")
    if len(set(board_list)) != len(board_list):
        raise ValueError("Duplicate cards in board")

    results = [EquityResult() for _ in hands]
    deck = full_deck()
    cards_needed = 5 - len(board_list)
    max_attempts = iterations * max_attempts_multiplier
    attempts = 0
    completed = 0

    while completed < iterations and attempts < max_attempts:
        attempts += 1
        used = set(board_list)
        sampled_hands: List[List[Card]] = []
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
