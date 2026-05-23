# PR 8 spec — NEON SIMD + cache-blocking + public chance sampling in Rust

**Updated 2026-05-21 per consistency review:** (a) §6 "Files to modify" now explicitly authorizes the `HUNLConfig.use_pcs: bool = False` schema extension on the Python side (PR 6 pre-emptively mirrors this in its Rust `HUNLConfig` — see PR 6 §4.1 amended note); resolves consistency-review I6. (b) §2 spot 3's bucket notation "50/64 buckets" clarified as a typo / shorthand and replaced with the documented tier "64/32/16" (resolves I7). (c) §7 diff-test tolerance language reaffirms alignment with the PR 6 / PR 7 / PR 9 `5e-3` per-action + `1e-3` per-spot game-value cluster (resolves I3 for PR 8's Layer D Python end-to-end test).

## 1. Goal

Performance optimization of the Rust HUNL solver landed by PR 6. **Strict performance work — no algorithmic change.** Three orthogonal optimizations layered on top of the unoptimized Rust DCFR baseline:

1. **ARM NEON 128-bit SIMD** — vectorize the regret-matching / strategy-accumulation hot loops via `std::arch::aarch64` intrinsics (4-wide f64).
2. **Cache-blocked infoset storage** — replace `HashMap<String, InfosetData>` (the current layout in `crates/cfr_core/src/dcfr.rs:65`) with flat SoA arrays of `(regret_sum, strategy_sum)` indexed by `(tree_node_id, bucket_id)`.
3. **Public chance sampling (PCS)** — sample one public chance outcome per iteration instead of enumerating all 47–49 turn / 45–47 river cards; aggregate over iterations with importance correction.

**Target speedup:** **10× minimum**, **50× stretch** over the unoptimized Rust baseline on the standard HUNL flop solve (Section 2 spot 4). Hard gate at 10×: if not met, PR does not ship.

**Non-goals:**

- No algorithmic change beyond the three opt'ns. The DCFR(α=1.5, β=0, γ=2.0) loop is preserved bit-for-bit on the non-PCS path; PCS path switches to β=0.5 (see Section 9 item 4 and `references/papers/_INDEX.md:38`).
- No new game support — HUNL only (Kuhn / Leduc kept only as parity tests).
- No GPU. No new multi-threading beyond rayon if PR 6 already enabled it.
- No new card abstraction — re-uses PR 4's EMD bucketing as-is.
- No node locking, no exploitative play, no real-time depth-limited search.
- **No `unsafe` outside SIMD intrinsics wrappers.** Every `unsafe` block in `simd.rs` carries a `// SAFETY:` comment; the rest of the codebase remains safe Rust.

## 2. Baseline measurement (first PR action)

**PR 6 produces benchmark data.** PR 8's first action is to capture the unoptimized baseline so all speedup claims are reproducible. The bench harness itself is **created in this PR** under `benches/cfr_bench.rs` (Criterion) — PR 6's bench setup, if any, is treated as a starting point, not a contract.

**Bench spots:**

| # | Spot | Iterations | Purpose | Expected (scalar baseline) |
|---|---|---|---|---|
| 1 | Kuhn (12 infosets) | 10,000 | Sanity floor; SIMD effect is noise | <1 s |
| 2 | Leduc (288 infosets) | 10,000 | Small but vectorizable | 1–5 s |
| 3 | HUNL flop subgame, simple (`As Kc 7d`), 3 bet sizes, 100 BB, **64/32/16 buckets** (tier-2 from PLAN.md §1) | 1,000 | Primary target | 1–3 min |
| 4 | HUNL flop subgame, standard (`Js 9h 6d`), 5 bet sizes, 100 BB, 256/128/64 buckets | 1,000 | Stretch target | 5–15 min |

These match PLAN.md §1 "Performance targets" — Kuhn <1 sec, Leduc <10 sec, HUNL postflop simple flop 3 sizes 1–3 min, standard flop 5 sizes 5–15 min.

**Methodology:**

- Run via `cargo bench --release` on `aarch64-apple-darwin` only (Apple M-series).
- Warm-up: 5 iterations. Sample: 20 iterations. Criterion reports mean ± stddev.
- Capture machine state: macOS version, model identifier, thermal state at run start.
- Output: `benches/baseline.json` (committed), header includes machine + date + commit hash of the run.
- Subsequent PRs compare against this baseline (PLAN.md §4 "Perf check — flag regressions >10%").

**No baseline = no PR 8.** The first task of Agent B is to run the unoptimized solver, capture `baseline.json`, and commit it before the optimization work begins. The baseline lives at `benches/baseline.json` in the repo root (so future PRs can find it without spelunking).

## 3. NEON SIMD module (`crates/cfr_core/src/simd.rs`)

### Scope of vectorization

The hot loop in DCFR is regret-matching + strategy-accumulation per infoset, currently scalar in `crates/cfr_core/src/dcfr.rs:83-100, 111-134, 196-200`. Four ops dominate:

1. **`max(0, regret)` over a vector of f64** — needed in `get_strategy` (`dcfr.rs:83-100`).
2. **Normalize-then-scale** (divide each element by the sum of positive regrets) — also `get_strategy`.
3. **FMA-like accumulation**: `regret_sum[a] += opp_reach * (action_value[a] - node_value)` and `strategy_sum[a] += own_reach * strategy[a]` (`dcfr.rs:196-200`).
4. **DCFR sign-conditional discount**: pointwise `r *= pos_scale` if `r > 0` else `r *= neg_scale` (`dcfr.rs:122-128`).

### API

```rust
// Opaque newtype around float64x2x2_t (NEON has 128-bit registers; 2 lanes = 2 f64).
pub struct Vec4f64(...);

impl Vec4f64 {
    #[inline(always)] pub fn load(slice: &[f64; 4]) -> Self;
    #[inline(always)] pub fn store(self, slice: &mut [f64; 4]);
    #[inline(always)] pub fn zero() -> Self;
    #[inline(always)] pub fn splat(x: f64) -> Self;
    #[inline(always)] pub fn add(self, other: Self) -> Self;
    #[inline(always)] pub fn sub(self, other: Self) -> Self;
    #[inline(always)] pub fn mul(self, other: Self) -> Self;
    #[inline(always)] pub fn fma(self, mul: Self, add: Self) -> Self;   // self + mul*add
    #[inline(always)] pub fn max(self, other: Self) -> Self;
    #[inline(always)] pub fn min(self, other: Self) -> Self;
    #[inline(always)] pub fn horizontal_sum(self) -> f64;
}

// Higher-level ops the DCFR loop calls directly.
pub fn regret_matching_simd(regrets: &[f64], out: &mut [f64]) -> f64;     // returns total
pub fn fma_scalar_vec(scale: f64, source: &[f64], dest: &mut [f64]);
pub fn discount_positive_negative(regrets: &mut [f64], pos_scale: f64, neg_scale: f64);
pub fn discount_strategy(strategy: &mut [f64], strat_scale: f64);
```

### Implementation rules

- **Use `std::arch::aarch64`** intrinsics only: `vld1q_f64`, `vst1q_f64`, `vaddq_f64`, `vsubq_f64`, `vmulq_f64`, `vfmaq_f64`, `vmaxq_f64`, `vminq_f64`, `vdupq_n_f64`, `vgetq_lane_f64`, `vpaddq_f64` (for horizontal sum).
- **No inline assembly.** Forbidden.
- **`#[cfg(target_arch = "aarch64")]`** gates the NEON impl. **`#[cfg(not(target_arch = "aarch64"))]`** gates a scalar fallback. The scalar fallback is bit-for-bit identical to the NEON path on its outputs (modulo FMA-vs-mul-then-add LSB; see Section 7).
- **Tail handling:** for length-N slices where N % 4 != 0, process `N / 4` chunks via SIMD and the last `N % 4` elements via scalar. Pattern: `chunks_exact(4).remainder()` (the same pattern used in `references/code/postflop-solver/src/utility.rs:118, 138, 182, 201`).
- **`unsafe` blocks** every NEON intrinsic call. Each block has a `// SAFETY: ...` comment explaining the alignment + length invariant (NEON 128-bit ops do not require 16-byte alignment on AArch64, but length must be ≥ 4 in the SIMD path).
- **Feature flag:** `target_arch` gate is sufficient; no Cargo `simd` feature is introduced (per Decision 11.1).

### Reference pattern

`references/code/postflop-solver/src/utility.rs:79-203` demonstrates the `chunks_exact + remainder` pattern for WASM SIMD (`std::arch::wasm32`, AGPL — read-only inspiration). The structure transfers directly to NEON: same `load → op → store → tail-scalar` shape. **Implementation derived from scratch** per Apple's NEON intrinsics docs; no code is copied from postflop-solver.

Vectorized showdown evaluation in `references/code/noambrown_poker_solver/cpp/src/vector_eval.cpp:90-131` (MIT) is the **safe-to-port** reference. Key patterns:

- **Prefix-sum over sorted opponent strengths** (`vector_eval.cpp:97-103`):
  ```cpp
  scratch.prefix[0] = 0.0;
  for (int i = 0; i < opp_count; ++i) {
      scratch.prefix[i + 1] = scratch.prefix[i] + opp_weights[cache.sorted_indices[i]];
  }
  ```
  This pattern is reused (verbatim algorithm, re-derived code) when PR 8 computes range-vs-range showdown values.
- **Per-hand win/tie/loss aggregation via blocked-index lists** (`vector_eval.cpp:111-131`): for each hand, look up `(start, end)` in the sorted-strength prefix sum, subtract weight contributions from blocked opponents (those sharing a card). PR 8 mirrors this for the river-leaf evaluator under SIMD.

PR 8 may port `vector_eval.cpp` lines 90–131 to Rust with MIT attribution in the file header. Other repo files (especially `postflop-solver` and `TexasSolver`, both AGPL) are pattern-only.

## 4. Cache-blocked infoset layout (`crates/cfr_core/src/layout.rs`)

### Motivation

The current infoset store (`dcfr.rs:65`) is `HashMap<String, InfosetData>`. For HUNL postflop with 5 bet sizes and standard buckets (256/128/64), the tree has ~10K nodes. With per-bucket infosets, total count is ~640K – 1.6M. Each `InfosetData` holds two `Vec<f64>` (separate heap allocations) and a `String` key (further heap allocation). The hash table itself adds bucket arrays and probe chains.

**Costs:**

- String-key hashing per access.
- Pointer chasing through the hash table.
- Two separate cache lines per infoset (regret_sum vector + strategy_sum vector).
- No spatial locality between adjacent buckets of the same tree node.

### Replacement layout (SoA primary path)

```rust
pub struct FlatInfosetStore {
    /// Tree-node ID → starting index into `regret_sum` / `strategy_sum`.
    pub node_offset: Vec<u32>,
    /// Tree-node ID → number of actions at that node.
    pub node_actions: Vec<u8>,
    /// Tree-node ID → number of buckets (infosets per node).
    pub node_buckets: Vec<u32>,
    /// Tree-node ID → last iteration this node's infosets were discounted at.
    /// Node-granularity (every bucket of a node is touched in the same iter).
    pub node_last_discount: Vec<u32>,

    /// Flat storage, indexed by `node_offset[n] + bucket_id * node_actions[n] + action`.
    pub regret_sum: Vec<f64>,
    pub strategy_sum: Vec<f64>,
}
```

### Indexing & strides

- A single bucket's action regrets are contiguous in memory (stride = `num_actions`).
- A single tree node's bucket × action matrix is contiguous (size = `num_buckets * num_actions`).
- The SIMD hot path (regret-matching over one bucket's actions) sees aligned, contiguous data — exactly what NEON wants.

### Block size

- M1 P-core L1 data cache is **192 KB**. L2 unified is 128 KB per core (shared with L1 on E-cores).
- Working set per inner loop step: 1 bucket × 6 actions × 8 B (regret_sum) + 1 bucket × 6 actions × 8 B (strategy_sum) + ~6 actions of strategy buffer = ~96 B per bucket.
- **Block size: 64 infosets per cache "block"** → 64 × 96 B = ~6 KB. Fits comfortably in L1 alongside the strategy + reach buffers (≤ ~1 KB).
- Block size is a `const BLOCK_SIZE: usize = 64;` in `layout.rs` — easy to retune after profiling.

### SoA vs AoS — decision

**SoA primary path.** Rationale:

- The hot loop is per-bucket regret-matching + accumulation, which is N consecutive f64s per bucket — SoA storage of `regret_sum[bucket_id × num_actions .. bucket_id × num_actions + num_actions]` is the same memory layout SIMD wants.
- AoS would require either gather/scatter (no efficient NEON gather for f64) or a row transpose per access (costly).
- **Open question 11.4:** if Agent B's microbench shows AoS wins on a hot path we missed (e.g., "iterate all infosets of a node to compute a per-node sum"), the layout is configurable via a private feature flag and the spec is amended.

### Lookup

`HashMap::get(&key)` → `node_offset[node_id] + bucket_id * num_actions`. The tree walker already carries `node_id` (it's traversing tree nodes by index, not by key). The `bucket_id` comes from PR 4's abstraction (cached per hand pair at infoset-key construction time).

**Net lookup cost:** O(1) array indexing (one multiply + one add). Replaces O(1) amortized hash lookup with hashing + probing. Profile to confirm net win; preliminary estimate is 5–10× lookup speedup, but lookup is < 10% of solver cost (hot ops dominate).

### Migration path

PR 8 adds `FlatInfosetStore` alongside the existing `HashMap<String, InfosetData>`. During development, both paths coexist (selectable via a builder flag). The diff test (Section 7 Layer B) runs both paths on Kuhn + Leduc and asserts numerical parity to 1e-12. Once parity is confirmed and benches pass, the HashMap path is deleted in the same PR.

### API breakage

The old `HashMap<String, InfosetData>` is removed. Any caller that took `&mut InfosetData` is rewritten to take `&mut [f64]` slices (regret + strategy_sum). Files affected:

- `crates/cfr_core/src/dcfr.rs` — main consumer; entirely rewritten on the layout side.
- `crates/cfr_core/src/solver.rs` — top-level wrapper; minor API surface changes.
- `crates/cfr_core/src/lib.rs` — re-exports updated.
- `crates/cfr_core/src/{kuhn,leduc}.rs` — unchanged (they consume DCFR via the Game trait; they don't see the storage layout).

## 5. Public chance sampling (`crates/cfr_core/src/pcs.rs`)

### Algorithm

Following the public chance sampling variant of MCCFR. The canonical reference is Johanson et al. 2012 (not in our local library); the closest available references in our repo are:

- `references/papers/cfrplus_tammelin_2014.pdf` — Tammelin 2014 references PCS as a prior MCCFR variant (`_INDEX.md:11`).
- `references/papers/libratus_brown_2017_supplement.pdf` — Brown 2017 supplement gives full pseudocode for ES-MCCFR with regret pruning (`_INDEX.md:179-181`), the closest implemented variant.
- `references/code/noambrown_poker_solver/cpp/src/mccfr.cpp:229-302` — MIT-licensed ES-MCCFR implementation; PR 8's PCS can structurally mirror this (different sampling target but same recursive shape).

### Operation

For HUNL postflop:

- **Standard DCFR (the current path):** at each chance node (turn deal: 47 cards available; river deal: 46 cards available), enumerate every outcome. For each outcome, recurse with the full 1326×1326 hand combo state. Cost per chance node = 47× or 46× one recursive subtree.
- **PCS:** at each iteration, **sample one public outcome** at each chance node according to the chance distribution. Recurse only into the sampled outcome. **Aggregate over iterations** — at iteration t we explored a different (turn, river) pair than at iteration t-1.

### Cost / convergence trade-off

- **Cost reduction per chance node visit:** ~47× (turn) and ~46× (river) → ~50× per chance node.
- **Convergence rate penalty:** PCS is an unbiased estimator (with importance correction), but variance is higher. Empirically (Johanson 2012, cited in Tammelin 2014): ~5× more iterations needed to reach the same exploitability.
- **Net speedup:** ~50× / 5× = **~10× per equivalent-quality iteration**.

This is the per-chance-node speedup multiplier; combined with NEON SIMD (~3–4× inner-loop) and cache blocking (~2× memory ops), the total speedup target of 10–50× is plausible.

### Hand pairs stay vector-form

PCS samples **public** chance only. **Private chance** (each player's 2 hole cards = 1326 combos per player) is still enumerated — vector-form CFR over hand-pair reach probabilities. This is what distinguishes PCS from full ES-MCCFR (which samples both public and private).

### Importance weighting

If we sample outcome `c` from `K` outcomes with uniform probability `1/K`, the importance weight `w = K` corrects the estimator:

```
E[w * v(c)] = sum_c (1/K) * K * v(c) = sum_c v(c)
```

**The convergence-to-Nash guarantee requires this importance correction.** Skipping it gives a biased estimator that does not converge to the unsampled equilibrium. Tested explicitly via a negative-control test (Section 7).

### Sampler interface

```rust
pub struct PCSSampler {
    rng: ChaCha8Rng,  // deterministic; seedable for reproducibility & diff parity.
    // Per-chance-node cached outcome lists (so we don't re-derive them per iter).
    public_outcomes_per_node: HashMap<TreeNodeId, Vec<(Card, f64)>>,
}

impl PCSSampler {
    pub fn new(seed: u64) -> Self;

    /// Sample one public outcome at the given chance node.
    /// Returns the sampled outcome and the importance weight `K` (= number of outcomes).
    pub fn sample_public(&mut self, node: TreeNodeId) -> (Card, f64);
}
```

### DCFR-PCS parameter compatibility

From `_INDEX.md:38`:

> Caveat: β ≤ 0 makes regrets on suboptimal actions drift toward -infinity, which breaks regret-based pruning. If you want pruning compatibility, use β = 0.5 instead (paper shows this still works well).

PCS introduces sampling variance, which interacts badly with β=0 (where negative regrets are reset to 0 each iteration — they don't accumulate, so the sampling noise has nowhere to go). PR 8's PCS path **internally switches β=0 → β=0.5** when `use_pcs=true`. Documented in `pcs.rs` module docstring. Tested explicitly (Section 7 Layer C).

### Default

**Opt-in for v1** (`HUNLConfig.use_pcs: bool = False`). Rationale: PCS is the riskiest of the three optimizations (statistical, not numerically identical); we want a clean rollback path. Switch to default in a follow-up PR after measuring PCS-vs-full convergence on real flop spots.

## 6. Files to create / modify

### Create

| Path | Purpose | Owner |
|---|---|---|
| `crates/cfr_core/src/simd.rs` | NEON `Vec4f64` + 4 hot-loop ops + scalar fallback | Agent A |
| `crates/cfr_core/src/layout.rs` | Flat-array `FlatInfosetStore` + tree-node index | Agent B |
| `crates/cfr_core/src/pcs.rs` | Public chance sampler + importance weighting | Agent C |
| `tests/test_simd.rs` (Rust integration test) | SIMD vs scalar parity (incl. NaN / Inf / denormals) | Agent A |
| `tests/test_layout.rs` (Rust integration test) | Flat-array storage parity vs HashMap on Kuhn + Leduc | Agent B |
| `tests/test_pcs.rs` (Rust integration test) | PCS convergence to same Leduc Nash value across 5 seeds | Agent C |
| `tests/test_pr8_convergence.py` (Python) | End-to-end: optimized Rust ≈ Python ref on river spot | Agent B (lead) |
| `benches/cfr_bench.rs` | Criterion harness with the 4 spots from Section 2 | Agent B |
| `benches/baseline.json` | Captured pre-optimization wall-clock; committed once | Agent B |

### Modify

| Path | Change | Owner |
|---|---|---|
| `crates/cfr_core/src/dcfr.rs` | Swap `HashMap` → `FlatInfosetStore`; route hot ops through `simd::*`; gate PCS via `use_pcs` field on the solver | Agent B + Agent C (PCS hook) |
| `crates/cfr_core/src/hunl_solver.rs` (assumed landed by PR 6) | Add `use_pcs: bool` config; call PCS sampler at chance nodes when enabled | Agent C |
| `crates/cfr_core/src/lib.rs` | `mod simd; mod layout; mod pcs;` + re-exports | Agent A (just module declarations) |
| `crates/cfr_core/src/solver.rs` | Adapter for new infoset store API | Agent B |
| `crates/cfr_core/Cargo.toml` | Add `[dev-dependencies] criterion = "0.5"` | Agent A |
| **`poker_solver/hunl.py`** | **Add `use_pcs: bool = False` field to `HUNLConfig` dataclass** (Python schema extension authorized here; pre-mirrored in PR 6 §4.1 Rust `HUNLConfig` to avoid a future migration). | Agent C |
| `pyproject.toml` | **No change required** — Cargo `target_arch` gating doesn't propagate through maturin; document in PR notes that `maturin develop --release` is the build command. If Decision 11.1 flips to a `simd` Cargo feature, then `[tool.maturin] features = ["pyo3/extension-module", "simd"]` is added. | (none in default path) |

**Note on consistency-review I6:** PR 8 explicitly authorizes the `HUNLConfig.use_pcs: bool = False` field extension on the Python side. PR 6 §4.1 pre-emptively includes the field in its Rust `HUNLConfig` mirror (see PR 6 amended note), so PR 6 and PR 8 land in either order without a schema-migration step. Default is `False` (opt-in) per §5 "Default" and §11 #2.

### Note on PR 6 dependence

PR 6 (HUNL postflop port to Rust) has **not yet landed** at PR 8 spec write-time. The "modify `hunl_solver.rs`" entry assumes PR 6 lands a file with that name and a `solve(config)` method. If PR 6 names the file differently (e.g., `hunl.rs` or `postflop.rs`), Agent C's integration is rewritten in a ~1-day adaptation step. The integration point is small (~50 LoC) — gracefully reconcilable.

## 7. Differential test commitment

PR 8 must produce numerically identical regret + strategy values on the **non-PCS path** vs the pre-PR-8 scalar baseline. The **PCS path** is allowed to differ (sampling is statistical) but the **average strategy at convergence must agree within tolerance**. Three test layers:

### Layer A — SIMD parity (numerically identical)

File: `tests/test_simd.rs`.

Exhaustively tests `Vec4f64` ops against the scalar equivalent on:

- Aligned 4-element inputs.
- Length-7 inputs (tail handling kicks in).
- Edge values: `0.0`, `-0.0`, `f64::NAN` (NaN must propagate), `f64::INFINITY`, `f64::NEG_INFINITY`, smallest denormal.
- Random uniform inputs across 1000 trials (seeded).

**Pass criterion:** `result_simd[i].to_bits() == result_scalar[i].to_bits()` (exact bit equality).

**Exception:** if a future compiler emits `vfmaq_f64` for the scalar path where the spec uses separate multiply+add, the FMA result may differ at the LSB (Inf-precision FMA vs round-after-multiply). Allowance: **`ULP ≤ 1`**, only on the explicit FMA op. Default is exact equality for all non-FMA ops.

### Layer B — Layout parity (numerically identical)

File: `tests/test_layout.rs`.

Runs Kuhn (12 infosets, 1K iter) and Leduc (288 infosets, 10K iter) on both `HashMap`-backed DCFR and `FlatInfosetStore`-backed DCFR with identical inputs and identical iteration counts.

**Pass criterion:** per-infoset average strategy probabilities match within `1e-12` (absorbs FP-noise from different summation orders in tail handling; see Section 10 risk 5).

### Layer C — PCS convergence (statistical)

File: `tests/test_pcs.rs`.

Runs Leduc with `iterations=10_000` (PCS path) vs `iterations=2_000` (full path) and checks Nash-value parity.

**Pass criteria:**

- Per-action mean absolute error across all infosets < `5e-3` (matches `pr7_spec.md` §1 and `tests/test_leduc_diff.py` tolerance).
- Per-action max absolute error < `2e-2` (loose; PCS at finite iterations has tail variance).
- Across 5 distinct seeds: **mean** of per-seed mean-errors < `5e-3`.

**Negative control:** a separate test removes the importance weight from PCS and asserts the test **fails** (confirming the tolerance is calibrated and PCS is doing real work). This prevents silent regressions where someone accidentally drops the weight.

### Layer D — Python end-to-end

File: `tests/test_pr8_convergence.py`.

Runs the existing `tests/test_dcfr_diff.py` river-spot test but with the **optimized Rust solver** (cache-blocked + SIMD; PCS off by default). Asserts Python reference ↔ optimized Rust agreement within `5e-3` — matches the existing tolerance.

**No tolerances are weaker than the existing Python ↔ Rust diff test.** PR 8 must not silently regress correctness in exchange for speed.

## 8. Three-agent fan-out plan

Same parallelization pattern as PR 3, 3.5, 4, 7. Three concurrent agents writing to disjoint files; integration step after all three land.

### Agent A — SIMD module + scalar fallback + tests

**Owns:** `crates/cfr_core/src/simd.rs`, `tests/test_simd.rs`, `Cargo.toml` dev-dep additions (criterion), the `mod simd;` line in `lib.rs`.

**Does NOT touch:** `dcfr.rs`, `layout.rs`, `pcs.rs`, `hunl_solver.rs`, any `benches/*` file.

**Deliverables:**

- `Vec4f64` type (NEON storage on aarch64; scalar `[f64; 4]` storage on x86 fallback).
- Four high-level ops: `regret_matching_simd`, `fma_scalar_vec`, `discount_positive_negative`, `discount_strategy`.
- Scalar fallback gated by `#[cfg(not(target_arch = "aarch64"))]`.
- Exhaustive `test_simd.rs` per Section 7 Layer A.

**Acceptance:**

- `cargo test --release test_simd` passes on aarch64-apple-darwin.
- `cargo clippy --all-targets -- -D warnings` clean.
- Standalone microbench (Agent A includes a Criterion bench targeting a 1024-element regret vector) shows ≥3× speedup of `regret_matching_simd` over the scalar fallback. If the speedup is < 3×, the SIMD implementation is wrong or the compiler is already auto-vectorizing the scalar; Agent A profiles and explains.

### Agent B — Cache-blocked layout + DCFR integration + bench harness + baseline

**Owns:** `crates/cfr_core/src/layout.rs`, `tests/test_layout.rs`, `tests/test_pr8_convergence.py`, modifies `crates/cfr_core/src/dcfr.rs`, modifies `crates/cfr_core/src/solver.rs`, creates `benches/cfr_bench.rs`, captures and commits `benches/baseline.json`.

**Does NOT touch:** `simd.rs`, `pcs.rs`, `hunl_solver.rs`.

**Deliverables:**

- `FlatInfosetStore` per Section 4.
- Refactored DCFR loop using the new store; calls Agent A's SIMD ops via the public API in `simd.rs`. DCFR's call sites for `get_strategy`, the regret update, the strategy_sum update, and the lazy discount all route through `simd::*`.
- `cfr_bench.rs` with the 4 Section 2 spots.
- **Baseline capture step** (run before any optimization work): run the bench on PR 6's unoptimized code, commit `benches/baseline.json` with machine + date metadata.
- Layout parity test per Section 7 Layer B.
- Python end-to-end test per Section 7 Layer D.

**Acceptance:**

- Kuhn + Leduc tests pass (existing test suite, no regressions).
- Layout parity test passes to `1e-12`.
- `cargo bench` runs to completion; `benches/baseline.json` exists and is committed.
- Python end-to-end test passes within `5e-3` tolerance.

### Agent C — Public chance sampling + hunl_solver integration + PCS tests

**Owns:** `crates/cfr_core/src/pcs.rs`, `tests/test_pcs.rs`, modifies `crates/cfr_core/src/hunl_solver.rs` (PR 6's file; if not present, Agent C stubs the integration point and the PR is split into 8a/8b).

**Does NOT touch:** `simd.rs`, `layout.rs`. Lightly touches `dcfr.rs` only for the `use_pcs` config-flag wiring (Agent B owns the DCFR side of this; Agent C provides the pcs.rs API).

**Deliverables:**

- `PCSSampler` per Section 5, with `ChaCha8Rng` for cross-platform deterministic seeding.
- Importance weighting per Section 5.
- Opt-in `use_pcs: bool` config on `HUNLConfig` / `HUNLSolver`.
- DCFR-PCS parameter switch (β=0 → β=0.5 when `use_pcs=true`).
- Negative-control test (removes importance weight, asserts failure).
- Leduc convergence test across 5 seeds per Section 7 Layer C.

**Acceptance:**

- PCS path converges to the same Leduc Nash value within `2e-2` per-action and `5e-3` mean-error.
- Deterministic for fixed seed across aarch64 + x86_64.
- Negative-control test fails as expected.

### Integration step (after all three agents land)

1. Run **`tests/test_pr8_convergence.py`** against the full optimized stack (SIMD + layout + PCS-off).
2. Run **`cargo bench`** and compare to `benches/baseline.json`. **Hard gate: ≥10× wall-clock speedup on Section 2 spot 4 (standard HUNL flop).** **Soft gate: ≥30× on either spot 3 or spot 4.**
3. If the hard gate fails: profile with `cargo flamegraph`, identify the cold spot, iterate. PR does not ship until the 10× gate passes.
4. PR audit (per PLAN.md §4): fresh general-purpose agent reviews the diff; outputs `audit_report.md`.
5. User reads `pr_report.md` + `audit_report.md`; approves commit + push.

## 9. Critical correctness items

1. **SIMD/scalar bit-parity.** Tested exhaustively (Section 7 Layer A). No tolerance below ULP-1; default is exact equality. NaN must propagate, Inf must propagate, signed zero must be preserved.

2. **PCS converges to the same average strategy as the full path.** Tested with 5 seeds, mean error tolerance `5e-3` (Section 7 Layer C). Matches `tests/test_leduc_diff.py` tolerance — no special-case looseness.

3. **No `unsafe` outside SIMD intrinsics wrappers.** Every `unsafe { ... }` block in `simd.rs` has a `// SAFETY:` comment explaining the alignment + length invariant. No unsafe in `layout.rs` or `pcs.rs`. The flat-array indexing uses bounds-checked `slice[i]`; if profiling shows bounds checks dominate, identified hotspots can use `get_unchecked` with explicit `// SAFETY:` comments — but the default is checked indexing.

4. **DCFR-PCS parameter switch.** When `use_pcs=true`, the solver internally switches β=0 → β=0.5 (per `_INDEX.md:38` caveat). Documented in `pcs.rs` module docstring and tested explicitly (a test sets `use_pcs=true` and asserts `solver.beta == 0.5` after construction).

5. **Importance weighting in PCS.** Without it, the estimator is biased and the average strategy diverges from the unsampled equilibrium. Tested directly via the negative-control test (Section 7 Layer C).

6. **No new dependencies beyond `criterion`.** No `ndarray`, no `simd-sys` crate, no `packed_simd_2`. Use `std::arch::aarch64` directly. Do not add `rayon` here — if PR 6 added it, we leave it alone.

7. **Reproducibility of PCS.** Same seed → same sequence of sampled cards on aarch64 and x86_64. ChaCha8Rng is portable; explicitly tested via a unit test that runs the sampler with `seed=7` and asserts the first 100 sampled cards match a recorded fixture.

8. **Baseline `benches/baseline.json` must be committed before any optimization lands.** If the baseline is not present in the diff, the PR cannot be reviewed. Agent B's first task is the baseline capture.

## 10. Risks

1. **macOS aarch64 compile flags.** NEON is mandatory on aarch64, so `target-feature` overrides should not be needed. *Mitigation:* `simd.rs` includes a compile-time assertion (e.g., `static_assertions::const_assert!(cfg!(target_feature = "neon") || !cfg!(target_arch = "aarch64"))`) or equivalent doc-comment. Test: `cargo build --release --target aarch64-apple-darwin` must succeed without manual `RUSTFLAGS`.

2. **PCS variance at low iteration counts.** Tests at 1000 iterations may show 5–10% deviation between different seeds. *Mitigation:* tests use 10K iterations and aggregate across 5 seeds (Section 7 Layer C); the **mean** error tolerance is 5e-3 even though individual-seed errors may be 2e-2. Negative-control test must fail to confirm the tolerance is calibrated correctly.

3. **Cache-blocked layout makes infoset lookup slower in absolute terms.** Arithmetic `node_offset[id] + bucket*actions` vs `HashMap::get`. *Mitigation:* HashMap is amortized O(1) but with hashing + probing; flat array is plain O(1). Profile in the baseline + post-PR bench to confirm net win.

4. **AoS-vs-SoA wrong choice.** *Mitigation:* SoA is primary (Section 4); Agent B's microbench checks AoS on a representative hot path; if AoS wins, the spec is amended and the layout adapted.

5. **Tail handling FP drift.** A length-13 regret vector processes 12 elements via SIMD (3 chunks of 4) and 1 element via scalar; the scalar tail may sum in a different order from the SIMD prefix. *Mitigation:* SIMD ops do not change associativity within lanes (a single `horizontal_sum` sums the 4 lanes in a fixed order); the scalar tail adds at the end in fixed order. Total is deterministic, but may differ from a pure-scalar implementation at LSB. Layout parity tolerance is `1e-12`, which absorbs this.

6. **PR 6 has not landed at write-time.** Section 6's "modify `hunl_solver.rs`" depends on PR 6's surface. *Mitigation:* Agent C stubs the integration point if `hunl_solver.rs` doesn't yet exist; PR 8 splits into 8a (SIMD + layout, lands on top of PR 5 / Python) and 8b (PCS, lands on top of PR 6) if necessary.

7. **Bench machine variance.** Wall-clock numbers depend on thermal state, background processes, macOS power scheduling. *Mitigation:* Criterion's statistical framework controls for this; pre/post comparisons use the same Criterion config; baseline run captured on the same machine as the post-PR run; high stddev triggers a re-run (Agent B documents stddev alongside mean in `pr_report.md`).

8. **Criterion as a dev-dep adds ~30 transitive crates.** Compile-time impact in CI. *Mitigation:* `criterion = "0.5"` with `default-features = false` plus only required features; document compile-time delta in `pr_report.md`.

9. **PCS RNG determinism cross-platform.** *Mitigation:* ChaCha8Rng is reproducible across platforms when seeded identically. Test asserts identical sequence on aarch64 and x86_64 (CI). If a fallback RNG is ever used, the test must explicitly catch the divergence.

10. **AGPL contamination from postflop-solver.** PR 8 cites the NEON-pattern shape (chunks_exact + remainder) from `references/code/postflop-solver/src/utility.rs` — which is AGPL. *Mitigation:* `simd.rs`'s module docstring says: "Pattern inspired by postflop-solver's `chunks_exact` tail handling (AGPL — read-only); implementation derived from scratch per Apple's NEON intrinsics docs. No code copied." A fresh agent comparing our `simd.rs` to `postflop-solver/src/utility.rs` should not find verbatim or near-verbatim sequences. License audit step in `scripts/check_pr.sh` runs `grep` for known AGPL-only function names against the new files.

11. **The 10× hard gate may be unmeetable on certain spots.** If the unoptimized PR 6 baseline already runs in 5 minutes on Section 2 spot 4, a 10× speedup means 30 seconds — well within reach. But if the baseline is already 30 seconds, 10× is 3 seconds and may bottleneck on overhead (CFR setup, tree construction). *Mitigation:* the hard gate measures **steady-state CFR iteration cost**, not end-to-end including setup. Agent B's Criterion harness measures iteration-only time using `Criterion::bench_function`'s setup hook.

12. **`std::arch::aarch64` intrinsics are unstable on some Rust versions.** *Mitigation:* `std::arch::aarch64` has been stable since Rust 1.59 (Feb 2022). The project's MSRV (per `Cargo.toml`) is implicitly latest stable. Add an explicit MSRV check in CI.

## 11. Decisions deferred to user

These are flagged in the spec for the user to confirm before Agents A/B/C are launched.

1. **SIMD as Cargo feature flag (`--features simd`) vs always-on?**
   **Recommended: always-on for aarch64** via `#[cfg(target_arch = "aarch64")]`; scalar fallback for non-aarch64 (CI compat). No Cargo `simd` feature. Rationale: NEON is mandatory on aarch64; gating it does nothing useful. Matches the original prompt's stated default.

2. **PCS as default sampling mode vs opt-in?**
   **Recommended: opt-in for v1** (`HUNLConfig.use_pcs: bool = False`). Rationale: PCS is the riskiest of the three optimizations (statistical, not numerically identical); we want a clean rollback path. Switch to default in a follow-up PR after measuring PCS-vs-full convergence on real flop spots.

3. **Target speedup: 10× minimum, 50× stretch.**
   **Recommended: keep as stated.** Hard gate at 10× on standard HUNL flop (Section 2 spot 4); stretch at 50× on either spot 3 or spot 4. PR does not ship if the hard gate fails.

4. **SoA vs AoS for infoset storage.**
   **Recommended: SoA primary** (Section 4). Revisit only if Agent B's microbench shows AoS wins on a hot path we missed.

5. **Block size for cache blocking.**
   **Recommended: 64 infosets per block** (Section 4 calculation). Tunable as `const BLOCK_SIZE: usize = 64;` — easy to change after profiling.

6. **PCS sampling granularity: per-iteration (one outcome at each chance node in the path) vs per-chance-node (independent sample at each chance node).**
   **Recommended: per-iteration**. Lower variance and matches the cost-reduction estimate in Section 5.

7. **PCS seed source.**
   **Recommended: explicit seed via solver config (`seed: u64 = 7`).** Deterministic for tests; user-overridable for production.

8. **Criterion vs cargo's built-in bench.**
   **Recommended: Criterion.** Cargo's built-in bench is unstable-only and produces less reliable statistical analysis. Criterion adds ~30 transitive crates (acceptable for dev-dep only).

9. **`benches/baseline.json` lifecycle: commit it (single artifact, no churn) vs gitignore (regenerate per machine).**
   **Recommended: commit** the baseline measured on the developer's M-series MacBook. Document in the file's header which machine + macOS version + commit hash it was captured against. Future PRs compare against the committed baseline (per PLAN.md §4 "Perf check — flag regressions >10%").

10. **Should PR 8 add multi-threading (rayon) to the DCFR walker?**
    **Recommended: no — out of scope.** PR 8 is single-threaded optimization. Multi-threading is a follow-up.

11. **Should the spec include a stretch goal for ARM SVE?**
    **Recommended: no.** Apple M-series does not have SVE (only NEON). SVE is for AArch64 server chips (Graviton, Ampere). Out of scope for the MacBook-only target.

12. **Should we bench the differential test itself (does PR 8 speed up the diff-test loop)?**
    **Recommended: yes.** Add a Criterion bench `bench_dcfr_diff_loop` that runs the diff-test setup at 1000 iterations. This is the most user-facing speedup metric — it's what the developer sees on every PR.

13. **Should the spec authorize MIT-attributed verbatim port of `references/code/noambrown_poker_solver/cpp/src/vector_eval.cpp:90-131` (Section 3)?**
    **Recommended: yes, with attribution header.** The file is MIT-licensed (`references/code/noambrown_poker_solver/LICENSE`); a verbatim port to Rust with an MIT attribution comment in the file header is policy-compliant per PLAN.md §6 "OK to copy / port verbatim with notice."

14. **PCS path β-switch (β=0 → β=0.5): silent (internal) vs user-visible (configured field)?**
    **Recommended: silent for v1.** The user picks `use_pcs=true`; the solver internally adjusts β. Documented in `pcs.rs` docstring and surfaced in the audit report. Future PR can expose β as a user-controlled knob.

15. **Should the integration step include a poker-intuition gauntlet check (per PLAN.md §4)?**
    **Recommended: yes** — run the existing gauntlet (MDF on overpair, fold-equity on all-in, polarization on monotone) against the optimized solver. If any check regresses vs PR 6, the PR does not ship. Pure scalar baseline → optimized must produce the same gauntlet result within tolerance.
