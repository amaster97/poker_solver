# v1.8 Decision Brief — Make Solver 4-8x Faster (Cross-Platform)

**Date:** 2026-05-25 (revised from NEON-only 2026-05-23)
**Decision needed:** Prioritize for the next release after v1.7.2? **YES / NO**

---

## What is v1.8?

A perf-only release that makes the solver 4-8x faster by rewriting the inner loops of our main solving algorithm to use the CPU's built-in parallel math hardware (SIMD). Same answers, same accuracy — just dramatically less waiting.

**Cross-platform scope (revised 2026-05-25):** Because this is a public OSS poker solver, v1.8 ships SIMD kernels on every supported target — Apple Silicon (NEON), Intel Mac / Linux / Windows x86_64 (SSE4.2 baseline + AVX2 runtime-detected), and a scalar fallback for anything else. Earlier draft was Apple-Silicon-only; that would have left the majority of public-repo users on the scalar path, which contradicts a "perf release."

## Why it matters for users

**Today (post-v1.7.0):** Sarah's turn workflow (8-class, 500-iter Nash solve) takes **over 10 minutes** wall-clock on M-series. Her stated tolerance is **5 minutes**. She's currently waiting too long and disengaging. x86_64 users have proportionally worse latency.

**After v1.8:**
- **Apple Silicon (NEON):** Same solve in **≤ 5 min** — Sarah's budget met. Turn-multi-street Nash becomes interactively viable.
- **x86_64 SSE4.2 baseline (older Intel Mac / older Linux / Windows):** ~3-5x faster than today (per-kernel, in the inner loops).
- **x86_64 AVX2 (most modern desktops since ~2015):** ~6-10x faster — runtime-detected, no separate build needed.
- **Other targets (rare):** scalar fallback; no regression vs today.

Marcus's and other personas' turn workflows benefit proportionally on whichever ISA they run.

**What's still blocked after v1.8:** Flop interactive viability — that's the v1.9 candidate (a separate, larger PR with EMD bucketing). v1.8 alone unblocks turn workflows, not flop.

## Cost (revised)

- **Dev time:** ~11-16 focused dev-days (**2-3 weeks**, one engineer). Was 7-12 days (1-2 weeks) in NEON-only spec.
- **Drivers of the increase:**
  - Three SIMD implementations per kernel (NEON, SSE4.2, AVX2) instead of one.
  - Per-target bit-parity tests on 4 ISA permutations × 4 kernels.
  - CI matrix expands to 4 runners (macOS arm64, macOS x86, Ubuntu x86, Windows x86) instead of 1.
  - Windows pytest compatibility audit (paths, line endings, subprocess).
- **Risk:** MEDIUM (unchanged). The math is unchanged. Risk now spans more ISAs but they're all f64-elementwise/2D-row kernels — the patterns generalize cleanly from PR 8's NEON precedent. Bit-parity discipline (sequential sum, two-rounding vmul+vadd, per-lane vdiv) translates 1:1 across NEON / SSE / AVX.

## SIMD abstraction approach picked

**Option C: Hand-written `cfg`-gated intrinsics with scalar fallback.** This is the same pattern as PR 8 (`crates/cfr_core/src/simd.rs`), generalized from NEON-only to also cover x86_64 SSE/AVX. Rationale:

- **Zero new dependencies** — important for OSS auditability.
- **Stable Rust** — no nightly toolchain needed (rules out Option A: `std::simd`).
- **Direct precedent** — PR 8's scalar-fallback + NEON pattern already lives in our tree; we are adding SSE/AVX as siblings, not replacing the abstraction.
- **Bit-parity is local code** — our discipline (sequential sum / two-rounding / per-lane vdiv) is the load-bearing guarantee against the `STRATEGY_ATOL=1e-4` diff bar. Owning the kernels keeps that transparent. (Rules out Option B: the `wide` crate — would push parity guarantees into a third-party dependency.)

Runtime feature detection (`is_x86_feature_detected!("avx2")`) is available on stable; AVX2 dispatches at first call and predicts cleanly afterward.

## Alternatives considered and rejected

- **NEON-only (original draft):** rejected — leaves majority of public-repo users on scalar path.
- **`std::simd` (nightly):** rejected — public OSS users build on stable.
- **`wide` crate:** rejected — trades parity transparency for code reduction; recurring audit chore on every release.
- **GPU (PyTorch MPS / Metal / CUDA):** rejected in original Ultraplan — framework dependency, memory overhead, MPS f64 gaps. Cross-platform GPU would be even larger surface area.
- **Deep CFR / neural function approx:** Out of scope; changes the algorithm, not just the implementation.
- **EMD bucketing (v1.9 candidate):** Complementary; addresses *flop* viability. Recommended as the *next* step after v1.8, not a replacement.
- **f32 widening:** rejected — `STRATEGY_ATOL=1e-4` parity discipline is f64-anchored.
- **AVX-512 explicit target:** deferred — Intel consumer-chip deprecation makes the consumer-laptop footprint small; revisit if persona evidence shows server-side use.
- **"Just run fewer iterations":** Degrades convergence quality. Not a fix.

## Recommended priority

**HIGH.** It's the smallest, lowest-risk, highest-confidence path to unblocking Sarah's turn workflow — the gating persona budget — and PR 8 already proved this exact pattern works on a similar kernel shape. The cross-platform extension adds about a week to dev time but multiplies the user-facing benefit by the entire non-Apple-Silicon user base (Intel Mac / Linux / Windows), which is the right call for a public OSS repo.

---

## What you need to decide

**One question:** After v1.7.2 ships, do we make v1.8 the next release? **YES / NO**

- YES → 2-3 weeks of perf work; Sarah's turn workflow unblocked on M-series, x86_64 users get 3-10x speedup; flop work (v1.9) follows.
- NO → Turn workflow stays over-budget on every ISA; consider alternative next steps (e.g., features over perf, or jump straight to v1.9).

---

## Companion docs

- Spec: `docs/pr_proposals/v1_8_cross_platform_simd_spec.md` — full target matrix, per-kernel intrinsic tables, phased migration plan, CI strategy.
- Implementation roadmap: `docs/v1_8_neon_implementation_roadmap.md` — per-kernel algorithm reference (still valid; intrinsic tables in the cross-platform spec §7.1 supplement it).
- Superseded: `docs/pr_proposals/v1_8_neon_vector_kernels_spec.md` (NEON-only original; redirects to the cross-platform spec).
