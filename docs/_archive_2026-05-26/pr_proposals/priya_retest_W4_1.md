# v1.4.0 Retest Prompt — W4.1 (Priya: programmatic build + parse into pandas, Library round-trip)

**Status:** READY TO SPAWN against current v1.4.0 main. All dependencies
(`solve_hunl_postflop`, `Library.put`/`get`, `SpotDescription.spot_id`,
`HUNLSolveResult.average_strategy`) are already exported from
`poker_solver/__init__.py` per the v1.4.0 module surface check.

---

## A. Header

- **Workflow:** W4.1 — "Programmatic build + parse a result into pandas." Call
  `solve_hunl_postflop` once on a representative config, store
  `HUNLSolveResult.average_strategy` as a `DataFrame` row, confirm
  `Library.put(spot, result)` round-trips with a deterministic SHA256 spot ID.
- **Persona:** Priya (researcher / developer). API consumer; lives in Python;
  cares about typed importable library shape, reproducibility, and the
  "20-line script" entry-point. Acceptance is `WORKS-BUT-DOCS-CONFUSING` per
  `docs/pr13_prep/persona_acceptance_spec.md:67` — "pieces exist; no
  documented 20-line script recipe."
- **Prior failure mode:** No prior W4.x test results exist
  (`docs/persona_test_results/` is empty; no `W4_*` files found under
  `docs/pr13_prep/` either). This is the FIRST run for the Priya cohort.
- **What v1.4.0 ships that makes this runnable today:**
  `poker_solver.solve_hunl_postflop` (hunl_solver.py:100), `Library`,
  `Library.put`, `Library.get`, `LibraryFilter`, `SpotDescription`,
  `HUNLSolveResult` are all exported (`poker_solver/__init__.py:66-73` and
  `:140-188`). `_compute_spot_id` returns sha256 hex
  (`poker_solver/library.py:251`). No v1.4.1 dependency.

## B. Acceptance criteria (PASS definition)

Source: `docs/pr13_prep/persona_acceptance_spec.md:67` (W4.1 row) +
Heuristics §3 + `persona_time_budgets.md §1` (single-spot fixed-cards
subgame cell).

Quoted criteria from the spec:
> "Call `solve_hunl_postflop` once on a representative config, store
> `HUNLSolveResult.average_strategy` as a row, confirm `Library.put(spot,
> result)` round-trips. Single spot at standard accuracy (per Section 1
> cell): <5 min Pio-class, kill switch at 30 min. Expect a `DataFrame`
> row with exploitability < 0.5% pot and a deterministic SHA256 spot ID."
> (`docs/pr13_prep/persona_acceptance_spec.md:67`)

The retest **PASSES** iff **all** of the following hold:

1. **Setup runs end-to-end without monkey-patching.** A single Python script
   using only public imports from `poker_solver` builds a `HUNLConfig`,
   calls `solve_hunl_postflop`, inserts the result into a pandas
   `DataFrame` (one row per infoset OR one row summarizing the
   `average_strategy`; either is acceptable as the "row" interpretation),
   calls `Library.put(spot, result)`, and calls `Library.get(spot)` —
   without raising, segfaulting, or requiring private `_` imports.
2. **Round-trip equality.** `Library.get(spot)` returns a `SolveResult`
   whose `average_strategy` matches the in-memory result key-for-key
   (same infoset set, value arrays equal under `np.allclose(atol=1e-9)`).
3. **Deterministic spot ID.** Running `_compute_spot_id(spot)` twice on
   the same `SpotDescription` produces the same sha256 hex. Computing
   it on a structurally-equivalent rebuild of the same config also
   matches. (Public path: `result_spot_id = library.put(...)` then
   `library.put(...)` second time raises `LibraryDuplicateError` —
   confirming the ID is reproducible from the config alone.)
4. **Exploitability within band.** Final exploitability is < 0.5% of pot
   (per spec quote). If the standard-accuracy iteration count cannot hit
   that floor on the chosen fixture, record the observed value and
   classify as `PARTIAL — accuracy gap` (not PASS) — this is the spec's
   acceptance heuristic, not a soft target.
5. **Wall-clock within budget.** Per-spot < 5 min target at standard
   accuracy (`persona_time_budgets.md §1`, "Single subgame, 5 sizes, 2
   streets, ~1% pot precision" cell). Kill-switch at 30 min. Total
   agent wall-clock <= 15 min (Priya's session cell for "Single-spot
   fixed-cards subgame," `persona_time_budgets.md §2`).

If (1), (2), or (3) fails: **FAIL** with the offending criterion named.
If (4) is the only miss but solve completed: **PARTIAL — accuracy gap**
(record observed exploitability; do not mark loop closed).
If (5) is the only miss but solve was converging: **PARTIAL — perf
regression** (file a perf-bug ticket).

## C. Time budget

Authoritative source: `docs/pr13_prep/persona_time_budgets.md`.

- **Per-spot engine time (Section 1, "Single subgame, 5 sizes, 2 streets,
  ~1% pot precision" cell):** 1-5 min target at standard accuracy.
- **Kill-switch (Section 1):** > 30 min on one spot terminates the test and
  files a perf-bug.
- **Session total (Section 2, Priya "Single-spot fixed-cards subgame" cell):**
  "sweeps × <30 min total." This retest is **one** spot, so per-spot
  governs; total agent wall-clock cap = **15 min**.
- **Agent stall-check (per `feedback_stall_check.md`):** > 30 min no
  progress -> partial report + STOP.

## D. Paste-ready agent prompt

```
You are a one-shot retest agent for W4.1 (Priya persona, programmatic build + Library round-trip) on poker_solver v1.4.0.

CONTEXT
- Repo: /Users/ashen/Desktop/poker_solver
- Workflow: W4.1. Heuristic: solve_hunl_postflop runs end-to-end, result lands in a pandas DataFrame row, Library.put(spot, result) round-trips, deterministic SHA256 spot_id, exploitability < 0.5% pot.
- This is the FIRST Priya cohort retest; no prior failure mode to verify against. Acceptance is "WORKS-BUT-DOCS-CONFUSING" per spec — pieces exist; this run confirms they connect.
- Time budget: per-spot 1-5 min target, 30 min HARD kill switch, total agent wall-clock <= 15 min.
- Stall-check: > 30 min no progress -> report partial findings and STOP.

PRE-CONDITION VERIFICATION (do FIRST; BLOCKED on any failure)
1. cd /Users/ashen/Desktop/poker_solver && git rev-parse HEAD (record commit).
2. python -c "import poker_solver; print(poker_solver.__version__)" prints 1.4.0 (or later patch).
3. Import smoke:
   python -c "from poker_solver import solve_hunl_postflop, Library, SpotDescription, HUNLConfig, HUNLSolveResult, Street; print('imports OK')"
   If ImportError -> BLOCKED.
4. pandas availability:
   python -c "import pandas as pd; print(pd.__version__)"
   If missing, install in the project venv OR record BLOCKED — DO NOT pip-install globally.
5. If any precondition fails, write BLOCKED report to the report path below and STOP. Do not debug.

RETEST EXECUTION
Build a representative single-spot postflop config (small, standard-accuracy) and exercise the full Priya 20-line script flow:

Concrete fixture (chance-enum-at-root river, the cheapest reproducible spot):
- Board: As 7c 2d Kh 5s (river, 5 cards).
- starting_stack=1000, big_blind=100, initial_pot=1000, initial_contributions=(500, 500) (symmetric — no v1.4.1 dependency).
- initial_hole_cards=() (chance-enum-at-root).
- bet_size_fractions=(0.5, 1.0), postflop_raise_cap=3.
- starting_street=Street.RIVER, initial_board=<card_index tuple for "As 7c 2d Kh 5s">.
- iterations=200 (standard accuracy for this fixture; matches W1.5 retest setup at docs/pr13_prep/v1_3_2_w1_5_retest.md).

Then:
- result = solve_hunl_postflop(config, iterations=200, seed=42)
  (Use seed=42 for the determinism check — second run with same seed must produce identical exploitability.)
- Build the DataFrame: rows are infosets, columns are action freqs (acceptable alternative: a single summary row with exploitability + iteration count + spot_id). Pick whichever interpretation lets you assert "non-empty DataFrame."
- spot = SpotDescription(config=config, ...other required fields...) — check poker_solver/library.py for the SpotDescription dataclass shape.
- library = Library(":memory:") OR Library("/tmp/priya_w4_1_lib.sqlite") — either works.
- spot_id_1 = library.put(spot, result)
- result_back = library.get(spot)
- assert spot_id_1 is a 64-char hex (sha256).
- assert result_back is not None and np.allclose(result_back.average_strategy[k], result.average_strategy[k]) for every k.
- Try library.put(spot, result) again — must raise LibraryDuplicateError (this confirms the spot_id is deterministic / not nonce-based).

AGGREGATION + VERDICT
- PASS if all five acceptance criteria hold.
- FAIL if any of (1)-(3) fails; PARTIAL if (4) or (5) misses alone.
- Record: wall-clock for solve, wall-clock for library.put + get, final exploitability as % of pot (= final_expl_chips / initial_pot * 100), spot_id hex.
- Subprocess wrapper: subprocess.run(..., timeout=1800) for the solve step (30 min hard ceiling).

WRITE REPORT to: /Users/ashen/Desktop/poker_solver/docs/persona_test_results/W4_1_v1_4_0_retest.md
Format (match docs/pr13_prep/v1_3_2_w1_5_retest.md):
- Date, tip (commit hash), version, verdict (PASS / FAIL / PARTIAL / BLOCKED).
- Test scenario (board, stack, pot, contributions, iterations, seed, backend).
- Measurements table (solve wall-clock, library.put + get wall-clock, exploitability absolute + % pot, spot_id, DataFrame shape).
- Verdict justification keyed to criteria (1)-(5).
- Caveats / follow-ups (e.g. "USAGE.md §5b recipe still missing per spec fix-note" — flag this but don't block).

HARD RULES
- Read-only on poker_solver/, tests/, scripts/. Driver scripts go in /tmp/.
- mkdir -p docs/persona_test_results/ first if missing.
- No git commits, no pushes, no code edits.
- Stall (> 30 min no progress): partial report "STALL — incomplete" then STOP.
- Do not invoke other agents.
```

## E. Expected ship-time effect

If PASS, closes the W4.1 loop — Priya cohort goes from 0/3 to 1/3 verified
WORKS-NOW. The spec's fix-note ("USAGE.md §5b or DEVELOPER.md §11 worked
example") becomes a docs-debt ticket, NOT a blocker — the underlying API
works; only the recipe is missing. This is consistent with the spec's
`WORKS-BUT-DOCS-CONFUSING` classification — a PASS verdict does not require
USAGE.md to be updated in this PR; it requires the API to function.

If FAIL, surfaces a P0 gap in the v1.4.0 library shape — likely a missing
`SpotDescription` field, a `Library.put` schema mismatch, or a
non-deterministic `_compute_spot_id` path. Any of those would warrant a
v1.4.x patch PR before burst close.
