# Preflop 6-Experiment Ratio Comparison (2026-05-28)

**Scope:** 6 preflop solves at 100 BB, raise cap = 4, 2500 iters each, True Path B 169-class fast engine (`_rust.solve_hunl_preflop_rvr_class169`).

**Per-experiment menus:** open sizes (bb) and reraise multipliers scale together — they share the same number in each config so the ratio between bet level and raise increment is the experimental axis.

## Wall time

| Exp | Wall (s) | Menu | Ante |
|-----|----------|------|------|
| E1 | 0.64 | opens=2.5 rerais=2.5 | none |
| E2 | 0.55 | opens=5.0 rerais=5.0 | none |
| E3 | 2.09 | opens=2.5/5.0 rerais=2.5/5.0 | none |
| E4 | 0.64 | opens=2.5 rerais=2.5 | 1.0bb |
| E5 | 0.64 | opens=5.0 rerais=5.0 | 1.0bb |
| E6 | 2.32 | opens=2.5/5.0 rerais=2.5/5.0 | 1.0bb |
| **total** | **6.90** | | |

## Table 1 — aggregates (combo-weighted across 1326 starting hands)

```
                  E1         E2         E3         E4         E5         E6
                  no-ante    no-ante    no-ante    ante       ante       ante
                  open=2.5   open=5.0   both       open=2.5   open=5.0   both
SB RFI fold          15.7%     21.9%     23.1%      0.0%      0.0%      0.0%
SB RFI limp          43.5%     46.0%     28.7%     82.6%     71.3%     48.2%
SB RFI raise+        40.8%     32.0%     48.2%     17.4%     28.7%     51.8%

BB fold               2.5%     53.0%     19.4%      0.0%      3.3%      1.5%
BB call              84.1%     36.4%     64.8%     86.2%     84.1%     77.7%
BB 3-bet+            13.3%     10.7%     15.8%     13.8%     12.6%     20.8%
```

*BB row is conditional on SB opening — averaged across the open sizes weighted by how often SB chose each one.*

## Engine convention note (matters for Table 2 labels)

`bet_to = current_bet + multiplier × prev_bet` where `prev_bet = max(last_bet_size, big_blind)` and `last_bet_size` is the PREVIOUS raise INCREMENT, not the absolute bet. With ante=1bb, the BB blind contribution is 2bb (= 1bb blind + 1bb ante), so SB's open-to-2.5bb raises by 0.5bb (clamped to BB floor = 1bb), making the BB's 3-bet increment SMALLER than in the no-ante case. This is why E6's BB-facing-2.5bb-open 3-bet sizes (e.g. `raise_to_500` = 5.0bb) differ from E3's (e.g. `raise_to_625` = 6.25bb).

## Table 2 — size breakdown for the two-size configs (E3, E6)

```
                                       E3 (no ante)   E6 (ante)
SB open 2.5bb mass                    30.8%          23.0%
SB open 5.0bb mass                    17.5%          28.8%

BB 3-bet+ vs SB's 2.5bb open
  3-bet to 6.25bb (raise_to_625)              2.4%        0.0%
  3-bet to 10.00bb (raise_to_1000)           15.0%        0.0%
  all-in                                      0.7%        3.5%
  3-bet to 5.00bb (raise_to_500)              0.0%        3.4%
  3-bet to 7.50bb (raise_to_750)              0.0%       22.9%

BB 3-bet+ vs SB's 5.0bb open
  3-bet to 15.00bb (raise_to_1500)            7.7%        0.0%
  3-bet to 25.00bb (raise_to_2500)            3.6%        0.0%
  all-in                                      0.4%        0.4%
  3-bet to 12.50bb (raise_to_1250)            0.0%        0.0%
  3-bet to 20.00bb (raise_to_2000)            0.0%       13.1%

```

## Spot-check table — dominant action by hand × experiment

SB-row format: dominant action at the SB-RFI infoset (`FOLD` / `LIMP` / `RAISE`). BB-row format: dominant action at the BB-facing-smallest-open infoset (`FOLD` / `CALL` / `3BET`).

| Hand | E1 SB | E1 BB | E2 SB | E2 BB | E3 SB | E3 BB | E4 SB | E4 BB | E5 SB | E5 BB | E6 SB | E6 BB |
|------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|
| `AA` | RAISE | 3BET | RAISE | 3BET | RAISE | 3BET | LIMP | 3BET | LIMP | 3BET | LIMP | 3BET |
| `KK` | RAISE | 3BET | RAISE | 3BET | RAISE | 3BET | LIMP | 3BET | RAISE | 3BET | RAISE | 3BET |
| `QQ` | RAISE | 3BET | RAISE | 3BET | RAISE | 3BET | LIMP | 3BET | RAISE | 3BET | RAISE | 3BET |
| `TT` | RAISE | 3BET | LIMP | 3BET | RAISE | 3BET | LIMP | 3BET | LIMP | 3BET | RAISE | 3BET |
| `55` | RAISE | CALL | LIMP | CALL | RAISE | CALL | RAISE | CALL | LIMP | 3BET | RAISE | 3BET |
| `22` | LIMP | CALL | RAISE | 3BET | RAISE | CALL | LIMP | CALL | LIMP | CALL | LIMP | 3BET |
| `AKs` | LIMP | 3BET | RAISE | 3BET | LIMP | 3BET | LIMP | 3BET | RAISE | 3BET | LIMP | 3BET |
| `AQs` | RAISE | 3BET | LIMP | 3BET | RAISE | 3BET | RAISE | 3BET | LIMP | 3BET | LIMP | 3BET |
| `T9s` | RAISE | CALL | LIMP | 3BET | RAISE | 3BET | LIMP | 3BET | LIMP | 3BET | LIMP | 3BET |
| `65s` | LIMP | CALL | RAISE | 3BET | RAISE | CALL | LIMP | CALL | LIMP | CALL | LIMP | CALL |
| `AKo` | RAISE | 3BET | RAISE | 3BET | RAISE | 3BET | LIMP | 3BET | LIMP | 3BET | RAISE | 3BET |
| `KQo` | RAISE | 3BET | RAISE | CALL | RAISE | 3BET | RAISE | 3BET | RAISE | 3BET | RAISE | 3BET |
| `Q9o` | RAISE | CALL | RAISE | CALL | RAISE | CALL | RAISE | CALL | RAISE | CALL | RAISE | CALL |
| `J8o` | RAISE | CALL | LIMP | FOLD | RAISE | CALL | LIMP | CALL | RAISE | CALL | RAISE | 3BET |
| `72o` | FOLD | FOLD | FOLD | FOLD | FOLD | CALL | LIMP | CALL | LIMP | FOLD | RAISE | CALL |

## Observations
**Ante effect (pot-odds prediction: ante widens defense).** At fixed menu, ante shifts SB-RFI fold by -15.7/-21.9/-23.1 pp (E4-E1, E5-E2, E6-E3) and BB-facing-open fold by -2.5/-49.7/-17.9 pp. Negative SB-fold delta = wider RFI when ante is present, consistent with pot-odds prediction.

**Menu freedom (1 size → 2 sizes).** SB total RAISE mass changes by E1→E3=+7.4pp, E2→E3=+16.2pp, E4→E6=+34.4pp, E5→E6=+23.2pp. If menu freedom merely splits existing raise mass across sizes, totals should stay close to a same-ante 1-size baseline; large changes would indicate the optimal raise-frequency itself moves when the strategy can mix sizes.

**Tightest SB equilibrium:** E3 (SB fold  23.1%). **Widest SB equilibrium:** E4 (SB fold   0.0%).

**SB/BB symmetry.** Pearson correlation between SB-RFI fold and BB-vs-open fold across the 6 experiments: r=+0.72. Positive r → when SB plays tighter (folds more), BB also plays tighter (folds more) — i.e. both players co-tighten when stack-to-pot is deeper relative to the bet size. Negative r → asymmetric.

**Caveats.** 100bb-stack deep-cap solves have known Nash indifference manifolds (see project memory `feedback_nash_multiplicity_acceptance.md`); any single 2500-iter strategy is one realization on the manifold, not a unique equilibrium. Aggregate fold/raise rates are robust across realizations; per-class spot-check actions (especially close-to-indifferent hands like 22, 65s, T9s) may differ run-to-run within the same equilibrium class. The deltas BETWEEN experiments are still meaningful because the menu or ante change is the dominant signal compared to within-equilibrium drift.


## One-line summary

Wall: total 6.90s; SB fold by exp E1-E6:  15.7% /  21.9% /  23.1% /   0.0% /   0.0% /   0.0%; BB fold by exp E1-E6:   2.5% /  53.0% /  19.4% /   0.0% /   3.3% /   1.5%.
