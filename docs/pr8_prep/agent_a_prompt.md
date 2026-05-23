# PR 8 Agent A — NEON SIMD module + scalar fallback + parity tests

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 8 Agent A.**
**Your scope:** the ARM NEON 128-bit SIMD vectorization module + its bit-parity scalar fallback for non-aarch64 targets + the exhaustive SIMD-vs-scalar parity test file; also the `mod simd;` re-export line in `crates/cfr_core/src/lib.rs` and the Criterion dev-dependency entry in `Cargo.toml`.
**Your contract:** produce `crates/cfr_core/src/simd.rs` (with `Vec4f64` + four hot-loop ops) and `tests/test_simd.rs`, exposing the public API documented in §"Public API contract" below; Agents B + C consume `simd::regret_matching_simd`, `simd::fma_scalar_vec`, `simd::discount_positive_negative`, `simd::discount_strategy` from the DCFR loop after their integration step.
**Your success criteria:** `cargo test --release test_simd` passes on aarch64-apple-darwin with bit-exact equality between SIMD and scalar paths (NaN/Inf/denormal/signed-zero correctly propagated); `cargo clippy --all-targets -- -D warnings` clean; standalone microbench shows ≥3× SIMD speedup over scalar fallback on a 1024-element regret vector; no `unsafe` outside SIMD intrinsics wrappers, each `unsafe` block carries a `// SAFETY:` comment.
**File ownership:** you own and may write ONLY `crates/cfr_core/src/simd.rs`, `tests/test_simd.rs`, the `mod simd;` line in `crates/cfr_core/src/lib.rs`, and the `[dev-dependencies] criterion = "0.5"` line in `crates/cfr_core/Cargo.toml`.

---

## Strict file ownership

**You own (write + create freely):**
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/simd.rs` (new file)
- `/Users/ashen/Desktop/poker_solver/tests/test_simd.rs` (new Rust integration test file at the workspace root `tests/` dir — NOT under `crates/cfr_core/tests/`; this matches the existing repo layout where Rust integration tests live alongside Python tests in `/Users/ashen/Desktop/poker_solver/tests/`. If the existing repo layout has Rust integration tests under `crates/cfr_core/tests/` instead, follow that convention; check by running `ls crates/cfr_core/tests/` first.)

**You may modify (existing files, surgical edits only):**
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/lib.rs` — add ONLY a `pub mod simd;` line (and its re-export of the four public hot-loop ops if appropriate). Do NOT touch any other declaration. Do NOT add `mod layout;` or `mod pcs;` — those are Agent B's and Agent C's lines respectively.
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/Cargo.toml` — add the `[dev-dependencies] criterion = { version = "0.5", default-features = false, features = ["html_reports"] }` block if not already present. Do NOT add any runtime dependency. Do NOT add the `simd` Cargo feature (per Decision 11.1, NEON is gated by `target_arch`, not by feature flag).

**You must NOT touch:**
- `crates/cfr_core/src/layout.rs` — Agent B owns this. (Do NOT create it. Agent B will define it.)
- `crates/cfr_core/src/pcs.rs` — Agent C owns this. (Do NOT create it.)
- `crates/cfr_core/src/dcfr.rs` — Agent B owns the DCFR refactor; you only provide the public API in `simd.rs` that Agent B's `dcfr.rs` will call.
- `crates/cfr_core/src/solver.rs` — Agent B owns.
- `crates/cfr_core/src/hunl_solver.rs` (if it exists post-PR 6) — Agent C owns.
- `crates/cfr_core/src/{kuhn,leduc,game,eval}.rs` — out of scope (unchanged by PR 8).
- `benches/cfr_bench.rs` — Agent B owns the bench harness.
- `benches/baseline.json` — Agent B owns; first task of Agent B before any optimization lands.
- Any Python file (`poker_solver/*.py`) — out of scope.
- Any other test file (`tests/test_layout.rs`, `tests/test_pcs.rs`, `tests/test_pr8_convergence.py`) — Agents B and C own these.

If you discover an awkward signature mid-implementation, **do not silently change it**. Stop and write a short note to the orchestrator describing the conflict; the orchestrator will reconcile across agents.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/pr8_spec.md`. Internalize §1 (goal + non-goals), §3 (NEON SIMD module — your stage), §6 (files to create — your owned rows), §7 Layer A (your test layer), §8 Agent A deliverables + acceptance criteria, §9 items 1, 3, 6, 12 (your critical correctness items), §10 risks 1, 5, 10, 12 (your risks), §11 decisions 1, 8 (your locked defaults).
2. **The PLAN (locked decisions):** `/Users/ashen/Desktop/poker_solver/PLAN.md`. Especially §1 perf targets (the 10×/50× gate you ultimately enable), §1 "No GPU. PyTorch MPS underperforms..." line (which motivates NEON over GPU), §6 license audit (the AGPL contamination guardrail re postflop-solver patterns).
3. **The autonomous log (locked decisions in flight):** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md`. Skim for any PR 8-related amendments after PR 8 spec write-time.
4. **Spec consistency review (cross-cutting amendments):** `/Users/ashen/Desktop/poker_solver/docs/spec_consistency_review.md`. Skim for entries referring to PR 8 (especially I3 tolerance, I6 `use_pcs` schema — neither directly affects you; you implement bit-exact ops with no statistical tolerance).
5. **The existing DCFR Rust hot loop (your code's caller):** `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/dcfr.rs`. Read lines 83-100 (`get_strategy`: regret_matching scalar path you'll vectorize), lines 111-134 (DCFR discount; pos/neg sign-conditional pointwise), lines 196-200 (regret_sum + strategy_sum FMA-like accumulation). These are the four scalar ops you're replacing. Your `simd.rs` exposes a public API; Agent B refactors `dcfr.rs` to call into it.
6. **NEON intrinsics reference patterns:**
   - `/Users/ashen/Desktop/poker_solver/references/code/postflop-solver/src/utility.rs` lines 79-203 — **AGPL** WASM-SIMD `chunks_exact + remainder` pattern. **Read-only inspiration; no code copy.** You derive the NEON implementation from scratch.
   - Apple NEON intrinsics docs: `vld1q_f64`, `vst1q_f64`, `vaddq_f64`, `vsubq_f64`, `vmulq_f64`, `vfmaq_f64`, `vmaxq_f64`, `vminq_f64`, `vdupq_n_f64`, `vgetq_lane_f64`, `vpaddq_f64`. These are stable in `std::arch::aarch64` since Rust 1.59 (Feb 2022).
7. **PR 4 reference prompt style:** `/Users/ashen/Desktop/poker_solver/docs/pr4_prep/agent_a_prompt.md` (the orchestrator's prior fan-out template).

## Default decisions LOCKED (do not deviate)

These are the amended/clarified PR 8 decisions; where the spec text differs, **these locked defaults win**:

- **Decision 11.1 = NEON always-on for aarch64, no Cargo feature flag.** Gate via `#[cfg(target_arch = "aarch64")]` for the NEON impl and `#[cfg(not(target_arch = "aarch64"))]` for the scalar fallback. Do NOT introduce `#[cfg(feature = "simd")]` — there is no Cargo `simd` feature.
- **Decision 11.8 = Criterion 0.5 as dev-dependency.** `criterion = { version = "0.5", default-features = false, features = ["html_reports"] }`. You add only the dev-dep entry; Agent B writes the actual `benches/cfr_bench.rs` harness.
- **Decision 11.11 = no SVE.** NEON only. Apple M-series does not have SVE. Do NOT add any SVE-targeted code or `target_feature = "sve"` gates.
- **Bit-exact SIMD/scalar equality is the default; ULP ≤ 1 is allowed only on the explicit FMA op** (per spec §7 Layer A "Exception").
- **No `unsafe` outside SIMD intrinsics wrappers.** Every `unsafe { ... }` block in `simd.rs` has a `// SAFETY: ...` comment explaining the alignment + length invariant (NEON 128-bit ops do not require 16-byte alignment on AArch64, but length must be ≥ 2 for one f64x2 load).
- **No new runtime dependencies.** Imports: `std::arch::aarch64::*` (aarch64 only) + stdlib. Optional: `static_assertions` crate may be added as a dev-dep if you want a compile-time NEON-availability check per spec §10 risk 1; **prefer a `#[cfg(...)]` doc-comment over adding a crate**.
- **`Vec4f64` storage:** NEON path uses `float64x2x2_t` (a struct of two `float64x2_t`); scalar fallback uses `[f64; 4]`. Both paths expose the same public method surface.

## Public API contract (signatures Agent B + Agent C depend on)

Export the following from `crates/cfr_core/src/simd.rs`. **Signature drift breaks Agent B's `dcfr.rs` refactor.** Type docs required; `#[inline(always)]` on the per-op methods.

```rust
//! NEON SIMD ops for the DCFR hot loop.
//!
//! Two implementations exist, gated by `target_arch`:
//!
//! - **aarch64 path:** `std::arch::aarch64` intrinsics, 128-bit registers = 2 f64 lanes,
//!   packed two-to-a-struct as `float64x2x2_t` to expose a "4 f64 at a time" surface.
//! - **Scalar fallback:** `[f64; 4]` storage with the same op semantics, used on x86_64
//!   and any non-aarch64 target.
//!
//! **Bit-parity contract:** on the four high-level ops below, the aarch64 and scalar paths
//! produce bit-identical outputs (modulo the explicit FMA op, which may differ at the LSB
//! per spec §7 Layer A allowance). Tested exhaustively in `tests/test_simd.rs`.
//!
//! **Pattern inspired by postflop-solver's `chunks_exact` tail handling
//! (AGPL — read-only); implementation derived from scratch per Apple's NEON intrinsics docs.
//! No code copied.**

#![allow(clippy::needless_range_loop)]

/// 4-wide f64 SIMD vector. Lane-major: lanes 0..=3 correspond to slice indices 0..=3
/// after `load(slice)`.
#[derive(Clone, Copy)]
pub struct Vec4f64(/* private storage: float64x2x2_t on aarch64, [f64;4] on scalar */);

impl Vec4f64 {
    /// Load 4 contiguous f64 lanes from a slice.
    #[inline(always)]
    pub fn load(slice: &[f64; 4]) -> Self;

    /// Store 4 contiguous f64 lanes into a slice.
    #[inline(always)]
    pub fn store(self, slice: &mut [f64; 4]);

    /// Zero vector.
    #[inline(always)]
    pub fn zero() -> Self;

    /// Broadcast a scalar to all 4 lanes.
    #[inline(always)]
    pub fn splat(x: f64) -> Self;

    /// Lanewise add.
    #[inline(always)]
    pub fn add(self, other: Self) -> Self;

    /// Lanewise subtract.
    #[inline(always)]
    pub fn sub(self, other: Self) -> Self;

    /// Lanewise multiply.
    #[inline(always)]
    pub fn mul(self, other: Self) -> Self;

    /// Lanewise fused multiply-add: returns `self + mul_a * mul_b`. (Note: NEON's vfmaq
    /// is `acc + a*b`; mirror that ordering — `self` is the accumulator.)
    #[inline(always)]
    pub fn fma(self, mul_a: Self, mul_b: Self) -> Self;

    /// Lanewise max.
    #[inline(always)]
    pub fn max(self, other: Self) -> Self;

    /// Lanewise min.
    #[inline(always)]
    pub fn min(self, other: Self) -> Self;

    /// Sum of all 4 lanes. Uses a fixed pairwise reduction order so the result is
    /// deterministic across NEON and scalar paths.
    #[inline(always)]
    pub fn horizontal_sum(self) -> f64;
}

// ---- High-level hot-loop ops Agent B + Agent C call from dcfr.rs ----

/// Regret-matching step: compute `max(0, regrets[i])` into `out[i]`, then normalize
/// by the sum of positives. Returns the unnormalized total (= sum of positive regrets,
/// pre-normalize), which the caller compares against 0 to decide between uniform
/// strategy and the normalized output.
///
/// Contract:
/// - If the returned total is ≤ 0, `out` is filled with `1.0 / out.len()` (uniform).
/// - Otherwise, `out[i] = max(0, regrets[i]) / total`.
///
/// `regrets` and `out` must have the same length (asserted; no SIMD on empty).
/// Tail (last `len % 4` elements) handled via scalar.
pub fn regret_matching_simd(regrets: &[f64], out: &mut [f64]) -> f64;

/// Compute `dest[i] += scale * source[i]` (FMA-style accumulation).
/// `source` and `dest` must have the same length. Tail handled via scalar.
pub fn fma_scalar_vec(scale: f64, source: &[f64], dest: &mut [f64]);

/// DCFR sign-conditional discount on regret_sum:
///   for each i: if regrets[i] > 0.0 { regrets[i] *= pos_scale } else { regrets[i] *= neg_scale }.
///
/// Implementation uses lane-mask blend: compute both products, then select via
/// `vbslq_f64` (NEON) or scalar if-else (fallback). This avoids a branch in the
/// hot loop. Tail handled via scalar.
///
/// Per spec §1 "DCFR(α=1.5, β=0, γ=2.0) loop preserved bit-for-bit" — this op
/// is the most numerically sensitive; bit-parity is mandatory.
pub fn discount_positive_negative(regrets: &mut [f64], pos_scale: f64, neg_scale: f64);

/// Discount the strategy_sum vector: for each i: `strategy[i] *= strat_scale`.
/// Tail handled via scalar.
pub fn discount_strategy(strategy: &mut [f64], strat_scale: f64);
```

The four high-level ops are what Agent B's refactored `dcfr.rs` will call. The `Vec4f64` type is exposed for any caller who wants direct lane-level control, but the four ops are the primary contract.

## Implementation rules (per spec §3)

- **Use `std::arch::aarch64`** intrinsics only on the NEON path: `vld1q_f64` (load), `vst1q_f64` (store), `vaddq_f64` (add), `vsubq_f64` (sub), `vmulq_f64` (mul), `vfmaq_f64` (FMA: `a + b*c`), `vmaxq_f64` (max), `vminq_f64` (min), `vdupq_n_f64` (splat), `vgetq_lane_f64` (lane extract), `vpaddq_f64` (pairwise add for horizontal sum), `vbslq_f64` (bit-select for the discount mask), `vcgtq_f64` (greater-than mask).
- **No inline assembly.** Forbidden.
- **`#[cfg(target_arch = "aarch64")]`** gates the NEON impl. **`#[cfg(not(target_arch = "aarch64"))]`** gates a scalar fallback. The scalar fallback is bit-for-bit identical to the NEON path on its outputs (modulo FMA-vs-mul-then-add LSB; see §"Critical correctness items").
- **Tail handling:** for length-N slices where N % 4 != 0, process `N / 4` chunks via SIMD and the last `N % 4` elements via scalar. Pattern (Rust idiomatic, derived from scratch — postflop-solver shows the **architectural shape** only):
  ```rust
  let chunks = slice.chunks_exact_mut(4);
  let remainder = chunks.remainder();  // length 0..3
  for chunk in chunks {
      // SIMD path over &mut [f64; 4]
  }
  // scalar path over remainder
  ```
- **`unsafe` blocks** wrap every NEON intrinsic call. Each block has a `// SAFETY: ...` comment. Example:
  ```rust
  // SAFETY: NEON 128-bit ops do not require 16-byte alignment on AArch64
  // (per ARM ARM A1.7.7); the `chunk` slice is &mut [f64; 4], i.e., 32 bytes
  // contiguous and properly aligned for f64 access.
  let v = unsafe { vld1q_f64(chunk.as_ptr()) };
  let v2 = unsafe { vld1q_f64(chunk.as_ptr().add(2)) };
  ```
- **`horizontal_sum` lane order:** define a single canonical reduction. Recommended: pairwise reduce via `vpaddq_f64(v_lo, v_hi)` then extract lane 0 + lane 1 + add. Document the order in a comment so the scalar fallback uses the same accumulation order (`s = ((a[0] + a[1]) + (a[2] + a[3]))` — left-associative pairwise).
- **No allocation in the hot ops.** No `Vec::new`, no `Box::new` — the four high-level ops take `&[f64]` / `&mut [f64]` slices and operate in-place or write to a caller-provided `&mut [f64]` output.
- **Compile-time NEON-availability assertion:** include a doc comment (or a `static_assertions::const_assert!` if you elect to add `static_assertions` as a dev-dep — prefer the doc comment) noting that NEON is mandatory on aarch64. Per spec §10 risk 1, `target-feature` overrides should not be needed.

## Critical correctness items

### 1. Bit-exact SIMD/scalar parity (spec §7 Layer A; §9 #1)

**Default contract:** every op produces a bit-identical output between the aarch64 NEON path and the scalar fallback (`result_simd[i].to_bits() == result_scalar[i].to_bits()`). NaN must propagate (with the canonical NaN payload pattern preserved per IEEE 754). Inf must propagate (positive + negative). Signed zero (`-0.0` vs `+0.0`) must be preserved.

**FMA allowance:** the `fma` op (and any high-level op that uses `vfmaq_f64`) may differ at the LSB from `mul + add` because `vfmaq_f64` is single-rounded while `mul + add` is double-rounded. Allowance: **ULP ≤ 1**, only on the explicit FMA op.

If the scalar fallback uses `f64::mul_add` (which is also a fused FMA on aarch64 hardware), the LSB will match the NEON path. **Recommended:** the scalar fallback for FMA uses `a + b * c` (separate mul + add) on x86 (where there's no native FMA), and uses `f64::mul_add` on aarch64-scalar-test scenarios. **Simpler recommended:** the scalar fallback always uses `a + b * c` (separate mul + add); the parity test allows ULP ≤ 1 only on this op.

**Test fixture for the parity tests** (your test file builds these directly):
- Aligned 4-element inputs (covering all four lanes).
- Length-7 inputs (one full chunk of 4 + tail of 3).
- Length-3 inputs (no SIMD chunk; pure tail).
- Length-13 inputs (three chunks + tail of 1) — exercises the `chunks_exact` boundary.
- Edge values: `0.0`, `-0.0`, `f64::NAN`, `f64::INFINITY`, `f64::NEG_INFINITY`, smallest denormal (`f64::MIN_POSITIVE / 2.0`).
- Random uniform inputs across 1000 trials (seeded RNG — use `rand::SeedableRng` + `ChaCha8Rng` if available in the dev-deps; otherwise a small LCG written from scratch is fine, document the choice).

### 2. NaN / Inf / signed-zero semantics

- `max(NaN, x)` and `max(x, NaN)` — NEON's `vmaxq_f64` is **NaN-preserving** per ARM ARM A1.4 (returns NaN if either input is NaN, not the "minNum/maxNum" variant). The scalar fallback must match this. Use `f64::max` carefully: **`f64::max` is NaN-quieting** (returns the non-NaN argument if exactly one is NaN), which differs from NEON's behavior. Implement the scalar fallback as:
  ```rust
  fn scalar_max(a: f64, b: f64) -> f64 {
      if a.is_nan() || b.is_nan() { f64::NAN }
      else if a > b { a } else { b }
  }
  ```
- Or: use `f64::from_bits` on the comparison mask directly to mirror NEON behavior bit-for-bit.

- `max(-0.0, +0.0)` — NEON's `vmaxq_f64` returns `+0.0` (the larger sign). The scalar fallback must too. Use `a.to_bits() vs b.to_bits()` after the > check, OR rely on `a > b` returning `false` for `+0.0 > -0.0` (which it does — they compare equal) — in that case, return `b` and ensure `b` is `+0.0`. Document this.

- Signed zero in arithmetic: `(-0.0) + 0.0 = +0.0`. `(-0.0) * 1.0 = -0.0`. These are IEEE 754 defaults and both NEON and scalar f64 obey them. No special handling needed.

### 3. Horizontal sum determinism

Define **one** reduction order. Recommended: left-associative pairwise.
```
sum = ((lane0 + lane1) + (lane2 + lane3))
```
NEON path uses `vpaddq_f64(v_lo, v_hi)` then `vaddq_f64(pairs_lo, pairs_hi)`-style reduction (or equivalent that gives the same associativity); scalar fallback writes the explicit `((a[0] + a[1]) + (a[2] + a[3]))` summation. Test asserts both paths produce bit-identical sums on random inputs.

### 4. Tail-handling FP drift (spec §10 risk 5)

A length-13 regret vector processes 12 elements via SIMD (3 chunks of 4) and 1 element via scalar. Within the SIMD path, the lane order is fixed; within the scalar tail, the order is fixed. The tail is processed **after** the SIMD chunks. The aggregate sum is deterministic, but may differ at the LSB from a pure-scalar (single-stream) implementation. **Your tests assert bit-exact equality between the NEON path and the scalar fallback, both of which use the same chunks-then-tail pattern.** They do NOT assert equality against a "natural single-stream scalar loop" — Agent B's layout-parity test (Layer B at tolerance `1e-12`) absorbs that drift, which is out of your scope.

### 5. `unsafe` discipline (spec §9 #3)

- Every `unsafe { ... }` block in `simd.rs` has a `// SAFETY: ...` comment.
- The `// SAFETY:` comment explains: (a) why NEON intrinsics are safe to call (alignment, length), (b) what invariant the caller is relying on (e.g., "the chunk slice has exactly 4 f64 elements, guaranteed by `chunks_exact_mut(4)`").
- No `unsafe` outside SIMD intrinsic wrappers. The high-level ops (`regret_matching_simd`, etc.) use safe Rust around the inner SIMD calls.
- `#[deny(unsafe_op_in_unsafe_fn)]` at the top of the file is good hygiene (forces explicit `unsafe { ... }` even inside `unsafe fn`).

### 6. Microbench acceptance gate (spec §8 Agent A acceptance)

You include a Criterion bench `bench_regret_matching_simd_vs_scalar` targeting a 1024-element regret vector. The bench measures wall-clock for both the NEON path and the scalar fallback. **Acceptance: SIMD path is ≥3× faster than scalar fallback.** If <3×, either (a) the SIMD implementation is wrong (revisit), (b) the compiler is auto-vectorizing the scalar fallback (use `#[inline(never)]` on the scalar fallback to defeat this, OR confirm via `cargo asm` that the scalar fallback emits scalar instructions). Document your finding in the report.

This bench lives at the end of `simd.rs` as a `#[cfg(feature = "bench")]`-gated module OR (preferred) as a `crates/cfr_core/benches/simd_microbench.rs` file. **If you put it in a separate `benches/simd_microbench.rs` file, that's a new file you own**; the spec's "Agent B owns benches/" guidance refers to the main `cfr_bench.rs` end-to-end harness, not to per-module microbenches. **Recommended:** put the microbench in `crates/cfr_core/benches/simd_microbench.rs` with `criterion_group!` + `criterion_main!`.

## Reference pattern

`/Users/ashen/Desktop/poker_solver/references/code/postflop-solver/src/utility.rs` lines 79-203 demonstrates the `chunks_exact + remainder` pattern for WASM SIMD (`std::arch::wasm32`, **AGPL — read-only inspiration**). The structure transfers directly to NEON: same `load → op → store → tail-scalar` shape. **Your implementation is derived from scratch** per Apple's NEON intrinsics docs; no code is copied from postflop-solver.

The MIT-licensed vectorized showdown evaluator in `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/vector_eval.cpp` is the **safe-to-port** reference for any future vector-eval extension; per spec §3, PR 8 may port lines 90-131 with MIT attribution. **This is NOT part of your current scope** — your scope is the four hot-loop ops only. If you encounter a need for vector-eval, defer it to a follow-up PR.

## License-aware sourcing

**You may NOT copy code from AGPL sources:**
- `references/code/postflop-solver/` — **AGPL v3**. Read-only inspiration. If you cite a pattern, do so in a docstring comment that says "Pattern inspired by; no code copied" and derive your implementation from scratch.
- `references/code/TexasSolver/` — **AGPL v3**. Same rule.

**You may copy / port verbatim with attribution from MIT/Apache sources:**
- `references/code/noambrown_poker_solver/` (**MIT**) — out of scope for this prompt, but available for follow-ups.
- `references/code/slumbot2019/` (**MIT**) — out of scope.

**You may NOT extrapolate from training data.** If you "remember" a NEON intrinsics sequence or an FMA-vs-mul-then-add trick and want to use it, ground it in either the locally-cited reference above or the PR 8 spec / Apple's NEON intrinsics docs.

**Module docstring license attribution:** include this comment at the top of `simd.rs`:
```rust
//! Pattern inspired by postflop-solver's `chunks_exact` WASM-SIMD tail handling
//! (AGPL — read-only); implementation derived from scratch per Apple's NEON
//! intrinsics docs. No code copied.
```

## Quality bar

- **`cargo test --release test_simd`** passes on aarch64-apple-darwin (verify on your local MacBook). All ~30-40 test cases in `test_simd.rs` (the exhaustive parity table, edge values, random trials) pass with bit-exact equality on non-FMA ops and ULP ≤ 1 on the FMA op.
- **`cargo clippy --all-targets -- -D warnings`** clean. No `unsafe`-related lints. No `clippy::missing_safety_doc` (because you DID provide SAFETY comments).
- **`cargo fmt`** clean (`cargo fmt --check`).
- **`cargo build --release --target aarch64-apple-darwin`** succeeds without manual `RUSTFLAGS` (per spec §10 risk 1).
- **No new runtime deps in `Cargo.toml`.** Only `criterion = "0.5"` under `[dev-dependencies]`. Optional dev-dep: `static_assertions` (prefer doc comment instead).
- **Microbench shows ≥3× speedup** of `regret_matching_simd` over the scalar fallback on a 1024-element regret vector. Document in your report.
- **Code size budget: ~600-900 LOC** combined across `simd.rs` (~400-600 LOC for the NEON + scalar paths + high-level ops) and `test_simd.rs` (~200-300 LOC for the exhaustive parity tests). Stay within budget; do not over-engineer.

## Reference-first rule

Before any technical claim, citation, or formula, check the local references. Never extrapolate from training data when a local authoritative source exists. The reference index is `/Users/ashen/Desktop/poker_solver/references/README.md` — skim it for "SIMD", "NEON", "vectorization" entries.

Apple's NEON intrinsics documentation is your primary technical source (cite the intrinsic name + arity, e.g., `vfmaq_f64(acc, a, b) -> a + b * c`). The ARM ARM (Architecture Reference Manual) is the authoritative spec for NaN propagation semantics — cite "ARM ARM A1.4" or equivalent when documenting NaN behavior.

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Format + lint
cargo fmt --check --manifest-path crates/cfr_core/Cargo.toml
cargo clippy --manifest-path crates/cfr_core/Cargo.toml --all-targets -- -D warnings

# 2. Build (release, aarch64 native)
cargo build --release --manifest-path crates/cfr_core/Cargo.toml

# 3. Run YOUR tests (bit-exact parity, NaN/Inf/denormal, random trials)
cargo test --release --manifest-path crates/cfr_core/Cargo.toml --test test_simd 2>&1 | tail -30

# 4. Run the existing test suite to confirm no regressions
cargo test --release --manifest-path crates/cfr_core/Cargo.toml 2>&1 | tail -20

# 5. Run your standalone microbench
cargo bench --manifest-path crates/cfr_core/Cargo.toml --bench simd_microbench 2>&1 | tail -30
# Confirm: SIMD path is ≥3× faster than scalar fallback on the 1024-element vector.

# 6. Smoke test the four high-level ops manually
cat > /tmp/simd_smoke.rs << 'EOF'
// (You can also do this inside a unit test within simd.rs.)
use poker_solver_cfr_core::simd::*;

fn main() {
    // regret_matching_simd
    let regrets = vec![1.0, -2.0, 3.0, 0.5, 0.0, -1.0, 2.5];
    let mut out = vec![0.0; 7];
    let total = regret_matching_simd(&regrets, &mut out);
    assert!(total > 0.0);
    let sum: f64 = out.iter().sum();
    assert!((sum - 1.0).abs() < 1e-12, "expected sum=1.0, got {}", sum);

    // fma_scalar_vec
    let source = vec![1.0, 2.0, 3.0, 4.0, 5.0];
    let mut dest = vec![10.0; 5];
    fma_scalar_vec(2.0, &source, &mut dest);
    assert_eq!(dest, vec![12.0, 14.0, 16.0, 18.0, 20.0]);

    // discount_positive_negative
    let mut regrets = vec![1.0, -2.0, 3.0, -0.5, 0.0];
    discount_positive_negative(&mut regrets, 0.5, 0.0);
    // 0.0 case: 0.0 is not > 0.0 in our definition (uses strict > 0); scaled by neg_scale=0
    assert_eq!(regrets, vec![0.5, 0.0, 1.5, 0.0, 0.0]);

    // discount_strategy
    let mut strategy = vec![10.0, 20.0, 30.0];
    discount_strategy(&mut strategy, 0.5);
    assert_eq!(strategy, vec![5.0, 10.0, 15.0]);

    println!("simd smoke OK");
}
EOF
# (or invoke via cargo run --example simd_smoke if you add an example file —
#  optional, but a quick sanity check.)
```

If any of the above fails, fix the issue before reporting done. If a parity test reveals an ambiguity in the spec (e.g., "should `discount_positive_negative` treat `+0.0` as positive or non-positive?" — the spec uses `> 0` per `dcfr.rs:122-128`, so `+0.0` is NON-positive, scaled by `neg_scale`), **stop and flag it** in your report; do not silently choose.

## Report back format

When done, write a concise report (≤300 words) covering:

1. Files created with line counts (`simd.rs`, `test_simd.rs`, `benches/simd_microbench.rs` if created); files modified (`lib.rs` line delta, `Cargo.toml` line delta).
2. Microbench result: SIMD speedup over scalar fallback on the 1024-element vector (mean ± stddev). If <3×, explain why.
3. Any spec amendment you made or contract drift you flagged (e.g., "the spec says `vmaxq_f64` is NaN-preserving but the scalar fallback's natural `f64::max` is NaN-quieting; I implemented `scalar_max` to mirror NEON semantics — verify in §7 Layer A test").
4. Verification command output (paste tails of clippy, test, and bench).
5. NaN / Inf / signed-zero handling decisions — confirm all six edge values are tested (`0.0`, `-0.0`, `NaN`, `+Inf`, `-Inf`, smallest denormal).
6. License attributions added (the module docstring comment).
7. Any open question you couldn't resolve from the spec / PLAN / autonomous log — flag for human review.
