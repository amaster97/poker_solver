# Persona Retest — W4.2 (Priya) — 2026-05-26

## Brief

- **Workflow:** W4.2 "Add a custom 'limp-or-fold' mode for play vs short stacks." Extend the action abstraction to a 2-action menu (LIMP/CALL + FOLD, no raises, no all-in). Single representative solve at standard accuracy.
- **Persona:** Priya (researcher / developer; per-spot 1-5 min Pio-class; session 15 min)
- **Prior verdict:** PARTIAL — wiring + action restriction PASS; criterion (3-trash) + criterion (4) structurally mis-aligned with subgame mode. Type A DEVELOPER.md doc add.
  - Per `docs/persona_test_status_2026-05-26.md:94`: "Wiring + action restriction PASS; heuristic criteria mis-aligned with subgame mode."
  - Latest prior retest fixture: `docs/persona_test_results/W4_2_v1_4_0_retest.md` (v1.4.0, 2026-05-23, PARTIAL).
- **Spec:** `docs/pr13_prep/persona_acceptance_spec.md:69` + `docs/pr_proposals/priya_retest_W4_2.md` §B.
- **P3 priority backlog** (per task brief).

## Execution

- **Tip at retest start:** `d0b7b34` (then `98fb503` after concurrent PR #69 merge mid-session; retest workspace held the d0b7b34 tree)
- **Interpreter:** `/Users/ashen/Desktop/poker_solver/.venv/bin/python`
- **`poker_solver.__version__`:** `'1.7.0'`
- **Driver:** `/tmp/w42_retest.py` (read-only against `poker_solver/`)
- **Wall-clock:** 130.12 s = 2.17 min (well under 10 min budget, well under 15 min session cell)
- **Backend:** Python (`solve_hunl_preflop`)

## Test Scenario

Mirrors the v1.4.0 retest with the same fixture so verdict shifts are attributable to engine changes only.

- `HUNLConfig(starting_stack=900, small_blind=50, big_blind=100, starting_street=Street.PREFLOP, bet_size_fractions=(), include_all_in=False, initial_hole_cards=(hero, villain))`
- 9 BB effective — short-stack, limp-or-fold is GTO-meaningful
- `iterations=500`, `seed=42`
- `solve_hunl_preflop(cfg, ..., allow_pushfold_range=True)` — `allow_pushfold_range` required at 9 BB per `preflop.py:441` (research-mode escape from the push/fold short-circuit at ≤15 BB)
- **Hand panel:** 7 premium (AA, KK, QQ, JJ, TT, AKs, AQs) + 3 trash (32o, 72o, 92o) vs fixed villain Js9c (mid-tier offsuit, ~30th percentile)
- **Differential probes:** 32o vs KK (trash-vs-monster, must FOLD), AA vs KK (premium-vs-premium, must LIMP)
- **Card suit selection avoids Js9c clash** — pairs use h+d, suited use d+d, offsuit use d+h (versus the v1.4.0 retest which hit a JJ duplicate-card error if not careful; the v1.4.0 doc reports JJ at t=12.82 s, so they avoided the clash too)

## Pre-condition Verification

| Check | Result |
|---|---|
| `git rev-parse HEAD` | `d0b7b34` (retest start) / `98fb503` (post-PR #69 merge mid-session) |
| `poker_solver.__version__` | `"1.7.0"` (>=1.4.0 gate PASS) |
| `HUNLConfig(...).bet_size_fractions == ()` | True |
| `HUNLConfig(...).include_all_in is False` | True |
| `HUNLConfig(...).starting_street == Street.PREFLOP` | True |
| `solve_hunl_preflop` accepts `allow_pushfold_range=True` | True |

All pre-conditions PASS. No BLOCKED.

## API Observation (v1.7.0)

`PreflopSolveResult.average_strategy` is `dict[str, list[float]]` keyed by infoset-id strings of form `'<hero>|<board>|p|<action_chars>'`. Each value is a probability distribution over LEGAL actions sorted ascending by action-ID.

- SB root (key like `'AsAh||p|'`): list length 2 — `[FOLD_p, CALL_p]` (since `ACTION_FOLD=0 < ACTION_CALL=2`)
- BB response after SB limp (key like `'9cJs||p|c'`): list length 1 — `[CHECK_p]` (since `ACTION_CHECK=1` is the only legal action when no raise sizes available)

Criterion (2) action-restriction PASS is established by `max(len(d) for d in average_strategy.values()) == 2`. Any `len > 2` would indicate a bet/raise/all-in slipped into the support.

## Measurements

### Per-hand strategy at SB root (legal actions sorted by ID → [FOLD, CALL])

| Hand | Bucket | t (s) | LIMP | FOLD | sb_len | bb_len | max_len |
|---|---|---|---|---|---|---|---|
| AA | premium | 10.77 | 1.0000 | 0.0000 | 2 | 1 | 2 |
| KK | premium | 10.83 | 1.0000 | 0.0000 | 2 | 1 | 2 |
| QQ | premium | 10.84 | 1.0000 | 0.0000 | 2 | 1 | 2 |
| JJ | premium | 10.87 | 1.0000 | 0.0000 | 2 | 1 | 2 |
| TT | premium | 10.87 | 1.0000 | 0.0000 | 2 | 1 | 2 |
| AKs | premium | 10.95 | 1.0000 | 0.0000 | 2 | 1 | 2 |
| AQs | premium | 11.00 | 1.0000 | 0.0000 | 2 | 1 | 2 |
| 32o | trash | 10.86 | 1.0000 | 0.0000 | 2 | 1 | 2 |
| 72o | trash | 10.90 | 1.0000 | 0.0000 | 2 | 1 | 2 |
| 92o | trash | 10.91 | 0.0000 | 1.0000 | 2 | 1 | 2 |

### Differential probes (equity-discriminator validation)

| Hand pair | t (s) | LIMP | FOLD | Expected | Match |
|---|---|---|---|---|---|
| 32o vs KK | 10.74 | 0.0000 | 1.0000 | FOLD (trash vs monster) | YES |
| AA vs KK | 10.58 | 1.0000 | 0.0000 | LIMP (premium vs premium) | YES |

### Aggregate metrics

| Metric | Value | Criterion gate | Met? |
|---|---|---|---|
| Premium LIMP min (across 7 premium) | **1.0000** | `>= 0.90` | **PASS** |
| Trash FOLD min (across 3 trash) | **0.0000** | `>= 0.90` | **STRUCTURAL FAIL** (mirrors v1.4.0 doc) |
| Aggregate panel LIMP freq (mean of 10) | **0.9000** | `in [0.40, 0.90]` | **PASS** (right at upper bound) |
| Any forbidden action (bet / raise / all-in) | **None** | none allowed | **PASS** |
| `max(len(d) for d in average_strategy)` | **2** | `<= 2` | **PASS** |
| Total wall-clock | **130.12 s (2.17 min)** | `<= 15 min` | **PASS** |
| Per-spot wall-clock | 10.58-11.00 s | `< 5 min` | **PASS** |
| Kill-switch | not triggered | 30 min | **PASS** |

## Verdict Justification (keyed to criteria 1-5)

1. **Setup is executable.** PASS. All 12 solves (10 panel + 2 probes) completed without `ValueError`, `NotImplementedError`, or segfault. `HUNLConfig(..., bet_size_fractions=(), include_all_in=False)` reaches the engine via `HUNLConfig.to_action_config()` (`hunl.py:151-159`) unchanged from v1.4.0.

2. **Action set is restricted.** PASS. Every infoset's `len(dist) <= 2` (SB root = 2 [FOLD, CALL]; BB response after SB-limp = 1 [CHECK]). No bet/raise/all-in slot appears anywhere in any infoset's average strategy across all 12 solves.

3. **Strategy non-degenerate — premium PASS, trash STRUCTURAL FAIL.**
   - Premium (AA, KK, QQ, JJ, TT, AKs, AQs): all limp at `1.0000 >= 0.90`. PASS.
   - Trash (32o, 72o, 92o vs Js9c villain): 2 of 3 limp 1.0000, only 92o folds. STRUCTURAL FAIL per the v1.4.0 doc — at 9 BB with no raise actions, SB's choice is "lose 50 (already-posted SB) by folding vs check down to showdown." Break-even raw equity threshold is **25%** (`EV_limp = 200·equity - 100; EV_fold = -50; limp > fold ⟺ equity > 0.25`). Most trash hands beat 25% raw equity vs the mid-tier Js9c villain, so limping is mechanically correct. The differential probes confirm: when villain is a monster (KK), 32o folds 1.0000 — the solver is making equity-driven decisions. **Not a solver bug.**

4. **BB iso-raising frequency proxy.** PASS this run (0.9000 right at the [0.40, 0.90] upper bound, vs v1.4.0's 0.9200 just over). The structural caveat from the v1.4.0 doc still applies: with no raise actions, BB cannot iso-raise, so the heuristic reduces to "SB's aggregate limp freq vs the median villain." The mean across the 10-hand panel is 0.9000, which is just inside the [0.40, 0.90] gate. Note: the small panel composition (7 premium + 3 trash) skews the mean upward; the v1.4.0 doc ran a 20-hand panel with more mid-tier hands, hitting 0.9200. PASS this run is partly an artifact of panel composition — would still PARTIAL on a larger panel — and the heuristic remains "inapplicable in subgame mode" per v1.4.0 §Caveats(4).

5. **Wall-clock within budget.** PASS. Per-spot 10.58-11.00 s (well under 5-min standard target; about 30% faster than v1.4.0's 12.67-17.62 s per-spot wall-clock — consistent with the persistent v1.5+ Python-tier improvements between v1.4.0 and v1.7.0). Total agent wall-clock 2.17 min (well under Priya's 15-min session cell, and well under the parent task's 10-min budget).

**Per-criterion verdict mapping:**
- (1) PASS, (2) PASS, (3) split (premium PASS / trash STRUCTURAL FAIL), (4) PASS-by-arithmetic (structurally inapplicable), (5) PASS
- Result: **PARTIAL** ("wiring OK, heuristic miss" branch)

## Type Classification

**Type A (DEVELOPER.md docs-debt; no code patch required).** The persistent classification from the 2026-05-23 v1.4.0 retest holds:

- Engine wiring is correct end-to-end. `ActionAbstractionConfig` knobs (`include_all_in=False`, `bet_size_fractions=()`) reach the engine via `HUNLConfig` first-class fields without regression from v1.4.0 to v1.7.0.
- Criterion (3-trash) and criterion (4) heuristics are structurally inapplicable in subgame mode (`solve_hunl_preflop` fixes both hole cards, so per-hand-pair best response is fully determined by equity, not by population-level range dynamics).
- The two reasonable refinements documented in the v1.4.0 doc §Caveats(2) remain valid:
  - (a) Extend the menu to include a single BB iso-raise size (e.g. `bet_size_fractions=(2.0,)`) to restore the iso-raise dynamic the spec heuristic references.
  - (b) Reclassify criterion (4) as informational-only when no raise actions exist.

**No solver bug. No engine patch needed. Same Type A classification carries.**

## Comparison to v1.4.0 Retest

| Metric | v1.4.0 (2026-05-23) | v1.7.0 (today) | Delta |
|---|---|---|---|
| Verdict | PARTIAL | PARTIAL | unchanged |
| Type | A (DEVELOPER.md docs) | A (DEVELOPER.md docs) | unchanged |
| Premium LIMP min | 1.0000 | 1.0000 | unchanged |
| Trash FOLD min | 0.0000 (5 trash) | 0.0000 (3 trash) | unchanged |
| Aggregate panel LIMP | 0.9200 (20-hand panel) | 0.9000 (10-hand panel) | -0.02 (within [0.40, 0.90] gate vs just over) |
| Per-spot wall-clock | 12.67-17.62 s | 10.58-11.00 s | **~30 % faster** |
| Total wall-clock | 5.65 min (24 solves) | 2.17 min (12 solves) | proportional |
| `max(len(dist))` | 2 (FOLD+CALL only) | 2 (FOLD+CALL only) | unchanged — no regression |

**No regression. v1.7.0 is faster per-spot (consistent with general v1.5+ Python-tier improvements; not v1.8-SIMD-attributable per `docs/v1_8_simd_perf_benchmark_2026-05-26.md` ~1.0× measurement).**

## Caveats

1. **Smaller panel than v1.4.0 retest.** Today's 10-hand panel (7 premium + 3 trash) is smaller than v1.4.0's 20-hand panel (9 premium + 6 mid + 5 trash). I omitted the mid-tier bucket (99, 88, ATo, KQs, 76s, 65s) to stay inside the parent task's <10-min budget. Aggregate-limp freq is therefore mean-shifted upward (no mid-tier hands to pull the average down). The verdict label is unchanged; only the precise aggregate-limp number differs.

2. **`allow_pushfold_range=True` required at 9 BB.** Same caveat as v1.4.0 §Caveats(4) — this is the documented research-mode escape (`preflop.py:441-443`). If W4.2 ships with the 9 BB short-stack exemplar, this flag must appear in the documented recipe.

3. **Subgame-mode caveat.** Same as v1.4.0 §Caveats(3) — `solve_hunl_preflop` requires both `initial_hole_cards`, so each solve is a fully-determined subgame rather than a range-aware equilibrium. Population-level Nash claims must be qualified accordingly.

4. **Tip moved during retest.** `d0b7b34` → `98fb503` (PR #69 merged mid-session; that PR is a HUNL postflop hard-fail guard, unrelated to the preflop limp-or-fold action menu). My run was against the workspace tree present at retest invocation; v1.7.0 package init.py was active throughout. Verdict is robust to this tip-shift (no preflop changes between the two commits).

## Orchestrator-Needed Flags

- **No code-side bugs found.** Engine behavior on the limp-or-fold action menu is correct end-to-end at v1.7.0 (identical to v1.4.0).
- **Type A docs-debt persists:** DEVELOPER.md "extending the action abstraction" still not landed. No new code work needed; orchestrator can:
  - File a docs-debt ticket for DEVELOPER.md §5a (carry-over from v1.4.0).
  - Decide whether to amend the W4.2 spec criteria (3-trash) and (4) to acknowledge the subgame-mode structural mismatch — at this point this has been a known caveat for 3 days (v1.4.0 retest 2026-05-23 → today).
- **No release-narrative impact.** v1.7.0 status is unchanged; W4.2 remains PARTIAL in the persona test status table.

## Bottom-line answer

**Verdict: PARTIAL. Type A (DEVELOPER.md docs-debt). No regression from v1.4.0.** Wiring + action restriction PASS, premium-limp PASS, wall-clock PASS; trash-fold structurally FAIL and aggregate-limp heuristic structurally inapplicable in subgame mode (same caveat as v1.4.0). No engine patch required.

## References

- Prior retest: `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/W4_2_v1_4_0_retest.md`
- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/persona_acceptance_spec.md:69`
- Retest brief: `/Users/ashen/Desktop/poker_solver/docs/pr_proposals/priya_retest_W4_2.md`
- Persona test status (today): `/Users/ashen/Desktop/poker_solver/docs/persona_test_status_2026-05-26.md`
- Time budgets: `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/persona_time_budgets.md`
- Driver: `/tmp/w42_retest.py` (read-only; ephemeral)
- Machine-readable summary: `/tmp/w42_retest_summary.json`
- v1.8 SIMD bench (non-load-bearing here, ~1.0×): `/Users/ashen/Desktop/poker_solver/docs/v1_8_simd_perf_benchmark_2026-05-26.md`
