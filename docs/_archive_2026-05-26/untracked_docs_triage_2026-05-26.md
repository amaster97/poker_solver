# Untracked Docs Triage Report — 2026-05-26

## Summary

Triaged 2 `.local` artifacts and ~60 untracked dated `docs/*.md` drafts
in the main workspace. Results:

- **2 `.local` files**: deleted (both were superseded by tracked
  origin versions; no unique content).
- **34 dated drafts**: archived to PR branch
  `pr-95-untracked-docs-archive` under
  `docs/_archive_2026-05-26_session/` (copies; originals retained in
  main workspace for user to delete separately).
- **26 dated drafts**: KEPT in main workspace (today's 2026-05-26
  session work or referenced from tracked files).

## .local file decisions

| File | Decision | Rationale |
| --- | --- | --- |
| `docs/v1_6_1_engine_ship_plan_final.md.local` | DELETED | Older pre-PR-50 draft. Diff vs current (`docs/v1_6_1_engine_ship_plan_final.md`): origin has a 12-line "HOLD LIFTED" status banner the `.local` lacks. `.local` only adds one stale "PRE-STAGED" line. No unique preservable content. |
| `docs/v1_8_0_release_notes_DRAFT.md.local` | DELETED | Older pre-PR-50/PR-88 draft. Diff vs current: origin has 70+ lines of new content (Phases 1-4 + AVX2 status, engine + parity-wrapper fix summary, v1.7.2 fold rationale). `.local` only contains stale "TBD" placeholders and pre-supersession status lines. No unique preservable content. |

## Archive PR

- **Branch:** `pr-95-untracked-docs-archive`
- **Worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/pr-95-archive`
- **Archive path:** `docs/_archive_2026-05-26_session/`
- **Index doc:** `docs/_archive_2026-05-26_session/README.md` (per-file
  reasons; full table)

## Archive selection rules

A file was archived iff ALL of:

1. Date stamp 2026-05-23 or 2026-05-25 (older than 2 days);
2. Untracked on `origin/main` (loose draft, never committed);
3. Not referenced from any tracked main-line file
   (CHANGELOG/README/USAGE/DEVELOPER/CONTRIBUTING + any tracked
   `docs/**.md`).

## Files KEPT in main workspace

### Today's session (2026-05-26) — 18 files

Today's work, kept per "current session" rule:
- `backup_branch_audit_2026-05-26.md`
- `backup_integration_sync_2026-05-26.md`
- `cleanup_pr_79_report_2026-05-26.md`
- `dmg_packaging_hardening_pr_86_2026-05-26.md`
- `dmg_spawn_loop_rca_2026-05-26.md`
- `doc_code_bug_fixes_pr_83_2026-05-26.md`
- `doc_drift_cleanup_pr_85_2026-05-26.md`
- `golden_file_check_rca_2026-05-26.md`
- `golden_file_rebases_2026-05-26.md`
- `mypy_followup_pr_84_2026-05-26.md`
- `plan_prune_pr_89_2026-05-26.md`
- `pr_24_obsolescence_audit_2026-05-26.md`
- `surviving_worktree_audit_2026-05-26.md`
- `usage_path_verification_dev_docs_2026-05-26.md`
- `usage_path_verification_user_docs_2026-05-26.md`
- `v1_7_1_tag_decision_2026-05-26.md`
- `v1_8_0_release_notes_prep_2026-05-26.md`
- `v1_8_phase3_rebase_plan_2026-05-26.md`
- `v1_8_phase3_rerebase_2026-05-26.md`
- `v1_8_phase4_rebase_2026-05-26.md`
- `v1_8_phase4_rebase_diagnostic_2026-05-26.md`
- `v1_8_simd_perf_benchmark_2026-05-26.md`
- `worktree_housekeeping_2026-05-26.md`

(Several of these are referenced from tracked files — additional
preservation reason.)

### Referenced from tracked files — 2 files

- `PAUSE_RESUME_2026-05-25.md` (referenced from
  `docs/SIGNON_SUMMARY_2026-05-25.md` and `docs/persona_test_status_2026-05-25.md`).
- `river_parity_timeout_investigation_2026-05-23.md` (referenced from
  tracked release notes / ship hold review).

## 2026-05-24 STATUS docs note

All ten `STATUS_2026-05-24_*.md` files were either already TRACKED on
`origin/main` or referenced from tracked v1.8.0 release notes + v1.6.1
ship-hold review. None were untracked orphans, so none were
archive-candidates.

## Decision count

- DELETED: 2
- ARCHIVED (copied to PR branch): 34
- KEPT (today): ~18-23 (2026-05-26)
- KEPT (referenced): 2 (`PAUSE_RESUME_2026-05-25.md`,
  `river_parity_timeout_investigation_2026-05-23.md`)

## Workspace-root release orphans (RELEASE_NOTES/HEADLINES/CHECKLIST_2026-05-23.md)

The session-start git status listed three workspace-root orphans:
`RELEASE_NOTES_2026-05-23.md`, `RELEASE_HEADLINES_2026-05-23.md`,
`RELEASE_CHECKLIST_2026-05-23.md`. These NO LONGER EXIST in the main
workspace at triage time (2026-05-26 mid-morning) — they were already
cleaned by a prior session pass. No action required.

## Non-archive untracked items still in main workspace

These were OUT OF SCOPE for this triage (no date stamp) but the user
may want to address them later:

- Many `pr_NN_prep/` directories (`pr8_prep/`, `pr9_prep/`,
  `pr10b_prep/`, `pr11_prep/`, `pr13_prep/`, `pr15_prep/`, `pr16_prep/`,
  `pr18_prep/`, `pr8b_prep/`) — prep working dirs from earlier PRs.
- Many undated `pr_NN_*` audit/report files (`pr44_*`, `pr_23_*`,
  `pr_38_*`, `pr_39_*`, `pr_41_*`, `pr_42_*`, `pr_46_*`, `pr_50_*`,
  etc.).
- `acceptance_test_reframe.{md,patch}`, `action_menu_*.md`,
  `r11_*.md`, `terminal_utility_audit_{brown,python,rust_*}.md`, etc.
- Workspace-root: `PLAN.md` (intentionally untracked per project
  policy).
- Untracked code: `crates/cfr_core/examples/`,
  `scripts/cleanup_pr_branches.sh`, `scripts/ship_v1_6_1_engine.sh`,
  `tests/test_aa_vs_aa_root_indifference.py`,
  `tests/test_minimal_nash_fixture.py`.

## Next-step recommendations for the user

1. After the archive PR (`#TBD`) merges, deleting the 34 originals from
   main workspace is safe (their archived copies are committed on
   `origin/main`).
2. The undated `pr_NN_*` files and `pr_NN_prep/` dirs need a separate
   triage pass — most are likely stale but they don't fit the
   date-based archive criterion used here.
3. Consider committing PLAN.md if its working state should be
   preserved (currently untracked).
