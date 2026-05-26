# Stash Recovery — 2026-05-23

## Context

After the earlier shared-tree resync, valuable doc files remained captured in
the untracked side of two stashes. This recovery extracted them to disk
without applying the code rollback that also rode in the stash.

## Method

For each missing doc/example/script file, used:

```
git show "stash@{N}^3:<path>" > <path>
```

This restores the untracked tree content only. No `stash pop` was run, so the
code rollback (CHANGELOG / pyproject / __init__.py reverts) was NOT applied.
Both stashes (`stash@{0}` and `stash@{1}`) are preserved for further recovery.

## Files recovered

- 13 files from `stash@{0}^3` (the WIP-on-main stash) — integration_sequencing_strategy.md, leg6_v1_3_1_ship_plan.md, 8x `pr13_prep/` persona+phase docs, `pr16_prep/stress_test_results.md`, and `pr_proposals/v1_4_node_locking.md`.
- 39 files from `stash@{1}^3` (pre-comprehensive-review-fix backup) — autonomous_burst_release_plan.md, comprehensive_review_2026-05-23.md, final_consistency_audit.md, midsession_hygiene_check.md, post_integration_verification_protocol.md, post_sync_consistency_check.md, pr_branch_deeper_audit.md, public_doc_content_audit.md, strip_and_soften_edits.md, plus full `pr8_prep/` (5), `pr8b_prep/` (2), `pr9_prep/` (7), `pr10b_prep/` (1), `pr11_prep/` (4), `pr15_prep/` (1), `pr16_prep/audit_kickoff.md`, 7x `pr_proposals/v1_3_*` docs, `examples/range_vs_range_river.py`, and `scripts/cleanup_pr_branches.sh`.

## Already on disk (skipped)

- `docs/pr16_prep/stress_test_results.md` — already restored from `stash@{0}^3` (135 lines, shorter draft); `stash@{1}^3` had a longer 235-line variant which was NOT used per "skip if exists" rule. The `stash@{1}^3` version remains retrievable via `git show "stash@{1}^3:docs/pr16_prep/stress_test_results.md"` if desired.

## Errors

None. All `git show` redirects landed cleanly.

## Totals

- 52 files recovered (13 from stash@{0}^3, 39 from stash@{1}^3)
- 1 file skipped (already on disk from prior recovery wave)
- 0 errors
