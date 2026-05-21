//! Solver orchestration: run DCFR, compute exploitability + game value.
//!
//! This is the Rust counterpart of `poker_solver/solver.py`. Best-response
//! traversal walks Kuhn's tree (≤36 leaf paths) — trivial enough that we don't
//! bother with caching beyond infoset-keyed best-action lookup.

use std::collections::HashMap;

use crate::dcfr::DCFRSolver;
use crate::kuhn::KuhnState;

/// Bundled outputs from a Kuhn solve.
pub struct SolveOutput {
    pub average_strategy: HashMap<String, Vec<f64>>,
    pub exploitability: f64,
    pub game_value: f64,
    pub iterations: u32,
}

pub fn solve_kuhn(iterations: u32, alpha: f64, beta: f64, gamma: f64) -> SolveOutput {
    let mut solver = DCFRSolver::new(alpha, beta, gamma);
    let average_strategy = solver.solve(iterations);
    let game_value = expected_value(&KuhnState::initial(), &average_strategy)[0];
    let expl = exploitability(&average_strategy);
    SolveOutput { average_strategy, exploitability: expl, game_value, iterations }
}

/// Player 0's expected value under `strategy` (both players follow it).
fn expected_value(state: &KuhnState, strategy: &HashMap<String, Vec<f64>>) -> [f64; 2] {
    if state.is_terminal() {
        return state.utility();
    }
    let player = state.current_player();
    if player == -1 {
        let mut value = [0.0_f64; 2];
        for (action, prob) in state.chance_outcomes() {
            let child = expected_value(&state.apply(action), strategy);
            value[0] += prob * child[0];
            value[1] += prob * child[1];
        }
        return value;
    }
    let actions = state.legal_actions();
    let key = state.infoset_key(player as u8);
    let default = vec![1.0 / actions.len() as f64; actions.len()];
    let probs = strategy.get(&key).unwrap_or(&default);
    let mut value = [0.0_f64; 2];
    for (idx, &action) in actions.iter().enumerate() {
        let child = expected_value(&state.apply(action), strategy);
        value[0] += probs[idx] * child[0];
        value[1] += probs[idx] * child[1];
    }
    value
}

/// Mean over players of (best-response value − on-strategy value).
/// Equals NashConv / num_players for zero-sum 2p games (matches OpenSpiel +
/// the DCFR paper). On Kuhn, ε-Nash gives this close to 0.
pub fn exploitability(strategy: &HashMap<String, Vec<f64>>) -> f64 {
    let on_policy = expected_value(&KuhnState::initial(), strategy);
    let mut total = 0.0;
    for (player, &on) in on_policy.iter().enumerate() {
        let br_value = best_response_value(strategy, player);
        total += br_value - on;
    }
    total / 2.0
}

/// Compute `br_player`'s value when best-responding to opponents on `strategy`.
fn best_response_value(strategy: &HashMap<String, Vec<f64>>, br_player: usize) -> f64 {
    // First pass: collect (state, counterfactual_reach) entries per infoset
    // belonging to `br_player`.
    let mut groups: HashMap<String, Vec<(KuhnState, f64)>> = HashMap::new();
    collect_infosets(&KuhnState::initial(), 1.0, br_player, strategy, &mut groups);

    // Determine best action per infoset by maximizing expected utility.
    let mut best_action: HashMap<String, usize> = HashMap::new();
    for (key, entries) in &groups {
        // Two actions in Kuhn at every player node; safe to hardcode 2 here.
        let mut action_values = [0.0_f64; 2];
        for (state, cf_reach) in entries {
            let actions = state.legal_actions();
            for (idx, &action) in actions.iter().enumerate() {
                let child_v = br_state_value(
                    &state.apply(action),
                    br_player,
                    &best_action,
                    strategy,
                );
                action_values[idx] += cf_reach * child_v;
            }
        }
        let best = if action_values[0] >= action_values[1] { 0 } else { 1 };
        best_action.insert(key.clone(), best);
    }
    br_state_value(&KuhnState::initial(), br_player, &best_action, strategy)
}

fn collect_infosets(
    state: &KuhnState,
    cf_reach: f64,
    br_player: usize,
    strategy: &HashMap<String, Vec<f64>>,
    groups: &mut HashMap<String, Vec<(KuhnState, f64)>>,
) {
    if state.is_terminal() {
        return;
    }
    let player = state.current_player();
    if player == -1 {
        for (action, prob) in state.chance_outcomes() {
            collect_infosets(&state.apply(action), cf_reach * prob, br_player, strategy, groups);
        }
        return;
    }
    let actions = state.legal_actions();
    if player as usize == br_player {
        let key = state.infoset_key(player as u8);
        groups.entry(key).or_default().push((state.clone(), cf_reach));
        for &action in &actions {
            collect_infosets(&state.apply(action), cf_reach, br_player, strategy, groups);
        }
    } else {
        let key = state.infoset_key(player as u8);
        let default = vec![1.0 / actions.len() as f64; actions.len()];
        let probs = strategy.get(&key).unwrap_or(&default);
        for (idx, &action) in actions.iter().enumerate() {
            collect_infosets(
                &state.apply(action),
                cf_reach * probs[idx],
                br_player,
                strategy,
                groups,
            );
        }
    }
}

fn br_state_value(
    state: &KuhnState,
    br_player: usize,
    best_action: &HashMap<String, usize>,
    strategy: &HashMap<String, Vec<f64>>,
) -> f64 {
    if state.is_terminal() {
        return state.utility()[br_player];
    }
    let player = state.current_player();
    if player == -1 {
        let mut value = 0.0;
        for (action, prob) in state.chance_outcomes() {
            value += prob * br_state_value(&state.apply(action), br_player, best_action, strategy);
        }
        return value;
    }
    let actions = state.legal_actions();
    if player as usize == br_player {
        let key = state.infoset_key(player as u8);
        let idx = *best_action.get(&key).unwrap_or(&0);
        return br_state_value(&state.apply(actions[idx]), br_player, best_action, strategy);
    }
    let key = state.infoset_key(player as u8);
    let default = vec![1.0 / actions.len() as f64; actions.len()];
    let probs = strategy.get(&key).unwrap_or(&default);
    let mut value = 0.0;
    for (idx, &action) in actions.iter().enumerate() {
        value += probs[idx] * br_state_value(&state.apply(action), br_player, best_action, strategy);
    }
    value
}
