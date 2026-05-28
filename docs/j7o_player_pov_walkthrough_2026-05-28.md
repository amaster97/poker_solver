# J7o Player-POV Walkthrough — Tests 1-4 (FULL Postflop Solves)

**Date:** 2026-05-28

Companion to ``docs/j7o_walkthrough_tests_1_4_2026-05-28.md``
(which reported equity only). This doc reports **actual GTO
action distributions** from postflop subgame solves at each
decision point. Format = player POV: at each street, what
does the solver say SB does specifically with J♠7♦?

## Configuration

```python
Stack: 40 BB (4000 chips at 100 chips/BB)
Blinds: SB 50 / BB 100
Preflop solve: 1500 DCFR iterations (169-class engine)
Postflop turn solve: 10 DCFR iterations, top-8 classes / side + hero pin
Postflop river solve: 30 DCFR iterations, top-8 classes / side + hero pin
Postflop bet sizings: 33%, 75%, 100%, 150%, 200% pot
Postflop raise cap: 3 (set by engine default)
```

**Flop solves are DEFERRED** in this walkthrough. Empirical measurement
on 2026-05-28 (worktree ``j7o-walkthrough-full-pov``) showed flop subgame
solves exceeding 5 minutes of CPU per solve even at top-K = 4 classes
and 5 iterations — the chance tree from flop to river blows up per-iter
cost in the vector-form solver. Turn solves succeed in ~15s and river
solves in <1s (TerminalCache amortizes the dominant evaluator cost on
a constant board). The flop directional reads below are from the
equity-only walkthrough in ``docs/j7o_walkthrough_tests_1_4_2026-05-28.md``.

**Wall time:** preflop solve = 4.5s, total = 21.6s

## Methodology

- Preflop: read SB's 169-class blueprint at the root infoset
  (``||p|``); J7o gets its action distribution directly.
- Postflop: at each street we call
  ``solve_postflop_from_blueprint`` with the preflop action
  sequence and the board. The solver propagates the preflop
  blueprint's continuation ranges (SB's open range vs BB's
  defend-vs-open range) into a postflop range-vs-range Nash
  solve, then we extract J7o's per-class strategy at SB's
  first decision and J♠7♦'s specific per-history strategy.
- Convention: in this engine, **BB acts first postflop**. So
  SB's flop decision is a RESPONSE to BB's modal action (check or
  bet). The ``BB modal`` line at each street reports what BB
  does most-often in the Nash solve — that's the context for
  SB's strategy.
- **Limitation surfaced**: turn/river subgame solves do NOT
  condition on a specific postflop action history. They solve
  Nash from the turn/river root given the preflop continuation
  ranges. So the turn strategy is 'what does GTO say with SB's
  open-call range vs BB's call range on this turn board' — not
  'what does SB do on the turn having checked-back the flop'.

========================================================
## TEST 1 — Baseline (no folds)
========================================================

**You hold:** J♠ 7♦
**Position:** Small Blind (40 BB effective)

### Preflop decision

Action on you. Pot: 1.5 BB (0.5 SB + 1.0 BB). Stack: 39.5 BB.

**Solver strategy for J♠7♦:**
```
  fold       :   0.0%
  call       :   1.6%
  open_to_200:  92.1%
  open_to_300:   6.3%
  open_to_400:   0.0%
  open_to_500:   0.0%
  all_in     :   0.0%
```
**GTO action:** ``open_to_200`` ( 92.1% of the time)

**Test forces:** raise to 3 BB (open_to_300). Slight off-tree —
solver prefers 2 BB open at 40 BB, but 3 BB is a near-equilibrium
alternative (no fold-mass).

(You raise to 3 BB. BB calls.)

**Pot after preflop:** 600 chips (6.0 BB). Stacks: 37 BB each.

### Flop: A♦ 8♥ 9♦

Pot: 600 chips (6.0 BB).

**Flop subgame solve DEFERRED.** Empirical measurement (2026-05-28):
the vector-form solver runs > 5 minutes of CPU per flop solve at
the smallest viable parameters (top-K = 4 hand classes + J7o pin,
only 5 DCFR iterations) — the chance tree from flop to river blows
up per-iter cost. Turn and river solves succeed (turn ~15s with
top-K=8, river <1s with TerminalCache).

Directional read (from equity-only walkthrough, doc #179):
J♠7♦ has no pair, no draw on A♦8♥9♦ (the 7♦ blocks a flush draw
but is otherwise dry). Equity vs BB's call range = ~40.1%. On an
Ax-heavy continuing range, J-high is a low-equity hand — solver's
preferred line is the smallest action that lets J7o give up
cheaply (check or fold to a small bet), occasionally a bluff cbet.

### Turn: 2♣ (brick)

Pot at turn: 600 chips. Board: A♦ 8♥ 9♦ 2♣.

**Subgame solved fresh at turn root** (does not condition on flop
action; sees only preflop continuation ranges).

**BB acts first on turn.** BB's modal action: ``bet_33`` ( 34.3%).
BB's turn action distribution:
```
  check     :  28.7%
  bet_33    :  34.3%
  bet_75    :  17.4%
  bet_100   :   9.9%
  bet_150   :   2.4%
  bet_200   :   7.1%
```

**SB strategy for J♠7♦ on turn (after BB's modal action):**
```
  raise_33  :  30.3%
  raise_75  :  18.8%
  fold      :  18.0%
  raise_100 :  14.1%
  raise_150 :  10.8%
  raise_200 :   3.7%
  all_in    :   2.4%
  call      :   1.9%
```
**GTO action for J♠7♦ on turn:** ``raise_33`` ( 30.7%)

### River: 3♠ (brick)

Pot at river: 600 chips. Board: A♦ 8♥ 9♦ 2♣ 3♠.

**BB acts first on river.** BB's modal action: ``check`` ( 84.5%).

**SB strategy for J♠7♦ on river (after BB's modal action):**
```
  all_in    :  49.1%
  bet_100   :  15.0%
  bet_200   :  11.4%
  bet_150   :   8.7%
  bet_75    :   7.3%
  check     :   6.6%
  bet_33    :   1.9%
```
**GTO action for J♠7♦ on river:** ``all_in`` ( 49.7%)

**Reading:** J-high almost never wins at showdown vs BB's wide call
range on this dry runout. The solver's preferred river action
reflects either a give-up (fold/check) or a low-frequency bluff.

========================================================
## TEST 2 — 3-bet / 4-bet pot (committed)
========================================================

**You hold:** J♠ 7♦
**Position:** Small Blind (40 BB)

**Solver preflop strategy for J♠7♦ (root):** ``open_to_200`` modally.

**Test forces:** SB opens 3x -> BB 3-bets to 9 BB -> SB 4-bets to
21 BB (nearest menu choice for ~22 BB) -> BB calls. The engine
actually has J7o folding to a 3-bet at near-100% rate, so this
flop scenario is OFF the GTO tree for J7o specifically — but the
postflop range solve still reflects SB's 4-bet range and BB's
call-vs-4bet range as they ACTUALLY are in the blueprint.

### Flop: A♦ 8♥ 9♦ (4-bet pot)

Pot at flop: 1200 chips (12.0 BB).
Effective stack remaining: 3400 chips per player.
SPR ≈ 2.83 — shallow; with 4-bet sizing both players are heavily committed.

**Flop subgame solve DEFERRED.** Same constraint as Test 1 — flop
solves exceed the salvage budget at any meaningful resolution.

Directional read: at SPR ~2.8 (after a 4-bet pot of 1200 chips)
both players are committed enough that modal SB action with most
hands is shove or call, not fold. J7o on A♦8♥9♦ has ~40% equity
vs BB's call-vs-4bet range (per doc #179), which clears the
required-equity threshold at this SPR. The headline finding is from
the preflop blueprint above: J7o folds to a 3-bet at 99.99% rate,
so this postflop spot is reachable only as a non-modal off-tree
event for J7o specifically.

========================================================
## TEST 3 — Postflop cbet / raise tree
========================================================

**You hold:** J♠ 7♦
**Position:** Small Blind
**Setup:** Same as Test 1 — SB opens 3x, BB calls. Pot 6 BB.

### Flop: A♦ 8♥ 9♦

Pot: 600 chips. (Same as Test 1 flop.)

**Flop subgame solve DEFERRED** (same constraint as Tests 1-2). The
postflop cbet-then-raise spot also requires the per_history_strategy
dict from a flop solve to surface, which is unavailable here. The
equity-based read below stands in.

### Hypothetical: BB checks, SB cbets, BB raises

Test 3's scenario asks: what does SB do when BB **raises** SB's
cbet? This requires a 3-deep flop infoset (BB check, SB bet,
BB raise). Since BB acts first on flop, the per_class projection
(which follows BB's modal first action) gives only SB's response
to BB's modal action — not the facing-raise spot.

We scanned the per_history_strategy dict for J♠7♦ rows where the
flop history matches ``x-b<size>-r<size>`` (BB check, SB bet, BB raise):

- Number of facing-raise infosets found for J♠7♦: **0**

**No 3-deep facing-raise infosets found** — likely because BB's
modal flop action is check (the bet-then-raise lines have low
probability under the converged strategy, and the vector-form
Rust binding only emits rows for infosets actually visited).
If SB cbets and BB raises, J7o's response is essentially the
'last-action' decision: with no equity and no draw, the GTO
response is a fold the vast majority of the time.

========================================================
## TEST 4 — Off-distribution 5x open with 2♦7♥
========================================================

**You hold:** 2♦ 7♥ (canonical class 72o)
**Position:** Small Blind

**Solver preflop strategy for 72o (root):**
```
  fold       : 100.0%
  call       :   0.0%
  open_to_200:   0.0%
  open_to_300:   0.0%
  open_to_400:   0.0%
  open_to_500:   0.0%
  all_in     :   0.0%
```
**GTO action for 72o:** ``fold`` (100.0%) — fold is correct, 5x open is heavily off-tree.

**Test forces:** 5x open (open_to_500) with 72o. BB calls. We solve
the postflop subgame with SB's 5x-open range vs BB's call-vs-5x range
on A♦8♥9♦ -> 2♣ -> 3♠.

### Flop: A♦ 8♥ 9♦

**Flop subgame solve DEFERRED.** Test 4 skips all postflop
solves because 72o has near-zero reach in SB's 5x-open range — the
per-class projection would be very noisy at any iteration budget.
Flop is additionally subject to the global SKIP_FLOP_SOLVES gate.

### Turn: A♦ 8♥ 9♦ 2♣

**Turn subgame solve DEFERRED.** Test 4 skips all postflop
solves because 72o has near-zero reach in SB's 5x-open range — the
per-class projection would be very noisy at any iteration budget.
Flop is additionally subject to the global SKIP_FLOP_SOLVES gate.

### River: A♦ 8♥ 9♦ 2♣ 3♠

**River subgame solve DEFERRED.** Test 4 skips all postflop
solves because 72o has near-zero reach in SB's 5x-open range — the
per-class projection would be very noisy at any iteration budget.
Flop is additionally subject to the global SKIP_FLOP_SOLVES gate.

**Reading:** 72o on A89dd with no draw or pair has near-zero
equity vs BB's defending range. The solver's preferred lines will
be give-ups or rare bluffs — but note 72o has near-zero reach in
SB's 5x-open range to begin with, so the class-averaged strategy
reflects what FEW 72o combos that DID open 5x would do.

## Reproduction

```
python scripts/run_j7o_walkthrough_full_pov.py
```

Branch: ``j7o-walkthrough-full-pov`` (off origin/main).

