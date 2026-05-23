# Spec consistency review v2

**Date:** 2026-05-21
**Reviewer:** consistency audit agent (round 2)
**Inputs:** v1 review findings (`docs/spec_consistency_review.md`) + amended specs (PR 3.5, 4, 5, 6, 8, 9) + fix log (`docs/autonomous_log.md` "Spec consistency fixes (2026-05-21)")

## v1 findings → resolution status

### Blockers (B1–B4)

- **B1 (PR 4 → PR 6 `.npz` metadata seam).** Resolved — **PARTIAL** (header amendment correct; in-body Stage 5 description not re-edited).
  - PR 4 §3 header amendment (`pr4_spec.md:3`) declares: metadata is "a single nested dict (NOT separate top-level NumPy arrays per metadata field)" stored as `json.dumps(metadata).encode()` in a `bytes_` array. PR 6 un-nests via `serde_json::from_slice`.
  - PR 6 §4.4 (`pr6_spec.md:263`) explicitly mirrors this: "PR 4 §4 Stage 5 is authoritative on the on-disk layout: `metadata` is one nested dict… PR 6's Rust loader is responsible for the un-nesting on load."
  - **Drift:** PR 4 §4 Stage 5 body (`pr4_spec.md:120-136`) still shows the layout as `metadata           : { schema_version: 1, … }` without any note that the dict is actually serialized via `json.dumps().encode()` into a `bytes_` array. The header amendment notes the JSON-encoding, but the §4 Stage 5 body — where an implementer would naturally read the on-disk layout — was not updated. A reader who only reads §4 Stage 5 will not see the JSON-encoded-bytes layer. Severity: cosmetic / documentation-quality, not blocker (the header is authoritative).

- **B2 (PR 4 → PR 6 `source_path` on `HUNLConfig.abstraction`).** Resolved — **PARTIAL** (the canonical authoritative section is updated; two other locations in the same spec still describe the old type).
  - PR 4 §6 (`pr4_spec.md:156-165`) correctly declares: "`HUNLConfig` gains an optional `abstraction: Optional[AbstractionRef] = None` field" + dataclass `AbstractionRef(source_path: str, version: str)`. ✓
  - PR 6 §6.3 (`pr6_spec.md:434-436`) consumes the new field correctly: "PR 6 does NOT add a new field; it consumes the one PR 4 amended its spec to declare." ✓
  - **NEW INCONSISTENCY (drift within PR 4):**
    - PR 4 §3.5 line 53 still says: "`HUNLConfig` gains an optional field `abstraction: AbstractionTables | None = None`" — contradicts the §6 amendment.
    - PR 4 §8 Agent B deliverable line 354 still says: "Modifies `HUNLConfig` (adds `abstraction: AbstractionTables | None = None` field)" — contradicts §6.
  - Severity: medium. An implementer reading Agent B's deliverable section (§8 line 354) will produce code matching the old contract (`AbstractionTables | None`) instead of the new one (`Optional[AbstractionRef]`). The header amendment + §6 are authoritative but Agent B's prompt-handoff text directly contradicts them.

- **B3 (Action ID consistency across PRs).** Resolved — **NO CHANGE NEEDED** (already consistent; no edits made). ✓
  - PR 3 defines `ACTION_FOLD = 0` … `ACTION_ALL_IN = 13`; PR 6 §4.1 line 137 mandates byte-parity with the Python file; PR 9 confirms `action_abstraction.py` as source-of-truth.

- **B4 (Dispatch ordering across PR 3.5 / PR 5 / PR 9).** Resolved — **YES**.
  - PR 9 §6 (`pr9_spec.md:188-235`) is now declared canonical: header says "CANONICAL — referenced by PR 3.5 §6 and PR 5 §6", with explicit ordering invariant ("push/fold short-circuit MUST execute before the postflop and preflop branches") and boundary tests locked.
  - PR 3.5 §6 (`pr3_5_spec.md:194-207`) cross-references PR 9 §6 explicitly and includes the short-circuit-first language.
  - PR 5 §6 (`pr5_prep/pr5_spec.md:161`) likewise cross-references PR 9 §6.

### Important (I1–I10)

- **I1 (PR 5 "PR 4 is the last spec that touches `hunl.py`" — incorrect).** Resolved — **YES**.
  - PR 5 §6 "Not modified" line (`pr5_spec.md:170`) now reads: "(Note: PR 6 will modify `hunl.py` to add `_serialize_hunl_config`… and PR 8 will modify `hunl.py` to add `use_pcs: bool`…)". Footer note at line 174 confirms the cross-reference. ✓

- **I2 (PR 11 missing UX warning for missing abstraction artifact).** **NOT RESOLVED** — flagged for user.
  - Confirmed: `grep -n "first-launch\|precompute-abstraction\|abstraction artifact" docs/pr11_prep/pr11_spec.md` returns zero matches.
  - Fix log explicitly notes this as flagged-for-user (not blocking; the recommended ~5-line edit lives in PR 11 §3 / §6 pre-implementation).

- **I3 (PR 9 diff tolerance `1e-4` outlier).** Resolved — **YES**.
  - PR 9 §10.4 (`pr9_spec.md:380`) now reads: "PR 9 adopts the PR 6 / PR 7 / PR 8 tolerance cluster — `5e-3` per-action probability + `1e-3 × base_pot` per-spot game value. (Earlier draft cited `1e-4`; reconciled to match the established cluster per `docs/spec_consistency_review.md` finding I3.)" Justification provided. Tests at §10.4 #1–#4 all use the `5e-3 / 1e-3` cluster.
  - PR 9 §13 risk row (`pr9_spec.md:479`) corrected: "`5e-3` per-action + `1e-3 × base_pot` per-spot game-value tolerance from PR 6/7/8 applies (aligned per `docs/spec_consistency_review.md` I3; was previously misquoted as `1e-4`)".

- **I4 (PR 9 missing `psutil` 10% inheritance).** Resolved — **YES**.
  - PR 9 §12 (`pr9_spec.md:457-459`) now reads: "PR 9 explicitly inherits the same calibration tolerance… each subgame is solved sequentially (one at a time) with the same memory budget AND the same 10% calibration tolerance per-subgame."

- **I5 (PR 9 missing end-to-end exploitability target).** Resolved — **YES**.
  - PR 9 §7.4 (`pr9_spec.md:269-272`) now declares end-to-end target: "< 0.05 BB/hand on the PR 9 validation fixture (HU NL cash-game 100 BB starting stacks…)". Per-stage targets broken out: blueprint < 0.5 BB/100, refined per-subgame < 0.1 BB/100, unrefined < 1 BB/100. Test `test_combined_exploitability_under_0_05_bb_per_hand` added at §10.3 #5 (`pr9_spec.md:376`). Success criteria §17 references it (`pr9_spec.md:554`).

- **I6 (PR 8 `use_pcs` schema extension unauthorized).** Resolved — **YES**.
  - PR 8 §6 "Files to modify" table (`pr8_spec.md:281`) now includes `poker_solver/hunl.py` with explicit row: "Add `use_pcs: bool = False` field to `HUNLConfig` dataclass (Python schema extension authorized here; pre-mirrored in PR 6 §4.1 Rust `HUNLConfig`…)".
  - PR 6 §4.1 (`pr6_spec.md:115-120`) Rust `HUNLConfig` mirror pre-emptively includes `use_pcs: bool` with explanatory doc-comment: "Pre-included here to avoid a forced schema migration when PR 8 lands (per consistency review I6)." ✓
  - PR 5 §6 mentions both PR 6 + PR 8 will modify `hunl.py` (cross-reference complete, line 170).

- **I7 (PR 8 ambiguous "50/64 buckets" notation).** Resolved — **YES**.
  - PR 8 §2 spot 3 (`pr8_spec.md:34`) now reads: "**64/32/16 buckets** (tier-2 from PLAN.md §1)". Matches the documented tier. Spot 4 unchanged at 256/128/64 (default tier).

- **I8 (PR 11 bundle line — already consistent).** No-op confirmed. PR 11 §6.2 line 343 says "`poker_solver/charts/` (PR 3.5 push/fold charts)". Consistent.

- **I9 (PR 10 / PR 11 sequence — already consistent).** No-op confirmed.

- **I10 (PR 9 push/fold 15 BB boundary).** Already consistent; confirmed.

### Nice-to-resolve (N1–N7)

- **N1 (license attribution language varies).** NOT EDITED. Per fix-log: "user instructions restricted edits". Defer.
- **N2 (PR 10 success-criteria note).** NOT EDITED. Defer.
- **N3 (lossless vs bucketed key-format language).** NOT EDITED. Defer.
- **N4 (subgame / spot / subtree terminology).** NOT EDITED. Defer.
- **N5 (PR 4 §10 bundle hypothesis).** NOT EDITED. Per fix-log: "Recommended cleanup: PR 4 §10 should be edited" but explicitly skipped. Defer.
- **N6 (PCS opt-in consistency).** Confirmed; both PR 8 + PR 9 default to opt-in. ✓
- **N7 (`HUNLSolveResult` shape lock).** Resolved — **YES**.
  - PR 5 §14 #3 (`pr5_spec.md:533`) now reads: "**LOCKED** to subclass per `docs/spec_consistency_review.md` finding N7 — PR 9 and PR 11 already depend on the subclass form… Tuple form rejected."

## New findings (introduced by the amendments)

- **NEW-1 (PR 4 internal contradiction on `HUNLConfig.abstraction` type).** Severity: **MEDIUM**.
  - Three locations in PR 4 disagree:
    - Header amendment (line 3) + §6 line 156: `Optional[AbstractionRef]` ✓ (authoritative).
    - §3.5 line 53: `abstraction: AbstractionTables | None = None` (stale).
    - §8 Agent B deliverable line 354: `abstraction: AbstractionTables | None = None` (stale, prescriptive for Agent B).
  - An implementer following Agent B's instructions (§8 is the agent-prompt zone) will produce the old contract. The amendment didn't propagate to either the conceptual-architecture (§3.5) or agent-handoff (§8) sections.
  - Recommended fix: 2-line search-replace in §3.5 line 53 and §8 line 354 of `pr4_spec.md` from `AbstractionTables | None = None` to `Optional[AbstractionRef] = None`, with a parenthetical pointer to §6's `AbstractionRef` declaration.

- **NEW-2 (PR 4 §4 Stage 5 body doesn't describe the JSON-bytes layer).** Severity: **LOW** (cosmetic).
  - The header amendment specifies metadata is JSON-encoded into a `bytes_` array, but §4 Stage 5 (lines 120-136) still shows the metadata layout as a dict literal (`metadata : { schema_version: 1, … }`) without any reference to the JSON serialization. The header amendment is authoritative but a reader of §4 Stage 5 in isolation will not see the on-disk encoding detail.
  - Recommended fix: append one sentence to §4 Stage 5 after the layout block: "On disk, `metadata` is serialized via `json.dumps(metadata).encode()` into a one-element `bytes_` array inside the `.npz` (PR 6's Rust loader uses `serde_json::from_slice` to un-nest)."

- **NEW-3 (PR 6 Rust `HUNLConfig` keeps `abstraction: Option<Arc<AbstractionTables>>`, not `AbstractionRef`).** Severity: **NONE** (intentional, cross-tier seam is correct).
  - PR 6 §4.1 line 115 declares the Rust `HUNLConfig` mirror has `pub abstraction: Option<Arc<AbstractionTables>>` (the *loaded* table), not `AbstractionRef`. This is by-design: the PyO3 boundary passes `(config_json, abstraction_path: Option<&str>)` separately (PR 6 §5), and the Rust side materializes the in-memory `AbstractionTables` from the path. The Python `HUNLConfig.abstraction` (path-only `AbstractionRef`) and the Rust internal `HUNLConfig.abstraction` (loaded `AbstractionTables`) are different *types representing different lifetimes* — Python persists the path, Rust holds the loaded data. Documented at PR 6 §6.3 line 436. Not an inconsistency; flagged here only because a naive cross-tier diff would notice the type mismatch.

## Cross-cutting decisions — current consensus status

After v2, decisions are now consistent across specs:

- **HUNLSolveResult shape:** LOCKED subclass (was open) — PR 5 §14 #3, consumed by PR 9 + PR 11. ✓
- **Dispatch order (push/fold ≤15 BB → postflop → preflop → error):** LOCKED in PR 9 §6 canonical; PR 3.5 + PR 5 cross-reference. ✓
- **Diff-test tolerance cluster:** LOCKED `5e-3` per-action + `1e-3 × base_pot` per-spot game value across PR 6 §7.3, PR 7 §1 + §11 #3, PR 8 §7 Layer C+D, PR 9 §10.4. PR 8 Layer A (SIMD bit-exact) and Layer B (layout 1e-12) are correctly tighter for their own scope. ✓
- **`HUNLConfig.use_pcs` schema:** AUTHORIZED in PR 8 §6, pre-mirrored in PR 6 §4.1. ✓
- **`HUNLConfig.abstraction` field type:** Conceptually LOCKED to `Optional[AbstractionRef]` per PR 4 §6 + PR 6 §6.3 + PR 9 implicit; but PR 4 §3.5 + §8 still mention `AbstractionTables | None`. **One spec edit still needed (NEW-1).**
- **`.npz` metadata as JSON-bytes:** LOCKED per PR 4 header + PR 6 §4.4. Stage 5 body would benefit from one-line cross-reference (NEW-2, cosmetic).
- **End-to-end exploitability target (PR 9):** `< 0.05 BB/hand` on Pio 100 BB cash-game validation fixture — LOCKED, with tests. ✓
- **`psutil` 10% calibration inheritance:** PR 9 §12 inherits PR 5 §7.6. ✓

## Verdict

**Mostly READY, with one residual spec edit recommended before PR 4 launches** (NEW-1 inside PR 4 §3.5 + §8: 2-line patch to `Optional[AbstractionRef] = None`), and one cosmetic note (NEW-2) that doesn't block.

### Residual blocker count: **0 hard blockers**

The NEW-1 finding inside PR 4 (two locations still describing the old field type) is medium severity but not a hard blocker because the authoritative §6 + header amendment do correctly declare the new field. Agent B's prompt-zone language is wrong but the §6 contract is right, and Agent B is expected to read the spec end-to-end. Still, the cleanest path is patching those two lines before PR 4 launches.

### Per-PR launch readiness

| PR | v1 blockers | v2 status | Ready to launch? | Notes |
|---|---|---|---|---|
| **PR 3.5** | None | Cross-reference to PR 9 §6 added | YES | Dispatch text now consistent with canonical PR 9 §6. |
| **PR 4** | B1, B2 | Partial (header + §6 correct; §3.5 + §8 stale) | **YES with patch recommended** | NEW-1 patch (2-line type fix in §3.5 + §8) recommended before Agent B launches to avoid implementer ambiguity. NEW-2 cosmetic-only. |
| **PR 5** | I1 (note), N7 (lock) | Both fixed | YES | Dispatch cross-reference correct, `hunl.py` modification note corrected, `HUNLSolveResult` locked as subclass. |
| **PR 6** | B1, B2 (consumer), I6 (mirror) | All three fixed | YES | §4.1 mirrors `use_pcs`, §4.4 parses metadata dict, §6.3 consumes `AbstractionRef`. License + diff-test tolerance language aligned. |
| **PR 7** | None | Unchanged (no edit needed) | YES | Tolerances already in canonical cluster; no spec drift. |
| **PR 8** | I6, I7 | Both fixed | YES | Schema extension authorized, bucket notation clarified to "64/32/16 tier-2", diff-test tolerance reaffirmed. |
| **PR 9** | B4, I3, I4, I5 | All four fixed | YES | Dispatch declared canonical, tolerance aligned, profiler inheritance noted, end-to-end exploitability target added with test. |
| **PR 10** | None | Unchanged | YES | No consistency-review findings against PR 10 spec. |
| **PR 11** | I2 (not fixed) | I2 still unaddressed | **YES with caveat** | The first-launch missing-abstraction warning was explicitly deferred per fix log; recommend a ~5-line PR 11 spec edit before launch so users don't hit a broken solve on first install. Not a blocker (UX polish, not contract). N5 (PR 4 §10 bundle hypothesis update) also deferred. |
| **PR 12** | N/A | Not in v1 review scope | YES (independently) | New 3-handed stretch spec; no v1 findings apply. |

### Summary

All four v1 blockers are resolved at the authoritative-section level. PR 6 / PR 7 / PR 8 / PR 9 / PR 10 / PR 11 / PR 12 are ready to launch. PR 4 is functionally ready but carries one internal contradiction (NEW-1) where two non-authoritative sections still describe the old `AbstractionTables | None` field type — a 2-line patch resolves it cleanly. PR 11 has a known UX gap (I2 missing-abstraction first-launch warning) that the fix agent deferred; recommend a quick spec edit before PR 11 implementation begins but not a launch blocker for PR 11 since the gap was already flagged in the fix log.

The fix agent's claims in `autonomous_log.md` § "Spec consistency fixes (2026-05-21)" are **substantially accurate** — every blocker fix and every claimed Important-finding fix did land at the correct spec location. The one drift identified (NEW-1 in PR 4) is a propagation gap, not a wrong fix.
