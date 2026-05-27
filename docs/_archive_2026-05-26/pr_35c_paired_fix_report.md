# PR 35 Fix C (Paired): Drop ALL_IN at Cap on Rust + Python

**Branch**: `pr-35c-paired-fix`
**Worktree**: `/tmp/pr-35c-paired-60921` (kept; not removed pending review)
**Branch SHA before commit**: `d885bca` (origin/main, v1.6.0)
**Commit hash**: `63c9432`
**Date**: 2026-05-23
**Reporter agent**: Path A executor

---

## Summary

Implemented the **paired** version of PR 35 Fix C: the cap-reached
node legal-action set no longer includes ALL_IN on **either** the
Rust side (`crates/cfr_core/src/hunl.rs`) or the Python side
(`poker_solver/action_abstraction.py`). Both engines now match
Brown's reference solver
(`references/code/noambrown_poker_solver/cpp/src/river_game.cpp:76-78`),
which early-returns at cap with only `[c, f]`.

The original PR 35 Fix C dropped ALL_IN at cap on Rust only, which
regressed `test_exploit_diff` because Python still emitted ALL_IN
at cap, producing a Python-vs-Rust value mismatch. **This paired
fix preserves Rust↔Python parity** (verified: 5/5 `test_exploit_diff`
tests pass).

---

## Edits Applied

### 1. Rust: `crates/cfr_core/src/hunl.rs` (lines 1133-1141 in worktree)

**Before** (origin/main `d885bca`):
```rust
if ctx.include_all_in {
    actions.push(ACTION_ALL_IN);
}
```

**After** (this fix):
```rust
// PR 35 Fix C (paired): at cap, do NOT emit ALL_IN. Matches Brown
// reference (`cpp/src/river_game.cpp:76-78` early return at cap with
// only `[c, f]`). The unpaired Rust-only fix in PR 35 regressed
// `test_exploit_diff` because Python still emitted ALL_IN at cap;
// this version is paired with the matching guard in
// `poker_solver/action_abstraction.py:236-237`.
if ctx.include_all_in && !cap_reached {
    actions.push(ACTION_ALL_IN);
}
```

### 2. Python: `poker_solver/action_abstraction.py` (lines 236-241 in worktree)

**Before**:
```python
if ctx.include_all_in:
    actions.append(ACTION_ALL_IN)
```

**After**:
```python
# PR 35 Fix C (paired): at cap, do NOT emit ALL_IN. Matches Brown
# reference (`cpp/src/river_game.cpp:76-78` early return at cap with
# only `[c, f]`). Paired with the matching guard in
# `crates/cfr_core/src/hunl.rs:enumerate_legal_actions`.
if ctx.include_all_in and not cap_reached:
    actions.append(ACTION_ALL_IN)
```

### 3. Test sync: `crates/cfr_core/tests/hunl_state_unit.rs` (test_06_raise_cap_postflop)

The test previously asserted ALL_IN is present at cap; flipped to
assert ALL_IN is NOT present at cap, with explanatory comment.

```rust
assert!(!acts.contains(&ACTION_ALL_IN));
```

### 4. `Cargo.lock` — incidental sync

`cfr_core 0.5.0 → 0.6.0` lockfile bump (Cargo.toml had already
declared 0.6.0; lockfile at origin/main was stale).

---

## Verification

### Build
```
cargo build --release --manifest-path crates/cfr_core/Cargo.toml
```
Status: **PASS** — Finished `release` profile [optimized] target(s).

### Cargo tests
```
cargo test --manifest-path crates/cfr_core/Cargo.toml --release
```
Status: **82/82 PASS**
- 50/50 lib tests
- 19/19 `hunl_state_unit.rs` integration tests
- 13/13 `test_hunl_rust.rs` integration tests
- 0 doc tests

### Scoped pytest (the spec-listed scope)
```
pytest tests/test_action_abstraction.py tests/test_hunl_tree.py -v
```
Status: **22/22 PASS**

### Critical regression gate
```
pytest tests/ -k exploit_diff -v
```
Status: **5/5 PASS** (this was the test that caused the original
PR 35 Fix C to be reverted)

| Test | Result |
|------|--------|
| `test_fixed_combo_river_empty_strategy_matches` | PASS |
| `test_fixed_combo_river_after_short_solve_matches` | PASS |
| `test_fixed_combo_river_single_bet_size_matches` | PASS |
| `test_chance_enum_river_completes_within_perf_gate` | PASS |
| `test_chance_enum_river_end_to_end_solve_within_perf_gate` | PASS |

Python-vs-Rust value parity is **preserved** by the paired fix.

### A83 spot test
```
pytest tests/test_v1_5_brown_apples_to_apples.py -v -k A83
```
Status: **BLOCKED by pre-existing bug** — `ValueError: index out of
bounds: the len is 49 but the index is 49` from
`crates/cfr_core/src/dcfr_vector.rs:651` when calling
`solve_range_vs_range_rust`. Confirmed this panic reproduces
on origin/main without any of our changes (ran same test with
shared-tree `_rust.so` from main branch → same panic). The A83
spot cannot be exercised via this test until that upstream
index bug is fixed.

### K72 spot test (other Brown apples-to-apples spot)
```
pytest tests/test_v1_5_brown_apples_to_apples.py -v -k K72
pytest tests/test_river_diff.py::test_river_parity_vs_brown[dry_K72_rainbow]
```

**v1_5 test (`test_v1_5_brown_apples_to_apples`):**
- With this fix: history coverage **53.3%** (16/30 Brown histories
  matched in Rust's keys) — fails 80% floor.
- On origin/main baseline: history coverage **53.3%** — identical.
- **Conclusion**: Fix C alone does not move the K72 coverage
  needle visibly in this test.

**river_diff test (`test_river_diff.py::test_river_parity_vs_brown[K72]`):**
- With this fix: **timed out at 660s** during solve.
- On origin/main baseline: **also timed out at 660s** — identical
  failure mode.
- **Conclusion**: Not a regression; the K72 river_diff timeout is
  a pre-existing flake / perf issue.

The tree-shape divergence has multiple sources beyond the cap-
ALL_IN issue (per the A83 root-cause investigation). The paired
fix is **necessary but not sufficient** for closing the K72/A83
gap.

### Broader sweep (partial)
- `test_hunl_diff.py`: 7 pass, 1 fail
  (`test_hunl_flop_dry_3size_diff_python_vs_rust_tiny_abstraction`)
  - Pre-existing: same failure on origin/main with same error
    (`canonical board key 'r2s0_r2s1_r7s2_r14s0' not in TURN table
    (build-side coverage bug)`). Not caused by our fix.
- `test_hunl_core.py`: 17/17 pass.

---

## Recommended Next Step

**Path: combine with Path C tolerance widening**, plus continued
investigation per the A83 root-cause doc.

Rationale:
1. The paired Fix C is **correct in isolation** (matches Brown's
   tree shape, preserves Rust↔Python parity) and should be merged
   regardless — it removes one source of divergence and aligns the
   action-enumeration semantics with the reference solver.
2. **It alone does not measurably close the K72 coverage gap**, so
   the remaining 26.7pp (or whatever the post-merge value is)
   must come from elsewhere — likely Path B (canonicalization
   render bug suspicion) or a deeper engine-shape issue.
3. **A83 spot is gated by an unrelated `dcfr_vector.rs:651` index
   bug** which must be fixed before A83 can be re-baselined under
   any of the three Paths.
4. **Path C tolerance widening** is appropriate as a short-term
   guardrail to convert the acceptance gate from a hard failure
   into a measurable budget while the deeper divergence is
   investigated, but it should **not** be the only response.

### Concrete next-up checklist
- [ ] Merge this commit (`63c9432`) into the v1.6.1 bundle on a
      private integration branch.
- [ ] Open follow-up: fix `dcfr_vector.rs:651` hand-index bug
      that blocks A83 testing entirely.
- [ ] Re-run K72 + A83 once the dcfr_vector bug is fixed; quantify
      the post-paired-fix coverage delta.
- [ ] If post-fix coverage gap is still >5pp, investigate Path B
      (canonicalization renderer in the test harness) — the test
      error message itself says "test bug — fix the renderer" as
      an alternative explanation.
- [ ] Independently, apply Path C tolerance widening on the K72/
      A83 acceptance gates so they don't block CI while the
      deeper investigation continues.

---

## Cleanup Status

- Worktree at `/tmp/pr-35c-paired-60921` is **kept** for next-agent
  follow-up.
- Branch `pr-35c-paired-fix` at commit `63c9432` is **local-only**;
  has NOT been pushed to origin (per task spec).
- A symlink was created at
  `/tmp/pr-35c-paired-60921/references/code/noambrown_poker_solver/cpp/build/river_solver_optimized`
  pointing to the shared-tree binary so Brown-parity tests can run
  inside the worktree. This is read-only and does not pollute the
  shared tree.

## Constraints Honored

- [x] Worktree-isolated (no edits to shared `/Users/ashen/Desktop/poker_solver`)
- [x] No push to origin
- [x] No sub-agents spawned
- [x] No destructive git operations
- [x] Within 60-min time budget
