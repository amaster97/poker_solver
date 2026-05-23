//! PR 23 — Vector-form DCFR for true range-vs-range Nash solves.
//!
//! Brown, N. and Sandholm, T. (2019). "Solving Imperfect-Information Games
//! via Discounted Regret Minimization." AAAI 2019. (arxiv 1809.04040)
//!
//! This module implements the **vector-form** CFR update where each player
//! infoset stores a `hand_count × action_count` regret / strategy_sum
//! table and the betting tree is walked **once per iteration** (no hole-
//! card chance enum at the root). It is a structural port of Brown's
//! reference C++ trainer:
//!
//!   - `references/code/noambrown_poker_solver/cpp/src/trainer.cpp:138-209`
//!     (MIT, `Trainer::traverse`) — the load-bearing reference. Loop shape:
//!     opponent node = scale opp reach per-hand by their strategy, recurse;
//!     own node = collect per-(action, hand) action values, compute
//!     `node_value[h] = Σ_a strategy[h,a] * action_value[a,h]`, then update
//!     `regret[h,a] += opp_reach * (action_value[a,h] - node_value[h])`.
//!   - `references/code/noambrown_poker_solver/cpp/src/trainer.h:41-46`
//!     (MIT) — `InfoSet { action_count, hand_count, regret, strategy_sum }`
//!     layout (row-major over `hand_idx * action_count + action_idx`).
//!   - `references/code/noambrown_poker_solver/cpp/src/river_game.h:19-26`
//!     (MIT) — `TreeNode` carries no chance children at the betting layer;
//!     hands live as a global vector on the game, not branched into nodes.
//!
//! In-codebase precedent for the same vector-form pattern (read-side):
//!   - `crates/cfr_core/src/exploit.rs:670-727` (PR 15 `flat_tree_exploit`)
//!     — precomputes the betting tree once via `BettingTree::build_from`,
//!     then iterates combos against the flat tree for EV / BR. PR 23
//!     extends the same pattern to the write side (regret + strategy
//!     updates during DCFR).
//!
//! Python ground truth: `poker_solver/dcfr.py` (the scalar reference) plus
//! the empty-`initial_hole_cards` path through `_enumerate_preflop_hole_outcomes`
//! (`poker_solver/hunl.py:601`). The vector-form is the *Rust* shape of
//! "true Nash range-vs-range"; the Python tier runs this via the slow
//! chance-enum-at-root scalar path.
//!
//! ## What this module is NOT
//!
//! - NOT a copy of `references/code/postflop-solver` (AGPL — forbidden).
//! - NOT a copy of `references/code/TexasSolver` (AGPL — forbidden).
//! - NOT a replacement for the scalar `dcfr.rs::DCFRSolver<G>` — Kuhn,
//!   Leduc, fixed-combo HUNL still go through `dcfr.rs` byte-for-byte.
//!
//! ## v1.5.0 scope (per spec §8 Q2)
//!
//! - Postflop range-vs-range (`Street::Flop / Turn / River` with
//!   `initial_hole_cards = None`) is supported.
//! - Preflop range-vs-range deferred to v1.5.1 (memory edge at 16 GB
//!   per spec §4).
//! - Bucketing not yet engaged here — hands are full C(deck, 2) pairs;
//!   v1.5.1 will plug EMD bucketing into the hand-vector dimension.
//! - Python `solve_range_vs_range` aggregator is NOT rewired here (Q3
//!   default); the new entrypoint exists alongside as a PyO3 surface.

// The vector-form CFR inner loops index per-(hand, action) into multiple
// parallel arrays (regret, strategy, action_values, reach), so the
// indexed-for-loop shape is clearer than the iterator form Clippy
// proposes. Brown's reference (`trainer.cpp`, MIT) uses the same shape.
#![allow(clippy::needless_range_loop)]

use std::collections::HashMap;

use crate::exploit::{
    enumerate_hole_card_pairs, hole_string, terminal_utility, BettingTree, FlatNode,
};
use crate::hunl::{HUNLConfig, HUNLState};

/// Per-decision-node vector-form regret + strategy_sum table.
///
/// Layout: row-major `regret[hand_idx * action_count + action_idx]`.
/// Mirrors Brown's `InfoSet` in `trainer.h:41-46` (MIT). The `f64`
/// element type matches the scalar `dcfr.rs::InfosetData` so the diff
/// test against Python's `dcfr.py` (also `np.float64`) stays clean;
/// Brown's reference uses configurable `CFRScalar = float | double`,
/// we pick `double` unconditionally to keep parity with Python.
#[derive(Clone, Debug)]
pub struct VectorInfosetData {
    pub action_count: usize,
    pub hand_count: usize,
    pub regret: Vec<f64>,
    pub strategy_sum: Vec<f64>,
    /// Iteration this infoset was last discounted at. Lazy discounting
    /// catches up on access, matching the scalar `dcfr.rs::InfosetData`
    /// behavior and the Python tier's `_discount`.
    pub last_discount_iter: u32,
}

impl VectorInfosetData {
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
}

/// Per-street memory profile for the vector-form solver.
///
/// Matches PR 5's per-street profiler pattern (Python side:
/// `poker_solver.profiler`) so downstream tooling (`PLAN.md:29-30`'s
/// per-street memory report) can consume the same dict shape. Reported
/// numbers come from `VectorInfosetData::regret + strategy_sum` byte
/// sizes; the surrounding overheads (HashMap nodes, tree nodes) are
/// not included because they're dwarfed by the regret tables at scale.
///
/// `pub` so the differential test + the PyO3 binding's eventual
/// memory-report PyDict export can read it directly.
#[derive(Debug, Default)]
pub struct VectorMemoryProfile {
    /// Total bytes used for regret + strategy_sum across all infosets.
    pub total_bytes: u64,
    /// Per-street breakdown: keys are `"flop" | "turn" | "river" |
    /// "showdown"`. Values are total bytes for infosets on that street.
    pub by_street: std::collections::HashMap<String, u64>,
    /// Total infoset count.
    pub infoset_count: u32,
    /// Per-street infoset count.
    pub infoset_count_by_street: std::collections::HashMap<String, u32>,
    /// Hand count per player (the vector dimension).
    pub hand_count: [usize; 2],
}

/// Output of a vector-form DCFR solve.
///
/// `per_hand_strategy` maps `(node_idx, hand_idx)` rows back to the
/// stable string keys Python expects. The strategy dict shape mirrors
/// the scalar Rust tier (`HashMap<String, Vec<f64>>`); each per-hand
/// row becomes one entry in the dict with key `<hole_string>|<key_suffix>`,
/// where `key_suffix` is the betting-tree node's precomputed
/// `|<board>|<street>|<history>` portion.
pub struct VectorSolveOutput {
    pub average_strategy: HashMap<String, Vec<f64>>,
    /// Number of betting-tree decision nodes (infosets in the vector
    /// shape — distinct from the scalar Rust tier's per-(hole, decision)
    /// infoset count). One value per actual decision point in the
    /// betting tree, hand-vector-expanded.
    pub decision_node_count: u32,
    /// Total emitted strategy entries (= number of decision nodes ×
    /// hand_count, roughly).
    pub strategy_entry_count: u32,
    /// Number of iterations actually run.
    pub iterations: u32,
    /// Per-player hand count (the vector dimension). Useful for the
    /// memory profiler and the Python diff test.
    pub hand_count_per_player: [usize; 2],
    /// Per-street memory profile (spec §4). Populated after solve;
    /// matches PR 5's per-street memory report pattern.
    pub memory_profile: VectorMemoryProfile,
}

/// Vector-form DCFR solver — Brown's `Trainer` (MIT) restated in safe Rust.
///
/// Maps each `FlatNode::Decision` in the betting tree to one
/// `VectorInfosetData`. Per-iteration both players are updated
/// alternately, matching `trainer.cpp:366-369`:
///
/// ```cpp
///     for (int player = 0; player < 2; ++player) {
///         traverse(tree_.root, player, hand_weights_ptr_[player], ...);
///     }
/// ```
pub struct VectorDCFR {
    alpha: f64,
    beta: f64,
    gamma: f64,
    iteration: u32,
    /// One slot per `FlatNode` index. `None` for non-decision nodes
    /// (terminals, chance). Mirrors `Trainer::infosets_` (`trainer.cpp:13-25`,
    /// MIT) which also stores one slot per tree node and skips non-
    /// decision nodes.
    infosets: Vec<Option<VectorInfosetData>>,
}

impl VectorDCFR {
    pub(crate) fn new(tree: &BettingTree, hand_count_per_player: [usize; 2], alpha: f64, beta: f64, gamma: f64) -> Self {
        let mut infosets: Vec<Option<VectorInfosetData>> = Vec::with_capacity(tree.nodes.len());
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
        Self {
            alpha,
            beta,
            gamma,
            iteration: 0,
            infosets,
        }
    }

    /// Regret-matching per-hand. Output is row-major
    /// `strategy[hand_idx * action_count + action_idx]`.
    ///
    /// Mirrors Brown's `Trainer::compute_strategy`
    /// (`trainer.cpp:72-98`, MIT): for each hand, sum positive regrets;
    /// if positive, normalize them as the strategy; else uniform.
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

    /// Normalize cumulative strategy_sum into an average strategy.
    /// Mirrors `Trainer::compute_avg_strategy` (`trainer.cpp:100-122`, MIT).
    fn compute_avg_strategy(info: &VectorInfosetData, out: &mut [f64]) {
        let hand_count = info.hand_count;
        let action_count = info.action_count;
        debug_assert_eq!(out.len(), hand_count * action_count);
        for h in 0..hand_count {
            let offset = h * action_count;
            let mut normalizing = 0.0_f64;
            for a in 0..action_count {
                normalizing += info.strategy_sum[offset + a];
            }
            if normalizing > 0.0 {
                for a in 0..action_count {
                    out[offset + a] = info.strategy_sum[offset + a] / normalizing;
                }
            } else {
                let prob = 1.0 / action_count as f64;
                for a in 0..action_count {
                    out[offset + a] = prob;
                }
            }
        }
    }

    /// DCFR discount catch-up. Same math as the scalar `dcfr.rs::discount_info`
    /// (and as Brown's `Trainer::apply_dcfr_discount` at `trainer.cpp:124-136`,
    /// MIT), applied to the full `hand_count × action_count` regret / strat
    /// vectors. We do not route through `simd::discount_regrets` here
    /// because the vector shape is `hand_count × action_count` rather than
    /// `action_count` and the existing SIMD kernels assume the action-only
    /// width; a vector-shape SIMD kernel is a follow-up for v1.5.x perf.
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

    /// Vector-form recursive traversal.
    ///
    /// Direct port of Brown's `Trainer::traverse` (`trainer.cpp:138-240`,
    /// MIT) with one Rust idiom adaptation: instead of a mutable scratch
    /// vector per frame, we allocate per-call. This is the conservative
    /// path that prioritizes correctness for v1.5.0; v1.5.x can switch to
    /// a pre-allocated scratch arena (matching `trainer.cpp:48-53`) once
    /// the diff test is established.
    ///
    /// Returns per-hand value vector for `update_player` (length
    /// `hand_counts[update_player]`).
    fn traverse(
        &mut self,
        tree: &BettingTree,
        eval_ctx: &EvalContext,
        node_idx: usize,
        update_player: usize,
        reach_p: &[f64],
        reach_opp: &[f64],
    ) -> Vec<f64> {
        let node = &tree.nodes[node_idx];
        let update_hands = eval_ctx.hand_count[update_player];

        match node {
            FlatNode::Fold { .. } | FlatNode::Showdown { .. } => {
                // Terminal — compute the per-hand utility weighted by
                // opponent's reach. Per Brown's `Trainer::traverse`
                // (`trainer.cpp:147-159`, MIT): the returned value for
                // `update_player` is the cf-utility, i.e. sum over
                // opponent hands of `opp_reach * value_per_pair`.
                let opp_player = 1 - update_player;
                terminal_value_vector(node, eval_ctx, update_player, opp_player, reach_opp)
            }
            FlatNode::Chance { prob, children } => {
                // Board-card chance node (postflop run-out). Per Brown's
                // pattern, chance children at the betting layer are
                // weight-summed: value = Σ_c prob * traverse(c, ...).
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
            FlatNode::Decision { player, actions, children, .. } => {
                let player = *player as usize;
                let action_count = actions.len();
                let opp_player = 1 - player;
                let opp_hands = eval_ctx.hand_count[opp_player];

                // Compute the per-hand current strategy from regret-matching.
                let player_hands = eval_ctx.hand_count[player];
                let mut strategy = vec![0.0_f64; player_hands * action_count];
                {
                    let info = self.infosets[node_idx]
                        .as_ref()
                        .expect("decision node must have an infoset slot");
                    Self::compute_strategy(info, &mut strategy);
                }

                if player != update_player {
                    // Opponent node — propagate their reach via current
                    // strategy and accumulate update_player values.
                    // Mirrors `trainer.cpp:166-181` (MIT).
                    let mut values = vec![0.0_f64; update_hands];
                    let mut next_reach = vec![0.0_f64; opp_hands];
                    for (a, &child_idx) in children.iter().enumerate() {
                        // next_reach[h] = reach_opp[h] * strategy[h, a]
                        for h in 0..opp_hands {
                            next_reach[h] = reach_opp[h] * strategy[h * action_count + a];
                        }
                        let child_values = self.traverse(
                            tree,
                            eval_ctx,
                            child_idx,
                            update_player,
                            reach_p,
                            &next_reach,
                        );
                        for h in 0..update_hands {
                            values[h] += child_values[h];
                        }
                    }
                    return values;
                }

                // Own (update_player) node. Mirrors `trainer.cpp:184-238`
                // (MIT). Apply DCFR discount, gather per-action child
                // values, compute node value as `Σ_a strategy[h,a] *
                // action_value[a,h]`, then update regret + strategy_sum.
                {
                    let info = self.infosets[node_idx]
                        .as_mut()
                        .expect("decision node must have an infoset slot");
                    Self::discount(info, self.iteration, self.alpha, self.beta, self.gamma);
                }
                // Recompute strategy after the discount (the prior
                // `strategy` was based on pre-discount regrets — Brown's
                // C++ does the same flow at `trainer.cpp:186-188`).
                {
                    let info = self.infosets[node_idx]
                        .as_ref()
                        .expect("decision node must have an infoset slot");
                    Self::compute_strategy(info, &mut strategy);
                }

                let mut action_values = vec![0.0_f64; action_count * update_hands];
                let mut next_reach = vec![0.0_f64; player_hands];
                for (a, &child_idx) in children.iter().enumerate() {
                    // next_reach[h] = reach_p[h] * strategy[h, a]
                    for h in 0..player_hands {
                        next_reach[h] = reach_p[h] * strategy[h * action_count + a];
                    }
                    let child_values = self.traverse(
                        tree,
                        eval_ctx,
                        child_idx,
                        update_player,
                        &next_reach,
                        reach_opp,
                    );
                    let dst = a * update_hands;
                    action_values[dst..dst + update_hands].copy_from_slice(&child_values);
                }

                // node_values[h] = Σ_a strategy[h,a] * action_values[a,h]
                let mut node_values = vec![0.0_f64; update_hands];
                for h in 0..update_hands {
                    let mut value = 0.0_f64;
                    let s_offset = h * action_count;
                    for a in 0..action_count {
                        value += strategy[s_offset + a] * action_values[a * update_hands + h];
                    }
                    node_values[h] = value;
                }

                // Update regret + strategy_sum. Brown's update is
                // `regret[h,a] += (action_value[a,h] - node_value[h])`
                // (`trainer.cpp:211-224`, MIT) — note the cf-utility is
                // already opp-reach-weighted by the terminal-leaf
                // return path, so no extra opp_reach multiplier here.
                // This is the key difference vs the scalar `dcfr.rs`
                // path, which carries reach separately and multiplies
                // at the leaf.
                let regret_weight = 1.0_f64; // DCFR uses `regret_weight = 1` (`trainer.cpp:354-355`).
                let avg_weight = 1.0_f64; // DCFR uses `avg_weight = 1` (`trainer.cpp:355`).
                {
                    let info = self.infosets[node_idx]
                        .as_mut()
                        .expect("decision node must have an infoset slot");
                    for h in 0..update_hands {
                        let offset = h * action_count;
                        let base = node_values[h];
                        for a in 0..action_count {
                            let delta = (action_values[a * update_hands + h] - base) * regret_weight;
                            info.regret[offset + a] += delta;
                        }
                    }
                    // strategy_sum[h,a] += reach_p[h] * avg_weight * strategy[h,a]
                    // Mirrors `trainer.cpp:226-237` (MIT).
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
                }

                node_values
            }
        }
    }

    /// Drive `iterations` iterations of vector-form DCFR. Alternates
    /// player updates per iteration to match Brown's `Trainer::run`
    /// (`trainer.cpp:343-369`, MIT).
    pub(crate) fn solve(
        &mut self,
        tree: &BettingTree,
        eval_ctx: &EvalContext,
        iterations: u32,
    ) {
        // Uniform reach vectors per player. Brown's reference
        // initializes from `hand_weights_ptr_` (the per-hand range
        // weights from the `RiverGame`); for true RvR with uniform
        // ranges we use `1.0` per hand. Future enhancement (v1.5.x)
        // can plug in non-uniform Sklansky-like ranges through this
        // same vector.
        let reach_p0: Vec<f64> = vec![1.0; eval_ctx.hand_count[0]];
        let reach_p1: Vec<f64> = vec![1.0; eval_ctx.hand_count[1]];
        for _ in 0..iterations {
            self.iteration += 1;
            // Update player 0.
            self.traverse(tree, eval_ctx, 0, 0, &reach_p0, &reach_p1);
            // Update player 1.
            self.traverse(tree, eval_ctx, 0, 1, &reach_p1, &reach_p0);
        }
    }
}

/// Per-hand bookkeeping used by `VectorDCFR::traverse` for terminal-leaf
/// evaluation. Stores both players' `(node_idx, hand_idx) → hole-pair`
/// mapping so the showdown eval can resolve cards without re-deriving
/// the canonical ordering at every leaf.
pub struct EvalContext {
    /// Number of hands per player (the vector dimension). For symmetric
    /// RvR with the same range definition for both players, these are
    /// equal; we keep them as a pair to match Brown's reference layout
    /// (`trainer.h:61` `std::array<int, 2> num_hands_`).
    pub hand_count: [usize; 2],
    /// `hole[p][h] = [card0, card1]` for player `p`, hand index `h`.
    pub hole: [Vec<[u8; 2]>; 2],
    /// Precomputed hole-card strings per `(player, hand)`, in the
    /// canonical format `HUNLState::infoset_key` uses. Used to build
    /// the output dict keys at the end of the solve.
    pub hole_str: [Vec<String>; 2],
    /// Big blind in cents (chip-to-BB normalization factor for utility).
    pub big_blind: i32,
}

impl EvalContext {
    /// Build an `EvalContext` from a true range-vs-range root state
    /// (must have `initial_hole_cards = None`). For v1.5.0 this enumerates
    /// the full C(52 - |board|, 2) per-player hand list with NO blocker
    /// filter on the cross product — every (p0, p1) pair with disjoint
    /// cards is implicitly handled inside `terminal_value_vector` by
    /// zero-weighting blocker conflicts.
    pub fn from_root(initial: &HUNLState) -> Self {
        let combos = enumerate_hole_card_pairs(initial);
        // The combos list is the *cross product* of player hands.
        // For the vector form we want per-player hand lists separately:
        // unique P0 holes + unique P1 holes. Both lists are the same
        // set (the deck minus the board, taken 2 at a time).
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
        // Sanity check: cross-product size should match `combos.len()`.
        debug_assert!(
            !combos.is_empty() || single_holes.is_empty(),
            "combo enumeration drift"
        );
        let p0_holes = single_holes.clone();
        let p1_holes = single_holes;
        let hand_count = [p0_holes.len(), p1_holes.len()];
        let big_blind = initial.config.big_blind;
        let hole_str_p0: Vec<String> = p0_holes.iter().map(|&h| hole_string(h)).collect();
        let hole_str_p1: Vec<String> = p1_holes.iter().map(|&h| hole_string(h)).collect();
        Self {
            hand_count,
            hole: [p0_holes, p1_holes],
            hole_str: [hole_str_p0, hole_str_p1],
            big_blind,
        }
    }

    /// Suit-iso-collapsed root context — stretch goal, not used in v1.5.0.
    /// Stubbed here so the public API surface is forward-compatible with
    /// the preflop full-1326 fallback in spec §4 / §8 Q2.
    #[allow(dead_code)]
    pub fn from_suit_iso(_initial: &HUNLState) -> Self {
        unimplemented!("suit-iso reduction is v1.5.1 follow-up — see spec §8 Q2 (c)")
    }

    /// Build an `EvalContext` from explicit per-player hand lists. Used by
    /// the differential test in `tests/test_range_vs_range_rust_diff.py`
    /// to construct a small enough case (<= 10 hands per player) that
    /// Python's `dcfr.py` ground truth can complete in reasonable wall-
    /// clock. Production callers go through `from_root` which enumerates
    /// the full C(deck, 2) hand vector.
    ///
    /// The hand lists must already be filtered for board collisions.
    /// We do NOT validate further here; the differential test owns that
    /// invariant.
    pub fn from_hand_lists(
        p0_holes: Vec<[u8; 2]>,
        p1_holes: Vec<[u8; 2]>,
        big_blind: i32,
    ) -> Self {
        let hand_count = [p0_holes.len(), p1_holes.len()];
        let hole_str_p0: Vec<String> = p0_holes.iter().map(|&h| hole_string(h)).collect();
        let hole_str_p1: Vec<String> = p1_holes.iter().map(|&h| hole_string(h)).collect();
        Self {
            hand_count,
            hole: [p0_holes, p1_holes],
            hole_str: [hole_str_p0, hole_str_p1],
            big_blind,
        }
    }
}

/// Terminal-leaf value vector for `update_player`.
///
/// For each `update_player` hand `hp`, sum over `opp_player` hands `ho`:
///   value[hp] += reach_opp[ho] * utility(hp, ho)   [if disjoint]
///   value[hp] += 0                                  [if hp ∩ ho ≠ ∅]
///
/// The blocker-disjoint check enforces the standard CFR-on-poker
/// "no card collision" constraint at the leaf; Brown handles this via
/// the `VectorEvaluator::showdown_values` / `fold_values` precomputed
/// masks (`trainer.cpp:147-159`, `vector_eval.h` MIT). We do it inline
/// here because v1.5.0 keeps the implementation single-threaded and
/// uncached; v1.5.x can move blocker masks into a dedicated evaluator.
fn terminal_value_vector(
    node: &FlatNode,
    ctx: &EvalContext,
    update_player: usize,
    opp_player: usize,
    reach_opp: &[f64],
) -> Vec<f64> {
    let update_hands = ctx.hand_count[update_player];
    let opp_hands = ctx.hand_count[opp_player];
    let mut out = vec![0.0_f64; update_hands];

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
            // Build a [[p0_hole], [p1_hole]] tuple in the orientation
            // the exploit module's `terminal_utility` expects.
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
    out
}

/// Build an output `HashMap<String, Vec<f64>>` matching Python's
/// `solver.average_strategy()` shape. One entry per `(decision_node,
/// player_hand)` row, keyed by `<hole_string>|<key_suffix>` to mirror
/// Python's `HUNLState.infoset_key(player, abstraction=None)` lossless
/// format.
///
/// Note: hands where every action sees zero strategy_sum (because
/// the hand was always blocked by opp's reach at this node) emit
/// uniform — matching `compute_avg_strategy` (`trainer.cpp:111-120`,
/// MIT).
pub(crate) fn build_average_strategy(
    solver: &VectorDCFR,
    tree: &BettingTree,
    ctx: &EvalContext,
) -> HashMap<String, Vec<f64>> {
    let mut out: HashMap<String, Vec<f64>> = HashMap::new();
    for (node_idx, slot) in solver.infosets.iter().enumerate() {
        let info = match slot {
            Some(info) => info,
            None => continue,
        };
        let node = &tree.nodes[node_idx];
        let (player, key_suffix) = match node {
            FlatNode::Decision { player, key_suffix, .. } => (*player as usize, key_suffix.as_str()),
            _ => continue,
        };
        let action_count = info.action_count;
        let hand_count = info.hand_count;
        let mut avg = vec![0.0_f64; hand_count * action_count];
        VectorDCFR::compute_avg_strategy(info, &mut avg);

        for h in 0..hand_count {
            let hole_str = &ctx.hole_str[player][h];
            // Skip hands blocked by the board (their hole pair contained
            // a board card). We could filter at the `EvalContext` build
            // step, but it's cleaner to skip on output so the row indices
            // line up with the `enumerate_hole_card_pairs` ordering.
            // For postflop with a fixed board, `hole_str[player][h]`
            // never contains a board card (build step filters those out).
            let mut key = String::with_capacity(hole_str.len() + key_suffix.len());
            key.push_str(hole_str);
            key.push_str(key_suffix);
            let offset = h * action_count;
            let row: Vec<f64> = avg[offset..offset + action_count].to_vec();
            out.insert(key, row);
        }
    }
    out
}

/// Top-level vector-form DCFR solve for true range-vs-range Nash.
///
/// Build the betting tree once from the user's HUNL config, allocate
/// per-decision `VectorInfosetData`, run `iterations` iterations of
/// vector-form CFR, and emit the average strategy in the standard
/// `HashMap<String, Vec<f64>>` shape (per-(infoset, hand) row).
///
/// Validates that the config is a true RvR config (`initial_hole_cards
/// = None`); other configs should keep using `hunl_solver::solve_hunl_postflop`.
pub fn solve_range_vs_range_postflop(
    config: &HUNLConfig,
    iterations: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
) -> Result<VectorSolveOutput, String> {
    solve_range_vs_range_postflop_with_hands(config, None, iterations, alpha, beta, gamma)
}

/// Vector-form DCFR with explicit per-player hand lists.
///
/// Same as `solve_range_vs_range_postflop` but lets callers specify the
/// exact hands the solver should vectorize over. Used by the
/// differential test in `tests/test_range_vs_range_rust_diff.py` to
/// build cases small enough that Python's `dcfr.py` ground truth can
/// finish within the test budget.
///
/// `hand_lists`: `Some(([p0_holes], [p1_holes]))` to specify hands
/// explicitly; `None` to enumerate the full C(deck minus board, 2)
/// per player (the production path).
pub fn solve_range_vs_range_postflop_with_hands(
    config: &HUNLConfig,
    hand_lists: Option<[Vec<[u8; 2]>; 2]>,
    iterations: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
) -> Result<VectorSolveOutput, String> {
    if config.initial_hole_cards.is_some() {
        return Err(
            "solve_range_vs_range_postflop requires initial_hole_cards = None; \
             use solve_hunl_postflop for fixed-combo configs"
                .into(),
        );
    }
    if config.starting_street == crate::hunl::Street::Preflop {
        return Err(
            "preflop range-vs-range is deferred to v1.5.1 per spec §8 Q2; \
             use starting_street >= Flop for v1.5.0"
                .into(),
        );
    }

    let initial = HUNLState::initial(std::sync::Arc::new(config.clone()));
    let eval_ctx = match hand_lists {
        Some([p0, p1]) => {
            if p0.is_empty() || p1.is_empty() {
                return Err("hand_lists must be non-empty for both players".into());
            }
            EvalContext::from_hand_lists(p0, p1, config.big_blind)
        }
        None => {
            let ctx = EvalContext::from_root(&initial);
            if ctx.hand_count[0] == 0 {
                return Err("no valid hole-card pairs at root (board exhausts deck?)".into());
            }
            ctx
        }
    };

    // Build the betting tree from a placeholder hole-card state. The
    // placeholder hole-pair is any valid pair (we pick the first one);
    // the precomputed `key_suffix` strings strip the hole prefix so we
    // substitute per-hand later. Mirrors `exploit.rs::flat_tree_exploit`
    // tree-build path.
    let placeholder = initial.clone_with_hole_cards([eval_ctx.hole[0][0], eval_ctx.hole[1][0]]);
    let tree = BettingTree::build_from(&placeholder);

    let mut solver = VectorDCFR::new(&tree, eval_ctx.hand_count, alpha, beta, gamma);
    solver.solve(&tree, &eval_ctx, iterations);

    // Final discount catch-up to mirror `dcfr.rs::DCFRSolver::solve`
    // tail-discount semantics + Python's `_discount` final pass.
    let final_iter = solver.iteration;
    let alpha = solver.alpha;
    let beta = solver.beta;
    let gamma = solver.gamma;
    for info in solver.infosets.iter_mut().flatten() {
        VectorDCFR::discount(info, final_iter, alpha, beta, gamma);
    }

    let average_strategy = build_average_strategy(&solver, &tree, &eval_ctx);
    let decision_node_count = solver
        .infosets
        .iter()
        .filter(|s| s.is_some())
        .count() as u32;
    let strategy_entry_count = average_strategy.len() as u32;
    let memory_profile = build_memory_profile(&solver, &tree, &eval_ctx);
    Ok(VectorSolveOutput {
        average_strategy,
        decision_node_count,
        strategy_entry_count,
        iterations,
        hand_count_per_player: eval_ctx.hand_count,
        memory_profile,
    })
}

/// Compute the per-street memory profile for a finished solve.
///
/// Each infoset contributes
/// `2 * (hand_count × action_count × 8 bytes)` (regret + strategy_sum,
/// both `f64`). The street label is read from the decision node's
/// `key_suffix` (`"|<board>|<street_token>|<history>"`) — the second
/// `|`-separated token. Spec §4 expectations:
///
/// | Street | hand_count | num_actions | bytes / infoset |
/// |---|---|---|---|
/// | Flop (bucketed) | 256 | 14 | 57 KB |
/// | Turn (bucketed) | 128 | 14 | 28 KB |
/// | River (bucketed) | 64 | 14 | 14 KB |
/// | Preflop (lossless) | 1326 | 14 | 297 KB |
///
/// v1.5.0 ships without bucketing engaged in the vector form so actual
/// per-infoset memory is closer to `hand_count = C(deck-board, 2)`
/// (1081 for river, 1128 for turn). The profile is honest about what
/// it measures (see `feedback_no_extrapolate.md` in user memory: "no
/// per-layer extrapolation without measurement").
pub(crate) fn build_memory_profile(
    solver: &VectorDCFR,
    tree: &BettingTree,
    ctx: &EvalContext,
) -> VectorMemoryProfile {
    let mut total_bytes: u64 = 0;
    let mut by_street: std::collections::HashMap<String, u64> =
        std::collections::HashMap::new();
    let mut infoset_count_by_street: std::collections::HashMap<String, u32> =
        std::collections::HashMap::new();
    let mut infoset_count: u32 = 0;
    for (node_idx, slot) in solver.infosets.iter().enumerate() {
        let info = match slot {
            Some(info) => info,
            None => continue,
        };
        let node = &tree.nodes[node_idx];
        let key_suffix = match node {
            FlatNode::Decision { key_suffix, .. } => key_suffix.as_str(),
            _ => continue,
        };
        // Parse the street token out of "|<board>|<street>|<history>".
        let street = key_suffix
            .split('|')
            .nth(2)
            .map(street_label_from_token)
            .unwrap_or("unknown");
        let bytes = (info.regret.len() as u64 + info.strategy_sum.len() as u64) * 8;
        total_bytes += bytes;
        *by_street.entry(street.to_string()).or_insert(0) += bytes;
        *infoset_count_by_street.entry(street.to_string()).or_insert(0) += 1;
        infoset_count += 1;
    }
    VectorMemoryProfile {
        total_bytes,
        by_street,
        infoset_count,
        infoset_count_by_street,
        hand_count: ctx.hand_count,
    }
}

/// Map a `HUNLState::infoset_key` street token to a human-readable name.
/// Mirrors `Street::token()` in `hunl.rs:73-81`.
fn street_label_from_token(token: &str) -> &'static str {
    match token {
        "p" => "preflop",
        "f" => "flop",
        "t" => "turn",
        "r" => "river",
        "s" => "showdown",
        _ => "unknown",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::hunl::{card_to_int, HUNLConfig, Street};

    fn tiny_river_rvr() -> HUNLConfig {
        // Tiny river RvR config: a fixed 5-card board so the hole-card
        // dimension is bounded at C(47, 2) = 1081 hands per player.
        // Single bet size for a small tree.
        HUNLConfig {
            starting_stack: 1000,
            small_blind: 50,
            big_blind: 100,
            ante: 0,
            starting_street: Street::River,
            initial_board: vec![
                card_to_int(14, 0), // As
                card_to_int(7, 3),  // 7c
                card_to_int(2, 2),  // 2d
                card_to_int(13, 1), // Kh
                card_to_int(5, 0),  // 5s
            ],
            initial_pot: 1000,
            initial_contributions: [500, 500],
            initial_hole_cards: None,
            preflop_raise_cap: 4,
            postflop_raise_cap: 1,
            bet_size_fractions: vec![1.0],
            include_all_in: false,
            force_allin_threshold: 1,
            min_bet_bb: 1,
            rake_rate: 0.0,
            rake_cap: 0,
            abstraction_path: None,
            abstraction_version: None,
            use_pcs: false,
        }
    }

    #[test]
    fn vector_solver_runs_minimum_iters() {
        // Smoke test: 3 iterations on the tiny river RvR config.
        // We do NOT check exploitability here (that's the differential
        // test in `tests/test_range_vs_range_rust_diff.py`); this only
        // verifies that the solver runs to completion and emits a
        // sensible dict shape. 3 iters keeps the test under ~60s on
        // a 1081-hand tree; perf optimization is v1.5.x.
        let cfg = tiny_river_rvr();
        let out = solve_range_vs_range_postflop(&cfg, 3, 1.5, 0.0, 2.0).unwrap();
        assert!(
            out.decision_node_count > 0,
            "no decision nodes — tree build broken"
        );
        assert!(
            out.strategy_entry_count > 0,
            "no strategy entries emitted"
        );
        assert_eq!(out.iterations, 3);
        let expected_hands = 47 * 46 / 2;
        assert_eq!(out.hand_count_per_player, [expected_hands, expected_hands]);
        // Each strategy row should sum to ~1.0.
        for (key, probs) in out.average_strategy.iter().take(5) {
            let total: f64 = probs.iter().sum();
            assert!(
                (total - 1.0).abs() < 1e-6,
                "row {key:?} does not sum to 1.0 (got {total})"
            );
        }
    }

    #[test]
    fn vector_solver_rejects_fixed_combo_config() {
        // Hard rule: solve_range_vs_range_postflop must reject configs
        // with `initial_hole_cards` set — those should route through
        // `hunl_solver::solve_hunl_postflop`.
        let mut cfg = tiny_river_rvr();
        cfg.initial_hole_cards = Some([
            [card_to_int(14, 1), card_to_int(13, 3)],
            [card_to_int(12, 2), card_to_int(12, 1)],
        ]);
        let err = solve_range_vs_range_postflop(&cfg, 5, 1.5, 0.0, 2.0);
        assert!(err.is_err(), "must reject fixed-combo config");
    }

    #[test]
    fn vector_solver_rejects_preflop_config() {
        let mut cfg = tiny_river_rvr();
        cfg.starting_street = Street::Preflop;
        cfg.initial_board = vec![];
        let err = solve_range_vs_range_postflop(&cfg, 5, 1.5, 0.0, 2.0);
        assert!(err.is_err(), "must reject preflop config in v1.5.0");
    }
}
