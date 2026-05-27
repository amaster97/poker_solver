"""Regression gate: minimal hand-computable Nash diff-test fixture.

Implements the 2-class (AA, KK) river fixture designed in
``docs/minimal_diff_test_fixture.md`` (2026-05-23/24 synthesis after the
v1.6.1 dry-run #2 22-42pp empirical divergence). The fixture is the
**shallowest possible** range-vs-range river spot whose Nash equilibrium
is hand-computable via dominance arguments:

  - Board ``7c 5d 3h Qs 2c`` (rainbow brick river; no pair, no flush).
  - Ranges ``{AA, KK}`` on both sides, uniform-weighted (6 combos per
    class per player, board-disjoint).
  - 2 BB starting pot, 3 BB remaining stack per side, bet size 0.5x pot
    (= 1 BB), ``postflop_raise_cap=1`` (no 3-bets possible).
  - P1 (BB seat) acts first on the river (per ``HUNLPoker._begin_street_*``
    convention for symmetric contributions, ``hunl.py:425-429``).

The hand-computed Nash has **12 strict-strategy slots** (must hold at any
correct equilibrium by pure-dominance) and **4 mixed-strategy slots**
(an indifference manifold for the AA bet-rate at no-bet-to-face nodes):

  STRICT:
    - Root P1, KK: bet=0, check=1 (KK underpair vs AA-only call range)
    - After-P1-check P0, KK: bet=0, check=1 (same dominance)
    - After-P1-bet P0, AA: call=1, fold=0 (AA dominates KK ≥ 13/14 equity)
    - After-P1-bet P0, KK: call=0, fold=1 (KK loses 100% vs AA call range)
    - After-P1-check-P0-bet P1, AA: call=1, fold=0
    - After-P1-check-P0-bet P1, KK: call=0, fold=1

  MIXED (indifference manifold; informative, not load-bearing):
    - Root P1, AA: bet=a_1 ∈ [0,1], check=1-a_1
    - After-P1-check P0, AA: bet=a_2 ∈ [0,1], check=1-a_2

This test acts as a **regression gate**: any future change that breaks
the basic Nash on this 2-class fixture indicates the solver kernel
(action menu, comparator, DCFR weighting, reach handling, or terminal
utility) is broken — not just deep-cap. Per the design doc, a passing
result here is consistent with the v1.6.1 "depth-related divergence"
hypothesis; a failing result narrows the bug to the shallow kernel.

Both code paths are exercised:
  - ``_rust.solve_range_vs_range_rust`` — the bedrock binding (PoC pattern
    matching ``test_range_vs_range_rust_diff.py``).
  - ``poker_solver.solve_range_vs_range_nash`` — the user-facing wrapper
    added in PR 43 (v1.7.0), which delegates to the same binding but adds
    per-class projection. Verifies the wrapper preserves correctness.

Tolerance: 0.02 absolute for strict slots (5000 iters; per design doc
§"Strict slots (must match within 2pp)"). Mixed slots are not asserted
beyond the implicit [0,1] range check.
"""

from __future__ import annotations

import importlib

import pytest

try:
    from poker_solver import (
        HUNLConfig,
        Street,
        parse_board,
        solve_range_vs_range_nash,
    )
    from poker_solver.card import Card, card_to_int, parse_card
    from poker_solver.hunl import _serialize_hunl_config
except Exception:  # noqa: BLE001
    HUNLConfig = None  # type: ignore[assignment,misc]
    Street = None  # type: ignore[assignment,misc]
    parse_board = None  # type: ignore[assignment]
    solve_range_vs_range_nash = None  # type: ignore[assignment]
    Card = None  # type: ignore[assignment,misc]
    card_to_int = None  # type: ignore[assignment]
    parse_card = None  # type: ignore[assignment]
    _serialize_hunl_config = None  # type: ignore[assignment]

try:
    _rust_module = importlib.import_module("poker_solver._rust")
    _rust_solve_rvr = getattr(_rust_module, "solve_range_vs_range_rust", None)
except Exception:  # noqa: BLE001
    _rust_module = None  # type: ignore[assignment]
    _rust_solve_rvr = None  # type: ignore[assignment]


pytestmark = [
    pytest.mark.skipif(
        HUNLConfig is None,
        reason="poker_solver HUNL surface not importable",
    ),
    pytest.mark.skipif(
        _rust_solve_rvr is None,
        reason=(
            "_rust.solve_range_vs_range_rust missing — rebuild via "
            "`maturin develop --release`"
        ),
    ),
]


# ---------------------------------------------------------------------------
# Fixture constants — kept module-level so the test functions stay short.
# ---------------------------------------------------------------------------

# Tolerance for strict slots. Design doc §"Strict slots (must match within
# 2pp)" sets 0.02; empirically converges much tighter at 5000 iters on
# this tiny fixture but we keep the doc's value for safety.
STRICT_TOL = 0.02

# Looser tolerance for mixed slots — they only need to be a valid
# probability AND consistent between paths.
MIXED_TOL = 0.05

ITERATIONS = 5000  # Per design doc; converges in <5s on this 2-class spot.
ALPHA, BETA, GAMMA = 1.5, 0.0, 2.0

BOARD_STR = "7c 5d 3h Qs 2c"

AA_COMBO_STRS = ["AcAd", "AcAh", "AcAs", "AdAh", "AdAs", "AhAs"]
KK_COMBO_STRS = ["KcKd", "KcKh", "KcKs", "KdKh", "KdKs", "KhKs"]


# ---------------------------------------------------------------------------
# Helpers — combo enumeration + key-suffix construction matching Rust.
# ---------------------------------------------------------------------------


def _combo_from_str(s: str) -> tuple[Card, Card]:
    """Parse a 4-char combo string like 'AcAd' to a (Card, Card) tuple."""
    return parse_card(s[:2]), parse_card(s[2:])


def _hole_ids_sorted(combo: tuple[Card, Card]) -> list[int]:
    """Sorted card-int pair for the Rust binding's p0_holes/p1_holes shape.

    Mirrors what ``test_range_vs_range_rust_diff.py::_hand_card_ids`` does
    (Rust's vector-form expects ``list[list[int, int]]`` with each inner
    list sorted ascending, matching ``crates/cfr_core/src/exploit.rs``
    ``hole_string``'s sort convention).
    """
    return sorted([card_to_int(combo[0]), card_to_int(combo[1])])


def _hole_string(combo: tuple[Card, Card]) -> str:
    """Render the 4-char ``<rank+suit><rank+suit>`` prefix Rust emits.

    Mirrors ``crates/cfr_core/src/exploit.rs::hole_string``: sort by
    card-int, then concat ``rank+suit`` chars. RANKS = "23456789TJQKA",
    SUITS = "shdc" (suit 0 = s, 1 = h, 2 = d, 3 = c).
    """
    ranks = "23456789TJQKA"
    suits = "shdc"
    ids = sorted([card_to_int(combo[0]), card_to_int(combo[1])])
    out = []
    for cid in ids:
        r = cid >> 2
        s = cid & 3
        out.append(f"{ranks[r - 2]}{suits[s]}")
    return "".join(out)


def _board_string(board: tuple[Card, ...]) -> str:
    """Sorted board string matching ``hunl._sorted_card_string``."""
    sorted_cards = sorted(board, key=lambda c: (c.rank, c.suit))
    return "".join(str(c) for c in sorted_cards)


def _build_config() -> HUNLConfig:
    """Build the minimal-diff fixture config per design doc §"Fixture spec"."""
    board = tuple(parse_board(BOARD_STR))
    return HUNLConfig(
        starting_stack=300,  # 3 BB remaining behind after pre-river contribs
        big_blind=100,
        small_blind=50,
        starting_street=Street.RIVER,
        initial_board=board,
        initial_pot=200,  # 2 BB pot at start of river
        initial_contributions=(100, 100),  # 1 BB each pre-river
        initial_hole_cards=(),  # vector-form enumerates via p0/p1_holes
        bet_size_fractions=(0.5,),  # 0.5 * pot = 100 chips = 1 BB bet
        include_all_in=False,
        postflop_raise_cap=1,  # blocks 3-bet entirely
    )


def _all_combos() -> tuple[list[tuple[Card, Card]], list[tuple[Card, Card]]]:
    """Return (aa_combos, kk_combos) as the 12 board-disjoint combos."""
    aa = [_combo_from_str(s) for s in AA_COMBO_STRS]
    kk = [_combo_from_str(s) for s in KK_COMBO_STRS]
    return aa, kk


def _ordered_holes() -> tuple[list[list[int]], list[list[int]]]:
    """Return (p0_holes, p1_holes) in the deterministic [AA..., KK...] order."""
    aa, kk = _all_combos()
    holes = [_hole_ids_sorted(c) for c in aa + kk]
    return list(holes), list(holes)


# ---------------------------------------------------------------------------
# Per-test infoset-key construction.
# ---------------------------------------------------------------------------


def _key_root_p1(combo: tuple[Card, Card]) -> str:
    """Infoset key at P1's root decision (no history yet)."""
    board = tuple(parse_board(BOARD_STR))
    return f"{_hole_string(combo)}|{_board_string(board)}|r|"


def _key_after_p1_check_p0(combo: tuple[Card, Card]) -> str:
    """Infoset key at P0's decision after P1 checked (token 'x')."""
    board = tuple(parse_board(BOARD_STR))
    return f"{_hole_string(combo)}|{_board_string(board)}|r|x"


def _key_after_p1_bet_p0(combo: tuple[Card, Card]) -> str:
    """Infoset key at P0's facing-bet decision (P1 bet 100 chips, token 'b100')."""
    board = tuple(parse_board(BOARD_STR))
    return f"{_hole_string(combo)}|{_board_string(board)}|r|b100"


def _key_after_p1_check_p0_bet_p1(combo: tuple[Card, Card]) -> str:
    """Infoset key at P1's facing-bet decision (P1 checked, P0 bet 100)."""
    board = tuple(parse_board(BOARD_STR))
    return f"{_hole_string(combo)}|{_board_string(board)}|r|xb100"


# ---------------------------------------------------------------------------
# Solver invocation — cached as session-scoped fixtures so the 5000-iter
# solve runs ONCE for all 12+ test functions in this file.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def rust_direct_strategy() -> dict[str, list[float]]:
    """Average strategy from the direct ``_rust.solve_range_vs_range_rust`` call."""
    config = _build_config()
    config_json = _serialize_hunl_config(config)
    p0_holes, p1_holes = _ordered_holes()
    rs_result = _rust_solve_rvr(
        config_json,
        ITERATIONS,
        ALPHA,
        BETA,
        GAMMA,
        p0_holes,
        p1_holes,
    )
    return dict(rs_result["average_strategy"])


@pytest.fixture(scope="module")
def wrapper_strategy() -> dict[str, list[float]]:
    """Average strategy from the user-facing ``solve_range_vs_range_nash`` wrapper.

    The wrapper delegates to the same Rust binding but adds per-class
    projection; verifying its ``per_history_strategy`` agrees with the
    direct call confirms the wrapper preserves correctness.
    """
    config = _build_config()
    result = solve_range_vs_range_nash(
        config_template=config,
        hero_range=["AA", "KK"],
        villain_range=["AA", "KK"],
        iterations=ITERATIONS,
        alpha=ALPHA,
        beta=BETA,
        gamma=GAMMA,
        hero_player=1,  # P1 acts first on river (symmetric contribs)
        compute_exploitability_at_end=False,
    )
    return dict(result.per_history_strategy)


# ---------------------------------------------------------------------------
# Action-index helpers.
#
# Per `action_abstraction.py`:
#   - Not-facing-bet (root, after-check): actions sorted are
#     [ACTION_CHECK=1, ACTION_BET_33=3]. So index 0 = CHECK, index 1 = BET.
#   - Facing-bet (after b100 or xb100): actions sorted are
#     [ACTION_FOLD=0, ACTION_CALL=2]. So index 0 = FOLD, index 1 = CALL.
# ---------------------------------------------------------------------------

IDX_CHECK = 0  # in [CHECK, BET]
IDX_BET = 1
IDX_FOLD = 0  # in [FOLD, CALL]
IDX_CALL = 1


def _average_freq(
    strategy: dict[str, list[float]],
    combos: list[tuple[Card, Card]],
    key_builder,
    action_idx: int,
) -> float:
    """Average action-index probability across `combos` at the given infoset."""
    total = 0.0
    count = 0
    for combo in combos:
        key = key_builder(combo)
        row = strategy.get(key)
        if row is None:
            continue
        if action_idx >= len(row):
            continue
        total += float(row[action_idx])
        count += 1
    if count == 0:
        pytest.fail(
            f"no rows found in strategy for combos at key sample {key!r}; "
            f"strategy has {len(strategy)} entries. "
            f"First few keys: {list(strategy.keys())[:5]}"
        )
    return total / count


# ---------------------------------------------------------------------------
# Coverage smoke test — verifies both paths emit overlapping infoset keys
# in the expected lossless format. Helps localize "key drift" failures
# before the per-slot tests fire.
# ---------------------------------------------------------------------------


def test_solver_emits_expected_root_keys(rust_direct_strategy):
    """The Rust path should produce P1-root infoset keys for every AA/KK combo."""
    aa, kk = _all_combos()
    missing = []
    for combo in aa + kk:
        key = _key_root_p1(combo)
        if key not in rust_direct_strategy:
            missing.append(key)
    if missing:
        sample_keys = list(rust_direct_strategy.keys())[:6]
        pytest.fail(
            f"{len(missing)} root P1 infoset keys missing from "
            f"rust_direct_strategy. First missing: {missing[0]!r}. "
            f"Sample of available keys: {sample_keys}"
        )


def test_wrapper_strategy_matches_direct(rust_direct_strategy, wrapper_strategy):
    """Wrapper's per_history_strategy must match direct call exactly.

    Both call the same Rust binding with the same args; the wrapper just
    repackages the dict. Any divergence indicates a wrapper bug (input
    permutation, key rewriting, or extra processing).
    """
    # Keys should be identical sets.
    direct_keys = set(rust_direct_strategy.keys())
    wrapper_keys = set(wrapper_strategy.keys())
    only_direct = direct_keys - wrapper_keys
    only_wrapper = wrapper_keys - direct_keys
    assert not only_direct, (
        f"{len(only_direct)} keys in direct but not wrapper: "
        f"{list(only_direct)[:3]}"
    )
    assert not only_wrapper, (
        f"{len(only_wrapper)} keys in wrapper but not direct: "
        f"{list(only_wrapper)[:3]}"
    )
    # Spot-check a few rows for value-equality (both paths are
    # deterministic given the same iters/alpha/beta/gamma).
    aa, _ = _all_combos()
    sample_combo = aa[0]
    sample_key = _key_root_p1(sample_combo)
    direct_row = rust_direct_strategy[sample_key]
    wrapper_row = wrapper_strategy[sample_key]
    assert len(direct_row) == len(wrapper_row), (
        f"row length mismatch at {sample_key!r}: "
        f"direct={direct_row}, wrapper={wrapper_row}"
    )
    for i, (a, b) in enumerate(zip(direct_row, wrapper_row)):
        assert abs(a - b) < 1e-9, (
            f"row[{i}] mismatch at {sample_key!r}: direct={a}, wrapper={b}"
        )


# ===========================================================================
# STRICT SLOTS — must hold within STRICT_TOL on both code paths.
# Direct Rust call is the bedrock; the wrapper is verified separately
# above to match the direct path, so per-slot assertions only need to run
# against rust_direct_strategy.
# ===========================================================================


# ---- Slot 1: Root P1, KK -> bet = 0 (strict) -------------------------------


def test_strict_root_p1_kk_bet_zero(rust_direct_strategy):
    """KK at root P1 must STRICT-check (bet freq = 0).

    Dominance argument: opponent's calling range with KK is AA-only (KK
    strict-folds facing bet); KK loses 100% vs AA. EV(bet KK) = 2 - 3f
    where f = 6/7 = AA-only call frequency, giving EV(bet) ≈ -0.57 BB
    while EV(check KK) ≈ +0.14 BB. STRICT CHECK.
    """
    _, kk = _all_combos()
    freq_bet = _average_freq(rust_direct_strategy, kk, _key_root_p1, IDX_BET)
    assert freq_bet < STRICT_TOL, (
        f"KK at root P1 should STRICT-check (bet=0); got bet_freq={freq_bet:.4f} "
        f"(tolerance {STRICT_TOL})"
    )


# ---- Slot 2: Root P1, KK -> check = 1 (strict, complement of Slot 1) -------


def test_strict_root_p1_kk_check_one(rust_direct_strategy):
    """KK at root P1 must STRICT-check (check freq = 1, complement of Slot 1)."""
    _, kk = _all_combos()
    freq_check = _average_freq(rust_direct_strategy, kk, _key_root_p1, IDX_CHECK)
    assert freq_check > 1.0 - STRICT_TOL, (
        f"KK at root P1 should STRICT-check (check=1); got check_freq={freq_check:.4f} "
        f"(tolerance {STRICT_TOL})"
    )


# ---- Slot 3: After-P1-check P0, KK -> bet = 0 (strict) ---------------------


def test_strict_after_check_p0_kk_bet_zero(rust_direct_strategy):
    """KK at after-P1-check P0 must STRICT-check (bet=0). Same dominance as Slot 1."""
    _, kk = _all_combos()
    freq_bet = _average_freq(
        rust_direct_strategy, kk, _key_after_p1_check_p0, IDX_BET
    )
    assert freq_bet < STRICT_TOL, (
        f"KK at after-P1-check P0 should STRICT-check (bet=0); "
        f"got bet_freq={freq_bet:.4f} (tolerance {STRICT_TOL})"
    )


# ---- Slot 4: After-P1-check P0, KK -> check = 1 (strict, complement) -------


def test_strict_after_check_p0_kk_check_one(rust_direct_strategy):
    """KK at after-P1-check P0 must STRICT-check (check=1; complement of Slot 3)."""
    _, kk = _all_combos()
    freq_check = _average_freq(
        rust_direct_strategy, kk, _key_after_p1_check_p0, IDX_CHECK
    )
    assert freq_check > 1.0 - STRICT_TOL, (
        f"KK at after-P1-check P0 should STRICT-check (check=1); "
        f"got check_freq={freq_check:.4f} (tolerance {STRICT_TOL})"
    )


# ---- Slot 5: After-P1-bet P0, AA -> call = 1 (strict) ----------------------


def test_strict_facing_p1_bet_p0_aa_call_one(rust_direct_strategy):
    """AA facing P1's bet must STRICT-call (call=1).

    AA dominates KK and chops AA; equity vs opponent's bet range is
    ≥ 13/14. Pot odds require only 25%. STRICT CALL.
    """
    aa, _ = _all_combos()
    freq_call = _average_freq(
        rust_direct_strategy, aa, _key_after_p1_bet_p0, IDX_CALL
    )
    assert freq_call > 1.0 - STRICT_TOL, (
        f"AA facing P1's bet should STRICT-call (call=1); "
        f"got call_freq={freq_call:.4f} (tolerance {STRICT_TOL})"
    )


# ---- Slot 6: After-P1-bet P0, AA -> fold = 0 (strict, complement) ----------


def test_strict_facing_p1_bet_p0_aa_fold_zero(rust_direct_strategy):
    """AA facing P1's bet must STRICT-call (fold=0; complement of Slot 5)."""
    aa, _ = _all_combos()
    freq_fold = _average_freq(
        rust_direct_strategy, aa, _key_after_p1_bet_p0, IDX_FOLD
    )
    assert freq_fold < STRICT_TOL, (
        f"AA facing P1's bet should STRICT-call (fold=0); "
        f"got fold_freq={freq_fold:.4f} (tolerance {STRICT_TOL})"
    )


# ---- Slot 7: After-P1-bet P0, KK -> call = 0 (strict) ----------------------


def test_strict_facing_p1_bet_p0_kk_call_zero(rust_direct_strategy):
    """KK facing P1's bet must STRICT-fold (call=0).

    Opponent's betting range at the symmetric Nash is value-heavy (AA
    plus at most small KK bluffs). KK loses to AA, chops KK. EV(call KK)
    ≈ -1 BB; EV(fold) = 0. STRICT FOLD.
    """
    _, kk = _all_combos()
    freq_call = _average_freq(
        rust_direct_strategy, kk, _key_after_p1_bet_p0, IDX_CALL
    )
    assert freq_call < STRICT_TOL, (
        f"KK facing P1's bet should STRICT-fold (call=0); "
        f"got call_freq={freq_call:.4f} (tolerance {STRICT_TOL})"
    )


# ---- Slot 8: After-P1-bet P0, KK -> fold = 1 (strict, complement) ----------


def test_strict_facing_p1_bet_p0_kk_fold_one(rust_direct_strategy):
    """KK facing P1's bet must STRICT-fold (fold=1; complement of Slot 7)."""
    _, kk = _all_combos()
    freq_fold = _average_freq(
        rust_direct_strategy, kk, _key_after_p1_bet_p0, IDX_FOLD
    )
    assert freq_fold > 1.0 - STRICT_TOL, (
        f"KK facing P1's bet should STRICT-fold (fold=1); "
        f"got fold_freq={freq_fold:.4f} (tolerance {STRICT_TOL})"
    )


# ---- Slot 9: After-P1-check-P0-bet P1, AA -> call = 1 (strict) -------------


def test_strict_facing_p0_bet_after_check_p1_aa_call_one(rust_direct_strategy):
    """AA at P1 facing-bet after P1 checked + P0 bet must STRICT-call (call=1)."""
    aa, _ = _all_combos()
    freq_call = _average_freq(
        rust_direct_strategy, aa, _key_after_p1_check_p0_bet_p1, IDX_CALL
    )
    assert freq_call > 1.0 - STRICT_TOL, (
        f"AA at P1-facing-bet (after-check) should STRICT-call (call=1); "
        f"got call_freq={freq_call:.4f} (tolerance {STRICT_TOL})"
    )


# ---- Slot 10: After-P1-check-P0-bet P1, AA -> fold = 0 (strict, complement)


def test_strict_facing_p0_bet_after_check_p1_aa_fold_zero(rust_direct_strategy):
    """AA at P1 facing-bet after-check must STRICT-call (fold=0; complement of Slot 9)."""
    aa, _ = _all_combos()
    freq_fold = _average_freq(
        rust_direct_strategy, aa, _key_after_p1_check_p0_bet_p1, IDX_FOLD
    )
    assert freq_fold < STRICT_TOL, (
        f"AA at P1-facing-bet (after-check) should STRICT-call (fold=0); "
        f"got fold_freq={freq_fold:.4f} (tolerance {STRICT_TOL})"
    )


# ---- Slot 11: After-P1-check-P0-bet P1, KK -> call = 0 (strict) ------------


def test_strict_facing_p0_bet_after_check_p1_kk_call_zero(rust_direct_strategy):
    """KK at P1 facing-bet after-check must STRICT-fold (call=0)."""
    _, kk = _all_combos()
    freq_call = _average_freq(
        rust_direct_strategy, kk, _key_after_p1_check_p0_bet_p1, IDX_CALL
    )
    assert freq_call < STRICT_TOL, (
        f"KK at P1-facing-bet (after-check) should STRICT-fold (call=0); "
        f"got call_freq={freq_call:.4f} (tolerance {STRICT_TOL})"
    )


# ---- Slot 12: After-P1-check-P0-bet P1, KK -> fold = 1 (strict, complement)


def test_strict_facing_p0_bet_after_check_p1_kk_fold_one(rust_direct_strategy):
    """KK at P1 facing-bet after-check must STRICT-fold (fold=1; complement of Slot 11)."""
    _, kk = _all_combos()
    freq_fold = _average_freq(
        rust_direct_strategy, kk, _key_after_p1_check_p0_bet_p1, IDX_FOLD
    )
    assert freq_fold > 1.0 - STRICT_TOL, (
        f"KK at P1-facing-bet (after-check) should STRICT-fold (fold=1); "
        f"got fold_freq={freq_fold:.4f} (tolerance {STRICT_TOL})"
    )


# ===========================================================================
# MIXED SLOTS — informative, not load-bearing. We assert only that the
# values are valid probabilities in [0, 1] and that the BET + CHECK
# (or CALL + FOLD) frequencies sum to ~1.0 within MIXED_TOL. The exact
# mixing rate sits on a 1-dim indifference manifold per the design doc.
# ===========================================================================


# ---- Mixed Slot A: Root P1, AA -> (bet=a_1, check=1-a_1) -------------------


def test_mixed_root_p1_aa_in_unit_interval(rust_direct_strategy):
    """AA at root P1 sits on the indifference manifold: bet + check ≈ 1."""
    aa, _ = _all_combos()
    freq_bet = _average_freq(rust_direct_strategy, aa, _key_root_p1, IDX_BET)
    freq_check = _average_freq(rust_direct_strategy, aa, _key_root_p1, IDX_CHECK)
    assert 0.0 - MIXED_TOL <= freq_bet <= 1.0 + MIXED_TOL, (
        f"AA bet freq at root P1 outside [0,1]: {freq_bet:.4f}"
    )
    assert 0.0 - MIXED_TOL <= freq_check <= 1.0 + MIXED_TOL, (
        f"AA check freq at root P1 outside [0,1]: {freq_check:.4f}"
    )
    assert abs((freq_bet + freq_check) - 1.0) < MIXED_TOL, (
        f"AA at root P1: bet({freq_bet:.4f}) + check({freq_check:.4f}) != 1.0 "
        f"(tolerance {MIXED_TOL})"
    )


# ---- Mixed Slot B: After-P1-check P0, AA -> (bet=a_2, check=1-a_2) ---------


def test_mixed_after_check_p0_aa_in_unit_interval(rust_direct_strategy):
    """AA at after-P1-check P0 sits on the indifference manifold: bet + check ≈ 1."""
    aa, _ = _all_combos()
    freq_bet = _average_freq(
        rust_direct_strategy, aa, _key_after_p1_check_p0, IDX_BET
    )
    freq_check = _average_freq(
        rust_direct_strategy, aa, _key_after_p1_check_p0, IDX_CHECK
    )
    assert 0.0 - MIXED_TOL <= freq_bet <= 1.0 + MIXED_TOL, (
        f"AA bet freq at after-check P0 outside [0,1]: {freq_bet:.4f}"
    )
    assert 0.0 - MIXED_TOL <= freq_check <= 1.0 + MIXED_TOL, (
        f"AA check freq at after-check P0 outside [0,1]: {freq_check:.4f}"
    )
    assert abs((freq_bet + freq_check) - 1.0) < MIXED_TOL, (
        f"AA at after-check P0: bet({freq_bet:.4f}) + check({freq_check:.4f}) "
        f"!= 1.0 (tolerance {MIXED_TOL})"
    )


# ===========================================================================
# Wrapper-level sanity: a single strict-slot replay against the wrapper
# strategy confirms the wrapper is wired correctly. The detailed per-slot
# tests above all use rust_direct_strategy; this single replay is a
# minimum-cost smoke for the wrapper's strict-slot correctness.
# ===========================================================================


def test_wrapper_strict_kk_fold_facing_bet(wrapper_strategy):
    """Smoke: KK facing P1's bet via the wrapper must STRICT-fold (fold=1)."""
    _, kk = _all_combos()
    freq_fold = _average_freq(
        wrapper_strategy, kk, _key_after_p1_bet_p0, IDX_FOLD
    )
    assert freq_fold > 1.0 - STRICT_TOL, (
        f"WRAPPER: KK facing P1's bet should STRICT-fold (fold=1); "
        f"got fold_freq={freq_fold:.4f} (tolerance {STRICT_TOL}) — "
        f"divergence from direct path indicates a wrapper-side bug"
    )
