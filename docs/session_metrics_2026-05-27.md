# Session Metrics — 2026-05-27 Autonomous Burst

Compact glance-at-it-when-you-wake-up snapshot. All numbers verified
against `gh pr list` / `git log` / `git show` / `gh release view` —
no estimates. Window: ~2026-05-27 04:00 EDT (= 08:00 UTC) → 06:30
EDT (= 10:30 UTC). Earliest landed commit `37e5be1` (PR #78 purge,
04:15 EDT); latest `4a096f3` (PR #100 decision matrix, 06:16 EDT).

---

## Headline

**v1.8.0 SHIPPED** at `8a9c8d2` (`chore: bump version to 1.8.0`,
2026-05-27 05:18 EDT). Public release published 2026-05-27 05:18
EDT: https://github.com/amaster97/poker_solver/releases/tag/v1.8.0
(per `gh release view v1.8.0 --json publishedAt`). Backup mirror
(`https://github.com/amaster97/poker_solver_private.git`) synced —
both remotes configured per `git remote -v`.

---

## Counts

- **PRs merged today:** **22** (per `gh pr list --state merged
  --jq '.[] | select(.mergedAt > "2026-05-27T00:00:00Z")'`):
  #75, #76, #77, #78, #79, #80, #81, #82, #83, #84, #85, #86,
  #87, #88, #90, #91, #92, #93, #95, #96, #98, #100.
- **PRs open (held for review):** **7** (per `gh pr list --state
  open`): #20, #49, #89, #94, #97, #99, #101.
- **Commits to main today:** **21** (per `git log --oneline
  --since='2026-05-27 04:00' main | wc -l`).
- **Cumulative diff vs session start (`79d6534`..HEAD):** **399
  files changed, +77,812 / −581** (per `git diff 79d6534 HEAD --stat`).
- **Sub-agents spawned:** rough estimate ~40-60 across the burst
  (orchestrator + per-PR ship-agents + QA iter agents + persona
  retest agents + audit agents).
- **Worktrees:** current = **8** (per `git worktree list`); WAKEUP
  doc reports session pruned from ~12 → 6 active. The 8 figure
  includes 1 main + 7 feature trees (2 added post-WAKEUP for
  in-flight work).
- **Remote stale branches pruned:** **36** (per
  `docs/WAKEUP_2026-05-27.md` line 65, "Remote stale branches: 36
  deleted via gh API"). Current remote branch count = 35 (per
  `git for-each-ref refs/remotes/origin | wc -l`).
- **Docs archived:** **249** files moved into
  `docs/_archive_2026-05-26/` in PR #92 (per `git ls-tree -r
  d5b2ced docs/_archive_2026-05-26/ | wc -l`). Commit body cites
  243 (input set was 243; 6 already-tracked files joined them →
  249 final). PR #92 stats: +53,828 / −0 across 100 file ops
  (`gh pr view 92 --json additions,deletions,files`).

---

## Engine correctness validated (post-purge regression scan)

All claims cite QA findings doc
`docs/perpetual_qa_findings_2026-05-27.md`:

- **Convention purge (PR #78, `37e5be1`) self-consistent.**
  Constant-sum invariant `u[0]+u[1] == initial_pot/bb` holds at every
  terminal leaf across 21 leaves × 3 postflop configs × 7 action
  sequences (QA iter 9 test 1, lines 1758-1771).
- **Cross-tier Python/Rust DCFR bit-identical.** Fresh Leduc fixture
  @ 500 iter, max per-cell diff = 0.0 (QA iter 9 test 6, line 1823).
- **SIMD codepath deterministic across runs.** NEON path on
  `_rust.cpython-313-darwin.so` arm64 (QA iter 9 environment,
  line 1749; iter 5 determinism re-tested line ~38).
- **Convergence monotonic on Kuhn + Leduc.** DCFR (α=1.5, β=0,
  γ=2.0): Kuhn `gv_err` 1.63e-2 → 1.06e-5 across 10/100/1k/10k iters;
  Leduc `exp` 1.68e-1 → 2.12e-2 across 10/100/1k iters (QA iter 10
  tests 1+2, lines 2043-2065).
- **Multiprocess + thread-safe.** 4-worker `spawn`-context pool all
  return bit-identical Kuhn strategies + gv (QA iter 10 test 5, lines
  2089-2098).
- **EV(action) invariance gauntlet implemented + merged.** PR #98
  (`3cc5eba`) adds `tests/test_ev_invariance_gauntlet.py` —
  Nash-invariant cross-solver check on K72 + A83 deep-cap fixtures
  per Brown 2019 Thm 2.
- **v1.5 Brown apples-to-apples PASSES both K72 + A83** under
  4-layer reframed gate (per
  `docs/v1_5_brown_post_purge_numbers_2026-05-27.md` lines 16-26).
  Verdict: `PASSED` end-to-end runtime 272.91s; K72 L1 max 1.703,
  A83 L1 max 1.813.

---

## .dmg ready

- Built locally: `/Users/ashen/Desktop/poker_solver/dist/Poker-Solver-1.8.0-arm64.dmg`
- Size: **48 MB** (50,120,860 bytes per `ls -la`).
- SHA256: `fcdb2d005d183c9474024ca40333dc2be22d920b1b347626035a8f3a4bc2e6d7`
  (per `shasum -a 256`).
- No fork-bomb (verified post PR #42 fix, QA iter 9 test 3
  `pyinstaller_entry_import_smoke`, lines 1788-1797).
- **NOT uploaded** to v1.8.0 release assets (per
  `gh release view v1.8.0 --json assets` = empty). Per your
  explicit deferral.

---

## What's still on you (open PRs + decisions)

Held for your eyes:

- **#20** — `feat(ci): cross-platform CI matrix for v1.8 prep`
  (rebased on post-PR-91 main; blocked only by #89 dep).
- **#49** — `docs: RESUME_2026-05-26 morning hand-off` (8 refresh
  passes done).
- **#89** — `fix(build): patch Brown's subgame_config.cpp for GCC
  11 incomplete-type build`.
- **#94** — `docs(persona): post-v1.8.0 production-scale retest
  results (W2.1, W2.3, W2.5, W3.4, W3.5, W4.2, M)`.
- **#97** — `docs: pre-flight merge-order analysis for 4 open PRs`.
- **#99** — `proposal: DCFR α-guard options (v1.8.1 candidate)` —
  addresses HIGH-1 from WAKEUP.
- **#101** — `docs: disclose v1.8.0 GUI mock-mode in user-facing
  locations (post-PR-94 audit)`.

Two HIGH findings flagged for v1.8.1 (per
`docs/WAKEUP_2026-05-27.md` lines 40-41):

- **HIGH-1**: DCFR `α=0` silently produces non-Nash strategy
  (Kuhn gv −0.093 vs correct −0.056). Locked production
  hyperparameter is α=1.5; question is whether to restrict API or
  document. Candidate for v1.8.1. Addressed by PR #99 proposal.
- **HIGH-2**: Vector-form Rust RvR
  (`_rust.solve_range_vs_range_rust`) unusable interactively on
  river (>14 min for 200 iter on 1326-hand vector). Candidate for
  v1.8.1 docs-only iter-limit guidance.

---

## What's NOT done (per explicit deferral)

- v1.8.0 `.dmg` asset upload — you said "literally last thing to
  do" and want to eyeball the build first.
- Task #31 (preflop chained orchestrator) + Task #32 (full-tree
  preflop RvR) — multi-day v1.9+ scope per WAKEUP line 57.

---

## Summary table

| Metric | Value | Source |
| --- | --- | --- |
| PRs merged | 22 | `gh pr list --state merged --jq ...` |
| PRs open | 7 | `gh pr list --state open` |
| Commits to main | 21 | `git log --since='2026-05-27 04:00'` |
| Files changed (cumulative) | 399 | `git diff 79d6534 HEAD --stat` |
| Net lines (+/−) | +77,812 / −581 | `git diff 79d6534 HEAD --stat` |
| Docs archived (PR #92) | 249 | `git ls-tree -r d5b2ced docs/_archive_2026-05-26/` |
| Worktrees current | 8 | `git worktree list` |
| Remote stale branches pruned | 36 | `docs/WAKEUP_2026-05-27.md` line 65 |
| .dmg size | 48 MB | `ls -la dist/` |
| .dmg SHA256 | `fcdb2d00...e6d7` | `shasum -a 256` |
| v1.8.0 ship SHA | `8a9c8d2` | `gh release view v1.8.0` |
| HIGH findings flagged | 2 | `docs/WAKEUP_2026-05-27.md` lines 40-41 |
| QA iters completed | 1-6 + 8 + 9 + 10 (iter 7 died from 529 storm) | `perpetual_qa_findings_2026-05-27.md` headers |

---

## Notes / caveats

- WAKEUP doc reports 12→6 worktrees during the session; current
  count is 8 because 2 trees were added post-WAKEUP for in-flight
  work (#88 release-notes prep, #20 slow-markers).
- Iter 7 of perpetual-QA died from a 529 storm (per iter 8 doc
  line 18); iter 8 is in a standalone file rather than the master.
- PR #92's commit body says "243 stale docs"; final directory
  count is 249 because the input set merged with 6 already-tracked
  load-bearing docs that got moved alongside. Both numbers are
  correct for what they describe.
- Cumulative `+77,812` lines is dominated by PR #92's bulk
  archive move (53,828 of the +77,812).
- "Sub-agents spawned" is an estimate range (no event log
  available); orchestrator + ship-agents + QA agents + persona
  agents + audit agents over a ~2.5 hr window.
