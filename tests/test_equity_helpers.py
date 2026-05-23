"""Unit tests for the equity test-helpers.

The expected values for the four audit spots come from
``docs/poker_spots_audit_2026-05-23.md``. Each spot is annotated with the
matching audit row so future regressions can be traced back to the source.

All tests use exact enumeration (two concrete hands + 0..5 board cards), so
results are deterministic — no RNG seeding required.
"""

from __future__ import annotations

import pytest

from tests._equity_helpers import assert_equity_close, equity_of, equity_vs_range

# --- audit spot reproductions -------------------------------------------------


def test_spot1_9sTs_vs_kx_on_double_paired_river():
    """SPOT 1 (audit): 9sTs on K-7-2-K-5 river vs a K-x value hand.

    Audit verdict: hero claimed "10-25%", reality 0-10%. Against any concrete
    K-x value hand on the double-paired board, 9sTs (ten-high, no draw) has
    literally 0% equity on the river.
    """
    hero_eq, villain_eq, tie = equity_of("9sTs", "KcQd", "Kh7d2cKs5d")
    assert hero_eq == pytest.approx(0.0, abs=1e-9)
    assert villain_eq == pytest.approx(1.0, abs=1e-9)
    assert tie == pytest.approx(0.0, abs=1e-9)


def test_spot7_AKs_vs_JJ_on_AsTc5d_flop():
    """SPOT 7 (audit): AhKs vs JhJd on AsTc5d flop.

    Audit verdict: spec said 27/73; reality 91/9 (verified by PokerStove).
    W1.3 retest caught this using the underlying ``equity()`` call — this
    test pins the exact value the helper returns so any future regression
    against the spec is loud.
    """
    hero_eq, villain_eq, _tie = equity_of("AhKs", "JhJd", "AsTc5d")
    assert hero_eq == pytest.approx(0.9081, abs=0.005)
    assert villain_eq == pytest.approx(0.0919, abs=0.005)


def test_spot5_KK_vs_QQset_on_spadey_Qd_turn():
    """SPOT 5 (audit): KcKd vs QcQh on As 7s 2s Qd turn.

    Audit verdict: KK ~4.5%, QQ-set ~95.5%. Uses non-spade KK so the 3-spade
    board does not give KK a K-high flush draw (which would inflate equity to
    ~22%, see implementer note below). KK's only out is runner-K, which is
    1 card away with 2 outs of 46 → 2/46 ≈ 4.35%.
    """
    hero_eq, villain_eq, _tie = equity_of("KcKd", "QcQh", "As7s2sQd")
    assert hero_eq == pytest.approx(0.0435, abs=0.005)
    assert villain_eq == pytest.approx(0.9565, abs=0.005)


def test_spot6_AAset_vs_QQ_on_rainbow_turn():
    """SPOT 6 (audit): AhAd vs QcQh on As 7d 2c 5h turn.

    Audit calculated "QQ ~5% via 2 outs to set". That arithmetic is wrong —
    a set of queens would still LOSE to a set of aces, so QQ's equity is
    literally 0%, not 4.3%. This is precisely the class of error the helper
    is meant to prevent: the audit number was a hand-wave, the helper
    returns ground truth.
    """
    hero_eq, villain_eq, _tie = equity_of("AhAd", "QcQh", "As7d2c5h")
    assert hero_eq == pytest.approx(1.0, abs=1e-9)
    assert villain_eq == pytest.approx(0.0, abs=1e-9)


# --- edge cases ---------------------------------------------------------------


def test_empty_board_preflop_AA_vs_KK():
    """Edge case: empty board (preflop). AA vs KK should be ~81/19.

    Preflop AA vs KK is the classic textbook spot. With an empty board the
    enumeration runouts = C(46, 5) = 1,533,939, which is above the default
    100k enum threshold, so the underlying engine uses Monte Carlo. We pass
    a small ``iterations`` budget to keep the test sub-second; the loose
    tolerance (2 percentage points) absorbs MC noise.
    """
    hero_eq, villain_eq, _tie = equity_of("AhAd", "KsKc", "", iterations=10_000)
    assert hero_eq == pytest.approx(0.815, abs=0.02)
    assert villain_eq == pytest.approx(0.185, abs=0.02)


def test_full_board_river_set_over_set_split():
    """Edge case: 5-card board (river), set over set.

    AsAh (set of aces) vs 7s7h (set of sevens) on Ac 7c 2d 9s Jh. AA has
    full house aces full of sevens; 77 has sevens full of aces. AA wins
    deterministically — exact enumeration with cards_needed=0 returns a
    single runout, so the result is exactly 1.0 / 0.0.
    """
    hero_eq, villain_eq, tie = equity_of("AsAh", "7s7h", "Ac7c2d9sJh")
    assert hero_eq == 1.0
    assert villain_eq == 0.0
    assert tie == 0.0


# --- range and assertion-helper tests ------------------------------------------


def test_equity_vs_range_AA_vs_underpair_range_on_rainbow_turn():
    """Range helper: AhAd vs uniform {QcQh, JcJh, TcTh, 8c8h} on rainbow turn.

    Each underpair has 0 outs to beat a set of aces on the rainbow turn (only
    1 card to come, can't make quads, can't catch any rank that beats trip
    aces). Hero equity is exactly 1.0 across all combos. A small MC budget
    keeps the test sub-second since multi-combo ranges fall through to
    sampling.
    """
    hero_eq = equity_vs_range(
        "AhAd",
        ["QcQh", "JcJh", "TcTh", "8c8h"],
        "As7d2c5h",
        iterations=2_000,
    )
    assert hero_eq == pytest.approx(1.0, abs=1e-9)


def test_assert_equity_close_passes_within_tolerance():
    """assert_equity_close: matching value within tol passes silently."""
    # AKs vs JJ flop is ~0.9081 hero; 0.91 expected with tol=0.01 should pass.
    assert_equity_close("AhKs", "JhJd", "AsTc5d", expected=0.91, tol=0.01)


def test_assert_equity_close_raises_on_mismatch():
    """assert_equity_close: out-of-tolerance value raises AssertionError with diff info."""
    with pytest.raises(AssertionError) as excinfo:
        # Real hero equity ~0.0; claim 0.50 with tol 0.01 → must fail.
        assert_equity_close("9sTs", "KcQd", "Kh7d2cKs5d", expected=0.50, tol=0.01)
    msg = str(excinfo.value)
    assert "9sTs" in msg
    assert "KcQd" in msg
    assert "expected" in msg
