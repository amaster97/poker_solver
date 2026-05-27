# Acceptance Test Reframe — `test_v1_5_brown_apples_to_apples.py` from strict gate to sanity check

**Date:** 2026-05-24
**Author:** orchestrated single-thread agent (rewrite + tri-worktree verification)
**Status:** PROPOSED — verification COMPLETE; verdict in §9.
**Supersedes:** Path D (`docs/v1_6_1_path_d_decision.md`) `xfail` interim plan IF this reframe is approved.
**Canonical test file:** `/tmp/acceptance-reframe/pr50/tests/test_v1_5_brown_apples_to_apples.py`
**Patch:** `docs/acceptance_test_reframe.patch` (vs `origin/pr-50-facing-all-in-guard`)

---

## 1. Problem statement

The original test
(`tests/test_v1_5_brown_apples_to_apples.py::test_v1_5_brown_apples_to_apples_parity`)
required strict per-action probability match between Brown's
`river_solver_optimized` and our Rust vector-form CFR
(`_rust.solve_range_vs_range_rust`) within `PER_ACTION_TOL = 5e-2` (5pp).
Empirically (per dry-run #2 with PR 35c + PR 40 bundled):

| Spot | Max \|diff\| | Cells > 5e-2 | Action-count mismatches |
|------|--------------|--------------|-------------------------|
| `dry_K72_rainbow` | 0.42 | ~305 | 6 |
| `dry_A83_rainbow` | 0.27 | ~306 | 6 |

PR 50's `stack > to_call` facing-all-in guard closes the action-count
mismatches but is predicted (per `docs/pr_50_independent_verification.md`)
to leave K72 max \|diff\| still in the 0.30-0.42 range, driven by Brown's
`base_pot × P_win` terminal-utility convention divergence (candidate
(d) in `docs/a83_deep_cap_root_cause_investigation.md`).

User's reframe (verbatim): *"we don't have to match exactly with Brown if
our choice is different, just use as sanity check to make sure our logic
is coming nicely."*

This is well-grounded: Brown is not ground truth (their action menu is
intentionally narrower than ours; mixed-strategy Nash equilibria are
non-unique; terminal-utility conventions differ).

## 2. Design space

The brief surfaced four options:

* **Option A — STRUCTURAL parity.** Same histories visited, same hand
  classes, shallow per-action strict + deep just structural.
* **Option B — CORRELATION.** Per-hand-class action-probability vectors
  correlate ≥ 0.7 (Pearson) at shallow nodes.
* **Option C — SHALLOW-ONLY strict + DEEP-EXEMPT.** Strict at depth 0-1,
  exempt depth 2+.
* **Option D — TRENDS.** Directional agreement on aggression buckets.

## 3. Chosen approach — HYBRID (A + C + D)

The hybrid combines the strongest signal from each pure option:

| Layer | From option | What it gates | Why hybrid wins |
|-------|-------------|---------------|-----------------|
| 1. Structural (coverage, well-formedness, action-count parity) | A | Tree shape + engine sanity | Catches no-decision / NaN / topology bugs |
| 2. Shallow-strict per-action (root only) | C | Genuine regressions (e.g., AA folds 99%) | Strict where action menus *must* match |
| 3. L1-distance directional ceiling + 75th-pct | D + Option B | No row > 1.0 L1 (= near-inversion); p75 ≤ 0.60 | Catches widespread divergence; tolerates documented deep-cap drift |
| 4. Top-action agreement | D | Brown ≥ 70% mass → Rust ≥ 20% on same action | Catches sign-flipped strategies that L1 might allow |

**Why not pure B (Pearson correlation):** action vectors are 2-5 long,
so correlation is too noisy and Pearson treats `[0.5, 0.5]` vs
`[0.99, 0.01]` as 100% correlated even though they're very different
strategies.

**Why not pure C (shallow-only strict, deep-exempt):** silently allows
arbitrary strategy at deep nodes, including outright inversions. Layer 3
+ 4 catch that.

**Why not pure D (trends):** loses the regression-detection power at
root that C provides for free.

## 4. Gate parameters

| Constant | Value | Rationale |
|----------|-------|-----------|
| `COVERAGE_FLOOR` | 0.80 | Inherited from original; tree shapes must mostly match |
| `ROW_SUM_TOL` | 1e-3 | Floating-point arithmetic envelope for averaged DCFR strategy |
| `ACTION_COUNT_PARITY_FLOOR` | 0.50 | Pre-PR-50: ~85%; with PR 50 fix: ~100%. 0.50 catches a topology regression that would affect more than half the comparison surface |
| `SHALLOW_PER_ACTION_TOL` | 5e-2 | Same as the original strict bar — but applied ONLY at depth-0 |
| `SHALLOW_MAX_VIOLATIONS_PER_SPOT` | 5 | Tolerates a handful of mixed-strategy noise rows at root; L1 ceiling covers anything pathological |
| `L1_PER_ROW_CEILING` | 1.0 | Max L1 between two probability distributions is 2.0; 1.0 = "at most half the mass moved between actions" |
| `L1_P75_CEILING` | 0.60 | Tolerates the documented 22-42pp deep-cap drift while rejecting widespread mass-swap |
| `TOP_ACTION_BROWN_THRESHOLD` | 0.70 | Only check rows where Brown is committed (avoids ambiguity when Brown is itself mixing) |
| `TOP_ACTION_MIN_MASS` | 0.20 | Rust must put ≥ 20% on Brown's preferred action — catches outright inversion but allows Nash mixing |
| `TOP_ACTION_PASS_FLOOR` | 0.60 | ≥ 60% of "committed Brown" decisions must directionally agree |

## 5. What this catches (regression criteria)

* **AA folds 99% at root** (any spot) → blocked by shallow-strict (Layer 2).
* **Hole-card hashing bug** that mis-assigns QQ → caught by Layer 1b
  (sum-to-1 / NaN) + Layer 3 L1 (mis-attributed rows produce extreme L1).
* **Phantom action at root** → blocked by action-count parity (Layer 1c)
  + shallow-strict (Layer 2).
* **Tree-construction bug** (no decisions emitted) → blocked by coverage
  floor (Layer 1a).
* **Engine emits NaN or unnormalized distributions** → blocked by
  per-row well-formedness (Layer 1b).
* **Sign-flipped strategy** (Brown jams, we fold) → blocked by Layer 4
  top-action agreement.

## 6. What this INTENTIONALLY does NOT catch (documented allowed divergence)

* Brown calls top-pair-K 87%; we call 45% at deep-cap (L1 ≈ 0.84,
  passes the 1.0 ceiling; consistent with terminal-utility convention
  drift documented in `a83_deep_cap_root_cause_investigation.md`).
* Brown bets 33% pure with mid-pair; we mix 20%-bet33 / 13%-bet75 (top
  action agreement passes; L1 ≈ 0.13).
* The 305 / 306 deep-cap cells that strictly exceed 5e-2 in dry-run #2
  (informational `STRICT_RESULT` continues to report this metric for
  monitoring without blocking ship).

## 7. Implementation

See `tests/test_v1_5_brown_apples_to_apples.py`. Key changes:

* Module docstring rewritten to explain the four layers and what is /
  isn't caught.
* New constants block (Layer 2/3/4 thresholds) above.
* Added `_brown_to_rust_action_permutation` helper (ported from PR 40)
  so action-column comparison is correct (Brown facing-bet order
  `[c, f, raises]` vs Rust `[f, c, raises, A]`). Without this, every
  facing-bet cell on `main` is silently wrong.
* New test body iterates cells once, accumulating per-row L1
  distances, top-action checks, shallow violations, and the
  informational strict-violation count. Then asserts the four layers.
* Prints `STRICT_RESULT` (informational) + `SANITY_RESULT` (gated) for
  monitoring.

## 8. Verification

**Three worktree-isolated runs:**

```bash
git worktree add /tmp/acceptance-reframe/main   origin/main
git worktree add /tmp/acceptance-reframe/pr50   origin/pr-50-facing-all-in-guard
git worktree add /tmp/acceptance-reframe/bundle origin/main
# Apply PR 46 + PR 35c + PR 50 to bundle worktree.
# Apply rewritten test (with PR 40 Fix B player-slot swap) to each.
# Build poker_solver in each (pip install -e . triggers maturin).
# Symlink references/ for Brown binary discovery.
# Run pytest in each.
```

Results (full output captured in
`/tmp/acceptance-reframe/{main,pr50,bundle}_test_output.log`):

### Run 1: `origin/main` (rewritten test, NO PR 46/PR 50)

Both spots FAIL — but for upstream reasons, NOT because of the reframed gates:

| Spot | Outcome | Reason |
|------|---------|--------|
| `dry_K72_rainbow` | FAIL @ Layer 1a | coverage 53.3% < 80% — Brown produced 30 histories, Rust matched 16. This is the known PR 35-Fix-A renderer bug (history canonicalization incomplete on plain main). |
| `dry_A83_rainbow` | FAIL pre-Layer-1 | Rust solver PANIC at `dcfr_vector.rs:651`: "len is 49 but index is 49." This is the off-by-one fixed by PR 46 (originally PR 34). |

These pre-empt the new sanity layers, so the reframe's effectiveness
cannot be evaluated on plain main. The failures are the documented
blockers Path D was created to work around.

### Run 2: `pr-50-facing-all-in-guard` (rewritten test, PR 50 only)

Same outcome as origin/main — PR 50 doesn't fix the renderer (PR 35-Fix-A
territory) or the panic (PR 46 territory).

### Run 3: `bundle` = origin/main + PR 46 + PR 35c + PR 50 (rewritten test)

This is the realistic v1.6.1 bundle (the same composition as
`docs/leg21_v1_6_1_engine_only_ship_plan.md` §1; my rewrite includes
PR 40's Fix A + Fix B inline AND PR 35's renderer Fix A `stack_ceiling`
parameter).

Both spots FAIL — but the failure surfaces a NEW, previously-hidden
test-side or engine-side **suit-encoding bug** that the original strict
gate had been hiding behind action-count / coverage failures.

| Spot | K72 | A83 |
|------|-----|-----|
| L1 max (need ≤ 1.0) | 1.777 ✗ | 1.815 ✗ |
| L1 p75 (need ≤ 0.60) | 0.060 ✓ | 0.041 ✓ |
| L1 median | 0.003 ✓ | 0.002 ✓ |
| Top-action pass rate (need ≥ 60%) | 99.3% (422/425) ✓ | 99.2% (609/614) ✓ |
| Shallow violations (allow ≤ 5) | 20 ✗ | 20 ✗ |
| Coverage | 100% ✓ | 100% ✓ |
| Action-count parity | 100% ✓ | 100% ✓ |
| Strict per-cell violations (informational) | 183 | 233 |
| Strict max \|diff\| (informational) | 8.886e-1 | 9.076e-1 |

**Diagnostic signal from the failure:**

K72 shallow violations show paired suit-swaps:

```
hand=8s9s hist='' action='c':    brown=0.000  rust=0.335
hand=8s9s hist='' action='b750': brown=0.770  rust=0.370
hand=8c9c hist='' action='c':    brown=0.343  rust=0.000
hand=8c9c hist='' action='b750': brown=0.365  rust=0.775
```

Brown's `8s9s` ≈ Rust's `8c9c`, and Brown's `8c9c` ≈ Rust's `8s9s`. The
same swap pattern appears on `5h6h` / `5d6d` and `8sTs` / `8cTc`. This
is consistent with a SUIT-ORDER mismatch in the test-side
hand-string-rendering path (`noambrown_wrapper._card_to_brown_str` /
`_brown_card_id`):

  * `poker_solver.card.SUITS = "shdc"` (Python suit 0 = spades).
  * `noambrown_wrapper._BROWN_SUIT_CHARS = "cdhs"` (Brown suit 0 = clubs).
  * `_card_to_brown_str` uses `_BROWN_SUIT_CHARS[card.suit]` directly —
    treating our Python suit-0 (spades) as Brown's suit-0 (clubs).

  Net effect: when we forward `Card(rank=8, suit=0)` (= our "8 of
  spades") to Brown's JSON, we serialize it as `"8c"` (Brown's spelling
  of suit 0 = clubs). Brown solves under that label. Our subsequent
  Rust solve receives `card_to_int(Card(8, 0)) = 24` and emits the
  hole-string as "8s" (Rust's `SUITS = "shdc"`). The two engines have
  solved a structurally identical game but mis-labeled hands, so when
  the test looks up `brown_hand_str="8c9c"` in Rust's lookup it pulls
  the strategy our Rust assigned to what it thinks is "the same combo"
  in OUR convention — which is `8c9c` by our integer encoding, NOT the
  same physical combo Brown was solving for.

This is a **pre-existing wrapper bug**, NOT a bug introduced by my
reframe. The original strict gate did NOT surface it because:

  * Pre-PR-46: A83 panicked, so it never ran end-to-end.
  * Pre-PR-35-Fix-A: K72 coverage capped at 53.3%, never reaching the
    per-cell loop.

The reframed gate's `L1_PER_ROW_CEILING = 1.0` ASSERTION + Layer 2
shallow-strict are both doing their job: catching the real divergence
pattern that was hidden by upstream failures.

The deep-cap candidate-(d) drift (Brown's `base_pot × P_win` terminal-
utility convention) is the SECOND finding visible in `L1_p75 = 0.060`
and the 183-233 informational strict violations: most cells are very
close but a few hundred deep-cap cells drift 5-30pp, consistent with
the v1_6_1_dryrun_attempt_2 measurements.

## 9. Verdict

**RELAXED-GATE-STILL-FAILS — but the failure surfaces a real, actionable
test-side bug, not a gate-too-tight problem.**

The reframe is functioning correctly. The four layers each carry
diagnostic weight:

  * Layer 1 (structural): coverage 100%, action-count parity 100%, no
    NaN — passes. Confirms PR 46 + PR 35c + PR 50 close the upstream
    blockers.
  * Layer 2 (shallow-strict): FAILS @ 20 violations on each spot.
    Surfaces the suit-encoding bug as paired hand-swaps at root.
  * Layer 3 (L1 directional): max L1 = 1.78 / 1.82 (need ≤ 1.0) FAILS;
    p75 + median = 0.06 / 0.003 PASS. The few hand pairs that ARE
    suit-swapped have near-mirror-image distributions, blowing past
    the ceiling. The aggregate (p75, median) is healthy.
  * Layer 4 (top-action): 99.3% / 99.2% PASS — directional agreement
    is overwhelming.

### Path forward

1. **DO NOT ship v1.6.1 with this gate as-is.** The suit-encoding bug
   is real and load-bearing for any consumer comparing our solver
   against Brown / external references. Triage: noambrown_wrapper's
   `_card_to_brown_str` and `_brown_card_id` need the SUIT character
   mapping (Python's "shdc" index → Brown's "cdhs" index) instead of
   direct index forwarding.

2. **Alternative if user prefers to ship now:** the four-layer gate
   could be made even more permissive by switching Layer 2 from
   "shallow-strict at root" to "shallow-DIRECTIONAL at root" (e.g.,
   require Pearson correlation ≥ 0.5 instead of per-action ≤ 5e-2).
   Doing so would mask this bug, which is the opposite of the
   sanity-check intent. NOT recommended.

3. **Path-D (xfail) is no longer the right hammer.** With the
   reframed gate landed AND the suit-encoding bug surfaced, the new
   v1.6.1 plan should be:
     a. Land the reframed test (this PR).
     b. Fix the wrapper suit-encoding bug as a follow-up PR (likely
        small; <50 LOC).
     c. Re-run the reframed test on the patched bundle.
     d. If all four layers pass: ship v1.6.1 with the reframed gate
        as the new strict-but-fair acceptance bar.
     e. If Layer 2/3 still fail at residual deep-cap candidate-(d)
        drift after the suit-fix: SHALLOW_MAX_VIOLATIONS_PER_SPOT
        can move from 5 to ~15 with documented rationale.

## 10. Artifacts

  * Rewritten test: `tests/test_v1_5_brown_apples_to_apples.py`
    (872 lines; old was 683).
  * This document.
  * Run outputs (transient, in `/tmp/`):
    - `/tmp/acceptance-reframe/main_test_output.log` (origin/main —
       blocked by panic + renderer)
    - `/tmp/acceptance-reframe/pr50_test_output.log` (PR 50 only —
       blocked by panic + renderer)
    - `/tmp/acceptance-reframe/bundle_test_output2.log` (PR 46 +
       PR 35c + PR 50 — surfaces suit-encoding bug + deep-cap drift)
