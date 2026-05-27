# PR 41 Verification Audit — Phase 2b Audit AK Revision

- **Date:** 2026-05-23
- **PR:** PR 41 (`pr-41-phase2b-audit-revision` @ `dcc9d83`)
- **Worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/phase2b-audit-revision`
- **File audited:** `docs/pr13_prep/v1_3_2_phase2b_audit.md` (+33 / -1 vs PR 38's `71d161d`)
- **Source evidence:** `docs/persona_test_results/W2b_1_per_hand_breakdown.md`
- **Auditor stance:** READ-ONLY (no source modified; only this audit doc written)

## Verdict: **APPROVE**

The revision is faithful to the W2b.1 per-hand breakdown empirical evidence. One minor inconsistency (prose lag in the "sane strategies" paragraph) is flagged below but does NOT block approval — it is mitigated by the inline follow-up annotation that immediately follows and the top-of-doc revision banner.

---

## 1. Empirical claim verification — **MATCH**

PR 41's revised AK line (line 354 of revised audit):

> `AK: fold=0.77 (NOT pure drawing-dead as initial 50-iter measurement suggested; AK has ~39% equity vs villain range — it can chop vs villain AK and bluff-catch some of villain's bluff range. At 500 iters AK defends 22.7% — small but non-trivial mixed defense leg).`

Cross-checked against W2b.1 per-hand breakdown line 100:

| Field | PR 41 claim | W2b.1 evidence | Match? |
|---|---|---|---|
| fold | 0.77 | 0.7730 | YES (rounded to 2 sf) |
| equity vs villain range | ~39% | 0.389 | YES |
| defense (1 − fold) | 22.7% | 0.2270 | YES |
| call (implied via defense) | n/a (only "defends" cited) | 0.1020 | not explicitly stated; consistent |
| raise_33 (implied) | n/a (only "defends" cited) | 0.0448 | not explicitly stated; consistent |
| raise_75 (implied) | n/a (only "defends" cited) | 0.0802 | not explicitly stated; consistent |
| 22.7% = call + raise_33 + raise_75 | yes (1 − 0.773 = 0.227) | 0.1020 + 0.0448 + 0.0802 = 0.2270 | YES |

Top-of-doc revision banner (lines 9-20) and inline follow-up annotation (lines 369-386) also assert:

- **`AK fold=0.773, defend=0.227 mixed`** — matches W2b.1 row exactly.
- **Aggregate MDF 59.8% (50 iter) → 64.5% (500 iter)** — matches W2b.1 headline table (lines 76-79).
- **Both in Janda-ballpark band** — matches W2b.1 §"Headline measurements" assessment.

All four empirical claims (AK fold, AK defend, AK equity, aggregate MDF shift) match the per-hand breakdown verbatim.

## 2. Removed "drawing dead" framing — **CORRECTED**

`grep -i "drawing dead\|drawing-dead"` against the revised audit returns only 2 hits, both in the **corrected** framing:

- Line 13 (top-of-doc revision banner): `**AK is NOT pure drawing-dead at convergence.**`
- Line 354 (per-class strategies block): `fold=0.77 (NOT pure drawing-dead as initial 50-iter measurement suggested ...)`

The original `AK: fold=0.9999 (drawing dead vs SB's QQ/JJ value range)` line at the same location has been replaced (confirmed via `git diff 71d161d dcc9d83`). No residual "drawing dead" assertion remains in the doc — both surviving mentions explicitly negate the prior framing.

## 3. Top-of-doc revision banner — **HONEST FRAMING**

The banner at lines 9-20:

- **Cites the per-hand breakdown agent's finding:** Yes — explicitly names `docs/persona_test_results/W2b_1_per_hand_breakdown.md` and the agent's re-run config (500 iter / villain_reps=2 vs the audit's 50 iter / reps=1).
- **Acknowledges audit's earlier conclusion was wrong:** Yes — `The 50-iter "AK fold=0.9999" figure in §"Per-class strategies" below is an under-converged artifact`.
- **States the corrected conclusion:** Yes — `the trustworthy 500-iter figure is AK fold=0.773, defend=0.227 mixed`.
- **Preserves the W2b.1 PASS verdict honestly:** Yes — `both still sit in the Janda-ballpark band, so the §"Audit Target #3" verdict (CONFIRMED-RESOLVED) is unchanged`.
- **Tone:** Honest. The banner directly admits the audit's per-class characterization was under-converged; it does not hide behind "supplements" or "additional context" language.

## 4. Cross-references — **PRESERVED**

- **Phase 2b W2b.1 verdict "CONFIRMED-RESOLVED on v1.4.1"** — preserved at TL;DR (line 28) and §"Audit Target #3" verdict (line 393).
- **Audit's overall W2b.1 PASS verdict** — preserved.
- **Per-hand data is now correctly characterized** — yes, via the inline follow-up annotation (lines 369-386) that explicitly:
  - Points to the per-hand breakdown report.
  - Explains the bimodal-range structural issue (`call=0.038` is structural, not a solver defect).
  - States the 500-iter aggregate is 64.5% defense.
  - States the per-class table at 500 iter has `AK defend=0.227` (mixed) rather than `AK fold=0.9999`.

## 5. Inconsistencies to call out

### Minor (does not block approval): prose lag on "air (AK, A4o) folds ~100%"

**Location:** Line 364, in the §"Per-class strategies" sanity paragraph:

> `The strategies are sane: top-tier value hands (QQ, KQ, AQ) defend ~100%; medium pairs (KK / JJ) defend ~75% (a quarter fold mass comes from spots where villain's specific combo dominates); air (AK, A4o) folds ~100%; semibluff (T9s) defends ~50%.`

This still classifies **AK as air folding ~100%**, which contradicts the revised AK line directly above it (where AK is now characterized as a mixed bluff-catcher with 22.7% defense). The contradiction is mitigated by:

1. The inline follow-up annotation (lines 369-386) immediately below, which explicitly updates this.
2. The top-of-doc revision banner (lines 9-20), which forewarns readers.
3. The TL;DR row at line 28 also still says "air folds 100%" — this is a similar prose lag.

**Why this is acceptable:** The revision strategy PR 41 chose was annotation-style (add banners + inline notes) rather than text-replacement-style (rewrite the older prose to match). This is honest in that it preserves the audit's historical narrative while flagging where it was wrong. Per the orchestrator's revision-history rule, this is the correct pattern for a doc that records an audit-time view + a later correction.

**Recommended (NOT required for approval):** A future micro-revision could add a parenthetical `(see follow-up annotation re: AK)` to line 364 and the TL;DR row for W2b.1. But this is a polish item, not an audit blocker.

### No other inconsistencies found

- No contradictory numbers anywhere else in the doc.
- No new unsupported claims introduced.
- Source attributions are accurate (W2b.1 per-hand breakdown path is correct).
- Verdicts for the other 2 targets (W2b.5, W2b.2) are untouched.

## Summary table

| Audit task | Result |
|---|---|
| 1. Empirical numbers (AK fold, defend, equity; aggregate MDF) | **MATCH** |
| 2. "Drawing dead" framing | **CORRECTED** (only negating mentions remain) |
| 3. Revision banner: cites source / honest framing | **PASS** |
| 4. Cross-refs preserved (W2b.1 PASS, verdict CONFIRMED-RESOLVED) | **PASS** |
| 5. Inconsistencies | 1 minor prose lag (mitigated by annotations); no blocking issue |

## Final verdict: **APPROVE**

PR 41 is a faithful, honest annotation of the v1.3.2 Phase 2b audit. All empirical claims trace cleanly to the W2b.1 per-hand breakdown. The "drawing dead" framing is removed from the AK characterization. The revision banner acknowledges the audit's prior error honestly while preserving the unchanged overall verdict.

The one minor prose lag (line 364 still saying "air (AK, A4o) folds ~100%") is annotation-style legacy text and is mitigated by the surrounding revision banner + follow-up annotation. It does not warrant blocking the PR.
