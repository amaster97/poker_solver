"""Unit tests for the UI card-graphics dress-up (issue: real card graphics).

The GUI renders *specific* cards (board / hole / saved-spot board signature)
as colored 4-color-deck suit symbols via ``ui/views/_cards.py`` instead of raw
2-char codes (e.g. ``Ts8h7s``). These tests lock the parsing/splitting logic
that feeds those renders and the ``ps-card`` graphic contract (a colored suit
glyph + a canonical ``aria-label`` like "As" preserved for accessibility /
text-marker lookups).

Pure-Python (no NiceGUI ``User`` fixture, no library DB) so they stay fast and
dependency-free; the full-render assertions live in ``test_ui_chained_tab.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

pytestmark = [pytest.mark.ui]


# ---------------------------------------------------------------------------
# _cards.py contract: graphic span carries the canonical aria-label
# ---------------------------------------------------------------------------


def test_card_html_emits_colored_glyph_and_canonical_aria_label() -> None:
    """``card_html`` returns a ``ps-card`` span with the colored suit glyph
    AND the canonical 2-char ``aria-label`` (e.g. "Ah" -> red heart + "Ah").
    """
    from poker_solver.card import Card
    from ui.views._cards import card_html

    html = card_html(Card.from_str("Ah"))
    assert "ps-card" in html
    assert "♥" in html  # heart glyph
    assert "#d83232" in html  # the heart color from _SUIT_COLORS
    assert "aria-label='Ah'" in html
    assert "title='Ah'" in html

    spade = card_html(Card.from_str("As"))
    assert "♠" in spade
    assert "aria-label='As'" in spade
    # Spades read the theme-aware --ps-text var (dark-on-light/light-on-dark).
    assert "var(--ps-text)" in spade


def test_board_html_joins_canonical_labels_in_order() -> None:
    """``board_html`` emits one ``ps-card`` span per card, in order, each
    carrying its canonical aria-label."""
    import re

    from poker_solver.card import parse_board
    from ui.views._cards import board_html

    html = board_html(parse_board("Ts8h7s"), sep="")
    labels = re.findall(r"aria-label='([^']+)'", html)
    assert labels == ["Ts", "8h", "7s"]
    assert html.count("ps-card") == 3
    # 4-color deck: the heart glyph appears for 8h.
    assert "♥" in html and "♠" in html


# ---------------------------------------------------------------------------
# library_browser._row_title_parts: split title prefix from board cards
# ---------------------------------------------------------------------------


@dataclass
class _FakeMeta:
    """Minimal ``SpotMetadata`` stand-in for the row-title helper."""

    label: str = ""
    spot_id: str = "abcdef0123456789"
    board_signature: str = ""


def test_row_title_parts_splits_card_signature_into_cards() -> None:
    """A clean ``board_signature`` (concatenated 2-char codes) is parsed into
    ``Card`` objects so the row can render colored graphics, with the text
    prefix ending in 'on'."""
    from poker_solver.card import parse_board
    from ui.views.library_browser import _row_title_parts

    prefix, cards = _row_title_parts(
        _FakeMeta(label="AKo vs QQ", board_signature="7s8hTs")
    )
    assert prefix == "AKo vs QQ on"
    assert cards == parse_board("7s8hTs")


def test_row_title_parts_preflop_has_no_board() -> None:
    """A preflop spot (empty signature) yields no board cards."""
    from ui.views.library_browser import _row_title_parts

    prefix, cards = _row_title_parts(_FakeMeta(label="4bp 3-bet pot"))
    assert prefix == "4bp 3-bet pot"
    assert cards is None


def test_row_title_parts_non_card_signature_stays_text() -> None:
    """A non-card shorthand signature (e.g. a stub 'K72r') is not parseable
    as a board, so it falls back to plain text (no crash)."""
    from ui.views.library_browser import _row_title_parts

    prefix, cards = _row_title_parts(
        _FakeMeta(label="spot", board_signature="K72r")
    )
    assert cards is None
    assert prefix == "spot on K72r"


def test_row_title_parts_blank_label_falls_back_to_spot_id() -> None:
    """An empty label uses the ``spot_{id[:8]}`` fallback (matches the old
    text-only ``_row_title`` behavior)."""
    from ui.views.library_browser import _row_title, _row_title_parts

    meta = _FakeMeta(label="", spot_id="deadbeef99887766", board_signature="")
    prefix, cards = _row_title_parts(meta)
    assert prefix == "spot_deadbeef"
    assert cards is None
    # The text-only helper still agrees for the no-board case.
    assert _row_title(meta) == "spot_deadbeef"
