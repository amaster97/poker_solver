# Outstanding Queue — 2026-05-25

**Mode:** Read-only inventory sweep
**Scope:** Outstanding bugs + pending TaskList items + CHANGELOG/docs gaps
**Origin HEAD audited:** `0a0e885` (matches `STATUS_2026-05-25_post_matched_config.md` L79)

---

## Confirmed pending

| Item | Status | Priority | Blocker |
|---|---|---|---|
| **`dcfr_vector.rs:363` panic on asymmetric ranges** (Hero≠Villain combo counts) | OPEN on origin/main; **fix is PR #6 ("PR 51"), OPEN-MERGEABLE on GitHub** | HIGH for Nash-API users; LOW for aggregator-path users | Reproduces on `0a0e885`: `let mut next_reach = vec![0.0_f64; opp_hands];` followed by `for h in 0..opp_hands { next_reach[h] = reach_opp[h] * strategy[h * action_count + a]; }` where `strategy` is sized `player_hands * action_count`. When the **acting** player has fewer hands than the update player, indexing `strategy[h * action_count + a]` overruns. PR 51 changes both `opp_hands` → `player_hands` (see `78c7155`). Bundled into v1.7.1 (in flight). |
| **CHANGELOG.md L28 still says "deferred to v1.5.2"** (in v1.6.0 "Notes" section) | OPEN on origin/main | LOW (cosmetic) | Commit `94007ca` ("CHANGELOG fix") fixed the v1.5.1 entry's own reference but did NOT fix the v1.6.0 Notes section reference. Local copy and `git show origin/main:CHANGELOG.md` both contain it. |
| **USAGE.md L355 references `docs/pr16_prep/stress_test_results.md`** which does not exist on `origin/main` | OPEN on origin/main | LOW | Broken link; reachable from public-facing USAGE.md. Private-mirror-only doc. |
| **CHANGELOG.md cites ~14 docs that are private-mirror-only** (e.g. `docs/architecture.md`, `docs/leg9_v1_4_0_ship_plan.md`, `docs/pr3_prep/audit_report.md`, `docs/river_parity_timeout_investigation_2026-05-23.md`, `docs/v1_6_1_no_go_synthesis*`) | OPEN on origin/main | LOW (historical entries; public readers hit broken links) | All 14 confirmed absent via `git ls-tree -r origin/main`. Not regression from PR #4 — these orphan refs predate it. |
| **v1.7.1 ship not yet on origin/main** (7-PR bundle: PR 50, 51, 52, 53b, 54, 55, 56) | In flight (sister agent per L67 of `STATUS_2026-05-25_post_matched_config.md`) | HIGH | All 7 PRs MERGEABLE+CLEAN per `docs/v1_7_1_final_readiness.md` L34-46. Ship script needs PR 55-ext drop edit; user signon docs need refresh. |

---

## Resolved (mark completed in TaskList for next refresh)

| Task # | Resolution |
|---|---|
| **#179** ("River parity test fix (multi-option)") | **Subsumed.** Option 1 (`@pytest.mark.slow` marker) merged via PR 25 fix #1 (commit `e0c950f`, on origin/main). Option 2 (concrete hole cards in `_solve_with_our_engine`) merged on branch `pr-25-river-parity-test-fix` (`6bf8b9e`) but the **entire wrapper approach was superseded by `poker_solver/parity/noambrown_wrapper.py`** which is the basis for PR 50/52/55/56 in the v1.7.1 bundle. The original brittle `test_river_parity_vs_brown` chain no longer exists on origin/main (file removed; replaced by `test_river_diff.py` and the noambrown_wrapper-based acceptance harness). Close as **subsumed**. |
| **#223** ("v1.6.1 ship NO-GO: bundle still fails acceptance; bisection in flight") | **Architecturally resolved.** v1.6.1 ship was abandoned; replaced by (a) v1.7.0 engine-only ship (live, tag `v1.7.0`, commit `3843ce7`) which dropped PR 35's Fix C, and (b) v1.7.1 7-PR Hybrid-path bundle (in flight, sister agent). The original blocker — PR 33+34+35 bundle failing acceptance — was bisected to PR 35 Fix C per task #230 ("BISECTION DEFINITIVE: PR 23 has additional algorithmic bug at deep-cap; drop PR 35 from v1.6.1") and to the Brown-vs-our action-menu hypothesis (refuted by matched-config investigation, see `STATUS_2026-05-25_post_matched_config.md`). The v1.7.1 Hybrid path is the closure; matched-config confirmed it's not a kernel bug but Nash multiplicity. Close as **resolved via Hybrid path; v1.7.1 ship in flight**. |
| **#225** ("CHANGELOG fix: v1.5.1 entry references v1.5.2 but should be v1.6.1") | **Partially resolved + new instance found.** Commit `94007ca` (2026-05-23 16:14) fixed the v1.5.1 entry's own "v1.5.2 → v1.6.1" reference. **However**, the v1.6.0 entry's "Notes" section (CHANGELOG L28) still says "deferred to v1.5.2 pending per-action divergence diagnosis." Recommend: close #225 as scoped-resolved, open a small follow-up to flip L28 to either "v1.6.1 (then deferred again to v1.7.1)" or simply "deferred past v1.6.0; see v1.7.0/v1.7.1 entries." Listed above under Confirmed pending. |

---

## Genuinely backlog (v1.8+)

| Item | Spec |
|---|---|
| Task #167: **200K-iter production-scale HUNL validation (Gate 4)** | B6 in PLAN §11; 50K validation in flight (sister agent per L69 STATUS_2026-05-25); 200K queues on PASS. Records exploitability convergence curve. |
| Task #169: **All-18-workflow final sweep retest** | Gate 3 in PLAN §10; fires after persona-cascade trigger post-v1.7.1. Per L85 STATUS: 12 PASS / 4 PARTIAL / 2 BLOCKED today; PARTIAL/BLOCKED retest after v1.7.1 ships. |
| Task #170: **v-final .dmg ship + GitHub release with .dmg attached (Gate 5)** | B5 + Gate 5 in PLAN §10; latest .dmg is v1.6.0 (45 MB arm64). v-final dmg comes after v1.8+ features land. |
| Task #189: **Range fractional-frequency refactor** | W2.2 PARTIAL + PR 27 docstring callout; needs `Combo.weight: float` field + `AKo:0.25` parse syntax + weighted `Range.diff`. v1.5+ deferred; not a v1.7.x blocker. |
| **v1.8 NEON SIMD perf release** (per `docs/v1_8_decision_brief.md`) | YES/NO decision queued for user post-v1.7.1. Recommended HIGH. 7-12 dev-days. Unblocks Sarah's turn workflow (currently >10 min vs 5 min tolerance). |
| **v1.9 EMD bucketing (flop viability)** | Reference in v1.8 decision brief; out-of-scope for v1.8. |

---

## Notes on PR #4 (README cleanup, `cb59927`)

- PR #4 removed two broken README cross-refs: `docs/dmg_v1_4_0_smoke_verification.md` (replaced with pointer to `docs/dmg_install_guide.md` which exists) and `docs/v1_6_1_dryrun_verification.md` (deleted reference; surrounding text retained).
- **No README regression introduced.** Current README on origin/main only refs 2 docs paths (`docs/aggregator_vs_true_nash_explainer.md`, `docs/dmg_install_guide.md`), both extant.
- PR #4 did NOT touch USAGE.md or CHANGELOG.md. The 1 USAGE orphan ref + 14 CHANGELOG orphan refs are independent of PR #4 and were not introduced by it.

---

## Evidence cited

- `crates/cfr_core/src/dcfr_vector.rs:363` on `origin/main` (`git show origin/main:crates/cfr_core/src/dcfr_vector.rs | sed -n '355,375p'`)
- PR 51 fix at `78c7155` (`git show 78c7155 -- crates/cfr_core/src/dcfr_vector.rs`)
- PR #6 status: OPEN via `gh pr view 6 --repo amaster97/poker_solver`
- CHANGELOG L28 leftover: `git show origin/main:CHANGELOG.md | grep -n "v1.5.2"`
- USAGE orphan ref at L355: `git show origin/main:USAGE.md | grep -n "stress_test_results"`
- 14 CHANGELOG orphan refs verified via `git cat-file -e origin/main:<path>` per-file
- `94007ca` CHANGELOG fix: `git show 94007ca -- CHANGELOG.md`
- PR #4 (README cleanup) diff: `git show cb59927 -- README.md`
- Task JSON: `/Users/ashen/.claude/tasks/b82103c3-b1e7-41e1-82ec-3829d1b6ca54/{179,223,225,167,169,170,189}.json`
- v1.7.1 in-flight status: `docs/STATUS_2026-05-25_post_matched_config.md` L67-71
- v1.8 priority: `docs/v1_8_decision_brief.md` L36-41
