# Archive — 2026-05-26 Session Cleanup

This archive captures 34 unreferenced dated-session draft documents that
accumulated in `docs/` between 2026-05-23 and 2026-05-25 and were never
linked from any tracked main-line document. They are preserved here for
historical reference; the originals remained in the main workspace at
archive time and may be deleted separately by the user.

## Why these were archived

- **Date stamp ≥ 3 days old** (2026-05-23, 2026-05-25); not part of the
  current 2026-05-26 working session.
- **Unreferenced** by any tracked file on `origin/main` (CHANGELOG,
  README, USAGE, DEVELOPER, CONTRIBUTING, or any tracked `docs/*.md`).
- **Not load-bearing** for any active workflow — these are intermediate
  session notes, audit drafts, review snapshots, status reports, and
  cleanup logs from prior sessions.

## What was NOT archived

- All `*_2026-05-26.md` docs (current session's work) — kept in main
  workspace.
- All `*_2026-05-24*.md` STATUS docs — referenced from tracked v1.8.0
  release notes or v1.6.1 ship-hold review.
- `PAUSE_RESUME_2026-05-25.md`, `river_parity_timeout_investigation_2026-05-23.md`
  — referenced from tracked docs.
- `WELCOME_BACK_USER_2026-05-23.md`, `SIGNON_SUMMARY_2026-05-25.md`,
  `persona_test_status_2026-05-25.md` — already tracked on `origin/main`.

## Archived files

### 2026-05-23 — 32 files

| Original path | One-line reason |
| --- | --- |
| `docs/archived_claims_2026-05-23.md` | Pruning-sweep ledger of refuted claims; superseded by post-PR-50 doc baseline. |
| `docs/brown_apples_to_apples_2026-05-23.md` | Mid-session Brown parity experiment notes; superseded by `a83_validation_2026-05-26.md`. |
| `docs/burst_summary_2026-05-23.md` | End-of-day session burst summary; superseded by later release notes. |
| `docs/comprehensive_review_2026-05-23.md` | Mid-session comprehensive review; superseded by `-late`, `-night`, `-final` variants. |
| `docs/comprehensive_review_2026-05-23-late.md` | Late-evening comprehensive review; intermediate snapshot. |
| `docs/comprehensive_review_2026-05-23-night.md` | Night comprehensive review; intermediate snapshot. |
| `docs/comprehensive_review_2026-05-23-final.md` | Final 2026-05-23 review; superseded by 2026-05-26 release artifacts. |
| `docs/dcfr_perf_regression_bisection_2026-05-23.md` | DCFR perf bisection v1.3 -> v1.4.1; investigation closed pre-v1.8.0. |
| `docs/doc_orphan_audit_2026-05-23.md` | Earlier orphan audit; superseded by this archive operation. |
| `docs/doc_walkback_3rd_reversal_2026-05-23.md` | Doc walk-back snapshot during repeated re-verification reversals. |
| `docs/faq_verification_2026-05-23.md` | FAQ verification pass; superseded by `docs/PRE_SIGNON_FAQ.md` (newer untracked doc). |
| `docs/final_consistency_audit_2026-05-23.md` | Session-close consistency audit; superseded by later audits. |
| `docs/heuristic_judgement_audit_2026-05-23.md` | Heuristic judgement audit log; superseded after persona-test framework update. |
| `docs/integration_catchup_report_2026-05-23.md` | Late integration catch-up; superseded by 2026-05-26 integration syncs. |
| `docs/integration_cleanup_report_2026-05-23.md` | Mid-session integration cleanup; superseded by `cleanup_pr_79_report_2026-05-26.md`. |
| `docs/oss_competitor_comparison_2026-05-23.md` | OSS solver landscape comparison; informational, no main-line reference. |
| `docs/poker_spots_audit_2026-05-23.md` | Poker-spots heuristic audit (original). |
| `docs/poker_spots_audit_CORRECTED_2026-05-23.md` | Poker-spots audit (corrected pass); both superseded by tracked persona-test results. |
| `docs/poker_spots_reverification_2026-05-23.md` | Poker-spots re-verification pass; superseded. |
| `docs/PR_REVIEW_PREP_2026-05-23.md` | PR review prep notes; review window closed. |
| `docs/private_mirror_sync_2026-05-23-late.md` | Private mirror sync log; operational, transient. |
| `docs/pytest_pyenv_arch_quirk_2026-05-23.md` | Pytest pyenv arch-mismatch diagnosis; resolved at session level. |
| `docs/reference_validation_2026-05-23.md` | Reference-citation validation for README/aggregator explainer. |
| `docs/repo_metadata_polish_2026-05-23.md` | Repo metadata polish notes; merged into 2026-05-26 follow-ups. |
| `docs/retag_execution_report_2026-05-23.md` | Re-tag execution report; superseded by v1.8.0 release process. |
| `docs/shared_tree_cleanup_2026-05-23-late.md` | Shared tree cleanup log; operational, transient. |
| `docs/stash_recovery_2026-05-23.md` | Stash recovery operation log; one-shot. |
| `docs/state_consistency_audit_2026-05-23-late.md` | State consistency audit; superseded by `terminal_utility_audit_2026-05-26.md` etc. |
| `docs/state_verification_2026-05-23-late.md` | v1.4.0 burst state verification; superseded by v1.8.0 baseline. |
| `docs/task_list_review_2026-05-23-late.md` | Task list review; superseded by PLAN.md cycle. |
| `docs/test_wave_2026-05-23_integration.md` | Test-wave verification post-integration; transient. |
| `docs/tmp_cleanup_final_2026-05-23.md` | `/tmp/` cleanup sweep log; operational, transient. |

### 2026-05-25 — 2 files

| Original path | One-line reason |
| --- | --- |
| `docs/outstanding_queue_2026-05-25.md` | Pre-pause outstanding queue snapshot; superseded by PLAN.md + `PAUSE_RESUME_2026-05-25.md`. |
| `docs/v1_7_2_ci_hardening_audit_2026-05-25.md` | v1.7.2 CI hardening pre-merge audit; v1.7.2 folded into v1.8.0 per tag-decision doc. |

## Archive policy

- Originals were COPIED (not moved) from
  `/Users/ashen/Desktop/poker_solver/docs/` into this archive at
  2026-05-26. The main workspace retains the originals; the user may
  delete them separately when convenient.
- The HARD RULE for this PR was: never delete files from the main
  workspace from an automated agent (precedent: a prior agent was
  killed for doing so).
- See `docs/untracked_docs_triage_2026-05-26.md` (main workspace) for
  the full triage report and per-file decision count.
