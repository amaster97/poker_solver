# PR 8 Agent C — public chance sampling + hunl_solver integration + PCS tests + Python schema

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 8 Agent C.**
**Your scope:** the public chance sampling module (`crates/cfr_core/src/pcs.rs`) with `PCSSampler` + importance weighting + the DCFR-PCS β=0 → β=0.5 silent switch; the integration into `crates/cfr_core/src/hunl_solver.rs` (PR 6's file; if absent, you stub the integration point) gated by `use_pcs: bool`; the Python-side `HUNLConfig.use_pcs: bool = False` field addition (authorized by spec §6 "Modify" per consistency review I6); the PCS convergence + negative-control tests.
**Your contract:** produce `crates/cfr_core/src/pcs.rs` + `tests/test_pcs.rs` + the `HUNLConfig.use_pcs` field on `poker_solver/hunl.py`; modify `crates/cfr_core/src/hunl_solver.rs` to call the sampler at chance nodes when `use_pcs=true`; lightly modify `crates/cfr_core/src/dcfr.rs` ONLY to flip β from 0 to 0.5 when `use_pcs=true` (Agent B owns the `use_pcs: bool` STORAGE; you own the BEHAVIOR change downstream); expose `PCSSampler::new(seed)` + `PCSSampler::sample_public(node) -> (Card, f64)` to internal callers; add `mod pcs;` to `lib.rs`.
**Your success criteria:** PCS path converges to the same Leduc Nash value within `2e-2` per-action + `5e-3` mean error across 5 seeds; negative-control test (importance weight removed) FAILS; deterministic ChaCha8Rng sequence across aarch64 + x86_64; `cargo test --release test_pcs` passes; `cargo clippy --all-targets -- -D warnings` clean; Python-side `HUNLConfig.use_pcs` field defaults to `False`; PR 3 lossless infoset_key behavior preserved (your hunl.py edit is additive only).
**File ownership:** you own `crates/cfr_core/src/pcs.rs`, `tests/test_pcs.rs`, and you may EDIT `crates/cfr_core/src/hunl_solver.rs`, `crates/cfr_core/src/dcfr.rs` (β-switch logic only), `crates/cfr_core/src/lib.rs` (only `mod pcs;` line), `poker_solver/hunl.py` (only `use_pcs: bool = False` field on `HUNLConfig`) — nothing else.

---

## Strict file ownership

**You own (create new):**
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/pcs.rs`
- `/Users/ashen/Desktop/poker_solver/tests/test_pcs.rs` (Rust integration test at workspace `tests/`; if the repo convention is `crates/cfr_core/tests/`, follow that — check with `ls crates/cfr_core/tests/` first)
- `/Users/ashen/Desktop/poker_solver/tests/fixtures/pcs_seed7_first100.json` (deterministic-sequence fixture per spec §9 #7 — first 100 sampled cards under `seed=7`, used by the cross-platform-determinism test)

**You may modify (existing files, surgical edits only):**
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/hunl_solver.rs` (PR 6's file; if absent, your integration is stubbed per spec §10 risk 6) — add `use_pcs` config consumption; call `PCSSampler::sample_public(node)` at chance nodes when `use_pcs=true`; apply importance weight `K` to the recursive value.
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/dcfr.rs` — ONLY the β=0 → β=0.5 silent-switch logic (per spec §5 "DCFR-PCS parameter compatibility" + §9 #4). Agent B owns the `use_pcs: bool` field STORAGE on the DCFR config; you own the BEHAVIOR change (read the flag, set β accordingly). Coordinate with Agent B via orchestrator if the boundary is unclear. Touch only the β-init / β-read sites; do NOT modify any other DCFR loop logic.
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/lib.rs` — add ONLY `pub mod pcs;`. Do NOT add `mod simd;` (Agent A's line) or `mod layout;` (Agent B's line).
- `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` — add ONLY `use_pcs: bool = False` field to `HUNLConfig` dataclass. PR 3's lossless behavior must be preserved EXACTLY (no other change to `hunl.py`). Per spec §6 amended note + consistency review I6: this is the only Python schema change PR 8 makes.
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/Cargo.toml` — add `rand = "0.8"` + `rand_chacha = "0.3"` as runtime deps if not already present. These are the smallest portable RNG crates for ChaCha8. (Per spec §11 #7 + §10 #9.)

**You must NOT touch:**
- `crates/cfr_core/src/simd.rs` — Agent A.
- `crates/cfr_core/src/layout.rs` — Agent B.
- `tests/test_simd.rs` — Agent A.
- `tests/test_layout.rs` — Agent B.
- `tests/test_pr8_convergence.py` — Agent B.
- `crates/cfr_core/benches/cfr_bench.rs` — Agent B.
- `benches/baseline.json` — Agent B.
- `crates/cfr_core/src/solver.rs` — Agent B owns surface-level changes.
- `crates/cfr_core/src/{kuhn,leduc,game,eval}.rs` — out of scope.
- Any other Python file in `poker_solver/` — out of scope.
- `pyproject.toml` — no Python dep changes; ChaCha8Rng is Rust-only.

If you discover that Agent A's or Agent B's signature is incompatible with what you need, **do not silently change either side**. Stop and write a short note to the orchestrator describing the conflict; the orchestrator will reconcile.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/pr8_spec.md`. Internalize §1 (goal + non-goals), §5 (public chance sampling — your stage), §6 (files to create + modify — your owned rows, ESPECIALLY the consistency-review note re `HUNLConfig.use_pcs`), §7 Layer C (your test layer), §8 Agent C deliverables + acceptance criteria, §9 items 2, 4, 5, 7 (your critical correctness items), §10 risks 2, 6, 9 (your risks), §11 decisions 2, 6, 7, 14 (your locked defaults).
2. **The PLAN (locked decisions):** `/Users/ashen/Desktop/poker_solver/PLAN.md`. Especially §1 "Public chance sampling: add after baseline DCFR converges (PR 8 perf work)" — confirms PCS is gated to PR 8.
3. **The autonomous log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md`. Skim for PR 8-related amendments.
4. **Spec consistency review:** `/Users/ashen/Desktop/poker_solver/docs/spec_consistency_review.md`. **CRITICAL:** I6 amendment — `HUNLConfig.use_pcs: bool = False` schema extension is explicitly authorized on the Python side by PR 8; PR 6 §4.1 pre-emptively mirrors this in its Rust `HUNLConfig` so the two PRs land in either order. You add the Python field; you confirm the Rust field is either already present (if PR 6 landed first) or will be added by Agent B alongside the `use_pcs` config wiring on the DCFR config struct. Coordinate with Agent B via the orchestrator.
5. **The DCFR Rust implementation (where your β-switch logic lives):** `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/dcfr.rs`. Identify the β-init / β-read sites (likely at construction time + at the discount-application time).
6. **The HUNL Python file (where your Python schema edit lives):** `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py`. The `HUNLConfig` dataclass is at ~lines 76-130. Note the existing fields' style (frozen=True, type hints) — match exactly. The lossless `infoset_key` is at lines ~309-318 — DO NOT TOUCH; preserve PR 3 behavior bit-for-bit.
7. **PR 6's `hunl_solver.rs`** (if present): `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/hunl_solver.rs`. Read it to understand where chance nodes are visited; that's where you wire the PCS sampler call. If the file is absent (PR 6 hasn't landed), stub the integration via a comment per spec §10 risk 6.
8. **Reference patterns:**
   - `references/papers/cfrplus_tammelin_2014.pdf` (Tammelin 2014; references PCS as prior MCCFR variant; `_INDEX.md:11`).
   - `references/papers/libratus_brown_2017_supplement.pdf` (Brown 2017 supplement; full ES-MCCFR pseudocode; `_INDEX.md:179-181` — closest implemented variant).
   - `references/code/noambrown_poker_solver/cpp/src/mccfr.cpp` lines 229-302 (**MIT**) — ES-MCCFR implementation; your PCS structurally mirrors this with different sampling target.

## Default decisions LOCKED (do not deviate)

These amendments / clarifications to the PR 8 spec win where the spec text differs:

- **Decision 11.2 = opt-in for v1.** `HUNLConfig.use_pcs: bool = False` (Python) + `pub use_pcs: bool = false` (Rust). PCS is the riskiest of the three optimizations (statistical, not numerically identical); a clean rollback path requires opt-in.
- **Decision 11.6 = per-iteration sampling granularity.** At each iteration, one outcome is sampled at each chance node in the recursive path; the (turn, river) pair the solver explores is different per iteration. Lower variance than per-chance-node independent sampling.
- **Decision 11.7 = explicit seed via solver config (`seed: u64 = 7`).** Deterministic for tests; user-overridable for production. The seed parameter lives on `PCSSampler::new(seed)`; the upstream config (`HUNLConfig` Python / Rust) passes it through.
- **Decision 11.14 = silent β-switch.** When `use_pcs=true`, the solver INTERNALLY adjusts β=0 → β=0.5. Not surfaced as a user-controlled field. Documented in `pcs.rs` module docstring + tested explicitly (a test sets `use_pcs=true` and asserts `solver.beta == 0.5` after construction).
- **PCS importance weight: K = number of outcomes** at the sampled chance node (e.g., 47 for turn, 46 for river). Per spec §5 "Importance weighting" math:
  ```
  E[w · v(c)] = sum_c (1/K) · K · v(c) = sum_c v(c)
  ```
- **PCS uses ChaCha8Rng** for portable, deterministic seeding across aarch64 + x86_64. From the `rand_chacha = "0.3"` crate. Tested via the `pcs_seed7_first100.json` fixture (spec §9 #7).
- **PCS samples PUBLIC chance only.** Private chance (hole cards = 1326 combos per player) is still enumerated — vector-form CFR over hand-pair reach probabilities. This distinguishes PCS from full ES-MCCFR.
- **Tolerances (spec §7 Layer C):**
  - Per-action mean absolute error across all infosets < `5e-3` (matches `pr7_spec.md` §1 + `tests/test_leduc_diff.py`).
  - Per-action max absolute error < `2e-2` (loose — PCS at finite iterations has tail variance).
  - Across 5 seeds: **mean** of per-seed mean-errors < `5e-3`.
- **Negative control test MUST FAIL** (importance weight removed → biased estimator → diverges from unsampled equilibrium). Per spec §7 "Negative control" + §9 #5.
- **No new Rust runtime deps beyond `rand = "0.8"` + `rand_chacha = "0.3"`.** ChaCha8Rng is in `rand_chacha`. No `nanorand`, no `rand_pcg`, no `rand_xoshiro` — ChaCha8 is the portable, reproducible choice.

## Public API contract (signatures Agent B + Agent C + downstream depend on)

### `crates/cfr_core/src/pcs.rs`

```rust
//! Public chance sampling (PCS) for the DCFR loop.
//!
//! Samples ONE public chance outcome per iteration at each chance node, instead
//! of enumerating all 47-49 turn / 45-47 river cards. Aggregates over iterations
//! with importance correction.
//!
//! **Variance vs full enumeration:** PCS is an unbiased estimator (with
//! importance weight K = number of outcomes); variance is higher. Empirically
//! ~5× more iterations needed to reach the same exploitability (Johanson 2012,
//! cited in Tammelin 2014). Cost reduction per chance node ~47× → net ~10×
//! per equivalent-quality iteration.
//!
//! **DCFR-PCS parameter compatibility:** PCS introduces sampling variance, which
//! interacts badly with β=0 (negative regrets reset each iter; sampling noise
//! has nowhere to go). When `use_pcs=true`, the solver INTERNALLY switches
//! β=0 → β=0.5 (per references/papers/_INDEX.md:38 caveat). Documented here +
//! tested explicitly in tests/test_pcs.rs.
//!
//! **Sampling granularity:** per-iteration (one outcome at each chance node in
//! the recursive path). Per Decision 11.6.
//!
//! **RNG:** ChaCha8Rng from `rand_chacha = "0.3"`. Portable across aarch64 +
//! x86_64 for fixed seed (tested via fixture).
//!
//! Pattern structurally mirrors references/code/noambrown_poker_solver/cpp/src/mccfr.cpp
//! lines 229-302 (MIT, attribution required). Different sampling target (public
//! chance vs ES-MCCFR's full action+chance), same recursive shape.

use std::collections::HashMap;
use rand::{Rng, SeedableRng};
use rand_chacha::ChaCha8Rng;

use crate::layout::TreeNodeId;
// Card type: use the existing eval::Card or equivalent from PR 6; placeholder here.
pub type Card = u8;  // bridge type; the real Card comes from PR 6's hunl module.

/// Public chance sampler for PCS-mode DCFR.
///
/// Holds per-chance-node cached outcome lists so we don't re-derive them per iter.
/// (Cost-amortization at build time.)
pub struct PCSSampler {
    /// Deterministic RNG seeded at construction.
    rng: ChaCha8Rng,
    /// Per-chance-node cached outcome lists: TreeNodeId -> Vec<(Card, weight)>.
    /// For HUNL postflop, weight is uniform 1/K; we still store it explicitly so
    /// non-uniform chance distributions (e.g., card-removal-effects ranges)
    /// could be added in a follow-up without API change.
    public_outcomes_per_node: HashMap<TreeNodeId, Vec<(Card, f64)>>,
}

impl PCSSampler {
    /// Construct a PCS sampler seeded for cross-platform deterministic sampling.
    /// `seed = 7` is the recommended default per Decision 11.7; user-overridable.
    pub fn new(seed: u64) -> Self;

    /// Register the public chance outcomes for a tree node. Build-time only.
    /// (Pre-computed once during tree construction; not called from the hot loop.)
    pub fn register_chance_node(&mut self, node: TreeNodeId, outcomes: Vec<(Card, f64)>);

    /// Sample ONE public outcome at the given chance node.
    /// Returns `(sampled_card, importance_weight)` where importance_weight = K
    /// (the number of outcomes; corrects for the sampling probability 1/K).
    ///
    /// Determinism: for a fixed seed + fixed call sequence, returns an identical
    /// stream of (Card, weight) pairs across aarch64 + x86_64.
    pub fn sample_public(&mut self, node: TreeNodeId) -> (Card, f64);

    /// Reset RNG state to the construction seed. Used for cross-iter
    /// reproducibility tests + per-seed convergence tests.
    pub fn reset(&mut self);

    /// Return the current RNG state's seed (for debugging / reproducibility).
    pub fn seed(&self) -> u64;
}
```

### `crates/cfr_core/src/hunl_solver.rs` modifications

(File assumed landed by PR 6. If absent, stub the integration via a `TODO(PR 6)` comment and proceed; the PR splits into 8a/8b per spec §10 risk 6.)

At each chance node visit:

```rust
fn visit_chance_node(&mut self, node: TreeNodeId, state: &mut HUNLState) -> f64 {
    if self.config.use_pcs {
        // PCS path: sample one outcome, recurse, multiply by importance weight.
        let (card, weight) = self.pcs_sampler.sample_public(node);
        state.apply_chance_outcome(card);
        let recursive_value = self.recurse(state);
        state.unapply_chance_outcome(card);
        weight * recursive_value
    } else {
        // Enumeration path: sum over all outcomes (existing PR 6 logic).
        let mut total = 0.0;
        for outcome in self.chance_outcomes_for(node) {
            state.apply_chance_outcome(outcome.card);
            total += outcome.probability * self.recurse(state);
            state.unapply_chance_outcome(outcome.card);
        }
        total
    }
}
```

The exact function names + signatures depend on PR 6's surface. Adapt accordingly; the principle is: at each chance node, branch on `self.config.use_pcs`.

### `crates/cfr_core/src/dcfr.rs` modifications (β-switch only)

At the β-init site (likely in solver construction):

```rust
let beta = if config.use_pcs {
    // Silent switch per spec §5 + §9 #4: β=0 would break with PCS variance.
    // Use β=0.5 (paper-recommended pruning-compatible value).
    0.5
} else {
    config.beta  // default 0.0 per DCFR(α=1.5, β=0, γ=2.0)
};
```

That's the entire β-switch logic. Do not modify other DCFR loop logic. Agent B's storage is `pub use_pcs: bool` on the DCFR config; you read it here.

### `crates/cfr_core/src/lib.rs` modification

Add ONLY:
```rust
pub mod pcs;
```

(Agent A adds `pub mod simd;`; Agent B adds `pub mod layout;`. Three independent lines.)

### `poker_solver/hunl.py` modification

Add to `HUNLConfig` (existing frozen dataclass):

```python
# Inside HUNLConfig (line ~76-130 of hunl.py):
use_pcs: bool = False
```

**Critical:** the `infoset_key` method (lines ~309-318) and all other PR 3 behavior is preserved EXACTLY. Your edit is a single new field with a default; no behavior change unless the caller explicitly sets `use_pcs=True`. Run `pytest tests/test_hunl_core.py tests/test_hunl_tree.py` before and after — confirm 138/138 tests still pass.

### `tests/test_pcs.rs`

Rust integration test, Layer C per spec §7. Convergence + negative-control + cross-platform determinism.

```rust
//! PCS convergence tests (Layer C).
//!
//! Pass criteria per spec §7 Layer C + §9 #2:
//! - Per-action mean absolute error across all infosets < 5e-3.
//! - Per-action max absolute error < 2e-2.
//! - Across 5 distinct seeds: MEAN of per-seed mean-errors < 5e-3.
//!
//! Negative control: removes the importance weight → estimator becomes biased →
//! test FAILS (confirms tolerance is calibrated correctly).

use poker_solver_cfr_core::pcs::PCSSampler;
// (other imports for Leduc DCFR solver via the Rust API)

#[test]
fn test_pcs_leduc_converges_within_tolerance_across_5_seeds() {
    // Run Leduc DCFR with use_pcs=true at 10K iter for seeds [0, 1, 2, 3, 4].
    // Run Leduc DCFR with use_pcs=false (full enumeration) at 2K iter as ground truth.
    // For each seed: compute per-action MAE across all infosets vs ground truth.
    // Assert: mean(per_seed_mae[0..5]) < 5e-3.
    // Assert: max(per_seed_mae[0..5]) < 2e-2.
    todo!()
}

#[test]
fn test_pcs_deterministic_for_fixed_seed() {
    // Two calls to PCSSampler::new(7) followed by 100 sample_public calls each
    // (on a synthetic chance node with 47 outcomes) produce the same sequence.
    todo!()
}

#[test]
fn test_pcs_cross_platform_determinism_fixture() {
    // Per spec §9 #7: sample 100 cards with seed=7 on synthetic chance node;
    // compare against tests/fixtures/pcs_seed7_first100.json (committed fixture).
    // Same fixture passes on aarch64 + x86_64.
    let fixture: Vec<u8> = serde_json::from_reader(
        std::fs::File::open("tests/fixtures/pcs_seed7_first100.json").unwrap()
    ).unwrap();

    let mut sampler = PCSSampler::new(7);
    // ... register a synthetic chance node with 47 outcomes ...
    let mut sampled = Vec::with_capacity(100);
    for _ in 0..100 {
        let (card, _w) = sampler.sample_public(/* synthetic node id */);
        sampled.push(card);
    }
    assert_eq!(sampled, fixture);
}

#[test]
fn test_pcs_importance_weight_is_K() {
    // Register a chance node with K=47 outcomes (uniform).
    // Sample once. Assert returned weight == 47.0.
    todo!()
}

#[test]
fn test_pcs_beta_switch_to_half_when_enabled() {
    // Construct a solver with use_pcs=true. Assert solver.beta == 0.5.
    // Construct a solver with use_pcs=false. Assert solver.beta == 0.0.
    todo!()
}

#[test]
#[should_panic(expected = "diverged")]  // or expected-failure mechanism
fn test_pcs_negative_control_without_importance_weight_fails() {
    // Per spec §7 + §9 #5: remove the importance weight from the PCS path;
    // run the same convergence test; assert the estimator's per-action MAE
    // exceeds 5e-3 (test FAILS = confirms importance weight is doing real work).
    //
    // Implementation: this is a separate test path that DOES NOT modify pcs.rs;
    // instead, you simulate the bias by multiplying by 1.0 instead of K. The
    // test asserts that this biased path's MAE > 5e-2 (orders-of-magnitude
    // worse than the proper PCS path).
    todo!()
}

#[test]
fn test_pcs_sample_public_returns_valid_card_index() {
    // Sample 1000 times from a chance node with K=47 outcomes (cards 0..47).
    // Assert every returned card is in [0, 47).
    todo!()
}
```

### `tests/fixtures/pcs_seed7_first100.json`

Cross-platform determinism fixture. Captured ONCE on aarch64-apple-darwin; the cross-platform test on x86_64 asserts the same sequence.

```json
[<u8>, <u8>, ..., <u8>]  // 100 values, captured from PCSSampler::new(7) sampling
                          // 100 times on a synthetic chance node with 47 uniform outcomes.
```

**Generation:** write a small Rust binary (`crates/cfr_core/examples/gen_pcs_fixture.rs`) that constructs the sampler, samples 100 cards, and prints the JSON; run it, commit the output. Optional: include the example binary itself or just commit the fixture.

## Critical correctness items

### 1. PCS convergence to same Nash value (spec §7 Layer C + §9 #2)

PCS path at 10K iter converges to the same Leduc Nash value as the full enumeration path at 2K iter, within `5e-3` per-action mean (across 5 seeds) and `2e-2` per-action max. **No tolerance below this:** matches `tests/test_leduc_diff.py` baseline.

If convergence fails:
- First, check importance weighting (the load-bearing bias-correction; per §9 #5).
- Second, check β-switch is active (β=0.5 when `use_pcs=true`; per §9 #4).
- Third, check the sampling distribution (must be UNIFORM over the K outcomes for the spec's `w = K` weighting to be correct).
- If all three look right, the variance bound may be wider than the spec estimates; flag to orchestrator before relaxing the tolerance.

### 2. Importance weight = K (spec §5 "Importance weighting" + §9 #5)

The estimator is:
```
E[w · v(c)] = sum_c (1/K) · K · v(c) = sum_c v(c)  ✓ unbiased
```
**Without the K-weight:**
```
E[v(c)] = sum_c (1/K) · v(c) = (1/K) sum_c v(c)  ✗ biased
```
The biased path produces estimates K× smaller than reality; the average strategy diverges from the unsampled equilibrium. The **negative-control test** (per §7 Layer C "Negative control") explicitly demonstrates this: it runs PCS without the K-weight and asserts the MAE > 5e-2 (orders-of-magnitude worse than the proper path).

### 3. β=0 → β=0.5 silent switch (spec §5 + §9 #4)

When `config.use_pcs == true`, the solver internally sets `beta = 0.5` (overriding the DCFR default 0.0). Documented in `pcs.rs` module docstring; tested explicitly (`test_pcs_beta_switch_to_half_when_enabled`).

### 4. Cross-platform RNG determinism (spec §9 #7 + §10 risk 9)

ChaCha8Rng from `rand_chacha = "0.3"` is reproducible across aarch64 + x86_64 for fixed seed. **Test fixture** (`tests/fixtures/pcs_seed7_first100.json`) is captured ONCE and asserted on both platforms. If the fixture diverges on x86_64, the test FAILS — do not silently regenerate the fixture per-platform.

### 5. Per-iteration sampling granularity (Decision 11.6)

At each iteration, one outcome is sampled at each chance node in the recursive path. This is the LOWER-VARIANCE choice (vs per-chance-node independent sampling). The `sample_public(node)` API is called once per chance node per iteration; the sampler's RNG state advances by one draw per call.

### 6. PR 3 lossless behavior preserved on Python side (your `hunl.py` edit)

The `use_pcs: bool = False` field is ADDITIVE only. The `infoset_key` method (lines ~309-318) is UNCHANGED. PR 3's 138 tests must still pass. **Validation:** run `pytest tests/test_hunl_core.py tests/test_hunl_tree.py` before and after your edit; expect identical pass count.

### 7. PR 6 absence (spec §10 risk 6)

If `crates/cfr_core/src/hunl_solver.rs` does not exist (PR 6 hasn't landed at PR 8 spec write-time per spec §1 + §6 footer + §10 risk 6), stub the integration point via a comment:

```rust
// TODO(PR 6): wire PCSSampler::sample_public at chance nodes when use_pcs=true.
// See pcs.rs and docs/pr8_prep/pr8_spec.md §5.
```

And split the PR into 8a (SIMD + layout, lands on top of PR 5 / Python) and 8b (PCS, lands on top of PR 6). Flag this to the orchestrator immediately if `hunl_solver.rs` is absent.

### 8. No new Python dependencies

`use_pcs: bool = False` is a primitive bool; no `pyproject.toml` change. No `import` change in `hunl.py`. The `HUNLConfig` Python dataclass already supports bool fields. Verify with `mypy --strict poker_solver/hunl.py` after your edit.

## License-aware sourcing

**You may port architecturally (not code-copy) from MIT/Apache sources:**
- `references/code/noambrown_poker_solver/cpp/src/mccfr.cpp` lines 229-302 (**MIT**) — ES-MCCFR implementation. Your PCS structurally mirrors this (different sampling target but same recursive shape). Cite in `pcs.rs` module docstring.
- `references/code/open_spiel/` (**Apache 2.0**) — OS solvers + MCCFR implementations; OK to port with attribution.

**You may NOT copy from AGPL sources:**
- `references/code/postflop-solver/` — **AGPL v3**, read-only only.
- `references/code/TexasSolver/` — **AGPL v3**, same rule.

**You may NOT extrapolate from training data.** Cite local references for any non-trivial pattern.

If you copy a non-trivial snippet (>~5 LOC) from `mccfr.cpp` or an Apache source, add an attribution comment:
```rust
// Pattern from noambrown_poker_solver/cpp/src/mccfr.cpp (MIT, attribution required).
// Reference: references/code/noambrown_poker_solver/cpp/src/mccfr.cpp:229-302
```

## Quality bar

- **`cargo test --release test_pcs`** passes on aarch64-apple-darwin. Convergence test (5 seeds) + determinism test + cross-platform fixture test + negative-control + β-switch test all pass.
- **`cargo clippy --all-targets -- -D warnings`** clean.
- **`cargo fmt`** clean (`cargo fmt --check`).
- **PR 3 Python tests preserved.** `pytest -x tests/test_hunl_core.py tests/test_hunl_tree.py` — 138 existing tests still pass after your `hunl.py` edit.
- **`ruff check poker_solver/hunl.py`** + **`mypy --strict poker_solver/hunl.py`** clean.
- **No new Python deps.** `pyproject.toml` unchanged.
- **New Rust deps:** ONLY `rand = "0.8"` + `rand_chacha = "0.3"`. No `nanorand`, `rand_pcg`, etc.
- **Code size budget: ~400-700 LOC** combined across `pcs.rs` (~300 LOC) + `test_pcs.rs` (~250 LOC) + `hunl_solver.rs` delta (~50 LOC) + `dcfr.rs` β-switch delta (~10 LOC) + `hunl.py` delta (1 LOC). Stay within budget.

## Reference-first rule

Before any technical claim, citation, or formula, check the local references. Never extrapolate from training data when a local authoritative source exists. The reference index is `/Users/ashen/Desktop/poker_solver/references/README.md` — skim for "PCS", "public chance sampling", "MCCFR", "importance sampling" entries.

The PCS algorithm + variance bounds + β=0.5 caveat are cited explicitly:
- Johanson 2012 (PCS variance: ~5× more iterations).
- Tammelin 2014 (DCFR; `_INDEX.md:38` β=0.5 caveat).
- Brown 2017 Libratus supplement (ES-MCCFR pseudocode; `_INDEX.md:179-181`).

Cite any non-trivial claim against these references; never extrapolate.

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Format + lint (Rust)
cargo fmt --check --manifest-path crates/cfr_core/Cargo.toml
cargo clippy --manifest-path crates/cfr_core/Cargo.toml --all-targets -- -D warnings

# 2. Lint Python edit
ruff check poker_solver/hunl.py
black --check poker_solver/hunl.py
mypy --strict poker_solver/hunl.py

# 3. Build (release)
cargo build --release --manifest-path crates/cfr_core/Cargo.toml

# 4. PR 3 Python behavior preservation (138 existing tests)
pytest -x tests/test_hunl_core.py tests/test_hunl_tree.py 2>&1 | tail -10

# 5. YOUR Rust tests
cargo test --release --manifest-path crates/cfr_core/Cargo.toml --test test_pcs 2>&1 | tail -30

# 6. Confirm cross-platform determinism fixture is committed
ls -la tests/fixtures/pcs_seed7_first100.json
python3 -c "import json; d = json.load(open('tests/fixtures/pcs_seed7_first100.json')); assert len(d) == 100; print('fixture OK, first 5:', d[:5])"

# 7. Confirm `use_pcs` field is on Python HUNLConfig
python3 -c "from poker_solver.hunl import HUNLConfig; c = HUNLConfig(); assert hasattr(c, 'use_pcs'); assert c.use_pcs is False; print('use_pcs default OK')"

# 8. Smoke test: end-to-end Leduc convergence with PCS enabled
cargo test --release --manifest-path crates/cfr_core/Cargo.toml \
    --test test_pcs test_pcs_leduc_converges_within_tolerance_across_5_seeds \
    2>&1 | tail -10

# 9. Negative control: importance weight removed → test FAILS as expected
cargo test --release --manifest-path crates/cfr_core/Cargo.toml \
    --test test_pcs test_pcs_negative_control_without_importance_weight_fails \
    2>&1 | tail -10
# Expected: this test passes (the `#[should_panic]` annotation succeeds).
```

If any of the above fails, fix the issue before reporting done. If a convergence test reveals a spec ambiguity, **stop and flag it** — do not silently relax the tolerance.

## Report back format

When done, write a concise report (≤300 words) covering:

1. Files created with line counts (`pcs.rs`, `test_pcs.rs`, `tests/fixtures/pcs_seed7_first100.json`); files modified with line-delta (`hunl_solver.rs`, `dcfr.rs`, `lib.rs`, `hunl.py`, `Cargo.toml`).
2. Convergence test result: per-seed MAE for seeds [0..5]; mean of per-seed MAE; max per-action error. Confirm < 5e-3 mean + < 2e-2 max.
3. Negative-control test result: with importance weight removed, what's the MAE? (Should be orders-of-magnitude worse — confirm.)
4. Cross-platform fixture: was it captured on aarch64? First 5 values for sanity.
5. β-switch test result: when `use_pcs=true`, what's `solver.beta`? (Expect 0.5.)
6. PR 6 dependence: was `hunl_solver.rs` present? If not, what stub did you leave?
7. PR 3 Python tests: 138/138 still pass after `hunl.py` edit? (yes/no + count.)
8. Any spec amendment you made or contract drift you flagged (especially around the `use_pcs` field placement on the Rust DCFR config — coordinate with Agent B; and the β-switch logic boundary between you and Agent B).
9. License attributions added (the `pcs.rs` module docstring + any inline `// Pattern from mccfr.cpp ...` comment).
10. Open questions for human review — especially: is PR 6 landed? If not, the 8a/8b split per spec §10 risk 6 may apply.
