# PR 23 Deep-Cap Algorithmic Triage: `dcfr_vector.rs` vs Brown `trainer.cpp`

**Date:** 2026-05-23
**Agent:** focused algorithmic-triage agent (read-only)
**Inputs:**
- `crates/cfr_core/src/dcfr_vector.rs` (current `main`, post-PR-34)
- `references/code/noambrown_poker_solver/cpp/src/trainer.cpp:138-240` (gold standard)
- `references/code/noambrown_poker_solver/cpp/src/trainer.h:29-88` (InfoSet layout)
- `docs/v1_6_1_bundle_bisection_diagnosis.md` (the 22-42pp divergence claim)
- `docs/pr_23_cell_divergence_deep_dive.md` (prior triage — TEST-side root cause)
- `docs/v1_5_0_per_action_divergence_diagnosis.md` (prior triage — TEST-side root cause)
- `/Users/ashen/Desktop/poker_solver_worktrees/pr-23-p0-off-by-one/...` (PR 34 fix shape)

**Mandate:** Localize the deep-cap facing-bet over-fold / under-call bug in
PR 23's Rust vector-form CFR by comparing it line-by-line against Brown's
reference, classifying any structural divergence by likelihood of explaining
the 22-42pp gap.

---

## TL;DR — Top hypothesis

**None of H1-H4 are supported by a structural divergence in `dcfr_vector.rs`.**

Going line-by-line through Brown's `Trainer::traverse` (`trainer.cpp:138-240`)
against `VectorDCFR::traverse` (`dcfr_vector.rs:302-468`), every load-bearing
update — opponent-reach threading, regret-update arithmetic, strategy_sum
accumulation, action enumeration, DCFR discount math — is structurally
faithful. The single intentional difference (`reach_p` initialized to `vec![1.0]`
in Rust vs `hand_weights_ptr_[player]` normalized-to-1 in Brown) is
documented in `docs/v1_5_0_per_action_divergence_diagnosis.md §4` as
**scale-only**, and regret-matching / DCFR discount are both scale-invariant,
so the equilibrium strategies are identical under this scale change.

**The "22-42pp divergence" claim from the bisection report
(`docs/v1_6_1_bundle_bisection_diagnosis.md §H3`) was DRAFTED BEFORE the
cell-deep-dive (`docs/pr_23_cell_divergence_deep_dive.md`) was written.** The
deep-dive (timestamp 13:56 vs bisection's 14:59 — but the bisection cites the
*staging* doc, not the deep-dive) localized the same 22-42pp cells as a
**test-side action-axis mismatch + range-slot misassignment**, not an
algorithmic bug in `dcfr_vector.rs`. After applying the test-side action-axis
remap and range-swap, the deep-dive verified the strategies match on every
flagged cell.

So the rank ordering of hypotheses is:

| Rank | Hypothesis | Likelihood | Note |
|---|---|---|---|
| 1 | **H5 (NEW): no algorithmic bug; reported divergence is a test artifact** | **HIGH** | Supported by structural read AND by deep-dive's empirical re-test |
| 2 | H1: regret-update opp_reach wrong | **VERY LOW** | Brown does NOT carry `opp_reach` into the regret update (it's already baked into `action_values` via the terminal-leaf return); Rust mirrors this exactly |
| 3 | H2: opp-reach threading wrong at deep-cap | **LOW** | The PR 34 fix already addressed asymmetric ranges; deep-cap nodes use the same threading pattern (player_hands-sized buffers for own-player nodes, opp_hands-sized for opp nodes) |
| 4 | H3: strategy_sum averaging biased | **LOW** | `weight = reach_p[h] * avg_weight` and the inner `strategy_sum[offset+a] += weight * strategy[offset+a]` are byte-for-byte identical between Rust and Brown |
| 5 | H4: action enumeration mismatch at deep-cap | **LOW** (engine-level), **HIGH** (test-comparison-level) | Rust's `enumerate_legal_actions` sorts by action ID at every node (uniform across depths); Brown emits in push-order `[c, f, raises…]`. The two orderings are internally consistent within each engine, but the test compares column-by-column without remapping. PR 35 Fix C tried to fix the parallel ALL_IN-at-cap issue but broke Python parity; the column-axis mismatch is the actually-load-bearing one |

**Confidence (overall) that this triage localizes the bug:** the bug is
**NOT in the Rust solver**. Confidence in this NEGATIVE finding is **HIGH**
based on (a) the line-by-line read in §3 below, (b) the prior empirical
verification in `pr_23_cell_divergence_deep_dive.md` that strategies match
when the test-side artifacts are corrected.

**Confidence that the bug IS in the test:** **MEDIUM-HIGH**. The deep-dive
named two specific test bugs (action-axis mismatch + range-slot swap) and
verified empirically that fixing them collapses the divergence. The bisection
report cited the per-action parity check as "still failing" in the full bundle
because the full bundle never applied the test-side action-axis remap (PR 35
Fix B addressed only the player-index inversion, NOT the per-position remap
within facing-bet rows).

---

## 1. Source comparison setup

| Side | File | Range |
|---|---|---|
| Rust | `crates/cfr_core/src/dcfr_vector.rs` | lines 302-468 (`VectorDCFR::traverse`), 207-289 (`compute_strategy`, `compute_avg_strategy`, `discount`), 474-495 (`solve`), 619-656 (`terminal_value_vector`) |
| Brown | `references/code/noambrown_poker_solver/cpp/src/trainer.cpp` | lines 138-240 (`Trainer::traverse`), 72-136 (compute helpers), 343-369 (`Trainer::run`) |

The Rust file documents its provenance: lines 11-23 explicitly cite
`trainer.cpp:138-209` as the load-bearing reference, and the in-file comments
at 357, 380-381, 430-437, 453 cite specific Brown line ranges per-update.

PR 34's off-by-one fix is fully integrated in `main` and visible at
`dcfr_vector.rs:341-371` (the renamed `player_hands` usage). The
diff against the PR 34 worktree confirms only cosmetic differences (rename
of `_opp_player`/`_opp_hands` to `opp_player`/`opp_hands` and addition of a
`debug_assert!` at line 663). The PR 34 fix itself (the `opp_hands` →
`player_hands` swap) is in `main`.

---

## 2. Per-section diff classification

### 2.1 Terminal value computation

Brown `trainer.cpp:147-159`:
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
        evaluator_.showdown_values(update_player, reach_opp, pot, contrib, ...);
    }
    return frame.values.data();
}
```

Rust `dcfr_vector.rs:314-323`:
```rust
FlatNode::Fold { .. } | FlatNode::Showdown { .. } => {
    let opp_player = 1 - update_player;
    terminal_value_vector(node, eval_ctx, update_player, opp_player, reach_opp)
}
```

with `terminal_value_vector` (lines 619-656) doing:
```rust
for hp in 0..update_hands {
    let hole_p = ctx.hole[update_player][hp];
    let mut total = 0.0_f64;
    for ho in 0..opp_hands {
        let hole_o = ctx.hole[opp_player][ho];
        // blocker check ...
        let combo = if update_player == 0 { [hole_p, hole_o] } else { [hole_o, hole_p] };
        let utility = terminal_utility(node, combo, update_player);
        total += reach_opp[ho] * utility;
    }
    out[hp] = total;
}
```

**Classification: SUBTLE-BUT-CORRECT.**

Brown calls into `VectorEvaluator::fold_values` / `showdown_values` which
precompute per-(hp, ho) utility tables and dot-product them with `reach_opp`.
Rust does the same dot-product inline with a blocker check at the leaf. Both
compute `value[hp] = Σ_ho reach_opp[ho] * utility(hp, ho)`. The blocker
filter is structurally identical (Brown bakes it into the precomputed
showdown-values via masks; Rust does it via an `if hole_p[0] == hole_o[0]
|| ...` continue). Output values are equivalent.

The Brown vs Rust base-pot accounting difference (Brown uses `pot - contrib`,
Rust's `terminal_utility` uses `±c_loser`) is a per-leaf CONSTANT, so it
contributes the same constant to every action's child value and cancels
exactly when forming `action_value - node_value` in the regret update.
Confirmed in `pr_23_cell_divergence_deep_dive.md §4`.

### 2.2 Opponent-node branch

Brown `trainer.cpp:166-181`:
```cpp
if (player != update_player) {
    compute_strategy(info_const, frame.strategy.data());
    std::fill(frame.values.begin(), frame.values.begin() + update_hands, 0.0);
    int opp_hands = info_const.hand_count;
    for (int a = 0; a < action_count; ++a) {
        for (int h = 0; h < opp_hands; ++h) {
            frame.next_reach[h] = reach_opp[h] * frame.strategy[h * action_count + a];
        }
        const double *child_values = traverse(node.next[a], update_player, reach_p,
                                              frame.next_reach.data(), depth + 1);
        for (int h = 0; h < update_hands; ++h) {
            frame.values[h] += child_values[h];
        }
    }
    return frame.values.data();
}
```

Rust `dcfr_vector.rs:354-378`:
```rust
if player != update_player {
    let mut values = vec![0.0_f64; update_hands];
    let mut next_reach = vec![0.0_f64; opp_hands];
    for (a, &child_idx) in children.iter().enumerate() {
        for h in 0..opp_hands {
            next_reach[h] = reach_opp[h] * strategy[h * action_count + a];
        }
        let child_values = self.traverse(tree, eval_ctx, child_idx, update_player,
                                         reach_p, &next_reach);
        for h in 0..update_hands {
            values[h] += child_values[h];
        }
    }
    return values;
}
```

**Classification: TRIVIAL (post-PR-34).**

PR 34's fix already corrected `opp_hands` to mean `info.hand_count` (= the
opponent player's hand count, since at opp nodes `player = opp = 1 -
update_player`). Both implementations now compute the same per-action
opponent-reach update and recurse with the SAME `reach_p` (= update_player's
reach, untouched) and the modified `next_reach` (= opponent's reach scaled
by opp's strategy at this node). Identical behavior.

### 2.3 Own-player branch — strategy compute + discount

Brown `trainer.cpp:184-188`:
```cpp
InfoSet &info = infosets_[node_id];
if (algo_ == Algorithm::DCFR) {
    apply_dcfr_discount(info, dcfr_pos_scale_, dcfr_neg_scale_, dcfr_strat_scale_);
}
compute_strategy(info, frame.strategy.data());
```

Rust `dcfr_vector.rs:384-398`:
```rust
{
    let info = self.infosets[node_idx].as_mut().expect(...);
    Self::discount(info, self.iteration, self.alpha, self.beta, self.gamma);
}
{
    let info = self.infosets[node_idx].as_ref().expect(...);
    Self::compute_strategy(info, &mut strategy);
}
```

**Classification: SUBTLE-BUT-CORRECT.**

Brown applies its DCFR discount factor once per iteration (Brown's `run`
sets `dcfr_pos_scale_` / `dcfr_neg_scale_` / `dcfr_strat_scale_` ONCE per
outer iteration based on `t`, then `traverse` discounts each infoset once
when it visits it). Rust uses lazy catch-up: `VectorDCFR::discount` reads
`info.last_discount_iter` and applies the per-iter formula for each missed
iteration since the last visit (`dcfr_vector.rs:267-289`). When every
infoset IS visited every iteration (the production case — both player
traversals walk the full tree), Rust's catch-up runs exactly one
discount step per iter — same as Brown.

The lazy form is strictly more general (handles infosets that aren't
visited every iter, which is the v1.5.1 bucketing case), but for v1.5.0
with full traversal it's mathematically equivalent. The formula at lines
271-276 (`pos_scale = t^α / (t^α + 1)`, etc.) is byte-for-byte identical
to Brown's at `trainer.cpp:354-361`.

### 2.4 Own-player branch — action_values gather

Brown `trainer.cpp:191-198`:
```cpp
double *action_values = frame.action_values.data();
for (int a = 0; a < action_count; ++a) {
    for (int h = 0; h < update_hands; ++h) {
        frame.next_reach[h] = reach_p[h] * frame.strategy[h * action_count + a];
    }
    const double *child_values = traverse(node.next[a], update_player,
                                          frame.next_reach.data(), reach_opp,
                                          depth + 1);
    std::copy(child_values, child_values + update_hands, action_values + a * update_hands);
}
```

Rust `dcfr_vector.rs:400-417`:
```rust
let mut action_values = vec![0.0_f64; action_count * update_hands];
let mut next_reach = vec![0.0_f64; player_hands];
for (a, &child_idx) in children.iter().enumerate() {
    for h in 0..player_hands {
        next_reach[h] = reach_p[h] * strategy[h * action_count + a];
    }
    let child_values = self.traverse(tree, eval_ctx, child_idx, update_player,
                                     &next_reach, reach_opp);
    let dst = a * update_hands;
    action_values[dst..dst + update_hands].copy_from_slice(&child_values);
}
```

**Classification: TRIVIAL.**

At own-player nodes `player == update_player`, so `player_hands ==
update_hands == info.hand_count`. The two implementations differ only in
the iteration variable name. The recursive call passes the modified
`next_reach` as `reach_p` and unchanged `reach_opp` (both correct — opp's
reach doesn't change at our own nodes, our own reach does). Identical.

### 2.5 Own-player branch — node value

Brown `trainer.cpp:200-208`:
```cpp
double *node_values = frame.values.data();
for (int h = 0; h < update_hands; ++h) {
    double value = 0.0;
    int offset = h * action_count;
    for (int a = 0; a < action_count; ++a) {
        value += frame.strategy[offset + a] * action_values[a * update_hands + h];
    }
    node_values[h] = value;
}
```

Rust `dcfr_vector.rs:420-428`:
```rust
let mut node_values = vec![0.0_f64; update_hands];
for h in 0..update_hands {
    let mut value = 0.0_f64;
    let s_offset = h * action_count;
    for a in 0..action_count {
        value += strategy[s_offset + a] * action_values[a * update_hands + h];
    }
    node_values[h] = value;
}
```

**Classification: TRIVIAL.** Byte-for-byte identical.

### 2.6 Own-player branch — regret update (CRITICAL — H1's territory)

Brown `trainer.cpp:210-224`:
```cpp
CFRScalar *regret = info.regret.data();
for (int h = 0; h < update_hands; ++h) {
    int offset = h * action_count;
    double base = node_values[h];
    for (int a = 0; a < action_count; ++a) {
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

Rust `dcfr_vector.rs:440-451`:
```rust
{
    let info = self.infosets[node_idx].as_mut().expect(...);
    for h in 0..update_hands {
        let offset = h * action_count;
        let base = node_values[h];
        for a in 0..action_count {
            let delta = (action_values[a * update_hands + h] - base) * regret_weight;
            info.regret[offset + a] += delta;
        }
    }
    ...
}
```

**Classification: SUBTLE-BUT-CORRECT.**

The two are mathematically identical. Brown branches on `Algorithm::CFR_PLUS`
to clamp negative regrets to zero; Rust does NOT — but Rust is hardcoded
to DCFR semantics (see the constructor signature taking `alpha, beta, gamma`
and not a parameter for the algorithm choice). For DCFR, Brown's else-branch
runs unconditionally, which matches Rust's unconditional regret accumulation.

**Critical point on H1 (opp_reach in regret update):** Brown's regret
update does NOT multiply by `opp_reach` here. The opp_reach factor is
already baked into `action_values` via the terminal-leaf return path
(`terminal_value_vector` summed over `opp_player` hands weighted by
`reach_opp[ho]`). This is documented in `dcfr_vector.rs:430-437`:

> Brown's update is `regret[h,a] += (action_value[a,h] - node_value[h])`
> (`trainer.cpp:211-224`, MIT) — note the cf-utility is already
> opp-reach-weighted by the terminal-leaf return path, so no extra
> opp_reach multiplier here. This is the key difference vs the scalar
> `dcfr.rs` path, which carries reach separately and multiplies at
> the leaf.

So H1 ("opp_reach missing or wrong-signed in the regret accumulation") is
**not the bug**. Both engines correctly fold opp_reach into action_values
at the terminal-leaf return, then form the regret delta from raw value
differences. If H1 were the bug, BOTH engines would have it.

### 2.7 Own-player branch — strategy_sum update (H3's territory)

Brown `trainer.cpp:226-237`:
```cpp
CFRScalar *strategy_sum = info.strategy_sum.data();
for (int h = 0; h < update_hands; ++h) {
    double weight = reach_p[h] * avg_weight_;
    if (weight == 0.0) continue;
    int offset = h * action_count;
    for (int a = 0; a < action_count; ++a) {
        strategy_sum[offset + a] = static_cast<CFRScalar>(
            static_cast<double>(strategy_sum[offset + a]) + weight * frame.strategy[offset + a]);
    }
}
```

Rust `dcfr_vector.rs:454-463`:
```rust
for h in 0..update_hands {
    let weight = reach_p[h] * avg_weight;
    if weight == 0.0 { continue; }
    let offset = h * action_count;
    for a in 0..action_count {
        info.strategy_sum[offset + a] += weight * strategy[offset + a];
    }
}
```

**Classification: TRIVIAL.** Byte-for-byte identical.

H3 ("strategy_sum biased over-fold") would require the increment formula
or the weight to diverge between the two — they don't.

### 2.8 Reach initialization (scale-only divergence)

Brown `trainer.cpp:367`:
```cpp
traverse(tree_.root, player, hand_weights_ptr_[player],
                              hand_weights_ptr_[1 - player], 0);
```

where `hand_weights_ptr_[p]` points to `game.hand_weights[p]` which is
normalized to sum to 1.0 in `river_game.cpp:204-209` (per
`docs/v1_5_0_per_action_divergence_diagnosis.md §4`).

Rust `dcfr_vector.rs:486-487`:
```rust
let reach_p0: Vec<f64> = vec![1.0; eval_ctx.hand_count[0]];
let reach_p1: Vec<f64> = vec![1.0; eval_ctx.hand_count[1]];
```

**Classification: SUBTLE-BUT-CORRECT (scale-only).**

Brown sums to 1.0 (e.g. 1/55 per hand on a 55-hand range). Rust sums to
N (e.g. 1.0 per hand → 55 total). All regrets, strategy_sums, and
action-values scale uniformly by N. Regret-matching (positive normalization)
and DCFR discount (multiplicative per-iter) are both scale-invariant.
**Strategies are identical** under this scale change.

If the test is comparing strategies (not raw regret values or exploitability),
this difference cannot account for the divergence.

### 2.9 Iteration loop

Brown `trainer.cpp:343-369`:
```cpp
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
    ...
    for (int player = 0; player < 2; ++player) {
        traverse(tree_.root, player, hand_weights_ptr_[player],
                                      hand_weights_ptr_[1 - player], 0);
    }
}
```

Rust `dcfr_vector.rs:488-494`:
```rust
for _ in 0..iterations {
    self.iteration += 1;
    self.traverse(tree, eval_ctx, 0, 0, &reach_p0, &reach_p1);
    self.traverse(tree, eval_ctx, 0, 1, &reach_p1, &reach_p0);
}
```

**Classification: TRIVIAL.** Player update alternation is identical;
discount formulas are identical (in Rust they live inside `discount` —
which is called from inside `traverse`'s own-player branch, not at the
top of the iteration loop — but the math evaluates to the same per-iter
scale).

### 2.10 Action enumeration (H4's territory)

Rust `crates/cfr_core/src/hunl.rs:1105-1146` (from prior diagnoses):
```rust
if facing_bet {
    actions.push(ACTION_FOLD);   // 0
    actions.push(ACTION_CALL);   // 2
} else {
    actions.push(ACTION_CHECK);  // 1
}
let cap_reached = ctx.street_num_raises >= cap;
if !cap_reached { /* raises */ }
if ctx.include_all_in /* && !cap_reached after PR 35 */ {
    actions.push(ACTION_ALL_IN); // 13
}
actions.sort_unstable();
```

Brown `river_game.cpp:74-105` (per prior diagnoses):
```cpp
actions.push_back({'c', to_call});  // call FIRST
actions.push_back({'f', 0});         // fold SECOND
if (state.raises >= max_raises) return actions;
// then raises, then all-in
```

**Classification: SUSPECT at engine level, but only via the test-comparison
layer.**

Each engine is internally consistent: Rust's `VectorInfosetData::regret`
and `strategy_sum` are laid out per the sorted-by-ID column order; Brown's
are laid out per the push-order. The strategies emitted by each engine
are CORRECT for that engine's own column convention.

The deep-cap facing-bet issue surfaces because:
1. The acceptance test reads Brown's `actions = (c, f, raises…)` as the
   source-of-truth ordering.
2. The test indexes Rust's strategy row by the SAME positional index.
3. At facing-bet, Rust's column 0 = FOLD (Brown's column 1) and Rust's
   column 1 = CALL (Brown's column 0).
4. PR 35 Fix C tried to address a parallel concern (ALL_IN-at-cap) but
   did NOT fix the per-position remap; it also introduced a separate
   Python-Rust parity break.

This is documented in `docs/pr_23_cell_divergence_deep_dive.md §1` and
`docs/v1_5_0_per_action_divergence_diagnosis.md §2`. The fix is a test-
side action-axis permutation (Brown's `actions[0]='c'` ↔ Rust col 1,
Brown's `actions[1]='f'` ↔ Rust col 0, raises preserved positionally).

This is **not a `dcfr_vector.rs` bug**, but it manifests as a measured
divergence at facing-bet rows specifically, which is exactly the pattern
the bisection report observed.

### 2.11 Other subtleties checked and dismissed

| Check | Result |
|---|---|
| Sign of regret delta — same direction (action - base) in both | ✓ MATCH |
| Update only `update_player`'s infoset (skip for opp nodes) | ✓ MATCH (only own-player branch updates `info`) |
| Discount applied BEFORE compute_strategy at own-player node | ✓ MATCH (Brown: lines 185-188; Rust: lines 384-398) |
| Per-iter discount step exactly once per infoset visit | ✓ MATCH (Brown's eager / Rust's lazy-catch-up converge for full traversal) |
| `info.regret` indexing `[h * action_count + a]` | ✓ MATCH (both row-major) |
| `info.strategy_sum` indexing `[h * action_count + a]` | ✓ MATCH (both row-major) |
| Strategy-sum guarded by `weight == 0` | ✓ MATCH |
| Chance node handling — sum prob-weighted child values | ✓ MATCH (Rust `FlatNode::Chance` at lines 324-337) |
| Compute-strategy after discount | ✓ MATCH |
| Terminal leaf returns opp-reach-weighted value | ✓ MATCH (per §2.1 above) |

---

## 3. Hypothesis ranking with evidence

### H1: Regret-update opp_reach missing / wrong-signed — **REJECTED**

Brown does NOT multiply by opp_reach in the regret accumulation step. The
opp_reach factor is already baked into `action_values` (and `node_values =
Σ_a strategy * action_values`) via the terminal-leaf return path. Rust
mirrors this exactly. Both implementations form `regret_delta = action_value
- node_value` from already-opp-reach-weighted quantities. There is no
missing factor and no sign error.

If H1 were the bug, the divergence pattern would be uniform across all
nodes (because all node values share the opp_reach factor in the same
way). The observed pattern is concentrated at deep-cap facing-bet — which
fits the action-axis test artifact better than a uniform algorithmic bug.

### H2: opp-reach threading wrong at deep-cap — **REJECTED**

PR 34 already fixed the asymmetric-range bug in the opponent-node branch
(`opp_hands` → `player_hands` for the buffer that holds `update_player`'s
opponent's reach). The deep-cap subtree uses the same code path as
shallow-cap subtrees; there is no special-case branching at the cap.

If H2 were the bug, the symptom would be either a panic (as it was
pre-PR-34) or a numerical NaN/garbage at deep cap. The observed symptom
is a clean, finite over-fold/under-call probability that's a different
member of the Nash polytope — consistent with a test-side action-position
mismatch.

### H3: Strategy_sum averaging biased — **REJECTED**

The strategy_sum update is byte-for-byte identical between Brown and
Rust (per §2.7 above). If Rust were over-folding due to strategy_sum
bias, the entire strategy distribution (not just facing-bet rows) would
be off — but the deep-dive verified the strategies match on other rows
once the action-axis remap is applied.

### H4: Action enumeration at deep-cap facing-bet — **LOW (engine-level)**, **HIGH (test-level)**

The action enumeration ordering differs between Rust (sort by ID) and
Brown (push order). This is internally consistent within each engine.
The issue surfaces only in the test, which compares column-by-column
without remapping.

Within `dcfr_vector.rs` itself, action enumeration is delegated to
`hunl.rs::enumerate_legal_actions` and the betting-tree builder; the
DCFR loop doesn't care about the semantic action labels, only about
the column index. Each engine's regret/strategy/strategy_sum is
correctly laid out for its own column convention.

The deep-cap facing-bet rows are where the action-axis ordering DIFFERS
MOST between the engines (5 actions at facing-bet vs 4 at no-bet vs 2
at cap). So the column-position mismatch produces the largest absolute
divergence at exactly the rows the bisection report flagged: deep-cap
facing-bet high-stakes.

### H5 (NEW): No algorithmic bug; reported divergence is test-side — **CONFIRMED**

Supported by:
- Line-by-line read in §2 above: every load-bearing update is structurally
  faithful to Brown.
- Independent empirical verification in `docs/pr_23_cell_divergence_deep_dive.md`:
  re-running Brown with the range slots swapped + remapping Rust's action
  columns produces strategies that match within tolerance on every cell
  the bisection flagged.
- The "over-fold 3× / under-call ~half" pattern is exactly the signature of
  a positional comparison artifact: at facing-bet, Brown's `c@col0` (≈0)
  vs Rust's `FOLD@col0` (≈1) reads as "Rust over-folds"; Brown's `f@col1`
  (≈1) vs Rust's `CALL@col1` (≈0) reads as "Rust under-calls".

---

## 4. Specific file:line suspects

If the conclusion is "no `dcfr_vector.rs` bug", the file:line suspects are
TEST-side, already documented in prior triages:

### Primary (test renderer column mismatch)

`tests/test_v1_5_brown_apples_to_apples.py:530-556` — per-action comparison
loop indexes `rust_row[a_idx]` by Brown's positional `a_idx` without
applying the action-axis permutation. At facing-bet, Brown's `actions[0]='c'`
must map to Rust's column 1 (CALL), and Brown's `actions[1]='f'` must map
to Rust's column 0 (FOLD).

### Secondary (engine action ordering)

`crates/cfr_core/src/hunl.rs:1105-1138` — `enumerate_legal_actions` builds
actions in `[FOLD, CALL, raises…, ALL_IN]` order after a sort by action
ID. Brown's `river_game.cpp:74-105` builds them in `[c, f, raises…]`
push-order. Both are internally consistent; the divergence is at the
column-axis comparison layer in the test.

### Tertiary (range slot assignment, separately tracked)

`tests/test_v1_5_brown_apples_to_apples.py:457-481` — `p0_holes` /
`p1_holes` are assigned from `spot.ranges[0]` / `spot.ranges[1]` per
spot-author intent, but the engines have opposite first-actor conventions
(Brown's P0 acts first on river; our P1 acts first on river). Without
swapping the range assignment to match, the engines solve different
games. This was partially addressed by PR 35 Fix B (player-index
inversion in the per-action comparison loop) but NOT in the range
input to Rust.

**No lines in `dcfr_vector.rs` are suspect.** PR 34's fix at lines
341-371 is correct and load-bearing; the rest of the file is structurally
faithful to Brown.

---

## 5. Recommended fix sketch

The fix is **test-side**, not solver-side. Three independent corrections,
to be applied together (this is essentially PR 35 + an additional column-
remap that PR 35 missed):

### Fix 1 — Action-axis column remap in the test

In `tests/test_v1_5_brown_apples_to_apples.py`, replace the positional
loop in the per-action comparison with a semantic permutation:

```python
def _brown_to_rust_action_perm(brown_actions: tuple[str, ...]) -> list[int]:
    """Map Brown's column index → Rust's column index for the same semantic action."""
    facing = "f" in brown_actions
    if not facing:
        return list(range(len(brown_actions)))  # both start with check, identity
    # Facing bet: Brown [c, f, raises…] → Rust [f, c, raises…, A]
    return [1, 0] + list(range(2, len(brown_actions)))

# Inside the per-cell loop:
perm = _brown_to_rust_action_perm(actions)
for a_idx in range(n_actions):
    brown_p = float(brown_row[a_idx])
    rust_p = float(rust_row[perm[a_idx]])
    if abs(brown_p - rust_p) >= PER_ACTION_TOL: diffs.append(...)
```

LOC: ~15 lines. Risk: low. Verified empirically by deep-dive to collapse
the 22-42pp cells to within tolerance.

### Fix 2 — Range-to-player-slot wiring

Either (a) swap the Rust call site to put the opener-leaning range in
Rust's P1 (= our first actor), or (b) re-invoke Brown on a `replace(spot,
ranges=(ranges[1], ranges[0]))` view. (a) is more direct:

```python
# tests/test_v1_5_brown_apples_to_apples.py:467-481 (current):
p0_holes = _spot_hand_ids(spot, 0)
p1_holes = _spot_hand_ids(spot, 1)

# Replace with:
p0_holes = _spot_hand_ids(spot, 1)  # Rust P0 = defender ← Brown's player[1]
p1_holes = _spot_hand_ids(spot, 0)  # Rust P1 = opener  ← Brown's player[0]
```

The hand-string lookup table needs corresponding update so per-hand
emissions are matched against the correct player slot.

LOC: ~5 lines. Risk: low.

### Fix 3 — Hand-string suit-order normalization

Brown uses suit string `"cdhs"`; our `card.py` uses `"shdc"`. For most
combos this produces the same canonical string, but for K-paired and
other suit-order-sensitive hands, Brown's `KhKs` may be our `KsKh`. A
small lookup table can be built from each side's `card_to_int` ordering.

LOC: ~20 lines. Risk: low.

Together these three fixes are what PR 35 was *aiming* at; PR 35 only
landed Fix 1 partially (Fix B = player-index inversion, which is a
related but distinct issue) and Fix 2 partially (Fix A = canonicalization
renderer). The Fix 1 column-remap was missed entirely. Re-doing PR 35
correctly + dropping PR 35 Fix C (which broke Python-Rust parity) is
the right v1.6.x sequence.

### What NOT to do

**Do not modify `dcfr_vector.rs` to "fix" the divergence.** The Rust
solver is a faithful port of Brown's reference. Modifying it to match
an incorrectly-encoded test would be removing a correct solver to
satisfy an incorrect test.

---

## 6. Confidence assessment

**Confidence that this triage correctly localizes the bug:** **HIGH**

Evidence:
1. Line-by-line read (§2) shows zero structural divergence in
   `VectorDCFR::traverse` vs `Trainer::traverse`.
2. The single intentional difference (reach scale) is documented
   as scale-only and verified to not affect strategies.
3. The deep-dive (`pr_23_cell_divergence_deep_dive.md`) already
   produced an empirical verification: with the test-side action-axis
   remap and range-swap applied, strategies match within tolerance
   on every cell flagged by the bisection.
4. The per-action divergence diagnosis (`v1_5_0_per_action_divergence_diagnosis.md`)
   independently arrived at the same conclusion via a different
   verification path.

**Confidence that the bug is `dcfr_vector.rs`:** **LOW (10-15%)**

The only residual uncertainty is the deep-dive's §4 statement:

> after applying BOTH the action-axis remap and the range-wiring
> correction, 697 cells still differ by ≥5e-3 (vs 0 expected). The top
> divergences are mostly between `c@pos0` (Brown's call) and `r5000@pos2`
> (Rust's call → raise drift) ... These are plausibly Nash mixed-strategy
> non-uniqueness ... but I did not run a best-response cross-check to
> confirm.

This residual is one of (a) Nash polytope non-uniqueness at indifference
cells, (b) iteration-count convergence drift between the two engines at
identical alpha/beta/gamma, or (c) a remaining sub-1pp algorithmic delta
that doesn't manifest at the cells the bisection flagged. None of these
match the deep-cap over-fold 3× / under-call ~½ pattern, so the bisection's
specific claim is well-explained by the test artifact alone.

**Honest framing:** if a follow-up validation run after applying Fixes 1+2+3
above STILL shows 22-42pp divergence at deep-cap facing-bet rows, then a
SECOND triage agent should look for an actual `dcfr_vector.rs` bug. Until
then, the evidence strongly points to test-side artifacts.

---

## 7. Recommended next step for orchestrator

**Spawn a focused-fix implementer** to apply the three test-side fixes
(action-axis remap + range-slot swap + suit-order normalization), then
RE-RUN the acceptance test. If the test passes within tolerance, the
v1.6.1 acceptance gate is unblocked WITHOUT touching the Rust solver.

If after these fixes the per-action divergence persists at 22-42pp on
deep-cap rows, escalate to a continued-investigation agent specifically
on the residual cells. Hypotheses to test in that follow-up:
- iteration-count convergence (does 5000 iter reduce the gap vs 2000?)
- Nash polytope non-uniqueness (does a best-response cross-check (Rust
  strategy through Brown's exploitability + vice versa) show both at
  near-zero exploitability against each other?)
- chance-node weighting at multi-card runouts (only relevant if not
  river — out of scope for `dry_K72_rainbow`)

**Do not spawn a wider rewrite of `dcfr_vector.rs`.** The structural
read in §2 above gives high confidence the solver is correct as-is.
A wider rewrite would risk regressing the (passing) tiny-river RvR
smoke test (`vector_solver_runs_minimum_iters`) and the (passing)
Rust↔Python differential test in `test_range_vs_range_rust_diff.py`,
both of which already verify the algorithm structurally.

---

## 8. Source-of-truth pointers (absolute paths)

- Rust solver: `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/dcfr_vector.rs`
- Brown reference: `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/trainer.cpp`
- Brown header: `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/trainer.h`
- PR 34 worktree: `/Users/ashen/Desktop/poker_solver_worktrees/pr-23-p0-off-by-one/`
- Prior triage (cells): `/Users/ashen/Desktop/poker_solver/docs/pr_23_cell_divergence_deep_dive.md`
- Prior triage (per-action): `/Users/ashen/Desktop/poker_solver/docs/v1_5_0_per_action_divergence_diagnosis.md`
- Bisection report: `/Users/ashen/Desktop/poker_solver/docs/v1_6_1_bundle_bisection_diagnosis.md`
- Acceptance test: `/Users/ashen/Desktop/poker_solver/tests/test_v1_5_brown_apples_to_apples.py`
- Action enumeration: `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/hunl.rs` (lines 1105-1146)
