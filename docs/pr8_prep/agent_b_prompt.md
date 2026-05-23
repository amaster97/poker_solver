# PR 8 Agent B — flat-array infoset layout + DCFR integration + Criterion bench + baseline capture

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 8 Agent B.**
**Your scope:** the cache-blocked SoA infoset layout (`FlatInfosetStore`) + the DCFR loop refactor that swaps `HashMap<String, InfosetData>` for the new flat-array layout + the Criterion bench harness + the pre-optimization baseline capture + the layout-parity Rust integration test + the Python end-to-end test. You also route the DCFR hot ops through Agent A's `simd::*` public API.
**Your contract:** produce `crates/cfr_core/src/layout.rs` + `tests/test_layout.rs` + `tests/test_pr8_convergence.py` + `benches/cfr_bench.rs` + `benches/baseline.json`; refactor `crates/cfr_core/src/dcfr.rs` and `crates/cfr_core/src/solver.rs` to use the new layout; expose `FlatInfosetStore`, `node_index_for(...)`, the redesigned `DCFRSolver` API; consume Agent A's `simd::regret_matching_simd / fma_scalar_vec / discount_positive_negative / discount_strategy` and gate Agent C's `use_pcs` flag wiring on the DCFR side.
**Your success criteria:** Kuhn (10K iter) + Leduc (10K iter) tests pass after refactor; layout-parity test passes to `1e-12` per-action mean; `cargo bench` runs to completion; `benches/baseline.json` exists and is committed; Python end-to-end test (`test_pr8_convergence.py`) passes within `5e-3` tolerance; `cargo clippy --all-targets -- -D warnings` clean; no `unsafe` in `layout.rs`.
**File ownership:** you own `crates/cfr_core/src/layout.rs`, `tests/test_layout.rs`, `tests/test_pr8_convergence.py`, `benches/cfr_bench.rs`, `benches/baseline.json`, and you may EDIT `crates/cfr_core/src/dcfr.rs` + `crates/cfr_core/src/solver.rs` + `crates/cfr_core/src/lib.rs` per the integration scope below — nothing else.

---

## Strict file ownership

**You own (create new):**
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/layout.rs`
- `/Users/ashen/Desktop/poker_solver/tests/test_layout.rs` (Rust integration test at workspace `tests/`; if the repo convention is `crates/cfr_core/tests/`, follow that — check with `ls crates/cfr_core/tests/` first)
- `/Users/ashen/Desktop/poker_solver/tests/test_pr8_convergence.py` (Python end-to-end test)
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/benches/cfr_bench.rs` (Criterion harness; if the repo convention puts benches at workspace-root `benches/`, follow that — check with `ls benches/` first)
- `/Users/ashen/Desktop/poker_solver/benches/baseline.json` (or `crates/cfr_core/benches/baseline.json` to match the bench file's directory — pick one and document; spec §2 puts it at `benches/baseline.json` in the repo root)

**You may modify (existing files, surgical edits only):**
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/dcfr.rs` — entirely rewrite the storage side: replace `HashMap<String, InfosetData>` with `FlatInfosetStore`; replace scalar hot-loop calls with `simd::*` calls (Agent A's API); add the `use_pcs: bool` config-flag wiring (the FIELD on the solver struct; Agent C wires the PCS sampler call from `hunl_solver.rs`). Per-line ownership clarification: Agent C owns the `pcs.rs` module and the `hunl_solver.rs` PCS integration; Agent C also owns the β=0 → β=0.5 switch logic within the solver state (the where-it-applies); you own the `use_pcs: bool` storage on the DCFR config struct. Coordinate via the orchestrator if the boundary is unclear.
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/solver.rs` — adapt the top-level solver API for the new infoset store. Surface-level changes only; the wrapper still exposes a `solve(config) -> Result<Solution>` shape.
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/lib.rs` — add `pub mod layout;` (you own this line); do NOT add `mod simd;` (Agent A's line) or `mod pcs;` (Agent C's line). Re-export `FlatInfosetStore` if appropriate.
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/Cargo.toml` — add `[[bench]]` entries for `cfr_bench` if not already present (Agent A added `criterion = "0.5"` to dev-deps; you ensure the bench target is declared). Do NOT add any runtime dependency.

**You must NOT touch:**
- `crates/cfr_core/src/simd.rs` — Agent A. (Do NOT create it; do NOT modify it after Agent A lands. Inspect for API only.)
- `crates/cfr_core/src/pcs.rs` — Agent C. (Do NOT create it.)
- `crates/cfr_core/src/hunl_solver.rs` (if it exists post-PR 6) — Agent C owns the PCS integration on this file. You may read it for context but do not edit it.
- `crates/cfr_core/src/{kuhn,leduc,game,eval}.rs` — these consume DCFR via the Game trait; they should not see the storage layout (only their indexing changes if your `infoset_key → node_id, bucket_id` mapping requires a Game-trait extension; if so, flag it).
- `tests/test_simd.rs` — Agent A.
- `tests/test_pcs.rs` — Agent C.
- Any Python file outside `tests/test_pr8_convergence.py` — out of scope. (Notably, `poker_solver/hunl.py`'s `HUNLConfig.use_pcs: bool = False` is Agent C's edit, NOT yours.)
- `pyproject.toml` — no Python schema changes from you; Agent C handles the Python `use_pcs` field.

If you discover that Agent A's signature is incompatible with what you need, **do not silently change either side**. Stop and write a short note to the orchestrator describing the conflict; the orchestrator will reconcile.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/pr8_spec.md`. Internalize §1 (goal), §2 (baseline measurement — your **first** task), §4 (cache-blocked infoset layout — your stage), §6 (files to create + modify — your owned rows), §7 Layer B + Layer D (your test layers), §8 Agent B deliverables + acceptance criteria, §9 items 3, 6, 8 (your critical correctness items), §10 risks 3, 4, 5, 7, 8, 11 (your risks), §11 decisions 4, 5, 8, 9, 12 (your locked defaults).
2. **The PLAN (locked decisions):** `/Users/ashen/Desktop/poker_solver/PLAN.md`. Especially §1 perf targets (Kuhn <1s, Leduc <10s, HUNL postflop 1–3 min for simple flop / 5–15 min for standard flop), §4 "Perf check — flag regressions >10%", §6 license audit.
3. **The autonomous log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md`. Skim for PR 8-related amendments.
4. **Spec consistency review:** `/Users/ashen/Desktop/poker_solver/docs/spec_consistency_review.md`. Especially I3 (tolerance alignment across PR 6/7/8/9) and I6 (`use_pcs` schema authorized by PR 8). These confirm: PR 8 Layer D Python end-to-end test uses `5e-3 per-action + 1e-3 per-spot game-value cluster`; the `use_pcs: bool = False` field on `HUNLConfig` (Python) is authorized to land here, and Agent C owns the actual edit.
5. **The existing DCFR Rust implementation (the file you'll rewrite the storage of):** `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/dcfr.rs`. Pay attention to line 65 (the `HashMap<String, InfosetData>` you're replacing), lines 83-100 (`get_strategy`), lines 111-134 (DCFR discount), lines 196-200 (regret_sum + strategy_sum accumulation). The four hot loops are what you route through Agent A's `simd::*`.
6. **The existing solver wrapper:** `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/solver.rs`. Understand the public surface; preserve it as much as possible (only surface-level changes for the new infoset store).
7. **Agent A's public API (your input):** see §"Agent A's exports you depend on" below. Read `crates/cfr_core/src/simd.rs` after Agent A lands to confirm the signatures; do NOT read it before Agent A lands (it doesn't exist yet).
8. **The bench harness style:** Criterion 0.5 docs (https://bheisler.github.io/criterion.rs/book/). Standard pattern: `criterion_group!` + `criterion_main!`.
9. **Reference patterns:**
   - `references/code/slumbot2019/src/build_kmeans_buckets.cpp` (**MIT**) — flat-array layout patterns OK to port architecturally.
   - `references/code/noambrown_poker_solver/cpp/src/cfr_core.cpp` (**MIT**) — flat infoset table architectural inspiration; OK to port verbatim with attribution.
   - `references/code/postflop-solver/src/` (**AGPL**) — read-only; no code copy.

## Default decisions LOCKED (do not deviate)

These amendments / clarifications to the PR 8 spec win where the spec text differs:

- **Decision 11.4 = SoA primary path** (per spec §4 "SoA primary path. Rationale: ..."). Your `FlatInfosetStore` uses Structure-of-Arrays. If your microbench shows AoS wins on a hot path you'd otherwise miss, flag it to the orchestrator and amend the spec — do NOT silently switch to AoS.
- **Decision 11.5 = block size 64 infosets per cache block.** Implement as `pub const BLOCK_SIZE: usize = 64;` in `layout.rs`. Tunable but not currently tuned.
- **Decision 11.8 = Criterion bench, not cargo's built-in.** You use `criterion = "0.5"` (already added by Agent A as dev-dep).
- **Decision 11.9 = commit `benches/baseline.json`.** Single artifact, captured on the developer's M-series MacBook before any optimization lands. Header includes: machine ID, macOS version, commit hash of the run, date.
- **Decision 11.12 = bench the differential test loop.** Add a Criterion bench `bench_dcfr_diff_loop` that runs the diff-test setup at 1000 iterations. This is the most user-facing speedup metric. Include alongside the 4 main bench spots.
- **Layout parity tolerance: `1e-12`** per-action average strategy probability (spec §7 Layer B). Absorbs FP-noise from tail handling.
- **Python end-to-end tolerance: `5e-3`** per-action mean + `1e-3` per-spot game-value cluster (spec §7 Layer D, per consistency review I3). Matches existing PR 6 / PR 7 / PR 9 tolerance.
- **No `unsafe` in `layout.rs`.** Use bounds-checked `slice[i]` indexing. If profiling shows bounds checks dominate, identified hotspots may use `get_unchecked` with explicit `// SAFETY:` comments — but the DEFAULT is checked indexing.
- **No new runtime dependencies.** Imports: `std::collections::HashMap` (only at index-build time, not in the hot loop), `crate::simd::*` (Agent A's exports), stdlib. No `ndarray`, no `bytemuck`, no `rayon`.
- **`HashMap<String, InfosetData>` is REMOVED in this PR.** Once parity is confirmed (Layer B test passes to `1e-12`), the HashMap path is deleted in the same PR. Do NOT leave a runtime selector / builder flag in production code.

## Agent A's exports you depend on

You consume these from `crates/cfr_core/src/simd.rs`. If Agent A's signatures drift, flag it — do not silently adapt.

```rust
// From simd.rs (Agent A):
pub fn regret_matching_simd(regrets: &[f64], out: &mut [f64]) -> f64;
pub fn fma_scalar_vec(scale: f64, source: &[f64], dest: &mut [f64]);
pub fn discount_positive_negative(regrets: &mut [f64], pos_scale: f64, neg_scale: f64);
pub fn discount_strategy(strategy: &mut [f64], strat_scale: f64);

// Vec4f64 + lane-level ops (you probably don't need these directly; the four
// high-level ops above are your primary contract).
pub struct Vec4f64(...);
impl Vec4f64 { /* load, store, zero, splat, add, sub, mul, fma, max, min, horizontal_sum */ }
```

**Integration pattern:** in your refactored `dcfr.rs` hot loop, replace:
- Scalar `get_strategy` loop (lines 83-100) → single call to `simd::regret_matching_simd(regret_slice, &mut strategy_slice)`.
- Scalar regret-sum update (lines 196-200, the `regret_sum[a] += opp_reach * (action_value[a] - node_value)` shape) → use `simd::fma_scalar_vec` with appropriate scale; for the action-value vs node-value difference, you may need to materialize a `diff` slice first OR compute the diff lanewise via `Vec4f64::sub`. Document your choice.
- Scalar strategy-sum update (`strategy_sum[a] += own_reach * strategy[a]`) → `simd::fma_scalar_vec(own_reach, &strategy_slice, &mut strategy_sum_slice)`.
- DCFR discount (lines 111-134, sign-conditional `r *= pos_scale` vs `r *= neg_scale`) → `simd::discount_positive_negative(&mut regret_slice, pos_scale, neg_scale)`.
- Strategy discount (`s *= strat_scale`) → `simd::discount_strategy(&mut strategy_sum_slice, strat_scale)`.

The hot-loop body, post-refactor, is a sequence of slice-mutating calls into `simd::*` — no per-action `for` loops in the hot path.

## Public API contract (signatures Agent C tests + downstream PRs depend on)

Export the following from `crates/cfr_core/src/layout.rs`. Type hints required; `pub` only where Agent C or external callers need access.

### `crates/cfr_core/src/layout.rs`

```rust
//! Cache-blocked SoA infoset storage for the DCFR hot loop.
//!
//! Replaces the legacy `HashMap<String, InfosetData>` storage (pre-PR 8) with
//! flat `Vec<f64>` arrays indexed by `(tree_node_id, bucket_id, action_idx)`.
//!
//! **Layout:** a single bucket's action regrets are contiguous in memory
//! (stride = `num_actions`); a single tree node's bucket × action matrix is
//! contiguous (size = `num_buckets * num_actions`). The SIMD hot path
//! (regret-matching over one bucket's actions) sees aligned, contiguous data —
//! exactly what NEON wants.
//!
//! **Block size:** 64 infosets per cache "block" (per spec §4 + Decision 11.5).
//! M1 P-core L1 data cache is 192 KB; 64 × (~96 B per infoset) ≈ 6 KB, fits in L1.
//!
//! **No `unsafe`** in this file. Bounds-checked indexing throughout. If profiling
//! shows bounds checks dominate, individual hotspots may use `get_unchecked`
//! with explicit `// SAFETY:` comments (per spec §9 #3) — DEFAULT is checked.
//!
//! Pattern inspired by slumbot2019/src/build_kmeans_buckets.cpp flat-array layout
//! (MIT, attribution); architectural inspiration from
//! noambrown_poker_solver/cpp/src/cfr_core.cpp (MIT).

use std::collections::HashMap;

/// Block size for cache-blocked iteration. 64 infosets per block; tunable.
pub const BLOCK_SIZE: usize = 64;

/// Compact tree-node identifier. `u32` gives 4 billion nodes — plenty for HUNL.
pub type TreeNodeId = u32;

/// Compact bucket identifier within a tree node. `u32` for headroom; `u16` would
/// suffice for K_max = 256, but the index arithmetic is on `u32` either way.
pub type BucketId = u32;

/// Flat-array storage for all DCFR infosets across all tree nodes.
///
/// Indexing: for tree node `n`, bucket `b`, action `a`:
///   regret_sum[node_offset[n] + b * node_actions[n] as usize + a]
pub struct FlatInfosetStore {
    /// Tree-node ID → starting index into `regret_sum` / `strategy_sum`.
    pub node_offset: Vec<u32>,
    /// Tree-node ID → number of actions at that node (uniform within a node).
    pub node_actions: Vec<u8>,
    /// Tree-node ID → number of buckets (infosets per node).
    pub node_buckets: Vec<u32>,
    /// Tree-node ID → last iteration this node's infosets were discounted at.
    /// Node-granularity (every bucket of a node is touched in the same iter).
    pub node_last_discount: Vec<u32>,

    /// Flat storage, indexed per the layout described above.
    pub regret_sum: Vec<f64>,
    pub strategy_sum: Vec<f64>,
}

impl FlatInfosetStore {
    /// Construct an empty store; nodes are registered via `register_node`.
    pub fn new() -> Self;

    /// Register a tree node with `num_actions` actions and `num_buckets` buckets.
    /// Returns the assigned TreeNodeId. Allocates `num_buckets * num_actions` f64
    /// in each of `regret_sum` and `strategy_sum`.
    ///
    /// Build-time only; not called from the hot loop.
    pub fn register_node(&mut self, num_actions: u8, num_buckets: u32) -> TreeNodeId;

    /// Compute the flat-array offset for `(node, bucket, action=0)`.
    /// Returns `node_offset[node as usize] + bucket * node_actions[node as usize] as u32`.
    #[inline(always)]
    pub fn offset_for(&self, node: TreeNodeId, bucket: BucketId) -> usize;

    /// Borrow the action-stride slice for `(node, bucket)`'s regret_sum.
    /// Length = `node_actions[node]`. Used by the DCFR hot loop and SIMD ops.
    #[inline(always)]
    pub fn regret_slice(&self, node: TreeNodeId, bucket: BucketId) -> &[f64];

    /// Mutably borrow the action-stride slice for `(node, bucket)`'s regret_sum.
    #[inline(always)]
    pub fn regret_slice_mut(&mut self, node: TreeNodeId, bucket: BucketId) -> &mut [f64];

    /// Borrow the action-stride slice for `(node, bucket)`'s strategy_sum.
    #[inline(always)]
    pub fn strategy_sum_slice(&self, node: TreeNodeId, bucket: BucketId) -> &[f64];

    /// Mutably borrow the action-stride slice for `(node, bucket)`'s strategy_sum.
    #[inline(always)]
    pub fn strategy_sum_slice_mut(&mut self, node: TreeNodeId, bucket: BucketId) -> &mut [f64];

    /// Borrow ALL bucket × action regret data for a single tree node as a flat slice.
    /// Length = `node_buckets[node] * node_actions[node]`. Used for batch ops
    /// (e.g., per-node lazy discount that touches every bucket).
    pub fn node_regret_block(&self, node: TreeNodeId) -> &[f64];

    /// Mutable variant of `node_regret_block`.
    pub fn node_regret_block_mut(&mut self, node: TreeNodeId) -> &mut [f64];

    /// Mutable variant for strategy_sum across all buckets of a node.
    pub fn node_strategy_block_mut(&mut self, node: TreeNodeId) -> &mut [f64];

    /// Total infoset count across all nodes (sum of node_buckets[i] for all i).
    pub fn total_infosets(&self) -> u64;
}

impl Default for FlatInfosetStore {
    fn default() -> Self { Self::new() }
}
```

### `crates/cfr_core/src/dcfr.rs` modifications

Replace the `HashMap<String, InfosetData>` storage with `FlatInfosetStore`. Concretely:

1. **Struct change:** the `DCFRSolver` (or equivalent struct) holds `store: FlatInfosetStore` instead of `infosets: HashMap<String, InfosetData>`.
2. **Infoset-key → (node_id, bucket_id) lookup:** the existing `infoset_key: String` consumed by the Game trait is replaced (or augmented) by a `(TreeNodeId, BucketId)` pair. If the Game trait already exposes `node_id(...)` and `bucket_id(...)` accessors (because PR 4 + PR 6 introduced bucketed indexing), use them directly. If not, you'll need a small Game-trait extension — flag it to the orchestrator before implementing.
3. **Hot-loop refactor:** call `simd::regret_matching_simd`, `simd::fma_scalar_vec`, `simd::discount_positive_negative`, `simd::discount_strategy` per the integration pattern above.
4. **`use_pcs: bool` config field:** add to the DCFR config struct (or `DCFRSolver`'s state). Default `false`. **You wire the storage; Agent C wires the actual PCS sampler call from `hunl_solver.rs` and the β-switch logic.** Coordinate via orchestrator if unclear.

### `crates/cfr_core/src/solver.rs` modifications

Surface-level changes: the wrapper `solve(config) -> Result<Solution>` shape is preserved. Internal: it now constructs a `FlatInfosetStore` instead of a `HashMap`. Document the API surface in a doc comment.

### `crates/cfr_core/src/lib.rs` modifications

Add `pub mod layout;` (your line). Re-export `FlatInfosetStore` if external callers need it (likely yes, for tests). Do NOT add `mod simd;` (Agent A) or `mod pcs;` (Agent C).

### `crates/cfr_core/benches/cfr_bench.rs`

```rust
//! Criterion bench harness for PR 8 perf gating.
//!
//! Four spots per spec §2 + the diff-test loop bench per Decision 11.12.
//!
//! Run: `cargo bench --bench cfr_bench`
//!
//! On the FIRST run (pre-optimization), the output is captured in
//! `benches/baseline.json`. Subsequent PRs compare against the baseline
//! (per PLAN.md §4 "Perf check — flag regressions >10%").

use criterion::{criterion_group, criterion_main, Criterion, BenchmarkId, Throughput};

fn bench_kuhn(c: &mut Criterion) {
    let mut group = c.benchmark_group("kuhn");
    group.sample_size(20);   // per spec §2 "Sample: 20 iterations"
    group.warm_up_time(std::time::Duration::from_secs(2));  // "Warm-up: 5 iterations"
    group.bench_function("dcfr_10k_iter", |b| {
        b.iter(|| {
            // Construct + solve Kuhn for 10K iterations.
            // Sanity floor; SIMD effect is noise.
            todo!("invoke kuhn DCFR solver for 10K iterations")
        });
    });
    group.finish();
}

fn bench_leduc(c: &mut Criterion) {
    // 288 infosets, 10K iter. Per spec §2 row 2.
    todo!()
}

fn bench_hunl_simple_flop(c: &mut Criterion) {
    // As Kc 7d, 3 bet sizes, 100 BB, 64/32/16 buckets (tier-2). 1K iter.
    // Primary 10× speedup target.
    todo!()
}

fn bench_hunl_standard_flop(c: &mut Criterion) {
    // Js 9h 6d, 5 bet sizes, 100 BB, 256/128/64 buckets. 1K iter.
    // Stretch 50× speedup target.
    todo!()
}

fn bench_dcfr_diff_loop(c: &mut Criterion) {
    // Per Decision 11.12 — bench the existing diff-test loop at 1K iter.
    // Most user-facing speedup metric.
    todo!()
}

criterion_group!(benches,
    bench_kuhn,
    bench_leduc,
    bench_hunl_simple_flop,
    bench_hunl_standard_flop,
    bench_dcfr_diff_loop,
);
criterion_main!(benches);
```

Fill in the `todo!()` bodies. Use the existing Rust DCFR solver entry points (whichever PR 6 / PR 4 expose for HUNL).

### `benches/baseline.json`

Captured **before any optimization lands.** Format:

```json
{
  "metadata": {
    "machine": "Apple MacBook ?? (M? chip)",
    "macos_version": "<output of `sw_vers -productVersion`>",
    "rustc_version": "<output of `rustc --version`>",
    "commit_hash": "<output of `git rev-parse HEAD`>",
    "captured_date": "2026-05-21",
    "criterion_version": "0.5",
    "warm_up_iterations": 5,
    "sample_iterations": 20
  },
  "benchmarks": {
    "kuhn/dcfr_10k_iter":     {"mean_ns": ..., "stddev_ns": ..., "median_ns": ...},
    "leduc/dcfr_10k_iter":    {"mean_ns": ..., "stddev_ns": ..., "median_ns": ...},
    "hunl_simple_flop/dcfr_1k_iter":   {"mean_ns": ..., "stddev_ns": ..., "median_ns": ...},
    "hunl_standard_flop/dcfr_1k_iter": {"mean_ns": ..., "stddev_ns": ..., "median_ns": ...},
    "dcfr_diff_loop/dcfr_1k_iter":     {"mean_ns": ..., "stddev_ns": ..., "median_ns": ...}
  }
}
```

**Process:**
1. Check out the commit immediately before your refactor (i.e., the tip of PR 6's branch, or main with no PR 8 changes applied).
2. Run `cargo bench --bench cfr_bench --manifest-path crates/cfr_core/Cargo.toml`.
3. Capture Criterion's output (it writes JSON to `target/criterion/<bench-name>/base/estimates.json`).
4. Aggregate into `benches/baseline.json` in the format above.
5. Commit the file with a clear message: `bench: capture pre-PR-8 baseline on M?`.
6. Then begin your optimization work.

**Critical:** the bench harness file (`cfr_bench.rs`) MUST exist BEFORE the baseline capture. Order: write `cfr_bench.rs` → confirm it compiles + runs → check out pre-PR-8 state → capture baseline → return to optimization branch → begin layout refactor.

### `tests/test_layout.rs`

Rust integration test, Layer B per spec §7. Layout parity to `1e-12`.

```rust
//! Layout parity test: FlatInfosetStore vs reference HashMap-backed DCFR.
//!
//! Runs Kuhn + Leduc on both storage backends with identical inputs and asserts
//! per-action average strategy probabilities match within 1e-12.
//!
//! **However:** the HashMap path is REMOVED in this PR (per spec §4 "Migration
//! path"). So the parity test compares against a **golden fixture** captured
//! from the pre-PR-8 implementation, OR uses the Python reference DCFR as the
//! ground truth.
//!
//! Recommended: a golden fixture committed at `tests/fixtures/dcfr_kuhn_10k.json`
//! and `tests/fixtures/dcfr_leduc_10k.json`, captured from the pre-PR-8 main
//! branch and treated as immutable reference data.

#[test]
fn test_flat_layout_kuhn_matches_golden() {
    // Run Kuhn DCFR with FlatInfosetStore for 10K iter.
    // Load tests/fixtures/dcfr_kuhn_10k.json.
    // For each infoset key in the fixture, assert per-action avg strategy
    // matches within 1e-12.
    todo!()
}

#[test]
fn test_flat_layout_leduc_matches_golden() {
    todo!()
}

#[test]
fn test_flat_layout_register_node_round_trip() {
    // Register 3 nodes with various (num_actions, num_buckets); confirm
    // offset_for / regret_slice / regret_slice_mut produce non-overlapping,
    // correctly-sized slices.
    todo!()
}

#[test]
fn test_flat_layout_block_size_constant() {
    use poker_solver_cfr_core::layout::BLOCK_SIZE;
    assert_eq!(BLOCK_SIZE, 64);
}
```

**Golden fixture generation:** before deleting the HashMap path, run the (pre-refactor) HashMap-backed DCFR on Kuhn + Leduc at 10K iter and dump the average strategy to `tests/fixtures/dcfr_kuhn_10k.json` and `tests/fixtures/dcfr_leduc_10k.json`. Commit these fixtures. They become the immutable reference data for all future PRs touching DCFR storage.

Fixture format:
```json
{
  "game": "kuhn",
  "iterations": 10000,
  "captured_commit": "<pre-PR-8 commit hash>",
  "infosets": {
    "<infoset_key>": {
      "avg_strategy": [<f64>, <f64>, ...]
    },
    ...
  }
}
```

### `tests/test_pr8_convergence.py`

Python end-to-end test, Layer D per spec §7. Tolerance: `5e-3` per-action mean + `1e-3` per-spot game-value cluster (per consistency review I3).

```python
"""End-to-end PR 8 convergence test (Layer D).

Runs the existing tests/test_dcfr_diff.py river-spot test but with the
optimized Rust solver (cache-blocked + SIMD; PCS off by default).

Tolerance per spec §7 Layer D + consistency review I3:
- Per-action mean absolute error across all infosets < 5e-3.
- Per-spot game-value cluster < 1e-3.

Matches PR 6 / PR 7 / PR 9 tolerance. No silent regression of correctness.
"""

import pytest
import numpy as np

# Use the optimized Rust solver path (post-PR-8). The exact import depends on
# PR 6's API; canonical entry point is `poker_solver._rust.solve_hunl(...)`.
from poker_solver._rust import solve_hunl as solve_hunl_rust  # type: ignore[import]

# Reference Python DCFR.
from poker_solver.dcfr import solve as solve_python_ref
from poker_solver.hunl import HUNLConfig

# Reuse the existing diff-test river spot.
from tests.test_dcfr_diff import RIVER_SPOT_FIXTURES  # type: ignore[import]


@pytest.mark.parametrize("spot_id", list(RIVER_SPOT_FIXTURES.keys()))
def test_pr8_optimized_rust_matches_python_ref(spot_id: str) -> None:
    spot = RIVER_SPOT_FIXTURES[spot_id]
    config = HUNLConfig(
        # ... fields from spot ...
        use_pcs=False,  # PCS off by default per spec §5 + §11 #2
    )

    rust_result = solve_hunl_rust(config, iterations=10_000)
    python_result = solve_python_ref(config, iterations=10_000)

    # Per-action mean absolute error
    for infoset_key in rust_result.average_strategy:
        rust_strategy = np.asarray(rust_result.average_strategy[infoset_key])
        python_strategy = np.asarray(python_result.average_strategy[infoset_key])
        mae = np.abs(rust_strategy - python_strategy).mean()
        assert mae < 5e-3, f"infoset {infoset_key}: MAE={mae:.2e} > 5e-3"

    # Per-spot game-value cluster
    game_value_diff = abs(rust_result.game_value - python_result.game_value)
    assert game_value_diff < 1e-3, (
        f"game value diff {game_value_diff:.2e} > 1e-3"
    )
```

## Critical correctness items

### 1. Layer B parity to 1e-12 (spec §7 Layer B)

Per-action average strategy probability matches the golden fixture within `1e-12`. This absorbs FP-noise from tail handling (spec §10 risk 5). If a test infoset fails the tolerance:
- First, check that Agent A's SIMD path is bit-exact on the four hot ops (it should be, per Agent A's Layer A).
- Second, check that the DCFR loop iteration order is unchanged (visiting infosets in a different order changes the accumulated regret_sum at the LSB).
- Third, if both look right, the `1e-12` bound may be slightly tighter than needed; flag to orchestrator before relaxing.

### 2. Layer D Python end-to-end tolerance (spec §7 Layer D + I3)

`5e-3` per-action mean + `1e-3` per-spot game-value cluster. **Do not loosen this tolerance** to make a flaky test pass. If it fails, it's a real bug in your refactor or in Agent A's SIMD parity, not a tolerance issue.

### 3. `benches/baseline.json` committed BEFORE any optimization (spec §9 #8)

This is the load-bearing reproducibility check. No baseline → no PR 8. **Sequence:**
1. Write `cfr_bench.rs` skeleton (and stub the bench bodies to compile).
2. Confirm `cargo bench` runs to completion on the pre-PR-8 state.
3. Capture `benches/baseline.json` from the pre-PR-8 run.
4. Commit `baseline.json` with a clean commit (do not bundle with refactor commits).
5. Then begin the layout refactor.

### 4. Hot-loop refactor preserves bit-for-bit (non-PCS path) (spec §1)

After the refactor, the DCFR(α=1.5, β=0, γ=2.0) loop on the non-PCS path produces the same regret_sum / strategy_sum values as the pre-PR-8 implementation, modulo Agent A's `1e-12`-bounded SIMD tail drift. Tested by Layer B (your `test_layout.rs`).

### 5. `use_pcs: bool` config flag wiring (spec §6 "Modify" + §9 #4)

The DCFR config struct gets a `pub use_pcs: bool` field, default `false`. This is the STORAGE side. Agent C consumes it in `hunl_solver.rs` to gate the PCS sampler. Agent C also wires the β=0 → β=0.5 switch when `use_pcs=true`. Coordinate with Agent C via the orchestrator if the field name or location changes.

### 6. No `unsafe` in `layout.rs` (spec §9 #3)

Bounds-checked `slice[i]` indexing throughout. If profiling shows bounds checks dominate, use `get_unchecked` with `// SAFETY:` comments at the identified hotspot — but the DEFAULT is checked.

### 7. Hash-map removal (spec §4 "Migration path" + "API breakage")

Once Layer B parity is confirmed and benches pass, the HashMap path is REMOVED in the same PR. No runtime selector / builder flag survives in production code. The HashMap → flat-array migration is one-way.

### 8. Bench machine variance (spec §10 risk 7)

Wall-clock numbers depend on thermal state, background processes, macOS power scheduling. Criterion's statistical framework controls for this. Document the **stddev alongside the mean** in `pr_report.md`. High stddev (>10% of mean) triggers a re-run.

## License-aware sourcing

**You may port architecturally (not code-copy) from MIT/Apache sources:**
- `references/code/slumbot2019/src/build_kmeans_buckets.cpp` (**MIT**) — flat-array layout patterns. Cite in `layout.rs` module docstring.
- `references/code/noambrown_poker_solver/cpp/src/cfr_core.cpp` (**MIT**) — infoset table architectural inspiration. OK to port verbatim with attribution if a specific pattern lifts cleanly.
- `references/code/open_spiel/` (**Apache 2.0**) — CFR / DCFR reference implementations; OK to port with attribution.

**You may NOT copy from AGPL sources:**
- `references/code/postflop-solver/` — **AGPL v3**, read-only only.
- `references/code/TexasSolver/` — **AGPL v3**, same rule.

**You may NOT extrapolate from training data.** Cite local references for any non-trivial pattern.

If you copy a non-trivial snippet (>~5 LOC) from an MIT/Apache source, add an attribution comment:
```rust
// Pattern from noambrown_poker_solver/cpp/src/cfr_core.cpp (MIT, attribution required).
// Reference: references/code/noambrown_poker_solver/cpp/src/cfr_core.cpp
```

## Quality bar

- **`cargo test --release`** passes (all existing tests + your new `test_layout` + the unchanged Kuhn/Leduc tests).
- **`cargo clippy --all-targets -- -D warnings`** clean. No new warnings; no `clippy::unsafe_derive_deserialize` or similar.
- **`cargo fmt`** clean (`cargo fmt --check`).
- **`cargo bench --bench cfr_bench`** runs to completion. All four spots + `bench_dcfr_diff_loop` produce numbers.
- **`benches/baseline.json`** exists and is committed.
- **`tests/test_pr8_convergence.py`** passes within `5e-3` / `1e-3` tolerance.
- **No new runtime deps in `Cargo.toml`.** Only Agent A's `criterion = "0.5"` dev-dep.
- **`ruff check tests/test_pr8_convergence.py`** + **`mypy --strict tests/test_pr8_convergence.py`** clean.
- **Code size budget: ~600-900 LOC** combined across `layout.rs` (~400 LOC) + `dcfr.rs` delta (~200 LOC, mostly substitution) + `solver.rs` delta (~50 LOC) + `cfr_bench.rs` (~150 LOC) + `test_layout.rs` (~150 LOC) + `test_pr8_convergence.py` (~100 LOC). Stay within budget.

## Reference-first rule

Before any technical claim, citation, or formula, check the local references. Never extrapolate from training data when a local authoritative source exists. The reference index is `/Users/ashen/Desktop/poker_solver/references/README.md` — skim for "cache blocking", "SoA", "flat layout", "infoset table" entries.

The Apple Silicon M1 cache hierarchy data (192 KB L1d, 128 KB L2 unified, etc.) is locally verifiable via `sysctl hw.l1dcachesize`-style commands; cite the source of any number you use.

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Format + lint
cargo fmt --check --manifest-path crates/cfr_core/Cargo.toml
cargo clippy --manifest-path crates/cfr_core/Cargo.toml --all-targets -- -D warnings

# 2. Build (release)
cargo build --release --manifest-path crates/cfr_core/Cargo.toml

# 3. Existing test suite (Kuhn + Leduc + any PR 6 tests). These must still pass
# after your refactor.
cargo test --release --manifest-path crates/cfr_core/Cargo.toml 2>&1 | tail -30

# 4. YOUR new tests
cargo test --release --manifest-path crates/cfr_core/Cargo.toml --test test_layout 2>&1 | tail -20

# 5. Python end-to-end
pytest -x tests/test_pr8_convergence.py 2>&1 | tail -20

# 6. Bench harness runs (this also produces the post-refactor numbers; compare
# to baseline.json mentally — the hard gate at 10× / soft gate at 30× is checked
# during the integration step, not your individual sign-off).
cargo bench --bench cfr_bench --manifest-path crates/cfr_core/Cargo.toml 2>&1 | tail -50

# 7. Confirm baseline.json is committed and has all 5 bench entries
cat benches/baseline.json | jq '.benchmarks | keys'
# Expected: ["kuhn/...", "leduc/...", "hunl_simple_flop/...", "hunl_standard_flop/...", "dcfr_diff_loop/..."]

# 8. Confirm no HashMap<String, InfosetData> remains in dcfr.rs (post-removal)
grep -n "HashMap<String, InfosetData>" crates/cfr_core/src/dcfr.rs
# Expected: no matches.

# 9. Confirm no `unsafe` in layout.rs
grep -n "unsafe" crates/cfr_core/src/layout.rs
# Expected: no matches (or only matches in doc comments).
```

If any of the above fails, fix the issue before reporting done. If a parity test reveals a spec ambiguity, **stop and flag it** — do not silently work around it.

## Report back format

When done, write a concise report (≤300 words) covering:

1. Files created with line counts; files modified with line-delta.
2. Baseline capture: machine ID, macOS version, commit hash, mean+stddev for each of the 5 bench spots. **Numbers themselves**, not just "captured."
3. Post-refactor bench numbers: mean+stddev for each of the 5 spots, alongside the baseline mean. Wall-clock speedup ratios per spot. (The hard 10× gate is judged at integration step; you report numbers, the orchestrator judges.)
4. Layout parity test result: did all golden-fixture infosets match within `1e-12`? If not, list which infosets diverged and the divergence magnitude.
5. Python end-to-end test result: pass/fail per spot, max per-action MAE, max game-value diff.
6. Any spec amendment you made or contract drift you flagged (especially around `use_pcs` field placement, Game-trait extension for `(node_id, bucket_id)` lookup).
7. License attributions added.
8. Open questions for human review.
