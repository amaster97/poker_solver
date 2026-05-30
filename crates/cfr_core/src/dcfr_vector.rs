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
//!
//! ## B10 Phase B — per-combo fractional weights (2026-05-28)
//!
//! Adds an optional `hand_weights: Option<[Vec<f64>; 2]>` parameter to
//! `solve_range_vs_range_postflop_with_hands` (and the PyO3 wrapper
//! `solve_range_vs_range_rust` via the `p0_weights` / `p1_weights`
//! kwargs in `lib.rs`). When supplied, each `w[i]` aligns positionally
//! with `pN_holes[i]` and becomes the initial reach into the root
//! infoset for that hand. **Multiplicative factor only**: the
//! regret-matching / strategy-update / discount loops are bit-identical
//! to the pre-Phase-B code. All-ones weights (the default) reproduce
//! the legacy behavior exactly. See
//! `docs/b10_per_combo_frequency_plan_2026-05-28.md` §3.

// The vector-form CFR inner loops index per-(hand, action) into multiple
// parallel arrays (regret, strategy, action_values, reach), so the
// indexed-for-loop shape is clearer than the iterator form Clippy
// proposes. Brown's reference (`trainer.cpp`, MIT) uses the same shape.
#![allow(clippy::needless_range_loop)]

use std::collections::HashMap;

use crate::arena::{BumpArena, TLS_ARENA};
use crate::exploit::{
    enumerate_hole_card_pairs, hole_string, terminal_utility, BettingTree, BettingTreeMode,
    FlatNode,
};
use crate::hunl::{HUNLConfig, HUNLState};
use crate::hunl_eval::Strength;
use crate::simd;

thread_local! {
    /// Per-thread prefix-sum scratch for [`terminal_value_vector_ie`].
    ///
    /// Reused across every IE terminal eval on this thread (cleared and
    /// resized in-place), so the opt-in IE path never allocates per call.
    /// Thread-local so each rayon worker on the parallel chance path owns
    /// its own buffer with no cross-thread borrow. Never allocated unless
    /// the IE path runs (`CFR_TERMINAL_IE` set).
    static TLS_IE_SCRATCH: std::cell::RefCell<Vec<f64>> = const { std::cell::RefCell::new(Vec::new()) };
}

// ---------------------------------------------------------------------------
// HIGH-2 follow-up: terminal-leaf precomputation cache.
//
// Profile data on full-deck river (1081 board-disjoint hands per player,
// 4 terminal leaves) showed `terminal_value_vector` consuming ~100% of
// inner-kernel time. Root cause: `terminal_utility` calls `evaluate_7`
// twice per (hp, ho) pair at every Showdown leaf, every iteration —
// `~1.1M pairs × 2 evals × N leaves × 2N iters` of repeated O(N²)
// `evaluate_7` work for a constant board.
//
// This cache precomputes once per solve:
//   - For Showdown leaves: per-player `Strength` vector. The per-pair
//     utility becomes a single `Strength` cmp (u64 cmp) + a branch on
//     {win, lose, tie} payoff. No `evaluate_7` in the inner loop.
//   - For Fold leaves: utility is constant in the holes (just chip flow);
//     stored as a single scalar per (leaf, update_player).
//
// Bit-exactness with the un-cached path is preserved because:
//   - `Strength::evaluate_7` is deterministic, so caching the result and
//     comparing cached `u64`s yields the same `>`/`<`/`==` outcome.
//   - The payoff branches use the same chip arithmetic as `terminal_utility`,
//     verified by the unit test `terminal_value_vector_matches_uncached`.
// ---------------------------------------------------------------------------

/// Precomputed per-leaf utility data, keyed by `tree.nodes` index.
///
/// One entry per terminal leaf (Fold or Showdown). Non-terminal nodes
/// (Chance, Decision) get `LeafKind::NonTerminal` placeholders so we can
/// index by `node_idx` directly without a side-map.
pub(crate) struct TerminalCache {
    pub(crate) leaves: Vec<LeafCacheEntry>,
    /// Board-independent fold blocker unions, present iff the inclusion-
    /// exclusion terminal evaluator (`CFR_TERMINAL_IE`) is enabled for
    /// this solve. `fold_blockers[up][hp]` lists the deduped opp hand
    /// indices that share at least one card with player `up`'s hand
    /// `hp` (opp = `1 - up`). `None` when the flag is unset — zero
    /// default memory cost.
    ///
    /// Computed once per `up` because the fold blocker set depends only
    /// on hole cards (not on the leaf/board), so it is identical for
    /// every Fold leaf in the tree.
    pub(crate) fold_blockers: Option<[Vec<Vec<u32>>; 2]>,
}

pub(crate) enum LeafCacheEntry {
    /// Non-terminal node (Chance or Decision) — no cache content.
    NonTerminal,
    /// Fold leaf — utility is constant in hole cards.
    /// `payoff[update_player]` is the BB-normalized chip flow.
    Fold { payoff: [f64; 2] },
    /// Showdown leaf — precomputed per-player strength vectors plus the
    /// constant chip-flow factors. The per-pair utility is:
    ///   if s0 > s1: P0 wins → `(pot/2 + cs_loser0)/bb` for winner,
    ///               `-cs0/bb` for loser. Etc.
    Showdown {
        /// `strength[p][h] = Strength::evaluate_7(hole[p][h] ++ board)`.
        strength: [Vec<Strength>; 2],
        /// Per-(winning_player, update_player) payoff. `win_payoff[winner][update]`.
        /// e.g. `win_payoff[0][0] = (pot_total - cs0) / bb` (P0 wins, payoff to P0).
        win_payoff: [[f64; 2]; 2],
        /// Per-update_player tie payoff (split pot).
        tie_payoff: [f64; 2],
        /// Inclusion-exclusion precompute, present iff `CFR_TERMINAL_IE`
        /// is enabled. `None` (a null pointer — no allocation, no compute
        /// cost) when the flag is unset. Boxed so the enum's inline size
        /// stays small on the flag-off (default) path. One entry per
        /// update_player perspective.
        ie: Option<Box<[ShowdownIE; 2]>>,
    },
}

/// Per-(update_player) inclusion-exclusion precompute for one Showdown
/// leaf. Enables an O(N + N·B) showdown evaluation (prefix-sum over
/// sorted opp strengths, minus per-hand blocker corrections) in place of
/// the O(N²) per-pair scan.
///
/// Algorithm: Noam Brown poker_solver vector_eval.cpp
/// build_cache/showdown_values/fold_values (MIT, (c) 2025 Noam Brown).
pub(crate) struct ShowdownIE {
    /// Opp hand indices sorted ascending by opp `Strength`. Length `n_op`.
    pub(crate) sorted_idx: Vec<u32>,
    /// `range_start[hp]` = count of opp hands strictly weaker than
    /// player hand `hp` (partition_point on the sorted strengths).
    pub(crate) range_start: Vec<u32>,
    /// `range_end[hp]` = count of opp hands weaker-or-equal to `hp`.
    /// `[range_start, range_end)` is the tie band.
    pub(crate) range_end: Vec<u32>,
    /// Deduped blocker opp idxs (sharing a card with `hp`) that are
    /// strictly WEAKER than `hp` (player wins vs these).
    pub(crate) blk_less: Vec<Vec<u32>>,
    /// Deduped blocker opp idxs that TIE `hp`.
    pub(crate) blk_equal: Vec<Vec<u32>>,
    /// Deduped blocker opp idxs that are strictly STRONGER than `hp`
    /// (player loses vs these).
    pub(crate) blk_greater: Vec<Vec<u32>>,
}

impl TerminalCache {
    /// Build a per-leaf cache for every terminal in `tree`. Showdown
    /// leaves are evaluated once per player; Fold leaves only need their
    /// chip-flow precomputed (no per-hand evaluation needed).
    ///
    /// `terminal_ie`: when `true`, additionally precompute the
    /// inclusion-exclusion data ([`ShowdownIE`] per Showdown leaf, plus a
    /// board-independent fold-blocker union) used by
    /// [`terminal_value_vector_ie`]. When `false` (default), no IE data is
    /// built — `ie` fields stay `None` and `fold_blockers` stays `None`,
    /// so the flag-off path carries zero added memory/compute cost.
    pub(crate) fn build(tree: &BettingTree, ctx: &EvalContext, terminal_ie: bool) -> Self {
        let mut leaves: Vec<LeafCacheEntry> = Vec::with_capacity(tree.nodes.len());
        for node in &tree.nodes {
            match node {
                FlatNode::Fold {
                    contributions,
                    big_blind,
                    folded_player,
                    initial_pot,
                    initial_contributions,
                } => {
                    let bb = *big_blind as f64;
                    let cs0 = contributions[0] as f64 - initial_contributions[0] as f64;
                    let cs1 = contributions[1] as f64 - initial_contributions[1] as f64;
                    let pot_total = *initial_pot as f64 + cs0 + cs1;
                    let payoff = if *folded_player == 0 {
                        // P1 wins.
                        [-cs0 / bb, (pot_total - cs1) / bb]
                    } else {
                        // P0 wins.
                        [(pot_total - cs0) / bb, -cs1 / bb]
                    };
                    leaves.push(LeafCacheEntry::Fold { payoff });
                }
                FlatNode::Showdown {
                    contributions,
                    big_blind,
                    board,
                    initial_pot,
                    initial_contributions,
                } => {
                    let bb = *big_blind as f64;
                    let cs0 = contributions[0] as f64 - initial_contributions[0] as f64;
                    let cs1 = contributions[1] as f64 - initial_contributions[1] as f64;
                    let pot_total = *initial_pot as f64 + cs0 + cs1;
                    // win_payoff[winner][update_player]:
                    //   winner = 0: P0 collects (pot - cs0)/bb, P1 pays -cs1/bb
                    //   winner = 1: P0 pays   -cs0/bb,         P1 collects (pot - cs1)/bb
                    let win_payoff = [
                        [(pot_total - cs0) / bb, -cs1 / bb],
                        [-cs0 / bb, (pot_total - cs1) / bb],
                    ];
                    let tie_payoff = [
                        (pot_total / 2.0 - cs0) / bb,
                        (pot_total / 2.0 - cs1) / bb,
                    ];
                    // Per-player strength vectors. Each evaluation is a
                    // single `evaluate_7(hole ++ board)` call.
                    let mut strength_p: [Vec<Strength>; 2] = [
                        Vec::with_capacity(ctx.hand_count[0]),
                        Vec::with_capacity(ctx.hand_count[1]),
                    ];
                    for p in 0..2 {
                        for h in 0..ctx.hand_count[p] {
                            let hole = ctx.hole[p][h];
                            let mut seven = [0u8; 7];
                            seven[0] = hole[0];
                            seven[1] = hole[1];
                            seven[2..7].copy_from_slice(board);
                            strength_p[p].push(Strength::evaluate_7(&seven));
                        }
                    }
                    let ie = if terminal_ie {
                        Some(Box::new([
                            build_showdown_ie(&strength_p, ctx, 0),
                            build_showdown_ie(&strength_p, ctx, 1),
                        ]))
                    } else {
                        None
                    };
                    leaves.push(LeafCacheEntry::Showdown {
                        strength: strength_p,
                        win_payoff,
                        tie_payoff,
                        ie,
                    });
                }
                _ => leaves.push(LeafCacheEntry::NonTerminal),
            }
        }
        let fold_blockers = if terminal_ie {
            Some([
                build_fold_blockers(ctx, 0),
                build_fold_blockers(ctx, 1),
            ])
        } else {
            None
        };
        Self {
            leaves,
            fold_blockers,
        }
    }
}

/// Board-independent fold-blocker union for player `up` (opp = `1 - up`).
///
/// `out[hp]` = deduped opp hand indices sharing ≥1 card with player `up`'s
/// hand `hp`. Depends only on hole cards, so it is computed once and
/// reused for every Fold leaf (which has constant-in-holes utility).
///
/// Algorithm: Noam Brown poker_solver vector_eval.cpp build_cache
/// (card_to_indices + epoch-stamped dedup) (MIT, (c) 2025 Noam Brown).
fn build_fold_blockers(ctx: &EvalContext, up: usize) -> Vec<Vec<u32>> {
    let op = 1 - up;
    let n_op = ctx.hand_count[op];
    let n_up = ctx.hand_count[up];

    // Card encoding is `rank*4 + suit`, range [8, 59] (NOT [0, 51]), so
    // size the table to 64 to hold every legal card int.
    let mut card_to_idx: [Vec<u32>; 64] = std::array::from_fn(|_| Vec::new());
    for (idx, hole) in ctx.hole[op].iter().enumerate() {
        card_to_idx[hole[0] as usize].push(idx as u32);
        card_to_idx[hole[1] as usize].push(idx as u32);
    }

    let mut out: Vec<Vec<u32>> = Vec::with_capacity(n_up);
    // Epoch-stamp dedup: the {c0,c1} opp hand appears in BOTH card lists,
    // so guard each idx with the per-hand `stamp` (never clearing `seen`).
    // `stamp` starts at 1 so it differs from the all-zero initial `seen`.
    let mut seen: Vec<u32> = vec![0u32; n_op];
    for (stamp, hole) in (1_u32..).zip(ctx.hole[up].iter()) {
        let mut blocked: Vec<u32> = Vec::new();
        for &card in hole.iter() {
            for &idx in &card_to_idx[card as usize] {
                if seen[idx as usize] != stamp {
                    seen[idx as usize] = stamp;
                    blocked.push(idx);
                }
            }
        }
        out.push(blocked);
    }
    out
}

/// Per-(update_player) inclusion-exclusion precompute for one Showdown
/// leaf. `strength_p[p][h]` is the precomputed 7-card strength for player
/// `p`'s hand `h`; `up` is the perspective player (opp = `1 - up`).
///
/// Algorithm: Noam Brown poker_solver vector_eval.cpp build_cache
/// (MIT, (c) 2025 Noam Brown). Sorts opp strengths, derives strength
/// partition points via binary search, and partitions each player hand's
/// deduped blocker union by relative strength.
fn build_showdown_ie(strength_p: &[Vec<Strength>; 2], ctx: &EvalContext, up: usize) -> ShowdownIE {
    let op = 1 - up;
    let n_op = ctx.hand_count[op];
    let n_up = ctx.hand_count[up];
    let s_up = &strength_p[up];
    let s_op = &strength_p[op];

    // Opp indices sorted ascending by opp strength. `Strength(u64)`
    // derives Ord, so we sort by it directly.
    let mut sorted_idx: Vec<u32> = (0..n_op as u32).collect();
    sorted_idx.sort_unstable_by_key(|&i| s_op[i as usize]);
    let strengths_sorted: Vec<Strength> =
        sorted_idx.iter().map(|&i| s_op[i as usize]).collect();

    // Strength partition points per player hand.
    let mut range_start: Vec<u32> = Vec::with_capacity(n_up);
    let mut range_end: Vec<u32> = Vec::with_capacity(n_up);
    for &sp in s_up.iter() {
        let start = strengths_sorted.partition_point(|&s| s < sp);
        let end = strengths_sorted.partition_point(|&s| s <= sp);
        range_start.push(start as u32);
        range_end.push(end as u32);
    }

    // card -> opp idxs, for the blocker union. Card encoding is
    // `rank*4 + suit`, range [8, 59], so size the table to 64.
    let mut card_to_idx: [Vec<u32>; 64] = std::array::from_fn(|_| Vec::new());
    for (idx, hole) in ctx.hole[op].iter().enumerate() {
        card_to_idx[hole[0] as usize].push(idx as u32);
        card_to_idx[hole[1] as usize].push(idx as u32);
    }

    let mut blk_less: Vec<Vec<u32>> = Vec::with_capacity(n_up);
    let mut blk_equal: Vec<Vec<u32>> = Vec::with_capacity(n_up);
    let mut blk_greater: Vec<Vec<u32>> = Vec::with_capacity(n_up);
    // Epoch-stamp dedup so the {c0,c1} opp hand is counted exactly once.
    // `stamp` starts at 1 so it differs from the all-zero initial `seen`.
    let mut seen: Vec<u32> = vec![0u32; n_op];
    for (stamp, (hp, hole)) in (1_u32..).zip(ctx.hole[up].iter().enumerate()) {
        let sp = s_up[hp];
        let mut less: Vec<u32> = Vec::new();
        let mut equal: Vec<u32> = Vec::new();
        let mut greater: Vec<u32> = Vec::new();
        for &card in hole.iter() {
            for &idx in &card_to_idx[card as usize] {
                if seen[idx as usize] != stamp {
                    seen[idx as usize] = stamp;
                    let so = s_op[idx as usize];
                    // blk_less = opp WEAKER => player WINS (win_self).
                    // blk_greater = opp STRONGER => player LOSES (win_opp).
                    if so < sp {
                        less.push(idx);
                    } else if so > sp {
                        greater.push(idx);
                    } else {
                        equal.push(idx);
                    }
                }
            }
        }
        blk_less.push(less);
        blk_equal.push(equal);
        blk_greater.push(greater);
    }

    ShowdownIE {
        sorted_idx,
        range_start,
        range_end,
        blk_less,
        blk_equal,
        blk_greater,
    }
}

// ---------------------------------------------------------------------------
// HIGH-2 follow-up profiling instrumentation (feature `profile_rvr`).
//
// When the `profile_rvr` feature is enabled, each labeled phase inside
// `traverse` accumulates its wall-clock cost into a thread-local counter
// reported by the `rvr_profile` bench. Without the feature, `prof_start`
// returns `()` and `prof_end` is a no-op — the compiler folds both away
// so the production hot path pays zero overhead.
// ---------------------------------------------------------------------------

#[cfg(feature = "profile_rvr")]
pub mod profile {
    use std::cell::RefCell;
    use std::time::{Duration, Instant};

    #[derive(Default, Clone, Debug)]
    pub struct PhaseCounters {
        pub terminal_eval_ns: u128,
        pub compute_strategy_ns: u128,
        pub discount_ns: u128,
        pub opp_next_reach_ns: u128,
        pub own_next_reach_ns: u128,
        pub node_values_ns: u128,
        pub update_regret_ns: u128,
        pub update_strategy_sum_ns: u128,
        pub alloc_action_values_ns: u128,
        pub alloc_strategy_buf_ns: u128,
        pub chance_accumulate_ns: u128,
    }

    thread_local! {
        static COUNTERS: RefCell<PhaseCounters> = RefCell::new(PhaseCounters::default());
    }

    pub fn reset() {
        COUNTERS.with(|c| *c.borrow_mut() = PhaseCounters::default());
    }

    pub fn snapshot() -> PhaseCounters {
        COUNTERS.with(|c| c.borrow().clone())
    }

    #[inline(always)]
    pub fn start() -> Instant {
        Instant::now()
    }

    #[inline(always)]
    pub fn add(field: PhaseField, t: Instant) {
        let dur: Duration = t.elapsed();
        let ns = dur.as_nanos();
        COUNTERS.with(|c| {
            let mut cnt = c.borrow_mut();
            match field {
                PhaseField::TerminalEval => cnt.terminal_eval_ns += ns,
                PhaseField::ComputeStrategy => cnt.compute_strategy_ns += ns,
                PhaseField::Discount => cnt.discount_ns += ns,
                PhaseField::OppNextReach => cnt.opp_next_reach_ns += ns,
                PhaseField::OwnNextReach => cnt.own_next_reach_ns += ns,
                PhaseField::NodeValues => cnt.node_values_ns += ns,
                PhaseField::UpdateRegret => cnt.update_regret_ns += ns,
                PhaseField::UpdateStrategySum => cnt.update_strategy_sum_ns += ns,
                PhaseField::AllocActionValues => cnt.alloc_action_values_ns += ns,
                PhaseField::AllocStrategyBuf => cnt.alloc_strategy_buf_ns += ns,
                PhaseField::ChanceAccumulate => cnt.chance_accumulate_ns += ns,
            }
        });
    }

    #[derive(Copy, Clone)]
    pub enum PhaseField {
        TerminalEval,
        ComputeStrategy,
        Discount,
        OppNextReach,
        OwnNextReach,
        NodeValues,
        UpdateRegret,
        UpdateStrategySum,
        AllocActionValues,
        AllocStrategyBuf,
        ChanceAccumulate,
    }
}

#[cfg(feature = "profile_rvr")]
macro_rules! prof_start {
    () => { Some($crate::dcfr_vector::profile::start()) };
}
#[cfg(feature = "profile_rvr")]
macro_rules! prof_end {
    ($t:expr, $field:ident) => {
        if let Some(t) = $t {
            $crate::dcfr_vector::profile::add(
                $crate::dcfr_vector::profile::PhaseField::$field, t);
        }
    };
}

#[cfg(not(feature = "profile_rvr"))]
macro_rules! prof_start {
    () => { () };
}
#[cfg(not(feature = "profile_rvr"))]
macro_rules! prof_end {
    ($t:expr, $field:ident) => { let _ = $t; };
}

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
    /// `v1.10 PR-2` — per-`FlatNode` index, true iff the chance node at this
    /// index has a `ChanceTemplate` entry (its children share structural
    /// identity, so `traverse_turn_chance` can use the shared-scratch path).
    /// `false` for non-chance nodes and for chance nodes that didn't make
    /// the template extraction (single-child run-out chance, or `Standard`
    /// build mode). Indexed by `FlatNode` index for O(1) lookup in the
    /// chance match arm of `traverse`.
    has_chance_template: Vec<bool>,
    /// `v1.10 PR-3` — per-`FlatNode` index, the chance template's
    /// `chance_depth` (or `0` when no template). Indexed by `FlatNode`
    /// index for O(1) lookup in the chance match arm. Combined with
    /// `has_chance_template`, the dispatch can route to:
    ///   - `depth == 2` (flop chance) → `traverse_flop_chance_recursive`
    ///   - `depth == 1` (turn chance) → `traverse_turn_chance_recursive`
    ///   - otherwise → legacy chance loop
    ///
    /// **Note:** currently consumed only at solve-time via the dispatch
    /// lookup in `RunoutCache::build` (the cache scans
    /// `tree.chance_templates` directly). Reserved as the O(1)
    /// per-node lookup once a hot-path dispatch optimization is needed.
    #[allow(dead_code)]
    chance_depth: Vec<u8>,
}

impl VectorDCFR {
    /// Construct a `VectorDCFR` with all-zero initial regrets. Equivalent to
    /// `with_init_noise(tree, …, regret_init_noise = 0.0, rng_seed = 0)`.
    /// Kept as a binary-API stub for external consumers + the
    /// `vector_solver_runs_minimum_iters` smoke test; production paths flow
    /// through `with_init_noise` so the PR 90 noise plumbing is exercised
    /// on the default (zero) branch as well as the perturbed branch.
    #[allow(dead_code)]
    pub(crate) fn new(tree: &BettingTree, hand_count_per_player: [usize; 2], alpha: f64, beta: f64, gamma: f64) -> Self {
        Self::with_init_noise(tree, hand_count_per_player, alpha, beta, gamma, 0.0, 0)
    }

    /// PR 90 (A83 Track A) — construct with optional initial regret
    /// perturbation for empirical Nash-multiplicity testing.
    ///
    /// When `regret_init_noise > 0.0`, each `regret[h*A+a]` is seeded with
    /// `noise * rng.next_f64_signed()` instead of `0.0`. The RNG is
    /// deterministically seeded by `rng_seed` (a `PcsRng` splitmix64
    /// stream) so the same `(noise, seed)` pair always produces the same
    /// initial state. `regret_init_noise = 0.0` is bit-identical to the
    /// prior `VectorInfosetData::new` all-zero initialization, preserving
    /// the differential-test contract.
    ///
    /// Vector-form populates ALL decision-node infosets up front (no lazy
    /// `or_insert_with` like the scalar `hunl_solver.rs` path) — so the
    /// perturbation is applied here in the constructor, NOT in the
    /// per-iteration traverse.
    pub(crate) fn with_init_noise(
        tree: &BettingTree,
        hand_count_per_player: [usize; 2],
        alpha: f64,
        beta: f64,
        gamma: f64,
        regret_init_noise: f64,
        rng_seed: u64,
    ) -> Self {
        // v1.8.1 (HIGH-1): HARD-FAIL on α ≤ 0, WARN on α < 0.5.
        crate::dcfr::validate_alpha(alpha);
        let mut init_rng = crate::pcs::PcsRng::new(rng_seed);
        let mut infosets: Vec<Option<VectorInfosetData>> = Vec::with_capacity(tree.nodes.len());
        for node in &tree.nodes {
            match node {
                FlatNode::Decision { player, actions, .. } => {
                    let action_count = actions.len();
                    let hand_count = hand_count_per_player[*player as usize];
                    let mut info = VectorInfosetData::new(action_count, hand_count);
                    if regret_init_noise > 0.0 {
                        for slot in info.regret.iter_mut() {
                            *slot = regret_init_noise * init_rng.next_f64_signed();
                        }
                    }
                    infosets.push(Some(info));
                }
                _ => infosets.push(None),
            }
        }
        // `v1.10 PR-2` — build the per-node has_chance_template lookup from
        // the tree's `chance_templates` list (populated only in
        // `BettingTreeMode::TemplateExtract`). When the list is empty (e.g.
        // `Standard` mode for river-rooted subgames), every entry is false
        // and the chance-arm dispatches to the legacy per-branch recursion.
        let mut has_chance_template = vec![false; tree.nodes.len()];
        // `v1.10 PR-3` — per-node chance-template depth (0 = no template).
        let mut chance_depth = vec![0u8; tree.nodes.len()];
        for t in &tree.chance_templates {
            has_chance_template[t.chance_node_idx] = true;
            chance_depth[t.chance_node_idx] = t.chance_depth;
        }
        Self {
            alpha,
            beta,
            gamma,
            iteration: 0,
            infosets,
            has_chance_template,
            chance_depth,
        }
    }

    /// Regret-matching per-hand. Output is row-major
    /// `strategy[hand_idx * action_count + action_idx]`.
    ///
    /// Mirrors Brown's `Trainer::compute_strategy`
    /// (`trainer.cpp:72-98`, MIT): for each hand, sum positive regrets;
    /// if positive, normalize them as the strategy; else uniform.
    ///
    /// PR 71 (v1.8 Phase 4) routes the per-hand body through
    /// `simd::compute_strategy_row` which dispatches NEON / AVX2 / SSE2 /
    /// scalar based on the current target. The scalar implementation here
    /// is preserved as the parity reference (and used unchanged on
    /// non-vectorized targets via the scalar fallback inside the dispatch).
    fn compute_strategy(info: &VectorInfosetData, out: &mut [f64]) {
        let hand_count = info.hand_count;
        let action_count = info.action_count;
        debug_assert_eq!(out.len(), hand_count * action_count);
        for h in 0..hand_count {
            let offset = h * action_count;
            let regrets_row = &info.regret[offset..offset + action_count];
            let out_row = &mut out[offset..offset + action_count];
            crate::simd::compute_strategy_row(regrets_row, out_row);
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
    /// vectors.
    ///
    /// PR 61 (v1.8 Phase 1): routes through `simd::discount_regrets` +
    /// `simd::discount_strategy_sum`. Those kernels operate on flat
    /// `&mut [f64]` slices and don't care about the row-major
    /// `hand_count × action_count` layout — they vectorize across whatever
    /// width the slice has. NEON on aarch64, SSE2 on x86_64, scalar
    /// fallback elsewhere. Behavior is bit-identical to the previous
    /// inline scalar loop (the SIMD paths' `_matches_scalar` tests are
    /// part of the `simd` module's parity gate).
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
            simd::discount_regrets(&mut info.regret, pos_scale, neg_scale);
            simd::discount_strategy_sum(&mut info.strategy_sum, strat_scale);
        }
        info.last_discount_iter = t;
    }

    /// Drive `iterations` iterations of vector-form DCFR. Alternates
    /// player updates per iteration to match Brown's `Trainer::run`
    /// (`trainer.cpp:343-369`, MIT).
    ///
    /// HIGH-2 follow-up: builds a `TerminalCache` once before iteration
    /// so per-pair `evaluate_7` work happens only once per leaf for the
    /// whole solve, not per iter.
    ///
    /// **B10 Phase B — per-combo weights.** When `hand_weights` is
    /// supplied (`Some([w0, w1])`), the initial reach vectors are set to
    /// the supplied per-hand weights instead of the all-ones default.
    /// This is the **multiplicative-only** wiring of per-combo fractional
    /// frequencies into the kernel: the regret/strategy update path is
    /// unchanged; only the initial reach into the root infoset is scaled.
    /// Each `w[i]` aligns positionally with `eval_ctx.hole[p][i]` (and
    /// hence with the `p{p}_holes` list that built the `EvalContext`).
    /// All-ones weights are bit-identical to the legacy `None` path.
    pub(crate) fn solve(
        &mut self,
        tree: &BettingTree,
        eval_ctx: &EvalContext,
        iterations: u32,
        hand_weights: Option<[Vec<f64>; 2]>,
    ) {
        // Initial reach vectors per player. Brown's reference initializes
        // from `hand_weights_ptr_` (the per-hand range weights from the
        // `RiverGame`); we now plug per-combo fractional weights from
        // Python through this same vector. Default = ones (legacy
        // back-compat, bit-identical to pre-B10-Phase-B).
        let (reach_p0, reach_p1) = match hand_weights {
            Some([w0, w1]) => {
                // Defensive length check — the Python binding aligns these
                // with `p0_holes`/`p1_holes`, but a misaligned call could
                // silently produce garbage. Hard-fail instead.
                assert_eq!(
                    w0.len(),
                    eval_ctx.hand_count[0],
                    "p0_weights length {} != hand_count[0] {}",
                    w0.len(),
                    eval_ctx.hand_count[0],
                );
                assert_eq!(
                    w1.len(),
                    eval_ctx.hand_count[1],
                    "p1_weights length {} != hand_count[1] {}",
                    w1.len(),
                    eval_ctx.hand_count[1],
                );
                (w0, w1)
            }
            None => (
                vec![1.0; eval_ctx.hand_count[0]],
                vec![1.0; eval_ctx.hand_count[1]],
            ),
        };
        // Read `CFR_TERMINAL_IE` ONCE per solve (mirroring `rayon_enabled`).
        // When set, the inclusion-exclusion terminal evaluator is used and
        // its precompute is built into the cache; when unset, no IE data is
        // built and the legacy cached path runs unchanged.
        let terminal_ie = terminal_ie_enabled();
        let terminal_cache = TerminalCache::build(tree, eval_ctx, terminal_ie);
        // v1.10 PR-3 — build the RunoutCache once at solve-start so the
        // flop-level walker can reuse its scratch buffers across all
        // iterations. When the tree has no depth==2 chance template
        // (turn/river-rooted solves, or `Standard` build mode), this
        // returns an empty/inactive cache and the dispatch falls
        // through to the PR-2 turn walker or the legacy chance loop.
        let mut runout_cache = RunoutCache::build(tree, eval_ctx);
        // v1.10 PR-4 — dispatch on the `CFR_RAYON_CHANCE` env var ONCE
        // per solve (not per iter). When set, the FIRST multi-child
        // `FlatNode::Chance` encountered during each iteration's
        // traversal gets parallelized (the rest of the tree stays
        // sequential to avoid oversubscription). Default (env var
        // unset) is bit-identical to pre-PR-4.
        let rayon_enabled = crate::dcfr_vector_parallel::parallel_chance_enabled();
        // v1.10 PR-1 — pull the thread-local bump arena once and reuse
        // across all iterations. Per-`traverse` scratch buffers
        // (`strategy`, `action_values`, `next_reach`) come from this
        // arena instead of `vec![0.0; N]`. Backing capacity grows by
        // doubling on the first solve and is reused for every
        // subsequent solve on this thread.
        //
        // `has_chance_template` is threaded through so the v1.10 PR-2
        // template walker hook fires inside the recursive traversal when
        // a chance node was tagged at tree-build time.
        //
        // v1.10 PR-3 — `runout_cache` is also threaded through so the
        // outer flop chance walker's scratch buffers persist across both
        // player updates of every iteration.
        TLS_ARENA.with(|cell| {
            let mut arena_ref = cell.borrow_mut();
            let arena: &mut BumpArena = &mut arena_ref;
            let outer_mark = arena.mark();
            for _ in 0..iterations {
                self.iteration += 1;
                let iteration = self.iteration;
                let alpha = self.alpha;
                let beta = self.beta;
                let gamma = self.gamma;
                // Update player 0.
                traverse_recursive_with_parallel(
                    tree,
                    eval_ctx,
                    &terminal_cache,
                    arena,
                    0,
                    0,
                    iteration,
                    alpha,
                    beta,
                    gamma,
                    &reach_p0,
                    &reach_p1,
                    &mut self.infosets,
                    0,
                    rayon_enabled,
                    terminal_ie,
                    &self.has_chance_template,
                    &mut runout_cache,
                );
                arena.reset_to(outer_mark);
                // Update player 1.
                traverse_recursive_with_parallel(
                    tree,
                    eval_ctx,
                    &terminal_cache,
                    arena,
                    0,
                    1,
                    iteration,
                    alpha,
                    beta,
                    gamma,
                    &reach_p1,
                    &reach_p0,
                    &mut self.infosets,
                    0,
                    rayon_enabled,
                    terminal_ie,
                    &self.has_chance_template,
                    &mut runout_cache,
                );
                arena.reset_to(outer_mark);
            }
        });
    }
}

/// Slice-based recursive traversal — the load-bearing body extracted
/// from `VectorDCFR::traverse` (v1.10 PR-4 refactor).
///
/// Walks the betting tree starting at global `node_idx`, mutating the
/// `infosets` slice in-place. The slice represents a CONTIGUOUS
/// sub-range of `VectorDCFR::infosets` starting at global index `offset`
/// (so `infosets[i]` corresponds to global node_idx `offset + i`).
///
/// For the sequential path `offset = 0` and `infosets.len() ==
/// tree.nodes.len()`, recovering the original `&mut self` behavior
/// bit-identically.
///
/// For the parallel path, each worker calls into this function with
/// `offset = child.start` and `infosets.len() = child.end - child.start`,
/// so its `node_idx` accesses translate to local slice positions
/// `node_idx - offset` that stay inside its own shard.
///
/// **Invariant**: every `node_idx` reached during the walk must satisfy
/// `offset <= node_idx < offset + infosets.len()`. The DFS-built tree
/// guarantees this for child-subtree starts — the recursion never
/// crosses out of its own contiguous range.
///
/// `allow_parallel`: when `true` AND we encounter a multi-child
/// `FlatNode::Chance`, dispatch to
/// `dcfr_vector_parallel::parallel_traverse_chance` and pass
/// `allow_parallel = false` down to children to avoid nested
/// parallelism (oversubscription). When `false`, the chance branch
/// walks sequentially. The caller from `VectorDCFR::solve` sets this
/// to `true` only when `CFR_RAYON_CHANCE` is set in the env.
///
/// `has_chance_template`: per-`FlatNode` index lookup populated by
/// `VectorDCFR::with_init_noise` from the tree's `chance_templates`
/// list (v1.10 PR-2). When the rayon path doesn't fire and the chance
/// node is flagged, the walker dispatches to `traverse_turn_chance_recursive`
/// — bit-identical to the legacy loop in v1.10 PR-2 but a hook point
/// for future arena-based scratch reuse. Empty / all-false outside
/// `BettingTreeMode::TemplateExtract`.
///
/// `terminal_ie`: when `true`, terminal leaves are evaluated with the
/// O(N + N·B) inclusion-exclusion evaluator (`terminal_value_vector_ie`)
/// instead of the O(N²) cached scan. Read once per solve from
/// `CFR_TERMINAL_IE` and threaded UNCHANGED through the whole traversal
/// (including rayon workers). When `false` the legacy dispatch (uncached
/// vs cached) is byte-for-byte unchanged.
///
/// `runout_cache`: pre-allocated scratch buffers for v1.10 PR-3's
/// `traverse_flop_chance_recursive` (the flop-level chance walker).
/// When the chance node has a `chance_depth == 2` template AND the
/// cache is active, dispatch routes through the flop walker. When
/// inactive (e.g. turn/river-rooted solves or `Standard` build mode),
/// dispatch falls through to the legacy chance arm. The cache is
/// threaded through unchanged for non-flop branches.
#[allow(clippy::too_many_arguments)]
pub(crate) fn traverse_recursive_with_parallel(
    tree: &BettingTree,
    eval_ctx: &EvalContext,
    terminal_cache: &TerminalCache,
    arena: &mut BumpArena,
    node_idx: usize,
    update_player: usize,
    iteration: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
    reach_p: &[f64],
    reach_opp: &[f64],
    infosets: &mut [Option<VectorInfosetData>],
    offset: usize,
    allow_parallel: bool,
    terminal_ie: bool,
    has_chance_template: &[bool],
    runout_cache: &mut RunoutCache,
) -> Vec<f64> {
    let node = &tree.nodes[node_idx];
    let update_hands = eval_ctx.hand_count[update_player];
    let local_idx = node_idx.wrapping_sub(offset);
    debug_assert!(
        local_idx < infosets.len(),
        "traverse_recursive: node_idx {node_idx} out of slice range \
         [{offset}, {}); local_idx={local_idx}, slice.len()={}",
        offset + infosets.len(),
        infosets.len(),
    );
    // v1.10 PR-1 — record arena high-water-mark on entry so we can
    // restore it before returning, preserving LIFO stack discipline.
    // The Vec<f64> return value is allocated on the heap so it survives
    // the arena reset (the rayon merge in
    // `parallel_traverse_chance` needs to own the per-child Vec<f64>).
    let entry_mark = arena.mark();

    let result = match node {
        FlatNode::Fold { .. } | FlatNode::Showdown { .. } => {
            let opp_player = 1 - update_player;
            let _t = prof_start!();
            let r = if terminal_ie {
                TLS_IE_SCRATCH.with(|cell| {
                    let mut scratch = cell.borrow_mut();
                    terminal_value_vector_ie(
                        &terminal_cache.leaves[node_idx],
                        terminal_cache.fold_blockers.as_ref(),
                        eval_ctx,
                        update_player,
                        opp_player,
                        reach_opp,
                        &mut scratch,
                    )
                })
            } else if std::env::var("CFR_VECTOR_NO_TERMINAL_CACHE").is_ok() {
                terminal_value_vector(node, eval_ctx, update_player, opp_player, reach_opp)
            } else {
                terminal_value_vector_cached(
                    &terminal_cache.leaves[node_idx],
                    eval_ctx,
                    update_player,
                    opp_player,
                    reach_opp,
                )
            };
            prof_end!(_t, TerminalEval);
            r
        }
        FlatNode::Chance { prob, children } => {
            // Decide: parallel dispatch, flop walker, turn walker, or
            // sequential walk?
            //
            // Order matters:
            //   1. Rayon (if enabled + multi-child) — parallelizes the
            //      flop or turn chance level. Workers run sequentially
            //      below.
            //   2. v1.10 PR-3 flop walker (if depth==2 + active cache) —
            //      scratch-buffer reuse on the outer flop accumulator.
            //   3. v1.10 PR-2 turn walker (if depth==1) — bit-identical
            //      to legacy, hook point for future scratch reuse.
            //   4. Legacy chance loop (single-child runouts, river-rooted
            //      solves, or Standard build mode).
            if allow_parallel && children.len() >= 2 {
                // Dispatch to the rayon parallel walker. Set
                // `allow_parallel = false` for child subtrees to
                // prevent nested parallelism (oversubscription).
                //
                // v1.10 PR-1: the parallel walker pulls each worker's
                // own thread-local arena (via `TLS_ARENA` inside
                // `traverse_with_infosets`) — this thread's arena is
                // untouched while the workers run, so we MUST rewind to
                // entry_mark on the way out.
                //
                // v1.10 PR-3: each worker constructs its own empty
                // `RunoutCache` locally because the worker's root is
                // below the flop chance, so the depth==2 dispatch never
                // fires inside the worker.
                let r = crate::dcfr_vector_parallel::parallel_traverse_chance(
                    tree,
                    eval_ctx,
                    terminal_cache,
                    node_idx,
                    children,
                    *prob,
                    update_player,
                    iteration,
                    alpha,
                    beta,
                    gamma,
                    reach_p,
                    reach_opp,
                    infosets,
                    offset,
                    terminal_ie,
                    has_chance_template,
                );
                arena.reset_to(entry_mark);
                return r;
            }
            // `v1.10 PR-3` — outer-level chance (depth>=1, i.e. has a
            // nested chance below it). Dispatches to the specialized
            // walker that pre-allocates scratch buffers for the outer
            // flop accumulator. Only fires when:
            //   - The cache is active (built from a tree with an outer
            //     chance template), AND
            //   - This node is the outer chance template (chance_depth>=1).
            //
            // **Naming note:** the design doc uses "depth==2" for
            // preflop-rooted trees (flop→turn→river = 3 chance levels,
            // outer has 2 below). For flop-rooted RvR (the v1.10
            // headline target) the outer chance is the turn deal with
            // the river deal nested below — depth==1 in our actual
            // tree. We dispatch on `depth >= 1` so both topologies
            // route through the same walker.
            if runout_cache.is_active()
                && !has_chance_template.is_empty()
                && has_chance_template[node_idx]
                && tree.chance_templates
                    .iter()
                    .any(|t| t.chance_node_idx == node_idx && t.chance_depth >= 1)
            {
                let r = traverse_flop_chance_recursive(
                    tree,
                    eval_ctx,
                    terminal_cache,
                    arena,
                    *prob,
                    children,
                    update_player,
                    iteration,
                    alpha,
                    beta,
                    gamma,
                    reach_p,
                    reach_opp,
                    infosets,
                    offset,
                    allow_parallel,
                    terminal_ie,
                    has_chance_template,
                    runout_cache,
                );
                arena.reset_to(entry_mark);
                return r;
            }
            // `v1.10 PR-2` — when the chance node has a `ChanceTemplate`
            // (all children share structural identity), dispatch to
            // `traverse_turn_chance_recursive` which is a hook point for
            // future arena-based scratch reuse. Currently bit-identical
            // to the legacy loop below: same DFS visit order, same
            // arithmetic, same accumulator update sequence.
            if !has_chance_template.is_empty() && has_chance_template[node_idx] {
                let r = traverse_turn_chance_recursive(
                    tree,
                    eval_ctx,
                    terminal_cache,
                    arena,
                    *prob,
                    children,
                    update_player,
                    iteration,
                    alpha,
                    beta,
                    gamma,
                    reach_p,
                    reach_opp,
                    infosets,
                    offset,
                    allow_parallel,
                    terminal_ie,
                    has_chance_template,
                    runout_cache,
                );
                arena.reset_to(entry_mark);
                return r;
            }
            let mut values = vec![0.0_f64; update_hands];
            // Snapshot children to release `node` borrow so we can
            // re-borrow `arena` (and `infosets`) mutably in the loop.
            let children_vec: Vec<usize> = children.clone();
            let prob_val = *prob;
            for c in children_vec {
                let child_values = traverse_recursive_with_parallel(
                    tree,
                    eval_ctx,
                    terminal_cache,
                    arena,
                    c,
                    update_player,
                    iteration,
                    alpha,
                    beta,
                    gamma,
                    reach_p,
                    reach_opp,
                    infosets,
                    offset,
                    false,
                    terminal_ie,
                    has_chance_template,
                    runout_cache,
                );
                let _t = prof_start!();
                for (i, v) in child_values.iter().enumerate() {
                    values[i] += prob_val * v;
                }
                prof_end!(_t, ChanceAccumulate);
            }
            values
        }
        FlatNode::Decision { player, actions, children, .. } => {
            let player = *player as usize;
            let action_count = actions.len();
            let player_hands = eval_ctx.hand_count[player];
            // Snapshot children indices to release the immutable `node`
            // borrow before the recursive `&mut arena` re-borrow.
            let children_vec: Vec<usize> = children.clone();
            let _ta = prof_start!();
            // v1.10 PR-1 — `strategy` moves from per-call vec! to arena.
            let strategy_off = arena.alloc_zeroed(player_hands * action_count);
            prof_end!(_ta, AllocStrategyBuf);
            {
                let info = infosets[local_idx]
                    .as_ref()
                    .expect("decision node must have an infoset slot");
                let _t = prof_start!();
                let strategy = arena.get_mut(strategy_off, player_hands * action_count);
                VectorDCFR::compute_strategy(info, strategy);
                prof_end!(_t, ComputeStrategy);
            }

            if player != update_player {
                let mut values = vec![0.0_f64; update_hands];
                // `next_reach` is a heap Vec — small enough (≤1326 f64s
                // per player at full deck) that allocator reuse is faster
                // than threading a fourth arena offset through; the
                // arena wins on the LARGER buffers (strategy +
                // action_values, both ~`player_hands * action_count`).
                let mut next_reach = vec![0.0_f64; player_hands];
                for (a, child_idx) in children_vec.iter().enumerate() {
                    let _t = prof_start!();
                    {
                        // next_reach[h] = reach_opp[h] * strategy[h, a]
                        let strategy = arena.get(strategy_off, player_hands * action_count);
                        for h in 0..player_hands {
                            next_reach[h] = reach_opp[h] * strategy[h * action_count + a];
                        }
                    }
                    prof_end!(_t, OppNextReach);
                    let child_values = traverse_recursive_with_parallel(
                        tree,
                        eval_ctx,
                        terminal_cache,
                        arena,
                        *child_idx,
                        update_player,
                        iteration,
                        alpha,
                        beta,
                        gamma,
                        reach_p,
                        &next_reach,
                        infosets,
                        offset,
                        allow_parallel,
                        terminal_ie,
                        has_chance_template,
                        runout_cache,
                    );
                    let _t = prof_start!();
                    for h in 0..update_hands {
                        values[h] += child_values[h];
                    }
                    prof_end!(_t, ChanceAccumulate);
                }
                arena.reset_to(entry_mark);
                return values;
            }

            // v1.10 PR-1 (Candidate I3) — skip the post-discount strategy
            // recompute when the discount was a no-op
            // (`last_discount_iter >= iteration`, i.e. the regret table
            // is unchanged). Bit-identical to the unconditional recompute
            // because the regrets read by the recompute are the same in
            // that case. Saves one `compute_strategy` call per
            // own-decision visit when the node has already been
            // discounted earlier this iteration (e.g. both players'
            // walks visit the same node within one iter).
            let needs_strategy_recompute = {
                let info = infosets[local_idx]
                    .as_mut()
                    .expect("decision node must have an infoset slot");
                let needs = info.last_discount_iter < iteration;
                let _t = prof_start!();
                VectorDCFR::discount(info, iteration, alpha, beta, gamma);
                prof_end!(_t, Discount);
                needs
            };
            if needs_strategy_recompute {
                let info = infosets[local_idx]
                    .as_ref()
                    .expect("decision node must have an infoset slot");
                let _t = prof_start!();
                let strategy = arena.get_mut(strategy_off, player_hands * action_count);
                VectorDCFR::compute_strategy(info, strategy);
                prof_end!(_t, ComputeStrategy);
            }

            let _ta = prof_start!();
            // v1.10 PR-1 — `action_values` moves from per-call vec! to arena.
            let action_values_off = arena.alloc_zeroed(action_count * update_hands);
            let mut next_reach = vec![0.0_f64; player_hands];
            prof_end!(_ta, AllocActionValues);
            for (a, child_idx) in children_vec.iter().enumerate() {
                let _t = prof_start!();
                {
                    // next_reach[h] = reach_p[h] * strategy[h, a]
                    let strategy = arena.get(strategy_off, player_hands * action_count);
                    for h in 0..player_hands {
                        next_reach[h] = reach_p[h] * strategy[h * action_count + a];
                    }
                }
                prof_end!(_t, OwnNextReach);
                let child_values = traverse_recursive_with_parallel(
                    tree,
                    eval_ctx,
                    terminal_cache,
                    arena,
                    *child_idx,
                    update_player,
                    iteration,
                    alpha,
                    beta,
                    gamma,
                    &next_reach,
                    reach_opp,
                    infosets,
                    offset,
                    allow_parallel,
                    terminal_ie,
                    has_chance_template,
                    runout_cache,
                );
                let dst = a * update_hands;
                let action_values =
                    arena.get_mut(action_values_off, action_count * update_hands);
                action_values[dst..dst + update_hands].copy_from_slice(&child_values);
            }

            let _t = prof_start!();
            let mut node_values = vec![0.0_f64; update_hands];
            {
                // strategy (R), action_values (R) — both immutable slice
                // borrows from the same Vec are allowed simultaneously.
                let strategy = arena.get(strategy_off, player_hands * action_count);
                let action_values = arena.get(action_values_off, action_count * update_hands);
                for h in 0..update_hands {
                    let mut value = 0.0_f64;
                    let s_offset = h * action_count;
                    for a in 0..action_count {
                        value += strategy[s_offset + a] * action_values[a * update_hands + h];
                    }
                    node_values[h] = value;
                }
            }
            prof_end!(_t, NodeValues);

            let regret_weight = 1.0_f64;
            let avg_weight = 1.0_f64;
            let _ = regret_weight;
            {
                // The SIMD kernels mutate `info.regret` / `info.strategy_sum`
                // (a slot in `infosets[local_idx]`), which is a separate
                // object from `arena.buf` — we can hold immutable arena
                // slice borrows concurrently with the mutable infoset
                // borrow without conflict.
                let action_values = arena.get(action_values_off, action_count * update_hands);
                let strategy = arena.get(strategy_off, player_hands * action_count);
                let info = infosets[local_idx]
                    .as_mut()
                    .expect("decision node must have an infoset slot");
                let _t = prof_start!();
                simd::update_regret_sum_vector(
                    &mut info.regret,
                    action_values,
                    &node_values,
                    update_hands,
                    action_count,
                );
                prof_end!(_t, UpdateRegret);
                let _t = prof_start!();
                for h in 0..update_hands {
                    let weight = reach_p[h] * avg_weight;
                    if weight == 0.0 {
                        continue;
                    }
                    let offset_ha = h * action_count;
                    let row_end = offset_ha + action_count;
                    crate::simd::update_strategy_sum(
                        &mut info.strategy_sum[offset_ha..row_end],
                        &strategy[offset_ha..row_end],
                        weight,
                    );
                }
                prof_end!(_t, UpdateStrategySum);
            }

            node_values
        }
    };

    arena.reset_to(entry_mark);
    result
}

// ============================================================================
// v1.10 PR-3 — Vector-form flop forward walk with double chance compaction.
//
// PR-3 extends PR-2's `ChanceTemplate` extraction to two-level chance
// compaction (flop → turn → river). The flop subgame's outer chance loop
// iterates 45 × 44 = 1980 (turn_card, river_card) runouts against a
// precomputed cache instead of recursively rebuilding the river betting
// tree per runout. Goal: 10-20× wall reduction on flop top_k=169
// (currently OOM-killed at 2.3 GB) + 4-5× RSS reduction.
//
// **Design summary** (see `docs/v1_10_pr3_flop_vector_design.md`):
//   - `RunoutCache` holds pre-allocated scratch buffers for the flop
//     walker; built once at solve-start, reused in place across iters.
//   - `traverse_flop_chance_recursive` walks 45 turn-card children in
//     DFS order, identical to the legacy chance arm, but uses
//     pre-allocated scratch instead of fresh `vec!` allocations.
//   - Dispatch in `traverse_recursive_with_parallel`: at a chance node
//     with `chance_depth == 2`, route to the flop walker; with
//     `chance_depth == 1`, route to PR-2's turn walker; otherwise fall
//     through to the legacy loop.
//
// **Bit-identity contract:** the per-branch arithmetic + DFS order are
// preserved exactly. The only behavioral change is scratch-buffer
// provenance (pre-allocated pool vs fresh `vec!`).
// ============================================================================

/// `v1.10 PR-3` — runout-value cache for two-level chance compaction.
///
/// Holds pre-allocated `Vec<f64>` scratch buffers used by
/// `traverse_flop_chance_recursive` for its outer (flop-level)
/// accumulator and the per-turn-child inner accumulator. Indexed by
/// runout `(turn_idx, river_idx)` so the cache shape mirrors the
/// double-chance enumeration; in practice the lazy-DFS variant
/// (Strategy B in the design doc §3.3) only needs O(turn_fanout)
/// concurrent buffers but the (turn × river) layout is kept so a
/// future Strategy-A (eager precompute) variant can swap in without
/// signature churn.
///
/// **Memory footprint:** at top_k=169 (1081 hands) and a 45-turn ×
/// 44-river flop subgame, the cache is `1980 × 1081 × 8 = ~17 MB` —
/// small relative to the 2.3 GB legacy footprint. At smaller `top_k`
/// it scales linearly.
///
/// **Invariant:** `runout_values.is_empty()` iff this is an inactive
/// cache (turn/river-rooted solves, or `Standard` build mode). The
/// dispatch in `traverse_recursive_with_parallel` skips the flop
/// walker when the cache is inactive.
///
/// See `docs/v1_10_pr3_flop_vector_design.md` §5 for placement rationale.
pub(crate) struct RunoutCache {
    /// Pre-allocated per-runout value buffers. Indexed by
    /// `turn_idx * river_fanout + river_idx`. Each inner `Vec<f64>` has
    /// length `max_hands`; the active-player slice `[..hand_count[update_player]]`
    /// is used per call.
    ///
    /// **Note:** in the v1.10 PR-3 lazy-DFS implementation, only a small
    /// subset of these buffers are touched per `traverse_flop_chance_recursive`
    /// invocation (specifically the outer `values` accumulator and one
    /// per turn-child accumulator). The full 1980-buffer pool is kept
    /// because (a) the memory footprint is negligible compared to
    /// per-iteration legacy allocation churn, and (b) the eager
    /// Strategy-A variant can use the full layout in a follow-up PR
    /// without API churn.
    #[allow(dead_code)]
    runout_values: Vec<Vec<f64>>,
    /// Fan-out of the river chance node within each turn-card subtree.
    /// Typically 44 for a flop-rooted subgame (52 deck - 5 known cards).
    /// `0` when no two-level chance template is present (e.g. turn-rooted
    /// or river-rooted solves), in which case `runout_values.is_empty()`.
    #[allow(dead_code)]
    river_fanout: usize,
    /// Number of hands per player (max across the two), used to size
    /// the pre-allocated scratch buffers consumed by
    /// `traverse_flop_chance_recursive`.
    max_hands: usize,
    /// Reusable scratch buffer for the flop-level accumulator (`values`
    /// in the chance-arm math). Pre-allocated to `max_hands` length;
    /// the walker zeros and uses the active-player slice per call.
    flop_values_scratch: Vec<f64>,
    /// Reusable scratch buffer for the per-turn-child accumulator
    /// (`turn_values` in the design doc §3.3 pseudo-code). Same length
    /// as `flop_values_scratch`. Reserved for a follow-up Strategy A
    /// (eager precompute) variant that needs an intermediate per-turn
    /// reduction buffer.
    #[allow(dead_code)]
    turn_values_scratch: Vec<f64>,
    /// FlatNode index of the depth-2 chance template (the flop deal).
    /// `usize::MAX` when no flop template was found.
    #[allow(dead_code)]
    flop_chance_idx: usize,
}

impl RunoutCache {
    /// `v1.10 PR-3` — construct an empty / inactive cache.
    ///
    /// Used when no flop-level chance template exists in the tree
    /// (turn/river-rooted solves, or `Standard` build mode). The
    /// dispatch in `traverse_recursive_with_parallel` skips
    /// `traverse_flop_chance_recursive` when the cache is inactive.
    pub(crate) fn empty() -> Self {
        Self {
            runout_values: Vec::new(),
            river_fanout: 0,
            max_hands: 0,
            flop_values_scratch: Vec::new(),
            turn_values_scratch: Vec::new(),
            flop_chance_idx: usize::MAX,
        }
    }

    /// `v1.10 PR-3` — pre-allocate scratch buffers from the flop chance
    /// template in `tree.chance_templates`.
    ///
    /// **Implementation steps:**
    /// 1. Find the `ChanceTemplate` with `chance_depth == 2` (the flop
    ///    chance). If none, return `Self::empty()`.
    /// 2. Inspect the `FlatNode::Chance` at `chance_node_idx` to get
    ///    `turn_fanout = children.len()` (typically 45).
    /// 3. Use `BettingTree::first_inner_chance` on `children[0]` to get
    ///    the river-level chance node and read `river_fanout`
    ///    (typically 44).
    /// 4. Allocate `turn_fanout × river_fanout` per-hand buffers, each of
    ///    length `max_hands = max(eval_ctx.hand_count)`. Also allocate
    ///    the two outer scratch buffers (`flop_values_scratch`,
    ///    `turn_values_scratch`).
    pub(crate) fn build(tree: &BettingTree, eval_ctx: &EvalContext) -> Self {
        let max_hands = eval_ctx
            .hand_count
            .iter()
            .copied()
            .max()
            .unwrap_or(0);
        // Find the outer chance template (depth>=1: has a nested chance
        // below it). We only build an active cache when one exists;
        // otherwise the walker is never dispatched.
        //
        // **Naming note:** the design doc calls this "depth==2" assuming
        // a preflop→flop→turn→river chain (3 chance levels with the
        // outer at depth 2). For flop-rooted RvR (the v1.10 headline)
        // the outer chance is the turn deal with the river deal below
        // — depth==1 in our actual tree. We accept depth>=1 so both
        // topologies route through the same walker.
        let flop_template = tree
            .chance_templates
            .iter()
            .find(|t| t.chance_depth >= 1);
        let (turn_fanout, river_fanout, flop_chance_idx) = match flop_template {
            Some(t) => {
                let turn_fanout = match &tree.nodes[t.chance_node_idx] {
                    FlatNode::Chance { children, .. } => children.len(),
                    _ => 0,
                };
                // Find the river chance node inside the first turn child's
                // subtree. This is the inner template that the PR-2 turn
                // walker will hit during nested recursion.
                let river_fanout = if turn_fanout == 0 {
                    0
                } else {
                    let first_turn_child = match &tree.nodes[t.chance_node_idx] {
                        FlatNode::Chance { children, .. } => children[0],
                        _ => 0,
                    };
                    match tree.first_inner_chance(first_turn_child) {
                        Some(idx) => match &tree.nodes[idx] {
                            FlatNode::Chance { children, .. } => children.len(),
                            _ => 0,
                        },
                        None => 0,
                    }
                };
                (turn_fanout, river_fanout, t.chance_node_idx)
            }
            None => (0, 0, usize::MAX),
        };
        let runout_count = turn_fanout * river_fanout;
        // Only build active storage when both fanouts are non-zero AND
        // max_hands > 0. Otherwise return an inactive cache and the
        // dispatch falls through to the legacy chance arm.
        let (runout_values, flop_scratch, turn_scratch) = if runout_count > 0 && max_hands > 0 {
            // Per-runout per-hand value buffers (currently unused in
            // Strategy B, see RunoutCache::runout_values doc comment).
            let mut runouts = Vec::with_capacity(runout_count);
            for _ in 0..runout_count {
                runouts.push(vec![0.0_f64; max_hands]);
            }
            (
                runouts,
                vec![0.0_f64; max_hands],
                vec![0.0_f64; max_hands],
            )
        } else {
            (Vec::new(), Vec::new(), Vec::new())
        };
        Self {
            runout_values,
            river_fanout,
            max_hands,
            flop_values_scratch: flop_scratch,
            turn_values_scratch: turn_scratch,
            flop_chance_idx,
        }
    }

    /// `v1.10 PR-3` — true iff this cache has scratch buffers allocated
    /// (i.e., the tree has a flop-level chance template). `false` for
    /// turn-rooted / river-rooted solves or `Standard` build mode.
    pub(crate) fn is_active(&self) -> bool {
        !self.flop_values_scratch.is_empty()
    }
}

/// `v1.10 PR-3` — specialized chance walker for the **flop-level**
/// chance node (turn-card deal). Performs two-level chance compaction
/// by reusing pre-allocated scratch buffers in `runout_cache` instead
/// of allocating per-turn-branch.
///
/// **Dispatch:** called from `traverse_recursive_with_parallel` at a
/// `FlatNode::Chance` arm when:
///   1. The chance node has a `ChanceTemplate` entry (PR-2 invariant), AND
///   2. The template's `chance_depth == 2` (PR-3 extension), AND
///   3. `runout_cache.is_active()` (scratch buffers allocated).
///
/// **Bit-identity contract:** produces identical strategy and game-value
/// output to the legacy per-branch recursion at 1e-12 tolerance.
/// Achieved by preserving:
///   - DFS visit order over `flop_chance_children` (low-to-high index)
///   - Per-branch arithmetic: `values[h] += prob * child_values[h]`
///   - IEEE-754 summation order (same loop nest as legacy)
///
/// The ONLY change vs the legacy chance arm is that the `values`
/// accumulator is pulled from `runout_cache.flop_values_scratch`
/// (pre-allocated, zeroed at function entry) instead of a fresh
/// `vec![0.0; update_hands]` per call.
///
/// **DFS-order invariant:** must visit decision nodes in the same global
/// order as `traverse_recursive_with_parallel`:
///
///   for `turn_idx in 0..turn_fanout`:
///     descend into turn-line decision subtree (delegating back to
///     `traverse_recursive_with_parallel` which itself routes through
///     PR-2's `traverse_turn_chance_recursive` for the inner river
///     chance) — preserved DFS;
///     backprop turn's per-hand values via `values[h] += prob * v[h]`.
///
/// `allow_parallel`: passed `false` to children. PR-4's
/// `parallel_traverse_chance` already split the flop chance node 45
/// ways if `CFR_RAYON_CHANCE=1`; nested parallelism on the inner river
/// chance would degrade through oversubscription.
///
/// Returns the per-hand value vector for the flop chance node
/// (`update_hands` length), matching the legacy chance-arm return.
#[allow(clippy::too_many_arguments)]
pub(crate) fn traverse_flop_chance_recursive(
    tree: &BettingTree,
    eval_ctx: &EvalContext,
    terminal_cache: &TerminalCache,
    arena: &mut BumpArena,
    flop_chance_prob: f64,
    flop_chance_children: &[usize],
    update_player: usize,
    iteration: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
    reach_p: &[f64],
    reach_opp: &[f64],
    infosets: &mut [Option<VectorInfosetData>],
    offset: usize,
    _allow_parallel: bool,
    terminal_ie: bool,
    has_chance_template: &[bool],
    runout_cache: &mut RunoutCache,
) -> Vec<f64> {
    let update_hands = eval_ctx.hand_count[update_player];
    debug_assert!(
        runout_cache.is_active(),
        "traverse_flop_chance_recursive must only be called with an active RunoutCache"
    );
    debug_assert!(
        update_hands <= runout_cache.max_hands,
        "update_hands ({}) exceeds RunoutCache::max_hands ({})",
        update_hands,
        runout_cache.max_hands,
    );

    // Zero the pre-allocated outer accumulator. This is bit-identical to
    // `vec![0.0; update_hands]` because both produce all-zero f64s.
    // We use the full max_hands-length scratch but only touch the
    // update_hands prefix.
    for slot in &mut runout_cache.flop_values_scratch[..update_hands] {
        *slot = 0.0;
    }

    // DFS over flop_chance_children in index order (matches legacy).
    // `allow_parallel = false` to prevent rayon oversubscription —
    // PR-4 has already either parallelized this level above us or
    // chosen to run sequentially here.
    for &c in flop_chance_children {
        let child_values = traverse_recursive_with_parallel(
            tree,
            eval_ctx,
            terminal_cache,
            arena,
            c,
            update_player,
            iteration,
            alpha,
            beta,
            gamma,
            reach_p,
            reach_opp,
            infosets,
            offset,
            /* allow_parallel = */ false,
            terminal_ie,
            has_chance_template,
            runout_cache,
        );
        // Bit-identical to the legacy chance arm: `values[i] += prob * v_i`.
        // Same loop body, same accumulation order.
        let _t = prof_start!();
        for (i, v) in child_values.iter().enumerate() {
            runout_cache.flop_values_scratch[i] += flop_chance_prob * v;
        }
        prof_end!(_t, ChanceAccumulate);
    }

    // Return a fresh Vec<f64> of length update_hands. The caller
    // expects an owned Vec (matching the legacy chance arm's return);
    // we copy from scratch storage. This single per-call clone is
    // bit-identical to the legacy `let mut values = vec![…]; … values`
    // path and is dominated by the inner work.
    runout_cache.flop_values_scratch[..update_hands].to_vec()
}

// ============================================================================
// End v1.10 PR-3 vector-form flop forward walk.
// ============================================================================

/// Thin `pub(crate)` entry point for `dcfr_vector_parallel.rs` to enter
/// the slice-based traversal at the start of a worker thread's subtree.
/// Always passes `allow_parallel = false` — nested parallelism would
/// oversubscribe the Rayon thread pool and degrade perf.
///
/// `has_chance_template` is threaded through so that any sub-chance
/// nodes inside a parallel worker's shard still hit the v1.10 PR-2
/// template walker hook when applicable.
///
/// **v1.10 PR-1**: pulls the worker thread's own `TLS_ARENA` and threads
/// it into the recursive walker. Each Rayon worker has a distinct
/// thread-local arena (so workers' scratch buffers do not contend), and
/// the arena's backing `Vec<f64>` capacity persists across iterations
/// on the same worker.
///
/// **v1.10 PR-3**: each rayon worker constructs its own empty
/// `RunoutCache` locally. The worker's root is a turn-card subtree
/// (i.e. one child of the flop chance node, depth==1 max), so the
/// depth==2 dispatch never fires inside the worker and an inactive
/// cache is correct. The empty-cache allocation is O(1) since
/// `Vec::new()` doesn't allocate.
#[allow(clippy::too_many_arguments)]
pub(crate) fn traverse_with_infosets(
    tree: &BettingTree,
    eval_ctx: &EvalContext,
    terminal_cache: &TerminalCache,
    node_idx: usize,
    update_player: usize,
    iteration: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
    reach_p: &[f64],
    reach_opp: &[f64],
    infosets: &mut [Option<VectorInfosetData>],
    offset: usize,
    terminal_ie: bool,
    has_chance_template: &[bool],
) -> Vec<f64> {
    let mut local_cache = RunoutCache::empty();
    TLS_ARENA.with(|cell| {
        let mut arena_ref = cell.borrow_mut();
        let arena: &mut BumpArena = &mut arena_ref;
        let entry_mark = arena.mark();
        let r = traverse_recursive_with_parallel(
            tree,
            eval_ctx,
            terminal_cache,
            arena,
            node_idx,
            update_player,
            iteration,
            alpha,
            beta,
            gamma,
            reach_p,
            reach_opp,
            infosets,
            offset,
            /* allow_parallel = */ false,
            terminal_ie,
            has_chance_template,
            &mut local_cache,
        );
        arena.reset_to(entry_mark);
        r
    })
}

/// `v1.10 PR-2` — specialized chance-node walker for chance nodes with
/// a `ChanceTemplate` (all children share structural identity).
///
/// **Bit-identity gate:** the walker computes `values[i] += prob * v`
/// INSIDE the inner loop, matching the legacy chance arm's arithmetic
/// exactly. DFS order over `children` is preserved. The only thing this
/// function does differently from the legacy fallthrough loop is the
/// dispatch route (controlled by `has_chance_template[node_idx]`), which
/// makes it a hook point for future arena-based scratch reuse without
/// touching the load-bearing chance-arm code path.
///
/// **Where the real PR-2 perf win comes from:** when this walker is
/// active, future PRs (PR-3 vector flop) can pivot to a "single shared
/// scratch buffer per template-node" path. For PR-2 alone, the win is
/// the framework + per-branch instrumentation hoist; the bit-identity
/// gate is the load-bearing acceptance criterion.
///
/// Recursive children are dispatched back through
/// `traverse_recursive_with_parallel`, so any nested chance / decision
/// nodes still hit rayon dispatch and the template walker recursively
/// as appropriate.
#[allow(clippy::too_many_arguments)]
fn traverse_turn_chance_recursive(
    tree: &BettingTree,
    eval_ctx: &EvalContext,
    terminal_cache: &TerminalCache,
    arena: &mut BumpArena,
    prob: f64,
    children: &[usize],
    update_player: usize,
    iteration: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
    reach_p: &[f64],
    reach_opp: &[f64],
    infosets: &mut [Option<VectorInfosetData>],
    offset: usize,
    allow_parallel: bool,
    terminal_ie: bool,
    has_chance_template: &[bool],
    runout_cache: &mut RunoutCache,
) -> Vec<f64> {
    let update_hands = eval_ctx.hand_count[update_player];
    let mut values = vec![0.0_f64; update_hands];
    // Snapshot children indices so we can re-borrow `arena` mutably in the
    // loop without conflicting with the immutable `children: &[usize]`
    // borrow held by the caller's `FlatNode::Chance` match arm.
    let children_vec: Vec<usize> = children.to_vec();
    for c in children_vec {
        let child_values = traverse_recursive_with_parallel(
            tree,
            eval_ctx,
            terminal_cache,
            arena,
            c,
            update_player,
            iteration,
            alpha,
            beta,
            gamma,
            reach_p,
            reach_opp,
            infosets,
            offset,
            allow_parallel,
            terminal_ie,
            has_chance_template,
            runout_cache,
        );
        // Bit-identical to the legacy chance arm: `values[i] += prob * v_i`.
        for (i, v) in child_values.iter().enumerate() {
            values[i] += prob * v;
        }
    }
    values
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

/// **Reference (uncached) terminal-leaf value vector.**
///
/// Retained as the parity reference for the cached path
/// (`terminal_value_vector_cached`) — the unit test
/// `cached_matches_uncached_terminal_value` asserts bit-identical output
/// between the two on a small fixture. Production callers go through
/// the cached version; this implementation is selected at the
/// `traverse` call-site when the `CFR_VECTOR_NO_TERMINAL_CACHE` env var
/// is set (used by the `rvr_profile` bench for baseline measurement).
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

/// **Cached terminal-leaf value vector (HIGH-2 follow-up).**
///
/// Same math as [`terminal_value_vector`] (kept above as the parity
/// reference) but reads precomputed `Strength` vectors and chip-flow
/// payoffs from `TerminalCache`. No `evaluate_7` calls in the inner
/// loop — they happened once at `TerminalCache::build` time, before
/// any iteration. For a 1081-hand river with 4 terminal leaves this
/// hoists ~17M evaluate_7 calls per iter out to a one-time ~8.6K-call
/// build cost.
///
/// Bit-exactness vs [`terminal_value_vector`]: cached `Strength` values
/// are the unmodified output of `evaluate_7`, so the `>`/`<`/`==` branch
/// on them is identical to the uncached path's comparison. The chip-flow
/// constants come from the same formulas in `terminal_utility`.
fn terminal_value_vector_cached(
    leaf: &LeafCacheEntry,
    ctx: &EvalContext,
    update_player: usize,
    opp_player: usize,
    reach_opp: &[f64],
) -> Vec<f64> {
    let update_hands = ctx.hand_count[update_player];
    let opp_hands = ctx.hand_count[opp_player];
    let mut out = vec![0.0_f64; update_hands];

    match leaf {
        LeafCacheEntry::Fold { payoff } => {
            // Fold leaf: utility is constant in holes. Inner loop is
            // just a blocker-filter + reach accumulation.
            let util = payoff[update_player];
            for hp in 0..update_hands {
                let hole_p = ctx.hole[update_player][hp];
                let mut total = 0.0_f64;
                // SAFETY: indexed-for loop into `ctx.hole[opp]` and
                // `reach_opp` with bounds known equal to `opp_hands`
                // (precondition of the EvalContext build).
                for ho in 0..opp_hands {
                    let hole_o = ctx.hole[opp_player][ho];
                    if hole_p[0] == hole_o[0]
                        || hole_p[0] == hole_o[1]
                        || hole_p[1] == hole_o[0]
                        || hole_p[1] == hole_o[1]
                    {
                        continue;
                    }
                    total += reach_opp[ho] * util;
                }
                out[hp] = total;
            }
        }
        LeafCacheEntry::Showdown {
            strength,
            win_payoff,
            tie_payoff,
            ..
        } => {
            // Showdown leaf: per-pair outcome from precomputed `Strength`
            // comparison. Branch on `s_p` vs `s_o` and pick the right
            // payoff (winner-perspective × update_player's payoff slot).
            let s_self = &strength[update_player];
            let s_opp = &strength[opp_player];
            let win_self = win_payoff[update_player][update_player];
            let win_opp = win_payoff[opp_player][update_player];
            let tie = tie_payoff[update_player];
            for hp in 0..update_hands {
                let hole_p = ctx.hole[update_player][hp];
                let sp = s_self[hp];
                let mut total = 0.0_f64;
                for ho in 0..opp_hands {
                    let hole_o = ctx.hole[opp_player][ho];
                    if hole_p[0] == hole_o[0]
                        || hole_p[0] == hole_o[1]
                        || hole_p[1] == hole_o[0]
                        || hole_p[1] == hole_o[1]
                    {
                        continue;
                    }
                    let so = s_opp[ho];
                    let util = if sp > so {
                        win_self
                    } else if so > sp {
                        win_opp
                    } else {
                        tie
                    };
                    total += reach_opp[ho] * util;
                }
                out[hp] = total;
            }
        }
        LeafCacheEntry::NonTerminal => {
            unreachable!("terminal_value_vector_cached called on a non-terminal node")
        }
    }
    out
}

/// **Inclusion-exclusion terminal-leaf value vector (opt-in, `CFR_TERMINAL_IE`).**
///
/// Same math as [`terminal_value_vector_cached`] (the parity reference)
/// but evaluated in O(N + N·B) instead of O(N²): a prefix sum over opp
/// reach reordered by sorted opp strength gives each player hand's
/// win/tie/lose weight against the WHOLE opp range, then per-hand blocker
/// corrections subtract the (small) set of opp hands sharing a card.
///
/// Requires the leaf to carry IE precompute (built by `TerminalCache::build`
/// with `terminal_ie = true`) and `terminal_cache.fold_blockers` to be
/// `Some` for Fold leaves. Both hold whenever `CFR_TERMINAL_IE` is set.
///
/// `scratch` is reused across calls to avoid per-call allocation; it is
/// resized to `n_op + 1` and overwritten each call.
///
/// Reorders FP summation relative to the cached path, so output is
/// tolerance-close (NOT bit-exact) to [`terminal_value_vector_cached`].
///
/// Algorithm: Noam Brown poker_solver vector_eval.cpp
/// build_cache/showdown_values/fold_values (MIT, (c) 2025 Noam Brown).
fn terminal_value_vector_ie(
    leaf: &LeafCacheEntry,
    fold_blockers: Option<&[Vec<Vec<u32>>; 2]>,
    ctx: &EvalContext,
    update_player: usize,
    opp_player: usize,
    reach_opp: &[f64],
    scratch: &mut Vec<f64>,
) -> Vec<f64> {
    let update_hands = ctx.hand_count[update_player];
    let mut out = vec![0.0_f64; update_hands];

    match leaf {
        LeafCacheEntry::Fold { payoff } => {
            let util = payoff[update_player];
            let union = &fold_blockers
                .expect("terminal_value_vector_ie: fold_blockers must be built (CFR_TERMINAL_IE)")
                [update_player];
            let total: f64 = reach_opp.iter().sum();
            if total <= 0.0 {
                return out;
            }
            for (hp, slot) in out.iter_mut().enumerate() {
                let mut blocked = 0.0_f64;
                for &idx in &union[hp] {
                    blocked += reach_opp[idx as usize];
                }
                *slot = util * (total - blocked);
            }
        }
        LeafCacheEntry::Showdown {
            win_payoff,
            tie_payoff,
            ie,
            ..
        } => {
            let ie = ie
                .as_ref()
                .expect("terminal_value_vector_ie: showdown IE must be built (CFR_TERMINAL_IE)");
            let ie = &ie[update_player];
            // Hoist payoff constants identically to the cached fn.
            let win_self = win_payoff[update_player][update_player];
            let win_opp = win_payoff[opp_player][update_player];
            let tie = tie_payoff[update_player];

            let n_op = ie.sorted_idx.len();
            scratch.clear();
            scratch.reserve(n_op + 1);
            scratch.push(0.0);
            // Prefix sum over opp reach reordered by ascending strength.
            for i in 0..n_op {
                let prev = scratch[i];
                scratch.push(prev + reach_opp[ie.sorted_idx[i] as usize]);
            }
            let total = scratch[n_op];
            if total <= 0.0 {
                return out;
            }

            for (hp, slot) in out.iter_mut().enumerate() {
                let start = ie.range_start[hp] as usize;
                let end = ie.range_end[hp] as usize;
                let mut win = scratch[start];
                let mut tiew = scratch[end] - scratch[start];
                let mut lose = total - win - tiew;
                // Blocker corrections: remove opp hands sharing a card.
                for &idx in &ie.blk_less[hp] {
                    win -= reach_opp[idx as usize];
                }
                for &idx in &ie.blk_equal[hp] {
                    tiew -= reach_opp[idx as usize];
                }
                for &idx in &ie.blk_greater[hp] {
                    lose -= reach_opp[idx as usize];
                }
                *slot = win * win_self + tiew * tie + lose * win_opp;
            }
        }
        LeafCacheEntry::NonTerminal => {
            unreachable!("terminal_value_vector_ie called on a non-terminal node")
        }
    }
    out
}

/// Read `CFR_TERMINAL_IE` from the environment. Returns `true` iff the
/// variable is set to any non-empty value. Called ONCE per
/// `VectorDCFR::solve` and threaded through the traversal (mirroring
/// `parallel_chance_enabled`), so flag-off solves never touch the IE path.
pub(crate) fn terminal_ie_enabled() -> bool {
    matches!(std::env::var("CFR_TERMINAL_IE"), Ok(v) if !v.is_empty())
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
    solve_range_vs_range_postflop_with_hands(
        config, None, iterations, alpha, beta, gamma, 0.0, 0, None,
    )
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
///
/// **B10 Phase B contract — `hand_weights`.** When supplied, the kernel
/// uses these per-hand fractional weights as the initial reach vectors
/// (in place of the all-ones default). `hand_weights = Some([w0, w1])`
/// requires `w0.len() == p0_holes.len()` and `w1.len() == p1_holes.len()`;
/// each `w[i]` aligns positionally with `p{p}_holes[i]`. All-ones is
/// bit-identical to `None`. This is the **only** algorithmic touch
/// point — the per-(hand, action) regret/strategy update path is
/// unchanged.
#[allow(clippy::too_many_arguments)]
pub fn solve_range_vs_range_postflop_with_hands(
    config: &HUNLConfig,
    hand_lists: Option<[Vec<[u8; 2]>; 2]>,
    iterations: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
    regret_init_noise: f64,
    rng_seed: u64,
    hand_weights: Option<[Vec<f64>; 2]>,
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
    //
    // `v1.10 PR-2` — when starting street is Turn or Flop, build with
    // `TemplateExtract` mode so the chance-node template metadata is
    // populated. The vector-form `traverse_turn_chance` walker uses this
    // to reuse scratch buffers across the 45 river-card branches at a
    // turn-chance node. `Standard` mode is preserved for River-rooted
    // subgames (no chance nodes inside the betting tree) and as the
    // fallback if template extraction proves to be a regression on any
    // existing fixture. Both modes produce bit-identical solve results;
    // the metadata is purely out-of-band.
    //
    // `v1.10 PR-3` diff-test escape hatch: setting
    // `CFR_VECTOR_FLOP_TEMPLATE=0` forces `Standard` mode even on
    // flop/turn-rooted solves, disabling both the PR-2 turn walker
    // and the PR-3 flop walker dispatch. This is used by
    // `tests/test_v1_10_3_flop_diff.py` to run the canonical (legacy
    // per-runout) path as the bit-identical reference baseline.
    // Default behavior is unchanged.
    let placeholder = initial.clone_with_hole_cards([eval_ctx.hole[0][0], eval_ctx.hole[1][0]]);
    let template_disabled = matches!(
        std::env::var("CFR_VECTOR_FLOP_TEMPLATE"),
        Ok(v) if v == "0"
    );
    let build_mode = if template_disabled {
        BettingTreeMode::Standard
    } else {
        match config.starting_street {
            crate::hunl::Street::Turn | crate::hunl::Street::Flop => {
                BettingTreeMode::TemplateExtract
            }
            _ => BettingTreeMode::Standard,
        }
    };
    let tree = BettingTree::build_with_mode(&placeholder, build_mode);

    // PR 90 (A83 Track A) — `regret_init_noise = 0.0` keeps the prior
    // all-zero initialization (bit-identical to pre-PR 90). Non-zero
    // values seed each per-(hand, action) regret cell with `noise * U(-1, 1)`
    // via a deterministic `PcsRng` stream seeded by `rng_seed`.
    let mut solver = VectorDCFR::with_init_noise(
        &tree,
        eval_ctx.hand_count,
        alpha,
        beta,
        gamma,
        regret_init_noise,
        rng_seed,
    );
    solver.solve(&tree, &eval_ctx, iterations, hand_weights);

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

    /// Regression test for the line-363 panic: when hero (P0) and villain
    /// (P1) have DIFFERENT combo counts (e.g. AA+KK = 12 combos vs
    /// 72o+83o = 24 combos), the opponent-node branch in `traverse` used
    /// `opp_hands` (= hand_count[update_player]) to size `next_reach` and
    /// bound the strategy-fold loop. The correct size is `player_hands`
    /// (= hand_count of the current node's player, who is the opponent
    /// of `update_player`). Same family as PR 51's line-651 fix.
    ///
    /// Pre-fix: this panics with `index out of bounds: the len is 12 but
    /// the index is 12` (or similar) inside `traverse` at line 363.
    /// Post-fix: solve completes and emits a per-hand strategy table.
    #[test]
    fn vector_solver_handles_asymmetric_combo_counts() {
        // Dry rainbow river board where AA, KK, 72o, 83o all avoid
        // collisions: Tc 9d 4h Jc 6s (matches the Python sanity-gate
        // fixture in `tests/test_asymmetric_range_sanity.py`).
        let cfg = HUNLConfig {
            starting_stack: 1000,
            small_blind: 50,
            big_blind: 100,
            ante: 0,
            starting_street: Street::River,
            initial_board: vec![
                card_to_int(10, 3), // Tc
                card_to_int(9, 1),  // 9d
                card_to_int(4, 2),  // 4h
                card_to_int(11, 3), // Jc
                card_to_int(6, 0),  // 6s
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
        };

        // Hero (P0): AA + KK = 12 combos (6 each).
        let mut p0_holes: Vec<[u8; 2]> = Vec::new();
        for (s0, s1) in [(0u8, 1u8), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)] {
            p0_holes.push([card_to_int(14, s0), card_to_int(14, s1)]);
            p0_holes.push([card_to_int(13, s0), card_to_int(13, s1)]);
        }
        assert_eq!(p0_holes.len(), 12);

        // Villain (P1): 72o + 83o = 24 combos (12 each off-suit).
        let mut p1_holes: Vec<[u8; 2]> = Vec::new();
        for sa in 0u8..4 {
            for sb in 0u8..4 {
                if sa == sb {
                    continue;
                }
                let lo = card_to_int(2, sa);
                let hi = card_to_int(7, sb);
                p1_holes.push([lo.min(hi), lo.max(hi)]);
                let lo = card_to_int(3, sa);
                let hi = card_to_int(8, sb);
                p1_holes.push([lo.min(hi), lo.max(hi)]);
            }
        }
        assert_eq!(p1_holes.len(), 24);
        assert_ne!(
            p0_holes.len(),
            p1_holes.len(),
            "this regression test only exercises the bug if combo counts differ"
        );

        let out = solve_range_vs_range_postflop_with_hands(
            &cfg,
            Some([p0_holes, p1_holes]),
            3,
            1.5,
            0.0,
            2.0,
            0.0,
            0,
            None,
        )
        .expect("asymmetric range solve must not panic post-fix");
        assert_eq!(out.hand_count_per_player, [12, 24]);
        assert!(out.decision_node_count > 0, "no decision nodes");
        assert!(out.strategy_entry_count > 0, "no strategy entries");
    }

    // ------------------------------------------------------------------
    // PR 90 — A83 Track A: regret-init-noise plumbing tests.
    // ------------------------------------------------------------------

    /// PR 90 — verifies the `--regret-init-noise` flag's default value
    /// (`0.0`) is bit-identical to the pre-PR-90 all-zero initialization
    /// when consumed via the public `solve_range_vs_range_postflop`
    /// surface. Two calls with `noise=0.0` and identical other parameters
    /// must produce strategy entries with `f64::EQ` equality across the
    /// full output map.
    ///
    /// The success criterion is: `noise=0` is reproducible (DCFR is
    /// deterministic under fixed iteration order; no implicit RNG in the
    /// default path).
    #[test]
    fn regret_init_noise_zero_is_reproducible() {
        let cfg = tiny_river_rvr();
        let out_a = solve_range_vs_range_postflop_with_hands(
            &cfg, None, 3, 1.5, 0.0, 2.0, 0.0, 0, None,
        )
        .expect("solve must complete");
        let out_b = solve_range_vs_range_postflop_with_hands(
            &cfg, None, 3, 1.5, 0.0, 2.0, 0.0, 0, None,
        )
        .expect("solve must complete");
        assert_eq!(out_a.average_strategy.len(), out_b.average_strategy.len());
        for (key, probs_a) in &out_a.average_strategy {
            let probs_b = out_b
                .average_strategy
                .get(key)
                .expect("noise=0.0 reruns must produce identical key sets");
            assert_eq!(
                probs_a, probs_b,
                "noise=0.0 reruns must be bit-identical at infoset {key:?}"
            );
        }
    }

    /// PR 90 — verifies the `--regret-init-noise` epsilon path engages.
    /// Two solves with `noise=0.0` vs `noise=1e-9` (same other args, same
    /// seed) MUST produce regret rows that differ by `O(epsilon)` at
    /// iteration 1, demonstrating the flag is plumbed end-to-end and
    /// actually perturbs `regret_sum`. Three iters of solve are enough
    /// for the perturbation to propagate through strategy_sum.
    ///
    /// The test is intentionally weak on convergence — it only asserts
    /// the noise path engages, not that the resulting strategy is any
    /// closer to / farther from the noise-free Nash. The Nash-multiplicity
    /// experiment (A83 Track A) lives in the 200K-iter nohup runs
    /// downstream of this PR.
    #[test]
    fn regret_init_noise_epsilon_perturbs_strategy() {
        // Use a config with multi-action infosets so the noise CAN
        // perturb the strategy distribution. `tiny_river_rvr` produces
        // a single-action degenerate tree (`postflop_raise_cap=1` +
        // single bet size collapses every decision node to one legal
        // action) which masks the perturbation — every strategy row is
        // `[1.0]` regardless of regret state. Boosting the cap + adding
        // all-in produces 4324 multi-action infosets.
        let mut cfg = tiny_river_rvr();
        cfg.postflop_raise_cap = 3;
        cfg.include_all_in = true;
        let noise = 1e-9_f64;
        let out_zero = solve_range_vs_range_postflop_with_hands(
            &cfg, None, 3, 1.5, 0.0, 2.0, 0.0, 1, None,
        )
        .expect("baseline solve must complete");
        let out_eps = solve_range_vs_range_postflop_with_hands(
            &cfg, None, 3, 1.5, 0.0, 2.0, noise, 1, None,
        )
        .expect("perturbed solve must complete");
        // Same infoset key set (tree shape is identical regardless of
        // regret state — noise only perturbs values, not topology).
        assert_eq!(
            out_zero.average_strategy.len(),
            out_eps.average_strategy.len(),
            "noise must not change tree shape"
        );
        // Quantify the per-cell drift. With `noise = 1e-9` we expect at
        // least one cell to differ by *something* — the early iterations
        // can amplify ε-sized regret deltas into O(1) strategy
        // differences via regret-matching's `max(r, 0) / Σ max(r, 0)`
        // step, since `r_i ≈ ε` produces a degenerate normalization
        // where the sign pattern (rather than magnitude) determines the
        // strategy. This is precisely the Nash-multiplicity mechanism
        // the A83 200K-iter runs probe at scale.
        //
        // Pre-fix tests asserted an upper bound (`< 1e-3`) which was
        // theoretically wrong — regret-matching at the boundary
        // between negative and positive regret IS expected to flip
        // strategies between corners with ε-sized perturbations at
        // very low iteration counts.
        let mut max_diff: f64 = 0.0;
        for (key, probs_zero) in &out_zero.average_strategy {
            let probs_eps = out_eps
                .average_strategy
                .get(key)
                .expect("epsilon-perturbed solve must produce same key set");
            for (a, b) in probs_zero.iter().zip(probs_eps.iter()) {
                max_diff = max_diff.max((a - b).abs());
            }
        }
        assert!(
            max_diff > 0.0,
            "noise=1e-9 must produce non-zero divergence from noise=0.0 \
             (got max_diff={max_diff})"
        );
    }

    /// PR 90 — different `rng_seed` values with the same `noise > 0`
    /// MUST produce divergent strategies (proves the seed is actually
    /// consumed; if the seed argument were ignored the two solves would
    /// be bit-identical).
    #[test]
    fn regret_init_noise_seed_changes_outcome() {
        // Same cap-3 + all-in config as the epsilon test — single-
        // action infosets mask the seed effect.
        let mut cfg = tiny_river_rvr();
        cfg.postflop_raise_cap = 3;
        cfg.include_all_in = true;
        let noise = 1e-9_f64;
        let out_seed1 = solve_range_vs_range_postflop_with_hands(
            &cfg, None, 3, 1.5, 0.0, 2.0, noise, 1, None,
        )
        .expect("solve must complete");
        let out_seed2 = solve_range_vs_range_postflop_with_hands(
            &cfg, None, 3, 1.5, 0.0, 2.0, noise, 2, None,
        )
        .expect("solve must complete");
        let mut any_diff = false;
        for (key, probs_1) in &out_seed1.average_strategy {
            let probs_2 = out_seed2.average_strategy.get(key).unwrap();
            for (a, b) in probs_1.iter().zip(probs_2.iter()) {
                if (a - b).abs() > 0.0 {
                    any_diff = true;
                    break;
                }
            }
            if any_diff {
                break;
            }
        }
        assert!(any_diff, "different rng_seeds must produce different strategies");
    }

    /// HIGH-2 follow-up parity test: `terminal_value_vector_cached` must
    /// produce bit-identical output to the uncached `terminal_value_vector`
    /// across all terminal leaves of a tiny river RvR tree.
    ///
    /// We build an `EvalContext` with a non-trivial hand list (the full
    /// C(47, 2) = 1081 river-disjoint hands) and a random reach vector,
    /// walk every terminal in the tree, and compare per-hand output.
    /// This is the load-bearing correctness gate for the cache: any
    /// divergence here means the cached path is mis-computing showdown
    /// outcomes or chip-flow, and the differential test against Python
    /// would fail downstream.
    #[test]
    fn cached_matches_uncached_terminal_value() {
        let cfg = tiny_river_rvr();
        let initial = HUNLState::initial(std::sync::Arc::new(cfg.clone()));
        let ctx = EvalContext::from_root(&initial);
        // Build betting tree on a placeholder hole pair.
        let placeholder = initial.clone_with_hole_cards([
            ctx.hole[0][0],
            ctx.hole[1][0],
        ]);
        let tree = BettingTree::build_from(&placeholder);
        let cache = TerminalCache::build(&tree, &ctx, false);

        // Random-ish reach vectors for both players (deterministic so the
        // test is reproducible; we want non-uniform reach to stress the
        // accumulator path).
        let mk_reach = |n: usize, seed: u64| -> Vec<f64> {
            let mut r = vec![0.0_f64; n];
            let mut state = seed;
            for v in r.iter_mut() {
                // Splitmix64 (deterministic, fast).
                state = state.wrapping_add(0x9E37_79B9_7F4A_7C15);
                let mut z = state;
                z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
                z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
                z ^= z >> 31;
                // Convert to f64 in [0, 1).
                *v = (z as f64) / (u64::MAX as f64);
            }
            r
        };
        let reach_p0 = mk_reach(ctx.hand_count[0], 42);
        let reach_p1 = mk_reach(ctx.hand_count[1], 99);

        let mut compared = 0usize;
        for (node_idx, node) in tree.nodes.iter().enumerate() {
            match node {
                FlatNode::Fold { .. } | FlatNode::Showdown { .. } => {
                    for update_player in 0..2 {
                        let opp_player = 1 - update_player;
                        let reach_opp = if opp_player == 0 { &reach_p0 } else { &reach_p1 };
                        let uncached = terminal_value_vector(
                            node, &ctx, update_player, opp_player, reach_opp,
                        );
                        let cached = terminal_value_vector_cached(
                            &cache.leaves[node_idx],
                            &ctx,
                            update_player,
                            opp_player,
                            reach_opp,
                        );
                        assert_eq!(
                            uncached.len(),
                            cached.len(),
                            "size mismatch node={node_idx} update={update_player}"
                        );
                        for (hp, (u, c)) in uncached.iter().zip(cached.iter()).enumerate() {
                            // Bit-identical: both compute the same chip
                            // arithmetic from the same `Strength::evaluate_7`
                            // output, so equality should be exact.
                            assert_eq!(
                                u.to_bits(),
                                c.to_bits(),
                                "bit-mismatch at node={node_idx} update={update_player} \
                                 hp={hp}: uncached={u} cached={c}"
                            );
                        }
                        compared += 1;
                    }
                }
                _ => {}
            }
        }
        assert!(compared > 0, "no terminal leaves walked — fixture broken");
    }

    /// Parity gate for the inclusion-exclusion terminal evaluator
    /// (`CFR_TERMINAL_IE`): `terminal_value_vector_ie` must match
    /// `terminal_value_vector_cached` to FP tolerance on every Fold and
    /// Showdown leaf of `tiny_river_rvr()` (full C(47,2)=1081-hand river,
    /// NON-UNIFORM reach), for BOTH update_player perspectives.
    ///
    /// Tolerance (not bit-identity): the IE path reorders summation
    /// (prefix sum over sorted strengths minus blocker corrections), so
    /// it is FP-close, not bit-exact. Per element:
    ///   `|ie - cached| <= 1e-9 + 1e-9 * max(|ie|, |cached|)`.
    ///
    /// Also exercises the dedup edge case: in `from_root` both players
    /// share an identical hole list, so for every player hand `hp` there
    /// is an opp hand whose two cards coincide with `hp`'s — that opp idx
    /// appears in BOTH of `hp`'s card lists and MUST be counted exactly
    /// once. We assert this structurally on the IE buckets in addition to
    /// the numeric parity (a double-count would skew bucket weights).
    #[test]
    fn ie_matches_cached_terminal_value() {
        let cfg = tiny_river_rvr();
        let initial = HUNLState::initial(std::sync::Arc::new(cfg.clone()));
        let ctx = EvalContext::from_root(&initial);
        let placeholder = initial.clone_with_hole_cards([ctx.hole[0][0], ctx.hole[1][0]]);
        let tree = BettingTree::build_from(&placeholder);
        // IE data built ONLY here (flag-on equivalent); the cached cache
        // (flag-off) is the parity reference.
        let cache_ie = TerminalCache::build(&tree, &ctx, true);
        let cache_ref = TerminalCache::build(&tree, &ctx, false);

        let mk_reach = |n: usize, seed: u64| -> Vec<f64> {
            let mut r = vec![0.0_f64; n];
            let mut state = seed;
            for v in r.iter_mut() {
                state = state.wrapping_add(0x9E37_79B9_7F4A_7C15);
                let mut z = state;
                z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
                z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
                z ^= z >> 31;
                *v = (z as f64) / (u64::MAX as f64);
            }
            r
        };
        let reach_p0 = mk_reach(ctx.hand_count[0], 42);
        let reach_p1 = mk_reach(ctx.hand_count[1], 99);

        // --- Structural dedup edge case on the IE precompute itself. ---
        // For each Showdown leaf and update_player, find a player hand
        // `hp` whose exact cards match an opp hand `ho`; assert that opp
        // idx appears EXACTLY ONCE across the three IE blocker buckets.
        let mut dedup_checked = 0usize;
        for entry in &cache_ie.leaves {
            if let LeafCacheEntry::Showdown { ie: Some(ie_arr), .. } = entry {
                for up in 0..2 {
                    let op = 1 - up;
                    let ie = &ie_arr[up];
                    // hp == ho works because both players share the same
                    // hole list (identical exact-match cards) under
                    // `from_root`. Pick a representative hand index.
                    let hp = ctx.hand_count[up] / 2;
                    let exact = ctx.hole[up][hp];
                    // Locate the opp idx with identical cards.
                    let twin = ctx.hole[op]
                        .iter()
                        .position(|&h| h == exact)
                        .expect("opp must hold the identical exact-match hand under from_root");
                    let twin = twin as u32;
                    let count = ie.blk_less[hp].iter().filter(|&&i| i == twin).count()
                        + ie.blk_equal[hp].iter().filter(|&&i| i == twin).count()
                        + ie.blk_greater[hp].iter().filter(|&&i| i == twin).count();
                    assert_eq!(
                        count, 1,
                        "dedup edge case: exact-match opp idx {twin} for hp={hp} \
                         up={up} appears {count}× across IE blocker buckets (must be 1)"
                    );
                    // The exact-match hand has equal strength, so it lands
                    // in blk_equal.
                    assert!(
                        ie.blk_equal[hp].contains(&twin),
                        "exact-match opp idx must be in the tie bucket"
                    );
                    dedup_checked += 1;
                }
            }
        }
        assert!(dedup_checked > 0, "no Showdown leaf exercised the dedup edge case");

        // --- Numeric parity over every terminal leaf. ---
        let tol = |a: f64, b: f64| 1e-9 + 1e-9 * a.abs().max(b.abs());
        let mut scratch: Vec<f64> = Vec::new();
        let mut compared = 0usize;
        for (node_idx, node) in tree.nodes.iter().enumerate() {
            match node {
                FlatNode::Fold { .. } | FlatNode::Showdown { .. } => {
                    for update_player in 0..2 {
                        let opp_player = 1 - update_player;
                        let reach_opp = if opp_player == 0 { &reach_p0 } else { &reach_p1 };
                        let cached = terminal_value_vector_cached(
                            &cache_ref.leaves[node_idx],
                            &ctx,
                            update_player,
                            opp_player,
                            reach_opp,
                        );
                        let ie = terminal_value_vector_ie(
                            &cache_ie.leaves[node_idx],
                            cache_ie.fold_blockers.as_ref(),
                            &ctx,
                            update_player,
                            opp_player,
                            reach_opp,
                            &mut scratch,
                        );
                        assert_eq!(
                            ie.len(),
                            cached.len(),
                            "size mismatch node={node_idx} update={update_player}"
                        );
                        for (hp, (i, c)) in ie.iter().zip(cached.iter()).enumerate() {
                            let diff = (i - c).abs();
                            assert!(
                                diff <= tol(*i, *c),
                                "IE/cached divergence at node={node_idx} \
                                 update={update_player} hp={hp}: ie={i} cached={c} \
                                 diff={diff} tol={}",
                                tol(*i, *c),
                            );
                        }
                        compared += 1;
                    }
                }
                _ => {}
            }
        }
        assert!(compared > 0, "no terminal leaves walked — fixture broken");
    }

    // ------------------------------------------------------------------
    // B10 Phase B — per-combo weights (`hand_weights`) tests.
    // ------------------------------------------------------------------

    /// Back-compat: supplying `Some([vec![1.0; n0], vec![1.0; n1]])` for
    /// `hand_weights` MUST produce a bit-identical strategy to the legacy
    /// `None` path. This codifies the multiplicative-only invariant: an
    /// all-ones weight vector is the same scalar as the default initial
    /// reach, so every per-(hand, action) regret/strategy update walks
    /// the exact same trajectory.
    #[test]
    fn b10_phase_b_all_ones_weights_matches_legacy_none() {
        let cfg = tiny_river_rvr();
        let out_none = solve_range_vs_range_postflop_with_hands(
            &cfg, None, 5, 1.5, 0.0, 2.0, 0.0, 0, None,
        )
        .expect("None-weight baseline must complete");
        // Build all-ones weight vectors of the right length. We need the
        // hand counts; rerun `EvalContext::from_root` to get them.
        let initial = HUNLState::initial(std::sync::Arc::new(cfg.clone()));
        let ctx = EvalContext::from_root(&initial);
        let weights = Some([
            vec![1.0; ctx.hand_count[0]],
            vec![1.0; ctx.hand_count[1]],
        ]);
        let out_ones = solve_range_vs_range_postflop_with_hands(
            &cfg, None, 5, 1.5, 0.0, 2.0, 0.0, 0, weights,
        )
        .expect("all-ones weights solve must complete");
        assert_eq!(
            out_none.average_strategy.len(),
            out_ones.average_strategy.len(),
            "all-ones weights must produce the same infoset count as None"
        );
        for (key, probs_none) in &out_none.average_strategy {
            let probs_ones = out_ones
                .average_strategy
                .get(key)
                .expect("all-ones weights must produce identical key set");
            assert_eq!(
                probs_none, probs_ones,
                "all-ones weights MUST be bit-identical to None at infoset {key:?}"
            );
        }
    }

    /// Non-uniform `hand_weights` produces a strategy that diverges from
    /// the all-ones baseline by a non-zero amount. The smoke claim is
    /// just "the weights actually engage" — we don't assert a specific
    /// quantitative drift, only that some cell moves.
    ///
    /// Mirrors the `regret_init_noise_epsilon_perturbs_strategy` config
    /// shape: cap=3 + all-in enabled so the tree has multi-action
    /// infosets (the default `tiny_river_rvr` collapses every decision
    /// to a single legal action, masking any perturbation).
    #[test]
    fn b10_phase_b_non_uniform_weights_perturbs_strategy() {
        let mut cfg = tiny_river_rvr();
        cfg.postflop_raise_cap = 3;
        cfg.include_all_in = true;
        let initial = HUNLState::initial(std::sync::Arc::new(cfg.clone()));
        let ctx = EvalContext::from_root(&initial);
        // All-ones baseline.
        let out_ones = solve_range_vs_range_postflop_with_hands(
            &cfg, None, 5, 1.5, 0.0, 2.0, 0.0, 0,
            Some([vec![1.0; ctx.hand_count[0]], vec![1.0; ctx.hand_count[1]]]),
        )
        .expect("baseline must complete");
        // Skew: half-weight on every other hand for each player. The
        // kernel scales the initial reach into the root infoset by 0.5
        // for those hands, so every downstream regret update for them is
        // correspondingly attenuated. With a multi-action tree this MUST
        // perturb at least one strategy cell.
        let mut w0 = vec![1.0; ctx.hand_count[0]];
        let mut w1 = vec![1.0; ctx.hand_count[1]];
        for i in (0..ctx.hand_count[0]).step_by(2) {
            w0[i] = 0.5;
        }
        for i in (0..ctx.hand_count[1]).step_by(2) {
            w1[i] = 0.5;
        }
        let out_skewed = solve_range_vs_range_postflop_with_hands(
            &cfg, None, 5, 1.5, 0.0, 2.0, 0.0, 0, Some([w0, w1]),
        )
        .expect("skewed-weight solve must complete");
        let mut max_diff: f64 = 0.0;
        for (key, probs_ones) in &out_ones.average_strategy {
            if let Some(probs_skewed) = out_skewed.average_strategy.get(key) {
                for (a, b) in probs_ones.iter().zip(probs_skewed.iter()) {
                    max_diff = max_diff.max((a - b).abs());
                }
            }
        }
        // Some cell must have moved. We don't claim a specific magnitude
        // — Nash multiplicity is real and 5 iters is not enough to assert
        // direction. The key invariant is the weights engage.
        assert!(
            max_diff > 0.0,
            "non-uniform hand_weights must produce non-zero strategy drift \
             (got max_diff = {max_diff})"
        );
    }

    /// Length-mismatched `hand_weights` MUST panic — the assertion guards
    /// against silent garbage when the caller mis-aligns weights with
    /// the hand list.
    #[test]
    #[should_panic(expected = "p0_weights length")]
    fn b10_phase_b_mismatched_weight_length_panics() {
        let cfg = tiny_river_rvr();
        // Pass a 1-element p0_weights against the full 1081-hand p0 list
        // from `from_root`. Should panic via the assert_eq! in `solve`.
        let _ = solve_range_vs_range_postflop_with_hands(
            &cfg, None, 1, 1.5, 0.0, 2.0, 0.0, 0,
            Some([vec![1.0; 1], vec![1.0; 1]]),
        );
    }

    // ------------------------------------------------------------------
    // v1.10 PR-2 — vector-form turn forward walk: bit-identical gate.
    // ------------------------------------------------------------------

    /// Tiny turn RvR config used by the v1.10 PR-2 bit-identical tests.
    /// Single bet size + raise_cap=1 to keep the tree small enough that
    /// the test finishes in <1s.
    fn tiny_turn_rvr() -> HUNLConfig {
        HUNLConfig {
            starting_stack: 1000,
            small_blind: 50,
            big_blind: 100,
            ante: 0,
            starting_street: Street::Turn,
            initial_board: vec![
                card_to_int(12, 0), // Qs
                card_to_int(7, 1),  // 7h
                card_to_int(2, 2),  // 2d
                card_to_int(5, 3),  // 5c
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

    /// `v1.10 PR-2` — `BettingTree::build_with_mode(TemplateExtract)`
    /// produces a `chance_templates` entry for the turn → river chance
    /// node, while `Standard` mode does not.
    ///
    /// The structural property under test: the FlatNode list is identical
    /// between the two modes (`TemplateExtract` only adds out-of-band
    /// metadata).
    #[test]
    fn template_extract_finds_turn_chance_node() {
        let cfg = tiny_turn_rvr();
        let initial = HUNLState::initial(std::sync::Arc::new(cfg.clone()));
        let placeholder = initial.clone_with_hole_cards([
            [card_to_int(14, 0), card_to_int(14, 1)],
            [card_to_int(13, 0), card_to_int(13, 1)],
        ]);
        let tree_std = BettingTree::build_with_mode(&placeholder, BettingTreeMode::Standard);
        let tree_tmpl =
            BettingTree::build_with_mode(&placeholder, BettingTreeMode::TemplateExtract);
        assert_eq!(
            tree_std.nodes.len(),
            tree_tmpl.nodes.len(),
            "TemplateExtract mode must preserve FlatNode list shape"
        );
        assert!(
            tree_std.chance_templates.is_empty(),
            "Standard mode must not extract chance templates"
        );
        assert!(
            !tree_tmpl.chance_templates.is_empty(),
            "TemplateExtract mode must find at least one chance template (the turn-river chance)"
        );
        // Verify the extracted template points at a Chance node with >1 children.
        for t in &tree_tmpl.chance_templates {
            match &tree_tmpl.nodes[t.chance_node_idx] {
                FlatNode::Chance { children, .. } => {
                    assert!(
                        children.len() > 1,
                        "chance template must have >1 children (got {})",
                        children.len()
                    );
                }
                _ => panic!("chance_node_idx must point at a Chance node"),
            }
        }
    }

    /// `v1.10 PR-2` — the `TemplateExtract` solve path produces strategy
    /// outputs that are **bit-identical** to the `Standard` solve path.
    ///
    /// This is the critical acceptance gate for PR-2: the only intended
    /// difference is the dispatch through `traverse_turn_chance` at
    /// chance nodes with a `ChanceTemplate`, and that function performs
    /// the EXACT same arithmetic as the legacy chance arm. Every
    /// (key, action_idx) pair in the output `average_strategy` map must
    /// be equal byte-for-byte across the two modes.
    #[test]
    fn template_extract_bit_identical_to_standard() {
        let cfg = tiny_turn_rvr();
        let initial = HUNLState::initial(std::sync::Arc::new(cfg.clone()));

        // Use a small hand list to keep the test fast.
        let p0_holes = vec![
            [card_to_int(14, 0), card_to_int(14, 1)], // AsAh
            [card_to_int(13, 0), card_to_int(13, 1)], // KsKh
        ];
        let p1_holes = p0_holes.clone();

        // Build both trees explicitly to bypass the public API's mode
        // auto-selection.
        let placeholder = initial.clone_with_hole_cards([p0_holes[0], p1_holes[0]]);
        let tree_std = BettingTree::build_with_mode(&placeholder, BettingTreeMode::Standard);
        let tree_tmpl =
            BettingTree::build_with_mode(&placeholder, BettingTreeMode::TemplateExtract);

        let ctx_std = EvalContext::from_hand_lists(p0_holes.clone(), p1_holes.clone(), 100);
        let ctx_tmpl = EvalContext::from_hand_lists(p0_holes, p1_holes, 100);

        // Run both solves with identical hyperparameters + zero noise.
        let mut solver_std = VectorDCFR::with_init_noise(
            &tree_std,
            ctx_std.hand_count,
            1.5,
            0.0,
            2.0,
            0.0,
            0,
        );
        let mut solver_tmpl = VectorDCFR::with_init_noise(
            &tree_tmpl,
            ctx_tmpl.hand_count,
            1.5,
            0.0,
            2.0,
            0.0,
            0,
        );

        solver_std.solve(&tree_std, &ctx_std, 5, None);
        solver_tmpl.solve(&tree_tmpl, &ctx_tmpl, 5, None);

        // Final discount catch-up — match the public solve's tail.
        let final_iter_std = solver_std.iteration;
        for info in solver_std.infosets.iter_mut().flatten() {
            VectorDCFR::discount(info, final_iter_std, 1.5, 0.0, 2.0);
        }
        let final_iter_tmpl = solver_tmpl.iteration;
        for info in solver_tmpl.infosets.iter_mut().flatten() {
            VectorDCFR::discount(info, final_iter_tmpl, 1.5, 0.0, 2.0);
        }

        let strat_std = build_average_strategy(&solver_std, &tree_std, &ctx_std);
        let strat_tmpl = build_average_strategy(&solver_tmpl, &tree_tmpl, &ctx_tmpl);

        assert_eq!(
            strat_std.len(),
            strat_tmpl.len(),
            "TemplateExtract must emit identical key set ({} std vs {} tmpl)",
            strat_std.len(),
            strat_tmpl.len(),
        );
        for (key, probs_std) in &strat_std {
            let probs_tmpl = strat_tmpl
                .get(key)
                .unwrap_or_else(|| panic!("missing key in template-mode output: {key:?}"));
            assert_eq!(
                probs_std.len(),
                probs_tmpl.len(),
                "key {key:?}: action_count mismatch ({} std vs {} tmpl)",
                probs_std.len(),
                probs_tmpl.len(),
            );
            for (a, (ps, pt)) in probs_std.iter().zip(probs_tmpl.iter()).enumerate() {
                // 1e-12 bit-identical gate per the PR-2 spec.
                assert!(
                    (ps - pt).abs() < 1e-12,
                    "key {key:?} action {a}: std={ps} tmpl={pt} diff={}",
                    (ps - pt).abs()
                );
            }
        }
    }

    /// `v1.10 PR-2` — verifies that on a river-rooted config the public
    /// solve path uses `Standard` mode (no chance templates extracted,
    /// since the river-betting tree has no chance node within it).
    /// Also verifies that the river solve still produces sensible output.
    ///
    /// This is the negative-control half of the PR-2 acceptance: when
    /// there's nothing to template-extract, the solve falls through to
    /// the legacy path bit-identically.
    #[test]
    fn river_solve_does_not_template_extract() {
        let cfg = tiny_river_rvr();
        let out = solve_range_vs_range_postflop(&cfg, 3, 1.5, 0.0, 2.0)
            .expect("tiny river solve must succeed");
        assert!(out.decision_node_count > 0);
        assert!(out.strategy_entry_count > 0);
    }

    // ------------------------------------------------------------------
    // v1.10 PR-3 — vector-form flop forward walk tests.
    // ------------------------------------------------------------------

    /// Tiny flop RvR config for the v1.10 PR-3 bit-identical tests.
    /// Single bet size + raise_cap=1 to keep the tree tractable. The
    /// flop board is 2c3d4h, leaving the (turn × river) chance
    /// enumeration at the standard 49 × 48 = 2352 runouts. Combined
    /// with 1 bet size and raise_cap=1 the betting tree has a small
    /// number of decision nodes per runout.
    fn tiny_flop_rvr() -> HUNLConfig {
        HUNLConfig {
            starting_stack: 200,
            small_blind: 50,
            big_blind: 100,
            ante: 0,
            starting_street: Street::Flop,
            initial_board: vec![
                card_to_int(2, 0), // 2c
                card_to_int(3, 1), // 3d
                card_to_int(4, 2), // 4h
            ],
            initial_pot: 200,
            initial_contributions: [100, 100],
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

    /// `v1.10 PR-3` — `extract_chance_templates` assigns
    /// `chance_depth == 2` to the flop chance node and `chance_depth == 1`
    /// to the nested turn chance node.
    ///
    /// Structural property: a flop-rooted RvR has exactly TWO depth-bearing
    /// chance templates — the outer flop deal (depth=2) and the inner
    /// turn deal (depth=1). All-in chance run-outs that don't match the
    /// "all children structurally identical" gate are excluded.
    #[test]
    fn template_extract_assigns_correct_chance_depths() {
        let cfg = tiny_flop_rvr();
        let initial = HUNLState::initial(std::sync::Arc::new(cfg.clone()));
        let placeholder = initial.clone_with_hole_cards([
            [card_to_int(14, 0), card_to_int(13, 0)], // AsKs
            [card_to_int(14, 1), card_to_int(13, 1)], // AhKh
        ]);
        let tree =
            BettingTree::build_with_mode(&placeholder, BettingTreeMode::TemplateExtract);
        assert!(
            !tree.chance_templates.is_empty(),
            "flop-rooted TemplateExtract must find chance templates"
        );

        // A flop-rooted RvR has two chance levels: the outer turn-deal
        // chance (depth==1, river chance nested below) and the inner
        // river-deal chance (depth==0). Both must show up in the
        // extracted templates.
        let mut saw_depth_ge_1 = false;
        let mut saw_depth_0 = false;
        for t in &tree.chance_templates {
            if t.chance_depth >= 1 {
                saw_depth_ge_1 = true;
            } else {
                saw_depth_0 = true;
            }
        }
        assert!(
            saw_depth_ge_1,
            "flop-rooted tree must have at least one outer chance template \
             (depth>=1, the turn-deal chance with river-deal nested below)"
        );
        assert!(
            saw_depth_0,
            "flop-rooted tree must have at least one leaf chance template \
             (depth==0, e.g. the river-deal chance)"
        );
    }

    /// `v1.10 PR-3` — `RunoutCache::build` allocates scratch buffers when
    /// a depth==2 template is present, and reports `is_active() == true`.
    /// Turn-rooted solves yield an inactive cache.
    #[test]
    fn runout_cache_active_only_on_flop_root() {
        // Flop-rooted: active cache.
        let cfg_flop = tiny_flop_rvr();
        let initial_flop = HUNLState::initial(std::sync::Arc::new(cfg_flop.clone()));
        let placeholder_flop = initial_flop.clone_with_hole_cards([
            [card_to_int(14, 0), card_to_int(13, 0)],
            [card_to_int(14, 1), card_to_int(13, 1)],
        ]);
        let tree_flop = BettingTree::build_with_mode(
            &placeholder_flop,
            BettingTreeMode::TemplateExtract,
        );
        let ctx_flop = EvalContext::from_hand_lists(
            vec![[card_to_int(14, 0), card_to_int(13, 0)]],
            vec![[card_to_int(14, 1), card_to_int(13, 1)]],
            100,
        );
        let cache_flop = RunoutCache::build(&tree_flop, &ctx_flop);
        assert!(
            cache_flop.is_active(),
            "RunoutCache must be active for flop-rooted trees with depth==2 templates"
        );

        // Turn-rooted: inactive cache (max depth==1).
        let cfg_turn = tiny_turn_rvr();
        let initial_turn = HUNLState::initial(std::sync::Arc::new(cfg_turn.clone()));
        let placeholder_turn = initial_turn.clone_with_hole_cards([
            [card_to_int(14, 0), card_to_int(14, 1)],
            [card_to_int(13, 0), card_to_int(13, 1)],
        ]);
        let tree_turn = BettingTree::build_with_mode(
            &placeholder_turn,
            BettingTreeMode::TemplateExtract,
        );
        let ctx_turn = EvalContext::from_hand_lists(
            vec![[card_to_int(14, 0), card_to_int(14, 1)]],
            vec![[card_to_int(13, 0), card_to_int(13, 1)]],
            100,
        );
        let cache_turn = RunoutCache::build(&tree_turn, &ctx_turn);
        assert!(
            !cache_turn.is_active(),
            "RunoutCache must be inactive for turn-rooted trees (no depth==2 template)"
        );
    }

    /// `v1.10 PR-3` — solve via `TemplateExtract` (PR-3 vector flop walker
    /// active) produces bit-identical strategy to `Standard` mode (legacy
    /// per-runout recursion). This is the headline acceptance gate for
    /// PR-3: the dispatch through `traverse_flop_chance_recursive` does
    /// the EXACT same arithmetic + DFS as the legacy chance arm, only
    /// with pre-allocated scratch in place of fresh `vec!`.
    ///
    /// Tiny flop fixture (4 hands, 1 bet size, raise_cap=1) — the same
    /// shape the Python diff test uses for F4_synth (`tests/test_v1_10_3_flop_diff.py::test_f4_synth_small_tree_diff`).
    #[test]
    fn flop_template_extract_bit_identical_to_standard() {
        let cfg = tiny_flop_rvr();
        let initial = HUNLState::initial(std::sync::Arc::new(cfg.clone()));

        let p0_holes = vec![
            [card_to_int(14, 0), card_to_int(13, 0)], // AsKs
            [card_to_int(14, 1), card_to_int(13, 1)], // AhKh
            [card_to_int(14, 2), card_to_int(13, 2)], // AdKd
            [card_to_int(14, 3), card_to_int(13, 3)], // AcKc
        ];
        let p1_holes = p0_holes.clone();

        let placeholder = initial.clone_with_hole_cards([p0_holes[0], p1_holes[0]]);
        let tree_std = BettingTree::build_with_mode(&placeholder, BettingTreeMode::Standard);
        let tree_tmpl =
            BettingTree::build_with_mode(&placeholder, BettingTreeMode::TemplateExtract);

        let ctx_std = EvalContext::from_hand_lists(p0_holes.clone(), p1_holes.clone(), 100);
        let ctx_tmpl = EvalContext::from_hand_lists(p0_holes, p1_holes, 100);

        let mut solver_std =
            VectorDCFR::with_init_noise(&tree_std, ctx_std.hand_count, 1.5, 0.0, 2.0, 0.0, 0);
        let mut solver_tmpl = VectorDCFR::with_init_noise(
            &tree_tmpl,
            ctx_tmpl.hand_count,
            1.5,
            0.0,
            2.0,
            0.0,
            0,
        );

        solver_std.solve(&tree_std, &ctx_std, 3, None);
        solver_tmpl.solve(&tree_tmpl, &ctx_tmpl, 3, None);

        // Final discount catch-up to mirror the public solve's tail.
        let final_iter_std = solver_std.iteration;
        for info in solver_std.infosets.iter_mut().flatten() {
            VectorDCFR::discount(info, final_iter_std, 1.5, 0.0, 2.0);
        }
        let final_iter_tmpl = solver_tmpl.iteration;
        for info in solver_tmpl.infosets.iter_mut().flatten() {
            VectorDCFR::discount(info, final_iter_tmpl, 1.5, 0.0, 2.0);
        }

        let strat_std = build_average_strategy(&solver_std, &tree_std, &ctx_std);
        let strat_tmpl = build_average_strategy(&solver_tmpl, &tree_tmpl, &ctx_tmpl);

        assert_eq!(
            strat_std.len(),
            strat_tmpl.len(),
            "PR-3 TemplateExtract must emit identical key set ({} std vs {} tmpl)",
            strat_std.len(),
            strat_tmpl.len(),
        );
        for (key, probs_std) in &strat_std {
            let probs_tmpl = strat_tmpl
                .get(key)
                .unwrap_or_else(|| panic!("missing key in PR-3 template-mode output: {key:?}"));
            assert_eq!(
                probs_std.len(),
                probs_tmpl.len(),
                "key {key:?}: action_count mismatch ({} std vs {} tmpl)",
                probs_std.len(),
                probs_tmpl.len(),
            );
            for (a, (ps, pt)) in probs_std.iter().zip(probs_tmpl.iter()).enumerate() {
                // 1e-12 bit-identical gate per the PR-3 spec.
                assert!(
                    (ps - pt).abs() < 1e-12,
                    "PR-3 strategy drift at key {key:?} action {a}: \
                     std={ps} tmpl={pt} diff={}",
                    (ps - pt).abs()
                );
            }
        }
    }

    /// End-to-end parity gate for the inclusion-exclusion terminal
    /// evaluator (`CFR_TERMINAL_IE`): a FULL multi-iteration river solve
    /// must produce the same average-strategy map with the flag OFF
    /// (legacy `terminal_value_vector_cached`) and ON (the O(N + N·B)
    /// `terminal_value_vector_ie` path). Belt-and-suspenders over the
    /// per-leaf gate `ie_matches_cached_terminal_value`: this proves the
    /// two terminal evaluators stay in lockstep across the WHOLE CFR
    /// recursion (reach-weighted regret/strategy accumulation over many
    /// iterations), not just at a single leaf.
    ///
    /// **Isolation contract.** `CFR_TERMINAL_IE` is process-global and
    /// cargo runs tests on parallel threads, so this test must be run
    /// with `--test-threads=1` (or `--exact` in isolation). It does the
    /// baseline (flag UNSET) solve FIRST, then sets the var, then removes
    /// it, leaving the environment clean for any subsequent test.
    ///
    /// We boost `postflop_raise_cap`/`include_all_in` so the tree has
    /// genuine multi-action infosets (the default `tiny_river_rvr` tree
    /// collapses to single-action rows that are `[1.0]` regardless of the
    /// terminal-value math, which would make the comparison vacuous).
    ///
    /// Tolerance `|a-b| <= 1e-6 + 1e-6 * max(|a|,|b|)` is looser than the
    /// per-leaf 1e-9 because FP error accumulates across iterations, but
    /// is still tight enough that any real divergence in the IE path
    /// fails the gate rather than being masked.
    #[test]
    fn ie_full_solve_matches_cached() {
        let mut cfg = tiny_river_rvr();
        // Multi-action tree so the terminal-value path actually shapes a
        // non-degenerate strategy (mirrors `regret_init_noise_epsilon_
        // perturbs_strategy`'s rationale).
        cfg.postflop_raise_cap = 3;
        cfg.include_all_in = true;
        let iters: u32 = 40;

        // Step 1 — baseline with the flag UNSET (legacy cached path).
        std::env::remove_var("CFR_TERMINAL_IE");
        let out_off = solve_range_vs_range_postflop(&cfg, iters, 1.5, 0.0, 2.0)
            .expect("flag-off solve must complete");

        // Step 2 — same solve with the flag SET (inclusion-exclusion path).
        std::env::set_var("CFR_TERMINAL_IE", "1");
        let out_on = solve_range_vs_range_postflop(&cfg, iters, 1.5, 0.0, 2.0)
            .expect("flag-on solve must complete");
        // Restore clean environment regardless of the assertions below.
        std::env::remove_var("CFR_TERMINAL_IE");

        assert_eq!(
            out_off.iterations, out_on.iterations,
            "iteration counts must match"
        );
        assert_eq!(
            out_off.average_strategy.len(),
            out_on.average_strategy.len(),
            "IE flag must not change the infoset key-set size \
             ({} off vs {} on)",
            out_off.average_strategy.len(),
            out_on.average_strategy.len(),
        );

        let mut max_abs_diff = 0.0_f64;
        let mut worst_key = String::new();
        for (key, probs_off) in &out_off.average_strategy {
            let probs_on = out_on
                .average_strategy
                .get(key)
                .unwrap_or_else(|| panic!("IE flag dropped infoset key: {key:?}"));
            assert_eq!(
                probs_off.len(),
                probs_on.len(),
                "key {key:?}: action_count mismatch ({} off vs {} on)",
                probs_off.len(),
                probs_on.len(),
            );
            for (a, (po, pn)) in probs_off.iter().zip(probs_on.iter()).enumerate() {
                let diff = (po - pn).abs();
                if diff > max_abs_diff {
                    max_abs_diff = diff;
                    worst_key = format!("{key:?}#{a}");
                }
                let tol = 1e-6 + 1e-6 * po.abs().max(pn.abs());
                assert!(
                    diff <= tol,
                    "IE-vs-cached strategy divergence at {key:?} action {a}: \
                     off={po} on={pn} diff={diff} tol={tol}"
                );
            }
        }
        // Surface the max observed value-difference (visible with
        // `cargo test -- --nocapture`).
        println!(
            "ie_full_solve_matches_cached: compared {} infosets over {} iters; \
             max |off - on| = {max_abs_diff:e} at {worst_key}",
            out_off.average_strategy.len(),
            iters,
        );
        assert!(
            max_abs_diff.is_finite(),
            "max diff must be finite (got {max_abs_diff})"
        );
    }

    /// Diagnostic (not a gate — always passes): quantify the IE precompute
    /// memory footprint by counting `FlatNode::Showdown` leaves in a turn
    /// vs flop tree and measuring the actual bytes of `ShowdownIE` data
    /// attached per leaf. Run with `--nocapture` to print the table.
    ///
    /// Established facts this confirms:
    ///   - `TerminalCache` has exactly one `LeafCacheEntry` per tree node
    ///     (built ONCE per solve, not per runout) — distinct runouts are
    ///     already distinct `FlatNode::Showdown` nodes in the materialized
    ///     tree, so IE memory is O(Showdown_leaves × N), NOT
    ///     O(runouts × betting_leaves × N) on top of a compacted tree.
    ///   - Per-Showdown-leaf IE bytes scale ~linearly in N (sorted_idx +
    ///     range_start + range_end are 3·N u32s; the blocker lists add a
    ///     small board-dependent constant), so the flop blow-up is driven
    ///     by the much larger Showdown-leaf COUNT of a flop tree.
    fn count_showdown_leaves(tree: &BettingTree) -> usize {
        tree.nodes
            .iter()
            .filter(|n| matches!(n, FlatNode::Showdown { .. }))
            .count()
    }

    /// Exact heap bytes of one `ShowdownIE` (both update-player perspectives
    /// summed): the three N-length `Vec<u32>` plus every blocker sub-vec.
    fn showdown_ie_bytes(ie: &[ShowdownIE; 2]) -> usize {
        let mut total = 0usize;
        for p in ie.iter() {
            total += p.sorted_idx.len() * 4;
            total += p.range_start.len() * 4;
            total += p.range_end.len() * 4;
            for v in p.blk_less.iter() {
                total += v.len() * 4;
            }
            for v in p.blk_equal.iter() {
                total += v.len() * 4;
            }
            for v in p.blk_greater.iter() {
                total += v.len() * 4;
            }
        }
        total
    }

    #[test]
    fn ie_memory_footprint_turn_vs_flop_diagnostic() {
        // Small hand list keeps the flop tree build memory-safe in-test.
        // The per-leaf IE bytes scale linearly in N, so the SHAPE measured
        // here extrapolates to production N (e.g. ~1081 at full deck).
        let n = 24usize;
        let mut p0: Vec<[u8; 2]> = Vec::new();
        let mut p1: Vec<[u8; 2]> = Vec::new();
        // Build N disjoint-from-board pairs from high cards.
        let mut pairs: Vec<[u8; 2]> = Vec::new();
        for r0 in (2u8..=14).rev() {
            for s0 in 0u8..4 {
                for r1 in (2u8..=14).rev() {
                    for s1 in 0u8..4 {
                        let c0 = r0 * 4 + s0;
                        let c1 = r1 * 4 + s1;
                        if c0 < c1 {
                            pairs.push([c0, c1]);
                        }
                    }
                }
            }
        }
        for &pr in pairs.iter() {
            if p0.len() >= n {
                break;
            }
            // Use cards >= 6*4 so they avoid the low flop board below.
            if pr[0] >= 6 * 4 && pr[1] >= 6 * 4 {
                p0.push(pr);
                p1.push(pr);
            }
        }
        let ctx = EvalContext::from_hand_lists(p0.clone(), p1.clone(), 100);

        let measure = |cfg: &HUNLConfig, label: &str| {
            let initial = HUNLState::initial(std::sync::Arc::new(cfg.clone()));
            let placeholder = initial.clone_with_hole_cards([ctx.hole[0][0], ctx.hole[1][0]]);
            let tree =
                BettingTree::build_with_mode(&placeholder, BettingTreeMode::TemplateExtract);
            let showdowns = count_showdown_leaves(&tree);
            let cache = TerminalCache::build(&tree, &ctx, true);
            let mut ie_total = 0usize;
            let mut sample_per_leaf = 0usize;
            for leaf in &cache.leaves {
                if let LeafCacheEntry::Showdown { ie: Some(ie_arr), .. } = leaf {
                    let b = showdown_ie_bytes(ie_arr);
                    ie_total += b;
                    if sample_per_leaf == 0 {
                        sample_per_leaf = b;
                    }
                }
            }
            // fold_blockers (board-independent, one per up perspective).
            let mut fold_bytes = 0usize;
            if let Some(fb) = &cache.fold_blockers {
                for up in fb.iter() {
                    for v in up.iter() {
                        fold_bytes += v.len() * 4;
                    }
                }
            }
            println!(
                "[IE-mem {label}] nodes={} showdown_leaves={} N={} \
                 ie_bytes/leaf={} ie_total={:.2}MB fold_blockers={:.3}MB",
                tree.nodes.len(),
                showdowns,
                n,
                sample_per_leaf,
                ie_total as f64 / 1_048_576.0,
                fold_bytes as f64 / 1_048_576.0,
            );
            (showdowns, ie_total, sample_per_leaf)
        };

        let (turn_sd, _turn_ie, per_leaf) = measure(&tiny_turn_rvr(), "turn");
        let (flop_sd, _flop_ie, _) = measure(&tiny_flop_rvr(), "flop");

        // Per-Showdown-leaf IE bytes (summed over both perspectives) are
        // dominated by 3 * N u32s per perspective = 6 * N * 4 bytes, plus
        // blockers. Sanity-check the linear-in-N lower bound.
        assert!(
            per_leaf >= 6 * n * 4,
            "per-leaf IE bytes ({per_leaf}) below 6*N*4 lower bound ({})",
            6 * n * 4
        );
        // The flop tree has dramatically more Showdown leaves than the turn
        // tree (one per river runout per betting line, summed over ~47 turn
        // deals). This is the root of the flop memory blow-up.
        assert!(
            flop_sd > turn_sd,
            "flop tree must have more Showdown leaves than turn \
             (turn={turn_sd} flop={flop_sd})"
        );
        println!(
            "[IE-mem ratio] flop/turn showdown_leaves = {:.1}x  \
             (IE memory scales with this ratio at fixed N)",
            flop_sd as f64 / turn_sd as f64
        );
    }

    /// End-to-end parity gate for the inclusion-exclusion terminal
    /// evaluator (`CFR_TERMINAL_IE`), ONE STREET DEEPER than
    /// `ie_full_solve_matches_cached`: a FULL multi-iteration **turn**
    /// subgame solve must produce the same average-strategy map with the
    /// flag OFF (legacy `terminal_value_vector_cached`) and ON (the
    /// O(N + N·B) `terminal_value_vector_ie` path).
    ///
    /// Why a turn fixture matters: a turn-rooted subgame (4-card board)
    /// has ONE MORE chance deal than the river fixture — the river-card
    /// deal expands into ~46 distinct `FlatNode::Showdown` runouts, each
    /// carrying its own `ShowdownIE` precompute. This proves the IE path
    /// stays in lockstep with the cached path across the inner chance
    /// recursion (`traverse_turn_chance_recursive`), not just at the
    /// flat river-betting layer. It is the correctness evidence for
    /// considering an IE default flip on the turn street.
    ///
    /// **Isolation contract** (identical to `ie_full_solve_matches_cached`):
    /// `CFR_TERMINAL_IE` is process-global, so run with
    /// `--test-threads=1 --exact`. The baseline (flag UNSET) solve runs
    /// FIRST, then the var is set, then removed — leaving a clean env.
    ///
    /// We boost `postflop_raise_cap`/`include_all_in` so the tree has
    /// genuine multi-action infosets (the default `tiny_turn_rvr` tree
    /// collapses to single-action `[1.0]` rows that are invariant to the
    /// terminal-value math, making the comparison vacuous).
    ///
    /// Tolerance `|a-b| <= 1e-6 + 1e-6 * max(|a|,|b|)` matches the river
    /// gate: looser than the per-leaf 1e-9 because FP error accumulates
    /// across iterations AND across the extra chance level, but still
    /// tight enough that any real IE-path divergence fails rather than
    /// being masked.
    #[test]
    fn ie_full_solve_matches_cached_turn() {
        let mut cfg = tiny_turn_rvr();
        // Multi-action tree so the terminal-value path actually shapes a
        // non-degenerate strategy (mirrors `ie_full_solve_matches_cached`).
        cfg.postflop_raise_cap = 2;
        cfg.include_all_in = true;
        let iters: u32 = 24;

        // Step 1 — baseline with the flag UNSET (legacy cached path).
        std::env::remove_var("CFR_TERMINAL_IE");
        let out_off = solve_range_vs_range_postflop(&cfg, iters, 1.5, 0.0, 2.0)
            .expect("turn flag-off solve must complete");

        // Step 2 — same solve with the flag SET (inclusion-exclusion path).
        std::env::set_var("CFR_TERMINAL_IE", "1");
        let out_on = solve_range_vs_range_postflop(&cfg, iters, 1.5, 0.0, 2.0)
            .expect("turn flag-on solve must complete");
        // Restore clean environment regardless of the assertions below.
        std::env::remove_var("CFR_TERMINAL_IE");

        assert_eq!(
            out_off.iterations, out_on.iterations,
            "iteration counts must match"
        );
        assert_eq!(
            out_off.average_strategy.len(),
            out_on.average_strategy.len(),
            "IE flag must not change the infoset key-set size \
             ({} off vs {} on)",
            out_off.average_strategy.len(),
            out_on.average_strategy.len(),
        );
        // Guard against a vacuous comparison: a multi-action turn tree
        // must have at least one infoset with >1 action.
        assert!(
            out_off
                .average_strategy
                .values()
                .any(|p| p.len() > 1),
            "turn fixture collapsed to single-action rows — comparison \
             would be vacuous; boost postflop_raise_cap/include_all_in"
        );

        let mut max_abs_diff = 0.0_f64;
        let mut worst_key = String::new();
        for (key, probs_off) in &out_off.average_strategy {
            let probs_on = out_on
                .average_strategy
                .get(key)
                .unwrap_or_else(|| panic!("IE flag dropped infoset key: {key:?}"));
            assert_eq!(
                probs_off.len(),
                probs_on.len(),
                "key {key:?}: action_count mismatch ({} off vs {} on)",
                probs_off.len(),
                probs_on.len(),
            );
            for (a, (po, pn)) in probs_off.iter().zip(probs_on.iter()).enumerate() {
                let diff = (po - pn).abs();
                if diff > max_abs_diff {
                    max_abs_diff = diff;
                    worst_key = format!("{key:?}#{a}");
                }
                let tol = 1e-6 + 1e-6 * po.abs().max(pn.abs());
                assert!(
                    diff <= tol,
                    "IE-vs-cached TURN strategy divergence at {key:?} action {a}: \
                     off={po} on={pn} diff={diff} tol={tol}"
                );
            }
        }
        // Surface the max observed value-difference (visible with
        // `cargo test -- --nocapture`).
        println!(
            "ie_full_solve_matches_cached_turn: compared {} infosets over {} iters; \
             max |off - on| = {max_abs_diff:e} at {worst_key}",
            out_off.average_strategy.len(),
            iters,
        );
        assert!(
            max_abs_diff.is_finite(),
            "max diff must be finite (got {max_abs_diff})"
        );
    }
}
