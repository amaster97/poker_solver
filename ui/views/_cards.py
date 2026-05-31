"""Shared card-rendering helpers for the specific-card display sites.

Used wherever the GUI shows *specific* cards (board chips, the combo
inspector, the header spot label) — NOT the 13x13 hand-class matrix,
whose cells are classes ("AKs" / "72o") with no concrete suit.

Renders ``rank + colored suit symbol`` (e.g. ``A♠``). A 4-color deck
(common in solvers) keeps suits distinguishable at a glance:

    spades   ♠ -> theme-aware neutral (``var(--ps-text)``)
    hearts   ♥ -> red
    diamonds ♦ -> blue
    clubs    ♣ -> green

The colors are THEME-AWARE: spades read via the ``--ps-text`` CSS custom
property so they are dark on the light theme and light on the dark theme.
Red / blue / green are mid-tones chosen to clear BOTH backgrounds (not
pure ``#f00`` etc.). Keep the map here (one place) so it is trivial to
retune later.
"""

from __future__ import annotations

import html as _html

from poker_solver.card import RANKS, SUITS, Card

# Unicode suit glyphs, indexed by suit value (SUITS = "shdc").
_SUIT_SYMBOLS: dict[int, str] = {
    0: "♠",  # s -> ♠ spade
    1: "♥",  # h -> ♥ heart
    2: "♦",  # d -> ♦ diamond
    3: "♣",  # c -> ♣ club
}

# Per-suit CSS color. Mid-tones legible on light AND dark backgrounds.
# Spades use the theme-aware ``--ps-text`` var (dark-on-light /
# light-on-dark); the rest are saturated-but-not-pure so they clear both.
_SUIT_COLORS: dict[int, str] = {
    0: "var(--ps-text)",  # s -> theme-aware neutral
    1: "#d83232",  # h -> red
    2: "#3a7bd5",  # d -> blue
    3: "#1f9d4d",  # c -> green
}


def card_symbol(card: Card) -> tuple[str, str, str]:
    """Return ``(rank_str, suit_symbol, css_color)`` for a card.

    ``rank_str`` is the single rank char ("A", "K", ... "2"); ``suit_symbol``
    is the unicode glyph (♠♥♦♣); ``css_color`` is a CSS color string (a
    ``var(--ps-text)`` for spades, a hex mid-tone otherwise).
    """
    rank_str = RANKS[card.rank - 2]
    return rank_str, _SUIT_SYMBOLS[card.suit], _SUIT_COLORS[card.suit]


def card_html(card: Card) -> str:
    """Return an inline HTML ``<span>`` for one card: rank + colored suit.

    The span carries ``aria-label``/``title`` set to the canonical 2-char
    code (e.g. ``"As"``) so screen-readers and any text/marker lookups keep
    a parsable, suit-letter equivalent even though the visible suit is a
    colored glyph.
    """
    rank_str, suit_symbol, color = card_symbol(card)
    canonical = f"{rank_str}{SUITS[card.suit]}"
    aria = _html.escape(canonical, quote=True)
    return (
        f"<span class='ps-card' aria-label='{aria}' title='{aria}' "
        f"style='font-family:Menlo,Consolas,monospace;white-space:nowrap'>"
        f"<span style='color:var(--ps-text)'>{rank_str}</span>"
        f"<span style='color:{color}'>{suit_symbol}</span>"
        f"</span>"
    )


def board_html(cards: list[Card], sep: str = "&nbsp;") -> str:
    """Return inline HTML for a sequence of cards joined by ``sep``."""
    return sep.join(card_html(c) for c in cards)
