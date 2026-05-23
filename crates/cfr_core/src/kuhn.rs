//! Kuhn poker game definition (Rust production tier).
//!
//! Kuhn poker is a 3-card deck (J=11, Q=12, K=13), two players, one ante each
//! (pot starts at 2), one betting round (check/bet/call/fold). This is the
//! canonical smallest imperfect-information game used to validate CFR-family
//! solvers — closed-form Nash equilibrium is known.
//!
//! Mirrors the Python reference in `poker_solver/games.py`. The differential
//! test (`tests/test_dcfr_diff.py`) requires structural parity so per-action
//! probabilities agree within 1e-4.

use crate::game::Game;

pub const PASS: u8 = 0;
pub const BET: u8 = 1;

/// Kuhn poker deck — three cards, values 11/12/13 (J/Q/K).
const KUHN_DECK: [i8; 3] = [11, 12, 13];

/// Game state. `chance_phase` tracks the two chance moves (deal P1, deal P2)
/// before the playing phase. Player 0 acts first at depth 0.
#[derive(Clone, Debug)]
pub struct KuhnState {
    /// Dealt cards by player index. -1 means not yet dealt.
    pub cards: [i8; 2],
    /// Action history (PASS / BET) once both cards are dealt.
    pub history: Vec<u8>,
    /// 0 = need to deal to P1, 1 = need to deal to P2, 2 = playing.
    pub chance_phase: u8,
}

impl KuhnState {
    pub fn initial() -> Self {
        Self {
            cards: [-1, -1],
            history: Vec::new(),
            chance_phase: 0,
        }
    }

    /// Render the history as a "p"/"b" string for infoset keys.
    fn history_string(&self) -> String {
        let mut s = String::with_capacity(self.history.len());
        for &a in &self.history {
            s.push(if a == BET { 'b' } else { 'p' });
        }
        s
    }

    pub fn is_terminal(&self) -> bool {
        if self.chance_phase < 2 {
            return false;
        }
        let h = self.history_string();
        matches!(h.as_str(), "pp" | "bp" | "bb" | "pbp" | "pbb")
    }

    /// Player 0's payoff (player 1 gets the negation; zero-sum).
    pub fn utility(&self) -> [f64; 2] {
        let h = self.history_string();
        let (c0, c1) = (self.cards[0], self.cards[1]);
        let p1_wins_showdown = c0 > c1;
        let payoff = match h.as_str() {
            "pp" => {
                if p1_wins_showdown {
                    1.0
                } else {
                    -1.0
                }
            }
            "bp" => 1.0,
            "bb" => {
                if p1_wins_showdown {
                    2.0
                } else {
                    -2.0
                }
            }
            "pbp" => -1.0,
            "pbb" => {
                if p1_wins_showdown {
                    2.0
                } else {
                    -2.0
                }
            }
            _ => panic!("utility called on non-terminal history: {h}"),
        };
        [payoff, -payoff]
    }

    /// Returns -1 for chance, 0 or 1 for player to act.
    pub fn current_player(&self) -> i8 {
        if self.chance_phase < 2 {
            return -1;
        }
        (self.history.len() % 2) as i8
    }

    /// Uniform-over-remaining chance distribution (cards not yet dealt).
    pub fn chance_outcomes(&self) -> Vec<(u8, f64)> {
        let mut dealt = [false; 3];
        for &c in &self.cards {
            if c >= 11 {
                dealt[(c - 11) as usize] = true;
            }
        }
        let remaining: Vec<i8> = KUHN_DECK
            .iter()
            .copied()
            .enumerate()
            .filter_map(|(i, c)| (!dealt[i]).then_some(c))
            .collect();
        let p = 1.0 / remaining.len() as f64;
        remaining.into_iter().map(|c| (c as u8, p)).collect()
    }

    pub fn legal_actions(&self) -> Vec<u8> {
        if self.is_terminal() {
            return Vec::new();
        }
        vec![PASS, BET]
    }

    /// Apply an action (chance card during dealing phases, PASS/BET during play).
    pub fn apply(&self, action: u8) -> KuhnState {
        let mut next = self.clone();
        if self.chance_phase == 0 {
            next.cards[0] = action as i8;
            next.chance_phase = 1;
        } else if self.chance_phase == 1 {
            next.cards[1] = action as i8;
            next.chance_phase = 2;
        } else {
            next.history.push(action);
        }
        next
    }

    /// Infoset key for `player`: their card + the visible action history.
    pub fn infoset_key(&self, player: u8) -> String {
        format!("{}|{}", self.cards[player as usize], self.history_string())
    }
}

impl Game for KuhnState {
    fn num_players() -> usize {
        2
    }
    fn initial() -> Self {
        KuhnState::initial()
    }
    fn is_terminal(&self) -> bool {
        KuhnState::is_terminal(self)
    }
    fn utility(&self) -> [f64; 2] {
        KuhnState::utility(self)
    }
    fn current_player(&self) -> i8 {
        KuhnState::current_player(self)
    }
    fn chance_outcomes(&self) -> Vec<(u8, f64)> {
        KuhnState::chance_outcomes(self)
    }
    fn legal_actions(&self) -> Vec<u8> {
        KuhnState::legal_actions(self)
    }
    fn apply(&self, action: u8) -> Self {
        KuhnState::apply(self, action)
    }
    fn infoset_key(&self, player: u8) -> String {
        KuhnState::infoset_key(self, player)
    }
}
