# Shared Tree Cleanup Report — 2026-05-23 (late)

**Triggering issue:** PR 44 rebuild agent committed `c09abe7` on `pr-44-dmg-packaging-fix` in the shared working tree at `/Users/ashen/Desktop/poker_solver/` instead of using a worktree. Per `feedback_no_concurrent_branch_ops.md`, this violates the "never branch-switch in the shared tree while other agents may write" rule.

**Constraints honored:**
- No feature branches deleted
- No stashes dropped
- No force pushes
- Ship worktree at `/tmp/ship-v1.7.0-66279/` left untouched (uncertain whether agent is active)

---

## Phase 1: v1.7.0 ship agent status

| Check | Result |
|---|---|
| `/tmp/ship-v1.7.0-66279/` exists | YES, valid git worktree (`.git` → `.git/worktrees/ship-v1.7.0-66279`) |
| Last file mtime (`Cargo.lock`) | 2026-05-23 17:38 (~30 min before cleanup ran at ~18:05) |
| Active claude/cargo/git process for ship | NONE found via `ps aux` |
| v1.7.0 tag exists | NO. Highest tag is `v1.6.0` |
| Recent commits on detached HEAD | None visible — HEAD is at `a99e470` (PR 39 commit) |
| Worktree status | Detached HEAD with uncommitted CHANGELOG, Cargo.lock, cfr_core/Cargo.toml, `__init__.py`, `pyproject.toml` |

**Verdict:** **AMBIGUOUS.** Files recently touched but no live process. Per orchestrator's explicit instruction ("DO NOT REMOVE that worktree if v1.7.0 ship still active"), and given ambiguity, the ship worktree was **preserved**. The ship agent appears to have stopped mid-flight without committing — work is incomplete (no tag, no commit, no push). **This needs orchestrator decision: resume vs. abandon.**

---

## Phase 2: Branch switch result

| Step | Before | After |
|---|---|---|
| Shared tree branch | `pr-44-dmg-packaging-fix` @ `c09abe7` | `main` @ `ca8c7af` |
| Origin main HEAD | `94007ca` (per audit doc expectation) | `ca8c7af` (advanced — README v1.5.1→v1.6.0 bump) |
| Uncommitted in shared tree | `Cargo.lock` modified | None (stashed) |
| Untracked files | ~120 untracked docs/scratch files | unchanged (kept) |

`ca8c7af docs: bump README version reference v1.5.1 → v1.6.0` was pulled fast-forward. The audit doc expected `94007ca`; main moved forward by 1 commit since the audit was written.

---

## Phase 3: Cargo.lock leak diagnosis

**Pre-stash diff (working tree vs `pr-44-dmg-packaging-fix` HEAD):**
```
 [[package]]
 name = "cfr_core"
-version = "0.5.0"
+version = "0.6.0"
```

**Cross-reference table:**

| Source | `Cargo.toml` cfr_core version | `Cargo.lock` cfr_core version |
|---|---|---|
| `origin/main` | **0.6.0** | **0.5.0** (skew) |
| `pr-44-dmg-packaging-fix` HEAD | 0.6.0 | 0.5.0 (inherits skew) |
| `pr-35c-paired-fix` HEAD | (not checked) | 0.6.0 |
| `pr-46-dcfr-panic-fix` HEAD | (not checked) | 0.6.0 |
| `pr-43-nash-wrapper` HEAD | (not checked) | 0.5.0 |
| `/tmp/ship-v1.7.0-66279` (working) | (not checked) | **0.7.0** |
| `/tmp/pr-35c-paired-60921` (working) | (not checked) | 0.6.0 |
| `/tmp/pr-35d-brown-quirk-61060` (working) | (not checked) | 0.5.0 |

**Verdict: Pre-existing skew on origin/main — NOT a cross-branch leak.**

- The 0.5.0 → 0.6.0 bump in the working tree's `Cargo.lock` is just `cargo` regenerating the lock to match `Cargo.toml` (which is already 0.6.0 on main and all live branches).
- The real bug is on `origin/main`: `Cargo.toml = 0.6.0` but `Cargo.lock = 0.5.0`. Any `cargo build` regenerates the lock to 0.6.0. **This was committed wrong somewhere upstream.**
- Suggested follow-up: fold a clean `Cargo.lock` regeneration commit into the next non-feature push to main (Type A bookkeeping fix). The stash holds the regenerated lock content for reference.

**Side observation:** `/tmp/ship-v1.7.0-66279/` shows cfr_core 0.7.0 — the ship agent had bumped the crate as part of v1.7.0 prep before stopping. Compatible with "incomplete ship" hypothesis from Phase 1.

---

## Phase 4: Worktrees purged

| Path | Status |
|---|---|
| `/private/tmp/cu-pr-4.5` | REMOVED |
| `/private/tmp/dcfr_panic_repro_66023` | REMOVED |
| `/private/tmp/poker_pr35` | REMOVED |
| `/private/tmp/pr-35c-paired-60921` | REMOVED |
| `/private/tmp/pr-35d-brown-quirk-61060` | REMOVED |
| `/private/tmp/ship-v1.7.0-66279` | **PRESERVED** (ambiguous status — see Phase 1) |
| `/private/tmp/v1_6_1_dryrun2_72023` | Already gone (no-op) |

`git worktree prune` ran cleanly (no orphan entries to purge).

All branches preserved — `git worktree remove --force` only deletes the working directory, not the branch it pointed to.

---

## Phase 5: Final state

**Shared tree:**
```
On branch main
Your branch is up to date with 'origin/main'.
HEAD: ca8c7af docs: bump README version reference v1.5.1 → v1.6.0
```

**Worktrees (17 total, all expected):**
- Shared tree on `main`
- Ship worktree (preserved, awaiting decision)
- 15 named worktrees under `~/Desktop/poker_solver_worktrees/` (untouched)

**Stash list:**
```
stash@{0}: On pr-44-dmg-packaging-fix: shared-tree-cleanup-2026-05-23-late: Cargo.lock cfr_core 0.5.0 -> 0.6.0
stash@{1}: On main: pre-comprehensive-review-fix backup
```

**Feature branches confirmed present:** `pr-35c-paired-fix`, `pr-35d-brown-quirk-doc`, `pr-43-nash-wrapper`, `pr-44-dmg-packaging-fix`, `pr-46-dcfr-panic-fix`, `pr-3.5-pushfold`, plus all PR 17–42 branches.

**Untracked files in shared tree:** ~120 docs/scratch files (PLAN.md, RELEASE_*.md, docs/*) — none touched by this cleanup.

---

## Verdict: **CLEAN WITH ONE DISCREPANCY**

- Phase 2 (branch switch): **CLEAN** — shared tree restored to main @ ca8c7af with no uncommitted changes.
- Phase 3 (Cargo.lock): **DIAGNOSED** — pre-existing skew on origin/main, not a cross-branch leak. Stash preserved for follow-up.
- Phase 4 (worktree purge): **CLEAN** — 5 leaked worktrees removed, 1 active ship worktree preserved.
- Phase 5 (audit): **CLEAN** — no unexpected state.

**Outstanding item flagged for orchestrator:**
1. **v1.7.0 ship worktree** at `/tmp/ship-v1.7.0-66279/` — agent appears stopped mid-flight (no live process, no commit, no tag, ~30 min since last file touch). Decide: resume vs. abandon. Worktree preserved.
2. **origin/main Cargo.lock skew** (cfr_core 0.6.0 in toml, 0.5.0 in lock). Fold a clean lock-regen commit into next push to main.
