# Minimal Nash Regression Test — Specification

**Test file:** `tests/test_minimal_nash_fixture.py` (17 test functions, ~580
LOC). **Design source:** `docs/minimal_diff_test_fixture.md` (2026-05-23/24).
**Baseline pass commit:** `3843ce7` (origin/main, v1.7.0). **Wall-clock:**
~4.2 s on M-series for the full 17-test sweep (5000 DCFR iterations,
2-class 12-combo fixture, river-only, postflop_raise_cap=1).

---

## Test purpose

This is a **forever regression gate** for the solver's basic Nash kernel.
It pins down whether the vector-form CFR solver
(`_rust.solve_range_vs_range_rust` and its user-facing wrapper
`solve_range_vs_range_nash`) computes the correct Nash equilibrium for the
shallowest possible range-vs-range river spot whose Nash is hand-computable
via dominance arguments.

It was designed in response to the v1.6.1 dry-run #2 22-42pp Brown-vs-ours
strategy divergence at deep-cap river spots, to discriminate between:

  * **shallow bug** — the basic algorithmic kernel (action menu, comparator,
    DCFR weighting, reach handling, terminal utility) is broken. If this
    test FAILS, the bug exists at the simplest possible form.
  * **depth-related bug** — only emerges with multi-decision raise trees
    (3-bet, 4-bet sequences). If this test PASSES but deep-cap diff tests
    fail, the bug lives in raise-tree accumulation across many decisions.

Per the design doc, **a passing result is consistent with the "depth-
related divergence" hypothesis**; a failing result narrows the bug to
the shallow kernel.

---

## What's being asserted

### Fixture (per `docs/minimal_diff_test_fixture.md` §"Fixture spec")

* Board: `7c 5d 3h Qs 2c` (rainbow brick river).
* Both ranges: `{AA, KK}` (6 combos per class per player, uniform).
* Pot: 2 BB. Stack remaining: 3 BB per side. Bet size: 0.5x pot (= 1 BB).
* `postflop_raise_cap=1` (no 3-bets reachable).
* P1 (BB seat) acts first on the river per `hunl.py:425-429`.
* 5000 DCFR iterations, α=1.5 / β=0 / γ=2.0.

### Assertions

**12 strict-strategy slots** (`STRICT_TOL = 0.02`):

| # | Infoset | Hand class | Action | Expected |
|---|---|---|---|---|
| 1 | Root P1 | KK | bet | 0 |
| 2 | Root P1 | KK | check | 1 |
| 3 | After-P1-check P0 | KK | bet | 0 |
| 4 | After-P1-check P0 | KK | check | 1 |
| 5 | After-P1-bet P0 | AA | call | 1 |
| 6 | After-P1-bet P0 | AA | fold | 0 |
| 7 | After-P1-bet P0 | KK | call | 0 |
| 8 | After-P1-bet P0 | KK | fold | 1 |
| 9 | After-P1-check-P0-bet P1 | AA | call | 1 |
| 10 | After-P1-check-P0-bet P1 | AA | fold | 0 |
| 11 | After-P1-check-P0-bet P1 | KK | call | 0 |
| 12 | After-P1-check-P0-bet P1 | KK | fold | 1 |

**2 mixed-strategy slots** (`MIXED_TOL = 0.05`, informative only):

| # | Infoset | Hand class | Assertion |
|---|---|---|---|
| 13 | Root P1, AA | (bet, check) | both in `[0, 1]`; sum ≈ 1 |
| 14 | After-P1-check P0, AA | (bet, check) | both in `[0, 1]`; sum ≈ 1 |

**3 sanity/wiring tests:**

| Test | Asserts |
|---|---|
| `test_solver_emits_expected_root_keys` | Rust path produces P1-root keys for all 12 AA/KK combos in the lossless `<hole>|<board>|r|` format. |
| `test_wrapper_strategy_matches_direct` | `solve_range_vs_range_nash` wrapper's `per_history_strategy` is value-equal to the direct `_rust.solve_range_vs_range_rust` call. |
| `test_wrapper_strict_kk_fold_facing_bet` | Wrapper-side smoke for the KK-facing-bet strict slot. |

---

## Expected behavior on origin/main

**Status: PASSING (all 17/17)** at `3843ce7` (v1.7.0).

Numerical values observed at 5000 iters (precision: to 6 decimals; all
strict slots converge to machine precision, not just within tolerance):

```
STRICT slots (expected ~0 or ~1; STRICT_TOL=0.02):
  Root P1 KK    bet  : 0.000000 (expect 0)
  Root P1 KK    check: 1.000000 (expect 1)
  AfterCk P0 KK bet  : 0.000000 (expect 0)
  AfterCk P0 KK check: 1.000000 (expect 1)
  AfterBet P0 AA call: 1.000000 (expect 1)
  AfterBet P0 AA fold: 0.000000 (expect 0)
  AfterBet P0 KK call: 0.000000 (expect 0)
  AfterBet P0 KK fold: 1.000000 (expect 1)
  AfterXkBet P1 AA call: 1.000000 (expect 1)
  AfterXkBet P1 AA fold: 0.000000 (expect 0)
  AfterXkBet P1 KK call: 0.000000 (expect 0)
  AfterXkBet P1 KK fold: 1.000000 (expect 1)

MIXED slots (a_1, a_2 in [0,1]; MIXED_TOL=0.05):
  Root P1 AA    bet  : 0.075472 = a_1
  Root P1 AA    check: 0.924528
  AfterCk P0 AA bet  : 1.000000 = a_2
  AfterCk P0 AA check: 0.000000
```

Wall clock: 4.24 s for the full 17-test sweep on an M-series Mac.

Note: the two mixed slots land on **different points of the 1-dim
indifference manifold** — (a_1 ≈ 0.075, a_2 ≈ 1.0). Both are valid Nash
points by definition of indifference; the design doc explicitly allows
this and only checks the strict slots as load-bearing. Any future Brown
parity diff that pins these to specific values should be added as a
separate "DCFR-averaging-convention sentinel" test, not folded into this
regression gate.

---

## What it means if this test starts failing

The 12 strict slots are determined by **pure dominance arguments** (no
mixing required) — they must hold at ANY correct Nash equilibrium. A
failure on any strict slot indicates the basic algorithmic kernel is
broken, with the specific failing slot localizing the suspect (per
`minimal_diff_test_fixture.md` §"Diagnostic interpretation"):

| Failing slot | Likely suspect |
|---|---|
| KK at no-bet-to-face not checked (Slots 1-4) | action-menu emitter, equity computation, or DCFR weighting believing KK has more equity than it does. |
| AA facing bet not calling (Slots 5-6, 9-10) | per-combo equity at terminal nodes (AA dominates KK), action-menu, or reach handling. |
| KK facing bet not folding (Slots 7-8, 11-12) | per-combo equity, action menu, or terminal utility for the dominated-pair case. |
| `test_wrapper_strategy_matches_direct` fails | wrapper-side bug in `solve_range_vs_range_nash` (input permutation, key rewriting, or extra post-processing). NOT a kernel bug. |
| `test_solver_emits_expected_root_keys` fails | infoset key format drift between the Rust emitter and the Python `HUNLState.infoset_key` reader. Likely a refactor regression. |
| Mixed-slot tests fail (`a_1`, `a_2` outside `[0,1]` or sum != 1) | strategy emit shape regression or normalization bug; check `dcfr_vector.rs` ratio-conversion. |

**Triage workflow on failure:**

1. Re-read `docs/minimal_diff_test_fixture.md` §"Predicted divergence
   pattern" — the failing slot tells you which suspect to investigate.
2. Sanity-check the action menu by running:
   ```python
   from poker_solver import HUNLConfig, HUNLPoker, Street, parse_board
   cfg = HUNLConfig(starting_stack=300, ..., bet_size_fractions=(0.5,),
                    postflop_raise_cap=1, ...)
   game = HUNLPoker(cfg)
   state = game.initial_state()
   print(game.legal_actions(state))  # expect [CHECK=1, BET_33=3]
   ```
3. Compare against Brown's solver on the same fixture (per design doc
   §"How to invoke both solvers" → §"Brown's solver — shell invocation").
   Brown agreement + ours disagreement = our-side bug. Brown disagreement
   too = spec-level convention difference (DCFR variant, terminal utility
   convention, etc.).
4. Compare `_rust.solve_range_vs_range_rust` direct vs `solve_range_vs_range_nash`
   wrapper outputs — divergence isolates to the wrapper (Python-side bug);
   agreement means the bug is in the Rust kernel.

**Tolerance rationale:**

* `STRICT_TOL = 0.02` is from the design doc's "must match within 2pp"
  spec. Empirically at 5000 iters this fixture converges to machine
  precision, so the tolerance is 4 orders of magnitude looser than the
  observed residual. We keep the doc's value for safety — future
  changes that cause even 1pp drift would still pass but trip Brown
  parity tests.
* `MIXED_TOL = 0.05` is looser because the mixed slots are on an
  indifference manifold; DCFR can legitimately land anywhere on it. The
  tolerance is for the sum-to-1 check, not for any specific value.

---

## How to run

```bash
# All tests in the fixture (4.2s on M-series; passes on origin/main 3843ce7).
pytest tests/test_minimal_nash_fixture.py -v

# Just the 12 strict slots (the load-bearing diagnostic).
pytest tests/test_minimal_nash_fixture.py -v -k "strict"

# Just the wiring/sanity tests (key format, wrapper-matches-direct).
pytest tests/test_minimal_nash_fixture.py -v -k "wrapper or emits or smoke"
```

The test requires:
* `poker_solver` installable (or PYTHONPATH set).
* `poker_solver._rust` extension built (`maturin develop --release`).
* `solve_range_vs_range_nash` available (PR 43 / v1.7.0+).

Tests auto-skip if any of these are missing.

---

## Cross-references

* Design doc: `docs/minimal_diff_test_fixture.md` — fixture spec, hand-
  computed Nash, expected frequencies, Brown invocation pattern.
* Rust binding: `crates/cfr_core/src/lib.rs:428` — `solve_range_vs_range_rust`.
* Wrapper: `poker_solver/range_aggregator.py` — `solve_range_vs_range_nash`
  (PR 43, v1.7.0).
* Vector-form CFR core: `crates/cfr_core/src/dcfr_vector.rs`.
* Infoset key contract: `poker_solver/hunl.py:504-539` — `HUNLState.infoset_key`.
* Companion test: `tests/test_range_vs_range_rust_diff.py` — exploitability-
  based diff against Python `dcfr.py` ground truth (used for the
  3/10-hand-per-side cases; this minimal fixture is finer-grained because
  the Nash is hand-computable rather than just exploitability-bounded).
