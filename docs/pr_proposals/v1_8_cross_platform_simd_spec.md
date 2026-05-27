# v1.8 Candidate Spec — Cross-Platform Vector Kernels (SIMD)

**Status:** Pre-spec / forward-looking. NOT for execution this session.
**Date:** 2026-05-25 (originally drafted as NEON-only 2026-05-23; revised cross-platform 2026-05-25)
**Targets:** v1.8 (perf-only, post-v1.7.0)
**Source perf profile:** `docs/v1_7_0_nash_path_perf_profile.md` §"v1.8 candidate"
**Supersedes:** `docs/pr_proposals/v1_8_neon_vector_kernels_spec.md` (NEON-only draft)

---

## 0. Why cross-platform (revision rationale)

The earlier draft restricted v1.8 to Apple Silicon NEON. This repo is **public OSS** and the v1.0+ packaging line ships to:

- Apple Silicon (primary dev target),
- Intel Mac (still in use by the user base — universal2 .dmg from PR 11),
- Linux x86_64 (most server / power-user installs),
- Windows x86_64 (matters for any non-trivial OSS poker tool reach).

A NEON-only kernel set would leave the **majority of public-repo users on the scalar path**, which is the exact opposite of what a "perf release" should do. v1.8 therefore picks an abstraction that lets the *same call site* dispatch to NEON, SSE4.2 / AVX2, or scalar based on `cfg(target_arch)` + runtime feature detection. Scalar remains the correctness reference.

The four kernels and the algorithmic analysis (transpose for the regret update, sequential-sum bit-parity, etc.) are unchanged from the NEON draft — only the abstraction and target matrix expand.

---

## 1. Goal

Apply portable SIMD to the four vector-form DCFR hot loops in
`crates/cfr_core/src/dcfr_vector.rs`. Bring Sarah's turn 8-class × 500-iter
Nash solve from ~10+ min wall-clock down to **≤ 5 min** on Apple Silicon
(her stated budget; see [`feedback_persona_time_budgets`](file:///Users/ashen/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/feedback_persona_time_budgets.md))
and deliver **comparable proportional speedups on Intel Mac / Linux x86_64 / Windows x86_64**.

**Target functions** (all in `dcfr_vector.rs`):

- `VectorDCFR::discount` (lines 266-289) — sign-conditional regret rescale + strategy_sum rescale, per-iter catch-up loop.
- `VectorDCFR::traverse` regret-update block (lines 444-450) — `regret[h,a] += action_value[a,h] - node_value[h]` over `hand_count × action_count`.
- `VectorDCFR::traverse` strategy-sum-update block (lines 454-463) — `strategy_sum[h,a] += reach_p[h] * strategy[h,a]`.
- `VectorDCFR::compute_strategy` (lines 207-232) — regret-matching per hand (positive-clamp + normalize).

**Projected speedup (per target ISA):**
- aarch64 NEON (2-lane f64): **4-8×** on these kernels (PR 8 calibration).
- x86_64 SSE4.2 (2-lane f64): **3-5×** (same lane width, same intrinsic shape as NEON).
- x86_64 AVX2 (4-lane f64): **6-10×** (wider lanes; runtime-detected).
- Scalar fallback: 1× (no regression vs current code).

---

## 2. Background

- **PR 8** (v1.2.0, `crates/cfr_core/src/simd.rs`) landed NEON for the *scalar*-shape DCFR with `cfg(target_arch = "aarch64")` gating and a bit-exact scalar fallback for everything else. Bit-parity diff vs scalar fallback maintained (`STRATEGY_ATOL = 1e-4` differential test bar).
- **PR 23** (v1.5.0, `dcfr_vector.rs`) introduced the *vector*-form CFR with a 2D shape: `hand_count × action_count` row-major. Implementer notes (`docs/pr_proposals/v1_5_pr_23_implementer_notes.md:101`) explicitly flagged vector-shape SIMD as deferred: *"the existing `simd.rs` kernels assume `action_count` shape; vector-form needs `hand_count × action_count` shape… Rough projection: 4-8× speedup based on PR 8's experience."*
- **Code comment** at `dcfr_vector.rs:263-265` reinforces it: *"We do not route through `simd::discount_regrets` here because the vector shape is `hand_count × action_count` rather than `action_count` … a vector-shape SIMD kernel is a follow-up for v1.5.x perf."*

---

## 3. References

- `crates/cfr_core/src/dcfr_vector.rs` — scalar implementations of the four targets.
- `crates/cfr_core/src/simd.rs` — PR 8 NEON helpers + scalar fallback pattern (the cross-platform precedent for this PR).
- `references/code/noambrown_poker_solver/cpp/src/trainer.cpp:138-240` — Brown's MIT reference (algorithm correctness anchor).
- `docs/v1_7_0_nash_path_perf_profile.md` — measured per-iter cost data motivating this PR.
- `docs/pr_proposals/v1_5_pr_23_implementer_notes.md:96-104` — original deferred-work entry.
- Intel intrinsics guide (`https://www.intel.com/content/www/us/en/docs/intrinsics-guide/`) — SSE/AVX intrinsic reference (kernels re-derived from public docs; no AGPL code copied).
- Apple NEON intrinsics reference (existing precedent in `simd.rs` doc header).

---

## 4. SIMD abstraction approach — Option C (hand-written cfg-gated intrinsics)

Three abstractions were considered:

### Option A: Rust nightly `std::simd` (`portable-simd`)
- **Pro:** clean, idiomatic, single source per kernel.
- **Con:** **requires nightly toolchain.** A public OSS solver must build on stable. **Rejected.**

### Option B: `wide` crate (third-party portable SIMD)
- **Pro:** stable Rust support, NEON+SSE+AVX coverage, clean API.
- **Con:** new dependency for a perf-critical path; bit-parity guarantees become a property of the dependency, not our code (PR 8's parity discipline — sequential sum, two-rounding vmul+vadd, per-lane vdiv — is *load-bearing* against the `STRATEGY_ATOL=1e-4` diff bar). Auditing `wide`'s reduction semantics across every release would be a recurring chore. Also: extra build-time cost on every downstream consumer.
- **Verdict:** would work, but trades parity transparency for code volume reduction. Not preferred.

### Option C: Hand-written cfg-gated intrinsics with scalar fallback (CHOSEN)
- **Pro:**
  - **Zero new dependencies** — important for OSS auditability.
  - **Stable Rust** — uses `core::arch::aarch64`, `core::arch::x86_64`.
  - **Direct precedent:** `crates/cfr_core/src/simd.rs` (PR 8) already does this for NEON. The scalar fallback is the cross-platform fallback today; we are *adding* SSE/AVX paths alongside the NEON one, not replacing the abstraction.
  - **Bit-parity is local code** — our sequential-sum / two-rounding / per-lane-vdiv discipline lives in our tree and is diff-tested in-source.
  - **Runtime feature detection** for AVX2 is available on stable via `is_x86_feature_detected!()` (no nightly required).
- **Con:** more code (three implementations per kernel: NEON, SSE/AVX, scalar). Tractable because each kernel is small (~30-50 LoC each); the existing NEON code is ~150 LoC for five kernels.

**Decision: Option C.** Continuity with PR 8's pattern is the deciding factor — every learning baked into `simd.rs` (NaN-preserving max, sequential-sum bit-parity, vmul+vadd vs FMA tradeoff, per-lane vdiv) is reusable verbatim, and we add SSE/AVX as siblings under the same dispatch.

---

## 5. Target matrix

| Target triple | SIMD path | Lane width (f64) | Notes |
|---|---|---|---|
| `aarch64-apple-darwin` | NEON | 2 | Primary dev target; PR 8 already lands NEON here. |
| `x86_64-apple-darwin` | SSE4.2 baseline; AVX2 runtime-detected | 2 (SSE) / 4 (AVX2) | Intel Mac universal2 baseline is SSE4.2 (Apple's universal2 floor). AVX2 gated by `is_x86_feature_detected!("avx2")`. |
| `x86_64-unknown-linux-gnu` | SSE4.2 baseline; AVX2 runtime-detected | 2 / 4 | Most Linux installs since ~2013 have AVX2. Detection at runtime, no cfg switch needed for end-users. |
| `aarch64-unknown-linux-gnu` | NEON | 2 | Server-side ARM (e.g., AWS Graviton). NEON is mandatory on aarch64 — same code path as Apple Silicon. |
| `x86_64-pc-windows-msvc` | SSE4.2 baseline; AVX2 runtime-detected | 2 / 4 | Windows MSVC toolchain; same intrinsics as Linux/macOS x86_64. |
| Any other (e.g., `wasm32`, `x86_64-unknown-freebsd`) | Scalar fallback | 1 | Correctness preserved; perf unchanged from pre-v1.8 vector-form. |

**Lane width note:** the existing `simd.rs` codebase is f64-throughout. We do NOT widen to f32 in this PR (precision discipline; see `STRATEGY_ATOL=1e-4` constraint). f64-only means NEON gets 2 lanes, SSE2/SSE4.2 gets 2 lanes, AVX2 gets 4 lanes, AVX-512 gets 8 lanes (AVX-512 not targeted in this PR — small consumer-laptop footprint and Intel deprecation on consumer chips).

**Baseline policy:** SSE4.2 (not just SSE2) is the x86_64 baseline because (a) universal2 .dmg already targets it; (b) all 64-bit x86 CPUs since ~2008 support it; (c) the only intrinsics we need (`_mm_loadu_pd`, `_mm_mul_pd`, `_mm_add_pd`, `_mm_max_pd`, `_mm_div_pd`, `_mm_cmpgt_pd`, `_mm_blendv_pd`) are SSE2/SSE4.1 — calling it SSE4.2 just pins the floor unambiguously for CI and packaging.

---

## 6. Module layout

```
crates/cfr_core/src/
  simd.rs              # Existing — keep as-is (or split into submodules; see below).
  simd_vector.rs       # NEW — vector-shape kernels (this PR's deliverable).
```

Within `simd.rs` / `simd_vector.rs`, organize as:

```rust
// Scalar reference impls (always compiled; used on non-SIMD targets + as
// the parity-test reference). Identical to PR 8 pattern.
pub fn <kernel>_scalar(...) { ... }

#[cfg(target_arch = "aarch64")]
mod neon {
    use core::arch::aarch64::*;
    #[target_feature(enable = "neon")]
    pub unsafe fn <kernel>_neon(...) { ... }
}

#[cfg(target_arch = "x86_64")]
mod sse {
    use core::arch::x86_64::*;
    #[target_feature(enable = "sse4.2")]
    pub unsafe fn <kernel>_sse(...) { ... }
}

#[cfg(target_arch = "x86_64")]
mod avx {
    use core::arch::x86_64::*;
    #[target_feature(enable = "avx2")]
    pub unsafe fn <kernel>_avx2(...) { ... }
}

// Public dispatch — single entry point per kernel.
#[inline]
pub fn <kernel>(...) {
    #[cfg(all(target_arch = "aarch64", not(feature = "force_scalar")))]
    unsafe { neon::<kernel>_neon(...) }

    #[cfg(all(target_arch = "x86_64", not(feature = "force_scalar")))]
    {
        if is_x86_feature_detected!("avx2") {
            unsafe { avx::<kernel>_avx2(...) }
        } else {
            // SSE4.2 is unconditionally available on x86_64 (it's our
            // baseline per §5); no detection needed.
            unsafe { sse::<kernel>_sse(...) }
        }
    }

    #[cfg(not(any(
        all(target_arch = "aarch64", not(feature = "force_scalar")),
        all(target_arch = "x86_64", not(feature = "force_scalar")),
    )))]
    <kernel>_scalar(...)
}
```

The runtime dispatch on x86_64 happens **once per kernel call**. Branch prediction makes this near-free after the first call. If profiling shows the dispatch overhead matters on the smallest kernel sizes (action_count=2, hand_count=64), we can cache the AVX2 flag in a `OnceCell<bool>` at module init — but expect this is unnecessary.

---

## 7. Per-kernel implementation sketches

### 7.1 Discount (Phase 1 — start here)

**Scalar reference** (`dcfr_vector.rs:277-286`):
```rust
for r in &mut info.regret {
    if *r > 0.0 { *r *= pos_scale; }
    else if *r < 0.0 { *r *= neg_scale; }
}
for s in &mut info.strategy_sum { *s *= strat_scale; }
```

**Per-target intrinsic mappings:**

| Op | NEON | SSE4.2 | AVX2 |
|---|---|---|---|
| Load 2/4 f64 | `vld1q_f64` | `_mm_loadu_pd` | `_mm256_loadu_pd` |
| Splat scale | `vdupq_n_f64` | `_mm_set1_pd` | `_mm256_set1_pd` |
| Multiply | `vmulq_f64` | `_mm_mul_pd` | `_mm256_mul_pd` |
| Compare > 0 | `vcgtq_f64` | `_mm_cmpgt_pd` | `_mm256_cmp_pd(_, _, _CMP_GT_OQ)` |
| Blend by mask | `vbslq_f64` | `_mm_blendv_pd` | `_mm256_blendv_pd` |
| Store 2/4 f64 | `vst1q_f64` | `_mm_storeu_pd` | `_mm256_storeu_pd` |

Each ISA processes the flat `hand_count × action_count` buffer two/four lanes at a time; scalar tail handles `len % lane_width` remainder. Shape is irrelevant for this kernel (pure elementwise).

**Bit-parity contract:** NaN-preserving max (mirroring `nan_preserving_max` in current `simd.rs`); for SSE/AVX use `_mm_max_pd` / `_mm256_max_pd` which are NaN-preserving on x86 by spec (matches NEON `vmaxq_f64` semantics).

### 7.2 Per-hand regret update (Phase 2)

Pre-transpose `action_values` from action-major to hand-major (as in original spec §5 / roadmap Phase 2), then delegate per-hand-row to `update_regret_sum` (which now dispatches to NEON / SSE / AVX / scalar).

Transpose itself: scalar `for h { for a { out[h*A+a] = in[a*H+h]; } }` is fine for v1.8 — vectorized transpose (vld2q on NEON, `_MM_TRANSPOSE2_PD` on SSE) is a possible v1.8.x follow-up.

### 7.3 Strategy-sum update (Phase 3)

Shape already aligned (hand-major both sides). Per-hand-row delegate to `update_strategy_sum`. Preserve the `weight == 0.0` short-circuit.

### 7.4 Compute strategy (Phase 4)

Per-hand-row regret-matching:
1. Positive-clamp + sequential sum → `positive_regrets_and_total`.
2. Divide-by-total or uniform fallback → `normalize`.

Both already exist in `simd.rs` for NEON; this PR adds the SSE/AVX siblings.

**Critical for parity:** sequential sum (not horizontal SIMD reduction) on ALL ISAs. Per-lane division (not multiply-by-reciprocal) on ALL ISAs. Two-rounding vmul+vadd (not FMA) for the update kernels on ALL ISAs.

---

## 8. Migration path (phased)

### Phase 1 — `discount` (smallest, lowest-risk, no shape mismatch)
- Add SSE4.2 + AVX2 paths to existing `simd::discount_regrets` and `simd::discount_strategy_sum`.
- Wire `VectorDCFR::discount` to call them on the flat buffer.
- Differential test: scalar vs NEON, scalar vs SSE, scalar vs AVX2 — bit-exact (or ULP≤1 where annotated).
- **Estimated: 1.5-2 days** (was 0.5-1 in NEON-only; cross-platform doubles the scope per kernel).

### Phase 2 — Regret update (transpose + per-hand delegate)
- Add SSE4.2 + AVX2 paths to `simd::update_regret_sum`.
- Add transpose helper (scalar is fine for v1.8).
- Wire `traverse` block.
- **Estimated: 3-4 days.**

### Phase 3 — Strategy-sum update (per-hand delegate, no transpose)
- Add SSE4.2 + AVX2 paths to `simd::update_strategy_sum`.
- Wire `traverse` block.
- **Estimated: 2 days.**

### Phase 4 — Compute strategy (per-hand regret-matching)
- Add SSE4.2 + AVX2 paths to `simd::positive_regrets_and_total` and `simd::normalize`.
- Wire `VectorDCFR::compute_strategy`.
- **Estimated: 2-3 days.**

**Cross-phase shared work:**
- Validation + bench scaffolding (per-target): 2-3 days.
- W2.1 retest on M-series + secondary perf check on x86_64 (Linux CI runner): 1-2 days.

**Total revised: 11-16 dev-days (~2-3 weeks focused).** Was 7-12 (~1-2 weeks) in NEON-only spec.

---

## 9. Validation

### 9.1 Bit-parity diff tests (in-source, per kernel, per ISA)

Extend the existing parity tests in `simd.rs` to cover all three SIMD paths:

```rust
#[cfg(target_arch = "aarch64")]
#[test]
fn discount_regrets_neon_matches_scalar() { /* existing, keep */ }

#[cfg(target_arch = "x86_64")]
#[test]
fn discount_regrets_sse_matches_scalar() { /* new */ }

#[cfg(target_arch = "x86_64")]
#[test]
fn discount_regrets_avx2_matches_scalar() {
    if !is_x86_feature_detected!("avx2") { return; /* skip on non-AVX2 CI */ }
    /* new */
}
```

Inputs cover sizes `{1×2, 8×3, 64×4, 1081×14}` (mirrors the original NEON spec §6). Per-lane `to_bits()` equality (or ULP≤1 for total-sum where the spec explicitly allows it).

### 9.2 Integration test

New file `crates/cfr_core/tests/test_dcfr_vector_simd.rs` (renamed `tests/test_dcfr_vector_simd_cross_platform.rs` if appropriate): exercises all four kernels via their public entry points and asserts dispatch correctness on the current build target. Runs on every CI target.

### 9.3 Differential test against Python ground truth

`tests/test_range_vs_range_rust_diff.py` continues to gate at `STRATEGY_ATOL = 1e-4`. Must PASS on every CI target.

### 9.4 Criterion microbench (per-target)

`crates/cfr_core/benches/bench_dcfr_vector_simd.rs` — measure per-kernel wall-clock on `hand_count × action_count ∈ {64×3, 256×3, 1081×3, 1081×14}` for:
- aarch64 NEON (macOS arm64 CI runner).
- x86_64 SSE4.2 baseline (Linux x86_64 CI, AVX2 disabled via `--cfg force_scalar` or env var).
- x86_64 AVX2 (Linux x86_64 CI, AVX2 enabled).

### 9.5 End-to-end W2.1 retest

Sarah's turn 8-class × 500-iter Nash solve must complete in **≤ 5 min** on Apple Silicon. On x86_64 (Linux CI), record the wall-clock as a regression baseline but do not gate (different hardware classes; persona budget is the M-series number).

---

## 10. Cross-platform CI strategy

**Prerequisite:** v1.7.2 (ship-process hardening) introduces GitHub Actions. v1.8 extends the matrix.

```yaml
# .github/workflows/ci.yml (illustrative — to be authored in v1.7.2 / v1.8)
jobs:
  test:
    strategy:
      matrix:
        os: [macos-14, macos-13, ubuntu-22.04, windows-2022]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - run: rustup install stable
      - run: cargo test --workspace
      - run: cargo test --workspace --features force_scalar
        # Force-scalar mode verifies the fallback path even on ISA-rich hosts.
      - run: pytest tests/
```

| Runner | OS | ISA | Coverage |
|---|---|---|---|
| `macos-14` | macOS 14, M-series | aarch64 NEON | Primary; W2.1 perf gate runs here. |
| `macos-13` | macOS 13, Intel | x86_64 SSE4.2/AVX2 | Intel Mac users; AVX2 detected at runtime on these runners (Skylake-class). |
| `ubuntu-22.04` | Linux x86_64 | SSE4.2/AVX2 | Linux user base; AVX2 detected at runtime. |
| `windows-2022` | Windows MSVC | x86_64 SSE4.2/AVX2 | Windows users; same x86_64 code path. Verify Rust + pytest both build clean. |

**Force-scalar regression lane:** running `cargo test --features force_scalar` on every target catches any drift where the scalar fallback differs from the SIMD path. This is the cross-platform extension of PR 8's `force_scalar` feature flag (already exists in `simd.rs:396`).

**Differential SIMD test gating:** every kernel's `_matches_scalar` test must PASS on every target. CI fails fast if any per-lane `to_bits()` diverges between scalar and SIMD on any ISA.

**Windows-specific note:** `pytest tests/` needs Windows-compatibility audit (path separators, line endings, subprocess handling). v1.7.2 should establish this baseline; v1.8 inherits it.

---

## 11. Effort estimate (revised)

- **Dev time:** ~11-16 dev-days (**2-3 weeks focused**, one engineer). Was 7-12 days (1-2 weeks) in NEON-only spec.
- **Drivers of the increase vs NEON-only:**
  - Three implementations per kernel (NEON, SSE, AVX2) instead of one.
  - Per-target bit-parity tests (4 ISA permutations × 5 kernels).
  - CI matrix expansion (4 OS × test/bench × scalar/SIMD).
  - Windows pytest compatibility verification.
- **Risk:** **MEDIUM** (unchanged from NEON-only). The math is unchanged. Risk now spans more ISAs but they're all f64-elementwise/2D-row kernels — the patterns generalize cleanly. The PR 8 parity discipline (sequential sum, two-rounding, per-lane vdiv) translates 1:1 across NEON/SSE/AVX.
- **Confidence in speedup targets:**
  - NEON 4-8×: MED-HIGH (PR 8 calibration, unchanged).
  - SSE4.2 3-5×: HIGH (same lane width as NEON; identical algorithm).
  - AVX2 6-10×: MED-HIGH (4 lanes vs 2; expect ~1.5-1.8× over SSE on memory-bound kernels, more on FMA-rich paths).

---

## 12. Dependencies

- Requires **v1.7.0** baseline (vector-form architecture must exist).
- Requires **v1.7.2** baseline (GitHub Actions CI scaffolding — the cross-platform matrix is built on top of it).
- **Independent** of v1.6.1 Path D decision; can ship even while that stays paused.
- Independent of v1.9 candidate (EMD bucketing); both could ship in either order.

---

## 13. Acceptance criteria

1. Bit-parity diff test PASSes on all four kernels at sizes up to `1081 × 14` on **every** CI target (macos-14 / macos-13 / ubuntu-22.04 / windows-2022).
2. Criterion benchmark shows:
   - **≥ 4×** speedup on each kernel at `≥ 256 × 3` shape on aarch64 NEON.
   - **≥ 3×** speedup on each kernel at `≥ 256 × 3` shape on x86_64 SSE4.2.
   - **≥ 6×** speedup on each kernel at `≥ 256 × 3` shape on x86_64 AVX2 (where available; gated by `is_x86_feature_detected!("avx2")`).
3. **W2.1 retest** (turn, 8 classes × 500 iter) completes in **≤ 5 min** wall-clock on M-series Mac (Sarah's persona budget).
4. Differential test (`test_range_vs_range_rust_diff.py`) still PASSes at `STRATEGY_ATOL = 1e-4` on every CI target.
5. `cargo test --workspace` and `cargo test --workspace --features force_scalar` green on every CI target; `pytest tests/` green on every CI target; no regressions in any persona retest.

---

## 14. Alternatives considered

- **NEON-only (this spec's original draft):** rejected — leaves majority of public-repo users on scalar path. See §0.
- **`std::simd` (nightly):** rejected — public OSS users build on stable. See §4 Option A.
- **`wide` crate:** considered but rejected for parity-transparency reasons. See §4 Option B.
- **GPU (PyTorch MPS / Metal / CUDA):** rejected in original Ultraplan (framework dependency, memory overhead, MPS f64 gaps). Cross-platform GPU would be even larger surface area.
- **f32 widening:** rejected — `STRATEGY_ATOL=1e-4` parity discipline is f64-anchored; widening would force a new parity bar.
- **AVX-512 explicit target:** deferred — Intel deprecation on consumer chips makes the consumer-laptop footprint small; revisit if persona evidence shows large server-side AVX-512 use. AVX2 covers ~95%+ of modern x86_64.
- **EMD bucketing in vector form (v1.9 candidate):** the next PR after v1.8; complementary, not a replacement.
- **"Just run fewer iterations":** doesn't address per-iter cost; degrades convergence quality.

---

## 15. Cross-references

- Memory: [`project_solver`](file:///Users/ashen/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/project_solver.md) §Status — v1.8 candidate listed here once spec approved.
- Memory: [`feedback_persona_time_budgets`](file:///Users/ashen/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/feedback_persona_time_budgets.md) — Sarah's ≤ 5 min budget is the gating acceptance bar (on M-series).
- Memory: [`feedback_public_repo_hygiene`](file:///Users/ashen/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/feedback_public_repo_hygiene.md) — public OSS repo is the reason for cross-platform scope.
- Memory: [`feedback_no_extrapolate`](file:///Users/ashen/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/feedback_no_extrapolate.md) — per-target speedup numbers are TARGETS, not locked deltas. Per-target bench data required before claiming final numbers.
- PLAN.md: add v1.8 row under post-v1.7.0 perf workstream once accepted.
- Companion: `docs/v1_8_neon_implementation_roadmap.md` — phased implementation plan (still valid as the per-kernel algorithm reference; ISA-specific intrinsic tables in this spec §7.1 supplement it).

---

## 16. Recommended priority

**HIGH.** This is the gating perf gain for turn-multi-street Nash interactive viability per the v1.7.0 perf profile. Without it, Sarah's turn workflows remain over-budget on M-series, and **x86_64 users are systematically slower** (a worse outcome on a public OSS repo than NEON-only would suggest). Cross-platform scope adds ~1 week to the dev estimate but multiplies the user-facing benefit by the entire non-Apple-Silicon user base.

---

## Appendix A — Why not just NEON + scalar?

A naive read of PR 8 would say: "we already have NEON + scalar fallback; non-aarch64 users get scalar, which is what they have today; no regression." That's true for *correctness*, but a perf release that leaves the majority of users (every Linux/Windows installer + Intel Mac user) at pre-v1.8 speeds is not a perf release — it's an Apple-Silicon-perf release with cross-platform-correctness preservation.

For a v1.8 labeled "make the solver 4-8× faster" to be honest on the public README, x86_64 needs first-class kernels. SSE4.2 + AVX2 give us that without nightly or new deps.

## Appendix B — Why not AVX-512?

AVX-512 (8-lane f64) would offer another ~1.5-1.8× over AVX2 on these kernels. Reasons to defer:
1. Intel deprecation on consumer Alder/Raptor Lake (E-cores lack it; P-cores have it disabled in shipping firmware).
2. AMD Zen 4+ has it, but the consumer-laptop footprint is still smaller than AVX2.
3. Adds another ISA path (4 implementations per kernel, not 3) and another CI permutation.
4. The marginal gain is small relative to the cliff from scalar → SSE (or NEON).

If post-v1.8 telemetry shows significant server-side Zen 4 / Sapphire Rapids use, revisit. Otherwise, AVX-512 stays out of scope.
