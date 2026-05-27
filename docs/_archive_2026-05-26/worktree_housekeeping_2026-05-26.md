# Worktree & Git Housekeeping Report
**Date:** 2026-05-26
**Context:** Post-crash cleanup of stale git state in `poker_solver` repo
**Working dir:** `/Users/ashen/Desktop/poker_solver`

---

## Summary of Actions Executed (Autonomous)

| Action | Result |
|---|---|
| `git worktree prune -v` | **19 stale `/private/tmp/` entries removed.** Listed below. |
| `rm .git/AUTO_MERGE` | **Skipped — file did not exist.** Either prior cleanup or never existed in this workspace. No action needed. |
| `git worktree remove .../pr-78-dmg-fix` | **Already gone.** A prior step (likely `worktree prune` since the directory was on `/Users/ashen/Desktop/...`, not `/private/tmp/`, but it was no longer registered) removed the worktree dir. The PR-#42-merged branch `pr-78-dmg-freeze-support-fix` still exists locally. |

### Pruned worktree entries (19)
All under `/private/tmp/...` — wiped on reboot, refs were dangling:
```
worktrees/bisect-b-engine-75843
worktrees/pr-51-dcfr-vector-panic-31998
worktrees/matched-config-10360
worktrees/signon-refresh-79976
worktrees/pr20-fix-75881
worktrees/v1.8-phase4-57428
worktrees/pr50
worktrees/bundle
worktrees/gate4-run-17042
worktrees/pr19-rebase-77870
worktrees/phase2-rebase-81732
worktrees/pr23
worktrees/bisect-c-bundle-75843
worktrees/bisect-a-main-75843
worktrees/main
worktrees/pr-55-extend-57825
worktrees/pr-52-suit-encoding-37531
worktrees/phase3-rebase-fresh
worktrees/private-mirror-comprehensive-59887
```

### Note on `.git/AUTO_MERGE` and SHA `26d7656c`
The task brief said to verify `git rev-parse 26d7656c` errors before deleting. Actual finding:
- `git rev-parse 26d7656c` → resolves to `26d7656c1462cd5e247d6713679f887087cb3fb1`
- `git cat-file -t 26d7656c...` → **`tree`** (not a commit!)
- `git cat-file commit 26d7656c...` → `fatal: ... bad file`
So the SHA is a tree-object hash, not a commit. The brief's premise that "the SHA doesn't exist" is technically false (object exists), but as a *commit* it doesn't. Moot either way: `.git/AUTO_MERGE` was already absent.

---

## Surviving Desktop Worktrees — Audit Results

Final state: **18 active worktrees** at `/Users/ashen/Desktop/poker_solver_worktrees/` + main at `/Users/ashen/Desktop/poker_solver`.

### Recommendation matrix

| Worktree | Branch | Status | Ahead/Behind origin/main | Open PR? | Recommendation |
|---|---|---|---|---|---|
| `cli-ergonomics` | `pr-39-cli-ergonomics` | clean | +1 / -47 | NO (PR 39 merged as #39 unrelated work) | **REVIEW**: orphan — branch may already be superseded; user verify before kill |
| `persona-corrections` | `pr-38-persona-corrections` | 2 untracked docs | +2 / -47 | NO | **REVIEW**: 2 untracked doc files, branch ahead of main; consider preserving docs then kill |
| `phase2b-audit-revision` | `pr-41-phase2b-audit-revision` | clean | +3 / -47 | NO | **REVIEW**: 3 commits ahead, no open PR; verify content not needed before kill |
| `pr-17-plan-c` | `pr-17-plan-c-dense-slabs` | 1 untracked dir (`docs/pr17_prep/`) | +1 / -79 | NO | **REVIEW**: WIP-parked branch (commit msg says "superseded by Option A v1.3.2"); safe-ish to ARCHIVE-COMMITS-AND-KILL |
| `pr-23-p0-off-by-one` | `pr-34-p0-off-by-one` | 1 untracked dir (`references/`) | +1 / -51 | NO | **REVIEW**: PR 34 P0 fix; verify the fix landed elsewhere (e.g. via PR 46) before kill |
| `pr-24a-gui-rvr-slider` | `feature/pr-24a-gui-rvr-slider` | (not audited; pre-existing) | +4 / -51 | NO | **REVIEW**: pre-existing, not in brief |
| `pr-24b-gui-nodelock-asym` | `feature/pr-24b-gui-nodelock-asym` | (not audited; pre-existing) | unknown | NO | **REVIEW**: pre-existing, not in brief |
| `pr-33-phase3-rebase` | `pr-33-phase3-rebase-2026-05-26` | clean | (Phase 3 SIMD rebase) | NO (PR 33 in queue) | **KEEP**: Phase 3 rebase in flight |
| `pr-35-canonicalization` | `pr-35-canonicalization` | (not audited; pre-existing) | +1 / -51 | NO | **REVIEW**: pre-existing |
| `pr-40-acceptance-test-fix` | `pr-40-acceptance-test-fix` | (not audited; pre-existing) | +1 / -47 | NO | **REVIEW**: pre-existing |
| `pr-79-cleanup` | `pr-79-lint-format-deps-cleanup` | clean | head=6526fb0 (lint/clippy/format/deps green-up) | NO (newly built by cleanup agent) | **KEEP**: Cleanup-PR agent's worktree; agent appears to have completed work |
| `pr-81-doc-drift` | `pr-81-doc-drift-cleanup` | clean (at origin/main) | 0 / 0 | NO (doc-drift agent worktree) | **KEEP**: Doc-drift cleanup agent's worktree |
| `python-delegate` | `pr-33-python-delegate` | (not audited; pre-existing) | +1 / -51 | NO | **REVIEW**: pre-existing |
| `river-parity-fix` | `pr-25-river-parity-test-fix` | (not audited; pre-existing) | +2 / -71 | NO | **REVIEW**: pre-existing |
| `ship-v1.6.0` | `ship-v1.6.0` | (not audited; pre-existing) | 0 / -36 | NO | **REVIEW**: behind main, no work ahead — likely safe to ARCHIVE-AND-KILL |
| `spec-corrections` | `pr-29-persona-spec-corrections` | (not audited; pre-existing) | unknown | NO | **REVIEW**: pre-existing |
| `v1-7-0-nash-wrapper` | `pr-43-nash-wrapper` | (not audited; pre-existing) | +2 / -47 | NO | **REVIEW**: pre-existing |
| `w3-5-reversal` | `pr-42-w3-5-reversal` | (not audited; pre-existing) | unknown | NO | **REVIEW**: pre-existing |

### User-gated kill candidates (high confidence orphan, no PR on origin)
Per brief, **DO NOT KILL autonomously**. User decision required:
1. `cli-ergonomics` (pr-39-cli-ergonomics)
2. `persona-corrections` (pr-38-persona-corrections) — preserve 2 untracked docs first
3. `phase2b-audit-revision` (pr-41-phase2b-audit-revision)
4. `pr-17-plan-c` (pr-17-plan-c-dense-slabs) — explicitly parked by author
5. `pr-23-p0-off-by-one` (pr-34-p0-off-by-one) — verify PR 46 superseded before kill

### Currently-open PRs on origin (from `gh pr list`)
| # | Branch | Title |
|---|---|---|
| 38 | pr-76-exploitative-play | PR 76: exploitative play (BR vs fixed opponent) |
| 36 | pr-77-range-fractional-spec | PR 77: spec for Range fractional-frequency refactor |
| 34 | pr-74-v1.8-release-notes-prep | PR 74: v1.8.0 release notes + CHANGELOG draft (HOLD) |
| 33 | pr-70-v1.8-phase3-update-strategy-sum-simd | PR 70: v1.8 Phase 3 — update_strategy_sum SIMD |
| 32 | pr-71-v1.8-phase4-compute-strategy-simd | PR 71: v1.8 Phase 4 — compute_strategy SIMD |
| 24 | pr-69-docs-refresh-v1.7.1-v1.8 | docs: refresh public docs for v1.7.1/v1.7.2/v1.8 |
| 20 | pr-64-cross-platform-ci-matrix | feat(ci): cross-platform CI matrix for v1.8 prep |

None of the 5 user-gated kill candidates have open PRs upstream.

---

## Local Branches — Merged-Into-Main (Safe-Delete Candidates)

`git branch --merged main` returned 15 branches (excluding `* main` and worktree-checked-out branches marked `+`):

```
pr-10a-ui-mock-first
pr-10a.5-conformance
pr-11-library-and-packaging
pr-18-stage-c1-numpy-slab
pr-3-hunl-tree
pr-3.5-pushfold
pr-4-card-abstraction
pr-4.5-audit-debt-sweep
pr-5-hunl-postflop-solve
pr-6-rust-hunl-port
pr-7-noambrown-diff
ship-v1.4.2
ship-v1.4.3
ship-v1.5.0
ship-v1.5.1
```

**Recommendation:** These are merged into `main` and can be deleted with `git branch -d <name>` (safe — `-d` not `-D`). Per the brief, **not deleted automatically**. Total local-branch count: **86**.

### Branch deletion command (user-runnable)
```bash
for b in pr-10a-ui-mock-first pr-10a.5-conformance pr-11-library-and-packaging \
         pr-18-stage-c1-numpy-slab pr-3-hunl-tree pr-3.5-pushfold \
         pr-4-card-abstraction pr-4.5-audit-debt-sweep pr-5-hunl-postflop-solve \
         pr-6-rust-hunl-port pr-7-noambrown-diff \
         ship-v1.4.2 ship-v1.4.3 ship-v1.5.0 ship-v1.5.1; do
  git branch -d "$b"
done
```

---

## Workspace-Root Untracked Files

| File / Dir | Recommendation | Reason |
|---|---|---|
| `PLAN.md` (102 KB) | **DO NOT TOUCH** | Active spec per user rule |
| `RELEASE_NOTES_2026-05-23.md` | **ARCHIVE** to `docs/_archive_2026-05-23/` | Never shipped; 3 days stale |
| `RELEASE_HEADLINES_2026-05-23.md` | **ARCHIVE** to `docs/_archive_2026-05-23/` | Same |
| `RELEASE_CHECKLIST_2026-05-23.md` | **ARCHIVE** to `docs/_archive_2026-05-23/` | Same |
| `.merge_logs/` | **ARCHIVE** to `docs/_archive_2026-05-23/.merge_logs/` | Contains 1 transient file: `automerge_20260525_223022.log` (just `"Auto-merge session 2026-05-25"`, 30 bytes) |

### Suggested move commands (user-runnable; DO NOT autonomously execute per brief)
```bash
mkdir -p docs/_archive_2026-05-23
mv RELEASE_NOTES_2026-05-23.md RELEASE_HEADLINES_2026-05-23.md RELEASE_CHECKLIST_2026-05-23.md docs/_archive_2026-05-23/
mv .merge_logs docs/_archive_2026-05-23/
```

---

## `docs/` Untracked-File Audit

**Total files in `docs/`:** 220
**Untracked entries (per `git status --porcelain`):** 220
**Breakdown:**

### Category 1 — `*_2026-05-23*` (34 files): archive candidates
Yesterday's drafts; releases never shipped on those names. Likely safe to archive.
```
archived_claims_2026-05-23.md
brown_apples_to_apples_2026-05-23.md
burst_summary_2026-05-23.md
comprehensive_review_2026-05-23-final.md
comprehensive_review_2026-05-23-late.md
comprehensive_review_2026-05-23-night.md
comprehensive_review_2026-05-23.md
dcfr_perf_regression_bisection_2026-05-23.md
doc_orphan_audit_2026-05-23.md
doc_walkback_3rd_reversal_2026-05-23.md
faq_verification_2026-05-23.md
final_consistency_audit_2026-05-23.md
heuristic_judgement_audit_2026-05-23.md
integration_catchup_report_2026-05-23.md
integration_cleanup_report_2026-05-23.md
oss_competitor_comparison_2026-05-23.md
poker_spots_audit_2026-05-23.md
poker_spots_audit_CORRECTED_2026-05-23.md
poker_spots_reverification_2026-05-23.md
PR_REVIEW_PREP_2026-05-23.md
private_mirror_sync_2026-05-23-late.md
pytest_pyenv_arch_quirk_2026-05-23.md
README_proposed_update_2026-05-23.md
reference_validation_2026-05-23.md
repo_metadata_polish_2026-05-23.md
retag_execution_report_2026-05-23.md
river_parity_timeout_investigation_2026-05-23.md
shared_tree_cleanup_2026-05-23-late.md
stash_recovery_2026-05-23.md
state_consistency_audit_2026-05-23-late.md
state_verification_2026-05-23-late.md
task_list_review_2026-05-23-late.md
tmp_cleanup_final_2026-05-23.md
```

Plus dated SESSION/STATUS files (also untracked, but with `SESSION_` or `STATUS_` prefix — kept in their own group):
- `SESSION_AUDIT_TRAIL_2026-05-23.md`, `session_shipped_2026-05-23.md`, `session_state_2026-05-23_evening.md`, `STATUS_2026-05-23_*.md` (4 files), `test_wave_2026-05-23_integration.md`, `wake_up_brief_2026-05-23.md`, `WELCOME_BACK_USER_2026-05-23.md`

### Category 2 — `*_2026-05-24*` (0 files in untracked, ~9 in tracked)
All committed already. Not in cleanup scope.

### Category 3 — `*_2026-05-25*` (3 untracked files): recent, load-bearing — KEEP
```
PAUSE_RESUME_2026-05-25.md
outstanding_queue_2026-05-25.md
v1_7_2_ci_hardening_audit_2026-05-25.md
```
Plus dated SESSION/STATUS files at 05-25 are still load-bearing for current state.

### Category 4 — non-dated `.md` files (~165): manual review required
Mix of:
- **`UPPERCASE_*.md`** at root of `docs/` (8 files: `DOCS_NAV_MAP.md`, `FINAL_PRE_SIGNON_AUDIT.md`, `PRE_SIGNON_FAQ.md`, `PR_CONFLICT_RESOLUTION.md`, `SIGNON_CHECKLIST.md`, `USER_GREETING.md`, etc.) — operational guidance docs, probably KEEP
- **`leg*_v*_ship_plan.md` / `leg*_v*_ship_report.md`** (~22 files for legs 6, 9, 11–22) — historical ship records, probably KEEP (or archive en masse)
- **`pr44_*.md`** (4 files) and **`pr_*_report.md`** / **`pr_*_audit.md`** (~30 files) — PR-specific reports, mixed value
- **investigation/audit `.md` files** (~30 files): topic-named drafts like `a83_deep_cap_root_cause_investigation.md`, `acceptance_test_reframe.md`, `kk_fold_inversion_diagnosis.md`, etc.

### Category 5 — Untracked directories (10):
```
docs/persona_test_results/   # likely keep — test artifacts
docs/pr10b_prep/             # prep dirs; mostly historical
docs/pr11_prep/
docs/pr13_prep/
docs/pr15_prep/
docs/pr16_prep/
docs/pr18_prep/
docs/pr8_prep/
docs/pr8b_prep/
docs/pr9_prep/
docs/pr_proposals/           # appears mid-list — partial
```
The `pr*_prep/` dirs map to long-merged PRs; candidates for batch archive.

**Per brief: do NOT autonomously move/delete. Doc-drift agent owns this.**

---

## Key Findings

1. **`.git/AUTO_MERGE` never existed in this workspace** — the brief's premise (stale ref pointing to non-existent SHA) didn't match reality. No-op.
2. **SHA `26d7656c` resolves to a tree object, not a commit.** Brief's "non-existent SHA" was almost right — it doesn't exist as a *commit*.
3. **`pr-78-dmg-fix` worktree was already gone** by the time `worktree remove` was attempted. PR #42 merge probably auto-cleaned it (or it was wiped on reboot since the symlink lived under `/Users/ashen/Desktop/poker_solver_worktrees/` but its `.git/worktrees/` admin file pointed elsewhere). Either way: clean.
4. **2 new worktrees observed not in the brief:** `pr-79-cleanup` (lint/clippy/format/deps cleanup agent, commit `6526fb0`) and `pr-81-doc-drift` (doc-drift cleanup agent at origin/main). Both KEEP — they're agent-managed.
5. **86 local branches total**, of which **15 are merged into main and safe to `-d`-delete.**
6. **220 untracked entries in `docs/`** — bulk archive candidate (34 dated 05-23 + 10 dirs + ~22 historical `leg*` ship docs). Doc-drift agent owns.
7. **4 untracked root-level items** (`.merge_logs/`, 3 `RELEASE_*_2026-05-23.md` files) can be batch-archived to `docs/_archive_2026-05-23/`.

---

## What Was NOT Done (User Decision Required)

- 5 orphan worktrees per brief: `cli-ergonomics`, `persona-corrections`, `phase2b-audit-revision`, `pr-17-plan-c`, `pr-23-p0-off-by-one` — recommend KILL per audit, but per brief held for user review
- Pre-existing worktrees not in brief: `pr-24a-gui-rvr-slider`, `pr-24b-gui-nodelock-asym`, `pr-35-canonicalization`, `pr-40-acceptance-test-fix`, `python-delegate`, `river-parity-fix`, `ship-v1.6.0`, `spec-corrections`, `v1-7-0-nash-wrapper`, `w3-5-reversal` — not audited; user discretion
- 15 merged-into-main branches: listed, not deleted
- 4 root-level untracked files: not archived
- ~220 untracked docs files: not touched (doc-drift agent's job)
