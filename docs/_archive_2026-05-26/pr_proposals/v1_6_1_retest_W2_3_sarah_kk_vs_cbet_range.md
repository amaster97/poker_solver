# v1.6.1 Retest Prompt — W2.3 (Sarah, KK on Q-high flop vs villain's c-bet range)

**Status:** Pre-staged. Spawn this prompt as a one-shot agent the moment v1.6.1
ships (PR 33 Python -> Rust delegate + PR 34 off-by-one fix + PR 35
canonicalization + PR 40 acceptance-test fix bundle) and a fresh `.so` is built.

---

## A. Header

- **Workflow:** W2.3 — "Solve KK on Q-high flop vs villain's c-bet range." Flop subgame with custom starting ranges, BB-defender facing a half-pot c-bet.
- **Persona:** Sarah (serious amateur, aspiring pro). Library / Jupyter user; needs the postflop entry point with custom ranges and asymmetric pot. Tolerates 15 min solves; will not tolerate algorithmic nonsense.
- **Prior verdict:** **INCONCLUSIVE-SLOW** on v1.4.1 — the asymmetric-contributions fix (PR 22) made the engine *structurally reachable*, but the chance-enum-at-root path through Python scalar DCFR did not converge within Sarah's 15-min session budget at flop scope. See `docs/persona_test_results/W2_3_v1_4_1_retest.md` (if logged) and the design context in `docs/pr_proposals/v1_5_1_python_rust_delegate.md` §4 (W2.3 row: "INCONCLUSIVE-SLOW (defender solve at flop-scope blew past 90 s probe)").
- **What v1.6.1 changes (the unblock bundle):**
  - **PR 33 (Python -> Rust delegate):** `solve_hunl_postflop(..., initial_hole_cards=())` AND `solve_range_vs_range_rust` both route through PR 23's vector-form CFR. The chance-enum-at-root Python perf cliff is bypassed for flop-scope range solves.
  - **PR 34 (off-by-one fix):** `dcfr_vector.rs:651` index-out-of-bounds panic resolved. Vector-form CFR no longer crashes on boards that triggered the hand-list length mismatch.
  - **PR 35 (canonicalization):** History canonicalization renderer (Brown <-> Rust key format) fixed so coverage-floor checks reach the per-action tolerance comparison instead of failing pre-comparison.
  - **PR 40 (acceptance test fix):** Locked tolerances reconciled to **2e-2** per PR 23 spec §5 Case B (was 5e-3 in v1.5.0); semantic action mapping and range-slot correction land in the diff harness. Acceptance test (`tests/test_v1_5_brown_apples_to_apples.py`) now PASSES on both `dry_K72_rainbow` and `dry_A83_rainbow`.

## B. Acceptance criteria (PASS definition)

Source: `docs/pr13_prep/persona_acceptance_spec.md` W2.3 + Heuristics §3 + the v1.5.1 delegate spec §4 (re-baselined for the vector-form path).

The retest **PASSES** iff **all** of the following hold:

1. **Setup is executable on the vector-form path.** `solve_range_vs_range_rust` (PR 23 direct) OR `solve_hunl_postflop(initial_hole_cards=())` (PR 33 auto-delegate) accepts a Q-high flop config with custom hero / villain ranges and asymmetric contributions, and returns a non-degenerate strategy without segfault, panic, or `ValueError`. `result["backend"] == "rust_vector"` (or equivalent identifier from the auto-delegate path).
2. **KK defend frequency near 100%.** Per `persona_acceptance_spec.md` W2.3 heuristic ("KK on Q-high is near-100% defend with mixed raises vs bluff-heavy c-bets"). Per-hand KK on Q-high vs a c-bet range that does NOT contain QQ-set or made flushes — KK is an essentially-unbeatable overpair (one over to villain's top set only). Acceptance band: **per-hand average defend (call + raise frequencies) for any KK combo >= 0.95**, with `fold_freq <= 0.05`. Equity floor sanity check via `tests/_equity_helpers.equity_vs_range` (if available; else `poker_solver.equity` — see Pre-Conditions): KK equity vs villain's c-bet range >= 0.75 on this dry Q-high flop. Equity that strong combined with pot-odds (`0.5/(0.5+1.0) = 33%` to call) makes folding KK structurally indefensible.
3. **Reraise dynamic visible at deep stack.** Per the W1.2 deep-stack lesson (`docs/persona_test_results/W1_2_v1_5_1_retest_deep_stack.md`): at 200 BB, intermediate raise sizes (`raise_50`, `raise_100`, `raise_200`) carry non-trivial mass on the value-heavy KK class. Acceptance: **KK total reraise frequency (sum of all raise actions including all_in) >= 0.20**, with **at least 2 distinct raise sizes carrying >= 0.05 mass each**. This excludes pure-flat-call collapse and pure-jam collapse.
4. **Some mixing on at least one bluff-catcher class.** At least one weaker class from `{QJs, JJ, TT, AQs, KQs}` shows a non-degenerate mixed strategy (no action >= 0.99). Sanity check that the solver is not collapsing to pure strategies range-wide.
5. **Wall-clock within budget.** Total retest wall-clock <= 15 min (Sarah session cell). Per-spot stays well under the kill-switch; the vector-form path should complete this fixture in **< 2 min** (per PR 23 perf profile + v1.5.1 delegate spec §4 W2.3 row: "Should PASS in <2 min").

If (1) or (2) fails, verdict is **FAIL**.
If (3) fails but (1)(2)(4)(5) pass, verdict is **PARTIAL — KK defend OK, sizing dynamic absent** (file follow-up; the deep-stack regime is structurally less informative than expected).
If (4) fails but (1)(2)(3)(5) pass, verdict is **PARTIAL — pure-strategy collapse on neighbors** (file follow-up).
If (5) is the only miss but the spot is converging, verdict is **PARTIAL — perf regression** (file perf-bug ticket).

**Aggregator vs vector-form note (important):** Do NOT use `poker_solver.range_aggregator.solve_range_vs_range` (the per-combo Pluribus-blueprint aggregator). The aggregator's per-class numbers are an averaged Cartesian product of full-information 1v1 subgame solves — NOT a true range-vs-range Nash mix. The user's W1.2 deep-stack retest demonstrated this is a structural API limitation: the aggregator pooled `fold_freq = AA_rep_fraction` artifact on a hand that would never fold in Nash. Use the **vector-form** path so the imperfect-information range Nash is preserved.

## C. Time budget

Authoritative source: `docs/pr13_prep/persona_time_budgets.md`.

- **Per-spot engine time (Section 1, "Range-vs-range medium (10x10 hand classes)" cell):** < 2 min target at standard accuracy.
- **Kill-switch:** > 30 min for one spot terminates the test (Section 1).
- **Session total (Section 2, Sarah "Range-vs-range medium" cell):** "a few x < 5 min total." This retest is **one** spot; agent wall-clock cap = **10 min** (per task spec; hard ceiling overriding the 15-min session budget).
- **Agent stall-check:** > 30 min no progress -> report partial findings and STOP.

## D. Paste-ready agent prompt

```
You are a one-shot retest agent for W2.3 (Sarah persona, KK on Q-high vs c-bet range) on poker_solver v1.6.1.

CONTEXT
- Repo: /Users/ashen/Desktop/poker_solver
- Workflow: W2.3. Heuristic: KK on Q-high is near-100% defend (fold_freq(KK) <= 0.05); reraise dynamic visible at 200 BB; some mixing on at least one bluff-catcher class.
- Prior verdict: INCONCLUSIVE-SLOW on v1.4.1 (chance-enum-at-root Python path did not converge in budget).
- v1.6.1 unblock bundle:
  - PR 33: solve_hunl_postflop(..., initial_hole_cards=()) auto-delegates to Rust vector-form CFR
  - PR 34: dcfr_vector.rs:651 off-by-one panic fixed
  - PR 35: history canonicalization renderer fixed
  - PR 40: acceptance test passes at 2e-2 tolerance (PR 23 spec §5 Case B)
- KEY: USE the Rust vector-form path. Either:
  - `from poker_solver._rust import solve_range_vs_range_rust` (direct PR 23 binding), OR
  - `solve_hunl_postflop(config_with_initial_hole_cards_empty_tuple, ...)` (PR 33 auto-delegate)
  Both route through PR 23's vector form. DO NOT use poker_solver.range_aggregator.solve_range_vs_range (per-combo aggregator; not true Nash — see W1.2 deep-stack retest).
- Time budget: per-spot < 2 min target, 30 min HARD kill switch, total agent wall-clock <= 10 min.
- Stall-check: > 30 min no progress -> report partial findings and STOP.

PRE-CONDITION VERIFICATION (do FIRST, BLOCKED on any failure)
1. cd /Users/ashen/Desktop/poker_solver && git rev-parse HEAD (record commit).
2. Confirm `poker_solver/__init__.py` `__version__` is "1.6.1". If lower -> BLOCKED.
3. `python -c "import poker_solver; print(poker_solver.__version__)"` prints 1.6.1.
4. Rust vector binding present:
   `python -c "from poker_solver._rust import solve_range_vs_range_rust; print('OK')"`
   If ImportError -> BLOCKED.
5. PR 40 acceptance test PASSES (gates the unblock bundle):
   `pytest tests/test_v1_5_brown_apples_to_apples.py -v -m parity_noambrown -o "addopts=" --timeout=600`
   Both `dry_K72_rainbow` AND `dry_A83_rainbow` must PASS. If either FAILs or panics -> BLOCKED (unblock bundle incomplete).
6. Asymmetric-contributions smoke (still required for the BB-facing-c-bet config):
   `python -c "from poker_solver import HUNLConfig, HUNLPoker, Street; s = HUNLPoker(HUNLConfig(starting_street=Street.FLOP, starting_stack=20000, big_blind=100, initial_pot=750, initial_contributions=(500, 250), initial_board=(0,1,2))).initial_state(); print(s.to_call, s.cur_player, s.street_aggressor)"`
   Expect `250 1 0`. If `0 1 -1` -> BLOCKED.
7. Equity helper available (preferred path):
   `python -c "from tests._equity_helpers import equity_vs_range; print('OK')"`
   If ImportError, fall back to `from poker_solver.equity import equity_vs_range` or `from poker_solver import equity` (record fallback in report).
8. If any precondition fails, write BLOCKED report and STOP.

RETEST EXECUTION

Fixture (DEEP STACKS for reraise dynamic):
- Board: Qs 7h 2d (Q-high dry flop; classic teaching board).
- Stacks: starting_stack=20000 (**200 BB** — required to expose intermediate raise sizes per the W1.2 deep-stack lesson at docs/persona_test_results/W1_2_v1_5_1_retest_deep_stack.md).
- big_blind=100.
- SRP pre c-bet pot: SB opens to 250, BB calls -> pot=500. SB c-bets half-pot (250). When BB acts: contributions=(500, 250), pot=750.
- HUNLConfig:
  starting_street=Street.FLOP, initial_pot=750, initial_contributions=(500, 250),
  starting_stack=20000, big_blind=100,
  bet_size_fractions=(0.5, 1.0, 2.0), postflop_raise_cap=3,
  initial_hole_cards=() (REQUIRED for vector-form path; range info passed via ranges),
  initial_board=<card_index tuple for "Qs 7h 2d">.
- hero_range (BB defender; includes KK explicitly and a representative defending mix):
  parse_range("KK,QQ,JJ,TT,99,88,AQs,AJs,KQs,KJs,QJs,JTs,T9s,98s,87s,76s,AQo,AJo,KQo")
- villain_range (SB c-bettor; bluff-balanced, EXPLICITLY OMITS QQ-set and made-flush combos so KK is structurally near-nuts):
  parse_range("AA,KK,AKs,AQs,AJs,ATs,KQs,KJs,QJs,JTs,T9s,98s,87s,76s,65s,A5s-A2s,K5s,Q5s,J9s,AQo,AJo,KQo,KJo")
  NB: deliberately NO QQ in villain (avoids QQ-set crusher) and no specific flush combos (Q-high rainbow board has no flush threats anyway, so this is documentation/clarity).
- iterations=2000 (matches acceptance test ITERATIONS), alpha=1.5, beta=0.0, gamma=2.0 (matches PR 23 DCFR defaults per test_v1_5_brown_apples_to_apples.py).

Step 1: Equity floor sanity check
- Use `equity_vs_range` (from tests/_equity_helpers if present, else poker_solver.equity) to compute KK equity vs villain_range on board "Qs 7h 2d".
- Pick KK combo: KhKd (no board conflict — only Qs/7h/2d on board so any KK combo works).
- Acceptance: KK equity >= 0.75 (sanity floor; should comfortably exceed).
- Record the exact equity number in the report.

Step 2: Vector-form solve
- Preferred entry: `solve_range_vs_range_rust(config_json, iterations=2000, alpha=1.5, beta=0.0, gamma=2.0)` where config_json is the JSON-serialized HUNLConfig + ranges per the PR 23 binding signature.
- Alternative (PR 33 auto-delegate): `solve_hunl_postflop(config, iterations=2000)` — verify `result.backend == "rust_vector"` post-solve.
- Wrap in subprocess.run(..., timeout=900) (15-min subprocess ceiling; per-spot target is < 2 min).
- Record: wall-clock, exploitability (if available), per-hand action probabilities.

Step 3: KK-class analysis
- Inspect average_strategy for every KK combo (KhKd, KhKc, KhKs, KdKc, KdKs, KcKs — board-blocked KK combos already excluded by vector-form path).
- For each KK combo at the first decision node (hero facing villain's 250 c-bet):
  - Extract action probabilities. Action labels per vector-form output: {fold, call, raise_50, raise_100, raise_200, all_in} (depending on which sizes are legal post-contribution).
  - Compute fold_freq, total defend (1 - fold), total reraise (sum of all raise actions).
- Aggregate KK-class freqs (average over the 6 KK combos).
- Acceptance: KK aggregate fold_freq <= 0.05; KK aggregate reraise >= 0.20; at least 2 raise sizes each >= 0.05 mass.

Step 4: Neighbor-class mixing check
- For at least one class in {QJs, JJ, TT, AQs, KQs}, enumerate combos in average_strategy, average action probs.
- Find at least one neighbor class with no action >= 0.99 (genuine mix). Record which class(es) show mixing and their action vectors.

VERDICT
- PASS: criteria (1)-(5) all met.
- FAIL: criterion (1) or (2) miss.
- PARTIAL — sizing dynamic absent: (3) miss only.
- PARTIAL — pure-strategy collapse on neighbors: (4) miss only.
- PARTIAL — perf regression: (5) only miss.
- BLOCKED — unblock bundle incomplete: precondition 5 failed.

WRITE REPORT to: /Users/ashen/Desktop/poker_solver/docs/persona_test_results/W2_3_v1_6_1_retest.md
Format (match docs/persona_test_results/W1_2_v1_5_1_retest_deep_stack.md):
- Date, tip (commit hash), version, verdict (PASS / FAIL / PARTIAL / BLOCKED).
- Pre-conditions table (each gate + observed result).
- Test scenario (board, ranges enumerated verbatim, stack, pot, contributions, iterations, backend, DCFR params).
- Equity floor measurement.
- Measurements: wall-clock, KK aggregate fold/call/raise-by-size freqs, neighbor-class mixed strategies, max action prob per class.
- Verdict justification keyed to criteria (1)-(5).
- Caveats / follow-ups (e.g. residual API ergonomics, CLI gap unchanged).

HARD RULES
- Read-only on poker_solver/, tests/, scripts/, crates/. Driver scripts go in /tmp/.
- NO background processes (subprocess.run is fine; no `&`, no `run_in_background`).
- mkdir -p docs/persona_test_results/ first if missing.
- No git commits, no pushes, no code edits.
- 10-min agent wall-clock budget (hard ceiling; abort with PARTIAL "wall-clock exceeded" if exceeded).
- Write report REGARDLESS of verdict (even on BLOCKED / STALL / partial — orchestrator needs the data).
- Do not invoke other agents.
```

## E. Expected ship-time effect

If PASS, closes the W2.3 loop and Sarah's range-level c-bet defense workflow becomes **WORKS-NOW** via the vector-form path. This unblocks the W2 cohort's most-blocking workflow (per `docs/pr_proposals/v1_4_1_retest_W2_3_sarah_kk_vs_cbet_range.md` §E: "the single most-blocking workflow in the spec").

**Residual gaps (NOT closed by v1.6.1):**
- The Pluribus-blueprint aggregator (`poker_solver.range_aggregator.solve_range_vs_range`) is still the per-combo Cartesian-averaged workaround; its `fold > 0` artifact on must-defend hands remains structural. Sarah's actual workflow uses the vector-form path so this is not a blocker, but a documentation update flagging "use `solve_range_vs_range_rust` for true Nash; aggregator is approximate" should land in the user guide (separate task).
- CLI surface gap for range-vs-range solves (no `poker-solver flop --hero-range ... --villain-range ...` subcommand) is unchanged; Sarah uses the library path.

## F. Open question for orchestrator

**Tolerance/iteration sensitivity:** The retest uses `iterations=2000` to match the acceptance test's locked ITERATIONS constant. If the W2.3 fixture is materially larger than the acceptance test fixtures (Q-high flop SRP has ~50 hero hands x ~80 villain hands, vs the acceptance test's 50-55 hands per player), 2000 iterations may under-converge. **Recommendation:** if exploitability at 2000 iters > 0.05 BB/hand, bump iterations to 5000 and re-run; flag the per-iter convergence trajectory in the report so orchestrator can decide whether to widen the iteration default.
