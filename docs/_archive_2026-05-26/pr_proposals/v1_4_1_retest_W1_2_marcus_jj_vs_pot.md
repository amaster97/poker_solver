# v1.4.1 Retest Prompt — W1.2 (Marcus, JJ on As Tc 5d Jh 8s vs pot-sized river bet)

**Status:** Pre-staged. Spawn this prompt as a one-shot agent the moment PR 22
(v1.4.1 — asymmetric initial contributions) ships and a fresh `.so` is built.

---

## A. Header

- **Workflow:** W1.2 — "Villain bet pot on river. I have JJ on As Tc 5d Jh 8s. Was calling right?" Single-spot river bluff-catcher MDF for a rec player.
- **Persona:** Marcus (casual rec). Hard interactive-response gate: < 30 s at standard accuracy or he abandons. Single CLI / library invocation expected.
- **Prior failure mode:** Per `persona_acceptance_spec.md` W1.2 — `default_tiny_subgame()` hard-codes a different fixture; CLI `--hunl-mode postflop` accepts `--board`/`--stacks` but not `--hero` / `--villain` / `--starting-ranges`. ALSO, even building the config in Python, asymmetric `initial_contributions` (for "villain bet pot, hero faces decision") was ignored by `HUNLPoker.initial_state` pre-v1.4.1, so the workflow was structurally unreachable.
- **Prior failure timestamp / commit:** Classification `DOESN'T-WORK` in `persona_acceptance_spec.md`; re-listed in v1.4 design doc 2026-05-23 (`docs/pr_proposals/v1_4_asymmetric_contributions.md` §1).
- **What v1.4.1 changes:** PR 22 patches `poker_solver/hunl.py:260-282` so `initial_contributions=(pot, 0)` correctly puts hero on `to_call=pot`, `cur_player=1` (hero seat), `street_aggressor=0` (villain). The CLI surface gap (no `--hero` / `--villain-range`) is **not** addressed by PR 22 — see Section E "dependencies" — so this retest exercises the **library** path, not the CLI, and verifies the engine can now answer the question even if the CLI ergonomics are still pending.

## B. Acceptance criteria (PASS definition)

Source: `docs/pr13_prep/persona_acceptance_spec.md` W1.2 + Heuristics §3 (MDF row, bluff-to-value ratio row).

The retest **PASSES** iff **all** of the following hold:

1. **Setup is executable.** A fixed-cards river config — hero JJ, villain a representative range, pot-sized bet via asymmetric `initial_contributions` — builds and solves without segfault or `ValueError`. Cur_player must be the defender (hero seat = 1), to_call = bet size.
2. **JJ call frequency in band.** Per spec heuristic ("Expected call freq ~= 1.0; MDF vs pot = 50%; JJ well above median"): on a board `As Tc 5d Jh 8s`, hero JJ holds **second-nuts trips** (JJJ set, dominated only by AA / QQ-as-runner-runner / specific straights). JJ should call >= 0.90 facing a polarized pot-sized river bet. Acceptance band: **JJ call_freq in [0.85, 1.00]** (fold_freq <= 0.15). The 0.85 lower bound accommodates equilibrium villain bluff frequencies just under MDF; pure-fold (call_freq <= 0.10) is the clear FAIL signal.
3. **Bluff-catcher mix on neighbor class.** At least one weaker hero class evaluated in parallel — e.g., **TT** (second pair) — shows a non-degenerate strategy (`0.05 <= call_freq <= 0.95`). This confirms the engine evaluated the decision rather than rubber-stamping a pure strategy across the board.
4. **Wall-clock within Marcus's gate.** Per-spot wall-clock < **30 s** at standard accuracy on the Rust tier (Marcus's interactive-response feature gate; `persona_time_budgets.md` Section 1 "Single-spot fixed-cards subgame"). This is **stricter** than W3.4 / W2.3 because Marcus's persona has the tightest gate. If JJ alone is single-combo + single-villain-combo, the spot is `Single-spot fixed-cards subgame (<30 s)`, not range-vs-range; use single-combo solve, not range aggregation.

If (1) or (2) fails, verdict is **FAIL**.
If (3) fails but (1)(2)(4) pass, verdict is **PARTIAL — JJ signal OK, neighbor mix absent** (file follow-up; loop conditionally closed for the JJ-specific question).
If (4) fails (wall-clock >= 30 s) but (1)-(3) pass, verdict is **PARTIAL — engine correct, Marcus's gate breached** (file perf bug; loop NOT closed for Marcus persona — for rec users the speed IS the feature).

## C. Time budget

Authoritative source: `docs/pr13_prep/persona_time_budgets.md`.

- **Per-spot engine time (Section 1, "Single-spot fixed-cards subgame" cell):** < **30 s** target at standard accuracy. This is the **Marcus interactive-response feature gate** and is the dominant constraint for this workflow.
- **Kill-switch:** > 30 min on a single spot (Section 1) — but for W1.2, anything over 30 s is already a persona FAIL on criterion (4).
- **Session total (Section 2, Marcus "Single-spot fixed-cards subgame" cell):** 1 spot x < 30 s (then abandon). The retest is one spot; agent wall-clock cap = **5 min** (allows for `.so` import, smoke check, single solve, and report write).
- **Agent stall-check:** > 30 min no progress -> partial report and STOP. (In practice this should never fire for W1.2 — if the spot doesn't return in < 60 s, the Marcus gate is already failed.)

## D. Paste-ready agent prompt

```
You are a one-shot retest agent for W1.2 (Marcus persona, JJ vs pot-sized river bet) on poker_solver v1.4.1.

CONTEXT
- Repo: /Users/ashen/Desktop/poker_solver
- Workflow: W1.2. Single-spot river bluff-catcher. Marcus's gate: <30s per-spot. Heuristic: JJ on As Tc 5d Jh 8s vs pot bet -> call_freq in [0.85, 1.00].
- Pre-v1.4.1: asymmetric initial_contributions ignored by engine. PR 22 fixed hunl.py:260-282.
- KEY: this is single-combo, fixed-cards. Use `solve_hunl_postflop` with `initial_hole_cards=(JJ_combo,)` OR build a single-combo `solve_range_vs_range` with hero={"JJ"} and villain a representative range. Prefer solve_hunl_postflop with fixed hole cards for the strict Marcus <30s gate.
- Time budget: per-spot <30s = Marcus's interactive-response gate. Agent wall-clock cap: 5 min total.

PRE-CONDITION VERIFICATION (do FIRST, BLOCKED on any failure)
1. cd /Users/ashen/Desktop/poker_solver && git rev-parse HEAD (record commit).
2. Confirm `poker_solver/__init__.py` `__version__` is "1.4.1". If still "1.4.0" -> BLOCKED.
3. `python -c "import poker_solver; print(poker_solver.__version__)"` prints 1.4.1.
4. Asymmetric-contributions smoke for river (pot-sized bet, hero faces):
   `python -c "from poker_solver import HUNLConfig, HUNLPoker, Street; s = HUNLPoker(HUNLConfig(starting_street=Street.RIVER, starting_stack=1000, big_blind=100, initial_pot=2000, initial_contributions=(1500, 500), initial_board=(0,1,2,3,4))).initial_state(); print(s.to_call, s.cur_player, s.street_aggressor)"`
   Expect `1000 1 0` (villain bet 1000 of a 1000-pot, hero faces). If `0 1 -1` -> BLOCKED.
5. If any precondition fails, write BLOCKED report and STOP.

RETEST EXECUTION
Concrete fixture:
- Board: As Tc 5d Jh 8s (river, 5 cards).
- Hero hole: JhJd? Wait — Jh is on the board. Use JcJs (the only JJ combo with no board conflict; J-spades / J-clubs both off-board).
- Villain hole: NOT fixed-combo; we want a "villain bets pot" decision against JJ. Best path:
  Use `solve_range_vs_range` with hero={"JJ"} (single hand class -> single combo after board-blocking) and villain=parse_range("AA,QQ,KK,AK,A5s,A2s,76s,T9s,87s,65s") — a representative polarized pot-bet river range (value + bluffs). hero_player=1.
- HUNLConfig: starting_street=Street.RIVER, starting_stack=1500, big_blind=100, initial_pot=2000, initial_contributions=(1500, 500), bet_size_fractions=(1.0,) (just the pot bet for villain's previous decision, but since we're entering at hero's facing-bet node, this is moot — set to (0.5, 1.0) for safety so any continuation node has legal sizes), postflop_raise_cap=3, initial_board=tuple of card indices for "As Tc 5d Jh 8s".
- Reasoning on initial_pot / initial_contributions: river arrives with pot 1000 (say, both contributed 500 pre+flop+turn aggregation). Villain bets pot (1000), so when hero acts: contributions=(1500, 500), pot=2000, to_call=1000.
- Call: `solve_range_vs_range(config, hero_range=parse_range("JJ"), villain_range=<above>, iterations=200, backend="rust", hero_player=1, reps_per_class=1, villain_reps=5)`.
- Confirm result.position == "defender".
- Wrap in subprocess.run(..., timeout=120) (2 min subprocess ceiling; Marcus gate is 30s so anything past 30s already fails).

PARALLEL CHECK FOR CRITERION (3) — NEIGHBOR MIX
Run the SAME config with hero_range=parse_range("TT") (only TT as second-pair / weaker-bluff-catcher). Verify TT's call_freq in [0.05, 0.95] (some mix).
This is a separate solve; budget another ~30s.

AGGREGATION + VERDICT
- Extract JJ class's first-decision freqs from result. (Field names: check range_aggregator.py `RangeVsRangeResult`.)
- PASS if: JJ call_freq in [0.85, 1.00] AND TT call_freq in [0.05, 0.95] AND BOTH solves return in <30s wall-clock each.
- FAIL if JJ call_freq < 0.85 OR setup didn't run.
- PARTIAL "neighbor mix absent" if JJ OK but TT pure-pole.
- PARTIAL "Marcus gate breached" if engine correct but per-spot >= 30s.

WRITE REPORT to: /Users/ashen/Desktop/poker_solver/docs/persona_test_results/W1_2_v1_4_1_retest.md
Format (match docs/pr13_prep/v1_3_2_w1_5_retest.md):
- Date, tip (commit hash), verdict (PASS / FAIL / PARTIAL / BLOCKED).
- Test scenario (board, hero combo, villain range, stack/pot/contributions, iterations, backend).
- Measurements: per-solve wall-clock (JJ and TT separately), JJ fold/call/raise freqs, TT fold/call/raise freqs.
- Verdict justification keyed to criteria (1)-(4).
- Marcus-gate verdict: wall-clock < 30s for the primary JJ solve? Explicit yes/no.
- Caveats / follow-ups: explicit note that the **CLI gap** (no `--hero` / `--villain-range` flags) remains AFTER v1.4.1 — this retest validates the engine, not the CLI surface Marcus would actually use. That CLI ergonomics PR is a separate ticket.

HARD RULES
- Read-only on poker_solver/, tests/, scripts/. Driver in /tmp/.
- mkdir -p docs/persona_test_results/ first.
- No git commits, no pushes, no code edits.
- Stall (> 30 min no progress, though for Marcus's <30s gate this should never fire) -> partial report "STALL" then STOP.
- Do not invoke other agents.
```

## E. Expected ship-time effect

If PASS, closes the **engine half** of W1.2 — Marcus can now (in principle) answer the JJ-vs-pot question via library / Jupyter. **Marcus's W1 cohort still has CLI ergonomics debt** (no `poker-solver river --board ... --hero ... --villain-range ...` subcommand; this is the persona_acceptance_spec.md §6 "river spot vs villain range CLI surface" gap). PR 22 unblocks the engine; a follow-up CLI PR is required for Marcus to actually reach this from the `.dmg` install.

**Dependency that v1.4.1 alone does NOT unblock for W1.2:** the CLI surface gap (no `--hero` / `--villain-range` flags on `--hunl-mode postflop`). This retest verifies the **engine** is correct; the **user-facing path** for Marcus still needs a separate small CLI PR. Flag this in the report as the gating residual for full Marcus W1.2 closure.
