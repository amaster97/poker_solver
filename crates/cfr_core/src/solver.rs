//! Solver orchestration: run DCFR, compute exploitability + game value.
//!
//! This is the Rust counterpart of `poker_solver/solver.py`. Best-response
//! traversal walks the (small) game tree for both Kuhn and Leduc. We hold the
//! same general structure as the Python tier and crucially **iterate the BR
//! computation to a fixed point**: for multi-round games (Leduc) the round-2
//! action choices feed back into round-1 BR action values, so a single pass is
//! incorrect. The Python tier had to be fixed for the same reason; this port
//! does it from the start.
//!
//! Generic over `G: Game` — the same code path serves Kuhn (`solve_kuhn`),
//! Leduc (`solve_leduc`), and any future game implementing the trait.

use std::collections::HashMap;

use crate::dcfr::DCFRSolver;
use crate::game::Game;
use crate::kuhn::KuhnState;
use crate::leduc::LeducState;

/// Bundled outputs from a solve.
pub struct SolveOutput {
    pub average_strategy: HashMap<String, Vec<f64>>,
    pub exploitability: f64,
    pub game_value: f64,
    pub iterations: u32,
}

pub fn solve_kuhn(
    iterations: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
    locked_strategies: Option<HashMap<String, Vec<f64>>>,
) -> SolveOutput {
    solve_generic::<KuhnState>(iterations, alpha, beta, gamma, locked_strategies)
}

pub fn solve_leduc(
    iterations: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
    locked_strategies: Option<HashMap<String, Vec<f64>>>,
) -> SolveOutput {
    solve_generic::<LeducState>(iterations, alpha, beta, gamma, locked_strategies)
}

fn solve_generic<G: Game>(
    iterations: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
    locked_strategies: Option<HashMap<String, Vec<f64>>>,
) -> SolveOutput {
    // v1.4 node-locking: route lock map into the solver. Empty/`None` is
    // bit-identical to v1.3.
    let locked = locked_strategies.unwrap_or_default();
    let mut solver = DCFRSolver::<G>::with_locked(alpha, beta, gamma, locked);
    let average_strategy = solver.solve(iterations);
    let game_value = expected_value::<G>(&G::initial(), &average_strategy)[0];
    let expl = exploitability::<G>(&average_strategy);
    SolveOutput {
        average_strategy,
        exploitability: expl,
        game_value,
        iterations,
    }
}

/// Player 0's expected value under `strategy` (both players follow it).
fn expected_value<G: Game>(state: &G, strategy: &HashMap<String, Vec<f64>>) -> [f64; 2] {
    if state.is_terminal() {
        return state.utility();
    }
    let player = state.current_player();
    if player == -1 {
        let mut value = [0.0_f64; 2];
        for (action, prob) in state.chance_outcomes() {
            let child = expected_value::<G>(&state.apply(action), strategy);
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
        let child = expected_value::<G>(&state.apply(action), strategy);
        value[0] += probs[idx] * child[0];
        value[1] += probs[idx] * child[1];
    }
    value
}

/// Mean over players of (best-response value − on-strategy value).
/// Equals NashConv / num_players for zero-sum 2p games (matches OpenSpiel +
/// the DCFR paper).
pub fn exploitability<G: Game>(strategy: &HashMap<String, Vec<f64>>) -> f64 {
    let on_policy = expected_value::<G>(&G::initial(), strategy);
    let mut total = 0.0;
    for (player, &on) in on_policy.iter().enumerate() {
        let br_value = best_response_value::<G>(strategy, player);
        total += br_value - on;
    }
    total / 2.0
}

/// Compute `br_player`'s value when best-responding to opponents on `strategy`.
///
/// For multi-round games, infosets are visited in DFS pre-order; a single BR
/// pass would use stale (default) choices at deeper infosets. We iterate to a
/// fixed point — the `best_action` map stabilizes after at most one pass per
/// dependency layer, which on Leduc converges in <10 passes in practice.
fn best_response_value<G: Game>(strategy: &HashMap<String, Vec<f64>>, br_player: usize) -> f64 {
    // First, gather all (state, counterfactual_reach) entries per `br_player`
    // infoset. Strategy doesn't change between passes, so the groups don't either.
    let mut groups: HashMap<String, Vec<(G, f64)>> = HashMap::new();
    collect_infosets::<G>(&G::initial(), 1.0, br_player, strategy, &mut groups);

    let mut best_action: HashMap<String, usize> = HashMap::new();
    loop {
        let previous = best_action.clone();
        for (key, entries) in &groups {
            // First entry gives us the action count for this infoset; all
            // entries in a group share legal-action set (same player infoset).
            let num_actions = entries[0].0.legal_actions().len();
            let mut action_values: Vec<f64> = vec![0.0; num_actions];
            for (state, cf_reach) in entries {
                let actions = state.legal_actions();
                for (idx, &action) in actions.iter().enumerate() {
                    let child_v = br_state_value::<G>(
                        &state.apply(action),
                        br_player,
                        &best_action,
                        strategy,
                    );
                    action_values[idx] += cf_reach * child_v;
                }
            }
            let mut best = 0usize;
            let mut best_v = action_values[0];
            for (idx, &v) in action_values.iter().enumerate().skip(1) {
                if v > best_v {
                    best_v = v;
                    best = idx;
                }
            }
            best_action.insert(key.clone(), best);
        }
        if best_action == previous {
            break;
        }
    }
    br_state_value::<G>(&G::initial(), br_player, &best_action, strategy)
}

fn collect_infosets<G: Game>(
    state: &G,
    cf_reach: f64,
    br_player: usize,
    strategy: &HashMap<String, Vec<f64>>,
    groups: &mut HashMap<String, Vec<(G, f64)>>,
) {
    if state.is_terminal() {
        return;
    }
    let player = state.current_player();
    if player == -1 {
        for (action, prob) in state.chance_outcomes() {
            collect_infosets::<G>(
                &state.apply(action),
                cf_reach * prob,
                br_player,
                strategy,
                groups,
            );
        }
        return;
    }
    let actions = state.legal_actions();
    if player as usize == br_player {
        let key = state.infoset_key(player as u8);
        groups
            .entry(key)
            .or_default()
            .push((state.clone(), cf_reach));
        for &action in &actions {
            collect_infosets::<G>(&state.apply(action), cf_reach, br_player, strategy, groups);
        }
    } else {
        let key = state.infoset_key(player as u8);
        let default = vec![1.0 / actions.len() as f64; actions.len()];
        let probs = strategy.get(&key).unwrap_or(&default);
        for (idx, &action) in actions.iter().enumerate() {
            collect_infosets::<G>(
                &state.apply(action),
                cf_reach * probs[idx],
                br_player,
                strategy,
                groups,
            );
        }
    }
}

fn br_state_value<G: Game>(
    state: &G,
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
            value +=
                prob * br_state_value::<G>(&state.apply(action), br_player, best_action, strategy);
        }
        return value;
    }
    let actions = state.legal_actions();
    if player as usize == br_player {
        let key = state.infoset_key(player as u8);
        let idx = *best_action.get(&key).unwrap_or(&0);
        return br_state_value::<G>(&state.apply(actions[idx]), br_player, best_action, strategy);
    }
    let key = state.infoset_key(player as u8);
    let default = vec![1.0 / actions.len() as f64; actions.len()];
    let probs = strategy.get(&key).unwrap_or(&default);
    let mut value = 0.0;
    for (idx, &action) in actions.iter().enumerate() {
        value += probs[idx]
            * br_state_value::<G>(&state.apply(action), br_player, best_action, strategy);
    }
    value
}
