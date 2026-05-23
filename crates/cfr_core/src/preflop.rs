//! HUNL preflop solver (Rust production tier, PR 9).
//!
//! The full HUNL preflop tree blows up to >250M postflop board run-outs per
//! preflop line, intractable without a card abstraction (PR 4) and a postflop
//! solver (PR 5). This module solves a tractable subset — the **preflop
//! subgame** with fixed hole cards — by collapsing postflop board chance
//! nodes to equity-weighted leaves. For all-in preflop lines the equity
//! substitution is **exact**. For limp / flat-call lines it bakes in a
//! check-it-down approximation (canonical depth-limited-solving pattern;
//! Brown & Sandholm 2018).
//!
//! Mirrors `poker_solver/preflop.py` (`PreflopSubgameGame` + `solve_hunl_preflop`).
//! License posture: original implementation; orchestration shape from
//! `noambrown_poker_solver` (MIT) pattern; no AGPL code copied.

use crate::abstraction::AbstractionTables;
use crate::dcfr::InfosetData;
use crate::hunl::{HUNLConfig, HUNLState, Street};
use crate::hunl_eval::Strength;
use std::collections::HashMap;
use std::sync::Arc;
use std::time::Instant;

/// Solve output for PR 9's preflop entry.
pub struct PreflopSolveOutput {
    pub average_strategy: HashMap<String, Vec<f64>>,
    pub exploitability: f64,
    pub game_value: f64,
    pub iterations: u32,
    pub wallclock_seconds: f64,
    pub infoset_count: u32,
}

/// Failure modes (kept narrow — Python validates upstream).
#[derive(Debug)]
pub enum PreflopSolveError {
    /// Reached without fixed `initial_hole_cards`.
    MissingHoleCards,
    /// Not a preflop config (caller should route to postflop solver).
    NotPreflop,
    /// Non-zero rake (rake post-v1 follow-up).
    RakeNonZero,
}

impl std::fmt::Display for PreflopSolveError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            PreflopSolveError::MissingHoleCards => write!(
                f,
                "solve_hunl_preflop requires initial_hole_cards to be set (subgame mode)"
            ),
            PreflopSolveError::NotPreflop => write!(
                f,
                "solve_hunl_preflop: starting_street must be Street::Preflop"
            ),
            PreflopSolveError::RakeNonZero => {
                write!(f, "solve_hunl_preflop: rake support is a post-v1 follow-up")
            }
        }
    }
}

impl std::error::Error for PreflopSolveError {}

/// Equity cache key: `(p0_hole_canonical, p1_hole_canonical, board_canonical)`.
///
/// Each hand-pair is sorted by `card_to_int` (`rank*4 + suit`) so the same
/// pair always hashes the same way regardless of input order.
type EquityCacheKey = (u16, u16, Vec<u8>);

struct EquityCache {
    inner: HashMap<EquityCacheKey, f64>,
}

impl EquityCache {
    fn new() -> Self {
        Self {
            inner: HashMap::new(),
        }
    }

    fn key(hole: &[[u8; 2]; 2], board: &[u8]) -> EquityCacheKey {
        let p0 = pack_hole(hole[0]);
        let p1 = pack_hole(hole[1]);
        let mut b: Vec<u8> = board.to_vec();
        b.sort_unstable();
        (p0, p1, b)
    }
}

/// Pack a 2-card hole into a `u16` with smaller card in low bits (sort canonical).
fn pack_hole(pair: [u8; 2]) -> u16 {
    let (a, b) = if pair[0] <= pair[1] {
        (pair[0], pair[1])
    } else {
        (pair[1], pair[0])
    };
    (a as u16) | ((b as u16) << 8)
}

/// P0's equity (win + 0.5*tie share) given fixed hole + partial board.
///
/// Exhaustive enumeration: walks every possible completion of the remaining
/// board cards. For an empty board this is C(48,5) = 1,712,304 runouts;
/// each runout is a single 5- or 7-card hand evaluation.
///
/// Cache-keyed via `EquityCacheKey`. The DCFR loop walks the same leaf
/// millions of times across iterations, but the equity is constant.
fn compute_p0_equity(hole: &[[u8; 2]; 2], board: &[u8], cache: &mut EquityCache) -> f64 {
    let key = EquityCache::key(hole, board);
    if let Some(&eq) = cache.inner.get(&key) {
        return eq;
    }
    let eq = enumerate_equity(hole, board);
    cache.inner.insert(key, eq);
    eq
}

/// Exhaustive enumeration of P0's equity. Walks every possible board
/// completion via `next_card_combination`-style iteration.
fn enumerate_equity(hole: &[[u8; 2]; 2], partial_board: &[u8]) -> f64 {
    // Build the deck minus used cards.
    let mut used = [false; 64];
    for c in [hole[0][0], hole[0][1], hole[1][0], hole[1][1]] {
        used[c as usize] = true;
    }
    for &c in partial_board {
        used[c as usize] = true;
    }
    let mut deck: Vec<u8> = Vec::with_capacity(52);
    for r in 2u8..=14 {
        for s in 0u8..4 {
            let c = (r << 2) | s;
            if !used[c as usize] {
                deck.push(c);
            }
        }
    }
    let n_to_deal = 5 - partial_board.len();
    if n_to_deal == 0 {
        // Showdown directly.
        let mut seven0 = [0u8; 7];
        let mut seven1 = [0u8; 7];
        seven0[0] = hole[0][0];
        seven0[1] = hole[0][1];
        seven1[0] = hole[1][0];
        seven1[1] = hole[1][1];
        for (i, &c) in partial_board.iter().enumerate() {
            seven0[2 + i] = c;
            seven1[2 + i] = c;
        }
        let s0 = Strength::evaluate_7(&seven0);
        let s1 = Strength::evaluate_7(&seven1);
        return if s0 > s1 {
            1.0
        } else if s1 > s0 {
            0.0
        } else {
            0.5
        };
    }

    // Iterate combinations of size `n_to_deal` from `deck`.
    let mut indices: Vec<usize> = (0..n_to_deal).collect();
    let n = deck.len();
    let mut wins: u64 = 0;
    let mut ties: u64 = 0;
    let mut total: u64 = 0;
    let mut seven0 = [0u8; 7];
    let mut seven1 = [0u8; 7];
    seven0[0] = hole[0][0];
    seven0[1] = hole[0][1];
    seven1[0] = hole[1][0];
    seven1[1] = hole[1][1];
    let n_partial = partial_board.len();
    for (i, &c) in partial_board.iter().enumerate() {
        seven0[2 + i] = c;
        seven1[2 + i] = c;
    }

    loop {
        // Fill seven0/seven1 board slots from `indices` into the deck.
        for (k, &di) in indices.iter().enumerate() {
            let c = deck[di];
            seven0[2 + n_partial + k] = c;
            seven1[2 + n_partial + k] = c;
        }
        let s0 = Strength::evaluate_7(&seven0);
        let s1 = Strength::evaluate_7(&seven1);
        if s0 > s1 {
            wins += 1;
        } else if s0 == s1 {
            ties += 1;
        }
        total += 1;

        // Advance the combination indices (standard combinatorial iter).
        let mut k = n_to_deal;
        loop {
            if k == 0 {
                // exhausted
                let eq = (wins as f64 + 0.5 * ties as f64) / total as f64;
                return eq;
            }
            k -= 1;
            indices[k] += 1;
            if indices[k] < n - (n_to_deal - 1 - k) {
                // valid; reset trailing indices
                for j in (k + 1)..n_to_deal {
                    indices[j] = indices[j - 1] + 1;
                }
                break;
            }
        }
    }
}

/// Wrapper: a frontier-aware terminal check that returns `true` for any
/// "preflop just closed; would deal first board card" state. This is the
/// PR 9 equity-leaf surface — collapses postflop board runouts to a single
/// expected-value leaf.
fn is_preflop_subgame_terminal(state: &HUNLState) -> bool {
    if state.is_terminal() {
        return true;
    }
    if state.cur_player == -1
        && state.hole_cards.is_some()
        && state.board.len() < 5
        && state.pending_board_deals > 0
        && !state.folded[0]
        && !state.folded[1]
        && state.to_call == 0
    {
        return true;
    }
    false
}

/// Wrapper utility: returns base game's utility for folds / showdown, else
/// equity-weighted utility at the preflop-close frontier.
fn preflop_subgame_utility(state: &HUNLState, cache: &mut EquityCache) -> [f64; 2] {
    if state.folded[0] || state.folded[1] || state.street == Street::Showdown {
        return state.utility();
    }
    // Equity-leaf case.
    let bb = state.config.big_blind as f64;
    let c0 = state.contributions[0] as f64;
    let c1 = state.contributions[1] as f64;
    let risk = c0.min(c1);
    let pot = 2.0 * risk;
    let hole = state.hole_cards.expect("equity leaf requires hole cards");
    let eq_p0 = compute_p0_equity(&hole, &state.board, cache);
    let ev_p0_chips = pot * eq_p0 - risk;
    [ev_p0_chips / bb, -ev_p0_chips / bb]
}

/// Custom DCFR solver for preflop subgame (mirrors `HUNLDcfr` but uses the
/// equity-leaf terminal check). Held in this file so PR 6's `hunl_solver.rs`
/// stays frozen.
struct PreflopDcfr {
    alpha: f64,
    beta: f64,
    gamma: f64,
    iteration: u32,
    infosets: HashMap<String, InfosetData>,
    equity_cache: EquityCache,
    /// v1.4 node-locking: see `crate::dcfr::DCFRSolver::locked_strategies`.
    locked_strategies: HashMap<String, Vec<f64>>,
    validated_locked_keys: std::collections::HashSet<String>,
}

impl PreflopDcfr {
    /// v1.3-compat constructor (no locks). Lock-aware variant: `with_locked`.
    #[allow(dead_code)]
    fn new(alpha: f64, beta: f64, gamma: f64) -> Self {
        Self::with_locked(alpha, beta, gamma, HashMap::new())
    }

    fn with_locked(
        alpha: f64,
        beta: f64,
        gamma: f64,
        locked_strategies: HashMap<String, Vec<f64>>,
    ) -> Self {
        Self {
            alpha,
            beta,
            gamma,
            iteration: 0,
            infosets: HashMap::new(),
            equity_cache: EquityCache::new(),
            locked_strategies,
            validated_locked_keys: std::collections::HashSet::new(),
        }
    }

    /// Lock-entry validation mirrors `dcfr.rs`. Lazy: first visit only.
    fn validate_locked_entry(
        key: &str,
        vec: &[f64],
        num_actions: usize,
    ) -> Result<(), String> {
        if vec.len() != num_actions {
            return Err(format!(
                "locked_strategies['{key}'] has length {} but the engine \
                 emits {num_actions} legal actions; usually means \
                 bet_size_fractions changed since the lock was created.",
                vec.len()
            ));
        }
        if vec.iter().any(|&p| p < 0.0) {
            return Err(format!(
                "locked_strategies['{key}'] contains a negative entry \
                 ({vec:?}); probabilities must be non-negative."
            ));
        }
        let total: f64 = vec.iter().sum();
        if (total - 1.0).abs() > 1e-9 {
            return Err(format!(
                "locked_strategies['{key}'] sums to {total}, not 1.0 \
                 (tolerance 1e-9); normalize before passing in."
            ));
        }
        Ok(())
    }

    fn discount(info: &mut InfosetData, t: u32, alpha: f64, beta: f64, gamma: f64) {
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
            for r in &mut info.regret_sum {
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

    fn get_strategy(info: &InfosetData) -> Vec<f64> {
        let mut positive = vec![0.0_f64; info.num_actions];
        let mut total = 0.0;
        for (i, &r) in info.regret_sum.iter().enumerate() {
            if r > 0.0 {
                positive[i] = r;
                total += r;
            }
        }
        if total > 0.0 {
            for p in &mut positive {
                *p /= total;
            }
            positive
        } else {
            vec![1.0 / info.num_actions as f64; info.num_actions]
        }
    }

    fn cfr(
        &mut self,
        state: &HUNLState,
        abstraction: Option<&AbstractionTables>,
        reach: [f64; 3],
        iteration: u32,
    ) -> [f64; 2] {
        // PR 9 — equity-leaf terminal check.
        if is_preflop_subgame_terminal(state) {
            return preflop_subgame_utility(state, &mut self.equity_cache);
        }
        let player = state.current_player();
        if player == -1 {
            let mut value = [0.0_f64; 2];
            for (action, prob) in state.chance_outcomes() {
                let mut new_reach = reach;
                new_reach[2] *= prob;
                let child = self.cfr(&state.apply(action), abstraction, new_reach, iteration);
                value[0] += prob * child[0];
                value[1] += prob * child[1];
            }
            return value;
        }

        let player_idx = player as usize;
        let key = state.infoset_key(player as u8, abstraction);
        let actions = state.legal_actions();
        let num_actions = actions.len();

        // v1.4 node-locking: see `dcfr.rs` for the canonical pattern. The
        // locked vector is read; regret / strategy-sum updates are skipped.
        if let Some(locked_vec) = self.locked_strategies.get(&key) {
            if !self.validated_locked_keys.contains(&key) {
                if let Err(msg) =
                    Self::validate_locked_entry(&key, locked_vec, num_actions)
                {
                    panic!("{msg}");
                }
                self.validated_locked_keys.insert(key.clone());
            }
            let strategy = locked_vec.clone();
            let mut node_value = [0.0_f64; 2];
            for (idx, &action) in actions.iter().enumerate() {
                let mut new_reach = reach;
                new_reach[player_idx] *= strategy[idx];
                let v = self.cfr(&state.apply(action), abstraction, new_reach, iteration);
                node_value[0] += strategy[idx] * v[0];
                node_value[1] += strategy[idx] * v[1];
            }
            return node_value;
        }

        let info = self
            .infosets
            .entry(key.clone())
            .or_insert_with(|| InfosetData {
                regret_sum: vec![0.0; num_actions],
                strategy_sum: vec![0.0; num_actions],
                num_actions,
                last_discount_iter: 0,
            });
        Self::discount(info, iteration, self.alpha, self.beta, self.gamma);
        let strategy = Self::get_strategy(info);

        let mut node_value = [0.0_f64; 2];
        let mut action_values: Vec<[f64; 2]> = vec![[0.0_f64; 2]; num_actions];
        for (idx, &action) in actions.iter().enumerate() {
            let mut new_reach = reach;
            new_reach[player_idx] *= strategy[idx];
            let v = self.cfr(&state.apply(action), abstraction, new_reach, iteration);
            action_values[idx] = v;
            node_value[0] += strategy[idx] * v[0];
            node_value[1] += strategy[idx] * v[1];
        }

        let mut opponent_reach = 1.0;
        for (i, &r) in reach.iter().enumerate() {
            if i != player_idx {
                opponent_reach *= r;
            }
        }
        let own_reach = reach[player_idx];

        let info = self
            .infosets
            .get_mut(&key)
            .expect("infoset must exist after insert");
        for idx in 0..num_actions {
            let regret = opponent_reach * (action_values[idx][player_idx] - node_value[player_idx]);
            info.regret_sum[idx] += regret;
            info.strategy_sum[idx] += own_reach * strategy[idx];
        }
        node_value
    }

    fn average_strategy(&self) -> HashMap<String, Vec<f64>> {
        let mut out = HashMap::new();
        for (key, info) in &self.infosets {
            let total: f64 = info.strategy_sum.iter().sum();
            let probs = if total > 0.0 {
                info.strategy_sum.iter().map(|s| s / total).collect()
            } else {
                vec![1.0 / info.num_actions as f64; info.num_actions]
            };
            out.insert(key.clone(), probs);
        }
        // v1.4 node-locking: bit-identical passthrough of locked vectors.
        for (key, vec) in &self.locked_strategies {
            out.insert(key.clone(), vec.clone());
        }
        out
    }
}

/// Solve a HUNL preflop subgame via DCFR with equity-leaf postflop collapse.
///
/// Validates upstream (preflop start; hole cards set; rake == 0). Per
/// `solve_hunl_postflop`'s contract, `exploitability` and `game_value`
/// stay 0.0 in the output — Python recomputes from the strategy (D5).
#[allow(clippy::too_many_arguments)]
pub fn solve_hunl_preflop(
    config: &HUNLConfig,
    iterations: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
    _target_exploitability: Option<f64>,
    _seed: Option<u64>,
    locked_strategies: Option<HashMap<String, Vec<f64>>>,
) -> Result<PreflopSolveOutput, PreflopSolveError> {
    if config.starting_street != Street::Preflop {
        return Err(PreflopSolveError::NotPreflop);
    }
    if config.initial_hole_cards.is_none() {
        return Err(PreflopSolveError::MissingHoleCards);
    }
    if config.rake_rate != 0.0 || config.rake_cap != 0 {
        return Err(PreflopSolveError::RakeNonZero);
    }

    let config_arc = Arc::new(config.clone());
    let started = Instant::now();
    // v1.4 node-locking: route lock map into the solver.
    let locked = locked_strategies.unwrap_or_default();
    let mut solver = PreflopDcfr::with_locked(alpha, beta, gamma, locked);

    let initial = HUNLState::initial(Arc::clone(&config_arc));
    let abstraction: Option<&AbstractionTables> = None;
    for _ in 0..iterations {
        solver.iteration += 1;
        let reach = [1.0_f64, 1.0, 1.0];
        let _ = solver.cfr(&initial, abstraction, reach, solver.iteration);
    }

    let average_strategy = solver.average_strategy();
    let wallclock_seconds = started.elapsed().as_secs_f64();
    let infoset_count = solver.infosets.len() as u32;

    Ok(PreflopSolveOutput {
        average_strategy,
        exploitability: 0.0,
        game_value: 0.0,
        iterations,
        wallclock_seconds,
        infoset_count,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Pack a card from rank + suit using the `card_to_int` formula
    /// (rank << 2 | suit) used throughout the crate.
    fn card(rank: u8, suit: u8) -> u8 {
        (rank << 2) | suit
    }

    #[test]
    fn equity_aa_vs_kk_matches_known_value() {
        let hole = [
            [card(14, 0), card(14, 1)], // AA (As, Ah - suits 0,1)
            [card(13, 2), card(13, 3)], // KK (Kd, Kc)
        ];
        let eq = enumerate_equity(&hole, &[]);
        // AA vs KK preflop ≈ 0.813 (Brunson 2-player Hold'em odds tables).
        assert!(
            (0.805..=0.820).contains(&eq),
            "AA vs KK equity {eq} outside [0.805, 0.820]"
        );
    }

    #[test]
    fn equity_aa_vs_aa_is_half() {
        // Different suits to avoid duplicate cards.
        let hole = [
            [card(14, 0), card(14, 1)], // AsAh
            [card(14, 2), card(14, 3)], // AdAc
        ];
        let eq = enumerate_equity(&hole, &[]);
        // Identical strength: pure 0.5 (ties always).
        assert!((eq - 0.5).abs() < 1e-9, "AA vs AA equity {eq} != 0.5");
    }

    #[test]
    fn preflop_solver_accepts_subgame_config() {
        let cfg = HUNLConfig {
            initial_hole_cards: Some([[card(14, 0), card(14, 1)], [card(13, 2), card(13, 3)]]),
            ..Default::default()
        };
        let res = solve_hunl_preflop(&cfg, 10, 1.5, 0.0, 2.0, None, None, None);
        assert!(res.is_ok(), "preflop solve should succeed: {:?}", res.err());
        let out = res.unwrap();
        assert_eq!(out.iterations, 10);
        assert!(out.infoset_count > 0);
    }

    #[test]
    fn preflop_solver_rejects_missing_hole_cards() {
        let cfg = HUNLConfig::default(); // no hole cards
        let res = solve_hunl_preflop(&cfg, 10, 1.5, 0.0, 2.0, None, None, None);
        assert!(matches!(res, Err(PreflopSolveError::MissingHoleCards)));
    }
}
