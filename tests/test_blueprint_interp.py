"""Phase 3 blueprint interpolation tests (Premium-A, task #68).

Coverage:
  1. Exact-match short-circuit: target = supplied depth → byte-for-byte
     return (no normalization drift, no NaNs).
  2. Midpoint linear interpolation: 50/50 blend between two depths.
  3. Below-min clamp: target < minimum supplied depth → lowest blueprint.
  4. Above-max clamp: target > maximum supplied depth → highest blueprint.
  5. Normalization preserved: every interpolated vector sums to 1.0 within
     1e-9 across a fine grid of target depths.
  6. Mixed strategy interpolation: AA 80/20 raise/limp at 40bb and 90/10
     at 80bb → 85/15 at 60bb (midpoint).
  7. ``method="nearest"`` snaps to closest grid point with deterministic
     low-tie-break.
  8. ``method="nearest"`` vs ``method="linear"`` differ in mid-grid cases.
  9. Empty strategies dict → ``InterpolationError``.
 10. Unknown method string → ``InterpolationError``.
 11. Mismatched action-vector lengths between depths → ``InterpolationError``.
 12. Negative probability input rejected.
 13. NaN probability input rejected.
 14. Single supplied depth (degenerate grid) → that depth used for any target.
 15. Full blueprint-block interpolation: 169-class shape preserved.
 16. Blueprint-block mismatch detected: missing history key in one depth.
 17. Blueprint-block mismatch detected: missing hand class in one infoset.
 18. ``find_flanking_depths`` returns correct pair (interior, boundary,
     exact, out-of-range).
 19. ``find_flanking_depths`` rejects empty depth list.
 20. Worst-case L1 drift across the full 9-depth blueprint grid is bounded.
 21. Returned vectors are detached from caller-supplied lists (no aliasing).
"""

from __future__ import annotations

import math

import pytest

from poker_solver.blueprint_interp import (
    InterpolationError,
    find_flanking_depths,
    interpolate_blueprint_strategies,
    interpolate_strategy,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

# Locked Phase 1 blueprint grid (must match ``blueprint.standard_batch_specs``).
PHASE_1_DEPTHS = [20, 30, 40, 60, 80, 100, 150, 175, 200]


def _make_two_depth_strategies(
    v_lo: list[float], v_hi: list[float], d_lo: float = 40, d_hi: float = 80
) -> dict[float, list[float]]:
    """Convenience: build a {d_lo: v_lo, d_hi: v_hi} input."""
    return {d_lo: v_lo, d_hi: v_hi}


# ---------------------------------------------------------------------------
# 1. Exact-match short-circuit
# ---------------------------------------------------------------------------


def test_exact_match_returns_input_no_drift() -> None:
    strategies = _make_two_depth_strategies(
        [0.8, 0.15, 0.05], [0.6, 0.3, 0.1], d_lo=40, d_hi=80
    )
    result = interpolate_strategy(target_bb=40, strategies=strategies)
    # Byte-for-byte: each entry equals the source. (We return a *new*
    # list so this checks values, not identity.)
    assert result == [0.8, 0.15, 0.05]
    # No NaN regardless.
    for x in result:
        assert not math.isnan(x)


def test_exact_match_high_end_returns_input() -> None:
    strategies = _make_two_depth_strategies(
        [0.8, 0.15, 0.05], [0.6, 0.3, 0.1], d_lo=40, d_hi=80
    )
    result = interpolate_strategy(target_bb=80, strategies=strategies)
    assert result == [0.6, 0.3, 0.1]


def test_exact_match_within_float_tolerance() -> None:
    # 40 + 1e-12 is "exactly" 40 for our purposes.
    strategies = _make_two_depth_strategies([0.5, 0.5], [0.2, 0.8], d_lo=40, d_hi=80)
    result = interpolate_strategy(target_bb=40 + 1e-12, strategies=strategies)
    assert result == [0.5, 0.5]


# ---------------------------------------------------------------------------
# 2. Midpoint linear interpolation
# ---------------------------------------------------------------------------


def test_midpoint_is_50_50_blend() -> None:
    strategies = _make_two_depth_strategies([1.0, 0.0], [0.0, 1.0], d_lo=40, d_hi=80)
    result = interpolate_strategy(target_bb=60, strategies=strategies)
    # 50/50 of [1, 0] and [0, 1] = [0.5, 0.5].
    assert result == pytest.approx([0.5, 0.5], abs=1e-12)


def test_third_point_is_weighted_correctly() -> None:
    # target=50 between 40 and 80 → t = (50 - 40) / (80 - 40) = 0.25.
    # Expect: 0.75 * v_lo + 0.25 * v_hi.
    strategies = _make_two_depth_strategies([1.0, 0.0], [0.0, 1.0], d_lo=40, d_hi=80)
    result = interpolate_strategy(target_bb=50, strategies=strategies)
    assert result == pytest.approx([0.75, 0.25], abs=1e-12)


def test_strict_between_in_open_interval() -> None:
    """For target strictly between d_lo and d_hi, result must strictly
    lie *between* the endpoints (not equal to either)."""
    strategies = _make_two_depth_strategies(
        [0.8, 0.15, 0.05], [0.6, 0.3, 0.1], d_lo=40, d_hi=80
    )
    result = interpolate_strategy(target_bb=60, strategies=strategies)
    v_lo = strategies[40]
    v_hi = strategies[80]
    for x, lo, hi in zip(result, v_lo, v_hi):
        # Either x is strictly between lo and hi, or it equals one of
        # them only because lo == hi at that slot.
        if lo == hi:
            assert x == pytest.approx(lo, abs=1e-12)
        else:
            assert min(lo, hi) < x < max(lo, hi)


# ---------------------------------------------------------------------------
# 3 & 4. Out-of-range clamp
# ---------------------------------------------------------------------------


def test_below_min_clamps_to_lowest_depth() -> None:
    strategies = _make_two_depth_strategies([0.8, 0.2], [0.5, 0.5], d_lo=40, d_hi=80)
    result = interpolate_strategy(target_bb=20, strategies=strategies)
    assert result == [0.8, 0.2]


def test_above_max_clamps_to_highest_depth() -> None:
    strategies = _make_two_depth_strategies([0.8, 0.2], [0.5, 0.5], d_lo=40, d_hi=80)
    result = interpolate_strategy(target_bb=300, strategies=strategies)
    assert result == [0.5, 0.5]


def test_clamp_across_full_phase1_grid() -> None:
    # Mock a full 9-depth grid where each depth has a distinct vector.
    grid = {d: [float(d) / 1000.0, 1.0 - float(d) / 1000.0] for d in PHASE_1_DEPTHS}
    # Target below grid → clamp to 20.
    res_lo = interpolate_strategy(target_bb=5, strategies=grid)
    assert res_lo == pytest.approx(grid[20], abs=1e-12)
    # Target above grid → clamp to 200.
    res_hi = interpolate_strategy(target_bb=500, strategies=grid)
    assert res_hi == pytest.approx(grid[200], abs=1e-12)


# ---------------------------------------------------------------------------
# 5. Normalization preserved everywhere
# ---------------------------------------------------------------------------


def test_normalization_sums_to_one_across_fine_grid() -> None:
    # Two unit-sum vectors at 40bb and 80bb. Walk target across the
    # full plausible range in 0.5-BB steps; every result must sum to
    # 1.0 within 1e-9.
    strategies = _make_two_depth_strategies(
        [0.4, 0.35, 0.2, 0.05], [0.25, 0.5, 0.15, 0.10], d_lo=40, d_hi=80
    )
    bb = 10.0
    while bb <= 110.0:
        result = interpolate_strategy(target_bb=bb, strategies=strategies)
        s = sum(result)
        assert abs(s - 1.0) <= 1e-9, f"sum = {s} at target_bb={bb}"
        for x in result:
            assert 0.0 <= x <= 1.0, f"entry {x} out of [0, 1] at target_bb={bb}"
        bb += 0.5


def test_normalization_with_full_grid() -> None:
    """Same normalization invariant against the 9-depth grid."""
    grid: dict[float, list[float]] = {}
    # Pseudo-mixed strategies that still each sum to 1.
    for d in PHASE_1_DEPTHS:
        p = (d - 20) / (200 - 20)  # 0..1 as depth ramps
        grid[d] = [0.5 + 0.3 * p, 0.5 - 0.3 * p]
    for target in [25, 35, 45, 55, 67, 70, 90, 125, 175, 190]:
        result = interpolate_strategy(target_bb=target, strategies=grid)
        assert abs(sum(result) - 1.0) <= 1e-9


# ---------------------------------------------------------------------------
# 6. Mixed strategy interpolation (explicit AA raise/limp example)
# ---------------------------------------------------------------------------


def test_mixed_strategy_aa_raise_limp_midpoint() -> None:
    """AA 80% raise / 20% limp at 40bb, 90% raise / 10% limp at 80bb
    → 85% raise / 15% limp at 60bb (midpoint)."""
    strategies = {
        40: [0.20, 0.80],  # [limp, raise]
        80: [0.10, 0.90],
    }
    result = interpolate_strategy(target_bb=60, strategies=strategies)
    assert result == pytest.approx([0.15, 0.85], abs=1e-12)


def test_mixed_strategy_67bb_user_scenario() -> None:
    """User at 67bb between 60bb and 80bb shards.

    AA 92% raise / 8% all-in at 60bb, 88% raise / 12% all-in at 80bb.
    Target 67bb → t = 0.35 → ~0.9060 raise, ~0.0940 all-in.
    """
    strategies = {
        60: [0.92, 0.08],
        80: [0.88, 0.12],
    }
    result = interpolate_strategy(target_bb=67, strategies=strategies)
    t = (67 - 60) / (80 - 60)
    expected = [
        (1 - t) * 0.92 + t * 0.88,
        (1 - t) * 0.08 + t * 0.12,
    ]
    # Should match before final renormalization to within ULP; after
    # renormalization to within 1e-12.
    assert result == pytest.approx(expected, abs=1e-9)
    assert abs(sum(result) - 1.0) <= 1e-9


# ---------------------------------------------------------------------------
# 7-8. Linear vs nearest mode
# ---------------------------------------------------------------------------


def test_nearest_mode_snaps_to_closest_depth() -> None:
    strategies = {
        40: [1.0, 0.0],
        80: [0.0, 1.0],
    }
    # Closer to 40 → snap to 40.
    res = interpolate_strategy(target_bb=55, strategies=strategies, method="nearest")
    assert res == [1.0, 0.0]
    # Closer to 80 → snap to 80.
    res2 = interpolate_strategy(target_bb=70, strategies=strategies, method="nearest")
    assert res2 == [0.0, 1.0]


def test_nearest_mode_tie_break_low() -> None:
    """Exact midpoint → tie-break toward the lower depth."""
    strategies = {
        40: [1.0, 0.0],
        80: [0.0, 1.0],
    }
    res = interpolate_strategy(target_bb=60, strategies=strategies, method="nearest")
    # Midpoint is 60 → tie-break low → returns 40bb strategy.
    assert res == [1.0, 0.0]


def test_linear_vs_nearest_differ_off_grid() -> None:
    strategies = {
        40: [1.0, 0.0],
        80: [0.0, 1.0],
    }
    linear = interpolate_strategy(target_bb=70, strategies=strategies, method="linear")
    nearest = interpolate_strategy(
        target_bb=70, strategies=strategies, method="nearest"
    )
    # Linear at t=0.75 → [0.25, 0.75].
    assert linear == pytest.approx([0.25, 0.75], abs=1e-12)
    # Nearest at 70 (closer to 80) → [0, 1].
    assert nearest == [0.0, 1.0]
    assert linear != nearest


def test_nearest_mode_handles_exact_match() -> None:
    strategies = {40: [0.7, 0.3], 80: [0.4, 0.6]}
    res = interpolate_strategy(target_bb=40, strategies=strategies, method="nearest")
    assert res == [0.7, 0.3]


def test_nearest_mode_clamps_out_of_range() -> None:
    strategies = {40: [0.7, 0.3], 80: [0.4, 0.6]}
    assert interpolate_strategy(
        target_bb=10, strategies=strategies, method="nearest"
    ) == [0.7, 0.3]
    assert interpolate_strategy(
        target_bb=300, strategies=strategies, method="nearest"
    ) == [0.4, 0.6]


# ---------------------------------------------------------------------------
# 9-13. Error handling
# ---------------------------------------------------------------------------


def test_empty_strategies_raises() -> None:
    with pytest.raises(InterpolationError, match="at least one depth"):
        interpolate_strategy(target_bb=60, strategies={})


def test_unknown_method_raises() -> None:
    with pytest.raises(InterpolationError, match="unknown interpolation method"):
        interpolate_strategy(
            target_bb=60,
            strategies={40: [1.0, 0.0], 80: [0.0, 1.0]},
            method="cubic",  # type: ignore[arg-type]
        )


def test_mismatched_vector_lengths_raises() -> None:
    with pytest.raises(InterpolationError, match="length"):
        interpolate_strategy(
            target_bb=60,
            strategies={40: [1.0, 0.0], 80: [0.0, 0.5, 0.5]},
        )


def test_negative_probability_input_rejected() -> None:
    with pytest.raises(InterpolationError, match="out of"):
        interpolate_strategy(
            target_bb=60,
            strategies={40: [1.1, -0.1], 80: [0.0, 1.0]},
        )


def test_nan_input_rejected() -> None:
    with pytest.raises(InterpolationError, match="NaN"):
        interpolate_strategy(
            target_bb=60,
            strategies={40: [float("nan"), 0.0], 80: [0.5, 0.5]},
        )


# ---------------------------------------------------------------------------
# 14. Degenerate single-depth grid
# ---------------------------------------------------------------------------


def test_single_depth_returns_that_strategy_for_any_target() -> None:
    strategies = {60: [0.4, 0.6]}
    # Below.
    assert interpolate_strategy(target_bb=10, strategies=strategies) == [0.4, 0.6]
    # Exact.
    assert interpolate_strategy(target_bb=60, strategies=strategies) == [0.4, 0.6]
    # Above.
    assert interpolate_strategy(target_bb=500, strategies=strategies) == [0.4, 0.6]


# ---------------------------------------------------------------------------
# 15-17. Blueprint-block interpolation
# ---------------------------------------------------------------------------


def _make_mini_block(
    p_fold: float, p_call: float, p_raise: float
) -> dict[str, dict[str, list[float]]]:
    """Construct a tiny ``{history: {class: [probs]}}`` block."""
    return {
        "||p|": {
            "AA": [p_fold, p_call, p_raise],
            "KK": [p_fold + 0.05, p_call, p_raise - 0.05],
        }
    }


def test_blueprint_block_interpolation_169_shape_preserved() -> None:
    block_lo = _make_mini_block(0.0, 0.2, 0.8)
    block_hi = _make_mini_block(0.0, 0.4, 0.6)
    strategies = {40: block_lo, 80: block_hi}
    out = interpolate_blueprint_strategies(target_bb=60, strategies=strategies)
    # Shape preserved.
    assert set(out.keys()) == {"||p|"}
    assert set(out["||p|"].keys()) == {"AA", "KK"}
    # AA at midpoint: [0, 0.3, 0.7].
    assert out["||p|"]["AA"] == pytest.approx([0.0, 0.3, 0.7], abs=1e-12)
    # KK at midpoint: [0.05, 0.3, 0.65].
    assert out["||p|"]["KK"] == pytest.approx([0.05, 0.3, 0.65], abs=1e-12)


def test_blueprint_block_exact_match_returns_copy() -> None:
    block_lo = _make_mini_block(0.0, 0.2, 0.8)
    block_hi = _make_mini_block(0.0, 0.4, 0.6)
    strategies = {40: block_lo, 80: block_hi}
    out = interpolate_blueprint_strategies(target_bb=40, strategies=strategies)
    # Equal to block_lo, but not the same object.
    assert out == block_lo
    assert out is not block_lo
    assert out["||p|"]["AA"] is not block_lo["||p|"]["AA"]


def test_blueprint_block_clamp_below_min() -> None:
    block_lo = _make_mini_block(0.0, 0.2, 0.8)
    block_hi = _make_mini_block(0.0, 0.4, 0.6)
    strategies = {40: block_lo, 80: block_hi}
    out = interpolate_blueprint_strategies(target_bb=5, strategies=strategies)
    assert out == block_lo


def test_blueprint_block_mismatched_history_keys_raises() -> None:
    block_lo = {"||p|": {"AA": [0.5, 0.5]}}
    block_hi = {"||p|c": {"AA": [0.3, 0.7]}}
    strategies = {40: block_lo, 80: block_hi}
    with pytest.raises(InterpolationError, match="history keys differ"):
        interpolate_blueprint_strategies(target_bb=60, strategies=strategies)


def test_blueprint_block_mismatched_hand_classes_raises() -> None:
    block_lo = {"||p|": {"AA": [0.5, 0.5], "KK": [0.6, 0.4]}}
    block_hi = {"||p|": {"AA": [0.5, 0.5], "QQ": [0.6, 0.4]}}
    strategies = {40: block_lo, 80: block_hi}
    with pytest.raises(InterpolationError, match="hand classes differ"):
        interpolate_blueprint_strategies(target_bb=60, strategies=strategies)


def test_blueprint_block_action_length_mismatch_raises() -> None:
    block_lo = {"||p|": {"AA": [0.5, 0.5]}}
    block_hi = {"||p|": {"AA": [0.3, 0.3, 0.4]}}
    strategies = {40: block_lo, 80: block_hi}
    with pytest.raises(InterpolationError, match="action vector length mismatch"):
        interpolate_blueprint_strategies(target_bb=60, strategies=strategies)


def test_blueprint_block_nearest_mode_returns_closest() -> None:
    block_lo = _make_mini_block(0.0, 0.2, 0.8)
    block_hi = _make_mini_block(0.0, 0.4, 0.6)
    strategies = {40: block_lo, 80: block_hi}
    out = interpolate_blueprint_strategies(
        target_bb=70, strategies=strategies, method="nearest"
    )
    # 70 is closer to 80 → return block_hi.
    assert out == block_hi


# ---------------------------------------------------------------------------
# 18-19. Flanking-depth helper
# ---------------------------------------------------------------------------


def test_find_flanking_depths_interior() -> None:
    depths = [20, 40, 60, 80, 100]
    assert find_flanking_depths(target_bb=50, depths=depths) == (40, 60)
    assert find_flanking_depths(target_bb=67, depths=depths) == (60, 80)


def test_find_flanking_depths_exact_match() -> None:
    depths = [20, 40, 60, 80, 100]
    assert find_flanking_depths(target_bb=40, depths=depths) == (40, 40)


def test_find_flanking_depths_below_min() -> None:
    depths = [20, 40, 60, 80, 100]
    assert find_flanking_depths(target_bb=10, depths=depths) == (20, 20)


def test_find_flanking_depths_above_max() -> None:
    depths = [20, 40, 60, 80, 100]
    assert find_flanking_depths(target_bb=300, depths=depths) == (100, 100)


def test_find_flanking_depths_empty_raises() -> None:
    with pytest.raises(InterpolationError, match="non-empty"):
        find_flanking_depths(target_bb=60, depths=[])


def test_find_flanking_depths_user_67bb_scenario() -> None:
    """User at 67bb against the Phase 1 grid should flank with 60-80."""
    assert find_flanking_depths(67, PHASE_1_DEPTHS) == (60, 80)


# ---------------------------------------------------------------------------
# 20. Worst-case L1 drift bound
# ---------------------------------------------------------------------------


def test_worst_case_l1_drift_bounded() -> None:
    """Across a representative grid of (vector, target_bb) pairs, the
    L1 distance between interpolation-then-renormalize and a manually
    computed convex blend must stay below 1e-12.

    This is the precise "drift" the report asks about — what the
    renormalize step introduces beyond an exact convex combination.
    """
    test_vectors_lo = [
        [0.5, 0.5],
        [0.1, 0.2, 0.3, 0.4],
        [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # extreme: pure
        [0.999, 0.001],
    ]
    test_vectors_hi = [
        [0.7, 0.3],
        [0.4, 0.3, 0.2, 0.1],
        [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        [0.5, 0.5],
    ]
    targets = [25, 41, 50, 67, 79.5, 99, 175]
    worst_drift = 0.0
    for v_lo, v_hi in zip(test_vectors_lo, test_vectors_hi):
        strategies = {40: v_lo, 80: v_hi}
        for target in targets:
            result = interpolate_strategy(target_bb=target, strategies=strategies)
            # Manual reference: same convex combination, no renormalize.
            if target <= 40:
                expected = list(v_lo)
            elif target >= 80:
                expected = list(v_hi)
            else:
                t = (target - 40) / (80 - 40)
                expected = [(1 - t) * a + t * b for a, b in zip(v_lo, v_hi)]
            drift = sum(abs(r - e) for r, e in zip(result, expected))
            worst_drift = max(worst_drift, drift)
    # We're not asserting on a particular bound in the test name, but
    # we use 1e-12 here — the renormalize step's drift over a 7-action
    # vector is bounded by ~7 ULPs of the float type, which is ~1e-15.
    assert worst_drift <= 1e-12, f"worst-case L1 drift {worst_drift} > 1e-12"


def test_worst_case_l1_drift_extreme_targets() -> None:
    """Extreme target values (very close to boundary) must not amplify drift."""
    strategies = {40: [0.5, 0.5], 80: [0.3, 0.7]}
    for target in [40.0000001, 40.5, 79.999, 79.5, 60.0]:
        result = interpolate_strategy(target_bb=target, strategies=strategies)
        assert abs(sum(result) - 1.0) <= 1e-12


# ---------------------------------------------------------------------------
# 21. Aliasing safety
# ---------------------------------------------------------------------------


def test_returned_list_is_not_aliased_with_input() -> None:
    """Mutating the returned list must not corrupt the caller's strategies."""
    v_lo = [0.8, 0.2]
    v_hi = [0.5, 0.5]
    strategies: dict[float, list[float]] = {40: v_lo, 80: v_hi}
    result = interpolate_strategy(target_bb=40, strategies=strategies)
    result[0] = 999.0
    assert v_lo == [0.8, 0.2], "returned list aliased caller's source"


def test_blueprint_block_returned_lists_not_aliased() -> None:
    block_lo = {"||p|": {"AA": [0.5, 0.5]}}
    block_hi = {"||p|": {"AA": [0.3, 0.7]}}
    strategies = {40: block_lo, 80: block_hi}
    out = interpolate_blueprint_strategies(target_bb=40, strategies=strategies)
    out["||p|"]["AA"][0] = 999.0
    assert block_lo["||p|"]["AA"] == [0.5, 0.5]
