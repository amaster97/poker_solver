# Morning Checklist — 2026-05-26

**Session-wrap audit timestamp:** 2026-05-26 (overnight burst close)
**Local HEAD:** `98fb503` (`main`, 1 commit behind `origin/main`)
**Action on wake:** `git fetch && git pull --ff-only origin main` to pick
up PR #68 (`b401f6c` — A83 Nash multiplicity confirmation doc).

---

## Decisions / approvals needed

1. **PR #49 RESUME doc** — **READ FIRST**. Morning hand-off doc.
   URL: https://github.com/amaster97/poker_solver/pull/49
2. **PR #20 cross-platform CI matrix** — open; CI timeout investigation
   complete; rebase branch staged at
   `poker_solver_worktrees/pr-20-timeout`. User decides whether to merge
   as part of v1.8 or defer.
   URL: https://github.com/amaster97/poker_solver/pull/20
3. **PLAN.md prune (PR #89)** — held for review. Branch:
   `pr-89-plan-prune` (worktree at `/private/tmp/wt-pr-89-plan-prune`).
4. **v1.8.0 release tag** — ship script ready (`scripts/release_v1_8_0.sh`,
   executable). Pre-flight blockers documented + resolved.
5. **.dmg LAST build** — once v1.8.0 tag lands, build locally per
   `docs/dmg_build_runbook_2026-05-26.md`.

## Autonomous releases ready to ship (one user command each)

After `git pull --ff-only origin main`:

```bash
# v1.8.0 release (release script bumps pyproject 1.7.0 -> 1.8.0,
# tags, pushes, creates GitHub Release).
git stash --include-untracked && \
  bash scripts/release_v1_8_0.sh --expected-sha b401f6c && \
  git stash pop
```

- After v1.8.0 ships: build the `.dmg` locally per
  `docs/dmg_build_runbook_2026-05-26.md` (run on this M4 Pro; aarch64
  artifact).
- After `.dmg` upload: re-run Marcus persona retest at production scale
  per `feedback_post_ship_persona_retest.md`.

## Confirmed-resolved tonight

- **v1.6.0 .dmg fork-bomb** — RCA + asset pull + warning text + repackaged
  build slot in v1.8.0.
- **A83 deep-cap 33pp gap** — Nash multiplicity empirically confirmed
  via corrected probe (PR #68 merged as `b401f6c`).
  Doc: `docs/a83_nash_multiplicity_confirmed_2026-05-26.md`. **NOT a
  bug** — design diff vs Brown (acceptable per
  `feedback_external_solver_sanity_check.md` +
  `feedback_nash_multiplicity_acceptance.md`).
- **v1.6.1 hold lifted** — folded into v1.8.0 per
  `docs/v1_6_1_ship_hold_review_2026-05-26.md`.
- **v1.7.1 closed as obsolete** — piecewise-merged; no tag.
  See `docs/v1_7_1_tag_decision_2026-05-26.md`.
- **v1.8 SIMD: portability win, not speedup** — corrected to ~1.0×
  honesty per measured M4 Pro wall-clock. Primary value: x86_64
  AVX2/SSE2 dispatch + handwritten floor. Release notes reflect this.
- **Persona test:** 10 PASS / 4 PARTIAL / 2 BLOCKED / 1 FAIL
  (W3.2, W3.3 reclassified up per snapshot in PR #40).
- **Memory pruned** 30 → 25.
- **Worktrees pruned** 23 → 15 (still over ≤10 cap; see "Open / parked").
- **Chance node validation ship-blocker** patched (PR #69 merged
  `2026-05-26T08:22Z`).
- **All key audits + reports persisted on `main`** (no transient findings
  lost to ephemeral worktrees).

## Open / parked

- **PR #20** (CI cross-platform matrix) — user reviews; rebase branch
  staged.
- **PR #89** (PLAN.md prune) — user reviews.
- **v1.8.0 release tag** — user invokes ship script (see above).
- **.dmg LAST build** — user invokes per runbook.
- **v1.9 multiway 3-handed** — out of scope per user.
- **Apple Developer enrollment** — out of scope per user.
- **15 active worktrees** — over ≤10 soft cap. After v1.8.0 ships, prune
  these (each has a merged-or-superseded PR):
  - `pr-102-changelog-shim` (PR #102)
  - `pr-105-a83-supersede` (PR #105 — superseded by PR #68)
  - `pr-108-chance-hotpatch` (PR #108 / merged as #69)
  - `pr-110-a83-confirmed` (PR #110 — merged as #68 / `b401f6c`)
  - `pr-88-v1.8.0-notes` (release notes prep — folded into ship)
  - `pr-92-resume-doc` (PR #92 — superseded by PR #49)
  - `pr-93-tu-ablation` (parked)
  - `pr-95-archive` (untracked-docs archive — superseded by `docs/`
    persistence policy)
  - `pr-98-release-notes-honesty-w32-smoke` (folded into ship)
  - `pr-99-medium-staleness-fix` (parked)
  - `pr-20-timeout` + `rebase-pr-20` (consolidate after PR #20 decides)
  - `bench-pre-simd` (benchmark scratch in `/private/tmp`)
  - `wt-pr-89-plan-prune` (PR #89 — pending review)
  Prune via `git worktree remove <path>` for each merged path.

## Audit verification (this session's checks)

| Check                                    | Expected      | Observed                  | Status |
|------------------------------------------|---------------|---------------------------|--------|
| Open PRs                                 | #49 + #20     | #49 + #20                 | OK     |
| `backup/main` vs `origin/main`           | 0             | 0                         | OK     |
| `backup/integration` vs `origin/main`    | ≥ 0           | 41                        | OK     |
| `HEAD` ahead of `origin/main`            | 0             | 0                         | OK     |
| `origin/main` ahead of `HEAD`            | 0             | 1 (PR #68 — pull on wake) | NOTE   |
| Worktree count                           | ≤ 10          | 15                        | PRUNE  |
| Background `poker_solver.cli` processes  | 0             | 0                         | OK     |
| A83 confirmation doc on `origin/main`    | present       | `09ca2376` blob present   | OK     |
| `pyproject.toml` version (pre-bump)      | 1.7.0         | 1.7.0                     | OK     |
| `docs/v1_8_0_release_notes_DRAFT.md`     | exists        | 26455 bytes               | OK     |
| `scripts/release_v1_8_0.sh` executable   | yes           | `-rwxr-xr-x`              | OK     |
| `docs/dmg_build_runbook_2026-05-26.md`   | exists        | 12377 bytes               | OK     |
| PR #69 (chance node ship-blocker)        | MERGED        | MERGED 08:22Z             | OK     |
| Untracked files                          | high OK       | 265                       | NOTE   |

**Only blocking items: none.** PR #68 merge means local `main` is 1
behind `origin/main`; `git pull --ff-only` handles it. Untracked files
will be handled by release script Phase 0.2 (auto-prompts for stash).
Worktree prune is post-ship cleanup, not a release blocker.

---

*Generated by final session-wrap audit. Read-only audit; no PRs opened
from this artifact. Sleep well.*
