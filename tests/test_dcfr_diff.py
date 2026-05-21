"""Differential tests asserting the Python and Rust DCFR implementations agree.

The Python reference tier (`poker_solver/dcfr.py`) is the ground truth. The Rust
production tier (`crates/cfr_core/`) is a structural port that must produce
numerically equivalent outputs. These tests are the gate that keeps the two
implementations in lockstep.
"""

from __future__ import annotations

import pytest

from poker_solver import KuhnPoker, solve

# Tolerances. The Rust port is bit-exact today; we allow small headroom for
# future float-order changes (e.g. SIMD reductions) without making real
# divergences pass silently.
STRATEGY_ATOL = 1e-4
VALUE_ATOL = 1e-5
EXPLOIT_ATOL = 1e-4

ITERATIONS = 10_000
DCFR_KWARGS = dict(alpha=1.5, beta=0.0, gamma=2.0)


@pytest.fixture(scope="module")
def both_results():
    game = KuhnPoker()
    py = solve(game, iterations=ITERATIONS, backend="python", **DCFR_KWARGS)
    rs = solve(game, iterations=ITERATIONS, backend="rust", **DCFR_KWARGS)
    return py, rs


def _diff_strategies(a: dict[str, list[float]], b: dict[str, list[float]], atol: float):
    """Return a list of (infoset, action_idx, py_prob, rs_prob, abs_diff)
    tuples for any per-action diff exceeding atol."""
    diffs = []
    for key in sorted(set(a.keys()) | set(b.keys())):
        if key not in a or key not in b:
            diffs.append((key, -1, a.get(key), b.get(key), float("inf")))
            continue
        for i, (pa, pb) in enumerate(zip(a[key], b[key])):
            d = abs(pa - pb)
            if d > atol:
                diffs.append((key, i, pa, pb, d))
    return diffs


def test_kuhn_python_rust_infoset_keys_match(both_results):
    py, rs = both_results
    py_keys = set(py.average_strategy.keys())
    rs_keys = set(rs.average_strategy.keys())
    assert py_keys == rs_keys, (
        f"Infoset key sets diverge.\n"
        f"  Only in Python: {sorted(py_keys - rs_keys)}\n"
        f"  Only in Rust:   {sorted(rs_keys - py_keys)}"
    )
    assert len(py_keys) == 12, f"Kuhn should have 12 infosets, got {len(py_keys)}"


def test_kuhn_python_rust_strategy_agreement(both_results):
    py, rs = both_results
    diffs = _diff_strategies(py.average_strategy, rs.average_strategy, STRATEGY_ATOL)
    assert not diffs, (
        "Per-action strategy probabilities diverge between Python and Rust tiers:\n"
        + "\n".join(
            f"  {key} action {i}: python={pa!r} rust={pb!r} |diff|={d:.3e}"
            for (key, i, pa, pb, d) in diffs
        )
    )


def test_kuhn_python_rust_game_value_agreement(both_results):
    py, rs = both_results
    assert py.game_value == pytest.approx(
        rs.game_value, abs=VALUE_ATOL
    ), f"Game value diverges: python={py.game_value!r} rust={rs.game_value!r}"


def test_kuhn_python_rust_exploitability_agreement(both_results):
    py, rs = both_results
    py_exp = py.exploitability_history[-1]
    rs_exp = rs.exploitability_history[-1]
    assert py_exp == pytest.approx(
        rs_exp, abs=EXPLOIT_ATOL
    ), f"Final exploitability diverges: python={py_exp!r} rust={rs_exp!r}"


def test_kuhn_both_backends_reach_nash(both_results):
    """Sanity: both implementations should also be near the closed-form Nash."""
    nash_value = -1.0 / 18.0
    py, rs = both_results
    assert py.game_value == pytest.approx(nash_value, abs=5e-3)
    assert rs.game_value == pytest.approx(nash_value, abs=5e-3)
    assert py.exploitability_history[-1] < 5e-3
    assert rs.exploitability_history[-1] < 5e-3
