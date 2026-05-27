# v1.3 Plan C Implementer Prompt — noambrown-pattern Vector BR Port

**Use when:** Both Option A (`pr-15-rvr-perf`) AND Option B (`pr-16-blueprint`)
missed their perf gates. Plan C is the research-backed fallback from
`docs/pr_proposals/v1_3_research_alternatives.md` §4 Rank 1 — a vector-form
BR rewrite following Noam Brown's MIT C++ trainer. Estimated 5-7 days.

---

## Agent Prompt (paste-ready)

You are the implementer for **PR 17 — v1.3 Plan C: noambrown-pattern vector
BR port**. Both prior approaches missed the < 60 s perf gate; this PR targets
**< 30 s** on the same bench config. Technique and rationale are in
`docs/pr_proposals/v1_3_research_alternatives.md` §4 Rank 1 — read that
before writing code. The 30-100× speedup is sourced from noambrown's
`_NOTES.md:30` precedent (same algorithmic shift, comparable evaluator) and
is **not extrapolation**.

### Worktree setup

```bash
git worktree add /Users/ashen/Desktop/poker_solver_worktrees/pr-17-plan-c \
  origin/main -b pr-17-plan-c-noambrown-pattern
cd /Users/ashen/Desktop/poker_solver_worktrees/pr-17-plan-c
```

Never branch-switch in the shared tree. Run `git log -1` on the base commit
and record the SHA in your PR report.

### Required reading (in order)

1. `docs/pr_proposals/v1_3_research_alternatives.md` §3, §4 Rank 1, §5 (Option
   A recommendations apply directly here).
2. `references/code/noambrown_poker_solver/cpp/src/trainer.cpp:242-305` —
   the canonical vector-form BR you are porting (MIT, portable):
   - Lines 246-247: `ScratchFrame &frame = scratch_[depth];` — per-depth
     scratch, zero alloc during traversal.
   - Lines 269-283: opponent branch — multiply `reach_opp` by `strategy[h *
     action_count + a]`, recurse, sum child CFVs.
   - Lines 286-302: target branch — collect per-action CFVs, elementwise max
     per hand (line 297 `if (value > best_val)`).
   - Lines 250-262: chance/terminal via showdown evaluator.
3. `references/code/noambrown_poker_solver/cpp/src/trainer.h` —
   `ScratchFrame` struct (`_NOTES.md:43-49` is the explicit recommendation).
4. `poker_solver/solver.py:253-297` — Python `_best_response_value` being
   replaced. Bit-equivalence is the diff-test contract.
5. `crates/cfr_core/src/solver.rs`, `simd.rs`, `layout.rs` — current layout.

### Scope (Rust + Python glue)

1. **New file** `crates/cfr_core/src/exploit_vec.rs`:
   - Vector-form BR — one tree walk per `target_player`.
   - Public `pub fn exploitability(tree: &Tree, strategy: &StrategySlabs) -> f64`
     returning `(mes_ev[0] + mes_ev[1]) * 0.5`.
   - Recursor `fn best_response(node_id, target_player, reach_opp: &[f64], depth)`
     mirroring `trainer.cpp:242-305`.
   - **Dense per-node `Vec<f32>` strategy slabs** indexed `[hand *
     action_count + action]`. Materialize from `HashMap<String, Vec<f64>>`
     once at Rust entry. Slab storage stays `f64`; only per-row slice
     arithmetic narrows to `f32` (matches postflop-solver / noambrown).
   - **Single shared traversal** parameterized by `enum Mode { Solve,
     BestResponse, OnPolicy }`. `Solve` = regret-matching weighted sum
     (reuses CFR engine), `BestResponse` = elementwise max, `OnPolicy` =
     strategy-weighted sum. Slumbot pattern (`rgbr.cpp:39`,
     `value_calculation_ = true`). Eliminates solve/BR code drift.
   - **Per-depth `ScratchFrame` { strategy, values, action_values, next_reach
     }** pre-allocated at setup, sized to `max_action_fanout ×
     max_hands_at_depth`. Zero `Vec::with_capacity` calls on the hot path.

2. **Strategy materialization helper**: walks existing `HashMap<String,
   Vec<f64>>` + tree once at entry, builds dense slabs. Hashmap stays the
   on-disk format; slab is in-memory pre-compute.

3. **Python binding** in `crates/cfr_core/src/lib.rs` (additive):
   `exploitability_hunl_postflop_vec(config_json, strategy) -> float` and
   `_preflop_vec(...)`. Mirror PR 15's binding signatures for drop-in.
   Python `_best_response_value` is retained as diff-test oracle.

4. **Python wiring** in `poker_solver/solver.py`: `use_vec_br=True` default
   kwarg on `exploitability()` routes through the new binding; `False`
   keeps the Python path. Do not remove Python path.

### Performance gate (load-bearing)

**< 30 s** end-to-end on the Phase 1E bench config (500 iters × 2 bet sizes
× `initial_hole_cards=()`, same machine identity in
`benches/exploitability_baseline.json`). More ambitious than Option A's 60 s
— supported by noambrown's 30-100× precedent. Mean ± stddev over ≥ 5 runs;
CV > 20 % triggers re-run. Microbench deltas do not count — end-to-end only
(PR 8 § 7, MEMORY.md `[Don't extrapolate]`).

### Diff-test gate (load-bearing)

New `tests/test_exploitability_diff_vec.py`. **Bit-equivalent (≤ 1e-6 abs,
≤ 1e-9 on-strategy)** vs Python `_best_response_value` on all 5 spec fixtures
(`v1_3_range_vs_range.md` §3: default_tiny_subgame, PR 9 preflop AhKh-vs-QdQc,
W1E.3 flop-start, W1E.4 river-start, tiny chance-enum empty-`()`). Looser
tolerance must-fix unless accumulation-order analysis justifies. Use
`to_bits()` where allowed (PR 8 §8).

### Regression gates

All existing test suites stay green:
- `pytest tests/ -m 'not slow'` (full Python).
- `cargo test --release --all-targets`.
- `cargo clippy --release --all-targets -- -D warnings`.
- PR 6 / PR 7 / PR 9 differential tests untouched (`test_river_diff.py`,
  `test_kuhn_diff.py`, `test_leduc_diff.py`, `test_exploitability_diff.py`
  if PR 15 landed).
- Phase 1E re-runs (W1E.2 / W1E.3 / W1E.4) complete within 10-15 min budgets.

### License hygiene

noambrown_poker_solver is **MIT** — `references/code/noambrown_poker_solver/LICENSE`.
You may port `trainer.cpp:242-305` and the `trainer.h` `ScratchFrame` pattern
directly. **Cite the source in commit message** via a `Ported-From:` trailer
naming the file:line range and upstream MIT license (not `Co-Authored-By`).
New `.rs` files carry MIT headers. AGPL probe still applies — no
`compute_average`, `slice_absolute_max`, `compute_cfvalue_recursive`,
`scratch.prefix`, `finalize_bunch` (PR 8 §5 list).

### Out of scope

- AVX-512 / wide SIMD beyond `simd.rs`.
- Sampled BR (Rank 2 — v2.0).
- Probability-cut threshold (Rank 3 — separate PR if Plan C also misses).
- Rayon parallelism over children — single-threaded matches noambrown
  (`_NOTES.md:46`); parallelism is v1.4+ work.

### Deliverables

- `crates/cfr_core/src/exploit_vec.rs` (new).
- `crates/cfr_core/src/lib.rs` (PyO3 binding additions, additive only).
- `poker_solver/solver.py` (`use_vec_br=True` routing).
- `tests/test_exploitability_diff_vec.py` (new diff test).
- `benches/exploitability_baseline.json` updated, same machine identity.
- `docs/pr17_prep/pr_report.md` (numbers, gate status, port citations).

Report back: bench mean ± stddev, diff-test max absolute delta across all 5
fixtures, and confirm gates 1-3 above. The orchestrator drafts
`docs/pr17_prep/audit_kickoff.md` once your report lands.
