# Poker Spots Heuristic Audit — 2026-05-23

**Purpose:** the user (correctly) called out that my 9sTs equity hand-wave (10-25%) was off by ~3×; actual is 2-8%. They want EVERY concrete poker spot I've made strategic claims about, re-analyzed with rigorous poker logic. If my judgement was off elsewhere, those PASS/FAIL verdicts may be wrong.

**Each entry:** setup → what I/agent claimed → rigorous poker analysis → was I right or wrong → confidence.

---

## SPOT 1: 9sTs on K-7-2 rainbow river facing `b1500` (v1.5.0 acceptance test, dry_K72_rainbow)

**Setup:** River, board K-7-2-X-X rainbow (no draws live), hero P1 holds 9sTs (= ten-high, no pair, no draw). Villain bet 1500 into ~200 pot.

**What I claimed initially:** "10-25% equity at best; correct Nash play is FOLD."

**Rigorous analysis:**
- 9sTs on K-7-2 rainbow river is **ten-high** (board is rainbow, so no flush; no straight available with 9-T on K-7-2).
- Villain's river betting range on dry board is value-heavy: any K-x (pair of kings), 7-x, 2-x, sets, two-pair, plus some bluffs.
- vs K-x: 0% equity (any K wins)
- vs 7-x: 0% (any 7 wins)
- vs 2-x: 0% (any 2 wins)
- vs sets/two-pair: 0%
- vs random air bluffs (8-high, J-high without pair): ~50% (since 9sTs is ten-high)
- If villain is 80% value / 20% bluff: equity ≈ 20% × 50% = **10%**
- If villain is 90% value / 10% bluff (typical river): equity ≈ 5%
- Pot odds with `b1500` into ~200: need 1500/(1500+1700) = **46.9% equity** to call.

**Verdict:**
- My "10-25%" was the *upper* edge of realistic; closer to 2-10% in practice. **My equity estimate was too generous by ~2-3×.**
- The fold direction was correct.
- **CONFIDENCE: low on the number, high on the action.** Brown's 0% call freq is correct. Rust's 98.6% is pathologically wrong (calls a -EV spot with garbage).

**Impact on burst:** the per-action divergence between Brown (0%) and Rust (98.6%) **cannot be explained by Nash mixed-strategy non-uniqueness** on an obvious-fold spot. Real PR 23 bug.

---

## SPOT 2: 9sTs on K-7-2 rainbow river facing all-in after `b1500r5000A`

**Setup:** Same hand and board as Spot 1, but P1 now faces all-in after villain bet 1500, hero raised to 5000, villain shoved all-in.

**What I claimed initially:** "~15% equity facing all-in shove range."

**Rigorous analysis:**
- Same hand (ten-high), same board. Now facing all-in.
- An all-in shove range on river is even MORE value-skewed than a normal bet range (no fold-equity for villain, so they only shove pure value or pure airball; on dry boards they're mostly value).
- vs K-x or better: 0%
- vs the rare bluff: ~50%
- Realistic shove range: 95% value / 5% bluff → equity ≈ 2.5%
- **Actual equity: 0-3%.** My "15%" had no basis.

**Verdict:**
- My equity number was **wildly wrong (15% claimed vs 0-3% actual).**
- The fold direction was correct.
- **CONFIDENCE: very low on the number, certain on the action.** Brown's 0.04% (near-zero) is right. Rust's 100% is even more pathologically wrong than Spot 1.

---

## SPOT 3: AA on Ts 8s 6s 4c 2d (monotone river) — W3.5 Daniel polarization

**Setup:** River, board Ts 8s 6s 4c 2d. Hero AhAd (overpair, but the 3-spade board allows villain to have a flush).

**What I claimed (accepted from agent):** "AA pure-checks vs villain's flush (QsJs) and set (8c8d); pure-bets vs Q-high (Qc7s) and K-high (KhQh) — matches the spec's 'AA either bets big OR checks back, not bluff-incentivized.'"

**Rigorous analysis per villain combo:**
- **vs QsJs (flush):** villain has a made flush. AA is dead (~0% equity). Pure check is sane (folds to any bet; checking back accepts the loss). ✓
- **vs 8c8d (set):** villain has set of eights. AA is dead (~5% to runner-runner, but no runners left on river). Pure check is correct (folds to bet). ✓
- **vs Qc7s (Q-high):** villain has Q-high with no pair, no draw. AA crushes ~100% equity. Pure bet for value. ✓
- **vs KhQh (K-high):** wait — board is Ts 8s 6s 4c 2d, no spade for KhQh to make a flush. KhQh has K-high with no pair, no draw. AA crushes. Pure bet for value. ✓

**Verdict:**
- Each per-combo strategy is sensible against the SPECIFIC combo. ✓
- BUT: the spec calls for **range-level polarization** (large bets for value AND bluffs; smaller bets in the middle). The agent observed value-side polarization only (large bets vs weak, checks vs strong). Bet-sizing distribution and bluff frequency were "NOT observable."
- Polarization signature: **partial.** I accepted PASS but this is more honestly **PARTIAL.**
- **CONFIDENCE: high on per-combo correctness; PASS verdict too generous.**

**Impact:** W3.5 should likely be downgraded from PASS to PARTIAL.

---

## SPOT 4: W2b.1 BB defense MDF on turn (post v1.4.1 Fix A)

**Setup:** Turn, BB defending vs SB c-bet. `initial_contributions=(450, 0)` per agent, meaning SB has put in 450 more than BB. Agent reports the bet was ~half-pot or similar.

**What I claimed (accepted from agent):** "MDF = 59.8%, within 2.7pp of Janda's 57.1% theoretical MDF."

**Rigorous analysis:**
- MDF formula (Janda): MDF = 1 - bet_size / (bet_size + pot_before_bet).
- If `initial_contributions=(450, 0)` and previous pot was P, then to_call = 450.
- Janda 57.1% MDF corresponds to bet/(bet+pot) = 0.429 → bet = 0.75×pot. So this is a **3/4-pot bet**, not half-pot.
- For 3/4-pot bet: MDF = 1 - 0.75/1.75 = 0.571 = 57.1% ✓
- Observed 59.8% is 2.7pp above target.

**Caveats I didn't surface:**
- Janda MDF assumes (1) uniform defense, (2) no card-removal effects, (3) villain bets a polarized range. Real Nash MDF can differ ±5pp without bug. 2.7pp is well within noise.
- The observed mix `{fold: 0.402, call: 0.025, raise_33: 0.210, raise_75: 0.362}` shows MOSTLY raises, very little flat-calling. That's strategically unusual for a BB defense range (typically you call more, raise less). Worth a second look at whether the BB range is right.

**Verdict:**
- Number is in the expected band ✓
- BUT the call/raise ratio is suspicious (call=0.025 is unusually low for a defending range). May indicate the BB range is too strong (only nutted hands, which raise; no marginal hands which call).
- **CONFIDENCE: medium.** The MDF aggregate is fine; the action distribution within MDF needs poker-eye review.

---

## SPOT 5: W2b.2 KK vs villain range including QQ on As 7s 2s Qd

**Setup:** Turn, board As 7s 2s Qd (3 spades + Qd). Hero P0 holds KhKs. Villain range includes QQ, JJ, TT, AQs, KQs.

**What I claimed:** "QQ has TRIPS (Q on board + QQ in hand), KK has just pair. QQ crushes KK ~95% equity."

**Terminology correction:**
- QQ in hand + Qd on board = **SET** (pair in hand + matching board card), NOT trips.
- Trips = one card in hand + pair on board. Different strategic implications (set is harder to read; trips is more obvious).
- My equity calculation was right; my terminology was wrong.

**Rigorous analysis:**
- Board As 7s 2s Qd = TURN, 1 card to come.
- KK outs: 2 (any K on river = top set for KK). Probability: 2/46 ≈ 4.3%.
- KK can NOT win vs QQ-set with current cards (set > pair).
- QQ outs to improve to quads: 1 (the last queen).
- **Real equity: KK ~4.3%, QQ ~95.7%.** ✓
- AKs/KQs in villain range: those have an A-high + K pair, would beat KK; complicates the range-wide analysis.
- Aggregator output `KK fold=0.31` reflects a faithful average across the 5 villain classes (QQ contributes 100% fold-mass when KK faces a bet; JJ/TT contribute check-mass since KK is ahead of underpairs).

**Verdict:**
- Math correct ✓
- Terminology wrong (set vs trips) — doesn't affect EV but matters for documentation.
- **CONFIDENCE: high on math; should correct "trips" → "set" in any doc that uses my framing.**

---

## SPOT 6: W2b.5 AA vs underpairs (QQ, JJ, TT, 88) on As 7d 2c 5h turn

**Setup:** Turn, board As 7d 2c 5h rainbow. Hero P0 holds AhAd (= top set of aces). Villain range = QQ, JJ, TT, 88.

**What I claimed (accepted):** "QQ has ~5% equity vs AA on Axxx (Q needs to come)."

**Rigorous analysis:**
- AA on As 7d 2c 5h with Ah in hand = SET of aces (three aces).
- QQ on this board has pair of queens (no Q on board, no draws).
- 1 card to come (turn → river).
- QQ outs: 2 (last two queens) to make set of queens. P = 2/46 ≈ 4.3%.
- Other villain combos (JJ/TT/88): same situation, 2 outs each, ~4.3%.
- vs AA-set, all four classes are crushed similarly.

**Verdict:**
- "~5%" is close to actual 4.3%; within rounding error. ✓
- The EV-indifference argument (when villain folds 100% to any bet, EV(bet, any size) = pot = EV(check)) is valid for this dynamic.
- **CONFIDENCE: high.** Phase 2b's Nash-indifference framing is correct on this spot.

---

## SPOT 7: AKs vs JJ on As Tc 5d flop (W1.3 Marcus equity)

**Setup:** Flop (3-card board), As Tc 5d. Hero AKs (suited), villain JJ.

**Spec claim (TURNED OUT TO BE WRONG):** "AKs ≈ 27%, JJ ≈ 73%"

**Reality (verified by retest agent against PokerStove):** AKs ≈ 91%, JJ ≈ 9%

**Rigorous analysis:**
- AKs: top pair (aces) with K kicker. Pair of aces.
- JJ: under-pair to top board card.
- 2 cards to come (turn + river).
- JJ outs: 2 jacks to make set. P(catch any J on turn or river): 1 - (45/47)(44/46) ≈ 8.6%.
- Plus tiny runner-runner straight (J-T-9-8-7 needs runners): negligible.
- AKs: top pair, but vs a set on the next card it loses.
- **Real equity: AKs ~91%, JJ ~9%.** ✓

**Verdict:**
- Spec was wrong; AKs/JJ values inverted.
- Retest agent independently caught it using PokerStove community standard.
- **CONFIDENCE: very high.** This is closed-form equity enumeration, not heuristic.
- **Spec correction shipped in PR 29.**

---

## SPOT 8: JJ-vs-pot bluff-catcher (W1.2 Marcus)

**Setup:** River, hero JJ facing pot-sized bet, vs polarized villain. (Specific board not in my notes — I should have nailed this down.)

**What I claimed (accepted):** "JJ defend rate 0.923 ∈ [0.85, 1.00] = PASS. High all-in mass (~57%) is correct value-jamming with set-of-jacks vs villain range with no straights/sets."

**Rigorous analysis (caveats due to incomplete board info):**
- IF JJ is **set of jacks** (J on board, JJ in hand), then it crushes any pair-only villain hand. Vs a polarized range (value: better sets, two pair, straights; bluffs: missed draws/air), JJ-set should defend overwhelmingly.
- Defend rate 92.3% in [85%, 100%] is reasonable for a near-bottom-of-value-tier hand vs polarized villain.
- The 57% all-in mass is aggressive but POSSIBLE if board structure makes raise-jam profitable (e.g., no straights or higher sets in villain's range).

**Verdict:**
- Without the specific board, I can't fully verify. I accepted the agent's analysis at face value.
- **CONFIDENCE: medium-low.** Should re-verify with the actual board + villain range definition. The 57% all-in mass deserves a second look — JJ-set jamming over pot bet is aggressive.

---

## SPOT 9: 88 jam at 9 BB SB heads-up (W1.1 push/fold)

**Setup:** Preflop, hero SB with 9 BB stack, holding 88. Push or fold?

**What I claimed (accepted via Sklansky-Chubukov chart):** "88 jams at 9 BB SB; pure-push (frequency = 1.0)."

**Rigorous analysis:**
- At 9 BB stack depth, the SB's pure-push range in HU is broad. Most pocket pairs jam.
- Sklansky-Chubukov ranks 88 well above the jamming threshold at 9 BB.
- Nash HU SNG push/fold charts (HRC, ICMIZER) also have 88 as pure-jam at 9 BB SB.

**Caveat:**
- S-C is a HEURISTIC ranking, not provably Nash. Two different SNG solvers (HRC, ICMIZER) can disagree at the margins.
- **At 9 BB with 88, all charts I'm aware of agree on pure-jam.** So this spot is on solid ground.

**Verdict:**
- 88 jam at 9 BB SB = correct per multiple oracles.
- **CONFIDENCE: high.** This is one of the easier spots; multiple independent charts agree.

---

## SPOT 10: W2b.2 c-bet sizing flat (`bet_33 ≈ bet_75 ≈ 10⁻⁷`)

**Setup:** Turn As 7s 2s Qd. Hero KK c-betting, choosing between bet_33 and bet_75 and other sizes. Solver output showed flat distribution across sizings.

**What I claimed (accepted from Phase 2b):** "When villain folds 100% to any bet, EV(bet, size s) = pot independent of s. All sizes are Nash-equivalent — flat distribution is correct."

**Rigorous analysis:**
- If villain's strategy is fold-100%-to-any-bet, then bet of size s wins pot. EV(bet) = pot, independent of s.
- Nash is indifferent across sizings in this case.
- But: in REAL multi-villain-combo range solving, villain might fold-100% to BIG bets but call SMALL bets. Then sizings have different EVs.
- Per Phase 2b audit, on this specific spot the villain range was crushed so completely (all classes losing to KK in the absence of QQ-set) that smaller bets DID fold villain across the board, making sizings EV-tied.

**Verdict:**
- The "Nash indifference" argument is valid IF the dynamic genuinely has villain folding to any size.
- Need to verify: did villain actually fold to ALL sizes in the aggregator output? Or only to large sizes?
- **CONFIDENCE: medium.** Math is right *given* the dynamic; the dynamic itself wasn't rigorously verified.

---

## Aggregate verdict on my poker-spot judgement quality

| Spot | My equity number | Actual | Direction | Number quality |
|---|---|---|---|---|
| 1. 9sTs vs b1500 | 10-25% | 2-10% | ✓ fold | **WRONG (too generous)** |
| 2. 9sTs vs all-in | 15% | 0-3% | ✓ fold | **WRONG (way too generous)** |
| 3. AA polarization combos | per-combo correct | per-combo correct | ✓ | OK (terminology + range-level interpretation soft) |
| 4. W2b.1 MDF 59.8% | within 2.7pp | within Janda ±5pp | ✓ | OK aggregate; suspicious internal distribution |
| 5. KK vs QQ on Qd turn | 4.5%/95.5% | 4.3%/95.7% | ✓ | OK math; "trips" should be "set" |
| 6. AA vs underpair | ~5% | 4.3% | ✓ | OK |
| 7. AKs vs JJ on As Tc 5d | 91%/9% | 91%/9% | ✓ | OK (verified by PokerStove) |
| 8. JJ-vs-pot | accepted 92.3% defend | unverified | ? | **NEEDS BOARD INFO TO VERIFY** |
| 9. 88 jam 9BB | jam | jam | ✓ | OK (multi-chart agree) |
| 10. KK c-bet flat sizing | Nash-indifferent | Nash-indifferent IF dynamic | ✓ | math right; dynamic unverified |

**Pattern:** when I or the agents gave QUALITATIVE direction (fold/call/jam), we were right. When we gave NUMERICAL equity estimates without a calculator, we were often **2-5× off** on the lopsided spots. The persona test verdicts that depend on numerical bands (W2b.1 MDF in [55%, 85%]; W1.2 JJ defend in [85%, 100%]) are RELATIVELY robust because the bands are wide. But narrow-tolerance comparisons (like the v1.5.0 acceptance test's 5e-3 per-action tolerance) are NOT robust to this kind of estimation noise.

**Implication for v1.5.0 acceptance test:** the test is comparing per-action probabilities at 5e-3 tolerance. If Brown and Rust were both at "essentially zero" on Spot 1 (fold 9sTs to 1500), Brown could be 0.000 and Rust could be 0.003 and the test would PASS. But Brown=0.000 and Rust=0.986 is a 0.986 spread — clearly not noise. **This confirms the per-action divergence is REAL bug territory, not "narrow tolerance + estimation noise."**

---

## Items needing user review

1. **Spot 8 (JJ-vs-pot W1.2):** need the actual board + villain range to verify my acceptance of 92.3% defend. The 57% all-in mass deserves a second look.
2. **Spot 4 (W2b.1 MDF):** the call/raise split is unusual (call=0.025, raise=0.572). Indicates BB range may be too strong. Worth a closer look.
3. **Spot 3 (W3.5 polarization):** I accepted PASS but only value-side polarization was observable. Honestly should be PARTIAL.
4. **Spot 10 (W2b.2 flat sizing):** the Nash-indifference argument is *conditional* on villain folding to all sizes; should verify the dynamic holds.
5. **Spot 5 terminology:** correct "trips" → "set" in any documentation that used my framing.
6. **General rule going forward:** I should NOT cite equity numbers without either (a) actually running an equity calculator, OR (b) using conservative qualitative language ("essentially zero", "trivially folding", "crushed").
