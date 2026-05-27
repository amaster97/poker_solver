# Worktree Cleanup Sweep — 2026-05-26

**Scope:** Broader sweep of all worktrees outside main, per user's branch policy
("keep working trail for debugging/building, no redundant clutter").
Complements the earlier surviving-Desktop-worktrees agent's pass on 5 specific
worktrees.

**Working dir:** `/Users/ashen/Desktop/poker_solver`

## Before / After

| Metric | Before | After |
|---|---|---|
| Total worktrees (incl. main) | 23 | 9 |
| Non-main worktrees | 22 | 8 |
| Local branches deleted | — | 13 |
| Target (<10 worktrees) | — | met |

## Per-Worktree Decisions

### Removed — ABSORBED IN MAIN (6)

| Worktree | Branch | Reason |
|---|---|---|
| `pr-24a-gui-rvr-slider` | `feature/pr-24a-gui-rvr-slider` | All 4 commits already on `origin/main` (`5d381a9`, `daafc8e`, `92e70ea`, `0e0e2c8`). |
| `pr-24b-gui-nodelock-asym` | `feature/pr-24b-gui-nodelock-asym` | All 5 commits already on `origin/main` (`0949207`, `14b961f`, `7b34a39`, `f22c65d`, `e9e2df1`). |
| `python-delegate` | `pr-33-python-delegate` | `initial_hole_cards=()` delegate verified present in `poker_solver/solver.py` on `origin/main` (sibling commit `a772904`). |
| `v1-7-0-nash-wrapper` | `pr-43-nash-wrapper` | `solve_range_vs_range_nash` shipped on `origin/main` (commits `32de21c`, `6f5cd43`). |
| `ship-v1.6.0` | `ship-v1.6.0` | Branch had no unique commits vs `origin/main`. |
| `pr-91-a83-docs` | `pr-91-a83-docs-release-notes-update` | Merged as PR #50 on 2026-05-26 06:53Z. |

### Removed — SUPERSEDED (3)

| Worktree | Branch | Reason |
|---|---|---|
| `pr-35-canonicalization` | `pr-35-canonicalization` | Superseded by merged PRs #5 (action menu guard), #9 (renderer stack_ceiling), #12 (hand-string canonicalization). |
| `pr-40-acceptance-test-fix` | `pr-40-acceptance-test-fix` | Superseded by merged PRs #14 (acceptance reframe rebased) + #15 (Layer 3 ceiling loosen). |
| `rebase-pr-24` | `rebase-24-2026-05-26` | PR #24 CLOSED without merge on 2026-05-26; salvageable content shipped via merged PR #48 (USAGE §7b refresh). |

### Removed — STALE-BUT-INTERESTING / archived to `docs/_archive_2026-05-26/` (4)

| Worktree | Branch | Archive location | Reason |
|---|---|---|---|
| `spec-corrections` | `pr-29-persona-spec-corrections` | `docs/_archive_2026-05-26/worktree_spec-corrections/0001-Persona-spec-corrections-*.patch` | May-23 persona spec fixes; never PR'd; subsequent persona reframe work (W1.3, W3.5 reversal) supersedes. |
| `river-parity-fix` | `pr-25-river-parity-test-fix` | `docs/_archive_2026-05-26/worktree_river-parity-fix/0001-0002-*.patch` | May-23 river-parity test marker + concrete hole cards; never PR'd on origin. |
| `w3-5-reversal` | `pr-42-w3-5-reversal` | `docs/_archive_2026-05-26/worktree_w3-5-reversal/0001-0005-*.patch` | May-23 W3.5 vector-form Nash reversal + audit-finding cleanup; never PR'd on origin; later persona work on `main` supersedes. |
| `pr-81-doc-drift` | `pr-81-doc-drift-cleanup` | `docs/_archive_2026-05-26/worktree_pr-81-doc-drift/` (3 files: `FINAL_PRE_SIGNON_AUDIT.md`, `README_proposed_update_2026-05-23.md`, `RELEASE_NOTES_PROVENANCE.md`) | Killed agent's worktree; behind `origin/main` by 12 commits with no unique commits. Uncommitted edits to CHANGELOG/USAGE/dmg_install_guide already superseded by merged PRs #42/#44/#45/#48. Only the 3 untracked doc files were unique; archived. |

### Removed — failed/empty run dir (1)

| Worktree | Branch | Reason |
|---|---|---|
| `gate4-run-23262` | (detached HEAD, commit `cfc6bc5`) | Removed via `git worktree remove --force` after prune in earlier pass already nuked the dir; harmless cleanup. |

### KEPT — IN-FLIGHT (8 non-main worktrees + main)

| Worktree | Branch / Commit | Reason kept |
|---|---|---|
| `/Users/ashen/Desktop/poker_solver` | `main` (`3eea3b1`) | Main worktree. |
| `/private/tmp/bench-pre-simd` | `bench-pre-simd` (`3843ce7`) | SIMD pre-vs-post perf bench baseline reference; per user note "can remove if benchmark agent done" — benchmark agent status not verified; held conservative. |
| `/private/tmp/wt-pr-89-plan-prune` | `pr-89-plan-prune` (`a012de6`) | PLAN.md prune held for user review per user note. |
| `pr-88-v1.8.0-notes` | `pr-88-v1.8.0-release-notes-prep` (`01b661c`) | v1.8.0 release notes pre-draft, user-held. |
| `pr-90-regret-init-noise` | `pr-90-regret-init-noise` (`5ead08f`) | A83 Track A in-flight; ~7 modified files in working tree (regret-init noise investigation). |
| `pr-92-resume-doc` | `pr-92-resume-doc` (`5eef287`) | **OPEN PR #49** (RESUME doc) — held. |
| `pr-93-tu-ablation` | `pr-93-terminal-utility-ablation` (`a5be2be`) | A83 terminal-utility ablation agent in-flight; ~4 modified files in working tree. |
| `pr-95-archive` | `pr-95-untracked-docs-archive` (`3eea3b1`) | Newly spawned by another agent during this sweep; untracked archive work; do not touch. |
| `rebase-pr-20` | `rebase-20-2026-05-26` (`2226c6d`) | **OPEN PR #20** (cross-platform CI matrix); branch already in sync with `origin/pr-64-cross-platform-ci-matrix`. |

## Origin Branch Cleanup — REQUIRES USER OK (not executed)

Origin branches that could be deleted on user approval (per policy: origin deletes need user OK):

- `origin/pr-87-docs-refresh-salvage` (PR #48 merged)
- `origin/pr-91-a83-docs-release-notes-update` (PR #50 merged)
- `origin/pr-94-terminal-utility-audits` (PR #51 merged)
- ...and other already-merged-PR head branches still present on `origin`.

Run `gh pr list --state merged --limit 100 --json headRefName` for full list when ready.

## Safety Verification

- All "removed" worktrees confirmed via either:
  - Commits present in `git log origin/main --oneline` (absorbed), OR
  - PR state confirmed via `gh pr view <n>` (merged/closed), OR
  - Unique commits saved as patches under `docs/_archive_2026-05-26/`.
- No in-flight work touched. All 5 KNOWN-IN-FLIGHT worktrees from user brief preserved.
- Open PR branches (#20, #49) preserved.
- `bench-pre-simd` kept conservative pending benchmark-agent status confirmation.
- `pr-95-archive` (parallel agent's worktree) untouched.

## Archive Index

```
docs/_archive_2026-05-26/
├── worktree_pr-81-doc-drift/
│   ├── FINAL_PRE_SIGNON_AUDIT.md
│   ├── README_proposed_update_2026-05-23.md
│   └── RELEASE_NOTES_PROVENANCE.md
├── worktree_spec-corrections/
│   └── 0001-Persona-spec-corrections-*.patch
├── worktree_river-parity-fix/
│   ├── 0001-PR-25-fix-1-mark-test_river_parity_vs_brown-*.patch
│   └── 0002-PR-25-fix-2-pass-concrete-hole-cards-*.patch
└── worktree_w3-5-reversal/
    ├── 0001-PR-38-propagate-persona-verdict-downgrades-*.patch
    ├── 0002-PR-38-spec-audit-framing-retest-prompts-*.patch
    ├── 0003-PR-42-REVERSE-W3.5-downgrade-*.patch
    ├── 0004-PR-42-fix-up-commit-W3_5_TRUE_nash-evidence-*.patch
    └── 0005-PR-42-fix-up-correct-BLOCKED-set-membership-*.patch
```

To restore any archived branch:

```bash
cd /Users/ashen/Desktop/poker_solver
git checkout -b <restore-branch-name> origin/main
git am docs/_archive_2026-05-26/worktree_<name>/*.patch
```
