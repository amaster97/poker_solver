# v1.8.1 Candidate Findings — Post-v1.8.0 Production-Scale Retest

**Date:** 2026-05-27
**Trigger:** Post-ship persona retest at production scale (≥10-class RvR).
**Source retest:** `docs/persona_status_post_v1_8_0_shipped_2026-05-27.md`
**Branch tip:** v1.8.0 (`8a9c8d2`) including PR #78 convention purge (`37e5be1`).

---

## Summary

**One candidate identified:** W3.5 monotone-board polarization, class-expansion
semantics bug. The pattern was previously documented as a "Type B-DOC" /
wrapper-class-expansion hazard but had only been smoke-confirmed at the
6-class size; the post-v1.8.0 production-scale retest provides a clean
**reproducible production-scale demo** at v1.8.0 tip.

**No new regressions.** No persona that was PASS pre-v1.8.0 has regressed.

---

## W3.5 — Monotone polarization, class-expansion bug

### Empirical observation

Same board (`Ts 8s 6s 4c 2d`), same backend (`rust_vector`),
same iter (500), same v1.8.0 build. Only the symmetric class count differs:

| Range | Classes | AA check | AA bet_33 | AA bet_75 | AA bet_150 | Verdict |
|---|---|---|---|---|---|---|
| 6-class | `AA,KK,QQ,JJ,TT,99` | **0.9194** | 0.0792 | 0.0013 | <1e-4 | Polarized (close to spec; PASS at ≥0.90 lower bound) |
| 10-class | `AA,KK,QQ,JJ,TT,99,88,AKs,AQs,KQs` | **0.1434** | **0.8542** | 0.0024 | <1e-5 | **Inverted** (FAIL on AA check ≥0.90, AA max bet <0.50) |

Across the 6 → 10 class expansion:
- AA check drops 0.92 → 0.14 (−0.78 absolute)
- AA bet_33 rises 0.08 → 0.85 (+0.77 absolute)
- AA flips from "pure bluff-catcher" to "pure value bet"

### Why this is a Type B (wrapper) bug, not a Nash result

Per the persona acceptance spec and `W3_5_TRUE_nash_v1_5_1.md` PoC:
- AA on `Ts 8s 6s 4c 2d` with no nut flush is a **bluff-catcher**. Every flush
  beats AA; AA's only "value" is against under-pairs that fold to any bet.
  Pure check at Nash equilibrium is the empirical PoC result (1.0000 @ 3000 iter
  on 15x15 symmetric).
- AA's equity against a 10-class symmetric range that adds `{88, AKs, AQs, KQs}`
  is **lower** than against 6-class `{AA-99}`. (AKs / AQs / KQs all carry the
  As-of-the-suited which makes AA's blockers thinner; 88 is another set that
  beats AA. Equity strictly decreases.)
- A pure value-bet from a bluff-catcher whose equity dropped is **NOT** a
  Nash result — it's a strategy-route artifact.

The aggregator-misroute pattern (`v1_7_1_wrapper_fix_spec.md` §3) describes
exactly this: per-combo Nash strategies from the inner CFR are class-expanded
into the wrapper's aggregator slot via a class-count-derived index; the index
arithmetic is silent-no-op at one class count and silently-routes-wrong at
another.

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
