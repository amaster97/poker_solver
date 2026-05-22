from __future__ import annotations

import pytest

from poker_solver import LeducPoker, solve

LEDUC_ITERATIONS = 600
LEDUC_EXPLOIT_THRESHOLD = 0.05


@pytest.fixture(scope="module")
def leduc_run():
    return solve(LeducPoker(), LEDUC_ITERATIONS)


def test_leduc_converges_below_threshold(leduc_run):
    assert leduc_run.exploitability_history[-1] < LEDUC_EXPLOIT_THRESHOLD


def test_leduc_strategy_table_size(leduc_run):
    # 6-card deck collapsed by rank in the infoset key: 3 round-1 contexts per
    # private card (6 per-round shapes) plus 90 round-2 contexts gives 288
    # infosets total (18 in round 1, 270 in round 2). This matches the
    # canonical count for rank-keyed 2-suit Leduc.
    assert len(leduc_run.average_strategy) == 288


def test_leduc_game_value_close_to_known(leduc_run):
    # Southey et al. and follow-up CFR results put P0's equilibrium value
    # near -0.085 chips. A modest iteration count is enough to land in a
    # tight band around this since DCFR's average strategy converges fast.
    assert leduc_run.game_value == pytest.approx(-0.085, abs=0.02)


@pytest.mark.timeout(300)
def test_leduc_exploitability_monotone_trend():
    game = LeducPoker()
    sampled = []
    for n in (100, 300, 600):
        r = solve(game, n)
        sampled.append(r.exploitability_history[-1])
    # Strictly decreasing across these spacings in this regime; allow a
    # 5e-3 wobble to absorb numerical noise from average-strategy updates.
    assert sampled[-1] < sampled[0]
    for prev, cur in zip(sampled, sampled[1:]):
        assert cur <= prev + 5e-3


def test_leduc_strong_hand_seldom_folds(leduc_run):
    # KK is the nuts after a K public card. P0 with K should never fold.
    # We probe the round-2 infoset reached by check-check-then-K-public:
    # key = "13|cc|13|". The strategy has 2 actions in that position (no
    # fold available since stakes == ante); but if P0 ever faces a raise
    # in round 2 with a pair, the fold weight should be near zero.
    raised_key = "13|cc|13|r"
    if raised_key in leduc_run.average_strategy:
        probs = leduc_run.average_strategy[raised_key]
        # Three actions when facing a raise: [fold, call, raise]. Fold
        # probability for KK should be tiny.
        assert probs[0] < 0.05
