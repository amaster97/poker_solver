//! Phase A.5 — Rust smoke tests for the full-tree preflop RvR solver.
//!
//! These tests exercise the new `solve_hunl_preflop_rvr` end-to-end via the
//! shipped 169x169x3 equity table at `assets/preflop_equity_169x169.npz`.
//! Three checks:
//!
//! 1. 3-iter smoke: tree builds, strategy is non-empty, hand_count =
//!    [1326, 1326].
//! 2. AA-only range vs KK-only range -> AA jam ~100% at deep iters.
//! 3. The CFR loop doesn't panic on the default config.

use std::path::PathBuf;

use cfr_core::hunl::{card_to_int, HUNLConfig, Street};
use cfr_core::preflop_rvr::{solve_hunl_preflop_rvr, solve_hunl_preflop_rvr_with_hands};

/// Resolve the absolute path to the committed equity table.
fn equity_table_path() -> PathBuf {
    // `CARGO_MANIFEST_DIR` is `crates/cfr_core`; assets lives two levels up.
    let manifest_dir = env!("CARGO_MANIFEST_DIR");
    let mut p = PathBuf::from(manifest_dir);
    p.pop(); // -> crates
    p.pop(); // -> repo root
    p.push("assets");
    p.push("preflop_equity_169x169.npz");
    p
}

fn default_preflop_config() -> HUNLConfig {
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
        ..Default::default()
    }
}

#[test]
fn three_iter_smoke_emits_non_empty_strategy() {
    let path = equity_table_path();
    assert!(
        path.exists(),
        "equity table missing at {path:?} — run `cargo run --release \
         --example build_preflop_equity` first"
    );
    let cfg = default_preflop_config();
    let out = solve_hunl_preflop_rvr(
        &cfg,
        &path,
        &[2.0, 3.0, 4.0, 5.0],
        &[2.0, 3.0, 4.0, 5.0],
        3,
        1.5,
        0.0,
        2.0,
    )
    .expect("solve must succeed with valid config + table");

    assert!(out.decision_node_count > 0, "no decision nodes");
    assert!(
        out.strategy_entry_count > 0,
        "strategy dict empty after 3 iters"
    );
    assert_eq!(
        out.hand_count_per_player,
        [1326, 1326],
        "expected full 1326-combo per player"
    );

    // Each row should sum to ~1.0.
    let mut bad = 0usize;
    for (k, probs) in out.average_strategy.iter().take(20) {
        let s: f64 = probs.iter().sum();
        if (s - 1.0).abs() > 1e-6 {
            eprintln!("row {k:?} sum={s}");
            bad += 1;
        }
    }
    assert_eq!(bad, 0, "rows did not normalize to 1.0");
}

/// Closed-form micro-test: hero range = {AA only}, villain range = {KK only}.
/// AA crushes KK preflop (~81.3% equity), so at deep convergence AA should
/// either OPEN large or JAM ALL-IN with very high frequency (no folding).
///
/// We constrain ranges by passing single-combo hand lists.
#[test]
fn aa_vs_kk_closed_form_aa_does_not_fold() {
    let path = equity_table_path();
    if !path.exists() {
        eprintln!("equity table missing — skipping");
        return;
    }
    let cfg = default_preflop_config();
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
    .expect("aa-vs-kk solve must succeed");

    assert!(out.decision_node_count > 0);
    // Find the root SB opener (action set should be [check OR call, open opts, all-in]).
    // The root preflop key is `<AsAh>||p|` (sorted: "AhAs" or "AsAh" depending
    // on canonicalization; we'll look up by suffix).
    let mut aa_root_strat: Option<Vec<f64>> = None;
    for (key, probs) in &out.average_strategy {
        // Root suffix: "||p|" with no history yet.
        if key.ends_with("||p|") && (key.starts_with("AhAs") || key.starts_with("AsAh")) {
            aa_root_strat = Some(probs.clone());
            break;
        }
    }
    let strat = aa_root_strat
        .expect("AA root strategy must exist in the output");
    // Action set: [Fold-not-applicable, Call (BB call), open_2bb, open_3bb,
    // open_4bb, open_5bb, AllIn]. Actually at the root SB faces the BB
    // blind so to_call > 0 -> [Fold, Call, opens..., AllIn]. So index 0
    // = Fold. AA should never fold.
    eprintln!("AA root strategy: {strat:?}");
    let fold_prob = strat[0];
    assert!(
        fold_prob < 0.05,
        "AA must not fold preflop (got fold_prob={fold_prob})"
    );
    // Sum of aggressive actions (everything except fold or limp-call) should
    // dominate.
    // Action ordering in our enumerator (when facing bet, cap not reached):
    //   [Fold, Call, OpenTo(...), OpenTo(...), ..., AllIn]
    let agg_prob: f64 = strat[2..].iter().sum();
    assert!(
        agg_prob > 0.5,
        "AA should mostly raise/jam preflop (got agg_prob={agg_prob}; strat={strat:?})"
    );
}

#[test]
fn rejects_postflop_config() {
    let mut cfg = default_preflop_config();
    cfg.starting_street = Street::Flop;
    cfg.initial_board = vec![8, 12, 16, 20, 24];
    let path = equity_table_path();
    if !path.exists() {
        eprintln!("equity table not built — skipping (will be HARD-FAIL once table is committed)");
        return;
    }
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
    assert!(res.is_err(), "must reject postflop config");
}

#[test]
fn rejects_fixed_hole_cards() {
    let mut cfg = default_preflop_config();
    cfg.initial_hole_cards = Some([
        [cfr_core::hunl::card_to_int(14, 0), cfr_core::hunl::card_to_int(14, 1)],
        [cfr_core::hunl::card_to_int(13, 2), cfr_core::hunl::card_to_int(13, 3)],
    ]);
    let path = equity_table_path();
    if !path.exists() {
        eprintln!("equity table not built — skipping");
        return;
    }
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
    assert!(res.is_err(), "must reject fixed-hole config");
}
