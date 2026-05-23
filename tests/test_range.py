import pytest

from poker_solver.card import parse_card as p
from poker_solver.range import Range, parse_range


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


# ---------- Range.diff() ----------


def test_diff_against_empty_range_equals_self():
    a = parse_range("AA, KK")
    empty = Range()
    out = a.diff(empty)
    assert len(out) == len(a)
    assert set(out.combos) == set(a.combos)


def test_diff_against_self_is_empty():
    a = parse_range("AA, KK, AKs")
    out = a.diff(a)
    assert len(out) == 0
    assert list(out) == []


def test_diff_against_superset_is_empty():
    sub = parse_range("AA")
    sup = parse_range("AA, KK, QQ")
    out = sub.diff(sup)
    assert len(out) == 0


def test_diff_partial_overlap_removes_only_shared_combos():
    a = parse_range("AA, KK")  # 6 + 6 = 12 combos
    b = parse_range("AA, QQ")  # AA shared, QQ not in a
    out = a.diff(b)
    # All KK combos remain; no AA combos.
    assert len(out) == 6
    for combo in out:
        # KK = rank value 13
        assert combo[0].rank == 13 and combo[1].rank == 13


def test_diff_boolean_set_semantics_all_freq_one():
    # With the current Range (implicit freq=1.0 per combo), diff is exact
    # set-difference: every combo in `a` not in `b` survives.
    a = parse_range("AKs")  # 4 suited combos
    b = parse_range("AhKh")  # 1 specific combo
    out = a.diff(b)
    assert len(out) == 3
    out_set = set(out.combos)
    # The AhKh combo should be removed; the other three suited combos remain.
    ah_kh = tuple(sorted((p("Ah"), p("Kh")), key=lambda c: (-c.rank, c.suit)))
    assert ah_kh not in out_set
    for combo in out_set:
        assert combo[0].suit == combo[1].suit


def test_diff_is_directional():
    a = parse_range("AA")
    b = parse_range("AA, KK")
    # a.diff(b) is empty (a ⊆ b)
    assert len(a.diff(b)) == 0
    # b.diff(a) yields the KK combos that a doesn't have
    out = b.diff(a)
    assert len(out) == 6
    for combo in out:
        assert combo[0].rank == 13 and combo[1].rank == 13


def test_diff_returns_new_range_does_not_mutate_self():
    a = parse_range("AA, KK")
    b = parse_range("AA")
    original_len = len(a)
    original_combos = list(a.combos)
    _ = a.diff(b)
    # `self` unchanged after diff.
    assert len(a) == original_len
    assert a.combos == original_combos


def test_diff_with_disjoint_ranges_equals_self():
    a = parse_range("AA")
    b = parse_range("22")
    out = a.diff(b)
    assert len(out) == len(a)
    assert set(out.combos) == set(a.combos)
