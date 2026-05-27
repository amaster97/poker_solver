# v1.4.0 Retest Prompt — W4.2 (Priya: custom "limp-or-fold" action menu)

**Status:** READY TO SPAWN against current v1.4.0 main. All dependencies
(`ActionAbstractionConfig` with `include_all_in=False`,
`bet_size_fractions=()`, the SB-CALL preflop branch) are present in the
v1.4.0 surface per `poker_solver/action_abstraction.py:56-86` and
`poker_solver/__init__.py:28`.

---

## A. Header

- **Workflow:** W4.2 — "Add a custom 'limp-or-fold' mode for play vs short
  stacks." Extend the action abstraction to a 2-action menu (LIMP +
  FOLD, no raises, no all-in). Single representative solve at standard
  accuracy.
- **Persona:** Priya (researcher / developer). API consumer building a
  custom variant on top of the solver — the spec's exemplar use-case
  for the "extensibility" axis. Acceptance is `WORKS-BUT-DOCS-CONFUSING`
  per `docs/pr13_prep/persona_acceptance_spec.md:69` — "hooks exist;
  docs don't connect them."
- **Prior failure mode:** No prior W4.x test results exist
  (`docs/persona_test_results/` is empty). This is the FIRST run for
  the Priya cohort. The spec's open question is whether
  `ActionAbstractionConfig(include_all_in=False, bet_size_fractions=())`
  alone is sufficient to produce a limp-or-fold equilibrium, or whether
  additional plumbing (e.g. preflop SB-CALL routing, BB iso-raise
  suppression) is required.
- **What v1.4.0 ships that makes this runnable today:**
  `ActionAbstractionConfig` exposes `include_all_in: bool = True` and
  `bet_size_fractions: tuple[float, ...]` as public knobs
  (`poker_solver/action_abstraction.py:56-86`). Setting
  `include_all_in=False, bet_size_fractions=()` reduces the preflop
  action set to {LIMP/CALL, FOLD} (per spec text:
  `persona_acceptance_spec.md:69` "limp is a preflop SB-CALL handled by
  `_apply_player`'s SB-call branch"). No v1.4.1 dependency.

## B. Acceptance criteria (PASS definition)

Source: `docs/pr13_prep/persona_acceptance_spec.md:69` (W4.2 row) +
Heuristics §3 + `persona_time_budgets.md §1`.

Quoted criteria from the spec:
> "Extend the action abstraction to a 2-action menu.
> `ActionAbstractionConfig(include_all_in=False,
> bet_size_fractions=())` covers part of it; 'limp' is a preflop
> SB-CALL handled by `_apply_player`'s SB-call branch... Acceptance
> test exercises one limp-or-fold solve at standard accuracy: <5 min
> Pio-class, kill switch at 30 min. Heuristic: limp-or-fold
> equilibrium is mostly determined by BB's iso-raising frequency."
> (`docs/pr13_prep/persona_acceptance_spec.md:69`)

The retest **PASSES** iff **all** of the following hold:

1. **Setup is executable.** A `HUNLConfig` built with
   `ActionAbstractionConfig(include_all_in=False, bet_size_fractions=())`
   solves to completion without raising `ValueError`,
   `NotImplementedError`, or segfault — confirming the public knobs
   reach the engine.
2. **Action set is restricted.** The solver's strategy contains ONLY
   `{LIMP/CALL, FOLD}` actions (no bet / raise / all-in entries
   present in `average_strategy`). If `include_all_in=False,
   bet_size_fractions=()` silently re-enables actions, that is a
   regression and a FAIL.
3. **Strategy is non-degenerate.** SB's preflop strategy at the root
   shows a non-trivial mix between LIMP and FOLD across hand classes —
   premium hands (TT+, AJs+) limp at >=0.90 frequency; trash (32o, 72o,
   etc.) folds at >=0.90 frequency. A pure-pole (all-limp or all-fold
   uniformly across the root) is a regression flag.
4. **Heuristic — BB iso-raising frequency proxy.** Per spec, "limp-or-
   fold equilibrium is mostly determined by BB's iso-raising frequency."
   Since this fixture has NO raise actions for either player, BB
   cannot iso-raise — so the equilibrium reduces to SB
   limp-or-fold-based-on-equity vs BB's check option. The proxy
   heuristic becomes: **SB limps at least 60% of hands** (any hand with
   >=50% equity vs random when BB checks freely; this is roughly the
   top ~60% of starting hands by equity, per pokerstove community
   standard). If SB limps <40% or >90%, that is a heuristic miss.
5. **Wall-clock within budget.** Per-spot < 5 min target at standard
   accuracy. Kill-switch at 30 min. Total agent wall-clock <= 15 min
   (Priya's session cell).

If (1) fails: **FAIL — wiring broken**.
If (2) fails: **FAIL — action restriction not honored**.
If (3) or (4) fails but (1)-(2) pass: **PARTIAL — wiring OK, heuristic
miss** (file an investigation ticket; may be a real solver bug or a
spec heuristic that needs refinement).
If (5) is the only miss: **PARTIAL — perf regression**.

**Note for the orchestrator:** Criterion (4)'s heuristic was derived
from first-principles given that BB has no raise option in this
action menu — the spec text leans on "BB's iso-raising frequency"
which is structurally absent here. If the agent finds the heuristic
ambiguous, fall back to criterion (3) as the primary signal and
record observed SB limp frequency for orchestrator review.

## C. Time budget

Authoritative source: `docs/pr13_prep/persona_time_budgets.md`.

- **Per-spot engine time (Section 1, "Single subgame, 5 sizes, 2 streets,
  ~1% pot precision" cell):** 1-5 min target at standard accuracy.
  (Limp-or-fold is a SIMPLER action menu, so should be faster — but
  cite the standard cell as the gate.)
- **Kill-switch (Section 1):** > 30 min on one spot terminates.
- **Session total (Section 2, Priya cell):** total agent wall-clock cap
  = **15 min**.
- **Agent stall-check:** > 30 min no progress -> partial report +
  STOP.

## D. Paste-ready agent prompt

```
You are a one-shot retest agent for W4.2 (Priya persona, custom limp-or-fold action menu) on poker_solver v1.4.0.

CONTEXT
- Repo: /Users/ashen/Desktop/poker_solver
- Workflow: W4.2. Heuristic: ActionAbstractionConfig(include_all_in=False, bet_size_fractions=()) reduces preflop action set to {LIMP/CALL, FOLD}; equilibrium has SB mixing limp vs fold across hand classes; premium hands limp >=0.90, trash folds >=0.90, aggregate SB limp freq in [0.40, 0.90].
- Pre-condition: spec says hooks exist (ActionAbstractionConfig knobs); docs don't connect them. This run verifies the wiring.
- Time budget: per-spot < 5 min target, 30 min HARD kill switch, total agent wall-clock <= 15 min.
- Stall-check: > 30 min no progress -> report partial findings and STOP.

PRE-CONDITION VERIFICATION (do FIRST; BLOCKED on any failure)
1. cd /Users/ashen/Desktop/poker_solver && git rev-parse HEAD (record commit).
2. python -c "import poker_solver; print(poker_solver.__version__)" prints 1.4.0+.
3. Import smoke:
   python -c "from poker_solver import HUNLConfig, ActionAbstractionConfig, HUNLPoker; cfg = ActionAbstractionConfig(include_all_in=False, bet_size_fractions=()); print(cfg.include_all_in, cfg.bet_size_fractions)"
   Must print "False ()". If TypeError -> BLOCKED (config field missing).
4. Check if HUNLConfig accepts a custom ActionAbstractionConfig — inspect HUNLConfig dataclass for an `action_abstraction` field OR equivalent threading. If no such field, check whether action_abstraction is configured globally / via a different surface. If the wiring is unclear, record BLOCKED with the specific gap.
5. If any precondition fails, write BLOCKED report and STOP.

RETEST EXECUTION
Build a short-stack preflop config with the 2-action menu enabled:

Concrete fixture:
- starting_stack=900, big_blind=100 (9 BB — short stack, justifies limp-or-fold game theory).
- starting_street=Street.PREFLOP (root of game tree).
- ActionAbstractionConfig: include_all_in=False, bet_size_fractions=().
- Thread the ActionAbstractionConfig into HUNLConfig per whatever field/keyword the v1.4.0 API exposes (check poker_solver/hunl.py and hunl_solver.py for the connection point; if it's solver-side only, pass via dcfr_kwargs or equivalent).
- iterations=500 (standard accuracy for a 2-action preflop game — converges fast).
- backend="rust" if supported for preflop; else "python". Record which.

Solve:
- result = solve_hunl_postflop(config, iterations=500, seed=42)
  IF solve_hunl_postflop rejects preflop configs (per its docstring: "starting_street >= Street.FLOP"), fall back to using the lower-level CFR API directly (poker_solver.solver.solve(...) or poker_solver.cfr.* — check the public surface in __init__.py for a preflop entry-point).

AGGREGATION + VERDICT
- Enumerate result.average_strategy. Confirm every action ID in the strategy maps to {LIMP/CALL or FOLD} per the action_abstraction.py constants (ACTION_CALL, ACTION_FOLD). If any ACTION_BET_* or ACTION_ALL_IN appears, that is criterion (2) FAIL.
- Compute SB's root preflop strategy aggregated over hand classes (or over the SB's first decision infoset). Report:
  - SB limp frequency (weighted by hand-class combo count) — must be in [0.40, 0.90] for criterion (4) PASS.
  - SB premium-hand limp freq (AA, KK, QQ, JJ, AKs, AKo, AQs) — must be >= 0.90 for criterion (3) PASS on the premium side.
  - SB trash-hand fold freq (32o, 72o, 82o, 92o) — must be >= 0.90 for criterion (3) PASS on the trash side.
- PASS if all five criteria hold.
- FAIL if (1) or (2) fails; PARTIAL if (3), (4), or (5) miss alone (per the per-criterion verdict mapping in Section B).
- Subprocess wrapper: subprocess.run(..., timeout=1800).

WRITE REPORT to: /Users/ashen/Desktop/poker_solver/docs/persona_test_results/W4_2_v1_4_0_retest.md
Format (match docs/pr13_prep/v1_3_2_w1_5_retest.md):
- Date, tip (commit hash), version, verdict (PASS / FAIL / PARTIAL / BLOCKED).
- Test scenario (stack, BB, action config, iterations, seed, backend, preflop entry-point used).
- Measurements: wall-clock, action set actually present in strategy (action ID counts), SB aggregate limp freq, SB premium limp freq, SB trash fold freq.
- Verdict justification keyed to criteria (1)-(5).
- Caveats / follow-ups (e.g. "DEVELOPER.md §5a 'extending the action abstraction' missing per spec fix-note" — flag, don't block).

HARD RULES
- Read-only on poker_solver/, tests/, scripts/. Driver scripts go in /tmp/.
- mkdir -p docs/persona_test_results/ first if missing.
- No git commits, no pushes, no code edits.
- Stall (> 30 min no progress): partial report "STALL — incomplete" then STOP.
- Do not invoke other agents.
```

## E. Expected ship-time effect

If PASS, closes the W4.2 loop — Priya cohort moves to 2/3 verified
WORKS-NOW (assuming W4.1 also passes). The spec's fix-note ("DEVELOPER.md
§5a 'extending the action abstraction'") becomes a docs-debt ticket,
NOT a blocker.

If FAIL with criterion (2) miss (action restriction not honored), that
surfaces a v1.4.x bug — `include_all_in=False, bet_size_fractions=()`
should reduce the action set deterministically; if it doesn't,
Priya's extensibility story is broken and a patch is required before
burst close.

If FAIL with criterion (1) miss (wiring broken — `ActionAbstractionConfig`
doesn't reach the engine), that is a P0 gap and the workflow becomes
`DOESN'T-WORK`, downgrading the spec classification.

**Open question for orchestrator:** Criterion (4)'s heuristic was
derived from first-principles given BB's lack of iso-raise option;
the spec text leans on "BB's iso-raising frequency" which doesn't
apply here. If orchestrator wants stricter heuristic, recommend
either: (a) extending the action menu to include a BB iso-raise size
(e.g. `bet_size_fractions=(2.0,)` for a 2x iso, `include_all_in=False`)
and re-running, or (b) reclassifying criterion (4) as informational-
only.
