"""Tests for ``poker_solver.solve_hunl_preflop`` (PR 9 Python tier).

Covers:
  - API contract (config validation, mode='subgame', return shape)
  - Closed-form sanity (AA vs AA -> symmetric / zero game value)
  - Trivial regions: very tight ranges resolve to dominant action
  - Dispatch composition (push/fold short-circuit precedence preserved)
  - Equity-leaf substitution (PreflopSubgameGame produces matching utility)

The differential test against push/fold charts lives in
``tests/test_preflop_diff.py``.
"""

from __future__ import annotations

import pytest

# Defensive imports per the PR 5 test pattern: any breakage during PR 9
# development leaves the rest of the suite importable.
try:
    from poker_solver import (
        PREFLOP_MAX_BB,
        Card,
        HUNLConfig,
        HUNLPoker,
        PreflopSolveResult,
        SolveResult,
        Street,
        solve,
        solve_hunl_preflop,
    )
    from poker_solver.preflop import PreflopSubgameGame, _compute_p0_equity
except Exception:  # noqa: BLE001
    Card = None  # type: ignore[assignment,misc]
    HUNLConfig = None  # type: ignore[assignment,misc]
    HUNLPoker = None  # type: ignore[assignment,misc]
    PREFLOP_MAX_BB = None  # type: ignore[assignment]
    PreflopSolveResult = None  # type: ignore[assignment,misc]
    SolveResult = None  # type: ignore[assignment,misc]
    Street = None  # type: ignore[assignment,misc]
    solve = None  # type: ignore[assignment]
    solve_hunl_preflop = None  # type: ignore[assignment]
    PreflopSubgameGame = None  # type: ignore[assignment,misc]
    _compute_p0_equity = None  # type: ignore[assignment]


pytestmark = pytest.mark.skipif(
    solve_hunl_preflop is None,
    reason="solve_hunl_preflop not importable (PR 9 surface missing)",
)


def _hole(p0: str, p1: str) -> tuple[tuple[Card, Card], tuple[Card, Card]]:
    """Helper: parse two 4-character hole-card strings (e.g. 'AhAs', 'KdKc')."""
    return (
        (Card.from_str(p0[:2]), Card.from_str(p0[2:])),
        (Card.from_str(p1[:2]), Card.from_str(p1[2:])),
    )


# ---------------------------------------------------------------------------
# API contract
# ---------------------------------------------------------------------------


def test_preflop_returns_PreflopSolveResult() -> None:
    """Result is a PreflopSolveResult (subclass of HUNLSolveResult / SolveResult)."""
    cfg = HUNLConfig(starting_stack=10_000, initial_hole_cards=_hole("AhAs", "KdKc"))
    result = solve_hunl_preflop(cfg, iterations=10)
    assert isinstance(result, PreflopSolveResult)
    assert isinstance(result, SolveResult)
    assert result.mode == "subgame"
    assert result.backend == "python"
    assert result.iterations == 10


def test_preflop_rejects_postflop_starting_street() -> None:
    """Postflop configs must route through solve_hunl_postflop."""
    cfg = HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.FLOP,
        initial_board=(
            Card.from_str("As"),
            Card.from_str("Kd"),
            Card.from_str("7c"),
        ),
        initial_pot=200,
        initial_contributions=(100, 100),
        initial_hole_cards=_hole("AhAd", "QsQd"),
    )
    with pytest.raises(ValueError, match="starting_street"):
        solve_hunl_preflop(cfg, iterations=1)


def test_preflop_rejects_missing_hole_cards() -> None:
    """Without fixed hole cards the tree is intractable (1.6M chance enum)."""
    cfg = HUNLConfig(starting_stack=10_000)  # No initial_hole_cards
    with pytest.raises(ValueError, match="initial_hole_cards"):
        solve_hunl_preflop(cfg, iterations=1)


def test_preflop_rejects_pushfold_range_without_override() -> None:
    """Stacks <=15 BB route through the chart by default."""
    cfg = HUNLConfig(
        starting_stack=1_000,  # 10 BB
        initial_hole_cards=_hole("AhAs", "KdKc"),
    )
    with pytest.raises(ValueError, match="push/fold"):
        solve_hunl_preflop(cfg, iterations=1)


def test_preflop_accepts_pushfold_override() -> None:
    """allow_pushfold_range=True opens the chart range to full tree solve."""
    cfg = HUNLConfig(
        starting_stack=1_000,
        initial_hole_cards=_hole("AhAs", "KdKc"),
    )
    result = solve_hunl_preflop(cfg, iterations=20, allow_pushfold_range=True)
    assert result.iterations == 20


def test_preflop_rejects_oversized_stack() -> None:
    """Above PREFLOP_MAX_BB the v1 ceiling kicks in."""
    cfg = HUNLConfig(
        starting_stack=PREFLOP_MAX_BB * 100 + 100,  # 251 BB
        initial_hole_cards=_hole("AhAs", "KdKc"),
    )
    with pytest.raises(ValueError, match="ceiling"):
        solve_hunl_preflop(cfg, iterations=1)


def test_preflop_rejects_two_hole_cards_only() -> None:
    """`initial_hole_cards` must contain exactly two entries (hero + villain).

    PR 31: validation moved up from `solve_hunl_preflop` to
    `HUNLConfig.__post_init__` (loud failure at the dataclass boundary,
    not deep in the solver). Constructing via `replace(...)` now triggers
    the check directly.
    """
    from dataclasses import replace

    cfg = HUNLConfig(starting_stack=10_000, initial_hole_cards=_hole("AhAs", "KdKc"))
    with pytest.raises(ValueError, match="exactly 2"):
        replace(cfg, initial_hole_cards=(_hole("AhAs", "KdKc")[0],))  # 1-tuple


# ---------------------------------------------------------------------------
# Closed-form sanity
# ---------------------------------------------------------------------------


def test_preflop_AA_vs_AA_symmetry() -> None:
    """Identical strength hands: game value should be ~0 (chops on average)."""
    cfg = HUNLConfig(
        starting_stack=10_000,
        initial_hole_cards=_hole("AhAs", "AdAc"),
    )
    result = solve_hunl_preflop(cfg, iterations=200)
    # Tolerance: 0.05 BB (5e-2). Tighter than this requires many more iters.
    assert abs(result.game_value) < 0.05, (
        f"AA vs AA should chop to ~0 BB; got {result.game_value} BB"
    )
    # And exploitability should be very small (true equilibrium with one
    # action at the relevant infosets).
    assert result.exploitability_history[-1] < 0.01, (
        f"AA vs AA equilibrium exploitability "
        f"{result.exploitability_history[-1]} too high"
    )


def test_preflop_AA_vs_KK_AA_has_positive_ev() -> None:
    """AA has ~81.3% equity vs KK; subgame solver should give P0 (AA) positive EV."""
    cfg = HUNLConfig(
        starting_stack=10_000,
        initial_hole_cards=_hole("AhAs", "KdKc"),
    )
    result = solve_hunl_preflop(cfg, iterations=200)
    # Loose bound: AA must extract MORE than the dead BB it would collect from
    # a fold (1.0 BB), OR at the floor it picks up the BB. Either way > 0.5.
    # On the equilibrium where KK folds to AA's shove, AA collects 1 BB.
    assert result.game_value > 0.5, (
        f"AA vs KK should give P0 >= 0.5 BB (KK folds to large bets in subgame); "
        f"got {result.game_value}"
    )


def test_preflop_equity_AA_vs_KK_matches_canonical() -> None:
    """The equity-leaf substitution computes the canonical preflop equity."""
    eq = _compute_p0_equity(
        (Card.from_str("Ah"), Card.from_str("As")),
        (Card.from_str("Kd"), Card.from_str("Kc")),
        (),  # no partial board
    )
    # AA vs KK preflop equity ≈ 0.8126 (Brunson, 2-Player Hold'em odds tables).
    assert 0.805 < eq < 0.820, f"AA vs KK preflop equity {eq} outside [0.805, 0.820]"


# ---------------------------------------------------------------------------
# Dispatch composition
# ---------------------------------------------------------------------------


def test_solve_dispatches_to_pushfold_for_short_stacks() -> None:
    """At 10 BB, `solve()` short-circuits to the chart (PR 3.5)."""
    cfg = HUNLConfig(
        starting_stack=1_000,  # 10 BB - inside push/fold range
        initial_hole_cards=_hole("AhAs", "KdKc"),
    )
    game = HUNLPoker(cfg)
    result = solve(game, iterations=100)
    # Push/fold path sets backend = "pushfold_chart" (not "python").
    assert result.backend == "pushfold_chart", (
        f"≤15-BB preflop should short-circuit to chart; backend={result.backend}"
    )


def test_solve_dispatches_to_preflop_for_deep_stacks() -> None:
    """At 100 BB with fixed hole cards, `solve()` routes through solve_hunl_preflop."""
    cfg = HUNLConfig(
        starting_stack=10_000,  # 100 BB
        initial_hole_cards=_hole("AhAs", "KdKc"),
    )
    game = HUNLPoker(cfg)
    result = solve(game, iterations=50)
    assert result.backend == "python"
    assert isinstance(result, PreflopSolveResult)


# ---------------------------------------------------------------------------
# PreflopSubgameGame behavior
# ---------------------------------------------------------------------------


def test_preflop_subgame_game_is_terminal_at_flop_frontier() -> None:
    """After preflop closes, the wrapper claims the would-be-flop state as terminal."""
    cfg = HUNLConfig(
        starting_stack=10_000,
        initial_hole_cards=_hole("AhAs", "KdKc"),
    )
    game = PreflopSubgameGame(cfg)
    state = game.initial_state()
    # Walk: SB calls, BB checks (closes preflop).
    from poker_solver.action_abstraction import ACTION_CALL, ACTION_CHECK

    state = game.apply(state, ACTION_CALL)  # SB completes
    state = game.apply(state, ACTION_CHECK)  # BB checks option
    # Now the would-be flop frontier. Per the wrapper, this is terminal.
    assert game.is_terminal(state), (
        f"Wrapper should claim preflop-close frontier as terminal; "
        f"street={state.street} board_len={len(state.board)} "
        f"pending={state.pending_board_deals} cur_player={state.cur_player}"
    )
    # Utility should be equity-weighted, near 2 BB * (0.813 - 0.5) ≈ +0.63 for P0.
    u0, u1 = game.utility(state)
    # P0 contributed 100 chips (SB) -> 100 chips total after limp; P1 contributed
    # 100 chips (BB). Pot = 200. P0 equity ≈ 0.813. P0 EV chips = 200 * 0.813 - 100
    #   = 62.6 → 0.626 BB.
    assert 0.5 < u0 < 0.8, f"P0 utility at limp-check leaf should be ~0.6 BB; got {u0}"
    assert u0 + u1 == pytest.approx(0.0, abs=1e-9), "zero-sum utility violated"


def test_preflop_subgame_game_is_terminal_on_fold() -> None:
    """Folds still go through the base-class terminal handling."""
    cfg = HUNLConfig(
        starting_stack=10_000,
        initial_hole_cards=_hole("AhAs", "KdKc"),
    )
    game = PreflopSubgameGame(cfg)
    state = game.initial_state()
    from poker_solver.action_abstraction import ACTION_FOLD

    state = game.apply(state, ACTION_FOLD)  # SB folds
    assert game.is_terminal(state)
    u0, u1 = game.utility(state)
    # SB lost 0.5 BB (the SB blind).
    assert u0 == pytest.approx(-0.5, abs=1e-9)
    assert u1 == pytest.approx(0.5, abs=1e-9)


# ---------------------------------------------------------------------------
# Memory + return shape contracts
# ---------------------------------------------------------------------------


def test_preflop_returns_memory_report() -> None:
    """PreflopSolveResult has a non-None memory_report (PR 5 contract inherits)."""
    cfg = HUNLConfig(
        starting_stack=10_000,
        initial_hole_cards=_hole("AhAs", "KdKc"),
    )
    result = solve_hunl_preflop(cfg, iterations=5)
    assert result.memory_report is not None
    assert result.memory_report.total_gb >= 0.0


def test_preflop_strategy_keys_are_well_formed() -> None:
    """Infoset keys follow the same `hole|board|street|history` format as PR 3."""
    cfg = HUNLConfig(
        starting_stack=10_000,
        initial_hole_cards=_hole("AhAs", "KdKc"),
    )
    result = solve_hunl_preflop(cfg, iterations=5)
    for key in result.average_strategy:
        # Format: "<hole>||<street>|<history>"
        # Hole is 4 chars (2-card pair), board is empty preflop, street is 'p'.
        parts = key.split("|")
        assert len(parts) == 4, f"infoset key {key!r} should have 4 |-fields"
        hole_part = parts[0]
        board_part = parts[1]
        street_part = parts[2]
        assert len(hole_part) == 4, f"hole part should be 4 chars; got {hole_part!r}"
        assert board_part == "", f"preflop board should be empty; got {board_part!r}"
        assert street_part == "p", f"street token should be 'p'; got {street_part!r}"
