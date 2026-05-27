# Integration Catch-up Report — 2026-05-23 (late)

**Operation:** advance public `origin/integration` from `bc362e9` (v1.3.1-era, last cleaned 2026-05-23 morning) to a filtered copy of public `origin/main` at `eea3a8b` (v1.4.3 tip).
**Model:** "public integration = private integration with private things stripped out."
**Workspace:** `/tmp/poker_solver_integration_catchup_1779532233/integration_catchup` (fresh clone, isolated from shared tree).
**Tool:** `git-filter-repo` (`/Users/ashen/.local/bin/git-filter-repo`).

---

## TL;DR

- Public `origin/integration` rewritten from `bc362e9` -> `c09411c` (force-pushed, integration branch only).
- New tip is a filtered copy of public main at `eea3a8b` (v1.4.3) with all internal-planning paths stripped from full history.
- Commit count: 77 (main lineage) -> 71 (post-filter; 6 dropped as empty after content strip).
- HEAD file count: 126 files (no `docs/` directory; user-facing content lives in root CHANGELOG/README/USAGE/DEVELOPER/CONTRIBUTING + code dirs).
- .git size: 2.8M -> 1.1M (~60% reduction from filter dedup).
- Public `origin/main` unchanged at `eea3a8b`.
- Public tags unchanged.
- Private mirror unchanged (`backup/integration` = `2878bda`; `backup/main` = `166d2b8`).

---

## Pre-flight checks

| Check | Result |
|---|---|
| Public origin URL | `https://github.com/amaster97/poker_solver.git` |
| Private mirror URL | `https://github.com/amaster97/poker_solver_private.git` |
| URLs distinct | YES — safe to proceed |
| Workspace | `/tmp/poker_solver_integration_catchup_1779532233/integration_catchup` (fresh clone, not shared tree) |
| Branches in scope | `integration` only |
| Branches NOT touched | `main`, all tags, all PR-* branches on origin; entire private mirror |

---

## Strategy

Public main and public integration had divergent histories (integration was filter-repo rewritten 2026-05-23 morning; main has linear unrewritten commits with v1.4.0->v1.4.3 added on top). To "catch up integration to main with internals stripped," the workflow was:

1. Clone public origin fresh.
2. Run `git-filter-repo --invert-paths --paths-from-file paths-to-remove.txt --force` over the clone. This rewrites all branches (including main and integration locally inside the clone) with internal paths stripped from history.
3. Delete the old local `integration` branch (which was the rewrite of `bc362e9` v1.3.1-era tip).
4. Recreate `integration` from the filtered `main` (which carries v1.4.0->v1.4.3 plus all prior content).
5. Force-push `integration:integration` to public origin. No other refs pushed.

This produces an integration that is a strict filtered subset of main — exactly the "public integration = public main with internals stripped" semantic. The historical merge-commit graph from the pre-v1.0.0 era is preserved (14 merge commits visible in `git log --merges`) because main carries that history.

---

## Strip list (paths-to-remove.txt)

Path: `/tmp/poker_solver_integration_catchup_1779532233/paths-to-remove.txt`

Reused canonical list from `docs/integration_cleanup_report_2026-05-23.md` (`/tmp/poker_solver_integration_cleanup/paths-to-remove.txt`), with v1.4.x/v1.5.x defensive entries appended per orchestrator spec. Full list categories:

```
# Root-level planning/status/session/handoff artifacts:
PLAN.md, STATUS.md, SESSION_END_FINAL.md, V1_GA_CLOSE.md,
glob:STATUS*.md, glob:SESSION_*.md, glob:V*_GA_CLOSE.md,
glob:V*_MILESTONE*.md, glob:wake_up_*.md, glob:*_HANDOFF.md

# docs/ session/status/wake-up/handoff artifacts:
docs/SESSION_END_REPORT.md, docs/SESSION_HANDOFF.md,
docs/V1_GA_MILESTONE_HIT.md, docs/wake_up_brief*.md,
docs/session_pause_2026-05-21.md, docs/session_retrospective_2026-05-22.md,
docs/morning_briefing_check.md, docs/next_session_plan.md,
docs/final_state_check_2026-05-22.md, docs/INDEX_2026-05-22.md,
docs/ONE_PAGE_SUMMARY.md, docs/snapshot_*.md,
docs/git_state_post_recovery.md

# Autonomous / planning logs:
docs/autonomous_log.md, docs/autonomous_burst_release_plan.md,
docs/autonomous_decisions_2026-05-22.md, docs/plan_log_*.md,
docs/plan_index_final_alignment.md, docs/planning_preservation_decision.md,
docs/plan_md_post_pr*_edit_recipe.md

# Audits / reviews / state verifications (50+ files):
docs/open_items_audit_*.md, docs/audit_*.md, docs/branch_name_*.md,
docs/cargo_lock_audit.md, docs/changelog_*.md, docs/cross_*.md,
docs/doc_inventory.md, docs/doc_retention_policy.md,
docs/effort_estimate_revalidation.md, docs/equity_precision_*.md,
docs/card_removal_investigation.md, docs/memory_*.md,
docs/per_pr_*.md, docs/perf_bench_scaffolds_review.md,
docs/readme_accuracy_check.md, docs/reference_repo_audit.md,
docs/repo_audit.md, docs/roadmap_status_2026-05-22.md,
docs/routing_check_2026-05-23.md, docs/spec_consistency_*.md,
docs/split_script_smoke.md, docs/test_coverage_post_pr5.md,
docs/usage_dev_proofread_report.md, docs/v0*_*_consistency_*.md,
docs/zombie_pytest_cleanup.md, docs/prune_report_2026-05-23.md,
glob:docs/comprehensive_review*.md, glob:docs/state_verification*.md,
glob:docs/river_parity_timeout_investigation*.md,
glob:docs/retag_execution_report*.md, glob:docs/integration_cleanup*.md,
glob:docs/integration_catchup*.md, glob:docs/leg*_*.md,
docs/integration_sequencing_strategy.md, docs/integration_test_scaffolds*.md,
docs/pr_prep_state_check.md, docs/midsession_hygiene_check.md,
docs/post_integration_verification_protocol.md,
docs/post_sync_consistency_check.md, docs/session_shipped_2026-05-23.md,
docs/stash_recovery_2026-05-23.md, docs/strip_and_soften_edits.md,
docs/final_consistency_audit.md, docs/pr_branch_deeper_audit.md,
docs/public_doc_content_audit.md

# Cutover / option_c (private deploy strategy) / sync runbooks:
docs/cutover_*.md, docs/option_c_*.md, docs/sync_repos_runbook.md,
docs/branch_split_runbook.md, docs/public_cleanup_advisory.md

# Internal release-flow recipes:
docs/v0.5.0_release_recipe.md, docs/v1.0.0_release_recipe.md,
docs/publish_workflow.md

# Per-PR prep directories (explicit + glob):
glob:docs/pr*_prep/**, glob:docs/pr*_audit_debt/**,
glob:docs/persona_test_results/**, glob:docs/pr_proposals/**,
(explicit globs for pr3_prep ... pr22_prep, pr3_5_prep,
 pr4_5_audit_debt, pr8b_prep, pr10a_5_prep, pr10c_prep)
docs/pr_launch_runbook.md

# v1.4.x / v1.5.x-era internal audits (defensive, added this run):
glob:docs/brown_apples_to_apples*.md, glob:docs/dcfr_perf_regression*.md,
docs/v1_4_3_pre_ship_audit.md, docs/v1_5_0_pr_23_audit.md,
docs/v1_5_brown_acceptance_test_status.md,
docs/v1_5_slider_tier_defaults_measured.md
```

Total: 184 lines (170 from canonical + 14 added defensive entries).

---

## Before / after metrics

| Metric | Before (main HEAD) | After (filtered integration HEAD) | Delta |
|---|---|---|---|
| Integration tip SHA | `bc362e9` (v1.3.1-era, pre-catchup integration) | `c09411c` (v1.4.3-era) | rewritten |
| Source for filter | `origin/main` at `eea3a8b` (v1.4.3) | filtered copy | -- |
| Commit count on filtered branch | 77 (main lineage) | 71 | -6 (commits that touched only stripped paths became empty and were dropped) |
| Files in HEAD tree | 126 (main HEAD was already clean of `docs/` internals) | 126 | 0 (HEAD was already clean) |
| .git size | 2.8M | 1.1M | ~-60% (filter-repo dedup + history strip) |

### Files in HEAD (top-level):

```
.github/                # GitHub workflows + templates
.gitignore
CHANGELOG.md            # Full release history v0.3 -> v1.4.3 inline
CONTRIBUTING.md
Cargo.lock
Cargo.toml
DEVELOPER.md            # Two-tier honesty notes + action abstraction
LICENSE
README.md
USAGE.md                # v1.4.x capability matrix + perf cliffs
assets/                 # Icon files for .dmg
crates/                 # Rust crate source
examples/
poker_solver/           # Python package
pyproject.toml
scripts/
tests/
ui/                     # NiceGUI app
```

NOTE: `docs/` directory is absent in HEAD. Public main was independently pruned of all `docs/` content (including user-facing release_notes_v*.md, architecture.md, etc.) at some earlier point. This catchup preserves that state — integration mirrors main exactly. Release-notes content survives in `CHANGELOG.md` as inline `## [x.y.z]` sections (24 version entries).

---

## Verification: internal paths gone from all history

```
$ git -C integration_catchup log --all --pretty=format: --name-only | sort -u \
    | grep -E '(PLAN\.md|pr.*_prep|autonomous_log|SESSION_|wake_up|STATUS|HANDOFF|state_verification|comprehensive_review|persona_test_results|pr_proposals|brown_apples|v1_5_|v1_4_3_pre|dcfr_perf|river_parity_timeout|retag_execution|integration_cleanup|integration_catchup|leg[0-9]+_|autonomous_burst|midsession_|cutover_|option_c|sync_repos_runbook|publish_workflow|release_recipe|prune_report|public_cleanup|public_doc_content|V1_GA_)'
(empty)
```

```
$ git -C integration_catchup ls-tree -r HEAD \
    | grep -E '(PLAN\.md|pr.*_prep|autonomous_log|SESSION_|wake_up|STATUS|HANDOFF)'
(empty)
```

---

## Verification: PR merge structure preserved

14 historical merge commits intact (`git log --merges --oneline | head -14`):

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

Post-v1.0.0 era is linear (PR 8 / 9 / 15 / 16 / 21 / 22 / 25 / 27 / 30 etc. went directly to main on public origin, not via integration-merge). v1.4.0 -> v1.4.3 content visible as linear commits on filtered branch:

```
c09411c v1.4.3: validation + Range.diff + docs refresh
f58854d PR 30 fix-ups: v1.4.3 preamble + drop PR 27 forward-ref + drop dangling brown_apples reference
54a3797 DEVELOPER.md: two-tier honesty + action abstraction + op notes
12fa085 USAGE.md: v1.4.x capabilities + CLI gaps + perf cliffs
9f1dfa0 Add Range.diff() utility for set-difference semantics (unblocks W2.2)
89200ca HUNLConfig: validate types in __post_init__ (loud failure at boundary, not silent crash deep in solver)
d3d24a4 Bump version to v1.4.2 (docs honesty + test marker)
2d95c63 Fix module-level docstring same hero_player misleading framing
3464f41 Fix misleading hero_player docstring (P0=SB-seat acts LAST postflop)
388622e PR 25 fix #1: mark test_river_parity_vs_brown as @pytest.mark.slow
a9a9dd9 PR 22 follow-up: route hole-deal to facing-bet player
798e436 PR 22: asymmetric initial-contributions for facing-bet subgames (v1.4.1)
ded1212 chore(release): v1.4.0 — Node-locking (MINOR; Daniel-persona unlock)
657bcda PR 21: v1.4.0 node locking (Python + Rust)
fa7506b chore(release): v1.3.2 — Rust port of exploitability walk (PATCH bump)
85aaa7a PR 15: Rust port of HUNL exploitability + game-value walks (v1.3 RvR perf)
b6fcbad v1.3.1: fix range_aggregator hero_player gap + honest caveats
5495188 chore(release): v1.3.0 — range-vs-range API via blueprint aggregator (MINOR bump)
```

---

## Push verification

```
$ git push --force origin integration:integration
To https://github.com/amaster97/poker_solver.git
 + bc362e9...c09411c integration -> integration (forced update)
```

```
$ git ls-remote https://github.com/amaster97/poker_solver.git refs/heads/integration
c09411ca3812127cd0482372319183cbfc05f767	refs/heads/integration   # NEW v1.4.3-era tip

$ git ls-remote https://github.com/amaster97/poker_solver.git refs/heads/main
eea3a8b502ec5b5e2e7ad18e61eb71b3b00aaafc	refs/heads/main          # UNCHANGED

$ git ls-remote https://github.com/amaster97/poker_solver_private.git refs/heads/integration
2878bdaca445d801de61a78ec8b2f2cfb1d8b0a7	refs/heads/integration   # PRIVATE MIRROR UNCHANGED

$ git ls-remote https://github.com/amaster97/poker_solver_private.git refs/heads/main
166d2b89c74865a0ab82ee8bdbb7ebe6d31a804b	refs/heads/main          # PRIVATE MIRROR UNCHANGED
```

Tag tips on public origin (spot-checked v0.6.0, v0.6.1, v1.0.0) unchanged.

---

## Hard-rule compliance

| Rule | Status |
|---|---|
| Only touched public origin's `integration` branch | OK (force-pushed only `integration:integration`) |
| No tag touched | OK (no `git tag` / `git push --tags` invoked) |
| `main` not touched | OK (origin/main = `eea3a8b`, unchanged) |
| Private mirror not touched | OK (backup/integration = `2878bda`, backup/main = `166d2b8`, both unchanged) |
| No branches deleted on origin | OK |
| Operated in fresh clone | OK (`/tmp/poker_solver_integration_catchup_1779532233/integration_catchup`) |
| Push went to PUBLIC origin only | OK (verified URL `github.com/amaster97/poker_solver.git`, NOT `_private.git`) |
| Time budget (15 min) | OK |

---

## Anomalies / notes

1. **`docs/` directory absent in HEAD.** Public origin's `main` HEAD itself contains no `docs/` directory at all — this was the state on origin/main before this run, not caused by the filter. The previous 2026-05-23 morning integration cleanup retained 12 user-facing `docs/*.md` files because it was working from a different starting state. Result: this catchup leaves integration with the same HEAD layout as main (no `docs/`). Release notes content is preserved inline in `CHANGELOG.md` (24 version sections).

2. **6 commits dropped as empty.** Commits whose only file changes targeted stripped paths became empty after filter and were pruned by `git-filter-repo`. All semantic content-bearing commits and merge commits are preserved.

3. **Commit messages may reference internal docs.** Some commit messages (e.g., `f58854d`'s "drop dangling brown_apples reference") mention internal-doc filenames in the message body. Per the user's strip list, only file *contents* were targeted, not commit messages. These are dangling textual references only — the referenced files are absent from history. Consistent with prior cleanup's anomaly #2.

4. **Pre-v1.0.0 merge graph preserved; post-v1.0.0 is linear.** PR 3 -> PR 11 era used branch-based merges (visible as 14 merge commits). PR 15+ went directly to main without intermediate integration-merge commits. The post-v1.0.0 linear history honestly reflects how integration was actually maintained on public origin during v1.1.0 -> v1.4.3 (i.e., main-direct).

5. **Workspace dual filter side-effect.** filter-repo rewrites all refs in the workspace, so the local `integration` branch was also filtered (its tip `bc362e9` was rewritten). The local `integration` branch was discarded and recreated from filtered `main` before push, so this side-effect did not contaminate the push.

6. **No leaked internal paths discovered in public origin/main history that weren't already covered by the canonical strip list.** The v1.4.x defensive entries (brown_apples, dcfr_perf, v1_4_3_pre_ship_audit, v1_5_*) hit nothing in public main's history — confirming v1.4.x PRs shipped to public main cleanly without leaking internal docs.

7. **Origin PR-* branches still present.** Public origin retains 10+ stale PR branches (`pr-3-hunl-tree`, `pr-10a-ui-mock-first`, etc.) from earlier work. They were NOT touched by this operation (out of scope per the orchestrator's hard rules).

---

## Workspace location

`/tmp/poker_solver_integration_catchup_1779532233/`
- `integration_catchup/` — the filtered repo (~2.9M)
- `paths-to-remove.txt` — 184-line strip list

Safe to `rm -rf /tmp/poker_solver_integration_catchup_1779532233/` once orchestrator confirms.
