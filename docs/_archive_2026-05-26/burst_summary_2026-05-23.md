# Burst Summary — 2026-05-23

User-facing recap of the day's autonomous work on the GTO solver.

---

## 1. TL;DR

- **Shipped:** v1.4.1 → v1.5.1 on public origin (five tagged releases), plus the PR 23 vector-form CFR engine landing in v1.5.0.
- **In flight:** v1.6.0 GUI ship (PR 24a + 24b bundle); v1.6.1 engine bundle is HELD — composed dry-run empirically re-confirmed a 33-pp deep-cap divergence on A83 bottom-pair-Ace at `b1000r3000` even with all test-side fixes applied; root-cause investigation underway.
- **Pending:** v1.6.1 root-cause investigation (best-response cross-check + iteration sweep + line-by-line re-read of facing-raise path); 200K-iter production validation; v-final .dmg rebuild; v1.7.0 CLI + aggregator→vector wiring bundle (branches ready, queued).

---

## 2. Ships landed (public origin)

| Version | Tag      | Headline                                         | Notes                                            |
|---------|----------|--------------------------------------------------|--------------------------------------------------|
| v1.4.1  | `v1.4.1` | Asymmetric initial-contributions (facing-bet)    | PR 22 + follow-up (`ceff9bb` / `89a124b`)        |
| v1.4.2  | `v1.4.2` | Docs honesty + test marker + `__post_init__` validation | `d9094c2`; HUNLConfig loud failure at boundary |
| v1.4.3  | `v1.4.3` | Validation + `Range.diff` + docs refresh         | `eea3a8b`; unblocks W2.2 set-difference work     |
| v1.5.0  | `v1.5.0` | Vector-form DCFR (Brown trainer.cpp pattern)     | `dc3df6c`; PR 23 + acceptance harness            |
| v1.5.1  | `v1.5.1` | Test rigor + docs honesty                        | `b5777f2`; engine bundle deferred to v1.5.2/v1.6.1 |

**v1.6.0 GUI in flight at time of writing** — PR 24a (RvR + hero swap) and PR 24b (node-lock editor, range editor polish, asymmetric inputs, slider tooltip) already on integration; release tag pending.

---

## 3. Major architectural finding

**PR 23 vector-form CFR matches Brown structurally per 3 independent code reviews; PR 40 fixes test-side artifacts; deep-cap A83 facing-raise still empirically diverges (33-pp on bottom-pair-Ace).**

The framing "v1.5.0 acceptance test FAILS → solver bug" decomposes into two distinct findings:

(a) Three compound TEST-side encoding bugs in `tests/test_v1_5_brown_apples_to_apples.py` — confirmed real:
1. Action-axis column ordering — Brown emits `[c,f,...]` at facing-bet; Rust emits `[f,c,...]` via `sort_unstable` on action ID. Fixed by PR 40 Fix A (semantic permutation `_brown_to_rust_action_permutation`).
2. Range-to-player-slot inversion — Brown's P0 opens river; our engine's P1 opens river. Opener-range was wired to defender slot. Fixed by PR 40 Fix B.
3. Hand-string suit-order normalization — `cdhs` vs `shdc` causes silent miss-mapping on a subset of cells. PR 45 conditional (defer unless coverage dips).

(b) At least one genuine algorithmic gap at deep-cap facing-raise NOT yet localized — the dry-run empirically confirmed it.

PR 23 vector-form CFR is **structurally** faithful to Brown's `trainer.cpp:138-240` per **three independent code reviews**:
- `docs/v1_5_0_per_action_divergence_diagnosis.md` (per-action divergence diagnosis)
- `docs/pr_23_cell_divergence_deep_dive.md` (cell-level empirical re-test)
- `docs/pr_23_deep_cap_algorithmic_triage.md` (line-by-line code read vs Brown's `cpp/src/trainer.cpp:138-240`)

The structural reviews verified CODE matches Brown's algorithm; they did not verify the algorithm produces Brown's empirical OUTPUT at the deep-cap facing-raise scenario — a **label-vs-semantics gap** (MEMORY.md::label-vs-semantics meta-rule). The composed-bundle dry-run (PR 33+34+35-A+B+40, 2000-DCFR-iter, read-only worktree; `docs/v1_6_1_dryrun_verification.md`) re-confirms the bisection's "additional algorithmic divergence" verdict: A83 max |diff| 0.33 on 3sAs/3cAc at history `b1000r3000` (Brown call ~0.36, Rust call ~0.69). K72 max |diff| reduced to ~0.07 (PR 40 column remap helped). Affected scenarios: deep-cap facing-raise on bottom-pair-Ace hand classes at large raise sizes. Unaffected: river single-shot, shallow-cap postflop, push/fold preflop. **v1.6.1 ship HELD pending root-cause investigation**: best-response cross-check (does the gap disappear at vanilla CFR? → DCFR discount suspect), iteration sweep at 500/1000/2000/4000/8000 (monotone shrink → late convergence; plateau → algorithmic), and side-by-side re-read of `dcfr_vector.rs::traverse` vs `trainer.cpp:138-240` on the facing-raise reach-propagation / regret-update path.

**Aggregator vs True Nash distinction surfaced empirically.**

The W3.5 reverification (PR 42) flipped a "FAIL" to PASS once we ran the test against the vector-form path on a small symmetric range. The TRUE Nash test showed AA = 100% check at river-open — the poker-intuitive answer — while the aggregator's "68% bet" was a per-combo basket-selection artifact, **not** range Nash. Both code paths solve different mathematical objects. The vector-form path is structurally verified faithful to Brown by three independent code reviews and empirically matches Brown on shallow-cap and river single-shot spots; deep-cap facing-raise empirical divergence is the open investigation. Documented in `docs/aggregator_vs_true_nash_explainer.md`.

---

## 4. Persona test progress

| Stage                                | PASS | PARTIAL | BLOCKED |
|--------------------------------------|------|---------|---------|
| Start of burst (rough)               | ~5   | ~8      | ~5      |
| Current (post W3.5 reversal)         | 10   | 5       | 3       |
| Post-v1.6.1 ship (active estimate)   | 10-12 | TBD    | TBD     |
| Post-deep-cap-fix (optimistic)       | 13   | 5       | 0       |
| Post-v1.7.0 (aggregator→vector wiring + CLI) | TBD | TBD | TBD     |

W3.5 reversal alone moved one item from BLOCKED→PASS. The active post-v1.6.1 estimate is **10-12 PASS**: v1.6.1 ship is HELD pending the deep-cap A83 root-cause investigation, so Wave 1 retests on deep-cap facing-raise spots may not cleanly PASS via the new path. The 13-PASS cascade target is reachable only once the deep-cap fix lands; shallow-cap retests can proceed against v1.6.1's bundle once the dry-run blocker clears.

---

## 5. Burst close gate status

| Gate                                   | Status                                                                |
|----------------------------------------|-----------------------------------------------------------------------|
| 1. Engine completeness                 | HELD; 3 reviews verified structural fidelity, dry-run still shows 33-pp A83 deep-cap divergence; root-cause investigation in flight |
| 2. UI completeness                     | in flight (v1.6.0 GUI shipping)                                       |
| 3. Persona completeness                | 10/18 PASS; conservative 10-12 PASS estimate pending v1.6.1 root-cause |
| 4. 200K-iter production validation     | **not yet started** — blocked behind Gate 1                           |
| 5. Packaging (v-final .dmg)            | pending Gates 1-4                                                     |

---

## 6. Honest framing for what's NOT done

- **v1.6.1 engine bundle HELD pending root-cause investigation.** Composed dry-run (PR 33 + PR 34 + PR 35-A + PR 35-B + PR 40; PR 35-C remains dropped) was empirically re-tested in a read-only worktree at 2000-DCFR-iter; result: A83 max |diff| 0.33 on bottom-pair-Ace cells at `b1000r3000` (Brown call ~0.36, Rust call ~0.69), K72 max |diff| ~0.07. 3 independent code reviews verified PR 23 structurally faithful to `trainer.cpp:138-240` (iteration loop, DCFR weights, regret matching, average strategy match line-by-line); PR 40 confirmed and fixed three test-side encoding artifacts. The remaining gap is semantic — same action, different probability, at the deep-cap facing-raise path — and was the 10-15% caveat in the prior synthesis. Investigation in flight: best-response cross-check (does the gap disappear at vanilla CFR? → DCFR discount suspect), iteration sweep 500/1000/2000/4000/8000, side-by-side re-read of `dcfr_vector.rs::traverse` vs `trainer.cpp:138-240` focused on facing-raise reach-propagation / regret-update. NOT a wholesale `dcfr_vector.rs` rewrite — most paths are verified correct. Full dry-run report: `docs/v1_6_1_dryrun_verification.md`.
- **Range fractional-frequency refactor** is v1.7.0+ scope. W2.2 PARTIAL won't fully close until shipped (PR 43 branch is ready but queued).
- **200K-iter production validation not yet attempted.** Multi-hour run; cannot fire until v1.6.1 lands and bisection resolves.
- **v-final .dmg not yet rebuilt.** PR 11 packaging pass pending Gate 4.

---

## 7. Codified meta-learnings

Six meta-learnings now in memory:

1. *(existing)* min-five-agents floor with CPU contention nuance
2. *(existing)* don't-extrapolate equity/numerics without calculator
3. *(existing)* research-first failure protocol
4. *(existing)* stall-check + relaunch
5. *(existing)* parallel-agents-default
6. **NEW** — **label vs semantics:** function/test names don't equal what they actually do; verify both layers. Surfaced from the W3.5 "FAIL" reversal and now load-bearing across THIS burst's three confidence reversals on PR 23. The v1.5.0 acceptance test divergence has TWO components: (a) confirmed test-side encoding artifacts (action-axis column ordering, range-to-player-slot inversion, hand-string suit-order normalization), all label-vs-semantics at the test/engine boundary; (b) a genuine algorithmic gap at deep-cap facing-raise that the structural code reviews did NOT catch — the reviews verified CODE matches Brown's algorithm, but did not verify the algorithm produces Brown's empirical OUTPUT at this scenario. Same meta-pattern, deeper layer.

**Anti-patterns avoided AND surfaced:** 2-3 false-confidence cycles caught by user pushback this burst — equity hand-waves (resolved with `tests/_equity_helpers.py`) and the "test FAIL = solver bug" reflex. **One anti-pattern NOT avoided:** revising confidence three times on PR 23 (deep-dive PASS → bisection FAIL → triage PASS → dry-run FAIL) without running an end-to-end composed-bundle empirical re-test until the third revision. Cross-cutting meta-discipline: **structural code reviews are necessary but not sufficient** — multi-layer fix bundles need post-composition empirical verification BEFORE shipping. When an empirical observation (bisection) conflicts with a code-level structural read (3 reviews concur), the only definitive arbiter is a composed-bundle end-to-end run; the dry-run was that arbiter here, and the empirical truth was the bisection's.

---

## 8. Audit infrastructure built today

- `docs/heuristic_judgement_audit_2026-05-23.md` — meta-process audit of how spot judgements were being made.
- `docs/poker_spots_audit_2026-05-23.md` + `_CORRECTED_` + `_reverification_` — per-spot poker math, multi-pass.
- `docs/aggregator_vs_true_nash_explainer.md` — operational guide distinguishing the two code paths.
- `tests/_equity_helpers.py` (PR 37) — rigorous numerical oracle for persona acceptance criteria.
- `tests/test_v1_5_brown_apples_to_apples.py` — acceptance harness (with PR 40 fixes pending bundle).
- Per-hand W2b.1 breakdown — first-of-kind detailed per-hand persona analysis (`docs/persona_test_results/`).

---

## 9. PRs landed / queued

**Public origin (shipped):** PR 22, 25 (#1), 26, 27, 28 + module-level docstring, 30, 31, 32, 33, 36, 37.

**Public branches ready (queued):** PR 39 (CLI ergonomics subcommands — `7584e06`), PR 43 (aggregator→vector wiring).

**Public bundle held (pending root-cause investigation):** PR 33 + PR 34 (`bf178c8` off-by-one panic fix) + PR 35-A/B (`9033266` canonicalization + player-index inversion + max_raises ALL_IN; Fix C dropped per synthesis) + PR 40 (`68a3ac1` test-side encoding fixes). Together → v1.6.1 engine. Dry-run NO-GO: A83 deep-cap facing-raise still diverges (33-pp on bottom-pair-Ace) — investigation in flight (`docs/v1_6_1_dryrun_verification.md`).

**Private mirror only (audit-cleared):** PR 29 spec corrections, PR 38 persona corrections (`71d161d` / `149ca11`), PR 41 Phase 2b AK revision (`dcc9d83`), PR 42 W3.5 reversal (`794df95` + fix-ups `a2b4ff1` / `90a3c27`).

---

## 10. What I'd ship next if I had 4 more hours

1. **v1.6.0 GUI** — in flight; will land soon. Closes Gate 2.
2. **v1.7.0** — CLI subcommands + aggregator→vector wiring. Both branches ready. Closes 1-2 more PARTIAL persona items.
3. **v1.6.1 engine bundle** — currently HELD pending root-cause investigation. Dry-run NO-GO (`docs/v1_6_1_dryrun_verification.md`): A83 max |diff| 0.33 on bottom-pair-Ace at `b1000r3000` even with PR 33+34+35-A+B+40 composed. The bisection's deep-cap algorithmic gap is empirically re-confirmed. PR 35 Fix C remains dropped (induces `test_exploit_diff` regression and is orthogonal).
4. **Retest cascade** — only shallow-cap retests can fire against v1.6.1 once bundle clears. Conservative target 10-12/18 PASS; optimistic 13/18 contingent on the deep-cap fix landing.
5. **Algorithmic-triage 2.0 on `dcfr_vector.rs` vs `trainer.cpp:138-240`** at the facing-raise path specifically — best-response cross-check (vanilla CFR vs DCFR on A83) + iteration sweep + line-by-line re-read of the bottom-pair-Ace cells' reach-propagation / regret-update. Gating Gate 1 closure. Using A83 3sAs/3cAc at `b1000r3000` as primary reproducer.

Beyond that horizon: 200K-iter production validation (Gate 4) and v-final .dmg (Gate 5).

---

*Document generated by orchestrator burst-close routine, 2026-05-23. All claims cross-reference commit SHAs or docs paths above; numbers reflect state at time of writing.*
