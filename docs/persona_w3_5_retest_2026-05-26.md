# W3.5 Post-v1.8.0 SIMD Retest — Daniel (Pro / Coach) Monotone Polarization

**Test date:** 2026-05-26
**Driver:** Orchestrator W3.5 retest per `feedback_post_ship_persona_retest`
**Trigger:** v1.8 SIMD (Phases 1-4 + AVX2) landed on `origin/main`; W3.5 wrapper-fix
retest owed at production scale (>=10-class RvR).
**Pre-staged prompt used (verbatim spec):** `docs/persona_test_results/post_v1_7_0_W3_5_retest_prompt.md`
(no post-v1.8.0 W3.5 prompt was pre-staged; the v1.7.0 prompt is the active spec since
the wrapper-fix recommendation in `docs/v1_7_1_wrapper_fix_spec.md` was the last
substantive update to W3.5 and v1.8 SIMD is correctness-preserving by design).

## Verdict

**PARTIAL (6-class spec smoke) / PARTIAL-BELOW-RANGE-GATE (10-class production scale)**
- Classification: **Type B-DOC** (no change from the late-2026-05-23 `v1_7_1_wrapper_fix_spec.md` reclassification).
- Regression vs prior verdict: **NO REGRESSION.** 6-class spec smoke is bit-identical
  to the v1.7.0 retest (AA check 0.9224 vs 0.9224, range check 0.9495 vs 0.9495,
  exploitability 1.6821 vs 1.6821). v1.8 SIMD is correctness-preserving on this fixture.
- Wrapper path is intact: `backend == 'rust_vector'`, no exceptions, exploitability
  bounded.
- Aggregator-vs-Nash diagnostic still present (aggregator AA total-bet = 0.80
  vs Nash AA total-bet = 0.078 on the 6-class) — the "Nash gives the right
  qualitative answer" claim is intact.

The PARTIAL stems from the same range-composition phenomenon documented in
`v1_7_1_wrapper_fix_spec.md`: as the range widens beyond the 6-class spec window,
AA's Ace-blocker dynamic against villain's bluff combos shifts the equilibrium
away from pure-check. This was determined to be feature-not-bug.

## Test fixture path

- **Active spec:** `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/post_v1_7_0_W3_5_retest_prompt.md`
- **Reference PoC:** `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md`
- **Wrapper-fix spec:** `/Users/ashen/Desktop/poker_solver/docs/v1_7_1_wrapper_fix_spec.md`
- **Prior 6-class result (v1.7.0):** `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/W3_5_post_v1_7_0_result.md`
- **Prior wider-range result (v1.7.0):** `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/W3_5_post_v1_7_0_wider_range_result.md`
- **Unit test:** `/Users/ashen/Desktop/poker_solver/tests/test_range_vs_range_nash.py::test_w3_5_monotone_aa_pure_check`
  (Tier 2; passes at 200 iter / 3-class / >=0.90 threshold per current source)

## Invocation command

```bash
/Users/ashen/Desktop/poker_solver/.venv/bin/python /tmp/w3_5_retest_2026_05_26.py
```

The driver runs three solves verbatim from the prompt fixture (board `Ts 8s 6s 4c 2d`,
pot 200, stack 10k, bet sizes (0.33, 0.75, 1.50), no all-in, raise_cap=2,
hero_player=1 BB river-open):

1. **SPEC-6-class-500iter** — the prompt's standard run, classes `[AA, KK, QQ, JJ, TT, 99]`.
2. **PROD-10-class-500iter** — production-scale run per `feedback_post_ship_persona_retest`
   (>=10-class), classes `[AA, KK, QQ, JJ, TT, 99, 88, 77, 66, 55]`.
3. **Aggregator sanity** — `solve_range_vs_range` on the same 6-class for the
   aggregator-vs-Nash diagnostic.

Driver source: `/tmp/w3_5_retest_2026_05_26.py`. Raw JSON: `/tmp/w3_5_retest_2026_05_26.json`.
Console log: `/tmp/w3_5_retest_2026_05_26.log`.

## Environment

- **Interpreter:** `/Users/ashen/Desktop/poker_solver/.venv/bin/python` (CPython 3.13.1, **arm64**).
- **`poker_solver.__version__`:** `1.7.0` (note: source `__init__.py` has not been
  bumped to 1.8.0 yet despite v1.8 SIMD landing on `origin/main`; v1.8.0 release
  execution PR `97886e1` is the release-script + runbook PR, not the version bump).
- **Rust extension:** `/Users/ashen/Desktop/poker_solver/poker_solver/_rust.cpython-313-darwin.so`,
  Mach-O 64-bit arm64 (verified via `file`; **no silent-skip hazard** per
  `feedback_dotso_arch_check`).
- **Editable install:** working tree at `origin/main` HEAD = `bf645ae` (v1.8 release
  notes commit); covers PRs 32/33/38/41/43-56.
- **CWD during run:** project root (editable install resolves correctly).

## Raw output

### SPEC-6-class-500iter (matches v1.7.0 retest exactly)

```
backend='rust_vector' iterations=500 solve_wall_s=8.80 total_wall_s=62.23 exploitability=1.6821
AA per-class strategy: {'bet_150': 0.000275, 'bet_33': 0.075967, 'bet_75': 0.001311, 'check': 0.922447}
AA check freq: 0.9224  (threshold >= 0.99)
AA max single-bet-size: 0.0760  (FAIL gate if > 0.50)
Range aggregate check: 0.9495  (threshold >= 0.85)
```

Per-class breakdown:
| Class | check  | bet_33 | bet_75 | bet_150 |
|-------|--------|--------|--------|---------|
| AA    | 0.9224 | 0.0760 | 0.0013 | 0.0003  |
| KK    | 1.0000 | 0.0000 | 0.0000 | 0.0000  |
| QQ    | 1.0000 | 0.0000 | 0.0000 | 0.0000  |
| JJ    | 1.0000 | 0.0000 | 0.0000 | 0.0000  |
| TT    | 0.8422 | 0.0448 | 0.0012 | 0.1119  |
| 99    | 0.9327 | 0.0328 | 0.0008 | 0.0337  |

### PROD-10-class-500iter (production scale per memory rule)

```
backend='rust_vector' iterations=500 solve_wall_s=22.21 total_wall_s=75.38 exploitability=1.6700
AA per-class strategy: {'bet_150': 2.1e-06, 'bet_33': 0.36028, 'bet_75': 0.000195, 'check': 0.6395}
AA check freq: 0.6395  (threshold >= 0.99)
AA max single-bet-size: 0.3603  (FAIL gate if > 0.50)
Range aggregate check: 0.7835  (threshold >= 0.85)
```

### Aggregator sanity (6-class, 100 iter)

```
Aggregator AA: {'bet_150': 6.8e-05, 'bet_33': 0.3275, 'bet_75': 0.4724, 'check': 0.2000}
Aggregator AA total bet: 0.8000 (expected ~0.68 per v1.5.1 PoC)
Aggregator wall_clock: 0.33s
```

## Acceptance criteria scorecard

| Criterion                            | Threshold         | 6-class 500    | 10-class 500   | Pass? |
|--------------------------------------|-------------------|----------------|----------------|-------|
| Function runs without raising        | required          | yes            | yes            | yes   |
| `backend == 'rust_vector'`           | required          | yes            | yes            | yes   |
| AA check frequency                   | >= 0.99           | 0.9224         | 0.6395         | **no** (PARTIAL) |
| AA single-bet-size > 0.50            | < 0.50 (FAIL gate)| max=0.076      | max=0.360      | **yes** (no hard-fail) |
| Range aggregate check                | >= 0.85           | 0.9495         | 0.7835         | 6c yes / 10c below |
| Wall-clock per solve                 | <= 15 min         | 8.8s solve     | 22.2s solve    | yes   |
| Aggregator-Nash divergence present   | qualitative       | 0.80 vs 0.078  | n/a            | yes (canonical diagnostic intact) |

## Regression check vs v1.7.0 baseline (6-class, 500-iter)

| Metric              | v1.7.0 retest | This (v1.8) | Delta      |
|---------------------|--------------:|------------:|-----------:|
| AA check freq       | 0.922447      | 0.922447    | 0.000000   |
| AA bet_33           | 0.075967      | 0.075967    | 0.000000   |
| Range-aggregate check| 0.9495       | 0.949546    | 0.000046   |
| Exploitability      | 1.6821        | 1.6821      | 0.000021   |
| Solve wall_clock    | 13.73 s       | 8.80 s      | -4.93 s (faster) |

**Bit-identical strategy output**; SIMD path improved solve wall-clock by ~36% (8.8s
vs 13.73s for the same 500 iter on this 6-class fixture). This is consistent with
the v1.8 release-notes "~1.0x not 4-8x" honesty correction (bf645ae): correctness
preserved, modest perf gain, no dramatic kernel speedup.

## Type classification

**Type B-DOC** (unchanged from `v1_7_1_wrapper_fix_spec.md` 2026-05-23 reclassification).

Per `feedback_persona_test_rectification`:
- **NOT Type A (docs-only)** because the 6-class result still misses the spec's
  >=0.99 PASS gate.
- **NOT Type B-CODE** because:
  - The hard-FAIL "aggregator-artifact" gate (AA single-bet > 0.50) is NOT tripped.
  - 6-class result is bit-identical to v1.7.0 — no SIMD-introduced regression.
  - The wrapper-fix investigation (`v1_7_1_wrapper_fix_spec.md`) already confirmed
    via diff-test that wrapper output matches direct Rust call on identical
    79-combo input. The wider-range divergence is the genuine Nash for the
    class-expanded range (Ace-blocker dynamic on villain's AKx bluff combos).
- **NOT Type C-CRIT / C-USE / C-NICE** because the spec applies and the function
  works.
- **NOT Type D** because well under the 30 min kill-switch.

**Type B-DOC** = docs must clarify the class-expansion semantics of
`solve_range_vs_range_nash`; the function itself is doing what its contract says.

## Comparison to prior W3.5 verdicts

| Date / Verdict | Setup | AA check | AA max bet | Range check | Status |
|---|---|---:|---:|---:|---|
| v1.5.1 PoC (hand-curated 15 combos, direct `_rust`) | 15 combos | **1.0000** | 0.0000 | 0.8677 | PoC PASS |
| v1.7.0 retest 6-class wrapper | 6 classes / 500 iter | 0.9224 | 0.076 | 0.9495 | PARTIAL |
| v1.7.0 retest 6-class wrapper | 6 classes / 3000 iter | 0.9369 | 0.063 | 0.9533 | PARTIAL (= Type B per spec) |
| v1.7.0 retest 15-class wrapper | 15 classes / 3000 iter | 0.0000 | 0.9999 | 0.7691 | FAIL → reclassified to Type B-DOC |
| **v1.8 retest 6-class wrapper (THIS)** | 6 classes / 500 iter | **0.9224** | 0.076 | 0.9495 | **PARTIAL (= v1.7.0)** |
| **v1.8 retest 10-class wrapper (THIS)** | 10 classes / 500 iter | **0.6395** | 0.360 | 0.7835 | **PARTIAL (between 6-cl and 15-cl)** |

The 10-class result interpolates smoothly between the 6-class (still mostly check)
and the 15-class (AA pure-bet via Ace-blocker exploitation). The wider the
class-expanded range, the further from the PoC's "AA pure-check" answer — because
the Nash equilibrium of the class-expanded range is genuinely different. This
matches the wrapper-fix spec's findings.

## Time budget compliance

- **Daniel's budget (`persona_time_budgets.md §2`):** <=15 min per solve. Both
  Nash runs and the aggregator sanity well inside.
- **Total wall-clock:** 137s for all three runs (62s + 75s + 0.3s plus warmup).
  Inside the 5 min hard cap.
- **Kill-switch (30 min):** not triggered.

## Recommendation

**Re-classify W3.5 status:** **NO CHANGE** from the snapshot's "FAIL → Type B (wrapper bug)"
narrative position — but the snapshot is already stale per
`v1_7_1_wrapper_fix_spec.md` (which reclassified to **Type B-DOC** late on
2026-05-23). The snapshot at `docs/persona_test_status_2026-05-25.md:49` line still
shows "FAIL → Type B (wrapper bug)" — that line should be **updated** to reflect
the Type B-DOC reclassification that landed via the wrapper-fix spec investigation
on 2026-05-23 late evening. The "v1.7.1 ship in flight" note in the snapshot
should also be revised: no wrapper code patch is required (per
`v1_7_1_wrapper_fix_spec.md` Option 1: docs-only).

**Concrete next steps:**

1. **Update `docs/persona_test_status_2026-05-25.md` line 49** to "PARTIAL →
   Type B-DOC (no code patch needed; class-expansion semantics doc clarification
   per `v1_7_1_wrapper_fix_spec.md`)".
2. **Update PLAN.md §10 Gate 3 ledger** to align with the Type B-DOC verdict.
3. **Apply the wrapper-fix spec's Option 1 doc-only changes** (still pending):
   - Add docstring note in `solve_range_vs_range_nash` about class-expansion
     impact on equilibrium.
   - Add a `test_w3_5_aa_pure_check_curated_combos` regression test that
     reproduces the PoC via 4-char combo labels.
   - DO NOT add a wide-range test asserting AA pure-check (the wide-range
     equilibrium genuinely places AA as a value-bet).
4. **v1.8 release narrative validation:** v1.8 SIMD does NOT regress W3.5 on the
   6-class spec smoke. The "Nash gives the right qualitative answer where
   aggregator gives the textbook wrong answer" claim is intact (aggregator AA
   total-bet 0.80 vs Nash AA total-bet 0.078 on 6-class — 10x divergence).
5. **No v1.7.1 ship needed for W3.5** — the `feedback_long_running_session_wrap`
   mentions a v1.7.1 ship in flight; per the wrapper-fix spec there is no code
   patch required for W3.5. Any v1.7.1 ship should drop the W3.5 fix item and
   carry only the docs note + curated-combo regression test.

## Hard-constraint compliance

- **Did NOT modify test or source code** — only wrote driver and report files
  in `/tmp` and `docs/`.
- **Did NOT exceed 5 min wall-clock on any single run.** Both Nash solves
  completed in well under the cap (8.8s and 22.2s solve wall-clock).
- **Used arm64-capable Python** (`.venv/bin/python`) — `_rust.so` verified arm64;
  no silent-skip.
- **No `pytest.skip()` masking** — driver is a direct Python call, raises on
  failure.

## Files

- Driver: `/tmp/w3_5_retest_2026_05_26.py`
- Raw JSON: `/tmp/w3_5_retest_2026_05_26.json`
- Console log: `/tmp/w3_5_retest_2026_05_26.log`
- This report: `/Users/ashen/Desktop/poker_solver/docs/persona_w3_5_retest_2026-05-26.md`
