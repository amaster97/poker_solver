"""Differential tests asserting the Python and Rust DCFR implementations agree on Leduc.

The Python reference tier (`poker_solver/dcfr.py`) is the ground truth. The Rust
production tier (`crates/cfr_core/`) is a structural port that must produce
numerically equivalent outputs. These tests are the gate that keeps the two
implementations in lockstep for Leduc poker.
"""

from __future__ import annotations

import pytest

from poker_solver import LeducPoker, solve

# Tolerances. The Rust port targets bit-exactness; we allow small headroom for
# future float-order changes (e.g. SIMD reductions) without making real
# divergences pass silently.
STRATEGY_ATOL = 1e-4
VALUE_ATOL = 1e-5
EXPLOIT_ATOL = 1e-4

ITERATIONS = 2_000
DCFR_KWARGS = dict(alpha=1.5, beta=0.0, gamma=2.0)


@pytest.fixture(scope="module")
def both_results():
    game = LeducPoker()
    py = solve(game, iterations=ITERATIONS, backend="python", **DCFR_KWARGS)
    rs = solve(game, iterations=ITERATIONS, backend="rust", **DCFR_KWARGS)
    return py, rs


# pytest-timeout doesn't apply to module-scoped fixtures by default; bumping
# the timeout per-test gives the shared fixture's first-touch setup (Python
# Leduc DCFR + Rust DCFR @ 2k iters + cold Rust binding load) ample headroom
# above pytest's 90s default. Observed ~140s on x86_64 Python under Rosetta
# (Python baseline leg dominates; Rust leg is ~18s).
_LEDUC_DIFF_TIMEOUT = 300


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


@pytest.mark.timeout(_LEDUC_DIFF_TIMEOUT)
def test_leduc_python_rust_infoset_keys_match(both_results):
    py, rs = both_results
    py_keys = set(py.average_strategy.keys())
    rs_keys = set(rs.average_strategy.keys())
    assert py_keys == rs_keys, (
        f"Infoset key sets diverge.\n"
        f"  Only in Python: {sorted(py_keys - rs_keys)}\n"
        f"  Only in Rust:   {sorted(rs_keys - py_keys)}"
    )
    assert len(py_keys) == 288, f"Leduc should have 288 infosets, got {len(py_keys)}"


@pytest.mark.timeout(_LEDUC_DIFF_TIMEOUT)
def test_leduc_python_rust_strategy_agreement(both_results):
    py, rs = both_results
    diffs = _diff_strategies(py.average_strategy, rs.average_strategy, STRATEGY_ATOL)
    assert not diffs, (
        "Per-action strategy probabilities diverge between Python and Rust tiers:\n"
        + "\n".join(
            f"  {key} action {i}: python={pa!r} rust={pb!r} |diff|={d:.3e}"
            for (key, i, pa, pb, d) in diffs
        )
    )


@pytest.mark.timeout(_LEDUC_DIFF_TIMEOUT)
def test_leduc_python_rust_game_value_agreement(both_results):
    py, rs = both_results
    assert py.game_value == pytest.approx(
        rs.game_value, abs=VALUE_ATOL
    ), f"Game value diverges: python={py.game_value!r} rust={rs.game_value!r}"


@pytest.mark.timeout(_LEDUC_DIFF_TIMEOUT)
def test_leduc_python_rust_exploitability_agreement(both_results):
    py, rs = both_results
    py_exp = py.exploitability_history[-1]
    rs_exp = rs.exploitability_history[-1]
    assert py_exp == pytest.approx(
        rs_exp, abs=EXPLOIT_ATOL
    ), f"Final exploitability diverges: python={py_exp!r} rust={rs_exp!r}"


@pytest.mark.timeout(_LEDUC_DIFF_TIMEOUT)
def test_leduc_both_backends_reach_published_value(both_results):
    """Sanity: both implementations should be near the published Leduc value."""
    published_value = -0.085
    py, rs = both_results
    assert py.game_value == pytest.approx(published_value, abs=5e-3)
    assert rs.game_value == pytest.approx(published_value, abs=5e-3)
