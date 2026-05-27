# Orphan-Reference-Target Tracking — PR #60 Report (2026-05-26)

**PR URL:** https://github.com/amaster97/poker_solver/pull/60
**Branch:** `pr-101-orphan-refs` (deleted post-merge)
**Status:** MERGED (squash-merged 2026-05-26 ~07:40 UTC, all CI green)
**Trigger:** MEDIUM-staleness-fix agent surfaced `docs/v1_7_1_tag_decision_2026-05-26.md` as orphan target; broader sweep identified 7 additional orphans.

---

## TL;DR

8 orphan reference targets tracked verbatim on `origin/main` via PR #60. 2 truly-missing files surfaced as broken-link findings (out of scope; need follow-up).

---

## Per-file tracking decisions

### Tracked (8 files added to `origin/main`)

| File | Workspace size | Cited from (tracked main-line) | Decision rationale |
|---|---|---|---|
| `docs/v1_7_1_tag_decision_2026-05-26.md` | 11,368 B | `CHANGELOG.md:21`, `README.md:21`, `a83_validation_2026-05-26_plain_english.md`, `dmg_install_guide.md`, `dmg_spawn_loop_rca_2026-05-26.md`, etc. | Required by task spec. Audit decision doc on v1.7.1 closure. |
| `docs/a83_deep_cap_root_cause_investigation.md` | 22,337 B | `README.md:259`, `a83_validation_2026-05-26.md`, `a83_validation_2026-05-26_plain_english.md`, `terminal_utility_arbitration_2026-05-26.md`, `terminal_utility_audit_2026-05-26.md` | Task spec authorized tracking; **NOTE:** possible math error per Task #20 — correction is a follow-up, not blocked here. |
| `docs/v1_5_brown_current_state_2026-05-26.md` | 12,176 B | `README.md:245` | State-capture sanity check post-v1.8 SIMD landing; both A83/K72 spots PASS. |
| `docs/v1_8_simd_perf_benchmark_2026-05-26.md` | 12,632 B | `CHANGELOG.md:210`, `v1_8_0_release_notes_DRAFT.md` | Empirical bench finding (~1.0x not 4-8x); already referenced from CHANGELOG/draft. |
| `docs/river_parity_timeout_investigation_2026-05-23.md` | 12,383 B | `CHANGELOG.md:117` | Historical investigation; CHANGELOG cites it directly. |
| `docs/v1_6_1_dryrun_10.md` | 6,840 B | `a83_validation_2026-05-26.md`, `a83_validation_2026-05-26_plain_english.md`, `v1_6_1_ship_hold_review_2026-05-26.md`, `v1_8_0_release_notes_DRAFT.md` | Baseline dry-run #10 report cited from 4 tracked docs. |
| `docs/matched_config_investigation.md` | 7,551 B | `a83_validation_2026-05-26.md`, `a83_validation_2026-05-26_plain_english.md`, `terminal_utility_arbitration_2026-05-26.md`, `v1_6_1_ship_hold_review_2026-05-26.md`, `v1_8_0_release_notes_DRAFT.md` | Historical investigation cited from 5 tracked docs. |
| `docs/v1_8_0_release_notes_prep_2026-05-26.md` | 21,145 B | `v1_8_0_release_notes_DRAFT.md`, `v1_6_1_ship_hold_review_2026-05-26.md` | Prep report referenced from the tracked DRAFT itself. |

### Broken-link findings (NOT fixed in PR #60; out of scope)

| File | Cited from | Workspace status | Recommended action |
|---|---|---|---|
| `docs/architecture.md` | `CHANGELOG.md:1517` | Does not exist in workspace | Either author the file or remove/rephrase the CHANGELOG citation. |
| `docs/pushfold_v1_generation_notes.md` | `CHANGELOG.md:1562`, `CHANGELOG.md:1627` | Does not exist in workspace | Either author the file or remove/rephrase both CHANGELOG citations. |

Both CHANGELOG citations are in pre-v1.0 history sections (line 1500+), so they are documenting old pushfold/architecture work that may have been refactored away. Not user-facing in current release.

---

## Procedure summary

1. Verified `docs/v1_7_1_tag_decision_2026-05-26.md` (11,368 B, "v1.7.1 Tag Decision — 2026-05-26" header).
2. Swept all `docs/<filename>.md` references in main-line tracked docs (README.md, USAGE.md, CHANGELOG.md, dmg_install_guide.md, aggregator_vs_true_nash_explainer.md, v1_8_0_release_notes_DRAFT.md). Cross-referenced each against `git ls-tree origin/main:docs/`.
3. For each candidate, also ran `git grep -l "<filename>" origin/main -- '*.md'` to confirm it's cited from a tracked main-line doc (not just from an archived doc).
4. Created worktree `/Users/ashen/Desktop/poker_solver_worktrees/pr-101-orphan-refs` on branch `pr-101-orphan-refs` based on `origin/main`.
5. Copied 8 orphan files verbatim into worktree.
6. After fast-forwarding to latest `origin/main` (one new commit had landed mid-task), re-staged and committed with detailed message documenting all 8 files + the 2 broken-link findings.
7. Pushed to `origin`, opened PR #60.
8. Enabled squash auto-merge with `--repo amaster97/poker_solver` flag (the in-worktree `gh pr merge --auto` had failed because gh CLI tried to switch to main, which was already in another worktree).
9. CI passed (Golden File Check, Ship Dry Run, Skip-Ban Acceptance Tests). PR auto-merged.
10. Cleaned up worktree + local branch.

---

## Constraints honored

- No tracked file modified.
- All 8 orphan docs added verbatim (no content edits, no new docs authored).
- Did not block on the `a83_deep_cap_root_cause_investigation.md` math error — tracked the file as-is per task spec; correction queued as follow-up.

---

## Follow-up work surfaced

1. **Math-error correction in `a83_deep_cap_root_cause_investigation.md`** (per Task #20) — now tracked, so a future PR can edit it in place.
2. **Resolve the 2 truly-missing files** — either author `docs/architecture.md` and `docs/pushfold_v1_generation_notes.md`, or update the CHANGELOG citations.
3. **Run a periodic broken-link audit** — this is the second time this session that orphan refs have been surfaced after-the-fact; a CI gate or pre-commit hook that scans for `docs/<path>.md` references and verifies tracked-presence would catch this earlier.
