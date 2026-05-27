# v1.4.1 Retest Prompt — W2.3 (Sarah, KK on Q-high flop vs villain's c-bet range)

**Status:** Pre-staged. Spawn this prompt as a one-shot agent the moment PR 22
(v1.4.1 — asymmetric initial contributions) ships and a fresh `.so` is built.

---

## A. Header

- **Workflow:** W2.3 — "Solve KK on Q-high flop vs villain's c-bet range." Flop subgame with custom starting ranges.
- **Persona:** Sarah (serious amateur, aspiring pro). Library / Jupyter user; needs `solve_hunl_postflop`-style entry point with custom ranges and asymmetric pot. Tolerates 15 min solves but not implausible output.
- **Prior failure mode:** Pre-v1.4.1, ranges were threaded via `solve_range_vs_range` but the underlying `HUNLPoker.initial_state` ignored asymmetric `initial_contributions` (hardcoded `to_call=0`), so a "facing c-bet" config silently became "opening." Sarah's defender solve returned the opener's strategy.
- **Prior failure timestamp / commit:** Captured in v1.4 design doc 2026-05-23 (`docs/pr_proposals/v1_4_asymmetric_contributions.md` §1 listing W2.3 as one of three blocked workflows). Original W2.3 classification `DOESN'T-WORK` from `persona_acceptance_spec.md`.
- **What v1.4.1 changes:** PR 22 patches `poker_solver/hunl.py:260-282`. With ranges + asymmetric contributions now both honored, Sarah's intended workflow becomes runnable.

## B. Acceptance criteria (PASS definition)

Source: `docs/pr13_prep/persona_acceptance_spec.md` W2.3 + Heuristics §3.

The retest **PASSES** iff **all** of the following hold:

1. **Setup is executable.** `solve_range_vs_range` accepts the custom hero_range / villain_range, the asymmetric contributions config builds and solves without segfault or `ValueError`. `result.position == "defender"`.
2. **KK behaves correctly (heuristic in spec).** From `persona_acceptance_spec.md`: "KK on Q-high is near-100% defend with mixed raises vs bluff-heavy c-bets." Specifically for KK as the **hero class**: `class.fold_freq <= 0.05` AND `class.raise_freq + class.call_freq >= 0.95`. KK should essentially never fold to a half-pot c-bet on Q-high (overpair, one over to villain).
3. **Some mixing on at least one bluff-catcher class.** At least one hero class from `{QJs, JJ, TT, AhQc-or-similar}` shows a non-degenerate mixed strategy (no action >= 0.99) — confirming the solver is not collapsing to pure strategies.
4. **Aggregate defense in MDF band.** Across the full BB range, total defense (`1 - fold`) >= 0.50 (loosening W3.4's 0.55 floor by 5 pts because W2.3 acceptance heuristic emphasizes the per-class KK signal, not the aggregate). This is a secondary check.
5. **Wall-clock within budget.** Total retest wall-clock <= 15 min (Sarah session cell). Per-spot stays under kill-switch.

If (1) or (2) fails, verdict is **FAIL**.
If (3) or (4) fails but (1) and (2) pass, verdict is **PARTIAL — KK signal OK, range-level signal degraded** (loop closes for KK demo; file follow-up).
If (5) is the only miss, verdict is **PARTIAL — perf regression** (per-spot exceeded 2-min cell; file perf bug).

## C. Time budget

Authoritative source: `docs/pr13_prep/persona_time_budgets.md`.

- **Per-spot engine time (Section 1, "Range-vs-range medium (10x10 hand classes)" cell):** < 2 min target at standard accuracy.
- **Kill-switch:** > 30 min for one spot terminates the test (Section 1).
- **Session total (Section 2, Sarah "Range-vs-range medium" cell):** "a few x < 5 min total." This retest is **one** spot; total agent wall-clock cap = **15 min** (use Daniel's cell as ceiling since the test is bookkeeping + one solve, not Sarah's typical study chain).
- **Agent stall-check:** > 30 min no progress -> report partial findings and STOP.

## D. Paste-ready agent prompt

```
You are a one-shot retest agent for W2.3 (Sarah persona, KK on Q-high vs c-bet range) on poker_solver v1.4.1.

CONTEXT
- Repo: /Users/ashen/Desktop/poker_solver
- Workflow: W2.3. Heuristic: KK on Q-high is near-100% defend (fold_freq(KK) <= 0.05); aggregate defense >= 0.50; some mixed strategy on at least one bluff-catcher class.
- Pre-v1.4.1 the postflop engine ignored asymmetric initial_contributions; BB defender solves returned opener strategy. PR 22 fixed hunl.py:260-282.
- Time budget: per-spot < 2 min target, 30 min HARD kill switch, total agent wall-clock <= 15 min.
- Stall-check: > 30 min no progress -> partial report and STOP.

PRE-CONDITION VERIFICATION (do FIRST, BLOCKED on any failure)
1. cd /Users/ashen/Desktop/poker_solver && git rev-parse HEAD (record commit).
2. Confirm `poker_solver/__init__.py` `__version__` is "1.4.1". If still "1.4.0" -> BLOCKED.
3. `python -c "import poker_solver; print(poker_solver.__version__)"` prints 1.4.1.
4. Asymmetric-contributions smoke:
   `python -c "from poker_solver import HUNLConfig, HUNLPoker, Street; s = HUNLPoker(HUNLConfig(starting_street=Street.FLOP, starting_stack=1000, big_blind=100, initial_pot=1500, initial_contributions=(1000, 500), initial_board=(0,1,2))).initial_state(); print(s.to_call, s.cur_player, s.street_aggressor)"`
   Expect `500 1 0`. If `0 1 -1` -> BLOCKED.
5. If any precondition fails, write BLOCKED report and STOP. Do not debug.

RETEST EXECUTION
Build a half-pot c-bet config on a Q-high flop with KK explicitly in the hero range.

Concrete fixture:
- Board: Qs 7h 2d (Q-high dry flop).
- starting_stack=10000, big_blind=100 (100 BB stacks).
- SRP pre c-bet pot: SB opens to 250, BB calls -> pot=500. SB c-bets half-pot (250). When BB acts: contributions=(500, 250), pot=750.
- HUNLConfig:
  starting_street=Street.FLOP, initial_pot=750, initial_contributions=(500, 250),
  starting_stack=10000, big_blind=100,
  bet_size_fractions=(0.5, 1.0), postflop_raise_cap=3,
  initial_board=<card_index tuple for "Qs 7h 2d">.
- hero_range (BB, includes KK explicitly): parse_range("KK,QQ,JJ,TT,99,AQs,AJs,KQs,QJs,JTs,T9s,98s,AQo,KQo")
- villain_range (SB c-bet, bluff-balanced): parse_range("AA,KK,QQ,JJ,TT,AKs,AQs,AJs,KQs,QJs,JTs,T9s,98s,76s,A5s-A2s,K5s,Q5s,J9s,AQo,AJo,KQo")
- solve_range_vs_range(config, hero_range, villain_range, iterations=200, backend="rust", hero_player=1, reps_per_class=1, villain_reps=3).
- Confirm result.position == "defender".

AGGREGATION + VERDICT
- Inspect `result.per_class["KK"]` (or whichever field name `RangeVsRangeResult` uses; check range_aggregator.py for the exact accessor): fold_freq must be <= 0.05.
- Compute aggregate defense = sum(class_weight * (1 - class.fold_freq)) across all hero classes. Must be >= 0.50.
- Look at mixing: enumerate all classes; find at least one with no action >= 0.99 (genuine mix). Bluff-catcher candidates: JJ, TT, QJs, AJs, KQs. Record which class(es) show mixing.
- PASS if all three: KK fold_freq <= 0.05, aggregate >= 0.50, at least one mixed class.
- PARTIAL if KK signal good but aggregate < 0.50 or no class mixed.
- FAIL if KK fold_freq > 0.05 or setup didn't run.
- Wrap the solve in subprocess.run(..., timeout=1800).

WRITE REPORT to: /Users/ashen/Desktop/poker_solver/docs/persona_test_results/W2_3_v1_4_1_retest.md
Format (match docs/pr13_prep/v1_3_2_w1_5_retest.md):
- Date, tip (commit hash), verdict (PASS / FAIL / PARTIAL / BLOCKED).
- Test scenario (board, ranges, stack, pot, contributions, iterations, backend).
- Measurements: wall-clock, KK fold/call/raise freqs, aggregate defense, top 3 mixed classes with their action vectors.
- Verdict justification keyed to criteria (1)-(5).
- Caveats / follow-ups.

HARD RULES
- Read-only on poker_solver/, tests/, scripts/. Driver scripts go in /tmp/.
- mkdir -p docs/persona_test_results/ first if missing.
- No git commits, no pushes, no code edits.
- Stall (> 30 min no progress): partial report "STALL — incomplete" then STOP.
- Do not invoke other agents.
```

## E. Expected ship-time effect

If PASS, closes the W2.3 loop and Sarah's range-level c-bet defense workflow becomes WORKS-NOW. This is the **single most-blocking workflow** in the spec (it gates W3.4, W3.5, and W3.4's polarization companion). W2 cohort moves to **partial coverage** (W2.1, W2.2, W2.5 still pending PR 9; W2.4 batch-solve separate; W2.3 unblocks Sarah's library use case).
