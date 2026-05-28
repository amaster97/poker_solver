# v1.10 Postflop Subgame Optimization — Research + Implementation Plan

**Date:** 2026-05-28
**Status:** Research phase complete. Implementation queued as task #70.
**Source agent:** `a9f20bc07ae60bc67` (Plan architect, read-only research).

## Executive Summary (5-bullet headline)

1. **Root cause of flop OOM is the recursive `traverse()` in `crates/cfr_core/src/dcfr_vector.rs:591-835` allocating four to six `Vec<f64>` per node visit** (sized `update_hands` or `player_hands × action_count`). On flop with full ranges (~1081 combos/player) and ~1980 chance-tree leaves, this allocates ~10 GB of transient `Vec<f64>`s **per iteration** even though peak live memory at any instant is much smaller. The 2.3 GB RSS is the high-water mark; the 5 min wall is allocator pressure + chance branching.

2. **Top three optimizations, prioritized**: (a) **thread-local arena pool for the four `Vec<f64>` buffers** in `traverse()` — eliminates 90%+ of malloc traffic, ~3-5× speedup, near-zero quality risk; (b) **decision-tree-walk vector-form for flop chance subtree** — keep the betting-tree walk recursive, but vectorize the chance-card enumeration with a single pre-allocated `(N_runouts × hand_count)` buffer reused across iterations (matches PR #114's TerminalCache pattern, extends to non-terminal); (c) **rayon multi-threading across turn-card chance branches at flop root** — embarrassingly parallel; need a regret/strategy_sum write-conflict resolution.

3. **Expected v1.10 perf at full top_k=169** (no truncation): **flop solve in 60-120 s** (vs current OOM-killed at 5 min); turn in 5-10 s; river in <1 s (already shipped). Top_k=4 (smallest) should be <5 s flop. This is 30-50× headline speedup over current state.

4. **Engineering cost: ~3-4 weeks** wall (~15-20 working days). Arena alone is ~3 days; flop vector form ~5 days; rayon ~5 days; full bench suite + diff-test gauntlet ~5 days; release prep ~2 days.

5. **Highest-risk item: rayon-induced regret update ordering breaking the bit-identical diff test gate.** Mitigation: ship rayon behind an opt-in flag (`CFR_RAYON_CHANCE=1`) with **separate looser-tolerance diff tests** (`1e-6` exploitability vs current `1e-9`) for the parallel path, while keeping the single-threaded path as the bit-identical canonical reference. Same dual-path pattern as PR #170 (`BrWalkMode::PerCombo` / `Vector`).

---

## 1. Profile + Cost Analysis

### 1.1 Code path for flop solve

User-level call chain:
1. **Python:** `solve_postflop_from_blueprint` (`poker_solver/blueprint_subgame.py:551`) — builds the prior ranges from blueprint, calls...
2. **Python:** `solve_range_vs_range_nash` (`poker_solver/range_aggregator.py:904`) — packages config + per-player combo lists + per-combo weights, calls...
3. **PyO3:** `_rust.solve_range_vs_range_rust` (`crates/cfr_core/src/lib.rs:476-591`) — releases GIL, calls...
4. **Rust:** `solve_range_vs_range_postflop_with_hands` (`crates/cfr_core/src/dcfr_vector.rs:1259-1351`) — builds `BettingTree`, `EvalContext`, `VectorDCFR`, then...
5. **Rust:** `VectorDCFR::solve` (`crates/cfr_core/src/dcfr_vector.rs:854-900`) — drives iterations, each iter calls `traverse` twice (one per update_player).
6. **Rust:** `VectorDCFR::traverse` (`crates/cfr_core/src/dcfr_vector.rs:590-835`) — the hot path. Recursive postflop tree walk.

### 1.2 Three cost dominants

**Dominant 1: Per-node `Vec<f64>` allocations in `traverse()` (allocator pressure).**

For each `FlatNode::Decision` visit:
- Line 661: `let mut strategy = vec![0.0_f64; player_hands * action_count]`. For top_k=169 at flop with avg 5 actions: 1081 × 5 × 8 = ~43 KB.
- Lines 689-690 (opponent branch): `values = vec![0.0; update_hands]` + `next_reach = vec![0.0; player_hands]` = ~17 KB. **Allocated per opponent-decision visit.**
- Lines 741-742 (own branch): `action_values = vec![0.0; action_count * update_hands]` = ~43 KB; `next_reach = vec![0.0; player_hands]` = ~8.6 KB. **Allocated per own-decision visit.**
- Line 766: `node_values = vec![0.0; update_hands]` = ~8.6 KB.

For each `FlatNode::Chance` visit (line 635): `let mut values = vec![0.0; update_hands]` = ~8.6 KB.

Per iteration:
- ~2 walks (one per update_player) × ~200k node visits × ~5 `Vec<f64>` per visit × ~10 KB each = **~20 GB of transient Vec<f64> allocation per iteration**.

The allocator can recycle inside a single recursion, so RSS peak is bounded by recursion depth × max-vec-size. But the malloc/free churn is the wall-time killer.

**Dominant 2: Tree size explosion on flop (chance branching).**

- Flop chance node has ~45 outcomes (line 437-444 in exploit.rs).
- Each turn-card subtree builds its own flop-line betting subtree + 44 river subtrees.
- Decision_node_count for a typical flop subgame at raise_cap=3 with 2 bet sizes: **expect ~5000-30000 decision nodes**.

`VectorInfosetData` is allocated **per decision node** (line 462-490 in dcfr_vector.rs): `2 × hand_count × action_count × 8 bytes`. At top_k=169 with 1081 hands × 5 actions × 16 bytes = **86 KB per decision**. For 10k decisions = **860 MB just for storage**, plus the `BettingTree::nodes` Vec, plus `TerminalCache`. **This is the 2.3 GB.**

**Dominant 3: Terminal-leaf O(N²) double-loop.**

`terminal_value_vector_cached` at `dcfr_vector.rs:1085-1137` does an O(N²) blocker-check over (hp, ho) pairs. For 1081 × 1081 = **1.17M pairs per Showdown leaf**. ~2.3 B comparisons per iteration at full top_k.

---

## 2. Optimization Candidates — Survey + Estimate

### Candidate A — Thread-local arena pool for `traverse()` Vec<f64>s

**What it changes:** Replace per-call `vec![0.0; N]` allocations at `dcfr_vector.rs:635, 661, 689-690, 741-742, 766` with a thread-local `BufferArena` that hands out reusable `&mut [f64]` slices in stack-discipline.

**Reference:** `references/code/postflop-solver/src/alloc.rs` ships exactly this pattern (AGPL, no code copy). `crates/cfr_core/src/layout.rs:80-127` already has an arena for scalar DCFR — same idea.

**Expected speedup:** 3-5× wall. **No memory peak reduction** but **massive reduction in allocator metadata**.

**Engineering effort:** 2-3 days. **Risk: LOW** — RAII `BumpScope` guard preserves stack discipline.

**Bit-identical diff-test gate:** All 10 PR #170 fixtures + 8 kill-switch fixtures, 1e-12 EV tolerance.

### Candidate B — Vector-form turn forward walk

**What it changes:** Apply chance-tree compaction to turn → river enumeration. Precompute river-board-conditional payoff tables once at solve-start; turn loop does 45 weighted sums instead of 45 deep recursions.

**Expected speedup:** 2-3× on turn. Turn top_k=15: 15s → 5-7s; top_k=169: 50-90s → 20-30s.

**Engineering effort:** 4-5 days. **Risk: MEDIUM** — river-betting-tree currently board-dependent through `key_suffix`; need careful template extraction.

**Diff-test:** F3.1, F3.4-F3.6, F6.6.

### Candidate C — Vector-form flop forward walk

**What it changes:** Extend (B) to double chance compaction (turn × river). Build a `(turn_card, river_card)` → cached_subtree_value table. Flop's outer chance loop does 45 × 44 = 1980 weighted sums against this cache.

**Expected speedup:** **10-20× on flop.** Currently OOM-killed at 5 min → **~60-90s** at top_k=169.

**Memory impact:** **Dramatic reduction.** Collapses duplicated river-betting-tree storage to single template + per-runout multiplier. Expected RSS: ~500 MB.

**Engineering effort:** 7-10 days. **Risk: HIGH** — novel engineering, DFS-order preservation hard.

**Diff-test:** F4.1, F4.2, F4.3 + new small-tree synthetic fixture proving template broadcast.

### Candidate D — Board-isomorphism caching at chance nodes

**What it changes:** Cache suit-iso-equivalent subtrees within chance-node enumeration.

**Existing work:** `crates/cfr_core/src/postflop_iso_cache.rs` does this at board-level (PR #150). No in-engine chance-node iso-cache yet.

**Expected speedup:** 2-4× on flop chance subtree.

**Engineering effort:** 6-8 days. **Risk: MEDIUM-HIGH** — suit-iso only sound when ranges are suit-symmetric; need runtime check + fallback.

**Diff-test:** Symmetric (AA-vs-KK on Qs7h2d) vs asymmetric (AsKs-vs-QcJc on Qs7h2d) fixtures.

### Candidate E — Sparse range representation

**What it changes:** When blueprint reach is concentrated, allocate `regret/strategy_sum` only for active combos. Skip zero-reach rows in kernels.

**Expected speedup:** 2-10× on sparse workloads (Premium-A blueprint flows are sparse).

**Engineering effort:** 5-7 days. **Risk: MEDIUM** — indexing bugs easy.

**Diff-test:** Sparse vs dense bit-identical on fixture with many zero-reach hands.

### Candidate F — Incremental computation

**Expected speedup:** Small (~10-20%). **Recommendation: defer to v1.11.**

### Candidate G — Rayon multi-threading over flop turn-card chance branches

**What it changes:** Parallelize iteration over 45 turn cards using `rayon::par_iter`. Each thread walks one turn subtree, contributes regret/strategy_sum deltas to a shared `VectorDCFR`.

**Expected speedup:** **4-8× on M-series (8 P-cores).** Stacks with arena → 12-40× combined.

**Memory impact:** ~Nx working memory per thread (~8× working set). Opt-in mode.

**Engineering effort:** 6-8 days. **Risk: HIGH** — write-conflicts on `self.infosets`. Use per-thread delta buffers + merge step. **Bit-identical NOT preserved** due to sum reordering.

**Mitigation:** Dual-path. `CFR_RAYON_CHANCE=1` opt-in flag, default single-threaded canonical path. Same pattern as PR #170's `BrWalkMode`.

**Diff-test:** New `test_vector_rayon_diff.py` with **loose tolerance** (1e-6 exploitability).

### Candidate H — Compiler optimizations

- **H1 LTO**: 5-15% speedup, 1 hour effort, NO risk. **Ship immediately.**
- **H2 PGO**: 10-20% speedup, 1 day, LOW risk. Defer to v1.11.
- **H3 BLAS-backed kernels**: 1.5-3× kernel speedup, 4-5 days, MEDIUM risk. Defer to v1.11.

### Candidate I — Other findings

- **I1 f64 → f32**: ~2× kernel + memory. Breaks every diff test. **Defer to v1.11.**
- **I2** `placeholder.clone_with_hole_cards`: one-time cost, skip.
- **I3 Skip discount-strategy recompute** when no-op: 5% speedup, 2 hours. **Bundle into Candidate A's PR.**

---

## 3. Implementation Order

```
Week 1: A (arena) + H1 (LTO) + I3 (skip-discount-recompute)
        └─ PR #v1.10-1 "perf: thread-local arena + LTO for flop subgame"
        └─ Expected: 3-5× wall reduction

Week 2: B (vector-form turn)
        └─ PR #v1.10-2 "perf: vector-form turn forward walk"
        └─ Expected: 2-3× turn wall reduction

Week 3: C (vector-form flop)
        └─ PR #v1.10-3 "perf: vector-form flop chance-tree compaction"
        └─ Expected: 10-20× flop wall reduction

Week 4: G (rayon opt-in) + final bench + ledger update
        └─ PR #v1.10-4 "perf: opt-in rayon multi-threading for flop"
        └─ Expected: 4-8× additional on flop when opted-in

Deferred to v1.11: D (board-iso), E (sparse), H2 (PGO), H3 (BLAS), I1 (f32).
```

**Per-stage success criteria:**

| PR | Success criteria |
|---|---|
| #v1.10-1 (arena+LTO) | All diff tests bit-identical (1e-12); flop top_k=4 iter=5 in <60s (was OOM); RSS ≤ 1.5 GB. |
| #v1.10-2 (vector turn) | Turn diff tests bit-identical; turn top_k=15 iter=100 in <10s; top_k=169 iter=100 in <60s. |
| #v1.10-3 (vector flop) | Flop diff tests bit-identical; flop top_k=4 iter=100 in <30s; top_k=169 iter=100 in <120s; RSS ≤ 1 GB. |
| #v1.10-4 (rayon) | Opt-in path passes loose-tolerance (1e-6); canonical bit-identical to v1.10-3; flop top_k=169 iter=100 in <30s with `CFR_RAYON_CHANCE=1` on 8-core. |

---

## 4. Bit-Identical Diff-Test Strategy

### 4.1 Reference path

Canonical reference at each layer = the immediately prior PR's tip. Each PR's diff test compares new implementation against the immediately prior reference at bit-identical tolerance.

### 4.2 Tolerances

| Quantity | Tolerance | Justification |
|---|---|---|
| Per-history strategy entry | 1e-12 | float roundoff (PR #170 precedent) |
| Exploitability | 1e-9 | sum-of-many cf-utilities |
| Game value | 1e-12 | direct readout |
| Per-combo BR action (argmax) | exact | no float tolerance allowed |
| Rayon path (G) — exploitability | 1e-6 | thread-order non-determinism |

### 4.3 Fixtures (canonical 8 + v1.10 additions)

From `docs/w2_3_vector_br_walk_test_fixtures.md`:
- F1.1 Kuhn, F1.3 Leduc, F2.4 8-class river dry, F3.1 W2.3 reference (Qs7h2d5c), F4.1 standard flop (Qh7c2d), F4.2 wet flop (JsTs9h), F4.3 static flop (Kc7s2d), F5.2 pure-strategy edge, F5.3 heavily mixed edge.

**New v1.10 additions:**
- F4.4 J7o A♦8♥9♦ 40-BB (user's empirical fixture).
- F4.5 sparse range (top_k=4 with hero_classes=["AA","KK","QQ","JJ"]).
- F4.6 full range (top_k=169) — headline number.

### 4.4 CI integration

- **Per-commit gate (~40 min)**: F1.1 + F1.3 + F2.4 + F3.1 + F4.1 + F5.2 + F5.3.
- **Per-PR full gate (~3 hr)**: above + F4.2 + F4.3 + F4.4-F4.6.
- **Pre-merge soak (~6 hr)**: 36-fixture matrix + 3 v1.10 additions. Run by independent agent.

### 4.5 Rayon special case

Opt-in path: `tests/test_vector_rayon_diff.py` with `CFR_RAYON_CHANCE=1`, 1e-6 EV tolerance, no NaN / no divergence.

---

## 5. Final Benchmark Suite

### 5.1 Canonical perf table

Single fixture: **J7o A♦8♥9♦, 40 BB, SB-opens-3x / BB-calls**. `iterations=200`. Matrix: top_k ∈ {4, 15, 50, 169} × street ∈ {flop, turn, river}.

**Pre-v1.10 baseline:**

| top_k | Street | Wall (s) | Peak RSS (MB) |
|---|---|---|---|
| 4 | Flop | OOM @ 5min | 2310 |
| 4 | Turn | 0.7 | 240 |
| 4 | River | 0.05 | 50 |
| 15 | Flop | OOM @ 5min | >2300 |
| 15 | Turn | 15.0 | 540 |
| 15 | River | 0.5 | 80 |
| 50 | Flop | OOM @ 5min | >5000 |
| 50 | Turn | ~150 | ~1200 |
| 50 | River | 5.0 | 280 |
| 169 | Flop | est. OOM | est. >8000 |
| 169 | Turn | ~600 | ~4500 |
| 169 | River | 67 | 1100 |

**v1.10 target (post all 4 PRs):**

| top_k | Street | Wall target (s) | RSS target (MB) | Speedup vs current |
|---|---|---|---|---|
| 4 | Flop | <5 | <200 | OOM → completes |
| 4 | Turn | <0.3 | <100 | 2.3× |
| 4 | River | <0.05 | <50 | unchanged |
| 15 | Flop | <15 | <400 | OOM → completes |
| 15 | Turn | <5 | <250 | 3× |
| 15 | River | <0.5 | <80 | unchanged |
| 50 | Flop | <30 | <500 | OOM → completes |
| 50 | Turn | <30 | <500 | 5× |
| 50 | River | <2 | <200 | 2.5× |
| **169** | **Flop** | **<120** | **<1000** | **OOM → completes** |
| **169** | **Turn** | **<60** | **<800** | **10×** |
| **169** | **River** | **<30** | **<600** | **2.2×** |

The **`top_k=169 Flop <120s`** is the v1.10 user-facing headline.

### 5.2 Bench harness

Add `crates/cfr_core/benches/flop_subgame_perf.rs` + Python driver `scripts/run_v1_10_perf_bench.py`. Output: `docs/v1_10_perf_benchmark_2026-MM-DD.md` with the 12-cell table.

---

## 6. Risk Register

| Risk | Severity | Mitigation |
|---|---|---|
| Arena (A) corrupts memory on edge-case recursion | HIGH | RAII `BumpScope` guard with debug-assert; `CFR_NO_ARENA=1` fallback flag |
| Vector flop (C) DFS-order drift breaks diff tests | HIGH | F4.1/F4.2/F4.3 at 1e-9 + synthetic small-tree fixture |
| Rayon (G) data races on `self.infosets` | CRITICAL | Per-thread `Vec<HashMap<usize, RegretDelta>>` accumulator + merge; defensive `assert!(self.in_parallel_section)` |
| Suit-iso (D) wrong on asymmetric ranges | HIGH | Runtime `is_range_suit_symmetric` check + fallback path |
| f32 migration (I1) breaks every diff test | HIGH | Deferred to v1.11 |
| PyO3 ABI break | LOW | Arena is internal; rayon adds env var only |
| LTO inflates build time | LOW | ~5 min CI; accept |
| Wall regression on small fixtures | LOW | Kuhn smoke per PR; gate arena behind hand-count heuristic if >20% regression |
| Persona 17/0/0/0 regression | HIGH | Full persona suite gate per PR |
| OOM not fixed post-C | MEDIUM | Iter-budget exit (return partial result); diagnostic profile run |

---

## 7. Done Criteria — "v1.10 ships"

### Hard gates

1. Flop top_k=169 completes in <120s (target <60s) on J7o A♦8♥9♦ 40-BB at 200 iter.
2. All bit-identical diff tests pass at 1e-9 EV (canonical non-rayon path).
3. Persona table stays 17/0/0/0.
4. `docs/v1_10_perf_benchmark_2026-MM-DD.md` published with 12-cell table.
5. `docs/rust_optimization_ledger.md` updated with PRs #v1.10-1 through #v1.10-4.
6. Memory peak at top_k=169 flop ≤ 1 GB RSS.
7. CHANGELOG.md v1.10.0 entry.

### Soft gates

8. Independent-agent soak run confirms numbers within ±10%.
9. UI smoke: blueprint→flop solve from GUI without OOM.
10. CHANGELOG mentions rayon opt-in flag with example.

---

## 8. File-Level Implementation Pointers

### Arena (A)
- **New:** `crates/cfr_core/src/arena.rs` — `BumpArena`, `BumpScope`, `BumpSlice<'a>`.
- **Modified:** `crates/cfr_core/src/dcfr_vector.rs:590-835` — replace `vec![0.0; N]` at lines 635, 661, 689-690, 741-742, 766 with `arena.alloc_zeroed(N)`.
- **Modified:** `crates/cfr_core/src/dcfr_vector.rs:854-900` — instantiate arena at solve start; pass through `traverse`.

### Vector turn (B)
- **Modified:** `crates/cfr_core/src/exploit.rs:369-471` — add `template_mode` flag for shared river-subtree.
- **New:** `crates/cfr_core/src/dcfr_vector.rs:traverse_turn_chance` — broadcasts the template.

### Vector flop (C)
- Same files as B; extends template to (turn, river) double-broadcast.
- **New:** `crates/cfr_core/src/dcfr_vector.rs:traverse_flop_chance`.

### Rayon (G)
- **Modified:** `crates/cfr_core/Cargo.toml` — add `rayon = "1.10"`.
- **Modified:** `crates/cfr_core/src/dcfr_vector.rs:854-900` — branch on env var.
- **New:** `crates/cfr_core/src/dcfr_vector_parallel.rs` — parallel traverse with per-thread regret delta buffers.

### Benches
- **New:** `crates/cfr_core/benches/flop_subgame_perf.rs`.
- **New:** `scripts/run_v1_10_perf_bench.py`.

### Diff tests
- **New:** `tests/test_arena_diff.py` (v1.10-1 gate).
- **New:** `tests/test_vector_turn_template_diff.py` (v1.10-2 gate).
- **New:** `tests/test_vector_flop_template_diff.py` (v1.10-3 gate).
- **New:** `tests/test_vector_rayon_diff.py` (v1.10-4 loose gate).

---

*Plan source: agent `a9f20bc07ae60bc67`, 2026-05-28.*
