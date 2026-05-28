# W4.2 (Priya) Production-Scale Investigation — Task #52

**Date:** 2026-05-27
**Tip:** `main` @ `8f173db` (v1.8.0+, post-PR #123 CLI walk-tree).
**Version:** `poker_solver.__version__ == "1.8.0"`.
**Backend:** Python (`solve_hunl_preflop`) + Rust vector form (`solve_range_vs_range_nash`).
**Architecture:** `_rust.cpython-313-darwin.so` confirmed arm64 (no silent-skip hazard).
**Status:** **INVESTIGATION COMPLETE — NO PRODUCTION-SCALE WIRING BREAK FOUND.**

## TL;DR — bottom line

The task brief states "Persona test W4.2 is PARTIAL — wiring breaks at
production-scale ranges. Failure mode is unknown." This investigation
empirically **refutes** the "wiring breaks at production scale" hypothesis:

- **12-hand class panel at 9 BB preflop** (limp-or-fold action menu via
  `bet_size_fractions=(), include_all_in=False`) runs cleanly in **136.9 s
  (2.28 min)**. All 12 hands return well-formed `PreflopSolveResult`s with
  the action set restricted to `{FOLD, CALL}` at SB root and `{CHECK}` at
  BB response. **0 exceptions raised by the solver itself.**
- **Variant with 2x iso-raise extension** (12 hands × `bet_size_fractions=(2.0,)`
  + `include_all_in=False`) also runs cleanly in **144.6 s (2.41 min)** —
  4 infosets per solve, 3-action SB root, the iso-raise dynamic restored.
- **Post-v1.8.0 sweep already confirmed the river RvR path** at 10 classes
  in 0.7 s (see `docs/persona_status_post_v1_8_0_shipped_2026-05-27.md` row
  W4.2).

**The PARTIAL label is the SAME 3-day-old structural-heuristic mismatch
documented in `W4_2_v1_4_0_retest.md` (2026-05-23) and reconfirmed in
`persona_w4_2_retest_2026-05-26.md` (2026-05-26).** It is NOT a
production-scale wiring failure. The retest at v1.8.0 reproduces the same
mismatch with no new symptoms.

**Recommended fix scope: TRIVIAL (<1 day), docs-only.** The "fix" is a
3-line amendment to `docs/pr13_prep/persona_acceptance_spec.md` line 69 to
acknowledge the subgame-mode structural constraint that has been
documented for 4 days. No code change required (and explicitly out of
scope per task constraint).

---

## Investigation method

### 1. Locate the W4.2 fixture / spec

- **Workflow spec:** `docs/pr13_prep/persona_acceptance_spec.md:69`
- **Persona test prompt:** `docs/_archive_2026-05-26/pr_proposals/priya_retest_W4_2.md`
- **v1.4.0 retest (PARTIAL baseline):** `docs/persona_test_results/W4_2_v1_4_0_retest.md`
- **2026-05-26 retest (PARTIAL reconfirmed):** `docs/_archive_2026-05-26/persona_w4_2_retest_2026-05-26.md`
- **Post-v1.8.0 status:** `docs/persona_status_post_v1_8_0_shipped_2026-05-27.md`
  (row W4.2, 0.7 s wall via river RvR path at 10 classes)

The task brief references `docs/persona_test_results/post_v1_8_0_W4_2_retest_prompt.md`
— **that file does not exist** (the sibling files `post_v1_8_0_W2_3_retest_prompt.md`
and `post_v1_8_0_W3_4_retest_prompt.md` do exist, but no W4.2 retest
prompt was pre-staged for v1.8.0). The brief's framing of "production-scale
failure mode unknown" therefore had no concrete reproduction recipe to
investigate against. I derived the recipe from the existing v1.4.0 / v1.7.0
retest fixtures, scaled to 12 hand classes.

### 2. What does Priya try to do?

Priya is the "extensibility" persona. Her exemplar use-case per the spec:

> Extend the action abstraction to a 2-action menu. `ActionAbstractionConfig
> (include_all_in=False, bet_size_fractions=())` covers part of it; 'limp'
> is a preflop SB-CALL handled by `_apply_player`'s SB-call branch...
> Acceptance test exercises one limp-or-fold solve at standard accuracy:
> <5 min Pio-class, kill switch at 30 min. Heuristic: limp-or-fold
> equilibrium is mostly determined by BB's iso-raising frequency.
> (`docs/pr13_prep/persona_acceptance_spec.md:69`)

In practice this means: configure a `HUNLConfig` with the action knobs
restricted, run a preflop solve at short-stack depth (9 BB justifies
limp-or-fold game theory), and observe the equilibrium across multiple
hero hands.

### 3. Small-scale smoke (3 hand classes)

Driver: `/tmp/w42_task52_smoke.py`. Fixture: 3 hero hands (AA, KK, 32o) vs
fixed villain Js9c. iterations=500, seed=42, `allow_pushfold_range=True`.

| Hand | Wall (s) | Infosets | Max action_len | LIMP | FOLD |
|---|---|---|---|---|---|
| AA  | 11.43 | 2 | 2 | 1.0000 | 0.0000 |
| KK  | 11.71 | 2 | 2 | 1.0000 | 0.0000 |
| 32o | 13.79 | 2 | 2 | 1.0000 | 0.0000 |

**Total: 36.9 s. PASS — no exceptions.**

### 4. Production-scale (12 hand classes)

Driver: `/tmp/w42_task52_production.py`. Same fixture style scaled to 12
hero hands (7 premium AA-99 + 3 suited AKs/AQs/KQs + 3 trash 32o/72o/92o)
vs fixed villain Js9c.

| Hand | Wall (s) | Infosets | MaxLen | LIMP | FOLD |
|---|---|---|---|---|---|
| AA  | 11.65 | 2 | 2 | 1.0000 | 0.0000 |
| KK  | 11.48 | 2 | 2 | 1.0000 | 0.0000 |
| QQ  | 11.49 | 2 | 2 | 1.0000 | 0.0000 |
| JJ  | 11.55 | 2 | 2 | 1.0000 | 0.0000 |
| TT  | 11.28 | 2 | 2 | 1.0000 | 0.0000 |
| 99  | 11.29 | 2 | 2 | 1.0000 | 0.0000 |
| AKs | 11.34 | 2 | 2 | 1.0000 | 0.0000 |
| AQs | 11.35 | 2 | 2 | 1.0000 | 0.0000 |
| KQs | 11.32 | 2 | 2 | 1.0000 | 0.0000 |
| 32o | 11.34 | 2 | 2 | 1.0000 | 0.0000 |
| 72o | 11.33 | 2 | 2 | 1.0000 | 0.0000 |
| 92o | 11.49 | 2 | 2 | 0.0000 | 1.0000 |

**Total: 136.9 s (2.28 min). PASS — 12/12 hands, 0 solver-side exceptions.**

Aggregate metrics:
- **Premium LIMP min** (AA, KK, QQ, JJ, TT, AKs, AQs): **1.0000** (≥0.90 → PASS)
- **Trash FOLD min** (32o, 72o, 92o): **0.0000** (≥0.90 → STRUCTURAL FAIL,
  same as prior retests — 32o/72o have >25% raw equity vs Js9c so limping
  is mechanically correct in subgame mode)
- **Aggregate LIMP mean**: **0.9167** (in [0.40, 0.90] gate → just over
  upper bound, same as v1.4.0's 0.9200 — heuristic structurally
  inapplicable in subgame mode)
- **Max action_len across all infosets**: 2 (only `{FOLD, CALL}` at SB
  root; no bet/raise/all-in leak)

### 5. Variant: 12 hands WITH 2x BB iso-raise extension

Per v1.4.0 retest §Caveats(2)(a), extending the menu with a single
`bet_size_fractions=(2.0,)` restores the iso-raise dynamic the spec
heuristic references.

Driver: `/tmp/w42_task52_iso_raise.py`. Result:

| Hands attempted | Hands completed | Total wall | Avg wall/hand | Max action_len | SB root dist len |
|---|---|---|---|---|---|
| 12 | 12 | 144.6 s (2.41 min) | 12.05 s | 3 | 3 |

**All 12 hands complete. Iso-raise variant also passes at production scale.**

### 6. River RvR path (post-v1.8.0 retest re-execution)

Driver: `/tmp/persona_retests/w4_2_retest.py` (pre-existing from post-ship sweep).

| Spec | Value |
|---|---|
| Backend | `solve_range_vs_range_nash` (rust vector form) |
| Classes | 10 (`AA, KK, QQ, JJ, TT, 99, AKs, AQs, KQs, QJs`) |
| Board | `Qs7h2d5c9h` (river) |
| iter | 200 |
| Wall | **0.45 s** |
| AA action keys | `{'check'}` |
| Range-aggregate | check=1.000, call=0.000, fold=0.000 |
| Action menu restricted | True (no bet/raise leak) |

**The post-v1.8.0 row in `persona_status_post_v1_8_0_shipped_2026-05-27.md`
table is reproducible at v1.8.0.**

---

## Failure-mode capture (per task brief item 5)

The task brief requested "error type, traceback, wall time before failure,
which solver/aggregator function was called." **No failure occurred** at
production scale on any pathway tested:

| Pathway | Function | Classes | Wall (s) | Exception? | Notes |
|---|---|---|---|---|---|
| River RvR Nash | `solve_range_vs_range_nash` | 10 | 0.45 | NO | Existing post-v1.8.0 retest |
| Preflop subgame, pure limp-fold | `solve_hunl_preflop` (per-pair loop) | 12 | 136.9 | NO | This investigation |
| Preflop subgame, +2x iso-raise | `solve_hunl_preflop` (per-pair loop) | 12 | 144.6 | NO | This investigation |

The only "exceptions" that appeared in `/tmp/w42_task52_production.json`
were `ValueError: Invalid format specifier '.4f if fold_p else 0:.4f'` —
a Python f-string typo in MY driver script (line 99), not a solver error.
The same JSON file shows each hand also has a `"status": "completed"`
entry alongside the printing-side `"status": "exception"` entry. The
solve returned `PreflopSolveResult` cleanly for all 12 hands; the post-
solve `print()` then failed to format the result, which I caught and
serialized. The aggregate metrics block in the JSON computes
correctly from the `"completed"` entries.

**Net: the solver-side wiring is intact at production scale. No reproducible
production-scale failure exists to fix.**

---

## Root cause analysis — why is W4.2 labeled PARTIAL?

The PARTIAL label is **NOT** due to a production-scale failure. It is due
to TWO structural-heuristic mismatches that are inherent to the
subgame-mode constraint on `solve_hunl_preflop`, both documented as
structural caveats for 4+ days:

### Cause 1: Trash-FOLD ≥0.90 criterion vs. raw-equity reality

The W4.2 spec criterion (3) requires trash hands (32o, 72o, etc.) to fold
at ≥0.90 frequency. In subgame mode with no raise actions, the SB's choice
is purely:
```
EV_limp = 200 * equity - 100   (limp + check down to showdown)
EV_fold = -50                  (lose posted SB)
limp > fold  iff  equity > 0.25
```
Most "trash" hands beat 25% raw equity vs a mid-tier offsuit villain
(Js9c). So they limp, not fold. **This is mechanically correct, not a
solver bug** — the spec heuristic was written assuming range-vs-range
dynamics; subgame mode collapses to per-hand equity comparison.

The differential probes (32o vs KK, 72o vs AA) confirm equity-driven
decisions: when villain is a monster, trash hands fold cleanly (1.0000).

### Cause 2: "BB iso-raising frequency" heuristic is inapplicable with no raise action

The spec heuristic for criterion (4) reads: "limp-or-fold equilibrium is
mostly determined by BB's iso-raising frequency." But the W4.2 fixture
sets `bet_size_fractions=()`, which removes ALL raise actions including
BB's. The heuristic therefore reduces to a degenerate proxy ("aggregate SB
limp frequency in [0.40, 0.90]") which is structurally a function of
panel composition rather than equilibrium dynamics.

At 12 classes with 1 mid-tier villain, the aggregate LIMP mean is 0.917
(just over the 0.90 upper bound). Same value as v1.4.0's 0.92 at 20
classes, same value as v1.7.0's 0.90 at 10 classes — **panel-composition
artifact, not solver state.**

### Source-file references

- **Wiring path:** `HUNLConfig(bet_size_fractions=(), include_all_in=False)`
  → `HUNLConfig.to_action_config()` (`poker_solver/hunl.py:151-159`)
  → engine via `enumerate_legal_actions`. **Confirmed end-to-end at v1.8.0.**
- **Preflop subgame enforcement:** `poker_solver/preflop.py:419-426`
  (requires `initial_hole_cards`; full-tree preflop deferred post-v1).
- **`solve_range_vs_range_nash` preflop rejection:** `poker_solver/range_aggregator.py:982-988`
  ("solve_range_vs_range_nash does not support preflop range-vs-range").

These design constraints are intentional and load-bearing for v1; they
are not bugs.

---

## Recommended fix scope

**TRIVIAL (<1 day) — docs-only.**

There is no code-side fix because there is no code-side bug. The remaining
work is to amend the W4.2 acceptance criteria so the structural
subgame-mode constraint is reflected in the PASS/PARTIAL/FAIL routing.
Two viable amendments (carried forward from the v1.4.0 retest §Caveats(2),
2026-05-23):

**Option A (preferred):** Reclassify W4.2 criterion (3-trash) and (4) as
informational-only when `bet_size_fractions=()`. Lock criterion (3-premium)
+ criterion (2) action-restriction + criterion (5) wall-clock as the
hard PASS gates. **Result: W4.2 PARTIAL → PASS at next persona sweep.**

**Option B:** Extend the canonical W4.2 fixture to include a single
`bet_size_fractions=(2.0,)` BB iso-raise option. This restores the
iso-raise dynamic the spec heuristic references. **Result: heuristic
becomes empirically testable; verdict path no longer depends on a
structurally-inapplicable proxy.**

Both options are 3-5 line edits to `docs/pr13_prep/persona_acceptance_spec.md:69`
plus a short note in the W4.2 retest fixture. **No code change. No solver
rebuild. No `.dmg` regeneration.**

The 2026-05-23 v1.4.0 retest already flagged this as Type C-USEFUL
(docs-only); 2026-05-26 retest reconfirmed Type A (`DEVELOPER.md`
docs-debt). v1.8.0 status table reconfirms PARTIAL with the same
classification.

### Why this is NOT "medium" or "significant"

A medium-scope fix would be required if any of the following were true:

- **Solver crash at production scale.** Did not happen — 12 hands ran
  clean in 137 s.
- **Wall-time blowup beyond Priya's 15-min session budget.** Did not
  happen — 2.28 min total, ~30% faster per-spot than v1.4.0.
- **Action-menu leak (raise/bet keys appearing despite `bet_size_fractions=()`).**
  Did not happen — `max(action_len) = 2` at SB root, 1 at BB response,
  no leak.
- **Wiring regression between v1.4.0 / v1.7.0 / v1.8.0.** Did not happen
  — same equilibrium, same action restriction, same heuristic mismatch.

A significant-scope fix would be required only if Priya's exemplar use-case
genuinely needed full-tree (unfixed-hole-card) preflop solves. That is
explicitly out of scope per `poker_solver/preflop.py:422-426`
("full-tree preflop... is intractable without a hand-class abstraction —
reserved for a post-v1 follow-up"). The W4.2 spec language already
accepts the subgame constraint; the only gap is between the criterion
heuristics and the subgame reality.

---

## Failure reproduction script (per task brief item 1)

There is no failure to reproduce. The investigation reproduction scripts are:

1. **Small-scale smoke (3 hands, 37 s):** `/tmp/w42_task52_smoke.py`
2. **Production scale, pure limp-fold (12 hands, 137 s):** `/tmp/w42_task52_production.py`
3. **Production scale, +iso-raise variant (12 hands, 145 s):** `/tmp/w42_task52_iso_raise.py`
4. **River RvR path (10 classes, 0.5 s):** `/tmp/persona_retests/w4_2_retest.py`

Result JSONs:
- `/tmp/w42_task52_smoke.json` (3-hand smoke; all PASS)
- `/tmp/w42_task52_production.json` (12-hand production; all PASS, 1 driver f-string typo cosmetic)
- `/tmp/w42_task52_iso_raise.json` (12-hand iso-raise variant; all PASS)
- `/tmp/persona_retests/w4_2_result.json` (10-class river RvR; restricted to {check}, PASS)

All drivers are read-only against `poker_solver/`. No source-tree edits.

---

## Caveats / open items for orchestrator

1. **The task brief framing was incorrect.** "Wiring breaks at
   production-scale ranges. Failure mode is unknown." was an
   over-statement. There is no production-scale wiring break. The PARTIAL
   label is a heuristic-vs-subgame-mode mismatch documented for 4+ days.
   Recommend updating the task #52 spec to reflect this.

2. **Docs-debt ticket still open.** `DEVELOPER.md §5a "extending the
   action abstraction"` was flagged as missing in the 2026-05-23 v1.4.0
   retest (Type C-USEFUL). It remains unaddressed. File as a separate
   docs-only ticket; not gating release.

3. **Persona acceptance spec (`docs/pr13_prep/persona_acceptance_spec.md:69`)
   amendment recommended.** Choose Option A or Option B above. Trivial
   doc edit.

4. **No code change in this investigation.** Per task brief constraint
   ("DON'T modify any code in this agent — investigation only"). Solver
   tree at HEAD `8f173db` is unchanged.

5. **No `.dmg` regeneration impact.** This investigation finds no
   v1.8.x regression; v1.8.0 ship narrative is unaffected.

---

## Bottom-line answer (one sentence)

**W4.2 PARTIAL at v1.8.0 is the SAME structural-heuristic mismatch documented
across the 2026-05-23 v1.4.0 retest and the 2026-05-26 v1.7.0 retest; the
solver wiring is intact at production scale (12 hand classes in 2.28 min,
0 exceptions), and the fix scope is TRIVIAL (3-5 line edit to
`persona_acceptance_spec.md:69`), not a code change.**

---

## References

- **Spec:** `docs/pr13_prep/persona_acceptance_spec.md:69`
- **Test prompt:** `docs/_archive_2026-05-26/pr_proposals/priya_retest_W4_2.md`
- **Prior retests (PARTIAL baseline):**
  - `docs/persona_test_results/W4_2_v1_4_0_retest.md` (2026-05-23)
  - `docs/_archive_2026-05-26/persona_w4_2_retest_2026-05-26.md` (2026-05-26)
- **Post-v1.8.0 status table:** `docs/persona_status_post_v1_8_0_shipped_2026-05-27.md`
  (row W4.2, 0.7 s wall via river RvR path)
- **Persona time budgets (Priya 15-min cell):** `docs/pr13_prep/persona_time_budgets.md`
- **Source files (no edits made):**
  - `poker_solver/hunl.py:109-110` (HUNLConfig action knobs)
  - `poker_solver/hunl.py:151-159` (to_action_config)
  - `poker_solver/preflop.py:283-398` (solve_hunl_preflop)
  - `poker_solver/preflop.py:419-426` (subgame-mode hard requirement)
  - `poker_solver/range_aggregator.py:878-988` (solve_range_vs_range_nash;
    preflop rejection at 982-988)
- **Drivers (read-only, /tmp/):**
  - `/tmp/w42_task52_smoke.py` + `/tmp/w42_task52_smoke.json`
  - `/tmp/w42_task52_production.py` + `/tmp/w42_task52_production.json`
  - `/tmp/w42_task52_iso_raise.py` + `/tmp/w42_task52_iso_raise.json`
