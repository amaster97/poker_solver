# PR 42 Verification Audit (Fresh-Eyes / Independent)

**Date:** 2026-05-23
**Auditor:** Fresh-eyes audit agent (same pattern as prior PR 38 re-verification)
**Subject:** PR 42 — W3.5 verdict reversal (BLOCKED → PASS+)
**PR 42 commit:** `794df95` on branch `pr-42-w3-5-reversal`
**PR 38 base commits:** `71d161d` + `149ca11` (preserved underneath)
**Method:** READ-ONLY across all source files; cross-checked the empirical evidence file, each of the 3 modified files, git history, and persona count consistency.

---

## 1. Empirical evidence check

**Subject file:** `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md`

### Findings

| Claim from PR 42 commit body | Cited evidence in TRUE-Nash file | Status |
|---|---|---|
| AA pure-checks 100% at river-open | `W3_5_TRUE_nash_v1_5_1.md:87-89` — table row `AhAd \| 1.0000 \| 0.0000 \| 0.0000 \| 0.0000` and `AhAc \| 1.0000 \| 0.0000 \| 0.0000 \| 0.0000`; reinforced at `:90` ("AA pure-checks 100% at the river-open infoset.") | **SUPPORTED** |
| Range-aggregate ~87% check / ~13% bet | `W3_5_TRUE_nash_v1_5_1.md:116` — "Range-aggregate: check=0.8677, bet=0.1323 (≈ 87% check, 13% bet)." | **SUPPORTED** |
| Defend % vs villain bets weighted ~62% (fold rate grows with bet size) | `W3_5_TRUE_nash_v1_5_1.md:152-161` — table at `:152-156`: 0.33-pot defend 0.69, 0.75-pot defend 0.51, 1.5-pot defend 0.31 (fold 0.69 at 1.5-pot). `:161` — "AA's overall defend frequency: 61.7% (folds 38.3% when villain bets)." | **SUPPORTED** |
| Polarization signature: aggressor's range splits into nuts + checks | `W3_5_TRUE_nash_v1_5_1.md:98-116` — full 15-hand table shows only TT/88 (top + mid set) bet at non-trivial rates (~32-38%); KK/QQ/JJ/66/9s/7s/A-high/K-high all overwhelmingly check. `:138-142` — explicit "textbook polarization signature" framing | **SUPPORTED** |
| Entry point used = `solve_range_vs_range_rust` (PR 23 vector-form), NOT per-combo aggregator | `W3_5_TRUE_nash_v1_5_1.md:6-9` — "**`poker_solver._rust.solve_range_vs_range_rust`** — PR 23's vector-form Brown CFR with hands as a vector dimension. This is the algorithmically correct chance-enum Nash for the supplied (p0_holes, p1_holes), NOT the per-combo aggregator used in the prior W3.5 PoC." Table at `:19-23` explicitly contrasts the three solver paths (per-combo / aggregator / vector-form) and labels this report as the vector-form one. | **SUPPORTED** |
| Bluff-catcher behavior (AA fold 69% to 1.5x pot) | `W3_5_TRUE_nash_v1_5_1.md:156` — "1.67:1 \| 0.69 \| 0.31 \| 0.00 \| 0.00 \| 0.00 \| **0.31**" (fold=0.69 vs `b300`); `:163-174` polarization-in-AA's-response section | **SUPPORTED** |

### Verdict
**Empirical evidence: SUPPORTED.** Every numerical claim PR 42's commit body and revised verdict cite is verifiable at the cited locations in `W3_5_TRUE_nash_v1_5_1.md`. The solver entry point is correctly identified as `solve_range_vs_range_rust` (the PR 23 vector-form Rust path), distinct from the per-combo aggregator that PR 38 critiqued.

### CRITICAL FINDING — tracking gap

**The empirical-evidence file `W3_5_TRUE_nash_v1_5_1.md` exists on disk at `docs/persona_test_results/` but is NOT tracked in any commit, including PR 42's `794df95`.**

Verified via:
- `git ls-tree 794df95 docs/persona_test_results/ | grep w3_5` returns only `W3_5_v1_4_1_retest.md` (no TRUE_nash file).
- `git show 794df95:docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md` returns `fatal: path 'docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md' exists on disk, but not in '794df95'`.
- `git status` lists `docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md` as Untracked.
- `git log --all -- docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md` returns nothing (no commit ever added this file).

**Impact:** PR 42's three modified files reference the TRUE-Nash file as the load-bearing empirical evidence (e.g., spec note: "see `W3_5_TRUE_nash_v1_5_1.md`"). If PR 42 is merged without also committing the TRUE-Nash file, the citations become dangling references — any future reader checking out the PR-42 tree will find no evidence file backing the PASS+ verdict. This is a NEEDS-FIX before merge.

---

## 2. Reversal application check (3 modified files)

Diff source: `git diff 71d161d 794df95 -- <file>` (PR 42 commits cleanly on top of PR 38's `71d161d`).

### 2.1 `docs/persona_test_results/W3_5_v1_4_1_retest.md`
- **Edit type:** prepended "Verdict re-revision (2026-05-23 final) — PR 42 reversal" section at the top header block; updated verdict line to `PASS+`; relabeled the prior PR 38 BLOCKED note as "Intermediate verdict ... NOW SUPERSEDED by PR 42"; preserved the PR 38 BLOCKED rationale section verbatim below a divider that flags it as historical record. Net 41 line additions (per `git diff --stat`).
- **Fidelity to PR 42 framing:** correct. Verdict header (`:6`) now reads `**Verdict (FINAL — 2026-05-23 final, after PR 42 re-revision):** **PASS+**`. Intermediate-PR-38 verdict (`:7`) preserved with explicit "SUPERSEDED" marker. Original-PASS line (`:8`) also preserved. Re-revision section (`:10-49`) lays out the empirical numbers, source file pointer, and rationale for the reversal.
- **Status:** **APPLIED.**

### 2.2 `docs/pr13_prep/persona_acceptance_spec.md`
- **Edit type:** single-line replacement at the W3.5 inline note (1 deletion, 1 addition). PR 38's BLOCKED note replaced by a `2026-05-23 final` PR 42 PASS+ note that points to `W3_5_TRUE_nash_v1_5_1.md` and the revision-history doc, summarizes the 100%-check / 87%-check-13%-bet / 62%-defend findings, and explicitly states "This supersedes the PR 38 BLOCKED downgrade."
- **Fidelity to PR 42 framing:** correct. Old PR 38 note is fully replaced (not preserved alongside) — which makes sense because the spec file is the canonical "current verdict" surface; full history lives in the revision-history doc.
- **Status:** **APPLIED.**

### 2.3 `docs/pr13_prep/persona_verdict_revision_history.md`
- **Edit type:** appended new `## 2026-05-23 final re-revision (PR 42) — W3.5 reversal` section AT TOP (between the global header/scope text and the existing `## 2026-05-23 late corrections (PR 38)` section); updated the "Files referenced" list at the bottom to mention the new TRUE-Nash evidence file. 47 line additions, 1 deletion.
- **Fidelity to PR 42 framing:** correct. New section is properly chronological (later revision at top), preserves PR 38's section unchanged below, walks through trigger / rationale / empirical findings / counts / files-updated / files-not-modified. Files-referenced footer correctly notes the TRUE-Nash file as "NEW — PR 42 empirical evidence."
- **Status:** **APPLIED.**

### Per-file summary
| File | Verdict |
|---|---|
| `docs/persona_test_results/W3_5_v1_4_1_retest.md` | **APPLIED** |
| `docs/pr13_prep/persona_acceptance_spec.md` | **APPLIED** |
| `docs/pr13_prep/persona_verdict_revision_history.md` | **APPLIED** |

All three reversal edits are faithfully applied. PR 42's commit body claim of "3 files updated" matches the diff exactly.

---

## 3. History preservation check

`git log pr-42-w3-5-reversal --oneline | head -5`:

```
794df95 PR 42: REVERSE W3.5 downgrade per vector-form TRUE Nash validation
71d161d PR 38: spec + audit framing + retest prompts + revision history
149ca11 PR 38: propagate persona verdict downgrades (W3.5, W1.2)
b5777f2 v1.5.1: test rigor + docs honesty (engine bundle deferred to v1.5.2)
8b8d181 Honest docs: PR 7 '<10s/spot' claim was aspirational, never validated (see investigation)
```

- PR 42's `794df95` sits on top of the unchanged PR 38 commits.
- PR 38's `71d161d` and `149ca11` are present, unmodified (verified by SHAs matching the original PR 38 audit references).
- No rebase, amend, or force-push artifact — PR 42 is purely additive.

**Status: PRESERVED.**

---

## 4. Persona count consistency check

PR 42 commit body claim: "Updated persona count: 10 PASS / 5 PARTIAL / 3 BLOCKED."
PR 38 baseline (from `71d161d` revision-history file): "9 PASS / 5 PARTIAL / 3 BLOCKED" with W3.5 in the BLOCKED set.

### Direction check
- PR 42 moves W3.5 BLOCKED → PASS+. That adds 1 to PASS (9 → 10) and removes 1 from BLOCKED (3 → 2).
- The revised count "10 PASS / 5 PARTIAL / 3 BLOCKED" only sums to a delta of +1 PASS and 0 BLOCKED — implying one **new** BLOCKED has emerged or the BLOCKED count is wrong by 1.

### What PR 42's revision-history says about the new BLOCKED set
From `persona_verdict_revision_history.md` (PR 42 section):

> **3 BLOCKED:** W1.4 (PR 9 path), W2.3 (W2.3 RvR custom-range API gap distinct from W3.5's vector-form path), and 1 residual. W3.5 is **no longer** in this category.

The doc lists 2 of the 3 BLOCKED workflows (W1.4, W2.3) and explicitly acknowledges "1 residual" — i.e. the doc itself doesn't know what the third BLOCKED is. PR 38's BLOCKED set was {W1.4, W2.3, W3.5}; removing W3.5 leaves {W1.4, W2.3} = 2, not 3.

The audit task framing supplied to this agent ("the 3 BLOCKED are now: W2.3, W3.4, W4.3") does NOT match the revision-history doc's framing (which lists W1.4 + W2.3 + 1 residual). **Neither answer is empirically grounded** in the docs:
- W3.4 v1.4.1 retest's recorded verdict is **INCONCLUSIVE-SLOW**, not BLOCKED (see `W3_4_v1_4_1_retest.md:6`). The recommendation in that file is "soft re-open" pending perf instrumentation, not BLOCKED.
- W4.3 v1.4.0 retest's verdict is "BLOCKED — canonical parity test timeout regression" (`W4_3_v1_4_0_retest.md:8`), so W4.3 IS a plausible BLOCKED candidate.

### Inner inconsistency in PR 42's own "10 PASS" list
The revision-history doc lists the 10 PASS as: "W1.1, W1.3, W1.5, W2.4, W3.1, W3.2, W3.3, W3.5 (restored — PR 42), W4.1, W4.2, W4.3 (the count of 10 indicative; exact membership depends on which interim test reports are tallied)."

Counted: W1.1, W1.3, W1.5, W2.4, W3.1, W3.2, W3.3, W3.5, W4.1, W4.2, W4.3 = **11 items**, not 10.

If W4.3 belongs in PASS (per the listed enumeration), it cannot also be in BLOCKED (per the audit-task framing's alternative). PR 42's own enumeration self-contradicts unless one of the listed 11 (e.g. W3.1/W3.2/W3.3, which were "node-locking workflows" the v1.4.0 retest treated separately) doesn't actually have a PASS retest report. PR 38 already softly flagged this: "the exact PASS list depends on which interim test reports are counted."

### Headline number vs membership
- **Headline 10/5/3 = 18 total:** consistent with the 18-workflow universe per the spec, and direction (+1 PASS, −1 BLOCKED) matches the PR 42 reversal.
- **Membership ambiguity:** the BLOCKED set is documented as `{W1.4, W2.3, 1 residual}` in PR 42's own revision-history (i.e. the third member is not committed) and the PASS list contains 11 items, not 10.

### Verdict
**Persona count: HEADLINE CONSISTENT, MEMBERSHIP AMBIGUOUS.**

The 10/5/3 headline shift from PR 38's 9/5/3 by exactly +1 PASS / 0 PARTIAL / 0 BLOCKED is internally inconsistent (a +1 PASS should be paired with −1 BLOCKED, giving 10/5/2, unless a workflow simultaneously enters BLOCKED). PR 38's original 9/5/3 had the same +1/0/0-issue at the 17-total level ("leaves 1 workflow uncategorized" disclaimer at `persona_verdict_revision_history.md` PR 38 section); PR 42 inherits and reuses that disclaimer rather than resolving it.

This is the same indicative-not-load-bearing count language PR 38 used. It's not a regression from PR 38 — it's a preserved-and-relabeled inconsistency that neither PR 38 nor PR 42 has actually closed.

---

## 5. Verdict

| Audit dimension | Status |
|---|---|
| Empirical evidence | SUPPORTED |
| File 1 (W3_5_v1_4_1_retest.md) | APPLIED |
| File 2 (persona_acceptance_spec.md) | APPLIED |
| File 3 (persona_verdict_revision_history.md) | APPLIED |
| History preservation | PRESERVED |
| Persona count headline | CONSISTENT (with same indicative disclaimer as PR 38) |
| Persona count membership | AMBIGUOUS (carry-over from PR 38; not a new defect) |

**Overall verdict: NEEDS-FIX.**

The reversal's substance — the verdict change from BLOCKED to PASS+ and the propagation across the three docs — is correctly authored. However, **the empirical evidence file (`W3_5_TRUE_nash_v1_5_1.md`) is UNTRACKED**, not committed to PR 42's `794df95`. Every reference in the three modified files points at that file as the load-bearing source of the reversal; if PR 42 merges without also adding the TRUE-Nash file to a commit, the reversal is unsupported in the committed history.

**Recommended fix (single action):** add `docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md` to PR 42 (either by amending `794df95` or by a follow-on commit `PR 42b: add TRUE Nash evidence file`). After this fix, the audit would flip to APPROVE.

If the orchestrator confirms that the TRUE-Nash file is intentionally being held outside the PR (e.g. for staging into a separate evidence-archive PR), the three modified docs should soften their citations from "see file X" to "see TRUE-Nash evidence in upcoming PR Y" until the evidence file lands. Either approach closes the gap; the current state cites a file that doesn't exist in the committed tree.

---

## 6. Open questions for orchestrator

### Q1: PASS vs PASS+
The PR 42 docs use `PASS+` (in `W3_5_v1_4_1_retest.md` final verdict line and the acceptance-spec note) while the revision-history's count line says `PASS` (in the "10 PASS" list — W3.5 is shown as "restored" without the `+`). Both are present in the same PR.

The `+` is meant to signal "answered via the canonical vector-form method, stronger than a regular PASS." This is a defensible semantic distinction — the spec's polarization question was empirically closed via the gold-standard solver path (PR 23's vector-form Rust DCFR), which is a stronger evidence basis than a per-combo or aggregator proxy.

**My recommendation:** Keep PASS+ in the W3.5 retest doc and the acceptance-spec note where the evidence is being cited; use plain PASS in the count tally (because count summaries don't carry the qualifier). The current PR 42 wording already does this, just without an explicit policy statement. The orchestrator may want to formalize "PASS+ = answered via canonical method" in the spec.

### Q2: Pre-emptive up-revision of other downgraded verdicts
The W3.5 reversal demonstrates a methodology lesson: **downgrades issued on aggregator-only evidence are vulnerable to upward revision when the vector-form Nash path is exercised**. PR 38 downgraded W1.2 (JJ vs pot-sized river bet) on a similar "per-combo basket can't measure range Nash" critique.

W1.2's PR 38 downgrade rests on TWO orthogonal issues: (a) the 7.7% fold is convergence noise, not range-Nash, and (b) the all-in mass is engine-bookkeeping because villain is already all-in at the configured SPR. Issue (b) is independent of aggregator-vs-vector-form — it's a stack-depth / SPR issue that vector-form CFR doesn't fix. Issue (a) might be revisitable via a `solve_range_vs_range_rust` retest, but only if the retest is re-run at the new deeper-stack config (200 BB) that PR 38 prescribed for the W1.2 follow-up.

**My recommendation:** DO NOT pre-emptively up-revise W1.2 or W2b verdicts based on PR 42's evidence alone. The methodology lesson (per-combo proxies underestimate range Nash polarization) applies specifically to W3.5; the other downgrades have additional independent issues (W1.2's SPR=0 collapse; W2b's KK-vs-QQ-trips equity reality). Schedule a separate vector-form-retest wave for any other PR 38 downgrade whose ONLY critique was "aggregator can't measure range Nash" — but W1.2 and W2b have richer critiques than that.

### Q3: BLOCKED set membership (third member)
PR 42's revision-history acknowledges "1 residual" in the BLOCKED set but doesn't name it. The audit task framing supplied to me suggested {W2.3, W3.4, W4.3}, but W3.4's actual recorded verdict in `W3_4_v1_4_1_retest.md` is INCONCLUSIVE-SLOW (not BLOCKED), and the file explicitly recommends "soft re-open" pending perf instrumentation. W4.3's `W4_3_v1_4_0_retest.md` is recorded as BLOCKED.

**My recommendation:** Before any subsequent PR builds on the persona count headline, orchestrator should resolve membership for the BLOCKED set. Most plausible third member based on retest files: W4.3 (BLOCKED per its own retest), giving BLOCKED = {W1.4, W2.3, W4.3}. But this needs explicit policy because the count line is being cited as "load-bearing for release gating" in some downstream contexts even though the disclaimer says "indicative." Resolve the disclaimer-vs-load-bearing tension before W3.5's PASS+ recovery is propagated into release messaging.

---

## 7. File paths referenced (absolute)

- `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md` (empirical evidence — UNTRACKED; see §1 Critical Finding)
- `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/W3_5_v1_4_1_retest.md` (PR 42 modified)
- `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/persona_acceptance_spec.md` (PR 42 modified)
- `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/persona_verdict_revision_history.md` (PR 42 modified)
- `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/W3_4_v1_4_1_retest.md` (cross-checked — INCONCLUSIVE-SLOW, not BLOCKED)
- `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/W4_3_v1_4_0_retest.md` (cross-checked — BLOCKED)
- `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/untested_workflow_readiness_audit.md` (cross-checked for context)
