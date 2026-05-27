# v1.6.1 Retest Prompt — W4.3 (Priya, parity diff vs Brown's noambrown on a novel river spot)

**Status:** Pre-staged. Spawn this prompt as a one-shot agent the moment v1.6.1
ships (PR 33 Python -> Rust delegate + PR 34 off-by-one fix + PR 35
canonicalization + PR 40 acceptance-test fix bundle) and a fresh `.so` is built.

---

## A. Header

- **Workflow:** W4.3 — "Diff our solver vs Brown's noambrown on a novel river spot." Extend the PR 7 / PR 23 / PR 28 diff test to a Priya-controlled spot.
- **Persona:** Priya (researcher / developer). API consumer; cares about parity / reproducibility / scriptability. Acceptance is `WORKS-BUT-DOCS-CONFUSING` per `docs/pr13_prep/persona_acceptance_spec.md:71`.
- **Prior verdict:** **BLOCKED-PERF on v1.4.0/v1.4.1** — `tests/test_river_diff.py::test_river_parity_vs_brown` timed out at ~660 s on the chance-enum-at-root Python path (per `docs/persona_test_results/W4_3_v1_4_0_retest.md:111-137`). Also **FAILED on v1.5.0** (per `docs/v1_5_0_brown_acceptance_result.md`): both `dry_K72_rainbow` (coverage-floor 53.3% < 80%) and `dry_A83_rainbow` (Rust panic `dcfr_vector.rs:651` off-by-one) failed pre-tolerance gates.
- **What v1.6.1 changes (the unblock bundle):**
  - **PR 33 (Python -> Rust delegate):** `solve_hunl_postflop(..., initial_hole_cards=())` AND `solve_range_vs_range_rust` route through PR 23's vector-form CFR; river chance-enum-at-root completes in seconds, not 660s.
  - **PR 34 (off-by-one fix):** `dcfr_vector.rs:651` index-out-of-bounds panic resolved (the `dry_A83_rainbow` crash from v1.5.0 acceptance test).
  - **PR 35 (canonicalization):** History canonicalization renderer fixed — Brown's `b<amount>` action shape and Rust's emitted `<hole_string>|<key_suffix>` format now align. Coverage-floor check no longer fails pre-comparison.
  - **PR 40 (acceptance test fix):** Locked per-action tolerance reconciled to **2e-2** per PR 23 spec §5 Case B (was 5e-3 in v1.5.0); semantic action mapping (Brown's bet-shape vs Rust's action-id) and range-slot correction (Brown's hand-list ordering vs Rust's vector-slot indexing) land in the diff harness. Acceptance test (`tests/test_v1_5_brown_apples_to_apples.py`) now PASSES on both `dry_K72_rainbow` and `dry_A83_rainbow`.
- **maturin universal2 build:** the v1.5.0+ build chain produces a universal2 (arm64 + x86_64) `.so`, ensuring Priya's bench reproducibility on either Apple silicon or Intel macOS without re-compile drift.

## B. Acceptance criteria (PASS definition)

Source: `docs/pr13_prep/persona_acceptance_spec.md:71` (W4.3 row) + Heuristics §3 + `tests/test_v1_5_brown_apples_to_apples.py` locked thresholds (PR 40 reconciled).

The retest **PASSES** iff **all** of the following hold:

1. **noambrown binary built and importable.** `references/code/noambrown_poker_solver/cpp/build/river_solver_optimized` exists and is executable (already built per task #197, see `docs/v1_5_0_brown_acceptance_result.md` §1). `from poker_solver.parity.noambrown_wrapper import ...` imports without raising. If the binary is missing, run `scripts/build_noambrown.sh` (idempotent — will reuse existing build per the v1.5.0 acceptance doc).

2. **Canonical PR 40 acceptance test PASSES.** Gates the unblock bundle:
   `pytest tests/test_v1_5_brown_apples_to_apples.py -v -m parity_noambrown -o "addopts=" --timeout=600`
   Both `dry_K72_rainbow` AND `dry_A83_rainbow` parametrized spots must PASS within the locked tolerances:
   - **`COVERAGE_FLOOR = 0.80`** (>=80% of Brown's canonical histories appear in Rust's emitted keys after PR 35 canonicalization).
   - **`PER_ACTION_TOL = 2e-2`** (per PR 40 fix; was 5e-3 in v1.5.0 per PR 23 spec §5 Case B).
   - Iterations: `ITERATIONS = 2000`, `DCFR_ALPHA = 1.5`, `DCFR_BETA = 0.0`, `DCFR_GAMMA = 2.0`.

3. **Novel-spot diff agrees to 2e-2 per-action.** Construct a NOVEL river spot distinct from the two canonical fixtures (`dry_K72_rainbow` Ks 7h 2d 4c Jh and `dry_A83_rainbow` Ah 8c 3d Tc 6s). Use the **`dry_Q52_mixed`** spot from `tests/data/river_spots.json` (board `Qh 5s 2c 9d 4h`, dry rainbow texture, bet sizes 0.75/1.5 with all-in) — already in the fixture but NOT covered by `COVERED_SPOT_IDS` in the acceptance test (per `tests/test_v1_5_brown_apples_to_apples.py:115`), so it's "novel" relative to the locked acceptance gates. Per-action agreement: max abs diff < `2e-2` across the matched-history set (per PR 40 spec).

4. **Repeatable on the same novel spot.** Re-running the diff with the same seed produces the same numbers (Priya-specific reproducibility concern per `persona_acceptance_spec.md` §1: "cares about end-to-end reproducibility: same config, same seed, same answer").

5. **Wall-clock within reasonable budget.** Per-side < 5 min target; total (poker_solver + noambrown + diff) < **10 min** (per task spec — hard ceiling overriding the 15-min Priya session budget for this retest). Kill-switch at 30 min per side. **Vector-form Rust path should complete the novel spot in single-digit seconds** (per PR 23 perf profile + v1.5.1 delegate spec §4 W4.3 row: "Should PASS in <60 s").

If (1) fails: **BLOCKED — toolchain** (orchestrator triage).
If (2) fails: **BLOCKED — unblock bundle incomplete** (PR 33/34/35/40 not all landed).
If (3) fails: **FAIL — novel-spot parity miss**, with max-diff infoset(s) named.
If (4) fails but (1)-(3) pass: **PARTIAL — determinism gap** (file follow-up; record observed jitter magnitude).
If (5) is the only miss but converging: **PARTIAL — perf regression**.

## C. Time budget

Authoritative source: `docs/pr13_prep/persona_time_budgets.md`.

- **Per-side engine time (Section 1, "Single subgame, 5 sizes, 2 streets, ~1% pot precision" cell):** 1-5 min target.
- **Total session (Section 2, Priya "Single-spot fixed-cards subgame" cell):** "sweeps × <30 min total." For this single-pair diff, cap total at **10 min** per task spec.
- **Kill-switch (Section 1):** > 30 min per side terminates.
- **Build step (out of band):** `scripts/build_noambrown.sh` is idempotent and should be a no-op (binary already built per task #197). If it runs, count separately and exclude from the 10-min cap.
- **Agent stall-check:** > 30 min no progress -> partial report + STOP.

## D. Paste-ready agent prompt

```
You are a one-shot retest agent for W4.3 (Priya persona, noambrown parity diff on a novel river spot) on poker_solver v1.6.1.

CONTEXT
- Repo: /Users/ashen/Desktop/poker_solver
- Workflow: W4.3. Heuristic: a novel river spot solved on both poker_solver and noambrown sides agrees to 2e-2 per-action (per PR 40 fix; PR 23 spec §5 Case B).
- Prior verdict: BLOCKED-PERF on v1.4.0/v1.4.1 (Python chance-enum path timed out at 660s); FAILED on v1.5.0 (dry_K72 coverage 53.3% < 80%; dry_A83 Rust panic at dcfr_vector.rs:651).
- v1.6.1 unblock bundle:
  - PR 33: solve_hunl_postflop(..., initial_hole_cards=()) auto-delegates to Rust vector-form CFR
  - PR 34: dcfr_vector.rs:651 off-by-one panic fixed (resolves dry_A83 crash)
  - PR 35: history canonicalization renderer fixed (resolves dry_K72 53.3% coverage)
  - PR 40: acceptance test passes at 2e-2 tolerance (PR 23 spec §5 Case B); semantic action mapping + range-slot correction
- maturin universal2 build ensures reproducibility on arm64 + x86_64 macOS.
- Time budget: per-side < 5 min target, 30 min HARD kill switch per side, total agent wall-clock <= 10 min (build step excluded).
- Stall-check: > 30 min no progress -> report partial findings and STOP.

PRE-CONDITION VERIFICATION (do FIRST, BLOCKED on any failure)
1. cd /Users/ashen/Desktop/poker_solver && git rev-parse HEAD (record commit).
2. Confirm `poker_solver/__init__.py` `__version__` is "1.6.1". If lower -> BLOCKED.
3. `python -c "import poker_solver; print(poker_solver.__version__)"` prints 1.6.1.
4. Rust vector binding present:
   `python -c "from poker_solver._rust import solve_range_vs_range_rust; print('OK')"`
   If ImportError -> BLOCKED.
5. noambrown binary present and executable:
   `ls -la /Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/build/river_solver_optimized`
   `bash /Users/ashen/Desktop/poker_solver/scripts/build_noambrown.sh` (idempotent; expect "already up-to-date")
   `python -c "from poker_solver.parity.noambrown_wrapper import *; print('wrapper import OK')"`
   If any fail -> BLOCKED — toolchain.
6. PR 40 acceptance test PASSES (gates the unblock bundle):
   `pytest tests/test_v1_5_brown_apples_to_apples.py -v -m parity_noambrown -o "addopts=" --timeout=600`
   Both `dry_K72_rainbow` AND `dry_A83_rainbow` must PASS at the locked tolerances (PER_ACTION_TOL=2e-2 after PR 40 fix, COVERAGE_FLOOR=0.80).
   If either FAILs or panics -> BLOCKED (unblock bundle incomplete).
7. If any precondition fails, write BLOCKED report and STOP.

RETEST EXECUTION

Novel-spot fixture: **`dry_Q52_mixed`** from `tests/data/river_spots.json` (NOT in acceptance test's COVERED_SPOT_IDS — see test_v1_5_brown_apples_to_apples.py:115).
- Board: Qh 5s 2c 9d 4h (river, 5 cards quoted verbatim from fixture; dry-ish mixed-suit texture).
- Pot: 1000 (per fixture).
- Stack: 9500 (per fixture).
- Bet sizes: [0.75, 1.5] with include_all_in=true (per fixture).
- Max raises: 3 (per fixture).
- Hands: enumerate both players' hand lists verbatim from the fixture entry (50 hands per player; load via the same fixture loader used by test_river_diff.py).
- DCFR params: iterations=2000, alpha=1.5, beta=0.0, gamma=2.0 (matches acceptance test).
- Seed: 42 (Priya determinism concern; lock for repeatability).

Step 1: poker_solver vector-form solve
- Preferred entry: direct `_rust.solve_range_vs_range_rust(config_json, iterations=2000, alpha=1.5, beta=0.0, gamma=2.0)`.
- Alternative (PR 33 auto-delegate): `solve_hunl_postflop(config, iterations=2000)` with `initial_hole_cards=()`; verify `result["backend"] == "rust_vector"`.
- Wrap in subprocess.run(..., timeout=900) (15-min subprocess ceiling).
- Record: wall-clock, average_strategy dict (full), iterations consumed.

Step 2: noambrown solve
- Call `poker_solver.parity.noambrown_wrapper.<solve_function>` with the equivalent spot config (board, ranges, pot, stack, sizes).
- Reference the same loader used by `tests/test_v1_5_brown_apples_to_apples.py` (look at how it constructs the noambrown input from the SpotSpec — inspect the test file to verify the loader API for `dry_Q52_mixed`).
- Wrap in subprocess.run(..., timeout=900).
- Record: wall-clock, returned strategy histories, format.

Step 3: per-action diff (semantic action mapping + range-slot correction per PR 40)
- Apply the SAME canonicalization renderer used by the acceptance test (post-PR 35 fix). DO NOT roll your own — use the helper from `tests/test_v1_5_brown_apples_to_apples.py` (or wherever PR 35 lands the renderer).
- For each (hand, history) key present in BOTH outputs:
  - Compute per-action absolute diff.
  - Record max abs diff and the offending (hand, history, action) triple.
- Verify coverage: matched_keys / brown_keys >= 0.80 (COVERAGE_FLOOR; sanity check that the canonicalization renders the new spot too, not just the locked ones).
- Acceptance: max abs diff < 2e-2 AND coverage >= 0.80.

Step 4: Repeatability check
- Re-run Step 1 with the same seed=42, iterations=2000.
- Assert np.allclose(result_v1.average_strategy[k], result_v2.average_strategy[k]) for every k within 1e-9 (Rust vector-form CFR should be bit-identical for same seed; if not, it's a determinism bug).
- If allclose fails: record observed jitter magnitude.

VERDICT
- PASS: criteria (1)-(5) all met. max_diff < 2e-2, coverage >= 0.80, repeatability holds, per-side < 5 min, total < 10 min.
- BLOCKED — toolchain: precondition 5 failed (noambrown build/import).
- BLOCKED — unblock bundle incomplete: precondition 6 failed (PR 40 acceptance test FAIL/PANIC).
- FAIL — novel-spot parity miss: max_diff >= 2e-2 OR coverage < 0.80.
- PARTIAL — determinism gap: criterion (4) only miss; record jitter.
- PARTIAL — perf regression: criterion (5) only miss but converging.

WRITE REPORT to: /Users/ashen/Desktop/poker_solver/docs/persona_test_results/W4_3_v1_6_1_retest.md
Format (match docs/persona_test_results/W1_2_v1_5_1_retest_deep_stack.md):
- Date, tip (commit hash), version, verdict (PASS / FAIL / PARTIAL / BLOCKED).
- Pre-conditions table (each gate + observed; especially: PR 40 acceptance test status — both dry_K72_rainbow and dry_A83_rainbow PASS/FAIL with timing).
- Test scenario (board, hand lists verbatim from fixture for both players, pot, stack, bet sizes, iterations, seed, backend, DCFR params, noambrown build commit).
- Measurements:
  - poker_solver wall-clock.
  - noambrown wall-clock.
  - Total wall-clock.
  - Matched history count / Brown history count / coverage %.
  - Max per-action abs diff + offending triple.
  - Repeatability check result (allclose to 1e-9? observed jitter if not).
- Verdict justification keyed to criteria (1)-(5).
- Caveats / follow-ups (note: public `poker_solver.parity.diff_vs_noambrown(config) -> DiffReport` API still missing per spec fix-note — flag, don't block).

HARD RULES
- Read-only on poker_solver/, tests/, scripts/, crates/, references/. Driver scripts go in /tmp/.
- The build step (scripts/build_noambrown.sh) is allowed — it's idempotent setup, not a code edit.
- NO background processes (subprocess.run is fine; no `&`, no `run_in_background`).
- mkdir -p docs/persona_test_results/ first if missing.
- No git commits, no pushes, no code edits.
- 10-min agent wall-clock budget (hard ceiling; abort with PARTIAL "wall-clock exceeded" if exceeded).
- Write report REGARDLESS of verdict (even on BLOCKED / STALL / partial — orchestrator needs the data).
- Do not invoke other agents.
```

## E. Expected ship-time effect

If PASS, closes the W4.3 loop and Priya cohort moves to **3/3 verified WORKS-NOW** (assuming W4.1 and W4.2 also pass per earlier Priya retests). The spec's fix-note ("expose `poker_solver.parity.diff_vs_noambrown(config) -> DiffReport`") becomes a docs/API-ergonomic ticket, NOT a blocker — the underlying parity machinery + the canonical 2-spot acceptance test now both pass.

**Residual gaps (NOT closed by v1.6.1):**
- Public `poker_solver.parity.diff_vs_noambrown(config) -> DiffReport` library API still absent; Priya reaches in via `parity.noambrown_wrapper` directly. Documented `WORKS-BUT-DOCS-CONFUSING` per spec, NOT a blocker.
- Parity gauntlet coverage: this retest extends to one novel spot (`dry_Q52_mixed`). A broader sweep across the full `river_spots.json` (16 spots) would strengthen the parity claim but is out of v1.6.1 scope (separate orchestrator decision: spawn a full-sweep agent post-PASS).

## F. Open question for orchestrator

**Novel-spot definition ambiguity:** The retest uses `dry_Q52_mixed` from the existing fixture file (board: Qh 5s 2c 9d 4h) as the "novel" spot because (a) it's NOT in the acceptance test's `COVERED_SPOT_IDS = ("dry_K72_rainbow", "dry_A83_rainbow")`, and (b) using a fixture-defined spot avoids hand-rolling a new SpotSpec that might trigger range-canonicalization edge cases the test harness doesn't handle. **If orchestrator prefers a truly hand-rolled novel spot** (e.g., a 4-flush-on-board board not present in the fixture), specify the alternative board and hand lists before spawning — the prompt's Step 2 noambrown call assumes the fixture loader API works for the spot ID. **Default recommendation: use `dry_Q52_mixed` as specified.**

**Tolerance reconciliation note:** The task spec says "2e-2 per PR 40 fix (PR 23 spec §5 Case B)". The v1.5.0 acceptance test has `PER_ACTION_TOL: float = 5e-3` per `tests/test_v1_5_brown_apples_to_apples.py:118`. The retest's precondition 6 PASS-gate runs that test verbatim, so whichever value PR 40 LANDS in main is what the retest will enforce. **If PR 40 leaves `PER_ACTION_TOL = 5e-3` and only fixes the canonicalization, the retest's Step 3 should still match the locked test value, NOT hard-code 2e-2.** The implementer of PR 40 should reconcile the spec text ("2e-2") with the locked test constant before merge; the retest agent is instructed to use whatever value is locked in main at retest time.
