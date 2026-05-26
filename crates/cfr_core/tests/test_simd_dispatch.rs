//! PR 61 (v1.8 Phase 1) — cross-platform SIMD dispatch parity test.
//!
//! Verifies that the public `simd::discount_regrets` / `simd::discount_strategy_sum`
//! dispatch (NEON on aarch64, SSE2 on x86_64, scalar elsewhere) produces
//! output that matches the explicit scalar reference for vector-shape
//! slices typical of `dcfr_vector.rs` (`hand_count × action_count`, which
//! for HUNL is `1326 × 3` ≈ 3978 f64 lanes).
//!
//! The in-source `simd::tests` module already covers small bit-exact
//! parity. This integration test covers a larger workload representative
//! of the actual DCFR vector-form hot path, plus odd-length tails.

use cfr_core::simd;

/// 1e-12 absolute tolerance: NEON & SSE2 paths are designed bit-exact
/// vs scalar (no FMA, no reordered sums in the discount kernel) so we'd
/// expect `== 0`, but we leave 1e-12 headroom for any future
/// architectural variation.
const TOL: f64 = 1e-12;

#[test]
fn discount_regrets_vector_matches_scalar() {
    // Mix of positives, negatives, zero, tiny values, and large magnitudes.
    let base: Vec<f64> = (0..3978)
        .map(|i| {
            let x = (i as f64) * 0.137 - 273.4;
            if i % 7 == 0 {
                0.0
            } else if i % 3 == 0 {
                -x
            } else {
                x
            }
        })
        .collect();

    let mut via_dispatch = base.clone();
    let mut via_scalar = base.clone();

    simd::discount_regrets(&mut via_dispatch, 0.51, 0.27);
    simd::discount_regrets_scalar(&mut via_scalar, 0.51, 0.27);

    for (i, (a, b)) in via_dispatch.iter().zip(via_scalar.iter()).enumerate() {
        assert!(
            (a - b).abs() < TOL,
            "lane {} diff: dispatch={} scalar={}",
            i,
            a,
            b
        );
    }
}

#[test]
fn discount_strategy_sum_vector_matches_scalar() {
    let base: Vec<f64> = (0..3978).map(|i| (i as f64).sin().abs() * 1000.0).collect();

    let mut via_dispatch = base.clone();
    let mut via_scalar = base.clone();

    simd::discount_strategy_sum(&mut via_dispatch, 0.875);
    simd::discount_strategy_sum_scalar(&mut via_scalar, 0.875);

    for (i, (a, b)) in via_dispatch.iter().zip(via_scalar.iter()).enumerate() {
        assert!(
            (a - b).abs() < TOL,
            "lane {} diff: dispatch={} scalar={}",
            i,
            a,
            b
        );
    }
}

/// Spec example from the PR description: short input, simple scale.
#[test]
fn discount_vector_matches_scalar() {
    let scalar = vec![1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0];
    let mut simd_buf = scalar.clone();
    let mut ref_scalar = scalar.clone();

    // discount_regrets with both positives: only `pos_scale` matters here.
    simd::discount_regrets(&mut simd_buf, 0.5, 0.5);
    simd::discount_regrets_scalar(&mut ref_scalar, 0.5, 0.5);

    for (a, b) in simd_buf.iter().zip(ref_scalar.iter()) {
        assert!((a - b).abs() < TOL, "SIMD vs scalar diff: {} vs {}", a, b);
    }
}

/// Odd lengths exercise the trailing-lane scalar tail in NEON / SSE2.
#[test]
fn discount_regrets_handles_odd_length_tails() {
    for len in [1, 2, 3, 5, 9, 17, 33, 1325, 1327] {
        let base: Vec<f64> = (0..len).map(|i| (i as f64) - (len as f64) * 0.5).collect();
        let mut via_dispatch = base.clone();
        let mut via_scalar = base.clone();

        simd::discount_regrets(&mut via_dispatch, 0.6, 0.4);
        simd::discount_regrets_scalar(&mut via_scalar, 0.6, 0.4);

        for i in 0..len {
            assert!(
                (via_dispatch[i] - via_scalar[i]).abs() < TOL,
                "len={} lane {} diff: dispatch={} scalar={}",
                len,
                i,
                via_dispatch[i],
                via_scalar[i]
            );
        }
    }
}

#[test]
fn discount_strategy_sum_handles_odd_length_tails() {
    for len in [1, 2, 3, 5, 9, 17, 33, 1325, 1327] {
        let base: Vec<f64> = (0..len).map(|i| (i as f64) * 0.1 + 1.0).collect();
        let mut via_dispatch = base.clone();
        let mut via_scalar = base.clone();

        simd::discount_strategy_sum(&mut via_dispatch, 0.75);
        simd::discount_strategy_sum_scalar(&mut via_scalar, 0.75);

        for i in 0..len {
            assert!(
                (via_dispatch[i] - via_scalar[i]).abs() < TOL,
                "len={} lane {} diff: dispatch={} scalar={}",
                len,
                i,
                via_dispatch[i],
                via_scalar[i]
            );
        }
    }
}
