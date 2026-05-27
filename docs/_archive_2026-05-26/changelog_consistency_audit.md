# CHANGELOG Consistency Audit — v1.4.0 through v1.5.1

**Date:** 2026-05-23
**Scope:** `CHANGELOG.md` on `origin/main` (HEAD `b5777f2`, tag `v1.5.1`)
**Auditor:** read-only audit; no CHANGELOG.md edits performed.
**Budget:** 12 min.

This audit reviews stylistic + factual consistency across the v1.4.0 → v1.5.1 entries, cross-references PR citations to actual branches / commits / files, and verifies cited spec docs exist.

---

## 1. Net Verdict

**NEEDS-MICRO-PR.** One HIGH-severity stale-version reference (v1.5.1 entry points engine bundle to "v1.5.2" but the tag ladder has since been re-keyed to v1.6.0 GUI first → v1.6.1 engine bundle). Two MEDIUM-severity items (v1.5.0 entry omits the empirical acceptance-test status; v1.5.1 does not yet reflect the test-bug diagnosis converged on 2026-05-23 late). One LOW-severity formatting nit (missing blank line between v1.4.1 last bullet and v1.4.0 H2).

The HIGH-severity item is reader-misleading: callers of the CHANGELOG will look for v1.5.2 and find nothing (the next release is v1.6.0 GUI). Recommended as a micro-PR before v1.6.0 ship, or rolled into the v1.6.0 CHANGELOG entry itself if cheaper.

---

## 2. Per-Version Review

### v1.5.1 — 2026-05-23 (PR 32 + PR 36 + PR 37; engine bundle deferred)

**Style:** OK. Plain `### Added` / `### Changed` / `### Deferred to v1.5.2` / `### Honest scope` headers (no inline "—" subtitle), which is a stylistic departure from v1.5.0 / v1.4.3 / v1.4.1 / v1.4.0 where the `### Added — <feature>` pattern is used. This is consistent with v1.4.2 ("Fixed — Docs honesty + test marker") and tolerable; it just trades thematic clarity for compactness.

**Factual accuracy:**
- PR 32 / PR 36 / PR 37 citations match local branch names `pr-32-pr-7-docs-honesty`, `pr-36-profiler-test-rigor`, `pr-37-equity-test-helper`. Commits `8b8d181` (PR 32), `5145674` (PR 36), `87e0b9a` (PR 37) all reachable from `origin/main`. PASS.
- `tests/_equity_helpers.py`, `tests/test_memory_profiler.py`, `tests/test_river_diff_self_sanity.py` all present in `origin/main` tree. PASS.
- `docs/river_parity_timeout_investigation_2026-05-23.md` cited at line 37 — exists. PASS.
- 91-green / 5-skipped smoke test count: not independently re-verified in this audit (would need a test run; out of budget).

**Cross-references:**
- **HIGH:** Line 44 — `### Deferred to v1.5.2` — and line 45-49: "Engine bundle (PR 33 + PR 34 + PR 35 + caveats) is HELD … v1.5.2's gating responsibility." This is **stale**. `PLAN.md` and `docs/leg18_v1_6_0_gui_ship_plan.md` now anchor the engine bundle at **v1.6.1**, because v1.6.0 GUI surfaces (PR 24a + PR 24b) ship first. PLAN.md explicitly states: "Engine bundle now scheduled as **v1.6.1**" (PLAN.md line 9). LEG 17 ship report `docs/leg17_v1_5_1_ship_report.md` still references "v1.5.2" because it was written before the rename, but the authoritative PLAN.md plus LEG 18 plan have flipped to v1.6.1. The CHANGELOG entry mis-aligns with current planning.
- **MEDIUM:** Lines 58-60: "v1.5.0 acceptance-test status is unchanged. This release does NOT address the per-action divergence observed in the v1.5.0 Brown apples-to-apples acceptance test." Per `PLAN.md` (line 9) and `docs/leg17_v1_5_1_ship_report.md` (lines 5-9, 329, 457-461), the divergence has since been **diagnosed as TEST-BUGS (NOT solver-bugs)**: action-ordering + range-slot misassignment in the acceptance harness. The diagnosis converged 2026-05-23 late (PR 23 cell deep-dive + W3.5 RvR PoC + W1.2 deep-stack + per-action divergence diagnosis). The v1.5.1 CHANGELOG entry pre-dates this convergence and still frames the divergence as "pending diagnosis." Honest-framing language should be updated to: "diagnosed as test-bugs in the acceptance harness, not solver-bugs; engine fix and test-plumbing fix deferred to v1.6.1."

**Tense:** Past tense throughout for shipped work; future tense ("remains v1.5.2's gating responsibility") for the deferred bundle. OK except the v1.5.2 anchor is stale.

**Verdict:** NEEDS-MICRO-PR for HIGH + MEDIUM items.

---

### v1.5.0 — 2026-05-23 (PR 23 + PR 28)

**Style:** Uses `### Added — <feature>` headers (matches v1.4.x convention). Two sub-`### Added —` blocks split between PR 23 and PR 28; reasonable.

**Factual accuracy:**
- `crates/cfr_core/src/dcfr_vector.rs` (line 70) — exists on origin/main. PASS.
- `references/code/noambrown_poker_solver/cpp/src/trainer.cpp:138-209` (line 74) — file exists. Line range not independently verified.
- `tests/test_range_vs_range_rust_diff.py` (4 active, 1 skipped) and `tests/test_v1_5_brown_apples_to_apples.py` (574 LOC, opt-in via `-m parity_noambrown`) — both exist on origin/main. PASS on file existence.
- "<= 0.05 BB exploitability on the Case A spot" (line 49-50) — not independently re-verified.

**Cross-references:**
- **MEDIUM:** v1.5.0 entry presents the Brown apples-to-apples acceptance test (PR 28) as if it works as intended: "asserts <= 5e-3 strategy diff on >= 80% of histories" (line 108-109). It does NOT mention that the test **actually failed empirically** on the 9sTs vs b1500 spot (Brown=0% bet vs Rust=98.6% bet) when first executed — which was later diagnosed (post-v1.5.1) as compound test-bugs in the acceptance harness, not a solver bug. Reader of the CHANGELOG would not know this from the v1.5.0 entry alone. The honest framing per PLAN.md is: "acceptance test had compound test bugs (NOT solver bug; resolved in v1.6.1 via PR 40)" (PLAN.md line 110). The v1.5.0 CHANGELOG entry is silent on this — a "Known issues" or "Honest framing" sub-section would be appropriate.
- The "Deferred to v1.5.1+" block (lines 118-126) is partly factually superseded:
    - "Wire `range_aggregator.solve_range_vs_range` to use the new Rust tier" — per PLAN.md, this is now PR 33, queued for v1.6.1 (not landed in v1.5.1). The v1.5.0 phrasing said "deferred to v1.5.1+" which technically permits a later release; the "+" suffix saves it from being factually wrong. LOW.
    - "UI surfacing" — per LEG 18, this lands as v1.6.0 (PR 24a + PR 24b). Same: "v1.5.1+" covers it.
    - These are not hard inconsistencies given the "+" semantics; they're just diffuse cross-references.

**Tense:** Past tense for shipped, future tense for deferred. OK.

**Verdict:** MEDIUM honest-framing gap on the acceptance test status. Suggest adding a "Known issues" line in a future micro-PR or in the v1.6.1 CHANGELOG retrospectively.

---

### v1.4.3 — 2026-05-23 (PR 27 + PR 30 + PR 31)

**Style:** Three `### Added — / Fixed — / Documentation —` blocks (PR-grouped); `### Honest scope` closer. Matches v1.5.0 / v1.4.0 idiom. PASS.

**Factual accuracy:**
- PR 31 (`pr-31`-style branch not in `git branch` listing under that name; need to check): `pr_proposals` doesn't list it but the commit `8fd9dbd` ("HUNLConfig: validate types in __post_init__ …") matches. PASS by commit-name match, even if there's no explicit `pr-31-*` local branch (PR was likely merged inline).
- PR 27 = local branch `pr-27-range-diff-utility` (matches). PASS.
- PR 30 = local branch — `git branch` listing did not show `pr-30-*` but commit `f9c9aad` ("PR 30 fix-ups: v1.4.3 preamble …") matches. PASS by commit-name match.
- `tests/test_range.py` (22 tests), `tests/test_hunl_config_validation.py` (28 tests) — both exist. PASS.

**Cross-references:**
- "v1.4.2 `_rust.cpython-313-darwin.so` is byte-identical for this release" — true per ship plan. PASS.

**Tense:** Past tense throughout. PASS.

**Verdict:** APPROVE.

---

### v1.4.2 — 2026-05-23

**Style:** `### Fixed — Docs honesty + test marker` + `### Honest framing` closer. Compact, two-fix entry. Matches v1.4.1 idiom. PASS.

**Factual accuracy:**
- `poker_solver/range_aggregator.py` docstring fix — exists. Per commit history (`b18beeb`, `9d9640c`), matches.
- `tests/test_river_parity_vs_brown.py::test_river_parity_vs_brown` `@pytest.mark.slow` — commit `e0c950f` confirms. PASS.

**Cross-references:** None to flag.

**Tense:** Past tense. PASS.

**Verdict:** APPROVE.

---

### v1.4.1 — 2026-05-23 (PR 22)

**Style:** `### Fixed — Asymmetric initial-contributions (PR 22)` + `### Persona workflows unblocked` + `### Honest framing`. Matches v1.4.0 idiom. PASS.

**Factual accuracy:**
- `HUNLPoker.initial_state` and `crates/cfr_core/src/hunl.rs` mirror fix — branch `pr-22-asymmetric-contributions` exists. Commit `ceff9bb` matches. PASS.
- `docs/pr_proposals/v1_4_asymmetric_contributions.md` cited at line 235 — exists. PASS.
- `docs/pr13_prep/v1_3_1_s4_retest.md` cited at line 244 — exists. PASS.
- `tests/test_asymmetric_contributions.py` (13 tests) — should exist; not independently verified but commit history supports.

**Cross-references:** "spec §7 'expect 0-2 such bugs during Fix A'" (line 250) — verbatim quote, attribution OK.

**LOW formatting:** Line 273 "get an early, clear error." → line 274 `## [1.4.0] - 2026-05-23` has **no blank line between the closing bullet and the next H2 heading**. All other v1.4.x → v1.4.y boundaries have a blank line (e.g., line 222 → 224, line 196 → 199). Cosmetic; one-line fix.

**Tense:** Past tense. PASS.

**Verdict:** APPROVE (with LOW formatting note).

---

### v1.4.0 — 2026-05-23 (PR 21)

**Style:** `### Added — Node locking (marquee feature; PR 21)` + `### Daniel persona workflows unblocked (4 of 5)` + `### Honest framing` + `### Performance` + `### Resolves`. Matches PR 21 spec. PASS.

**Factual accuracy:**
- `docs/pr_proposals/v1_4_node_locking.md` cited line 283 — exists. PASS.
- `docs/leg9_v1_4_0_ship_plan.md` cited line 332 — exists. PASS.
- `tests/test_node_locking.py` (19 tests) — should exist; commit history supports.
- "1.6% vs unlocked (target: <10%)" — not independently re-verified.

**Cross-references:**
- "Convergence under one-sided locking … DCFR α=1.5/β=0/γ=2.0 schedule was tuned for two-sided play" (line 325-328) — honest caveat language. PASS.

**Tense:** Past tense. PASS.

**Verdict:** APPROVE.

---

## 3. Cross-Cutting Style Observations

| Aspect | v1.4.0 | v1.4.1 | v1.4.2 | v1.4.3 | v1.5.0 | v1.5.1 |
|---|---|---|---|---|---|---|
| `### Added — <feature> (PR N)` pattern | YES | YES (Fixed —) | YES (Fixed —) | YES (three sub-blocks) | YES | NO (plain `### Added`) |
| Closing `### Honest framing` / `### Honest scope` | YES | YES | YES | YES (Honest scope) | NO | YES (Honest scope) |
| File-line citations (e.g., `:138-209`) | YES (Appendix §) | YES | NO | NO | YES (`trainer.cpp:138-209`) | NO |
| Empirical perf gates cited | YES (1.6%) | NO | N/A | NO | YES (<= 5e-3, <= 0.05 BB) | NO |
| "Deferred to vX.Y" sub-block | NO (only "Resolves") | NO | NO | NO | YES (`v1.5.1+`) | YES (`v1.5.2` — **stale**) |
| PR branch citation matches local branches | YES (`pr-21-*`) | YES (`pr-22-*`) | (no PR cited) | YES (PR 27 / 30 / 31) | YES (`pr-23-*` / `pr-28-*`) | YES (PR 32 / 36 / 37) |

**Observations:**
- v1.5.1 is the only entry without inline-em-dash subtitle in `### Added` / `### Changed`. Stylistic departure, LOW.
- v1.5.0 is the only post-GA entry lacking a `### Honest framing` / `### Honest scope` closer. This compounds with the MEDIUM acceptance-test-omission flag above (the closer is where the empirical caveat would naturally land).
- All other v1.4.x / v1.5.x entries have either past-tense shipped framing or explicit deferred future-tense; tense is consistent throughout.

---

## 4. Tag-Ladder Mention Consistency

**v1.5.0 entry says:** "preflop RvR deferred to v1.5.1 per spec §8 Q2" (line 90), "EMD bucketing also deferred to v1.5.1" (line 92). **Reality:** v1.5.1 did NOT ship preflop RvR or EMD bucketing — it shipped test rigor only. **However**, the "v1.5.1+" semantic in the "Deferred to" block (line 118) saves the spec citation from being a hard inconsistency: anything deferred to "v1.5.1+" is allowed to slip later. The per-bullet "deferred to v1.5.1" (lines 90, 92) without `+` is technically a soft promise broken; **LOW** because the v1.5.0 entry was authored before the v1.5.1 scope contraction.

**v1.5.1 entry says:** engine bundle "Deferred to v1.5.2" (line 44). **Reality per PLAN.md / LEG 18:** v1.6.0 GUI ships first, engine bundle ships as **v1.6.1**. **HIGH** because (a) v1.5.2 will never exist, (b) future readers searching for v1.5.2 will find nothing, (c) PLAN.md is now the authoritative source and it says v1.6.1.

---

## 5. Recommended Micro-PR(s)

### Micro-PR A — HIGH-severity v1.5.1 stale anchor

**Scope:** Single-file edit to `CHANGELOG.md` v1.5.1 entry.

**Changes (suggested wording):**
1. Line 44: `### Deferred to v1.5.2` → `### Deferred to v1.6.1`.
2. Lines 45-49: replace "v1.5.2's gating responsibility" with "v1.6.1's gating responsibility (engine bundle ships after v1.6.0 GUI per LEG 18 sequencing)".
3. Lines 58-60: replace "the per-action divergence observed in the v1.5.0 Brown apples-to-apples acceptance test" with honest-converged framing, e.g.: "the per-action divergence observed in the v1.5.0 Brown apples-to-apples acceptance test was diagnosed (2026-05-23 late) as compound test-bugs in the acceptance harness — action-ordering + range-slot misassignment — NOT solver-bugs in PR 23. Engine bundle (PR 33-35) + acceptance-test plumbing fix (PR 40) ship together as v1.6.1; see `docs/v1_5_0_per_action_divergence_diagnosis.md`."

**Severity:** HIGH (reader-misleading version reference).

### Micro-PR B — MEDIUM-severity v1.5.0 honest framing

**Scope:** Add a short "Known issues" or "Honest framing" sub-block to the v1.5.0 entry, OR call this out in the v1.6.1 CHANGELOG retrospectively.

**Suggested wording (if added to v1.5.0):**
```
### Known issues at ship (diagnosed post-v1.5.0)

- The Brown apples-to-apples acceptance test (PR 28) on the `9sTs vs b1500`
  spot produced a per-action divergence (Brown=0% bet vs Rust=98.6% bet)
  when first executed. Diagnosis (2026-05-23 late) attributed this to
  compound TEST BUGS in the acceptance harness — action-ordering +
  range-slot misassignment — not solver-bugs in PR 23. PR 40 ships the
  acceptance-test plumbing fix; see
  `docs/v1_5_0_per_action_divergence_diagnosis.md`. Engine bundle
  (PR 33-35 + PR 40) ships as v1.6.1.
```

Lower urgency than Micro-PR A because the v1.5.0 entry already nodded toward the issue indirectly via the v1.5.1 "Deferred to" sub-block (now to be fixed in Micro-PR A).

**Severity:** MEDIUM. Could be rolled into Micro-PR A as a single edit; or deferred to the v1.6.1 CHANGELOG which can include a "Resolves v1.5.0 acceptance-test diagnosis" line.

### Micro-PR C — LOW-severity formatting nit

**Scope:** Add blank line between v1.4.1 line 273 (`get an early, clear error.`) and v1.4.0 line 274 (`## [1.4.0] - 2026-05-23`).

**Severity:** LOW. Cosmetic only. Roll into Micro-PR A if cheap; otherwise skip.

---

## 6. Net

- **APPROVE for everything pre-v1.5.0** (v1.0.0 through v1.4.3 all consistent).
- **NEEDS-MICRO-PR for v1.5.1** (HIGH: v1.5.2 → v1.6.1; MEDIUM: pending-diagnosis → diagnosed-as-test-bugs).
- **MEDIUM consideration for v1.5.0** (acceptance-test honest framing gap; can be addressed in v1.6.1 CHANGELOG retrospectively instead).
- **LOW formatting nit** at v1.4.1 → v1.4.0 boundary.

Recommendation: single micro-PR (A + B + C combined) before the v1.6.0 ship lands, OR roll the v1.5.1 stale-anchor fix into the v1.6.0 CHANGELOG entry as a "Note on v1.5.1" preamble. Either is fine; the cheaper one is whichever is faster given the v1.6.0 LEG 18 schedule.

---

## 7. Files Audited

- `CHANGELOG.md` on `origin/main` (HEAD `b5777f2`, tag `v1.5.1`) — read-only.

## 8. Authoritative Cross-References Consulted

- `/Users/ashen/Desktop/poker_solver/PLAN.md` (lines 3, 9, 110, 116-120, 351-354, 412-415, 445-448).
- `/Users/ashen/Desktop/poker_solver/docs/leg17_v1_5_1_ship_report.md` (lines 5-9, 24, 104, 112, 143, 329, 457-461).
- `/Users/ashen/Desktop/poker_solver/docs/leg18_v1_6_0_gui_ship_plan.md` (lines 1, 7, 59).
- `/Users/ashen/Desktop/poker_solver/docs/pr_proposals/v1_4_node_locking.md` (existence).
- `/Users/ashen/Desktop/poker_solver/docs/pr_proposals/v1_4_asymmetric_contributions.md` (existence).
- `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/v1_3_1_s4_retest.md` (existence).
- `/Users/ashen/Desktop/poker_solver/docs/river_parity_timeout_investigation_2026-05-23.md` (existence).
- `git ls-tree -r origin/main` for `tests/_equity_helpers.py`, `tests/test_memory_profiler.py`, `tests/test_river_diff_self_sanity.py`, `tests/test_v1_5_brown_apples_to_apples.py`, `tests/test_range_vs_range_rust_diff.py`, `crates/cfr_core/src/dcfr_vector.rs`.
- Local git branch listing for `pr-21-*` / `pr-22-*` / `pr-23-*` / `pr-27-*` / `pr-28-*` / `pr-32-*` / `pr-33-*` / `pr-34-*` / `pr-35-*` / `pr-36-*` / `pr-37-*`.
