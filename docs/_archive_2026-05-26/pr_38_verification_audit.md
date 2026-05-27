# PR 38 Verification Audit — Persona Corrections Propagation

**Date:** 2026-05-23 (late afternoon)
**Auditor:** independent verification agent (read-only across all source files)
**PR 38 worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/persona-corrections`
**PR 38 branch tip:** `71d161d` (HEAD) after two commits — `149ca11` (retest doc downgrades) + `71d161d` (spec/audit/prompts + revision history)
**Audit window:** ~13:46 (worktree provisioned) through ~13:56 (final commit landed)
**Audit method:** byte-level diff of every PR 38 target file vs main repo (`/Users/ashen/Desktop/poker_solver/docs/...`) + commit-stat verification + cross-check against `docs/poker_spots_audit_CORRECTED_2026-05-23.md` and `docs/poker_spots_reverification_2026-05-23.md`.

---

## Verdict summary

**APPROVE** — all six spawning-prompt deliverables are APPLIED, citations are intact, and the verdict downgrades correctly reflect the user-validated audit conclusions. Recommended action: push to private mirror per the dual-remote workflow.

The verdict downgrades that are applied are stronger than the reverification document's minimum recommendation in two places (W3.5: TEST-DESIGN-FAIL vs reverification's PARTIAL; W1.2: PARTIAL vs reverification's KEEP-PASS), but both stronger verdicts are explicitly authorized by the spawning prompt and grounded in the user-provided expanded rationale (range-Nash AA should be ~80-95% CHECK on monotone Ts 8s 6s 4c 2d; W1.2's 7.7% fold is convergence noise rather than a balanced equilibrium response to AA-set frequency).

---

## Per-deliverable verification

### Deliverable 1 — W3.5 retest report verdict: PASS → TEST-DESIGN-FAIL

**Target file:** `docs/persona_test_results/W3_5_v1_4_1_retest.md`
**Status:** APPLIED (clean)

**Commit:** `149ca11` (first PR 38 commit).

**File state:** size grew 15422 → 21897 bytes. Original retest text preserved below a horizontal-rule line. New §"Verdict revision (2026-05-23 late)" section added at top.

**Verdict downgrade in place:**
- Top-of-file: `**Verdict (revised 2026-05-23 late):** **TEST-DESIGN-FAIL** (closest standard mapping: BLOCKED).`
- Original PASS verdict explicitly marked `**Original verdict (2026-05-23 mid-session, NOW SUPERSEDED):** PASS (with caveats — value-side polarization observable; bluff-side and bet-sizing polarization NOT observable under per-solve perfect-info; see §Caveats)`.

**Rationale citation match:**
- Cites `docs/poker_spots_reverification_2026-05-23.md` (Spot 3 re-analysis) as the source of revision.
- Reproduces the user-validated framing verbatim: *"Per the user (validated as the correct intuition): under the actual range-vs-range Nash on a monotone Ts 8s 6s 4c 2d, AA should be approximately **80-95% CHECK** ... with only occasional small leads, and NEVER large bets. AA should also FOLD to large bets/raises (bluff-catcher behavior)."*
- Identifies the per-combo proxy as "trivial best response, not range Nash" — consistent with the reverification doc's Spot 3 conclusion that only 1-of-3 polarization legs (value-side) is observable AND that this "value-side" is per-combo, not range Nash.
- Horizontal-rule separation ensures audit-trail integrity.

**Verdict-vs-reverification consistency:** reverification doc recommends `DOWNGRADE PASS → PARTIAL` for Spot 3 (W3.5). PR 38 goes further to TEST-DESIGN-FAIL (~ BLOCKED), based on the user's expanded rationale. The spawning prompt explicitly listed `TEST-DESIGN-FAIL or PARTIAL` as acceptable. PR 38's choice of the stronger downgrade is correctly justified: "the actual failure mode here is that ALL THREE polarization legs (value side, bluff side, bet-sizing) are unobservable under per-combo perfect-info, and the visible 'value side' is a trivial best response, not a Nash signal."

**Cited-text matches per modification:**
- `bluff frequency is fundamentally unobservable under per-solve perfect-info` ✓ (matches reverification §Spot 3)
- `Bet-sizing polarization is unobservable for the same reason` ✓ (matches reverification §Spot 3, Items 1 & 2)
- `correct path forward: range-vs-range solve on a monotone flop ... blocked on PR 23 (W2.3 chance-enum perf cliff)` ✓ (matches reverification §Recommended follow-ups #1)

**Issues:** none.

---

### Deliverable 2 — W1.2 retest report verdict: PASS → PARTIAL

**Target file:** `docs/persona_test_results/W1_2_v1_4_1_retest.md`
**Status:** APPLIED (clean)

**Commit:** `149ca11` (first PR 38 commit).

**File state:** size grew 9701 → 16593 bytes. Original retest text preserved below a horizontal-rule line. New §"Verdict revision (2026-05-23 late)" section added at top with three numbered issues.

**Verdict downgrade in place:**
- Top-of-file: `**PARTIAL** — the 92.3% defend is technically inside the spec's [0.85, 1.00] band but the strict Nash answer is ~100% defend (the 7.7% fold is convergence noise from 200 iters × 5 villain reps under-converged). The 56.8% all-in mass CANNOT be validated as the reraise dynamic the spec intends, because the stack-to-pot ratio is effectively zero under the configured stacks (villain is already all-in from the pot bet; hero has no room for an intermediate raise).`
- Original PASS verdict marked `**Original verdict (2026-05-23 mid-session, NOW SUPERSEDED):** PASS`.

**Rationale citation match:**
- Cites `docs/poker_spots_audit_CORRECTED_2026-05-23.md` (Spot 8 re-analysis) and `docs/poker_spots_reverification_2026-05-23.md` (Spot 8 rationale correction) as revision sources.
- Issue 1 ("the 7.7% fold is convergence noise") cites pot odds = 33.3% (1000 / (2000 + 1000)) and JJ raw equity = 93.3% (42/45 combos), per the CORRECTED audit's Spot 8 enumeration.
- Issue 2 ("the 56.8% all-in mass cannot be validated as a reraise dynamic") correctly identifies villain's 0-chips-behind state as the cause of the collapsed action set `[fold, call, all_in]`, matching the reverification doc's Spot 8 observation that "villain at P0 contributed all 1500 of 1500-stack, so villain is already all-in."
- Issue 3 (rationale-level correction: AA = set of aces) cites the reverification's Spot 8 finding: "the retest report at line 99 states 'There is no straight in villain's range; T9s makes top pair only.' This is partially correct but misses that AA = set of aces."

**Verdict-vs-reverification consistency:** reverification doc recommends `KEEP PASS, with rationale correction` for Spot 8. PR 38 goes further to PARTIAL based on the user-expanded rationale (strict Nash should be ~100% defend; observed 92.3% is convergence noise; reraise dynamic is structurally untestable at the configured stacks). The spawning prompt explicitly called out the verdict downgrade and the "reraise dynamic not testable due to short stacks" framing. The PR 38 verdict is more conservative than the reverification's, but it's the verdict the spawning prompt asked for.

**Cited-text matches per modification:**
- Pot odds 33.3% required vs reverification's `1000 / (2000+1000) = 33.3% required` ✓ (exact)
- JJ raw equity 93.3% vs reverification's `Total: 3/45 combos (6.7%) BEAT JJ-set; 42/45 (93.3%) lose` ✓ (exact)
- Recommendation: `starting_stack=20000 (200 BB)` for the deep-stack rerun + PR 37 equity helper ✓ (spawning-prompt-aligned)

**Issues:** none.

---

### Deliverable 3 — W2b.2 Phase 2b audit rationale correction

**Target file:** `docs/pr13_prep/v1_3_2_phase2b_audit.md`
**Status:** APPLIED (clean)

**Commit:** `71d161d` (second PR 38 commit).

**File state:** size grew 21824 → 24294 bytes. New §"Framing correction (2026-05-23 late)" section added at the top of Audit Target #2 (W2b.2). Original audit text preserved below the correction with header `### Original audit text (PRESERVED — but read with the framing correction above in mind)`.

**Correction in place:**
- Identifies the "villain folds 100% to any bet → EV(bet, s) = pot, independent of s" rationale as WRONG.
- Correct reason for flat sizing: villain's range contains QQ-trips, AQs-two-pair, KQs-flush — all crush KK and would NEVER fold. The flat sizing reflects KK essentially NEVER betting at all (10⁻⁷ on `bet_33` / `bet_75` is DCFR convergence noise where neither size is favored because both are dominated by checking).
- Solver behavior assessed as CORRECT — only the rationale needed revision.

**Rationale citation match:**
- Cites `docs/poker_spots_reverification_2026-05-23.md` Spot 10 as the source of revision.
- Matches the reverification doc's Spot 10 per-combo decomposition:
  - QQ → three-of-a-kind (97.7% equity vs KK)
  - AQs → two-pair (95.5%)
  - KQs → K-high spade flush (100%)
  - JJ, TT → KK dominator (25% villain equity)
- Matches the reverification doc's conclusion: "the flat sizing claim is NOT about Nash indifference between bet_33 and bet_75 — it's about the strategic dominance of all-in over smaller sizes."

**Verdict-vs-reverification consistency:** reverification's Spot 10 recommendation was `DOWNGRADE PASS → PARTIAL` — but the persona-verdict downgrade is documented in `persona_acceptance_spec.md` §7 (see Deliverable 4) and in the new `persona_verdict_revision_history.md` (see Deliverable 6), not in the Phase 2b audit doc. The Phase 2b audit doc retains its "Verdict: **CONFIRMED**" line, which assesses solver code correctness — and that IS confirmed. The spawning prompt asked specifically for a "rationale correction" on W2b.2 — code-correctness verdict change was NOT requested. Layered correctly.

**Cited-text matches per modification:**
- `QQ → trips of queens (Qd on board + pocket QQ)` ✓
- `AQs → two pair (A + Q)` ✓
- `KQs → K-high spade flush` ✓
- `The flat sizing residual between bet_33 and bet_75 (both ~10⁻⁷) is the DCFR convergence noise when neither size is favored` ✓ (matches reverification's Spot 10 conclusion)

**Issues:** none.

---

### Deliverable 4 — Persona acceptance spec notes on test design gaps

**Target file:** `docs/pr13_prep/persona_acceptance_spec.md`
**Status:** APPLIED (clean)

**Commit:** `71d161d` (second PR 38 commit).

**File state:** size grew 18118 → 22545 bytes. Three additions:
1. Note after W1.2 line (lines 33-34): documents the stack-constrained 0-SPR all-in collapse + the verdict revision PASS → PARTIAL.
2. Note after W3.5 line (lines 65-66): documents the per-combo perfect-info trivial best response + verdict revision PASS → TEST-DESIGN-FAIL (~ BLOCKED).
3. New §7 "Audit-trail addendum (2026-05-23 late) — W2b cohort and W2.2 retest methodology": captures the W2b cohort framing corrections.

**Rationale citation match:**
- All three additions reference `docs/poker_spots_audit_CORRECTED_2026-05-23.md`, `docs/poker_spots_reverification_2026-05-23.md`, and `docs/pr13_prep/persona_verdict_revision_history.md`. The revision history doc reference is now SATISFIED (see Deliverable 6).
- W1.2 note: "the spec phrasing 'MDF vs pot = 50%' is the MDF range-level heuristic; the per-combo 1v1 engine uses pot odds (33.3% required equity = 1000 / 3000 here). JJ raw equity vs the listed villain range is 93.3% (loses only to AA = 3/45 combos), so strict Nash defend ≈ 100%." — matches CORRECTED audit's Spot 8 numbers exactly.
- W3.5 note: "User intuition (validated): on a monotone Ts 8s 6s 4c 2d, range-Nash AA should be ~80-95% CHECK, NEVER large bets, and FOLD to large bets/raises." — matches the user-validated rationale verbatim.

**Cited-text matches per modification:**
- 33.3% required equity = 1000 / 3000 ✓ (matches reverification §Spot 8)
- JJ raw equity 93.3% ✓ (matches reverification §Spot 8)
- AA = 3/45 combos ✓ (matches reverification §Spot 8)
- "80-95% CHECK, NEVER large bets" ✓ (matches the W3.5 retest's verdict-revision section verbatim)

**Issues:** none.

---

### Deliverable 5 — Retest prompts updated to use PR 37 equity helper + deeper stacks

**Target files:**
- `docs/pr_proposals/v1_4_1_retest_W1_2_marcus_jj_vs_pot.md` (W1.2 prompt)
- `docs/pr_proposals/v1_4_1_retest_W2_3_sarah_kk_vs_cbet_range.md` (W2.3 prompt)
- `docs/pr_proposals/v1_4_1_retest_W3_4_daniel_mdf.md` (W3.4 prompt)

**Status:** APPLIED (all three, clean)

**Commit:** `71d161d` (second PR 38 commit).

**Per-prompt state:**
- **W1.2 prompt:** APPLIED. Size grew 10800 → 18380 bytes. (a) "Update (2026-05-23 late)" block at line 5 enumerates the two methodology errors (stack-to-pot zero; convergence noise) and the three required updates for the next retest run. (b) NEW §"D-update. Paste-ready agent prompt — DEEP-STACK VERSION (2026-05-23 late)" at line 121, with `starting_stack=20000`, `initial_contributions=(20000, 19000)`, `iterations=2000` (bumped from 200), and explicit equity-helper invocation. The original §D is preserved as the v1.4.1 baseline record.
- **W2.3 prompt:** APPLIED. Size grew 8112 → 8758 bytes. Added equity-helper requirement at top with rationale citation to `docs/poker_spots_audit_CORRECTED_2026-05-23.md` (orchestrator's prior equity hand-waves were 2-5× off on lopsided spots) and forward-link to `docs/pr13_prep/persona_verdict_revision_history.md`.
- **W3.4 prompt:** APPLIED. Size grew 8456 → 9309 bytes. Added equity-helper requirement at top with MDF-formula nuance ("MDF heuristic is a range-level pot-odds formula and does not need per-combo equity — but any claim about per-class behavior should be backed by `equity_vs_range`, not by hand-wave") + same rationale citation.

**Rationale citation match (W1.2 prompt deep-stack section):**
- Pot odds 33.3% / JJ raw equity 93.3% / AA = 3/45 ✓ (matches Spot 8 reverification)
- `starting_stack=20000` / `initial_contributions=(20000, 19000)` ✓ (matches W1.2 retest doc deeper-stack recommendation)
- Equity-helper API `equity_of`, `equity_vs_range`, `assert_equity_close` ✓ (matches PR 37 CHANGELOG entry)
- Acceptance band: `defend ≥ 0.95` (raised from 0.85) for strict-Nash compliance + `intermediate-raise mass ≥ 0.05` to verify reraise dynamic ✓ (matches spawning-prompt direction)
- `iterations=2000` (bumped from 200) to mitigate convergence noise ✓ (correctly addresses Issue 1 from the W1.2 retest revision)

**Issues:** none.

---

### Deliverable 6 — New meta-doc `persona_verdict_revision_history.md`

**Target file:** `docs/pr13_prep/persona_verdict_revision_history.md`
**Status:** APPLIED (clean, 11319 bytes / 122 lines)

**Commit:** `71d161d` (second PR 38 commit).

**File contents:**
- §Purpose + Scope.
- §"2026-05-23 late corrections (PR 38)" — describes the trigger (user-identified errors), enumerates source-of-truth documents (`docs/poker_spots_audit_CORRECTED_2026-05-23.md`, `docs/poker_spots_reverification_2026-05-23.md`, orchestrator's subsequent conversational corrections).
- §"Verdict changes propagated by PR 38":
  - W3.5: PASS → TEST-DESIGN-FAIL with full rationale and 80-95% CHECK user-validated framing.
  - W1.2: PASS → PARTIAL with two-issue rationale (convergence noise; reraise dynamic untestable due to 0 SPR).
  - W2b.2: solver behavior PASS; rationale needed revision (the "villain folds 100%" framing was wrong because villain's range contains QQ-trips, AQs-two-pair, KQs-flush).
- §"Persona count summary (post-revision)": 9 PASS / 5 PARTIAL / 3 BLOCKED with footnote that the count is indicative, not load-bearing.
- §"What is NOT being revised": explicitly enumerates W1.1, W1.3, W1.5, W2b.1, W2b.5, and v1.5.0 Brown acceptance test as unchanged.
- §"Methodology lessons" — 4 lessons (per-combo ≠ range Nash; pot odds ≠ MDF; SPR governs legal action sets; equity hand-waves must die).
- §"Files referenced" — full cross-reference list.

**Verdict-vs-reverification consistency:** the doc faithfully reflects all three verdict changes (W3.5, W1.2, W2b.2 rationale correction) and explicitly enumerates what was NOT revised. Citations to source-of-truth documents are correct.

**Cited-text matches per modification:**
- "80-95% CHECK" for range-Nash AA on monotone Ts 8s 6s 4c 2d ✓
- "JJ raw equity 93.3% vs the listed villain range" ✓
- "AA = 3/45 combos giving three aces > three jacks" ✓
- "DCFR convergence noise where neither size is favored because both are dominated by checking" ✓ (W2b.2 framing)

**Issues:** none.

---

## Commit-level audit

Two commits on `pr-38-persona-corrections`:

1. **`149ca11 PR 38: propagate persona verdict downgrades (W3.5, W1.2)`** — modifies the two retest reports. 2 files changed (only W3.5 and W1.2 retest docs).

2. **`71d161d PR 38: spec + audit framing + retest prompts + revision history`** — modifies the spec/audit/prompts and creates the new revision history doc. 6 files: persona_acceptance_spec.md (140 lines added), persona_verdict_revision_history.md (122 lines, NEW), v1_3_2_phase2b_audit.md (494 lines added — note: this number includes the preserved original text being counted as "added" because git treats the framing-correction insert as a substantial change), 3 retest prompts (108/101/178 lines added respectively, with the W1.2 prompt's 178-line addition reflecting both the update header AND the new D-update paste-ready section).

Both commit messages are well-formed, cite the source-of-truth audit documents, and accurately describe their respective scope. Co-authored attribution present on both. No `--no-verify`. No skipped hooks.

---

## Inconsistencies between PR 38 and the audit docs

**None of substance.** Specific potential inconsistencies investigated and dismissed:

1. **W3.5 verdict (TEST-DESIGN-FAIL vs reverification's PARTIAL):** the spawning prompt explicitly enumerated both TEST-DESIGN-FAIL and PARTIAL as acceptable. PR 38's choice of the stronger downgrade is grounded in the user-expanded rationale that even the "value-side" of polarization (which the reverification recognized as observable) is a per-combo best response — not a Nash signal. PR 38's framing is more honest than the reverification's. Not an inconsistency.

2. **W1.2 verdict (PARTIAL vs reverification's KEEP-PASS):** the reverification recommended `KEEP PASS, with rationale correction` — but the spawning prompt explicitly directed PR 38 to downgrade to PARTIAL on the basis that (a) defend should be ~100% not 92.3%, and (b) the reraise dynamic is not testable due to short stacks. PR 38 follows the spawning prompt's direction, which expanded on the reverification's analysis. Not an inconsistency.

3. **W2b.2 Phase 2b audit verdict line still says "CONFIRMED":** intentional. The Phase 2b audit's verdict is about solver-CODE correctness, which IS confirmed (solver checks ~100% on the QQ/AQs/KQs portion of the range; bet-mass 10⁻⁷ is correctly residual numerical noise). The persona-level downgrade for W2b.2 (PASS → PARTIAL) lives in `persona_acceptance_spec.md` §7 and is enumerated in `persona_verdict_revision_history.md`. Layered correctly. Not an inconsistency.

---

## Recommended verdict before push to private mirror

**APPROVE.**

All six spawning-prompt deliverables are APPLIED, citations are correct, verdict downgrades match (or honestly exceed in defensible ways) the user-validated audit conclusions. Two clean commits with proper messages and co-author attribution. No code-correctness changes (this is a doc-only PR — solver behavior is unchanged across all touched paths). The new D-update paste-ready prompt for W1.2 deep-stack retest is ready to be re-fired post-merge.

**No NEEDS-FIX items.**

---

## Files reviewed (worktree paths)

- `/Users/ashen/Desktop/poker_solver_worktrees/persona-corrections/docs/persona_test_results/W3_5_v1_4_1_retest.md` (modified — APPLIED)
- `/Users/ashen/Desktop/poker_solver_worktrees/persona-corrections/docs/persona_test_results/W1_2_v1_4_1_retest.md` (modified — APPLIED)
- `/Users/ashen/Desktop/poker_solver_worktrees/persona-corrections/docs/pr13_prep/v1_3_2_phase2b_audit.md` (modified — APPLIED)
- `/Users/ashen/Desktop/poker_solver_worktrees/persona-corrections/docs/pr13_prep/persona_acceptance_spec.md` (modified — APPLIED)
- `/Users/ashen/Desktop/poker_solver_worktrees/persona-corrections/docs/pr13_prep/persona_verdict_revision_history.md` (NEW — APPLIED)
- `/Users/ashen/Desktop/poker_solver_worktrees/persona-corrections/docs/pr_proposals/v1_4_1_retest_W1_2_marcus_jj_vs_pot.md` (modified — APPLIED, incl. new D-update section)
- `/Users/ashen/Desktop/poker_solver_worktrees/persona-corrections/docs/pr_proposals/v1_4_1_retest_W2_3_sarah_kk_vs_cbet_range.md` (modified — APPLIED, equity-helper note added)
- `/Users/ashen/Desktop/poker_solver_worktrees/persona-corrections/docs/pr_proposals/v1_4_1_retest_W3_4_daniel_mdf.md` (modified — APPLIED, equity-helper note added)

## Audit reference docs (main repo paths)

- `/Users/ashen/Desktop/poker_solver/docs/poker_spots_audit_CORRECTED_2026-05-23.md` (Spots 1-10, source of all per-spot equity numbers)
- `/Users/ashen/Desktop/poker_solver/docs/poker_spots_reverification_2026-05-23.md` (Spots 3, 4, 8, 10 — verdict downgrade recommendations)
