# v1.4.1 Retest Prompt — W3.4 (Daniel MDF check, BB defense vs half-pot c-bet)

**Status:** Pre-staged. Spawn this prompt as a one-shot agent the moment PR 22
(v1.4.1 — asymmetric initial contributions) ships and a fresh `.so` is built.

---

## A. Header

- **Workflow:** W3.4 — "MDF check: BB should defend >= MDF vs half-pot c-bet; verify."
- **Persona:** Daniel (pro / coach). Highest-bar persona. Heuristic-driven sanity check on a numerical defense frequency.
- **Prior failure mode:** Pre-v1.4.1, `HUNLPoker.initial_state` hardcoded `to_call=0` and `cur_player=1` for postflop subgames regardless of `initial_contributions`, so a "BB facing half-pot c-bet" config silently degraded to "BB opening" (returned `fold=0.000, call=0.000` opening strategy in the S4 re-test). The defender-facing-bet game was structurally unreachable.
- **Prior failure timestamp / commit:** S4 re-test logged 2026-05-23 against v1.3.1 main tip `88b7a1c` (`docs/pr13_prep/v1_3_1_s4_retest.md`). Re-confirmed in v1.4 design doc (`docs/pr_proposals/v1_4_asymmetric_contributions.md` §1).
- **What v1.4.1 changes:** PR 22 patches `poker_solver/hunl.py:260-282` so callers can pass `initial_contributions=(higher, lower)` and the engine derives `to_call = max - min`, `cur_player = argmin(contributions)`, `street_aggressor = argmax(contributions)`. Symmetric `(500, 500)` is unchanged.

## B. Acceptance criteria (PASS definition)

Source: `docs/pr13_prep/persona_acceptance_spec.md` W3.4 + Heuristics §3 (MDF row) + the v1.4 design doc §4.

The retest **PASSES** iff **all** of the following hold:

1. **Setup is executable.** `HUNLConfig` accepts asymmetric `initial_contributions` for a half-pot c-bet config without raising or segfaulting; `solve_range_vs_range` returns a non-degenerate `RangeVsRangeResult` for `hero_player=1` (BB defender).
2. **BB defense frequency in band.** Aggregated across the BB defending range, total defense (call + raise frequencies, i.e., `1 - fold`) lands in `[0.55, 0.85]`. The theoretical MDF vs half-pot is `1 - 0.5/(0.5+1.0) = 0.667`; the band brackets that anchor with realistic tolerance per `docs/pr_proposals/v1_4_asymmetric_contributions.md` §4 ("defense in [55%, 80%]") expanded to 0.85 upper to allow for equity-rich defenders pushing the upper edge.
3. **Strategy non-degenerate.** The aggregated first-decision strategy is NOT `fold=1.0` AND NOT `call=1.0` AND NOT `raise=1.0` — i.e., a real mix that demonstrates the engine evaluated the facing-bet decision. A pure-pole result is a regression flag even if the number falls in [0.55, 0.85].
4. **Position field correct.** `RangeVsRangeResult.position == "defender"` (per the v1.3.1 fix at `range_aggregator.py:217`).
5. **Wall-clock within budget.** Total retest wall-clock <= 15 min (Daniel's session cell, Section 2; per-spot stays under the kill-switch).

If any of (1)-(4) fails, verdict is **FAIL** with the offending criterion named.
If (5) is the only miss but the spot is converging, verdict is **PARTIAL — perf regression** (file a perf-bug ticket; do not mark loop closed).

## C. Time budget

Authoritative source: `docs/pr13_prep/persona_time_budgets.md`.

- **Per-spot engine time (Section 1, "Range-vs-range medium (10x10 hand classes)" cell):** < 2 min target at standard accuracy.
- **Kill-switch:** > 30 min for one spot terminates the test and triggers a perf-bug investigation (Section 1 framing). **DO NOT chase a converging-but-slow solve past 30 min.**
- **Session total (Section 2, Daniel "Range-vs-range medium" cell):** several spots x < 15 min total. This retest is **one** spot, so the per-spot budget governs; session total budget is the agent's hard wall-clock cap.
- **Agent stall-check (per `feedback_stall_check.md`):** > 30 min of no log/progress = report partial findings and STOP, even if the process is still alive.

## D. Paste-ready agent prompt

```
You are a one-shot retest agent for W3.4 (Daniel persona, MDF defense check) on poker_solver v1.4.1.

CONTEXT
- Repo: /Users/ashen/Desktop/poker_solver
- Workflow: W3.4. Heuristic: BB should defend >= MDF (~66.7%) vs half-pot c-bet. Acceptance: defense in [0.55, 0.85], non-degenerate mix.
- Pre-v1.4.1 this was structurally unreachable (hardcoded to_call=0 in HUNLPoker.initial_state postflop branch). PR 22 made initial_contributions honored.
- Time budget: per-spot < 2 min target, 30 min HARD kill switch, total session wall-clock <= 15 min.
- Stall-check: > 30 min no progress -> report partial findings and STOP.

PRE-CONDITION VERIFICATION (do this FIRST, abort to BLOCKED if it fails)
1. cd /Users/ashen/Desktop/poker_solver && git rev-parse HEAD (record commit).
2. Confirm `poker_solver/__init__.py` `__version__` is "1.4.1" (or whatever the v1.4.1 tip declares); if still "1.4.0" -> BLOCKED, .so not rebuilt.
3. Run `python -c "import poker_solver; print(poker_solver.__version__)"`. Must print 1.4.1.
4. Smoke-test the fix: run `python -c "from poker_solver import HUNLConfig, HUNLPoker, Street; cfg = HUNLConfig(starting_street=Street.FLOP, starting_stack=1000, big_blind=100, initial_pot=1500, initial_contributions=(1000, 500), initial_board=(0,1,2)); s = HUNLPoker(cfg).initial_state(); print(s.to_call, s.cur_player, s.street_aggressor)"`. Expect `500 1 0`. If `0 1 -1` -> BLOCKED, fix did not land.
5. If any precondition fails, write the BLOCKED verdict to the report path below and STOP. Do not debug.

RETEST EXECUTION
Build a half-pot c-bet config on a standard flop with 100 BB SRP-ish ranges. Use `solve_range_vs_range` with `hero_player=1` (BB = defender).

Concrete fixture:
- Board: Qs 7h 2d (Q-high dry flop; standard MDF teaching board).
- starting_stack=10000, big_blind=100 (100 BB).
- SRP pot pre c-bet: SB opened to 250, BB called -> pot = 500. SB c-bets half-pot (250). Contributions when BB acts: SB=500, BB=250.
- HUNLConfig: starting_street=Street.FLOP, initial_pot=750 (500 pre + 250 c-bet), initial_contributions=(500, 250) so P0=SB=aggressor (higher), P1=BB=defender (lower).
- bet_size_fractions=(0.5, 1.0), postflop_raise_cap=3, starting_stack=10000, big_blind=100.
- initial_board=card_index tuple for "Qs 7h 2d" (use poker_solver.card.card_index or parse_card).
- hero_range (BB defender): parse_range("22-JJ,AJs+,KQs,QJs,JTs,T9s,98s,AQo+,KQo") — a realistic ~100 BB BB calling range. About 60+ combos / ~14 hand classes.
- villain_range (SB c-bettor): parse_range("22+,A2s+,K9s+,Q9s+,J9s+,T9s,98s,87s,76s,A9o+,KTo+,QTo+,JTo") — realistic SB c-bet range.
- Call: solve_range_vs_range(config, hero_range, villain_range, iterations=200, backend="rust", hero_player=1, reps_per_class=1, villain_reps=3).
- Confirm result.position == "defender".

AGGREGATION + VERDICT
- Compute weighted defense frequency: sum(class_weight * (1 - class.fold_freq)) across hero classes from result.aggregate, or use result.first_decision_freqs if it sums to a single defender-action distribution. Refer to range_aggregator.py for exact field names.
- PASS if defense_freq in [0.55, 0.85] AND no single action freq >= 0.99.
- FAIL otherwise; record the observed number and the dominant action.
- Wall-clock: subprocess.run with timeout=1800 (30 min hard ceiling) wrapping a small driver script in /tmp.

WRITE REPORT to: /Users/ashen/Desktop/poker_solver/docs/persona_test_results/W3_4_v1_4_1_retest.md
Format (match docs/pr13_prep/v1_3_2_w1_5_retest.md):
- Date, tip (commit hash), verdict (PASS / FAIL / BLOCKED / PARTIAL).
- Test scenario (board, ranges, stack, pot, contributions).
- Measurements table (wall-clock, exploitability if available, defense_freq, dominant actions per top 3 hand classes).
- Verdict justification keyed to criteria (1)-(5).
- Caveats / follow-ups.

HARD RULES
- Read-only on existing code. Do NOT edit poker_solver/, tests/, scripts/.
- You may write the driver script in /tmp/ and the report at docs/persona_test_results/.
- mkdir -p the persona_test_results dir first if it doesn't exist.
- Do not commit, do not push, do not modify git state.
- If you hit > 30 min no progress (stall-check), write a partial report with verdict "STALL — incomplete" and STOP. The orchestrator will triage.
- Do not invoke other agents; do not call ToolSearch for non-essential tools.
```

## E. Expected ship-time effect

If PASS, closes the W3.4 loop and Daniel's W3 cohort jumps to **4/5 verified WORKS-NOW** (W3.1, W3.2, W3.3 already PASS per v1.4.0 Daniel retest; W3.5 polarization remains pending W2.3 + dedicated test).
