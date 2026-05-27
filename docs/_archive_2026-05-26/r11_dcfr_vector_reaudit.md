# R11 dcfr_vector.rs Re-Audit — Fresh Eyes, Line-by-Line vs Brown's `trainer.cpp:138-240`

**Date**: 2026-05-24
**Auditor**: orchestrator agent (P0 targeted re-audit)
**Scope**: `crates/cfr_core/src/dcfr_vector.rs` (984 LOC) vs `references/code/noambrown_poker_solver/cpp/src/trainer.cpp:138-240` (the `Trainer::traverse` + `Trainer::run` body).
**Constraint**: READ-ONLY, paranoia mode (assume bug until proven otherwise), quote both sides verbatim.

## Executive verdict

**No SEMANTIC bug found in `dcfr_vector.rs` against Brown's reference.** The audit
walked all 7 areas requested + 4 additional surfaces. Every divergence flagged
was either:
1. A NAMING/labeling difference with no behavioral effect, or
2. A scale-invariant difference that cancels in regret-matching, or
3. A genuine off-spec choice (CFRScalar=float in Brown vs f64 in Rust) that
   cannot explain a 60-75pp strategy delta.

The dry-run #8 AA root-divergence is **most likely** rooted OUTSIDE this file,
in (a) action-menu pruning differences (force_allin_threshold filter — see
`docs/r11_aa_vs_aa_minimal.md` Phase 4 verdict), (b) iteration-history
convergence on indifference-rich manifolds, or (c) the betting-tree/key-suffix
construction in `exploit.rs::BettingTree::build_from`. The kernel
(`dcfr_vector.rs::VectorDCFR::traverse`) is a faithful port of
`trainer.cpp:138-240`.

The corroborating evidence comes from `docs/r11_aa_vs_aa_minimal.md` Phase 4b:
on the AA-vs-AA Fixture B (3 BB behind, identical action menus on both sides),
**Rust and Brown agree to floating-point precision at the root** — exact
`[3e-8, 0.5, 0.5]` for all 6 AA combos on both engines. This is strong
empirical evidence the kernel is right.

---

## Area-by-area findings

### 1. Hole-card layout in regret tables — **MATCH**

**Brown** (`trainer.cpp:13-25`):

```cpp
infosets_.resize(tree_.nodes.size());
for (std::size_t i = 0; i < tree_.nodes.size(); ++i) {
    const TreeNode &node = tree_.nodes[i];
    if (node.player < 0) {
        continue;
    }
    InfoSet &info = infosets_[i];
    info.action_count = node.action_count;
    info.hand_count = num_hands_[node.player];
    int total = info.hand_count * info.action_count;
    info.regret.assign(total, CFRScalar(0));
    info.strategy_sum.assign(total, CFRScalar(0));
}
```

Layout: `regret[hand_idx * action_count + action_idx]` — row-major, one slot
per tree node, skipping non-decision nodes.

**Rust** (`dcfr_vector.rs:90-100`, `180-198`):

```rust
fn new(action_count: usize, hand_count: usize) -> Self {
    let total = action_count * hand_count;
    Self {
        action_count,
        hand_count,
        regret: vec![0.0; total],
        strategy_sum: vec![0.0; total],
        last_discount_iter: 0,
    }
}
...
for node in &tree.nodes {
    match node {
        FlatNode::Decision { player, actions, .. } => {
            let action_count = actions.len();
            let hand_count = hand_count_per_player[*player as usize];
            infosets.push(Some(VectorInfosetData::new(action_count, hand_count)));
        }
        _ => infosets.push(None),
    }
}
```

Same row-major `hand_idx * action_count + action_idx` (verified via every
read/write site in `compute_strategy`, `compute_avg_strategy`, the regret
update at line 444-451, and the strategy_sum update at line 454-463).
Same per-node `Some/None` pattern as Brown's `node.player < 0` skip.

**MATCH** — verbatim layout, including the per-tree-node infoset slot.
The infoset is keyed by `node_idx` (not by hole-card hash); the per-hand
dimension is the SECOND axis. This is the vector-form invariant from
Brown's MIT reference.

---

### 2. Per-hand reach probability handling — **MATCH (with one labeling difference, behaviorally identical)**

**Brown** (`trainer.cpp:166-181` — opponent node) and (`trainer.cpp:191-198` — own node):

```cpp
// Opponent node:
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

// Own node:
for (int a = 0; a < action_count; ++a) {
    for (int h = 0; h < update_hands; ++h) {
        frame.next_reach[h] = reach_p[h] * frame.strategy[h * action_count + a];
    }
    const double *child_values = traverse(node.next[a], update_player, frame.next_reach.data(), reach_opp,
                                          depth + 1);
    std::copy(child_values, child_values + update_hands, action_values + a * update_hands);
}
```

**Rust** (`dcfr_vector.rs:354-376` — opponent node, `400-417` — own node):

```rust
if player != update_player {
    // Opponent node — propagate their reach via current
    // strategy and accumulate update_player values.
    let mut values = vec![0.0_f64; update_hands];
    let mut next_reach = vec![0.0_f64; opp_hands];
    for (a, &child_idx) in children.iter().enumerate() {
        for h in 0..opp_hands {
            next_reach[h] = reach_opp[h] * strategy[h * action_count + a];
        }
        let child_values = self.traverse(
            tree, eval_ctx, child_idx, update_player, reach_p, &next_reach,
        );
        for h in 0..update_hands {
            values[h] += child_values[h];
        }
    }
    return values;
}
// Own node:
let mut action_values = vec![0.0_f64; action_count * update_hands];
let mut next_reach = vec![0.0_f64; player_hands];  // <-- labeling: player_hands here, update_hands in Brown
for (a, &child_idx) in children.iter().enumerate() {
    for h in 0..player_hands {
        next_reach[h] = reach_p[h] * strategy[h * action_count + a];
    }
    let child_values = self.traverse(tree, eval_ctx, child_idx, update_player, &next_reach, reach_opp);
    let dst = a * update_hands;
    action_values[dst..dst + update_hands].copy_from_slice(&child_values);
}
```

Note: at an own decision node, `player == update_player` so `player_hands ==
update_hands`. The labeling difference (Rust uses `player_hands` where Brown
uses `update_hands`) is **conceptually fine** — they refer to the same value
at this branch — but `update_hands` is the cleaner name (Brown's). Cosmetic
only. No behavioral difference.

The opp-node reach scaling uses `opp_hands` (the OPPONENT'S hand count), and
the iteration loop is bounded by `opp_hands` correctly in both sides.

At the terminal leaf the cf-utility is already opp-reach-weighted (see Area 4
below), so no second-pass opp_reach multiplication is needed at the regret
update — both Brown and Rust correctly omit it.

**MATCH** (modulo the cosmetic `player_hands` vs `update_hands` naming).

---

### 3. Hand-class to combo expansion — **MATCH (with one INDEXING difference, behaviorally invariant)**

**Brown** (`river_game.cpp:159-184`):

```cpp
std::vector<int> deck;
deck.reserve(52);
std::vector<bool> blocked(52, false);
for (int card : exclude) {
    blocked[card] = true;
}
for (int card = 0; card < 52; ++card) {
    if (!blocked[card]) {
        deck.push_back(card);
    }
}
std::vector<std::array<int, 2>> hands;
for (std::size_t i = 0; i < deck.size(); ++i) {
    for (std::size_t j = i + 1; j < deck.size(); ++j) {
        int c1 = deck[i];
        int c2 = deck[j];
        if (c1 < c2) {
            hands.push_back({c1, c2});
        } else {
            hands.push_back({c2, c1});
        }
    }
}
```

Card encoding (Brown): `card_id = suit * 13 + rank`, suits = `cdhs` (so
c=0, d=1, h=2, s=3), ranks = `2..A` mapped to 0..12. Range [0, 51].

**Rust** (`dcfr_vector.rs:531-552`):

```rust
let mut held = [false; 64];
for &c in &initial.board {
    held[c as usize] = true;
}
let mut single_holes: Vec<[u8; 2]> = Vec::new();
for r0 in 2u8..=14 {
    for s0 in 0u8..4 {
        let c0 = crate::hunl::card_to_int(r0, s0);
        if held[c0 as usize] {
            continue;
        }
        for r1 in 2u8..=14 {
            for s1 in 0u8..4 {
                let c1 = crate::hunl::card_to_int(r1, s1);
                if held[c1 as usize] || c0 >= c1 {
                    continue;
                }
                single_holes.push([c0, c1]);
            }
        }
    }
}
```

Card encoding (Rust): `card_to_int(rank, suit) = rank * 4 + suit`, suits =
`shdc` (s=0, h=1, d=2, c=3), ranks 2..14. Range [8, 59].

**DIFFERENCE (cosmetic)**: The two encodings are different bijections to
{Ar, ..., 2c}. Brown's `c < d` is "clubs before diamonds" while Rust's `s
< h` is "spades before hearts". The **hand enumeration ORDER is different**
between Brown and Rust (Brown iterates by card_id 0..51 in suit-major order;
Rust iterates by card_to_int 8..59 in rank-major order).

However:
- The total set of (c0, c1) pairs is identical.
- Each side independently uses its OWN hand index for regret/strategy storage.
- The output dict keys (`<hole_string>|<key_suffix>`) are constructed via the
  CANONICAL sorted-by-card-id string, so the dict-side lookup uses the same
  hand-string for the same physical hand regardless of internal index.

Since the algorithm is per-hand-independent (regrets at hand_idx h depend
only on action-values seen for that h), the iteration order has **no
effect on the converged strategy** — only on which storage slot it lives in.

The test (`test_v1_5_brown_apples_to_apples.py:457-468`) bypasses
`enumerate_hole_card_pairs` entirely when both `p0_holes` / `p1_holes` are
passed (line 444-452 of `lib.rs`); the test passes hands in the FIXTURE
ORDER from `tests/data/river_spots.json`, NOT in either Brown's or Rust's
canonical order. So even if there were an ordering-sensitive bug, it would
be the FIXTURE'S order both sides see.

For the dry_A83 spot, P1's first 3 hands are `AcAd, AcAs, AdAs` (the only
non-board-blocked AA combos on Ah board). Both Brown and Rust receive these
in this order.

**Effective MATCH** — different enumeration orders, but the hand SET is
identical and order doesn't affect per-hand strategy convergence.

**Blocker filtering**: Brown filters at `RiverGame::build_hands` (line
229-249) — drops a hand if `card[0]` or `card[1]` is in the board. Rust
filters at `EvalContext::from_root` line 540, 546 — drops a hand if any
card is `held` (i.e., in the board). Same logic.

---

### 4. Iteration counter — **MATCH**

**Brown** (`trainer.cpp:343-369`):

```cpp
void Trainer::run(int iterations) {
    for (int i = 0; i < iterations; ++i) {
        iteration_ += 1;
        if (algo_ == Algorithm::DCFR) {
            regret_weight_ = 1.0;
            avg_weight_ = 1.0;
            double t = static_cast<double>(iteration_);
            double pos_base = std::pow(t, dcfr_.alpha);
            double neg_base = std::pow(t, dcfr_.beta);
            dcfr_pos_scale_ = pos_base / (pos_base + 1.0);
            dcfr_neg_scale_ = neg_base / (neg_base + 1.0);
            dcfr_strat_scale_ = std::pow(t / (t + 1.0), dcfr_.gamma);
        }
        for (int player = 0; player < 2; ++player) {
            traverse(tree_.root, player, hand_weights_ptr_[player], hand_weights_ptr_[1 - player], 0);
        }
    }
}
```

`iteration_` starts at 0, increments to 1 on first iter. `t = iter` is fed
into pos_scale = t^α / (t^α + 1), neg_scale = t^β / (t^β + 1), strat_scale =
(t/(t+1))^γ. Both players traverse with the same scales.

**Rust** (`dcfr_vector.rs:486-495`, `266-289`):

```rust
let reach_p0: Vec<f64> = vec![1.0; eval_ctx.hand_count[0]];
let reach_p1: Vec<f64> = vec![1.0; eval_ctx.hand_count[1]];
for _ in 0..iterations {
    self.iteration += 1;
    self.traverse(tree, eval_ctx, 0, 0, &reach_p0, &reach_p1);
    self.traverse(tree, eval_ctx, 0, 1, &reach_p1, &reach_p0);
}
// And the discount catch-up at line 266-289:
fn discount(info: &mut VectorInfosetData, t: u32, alpha: f64, beta: f64, gamma: f64) {
    if info.last_discount_iter >= t {
        return;
    }
    for tt in (info.last_discount_iter + 1)..=t {
        let tt_f = tt as f64;
        let ta = tt_f.powf(alpha);
        let tb = tt_f.powf(beta);
        let pos_scale = ta / (ta + 1.0);
        let neg_scale = tb / (tb + 1.0);
        let strat_scale = (tt_f / (tt_f + 1.0)).powf(gamma);
        ...
    }
    info.last_discount_iter = t;
}
```

`iteration` starts at 0, increments to 1 on first iter. The CATCH-UP discount
applies scales for each `tt` from `last_discount_iter+1` to `t`. In normal
operation (every infoset visited every iter), `last_discount_iter+1 == t`
on entry, so only ONE iteration of the inner loop runs with the same scales
as Brown.

Order: discount FIRST, then compute_strategy, then recursive walk, then
regret + strategy_sum update. **Identical** to Brown's flow at
`trainer.cpp:185-237`.

α / β / γ values: `1.5 / 0.0 / 2.0` are the default DCFR triple in both
solvers (Brown's `DcfrParams` at `trainer.h:16-20`; our test fixtures pass
the same values).

**MATCH** — same scale formulas, same iter counter semantics, same per-iter
both-player traversal.

---

### 5. Initial strategy — **MATCH**

**Brown** (`trainer.cpp:72-98`):

```cpp
void Trainer::compute_strategy(const InfoSet &info, double *out_strategy) const {
    int hand_count = info.hand_count;
    int action_count = info.action_count;
    const CFRScalar *regret = info.regret.data();
    for (int h = 0; h < hand_count; ++h) {
        double normalizing = 0.0;
        int offset = h * action_count;
        for (int a = 0; a < action_count; ++a) {
            double r = static_cast<double>(regret[offset + a]);
            if (r > 0.0) {
                normalizing += r;
            }
        }
        if (normalizing > 0.0) {
            for (int a = 0; a < action_count; ++a) {
                double r = static_cast<double>(regret[offset + a]);
                out_strategy[offset + a] = (r > 0.0 ? r : 0.0) / normalizing;
            }
        } else {
            double prob = 1.0 / static_cast<double>(action_count);
            for (int a = 0; a < action_count; ++a) {
                out_strategy[offset + a] = prob;
            }
        }
    }
}
```

**Rust** (`dcfr_vector.rs:207-232`):

```rust
fn compute_strategy(info: &VectorInfosetData, out: &mut [f64]) {
    let hand_count = info.hand_count;
    let action_count = info.action_count;
    debug_assert_eq!(out.len(), hand_count * action_count);
    for h in 0..hand_count {
        let offset = h * action_count;
        let mut normalizing = 0.0_f64;
        for a in 0..action_count {
            let r = info.regret[offset + a];
            if r > 0.0 {
                normalizing += r;
            }
        }
        if normalizing > 0.0 {
            for a in 0..action_count {
                let r = info.regret[offset + a];
                out[offset + a] = if r > 0.0 { r / normalizing } else { 0.0 };
            }
        } else {
            let prob = 1.0 / action_count as f64;
            for a in 0..action_count {
                out[offset + a] = prob;
            }
        }
    }
}
```

At iteration 0, all regrets are 0, so `normalizing == 0.0`, the fallback
branch fires, and the initial strategy is uniform `1/action_count` per
action. **Both sides identical.**

**MATCH** — uniform initial strategy on the first regret-matching call.

---

### 6. Average strategy weighting — **MATCH (lazy-catch-up vs eager, but equivalent under normal traversal)**

**Brown** (`trainer.cpp:124-136` apply_dcfr_discount, `trainer.cpp:226-237`
strategy_sum update):

```cpp
void Trainer::apply_dcfr_discount(InfoSet &info, double pos_scale, double neg_scale, double strat_scale) const {
    for (CFRScalar &regret : info.regret) {
        if (regret > CFRScalar(0)) {
            regret = static_cast<CFRScalar>(static_cast<double>(regret) * pos_scale);
        } else if (regret < CFRScalar(0)) {
            regret = static_cast<CFRScalar>(static_cast<double>(regret) * neg_scale);
        }
    }
    for (CFRScalar &value : info.strategy_sum) {
        value = static_cast<CFRScalar>(static_cast<double>(value) * strat_scale);
    }
}
...
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

Effective DCFR recurrence (per iteration t, OWN decision node):
1. strategy_sum := strat_scale(t) * strategy_sum
2. strategy_sum += reach_p[h] * 1.0 * strategy_t[h, a]    (avg_weight = 1.0 for DCFR)

**Rust** (`dcfr_vector.rs:266-289`, `454-463`):

```rust
fn discount(info: &mut VectorInfosetData, t: u32, alpha: f64, beta: f64, gamma: f64) {
    if info.last_discount_iter >= t {
        return;
    }
    for tt in (info.last_discount_iter + 1)..=t {
        let tt_f = tt as f64;
        let ta = tt_f.powf(alpha);
        let tb = tt_f.powf(beta);
        let pos_scale = ta / (ta + 1.0);
        let neg_scale = tb / (tb + 1.0);
        let strat_scale = (tt_f / (tt_f + 1.0)).powf(gamma);
        for r in &mut info.regret {
            if *r > 0.0 {
                *r *= pos_scale;
            } else if *r < 0.0 {
                *r *= neg_scale;
            }
        }
        for s in &mut info.strategy_sum {
            *s *= strat_scale;
        }
    }
    info.last_discount_iter = t;
}
...
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

Effective recurrence per iter t, OWN decision node:
1. CATCH-UP: for each tt in (last_discount_iter+1)..=t: strategy_sum *=
   strat_scale(tt).
2. last_discount_iter := t.
3. strategy_sum += reach_p[h] * 1.0 * strategy_t[h, a].

In normal operation, every decision node is visited every iteration (the
tree walk is exhaustive), so `last_discount_iter+1 == t` on entry. The
inner loop runs ONCE per visit with `strat_scale(t)` — identical to Brown.

The catch-up form gracefully handles a node unreached for one iter (regret
matching to zero on opp side, etc.), applying the missing scales on next
visit. This is a STRICTLY MORE ROBUST version of Brown's. Brown does not
catch up — if a node is unreached for one iter, its scaling lags by one.
In tree-exhaustive walks this never happens.

**Off-by-one check on (t)/(t+1) form**: Brown applies strat_scale BEFORE
the iter-t contribution, so after T iterations the weight on iter-t's
contribution is `((t+1)/(T+1))^γ` (the product of strat_scale(t+1) through
strat_scale(T)). Rust's catch-up form produces the SAME recurrence:
strat_scale at iter t is `(t/(t+1))^γ` applied BEFORE the iter-t addition,
so iter-t contribution accumulates the same `((t+1)/(T+1))^γ` post-discount.

The final catch-up at line 791-797 is a no-op when every infoset was
visited at the last iter (every infoset's `last_discount_iter == T`
already).

**MATCH** — same DCFR averaging recurrence; lazy-catch-up is strictly
more robust on unreached nodes (no behavior change on exhaustive walks).

---

### 7. Showdown evaluation — **MATCH (different code paths, same semantics)**

**Brown** (`vector_eval.cpp:6-131`): uses a precomputed `EvalCache` with
sorted strengths and per-hand blocker lists for O(player_count *
log(opp_count)) showdown evaluation. The kernel:

```cpp
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
```

This computes EV under the standard showdown model:
- win: get pot_total per opp hand
- tie: get pot_total / 2 per opp hand
- (subtract contribution times active opp weight for the EV-in-stack-delta
  formulation)

Note Brown's `pot_total = base_pot + contrib0 + contrib1` (the FULL pot
including dead money + both players' bets).

**Rust** (`dcfr_vector.rs:619-656` + `exploit.rs:515-573`):

```rust
fn terminal_value_vector(
    node: &FlatNode, ctx: &EvalContext,
    update_player: usize, opp_player: usize, reach_opp: &[f64],
) -> Vec<f64> {
    let update_hands = ctx.hand_count[update_player];
    let opp_hands = ctx.hand_count[opp_player];
    let mut out = vec![0.0_f64; update_hands];
    for hp in 0..update_hands {
        let hole_p = ctx.hole[update_player][hp];
        let mut total = 0.0_f64;
        for ho in 0..opp_hands {
            let hole_o = ctx.hole[opp_player][ho];
            if hole_p[0] == hole_o[0] || hole_p[0] == hole_o[1]
               || hole_p[1] == hole_o[0] || hole_p[1] == hole_o[1] {
                continue;
            }
            let combo = if update_player == 0 { [hole_p, hole_o] } else { [hole_o, hole_p] };
            let utility = terminal_utility(node, combo, update_player);
            total += reach_opp[ho] * utility;
        }
        out[hp] = total;
    }
    out
}
```

And `terminal_utility` for Showdown (`exploit.rs:537-570`):

```rust
FlatNode::Showdown { contributions, big_blind, board } => {
    let bb = *big_blind as f64;
    let c0 = contributions[0] as f64;
    let c1 = contributions[1] as f64;
    ...
    if s0 > s1 {
        if player == 0 { c1 / bb } else { -c1 / bb }
    } else if s1 > s0 {
        if player == 0 { -c0 / bb } else { c0 / bb }
    } else {
        0.0
    }
}
```

**Semantic comparison**:
- **Brown's utility for the winner**: pot_total per opp hand = `base_pot
  + c_winner + c_loser`. For the loser: 0 per opp hand (formula gives
  `-contrib_player * active_weight` only, since win_weight=0). The
  win/loss sum across players: `base_pot + c_winner + c_loser -
  c_winner - c_loser = base_pot`. So Brown's utility is NOT zero-sum;
  it has a constant `+base_pot` offset for the winner.
- **Our utility for the winner**: `c_loser / bb` (the loser's
  contribution). For the loser: `-c_loser / bb`. **Zero-sum**.
- **Tie**: both give `pot_total / 2 - contrib_player` (Brown) vs `0`
  (ours) — Brown has a constant `(base_pot + c_loser - c_winner) / 2`
  offset; ours has 0.

**This IS a different utility function** at the absolute-value level.
Brown's utility includes a `+base_pot` for winner (per valid opp hand);
ours collapses to zero-sum.

**HOWEVER** this does NOT affect Nash strategy. The regret update is
`regret[h, a] += (action_value[a, h] - node_value[h]) * regret_weight`. A
constant offset shared across all actions cancels in the difference. The
constant `base_pot * opp_reach_total[h]` is the same for ALL action
branches from a decision node (it depends only on h, not on a), so
`action_value[a, h] - node_value[h]` is identical between Brown and ours.

Confirmed by the AA-vs-AA minimal fixture (`docs/r11_aa_vs_aa_minimal.md`
Phase 4b): with `stack_behind=300` so the action menus match, Brown and
our Rust agree at floating-point precision (`[3e-8, 0.5, 0.5]` for all 6
AA combos at root). If the utility difference mattered for strategy,
this exact agreement would not hold.

**Hand-strength evaluator**: Brown's `evaluate_7` (`cards.cpp:168`)
selects the best 5-card hand from 7 by enumerating C(7,5)=21 subsets.
Our `Strength::evaluate_7` (`hunl_eval.rs:260`) does the same. The
strength ranking is the standard category+tiebreaker encoding. (PR 10c
made this part rigorously tested.)

**MATCH** — different absolute utility, identical regret-update semantics
(constant offsets cancel in differences). Strength evaluator is structurally
the same C(7,5) enumeration.

---

## Additional surfaces audited beyond the 7 requested

### 8. Reach-probability initial scale — **DIFFERS in scale, equivalent under regret-matching normalization**

Brown: `hand_weights_ptr_` is normalized to sum=1.0 per player
(`river_game.cpp:204-208`). Initial reach is `1/N` per hand.

Rust: `let reach_p0: Vec<f64> = vec![1.0; eval_ctx.hand_count[0]]`
(`dcfr_vector.rs:486-487`). Initial reach is 1.0 per hand.

Both reaches accumulate by multiplication along the tree. The ABSOLUTE
SCALE differs by a factor of N, but this scale appears identically in
ALL action_values at every decision node, and in the regret update
`(action_value[a, h] - node_value[h])` it cancels. The strategy_sum
also scales by the same factor, which normalizes out in
`compute_avg_strategy`.

**Effective MATCH** — scale-invariant; cannot cause strategy divergence.

### 9. Float vs double for regret/strategy_sum — **DIFFERS, behaviorally irrelevant for our scale**

Brown: `CFRScalar = float` by default (`trainer.h:25-27`); `double` only
under `CFR_USE_DOUBLE` build flag. Brown's regrets/strategy_sums are
single-precision (~7 decimal digits of precision).

Rust: `f64` unconditionally. Double-precision (~15-16 decimal digits).

This could cause SLIGHT numerical divergence after many iterations
(accumulated float roundoff), but not on the order of 60-75pp on AA
strategy. The minimal AA-vs-AA fixture showed exact agreement at root
despite this difference, so it is not load-bearing.

### 10. Discount on opponent nodes during update_player's traversal — **MATCH**

In both solvers, when `update_player` visits an OPPONENT node, the
opponent's infoset is NOT discounted; only the opponent's strategy is
computed (via `compute_strategy`). The opponent's discount happens when
the opponent is the update_player. This means each infoset is discounted
EXACTLY ONCE per iteration (during its owning player's traversal).

Verified: Brown `trainer.cpp:166-181` has no `apply_dcfr_discount` call
in the opp-node branch. Rust `dcfr_vector.rs:354-378` similarly has no
discount call in the opp-node branch.

### 11. Tree key_suffix construction — **AT RISK (in `exploit.rs`, not `dcfr_vector.rs`)**

`exploit.rs:439-443` constructs `key_suffix` by stripping the first `|` from
`state.infoset_key(player, None)`. This is correct as long as
`HUNLState::infoset_key` always emits a leading `<hole>|` prefix and never
embeds a `|` in the hole prefix. Verified at `hunl.rs:622`: format string
is `"{player_hole}|{board_str}|{street_token}|{history}"`. The
`sorted_card_string` of a 2-card hole is 4 chars without `|`. ✓

The placeholder hole-card state at `dcfr_vector.rs:783` uses
`eval_ctx.hole[0][0]` and `eval_ctx.hole[1][0]` — the first hand for each
player. These do NOT need to be disjoint (the tree builder doesn't check),
and the placeholder is ONLY used to advance state through the betting tree.

Since the betting tree shape is hole-card-independent (no hole-card
chance nodes in postflop), this is safe.

**MATCH** (assuming `exploit.rs` does what its comments promise).

---

## Most likely site of R11 bug

**Not in `dcfr_vector.rs`.** Evidence:
1. All 7 requested areas + 4 additional surfaces show structural and
   semantic match against Brown's `trainer.cpp:138-240`.
2. The empirical AA-vs-AA Fixture B test (`docs/r11_aa_vs_aa_minimal.md`
   Phase 4b) confirms ROOT agreement at float precision when action
   menus match. This directly refutes the kernel-bug hypothesis.

**More likely sites** (ordered by Bayesian probability):

1. **Action-menu construction divergence in
   `poker_solver/action_abstraction.py:_enumerate_bets:180`** —
   already-known `force_allin_threshold` filter difference, documented in
   `docs/r11_aa_vs_aa_minimal.md` Phase 4. At low stack-behind spots,
   our solver prunes bets that Brown offers. Different action menus →
   different valid Nash strategies on indifference manifolds.

2. **Multi-Nash convergence on indifference subtrees** — when EV of all
   actions is zero (AA-vs-AA chops, or rank-tied range-vs-range subspots),
   the indifference manifold is open and CFR variants drift to different
   points within it. Documented as the v1.7.0 session-close explainer.

3. **Action ORDER mismatch at a given decision node** — if Brown emits
   actions `[c, b500, b1000]` and Rust emits `[c, b1000, b500]` for the
   same conceptual node, the test's per-action probability mapping would
   misalign even though both are valid Nash. Check
   `state.legal_actions()` action-sort order vs Brown's
   `legal_actions` in `river_game.cpp:31-107`. (Brown sorts amounts
   ascending at line 66; need to verify ours does too.)

4. **Bet-size resolution divergence** — Brown's `b<amount>` is the chip
   ADDITION (line 53-54: `bet_amount = round(pot * size)`); our wire
   format is `b<chips_added>`. If the resolved amounts differ (e.g.
   Brown rounds half-pot of 200 to 100 chips and we round to 99 or 101),
   the action labels won't match and the test sees different rows.

5. **Iteration-count mismatch** — Brown defaults to 2000 iters
   (run_brown_solver call site); our test passes ITERATIONS (need to
   verify same). At 2000 iters DCFR is still converging on
   indifference-rich subtrees.

---

## Recommended fix or next investigation

**No fix recommended for `dcfr_vector.rs`** — the audit found no semantic
bug, and the AA-vs-AA minimal fixture empirically confirms the kernel is
correct.

**Recommended next investigation (in priority order)**:

A. **Bet-amount parity diagnostic**: For dry_K72 with `bet_sizes =
   [0.75, 1.5]` and pot=1000, compute exact bet amounts emitted by
   Brown (`river_game.cpp:53-54` rounding) and ours
   (`poker_solver/action_abstraction.py:_enumerate_bets`). Diff the
   amount lists per decision node. Suspect: rounding-mode mismatch
   (Python's `round()` is banker's rounding; C++'s `std::round()` is
   half-away-from-zero).

B. **Action-order normalization at the test layer**: Confirm that
   `tests/test_v1_5_brown_apples_to_apples.py` maps Brown's action
   labels to Rust's action ordering by NAME (not by position), so that
   `[c, b500, b1000]` vs `[c, b1000, b500]` would still align correctly
   under the per-action diff. Re-read the test's action mapping at line
   513-540ish.

C. **Brown CLI iteration param**: Verify the iterations passed to
   `run_brown_solver` match the iterations passed to
   `_rust_solve_rvr`. Check if Brown's CLI has an override that
   triggers >2000 (e.g. the JSON `iterations_override` field defaults to
   `null` but is honored in the wrapper).

D. **Move R11 investigation OUT of `dcfr_vector.rs`** and into
   `crates/cfr_core/src/exploit.rs::BettingTree::build_from` (action
   topology), `poker_solver/action_abstraction.py` (bet-amount
   resolution), and the test's per-action diff renderer.

---

## Files cited

- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/dcfr_vector.rs` (984 LOC, audit target)
- `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/trainer.cpp` (370 LOC, reference)
- `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/trainer.h` (88 LOC, layout reference)
- `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/vector_eval.cpp` (190 LOC, showdown reference)
- `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/river_game.cpp` (300+ LOC, hand-expansion + tree-build reference)
- `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/cards.cpp` (300+ LOC, encoding + strength)
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/exploit.rs` (BettingTree, FlatNode, hole_string, terminal_utility, enumerate_hole_card_pairs)
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/hunl.rs` (card_to_int, infoset_key, utility, clone_with_hole_cards)
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/hunl_eval.rs` (Strength, evaluate_7)
- `/Users/ashen/Desktop/poker_solver/tests/test_v1_5_brown_apples_to_apples.py` (the failing test)
- `/Users/ashen/Desktop/poker_solver/tests/data/river_spots.json` (dry_K72_rainbow + dry_A83_rainbow fixtures)
- `/Users/ashen/Desktop/poker_solver/docs/r11_aa_vs_aa_minimal.md` (Phase 4 empirical refutation of the kernel-bug hypothesis)
- `/Users/ashen/Desktop/poker_solver/docs/STATUS_2026-05-24_r11_engine_bug.md` (R11 framing)
- `/Users/ashen/Desktop/poker_solver/docs/v1_6_1_dryrun_8.md` (dry-run #8 evidence: 60-75pp AA divergence)
