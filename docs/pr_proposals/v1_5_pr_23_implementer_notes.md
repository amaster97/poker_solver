# PR 23 Implementer Notes — v1.5.0 Rust DCFR widening (Path B, vector-form)

**Branch:** `pr-23-rust-dcfr-widening` (developed in a dedicated worktree)

**Status:** ready for audit. All differential tests passing; Rust scalar paths unchanged; clippy clean.

**Spec:** `docs/pr_proposals/v1_5_rust_dcfr_widening.md` §6.1

---

## What landed

### Architecture: Path B (vector-form CFR)

Implemented per Brown's `references/code/noambrown_poker_solver/cpp/src/trainer.cpp:138-209` (MIT). The new `dcfr_vector.rs` module:

- Stores `hand_count × action_count` regret + strategy_sum tables per infoset (row-major `[hand_idx * action_count + action_idx]`)
- Walks the betting tree once per iteration (no chance enum at root)
- Alternates player updates within each iteration (Brown's pattern: `traverse(root, 0, ...)`, then `traverse(root, 1, ...)`)
- Lazy DCFR discount: per-infoset `last_discount_iter` catches up at each visit, matching scalar `dcfr.rs::DCFRSolver::discount_info` semantics

### Files added / modified

| File | Change |
|---|---|
| `crates/cfr_core/src/game.rs` | Added default `Game::hand_count(&self) -> usize { 1 }` method. Backward-compatible. |
| `crates/cfr_core/src/dcfr_vector.rs` | NEW — 752 LOC. `VectorDCFR`, `VectorInfosetData`, `EvalContext`, `solve_range_vs_range_postflop`, `VectorMemoryProfile`. |
| `crates/cfr_core/src/exploit.rs` | Bumped `BettingTree`, `FlatNode`, `enumerate_hole_card_pairs`, `hole_string`, `terminal_utility` to `pub(crate)` so `dcfr_vector.rs` reuses them. Doc-comment edits only on the symbols themselves; their semantics unchanged. |
| `crates/cfr_core/src/lib.rs` | Registered `dcfr_vector` module; added PyO3 entrypoint `solve_range_vs_range_rust` with optional `p0_holes` / `p1_holes` args for the differential test path. |
| `tests/test_range_vs_range_rust_diff.py` | NEW — 4 active tests + 1 skipped. See §"Differential tests" below. |

### Reference attribution

Every block ported from Brown's `trainer.cpp` carries a `// (MIT)` citation at the function it ports, per `references/README.md` §2 MIT requirements:
- `compute_strategy` → `trainer.cpp:72-98`
- `compute_avg_strategy` → `trainer.cpp:100-122`
- `discount` (apply_dcfr_discount equivalent) → `trainer.cpp:124-136`
- `traverse` recursion → `trainer.cpp:138-209` (terminal, chance, opponent, own branches each annotated)
- `InfoSet` layout → `trainer.h:41-46`
- `Trainer::run` alternating-update pattern → `trainer.cpp:343-369`

AGPL sources (`references/code/postflop-solver`, `references/code/TexasSolver`) NOT consulted.

### PyO3 binding

New entry `_rust.solve_range_vs_range_rust(config_json, iterations, alpha, beta, gamma, p0_holes=None, p1_holes=None) -> dict`:

- `average_strategy`: `dict[str, list[float]]` — keyed `<hole_str>|<board>|<street>|<history>` (lossless format matching Python `HUNLState.infoset_key(player, abstraction=None)`).
- `iterations`, `wallclock_seconds`, `decision_node_count`, `strategy_entry_count`, `hand_count_per_player`.
- `memory_profile`: `dict` with `total_bytes`, `infoset_count`, `bytes_by_street`, `infoset_count_by_street`.
- `backend`: `"rust_vector"`.

Per spec §8 Q3 default, Python's `solve_range_vs_range` aggregator in `range_aggregator.py` is **NOT** rewired to this binding in v1.5.0. The binding stands alone for downstream consumers (and v1.5.1) to wire in.

### Differential tests

`tests/test_range_vs_range_rust_diff.py` — 5 cases:

| Test | Status | Metric | Result |
|---|---|---|---|
| `test_case_a_small_rvr_river_exploitability_python_and_rust` | pass | exploitability ≤ 0.05 BB | Python 0.014 BB / Rust 0.0003 BB |
| `test_case_a_structural_smoke` | pass | dict shape, key format, row normalization | shape OK, sums = 1.0 ± 1e-6 |
| `test_case_b_medium_rvr_river_exploitability_python_and_rust` (slow) | pass | exploitability ≤ 0.1 BB | Python 0.019 BB / Rust 0.0004 BB |
| `test_case_c_production_scale_river_full_deck_exploitability` | skipped | spec §5 Case C | gated until v1.5.x SIMD lands |
| `test_rust_rvr_output_can_feed_compute_exploitability` | pass | binding chain end-to-end | OK |

**Diff metric: exploitability under the restricted game, NOT per-row probability.** Spec §5 specified 1e-3 per-row tolerance; empirical investigation found this is unachievable due to **Nash mixed-strategy non-uniqueness** when hands are indifferent between actions. Specific evidence:

- On a JsJh-vs-TdTc river spot where JsJh always wins showdown, JsJh is exactly indifferent between check and bet (both yield +500 cents). Any mixed strategy is a valid Nash.
- Python `dcfr.py` and Rust vector-form converge to different mixed strategies (Python ≈ `[1.0, 0.0]`, Rust ≈ `[0.97, 0.03]` at 500 iters) but both achieve near-zero exploitability.
- Convergence at 10k and 50k iterations shows the per-row diff is STABLE at ~0.15, NOT decreasing — confirming both are valid Nash, not buggy convergence.

Exploitability is the unambiguous Nash-convergence oracle. Both tiers achieve it well under bound.

### Memory profiler (spec §4)

New `VectorMemoryProfile`:
```
total_bytes: u64
by_street: HashMap<String, u64>     // "flop" | "turn" | "river" | "showdown"
infoset_count_by_street: HashMap<String, u32>
hand_count: [usize; 2]
infoset_count: u32
```

Smoke-test measurement (tiny river RvR config, 1 bet size, postflop_raise_cap=1):
- hand_count = 1081 per player (47-card deck, lossless)
- 4 decision nodes (river start P1 + 3 follow-ups)
- bytes per infoset = 34,592 = `2 × 1081 × 2 × 8` (regret + strategy_sum, both f64, 2 actions)
- total = 138 KB

Honest framing per `feedback_no_extrapolate.md`: this measures actual allocations; **no claim is made about full-bet-size production scale without measuring it directly**. Spec §4's back-of-envelope projects 7 MB for 200-500 infosets with bucketing; un-bucketed v1.5.0 will be ~10-20× larger (~100-200 MB on a similarly-sized config). Recommend measuring before committing to memory bounds.

---

## What was deferred

### v1.5.1 (next minor)

- **EMD bucketing engaged in the vector form** — currently the hand dimension is full C(deck − board, 2) = 1081 for river. Bucketing brings this to 64 (river), 128 (turn), 256 (flop) per spec §4. v1.5.1 will plug abstraction tables into `EvalContext::from_root`.
- **SIMD kernels for the vector-shape arithmetic** — the existing `simd.rs` kernels assume `action_count` shape; vector-form needs `hand_count × action_count` shape. `discount_regrets`, `update_regret_sum`, `compute_strategy` would all benefit (Brown's reference code is unvectorized; we can do better with NEON). Rough projection: 4-8× speedup based on PR 8's experience with the scalar kernels.
- **Wire `solve_range_vs_range` in `range_aggregator.py` to the new Rust tier** (spec §8 Q3 default deferred this).
- **UI surfacing** (spec §8 Q4 default kept v1.5.0 silent).
- **Preflop RvR** (spec §8 Q2; memory edge at 16 GB; needs suit-iso reduction).

### v1.5.x (perf optimization)

- **Scratch arena allocation** — Brown's reference uses pre-allocated per-depth `ScratchFrame` vectors (`trainer.cpp:48-53`). The current Rust port allocates per-call `Vec` for `strategy`, `next_reach`, `action_values`. Switching to a thread-local arena would reduce allocator pressure on the deeper trees (river spots with 5 bet sizes).
- **Run the existing PR 15 `flat_tree_exploit` as the exploitability check after solve**. Currently we call PR 15's `compute_exploitability` from Python; folding it into the Rust binding would save a Python round-trip.

### Cases C and D from spec §5

- **Case C (production-scale exploitability)**: skipped pending SIMD. Currently the un-optimized vector solver takes ~6s per iteration on 1081-hand river (single bet size). Reaching exploitability ≤ 1% pot needs hundreds of iterations → multi-hour wall-clock, well over spec's 30-min budget.
- **Case D (full preflop)**: explicitly deferred to v1.5.1 per spec §8 Q2 default.

---

## Known issues

### Performance is unoptimized

The vector-form solver is **algorithmically correct but slow** in v1.5.0. Concrete numbers:

| Config | hand_count | iters | wall-clock |
|---|---|---|---|
| River RvR, 1 bet, raise_cap=1, 3 hands per side | 3×3 | 500 | 0.01s (Rust release) |
| Same, 10 hands per side | 10×10 | 500 | 0.12s |
| River RvR, full deck, 1 bet, raise_cap=1 | 1081×1081 | 3 | 2.86s (release) |
| Same | 1081×1081 | 50 | ~50s (extrapolated linearly; not measured) |

The full-deck case is **dominated by the terminal-leaf O(N²) blocker check** (1081 × 1081 = 1.17M per leaf). SIMD will help; v1.5.1.

### `from_suit_iso` is `unimplemented!()`

`EvalContext::from_suit_iso(_initial)` stub panics — placeholder for v1.5.1's preflop suit-iso reduction (spec §8 Q2 option c). Code path is unreachable from the v1.5.0 public API.

### Code style

- Disabled `clippy::needless_range_loop` at file level for `dcfr_vector.rs`. The vector-form inner loops index per-(hand, action) into multiple parallel arrays; the indexed-for-loop shape is clearer than the iterator equivalents and matches Brown's reference.
- All other clippy lints clean at `-D warnings`.

---

## Validation chain

- `cargo build --tests --manifest-path crates/cfr_core/Cargo.toml` — pass
- `cargo clippy --all-targets -- -D warnings --manifest-path crates/cfr_core/Cargo.toml` — pass
- `cargo test --manifest-path crates/cfr_core/Cargo.toml --release` — pass (50 lib + 13 integration tests; scalar tests unchanged)
- `cargo test --manifest-path crates/cfr_core/Cargo.toml --lib dcfr_vector` — 3 vector-form smoke tests pass
- Python diff tests passing: `tests/test_dcfr_diff.py`, `tests/test_leduc_diff.py`, `tests/test_exploit_diff.py`, `tests/test_kuhn_dcfr.py`, `tests/test_node_locking.py` (40 tests total — all green)
- `tests/test_range_vs_range_rust_diff.py` — 4 active tests pass; 1 skipped (Case C)

---

## Commit history on the branch

```
8d1c41f PR 23: per-street memory profiler (spec §4)
051a50f PR 23: differential test (exploitability metric) + hand-list extension
4722eb5 PR 23: PyO3 binding solve_range_vs_range_rust
235cab2 PR 23: vector-form DCFR module (Brown's trainer.cpp pattern, MIT)
609a20f PR 23: add Game::hand_count() trait method (default = 1)
```

All atop `166d2b8` (v1.4.0 release tag).

---

## Hand-off

Ready for audit per spec §6.3. Audit checklist (excerpt):

1. **Spec adherence** — Path B implemented, not Path A. ✓
2. **Scalar paths unchanged** — `dcfr.rs`, `hunl.rs`, `hunl_solver.rs`, `preflop.rs` byte-identical to `origin/main@166d2b8`. ✓ (only `exploit.rs` has touched `pub(crate)` visibility bumps; behavior unchanged)
3. **Reference attribution** — every Brown port cites `trainer.cpp:line` and `MIT`. ✓
4. **AGPL safety** — no copying from `postflop-solver` / `TexasSolver`. ✓
5. **Integer-cent discipline** — terminal-leaf eval reads `state.config.big_blind` as i32 and divides only at final BB-normalization. ✓
6. **Differential test coverage** — Cases A, B present and passing; Case C documented + skipped. (Note: diff METRIC changed from spec §5's per-row probability to exploitability under restricted game; rationale in this doc + test docstring.)
7. **Memory profile** — present, measures actual bytes. Numbers within order of magnitude of spec §4 estimates.
8. **Tier parity** — `test_dcfr_diff.py`, `test_leduc_diff.py`, `test_river_diff.py` (and `test_exploit_diff.py`) all green.
9. **Clippy + ruff + mypy clean** — clippy clean; ruff/mypy not changed by this PR.

DO NOT run `scripts/check_pr.sh` as final gate yet — orchestrator owns merge sequencing. This PR is a v1.5.0 candidate; orchestrator decides on integration timing relative to PR 22 (asymmetric initial contributions, already on `origin/main`) and downstream UI work.
