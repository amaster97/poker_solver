# Worktree Final Cleanup — 2026-05-26

## Summary

Removed 6 worktrees whose PRs have already merged (worktree-blocks-branch-delete
pattern). All removed worktrees were clean (no uncommitted changes). Worktree
count: **14 → 8**.

## Before count

14 worktrees:

| Path | Branch | Notes |
| --- | --- | --- |
| `/Users/ashen/Desktop/poker_solver` | `main` | primary checkout |
| `/private/tmp/bench-pre-simd` | `bench-pre-simd` | benchmark snapshot (outside target dir) |
| `/private/tmp/wt-pr-89-plan-prune` | `pr-89-plan-prune` | held for user review |
| `…/pr-102-changelog-shim` | `pr-102-changelog-shim-note` | PR #58 MERGED |
| `…/pr-105-a83-supersede` | `pr-105-a83-doc-supersede` | PR #63 MERGED |
| `…/pr-108-chance-hotpatch` | `pr-108-chance-validation-hotpatch` | PR #69 MERGED |
| `…/pr-20-timeout` | `pr-20-rebase-with-timeout-fix` | no PR found |
| `…/pr-88-v1.8.0-notes` | `pr-88-v1.8.0-release-notes-prep` | release-notes reference, no PR |
| `…/pr-92-resume-doc` | `pr-92-resume-doc` | PR #49 OPEN |
| `…/pr-93-tu-ablation` | `pr-93-terminal-utility-ablation` | no PR found |
| `…/pr-95-archive` | `pr-95-untracked-docs-archive` | PR #52 MERGED |
| `…/pr-98-release-notes-honesty-w32-smoke` | `pr-98-release-notes-honesty-w32-smoke` | PR #56 MERGED |
| `…/pr-99-medium-staleness-fix` | `pr-99-medium-staleness-fix` | PR #57 MERGED |
| `…/rebase-pr-20` | `rebase-20-2026-05-26` | no PR found |

## Removed (6)

All clean working trees; worktree removed and local branch deleted.

| Worktree | Branch | PR | PR title |
| --- | --- | --- | --- |
| `pr-102-changelog-shim` | `pr-102-changelog-shim-note` | #58 MERGED | docs: CHANGELOG note for poker-solver PATH shim quirk |
| `pr-105-a83-supersede` | `pr-105-a83-doc-supersede` | #63 MERGED | docs: supersede banner on a83 RC investigation (math error in §2(d)) |
| `pr-108-chance-hotpatch` | `pr-108-chance-validation-hotpatch` | #69 MERGED | fix(solver): hard-fail scalar HUNL postflop without initial_hole_cards (v1.8 ship-blocker) |
| `pr-95-archive` | `pr-95-untracked-docs-archive` | #52 MERGED | docs: archive 34 unreferenced 2026-05-23/25 session drafts |
| `pr-98-release-notes-honesty-w32-smoke` | `pr-98-release-notes-honesty-w32-smoke` | #56 MERGED | docs: v1.8 release notes honesty (~1.0x not 4-8x) + W3.2 BR smoke |
| `pr-99-medium-staleness-fix` | `pr-99-medium-staleness-fix` | #57 MERGED | docs: resolve 7 MEDIUM stale claims (post-HIGH-fix follow-up) |

## Kept (8)

| Path | Branch | Reason |
| --- | --- | --- |
| `/Users/ashen/Desktop/poker_solver` | `main` | primary checkout |
| `/private/tmp/bench-pre-simd` | `bench-pre-simd` | benchmark snapshot, outside cleanup target dir |
| `/private/tmp/wt-pr-89-plan-prune` | `pr-89-plan-prune` | held for user review |
| `…/pr-20-timeout` | `pr-20-rebase-with-timeout-fix` | no merged PR found for this branch (kept) |
| `…/pr-88-v1.8.0-notes` | `pr-88-v1.8.0-release-notes-prep` | release-notes prep, no PR; useful reference |
| `…/pr-92-resume-doc` | `pr-92-resume-doc` | PR #49 OPEN |
| `…/pr-93-tu-ablation` | `pr-93-terminal-utility-ablation` | no merged PR; unmerged work-in-progress |
| `…/rebase-pr-20` | `rebase-20-2026-05-26` | no merged PR; rebase-in-flight |

## Skipped (uncommitted changes)

None — all 6 removable worktrees had clean working trees.

## Post count

**8 worktrees** (target dir `/Users/ashen/Desktop/poker_solver_worktrees/`
went from 11 → 5).

## Commands run

```
# remove worktrees
git worktree remove <path>          # x6

# delete local branches
git branch -D <branch>              # x6

# clean up refs
git worktree prune
```

All operations succeeded; no force-removes required.
