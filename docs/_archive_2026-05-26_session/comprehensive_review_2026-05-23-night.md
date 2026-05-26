# Comprehensive Consistency Review — 2026-05-23 (NIGHT)

**Companion to:** `comprehensive_review_2026-05-23-late.md` (historical snapshot). Re-issue captures v1.4.1 + v1.4.2 ships, 18-workflow persona battery, Brown apples-to-apples definitive finding, Phase 2b code-correctness audit, re-tag execution.

---

## 1. TL;DR

- **Where:** two further PATCH ships landed since LATE (v1.4.1, v1.4.2); two more pre-staged (v1.4.3 PATCH bundle; v1.5.0 PR 23 MINOR). Twelve tags on public origin, all clean.
- **Shipped:** v1.0.0 → v1.4.2 = 11 forward tags. 18-workflow persona battery retested against v1.4.1 / v1.4.0: Marcus 5/5 PASS; Sarah / Daniel / Priya mix of PASS / PARTIAL / BLOCKED; every non-PASS has a documented PASS-conversion path.
- **Gating burst close:** Strategic Brown parity (v1.5.0's load-bearing claim) requires PR 23 vector-form CFR + Brown apples-to-apples acceptance going green. Until then W2.3 / W3.4 / W4.3 stay PARTIAL / INCONCLUSIVE / BLOCKED.

---

## 2. Tag ladder (2026-05-23)

12 forward tags on public `origin/main`; all clean; all releases published.

| Tag | Commit | What |
|---|---|---|
| v1.0.1 | `373d35c` | PR 8 NEON SIMD + cache + PCS |
| v1.1.0 | `a335680` | PR 9 HUNL preflop subgame solver |
| v1.2.0 | `363b2bb` | PR 10b real-solver UI bindings |
| v1.2.1 | `41235d0` | universal2 `_rust.so` (PR 14) |
| v1.3.0 | `58b1ebd` | PR 16 RvR aggregator (Option B) |
| v1.3.1 | `88b7a1c` | PR 20 `hero_player` gap fix |
| v1.3.2 | `2758659` | PR 15 Rust expl walk |
| v1.4.0 | `166d2b8` | PR 21 node locking |
| **v1.4.1** | `89a124b` | PR 22 asymmetric contributions |
| **v1.4.2** | `d9094c2` | docs honesty + `@slow` marker |
| **v1.4.3** | READY | PR 27 `Range.diff()` + PR 29 spec + PR 30 docs + PR 31 `HUNLConfig` validation |
| **v1.5.0** | READY | PR 23 vector CFR + PR 28 Brown acceptance — true Nash RvR (postflop) |

Re-tag execution cleaned 5 dirty tags (v1.0.1 / v1.1.0 / v1.2.0 / v1.3.0 / v1.4.0) that pointed to integration-lineage commits with ~70k lines of internal planning. Public `origin/integration` was separately filter-repo cleaned.

---

## 3. 18-workflow persona status

### Per-cohort summary

| Cohort | PASS | PARTIAL | BLOCKED/INCONCLUSIVE |
|---|---|---|---|
| Marcus | 5/5 | 0 | 0 |
| Sarah | 1 (W2.5) | 3 (W2.1, W2.2, W2.4) | 1 (W2.3) |
| Daniel | 4 (W3.1/2/3/5) | 0 | 1 (W3.4) |
| Priya | 1 (W4.1) | 1 (W4.2) | 1 (W4.3) |
| **Total** | **11** | **4** | **3** |

### Per-workflow rows

| ID | Verdict | At |
|---|---|---|
| W1.1 push/fold 88 @ 9 BB | PASS | v1.4.1 |
| W1.2 JJ river vs pot | PASS engine; CLI gap | v1.4.1 |
| W1.3 equity AKs vs JJ | PASS (spec equity labels inverted — PR 29 fixes) | v1.4.1 |
| W1.4 100 BB SRP study | PASS (PR 9 + v1.2.1 arch fix) | v1.2.1 |
| W1.5 76s preflop @ 10 BB | PASS | v1.3.2 |
| W2.1 169-cell preflop chart | PARTIAL (scoped sweep PASS; full chart perf-budget) | v1.4.1 |
| W2.2 range diff vs GTO | PARTIAL (set-membership PASS via PR 27; #189 deferred) | PR 27 worktree |
| W2.3 KK on Q-high vs c-bet | INCONCLUSIVE-SLOW (PR 23 closes) | v1.4.1 |
| W2.4 batch-solve CSV | PARTIAL (library PASS; CLI INCONCLUSIVE-SLOW) | v1.4.1 |
| W2.5 30 BB SRP | PASS (scoped sweep) | v1.4.1 |
| W3.1 lock villain bluffs | PASS | v1.4.0 |
| W3.2 GTO vs actual freqs | PASS | v1.4.0 |
| W3.3 merged-range exploit | PASS | v1.4.0 |
| W3.4 MDF half-pot c-bet | INCONCLUSIVE-SLOW (engine fix OK per Phase 2b audit; perf cliff blocks) | v1.4.1 |
| W3.5 monotone polarization | PASS (value side observable) | v1.4.1 |
| W4.1 pandas round-trip | PASS | v1.4.0 |
| W4.2 limp-or-fold mode | PARTIAL (spec heuristic structural mismatch) | v1.4.0 |
| W4.3 novel-spot Brown diff | BLOCKED (Python chance-enum timeout; PR 23 fix) | v1.4.0 |

### PASS-conversion paths for non-PASS workflows

- **W2.1:** post-PR 23 (vector CFR makes 169-class sweep tractable). Not gating burst close.
- **W2.2:** task #189 (Range fractional-freq refactor). Post-v1.5; non-blocking.
- **W2.3:** PR 23 vector-form CFR — confirmed by Brown apples-to-apples experiment as the only path that produces a Brown-comparable RvR output.
- **W2.4 CLI batch-solve:** same RvR root cause as W2.3. Library path is PASS today.
- **W3.4:** Phase 2b audit measured MDF = 59.8% vs Janda 57.1% theoretical — code is correct; aggregator 100x perf regression (task #174 bisection in flight) blocks fire-and-forget retests.
- **W4.2:** spec heuristic mismatch (subgame-mode → equity-only driver). PR 29 reclasses to PARTIAL legitimately.
- **W4.3:** PR 23 + PR 25 commit 2 revert (pre-staged in v1.5.0 plan §2e) restores `initial_hole_cards=()` via Rust vector CFR. Closes BLOCKED → PASS.

---

## 4. Architectural correctness verdict

Three independent investigations converged: **v1.3.2 / v1.4.0 / v1.4.1 code is correct on every audited spot. The Brown divergence is a documented Option B aggregator approximation, not a bug.**

- **Phase 2b audit:** W2b.5 AA-vs-underpair aggregator is valid Nash (dead-money utility makes bet/check-down EV identical). W2b.2 KK-vs-QQ-trips: hand-derived 4.5% equity confirmed; aggregator `fold=0.311` is faithful 1-of-5-villains aggregation. W2b.1 MDF: v1.4.1 returns 59.8% defense vs Janda 57.1% (within 2.7 pp). Zero bug findings.
- **Brown apples-to-apples:** switching to apples-to-apples reveals real divergence (mean TV 0.47, max 1.00 across 8 hand classes) — but this is the documented Option B blueprint approximation, not a bug. PR 23 vector-form CFR is the only architectural fix.
- **River-parity timeout:** test was always slow; structurally infeasible at 2000 iter on `initial_hole_cards=()`. Not a regression.

PR 28 (Brown acceptance test using new `solve_range_vs_range_rust` PyO3 entry) is paste-ready; v1.5.0 plan §2e bundles a revert of PR 25 commit 2 (concrete hole cards) once vector CFR is live.

---

## 5. Open work tracked

| Item | Status | Target |
|---|---|---|
| **PR 23** (~984 LOC Rust vector CFR + trait extension + PyO3 entry) | IN FLIGHT (5 commits; rebase onto v1.4.2 recommended) | v1.5.0 |
| **PR 28** (Brown apples-to-apples acceptance test) | READY-TO-CHERRY-PICK | v1.5.0 |
| **DCFR 100x bisection** (task #174) | IN FLIGHT | post-v1.5.0 |
| **v1.4.3 bundle** (PR 27 + 29 + 30 + 31) | READY-TO-SHIP (waits on PR 31 audit-clear) | v1.4.3 |
| **Task #182** Python→Rust delegate | DEFERRED | v1.5.1 |
| **Range fractional-freq refactor** (#189) | DEFERRED | v1.5+ |
| **CLI ergonomics gaps** | DEFERRED | v1.5+ |
| **macOS .dmg rebuild** for v1.4.1+ | v1.4.0 .dmg live; v1.4.1+ pending PR 11 cycle | v1.5.x |

---

## 6. Honest gaps / known issues

1. **Strategic Brown parity:** LOAD-BEARING claim of v1.5.0. Needs PR 23 (vector CFR) + task #182 (Python delegate, v1.5.1). Architectural answer documented today; code path not yet on origin.
2. **DCFR 100x slowdown:** Phase 2b reproduced W2b.5 at 648s (vs 6.1s baseline). Bisection in flight (task #174); candidates: PR 22 over-shove refund, PR 21 lock dict.get, PR 15 Rust wiring.
3. **Library round-trip truncates `exploitability_history`:** documented gap in `W4_1_v1_4_0_retest.md`. Non-blocking.
4. **`--workers > 1` batch parallelism:** flag accepted, untested.
5. **CLI gaps:** `poker-solver pushfold` (W1.1), `river --hero --villain-range` (W1.2), `poker_solver.parity.diff_vs_noambrown` library wrapper (W4.3) all missing — user must use library path.
6. **Tier 1 docs:** USAGE.md / DEVELOPER.md / README.md stale to pre-v1.4. PR 30 closes (v1.4.3 bundle).
7. **Persona spec inaccuracies (7 items):** PR 29 closes (v1.4.3 bundle).

---

## 7. What "burst-close" looks like

Five gates per PLAN.md §10:

| Gate | State | ETA |
|---|---|---|
| Engine (Brown parity + true Nash RvR) | PR 23 in flight; PR 28 paste-ready; v1.5.0 staged | 50-90 min from PR 23 audit-clear (LEG 13 §8) |
| UI surface | PR 10b live since v1.2.0; v1.4.x features not yet UI-wired | post-v1.5.0 follow-up |
| Persona acceptance | 11/18 PASS, 4 PARTIAL, 3 BLOCKED; all have PASS-conversion paths | 4 retests post-v1.5.0 (~10-30 min each) |
| Production validation | Phase 2b cleared 3 spots; DCFR 100x bisection in flight | bisect ~1-3 hr |
| Packaging | v1.4.0 .dmg live; v1.4.1+ rebuild pending | next PR 11 cycle ~30 min |

Dominant uncertainty is PR 23 audit + post-ship retest wave; everything else is mechanical.

---

## 8. Drift findings

| Item | Status |
|---|---|
| PLAN.md pre-PR-15 | OPEN (continuous prune; rewrite before burst-close) |
| README.md version sticker | OPEN (post-PR 30 follow-up) |
| USAGE.md / DEVELOPER.md | CLOSED in PR 30 (v1.4.3 bundle) |
| `v1_3_*.md` design docs | OPEN (post-v1.5.0 single-source-of-truth pass) |
| `project_solver.md` v1.4.x bump | OPEN (continuous prune) |
| CHANGELOG hygiene | CLEAN through v1.4.2; v1.4.3 / v1.5.0 pre-drafted |
| Persona spec (7 items) | CLOSED in PR 29 (v1.4.3 bundle) |
| GH release pages (12 tags) | CONFIRMED CLEAN |
| `origin/integration` drift | RESOLVED via filter-repo clean |

**Verdict:** SHIPPING-ACCURATE INTERNALLY; Tier 1 docs close with v1.4.3. Post-v1.5.0 cleanup benefits from PR 23 landing first so Rust vector CFR is the canonical reference.

---

## Sources

Prior review: `docs/comprehensive_review_2026-05-23-late.md`. Ship reports: `docs/leg11_v1_4_1_ship_report.md`, `docs/leg12_v1_4_2_ship_report.md`. Pre-staged: `docs/leg14_v1_4_3_ship_plan.md`, `docs/leg13_v1_5_0_ship_plan.md`. Architectural: `docs/brown_apples_to_apples_2026-05-23.md`, `docs/river_parity_timeout_investigation_2026-05-23.md`, `docs/pr13_prep/v1_3_2_phase2b_audit.md`. Persona: all `docs/persona_test_results/W*_v1_4_*_retest.md` + `untested_workflow_readiness_audit.md`. State: `docs/state_verification_2026-05-23-late.md`, `docs/retag_execution_report_2026-05-23.md`, `docs/integration_cleanup_report_2026-05-23.md`.
