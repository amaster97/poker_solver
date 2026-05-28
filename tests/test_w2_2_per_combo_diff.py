"""B10 Phase D — W2.2 Sarah per-combo Range.diff persona verification.

Locks in the literal exemplar from
``docs/b10_per_combo_frequency_plan_2026-05-28.md`` §1:

    "KQo: you 3-bet 0%, GTO 25%."

Pre-B10 (set-membership ``Range.diff``) could not represent the 25%.
Phases A/B/C landed the per-combo weight data model + parser + serializer
(PR #149), engine/aggregator wiring (PR #154), and the per-combo intensity
editor UI (PR #158). Phase D is the persona retest: this test exercises the
literal Sarah exemplar through the public ``parse_range`` / ``Range.diff``
API and asserts the previously-inexpressible 25% survives the diff.

Three cases (per the task brief):
    1. **Literal exemplar.** ``parse_range("KQo:0.25").diff(parse_range("AA"))``
       returns every KQo combo at weight 0.25 (none of them are in the
       user's range, so no per-combo subtraction occurs and the GTO 25%
       passes through).
    2. **Per-combo partial subtraction.**
       ``parse_range("KQo:0.7, JTs:0.4").diff(parse_range("KQo:0.5"))``
       returns KQo at 0.2 (= 0.7 − 0.5) and JTs at 0.4 (untouched).
    3. **All-unit back-compat.** ``parse_range("AA, KK").diff(parse_range("AA"))``
       returns KK at 1.0 (set-membership semantics preserved when all
       inputs are at the default weight 1.0).
"""

from __future__ import annotations

import pytest

from poker_solver.range import parse_range


# ---------------------------------------------------------------------------
# Case 1 — Sarah's literal "KQo: you 3-bet 0%, GTO 25%" exemplar
# ---------------------------------------------------------------------------


def test_w2_2_literal_exemplar_kqo_quarter_diff_user_aa():
    """The previously-inexpressible W2.2 spot: GTO bets KQo 25% of the time,
    Sarah never does. ``gto.diff(user)`` should surface every KQo combo at
    weight 0.25 (the leak Sarah wants to see)."""
    gto = parse_range("KQo:0.25")
    user = parse_range("AA")  # Sarah never 3-bets KQo

    out = gto.diff(user)

    # KQo expands to 12 offsuit combos.
    assert len(out) == 12
    for combo in out:
        # All combos are KQo (rank 13 = K, rank 12 = Q).
        assert {combo[0].rank, combo[1].rank} == {13, 12}
        # Offsuit means the two cards have different suits.
        assert combo[0].suit != combo[1].suit
        # The 25% survives the diff — this is the formerly-inexpressible bit.
        assert combo.weight == pytest.approx(0.25)


def test_w2_2_literal_exemplar_full_user_range():
    """Same literal exemplar with Sarah's full reported user range
    ``AA, KK, QQ, AKs, AKo``: KQo is still entirely absent from the
    user side, so the GTO 25% survives untouched."""
    gto = parse_range("KQo:0.25")
    user = parse_range("AA, KK, QQ, AKs, AKo")

    out = gto.diff(user)

    assert len(out) == 12  # all 12 KQo combos
    for combo in out:
        assert combo.weight == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# Case 2 — per-combo partial subtraction (GTO partial vs user partial)
# ---------------------------------------------------------------------------


def test_w2_2_partial_subtraction_multi_class():
    """``KQo:0.7 - KQo:0.5 = KQo:0.2`` per-combo; JTs:0.4 untouched."""
    a = parse_range("KQo:0.7, JTs:0.4")
    b = parse_range("KQo:0.5")

    out = a.diff(b)

    # 12 KQo offsuit combos + 4 JTs suited combos = 16.
    assert len(out) == 16

    kqo = [c for c in out if {c[0].rank, c[1].rank} == {13, 12} and c[0].suit != c[1].suit]
    jts = [c for c in out if {c[0].rank, c[1].rank} == {11, 10} and c[0].suit == c[1].suit]

    assert len(kqo) == 12
    assert len(jts) == 4
    for combo in kqo:
        assert combo.weight == pytest.approx(0.2)  # 0.7 − 0.5
    for combo in jts:
        assert combo.weight == pytest.approx(0.4)  # untouched


# ---------------------------------------------------------------------------
# Case 3 — all-unit back-compat (set-membership semantics preserved)
# ---------------------------------------------------------------------------


def test_w2_2_all_unit_weight_back_compat():
    """When every combo on both sides has weight 1.0, ``diff`` reduces to
    boolean set difference — exactly the pre-B10 ``Range.diff`` behavior."""
    a = parse_range("AA, KK")
    b = parse_range("AA")

    out = a.diff(b)

    # 6 KK combos remain at weight 1.0.
    assert len(out) == 6
    for combo in out:
        assert combo[0].rank == 13 and combo[1].rank == 13
        assert combo.weight == 1.0
