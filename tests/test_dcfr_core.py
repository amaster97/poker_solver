import numpy as np
import pytest

from poker_solver.dcfr import DCFRSolver, InfosetData
from poker_solver.games import KuhnPoker


def _make_solver(**kwargs):
    return DCFRSolver(KuhnPoker(), **kwargs)


def _make_info(num_actions=2):
    return InfosetData(
        regret_sum=np.zeros(num_actions, dtype=np.float64),
        strategy_sum=np.zeros(num_actions, dtype=np.float64),
        num_actions=num_actions,
    )


def test_regret_matching_uniform_when_no_regret():
    solver = _make_solver()
    info = _make_info(num_actions=3)
    strat = solver._get_strategy(info)
    assert strat == pytest.approx([1 / 3, 1 / 3, 1 / 3])


def test_regret_matching_concentrates_on_positive_regret():
    solver = _make_solver()
    info = _make_info(num_actions=3)
    info.regret_sum[:] = [-1.0, 3.0, 1.0]
    strat = solver._get_strategy(info)
    assert strat == pytest.approx([0.0, 0.75, 0.25])
    assert strat.sum() == pytest.approx(1.0)


def test_dcfr_discount_applied_to_regret_sum():
    # At iteration t with alpha=1.5, the multiplicative factor on positive
    # regrets is t^1.5 / (t^1.5 + 1). At t = 4, that's 8 / 9.
    solver = _make_solver(alpha=1.5, beta=0.0, gamma=2.0)
    info = _make_info(num_actions=2)
    info.regret_sum[:] = [10.0, -4.0]
    info.last_discount_iter = 3
    solver._discount(info, 4)
    pos_factor = (4.0**1.5) / (4.0**1.5 + 1.0)
    neg_factor = (4.0**0.0) / (4.0**0.0 + 1.0)
    assert info.regret_sum[0] == pytest.approx(10.0 * pos_factor)
    assert info.regret_sum[1] == pytest.approx(-4.0 * neg_factor)


def test_dcfr_discount_applied_to_strategy_sum():
    # The strategy-sum factor is (t/(t+1))^gamma. With gamma=2 and t=3,
    # that's (3/4)^2 = 9/16.
    solver = _make_solver(alpha=1.5, beta=0.0, gamma=2.0)
    info = _make_info(num_actions=2)
    info.strategy_sum[:] = [4.0, 2.0]
    info.last_discount_iter = 2
    solver._discount(info, 3)
    expected = (3.0 / 4.0) ** 2.0
    assert info.strategy_sum[0] == pytest.approx(4.0 * expected)
    assert info.strategy_sum[1] == pytest.approx(2.0 * expected)
