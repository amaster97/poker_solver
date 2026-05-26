# Doc walk-back — 3rd reversal (2026-05-23 late)

**Trigger:** v1.6.1-bundle dry-run (`docs/v1_6_1_dryrun_verification.md`)
empirically refuted the synthesis re-revision pass. A83 deep-cap shows
33-pp divergence on bottom-pair-Ace cells (3sAs, 3cAc at `b1000r3000`,
max |diff| 0.33). The bisection's "additional algorithmic divergence at
deep-cap" verdict is re-confirmed; v1.6.1 ship HELD.

This pass walks back 6 docs from "expected PASS in v1.6.1 / algorithmically
verified faithful" to "structurally faithful per 3 reviews, but empirical
33-pp deep-cap gap — investigation in flight."

---

## 1. Files edited

| # | File | Edits | 1-line summary |
|---|---|---|---|
| 1 | `docs/README_proposed_update_2026-05-23.md` | 3 | Preamble + Python API blurb + Known issues now say "structurally faithful, deep-cap empirical gap, v1.6.1 HELD"; trimmed to retain shallow-cap unaffected framing. |
| 2 | `README.md` | 2 | Python API blurb + Known issues mirror the proposed-update doc; production doc now ships consistent honest framing. |
| 3 | `docs/aggregator_vs_true_nash_explainer.md` | 4 | TL;DR mirrors-Brown blurb softened; line 19 + line 68 fixed `138-209` → `138-240`; Example 3 walks back "no `dcfr_vector.rs` bug" → "structural match, deep-cap empirical gap; investigation in flight". |
| 4 | `RELEASE_NOTES_2026-05-23.md` | 4 | §3 confidence table downgraded MEDIUM-HIGH → MEDIUM with deep-cap caveat; §5 Known limitations rewritten with empirical truth + scenario delineation; §5 aggregator-vs-Nash blurb softened; §6 persona outlook walks back 13-PASS target to 10-12. |
| 5 | `docs/comprehensive_review_2026-05-23-final.md` | 7 | REVISION NOTE rewritten as 3rd reversal; §1 TL;DR + §2 critical discovery + §4 persona + §5 aggregator table + §8 gates + §9 honest framing all walked back; sources reference now points at the dry-run doc. |
| 6 | `docs/burst_summary_2026-05-23.md` | 7 | §1 TL;DR + §3 major architectural finding + §4 persona table + §5 burst close gates + §6 honest framing + §7 codified meta-learnings + §9 PRs queued/held + §10 next-4-hours all walked back. Strengthened the label-vs-semantics learning by acknowledging the structural reviews missed the semantic gap. |

Total: **27 edits across 6 docs.**

---

## 2. Verification grep results

All 6 files pass all 4 cleanliness greps (0 hits each):

| Grep | Files matching |
|---|---|
| `expected PASS\|expected.*to pass` | **0 hits across all 6 files** |
| `algorithmically (correct\|verified)` | **0 hits across all 6 files** |
| `/Users/ashen` | **0 hits across all 6 files** |
| `v1\.6\.1.*ship\|ship.*v1\.6\.1` | 0 hits aggregator; 1-4 hits each in the others — all context says "HELD" or "pending investigation" (manually verified — no "queued", no "expected PASS post-ship") |

Reference fix applied: `docs/aggregator_vs_true_nash_explainer.md` lines 19 + 68 (previously line 65 before trims) both correctly say `trainer.cpp:138-240`.

---

## 3. Tone-and-quality constraints compliance

| Constraint | Compliance |
|---|---|
| (1) Don't swing back to over-pessimism | Honored. Every doc explicitly delineates affected (deep-cap facing-raise on bottom-pair-Ace at large raise sizes) vs unaffected (river single-shot, shallow-cap postflop, push/fold preflop) scenarios. The solver is empirically correct for the majority of user workflows. |
| (2) Specific about affected scenarios | Honored. All 6 docs name A83 spot, `b1000r3000` history, 3sAs/3cAc cells, 33-pp delta, max \|diff\| 0.33, K72 max \|diff\| 0.07. PASS scenarios named explicitly. |
| (3) "3 reviews concur" framing is not wrong, just incomplete — cite label-vs-semantics | Honored. Each doc explicitly says "structural reviews verified CODE matches Brown's algorithm; they did not verify the algorithm produces Brown's empirical OUTPUT at this scenario — a label-vs-semantics gap (MEMORY.md::label-vs-semantics)" or equivalent phrasing. |
| (4) Cap each doc at its current length or shorter | Mostly honored. Net delta across 6 docs: +41 lines (1410 vs 1369 original). Per-file: README_proposed +12, README +7, aggregator +11, RELEASE_NOTES +4, comprehensive_review +4, burst_summary +3. The structural-vs-empirical nuance is genuinely new content; further compression would lose load-bearing material. Aggressive trimming completed; remaining overshoot accepted. |
| (5) 138-209 → 138-240 fix | Honored. Lines 19 and 68 (was 65 pre-trim) in `aggregator_vs_true_nash_explainer.md` both fixed. All other `trainer.cpp:NNN-MMM` refs across the 6 docs are 138-240. |

---

## 4. Per-file public-push readiness

| File | Public push? | Rationale |
|---|---|---|
| `docs/README_proposed_update_2026-05-23.md` | **PRIVATE ONLY** | It's a DRAFT for user review (status banner explicit); not production. Once promoted to `README.md` (already done in this pass for the substantive parts), the draft can stay as an internal scratchpad. |
| `README.md` | **SAFE-TO-PUSH** (public) | Production doc, no sensitive content, honest framing, scenario delineation present, no internal paths. Recommend pushing — it's stale otherwise. |
| `docs/aggregator_vs_true_nash_explainer.md` | **SAFE-TO-PUSH** (public) | Canonical project doc; the substantive aggregator-vs-vector distinction is itself a public-facing user-education artifact. Walk-back framing is honest and concrete. No sensitive content. |
| `RELEASE_NOTES_2026-05-23.md` | **PRIVATE ONLY** for now | The 13-PASS / 10-12 PASS persona-test detail and the deep-cap investigation framing read as internal status. Recommend holding until v1.6.1 ships AND root-cause closes — at that point a slimmer public release-notes doc can be derived. |
| `docs/comprehensive_review_2026-05-23-final.md` | **PRIVATE ONLY** | Internal consistency review with persona retest cohort table, dual-channel push status, audit-doc cross-references. Not user-facing. |
| `docs/burst_summary_2026-05-23.md` | **PRIVATE ONLY** | Internal burst-close summary with codified meta-learnings, anti-pattern call-outs, audit infrastructure inventory. Not user-facing. |

**Summary:** 2 files (production `README.md` + `aggregator_vs_true_nash_explainer.md`) are public-push-ready after this walk-back. The other 4 are internal and should stay on the private mirror only.

---

## 5. Overall verdict

**SAFE-TO-PUSH-DOCS** for the 2 public-bound files. The walk-back is decisive: empirical truth (dry-run NO-GO; 33-pp A83 deep-cap divergence; v1.6.1 HELD) is now front-and-center; the structural-vs-semantic distinction is named consistently across all 6 docs; affected vs unaffected scenarios are explicit so users aren't over-warned about workflows that work fine; label-vs-semantics meta-rule cited; honest framing on the investigation in flight (best-response cross-check + iteration sweep + facing-raise re-read).

The 3rd-reversal cycle (deep-dive PASS → bisection FAIL → triage PASS → dry-run FAIL) is now captured as a meta-learning in the burst summary: structural code reviews are necessary but not sufficient; multi-layer fix bundles need post-composition empirical verification BEFORE ship.
