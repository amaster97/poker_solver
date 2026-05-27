# Terminal Utility Audit — Rust Vector Form (`dcfr_vector.rs`)

**Date:** 2026-05-24
**Scope:** v1.5.0+ Rust vector-form CFR path; specifically the terminal-leaf payoff computation.
**Trigger:** Prior agent diagnosed a "non-zero-sum convention divergence" claiming our Rust `terminal_utility` omits `base_pot` while Brown's `vector_eval.cpp` includes it. We are now suspicious that diagnosis was based on a misread.

---

## Call graph

`VectorDCFR::traverse` (`dcfr_vector.rs:302-469`) handles three node types.
The terminal branch (line 315-323) delegates to `terminal_value_vector`
(line 619-656), which loops `(hp, ho)` hand pairs and calls
`terminal_utility` (`exploit.rs:515-572`) per disjoint pair — the per-pair
payoff in BB units. The vector form is just an outer "sum over opponent
hands weighted by `reach_opp`" wrapper around the same scalar payoff
function that the scalar `dcfr.rs` and `flat_expected_value` use.

### Section: Vector terminal dispatch

- **File:line:** `crates/cfr_core/src/dcfr_vector.rs:315-323`
- **Verbatim:**
  ```rust
  FlatNode::Fold { .. } | FlatNode::Showdown { .. } => {
      // Terminal — compute the per-hand utility weighted by
      // opponent's reach. Per Brown's `Trainer::traverse`
      // (`trainer.cpp:147-159`, MIT): the returned value for
      // `update_player` is the cf-utility, i.e. sum over
      // opponent hands of `opp_reach * value_per_pair`.
      let opp_player = 1 - update_player;
      terminal_value_vector(node, eval_ctx, update_player, opp_player, reach_opp)
  }
  ```
- **Decoded:** Dispatches both fold AND showdown terminals into the same
  per-pair-weighted helper. No special "all-in" terminal type — all-ins
  resolve via `FlatNode::Chance` board-card runouts, terminating at
  `Showdown` (full 5-card board) or earlier `Fold`.
- **Note on terminal types:** Only two terminal variants exist in this
  module's `FlatNode` enum (`exploit.rs:306-317`): `Fold` and `Showdown`.
  All-in lines route through chance run-outs to one of these two.

### Section: Per-pair vector accumulator

- **File:line:** `crates/cfr_core/src/dcfr_vector.rs:630-655`
- **Verbatim:**
  ```rust
  for hp in 0..update_hands {
      let hole_p = ctx.hole[update_player][hp];
      let mut total = 0.0_f64;
      for ho in 0..opp_hands {
          let hole_o = ctx.hole[opp_player][ho];
          // Blocker check — both players must hold disjoint cards.
          if hole_p[0] == hole_o[0]
              || hole_p[0] == hole_o[1]
              || hole_p[1] == hole_o[0]
              || hole_p[1] == hole_o[1]
          {
              continue;
          }
          let combo = if update_player == 0 {
              [hole_p, hole_o]
          } else {
              [hole_o, hole_p]
          };
          let utility = terminal_utility(node, combo, update_player);
          total += reach_opp[ho] * utility;
      }
      out[hp] = total;
  }
  ```
- **Decoded:** `value[hp] = Σ_ho reach_opp[ho] * utility(hp,ho)`. Pure
  reach-weighted sum, no extra pot terms added or subtracted here. The
  bedrock payoff is entirely sourced from `terminal_utility`.

### Section: Fold terminal payoff

- **File:line:** `crates/cfr_core/src/exploit.rs:517-536`
- **Verbatim:**
  ```rust
  FlatNode::Fold {
      contributions,
      big_blind,
      folded_player,
  } => {
      let c0 = contributions[0] as f64;
      let c1 = contributions[1] as f64;
      let bb = *big_blind as f64;
      if *folded_player == 0 {
          if player == 0 { -c0 / bb } else { c0 / bb }
      } else if player == 0 {
          c1 / bb
      } else {
          -c1 / bb
      }
  }
  ```
- **Decoded:** Loser's payoff = `-(own contribution)/bb`. Winner's
  payoff = `+(loser's contribution)/bb`. NET PROFIT semantics, not
  gross. Uncalled bets stay implicit because the winner is only credited
  with what the loser put in. Zero-sum in chips when contributions are
  symmetric.
- **Verdict:** WINNER-GETS-NET-PROFIT (not "full pot"); intentional and
  internally consistent. **Not a bug.**

### Section: Showdown terminal payoff

- **File:line:** `crates/cfr_core/src/exploit.rs:537-570`
- **Verbatim:**
  ```rust
  FlatNode::Showdown { contributions, big_blind, board } => {
      let bb = *big_blind as f64;
      let c0 = contributions[0] as f64;
      let c1 = contributions[1] as f64;
      ... // build 7-card hands, evaluate strengths
      if s0 > s1 {
          if player == 0 { c1 / bb } else { -c1 / bb }
      } else if s1 > s0 {
          if player == 0 { -c0 / bb } else { c0 / bb }
      } else {
          0.0
      }
  }
  ```
- **Decoded:** Same NET PROFIT semantics. Winner: `+opp_contribution`.
  Loser: `-own_contribution`. Tie: `0.0` per side (each player walks away
  with their own contribution back).
- **Verdict:** WINNER-GETS-NET-PROFIT; consistent with fold logic. **Not a bug.**

---

## Comparison to Brown's `vector_eval.cpp:129`

Brown's per-hand showdown payoff (`vector_eval.cpp:129`):
```cpp
out_values[h] = win_weight * pot_total + tie_weight * (pot_total * 0.5)
              - contrib_player * active_weight;
```
where `pot_total = base_pot + node.contrib0 + node.contrib1`
(`trainer.cpp:148`).

Algebraically Brown's per-pair payoff for a WIN is
`pot_total - contrib_player = base_pot + opp_contrib`.
Ours is `opp_contrib`. **The difference is `base_pot`, an additive
constant per terminal.**

**Why this is NOT a bug for our regret updates:** CFR's regret update is
`regret[a] += (action_value[a] - node_value)` (dcfr_vector.rs:444-450).
An additive constant on EVERY terminal cancels out in this difference.
So the strategy converges to the same Nash equilibrium under both
conventions.

**Why this MIGHT matter (the one place to watch):** in Brown's setup,
`base_pot = config.pot` (river_game.cpp:191) and `contrib0/contrib1`
start at 0 — Brown's river-only game treats all prior-street money as
`base_pot`. In our setup `HUNLState.contributions` STARTS at
`initial_contributions` (which equals `initial_pot` for normal subgames
per Python validator hunl.py:172). So in normal subgames our "base_pot
analogue" is 0 — there's no constant to drop.

The ONE configuration where the conventions actually diverge in chip
terms: `initial_pot > 0` with `initial_contributions = (0, 0)` (the
"dead money pot" exception explicitly allowed by Python validator
hunl.py:168-176). Here our terminal_utility credits the winner with
ONLY `opp_contrib`, NOT the dead money. Python's `hunl.py:104` documents
this is INTENTIONAL: "(0,0) is accepted as a 'dead money' pot whose
chips don't count toward either player's fold-loss accounting (subgame
analysis)". So the Rust behavior matches the Python convention by
design.

---

## Final verdict

**CORRECT.** The prior agent's diagnosis was a **misread**.

- Our Rust `terminal_utility` uses **net-profit** payoff convention
  (winner = `+opp_contrib`, loser = `-own_contrib`, tie = 0).
- Brown's `vector_eval.cpp` uses **gross** payoff convention (winner =
  `pot - own_contrib`, loser = `-own_contrib`).
- The difference is an additive constant `base_pot` per terminal that
  is INVISIBLE to the regret-difference update.
- In all our test configs `initial_pot == sum(initial_contributions)`,
  so even the "base_pot analogue" is 0 — chip values match exactly.
- The "dead money pot" subgame case (`initial_contributions=(0,0),
  initial_pot>0`) is documented in Python as INTENTIONALLY not crediting
  the winner with the dead money; Rust matches that contract.

**Bug locations:** None.

**Recommended next action:** Cancel any in-flight "base_pot fix" PRs.
Re-audit the prior agent's report for the originating misread (likely
confused "net profit" with "missing pot"). If divergence between Brown
and our solver was actually observed in some empirical test, the root
cause is somewhere ELSE — re-run the comparison with controlled inputs
and instrument both solvers per terminal to pinpoint where the values
actually diverge. Specifically check:
1. Whether reach weights are normalized the same way at the root.
2. Whether the blocker-conflict handling differs (we skip; Brown
   subtracts from win/tie/lose buckets — algebraically equivalent for a
   single terminal, but check the in-flight cross-products line up).
3. Whether the `regret_weight` / `avg_weight` for DCFR differ
   (dcfr_vector.rs:438-439 hardcode 1.0; check Brown's
   `trainer.cpp:354-355`).
