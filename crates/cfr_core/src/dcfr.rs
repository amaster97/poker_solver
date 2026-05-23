//! Discounted Counterfactual Regret Minimization (Rust production tier).
//!
//! Brown, N. and Sandholm, T. (2019). "Solving Imperfect-Information Games via
//! Discounted Regret Minimization." AAAI 2019. (arxiv 1809.04040)
//!
//! Each iteration t:
//!   - Walk the game tree, computing counterfactual values for the current
//!     regret-matching strategy.
//!   - Discount the existing cumulative regrets and strategy sums by DCFR
//!     factors BEFORE adding this iteration's contributions:
//!
//!     R^t(I,a) = R^{t-1}(I,a) * (t^α / (t^α + 1)) + r^t(I,a)   if R^{t-1} > 0
//!     R^t(I,a) = R^{t-1}(I,a) * (t^β / (t^β + 1)) + r^t(I,a)   if R^{t-1} <= 0
//!     s_I[a]   = s_I[a] * (t / (t + 1))^γ + π_{-i}(I) * σ^t(I,a)
//!
//! Defaults (α, β, γ) = (1.5, 0.0, 2.0) — the paper's recommended setting.
//!
//! This file is a structural port of `poker_solver/dcfr.py` — same call graph,
//! same iteration semantics, same lazy-discount strategy. Mirrors the Python
//! tier's `_cfr` and `_discount` exactly so the differential test in
//! `tests/test_dcfr_diff.py` passes.
//!
//! The solver is generic over the `Game` trait (see `game.rs`); concrete games
//! (Kuhn, Leduc, future Hold'em abstractions) plug in without touching this
//! file. Action counts are stored as `Vec<f64>` because Leduc has 1–3 legal
//! actions per node depending on betting context — assuming a fixed width
//! would not survive the port.
//!
//! Algorithmic reference: `references/code/open_spiel/open_spiel/algorithms/cfr.cc`
//! (Apache 2.0) and `references/code/noambrown_poker_solver/cpp/src/trainer.cpp`
//! (MIT). The exact structure here was re-derived from `dcfr.py` to keep tier
//! parity; cross-checked against those references for correctness only.

use std::collections::HashMap;

use crate::game::Game;
use crate::simd;

/// Per-infoset cumulative regret and strategy-sum vectors.
#[derive(Clone, Debug)]
pub struct InfosetData {
    pub regret_sum: Vec<f64>,
    pub strategy_sum: Vec<f64>,
    pub num_actions: usize,
    /// Iteration this infoset was last discounted at. Lazy discounting catches
    /// up on access, matching the Python tier's `_discount` behavior.
    pub last_discount_iter: u32,
}

impl InfosetData {
    fn new(num_actions: usize) -> Self {
        Self {
            regret_sum: vec![0.0; num_actions],
            strategy_sum: vec![0.0; num_actions],
            num_actions,
            last_discount_iter: 0,
        }
    }
}

/// DCFR solver state, generic over a game type implementing `Game`.
pub struct DCFRSolver<G: Game> {
    pub alpha: f64,
    pub beta: f64,
    pub gamma: f64,
    pub infosets: HashMap<String, InfosetData>,
    pub iteration: u32,
    _phantom: std::marker::PhantomData<G>,
}

impl<G: Game> DCFRSolver<G> {
    pub fn new(alpha: f64, beta: f64, gamma: f64) -> Self {
        Self {
            alpha,
            beta,
            gamma,
            infosets: HashMap::new(),
            iteration: 0,
            _phantom: std::marker::PhantomData,
        }
    }

    /// Regret-matching strategy: positive regrets normalized, uniform if zero.
    ///
    /// PR 8: routes through `simd::positive_regrets_and_total` +
    /// `simd::normalize` so the per-iteration hot path benefits from the
    /// NEON-vectorized clamp + sum + divide on aarch64. Behavior is
    /// bit-identical to the scalar fallback on the per-lane outputs;
    /// horizontal-sum reduction order can differ by ULP≤1 (pairwise vs
    /// sequential).
    pub fn get_strategy(info: &InfosetData) -> Vec<f64> {
        let mut positive = vec![0.0_f64; info.num_actions];
        let total = simd::positive_regrets_and_total(&info.regret_sum, &mut positive);
        simd::normalize(&mut positive, total);
        positive
    }

    /// Lazy DCFR discount catch-up. Iterates from `last_discount_iter + 1`
    /// through `t`, applying the per-iteration regret/strategy decay. Fresh
    /// infosets start at zero so we can skip already-zero rows efficiently —
    /// but for parity with Python we still walk every intermediate iteration
    /// (Python's loop also does this). Discounts happen BEFORE the iteration's
    /// new contribution is added (Brown & Sandholm 2019, eq. 3-5).
    ///
    /// Free function (takes alpha/beta/gamma) to avoid borrowing `self` while
    /// `self.infosets` is already mutably borrowed inside `cfr`.
    fn discount_info(info: &mut InfosetData, t: u32, alpha: f64, beta: f64, gamma: f64) {
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
            // PR 8: NEON-vectorized discount kernels. The sign-conditional
            // regret discount uses `vbslq_f64` over the `> 0` mask;
            // strategy-sum is a flat `*= scale`. Behavior is bit-identical
            // to the scalar fallback (no FMA in these paths).
            simd::discount_regrets(&mut info.regret_sum, pos_scale, neg_scale);
            simd::discount_strategy_sum(&mut info.strategy_sum, strat_scale);
        }
        info.last_discount_iter = t;
    }

    /// Recursive CFR traversal.
    /// `reach` is `[p0_reach, p1_reach, chance_reach]`, mirroring Python's
    /// `np.ones(num_players + 1)`.
    pub fn cfr(&mut self, state: &G, reach: [f64; 3], iteration: u32) -> [f64; 2] {
        if state.is_terminal() {
            return state.utility();
        }
        let player = state.current_player();
        if player == -1 {
            // Chance node: weight children by probability.
            let mut value = [0.0_f64; 2];
            for (action, prob) in state.chance_outcomes() {
                let mut new_reach = reach;
                new_reach[2] *= prob;
                let child = self.cfr(&state.apply(action), new_reach, iteration);
                value[0] += prob * child[0];
                value[1] += prob * child[1];
            }
            return value;
        }

        let player_idx = player as usize;
        let key = state.infoset_key(player as u8);
        let actions = state.legal_actions();
        let num_actions = actions.len();

        // Lazy discount, then sample the current strategy (regret matching).
        let info = self
            .infosets
            .entry(key.clone())
            .or_insert_with(|| InfosetData::new(num_actions));
        Self::discount_info(info, iteration, self.alpha, self.beta, self.gamma);
        let strategy = Self::get_strategy(info);

        let mut node_value = [0.0_f64; 2];
        // `action_values` stores per-(action, player) utility. The outer Vec is
        // sized by `num_actions` because Leduc has 1–3 legal actions per node
        // depending on betting context (raise cap, fold availability); a fixed
        // `[..; 2]` outer width would only fit Kuhn.
        let mut action_values: Vec<[f64; 2]> = vec![[0.0_f64; 2]; num_actions];
        for (idx, &action) in actions.iter().enumerate() {
            let mut new_reach = reach;
            new_reach[player_idx] *= strategy[idx];
            let v = self.cfr(&state.apply(action), new_reach, iteration);
            action_values[idx] = v;
            node_value[0] += strategy[idx] * v[0];
            node_value[1] += strategy[idx] * v[1];
        }

        // Counterfactual reach: product of opponents' and chance's reach.
        let mut opponent_reach = 1.0;
        for (i, &r) in reach.iter().enumerate() {
            if i != player_idx {
                opponent_reach *= r;
            }
        }
        let own_reach = reach[player_idx];

        // Re-borrow the infoset to update regrets/strategy sum after recursion.
        let info = self
            .infosets
            .get_mut(&key)
            .expect("infoset must exist after insert");
        // PR 8: SIMD updates. Spread action_values into a contiguous per-player
        // slice once so `simd::update_regret_sum` can vectorize across lanes.
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

    /// Solve for `iterations` iterations, return the average strategy.
    pub fn solve(&mut self, iterations: u32) -> HashMap<String, Vec<f64>> {
        let initial = G::initial();
        for _ in 0..iterations {
            self.iteration += 1;
            let reach = [1.0_f64, 1.0, 1.0];
            self.cfr(&initial, reach, self.iteration);
        }
        // Final catch-up so any stale infosets reflect the latest t (matches
        // the Python tier's tail discount).
        let final_iter = self.iteration;
        let alpha = self.alpha;
        let beta = self.beta;
        let gamma = self.gamma;
        for info in self.infosets.values_mut() {
            Self::discount_info(info, final_iter, alpha, beta, gamma);
        }
        self.average_strategy()
    }

    pub fn average_strategy(&self) -> HashMap<String, Vec<f64>> {
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
        out
    }
}
