//! PR #67 (issue #159) — regression tests for the `State::initial`
//! `initial_contributions` bug.
//!
//! Pre-fix, `PreflopRvrState::initial` and `HUNLState::initial_preflop`
//! unconditionally set `contributions = [SB+ante, BB+ante]` regardless of
//! `config.initial_contributions`. Downstream leaves compute
//! `cs = contributions - initial_contributions`, so a caller passing
//! `initial_contributions=[SB+ante, BB+ante]` with `initial_pot=0`
//! produced `cs=[0,0]` and `pot_total=0` at every leaf — collapsing the
//! preflop Nash to fold-everywhere.
//!
//! Post-fix:
//!   1. `State::initial` honors `initial_contributions` (contribution =
//!      max of blind amount and caller-declared dead money).
//!   2. `HUNLConfig::validate()` rejects malformed configs at the entry
//!      point (defense-in-depth — Python's `__post_init__` was the only
//!      guard before PR #67; PyO3 callers skip it).
//!   3. `[0,0]+pot=0` and `[SB+ante,BB+ante]+pot=SB+BB+2*ante` produce
//!      Nash-equivalent strategies (payoffs differ by a constant per-player
//!      shift, which leaves the equilibrium invariant).

use std::path::PathBuf;

use cfr_core::hunl::{card_to_int, HUNLConfig, Street};
use cfr_core::preflop_rvr::{solve_hunl_preflop_rvr, solve_hunl_preflop_rvr_with_hands};

fn equity_table_path() -> PathBuf {
    let manifest_dir = env!("CARGO_MANIFEST_DIR");
    let mut p = PathBuf::from(manifest_dir);
    p.pop(); // -> crates
    p.pop(); // -> repo root
    p.push("assets");
    p.push("preflop_equity_169x169.npz");
    p
}

/// Baseline well-formed config: `initial_contributions=[0,0]`, engine
/// posts the blinds. Same shape as `preflop_rvr_smoke::default_preflop_config`.
fn config_engine_posts_blinds() -> HUNLConfig {
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

/// Equivalent well-formed config: caller declared the posted blinds as
/// already-in-pot dead money. `initial_contributions=[SB+ante, BB+ante]`,
/// `initial_pot=SB+BB+2*ante`.
fn config_caller_declared_blinds() -> HUNLConfig {
    let mut cfg = config_engine_posts_blinds();
    cfg.initial_contributions = [cfg.small_blind + cfg.ante, cfg.big_blind + cfg.ante];
    cfg.initial_pot = cfg.initial_contributions[0] + cfg.initial_contributions[1];
    cfg
}

// ============================================================================
// Regression: AA must not 100%-fold when caller declares posted blinds.
//
// This is the PR #159 repro: pre-fix, AA at the SB folded 100% (and even
// every other hand folded) because every leaf saw `pot_total=0`.
// ============================================================================

#[test]
fn aa_does_not_fold_when_caller_declares_posted_blinds() {
    let path = equity_table_path();
    if !path.exists() {
        eprintln!("equity table missing — skipping");
        return;
    }
    // Pre-fix this config triggered the cs-bug: `cs=[0,0]`, `pot_total=0`,
    // fold dominates. Post-fix, `State::initial` honors the declared
    // blinds and AA opens / jams as usual.
    let cfg = config_caller_declared_blinds();
    let p0_holes = vec![[card_to_int(14, 0), card_to_int(14, 1)]]; // AsAh
    let p1_holes = vec![[card_to_int(13, 2), card_to_int(13, 3)]]; // KdKc
    let out = solve_hunl_preflop_rvr_with_hands(
        &cfg,
        &path,
        Some([p0_holes, p1_holes]),
        &[2.0, 3.0, 4.0, 5.0],
        &[2.0, 3.0, 4.0, 5.0],
        200,
        1.5,
        0.0,
        2.0,
    )
    .expect("solve must succeed with caller-declared-blinds config");

    let mut aa_root_strat: Option<Vec<f64>> = None;
    for (key, probs) in &out.average_strategy {
        if key.ends_with("||p|") && (key.starts_with("AhAs") || key.starts_with("AsAh")) {
            aa_root_strat = Some(probs.clone());
            break;
        }
    }
    let strat = aa_root_strat.expect("AA root strategy must exist in the output");
    let fold_prob = strat[0];
    assert!(
        fold_prob < 0.05,
        "AA at SB must not 100%-fold with declared blinds (got fold_prob={fold_prob}; \
         strat={strat:?})"
    );
    // Sum of aggressive lines (anything that isn't fold or call) dominates.
    let agg_prob: f64 = strat[2..].iter().sum();
    assert!(
        agg_prob > 0.5,
        "AA should mostly raise/jam preflop (got agg_prob={agg_prob}; strat={strat:?})"
    );
}

// ============================================================================
// Diff-test: both well-formed configs produce identical strategies.
// ============================================================================

#[test]
fn engine_posts_vs_caller_declared_blinds_produces_identical_strategies() {
    let path = equity_table_path();
    if !path.exists() {
        eprintln!("equity table missing — skipping");
        return;
    }
    let cfg_a = config_engine_posts_blinds();
    let cfg_b = config_caller_declared_blinds();
    // Single-hand vs single-hand keeps the tree tiny and CFR converged in a
    // tractable iteration count. Larger hand sets are exercised by the
    // smoke test; the strategy-equivalence invariant doesn't depend on the
    // hand-list size.
    let p0_holes = vec![[card_to_int(14, 0), card_to_int(14, 1)]]; // AsAh
    let p1_holes = vec![[card_to_int(13, 2), card_to_int(13, 3)]]; // KdKc
    let iters = 200;
    let out_a = solve_hunl_preflop_rvr_with_hands(
        &cfg_a,
        &path,
        Some([p0_holes.clone(), p1_holes.clone()]),
        &[2.0, 3.0, 4.0, 5.0],
        &[2.0, 3.0, 4.0, 5.0],
        iters,
        1.5,
        0.0,
        2.0,
    )
    .expect("solve A must succeed");
    let out_b = solve_hunl_preflop_rvr_with_hands(
        &cfg_b,
        &path,
        Some([p0_holes, p1_holes]),
        &[2.0, 3.0, 4.0, 5.0],
        &[2.0, 3.0, 4.0, 5.0],
        iters,
        1.5,
        0.0,
        2.0,
    )
    .expect("solve B must succeed");

    assert_eq!(
        out_a.decision_node_count, out_b.decision_node_count,
        "tree topology must be identical between equivalent configs"
    );
    assert_eq!(
        out_a.strategy_entry_count, out_b.strategy_entry_count,
        "infoset count must be identical between equivalent configs"
    );

    // For every (key, probs) in A, B must have an identical entry. We test
    // bit-exact equality: the leaf payoffs differ by exact constants (no
    // rounding), CFR uses the same RNG-less update rule, the discount
    // schedule is deterministic. Any drift signals a non-Nash-equivalent
    // state difference between the two State::initial paths.
    let tol: f64 = 1e-4;
    let mut max_drift = 0.0_f64;
    let mut max_drift_key: String = String::new();
    for (key, probs_a) in &out_a.average_strategy {
        let probs_b = out_b
            .average_strategy
            .get(key)
            .unwrap_or_else(|| panic!("key {key:?} missing from cfg_b strategy"));
        assert_eq!(
            probs_a.len(),
            probs_b.len(),
            "action count differs at key {key:?}"
        );
        for (a, b) in probs_a.iter().zip(probs_b.iter()) {
            let drift = (a - b).abs();
            if drift > max_drift {
                max_drift = drift;
                max_drift_key = key.clone();
            }
        }
    }
    assert!(
        max_drift < tol,
        "strategies diverged beyond tolerance {tol}: max_drift={max_drift} at key \
         {max_drift_key:?}"
    );
}

// ============================================================================
// HUNLConfig::validate() rejects the malformed-config trigger.
// ============================================================================

#[test]
fn validate_rejects_preflop_contributions_without_matching_pot() {
    // The exact PR #159 repro: SB+BB declared but initial_pot left at 0.
    // Pre-fix this silently produced a fold-everywhere Nash; post-fix
    // `HUNLConfig::validate` rejects it loudly.
    let mut cfg = config_engine_posts_blinds();
    cfg.initial_contributions = [50, 100];
    cfg.initial_pot = 0;
    let err = cfg
        .validate()
        .expect_err("malformed [50,100]+pot=0 must be rejected at preflop");
    assert!(
        err.contains("initial_contributions"),
        "error message must mention initial_contributions; got {err:?}"
    );
}

#[test]
fn validate_accepts_engine_posts_blinds_form() {
    let cfg = config_engine_posts_blinds();
    cfg.validate()
        .expect("baseline [0,0]+pot=0 config must validate");
}

#[test]
fn validate_accepts_caller_declared_blinds_form() {
    let cfg = config_caller_declared_blinds();
    cfg.validate()
        .expect("caller-declared-blinds config must validate after PR #67 fix");
}

#[test]
fn validate_rejects_nonzero_rake_rate() {
    let mut cfg = config_engine_posts_blinds();
    cfg.rake_rate = 0.05;
    let err = cfg
        .validate()
        .expect_err("nonzero rake_rate must be rejected");
    assert!(
        err.contains("rake_rate"),
        "error message must mention rake_rate; got {err:?}"
    );
}

#[test]
fn validate_rejects_negative_starting_stack() {
    let mut cfg = config_engine_posts_blinds();
    cfg.starting_stack = -1;
    let err = cfg
        .validate()
        .expect_err("non-positive starting_stack must be rejected");
    assert!(
        err.contains("starting_stack"),
        "error message must mention starting_stack; got {err:?}"
    );
}

#[test]
fn validate_rejects_postflop_with_empty_board() {
    let mut cfg = config_engine_posts_blinds();
    cfg.starting_street = Street::Flop;
    cfg.initial_board = vec![]; // empty
    let err = cfg
        .validate()
        .expect_err("postflop with empty initial_board must be rejected");
    assert!(
        err.contains("initial_board"),
        "error message must mention initial_board; got {err:?}"
    );
}

#[test]
fn validate_rejects_postflop_contributions_not_summing_to_pot() {
    let mut cfg = config_engine_posts_blinds();
    cfg.starting_street = Street::Flop;
    cfg.initial_board = vec![8, 12, 16];
    cfg.initial_pot = 200;
    cfg.initial_contributions = [50, 100]; // sum=150, doesn't match pot=200
    let err = cfg
        .validate()
        .expect_err("postflop initial_contributions not matching initial_pot must be rejected");
    assert!(
        err.contains("sum"),
        "error message must mention sum invariant; got {err:?}"
    );
}

#[test]
fn validate_accepts_postflop_dead_money_subgame() {
    // (0, 0) is the "dead-money subgame" form per Python guard.
    let mut cfg = config_engine_posts_blinds();
    cfg.starting_street = Street::Flop;
    cfg.initial_board = vec![8, 12, 16];
    cfg.initial_pot = 200;
    cfg.initial_contributions = [0, 0];
    cfg.validate()
        .expect("postflop dead-money subgame must validate");
}

// ============================================================================
// solve_hunl_preflop_rvr-level validation: the bug-triggering config is
// rejected at the entry point, not silently producing a degenerate Nash.
// ============================================================================

#[test]
fn solve_hunl_preflop_rvr_rejects_malformed_initial_contributions() {
    let path = equity_table_path();
    if !path.exists() {
        eprintln!("equity table missing — skipping");
        return;
    }
    let mut cfg = config_engine_posts_blinds();
    cfg.initial_contributions = [50, 100];
    cfg.initial_pot = 0; // mismatched — would trigger pot_total=0 pre-fix.
    let res = solve_hunl_preflop_rvr(
        &cfg,
        &path,
        &[2.0, 3.0, 4.0, 5.0],
        &[2.0, 3.0, 4.0, 5.0],
        3,
        1.5,
        0.0,
        2.0,
    );
    // `PreflopRvrOutput` doesn't implement `Debug`, so we can't use
    // `expect_err` and have to unwrap manually.
    match res {
        Ok(_) => panic!("malformed config must be rejected at entry point"),
        Err(err) => assert!(
            err.contains("initial_contributions"),
            "error must mention initial_contributions; got {err:?}"
        ),
    }
}
