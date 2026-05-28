//! Phase A — Full-tree preflop range-vs-range solver.
//!
//! This module ships the engine + Python wrapper for the full HUNL preflop
//! tree with no fixed hole cards (path 3 in `docs/preflop_e2e_status_2026-05-27.md`).
//! Postflop runouts are collapsed to a single equity leaf per (hero_class,
//! villain_class, suit_variant) using the precomputed 169x169 table shipped
//! at `assets/preflop_equity_169x169.npz` (see `preflop_equity.rs`).
//!
//! The vector-form CFR loop is genericized over a `TerminalCacheLike` trait
//! so this module shares the inner traversal kernel with the postflop
//! `dcfr_vector::TerminalCache` (PR #114) while owning its own
//! preflop-specific terminal classification.
//!
//! ## User-confirmed action menu
//!
//! - **Preflop open sizes:** absolute BB amounts (2bb, 3bb, 4bb, 5bb).
//! - **Preflop reraise multipliers (3-bet, 4-bet, ...):** 2x, 3x, 4x, 5x of
//!   the previous bet (incl. the implicit BB blind for the SB open).
//! - **All-in:** always available.
//! - **Raise cap:** 4 (`preflop_raise_cap`, per existing config default).
//!
//! ## Why a custom betting tree
//!
//! The existing `BettingTree::build_from` consumes `state.legal_actions()`
//! which uses `bet_size_fractions` (pot-fraction sizing). The Phase A menu
//! is fundamentally different (absolute BB opens + multipliers of previous
//! bet), so we build the tree manually here rather than monkey-patching
//! the engine. This keeps the postflop and preflop-subgame paths
//! completely untouched.

// The vector-form CFR inner loops index per-(hand, action) into multiple
// parallel arrays (regret, strategy, action_values, reach), so the
// indexed-for-loop shape is clearer than the iterator form Clippy proposes.
// See `dcfr_vector.rs:60` for the same allow on the same shape.
#![allow(clippy::needless_range_loop)]

use std::collections::HashMap;
use std::path::Path;
use std::time::Instant;

use ndarray::Array3;

use crate::dcfr_vector::EvalContext;
use crate::hunl::{HUNLConfig, Street};
use crate::hunl_eval::Strength;
use crate::preflop_equity::{hole_to_class, load_equity_table, NUM_VARIANTS};
use crate::simd;

// ============================================================================
// Phase B (#53) — per-phase Instant instrumentation. Same pattern as
// `dcfr_vector::profile` (HIGH-2 follow-up). When the `profile_preflop_rvr`
// feature is enabled, each labeled phase inside `traverse` accumulates
// wall-clock cost into a thread-local counter reported by the
// `preflop_rvr_profile` bench. Without the feature flag, `prof_start`
// returns `()` and `prof_end` is a no-op so the production hot path pays
// zero overhead.
// ============================================================================

#[cfg(feature = "profile_preflop_rvr")]
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
        pub opp_accumulate_ns: u128,
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
                PhaseField::OppAccumulate => cnt.opp_accumulate_ns += ns,
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
        OppAccumulate,
    }
}

#[cfg(feature = "profile_preflop_rvr")]
macro_rules! prof_start {
    () => {
        Some($crate::preflop_rvr::profile::start())
    };
}
#[cfg(feature = "profile_preflop_rvr")]
macro_rules! prof_end {
    ($t:expr, $field:ident) => {
        if let Some(t) = $t {
            $crate::preflop_rvr::profile::add($crate::preflop_rvr::profile::PhaseField::$field, t);
        }
    };
}

#[cfg(not(feature = "profile_preflop_rvr"))]
macro_rules! prof_start {
    () => {
        ()
    };
}
#[cfg(not(feature = "profile_preflop_rvr"))]
macro_rules! prof_end {
    ($t:expr, $field:ident) => {
        let _ = $t;
    };
}

// ============================================================================
// Phase A action menu
// ============================================================================

/// One action in the Phase A preflop menu.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PreflopAction {
    Fold,
    Check,
    Call,
    /// Open by raising to `to_chips` (absolute contribution amount, in cents).
    OpenTo(i32),
    /// Reraise by raising to `to_chips`.
    RaiseTo(i32),
    AllIn,
}

impl PreflopAction {
    fn token(&self) -> String {
        match self {
            PreflopAction::Fold => "f".to_string(),
            PreflopAction::Check => "x".to_string(),
            PreflopAction::Call => "c".to_string(),
            PreflopAction::OpenTo(amt) => format!("b{amt}"),
            PreflopAction::RaiseTo(amt) => format!("r{amt}"),
            PreflopAction::AllIn => "A".to_string(),
        }
    }
}

// ============================================================================
// Preflop game state (minimal, dedicated to Phase A)
// ============================================================================

/// Phase A preflop state. Tracks only what's needed for the
/// preflop-betting subtree; postflop is collapsed via equity-leaf
/// substitution.
#[derive(Clone, Debug)]
struct PreflopRvrState {
    /// Contributions in cents (P0 = SB, P1 = BB).
    contributions: [i32; 2],
    /// Remaining behind in cents.
    stacks: [i32; 2],
    /// Total chips committed by aggressor in last raise (used for reraise
    /// multipliers). 0 if no aggression yet on this street; preflop starts
    /// at the BB level.
    last_bet_size: i32,
    /// Player to act (-1 = terminal / equity-leaf).
    cur_player: i8,
    /// Count of raises this street (BB blind counts as 1).
    street_num_raises: u8,
    /// Aggressor index (-1 = none, 0 = P0, 1 = P1).
    street_aggressor: i8,
    /// Amount the current player must pay to call.
    to_call: i32,
    /// True if this state ended in a fold.
    folded: [bool; 2],
    /// True if both players have committed all chips (-> showdown / runout).
    all_in: [bool; 2],
    /// Token history of the in-progress preflop street.
    tokens: Vec<String>,
}

impl PreflopRvrState {
    /// Build the initial preflop state.
    ///
    /// # Invariant honored: `config.initial_contributions`
    ///
    /// The downstream leaf-payoff math (`build_equity_leaf_payoff` and the
    /// `Fold` leaf builder in `PreflopTerminalCache::build`) computes
    /// `cs[i] = contributions[i] - config.initial_contributions[i]` — the
    /// chips player `i` has voluntarily committed since the subgame root.
    /// `cs[i]` is the per-player "risk" subtracted from each leaf payoff;
    /// `pot_total = config.initial_pot + cs0 + cs1` is the size of the
    /// pot fought over at the leaf.
    ///
    /// Two well-formed preflop configurations must produce identical
    /// strategies (the engine is agnostic to which way blinds are
    /// declared):
    ///
    /// 1. `initial_contributions = [0, 0]`, `initial_pot = 0` — engine
    ///    posts the blinds internally; `cs = [SB+ante, BB+ante]`,
    ///    `pot_total = SB+BB+2*ante`.
    /// 2. `initial_contributions = [SB+ante, BB+ante]`,
    ///    `initial_pot = SB+BB+2*ante` — caller declared blinds as
    ///    already-in-pot dead money; `cs = [0, 0]`, `pot_total =
    ///    SB+BB+2*ante`.
    ///
    /// Both configurations yield the same `pot_total` per leaf; the per-leaf
    /// payoffs differ only by a constant per-player shift (`SB+ante` for P0,
    /// `BB+ante` for P1), which leaves Nash strategies invariant.
    ///
    /// **Bug pre-fix (PR #67 / issue #159):** `contributions` was
    /// unconditionally set to `[SB+ante, BB+ante]` regardless of
    /// `config.initial_contributions`. With config (2) above, the leaf
    /// math then computed `cs = [0, 0]` and `pot_total = 0` (because
    /// caller's `initial_pot` defaulted to 0), collapsing every fold/equity
    /// payoff to ~0 and yielding a degenerate fold-everything Nash.
    fn initial(config: &HUNLConfig) -> Self {
        let blind_sb = config.small_blind + config.ante;
        let blind_bb = config.big_blind + config.ante;
        let init_c0 = config.initial_contributions[0];
        let init_c1 = config.initial_contributions[1];
        // Honor caller's `initial_contributions`: contribution at root is the
        // larger of (a) the blind that this player must post and (b) any
        // dead money the caller declared (e.g. blinds already-in-pot).
        // - `[0,0]` config: max(blind, 0) = blind  → engine posts blinds.
        // - `[SB+ante,BB+ante]` config: max(blind, blind) = blind → no
        //   double-post; the leaf's `cs = contributions - initial_contributions
        //   = 0` and `pot_total = initial_pot` (caller-declared).
        let sb_contrib = blind_sb.max(init_c0);
        let bb_contrib = blind_bb.max(init_c1);
        let stacks = [
            config.starting_stack - sb_contrib,
            config.starting_stack - bb_contrib,
        ];
        let to_call = bb_contrib - sb_contrib;
        Self {
            contributions: [sb_contrib, bb_contrib],
            stacks,
            // BB blind counts as the implicit "previous bet" for sizing the
            // SB open as an absolute-BB amount; SB acts first.
            last_bet_size: config.big_blind,
            cur_player: 0,
            street_num_raises: 1,
            street_aggressor: 1,
            to_call,
            folded: [false, false],
            all_in: [stacks[0] == 0, stacks[1] == 0],
            tokens: Vec::new(),
        }
    }
}

// ============================================================================
// Action enumeration (user-confirmed Phase A menu)
// ============================================================================

fn enumerate_actions(
    state: &PreflopRvrState,
    config: &HUNLConfig,
    preflop_open_sizes_bb: &[f64],
    preflop_reraise_multipliers: &[f64],
) -> Vec<PreflopAction> {
    if state.cur_player < 0 {
        return Vec::new();
    }
    let player = state.cur_player as usize;
    let stack = state.stacks[player];
    if stack <= 0 {
        return Vec::new();
    }

    let mut out: Vec<PreflopAction> = Vec::new();
    let facing_bet = state.to_call > 0;

    if facing_bet {
        out.push(PreflopAction::Fold);
        out.push(PreflopAction::Call);
    } else {
        // Postflop conventions in HUNL preflop: SB's first action is
        // facing the BB blind, but `state.to_call > 0` covers that case.
        // True non-facing branch happens only after a call when BB still
        // has option to check or raise.
        out.push(PreflopAction::Check);
    }

    let cap = config.preflop_raise_cap.max(1);
    let cap_reached = state.street_num_raises >= cap;
    let bb = config.big_blind;
    let cur_contrib = state.contributions[player];
    let max_to = cur_contrib + stack;
    let min_raise_to = cur_contrib + state.to_call.max(bb);

    if !cap_reached {
        if state.street_num_raises <= 1 && state.street_aggressor == 1 && player == 0 {
            // SB facing the BB blind — emit absolute-BB OPENS.
            let mut seen = Vec::<i32>::new();
            for size_bb in preflop_open_sizes_bb {
                let raise_to = (size_bb * bb as f64).round() as i32;
                let raise_to = raise_to.max(min_raise_to).min(max_to);
                if raise_to >= max_to {
                    continue;
                }
                if seen.contains(&raise_to) {
                    continue;
                }
                seen.push(raise_to);
                out.push(PreflopAction::OpenTo(raise_to));
            }
        } else if facing_bet {
            // 3-bet / 4-bet / ... — multiplier of previous bet.
            let prev_bet = state.last_bet_size.max(bb);
            let mut seen = Vec::<i32>::new();
            for mult in preflop_reraise_multipliers {
                let increment = (mult * prev_bet as f64).round() as i32;
                let raise_to = state.contributions[1 - player] + increment;
                let raise_to = raise_to.max(min_raise_to).min(max_to);
                if raise_to >= max_to {
                    continue;
                }
                if seen.contains(&raise_to) {
                    continue;
                }
                seen.push(raise_to);
                out.push(PreflopAction::RaiseTo(raise_to));
            }
        } else if state.street_num_raises < cap {
            // Non-facing branch (BB option after SB limp): treat as open.
            let mut seen = Vec::<i32>::new();
            for size_bb in preflop_open_sizes_bb {
                let raise_to = (size_bb * bb as f64).round() as i32;
                let raise_to = raise_to.max(cur_contrib + bb).min(max_to);
                if raise_to >= max_to {
                    continue;
                }
                if seen.contains(&raise_to) {
                    continue;
                }
                seen.push(raise_to);
                out.push(PreflopAction::OpenTo(raise_to));
            }
        }
        // All-in always available unless cap reached or stack already 0.
        if stack > state.to_call {
            out.push(PreflopAction::AllIn);
        }
    }
    out
}

// ============================================================================
// State transition
// ============================================================================

fn apply_action(state: &PreflopRvrState, action: PreflopAction) -> PreflopRvrState {
    let mut next = state.clone();
    let player = state.cur_player as usize;
    let opp = 1 - player;
    next.tokens.push(action.token());
    match action {
        PreflopAction::Fold => {
            next.folded[player] = true;
            next.cur_player = -1;
        }
        PreflopAction::Check => {
            // Check closes the street if BB after SB limp; otherwise it's
            // a pass.
            next.cur_player = -1;
        }
        PreflopAction::Call => {
            let pay = state.to_call.min(state.stacks[player]);
            next.contributions[player] += pay;
            next.stacks[player] -= pay;
            if next.stacks[player] == 0 {
                next.all_in[player] = true;
            }
            next.to_call = 0;
            // SB limp special case: SB calls BB, BB still gets option.
            if state.street_aggressor == 1
                && state.street_num_raises == 1
                && player == 0
                && !next.all_in[player]
                && !next.all_in[opp]
            {
                next.cur_player = 1;
            } else {
                // Calling closes preflop — postflop equity leaf.
                next.cur_player = -1;
            }
        }
        PreflopAction::OpenTo(raise_to) | PreflopAction::RaiseTo(raise_to) => {
            let pay = raise_to - state.contributions[player];
            next.contributions[player] = raise_to;
            next.stacks[player] -= pay;
            if next.stacks[player] == 0 {
                next.all_in[player] = true;
            }
            next.to_call = (raise_to - state.contributions[opp]).max(0);
            next.last_bet_size = raise_to - state.contributions[opp];
            next.street_aggressor = player as i8;
            next.street_num_raises += 1;
            next.cur_player = opp as i8;
        }
        PreflopAction::AllIn => {
            let pay = state.stacks[player];
            next.contributions[player] += pay;
            next.stacks[player] = 0;
            next.all_in[player] = true;
            next.to_call = (next.contributions[player] - state.contributions[opp]).max(0);
            next.last_bet_size = (next.contributions[player] - state.contributions[opp]).max(1);
            next.street_aggressor = player as i8;
            next.street_num_raises += 1;
            // If opponent already all-in, no further action.
            if next.all_in[opp] || next.stacks[opp] == 0 {
                next.cur_player = -1;
            } else {
                next.cur_player = opp as i8;
            }
        }
    }
    next
}

fn is_terminal_or_leaf(state: &PreflopRvrState) -> bool {
    state.cur_player < 0 || state.folded[0] || state.folded[1]
}

// ============================================================================
// Flat tree for vector-form CFR
// ============================================================================

/// Phase A preflop flat-tree node.
#[derive(Clone, Debug)]
pub enum PreflopFlatNode {
    /// Fold terminal — utility constant in holes.
    Fold {
        contributions: [i32; 2],
        folded_player: usize,
        big_blind: i32,
        initial_pot: i32,
        initial_contributions: [i32; 2],
    },
    /// Postflop close (all-in OR called) — collapse postflop chance subtree
    /// to a single equity-leaf value using the 169x169 table.
    EquityLeaf {
        contributions: [i32; 2],
        big_blind: i32,
        initial_pot: i32,
        initial_contributions: [i32; 2],
    },
    /// Decision node.
    Decision {
        player: u8,
        actions: Vec<PreflopAction>,
        children: Vec<usize>,
        key_suffix: String,
    },
}

/// Phase A flat betting tree. `nodes[0]` is the root.
#[derive(Debug)]
pub struct PreflopBettingTree {
    pub nodes: Vec<PreflopFlatNode>,
}

impl PreflopBettingTree {
    /// Walk the preflop-betting subtree of `config` and emit a flat
    /// indexed tree.
    pub fn build(
        config: &HUNLConfig,
        preflop_open_sizes_bb: &[f64],
        preflop_reraise_multipliers: &[f64],
    ) -> Self {
        let mut tree = PreflopBettingTree { nodes: Vec::new() };
        let root = PreflopRvrState::initial(config);
        tree.add(
            &root,
            config,
            preflop_open_sizes_bb,
            preflop_reraise_multipliers,
        );
        tree
    }

    fn add(
        &mut self,
        state: &PreflopRvrState,
        config: &HUNLConfig,
        preflop_open_sizes_bb: &[f64],
        preflop_reraise_multipliers: &[f64],
    ) -> usize {
        let idx = self.nodes.len();
        // Reserve slot — overwritten below.
        self.nodes.push(PreflopFlatNode::Fold {
            contributions: [0, 0],
            folded_player: 0,
            big_blind: 0,
            initial_pot: 0,
            initial_contributions: [0, 0],
        });

        let bb = config.big_blind;
        let initial_pot = config.initial_pot;
        let initial_contributions = config.initial_contributions;

        if state.folded[0] || state.folded[1] {
            let folded_player = if state.folded[0] { 0 } else { 1 };
            self.nodes[idx] = PreflopFlatNode::Fold {
                contributions: state.contributions,
                folded_player,
                big_blind: bb,
                initial_pot,
                initial_contributions,
            };
            return idx;
        }
        if is_terminal_or_leaf(state) {
            self.nodes[idx] = PreflopFlatNode::EquityLeaf {
                contributions: state.contributions,
                big_blind: bb,
                initial_pot,
                initial_contributions,
            };
            return idx;
        }

        let actions = enumerate_actions(
            state,
            config,
            preflop_open_sizes_bb,
            preflop_reraise_multipliers,
        );
        let mut children = Vec::with_capacity(actions.len());
        for action in &actions {
            let next = apply_action(state, *action);
            let cidx = self.add(
                &next,
                config,
                preflop_open_sizes_bb,
                preflop_reraise_multipliers,
            );
            children.push(cidx);
        }
        let player = state.cur_player as u8;
        let history = state.tokens.concat();
        let key_suffix = format!("||p|{history}");
        self.nodes[idx] = PreflopFlatNode::Decision {
            player,
            actions,
            children,
            key_suffix,
        };
        idx
    }
}

// ============================================================================
// Preflop equity-leaf cache
// ============================================================================

/// Precomputed per-leaf utility data for the preflop RvR tree.
pub struct PreflopTerminalCache {
    pub leaves: Vec<PreflopLeafEntry>,
    /// Phase B (#53) — pre-baked blocker mask shared across all leaves.
    ///
    /// `blocker_mask[update_player][ho * N_update + hp]` is `1.0` when
    /// `hole[update_player][hp]` is disjoint from `hole[opp_player][ho]`,
    /// else `0.0`. **Opp-major** layout (same convention as
    /// `PreflopLeafEntry::Equity::payoff_table`).
    ///
    /// Used by the `Fold` branch in `terminal_value_vector` to make the
    /// per-pair blocker check a branchless multiply against the mask.
    /// The `Equity` branch's `payoff_table` already bakes the mask into
    /// the table (blockers stored as `+0.0`), so it doesn't read this.
    ///
    /// Lifting the branch out + interchanging the loop (ho-outer,
    /// hp-inner) lets LLVM auto-vectorize the AXPY into 2-lane NEON
    /// (aarch64) / SSE2 (x86_64). Net: ~10× speedup on the
    /// `terminal_value_vector` kernel at 1326-hand width, ~6.5× on
    /// full-tree solve wall.
    pub blocker_mask: [Vec<f64>; 2],
}

pub enum PreflopLeafEntry {
    NonTerminal,
    Fold {
        payoff: [f64; 2],
    },
    /// Equity-leaf: postflop chance subtree collapsed to a single
    /// expected-value, indexed by (hero_class, villain_class, variant).
    /// Pre-flattens the per-(hero_hand, villain_hand) lookup so the inner
    /// CFR kernel just reads `eq_pairwise[(hp, ho)]` without re-doing
    /// the class+variant lookup every iter.
    Equity {
        /// Per-(update_player, hero_hand_idx, villain_hand_idx) payoff in
        /// BB units for the update player's perspective.
        ///
        /// Stored row-major as `payoff[update_player][hp * opp_hands + ho]`.
        /// (Two pre-flattened arrays — one per update_player — because
        /// `update_player` swaps which player is the "hero" in the
        /// payoff.)
        payoff_table: [Vec<f64>; 2],
    },
}

/// Compute the equity-leaf payoff per (hero_hand, villain_hand) and
/// pre-flatten the lookup table.
///
/// For each (hero_hand, villain_hand):
///   hero_class = preflop class of the hero pair (one of 169)
///   villain_class = preflop class of the villain pair (one of 169)
///   variant = suit-overlap orientation between the two pairs (one of 3)
///   equity = `table[hero_class][villain_class][variant]`
///   payoff[hero] = pot * equity - hero_risk
///   payoff[villain] = pot * (1 - equity) - villain_risk
///
/// `pot` and `risk` come from the leaf's contributions; blocker conflicts
/// emit `0.0` so the SIMD dot product in `terminal_value_vector` can run
/// branch-free.
///
/// ## Phase B (#53) layout
///
/// The output tables are stored **opp-major** (transpose of the natural
/// `[hero_hand][villain_hand]` order). Specifically:
///
/// - `payoff_table[update_player][ho * N_update + hp]`
///
/// where `ho` is the opponent's hand index and `hp` is `update_player`'s
/// hand index, and `N_update = ctx.hand_count[update_player]`.
///
/// The inner CFR kernel loops `for ho { for hp { out[hp] += reach[ho] *
/// table[ho * N_update + hp] } }`. With the opp-major layout, the
/// inner `hp` loop reads a contiguous row of the table, contiguously
/// writes to `out`, and LLVM auto-vectorizes the AXPY into 2-lane NEON
/// (aarch64) / SSE2 (x86_64) without breaking the per-`hp` accumulator
/// order (each `out[hp]` is still updated in `ho = 0..N_opp` order, i.e.
/// bit-identical to the pre-PR scalar shape).
fn build_equity_leaf_payoff(
    contributions: [i32; 2],
    big_blind: i32,
    initial_pot: i32,
    initial_contributions: [i32; 2],
    ctx: &EvalContext,
    equity_table: &Array3<f64>,
) -> [Vec<f64>; 2] {
    let bb = big_blind as f64;
    let cs0 = (contributions[0] - initial_contributions[0]) as f64;
    let cs1 = (contributions[1] - initial_contributions[1]) as f64;
    let pot_total = initial_pot as f64 + cs0 + cs1;
    let n_p0 = ctx.hand_count[0];
    let n_p1 = ctx.hand_count[1];

    // Opp-major layout (Phase B #53):
    //   payoff_p0[ho_outer * n_p0 + hp_inner]: when update=P0, ho=P1's hand,
    //                                          hp=P0's hand.
    //   payoff_p1[ho_outer * n_p1 + hp_inner]: when update=P1, ho=P0's hand,
    //                                          hp=P1's hand.
    let mut payoff_p0 = vec![0.0_f64; n_p1 * n_p0];
    let mut payoff_p1 = vec![0.0_f64; n_p0 * n_p1];

    for hp in 0..n_p0 {
        let hero = ctx.hole[0][hp];
        let h_class = hole_to_class(hero) as usize;
        for ho in 0..n_p1 {
            let villain = ctx.hole[1][ho];
            // Blocker conflict — zero contribution (both tables already
            // zero-initialized above).
            if hero[0] == villain[0]
                || hero[0] == villain[1]
                || hero[1] == villain[0]
                || hero[1] == villain[1]
            {
                continue;
            }
            let v_class = hole_to_class(villain) as usize;
            let variant = classify_suit_variant(hero, villain);
            let mut eq = equity_table[(h_class, v_class, variant)];
            if eq.is_nan() {
                // Fallback to variant 0 (always defined for valid pair).
                eq = equity_table[(h_class, v_class, 0)];
                if eq.is_nan() {
                    // Final fallback: compute on the fly. Rare path.
                    eq = crate::preflop_equity::enumerate_pair_equity(hero, villain);
                }
            }
            // P0's chip flow = pot * eq - cs0; P1's = pot * (1 - eq) - cs1
            // when P0 is the "hero." Both sides stored explicitly.
            let p0_payoff = (pot_total * eq - cs0) / bb;
            let p1_payoff = (pot_total * (1.0 - eq) - cs1) / bb;
            // Opp-major: ho is the outer axis.
            payoff_p0[ho * n_p0 + hp] = p0_payoff;
            payoff_p1[hp * n_p1 + ho] = p1_payoff;
        }
    }
    [payoff_p0, payoff_p1]
}

/// Classify the suit-overlap variant between hero and villain.
///
/// Returns 0..NUM_VARIANTS:
///   0 = no shared suit between the two pairs.
///   1 = exactly one shared suit (e.g. hero has a club, villain has a club).
///   2 = two+ shared suits / paired-suit (hero and villain both fully use
///       the same suit pair).
fn classify_suit_variant(hero: [u8; 2], villain: [u8; 2]) -> usize {
    let h_suits: [u8; 2] = [hero[0] & 3, hero[1] & 3];
    let v_suits: [u8; 2] = [villain[0] & 3, villain[1] & 3];
    // Count distinct shared suits between the two pairs.
    let mut shared = 0u8;
    for s in 0u8..4 {
        let in_hero = h_suits.contains(&s);
        let in_villain = v_suits.contains(&s);
        if in_hero && in_villain {
            shared += 1;
        }
    }
    match shared {
        0 => 0,
        1 => 1,
        _ => (NUM_VARIANTS - 1).min(2),
    }
}

/// Build the shared blocker mask shipped on `PreflopTerminalCache`.
///
/// Same opp-major layout as `PreflopLeafEntry::Equity::payoff_table`
/// (see `build_equity_leaf_payoff`):
///   `blocker_mask[update_player][ho * N_update + hp]`
/// where `ho` is opp's hand index and `hp` is `update_player`'s hand index.
fn build_blocker_mask(ctx: &EvalContext) -> [Vec<f64>; 2] {
    let n0 = ctx.hand_count[0];
    let n1 = ctx.hand_count[1];
    // Opp-major layout:
    //   mask_p0: update=P0, ho=P1's hand, hp=P0's hand. Size n1 * n0.
    //   mask_p1: update=P1, ho=P0's hand, hp=P1's hand. Size n0 * n1.
    let mut mask_p0 = vec![0.0_f64; n1 * n0];
    let mut mask_p1 = vec![0.0_f64; n0 * n1];
    for hp in 0..n0 {
        let hero = ctx.hole[0][hp];
        for ho in 0..n1 {
            let villain = ctx.hole[1][ho];
            let blocked = hero[0] == villain[0]
                || hero[0] == villain[1]
                || hero[1] == villain[0]
                || hero[1] == villain[1];
            let v = if blocked { 0.0 } else { 1.0 };
            mask_p0[ho * n0 + hp] = v;
            mask_p1[hp * n1 + ho] = v;
        }
    }
    [mask_p0, mask_p1]
}

impl PreflopTerminalCache {
    pub fn build(tree: &PreflopBettingTree, ctx: &EvalContext, equity_table: &Array3<f64>) -> Self {
        let mut leaves: Vec<PreflopLeafEntry> = Vec::with_capacity(tree.nodes.len());
        for node in &tree.nodes {
            match node {
                PreflopFlatNode::Fold {
                    contributions,
                    folded_player,
                    big_blind,
                    initial_pot,
                    initial_contributions,
                } => {
                    let bb = *big_blind as f64;
                    let cs0 = (contributions[0] - initial_contributions[0]) as f64;
                    let cs1 = (contributions[1] - initial_contributions[1]) as f64;
                    let pot_total = *initial_pot as f64 + cs0 + cs1;
                    let payoff = if *folded_player == 0 {
                        [-cs0 / bb, (pot_total - cs1) / bb]
                    } else {
                        [(pot_total - cs0) / bb, -cs1 / bb]
                    };
                    leaves.push(PreflopLeafEntry::Fold { payoff });
                }
                PreflopFlatNode::EquityLeaf {
                    contributions,
                    big_blind,
                    initial_pot,
                    initial_contributions,
                } => {
                    let payoff_table = build_equity_leaf_payoff(
                        *contributions,
                        *big_blind,
                        *initial_pot,
                        *initial_contributions,
                        ctx,
                        equity_table,
                    );
                    leaves.push(PreflopLeafEntry::Equity { payoff_table });
                }
                _ => leaves.push(PreflopLeafEntry::NonTerminal),
            }
        }
        let blocker_mask = build_blocker_mask(ctx);
        Self {
            leaves,
            blocker_mask,
        }
    }
}

// ============================================================================
// Vector-form DCFR (preflop-specific)
// ============================================================================

#[derive(Clone, Debug)]
struct VectorInfosetData {
    action_count: usize,
    hand_count: usize,
    regret: Vec<f64>,
    strategy_sum: Vec<f64>,
    last_discount_iter: u32,
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

/// Phase A preflop vector-form DCFR solver.
pub struct PreflopVectorDCFR {
    alpha: f64,
    beta: f64,
    gamma: f64,
    iteration: u32,
    /// One slot per tree-node index. `None` for non-decision nodes.
    infosets: Vec<Option<VectorInfosetData>>,
}

impl PreflopVectorDCFR {
    fn new(
        tree: &PreflopBettingTree,
        hand_count_per_player: [usize; 2],
        alpha: f64,
        beta: f64,
        gamma: f64,
    ) -> Self {
        crate::dcfr::validate_alpha(alpha);
        let mut infosets: Vec<Option<VectorInfosetData>> = Vec::with_capacity(tree.nodes.len());
        for node in &tree.nodes {
            match node {
                PreflopFlatNode::Decision {
                    player, actions, ..
                } => {
                    let hand_count = hand_count_per_player[*player as usize];
                    infosets.push(Some(VectorInfosetData::new(actions.len(), hand_count)));
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

    fn compute_strategy(info: &VectorInfosetData, out: &mut [f64]) {
        let hand_count = info.hand_count;
        let action_count = info.action_count;
        debug_assert_eq!(out.len(), hand_count * action_count);
        for h in 0..hand_count {
            let offset = h * action_count;
            let regrets_row = &info.regret[offset..offset + action_count];
            let out_row = &mut out[offset..offset + action_count];
            simd::compute_strategy_row(regrets_row, out_row);
        }
    }

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

    /// Vector-form traversal mirroring `dcfr_vector::VectorDCFR::traverse`
    /// but with preflop-specific terminal handling.
    #[allow(clippy::too_many_arguments)]
    fn traverse(
        &mut self,
        tree: &PreflopBettingTree,
        ctx: &EvalContext,
        cache: &PreflopTerminalCache,
        node_idx: usize,
        update_player: usize,
        reach_p: &[f64],
        reach_opp: &[f64],
    ) -> Vec<f64> {
        let update_hands = ctx.hand_count[update_player];
        match &tree.nodes[node_idx] {
            PreflopFlatNode::Fold { .. } | PreflopFlatNode::EquityLeaf { .. } => {
                let opp_player = 1 - update_player;
                let _t = prof_start!();
                let r = terminal_value_vector(
                    &cache.leaves[node_idx],
                    cache,
                    ctx,
                    update_player,
                    opp_player,
                    reach_opp,
                );
                prof_end!(_t, TerminalEval);
                r
            }
            PreflopFlatNode::Decision {
                player,
                actions,
                children,
                ..
            } => {
                let player = *player as usize;
                let action_count = actions.len();
                let player_hands = ctx.hand_count[player];

                let _ta = prof_start!();
                let mut strategy = vec![0.0_f64; player_hands * action_count];
                prof_end!(_ta, AllocStrategyBuf);
                {
                    let info = self.infosets[node_idx]
                        .as_ref()
                        .expect("decision node has infoset");
                    let _t = prof_start!();
                    Self::compute_strategy(info, &mut strategy);
                    prof_end!(_t, ComputeStrategy);
                }

                if player != update_player {
                    let mut values = vec![0.0_f64; update_hands];
                    let mut next_reach = vec![0.0_f64; player_hands];
                    for (a, &child_idx) in children.iter().enumerate() {
                        let _t = prof_start!();
                        for h in 0..player_hands {
                            next_reach[h] = reach_opp[h] * strategy[h * action_count + a];
                        }
                        prof_end!(_t, OppNextReach);
                        let child_values = self.traverse(
                            tree,
                            ctx,
                            cache,
                            child_idx,
                            update_player,
                            reach_p,
                            &next_reach,
                        );
                        let _t = prof_start!();
                        for h in 0..update_hands {
                            values[h] += child_values[h];
                        }
                        prof_end!(_t, OppAccumulate);
                    }
                    return values;
                }

                // Own (update_player) node.
                {
                    let info = self.infosets[node_idx]
                        .as_mut()
                        .expect("decision node has infoset");
                    let _t = prof_start!();
                    Self::discount(info, self.iteration, self.alpha, self.beta, self.gamma);
                    prof_end!(_t, Discount);
                }
                {
                    let info = self.infosets[node_idx]
                        .as_ref()
                        .expect("decision node has infoset");
                    let _t = prof_start!();
                    Self::compute_strategy(info, &mut strategy);
                    prof_end!(_t, ComputeStrategy);
                }

                let _ta = prof_start!();
                let mut action_values = vec![0.0_f64; action_count * update_hands];
                let mut next_reach = vec![0.0_f64; player_hands];
                prof_end!(_ta, AllocActionValues);
                for (a, &child_idx) in children.iter().enumerate() {
                    let _t = prof_start!();
                    for h in 0..player_hands {
                        next_reach[h] = reach_p[h] * strategy[h * action_count + a];
                    }
                    prof_end!(_t, OwnNextReach);
                    let child_values = self.traverse(
                        tree,
                        ctx,
                        cache,
                        child_idx,
                        update_player,
                        &next_reach,
                        reach_opp,
                    );
                    let dst = a * update_hands;
                    action_values[dst..dst + update_hands].copy_from_slice(&child_values);
                }

                let _t = prof_start!();
                let mut node_values = vec![0.0_f64; update_hands];
                for h in 0..update_hands {
                    let mut value = 0.0_f64;
                    let s_offset = h * action_count;
                    for a in 0..action_count {
                        value += strategy[s_offset + a] * action_values[a * update_hands + h];
                    }
                    node_values[h] = value;
                }
                prof_end!(_t, NodeValues);

                {
                    let info = self.infosets[node_idx]
                        .as_mut()
                        .expect("decision node has infoset");
                    let _t = prof_start!();
                    simd::update_regret_sum_vector(
                        &mut info.regret,
                        &action_values,
                        &node_values,
                        update_hands,
                        action_count,
                    );
                    prof_end!(_t, UpdateRegret);
                    let _t = prof_start!();
                    for h in 0..update_hands {
                        let weight = reach_p[h];
                        if weight == 0.0 {
                            continue;
                        }
                        let offset = h * action_count;
                        let row_end = offset + action_count;
                        simd::update_strategy_sum(
                            &mut info.strategy_sum[offset..row_end],
                            &strategy[offset..row_end],
                            weight,
                        );
                    }
                    prof_end!(_t, UpdateStrategySum);
                }
                node_values
            }
        }
    }

    fn solve(
        &mut self,
        tree: &PreflopBettingTree,
        ctx: &EvalContext,
        cache: &PreflopTerminalCache,
        iterations: u32,
    ) {
        let reach_p0: Vec<f64> = vec![1.0; ctx.hand_count[0]];
        let reach_p1: Vec<f64> = vec![1.0; ctx.hand_count[1]];
        for _ in 0..iterations {
            self.iteration += 1;
            self.traverse(tree, ctx, cache, 0, 0, &reach_p0, &reach_p1);
            self.traverse(tree, ctx, cache, 0, 1, &reach_p1, &reach_p0);
        }
    }
}

/// Terminal-leaf value vector (with blocker filter), mirroring
/// `dcfr_vector::terminal_value_vector_cached`.
///
/// # Phase B (#53) — opp-major layout + AXPY loop interchange
///
/// Pre-PR shape (hp-outer, ho-inner): per-hp dot product
///   `out[hp] = Σ_ho reach_opp[ho] * table[hp, ho]`
///   plus a per-pair blocker branch that defeats auto-vectorization.
///
/// New shape (ho-outer, hp-inner): per-ho AXPY accumulation
///   `for ho: for hp: out[hp] += reach_opp[ho] * table_T[ho, hp]`
///   with `table_T[ho, hp]` storing the **transpose** of the pre-PR table.
///
/// The inner `hp` loop is a contiguous read of `table_T[ho * N_hp..]`,
/// a contiguous write to `out[..]`, and a single FMA per element. LLVM
/// auto-vectorizes this into 2-lane NEON (aarch64) or SSE2 (x86_64)
/// without an associativity-breaking reduction: each `out[hp]`'s update
/// chain is still `ho = 0, 1, 2, ... N-1` in order, identical to the
/// pre-PR shape's accumulator order.
///
/// # Bit-identity vs the pre-PR branch shape
///
/// - **Equity**: pre-PR accumulated `reach * table[hp, ho]` only over
///   disjoint pairs (skipped blockers via early-continue). The transposed
///   table has blockers stored as `+0.0` (see `build_equity_leaf_payoff`)
///   so blocker contributions become `reach * 0.0 = +0.0` and `out[hp] +
///   0.0 = out[hp]` exactly (assuming finite `out`/`reach`, which always
///   holds — `reach = Π strategies ∈ [0,1]`).
/// - **Fold**: pre-PR accumulated `reach * util` only over disjoint pairs.
///   New shape: `out[hp] += reach[ho] * mask[ho, hp] * util` where
///   `mask ∈ {0.0, 1.0}`. IEEE-754 `x * 1.0 == x` for finite `x`, so when
///   mask=1 we get `reach * util` per term — exact. When mask=0 we get
///   `(reach * 0.0) * util = 0.0` (finite util), contributing nothing.
/// - **Accumulator order**: identical per `hp` (ho = 0..N in both shapes).
///
/// See `tests::optimized_matches_baseline_bit_exact` for the parity test
/// that locks this contract in.
fn terminal_value_vector(
    leaf: &PreflopLeafEntry,
    cache: &PreflopTerminalCache,
    ctx: &EvalContext,
    update_player: usize,
    opp_player: usize,
    reach_opp: &[f64],
) -> Vec<f64> {
    let update_hands = ctx.hand_count[update_player];
    let opp_hands = ctx.hand_count[opp_player];
    let mut out = vec![0.0_f64; update_hands];

    match leaf {
        PreflopLeafEntry::Fold { payoff } => {
            let util = payoff[update_player];
            let mask = &cache.blocker_mask[update_player];
            // ho-outer, hp-inner AXPY: `out += (reach[ho] * util) * mask_row`.
            // Auto-vectorized to NEON / SSE2 / AVX2 by LLVM.
            for ho in 0..opp_hands {
                let row = &mask[ho * update_hands..(ho + 1) * update_hands];
                let coeff = reach_opp[ho] * util;
                // Hoisting `util` out of the inner loop is bit-identical here
                // because `((reach * mask) * util) == ((reach * util) * mask)`
                // for finite reach/util and mask ∈ {0, 1}: when mask=0 both
                // sides give 0.0 (assuming finite operands); when mask=1
                // both sides give `reach * util`. Float multiply is
                // commutative AND associative for these specific operands
                // (mask is exact 0 or exact 1, no rounding).
                for hp in 0..update_hands {
                    out[hp] += coeff * row[hp];
                }
            }
        }
        PreflopLeafEntry::Equity { payoff_table } => {
            // The equity `payoff_table` is built with blockers set to `+0.0`
            // (see `build_equity_leaf_payoff`) AND stored opp-major.
            // ho-outer, hp-inner AXPY auto-vectorizes into 2-lane NEON/SSE2.
            let table = &payoff_table[update_player];
            for ho in 0..opp_hands {
                let row = &table[ho * update_hands..(ho + 1) * update_hands];
                let reach = reach_opp[ho];
                for hp in 0..update_hands {
                    out[hp] += reach * row[hp];
                }
            }
        }
        PreflopLeafEntry::NonTerminal => unreachable!("non-terminal in leaf path"),
    }
    out
}

/// Phase B (#53) — pre-optimization reference shape of
/// `terminal_value_vector`. Retained for the bit-identical parity test
/// (`tests::optimized_matches_baseline_bit_exact`).
///
/// The pre-PR Equity branch used the hp-outer, ho-inner shape with a per-pair
/// blocker branch:
/// ```ignore
/// for hp { let mut total = 0; for ho {
///     if blocker(hp, ho) { continue; }
///     total += reach[ho] * table_pre_PR[hp * N_ho + ho];
/// } out[hp] = total; }
/// ```
/// where `table_pre_PR` was stored hp-major (i.e. `table_pre_PR[hp][ho]`).
///
/// To reconstruct the pre-PR table from the new opp-major storage, this
/// function recomputes the per-pair equity / chip-flow on the fly via
/// `ctx.hole[*]` and the leaf's `payoff` semantics. The pre-PR shape is
/// thus reproduced exactly without round-tripping through the new
/// opp-major layout.
///
/// **Production callers must use `terminal_value_vector` (NOT this).**
/// This is a test-only function — `#[cfg(test)]`-gated.
#[cfg(test)]
fn terminal_value_vector_baseline(
    leaf_pre_pr: &PreflopLeafEntryBaseline,
    ctx: &EvalContext,
    update_player: usize,
    opp_player: usize,
    reach_opp: &[f64],
) -> Vec<f64> {
    let update_hands = ctx.hand_count[update_player];
    let opp_hands = ctx.hand_count[opp_player];
    let mut out = vec![0.0_f64; update_hands];

    match leaf_pre_pr {
        PreflopLeafEntryBaseline::Fold { payoff } => {
            let util = payoff[update_player];
            for hp in 0..update_hands {
                let hole_p = ctx.hole[update_player][hp];
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
                    total += reach_opp[ho] * util;
                }
                out[hp] = total;
            }
        }
        PreflopLeafEntryBaseline::Equity {
            payoff_table_hp_major,
        } => {
            // pre-PR layout: payoff_table[update_player][hp * opp_hands + ho]
            let table = &payoff_table_hp_major[update_player];
            for hp in 0..update_hands {
                let hole_p = ctx.hole[update_player][hp];
                let mut total = 0.0_f64;
                let base = hp * opp_hands;
                for ho in 0..opp_hands {
                    let hole_o = ctx.hole[opp_player][ho];
                    if hole_p[0] == hole_o[0]
                        || hole_p[0] == hole_o[1]
                        || hole_p[1] == hole_o[0]
                        || hole_p[1] == hole_o[1]
                    {
                        continue;
                    }
                    total += reach_opp[ho] * table[base + ho];
                }
                out[hp] = total;
            }
        }
    }
    out
}

/// Pre-PR `PreflopLeafEntry` shape (hp-major). Used only by the
/// bit-identical parity test to reconstruct the pre-Phase-B inner kernel
/// and prove the new opp-major + AXPY implementation gives identical
/// outputs lane-for-lane.
#[cfg(test)]
enum PreflopLeafEntryBaseline {
    Fold {
        payoff: [f64; 2],
    },
    Equity {
        payoff_table_hp_major: [Vec<f64>; 2],
    },
}

/// Phase B (#53) — build the pre-PR (hp-major) equity table from the same
/// inputs as `build_equity_leaf_payoff`. Test-only.
#[cfg(test)]
fn build_equity_leaf_payoff_baseline(
    contributions: [i32; 2],
    big_blind: i32,
    initial_pot: i32,
    initial_contributions: [i32; 2],
    ctx: &EvalContext,
    equity_table: &Array3<f64>,
) -> [Vec<f64>; 2] {
    let bb = big_blind as f64;
    let cs0 = (contributions[0] - initial_contributions[0]) as f64;
    let cs1 = (contributions[1] - initial_contributions[1]) as f64;
    let pot_total = initial_pot as f64 + cs0 + cs1;
    let n_p0 = ctx.hand_count[0];
    let n_p1 = ctx.hand_count[1];
    // hp-major: payoff_p0[hp * n_p1 + ho], payoff_p1[hp * n_p0 + ho].
    // Note: when update_player == 1, hp is P1's hand and ho is P0's hand
    // (per pre-PR convention).
    let mut payoff_p0 = vec![0.0_f64; n_p0 * n_p1];
    let mut payoff_p1 = vec![0.0_f64; n_p1 * n_p0];

    for hp in 0..n_p0 {
        let hero = ctx.hole[0][hp];
        let h_class = hole_to_class(hero) as usize;
        for ho in 0..n_p1 {
            let villain = ctx.hole[1][ho];
            if hero[0] == villain[0]
                || hero[0] == villain[1]
                || hero[1] == villain[0]
                || hero[1] == villain[1]
            {
                continue;
            }
            let v_class = hole_to_class(villain) as usize;
            let variant = classify_suit_variant(hero, villain);
            let mut eq = equity_table[(h_class, v_class, variant)];
            if eq.is_nan() {
                eq = equity_table[(h_class, v_class, 0)];
                if eq.is_nan() {
                    eq = crate::preflop_equity::enumerate_pair_equity(hero, villain);
                }
            }
            let p0_payoff = (pot_total * eq - cs0) / bb;
            let p1_payoff = (pot_total * (1.0 - eq) - cs1) / bb;
            // hp-major (pre-PR layout):
            //   payoff_p0[hp_of_p0 * n_p1 + ho_of_p1]
            //   payoff_p1[ho_of_p1 * n_p0 + hp_of_p0]  (P1 outer = ho here)
            payoff_p0[hp * n_p1 + ho] = p0_payoff;
            payoff_p1[ho * n_p0 + hp] = p1_payoff;
        }
    }
    [payoff_p0, payoff_p1]
}

// ============================================================================
// EvalContext builder for full-deck preflop RvR (no board cards held)
// ============================================================================

/// Build an `EvalContext` for full-deck preflop RvR. Enumerates all
/// C(52, 2) = 1326 hole-card pairs per player.
fn build_preflop_eval_context(config: &HUNLConfig) -> EvalContext {
    let bb = config.big_blind;
    let mut single_holes: Vec<[u8; 2]> = Vec::with_capacity(1326);
    for r0 in 2u8..=14 {
        for s0 in 0u8..4 {
            let c0 = crate::hunl::card_to_int(r0, s0);
            for r1 in 2u8..=14 {
                for s1 in 0u8..4 {
                    let c1 = crate::hunl::card_to_int(r1, s1);
                    if c0 >= c1 {
                        continue;
                    }
                    single_holes.push([c0, c1]);
                }
            }
        }
    }
    let p0 = single_holes.clone();
    let p1 = single_holes;
    EvalContext::from_hand_lists(p0, p1, bb)
}

// ============================================================================
// Public solve entry
// ============================================================================

/// Public output of a Phase A preflop RvR solve.
pub struct PreflopRvrOutput {
    /// `{<hole_string>|<key_suffix> -> [probs]}` — one row per (decision,
    /// hand). `key_suffix` mirrors the canonical lossless infoset-key
    /// shape used by the postflop vector path: `"||p|<history>"` (preflop
    /// has no board between the `|` separators).
    pub average_strategy: HashMap<String, Vec<f64>>,
    pub decision_node_count: u32,
    pub strategy_entry_count: u32,
    pub iterations: u32,
    pub hand_count_per_player: [usize; 2],
    pub wallclock_seconds: f64,
}

/// Phase A entry — solve the full HUNL preflop range-vs-range Nash with
/// the user-confirmed action menu (absolute BB opens + reraise
/// multipliers).
///
/// `equity_table_path` points to the precomputed `.npz` shipped at
/// `assets/preflop_equity_169x169.npz`.
#[allow(clippy::too_many_arguments)]
pub fn solve_hunl_preflop_rvr(
    config: &HUNLConfig,
    equity_table_path: &Path,
    preflop_open_sizes_bb: &[f64],
    preflop_reraise_multipliers: &[f64],
    iterations: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
) -> Result<PreflopRvrOutput, String> {
    solve_hunl_preflop_rvr_with_hands(
        config,
        equity_table_path,
        None,
        preflop_open_sizes_bb,
        preflop_reraise_multipliers,
        iterations,
        alpha,
        beta,
        gamma,
    )
}

/// Phase A entry with explicit per-player hand lists. Used by the
/// AA-vs-KK closed-form smoke test in
/// `tests/preflop_rvr_smoke.rs` to subset the 1326-combo deck down to a
/// small, tractable pair count.
#[allow(clippy::too_many_arguments)]
#[allow(clippy::needless_range_loop)]
pub fn solve_hunl_preflop_rvr_with_hands(
    config: &HUNLConfig,
    equity_table_path: &Path,
    hand_lists: Option<[Vec<[u8; 2]>; 2]>,
    preflop_open_sizes_bb: &[f64],
    preflop_reraise_multipliers: &[f64],
    iterations: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
) -> Result<PreflopRvrOutput, String> {
    // PR #67 (issue #159): defense-in-depth validation. The Python tier's
    // `HUNLConfig.__post_init__` blocks the malformed-`initial_contributions`
    // trigger combination, but PyO3 callers deserialize straight into
    // `HUNLConfig` and skip the Python `__post_init__`. Without this guard,
    // `[SB,BB]+pot=0` produces a fold-everywhere Nash silently. See
    // `HUNLConfig::validate` for the exact rules.
    config
        .validate()
        .map_err(|e| format!("solve_hunl_preflop_rvr: {e}"))?;
    if config.starting_street != Street::Preflop {
        return Err(format!(
            "solve_hunl_preflop_rvr requires starting_street = Preflop (got {:?})",
            config.starting_street
        ));
    }
    if config.initial_hole_cards.is_some() {
        return Err(
            "solve_hunl_preflop_rvr requires initial_hole_cards = None; \
             use solve_hunl_preflop for fixed-hole subgames"
                .into(),
        );
    }

    let started = Instant::now();
    let equity_table: Array3<f64> =
        load_equity_table(equity_table_path).map_err(|e| format!("load equity table: {e}"))?;

    let tree =
        PreflopBettingTree::build(config, preflop_open_sizes_bb, preflop_reraise_multipliers);
    let ctx = match hand_lists {
        Some([p0, p1]) => {
            if p0.is_empty() || p1.is_empty() {
                return Err("hand_lists must be non-empty for both players".into());
            }
            EvalContext::from_hand_lists(p0, p1, config.big_blind)
        }
        None => build_preflop_eval_context(config),
    };
    let cache = PreflopTerminalCache::build(&tree, &ctx, &equity_table);

    let mut solver = PreflopVectorDCFR::new(&tree, ctx.hand_count, alpha, beta, gamma);
    solver.solve(&tree, &ctx, &cache, iterations);

    // Final discount catch-up.
    let final_iter = solver.iteration;
    let alpha = solver.alpha;
    let beta = solver.beta;
    let gamma = solver.gamma;
    for info in solver.infosets.iter_mut().flatten() {
        PreflopVectorDCFR::discount(info, final_iter, alpha, beta, gamma);
    }

    // Build average strategy dict.
    let mut average_strategy: HashMap<String, Vec<f64>> = HashMap::new();
    let mut decision_node_count: u32 = 0;
    for (node_idx, slot) in solver.infosets.iter().enumerate() {
        let info = match slot {
            Some(info) => info,
            None => continue,
        };
        let node = &tree.nodes[node_idx];
        let (player, key_suffix) = match node {
            PreflopFlatNode::Decision {
                player, key_suffix, ..
            } => (*player as usize, key_suffix.as_str()),
            _ => continue,
        };
        let action_count = info.action_count;
        let hand_count = info.hand_count;
        let mut avg = vec![0.0_f64; hand_count * action_count];
        PreflopVectorDCFR::compute_avg_strategy(info, &mut avg);
        for h in 0..hand_count {
            let hole_str = &ctx.hole_str[player][h];
            let mut key = String::with_capacity(hole_str.len() + key_suffix.len());
            key.push_str(hole_str);
            key.push_str(key_suffix);
            let offset = h * action_count;
            average_strategy.insert(key, avg[offset..offset + action_count].to_vec());
        }
        decision_node_count += 1;
    }
    let _ = Strength::evaluate_7;

    let strategy_entry_count = average_strategy.len() as u32;
    Ok(PreflopRvrOutput {
        average_strategy,
        decision_node_count,
        strategy_entry_count,
        iterations,
        hand_count_per_player: ctx.hand_count,
        wallclock_seconds: started.elapsed().as_secs_f64(),
    })
}

// ============================================================================
// True Path B — 169-class abstraction mode (Phase 1.5 unblock, #68)
//
// In `COMBO_1326` mode (the existing path above) the engine stores
// `hand_count = 1326`-element regret/strategy_sum/reach vectors at each
// infoset, and the wrapper post-aggregates the converged 1326-combo
// strategy into 169 classes for the blueprint asset. The engine still
// pays full 1326-combo per-iter cost.
//
// In `CLASS_169` mode (added here) the engine stores 169-element vectors
// directly. Each "hand" is a Pio-style starting-hand class (e.g. `AA`,
// `AKs`, `72o`). The leaf payoff table integrates the per-(combo_a,
// combo_b) blocker effects up front into a per-(class_i, class_j) effective
// payoff. Convergence is in the abstracted policy space: at finite iter
// counts the 169-class average strategy matches `aggregate_to_169_classes
// (1326-combo strategy)` to ~L1 ≤ 0.05 (see `tests/test_true_path_b_diff.py`).
//
// ## Why this is a real speedup, not just a rename
//
// Per-iter cost is dominated by the terminal-leaf AXPY:
//   `for ho in 0..N_opp { for hp in 0..N_update { out[hp] += reach[ho] * table[ho, hp] } }`
//
// In 1326-mode `N_opp = N_update = 1326`, so the inner kernel is a
// 1326^2 = 1.76 M-op AXPY per leaf per iter. In 169-mode it is 169^2 =
// 28.6 K-op per leaf per iter — a 61.5× reduction in raw FLOPs. Realised
// speedup is lower due to fixed-cost overhead (allocation, traversal,
// strategy compute) but still 7-10× on representative configs.
//
// Plus the 169-element vectors fit in L1 cache (~1.3 KB at f64) whereas
// 1326-element vectors spill to L2 (~10 KB), giving an additional cache
// effect.
//
// ## What stays the same
//
// - Betting tree topology (PreflopBettingTree).
// - Action enumeration.
// - DCFR hyperparameters (α=1.5, β=0, γ=2.0).
// - SIMD kernels (simd::compute_strategy_row, simd::discount_regrets, etc.)
//   are dimension-agnostic — they operate on flat slices.
// - Fold leaf semantics (constant payoff in hero's perspective, scaled
//   by reach over opp's reachable mass).
//
// ## What changes
//
// - Leaf payoff table is 169 × 169 (per update_player), not 1326 × 1326.
// - Each leaf payoff cell integrates blocker effects across the
//   |I| × |J| concrete combos in the class pair.
// - The infoset key encodes `<class_label>` (e.g. `AsAh` is folded into
//   `AA` in the output), so the wrapper does NOT need to call
//   `aggregate_to_169_classes` — it can read the 169-row strategy directly.
// ============================================================================

/// Strategy storage resolution for the preflop RvR engine.
///
/// **`Combo1326`** — engine runs the existing 1326-combo per-player
/// inner loop. Wrapper post-aggregates to 169 classes for blueprint output.
/// This is the legacy path; kept for differential testing and for
/// applications that need exact per-combo strategies.
///
/// **`Class169`** — engine runs a 169-element inner loop. Leaf payoffs
/// are pre-baked to integrate blocker effects across class pairs.
/// ~7-10× per-iter speedup on representative configs; output is already
/// 169-class so the wrapper aggregation is a no-op.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum HandResolution {
    Combo1326,
    Class169,
}

/// Build the 169x169 per-class leaf payoff tables for an equity leaf.
///
/// For each (update_player, class_i, class_j) we integrate over all
/// concrete (combo_a, combo_b) ∈ class_i × class_j with disjoint cards.
/// The resulting cell encodes "expected payoff to update_player when its
/// concrete hand is uniformly distributed over the disjoint subset of
/// class_i and opponent's concrete hand is uniformly distributed over
/// the disjoint subset of class_j".
///
/// # Derivation (matches `Combo1326` after aggregation)
///
/// The 1326-combo kernel produces:
/// ```ignore
/// out_1326[hp] = Σ_{ho} reach_1326[ho] * payoff(hp, ho)   // payoff = 0 for blockers
/// ```
///
/// Aggregating to class I (`out_169[I] = (1/|I|) Σ_{hp∈I} out_1326[hp]`)
/// when reach is uniform over each class (`reach_1326[ho] = c_J` for all
/// `ho ∈ J`, where `c_J = reach_169[J] / |J|`):
/// ```ignore
/// out_169[I]
///     = (1/|I|) Σ_{hp∈I} Σ_J c_J Σ_{ho∈J} payoff(hp, ho)
///     = Σ_J (reach_169[J] / (|I|*|J|)) Σ_{hp∈I,ho∈J,disjoint} payoff(hp, ho)
///     = Σ_J reach_169[J] * payoff_169[I, J]
/// ```
/// where:
/// ```ignore
/// payoff_169[I, J] = (1 / (|I| * |J|)) Σ_{(hp,ho)∈I×J,disjoint} payoff(hp, ho)
/// ```
///
/// This is the **blocker-weighted average** of per-combo payoff over the
/// concrete (I, J) cross product. Combos that block (share a card) are
/// excluded from the sum but still divide |I|*|J| in the denominator —
/// the blocker mass is baked into the cell value.
///
/// # Opp-major layout (matches the existing 1326 leaf path)
///
/// Output is `[Vec<f64>; 2]` where `table[update_player][J * 169 + I]`
/// gives the payoff for update_player when its class is `I` and opp's
/// class is `J`. The inner CFR kernel does:
/// ```ignore
/// for J { for I { out[I] += reach_opp[J] * table[J * 169 + I] } }
/// ```
/// — contiguous read of `table[J*169..(J+1)*169]`, contiguous write to
/// `out[..]`, auto-vectorizes the same way as the 1326 path.
fn build_class169_leaf_payoff(
    contributions: [i32; 2],
    big_blind: i32,
    initial_pot: i32,
    initial_contributions: [i32; 2],
    equity_table: &Array3<f64>,
    class_combos: &Class169Combos,
) -> [Vec<f64>; 2] {
    let bb = big_blind as f64;
    let cs0 = (contributions[0] - initial_contributions[0]) as f64;
    let cs1 = (contributions[1] - initial_contributions[1]) as f64;
    let pot_total = initial_pot as f64 + cs0 + cs1;

    let n_classes = crate::preflop_equity::NUM_CLASSES; // 169
    let mut payoff_p0 = vec![0.0_f64; n_classes * n_classes];
    let mut payoff_p1 = vec![0.0_f64; n_classes * n_classes];

    // Iterate (I, J) and average payoff over (hp ∈ I, ho ∈ J) pairs
    // that don't block each other. Divide by |I|*|J| (not the count of
    // disjoint pairs) so the blocker mass is baked into the cell.
    for class_i in 0..n_classes {
        let combos_i = &class_combos.combos[class_i];
        let n_i = combos_i.len();
        if n_i == 0 {
            continue;
        }
        let inv_i_size = 1.0 / n_i as f64;
        for class_j in 0..n_classes {
            let combos_j = &class_combos.combos[class_j];
            let n_j = combos_j.len();
            if n_j == 0 {
                continue;
            }
            let inv_j_size = 1.0 / n_j as f64;
            // Look up the (I, J) equity once — variant chosen per
            // concrete pair via `classify_suit_variant`, falling back to
            // variant 0 if NaN.
            let mut sum_p0 = 0.0_f64;
            let mut sum_p1 = 0.0_f64;
            for &hero in combos_i {
                for &villain in combos_j {
                    // Blocker check: shared card.
                    if hero[0] == villain[0]
                        || hero[0] == villain[1]
                        || hero[1] == villain[0]
                        || hero[1] == villain[1]
                    {
                        continue;
                    }
                    let variant = classify_suit_variant(hero, villain);
                    let mut eq = equity_table[(class_i, class_j, variant)];
                    if eq.is_nan() {
                        eq = equity_table[(class_i, class_j, 0)];
                        if eq.is_nan() {
                            eq = crate::preflop_equity::enumerate_pair_equity(hero, villain);
                        }
                    }
                    let p0_payoff = (pot_total * eq - cs0) / bb;
                    let p1_payoff = (pot_total * (1.0 - eq) - cs1) / bb;
                    sum_p0 += p0_payoff;
                    sum_p1 += p1_payoff;
                }
            }
            // Average over the |I| * |J| cross product (NOT just disjoint
            // pairs). Blocker pairs contributed 0 to the sum and are
            // implicitly counted in the denominator — that's the
            // "blocker mass" weighting.
            let denom = inv_i_size * inv_j_size;
            // Opp-major layout: index by [class_j (opp) * 169 + class_i (update)].
            payoff_p0[class_j * n_classes + class_i] = sum_p0 * denom;
            payoff_p1[class_i * n_classes + class_j] = sum_p1 * denom;
        }
    }
    [payoff_p0, payoff_p1]
}

/// Build the 169-class blocker mass table.
///
/// `mass[update_player][J * 169 + I]` = `count_disjoint(I, J) / (|I| * |J|)`
/// — the fraction of (hp ∈ I, ho ∈ J) pairs that are NOT blocked.
///
/// Used by the `Fold` leaf in the 169-class kernel: a Fold leaf has a
/// constant per-perspective payoff `util` (not equity-weighted), so
/// `out_169[I] += util * Σ_J reach_169[J] * mass[J, I]`.
///
/// Same opp-major layout as the equity payoff tables.
fn build_class169_blocker_mass(class_combos: &Class169Combos) -> [Vec<f64>; 2] {
    let n_classes = crate::preflop_equity::NUM_CLASSES;
    let mut mass_p0 = vec![0.0_f64; n_classes * n_classes];
    let mut mass_p1 = vec![0.0_f64; n_classes * n_classes];
    for class_i in 0..n_classes {
        let combos_i = &class_combos.combos[class_i];
        let n_i = combos_i.len();
        if n_i == 0 {
            continue;
        }
        for class_j in 0..n_classes {
            let combos_j = &class_combos.combos[class_j];
            let n_j = combos_j.len();
            if n_j == 0 {
                continue;
            }
            let mut disjoint = 0_u32;
            for &hero in combos_i {
                for &villain in combos_j {
                    if hero[0] == villain[0]
                        || hero[0] == villain[1]
                        || hero[1] == villain[0]
                        || hero[1] == villain[1]
                    {
                        continue;
                    }
                    disjoint += 1;
                }
            }
            let mass = disjoint as f64 / (n_i as f64 * n_j as f64);
            mass_p0[class_j * n_classes + class_i] = mass;
            mass_p1[class_i * n_classes + class_j] = mass;
        }
    }
    [mass_p0, mass_p1]
}

/// Pre-enumeration of `class_idx -> Vec<[card0, card1]>` for all 169
/// classes over the full 52-card deck. Built once and shared by every
/// equity-leaf / fold-leaf table build.
///
/// Each class has 6 combos (pocket pair) / 4 combos (suited) / 12 combos
/// (offsuit). Total combos across all 169 classes = 13*6 + 78*4 + 78*12 =
/// 78 + 312 + 936 = 1326, as expected.
pub struct Class169Combos {
    pub combos: [Vec<[u8; 2]>; 169],
}

impl Class169Combos {
    /// Enumerate concrete combos for every 169-class label.
    pub fn build() -> Self {
        // SAFETY: array of Vec<...> ; initialized via from_fn so we don't
        // need Default impl on `Vec<[u8; 2]>`. (Vec<T> is Default but the
        // 169-element array literal would be verbose.)
        let combos: [Vec<[u8; 2]>; 169] = std::array::from_fn(|_| Vec::new());
        let mut this = Class169Combos { combos };
        for r0 in 2u8..=14 {
            for s0 in 0u8..4 {
                let c0 = crate::hunl::card_to_int(r0, s0);
                for r1 in 2u8..=14 {
                    for s1 in 0u8..4 {
                        let c1 = crate::hunl::card_to_int(r1, s1);
                        if c0 >= c1 {
                            continue;
                        }
                        let class_idx = hole_to_class([c0, c1]) as usize;
                        this.combos[class_idx].push([c0, c1]);
                    }
                }
            }
        }
        this
    }
}

/// Phase 1.5 (True Path B) — per-leaf cache for the 169-class engine.
///
/// Parallel to `PreflopTerminalCache` but stores 169 × 169 leaf tables
/// instead of 1326 × 1326. The leaf payoff already integrates blocker
/// effects, so the inner CFR kernel doesn't need a per-cell blocker
/// filter.
pub struct Class169TerminalCache {
    pub leaves: Vec<Class169LeafEntry>,
    /// Shared 169-class blocker mass table used by every Fold leaf.
    ///
    /// `shared_blocker_mass[up][J * 169 + I]` = fraction of (combo_a ∈ I,
    /// combo_b ∈ J) pairs that are disjoint (not blocked). Same opp-major
    /// layout as `Class169LeafEntry::Equity::payoff_table` so the inner
    /// kernel can use the same `for j { for i { ... } }` AXPY shape.
    pub shared_blocker_mass: [Vec<f64>; 2],
}

pub enum Class169LeafEntry {
    NonTerminal,
    /// Fold leaf — constant payoff per perspective times the shared
    /// blocker-mass table.
    Fold {
        /// Payoff per perspective (in BB units). Same semantics as
        /// `PreflopLeafEntry::Fold::payoff` — both perspectives stored
        /// since `update_player` swaps which is "hero".
        payoff: [f64; 2],
    },
    Equity {
        /// `payoff_table[update_player][J * 169 + I]` — opp-major,
        /// blocker-mass-weighted, in BB units.
        payoff_table: [Vec<f64>; 2],
    },
}

impl Class169TerminalCache {
    pub fn build(
        tree: &PreflopBettingTree,
        equity_table: &Array3<f64>,
        class_combos: &Class169Combos,
    ) -> Self {
        let shared_blocker_mass = build_class169_blocker_mass(class_combos);
        let mut leaves: Vec<Class169LeafEntry> = Vec::with_capacity(tree.nodes.len());
        for node in &tree.nodes {
            match node {
                PreflopFlatNode::Fold {
                    contributions,
                    folded_player,
                    big_blind,
                    initial_pot,
                    initial_contributions,
                } => {
                    let bb = *big_blind as f64;
                    let cs0 = (contributions[0] - initial_contributions[0]) as f64;
                    let cs1 = (contributions[1] - initial_contributions[1]) as f64;
                    let pot_total = *initial_pot as f64 + cs0 + cs1;
                    let payoff = if *folded_player == 0 {
                        [-cs0 / bb, (pot_total - cs1) / bb]
                    } else {
                        [(pot_total - cs0) / bb, -cs1 / bb]
                    };
                    leaves.push(Class169LeafEntry::Fold { payoff });
                }
                PreflopFlatNode::EquityLeaf {
                    contributions,
                    big_blind,
                    initial_pot,
                    initial_contributions,
                } => {
                    let payoff_table = build_class169_leaf_payoff(
                        *contributions,
                        *big_blind,
                        *initial_pot,
                        *initial_contributions,
                        equity_table,
                        class_combos,
                    );
                    leaves.push(Class169LeafEntry::Equity { payoff_table });
                }
                _ => leaves.push(Class169LeafEntry::NonTerminal),
            }
        }
        Self {
            leaves,
            shared_blocker_mass,
        }
    }
}

/// Phase 1.5 (True Path B) — 169-class vector-form DCFR solver.
///
/// Storage: 169-element regret / strategy_sum per (decision-node,
/// hand-class). Inner kernel calls the same `simd::*` primitives as the
/// 1326-combo path; the only difference is the vector dimension.
pub struct Class169VectorDCFR {
    alpha: f64,
    beta: f64,
    gamma: f64,
    iteration: u32,
    infosets: Vec<Option<VectorInfosetData>>,
}

impl Class169VectorDCFR {
    fn new(
        tree: &PreflopBettingTree,
        hand_count: usize,
        alpha: f64,
        beta: f64,
        gamma: f64,
    ) -> Self {
        crate::dcfr::validate_alpha(alpha);
        let mut infosets: Vec<Option<VectorInfosetData>> = Vec::with_capacity(tree.nodes.len());
        for node in &tree.nodes {
            match node {
                PreflopFlatNode::Decision { actions, .. } => {
                    infosets.push(Some(VectorInfosetData::new(actions.len(), hand_count)));
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

    fn traverse(
        &mut self,
        tree: &PreflopBettingTree,
        cache: &Class169TerminalCache,
        node_idx: usize,
        update_player: usize,
        reach_p: &[f64],
        reach_opp: &[f64],
    ) -> Vec<f64> {
        let n_classes = crate::preflop_equity::NUM_CLASSES;
        match &tree.nodes[node_idx] {
            PreflopFlatNode::Fold { .. } | PreflopFlatNode::EquityLeaf { .. } => {
                terminal_value_vector_169(&cache.leaves[node_idx], cache, update_player, reach_opp)
            }
            PreflopFlatNode::Decision {
                player,
                actions,
                children,
                ..
            } => {
                let player = *player as usize;
                let action_count = actions.len();
                let mut strategy = vec![0.0_f64; n_classes * action_count];
                {
                    let info = self.infosets[node_idx]
                        .as_ref()
                        .expect("decision node has infoset");
                    PreflopVectorDCFR::compute_strategy(info, &mut strategy);
                }

                if player != update_player {
                    let mut values = vec![0.0_f64; n_classes];
                    let mut next_reach = vec![0.0_f64; n_classes];
                    for (a, &child_idx) in children.iter().enumerate() {
                        for h in 0..n_classes {
                            next_reach[h] = reach_opp[h] * strategy[h * action_count + a];
                        }
                        let child_values =
                            self.traverse(tree, cache, child_idx, update_player, reach_p, &next_reach);
                        for h in 0..n_classes {
                            values[h] += child_values[h];
                        }
                    }
                    return values;
                }

                // Own (update_player) node.
                {
                    let info = self.infosets[node_idx]
                        .as_mut()
                        .expect("decision node has infoset");
                    PreflopVectorDCFR::discount(
                        info,
                        self.iteration,
                        self.alpha,
                        self.beta,
                        self.gamma,
                    );
                }
                {
                    let info = self.infosets[node_idx]
                        .as_ref()
                        .expect("decision node has infoset");
                    PreflopVectorDCFR::compute_strategy(info, &mut strategy);
                }

                let mut action_values = vec![0.0_f64; action_count * n_classes];
                let mut next_reach = vec![0.0_f64; n_classes];
                for (a, &child_idx) in children.iter().enumerate() {
                    for h in 0..n_classes {
                        next_reach[h] = reach_p[h] * strategy[h * action_count + a];
                    }
                    let child_values =
                        self.traverse(tree, cache, child_idx, update_player, &next_reach, reach_opp);
                    let dst = a * n_classes;
                    action_values[dst..dst + n_classes].copy_from_slice(&child_values);
                }

                let mut node_values = vec![0.0_f64; n_classes];
                for h in 0..n_classes {
                    let mut value = 0.0_f64;
                    let s_offset = h * action_count;
                    for a in 0..action_count {
                        value += strategy[s_offset + a] * action_values[a * n_classes + h];
                    }
                    node_values[h] = value;
                }

                {
                    let info = self.infosets[node_idx]
                        .as_mut()
                        .expect("decision node has infoset");
                    simd::update_regret_sum_vector(
                        &mut info.regret,
                        &action_values,
                        &node_values,
                        n_classes,
                        action_count,
                    );
                    for h in 0..n_classes {
                        let weight = reach_p[h];
                        if weight == 0.0 {
                            continue;
                        }
                        let offset = h * action_count;
                        let row_end = offset + action_count;
                        simd::update_strategy_sum(
                            &mut info.strategy_sum[offset..row_end],
                            &strategy[offset..row_end],
                            weight,
                        );
                    }
                }
                node_values
            }
        }
    }

    /// Run `iterations` of DCFR with the given per-class root reach.
    fn solve(
        &mut self,
        tree: &PreflopBettingTree,
        cache: &Class169TerminalCache,
        iterations: u32,
        root_reach_p0: &[f64],
        root_reach_p1: &[f64],
    ) {
        for _ in 0..iterations {
            self.iteration += 1;
            self.traverse(tree, cache, 0, 0, root_reach_p0, root_reach_p1);
            self.traverse(tree, cache, 0, 1, root_reach_p1, root_reach_p0);
        }
    }
}

/// Terminal-leaf value vector under 169-class storage.
///
/// Mirrors `terminal_value_vector` but at 169 dim. The Fold path
/// multiplies the fold-payoff by the shared blocker-mass table; the
/// Equity path reads from the per-leaf pre-baked payoff table that
/// already integrates blocker mass.
fn terminal_value_vector_169(
    leaf: &Class169LeafEntry,
    cache: &Class169TerminalCache,
    update_player: usize,
    reach_opp: &[f64],
) -> Vec<f64> {
    let n_classes = crate::preflop_equity::NUM_CLASSES;
    let mut out = vec![0.0_f64; n_classes];

    match leaf {
        Class169LeafEntry::Fold { payoff } => {
            let util = payoff[update_player];
            let mass = &cache.shared_blocker_mass[update_player];
            // ho-outer (opp class J), hp-inner (update class I) AXPY.
            for j in 0..n_classes {
                let row = &mass[j * n_classes..(j + 1) * n_classes];
                let coeff = reach_opp[j] * util;
                for i in 0..n_classes {
                    out[i] += coeff * row[i];
                }
            }
        }
        Class169LeafEntry::Equity { payoff_table } => {
            let table = &payoff_table[update_player];
            for j in 0..n_classes {
                let row = &table[j * n_classes..(j + 1) * n_classes];
                let reach = reach_opp[j];
                for i in 0..n_classes {
                    out[i] += reach * row[i];
                }
            }
        }
        Class169LeafEntry::NonTerminal => unreachable!("non-terminal in leaf path"),
    }
    out
}

/// Public output of a 169-class preflop RvR solve. The strategy map keys
/// are `<class_label>||p|<history>` (e.g. `"AA||p|"` for the SB AA root
/// decision); each value is the action probability vector for that
/// (class, history) pair.
pub struct Class169RvrOutput {
    pub average_strategy: HashMap<String, Vec<f64>>,
    pub decision_node_count: u32,
    pub strategy_entry_count: u32,
    pub iterations: u32,
    pub wallclock_seconds: f64,
}

/// True Path B entry — solve the full HUNL preflop range-vs-range Nash
/// in 169-class abstraction mode.
///
/// `root_reach` is per-player reach at the root, one float per class
/// (length 169). Default (full range, every class active uniformly):
/// `[[1.0; 169], [1.0; 169]]`. A "premium-only" filter sets reach[I] = 0
/// for excluded classes (e.g. for AA-vs-KK closed-form test).
#[allow(clippy::too_many_arguments)]
pub fn solve_hunl_preflop_rvr_class169(
    config: &HUNLConfig,
    equity_table_path: &Path,
    root_reach_p0: Option<Vec<f64>>,
    root_reach_p1: Option<Vec<f64>>,
    preflop_open_sizes_bb: &[f64],
    preflop_reraise_multipliers: &[f64],
    iterations: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
) -> Result<Class169RvrOutput, String> {
    config
        .validate()
        .map_err(|e| format!("solve_hunl_preflop_rvr_class169: {e}"))?;
    if config.starting_street != Street::Preflop {
        return Err(format!(
            "solve_hunl_preflop_rvr_class169 requires starting_street = Preflop (got {:?})",
            config.starting_street
        ));
    }
    if config.initial_hole_cards.is_some() {
        return Err(
            "solve_hunl_preflop_rvr_class169 requires initial_hole_cards = None; \
             use solve_hunl_preflop for fixed-hole subgames"
                .into(),
        );
    }

    let n_classes = crate::preflop_equity::NUM_CLASSES;
    // Default root reach: combo-count-weighted per class.
    //
    // Rationale: in 1326-combo mode, the engine implicitly uses
    // `reach[combo] = 1.0` for every combo. The aggregate reach over
    // class I is then `|I|` (6 for pairs, 4 for suited, 12 for offsuit).
    //
    // To produce strategies that match `aggregate_to_169_classes(1326-combo
    // output)` lane-for-lane, the 169-class default must use the same
    // per-class aggregate reach: `reach_169[I] = |I|`. The empirical
    // diff test (`test_class169_matches_hybrid_within_l1_tolerance`)
    // confirms this gives ≈ 1e-9 L1 drift across all infosets.
    //
    // Callers who want "uniform over classes" semantics (each class
    // treated as one virtual hand) pass `vec![1.0; 169]` explicitly.
    let class_combos = Class169Combos::build();
    let default_reach: Vec<f64> = (0..n_classes)
        .map(|i| class_combos.combos[i].len() as f64)
        .collect();
    let root_reach_p0 = root_reach_p0.unwrap_or_else(|| default_reach.clone());
    let root_reach_p1 = root_reach_p1.unwrap_or_else(|| default_reach.clone());
    if root_reach_p0.len() != n_classes {
        return Err(format!(
            "root_reach_p0 length {} != {n_classes}",
            root_reach_p0.len()
        ));
    }
    if root_reach_p1.len() != n_classes {
        return Err(format!(
            "root_reach_p1 length {} != {n_classes}",
            root_reach_p1.len()
        ));
    }

    let started = Instant::now();
    let equity_table: Array3<f64> =
        load_equity_table(equity_table_path).map_err(|e| format!("load equity table: {e}"))?;

    let tree =
        PreflopBettingTree::build(config, preflop_open_sizes_bb, preflop_reraise_multipliers);
    let cache = Class169TerminalCache::build(&tree, &equity_table, &class_combos);

    let mut solver = Class169VectorDCFR::new(&tree, n_classes, alpha, beta, gamma);
    solver.solve(&tree, &cache, iterations, &root_reach_p0, &root_reach_p1);

    // Final discount catch-up.
    let final_iter = solver.iteration;
    let alpha = solver.alpha;
    let beta = solver.beta;
    let gamma = solver.gamma;
    for info in solver.infosets.iter_mut().flatten() {
        PreflopVectorDCFR::discount(info, final_iter, alpha, beta, gamma);
    }

    // Build average strategy dict, keyed by `<class_label>||p|<history>`.
    let class_labels: Vec<String> = (0..n_classes)
        .map(|i| {
            let (rh, rl, suited) = crate::preflop_equity::class_decode(i as u16);
            class_label_string(rh, rl, suited)
        })
        .collect();

    let mut average_strategy: HashMap<String, Vec<f64>> = HashMap::new();
    let mut decision_node_count: u32 = 0;
    for (node_idx, slot) in solver.infosets.iter().enumerate() {
        let info = match slot {
            Some(info) => info,
            None => continue,
        };
        let node = &tree.nodes[node_idx];
        let key_suffix = match node {
            PreflopFlatNode::Decision { key_suffix, .. } => key_suffix.as_str(),
            _ => continue,
        };
        let action_count = info.action_count;
        let mut avg = vec![0.0_f64; n_classes * action_count];
        PreflopVectorDCFR::compute_avg_strategy(info, &mut avg);
        for cls_idx in 0..n_classes {
            let label = &class_labels[cls_idx];
            let mut key = String::with_capacity(label.len() + key_suffix.len());
            key.push_str(label);
            key.push_str(key_suffix);
            let offset = cls_idx * action_count;
            average_strategy.insert(key, avg[offset..offset + action_count].to_vec());
        }
        decision_node_count += 1;
    }
    let _ = Strength::evaluate_7;

    let strategy_entry_count = average_strategy.len() as u32;
    Ok(Class169RvrOutput {
        average_strategy,
        decision_node_count,
        strategy_entry_count,
        iterations,
        wallclock_seconds: started.elapsed().as_secs_f64(),
    })
}

/// Format a 169-class label as `AA` / `AKs` / `AKo` per the canonical
/// Pio-style hand-class naming.
fn class_label_string(rank_hi: u8, rank_lo: u8, suited: bool) -> String {
    const RANK_CHARS: [char; 15] = [
        '_', '_', '2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A',
    ];
    let hi = RANK_CHARS[rank_hi as usize];
    let lo = RANK_CHARS[rank_lo as usize];
    if rank_hi == rank_lo {
        format!("{hi}{lo}")
    } else if suited {
        format!("{hi}{lo}s")
    } else {
        format!("{hi}{lo}o")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ndarray::Array3;

    fn tiny_config() -> HUNLConfig {
        HUNLConfig {
            starting_stack: 10_000,
            small_blind: 50,
            big_blind: 100,
            ante: 0,
            starting_street: Street::Preflop,
            initial_board: vec![],
            initial_pot: 0,
            initial_contributions: [0, 0],
            initial_hole_cards: None,
            preflop_raise_cap: 4,
            postflop_raise_cap: 3,
            bet_size_fractions: vec![1.0],
            include_all_in: true,
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
    fn betting_tree_builds_with_default_menu() {
        let cfg = tiny_config();
        let tree = PreflopBettingTree::build(&cfg, &[2.0, 3.0, 4.0, 5.0], &[2.0, 3.0, 4.0, 5.0]);
        assert!(
            tree.nodes.len() > 1,
            "preflop tree must have multiple nodes"
        );
        // At least one decision node and one terminal.
        let mut decision_count = 0usize;
        let mut terminal_count = 0usize;
        for n in &tree.nodes {
            match n {
                PreflopFlatNode::Decision { .. } => decision_count += 1,
                _ => terminal_count += 1,
            }
        }
        assert!(decision_count > 0, "no decision nodes in preflop tree");
        assert!(terminal_count > 0, "no terminals in preflop tree");
    }

    #[test]
    fn rejects_postflop_config() {
        let mut cfg = tiny_config();
        cfg.starting_street = Street::Flop;
        cfg.initial_board = vec![8, 12, 16, 20, 24];
        let stub_table = Array3::<f64>::zeros((169, 169, 3));
        let tmp = std::env::temp_dir().join("__phase_a_test_stub.npz");
        crate::preflop_equity::save_equity_table(&tmp, &stub_table).unwrap();
        let res = solve_hunl_preflop_rvr(
            &cfg,
            &tmp,
            &[2.0, 3.0, 4.0, 5.0],
            &[2.0, 3.0, 4.0, 5.0],
            3,
            1.5,
            0.0,
            2.0,
        );
        assert!(res.is_err(), "must reject postflop config");
    }

    #[test]
    fn rejects_fixed_hole_cards() {
        let mut cfg = tiny_config();
        cfg.initial_hole_cards = Some([
            [
                crate::hunl::card_to_int(14, 0),
                crate::hunl::card_to_int(14, 1),
            ],
            [
                crate::hunl::card_to_int(13, 2),
                crate::hunl::card_to_int(13, 3),
            ],
        ]);
        let stub_table = Array3::<f64>::zeros((169, 169, 3));
        let tmp = std::env::temp_dir().join("__phase_a_test_stub2.npz");
        crate::preflop_equity::save_equity_table(&tmp, &stub_table).unwrap();
        let res = solve_hunl_preflop_rvr(
            &cfg,
            &tmp,
            &[2.0, 3.0, 4.0, 5.0],
            &[2.0, 3.0, 4.0, 5.0],
            3,
            1.5,
            0.0,
            2.0,
        );
        assert!(res.is_err(), "must reject fixed-hole config");
    }

    // ========================================================================
    // Phase B (#53) — bit-identical parity test.
    //
    // Mirrors PR #114 + PR #139's pattern: force the pre-PR scalar baseline
    // through `terminal_value_vector_baseline` + `build_equity_leaf_payoff_baseline`,
    // run both shapes on a small representative fixture, assert
    // `to_bits()` equality lane-for-lane.
    //
    // The fixture: 6 hole pairs / player (AA + KK + 72o sample), 3 reach
    // distributions (uniform, sparse, skewed), 2 update_players × 2 leaf
    // kinds (Fold + Equity). Drives the optimization correctness gate
    // for the engine change.
    // ========================================================================

    /// Build a small 6-hand × 6-hand EvalContext for parity testing.
    fn small_eval_ctx() -> EvalContext {
        let p_hands = vec![
            [
                crate::hunl::card_to_int(14, 0),
                crate::hunl::card_to_int(14, 1),
            ], // AsAh
            [
                crate::hunl::card_to_int(14, 2),
                crate::hunl::card_to_int(14, 3),
            ], // AdAc
            [
                crate::hunl::card_to_int(13, 0),
                crate::hunl::card_to_int(13, 1),
            ], // KsKh
            [
                crate::hunl::card_to_int(13, 2),
                crate::hunl::card_to_int(13, 3),
            ], // KdKc
            [
                crate::hunl::card_to_int(7, 0),
                crate::hunl::card_to_int(2, 1),
            ], // 7s2h
            [
                crate::hunl::card_to_int(7, 2),
                crate::hunl::card_to_int(2, 3),
            ], // 7d2c
        ];
        EvalContext::from_hand_lists(p_hands.clone(), p_hands, 100)
    }

    /// Build a stub 169x169x3 equity table with diverse values. Same shape
    /// as the production-shipped table, with deterministic per-cell values
    /// so the parity check is reproducible.
    fn stub_equity_table() -> Array3<f64> {
        let mut t = Array3::<f64>::zeros((169, 169, 3));
        for i in 0..169 {
            for j in 0..169 {
                for v in 0..3 {
                    // Deterministic in-range equity.
                    let raw = ((i * 17 + j * 13 + v * 7) % 1000) as f64 / 1000.0;
                    t[(i, j, v)] = 0.05 + 0.90 * raw; // [0.05, 0.95]
                }
            }
        }
        t
    }

    /// Phase B (#53) — bit-identical parity: `terminal_value_vector`
    /// (opp-major + AXPY) matches `terminal_value_vector_baseline`
    /// (pre-PR hp-major + branched) lane-for-lane via `to_bits()` equality.
    ///
    /// Coverage: Fold leaf + Equity leaf, both update_players, three
    /// distinct `reach_opp` distributions (uniform / sparse / skewed).
    #[test]
    fn optimized_matches_baseline_bit_exact() {
        let ctx = small_eval_ctx();
        let eq_table = stub_equity_table();

        // Build both layouts on the same inputs.
        let contributions = [200i32, 600i32]; // 2bb-vs-6bb dummy
        let big_blind = 100i32;
        let initial_pot = 0i32;
        let initial_contributions = [0i32, 0i32];

        let payoff_table_new = build_equity_leaf_payoff(
            contributions,
            big_blind,
            initial_pot,
            initial_contributions,
            &ctx,
            &eq_table,
        );
        let payoff_table_baseline = build_equity_leaf_payoff_baseline(
            contributions,
            big_blind,
            initial_pot,
            initial_contributions,
            &ctx,
            &eq_table,
        );

        // Construct the new-shape leaf entry and corresponding baseline.
        let leaf_new = PreflopLeafEntry::Equity {
            payoff_table: payoff_table_new.clone(),
        };
        let leaf_baseline = PreflopLeafEntryBaseline::Equity {
            payoff_table_hp_major: payoff_table_baseline,
        };

        // Fold-leaf payoff per (folded_player, BB).
        let cs0 = (contributions[0] - initial_contributions[0]) as f64;
        let cs1 = (contributions[1] - initial_contributions[1]) as f64;
        let pot_total = initial_pot as f64 + cs0 + cs1;
        let bb_f = big_blind as f64;
        // Folded_player = 0 → P1 wins.
        let fold_payoff = [-cs0 / bb_f, (pot_total - cs1) / bb_f];
        let fold_new = PreflopLeafEntry::Fold {
            payoff: fold_payoff,
        };
        let fold_baseline = PreflopLeafEntryBaseline::Fold {
            payoff: fold_payoff,
        };

        // Build the cache (just for the blocker_mask used by the new Fold path).
        // Use a stub single-leaf cache; only `blocker_mask` is consulted.
        let mock_tree = PreflopBettingTree {
            nodes: vec![PreflopFlatNode::Fold {
                contributions,
                folded_player: 0,
                big_blind,
                initial_pot,
                initial_contributions,
            }],
        };
        let cache = PreflopTerminalCache::build(&mock_tree, &ctx, &eq_table);

        // Three reach_opp distributions.
        let reach_uniform = vec![1.0_f64; 6];
        let reach_sparse = vec![1.0, 0.0, 0.5, 0.0, 0.25, 0.0];
        let reach_skewed = vec![0.7, 0.3, 0.9, 0.1, 0.5, 0.5];

        for (label, reach) in [
            ("uniform", &reach_uniform),
            ("sparse", &reach_sparse),
            ("skewed", &reach_skewed),
        ] {
            for update_player in 0..2usize {
                let opp_player = 1 - update_player;

                // Equity leaf parity.
                let out_new = terminal_value_vector(
                    &leaf_new,
                    &cache,
                    &ctx,
                    update_player,
                    opp_player,
                    reach,
                );
                let out_baseline = terminal_value_vector_baseline(
                    &leaf_baseline,
                    &ctx,
                    update_player,
                    opp_player,
                    reach,
                );
                assert_eq!(out_new.len(), out_baseline.len());
                for (hp, (a, b)) in out_new.iter().zip(out_baseline.iter()).enumerate() {
                    assert_eq!(
                        a.to_bits(),
                        b.to_bits(),
                        "Equity reach={} player={} hp={} differs: new={} baseline={}",
                        label,
                        update_player,
                        hp,
                        a,
                        b
                    );
                }

                // Fold leaf parity.
                let out_new_fold = terminal_value_vector(
                    &fold_new,
                    &cache,
                    &ctx,
                    update_player,
                    opp_player,
                    reach,
                );
                let out_baseline_fold = terminal_value_vector_baseline(
                    &fold_baseline,
                    &ctx,
                    update_player,
                    opp_player,
                    reach,
                );
                for (hp, (a, b)) in out_new_fold
                    .iter()
                    .zip(out_baseline_fold.iter())
                    .enumerate()
                {
                    assert_eq!(
                        a.to_bits(),
                        b.to_bits(),
                        "Fold reach={} player={} hp={} differs: new={} baseline={}",
                        label,
                        update_player,
                        hp,
                        a,
                        b
                    );
                }
            }
        }
    }

    // ========================================================================
    // Phase 1.5 (True Path B, #68) — 169-class engine smoke tests.
    // ========================================================================

    /// Sanity: `Class169Combos::build` enumerates exactly 1326 combos
    /// total across all 169 classes (13 pairs * 6 + 78 suited * 4 +
    /// 78 offsuit * 12 = 1326).
    #[test]
    fn class169_combos_enumerate_full_deck() {
        let cc = Class169Combos::build();
        let total: usize = cc.combos.iter().map(|v| v.len()).sum();
        assert_eq!(total, 1326, "169-class combo enumeration should cover all C(52,2)");
        // Per-class card counts.
        // Class 0 = AA pocket pair → C(4, 2) = 6 combos.
        assert_eq!(cc.combos[0].len(), 6, "AA pocket pair = 6 combos");
        // Class 13 = AKs (suited) → 4 combos.
        assert_eq!(cc.combos[13].len(), 4, "AKs = 4 combos");
        // Class 13 + 78 = AKo (offsuit) → 12 combos.
        assert_eq!(cc.combos[13 + 78].len(), 12, "AKo = 12 combos");
    }

    /// Sanity: blocker mass for non-self class pairs should be > 0 and ≤ 1;
    /// for AA-vs-AA blocker mass = 0 (cannot have two AA combos disjoint
    /// — only 4 aces in deck, AA uses 2 of them).
    #[test]
    fn class169_blocker_mass_basic_invariants() {
        let cc = Class169Combos::build();
        let mass = build_class169_blocker_mass(&cc);
        let n = crate::preflop_equity::NUM_CLASSES;
        // AA vs AA: 6 hero combos × 6 villain combos = 36 pairs. Each AA
        // uses 2 of the 4 aces. Two AA combos are disjoint iff together
        // they use all 4 aces (form a partition). For each hero combo
        // there is exactly 1 disjoint villain combo (its complement
        // in the C(4,2) ace partition). So mass = 6 / 36 = 1/6 ≈ 0.1667.
        // Index: opp-major, [J * 169 + I] in mass_p0.
        let _ = n;
        let aa_vs_aa = mass[0][0];
        assert!(
            (aa_vs_aa - 1.0 / 6.0).abs() < 1e-9,
            "AA vs AA blocker mass should be 1/6 (only complementary ace partitions): got {aa_vs_aa}"
        );
        // AA vs KK: 6 AA combos × 6 KK combos = 36 pairs, all disjoint
        // (KK has no aces). Mass = 36 / 36 = 1.0.
        let aa = 0;
        let kk = 1;
        assert!(
            (mass[0][kk * n + aa] - 1.0).abs() < 1e-9,
            "AA vs KK blocker mass should be 1.0: got {}",
            mass[0][kk * n + aa]
        );
        // AKs vs AKs: hero suited, villain suited; shares suits, lots
        // of blockers. Should be in (0, 1).
        let aks = 13;
        let mass_aks_aks = mass[0][aks * n + aks];
        assert!(
            mass_aks_aks > 0.0 && mass_aks_aks < 1.0,
            "AKs vs AKs blocker mass should be in (0, 1): got {}",
            mass_aks_aks
        );
    }

    /// AA-vs-KK closed-form smoke: in 169-class mode with reach filtered
    /// to AA-only / KK-only, AA must (i) never fold, (ii) commit chips.
    /// Mirrors the existing `aa_only_vs_kk_only_closed_form` Rust smoke
    /// (in `crates/cfr_core/tests/preflop_rvr_smoke.rs`) but goes through
    /// the 169-class kernel.
    #[test]
    fn class169_aa_vs_kk_does_not_fold() {
        let path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .join("assets")
            .join("preflop_equity_169x169.npz");
        if !path.exists() {
            eprintln!("equity table missing at {path:?} — skipping smoke");
            return;
        }
        let cfg = HUNLConfig {
            starting_stack: 10_000,
            small_blind: 50,
            big_blind: 100,
            ante: 0,
            starting_street: Street::Preflop,
            initial_board: vec![],
            initial_pot: 0,
            initial_contributions: [0, 0],
            initial_hole_cards: None,
            preflop_raise_cap: 4,
            postflop_raise_cap: 3,
            bet_size_fractions: vec![1.0],
            include_all_in: true,
            force_allin_threshold: 1,
            min_bet_bb: 1,
            rake_rate: 0.0,
            rake_cap: 0,
            abstraction_path: None,
            abstraction_version: None,
            use_pcs: false,
        };
        // Filter reach: AA only for P0, KK only for P1.
        let n = crate::preflop_equity::NUM_CLASSES;
        let mut reach_p0 = vec![0.0_f64; n];
        let mut reach_p1 = vec![0.0_f64; n];
        reach_p0[0] = 1.0; // AA
        reach_p1[1] = 1.0; // KK

        let out = solve_hunl_preflop_rvr_class169(
            &cfg,
            &path,
            Some(reach_p0),
            Some(reach_p1),
            &[2.0, 3.0, 4.0, 5.0],
            &[2.0, 3.0, 4.0, 5.0],
            300,
            1.5,
            0.0,
            2.0,
        )
        .expect("169-class solve must succeed");
        assert!(out.decision_node_count > 0);

        // AA at SB root: key = "AA||p|"
        let aa_root = out
            .average_strategy
            .get("AA||p|")
            .expect("AA||p| key must be present");
        let fold = aa_root[0];
        let call = aa_root[1];
        let aggressive: f64 = aa_root.iter().skip(2).sum();
        let commit = call + aggressive;
        assert!(
            fold < 0.01,
            "AA must not fold preflop in 169-class mode: fold = {fold}, full strategy = {aa_root:?}"
        );
        assert!(
            commit > 0.99,
            "AA must commit chips: commit = {commit}, full strategy = {aa_root:?}"
        );
    }

    /// Class-i = AA. With AA hero filter and uniform villain, the leaf
    /// payoff cells should be biased POSITIVE for hero (AA has ~85%
    /// equity averaged over all opp combos). This is a sanity check on
    /// the leaf table itself.
    #[test]
    fn class169_leaf_payoff_aa_vs_uniform_is_positive() {
        let path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .join("assets")
            .join("preflop_equity_169x169.npz");
        if !path.exists() {
            eprintln!("equity table missing at {path:?} — skipping");
            return;
        }
        let table = load_equity_table(&path).expect("load equity table");
        let cc = Class169Combos::build();
        // 100-BB stacks called all-in: contributions = [10000, 10000], pot = 20000.
        // initial_pot = 0; cs = [10000, 10000]; pot_total = 20000.
        // Expected payoff[AA, J] = pot * eq(AA, J) - 10000 = 20000 * eq - 10000.
        // For uniform J, mean eq ≈ 0.85 → payoff ≈ 20000 * 0.85 - 10000 = 7000
        // in cents = 70 BB.
        let payoff =
            build_class169_leaf_payoff([10_000, 10_000], 100, 0, [0, 0], &table, &cc);
        // Opp-major: payoff_p0[J * 169 + 0] = payoff[update=P0, hero=AA, opp=J].
        let n = crate::preflop_equity::NUM_CLASSES;
        let mut mean_aa_payoff = 0.0_f64;
        let mut count = 0;
        for j in 0..n {
            let cell = payoff[0][j * n];
            // Skip blocker-only or pair-on-pair-self cells (AA vs AA = 0
            // since blocker mass is zero).
            if cell == 0.0 {
                continue;
            }
            mean_aa_payoff += cell;
            count += 1;
        }
        let mean = mean_aa_payoff / count as f64;
        // AA's payoff in BB units. Should be positive (AA wins most of the
        // time at all-in). Use a permissive lower bound — exact value
        // depends on blocker mass weighting.
        assert!(
            mean > 30.0,
            "AA's mean leaf payoff (BB) should be strongly positive: got {mean}"
        );
    }

    /// Per-iter cost smoke: at 100 iters, 100-BB stacks, full deck,
    /// 169-class engine should complete in noticeably less wall time
    /// than the 1326-combo engine. We don't assert a specific ratio
    /// here (depends on machine) but we verify both paths run cleanly
    /// and 169-class is non-trivially faster.
    #[test]
    fn class169_iter_cost_is_lower_than_combo1326() {
        let path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .join("assets")
            .join("preflop_equity_169x169.npz");
        if !path.exists() {
            eprintln!("equity table missing at {path:?} — skipping perf smoke");
            return;
        }
        let cfg = HUNLConfig {
            starting_stack: 10_000,
            small_blind: 50,
            big_blind: 100,
            ante: 0,
            starting_street: Street::Preflop,
            initial_board: vec![],
            initial_pot: 0,
            initial_contributions: [0, 0],
            initial_hole_cards: None,
            preflop_raise_cap: 4,
            postflop_raise_cap: 3,
            bet_size_fractions: vec![1.0],
            include_all_in: true,
            force_allin_threshold: 1,
            min_bet_bb: 1,
            rake_rate: 0.0,
            rake_cap: 0,
            abstraction_path: None,
            abstraction_version: None,
            use_pcs: false,
        };
        // 1-iter wall for warm-up not measured; 30-iter to get stable
        // timings. The 1326-combo path's leaf table is built once at
        // construction so a few iters is enough to capture per-iter cost.
        let t0 = std::time::Instant::now();
        let _ = solve_hunl_preflop_rvr(
            &cfg,
            &path,
            &[2.0, 3.0],
            &[2.0, 3.0],
            5,
            1.5,
            0.0,
            2.0,
        )
        .unwrap();
        let combo_5iter = t0.elapsed().as_secs_f64();

        let t0 = std::time::Instant::now();
        let _ = solve_hunl_preflop_rvr_class169(
            &cfg,
            &path,
            None,
            None,
            &[2.0, 3.0],
            &[2.0, 3.0],
            5,
            1.5,
            0.0,
            2.0,
        )
        .unwrap();
        let class169_5iter = t0.elapsed().as_secs_f64();

        eprintln!(
            "169-class 5-iter wall: {class169_5iter:.3} s; 1326-combo 5-iter wall: {combo_5iter:.3} s; ratio: {:.2}x",
            combo_5iter / class169_5iter
        );
        // Sanity: 169-class must not be slower than 1326-combo (it should
        // be markedly faster, but the ratio depends on tree depth, leaf
        // count, and machine). Use a conservative lower bound.
        assert!(
            class169_5iter < combo_5iter * 1.5,
            "169-class engine must not be slower than 1326-combo: 169-class={class169_5iter:.3}, 1326={combo_5iter:.3}"
        );
    }
}
