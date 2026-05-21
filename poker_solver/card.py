"""Cards, decks, and parsing for Texas Hold'em.

Rank values: 2..14 (where 14 = Ace).
Suit values: 0..3 mapping to s, h, d, c.
"""

from __future__ import annotations

import random as _random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

RANKS = "23456789TJQKA"
SUITS = "shdc"
RANK_VALUE = {r: i + 2 for i, r in enumerate(RANKS)}
SUIT_VALUE = {s: i for i, s in enumerate(SUITS)}


@dataclass(frozen=True, order=True)
class Card:
    rank: int
    suit: int

    def __post_init__(self) -> None:
        if not 2 <= self.rank <= 14:
            raise ValueError(f"rank {self.rank} out of range (2..14)")
        if not 0 <= self.suit <= 3:
            raise ValueError(f"suit {self.suit} out of range (0..3)")

    def __str__(self) -> str:
        return RANKS[self.rank - 2] + SUITS[self.suit]

    def __repr__(self) -> str:
        return f"Card('{self}')"

    @classmethod
    def from_str(cls, s: str) -> Card:
        return parse_card(s)


def parse_card(s: str) -> Card:
    if len(s) != 2:
        raise ValueError(f"Invalid card {s!r}: expected 2 characters")
    r, st = s[0].upper(), s[1].lower()
    if r not in RANK_VALUE:
        raise ValueError(f"Invalid rank in {s!r}")
    if st not in SUIT_VALUE:
        raise ValueError(f"Invalid suit in {s!r}")
    return Card(RANK_VALUE[r], SUIT_VALUE[st])


def _tokenize_cards(s: str) -> list[str]:
    s = s.replace(",", " ").strip()
    if not s:
        return []
    if any(ch.isspace() for ch in s):
        return [t for t in s.split() if t]
    if len(s) % 2 != 0:
        raise ValueError(f"Cannot tokenize cards: {s!r}")
    return [s[i : i + 2] for i in range(0, len(s), 2)]


def parse_hand(s: str) -> list[Card]:
    tokens = _tokenize_cards(s)
    if len(tokens) != 2:
        raise ValueError(f"Hand must have exactly 2 cards, got {len(tokens)}: {s!r}")
    cards = [parse_card(t) for t in tokens]
    if cards[0] == cards[1]:
        raise ValueError(f"Hand has duplicate card: {s!r}")
    return cards


def parse_board(s: str) -> list[Card]:
    tokens = _tokenize_cards(s)
    if len(tokens) > 5:
        raise ValueError(f"Board must have 0-5 cards, got {len(tokens)}: {s!r}")
    cards = [parse_card(t) for t in tokens]
    if len(set(cards)) != len(cards):
        raise ValueError(f"Duplicate cards in board: {s!r}")
    return cards


_FULL_DECK: list[Card] = [Card(r, s) for r in range(2, 15) for s in range(4)]


def full_deck() -> list[Card]:
    return list(_FULL_DECK)


class Deck:
    """A shuffleable deck. Pass `exclude` to remove specific cards (e.g., hole cards)."""

    def __init__(self, exclude: Iterable[Card] | None = None) -> None:
        excluded = set(exclude or ())
        self.cards: list[Card] = [c for c in _FULL_DECK if c not in excluded]

    def shuffle(self, rng: _random.Random | None = None) -> None:
        (rng or _random).shuffle(self.cards)

    def deal(self, n: int) -> list[Card]:
        if n < 0:
            raise ValueError("Cannot deal a negative number of cards")
        if n > len(self.cards):
            raise ValueError(f"Cannot deal {n} cards; {len(self.cards)} remaining")
        dealt = self.cards[-n:]
        del self.cards[-n:]
        return dealt

    def __len__(self) -> int:
        return len(self.cards)


def cards_str(cards: Sequence[Card]) -> str:
    return " ".join(str(c) for c in cards)


def card_to_int(card: Card) -> int:
    """Map a Card to a stable integer in [8, 59] = rank * 4 + suit."""
    return card.rank * 4 + card.suit


def int_to_card(card_int: int) -> Card:
    """Inverse of card_to_int."""
    return Card(card_int // 4, card_int % 4)
