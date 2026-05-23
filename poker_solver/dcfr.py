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

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
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
        locked_strategies: optional v1.4 node-locking map. Keys are infoset
            keys (matching ``game.infoset_key(state, player)``); values are
            probability vectors over the legal-action ordering at that
            infoset. Locked infosets bypass regret-matching and contribute
            neither to ``regret_sum`` nor ``strategy_sum``; the unlocked
            side updates against the locked strategy as if it were part of
            the game's structure. Validated lazily on first visit
            (length / non-negative / sum-to-one) — the catch fires on
            iteration 1, so the cost of validation is paid only on infosets
            the solver actually visits. The map is frozen at construction
            via ``MappingProxyType`` so post-construction mutation is a
            ``TypeError`` rather than a silent corruption (spec §Appendix #1).
    """

    def __init__(
        self,
        game: Game,
        *,
        alpha: float = 1.5,
        beta: float = 0.0,
        gamma: float = 2.0,
        seed: int | None = None,
        locked_strategies: Mapping[str, list[float]] | None = None,
    ) -> None:
        self.game = game
        self.alpha = float(alpha)
        self.beta = float(beta)
        self.gamma = float(gamma)
        self.seed = seed
        self.infosets: dict[str, InfosetData] = {}
        self.iteration: int = 0
        # Internal storage: locked vectors as np.ndarray (avoids per-call
        # array allocation in the hot CFR loop). The public view returns
        # ``list[float]`` per the spec API contract.
        if locked_strategies is None:
            self._locked_strategies: Mapping[str, np.ndarray] = MappingProxyType({})
        else:
            if not isinstance(locked_strategies, Mapping):
                raise TypeError(
                    f"locked_strategies must be a mapping (dict-like), got "
                    f"{type(locked_strategies).__name__!r}."
                )
            frozen: dict[str, np.ndarray] = {}
            for key, vec in locked_strategies.items():
                if not isinstance(key, str):
                    raise TypeError(
                        f"locked_strategies keys must be str, got "
                        f"{type(key).__name__!r}: {key!r}."
                    )
                arr = np.asarray(vec, dtype=np.float64)
                if arr.ndim != 1:
                    raise ValueError(
                        f"locked_strategies[{key!r}] must be a 1D vector, "
                        f"got shape {arr.shape!r}."
                    )
                frozen[key] = arr
            self._locked_strategies = MappingProxyType(frozen)
        # Track which locked keys were actually visited so callers can
        # detect dead locks (R4: infoset-key churn). Surfaced via
        # ``unvisited_locked_keys()``.
        self._visited_locked_keys: set[str] = set()
        # Validation memo: only validate each key on FIRST visit, not every
        # CFR pass. Saves a per-call sum + shape check on the hot path.
        self._validated_locked_keys: set[str] = set()

    @property
    def locked_strategies(self) -> Mapping[str, np.ndarray]:
        """Read-only view of the locked-strategy map (frozen at construction).

        Values are ``np.ndarray``; convert via ``.tolist()`` if you need
        ``list[float]`` for serialization.
        """
        return self._locked_strategies

    def unvisited_locked_keys(self) -> set[str]:
        """Return the set of locked infoset keys that were never visited.

        Useful for diagnosing R4 (lock keys tied to the active action
        abstraction). Empty after a successful solve means every lock was
        applied at least once.
        """
        return set(self._locked_strategies.keys()) - self._visited_locked_keys

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
        # v1.4 node-locking: if this infoset is locked, READ the strategy
        # from the lock map and SKIP both `regret_sum` and `strategy_sum`
        # updates. The locked vector IS the average strategy at output time;
        # appending iteration contributions would dilute it back toward Nash
        # (spec §2.2). One dict lookup per infoset visit; allocation-free
        # in the locked branch.
        locked_vec = self._locked_strategies.get(key)
        if locked_vec is not None:
            if key not in self._validated_locked_keys:
                self._validate_locked_entry(key, locked_vec, len(actions))
                self._validated_locked_keys.add(key)
            self._visited_locked_keys.add(key)
            strategy = locked_vec
            node_value = np.zeros(self.game.num_players, dtype=np.float64)
            for idx, action in enumerate(actions):
                new_reach = reach.copy()
                new_reach[player] *= strategy[idx]
                child = self._cfr(self.game.apply(state, action), new_reach, iteration)
                node_value += strategy[idx] * child
            return node_value

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

    @staticmethod
    def _validate_locked_entry(key: str, vec: np.ndarray, num_actions: int) -> None:
        """Lazy validation of a locked-strategy entry. Fires on first visit.

        Enforces: length matches legal-action count; entries non-negative;
        sum within 1e-9 of 1.0. Failure raises ``ValueError`` with
        actionable remediation per spec §3.4.
        """
        if len(vec) != num_actions:
            raise ValueError(
                f"locked_strategies[{key!r}] has length {len(vec)} but the "
                f"engine emits {num_actions} legal actions; usually means "
                "bet_size_fractions changed since the lock was created."
            )
        if (vec < 0.0).any():
            raise ValueError(
                f"locked_strategies[{key!r}] contains a negative entry "
                f"({vec.tolist()!r}); probabilities must be non-negative."
            )
        total = float(vec.sum())
        if abs(total - 1.0) > 1e-9:
            raise ValueError(
                f"locked_strategies[{key!r}] sums to {total!r}, not 1.0 "
                f"(tolerance 1e-9); normalize before passing in."
            )

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
        # v1.4 node-locking: locked infosets are never inserted into
        # `self.infosets` (the engine never updates regret/strategy for
        # them), so merge their bit-identical vectors back into the output
        # here (spec §3.3). The lock entry IS the average strategy.
        for key, vec in self._locked_strategies.items():
            out[key] = vec.tolist()
        return out
