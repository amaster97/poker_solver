# Golden File Check — Rebase Report (2026-05-26)

## Objective

Refresh `refs/pull/N/merge` for 4 PRs whose merge trees still embed the
pre-PR-#39 (buggy) `.github/workflows/golden_check.yml`, so the Golden
File Check stops false-positively failing. Root cause documented in
`docs/golden_file_check_rca_2026-05-26.md` — none of the four PRs
actually touch golden files.

## Execution order (per task brief)

PR #36 (spec doc) -> PR #24 (docs refresh) -> PR #20 (CI matrix) -> PR
#38 (BR/exploitative). Rationale: safest first, riskiest last.

## Per-PR results

### PR #36 — `pr-77-range-fractional-spec` — PUSHED, GREEN, NOT MERGED

- **Branch worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/rebase-pr-36`
- **Pre-rebase HEAD:** `e593830`
- **Post-rebase HEAD:** `38e727a`
- **Rebase:** clean (single commit, no conflicts).
- **Post-rebase diff:** 1 file, 468 lines added — `docs/pr_proposals/v1_range_fractional_frequency_spec.md`.
- **Sanity check:** `git diff --stat` confirmed docs-only.
- **Force-push:** OK (`e593830...38e727a -> pr-77-range-fractional-spec`).
- **CI status (post-push):** `check` (Golden File Check) **SUCCESS**, `bundle-dry-run` **SUCCESS**.
- **Mergeability:** `MERGEABLE`, `CLEAN`.
- **Auto-merge decision:** SURFACED, NOT MERGED. PR body explicitly says
  *"DON'T merge inline — wait for user review."* Honored that
  instruction; would otherwise have squash-merged.

### PR #24 — `pr-69-docs-refresh-v1.7.1-v1.8` — REBASE CONFLICT, NOT PUSHED

- **Branch worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/rebase-pr-24` (worktree retained at pre-rebase HEAD for inspection).
- **Pre-rebase HEAD:** `51da64d` (single commit).
- **Rebase:** **CONFLICT** in `CHANGELOG.md` (lines 423-432) and
  `README.md` (lines 14-27). Auto-merge succeeded everywhere else.
- **Conflict character:** **semantic, not mechanical.**
  - `README.md`: HEAD describes v1.7.0 as *"aggregator->vector wiring +
    CLI subcommands -- PR 43 + PR 44; v1.6.1 held pending A83"*. PR
    side rewrites the same paragraph to *"joint range-Nash API +
    subcommands; v1.7.1 in flight; v1.7.2 / v1.8.0 planned"* AND adds a
    multi-row platform support matrix. Different prose, different
    facts, same anchor.
  - `CHANGELOG.md`: HEAD says *"This is the v1.4.0 ship per the
    stagger-fallback path in the v1.4.0 ship plan (internal mirror)."*
    PR side rewrites to drop *"in the v1.4.0 ship plan (internal
    mirror)"* — i.e., the PR is scrubbing internal-mirror references
    from public CHANGELOG, but main meanwhile got a different rewording
    of the same line.
- **Action:** `git rebase --abort` issued; no push. Per task brief
  ("Anything semantic ... STOP, report to user, skip pushing"), this PR
  is surfaced for manual resolution.
- **CI status:** unchanged (still based on stale merge ref).
- **PR #81 overlap note:** task brief asks to check overlap with
  doc-drift cleanup PR #81 (`gh pr view 81`). **No PR #81 exists on
  GitHub** for this repo — only a local branch `pr-81-doc-drift`. So
  the "if overlap exists, surface" instruction was vacuous; surfacing
  anyway because of the semantic conflict above.

### PR #20 — `pr-64-cross-platform-ci-matrix` — PUSHED, MOSTLY GREEN, NOT MERGED (per task instruction)

- **Branch worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/rebase-pr-20`
- **Pre-rebase HEAD:** `ce951d2`
- **Post-rebase HEAD:** `2226c6d`
- **Rebase:** clean (3 commits, no conflicts).
- **Post-rebase diff:** 2 files, 128 lines added —
  `.github/workflows/ci.yml` (73) and `.github/workflows/lint.yml`
  (55).
- **Sanity check:** YAML syntax of both new workflows validated via
  `python -c "import yaml; yaml.safe_load(...)"` — both **OK**.
- **Force-push:** OK (`ce951d2...2226c6d -> pr-64-cross-platform-ci-matrix`).
- **CI status (post-push):**
  - `check` (Golden File Check) **SUCCESS** -- objective achieved.
  - `bundle-dry-run` **SUCCESS**.
  - `rust` and `python` (lint workflow) **SUCCESS**.
  - The new cross-platform matrix (`test (macos-14 / macos-13 /
    ubuntu-22.04, 3.13, ...)`) is still **IN_PROGRESS / QUEUED** at
    report time. These are exactly the runs this PR adds — they take
    longer (5-10 min full Rust+Python build) on each runner.
- **Mergeability:** `UNKNOWN` (still computing; matrix not yet
  finished).
- **Auto-merge decision:** SURFACED, NOT MERGED. Per task instruction:
  *"for PR #20 (cross-platform CI matrix), DO NOT auto-merge — it
  changes CI infra, surface to user."* Honored.

### PR #38 — `pr-76-exploitative-play` — PUSHED, GREEN, NOT MERGED

- **Branch worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/rebase-pr-38`
- **Pre-rebase HEAD:** `ae52a08`
- **Post-rebase HEAD:** `160f472`
- **Rebase:** clean (single commit, no conflicts).
- **Post-rebase diff:** 4 files, 924 lines added —
  `docs/pr_proposals/v1_exploitative_play_spec.md` (401),
  `poker_solver/cli.py` (+159), `poker_solver/solver.py` (+147),
  `tests/test_exploitative_play.py` (219).
- **Sanity checks:**
  - `python -c "from poker_solver import *"` — clean (no error).
  - No Rust files touched -> `cargo check` skipped per task spec.
  - `pytest tests/test_cli_subcommands.py -k exploit` — 0 tests
    matched, 7 deselected (no exploit-named tests in that file). Ran
    the PR's own `tests/test_exploitative_play.py` instead: **5/5
    passed in 2.39s**
    (`test_br_value_at_least_on_strategy_value_uniform_villain`,
    `test_br_vs_nash_matches_one_sided_exploitability`,
    `test_br_vs_always_fold_villain_exploits`,
    `test_invalid_hero_player_rejected`,
    `test_result_dataclass_structure`).
- **Force-push:** OK (`ae52a08...160f472 -> pr-76-exploitative-play`).
- **CI status (post-push):** `check` (Golden File Check) **SUCCESS**,
  `bundle-dry-run` **SUCCESS**.
- **Mergeability:** `MERGEABLE`, `CLEAN`.
- **Auto-merge decision:** SURFACED, NOT MERGED. PR body says *"Status:
  HOLD label — user scope-added to v1 burst 2026-05-25; awaiting
  maintainer approval before merge."* That is an explicit HOLD; auto-
  merging would override user-set policy. Also, the PR is a design /
  feature surface (147 lines of new solver code + new CLI subcommand +
  4-PR roadmap), not a small / non-design PR — outside the task's
  auto-merge criterion either way.

## Summary table

| PR  | Rebase  | Push | Golden File Check | Other CI | Merged? | Reason not merged |
|-----|---------|------|---------------------|---------|---------|-------------------|
| #36 | clean   | yes  | SUCCESS              | bundle-dry-run SUCCESS | no | body says "DON'T merge inline" |
| #24 | CONFLICT| no   | (unchanged, stale)   | n/a     | no | semantic conflict in CHANGELOG/README; needs manual rewording |
| #20 | clean   | yes  | SUCCESS              | rust/python SUCCESS; matrix in-progress | no | task brief: never auto-merge CI infra |
| #38 | clean   | yes  | SUCCESS              | bundle-dry-run SUCCESS; 5/5 PR tests green locally | no | body has "HOLD label awaiting maintainer approval" |

## Surfaced to user (action needed)

1. **PR #24** — manual rebase needed; you have to choose which prose
   wins in `CHANGELOG.md` line 423ish and `README.md` line 14ish.
   Recommendation: take the PR side for both, since the PR's stated
   intent is *"refresh public docs for v1.7.1/v1.7.2/v1.8"* — but you
   should verify the v1.7.0 description is accurate (PR side says
   v1.7.0 = "joint range-Nash API + subcommands"; main side says
   v1.7.0 = "aggregator->vector wiring -- PR 43 + PR 44"; these may
   both be true depending on whether v1.7.0 covered one or both PRs).
2. **PR #20** — review the cross-platform matrix once it finishes
   running; if green, merge manually. Worth confirming the new CI
   surface is what you want before it lands.
3. **PR #36** — body says "DON'T merge inline"; will hold for your
   review. Spec-doc-only change, no behavior delta.
4. **PR #38** — has explicit "HOLD label awaiting maintainer approval"
   status. Will hold for your approval. Local 5/5 tests passed.

## Worktree state

All four rebase worktrees retained for inspection:

- `/Users/ashen/Desktop/poker_solver_worktrees/rebase-pr-20` (branch `rebase-20-2026-05-26`)
- `/Users/ashen/Desktop/poker_solver_worktrees/rebase-pr-24` (branch `rebase-24-2026-05-26`, still at `51da64d`)
- `/Users/ashen/Desktop/poker_solver_worktrees/rebase-pr-36` (branch `rebase-36-2026-05-26`)
- `/Users/ashen/Desktop/poker_solver_worktrees/rebase-pr-38` (branch `rebase-38-2026-05-26`)

Run `git worktree remove /Users/ashen/Desktop/poker_solver_worktrees/rebase-pr-<N>` and `git branch -D rebase-<N>-2026-05-26` to clean up once each PR is merged or closed.
