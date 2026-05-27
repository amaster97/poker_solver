# Downstream Verification — Post-Audit Sanity Check

**Date:** 2026-05-24
**Trigger:** 4-agent solver audit confirmed terminal utility convention is CORRECT
(both Python `poker_solver/hunl.py::utility` and Rust scalar/vector form).
The earlier "convention divergence" alarm traced to a misread of solver code.
This document verifies that downstream surfaces are NOT silently dependent on
incorrect numerical values that would have masked a real bug.

---

## Surface 1: Tests — **CLEAN**

**Location:** `/Users/ashen/Desktop/poker_solver/tests/` (47 test files)

**Tests that assert directly on terminal utility values:**
- `tests/test_leduc_core.py` (lines 71–140): 6 distinct showdown/fold assertions
- `tests/test_hunl_core.py` (lines 71–78, 262–320): fold + showdown utility assertions
- `tests/test_kuhn_dcfr.py`: no direct utility-value assertions (verified via grep)
- `tests/test_pushfold.py`: no direct utility-value assertions

**Representative verification — winner-gets-pot convention:**

1. `tests/test_leduc_core.py::test_leduc_fold_ends_hand` (line 72):
   ```
   assert game.utility(s) == (1.0, -1.0)
   ```
   After P1 RAISE then P0 FOLD → P1 wins → P1 gets +1.0, P0 loses 1.0.
   CORRECT for winner-gets-pot convention.

2. `tests/test_leduc_core.py::test_leduc_showdown_high_card_wins` (line 97):
   ```
   assert game.utility(s) == (-1.0, 1.0)
   ```
   P1's high card wins → P1 +1.0, P0 −1.0. CORRECT.

3. `tests/test_leduc_core.py::test_leduc_pot_arithmetic_through_a_hand` (line 140):
   ```
   assert s.ante == (9, 9) ... assert game.utility(s) == (-9.0, 9.0)
   ```
   Each player contributed 9; P1 wins → +9 for P1, −9 for P0. CORRECT.

4. `tests/test_hunl_core.py::test_hunl_fold_terminates_hand_correctly` (lines 75–78):
   `u[0] == pytest.approx(-0.5)` and `u[1] == pytest.approx(0.5)` — SB posts 0.5 BB,
   folds → SB loses 0.5 BB blind, BB wins 0.5 BB. CORRECT.

5. `tests/test_hunl_core.py::test_hunl_showdown_higher_hand_wins` (line 280):
   Zero-sum check only (`u[0] + u[1] == 0.0`) — convention-agnostic.

6. `tests/test_hunl_core.py::test_hunl_showdown_tie_splits_pot` (lines 319–320):
   `u == (0.0, 0.0)` — convention-agnostic.

**Source convention (hunl.py:465–479):** matches test assertions; winner receives
`+c_loser/bb`, loser receives `-c_loser/bb` (or `±c_self/bb` for fold). Tests
encode this consistently. **No test asserts an incorrect numerical value that
would have masked a real solver convention bug.**

---

## Surface 2: GUI — **CLEAN**

**Location:** `/Users/ashen/Desktop/poker_solver/ui/`
- Main entry: `ui/app.py` (composes 2-pane layout, polls `state.runner`)
- Views: `ui/views/{range_matrix, run_panel, tree_browser, library_browser}.py`

**Solver output surfaced by GUI:**

1. **Action probabilities** — `range_matrix._build_combo_rows()` aggregates
   `(fold, call, raise_)` from solver strategy via `_aggregate_action_buckets`.
   Probabilities are unit-less; convention-agnostic.

2. **Exploitability** — displayed in `run_panel` (live chart, log Y) and
   `library_browser` (line 100: `f"{meta.exploitability * 1000:.1f} mBB"`).
   Unit: mBB/pot. This is a magnitude reported by solver — unaffected by sign
   convention.

3. **Per-hand EV** — `range_matrix.py:892`: `ev_mbb=0.0` with comment
   *"Real EV plugs in when Agent A wires per-combo EV."* EV display is
   currently a placeholder (zeros). `tree_browser.range_weighted_ev` is also
   currently zero-initialized. **No real EV numbers are surfaced today**, so
   convention exposure is zero.

4. **Units:** All EV/exploitability displays use `mBB` (mBB/pot for exploit,
   +/- mBB for per-hand EV when wired). No raw chip values displayed. The
   solver itself normalizes by `big_blind` in `utility()` before any UI
   consumes the number, so even when EV wiring lands, the unit will be correct.

**Result:** GUI cannot mis-display a convention bug because (a) it only shows
unsigned magnitudes today, and (b) the underlying solver convention is
verified correct.

---

## Surface 3: .dmg — **CLEAN** (gated on solver correctness, which audit confirmed)

**Location:** `/Users/ashen/Desktop/poker_solver/dist/Poker-Solver-1.6.0-arm64.dmg`
**Build script:** `scripts/build_macos_dmg.sh` + `scripts/poker_solver.spec` + `scripts/pyinstaller_entry.py`

**Architecture:** The .dmg packages:
- Source `poker_solver/` Python tree (same as repo)
- Rust binary `poker_solver._rust` (same compiled artifact as `pip install -e .`)
- NiceGUI runtime + `ui/` views

**Baked-in expected values?** None. `scripts/pyinstaller_entry.py` only contains
a `--smoke-test` flag that verifies `poker_solver._rust` imports correctly and
exposes public symbols. No hardcoded utility values, expected EV tables, or
test fixtures embedded in the bundle.

**Conclusion:** The .dmg is a transport wrapper for the same source the
audit verified. Since the underlying solver is correct, the .dmg produces
correct results. (Launch + Rust-symbol-load already verified out-of-band per
the v1.6.0 release.)

---

## Surface 4: Persona Test Results — **CLEAN**

**Location:** `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/`

**Current classification (12 PASS / 4 PARTIAL / 2 BLOCKED) cross-check:**

- **W1.2 (post v1.7.0):** PASS — JJ fold went from 7.7%/11.5% (aggregator) to
  1.6e-08 (Nash). PASS based on aggregator-vs-Nash divergence detection;
  convention-agnostic.
- **W2.1 (post v1.7.0):** FAIL → Type D (timeout, 21 min wall-clock). PERF
  issue, not values. Convention-irrelevant.
- **W2.3 (post v1.7.0):** PARTIAL-TIMEOUT → Type D. PERF issue. Convention-irrelevant.
- **W3.4 (post v1.7.0):** PARTIAL-TIMEOUT → Type D. PERF issue. Convention-irrelevant.
- **W3.5 (post v1.7.0):** PARTIAL → was Type B-code → now Type B-DOC. The
  reclassification was about **class-expansion semantics** (6-class vs 15-class
  range; narrow ranges have less polarization signal, so AA mix margin is
  thinner) — NOT a solver convention bug. Recommended fix: docs note in
  USAGE.md/DEVELOPER.md about range-narrowness limitation. This reclassification
  STANDS independent of solver convention.

**Convention-related references found:**
- `PLAN.md:470`: "Brown convention divergence" — about the Noam Brown clone's
  `base_pot × P_win` non-zero-sum vs our zero-sum `c_opp/bb`. This is a
  **game-definition difference** between our solver and the Brown
  apples-to-apples reference — NOT a bug in our terminal utility. Our solver
  has always used the zero-sum convention; tests reflect this; persona results
  do not depend on Brown alignment.
- No persona test result was downgraded based on a false "convention divergence"
  in OUR solver. Verified by grep across all `W*_post_v1_7_0_result.md` files.

**Conclusion:** All persona verdicts hold. No reclassifications were keyed to
a (now-known-false) convention bug.

---

## Final Verdict Summary

| Surface | Status |
|---------|--------|
| Tests | **CLEAN** |
| GUI | **CLEAN** |
| .dmg | **CLEAN** (gated on solver correctness — confirmed by audit) |
| Persona results | **CLEAN** |

**Recommendation: SAFE-TO-CONTINUE**
