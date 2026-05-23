//! Leduc poker (Rust production tier).
//!
//! Adapted from open_spiel/games/leduc_poker.cc (Apache 2.0) for semantics;
//! structural design original (mirrors `poker_solver/games.py::LeducPoker`).
//!
//! Leduc poker is the canonical small two-round CFR benchmark (Southey et al.,
//! UAI 2005). Deck: two suits of (J=11, Q=12, K=13). Each player antes 1 chip,
//! then receives one private card. Round 1 betting (raise size 2, max 2
//! raises), then a single public card is revealed. Round 2 betting (raise size
//! 4, max 2 raises). At showdown a player whose private card matches the
//! public card wins; otherwise the higher private card wins; ties split the
//! pot.
//!
//! Action ids match `open_spiel`'s encoding: fold=0, call=1, raise=2. A player
//! may fold only when facing an unmatched bet; otherwise legal actions are
//! `{call, raise}` (and only `{call}` when the raise cap is hit). The starting
//! player for both betting rounds is P0.
//!
//! This file is a structural port of `poker_solver/games.py::LeducPoker` —
//! field-for-field. The cross-tier differential machinery (`solver.py` +
//! `_solve_rust` recomputation) keeps the two in lockstep.

use crate::game::Game;

pub const LEDUC_FOLD: u8 = 0;
pub const LEDUC_CALL: u8 = 1;
pub const LEDUC_RAISE: u8 = 2;

/// Two suits of J/Q/K — six cards total.
const LEDUC_DECK: [i8; 6] = [11, 11, 12, 12, 13, 13];
const LEDUC_FIRST_RAISE: i32 = 2;
const LEDUC_SECOND_RAISE: i32 = 4;
const LEDUC_MAX_RAISES: u8 = 2;
const LEDUC_ANTE: i32 = 1;

/// Render the action history of a single betting round (matches Python's
/// `_leduc_round_string`). Used only for infoset keys.
fn round_string(history: &[u8]) -> String {
    let mut s = String::with_capacity(history.len());
    for &a in history {
        s.push(match a {
            LEDUC_FOLD => 'f',
            LEDUC_CALL => 'c',
            LEDUC_RAISE => 'r',
            _ => panic!("invalid Leduc action in history: {a}"),
        });
    }
    s
}

/// Leduc poker state — field-for-field port of Python's `LeducState`
/// dataclass.
#[derive(Clone, Debug)]
pub struct LeducState {
    /// Private cards by player index. `len() < 2` while dealing.
    pub private_cards: Vec<i8>,
    /// Public card (round-2 board card); `None` until round 2 starts.
    pub public_card: Option<i8>,
    /// Round-1 betting history (PASS/CALL/RAISE ids).
    pub round1_history: Vec<u8>,
    /// Round-2 betting history (PASS/CALL/RAISE ids).
    pub round2_history: Vec<u8>,
    /// Chips put in so far by each player (includes ante).
    pub ante: [i32; 2],
    /// Per-player fold flag.
    pub folded: [bool; 2],
    /// 1 = pre-flop, 2 = post-flop.
    pub round_num: u8,
    /// Raises taken in the current round.
    pub num_raises: u8,
    /// Calls taken since the last raise (or start of round if no raise yet).
    pub num_calls: u8,
    /// Highest ante seen so far (the current stake to call).
    pub stakes: i32,
    /// Player to act, or -1 for chance.
    pub cur_player: i8,
}

impl LeducState {
    pub fn initial() -> Self {
        Self {
            private_cards: Vec::new(),
            public_card: None,
            round1_history: Vec::new(),
            round2_history: Vec::new(),
            ante: [LEDUC_ANTE, LEDUC_ANTE],
            folded: [false, false],
            round_num: 1,
            num_raises: 0,
            num_calls: 0,
            stakes: LEDUC_ANTE,
            cur_player: -1,
        }
    }

    /// Sum of both antes (chips currently in the pot). Not consumed by the
    /// solver but mirrors Python's `LeducState.pot` for debugging and parity.
    #[allow(dead_code)]
    pub fn pot(&self) -> i32 {
        self.ante[0] + self.ante[1]
    }

    pub fn is_terminal(&self) -> bool {
        if self.folded[0] || self.folded[1] {
            return true;
        }
        if self.round_num == 2 && self.round_complete() {
            return true;
        }
        false
    }

    /// Per-player payoff in chips. Only valid at a terminal state.
    pub fn utility(&self) -> [f64; 2] {
        let (ante0, ante1) = (self.ante[0] as f64, self.ante[1] as f64);
        if self.folded[0] {
            return [-ante0, ante0];
        }
        if self.folded[1] {
            return [ante1, -ante1];
        }
        let pub_card = self.public_card.expect("showdown requires public card");
        let c0 = self.private_cards[0];
        let c1 = self.private_cards[1];
        if c0 == pub_card && c1 != pub_card {
            return [ante1, -ante1];
        }
        if c1 == pub_card && c0 != pub_card {
            return [-ante0, ante0];
        }
        if c0 > c1 {
            return [ante1, -ante1];
        }
        if c1 > c0 {
            return [-ante0, ante0];
        }
        [0.0, 0.0]
    }

    pub fn current_player(&self) -> i8 {
        if self.is_terminal() {
            return -1;
        }
        self.cur_player
    }

    /// Uniform-over-remaining chance outcomes. Removes one occurrence per
    /// already-dealt card to handle the two-suit deck correctly.
    pub fn chance_outcomes(&self) -> Vec<(u8, f64)> {
        let mut dealt: Vec<i8> = self.private_cards.clone();
        if let Some(c) = self.public_card {
            dealt.push(c);
        }
        let mut remaining: Vec<i8> = LEDUC_DECK.to_vec();
        for card in &dealt {
            if let Some(pos) = remaining.iter().position(|c| c == card) {
                remaining.remove(pos);
            }
        }
        let p = 1.0 / remaining.len() as f64;
        remaining.into_iter().map(|c| (c as u8, p)).collect()
    }

    pub fn legal_actions(&self) -> Vec<u8> {
        if self.is_terminal() || self.cur_player == -1 {
            return Vec::new();
        }
        let player = self.cur_player as usize;
        let mut out: Vec<u8> = Vec::with_capacity(3);
        if self.stakes > self.ante[player] {
            out.push(LEDUC_FOLD);
        }
        out.push(LEDUC_CALL);
        if self.num_raises < LEDUC_MAX_RAISES {
            out.push(LEDUC_RAISE);
        }
        out
    }

    pub fn apply(&self, action: u8) -> LeducState {
        if self.cur_player == -1 {
            self.apply_chance(action)
        } else {
            self.apply_player(action)
        }
    }

    pub fn infoset_key(&self, player: u8) -> String {
        let private = self.private_cards[player as usize];
        let r1 = round_string(&self.round1_history);
        match self.public_card {
            None => format!("{private}|{r1}"),
            Some(pub_card) => {
                let r2 = round_string(&self.round2_history);
                format!("{private}|{r1}|{pub_card}|{r2}")
            }
        }
    }

    fn apply_chance(&self, card: u8) -> LeducState {
        let mut next = self.clone();
        if next.private_cards.len() < 2 {
            next.private_cards.push(card as i8);
            next.cur_player = if next.private_cards.len() < 2 { -1 } else { 0 };
        } else {
            next.public_card = Some(card as i8);
            next.round_num = 2;
            next.num_raises = 0;
            next.num_calls = 0;
            next.cur_player = Self::first_non_folded(next.folded);
        }
        next
    }

    fn apply_player(&self, action: u8) -> LeducState {
        let mut next = self.clone();
        let player = next.cur_player as usize;
        match action {
            LEDUC_FOLD => {
                next.folded[player] = true;
            }
            LEDUC_CALL => {
                next.ante[player] = next.stakes;
                next.num_calls += 1;
            }
            LEDUC_RAISE => {
                let raise_amount = if next.round_num == 1 {
                    LEDUC_FIRST_RAISE
                } else {
                    LEDUC_SECOND_RAISE
                };
                next.stakes += raise_amount;
                next.ante[player] = next.stakes;
                next.num_raises += 1;
                next.num_calls = 0;
            }
            _ => panic!("invalid Leduc action: {action}"),
        }
        if next.round_num == 1 {
            next.round1_history.push(action);
        } else {
            next.round2_history.push(action);
        }

        if next.folded[0] || next.folded[1] || next.round_complete() {
            next.cur_player = -1;
        } else {
            next.cur_player = Self::next_player(player as i8, next.folded);
        }
        next
    }

    fn first_non_folded(folded: [bool; 2]) -> i8 {
        for (i, &f) in folded.iter().enumerate() {
            if !f {
                return i as i8;
            }
        }
        -1
    }

    fn next_player(player: i8, folded: [bool; 2]) -> i8 {
        for i in 1..=2 {
            let cand = ((player + i) % 2) as usize;
            if !folded[cand] {
                return cand as i8;
            }
        }
        -1
    }

    fn round_complete(&self) -> bool {
        let remaining = 2u8 - (self.folded[0] as u8 + self.folded[1] as u8);
        if self.num_raises == 0 {
            self.num_calls == remaining
        } else {
            self.num_calls == remaining - 1
        }
    }
}

impl Game for LeducState {
    fn num_players() -> usize {
        2
    }
    fn initial() -> Self {
        LeducState::initial()
    }
    fn is_terminal(&self) -> bool {
        LeducState::is_terminal(self)
    }
    fn utility(&self) -> [f64; 2] {
        LeducState::utility(self)
    }
    fn current_player(&self) -> i8 {
        LeducState::current_player(self)
    }
    fn chance_outcomes(&self) -> Vec<(u8, f64)> {
        LeducState::chance_outcomes(self)
    }
    fn legal_actions(&self) -> Vec<u8> {
        LeducState::legal_actions(self)
    }
    fn apply(&self, action: u8) -> Self {
        LeducState::apply(self, action)
    }
    fn infoset_key(&self, player: u8) -> String {
        LeducState::infoset_key(self, player)
    }
}
