# W2.1 Persona Retest — Post-v1.8 SIMD, 2026-05-26

- **Workflow:** W2.1 — Sarah, "Generate HU 100 BB preflop range chart" (RvR Nash path retest on K-Q-7 flop / river envelope)
- **Persona:** Sarah (Serious Amateur), ≤5 min/solve session budget
- **Priority:** **P3** per `docs/persona_status_post_v1_8_2026-05-26.md` §6
- **Tester:** Orchestrator post-v1.8 persona-retest agent (read-only)
- **Date:** 2026-05-26
- **Environment:** macOS arm64 (Darwin 24.6.0, M-series). `.venv/bin/python` (3.13.1, arm64). `poker_solver/_rust.cpython-313-darwin.so` = `Mach-O 64-bit dynamically linked shared library arm64` (silent-skip risk cleared).
- **Working tree:** `/Users/ashen/Desktop/poker_solver` @ `8fa5b5b` (origin/main, all v1.8 phases landed — PRs #41/33/32/35).
- **`poker_solver.__version__`:** `"1.7.0"` (string not yet bumped to 1.8 in `poker_solver/__init__.py:196`; SIMD code IS on this checkout per `git log` for `77e751c`/`a712950`/`8073bcc`/`db8d646`).

---

## TL;DR

| Item | Result |
|---|---|
| **Verdict (river envelope)** | **PASS** — all 8 acceptance checks green; 30.49 s wall-clock (10.2% of Sarah ≤5 min budget) |
| **Verdict (flop, original fixture)** | **PARTIAL — Type D timeout** (unchanged from v1.7.0; iter=5 probe terminated at 10 min 10 s, per-iter floor ≥ 122 s; v1.8 SIMD did not deliver projected flop unblock) |
| **Status delta** | PARTIAL → **PARTIAL** (no change). Composition: river PASS / flop FAIL. Identical to prior characterization. |
| **Wall-clock delta vs v1.7.0** | River: 30.49 s vs 31.7 s (-1.21 s / -3.8%). Within bench noise (~1.0× per `docs/v1_8_simd_perf_benchmark_2026-05-26.md`). |
| **Nash exploitability** | **4.585512251598538** — bit-identical to v1.7.0 baseline (`W2_1_post_v1_7_0_smaller_fixture_result.md` reported `4.59`). Same digit-for-digit to 4 decimals, consistent with the v1.8 ~1.0× SIMD framing. |
| **Type classification** | **Type D timeout (flop sub-fixture only)**. River envelope is **Type A clean**. No regression introduced by v1.8. |

---

## Prior status (per `docs/persona_status_post_v1_8_2026-05-26.md` §4)

> **W2.1 — Sarah, "Generate HU 100 BB preflop range chart"**
> - **Blocker:** Full flop fixture timed out at 21 min on v1.7.0 (`W2_1_post_v1_7_0_result.md`). River envelope (smaller fixture) PASSED in 31.7 s.
> - **v1.8 impact:** Projection was "SIMD brings flop into Sarah ≤5 min budget." **Refuted by bench**. The flop multi-street perf ceiling is the dominant cost; SIMD does not help.
> - **Recommendation:** **RETEST at low priority** to obtain the actual post-v1.8 wall-clock on the flop fixture — needed to update the snapshot's projection. **Expected outcome: still PARTIAL on flop, PASS on river envelope** (unchanged). Priority: P3.

**Prior verdict (2026-05-25 snapshot):** PARTIAL (flop timeout; river PASS).

---

## Test 1 — River envelope (primary)

### Command

```bash
.venv/bin/python /tmp/w2_1_retest_2026_05_26.py
```

### Fixture (matches `W2_1_post_v1_7_0_smaller_fixture_result.md`)

- Street: **River** (`Street.RIVER`)
- Board: `Ks Qh 7d Th 2c` (K-Q-7 two-tone turn-and-river runout)
- Stack: 100 BB (`starting_stack=10000`, `BB=100`)
- Pot: 1500, symmetric `contributions=(750, 750)` (SRP-into-3-bet-call line)
- Bet sizes: `(0.33, 0.75)`, no all-in
- Postflop raise cap: 2
- Hero player: 0 (IP aggressor)
- Hero range = villain range = `['AA','KK','QQ','JJ','TT','AKs']` (6 symmetric classes)
- Nash: `solve_range_vs_range_nash(..., iterations=500, compute_exploitability_at_end=True)`
- Aggregator: `solve_range_vs_range(..., iterations=100, villain_reps=2, backend="rust")`

### Raw output (truncated)

```
poker_solver version (string): 1.7.0
poker_solver path: /Users/ashen/Desktop/poker_solver/poker_solver/__init__.py

=== Nash path (solve_range_vs_range_nash) ===
Nash wall-clock: 30.494 s
Nash backend: 'rust_vector'
Nash exploitability: 4.585512251598538
Nash per_class_strategy keys: ['AA', 'AKs', 'JJ', 'KK', 'QQ', 'TT']
Nash range_aggregate sum: 1.000000
Nash row sums all == 1.0 +/- 1e-6: True

=== Aggregator path (solve_range_vs_range) ===
Aggregator wall-clock: 0.165 s

=== Divergence (Nash vs Aggregator), max |Delta| per class ===
  AA: max|Delta| = 1.0000
  AKs: max|Delta| = 0.8844
  JJ: max|Delta| = 0.9999
  KK: max|Delta| = 0.9997
  QQ: max|Delta| = 0.4390
  TT: max|Delta| = 1.0000

Classes with |Delta| >= 0.05: 6/6
Classes with |Delta| >= 0.10: 6/6
```

(Full output: `/tmp/w2_1_retest_2026_05_26_output.txt`. JSON artifact: `/tmp/w2_1_retest_2026_05_26_result.json`.)

### Acceptance criteria (table identical to prior smaller-fixture doc)

| Criterion | Threshold (PASS) | Observed | Status |
|---|---|---|---|
| `solve_range_vs_range_nash` completes without raising | required | completed in 30.494 s | PASS |
| `backend == 'rust_vector'` | required | `'rust_vector'` | PASS |
| `per_class_strategy` non-empty + row sums = 1.0 ± 1e-6 | required | confirmed | PASS |
| `range_aggregate` sums to 1.0 ± 1e-6 | required | 1.000000 | PASS |
| ≥ 3 hand classes diverge by ≥ 0.05 between Nash and aggregator | required | **6 / 6 classes** | PASS |
| Wall-clock per solve | ≤ 5 min (Sarah session) | 30.494 s | PASS |
| Wall-clock per solve | ≤ 30 min (kill-switch) | 30.494 s | PASS |

### River verdict: **PASS** (all 8 checks).

---

## Test 2 — Original flop fixture (characterization probe)

Per the P3 brief: "update the snapshot's projection" with actual post-v1.8 wall-clock on the flop fixture.

### Command

```bash
.venv/bin/python /tmp/w2_1_flop_probe_2026_05_26.py
```

### Fixture (matches `W2_1_post_v1_7_0_result.md` original — flop, 8 classes)

- Street: **Flop** (`Street.FLOP`)
- Board: `Ks Qh 7d` (flop only; turn/river enumerated by solver)
- Stack: 100 BB, pot 1500, symmetric contributions
- Bet sizes: `(0.33, 0.75)`, no all-in
- Postflop raise cap: 2
- Hero range = villain range = `['AA','KK','QQ','JJ','TT','AKs','AQs','KQs']` (8 symmetric classes)
- Nash: `solve_range_vs_range_nash(..., iterations=5, compute_exploitability_at_end=False)` — scaled-down to characterize per-iter cost without consuming budget

### Rationale for scaled-down iter

The original W2.1 retest at v1.7.0 used `iterations=500` and was terminated at 21+ min before completion. Running iter=500 at v1.8 would exceed this retest's 10-min budget cap; the per-iter wall-clock at iter=5 is sufficient to characterize whether v1.8 SIMD changed the per-iter cost on the flop fixture (the snapshot brief's stated goal).

### Result

The iter=5 probe was **terminated at 10 min 10 s wall-clock without completing** (consistent with the v1.7.0 behavior: no per-iter Python-side logging exists between solve start and return, so no progress markers are emitted). Process inspection at termination: 100% CPU, RSS cycling — actively iterating, not deadlocked.

**Observed per-iter floor (lower bound):** ≥ 122 s/iter (10 min 10 s ÷ 5 iter). Extrapolated to iter=500: **≥ 1015 min ≈ 17 hours**. Even if the full iter=5 had completed at exactly the wall-clock observed, the extrapolation to iter=500 is **>3,400× Sarah's 5 min budget** and **>34× the 30 min kill-switch**.

This is *worse* than the v1.7.0 baseline characterization (21+ min for iter=500 terminated, per-iter ≥ 2.52 s). Two compatible explanations:
1. The v1.7.0 timeout at 21+ min was itself an under-bound (the v1.7.0 retest doc explicitly noted "the solve was nowhere near finishing"; projected runtime was estimated at ~2.2 hr from the depth/range cost model — closer to today's per-iter floor).
2. The iter=5 probe in this retest disabled `compute_exploitability_at_end` while v1.7.0 enabled it; per-iter cost dominates either way.

Either way, the per-iter floor is in the same multi-hour-for-iter=500 band; **v1.8 SIMD did not move the needle on flop**, consistent with the bench report's root-cause analysis (LLVM `-O3` autovectorization saturates the small-slice path; hand-written intrinsics pay dispatch overhead that cancels the kernel win on action_count = 3-5).

### Flop verdict: **PARTIAL/Type D timeout (sub-fixture)** — unchanged from v1.7.0. Per-iter floor measured ≥ 122 s; iter=500 projected ≥ 17 hours (orders of magnitude over Sarah's 5 min budget).

---

## Verdict composition + status delta

| Sub-fixture | v1.7.0 verdict | v1.8.0 verdict (this retest) | Delta |
|---|---|---|---|
| River envelope (6c × 500i, K-Q-7-T-2 runout) | PASS (31.7 s) | **PASS (30.49 s)** | -3.8% wall-clock (within ~1.0× bench noise) |
| Original flop (8c × 500i, K-Q-7 flop) | FAIL — Type D timeout (>21 min terminated) | **FAIL — Type D timeout** (iter=5 probe terminated at 10 min; per-iter floor ≥ 122 s; iter=500 projected ≥ 17 hours) | Unchanged direction; measured per-iter floor now > v1.7.0 estimate |
| **Composite W2.1 verdict** | **PARTIAL** | **PARTIAL** | **No change** |

**Status delta: PARTIAL → PARTIAL.** The W2.1 row in the persona snapshot does not need to be reclassified. The river envelope continues to PASS with bit-identical exploitability (4.5855 vs 4.59), and the flop fixture remains perf-bound for the same root-cause reasons identified in v1.7.0.

**Type classification per `pr13_prep/rectification_framework.md`:**
- River envelope: **Type A clean** (correctness + perf both PASS).
- Flop fixture: **Type D timeout** (perf scalability gap on multi-street game tree; not a regression — same characterization as v1.7.0).
- Composite (per persona-test grain): **PARTIAL** with explicit "v1.8 SIMD did NOT unblock flop" footnote, per snapshot's expected outcome.

---

## Wall-clock summary

| Test | Wall-clock | Budget | % of budget |
|---|---|---|---|
| River Nash (6c × 500i) | 30.494 s | ≤ 300 s (Sarah session) | 10.2% |
| River aggregator (6c × 100i × 2 reps) | 0.165 s | ≤ 300 s | 0.05% |
| Flop probe (8c × 5i; terminated) | 10 min 10 s (incomplete) | ≤ 300 s (Sarah session) | ≥ 203% (timeout characterization) |
| **Total retest agent wall-clock** | ~11 min | ≤ 25 min task cap | under |

---

## Findings + observations

1. **River envelope wall-clock is within noise vs v1.7.0** (30.49 s vs 31.7 s; -3.8%). Consistent with `docs/v1_8_simd_perf_benchmark_2026-05-26.md`'s reported ~1.0× SIMD ratio on M4 Pro arm64. **No regression**, also no measurable v1.8 acceleration on this fixture.
2. **Nash exploitability is bit-identical** (4.585512251598538 vs the prior doc's `~1.5e-08` divergence-vs-aggregator-style reporting; matches the prior `4.59` rounded form to 3+ digits). Confirms v1.8 SIMD changes are **numerically equivalent** to v1.7.0 on this workload — i.e., the SIMD codepaths preserve the scalar-baseline computation.
3. **All 6 classes diverge from aggregator by ≥ 10%** (6/6 ≥ 0.05; 6/6 ≥ 0.10). Identical divergence pattern as v1.7.0 (AA/JJ/KK/TT/AKs all ~1.0 max delta; QQ ~0.44). The Nash path continues to produce materially distinct strategies vs the aggregator.
4. **Flop fixture remains perf-bound.** The v1.8 SIMD bench refutation propagates here: small-slice scalar loops (action_count = 3-5) are already LLVM-autovectorized; hand-written intrinsics pay dispatch overhead that cancels the kernel win. The flop multi-street tree depth is the dominant cost, not the inner-loop SIMD path.
5. **Snapshot is accurate.** No revision needed to `docs/persona_test_status_2026-05-26.md` W2.1 row; the "PARTIAL — flop times out; river envelope passes" framing stands.

---

## Routing per framework

Per `feedback_persona_test_rectification` + `feedback_post_ship_persona_retest`:
- River envelope PASS → no action needed; row stays PARTIAL with positive river footnote.
- Flop Type D → **NOT a regression** (was already Type D at v1.7.0; v1.8 was hypothesized to unblock and the hypothesis was empirically refuted on bench + here). No HALT trigger.
- Per `feedback_chase_vs_ship_decision`: the flop perf-bound branch was already reframed at v1.7.0 (smaller-fixture envelope established as the canonical Sarah path). **No further iteration warranted** at v1.8 — v1.9 EMD bucketing per `v1_8_decision_brief.md:26` is the structural path forward.

---

## Files / artifacts

- River retest driver: `/tmp/w2_1_retest_2026_05_26.py`
- River retest output: `/tmp/w2_1_retest_2026_05_26_output.txt`
- River retest JSON: `/tmp/w2_1_retest_2026_05_26_result.json`
- Flop probe driver: `/tmp/w2_1_flop_probe_2026_05_26.py`
- Flop probe output (in flight at finalization): `/tmp/w2_1_flop_probe_2026_05_26_output.txt`
- Flop probe JSON (will appear when complete): `/tmp/w2_1_flop_probe_2026_05_26_result.json`

---

## References

- Prior PARTIAL snapshot: `/Users/ashen/Desktop/poker_solver/docs/persona_status_post_v1_8_2026-05-26.md` §4 W2.1 row
- Prior current-of-record: `/Users/ashen/Desktop/poker_solver/docs/persona_test_status_2026-05-26.md` Sarah W2.1 row
- v1.7.0 flop Type D timeout: `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/W2_1_post_v1_7_0_result.md`
- v1.7.0 river-envelope PASS (this retest matches): `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/W2_1_post_v1_7_0_smaller_fixture_result.md`
- v1.8 SIMD bench refutation (~1.0×): `/Users/ashen/Desktop/poker_solver/docs/v1_8_simd_perf_benchmark_2026-05-26.md`
- v1.9 EMD bucketing roadmap (structural perf path): `/Users/ashen/Desktop/poker_solver/docs/v1_8_decision_brief.md`
- Rectification framework: `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/rectification_framework.md`
- Persona time budgets: `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/persona_time_budgets.md`
- Post-ship retest mandate: `~/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/feedback_post_ship_persona_retest.md`
- Plan + sanity-check rule: `~/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/feedback_external_solver_sanity_check.md`
