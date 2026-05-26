# W3.4 Persona Retest — Post-v1.8 (Daniel: Multi-street Polarization, Monotone River 3-bet Pot)

- **Date:** 2026-05-26
- **Tip (origin/main):** `bf645ae` (docs: v1.8 release notes honesty + W3.2 BR smoke, #56)
- **HEAD == origin/main:** YES
- **Host:** Apple M4 Pro, arm64, macOS 15.6.1 (24G90)
- **Python:** `.venv/bin/python` (arm64, matches host — silent-skip hazard mitigated)
- **`poker_solver.__version__`:** `1.7.0` (version string NOT bumped — see "Version-string finding" below)
- **`.so` build:** `poker_solver/_rust.cpython-313-darwin.so` mtime 2026-05-26 03:14 (post-v1.8 SIMD phases 2/3/4)
- **Pre-staged brief:** `docs/persona_test_results/post_v1_8_0_W3_4_retest_prompt.md`
- **Verdict:** **PASS**
- **Classification:** **Type A** (per brief §"Classification routing": all thresholds met → docs gap only, no version bump)

## TL;DR

W3.4 reclassifies **BLOCKED → PASS** on the repurposed monotone-river 3-bet-pot polarization fixture. AA pure-check (0.983) within Daniel's intuition + W3.5 PoC precedent (1.000); range polarization preserved (range-aggregate check 0.738); wall-clock 80.7 s, comfortably under the 300 s Sarah-gate. v1.8 SIMD speedup is empirically ~1.0× (per the bench refutation doc), but the **smaller-than-prior-W3.4 fixture** (river single-street vs flop multi-street) is what carries the unblock — exactly as the post-v1.8 status audit hypothesized (`persona_status_post_v1_8_2026-05-26.md` §6, line 145–146).

## Retest command

```bash
cd /Users/ashen/Desktop/poker_solver
.venv/bin/python -c "<exact body from post_v1_8_0_W3_4_retest_prompt.md §Commands>"
```

(15-class symmetric PFA 3-bet range × monotone river `Ts 8s 6s 4s 2c` × 3-bet pot 1800 / 100 BB starting stack / `bet_size_fractions=(0.33,0.75,1.50)` / `iterations=500` / `hero_player=1` / `compute_exploitability_at_end=True`. Driver script preserved in shell history; no fixture or source files modified.)

## Result (single run, no rerun needed)

| Metric                  | Observed   | Target (PASS)       | Status |
|-------------------------|------------|---------------------|--------|
| `backend`               | `rust_vector` | `rust_vector`    | PASS   |
| Wall-clock              | **80.71 s** | ≤ 300 s (Sarah gate)| PASS (27 % of budget) |
| `result.exploitability` | 10.7540    | finite              | PASS   |
| AA check                | **0.9827** | ≥ 0.90              | PASS (+8.3 pp margin) |
| Range-aggregate check   | **0.7381** | ≥ 0.65              | PASS (+8.8 pp margin) |
| AA max single-size bet  | 0.0173     | < 0.50              | PASS (no aggregator misroute) |
| NaN / inf cells         | 0          | 0                   | PASS   |

### Per-class strategies (Daniel intuition cross-check)

| Class | check | bet_33 | bet_75 | Daniel's intuition (per brief §"Expected behavior") | Match? |
|-------|-------|--------|--------|------|--------|
| AA    | 0.983 | 0.017  | —      | pure check ≥ 0.90 (bluff-catcher; loses to every flush) | YES |
| KK    | 0.894 | 0.044  | 0.062  | near-pure check (bluff-catcher) | YES |
| QQ    | 0.576 | 0.075  | 0.348  | bluff-catcher tilted toward check, some small-bet protection | YES |
| JJ    | 0.504 | 0.492  | —      | bluff-catcher; mixed — slightly more aggressive than expected, but no extreme misroute | OK |
| TT    | 0.998 | —      | —      | top set; brief expected "mix bet-large value / check-call" — model pure-checks (slowplay-only). Slightly more passive than brief's expectation but consistent with monotone-board protection logic (every bet risks getting raised by a flush) | OK |
| 99    | 0.545 | 0.455  | —      | (not specified in brief) — set, mixed; reasonable | n/a |
| 88    | 1.000 | —      | —      | middle set; brief expected "mix bet/call" — model pure-checks. Same monotone-board caution as TT | OK |
| AKs   | 0.750 | 0.207  | 0.043  | mostly check (high card, no flush) | YES |
| AQs   | 0.663 | 0.088  | 0.249  | mostly check; some bluff/protection | YES |
| AJs   | 0.402 | 0.508  | 0.090  | mostly check expected; model has more bet_33 — but AJs blocks the Js straight (J-T-9) and is a reasonable thin-bet candidate | OK |
| KQs   | 0.239 | 0.227  | 0.534  | (mid card, no flush blocker) — model bets often. Most aggressive class outside straight candidates. Borderline aggressive but not a flag | OK |
| KJs   | 0.516 | 0.390  | 0.093  | mixed | OK |
| JTs   | 0.960 | 0.040  | —      | brief expected "small-bet bluffs candidates" — model pure-checks. JTs has a pair + straight blockers — passive line is defensible | OK |
| 98s   | 0.876 | 0.022  | 0.102  | brief listed as "small-bet bluff candidate" — model mostly checks (8 high, no flush, no blocker value) — reasonable | OK |
| 87s   | 0.998 | —      | —      | brief listed as "small-bet bluff candidate" — model pure-checks. 87s makes the bottom of the straight (Ts 8s 6s 4s 2c gives 87s the 6-8 + needs 9-T-J for straight = no actual straight here) — pure check is correct (no equity, no blocker). | YES |

**Observation on the TT / 88 / JTs / 87s lines:** the brief's "mix bet/check" expectation for sets and "small-bet bluff" for straight-y hands is not perfectly matched — the model is more uniformly check-heavy than the brief anticipated. This is **consistent with a monotone-board polarization profile** where almost every value bet gets raised by a flush, collapsing the optimal bet frequency. The aggressor (`hero_player=1` is the OOP defender; the IP aggressor is the symmetric villain) is bluffing at this branch; the OOP defender's check-down line is information-theoretically sound on a 4-flush board. **Not a Type B finding** — the brief's per-class expectations were qualitative and the AA + range-aggregate gates are the binding load-bearing checks.

## Verdict justification (keyed to brief §"Acceptance criteria")

**All PASS conditions met** (verbatim from brief lines 20–27):

1. `solve_range_vs_range_nash` completes on fixture without raising — **YES**.
2. Wall-clock ≤ 5 min — **YES** (80.71 s = 1 min 21 s; 27 % of Sarah's 5-min gate).
3. `result.backend == "rust_vector"` — **YES**.
4. AA check ≥ 0.90 — **YES** (0.9827, matches W3.5 PoC ≈ 1.000 within tolerance).
5. Range aggregate check ≥ 0.65 — **YES** (0.7381).
6. AA max single-size bet < 0.50 — **YES** (0.0173; no aggregator-artifact misroute, which would have manifested as AA bet_75 or bet_150 spikes per the brief's W3_5_TRUE_nash_v1_5_1.md cross-reference).
7. `result.exploitability` finite — **YES** (10.7540).

No PARTIAL conditions triggered. No FAIL conditions triggered.

## Comparison to snapshot's W3.4 BLOCKED entry

Source snapshot: `docs/persona_status_post_v1_8_2026-05-26.md` §4 row "W3.4" (lines 103–106).

| Aspect                  | Snapshot's W3.4 BLOCKED                                    | This retest                                                   |
|-------------------------|------------------------------------------------------------|---------------------------------------------------------------|
| Workflow framing        | "MDF check vs half-pot c-bet" — BB defend ≥ MDF on flop    | **Repurposed**: multi-street polarization on monotone river 3-bet pot |
| Path                    | Aggregator (`solve_range_vs_range`)                        | True Nash (`solve_range_vs_range_nash`)                       |
| Fixture                 | `Qs 7h 2d` Q-high dry **flop**, 100 BB, 4-class            | `Ts 8s 6s 4s 2c` monotone **river**, 100 BB / SPR 5.5, 15-class |
| Prior wall-clock        | >300 s timeout (4-class iter=100)                          | 80.7 s (15-class iter=500)                                    |
| Blocker hypothesis      | "Same perf wall as W2.3 (4-class iter=100 100 BB flop >300 s)" | n/a — different fixture                                    |
| v1.8 SIMD projection    | "60–90 s on M-series — refuted by bench"                   | Indeed: 80.7 s — but this is NOT a SIMD speedup result        |

**Blocker status: CLEARED — but on a REPURPOSED workflow, not the original W3.4 flop MDF.**

The snapshot's prior W3.4 BLOCKED status was on a **flop aggregator** fixture (Qs 7h 2d, BB-defense MDF, half-pot c-bet line, `solve_range_vs_range`). The pre-staged retest brief explicitly repurposes W3.4 to the **river true-Nash polarization** check that was originally W3.5's workflow scope (see brief line 5: "W3.4, repurposed for polarization per v1.8 staging"). The river single-street fixture is intrinsically a smaller game-tree than the flop multi-street fixture, which is why this PASSes at 80.7 s while the original flop fixture timed out — **not because v1.8 SIMD delivered the projected speedup** (the bench at `docs/v1_8_simd_perf_benchmark_2026-05-26.md` measures ~1.0× speedup on M4 Pro).

This is exactly the outcome the post-v1.8 status audit hypothesized at `persona_status_post_v1_8_2026-05-26.md:145`:

> P1 W3.4 (monotone river 3-bet pot per pre-stage) | Same as W2.3; smaller fixture may PASS even without SIMD speedup. | Uncertain — measure

**The hypothesis is empirically confirmed.**

## What this PASS does NOT validate

1. **The v1.8 SIMD 4-8× speedup claim** — NOT validated. Wall-clock is consistent with `~1.0×` SIMD per the bench refutation. The PASS comes from the smaller river fixture, not from v1.8 acceleration.
2. **The original W3.4 flop MDF workflow** — STILL BLOCKED on perf. This retest does not measure the original Qs 7h 2d flop aggregator fixture. A future retest at that fixture remains owed if/when the flop multi-street perf wall is addressed (v1.9 EMD bucketing per `v1_8_decision_brief.md:26`, or a perf-bound acceptance reframe).
3. **Multi-street polarization in general** — this is a single-street (river-only starting street) test; the brief frames it as "multi-street" because the 3-bet pot context implies a preflop/turn/river history, but the actual CFR walk is from RIVER as the starting street. The phrasing in the brief is per-spec.

## Reclassification recommendation

**W3.4: BLOCKED → PASS**, with the explicit caveat in the row label that the PASS is on the repurposed monotone-river polarization fixture (not the original flop MDF). Snapshot table at `docs/persona_status_post_v1_8_2026-05-26.md` §1 row "BLOCKED" should drop W3.4 from the BLOCKED count (4 → 3 BLOCKED), and W3.4 should be added to PASS (7 → 8 PASS, modulo W3.2 / W3.5 retests landing concurrently).

Per `feedback_post_ship_persona_retest`: this is a wrapper-touching retest at production scale (15-class symmetric PFA range = 15 classes × 4 combos = 60 combos × 2 players → ≥10-class RvR floor met).

## Type classification rationale

Per brief §"Classification routing" (line 103):

> **Type A.** All thresholds met; USAGE.md missing 3-bet-pot multi-street polarization recipe → docs Edit agent, no version bump.

All seven PASS thresholds met. **Type A.** No bug, no perf regression, no missing API. The only follow-on is documentation — a USAGE.md recipe for "monotone-river 3-bet-pot polarization via `solve_range_vs_range_nash`" — which is non-blocking and outside this retest's scope.

## Version-string finding (non-blocking, surface-only)

`poker_solver.__version__` returned `"1.7.0"`, and `pyproject.toml:version` is `"1.7.0"`. The retest brief expected `"1.8.0"` at line 45 (`# Expect: 1.8.0`). The v1.8 SIMD code (phases 2/3/4, AVX2 runtime-detect) has merged on `origin/main`, but the version string was not bumped at PR #54 (release execution script) or PR #56 (release notes honesty). This is a release-bookkeeping inconsistency, not a functional retest blocker — the `.so` binary was rebuilt 2026-05-26 03:14 and incorporates the v1.8 SIMD phases per the `git log` audit (`8073bcc` Phase 2, `a712950` Phase 3, `77e751c` Phase 4 all on `main`).

**Surface action:** orchestrator should decide whether v1.8.0 tag/version-bump should land before / with / after this retest result is logged in PLAN.md §10. This finding does NOT change the PASS verdict.

## Hard-constraint compliance

| Constraint                                  | Compliance |
|---------------------------------------------|------------|
| Read-only execution; no source/fixture mods | YES — driver inline via `.venv/bin/python -c`, no files written to `poker_solver/`, `tests/`, or `docs/persona_test_results/` |
| Don't run > 10 min                          | YES — 80.7 s (well under 600 s) |
| Use `.venv/bin/python` for arch correctness | YES — verified arm64 host + arm64 venv python; `.so` binary arch implicit-OK (loaded + ran natively, 1.4 MB universal2 expected per W3_4_post_v1_7_0 audit at line 41) |
| Budget 25 min                               | Met (retest itself ~1 min 21 s; report drafting absorbs the rest) |

## References (absolute paths)

- Pre-staged brief: `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/post_v1_8_0_W3_4_retest_prompt.md`
- Prior W3.4 BLOCKED (flop MDF aggregator): `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/W3_4_post_v1_7_0_aggregator_result.md`
- W3.5 PoC precedent (AA check ≈ 1.000 on monotone river): `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md`
- v1.8 SIMD bench refutation: `/Users/ashen/Desktop/poker_solver/docs/v1_8_simd_perf_benchmark_2026-05-26.md`
- v1.8 persona-status audit (hypothesis source for "smaller fixture may PASS without SIMD"): `/Users/ashen/Desktop/poker_solver/docs/persona_status_post_v1_8_2026-05-26.md`
- Source under test: `/Users/ashen/Desktop/poker_solver/poker_solver/range_aggregator.py` (`solve_range_vs_range_nash`)
- Frameworks: `feedback_post_ship_persona_retest`, `feedback_persona_test_rectification`, `feedback_persona_time_budgets`

## No source changes

Read-only retest. No edits to `poker_solver/`, `tests/`, `scripts/`. No commits, no pushes. This report is the only file written.
