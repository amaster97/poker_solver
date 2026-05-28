"""Tests for ``get_pushfold_strategy(..., return_ev=True)`` (task #48).

Marcus's W1.5 chart-lookup persona PARTIAL-rectification: in addition to the
strategy probability, Marcus needs the EV (in BB) of the aggressive action.
This file covers the kwarg's behaviour:

  1. ``return_ev=False`` (default) preserves the legacy ``float`` return shape
     (backward-compat guarantee — additive kwarg, no breaking change).
  2. ``return_ev=True`` returns a dict containing both the strategy probability
     and the EV in BB units, for jam-hand / fold-hand / mixed-decision cases.
  3. Sanity: a strong jam (AKs at 10 BB) must have higher EV than a weak jam
     (72o at 10 BB); both within plausible BB ranges.
"""

from __future__ import annotations

import pytest

from poker_solver import get_pushfold_strategy


def test_default_return_shape_is_float_backcompat():
    """Without ``return_ev`` (or with ``return_ev=False``), the return type is
    a plain ``float`` — the legacy contract for every existing caller."""
    f1 = get_pushfold_strategy(10, "sb_jam", "AKs")
    assert isinstance(f1, float)
    assert 0.0 <= f1 <= 1.0
    f2 = get_pushfold_strategy(10, "sb_jam", "AKs", return_ev=False)
    assert isinstance(f2, float)
    assert f1 == f2


def test_return_ev_true_returns_dict_with_strategy_and_ev_bb():
    """With ``return_ev=True``, callers get a dict carrying both fields."""
    result = get_pushfold_strategy(10, "sb_jam", "AKs", return_ev=True)
    assert isinstance(result, dict)
    assert set(result.keys()) == {"strategy", "ev_bb"}
    assert isinstance(result["strategy"], float)
    assert isinstance(result["ev_bb"], float)
    # AKs at 10 BB is a pure jam in any reasonable HU push/fold chart.
    assert result["strategy"] == pytest.approx(1.0)


def test_return_ev_jam_hand_ev_is_positive():
    """AKs jamming SB at 10 BB has positive EV (steals BB blind often,
    plays well at showdown when called). Loose upper bound: 5 BB."""
    result = get_pushfold_strategy(10, "sb_jam", "AKs", return_ev=True)
    ev = result["ev_bb"]
    assert ev > 0.0, f"Expected positive EV for AKs jam at 10 BB, got {ev}"
    assert ev < 5.0, f"Sanity-bound: EV(AKs jam, 10 BB) should be << 5 BB, got {ev}"


def test_return_ev_fold_hand_ev_is_below_jam():
    """72o at 10 BB has very low (likely negative) jam EV — much worse than
    AKs — which is exactly why the chart prescribes fold for it. The
    aggressive-action EV is still well-defined for any hand (it answers
    'what would this hand earn if it jammed?'), independent of strategy.
    """
    jam_aks = get_pushfold_strategy(10, "sb_jam", "AKs", return_ev=True)
    jam_72o = get_pushfold_strategy(10, "sb_jam", "72o", return_ev=True)
    # Strategy: AKs always jams, 72o never jams at 10 BB.
    assert jam_aks["strategy"] == pytest.approx(1.0)
    assert jam_72o["strategy"] == pytest.approx(0.0)
    # EV(jam | AKs) > EV(jam | 72o): the core sanity check the spec requested.
    assert jam_aks["ev_bb"] > jam_72o["ev_bb"], (
        f"EV(jam AKs)={jam_aks['ev_bb']:.3f} should exceed "
        f"EV(jam 72o)={jam_72o['ev_bb']:.3f} at 10 BB"
    )


def test_return_ev_mixed_decision_hand_returns_well_defined_ev():
    """Mid-strength hands (e.g. K2s at intermediate stack depths) can be
    mixed jam/fold in the equilibrium chart. The aggressive-action EV must
    still be a finite, well-defined float — regardless of how the strategy
    splits."""
    # Pick a depth + hand that's plausibly mixed; even if it ends up pure,
    # the EV field still has to be a number in a sensible BB band.
    result = get_pushfold_strategy(8, "sb_jam", "K2s", return_ev=True)
    assert isinstance(result["ev_bb"], float)
    # Loose physical bound: EV per hand at 8 BB lies in (-8 BB, +8 BB).
    assert -8.0 < result["ev_bb"] < 8.0, (
        f"EV {result['ev_bb']} out of physical bound at 8 BB depth"
    )


def test_return_ev_bb_call_position_also_works():
    """The kwarg also covers the BB call-vs-jam position; AA defending vs
    SB jam at 10 BB has a large positive EV (huge equity vs the SB jam range)."""
    result = get_pushfold_strategy(10, "bb_call_vs_jam", "AA", return_ev=True)
    assert isinstance(result, dict)
    assert result["strategy"] == pytest.approx(1.0)  # AA always calls
    # EV must be strongly positive — AA has ~80%+ equity vs any SB jam range.
    assert result["ev_bb"] > 2.0, (
        f"AA defending vs jam at 10 BB should earn > 2 BB, got {result['ev_bb']}"
    )
