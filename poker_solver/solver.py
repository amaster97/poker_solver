"""Solver orchestration: drive DCFR, compute exploitability, package results."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from poker_solver.dcfr import DCFRSolver
from poker_solver.games import Game, KuhnPoker, LeducPoker
from poker_solver.hunl import HUNLPoker, Street
from poker_solver.pushfold import is_pushfold_mode, solve_pushfold

logger = logging.getLogger(__name__)


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
    force_tree_solve: bool = False,
    locked_strategies: Mapping[str, Sequence[float]] | None = None,
    **dcfr_kwargs: Any,
) -> SolveResult:
    """Solve `game` via DCFR.

    Args:
        game: any object implementing the `Game` protocol.
        iterations: total iterations.
        backend: ``"python"`` (the reference tier) or ``"rust"`` (PR 6
            production tier for HUNL postflop; PR 1/2 Rust for Kuhn/Leduc).
            HUNL preflop on the Rust backend raises ``NotImplementedError``
            pointing at PR 9.
        log_every: if set, record exploitability every `log_every` iterations.
        force_tree_solve: if True, skip the push/fold chart short-circuit and
            always run the tree-builder solver. Power-user escape hatch per
            spec §13 risk row R4; useful for validation runs that need to
            cross-check chart values against a fresh DCFR solve.
        locked_strategies: v1.4 node-locking — pin a player's strategy at a
            specific infoset (or set of infosets) to a fixed probability
            distribution over its legal actions. The other side updates
            against the locked strategy as if it were part of the game's
            structure. Keys are infoset keys (matching
            ``game.infoset_key(state, player)``); values are probability
            vectors aligned with the engine's ``legal_actions`` ordering at
            that node. ``None`` and ``{}`` are bit-identical to the v1.3
            behavior. Returned ``result.average_strategy`` contains the
            locked vectors bit-identically (spec §2.2 / §3.3). When
            ``locked_strategies`` is non-empty and the game is ≤15 BB HUNL
            preflop, this function raises ``ValueError`` (the push/fold
            chart short-circuit is non-trainable; use
            ``force_tree_solve=True`` to override per spec Appendix #3).
        **dcfr_kwargs: forwarded to `DCFRSolver` (alpha, beta, gamma, seed).
    """
    # v1.4 node-locking: refuse locks under the push/fold chart fast path
    # (spec §Appendix #3). Chart values are precomputed and non-trainable;
    # silently routing through them would ignore the lock. Power user can
    # bypass via `force_tree_solve=True` (escape hatch already in the API
    # for chart validation runs).
    if (
        locked_strategies
        and not force_tree_solve
        and isinstance(game, HUNLPoker)
        and game.config.starting_street == Street.PREFLOP
        and is_pushfold_mode(game.config.starting_stack, game.config.big_blind)
    ):
        raise ValueError(
            "locked_strategies is incompatible with the push/fold chart "
            "short-circuit (≤15 BB HUNL preflop). The chart is precomputed "
            "and non-trainable; locks would be silently ignored. Pass "
            "`force_tree_solve=True` to run the tree-builder solver instead."
        )
    # PR 9 §6 canonical dispatch composition (PR 6 inherits):
    #   1. push/fold short-circuit (PR 3.5 — ≤15 BB HUNL preflop → chart)
    #   2. HUNL postflop Rust branch (PR 6 — backend == "rust", postflop)
    #   3. HUNL postflop Python fallback (PR 5)
    #   4. HUNL preflop branch (PR 9 — currently NotImplementedError)
    #   5. Kuhn/Leduc branches (PR 1/2)
    #
    # Inserting the HUNL Rust elif before push/fold would silently bypass
    # the chart for ≤15-BB postflop configs. Order matters.
    if (
        not force_tree_solve
        and isinstance(game, HUNLPoker)
        and game.config.starting_street == Street.PREFLOP
        and is_pushfold_mode(game.config.starting_stack, game.config.big_blind)
    ):
        eff_bb = game.config.starting_stack // game.config.big_blind
        logger.info(
            "solve(): dispatching to pushfold chart at %d BB effective stack",
            eff_bb,
        )
        return solve_pushfold(game.config)
    # PR 6: HUNL postflop Rust branch. Routes to `_solve_rust` (which calls
    # the PyO3 binding `_rust.solve_hunl_postflop`) when the user opts in
    # via `backend="rust"`. The default Python path (next branch) is
    # unchanged from PR 5.
    if (
        backend == "rust"
        and isinstance(game, HUNLPoker)
        and Street.FLOP <= game.config.starting_street < Street.SHOWDOWN
    ):
        return _solve_rust(
            game,
            iterations,
            locked_strategies=locked_strategies,
            **dcfr_kwargs,
        )
    # PR 5: HUNL postflop Python dispatch. See PR 9 spec §6 for the
    # canonical full dispatch composition; PR 5 adds the postflop branch
    # only; the push/fold short-circuit above takes precedence; the Rust
    # branch above pre-empts when `backend == "rust"`.
    if (
        isinstance(game, HUNLPoker)
        and Street.FLOP <= game.config.starting_street < Street.SHOWDOWN
    ):
        from poker_solver.hunl_solver import solve_hunl_postflop

        # Sort kwargs into ones the Python solver accepts directly vs ones
        # that need to ride along inside `dcfr_kwargs` (alpha/beta/gamma).
        _DIRECT_KEYS = {"target_exploitability", "memory_budget_gb", "seed"}
        direct_kwargs: dict[str, Any] = {
            k: v for k, v in dcfr_kwargs.items() if k in _DIRECT_KEYS
        }
        remainder = {k: v for k, v in dcfr_kwargs.items() if k not in _DIRECT_KEYS}
        return solve_hunl_postflop(
            game.config,
            iterations=iterations,
            log_every=log_every,
            dcfr_kwargs=remainder or None,
            locked_strategies=locked_strategies,
            **direct_kwargs,
        )
    # PR 9: HUNL preflop Rust dispatch (opt-in). Composes AFTER push/fold
    # (≤15 BB → chart) and AFTER postflop branches but BEFORE the Python
    # preflop branch — so users that opt into the Rust backend get the
    # production tier.
    if (
        backend == "rust"
        and isinstance(game, HUNLPoker)
        and game.config.starting_street == Street.PREFLOP
        and game.config.initial_hole_cards
    ):
        return _solve_rust(
            game,
            iterations,
            locked_strategies=locked_strategies,
            **dcfr_kwargs,
        )
    # PR 9: HUNL preflop Python dispatch. Composes AFTER push/fold (≤15 BB
    # routed to the chart above) and AFTER the postflop branch (which only
    # fires for starting_street >= FLOP). Subgame-only — `initial_hole_cards`
    # must be set on the config; the preflop solver validates this and
    # raises if not.
    if (
        isinstance(game, HUNLPoker)
        and game.config.starting_street == Street.PREFLOP
        and game.config.initial_hole_cards
    ):
        from poker_solver.preflop import solve_hunl_preflop

        _DIRECT_KEYS_PREFLOP = {
            "target_exploitability",
            "memory_budget_gb",
            "seed",
            "allow_pushfold_range",
        }
        direct_kwargs_pf: dict[str, Any] = {
            k: v for k, v in dcfr_kwargs.items() if k in _DIRECT_KEYS_PREFLOP
        }
        remainder_pf = {
            k: v for k, v in dcfr_kwargs.items() if k not in _DIRECT_KEYS_PREFLOP
        }
        return solve_hunl_preflop(
            game.config,
            iterations=iterations,
            log_every=log_every,
            dcfr_kwargs=remainder_pf or None,
            locked_strategies=locked_strategies,
            **direct_kwargs_pf,
        )
    if backend == "rust":
        return _solve_rust(
            game,
            iterations,
            locked_strategies=locked_strategies,
            **dcfr_kwargs,
        )
    if backend != "python":
        raise NotImplementedError(
            f"Backend {backend!r} not yet wired in the Python tier."
        )

    solver_kwargs: dict[str, Any] = dict(dcfr_kwargs)
    if locked_strategies is not None:
        solver_kwargs["locked_strategies"] = locked_strategies
    solver = DCFRSolver(game, **solver_kwargs)
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

    Walks the tree collecting (state, counterfactual_reach) groups per
    `br_player` infoset, then picks the action maximizing the responder's
    expected utility per infoset. For multi-round games infosets are visited
    in DFS pre-order; one BR pass therefore uses the previous pass's choices
    at deeper infosets, so we iterate to a fixed point.
    """
    infoset_groups: dict[str, list[tuple]] = {}
    _collect_infosets(
        game, strategy, game.initial_state(), 1.0, br_player, infoset_groups
    )
    best_action: dict[str, int] = {}
    while True:
        previous = dict(best_action)
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
        if best_action == previous:
            break
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


def _compute_exploitability_rust(
    config: Any, strategy: Mapping[str, Sequence[float]]
) -> tuple[float, float]:
    """Compute exploitability + P0 game value via the Rust port (PR 15).

    Returns ``(exploitability, game_value)``. Mirrors
    ``exploitability(game, strategy)`` and ``_game_value(game, strategy)``
    semantics but pushes the tree walk to ``_rust.compute_exploitability``
    so the chance-enum-at-root range-vs-range path (`initial_hole_cards
    = ()`) completes in seconds rather than minutes.

    The Rust extension is required (HUNL postflop Rust path already
    requires it). If the import fails for any reason we let the
    ``ImportError`` propagate — silent fallback to the Python walk
    would re-introduce the multi-minute hang.
    """
    from poker_solver._rust import (  # type: ignore[import-untyped]
        compute_exploitability as _rust_compute_exploitability,
    )
    from poker_solver.hunl import _serialize_hunl_config

    config_json = _serialize_hunl_config(config)
    # Marshal the strategy mapping into a plain ``dict[str, list[float]]``;
    # PyO3 accepts a ``dict[str, list[float]]`` directly.
    plain: dict[str, list[float]] = {
        str(k): [float(p) for p in v] for k, v in strategy.items()
    }
    out = _rust_compute_exploitability(config_json, plain)
    expl = float(out["exploitability"])
    # Tiny negative values from float rounding (~1e-9) are surface
    # rounding errors — clamp to keep the API contract that
    # exploitability is non-negative.
    if -1e-9 < expl < 0.0:
        expl = 0.0
    return expl, float(out["game_value"])


def _solve_rust(
    game: Game,
    iterations: int,
    *,
    locked_strategies: Mapping[str, Sequence[float]] | None = None,
    **dcfr_kwargs: Any,
) -> SolveResult:
    """Run the Rust DCFR production tier and adapt its output to `SolveResult`.

    Routes Kuhn → `_rust.solve_kuhn`, Leduc → `_rust.solve_leduc`, HUNL
    postflop → `_rust.solve_hunl_postflop` (PR 6), HUNL preflop (subgame
    mode) → `_rust.solve_hunl_preflop` (PR 9). Other games raise
    `NotImplementedError` so callers fall back to the Python tier.

    v1.4: ``locked_strategies`` threads through the PyO3 boundary as a
    plain ``dict[str, list[float]]`` (PyO3 auto-marshals). The Rust DCFR
    loop reads the lock map per infoset visit and skips both
    ``regret_sum`` and ``strategy_sum`` updates for locked entries
    (mirrors Python tier, spec §3.2).
    """
    alpha = float(dcfr_kwargs.get("alpha", 1.5))
    beta = float(dcfr_kwargs.get("beta", 0.0))
    gamma = float(dcfr_kwargs.get("gamma", 2.0))
    # Marshal `locked_strategies` to the wire format the PyO3 binding
    # accepts: `dict[str, list[float]]`. Validation against the engine's
    # legal-action shape is lazy in the Rust loop (matches Python tier).
    locked_wire: dict[str, list[float]] | None
    if locked_strategies is None or len(locked_strategies) == 0:
        locked_wire = None
    else:
        locked_wire = {k: [float(p) for p in v] for k, v in locked_strategies.items()}

    # PR 6/9: HUNL Rust branch. Composes AFTER the push/fold short-circuit
    # in `solve()` (which routes ≤15-BB preflop configs to the chart fast
    # path before reaching this function) — see PR 9 §6 canonical dispatch
    # order.
    if isinstance(game, HUNLPoker):
        # PR 9: route preflop (subgame mode) to the Rust preflop entry.
        # Full-tree preflop (unfixed hole cards) raises NotImplementedError
        # per the PR 9 scope decision (post-v1 follow-up).
        if game.config.starting_street == Street.PREFLOP:
            if not game.config.initial_hole_cards:
                raise NotImplementedError(
                    "HUNL preflop Rust backend is subgame-only (PR 9): "
                    "config must have `initial_hole_cards` set. Full-tree "
                    "preflop (hole cards as 1.6M-combo chance enum) is a "
                    "post-v1 follow-up."
                )
            from poker_solver._rust import (  # type: ignore[import-untyped]
                solve_hunl_preflop as _rust_solve_preflop,
            )
            from poker_solver.hunl import _serialize_hunl_config

            config_json_pf = _serialize_hunl_config(game.config)
            raw_pf = _rust_solve_preflop(
                config_json_pf,
                int(iterations),
                alpha,
                beta,
                gamma,
                dcfr_kwargs.get("target_exploitability"),
                dcfr_kwargs.get("seed"),
                locked_wire,
            )
            avg_pf = {k: list(v) for k, v in raw_pf["average_strategy"].items()}
            # Use the equity-leaf wrapper for exploitability + game_value
            # recompute. The bare HUNLPoker game would walk the intractable
            # postflop subtree under each preflop line; the wrapper collapses
            # those subtrees to equity leaves, matching what the Rust solver
            # actually computed against.
            from poker_solver.preflop import PreflopSubgameGame

            wrap_pf_game = PreflopSubgameGame(game.config)
            expl_pf = exploitability(wrap_pf_game, avg_pf)
            gv_pf = _game_value(wrap_pf_game, avg_pf)
            return SolveResult(
                average_strategy=avg_pf,
                exploitability_history=[expl_pf],
                game_value=gv_pf,
                iterations=int(raw_pf["iterations"]),
                backend="rust",
            )
        # `poker_solver._rust` is the PyO3 extension and lacks `.pyi`
        # stubs. The `type: ignore[import-untyped]` here silences mypy's
        # untyped-import warning; later imports in this function inherit
        # the suppression (mypy reports only the first occurrence per
        # module-load, so the Kuhn/Leduc imports below no longer need it
        # — but they keep their `# type: ignore` for backward compat with
        # the PR 5 surface).
        from poker_solver._rust import (  # type: ignore[import-untyped]
            solve_hunl_postflop as _rust_solve_hunl,
        )
        from poker_solver.abstraction.buckets import resolve_abstraction_ref
        from poker_solver.hunl import _serialize_hunl_config

        config_json = _serialize_hunl_config(game.config)
        abstraction_path: str | None = None
        if game.config.abstraction is not None:
            # Canonical entry: LRU-cached + version-checked resolver per PR 4.
            # Never reach into `game.config.abstraction.source_path` directly
            # — that bypasses the cache and the version check, silently
            # accepting stale artifacts (spec §6.3 lock).
            tables = resolve_abstraction_ref(game.config.abstraction)
            if tables.source_path is not None:
                abstraction_path = str(tables.source_path)
        raw = _rust_solve_hunl(
            config_json,
            abstraction_path,
            int(iterations),
            alpha,
            beta,
            gamma,
            dcfr_kwargs.get("target_exploitability"),
            dcfr_kwargs.get("seed"),
            locked_wire,
        )
        avg = {k: list(v) for k, v in raw["average_strategy"].items()}
        # PR 15 — recompute exploitability + game_value via the Rust port
        # (`_rust.compute_exploitability`). Mirrors D5's "Python recomputes
        # from strategy" contract but moves the bottleneck off the Python
        # tree walk. For chance-enum-at-root configs (range-vs-range mode,
        # `initial_hole_cards = ()`) the Python walk took >10 min; the
        # Rust port closes that gap. For fixed-combo configs the two
        # paths converge to the same value within 1e-6 BB/hand (verified
        # by `tests/test_exploit_diff.py`).
        expl, gv = _compute_exploitability_rust(game.config, avg)
        return SolveResult(
            average_strategy=avg,
            exploitability_history=[expl],
            game_value=gv,
            iterations=int(raw["iterations"]),
            backend="rust",
        )

    # Localized import so non-Rust environments don't pay the import cost.
    # PR 6 note: the HUNL import above carries the `type: ignore[import-untyped]`
    # for `_rust`; mypy reports the missing-stubs warning only once per module
    # load, so the Kuhn/Leduc imports below no longer need their own.
    if isinstance(game, KuhnPoker):
        from poker_solver._rust import solve_kuhn as _rust_solve
    elif isinstance(game, LeducPoker):
        from poker_solver._rust import solve_leduc as _rust_solve
    else:
        raise NotImplementedError(
            "Rust backend currently supports Kuhn, Leduc, and HUNL postflop. "
            f"Got {type(game).__name__}; use backend='python' instead."
        )
    result = _rust_solve(int(iterations), alpha, beta, gamma, locked_wire)
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
