# v1.10 PR-3 — Vector-Form Flop Forward Walk: Design + Scaffold

**Status:** Design only. Implementation deferred until PR-2 (#190) merges.
**Date:** 2026-05-28.
**Source plan:** [`docs/v1_10_postflop_optimization_plan.md`](./v1_10_postflop_optimization_plan.md) §2 Candidate C (commit `da38888`).
**Predecessor:** PR-2 (#190, `feat-v1-10-2-vector-turn`) — adds `BettingTreeMode::TemplateExtract`, `ChanceTemplate`, `traverse_turn_chance_recursive`.

---

## 1. Headline + Headlines

- **What PR-3 ships:** extend PR-2's `ChanceTemplate` extraction to **two-level chance compaction** (flop → turn → river). The flop subgame's outer chance loop iterates `45 × 44 = 1980` (turn_card, river_card) runouts against a precomputed cache instead of recursively rebuilding the river-betting-tree per runout.
- **Headline target:** flop top_k=169 in **<120s** (currently OOM-killed at 5 min / 2.3 GB RSS). 10-20× wall reduction + 4-5× RSS reduction (2.3 GB → ~500 MB).
- **Bit-identity:** PR-3 preserves DFS visit order and IEEE-754 summation order across all 1980 runouts; **1e-12 strategy / 1e-9 exploitability tolerance** vs PR-2 reference.
- **Risk:** HIGH — DFS-order drift is the headline failure mode. Mitigation = small-tree synthetic fixture (5 turn cards × 5 river cards × 1 decision) that fits in mental working memory.

---

## 2. Background — PR-2's Template Extraction Recap

PR-2 lands these symbols (see [`crates/cfr_core/src/exploit.rs`](../crates/cfr_core/src/exploit.rs) lines 398-561 in the WIP):

| Symbol | Kind | Purpose |
|---|---|---|
| `BettingTreeMode` | enum | `Standard` (legacy) vs `TemplateExtract` (PR-2+) |
| `ChanceTemplate` | struct | `{ chance_node_idx: usize, structure_hash: u64 }` |
| `BettingTree::chance_templates` | field | `Vec<ChanceTemplate>` — out-of-band metadata, empty in `Standard` mode |
| `BettingTree::build_with_mode` | fn | Replaces `build_from`; extracts templates when mode = `TemplateExtract` |
| `BettingTree::extract_chance_templates` | fn | Walks `FlatNode::Chance` nodes; records template iff all children share structural identity |
| `BettingTree::structure_hash` + `hash_subtree` | fns | Recursive structural hash (variant tag + fan-out, ignores payload) |
| `VectorDCFR::has_chance_template` | field | `Vec<bool>` indexed by `FlatNode` index for O(1) chance-arm dispatch |
| `traverse_turn_chance_recursive` | fn | Specialized chance walker (PR-2: bit-identical to legacy; PR-3 extends) |

**Key insight from PR-2:** the FlatNode list is **unchanged** between `Standard` and `TemplateExtract`. Only out-of-band metadata is added. This invariant must hold in PR-3 too — we never mutate the tree shape, only the walker dispatch.

**Critical assumption about PR-2's landing form:** the dispatch hook for templates is `traverse_turn_chance_recursive` (a free function). PR-3 will either rename it `traverse_chance_template_recursive` (generalized) OR add a parallel `traverse_flop_chance_recursive` that takes precedence when the chance node is at flop-level. The current scaffold chooses **the latter** to minimize PR-2-merge conflicts.

---

## 3. Two-Level Chance Compaction — The Math

### 3.1 Why double broadcast is sound

The flop subgame's chance structure is a **chain of two chance nodes**:

```
flop-root (decision tree)
   ...
   FlatNode::Chance (turn-deal, 45 outcomes, prob = 1/45)
      child[i] for i in 0..45
         (turn-line decision tree)
         ...
         FlatNode::Chance (river-deal, 44 outcomes, prob = 1/44)
            child[j] for j in 0..44
               (river-line decision tree)
               ...
               FlatNode::Showdown { board: [f0, f1, f2, t_i, r_j], ... }
```

The river-line decision subtree shape is **identical across all `45 × 44 = 1980` (turn_card, river_card)** combinations — same `BettingTree` nodes, same `action_count`, same `key_suffix` modulo the `t_i` / `r_j` substring (which lives in the leaf board payload, not the betting-tree shape).

### 3.2 The cache table

PR-3 introduces a `RunoutCache` keyed by `(turn_card_idx, river_card_idx) → SubtreeValue` where `SubtreeValue` is a per-hand value vector `Vec<f64>` of length `update_hands`. Pre-allocate once per solve, reuse across all `traverse` calls.

```rust
struct RunoutCache {
    // 45 × 44 = 1980 (turn, river) runouts.
    // Indexed by (turn_card_idx_in_chance_children × 44 + river_card_idx_in_chance_children).
    // Each cell is a Vec<f64; update_hands] reusing pre-allocated storage.
    runout_values: Vec<Vec<f64>>,
    // Reverse map: (turn_idx, river_idx) → flat_node_idx of the Showdown leaf.
    // Built once at solve-start by walking the betting tree.
    showdown_node_for_runout: Vec<usize>,
}
```

### 3.3 Two strategies, A and B

**Strategy A: Eager precompute.** At each `traverse_flop_chance` call, the walker first walks the 1980 river-line subtrees in **one outer loop**, populating `runout_values[turn_idx][river_idx]`. Then a second loop does the double weighted sum:

```
for turn_idx in 0..45:
    turn_values[h] = 0
    for river_idx in 0..44:
        for h in 0..update_hands:
            turn_values[h] += (1/44) * runout_values[turn_idx * 44 + river_idx][h]
    for h in 0..update_hands:
        flop_values[h] += (1/45) * turn_values[h]
```

The precompute step is `O(1980 × river_subtree_cost)` per `traverse_flop_chance` call, **same** as the legacy loop. The win is **memory**: the river-line subtree storage is shared across all 1980 runouts (single template; per-runout multiplier only).

**Strategy B: Lazy on-demand.** Walk the chain depth-first like the legacy code, but at each river-line walk, **dispatch through a single pre-allocated scratch buffer** (the `update_hands`-sized `Vec<f64>` lives in `RunoutCache` and is overwritten in place per runout).

**Decision: B for v1.10 PR-3.** A is cleaner mathematically but requires `1980 × update_hands × 8 bytes` of cache (at update_hands=1081 = ~17 MB) plus DFS reorder, which risks bit-identity. B preserves the legacy DFS order exactly and only adds scratch-buffer pre-allocation — same arithmetic, same summation order, just no `vec![0.0; N]` churn.

---

## 4. The `traverse_flop_chance` Walker Shape

### 4.1 Signature (mirrors PR-2's `traverse_turn_chance_recursive`)

```rust
#[allow(clippy::too_many_arguments)]
pub(crate) fn traverse_flop_chance_recursive(
    tree: &BettingTree,
    eval_ctx: &EvalContext,
    terminal_cache: &TerminalCache,
    flop_chance_prob: f64,          // 1/45 (turn-deal prob)
    flop_chance_children: &[usize], // 45 turn-card subtree roots
    update_player: usize,
    iteration: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
    reach_p: &[f64],
    reach_opp: &[f64],
    infosets: &mut [Option<VectorInfosetData>],
    offset: usize,
    allow_parallel: bool,
    has_chance_template: &[bool],
    runout_cache: &mut RunoutCache, // <-- NEW vs PR-2
) -> Vec<f64> { ... }
```

### 4.2 Dispatch logic in `traverse_recursive_with_parallel`

In the `FlatNode::Chance { prob, children }` arm, **after** PR-2's `has_chance_template[node_idx]` check, add a second check: is this chance node a flop-level chance (i.e., does its first child contain another chance subtree)?

```rust
if !has_chance_template.is_empty() && has_chance_template[node_idx] {
    // PR-3: check if this is the OUTER (flop-level) chance node.
    let is_flop_chance = matches!(
        // Inspect the structure of children[0]'s subtree — if its DFS
        // contains a FlatNode::Chance node, this is the flop chance.
        // Otherwise it's the turn chance (PR-2 case).
        tree.subtree_contains_chance(children[0]),
        true
    );
    if is_flop_chance {
        return traverse_flop_chance_recursive(
            tree, eval_ctx, terminal_cache,
            *prob, children, update_player, iteration,
            alpha, beta, gamma, reach_p, reach_opp,
            infosets, offset, allow_parallel,
            has_chance_template, runout_cache,
        );
    }
    // PR-2 turn-chance path (unchanged).
    return traverse_turn_chance_recursive(...);
}
```

**Alternative:** instead of runtime detection via `subtree_contains_chance`, classify the chance template at extraction time. Augment `ChanceTemplate` to record `chance_depth: u8` ∈ `{1, 2}` (1 = leaf-most chance i.e. turn→river, 2 = flop→turn→river). Pick this at `extract_chance_templates` time. **Recommended over runtime check** — cleaner, O(1) dispatch.

---

## 5. Memory Layout

### 5.1 RunoutCache placement

`RunoutCache` lives in `VectorDCFR::solve` (one per solve, not one per traverse call), instantiated **after** `TerminalCache::build` but **before** the iteration loop. Constructed once, mutated in place across all iterations.

```rust
pub(crate) fn solve(&mut self, tree: &BettingTree, eval_ctx: &EvalContext, ...) {
    ...
    let terminal_cache = TerminalCache::build(tree, eval_ctx);
    let mut runout_cache = RunoutCache::build(tree, eval_ctx); // <-- NEW
    ...
    for _ in 0..iterations {
        ...
        traverse_recursive_with_parallel(
            ..., &mut runout_cache, // <-- threaded through
        );
    }
}
```

### 5.2 RunoutCache::build

Walks the betting tree once at solve-start, identifying the flop chance node (`chance_depth = 2` template) and pre-allocating:

```rust
impl RunoutCache {
    pub(crate) fn build(tree: &BettingTree, eval_ctx: &EvalContext) -> Self {
        let max_hands = eval_ctx.hand_count.iter().copied().max().unwrap_or(0);
        // Find the flop-chance template node.
        let flop_chance_idx = tree.chance_templates.iter()
            .find(|t| t.chance_depth == 2)
            .map(|t| t.chance_node_idx);
        let runout_count = match flop_chance_idx {
            Some(idx) => {
                // 45 turn children × 44 river children each (typically).
                // Compute from tree shape rather than hardcoding for safety.
                if let FlatNode::Chance { children, .. } = &tree.nodes[idx] {
                    let turn_n = children.len();
                    // Look at children[0]'s first inner chance:
                    let river_n = tree.first_inner_chance_fanout(children[0]).unwrap_or(0);
                    turn_n * river_n
                } else { 0 }
            }
            None => 0,
        };
        // One Vec<f64> of length max_hands per runout. Pre-allocated; reused
        // in place across iterations.
        let runout_values = (0..runout_count)
            .map(|_| vec![0.0_f64; max_hands])
            .collect();
        Self { runout_values, ... }
    }
}
```

**Memory footprint:** `1980 × 1081 × 8 = ~17 MB` at top_k=169 — small compared to the 2.3 GB legacy footprint. At smaller top_k it scales linearly.

### 5.3 Scratch buffer reuse pattern

Inside `traverse_flop_chance_recursive`, the per-river-line walk overwrites `runout_cache.runout_values[turn_idx * river_n + river_idx]` in place rather than allocating fresh. The accumulator `values` for the outer (flop) loop still needs one `Vec<f64>` allocation per call — defer this to Candidate A (the arena PR, v1.10 PR-1).

---

## 6. DFS-Order Preservation Strategy

**Why this is the hardest part:** the regret update at each `Decision` node depends on the **value backpropagated from its children**. If we reorder the DFS, the backprop accumulation can have a different IEEE-754 summation order, breaking bit-identity even though the algorithm is mathematically equivalent.

**The invariant:** for any flop-rooted subgame, `traverse_flop_chance_recursive` must visit `Decision` nodes in **the same global order** as the legacy `traverse_recursive_with_parallel`:

```
turn_card[0]
  decision[0,0], decision[0,1], ..., decision[0,N_turn0-1]
  river_card[0,0]
    decision[0,0,0], ...
  river_card[0,1]
    decision[0,1,0], ...
  ...
  river_card[0,43]
turn_card[1]
  decision[1,0], ...
  river_card[1,0]
  ...
turn_card[44]
  ...
```

**Enforcement mechanism:**
1. In PR-3 the outer loop iterates `flop_chance_children` in index order (matches legacy `for &c in children`).
2. Within each turn subtree, the per-turn-line decision walk delegates to `traverse_recursive_with_parallel` (unchanged from legacy), which itself walks river-chance via PR-2's `traverse_turn_chance_recursive` — preserved DFS.
3. The 1980-cell `runout_values` cache is populated **lazily** as the recursion reaches each leaf — not eagerly batched. This is Strategy B (Section 3.3).
4. The chance-arm accumulator update `values[h] += prob * child_values[h]` is performed in the **outer flop loop** in the same order as legacy: `for turn_idx in 0..45 { ... values[h] += (1/45) * turn_values[h] ... }`.

**Test gate:** the small-tree synthetic fixture (Section 7.4) is constructed to make the DFS-order property visible — if PR-3 reorders, the strategy probabilities diverge **outside** float roundoff (10^-6 or larger).

---

## 7. Diff-Test Fixtures

Per plan §4.3, the v1.10-3 diff-test gate uses these specific fixtures:

### 7.1 F4.1 — Standard Flop (Qh 7c 2d)

**Config:** starting_stack=10000, starting_street=Flop, board=Qh7c2d, bet_size_fractions=(0.5, 1.0), postflop_raise_cap=3, hero_classes=villain_classes=HAND_CLASSES_8 (AA/KK/QQ/JJ/AKs/AKo/AQs/AQo), iters=2.

**Currently:** skipped in `test_v1_10_canonical_diff.py` (line 320-340 in current scaffold) with reason "Flop subgame OOMs on main; re-enable after v1.10-1 (arena) lands."

**PR-3 expectation:** runnable post-PR-3. Baseline recapture required.

### 7.2 F4.2 — Wet Flop (JsTs9h)

**Config:** identical to F4.1 except board=JsTs9h. New addition for PR-3.

**Purpose:** wet board → typically wider continuation strategies → exercises mixed-strategy infosets that are sensitive to chance-sum order drift.

### 7.3 F4.3 — Static Flop (Kc7s2d)

**Config:** identical to F4.1 except board=Kc7s2d. New addition for PR-3.

**Purpose:** static board → typically pure or near-pure strategies → exercises the regret-matching pure-strategy boundary (catches different drift mode than F4.2).

### 7.4 Small-Tree Synthetic Fixture (F4_synth)

**Config:**
- starting_stack=200, big_blind=100, starting_street=Flop, board=2c3d4h.
- bet_size_fractions=(1.0,) — single bet size, raise_cap=1, so 1 decision per street.
- Both players get the same 4 hand classes (AsKs, AhKh, AdKd, AcKc) — only 4 hands.
- iters=10.

**Why this fixture matters:** small enough to enumerate by hand. The total `1980 × 4 × 1 = ~8000` regret updates can be predicted analytically. **Any DFS-order drift between legacy and PR-3 produces a visible (>1e-6) strategy difference.**

**Property tested:** PR-3's vector-form walker produces bit-identical output to legacy when run on a fixture where every step is hand-traceable.

### 7.5 Tolerances (per plan §4.2)

| Quantity | Tolerance | Justification |
|---|---|---|
| Per-history strategy entry | 1e-12 | float roundoff |
| Exploitability | 1e-9 | sum of many CF-utilities |
| Game value | 1e-12 | direct readout |
| Per-combo BR action argmax | exact | no float tolerance |

---

## 8. Implementation Timeline (After PR-2 Lands)

Estimate: **5-7 working days** total (Plan §3 budgeted 5 days for vector turn; PR-3 is 1.4× larger but the framework is reused).

| Step | Wall | Gates / Diff-Tests |
|---|---|---|
| **1. Rebase on PR-2 tip.** Resolve any conflicts in `dcfr_vector.rs::traverse_recursive_with_parallel` and `exploit.rs::ChanceTemplate`. | 0.5 day | `cargo test --lib --release` green |
| **2. Extend `ChanceTemplate` with `chance_depth: u8`.** Update `extract_chance_templates` to compute depth (1 = turn-most, 2 = flop-most). Add `BettingTree::first_inner_chance_fanout` helper. | 0.5 day | Existing PR-2 tests (`template_extract_finds_turn_chance_node`, etc.) still pass at 1e-12 |
| **3. Build `RunoutCache` struct + `build()` method.** | 0.5 day | `cargo build` clean; `cargo clippy --all-targets -- -D warnings` clean |
| **4. Write `traverse_flop_chance_recursive` body.** Strategy B (lazy on-demand, scratch reuse). Dispatch hook in `traverse_recursive_with_parallel`. | 2 days | F4_synth at 1e-12 strategy; F1.1/F1.3 unchanged (no flop chance, depth=0); turn-only fixtures unchanged (PR-2 path still wins) |
| **5. Recapture canonical baseline.** Run F4.1 (8-class, restored from 3-class), F4.2, F4.3 against PR-3 tip; bake into `tests/fixtures/v1_10_canonical_baseline.json`. | 0.5 day | Baseline diff against committed JSON at 1e-12 |
| **6. Perf bench + report.** Run `scripts/run_v1_10_perf_bench.py` on the J7o A♦8♥9♦ 40-BB fixture at top_k ∈ {4, 15, 50, 169}. Write `docs/v1_10_pr3_perf_2026-MM-DD.md`. | 1 day | top_k=169 flop <120s on M4 Pro arm64; RSS ≤1 GB |
| **7. Integration test sweep + audit prep.** | 0.5 day | Full v1.10 canonical diff gate, all 8 kill-switch fixtures + 3 PR-3 additions, all bit-identical to PR-2 reference on non-flop fixtures |
| **8. Persona retest.** | 0.5 day | 17/0/0/0 persona table unchanged |

**Each step's diff-test gate is the dependency.** A test failure at step N rolls back to step N-1.

**Estimated implementation wall (post-PR-2-merge):** 6 working days median; 9 days p90 if DFS-order drift bug surfaces and requires the small-tree analytical fixture.

---

## 9. Open Questions / Decisions Deferred to Implementation

1. **Does PR-2 rename `traverse_turn_chance_recursive`?** Scaffold assumes NO — PR-3 adds a parallel `traverse_flop_chance_recursive` with its own dispatch hook. If PR-2 lands with the function renamed to `traverse_chance_template_recursive` (generalized), PR-3 rebase needs a small touch-up.

2. **Should `RunoutCache` live in `VectorDCFR` (struct field) or be passed through as `&mut RunoutCache` argument?** Scaffold assumes argument-passing for testability + minimum API surface change. Could be revisited if it makes `traverse_recursive_with_parallel`'s signature unwieldy.

3. **Does PR-3 require a new `BettingTreeMode` variant?** Scaffold says NO — `TemplateExtract` is sufficient, just extended to record `chance_depth`. New variant `FlopTemplateExtract` would be over-engineering since the depth distinction is metadata, not behavior.

4. **Interaction with Rayon (PR-4)?** PR-4 already merged on main (commit `f5ec665`) and parallelizes the flop chance at level 1 (45 turn cards). PR-3's vector-form walker must compose with rayon — recommend `allow_parallel=false` once entering `traverse_flop_chance_recursive` to prevent oversubscription. Scaffold reflects this.

---

## 10. References

- Plan: [`docs/v1_10_postflop_optimization_plan.md`](./v1_10_postflop_optimization_plan.md) — §2 Candidate C; §4 diff-test strategy; §8 file-level pointers.
- PR-2 WIP code: `/Users/ashen/Desktop/poker_solver_worktrees/feat-v1-10-2-vector-turn/crates/cfr_core/src/{exploit.rs,dcfr_vector.rs}`.
- PR-2 GitHub: https://github.com/<owner>/<repo>/pull/190 (HEAD `f8892942`).
- PR-2 task brief: see `docs/v1_10_postflop_optimization_plan.md` §2 Candidate B.
- Brown & Sandholm 2019 (DCFR): `references/papers/brown_sandholm_2019_dcfr.pdf` (not directly used by PR-3 but sets the algorithmic ground truth).
- Brown reference implementation (chance enumeration pattern): `references/code/noambrown_poker_solver/cpp/src/river_game.h:28-33`.
- Postflop-solver arena pattern (precedent, not copied): `references/code/postflop-solver/src/alloc.rs` (AGPL — no code copy).
- Existing canonical diff harness: [`tests/test_v1_10_canonical_diff.py`](../tests/test_v1_10_canonical_diff.py).
- Existing rayon dual-path precedent: [`tests/test_vector_rayon_diff.py`](../tests/test_vector_rayon_diff.py).

---

*Design author: agent at `/Users/ashen/Desktop/poker_solver_worktrees/feat-v1-10-3-vector-flop-design/`, 2026-05-28.*
*Implementation: deferred until PR-2 (#190) merges. Estimated 6 working days post-merge.*
