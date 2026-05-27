# PR 107 — Invalidation surface report (2026-05-26)

**Task:** Surface Gate 4 200K v2 + A83 Track A invalidation finding;
propose correct A83 probe approach.
**Owner:** Doc agent (this report).
**Source-of-truth analysis (consumed):**
`docs/a83_track_a_results_analysis_2026-05-26.md` (agent `aaf54c9`).
**PR opened:** https://github.com/amaster97/poker_solver/pull/65
(branch `pr-107-invalidation-surface`).
**Companion update:** PR #49 / branch `pr-92-resume-doc` (force-pushed
with rebase + invalidation section).

---

## Executive summary

Two experiments completed earlier in the session were INVALID and have
been surfaced honestly across the three required surfaces:

1. **Gate 4 200K v2 (river phase):** 186-byte empty-strategy log
   output. Reported figures = uniform-random fallback. Turn phase
   killed mid-run at ~60 min.
2. **A83 Track A `--regret-init-noise` 200K nohup probe (2 runs):**
   bit-identical 186-byte logs. The "bit-identical baseline+perturbed"
   outcome was two no-op runs, NOT Nash convergence evidence.

**Root cause (single, mechanical):** the CLI invocation
`solve --hunl-mode postflop --backend rust ...` without
`--initial-hole-cards` constructs an `HUNLConfig` with
`initial_hole_cards = None`. `HUNLState::chance_outcomes`
(`crates/cfr_core/src/hunl.rs:533-568`) returns `Vec::new()`
defensively in that case. The scalar CFR loop's chance branch
iterates over zero outcomes, returns `[0.0, 0.0]`, and never inserts
a single infoset into `strategy_sum`. Reported exploitability is then
recomputed against the empty strategy map and falls back to
`uniform(n_actions)` on every cache miss (`exploit.rs:472-475`).

**Critical distinction (preserved across all three surfaces):** the
`--regret-init-noise` flag IMPLEMENTATION (PR #53, commit `29d608e`)
is CORRECT. Three unit tests in `dcfr_vector.rs::tests` PASS
(zero-reproducibility, epsilon-perturbs-strategy on multi-action tree,
seed-changes-outcome). The CLI INVOCATION PATH is what's broken.

**Therefore:** the Nash multiplicity hypothesis for the A83 33pp
Brown-vs-ours bottom-pair-Ace deep-cap gap REMAINS UNTESTED.

---

## Section-by-section deliverables

### 1. PR #49 RESUME doc update (`pr-92-resume-doc`, force-pushed)

File: `docs/RESUME_2026-05-26.md`.
Commit: `f0ffa5e` on `pr-92-resume-doc`.
Push: `git push --force-with-lease` (rebase on top of latest main `8fa5b5b`).

Changes:

- **TODO status table:**
  - Task #23 (Gate 4 200K turn invocation reconstruction) → flagged
    INVALID with cross-reference to Invalidated experiments section.
  - Task #27 (A83 Track A `--regret-init-noise` nohup probe) → flagged
    INVALID with the same cross-reference. Note that the flag
    IMPLEMENTATION is correct; the nohup invocations are invalid.
  - Note on task numbering: the user task brief referenced Task #10 +
    Task #26; the actual matching task IDs in the TODO table are #23
    + #27. Flagged the actually-matching tasks.
- **New "Invalidated experiments" section** (before audit-trail block):
  - Mechanical root cause walked through (CLI invocation → empty
    chance_outcomes → empty strategy_sum → uniform-random
    exploitability fallback).
  - Note on 2026-05-25 Gate 4 v1 `5.28e-14 mbb/g` result: flagged as
    PROVISIONAL pending re-run via correct entrypoint (same bug may
    have applied).
  - Distinction between flag implementation (correct) and CLI
    invocation path (broken).
  - Statement that Nash multiplicity hypothesis REMAINS UNTESTED.
  - Recommended follow-up via `solve_range_vs_range_nash`.
- **Recommended morning workflow:**
  - Step 4 reframed: re-run Gate 4 200K via correct entrypoint OR
    skip and use v1.5 Brown acceptance baseline as canonical pass.
  - Step 10 added: optional CLI hardening (fail-fast guard for
    `hole_cards=None && starting_street=River` in `validate_config`).
- **"TWO MAJOR FINDINGS" section:** updated the Track A line under
  Finding 1 to reflect invalidation honestly (was: "still in flight";
  now: "INVALID due to CLI no-op bug; Nash multiplicity remains
  leading hypothesis, empirical probe pending").

**PR #49 status:** HELD for user review per task constraints. No
auto-merge.

### 2. v1.8.0 release notes draft tightening (`pr-107-invalidation-surface`)

File: `docs/v1_8_0_release_notes_DRAFT.md` in the pr-107 worktree.
Commit: `db7c5cb` on `pr-107-invalidation-surface`.

Changes (single bullet edited in "Known issues remaining" section,
plus one new bullet added):

- **Nash multiplicity framing tightened.** The original phrasing read
  Nash multiplicity at deep-cap indifference manifolds as part of the
  "remaining per-cell residual ... combined effect" of two causes,
  framed as if both were established. Rewrote as: "Nash multiplicity
  at indifference manifolds in the deep-cap subgame — leading
  hypothesis, NOT YET empirically confirmed." Added the explicit
  caveat about the v1 probe invalidation. Cross-references to
  `a83_track_a_results_analysis_2026-05-26.md` and
  `a83_followup_correct_experiment_2026-05-26.md` added.
- **Added Gate 4 200K result PROVISIONAL bullet.** Explicitly marks
  the `5.28e-14 mbb/g` figure (from the 2026-05-25 Gate 4 v1 run) as
  PROVISIONAL pending re-run, since the same CLI shape was used and
  may have hit the same no-op path. Notes that Gate 4 200K does NOT
  block the v1.8.0 release boundary (v1.5 Brown apples-to-apples
  acceptance test, Dry-run #10, is the canonical pass).

**Note:** the draft was NOT claiming "Gate 4 200K river PASS" or
"A83 Nash multiplicity is empirically confirmed" outright — the
language was already framed structurally. But the wording was tighter
than warranted, and the new framing carries the explicit caveat.

### 3. New follow-up doc: `docs/a83_followup_correct_experiment_2026-05-26.md`

Commit: `db7c5cb` on `pr-107-invalidation-surface` (same commit as #2).

Contents (8 sections):

1. **Background — why the v1 probe was invalid.** Mechanical recap
   from the source-of-truth doc.
2. **Correct entrypoint — `solve_range_vs_range_nash`.** Why the
   vector-form RvR path is the right one (matches the entrypoint used
   by the original 33pp divergence measurement in
   `tests/test_range_vs_range_rust_diff.py`; respects
   `--regret-init-noise` via `dcfr_vector.rs:207-241`).
3. **Proposed Python script skeleton.** ~80-line driver
   (`scripts/a83_track_a_probe_v2.py`) that calls
   `solve_range_vs_range_nash` with two noise settings, dumps JSON,
   computes per-cell L1 deltas, applies decision rule. Alternative:
   parametric pytest extension to `test_range_vs_range_rust_diff.py`
   with `@pytest.mark.slow`.
4. **Sanity check before launching.** 200-iter smoke that asserts
   `len(result.average_strategy) > 0` on both runs before launching
   the full probe. (This sanity check would have caught the v1
   no-op.)
5. **Wall-clock budget table:** 5K iters ~6-10 min; 50K iters
   ~60-100 min; 200K iters ~4-6 hr (NOT recommended). Recommends
   starting at 5K.
6. **Decision rule.** Symmetric: `max_per_cell_L1_delta ≥ 0.05` →
   Nash multiplicity confirmed (A83 closes Type-B); `≤ 0.01` → Nash
   uniqueness likely (re-open root-cause investigation for an
   unidentified third cause); `0.01-0.05` → inconclusive, iterate.
7. **Why not just relaunch via the CLI.** Two CLI repair options
   considered but both are independent of the Track A retest.
   Retest uses Python entrypoint directly.
8. **References.** All upstream pointers.

---

## Workflow execution log

- `git fetch origin` → done.
- `git worktree add -b pr-107-invalidation-surface
  /Users/ashen/Desktop/poker_solver_worktrees/pr-107-invalidation
  origin/main` → done (created from `origin/main` HEAD `8fa5b5b`).
- pr-92-resume-doc worktree: `git fetch origin main` + `git rebase
  origin/main` → done (4 commits rebased clean, no conflicts).
- All 3 task items applied to pr-107 worktree.
- Commit on pr-107: `db7c5cb` (2 files changed, 392+ / 12-).
- Commit on pr-92: `f0ffa5e` (1 file changed, 82+ / 10-).
- Force-pushed pr-92 with `--force-with-lease` (rebase target).
- Pushed pr-107 with `-u` upstream tracking.
- PR opened: #65 at
  https://github.com/amaster97/poker_solver/pull/65.

## Auto-merge status

- **PR #49 (pr-92-resume-doc):** HELD for user review per task
  constraints. No auto-merge.
- **PR #65 (pr-107-invalidation-surface):** CI status monitor armed;
  auto-merge attempt deferred to monitor completion. See "CI status"
  below for the live outcome.

## CI status (PR #65) — final

All 3 checks PASS (`bundle-dry-run: pass`, `check: pass`,
`check: pass`). Auto-merge executed per Stage-3 rules.

**PR #65 merged** at 2026-05-26T08:10:25Z (squash + delete-branch).
Local worktree at `/Users/ashen/Desktop/poker_solver_worktrees/pr-107-invalidation`
removed; local branch `pr-107-invalidation-surface` deleted.

---

## Honest framing — distinguishing the two findings

Per task constraint ("Be honest about the invalidation. Don't
soft-pedal."):

- The Gate 4 200K v2 + A83 Track A nohup results are **uniform-random
  fallback**, not converged Nash equilibria. The earlier reports that
  treated them as substantive results were wrong.
- The Nash multiplicity hypothesis for A83 was the **leading
  hypothesis**, not a settled finding. The session-end framing that
  treated A83 as "closed pending Track A confirmation" was correct
  in framing but wrong in the actual confirmation — Track A did not
  confirm anything.
- The `--regret-init-noise` flag itself (PR #53) is correct and
  ships in v1.8.0 as planned. The IMPLEMENTATION is not at fault.
- The CLI shape (`solve --hunl-mode postflop` without
  `--initial-hole-cards`) is a real CLI gap: it silently produces a
  no-op rather than failing fast. This affects any future agent or
  user who tries the same shape. The fail-fast guard in
  `validate_config` is a real product improvement and should ship.

---

## Files touched

| Path | Branch | Commit | Action |
|---|---|---|---|
| `docs/v1_8_0_release_notes_DRAFT.md` | `pr-107-invalidation-surface` | `db7c5cb` | Edit (Nash multiplicity framing + new Gate 4 PROVISIONAL bullet) |
| `docs/a83_followup_correct_experiment_2026-05-26.md` | `pr-107-invalidation-surface` | `db7c5cb` | New file (8-section follow-up proposal) |
| `docs/RESUME_2026-05-26.md` | `pr-92-resume-doc` | `f0ffa5e` | Edit (Tasks #23/#27 + new Invalidated experiments section + workflow update + Major Findings section update) |
| `docs/invalidation_surface_pr_107_2026-05-26.md` | (main; report file) | (workspace) | This report |

---

## References

- Source-of-truth analysis: `docs/a83_track_a_results_analysis_2026-05-26.md`
- v1 probe setup (background): `docs/a83_track_a_setup_2026-05-26.md`
- Original 33pp investigation: `docs/a83_deep_cap_root_cause_investigation.md`
- Follow-up proposal (new): `docs/a83_followup_correct_experiment_2026-05-26.md`
- Flag implementation: PR #53 / commit `29d608e`
- Flag unit tests: `crates/cfr_core/src/dcfr_vector.rs::tests` (3 tests, all PASS)
- No-op mechanism: `crates/cfr_core/src/hunl.rs:533-568`,
  `crates/cfr_core/src/hunl_solver.rs:265-282`,
  `crates/cfr_core/src/exploit.rs:472-475`
- Memory rule guiding framing: `feedback_nash_multiplicity_acceptance.md`
