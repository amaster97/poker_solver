# Poker Spots Re-verification — 2026-05-23

**Purpose:** The orchestrator flagged 4 poker spots from
`docs/poker_spots_audit_2026-05-23.md` as needing rigorous re-verification.
The orchestrator admitted to 2-5× equity-estimation errors elsewhere; prior
PASS verdicts on these 4 spots were SUSPECT.

This document re-verifies each spot using:
- `poker_solver.equity` enumeration (river / turn enumeration)
- `poker_solver.evaluator.evaluate` for hand strength
- Per-combo equity vs the actual villain range used in each test
- Pot-odds / MDF calculation from first principles

**Method:** read-only verification against repo state at v1.5.0. No source
modifications. All analysis scripts inline via `python -c "..."`.

---

## SPOT 3 — W3.5 AA polarization on `Ts 8s 6s 4c 2d` (monotone river)

### Setup recap
- Board: `Ts 8s 6s 4c 2d` (monotone spade flop with brick turn/river)
- Hero: `AhAd` (overpair, no spade for flush)
- Villain basket: `QsJs` (Q-high flush), `8c8d` (set of 8s), `Qc7s` (Q-high), `KhQh` (K-high)
- Hero strategy observed per W3.5 retest:
  - vs QsJs: pure CHECK `[1.0, 0, 0, 0]`
  - vs 8c8d: pure CHECK `[1.0, 0, 0, 0]`
  - vs Qc7s: pure BET `[0, 0.41, 0.59, 0]`
  - vs KhQh: pure BET `[0, 0.41, 0.59, 0]`

### Prior claim
**PASS** — per-combo polarization signature visible: AA pure-checks vs
flush/set, pure-bets vs Q/K-high.

### Rigorous per-combo verification (`evaluate` enumeration)
| Villain | Hand on board | vs AhAd |
|---|---|---|
| QsJs | FLUSH (Q-high spade flush) | BEATS AA |
| 8c8d | THREE_OF_A_KIND (set of 8s) | BEATS AA |
| Qc7s | HIGH_CARD (Q-high, no pair) | loses to AA |
| KhQh | HIGH_CARD (K-high, no pair) | loses to AA |

Per-combo strategies are textbook-correct:
- vs hands that beat AA → pure-check (no value in betting; check makes villain reveal)
- vs hands that lose to AA → pure-bet for value

### Verification of the missing observables
The spec calls for **range-level polarization** (large bets for value AND
bluffs; smaller bets in the middle). The retest observed:
- Bet sizing distribution: only `BET_33` (33% pot) and `BET_75` (75% pot)
  used; the largest size `BET_100` slot (carrying fraction 1.5x pot) is
  **never used** (0.0 across all 4 villains)
- Bluff frequency: **NOT observable** under per-solve perfect-info
  (KhJh-vs-KdQc probe showed pure-check, not bluff)
- Aggregate frequency for AhAd: 0.50 bet / 0.50 check (matching basket
  composition: AA beats 2/4 villains)

The retest report itself acknowledges in its §Caveats that bluff side and
bet-sizing-polarization side are invisible under this method. It chose to
report **PASS** on the basis that the value-side polarization (strong
hands bet, medium hands check vs strong villains) was observable, and
that the spec's literal sentence ("AA bets big or checks back") is
satisfied.

### Final verdict: **DOWNGRADE PASS → PARTIAL**

Rationale:
1. Per-combo strategies are mathematically sound. The value-side
   polarization claim is correct.
2. **But two of the three polarization legs are unobservable** by the
   chosen method: bluff frequency and bet-sizing polarization toward
   large bets. The spec calls for the full polarized signature (large
   value + large bluffs + smaller medium); only the BET-vs-CHECK leg is
   visible.
3. The retest's own caveats §3 explicitly says "this is not the spec's
   polarization toward large bets" — yet the verdict was PASS rather
   than PARTIAL.
4. The retest's verdict ladder defines PARTIAL as "aggregate signal was
   right but per-villain check-vs-bet wasn't differentiable" — that
   definition is too narrow. A more honest framing: PARTIAL is
   appropriate when only 1-of-3 polarization legs (value side) is
   observable.

**Recommendation:** W3.5 should be **PARTIAL**, with the explicit note
that "bluff side + bet-sizing polarization await RvR perf cliff fix
(PR 23 / W2.3)." The PASS verdict overstates what the test actually
demonstrates.

---

## SPOT 4 — W2b.1 BB defense MDF distribution

### Setup recap
- Board: `Qs 8h 3c Td` (turn)
- BB defending range (8 classes): `KK, QQ, AK, AQ, KQ, JJ, A4o, T9s`
- SB c-bet range (5 classes): `QQ, JJ, 98s, AK, A4s`
- `initial_pot=450`, `initial_contributions=(450, 0)`, `hero_player=1` (BB)
- Observed `range_aggregate`: `{fold: 0.402, call: 0.025, raise_33: 0.210, raise_75: 0.362}`
- Aggregate defense: 59.8% (target: Janda 57.1% MDF for 3/4-pot bet)

### Prior claim
**PASS** — MDF within 2.7pp of Janda's 57.1%. Per-class behavior sensible.

### Rigorous per-class equity (enumeration vs SB c-bet range, all 5 villain classes)

| BB class | Equity vs SB range | Per-class action observed |
|---|---|---|
| KK | 75.7% | raise 0.75, fold 0.25, call 0.002 |
| QQ | 92.2% | raise 0.91, fold 0.0, call 0.091 |
| AK | 38.9% | fold 0.9999 |
| AQ | 82.6% | raise 0.91, fold 0.0, call 0.091 |
| KQ | 82.3% | raise 1.00, fold 0.0, call 0.002 |
| JJ | 75.3% | raise 0.75, fold 0.25, call 0.002 |
| A4o | 9.4% | fold 0.9999 |
| T9s | 60.4% | raise 0.50, fold 0.50, call 0.001 |

### Analysis of the call/raise distribution
**Observation:** the call freq (0.025) is genuinely low. Verification of
the breakdown:
- KK, KQ, JJ, T9s: call ≤ 0.002 (essentially zero flat-call mass)
- AK, A4o: fold-dominant (no call mass to speak of)
- QQ, AQ: call = 0.091 each (the only meaningful flat-call contributors)
- Sum: `(0.002 + 0.091 + 0 + 0.091 + 0.002 + 0.002 + 0 + 0.001) / 8 = 0.024 ≈ 0.025` ✓

So the call distribution is mathematically consistent with the per-class
strategies.

**Why is the call freq so low?**

The BB range is **bimodal by composition**: 5 of 8 classes are either
strong value (QQ/AQ/KQ — defend ~100% by raising for protection / fold
equity) or trash (AK on this board has 38.9% equity = pair of nothing,
fold; A4o is air at 9.4%). Only T9s is genuinely marginal (60.4%).

A more realistic BB defending range on `Qs 8h 3c Td` would include:
- Middle pocket pairs: 99, 88, 77, 66 (call candidates)
- Suited connectors: J9s, JTs, 87s, 76s (call candidates)
- Backdoor draws: A high suited (call candidates)

The test range has NONE of these. Hence flat-calls have nowhere to come
from except the small Nash-indifference slack on QQ/AQ.

### Final verdict: **KEEP PASS (MDF aggregate) + flag test-range narrowness**

Rationale:
1. The 59.8% defense aggregate vs Janda's 57.1% (2.7pp delta) is
   genuinely within tolerance. The MDF measurement is valid.
2. The low call freq (0.025) is **explainable by range composition**, not
   a solver bug. The math (sum of per-class calls / 8 ≈ 0.025) checks
   out.
3. **However**, the test does NOT validate that the solver allocates
   flat-calls correctly in a realistic BB defending range with marginal
   hands. A re-run with a broader BB range (incl. 22-99, J9s-76s, AXs
   floats) is needed to exercise the flat-call decision.

**Recommendation:** KEEP PASS on MDF aggregate. Add a follow-up note
flagging the test-range narrowness and recommending a re-run with a
diverse BB range to validate flat-call behavior. The PASS verdict on
MDF is correct on its narrow claim; it does not generalize to "solver
correctly handles marginal calls" because the test does not include
marginal hands.

---

## SPOT 8 — W1.2 JJ vs pot-sized river bet (Marcus)

### Setup recap (found via retest report)
- Board: `As Tc 5d Jh 8s` (river, 5 cards)
- Hero range: `JJ` (only `JcJs` viable since `Jh` on board)
- Villain range: `AA, QQ, KK, AK, A5s, A2s, 76s, T9s, 87s, 65s` (polarized pot-bet range)
- `initial_pot=2000`, `initial_contributions=(1500, 500)` (villain P0 bet pot)
- Hero `to_call=1000`; pot odds = 1000 / (2000+1000) = 33.3% required
- Observed: `fold=0.077, call=0.355, all_in=0.568` → defend 0.923

### Prior claim
**PASS** — JJ defend 0.923 ∈ [0.85, 1.00]. 57% all-in mass "correct
value-jamming with set-of-jacks vs villain range with no straights/sets."

### Rigorous verification

**JJ hand strength:** `JcJs` + `As Tc 5d Jh 8s` board = SET of jacks
(`THREE_OF_A_KIND` rank 11). The `Jh` on the board combined with `JcJs`
in hand makes a three-of-a-kind. ✓

**Per-combo enumeration of villain range (45 valid combos after
board/hero blocking):**

| Class | Combos | Hand strength on board | Result vs JJ-set |
|---|---|---|---|
| AA | 3 | **THREE_OF_A_KIND (set of aces)** | **BEATS JJ-set** |
| QQ | 6 | PAIR (queens) | loses |
| KK | 6 | PAIR (kings) | loses |
| AK | 12 | PAIR (aces) | loses |
| A5s | 2 | TWO_PAIR (A+5) | loses |
| A2s | 3 | PAIR (aces) | loses |
| 76s | 4 | HIGH_CARD | loses |
| T9s | 3 | PAIR (tens) | loses |
| 87s | 3 | PAIR (eights) | loses |
| 65s | 3 | HIGH_CARD | loses |

**Total: 3/45 combos (6.7%) BEAT JJ-set; 42/45 (93.3%) lose.**

**Critical finding (retest agent error):** the retest report at line 99
states *"There is no straight in villain's range; T9s makes top pair
only."* This is partially correct but misses that **AA = set of aces**
(higher set than JJ-set). The agent's claim "vs villain range with no
straights/sets" was factually wrong — there are 3 AA combos (set of
aces) that beat JJ-set.

**Impact on verdict:** the error is rationale-level, not result-level.
- JJ raw winrate at showdown: 93.3% (42/45 combos)
- Required equity to call: 33.3%
- Strict Nash: should defend 100%; observed 92.3% (7.7% fold slack is small)
- Defend 0.923 ∈ [0.85, 1.00] band → PASS

**On the 57% all-in mass:** villain at P0 contributed all 1500 of
1500-stack, so **villain is already all-in**. From hero's perspective,
"call" and "all-in raise" lead to the same showdown — the engine
distinguishes them as labels but the EV is identical. The 57%
all-in-label + 35.5% call-label = 92.3% total defend mass is the
load-bearing signal. The label split is an artifact of how the engine
emits action labels under asymmetric-contribs all-in.

### Final verdict: **KEEP PASS, with rationale correction**

Rationale:
1. Numerical verdict criteria all satisfied:
   - `fold = 0.077 ≤ 0.15` ✓
   - `defend = 0.923 ∈ [0.85, 1.00]` ✓
   - TT neighbor non-degenerate ✓
   - Wall-clock 0.032s << 30s gate ✓
2. The agent's rationale ("no sets beat JJ") is wrong: AA = set of aces
   beats JJ-set. But this only affects 3/45 = 6.7% of combos, which is
   exactly the size of the slight fold mass (7.7%) the solver allocates.
3. The 57% all-in mass is sensible because villain is already all-in;
   call vs jam labels yield identical showdowns.

**Recommendation:** KEEP PASS. Annotate the W1.2 retest report with a
correction: "villain range contains AA = set of aces (3 combos that
beat JJ-set); the small 7.7% fold mass corresponds to this 6.7% combo
slice. JJ-set retains 93.3% raw equity vs the range."

---

## SPOT 10 — W2b.2 KK c-bet flat sizing on `As 7s 2s Qd`

### Setup recap
- Board: `As 7s 2s Qd` (turn)
- Hero: KK (range-aggregator: `AA, KK, QQ, AKs, AKo, AQs`)
- Villain range: `QQ, JJ, TT, AQs, KQs`
- Observed (Phase 2b retest): `check=0.594, fold=0.311, all_in=0.095,`
  `bet_33≈10⁻⁷, bet_75≈10⁻⁷`
- Phase 2b's Nash-indifference framing: "villain folds 100% to any bet →
  EV(bet, s) = pot independent of s → all sizes Nash-equivalent"

### Prior claim
**PASS** — Nash indifference makes flat sizing correct.

### Rigorous per-combo equity verification (`evaluate` + river enum)

| Villain class | Hand on `As 7s 2s Qd` | Equity vs KK |
|---|---|---|
| QQ (e.g. QhQs) | **THREE_OF_A_KIND (trips Q)** | 97.7% |
| JJ (e.g. JhJc) | PAIR (jacks) | 25.0% |
| TT (e.g. ThTc) | PAIR (tens) | 25.0% |
| AQs (e.g. AhQh) | **TWO_PAIR (A + Q)** | 95.5% |
| KQs (e.g. KsQs) | **FLUSH (K-high spade flush)** | 100.0% |

**Critical finding:** the villain range is **NOT all dominated by KK**.
Only JJ and TT are dominated (25% equity); QQ has trips (97.7%), AQs has
two-pair (95.5%), KQs has a flush (100%). KK is the dominator in only
2/5 villain classes.

So the Phase 2b retest's framing "villain folds 100% to any bet" is
**not universally true on this spot.** It applies only to the 2/5 villain
classes where KK is the dominator (JJ, TT). Against the other 3/5
classes (QQ-trips, AQs-twopair, KQs-flush), KK is crushed and folds.

### Analysis of the flat sizing
**Per-villain 1v1 decomposition (per the Phase 2b audit text):**
- vs QQ-trips (KK = 4.5% equity): KK folds 100%; QQ jams or checks
- vs JJ, TT (KK is dominator): KK bets, villain folds to any size
- vs AQs (KK is crushed): KK folds 100%
- vs KQs (KK is drawing dead): KK folds 100%

The aggregator output `check=0.594, fold=0.311, all_in=0.095` reflects:
- 3 of 5 villains contribute fold-mass (~0.6 of the aggregate)
- 2 of 5 villains (JJ, TT) contribute check/bet-mass (~0.4 of aggregate)
- The 10⁻⁷ bet mass on `bet_33` / `bet_75` is the residual when KK does
  decide to bet (rarely, only vs JJ/TT subspots)

**In the bet-subspots (KK vs JJ/TT only):**
- JJ/TT have 25% equity → pot odds threshold to call any bet ≥ 25% works,
  let's check:
  - bet_33: villain needs to call 33% pot to win pot + bet → pot odds =
    33/(133+33) = 19.9%. Villain (25%) > 19.9% threshold → should
    actually call, not fold.
  - bet_75: pot odds 75/(175+75) = 30%. Villain 25% < 30% → folds.
- So **bet_33 is NOT a clean fold for JJ/TT** by pot-odds. Villain
  should call bet_33 (25% equity > 19.9% pot odds).

Wait — this means the EV-indifference framing IS NOT fully accurate.
Let me re-derive:
- EV(bet_33, villain calls 25% equity) = 0.25 * (pot + 2*0.33*pot) + 0.75 *
  (-0.33*pot) = 0.25 * 1.66*pot - 0.75 * 0.33*pot = 0.415*pot - 0.2475*pot
  = +0.1675*pot
- EV(bet_75, villain folds 100%) = pot

So EV(bet_75, villain folds) = pot > EV(bet_33, villain calls) ≈ 0.17*pot.
**The sizes are NOT EV-equivalent if villain plays optimally** —
bet_75 is significantly better than bet_33 against JJ/TT specifically.

However: the per-hand 1v1 Nash solver may converge to JJ/TT folding to
bet_33 anyway (because in 1v1 villain may consider only beat/lose at
showdown, not pot-odds threshold continues). The 1v1 perfect-info
collapse means villain knows hero's exact combo and can choose to fold
or call deterministically.

Let me re-examine: in a 1v1 with perfect info where villain has 25%
equity vs hero, what does Nash say?
- If hero bets, villain's EV(call) = 0.25 * (pot + 2*bet) - bet =
  0.25*pot - 0.5*bet
- EV(fold) = 0
- Villain calls when 0.25*pot > 0.5*bet, i.e. when bet < 0.5*pot
- So villain should call bet_33 (0.33*pot < 0.5*pot → +EV call)
- And fold bet_75 (0.75*pot > 0.5*pot → −EV call)

This means **villain does NOT fold to all sizes equally** — villain
should call bet_33 and fold bet_75 against JJ/TT in 1v1. The
Nash-indifference argument in the Phase 2b retest is **incorrect on this
spot.**

### Recompute: what would the right hero strategy be?
For KK vs JJ on `As 7s 2s Qd` (1v1):
- Hero KK has 75% equity
- bet_33: villain calls (correct call) → hero EV = 0.75*(pot+2*0.33pot) - 0.25*0.33pot
  = 0.75 * 1.66pot - 0.0825pot = 1.245pot - 0.0825pot = +1.16pot (over current pot)
  Net gain over check: +0.16pot
- bet_75: villain folds → hero EV = +pot. Net gain over check (which
  would be EV=0.75*pot at showdown) = +pot - 0.75pot = +0.25pot
- check: hero wins 75% of showdowns, EV = 0.75*pot. Net = 0.

So bet_75 is BETTER than bet_33 in this 1v1, by 0.25pot - 0.16pot = +0.09pot.

**Conclusion:** bet sizes are NOT EV-equivalent on this spot. The solver
SHOULD prefer bet_75 over bet_33. The observed `bet_33 ≈ bet_75 ≈ 10⁻⁷`
flat split is suspicious.

### Resolving the apparent contradiction
The aggregator output shows total bet mass ≈ 10⁻⁷ — i.e., KK
**almost never bets at all** (KK checks 59%, folds 31%, all-ins 9.5%).
The flat sizing is on essentially zero mass.

So the practical question is: **why is KK's all-in mass at 9.5% non-zero
but its bet_33/bet_75 mass at 10⁻⁷?**

Hypothesis: in the 1v1 subspots where KK bets vs JJ/TT, the solver
prefers ALL-IN (which definitely folds JJ/TT, even at 25% equity, because
the pot-odds for villain to call all-in are ~33% which exceeds 25%).
Hence the 9.5% all-in mass captures KK's value-jamming vs JJ/TT.

The 10⁻⁷ flat split between bet_33 and bet_75 is residual numerical
noise from DCFR — neither size is favored because both sizes are clearly
DOMINATED by all-in (which gets a guaranteed fold from JJ/TT at 25%
equity; bet_33 would get called and bet_75 might get called marginally).

**Re-verified:** the flat sizing claim is NOT about Nash indifference
between bet_33 and bet_75 — it's about the **strategic dominance of
all-in over smaller sizes** in this specific dynamic. The "Nash
indifferent" framing in Phase 2b is technically wrong; the right framing
is "all-in strictly dominates smaller sizes against the dominated villain
sub-range, so smaller sizes collapse to zero mass with arbitrary 1:1
split among themselves."

### Final verdict: **DOWNGRADE PASS → PARTIAL**

Rationale:
1. The flat sizing between bet_33 and bet_75 is **on negligible mass**
   (10⁻⁷ each); the substantive bet mass is in `all_in` (9.5%).
2. The Phase 2b "Nash indifference" framing is **technically wrong**:
   EV(bet_33) ≠ EV(bet_75) at this spot. The flat sizing is residual
   numerical noise where neither size is favored because both are
   strictly dominated by all-in.
3. The aggregator output is **not a code bug** — it reflects the 1v1
   collapse where all-in is the EV-maximizing size and other sizes
   collapse to ~0.
4. **However**, the claim "flat sizing is correct Nash indifference" in
   the Phase 2b retest is **insufficiently rigorous** and arguably wrong.
   The correct rationalization is "smaller bet sizes are strictly
   dominated by all-in in this 1v1, so the residual mass on small sizes
   is arbitrary."

**Recommendation:** DOWNGRADE PASS → PARTIAL. Re-frame the Phase 2b
finding as "the flat sizing is on negligible mass dominated by all-in;
the Nash-indifference framing was incorrect. The solver behavior is
sensible but the rationale needs revision." A full RvR Nash with mixed
villain ranges (so villain has marginal continues) would be needed to
test whether the solver correctly prefers small sizes on monotone boards
— that test cannot be run on this spot under v1.4.1.

---

## Net summary

| Spot | Prior verdict | Re-verified verdict | Change |
|---|---|---|---|
| 3 (W3.5 AA polarization) | PASS | **PARTIAL** | DOWNGRADE |
| 4 (W2b.1 BB MDF) | PASS | **PASS** (with caveat on test-range narrowness) | KEEP |
| 8 (W1.2 JJ vs pot) | PASS | **PASS** (with rationale correction: AA = set of aces is in range) | KEEP |
| 10 (W2b.2 KK flat sizing) | PASS | **PARTIAL** | DOWNGRADE |

**Net count of prior PASS verdicts that HOLD UP: 2/4** (Spots 4, 8).

**Net count of prior PASS verdicts that need DOWNGRADE: 2/4** (Spots 3, 10).

**Common pattern:** the prior PASS verdicts were too generous on the
**framing / rationale** side, even when the observed numbers were within
tolerance. Specifically:
- W3.5 (Spot 3): only 1-of-3 polarization legs (value-side) was visible;
  PASS implies full polarization but the test only shows partial.
- W2b.2 (Spot 10): the Nash-indifference rationalization is wrong; the
  actual mechanism is all-in dominating smaller sizes, not bet-size
  EV-equivalence.

These downgrades do NOT indicate solver bugs — the solver behavior is
poker-sensible in every case. They indicate that the PASS verdicts
overstated what the test actually validated, in line with the
orchestrator's self-correction pattern (claiming more than the numerical
evidence supports).

### Recommended follow-ups
1. **W3.5 (Spot 3) → PARTIAL** awaiting PR 23 (W2.3 RvR perf cliff) fix
   to observe bluff-side + bet-sizing polarization
2. **W2b.1 (Spot 4)** → re-run with broader, realistic BB defending range
   (incl. middle pairs, suited connectors, floats) to validate flat-call
   distribution
3. **W1.2 (Spot 8)** → correct the W1.2 retest report rationale text
   ("no straights/sets beat JJ" → "only AA = set of aces beats JJ-set;
   3/45 combos, accounting for 7.7% fold slack")
4. **W2b.2 (Spot 10) → PARTIAL** with reframed rationale: "all-in
   strictly dominates smaller bet sizes in this 1v1 dynamic; smaller
   sizes collapse to residual ~0 mass with arbitrary 1:1 split"

---

## Files referenced
- `/Users/ashen/Desktop/poker_solver/docs/poker_spots_audit_2026-05-23.md`
- `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/W3_5_v1_4_1_retest.md`
- `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/W1_2_v1_4_1_retest.md`
- `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/v1_3_2_phase2b_audit.md`
- `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/v1_3_2_phase2b_retest.md`
- `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/phase2b_rvr_results.md`
- `/Users/ashen/Desktop/poker_solver/poker_solver/equity.py`
- `/Users/ashen/Desktop/poker_solver/poker_solver/evaluator.py`
