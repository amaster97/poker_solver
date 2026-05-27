# Reach Weighting + Chance Node Audit (P0)

**Date:** 2026-05-24
**Investigator:** read-only audit, no code modified
**Scope:** Verify reach probability and chance-node weighting parity between our
`crates/cfr_core/src/dcfr_vector.rs` and Brown's
`references/code/noambrown_poker_solver/cpp/src/trainer.cpp:138-240`.
**Constraint:** Solver terminal convention is being treated as CORRECT per task
prompt; this audit excludes the terminal-utility-convention thread.

---

## 0. TL;DR

The reach **propagation algebra** is byte-identical between the two solvers
(opponent node: `next_reach[h] = reach_opp[h] * strategy[h,a]`; own node:
`next_reach[h] = reach_p[h] * strategy[h,a]`; terminal: only `reach_opp` is
passed to the leaf evaluator). Counterfactual reach is handled correctly on
both sides — regret update at the own node multiplies the leaf-side
opp-reach-weighted action values, with no additional reach multiplier at the
update step, matching Brown verbatim.

**Two divergences identified**, both verified by code quote:

| # | Divergence | Severity for K72/A83 deep-cap | Verdict |
|---|---|---|---|
| 1 | **Reach normalization at root** — Brown normalizes `hand_weights[p]` to sum to 1.0 across the range (`river_game.cpp:200-208`); we initialize each hand's reach to `1.0` flat (`dcfr_vector.rs:486-487`). | **LOW** — the scaling factor is uniform across all hands, so under regret-matching the strategy ratios are scale-invariant at steady state (the regret and `strategy_sum` both scale by the same constant, and `compute_strategy` + `compute_avg_strategy` both normalize). Will NOT explain a 22-42pp deep-cap divergence on its own. | **DIFFERENT but harmless for strategy comparison** |
| 2 | **Chance node weighting baked at tree-build time with the wrong blocker set** — `BettingTree::build_from` builds the tree once with a placeholder hole-card pair (`dcfr_vector.rs:783`). Inside, `state.chance_outcomes()` (`hunl.rs:533-568`) excludes the placeholder hole cards when computing `prob = 1.0 / remaining.len()`. The resulting `FlatNode::Chance.prob` is then **shared** across all (p0_hand, p1_hand) pairs at solve time, but the true remaining-deck size depends on the ACTUAL hands at the leaf. | **N/A for K72 / A83 deep-cap (river-only spots, no chance nodes in the tree)**. Will bite v1.5.x **turn / flop** range-vs-range solves with deep all-in run-outs. | **DIFFERENT, latent for postflop-pre-river** |

Neither divergence is the K72/A83 22-42pp source — the K72/A83 test spots are
river-only (5-card boards in `tests/data/river_spots.json:4-5`), so chance
nodes never enter the tree (`build_node` only emits `FlatNode::Chance` when
`state.current_player() == -1`, which doesn't happen on the river except for
the all-in run-out that's already complete with a 5-card board). The reach
normalization is scale-invariant. Look elsewhere for the K72/A83 driver.

---

## 1. Reach handling in our Rust vector form

### 1a. Reach storage and traversal signature

`dcfr_vector.rs:302-310` (the `traverse` signature):
```rust
fn traverse(
    &mut self,
    tree: &BettingTree,
    eval_ctx: &EvalContext,
    node_idx: usize,
    update_player: usize,
    reach_p: &[f64],
    reach_opp: &[f64],
) -> Vec<f64>
```

Reach is **per-hand** (`&[f64]` of length `hand_count[player]`), carried
through recursion as a slice. NOT stored per-infoset.

### 1b. Decision node — opponent

`dcfr_vector.rs:354-378`:
```rust
if player != update_player {
    let mut values = vec![0.0_f64; update_hands];
    let mut next_reach = vec![0.0_f64; opp_hands];
    for (a, &child_idx) in children.iter().enumerate() {
        // next_reach[h] = reach_opp[h] * strategy[h, a]
        for h in 0..opp_hands {
            next_reach[h] = reach_opp[h] * strategy[h * action_count + a];
        }
        let child_values = self.traverse(
            tree, eval_ctx, child_idx, update_player,
            reach_p, &next_reach,
        );
        for h in 0..update_hands {
            values[h] += child_values[h];
        }
    }
    return values;
}
```

Each child gets a **scaled `reach_opp`** (`reach_opp * strategy_for_that_action`).
`reach_p` is passed through unchanged. The returned per-hand values are then
summed over actions (no per-action weight at the parent because the action
probability has already been baked into `next_reach`).

### 1c. Decision node — own (update_player)

`dcfr_vector.rs:400-417`:
```rust
let mut action_values = vec![0.0_f64; action_count * update_hands];
let mut next_reach = vec![0.0_f64; player_hands];
for (a, &child_idx) in children.iter().enumerate() {
    // next_reach[h] = reach_p[h] * strategy[h, a]
    for h in 0..player_hands {
        next_reach[h] = reach_p[h] * strategy[h * action_count + a];
    }
    let child_values = self.traverse(
        tree, eval_ctx, child_idx, update_player,
        &next_reach, reach_opp,
    );
    let dst = a * update_hands;
    action_values[dst..dst + update_hands].copy_from_slice(&child_values);
}
```

Own reach is scaled per action; opp reach is passed unchanged. Per-action
child values are stored (not summed) so we can compute regret deltas.

### 1d. Regret update (own node)

`dcfr_vector.rs:444-451`:
```rust
for h in 0..update_hands {
    let offset = h * action_count;
    let base = node_values[h];
    for a in 0..action_count {
        let delta = (action_values[a * update_hands + h] - base) * regret_weight;
        info.regret[offset + a] += delta;
    }
}
```

**No `reach_opp` multiplier here.** The `action_value` and `node_value` are
already cf-utilities (opp-reach-weighted at the terminal leaf), so the regret
update consumes them as-is. This matches the counterfactual-regret definition.

`dcfr_vector.rs:454-463` for `strategy_sum`:
```rust
for h in 0..update_hands {
    let weight = reach_p[h] * avg_weight;
    if weight == 0.0 {
        continue;
    }
    let offset = h * action_count;
    for a in 0..action_count {
        info.strategy_sum[offset + a] += weight * strategy[offset + a];
    }
}
```

`strategy_sum` IS reach-weighted (own reach), per standard CFR.

### 1e. Terminal leaf

`dcfr_vector.rs:315-323`:
```rust
FlatNode::Fold { .. } | FlatNode::Showdown { .. } => {
    let opp_player = 1 - update_player;
    terminal_value_vector(node, eval_ctx, update_player, opp_player, reach_opp)
}
```

`dcfr_vector.rs:619-656`:
```rust
fn terminal_value_vector(
    node: &FlatNode,
    ctx: &EvalContext,
    update_player: usize,
    opp_player: usize,
    reach_opp: &[f64],
) -> Vec<f64> {
    ...
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
            ...
            let utility = terminal_utility(node, combo, update_player);
            total += reach_opp[ho] * utility;
        }
        out[hp] = total;
    }
    out
}
```

**Only `reach_opp` is used at the leaf** — exactly cf-utility shape:
`u_cf[hp] = Σ_{ho: disjoint} reach_opp[ho] * u(hp, ho)`.

### 1f. Chance node

`dcfr_vector.rs:324-337`:
```rust
FlatNode::Chance { prob, children } => {
    let mut values = vec![0.0_f64; update_hands];
    for &c in children {
        let child_values =
            self.traverse(tree, eval_ctx, c, update_player, reach_p, reach_opp);
        for (i, v) in child_values.iter().enumerate() {
            values[i] += *prob * v;
        }
    }
    values
}
```

**`prob` is a single scalar** baked into `FlatNode::Chance` at tree-build
time (see §3). Both reaches pass through unchanged — chance does NOT modify
either player's reach. This is the standard "chance is a constant
probability" treatment (a.k.a. "chance-sampled MC" with full enumeration).

### 1g. Initial reach values

`dcfr_vector.rs:486-487`:
```rust
let reach_p0: Vec<f64> = vec![1.0; eval_ctx.hand_count[0]];
let reach_p1: Vec<f64> = vec![1.0; eval_ctx.hand_count[1]];
```

**Each hand's reach starts at `1.0` flat.** Total reach sum for player p is
`hand_count[p]` (e.g., 1081 for a 47-card-remaining river).

---

## 2. Reach handling in Brown's reference

### 2a. Reach storage and traversal signature

`trainer.h:80-84`:
```cpp
const double *traverse(int node_id,
                       int update_player,
                       const double *reach_p,
                       const double *reach_opp,
                       int depth);
```

Identical shape — per-hand vector, carried through recursion as a pointer.

### 2b. Decision node — opponent

`trainer.cpp:166-181`:
```cpp
if (player != update_player) {
    compute_strategy(info_const, frame.strategy.data());
    std::fill(frame.values.begin(), frame.values.begin() + update_hands, 0.0);
    int opp_hands = info_const.hand_count;
    for (int a = 0; a < action_count; ++a) {
        for (int h = 0; h < opp_hands; ++h) {
            frame.next_reach[h] = reach_opp[h] * frame.strategy[h * action_count + a];
        }
        const double *child_values = traverse(node.next[a], update_player, reach_p, frame.next_reach.data(),
                                              depth + 1);
        for (int h = 0; h < update_hands; ++h) {
            frame.values[h] += child_values[h];
        }
    }
    return frame.values.data();
}
```

**Identical algebra to ours.** `reach_opp` is scaled by per-hand strategy and
passed as the new `reach_opp`; `reach_p` is unchanged.

### 2c. Decision node — own

`trainer.cpp:184-198`:
```cpp
InfoSet &info = infosets_[node_id];
if (algo_ == Algorithm::DCFR) {
    apply_dcfr_discount(info, dcfr_pos_scale_, dcfr_neg_scale_, dcfr_strat_scale_);
}
compute_strategy(info, frame.strategy.data());

double *action_values = frame.action_values.data();
for (int a = 0; a < action_count; ++a) {
    for (int h = 0; h < update_hands; ++h) {
        frame.next_reach[h] = reach_p[h] * frame.strategy[h * action_count + a];
    }
    const double *child_values = traverse(node.next[a], update_player, frame.next_reach.data(), reach_opp,
                                          depth + 1);
    std::copy(child_values, child_values + update_hands, action_values + a * update_hands);
}
```

**Identical** — own reach scaled per action, opp reach passed through, per-action
child values stored not summed.

### 2d. Regret update

`trainer.cpp:210-224`:
```cpp
CFRScalar *regret = info.regret.data();
for (int h = 0; h < update_hands; ++h) {
    int offset = h * action_count;
    double base = node_values[h];
    for (int a = 0; a < action_count; ++a) {
        // Update per-hand regrets for the updating player.
        double delta = (action_values[a * update_hands + h] - base) * regret_weight_;
        double updated = static_cast<double>(regret[offset + a]) + delta;
        if (algo_ == Algorithm::CFR_PLUS) {
            regret[offset + a] = static_cast<CFRScalar>(updated > 0.0 ? updated : 0.0);
        } else {
            regret[offset + a] = static_cast<CFRScalar>(updated);
        }
    }
}
```

**Identical** — no extra opp_reach multiplier here either; the cf-utility
shape is enforced at the leaf.

`trainer.cpp:226-237` for `strategy_sum`:
```cpp
CFRScalar *strategy_sum = info.strategy_sum.data();
for (int h = 0; h < update_hands; ++h) {
    double weight = reach_p[h] * avg_weight_;
    if (weight == 0.0) {
        continue;
    }
    int offset = h * action_count;
    for (int a = 0; a < action_count; ++a) {
        strategy_sum[offset + a] = static_cast<CFRScalar>(static_cast<double>(strategy_sum[offset + a]) +
                                                         weight * frame.strategy[offset + a]);
    }
}
```

**Identical** — `strategy_sum` reach-weighted by own reach.

### 2e. Terminal leaf

`trainer.cpp:147-159`:
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

**Only `reach_opp` is passed** to `fold_values` / `showdown_values`. `reach_p`
is not consumed at the leaf. Same shape as ours.

### 2f. Chance node

**Brown has NO chance nodes in its betting tree.**

`river_game.h:19-26` (the `TreeNode` struct):
```cpp
struct TreeNode {
    int player = -1;
    int terminal_winner = -1;
    int contrib0 = 0;
    int contrib1 = 0;
    int action_count = 0;
    std::vector<int> next;
};
```

`player ∈ {0, 1}` for decisions, `player == -1` for terminals. No
`chance_node` variant. `river_game.cpp:187-211` requires `board_cards.size()
== 5` and stores the board as fixed metadata; there is no Turn-to-River
chance edge.

The `traverse` function (`trainer.cpp:147` test `if (node.player == -1)`)
treats every `player == -1` node as terminal directly — no chance branch.

### 2g. Initial reach values

`trainer.cpp:367`:
```cpp
traverse(tree_.root, player, hand_weights_ptr_[player], hand_weights_ptr_[1 - player], 0);
```

Where `hand_weights_ptr_` points into `RiverGame::hand_weights` initialized
at `river_game.cpp:200-208`:
```cpp
double total = 0.0;
for (const auto &hand : hands[player]) {
    total += hand.weight;
}
hand_weights[player].assign(hands[player].size(), 0.0);
if (total > 0.0) {
    for (std::size_t i = 0; i < hands[player].size(); ++i) {
        hand_weights[player][i] = hands[player][i].weight / total;
    }
}
```

**Each hand's reach starts at `weight / total_weight`** — i.e., the range is
**normalized to sum to 1.0** across the player's hand list. For a uniform
55-hand range (K72) each hand starts at `1/55 ≈ 0.0182`. Ours starts each
hand at `1.0`.

---

## 3. Chance node tree construction in our solver

`exploit.rs:404-423` (the chance branch of `build_node`):
```rust
if player == -1 {
    // Chance node — board-card deal. (Hole-card chance is handled
    // by the chance-enum root dispatch; we never see it here.)
    let outcomes = state.chance_outcomes();
    if outcomes.is_empty() {
        return FlatNode::Fold {
            contributions: state.contributions,
            big_blind,
            folded_player: 0,
        };
    }
    let prob = outcomes[0].1;
    let mut children = Vec::with_capacity(outcomes.len());
    for (action, _p) in outcomes {
        let child_state = state.apply(action);
        let cidx = self.add(&child_state);
        children.push(cidx);
    }
    return FlatNode::Chance { prob, children };
}
```

**`prob` is read once from `outcomes[0].1` at tree-build time.** `outcomes`
is computed in `hunl.rs:533-568`:
```rust
pub fn chance_outcomes(&self) -> Vec<(u8, f64)> {
    if self.cur_player != -1 || self.is_terminal() {
        return Vec::new();
    }
    let hole = match self.hole_cards {
        Some(h) => h,
        None => {
            return Vec::new();
        }
    };
    let mut held = [false; 64];
    for c in [hole[0][0], hole[0][1], hole[1][0], hole[1][1]] {
        held[c as usize] = true;
    }
    for &c in &self.board {
        held[c as usize] = true;
    }
    let mut remaining: Vec<u8> = Vec::with_capacity(52);
    for r in 2u8..=14 {
        for s in 0u8..4 {
            let c = card_to_int(r, s);
            if !held[c as usize] {
                remaining.push(c);
            }
        }
    }
    if remaining.is_empty() {
        return Vec::new();
    }
    let p = 1.0 / remaining.len() as f64;
    remaining.into_iter().map(|c| (c, p)).collect()
}
```

**`prob` = `1 / remaining.len()` where `remaining` excludes the PLACEHOLDER
hole cards.** And the tree is built with placeholder holes per
`dcfr_vector.rs:783`:
```rust
let placeholder = initial.clone_with_hole_cards([eval_ctx.hole[0][0], eval_ctx.hole[1][0]]);
let tree = BettingTree::build_from(&placeholder);
```

At solve time, when the traversal reaches a `FlatNode::Chance` with some
(hp, ho) pair currently being weighted, the `prob` is the placeholder-based
constant — NOT recomputed per (hp, ho). If the placeholder holes don't
overlap with the true (hp, ho), `remaining.len()` is off by 0, 1, or 2 cards
relative to the truth. The `children` list (board-card outcomes) is also
built from the placeholder's remaining deck — it can include cards that the
true (hp, ho) holds, and exclude cards that the true (hp, ho) doesn't hold.

**Concrete example**: turn-card chance node on a flop spot. Placeholder holes
fill 4 cards. `remaining.len() = 52 - 3 - 4 = 45`, so `prob = 1/45`. At solve
time, for a (hp, ho) pair where hp and ho share 2 distinct cards from the
placeholder, the true remaining size is also 45 → prob is right. But for a
(hp, ho) pair where hp uses one of the placeholder's cards, the true
remaining is 46 → prob should be `1/46` ≈ -2.2% off. The child list also
omits one card that the true pair would have allowed.

**Impact on K72/A83**: ZERO. Both spots are river-only (5-card boards). No
`FlatNode::Chance` is generated because `current_player() != -1` after the
betting closes on a full board — the tree is built with only decision and
terminal nodes.

This bug IS latent for any future turn/flop range-vs-range solve that hits a
chance node (all-in run-out on flop, turn-to-river, etc.).

---

## 4. Side-by-side comparison

| Aspect | Ours | Brown | Match? |
|---|---|---|---|
| Reach signature (`reach_p`, `reach_opp`) per-hand vector | yes | yes | yes |
| Opp decision: `next_reach[h] = reach_opp[h] * strat[h,a]` | yes | yes | yes |
| Own decision: `next_reach[h] = reach_p[h] * strat[h,a]` | yes | yes | yes |
| Counterfactual reach at leaf (only `reach_opp` consumed) | yes | yes | yes |
| Regret update uses `(action_value - node_value)`, no extra reach mult | yes | yes | yes |
| `strategy_sum` weighted by `reach_p * avg_weight` | yes | yes | yes |
| Blocker filter at leaf (disjoint card check) | inline (`terminal_value_vector:636-642`) | precomputed `blocked_less/equal/greater` (`vector_eval.cpp:39-78`) | **yes — same semantics, different implementation** |
| Initial reach per hand | `1.0` flat | `weight / total_weight` (normalized) | **DIFFERENT (scale-only)** |
| Chance node enumeration (board cards) | uniform `1 / remaining_after_placeholder_hole_cards` | NONE (river-only solver) | **DIFFERENT — chance only exists on our side** |
| Chance node weighting recomputed per (hp, ho)? | NO — baked in at tree-build time with placeholder holes | N/A | **DIFFERENT (latent bug for our turn/flop RvR; not exercised by K72/A83)** |

---

## 5. Specific check resolutions

- **Counterfactual reach.** Both solvers correctly weight regret by opponent
  reach only (the cf-utility is opp-reach-weighted at the leaf; the regret
  delta `action_value - node_value` then carries that weighting up). **Match.**
- **Chance node enumeration.** Ours enumerates remaining-deck cards
  exhaustively, weighted uniformly by `1/remaining.len()`. Blocked cards
  (held by EITHER PLACEHOLDER hole or the board) are excluded from
  enumeration. The blocker exclusion uses the placeholder holes, not the
  true per-hand holes — see §3 for the latent bug. Brown has no chance
  nodes; the river is fixed at construction. **DIFFERENT but not triggered
  by river spots.**
- **Hole-card distribution at root.** Ours: `EvalContext::from_root`
  (`dcfr_vector.rs:525-570`) enumerates C(52-|board|, 2) per player as a
  flat unweighted list (each hand reach 1.0). Brown: range comes from
  `RiverConfig.ranges[player]` (`river_game.h:42`) as an explicit hand list,
  then normalized to sum to 1.0 per player. **Same semantic universe (full
  C(47,2) when ranges are empty per `river_game.cpp:216-217`); different
  scaling.** For K72/A83 the ranges are user-supplied explicit hand lists
  (`river_spots.json` players[].hands), so the SAME hands enter both
  solvers; only the per-hand reach magnitude differs.

---

## 6. Verdict

**DIFFERENT, but neither difference explains the K72/A83 22-42pp divergence.**

1. **Reach normalization (`1.0` flat vs `weight/total`)**: scale-only.
   Strategy is scale-invariant under regret-matching at steady state
   (`regret` and `strategy_sum` both scale by the same constant `k`, and
   normalization in `compute_strategy` + `compute_avg_strategy` cancels `k`).
   **Will not produce a 22-42pp per-action divergence.** Worth fixing for
   numerical hygiene (cleaner DCFR discount math, easier to reason about
   convergence), but NOT a P0 ship-blocker.
2. **Chance-node placeholder-reach bug**: latent for turn/flop
   range-vs-range solves. **Not exercised by K72/A83 (river-only, no chance
   nodes).** Worth a v1.5.x fix (recompute `prob` from the actual remaining
   deck per (hp, ho) pair, OR build the chance subtree branching on the
   true remaining deck), but NOT the source of the current deep-cap
   divergence.

The 22-42pp deep-cap divergence on K72/A83 still requires another driver.
Candidates ruled out by this audit:

- Reach-propagation algebra (decision and opp nodes) — **byte-identical**.
- Counterfactual reach at terminal — **byte-identical**.
- Chance node weighting — **N/A for the failing river spots**.

Remaining candidates the user should investigate next (NOT audited here per
task scope):

- Hand-strength tie-handling at showdown (Brown uses precomputed
  `blocked_less/equal/greater` partition with rank-equality comparison;
  ours uses runtime `Strength::evaluate_7` + scalar `>` / `<` / `=`).
- Action-axis remap quirks at deep-cap (the prior triage flagged action
  permutation issues at `b1000r3000` and `b1500r5000`; the
  `_brown_to_rust_action_permutation` may not be the full story for nodes
  beyond raise-cap).
- Range-slot indexing between fixture order and Brown's internal hand
  ordering (Brown sorts hands by strength for `EvalCache.sorted_indices`
  at `vector_eval.cpp:11-15`).
- DCFR discount-application order: Brown discounts at the **own** node
  before computing strategy (`trainer.cpp:185-188`); ours does the same
  (`dcfr_vector.rs:384-398`), but the prior `strategy` (computed before
  discount at `dcfr_vector.rs:347-352`) is recomputed only at the own node.
  At the opponent node, the strategy is computed from current (un-discounted-
  this-iteration) regrets. Brown does the same. Likely match, but worth a
  pass.
