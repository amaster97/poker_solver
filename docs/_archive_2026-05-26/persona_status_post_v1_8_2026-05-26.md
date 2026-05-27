# Persona Test Status — Post-v1.8 Audit, 2026-05-26

**Mode:** read-only desk audit per `feedback_post_ship_persona_retest`.
**Source snapshot:** `docs/persona_test_status_2026-05-25.md` (landed PR #40).
**v1.8 landing:** PRs #41 (Phase 2 `update_regret_sum`), #33 (Phase 3 `update_strategy_sum`), #32 (Phase 4 `compute_strategy`), #35 (AVX2 runtime-detect). All four phases on `main`.
**Also landed since 2026-05-25 snapshot:** PR #38 = PR 76 Stage A (`solve_best_response` API + CLI subcommand).

---

## 1. Current counts (as of 2026-05-26 morning)

| Verdict | Count | Workflows |
|---|---|---|
| **PASS** | 7 | W1.1, W1.2, W1.3, W1.4, W2.5, W3.1, W4.1, W4.3 *(W4.3 via aggregator path)* |
| **PARTIAL** | 5 | W1.5, W2.1, W2.2, W2.4, W3.3, W4.2 |
| **BLOCKED** | 4 | W2.3, W3.2, W3.4 |
| **FAIL** | 2 | W3.5 *(Type B wrapper — v1.7.1 bundle in flight)* |

**These counts are UNCHANGED from the 2026-05-25 snapshot.** No persona retest result documents have landed since the snapshot. Two pre-staged retest prompts (`post_v1_8_0_W2_3_retest_prompt.md`, `post_v1_8_0_W3_4_retest_prompt.md`) exist but have not been executed.

> **NOTE on user-supplied count.** The task brief cited "4 PARTIAL / 2 BLOCKED." Actual snapshot is **5 PARTIAL / 4 BLOCKED / 1 FAIL (W3.5)**. The corrected counts are used below.

---

## 2. Was the post-v1.8 mandatory persona retest triggered?

**No.** Per `feedback_post_ship_persona_retest`: wrappers should be retested at production scale (≥10-class RvR) after wrapper-touching ships. v1.8 SIMD touches the inner CFR vector-form kernel — exactly the path that gates W2.3 / W3.4 / W2.1 / W2.4.

**Status:** the mandatory retest is OWED. Pre-staged retest prompts exist in `docs/persona_test_results/post_v1_8_0_W2_3_retest_prompt.md` and `.../post_v1_8_0_W3_4_retest_prompt.md`, both dated 2026-05-25 and gated on "v1.8.0 lands on origin/main." That precondition is now met (PRs #41 + #33 + #32 + #35 all merged). The retests have not been fired.

---

## 3. Critical empirical update: v1.8 SIMD did NOT deliver projected speedup

**`docs/v1_8_simd_perf_benchmark_2026-05-26.md` (today's bench) reports:**

| Workload | v1.7.0 | post-Phase-3 main | Ratio |
|---|---|---|---|
| River RvR, 1081 hands, 3 actions, 5 iter | 936 ms/iter | 942 ms/iter | **0.99×** |
| River RvR, 1081 hands, 5 actions, 5 iter | 4,777 ms/iter | 4,723 ms/iter | **1.01×** |

**Speedup on M4 Pro arm64 is within noise (~1.0×).** The release-notes draft's 4-8× projection has been measurably refuted on the workloads tested.

**Root cause (per bench report §Kernel-level microbench):** LLVM `-O3` already autovectorizes the small-slice scalar loops (action_count = 3-5 means 3-5 f64 slices, well below SIMD break-even). Hand-written intrinsics pay dispatch overhead that cancels the kernel-level win.

**Impact on persona projections:** the 2026-05-25 snapshot projected W2.3 / W3.4 / W2.1 from BLOCKED→PASS via "v1.8 SIMD 4-8×." That projection is now **EMPIRICALLY REFUTED on M4 Pro arm64**. Phase 4 (`compute_strategy`) is on main per PR #32, but the bench report notes Phase 4 was not yet measured at bench time; given the slice-width root cause, Phase 4 is unlikely to flip the result.

**Per `feedback_post_ship_persona_retest` + `feedback_empirical_over_audit`:** the retest should still fire to obtain the empirical wall-clock on the actual persona fixtures (turn / flop RvR Nash at 200 BB), not just the river micro-bench. But the projection that W2.3 / W3.4 will reclassify to PASS post-v1.8 is no longer load-bearing.

---

## 4. Per-PARTIAL / per-BLOCKED workflow status

### PARTIAL (5)

#### W1.5 — Marcus, "Why does 76s fold at 10 BB?"
- **Blocker:** `return_ev=True` decomposition not implemented; chart values are correct, only EV-breakdown explainer is missing.
- **v1.8 impact:** none (chart lookup is already <500 ms; SIMD does not touch pushfold path).
- **Recommendation:** **DEFER**. Classified Type C-NICE per snapshot. Not unblocked by v1.8 or PR 76.

#### W2.1 — Sarah, "Generate HU 100 BB preflop range chart"
- **Blocker:** Full flop fixture timed out at 21 min on v1.7.0 (`W2_1_post_v1_7_0_result.md`). River envelope (smaller fixture) PASSED in 31.7 s.
- **v1.8 impact:** Projection was "SIMD brings flop into Sarah ≤5 min budget." **Refuted by bench**. The flop multi-street perf ceiling is the dominant cost; SIMD does not help.
- **Recommendation:** **RETEST at low priority** to obtain the actual post-v1.8 wall-clock on the flop fixture — needed to update the snapshot's projection. **Expected outcome: still PARTIAL on flop, PASS on river envelope** (unchanged). Priority: P3.

#### W2.2 — Sarah, "Diff my BB 3-bet range vs GTO"
- **Blocker:** `Range.diff()` exists at set-membership level (PR 27); per-combo frequency representation requires B10 (Range fractional refactor — deferred to v1.5+).
- **v1.8 impact:** none (structural, not perf).
- **PR 76 impact:** none.
- **Recommendation:** **DEFER**. Awaits B10 (spec landed in PR #36 `9dbe7ff`; implementation not started).

#### W2.4 — Sarah, "Verify batch-solve CSV schema"
- **Blocker:** Library-direct path PASS (3/3 round-trip <10 ms); CLI `batch-solve` path INCONCLUSIVE-SLOW at river even with 1-row 1-iter probe.
- **v1.8 impact:** projected as v1.8 SIMD candidate per snapshot — **refuted by bench**.
- **Recommendation:** **RETEST at low priority** to confirm whether the slow path is the SIMD-touched vector-form CFR (refuted) or a different bottleneck (untested). If different, log as a separate perf finding. Priority: P3.

#### W3.3 — Daniel, "Merged-strategy range; GTO response"
- **Blocker:** Node-locking infrastructure exists (PR 24b in v1.6.0); specific merged-range workflow has no standalone retest doc.
- **v1.8 impact:** unclear — depends whether merged-range solve hits the vector-form CFR perf wall.
- **Recommendation:** **RETEST at medium priority** as a cheap closing test (node-locking shipped 2+ minor releases ago; this is overdue regardless of v1.8). Priority: P2.

#### W4.2 — Priya, "Custom limp-or-fold action menu"
- **Blocker:** Wiring + action restriction PASS; heuristic criteria mis-aligned with subgame mode (Type A docs).
- **v1.8 impact:** none (structural, not perf).
- **Recommendation:** **DEFER**. Pending DEVELOPER.md doc add (no PR open).

---

### BLOCKED (4 — note: snapshot table says 4, prose says 3; reconciled as 4 here)

#### W2.3 — Sarah, "Solve KK on Q-high flop vs c-bet range" (RvR postflop, 200 BB deep)
- **Blocker:** 4-class iter=100 flop aggregator >300 s on 200 BB deep stack.
- **v1.8 impact:** projection was 75-150 s on M-series — **refuted by bench**. Pre-staged retest exists but expects PASS based on the now-refuted projection.
- **PR 76 impact:** none.
- **Recommendation:** **RETEST at HIGH priority**. The pre-staged turn fixture (not flop — `post_v1_8_0_W2_3_retest_prompt.md` line 15) should fire to obtain ground-truth wall-clock. **Expected verdict per bench refutation: Type D timeout. Surfaces "v1.8 W2.3 unblock claim NOT delivered" per the prompt's pre-staging notes line 117-118.** This is a release-narrative-revision trigger — high priority. Priority: **P1**.

#### W3.2 — Daniel, "Compare GTO vs villain actuals; exploitative response"
- **Blocker per snapshot:** `best_response(game, fixed_strategy, player)` public API not exposed.
- **v1.8 impact:** none.
- **PR 76 impact (NEW)**: **THIS BLOCKER IS RESOLVED.** PR #38 (commit `feee974`, 2026-05-26) shipped `solve_best_response(game, opponent_strategy, *, hero_player)` at `poker_solver/solver.py:442` + CLI `poker-solver best-response` subcommand. See `poker_solver/solver.py` lines 442+ and `cli.py:174,1438`.
- **Recommendation:** **RETEST at HIGH priority**. The blocker named in the snapshot is now demonstrably shipped. **Expected outcome: BLOCKED → PASS** (assuming the spec workflow can be expressed in terms of `solve_best_response` + a fixed villain strategy file). Priority: **P1**.

#### W3.4 — Daniel, "MDF check vs half-pot c-bet" — BB defend ≥ MDF
- **Blocker:** Same perf wall as W2.3 (4-class iter=100 100 BB flop >300 s).
- **v1.8 impact:** projected 60-90 s on M-series — **refuted by bench**.
- **Recommendation:** **RETEST at HIGH priority** for the same reason as W2.3. The pre-staged retest (`post_v1_8_0_W3_4_retest_prompt.md`) is on a monotone river 3-bet pot fixture, which is smaller than the original W3.4 flop scope; that smaller scope may PASS even without the SIMD speedup, but the per-bench acceptance criterion of ≤5 min wall-clock should be measured rather than assumed. Priority: **P1**.

#### W4.3 — Priya, "Diff our solver vs Brown on novel river spot" (strict path)
- **Blocker:** Strict `tests/test_river_diff.py` path is canonical-parity timeout. Aggregator path PASSes (already in PASS count via aggregator).
- **v1.8 impact:** none meaningful (Brown parity is a separate code path).
- **Recommendation:** **DEFER**. Strict path is test-coupled, not user-facing. Priority: P4.

---

### FAIL (1)

#### W3.5 — Daniel, "Monotone-board polarization"
- **Blocker:** Type B wrapper bug; v1.7.1 ship in flight (PRs 50/51/52/54/55/56/53b/53c/59/60).
- **Status update:** Per `git log`, PR 53b (`0aec0a7`), PR 53c (`49c1421`), PR 9/10/12 (PR 50, 55, 56) have all merged. PR 51 (`dcfr_vector.rs:651` panic fix) status TBD from log alone. Most of the v1.7.1 bundle has landed.
- **v1.8 impact:** none directly (wrapper path, not SIMD).
- **Recommendation:** **RETEST at HIGH priority** once final v1.7.1 component lands. Per `feedback_post_ship_persona_retest`, wrapper bug fix is the highest-priority retest class. Priority: **P1**.

---

## 5. Marcus 30-s tolerance — v1.8 perf check

Per `feedback_persona_time_budgets` (`docs/pr13_prep/persona_time_budgets.md:43-52`):

- Marcus's <30 s gate applies to **single-spot interactive solves**.
- W1.1-W1.4 PASS already (W1.1 lookup ≈5.5 ms; W1.2 Nash 9.19 s; W1.3 0.30 s; W1.4 per-class subgame within budget).
- v1.8 SIMD bench refutation means **no expected acceleration of Marcus workflows**.
- Marcus is **not on the BLOCKED list** — all Marcus blockers are Type C-NICE (W1.5) or structural (none).
- **No retest is needed to re-validate Marcus's <30 s budget**, because v1.8 does not move his numbers (bench shows ~1.0×). The previously-PASSING Marcus workflows remain at the same wall-clock.

**Net for Marcus:** no v1.8 unblock benefit; no v1.8 regression risk; no retest gain. **DEFER all Marcus retests** — they were already PASS, and v1.8 didn't change them.

---

## 6. Recommended retest list (priority-ordered)

| Priority | Workflow | Rationale | Expected outcome |
|---|---|---|---|
| **P1** | **W3.2** | PR 76 ships the named blocker. Easy PASS confirmation. | BLOCKED → PASS |
| **P1** | **W2.3** (turn fixture per pre-stage) | v1.8 SIMD claim is empirically refuted on micro-bench; need ground-truth wall-clock on production-scale RvR Nash. Release-narrative impact. | Likely Type D timeout; surfaces narrative-revision trigger |
| **P1** | **W3.4** (monotone river 3-bet pot per pre-stage) | Same as W2.3; smaller fixture may PASS even without SIMD speedup. | Uncertain — measure |
| **P1** | **W3.5** | Wrapper fix retest per `feedback_post_ship_persona_retest`; v1.7.1 bundle mostly landed. | FAIL → PASS expected |
| **P2** | **W3.3** | Overdue closing test for node-locking-at-scale (v1.4.0 feature). | Likely PARTIAL → PASS or PARTIAL → BLOCKED-on-perf |
| **P3** | **W2.1** | Update flop-fixture wall-clock for snapshot accuracy. | Still PARTIAL expected |
| **P3** | **W2.4** | CLI batch-solve perf characterization. | Still PARTIAL expected |
| **P4** | **W4.3 strict path** | Test-coupled; not user-facing. | Still BLOCKED |
| **DEFER** | W1.5, W2.2, W4.2 | Structural / Type C-NICE / pending B10. No retest signal post-v1.8. | n/a |

---

## 7. Counts after recommended retests (projected)

If P1-P2 retests fire and produce expected outcomes:

| Verdict | Projected Count | Delta vs 2026-05-25 |
|---|---|---|
| PASS | 9-10 | +2-3 (W3.2 confirmed, W3.5 if v1.7.1 lands, W3.3 if perf OK) |
| PARTIAL | 5-6 | -0 to +1 (W3.3 could go either way) |
| BLOCKED | 2-3 | -1 to -2 (W3.2 closes; W2.3 + W3.4 likely remain) |
| FAIL | 0 | -1 (W3.5 retest, conditional on v1.7.1 close) |

**Key delta: v1.8 SIMD does NOT structurally unblock the perf-bound BLOCKED workflows (W2.3, W3.4) on M-series.** The headline projection from the 2026-05-25 snapshot ("v1.8 SIMD candidate" for W2.3 / W3.4) is refuted by empirical bench. Those will likely remain BLOCKED until v1.9 EMD bucketing (per `v1_8_decision_brief.md:26`) or until x86_64 AVX2 measurement reveals a different perf profile on that target.

---

## 8. Audit findings / action items

1. **Mandatory post-v1.8 persona retest is OWED but not fired.** Per `feedback_post_ship_persona_retest`, this should be triggered. Pre-staged prompts exist; only requires execution.
2. **v1.8 release-notes draft (`v1_8_0_release_notes_DRAFT.md`) currently claims 4-8× speedup; bench refutes.** Per `feedback_no_extrapolate`, the release narrative needs revision before v1.8.0 tag. The bench report (`v1_8_simd_perf_benchmark_2026-05-26.md`) already recommends specific replacement language.
3. **PR 76 (best-response) closes W3.2 blocker but has no retest doc.** Per `feedback_persona_test_rectification`, the loop should close with a W3.2 retest result document. Currently absent.
4. **2026-05-25 snapshot table says 4 BLOCKED, prose lists 3.** Minor count inconsistency in the source doc.
5. **The snapshot's "Projected end-state: 16-18 / 18 PASS after v1.8 SIMD + v1.7.1 + B10" is now too optimistic** for the v1.8 portion. Adjusted projection: 9-10 PASS post-recommended-retests, 16-18 PASS only realistic after v1.9 (EMD bucketing) or after acceptance-reframe for perf-bound workflows.

---

## 9. References (absolute paths)

- Source snapshot: `/Users/ashen/Desktop/poker_solver/docs/persona_test_status_2026-05-25.md`
- Rectification framework: `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/rectification_framework.md`
- Time budgets: `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/persona_time_budgets.md`
- v1.8 SIMD bench (load-bearing for §3): `/Users/ashen/Desktop/poker_solver/docs/v1_8_simd_perf_benchmark_2026-05-26.md`
- v1.8 decision brief: `/Users/ashen/Desktop/poker_solver/docs/v1_8_decision_brief.md`
- Pre-staged retests:
  - `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/post_v1_8_0_W2_3_retest_prompt.md`
  - `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/post_v1_8_0_W3_4_retest_prompt.md`
- Best-response API (W3.2 unblock): `/Users/ashen/Desktop/poker_solver/poker_solver/solver.py:442` + `cli.py:1438`
- PR 76 commit: `feee974` (merged 2026-05-26 via #38)
- v1.8 phase commits: `8073bcc` (#41 Phase 2), `a712950` (#33 Phase 3), `77e751c` (#32 Phase 4), `db8d646` (#35 AVX2)
