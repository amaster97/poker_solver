"""Poker hand range parser.

Accepts comma-separated tokens combining:
- Specific combos: ``AhKh``
- Pairs: ``AA``
- Suited/offsuit: ``AKs``, ``AKo``
- Unspecified suitedness: ``AK`` (expands to both suited and offsuit)
- Ranges: ``KK-TT``, ``ATs-A2s``, ``T9s-65s``
- "Plus" notation: ``TT+``, ``A2s+``, ``76s+``

Example: ``"AA, KK-TT, AKs, AKo, 76s+"``
"""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass, field

from poker_solver.card import RANK_VALUE, RANKS, Card, parse_card

Combo = tuple[Card, Card]


@dataclass
class Range:
    combos: list[Combo] = field(default_factory=list)
    _combo_set: set[Combo] = field(default_factory=set, repr=False)

    def add(self, combo: Iterable[Card]) -> None:
        c = tuple(sorted(combo, key=lambda card: (-card.rank, card.suit)))
        if len(c) != 2:
            raise ValueError(f"Combo must have 2 cards, got {len(c)}")
        if c[0] == c[1]:
            raise ValueError(f"Combo has duplicate card: {c}")
        if c in self._combo_set:
            return
        self._combo_set.add(c)
        self.combos.append(c)

    def __len__(self) -> int:
        return len(self.combos)

    def __iter__(self):
        return iter(self.combos)

    def diff(self, other: "Range") -> "Range":
        """Return a new ``Range`` of combos in ``self`` that are NOT in ``other``.

        Set-difference semantics, preserving combo order from ``self``. This is
        a directional diff (``a.diff(b) != b.diff(a)`` in general).

        Note: the current ``Range`` representation stores each combo with an
        implicit frequency of 1.0 (membership-only). Boolean set-difference is
        therefore equivalent to the frequency-aware definition ``max(self.freq
        - other.freq, 0)`` when all frequencies are 1.0. If per-combo frequency
        storage is added later, this method's per-combo accounting should be
        extended at that point.
        """
        result = Range()
        for combo in self.combos:
            if combo not in other._combo_set:
                result.add(combo)
        return result

    def sample_excluding(self, excluded: set[Card], rng: random.Random) -> Combo | None:
        """Pick a random combo whose cards are not in `excluded`.

        Falls back to a full scan if random rejection fails repeatedly.
        Returns None when no combo in the range is compatible.
        """
        if not self.combos:
            return None
        for _ in range(10):
            combo = rng.choice(self.combos)
            if combo[0] not in excluded and combo[1] not in excluded:
                return combo
        valid = [
            c for c in self.combos if c[0] not in excluded and c[1] not in excluded
        ]
        if not valid:
            return None
        return rng.choice(valid)


def parse_range(spec: str) -> Range:
    r = Range()
    for raw in spec.split(","):
        token = raw.strip()
        if not token:
            continue
        _add_token(token, r)
    return r


# ---------- internals ----------


def _add_token(token: str, r: Range) -> None:
    # Specific 4-character combo like "AhKh".
    if len(token) == 4 and token[1].lower() in "shdc" and token[3].lower() in "shdc":
        c1 = parse_card(token[:2])
        c2 = parse_card(token[2:])
        if c1 == c2:
            raise ValueError(f"Combo has duplicate card: {token!r}")
        r.add((c1, c2))
        return

    if "-" in token:
        lo, hi = token.split("-", 1)
        _add_dash_range(lo.strip(), hi.strip(), r)
        return

    if token.endswith("+"):
        _add_plus(token[:-1], r)
        return

    _add_single(token, r)


@dataclass
class _Token:
    is_pair: bool
    r1: int  # higher rank for non-pairs
    r2: int  # lower rank for non-pairs (== r1 for pairs)
    suit: str | None  # 's', 'o', or None


def _parse_hand_token(token: str) -> _Token:
    if not 2 <= len(token) <= 3:
        raise ValueError(f"Invalid hand token: {token!r}")
    r1c, r2c = token[0].upper(), token[1].upper()
    if r1c not in RANK_VALUE or r2c not in RANK_VALUE:
        raise ValueError(f"Invalid ranks in token: {token!r}")
    suit: str | None = None
    if len(token) == 3:
        suit = token[2].lower()
        if suit not in ("s", "o"):
            raise ValueError(f"Invalid suit indicator in {token!r}; use s or o")
    v1, v2 = RANK_VALUE[r1c], RANK_VALUE[r2c]
    is_pair = v1 == v2
    if is_pair and suit is not None:
        raise ValueError(f"Pair token cannot have suit indicator: {token!r}")
    if not is_pair and v1 < v2:
        v1, v2 = v2, v1
    return _Token(is_pair=is_pair, r1=v1, r2=v2, suit=suit)


def _rank_char(value: int) -> str:
    return RANKS[value - 2]


def _add_single(token: str, r: Range) -> None:
    t = _parse_hand_token(token)
    if t.is_pair:
        for s1 in range(4):
            for s2 in range(s1 + 1, 4):
                r.add((Card(t.r1, s1), Card(t.r2, s2)))
        return
    if t.suit in (None, "s"):
        for s in range(4):
            r.add((Card(t.r1, s), Card(t.r2, s)))
    if t.suit in (None, "o"):
        for s1 in range(4):
            for s2 in range(4):
                if s1 != s2:
                    r.add((Card(t.r1, s1), Card(t.r2, s2)))


def _add_dash_range(lo: str, hi: str, r: Range) -> None:
    a = _parse_hand_token(lo)
    b = _parse_hand_token(hi)
    if a.is_pair != b.is_pair:
        raise ValueError(f"Range endpoints mismatch: {lo}-{hi}")
    if a.suit != b.suit:
        raise ValueError(f"Range endpoints must share suitedness: {lo}-{hi}")
    if a.is_pair:
        lo_r, hi_r = sorted((a.r1, b.r1))
        for v in range(lo_r, hi_r + 1):
            _add_single(_rank_char(v) * 2, r)
        return
    gap_a, gap_b = a.r1 - a.r2, b.r1 - b.r2
    if a.r1 == 14 and b.r1 == 14:
        lo_k, hi_k = sorted((a.r2, b.r2))
        for k in range(lo_k, hi_k + 1):
            token = "A" + _rank_char(k) + (a.suit or "")
            _add_single(token, r)
        return
    if gap_a != gap_b:
        raise ValueError(f"Range endpoints must have same gap: {lo}-{hi}")
    lo_top, hi_top = sorted((a.r1, b.r1))
    for top in range(lo_top, hi_top + 1):
        bot = top - gap_a
        if bot < 2:
            continue
        token = _rank_char(top) + _rank_char(bot) + (a.suit or "")
        _add_single(token, r)


def _add_plus(token: str, r: Range) -> None:
    t = _parse_hand_token(token)
    if t.is_pair:
        for v in range(t.r1, 15):
            _add_single(_rank_char(v) * 2, r)
        return
    if t.r1 == 14:
        # Ace-X: top fixed at A, kicker increases toward K.
        for k in range(t.r2, 14):
            tok = "A" + _rank_char(k) + (t.suit or "")
            _add_single(tok, r)
        return
    gap = t.r1 - t.r2
    for top in range(t.r1, 15):
        bot = top - gap
        if bot < 2:
            continue
        tok = _rank_char(top) + _rank_char(bot) + (t.suit or "")
        _add_single(tok, r)
