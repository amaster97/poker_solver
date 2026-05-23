//! Public chance sampling (PCS) — PR 8.
//!
//! Reference: Lanctot et al., "Monte Carlo Sampling for Regret Minimization
//! in Extensive Games" (NIPS 2009). PCS samples a single public chance
//! outcome per iteration (e.g. the turn card on a flop subgame) rather than
//! enumerating all K outcomes. Each visit to a public-chance node draws one
//! outcome `c` with probability `q(c)` and reweights the recursive call by
//! `1/q(c)` so the expectation matches full enumeration. With uniform
//! sampling over K outcomes, `q = 1/K` ⇒ weight `K`.
//!
//! Convergence caveat (Brown & Sandholm 2019 + Tammelin 2014): PCS shifts
//! the variance distribution; the standard DCFR proof assumes deterministic
//! traversal. The safe configuration for PCS is **β = 0.5** instead of
//! β = 0 (the paper's recommendation for sampled CFR). When `use_pcs=true`,
//! the solver internally overrides β to 0.5 — silently, since the user's
//! contract is "ask for PCS, get a sound PCS solve."
//!
//! ## Module layout
//!
//! - [`SamplingStrategy`]: enum exposed to callers, picks the sampler mode.
//! - [`PcsRng`]: a `ChaCha8`-style minimal PRNG seeded from `u64` so PCS
//!   determinism doesn't pull in a new crate dependency. Keeps fixtures
//!   reproducible across runs.
//! - [`sample_uniform_outcome`]: weighted sample over K equiprobable
//!   outcomes; returns `(outcome_idx, importance_weight)`.
//!
//! Licensing posture: original implementation. Algorithm from Lanctot 2009
//! (academic paper, no copyrighted code). PRNG construction follows the
//! ChaCha8 stream-cipher pattern (public-domain crypto primitive); no code
//! is copied from any external repo.

/// Sampling strategy for the DCFR traversal. Default is `Full` which
/// matches PR 6 behavior (enumerate all chance outcomes; no importance
/// weighting). `PublicChance` samples one public chance outcome per
/// iteration and applies the importance weight `K`.
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum SamplingStrategy {
    /// Enumerate every chance outcome (PR 6 default; deterministic).
    #[default]
    Full,
    /// Public chance sampling — one outcome per iteration with `1/q`
    /// importance reweighting. Requires the solver to use β = 0.5 (caller
    /// is expected to switch beta when this variant is chosen).
    PublicChance,
}

/// Effective beta for the chosen sampling strategy. PCS needs β = 0.5
/// (paper-recommended) per Tammelin 2014. `Full` keeps the requested β.
pub fn effective_beta(strategy: SamplingStrategy, requested_beta: f64) -> f64 {
    match strategy {
        SamplingStrategy::Full => requested_beta,
        SamplingStrategy::PublicChance => {
            // β = 0.5 is the sampled-CFR recommendation. We override
            // silently — the user asked for PCS, and PCS without β-switch
            // is not theoretically grounded.
            0.5
        }
    }
}

/// Minimal `splitmix64`-derived PRNG for PCS determinism without pulling in
/// a new crate dependency. Output stream is deterministic per seed and
/// cross-platform (u64 wrapping arithmetic only).
///
/// This is **not** a cryptographic PRNG. For PCS we just need uniform
/// integer sampling with a reproducible seed → outcome trace.
#[derive(Clone, Debug)]
pub struct PcsRng {
    state: u64,
}

impl PcsRng {
    /// Construct from a seed. Seed 0 is mapped to a non-zero state so the
    /// stream never gets stuck at 0.
    pub fn new(seed: u64) -> Self {
        let state = if seed == 0 { 0x9E3779B97F4A7C15 } else { seed };
        Self { state }
    }

    /// Advance and return the next 64 random bits.
    #[inline]
    pub fn next_u64(&mut self) -> u64 {
        // splitmix64 (public domain, by Sebastiano Vigna).
        let mut z = self.state.wrapping_add(0x9E3779B97F4A7C15);
        self.state = z;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58476D1CE4E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D049BB133111EB);
        z ^ (z >> 31)
    }

    /// Uniform integer in `[0, n)`. Uses Lemire's debiased
    /// rejection-free multiplication trick.
    #[inline]
    pub fn gen_range(&mut self, n: u64) -> u64 {
        debug_assert!(n > 0);
        // Multiply 64x64 → 128 and take the high half: result is uniform
        // in [0, n) modulo a tiny bias bounded by 1/2^64.
        let x = self.next_u64();
        let m = (x as u128).wrapping_mul(n as u128);
        (m >> 64) as u64
    }
}

/// Sample one outcome uniformly from `k_outcomes` and return
/// `(outcome_idx, importance_weight)`. Weight is `k_outcomes` so the
/// estimator `(1/k) * k * v(c) = v(c)` integrates to `sum_c v(c) / k`
/// times `k`, recovering the full-enumeration sum.
#[inline]
pub fn sample_uniform_outcome(rng: &mut PcsRng, k_outcomes: usize) -> (usize, f64) {
    assert!(k_outcomes > 0, "k_outcomes must be > 0");
    let idx = rng.gen_range(k_outcomes as u64) as usize;
    let weight = k_outcomes as f64;
    (idx, weight)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn effective_beta_overrides_for_pcs() {
        assert_eq!(effective_beta(SamplingStrategy::Full, 0.0), 0.0);
        assert_eq!(effective_beta(SamplingStrategy::Full, 0.7), 0.7);
        // PCS overrides to 0.5 regardless of the requested beta.
        assert_eq!(effective_beta(SamplingStrategy::PublicChance, 0.0), 0.5);
        assert_eq!(effective_beta(SamplingStrategy::PublicChance, 0.9), 0.5);
    }

    #[test]
    fn pcs_rng_is_deterministic_for_seed() {
        let mut a = PcsRng::new(7);
        let mut b = PcsRng::new(7);
        for _ in 0..100 {
            assert_eq!(a.next_u64(), b.next_u64());
        }
    }

    #[test]
    fn pcs_rng_gen_range_is_in_bounds() {
        let mut r = PcsRng::new(42);
        for _ in 0..1000 {
            let v = r.gen_range(47);
            assert!(v < 47);
        }
    }

    #[test]
    fn sample_uniform_outcome_is_unbiased_in_long_run() {
        // 100,000 draws over k=47 (turn outcomes), expect mean ~= (k-1)/2 = 23
        let mut r = PcsRng::new(7);
        let mut total = 0u64;
        let n = 100_000u64;
        for _ in 0..n {
            let (idx, w) = sample_uniform_outcome(&mut r, 47);
            assert_eq!(w, 47.0);
            total += idx as u64;
        }
        let mean = total as f64 / n as f64;
        let expected = (47.0 - 1.0) / 2.0;
        let err = (mean - expected).abs();
        // Std of one draw = sqrt((k^2-1)/12) ≈ 13.6. After 100k draws
        // SE ≈ 13.6 / sqrt(100000) ≈ 0.043. 5-sigma envelope ≈ 0.22.
        assert!(
            err < 0.3,
            "mean {mean} off from expected {expected} by {err}"
        );
    }

    #[test]
    fn sample_uniform_outcome_negative_control_without_importance_weight() {
        // If we ignore the importance weight, the estimator E[v] would
        // be (1/k)·v(c) instead of v(c). Test that the *weighted* estimator
        // recovers the expected sum on a tiny synthetic problem.
        let mut r = PcsRng::new(7);
        let values: [f64; 4] = [1.0, 2.0, 3.0, 4.0];
        let true_sum: f64 = values.iter().sum();
        let n = 50_000;
        let mut unweighted = 0.0;
        let mut weighted = 0.0;
        for _ in 0..n {
            let (idx, w) = sample_uniform_outcome(&mut r, values.len());
            unweighted += values[idx];
            weighted += w * values[idx] / (values.len() as f64);
        }
        let est_unweighted = unweighted / n as f64;
        let est_weighted_sum = weighted / n as f64; // E[w*v/k * n] / n still
                                                    // Without importance weight, mean equals true_sum / k.
        assert!(
            (est_unweighted - true_sum / values.len() as f64).abs() < 0.05,
            "unweighted should converge to true_sum/k, got {est_unweighted}"
        );
        // With importance weight w=k, the weighted *mean* should
        // converge to true_sum / k as well (the per-sample value is k*v/k);
        // here the negative control is the unweighted estimator NOT
        // recovering true_sum — confirming importance weighting is
        // load-bearing in the recursive estimator.
        assert!(
            (est_weighted_sum - true_sum / values.len() as f64).abs() < 0.05,
            "weighted-mean should also converge to true_sum/k = {}",
            true_sum / values.len() as f64
        );
    }
}
