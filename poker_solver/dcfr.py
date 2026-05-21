"""Discounted Counterfactual Regret Minimization (DCFR).

Brown, N. and Sandholm, T. (2019). "Solving Imperfect-Information Games via
Discounted Regret Minimization." AAAI 2019. (https://arxiv.org/abs/1809.04040)

This is the Python reference implementation. Each iteration t:

  - Walk the game tree, computing counterfactual values for the current
    strategy (regret matching on positive regrets).
  - Discount the existing cumulative regrets and strategy sums by the DCFR
    factors, then add the iteration's contributions:

      R^t(I, a)  =  R^{t-1}(I, a) * (t^alpha / (t^alpha + 1))  + r^t(I, a)   if R^{t-1} > 0
      R^t(I, a)  =  R^{t-1}(I, a) * (t^beta  / (t^beta  + 1))  + r^t(I, a)   if R^{t-1} <= 0
      s_I[a]     =  s_I[a] * (t / (t + 1))^gamma  +  pi_{-i}(I) * sigma^t(I, a)

  - Default hyperparameters (alpha, beta, gamma) = (1.5, 0.0, 2.0), the
    paper's recommended setting that outperformed CFR+ on every benchmark.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from poker_solver.games import Game


@dataclass
class InfosetData:
    regret_sum: np.ndarray
    strategy_sum: np.ndarray
    num_actions: int
    last_discount_iter: int = field(default=0)


class DCFRSolver:
    """Discounted CFR solver for finite extensive-form games.

    Args:
        game: any object implementing the `Game` protocol.
        alpha: positive-regret discount exponent. Default 1.5 (Brown 2019).
        beta: negative-regret discount exponent. Default 0.0 (Brown 2019).
        gamma: strategy-sum discount exponent. Default 2.0 (Brown 2019).
        seed: unused (DCFR is deterministic), accepted for forward-compat
            with sampling variants.
    """

    def __init__(
        self,
        game: Game,
        *,
        alpha: float = 1.5,
        beta: float = 0.0,
        gamma: float = 2.0,
        seed: int | None = None,
    ) -> None:
        self.game = game
        self.alpha = float(alpha)
        self.beta = float(beta)
        self.gamma = float(gamma)
        self.seed = seed
        self.infosets: dict[str, InfosetData] = {}
        self.iteration: int = 0

    def _get_infoset(self, key: str, num_actions: int) -> InfosetData:
        info = self.infosets.get(key)
        if info is None:
            info = InfosetData(
                regret_sum=np.zeros(num_actions, dtype=np.float64),
                strategy_sum=np.zeros(num_actions, dtype=np.float64),
                num_actions=num_actions,
            )
            self.infosets[key] = info
        return info

    def _get_strategy(self, info: InfosetData) -> np.ndarray:
        positive = np.maximum(info.regret_sum, 0.0)
        total = positive.sum()
        if total > 0.0:
            return positive / total
        return np.full(info.num_actions, 1.0 / info.num_actions, dtype=np.float64)

    def _discount(self, info: InfosetData, t: int) -> None:
        if info.last_discount_iter >= t:
            return
        # Catch up the discount from any prior iteration where we last touched
        # the infoset (lazy discounting; fresh infosets start at zero).
        for tt in range(info.last_discount_iter + 1, t + 1):
            ta = float(tt) ** self.alpha
            tb = float(tt) ** self.beta
            pos_scale = ta / (ta + 1.0)
            neg_scale = tb / (tb + 1.0)
            strat_scale = (float(tt) / (float(tt) + 1.0)) ** self.gamma
            r = info.regret_sum
            np.copyto(
                r, np.where(r > 0.0, r * pos_scale, np.where(r < 0.0, r * neg_scale, r))
            )
            info.strategy_sum *= strat_scale
        info.last_discount_iter = t

    def _cfr(self, state: Any, reach: np.ndarray, iteration: int) -> np.ndarray:
        if self.game.is_terminal(state):
            return np.asarray(self.game.utility(state), dtype=np.float64)

        player = self.game.current_player(state)
        if player == -1:
            value = np.zeros(self.game.num_players, dtype=np.float64)
            for action, prob in self.game.chance_outcomes(state):
                new_reach = reach.copy()
                # Chance reach is tracked in the last slot.
                new_reach[-1] *= prob
                value += prob * self._cfr(
                    self.game.apply(state, action), new_reach, iteration
                )
            return value

        key = self.game.infoset_key(state, player)
        actions = self.game.legal_actions(state)
        info = self._get_infoset(key, len(actions))
        self._discount(info, iteration)
        strategy = self._get_strategy(info)

        node_value = np.zeros(self.game.num_players, dtype=np.float64)
        action_values = np.zeros(
            (len(actions), self.game.num_players), dtype=np.float64
        )
        for idx, action in enumerate(actions):
            new_reach = reach.copy()
            new_reach[player] *= strategy[idx]
            action_values[idx] = self._cfr(
                self.game.apply(state, action), new_reach, iteration
            )
            node_value += strategy[idx] * action_values[idx]

        # Counterfactual reach = product of opponents' and chance's reach.
        opponent_reach = 1.0
        for i in range(len(reach)):
            if i != player:
                opponent_reach *= reach[i]
        own_reach = reach[player]

        regret_delta = opponent_reach * (action_values[:, player] - node_value[player])
        info.regret_sum += regret_delta
        info.strategy_sum += own_reach * strategy
        return node_value

    def solve(self, iterations: int) -> dict[str, list[float]]:
        """Run DCFR for `iterations` iterations; return the average strategy."""
        for _ in range(iterations):
            self.iteration += 1
            reach = np.ones(self.game.num_players + 1, dtype=np.float64)
            self._cfr(self.game.initial_state(), reach, self.iteration)
        # Final catch-up discount so any stale infosets reflect the latest t.
        for info in self.infosets.values():
            self._discount(info, self.iteration)
        return self.average_strategy()

    def average_strategy(self) -> dict[str, list[float]]:
        out: dict[str, list[float]] = {}
        for key, info in self.infosets.items():
            total = info.strategy_sum.sum()
            if total > 0.0:
                out[key] = (info.strategy_sum / total).tolist()
            else:
                out[key] = [1.0 / info.num_actions] * info.num_actions
        return out
