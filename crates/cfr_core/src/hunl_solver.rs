//! HUNL postflop solve entry (Rust production tier).
//!
//! Counterpart to `poker_solver/hunl_solver.py::solve_hunl_postflop`
//! (project-internal, MIT). Wires Agent A's `HUNLState` + `HUNLTree` to a
//! DCFR loop that uses Agent A's `HUNLState::infoset_key(player,
//! abstraction)` directly — the bucketed-mode signature is not reachable
//! via the parameterless `Game::infoset_key(player)` trait method, so the
//! solve loop here calls `HUNLState::infoset_key` explicitly. The regret /
//! strategy bookkeeping shape mirrors `crate::dcfr::DCFRSolver`
//! (project-internal port of `references/code/noambrown_poker_solver/cpp/
//! src/trainer.cpp` (MIT)), but the outer recursion is inlined so we can
//! thread the abstraction through every infoset-key call.
//!
//! NEVER copy from `references/code/postflop-solver` (AGPL) or
//! `references/code/TexasSolver` (AGPL).
//!
//! Per PR 6 §6 dispatch ordering and D5 (Python recomputes exploitability +
//! game_value), this entrypoint returns `0.0` for both fields. The Python
//! wrapper in `_solve_rust` recomputes them via the reference-tier
//! `exploitability()` / `_game_value()` functions to remove cross-tier
//! floating-point drift.

use std::collections::HashMap;
use std::sync::Arc;
use std::time::Instant;

use crate::abstraction::AbstractionTables;
use crate::dcfr::InfosetData;
use crate::hunl::{HUNLConfig, HUNLState, Street};
use crate::hunl_tree::HUNLTree;
use crate::pcs::{effective_beta, sample_uniform_outcome, PcsRng, SamplingStrategy};
use crate::simd;

/// Output of `solve_hunl_postflop`. Mirrors PR 5's `HUNLSolveResult` minus
/// the `MemoryReport` (Rust-side memory profiling is deferred to PR 8).
pub struct HUNLSolveOutput {
    pub average_strategy: HashMap<String, Vec<f64>>,
    /// Always 0.0 in PR 6 — Python recomputes (D5).
    pub exploitability: f64,
    /// Always 0.0 in PR 6 — Python recomputes (D5).
    pub game_value: f64,
    pub iterations: u32,
    pub wallclock_seconds: f64,
    pub infoset_count: u32,
}

/// Solve-side error variants. Loud failures only — no silent fallbacks.
#[derive(Debug)]
pub enum HUNLSolveError {
    /// Preflop configs route through PR 9's preflop solver. PR 6 rejects them
    /// up front to match PR 5's behavior.
    PreflopNotSupported,
    /// `initial_board.len()` did not match `starting_street`'s required board
    /// length (flop = 3, turn = 4, river = 5).
    BoardLengthMismatch {
        expected: usize,
        found: usize,
        street: Street,
    },
    /// PR 6 inherits PR 5's "no rake" guarantee. Agent A's `HUNLConfig`
    /// carries `rake_rate` / `rake_cap` fields; this entrypoint rejects
    /// non-zero values up front.
    RakeNonZero,
    /// Errors propagated from `abstraction::load_abstraction` when caller
    /// passes a malformed table directly. (The PyO3 wrapper loads via
    /// `load_abstraction` before reaching here; this variant is reserved for
    /// future direct-table sanity checks.)
    #[allow(dead_code)]
    AbstractionLoad(crate::abstraction::AbstractionError),
    /// Generic catch-all for spec violations not covered above.
    InvalidConfig(String),
}

impl std::fmt::Display for HUNLSolveError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            HUNLSolveError::PreflopNotSupported => write!(
                f,
                "HUNL preflop port lands in PR 9; use starting_street >= Flop"
            ),
            HUNLSolveError::BoardLengthMismatch {
                expected,
                found,
                street,
            } => write!(
                f,
                "initial_board has {found} cards but starting_street={street:?} \
                 requires {expected}"
            ),
            HUNLSolveError::RakeNonZero => {
                write!(
                    f,
                    "PR 6 does not support rake; set rake_rate=0.0 + rake_cap=0"
                )
            }
            HUNLSolveError::AbstractionLoad(e) => write!(f, "abstraction load error: {e}"),
            HUNLSolveError::InvalidConfig(msg) => write!(f, "invalid config: {msg}"),
        }
    }
}

impl std::error::Error for HUNLSolveError {}

impl From<crate::abstraction::AbstractionError> for HUNLSolveError {
    fn from(e: crate::abstraction::AbstractionError) -> Self {
        HUNLSolveError::AbstractionLoad(e)
    }
}

/// Solver state — the abstraction-aware analog of `crate::dcfr::DCFRSolver`.
struct HUNLDcfr {
    alpha: f64,
    beta: f64,
    gamma: f64,
    iteration: u32,
    infosets: HashMap<String, InfosetData>,
    /// v1.4 node-locking: map of infoset key → fixed probability vector.
    /// Locked infosets bypass regret-matching; the unlocked side updates
    /// against them as if they were part of the game's structure.
    locked_strategies: HashMap<String, Vec<f64>>,
    /// Cache of locked keys validated on first visit (length + non-
    /// negative + sum-to-one).
    validated_locked_keys: std::collections::HashSet<String>,
}

impl HUNLDcfr {
    /// v1.3-compat constructor (no locks). Kept for symmetry with
    /// `DCFRSolver::new`; the lock-aware variant is `with_locked`.
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
            locked_strategies,
            validated_locked_keys: std::collections::HashSet::new(),
        }
    }

    /// Validate a locked-strategy entry on first visit (mirrors
    /// `dcfr.rs::DCFRSolver::validate_locked_entry`).
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

    /// Lazy DCFR discount catch-up (mirrors `dcfr.rs`'s `discount_info`
    /// exactly — same math, same lazy semantics, same parity contract with
    /// `poker_solver/dcfr.py::_discount`).
    ///
    /// PR 8: discount inner kernels now route through `simd::discount_regrets`
    /// + `simd::discount_strategy_sum` for NEON vectorization on aarch64.
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
            simd::discount_regrets(&mut info.regret_sum, pos_scale, neg_scale);
            simd::discount_strategy_sum(&mut info.strategy_sum, strat_scale);
        }
        info.last_discount_iter = t;
    }

    /// Regret-matching strategy: positive regrets normalized, uniform if zero.
    ///
    /// PR 8: SIMD-accelerated via `simd::positive_regrets_and_total` +
    /// `simd::normalize`. Bit-identical to scalar on per-lane outputs.
    fn get_strategy(info: &InfosetData) -> Vec<f64> {
        let mut positive = vec![0.0_f64; info.num_actions];
        let total = simd::positive_regrets_and_total(&info.regret_sum, &mut positive);
        simd::normalize(&mut positive, total);
        positive
    }

    /// Recursive CFR traversal — same shape as `DCFRSolver::cfr` but uses
    /// `HUNLState::infoset_key(player, abstraction)` so bucketed mode works.
    ///
    /// PR 8: optional `sampling` + `rng` arguments. When
    /// `sampling = SamplingStrategy::PublicChance`, chance nodes draw ONE
    /// outcome per visit and the recursive call's value is reweighted by
    /// `K` (the importance weight); this is the standard sampled-CFR
    /// estimator (Lanctot 2009). `Full` keeps PR 6 behavior bit-for-bit.
    ///
    /// Inner per-iteration arithmetic (discount, regret-matching, regret/
    /// strategy update) is routed through `simd::` so NEON kicks in on
    /// aarch64.
    #[allow(clippy::too_many_arguments)]
    fn cfr(
        &mut self,
        state: &HUNLState,
        abstraction: Option<&AbstractionTables>,
        reach: [f64; 3],
        iteration: u32,
        sampling: SamplingStrategy,
        rng: &mut PcsRng,
    ) -> [f64; 2] {
        if state.is_terminal() {
            return state.utility();
        }
        let player = state.current_player();
        if player == -1 {
            // Chance node. Two paths:
            //   - Full: enumerate every outcome, weight by probability.
            //   - PublicChance: sample ONE outcome uniformly and reweight by
            //     K (importance weight). Per Lanctot 2009 / Tammelin 2014.
            match sampling {
                SamplingStrategy::Full => {
                    let mut value = [0.0_f64; 2];
                    for (action, prob) in state.chance_outcomes() {
                        let mut new_reach = reach;
                        new_reach[2] *= prob;
                        let child = self.cfr(
                            &state.apply(action),
                            abstraction,
                            new_reach,
                            iteration,
                            sampling,
                            rng,
                        );
                        value[0] += prob * child[0];
                        value[1] += prob * child[1];
                    }
                    return value;
                }
                SamplingStrategy::PublicChance => {
                    let outcomes = state.chance_outcomes();
                    let k = outcomes.len();
                    if k == 0 {
                        return [0.0, 0.0];
                    }
                    let (idx, weight) = sample_uniform_outcome(rng, k);
                    let (action, prob) = outcomes[idx];
                    let mut new_reach = reach;
                    // The sampled-outcome reach is `prob * weight / k`; under
                    // uniform sampling weight = k so the factor reduces to
                    // `prob`. Multiply the resulting value by `weight` to
                    // recover the unbiased sum.
                    new_reach[2] *= prob;
                    let child = self.cfr(
                        &state.apply(action),
                        abstraction,
                        new_reach,
                        iteration,
                        sampling,
                        rng,
                    );
                    // Importance reweighting: scale by k * prob / (1/k)
                    // = prob * weight (here weight = k * prob is implicit
                    // when prob = 1/k). For non-uniform priors we'd carry
                    // the prob ratio; uniform DCFR chance prior assumed.
                    return [prob * weight * child[0], prob * weight * child[1]];
                }
            }
        }

        let player_idx = player as usize;
        let key = state.infoset_key(player as u8, abstraction);
        let actions = state.legal_actions();
        let num_actions = actions.len();

        // v1.4 node-locking: if this infoset is locked, READ the strategy
        // from the lock map and SKIP both `update_regret_sum` and
        // `update_strategy_sum`. The locked vector IS the average strategy
        // at output time (spec §2.2 / §3.2). One HashMap lookup per
        // infoset visit; allocation-free in the locked branch.
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
                let v = self.cfr(
                    &state.apply(action),
                    abstraction,
                    new_reach,
                    iteration,
                    sampling,
                    rng,
                );
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
            let v = self.cfr(
                &state.apply(action),
                abstraction,
                new_reach,
                iteration,
                sampling,
                rng,
            );
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
        // PR 8: SIMD updates. Spread the per-player action_values into a
        // contiguous slice once so `simd::update_regret_sum` can vectorize
        // across all lanes (up to 8 for HUNL).
        let mut av_player: arrayvec::ArrayVec<f64, 16> = arrayvec::ArrayVec::new();
        for av in action_values.iter().take(num_actions) {
            av_player.push(av[player_idx]);
        }
        simd::update_regret_sum(
            &mut info.regret_sum,
            &av_player,
            node_value[player_idx],
            opponent_reach,
        );
        simd::update_strategy_sum(&mut info.strategy_sum, &strategy, own_reach);
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
        // v1.4 node-locking: merge locked vectors bit-identically into
        // the output (spec §3.3). Locked infosets are never inserted into
        // `self.infosets`, so this is the canonical passthrough.
        for (key, vec) in &self.locked_strategies {
            out.insert(key.clone(), vec.clone());
        }
        out
    }
}

/// Solve a HUNL postflop subgame via DCFR.
///
/// Algorithm (PR 6 §4.5):
///   1. Validate the config (postflop start, rake==0, board length matches
///      street). Reject preflop up front (PR 9 territory).
///   2. Build Agent A's flat `HUNLTree` once (D11: tree build AFTER
///      abstraction load). PR 6 keeps the tree for documentation / future
///      perf work; the DCFR loop below walks `HUNLState` directly.
///   3. Run DCFR for `iterations` iterations against the user-supplied
///      initial state. The abstraction (if any) threads through every
///      `state.infoset_key` call so bucketed keys are used.
///   4. Return the average strategy + iteration count + wallclock + infoset
///      count. `exploitability` and `game_value` stay `0.0` — Python
///      recomputes via the reference tier (D5).
///
/// `_target_exploitability` and `_seed` are accepted for forward-compat with
/// PR 8 but are **no-ops in PR 6** (both variable names carry an underscore
/// prefix to suppress dead-code warnings — grep for `target_exploitability`
/// and `seed` without the prefix will return no hits inside the function
/// body). Per spec §9 #13 option 1, the generic DCFR loop does not expose
/// an early-exit hook; vanilla DCFR is deterministic given identical
/// iteration order, so the seed has no observable effect. PR 8 may wire
/// `_seed` into a `StdHasher` for `HashMap` insertion-order determinism and
/// `_target_exploitability` into an `exploitability::compute` poll loop.
#[allow(clippy::too_many_arguments)]
pub fn solve_hunl_postflop(
    config: &HUNLConfig,
    abstraction: Option<&AbstractionTables>,
    iterations: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
    _target_exploitability: Option<f64>,
    _seed: Option<u64>,
    locked_strategies: Option<HashMap<String, Vec<f64>>>,
) -> Result<HUNLSolveOutput, HUNLSolveError> {
    validate_config(config)?;

    let config_arc = Arc::new(config.clone());

    // D11 — build the flat tree AFTER abstraction load. PR 6 does not walk
    // it directly during the solve (the DCFR loop walks `HUNLState`), but
    // the build is the canonical structural invariant per spec §4.5 and a
    // forward-compat hook for PR 8. The let-binding holds the tree alive
    // for the duration of the solve.
    let _tree = HUNLTree::build(Arc::clone(&config_arc), abstraction);

    let started = Instant::now();

    // PR 8 — public chance sampling opt-in via `config.use_pcs`. When
    // enabled, we silently switch beta to 0.5 (the sampled-CFR
    // recommendation per Tammelin 2014) and the inner CFR loop draws one
    // chance outcome per visit instead of enumerating.
    let sampling = if config.use_pcs {
        SamplingStrategy::PublicChance
    } else {
        SamplingStrategy::Full
    };
    let solver_beta = effective_beta(sampling, beta);
    // v1.4: route lock map into the solver. Empty/`None` is bit-identical
    // to v1.3 (the lock branch in `cfr` short-circuits on `get` -> None).
    let locked_map = locked_strategies.unwrap_or_default();
    let mut solver = HUNLDcfr::with_locked(alpha, solver_beta, gamma, locked_map);
    // PCS RNG seeded from caller (default 7 if unset). Determinism: fixed
    // seed → fixed outcome trace → fixed `average_strategy` across runs.
    let mut rng = PcsRng::new(_seed.unwrap_or(7));

    // Drive DCFR against the user-supplied initial state. Agent A's
    // `Game::initial()` for `HUNLState` returns a *default* tiny subgame
    // (the trait method is unparameterized), so we construct the initial
    // state from the user's config directly. The tail-discount catch-up
    // in `DCFRSolver::solve` is a no-op for unsampled traversal (every
    // infoset is visited every iteration, so `last_discount_iter` always
    // matches `self.iteration`), so we omit it here as well.
    let initial = HUNLState::initial(Arc::clone(&config_arc));
    for _ in 0..iterations {
        solver.iteration += 1;
        let reach = [1.0_f64, 1.0, 1.0];
        let _ = solver.cfr(
            &initial,
            abstraction,
            reach,
            solver.iteration,
            sampling,
            &mut rng,
        );
    }

    let average_strategy = solver.average_strategy();
    let wallclock_seconds = started.elapsed().as_secs_f64();
    let infoset_count = solver.infosets.len() as u32;

    Ok(HUNLSolveOutput {
        average_strategy,
        exploitability: 0.0, // Python recomputes (D5).
        game_value: 0.0,     // Python recomputes (D5).
        iterations,
        wallclock_seconds,
        infoset_count,
    })
}

/// PR 6 Stage A — same validation as PR 5's `_validate_postflop_config`.
fn validate_config(config: &HUNLConfig) -> Result<(), HUNLSolveError> {
    if config.starting_street == Street::Preflop {
        return Err(HUNLSolveError::PreflopNotSupported);
    }
    if config.starting_street == Street::Showdown {
        return Err(HUNLSolveError::InvalidConfig(
            "starting_street == Showdown has no decisions to make".into(),
        ));
    }
    let required_board: usize = match config.starting_street {
        Street::Flop => 3,
        Street::Turn => 4,
        Street::River => 5,
        Street::Preflop | Street::Showdown => unreachable!("guarded above"),
    };
    let board_len = config.initial_board.len();
    if board_len != required_board {
        return Err(HUNLSolveError::BoardLengthMismatch {
            expected: required_board,
            found: board_len,
            street: config.starting_street,
        });
    }
    if config.rake_rate != 0.0 || config.rake_cap != 0 {
        return Err(HUNLSolveError::RakeNonZero);
    }
    Ok(())
}
