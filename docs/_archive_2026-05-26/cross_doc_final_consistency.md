# Cross-Doc Final Consistency Check — 2026-05-23

**Scope:** 4 user-facing docs, 8 cross-check fields.

Docs (abbreviated):
- **WB** = `docs/WELCOME_BACK_USER_2026-05-23.md` (primary touchdown)
- **FAQ** = `docs/PRE_SIGNON_FAQ.md`
- **STATUS** = `docs/STATUS_2026-05-23_post_retest_5th_reversal.md`
- **PREP** = `docs/PR_REVIEW_PREP_2026-05-23.md`

Relevance rules: PREP is PR-triage scoped, so persona-count / reversal-chain / Path-D are not expected of it. Each field below notes relevance.

---

## Field 1 — Persona count: 12 PASS / 4 PARTIAL / 2 BLOCKED

| Doc | Mentions | Value | Consistent? |
|---|---|---|---|
| WB | YES (L63, L104) | 12 PASS / 4 PARTIAL / 2 BLOCKED on 18 workflows | ✓ |
| FAQ | YES (L109) | 12 / 18; "zero Type B regressions post-R5" | ✓ (counts agree; PARTIAL+BLOCKED breakdown not given but consistent with 18-12=6 split) |
| STATUS | YES (L119-122, L191) | 12 PASS / 4 PARTIAL / 2 BLOCKED, Type B regression = 0 | ✓ |
| PREP | N/A (out of scope) | — | — |

**Consistent.** All three relevant docs report 12 PASS. FAQ doesn't spell out the 4 / 2 breakdown but is consistent (12+4+2=18). No drift.

---

## Field 2 — Reversal chain: 5 reversals (R1-R5)

| Doc | Mentions | Detail | Consistent? |
|---|---|---|---|
| WB | YES (L47-57, L11) | Full R1-R5 enumeration, matches STATUS framing | ✓ |
| FAQ | YES (L42 R5 reference; L93 cites pattern) | R5 cited; refers reader to WB §"5-reversal chain" | ✓ |
| STATUS | YES (L5-13, full §"Reversal #5") | Full R1-R5 enumeration with sources | ✓ (canonical) |
| PREP | NO | — | N/A — out of scope (PR-triage doc) |

**Consistent.** WB and STATUS use identical R1-R5 framing verbatim. FAQ defers to WB. No drift.

---

## Field 3 — Path D: PROPOSED, awaiting user

| Doc | Mentions | Status phrasing | Consistent? |
|---|---|---|---|
| WB | YES (L11, L27, L109) | "PENDING USER OK" | ✓ |
| FAQ | YES (L22, L46-48, L110) | "PENDING USER OK"; "Recommended: APPROVE" | ✓ |
| STATUS | YES (L58, L81-82, L190) | "still PROPOSED"; "awaiting user Path D OK" | ✓ |
| PREP | NO | — | N/A — out of scope (Path D ships via script, not PR) |

**Consistent.** All three relevant docs flag Path D as pending user decision. FAQ adds "Recommended: APPROVE" stance — that's an editorial position, not a state claim, so no drift. PREP correctly excludes (explicitly notes Path D is out of PR-merge scope, FAQ L87 also clarifies).

---

## Field 4 — 3 open PRs (#2 USAGE / #3 .dmg / #4 README)

| Doc | Mentions | Detail | Consistent? |
|---|---|---|---|
| WB | YES (L29-33, L103) | #2 USAGE, #3 .dmg, #4 README; all URLs | ✓ |
| FAQ | YES (L23, L52-59, L108) | Same 3 PRs, same branch names, same risk labels | ✓ |
| STATUS | YES (L66, L72-76) | References same branches in-flight | ✓ |
| PREP | YES (L3-7, full per-PR sections) | Same 3 PRs; full triage | ✓ (canonical) |

**Consistent.** All 4 docs identify the same 3 PRs by same numbers, same branch slugs, same purpose. No drift.

---

## Field 5 — Origin HEAD: `3843ce7` (v1.7.0)

| Doc | Mentions | Value | Consistent? |
|---|---|---|---|
| WB | YES (L4, L17, L100) | `3843ce7` v1.7.0 | ✓ |
| FAQ | YES (L3, L15, L105) | `3843ce7` v1.7.0 | ✓ |
| STATUS | YES (L43, L55) | `3843ce7` v1.7.0 | ✓ |
| PREP | NO (not relevant for PR triage) | — | N/A |

**Consistent.** All three relevant docs cite `3843ce7` as HEAD. No drift.

---

## Field 6 — v1.6.0 .dmg LIVE: SHA256 `0443e8f0...`

| Doc | Mentions | Value | Consistent? |
|---|---|---|---|
| WB | YES (L21, L102) | "45 MB, SHA256 `0443e8f0...`" | ✓ |
| FAQ | YES (L5, L15, L107) | "45 MB, arm64; SHA256 `0443e8f0...`" | ✓ |
| STATUS | YES (L46) | "45 MB, SHA256 `0443e8f0...`" | ✓ |
| PREP | NO | — | N/A |

**Consistent.** All three relevant docs cite same SHA256 prefix and 45 MB. No drift.

---

## Field 7 — v1.7.0 release notes: class-expansion semantics (NOT wrapper bug)

| Doc | Mentions | Framing | Consistent? |
|---|---|---|---|
| WB | YES (L11, L35, L55, L91) | "class-expansion semantics nuance, not a code bug"; v1.7.1 code patch CANCELED | ✓ |
| FAQ | YES (L42) | "class-expansion semantics framing (no 'wrapper bug' language)" | ✓ |
| STATUS | YES (L11, L29, L132, L186-188) | "class-expansion API semantics nuance"; "v1.7.1 code patch CANCELED post-R5" | ✓ |
| PREP | YES (L31, L13 title, L23) | "class-expanded 79-combo input vs PoC's 15-combo"; "class-label vs combo-level expansion semantics" | ✓ |

**Consistent.** All 4 docs land on the same diagnostic framing: not a wrapper bug, it's class-expansion semantics. No "wrapper bug confirmed" language in any doc; all four explicitly retract that earlier framing. No drift.

---

## Field 8 — Suggested merge order: #4 → #2 → #3

| Doc | Mentions | Order | Consistent? |
|---|---|---|---|
| WB | NO explicit order (lists PRs as 2/3/4 but doesn't prescribe order) | — | N/A (defers to PREP) |
| FAQ | YES (L79) | "#4 (README cleanup, smallest) → #2 (USAGE.md, docs only) → #3 (.dmg packaging…)" | ✓ |
| STATUS | NO explicit merge-order (lists PRs in-flight) | — | N/A (status doc, not triage) |
| PREP | YES (L181-183) | "PR #4 first … PR #2 second … PR #3 last" | ✓ (canonical) |

**Consistent.** FAQ and PREP both prescribe #4 → #2 → #3, in the same rationale (smallest/least-risky first; .dmg last because it triggers rebuild follow-up). WB lists PRs by number (2/3/4) but does not prescribe — defers to PREP/FAQ. No drift.

---

## Drift summary

| Field | Drift? |
|---|---|
| 1. Persona count 12/4/2 | None |
| 2. R1-R5 reversal chain | None |
| 3. Path D pending | None |
| 4. 3 open PRs | None |
| 5. Origin HEAD `3843ce7` | None |
| 6. v1.6.0 .dmg `0443e8f0...` | None |
| 7. Class-expansion framing | None |
| 8. Merge order #4→#2→#3 | None |

**Drift count: 0 / 8 fields**

---

## Minor observations (not drift; flagged for awareness)

1. **WB lists PRs in numeric order (2/3/4) without prescribing merge order.** This is fine because WB explicitly defers to PREP for merge triage. If user reads WB only, they'd see 2/3/4 ordering; if they follow the FAQ/PREP link they'd see #4→#2→#3. Not contradictory, but a reader reading WB-only might infer 2-first ordering. Low priority — both docs cross-reference PREP for triage.

2. **FAQ Q1 references `docs/STATUS_2026-05-23_v1_7_0_shipped.md` as a deep-dive (L15).** That doc was likely superseded by STATUS_2026-05-23_post_retest_5th_reversal.md per its own L3 header ("Supersedes: docs/STATUS_2026-05-23_post_retest.md"). The FAQ pointer may be a stale link — worth user-flagging but not strictly a consistency-field drift, so flagged here as an observation rather than counted as drift on the 8 cross-check fields.

3. **STATUS doc cites W4.3 PASS at L119/L124 (per-bucket) and L191 (summary).** Both consistent within STATUS. WB also cites W4.3 PASS via aggregator at L63. FAQ does not enumerate W4.3 specifically but its 12/18 PASS count includes it.

---

## Aggregate verdict

**COHERENT** — all 8 fields consistent across the relevant docs. Zero drift identified on the load-bearing fields. Two minor observations (potentially-stale link in FAQ, WB defers merge-order to PREP) are not contradictions; flagged for user awareness.

**Recommendation:** Ship as-is. The 4-doc bundle tells one consistent story.
