"""Poker hand range parser with per-combo fractional weights (B10 Phase A).

Accepts comma-separated tokens combining:

- Specific combos: ``AhKh``
- Pairs: ``AA``
- Suited/offsuit: ``AKs``, ``AKo``
- Unspecified suitedness: ``AK`` (expands to both suited and offsuit)
- Ranges: ``KK-TT``, ``ATs-A2s``, ``T9s-65s``
- "Plus" notation: ``TT+``, ``A2s+``, ``76s+``
- Per-combo / per-class fractional weight suffix: ``AKo:0.25``, ``AA``,
  ``KK:0.5``, ``AhKh:0.3``. Weights are floats in ``[0.0, 1.0]``.

Example: ``"AA, KK-TT, AKs, AKo, 76s+"`` (all combos at weight 1.0)
Example: ``"AKo:0.25, AA, KK:0.5, AhKh:0.3"`` (mixed weights)

The original ``Combo`` was a bare ``tuple[Card, Card]``. Phase A promotes it
to a ``tuple`` subclass that carries a ``weight`` attribute, while preserving
back-compat: ``__hash__`` and ``__eq__`` ignore ``weight`` (inherited from
``tuple``) so a ``Combo`` compares and hashes equal to its underlying tuple.
Iteration, indexing (``combo[0]``, ``c1, c2 = combo``), and ``isinstance(c,
tuple)`` are all automatic via the tuple base class.
"""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Union

from poker_solver.card import RANK_VALUE, RANKS, SUITS, Card, parse_card

# A ``ComboInput`` is anything that can be normalized into a sorted
# ``tuple[Card, Card]`` key: either a ``Combo`` instance or a bare 2-element
# sequence of ``Card`` objects.
ComboInput = Union["Combo", Iterable[Card]]


class Combo(tuple):
    """A 2-card combo with an optional fractional weight.

    Implemented as a ``tuple`` subclass so that ``isinstance(combo, tuple)``
    is True and ``hash(combo) == hash((card1, card2))``. This preserves
    back-compat with the original ``Combo = tuple[Card, Card]`` alias —
    all existing code that treats a Combo as a 2-tuple (indexing,
    unpacking, set/dict membership, ``isinstance`` checks against
    ``HUNLConfig.initial_hole_cards`` validation) keeps working unchanged.

    Equality and hashing are based on the two cards only — two ``Combo``
    objects with the same cards but different weights are considered equal
    and hash to the same value (inherited from ``tuple.__hash__`` /
    ``tuple.__eq__``).

    Cards are stored in the order passed; canonical sorting is the caller's
    responsibility (``Range.add`` sorts on insertion).
    """

    # Stored on each instance by ``__new__`` (tuple subclasses have
    # ``__dict__`` by default unless ``__slots__`` is declared).
    _weight: float

    def __new__(cls, cards: Iterable[Card], weight: float = 1.0) -> Combo:
        # Honor a passed-in Combo's weight when caller leaves weight at the
        # default 1.0 (parallels ``Range.add``'s explicit override rules).
        if isinstance(cards, Combo) and weight == 1.0 and cards.weight != 1.0:
            weight = cards.weight
        # Normalize the cards iterable into a 2-tuple of Card.
        card_tuple = cards if isinstance(cards, tuple) else tuple(cards)
        if len(card_tuple) != 2:
            raise ValueError(f"Combo must have 2 cards, got {len(card_tuple)}")
        if not 0.0 <= weight <= 1.0:
            raise ValueError(f"weight must be in [0.0, 1.0], got {weight!r}")
        inst = tuple.__new__(cls, card_tuple)
        # tuple subclasses have __dict__ by default; store the weight there.
        inst._weight = weight
        return inst

    @property
    def cards(self) -> tuple[Card, Card]:
        """The two cards as a bare 2-tuple (back-compat accessor)."""
        return (self[0], self[1])

    @property
    def weight(self) -> float:
        """Fractional weight in ``[0.0, 1.0]``; default 1.0."""
        return self._weight

    def __repr__(self) -> str:
        return f"Combo(cards=({self[0]!r}, {self[1]!r}), weight={self._weight!r})"

    # ``tuple.__hash__`` and ``tuple.__eq__`` already give the back-compat
    # semantics we want: ``Combo == bare_tuple`` when cards match;
    # ``hash(Combo) == hash(tuple)``. Both ignore ``weight``.

    def __reduce__(self):
        # Pickle support: restore both cards and weight via __new__.
        return (self.__class__, (tuple(self), self._weight))


def _canonical_key(combo: ComboInput) -> tuple[Card, Card]:
    """Normalize a ``ComboInput`` to a sorted ``(Card, Card)`` tuple.

    Sort order matches the legacy ``Range.add`` convention
    ``key=lambda c: (-c.rank, c.suit)`` so higher-rank card comes first;
    ties broken by ascending suit.
    """
    cards = list(combo.cards) if isinstance(combo, Combo) else list(combo)
    if len(cards) != 2:
        raise ValueError(f"Combo must have 2 cards, got {len(cards)}")
    cards.sort(key=lambda card: (-card.rank, card.suit))
    c0, c1 = cards
    if c0 == c1:
        raise ValueError(f"Combo has duplicate card: {(c0, c1)}")
    return (c0, c1)


@dataclass
class Range:
    """A poker range: ordered list of ``Combo`` plus per-combo weight map.

    ``combos`` stores ``Combo`` instances (each with a ``weight``).
    ``_combo_set`` keys on the bare ``tuple[Card, Card]`` so existing code
    that does ``some_tuple in range_._combo_set`` keeps working
    (back-compat invariant; see ``ui/state.py``).
    ``_weight`` mirrors per-combo weights keyed by bare tuple for O(1)
    lookups via ``weight()``.
    """

    combos: list[Combo] = field(default_factory=list)
    _combo_set: set[tuple[Card, Card]] = field(default_factory=set, repr=False)
    _weight: dict[tuple[Card, Card], float] = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------------
    # Construction / membership
    # ------------------------------------------------------------------

    def add(self, combo: ComboInput, weight: float = 1.0) -> None:
        """Add ``combo`` to the range.

        If ``combo`` is already present, the new weight is *summed* with the
        existing weight and capped at ``1.0``. This mirrors the natural
        interpretation of multiple per-combo specifications in
        ``parse_range`` (e.g. ``"AhKh:0.3, AhKh:0.4"`` -> 0.7).

        ``weight`` must be in ``[0.0, 1.0]``. When ``combo`` is a ``Combo``
        with a non-default weight and the explicit ``weight`` argument is
        left at its default (1.0), the ``Combo``'s weight is honored.
        """
        # If caller passed a Combo with a custom weight and didn't override
        # via the explicit ``weight`` arg, honor the Combo's weight.
        if isinstance(combo, Combo) and weight == 1.0 and combo.weight != 1.0:
            weight = combo.weight
        if not 0.0 <= weight <= 1.0:
            raise ValueError(f"weight must be in [0.0, 1.0], got {weight!r}")
        key = _canonical_key(combo)
        if key in self._combo_set:
            new_w = min(1.0, self._weight.get(key, 1.0) + weight)
            self._weight[key] = new_w
            # Replace the Combo entry to reflect the new weight.
            for i, existing in enumerate(self.combos):
                if existing.cards == key:
                    self.combos[i] = Combo(cards=key, weight=new_w)
                    break
            return
        self._combo_set.add(key)
        self._weight[key] = weight
        self.combos.append(Combo(cards=key, weight=weight))

    def __len__(self) -> int:
        return len(self.combos)

    def __iter__(self):
        return iter(self.combos)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Range):
            return NotImplemented
        if self._combo_set != other._combo_set:
            return False
        # Compare weights with a small float tolerance.
        for key in self._combo_set:
            if abs(self._weight.get(key, 0.0) - other._weight.get(key, 0.0)) > 1e-9:
                return False
        return True

    def __hash__(self) -> int:  # pragma: no cover - mutable container
        # Range is mutable (add/diff/normalize); not hashable.
        raise TypeError("Range is not hashable")

    # ------------------------------------------------------------------
    # Weight API (B10 Phase A)
    # ------------------------------------------------------------------

    def weight(self, combo: ComboInput) -> float:
        """Return the weight of ``combo`` (0.0 if absent)."""
        try:
            key = _canonical_key(combo)
        except ValueError:
            return 0.0
        return self._weight.get(key, 0.0)

    def set_weight(self, combo: ComboInput, w: float) -> None:
        """Set the weight of ``combo`` to ``w``.

        Raises ``ValueError`` if ``w`` is not in ``[0.0, 1.0]``. Adds
        ``combo`` to the range if not present.
        """
        if not 0.0 <= w <= 1.0:
            raise ValueError(f"weight must be in [0.0, 1.0], got {w!r}")
        key = _canonical_key(combo)
        if key not in self._combo_set:
            self._combo_set.add(key)
            self.combos.append(Combo(cards=key, weight=w))
            self._weight[key] = w
            return
        self._weight[key] = w
        for i, existing in enumerate(self.combos):
            if existing.cards == key:
                self.combos[i] = Combo(cards=key, weight=w)
                break

    def normalize(self) -> Range:
        """Return a copy where all weights are renormalized to sum to 1.0.

        If the range is empty or total weight is 0, returns an equivalent
        copy. Idempotent: ``r.normalize().normalize() == r.normalize()``.
        """
        total = sum(self._weight.values())
        out = Range()
        if total <= 0.0:
            for c in self.combos:
                out.combos.append(Combo(cards=c.cards, weight=c.weight))
                out._combo_set.add(c.cards)
                out._weight[c.cards] = c.weight
            return out
        for c in self.combos:
            new_w = c.weight / total
            out.combos.append(Combo(cards=c.cards, weight=new_w))
            out._combo_set.add(c.cards)
            out._weight[c.cards] = new_w
        return out

    def merge(self, other: Range, mode: str = "sum") -> Range:
        """Combine ``self`` with ``other`` under one of three modes.

        - ``"sum"``: per-combo weights summed, capped at 1.0.
        - ``"max"``: per-combo weights take the elementwise maximum.
        - ``"union"``: set-union of combos; weights from ``self`` take
          precedence where present, else from ``other``.
        """
        if mode not in ("sum", "max", "union"):
            raise ValueError(f"merge mode must be sum|max|union, got {mode!r}")
        out = Range()
        # Insert self's combos first so combo-list order matches self for
        # the overlap; new combos from `other` append in `other`'s order.
        for c in self.combos:
            key = c.cards
            if mode == "sum":
                w_other = other._weight.get(key, 0.0)
                w = min(1.0, c.weight + w_other)
            elif mode == "max":
                w_other = other._weight.get(key, 0.0)
                w = max(c.weight, w_other)
            else:  # union
                w = c.weight
            out._combo_set.add(key)
            out._weight[key] = w
            out.combos.append(Combo(cards=key, weight=w))
        for c in other.combos:
            key = c.cards
            if key in out._combo_set:
                continue
            if mode == "sum":
                w = min(1.0, c.weight)
            elif mode == "max":
                w = c.weight
            else:  # union
                w = c.weight
            out._combo_set.add(key)
            out._weight[key] = w
            out.combos.append(Combo(cards=key, weight=w))
        return out

    # ------------------------------------------------------------------
    # Diff & sampling
    # ------------------------------------------------------------------

    def diff(self, other: Range) -> Range:
        """Frequency-aware difference: per combo ``w_out = max(w_self - w_other, 0)``.

        Directional (``a.diff(b) != b.diff(a)`` in general). Combos whose
        resulting weight is zero are excluded from the output.

        When every combo on both sides has weight 1.0, this reduces to
        boolean set difference (back-compat with the pre-Phase-A
        implementation).
        """
        result = Range()
        for c in self.combos:
            key = c.cards
            w_self = c.weight
            w_other = other._weight.get(key, 0.0)
            w_out = w_self - w_other
            if w_out <= 0.0:
                continue
            result._combo_set.add(key)
            result._weight[key] = w_out
            result.combos.append(Combo(cards=key, weight=w_out))
        return result

    def sample_excluding(self, excluded: set[Card], rng: random.Random) -> Combo | None:
        """Pick a random combo whose cards are not in ``excluded``.

        Weighted by per-combo weight. When all weights are 1.0 (the common
        case), takes a uniform fast path with rejection sampling — matches
        the legacy behavior to keep call-site semantics identical.
        Returns None when no combo in the range is compatible.
        """
        if not self.combos:
            return None
        # Uniform fast path: all weights are 1.0.
        all_unit = all(c.weight == 1.0 for c in self.combos)
        if all_unit:
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
        # Weighted path: filter then sample proportional to weight.
        feasible = [
            c for c in self.combos if c[0] not in excluded and c[1] not in excluded
        ]
        if not feasible:
            return None
        weights = [c.weight for c in feasible]
        total = sum(weights)
        if total <= 0.0:
            return rng.choice(feasible)
        r = rng.random() * total
        acc = 0.0
        for c, w in zip(feasible, weights):
            acc += w
            if r <= acc:
                return c
        return feasible[-1]

    # ------------------------------------------------------------------
    # Round-trip serialization
    # ------------------------------------------------------------------

    def to_string(self) -> str:
        """Serialize to a comma-separated combo list.

        Emits each combo's concrete card pair (e.g. ``"AhKh"``); combos
        with weight 1.0 emit unadorned, combos with non-1.0 weights emit
        a ``:w`` suffix (e.g. ``"AhKh:0.25"``). Parsing the result with
        :func:`parse_range` reconstructs an equal ``Range``.
        """
        parts: list[str] = []
        for c in self.combos:
            c0, c1 = c.cards
            tok = f"{_card_to_str(c0)}{_card_to_str(c1)}"
            if abs(c.weight - 1.0) > 1e-9:
                tok += f":{_format_weight(c.weight)}"
            parts.append(tok)
        return ", ".join(parts)


# ---------- parsing ----------


def parse_range(spec: str) -> Range:
    """Parse a comma-separated range specification (see module docstring)."""
    r = Range()
    for raw in spec.split(","):
        token = raw.strip()
        if not token:
            continue
        token, weight = _split_weight(token)
        _add_token(token, r, weight=weight)
    return r


def _split_weight(token: str) -> tuple[str, float]:
    """Split a token like ``"AKo:0.25"`` into ``("AKo", 0.25)``.

    Tokens without ``:`` default to weight 1.0. Raises ``ValueError`` on
    malformed weight (non-float, out of ``[0, 1]``).
    """
    if ":" not in token:
        return token, 1.0
    head, _, tail = token.partition(":")
    head = head.strip()
    tail = tail.strip()
    if not head:
        raise ValueError(f"empty token before ':' in {token!r}")
    try:
        w = float(tail)
    except ValueError as exc:
        raise ValueError(f"invalid weight in token {token!r}: {tail!r}") from exc
    if not 0.0 <= w <= 1.0:
        raise ValueError(f"weight must be in [0.0, 1.0], got {w!r} in {token!r}")
    return head, w


def _add_token(token: str, r: Range, weight: float = 1.0) -> None:
    # Specific 4-character combo like "AhKh".
    if len(token) == 4 and token[1].lower() in "shdc" and token[3].lower() in "shdc":
        c1 = parse_card(token[:2])
        c2 = parse_card(token[2:])
        if c1 == c2:
            raise ValueError(f"Combo has duplicate card: {token!r}")
        r.add((c1, c2), weight=weight)
        return

    if "-" in token:
        lo, hi = token.split("-", 1)
        _add_dash_range(lo.strip(), hi.strip(), r, weight=weight)
        return

    if token.endswith("+"):
        _add_plus(token[:-1], r, weight=weight)
        return

    _add_single(token, r, weight=weight)


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


def _add_single(token: str, r: Range, weight: float = 1.0) -> None:
    t = _parse_hand_token(token)
    if t.is_pair:
        for s1 in range(4):
            for s2 in range(s1 + 1, 4):
                r.add((Card(t.r1, s1), Card(t.r2, s2)), weight=weight)
        return
    if t.suit in (None, "s"):
        for s in range(4):
            r.add((Card(t.r1, s), Card(t.r2, s)), weight=weight)
    if t.suit in (None, "o"):
        for s1 in range(4):
            for s2 in range(4):
                if s1 != s2:
                    r.add((Card(t.r1, s1), Card(t.r2, s2)), weight=weight)


def _add_dash_range(lo: str, hi: str, r: Range, weight: float = 1.0) -> None:
    a = _parse_hand_token(lo)
    b = _parse_hand_token(hi)
    if a.is_pair != b.is_pair:
        raise ValueError(f"Range endpoints mismatch: {lo}-{hi}")
    if a.suit != b.suit:
        raise ValueError(f"Range endpoints must share suitedness: {lo}-{hi}")
    if a.is_pair:
        lo_r, hi_r = sorted((a.r1, b.r1))
        for v in range(lo_r, hi_r + 1):
            _add_single(_rank_char(v) * 2, r, weight=weight)
        return
    gap_a, gap_b = a.r1 - a.r2, b.r1 - b.r2
    if a.r1 == 14 and b.r1 == 14:
        lo_k, hi_k = sorted((a.r2, b.r2))
        for k in range(lo_k, hi_k + 1):
            token = "A" + _rank_char(k) + (a.suit or "")
            _add_single(token, r, weight=weight)
        return
    if gap_a != gap_b:
        raise ValueError(f"Range endpoints must have same gap: {lo}-{hi}")
    lo_top, hi_top = sorted((a.r1, b.r1))
    for top in range(lo_top, hi_top + 1):
        bot = top - gap_a
        if bot < 2:
            continue
        token = _rank_char(top) + _rank_char(bot) + (a.suit or "")
        _add_single(token, r, weight=weight)


def _add_plus(token: str, r: Range, weight: float = 1.0) -> None:
    t = _parse_hand_token(token)
    if t.is_pair:
        for v in range(t.r1, 15):
            _add_single(_rank_char(v) * 2, r, weight=weight)
        return
    if t.r1 == 14:
        # Ace-X: top fixed at A, kicker increases toward K.
        for k in range(t.r2, 14):
            tok = "A" + _rank_char(k) + (t.suit or "")
            _add_single(tok, r, weight=weight)
        return
    gap = t.r1 - t.r2
    for top in range(t.r1, 15):
        bot = top - gap
        if bot < 2:
            continue
        tok = _rank_char(top) + _rank_char(bot) + (t.suit or "")
        _add_single(tok, r, weight=weight)


# ---------- serialization helpers ----------


def _card_to_str(card: Card) -> str:
    """Render a Card as a 2-char string like ``"Ah"``.

    Inverse of ``parse_card``. Rank uses uppercase; suit uses lowercase.
    """
    return RANKS[card.rank - 2] + SUITS[card.suit]


def _format_weight(w: float) -> str:
    """Format a weight in ``[0.0, 1.0]`` compactly for round-trip serialization.

    Strips trailing zeros so 0.25 -> "0.25", 0.3 -> "0.3", 0.5 -> "0.5";
    keeps full precision for arbitrary floats.
    """
    s = f"{w:.6f}".rstrip("0").rstrip(".")
    if s in ("", "-"):
        return "0"
    return s
