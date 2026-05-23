# Doc retention policy — 2026-05-22

**Purpose:** classify all 137 `docs/*.md` files (135 per-PR + 2 top-level inventories) into retention tiers so `docs/` doesn't grow unboundedly post-v1.
**Posture:** conservative — when in doubt, KEEP.
**Read-only.** No files moved, archived, or deleted by this pass.
**Companion:** `per_pr_doc_inventory.md` (file counts), `INDEX_2026-05-22.md` (semantic index).

---

## 1. Headline

| Category | Files | % of total | Action |
|---|---|---|---|
| Tier 1: Keep forever | ~14 | ~10% | Never archive |
| Tier 2: Keep through v1 ship | ~58 | ~42% | Archive ~90 days post-v1 ship |
| Tier 3: Archive post-PR-merge | ~50 | ~36% | Move to `docs/archive/prN/` ~30 days post-PR merge |
| Tier 4: Delete safe | ~15 | ~11% | Delete after PR ships + 7 days |
| **Total** | **137** | 100% | |

**Save list size if we retain everything:** docs/ will grow ~80–120 files per future PR (specs + 3 prompts + audit + 4 launch/fanout/preprep/invocations + audit report + commit drafts + supporting). At current rate, by v1.0.0 (post-PR-12) docs/ would be ~250+ files. Pruning Tier 3 + Tier 4 caps growth at ~150 long-term.

---

## 2. Tier 1 — Keep forever

**Definition:** long-term reference value; touched on every return-to-project; serves new contributors and future-you indefinitely.

### Files
- `PLAN.md` (project root, not docs/ — listed for completeness)
- `README.md` (root)
- `CHANGELOG.md` (root)
- `docs/architecture.md` — system architecture diagram + module map
- `docs/pr_launch_runbook.md` — universal per-PR playbook; canonical reference
- `docs/integration_test_scaffolds.md` — 18 scaffolds spec'd for future PRs
- `docs/competitor_landscape.md` — competitor research; useful for any roadmap revision
- `docs/rust_orientation.md` — Rust onboarding notes; pairs with PR 6 port
- `docs/pushfold_v1_generation_notes.md` — push/fold chart generator (data provenance)
- `docs/release_notes_v0.3.md`, `release_notes_v0.3.1.md` — release artifacts; never archive
- `docs/autonomous_log.md` — running S/D series log (continuously appended)
- `docs/autonomous_decisions_2026-05-22.md` — user-locked decisions (if rolled into a master `autonomous_decisions.md`, archive the dated ones)

**Subtotal:** ~12 docs/ files + 3 root files = **~14 forever-kept**.

---

## 3. Tier 2 — Keep through v1 ship

**Definition:** relevant during active v1 development (PR 7–12). High value while iterating; safe to archive once v1.0.0 ships and stabilizes for ~90 days.

### 2a. Audit reports (every shipped PR has one)
- `pr3_prep/audit_report.md`
- `pr3_5_prep/audit_report.md`
- `pr4_prep/audit_report.md`
- `pr5_prep/audit_report.md`, `audit_trail_2026-05-22.md`
- `pr6_prep/audit_report.md`
- `pr7_prep/audit_report.md` *(when produced)*
- `pr8–12_prep/audit_report.md` *(when produced)*

**Why keep:** audit reports document what was checked and what shipped with known limitations. Useful for security review, retrospectives, contributor onboarding.

### 2b. Specs (every PR has one)
- `prN_prep/prN_spec.md` for N ∈ {3, 3.5, 4, 5, 6, 7, 8, 9, 10a, 10b, 11, 12}
- `pr10_prep/pr10_spec.md` (pre-split combined spec — keep as historical context)

**Why keep:** specs are the contract for what each PR delivered. Even shipped PRs benefit from spec availability when debugging regressions or planning v2 work.

### 2c. Commit / ready artifacts
- `pr3_5_prep/ready_to_commit_summary.md`
- `pr4_prep/ready_to_commit_summary.md`
- `pr5_prep/commit_message_draft.md`, `pre_commit_checklist.md`, `pre_merge_sanity.md`
- `pr6_prep/commit_message_draft.md`, `commit_message_amendments.md`, `commit_pipeline_readiness.md`, `pre_commit_checklist.md`, `semver_sequencing.md`
- `pr4_5_audit_debt/launch_decision.md`

### 2d. Decision logs + retrospectives
- `session_retrospective_2026-05-22.md`
- `wake_up_brief_2026-05-22.md` (current)
- `roadmap_status_2026-05-22.md`
- `audit_followup_backlog.md`
- `open_items_audit_2026-05-22.md`
- `effort_estimate_revalidation.md`
- `cross_pr_cleanup_plan.md`

### 2e. Reference investigations (cited from PLAN / specs)
- `pr3_prep/hunl_tree_size_estimate.md`
- `pr3_prep/postflop_solver_tree_notes.md`, `open_spiel_noambrown_notes.md`
- `pr4_prep/postflop_solver_emd_patterns.md`
- `pr10_prep/competitor_ui_deep_dive.md`, `ui_design_principles.md`, `ui_mockups_and_debates.md`

**Subtotal:** ~58 files.

**Archive trigger:** v1.0.0 ships + 90 days of stability (no rollback / hotfix needed).

---

## 4. Tier 3 — Archive post-PR-merge

**Definition:** pre-implementation artifacts. High value during PR fan-out and audit, near-zero value once the PR has merged + landed. Move to `docs/archive/prN/` ~30 days post-merge.

### Per-PR pre-launch artifacts (Tier 3)
For each staged PR (currently PR 4.5, 7, 8, 9, 10a, 10b, 11, 12) the following files become low-value post-merge:

- `agent_a_prompt.md`, `agent_b_prompt.md`, `agent_c_prompt.md` — agent role briefs; consumed at fan-out time only
- `audit_prompt.md` (and `audit_prompt_final.md` when present) — audit role brief
- `launch_readiness.md`, `launch_readiness_v2.md`, `launch_readiness_v3.md` — pre-fan-out gate checks
- `launch_kickoff.md`, `launch_kickoff_10a.md`, `launch_kickoff_10b.md` — fan-out playbook
- `fanout_ready.md`, `fanout_ready_10a.md`, `fanout_ready_10b.md` — agent-launch shortlist
- `audit_preprep.md`, `audit_preprep_10a.md`, `audit_preprep_10b.md` — pre-audit gate check
- `launch_invocations.md`, `launch_invocations_10a.md`, `launch_invocations_10b.md` — Task tool invocation strings

**Count:** 8 staged PRs × ~7 files = **~56 files** *(some PRs have extras: PR 6 has 3 readiness versions, PR 10 has split a/b artifacts; some shipped PRs already accumulated these in Tier 2)*.

Filtered to currently-existing pre-launch files (excluding shipped PRs that never produced them): **~50 files**.

### Why archive (not delete)
- Useful for future PRs as templates (especially `pr_launch_runbook.md` evolved from PR 6 / 7 patterns)
- Audit trail for "how did we run PR N's fan-out?"
- Disk cost is trivial; semantic clutter in `docs/` is the real cost

### Archive structure (proposed)
```
docs/
  archive/
    pr7/
      agent_a_prompt.md
      agent_b_prompt.md
      …
    pr8/
      …
```

Versus deletion: archive subdir preserves history without polluting top-level `docs/` `ls` listings. Picked archive.

**Archive trigger:** PR merges to main + 30 days no rollback.

---

## 5. Tier 4 — Delete safe

**Definition:** one-shot intermediate artifacts that resolved cleanly. Pure noise post-resolution. Safe to `rm` after PR ships + 7 days.

### Candidates
- `spec_consistency_review.md` — v1 sweep, fully superseded by v2
- `pr5_prep/should_fix_triage.md` — triage rolled up into `audit_followup_backlog.md`
- `pr5_prep/deferred_cleanup.md` — same
- `pr5_prep/exploitability_verification_2026-05-22.md` — confirmed false alarm; resolution captured in audit report
- `pr6_prep/cross_agent_reconciliation.md`, `final_consistency_check.md`, `external_nash_cross_check.md`, `pre_commit_artifact_check.md` — once PR 6 merged + stable, these become archeology
- `pr6_prep/MUST_PATCH_BEFORE_LAUNCH.md` — patches landed; gate satisfied
- `session_pause_2026-05-21.md` — stale, superseded by 2026-05-22 brief
- `wake_up_brief.md` (2026-05-21) — marked stale at top; superseded
- `doc_inventory.md` (earlier scan, 90 files / 33,574 lines) — superseded by `INDEX_2026-05-22.md` and `per_pr_doc_inventory.md`
- `cross_doc_consistency_check.md` — clean result ("none material"); no value preserving the null finding
- `final_state_check_2026-05-22.md` — sanity-check snapshot; superseded after next session
- `plan_log_final_sweep.md` — same (per-session sanity check)
- `git_state_post_recovery.md` — incident artifact, resolved
- `equity_precision_branch_investigation.md` — once user decides on the dangling branch, the investigation becomes archeology (keep until decision)

**Subtotal:** **~15 files**.

**Delete trigger:** PR shipped + 7 days no callback to the doc + resolution captured in a Tier 2 rollup.

### NOT in Tier 4 (preserve even though tempting)
- `audit_report.md` for any PR (Tier 2)
- `card_removal_investigation.md` — non-trivial codebase audit; keep through v1
- `reference_repo_audit.md` — license + reference inventory; keep through v1
- `memory_audit_2026-05-22.md` — auto-memory inventory; archive if MEMORY.md rewritten, not delete

---

## 6. Recommended retention timeline

| Event | Action |
|---|---|
| PR fan-out launches | All Tier 3 files for that PR are "active"; no pruning |
| PR audit complete + audit_report.md produced | Tier 3 files still active until merge |
| PR merges to main | Tier 4 files for that PR become candidates for deletion (≥7 days) |
| PR merge + 30 days no rollback | Tier 3 files move to `docs/archive/prN/` |
| v1.0.0 ships + 90 days stable | Tier 2 files move to `docs/archive/v1_history/` |
| Forever | Tier 1 files stay in `docs/` top-level |

### Auto-archive script (proposed, not implemented this pass)
A future PR could add `scripts/archive_docs.py` that:
1. Reads `PLAN.md` to find shipped PRs + merge dates
2. For each shipped PR > 30 days ago, moves Tier 3 files to `docs/archive/prN/`
3. For each shipped PR > 7 days ago, prompts (not auto-deletes) to remove Tier 4 files
4. Logs the move/delete to `autonomous_log.md`

Not in scope for this audit.

---

## 7. Save list size projection

### Current (2026-05-22): 137 files, ~43k lines

### If we retain everything (no pruning policy)
- PR 7 ships: +5 files (audit report, commit draft, ready summary, etc.) → 142
- PR 8 ships: +5 → 147
- … through PR 12
- v1.0.0 = ~165 files in `docs/` top level

### With this policy applied
- PR 7 merges + 30 days: archive ~7 Tier 3 files for PR 7 → 130 in top-level
- PR 8 merges + 30 days: archive ~7 Tier 3 files for PR 8 → 128
- v1.0.0 + 90 days: archive ~50 Tier 2 files → **~80 files in top-level docs/**
- Long-term steady-state: **~14 Tier 1 + ~10 living docs = ~24 files visible**

`docs/archive/` holds ~120 historical files; out of sight, on disk, recoverable.

---

## 8. Edge cases + open questions

### Edge case: PR 6 has 26 files (heaviest pack)
Tier breakdown for PR 6:
- Tier 2 (keep through v1): `pr6_spec.md`, `audit_report.md`, `commit_message_draft.md`, `commit_message_amendments.md`, `commit_pipeline_readiness.md`, `semver_sequencing.md`, `pre_commit_checklist.md` — ~7 files
- Tier 3 (archive post-merge): 3 agent prompts, `audit_prompt.md`, `audit_prompt_final.md`, `launch_kickoff.md`, `launch_readiness_v2.md`, `launch_readiness_v3.md` — ~8 files
- Tier 4 (delete safe): `cross_agent_reconciliation.md`, `final_consistency_check.md`, `external_nash_cross_check.md`, `MUST_PATCH_BEFORE_LAUNCH.md`, `pre_commit_artifact_check.md` — ~5 files
- Reference notes (Tier 2): `leduc_timeout_recipe.md` (if separate file) — keep

**Result:** PR 6 prunes from 26 → ~7 long-term retained.

### Edge case: PR 4.5 cleanup sweep (5 files, no spec)
All 5 files (`launch_kickoff.md`, `fanout_ready.md`, `audit_preprep.md`, `launch_invocations.md`, `launch_decision.md`) become Tier 3 post-merge. `launch_decision.md` could be promoted to Tier 2 (decision rationale) — recommend KEEP for now.

### Edge case: PR 3 pre-canonicalization (6 files)
- `pr3_spec.md` (Tier 2), `audit_report.md` (Tier 2) → 2 keep
- `agent_a_interface_concerns.md`, `hunl_tree_size_estimate.md`, `postflop_solver_tree_notes.md`, `open_spiel_noambrown_notes.md` → Tier 2 (reference notes, cited from later PRs)

**Result:** PR 3 keeps all 6.

### Open question: dated session docs (`wake_up_brief_2026-05-22.md`, etc.)
Recommendation: keep the latest of each kind in Tier 2; once superseded by a new-date version, demote prior dated version to Tier 4. Currently `wake_up_brief.md` (no-date original, 2026-05-21) is already in Tier 4.

### Open question: shared PR 10 folder (`pr10_prep/`)
`_10a` / `_10b` suffix convention means archiving needs awareness of split. Recommend: `docs/archive/pr10/{10a/,10b/,shared/}` substructure.

---

## 9. Implementation guidance (NOT executed this pass)

1. **Validate counts:** before any move, run `find docs/ -type f -name "*.md" | wc -l` to confirm 137 baseline.
2. **Dry-run:** generate a `docs/retention_dry_run.md` listing exact moves for review.
3. **Backup:** `tar czf docs_pre_archive_$(date +%Y-%m-%d).tar.gz docs/` before any move.
4. **Move, don't delete:** `git mv` to preserve history.
5. **Update INDEX:** regenerate `INDEX_YYYY-MM-DD.md` post-archive.
6. **Update PLAN.md:** add archive section noting the policy applied.

---

## 10. Conservative bias note

When unsure between two tiers, this policy errs toward the higher (keep-longer) tier:
- All audit reports → Tier 2 (not Tier 3)
- All specs → Tier 2 (not Tier 3)
- Reference investigation notes → Tier 2 (not Tier 3 or 4)
- Decision logs → Tier 2 (not Tier 3)

Cost of false-positive keep: ~50 KB / file × 100 over-kept = ~5 MB of clutter. Cost of false-positive delete: 1 unrecoverable doc. Asymmetry favors keeping.

---

**Bottom line:** with this policy, `docs/` grows linearly to ~150 files through v1 ship, then settles at ~24 visible + ~120 archived. Without it, `docs/` hits ~250+ files by v1 and keeps growing.
