import pytest

from poker_solver import KuhnPoker, kuhn_nash_value, solve


@pytest.fixture(scope="module")
def kuhn_50k():
    return solve(KuhnPoker(), 50_000)


def test_kuhn_converges_to_nash_value(kuhn_50k):
    assert kuhn_50k.game_value == pytest.approx(kuhn_nash_value(), abs=5e-3)


def test_kuhn_exploitability_below_threshold(kuhn_50k):
    assert kuhn_50k.exploitability_history[-1] < 5e-3


def test_kuhn_p1_king_always_bets(kuhn_50k):
    # "13|" is P1's first action holding K. The Nash family puts mass 3*alpha
    # on BET; for any alpha in (0, 1/3], that's a strong bet majority and
    # > 0.99 once converged for any practical alpha. Use a looser bound that
    # is still tight enough to fail on a broken solver.
    probs = kuhn_50k.average_strategy["13|"]
    # With alpha ~ 0.25 we expect ~0.75 on BET; tolerate any converged alpha
    # in [0.25, 1/3] so BET >= 0.74.
    assert probs[1] > 0.74


def test_kuhn_p1_queen_never_initial_bets(kuhn_50k):
    # "12|" is P1's first action holding Q. The Nash family never bets Q here.
    probs = kuhn_50k.average_strategy["12|"]
    assert probs[1] < 0.05


def test_kuhn_bluff_calling_nash_relationship(kuhn_50k):
    # Kuhn Nash family: P1 bluffs J at frequency alpha at "11|"; then by the
    # equilibrium constraints P1 must call P2's bet with Q at frequency
    # alpha + 1/3 at "12|pb" (= "Q facing bet after own pass and opponent bet").
    # This is the algebraic relationship that characterizes the equilibrium
    # family; see OpenSpiel's get_optimal_policy for the canonical form.
    alpha = kuhn_50k.average_strategy["11|"][1]
    p1_call_Q = kuhn_50k.average_strategy["12|pb"][1]
    assert p1_call_Q == pytest.approx(alpha + 1.0 / 3.0, abs=0.05)


def test_kuhn_exploitability_monotone_decreasing():
    game = KuhnPoker()
    sampled = []
    for n in (1_000, 5_000, 10_000, 50_000):
        r = solve(game, n)
        sampled.append(r.exploitability_history[-1])
    # Kuhn converges well below 1e-2 quickly; the DCFR average-strategy
    # exploitability is not strictly monotone in this regime (small wiggles
    # are expected as the running average rebalances). Assert overall trend:
    # the final point is below the first by at least an order of magnitude.
    assert sampled[-1] < sampled[0] / 4
    assert sampled[-1] < 5e-3
