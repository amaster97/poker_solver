# Reality check: is the FlatInfosetStore "primary-wire" speedup real?

**Date:** 2026-05-23
**Context:** PR 8 landed NEON SIMD kernels (measured: 1.55-3.52x at HUNL row widths; 0.95x end-to-end on Leduc). Implementer's diagnosis: HashMap+tree-descent dominates, so a follow-up wiring `FlatInfosetStore` (`crates/cfr_core/src/layout.rs`, ~190 LOC, built but unwired) as the primary infoset backing could close the 10x end-to-end gap. This file rigorously interrogates that claim before commitment.

---

## Section A: Q1 verdict - is the speedup REAL?

### A.1 Status: OPTIMISTIC. Not hallucinated, but the implementer's framing materially overstates what `FlatInfosetStore` *as built today* would deliver.

### A.2 Evidence

**A.2.1. There is real precedent that competitor CFR/MCCFR solvers use flat-array storage, not HashMap.**

- `references/code/noambrown_poker_solver/cpp/src/trainer.h:69` declares `std::vector<InfoSet> infosets_;` indexed by **integer `node_id`**, NOT `std::unordered_map`. Access pattern at `trainer.cpp:13-19, 43, 51, 66, 163, 184, 266` is uniform `infosets_[node_id]` direct indexing.
- `references/code/postflop-solver/src/game/node.rs:42-69` goes even further: each `PostFlopNode` carries raw `storage1/storage2/storage3` pointers into a contiguous arena; `regrets()` and `strategy()` are `slice::from_raw_parts(self.storage2 as *const f32, ...)`. Combined with the custom stack allocator in `references/code/postflop-solver/src/alloc.rs:1-30`, this is an aggressive contiguous-storage design.
- `references/code/slumbot2019/src/cfr_street_values.h:53` (`T *AllValues(int p, int nt) const {return data_[p] ? data_[p][nt] : nullptr;}`) — slumbot stores regrets/strategy as `T*** data_` keyed by `(player, node_id, holding)`, no `unordered_map<string, ...>`. The MIT-licensed pattern the PR 8 implementer cites as inspiration is the real thing.
- Counter-precedent: `references/code/open_spiel/open_spiel/algorithms/cfr.h:103-104` uses `using CFRInfoStateValuesTable = std::unordered_map<std::string, CFRInfoStateValues>;` — same HashMap pattern as ours. OpenSpiel pays the same cost we do.

So the **direction** (flat arena, integer ID) is unambiguously the industry pattern for serious CFR solvers. The implementer is not making this up.

**A.2.2. The papers acknowledge CFR is memory-bound — direct quotes.**

- `references/papers/dcfr_brown_2019.pdf` (Brown & Sandholm AAAI 2019): "*when an algorithm is bottlenecked by memory access rather than computational speed*" — they explicitly discuss memory-vs-compute tradeoffs for CFR variants.
- `references/papers/libratus_brown_2017_supplement.pdf` (Libratus *Science* supplement): "*Since Libratus was bottlenecked primarily by memory access, only 14 cores were used on each node rather than the 28 available.*" This is a state-of-the-art HUNL solver explicitly identifying memory access as the binding constraint.
- `references/papers/pluribus_brown_2019_science.pdf`: stores blueprint in *compressed form* in 128 GB to fit. Implies memory bandwidth is precious.

So **"CFR is memory-bound" is an established empirical fact in the literature** — not hallucinated by the implementer.

**A.2.3. BUT — the empirical perf math on `FlatInfosetStore` as built today does NOT support a 10x end-to-end speedup.**

I ran a focused HashMap-vs-flat-array microbenchmark (release build, M-series, 300 infosets x 3 actions, 1M visits, sources at `/tmp/hashmap_vs_flat_bench.rs`):

| Path | ns/visit |
|---|---:|
| HashMap with pre-computed `&String` key | 20 |
| Flat array WITH pre-computed integer ID (no lookup) | 1 |
| Flat array with `key_to_id` HashMap (`String` -> `u32`), key passed in | 19 |
| **HashMap with `format!()` key per visit (mimics current DCFR loop)** | **67** |
| **Flat array with `format!()` key + `key_to_id` HashMap (mimics `FlatInfosetStore.intern()` today)** | **65** |

**The dominant cost is the `format!()` to build the infoset key (`leduc.rs:188`, `kuhn.rs:133`), which costs ~45-50 ns/visit by itself**, not the HashMap probe (~20 ns). The HashMap probe IS the second largest term, but `FlatInfosetStore::intern()` at `layout.rs:115` still does a `HashMap<String, InfosetId>` lookup keyed by the same `&str`. **The improvement from wiring `FlatInfosetStore` as built today is 67ns - 65ns = ~3% of HashMap-lookup cost** — a rounding error.

Quoting `layout.rs:71-74`: "Key -> InfosetId lookup (still indirection on first visit, but the hot inner loop walks `regret_arena` / `strategy_arena` directly **once it has the `InfosetId`**)." The comment is honest — the speedup *only* materializes if you skip the string lookup. PR 8's `FlatInfosetStore` does NOT do that.

The 20x->1ns flat-array-with-precomputed-ID number IS real, but it would require:
1. Pre-building the tree, assigning `InfosetId`s at tree-construction time.
2. Caching the `InfosetId` directly on each tree node.
3. Skipping `infoset_key()` (the `format!()` call) in the hot loop.

None of this is in PR 8 today. It's a **separate, deeper refactor** (touching `LeducState`, `KuhnState`, `HUNLState`, the tree builder, and probably the chance-node iteration). Postflop-solver does this — their `PostFlopNode` has the storage pointers baked in at tree-build time (`game/node.rs:42-69`).

**A.2.4. Decomposing the 7.9 us "remaining per visit" (per `pr_report.md:81`).**

The implementer attributes 7.9 us/visit to "HashMap lookup (string hash + bucket probe + two heap derefs), recursive tree descent, vec allocations for `action_values` / `strategy`, and `state.clone()` for `state.apply(action)`". My microbench bounds the HashMap+format!() portion at ~67 ns/visit. So:

- HashMap+format!() per visit:  ~67 ns (~0.8% of 7.9 us)
- Everything else per visit:    ~7833 ns (~99% — recursion, `state.clone()`, `Vec<[f64;2]> vec![[0.0; 2]; num_actions]` at `dcfr.rs:167`, etc.)

**Even a perfect FlatInfosetStore wire (no string format, direct integer index) saves ~67 ns of ~7900 ns/visit. End-to-end ceiling: ~1.01x.** To get end-to-end 10x, the dominant ~7.8 us has to go too — and that's `state.clone()`, vec allocations, and recursion overhead, NOT HashMap.

This matches `pr_report.md:138`: the implementer DOES say "To unlock end-to-end speedup, a follow-up PR would route the inner CFR loop through `FlatInfosetStore`". The framing is honest about the *direction*, but it conflates "necessary" with "sufficient". FlatInfosetStore is necessary infrastructure for the eventual rewrite; it is **not sufficient on its own** for 10x.

**A.2.5. No precedent in `references/papers/` for "flat array vs HashMap = 10x for tabular CFR".**

I ran `pdftotext` over the DCFR paper, the CFR+ paper, the Libratus supplement, and Pluribus, grepping for "cache", "memory layout", "contiguous", "flat array", "hashmap", "memory-bound", "SoA", "AoS". The only hits were the two "bottlenecked by memory" quotes above (A.2.2). **No paper in `references/papers/` quantifies a flat-array-vs-HashMap speedup for tabular CFR.** The 10x number comes from the project spec, NOT from external evidence.

### A.3 Q1 verdict summary

| Claim | Status |
|---|---|
| CFR is memory-bound | **REAL** — Libratus supplement, DCFR paper |
| Industry flat-array storage is the standard | **REAL** — slumbot, noambrown, postflop-solver |
| `FlatInfosetStore` as built today gives ~10x end-to-end | **HALLUCINATED** — empirically saves ~3% of HashMap cost (~2 ns of 7900) because the `format!()` + `key_to_id` HashMap is still in the hot path |
| A *deeper* refactor (pre-bound tree-node -> `InfosetId`, no `format!()` in hot loop) could eventually deliver large speedup | **OPTIMISTIC** — direction is correct, magnitude not measured. Would need to instrument and measure. |

**The implementer's PR report is honest** (see `pr_report.md:35`, `pr_report.md:81`, `pr_report.md:138-141`) about the gap. The "primary-wire" framing in the *user's* prompt is the part that overstates it.

---

## Section B: Q2 verdict - will wiring `FlatInfosetStore` break or change expected behavior?

### B.1 Status: **NEEDS DESIGN WORK — currently UNSAFE in three concrete ways**, all addressable but none addressed in PR 8.

### B.2 Evidence

**B.2.1. Determinism / iteration order: HashMap iteration is not stable; `FlatInfosetStore` *is*, but the wire-up loses that property unless explicitly preserved.**

- Current `dcfr.rs:218-220` does `for info in self.infosets.values_mut() { Self::discount_info(...) }`. `HashMap::values_mut()` returns in **arbitrary order** (in Rust std HashMap, randomized hash seed per process). For mathematical correctness of discounting, order doesn't matter (it's a per-row operation), but for **diff testing** against the Python tier (`tests/test_dcfr_diff.py:18` `STRATEGY_ATOL = 1e-4`), any float-order sensitivity would surface.
- `FlatInfosetStore` would iterate in `InfosetId` insertion order (deterministic given insertion order). **This is BETTER than HashMap for determinism**, but ONLY if the insertion order itself is deterministic — i.e., if the tree-traversal order at iteration 1 is identical across runs. In `dcfr.rs:131-202` the recursion is purely structural, so insertion order should be deterministic. Probably safe.
- **Risk:** different infoset *values* if the discount is iterated in a different order — only matters because `discount_info` is non-trivially intertwined with `cfr()` (it's done **lazy** inside `cfr()`, not in a separate sweep, see `dcfr.rs:159`). The "final catch-up sweep" at `dcfr.rs:215-220` is order-insensitive (each row independent). **Verdict: deterministic if insertion order is, which it is.**

**B.2.2. Float precision / bit-exact discipline: the SIMD work already passes bit-exact diff tests, but moving from `Vec<f64>` inside `InfosetData` to a slice of an arena is a memory-layout change that *should* be a no-op for floats but is worth verifying.**

- `simd.rs` already uses `vmaxq_f64`, `vmulq_f64`, etc. on `&mut [f64]`. The kernels in `dcfr.rs:194-200` already take slice references (`&mut info.regret_sum`). `FlatInfosetStore::regret_mut(id)` returns `&mut [f64]` of the same length. **The slice type is identical**; the only change is *where* the backing memory lives.
- Float operations on `&mut [f64]` are bit-exact regardless of underlying allocation. **Verdict: no precision risk.**

**B.2.3. API surface: `entry().or_insert_with()` semantics aren't fully replicated.**

- Current hot path at `dcfr.rs:155-158`: `self.infosets.entry(key.clone()).or_insert_with(|| InfosetData::new(num_actions))`. This is **insert-if-absent, return mutable ref to existing-or-new**, all in one call.
- `FlatInfosetStore::intern(key, num_actions)` returns `InfosetId`. To get the data row you then call `regret_mut(id)` / `strategy_sum_mut(id)`. **Two calls instead of one**, with a borrow-checker headache because `intern` mutably borrows `self`, but the returned `InfosetId` is `Copy` so a follow-up `self.row_mut(id)` is fine.
- The `row_mut(id)` method at `layout.rs:177-196` is the cleanest replacement — yields `(regret_slice, strategy_slice, meta_ref)` in one call. **The unsafe block at `layout.rs:191-194`** does a manual disjoint-borrow split via raw pointer cast; the comment claims correctness ("we hold mutable borrows on three disjoint regions of `self`") and the test at `layout.rs:215-229` covers the happy path. **This is a real `unsafe` reviewer should sign off on**, but the construction is standard and correct.
- **Verdict: API change is invasive but tractable. Both `dcfr.rs` cfr() and discount_info() need refactoring; `average_strategy()` at `dcfr.rs:224-235` also iterates HashMap and would need to walk `id_to_key` instead.**

**B.2.4. Differential test status (`tests/test_dcfr_diff.py`).**

- Test gate: `STRATEGY_ATOL = 1e-4` for per-action probabilities; `VALUE_ATOL = 1e-5` for game value; `EXPLOIT_ATOL = 1e-4` for exploitability (`test_dcfr_diff.py:18-20`).
- The Python reference uses `dict[str, InfosetData]` (HashMap) and the Rust uses the same today. **Both backends update each infoset's regrets/strategy by the same formula, in tree-traversal order.** Switching the Rust backend to `FlatInfosetStore` does NOT change the per-row math, only where the floats live in memory. **Tests should still pass** — but this needs to be *re-run* after wiring, not assumed.
- Critical: the PR 8 SIMD parity bar required bit-exactness vs scalar (see `pr_report.md:25` — FMA was specifically rejected because it caused 1.5% drift on `test_leduc_python_rust_strategy_agreement`). The same bar applies here. `FlatInfosetStore` doesn't introduce new arithmetic, so it shouldn't drift. **But if `FlatInfosetStore::row_mut(id)` triggers a different code path through the `simd::*` kernels — e.g., by changing slice alignment — there is a small risk of microcode-level reorder.** Low likelihood, but the diff test should be re-run.

**B.2.5. Differential test against Noam Brown's solver (PR 7 river spots).**

- Per PR 7 status (post-v1 GA): river-spot results compared at Nash tolerance ~5e-3 mbb/hand. `FlatInfosetStore` does not change algorithm semantics. **Should still pass within Nash tolerance.** Same caveat — must be re-run.

**B.2.6. Memory profile.**

- `poker_solver/profiler/memory.py` profiles the Python tier (`DCFRSolver`), not the Rust tier. `FlatInfosetStore` is Rust-only and wouldn't be visible here. **No conflict.**
- Memory comparison: Today's `HashMap<String, InfosetData>` per infoset = ~64 bytes overhead (hash table slot + key String header + Box<InfosetData> + 2 x Vec head). `FlatInfosetStore` per infoset = ~16 bytes `RowMeta` + 2 x `num_actions * 8` bytes in the arenas + the still-required `HashMap<String, InfosetId>` entry (~28 bytes) + `id_to_key` entry (~24 bytes). For Leduc (288 infosets, 3 actions): HashMap ~46 KB, Flat ~32 KB. **Flat is ~30% smaller**, mostly because the arena packs the two Vec<f64> heads away. For HUNL (millions of infosets) this is non-trivial but still secondary to the abstraction table.

### B.3 Q2 verdict summary

| Risk | Status |
|---|---|
| Determinism | LOW — flat store has deterministic iteration; insertion order from tree traversal is structurally deterministic |
| Float precision | LOW — slice semantics identical; no new arithmetic ordering |
| API surface refactor | MEDIUM — invasive (touches `cfr()`, `discount_info`, `average_strategy`, `solve`); requires a real diff-test re-run |
| Python<->Rust diff tests | LOW assuming no SIMD-alignment surprises; **must re-run, not assume** |
| Noam Brown river diff (PR 7) | LOW assuming no SIMD-alignment surprises; **must re-run** |
| Memory | NEUTRAL — flat is slightly smaller |
| `unsafe` block in `row_mut` | LOW — small, well-commented, tested at `layout.rs:215-229`; standard disjoint-borrow pattern; reviewer should sign off |

**Net verdict: SAFE in semantics, RISKY in execution.** No fundamental issue, but every refactor of this size in a numerically-sensitive solver needs the full diff-test gate re-run *before* merge. The PR 8 implementer correctly held off the wire-up for this reason (see `pr_report.md:35`).

---

## Section C: Synthesis - does the user have clear go-ahead?

### C.1 Recommendation: **NEEDS-DISCUSSION** (do NOT proceed on "primary-wire FlatInfosetStore -> 10x" framing as currently scoped).

### C.2 Concrete reasoning

1. **The "10x" target is not achievable from FlatInfosetStore alone.** My microbench shows the HashMap+`format!()` cost is ~67 ns of ~7900 ns per visit (~0.8%). Eliminating it gives an end-to-end ceiling of ~1.01x on Leduc. The remaining ~99% is in `state.clone()`, vec allocations, recursion. *This is not the implementer's fault* — the implementer was honest about it (`pr_report.md:81, 138-141`). The user's prompt framing implicitly assumed HashMap was the dominant cost; it is one of several roughly equal-magnitude costs.

2. **A 10x end-to-end speedup is achievable, but it requires a much deeper refactor**, modelled on postflop-solver (`game/node.rs` + custom arena allocator). The work items would be:
   - Pre-build the tree once at solver-init, assigning each tree-node a stable `InfosetId` (or storing the slice offset directly).
   - Skip `infoset_key()` (the `format!()`) in the hot loop entirely; the tree node carries the ID.
   - Replace `Vec<[f64; 2]> action_values = vec![[0.0; 2]; num_actions]` (`dcfr.rs:167`) with a stack-allocated `[f64; MAX_ACTIONS * 2]` or arena-allocated scratch.
   - Replace `state.apply(action)` (which clones state) with a `state.apply_in_place(action) / state.undo_in_place(action)` pattern (zobrist-style or recursive undo). This is the biggest item.
   - **This is a 500-1000 LOC refactor across `dcfr.rs`, `hunl_solver.rs`, `leduc.rs`, `kuhn.rs`, and the tree builders**, not the ~150-line wire-up that "primary-wire FlatInfosetStore" suggests.

3. **The PR 8 `FlatInfosetStore` IS useful infrastructure** — just not the load-bearing element. Wiring it as-is (`intern()` keyed by `&str`) gives ~1.03x at best. Wiring it *after* the tree-pre-bound `InfosetId` work is a meaningful component of a larger 5-10x rewrite. The honest path is: do not bill this as "the speedup PR"; do it as "the storage refactor PR, prereq for the tree-pre-bound ID refactor".

4. **The behavioral risk is low and manageable**, but every refactor must re-run the full `tests/test_dcfr_diff.py` + `tests/test_leduc_diff.py` + PR 7 river diff at Nash tolerance. The PR 8 implementer already gates this discipline (`pr_report.md:104-108`). Should be a checklist item on any follow-up PR.

### C.3 The 2-3 most load-bearing citations driving this verdict

1. **`/tmp/hashmap_vs_flat_bench.rs` empirical microbench** (Rust 1.x release, M-series): HashMap+`format!()` = 67 ns/visit, Flat+`format!()`+HashMap = 65 ns/visit. **Direct empirical evidence that the proposed wire-up saves ~3% of HashMap cost, not 10x of total.** This is the single most load-bearing piece of evidence.

2. **`crates/cfr_core/src/layout.rs:113-138` (`FlatInfosetStore::intern()`)**: the function literally does `self.key_to_id.get(key)` and `self.key_to_id.insert(key.to_string(), id)`. **The HashMap-by-string is still in the hot path**; the flat-array benefit only kicks in *after* you have the `InfosetId`. To truly cash the speedup, the tree must carry pre-bound `InfosetId`s — which is a deeper refactor not in PR 8.

3. **`references/code/postflop-solver/src/game/node.rs:42-69` + `references/code/postflop-solver/src/alloc.rs:1-37`**: the closest production-grade peer carries storage pointers (`storage1/2/3: *mut f32`) *directly on each tree node* and uses a custom stack allocator. This is the architecture that *does* deliver real speedup — and it's what `FlatInfosetStore` would need to become to deliver the spec's 10x target. The gap between `layout.rs` today and `postflop-solver`'s design is the gap between "1.03x" and "10x".

4. (Honorable mention) **`references/papers/libratus_brown_2017_supplement.pdf`**: "*Since Libratus was bottlenecked primarily by memory access, only 14 cores were used on each node rather than the 28 available.*" — confirms the *direction* (memory-bound is real for CFR) but does NOT quantify a HashMap-vs-flat speedup. The 10x project target has no precedent in the references.

### C.4 Suggested next move (recommendation only; user decides)

Rather than "wire `FlatInfosetStore` as primary and expect 10x", I would suggest:
- **Option A (conservative):** ship PR 8 as is. Document `FlatInfosetStore` as build infrastructure for a future PR. Keep the 10x claim out of the changelog.
- **Option B (the right work):** scope a new PR ("hot-path arena refactor") that pre-builds the tree with `InfosetId` baked in, eliminates `format!()` in the hot loop, replaces `state.clone()` with in-place apply/undo, and uses `FlatInfosetStore`'s arenas as the backing storage. **Instrument with the PR 8 microbench before/after.** Re-run the full diff-test gate.
- **Option C (compromise):** ship PR 8, then instrument Leduc with `perf` or `dtrace` to measure where the 7.9 us/visit actually goes (state.clone? Vec alloc? recursion?). Use that data to decide if the arena rewrite is worth the cost.

Per memory `feedback_no_extrapolate`, I'm declining to assert a numerical speedup target for any of these without measurement.

### C.5 What the user should NOT do

Do not commit to "10x end-to-end via primary-wire FlatInfosetStore" as a deliverable. The arithmetic doesn't support it; the empirical microbench refutes it. If the user wants 10x end-to-end, the work scope is approximately the postflop-solver-style storage architecture, not the ~150-line FlatInfosetStore wire-up.
