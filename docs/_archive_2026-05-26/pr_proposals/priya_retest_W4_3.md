# v1.4.0 Retest Prompt — W4.3 (Priya: diff vs Brown's noambrown on a novel river spot)

**Status:** READY TO SPAWN against current v1.4.0 main — with caveat that
the spec's "fix" (a public `poker_solver.parity.diff_vs_noambrown(config)
-> DiffReport` API) is NOT shipped. The underlying machinery exists at
`tests/test_river_diff.py` and `poker_solver.parity.noambrown_wrapper`
(per `tests/test_river_diff.py:86`). This retest verifies the workflow
runs via the existing test-coupled path; a PASS does NOT require the
public API to exist (matches spec's `WORKS-BUT-DOCS-CONFUSING`
classification).

---

## A. Header

- **Workflow:** W4.3 — "Diff our solver vs Brown's noambrown on a novel
  river spot." Extend the PR 7 diff test to a user-supplied spot.
- **Persona:** Priya (researcher / developer). API consumer; cares about
  parity / reproducibility / scriptability. Acceptance is
  `WORKS-BUT-DOCS-CONFUSING` per
  `docs/pr13_prep/persona_acceptance_spec.md:71` — "machinery in
  `tests/`, not a library function."
- **Prior failure mode:** No prior W4.x test results exist
  (`docs/persona_test_results/` is empty). This is the FIRST run for
  the Priya cohort. The known gap is the absence of a public
  `poker_solver.parity.diff_vs_noambrown(config) -> DiffReport` —
  Priya's intended ergonomic. Workflow can still be exercised via the
  test-coupled path (`tests/test_river_diff.py` parametrized on her
  novel spot, or a direct call into
  `poker_solver.parity.noambrown_wrapper`).
- **What v1.4.0 ships that makes this runnable today:**
  - `tests/test_river_diff.py` exists and imports
    `poker_solver.parity.noambrown_wrapper` (per
    `tests/test_river_diff.py:86`).
  - `scripts/build_noambrown.sh` exists (per
    `tests/test_river_diff.py:56` `BUILD_SCRIPT = REPO_ROOT / "scripts"
    / "build_noambrown.sh"`).
  - Parity tests gated by `parity_noambrown` marker (per
    `tests/test_river_diff.py:305`).
- **What's NOT shipped:** No public `poker_solver.parity.diff_vs_noambrown`
  function. Priya must reach in via the `parity.noambrown_wrapper`
  module directly or run pytest with a custom parametrize. This is the
  documented gap; the retest verifies the *workflow* (diff a novel
  spot to 1e-4 agreement), not the *ergonomic* (one-line library call).

## B. Acceptance criteria (PASS definition)

Source: `docs/pr13_prep/persona_acceptance_spec.md:71` (W4.3 row) +
Heuristics §3 + `persona_time_budgets.md §1` (river chance-enum cell).

Quoted criteria from the spec:
> "Extend the PR 7 diff test to a user-supplied spot...
> One representative novel-spot diff at standard accuracy: <5 min per
> side, <15 min total (Priya session budget per Section 2). Expect
> agreement to 1e-4."
> (`docs/pr13_prep/persona_acceptance_spec.md:71`)

The retest **PASSES** iff **all** of the following hold:

1. **noambrown binary is built and importable.** `scripts/build_noambrown.sh`
   has been run successfully OR the agent runs it as part of pre-condition
   setup. `from poker_solver.parity.noambrown_wrapper import ...` imports
   without raising. If the build script fails (missing toolchain), the
   verdict is **BLOCKED — toolchain**, NOT FAIL.
2. **Novel-spot config builds and solves on both sides.** A river config
   distinct from the canonical fixture in `tests/test_river_diff.py`
   solves to completion on the `poker_solver` side and on the
   `noambrown` side without segfault or exception.
3. **Agreement to 1e-4.** Per-action exploitability OR strategy
   probabilities (per whichever metric the existing
   `test_river_parity_vs_brown` uses — check
   `tests/test_river_diff.py:308` for the comparison metric) agree
   within `1e-4` absolute tolerance. If the canonical test uses a
   different tolerance (e.g. `1e-3`), use that as the floor; the spec
   text "1e-4" is the target.
4. **Wall-clock within budget.** Per-side < 5 min target; total
   (poker_solver + noambrown + diff) < 15 min (Priya session cell).
   Kill-switch at 30 min per side.
5. **Repeatable on the same novel spot.** Re-running the diff with the
   same seed produces the same numbers (sanity check on determinism;
   this is a Priya-specific concern per spec §1 persona definition
   "cares about end-to-end reproducibility: same config, same seed,
   same answer").

If (1) fails (build/import): **BLOCKED — toolchain** (orchestrator
triage; do not mark FAIL).
If (2) or (3) fails: **FAIL** with the offending criterion named.
If (4) is the only miss but converging: **PARTIAL — perf regression**.
If (5) is the only miss but (1)-(4) pass: **PARTIAL — determinism gap**
(file follow-up; record observed jitter magnitude).

## C. Time budget

Authoritative source: `docs/pr13_prep/persona_time_budgets.md`.

- **Per-side engine time (Section 1, "Single subgame, 5 sizes, 2 streets,
  ~1% pot precision" cell):** 1-5 min target.
- **Total session (Section 2, Priya "Single-spot fixed-cards subgame"
  cell):** "sweeps × <30 min total." For this single-pair diff, cap
  total at **15 min** per spec text.
- **Kill-switch (Section 1):** > 30 min per side terminates.
- **Build step (out of band):** `scripts/build_noambrown.sh` may take
  additional minutes; count it separately and do NOT include in the
  15-min cap. If the build alone exceeds 30 min, BLOCKED — toolchain.
- **Agent stall-check:** > 30 min no progress -> partial report + STOP.

## D. Paste-ready agent prompt

```
You are a one-shot retest agent for W4.3 (Priya persona, noambrown parity diff on a novel river spot) on poker_solver v1.4.0.

CONTEXT
- Repo: /Users/ashen/Desktop/poker_solver
- Workflow: W4.3. Heuristic: a novel river spot solved on both poker_solver and noambrown sides agrees to 1e-4 (or whatever tolerance the canonical test_river_parity_vs_brown uses).
- Gap: no public poker_solver.parity.diff_vs_noambrown(config) -> DiffReport API; reach in via tests/test_river_diff.py's existing scaffolding or poker_solver.parity.noambrown_wrapper directly.
- Time budget: per-side < 5 min target, 30 min HARD kill switch per side, total agent wall-clock <= 15 min (build step excluded).
- Stall-check: > 30 min no progress -> report partial findings and STOP.

PRE-CONDITION VERIFICATION (do FIRST; BLOCKED on any failure)
1. cd /Users/ashen/Desktop/poker_solver && git rev-parse HEAD (record commit).
2. python -c "import poker_solver; print(poker_solver.__version__)" prints 1.4.0+.
3. Check noambrown binary status:
   ls -la scripts/build_noambrown.sh && python -c "from poker_solver.parity.noambrown_wrapper import *; print('wrapper import OK')"
   If the wrapper imports cleanly, skip the build step.
   If ImportError, run: bash scripts/build_noambrown.sh (allow up to 30 min for the build).
   If the build fails (exit != 0 or binary missing afterward), write BLOCKED — toolchain report and STOP.
4. Confirm the existing canonical parity test passes as a sanity check:
   pytest tests/test_river_diff.py -m parity_noambrown -k test_river_parity_vs_brown --no-header -q (timeout 600s).
   If the canonical test fails, that's a v1.4.0 regression — write BLOCKED — canonical parity broken and STOP (do not attempt the novel-spot diff).
5. If any precondition fails, write BLOCKED report and STOP.

RETEST EXECUTION
Construct a NOVEL river spot — distinct from the canonical fixture in tests/test_river_diff.py — and diff both sides.

Concrete novel fixture (different board from the canonical's likely "As 7c 2d Kh 5s" or similar):
- Board: Th 8h 4s Jc 2d (river, 5 cards; mixed-suit, two-pair-possible texture).
- starting_stack=1000, big_blind=100, initial_pot=1000, initial_contributions=(500, 500).
- initial_hole_cards=() (chance-enum-at-root, matches the canonical test's pattern).
- bet_size_fractions=(0.5, 1.0), postflop_raise_cap=3.
- starting_street=Street.RIVER, initial_board=<card_index tuple for "Th 8h 4s Jc 2d">.
- iterations=200, backend="rust", seed=42.

Inspect tests/test_river_diff.py for:
- The exact comparison metric used by test_river_parity_vs_brown (line 308). Likely either per-action exploitability or per-infoset average_strategy delta.
- The wrapper API surface (noambrown_wrapper exports — likely solve_river_spot(spot) -> something comparable to HUNLSolveResult).

Run the diff:
- result_ps = solve_hunl_postflop(config, iterations=200, seed=42)
- result_nb = poker_solver.parity.noambrown_wrapper.<solve_function>(<equivalent config>)
- Compute per-action / per-infoset delta. Report max delta and the offending infoset(s) if any.

Repeatability check:
- Re-run result_ps_2 = solve_hunl_postflop(config, iterations=200, seed=42).
- Assert np.allclose(result_ps.average_strategy[k], result_ps_2.average_strategy[k]) for every k.

AGGREGATION + VERDICT
- PASS if max_delta < 1e-4 AND repeatability holds AND per-side wall-clock < 5 min AND total < 15 min.
- BLOCKED if build/import failed in pre-condition.
- FAIL if max_delta >= 1e-4 (criterion 3 miss) or solve failed on one side (criterion 2 miss).
- PARTIAL — perf regression if criterion 4 is the only miss.
- PARTIAL — determinism gap if criterion 5 is the only miss.
- Subprocess wrapper for each side: subprocess.run(..., timeout=1800).

WRITE REPORT to: /Users/ashen/Desktop/poker_solver/docs/persona_test_results/W4_3_v1_4_0_retest.md
Format (match docs/pr13_prep/v1_3_2_w1_5_retest.md):
- Date, tip (commit hash), version, verdict (PASS / FAIL / PARTIAL / BLOCKED).
- Test scenario (board, stack, pot, contributions, iterations, seed, backend, noambrown build commit if available).
- Measurements: per-side wall-clock, total wall-clock, max_delta, max-delta-infoset, repeatability check result.
- Verdict justification keyed to criteria (1)-(5).
- Caveats / follow-ups (e.g. "public poker_solver.parity.diff_vs_noambrown(config) -> DiffReport API still missing per spec fix-note" — flag, don't block).

HARD RULES
- Read-only on poker_solver/, tests/, scripts/. Driver scripts go in /tmp/.
- The build step (scripts/build_noambrown.sh) is allowed — it's a setup invocation, not a code edit.
- mkdir -p docs/persona_test_results/ first if missing.
- No git commits, no pushes, no code edits to poker_solver/ or tests/.
- Stall (> 30 min no progress): partial report "STALL — incomplete" then STOP.
- Do not invoke other agents.
```

## E. Expected ship-time effect

If PASS, closes the W4.3 loop — Priya cohort goes to 3/3 verified
WORKS-NOW (assuming W4.1 and W4.2 also pass). The spec's fix-note
("expose `poker_solver.parity.diff_vs_noambrown(config) -> DiffReport`")
becomes a docs/API-ergonomic ticket, NOT a blocker — the underlying
parity machinery works; only the one-line library entry-point is
missing.

If BLOCKED — toolchain (build_noambrown.sh fails), W4.3 stays
formally untested until the noambrown build is reproducible. This is
distinct from FAIL and should NOT count against burst-close gating
the same way (orchestrator triage required).

If FAIL with criterion (3) miss (max_delta >= 1e-4), that surfaces a
v1.4.0 parity regression — the canonical fixture passes but a novel
spot diverges, suggesting the parity gate's coverage is too narrow.
This would warrant a v1.4.x patch + parity gauntlet expansion before
burst close.

**Open question for orchestrator:** The tolerance `1e-4` from the spec
text may be stricter or looser than what `test_river_parity_vs_brown`
actually asserts. The agent is instructed to use the existing test's
tolerance as the floor; if that diverges meaningfully from `1e-4`,
the orchestrator may want to reconcile the spec text vs the test code
before declaring PASS.
