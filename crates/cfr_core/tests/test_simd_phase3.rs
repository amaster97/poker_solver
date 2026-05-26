//! PR 70 (v1.8 Phase 3) — differential tests for the cross-platform
//! `update_strategy_sum` SIMD dispatch.
//!
//! Mirrors PR 61's `test_simd_dispatch.rs` shape: full-width DCFR HUNL
//! workload (1326 hands × 3 actions = 3978 lanes), spec example, full sweep
//! of lengths 0..=12 (exercises 4-lane main loop + 2-lane SSE2 epilogue +
//! 1-lane scalar tail on AVX2), and larger odd lengths (17, 33, 1325, 1327).
//! The dispatcher selects:
//!
//!   - NEON on aarch64 (Apple Silicon, compile-time)
//!   - AVX2 on x86_64 (runtime-detected via `is_x86_feature_detected!`)
//!   - SSE2 on x86_64 (baseline)
//!   - scalar otherwise
//!
//! All four paths must be bit-identical to the scalar reference on each
//! lane (two roundings: multiply then add, no FMA).

use cfr_core::simd::{update_strategy_sum, update_strategy_sum_scalar};

/// Build a deterministic strategy-sum + strategy + reach triple from a
/// linear-congruential RNG. f64 lanes intentionally span the typical
/// DCFR magnitudes (`strategy ∈ [0, 1]`, `reach ∈ [0, 1]`, `strategy_sum`
/// is a running positive accumulator).
fn build_inputs(len: usize, seed: u64) -> (Vec<f64>, Vec<f64>, f64) {
    let mut s = seed.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
    let mut next = || {
        s = s.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
        ((s >> 11) as f64) / ((1u64 << 53) as f64) // [0, 1)
    };
    let strategy: Vec<f64> = (0..len).map(|_| next()).collect();
    let strategy_sum: Vec<f64> = (0..len).map(|_| next() * 10.0).collect();
    let own_reach = next();
    (strategy_sum, strategy, own_reach)
}

#[test]
fn update_strategy_sum_full_hunl_preflop_width() {
    // 1326 unique HU starting-hand combos × 3 actions (fold/call/raise) =
    // 3978 lanes. This is the largest single-row workload the dispatcher
    // sees in real DCFR; it stresses the 2-/4-lane body in both SSE2 and
    // AVX2 paths.
    let len = 1326 * 3;
    let (mut a, st, reach) = build_inputs(len, 0x_DCFE_C0DE);
    let mut b = a.clone();
    update_strategy_sum(&mut a, &st, reach);
    update_strategy_sum_scalar(&mut b, &st, reach);
    for i in 0..len {
        assert_eq!(
            a[i].to_bits(),
            b[i].to_bits(),
            "lane {} differs (a={} b={})",
            i,
            a[i],
            b[i]
        );
    }
}

#[test]
fn update_strategy_sum_spec_example() {
    // Spec: `strategy_sum[i] += own_reach * strategy[i]`. Hand-computed
    // values for double-check.
    let st = vec![0.25, 0.5, 0.25];
    let mut a = vec![1.0, 2.0, 4.0];
    let own = 0.4;
    update_strategy_sum(&mut a, &st, own);
    // Expected: 1.0 + 0.4*0.25 = 1.1; 2.0 + 0.4*0.5 = 2.2; 4.0 + 0.4*0.25 = 4.1.
    assert!((a[0] - 1.1).abs() < 1e-15);
    assert!((a[1] - 2.2).abs() < 1e-15);
    assert!((a[2] - 4.1).abs() < 1e-15);
}

#[test]
fn update_strategy_sum_lengths_0_to_12_bit_exact() {
    // Full sweep 0..=12: covers the AVX2 4-lane main loop (≥4), the 2-lane
    // SSE2 epilogue (`n % 4 ∈ {2, 3}`), the 1-lane scalar tail (odd `n`),
    // and the empty-slice edge case (`n = 0` — must be a no-op). NEON
    // (aarch64) 2-lane body + 1-lane tail also fully covered. This is the
    // PR brief's mandatory edge-case sweep.
    for len in 0..=12 {
        let (mut a, st, reach) = build_inputs(len, 0x9E37_79B9_7F4A_7C15);
        let mut b = a.clone();
        update_strategy_sum(&mut a, &st, reach);
        update_strategy_sum_scalar(&mut b, &st, reach);
        for i in 0..len {
            assert_eq!(
                a[i].to_bits(),
                b[i].to_bits(),
                "len={} lane {} differs (a={} b={})",
                len,
                i,
                a[i],
                b[i]
            );
        }
    }
}

#[test]
fn update_strategy_sum_larger_odd_lengths_bit_exact() {
    // Additional larger sizes including the production HUNL widths
    // (1325/1327 frame either side of the 1326-combo preflop range).
    for &len in &[17usize, 33, 64, 128, 1024, 1325, 1326, 1327] {
        let (mut a, st, reach) = build_inputs(len, 0x9E37_79B9_7F4A_7C15);
        let mut b = a.clone();
        update_strategy_sum(&mut a, &st, reach);
        update_strategy_sum_scalar(&mut b, &st, reach);
        for i in 0..len {
            assert_eq!(
                a[i].to_bits(),
                b[i].to_bits(),
                "len={} lane {} differs (a={} b={})",
                len,
                i,
                a[i],
                b[i]
            );
        }
    }
}

#[test]
fn update_strategy_sum_zero_reach_is_identity() {
    // `own_reach = 0.0` must leave strategy_sum unchanged on every lane
    // (since the kernel computes `strategy_sum[i] += 0 * strategy[i]` =
    // `strategy_sum[i] += 0`).
    let len = 17;
    let (mut a, st, _) = build_inputs(len, 7);
    let before = a.clone();
    update_strategy_sum(&mut a, &st, 0.0);
    for i in 0..len {
        assert_eq!(
            a[i].to_bits(),
            before[i].to_bits(),
            "lane {} changed under zero reach",
            i
        );
    }
}

#[test]
fn update_strategy_sum_tolerance_1e_12_vs_scalar() {
    // Looser-tolerance check (per the task brief: 1e-12). The bit-exact
    // tests above are strictly tighter; this is the explicit numeric
    // guard requested by the PR brief.
    for &len in &[1usize, 2, 3, 4, 5, 7, 8, 9, 16, 17, 32, 33, 1024, 3978] {
        let (mut a, st, reach) = build_inputs(len, (len as u64).wrapping_mul(31));
        let mut b = a.clone();
        update_strategy_sum(&mut a, &st, reach);
        update_strategy_sum_scalar(&mut b, &st, reach);
        for i in 0..len {
            let d = (a[i] - b[i]).abs();
            assert!(
                d < 1e-12,
                "len={} lane {} diff {} exceeds 1e-12 (a={} b={})",
                len,
                i,
                d,
                a[i],
                b[i]
            );
        }
    }
}
