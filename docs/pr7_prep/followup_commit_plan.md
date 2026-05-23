# PR 7 Follow-up Commit Plan: M1/M2/M3 Audit Patches

**Date:** 2026-05-22
**Branch of interest:** `pr-7-noambrown-diff`
**Reference commit:** PR 7 tip at `83d7b9c`
**Scope:** Determine whether M1/M2/M3 audit-remediation patches landed in the PR 7 commit, and if not, plan a follow-up commit on the same branch.

---

## 1. Hypothesis

PR 7 was committed at `83d7b9c` **without** the M1/M2/M3 patches produced by the audit-remediation agent. The patches almost certainly landed in the working tree (or staging area) **after** the commit object was sealed, which would explain why:

- The audit report (`audit_report.md`) describes the M1/M2/M3 fixes as "applied", but
- The PR 7 commit SHA does not reflect those file modifications, and
- The patch agent's progress report (`patch_progress.md`) timestamps the edits at or after the commit timestamp.

If confirmed, the patches exist on disk on `pr-7-noambrown-diff` (or were carried over via a branch switch) but are uncommitted. The fix is a small follow-up commit, **not** a rebase or amend.

If refuted (patches *were* in `83d7b9c`), no action is needed and this is a phantom concern.

---

## 2. Verification Commands

The orchestrator should run these **before** taking any write action. All commands assume the working tree is on `pr-7-noambrown-diff` with `integration` as the comparison base.

```bash
# M2 patch — noambrown_wrapper changes (likely seed plumbing or determinism fix)
git diff integration -- poker_solver/parity/noambrown_wrapper.py | head -30

# M1 patch — river_diff self-sanity test additions
git diff integration -- tests/test_river_diff_self_sanity.py | head -30

# M3 patch — Agent C prompt clarifications
git diff integration -- docs/pr7_prep/agent_c_prompt.md | head -10

# Full picture: what's on the branch vs integration, file list only
git diff integration --stat | head -40

# What's in 83d7b9c specifically (sanity-check commit contents)
git show --stat 83d7b9c | head -40

# What's uncommitted right now on this branch
git status --short
git diff HEAD --stat | head -20
```

**Decision rule:**
- If the three `git diff integration -- <file>` calls return non-empty output **and** `git show --stat 83d7b9c` does **not** list those three files → patches are on the branch but uncommitted (or in a later commit not yet pushed). Inspect `git log integration..HEAD --oneline` to confirm there is no intermediate commit already containing them.
- If `git status --short` shows the three files as modified/unstaged → Path A.
- If the three files are clean and `git diff integration -- <file>` is empty → Path B (lost in branch switch) **or** Path C (already in `83d7b9c`); disambiguate via `git show --stat 83d7b9c`.

---

## 3. Action Paths

### Path A: Patches in working tree on `pr-7-noambrown-diff`, not committed

Most likely outcome. Steps:

1. Confirm current branch: `git branch --show-current` → must be `pr-7-noambrown-diff`. If not, switch (no concurrent branch ops in shared tree — verify no other agents are writing).
2. Stage only the three patch files (avoid `git add -A`):
   ```bash
   git add poker_solver/parity/noambrown_wrapper.py \
           tests/test_river_diff_self_sanity.py \
           docs/pr7_prep/agent_c_prompt.md
   ```
3. Commit with message: `PR 7 follow-up: M1/M2/M3 audit patches` (PATCH version bump in any version file is optional and can be skipped to keep the commit minimal).
4. Push: `git push origin pr-7-noambrown-diff`.
5. The existing PR 7 will pick up the new commit automatically; no PR re-open required.

### Path B: Patches lost in a branch switch

If the verification shows the three files clean and `83d7b9c` does **not** contain them, the patches were likely discarded during a branch switch (or stashed and dropped — see memory rule on never `git stash drop` after a conflicted pop).

1. Recover patch content from the patch agent's report at `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/patch_progress.md` and/or `patch_verification.md`. Those files should contain enough diff snippets to reconstruct.
2. Re-apply each patch manually (Edit tool, not `patch(1)`, since the snippets may be summaries rather than unified diffs).
3. Run the same staged commit flow as Path A.
4. If reconstruction is uncertain, re-spawn the patch agent with the same prompt rather than guessing.

### Path C: PR 7 commit already included M1/M2/M3

If `git show --stat 83d7b9c` lists all three files with non-trivial line counts, the concern is phantom. No action. Document the verification result in `commit_pipeline_v2.md` so this question doesn't resurface.

---

## 4. Branch-Name and Downstream PR Follow-up

- If a follow-up commit lands on `pr-7-noambrown-diff`, the branch tip advances past `83d7b9c`. This is fine for PR 7 itself.
- **Do not** update PR 10a's base. PR 10a is based on `integration` (or a snapshot thereof), not on PR 7's branch tip. Re-basing PR 10a now would conflate the audit-patch follow-up with PR 10a's review scope.
- After PR 7 merges to `integration`, normal forward-merge into PR 10a's branch will pick up the patches.
- No tag or release note changes needed for a follow-up patch commit unless the PATCH version bump in Path A is taken — in which case update `CHANGELOG.md` (if present) with a one-line entry.

---

## 5. Constraints and Notes

- **Read-only plan**: this document records the decision tree only. No `git` writes, no edits, no commits performed as part of producing this plan.
- **No concurrent branch ops**: before any path is executed, confirm no other agent is writing to the shared working tree. Use `git worktree add` if parallel work is in flight.
- **Recommended path before verification**: Path A, based on the timestamp ordering hypothesis. Final selection requires the verification commands in Section 2.
