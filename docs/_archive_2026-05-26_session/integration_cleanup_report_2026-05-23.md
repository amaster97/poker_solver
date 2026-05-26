# Integration Cleanup Report — 2026-05-23

**Operation:** strip internal files from public `origin/integration` history (force-push), keep merge structure intact.
**Authorized by:** orchestrator model: "public integration = private integration with private things stripped out."
**Workspace:** `/tmp/poker_solver_integration_cleanup/integration_clean` (fresh clone, isolated from shared working tree).
**Tool:** `git-filter-repo` 2.47.0 (installed via `pip3 install --break-system-packages git-filter-repo` → `/Users/ashen/.local/bin/git-filter-repo`).

---

## TL;DR

- Public `origin/integration` rewritten from `b6936b9` → `bc362e9` (force-pushed; 14 merge commits preserved).
- 419 → 136 files in HEAD tree (~283 internal-planning files purged from history).
- Repo size dropped from 9.6M → 3.1M (~70% reduction).
- Public `origin/main` unchanged at `166d2b8`.
- Private mirror (`backup/integration`) unchanged at `2878bda` — full internal content retained.

---

## Pre-flight checks

| Check | Result |
|---|---|
| Public origin URL | `https://github.com/amaster97/poker_solver.git` |
| Private mirror URL | `https://github.com/amaster97/poker_solver_private.git` |
| URLs distinct | **YES** — safe to proceed |
| Workspace | `/tmp/poker_solver_integration_cleanup/integration_clean` (not the shared tree) |
| Branches in scope | `integration` only |
| Branches NOT touched | `main`, all tags, all PR-* branches on origin; entire private mirror |

---

## Strip list (paths-to-remove.txt)

Full file path: `/tmp/poker_solver_integration_cleanup/paths-to-remove.txt`

```
# === Root-level planning / status / session / handoff artifacts ===
PLAN.md
STATUS.md
SESSION_END_FINAL.md
glob:STATUS*.md
glob:SESSION_*.md
glob:V*_GA_CLOSE.md
glob:V*_MILESTONE*.md
glob:wake_up_*.md
glob:*_HANDOFF.md
V1_GA_CLOSE.md

# === docs/ — date-stamped session / status / wake-up / handoff artifacts ===
docs/SESSION_END_REPORT.md
docs/SESSION_HANDOFF.md
docs/V1_GA_MILESTONE_HIT.md
docs/wake_up_brief.md
docs/wake_up_brief_2026-05-22.md
docs/session_pause_2026-05-21.md
docs/session_retrospective_2026-05-22.md
docs/morning_briefing_check.md
docs/next_session_plan.md
docs/final_state_check_2026-05-22.md
docs/INDEX_2026-05-22.md
docs/ONE_PAGE_SUMMARY.md
docs/snapshot_in_flight.md
docs/snapshot_post_pr7_pr4_5.md
docs/git_state_post_recovery.md

# === Autonomous / planning logs ===
docs/autonomous_log.md
docs/autonomous_burst_release_plan.md
docs/autonomous_decisions_2026-05-22.md
docs/plan_log_final_sweep.md
docs/plan_index_final_alignment.md
docs/planning_preservation_decision.md
docs/plan_md_post_pr11_edit_recipe.md
docs/plan_md_post_pr45_edit_recipe.md
glob:docs/plan_log_*.md

# === Audits / reviews / state verifications ===
docs/open_items_audit_2026-05-22.md
glob:docs/open_items_audit_*.md
docs/audit_followup_backlog.md
docs/audit_prompt_maintenance_check.md
docs/branch_name_drift_audit.md
docs/branch_name_final_check.md
docs/cargo_lock_audit.md
docs/changelog_accuracy_check.md
docs/changelog_audit_v0_6_1.md
docs/cross_doc_consistency_check.md
docs/cross_doc_consistency_v2.md
docs/cross_pr_cleanup_plan.md
docs/cross_pr_coordination.md
docs/doc_inventory.md
docs/doc_retention_policy.md
docs/effort_estimate_revalidation.md
docs/equity_precision_branch_investigation.md
docs/card_removal_investigation.md
docs/memory_audit_2026-05-22.md
docs/memory_consistency_report.md
docs/per_pr_diff_stats.md
docs/per_pr_doc_inventory.md
docs/perf_bench_scaffolds_review.md
docs/readme_accuracy_check.md
docs/reference_repo_audit.md
docs/repo_audit.md
docs/roadmap_status_2026-05-22.md
docs/routing_check_2026-05-23.md
docs/spec_consistency_review.md
docs/spec_consistency_review_v2.md
docs/split_script_smoke.md
docs/test_coverage_post_pr5.md
docs/usage_dev_proofread_report.md
docs/v04_bump_consistency_sweep.md
docs/v05_version_consistency.md
docs/zombie_pytest_cleanup.md
docs/prune_report_2026-05-23.md
glob:docs/comprehensive_review*.md
glob:docs/state_verification*.md
glob:docs/river_parity_timeout_investigation*.md
glob:docs/retag_execution_report*.md
glob:docs/integration_cleanup*.md
glob:docs/leg*_*.md
docs/integration_sequencing_strategy.md
docs/integration_test_scaffolds.md
docs/integration_test_scaffolds_review.md
docs/pr_prep_state_check.md
docs/midsession_hygiene_check.md
docs/post_integration_verification_protocol.md
docs/post_sync_consistency_check.md
docs/session_shipped_2026-05-23.md
docs/stash_recovery_2026-05-23.md
docs/strip_and_soften_edits.md
docs/final_consistency_audit.md
docs/pr_branch_deeper_audit.md
docs/public_doc_content_audit.md

# === Cutover / option_c (private deploy strategy) / sync runbooks ===
docs/cutover_dry_run_preview.md
docs/cutover_execute_now.md
docs/cutover_execution_runbook.md
docs/cutover_preflight_checklist.md
docs/option_c_health_check.md
docs/option_c_hooks_upgrade.md
docs/sync_repos_runbook.md
docs/branch_split_runbook.md
docs/public_cleanup_advisory.md

# === Recipe / release-recipe (internal release-flow) ===
docs/v0.5.0_release_recipe.md
docs/v1.0.0_release_recipe.md
docs/publish_workflow.md

# === Per-PR prep directories ===
glob:docs/pr*_prep/*
glob:docs/pr*_prep/**
glob:docs/pr*_audit_debt/*
glob:docs/pr*_audit_debt/**
glob:docs/persona_test_results/**
glob:docs/persona_test_results/*
glob:docs/pr_proposals/**
glob:docs/pr_proposals/*
(per-PR explicit globs for pr10_prep ... pr22_prep, pr3_prep, pr3_5_prep,
 pr4_prep, pr4_5_audit_debt, pr5_prep ... pr9_prep, pr8b_prep)
docs/pr_launch_runbook.md
```

### Files retained in `docs/` (post-cleanup, all 12 user-facing):

```
docs/architecture.md
docs/competitor_landscape.md
docs/pushfold_v1_generation_notes.md
docs/release_notes_v0.3.1.md
docs/release_notes_v0.3.md
docs/release_notes_v0.5.0.md
docs/release_notes_v0.5.1.md
docs/release_notes_v0.5.2.md
docs/release_notes_v0.6.0.md
docs/release_notes_v1.0.0.md
docs/roadmap_diagram.md
docs/rust_orientation.md
```

Root files retained: `CHANGELOG.md`, `CONTRIBUTING.md`, `DEVELOPER.md`, `README.md`, `USAGE.md`, `LICENSE`, `pyproject.toml`, `Cargo.toml`, `Cargo.lock`.

---

## Before / after metrics

| Metric | Before | After | Delta |
|---|---|---|---|
| Integration HEAD SHA | `b6936b9` | `bc362e9` | rewritten |
| Commit count (`git log integration`) | 66 | 57 | -9 (commits that touched only stripped paths became empty and were dropped) |
| Merge commits | 14* (see note) | 14 | preserved |
| Files in HEAD tree | 419 | 136 | -283 |
| Repo size (.git) | 2.7M | 1.0M (filter-repo workspace), 896K (fresh clone) | -65% to -67% |
| Repo size (working tree + .git) | 9.6M | 3.1M (filter-repo), 2.9M (fresh clone) | -70% |

*Note: `git log --merges --oneline | head -20` showed 14 lines, but the original integration tip log included some PR 8/PR 9 commits that were direct linear (not merge) commits. Original merge graph for integration ≤ b6936b9 was 14 actual merge commits, all of which are preserved post-rewrite.

---

## Verification: internal paths gone from all history

```
$ git -C integration_clean log --all --pretty=format: --name-only | sort -u \
    | grep -E '(PLAN\.md|pr.*_prep|autonomous_log|SESSION_|wake_up|STATUS|HANDOFF|state_verification|comprehensive_review|persona_test_results|pr_proposals|leg[0-9]+_|autonomous_burst|midsession_|cutover_|option_c|sync_repos_runbook|publish_workflow|release_recipe|prune_report|public_cleanup_advisory|public_doc_content|V1_GA_)'
(empty)
```

```
$ find . -path ./.git -prune -o \( -name 'PLAN.md' -o -name 'SESSION_*.md' \
    -o -name 'STATUS*.md' -o -name 'V*_GA_*.md' -o -name 'autonomous_*' \
    -o -name 'wake_up_*' -o -name '*_HANDOFF.md' \) -print
(empty)
```

```
$ find . -path ./.git -prune -o -type d \( -name 'pr*_prep' -o -name 'pr*_audit_debt' \
    -o -name 'pr13_prep' -o -name 'persona_test_results' -o -name 'pr_proposals' \) -print
(empty)
```

---

## Verification: PR merge structure preserved

Sample of merge commits visible in cleaned history (`git log --merges --oneline`):

```
93f58b0 Integration: merge PR 11 followup v3 (nicegui pin bump)
a29f51d Integration: merge PR 11 follow-up (library + docs polish, v1.0.0)
6bab8e9 Integration: merge PR 11 (library + macOS .dmg, v1.0.0 GA)
e54412e Integration: merge PR 10a (UI mock-first scaffold + xfail followup, v0.6.0)
0049812 Integration: merge PR 10a (NiceGUI scaffold + mock solver, v0.6.0)
929297d Integration: merge PR 4.5 (audit-debt sweep, v0.5.2)
e62e363 Integration: merge PR 7 (river-spot diff vs Brown, v0.5.1)
1fc1e52 Integration: merge PR 6 (Rust port of HUNL postflop solve, v0.5.0)
424ba04 Integration: merge PR 6 (Rust port of HUNL postflop solve, v0.5.0)
8fc76ee Integration: merge PR 5 (HUNL postflop solve + memory profiler)
686e7dd Integration: merge PR 4 (card abstraction)
a395eb2 Integration: merge PR 3.5 audit follow-up (642493e)
27796f3 Integration: merge PR 3.5 (push/fold + v0.3 capstone)
9c5051d Integration: merge PR 3 (rebased on equity-hybrid main)
```

Sample `git show <merge>` (showing PR 11 merge — content clean, no internal docs):

```
$ git show 6bab8e9 --stat
commit 6bab8e9c66a9ba8f614885609e9c497ebd8c0e60
Merge: e54412e 9003d38
    Integration: merge PR 11 (library + macOS .dmg, v1.0.0 GA)

 CHANGELOG.md                         | 176 ++++++-
 README.md                            |   2 +-
 assets/README.md                     | 141 ++++++
 assets/poker_solver.icns             | Bin 0 -> 37200 bytes
 examples/tiny_csv.csv                |   3 +
 poker_solver/__init__.py             |  20 +-
 poker_solver/cli.py                  | 322 +++++++++++++
 poker_solver/library.py              | 878 +++++++++++++++++++++++++++++++++++
 ... (21 files total — no docs/pr*_prep, no PLAN.md, no SESSION_*) ...
 21 files changed, 4292 insertions(+), 77 deletions(-)
```

Sample older merge (PR 3.5 — v0.3 capstone):

```
$ git show 27796f3 --stat
commit 27796f3ac1161fa124e4b46e200f88a6af2f4367
Merge: 9c5051d 86acacb
    Integration: merge PR 3.5 (push/fold + v0.3 capstone)

 .github/ISSUE_TEMPLATE/bug_report.md      |   44 +
 .github/PULL_REQUEST_TEMPLATE.md          |   44 +
 CHANGELOG.md                              |  208 ++
 CONTRIBUTING.md                           |  117 ++
 README.md                                 |  241 ++
 poker_solver/__init__.py                  |   16 +-
 poker_solver/charts/__init__.py           |    6 +
 poker_solver/charts/pushfold_v1.json      | 3045 +++++++++++++++++++++++++++++
 poker_solver/pushfold.py                  |  211 ++
 poker_solver/solver.py                    |   46 +
 pyproject.toml                            |    5 +-
 scripts/generate_pushfold_charts.py       |  784 ++++++++
 tests/test_pushfold.py                    |  218 +++
 14 files changed, 4963 insertions(+), 61 deletions(-)
```

---

## Push verification (post-execution)

```
$ git push --force origin integration:integration
To https://github.com/amaster97/poker_solver.git
 + b6936b9...bc362e9 integration -> integration (forced update)
```

```
$ git ls-remote https://github.com/amaster97/poker_solver.git refs/heads/integration
bc362e94fdcfc7b679031ce5f1afbf20eca6b7ab	refs/heads/integration   # new clean tip

$ git ls-remote https://github.com/amaster97/poker_solver.git refs/heads/main
166d2b89c74865a0ab82ee8bdbb7ebe6d31a804b	refs/heads/main          # UNCHANGED

$ git ls-remote https://github.com/amaster97/poker_solver_private.git refs/heads/integration
2878bdaca445d801de61a78ec8b2f2cfb1d8b0a7	refs/heads/integration   # PRIVATE MIRROR UNCHANGED
```

---

## Hard-rule compliance

| Rule | Status |
|---|---|
| Only touched public origin's `integration` branch | OK (force-pushed only `integration:integration`) |
| No tag touched | OK (no `git tag` / `git push --tags` invoked) |
| `main` not touched | OK (origin/main = `166d2b8`, unchanged) |
| Private mirror not touched | OK (backup/integration = `2878bda`, unchanged) |
| No branches deleted | OK |
| Operated in fresh clone | OK (`/tmp/poker_solver_integration_cleanup/integration_clean`) |
| Push went to PUBLIC origin only | OK (verified URL `github.com/amaster97/poker_solver.git`, not `_private.git`) |

---

## Anomalies / notes

1. **9 commits dropped** as empty (file-only-internal commits became empty after the strip and were pruned by `git-filter-repo`). All merge commits and content-bearing commits are preserved. Example dropped commits would have been the ones that ONLY added `docs/pr*_prep/...` content or PLAN.md edits.

2. **Commit messages may still reference internal docs by path** (e.g., the `bc362e9` v1.3.1 commit message mentions `docs/pr16_prep/stress_test_results.md` as the "caught by" attribution). The referenced file does not exist in the cleaned tree, so this is a dangling text reference only — no content leak. Per the user's strip list, only file *contents* were targeted, not commit messages.

3. **PR 8 (SIMD) and PR 9 (preflop) were direct linear integration commits** in the original history (not merges). Their content is present as `5895961` and `aed4ac9` respectively in the cleaned history. So the visual "PR merge structure" shows merges for PR 3 → PR 11 (era of branch-based merges) plus direct linear commits for PR 8 and PR 9 (era of integration-direct). This faithfully reflects how integration was actually maintained.

4. **Private-mirror integration is at `2878bda` (v1.4.0)**, public-origin integration tip was at `b6936b9` (v1.3.1) before this cleanup. The public branch was already ~4 commits behind the private one for unrelated reasons (no integration-mirror sync between v1.3.1 and v1.4.0 happened for public). This cleanup did not change that — public integration is still at v1.3.1-era tip, just with internal files stripped from history. The private mirror remains the canonical source for v1.4.0 integration work.

5. **Other public origin branches** (`pr-3-hunl-tree`, `pr-10a-ui-mock-first`, etc. — 10+ stale PR branches from earlier work, per `state_verification_2026-05-23-late.md` §4.4) were NOT touched by this operation. They may contain their own internal content but were out of scope for this task.

---

## Workspace cleanup

Cleanup workspace at `/tmp/poker_solver_integration_cleanup/` left intact for orchestrator audit:
- `integration_clean/` — the filtered repo
- `paths-to-remove.txt` — the strip-list input
- `spot_check/verify_clone/` — fresh-clone verification
- `all_docs_in_history.txt` — pre-cleanup docs inventory

Safe to `rm -rf /tmp/poker_solver_integration_cleanup/` once orchestrator confirms the operation.
