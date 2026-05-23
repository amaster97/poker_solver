# PR 10b — Ready-to-fire checklist (one-page, fire-when-PR-9-lands)

**Status:** PRE-STAGED. PR 10b fires the moment PR 9 (HUNL preflop solver)
lands on `integration`. PR 10a is already merged. This checklist is the
one-page action list the orchestrator runs to launch PR 10b on day 0.

**Prerequisites (one-shot, before day 0 of PR 10b):**
- PR 9 must be merged to `integration`. Verify: `git log --oneline integration | grep "Integration: merge PR 9"`.
- PR 9 must expose `on_progress` kwarg on `solve_hunl_preflop` with the
  locked signature `Callable[[int, float, MemoryReport], None] | None = None`
  (per PR 9 §4 amendment derived from `pr10b_spec.md` §3). Verify via the
  `inspect.signature` check in `launch_kickoff_10b.md` §1d.
- PR 9 must expose `target_exploitability` kwarg on `solve_hunl_preflop`
  (PR 5 already exposes it on `solve_hunl_postflop`; PR 9 mirrors it).
  Verify same way. **If absent, halt and ship a tiny PR 9 follow-up on
  integration before PR 10b.**

---

## Day 0 — Launch sequence (orchestrator-side, ~10 min)

1. **Re-read the spec.** Open `pr10b_spec.md` end-to-end. Pay attention to
   §0.1 (Q3 reframe, locked 2026-05-22) — this is new since the original
   kickoff was written and is the dominant new UX delta in PR 10b.

2. **Run pre-flight checks.** Execute `launch_kickoff_10b.md` §1 verbatim:
   ```sh
   cd /Users/ashen/Desktop/poker_solver
   git fetch origin
   git log --oneline integration -20   # confirm PR 9 + PR 10a both reachable
   git rev-parse integration
   git rev-parse origin/integration    # hashes match
   git status                          # clean
   # 1d: confirm on_progress + target_exploitability on solve_hunl_preflop:
   python -c "import inspect; from poker_solver.preflop_solver import solve_hunl_preflop; \
       sig = inspect.signature(solve_hunl_preflop); \
       assert 'on_progress' in sig.parameters; \
       assert 'target_exploitability' in sig.parameters; \
       print('PR 9 surface OK')"
   git rev-parse integration > /tmp/integration_pre_pr_10b.hash
   ```
   If 1d fails, ship a PR 9 follow-up first (do NOT paper over with
   adapter logic in `ui/state.py`).

3. **Create the feature branch.**
   ```sh
   git checkout integration
   git pull --ff-only origin integration
   git checkout -b pr-10b-ui-real-solver
   ```

4. **Spawn the implementation agent (one-shot).** Use the orchestrator's
   `launch_invocations_10b.md` template, with these **mandatory** prompt
   additions (post-2026-05-22, not in the original template):

   - **Spec is `pr10b_spec.md` (updated 2026-05-22 with §0.1 Q3 reframe).**
     Read §0.1 before any code is written.
   - **Q3 reframe is in scope** (slider + advanced expansion + safety
     cap). Mark each tier's placeholder numeric default in source with
     `# TODO(pr-10c-calibration): tune post-measurement`.
   - **Q7 downgrade is in scope** (banner → chip).
   - **Q1, Q2, Q4, Q5, Q6 stay identical** (regression-protected).
   - **Forbidden files** (per `launch_kickoff_10b.md` §3 amended): every
     `ui/views/*.py` EXCEPT `run_panel.py` (which gains the slider).
     `range.py`, `library_browser.py`, `tree_browser.py`, `range_matrix.py`,
     `spot_input.py`, `onboarding.py` are all hands-off.

5. **In parallel, spawn three filler agents** (per the min-5-agents rule):
   - **PR 10c calibration spec drafter** — write a one-page spec for the
     measurement pass that calibrates the 4 tier defaults. Output:
     `docs/pr10c_prep/pr10c_spec.md`. Estimate ~30 min agent runtime.
   - **PR 11 spec polish reviewer** — re-read `pr11_prep/pr11_spec.md`
     for any references to PR 10b that the Q3 reframe might invalidate
     (e.g., "the iter input element"). Output: a delta list, no edits
     yet.
   - **`docs/autonomous_log.md` pruning agent** — ruthless prune of
     pre-v1.0 entries per the continuous-pruning rule. One-shot.

   This satisfies the "≥5 concurrent agents in autonomous sessions"
   floor: implementation + 3 fillers + orchestrator = 5.

---

## Day 0 — Implementation agent's day-1 todo

The implementation agent should produce these in order (per `pr10b_spec.md`
§3 + §4 + §0.1):

1. **Add `on_progress` kwarg to `solve_hunl_postflop`** in
   `poker_solver/hunl_solver.py`. Thread through `_run_with_probe`. PR 5
   tests still pass (kwarg defaults to None).

2. **Replace `ui/state.py`'s mock import** with the dispatch wrapper from
   `pr10b_spec.md` §4. Add the `SOLVE_QUALITY_TIERS` dict and
   `ITER_SAFETY_CAP = 2000` constant. Update `SolveRunner.start` to
   accept `quality_tier: str = "standard"` and translate to
   `target_exploitability`.

3. **Replace iter-count input in `ui/views/run_panel.py`** with the
   4-tier `ui.slider`. Add the live status line below it. Move iter
   input into an "Advanced" `ui.expansion` panel, hard-clamped at 2000.
   Register the three new markers (`solve-quality-slider`,
   `solve-quality-tier-label`, `solve-quality-status-line`).

4. **Downgrade Q7 banner → chip** in `ui/app.py`. Marker swap
   `mock-mode-banner` → `mock-mode-chip`. Chip disappears after first
   successful real solve.

5. **Delete `ui/mock_solver.py`** (and `ui/mock_solver_fixtures.py` if it
   was split). `git rm`.

6. **Update `tests/test_ui_smoke.py`:**
   - Delete the 5 mock-specific tests (per `pr10b_spec.md` §5).
   - Add the 4 new tests (per `pr10b_spec.md` §6): #14, #15, #16, #17.
   - Update at most 1–2 retained tests' locators to find the iter
     input inside the new Advanced expansion.

7. **Update `README.md`** (`## UI (mock)` → `## UI`; remove mock-mode
   paragraph) and **`USAGE.md` §4** (slider-tier framing, note placeholder
   defaults pending PR 10c).

8. **Run `pytest tests/test_ui_smoke.py -v`** — expect 12 tests passing.

9. **Run `pytest -x`** — expect full suite green; the `on_progress` kwarg
   addition must not break PR 5 / 6 / 7 / 9 existing tests.

10. **Manual smoke:** `poker-solver ui`. Load `river_tiny_subgame`. Set
    slider to Draft. Click Solve. Observe real DCFR converges, live
    status line updates, target reached → green badge → loop exits early.

---

## Audit + commit (after implementation agent returns)

11. `sh scripts/check_pr.sh > /tmp/check_pr_output.log 2>&1` — green.

12. Spawn the audit agent with `audit_prompt_final_10b.md` (already
    pre-staged; **review it once before launch** to confirm it covers
    the Q3 reframe — see "Open questions" below).

13. Resolve any must-fix from `audit_report.md`. Likely findings per
    `audit_preprep_10b.md` §1: `on_progress` signature drift (highest
    probability), mock-deletion completeness, Q7 chip styling.

14. Commit using the message template in `commit_message_draft_10b.md`
    (review for slider-reframe wording; may need a one-line addition).

15. Push, merge to `integration` with `--no-ff`, push integration.

16. Update `PLAN.md` §2 (PR 10b row → "landed"), `docs/autonomous_log.md`,
    and `~/.claude/plans/poker_solver.md` (plan-sync rule).

17. **Spawn PR 10c calibration pass** — small measurement PR to set the
    4 tier defaults from real DCFR convergence curves. Spec was drafted
    by the filler agent in step 5; orchestrator launches it post-PR-10b.

---

## Open questions (flag for user / PR 9 implementer)

1. **PR 9 must expose `target_exploitability` kwarg on `solve_hunl_preflop`.**
   Already required for slider dispatch. If PR 9 ships without it, PR 10b
   gains adapter logic. The pre-flight 1d check enforces this. **Owner:
   PR 9 implementer; reviewer: orchestrator at PR 9 audit.**

2. **`audit_prompt_final_10b.md` may need a fifth focus area** covering
   the Q3 slider (currently has 4: UI regression, `on_progress` signature,
   mock-deletion completeness, Q7 chip). Recommend a quick read-through
   to add: "Q3 slider: 4 tiers present; safety cap 2000; iter input
   demoted to Advanced; live status line wired; TODO comments on each
   tier default." **Owner: orchestrator before launch.**

3. **PR 10c calibration spec does not yet exist.** Filler agent in step 5
   drafts it; orchestrator reviews before launching the calibration PR.
   The measurement methodology should be agreed before the agent runs.

4. **Library tier safety cap (2000 vs relaxed e.g., 5000).** §0.1.3
   defers to the calibration pass. PR 10b ships with 2000 uniformly.

5. **USAGE.md §4 wording.** The current draft (2026-05-22) describes the
   UI as "iterations, bet-size menu, target-exploitability mode" — that
   framing is wrong post-Q3-reframe. PR 10b rewrites this. **Owner:
   PR 10b implementation agent.**

---

## Quick-reference paths

- `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10b_spec.md` —
  spec (updated 2026-05-22 with §0.1 Q3 reframe).
- `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/launch_kickoff_10b.md` —
  launch playbook (updated 2026-05-22 to mention slider).
- `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/ready_to_fire_checklist_10b.md` —
  this file.
- `/Users/ashen/Desktop/poker_solver/PLAN.md` §1 "Solver UI control" row.
- `/Users/ashen/Desktop/poker_solver/USAGE.md` §4 (will be rewritten).
- `/Users/ashen/Desktop/poker_solver/ui/views/run_panel.py` — iter input
  → slider swap site.
- `/Users/ashen/Desktop/poker_solver/ui/state.py` — `SOLVE_QUALITY_TIERS`
  dict + dispatch wrapper.
- `/Users/ashen/Desktop/poker_solver/poker_solver/hunl_solver.py` —
  `on_progress` kwarg addition site.
- `/Users/ashen/Desktop/poker_solver/poker_solver/preflop_solver.py` —
  PR 9's solver; must expose `on_progress` + `target_exploitability`.
