# Audit-prompt maintenance check (periodic per-PR doc review)

**Date:** 2026-05-22
**Type:** Read-only filler audit (per >=5 agents rule)
**Scope:** Verify each PR's `audit_prompt_final.md` references all HIGH-PROB findings from the matching `audit_preprep.md`, branch names match canonical list, tolerance numbers (5e-3 / 1e-3) referenced consistently, and expected verdict probabilities sane. For PR 4.5/6/7/8/9/10a/10b/11/12 also cross-reference launch_kickoff for consistency.

## Canonical branch names (from `branch_name_final_check.md`)

- `pr-4.5-audit-debt-sweep`
- `pr-6-rust-hunl-port`
- `pr-7-noambrown-diff`
- `pr-8-neon-simd-pcs`
- `pr-9-hunl-preflop`
- `pr-10a-ui-mock-first`
- `pr-10b-ui-real-solver`
- `pr-11-library-and-packaging`
- `pr-12-three-handed-stretch`

---

## Per-PR consistency verdicts

### PR 4.5 (`pr4_5_audit_debt/`) — YELLOW

| Doc | Branch line | Verdict probabilities | HIGH-PROB cross-ref |
| --- | --- | --- | --- |
| `audit_preprep.md` | canonical (L199, L201) | §2: READY expected | §1.1, §1.4, §1.6, §1.7, §1.8 — five categories named |
| `audit_prompt_final.md` | canonical (L23) | ~70% READY / ~25% W-patches / ~5% NOT-READY | "HIGH-PROB items (1, 2, 9 — per §1.1 / §1.4 / §1.7)" |
| `launch_kickoff.md` | canonical (L11, L185) | n/a (gates) | n/a |

**Drift:** L7-10 of `audit_prompt_final.md` names the "Top three pre-flagged HIGH-PROB risk surfaces" as: (1) Mechanical-only scope guard (§1.1), (2) License-header text consistency (§1.4), (3) `PushFoldChartUnavailable` consumer-grep (which lives in body focus area 6, tagged "HIGH-PROB consumer-grep miss" but no §-reference). Body L70 says "HIGH-PROB items (1, 2, 9 — per `audit_preprep.md` §1.1 / §1.4 / §1.7)" — focus area 9 is "Cross-agent file ownership", §1.7 in preprep. The anchor (L7-10) and L70 list of HIGH-PROB items do not agree: the orchestrator-side anchor lists 3 risks (scope, license, consumer-grep ≈ areas 1, 2, 6), but L70 says (1, 2, 9). The consumer-grep risk (area 6, §1.3 in preprep) is HIGH-PROB by anchor but not by L70.

**Cleanup recommendation:** reconcile L70 to either (1, 2, 6, 9) or move consumer-grep mention out of the anchor.

### PR 6 (`pr6_prep/`) — YELLOW

| Doc | Branch line | Verdict | HIGH-PROB cross-ref |
| --- | --- | --- | --- |
| `audit_prompt_final.md` | canonical (L14) | READY-WITH-PATCHES (~implicit) | references spec amendments by number, not pre-flagged §-IDs |
| `launch_kickoff.md` | canonical (L7, L75) | gates only | n/a |

**Drift:** There is **NO `audit_preprep.md` for PR 6** (only `audit_prompt.md` and `audit_prompt_final.md`). PR 6 was the first port and was audited in-flight via a custom successor prompt that folds Agents A/B's actual deltas back into the focus list. The audit_prompt_final doesn't claim to cross-reference a preprep file — so this is structural drift, not a content bug. Tolerance refs `5e-3 / 1e-3` are present (L108-112) and correct.

**Cleanup recommendation:** none required. If consistency with PR 7-12 is desired, retroactively author a stub `pr6_prep/audit_preprep.md` for documentation symmetry.

### PR 7 (`pr7_prep/`) — GREEN

Branch `pr-7-noambrown-diff` canonical across all three docs. `audit_prompt_final.md` L6-8 names top three HIGH-PROB risks (§1.3, §1.4, §1.1) with explicit `audit_preprep.md §` references throughout body. Tolerance cluster 5e-3 / 1e-3 referenced consistently (L73, L91-95). Verdict probabilities (~55% W-patches / ~30% READY / ~15% NOT-READY) match preprep §3. Branch hard-coded in audit_prompt.md per launch_kickoff L7.

### PR 8 (`pr8_prep/`) — YELLOW

Branch `pr-8-neon-simd-pcs` canonical across all three docs. Verdict probabilities (~50/30/15/5%) match preprep §3. Tolerance refs (5e-3 / 2e-2 / 1e-3 cluster) consistent.

**Drift:** L52 of `audit_prompt_final.md` names HIGH-PROB items as "(§1.1, §1.5, §1.6 per audit_preprep.md)" — mapping to focus areas 1 (baseline-first), 4 (`unsafe`), 8 (10x gate). But L231 says "HIGH-PROB risk surfaces (focus areas 1, 2, 3, 4, 8)". Body inline tags ALSO flag focus area 2 as `[HIGH-PROB must-fix per §1.2]` (L61) and focus area 3 as `[HIGH-PROB must-fix per §1.3]` (L73). So L52 under-counts (missing §1.2, §1.3) while L231 is correct.

**Cleanup recommendation:** patch L52 to "(§1.1, §1.2, §1.3, §1.5, §1.6 per audit_preprep.md)" so the upfront paragraph matches the inline tags and the L231 procedural note.

### PR 9 (`pr9_prep/`) — GREEN

Branch canonical across all three docs. Three HIGH-PROB risks (§1.1, §1.5, §1.2 mapping to focus areas 5, 6, 16) consistent at L7-10, L59 ("Pre-flagged HIGH-PROB items (focus areas 5, 6, 16 — per §1.1, §1.5, §1.2)"), L266 ("HIGH-PROB risk surfaces (focus areas 5, 6, 16)"). Tolerance 5e-3 / 1e-3 referenced consistently throughout — preprep correctly flags the I3 reconciliation from 1e-4 misquote. Verdict probabilities match preprep §3.

### PR 10a (`pr10_prep/audit_prompt_final_10a.md`) — GREEN

Branch `pr-10a-ui-mock-first` canonical. Two HIGH-PROB risks (§1.1, §1.5) consistent at L7, L52, L216. The audit_preprep_10a vs final cross-references are clean. Note: 5e-3 / 1e-3 tolerance not applicable here (mock-fidelity / MDF cap is the relevant metric). Verdict probabilities (~60/25/15%) match preprep §3.

### PR 10b (`pr10_prep/audit_prompt_final_10b.md`) — GREEN

Branch `pr-10b-ui-real-solver` canonical. Two HIGH-PROB risks (§1.1, §1.2) consistent at L7, L46, L175. Verdict probabilities (~60/30/10%) match preprep §3. Cross-reference to PR 9 spec for `on_progress` signature lock is correct.

### PR 11 (`pr11_prep/`) — GREEN

Branch `pr-11-library-and-packaging` canonical across all three docs. Three HIGH-PROB risks (§1.1 PyInstaller --add-binary, §1.2 code-signing optionality, §1.3 DMG notarization) consistent at L7-8, L53, L226. Verdict probabilities (~55/30/15%) match preprep §3. Low-prob-but-must-fix-band items (§1.4 WAL, §1.5 gzip-6, §1.6 schema) explicitly enumerated.

### PR 12 (`pr12_prep/`) — GREEN

Branch `pr-12-three-handed-stretch` canonical across all three docs. Three HIGH-PROB risks (§1.1 badge unsuppressible, §1.2 per-pair BR terminology, §1.3 side-pot TDA fixtures) consistent at L7, L51, L245. Verdict probabilities (~45/30/15/10%) match preprep §3. Tolerance refs in body (L157-159: HU 5e-3 vs 3p diff 1e-6) correctly distinguish per-spec rationale.

---

## Drift summary

**Total PRs checked:** 9 (4.5, 6, 7, 8, 9, 10a, 10b, 11, 12).
**Total audit_preprep + audit_prompt_final + launch_kickoff doc set audited:** 26 files (8 PRs * 3 + PR 6 has no preprep).
**GREEN verdicts:** 6 (PR 7, 9, 10a, 10b, 11, 12).
**YELLOW verdicts:** 3 (PR 4.5, 6, 8).
**RED verdicts:** 0.
**Drift count:** 3 minor.

### Top 3 drift items

1. **PR 8 audit_prompt_final L52 under-counts HIGH-PROB items.** L52 lists (§1.1, §1.5, §1.6) per upfront paragraph; body inline tags also flag focus areas 2 (§1.2) and 3 (§1.3) as HIGH-PROB; L231 procedural note correctly lists all five (1, 2, 3, 4, 8). Patch L52 to add §1.2 + §1.3.

2. **PR 4.5 audit_prompt_final HIGH-PROB list inconsistent between anchor and body.** L7-10 names top three as (scope guard, license headers, PushFoldChartUnavailable consumer-grep) ≈ focus areas 1, 2, 6. L70 says "HIGH-PROB items (1, 2, 9 — per §1.1 / §1.4 / §1.7)". Focus areas 6 and 9 differ. Decide whether the third HIGH-PROB area is 6 (consumer-grep) or 9 (cross-agent ownership) and reconcile both citations.

3. **PR 6 missing `audit_preprep.md` entirely.** The audit_prompt_final is correctly customized for what Agents A+B shipped (5 spec amendments documented), but the absence of a preprep breaks the symmetric pattern used by PR 7-12. Either author a retroactive stub or document the asymmetry in `docs/INDEX_2026-05-22.md`.

---

## Additional notes (read-only observations)

- **Tolerance cluster** (5e-3 per-action / 1e-3 per-spot) is consistently anchored across PR 6, 7, 8, 9 as a single "tolerance cluster" — phrasing is uniform.
- **PR 12** uniquely uses tighter 1e-6 for the small 3p river fixture (justified by fixture size) and explicitly notes the deviation from HU 5e-3.
- **Verdict probability anchors** in pre-stage orchestrator notes correctly avoid leaking into agent prompt body (per the "DO NOT include in prompt itself" pattern at top of every audit_prompt_final).
- **Branch-name discipline** is clean in all audit_prompt_final files (no `pr-6-hunl-rust-port` typo, no `pr-8-simd-layout-pcs`, no `pr-11-library-packaging`, no `pr-12-three-handed`). All canonical.
- **Cross-PR references** (PR 9 -> PR 10b on_progress, PR 6 -> PR 9 §6 dispatch ordering, PR 10b -> PR 9 + PR 10a) are coherent and bidirectional.

---

## Cleanup recommendations

1. (~10 min) Patch PR 8 `audit_prompt_final.md` L52 to list all 5 HIGH-PROB §-references (§1.1, §1.2, §1.3, §1.5, §1.6).
2. (~5 min) Reconcile PR 4.5 `audit_prompt_final.md` L7-10 anchor vs L70 inline; pick one canonical "top three" set.
3. (~optional) Retroactively author PR 6 `pr6_prep/audit_preprep.md` stub for documentation symmetry, OR document the omission in `INDEX_2026-05-22.md`.
4. (~ongoing) No action on PR 7, 9, 10a, 10b, 11, 12 — all GREEN.
