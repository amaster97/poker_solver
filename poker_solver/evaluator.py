"""5-to-7 card poker hand evaluator.

`evaluate(cards)` returns a tuple `(category, *tiebreakers)` that is directly
comparable: a larger tuple beats a smaller one. The category integers are:

    8 straight flush
    7 four of a kind
    6 full house
    5 flush
    4 straight
    3 three of a kind
    2 two pair
    1 one pair
    0 high card
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from enum import IntEnum

from poker_solver.card import Card


class HandRank(IntEnum):
    HIGH_CARD = 0
    PAIR = 1
    TWO_PAIR = 2
    THREE_OF_A_KIND = 3
    STRAIGHT = 4
    FLUSH = 5
    FULL_HOUSE = 6
    FOUR_OF_A_KIND = 7
    STRAIGHT_FLUSH = 8


def _straight_high(unique_ranks_desc: Sequence[int]) -> int:
    """Return the high card of the best straight, or 0 if none.

    `unique_ranks_desc` must be unique ranks sorted descending.
    Treats Ace as both high (14) and low (1) for the wheel.
    """
    if not unique_ranks_desc:
        return 0
    ranks = list(unique_ranks_desc)
    if ranks[0] == 14:
        ranks.append(1)
    for i in range(len(ranks) - 4):
        if ranks[i] - ranks[i + 4] == 4:
            return ranks[i]
    return 0


def evaluate(cards: Sequence[Card]) -> tuple[int, ...]:
    if len(cards) < 5:
        raise ValueError(f"evaluate needs at least 5 cards, got {len(cards)}")

    ranks_desc = sorted((c.rank for c in cards), reverse=True)
    rank_counts = Counter(ranks_desc)
    suit_counts: Counter = Counter(c.suit for c in cards)

    # Straight flush
    flush_suit = next((s for s, n in suit_counts.items() if n >= 5), None)
    if flush_suit is not None:
        flush_ranks_desc = sorted(
            (c.rank for c in cards if c.suit == flush_suit), reverse=True
        )
        sf_high = _straight_high(flush_ranks_desc)
        if sf_high:
            return (HandRank.STRAIGHT_FLUSH, sf_high)

    # Sort ranks by (count desc, rank desc) so the most frequent (and tiebroken by rank) come first.
    grouped = sorted(rank_counts.items(), key=lambda x: (-x[1], -x[0]))

    # Four of a kind
    if grouped[0][1] == 4:
        quad = grouped[0][0]
        kicker = max(r for r in ranks_desc if r != quad)
        return (HandRank.FOUR_OF_A_KIND, quad, kicker)

    # Full house — either 3+2 or 3+3 (use second trips as the pair).
    if grouped[0][1] == 3:
        trips = grouped[0][0]
        for r, n in grouped[1:]:
            if n >= 2:
                return (HandRank.FULL_HOUSE, trips, r)

    # Flush
    if flush_suit is not None:
        top5 = sorted((c.rank for c in cards if c.suit == flush_suit), reverse=True)[:5]
        return (HandRank.FLUSH, *top5)

    # Straight
    unique_desc = sorted(set(ranks_desc), reverse=True)
    s_high = _straight_high(unique_desc)
    if s_high:
        return (HandRank.STRAIGHT, s_high)

    # Three of a kind
    if grouped[0][1] == 3:
        trips = grouped[0][0]
        kickers = [r for r in ranks_desc if r != trips][:2]
        return (HandRank.THREE_OF_A_KIND, trips, *kickers)

    # Two pair
    if grouped[0][1] == 2 and len(grouped) >= 2 and grouped[1][1] == 2:
        p1, p2 = grouped[0][0], grouped[1][0]
        kicker = max(r for r in ranks_desc if r != p1 and r != p2)
        return (HandRank.TWO_PAIR, p1, p2, kicker)

    # One pair
    if grouped[0][1] == 2:
        pair = grouped[0][0]
        kickers = [r for r in ranks_desc if r != pair][:3]
        return (HandRank.PAIR, pair, *kickers)

    # High card
    return (HandRank.HIGH_CARD, *ranks_desc[:5])
