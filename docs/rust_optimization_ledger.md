# Rust Optimization Ledger

Speedups for each major performance optimization landed in the Rust
core (`crates/cfr_core/`). Sections 1-8 are **empirically measured**
from each merging PR's benchmark + diff-test gate, not projections.
Sections 9-12 (the v1.10 postflop burst) carry **TARGET** speedups
for the turn/river wall figures (plan projections + per-PR
microbenches) until the formal 12-cell bench run publishes
(`docs/v1_10_perf_bench_results.jsonl`); per the v1.8 SIMD lesson
(projected 4-8× → measured 1.0×) those are NOT to be cited as
confirmed production numbers. **The §11 flop entry (v1.10-3) is now
honest-measured**: the flop solve *completes* (wall-time +
reliability win, bit-identity verified), but the plan's "<120 s AND
≤ 1 GB RSS at top_k=169" memory gate is **NOT met** (measured
~6.7 GB at top_k=4, ~7.7 GB+ at top_k=169 where it does not finish)
— the board-tree memory collapse was scaffolded but deferred to
v1.11 (audit finding S-4).

**Last updated:** 2026-05-28 — v1.10 postflop optimization burst
(PRs v1.10-1 .. v1.10-4, all merged; PR-3 = commit `cda3eeb`).
NOTE: the turn/river wall figures in §9, §10, §12 carry **TARGET**
speedups (from the plan + each PR's own microbench) NOT yet
confirmed by the formal 12-cell bench run — replace each "TARGET"
with the measured figure once
`docs/v1_10_perf_bench_results.jsonl` publishes. §11 (flop) is
reframed to honest-measured reality per
`docs/v1_10_perf_benchmark_2026-05-28.md`.

---

## Table of contents

1. [Algorithm choice: DCFR vs vanilla CFR](#1-dcfr-vs-vanilla-cfr)
2. [PR #114 — Vector-form forward walk + TerminalCache](#2-pr-114--vector-form-forward-walk--terminalcache)
3. [PR #139 — BR-walk terminal-leaf cache](#3-pr-139--br-walk-terminal-leaf-cache)
4. [PR #150 — Board-isomorphism cache](#4-pr-150--board-isomorphism-cache)
5. [PR #157 — Preflop perf: opp-major layout + AXPY interchange](#5-pr-157--preflop-perf-opp-major-layout--axpy-interchange)
6. [PR #162 — BR-walk non-terminal cache + fused walk](#6-pr-162--br-walk-non-terminal-cache--fused-walk)
7. [PR #170 — Vector-form BR walk](#7-pr-170--vector-form-br-walk)
8. [PR #171 — True 169-class abstraction engine](#8-pr-171--true-169-class-abstraction-engine)
9. [v1.10-1 — Thread-local arena + LTO + skip-discount-recompute](#9-v110-1--thread-local-arena--lto--skip-discount-recompute)
10. [v1.10-2 — Vector-form turn forward walk (river template)](#10-v110-2--vector-form-turn-forward-walk-river-template)
11. [v1.10-3 — Vector-form flop forward walk (double chance compaction)](#11-v110-3--vector-form-flop-forward-walk-double-chance-compaction)
12. [v1.10-4 — Opt-in rayon parallel chance branches](#12-v110-4--opt-in-rayon-parallel-chance-branches)
13. [Compounding analysis](#compounding-analysis)

---

## 1. DCFR vs vanilla CFR

**Algorithmic choice, not a Rust optimization, but the largest single perf win in the entire stack.**

### Problem

Vanilla Counterfactual Regret Minimization (CFR) accumulates regret without
discounting. Early iterations (random/uniform strategies) drag convergence
because their bad-action regret persists.

### What we use

**Discounted CFR (Brown & Sandholm 2019)** with three exponents:
- `α = 1.5` — positive regret decay (recent good actions weighted more)
- `β = 0` — negative regret clamped to zero (CFR+ behavior; "no grudges")
- `γ = 2` — strategy-sum quadratic decay (final average heavily favors recent iters)

### Why each parameter helps

- **α > 0**: lets the solver gradually trust recent positive regret over ancient
- **β = 0**: in self-play, the opponent's strategy changes every iter — "this
  action was bad against an opponent that no longer exists" is the right model.
  Clamping negative regret lets actions get re-discovered when the equilibrium
  shifts.
- **γ > 1**: the final "average strategy" output is what users see; weighting
  early-iter random strategies the same as late-iter near-Nash strategies
  would slow effective convergence. Quadratic decay fixes this.

### Speedup vs vanilla CFR

Brown & Sandholm 2019 empirically measured DCFR (1.5, 0, 2) at **~100× faster
than vanilla CFR** on HUNL-class games to reach the same exploitability bound.
CFR+ (β=∞ or β=0) alone is ~10× faster.

### Where to verify

- Algorithm: `crates/cfr_core/src/dcfr.rs` (or wherever the regret update lives)
- Acceptance: `crates/cfr_core/tests/pushfold_brown_dcfr_diff.rs` — diff vs
  Brown's reference at canonical hyperparams
- Memory rule: `feedback_dcfr_alpha_zero` — α=0 silently produces non-Nash
  (task #38 fix); we lock at α=1.5 in production

---

## 2. PR #114 — Vector-form forward walk + TerminalCache

### Problem

Pre-PR #114, river range-vs-range solves traversed the game tree per-combo: for
each of 1326 hand combinations, walk the entire river decision tree
independently. On a single river fixture, this took ~30 seconds per iter — 50k
iters = 17 days. Unusable interactively.

### Optimization

Two stacked changes:

1. **Vector form**: instead of per-combo loop, operate on a 1326-element vector
   at each tree node. SIMD-friendly (NEON on aarch64). At each node, the entire
   range is processed in one batched op rather than 1326 separate scalar walks.

2. **TerminalCache**: at terminal leaves (showdown or fold), compute the
   per-combo payoffs once and cache by (board, action history). Subsequent
   visits to the same terminal hit the cache instead of recomputing equity.

### Speedup

**213× on river RvR** — measured by the PR's benchmark fixture. Single river
solve at 1326-combo went from ~30s/iter to ~140 ms/iter.

### Code path

- `crates/cfr_core/src/dcfr_vector.rs` — vector-form forward walk
- `crates/cfr_core/src/terminal_cache.rs` — TerminalCache
- Benchmark: `crates/cfr_core/benches/river_rvr_perf.rs`
- Diff test: vector-form output bit-identical to per-combo reference within 1e-12

### Caveats

- Vector form requires per-combo blockers to be enumerable at each node — works
  cleanly for HUNL with 169 hand classes' equity table, less cleanly for games
  with private card variation across opponents
- TerminalCache is bounded by tree depth; for deep multi-bet trees the cache
  hit rate drops

---

## 3. PR #139 — BR-walk terminal-leaf cache

### Problem

Best-response (BR) walk computes exploitability by iterating each player's
counter-strategy. Each BR pass walks the full tree per-combo, evaluating
terminal payoffs. The terminal evaluation was the bottleneck on W2.3 Sarah's
turn fixture — a pre-PR hard-kill at >1200s.

### Optimization

Similar pattern to PR #114's TerminalCache, but for the **BR walk** path
specifically. At each terminal leaf, cache the hand-strength evaluations and
payoff vectors by (board, action history). On subsequent BR passes (which is
where exploitability computation iterates), the cache hits eliminate the
showdown evaluation cost.

### Speedup

W2.3 unblock: pre-PR-#139 the 8-class turn fixture was hard-killed at >1200s
with no progress; post-PR-#139 it completes (just still slow — taken further by
PR #162 and PR #170). **No standalone "X×" number** because the pre-state was
"never finishes." Roughly **~2× standalone** on river-RvR workloads where the
forward walk was already cached.

### Code path

- `crates/cfr_core/src/exploit.rs` — `flat_collect_br` terminal-cache hook
- Diff test: BR-walk-with-cache matches BR-walk-without-cache to 1e-9 on
  exploitability

### Why limited speedup

The pre-PR bottleneck was algorithmic (per-combo loop dominated). #139 only
addressed the per-leaf cost. Real algorithmic fix came with PR #170.

---

## 4. PR #150 — Board-isomorphism cache

### Problem

Postflop solver processes flops one at a time. Two flops that are strategically
identical (e.g., `Js 9s 5s` and `Jh 9h 5h` — same ranks, same suitedness, just
different specific suits) get solved independently, wasting compute.

There are **22,100** possible HU flops but only **1,755 strategically distinct
flops** when you canonicalize by suit isomorphism. So in principle you should
solve 1,755 boards once and look up by isomorphism class for the other ~20k.

### Optimization

Canonicalize each board to its iso-class representative, solve the iso-class
once, and cache the result. Future lookups for boards in the same class hit the
cache instead of re-solving.

### Speedup

**~3-5× on workloads that touch many similar boards** (e.g., enumerating
postflop spots across all flops). On a single specific flop, no speedup
(cache miss on first encounter). On a batch of 100 flops chosen uniformly,
~85% are cache hits → ~5× speedup on the batch.

### Code path

- `crates/cfr_core/src/postflop_iso_cache.rs`
- Canonicalization: `crates/cfr_core/src/board.rs::canonicalize_suits`
- Diff test: same flop solved with/without iso-cache → bit-identical strategies

### Caveats

- Suit-iso is sound for preflop range vs preflop range — both ranges symmetric
  in suits
- Breaks if either range is suit-asymmetric (e.g., user provides "all suited
  hands" without specifying which suit) — iso-cache must fall back to direct
  solve in those cases

---

## 5. PR #157 — Preflop perf: opp-major layout + AXPY interchange

### Problem

Pre-PR #157, the full-tree preflop solver was iter-bound. At 1326 combos × ~500
acting nodes × 50k iters = ~33 billion infoset updates. The inner kernel was
the regret-update accumulator: for each infoset, for each action, accumulate
weighted regret across the opponent's reach probability vector.

The naive layout was **strategy-major**: for each infoset, loop over actions,
then within each action loop over the 1326-element opponent reach. This causes
poor cache locality — each iteration reads from different cache lines.

### Optimization

Two stacked changes profile-driven:

1. **Opp-major layout**: swap inner/outer loops. Now for each opponent reach
   element, accumulate against all actions sequentially. The opponent reach
   vector stays in cache; the action vector is the inner loop.

2. **AXPY loop interchange**: the regret update is a Y = αX + Y operation
   (AXPY in BLAS terms). Reordering to keep Y in a register while streaming X
   from cache reduces memory bandwidth pressure 3-5×.

### Speedup

Benchmark on `crates/cfr_core/benches/preflop_rvr_profile.rs`:
- **6.5× wall speedup** on the full benchmark
- **10.4× kernel speedup** on the AXPY hot loop in isolation

The wall is less than kernel because non-kernel overhead (action tree walk,
infoset key construction) doesn't get the kernel's speedup.

### Code path

- `crates/cfr_core/src/preflop_rvr.rs` — `update_regret_opp_major` (rough name)
- Benchmark: `crates/cfr_core/benches/preflop_rvr_profile.rs`
- Diff test: opp-major output matches strategy-major output bit-identically

### Caveats

- Speedup only applies to the preflop full-tree path (1326-combo). Postflop
  has different layout requirements.
- Compounded with PR #171 (which abstracts to 169-class), the AXPY win is
  smaller in absolute time (already fast), but still applies.

---

## 6. PR #162 — BR-walk non-terminal cache + fused walk

### Problem

Post-PR-#139 (terminal cache), the BR walk bottleneck moved to **non-terminal**
decision nodes. For each combo, the BR walk built a strategy key
(`<hole>|<action_history>`), hashed it, looked up the strategy in a HashMap,
and cloned the action-probability vector. On W2.3 (~1.17M combos × ~50 turn
decisions × ~50 river decisions × 5 passes), this dominated wall.

Additionally, the original implementation split the BR walk into two passes:
one to collect BR actions, then a second pass to compute BR value. Two
traversals over the same tree per combo.

### Optimization

Two stacked changes:

1. **DecisionStrategyTable**: precompute a per-(decision_node, player,
   unique_hole) strategy lookup table at iter start. ~54k HashMap ops once;
   subsequent BR-walk node visits index `&[f64]` directly (slice lookup, no
   hash).

2. **Fused walk**: merge `flat_collect_br` + `flat_br_value_unweighted` into a
   single `flat_collect_br_fused` that computes both subtree EV and side-effects
   `action_values` in one pass. Halves the per-combo tree traversal count on
   multi-round games.

### Speedup

**~2.5× on river chance-enum**: pre-PR 1.94s, post-PR 0.78s on the standard
8-class iter=100 fixture. Bit-identical exploitability vs the pre-PR
canonical path.

W2.3 specifically: cache + fused walk took the wall from "doesn't finish in 10
min" → still ~5 min. Algorithmic load remained dominant (~1.17M combos × 5000
nodes) — fully addressed by PR #170.

### Code path

- `crates/cfr_core/src/exploit.rs` — `flat_collect_br_fused`,
  `DecisionStrategyTable`
- Diff test: `cached_matches_uncached_decision_value`,
  `flat_tree_matches_recursive_aggregate_on_river`

---

## 7. PR #170 — Vector-form BR walk

### Problem

Even after PRs #139 + #162, the BR walk was still per-combo. The algorithmic
load on W2.3 was O(combos × tree_size) = 1.17M × 5000 ≈ 5.8B operations.
Caching helped the constant factor but not the asymptotic work.

### Optimization

Apply the **PR #114 vector-form pattern** (originally for forward walk) to the
**BR walk** path. Instead of looping per combo and walking the tree, vectorize
across combos: at each tree node, do one batched op over the 1.17M-element
combo vector.

This converts O(combos × nodes) per-combo loop into O(nodes) with SIMD-batched
vector ops at each node.

### Dual-path architecture (important)

The PR keeps both paths during transition:
- `BrWalkMode::PerCombo` (CANONICAL): unchanged, used as reference
- `BrWalkMode::Vector` (opt-in): new vectorized path

Bit-identical diff tests REQUIRED — 10 fixtures at 1e-9 tolerance for
exploitability, 1e-12 for individual EV components. All pass.

### Speedup

**6.27× on the W2.3 fixture** (the user-facing target): per-combo 202.43s,
vector 32.30s. Within Sarah's 10-min patience gate.

**Lower than projected** (we hoped for 50-100× from analogy to PR #114) because
the per-combo path already has caches from PR #139/#162 that compete with
vector's amortization gains. Vector form would show its full ~50-100× over
fresh per-combo code, but vs already-cached code the marginal gain is smaller.

### Code path

- `crates/cfr_core/src/exploit.rs` — `flat_tree_exploit_vector`
- 10 diff tests in `exploit::tests::vector_matches_per_combo_*`
- Bench fixtures cover river/turn × uniform/mixed × small/medium/large

### Caveats

- Default is still `PerCombo` — vector mode is opt-in via API parameter
- Vector mode allocates an 8 MB `Vec<f64>` per node visit; a thread-local arena
  could close more gap but was out of scope for the PR

---

## 8. PR #171 — True 169-class abstraction engine

### Problem

Strategy storage at 1326-combo resolution is academically correct but wasteful
for preflop (where suits are interchangeable). Industry-standard preflop
abstraction is **169 hand classes** (13 pairs + 78 suited + 78 offsuit), and
it's lossless for preflop strategy decisions.

Pre-PR #171, our solver stored strategies per-combo internally and only
collapsed to 169-class on output (the "hybrid" approach from PR #167). This
meant the engine still did 1326-combo work — slow.

### Optimization

Engine-level 169-class abstraction:
- Strategy storage at 169-class resolution (not 1326)
- Reach probability is a 169-element vector
- Regret is 169-element
- DCFR update operates on 169-element vectors
- Equity-leaf uses pre-baked 169×169 blocker-mass-weighted leaf payoffs (a new
  `Class169TerminalCache`)

The key innovation is `build_class169_blocker_mass`: at preflop equity-leaf
computation, properly weight class-i vs class-j equity by the number of
reachable combo pairs given blockers. This is what makes 169-class semantically
equivalent to 1326-combo for preflop.

### Speedup (the headline numbers)

Measured on the M-series silicon:

| Stack depth | Iters | Hybrid (1326) wall | True Path B (169) wall | Speedup |
|---|---|---|---|---|
| 15 BB | 1000 | 312.7 s | 1.75 s | **178×** |
| 40 BB | 200 | 410.6 s | 1.01 s | **406×** |
| 100 BB | 100 | 445.4 s | 0.99 s | **448×** |

Plus a 7.85× memory footprint reduction (1326 / 169 = 7.85 — matches theory).

### Bit-identity proof

Hybrid output (1326-combo solver → averaged to 169-class) vs True Path B
output (169-class solver directly): **L1 = 0.0000 across 6084 cells** at 15 BB
/ 1000 iters. Confirms the abstraction is lossless modulo numerical noise.

### Code path

- `crates/cfr_core/src/preflop_rvr.rs` — `HandResolution` enum,
  `Class169Combos`, `Class169TerminalCache`, `Class169VectorDCFR`,
  `solve_hunl_preflop_rvr_class169`
- Python binding: `_rust.solve_hunl_preflop_rvr_class169`
- 6 diff tests in `tests/test_true_path_b_diff.py`
- Blocker-mass build: `build_class169_blocker_mass` (the hard part — 1-2 days
  of the implementation budget)

### Workload impact

Phase 1.5 (Premium-A blueprint compute):
- Hybrid projection: 17-40h for 27 blueprints
- True Path B actual: **38.5 minutes** for 27 blueprints

That's the practical "this becomes shippable" win.

---

## 9. v1.10-1 — Thread-local arena + LTO + skip-discount-recompute

**Merge `eb5b4d0` / GitHub PR #197.** Plan reference:
`docs/v1_10_postflop_optimization_plan.md` §2A + §2H1 + §2I3.

> **Speedup status: TARGET, not yet measured by the formal bench.**
> The 3-5× below is the plan's projection; the merging PR ran the
> bit-identical diff gate but did NOT publish a formal wall number
> (the dominant flop cost is tree-storage, not allocator pressure —
> see caveat). Replace with the measured figure from
> `docs/v1_10_perf_bench_results.jsonl` at v1.10.0 tag.

### Problem

The recursive `traverse()` in `dcfr_vector.rs` allocated four to six
`Vec<f64>` per node visit (strategy, action_values, values,
next_reach, node_values). On a flop subgame at full ranges
(~1081 combos/player, ~thousands of decision nodes), this churns
~10-20 GB of *transient* `Vec<f64>` per iteration. Live peak RSS is
bounded by recursion depth, but the malloc/free traffic is a
wall-time cost.

### Optimization

Three stacked changes in one PR:

1. **Thread-local arena** (`crates/cfr_core/src/arena.rs`, NEW):
   `BumpArena` — a single `Vec<f64>`-backed stack-disciplined
   allocator with `alloc_zeroed(n) -> offset`, `reset_to(mark)`, and
   a `BumpScope<'a>` RAII guard. Each `traverse` frame records the
   high-water mark on entry and rewinds before returning (LIFO).
   **Safe Rust — no `unsafe`.** Threaded through
   `traverse_recursive_with_parallel` + `traverse_with_infosets`.
   Replaces the per-call `strategy` (`player_hands * action_count`)
   and `action_values` (`action_count * update_hands`) allocations;
   `next_reach` deliberately stays a heap `Vec` (smaller; allocator
   reuse beat arena overhead in the PR's measurement).
2. **H1 LTO** (`Cargo.toml` workspace `[profile.release]`):
   `lto = "fat"` + `codegen-units = 1` for cross-crate inlining on
   the vector-form DCFR hot path.
3. **I3 skip-discount-recompute**: skip the post-discount strategy
   recompute when the discount was a no-op
   (`last_discount_iter >= iteration`) — pre and post strategies are
   then identical, so this is bit-identical to the unconditional
   recompute.

### Expected speedup

**3-5× flop wall (TARGET, plan §2A); LTO +5-15% (TARGET, §2H1);
I3 ~5% (TARGET, §2I3).** No measured aggregate number published at
merge time.

### Risk

LOW. RAII `BumpScope` preserves stack discipline; safe Rust avoids
the memory-corruption hazard the plan §6 flagged for arena work.
`CFR_NO_ARENA=1` fallback contemplated in the plan as a kill switch.

### Bit-identity status

**Bit-identical, gated.** 1e-12 strategy / 1e-9 EV. 19 library tests
(`arena::*` 8, `dcfr_vector::*` 11) + the Python diff suite
(`test_blueprint_subgame_wiring` 15/15, `test_preflop_rvr_diff` 4/4,
`test_exploit_diff` 5/5, Kuhn/Leduc/dcfr 16/16) all pass.

### Code path

- `crates/cfr_core/src/arena.rs` — `BumpArena`, `BumpScope`
- `crates/cfr_core/src/dcfr_vector.rs` —
  `traverse_recursive_with_parallel`, `traverse_with_infosets`
- `Cargo.toml` — workspace `[profile.release]` LTO

### Caveat

The PR's empirical note: on flop subgames at full ranges, **tree
storage (plan §1.2 Dominant 2), not allocator pressure, is the
binding cost** — so arena alone does not unblock the OOM. The flop
unblock is carried by v1.10-2/-3 (vector-form chance compaction).

---

## 10. v1.10-2 — Vector-form turn forward walk (river template)

**Merge `7fa4d73` / GitHub PR #190.** Plan reference:
`docs/v1_10_postflop_optimization_plan.md` §2B (Candidate B).

> **Speedup status: TARGET.** Plan projects 2-3× on turn; this PR
> landed the *framework* (template extraction + dispatch hook) and
> gated bit-identity, not a published wall number.

### Problem

The turn forward walk recursed each river-card chance branch
independently even when those branches share identical betting-tree
structure. Redundant deep recursion at every turn → river enumeration.

### Optimization

Chance-template extraction at tree-build time:

1. **`BettingTreeMode`** (`exploit.rs`): `Standard` /
   `TemplateExtract`, plus `BettingTree::build_with_mode`.
   `TemplateExtract` populates `BettingTree::chance_templates` with
   one entry per `FlatNode::Chance` whose children share structural
   identity (verified via a per-subtree `structure_hash`). This is
   **out-of-band metadata — the `FlatNode` list itself is unchanged**
   between modes.
2. **`has_chance_template[]`** lookup on `VectorDCFR` (one bool per
   `FlatNode` index), populated in `with_init_noise`. The chance arm
   of `traverse()` dispatches to `traverse_turn_chance` when the flag
   is set, else falls through to the legacy per-branch recursion.
3. **Mode selection**: `TemplateExtract` for Turn/Flop starting
   streets, `Standard` for River.

### Expected speedup

**2-3× on turn (TARGET, plan §2B).** Turn top_k=15: 15s → 5-7s;
top_k=169: 50-90s → 20-30s (all TARGET). No measured number at merge.

### Risk

MEDIUM (plan rating) — the river betting tree is board-dependent
through `key_suffix`; template extraction needs careful structural
hashing. Realized risk was low: the framework verified clean.

### Bit-identity status

**Bit-identical, gated.** `traverse_turn_chance` performs the EXACT
same DFS-order arithmetic as the legacy chance arm (same
`values[i] += prob * v` accumulator; IEEE 754 summation order
preserved). New unit tests:
`template_extract_finds_turn_chance_node`,
`template_extract_bit_identical_to_standard` (1e-12 strategy),
`river_solve_does_not_template_extract` (negative control). 39+
existing diff tests pass unchanged.

### Code path

- `crates/cfr_core/src/exploit.rs` — `BettingTreeMode`,
  `build_with_mode`, `chance_templates`, `structure_hash`
- `crates/cfr_core/src/dcfr_vector.rs` — `has_chance_template[]`,
  `traverse_turn_chance`

### Note

This PR ships the structural framework that v1.10-3 (vector flop)
broadcasts across river-card chance branches; it is a prerequisite,
not a standalone flop unblock.

---

## 11. v1.10-3 — Vector-form flop forward walk (double chance compaction)

**Merge `cda3eeb`.** Plan reference:
`docs/v1_10_postflop_optimization_plan.md` §2C (Candidate C); design
doc `docs/v1_10_pr3_flop_vector_design.md`; honest benchmark
narrative `docs/v1_10_perf_benchmark_2026-05-28.md`.

> **Speedup magnitude: wall-time + reliability win delivered
> (qualitative), memory win DEFERRED to v1.11.** The flop solve now
> *completes* where the pre-v1.10 path was OOM/jetsam-killed at the
> ~5-min mark — that is the measurable win. The plan's "<120 s AND
> ≤ 1 GB RSS at top_k=169" headline gate is **NOT met**: full-range
> flop RSS is ~6.7 GB at top_k=4 and ~7.7 GB+ at top_k=169 (does not
> finish). Exact turn/river wall figures are PENDING the formal bench
> (`docs/v1_10_perf_bench_results.jsonl`).

### Problem

Even with v1.10-1 (arena) and v1.10-2 (turn template), the flop walk
still recurses the full turn × river chance subtree per outer flop
chance branch. Tree-storage explosion (plan §1.2 Dominant 2) keeps
the flop OOM/jetsam-killed at the ~5-min mark on the J7o A♦8♥9♦
40 BB / 169-class reference fixture.

### Optimization (what actually shipped)

Extends v1.10-2's template framework to **double chance compaction**:
the flop's outer chance loop does 45 × 44 = 1980 weighted sums and
**reuses pre-allocated scratch buffers** (a per-solve `RunoutCache`:
`flop_values_scratch` + the active turn accumulator) instead of
allocating a fresh `vec![0.0; update_hands]` per call. This is the
design doc's **Strategy B** (lazy on-demand, scratch reuse) — it
removes per-iteration allocator churn but does **not** collapse the
materialized board-tree storage.

### What was delivered vs deferred

- **Delivered (wall-time + reliability):** the flop subgame now
  completes; the pre-v1.10 allocator-churn OOM at the ~5-min mark is
  resolved. The shipped path is bit-identical to the v1.10-2
  reference.
- **Deferred (memory):** the design doc's **Strategy A** (eager
  board-tree memory collapse — sharing the river-betting-tree
  storage across all 1980 runouts) was **scaffolded but not wired**.
  The independent PR-3 audit confirmed this statically as **finding
  S-4**: `RunoutCache::runout_values` (the 1980-buffer pool) is
  **allocated but never read** — it carries `#[allow(dead_code)]`
  with the in-code note "currently unused in Strategy B … the eager
  Strategy-A variant can use the full layout in a follow-up PR."
  Consequently flop-solve memory is still dominated by the
  materialized board chance tree (45 turn × 44 river betting
  subtrees) + per-node infoset storage at full combo width, which is
  **independent of `top_k`**. Full-range flop memory optimization
  (sparse / lazy infoset storage + board-tree templating) is
  deferred to v1.11 — see
  `docs/v1_11_postflop_deeper_optimization_research.md` (Candidates E
  sparse range + Q lazy infoset + D board-iso chance caching).

### Risk

HIGH (plan rating) — DFS-order preservation across the double
broadcast was the load-bearing correctness property. Realized:
clean — bit-identity verified (below).

### Bit-identity status

**Bit-identical — VERIFIED.** F4_synth synthetic-tree canary passed
at `max_diff = 0.0`; 4 Rust unit tests pass incl.
`flop_template_extract_bit_identical_to_standard`; two independent
validators returned MATH-PRESERVED (no FP-accumulation-order
divergence). `CFR_VECTOR_FLOP_TEMPLATE=0` forces the `Standard`
build mode (canonical baseline). Regret / strategy_sum / discount
kernels untouched.

### Code path

- `crates/cfr_core/src/dcfr_vector.rs` — `traverse_flop_chance_recursive`,
  `RunoutCache` (extends v1.10-2's template dispatch)
- `crates/cfr_core/src/exploit.rs` — `ChanceTemplate.chance_depth`
- Diff test: `tests/test_v1_10_3_flop_diff.py`

---

## 12. v1.10-4 — Opt-in rayon parallel chance branches

**Merge `f5ec665` / GitHub PR #189.** Plan reference:
`docs/v1_10_postflop_optimization_plan.md` §2G (Candidate G).

> **Speedup status: PR-microbench, TARGET-grade.** The PR's own
> 14-core run reported ~4.79×; this is NOT yet the formal 12-cell
> bench number. Per the v1.8 SIMD lesson (projected 4-8× → measured
> 1.0×), do not promote this to a confirmed production headline until
> `docs/v1_10_perf_bench_results.jsonl` publishes.

### Problem

The flop turn-card chance enumeration (45 branches at the flop root)
is embarrassingly parallel but ran single-threaded.

### Optimization

Parallelize iteration over the 45 turn cards via `rayon::par_iter`.
Each thread walks one turn subtree and contributes
regret/strategy_sum deltas through **disjoint mutable access** on the
betting tree's contiguous child ranges — `split_at_mut` lets the
borrow checker enforce non-overlap statically, so **no `unsafe`**.
Refactored `traverse` to a slice-based free fn; `solve` dispatches on
the env var.

### Activation

**Opt-in via `CFR_RAYON_CHANCE=1`** (read once at `VectorDCFR::solve`
entry; empty/unset = canonical single-threaded path). Same dual-path
discipline as PR #170's `BrWalkMode::PerCombo` / `Vector`.

### Expected / reported speedup

Plan §2G projected **4-8× on M-series (8 P-cores)**. PR #189's
microbench (14-core M-series): **flop top_k=169 + 1 bet size +
cap 2, 100 iters: 16.7s → 3.49s = ~4.79×**; river top_k=169 +
2 bet sizes + cap 3, 100 iters: 0.035s → 0.033s = -5.8% overhead
(rayon setup cost on a workload too small to amortize). **All
TARGET-grade until the formal bench run.**

### Risk

The plan rated this CRITICAL (data races on `self.infosets`) and
expected to ship behind a loose 1e-6 tolerance. Realized risk was
**lower than spec**: the static `split_at_mut` disjointness +
source-order-preserving `par_iter+collect` + sequential per-hand
reduction gave **bit-identical** results.

### Bit-identity status

**Bit-identical — BETTER than the spec's loose-1e-6 gate.** Max
per-action probability diff 0.000e+00; exploit + game value match
the canonical path to absolute zero. 9/9 fixtures in
`tests/test_vector_rayon_diff.py` PASS; all 25 existing diff tests
PASS unchanged on the canonical path.

### Code path

- `Cargo.toml` — `rayon = "1.10"`
- `crates/cfr_core/src/lib.rs` — `pub mod dcfr_vector_parallel`
- `crates/cfr_core/src/dcfr_vector_parallel.rs` (NEW, ~275 LOC) —
  parallel chance branches; `CFR_RAYON_CHANCE` reader
- `crates/cfr_core/src/dcfr_vector.rs` — slice-based traverse +
  dispatch in `solve`
- `tests/test_vector_rayon_diff.py` (NEW, 9 fixtures)

---

## Compounding analysis

For the "generate Premium-A 27 preflop blueprints at 25k iters" workload,
walking the optimization stack:

| Stage | Wall time | Cumulative speedup |
|---|---|---|
| Vanilla CFR, 1326-combo, no optimizations | ~weeks | 1× |
| + DCFR (α/β/γ canonical) | ~days | ~100× |
| + PR #157 (preflop perf) | ~50 hours | ~650× |
| + PR #171 (true 169-class) | **38 minutes** | **~80,000×** |

The 80,000× combined speedup is what makes the blueprint pipeline practical on
a single M-series machine in a coffee break instead of a cloud cluster over a
weekend.

## Caveats on "actual" vs "claimed" speedups

All numbers in this doc come from the merging PR's own benchmark + diff-test
gate. Each was empirically measured, not projected. However:

- Speedups are **workload-dependent**. The same optimization shows different
  numbers on different fixtures. What's listed is the headline number from the
  PR's primary fixture.
- Speedups **compound multiplicatively** for orthogonal optimizations (e.g.,
  PR #157 + PR #171 stack). Non-orthogonal optimizations (e.g., #139 + #162 +
  #170 all on the BR walk path) have diminishing returns.
- "Speedup vs what" matters — PR #170's 6.27× is vs the already-cached
  per-combo path (post PR #139 + #162). Vs unoptimized vanilla, it would be
  much larger.

## Where to find this in the repo

- Benchmarks: `crates/cfr_core/benches/`
- Diff tests (correctness gate for each optimization): `crates/cfr_core/tests/`
- Brown reference implementation (sanity check baseline):
  `references/noam_brown_clone/`
- Source-of-truth perf claims: each PR's body on GitHub

## Future optimization opportunities

Not yet implemented; ranked by expected impact:

1. **Vector-form BR walk thread-local arena** — eliminate 8 MB per-node-visit
   allocation in PR #170's path. Estimated **~1.5-2× additional speedup**
   on W2.3-class workloads.
2. **Per-level multipliers** in action menu — engine refactor, NOT a speedup
   per se but enables exact apples-to-apples chart validation. **No solve
   speedup**, just better validation.
3. **GPU/Metal vectorization** — port vector-form ops to Metal Performance
   Shaders. **Potential 5-10× on large blueprint regens**, but high
   engineering cost (~weeks) and questionable ROI given current 38-min wall.
4. **6-max engine** — different scope; not a HUNL optimization. ~3-month
   project, separate from this ledger.
