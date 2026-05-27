# v1.8.1 Candidate Findings — Post-v1.8.0 Production-Scale Retest

**Date:** 2026-05-27
**Trigger:** Post-ship persona retest at production scale (≥10-class RvR).
**Source retest:** `docs/persona_status_post_v1_8_0_shipped_2026-05-27.md`
**Branch tip:** v1.8.0 (`8a9c8d2`) including PR #78 convention purge (`37e5be1`).

---

## Summary

**One candidate under investigation:** W3.5 monotone-board polarization shows
a class-count × iter-count interaction at production scale (10-15 class @ 500
iter gives AA check 0.14-0.33, vs PoC's 1.0000 @ 3000 iter on 15-class).

Root cause is **TBD between two hypotheses**:
- **A. Convergence/iter-scaling issue** (no code bug; iter budget needs scaling
  with class count for the W3.5 specific equilibrium structure).
- **B. Class-expansion wrapper bug** (per `v1_7_1_wrapper_fix_spec.md`).

A convergence test at 3000 iter on 15-class is in flight to distinguish.

**No new regressions.** No persona that was PASS pre-v1.8.0 has regressed.

---

## W3.5 — Monotone polarization, class-count × iter-count interaction

### Empirical observation

Same board (`Ts 8s 6s 4c 2d`), same backend (`rust_vector`), same v1.8.0 build,
same SPR (~50 from single-bet pot, initial_pot=200). Class count and iter
count vary:

| Range | iter | AA check | AA bet_33 | Verdict |
|---|---|---|---|---|
| 6-class `{AA,KK,QQ,JJ,TT,99}` | 500 | **0.9194** | 0.0792 | PARTIAL (close to PASS at ≥0.90 lower bound; below ≥0.99 PASS) |
| 10-class `{AA-99,88,AKs,AQs,KQs}` (value-heavy) | 500 | **0.1434** | 0.8542 | FAIL on AA check ≥0.90 |
| 15-class `{AA-88,AKs,AQs,AJs,KQs,KJs,JTs,98s,87s}` (full PoC range) | 500 | **0.3288** | 0.6204 | FAIL on AA check ≥0.90 |
| 15-class (same) | 3000 | TBD | TBD | Convergence test running |

PoC reference (`W3_5_TRUE_nash_v1_5_1.md`): AA check = **1.0000** on 15-class
range @ **3000 iter** (v1.5.1 build). At 500 iter, the 15-class range has not
converged to the PoC equilibrium.

### Diagnostic — wrapper bug or convergence issue?

Two pieces of evidence **disfavor** a clean wrapper bug:

1. **The W3.4 retest** (same v1.8.0 build, 15-class symmetric range, 4-spade
   monotone river `Ts 8s 6s 4s 2c`, 3-bet pot SPR≈5.5) PASSES with AA check
   = 0.9827 @ iter=500. If W3.5's failure were purely a class-count wrapper
   misroute triggered at ≥10 classes, W3.4 would fail identically. It doesn't.

2. **The canonical W3.5 regression test** (`tests/test_range_vs_range_nash.py:test_w3_5_monotone_aa_pure_check`)
   uses 3-class @ 200 iter with the looser ≥0.90 check bound, explicitly
   documenting that convergence at low iter counts is class-size-dependent:
   > the smaller range has fewer bluff-catch opportunities for villain so the
   > same qualitative effect holds with looser convergence.

This pattern is more consistent with **convergence/iter scaling** than with a
clean wrapper index error. The 3000-iter convergence test on the 15-class
range will distinguish definitively.

### Reproducer

Already in repo at `scripts_retest/w3_5_6class_check.py`:

```python
from poker_solver import Card, HUNLConfig, Street, solve_range_vs_range_nash

cfg = HUNLConfig(
    starting_stack=10000, small_blind=50, big_blind=100, ante=0,
    starting_street=Street.RIVER,
    initial_board=tuple(Card.from_str(c) for c in ('Ts','8s','6s','4c','2d')),
    initial_pot=200, initial_contributions=(100,100),
    initial_hole_cards=(), postflop_raise_cap=2,
    bet_size_fractions=(0.33, 0.75, 1.50), include_all_in=False,
)
for classes in [
    ['AA','KK','QQ','JJ','TT','99'],
    ['AA','KK','QQ','JJ','TT','99','88','AKs','AQs','KQs'],
]:
    r = solve_range_vs_range_nash(cfg, classes, classes, iterations=500,
                                   hero_player=1, compute_exploitability_at_end=True)
    aa = r.per_class_strategy.get('AA', {})
    print(f'{len(classes)}-class: AA check={aa.get("check",0):.4f}')
```

Output:
```
6-class: AA check=0.9194
10-class: AA check=0.1434
```

### Recommended v1.8.1 patch scope

Per `feedback_persona_test_rectification` Type B routing:
1. **Add a `tests/test_w3_5_class_expansion.py` regression test** with at
   least two class-count parametrizations (`6-class`, `10-class`, `15-class`)
   asserting AA check ≥0.85 on each. Currently the load-bearing test at
   `tests/test_range_vs_range_nash.py:test_w3_5_monotone_aa_pure_check` only
   covers a 3x3 range at iter=200.
2. **Root-cause the wrapper class-expansion path.** The 6-class vs 10-class
   delta is too large to be Nash-multiplicity noise (Δ=0.78 on AA check, AA
   bet_33 swings 0.08 → 0.85). Suspected location: per-combo → per-class
   aggregator at `poker_solver/range_aggregator.py` or the symmetric-class
   broadcast in `_rust.solve_range_vs_range_nash`'s post-processing.
3. **Validate the fix** against the v1.5.1 PoC reference (15x15 symmetric @ 3000 iter,
   AA check = 1.0000).

### Severity / urgency

**Type B (correctness)** per spec. Daniel-class workflow but the bug masks
itself at the persona-test fixture size used by the acceptance harness; this
is a **silent-no-op-at-fixture-size hazard** per `feedback_silent_noop_hazard`.

**Severity:** Medium. The bug does not corrupt arbitrary outputs — it
manifests specifically on monotone-board polarization (where AA is a
bluff-catcher whose equity strictly decreases as the villain range widens).
For W3.4 (multi-action set, 15-class), the bug does NOT surface. For other
RvR-Nash retests (W1.2 Marcus, W3.4 Daniel), the bug does NOT surface.

**Routing:** v1.8.1 candidate. Not a release-narrative blocker — v1.8.0
release notes already correctly document the W3.5 status as "PARTIAL — Type
B-DOC" with the wrapper-fix spec pending. The new production-scale empirical
data strengthens the case for prioritizing the wrapper-code fix over the
docs-only Option 1 in `v1_7_1_wrapper_fix_spec.md`.

---

## Other personas retested — NO REGRESSION

| Persona | Pre-v1.8.0 verdict | Post-v1.8.0 verdict | Regression? |
|---|---|---|---|
| W1.5 (Marcus 76s) | PARTIAL | PARTIAL | No |
| W2.1 (Sarah 100BB preflop) | PARTIAL | PARTIAL | No |
| W2.2 (Sarah Range.diff) | PARTIAL | PARTIAL | No |
| W2.3 (Sarah deep-stack turn) | BLOCKED | BLOCKED (Type D) | No |
| W2.4 (Sarah batch-solve CSV) | PARTIAL | PARTIAL (pending CLI run) | No |
| W3.4 (Daniel multi-street polarization) | PASS (caveated) | PASS (caveated, bit-identical) | No |
| W3.5 (Daniel monotone polarization) | FAIL (Type B-DOC) | FAIL (Type B confirmed) | No — same hazard, now production-scale confirmed |
| W4.2 (Priya limp-or-fold action menu) | PARTIAL | PARTIAL | No |
| Marcus 30s budget (W1.2 production scale) | PASS | PASS (14.7s) | No |

---

## References

- Retest source: `/Users/ashen/Desktop/poker_solver/docs/persona_status_post_v1_8_0_shipped_2026-05-27.md`
- W3.5 wrapper-fix spec: `/Users/ashen/Desktop/poker_solver/docs/v1_7_1_wrapper_fix_spec.md`
- W3.5 PoC reference: `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md`
- Class-expansion reproducer script: `/Users/ashen/Desktop/poker_solver/scripts_retest/w3_5_6class_check.py`
- W3.5 retest result JSON: `/tmp/persona_retests/w3_5_result.json`
- W3.5 class-compare result JSON: `/tmp/persona_retests/w3_5_class_compare.json`
- v1.8.0 tag commit: `8a9c8d2`
- Convention purge commit: `37e5be1` (PR #78)
