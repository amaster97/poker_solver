import pytest

from poker_solver.card import parse_card as p
from poker_solver.range import parse_range


def test_pair_has_six_combos():
    r = parse_range("AA")
    assert len(r) == 6


def test_suited_has_four_combos():
    r = parse_range("AKs")
    assert len(r) == 4
    for combo in r:
        assert combo[0].suit == combo[1].suit


def test_offsuit_has_twelve_combos():
    r = parse_range("AKo")
    assert len(r) == 12
    for combo in r:
        assert combo[0].suit != combo[1].suit


def test_both_suited_and_offsuit():
    r = parse_range("AK")
    assert len(r) == 16


def test_dash_range_pairs():
    r = parse_range("KK-TT")
    # KK, QQ, JJ, TT = 4 ranks * 6 combos = 24
    assert len(r) == 24


def test_dash_range_suited_kicker():
    r = parse_range("ATs-AKs")
    # ATs, AJs, AQs, AKs = 4 * 4 = 16
    assert len(r) == 16


def test_dash_range_same_gap():
    r = parse_range("T9s-65s")
    # 65s, 76s, 87s, 98s, T9s = 5 * 4 = 20
    assert len(r) == 20


def test_plus_pair():
    r = parse_range("TT+")
    # TT, JJ, QQ, KK, AA = 5 * 6 = 30
    assert len(r) == 30


def test_plus_ace_x():
    r = parse_range("A2s+")
    # A2s..AKs = 12 distinct kickers * 4 suits = 48
    assert len(r) == 48


def test_plus_connector():
    r = parse_range("76s+")
    # 76s, 87s, 98s, T9s, JTs, QJs, KQs, AKs = 8 * 4 = 32 (gap 1, walking top up to ace)
    assert len(r) == 32


def test_combined_with_commas():
    r = parse_range("AA, KK, AKs")
    # 6 + 6 + 4 = 16
    assert len(r) == 16


def test_explicit_combo():
    r = parse_range("AhKh")
    assert len(r) == 1
    combo = list(r)[0]
    assert set(combo) == {p("Ah"), p("Kh")}


def test_invalid_rejects():
    with pytest.raises(ValueError):
        parse_range("ZZ")
    with pytest.raises(ValueError):
        parse_range("AAs")  # pair with suit indicator
    with pytest.raises(ValueError):
        parse_range("AKx")  # invalid suit indicator


def test_no_duplicates_when_merging():
    r = parse_range("AA, AA")
    assert len(r) == 6
