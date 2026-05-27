# PR Bundle Mergeability Verification

**Date:** 2026-05-24
**Verifier:** Quick verification agent (worktree-isolated, read-only)
**Worktree base:** `origin/main` @ `3843ce7` (v1.7.0)

---

## Phase 1: Per-PR GitHub status

| PR  | Branch                                   | Mergeable | Merge state | Files changed |
|-----|------------------------------------------|-----------|-------------|---------------|
| #5  | `pr-50-facing-all-in-guard`              | Y         | CLEAN       | 2             |
| #6  | `pr-51-dcfr-vector-asymmetric-fix`       | Y         | CLEAN       | 1             |
| #7  | `pr-53-acceptance-test-reframe`          | Y         | CLEAN       | 1             |
| #8  | `pr-52-suit-encoding-fix`                | Y         | CLEAN       | 1             |
| #9  | `pr-54-renderer-stack-ceiling`           | Y         | CLEAN       | 1             |
| #10 | `pr-55-p0-p1-player-swap`                | Y         | CLEAN       | 2             |
| #11 | `pr-58-asymmetric-fixture`               | Y         | CLEAN       | 1             |
| #12 | `pr-56-hand-sort-canonicalization`       | Y         | CLEAN       | 1             |
| #13 | `pr-55-extend-input-range-swap`          | Y         | CLEAN       | 1             |

All 8 target PRs report MERGEABLE + CLEAN against `main` independently.

---

## Phase 2: Dry cherry-pick stack (plan order)

Order tested: 51 → 50 → 52 → 54 → 55 → 55-ext → 56 → 53

| # | PR  | Branch                              | Cherry-pick result |
|---|-----|-------------------------------------|--------------------|
| 1 | #6  | pr-51-dcfr-vector-asymmetric-fix    | CLEAN              |
| 2 | #5  | pr-50-facing-all-in-guard           | CLEAN              |
| 3 | #8  | pr-52-suit-encoding-fix             | CLEAN              |
| 4 | #9  | pr-54-renderer-stack-ceiling        | CLEAN              |
| 5 | #10 | pr-55-p0-p1-player-swap             | CLEAN (auto-merge resolved on `noambrown_wrapper.py`) |
| 6 | #13 | pr-55-extend-input-range-swap       | CLEAN (auto-merge resolved on `noambrown_wrapper.py`) |
| 7 | #12 | pr-56-hand-sort-canonicalization    | CLEAN (auto-merge resolved on `noambrown_wrapper.py`) |
| 8 | #7  | pr-53-acceptance-test-reframe       | **CONFLICT**       |

### Conflict detail

**PR #7 (pr-53-acceptance-test-reframe) vs PR #9 (pr-54-renderer-stack-ceiling)**

- **File:** `tests/test_v1_5_brown_apples_to_apples.py`
- **Conflict regions:** 4 hunks at approx lines 453, 472, 655, 729
- **Nature:** Both PRs edit overlapping regions of the same test file:
  - Comment text near lines 453, 472 (PR 54: "Fix A (PR 35):..." style; PR 53: "All-in jam:..." style)
  - Logic at ~line 729: PR 54 uses `(player, history_substr)`; PR 53 uses `(rust_player, history_substr)` — semantically different lookup
- **Order-independence:** Confirmed by re-running with PR 53 first then PR 54 — same conflict appears in reverse direction. The overlap is fundamental, not order-induced.

---

## Phase 3: PR #11 (asymmetric-fixture) independent test

- Branch: `pr-58-asymmetric-fixture`
- Single new file: `tests/test_asymmetric_range_sanity.py` (390 lines, added)
- Cherry-picked on top of the 7-PR stack (before reaching PR 53): **CLEAN**
- Cherry-picks cleanly against bare `origin/main` as well (no overlap with any other PR's changes)

---

## Phase 4: Cleanup

Worktree `/private/tmp/pr-verification-64428` removed. `git worktree prune` ran cleanly.

---

## Overall verdict

**CONFLICTS-FOUND**

- 7 of the 8 PRs (#5, #6, #8, #9, #10, #11, #12, #13) cherry-pick cleanly together.
- PR #7 (pr-53-acceptance-test-reframe) collides with PR #9 (pr-54-renderer-stack-ceiling) on `tests/test_v1_5_brown_apples_to_apples.py` in 4 hunks.

### Recommended next step

Resolve PR #7 vs PR #9 conflict before bundling. Two options:
1. Rebase PR #7 onto PR #9's branch, manually resolve the 4 hunks, force-push.
2. Ship PR #9 first, then re-target PR #7 to post-PR-9 main.

The non-conflicting subset (#5, #6, #8, #9, #10, #11, #12, #13) is bundle-ready and ships cleanly.
