# v1.6.1 Retest Prompt — W3.4 (Daniel MDF check, BB defense vs half-pot c-bet)

**Status:** Pre-staged. Spawn this prompt as a one-shot agent the moment v1.6.1
ships (PR 33 Python -> Rust delegate + PR 34 off-by-one fix + PR 35
canonicalization + PR 40 acceptance-test fix bundle) and a fresh `.so` is built.

---

## A. Header

- **Workflow:** W3.4 — "MDF check: BB should defend >= MDF vs half-pot c-bet; verify with **per-hand breakdown**." Pro-coach analysis using the Janda formula as ground truth.
- **Persona:** Daniel (pro / coach). Highest-bar persona. Heuristic-driven sanity check on a numerical defense frequency, with per-hand decomposition expected.
- **Prior verdict:** **INCONCLUSIVE-SLOW** on v1.4.1 (~648 s reproduction in the bisection bench; never completed within Daniel's 15-min session budget). PR 22 made the asymmetric-contributions config structurally reachable, but the Python scalar DCFR chance-enum-at-root path did not converge for flop-scope range solves in budget. See `docs/persona_test_results/W3_4_v1_4_1_retest.md` (if logged) and `docs/pr_proposals/v1_5_1_python_rust_delegate.md` §4 (W3.4 row: "INCONCLUSIVE-SLOW (~648 s reproduction; task #174 bisection in flight)").
- **What v1.6.1 changes (the unblock bundle):**
  - **PR 33 (Python -> Rust delegate):** `solve_hunl_postflop(..., initial_hole_cards=())` AND `solve_range_vs_range_rust` route through PR 23's vector-form CFR; flop-scope range solve completes in single-digit seconds instead of 600+s.
  - **PR 34 (off-by-one fix):** `dcfr_vector.rs:651` index-out-of-bounds panic resolved.
  - **PR 35 (canonicalization):** History canonicalization renderer fixed (Brown <-> Rust key format) so per-action diff harness reaches the tolerance comparison.
  - **PR 40 (acceptance test fix):** Locked tolerances reconciled (PR 23 spec §5 Case B); acceptance test PASSES.

## B. Acceptance criteria (PASS definition)

Source: `docs/pr13_prep/persona_acceptance_spec.md` W3.4 + Heuristics §3 (MDF row) + `docs/pr_proposals/v1_4_asymmetric_contributions.md` §4.

The retest **PASSES** iff **all** of the following hold:

1. **Setup is executable on the vector-form path.** `solve_range_vs_range_rust` (PR 23 direct) OR `solve_hunl_postflop(initial_hole_cards=())` (PR 33 auto-delegate) accepts the BB-facing-c-bet config (asymmetric `initial_contributions=(500, 250)`) and returns a non-degenerate strategy without segfault, panic, or `ValueError`. `result["backend"] == "rust_vector"` (or equivalent).
2. **Aggregate defense matches Janda MDF within ±5pp.** Janda formula: `MDF = 1 - bet/(bet+pot)`. For a half-pot c-bet (bet=250 into pot=500): `MDF = 1 - 250/750 = 0.6667`. **Acceptance band: aggregate defense in [Janda - 5pp, Janda + 5pp] = [0.6167, 0.7167]**, where aggregate defense = sum over hero classes of `class_weight * (1 - class.fold_freq)` computed from the vector-form per-hand outputs. Cite the bet size in the report verbatim.
3. **Strategy non-degenerate.** No single action accumulates >= 0.99 of aggregate weight. The aggregated first-decision strategy must show a genuine mix (call + raise + fold all materially present) — pure-pole is a regression flag even if the aggregate number falls in band.
4. **Per-hand breakdown PRESENT (not just aggregate).** REQUIRED for Daniel's coach use case. The report must enumerate per-hand action probabilities for the 8 representative BB defending hand classes listed below (flagged in the test config). Pure aggregate-only is a FAIL on this criterion.

   **8 flagged BB defending hand classes (per-hand breakdown required):**
   1. `KK` (overpair, near-nuts)
   2. `QQ` (top set — value-extracting)
   3. `JJ` (overpair, vulnerable to A-Q-J)
   4. `TT` (mid pair, bluff-catcher)
   5. `AQs` (top pair top kicker)
   6. `KQs` (top pair second kicker, gutshot threat)
   7. `JTs` (open-ender + backdoor flush)
   8. `87s` (backdoor straight + low pair potential — the "marginal flat" the W2b.1 bimodal-range caveat warns about losing)

5. **Wall-clock within budget.** Total retest wall-clock <= 10 min (per task spec; tighter than the 15-min Daniel session budget). Per-spot stays well under the kill-switch; the vector-form path should complete this fixture in **< 2 min** (per v1.5.1 delegate spec §4 W3.4 row: "Should PASS in <2 min").

If (1), (2), or (4) fails, verdict is **FAIL** with the offending criterion named.
If (3) fails but (1)(2)(4) pass, verdict is **FAIL — pure strategy collapse**.
If (5) is the only miss but the spot is converging, verdict is **PARTIAL — perf regression**.

**Range-design caveat (W2b.1 bimodal artifact):** Use a **realistic** BB defending range that includes marginal flat-calling hands (87s, T9s, 65s, AJo, KQo). Pure bimodal (only premiums + air) range produces the **0.025 call_freq artifact** documented in the W2b.1 caveat — defending becomes trivially polarized into call-everything-premium / fold-everything-trash, no decisions of substance. The range below intentionally includes the marginal continuation-defends.

**Aggregator vs vector-form note (important):** Do NOT use `poker_solver.range_aggregator.solve_range_vs_range` (per-combo Pluribus-blueprint aggregator). Use the **vector-form** path so true Nash range-vs-range is preserved. Per the W1.2 deep-stack retest (`docs/persona_test_results/W1_2_v1_5_1_retest_deep_stack.md`): the aggregator's per-class output is the average of full-info 1v1 subgame solves, not Nash — Daniel's MDF check is precisely the case where the structural difference matters.

## C. Time budget

Authoritative source: `docs/pr13_prep/persona_time_budgets.md`.

- **Per-spot engine time (Section 1, "Range-vs-range medium (10x10 hand classes)" cell):** < 2 min target at standard accuracy.
- **Kill-switch:** > 30 min for one spot terminates the test (Section 1).
- **Session total (Section 2, Daniel "Range-vs-range medium" cell):** several spots × < 15 min total. This retest is **one** spot; agent wall-clock cap = **10 min** (hard ceiling per task spec).
- **Agent stall-check:** > 30 min no progress -> report partial findings and STOP.

## D. Paste-ready agent prompt

```
You are a one-shot retest agent for W3.4 (Daniel persona, MDF defense check) on poker_solver v1.6.1.

CONTEXT
- Repo: /Users/ashen/Desktop/poker_solver
- Workflow: W3.4. Heuristic: BB defends >= MDF (~66.7%) vs half-pot c-bet (Janda formula 1 - bet/(bet+pot)). Acceptance: aggregate defense in [Janda - 5pp, Janda + 5pp] = [0.6167, 0.7167]; non-degenerate mix; PER-HAND BREAKDOWN REQUIRED.
- Prior verdict: INCONCLUSIVE-SLOW on v1.4.1 (~648 s on chance-enum-at-root Python path).
- v1.6.1 unblock bundle:
  - PR 33: solve_hunl_postflop(..., initial_hole_cards=()) auto-delegates to Rust vector-form CFR
  - PR 34: dcfr_vector.rs:651 off-by-one panic fixed
  - PR 35: history canonicalization renderer fixed
  - PR 40: acceptance test passes (locked tolerances per PR 23 spec §5 Case B)
- KEY: USE the Rust vector-form path. Either:
  - `from poker_solver._rust import solve_range_vs_range_rust` (direct PR 23 binding), OR
  - `solve_hunl_postflop(config_with_initial_hole_cards_empty_tuple, ...)` (PR 33 auto-delegate)
  Both route through PR 23's vector form. DO NOT use poker_solver.range_aggregator.solve_range_vs_range (per-combo aggregator; not true Nash).
- W2b.1 BIMODAL CAVEAT: BB range must include marginal flats (87s, T9s, AJo, KQo) — pure premium+air bimodal ranges produce the 0.025 call_freq artifact.
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
   `python -c "from poker_solver import HUNLConfig, HUNLPoker, Street; s = HUNLPoker(HUNLConfig(starting_street=Street.FLOP, starting_stack=10000, big_blind=100, initial_pot=750, initial_contributions=(500, 250), initial_board=(0,1,2))).initial_state(); print(s.to_call, s.cur_player, s.street_aggressor)"`
   Expect `250 1 0`. If `0 1 -1` -> BLOCKED.
7. If any precondition fails, write BLOCKED report and STOP.

RETEST EXECUTION

Janda math (cite verbatim in report):
- Bet size: 250 chips (half-pot c-bet)
- Pot before bet: 500 chips
- Janda MDF = 1 - bet/(bet+pot) = 1 - 250/(250+500) = 1 - 250/750 = 1 - 0.3333 = **0.6667** = 66.67%
- Acceptance band: [0.6667 - 0.05, 0.6667 + 0.05] = [0.6167, 0.7167]

Fixture (100 BB SRP — sufficient for MDF; deep stacks not strictly required since the heuristic is about aggregate defense, not sizing dynamic):
- Board: Qs 7h 2d (Q-high dry flop; canonical MDF teaching board).
- Stacks: starting_stack=10000 (**100 BB** — SRP-realistic).
- big_blind=100.
- SRP pre c-bet pot: SB opens to 250, BB calls -> pot=500. SB c-bets half-pot (250). When BB acts: contributions=(500, 250), pot=750.
- HUNLConfig:
  starting_street=Street.FLOP, initial_pot=750, initial_contributions=(500, 250),
  starting_stack=10000, big_blind=100,
  bet_size_fractions=(0.5, 1.0), postflop_raise_cap=3,
  initial_hole_cards=() (REQUIRED for vector-form path),
  initial_board=<card_index tuple for "Qs 7h 2d">.
- hero_range (BB defender; REALISTIC range INCLUDING marginal flats per W2b.1 caveat):
  parse_range("22-JJ,AJs+,KQs,KJs,QJs,JTs,T9s,98s,87s,76s,65s,AJo+,KQo,KJo")
  - Includes: small pairs (22-77 as set-mining floats), broadway pairs (88-JJ), suited Ax (AJs+), suited connectors top-down (87s, 76s, 65s included for W2b.1 caveat), offsuit broadways (AJo+, KQo, KJo).
  - About 70+ combos / ~15 hand classes.
- villain_range (SB c-bettor; realistic ~100 BB SB c-bet on Q-high dry):
  parse_range("22+,A2s+,K9s+,Q9s+,J9s+,T9s,98s,87s,76s,65s,A9o+,KTo+,QTo+,JTo")
- iterations=2000 (matches acceptance test ITERATIONS), alpha=1.5, beta=0.0, gamma=2.0.

Step 1: Vector-form solve
- Preferred entry: `solve_range_vs_range_rust(config_json, iterations=2000, alpha=1.5, beta=0.0, gamma=2.0)`.
- Alternative (PR 33 auto-delegate): `solve_hunl_postflop(config, iterations=2000)` — verify `result.backend == "rust_vector"`.
- Wrap in subprocess.run(..., timeout=600) (10-min subprocess ceiling).
- Record: wall-clock, exploitability (if available), per-hand action probabilities.

Step 2: Aggregate defense computation
- For each hero class in average_strategy keys (parse out via vector-form output format — hole_string|key_suffix):
  - Compute class.fold_freq, class.call_freq, class.raise_freq (sum over raise actions if multiple sizes legal).
- Compute aggregate defense = sum over hero classes of class_weight * (1 - class.fold_freq).
  - class_weight = (number of board-feasible combos in class) / (total combos in hero range).
- Cite the Janda formula in report; report aggregate defense as % with two decimals.
- Acceptance: aggregate defense in [0.6167, 0.7167].

Step 3: PER-HAND breakdown (REQUIRED — explicit list of 8 classes)
For each of these 8 classes, report fold_freq / call_freq / raise_freq (per-size if multiple raise sizes carry mass):
1. KK
2. QQ
3. JJ
4. TT
5. AQs
6. KQs
7. JTs
8. 87s

For each: also note the most likely action (max-prob action) and any class with action prob >= 0.99 (pure-strategy collapse flag).

Step 4: Non-degeneracy check
- Across ALL hero classes (not just the 8 flagged), find any class where one action has prob >= 0.99 (pure-pole).
- If aggregate first-decision distribution has any action >= 0.99: FAIL on criterion (3).

VERDICT
- PASS: criteria (1)-(5) all met. Aggregate defense in band; mix non-degenerate; per-hand breakdown present.
- FAIL: criterion (1), (2), (3), or (4) miss.
- PARTIAL — perf regression: (5) only miss.
- BLOCKED — unblock bundle incomplete: precondition 5 failed.

WRITE REPORT to: /Users/ashen/Desktop/poker_solver/docs/persona_test_results/W3_4_v1_6_1_retest.md
Format (match docs/persona_test_results/W1_2_v1_5_1_retest_deep_stack.md):
- Date, tip (commit hash), version, verdict (PASS / FAIL / PARTIAL / BLOCKED).
- Pre-conditions table.
- Test scenario (board, ranges enumerated verbatim, stack, pot, contributions, iterations, backend, DCFR params).
- Janda math (cited verbatim, with bet size).
- Measurements table:
  - Wall-clock, exploitability, aggregate defense %.
  - PER-HAND table: class | fold | call | raise | dominant action | notes (for all 8 flagged classes; ideally all classes).
- Verdict justification keyed to criteria (1)-(5).
- Range-design note: confirm marginal flats (87s, T9s, AJo, KQo, etc.) are present and their behavior is sensible (mostly-calls, not pure-folds — sanity check against W2b.1 bimodal artifact).
- Caveats / follow-ups.

HARD RULES
- Read-only on poker_solver/, tests/, scripts/, crates/. Driver scripts go in /tmp/.
- NO background processes (subprocess.run is fine; no `&`, no `run_in_background`).
- mkdir -p docs/persona_test_results/ first if missing.
- No git commits, no pushes, no code edits.
- 10-min agent wall-clock budget (hard ceiling).
- Write report REGARDLESS of verdict (even on BLOCKED / STALL / partial).
- Do not invoke other agents.
```

## E. Expected ship-time effect

If PASS, closes the W3.4 loop and Daniel's W3 cohort jumps to **4/5 verified WORKS-NOW** (W3.1, W3.2, W3.3 already PASS per v1.4.0 Daniel retest; W3.5 polarization remains pending dedicated test).

**Residual gaps (NOT closed by v1.6.1):**
- W3.5 (polarization companion) — depends on W2.3 + dedicated test, not bundled here.
- Per-hand breakdown UI surface — Daniel currently extracts this via library / Jupyter inspection; no GUI table yet. Separate PR 10b enhancement (out of v1.6.1 scope).

## F. Open question for orchestrator

**Range-design replication risk:** The W2b.1 bimodal caveat indicates the BB defending range MUST include marginal flats to produce non-trivial decisions. The range above includes 87s/76s/65s/T9s/98s/AJo/KQo/KJo — all flagged as continuation candidates. If the resulting aggregate defense is materially below the [0.6167, 0.7167] band (e.g. < 0.50), it may indicate:
(a) the range is still too premium-heavy (need to add more bluff-catcher floats like Q9s, J9s, 54s), OR
(b) the vector-form CFR is under-converged at 2000 iters (need 5000+).

**Recommendation:** if (2) fails with defense < 0.55, orchestrator should triage between range expansion vs iteration bump before re-classifying as FAIL. Report the exploitability trajectory if `log_every` is available so orchestrator can see convergence.
