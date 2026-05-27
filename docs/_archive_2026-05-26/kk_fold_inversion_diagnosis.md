# KK `fold=0.9998` River Side-Probe — Math Diagnosis

- **Date:** 2026-05-23
- **Source anomaly:** `docs/persona_test_results/W2_3_post_v1_7_0_result.md` line 49 & Caveat §3
- **Method:** Pure poker math (no engine execution); 15-min budget
- **Status:** READ-ONLY diagnosis

## Reproduced fixture spec

From the W2.3 side-probe driver `/tmp/w23_minimal_driver.py`:

| Field | Value |
|---|---|
| Board | `Qs 7h 2d Th 4c` (river — 5 cards) |
| Hero range | `['KK', 'QQ']` |
| Villain range | `['KK', 'QQ']` (symmetric per engine constraint) |
| `initial_contributions` | `(500, 250)` (BB=500, SB=250 — flop-c-bet asymmetric carry-over) |
| Pot at river start | 750 |
| `bet_size_fractions` | `(0.5, 1.0)` |
| Iterations | 50 |
| Hero player | 1 (BB) |

## KK equity on `Qs 7h 2d Th 4c` vs `{KK, QQ}`

Board cards consumed: `Qs, 7h, 2d, Th, 4c` (no straight possible: Q-T-7 gap, 7-4-2 gap; rainbow w/ only 2 hearts → no flush).

**Hero holds KK** (uses 2 of 4 kings). Remaining deck:
- Kings remaining: 2 → villain `KK` combos = `C(2,2) = 1`
- Queens remaining (one Q on board): 3 → villain `QQ` combos = `C(3,2) = 3`

**River matchups (no more cards to come):**
- KK vs KK: tie (50% equity, chop)
- KK vs QQ: QQ has flopped set of queens (`QQQ` w/ board Q) → KK loses 100% (0% equity)

**Combo-weighted equity:**
```
E[KK] = (1 × 0.50 + 3 × 0.00) / (1 + 3) = 0.500 / 4 = 0.125 = 12.5%
```

## Pot odds (facing a SB bet on river)

Pot at start of river action = 750. For each `bet_size_fraction`:

| Bet frac | Facing bet | Pot after bet | Pot odds (call required equity) |
|---|---|---|---|
| 0.5 | 375 | 1125 | 375 / (1125+375) = **25.0%** |
| 1.0 | 750 | 1500 | 750 / (1500+750) = **33.3%** |

(Asymmetric `(500,250)` contributions affect history/SPR but not the river-pot-odds calc, since pot=750 either way.)

## Defend-vs-fold heuristic

Required equity to call: **25% (min) – 33.3% (max)**.
KK actual equity: **12.5%**.
12.5% << 25%. → **Folding is mathematically correct**.

## Verdict

**ENGINE-CORRECT.** The `KK fold=0.9998` output is not an inversion bug — it is the mathematically correct answer for this degenerate 2-class symmetric fixture.

### Why the watchdog's heuristic mismatched

The W2.3 spec heuristic ("KK near-100% defend on Q-high") assumes a **realistic** villain range with bluffs, weaker pairs, missed draws, etc. In a **symmetric 2-class {KK, QQ} range** with a queen on the board:

- 3 of 4 villain combos are QQ (set of queens, dominates KK 100%)
- Only 1 of 4 villain combos is KK (chop)
- KK's combo-weighted equity collapses to 12.5%
- This is below ANY reasonable bet's pot-odds threshold → near-pure fold

The 2-class probe was designed as a **smoke test that the aggregator runs on a river** (per W2.3 doc Caveat §3: "NOT a valid KK sanity check"). It was never a position-mapping check.

### Secondary check: is there a position artifact?

The `initial_contributions=(500,250)` is asymmetric, but on the river with no further streets it does not invert who-acts-first vs equity-required. Even if hero/villain are swapped, the math is symmetric (both holders of KK face the same dominated spot vs the QQ-heavy combo distribution). No position bug needed to explain 99.98% fold.

## Recommended action

**NONE.** Engine output matches hand-math. No v1.7.x or v1.8 bug to file.

**Optional follow-up (LOW priority):** If a future river-only W2.3 probe is run, use a **realistic villain range** (e.g., `[KK, QQ, AQs, AK, JJ, TT, 99, A5s_bluff]`) — the watchdog's "KK near-100% defend" heuristic only holds against ranges with bluffs and weaker value. A symmetric 2-class fixture where one class makes a set on the board will always invert the heuristic.

## No source changes

Read-only diagnosis. No edits to `poker_solver/`, `tests/`, `scripts/`. Only this doc written. No commits, no pushes.
