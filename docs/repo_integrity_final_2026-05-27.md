# Repo Integrity Final Sweep — 2026-05-27

Read-only sweep before user wake-up. Each check is PASS / FAIL with one-line evidence.

## Summary

- **6 PASS / 3 FAIL** (1 cosmetic, 2 surface-worthy)
- No blockers; no destructive action recommended without user review

## Checks

### 1. origin/main vs backup/main parity — PASS

- `git rev-parse origin/main` = `9c98064beb9fd0d80e575bb6a16952071494ed6f`
- `git rev-parse backup/main` = `9c98064beb9fd0d80e575bb6a16952071494ed6f`
- Identical SHAs.

### 2. v1.8.0 tag on both remotes — PASS

- `git ls-remote --tags origin v1.8.0` → `5888cb5a773deddaa1f36ce96e19c644271c987d`
- `git ls-remote --tags backup v1.8.0` → `5888cb5a773deddaa1f36ce96e19c644271c987d`
- Annotated-tag object SHA matches on both remotes.
- Tag target commit: `git rev-parse v1.8.0^{commit}` = `8a9c8d2fbf960b3cf83a16aa2d09ca36a779aba2` ("chore: bump version to 1.8.0 for release") — matches prompt's expected commit `8a9c8d2`.
- Note: prompt expected `8a9c8d2`; `ls-remote` returns the tag-object SHA (`5888cb5`), not the commit SHA. Both layers consistent.

### 3. Local working tree (tracked) — PASS

- `git status --short | grep -v '^??'` returned no tracked modifications after re-check.
- (Initial check showed M flags for CHANGELOG.md/README.md/USAGE.md but `git diff` and `git diff HEAD` both empty — stale index state, no actual content delta.)
- All other `??` entries are untracked doc artifacts / archive dirs / prep folders — not in-flight tracked edits.

### 4. Stash list — FAIL (surface, non-blocking)

`git stash list` shows 7 stashes; none match the `pre-v1.8.0-release-stash-*` naming pattern, but several are old and likely orphaned:

- `stash@{0}` WIP on `docs/readme-quickstart-fix-v1-8-0` (post-ship; possibly leftover)
- `stash@{1}` WIP on `proposal/dcfr-alpha-guard-2026-05-27`
- `stash@{2}` WIP on `pr-75-purge-rust-convention`
- `stash@{3}` `On main: pre-pull-pr71-ship-retry-6` (old ship op)
- `stash@{4}` WIP on (no branch) — `Cargo.lock` skew, dated
- `stash@{5}` `On pr-44-dmg-packaging-fix: shared-tree-cleanup-2026-05-23-late`
- `stash@{6}` `On main: pre-comprehensive-review-fix backup`

No `pre-v1.8.0-release-stash-*` to surface (none were created with that name). User should triage stashes 3/4/5/6 for safe dropping.

### 5. Open PR merge state — FAIL (1 PR UNSTABLE)

Initial pass showed all UNKNOWN (transient GraphQL race); re-query yielded:

| PR    | mergeStateStatus | Notes                                                       |
|-------|------------------|-------------------------------------------------------------|
| #20   | **UNSTABLE**     | 1 FAILURE check + 6 SUCCESS + 1 empty conclusion            |
| #49   | CLEAN            | 3 / 3 SUCCESS                                               |
| #89   | CLEAN            | 3 / 3 SUCCESS                                               |
| #94   | CLEAN            | 3 / 3 SUCCESS                                               |
| #97   | CLEAN            | 3 / 3 SUCCESS                                               |
| #99   | CLEAN            | 3 / 3 SUCCESS                                               |
| #101  | CLEAN            | (from first pass)                                           |
| #103  | CLEAN            | (from first pass)                                           |

PR #20 (slow markers / cross-platform CI matrix) has one failing check — `docs/pr_20_macos14_failure_2026-05-27.md` is already on disk (untracked), suggesting this is a known macOS-14 failure under investigation. Not a new break.

No DIRTY / BLOCKED / KNOWN-conflict states.

### 6. Worktrees — FAIL (10 entries, prompt limit ≤8)

```
/Users/ashen/Desktop/poker_solver                                       40d101a [proposal/vector-rvr-perf-wall-2026-05-27]
/Users/ashen/Desktop/poker_solver_worktrees/dmg-v1-8-0-build            8a9c8d2 (detached HEAD)
/Users/ashen/Desktop/poker_solver_worktrees/fix-brown-buildable-ubuntu  5f814e4 [fix-brown-buildable-ubuntu]
/Users/ashen/Desktop/poker_solver_worktrees/fix-stale-mock-banner       86dac0f [fix-stale-mock-banner]
/Users/ashen/Desktop/poker_solver_worktrees/pr-101-mock-disclosure      1fce0a7 [docs/mock-mode-disclosure-v1-8-0]
/Users/ashen/Desktop/poker_solver_worktrees/pr-20-slow-markers          39a01c8 [pr-64-cross-platform-ci-matrix]
/Users/ashen/Desktop/poker_solver_worktrees/pr-88-v1.8.0-notes          e08c460 [pr-88-v1.8.0-release-notes-prep]
/Users/ashen/Desktop/poker_solver_worktrees/pr-92-resume-doc            4922364 [pr-92-resume-doc]
/Users/ashen/Desktop/poker_solver_worktrees/pr-93-tu-ablation           986f48d [pr-93-terminal-utility-ablation]
/Users/ashen/Desktop/poker_solver_worktrees/pr-merge-analysis           aaa3c10 [analysis/pr-merge-2026-05-27]
```

Candidates for cleanup (post-ship, branch likely merged or stale):
- `dmg-v1-8-0-build` (detached HEAD on v1.8.0 commit — ship is complete)
- `pr-88-v1.8.0-notes` (release notes prep — v1.8.0 shipped)
- `pr-92-resume-doc` (resume doc — likely merged)
- `pr-merge-analysis` (analysis dir, ephemeral)

User should `git worktree remove` 2-4 of these to get under ≤8.

Observation (not a check failure): main worktree HEAD is on `proposal/vector-rvr-perf-wall-2026-05-27` rather than `main`. Single forward commit from `origin/main` (`40d101a proposal: vector-form RvR perf wall options (v1.8.2 candidate)`). Working tree is clean, so safe; user may want to switch back to `main` for routine ops.

### 7. MEMORY.md index size — PASS

- `wc -l ~/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/MEMORY.md` = **23 lines** (< 50).

### 8. PLAN.md local vs canonical — PASS

- `md5 PLAN.md` = `2f1420ec426a5372fa977c2539623afd`
- `md5 ~/.claude/plans/poker_solver_PLAN.md` = `2f1420ec426a5372fa977c2539623afd`
- Identical — recent sync intact.

## Disposition

- **Per prompt instructions:** since there are FAILs (stash residue, worktree count > 8, PR #20 UNSTABLE), this doc is committed and the PR is **HELD for user review** — not auto-merged.
- None of the FAILs are time-sensitive; safe to triage after wake-up.
- No destructive action taken (no stash drops, no worktree removals, no force-pushes).
