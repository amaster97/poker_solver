# v1.3.0 — Research-Backed Alternatives for Range-vs-Range Exploitability

**Status:** Research summary, not a copied algorithm. Read-only review of `references/code/{postflop-solver, noambrown_poker_solver, open_spiel, slumbot2019}` and `references/papers/`, 2026-05-23. Goal: surface fallback paths before Option A (`pr-15`) or Option B (`pr-16`) reports perf numbers, in case either misses the gate (`v1_3_range_vs_range.md:124-131`).

---

## Section 1 — How each competitor handles exploitability / BR

### postflop-solver (Wataru Inariba, AGPL — READ ONLY)

**Algorithm.** `compute_exploitability` in `references/code/postflop-solver/src/utility.rs:277-291` is *vector-form* BR. A single recursive walk over the action tree carries one `cfreach: &[f32]` slice per node (one entry per opponent private hand) and returns one `result: &mut [MaybeUninit<f32>]` slice (one entry per BR-player private hand). The two recursors are `compute_cfvalue_recursive` (on-policy) at `utility.rs:358-562` and `compute_best_cfv_recursive` (BR) at `utility.rs:565-720`. Exploitability = `(mes_ev[0] + mes_ev[1]) * 0.5`.

**Data structure.** Strategy is **dense per-node** — `f32` array of length `num_actions * num_private_hands` stored on the tree node itself, not a `HashMap<String, Vec<f64>>`. BR at a BR-player node is a single elementwise max over action-CFV rows: `max_slices_uninit(result, &cfv_actions)` at line 672 (definition `sliceop.rs:101-114`). At an opponent node, `cfreach * sigma(I,a)` is an elementwise row op (`mul_slice` over `chunks_exact_mut(row_size)`, `utility.rs:699-702`).

**Parallelism / SIMD.** Children evaluated in parallel via Rayon: `for_each_child` at `utility.rs:13-29` dispatches `into_par_iter().for_each(op)` when `node.enable_parallelization()` is true. Hot-path slice math has a WASM-SIMD specialization at `utility.rs:79` and `:143`; the non-WASM path relies on compiler auto-vectorization (README:53 claims developer-reviewed assembly). A `custom-alloc` feature uses a stack-bump allocator (`alloc.rs`) for traversal scratch.

**Range-vs-range.** Native. `Range` (`range.rs:42`) is per-hand-combo weights; every solve is range-vs-range — single-combo is just a one-hot weight vector.

**Performance claims.** README:54 — "surpasses paid solvers such as PioSOLVER and GTO+." No published numbers; the WASM build (`wasm-postflop`) solves a 100 BB SRP flop at standard sizing in seconds.

**Insights adaptable without copying AGPL.**
1. Dense per-node `f32` strategy slab vs our `HashMap<String, Vec<f64>>` (orders of magnitude faster on the inner walk).
2. Vector-form BR with elementwise max — one tree walk, not infoset-iterate-then-re-walk like our `solver.py:_best_response_value` fixed-point loop (`solver.py:271-288`).
3. Stack-bump scratch allocator for hot recursion.
4. Tree-internal Rayon over children — no per-iteration thread-pool stage needed.

### noambrown_poker_solver (Noam Brown, MIT — CAN COPY)

**Algorithm.** Python reference + optimized C++; both vector-form, structurally identical. C++ `Trainer::best_response` at `cpp/src/trainer.cpp:242-305` recurses once per node carrying `reach_opp`. At target-player nodes: build `action_values[a * target_hands + h]` (lines 286-290) and take per-hand max (lines 293-301). At opponent nodes: split `reach_opp` by `frame.strategy[h * action_count + a]` (lines 273-281), sum child CFVs across actions (lines 277-282).

**Data structure.** `ScratchFrame` per recursion depth (`trainer.h`), pre-allocated once in trainer setup. Each frame holds `strategy`, `values`, `action_values`, `next_reach` sized to max action × hand product. **Zero allocations during traversal** — same effect as postflop-solver's `custom-alloc` without nightly Rust.

**Vectorized river evaluator.** The gold nugget. `cpp/src/vector_eval.cpp` (described in `_NOTES.md:22-23, :30`) sorts opponent hands by strength once, builds prefix sums of opponent weights, stores per-hero-hand `[range_start, range_end)` indices plus three blocker lists (`blocked_less / equal / greater`). Each `showdown_values` is then O(|hero| × |blockers|) with prefix-sum lookups — no O(|hero|×|villain|) scan. Python mirror at `vector_eval.py:83-124`.

**Parallelism.** None — single-threaded by design (`_NOTES.md:46`). MIT license; the per-depth-scratch pattern is the explicit recommendation in `_NOTES.md:43-49` as the basis for our Rust port.

**Insights — directly portable.**
1. Per-depth scratch frames. Cleaner than `custom-alloc` because each frame is sized at startup per depth-max-fanout.
2. Sorted-prefix-sum river showdown evaluator — O(N²) → O(N + blockers).
3. `f32` regret with `f64` traversal accumulation. Matches postflop-solver.
4. JSON subgame config format for tooling interop (`_NOTES.md:48`).

### open_spiel (DeepMind, Apache 2.0)

**Algorithm.** `BestResponsePolicy` at `best_response.py:87-232`. Strictly tabular state-based — *not* vector-form. Builds an `infosets` dict via DFS (`decision_nodes` lines 124-133), memoizes `value`/`q_value` per state, picks the reach-weighted-max action (lines 203-211).

**Performance characteristics.** This is the slow-but-correct path for testing. Comment at lines 19-20 directs production use to `TabularBestResponse` (C++ at `algorithms/best_response.h:55-99`), which pre-computes states once and uses `absl::flat_hash_map` for lookups. Non-toy games always wrap C++ via `CPPBestResponsePolicy` (lines 235-376).

**Cut threshold.** Header line 43: "A partially computed best-response can be computed when using a `prob_cut_threshold >= 0`" — branches below threshold are skipped. Exploitability lower bound; standard cheat for tractability.

**Insights.**
1. Pre-build infoset → states map once outside the BR fixed-point loop. Our `_collect_infosets` does this (`solver.py:267-269`) but re-runs per-action child evaluation inside the loop; OpenSpiel's `@_memoize_method` (line 36) makes each state's value compute once total.
2. Probability-cut threshold for approximate BR — cheap convergence check.
3. `flat_hash_map` over `unordered_map` — 2-3× faster on these lookups. Rust analog: `ahash::AHashMap` / `hashbrown`.

### slumbot2019 (Eric Jackson, MIT)

**Algorithm.** Two BR variants, both vector-form on the CFR-P engine. Exact RGBR (Real-Game BR) at `rgbr.cpp:34-195`; sampling approximation at `run_approx_rgbr.cpp` (864 lines). RGBR inherits from `CFRP` — the BR walk reuses CFR traversal with `value_calculation_ = true` (line 39), which swaps regret-matching for elementwise max over action values.

**Approximate RGBR.** `run_approx_rgbr.cpp:1-16`: "The responder is limited in how he can respond... we get a lower bound... We sample so that we only get an approximation of this lower bound." Pre-BR-street the responder plays target strategy; from BR street onward, BR; boards on the BR street are sampled.

**Performance characteristics.** Slumbot was a top ACPC HUNL agent (2017-2019). Exact RGBR with full card abstraction takes minutes-to-hours; approximate RGBR is the production check.

**Insights.**
1. Reuse the CFR engine for BR with one flag. Same traversal, swap "regret-matching weighted sum" for "elementwise max" at decision nodes. Suggests one `enum {Solve, BestResponse, OnPolicy}` parameter to a shared Rust traversal.
2. Sampling-based lower-bound BR — 10-100× faster than exact on large games.
3. Per-street BR start (`rgbr.cpp:10-12`). For "is my river converged?" without paying for preflop+flop+turn BR.

---

## Section 2 — Research paper findings

### Zinkevich et al. 2008 (`zinkevich_2008_cfr_nips.pdf`)
Original CFR. Theorem 4: `R_i^T ≤ Δ_{u,i} · |I_i| · √(|A_i|) / √(T)` — regret linear in `|I|`. BR walk cost is also linear in `|I|`. **Applicability:** confirms speedups must come from cheaper per-infoset BR work (vector ops, SIMD, dense storage), not from skipping infosets.

### Tammelin 2014, CFR+ (`cfrplus_tammelin_2014.pdf`)
Vector-form, alternating updates, linear averaging on T (`_INDEX.md:22-23`). CFR+ operates on hand-vectors per infoset, not per-hand. **Applicability:** our `solver.py` does this on the *solve* side but not the *BR* side; vectorizing BR is the highest-leverage micro-opt.

### Brown & Sandholm 2019, DCFR (`dcfr_brown_2019.pdf`)
Same vector-form structure as CFR+; discounting only re-weights accumulators. BR computation is independent of the regret-update rule. **Applicability:** Option A's BR speedup is orthogonal to our DCFR choice — same port helps any CFR variant.

### Brown 2017, Libratus (`libratus_brown_2017_science.pdf` + supplement)
Two production-scale BR techniques: (1) `CBV^{σ_{-i}}(I_i)` — counterfactual BR value at an infoset (supplement); used because full BR was intractable at 10^12 infosets; (2) ES-MCCFR with regret-based pruning — sampling probability `K/(K + C - R(a))` for actions with `R(a) < C`. Hardware: 196-600 nodes × (128 GB + 2× 14-core Haswell), ~12M core-hours total. **Applicability:** sampled BR is the production approach at scale — v2.0 territory, not v1.3.

### Brown et al. 2018, Modicum (`depth_limited_brown_2018.pdf`)
Depth-limited subgame with k continuation strategies. Cut HUNL from 600-node supercomputer to 4-core / 16 GB. **Applicability:** if our BR walk is too slow, depth-limiting the BR (BR from turn or river only) is the standard cheat — `_INDEX.md` Modicum entry confirms.

### Brown et al. 2020, ReBeL (`rebel_brown_2020.pdf`)
BR replaced by a learned value head over public belief states. **Applicability:** v3.0 architecture; listed for completeness.

### Zhang et al. 2024, HS-DCFR (`hyperparam_schedules_2024.pdf`)
SoTA *solving* schedules; doesn't touch BR computation. ~10-15 lines on top of DCFR (`_INDEX.md:115`). **Applicability:** if Option A speeds BR 5× and we still miss the gate, HS-DCFR cuts the number of BR walks needed by converging faster. Cheap to add.

---

## Section 3 — Patterns we're NOT using but could

1. **Dense per-node strategy slabs (instead of `HashMap<String, Vec<f64>>`).** Every cited solver uses dense arrays on a tree node; we use a hashmap keyed on infoset-string. The hashmap's `O(1)` lookup is amortized but the constant factor (UTF-8 string hash + Vec allocation + cache-miss-per-key) dominates the inner loop on a small-to-medium tree. Empirical evidence: noambrown C++ vs Python (`_NOTES.md:24`, `vector_eval.cpp`) — same algorithm, ~30-100× speedup just from `Vec<f32>` over `Dict[str, List[float]]`.

2. **Per-depth scratch frame arena.** `ScratchFrame` per recursion depth, allocated once at setup. Eliminates all `Vec::with_capacity` calls on the hot path. noambrown (`trainer.cpp:242-305`) and postflop-solver (`alloc.rs` custom-alloc feature) both use this; we currently don't.

3. **Sampled-board approximate RGBR with confidence bounds.** Slumbot's pattern (`run_approx_rgbr.cpp:1-16`). Trade exact exploitability for sampling variance with chosen N. For our case: BR over a sampled subset of opponent boards/runouts at the river step, scale by the sampling probability, report ±2σ confidence. Useful as the "fast feedback loop" mode in `solver.solve()` even after Option A lands.

4. **Probability-cut threshold (Open_Spiel's `prob_cut_threshold`).** Skip branches with `π_{-i}(I) < ε`. Trivially correct as a *lower bound* on exploitability — and the lower bound is what we typically want ("is my strategy at least this exploitable?"). Cheap to add; turns a 60 s BR walk into 2-5 s when `ε = 1e-4`.

5. **CFR engine reuse for BR (Slumbot's `value_calculation_ = true` flag).** Our Python `_best_response_value` is a separate code path from the CFR solve loop; the two implementations of "walk the tree, compute CFV" can drift. One traversal codepath with an enum `{Solve, BestResponse, EvaluateOnPolicy}` eliminates drift and shares all the SIMD/cache-blocking we've already added in PR 8 (`crates/cfr_core/src/simd.rs`, `:layout.rs`).

---

## Section 4 — Research-backed fallback paths

Ranked by speedup × implementation cost ratio, on the assumption that both Option A and Option B miss their perf gates and we still need a working range-vs-range exploitability story for v1.3.0.

### Rank 1 — Vector-form BR + dense per-node strategy + scratch arena (BEST)
**Technique.** A complete rewrite of `_best_response_value` (`solver.py:253-297`) following the noambrown C++ pattern (`trainer.cpp:242-305`): one tree walk, dense `Vec<f32>` per node indexed by `(action, hand)`, per-depth scratch frames, elementwise max over actions at BR-player nodes. Build a one-shot Rust port that consumes a `HashMap<String, Vec<f64>>` strategy *once at entry*, materializes it into per-node dense slabs, then walks once. License-clean: noambrown is MIT, we can port directly.

**Expected perf improvement.** 30-100× on the BR walk (`_NOTES.md:30` is the precedent — same algorithm shift on a comparable-size river evaluator). For our W1E.3 lossless flop-start (timed out at 2 minutes / 200 iterations), this likely brings the BR walk to seconds. The solve loop itself doesn't speed up — but the BR walk is what blocks Phase 1E workflows from finishing inside their budgets.

**Risk.** Float drift across the strategy materialization step (`HashMap[str, list[f64]] → Vec<f32>` slab). Mitigation: keep strategy storage as `f64` in the slab, only the slice arithmetic is `f32`. Our existing PR 7 differential tests (`tests/test_river_diff.py`) gate this.

**Estimated implementation time.** 5-7 days. Three components: (1) strategy materialization & tree rebuild (1-2 days, reuses `_serialize_hunl_config`); (2) vector-form BR traversal in Rust (2-3 days, port noambrown's `trainer.cpp:242-305` pattern); (3) diff test gauntlet (1-2 days, reuse the v1_3 Option A test plan).

### Rank 2 — Sampled approximate RGBR with confidence bounds
**Technique.** Slumbot's pattern (`run_approx_rgbr.cpp`). Pick the BR start street (river by default); sample N runouts; compute BR on the sampled subtrees only; report `exploitability ± 1.96·σ/√N`. Pure Python is acceptable since the loop runs over far fewer states than full BR.

**Expected perf improvement.** ~`(num_runouts / N)`× — i.e., if we sample 100 of 22100 turn boards, ~221× speedup at the cost of ~10% relative confidence interval. Cheap enough to run every iteration; full BR runs once at the end.

**Risk.** Approximate, not exact. Adds variance to convergence stopping criteria. Mitigation: report both the sampled CI and (every K iterations) the exact value when feasible.

**Estimated implementation time.** 2-3 days. Pure addition; doesn't touch existing code paths. Sits next to `exploitability()` as `approximate_exploitability(game, strategy, num_samples=100)`.

### Rank 3 — Probability-cut threshold on existing Python BR
**Technique.** Add `prob_cut_threshold` parameter to `_best_response_value` (`solver.py:253`). Skip the recursion when `cf_reach < threshold`. OpenSpiel pattern (`best_response.h:43`).

**Expected perf improvement.** 5-30× on rare-action-heavy trees (preflop 4-bet/5-bet ladders especially). Less on flat trees.

**Risk.** Lower-bound only, not exact. But for "is my exploitability below target?" checks this is correct in the same direction — a lower-bound BR understates exploitability, so if the lower bound is below target the strategy is also below target.

**Estimated implementation time.** 1 day. Single-file change; no new dependencies.

**Recommendation if both A and B fail:** ship Rank 3 first (1 day, fixes most workflows), then Rank 1 as v1.4.0 (5-7 days). Rank 2 is a v2.0 production feature, not a v1.3 fix.

**Update (2026-05-23, post-LEG-5):** Option B (blueprint aggregator) shipped at v1.3.0 then was reverted; Option A was not implemented. Rank 1 (vector-form BR + dense slabs + scratch arena) was promoted to "Plan C" and split into Stage C1 (pure-Python numpy slab, v1.3.1 PATCH target) and Stage C2 (Rust port, v1.4 target). See `v1_3_plan_c_prompt.md` and `v1_3_stage_c1_prompt.md` for current implementer prompts.

---

## Section 5 — Recommendations for in-flight implementations

### For Option A (pr-15-rvr-perf — Rust BR port)
1. **Use dense per-node `Vec<f32>` strategy, not the `HashMap<String, Vec<f64>>` that round-trips through `_solve_rust` today.** Materialize the hashmap once at Rust-entry, build per-node slabs, walk dense. This is the noambrown C++ pattern (`trainer.cpp:242-305`), MIT-licensed, directly portable.
2. **Single traversal function with an enum mode flag.** Don't duplicate the on-policy walk and the BR walk — share traversal, branch only at decision nodes (Slumbot pattern, `rgbr.cpp:39`).
3. **Per-depth `ScratchFrame` allocation.** Noambrown's `_NOTES.md:46`. Eliminates `Vec::with_capacity` on the hot path.
4. **Make the BR walk a Rayon `par_iter` over children at chance nodes** (postflop-solver `utility.rs:13-29`). Don't parallelize per-iteration — parallelize per-traversal — same model `crates/cfr_core/src/solver.rs` already uses.

### For Option B (pr-16-blueprint-aggregator)
1. **Pre-build the strength summary and blocker indices once per board, share across all combo subgames.** Noambrown's `build_strength_summary` + `build_blocked_indices` (`vector_eval.py:18-64`) pattern. The blocker indices are board-specific, not hand-specific, so they can be cached across the 169 × 169 combo enumeration.
2. **For the per-class aggregation, use noambrown's vectorized river showdown** (`vector_eval.py:83-124`). Sorted prefix-sum over opponent strengths replaces the O(N²) showdown scan with O(N) per query.
3. **Defer suit-isomorphism handling.** Postflop-solver does this at chance nodes (`utility.rs:421-436` `apply_swap` + `isomorphic_chances`), but the implementation is non-trivial and the suit-blocker effects matter mostly on paired / monotone / three-flush boards. v1.4 territory.

---

## Section 6 — Long-term v2.0 architecture implications

For production-scale range-vs-range (Libratus/Pluribus level), the architecture is research-mature. **Framing:** research summary, not a v2.0 commitment.

**Brown's production stack (Libratus / Pluribus):**
1. Blueprint via ES-MCCFR with regret pruning on a hand-crafted abstraction (Libratus: detailed first 2 rounds + 2.5M flop / 1.25M turn buckets).
2. Nested safe subgame solving from round 3+ with augmented-subgame / estimated-maxmargin formulation (Libratus Theorem 1; Modicum version).
3. Sampled approximate RGBR / CBV for exploitability checks at scale (Libratus supplement).
4. Multi-strategy depth-limited continuations (Modicum's k=4; Pluribus uses same).

**Migration path from current state:**
1. **v1.x:** tabular DCFR on hand-crafted abstraction. We're here.
2. **v2.0:** add nested safe subgame solving with one continuation (blueprint); add sampled RGBR. *Modicum* level; one researcher × a few months.
3. **v2.5:** add k=4 multi-strategy continuations + off-tree bet-size self-improver (Libratus's third module). *Libratus-lite*.
4. **v3.0 (speculative):** learned value head over public belief states (ReBeL). Multi-month NN training; huge surface.

**Hardware reality check.** Libratus: 196 nodes × (128 GB + 2× 14-core). Pluribus blueprint: 64-core server × 8 days × ~$144 cloud spot (`_INDEX.md` Pluribus, "Hardware footprint"). Our MacBook-only constraint (`PLAN.md` "Compute: MacBook-only") caps us at Modicum-level scope without cloud spend.

**Decision at v1.x → v2.0 boundary.** MacBook-only forever (Modicum cap) vs unlock cloud spend (Libratus-lite). MEMORY.md locks MacBook-only; pending re-examination.

---

**End.** Patterns described are MIT-licensed (noambrown) or design-level. AGPL code (postflop-solver) READ for inspiration only — no copy.
