//! HUNL postflop game state (Rust production tier).
//!
//! Adapted from `poker_solver/hunl.py` (project-internal, MIT) for semantics
//! and from `poker_solver/action_abstraction.py` (project-internal, MIT) for
//! the action-enumeration helpers. Action-enumeration shape mirrors
//! `references/code/noambrown_poker_solver/cpp/src/river_game.cpp` (MIT) by
//! pattern, not by code transcription.
//!
//! NEVER copy from `references/code/postflop-solver` (AGPL) or
//! `references/code/TexasSolver` (AGPL).
//!
//! Scope (PR 6): postflop only. Preflop chance outcomes (packed hole-card
//! 32-bit ints) do not fit in the `Game` trait's `u8` action type, and the
//! preflop port is PR 9. `HUNLState::initial` therefore requires
//! `starting_street >= Street::Flop` (a postflop config). The chance action
//! for board cards is a single `u8` card id (`card_to_int` form, [8, 59]).
//!
//! Integer-cent discipline: every chip value (contributions, stacks, to_call,
//! initial_pot, blinds, ante) is `i32` cents. The only float crossings happen
//! inside `compute_bet_amount` / `compute_raise_to`, where `pot * fraction`
//! is rounded back to `i32` immediately. Banker's rounding parity with
//! Python's `round()` on positive integers uses `(x + 0.5).floor() as i32`,
//! NOT Rust's `f64::round()` (which ties to even by default and would drift
//! from Python's round-half-away-from-zero on positive halves).

use crate::game::Game;
use std::sync::Arc;

// ============================================================================
// Street
// ============================================================================

/// Mirrors Python's `poker_solver.hunl.Street` IntEnum (values 0..=4).
///
/// `serde::Deserialize` implemented manually to match Python's IntEnum JSON
/// encoding (Python emits integers, not strings). See `_serialize_hunl_config`
/// on the Python side.
#[repr(u8)]
#[derive(Clone, Copy, Debug, Eq, PartialEq, Hash, Ord, PartialOrd)]
pub enum Street {
    Preflop = 0,
    Flop = 1,
    Turn = 2,
    River = 3,
    Showdown = 4,
}

impl<'de> serde::Deserialize<'de> for Street {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        let value: u8 = serde::Deserialize::deserialize(deserializer)?;
        Street::from_u8(value)
            .ok_or_else(|| serde::de::Error::custom(format!("invalid Street integer: {value}")))
    }
}

impl Street {
    fn from_u8(value: u8) -> Option<Street> {
        match value {
            0 => Some(Street::Preflop),
            1 => Some(Street::Flop),
            2 => Some(Street::Turn),
            3 => Some(Street::River),
            4 => Some(Street::Showdown),
            _ => None,
        }
    }

    /// Single-character street token used in `infoset_key`. Matches Python's
    /// `_STREET_TOKENS` map in `poker_solver/hunl.py`.
    fn token(self) -> &'static str {
        match self {
            Street::Preflop => "p",
            Street::Flop => "f",
            Street::Turn => "t",
            Street::River => "r",
            Street::Showdown => "s",
        }
    }
}

/// How many board cards are dealt when entering a given street from the
/// previous one. Matches Python's `_CARDS_TO_DEAL`.
fn cards_to_deal(street: Street) -> u8 {
    match street {
        Street::Flop => 3,
        Street::Turn | Street::River => 1,
        _ => 0,
    }
}

// ============================================================================
// Action IDs (verbatim with `poker_solver/action_abstraction.py`)
// ============================================================================

pub const ACTION_FOLD: u8 = 0;
pub const ACTION_CHECK: u8 = 1;
pub const ACTION_CALL: u8 = 2;
pub const ACTION_BET_33: u8 = 3;
pub const ACTION_BET_75: u8 = 4;
pub const ACTION_BET_100: u8 = 5;
pub const ACTION_BET_150: u8 = 6;
pub const ACTION_BET_200: u8 = 7;
pub const ACTION_RAISE_33: u8 = 8;
pub const ACTION_RAISE_75: u8 = 9;
pub const ACTION_RAISE_100: u8 = 10;
pub const ACTION_RAISE_150: u8 = 11;
pub const ACTION_RAISE_200: u8 = 12;
pub const ACTION_ALL_IN: u8 = 13;

const BET_ACTION_IDS: [u8; 5] = [
    ACTION_BET_33,
    ACTION_BET_75,
    ACTION_BET_100,
    ACTION_BET_150,
    ACTION_BET_200,
];

const RAISE_ACTION_IDS: [u8; 5] = [
    ACTION_RAISE_33,
    ACTION_RAISE_75,
    ACTION_RAISE_100,
    ACTION_RAISE_150,
    ACTION_RAISE_200,
];

fn is_opening_bet(action: u8) -> bool {
    matches!(
        action,
        ACTION_BET_33 | ACTION_BET_75 | ACTION_BET_100 | ACTION_BET_150 | ACTION_BET_200
    )
}

fn is_raise(action: u8) -> bool {
    matches!(
        action,
        ACTION_RAISE_33 | ACTION_RAISE_75 | ACTION_RAISE_100 | ACTION_RAISE_150 | ACTION_RAISE_200
    )
}

// ============================================================================
// Card encoding helper (matches `poker_solver/card.py::card_to_int`)
// ============================================================================

/// `rank * 4 + suit`, range `[8, 59]`. `rank in 2..=14`, `suit in 0..=3`.
#[inline]
pub const fn card_to_int(rank: u8, suit: u8) -> u8 {
    rank * 4 + suit
}

#[inline]
fn rank_of(card: u8) -> u8 {
    card >> 2
}

#[inline]
fn suit_of(card: u8) -> u8 {
    card & 3
}

/// Render a card as a 2-char string (matches Python's `Card.__str__`).
/// `RANKS = "23456789TJQKA"`, `SUITS = "shdc"`.
fn card_to_string(card: u8, out: &mut String) {
    const RANKS: &[u8; 13] = b"23456789TJQKA";
    const SUITS: &[u8; 4] = b"shdc";
    let r = rank_of(card);
    let s = suit_of(card);
    debug_assert!((2..=14).contains(&r), "bad rank for card {card}");
    debug_assert!(s < 4, "bad suit for card {card}");
    out.push(RANKS[(r - 2) as usize] as char);
    out.push(SUITS[s as usize] as char);
}

/// `_sorted_card_string` parity with Python's `poker_solver.hunl._sorted_card_string`.
fn sorted_card_string(cards: &[u8]) -> String {
    let mut sorted: Vec<u8> = cards.to_vec();
    // Python sorts by `(c.rank, c.suit)`. Since `card = rank*4 + suit`, sorting
    // by `card` ascending gives the same order.
    sorted.sort_unstable();
    let mut out = String::with_capacity(sorted.len() * 2);
    for &c in &sorted {
        card_to_string(c, &mut out);
    }
    out
}

// ============================================================================
// HUNLConfig
// ============================================================================

/// Immutable HUNL configuration. Mirrors Python's `HUNLConfig` dataclass.
///
/// `serde::Deserialize` impl matches `_serialize_hunl_config(config)` on the
/// Python side: the field set, types, and JSON keys are 1:1 with the Python
/// dataclass's serialized form. `serde(default)` lets the Python side omit
/// fields with default values without forcing them all to be emitted.
#[derive(Clone, Debug, serde::Deserialize)]
#[serde(default)]
pub struct HUNLConfig {
    pub starting_stack: i32,
    pub small_blind: i32,
    pub big_blind: i32,
    pub ante: i32,
    pub starting_street: Street,
    pub initial_board: Vec<u8>,
    pub initial_pot: i32,
    pub initial_contributions: [i32; 2],
    pub initial_hole_cards: Option<[[u8; 2]; 2]>,
    pub preflop_raise_cap: u8,
    pub postflop_raise_cap: u8,
    pub bet_size_fractions: Vec<f64>,
    pub include_all_in: bool,
    pub force_allin_threshold: i32,
    pub min_bet_bb: i32,
    pub rake_rate: f64,
    pub rake_cap: i32,
    /// Reference to the abstraction artifact on disk; `None` for lossless mode.
    /// The actual `AbstractionTables` is loaded by Agent B's `abstraction.rs`
    /// and threaded into the solver alongside the config; this field is the
    /// disk-side seam (path + version).
    pub abstraction_path: Option<String>,
    pub abstraction_version: Option<String>,
    /// PCS opt-in flag for PR 8 (v1.0.1: **Rust-internal only**).
    ///
    /// Default `false`. PR 6 ignores this field; PR 8 introduces the actual
    /// code path inside the Rust solver and microbench. The Python
    /// `HUNLConfig` dataclass (`poker_solver/hunl.py`) does NOT expose this
    /// field — the Python serializer at `_serialize_hunl_config` hardcodes
    /// `"use_pcs": False`, so Python callers cannot toggle PCS on. Exposing
    /// `use_pcs` to the Python tier is deferred to a follow-up PR; this
    /// avoids landing a half-wired Python surface for v1.0.1.
    pub use_pcs: bool,
}

impl Default for HUNLConfig {
    fn default() -> Self {
        Self {
            starting_stack: 10_000,
            small_blind: 50,
            big_blind: 100,
            ante: 0,
            starting_street: Street::Preflop,
            initial_board: Vec::new(),
            initial_pot: 0,
            initial_contributions: [0, 0],
            initial_hole_cards: None,
            preflop_raise_cap: 4,
            postflop_raise_cap: 3,
            bet_size_fractions: vec![0.33, 0.75, 1.00, 1.50, 2.00],
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
}

// ============================================================================
// HUNLState
// ============================================================================

/// HUNL game state (`Game`-conformant). Mirrors Python's `HUNLState`.
#[derive(Clone, Debug)]
pub struct HUNLState {
    /// `card_to_int` form. Empty when hole cards have not yet been dealt.
    /// Postflop initial states pre-populate this from `config.initial_hole_cards`.
    pub hole_cards: Option<[[u8; 2]; 2]>,
    pub board: Vec<u8>,
    pub street: Street,
    pub contributions: [i32; 2],
    pub stacks: [i32; 2],
    pub street_history: Vec<u8>,
    pub street_aggressor: i8,
    pub street_num_raises: u8,
    pub to_call: i32,
    pub cur_player: i8,
    pub folded: [bool; 2],
    pub all_in: [bool; 2],
    pub config: Arc<HUNLConfig>,
    /// Per-street betting tokens (each entry is the token sequence for one
    /// completed street). Append-only; finalized street's tokens move here.
    pub betting_tokens: Vec<Vec<String>>,
    /// Token sequence for the in-progress street.
    pub current_street_tokens: Vec<String>,
    /// Remaining board cards to deal before the next betting round. Used by
    /// the chance-node sequencing (flop = 3 → 2 → 1 → done; turn/river = 1).
    pub pending_board_deals: u8,
}

impl HUNLState {
    /// Construct the initial state from a config. Mirrors
    /// `HUNLPoker.initial_state` in `poker_solver/hunl.py`.
    ///
    /// **PR 6 restriction:** preflop start is not supported here (the chance
    /// action would be a 32-bit packed hole outcome that doesn't fit in
    /// `Game::Action = u8`). The Python side asserts this restriction at the
    /// PyO3 boundary (Agent B's `solve_hunl_postflop`); this function will
    /// panic if called with `Street::Preflop`, matching that contract.
    pub fn initial(config: Arc<HUNLConfig>) -> Self {
        // PR 9: preflop start is supported when `initial_hole_cards` is set
        // (subgame mode). Without hole cards the chance enum is intractable
        // (1.6M combos) and panics — that's the post-v1 follow-up.
        if config.starting_street == Street::Preflop {
            return Self::initial_preflop(config);
        }
        assert!(
            config.starting_street as u8 >= Street::Flop as u8,
            "HUNLState::initial: postflop branch requires Street::Flop or later. \
             Got starting_street={:?}",
            config.starting_street
        );
        let contributions = config.initial_contributions;
        // Per Python's `initial_state` postflop branch: each player starts with
        // the full starting_stack behind. Initial contributions are dead money
        // already in the pot.
        let stacks = [config.starting_stack, config.starting_stack];
        let all_in = [stacks[0] == 0, stacks[1] == 0];
        let hole_cards = config.initial_hole_cards;
        // PR 22 Fix A: mirror Python `HUNLPoker.initial_state` postflop branch
        // — honor asymmetric `initial_contributions` so facing-bet subgames
        // (MDF / c-bet response / bluff-catcher workflows) compose. Symmetric
        // `[c, c]` continues to yield `to_call=0`, `street_aggressor=-1`,
        // `street_num_raises=0`, `cur_player=1` (existing behavior unchanged).
        let c0 = contributions[0];
        let c1 = contributions[1];
        let (to_call, street_aggressor, postflop_first_actor): (i32, i8, i8) = if c0
            == c1
        {
            (0, -1, 1)
        } else if c0 < c1 {
            // P0 has less in; P0 faces the bet, P1 is the aggressor.
            (c1 - c0, 1, 0)
        } else {
            // P1 has less in; P1 faces the bet, P0 is the aggressor.
            (c0 - c1, 0, 1)
        };
        let street_num_raises: u8 = if to_call > 0 { 1 } else { 0 };
        let cur_player: i8 = if all_in[0] || all_in[1] || hole_cards.is_none() {
            -1
        } else {
            postflop_first_actor
        };
        let initial_board = config.initial_board.clone();
        Self {
            hole_cards,
            board: initial_board,
            street: config.starting_street,
            contributions,
            stacks,
            street_history: Vec::new(),
            street_aggressor,
            street_num_raises,
            to_call,
            cur_player,
            folded: [false, false],
            all_in,
            config,
            betting_tokens: Vec::new(),
            current_street_tokens: Vec::new(),
            pending_board_deals: 0,
        }
    }

    /// PR 9 — initial state for HUNL preflop subgame mode.
    ///
    /// Mirrors `HUNLPoker.initial_state` Python preflop branch in
    /// `poker_solver/hunl.py`: post the blinds + ante, set contributions,
    /// to_call = BB - SB, BB is the "aggressor" via the forced blind, SB
    /// (= P0) acts first.
    ///
    /// Requires `config.initial_hole_cards` to be set (full-tree mode with
    /// the 1.6M-combo chance enum is a post-v1 follow-up). `solve_hunl_preflop`
    /// validates this upstream; if reached without hole cards, cur_player is
    /// set to -1 (chance) which would then try to enumerate hole cards and
    /// panic in the caller.
    fn initial_preflop(config: Arc<HUNLConfig>) -> Self {
        let sb_contrib = config.small_blind + config.ante;
        let bb_contrib = config.big_blind + config.ante;
        let contributions = [sb_contrib, bb_contrib];
        let stacks = [
            config.starting_stack - sb_contrib,
            config.starting_stack - bb_contrib,
        ];
        let to_call = bb_contrib - sb_contrib;
        let hole_cards = config.initial_hole_cards;
        let cur_player: i8 = if hole_cards.is_some() { 0 } else { -1 };
        let all_in = [stacks[0] == 0, stacks[1] == 0];
        Self {
            hole_cards,
            board: Vec::new(),
            street: Street::Preflop,
            contributions,
            stacks,
            street_history: Vec::new(),
            // BB is the "aggressor" by virtue of posting the BB blind;
            // street_num_raises = 1 (the BB blind counts as one raise).
            street_aggressor: 1,
            street_num_raises: 1,
            to_call,
            cur_player,
            folded: [false, false],
            all_in,
            config,
            betting_tokens: Vec::new(),
            current_street_tokens: Vec::new(),
            pending_board_deals: 0,
        }
    }

    /// PR 15 — given a chance-enum root state (`hole_cards = None`,
    /// `cur_player = -1`), produce the child state with the supplied
    /// hand-pair dealt to both players. Mirrors Python's
    /// `_apply_chance(state, hole_action)` hole-card branch.
    ///
    /// `next_cur` matches the Python contract:
    ///   * preflop start → P0 (SB) acts first;
    ///   * postflop start (symmetric or P1 facing bet) → P1 (BB) acts first;
    ///   * postflop start (P0 facing bet via PR 22 asymmetric branch) → P0.
    ///
    /// Caller is responsible for not handing in hole cards that conflict
    /// with `state.board`; the exploit walk's `enumerate_hole_card_pairs`
    /// already filters out board collisions.
    pub fn clone_with_hole_cards(&self, hole: [[u8; 2]; 2]) -> Self {
        let next_cur: i8 = if self.street == Street::Preflop {
            0
        } else if self.contributions[0] < self.contributions[1] {
            // PR 22: P0 faces the bet → acts first postflop.
            0
        } else {
            1
        };
        let mut next = self.clone();
        next.hole_cards = Some(hole);
        next.cur_player = next_cur;
        next
    }

    /// Build the action context consumed by `enumerate_legal_actions` and the
    /// bet/raise size helpers. `pub` so integration tests
    /// (`crates/cfr_core/tests/hunl_state_unit.rs`) and downstream consumers
    /// can introspect bet/raise sizing without round-tripping through
    /// `legal_actions`. Companion helpers `enumerate_legal_actions`,
    /// `compute_bet_amount`, and `compute_raise_to` are already `pub` for the
    /// same reason; visibility consistency is the deciding factor.
    pub fn action_context(&self) -> ActionContext {
        let cfg = self.config.as_ref();
        // pot = sum(contributions) + initial_pot - sum(initial_contributions)
        let pot = self.contributions[0] + self.contributions[1] + cfg.initial_pot
            - cfg.initial_contributions[0]
            - cfg.initial_contributions[1];
        ActionContext {
            pot,
            to_call: self.to_call,
            stacks: self.stacks,
            contributions: self.contributions,
            cur_player: self.cur_player.max(0) as u8,
            street: self.street,
            street_num_raises: self.street_num_raises,
            street_aggressor: self.street_aggressor,
            big_blind: cfg.big_blind,
            bet_size_fractions: cfg.bet_size_fractions.clone(),
            preflop_raise_cap: cfg.preflop_raise_cap,
            postflop_raise_cap: cfg.postflop_raise_cap,
            force_allin_threshold: cfg.force_allin_threshold,
            min_bet_bb: cfg.min_bet_bb,
            include_all_in: cfg.include_all_in,
        }
    }

    pub fn is_terminal(&self) -> bool {
        if self.folded[0] || self.folded[1] {
            return true;
        }
        self.street == Street::Showdown
    }

    /// Per-player utility in big-blind units. Mirrors Python's
    /// `HUNLPoker.utility`. Only valid when `is_terminal()`.
    pub fn utility(&self) -> [f64; 2] {
        let bb = self.config.big_blind as f64;
        let c0 = self.contributions[0] as f64;
        let c1 = self.contributions[1] as f64;
        if self.folded[0] {
            return [-c0 / bb, c0 / bb];
        }
        if self.folded[1] {
            return [c1 / bb, -c1 / bb];
        }
        let hole = self.hole_cards.expect("showdown requires dealt hole cards");
        // Build 7-card hand: hole + board.
        let board = &self.board;
        debug_assert!(
            board.len() == 5,
            "showdown requires a 5-card board, got {} cards",
            board.len()
        );
        let mut seven0 = [0u8; 7];
        let mut seven1 = [0u8; 7];
        seven0[0] = hole[0][0];
        seven0[1] = hole[0][1];
        seven1[0] = hole[1][0];
        seven1[1] = hole[1][1];
        seven0[2..7].copy_from_slice(&board[..5]);
        seven1[2..7].copy_from_slice(&board[..5]);
        let s0 = crate::hunl_eval::Strength::evaluate_7(&seven0);
        let s1 = crate::hunl_eval::Strength::evaluate_7(&seven1);
        if s0 > s1 {
            [c1 / bb, -c1 / bb]
        } else if s1 > s0 {
            [-c0 / bb, c0 / bb]
        } else {
            // Tie — Python returns (0.0, 0.0), matching here.
            [0.0, 0.0]
        }
    }

    pub fn current_player(&self) -> i8 {
        if self.is_terminal() {
            return -1;
        }
        self.cur_player
    }

    /// Uniform-over-remaining chance outcomes for board cards. Empty when
    /// not a chance node. Mirrors `HUNLPoker.chance_outcomes` postflop path
    /// (preflop hole-deal path is PR 9 / out of scope per file-level note).
    pub fn chance_outcomes(&self) -> Vec<(u8, f64)> {
        if self.cur_player != -1 || self.is_terminal() {
            return Vec::new();
        }
        // PR 6 is postflop-only — hole cards must already be dealt. Build the
        // remaining-deck set per `_board_card_outcomes`.
        let hole = match self.hole_cards {
            Some(h) => h,
            None => {
                // Defensive: shouldn't happen post-init. Return empty rather
                // than enumerate preflop combinations (which don't fit in u8).
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

    pub fn legal_actions(&self) -> Vec<u8> {
        if self.is_terminal() || self.cur_player == -1 {
            return Vec::new();
        }
        let ctx = self.action_context();
        enumerate_legal_actions(&ctx)
    }

    pub fn apply(&self, action: u8) -> HUNLState {
        if self.cur_player == -1 {
            self.apply_chance(action)
        } else {
            self.apply_player(action)
        }
    }

    /// Build the per-player infoset key. Lossless format matches Python's
    /// `f"{player_hole}|{board}|{street_token}|{betting_history}"`; bucketed
    /// format matches `f"b{bucket_id}|{street_token}|{betting_history}"`.
    ///
    /// `abstraction` is the optional loaded bucket-table. Preflop always uses
    /// the lossless branch (matches Python's PR 4 §3.5 decision). If passed
    /// `None`, the lossless branch is taken unconditionally. The abstraction
    /// is threaded by the solver (Agent B's `hunl_solver.rs`); `HUNLState`
    /// does not hold it.
    pub fn infoset_key(
        &self,
        player: u8,
        abstraction: Option<&crate::abstraction::AbstractionTables>,
    ) -> String {
        let street_token = self.street.token();
        let history = self.format_history();
        if let Some(abst) = abstraction {
            if self.street as u8 >= Street::Flop as u8 {
                let hole = self
                    .hole_cards
                    .expect("bucketed infoset key requires dealt hole cards");
                let bucket_id = crate::abstraction::lookup_bucket(
                    abst,
                    &self.board,
                    &hole[player as usize],
                    self.street,
                );
                return format!("b{bucket_id}|{street_token}|{history}");
            }
        }
        // Lossless path.
        let player_hole = match self.hole_cards {
            Some(h) => sorted_card_string(&h[player as usize]),
            None => String::new(),
        };
        let board_str = sorted_card_string(&self.board);
        format!("{player_hole}|{board_str}|{street_token}|{history}")
    }

    /// Build the `betting_history` portion of the infoset key: joined-by-`/`
    /// per-street token concatenations. Matches Python's
    /// `"/".join("".join(tokens) for tokens in all_streets)`.
    fn format_history(&self) -> String {
        let total_streets = self.betting_tokens.len() + 1;
        let mut parts: Vec<String> = Vec::with_capacity(total_streets);
        for street_tokens in &self.betting_tokens {
            parts.push(street_tokens.concat());
        }
        parts.push(self.current_street_tokens.concat());
        parts.join("/")
    }

    fn apply_chance(&self, card: u8) -> HUNLState {
        // PR 6: only board-card chance actions are supported. Hole-card
        // chance actions (32-bit packed) would lose information in a `u8`
        // and are deferred to PR 9. Validate defensively.
        debug_assert!(
            self.hole_cards.is_some(),
            "apply_chance: PR 6 expects hole cards to be pre-populated"
        );
        let mut next = self.clone();
        next.board.push(card);
        let pending = next.pending_board_deals.saturating_sub(1);
        next.pending_board_deals = pending;
        if pending > 0 {
            return next;
        }
        self.after_board_dealt(next)
    }

    fn after_board_dealt(&self, mut state: HUNLState) -> HUNLState {
        if state.all_in[0] || state.all_in[1] {
            // Run-out: keep dealing one card at a time until board is full,
            // then go to showdown.
            if state.board.len() >= 5 {
                state.street = Street::Showdown;
                state.cur_player = -1;
                return state;
            }
            state.cur_player = -1;
            state.pending_board_deals = 1;
            return state;
        }
        state.cur_player = 1;
        state
    }

    fn apply_player(&self, action: u8) -> HUNLState {
        let ctx = self.action_context();
        let player = self.cur_player as usize;
        let mut contributions = self.contributions;
        let mut stacks = self.stacks;
        let mut folded = self.folded;
        let mut all_in = self.all_in;
        let mut street_aggressor = self.street_aggressor;
        let mut street_num_raises = self.street_num_raises;
        let mut to_call = self.to_call;
        let token: String;

        match action {
            ACTION_FOLD => {
                folded[player] = true;
                token = "f".to_string();
            }
            ACTION_CHECK => {
                token = "x".to_string();
            }
            ACTION_CALL => {
                let pay = self.to_call.min(stacks[player]);
                contributions[player] += pay;
                stacks[player] -= pay;
                if stacks[player] == 0 {
                    all_in[player] = true;
                }
                to_call = 0;
                token = "c".to_string();
            }
            ACTION_ALL_IN => {
                let pay = stacks[player];
                contributions[player] += pay;
                stacks[player] = 0;
                all_in[player] = true;
                let opp = 1 - player;
                to_call = (contributions[player] - contributions[opp]).max(0);
                street_aggressor = player as i8;
                street_num_raises += 1;
                token = "A".to_string();
            }
            a if is_opening_bet(a) => {
                let amount = compute_bet_amount(a, &ctx);
                contributions[player] += amount;
                stacks[player] -= amount;
                if stacks[player] == 0 {
                    all_in[player] = true;
                }
                let opp = 1 - player;
                to_call = contributions[player] - contributions[opp];
                street_aggressor = player as i8;
                street_num_raises += 1;
                token = format!("b{amount}");
            }
            a if is_raise(a) => {
                let new_contrib = compute_raise_to(a, &ctx);
                let pay = new_contrib - contributions[player];
                contributions[player] = new_contrib;
                stacks[player] -= pay;
                if stacks[player] == 0 {
                    all_in[player] = true;
                }
                let opp = 1 - player;
                to_call = contributions[player] - contributions[opp];
                street_aggressor = player as i8;
                street_num_raises += 1;
                token = format!("r{new_contrib}");
            }
            other => panic!("Unknown HUNL action: {other}"),
        }

        let mut new_state = self.clone();
        new_state.contributions = contributions;
        new_state.stacks = stacks;
        new_state.street_history.push(action);
        new_state.current_street_tokens.push(token);
        new_state.street_aggressor = street_aggressor;
        new_state.street_num_raises = street_num_raises;
        new_state.to_call = to_call;
        new_state.folded = folded;
        new_state.all_in = all_in;

        // Fold ends the hand.
        if new_state.folded[0] || new_state.folded[1] {
            new_state.cur_player = -1;
            return new_state;
        }
        if self.street_complete(action, &new_state) {
            return self.begin_street_transition(new_state);
        }
        // PR 22: if the next-to-act player is already all-in, they cannot act.
        // Refund any uncalled excess (over-shove) to the aggressor and close
        // the street. Reachable when an over-shove all-in is "called" by an
        // opponent who is already all-in for less, via the asymmetric
        // facing-bet branch.
        let next_player = 1 - player;
        if new_state.all_in[next_player] {
            let opp = next_player;
            let refund = (new_state.contributions[player] - new_state.contributions[opp]).max(0);
            if refund > 0 {
                new_state.contributions[player] -= refund;
                new_state.stacks[player] += refund;
                new_state.all_in[player] = new_state.stacks[player] == 0;
            }
            new_state.to_call = 0;
            return self.begin_street_transition(new_state);
        }
        new_state.cur_player = (1 - player) as i8;
        new_state
    }

    /// `_street_complete` parity with `poker_solver/hunl.py`.
    fn street_complete(&self, action: u8, new_state: &HUNLState) -> bool {
        if action == ACTION_FOLD {
            return false;
        }
        if new_state.to_call > 0 {
            return false;
        }
        // All-in that closes a prior aggression ends the street.
        if action == ACTION_ALL_IN && self.to_call > 0 {
            return true;
        }
        let player = self.cur_player;
        let opponent = 1 - player;
        // Postflop check-through: both players check with no aggression.
        if action == ACTION_CHECK
            && self.street_aggressor == -1
            && new_state.street_history.len() >= 2
        {
            return true;
        }
        // Preflop BB option: after SB limp, BB checking through ends the round.
        if self.street == Street::Preflop
            && action == ACTION_CHECK
            && player == 1
            && self.street_aggressor == 1
            && self.street_num_raises == 1
        {
            return true;
        }
        // A call closes the street unless it was a preflop SB limp.
        if action == ACTION_CALL {
            let preflop_sb_limp = self.street == Street::Preflop
                && self.street_aggressor == opponent
                && self.street_num_raises == 1
                && player == 0;
            return !preflop_sb_limp;
        }
        false
    }

    /// `_begin_street_transition` parity. Pushes the in-progress tokens onto
    /// `betting_tokens`, then either: (a) goes to showdown on river, (b) sets
    /// up the all-in run-out, or (c) transitions to the next street with the
    /// usual `pending_board_deals`.
    fn begin_street_transition(&self, mut state: HUNLState) -> HUNLState {
        let tokens = std::mem::take(&mut state.current_street_tokens);
        state.betting_tokens.push(tokens);
        if state.street == Street::River {
            state.street = Street::Showdown;
            state.cur_player = -1;
            return state;
        }
        if state.all_in[0] || state.all_in[1] {
            // All-in run-out: chance deals one card at a time until the board
            // is full (length 5).
            state.cur_player = -1;
            state.pending_board_deals = 1;
            state.street_history.clear();
            state.street_aggressor = -1;
            state.street_num_raises = 0;
            state.to_call = 0;
            return state;
        }
        let next_street_val = state.street as u8 + 1;
        let next_street = Street::from_u8(next_street_val).expect("next street in range");
        let deals = cards_to_deal(next_street);
        state.street = next_street;
        state.cur_player = -1;
        state.pending_board_deals = deals;
        state.street_history.clear();
        state.street_aggressor = -1;
        state.street_num_raises = 0;
        state.to_call = 0;
        state
    }
}

impl Game for HUNLState {
    fn num_players() -> usize {
        2
    }

    /// Postflop-only initial state. Builds a default-config river state with
    /// `default_tiny_subgame` so the generic `DCFRSolver` can instantiate the
    /// trait; in practice HUNL solves always go through
    /// `HUNLState::initial(config)` (Agent B owns that wiring).
    fn initial() -> Self {
        HUNLState::initial(Arc::new(default_tiny_subgame()))
    }

    fn is_terminal(&self) -> bool {
        HUNLState::is_terminal(self)
    }

    fn utility(&self) -> [f64; 2] {
        HUNLState::utility(self)
    }

    fn current_player(&self) -> i8 {
        HUNLState::current_player(self)
    }

    fn chance_outcomes(&self) -> Vec<(u8, f64)> {
        HUNLState::chance_outcomes(self)
    }

    fn legal_actions(&self) -> Vec<u8> {
        HUNLState::legal_actions(self)
    }

    fn apply(&self, action: u8) -> Self {
        HUNLState::apply(self, action)
    }

    /// Trait-side infoset key: takes no abstraction (lossless mode). Solver
    /// paths that need bucketed keys call `HUNLState::infoset_key(player,
    /// Some(&tables))` directly.
    fn infoset_key(&self, player: u8) -> String {
        HUNLState::infoset_key(self, player, None)
    }
}

/// River-only test fixture: matches Python's
/// `poker_solver.hunl.default_tiny_subgame`. AhKc vs QdQh on As7c2dKh5s,
/// pot=1000, stacks=1000, BB=100.
pub fn default_tiny_subgame() -> HUNLConfig {
    let board = vec![
        card_to_int(14, 0), // As
        card_to_int(7, 3),  // 7c
        card_to_int(2, 2),  // 2d
        card_to_int(13, 1), // Kh
        card_to_int(5, 0),  // 5s
    ];
    let hole = [
        [card_to_int(14, 1), card_to_int(13, 3)], // AhKc
        [card_to_int(12, 2), card_to_int(12, 1)], // QdQh
    ];
    HUNLConfig {
        starting_stack: 1000,
        starting_street: Street::River,
        initial_board: board,
        initial_pot: 1000,
        initial_contributions: [500, 500],
        initial_hole_cards: Some(hole),
        ..Default::default()
    }
}

// ============================================================================
// Action context + enumeration (port of action_abstraction.py)
// ============================================================================

/// Per-decision action-enumeration context. `pub(crate)` because the tree
/// builder and tests want to call the helpers directly; not part of the
/// public PyO3 surface (Agent B handles JSON marshalling).
#[derive(Clone, Debug)]
pub struct ActionContext {
    pub pot: i32,
    pub to_call: i32,
    pub stacks: [i32; 2],
    pub contributions: [i32; 2],
    pub cur_player: u8,
    pub street: Street,
    pub street_num_raises: u8,
    pub street_aggressor: i8,
    pub big_blind: i32,
    pub bet_size_fractions: Vec<f64>,
    pub preflop_raise_cap: u8,
    pub postflop_raise_cap: u8,
    pub force_allin_threshold: i32,
    pub min_bet_bb: i32,
    pub include_all_in: bool,
}

fn is_preflop(ctx: &ActionContext) -> bool {
    ctx.street == Street::Preflop
}

fn raise_cap(ctx: &ActionContext) -> u8 {
    if is_preflop(ctx) {
        ctx.preflop_raise_cap
    } else {
        ctx.postflop_raise_cap
    }
}

fn min_bet(ctx: &ActionContext) -> i32 {
    ctx.min_bet_bb * ctx.big_blind
}

fn force_allin_chip_threshold(ctx: &ActionContext) -> i32 {
    ctx.force_allin_threshold * ctx.big_blind
}

fn stack_remaining(ctx: &ActionContext) -> i32 {
    ctx.stacks[ctx.cur_player as usize]
}

fn min_raise_increment(ctx: &ActionContext) -> i32 {
    ctx.to_call.max(ctx.big_blind)
}

/// Banker's-rounding parity with Python's `round()` on non-negative values.
///
/// Python's `round()` uses **round-half-to-even** (banker's rounding):
///   - `round(0.5) == 0` (0 is even)
///   - `round(1.5) == 2` (2 is even)
///   - `round(2.5) == 2` (2 is even)
///   - `round(622.5) == 622` (622 is even)
///   - `round(623.5) == 624` (624 is even)
///
/// PR 9 update: the prior implementation `(value + 0.5).floor()` was
/// **round-half-up**, NOT banker's. That matched Python for ~half of all
/// `.5` cases by accident (odd integer parts) but disagreed for the other
/// half (even integer parts), causing the PR 6 test
/// `test_hunl_flop_dry_3size_diff_python_vs_rust_tiny_abstraction` to fail
/// and the PR 9 diff test `test_diff_aa_vs_kk_100bb` to fail on
/// preflop spots with `r1037` (Python) vs `r1038` (Rust) token drift.
///
/// We use Rust's `f64::round_ties_even()` (stable Rust 1.77+) which
/// implements true banker's rounding directly. Falls back to a manual
/// implementation if MSRV constrains us.
fn python_round_positive(value: f64) -> i32 {
    debug_assert!(
        value >= 0.0,
        "python_round_positive expects non-negative input"
    );
    // round_ties_even is stable since Rust 1.77.
    value.round_ties_even() as i32
}

fn bet_amount_for_fraction(ctx: &ActionContext, fraction: f64) -> i32 {
    let raw = python_round_positive(ctx.pot as f64 * fraction);
    raw.max(min_bet(ctx))
}

fn raise_to_for_fraction(ctx: &ActionContext, fraction: f64) -> i32 {
    let aggressor_idx = ctx.street_aggressor.max(0) as usize;
    let aggressor_contrib = ctx.contributions[aggressor_idx];
    let raw_increment = python_round_positive((ctx.pot + ctx.to_call) as f64 * fraction);
    let raise_to = aggressor_contrib + raw_increment;
    let min_raise_to = aggressor_contrib + min_raise_increment(ctx);
    raise_to.max(min_raise_to)
}

/// Chip delta added by an opening bet (or an opening all-in). Mirrors
/// `compute_bet_amount` in Python.
pub fn compute_bet_amount(action_id: u8, ctx: &ActionContext) -> i32 {
    let stack = stack_remaining(ctx);
    if action_id == ACTION_ALL_IN {
        return stack;
    }
    let idx = BET_ACTION_IDS
        .iter()
        .position(|&id| id == action_id)
        .unwrap_or_else(|| panic!("compute_bet_amount: action_id {action_id} is not a bet"));
    let fraction = ctx.bet_size_fractions[idx];
    bet_amount_for_fraction(ctx, fraction).min(stack)
}

/// New `contributions[cur_player]` total after a raise/all-in. Mirrors
/// `compute_raise_to` in Python.
pub fn compute_raise_to(action_id: u8, ctx: &ActionContext) -> i32 {
    let cur_contrib = ctx.contributions[ctx.cur_player as usize];
    let stack = stack_remaining(ctx);
    let max_raise_to = cur_contrib + stack;
    if action_id == ACTION_ALL_IN {
        return max_raise_to;
    }
    let idx = RAISE_ACTION_IDS
        .iter()
        .position(|&id| id == action_id)
        .unwrap_or_else(|| panic!("compute_raise_to: action_id {action_id} is not a raise"));
    let fraction = ctx.bet_size_fractions[idx];
    raise_to_for_fraction(ctx, fraction).min(max_raise_to)
}

fn enumerate_bets(ctx: &ActionContext) -> Vec<u8> {
    let stack = stack_remaining(ctx);
    let force_threshold = force_allin_chip_threshold(ctx);
    let mut seen_amounts: Vec<i32> = Vec::with_capacity(5);
    let mut actions: Vec<u8> = Vec::with_capacity(5);
    for (action_id, &fraction) in BET_ACTION_IDS.iter().zip(ctx.bet_size_fractions.iter()) {
        let raw_amount = bet_amount_for_fraction(ctx, fraction);
        if raw_amount >= stack || (stack - raw_amount) <= force_threshold {
            continue;
        }
        if seen_amounts.contains(&raw_amount) {
            continue;
        }
        seen_amounts.push(raw_amount);
        actions.push(*action_id);
    }
    actions
}

fn enumerate_raises(ctx: &ActionContext) -> Vec<u8> {
    let cur_contrib = ctx.contributions[ctx.cur_player as usize];
    let stack = stack_remaining(ctx);
    let max_raise_to = cur_contrib + stack;
    let force_threshold = force_allin_chip_threshold(ctx);
    let mut seen_raise_tos: Vec<i32> = Vec::with_capacity(5);
    let mut actions: Vec<u8> = Vec::with_capacity(5);
    for (action_id, &fraction) in RAISE_ACTION_IDS.iter().zip(ctx.bet_size_fractions.iter()) {
        let raise_to = raise_to_for_fraction(ctx, fraction);
        let chips_added = raise_to - cur_contrib;
        if raise_to >= max_raise_to || (stack - chips_added) <= force_threshold {
            continue;
        }
        if seen_raise_tos.contains(&raise_to) {
            continue;
        }
        seen_raise_tos.push(raise_to);
        actions.push(*action_id);
    }
    actions
}

/// Sorted list of legal action IDs. Mirrors Python's
/// `enumerate_legal_actions(ctx)`.
pub fn enumerate_legal_actions(ctx: &ActionContext) -> Vec<u8> {
    let mut actions: Vec<u8> = Vec::with_capacity(14);
    let stack = stack_remaining(ctx);

    if stack <= 0 {
        return actions;
    }

    let facing_bet = ctx.to_call > 0;

    if facing_bet {
        actions.push(ACTION_FOLD);
        actions.push(ACTION_CALL);
    } else {
        actions.push(ACTION_CHECK);
    }

    let cap = raise_cap(ctx);
    let cap_reached = ctx.street_num_raises >= cap;

    if !cap_reached {
        if facing_bet {
            actions.extend(enumerate_raises(ctx));
        } else {
            actions.extend(enumerate_bets(ctx));
        }
    }

    if ctx.include_all_in {
        actions.push(ACTION_ALL_IN);
    }

    actions.sort_unstable();
    actions
}

// ============================================================================
// Inline tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    fn river_state() -> HUNLState {
        let cfg = Arc::new(default_tiny_subgame());
        HUNLState::initial(cfg)
    }

    #[test]
    fn action_ids_match_python_constants() {
        // Pinned to the values in poker_solver/action_abstraction.py.
        assert_eq!(ACTION_FOLD, 0);
        assert_eq!(ACTION_CHECK, 1);
        assert_eq!(ACTION_CALL, 2);
        assert_eq!(ACTION_BET_33, 3);
        assert_eq!(ACTION_BET_75, 4);
        assert_eq!(ACTION_BET_100, 5);
        assert_eq!(ACTION_BET_150, 6);
        assert_eq!(ACTION_BET_200, 7);
        assert_eq!(ACTION_RAISE_33, 8);
        assert_eq!(ACTION_RAISE_75, 9);
        assert_eq!(ACTION_RAISE_100, 10);
        assert_eq!(ACTION_RAISE_150, 11);
        assert_eq!(ACTION_RAISE_200, 12);
        assert_eq!(ACTION_ALL_IN, 13);
    }

    #[test]
    fn card_encoding_matches_python_range() {
        // rank in 2..=14, suit in 0..=3 → range [8, 59]
        assert_eq!(card_to_int(2, 0), 8);
        assert_eq!(card_to_int(14, 3), 59);
        // Round-trip via rank_of/suit_of.
        for r in 2..=14 {
            for s in 0..4 {
                let c = card_to_int(r, s);
                assert_eq!(rank_of(c), r);
                assert_eq!(suit_of(c), s);
            }
        }
    }

    #[test]
    fn river_subgame_root_is_player_one_to_act() {
        let s = river_state();
        assert_eq!(s.street, Street::River);
        assert_eq!(s.cur_player, 1);
        assert_eq!(s.contributions, [500, 500]);
        assert_eq!(s.stacks, [1000, 1000]);
        assert_eq!(s.to_call, 0);
    }

    #[test]
    fn river_subgame_legal_actions_postflop_open() {
        let s = river_state();
        let acts = s.legal_actions();
        // Facing no bet: CHECK first, then bets (any non-collapsed), then ALL_IN.
        // With pot=1000, BB=100, bet_fractions=[0.33,0.75,1.0,1.5,2.0] and
        // stack=1000, ALL_IN absorbs the >stack candidates and the
        // force_allin_threshold may collapse near-shove bets.
        assert!(acts.contains(&ACTION_CHECK));
        assert!(acts.contains(&ACTION_ALL_IN));
        assert!(acts.is_sorted());
    }

    #[test]
    fn fold_terminates_with_loser_paying_contrib() {
        let s = river_state();
        // P1 checks; P0 then folds — pots end with P0 losing their contrib.
        let after_check = s.apply(ACTION_CHECK);
        assert_eq!(after_check.cur_player, 0);
        let after_fold = after_check.apply(ACTION_FOLD);
        assert!(after_fold.is_terminal());
        let u = after_fold.utility();
        // contributions[0] = 500, BB = 100 → P0 loses 5 BB, P1 wins 5 BB.
        assert!((u[0] - (-5.0)).abs() < 1e-9, "P0 utility = {}", u[0]);
        assert!((u[1] - 5.0).abs() < 1e-9, "P1 utility = {}", u[1]);
    }

    #[test]
    fn showdown_winner_collects_loser_contrib() {
        // River-only subgame: AhKc (P0) vs QdQh (P1). The board has an Ace
        // → P0 has top pair, beats P1's underpair. P1 checks; P0 checks;
        // showdown.
        let s = river_state();
        let after_p1_check = s.apply(ACTION_CHECK);
        let after_p0_check = after_p1_check.apply(ACTION_CHECK);
        assert!(after_p0_check.is_terminal());
        assert_eq!(after_p0_check.street, Street::Showdown);
        let u = after_p0_check.utility();
        // P0 wins → P0 = c1/BB = 500/100 = 5.0, P1 = -c0/BB = -5.0
        assert!((u[0] - 5.0).abs() < 1e-9, "P0 utility = {}", u[0]);
        assert!((u[1] - (-5.0)).abs() < 1e-9, "P1 utility = {}", u[1]);
    }

    #[test]
    fn infoset_key_lossless_format_uses_sorted_cards() {
        let s = river_state();
        // Trim history to a clean checkpoint.
        let key0 = s.infoset_key(0, None);
        // Format: "{player_hole}|{board}|r|" — river token "r", empty history.
        // P0's hole is AhKc; sorted by (rank, suit) ascending: Kc then Ah.
        // Card encoding: Kc = rank 13, suit 3 → "Kc"; Ah = rank 14, suit 1 → "Ah".
        // sorted ascending by (rank,suit) → Kc (13,3) < Ah (14,1) → "KcAh"
        // Board sorted: As(14,0) > Kh(13,1) > 7c(7,3) > 5s(5,0) > 2d(2,2)
        // Ascending: 2d, 5s, 7c, Kh, As
        assert_eq!(key0, "KcAh|2d5s7cKhAs|r|");
    }

    #[test]
    fn check_check_advances_to_showdown_on_river() {
        let s = river_state();
        assert_eq!(s.cur_player, 1);
        let a = s.apply(ACTION_CHECK);
        assert_eq!(a.cur_player, 0);
        let b = a.apply(ACTION_CHECK);
        assert!(b.is_terminal());
        assert_eq!(b.street, Street::Showdown);
    }

    #[test]
    fn raise_cap_postflop_is_three() {
        // Build a flop config so we can test the postflop cap.
        let board = vec![card_to_int(14, 0), card_to_int(7, 3), card_to_int(2, 2)];
        let hole = [
            [card_to_int(14, 1), card_to_int(13, 3)],
            [card_to_int(12, 2), card_to_int(12, 1)],
        ];
        let cfg = HUNLConfig {
            starting_stack: 100_000, // very deep so all bets/raises stay legal
            starting_street: Street::Flop,
            initial_board: board,
            initial_pot: 200,
            initial_contributions: [100, 100],
            initial_hole_cards: Some(hole),
            ..Default::default()
        };
        let s = HUNLState::initial(Arc::new(cfg));
        // P1 bets 100% pot → P0 raises → P1 raises → P0 raises (4th raise);
        // verify each step's legal_actions reflect the cap.
        let s1 = s.apply(ACTION_BET_100); // raises=1
        assert_eq!(s1.street_num_raises, 1);
        // P0 should still have raise options at raises=1.
        assert!(s1.legal_actions().iter().any(|&a| is_raise(a)));
        let s2 = s1.apply(ACTION_RAISE_100); // raises=2
        assert!(s2.legal_actions().iter().any(|&a| is_raise(a)));
        let s3 = s2.apply(ACTION_RAISE_100); // raises=3 → at cap
                                             // At cap → no raises legal (only fold/call/all-in).
        let acts = s3.legal_actions();
        assert!(
            !acts.iter().any(|&a| is_raise(a)),
            "raise after cap: {acts:?}"
        );
        assert!(acts.contains(&ACTION_FOLD));
        assert!(acts.contains(&ACTION_CALL));
    }

    #[test]
    fn banker_rounding_matches_python_on_half() {
        // Python's `round()` is banker's rounding (round-half-to-even).
        // PR 9 aligned `python_round_positive` with that convention via
        // `f64::round_ties_even`, fixing the prior round-half-up drift that
        // surfaced as `r1037` (Python) vs `r1038` (Rust) on `.5` ties.
        // The asserts below verify the new behavior matches Python exactly
        // on the canonical half-integer inputs:
        //   round(0.5) == 0  (0 is even)
        //   round(1.5) == 2  (2 is even)
        //   round(2.5) == 2  (2 is even)
        //   round(3.5) == 4  (4 is even)
        assert_eq!(python_round_positive(0.5), 0);
        assert_eq!(python_round_positive(1.5), 2);
        assert_eq!(python_round_positive(2.5), 2);
        assert_eq!(python_round_positive(3.5), 4);
        assert_eq!(python_round_positive(0.4999), 0);
        assert_eq!(python_round_positive(0.6), 1);
        // Standard non-half cases match Python's round() exactly.
        assert_eq!(python_round_positive(330.0), 330);
        assert_eq!(python_round_positive(329.7), 330);
    }
}
