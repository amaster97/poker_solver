"""HUNL Python <-> Rust differential tests (PR 6).

Verifies that the Rust port (Agents A + B) produces strategies, infoset keys,
and bucket lookups byte-or-strategy-equivalent to the Python tier (PR 5).
Tolerance: 1e-3 per-action on the river-only subgame, 5e-3 on the flop fixture
(locked per consistency-review I3 + PR 6 spec sec 7.3).

The spec is the source of truth. If a test surfaces a genuine spec ambiguity,
flag the orchestrator; do NOT silently tweak the tolerance.

Defensive imports: until Agent B has landed ``_rust.solve_hunl_postflop`` +
the Python-side ``_solve_rust`` HUNL branch, every test skips gracefully.
"""

from __future__ import annotations

import importlib
import math
from typing import Any

import pytest

# Cross-PR public surface (PR 3 + PR 5).
from poker_solver import (
    ACTION_ALL_IN,
    ACTION_BET_33,
    ACTION_BET_75,
    ACTION_BET_100,
    ACTION_BET_150,
    ACTION_BET_200,
    ACTION_CALL,
    ACTION_CHECK,
    ACTION_FOLD,
    ACTION_RAISE_33,
    ACTION_RAISE_75,
    ACTION_RAISE_100,
    ACTION_RAISE_150,
    ACTION_RAISE_200,
    Card,
    HUNLConfig,
    HUNLPoker,
    Street,
    default_tiny_subgame,
    solve,
)
from tests.fixtures.hunl_solve_fixtures import (
    flop_dry_3size_config,
    river_subgame_config,
    tiny_synthetic_abstraction_ref,
)

# Rust PR 6 surface — Agent B exposes this. Post PR 6 merge the symbol must be
# present; any ImportError on ``poker_solver._rust`` itself indicates a stale
# `.so` from a prior architecture (x86_64 binary on arm64 host or vice versa)
# and should halt collection LOUDLY rather than silently skipping the diff
# tests. A missing ``solve_hunl_postflop`` attribute (module imports cleanly
# but the symbol is absent — only possible during in-flight Rust development)
# still falls back to the per-test skip path, but the module-level import
# failure is now a hard error per PR 6 audit followup triage §3 / PR 6.5.
_rust_solve_hunl: Any = None
try:
    _rust_module = importlib.import_module("poker_solver._rust")
    _rust_solve_hunl = getattr(_rust_module, "solve_hunl_postflop", None)
except ImportError as exc:
    raise RuntimeError(
        f"_rust extension required for HUNL diff tests but failed to import: "
        f"{exc!r}. Rebuild via `maturin develop --release` from the project "
        f"root; common cause is a stale `.so` from a prior architecture "
        f"(x86_64 binary on arm64 host or vice versa)."
    ) from exc


# ---------------------------------------------------------------------------
# Tolerances (PR 6 spec sec 7.3 + consistency review I3). LOCKED.
# ---------------------------------------------------------------------------
# 1e-3 (river): the floor under which strategy behavior is poker-indistinguishable.
# 5e-3 (flop tiny abstraction): looser because chance branching x float-order
# interacts more.
RIVER_PER_ACTION_TOL: float = 1e-3
FLOP_PER_ACTION_TOL: float = 5e-3
ABS_FLOOR: float = 1e-6  # avoids divide-by-zero on tiny probabilities

RIVER_ITERATIONS: int = 1000
FLOP_ITERATIONS: int = 200

EXPLOIT_RECOMPUTE_TOL: float = 1e-2  # spec sec 8.3 deliverable 7

# DCFR hyperparameters (PLAN.md lock).
DCFR_KWARGS: dict[str, Any] = {"alpha": 1.5, "beta": 0.0, "gamma": 2.0}


# ---------------------------------------------------------------------------
# Skip helpers — every test gates on the cross-tier surface being installed.
# ---------------------------------------------------------------------------

_BASE_SKIP_REASON = (
    "PR 6 Rust HUNL surface not installed yet (Agent B's "
    "poker_solver._rust.solve_hunl_postflop + Python _solve_rust HUNL branch)."
)


def _require_rust_hunl_surface() -> None:
    """Skip the current test if the PR 6 Rust HUNL surface is missing."""
    if _rust_solve_hunl is None:
        pytest.skip(_BASE_SKIP_REASON)


def _check_strategy_diff(
    py_strategy: dict[str, list[float]],
    rs_strategy: dict[str, list[float]],
    tol: float,
    *,
    label: str,
) -> tuple[float, list[str]]:
    """Compare per-infoset-per-action probabilities.

    Returns (max_observed_abs_diff, list_of_divergence_messages). Empty list
    means the diff is within ``tol``.
    """
    py_keys = set(py_strategy.keys())
    rs_keys = set(rs_strategy.keys())
    diffs: list[str] = []
    if py_keys != rs_keys:
        only_py = sorted(py_keys - rs_keys)[:10]
        only_rs = sorted(rs_keys - py_keys)[:10]
        diffs.append(
            f"[{label}] infoset key sets diverge; "
            f"only in Python (first 10): {only_py}; "
            f"only in Rust (first 10): {only_rs}"
        )
        return float("inf"), diffs
    max_abs_diff = 0.0
    for key in sorted(py_keys):
        py_probs = py_strategy[key]
        rs_probs = rs_strategy[key]
        if len(py_probs) != len(rs_probs):
            diffs.append(
                f"[{label}] {key}: action vector length differs "
                f"(py={len(py_probs)} rs={len(rs_probs)})"
            )
            continue
        for i, (p, r) in enumerate(zip(py_probs, rs_probs)):
            abs_diff = abs(p - r)
            max_abs_diff = max(max_abs_diff, abs_diff)
            local_tol = max(ABS_FLOOR, tol * max(abs(p), abs(r), ABS_FLOOR))
            if abs_diff > local_tol:
                diffs.append(
                    f"[{label}] {key}[{i}]: py={p:.6f} rs={r:.6f} "
                    f"|diff|={abs_diff:.3e} tol={local_tol:.3e}"
                )
    return max_abs_diff, diffs


# ---------------------------------------------------------------------------
# Test 1 (PR 6 spec sec 8.3 #1): river-only subgame, no abstraction.
# ---------------------------------------------------------------------------


def test_hunl_river_subgame_diff_python_vs_rust() -> None:
    """River-only subgame: AhKc vs QdQh on As7c2dKh5s, SPR 1, full menu.

    1000 iterations on both tiers; per-infoset-per-action diff <= 1e-3
    (with abs floor 1e-6). See PR 6 spec sec 7.1 Test 1.
    """
    _require_rust_hunl_surface()
    config = river_subgame_config()
    game = HUNLPoker(config)
    py_result = solve(
        game,
        iterations=RIVER_ITERATIONS,
        backend="python",
        seed=42,
        **DCFR_KWARGS,
    )
    rs_result = solve(
        game,
        iterations=RIVER_ITERATIONS,
        backend="rust",
        seed=42,
        **DCFR_KWARGS,
    )
    assert py_result.average_strategy, "Python solve returned empty strategy"
    assert rs_result.average_strategy, "Rust solve returned empty strategy"

    max_abs, diffs = _check_strategy_diff(
        py_result.average_strategy,
        rs_result.average_strategy,
        tol=RIVER_PER_ACTION_TOL,
        label="river_subgame",
    )
    assert not diffs, (
        "Python <-> Rust strategy diverges beyond 1e-3 tolerance on the "
        "river-only subgame.\nMax abs per-action diff observed: "
        f"{max_abs:.3e}.\nFirst 10 divergences:\n" + "\n".join(diffs[:10])
    )


# ---------------------------------------------------------------------------
# Test 2 (PR 6 spec sec 8.3 #2): flop dry, 3 bet sizes, tiny abstraction.
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.timeout(3600)
def test_hunl_flop_dry_3size_diff_python_vs_rust_tiny_abstraction() -> None:
    """Flop dry As7c2d, 100 BB, 3 bet sizes [33%, 75%, 200%], 3-cap.

    PR 4's ``tiny_synthetic_abstraction()`` with bucket_counts=(4, 2, 2).
    200 iterations; per-infoset-per-action diff <= 5e-3.
    Marked slow: ~5 min Python tier, ~30 s Rust tier. See PR 6 spec sec 7.1 Test 2.
    """
    _require_rust_hunl_surface()
    abstraction_ref = tiny_synthetic_abstraction_ref()
    config = flop_dry_3size_config(abstraction=abstraction_ref)
    game = HUNLPoker(config)
    py_result = solve(
        game,
        iterations=FLOP_ITERATIONS,
        backend="python",
        seed=42,
        **DCFR_KWARGS,
    )
    rs_result = solve(
        game,
        iterations=FLOP_ITERATIONS,
        backend="rust",
        seed=42,
        **DCFR_KWARGS,
    )
    assert py_result.average_strategy, "Python solve returned empty strategy"
    assert rs_result.average_strategy, "Rust solve returned empty strategy"

    max_abs, diffs = _check_strategy_diff(
        py_result.average_strategy,
        rs_result.average_strategy,
        tol=FLOP_PER_ACTION_TOL,
        label="flop_dry_3size",
    )
    assert not diffs, (
        "Python <-> Rust strategy diverges beyond 5e-3 tolerance on the "
        "tiny-abstraction flop fixture.\nMax abs per-action diff observed: "
        f"{max_abs:.3e}.\nFirst 10 divergences:\n" + "\n".join(diffs[:10])
    )


# ---------------------------------------------------------------------------
# Test 3 (PR 6 spec sec 8.3 #3): Rust rejects preflop configs.
# ---------------------------------------------------------------------------


def test_hunl_rust_validates_postflop_only() -> None:
    """Passing a preflop config to backend='rust' raises ``NotImplementedError``.

    Mirrors PR 5's Python-tier behavior (preflop is PR 9). The Rust binding
    explicitly returns NotImplementedError with PR 9 in the message.
    """
    _require_rust_hunl_surface()
    # Default HUNLConfig() is preflop (Street.PREFLOP, 100 BB stacks, no
    # initial board) - the canonical "no subgame" config.
    config = HUNLConfig()
    game = HUNLPoker(config)
    # Note: 100 BB stacks => is_pushfold_mode is False so push/fold short-
    # circuit does NOT fire; the dispatch falls through to backend="rust".
    with pytest.raises(NotImplementedError, match=r"(?i)pr ?9|preflop"):
        solve(game, iterations=10, backend="rust", **DCFR_KWARGS)


# ---------------------------------------------------------------------------
# Test 4 (PR 6 spec sec 8.3 #4): board length validation.
# ---------------------------------------------------------------------------


def test_hunl_rust_validates_board_length() -> None:
    """Mismatched initial_board length raises a clear error.

    A 4-card board with ``starting_street=Street.FLOP`` (which expects 3
    cards) must trip either Python's pre-validation in
    ``solve_hunl_postflop`` or, if the Rust path is reached, the Rust
    loader's input-validation step.
    """
    _require_rust_hunl_surface()
    # 4 cards with FLOP-start: HUNLConfig.__post_init__ accepts this (it
    # only checks initial_board non-empty); the postflop solver should
    # raise on the length mismatch.
    board_4 = (
        Card.from_str("As"),
        Card.from_str("7c"),
        Card.from_str("2d"),
        Card.from_str("Kh"),
    )
    hole = (
        (Card.from_str("Ah"), Card.from_str("Kh")),
        (Card.from_str("Qd"), Card.from_str("Jd")),
    )
    config = HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.FLOP,
        initial_board=board_4,
        initial_pot=200,
        initial_contributions=(0, 0),
        initial_hole_cards=hole,
    )
    game = HUNLPoker(config)
    with pytest.raises((ValueError, RuntimeError), match=r"(?i)board"):
        solve(game, iterations=10, backend="rust", **DCFR_KWARGS)


# ---------------------------------------------------------------------------
# Test 5 (PR 6 spec sec 8.3 #5): strategy probabilities sum to 1.
# ---------------------------------------------------------------------------


def test_hunl_rust_strategy_sums_to_one() -> None:
    """Every infoset's Rust-returned probs sum to 1.0 +/- 1e-9.

    Also confirms all probs are in [0, 1] and finite (no NaN/inf).
    """
    _require_rust_hunl_surface()
    config = default_tiny_subgame()
    game = HUNLPoker(config)
    result = solve(game, iterations=100, backend="rust", seed=42, **DCFR_KWARGS)
    assert result.average_strategy, "Rust solve returned empty strategy"
    for key, probs in result.average_strategy.items():
        # Sum ~ 1.0
        assert abs(sum(probs) - 1.0) < 1e-9, f"{key}: probs={probs} sum={sum(probs)}"
        # Range
        assert all(
            0.0 <= p <= 1.0 for p in probs
        ), f"{key}: probs out of [0,1] range: {probs}"
        # Finite
        assert not any(
            math.isnan(p) or math.isinf(p) for p in probs
        ), f"{key}: probs contain NaN or inf: {probs}"


# ---------------------------------------------------------------------------
# Test 6 (PR 6 spec sec 8.3 #6): determinism with seed.
# ---------------------------------------------------------------------------


def test_hunl_rust_deterministic_with_seed() -> None:
    """Same seed + config + abstraction -> byte-identical strategy.

    Tests Agent B's ``seed`` parameter passes through and Agent B's HashMap
    hasher is locked under ``#[cfg(test)]`` (D8 lock).
    """
    _require_rust_hunl_surface()
    config = default_tiny_subgame()
    game = HUNLPoker(config)
    r1 = solve(game, iterations=100, backend="rust", seed=42, **DCFR_KWARGS)
    r2 = solve(game, iterations=100, backend="rust", seed=42, **DCFR_KWARGS)
    assert (
        r1.average_strategy.keys() == r2.average_strategy.keys()
    ), "Rust strategy keys not deterministic"
    for key in r1.average_strategy:
        a = r1.average_strategy[key]
        b = r2.average_strategy[key]
        assert a == b, f"nondeterminism at infoset {key}: r1={a} r2={b}"


# ---------------------------------------------------------------------------
# Test 7 (PR 6 spec sec 8.3 #7): exploitability matches Python recompute.
# ---------------------------------------------------------------------------


def test_hunl_rust_exploitability_matches_python_recompute() -> None:
    """Python recomputes exploitability from the Rust strategy (D5 lock).

    Per PR 6 spec sec 6.1, Python recomputes exploitability + game_value via
    ``exploitability(game, rust_strategy)`` after Rust returns the
    strategy. The recomputed value should match
    ``solve(backend='python')``'s exploitability within ``1e-2`` after
    1000 iterations on the river subgame.
    """
    _require_rust_hunl_surface()
    config = river_subgame_config()
    game = HUNLPoker(config)
    py = solve(
        game,
        iterations=RIVER_ITERATIONS,
        backend="python",
        seed=42,
        **DCFR_KWARGS,
    )
    rs = solve(
        game,
        iterations=RIVER_ITERATIONS,
        backend="rust",
        seed=42,
        **DCFR_KWARGS,
    )
    assert (
        rs.exploitability_history
    ), "Rust path should populate exploitability_history (Python recompute)"
    rs_exp = rs.exploitability_history[-1]
    py_exp = py.exploitability_history[-1]
    assert rs_exp >= 0.0, f"exploitability must be non-negative, got {rs_exp}"
    assert math.isfinite(rs_exp), f"exploitability must be finite, got {rs_exp}"
    assert abs(rs_exp - py_exp) <= EXPLOIT_RECOMPUTE_TOL, (
        f"Rust-strategy exploitability ({rs_exp:.6f}) diverges from Python's "
        f"({py_exp:.6f}) by more than {EXPLOIT_RECOMPUTE_TOL}."
    )


# ---------------------------------------------------------------------------
# Test 8 (PR 6 spec sec 8.3 #8): action ID constants match Python.
# ---------------------------------------------------------------------------


def test_hunl_rust_action_ids_match_python_constants() -> None:
    """Rust ``ACTION_FOLD..ACTION_ALL_IN`` integer constants match Python.

    The Rust constants are not directly exposed via PyO3 in PR 6; we verify
    by indirect means: the infoset_key betting_history token formatted by
    the Rust solver embeds action IDs through ``apply()`` + history
    bookkeeping. If the Rust key set matches Python's (Test 1) AND the
    betting-history tokens line up, the action IDs round-trip correctly.

    This test additionally documents the canonical Python action ID table
    so any drift between PR 3's constants and PR 6's Rust mirror is
    surfaced loudly here, not silently downstream in Test 1.
    """
    _require_rust_hunl_surface()
    # Document the canonical Python action IDs. The Rust mirror in
    # hunl.rs must match these values exactly (PR 6 spec sec 4.1 +
    # critical-correctness item sec 9 #15).
    expected = {
        "ACTION_FOLD": 0,
        "ACTION_CHECK": 1,
        "ACTION_CALL": 2,
        "ACTION_BET_33": 3,
        "ACTION_BET_75": 4,
        "ACTION_BET_100": 5,
        "ACTION_BET_150": 6,
        "ACTION_BET_200": 7,
        "ACTION_RAISE_33": 8,
        "ACTION_RAISE_75": 9,
        "ACTION_RAISE_100": 10,
        "ACTION_RAISE_150": 11,
        "ACTION_RAISE_200": 12,
        "ACTION_ALL_IN": 13,
    }
    actual = {
        "ACTION_FOLD": ACTION_FOLD,
        "ACTION_CHECK": ACTION_CHECK,
        "ACTION_CALL": ACTION_CALL,
        "ACTION_BET_33": ACTION_BET_33,
        "ACTION_BET_75": ACTION_BET_75,
        "ACTION_BET_100": ACTION_BET_100,
        "ACTION_BET_150": ACTION_BET_150,
        "ACTION_BET_200": ACTION_BET_200,
        "ACTION_RAISE_33": ACTION_RAISE_33,
        "ACTION_RAISE_75": ACTION_RAISE_75,
        "ACTION_RAISE_100": ACTION_RAISE_100,
        "ACTION_RAISE_150": ACTION_RAISE_150,
        "ACTION_RAISE_200": ACTION_RAISE_200,
        "ACTION_ALL_IN": ACTION_ALL_IN,
    }
    assert actual == expected, (
        "Python action-ID constants drifted from the canonical table; "
        "Rust mirror in hunl.rs must be updated to match."
    )
    # Indirect parity proxy: drive a short solve and confirm the key set
    # (which embeds the betting-history tokens via apply()) matches Python's.
    config = default_tiny_subgame()
    game = HUNLPoker(config)
    py = solve(game, iterations=100, backend="python", seed=42, **DCFR_KWARGS)
    rs = solve(game, iterations=100, backend="rust", seed=42, **DCFR_KWARGS)
    py_keys = set(py.average_strategy.keys())
    rs_keys = set(rs.average_strategy.keys())
    only_py = sorted(py_keys - rs_keys)[:10]
    only_rs = sorted(rs_keys - py_keys)[:10]
    assert py_keys == rs_keys, (
        "Action-ID drift: infoset key sets differ (likely betting_history "
        "token mismatch from a Rust action-ID off-by-one).\n"
        f"  Only in Python (first 10): {only_py}\n"
        f"  Only in Rust   (first 10): {only_rs}"
    )
