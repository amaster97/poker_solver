# Archived Claims — 2026-05-23 Pruning Sweep

Retrospective archive of claims pruned from PLAN.md during the post-retest-5th-reversal continuous-pruning sweep. Kept for reasoning-trail integrity per `feedback_continuous_pruning.md`.

---

## 1. v1.6.1 strict-gate plan (REFUTED by dry-run #2)

**Original claim (mid-burst):** PR 35c (Path A paired cap-guard fix on Rust + Python) + PR 35d (Path C Brown base_pot quirk doc + acceptance tolerance widen to 5e-2) + PR 46 panic fix would close the v1.6.1 strict-gate acceptance test and ship as the next tag.

**Reasoning chain:**
- A83 deep-cap divergence (Rust=98.6% vs Brown=0% bet) initially diagnosed as cap-guard tree-shape mismatch.
- Path A (drop ALL_IN at cap on both engines) was committed on `pr-35c-paired-fix` @ `63c9432`.
- Path C (Brown convention doc + widen 5e-2 tolerance) committed on `pr-35d-brown-quirk-doc` @ `e9e5d3a`.
- PR 46 `dcfr_vector.rs:651` panic fix branched in flight.

**Refutation:** Dry-run #2 returned **conclusive NO-GO** — K72 max-diff 4.22e-1 (42pp), A83 max-diff 2.71e-1 (27pp). Even with Path A+C applied, divergence remained driven by:
- Residual phantom-ALL_IN at deep nodes downstream of jam (6 action-count mismatches at `b1000A`)
- Brown's `base_pot × P_win` non-zero-sum convention vs our zero-sum `c_opp/bb` convention — a genuine game-definition divergence, not a bug in either engine

**Outcome:** Path D proposed — pause strict gate, ship engine improvements only as v1.6.1-engine, reframe gate as structural-parity test with WARN/FAIL bands (Path B) for future release. Awaiting user OK on Path D as of 2026-05-23 late.

**Doc reference:** `docs/v1_6_1_path_d_decision.md`.

---

## 2. PR 33 / 34 / 35 / 40 engine bundle (RESCOPED into Path D)

**Original claim:** PR 33 (Python delegate to Rust RvR), PR 34 (off-by-one vector indexing), PR 35 (canonicalization), PR 40 (acceptance-test plumbing fix) would all ship as a v1.6.1 bundle and "cascade BLOCKED→PASS for W2.3/W3.4/W4.3."

**Refutation:** The strict-gate framing was wrong-from-the-start (see #1 above). PR 33 + PR 40 fold into Path D's v1.6.1-engine ship; PR 34/35 deferred pending structural-parity reframe. The cascading PASS prediction was extrapolation without per-fix instrumentation — violated `feedback_no_extrapolate.md`.

---

## 3. PR 47 / v1.7.1 wrapper class→combo expansion bug (REFUTED post-R5)

**Original claim:** v1.7.0's `solve_range_vs_range_nash` wrapper had a class→combo expansion bug at the suspected `_expand` site (`range_aggregator.py:984`). W3.5 15-class hard-FAIL (AA bet_33 = 0.9999 vs PoC's 0.0000) attributed to the wrapper not properly expanding class labels (`AA`) into the 6 suit combos.

**Refutation:** Independent diff-test (`docs/v1_7_1_wrapper_fix_spec.md`) verified:
1. Wrapper run AND direct `_rust.solve_range_vs_range_rust` on identical 79-combo input → matching per-class strategies within DCFR variance.
2. Wrapper on PoC's 15 hand-curated combos → reproduces v1.5.1 PoC AA pure-check 0.9999.

**Conclusion:** Wrapper correctly translates class labels to combos. The 79-combo class-expansion has a genuinely different Nash than the 15-combo hand-curated PoC (Ace-blocker dynamics on villain's AKx + spade-blocker AA combos shift the equilibrium). Not a code bug — API class-expansion semantics nuance.

**Outcome:**
- v1.7.1 code patch CANCELED.
- W3.5 verdict reclassified Type B → Type B-DOC.
- Replaced with docs-only USAGE.md update on `pr-48-usage-v1-7-0-semantics` (class-expansion semantics + Nash path perf scope river/turn/flop tiers).
- v1.7.0 release notes correction retracts wrapper-bug claim.

---

## 4. W3.5 verdict thread (5 sequential reversals)

The most-reversed claim of the burst. Documented in §13 R5 meta-meta-lesson but worth pulling out for the retrospective:

1. **R1** — "solver-broken" (per PR 23 cell divergence deep-dive)
2. **R2** — "test-bugs-only" (per bisection of v1.5.0 acceptance harness)
3. **R3** — "solver-has-deep-cap-bug" (per A83 dry-run #1)
4. **R4** — "no bug, just test plumbing" REFUTED by dry-run #2 (real cross-engine divergence vs Brown; Path D)
5. **R5** — "W3.5 wrapper bug" REFUTED by independent diff-test (only API class-expansion semantics nuance)

**Cost of each reversal:** docs/code walkbacks. R3 cost the 27-edit walkback across 6 docs; R5 cost two staged-but-not-yet-shipped artifacts (v1.7.0 release notes + USAGE.md) before the diff-test caught the misframing.

**Codified rules from this thread:**
- `feedback_post_ship_persona_retest.md` (R3 origin, R5 refinement)
- `feedback_independent_verification.md` (R5 — must independent-diff-test before concluding code bug)
- `feedback_label_vs_semantics.md` (REINFORCED — both cascading misroutes traced to label-trust)

---

## 5. DCFR perf "regression" (RESOLVED — measurement artifact)

**Original claim:** A DCFR perf regression was flagged earlier in the burst suggesting kernel-level slowdown.

**Resolution:** Re-instrumented under PR 32/37 helper conventions; no kernel-level slowdown. The "regression" was a measurement artifact from helper-convention drift across versions.

---

## 6. PR 23 algorithmic correctness doubt (RESOLVED)

**Original claim (mid-burst):** PR 23 might have a deep algorithmic bug in the vector-form CFR implementation; the v1.5.0 9sTs vs b1500 acceptance test failure (Brown=0% vs Rust=98.6% bet) looked catastrophic.

**Resolution:** Four independent diagnostic threads converged:
- Per-action divergence diagnosis → TEST-BUG (action-ordering + range-slot misassignment)
- PR 23 cell deep-dive → solver Nash matches hand-derived 9sTs Nash
- W3.5 RvR PoC → aggregator artifact, not vector-form bug
- W1.2 deep-stack → 92.3% total reraise validates user prediction; 7.7% fold is aggregator artifact

**Outcome:** PR 23 engine algorithm is empirically correct. PR 40 fixes the acceptance test plumbing; the solver itself is NOT changing. (Note: Later A83 dry-run #2 showed Brown-convention divergence is real but distinct — PR 23 still sound on its own contract.)

---

## 7. Carryover items retired in this sweep

- PR 5 TURN abstraction coverage gap → resolved in PR 6 audit (Rust port resolved via cleaner production-scale clustering)
- PR 4 kmeans homogeneity test loosened → resolved at v0.5.2 / PR 4.5
- `origin/equity-precision` dangling branch → deleted from origin 2026-05-22
- v0.6.0 + v1.0.0 tag ratification → self-resolved via integration→main FF merge
- PR 10a Q3 iter count → reframed as exploitability-target slider (see §1 Solver UI control)
- PR 8 / PR 9 / PR 10b sequencing → all shipped in v1.2.0 cluster

---

## Meta-pattern (carried forward as lesson §13 in PLAN.md)

The burst's pattern of refutation cascades validates `feedback_research_first_failure_protocol.md` and `feedback_no_extrapolate.md`:
- Premature single-cause locks cost docs/code walkbacks each reversal.
- Cascading verdicts based on label-trust (function/test names promising semantics they don't deliver) are the highest-cost failure mode.
- Independent diff-test verification BEFORE concluding code regression is now mandatory for any verdict that could trigger v-NEXT release or doc retraction.
