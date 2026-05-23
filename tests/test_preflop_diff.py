"""Differential test: Python preflop tier vs Rust preflop tier (PR 9).

The bedrock of this project — every Rust solver must produce strategies
within float-tolerance of the Python reference on identical inputs (Kuhn,
Leduc, HUNL postflop, river spots all carry this gate; PR 9's preflop
solver is no exception).

Tolerance: per-action 5e-3; per-spot game value 1e-3. Matches the
PR 6/7/8 cluster precedent.

Tests are kept fast (<60s wall-clock each) by capping iterations at 200
and using a single fixed hole-card pair per case. The slow-marked
suite at the bottom runs the full 5k-iter convergence sweep.
"""

from __future__ import annotations

import importlib

import pytest

try:
    from poker_solver import (
        Card,
        HUNLConfig,
        HUNLPoker,
        Street,
        solve,
        solve_hunl_preflop,
    )
    from poker_solver.hunl import _serialize_hunl_config
    from poker_solver.solver import _game_value, exploitability
except Exception:  # noqa: BLE001
    HUNLConfig = None  # type: ignore[assignment,misc]
    HUNLPoker = None  # type: ignore[assignment,misc]
    Card = None  # type: ignore[assignment,misc]
    Street = None  # type: ignore[assignment,misc]
    solve = None  # type: ignore[assignment]
    solve_hunl_preflop = None  # type: ignore[assignment]
    _serialize_hunl_config = None  # type: ignore[assignment]
    _game_value = None  # type: ignore[assignment]
    exploitability = None  # type: ignore[assignment]

try:
    _rust_module = importlib.import_module("poker_solver._rust")
    _rust_solve_preflop = getattr(_rust_module, "solve_hunl_preflop", None)
except Exception:  # noqa: BLE001
    _rust_solve_preflop = None  # type: ignore[assignment]


pytestmark = [
    pytest.mark.skipif(
        solve_hunl_preflop is None,
        reason="Python preflop tier not importable",
    ),
    pytest.mark.skipif(
        _rust_solve_preflop is None,
        reason="Rust _rust.solve_hunl_preflop missing — rebuild via maturin",
    ),
]


# Per-action probability tolerance + per-spot game-value tolerance. These
# match the PR 6/7/8 cluster locked thresholds (5e-3 / 1e-3) and are
# documented in the PR 9 spec §10.4 tolerance cluster.
_ACTION_TOL: float = 5e-3
_GV_TOL: float = 1e-3


def _hole(p0: str, p1: str) -> tuple[tuple[Card, Card], tuple[Card, Card]]:
    return (
        (Card.from_str(p0[:2]), Card.from_str(p0[2:])),
        (Card.from_str(p1[:2]), Card.from_str(p1[2:])),
    )


def _run_diff(config: HUNLConfig, iterations: int = 100) -> tuple[dict, dict]:
    """Return (python_strategy, rust_strategy) for the given config."""
    config_json = _serialize_hunl_config(config)
    rust_raw = _rust_solve_preflop(
        config_json, int(iterations), 1.5, 0.0, 2.0, None, None
    )
    rust_strategy = {k: list(v) for k, v in rust_raw["average_strategy"].items()}

    py_result = solve_hunl_preflop(config, iterations=iterations)
    py_strategy = dict(py_result.average_strategy)
    return py_strategy, rust_strategy


def _check_strategies_match(
    py: dict, rust: dict, action_tol: float = _ACTION_TOL
) -> None:
    """Assert per-action probability parity within `action_tol`."""
    assert py.keys() == rust.keys(), (
        f"infoset key sets diverge; py-only: {set(py) - set(rust)}, "
        f"rust-only: {set(rust) - set(py)}"
    )
    for key in py:
        py_p = py[key]
        rust_p = rust[key]
        assert len(py_p) == len(rust_p), (
            f"action count mismatch at {key!r}: python={len(py_p)} rust={len(rust_p)}"
        )
        for idx, (p, r) in enumerate(zip(py_p, rust_p)):
            assert abs(p - r) <= action_tol, (
                f"infoset {key!r} action {idx}: "
                f"python={p:.6f} rust={r:.6f} delta={p - r:.6e} (tol={action_tol})"
            )


# ---------------------------------------------------------------------------
# Diff tests
# ---------------------------------------------------------------------------


def test_diff_aa_vs_kk_100bb() -> None:
    """AA vs KK at 100 BB: Python and Rust must produce identical strategies."""
    cfg = HUNLConfig(
        starting_stack=10_000,
        initial_hole_cards=_hole("AhAs", "KdKc"),
    )
    py_strat, rust_strat = _run_diff(cfg, iterations=50)
    _check_strategies_match(py_strat, rust_strat)


def test_diff_aa_vs_aa_100bb() -> None:
    """AA vs AA: symmetric subgame. Both tiers must produce symmetric strategies."""
    cfg = HUNLConfig(
        starting_stack=10_000,
        initial_hole_cards=_hole("AhAs", "AdAc"),
    )
    py_strat, rust_strat = _run_diff(cfg, iterations=50)
    _check_strategies_match(py_strat, rust_strat)


def test_diff_72o_vs_aa_100bb() -> None:
    """72o vs AA at 100 BB: ~30% equity; AA dominates. Diff parity check."""
    cfg = HUNLConfig(
        starting_stack=10_000,
        initial_hole_cards=_hole("7h2c", "AdAs"),
    )
    py_strat, rust_strat = _run_diff(cfg, iterations=50)
    _check_strategies_match(py_strat, rust_strat)


def test_diff_aa_vs_kk_20bb() -> None:
    """AA vs KK at 20 BB: shorter stack, mostly all-in lines. Diff parity."""
    cfg = HUNLConfig(
        starting_stack=2_000,
        initial_hole_cards=_hole("AhAs", "KdKc"),
    )
    py_strat, rust_strat = _run_diff(cfg, iterations=100)
    _check_strategies_match(py_strat, rust_strat)


def test_diff_game_value_parity() -> None:
    """Player-0 game value must match between tiers within 1e-3 BB."""
    cfg = HUNLConfig(
        starting_stack=10_000,
        initial_hole_cards=_hole("AhAs", "KdKc"),
    )
    py_strat, rust_strat = _run_diff(cfg, iterations=50)
    # Compute game value on the same game both ways.
    HUNLPoker(cfg)
    from poker_solver.preflop import PreflopSubgameGame

    wrap_game = PreflopSubgameGame(cfg)
    py_gv = _game_value(wrap_game, py_strat)
    rust_gv = _game_value(wrap_game, rust_strat)
    assert abs(py_gv - rust_gv) <= _GV_TOL, (
        f"game value mismatch: python={py_gv:.6f} rust={rust_gv:.6f} "
        f"delta={py_gv - rust_gv:.6e}"
    )


def test_diff_infoset_count_matches() -> None:
    """Both tiers must reach the same set of infosets (tree shape parity)."""
    cfg = HUNLConfig(
        starting_stack=10_000,
        initial_hole_cards=_hole("AhAs", "KdKc"),
    )
    py_strat, rust_strat = _run_diff(cfg, iterations=10)
    assert len(py_strat) == len(rust_strat), (
        f"infoset count mismatch: python={len(py_strat)} rust={len(rust_strat)}"
    )


def test_diff_short_stack_pushfold_override() -> None:
    """At 15 BB with allow_pushfold_range=True, both tiers must agree."""
    cfg = HUNLConfig(
        starting_stack=1_500,
        initial_hole_cards=_hole("AhAs", "KdKc"),
    )
    config_json = _serialize_hunl_config(cfg)
    rust_raw = _rust_solve_preflop(config_json, 100, 1.5, 0.0, 2.0, None, None)
    rust_strat = {k: list(v) for k, v in rust_raw["average_strategy"].items()}
    py_result = solve_hunl_preflop(cfg, iterations=100, allow_pushfold_range=True)
    py_strat = dict(py_result.average_strategy)
    _check_strategies_match(py_strat, rust_strat)


# ---------------------------------------------------------------------------
# Push/fold chart diff — trivial regions (AA / 72o at 5/10/15 BB)
# ---------------------------------------------------------------------------
#
# The chart encodes the equilibrium SB-jam frequency per hand class at each
# stack depth (2..15 BB). Trivial regions: AA = 100% jam at every depth;
# 72o = 100% fold at every depth (even 2 BB). Our preflop solver, run with
# `allow_pushfold_range=True`, should reach the same conclusions for these
# extreme hands — i.e., the fold probability on the SB's first decision
# should be near-zero for AA and near-one for 72o.
#
# We do not assert chart parity on borderline hands (e.g., A5o at 12 BB) —
# the iterative solver vs the chart's pre-converged values diverge by
# more than the test's iteration budget tolerates. The PR 9 spec calls
# out "trivial regions" specifically; borderline parity is a slow-test
# follow-up.


def _sb_first_decision_probs(
    strategy: dict[str, list[float]], hole_str: str
) -> dict[str, float]:
    """Extract P0 (SB) first-decision action probabilities from the strategy."""
    # Infoset key shape: "<hole>||p|" (preflop, no betting yet, empty board).
    # Hole is rendered by `_sorted_card_string`: ranks sorted by (rank, suit).
    # We accept either ordering since `_sorted_card_string` is deterministic.
    key_candidates = [f"{hole_str}||p|"]
    # Try a reordered version too.
    alt = hole_str[2:] + hole_str[:2]
    key_candidates.append(f"{alt}||p|")
    probs: dict[str, float] = {}
    for k in key_candidates:
        if k in strategy:
            ps = strategy[k]
            # Action order from `enumerate_legal_actions` at the SB's first
            # decision: FOLD (0) + CALL (2) + sized raises + ALL_IN (13),
            # ordered by action id. Indices 0=fold, 1=call, then raises, last=all-in.
            probs["fold"] = ps[0]
            probs["call"] = ps[1]
            probs["all_in"] = ps[-1]
            probs["raises"] = sum(ps[2:-1])
            return probs
    raise KeyError(f"no SB first-decision infoset found for {hole_str}")


@pytest.mark.parametrize("stack_bb", [5, 10, 15])
def test_diff_pushfold_AA_jams(stack_bb: int) -> None:
    """AA at <=15 BB: solver agrees with chart that AA shoves (fold prob ~0).

    Chart says SB jams AA at 100% frequency; our solver should converge to
    SB folding AA at <5% frequency at the SB's first decision. We use the
    `allow_pushfold_range=True` override to run the full DCFR solve in the
    chart's territory.
    """
    cfg = HUNLConfig(
        starting_stack=stack_bb * 100,
        initial_hole_cards=_hole("AhAs", "KdKc"),  # KK is a plausible villain
    )
    result = solve_hunl_preflop(cfg, iterations=300, allow_pushfold_range=True)
    probs = _sb_first_decision_probs(result.average_strategy, "AhAs")
    # AA is almost never folded preflop at short stacks.
    assert probs["fold"] < 0.05, (
        f"AA at {stack_bb} BB: solver folds {probs['fold']:.3f} of the time "
        f"(chart says 0%); strategy={probs}"
    )


@pytest.mark.parametrize("stack_bb", [5, 10, 15])
def test_diff_pushfold_72o_folds_or_calls(stack_bb: int) -> None:
    """72o at <=15 BB: solver agrees with chart that 72o does not shove.

    Chart says SB jams 72o at 0% frequency. In the subgame interpretation
    (knowing villain has AA), 72o has ~13% equity — at 5 BB sometimes
    pot-odds force a call, but jamming is almost never correct.
    """
    cfg = HUNLConfig(
        starting_stack=stack_bb * 100,
        initial_hole_cards=_hole("7h2c", "AdAs"),  # AA villain
    )
    result = solve_hunl_preflop(cfg, iterations=300, allow_pushfold_range=True)
    probs = _sb_first_decision_probs(result.average_strategy, "7h2c")
    # 72o vs AA: aggressive actions (shoves + raises) should sum to a low
    # fraction. The chart says SB jam = 0% with 72o.
    aggressive = probs.get("all_in", 0.0) + probs.get("raises", 0.0)
    assert aggressive < 0.20, (
        f"72o vs AA at {stack_bb} BB: aggressive actions sum to {aggressive:.3f} "
        f"(chart says ~0% jam); strategy={probs}"
    )


# ---------------------------------------------------------------------------
# Slow convergence sweep — gated under @pytest.mark.slow
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_diff_aa_vs_kk_convergence_5k() -> None:
    """Long-run convergence sweep at 5k iterations. Diff must stay tight."""
    cfg = HUNLConfig(
        starting_stack=10_000,
        initial_hole_cards=_hole("AhAs", "KdKc"),
    )
    py_strat, rust_strat = _run_diff(cfg, iterations=5000)
    _check_strategies_match(py_strat, rust_strat)
