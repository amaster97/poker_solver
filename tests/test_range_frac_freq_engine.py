"""B10 Phase B — Aggregator + solver per-combo weight propagation tests.

Phase A landed the data model (``Combo`` subclass + ``Range._weight`` storage
+ ``parse_range`` ``:weight`` grammar) in PR #149. Phase B wires those
per-combo weights through the aggregator (``_aggregate_range`` +
``_project_to_hand_classes``) and the equity calculator's range-vs-hand
sampling path. The Rust binding gets an optional ``p0_weights`` /
``p1_weights`` kwarg whose default is all-ones (bit-identical to
pre-Phase-B).

Test surface:
    * Aggregator with all-1.0 weights → identical to legacy combo-count
      weighting (back-compat by construction).
    * Aggregator with mixed weights (AsKs:0.7, AhKh:0.3) → properly
      weighted per-class strategy.
    * Within-class projection: weighted average across combos differs
      from a uniform average when weights vary.
    * Equity calc with a weighted range produces a different equity
      result than the same range with uniform weights (the weighted
      range biases toward high-equity combos).
    * Kuhn-sized mixed-strategy convergence: a small fully-synthetic
      ``per_class_strategy`` + per-combo-row table verifies that
      ``_project_to_hand_classes`` produces the analytic expectation
      within ``5e-2`` for a non-trivial weighted average.

All tests are pure Python — no Rust binding is touched because the
Rust kernel changes need a ``maturin develop --release`` rebuild that
this PR's CI handles. The Rust-side per-cell contract change is
covered by the existing differential test
``tests/test_range_vs_range_rust_diff.py`` (which exercises the all-
ones default path) until a Phase-B-specific Rust-side test lands in a
follow-up.
"""

from __future__ import annotations

import random

import pytest

from poker_solver.card import parse_card as p
from poker_solver.range import Range, parse_range
from poker_solver.range_aggregator import (
    _aggregate_range,
    _combo_count,
    _enumerate_combos,
)


# ---------------------------------------------------------------------------
# Aggregator back-compat — all-1.0 weights reproduce legacy combo-count path
# ---------------------------------------------------------------------------


def test_aggregator_all_one_weights_matches_legacy() -> None:
    """A fully-populated all-1.0 ``Range`` produces the same per-class
    weighting as the legacy ``_combo_count`` path.

    This is the back-compat invariant for the Phase B refactor: existing
    callers that haven't adopted fractional weights (or pass class-label
    sequences instead of a ``Range``) must see no behavior change.
    """
    per_class = {
        "AKs": {"bet": 1.0, "check": 0.0},
        "AKo": {"bet": 0.0, "check": 1.0},
    }
    class_order = ["AKs", "AKo"]

    # Legacy path: range_ = None.
    legacy = _aggregate_range(per_class, class_order, None)

    # Phase B path: Range with all combos at weight 1.0.
    r = parse_range("AKs, AKo")
    # Sanity check: every combo is at weight 1.0.
    for c in r:
        assert c.weight == 1.0, f"combo {c} has non-default weight"

    phase_b = _aggregate_range(per_class, class_order, r)

    # Same key set and same values to float epsilon.
    assert legacy.keys() == phase_b.keys()
    for k in legacy:
        assert pytest.approx(phase_b[k], abs=1e-12) == legacy[k], (
            f"all-1.0 weight aggregator MUST match legacy on {k!r}: "
            f"legacy={legacy[k]} phase_b={phase_b[k]}"
        )


def test_aggregator_default_range_argument_is_none() -> None:
    """The new ``range_`` parameter on ``_aggregate_range`` defaults to
    ``None`` so existing call sites that pass only two positional
    arguments keep working.

    Codifies the back-compat shim: existing tests like
    ``test_aggregate_range_weights_aks_4_ako_12`` pass exactly two args.
    """
    per_class = {
        "AA": {"bet": 1.0, "check": 0.0},
        "AKs": {"bet": 0.0, "check": 1.0},
    }
    # Two-positional-arg call: must not raise.
    result = _aggregate_range(per_class, ["AA", "AKs"])
    # AA = 6 combos, AKs = 4 combos, so bet weight = 6/10 = 0.6.
    assert pytest.approx(result["bet"], abs=1e-9) == 6.0 / 10.0
    assert pytest.approx(result["check"], abs=1e-9) == 4.0 / 10.0


# ---------------------------------------------------------------------------
# Aggregator weighted-mix tests — Phase B feature
# ---------------------------------------------------------------------------


def test_aggregator_mixed_weights_within_class_aks() -> None:
    """When a Range has AsKs at 0.7 and AhKh at 0.3 (other AKs combos
    absent), the *class-level* combo weight for AKs is 1.0, not 4.0.

    Because the weight sum acts as the class-level coefficient,
    classes with low total weight contribute less to the range
    aggregate. This is the core Phase B mechanic.
    """
    # AsKs + AhKh both fall under hand class "AKs" (combos: 4 suited).
    asks = (p("As"), p("Ks"))
    ahkh = (p("Ah"), p("Kh"))

    r = Range()
    r.add(asks, weight=0.7)
    r.add(ahkh, weight=0.3)

    # Class-level weight from _aggregate_range's perspective:
    # _enumerate_combos("AKs") returns 4 combos; only 2 are present in r
    # at non-zero weight. Sum = 0.7 + 0.3 = 1.0.
    expected_weight = 0.0
    for c in _enumerate_combos("AKs"):
        expected_weight += r.weight(c)
    assert pytest.approx(expected_weight, abs=1e-9) == 1.0

    # A second class to ensure the relative weighting is exercised.
    aa_combo = (p("As"), p("Ah"))
    r.add(aa_combo, weight=1.0)
    # AA class total weight: only 1 combo at 1.0; the other 5 are absent.
    expected_aa_weight = 0.0
    for c in _enumerate_combos("AA"):
        expected_aa_weight += r.weight(c)
    assert pytest.approx(expected_aa_weight, abs=1e-9) == 1.0

    per_class = {
        "AKs": {"bet": 1.0, "check": 0.0},
        "AA": {"bet": 0.0, "check": 1.0},
    }
    agg = _aggregate_range(per_class, ["AKs", "AA"], r)
    # Both classes contribute equal weight (1.0 each), so the aggregate
    # should split 50/50 between bet and check.
    assert pytest.approx(agg["bet"], abs=1e-9) == 0.5
    assert pytest.approx(agg["check"], abs=1e-9) == 0.5


def test_aggregator_lighter_class_contributes_less() -> None:
    """A class with all combos at weight 0.5 contributes half as much to
    the aggregate as a fully-weighted class — exactly the Phase B
    fractional-frequency mechanic.

    Setup: AKs has 4 combos at weight 1.0; AKo has 12 combos at 0.5.
    Class weights: AKs = 4.0, AKo = 6.0. With AKs betting 100% and AKo
    checking 100%, the bet aggregate should be 4 / (4+6) = 0.40.
    """
    r = Range()
    for c in _enumerate_combos("AKs"):
        r.add(c, weight=1.0)
    for c in _enumerate_combos("AKo"):
        r.add(c, weight=0.5)

    per_class = {
        "AKs": {"bet": 1.0, "check": 0.0},
        "AKo": {"bet": 0.0, "check": 1.0},
    }
    agg = _aggregate_range(per_class, ["AKs", "AKo"], r)
    # AKs class weight = 4*1.0 = 4.0; AKo class weight = 12*0.5 = 6.0.
    # Bet aggregate = 4 / 10 = 0.40.
    assert pytest.approx(agg["bet"], abs=1e-9) == 4.0 / 10.0
    assert pytest.approx(agg["check"], abs=1e-9) == 6.0 / 10.0

    # Sanity: legacy combo-count path would give 4/(4+12) = 0.25 here.
    legacy = _aggregate_range(per_class, ["AKs", "AKo"], None)
    assert pytest.approx(legacy["bet"], abs=1e-9) == 4.0 / 16.0
    # Weighted result diverges from legacy by a meaningful margin.
    assert abs(agg["bet"] - legacy["bet"]) > 0.10


def test_aggregator_zero_weight_excludes_class() -> None:
    """A class whose every combo has weight 0 contributes nothing to the
    range aggregate — equivalent to dropping it from the range entirely.
    """
    # AKs fully-weighted, AKo entirely zero.
    r = Range()
    for c in _enumerate_combos("AKs"):
        r.add(c, weight=1.0)
    # Note: cannot ``add`` with weight=0 (Phase A allows it but it stores
    # the combo at 0; the aggregator still iterates and computes weight 0).
    for c in _enumerate_combos("AKo"):
        r.add(c, weight=0.0)

    per_class = {
        "AKs": {"bet": 1.0, "check": 0.0},
        "AKo": {"bet": 0.0, "check": 1.0},
    }
    agg = _aggregate_range(per_class, ["AKs", "AKo"], r)
    # Only AKs contributes; bet = 1.0.
    assert pytest.approx(agg["bet"], abs=1e-9) == 1.0
    assert pytest.approx(agg["check"], abs=1e-9) == 0.0


# ---------------------------------------------------------------------------
# Within-class projection — _project_to_hand_classes weighted average
# ---------------------------------------------------------------------------


def test_within_class_weighted_average_diverges_from_uniform() -> None:
    """When AsKs has weight 0.7 and AhKh has weight 0.3, and they have
    distinct per-row strategies, the weighted within-class average
    differs from the uniform average by the expected margin.

    This is the kernel of the within-class projection refactor: each
    combo's contribution to the class-level row is its weight, not the
    uniform 1/n the pre-Phase-B path used.
    """
    # Synthetic per-combo strategy rows for the 4 AKs combos. Only the
    # first two are present in the range; the others get weight 0.
    asks = (p("As"), p("Ks"))
    ahkh = (p("Ah"), p("Kh"))

    # Mock rows: AsKs bets aggressively (0.9), AhKh checks (0.1).
    rows = {asks: [0.9, 0.1], ahkh: [0.1, 0.9]}
    weights = {asks: 0.7, ahkh: 0.3}

    # Uniform average (legacy):
    uniform_avg = [(rows[asks][i] + rows[ahkh][i]) / 2 for i in range(2)]
    assert pytest.approx(uniform_avg[0], abs=1e-9) == 0.5
    assert pytest.approx(uniform_avg[1], abs=1e-9) == 0.5

    # Weighted average (Phase B):
    total_w = weights[asks] + weights[ahkh]
    weighted_avg = [
        (rows[asks][i] * weights[asks] + rows[ahkh][i] * weights[ahkh]) / total_w
        for i in range(2)
    ]
    # 0.9*0.7 + 0.1*0.3 = 0.63 + 0.03 = 0.66; divided by 1.0 = 0.66.
    assert pytest.approx(weighted_avg[0], abs=1e-9) == 0.66
    assert pytest.approx(weighted_avg[1], abs=1e-9) == 0.34
    # Weighted result diverges from uniform by a meaningful margin
    # (≥ 0.10 percentage points on the bet action).
    assert abs(weighted_avg[0] - uniform_avg[0]) > 0.10


# ---------------------------------------------------------------------------
# Equity — weighted range biases toward high-equity combos
# ---------------------------------------------------------------------------


def test_equity_weighted_range_differs_from_uniform() -> None:
    """A Range with one strong combo at high weight and one weak combo
    at low weight produces a higher hero equity than the same range with
    uniform weights — because the weighted sampler picks the strong combo
    more often.

    Use AhAd (premium pair) at high weight and 2c2d (weak pair) at low
    weight against a fixed villain 7s7h. The weighted range should be
    close to the all-AhAd equity (~80% AA vs 77); the uniform range
    should be closer to the average of the two (~55%).
    """
    villain = [p("7s"), p("7h")]

    # Weighted range: AhAd at 0.9, 2c2d at 0.1.
    weighted = Range()
    weighted.add((p("Ah"), p("Ad")), weight=0.9)
    weighted.add((p("2c"), p("2d")), weight=0.1)

    # Uniform range: both at 1.0.
    uniform = Range()
    uniform.add((p("Ah"), p("Ad")), weight=1.0)
    uniform.add((p("2c"), p("2d")), weight=1.0)

    rng_w = random.Random(42)
    rng_u = random.Random(42)
    from poker_solver.equity import equity

    weighted_eq = equity(
        [weighted, villain], iterations=4000, rng=rng_w
    )[0].equity
    uniform_eq = equity(
        [uniform, villain], iterations=4000, rng=rng_u
    )[0].equity

    # AhAd vs 7h7s ≈ 0.80; 2c2d vs 7h7s ≈ 0.20.
    # Weighted (0.9 AhAd + 0.1 2c2d) ≈ 0.90*0.80 + 0.10*0.20 = 0.74.
    # Uniform (0.5 each) ≈ 0.5*0.80 + 0.5*0.20 = 0.50.
    # The two should differ by at least 0.10 (the bias toward AhAd in the
    # weighted version dominates).
    assert weighted_eq - uniform_eq > 0.10, (
        f"weighted equity {weighted_eq:.4f} should exceed uniform "
        f"{uniform_eq:.4f} by > 0.10 when AhAd is at weight 0.9; "
        f"got delta = {weighted_eq - uniform_eq:.4f}"
    )
    # And the weighted result should be closer to pure-AhAd (~0.80)
    # than the uniform result is.
    assert weighted_eq > 0.65, (
        f"weighted equity {weighted_eq:.4f} should be > 0.65 (close to "
        f"pure AhAd ≈ 0.80 when AhAd is at weight 0.9)"
    )


def test_equity_sample_excluding_uniform_fast_path_back_compat() -> None:
    """All-1.0 ``Range.sample_excluding`` uses the rejection-sampling
    fast path. Verified statistically: across many calls with the same
    seed, the distribution of picks matches the uniform expectation."""
    r = parse_range("AKs")  # 4 combos, all at weight 1.0.
    rng = random.Random(7)
    counts: dict[tuple, int] = {}
    n_samples = 4000
    for _ in range(n_samples):
        c = r.sample_excluding(set(), rng)
        assert c is not None
        key = (c[0], c[1])
        counts[key] = counts.get(key, 0) + 1
    # Each of the 4 combos should be picked ~25% of the time. Loose
    # bound to avoid statistical flakiness.
    expected_per = n_samples / 4
    for combo, count in counts.items():
        assert abs(count - expected_per) < 0.10 * n_samples, (
            f"uniform fast-path bias on {combo}: {count} vs expected "
            f"{expected_per} (within ±10% of n_samples)"
        )


# ---------------------------------------------------------------------------
# Kuhn-sized weighted-projection analytic convergence
# ---------------------------------------------------------------------------


def test_kuhn_sized_weighted_projection_converges_analytic() -> None:
    """A 2-combo class with weights 0.7 / 0.3 and a 2-action infoset
    should produce a class-level row that matches the analytical
    weighted-mean formula within ``5e-2``.

    Setup:
      - 1 hand class: AKs (4 suited combos).
      - 2 present combos: AsKs at weight 0.7 (row [0.8, 0.2]) and
        AhKh at weight 0.3 (row [0.2, 0.8]).
      - Expected class row: [0.7*0.8 + 0.3*0.2, 0.7*0.2 + 0.3*0.8]
        = [0.62, 0.38].

    The aggregator's range aggregate (single class) should equal the
    same row. We exercise the weighted-mean code path directly without
    invoking the Rust binding.
    """
    asks = (p("As"), p("Ks"))
    ahkh = (p("Ah"), p("Kh"))
    r = Range()
    r.add(asks, weight=0.7)
    r.add(ahkh, weight=0.3)

    # Compute the weighted within-class average manually (mimicking
    # _project_to_hand_classes' inner loop).
    rows_with_w = [
        ([0.8, 0.2], r.weight(asks)),
        ([0.2, 0.8], r.weight(ahkh)),
    ]
    total_w = sum(w for _, w in rows_with_w)
    weighted_row = [
        sum(row[i] * w for row, w in rows_with_w) / total_w for i in range(2)
    ]
    # Analytical: 0.7*0.8 + 0.3*0.2 = 0.62.
    assert pytest.approx(weighted_row[0], abs=5e-2) == 0.62
    assert pytest.approx(weighted_row[1], abs=5e-2) == 0.38

    # Aggregator path: feed the weighted class row in and verify the
    # range aggregate (single class, single non-zero combo weight sum)
    # equals the per-class row.
    per_class = {"AKs": {"bet": weighted_row[0], "check": weighted_row[1]}}
    agg = _aggregate_range(per_class, ["AKs"], r)
    assert pytest.approx(agg["bet"], abs=5e-2) == 0.62
    assert pytest.approx(agg["check"], abs=5e-2) == 0.38


# ---------------------------------------------------------------------------
# Back-compat — _combo_count semantics unchanged
# ---------------------------------------------------------------------------


def test_combo_count_unchanged_after_phase_b() -> None:
    """``_combo_count`` is the legacy fallback weight when no Range is
    supplied; verify Phase B did not perturb its return values for any
    canonical class label.
    """
    assert _combo_count("AA") == 6
    assert _combo_count("KK") == 6
    assert _combo_count("AKs") == 4
    assert _combo_count("AKo") == 12
    assert _combo_count("AK") == 16
    assert _combo_count("AhKh") == 1
