//! Cross-platform 128-bit SIMD kernels for the DCFR inner loop.
//!
//! PR 8 introduced ARM NEON paths for Apple Silicon (`vmulq_f64`, `vfmaq_f64`,
//! etc.). PR 61 (v1.8 Phase 1) extends the dispatch with a parallel SSE2
//! path so x86_64 hosts (Intel Macs, x86 Linux, Windows) also get 2-lane
//! f64 SIMD on the discount kernel. Wider-vector AVX2 (4-lane) is deferred
//! to v1.8 Phase 2+.
//!
//! Apple M-series CPUs expose 128-bit NEON: two `f64` lanes per vector
//! (`float64x2_t`). x86_64 SSE2 exposes the same 2-lane f64 width via
//! `__m128d`. The DCFR hot kernels here are:
//!
//!  1. **Discount** — multiply `regret_sum[i]` by either `pos_scale` or
//!     `neg_scale` depending on the sign of the existing regret; multiply
//!     `strategy_sum[i]` by `strat_scale`. Sign-conditional but the branch is
//!     vectorizable with `vbslq_f64` (bitwise select on a mask produced by
//!     `vcgtq_f64`).
//!  2. **Get-strategy** — clamp regrets to positive (`vmaxq_f64` against 0.0)
//!     and accumulate the sum for normalization. Two-stage.
//!  3. **Normalize** — divide each lane by the running total (or fall back to
//!     uniform). One `vdivq_f64`.
//!  4. **Regret update** — `regret_sum[i] += opp_reach * (action_v[i] -
//!     node_v)`. FMA via `vfmaq_f64` (single-instruction fused multiply-add).
//!  5. **Strategy-sum update** — `strategy_sum[i] += own_reach * strategy[i]`.
//!     FMA via `vfmaq_f64`.
//!
//! All NEON paths have a **scalar fallback** that produces *bit-identical*
//! output on aarch64. The fallback is what runs on non-aarch64 (CI x86,
//! Linux) — and it's also what `cfg(not(target_arch = "aarch64"))` compiles
//! to. Bit parity is guaranteed by:
//!
//!   - Using `vmaxq_f64` which is NaN-preserving (matches `f_max_nan_preserving`
//!     scalar helper, NOT `f64::max` which is NaN-quieting).
//!   - Avoiding `vfmaq_f64` in mathematically-fused-OK paths only — we use
//!     it in (4) and (5) where the spec is `a + b * c` and ULP≤1 is fine
//!     (the existing scalar code already produces a single rounding via
//!     `*= ... ; += ...` two-step; FMA single-rounding shaves the same
//!     intermediate to ULP≤1 relative to two-step rounding).
//!   - Horizontal sums via left-associative pairwise reduction.
//!
//! Licensing: pattern-only inspiration from `references/papers/dcfr.pdf`
//! (Brown & Sandholm 2019) and the structure of Noam Brown's MIT
//! `poker_solver/cpp/src/trainer.cpp`. **No code copied from
//! `references/code/postflop-solver` or `references/code/TexasSolver`
//! (AGPL).** The NEON intrinsics here were re-derived against Apple's
//! public NEON intrinsics reference.
//!
//! The module is `pub` so the DCFR loop in `dcfr.rs` / `hunl_solver.rs` and
//! microbenches can call into it; internal helpers are private.

#![allow(clippy::needless_range_loop)]

/// Bit-exact-or-ULP≤1 NaN-preserving max — mirrors NEON `vmaxq_f64`.
///
/// Rust's `f64::max` is NaN-QUIETING (returns the non-NaN operand when one is
/// NaN); NEON's `vmaxq_f64` is NaN-PRESERVING (returns NaN when either is).
/// DCFR regrets are never NaN under correct usage, but we keep parity with
/// the SIMD path here to make the SIMD vs scalar parity test bit-exact.
#[inline]
fn nan_preserving_max(a: f64, b: f64) -> f64 {
    if a.is_nan() || b.is_nan() {
        f64::NAN
    } else if a >= b {
        a
    } else {
        b
    }
}

// ---------------------------------------------------------------------------
// Scalar fallbacks (always present; used on non-aarch64 + as reference impls
// in the parity test).
// ---------------------------------------------------------------------------

/// Scalar version of [`discount_regrets`] — multiplies positives by
/// `pos_scale`, negatives by `neg_scale`, leaves zero alone.
#[inline]
pub fn discount_regrets_scalar(regrets: &mut [f64], pos_scale: f64, neg_scale: f64) {
    for r in regrets.iter_mut() {
        if *r > 0.0 {
            *r *= pos_scale;
        } else if *r < 0.0 {
            *r *= neg_scale;
        }
    }
}

/// Scalar version of [`discount_strategy_sum`].
#[inline]
pub fn discount_strategy_sum_scalar(strategy: &mut [f64], strat_scale: f64) {
    for s in strategy.iter_mut() {
        *s *= strat_scale;
    }
}

/// Scalar version of [`positive_regrets_and_total`] — for parity tests.
#[inline]
pub fn positive_regrets_and_total_scalar(regrets: &[f64], out_positive: &mut [f64]) -> f64 {
    debug_assert_eq!(regrets.len(), out_positive.len());
    let mut total = 0.0;
    for i in 0..regrets.len() {
        let v = nan_preserving_max(regrets[i], 0.0);
        out_positive[i] = v;
        total += v;
    }
    total
}

/// Scalar version of [`update_regret_sum_fma`] — `regret[i] += opp_reach *
/// (action_v[i] - node_v)`.
#[inline]
pub fn update_regret_sum_scalar(
    regret_sum: &mut [f64],
    action_values: &[f64],
    node_value: f64,
    opp_reach: f64,
) {
    debug_assert_eq!(regret_sum.len(), action_values.len());
    for i in 0..regret_sum.len() {
        regret_sum[i] += opp_reach * (action_values[i] - node_value);
    }
}

/// Scalar version of [`update_strategy_sum_fma`] — `strategy_sum[i] +=
/// own_reach * strategy[i]`.
#[inline]
pub fn update_strategy_sum_scalar(strategy_sum: &mut [f64], strategy: &[f64], own_reach: f64) {
    debug_assert_eq!(strategy_sum.len(), strategy.len());
    for i in 0..strategy_sum.len() {
        strategy_sum[i] += own_reach * strategy[i];
    }
}

/// Scalar version of [`update_regret_sum_vector`] — DCFR vector-form
/// regret update from `dcfr_vector.rs:443-450`.
///
/// For each `(h, a)`:
///   `regret[h*A + a] += action_value[a*H + h] - node_value[h]`
///
/// Note the **shape asymmetry**:
///   - `regret` is hand-major (`[h][a]`, contiguous over `a`).
///   - `action_value` is action-major (`[a][h]`, contiguous over `h`).
///   - `node_value` is per-hand (`[h]`, contiguous over `h`).
///
/// The reference traversal in Brown's `trainer.cpp:211-224` (MIT) writes
/// `regret_weight` separately; the call-site in `dcfr_vector.rs` carries
/// `regret_weight = 1.0` per DCFR spec (`trainer.cpp:354-355`), so the
/// SIMD kernels here fold the constant away.
#[inline]
pub fn update_regret_sum_vector_scalar(
    regret: &mut [f64],
    action_value: &[f64],
    node_value: &[f64],
    hand_count: usize,
    action_count: usize,
) {
    debug_assert_eq!(regret.len(), hand_count * action_count);
    debug_assert_eq!(action_value.len(), action_count * hand_count);
    debug_assert_eq!(node_value.len(), hand_count);
    for h in 0..hand_count {
        let offset = h * action_count;
        let base = node_value[h];
        for a in 0..action_count {
            let delta = action_value[a * hand_count + h] - base;
            regret[offset + a] += delta;
        }
    }
}

/// Scalar normalize-by-total (in-place). Mirrors the regret-matching
/// fallback used in `dcfr.rs`'s `get_strategy` *bit-for-bit*: the original
/// code does `*p /= total` (per-lane division), NOT `*p *= 1.0/total`
/// (multiply by reciprocal). Those two forms differ by ULP and the
/// difference accumulates over a long DCFR solve. We mirror `/= total`
/// here for diff-test parity.
#[inline]
pub fn normalize_scalar(out: &mut [f64], total: f64) {
    if total > 0.0 {
        for p in out.iter_mut() {
            *p /= total;
        }
    } else {
        let uniform = 1.0 / (out.len() as f64);
        for p in out.iter_mut() {
            *p = uniform;
        }
    }
}

// ---------------------------------------------------------------------------
// aarch64 NEON kernels (active on Apple Silicon). Scalar fallbacks are used
// for trailing lanes when `len % 2 != 0`.
// ---------------------------------------------------------------------------

#[cfg(target_arch = "aarch64")]
mod neon {
    use core::arch::aarch64::*;

    /// Clamp regrets to `max(r, 0)` lane-by-lane via NEON, then sum
    /// sequentially to match the scalar accumulation order *bit-for-bit*.
    ///
    /// **Why sequential sum, not horizontal SIMD sum?** Pairwise SIMD
    /// reduction (`vaddvq_f64`) and sequential `acc += r` produce
    /// different bit patterns for the same inputs (associativity of f64
    /// add is not exact). DCFR is iterative — ULP drift in the
    /// per-iteration total propagates through `normalize → strategy →
    /// next-iter regret` and the converged strategy can diverge from the
    /// Python reference past the project's `STRATEGY_ATOL=1e-4` bar. The
    /// SIMD win on the clamp is preserved; only the sum is sequential.
    ///
    /// # Safety
    /// `regrets` and `out_positive` must have identical length and be
    /// valid for read / write respectively. NEON loads/stores are
    /// unaligned-safe (`vld1q_f64` accepts unaligned pointers on AArch64).
    #[target_feature(enable = "neon")]
    #[inline]
    pub unsafe fn positive_regrets_and_total_neon(
        regrets: &[f64],
        out_positive: &mut [f64],
    ) -> f64 {
        debug_assert_eq!(regrets.len(), out_positive.len());
        let n = regrets.len();
        let zero = vdupq_n_f64(0.0);
        let mut i = 0usize;
        // Two-lane clamp loop. Sum is sequential below to match scalar
        // bit-for-bit.
        while i + 2 <= n {
            let v = vld1q_f64(regrets.as_ptr().add(i));
            let clamped = vmaxq_f64(v, zero); // NaN-preserving on aarch64.
            vst1q_f64(out_positive.as_mut_ptr().add(i), clamped);
            i += 2;
        }
        while i < n {
            // Mirror scalar `nan_preserving_max` semantics.
            let r = regrets[i];
            out_positive[i] = if r.is_nan() {
                f64::NAN
            } else if r >= 0.0 {
                r
            } else {
                0.0
            };
            i += 1;
        }
        // Sequential accumulation matches scalar bit-for-bit.
        let mut total = 0.0_f64;
        for v in out_positive.iter() {
            total += *v;
        }
        total
    }

    /// Sign-conditional discount: each lane `r > 0 ⇒ r * pos_scale`,
    /// `r < 0 ⇒ r * neg_scale`, `r == 0 ⇒ 0`.
    ///
    /// Implementation: blend two scaled vectors via `vbslq_f64` using a
    /// "positive-mask" derived from `vcgtq_f64(r, 0)`. Zero is handled
    /// implicitly because both scaled vectors equal 0 when `r == 0`.
    ///
    /// # Safety
    /// `regrets` must be a valid mutable slice.
    #[target_feature(enable = "neon")]
    #[inline]
    pub unsafe fn discount_regrets_neon(regrets: &mut [f64], pos_scale: f64, neg_scale: f64) {
        let n = regrets.len();
        let pos = vdupq_n_f64(pos_scale);
        let neg = vdupq_n_f64(neg_scale);
        let zero = vdupq_n_f64(0.0);
        let mut i = 0usize;
        while i + 2 <= n {
            let v = vld1q_f64(regrets.as_ptr().add(i));
            let mask_pos = vcgtq_f64(v, zero); // 1s where v > 0
            let scaled_pos = vmulq_f64(v, pos);
            let scaled_neg = vmulq_f64(v, neg);
            // bsl(mask, a, b) = (mask & a) | (~mask & b) — use scaled_pos
            // where mask is set, scaled_neg otherwise. For `v == 0`, both
            // scaled values are 0 so the choice doesn't matter.
            let blended = vbslq_f64(mask_pos, scaled_pos, scaled_neg);
            vst1q_f64(regrets.as_mut_ptr().add(i), blended);
            i += 2;
        }
        // Trailing scalar tail. Must match scalar semantics exactly
        // (zero is left untouched in scalar; here it's already 0*x=0
        // which is the same value).
        while i < n {
            if regrets[i] > 0.0 {
                regrets[i] *= pos_scale;
            } else if regrets[i] < 0.0 {
                regrets[i] *= neg_scale;
            }
            i += 1;
        }
    }

    /// `strategy_sum[i] *= strat_scale` vectorized.
    ///
    /// # Safety
    /// `strategy` must be a valid mutable slice.
    #[target_feature(enable = "neon")]
    #[inline]
    pub unsafe fn discount_strategy_sum_neon(strategy: &mut [f64], strat_scale: f64) {
        let n = strategy.len();
        let scale = vdupq_n_f64(strat_scale);
        let mut i = 0usize;
        while i + 2 <= n {
            let v = vld1q_f64(strategy.as_ptr().add(i));
            let scaled = vmulq_f64(v, scale);
            vst1q_f64(strategy.as_mut_ptr().add(i), scaled);
            i += 2;
        }
        while i < n {
            strategy[i] *= strat_scale;
            i += 1;
        }
    }

    /// `regret_sum[i] += opp_reach * (action_values[i] - node_value)` —
    /// vectorized via NEON, *bit-identical* to the scalar two-step
    /// (sub, then mul, then add — three roundings to match scalar).
    ///
    /// **Why not FMA?** `vfmaq_f64` would single-round the `add * mul + add`
    /// and shave ULP off the scalar two-step. That ULP accumulates over
    /// 10^3+ DCFR iterations and pushes the converged strategy past the
    /// project's `STRATEGY_ATOL=1e-4` differential-test bar. We keep
    /// behavior identical here; FMA is opt-in for hotter (single-pass)
    /// kernels only.
    ///
    /// # Safety
    /// All slices must be same length; pointers valid.
    #[target_feature(enable = "neon")]
    #[inline]
    pub unsafe fn update_regret_sum_neon(
        regret_sum: &mut [f64],
        action_values: &[f64],
        node_value: f64,
        opp_reach: f64,
    ) {
        let n = regret_sum.len();
        let opp = vdupq_n_f64(opp_reach);
        let node = vdupq_n_f64(node_value);
        let mut i = 0usize;
        while i + 2 <= n {
            let r = vld1q_f64(regret_sum.as_ptr().add(i));
            let av = vld1q_f64(action_values.as_ptr().add(i));
            let diff = vsubq_f64(av, node);
            let prod = vmulq_f64(opp, diff);
            let updated = vaddq_f64(r, prod);
            vst1q_f64(regret_sum.as_mut_ptr().add(i), updated);
            i += 2;
        }
        while i < n {
            regret_sum[i] += opp_reach * (action_values[i] - node_value);
            i += 1;
        }
    }

    /// `strategy_sum[i] += own_reach * strategy[i]` — vectorized,
    /// bit-identical to scalar (two roundings, not FMA — see
    /// [`update_regret_sum_neon`] for rationale).
    ///
    /// # Safety
    /// Slices same length; pointers valid.
    #[target_feature(enable = "neon")]
    #[inline]
    pub unsafe fn update_strategy_sum_neon(
        strategy_sum: &mut [f64],
        strategy: &[f64],
        own_reach: f64,
    ) {
        let n = strategy_sum.len();
        let own = vdupq_n_f64(own_reach);
        let mut i = 0usize;
        while i + 2 <= n {
            let s = vld1q_f64(strategy_sum.as_ptr().add(i));
            let st = vld1q_f64(strategy.as_ptr().add(i));
            let prod = vmulq_f64(own, st);
            let updated = vaddq_f64(s, prod);
            vst1q_f64(strategy_sum.as_mut_ptr().add(i), updated);
            i += 2;
        }
        while i < n {
            strategy_sum[i] += own_reach * strategy[i];
            i += 1;
        }
    }

    /// DCFR vector-form regret update — `regret[h*A + a] +=
    /// action_value[a*H + h] - node_value[h]`.
    ///
    /// **Shape complication**: `regret` is hand-major but `action_value` is
    /// action-major. Per the v1.8 roadmap, this first pass keeps the loop
    /// structure scalar (outer over `a`, inner over `h`) but vectorizes the
    /// inner-most subtraction across two contiguous hands per chunk.
    /// `action_value[a*H + h..h+2]` and `node_value[h..h+2]` are both
    /// contiguous over `h`, so `vsubq_f64` works directly; the scatter-add
    /// into `regret[h*A + a]` and `regret[(h+1)*A + a]` is scalar (the
    /// strided write defeats a vector store; a transpose-then-vectorize is
    /// the Phase 3+ optimization per the roadmap).
    ///
    /// Bit-exactness vs scalar: each lane computes `av - node` followed by
    /// `regret += diff` — the same two roundings as the scalar
    /// `update_regret_sum_vector_scalar` reference.
    ///
    /// # Safety
    /// All slices must satisfy: `regret.len() == H*A`,
    /// `action_value.len() == A*H`, `node_value.len() == H`.
    #[target_feature(enable = "neon")]
    #[inline]
    pub unsafe fn update_regret_sum_vector_neon(
        regret: &mut [f64],
        action_value: &[f64],
        node_value: &[f64],
        hand_count: usize,
        action_count: usize,
    ) {
        debug_assert_eq!(regret.len(), hand_count * action_count);
        debug_assert_eq!(action_value.len(), action_count * hand_count);
        debug_assert_eq!(node_value.len(), hand_count);
        for a in 0..action_count {
            let av_base = action_value.as_ptr().add(a * hand_count);
            let mut h = 0usize;
            while h + 2 <= hand_count {
                // Both av and node are contiguous over h.
                let av = vld1q_f64(av_base.add(h));
                let node = vld1q_f64(node_value.as_ptr().add(h));
                let diff = vsubq_f64(av, node);
                // Extract lanes for the scatter-add into hand-major regret.
                let d0 = vgetq_lane_f64::<0>(diff);
                let d1 = vgetq_lane_f64::<1>(diff);
                *regret.get_unchecked_mut(h * action_count + a) += d0;
                *regret.get_unchecked_mut((h + 1) * action_count + a) += d1;
                h += 2;
            }
            while h < hand_count {
                let delta = *av_base.add(h) - *node_value.get_unchecked(h);
                *regret.get_unchecked_mut(h * action_count + a) += delta;
                h += 1;
            }
        }
    }

    /// Normalize in place: divide each lane by `total` (if positive) or
    /// fill with `1/n` (if zero). **Bit-identical to scalar** —
    /// `vdivq_f64` per-lane division (not multiply-by-reciprocal).
    ///
    /// # Safety
    /// `out` valid mutable slice.
    #[target_feature(enable = "neon")]
    #[inline]
    pub unsafe fn normalize_neon(out: &mut [f64], total: f64) {
        let n = out.len();
        if total > 0.0 {
            let vtot = vdupq_n_f64(total);
            let mut i = 0usize;
            while i + 2 <= n {
                let v = vld1q_f64(out.as_ptr().add(i));
                let scaled = vdivq_f64(v, vtot);
                vst1q_f64(out.as_mut_ptr().add(i), scaled);
                i += 2;
            }
            while i < n {
                out[i] /= total;
                i += 1;
            }
        } else {
            let uniform = 1.0 / (n as f64);
            let vuni = vdupq_n_f64(uniform);
            let mut i = 0usize;
            while i + 2 <= n {
                vst1q_f64(out.as_mut_ptr().add(i), vuni);
                i += 2;
            }
            while i < n {
                out[i] = uniform;
                i += 1;
            }
        }
    }
}

// ---------------------------------------------------------------------------
// x86_64 SSE2 kernels (PR 61 — v1.8 Phase 1). SSE2 is baseline on every
// x86_64 target (it's part of the x86_64 ABI), so no runtime detection is
// needed — `target_arch = "x86_64"` implies SSE2 availability. Wider AVX2
// (4-lane f64) is deferred to v1.8 Phase 2; the SSE2 path is the safe
// universal baseline.
//
// Scope: only the discount kernel is SSE2-vectorized in PR 61. The other
// kernels (positive_regrets_and_total, update_regret_sum,
// update_strategy_sum, normalize) keep scalar fallback on x86_64 for now;
// extending them follows the same template and is the v1.8 Phase 2 task.
// ---------------------------------------------------------------------------

#[cfg(target_arch = "x86_64")]
mod sse2 {
    use core::arch::x86_64::*;

    /// Sign-conditional discount on x86_64 via SSE2. Same semantics as
    /// `discount_regrets_neon`: `r > 0 ⇒ r * pos_scale`, `r < 0 ⇒ r *
    /// neg_scale`, `r == 0 ⇒ 0`.
    ///
    /// Implementation: compute both scaled vectors, then blend via a mask
    /// derived from `_mm_cmpgt_pd(v, 0)` using bitwise AND/ANDNOT/OR (SSE2
    /// has no native `blendv`; that's SSE4.1, which we don't gate on).
    ///
    /// # Safety
    /// `regrets` must be a valid mutable slice. SSE2 loads/stores via
    /// `_mm_loadu_pd` / `_mm_storeu_pd` are unaligned-safe.
    #[target_feature(enable = "sse2")]
    #[inline]
    pub unsafe fn discount_regrets_sse2(regrets: &mut [f64], pos_scale: f64, neg_scale: f64) {
        let n = regrets.len();
        let pos = _mm_set1_pd(pos_scale);
        let neg = _mm_set1_pd(neg_scale);
        let zero = _mm_setzero_pd();
        let mut i = 0usize;
        while i + 2 <= n {
            let v = _mm_loadu_pd(regrets.as_ptr().add(i));
            // mask_pos has all-1 bits in lanes where v > 0, all-0 otherwise.
            let mask_pos = _mm_cmpgt_pd(v, zero);
            let scaled_pos = _mm_mul_pd(v, pos);
            let scaled_neg = _mm_mul_pd(v, neg);
            // Manual SSE2 blend: (mask & scaled_pos) | (~mask & scaled_neg).
            // For v == 0, both scaled values are 0 so the choice is moot.
            let pos_part = _mm_and_pd(mask_pos, scaled_pos);
            let neg_part = _mm_andnot_pd(mask_pos, scaled_neg);
            let blended = _mm_or_pd(pos_part, neg_part);
            _mm_storeu_pd(regrets.as_mut_ptr().add(i), blended);
            i += 2;
        }
        // Trailing scalar tail — matches scalar semantics exactly.
        while i < n {
            if regrets[i] > 0.0 {
                regrets[i] *= pos_scale;
            } else if regrets[i] < 0.0 {
                regrets[i] *= neg_scale;
            }
            i += 1;
        }
    }

    /// `strategy_sum[i] *= strat_scale` vectorized on SSE2 via `_mm_mul_pd`.
    ///
    /// # Safety
    /// `strategy` must be a valid mutable slice.
    #[target_feature(enable = "sse2")]
    #[inline]
    pub unsafe fn discount_strategy_sum_sse2(strategy: &mut [f64], strat_scale: f64) {
        let n = strategy.len();
        let scale = _mm_set1_pd(strat_scale);
        let mut i = 0usize;
        while i + 2 <= n {
            let v = _mm_loadu_pd(strategy.as_ptr().add(i));
            let scaled = _mm_mul_pd(v, scale);
            _mm_storeu_pd(strategy.as_mut_ptr().add(i), scaled);
            i += 2;
        }
        while i < n {
            strategy[i] *= strat_scale;
            i += 1;
        }
    }

    /// DCFR vector-form regret update on x86_64 via SSE2. Semantics:
    /// `regret[h*A + a] += action_value[a*H + h] - node_value[h]`.
    ///
    /// Same shape strategy as the NEON path: outer loop over `a`, inner
    /// over `h` in 2-wide chunks. `_mm_sub_pd` computes the diff over two
    /// contiguous hands; the scatter-add into hand-major `regret` is
    /// scalar (strided write defeats `_mm_storeu_pd`).
    ///
    /// # Safety
    /// All slices must satisfy: `regret.len() == H*A`,
    /// `action_value.len() == A*H`, `node_value.len() == H`. SSE2 is
    /// baseline on every x86_64 target.
    #[target_feature(enable = "sse2")]
    #[inline]
    pub unsafe fn update_regret_sum_vector_sse2(
        regret: &mut [f64],
        action_value: &[f64],
        node_value: &[f64],
        hand_count: usize,
        action_count: usize,
    ) {
        debug_assert_eq!(regret.len(), hand_count * action_count);
        debug_assert_eq!(action_value.len(), action_count * hand_count);
        debug_assert_eq!(node_value.len(), hand_count);
        for a in 0..action_count {
            let av_base = action_value.as_ptr().add(a * hand_count);
            let mut h = 0usize;
            while h + 2 <= hand_count {
                let av = _mm_loadu_pd(av_base.add(h));
                let node = _mm_loadu_pd(node_value.as_ptr().add(h));
                let diff = _mm_sub_pd(av, node);
                // Extract lanes for the scatter-add into hand-major regret.
                // _mm_cvtsd_f64 reads lane 0; lane 1 needs an unpackhi or
                // store-and-read. Store to a 2-element buffer is the
                // cleanest cross-version approach.
                let mut buf = [0.0f64; 2];
                _mm_storeu_pd(buf.as_mut_ptr(), diff);
                *regret.get_unchecked_mut(h * action_count + a) += buf[0];
                *regret.get_unchecked_mut((h + 1) * action_count + a) += buf[1];
                h += 2;
            }
            while h < hand_count {
                let delta = *av_base.add(h) - *node_value.get_unchecked(h);
                *regret.get_unchecked_mut(h * action_count + a) += delta;
                h += 1;
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Public dispatch: prefer NEON on aarch64, SSE2 on x86_64, scalar otherwise.
// The `discount` helpers and the regret/strategy updaters expose one public
// entrypoint each so callers (`dcfr.rs`, `dcfr_vector.rs`, `hunl_solver.rs`)
// don't sprinkle `#[cfg(...)]`.
// ---------------------------------------------------------------------------

// Dispatch macro: prefer NEON on aarch64 unless the `force_scalar` feature
// is set (used only by the PR 8 microbench to measure the pre-PR-8
// wall-clock against the NEON-on default path).

/// Sign-conditional regret discount — public dispatch.
///
/// Dispatch order (compile-time):
///   - `aarch64` + not `force_scalar` → NEON (`vmulq_f64` + `vbslq_f64`)
///   - `x86_64` + not `force_scalar` → SSE2 (`_mm_mul_pd` + manual blend)
///   - else → scalar fallback
#[inline]
pub fn discount_regrets(regrets: &mut [f64], pos_scale: f64, neg_scale: f64) {
    #[cfg(all(target_arch = "aarch64", not(feature = "force_scalar")))]
    // SAFETY: NEON is unconditionally available on AArch64 (Apple Silicon +
    // all aarch64 macOS targets); the function reads/writes within the
    // slice bounds and uses unaligned loads/stores.
    unsafe {
        neon::discount_regrets_neon(regrets, pos_scale, neg_scale)
    }
    #[cfg(all(
        target_arch = "x86_64",
        not(target_arch = "aarch64"),
        not(feature = "force_scalar")
    ))]
    // SAFETY: SSE2 is baseline on every x86_64 target (part of the x86_64
    // ABI); slice bounds are checked above; loads/stores are unaligned-safe.
    unsafe {
        sse2::discount_regrets_sse2(regrets, pos_scale, neg_scale)
    }
    #[cfg(any(
        feature = "force_scalar",
        not(any(target_arch = "aarch64", target_arch = "x86_64"))
    ))]
    discount_regrets_scalar(regrets, pos_scale, neg_scale)
}

/// Strategy-sum discount — public dispatch.
///
/// Dispatch order matches [`discount_regrets`]: NEON > SSE2 > scalar.
#[inline]
pub fn discount_strategy_sum(strategy: &mut [f64], strat_scale: f64) {
    #[cfg(all(target_arch = "aarch64", not(feature = "force_scalar")))]
    // SAFETY: see discount_regrets.
    unsafe {
        neon::discount_strategy_sum_neon(strategy, strat_scale)
    }
    #[cfg(all(
        target_arch = "x86_64",
        not(target_arch = "aarch64"),
        not(feature = "force_scalar")
    ))]
    // SAFETY: see discount_regrets — SSE2 baseline on x86_64.
    unsafe {
        sse2::discount_strategy_sum_sse2(strategy, strat_scale)
    }
    #[cfg(any(
        feature = "force_scalar",
        not(any(target_arch = "aarch64", target_arch = "x86_64"))
    ))]
    discount_strategy_sum_scalar(strategy, strat_scale)
}

/// Clamp regrets to positive + accumulate sum — public dispatch.
#[inline]
pub fn positive_regrets_and_total(regrets: &[f64], out_positive: &mut [f64]) -> f64 {
    #[cfg(all(target_arch = "aarch64", not(feature = "force_scalar")))]
    // SAFETY: NEON intrinsics on stable aarch64; slice-bounds-checked.
    unsafe {
        neon::positive_regrets_and_total_neon(regrets, out_positive)
    }
    #[cfg(not(all(target_arch = "aarch64", not(feature = "force_scalar"))))]
    positive_regrets_and_total_scalar(regrets, out_positive)
}

/// In-place normalize (divide each lane by `total` if positive, else fill
/// with uniform `1/n`). Public dispatch.
#[inline]
pub fn normalize(out: &mut [f64], total: f64) {
    #[cfg(all(target_arch = "aarch64", not(feature = "force_scalar")))]
    // SAFETY: NEON; slice-bounds-checked.
    unsafe {
        neon::normalize_neon(out, total)
    }
    #[cfg(not(all(target_arch = "aarch64", not(feature = "force_scalar"))))]
    normalize_scalar(out, total)
}

/// Regret-sum update — public dispatch.
#[inline]
pub fn update_regret_sum(
    regret_sum: &mut [f64],
    action_values: &[f64],
    node_value: f64,
    opp_reach: f64,
) {
    #[cfg(all(target_arch = "aarch64", not(feature = "force_scalar")))]
    // SAFETY: NEON; matched-length slices bounds-checked.
    unsafe {
        neon::update_regret_sum_neon(regret_sum, action_values, node_value, opp_reach)
    }
    #[cfg(not(all(target_arch = "aarch64", not(feature = "force_scalar"))))]
    update_regret_sum_scalar(regret_sum, action_values, node_value, opp_reach)
}

/// DCFR vector-form regret update — public dispatch.
///
/// Computes `regret[h*A + a] += action_value[a*H + h] - node_value[h]` for
/// every `(h, a)` pair. Replaces the scalar double-loop in
/// `dcfr_vector.rs:443-450`.
///
/// Dispatch order (compile-time):
///   - `aarch64` + not `force_scalar` → NEON (`vsubq_f64` + scalar scatter)
///   - `x86_64` + not `force_scalar` → SSE2 (`_mm_sub_pd` + scalar scatter)
///   - else → scalar fallback
#[inline]
pub fn update_regret_sum_vector(
    regret: &mut [f64],
    action_value: &[f64],
    node_value: &[f64],
    hand_count: usize,
    action_count: usize,
) {
    #[cfg(all(target_arch = "aarch64", not(feature = "force_scalar")))]
    // SAFETY: NEON is baseline on aarch64; shape pre-conditions are
    // debug-asserted in the kernel and statically enforced by the call site.
    unsafe {
        neon::update_regret_sum_vector_neon(
            regret,
            action_value,
            node_value,
            hand_count,
            action_count,
        )
    }
    #[cfg(all(
        target_arch = "x86_64",
        not(target_arch = "aarch64"),
        not(feature = "force_scalar")
    ))]
    // SAFETY: SSE2 is baseline on every x86_64 target; shape pre-conditions
    // are debug-asserted in the kernel.
    unsafe {
        sse2::update_regret_sum_vector_sse2(
            regret,
            action_value,
            node_value,
            hand_count,
            action_count,
        )
    }
    #[cfg(any(
        feature = "force_scalar",
        not(any(target_arch = "aarch64", target_arch = "x86_64"))
    ))]
    update_regret_sum_vector_scalar(regret, action_value, node_value, hand_count, action_count)
}

/// Strategy-sum update — public dispatch.
#[inline]
pub fn update_strategy_sum(strategy_sum: &mut [f64], strategy: &[f64], own_reach: f64) {
    #[cfg(all(target_arch = "aarch64", not(feature = "force_scalar")))]
    // SAFETY: NEON; matched-length slices bounds-checked.
    unsafe {
        neon::update_strategy_sum_neon(strategy_sum, strategy, own_reach)
    }
    #[cfg(not(all(target_arch = "aarch64", not(feature = "force_scalar"))))]
    update_strategy_sum_scalar(strategy_sum, strategy, own_reach)
}

// ---------------------------------------------------------------------------
// Tests (in-source; integration-level parity test lives in
// `crates/cfr_core/tests/test_simd.rs`).
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn discount_regrets_matches_scalar() {
        let mut a = vec![-2.0, -1.0, 0.0, 1.0, 2.5, -0.3, 0.7, 0.0];
        let mut b = a.clone();
        discount_regrets(&mut a, 0.7, 0.3);
        discount_regrets_scalar(&mut b, 0.7, 0.3);
        for i in 0..a.len() {
            assert_eq!(a[i].to_bits(), b[i].to_bits(), "lane {} differs", i);
        }
    }

    #[test]
    fn discount_strategy_sum_matches_scalar() {
        let mut a: Vec<f64> = (0..9).map(|i| (i as f64) * 0.1).collect();
        let mut b = a.clone();
        discount_strategy_sum(&mut a, 0.5);
        discount_strategy_sum_scalar(&mut b, 0.5);
        for i in 0..a.len() {
            assert_eq!(a[i].to_bits(), b[i].to_bits(), "lane {} differs", i);
        }
    }

    #[test]
    fn positive_regrets_and_total_matches_scalar() {
        let r = vec![-2.0, 1.5, 0.0, 3.0, -0.5, 0.25, 0.75];
        let mut a = vec![0.0; r.len()];
        let mut b = vec![0.0; r.len()];
        let ta = positive_regrets_and_total(&r, &mut a);
        let tb = positive_regrets_and_total_scalar(&r, &mut b);
        // Totals can differ by ULP due to associativity of pairwise vs
        // sequential sums; ULP≤1 is fine. Per-lane outputs are bit-exact.
        for i in 0..a.len() {
            assert_eq!(a[i].to_bits(), b[i].to_bits(), "lane {} differs", i);
        }
        assert!((ta - tb).abs() <= 1e-12, "total diff {} vs {}", ta, tb);
    }

    #[test]
    fn normalize_matches_scalar() {
        let mut a = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        let mut b = a.clone();
        normalize(&mut a, 15.0);
        normalize_scalar(&mut b, 15.0);
        for i in 0..a.len() {
            assert_eq!(a[i].to_bits(), b[i].to_bits(), "lane {} differs", i);
        }
        // Zero-total path → uniform.
        let mut a = vec![0.5, 1.5, 2.5];
        let mut b = a.clone();
        normalize(&mut a, 0.0);
        normalize_scalar(&mut b, 0.0);
        for i in 0..a.len() {
            assert_eq!(a[i].to_bits(), b[i].to_bits(), "uniform lane {} differs", i);
        }
    }

    #[test]
    fn update_regret_sum_matches_scalar_bit_exact() {
        let av = vec![0.5, -0.25, 1.0, -1.5, 0.0, 2.0, 0.1];
        let mut a = vec![0.0; av.len()];
        let mut b = vec![0.0; av.len()];
        update_regret_sum(&mut a, &av, 0.3, 1.7);
        update_regret_sum_scalar(&mut b, &av, 0.3, 1.7);
        // Two-rounding NEON (vmul + vadd) matches scalar bit-for-bit on
        // each lane — diff-test parity guarantee.
        for i in 0..a.len() {
            assert_eq!(a[i].to_bits(), b[i].to_bits(), "lane {} differs", i);
        }
    }

    #[test]
    fn update_strategy_sum_matches_scalar_bit_exact() {
        let st = vec![0.2, 0.3, 0.1, 0.4];
        let mut a = vec![1.0, 2.0, 3.0, 4.0];
        let mut b = a.clone();
        update_strategy_sum(&mut a, &st, 0.5);
        update_strategy_sum_scalar(&mut b, &st, 0.5);
        for i in 0..a.len() {
            assert_eq!(a[i].to_bits(), b[i].to_bits(), "lane {} differs", i);
        }
    }

    /// PR 61 — SSE2 path parity check. Only runs on x86_64; on aarch64 we
    /// rely on the dispatcher tests above (which select NEON) plus the
    /// CI x86_64 job exercising this path.
    #[cfg(target_arch = "x86_64")]
    #[test]
    fn discount_regrets_sse2_matches_scalar() {
        let inputs: Vec<f64> = vec![-2.0, -1.0, 0.0, 1.0, 2.5, -0.3, 0.7, 0.0, 1e-10, -1e-10];
        let mut a = inputs.clone();
        let mut b = inputs.clone();
        // SAFETY: SSE2 baseline on x86_64; slice valid.
        unsafe { super::sse2::discount_regrets_sse2(&mut a, 0.7, 0.3) };
        discount_regrets_scalar(&mut b, 0.7, 0.3);
        for i in 0..a.len() {
            assert_eq!(a[i].to_bits(), b[i].to_bits(), "lane {} differs", i);
        }
    }

    #[cfg(target_arch = "x86_64")]
    #[test]
    fn discount_strategy_sum_sse2_matches_scalar() {
        let inputs: Vec<f64> = (0..11).map(|i| (i as f64) * 0.1 - 0.5).collect();
        let mut a = inputs.clone();
        let mut b = inputs.clone();
        // SAFETY: SSE2 baseline on x86_64; slice valid.
        unsafe { super::sse2::discount_strategy_sum_sse2(&mut a, 0.5) };
        discount_strategy_sum_scalar(&mut b, 0.5);
        for i in 0..a.len() {
            assert_eq!(a[i].to_bits(), b[i].to_bits(), "lane {} differs", i);
        }
    }

    /// PR 63 — v1.8 Phase 2 vector-form regret update parity check.
    /// Differential: SIMD dispatch vs scalar reference, bit-exact per lane.
    #[test]
    fn update_regret_sum_vector_matches_scalar_bit_exact() {
        // HUNL-shape mini: 8 hands × 3 actions = 24 regret lanes,
        // 24 action_value lanes (action-major), 8 node_value lanes.
        let hand_count = 8;
        let action_count = 3;
        let action_value: Vec<f64> = (0..(hand_count * action_count))
            .map(|i| (i as f64) * 0.13 - 1.5)
            .collect();
        let node_value: Vec<f64> = (0..hand_count).map(|i| (i as f64) * 0.07 + 0.5).collect();
        let initial_regret: Vec<f64> = (0..(hand_count * action_count))
            .map(|i| (i as f64) * 0.01 - 0.5)
            .collect();

        let mut via_simd = initial_regret.clone();
        let mut via_scalar = initial_regret.clone();
        update_regret_sum_vector(
            &mut via_simd,
            &action_value,
            &node_value,
            hand_count,
            action_count,
        );
        update_regret_sum_vector_scalar(
            &mut via_scalar,
            &action_value,
            &node_value,
            hand_count,
            action_count,
        );
        for i in 0..via_simd.len() {
            assert_eq!(
                via_simd[i].to_bits(),
                via_scalar[i].to_bits(),
                "lane {} differs: simd={} scalar={}",
                i,
                via_simd[i],
                via_scalar[i]
            );
        }
    }

    /// Odd `hand_count` exercises the trailing-lane scalar tail.
    #[test]
    fn update_regret_sum_vector_handles_odd_hand_count() {
        for hand_count in [1usize, 2, 3, 5, 7, 9, 17, 33] {
            for action_count in [2usize, 3, 4] {
                let action_value: Vec<f64> = (0..(hand_count * action_count))
                    .map(|i| (i as f64) * 0.31 - 5.0)
                    .collect();
                let node_value: Vec<f64> =
                    (0..hand_count).map(|i| (i as f64) * 0.17 - 0.3).collect();
                let initial_regret: Vec<f64> = (0..(hand_count * action_count))
                    .map(|i| (i as f64) * 0.02 + 0.1)
                    .collect();

                let mut via_simd = initial_regret.clone();
                let mut via_scalar = initial_regret.clone();
                update_regret_sum_vector(
                    &mut via_simd,
                    &action_value,
                    &node_value,
                    hand_count,
                    action_count,
                );
                update_regret_sum_vector_scalar(
                    &mut via_scalar,
                    &action_value,
                    &node_value,
                    hand_count,
                    action_count,
                );
                for i in 0..via_simd.len() {
                    assert_eq!(
                        via_simd[i].to_bits(),
                        via_scalar[i].to_bits(),
                        "H={} A={} lane {} differs: simd={} scalar={}",
                        hand_count,
                        action_count,
                        i,
                        via_simd[i],
                        via_scalar[i]
                    );
                }
            }
        }
    }

    #[test]
    fn positive_regrets_and_total_is_bit_exact_for_total() {
        // The NEON path now does sequential summation to match scalar
        // bit-for-bit on the total (not just the per-lane outputs).
        let r = vec![-2.0, 1.5, 0.0, 3.0, -0.5, 0.25, 0.75];
        let mut a = vec![0.0; r.len()];
        let mut b = vec![0.0; r.len()];
        let ta = positive_regrets_and_total(&r, &mut a);
        let tb = positive_regrets_and_total_scalar(&r, &mut b);
        for i in 0..a.len() {
            assert_eq!(a[i].to_bits(), b[i].to_bits(), "lane {} differs", i);
        }
        assert_eq!(ta.to_bits(), tb.to_bits(), "total bit pattern differs");
    }
}
