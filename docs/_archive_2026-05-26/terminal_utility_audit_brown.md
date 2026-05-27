# Terminal Utility Audit: Noam Brown Reference Solver

**Date:** 2026-05-24
**Scope:** P0 ship-blocking — verify what Brown's terminal-utility functions actually compute, and whether the prior agent's "non-zero-sum convention" diagnosis is correct.

---

## Showdown function

**File:** `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/vector_eval.cpp`
**Lines:** 90–131

### Verbatim code

```cpp
void VectorEvaluator::showdown_values(int player,
                                      const double *opp_weights,
                                      double pot_total,
                                      double contrib_player,
                                      double *out_values,
                                      EvalScratch &scratch) const {
    const EvalCache &cache = cache_[player];
    int opp_count = num_hands_[1 - player];
    scratch.prefix.resize(static_cast<std::size_t>(opp_count) + 1);
    scratch.prefix[0] = 0.0;
    for (int i = 0; i < opp_count; ++i) {
        scratch.prefix[i + 1] = scratch.prefix[i] + opp_weights[cache.sorted_indices[i]];
    }
    // Prefix sums give total weight below each strength bucket.
    double total = scratch.prefix[opp_count];
    int player_count = num_hands_[player];
    if (total <= 0.0) {
        std::fill(out_values, out_values + player_count, 0.0);
        return;
    }

    for (int h = 0; h < player_count; ++h) {
        int start = cache.range_start[h];
        int end = cache.range_end[h];
        double win_weight = scratch.prefix[start];
        double tie_weight = scratch.prefix[end] - scratch.prefix[start];
        double lose_weight = total - win_weight - tie_weight;

        for (int idx : cache.blocked_less[h]) {
            win_weight -= opp_weights[idx];
        }
        for (int idx : cache.blocked_equal[h]) {
            tie_weight -= opp_weights[idx];
        }
        for (int idx : cache.blocked_greater[h]) {
            lose_weight -= opp_weights[idx];
        }

        double active_weight = win_weight + tie_weight + lose_weight;
        out_values[h] = win_weight * pot_total + tie_weight * (pot_total * 0.5) - contrib_player * active_weight;
    }
}
```

### Decoded formula

The output per hand `h`, weighted-summed over the opponent's reach distribution:

```
out[h] = win_weight * pot_total
       + tie_weight * (pot_total * 0.5)
       - contrib_player * active_weight
```

Where `active_weight = win_weight + tie_weight + lose_weight` (i.e., the total opponent reach on non-blocked hands).

This is a **vector-form expected utility** — each component multiplies a probability-weighted count by an amount. It is **NOT** the per-outcome reward in isolation; it's already a sum over the opponent's hand distribution.

The unit semantics for the underlying single-outcome reward (factoring out the `opp_weights`) are:

- **Win outcome (player has stronger hand):** `+pot_total - contrib_player`
- **Tie outcome:** `+0.5 * pot_total - contrib_player`
- **Lose outcome:** `0 - contrib_player` (the `lose_weight` term contributes only to `active_weight`, not to a positive winnings term)

---

## Fold function

**File:** `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/vector_eval.cpp`
**Lines:** 133–162

### Verbatim code

```cpp
void VectorEvaluator::fold_values(int player,
                                  const double *opp_weights,
                                  double value,
                                  double *out_values) const {
    const EvalCache &cache = cache_[player];
    int opp_count = num_hands_[1 - player];
    double total = 0.0;
    for (int i = 0; i < opp_count; ++i) {
        total += opp_weights[i];
    }
    int player_count = num_hands_[player];
    if (total <= 0.0) {
        std::fill(out_values, out_values + player_count, 0.0);
        return;
    }

    for (int h = 0; h < player_count; ++h) {
        double blocked_weight = 0.0;
        for (int idx : cache.blocked_less[h]) {
            blocked_weight += opp_weights[idx];
        }
        for (int idx : cache.blocked_equal[h]) {
            blocked_weight += opp_weights[idx];
        }
        for (int idx : cache.blocked_greater[h]) {
            blocked_weight += opp_weights[idx];
        }
        out_values[h] = value * (total - blocked_weight);
    }
}
```

### Decoded formula

```
out[h] = value * (total - blocked_weight_h)
```

i.e., per non-blocked opponent hand, the per-hand payoff is just the scalar `value` passed in by the caller. The function itself is "dumb" — it doesn't know whether `value` represents a win or a loss. It just multiplies a caller-supplied scalar by the valid opponent reach.

The semantics of `value` are determined entirely at the call site in `trainer.cpp`.

---

## Caller: trainer.cpp (terminal handling in `traverse`)

**File:** `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/trainer.cpp`
**Lines:** 147–160

### Verbatim code

```cpp
if (node.player == -1) {
    double pot = static_cast<double>(game_.base_pot + node.contrib0 + node.contrib1);
    double contrib = (update_player == 0) ? node.contrib0 : node.contrib1;
    if (node.terminal_winner >= 0) {
        if (node.terminal_winner == update_player) {
            evaluator_.fold_values(update_player, reach_opp, pot - contrib, frame.values.data());
        } else {
            evaluator_.fold_values(update_player, reach_opp, -contrib, frame.values.data());
        }
    } else {
        evaluator_.showdown_values(update_player, reach_opp, pot, contrib, frame.values.data(), eval_scratch_);
    }
    return frame.values.data();
}
```

Identical structure repeated at lines 250–262 in `best_response`.

### Decoded

- **`pot` = `base_pot + contrib0 + contrib1`** — the FULL pot at the terminal node, including the initial seed `base_pot` plus both players' in-tree contributions.
- **`contrib`** = the update player's own in-tree contribution (does NOT include `base_pot`).
- **Fold-win:** `value = pot - contrib` (full pot minus own contribution = net gain from opponent's chips)
- **Fold-lose:** `value = -contrib` (lose the chips you put in this subgame)
- **Showdown win:** `pot_total - contrib_player` = `(base_pot + contrib0 + contrib1) - contrib_self` = `base_pot + opp_contrib` (i.e., what you net = base pot was sitting there, plus opponent's contribution; your own contribution is washed out)
- **Showdown lose:** `-contrib_player` (you net minus your own contribution)
- **Showdown tie:** `0.5 * pot_total - contrib_player` (split pot)

---

## `base_pot` definition

**File:** `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/river_game.h:52`

```cpp
int base_pot = 0;
```

**Set at:** `river_game.cpp:191`:

```cpp
base_pot = config.pot;
```

**Config default:** `river_game.h:38`: `int pot = 1000;`

So `base_pot` = **the pot at the start of the subgame (= river street start)**. It represents chips already in the middle from prior streets — money that nobody can lose during this river subgame because nobody can take it back. Both players' in-tree contributions (`contrib0`, `contrib1`) start at 0 and accumulate as the river plays out.

`legal_actions` confirms this at line 27: `int pot_total(const State &state, int base_pot) { return base_pot + state.contrib0 + state.contrib1; }`.

---

## Decoded answer to the prior agent's claim

**Prior agent's claim:** "Brown's `showdown_values` and `fold_values` include the `base_pot` in the WIN payoff (`winner_payoff = base_pot + opp_contrib`)."

**Was the agent right? Y — but the framing is misleading.**

### What's actually happening

For a winning showdown, the per-outcome payoff Brown's code produces is:

```
pot_total - contrib_player
= (base_pot + contrib0 + contrib1) - contrib_self
= base_pot + contrib_opp
```

So yes, the literal arithmetic of "win payoff = base_pot + opp_contrib" appears in the code. **But this is the CORRECT zero-sum formula expressed as NET CHANGE in stack.** It is NOT a non-zero-sum convention.

### The semantics decoded

Brown's terminal utility is the player's **net stack change** at the end of the subgame, measured against their stack at the start of the subgame:

- **Win:** "I net the chips that were in the pot at subgame start (`base_pot`) plus the chips my opponent put into the pot during the subgame (`contrib_opp`). My own contribution `contrib_self` returns to me as part of the pot I scoop, so it doesn't show up in the net change."
- **Lose:** "I net minus my own in-tree contribution `contrib_self`." (I lose what I put in during the subgame; my prior chips that contributed to `base_pot` were already lost before the subgame started, so they're a sunk cost not in scope.)
- **Tie:** "I net `0.5 * pot_total - contrib_self`."

### Verification: this IS zero-sum

For winner W and loser L on a non-fold terminal:

```
net_W + net_L
= (base_pot + contrib_L) + (-contrib_L)
= base_pot
```

Brown himself confirms this is the expected zero-sum constant in `trainer.cpp:340`:

```cpp
return (br0 + br1 - static_cast<double>(game_.base_pot)) / 2.0;
```

Exploitability subtracts `base_pot` precisely because the per-player best-response values each carry a `+base_pot` "bonus" that comes from the chips already in the middle. In a true constant-sum subgame where the starting pot is `base_pot`, the sum of equilibrium utilities equals `base_pot` (both players each have an equal claim to the base in expectation under their reach distribution). Subtracting `base_pot` and dividing by 2 gives the per-player exploitability over and above the equilibrium baseline.

### What the agent likely misread

The agent saw the literal expression `pot - contrib = base_pot + opp_contrib` for the winner and concluded "Brown is paying out only the opponent's contribution plus the base pot — that's not the whole pot." That reading would imply the winner does NOT get back their own `contrib_self`, which would be non-zero-sum.

**The correct reading:** Brown's `out_values[h]` is **net change in chip stack**, not gross winnings. The winner's own contribution `contrib_self` is invisible because it's a wash — it goes from the player's stack into the pot, and then back into the player's stack when they scoop. Net change = 0 contribution from that chunk. The only NET change is the chips that crossed from the opponent (and from the seed pot) to the winner.

So "winner_payoff = base_pot + opp_contrib" is **the correct zero-sum formula expressed as net stack change**. It is mathematically equivalent to "winner gets the whole pot" — the two formulations differ only in reference frame.

---

## Final answer to "does Brown award full pot to winner"

**Y, expressed equivalently as net change.**

Brown's solver awards the winner the entire pot in the standard poker sense. The code expresses this as `pot - contrib_self` (net stack change) rather than `pot` (gross collection) because the natural quantity for CFR regret accounting is utility-relative-to-baseline, not absolute chip stack. The two formulations are mathematically identical because the winner's own contribution cancels: gross payout `pot` minus their own buy-in `contrib_self` equals net gain `pot - contrib_self = base_pot + contrib_opp`.

**Convention is fully zero-sum.** The exploitability formula at `trainer.cpp:340` explicitly subtracts `base_pot` to recover the standard zero-sum normalization, which is consistent with the convention `net_winner + net_loser = base_pot` (the constant value of the subgame).

The prior agent's "non-zero-sum convention" diagnosis is **WRONG**. Brown's solver uses correct zero-sum semantics throughout; the agent confused "net stack change formula" with "non-zero-sum payoff."
