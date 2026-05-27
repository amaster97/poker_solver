# Worktree + Stash Cleanup (Post-PR #106 Integrity Check)

**Date:** 2026-05-27
**Trigger:** Repo integrity check (PR #106) surfaced residue (7 stashes + 4 candidate worktrees for removal)
**Operator:** Cleanup agent, working dir `/Users/ashen/Desktop/poker_solver`
**Constraints honored:** No `--force` on worktree removes; no `stash drop` on unidentified stashes; preserved any stash with meaningful WIP message.

---

## Summary

| Action | Count |
|---|---|
| Stashes dropped | 2 |
| Stashes kept | 5 |
| Worktrees removed | 3 |
| Worktrees skipped (dirty) | 1 |
| Final worktree count (incl. main) | 7 |

---

## Stashes Dropped (2)

| Index (pre-cleanup) | Message | Rationale |
|---|---|---|
| `stash@{3}` | `On main: pre-pull-pr71-ship-retry-6` | Explicitly named in cleanup instructions as ship-op pattern. Ephemeral pre-pull backup tied to a long-shipped PR (#71 merged). |
| `stash@{5}` | `On pr-44-dmg-packaging-fix: shared-tree-cleanup-2026-05-23-late: Cargo.lock cfr_core 0.5.0 -> 0.6.0` | Marker `shared-tree-cleanup` = explicit cleanup-op leftover. Tiny diff (Cargo.lock only, 1 insertion / 1 deletion). Lock-skew context is stale (cfr_core has advanced past 0.6.0). |

## Stashes Kept (5)

| Index (post-cleanup) | Message | Rationale for keeping |
|---|---|---|
| `stash@{0}` | `WIP on docs/readme-quickstart-fix-v1-8-0: 9c98064 docs: local PASS confirmation for PR #98 EV invariance gauntlet (#104)` | Auto-WIP. Contains substantial doc/proposal work (466 line insertions across README/USAGE/CHANGELOG + new `docs/vector_rvr_perf_wall_proposal_2026-05-27.md`). Not ship-ephemeral; may be active. |
| `stash@{1}` | `WIP on proposal/dcfr-alpha-guard-2026-05-27: 083a6b5 proposal: DCFR α-guard options (v1.8.1 candidate)` | Auto-WIP. Stash shows empty diff (display anomaly possible). Conservative keep per "do not drop stashes you can't identify as ship-ephemeral". |
| `stash@{2}` | `WIP on pr-75-purge-rust-convention: a9a9029 WIP: convention purge (recovery)` | Explicit "(recovery)" marker — kept per "leave any stash with a meaningful WIP message" rule. Contains unit-test recovery work (`hunl_state_unit.rs` + `test_hunl_tree.py`). |
| `stash@{3}` (was `{4}`) | `WIP on (no branch): ca8c7af docs: bump README version reference v1.5.1 → v1.6.0` | Older WIP on detached HEAD. Single-purpose doc change. No ship-op marker, so kept conservatively. (User may want to verify if the bump landed elsewhere and drop manually.) |
| `stash@{4}` (was `{6}`) | `On main: pre-comprehensive-review-fix backup` | Despite "pre-" prefix, the diff is LARGE (2311 deletions across `range_aggregator.py`, `test_range_vs_range_aggregator.py`, UI state, CHANGELOG, etc.) — this is a substantive backup of a code purge, NOT a small ship-op cleanup. Kept per safety rule. |

---

## Worktrees Removed (3)

| Path | Branch | HEAD | Verification |
|---|---|---|---|
| `/Users/ashen/Desktop/poker_solver_worktrees/pr-88-v1.8.0-notes` | `pr-88-v1.8.0-release-notes-prep` | `e08c460` | No open PR uses this branch. v1.8.0 release notes already shipped via PRs #71, #62, #85, #96, #77, #50, #81 (all MERGED). Working tree clean. |
| `/Users/ashen/Desktop/poker_solver_worktrees/pr-92-resume-doc` | `pr-92-resume-doc` | `4922364` | PR #49 (open) `headRefOid` = `49223642ff1f0b8a932f7065f4ed951dd3ecbf54` — exact match. Branch fully captured upstream. Working tree clean. |
| `/Users/ashen/Desktop/poker_solver_worktrees/pr-merge-analysis` | `analysis/pr-merge-2026-05-27` | `aaa3c10` | PR #97 (open) `headRefOid` = `aaa3c1068d569a237b6f8de9d50c0898f6b320f5` — exact match. Branch fully captured upstream. Working tree clean. |

All three removed via clean `git worktree remove <path>` (no `--force`).

## Worktrees Skipped (1)

| Path | Reason | User action recommended |
|---|---|---|
| `/Users/ashen/Desktop/poker_solver_worktrees/dmg-v1-8-0-build` | `git worktree remove` refused: contains modified `Cargo.lock` (uncommitted). Detached HEAD at `8a9c8d2`. Per instructions, no `--force` used. | User to decide: (a) review Cargo.lock diff and either commit or discard, then `git worktree remove`; or (b) accept `--force` removal if lock-skew is known-stale. Build itself is done (.dmg artifact in main repo's `dist/`). |

---

## Branch Refs (Not Touched)

Per instructions, branches underlying removed worktrees are still present as refs:
- `pr-88-v1.8.0-release-notes-prep`
- `pr-92-resume-doc` (open PR #49 — keep)
- `analysis/pr-merge-2026-05-27` (open PR #97 — keep)

User may prune `pr-88-v1.8.0-release-notes-prep` manually if desired; the other two are tied to open PRs.

---

## Final Worktree State (7 total)

```
/Users/ashen/Desktop/poker_solver                                       [main]
/Users/ashen/Desktop/poker_solver_worktrees/dmg-v1-8-0-build            (detached, dirty — skipped)
/Users/ashen/Desktop/poker_solver_worktrees/fix-brown-buildable-ubuntu  [fix-brown-buildable-ubuntu]
/Users/ashen/Desktop/poker_solver_worktrees/fix-stale-mock-banner       [fix-stale-mock-banner]
/Users/ashen/Desktop/poker_solver_worktrees/pr-101-mock-disclosure      [docs/mock-mode-disclosure-v1-8-0]
/Users/ashen/Desktop/poker_solver_worktrees/pr-20-slow-markers          [pr-64-cross-platform-ci-matrix]
/Users/ashen/Desktop/poker_solver_worktrees/pr-93-tu-ablation           [pr-93-terminal-utility-ablation]
```

## Final Stash State (5 total)

```
stash@{0}: WIP on docs/readme-quickstart-fix-v1-8-0: 9c98064 docs: local PASS confirmation for PR #98 EV invariance gauntlet (#104)
stash@{1}: WIP on proposal/dcfr-alpha-guard-2026-05-27: 083a6b5 proposal: DCFR α-guard options (v1.8.1 candidate)
stash@{2}: WIP on pr-75-purge-rust-convention: a9a9029 WIP: convention purge (recovery)
stash@{3}: WIP on (no branch): ca8c7af docs: bump README version reference v1.5.1 → v1.6.0
stash@{4}: On main: pre-comprehensive-review-fix backup
```
