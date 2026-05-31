"""Python <-> Rust differential tests for the bet-size menu redesign.

Covers the three changes landed in the menu redesign:

  * C1 per-street opening-bet menus (flop/turn/river).
  * C2 lean raise menu (multiplier-of-the-bet-faced primitive).
  * C3 flop-no-donk (OOP may not open the flop).

Style mirrors ``tests/test_hunl_diff.py``: a solve runs on both tiers and the
per-infoset-per-action strategies are compared within a locked tolerance. The
solve-parity tests use single-street subgames (river/turn start) so the trees
stay tractable without abstraction; the flop-no-donk solve parity rides on the
tiny synthetic abstraction (marked slow). The structural flop-no-donk assertion
runs on the Python tier directly (the rule lives in ``enumerate_legal_actions``;
its cross-tier parity is pinned by the Rust inline tests + the
``test_action_abstraction.py`` unit tests).

Per the project convention: NEVER loosen a tolerance to make a divergence pass.
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest

from poker_solver import (
    ACTION_ALL_IN,
    ACTION_BET_33,
    ACTION_BET_75,
    ACTION_BET_100,
    ACTION_BET_150,
    ACTION_BET_200,
    ACTION_CHECK,
    Card,
    HUNLConfig,
    HUNLPoker,
    Street,
    solve,
)
from tests.fixtures.hunl_solve_fixtures import (
    flop_dry_3size_config,
    tiny_synthetic_abstraction_ref,
)

_rust_solve_hunl: Any = None
try:
    _rust_module = importlib.import_module("poker_solver._rust")
    _rust_solve_hunl = getattr(_rust_module, "solve_hunl_postflop", None)
except ImportError as exc:
    raise RuntimeError(
        f"_rust extension required for bet-menu diff tests but failed to "
        f"import: {exc!r}. Rebuild via `maturin develop --release`; a common "
        f"cause is a stale `.so` from a prior architecture."
    ) from exc

# Locked tolerances mirror test_hunl_diff.py.
PER_ACTION_TOL: float = 1e-3
FLOP_PER_ACTION_TOL: float = 5e-3
ABS_FLOOR: float = 1e-6
ITERATIONS: int = 500
FLOP_ITERATIONS: int = 200
DCFR_KWARGS: dict[str, Any] = {"alpha": 1.5, "beta": 0.0, "gamma": 2.0}

_BASE_SKIP_REASON = (
    "Rust HUNL surface not installed (poker_solver._rust.solve_hunl_postflop)."
)

_RIVER_BOARD = (
    Card.from_str("As"),
    Card.from_str("7c"),
    Card.from_str("2d"),
    Card.from_str("Kh"),
    Card.from_str("5s"),
)
_TURN_BOARD = (
    Card.from_str("As"),
    Card.from_str("7c"),
    Card.from_str("2d"),
    Card.from_str("Kh"),
)
_FLOP_BOARD = (
    Card.from_str("As"),
    Card.from_str("7c"),
    Card.from_str("2d"),
)
_HOLES = (
    (Card.from_str("Ah"), Card.from_str("Kc")),
    (Card.from_str("Qd"), Card.from_str("Qh")),
)

_BET_IDS = (ACTION_BET_33, ACTION_BET_75, ACTION_BET_100, ACTION_BET_150, ACTION_BET_200)


def _require_rust() -> None:
    if _rust_solve_hunl is None:
        pytest.skip(_BASE_SKIP_REASON)


def _check_strategy_diff(
    py_strategy: dict[str, list[float]],
    rs_strategy: dict[str, list[float]],
    tol: float,
    *,
    label: str,
) -> tuple[float, list[str]]:
    """Per-infoset-per-action probability comparison (mirrors test_hunl_diff)."""
    py_keys = set(py_strategy)
    rs_keys = set(rs_strategy)
    diffs: list[str] = []
    if py_keys != rs_keys:
        only_py = sorted(py_keys - rs_keys)[:10]
        only_rs = sorted(rs_keys - py_keys)[:10]
        diffs.append(
            f"[{label}] infoset key sets diverge; only in Python: {only_py}; "
            f"only in Rust: {only_rs}"
        )
        return float("inf"), diffs
    max_abs = 0.0
    for key in sorted(py_keys):
        p_probs = py_strategy[key]
        r_probs = rs_strategy[key]
        if len(p_probs) != len(r_probs):
            diffs.append(
                f"[{label}] {key}: vector length differs "
                f"(py={len(p_probs)} rs={len(r_probs)})"
            )
            continue
        for i, (p, r) in enumerate(zip(p_probs, r_probs)):
            d = abs(p - r)
            max_abs = max(max_abs, d)
            local_tol = max(ABS_FLOOR, tol * max(abs(p), abs(r), ABS_FLOOR))
            if d > local_tol:
                diffs.append(
                    f"[{label}] {key}[{i}]: py={p:.6f} rs={r:.6f} "
                    f"|diff|={d:.3e} tol={local_tol:.3e}"
                )
    return max_abs, diffs


def _solve_both(config: HUNLConfig, iterations: int, tol: float, label: str) -> None:
    game = HUNLPoker(config)
    py = solve(game, iterations=iterations, backend="python", seed=42, **DCFR_KWARGS)
    rs = solve(game, iterations=iterations, backend="rust", seed=42, **DCFR_KWARGS)
    assert py.average_strategy, "Python solve returned empty strategy"
    assert rs.average_strategy, "Rust solve returned empty strategy"
    max_abs, diffs = _check_strategy_diff(
        py.average_strategy, rs.average_strategy, tol=tol, label=label
    )
    assert not diffs, (
        f"Python <-> Rust strategy diverges beyond {tol} on {label}.\n"
        f"Max abs per-action diff: {max_abs:.3e}.\nFirst 10:\n"
        + "\n".join(diffs[:10])
    )


# ---------------------------------------------------------------------------
# C1: per-street menu solve parity (river-start exercises the 4-size river menu).
# ---------------------------------------------------------------------------


def test_c1_river_menu_solve_parity() -> None:
    """River-start subgame with the default 4-size river menu solves identically.

    OOP is not first-to-act here (river start with symmetric contribs puts P1
    to act first with no bet); flop-no-donk does not apply on the river, so OOP
    keeps its opens. The river menu is {0.15, 0.33, 0.75, 1.50}.
    """
    _require_rust()
    config = HUNLConfig(
        starting_stack=1000,
        starting_street=Street.RIVER,
        initial_board=_RIVER_BOARD,
        initial_pot=1000,
        initial_contributions=(500, 500),
        initial_hole_cards=_HOLES,
        river_bet_fractions=(0.15, 0.33, 0.75, 1.50),
        raise_size_xs=(3.0,),
    )
    _solve_both(config, ITERATIONS, PER_ACTION_TOL, "c1_river_menu")


def test_c1_turn_menu_solve_parity() -> None:
    """Turn-start subgame with the default 3-size turn menu solves identically."""
    _require_rust()
    config = HUNLConfig(
        starting_stack=600,
        starting_street=Street.TURN,
        initial_board=_TURN_BOARD,
        initial_pot=400,
        initial_contributions=(200, 200),
        initial_hole_cards=_HOLES,
        turn_bet_fractions=(0.33, 0.75, 1.50),
        raise_size_xs=(3.0,),
    )
    _solve_both(config, ITERATIONS, PER_ACTION_TOL, "c1_turn_menu")


# ---------------------------------------------------------------------------
# C2: lean raise solve parity (river-start with a small raise menu + facing bet).
# ---------------------------------------------------------------------------


def test_c2_lean_raise_solve_parity() -> None:
    """River-start subgame where one side faces a bet, exercising the lean
    raise primitive (3.0x of the bet faced) under both tiers."""
    _require_rust()
    config = HUNLConfig(
        starting_stack=2000,
        starting_street=Street.RIVER,
        initial_board=_RIVER_BOARD,
        # Asymmetric contributions => P0 faces a pending bet at the root, so the
        # raise branch is exercised from move one.
        initial_pot=900,
        initial_contributions=(300, 600),
        initial_hole_cards=_HOLES,
        river_bet_fractions=(0.33, 0.75, 1.50),
        raise_size_xs=(3.0,),
    )
    _solve_both(config, ITERATIONS, PER_ACTION_TOL, "c2_lean_raise")


def test_c2_two_size_raise_menu_solve_parity() -> None:
    """A two-entry raise menu {2.5x, 4.0x} fans out two raise slots identically."""
    _require_rust()
    config = HUNLConfig(
        starting_stack=3000,
        starting_street=Street.RIVER,
        initial_board=_RIVER_BOARD,
        initial_pot=600,
        initial_contributions=(200, 400),
        initial_hole_cards=_HOLES,
        river_bet_fractions=(0.33, 0.75),
        raise_size_xs=(2.5, 4.0),
    )
    _solve_both(config, ITERATIONS, PER_ACTION_TOL, "c2_two_size_raise")


# ---------------------------------------------------------------------------
# C3: flop-no-donk.
# ---------------------------------------------------------------------------


def test_c3_flop_no_donk_structural_python() -> None:
    """OOP's flop root exposes only CHECK; IP/turn/river opens are unaffected.

    Structural assertion on the Python tier (the rule lives in
    ``enumerate_legal_actions``; cross-tier parity is pinned by the Rust inline
    tests and the action-abstraction unit tests)."""
    config = HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.FLOP,
        initial_board=_FLOP_BOARD,
        initial_pot=200,
        initial_contributions=(100, 100),
        initial_hole_cards=_HOLES,
        flop_bet_fractions=(0.33, 0.75, 1.25),
        raise_size_xs=(3.0,),
    )
    game = HUNLPoker(config)
    root = game.initial_state()
    # P1 (OOP) is first-to-act postflop. Flop-no-donk => only CHECK.
    assert root.cur_player == 1
    assert game.legal_actions(root) == [ACTION_CHECK]

    # After OOP checks, IP (P0) may open the flop.
    after_check = game.apply(root, ACTION_CHECK)
    assert after_check.cur_player == 0
    ip_actions = game.legal_actions(after_check)
    assert any(a in _BET_IDS for a in ip_actions), ip_actions
    assert ACTION_ALL_IN in ip_actions


def test_c3_turn_oop_open_unaffected_python() -> None:
    """Turn-start OOP root keeps its opens (flop-no-donk is flop-only)."""
    config = HUNLConfig(
        starting_stack=600,
        starting_street=Street.TURN,
        initial_board=_TURN_BOARD,
        initial_pot=400,
        initial_contributions=(200, 200),
        initial_hole_cards=_HOLES,
        turn_bet_fractions=(0.33, 0.75, 1.50),
        raise_size_xs=(3.0,),
    )
    game = HUNLPoker(config)
    root = game.initial_state()
    assert root.cur_player == 1  # OOP first-to-act
    actions = game.legal_actions(root)
    assert any(a in _BET_IDS for a in actions), actions


@pytest.mark.slow
@pytest.mark.timeout(3600)
def test_c3_flop_no_donk_solve_parity() -> None:
    """Flop solve with per-street menus + lean raises + flop-no-donk matches
    across tiers on the tiny synthetic abstraction (slow)."""
    _require_rust()
    abstraction_ref = tiny_synthetic_abstraction_ref()
    base = flop_dry_3size_config(abstraction=abstraction_ref)
    # Layer the redesign config on top of the existing tiny-abstraction fixture.
    config = HUNLConfig(
        starting_stack=base.starting_stack,
        starting_street=base.starting_street,
        initial_board=base.initial_board,
        initial_pot=base.initial_pot,
        initial_contributions=base.initial_contributions,
        initial_hole_cards=base.initial_hole_cards,
        postflop_raise_cap=base.postflop_raise_cap,
        flop_bet_fractions=(0.33, 0.75, 1.25),
        turn_bet_fractions=(0.33, 0.75, 1.50),
        river_bet_fractions=(0.15, 0.33, 0.75, 1.50),
        raise_size_xs=(3.0,),
        abstraction=base.abstraction,
    )
    _solve_both(config, FLOP_ITERATIONS, FLOP_PER_ACTION_TOL, "c3_flop_no_donk")
