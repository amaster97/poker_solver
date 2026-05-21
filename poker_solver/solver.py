"""Solver orchestration: drive DCFR, compute exploitability, package results."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from poker_solver.dcfr import DCFRSolver
from poker_solver.games import Game, KuhnPoker


@dataclass
class SolveResult:
    average_strategy: dict[str, list[float]]
    exploitability_history: list[float] = field(default_factory=list)
    game_value: float = 0.0
    iterations: int = 0
    backend: str = "python"


def solve(
    game: Game,
    iterations: int,
    *,
    backend: str = "python",
    log_every: int | None = None,
    **dcfr_kwargs: Any,
) -> SolveResult:
    """Solve `game` via DCFR.

    Args:
        game: any object implementing the `Game` protocol.
        iterations: total iterations.
        backend: "python" (the reference tier). Rust backend lands in a later PR.
        log_every: if set, record exploitability every `log_every` iterations.
        **dcfr_kwargs: forwarded to `DCFRSolver` (alpha, beta, gamma, seed).
    """
    if backend == "rust":
        return _solve_rust(game, iterations, **dcfr_kwargs)
    if backend != "python":
        raise NotImplementedError(
            f"Backend {backend!r} not yet wired in the Python tier."
        )

    solver = DCFRSolver(game, **dcfr_kwargs)
    history: list[float] = []
    chunks = 1 if log_every is None else max(1, iterations // log_every)
    per_chunk = iterations if log_every is None else log_every
    done = 0
    for _ in range(chunks):
        remaining = iterations - done
        step = min(per_chunk, remaining)
        if step <= 0:
            break
        solver.solve(step)
        done += step
        if log_every is not None:
            history.append(exploitability(game, solver.average_strategy()))
    # Any leftover iterations (when iterations is not a multiple of log_every).
    if done < iterations:
        solver.solve(iterations - done)
        if log_every is not None:
            history.append(exploitability(game, solver.average_strategy()))
    avg = solver.average_strategy()
    value = _game_value(game, avg)
    if log_every is None:
        history.append(exploitability(game, avg))
    return SolveResult(
        average_strategy=avg,
        exploitability_history=history,
        game_value=value,
        iterations=iterations,
        backend=backend,
    )


def exploitability(game: Game, strategy: Mapping[str, Sequence[float]]) -> float:
    """Return mean over players of (best-response value - on-strategy value).

    For zero-sum 2p games, this equals NashConv / num_players; matches the
    `exploitability` definition used in OpenSpiel and the DCFR paper.
    """
    on_policy = _expected_value(
        game,
        strategy,
        game.initial_state(),
        np.ones(game.num_players + 1, dtype=np.float64),
    )
    total = 0.0
    for player in range(game.num_players):
        br_value = _best_response_value(game, strategy, player)
        total += br_value - on_policy[player]
    return total / game.num_players


def _game_value(game: Game, strategy: Mapping[str, Sequence[float]]) -> float:
    """Return player 0's expected value under `strategy` (both players)."""
    ev = _expected_value(
        game,
        strategy,
        game.initial_state(),
        np.ones(game.num_players + 1, dtype=np.float64),
    )
    return float(ev[0])


def _expected_value(
    game: Game,
    strategy: Mapping[str, Sequence[float]],
    state: Any,
    reach: np.ndarray,
) -> np.ndarray:
    if game.is_terminal(state):
        return np.asarray(game.utility(state), dtype=np.float64)
    player = game.current_player(state)
    if player == -1:
        value = np.zeros(game.num_players, dtype=np.float64)
        for action, prob in game.chance_outcomes(state):
            new_reach = reach.copy()
            new_reach[-1] *= prob
            value += prob * _expected_value(
                game, strategy, game.apply(state, action), new_reach
            )
        return value
    actions = game.legal_actions(state)
    key = game.infoset_key(state, player)
    probs = strategy.get(key)
    if probs is None:
        probs = [1.0 / len(actions)] * len(actions)
    value = np.zeros(game.num_players, dtype=np.float64)
    for idx, action in enumerate(actions):
        new_reach = reach.copy()
        new_reach[player] *= probs[idx]
        value += probs[idx] * _expected_value(
            game, strategy, game.apply(state, action), new_reach
        )
    return value


def _best_response_value(
    game: Game,
    strategy: Mapping[str, Sequence[float]],
    br_player: int,
) -> float:
    """Compute `br_player`'s value when best-responding to opponents on `strategy`.

    Walks the tree once collecting (state, counterfactual_reach) groups per
    `br_player` infoset, then picks the action maximizing the responder's
    expected utility per infoset.
    """
    infoset_groups: dict[str, list[tuple]] = {}
    _collect_infosets(
        game, strategy, game.initial_state(), 1.0, br_player, infoset_groups
    )
    best_action: dict[str, int] = {}
    for key, entries in infoset_groups.items():
        actions = entries[0][1]
        action_values = np.zeros(len(actions), dtype=np.float64)
        for state, _actions, cf_reach in entries:
            for idx, action in enumerate(actions):
                child_v = _br_state_value(
                    game,
                    strategy,
                    game.apply(state, action),
                    br_player,
                    best_action,
                )
                action_values[idx] += cf_reach * child_v
        best_action[key] = int(np.argmax(action_values))
    return float(
        _br_state_value(
            game,
            strategy,
            game.initial_state(),
            br_player,
            best_action,
        )
    )


def _collect_infosets(
    game: Game,
    strategy: Mapping[str, Sequence[float]],
    state: Any,
    cf_reach: float,
    br_player: int,
    groups: dict[str, list[tuple]],
) -> None:
    if game.is_terminal(state):
        return
    player = game.current_player(state)
    if player == -1:
        for action, prob in game.chance_outcomes(state):
            _collect_infosets(
                game,
                strategy,
                game.apply(state, action),
                cf_reach * prob,
                br_player,
                groups,
            )
        return
    actions = game.legal_actions(state)
    if player == br_player:
        key = game.infoset_key(state, player)
        groups.setdefault(key, []).append((state, actions, cf_reach))
        for action in actions:
            _collect_infosets(
                game, strategy, game.apply(state, action), cf_reach, br_player, groups
            )
    else:
        key = game.infoset_key(state, player)
        probs = strategy.get(key, [1.0 / len(actions)] * len(actions))
        for idx, action in enumerate(actions):
            _collect_infosets(
                game,
                strategy,
                game.apply(state, action),
                cf_reach * probs[idx],
                br_player,
                groups,
            )


def _br_state_value(
    game: Game,
    strategy: Mapping[str, Sequence[float]],
    state: Any,
    br_player: int,
    best_action: Mapping[str, int],
) -> float:
    if game.is_terminal(state):
        return float(game.utility(state)[br_player])
    player = game.current_player(state)
    if player == -1:
        value = 0.0
        for action, prob in game.chance_outcomes(state):
            value += prob * _br_state_value(
                game, strategy, game.apply(state, action), br_player, best_action
            )
        return value
    actions = game.legal_actions(state)
    if player == br_player:
        key = game.infoset_key(state, player)
        idx = best_action.get(key, 0)
        return _br_state_value(
            game, strategy, game.apply(state, actions[idx]), br_player, best_action
        )
    key = game.infoset_key(state, player)
    probs = strategy.get(key, [1.0 / len(actions)] * len(actions))
    value = 0.0
    for idx, action in enumerate(actions):
        value += probs[idx] * _br_state_value(
            game, strategy, game.apply(state, action), br_player, best_action
        )
    return value


def _solve_rust(game: Game, iterations: int, **dcfr_kwargs: Any) -> SolveResult:
    """Run the Rust DCFR production tier and adapt its output to `SolveResult`.

    The Rust extension currently only knows Kuhn; non-Kuhn games raise
    `NotImplementedError` so callers fall back to the Python tier.
    """
    if not isinstance(game, KuhnPoker):
        raise NotImplementedError(
            "Rust backend currently only supports Kuhn poker. "
            f"Got {type(game).__name__}; use backend='python' instead."
        )
    # Localized import so non-Rust environments don't pay the import cost.
    from poker_solver._rust import solve_kuhn as _rust_solve_kuhn  # type: ignore

    alpha = float(dcfr_kwargs.get("alpha", 1.5))
    beta = float(dcfr_kwargs.get("beta", 0.0))
    gamma = float(dcfr_kwargs.get("gamma", 2.0))
    result = _rust_solve_kuhn(int(iterations), alpha, beta, gamma)
    avg = {k: list(v) for k, v in result["average_strategy"].items()}
    # Recompute exploitability and game value via the Python reference
    # functions so the diff test compares like-for-like. The strategies are
    # bit-exact between tiers; the Rust-internal exploitability value can
    # differ by ~1e-4 due to HashMap iteration order in floating-point
    # accumulation. Re-deriving from the strategy removes that noise.
    expl = exploitability(game, avg)
    game_value = _game_value(game, avg)
    return SolveResult(
        average_strategy=avg,
        # Rust tier doesn't stream per-iteration exploitability; surface the
        # final value as a single-entry history so callers can read [-1].
        exploitability_history=[expl],
        game_value=game_value,
        iterations=int(result["iterations"]),
        backend="rust",
    )
