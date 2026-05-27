# Comprehensive Consistency Review — 2026-05-23 (FINAL)

**Companion to:** `comprehensive_review_2026-05-23-night.md` (preserved as the
prior snapshot, pre-test-bug discovery). This FINAL re-issue captures the
v1.5.1 ship; the v1.6.0 GUI in-flight; the v1.6.1 engine+test bundle
queued; and the now-operational aggregator-vs-true-Nash distinction.

**REVISION NOTE (2026-05-23 late, 3rd reversal):** earlier framing
oscillated between attributing the v1.5.0 acceptance divergence to
test-side bugs (deep-dive) vs an algorithmic gap (bisection). The
v1.6.1-bundle dry-run (PR 33+34+35-A+B+40 composed;
`docs/v1_6_1_dryrun_verification.md`) is the empirical authority and
re-confirms the bisection. Three code reviews verified PR 23
**structurally** faithful to Brown's `trainer.cpp:138-240`; PR 40
fixed three test-side artifacts explaining part of the 22-42pp
signal. But the dry-run shows A83 at `b1000r3000` still diverges by
~33-pp on bottom-pair-Ace cells (Brown ~0.36 call, Rust ~0.69) —
max |diff| 0.33. The structural reviews verified CODE matches
Brown's algorithm; they did not verify the algorithm produces
Brown's empirical OUTPUT at this scenario — a label-vs-semantics
gap (MEMORY.md::label-vs-semantics). **v1.6.1 ship HELD** pending
investigation. The prior 10-15% caveat is now the empirical case.

---

## 1. TL;DR

- Test-side encoding artifacts (action-axis column ordering +
  range-to-player-slot inversion + hand-string suit-order normalization)
  explained PART of the "PR 23 acceptance FAILS" signal — both engines
  agree on 9sTs/b1500 (Brown 100% fold, Rust 98.6% fold), and PR 40 +
  PR 35-A+B compose those fixes. PR 23 vector-form CFR matches Brown's
  `trainer.cpp:138-240` **structurally** per **three independent code
  reviews**. **But the v1.6.1-bundle dry-run**
  (`docs/v1_6_1_dryrun_verification.md`) **re-confirms an additional
  algorithmic divergence at deep-cap facing-raise**: A83 at `b1000r3000`,
  bottom-pair-Ace cells (3sAs, 3cAc) call ~0.69 in Rust vs ~0.36 in
  Brown — 33-pp delta, max |diff| 0.33. Label-vs-semantics gap: code
  matches algorithm structurally, output diverges empirically. v1.6.1
  ship HELD pending investigation.
- 14 forward-clean tags on public origin (v1.0.0 → v1.5.1); v1.6.0 GUI is
  in flight (LEG 18); v1.6.1 engine+test bundle (PR 33 + 34 + 35-A/B + 40)
  is composed but HELD (dry-run NO-GO; PR 35 Fix C remains dropped:
  it induced a `test_exploit_diff` regression and is orthogonal).
- Aggregator (`solve_range_vs_range`) and vector form
  (`solve_range_vs_range_rust`) solve **different mathematical objects** —
  per-hand verdicts that relied on the aggregator for range-Nash claims
  are being re-litigated through this lens. The vector form is
  structurally verified faithful to Brown by three independent code
  reviews and empirically correct on shallow-cap and river single-shot
  spots; the deep-cap facing-raise empirical divergence is the open
  investigation, NOT a wholesale rewrite trigger.

---

## 2. Critical discovery: test-side encoding bugs (3 independent reviews concur)

Three compound test-side defects in
`tests/test_v1_5_brown_apples_to_apples.py` explain the
"PR 23 acceptance test FAILS" framing (initial diagnosis at
`docs/v1_5_0_per_action_divergence_diagnosis.md`; cell-level
corroboration at `docs/pr_23_cell_divergence_deep_dive.md`;
line-by-line algorithmic triage confirms no solver-side bug at
`docs/pr_23_deep_cap_algorithmic_triage.md`). All three are real
and bundled in PR 40 for v1.6.1:

1. **Action-position mismatch.** Brown emits facing-bet actions as
   `[c, f, r_low, r_med, r_high]` (`river_game.cpp:48-71`); Rust sorts by
   action ID and emits `[f, c, r_low, r_med, A]`
   (`crates/cfr_core/src/hunl.rs:1105-1146`). The test compared
   position-by-position (`:556-583`), so position 0 lined up Brown's CALL
   against Rust's FOLD. On 9sTs/b1500 this surfaces as ~0.99 magnitude
   divergence; reality: Brown 100% fold, Rust 98.6% fold — both engines
   agree.
2. **Range-to-player-slot inversion.** Brown's P0 acts first on river
   (`river_game.cpp:9-10`); our P1 acts first
   (`poker_solver/hunl.py:286-289`). Test passed `spot.ranges[0]` as
   `p0_holes` and `spot.ranges[1]` as `p1_holes`, so each engine's opener
   received the other's defender range — structurally different games.

PR 23 vector-form CFR was structurally confirmed against Brown's
`cpp/src/trainer.cpp:138-240` by **three independent code reviews**:
iteration loop, DCFR weights (α=1.5, β=0, γ=2), regret matching,
average strategy, per-iteration discount all match Brown
line-by-line. Only documented intentional difference: scale-only
reach normalization (Brown sums to 1.0; Rust uses 1.0 per hand) —
scale-invariant under regret matching. This structural match makes
PR 23 correct on small symmetric ranges (W3.5 AA = 100% check on a
small symmetric range verified empirically) and on shallow-cap +
river single-shot scenarios.

**Dry-run verdict (`docs/v1_6_1_dryrun_verification.md`).** Composed
v1.6.1 bundle (PR 33+34+35-A+B+40, 2000-DCFR-iter, read-only worktree).
Result: **NO-GO**. K72 reduced to ~7-pp max |diff| (PR 40 column remap
helped). A83 still shows max |diff| 0.33 on 3sAs/3cAc at `b1000r3000`:
Brown call ~0.36, Rust call ~0.69. The action-axis permutation IS
applied (positions differ across engines), so divergence is **semantic**
— same action, different probability. The bisection's "additional
algorithmic divergence" hypothesis is empirically re-confirmed; the
triage's HIGH-confidence NEGATIVE is the 10-15% caveat triggering.

**v1.6.1 ship HELD.** Per synthesis fallback rule §5 row 4 (one spot
>1e-1 → HOLD + spawn deep-investigation agent), the next step is:
(1) side-by-side `dcfr_vector.rs::traverse` vs `trainer.cpp:138-240`
re-read of the facing-raise reach-propagation / regret-update path;
(2) best-response cross-check on A83 with vanilla CFR (no DCFR
discount); (3) iteration sweep 500/1000/2000/4000/8000. Affected
scenarios: deep-cap facing-raise on bottom-pair-Ace hand classes at
large raise sizes. Unaffected: river single-shot, shallow-cap
postflop, push/fold preflop.

User-validated learnings (refined):
1. "Acceptance test FAILS" doesn't AUTOMATICALLY equal "solver broken"
   — investigate test plumbing first. But test-plumbing fixes
   followed by an empirical re-test are the only way to definitively
   close the loop; code-level structural reviews alone are necessary
   but not sufficient.
2. Multi-layer fix bundles need post-composition empirical
   verification BEFORE ship — three rounds of confidence revision
   this burst (deep-dive PASS → bisection FAIL → triage PASS →
   dry-run FAIL) all traced to making confidence calls on
   reasoning-from-bundle-composition without an end-to-end run.
3. Label vs semantics: code matching an algorithm's structure
   (verified) is distinct from code producing the algorithm's
   empirical output at a specific scenario (verified separately).
   The dry-run is the gating verifier for the latter.

---

## 3. Ship cadence + tag ladder

14 forward tags on public `origin/main`; all clean; all releases published.

| Tag | Commit | What |
|---|---|---|
| v1.0.1 | `373d35c` | PR 8 NEON SIMD + cache + PCS |
| v1.1.0 | `a335680` | PR 9 HUNL preflop subgame solver |
| v1.2.0 | `363b2bb` | PR 10b real-solver UI bindings |
| v1.2.1 | `41235d0` | universal2 `_rust.so` (PR 14) |
| v1.3.0 | `58b1ebd` | PR 16 RvR aggregator (Option B) |
| v1.3.1 | `88b7a1c` | PR 20 `hero_player` gap fix |
| v1.3.2 | `2758659` | PR 15 Rust expl walk |
| v1.4.0 | `166d2b8` | PR 21 node locking |
| v1.4.1 | `89a124b` | PR 22 asymmetric contributions |
| v1.4.2 | `d9094c2` | docs honesty + `@slow` marker |
| v1.4.3 | `eea3a8b` | PR 27 `Range.diff` + PR 29 spec + PR 30 docs + PR 31 validation |
| v1.5.0 | `dc3df6c` | PR 23 vector CFR + PR 28 Brown apples-to-apples acceptance |
| v1.5.1 | `b5777f22` | docs+honesty PATCH |
| **v1.6.0** | IN FLIGHT (LEG 18) | PR 24a + 24b GUI surface |
| **v1.6.1** | PRE-STAGED (LEG 19) | PR 33 + 34 + 35 + 40 engine bundle + acceptance test fix |

v1.5.0 release notes were re-updated honestly (LEG 19 Task A) to remove
the misleading "ACCEPTANCE TEST FAILS" framing now that the failure is
diagnosed as test-side compound bugs.

---

## 4. Persona battery state

Canonical 18-workflow battery; current status **9 PASS / 5 PARTIAL / 3 BLOCKED**
(per-cohort table; some prior PASS verdicts downgraded under the
aggregator-vs-Nash lens — see §5).

| Cohort | PASS | PARTIAL | BLOCKED/INCONCLUSIVE |
|---|---|---|---|
| Marcus | 4 | 1 | 0 |
| Sarah | 1 | 2 | 2 |
| Daniel | 3 | 1 | 1 |
| Priya | 1 | 1 | 1 |
| **Total** | **9** | **5** | **3** |

Significant re-verdicts under the aggregator-vs-Nash lens:

- **W3.5 (monotone polarization):** PASS → **BLOCKED** when read as
  range-Nash; aggregator's "AA bets 68%" is basket-selection artifact.
  TRUE-Nash via PR 23 vector form gives AA pure-checks 100% matching user
  intuition (`docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md`).
- **W1.2 (JJ river deep stack):** PASS → **PARTIAL.** Aggregator's 7.69%
  fold is `3/39` (fraction of villain AA reps) — deterministic, not Nash.
  True Nash defends 100% (+1801 chips/hand).
- **W2b.2 (KK-vs-QQ-trips):** rationale revised — `fold=0.311` is faithful
  1-of-5-villain aggregation, not a Nash bluff-catching mix.

Post-v1.6.1 Wave 1 retest (W2.3, W3.4, W4.3) was previously projected
to unblock via PR 33 delegate and reach 12+ PASS. **v1.6.1 ship is
now HELD pending root-cause investigation** of the deep-cap A83
divergence; the conservative estimate is **10-12 PASS** until the
investigation concludes. Wave 1 retests that touch deep-cap facing-
raise spots may NOT cleanly PASS via the new path; shallow-cap
retests can proceed once a deep-cap fix lands. PARTIAL items that
won't close without further work regardless: W2.2 fractional-freq
(#189, v1.7.0+), W4.2 spec heuristic (subgame-mode/equity-only
mismatch), W2.4 CLI batch (CLI gap; library path is PASS).

---

## 5. Aggregator vs. True Nash — the operational insight

Documented at `docs/aggregator_vs_true_nash_explainer.md`. The codebase
ships two range-vs-range entrypoints whose names suggest they answer the
same question but actually solve different mathematical objects:

| Function | Solves |
|---|---|
| `solve_range_vs_range` (`range_aggregator.py:211`) | "For each (hero, villain) combo pair, what does *perfect-information* 1v1 Nash say? Then pool." Pluribus-blueprint aggregator. |
| `solve_range_vs_range_rust` (`crates/cfr_core/src/lib.rs:428`) | "What is the joint *imperfect-information* Nash equilibrium of hero's range vs villain's range?" PR 23 vector-form CFR (structural match to Brown per 3 reviews; deep-cap facing-raise empirical divergence under investigation). |

Critical implications:

1. The aggregator's "7.7% fold", "32% check", "68% bet" outputs are
   **deterministic basket-selection artifacts** of the aggregation rule,
   not Nash mixed frequencies. Iterating longer cannot close the gap.
2. Spec questions about bluff-catching, range polarization, polarized
   sizing, and inducing all require the vector form. The aggregator
   structurally cannot answer them.
3. The two paths agree closely where value-vs-air dominates (premium pair
   vs underpair on dry boards); they diverge by arbitrary magnitudes
   where range composition matters.

Going forward: persona retest agents must match the tool to the question
— aggregator for per-combo sanity, vector form for range-level Nash.

---

## 6. Audit + correction infrastructure built

Six artifacts now in place after the user called out unreliable
poker-intuition hand-waving:

- `docs/heuristic_judgement_audit_2026-05-23.md` — meta-process audit; every
  heuristic claim catalogued KEEP/UPDATE/REJECT.
- `docs/poker_spots_audit_2026-05-23.md` + `_CORRECTED_` + `_reverification_`
  — per-spot poker-math audits with fixture references; revised when
  board readings were wrong.
- `docs/persona_test_results/W2b_1_per_hand_breakdown.md` — first per-hand
  table for an aggregator output; establishes the breakdown convention.
- `tests/_equity_helpers.py` (PR 37) — closed-form equity oracle; removes
  the "I'll eyeball ~15% equity" failure mode.
- `docs/aggregator_vs_true_nash_explainer.md` (1197 words) — canonical
  project doc on the distinction.
- `docs/v1_5_0_per_action_divergence_diagnosis.md` + `pr_23_cell_divergence_deep_dive.md`
  — two independent diagnoses of the test-side bug.

PR 38 corrections + PR 29 spec corrections propagated to private mirror
(`docs/pr_29_pr_38_private_push_report.md`).

Five user-validated learnings now load-bearing on agent operations:

1. Solver intuition (qualitative direction fold/call/jam) is reliable
   when checked rigorously against fixture data.
2. Numerical equity estimates are 2-5× off without a calculator — use PR
   37 helper.
3. Generic descriptors ("rainbow river", "ten-high") mislead — quote the
   complete actual board from fixture.
4. "Acceptance test FAILS" doesn't equal "solver broken" — investigate
   test plumbing first.
5. Per-combo aggregation ≠ range Nash — use the right tool for the
   question.

---

## 7. Open work after v1.6.1

- **Range fractional-freq refactor** (#189) — `Range` per-combo float
  weights; v1.7.0+; unblocks W2.2.
- **Persona retest sweep** — Wave 1 (W2.3/3.4/4.3); Wave 2 (W3.5/1.2
  vector-form reretests); Wave 3 full 18-persona battery for v1.7.0
  promotion.
- **200K-iter validation** (Gate 4) — vector-form CFR on representative
  Brown spots at production iter counts.
- **v-final .dmg** (Gate 5) — universal2 macOS package post-Wave-3-clean.

---

## 8. Burst close gate progress

Five gates per PLAN.md §10:

| Gate | State | Path to close |
|---|---|---|
| 1 — Engine completeness | HELD; 3 reviews verified structural fidelity, dry-run still shows 33-pp A83 deep-cap divergence | Investigation in flight: best-response cross-check + iteration sweep + side-by-side re-read of facing-raise path |
| 2 — UI completeness | closes when v1.6.0 lands | LEG 18 in flight; PR 24a + 24b GUI surface |
| 3 — Persona completeness | 9/18 PASS; conservative 10-12 PASS pending v1.6.1 root-cause; the 13-PASS cascade requires deep-cap fix | Wave 1 retest holds for now; shallow-cap retests can proceed when v1.6.1 lands |
| 4 — Production validation | blocked behind Gate 1 | 200K-iter sweep on representative spots after v1.6.1 acceptance closes |
| 5 — Packaging | blocked behind Gates 1+4 | universal2 .dmg rebuild after v1.6.1 acceptance closes |

Dominant uncertainty is now Gate 1: the deep-cap A83 divergence root
cause is open. v1.6.0 (UI) can still proceed in parallel; v1.6.1
(engine+test bundle) HELD until the deep-cap fix lands; Wave 1
retest waits on v1.6.1; Wave 3 battery on Wave 1; Gate 5 .dmg on
Wave 3 clean. Gate 1 closure now requires both the structural reviews
AND a clean dry-run post-fix.

---

## 9. Honest framing of remaining risk

1. **Acceptance test HELD post-v1.6.1 dry-run.** The v1.6.1-bundle
   dry-run (`docs/v1_6_1_dryrun_verification.md`) empirically
   re-confirmed the bisection's "additional algorithmic divergence"
   verdict: A83 deep-cap facing-raise shows 33-pp delta on
   bottom-pair-Ace cells even with PR 40's column-axis remap applied.
   Three structural code reviews remain valid for what they checked
   (code matches Brown's algorithm structurally), but the empirical
   output diverges at this scenario. The 10-15% caveat the prior
   framing carried is now the active case. Investigation in flight:
   best-response cross-check, iteration sweep, side-by-side re-read
   of the facing-raise path. NOT a `dcfr_vector.rs` wholesale
   rewrite — most of the algorithm is verified correct shallow-cap
   and on river single-shot.
2. **Aggregator-vs-vector distinction implies some persona spec questions
   are PR-23-gated indefinitely.** W3.5 polarization, W1.2 bluff-catching,
   W2b.x range-aware mixing — not answerable via the aggregator at any
   iteration count. Until the vector-form path is exposed across all
   harness entrypoints (PR 33 delegate is the first step), some PARTIAL
   verdicts won't migrate to PASS.
3. **200K-iter Gate 4 validation may surface edge cases.** Vector-form
   CFR has been exercised at ≤3000 iter; the 2000-iter Brown acceptance
   test is the deepest run. Memory pressure on monotone boards,
   preflop-1326 deferral (`dcfr_vector.rs:49-50, 755`), and chance-enum
   interactions with the delegate path are not yet production-stressed.
4. **The aggregator path continues to ship.** Legitimate uses (fast
   Pluribus-quality answer, monotone boards near vector memory edge,
   per-combo sanity check). Docs, spec, and persona tests must label
   which path produced a given number.

---

## Sources

Prior reviews: `docs/comprehensive_review_2026-05-23-night.md`,
`comprehensive_review_2026-05-23-late.md`. Test-bug diagnosis:
`docs/v1_5_0_per_action_divergence_diagnosis.md`,
`docs/pr_23_cell_divergence_deep_dive.md`. Aggregator distinction:
`docs/aggregator_vs_true_nash_explainer.md`. Ship plan:
`docs/leg19_v1_6_1_ship_plan.md`. Audits:
`docs/heuristic_judgement_audit_2026-05-23.md`,
`docs/poker_spots_audit_2026-05-23.md` + corrections + reverifications.
Persona: `docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md`,
`W2b_1_per_hand_breakdown.md`, `W1_2_v1_5_1_retest_deep_stack.md`,
`W3_5_range_vs_range_v1_5_1.md`. Dry-run:
`docs/v1_6_1_dryrun_verification.md`. Algorithm reference:
`references/code/noambrown_poker_solver/cpp/src/trainer.cpp:138-240`,
`crates/cfr_core/src/dcfr_vector.rs`,
`crates/cfr_core/src/hunl.rs:1105-1146`. Private push:
`docs/pr_29_pr_38_private_push_report.md`.
