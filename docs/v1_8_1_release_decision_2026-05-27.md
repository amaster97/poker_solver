# v1.8.1 Release Decision — 2026-05-27

**Status:** v1.8.0 SHIPPED at commit `8a9c8d2` (tag object `5888cb5`) on 2026-05-27 09:18 UTC. v1.8.1 candidate fixes are accumulating from the post-burst audit + perpetual-QA iter 6 retry. This doc is the single place to decide what's in v1.8.1, what's deferred, and what's deferred-forever.

**Main HEAD at write time:** `9213085` (`docs(v1.8.1): fix release-notes broken refs + PR #93 collision + silent-skip hazard (#96)`).

---

## TL;DR — recommendation

**Ship v1.8.1 NOW as a doc/test-hygiene patch.** The 3 PR-merged fixes since v1.8.0 (#91 / #95 / #96) are already on main and address every HIGH finding from `docs/post_burst_audit_2026-05-27.md`. The two remaining HIGH findings (DCFR α=0 silent non-Nash, vector-form Rust RvR perf wall) are real engine-binding issues but **do not affect production users** — PLAN-locked production uses α=1.5, and the vector-form is documented as a v1.5.0 production-solve path, not an interactive-test path. Both can ship as v1.8.2 once a code fix or docs update is ready, without holding v1.8.1.

One-line rationale: **v1.8.1 is the credibility-of-release-page patch; HIGH-1/HIGH-2 are bind-boundary footguns that need their own decision cycle and shouldn't gate the doc-trail fix.**

---

## Already landed on main (DONE — would be in v1.8.1 automatically)

- [x] **PR #91** (`23f8966`) — `fix(tests): update Brown dump literals + chance_enum hole_cards post PR #69 + #78`. Cleans up two test-side stragglers from PR #69 (hard-fail on missing `initial_hole_cards`) + PR #78 (TerminalUtilityConvention purge). No runtime impact; tests only.
- [x] **PR #95** (`cdb1c47`) — `fix(build): resolve APP_PATH to absolute before defaults read`. Patches `scripts/build_macos_dmg.sh:257` relative-path silent-fail when `APP_PATH` is relative and `OUTPUT_DIR` defaulted from it. Source: noted in `docs/WAKEUP_2026-05-27.md` carry-items.
- [x] **PR #96** (`9213085`) — `docs(v1.8.1): fix release-notes broken refs + PR #93 collision + silent-skip hazard`. Addresses ALL HIGH findings from `docs/post_burst_audit_2026-05-27.md` + `docs/v1_8_1_candidate_doc_overclaims.md`:
  - 4 broken release-notes doc refs (`v1_5_brown_post_purge_numbers_2026-05-27.md`, `ev_invariance_sanity_gauntlet_design_2026-05-27.md`, `a83_terminal_utility_ablation_results_2026-05-26.md`, `terminal_utility_canonical_2026-05-27.md`) — files added to git (verified via `git ls-tree -r main --name-only | grep ...`).
  - PR #93 naming collision (5 release-notes refs to "PR #93" that mismapped to the WAKEUP doc instead of the local ablation branch `pr-93-terminal-utility-ablation` @ `986f48d`).
  - 2 silent-skip test files (`tests/test_minimal_nash_fixture.py`, `tests/test_aa_vs_aa_root_indifference.py`) added to git so the skip-ban CI guard + persona retest doc no longer reference untracked files.

**Status:** v1.8.1 already has 3 PRs of content. If we tag now, those land in users' hands as v1.8.1.

---

## Pending YOUR decision (HIGH severity, blocks v1.8.1 timing)

### HIGH-1 — DCFR α=0 silently produces non-Nash strategy (`#38` per local convention)

**Source:** `docs/perpetual_qa_findings_2026-05-27.md` iter 6 retry §"HIGH" + iter 6 retry test 3 (`iter6_retry_dcfr_alpha_zero`).

**Observed:** With `_rust.solve_kuhn(50_000, 0.0, 0.0, 2.0)` (i.e., α=0), exploitability is FLAT across iter (8.57e-2 @ 1k → 8.36e-2 @ 50k) vs α=1.5's standard 3.6× drop (4.60e-3 @ 1k → 1.27e-3 @ 10k). Game value lands at −0.093 BB instead of the correct ~−0.056 BB. Max strategy-cell diff vs α=1.5 @ 10k iter = **0.411**.

**Root cause** (`crates/cfr_core/src/dcfr.rs:171-173`): at α=0, `pos_scale = t^0 / (t^0 + 1) = 1/2` for ALL t, so positive regrets are halved every iter regardless of `t`. This is a degenerate DCFR config (NOT vanilla CFR despite surface intuition). The Rust binding accepts α=0 without warning.

**Impact:** Users following the "α=0 disables positive-regret discount" intuition (true for some CFR variants) will silently get a much worse strategy. **Production is NOT affected** — PLAN-locked default α=1.5 is what `solve_hunl_postflop`, `solve_kuhn`, and `solve_range_vs_range_rust` use by default.

**Options:**
1. **Reject α=0 at the binding boundary** (`crates/cfr_core/src/dcfr.rs` constructor; raise on `alpha <= 0.0` or `alpha < epsilon`). Code fix. v1.8.1 scope if pushed.
2. **Document the hazard** in the binding docstring + PLAN.md. Docs only. v1.8.1 scope.
3. **Hybrid** — both reject AND document.

**Status:** No proposal doc filed yet (`docs/dcfr_alpha_guard_proposal_2026-05-27.md` does not exist; the task brief mentions an in-flight agent but no artifact has landed). Branch `proposal/dcfr-alpha-guard-2026-05-27` exists but currently carries unrelated persona-retest work.

**Recommendation:** Option 2 (docs-only) for v1.8.1; Option 1 (code reject) as a follow-up v1.8.2 with the constructor-validation pattern. Reasoning: v1.8.1 is already cued up as a docs-hygiene patch; bolting on a binding change increases blast radius. Code-fix in a dedicated PR with empirical Kuhn-convergence regression test.

---

### HIGH-2 — Vector-form Rust RvR perf wall on river (`#39` per local convention)

**Source:** `docs/perpetual_qa_findings_2026-05-27.md` iter 6 retry test 4 (`iter6_retry_rvr_rust_diff`) — FAIL.

**Observed:** `_rust.solve_range_vs_range_rust` on a 5-card river fixture (AhTcTh4d9s, `initial_hole_cards=()`, pot=400, stack=20BB):
- 200 iter: pegged 1 CPU at 100% for **>14 min** before manual SIGKILL.
- 20 iter: still running at 100% CPU after 5 min, manual SIGKILL.

**Root cause hypothesis:** per-iter cost dominated by enumerating ~1326² ≈ 1.76M hand pairs per decision node. Iter count is a small multiplier on top; per-iter cost is O(minutes) on a single thread.

**Impact:** The function works correctly per its docstring ("v1.5.0 scope: postflop only — Flop / Turn / River with the full 1326-collapsed-by-board hand vector per player"). It's just **not suitable for interactive use**. Production solve workflows that batch overnight on multi-core hardware are unaffected.

**Options:**
1. **Document the perf wall** in the binding docstring + add a `--max-iter` advisory in the CLI. Docs only.
2. **Optimize** the hand-pair enumeration (e.g., precompute board-conditional reach + cache; release GIL via `py.allow_threads`). Code fix; high cost; v1.9+ scope.
3. **Add a soft cap** at the binding level (e.g., reject iter > 100 with a warning that flags this as a long-run path). Code fix; small.

**No proposal doc filed** for HIGH-2.

**Recommendation:** Option 1 for v1.8.1 (docstring + persona-retest doc note). Option 2 belongs in the v1.9 NEON roadmap (`docs/v1_8_neon_implementation_roadmap.md` already addresses river-vector perf at the SIMD layer). Option 3 is opinionated and probably wrong — power users who want overnight 10k-iter runs would have to override.

---

### PR #89 — Brown C++ Ubuntu buildability (held for review)

**State:** OPEN, MERGEABLE. Golden File / Skip-Ban / Ship Dry-Run all SUCCESS.
**Diff scope:** build-time sed patch for `unordered_map` → `map` in Brown's `subgame_config.cpp` (GCC 11.4 incomplete-type rejection on Ubuntu).
**Impact:** Unblocks Brown C++ comparison baseline on Linux CI. Engine unchanged; only affects the optional Brown-comparison harness build.
**Recommendation:** Merge into v1.8.1. The Brown harness is referenced from `docs/v1_5_brown_post_purge_numbers_2026-05-27.md` (now tracked via PR #96), so closing the loop on cross-platform Brown build is a natural v1.8.1 docs-coherence move.

---

### GitHub release body amendment (deferred for user eyeball)

**State:** `gh release view v1.8.0 --json body` still has the original v1.8.0 release-notes text. PR #96 fixed the source-of-truth (`docs/v1_8_0_release_notes_DRAFT.md` in main), but the *published* release page on GitHub still has the original broken-ref + PR-#93-collision text from the tag.
**Options:**
1. `gh release edit v1.8.0 --notes-file docs/v1_8_0_release_notes_DRAFT.md` — refresh the published body in place. Caveat: the release body would diverge from the tag's `docs/v1_8_0_release_notes_DRAFT.md` if anyone clones at the `v1.8.0` tag (which still has the original).
2. Tag and publish v1.8.1 with a fresh release page that cites the corrected refs; leave v1.8.0's page as-is (an audit-trail of what shipped originally + the v1.8.1 follow-up).
3. Both — refresh v1.8.0's body AND tag v1.8.1.

**Recommendation:** Option 2. Per `docs/v1_8_1_candidate_doc_overclaims.md:185-186`, this was the cleanest path the audit recommended ("OR tag v1.8.1 and publish a new release"). It also avoids the "edit-the-history" surprise for any external reviewer who looked at v1.8.0 mid-cycle. User wanted to eyeball — flag this section for the eyeball pass before clicking Edit on the GitHub release page.

---

## Hygiene tasks (user can do anytime, NOT v1.8.1 blocking)

- [ ] **Persona spec W3.5 update** (`docs/pr13_prep/persona_acceptance_spec.md` §2 W3.5): clarify that `AA check ≥ 0.99` applies to the PoC's explicit-no-flush-combo setup; class-name API setups including flush combos (e.g., `AKs`, `KQs`, `JTs`, `98s`, `87s`) get a different-but-correct Nash where `AA check ≥ 0.50` is more appropriate. Source: `docs/persona_status_post_v1_8_0_shipped_2026-05-27.md` §"W3.5 monotone polarization — diagnosed as range-setup mismatch (not a code bug)". Diagnostic ruled out wrapper bug (PoC explicit-combo setup reproduces `AA check = 1.0000` bit-clean at v1.8.0).

- [ ] **PR #49** (`pr-92-resume-doc`) — RESUME doc, OPEN MERGEABLE. **Stale** — body says "TWO MAJOR FINDINGS that need user decision before v1.8.0 ships" but v1.8.0 shipped. Either refresh the body and merge as historical, or close. Source: `docs/post_burst_audit_2026-05-27.md` §5 Open PR sanity.

- [ ] **PR #94** (`docs/persona-post-v1-8-0-production-retest`) — production-scale persona retest doc. OPEN MERGEABLE. No regressions found; W3.5 reclassified as range-setup mismatch. Pure docs.

- [ ] **PR #20** (`pr-64-cross-platform-ci-matrix`) — cross-platform CI matrix. OPEN MERGEABLE. Soft dep on PR #89 (PR #89's Brown build should be merged first so the Ubuntu matrix exercise validates). Per `docs/post_burst_audit_2026-05-27.md` §5, "Ubuntu CI should still fail without it" — confirm matrix actually exercises Brown build before merging.

- [ ] **PR #97** (`analysis/pr-merge-2026-05-27`) — merge-order analysis doc. OPEN MERGEABLE. Pure docs; rationale for #89 → #20 → #49 → #94 order. Merge after the relevant PRs land (or close as superseded by this v1.8.1 decision doc).

---

## Not in v1.8.1 (deferred)

- **v1.8.0 .dmg upload** — user direction: build but not upload; user wants to eyeball locally first. Per `docs/WAKEUP_2026-05-27.md:56`, "you said 'literally last thing to do'". PR #95's build-script fix unblocks the build; the upload step is manual.
- **Tasks #31 (preflop chained orchestrator) + #32 (full-tree preflop RvR)** — multi-day v1.9+ scope per `docs/WAKEUP_2026-05-27.md:57`. Not v1.8.1.
- **`docs/a83_validation_2026-05-26.md` SUPERSEDED banner** (MEDIUM finding from `docs/post_burst_audit_2026-05-27.md` §3) — internal-only doc still actively claims "documented design divergence" without a banner. Add banner in a separate docs PR (not v1.8.1 blocking; matters only for future agents reading without context).
- **`docs/persona_test_status_2026-05-25.md:130` broken inbound ref to `docs/PAUSE_RESUME_2026-05-25.md`** (MEDIUM finding from `docs/post_burst_audit_2026-05-27.md` §2) — absolute path is broken regardless. Internal-only chain, not user-facing.

---

## Open PRs at write time (for context)

| PR | Title | State | Mergeable | Verdict for v1.8.1 |
|---|---|---|---|---|
| **#20** | feat(ci): cross-platform CI matrix for v1.8 prep | OPEN | MERGEABLE | Hygiene — merge after #89 |
| **#49** | docs: RESUME_2026-05-26 morning hand-off | OPEN | MERGEABLE | Hygiene — close or refresh |
| **#89** | fix(build): patch Brown's subgame_config.cpp for GCC 11 | OPEN | MERGEABLE | **In v1.8.1** (recommended) |
| **#94** | docs(persona): post-v1.8.0 production-scale retest | OPEN | MERGEABLE | Hygiene — docs-only |
| **#97** | docs: pre-flight merge-order analysis | OPEN | MERGEABLE | Hygiene — close as superseded by this doc |

---

## Decision matrix — what's in v1.8.1?

| Item | Recommendation | Blocking v1.8.1? |
|---|---|---|
| PR #91 (Brown dump test literals) | **IN** (already on main) | n/a |
| PR #95 (.dmg build script fix) | **IN** (already on main) | n/a |
| PR #96 (release-notes doc refs + collision + silent-skip) | **IN** (already on main) | n/a |
| PR #89 (Brown Ubuntu buildability) | **IN** (merge before tag) | Soft yes — recommended |
| HIGH-1 DCFR α=0 docs-only note | **IN** (docs-only, low risk) | No — could defer to v1.8.2 |
| HIGH-1 DCFR α=0 binding reject | **DEFER** to v1.8.2 (code change) | No |
| HIGH-2 RvR perf-wall docs-only note | **IN** (docs-only, low risk) | No — could defer to v1.8.2 |
| HIGH-2 RvR optimization | **DEFER** to v1.9 (NEON roadmap) | No |
| GitHub v1.8.0 release body amendment | **DEFER** — user eyeball first | No |
| v1.8.0 .dmg upload | **DEFER** — user manually uploads | No |
| Persona spec W3.5 clarification | **DEFER** (hygiene) | No |
| Tasks #31/#32 preflop orchestrator | **DEFER** to v1.9+ | No |

---

## Final recommendation

**Ship v1.8.1 immediately with:**
1. The 3 already-landed PRs (#91, #95, #96).
2. **PR #89 merged** before the tag (cross-platform Brown build).
3. **Two docs-only HIGH-finding notes** added in a single v1.8.1 PR:
   - DCFR α=0 hazard in `crates/cfr_core/src/dcfr.rs` docstring + `PLAN.md` §"DCFR hyperparameter constraints".
   - `solve_range_vs_range_rust` per-iter cost in the binding docstring + `docs/persona_test_results/` river-fixture note.

**Then:**
- Tag v1.8.1 and publish a fresh release page citing the corrected refs.
- Leave v1.8.0's published release body alone (the tag stays canonical for historical clones).
- Defer .dmg upload to user's manual step.
- Plan v1.8.2 for the DCFR α=0 binding-reject code fix + RvR perf-wall instrumentation, with empirical regression tests.

**Tracker count:**
- HIGH findings remaining (post-PR-96): **2** (both bind-boundary / docs-fixable; neither is a runtime-correctness issue for default config).
- v1.8.1 carry items: docs notes for HIGH-1/HIGH-2 + PR #89 merge.

---

## References

- `docs/post_burst_audit_2026-05-27.md` — read-only independent audit of v1.8.0 stability (TL;DR: STABLE, 24h docs patch warranted).
- `docs/v1_8_1_candidate_doc_overclaims.md` — repro steps for the 3 HIGH findings already fixed in PR #96.
- `docs/v1_8_1_candidate_findings_2026-05-27.md` — persona retest findings (none became v1.8.1 candidates; W3.5 diagnosed as range-setup mismatch).
- `docs/persona_status_post_v1_8_0_shipped_2026-05-27.md` — production-scale retest table; persona spec W3.5 update hygiene item.
- `docs/perpetual_qa_findings_2026-05-27.md` (iter 6 retry §HIGH lines 1646-1680) — HIGH-1 (DCFR α=0) + HIGH-2 (RvR perf wall) source-of-truth.
- `docs/WAKEUP_2026-05-27.md` (lines 35-41) — original capture of the two HIGH-finding decision points.
- v1.8.0 tag commit: `8a9c8d2`. Main HEAD at write time: `9213085`.

---

**Author:** v1.8.1 release-decision consolidation agent, 2026-05-27. Pure docs / decision-matrix; zero code or runtime impact.
