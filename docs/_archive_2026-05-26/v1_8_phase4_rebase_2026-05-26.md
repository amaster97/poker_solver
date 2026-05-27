# PR #32 v1.8 Phase 4 (compute_strategy SIMD) — rebase + merge

**Date:** 2026-05-26
**Operator:** Agent (rebase executor)
**Branch:** `pr-71-v1.8-phase4-compute-strategy-simd`
**Local worktree branch:** `pr-32-phase4-rebase-2026-05-26`
**Source SHA (pre-rebase):** `0734c0d3e3de9f39e85af9a93bee0d5944254a61`
**Rebased SHA (post-resolve):** `b56f9abda57d010c301c909e2c9690995cb70d53`
**Squash-merge commit on main:** `77e751cdbee5861207b296ad0b40acb5890501b1`

## Pre-rebase diff stats (commit content only)

```
crates/cfr_core/src/dcfr_vector.rs        |  27 +--
crates/cfr_core/src/simd.rs               | 360 +++++++++++++++++++++++++++++-
crates/cfr_core/tests/test_simd_phase4.rs | 189 ++++++++++++++++
3 files changed, 555 insertions(+), 21 deletions(-)
```

The full `git diff --stat origin/main..HEAD` over the whole tree was ~53 files (1001+/3677-) because the Phase 4 branch was based off pre-Phase-1 main and the cumulative tree drift includes many files already changed on main; only the 3 files above are touched by the PR's commit itself.

## Rebase target

- `git fetch origin` → main moved to `a6b89f7`.
- Phase 3 (`a712950`) and prior Phase 1/2 work were already on main; Phase 4 was branched off pre-Phase-1 main and never re-stacked.

## Conflict surface

`git rebase origin/main` produced one conflicted file:

- `crates/cfr_core/src/dcfr_vector.rs` — **auto-merged** by git.
- `crates/cfr_core/src/simd.rs` — **5 conflict regions, all in x86_64 modules.** NEON region merged cleanly (Phase 4's `compute_strategy_row_neon` was appended inside main's existing `mod neon { ... }` block by git on its own).

### Conflict 1 — SSE2 module header comment (HEAD lines 607–627)

`mod sse2` doc comment text differs (HEAD lists PRs 61/63/70; Phase 4 mentions only PR 71).

**Resolution:** kept HEAD's lineage comment and extended it to mention PR 71 / `compute_strategy_row` in both the SSE2 scope list and the AVX2 cross-reference. No code involved.

### Conflict 2 — SSE2 module body (HEAD lines 634–853)

Both branches occupy the same lines inside `mod sse2 { ... }`. HEAD has 4 functions (`discount_regrets_sse2`, `discount_strategy_sum_sse2`, `update_regret_sum_vector_sse2`, `update_strategy_sum_sse2`); Phase 4 has 1 different function (`compute_strategy_row_sse2`).

**Resolution:** kept all 4 HEAD functions verbatim, appended Phase 4's `compute_strategy_row_sse2` verbatim immediately after `update_strategy_sum_sse2`. Added the closing brace pair that git's conflict region consumed at the boundary (the `}` that closed `update_strategy_sum_sse2`'s inner `while` and the `}` that closed the function itself were "shared" trailing-context lines outside both conflict halves, so the merged content needed explicit `}` `}` separators between the last HEAD function body and the new Phase 4 function).

### Conflict 3 + 4 — AVX2 module header comment (HEAD lines 859–883)

Same pattern as Conflict 1; HEAD comment lists PRs 68/70, Phase 4 mentions only PR 71. Two separate small conflict hunks inside one comment block.

**Resolution:** kept HEAD's comment, extended to mention PR 71.

### Conflict 5 — AVX2 module body (HEAD lines 890–1121)

Same shape as Conflict 2 in the AVX2 module: HEAD has 3 functions (`discount_regrets_avx2`, `discount_strategy_sum_avx2`, `update_strategy_sum_avx2`); Phase 4 has `compute_strategy_row_avx2`.

**Resolution:** kept all 3 HEAD functions verbatim; appended Phase 4's `compute_strategy_row_avx2` verbatim after `update_strategy_sum_avx2` with the analogous brace fix.

### Orphan marker

After resolving Conflict 5, a stray `<<<<<<< HEAD` line was left at the top of `mod avx2 { ... }`'s body (an artifact of how the rebase tool emitted the marker just inside the module opening brace, before its conflicting comment). It was a single orphan line with no matching `=======` / `>>>>>>>` partners (git considered it a marker because of the literal string at line start, but it had no separator); removed.

## Semantic conflicts: NONE

All 5 conflict regions were the predicted module-redeclaration pattern. **No function bodies overlapped between Phase 3 and Phase 4** — confirming the diagnostic note that Phase 3's `update_strategy_sum_*` functions and Phase 4's `compute_strategy_row_*` functions are disjoint.

Phase 4's algorithmic content (`compute_strategy_row_scalar/_neon/_sse2/_avx2`, the public dispatch in `simd.rs`, the call-site rewrite in `dcfr_vector.rs`) was preserved bit-for-bit.

## Cargo verification (M-series host, aarch64-apple-darwin)

```
$ cargo check --manifest-path crates/cfr_core/Cargo.toml
   Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.11s

$ cargo test --release --test test_simd_phase4
running 6 tests
test compute_strategy_row_all_positive_normalizes ... ok
test compute_strategy_row_hunl_full_menu_width ... ok
test compute_strategy_row_all_zero_falls_back_to_uniform ... ok
test compute_strategy_row_all_negative_falls_back_to_uniform ... ok
test compute_strategy_row_mixed_signs_preserve_zero_on_negatives ... ok
test compute_strategy_row_sweeps_lengths_zero_to_twelve ... ok
test result: ok. 6 passed; 0 failed

$ cargo test --lib simd
running 9 tests   (positive_regrets_and_total_matches_scalar, normalize_matches_scalar,
                   discount_strategy_sum_matches_scalar, update_regret_sum_matches_scalar_bit_exact,
                   discount_regrets_matches_scalar, update_strategy_sum_matches_scalar_bit_exact,
                   update_regret_sum_vector_matches_scalar_bit_exact,
                   update_regret_sum_vector_handles_odd_hand_count,
                   positive_regrets_and_total_is_bit_exact_for_total)
test result: ok. 9 passed; 0 failed

$ cargo test --release --test test_simd_phase3
running 6 tests   (update_strategy_sum_lengths_0_to_12_bit_exact, ...)
test result: ok. 6 passed; 0 failed

$ cargo test --release --test test_simd_dispatch
running 5 tests   (discount_strategy_sum_handles_odd_length_tails, ...)
test result: ok. 5 passed; 0 failed
```

All four passes green: Phase 4 own tests (6/6), in-tree lib SIMD tests (9/9 — regression check on Phase 1/2/3 kernels), Phase 3 tests (6/6 — Phase-3-specific regression check), and dispatch tests (5/5).

## Push

```
$ git push --force-with-lease origin pr-32-phase4-rebase-2026-05-26:pr-71-v1.8-phase4-compute-strategy-simd
 + 0734c0d...b56f9ab pr-32-phase4-rebase-2026-05-26 -> pr-71-v1.8-phase4-compute-strategy-simd (forced update)
```

## CI on rebased commit (b56f9ab)

```
bundle-dry-run     pass  5s
check              pass  5s
check              pass  3s
```

`mergeable: MERGEABLE`, `mergeStateStatus: CLEAN`.

## Merge

```
$ gh pr merge 32 --squash --delete-branch
```

PR #32 merged at 2026-05-26T06:26:42Z. Squash-merge commit SHA on `main`: **`77e751cdbee5861207b296ad0b40acb5890501b1`** with message `feat(cfr_core): v1.8 Phase 4 — compute_strategy SIMD (#32)`. Feature branch `pr-71-v1.8-phase4-compute-strategy-simd` deleted from origin.

## Post-merge sync

```
$ git pull --ff-only origin main   # already current at 77e751c
$ git push backup main             # Everything up-to-date (private mirror already in sync)
```

Local `main` HEAD: `77e751cdbee5861207b296ad0b40acb5890501b1`.

## Outstanding

- Local rebase worktree `/Users/ashen/Desktop/poker_solver_worktrees/pr-32-phase4-rebase` still present. Branch `pr-32-phase4-rebase-2026-05-26` is now redundant with merged main; safe to `git worktree remove` and `git branch -D` (not done by this agent — leaving cleanup discretionary).
- v1.8 Phase 4 now in main alongside Phase 1 (PR 61), Phase 2 (PR 68), and Phase 3 (PR 70). All four phases of the SIMD vectorization roll-up landed.

## Summary

Rebase completed in expected ~30-min envelope. Only module-redeclaration conflicts (5 regions, all in x86_64 modules — NEON auto-merged); no semantic conflicts. Phase 4's algorithmic content preserved verbatim. All four test passes green pre-push; CI green post-push. Squash-merge autonomous per Stage-3 (feature-branch only, no force-push to main, no branch deletion outside the feature branch, no C-CRIT changes).
