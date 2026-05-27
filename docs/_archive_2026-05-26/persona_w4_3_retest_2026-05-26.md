# W4.3 Persona Retest — 2026-05-26 (P3, aggregator focus)

- **Date:** 2026-05-26
- **Persona:** Priya (researcher; cares about parity, reproducibility, scriptability)
- **Workflow:** W4.3 — "Diff our solver vs Brown on novel river spot"
- **Priority:** P3 (per persona status snapshot directive)
- **Tip (origin/main):** `d0b7b34` (`docs: surface pyenv x86_64 vs arm64 .so arch hazard for devs (#67)`)
- **poker_solver version:** `1.7.0` (`poker_solver.__version__`)
- **Backend:** Rust (`backend="rust"`); arm64 `.so` (host arm64 — match verified)
- **Python:** `.venv/bin/python` (`/Users/ashen/Desktop/poker_solver/.venv`)
- **Path tested:** aggregator (`solve_range_vs_range`), NOT the strict Brown apples-to-apples diff harness (`tests/test_river_diff.py`)
- **Verdict:** **PASS via aggregator path (unchanged)**
- **Type:** **A** (correctness; population-frequency / determinism / scriptability read; no code change required)
- **Driver:** `/tmp/w43_retest_driver.py` (preserved)
- **Read-only:** no edits to `poker_solver/`, `tests/`, `scripts/`; no commits / pushes / branches.

---

## 1. Status snapshot context (why a retest)

Per `docs/persona_test_status_2026-05-26.md:95`:

> **W4.3** — "Diff our solver vs Brown on novel river spot" — **PASS via aggregator path** | v1.7.0 aggregator retest (`W4_3_post_v1_7_0_aggregator_result.md`) | Aggregator path <5 s on novel river spot. Strict `tests/test_river_diff.py` path remains test-coupled.

The 2026-05-26 snapshot lists W4.3 PASS-aggregator and flags it under "BLOCKED / PENDING" only for the strict canonical-parity test path:

> **W4.3 strict path** — `tests/test_river_diff.py` canonical-parity timeout (separately tracked from PASS via aggregator path)

The P3 retest scope is the **aggregator path** (matching the prior v1.7.0 retest protocol on the current tip), not the strict canonical-parity timeout. The v1.8 SIMD bench (`docs/v1_8_simd_perf_benchmark_2026-05-26.md`) measured ~1.0× on M4 Pro arm64 — strict-path perf characterization is therefore unchanged from v1.7.0 and out of scope here.

## 2. Pre-condition verification

| Check | Expected | Observed | Pass |
|---|---|---|---|
| `.so` arch matches host | host=arm64, `.so` includes arm64 | `_rust.cpython-313-darwin.so` = `Mach-O 64-bit dynamically linked shared library arm64`; `uname -m` = `arm64` | YES |
| `poker_solver.__version__` | `1.7.0` | `1.7.0` | YES |
| `solve_range_vs_range` importable | YES | YES | YES |
| `HUNLConfig`, `Card`, `Street` importable from `poker_solver` | YES | YES | YES |
| Novel board not in canonical fixtures | YES | YES (verified-novel against `tests/data/river_spots.json` per `W4_3_v1_4_0_retest.md §3`) | YES |

## 3. Scenario (identical to v1.7.0 retest)

- **Board:** `Th 8h 4s Jc 2d` (novel — verified against 15 canonical fixtures)
- **Starting street:** `Street.RIVER`
- **Starting stack:** 9500 chips (95 BB)
- **Initial pot:** 1000 chips (10 BB), contributions (500, 500)
- **`bet_size_fractions`:** `(0.5, 1.0)`
- **`postflop_raise_cap`:** 3
- **Hero range (P0 / aggressor):** `["AA", "KK", "QQ", "JJ", "TT", "99"]` (6 classes / 30 combos)
- **Villain range (P1 / defender):** `["AA", "KK", "QQ", "AKs", "AQs", "KQs"]` (6 classes)
- **Solver call:** `solve_range_vs_range(config, hero_range, villain_range, iterations=200, backend="rust", hero_player=0, reps_per_class=1, villain_reps=2, time_budget_per_solve_s=20.0, dcfr_kwargs={"seed": 42})`

API note: the v1.7.0 driver's `board=...` kwarg corresponds to `initial_board=...` on the current `HUNLConfig` signature (plus an explicit `starting_street=Street.RIVER`); this is shape-equivalent and was the only adaptation between the v1.7.0 retest driver and this run.

## 4. Results

### Run 1 (seed=42)

| Metric | Value |
|---|---|
| Wall-clock | **1.003 s** |
| Position | `aggressor` |
| Total combos enumerated | 30 |
| Total solves | 54 |
| Partial misses | 0 |
| Warnings | (none) |

Range-aggregate action frequencies:
- `bet_50: 0.398266`
- `fold: 0.250000`
- `bet_100: 0.211844`
- `all_in: 0.139890`
- `check: 0.000000`
- `call: 0.000000`

Per-class freqs (hero=aggressor):
- `AA: bet_50=0.531, bet_100=0.282, all_in=0.187, check=0.000` (no checking with AA, expected)
- `KK: bet_50=0.354, bet_100=0.188, all_in=0.124, fold=0.333` (mixed; same fold-share as v1.7.0)
- `QQ: bet_50=0.177, bet_100=0.094, all_in=0.062, fold=0.667` (mostly fold — beaten by JJ on board)
- `JJ: bet_50=0.531, bet_100=0.282, all_in=0.187` (top set, value bet)
- `TT: bet_50=0.531, bet_100=0.282, all_in=0.187`
- `99: bet_50=0.266, bet_100=0.141, all_in=0.093, fold=0.500`

### Run 2 (same seed=42, determinism check)

| Metric | Value |
|---|---|
| Wall-clock | **1.001 s** |
| Range-aggregate | identical to Run 1 |
| Max diff (range_aggregate) | **0.00e+00** |
| Within 1e-4 tolerance | **YES** |

### Wall-clock budget

| Budget | Value |
|---|---|
| Per-side spec ceiling | 5 min (300 s) |
| Observed per-run | 1.00 s |
| Total session ceiling | 15 min (900 s) |
| Observed total (both runs) | 2.00 s |
| Within budget | **YES** (~450x headroom; same scale as v1.7.0 retest's 200x) |

## 5. Verdict justification (5/5 PASS)

| # | Criterion | Status | Notes |
|---|---|---|---|
| 1 | Workflow runs end-to-end via public API | **PASS** | `solve_range_vs_range` is public, completes without exception |
| 2 | Novel-spot config solves | **PASS** | 54 per-hand solves complete in 1.00 s; 0 partial misses; 0 warnings |
| 3 | Determinism / reproducibility (same seed → same answer) | **PASS** | Max diff `0.00e+00` < 1e-4 tolerance (bit-identical) |
| 4 | Wall-clock within budget | **PASS** | 1.00 s per side; 2.00 s total vs 15 min ceiling |
| 5 | Plausible per-class action shape | **PASS** | QQ folds 0.667 (correctly weaker on JT-board), AA / JJ / TT value-bet pure (zero fold), 99 / KK mixed |

**All five PASS.** Strict PASS via the aggregator path on current tip `d0b7b34`.

## 6. Cross-check vs v1.7.0 retest

| Metric | v1.7.0 (`W4_3_post_v1_7_0_aggregator_result.md`) | This run (2026-05-26, tip `d0b7b34`) | Drift |
|---|---|---|---|
| Wall-clock per run | 1.65 s | 1.00 s | -39% (likely incidental scheduler / cache; same machine-class, same Rust solve count) |
| Total combos | 30 | 30 | 0 |
| Total solves | 54 | 54 | 0 |
| Partial misses | 0 | 0 | 0 |
| Determinism | max diff 0.000000 | max diff 0.00e+00 | 0 |
| AA action shape | `all_in=0.262, bet_50=0.492, bet_100=0.246, check=0.000` | `bet_50=0.531, bet_100=0.282, all_in=0.187, check=0.000` | Slight mass redistribution within {all_in, bet_50, bet_100}; total no-check / no-fold mass preserved at 1.000 |
| QQ fold-share | 0.667 | 0.667 | bit-identical |
| KK fold-share | 0.333 | 0.333 | bit-identical |
| 99 fold-share | 0.500 | 0.500 | bit-identical |

**Note on AA / JJ / TT mass redistribution:** The fold/check zeros and the QQ / KK / 99 fold-shares are bit-identical to v1.7.0. The internal split between `all_in` / `bet_50` / `bet_100` for value-bet classes shifted within the value-bet manifold (Nash-multiplicity / indifference behaviour on the value-bet sub-tree). This is the documented deep-cap manifold pattern called out in `feedback_nash_multiplicity_acceptance` — total value-bet mass is preserved (sums to 1.000 on AA / JJ / TT), and the fold-share — the load-bearing read for Priya's diff workflow — is bit-identical across runs. The shift is consistent with normal solver-version drift between v1.7.0 and the current tip and does not invalidate the PASS gate.

## 7. Caveats (unchanged from v1.7.0)

1. **Aggregator semantics ≠ Brown apples-to-apples Nash.** This retest does NOT make a bit-exact claim against Brown's `river_solver_optimized`. The strict-parity claim remains coupled to `tests/test_river_diff.py`.

2. **No strict-Nash comparison.** Per `feedback_post_ship_persona_retest.md`, the aggregator path is "documented as valid for population-level frequency reads." This is a population-frequency read, not a strict-Nash agreement check.

3. **`hero_player=0` only.** Aggressor-side only; defender-side would require `hero_player=1` and was not exercised in this run (same scope as v1.7.0 retest).

4. **Per-combo Nash semantics.** Each per-hand solve is 1-combo-vs-1-combo perfect-info, averaged across `villain_reps=2` representative villain combos per class. This is the documented aggregator behaviour; it does NOT model villain's mixed strategy across the full range.

5. **Strict `tests/test_river_diff.py` path NOT retested.** The 2026-05-26 status snapshot tracks the strict path separately under "BLOCKED / PENDING" as a perf-coupled blocker; v1.8 SIMD measured ~1.0× on M4 Pro arm64 per `v1_8_simd_perf_benchmark_2026-05-26.md`, so the strict-path timeout characterization from `W4_3_v1_4_0_retest.md` is unchanged. The strict-path retest is owed once a structural perf unlock lands (e.g., v1.9 EMD bucketing per `v1_8_decision_brief.md:26`).

## 8. Classification

- **Verdict:** PASS via aggregator path (no change from 2026-05-26 status snapshot row).
- **Type:** A (correctness; population-frequency / determinism / scriptability read).
- **Snapshot row impact:** none — W4.3 row already reads PASS-aggregator. This retest CONFIRMS the row on current tip `d0b7b34` and refreshes the per-run wall-clock to 1.00 s. The strict-path BLOCKED is unchanged and out of scope here.
- **Action item:** none for the aggregator path. The strict-path unblock remains gated on a structural perf fix (v1.9 EMD bucketing or equivalent) and is tracked separately.

## 9. Files referenced

- `/Users/ashen/Desktop/poker_solver/docs/persona_test_status_2026-05-26.md:95` (W4.3 row)
- `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/W4_3_post_v1_7_0_aggregator_result.md` (v1.7.0 retest baseline; protocol mirrored here)
- `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/W4_3_v1_4_0_retest.md` (canonical v1.4.0 BLOCKED; strict-path baseline; novel-board novelty verification §3)
- `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/persona_acceptance_spec.md:71` (W4.3 spec row)
- `/Users/ashen/Desktop/poker_solver/poker_solver/__init__.py` (exports `solve_range_vs_range`, `HUNLConfig`, `Card`, `Street`; `__version__="1.7.0"`)
- `/Users/ashen/Desktop/poker_solver/poker_solver/_rust.cpython-313-darwin.so` (arm64; arch verified)
- `/Users/ashen/Desktop/poker_solver/docs/v1_8_simd_perf_benchmark_2026-05-26.md` (v1.8 SIMD ~1.0× — strict-path perf-ceiling rationale)
- `/Users/ashen/Desktop/poker_solver/tests/data/river_spots.json` (canonical 15 fixtures; novel-board verification source)
- `/tmp/w43_retest_driver.py` (driver script; preserved)

## 10. No source changes

Read-only retest. No edits to `poker_solver/`, `tests/`, `scripts/`. No commits, no pushes, no branches. Driver script written only to `/tmp/`.

## 11. Bottom line

**W4.3 PASS via aggregator path confirmed on current tip `d0b7b34` (5/5 acceptance criteria, 1.00 s per run, bit-identical determinism, ~450x wall-clock headroom).** No reclassification needed — the 2026-05-26 status snapshot row reads PASS-aggregator and that is empirically confirmed. The strict canonical-parity path (`tests/test_river_diff.py`) remains separately tracked as perf-blocked and was not in scope here. Total retest wall-clock: ~3 s of compute + harness; well under the 10-minute / 25-minute budget.
