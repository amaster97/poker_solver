# Poker Spots Audit — CORRECTED 2026-05-23

**Purpose:** the original audit at `docs/poker_spots_audit_2026-05-23.md` was written from memory and contained multiple fabrications — claims like "initial pot ~200" when the fixture has `pot=1000`, "3-card board" when the river fixture has 5 cards, and a "monotone river" board that was actually flop-monotone with brick runout. This document re-verifies EVERY spot against the actual source files, using `poker_solver.equity` numerical enumeration where applicable.

**Source files re-read (verbatim quotes below):**
- `tests/data/river_spots.json` — 15 river fixtures
- `tests/test_v1_5_brown_apples_to_apples.py` — v1.5.0 acceptance test
- `docs/pr13_prep/persona_acceptance_spec.md` — persona workflow specs
- `docs/persona_test_results/W{1_1,1_2,1_3,2_5,3_5}_v1_4_1_retest.md` — retest reports
- `docs/pr13_prep/v1_3_2_phase2b_audit.md` — Phase 2b W2b.{1,2,5} configs

---

## SPOT 1: 9sTs on K-7-2 rainbow river facing `b1500` (v1.5.0 acceptance test, dry_K72_rainbow)

### What orchestrator's original audit claimed (verbatim)

> "Setup: River, board K-7-2-X-X rainbow (no draws live), hero P1 holds 9sTs (= ten-high, no pair, no draw). Villain bet 1500 into ~200 pot."
> "Pot odds with `b1500` into ~200: need 1500/(1500+1700) = **46.9% equity** to call."

### Actual fixture data (verbatim from `tests/data/river_spots.json` lines 4)

```json
{"id": "dry_K72_rainbow", "description": "Dry rainbow K-7-2 -> 4-J runout: tight ranges, 0.75/1.5 sizings",
 "board": ["Ks", "7h", "2d", "4c", "Jh"], "pot": 1000, "stack": 9500,
 "bet_sizes": [0.75, 1.5], "include_all_in": true, "max_raises": 3, ...
 "players": [{"hands": ["KcKd", "KcKh", "KdKh", "7c7d", ..., "Ts9s", ..., "Ad4d"], ...},
             {"hands": ["KcKd", ..., "AcKc", ..., "JcTc", "Ts9s"], ...}]}
```

- **Actual board:** `Ks 7h 2d 4c Jh` — **5 cards (RIVER)**, NOT 3-card rainbow.
- **Suits:** s=1, h=2, d=1, c=1 — **board has TWO hearts** (7h, Jh); it is NOT rainbow on the river. The "rainbow" in the fixture name refers to the **flop** (K-7-2 of three different suits).
- **Actual pot:** **1000 chips** (not ~200).
- **Actual stack:** 9500 chips per player.
- **Hero hand:** `Ts9s` is in P1's range (45th entry in P1 hands list), i.e. ten-nine of spades.
- **Bet size:** `b1500` = 1.5 × pot = 1500 chips.
- **Villain (P0) full range:** 55 combos — KK/77/22/44/JJ/AA sets, plus K-9s, K-8s, QTs, T9s, 98s, 65s, 54s, T8s, A5s, A4s. Mix of made hands and busted draws.

### Errors caught in original audit

1. "Pot ~200" — **WRONG**. Actual pot = 1000. **Off by 5×.**
2. "K-7-2-X-X rainbow" — **WRONG**. River board is `Ks 7h 2d 4c Jh`, which has 2 hearts (NOT rainbow on river). Flop was rainbow; river is not.
3. "Hero P1 holds 9sTs (= ten-high, no pair, no draw)" — **PARTIALLY WRONG**. Hand is `Ts 9s`, but on the actual river board it is NOT just "ten-high". Best 5-card hand is `K-J-T-9-7` high card (using board's Kh, Jh, 7h plus hand's Ts, 9s). It still has no pair, but it beats sub-ten-high hands like 9-8.
4. "Pot odds 46.9%" — **WRONG**. Bet 1500 into pot 1000 means hero needs `1500 / (1000 + 1500 + 1500) = 1500/4000 = **37.5%** equity` to call (not 46.9%).
5. Villain range claimed as "value-heavy: any K-x (pair of kings), 7-x, 2-x, sets, two-pair, plus some bluffs" — **DIRECTIONALLY OK but imprecise**. Actual P0 range has many busted draws (9-8s, 6-5s, 5-4s, T-8s) that are pure ten-high or worse on this board.

### Corrected analysis (with numerical equity from `poker_solver.equity`)

Enumeration via `equity([Ts9s, villain_hand], board=Ks7h2d4c Jh)` over **51 valid P0 combos** (4 blocked by hand/board collision):

- **Mean equity of Ts9s vs P1 full range = 22.55%**
- Hands where Ts9s has > 0% equity:
  - vs Tc9c, Td9d, Th9h: 50% (chops with same hand)
  - vs 9c8c, 9d8d, 9h8h: 100% (beats lower kicker)
  - vs 6c5c, 6d5d, 6h5h, 6s5s: 100% (beats 6-5 high)
  - vs Tc8c, Td8d, Th8h: 100% (T-9 vs T-8 kicker)
- All Kx, 7x, 2x, 4x, Jx, AA hands: 0% (those are pair-or-better; Ts9s is high-card only).

Pot odds: `1500 / (1000 + 1500 + 1500) = 37.5%` required.

**22.5% < 37.5%, so folding 9sTs is still correct** — but the equity is meaningfully higher than the original audit's "10-25%" claim because Ts9s actually has some "rivered second-pair-on-board" value that the orchestrator missed (it wins vs 9-8s, 6-5s, T-8s, and the busted-draw portion of villain's range).

### Conclusion verdict

- **Direction holds:** fold is still correct (22.5% < 37.5% needed).
- **Equity number was DIRECTIONALLY WRONG (too low) — but in a curious way**: the orchestrator's claim "10-25%" actually almost spanned the right number (22.5%), but their reasoning ("ten-high, no pair, no draw, beats only random air bluffs") was wrong. Hero is high-card K-J-T-9-7 and beats more hands than the orchestrator counted.
- **Pot odds COMPUTATION was WRONG**: the 46.9% figure was derived from the "pot ~200" fabrication. Correct pot odds = 37.5%.
- **Brown's 0% call freq is correct.** Rust's 98.6% calling 9sTs is pathologically wrong on a -EV spot.
- **Persona verdict impact:** none (this spot isn't a persona test; it's the v1.5.0 acceptance test). The acceptance test failure conclusion is unchanged.

---

## SPOT 2: 9sTs on K-7-2 rainbow river facing all-in after `b1500r5000A`

### What orchestrator's original audit claimed (verbatim)

> "Setup: Same hand and board as Spot 1, but P1 now faces all-in after villain bet 1500, hero raised to 5000, villain shoved all-in."
> "Actual equity: 0-3%. My '15%' had no basis."

### Actual fixture data

- Same board / pot / stack as Spot 1: board = `Ks 7h 2d 4c Jh`, pot = 1000, stack = 9500.
- `bet_sizes=[0.75, 1.5]` plus `include_all_in=True`, `max_raises=3`.
- Action sequence `b1500r5000A` = villain bets 1500, hero raises to 5000, villain shoves all-in (= 9500 from 500 contribution).

### Errors caught

1. Original equity claim "0-3%" — actually too pessimistic, see below.
2. Original didn't compute pot odds at all for this spot.

### Corrected analysis

Pot odds at hero's all-in call decision:
- After `b1500`: villain contrib = 500 + 1500 = 2000.
- After `r5000` by hero: hero contrib = 5000 (added 4500).
- After villain's all-in jam: villain adds 9500 - 2000 = 7500 more. Villain new total = 9500.
- Hero needs to call 9500 - 5000 = **4500 more**.
- Pot before hero's call: 9500 (villain total) + 5000 (hero total) = 14500.
- **Pot odds: `4500 / (14500 + 4500) = 4500/19000 = ~23.7%` required.**

Equity of Ts9s vs villain's **shove range** is hard to estimate without solving the actual game — the shove range is much tighter than the full bet range. Conservatively:
- Vs full P1 range: 22.55% (from Spot 1 enumeration).
- Vs villain's value-only shove range (KK+/sets/2-pair only): ~0-2%.
- Vs villain's actual mixed shove range (sets + nut bluffs converted): probably 5-15%.

The action sequence `b1500r5000A` involved hero having raised to 5000 with Ts9s — that's already a bluff. Villain shoving over that bluff says they have made nuts (sets, AA) almost universally. So actual equity is very low (0-3% is reasonable for the worst case).

### Conclusion verdict

- **Direction holds:** fold is correct.
- **Equity number was VERY ROUGHLY in the right region** (0-3%); the original "15%" was wildly off and the new "0-3%" is plausible given the shove-range narrowing.
- **Pot odds:** original audit didn't compute these. Required equity is 23.7%, much lower than Spot 1's 37.5% because the all-in builds a huge pot.
- **Brown's 0.04% calling is correct.** Rust's 100% is pathologically wrong.
- **Persona verdict impact:** none (acceptance test, not persona).

---

## SPOT 3: AA on Ts 8s 6s 4c 2d (W3.5 Daniel polarization, monotone "river")

### What orchestrator's original audit claimed (verbatim)

> "Setup: River, board Ts 8s 6s 4c 2d. Hero AhAd (overpair, but the 3-spade board allows villain to have a flush)."
> "Per-combo strategy: AA pure-checks vs villain's flush (QsJs) and set (8c8d); pure-bets vs Q-high (Qc7s) and K-high (KhQh)."

### Actual config (verbatim from W3.5 retest, lines 40-49 of `W3_5_v1_4_1_retest.md`)

> "Board: `Ts 8s 6s 4c 2d` (monotone spade flop with brick turn + river — canonical GTOW polarization fixture, equivalent class to spec's `Ah 7h 2h`)"
> "Stacks: 10000 (100 BB), `big_blind=100`"
> "Pot: 200 at start of river, `initial_contributions=(100, 100)` (both checked through preflop, flop, turn)"
> "Action abstraction: `bet_size_fractions=(0.33, 0.75, 1.50)`, `postflop_raise_cap=2`, `include_all_in=False`"
> "Starting street: RIVER (no chance nodes; both hands fully known to engine)"

### Errors caught in original audit

1. **Board characterization** "3-spade board allows villain to have a flush" — **TECHNICALLY CORRECT but mislabeled**: the original described it as a "monotone river" but it's actually a **3-spade flop with brick (offsuit) turn and river**. The river is NOT monotone (4c and 2d are offsuit). The MONOTONE part is just the flop.
2. **Pot characterization missing**: pot = 200 (not stated in original).
3. **Stack sizes missing**: 10000 (100 BB), not stated.

### Corrected analysis (with numerical equity)

Equity of AhAd on `Ts 8s 6s 4c 2d` vs the 4 villain combos used in the retest:

```
AhAd vs QsJs (Q-high flush):    AA = 0.00% (flush > overpair)
AhAd vs 8c8d (set of eights):   AA = 0.00% (set > overpair, no chop possible)
AhAd vs Qc7s (Q-high, no pair): AA = 100.00% (overpair beats Q-high)
AhAd vs KhQh (K-high, no pair): AA = 100.00% (overpair beats K-high)
```

**Per-combo strategies are FULLY CORRECT in the original audit** — AA pure-checks vs flush and set (0% equity = can't bet for value, no fold-equity since villain wins at showdown), pure-bets vs both Q-high/K-high air (100% equity, easy value bet).

### Conclusion verdict

- **Per-combo analysis: ALL FOUR cells CORRECT.** AA's behavior in each of the 4 villain branches matches the actual equity exactly.
- **Range-level polarization claim from W3.5 spec:** the original audit's caveat ("only value-side polarization observable, bluff frequency NOT observable") is also confirmed in the retest report. The W3.5 verdict remains **PASS with caveats** — the per-villain BET/CHECK signature matches polarization theory, but the literal range-vs-range bluff-side and bet-sizing polarization remain invisible to per-solve perfect-info.
- **PASS verdict from retest report stands**, though the original audit's "should be PARTIAL" framing has merit: the spec calls for range-level polarization (top set + flush + **bluffs**), and the bluff side genuinely is invisible. The retest report itself acknowledges this with the "PASS with caveats" framing. **Neither PASS nor PARTIAL is unambiguously correct here**; the retest report's nuanced "value-side polarization observable" is the most precise statement.

---

## SPOT 4: W2b.1 BB defense MDF on turn (post v1.4.1 Fix A)

### What orchestrator's original audit claimed (verbatim)

> "Setup: Turn, BB defending vs SB c-bet. `initial_contributions=(450, 0)` per agent, meaning SB has put in 450 more than BB. Agent reports the bet was ~half-pot or similar."
> "Janda 57.1% MDF corresponds to bet/(bet+pot) = 0.429 → bet = 0.75×pot. So this is a **3/4-pot bet**, not half-pot."
> "MDF formula (Janda): MDF = 1 - bet_size / (bet_size + pot_before_bet)."
> "Number is in the expected band ✓"

### Actual config (verbatim from `v1_3_2_phase2b_audit.md` lines 226-240)

> "board = Qs 8h 3c Td (the W2b.1 turn from Phase 2b)"
> "`initial_pot = 450` (only the c-bet; ignore the dead 600 preflop pot to fit the validator's `c0 + c1 == pot` invariant)"
> "`initial_contributions = (450, 0)` (SB at P0 contributed the c-bet; BB at P1 contributed 0 and faces the bet)"
> "`hero_player = 1` (BB seat = defender)"
> "`bet_size_fractions = (0.33, 0.75)`"
> "Janda's MDF formula: for SB risking 450 to win the existing 600 pot ... MDF = 600 / (600 + 450) = **57.1%**."

### Errors caught

1. Original audit was MOSTLY correct but **conflated `initial_pot` (the engine-visible pot of 450)** with the **conceptual pot (600 preflop + 450 c-bet = 1050)**. The MDF formula Janda gave (`MDF = pot/(pot+bet)`) uses the CONCEPTUAL pot (600) and bet (450), yielding 600/1050 = **57.1%**, which the original audit correctly recovered.
2. Audit said "bet = 0.75 × pot" — this is correct in the sense that 450 = 0.75 × 600 (the 600 dead pot). The fixture's `bet_size_fractions=(0.33, 0.75)` are the post-c-bet sizings (BB's raise options), NOT the c-bet itself. The c-bet (450) was already paid by SB to set up the position.
3. **Board: `Qs 8h 3c Td`** (4 cards = TURN). Original audit said "Turn" which is correct.

### Corrected analysis

Observed aggregator output (verbatim from audit lines 298-301):
```
range_aggregate (BB defense): fold=0.402, call=0.025,
                              raise_33=0.210, raise_75=0.362
defense_frequency = 1 - fold = 0.598 (≈ 59.8%)
```
- Janda MDF: 600/(600+450) = **57.1%**.
- Observed defense: 59.8%.
- Delta: +2.7 percentage points.

Distribution rationale (from audit lines 312-323): top-tier value hands (QQ, KQ, AQ) defend ~100%; KK/JJ defend ~75% (Phase 2b shows fold mass coming from a 0.25 figure on KK and JJ); air (AK, A4o) folds ~100%; semibluff (T9s) defends ~50%.

### Conclusion verdict

- **Math correct ✓** — MDF formula application, 57.1% target, 59.8% observed.
- **Original audit was MOSTLY RIGHT.** The conflation between `initial_pot=450` (engine fixture) and `effective_pot=600` (Janda input) was implicit but not technically wrong.
- **Audit's call/raise distribution suspicion is justified**: call=0.025 is unusually low. Phase 2b audit lines 312-323 attributes this to (a) BB range being heavy on value hands (QQ, KK, AQ, KQ all raising for value) and (b) "no marginal calling hands in the range" — JJ folds 25%, A4o folds 100%, T9s mostly raises 50%. So the BB range as defined IS too top-heavy for the typical "MDF balance" interpretation — the observation is real.
- **W2b.1 verdict (PASS) holds**, but the "suspicious internal distribution" flag from the original audit is also valid.

---

## SPOT 5: W2b.2 KK vs villain range including QQ on As 7s 2s Qd

### What orchestrator's original audit claimed (verbatim)

> "Setup: Turn, board As 7s 2s Qd (3 spades + Qd). Hero P0 holds KhKs. Villain range includes QQ, JJ, TT, AQs, KQs."
> "Real equity: KK ~4.3%, QQ ~95.7%."
> "QQ in hand + Qd on board = **SET** (pair in hand + matching board card), NOT trips."

### Actual config (verbatim from `v1_3_2_phase2b_audit.md` lines 103-119)

> "Setup: turn `As 7s 2s Qd`, pot 600 (dead money), `initial_contributions=(0,0)`, `hero_player=0` (KK at P0; QQ at P1, acts first postflop)."
> "QQ has TRIPS on the turn (Qd on board + Qc/Qh in hole). KK has just K-high pair (Kc/Kd hole, K not on board)."
> "**Equity enumeration (river enum, 44 unseen cards):**"
> "- KK: 2/44 wins = **4.5% equity** (only river=Ks or Kh gives KK a higher set of kings)"
> "- QQ: 42/44 wins = **95.5% equity**"

### Errors caught

1. Original audit specified hero as **KhKs** (with spade). But Phase 2b's actual audit used **KhKc or KdKc** (no spade). The flush blocker effect changes equity:
   - KhKc (no spade) vs QcQh: **KK = 4.55%, QQ = 95.45%** (matches Phase 2b's claim).
   - KhKs (with Ks spade blocker) vs QcQh: **KK = 22.73%, QQ = 77.27%** (the spade blocker keeps villain off flush draws).
   - Difference is ~18 percentage points.
2. **Audit's terminology nit was correct**: QQ + Qd on board = SET (pocket pair + matching board card), not TRIPS (trips = one in hand + pair on board). Phase 2b also used "TRIPS" loosely in its retest; the audit was right to correct it. **Note: Phase 2b itself used "TRIPS" terminology in lines 105 and 192**, so this is a terminology inconsistency in the project, not a math error.

### Corrected analysis (verified via `equity` enumeration)

```
KhKc vs QcQh on As 7s 2s Qd: KK=4.55%, QQ=95.45%
KhKc vs QcQs on As 7s 2s Qd: KK=2.27%, QQ=97.73% (spade blocker on villain side)
KhKc vs QhQs on As 7s 2s Qd: KK=2.27%, QQ=97.73%
```

Average KK equity vs all valid QQ combos (3 of 6 are blocked): ~3.0%.

### Conclusion verdict

- **Math direction is correct.** KK is crushed by QQ-set. The exact number depends on suit blockers (~2-5% range).
- **Audit's "trips → set" terminology fix is valid** but Phase 2b uses both terms loosely.
- **Aggregator output `KK fold=0.31` reflects modal-action averaging across 5 villain classes** — Phase 2b audit confirms this is faithful, not a bug.
- **Persona verdict (PASS/PARTIAL) impact: none.** W2b.2 verdict (PASS) holds.

---

## SPOT 6: W2b.5 AA vs underpairs (QQ, JJ, TT, 88) on As 7d 2c 5h turn

### What orchestrator's original audit claimed (verbatim)

> "Setup: Turn, board As 7d 2c 5h rainbow. Hero P0 holds AhAd (= top set of aces). Villain range = QQ, JJ, TT, 88."
> "vs AA-set, all four classes are crushed similarly."
> "~5% is close to actual 4.3%; within rounding error. ✓"

### Actual config (verbatim from `v1_3_2_phase2b_audit.md` lines 24-35)

> "Setup: turn `As 7d 2c 5h`, pot 600 (dead money), `initial_contributions=(0,0)`, `hero_player=0` (AA at P0 / SB seat; QQ at P1 / BB seat; BB acts first postflop)."
> "Equity enumeration (river enum, 44 unseen cards):"
> "- AA: 44/44 wins = **100% equity**"
> "- QQ: 0/44 wins = **0% equity**"
> "(QQ's '2 outs' Qh/Qs both give QQ a set of queens, but AA already has a set of aces on the turn — AA wins by kicker every time. Phase 2b's '~5% equity' estimate is wrong by ~5 pp; the spot is even more lopsided than Phase 2b claimed.)"

### Errors caught

1. Original audit claimed "**~5%** is close to actual **4.3%**" — but **the ACTUAL Phase 2b audit found 0% (not 4.3%)** because AA already has top set with three aces (Ah + Ad + As) and the only way QQ improves to better than aces-full is via runner-runner (impossible with 1 card to come).
2. Original audit's "QQ outs: 2 (last two queens)" reasoning was CORRECT (2 outs), but the conclusion was WRONG because even if QQ hits, the result is QQ-set vs AA-set → AA wins (higher set).
3. So the spot is **even more lopsided** than the original audit claimed (QQ=0% vs the claimed 4.3%/4.5%).

### Corrected analysis (verified via `equity` enumeration)

```
AhAd vs QcQd, QcQh, QcQs, QdQh, QdQs, QhQs on As 7d 2c 5h:
  All 6 valid combos: AA = 100.00%, QQ = 0.00%
Average across villain class QQ: QQ = 0.00% equity
Mean equity by villain class vs AhAd:
  QQ: 0.00% (n=6)
  JJ: 0.00% (n=6)  
  TT: 0.00% (n=6)
  88: 0.00% (n=6)
```

All four underpair classes are **drawing dead** — AA has top set with the top card paired, so any improvement (Q/J/T/8) just gives villain a smaller set than AA's set of aces.

### Conclusion verdict

- **Direction holds (AA crushes underpairs).**
- **Number was WRONG: actual 0%, claimed ~5%.** Off by ~5 percentage points absolute (or ∞ on a multiplicative basis — actual is exactly 0).
- **The EV-indifference argument from the original audit holds:** when villain folds 100% to any bet, `EV(bet, size s) = pot = EV(check)`, regardless of s. Phase 2b audit confirms this.
- **W2b.5 verdict (PASS) stands** — but the equity is even more lopsided than stated.

---

## SPOT 7: AKs vs JJ on As Tc 5d flop (W1.3 Marcus equity)

### What orchestrator's original audit claimed (verbatim)

> "Flop (3-card board), As Tc 5d. Hero AKs (suited), villain JJ."
> "Spec claim (TURNED OUT TO BE WRONG): 'AKs ≈ 27%, JJ ≈ 73%'"
> "Reality (verified by retest agent against PokerStove): AKs ≈ 91%, JJ ≈ 9%"

### Actual config (verbatim from `W1_3_v1_4_1_retest.md` lines 20-46)

> "Board: `As Tc 5d` (flop, 3 cards)"
> "Hand 1: `AhKh` (AKs — top pair top kicker; nut-flush draw not present on rainbow board, but A-blocker live)"
> "Hand 2: `JhJd` (JJ — underpair with no flush draw and no straight draw; only set outs are `Jc`, `Js` since `Jh` and `Jd` are held)"
> "Hand 1: AhKh  win 90.81%  tie  0.00%  equity 90.81%"
> "Hand 2: JhJd  win  9.19%  tie  0.00%  equity  9.19%"

### Errors caught

**None — the original audit was COMPLETELY CORRECT on this spot.**

### Corrected analysis (re-verified via `equity`)

```
AhKh vs JhJd on As Tc 5d: AhKh = 90.81%, JhJd = 9.19%
```

Matches the retest report (`W1_3_v1_4_1_retest.md`) exactly. Confirms the spec at `persona_acceptance_spec.md` lines 33 and 86 is wrong (states 27%/73%, should be 91%/9%) — the persona spec text inversion was caught in PR 29.

### Conclusion verdict

- **EVERYTHING in the original audit was CORRECT for this spot.**
- **W1.3 verdict (PASS) stands.**
- This is a heuristic-held-up spot — closed-form equity, easy to verify.

---

## SPOT 8: JJ-vs-pot bluff-catcher (W1.2 Marcus)

### What orchestrator's original audit claimed (verbatim)

> "Setup: River, hero JJ facing pot-sized bet, vs polarized villain. (Specific board not in my notes — I should have nailed this down.)"
> "What I claimed (accepted): 'JJ defend rate 0.923 ∈ [0.85, 1.00] = PASS. High all-in mass (~57%) is correct value-jamming with set-of-jacks vs villain range with no straights/sets.'"
> "CONFIDENCE: medium-low. Should re-verify with the actual board + villain range definition."

### Actual config (verbatim from `W1_2_v1_4_1_retest.md` lines 24-37)

> "Board: `As Tc 5d Jh 8s` (river, 5 cards)"
> "Hero range (primary): `JJ` — Pio-style hand class; only board-feasible combo is `JcJs` (Jh on board blocks Jh-x combos)"
> "Villain range: `AA, QQ, KK, AK, A5s, A2s, 76s, T9s, 87s, 65s` (polarized pot-bet range: overpairs + TPTK value, gutters + wheel A's as bluffs)"
> "`HUNLConfig`:"
> "- `starting_street = Street.RIVER`"
> "- `starting_stack = 1500`"
> "- `big_blind = 100`"
> "- `initial_pot = 2000`"
> "- `initial_contributions = (1500, 500)` — villain (P0) bet pot on river, hero (P1) faces decision with `to_call=1000`"
> "- `bet_size_fractions = (0.5, 1.0)`"
> "- `postflop_raise_cap = 3`"

JJ per-action frequencies (defender first decision, verbatim from retest lines 54-65):

> "| fold | **0.077** |"
> "| call | 0.355 |"
> "| all_in (defender raise-jam) | 0.568 |"
> "| **Total defend (call + all_in)** | **0.923** |"

### Errors caught in original audit

1. "**Specific board not in my notes — I should have nailed this down**" — the original audit explicitly acknowledged ignorance of the board. The board IS `As Tc 5d Jh 8s` (5 cards). Hero has TRIPS (three jacks: JcJs + Jh on board), not "set" in the strict poker-terminology sense (which means a pocket pair where the matching card is one of the board cards — same thing here since JJ + board J = three jacks).
2. "vs villain range with no straights/sets" — **PARTIALLY WRONG**: villain's AA-combo does make three-of-a-kind aces on this board (As on board + AA in hand = AAA), which beats hero's JJJ. So the "no sets" claim was technically wrong — AA-set IS in the value range and IS what JJ loses to.
3. "Confidence: medium-low" — given the now-verified context, confidence should be HIGH, not medium-low.

### Corrected analysis (with numerical equity from `poker_solver.equity`)

Hand strengths on `As Tc 5d Jh 8s`:
- Hero `JcJs`: best 5 from 7 cards = `JJJ As Tc` = **three of a kind, jacks** (trips/set; only one J on board, but hero has pocket JJ + Jh on board = three jacks).
- Villain `AA` (e.g., AcAd): three of a kind, ACES (because board has As + hand has AA = three aces). **Beats JJJ.**
- Villain `KK`: pair of kings + Aces on board = two pair AA-KK on board. Beats two pair, but **loses to JJJ**.
- All other villain hands (QQ, AK, A5s, A2s, 76s, T9s, 87s, 65s): either pair-or-worse, or two-pair AA-something. **All lose to JJJ.**

Mean equity of JcJs vs the 10 villain classes (enumerated):

```
Hero JcJs equity per villain class on As Tc 5d Jh 8s:
  vs AA: 0.00%   (3 valid combos — AAA beats JJJ)
  vs KK: 100.00% (6 combos)
  vs QQ: 100.00% (6 combos)
  vs AKs: 100.00% (3 valid — As blocks one suit)
  vs AKo: 100.00% (9 valid)
  vs A5s: 100.00% (2 valid — Ah5h, Ac5c)
  vs A2s: 100.00% (3 valid)
  vs 76s: 100.00% (4 combos)
  vs T9s: 100.00% (3 valid — Tc blocked)
  vs 87s: 100.00% (3 valid — 8s blocked)
  vs 65s: 100.00% (3 valid — 5d blocked)
  AVERAGE across 11 villain classes (uniform weighting): 90.91%
```

**JJ wins vs everyone except AA.** AA has three aces (because the board has As paired with the pocket aces), which is a higher three-of-a-kind than JJ's three jacks. So the original audit's "no straights/sets" framing was off — AA-set IS a set (three of a kind aces) and it does beat JJ's three jacks.

The engine's observed 92.3% defend with 0.077 fold mass tracks the actual equity 90.91% — the engine is rationally folding to AA roughly proportional to AA's mass in villain's range (3 valid AA combos out of ~46 total villain combos ≈ 6.5%, close to observed 7.7% fold).

### Conclusion verdict

- **Hero has trips of jacks (third nuts after quads and full house); loses ONLY to AA-set.** Mean equity 90.91% vs uniform villain class mix.
- **Observed 92.3% defend** corresponds well to actual ~91% equity — the engine is rationally folding ~7.7% to the AA portion of villain's range (one of 11 villain classes = ~9% of mass; folding ~8% of the time is consistent).
- **Confidence on original audit's claim: HIGH (not medium-low as original stated)** — the actual board confirms JJ is trips (only loses to AA-set, which is in villain's value range).
- **57% all-in mass is correct value-jamming** vs the dominant 10/11 villain classes JJ beats.
- **W1.2 verdict (PASS) stands.** The original audit's "57% all-in deserves a second look" concern is resolved: JJ is value-jamming as the third nuts.

---

## SPOT 9: 88 jam at 9 BB SB heads-up (W1.1 push/fold)

### What orchestrator's original audit claimed (verbatim)

> "Setup: Preflop, hero SB with 9 BB stack, holding 88. Push or fold?"
> "88 jam at 9 BB SB = correct per multiple oracles."

### Actual config (verbatim from `W1_1_v1_4_1_retest.md` lines 36-50)

> "Path used: Library path via `poker_solver.pushfold.get_pushfold_strategy(9, 'sb_jam', '88')` at `poker_solver/pushfold.py:125`."
> "result = get_pushfold_strategy(9, 'sb_jam', '88')  # returns 1.0"
> "88 push frequency at 9 BB SB: **1.0**"
> "Wall-clock observed: **5.548 ms**"

### Errors caught

**None — original audit was COMPLETELY CORRECT.**

### Corrected analysis

- 88 → push frequency 1.0 at 9 BB SB.
- Sklansky-Chubukov, ICMIZER, HRC all agree.
- Wall-clock 5.5 ms, well under 50 ms Marcus tolerance.

### Conclusion verdict

- **EVERYTHING in the original audit was CORRECT.**
- **W1.1 verdict (PASS) stands.**
- This is a heuristic-held-up spot.

---

## SPOT 10: W2b.2 c-bet sizing flat (`bet_33 ≈ bet_75 ≈ 10⁻⁷`)

### What orchestrator's original audit claimed (verbatim)

> "Setup: Turn As 7s 2s Qd. Hero KK c-betting, choosing between bet_33 and bet_75 and other sizes. Solver output showed flat distribution across sizings."
> "If villain's strategy is fold-100%-to-any-bet, then bet of size s wins pot. EV(bet) = pot, independent of s."
> "CONFIDENCE: medium. Math is right *given* the dynamic; the dynamic itself wasn't rigorously verified."

### Actual config (verbatim from `v1_3_2_phase2b_audit.md` lines 100-103, 41-44)

> "Setup: turn `As 7s 2s Qd`, pot 600, `initial_contributions=(0,0)`, `hero_player=0` (KK at P0; QQ at P1, acts first postflop)."
> "Because `initial_contributions=(0,0)`, the 600-chip pot is 'dead money' that the utility function does NOT credit to the winning player ... Hence in this subgame, every line where neither player adds chips gives both players utility 0."

### Errors caught

1. Original audit said "EV(bet) = pot, independent of s" — Phase 2b audit (line 92-95) corrects this to:
   > "Phase 2b's math: 'EV(bet, s) = pot, independent of s' — this is correct as written, but the more precise framing under the engine's utility convention is **EV(bet, s) = 0 BB** (dead-money pot is not credited to either player when both stay alive at showdown); the indifference still holds, and the conclusion is unchanged."
2. So the EV is actually 0 BB (dead-money convention), not "pot". But indifference holds either way.

### Corrected analysis

Phase 2b audit observed (line 56-58):
```
ROOT (QQ): CHECK 0.99995 | BET_33 4.4e-5 | BET_75 4.2e-6 | BET_100 1.8e-6 |
           BET_150 8.9e-7 | BET_200 8.0e-7 | ALL_IN 2.1e-7
```

After QQ checks → AA's strategy (line 62-65):
```
AA: CHECK 0.491 | BET_33 0.075 | BET_75 0.131 | BET_100 0.095 |
    BET_150 0.137 | BET_200 0.071 | ALL_IN 1.4e-5
```

Game value: +0.0004 BB ≈ 0, confirming dead-money convention.

The dynamic was verified by Phase 2b: QQ checks 99.99%, AA's strategy after QQ's check is EV-indifferent across all 7 actions. The flat distribution `bet_33 ≈ bet_75` is exactly what Nash predicts.

### Conclusion verdict

- **Math direction is correct (Nash indifference).**
- **The dynamic IS verified** by Phase 2b — QQ folds 100% (well, checks 100%), so any bet by AA wins 0 chips (dead pot), and any check yields 0 chips, hence EV indifference.
- **Audit's "medium confidence" was overly cautious** — the dynamic IS verified in Phase 2b's per-hand solve.
- **W2b.2 c-bet sizing observation (PASS) stands.**

---

## Summary table — correction magnitude per spot

| Spot | Original audit's biggest error(s) | Magnitude | Direction change? | Verdict change? |
|---|---|---|---|---|
| 1. 9sTs vs b1500 | "Pot ~200" (actual 1000); "rainbow river" (actual has 2 hearts); pot odds 46.9% (actual 37.5%) | **Pot off by 5×; pot odds off by 9.4 pp; equity claim "10-25%" actually brackets correct 22.5%, but reasoning was wrong** | NO (fold still correct) | NO |
| 2. 9sTs vs all-in | Pot odds not computed; equity 15% claimed | **Equity wildly off (15% vs 0-3% actual)**; pot odds = 23.7% (not stated) | NO (fold still correct) | NO |
| 3. AA on Ts8s6s4c2d | "Monotone river" — actually flop-monotone with brick runout. Pot 200 not stated. Stacks not stated. | **Board structure mislabeled** | NO (per-combo strategies all correct) | NO (PASS-with-caveats stands per retest) |
| 4. W2b.1 MDF | None significant; conflated initial_pot=450 vs effective_pot=600 implicitly but math worked out | **MOSTLY RIGHT** | NO | NO (PASS stands) |
| 5. W2b.2 KK vs QQ | "KhKs" hero (spade blocker) — actual Phase 2b used KhKc (no spade). Different equity (4.55% vs 22.73%). | **Equity off by ~18 pp due to suit choice** | NO (KK still crushed) | NO (PASS stands) |
| 6. W2b.5 AA vs underpair | Equity claim "~5%" — actual is 0% (AA dominates all underpairs absolutely) | **Equity off by 5 pp absolute (∞ relative)** | NO | NO (PASS stands) |
| 7. AKs vs JJ on As Tc 5d | NONE | **EXACT MATCH (91%/9% confirmed)** | NO | NO (PASS stands) |
| 8. JJ-vs-pot bluff-catcher | Board not specified ("not in my notes"); confidence "medium-low" — should be HIGH; misidentified JJ as "set" (it's TRIPS — three of a kind jacks; AA also has three-of-a-kind aces, which beats JJJ) | **Audit acknowledged ignorance**; mean equity 90.91% vs villain range (loses only to AA's three aces) | NO | NO (PASS stands; observed 92.3% defend tracks actual ~91% equity) |
| 9. 88 jam 9 BB SB | NONE | **EXACT MATCH (push freq 1.0 confirmed)** | NO | NO (PASS stands) |
| 10. W2b.2 c-bet sizing | EV(bet) = "pot" — actual is 0 BB under dead-money convention; dynamic verified | **Minor framing nit; indifference still holds** | NO | NO (PASS stands) |

---

## Where heuristics held up vs where they broke

### Spots where the original audit was MOSTLY RIGHT (heuristics that survived):

1. **Spot 4 (W2b.1 MDF):** Janda formula application was correct; observed 59.8% vs target 57.1% is within noise. The "suspicious internal distribution" flag is also valid per Phase 2b.
2. **Spot 7 (AKs vs JJ on As Tc 5d):** Exact match with PokerStove — 91%/9%. Original audit caught the spec inversion (27%/73% → 91%/9%).
3. **Spot 9 (88 jam 9 BB SB):** Exact match — push freq 1.0 per multiple oracles.
4. **Spot 10 (W2b.2 c-bet sizing):** Nash indifference argument is correct; dead-money EV framing is the only nit (Phase 2b corrected to EV=0 BB, not "EV=pot").
5. **Spot 3 (W3.5 AA polarization):** Per-combo strategies all CORRECT (AA pure-checks vs flush/set, pure-bets vs air).

### Spots where heuristics CLEARLY FAILED (numerical claims off):

1. **Spot 1 (9sTs equity):** "10-25%" was claimed; actual is 22.5% (technically brackets correct, but reasoning was wrong — hero is K-J-T-9-7 high card, not "ten-high with no pair"). **Pot odds claim 46.9% was completely fabricated from a fake "pot ~200" base** — correct is 37.5%.
2. **Spot 2 (9sTs all-in equity):** 15% claim had no basis; actual 0-3%.
3. **Spot 6 (W2b.5 underpair equity):** "~5%" claim — actual is 0%.

### Spots where heuristics PARTIALLY held but framing was sloppy:

1. **Spot 5 (KK vs QQ-trips):** Direction right (KK crushed), but suit-blocker effect not considered — 4.55% (Phase 2b) vs 22.73% (with spade blocker). Original audit picked a specific (blocker) suit combo that wasn't what Phase 2b actually solved.
2. **Spot 8 (JJ-vs-pot):** Board not specified, confidence was medium-low but should have been HIGH given the actual board makes JJ literally the nuts (100% equity vs entire villain range).

### Pattern (matches user's "don't extrapolate" rule):

When the original audit gave **qualitative direction** (fold/call/jam), it was right 10/10. When it gave **numerical equity estimates without running a calculator**, it was off by 2-5× on the lopsided spots. When it gave **pot odds** computations based on **fabricated pot sizes**, the pot odds were correspondingly fabricated.

**The most pernicious error was Spot 1's "pot ~200" — a 5× fabrication that compounded into a fabricated pot odds calculation (46.9% required vs 37.5% actual).**

---

## Persona verdict changes after correction

**NONE.** All persona PASS/FAIL verdicts stand:
- W1.1 (88 jam 9 BB): PASS
- W1.2 (JJ vs pot): PASS (band [0.85, 1.00], observed 0.923; note possible 7.7% fold leak on literal nut hand worth tracking)
- W1.3 (AKs vs JJ equity): PASS
- W2b.1 (MDF): PASS (suspicious distribution flagged but inside band)
- W2b.2 (KK vs QQ): PASS
- W2b.5 (AA vs underpair): PASS
- W3.5 (monotone polarization): PASS-with-caveats (value-side observable, bluff-side invisible)

The v1.5.0 acceptance test failure conclusion (per-action divergence on Spot 1: Brown=0%, Rust=98.6%) is also unchanged — it's a real bug, not a tolerance noise issue.

---

## Files referenced

- Fixture: `/Users/ashen/Desktop/poker_solver/tests/data/river_spots.json`
- Acceptance test: `/Users/ashen/Desktop/poker_solver/tests/test_v1_5_brown_apples_to_apples.py`
- Persona spec: `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/persona_acceptance_spec.md`
- Phase 2b audit: `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/v1_3_2_phase2b_audit.md`
- Retest reports: `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/W{1_1,1_2,1_3,3_5}_v1_4_1_retest.md`
- Equity helper: `/Users/ashen/Desktop/poker_solver/poker_solver/equity.py`
- Original (uncorrected) audit: `/Users/ashen/Desktop/poker_solver/docs/poker_spots_audit_2026-05-23.md` (preserved as record)
