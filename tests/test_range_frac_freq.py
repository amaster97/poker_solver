"""B10 Phase A — per-combo fractional weight tests.

Covers:
- ``Combo`` hash/eq ignore weight (cross-type with bare tuple too)
- ``Combo`` back-compat shims (``__iter__``, ``__getitem__``, ``len``)
- ``parse_range`` ``:weight`` suffix grammar (single combo, class, mixed)
- ``Range.weight`` / ``set_weight`` / ``add`` (cap, default, duplicate sum)
- ``Range.normalize`` (idempotent, sum=1)
- ``Range.merge`` (sum / max / union)
- ``Range.diff`` frequency-aware semantics
- ``Range.to_string`` round-trip
- ``Range.sample_excluding`` weighted + uniform fast-path
- Invalid weight detection
"""

from __future__ import annotations

import random

import pytest

from poker_solver.card import parse_card as p
from poker_solver.range import Combo, Range, parse_range

# ---------- Combo back-compat / hash & eq ----------


def test_combo_hash_ignores_weight():
    cards = (p("Ah"), p("Kh"))
    a = Combo(cards, 0.3)
    b = Combo(cards, 0.6)
    assert a == b
    assert hash(a) == hash(b)


def test_combo_equals_bare_tuple():
    cards = (p("Ah"), p("Kh"))
    combo = Combo(cards, 0.42)
    # Combo-side equality.
    assert combo == cards
    # Tuple-side equality (reflective).
    assert cards == combo
    # Hash matches the bare tuple so set membership is cross-type.
    assert hash(combo) == hash(cards)


def test_combo_iteration_and_indexing():
    cards = (p("Qs"), p("Jc"))
    c = Combo(cards, 0.7)
    # __iter__ unpacks like a tuple.
    a, b = c
    assert a == cards[0]
    assert b == cards[1]
    # __getitem__
    assert c[0] == cards[0]
    assert c[1] == cards[1]
    # __len__
    assert len(c) == 2


def test_combo_in_set_with_bare_tuple_key():
    cards = (p("Ah"), p("Kh"))
    s = {cards}
    assert Combo(cards, 0.5) in s
    s2 = {Combo(cards, 0.5)}
    assert cards in s2


# ---------- parse_range :weight grammar ----------


def test_parse_range_class_weight_single():
    # AKs:0.5 -> 4 suited combos each at 0.5.
    r = parse_range("AKs:0.5")
    assert len(r) == 4
    for c in r:
        assert c.weight == 0.5


def test_parse_range_specific_combo_weight():
    r = parse_range("AhKh:0.3")
    assert len(r) == 1
    assert r.combos[0].weight == 0.3


def test_parse_range_mixed_spec():
    # "AKo:0.25, AA, KK:0.5, AhKh:0.3"
    # AKo -> 12 offsuit combos at 0.25
    # AA  -> 6 pair combos at 1.0
    # KK  -> 6 pair combos at 0.5
    # AhKh -> 1 suited combo at 0.3 (not in AKo so stays at 0.3)
    r = parse_range("AKo:0.25, AA, KK:0.5, AhKh:0.3")
    # AhKh is suited (not in AKo), AsAh etc are pairs (not in AKo)
    assert len(r) == 12 + 6 + 6 + 1
    aa = (p("As"), p("Ah"))
    kk = (p("Ks"), p("Kh"))
    ako = (p("As"), p("Kh"))  # offsuit (s vs h)
    ahkh = (p("Ah"), p("Kh"))
    assert r.weight(aa) == 1.0
    assert r.weight(kk) == 0.5
    assert r.weight(ako) == 0.25
    assert r.weight(ahkh) == 0.3


def test_parse_range_no_weight_defaults_to_one():
    r = parse_range("AA")
    for c in r:
        assert c.weight == 1.0


def test_parse_range_weight_invalid_rejects():
    # weight > 1
    with pytest.raises(ValueError):
        parse_range("AA:1.5")
    # weight < 0
    with pytest.raises(ValueError):
        parse_range("AA:-0.1")
    # non-numeric
    with pytest.raises(ValueError):
        parse_range("AA:abc")


# ---------- Range.weight / set_weight / add ----------


def test_weight_absent_returns_zero():
    r = parse_range("AA")
    # KhKs not in AA range.
    assert r.weight((p("Kh"), p("Ks"))) == 0.0


def test_set_weight_changes_value():
    r = parse_range("AA")
    aa = (p("As"), p("Ah"))
    assert r.weight(aa) == 1.0
    r.set_weight(aa, 0.4)
    assert r.weight(aa) == 0.4


def test_set_weight_out_of_range_rejects():
    r = parse_range("AA")
    aa = (p("As"), p("Ah"))
    with pytest.raises(ValueError):
        r.set_weight(aa, 1.5)
    with pytest.raises(ValueError):
        r.set_weight(aa, -0.1)


def test_add_duplicate_sums_with_cap():
    r = Range()
    combo = (p("Ah"), p("Kh"))
    r.add(combo, weight=0.3)
    r.add(combo, weight=0.4)
    assert r.weight(combo) == pytest.approx(0.7)
    # Sum cap at 1.0.
    r.add(combo, weight=0.8)
    assert r.weight(combo) == 1.0


# ---------- normalize ----------


def test_normalize_sums_to_one():
    r = parse_range("AA:0.5, KK:0.3, QQ:0.2")
    n = r.normalize()
    total = sum(c.weight for c in n)
    assert total == pytest.approx(1.0)


def test_normalize_idempotent():
    r = parse_range("AA:0.5, KK:0.3, QQ:0.2")
    n1 = r.normalize()
    n2 = n1.normalize()
    assert n1 == n2


def test_normalize_empty_range_unchanged():
    r = Range()
    n = r.normalize()
    assert len(n) == 0


# ---------- merge ----------


def test_merge_sum_caps_at_one():
    a = parse_range("AA:0.6")
    b = parse_range("AA:0.7")
    out = a.merge(b, mode="sum")
    aa = (p("As"), p("Ah"))
    assert out.weight(aa) == 1.0


def test_merge_max_takes_higher_weight():
    a = parse_range("AA:0.3")
    b = parse_range("AA:0.7")
    out = a.merge(b, mode="max")
    aa = (p("As"), p("Ah"))
    assert out.weight(aa) == 0.7


def test_merge_union_self_takes_precedence():
    a = parse_range("AA:0.3, KK:0.4")
    b = parse_range("AA:0.9, QQ:0.5")
    out = a.merge(b, mode="union")
    aa = (p("As"), p("Ah"))
    qq = (p("Qs"), p("Qh"))
    assert out.weight(aa) == 0.3  # self wins
    assert out.weight(qq) == 0.5  # other-only


def test_merge_invalid_mode_rejects():
    a = parse_range("AA")
    with pytest.raises(ValueError):
        a.merge(a, mode="bogus")


# ---------- diff (frequency-aware) ----------


def test_diff_weight_aware_basic():
    a = parse_range("AA:0.5")
    b = parse_range("AA:0.3")
    out = a.diff(b)
    expected = parse_range("AA:0.2")
    assert out == expected


def test_diff_weight_aware_clamps_at_zero():
    a = parse_range("AA:0.3")
    b = parse_range("AA:0.5")
    # max(0.3 - 0.5, 0) == 0 -> combo excluded.
    out = a.diff(b)
    assert len(out) == 0


def test_diff_partial_class_weight():
    # KQo:0.25 - KQo (1.0) = 0; KQs:0.5 - empty = 0.5.
    a = parse_range("KQo:0.25, KQs:0.5")
    b = parse_range("KQo")
    out = a.diff(b)
    # All KQs combos at 0.5 survive (4 suited).
    assert len(out) == 4
    for c in out:
        assert c.weight == 0.5
        assert c[0].suit == c[1].suit  # suited


# ---------- to_string round-trip ----------


def test_to_string_round_trip_mixed_range():
    r = parse_range("AhKh:0.3, KsKh:0.5, QsJs")
    s = r.to_string()
    r2 = parse_range(s)
    assert r2 == r


def test_to_string_round_trip_kqo_quarter():
    # Literal exemplar from W2.2 Sarah test.
    r = parse_range("KQo:0.25")
    s = r.to_string()
    r2 = parse_range(s)
    assert r2 == r
    # All KQo combos preserve their weight.
    assert len(r2) == 12
    for c in r2:
        assert c.weight == 0.25


def test_to_string_unadorned_for_unit_weights():
    r = parse_range("AhKh")
    s = r.to_string()
    # Single specific combo at weight 1.0 emits no ":1" suffix.
    assert ":" not in s


# ---------- sample_excluding ----------


def test_sample_excluding_weighted_path():
    # Weighted path: combos have non-unit weights. Verify it returns
    # something valid (no exclusion).
    r = parse_range("AhKh:0.5, AsKs:0.5")
    rng = random.Random(42)
    sample = r.sample_excluding(set(), rng)
    assert sample is not None
    assert isinstance(sample, Combo)
    assert sample in r.combos


def test_sample_excluding_uniform_fast_path():
    # All weights 1.0 -> uniform fast path; just verify a valid pick.
    r = parse_range("AKs")
    rng = random.Random(0)
    sample = r.sample_excluding(set(), rng)
    assert sample is not None
    assert sample in r.combos


def test_sample_excluding_all_blocked_returns_none():
    r = parse_range("AhKh:0.3")
    rng = random.Random(0)
    sample = r.sample_excluding({p("Ah")}, rng)
    assert sample is None


# ---------- back-compat: existing tests still pass with new internals ----------


def test_range_iteration_yields_combos_not_tuples():
    # Iteration yields Combo instances but they behave like tuples via
    # __iter__ + __getitem__ + hash/eq semantics.
    r = parse_range("AA")
    for c in r:
        # Combo instance.
        assert isinstance(c, Combo)
        # But unpacks like a 2-tuple.
        c0, c1 = c
        assert c0.rank == 14 and c1.rank == 14
        # And compares equal to a bare tuple.
        assert c == c.cards


def test_combo_in_combo_set_membership():
    # _combo_set keys on bare tuple. ui/state.py:288 does
    # ``combo in self.base_range._combo_set`` and must keep working.
    r = parse_range("AhKh")
    bare = (p("Ah"), p("Kh"))
    assert bare in r._combo_set
    # Combo instance with weight is also a valid membership probe.
    assert Combo(bare, 0.5) in r._combo_set
