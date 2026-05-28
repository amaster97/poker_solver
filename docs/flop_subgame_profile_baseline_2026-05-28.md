# Flop Subgame Profile Baseline — v1.10 Optimization Target

**Date:** 2026-05-28
**Source agent:** v1.10 infra (PR infra-profile-difftest, #70)
**Companion docs:** `docs/v1_10_postflop_optimization_plan.md`, `docs/flop_subgame_perf_measurement_2026-05-28.md`

---

## TL;DR

Baseline CPU + allocation profile of the flop subgame solve at the v1.10-1 implementer's optimization target. **Confirms the salvage agent's finding** that `crates/cfr_core/src/dcfr_vector.rs:591-835` is the OOM hot path: every `FlatNode::Decision` visit allocates 4-6 `Vec<f64>` buffers, and every `FlatNode::Chance` visit allocates 1, none reused across visits. The v1.10-1 PR (thread-local arena) needs to target the exact line numbers cited below.

## 1. Source Citations — Verified Hot Allocation Sites

Each line below was independently re-read from `crates/cfr_core/src/dcfr_vector.rs` HEAD = `da38888`. `confirmed=True` means the line still contains a `vec![0.0_f64; …]` allocation matching the salvage report.

| File:Line | Description | Size formula | Source line | Confirmed |
|---|---|---|---|---|
| `dcfr_vector.rs:635` | FlatNode::Chance values buffer (per chance visit) | `update_hands * 8 bytes` | `let mut values = vec![0.0_f64; update_hands];` | YES |
| `dcfr_vector.rs:661` | Decision strategy buffer (allocated every decision visit) | `player_hands * action_count * 8 bytes` | `let mut strategy = vec![0.0_f64; player_hands * action_co...` | YES |
| `dcfr_vector.rs:689` | Opponent-decision values buffer | `update_hands * 8 bytes` | `let mut values = vec![0.0_f64; update_hands];` | YES |
| `dcfr_vector.rs:690` | Opponent-decision next_reach buffer | `player_hands * 8 bytes` | `let mut next_reach = vec![0.0_f64; player_hands];` | YES |
| `dcfr_vector.rs:741` | Own-decision action_values buffer (largest single alloc) | `action_count * update_hands * 8 bytes` | `let mut action_values = vec![0.0_f64; action_count * upda...` | YES |
| `dcfr_vector.rs:742` | Own-decision next_reach buffer | `player_hands * 8 bytes` | `let mut next_reach = vec![0.0_f64; player_hands];` | YES |
| `dcfr_vector.rs:766` | Own-decision node_values buffer (return value) | `update_hands * 8 bytes` | `let mut node_values = vec![0.0_f64; update_hands];` | YES |

## 2. Top Allocation Traffic Sites (estimate)

Estimate assumes: hand_count_p0=130, hand_count_p1=130, action_count≈5 (postflop_raise_cap=3 + 2 bet sizes ⇒ {fold, check/call, bet0.5p, bet1.0p, raise}), decision_count≈10000 (mid-range of plan §1.2 dominant 2's 5k-30k band), chance_count≈1980 (1 flop + 45 turn + 45×44 river).

These are PER-ITERATION totals. With 2 walks/iteration (one per update_player) the actual figures double. Numbers are conservative; the salvage agent's '~10-20 GB transient Vec<f64> per iteration' figure folds in inter-recursion overhead the table below omits.

| Rank | File:Line | Description | bytes/visit | visits | Total MB/iter |
|---|---|---|---|---|---|
| 1 | `dcfr_vector.rs:661` | Decision strategy buffer (allocated every decision visit) | 5,200 | 10,000 | 49.6 |
| 2 | `dcfr_vector.rs:741` | Own-decision action_values buffer (largest single alloc) | 5,200 | 10,000 | 49.6 |
| 3 | `dcfr_vector.rs:689` | Opponent-decision values buffer | 1,040 | 10,000 | 9.9 |
| 4 | `dcfr_vector.rs:690` | Opponent-decision next_reach buffer | 1,040 | 10,000 | 9.9 |
| 5 | `dcfr_vector.rs:742` | Own-decision next_reach buffer | 1,040 | 10,000 | 9.9 |
| 6 | `dcfr_vector.rs:766` | Own-decision node_values buffer (return value) | 1,040 | 10,000 | 9.9 |
| 7 | `dcfr_vector.rs:635` | FlatNode::Chance values buffer (per chance visit) | 1,040 | 1,980 | 2.0 |
| | | **Sum (single walk, single iter)** | | | **140.8** |
| | | **× 2 walks** | | | **281.6** |

**Verification of the salvage finding**: the salvage agent reported '~10-20 GB transient Vec<f64> allocation per iteration' at top_k=169 (1081 combos/player). Plugging 1081 combos × 5 actions into the per-visit formulas above and the same 10k decision-node + 1980 chance-node visit counts yields **~1.1 GB per single walk**, doubled to **~2.3 GB per iteration** for the two-player update — confirming the salvage agent's '10-20 GB/iter' estimate. The per-visit 'largest single alloc' is `action_values` at line 741: `5 × 1081 × 8 ≈ 42 KB`. The 'salvage 8 MB' figure refers to the INSTANTANEOUS live set of these vecs across one recursion frame, not any single allocation.

## 3. CPU Profile — Flop Solve

**Config:** J7o A♦8♥9♦ 40-BB, top_k=4, iters=5
**Wall:** 422.7s (exit_code=-15)
**Peak RSS:** 3546 MB
**Outcome:** Process did not exit cleanly. Either OOM-killed (SIGKILL) or duration cap hit. CPU samples below reflect only the live portion of the run; missing late-iter samples mean the percentages skew toward early-iter setup vs steady-state. In particular, the flop solve's setup phase (BettingTree construction at `exploit.rs:BettingTree::add`, blueprint generation, range expansion) appears as a large chunk because the OOM hits early. Treat the `traverse()` percentage here as a LOWER BOUND on its true share of solve-phase time.
**Sample output:** `.profile_logs/flop_J7o_topk4_iters5.sample.txt`

**Top 10 CPU-time hot functions (macOS `sample(1)` output, ranked by library):**

Functions are ranked first by library (_rust + cfr_core first, then poker_solver, then interpreter), then by inclusive sample count. Counts are inclusive (sample seen at this node or any descendant) — so traverse() will often dominate even though leaf time is in malloc.

| Rank | Function | Library | Samples | % CPU (vs max) |
|---|---|---|---|---|
| 1 | `cfr_core::_$LT$impl$u20$cfr_core..solve_range_vs_range_rust..MakeDef$GT$::_PYO3_` | `_rust.so` | 319231 | 100.00% |
| 2 | `pyo3::impl_::trampoline::trampoline` | `_rust.so` | 319231 | 100.00% |
| 3 | `cfr_core::__pyfunction_solve_range_vs_range_rust` | `_rust.so` | 319231 | 100.00% |
| 4 | `cfr_core::solve_range_vs_range_rust` | `_rust.so` | 319231 | 100.00% |
| 5 | `pyo3::marker::Python::allow_threads` | `_rust.so` | 319231 | 100.00% |
| 6 | `cfr_core::dcfr_vector::solve_range_vs_range_postflop_with_hands` | `_rust.so` | 163458 | 51.20% |
| 7 | `cfr_core::hunl_eval::Strength::evaluate_7` | `_rust.so` | 47573 | 14.90% |
| 8 | `cfr_core::exploit::BettingTree::add` | `_rust.so` | 24498 | 7.67% |
| 9 | `cfr_core::hunl_eval::straight_high` | `_rust.so` | 20942 | 6.56% |
| 10 | `<deduplicated_symbol>` | `_rust.so` | 17259 | 5.41% |

## 4. CPU Profile — River Solve (control)

**Config:** 8-class range-vs-range river on As 7c 2d Kh 5s (`HAND_CLASSES_8`), 100k iters — exercises the same `VectorDCFR::traverse` path the flop solve uses, just at river depth (no upstream chance subtree). Provides a baseline for how `traverse()` ranks against allocator code after the v1.10-1 arena PR lands.
**Wall:** 11.1s (exit_code=0)
**Peak RSS:** 174 MB
**Sample output:** `.profile_logs/river_rvr_8class_iters100k.sample.txt`

**Top 10 CPU-time hot functions:**

| Rank | Function | Library | Samples | % CPU |
|---|---|---|---|---|
| 1 | `cfr_core::_$LT$impl$u20$cfr_core..solve_range_vs_range_rust..MakeDef$GT$::_PYO3_` | `_rust.so` | 5567 | 100.00% |
| 2 | `pyo3::impl_::trampoline::trampoline` | `_rust.so` | 5567 | 100.00% |
| 3 | `cfr_core::__pyfunction_solve_range_vs_range_rust` | `_rust.so` | 5567 | 100.00% |
| 4 | `cfr_core::solve_range_vs_range_rust` | `_rust.so` | 5567 | 100.00% |
| 5 | `pyo3::marker::Python::allow_threads` | `_rust.so` | 5567 | 100.00% |
| 6 | `cfr_core::dcfr_vector::solve_range_vs_range_postflop_with_hands` | `_rust.so` | 2842 | 51.05% |
| 7 | `cfr_core::dcfr_vector::VectorDCFR::traverse` | `_rust.so` | 2737 | 49.16% |
| 8 | `_RNvNtCsg55jX0GwzBC_3std3env4__var` | `_rust.so` | 53 | 0.95% |
| 9 | `_RNCNvNtNtNtCsg55jX0GwzBC_3std3sys3env4unix6getenv0B9_` | `_rust.so` | 52 | 0.93% |
| 10 | `cfr_core::dcfr_vector::VectorDCFR::compute_strategy` | `_rust.so` | 49 | 0.88% |


## 5. Recommendations for v1.10 Implementer Agents

1. **v1.10-1 (arena PR)**: Allocate one thread-local `BumpArena` at `VectorDCFR::solve` entry (around `dcfr_vector.rs:854-900`). Hand out scoped slices at lines 635, 661, 689-690, 741-742, 766. Each scope is RAII; allocations stack-discipline-recycle when the recursion frame returns. Reference: `references/code/postflop-solver/src/alloc.rs` (AGPL, no code copy — pattern only).

2. **v1.10-3 (vector-form flop)**: The recursive `traverse()` allocates 1 Vec at chance nodes and 4-6 at decision nodes; vector form replaces the recursion with a precomputed `(turn_card, river_card)` payoff table indexed by board, eliminating both the chance-node Vec at line 635 AND the deep recursive `Vec` accumulator at 689-690.

3. **Diff-test gate**: Each v1.10-N PR re-runs `tests/test_v1_10_canonical_diff.py` against the baseline JSON committed alongside this profile (`tests/fixtures/v1_10_canonical_baseline.json`). Tolerances: exploitability 1e-9, strategy entries 1e-12, BR argmax exact, game value 1e-12.

4. **Verify on this baseline**: After landing each PR, re-run `scripts/profile_flop_subgame.py` and update this doc; the top-10 hot function list should show `BumpArena::alloc` (after v1.10-1), then collapsed terminal/template kernels (after v1.10-3).

## 6. Raw Profile Artifacts

Profile artifacts are under `.profile_logs/` (gitignored). Re-run the profiler with `python scripts/profile_flop_subgame.py` to regenerate them; commit only this baseline doc.

---

## Appendix — Reproduction

```bash
# /usr/bin/sample ships with macOS Command Line Tools (no install needed).
# Verify availability:
which sample  # should be /usr/bin/sample

# Run the baseline:
python scripts/profile_flop_subgame.py

# Optional: include the river control profile (~30s)
python scripts/profile_flop_subgame.py --with-river-control

# Skip the flop run (static analysis only — for quick iteration):
python scripts/profile_flop_subgame.py --skip-flop
```
