import pytest

from poker_solver.card import (
    Deck,
    parse_board,
    parse_card,
    parse_hand,
)


def test_parse_card_roundtrip():
    for s in ["Ah", "Ks", "Td", "2c", "9h"]:
        c = parse_card(s)
        assert str(c) == s


def test_parse_card_case_insensitive():
    assert parse_card("ah") == parse_card("AH") == parse_card("Ah")


def test_parse_card_rejects_bad_input():
    with pytest.raises(ValueError):
        parse_card("Z3")
    with pytest.raises(ValueError):
        parse_card("Ax")
    with pytest.raises(ValueError):
        parse_card("A")


def test_parse_hand_two_cards():
    h = parse_hand("AhKh")
    assert len(h) == 2
    assert str(h[0]) == "Ah" and str(h[1]) == "Kh"


def test_parse_hand_with_spaces_and_commas():
    assert parse_hand("Ah Kh") == parse_hand("AhKh")
    assert parse_hand("Ah,Kh") == parse_hand("AhKh")


def test_parse_hand_rejects_duplicate():
    with pytest.raises(ValueError):
        parse_hand("AhAh")


def test_parse_board_sizes():
    assert parse_board("") == []
    assert len(parse_board("2h7h9d")) == 3
    assert len(parse_board("2h7h9dKsAc")) == 5
    with pytest.raises(ValueError):
        parse_board("2h7h9dKsAc3d")  # 6 cards


def test_parse_board_rejects_duplicates():
    with pytest.raises(ValueError):
        parse_board("AhAh3c")


def test_deck_size_and_dealing():
    d = Deck()
    assert len(d) == 52
    dealt = d.deal(5)
    assert len(dealt) == 5
    assert len(d) == 47


def test_deck_excludes_known_cards():
    excluded = [parse_card("As"), parse_card("Kh")]
    d = Deck(exclude=excluded)
    assert len(d) == 50
    assert parse_card("As") not in d.cards
