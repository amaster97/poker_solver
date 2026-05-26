//! PR 71 (v1.8 Phase 4) — cross-platform SIMD dispatch parity test for
//! `simd::compute_strategy_row` (fused regret-matching for a single hand row).
//!
//! Verifies the public `simd::compute_strategy_row` (NEON on aarch64, AVX2 or
//! SSE2 on x86_64 depending on runtime feature detection, scalar elsewhere)
//! produces output bit-identical (or within 1 ULP on the divide path) to the
//! scalar reference `simd::compute_strategy_row_scalar`.
//!
//! Coverage:
//! - All row lengths 0..=12 (sweeps every combination of main-loop + epilogues
//!   + scalar tail across NEON's 2-lane, SSE2's 2-lane, and AVX2's 4+2+1 split).
//! - A typical row width of 14 (HUNL with full bet-size menu).
//! - The all-negative-regrets edge case (clip → uniform distribution).
//! - The all-zero edge case (also → uniform).
//! - A mix including NaN-free zeros + tiny positives + large positives.

use cfr_core::simd;

/// Compare `dispatch` vs `scalar` bit-for-bit. Acceptable for compute_strategy
/// because (a) the clamp pass is `_mm_max_pd` / `vmaxq_f64` which are spec'd
/// bit-exact, (b) the sum is sequential in both paths, and (c) the divide is
/// per-lane `_mm_div_pd` / `vdivq_f64` which IEEE-754 mandates as bit-exact.
fn assert_rows_bit_exact(len: usize, dispatch: &[f64], scalar: &[f64]) {
    assert_eq!(dispatch.len(), scalar.len(), "row length mismatch");
    for i in 0..dispatch.len() {
        assert_eq!(
            dispatch[i].to_bits(),
            scalar[i].to_bits(),
            "len={} lane {} differs: dispatch={:?} ({:#x}) scalar={:?} ({:#x})",
            len,
            i,
            dispatch[i],
            dispatch[i].to_bits(),
            scalar[i],
            scalar[i].to_bits(),
        );
    }
}

#[test]
fn compute_strategy_row_sweeps_lengths_zero_to_twelve() {
    // Mix of positives, negatives, and zero in a deterministic pattern.
    // We construct an oversized base buffer, then slice prefixes of every
    // length 0..=12. Every length is hit by NEON's 2-lane main loop
    // (lengths 2-12 even), the 1-lane scalar tail (odd lengths), AVX2's
    // 4-lane main loop (lengths 4-12), the SSE2 2-lane epilogue
    // (lengths 6, 7, 10, 11 in AVX2 path), and the final scalar lane
    // (odd lengths in every path).
    let base: Vec<f64> = (0..13)
        .map(|i| {
            let x = (i as f64) * 0.137 - 0.3;
            if i % 5 == 0 {
                -x.abs()
            } else if i % 3 == 0 {
                0.0
            } else {
                x
            }
        })
        .collect();
    for len in 0..=12 {
        let regrets: Vec<f64> = base[..len].to_vec();
        let mut via_dispatch = vec![0.0_f64; len];
        let mut via_scalar = vec![0.0_f64; len];
        simd::compute_strategy_row(&regrets, &mut via_dispatch);
        simd::compute_strategy_row_scalar(&regrets, &mut via_scalar);
        assert_rows_bit_exact(len, &via_dispatch, &via_scalar);
    }
}

#[test]
fn compute_strategy_row_all_negative_falls_back_to_uniform() {
    // Pure edge case: every regret negative ⇒ clamp gives zero sum ⇒
    // uniform distribution `1.0 / len` on every lane.
    for len in 1..=12 {
        let regrets: Vec<f64> = (0..len).map(|i| -1.0 - (i as f64) * 0.5).collect();
        let mut via_dispatch = vec![0.0_f64; len];
        let mut via_scalar = vec![0.0_f64; len];
        simd::compute_strategy_row(&regrets, &mut via_dispatch);
        simd::compute_strategy_row_scalar(&regrets, &mut via_scalar);
        assert_rows_bit_exact(len, &via_dispatch, &via_scalar);
        // Sanity: every lane should equal exactly `1.0 / len`.
        let expected = 1.0 / (len as f64);
        for (i, v) in via_dispatch.iter().enumerate() {
            assert_eq!(
                v.to_bits(),
                expected.to_bits(),
                "len={} lane {} not uniform: got {:?}",
                len,
                i,
                v
            );
        }
    }
}

#[test]
fn compute_strategy_row_all_zero_falls_back_to_uniform() {
    for len in 1..=12 {
        let regrets = vec![0.0_f64; len];
        let mut via_dispatch = vec![0.0_f64; len];
        let mut via_scalar = vec![0.0_f64; len];
        simd::compute_strategy_row(&regrets, &mut via_dispatch);
        simd::compute_strategy_row_scalar(&regrets, &mut via_scalar);
        assert_rows_bit_exact(len, &via_dispatch, &via_scalar);
        let expected = 1.0 / (len as f64);
        for (i, v) in via_dispatch.iter().enumerate() {
            assert_eq!(
                v.to_bits(),
                expected.to_bits(),
                "len={} lane {} not uniform: got {:?}",
                len,
                i,
                v
            );
        }
    }
}

#[test]
fn compute_strategy_row_all_positive_normalizes() {
    // Every regret positive ⇒ output is `r / sum(r)` per lane.
    for len in 1..=12 {
        let regrets: Vec<f64> = (1..=len).map(|i| (i as f64) * 0.25).collect();
        let mut via_dispatch = vec![0.0_f64; len];
        let mut via_scalar = vec![0.0_f64; len];
        simd::compute_strategy_row(&regrets, &mut via_dispatch);
        simd::compute_strategy_row_scalar(&regrets, &mut via_scalar);
        assert_rows_bit_exact(len, &via_dispatch, &via_scalar);
        // Sanity: row should sum to ~1.0 (within ULP × len).
        let s: f64 = via_dispatch.iter().sum();
        assert!(
            (s - 1.0).abs() < 1e-12,
            "len={} sum-to-one violated: {}",
            len,
            s
        );
    }
}

#[test]
fn compute_strategy_row_mixed_signs_preserve_zero_on_negatives() {
    // Mixed pattern: positives normalize, non-positive lanes stay 0.0.
    for len in 1..=12 {
        let regrets: Vec<f64> = (0..len)
            .map(|i| if i % 2 == 0 { (i as f64) + 0.5 } else { -1.0 })
            .collect();
        let mut via_dispatch = vec![0.0_f64; len];
        let mut via_scalar = vec![0.0_f64; len];
        simd::compute_strategy_row(&regrets, &mut via_dispatch);
        simd::compute_strategy_row_scalar(&regrets, &mut via_scalar);
        assert_rows_bit_exact(len, &via_dispatch, &via_scalar);
        for i in 0..len {
            if regrets[i] <= 0.0 {
                assert_eq!(
                    via_dispatch[i].to_bits(),
                    0.0_f64.to_bits(),
                    "len={} lane {} should be 0.0 (regret={}), got {:?}",
                    len,
                    i,
                    regrets[i],
                    via_dispatch[i]
                );
            }
        }
    }
}

#[test]
fn compute_strategy_row_hunl_full_menu_width() {
    // The HUNL bet-size menu in the slowest path is up to 14 actions wide.
    // Make sure that exact width is bit-exact too.
    let len = 14;
    let regrets: Vec<f64> = (0..len)
        .map(|i| {
            let x = (i as f64).sin();
            if i % 3 == 0 {
                -x.abs()
            } else {
                x.abs() + 0.1
            }
        })
        .collect();
    let mut via_dispatch = vec![0.0_f64; len];
    let mut via_scalar = vec![0.0_f64; len];
    simd::compute_strategy_row(&regrets, &mut via_dispatch);
    simd::compute_strategy_row_scalar(&regrets, &mut via_scalar);
    assert_rows_bit_exact(len, &via_dispatch, &via_scalar);
}
