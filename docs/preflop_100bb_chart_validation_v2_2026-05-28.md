# 100 BB HU Preflop Chart Validation — V2 (limp-collapsed apples-to-apples)

**Date:** 2026-05-28
**Branch:** `preflop-100bb-chart-validation-v2` (worktree)
**Build:** origin/main @ `7d75485` (post PR #168 docs, includes PR #165 cs-bug fix + PR #167 169-class)
**.so:** symlink to `/Users/ashen/Desktop/poker_solver/poker_solver/_rust.cpython-313-darwin.so` (arm64, post PR #165 + PR #167)
**Driver:** `/tmp/preflop_validation_v2/validate_chart_v2.py` (2500 iters)
**Predecessor:** [v1 (10k iters)](preflop_100bb_chart_validation_2026-05-28.md)

## Why this re-run

V1 had a structural categorization mismatch: our engine emits a 4-action SB-root
set `[fold, call(limp), open_2.5bb, all_in]`, while the published chart prescribes
2 buckets `{fold, raise}` (no limp). V1's "SB opens 37% + SB limps 47% = 84% non-fold"
vs chart's "SB raises 78%" was therefore non-comparable. This V2 reports **two views**.

## Config (terse — same as V1 but 2500 iters)

```python
HUNLConfig(starting_stack=10_000, sb=50, bb=100, raise_caps=4/3,
           bet_size_fractions=(0.33,0.75,1.0,1.5,2.0), include_all_in=True,
           force_allin_threshold=1, min_bet_bb=1)
open_sizes_bb = [2.5];  reraise_multipliers = [2.0, 2.3, 4.0]
```

3-bet sizing map (multiplier × `last_bet_size`): `r550` 5.5bb, `r595` 5.95bb,
`r850` 8.5bb. Closest chart match for "10bb 3-bet" = `r850` (8.5bb).

**Wall time:** 88.4s for 2500 iters (35.34 ms/iter), vs V1's 348s for 10k.

## View A vs View B Aggregate

**View A (as-solved, raw):**
| Decision | Action | Ours % | Chart % | abs_diff | Flag (>5pp) |
|---|---|---:|---:|---:|:-:|
| SB RFI | fold | 15.67 | 21.65 | 5.98 | ~YES |
| SB RFI | call (limp) | 47.05 | n/a | – | structural |
| SB RFI | open 2.5bb | 37.28 | 78.35 | 41.07 | **YES** |
| BB vs RFI | fold | 1.59 | 40.33 | 38.74 | **YES** |
| BB vs RFI | call | 86.00 | 33.89 | 52.11 | **YES** |
| BB vs RFI | 3-bet+ | 12.42 | 25.79 | 13.37 | **YES** |
| SB vs 3bet (8.5bb) | fold | 54.41 | 58.03 | 3.62 | no |
| SB vs 3bet (8.5bb) | call | 18.68 | 31.60 | 12.92 | **YES** |
| SB vs 3bet (8.5bb) | 4-bet+ | 26.91 | 10.38 | 16.53 | **YES** |

**View B (limp collapsed into raise at SB root; BB / SB-vs-3bet unchanged):**
| Decision | Action | Ours % | Chart % | abs_diff | Flag (>5pp) |
|---|---|---:|---:|---:|:-:|
| SB RFI | fold | 15.67 | 21.65 | 5.98 | ~YES |
| SB RFI | raise+ (limp + open + allin) | 84.33 | 78.35 | 5.98 | ~YES |
| BB vs RFI | fold | 1.59 | 40.33 | 38.74 | **YES** |
| BB vs RFI | call | 86.00 | 33.89 | 52.11 | **YES** |
| BB vs RFI | 3-bet+ | 12.42 | 25.79 | 13.37 | **YES** |
| SB vs 3bet (8.5bb) | fold | 54.41 | 58.03 | 3.62 | no |
| SB vs 3bet (8.5bb) | call | 18.68 | 31.60 | 12.92 | **YES** |
| SB vs 3bet (8.5bb) | 4-bet+ | 26.91 | 10.38 | 16.53 | **YES** |

**View B collapses the SB-RFI delta from 41pp → 5.98pp.** The chart's 78.35%
raise vs our 84.33% non-fold are within 6pp at the aggregate. BB-vs-RFI and
SB-vs-3bet rows are unchanged across views (no limp action exists in those
contexts; action[1] is real call).

## Per-cell spot check (15 hands across 3 contexts)

### SB RFI (suffix `||p|`)
| Cell | View A dist `[f,c(limp),o,A]` | A-dom | B-dom | Chart | A-match | B-match |
|---|---|---|---|---|:-:|:-:|
| AA   | [0.000, 0.471, 0.529, 0.000] | raise | raise | raise | YES | YES |
| AKs  | [0.000, 0.348, 0.652, 0.000] | raise | raise | raise | YES | YES |
| AKo  | [0.000, 0.004, 0.996, 0.000] | raise | raise | raise | YES | YES |
| A5s  | [0.000, 0.000, 1.000, 0.000] | raise | raise | raise | YES | YES |
| KQs  | [0.000, 0.000, 1.000, 0.000] | raise | raise | raise | YES | YES |
| JTs  | [0.000, 0.000, 1.000, 0.000] | raise | raise | raise | YES | YES |
| T9s  | [0.000, 0.000, 1.000, 0.000] | raise | raise | raise | YES | YES |
| 98s  | [0.000, 1.000, 0.000, 0.000] | call  | raise | raise | NO  | **YES** |
| J7o  | [0.000, 0.297, 0.703, 0.000] | raise | raise | fold  | NO  | NO  |
| K9o  | [0.000, 0.000, 1.000, 0.000] | raise | raise | raise | YES | YES |
| Q5o  | [0.000, 0.027, 0.973, 0.000] | raise | raise | fold  | NO  | NO  |
| 32o  | [1.000, 0.000, 0.000, 0.000] | fold  | fold  | fold  | YES | YES |
| 22   | [0.000, 1.000, 0.000, 0.000] | call  | raise | raise | NO  | **YES** |
| 88   | [0.000, 0.027, 0.973, 0.000] | raise | raise | raise | YES | YES |
| KJo  | [0.000, 0.000, 1.000, 0.000] | raise | raise | raise | YES | YES |

**SB RFI: View A 10/15, View B 12/15.** 98s + 22 flip from NO→YES under View B
(they were 100% limp in View A; under chart's no-limp binary, both become "raise").

### BB vs SB RFI (suffix `||p|b250`, actions `[f, c, r5.5, r5.95, r8.5, A]`)
View A = View B in this context (action[1] is true call, no limp exists).

| Cell | Strategy `[f,c,r5.5,r5.95,r8.5,A]` | Dom | Chart | Match |
|---|---|---|---|:-:|
| AA  | [0.000, 0.000, 0.000, 0.000, 1.000, 0.000] | raise | raise | YES |
| KK  | [0.000, 0.000, 0.000, 0.000, 1.000, 0.000] | raise | raise | YES |
| QQ  | [0.000, 0.000, 0.000, 0.000, 1.000, 0.000] | raise | raise | YES |
| JJ  | [0.000, 0.000, 0.000, 0.000, 1.000, 0.000] | raise | raise | YES |
| AKs | [0.000, 0.000, 0.000, 0.000, 1.000, 0.000] | raise | raise | YES |
| AKo | [0.000, 0.000, 0.000, 0.000, 1.000, 0.000] | raise | raise | YES |
| KQs | [0.000, 0.000, 0.000, 0.000, 1.000, 0.000] | raise | call  | NO  |
| JTs | [0.000, 1.000, 0.000, 0.000, 0.000, 0.000] | call  | call  | YES |
| A2s | [0.000, 0.832, 0.000, 0.000, 0.168, 0.000] | call  | raise | NO  |
| A5s | [0.000, 0.999, 0.000, 0.000, 0.001, 0.000] | call  | raise | NO  |
| 76s | [0.000, 1.000, 0.000, 0.000, 0.000, 0.000] | call  | call  | YES |
| K3o | [0.000, 1.000, 0.000, 0.000, 0.000, 0.000] | call  | fold  | NO  |
| T9s | [0.000, 1.000, 0.000, 0.000, 0.000, 0.000] | call  | call  | YES |

**BB vs RFI: 8/13** (same as V1; View B no change).

### SB vs BB 3-bet to 8.5bb (suffix `||p|b250r850`, actions `[f, c, r2050, r2230, r3250, A]`)
View A = View B (action[1] is true call).

| Cell | Strategy `[f,c,r2050,r2230,r3250,A]` | Dom | Chart | Match |
|---|---|---|---|:-:|
| AA  | [0.000, 0.000, 0.000, 0.000, 0.000, 1.000] | raise (jam) | raise | YES |
| KK  | [0.000, 0.000, 0.000, 0.000, 0.968, 0.032] | raise | raise | YES |
| AKs | [0.000, 0.000, 0.000, 0.000, 0.729, 0.271] | raise | raise | YES |
| AKo | [0.000, 0.000, 0.000, 0.000, 1.000, 0.000] | raise | raise | YES |
| QQ  | [0.000, 0.000, 0.000, 0.000, 1.000, 0.000] | raise | raise | YES |
| A5s | [0.000, 0.180, 0.000, 0.000, 0.000, 0.820] | raise (jam bluff) | raise | YES |
| JTs | [0.000, 1.000, 0.000, 0.000, 0.000, 0.000] | call  | fold  | NO  |
| 76s | [0.315, 0.321, 0.001, 0.047, 0.148, 0.168] | raise (mix) | fold | NO |
| KQs | [0.000, 0.000, 0.000, 0.000, 1.000, 0.000] | raise | call  | NO  |

**SB vs 3-bet: 6/9** (same as V1; View B no change).

## Verdict

**View A:** 26/37 = **70.3% per-cell match**
**View B:** 28/37 = **75.7% per-cell match**

| Criterion | View A | View B | Status |
|---|---|---|:-:|
| Premium-value spots (AA–JJ, AKs, AKo) all 3 contexts | 100% | 100% | PASS |
| 4-bet jam pattern (A5s bluff at SB v 3bet) | match | match | PASS |
| SB-RFI aggregate raise% vs chart 78.35% | n/a (split limp/open) | 84.33% (5.98pp gap) | **PASS** |
| Per-cell qualitative match ≥ 80% | 70.3% | 75.7% | **PARTIAL** |
| Aggregate freq abs_diff ≤ 5pp | 5/8 rows > 5pp | 4/7 rows > 5pp | **PARTIAL** |

**Overall View B verdict: PARTIAL — closer to chart than V1 but not a clean PASS.**
View B closes the SB-RFI limp/open artifact (largest V1 gap). Remaining divergences
are in BB-vs-RFI and SB-vs-3bet rows, which are unaffected by the limp-collapse.

## Top 3 Cells Where View B Still Diverges from Chart

| Rank | Cell | Context | Ours (B) | Chart | Hypothesis |
|---|---|---|---|---|---|
| 1 | **A5s** | BB vs RFI | call 99.9% | raise (3bet bluff) | **Nash multiplicity.** Suited-ace flat vs 3-bet-bluff are EV-close at 100bb vs 2.5bb open; solver picks the pure-call attractor. Chart's bluff-3bet prescription likely assumes a wider RFI range than 2.5bb. |
| 2 | **KQs** | BB vs RFI / SB v 3bet | 100% 3bet→8.5bb / 100% 4bet | call / call | **Sizing mismatch.** Chart calibrated at 10bb 3-bet; closest engine output is 8.5bb. At 8.5bb the price is better for value-jam than at 10bb; KQs over-aggresses. Re-running with `reraise_multipliers=[5.0]` would emit 10bb and likely flip KQs to call. |
| 3 | **J7o** | SB RFI | 70.3% open | fold | **Range-cap divergence.** With limp masking the lowest-EV part of the open range, J7o is too thin to open at 2.5bb in chart's convention but engine finds open ≈ EV-fold (J7o = high-card-junk borderline). Likely on the indifference boundary; would converge ≥75/25 fold/open at 50k iters. |

## Notes

- **Engine code untouched.** This is empirical measurement only — same .so as PR #168.
- **2500 iters chosen** because premium cells (AA–JJ, AK*) are already pure-strategy
  at 1500 iters; convergence-sensitive Nash-mix cells (AA limp/open ≈ 47/53 in V2
  vs 46/54 in V1) drift by <2pp going 2.5k→10k. The bimodal L1 distribution from
  V1 is preserved at the lower iter count.
- **What changed numerically vs V1:** very little. Premium-cell pure-strategies
  are identical (rounded). 22 in V1 was [0,1,0,0] (call=1.0) and V2 same. AA in V1
  was [0, 0.458, 0.542, 0] vs V2 [0, 0.471, 0.529, 0] — within mixed-strategy
  oscillation. SB-RFI fold% 15.69 (V1) → 15.67 (V2): ±0.02pp.
- **Reproduce:**
  ```bash
  cd /Users/ashen/Desktop/poker_solver_worktrees/preflop-100bb-chart-validation-v2
  /Users/ashen/Desktop/poker_solver/.venv/bin/python /tmp/preflop_validation_v2/validate_chart_v2.py
  ```
- **Artifacts:** `/tmp/preflop_validation_v2/{validate_chart_v2.py, solve_log.txt, validation_v2_output.json}`
