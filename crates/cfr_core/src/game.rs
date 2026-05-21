//! Generic `Game` trait — the contract every CFR-consumable game implements.
//!
//! Architectural decision (PR 2 Step 2 — Leduc port): we chose **Option A**
//! (Game-generic DCFR) over per-game duplication. The original `dcfr.rs` /
//! `solver.rs` carried a hard dependency on `KuhnState`, but their call graph
//! mirrors Python's protocol-driven `_cfr` loop exactly. Abstracting over a
//! small trait was ~50 LOC of churn — well under the 150-LOC bar — and keeps
//! tier parity with `poker_solver/games.py`'s `Game` protocol.
//!
//! Trait shape mirrors Python's `Game` protocol in `poker_solver/games.py`:
//!   - `initial()` builds the root state
//!   - `is_terminal`, `utility`, `current_player`, `legal_actions`, `apply`,
//!     `chance_outcomes`, `infoset_key` walk the tree
//!   - `num_players()` is constant per game
//!
//! Each concrete game (`KuhnState`, `LeducState`) implements `Game` for its own
//! state type; the DCFR solver and exploitability/BR machinery in `dcfr.rs` and
//! `solver.rs` are generic over `G: Game`.

/// Trait every CFR-consumable game implements. `Self` is the *state* type;
/// methods are self-methods on the state (matches Kuhn/Leduc's struct-method
/// layout). Game-level constants (e.g. `num_players`) are associated.
pub trait Game: Clone {
    /// Number of players (excludes chance). Not consumed by the current
    /// 2-player solver, but part of the trait contract — kept for symmetry
    /// with Python's `Game.num_players` and future-proofing for >2p variants.
    #[allow(dead_code)]
    fn num_players() -> usize;

    /// Fresh root state.
    fn initial() -> Self;

    /// True if this state is a leaf.
    fn is_terminal(&self) -> bool;

    /// Terminal payoffs by player (length `num_players()`). Only valid when
    /// `is_terminal()`.
    fn utility(&self) -> [f64; 2];

    /// Player to act, or -1 for chance.
    fn current_player(&self) -> i8;

    /// (action, probability) pairs for chance nodes; empty otherwise.
    fn chance_outcomes(&self) -> Vec<(u8, f64)>;

    /// Legal actions in this state.
    fn legal_actions(&self) -> Vec<u8>;

    /// Apply an action and return the successor state.
    fn apply(&self, action: u8) -> Self;

    /// Infoset key for `player` — must uniquely identify the player's
    /// information state (their private knowledge + visible history).
    fn infoset_key(&self, player: u8) -> String;
}
