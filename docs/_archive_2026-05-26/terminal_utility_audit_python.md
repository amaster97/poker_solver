# Terminal Utility Audit — Python Tier

**Date:** 2026-05-24
**Auditor:** Code-trace agent
**Scope:** Every Python file that computes terminal-node utility (`poker_solver/`)
**Question:** Does the Python tier compute the winner's payoff using the canonical
poker convention (winner takes full pot = all contributions including dead money)?

---

## Single source of truth

The CFR loop (`dcfr.py:171-172`) and the EV/BR evaluators (`solver.py:279-280`,
`solver.py:404-405`) **delegate terminal evaluation entirely to `game.utility(state)`**:

```python
# dcfr.py:171-172
if self.game.is_terminal(state):
    return np.asarray(self.game.utility(state), dtype=np.float64)
```

```python
# solver.py:279-280
if game.is_terminal(state):
    return np.asarray(game.utility(state), dtype=np.float64)
```

```python
# solver.py:404-405
if game.is_terminal(state):
    return float(game.utility(state)[br_player])
```

There is **no separate "winner-takes-pot" computation** anywhere else in the
solver stack. The audit therefore reduces to: does each `Game.utility(...)`
implementation return the correct chip-delta?

The conventions used by each `utility(...)` implementation:

- All implementations return a **zero-sum tuple `(p0_payoff, p1_payoff)`** in
  **chip-delta** convention (chips gained/lost relative to start of subgame),
  NOT the "winner gets full pot raw" convention.
- This is **mathematically equivalent** to winner-takes-full-pot. If each
  player put in `c` chips and winner takes the `2c` pot, winner's chip change
  is `+c = +opponent_contribution`; loser's is `-c = -own_contribution`. The
  pot's chips that came from the winner themselves are not "winnings" — they
  are recovered own contribution.

---

## HUNL (the production solver) — `poker_solver/hunl.py`

### Showdown terminal (all streets — flop/turn/river closes at street boundary, deals out, lands at `Street.SHOWDOWN`)

**File:line:** `poker_solver/hunl.py:465-479`

**Verbatim:**
```python
def utility(self, state: HUNLState) -> tuple[float, float]:
    cfg = state.config
    bb = cfg.big_blind
    c0, c1 = state.contributions
    if state.folded[0]:
        return (-c0 / bb, c0 / bb)
    if state.folded[1]:
        return (c1 / bb, -c1 / bb)
    rank0 = evaluate(list(state.hole_cards[0]) + list(state.board))
    rank1 = evaluate(list(state.hole_cards[1]) + list(state.board))
    if rank0 > rank1:
        return (c1 / bb, -c1 / bb)
    if rank1 > rank0:
        return (-c0 / bb, c0 / bb)
    return (0.0, 0.0)
```

**Decoded formula (P0 wins at showdown):**
- P0 payoff = `c1 / bb`
- P1 payoff = `-c1 / bb` (loses own contribution)
- where `c0, c1 = state.contributions` are the **cumulative chips contributed
  by each player since the start of the subgame** (initialized at line 413,
  `contributions = cfg.initial_contributions`, then incremented by `pay` on
  every call/bet/raise/all-in via `contributions[player] += pay`).

**Is this winner-takes-full-pot?** Yes, in chip-delta form. If `c0 == c1` (the
universal case at a called showdown), total pot = `c0 + c1 = 2c1`, winner
takes the whole pot, **winner's NET chip change** = `pot - own_contribution`
= `2c1 - c0 = c1` ✓.

**Subtle but important — dead money (`cfg.initial_pot`):** the subgame
constructor honors two modes (verified at `hunl.py:168-176`):
1. **Allocated mode** (`initial_contributions != (0,0)`): `initial_contributions`
   sum **must equal** `initial_pot`. So `state.contributions` already includes
   the prior-street money allocated to each side. ✓
2. **Unallocated dead-money mode** (`initial_contributions == (0,0)`,
   `initial_pot > 0`): documented as "dead-money pot whose chips don't count
   toward either player's fold-loss accounting." In this mode the dead money
   is intentionally not included in either side's chip-delta.

**Production paths use mode 1 only** (`cli.py:124-134`:
`initial_contributions=(big_blind, big_blind)`, `initial_pot=2*big_blind`;
all `tests/test_hunl_core.py` postflop fixtures: `initial_pot=200,
initial_contributions=(100, 100)`). Mode 2 is reserved for "dead money"
analysis where chips don't belong to either player by construction.

**Verdict:** WINNER-GETS-FULL-POT ✓ (in chip-delta convention,
equivalent to winner-takes-pot for production configurations)

---

### Fold terminal (any street — `state.folded[*] = True`)

**File:line:** `poker_solver/hunl.py:469-472`

**Verbatim:**
```python
if state.folded[0]:
    return (-c0 / bb, c0 / bb)
if state.folded[1]:
    return (c1 / bb, -c1 / bb)
```

**Decoded formula (P1 folds, P0 wins):**
- P0 payoff = `c1 / bb` (gains the chips P1 left in the pot)
- P1 payoff = `-c1 / bb` (loses own contribution)

**Same analysis as showdown:** uses cumulative `state.contributions` since
subgame start, which includes prior-street money in production mode-1
configurations.

Note an asymmetry worth flagging: when P0 folds, P0 loses `c0` (P0's own
contribution), and P1 gains `c0` (chips won from P0). This is correct **only
when `c0 == c1`** (the normal case where a player folds to a bet they cannot
match without committing their own chips). For an **asymmetric** facing-bet
fold — e.g., P0 has 100 in, P1 raises to 300, P0 folds — the code returns
`P1 gain = c0 = 100`, which is what P1 **won from P0**. P1's pre-fold
contribution `c1 = 300` is unchanged (still owned by P1). ✓ This is the
correct chip-delta.

**Verdict:** WINNER-GETS-FULL-POT ✓

---

### All-in terminal (all streets — runout-to-showdown, no further decisions)

The HUNL tree models all-in as: action `ACTION_ALL_IN` → both players all-in
(or one called, refund excess uncalled chips per `hunl.py:651-666`) → chance
deals remaining board cards → `street == Street.SHOWDOWN` → call `utility(...)`.

**File:line:** Same code path as the showdown case at `hunl.py:473-479`. No
separate "all-in payoff" function exists — runout is just deterministic chance
followed by showdown comparison.

**Decoded formula:** Identical to showdown. `c0, c1` reflect the all-in
contributions; winner's chip-delta = `opponent_contribution`. ✓

**Verdict:** WINNER-GETS-FULL-POT ✓

---

## Preflop equity-leaf — `poker_solver/preflop.py`

### Preflop-only terminal: "about-to-deal-flop" frontier (PR 9 leaf-value oracle)

**File:line:** `poker_solver/preflop.py:129-188`

**Verbatim (key lines):**
```python
def utility(self, state: HUNLState) -> tuple[float, float]:
    # Fold case + full-showdown case: delegate to base.
    if any(state.folded) or state.street == Street.SHOWDOWN:
        return super().utility(state)
    # Equity-leaf case: matched contributions, runout pending. ...
    bb = state.config.big_blind
    c0, c1 = state.contributions
    risk = min(c0, c1)
    pot = 2 * risk  # contested chips
    ...
    ev_p0_chips = pot * eq_p0 - risk
    return (ev_p0_chips / bb, -ev_p0_chips / bb)
```

**Decoded formula (preflop equity leaf):**
- P0 wins `pot * eq_p0` chips on average, P0 paid `risk`, so P0's EV =
  `pot * eq_p0 - risk` chips
- For `eq_p0 = 1.0` (sure win): EV = `pot - risk = 2*risk - risk = +risk = +c1`
  (P0 gains P1's contribution). ✓ Equivalent to winner-takes-pot.
- For `eq_p0 = 0.0` (sure loss): EV = `0 - risk = -risk = -c0` (P0 loses own
  contribution). ✓
- For `eq_p0 = 0.5` (tie): EV = `pot * 0.5 - risk = risk - risk = 0`. ✓

**Fold/full-showdown branches:** delegate to `super().utility(state)` =
`HUNLPoker.utility` (analyzed above). ✓

**Subtle:** uses `risk = min(c0, c1)` and `pot = 2 * risk`, NOT
`pot = c0 + c1`. This is **correct** for the all-in regime where one player
shoves more than the other can call: the uncalled excess is refunded
**before** this leaf is reached (`hunl.py:651-666`). By the time we hit the
equity leaf, `c0 == c1` (matched contested chips) and `min(c0, c1) ==
c0 == c1`. The comment at preflop.py:142-148 explicitly documents this
invariant. ✓

**Note on dead money:** This formula does NOT add prior-street dead money to
the winner's payoff. For preflop-start subgames (`starting_street ==
PREFLOP`), `initial_contributions == (0, 0)` is **forbidden by config
validation** to coexist with `initial_pot > 0` (see `hunl.py:143-149`:
preflop-start REQUIRES `initial_pot == 0` and `initial_contributions == (0,
0)`). So at preflop, both initial pot and initial contributions are 0,
the SB/BB blinds are posted within the betting (via the `_initial` setup at
`hunl.py:382-412`), and dead money is irrelevant. ✓

**Verdict:** WINNER-GETS-FULL-POT ✓

---

## Small-game references (Kuhn, Leduc) — `poker_solver/games.py`

### KuhnPoker — `games.py:89-105`

**Verbatim:**
```python
def utility(self, state: KuhnState) -> tuple[float, float]:
    hist = _history_string(state.history)
    c0, c1 = state.cards
    showdown_winner = 0 if c0 > c1 else 1
    if hist == "pp":
        payoff = 1.0 if showdown_winner == 0 else -1.0
    elif hist == "bp":
        payoff = 1.0  # P1 folded; P0 wins ante (+1)
    elif hist == "bb":
        payoff = 2.0 if showdown_winner == 0 else -2.0  # showdown pot 4, winner +2
    elif hist == "pbp":
        payoff = -1.0  # P0 folded; P1 wins, P0 net -1
    elif hist == "pbb":
        payoff = 2.0 if showdown_winner == 0 else -2.0
    ...
    return (payoff, -payoff)
```

**Decoded:** Each terminal payoff is the winner's chip-delta after they take
the full pot:
- `pp` (both pass, pot=2): each anted 1, winner takes 2, winner-delta = +1 ✓
- `bb` (both bet, pot=4): each contributed 2, winner takes 4, winner-delta = +2 ✓
- `bp` (P1 folds): P1 anted 1, P0 wins P1's ante = +1 ✓

**Verdict:** WINNER-GETS-FULL-POT ✓

### LeducPoker — `games.py:214-231`

**Verbatim:**
```python
def utility(self, state: LeducState) -> tuple[float, float]:
    ante0, ante1 = state.ante
    if state.folded[0]:
        return (-float(ante0), float(ante0))
    if state.folded[1]:
        return (float(ante1), -float(ante1))
    ...
    if c0 == pub and c1 != pub:
        return (float(ante1), -float(ante1))
    ...
```

**Decoded:** `ante[i]` is cumulative chips contributed by player `i` in the
round (incremented by call/raise in `_apply_player`). Winner gains
opponent's `ante`, equivalent to winner-takes-pot. ✓

**Verdict:** WINNER-GETS-FULL-POT ✓

---

## Summary table

| Street   | Showdown                                        | Fold                                            | All-in                                          | Verdict   |
|----------|-------------------------------------------------|-------------------------------------------------|-------------------------------------------------|-----------|
| Preflop  | `hunl.py:473-479` + `preflop.py:129-188` (equity-leaf) ✓ | `hunl.py:469-472` ✓                            | runout → showdown (same code path) ✓            | CORRECT   |
| Flop     | `hunl.py:473-479` ✓                            | `hunl.py:469-472` ✓                            | runout → showdown (same code path) ✓            | CORRECT   |
| Turn     | `hunl.py:473-479` ✓                            | `hunl.py:469-472` ✓                            | runout → showdown (same code path) ✓            | CORRECT   |
| River    | `hunl.py:473-479` ✓                            | `hunl.py:469-472` ✓                            | call → showdown (same code path) ✓              | CORRECT   |

| Game           | Showdown                       | Fold                          | Verdict   |
|----------------|--------------------------------|-------------------------------|-----------|
| Kuhn           | `games.py:93,97-98,101-102` ✓ | `games.py:95-96,99-100` ✓     | CORRECT   |
| Leduc          | `games.py:220-231` ✓          | `games.py:216-219` ✓          | CORRECT   |

---

## Final verdict

**CORRECT** — The Python tier uses **winner-takes-full-pot** consistently
across all streets and all terminal types, expressed in chip-delta form
`(p0_chips_won, p1_chips_won)`. The chip-delta convention is mathematically
identical to "winner takes the full pot" because:

`winner_chip_delta = pot − own_contribution = opponent_contribution` (for
matched contributions; refunds handle the all-in unmatched case).

The earlier diagnosis of "non-zero-sum convention divergence" between our
solver and Brown's appears to have **misinterpreted this chip-delta
representation as a partial-pot bug**. The Python code is correct.

**One nuance to flag for cross-tier comparison:** Brown's C++ may return the
raw winner-takes-full-pot value (`pot` for the winner, `0` for the loser,
non-zero-sum positive values), while ours returns the equivalent chip-delta
(`+c1, -c1`, zero-sum). Any cross-tier diff should **normalize the
representation** (subtract each player's own contribution from Brown's raw
output) before comparing — otherwise the conventions diverge by exactly each
player's own contribution and the diff agent will misreport "P0 differs by
c0" as a bug when in fact the underlying poker math agrees.

---

## Confidence

**High.** Single utility function per game; all CFR/EV/BR paths delegate to
it; no parallel "winner payoff" computation lurking elsewhere; chip-delta
math is unit-test-checkable against the textbook poker accounting (verified
by hand for AA-vs-anything, push/fold, and 100 BB called-shove cases).

The dead-money `(0, 0)` mode is documented as intentional and is **not** the
mode used by any production code path (CLI builds with
`initial_contributions=(big_blind, big_blind)`; tests with
`initial_contributions=(100, 100)`). If a future caller passes
`initial_contributions=(0,0)` with `initial_pot > 0` expecting the dead
money to land with the winner, that would be a contract-misuse bug, NOT a
core-solver bug.

## Recommended next action

1. **Look elsewhere for the source of the cross-tier divergence.** The Python
   utility is correct. The earlier "convention divergence" diagnosis is
   likely a **misinterpretation of the chip-delta representation**.
2. Audit the parity wrapper (`poker_solver/parity/noambrown_wrapper.py`) and
   the Rust tier (`crates/`) for whether they normalize Brown's raw-pot
   convention to match our chip-delta convention before diffing.
3. Specifically check the diff-computation site: if it directly compares
   `our_utility[0]` against `brown_utility[0]` without subtracting Brown's
   `own_contribution`, that's the bug.
