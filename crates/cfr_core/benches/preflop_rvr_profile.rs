//! Phase B profile harness — measure per-phase wall-clock cost inside the
//! full-tree preflop RvR engine (PR #122).
//!
//! Run with:
//! ```
//! cargo bench --bench preflop_rvr_profile --manifest-path crates/cfr_core/Cargo.toml \
//!   --features profile_preflop_rvr
//! ```
//! (Without `--features profile_preflop_rvr` only total wall is reported.)
//!
//! Default fixture: small 3-class range (AA, KK, 72o sampled) × 6 iters,
//! mirroring the user's referenced "3-class range" benchmark scale. A
//! `--full` flag widens to the full 1326-combo fixture.
//!
//! Reports per-phase seconds per iter + pct of total inner-kernel time.
//! This drives the Phase B perf optimization PR (task #53).
#![allow(dead_code)]

use std::path::PathBuf;
use std::time::Instant;

use cfr_core::hunl::{card_to_int, HUNLConfig, Street};
use cfr_core::preflop_rvr::solve_hunl_preflop_rvr_with_hands;

#[cfg(feature = "profile_preflop_rvr")]
use cfr_core::preflop_rvr::profile;

fn ns_to_s(ns: u128) -> f64 {
    ns as f64 / 1_000_000_000.0
}

fn equity_table_path() -> PathBuf {
    let manifest_dir = env!("CARGO_MANIFEST_DIR");
    let mut p = PathBuf::from(manifest_dir);
    p.pop();
    p.pop();
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
    }
}

/// 3-class fixture: 12 hand instances (4 AA + 4 KK + 4 72o combos) per player.
/// Approximates the "3-class range" scale referenced by the user.
fn three_class_hands() -> [Vec<[u8; 2]>; 2] {
    let h = vec![
        // AA: 4 combos.
        [card_to_int(14, 0), card_to_int(14, 1)],
        [card_to_int(14, 0), card_to_int(14, 2)],
        [card_to_int(14, 0), card_to_int(14, 3)],
        [card_to_int(14, 1), card_to_int(14, 2)],
        // KK: 4 combos.
        [card_to_int(13, 0), card_to_int(13, 1)],
        [card_to_int(13, 0), card_to_int(13, 2)],
        [card_to_int(13, 0), card_to_int(13, 3)],
        [card_to_int(13, 1), card_to_int(13, 2)],
        // 72o: 4 combos.
        [card_to_int(7, 0), card_to_int(2, 1)],
        [card_to_int(7, 0), card_to_int(2, 2)],
        [card_to_int(7, 1), card_to_int(2, 2)],
        [card_to_int(7, 2), card_to_int(2, 3)],
    ];
    [h.clone(), h]
}

/// Full-deck fixture (1326 combos / player).
fn full_deck_hands() -> [Vec<[u8; 2]>; 2] {
    let mut single_holes: Vec<[u8; 2]> = Vec::with_capacity(1326);
    for r0 in 2u8..=14 {
        for s0 in 0u8..4 {
            let c0 = card_to_int(r0, s0);
            for r1 in 2u8..=14 {
                for s1 in 0u8..4 {
                    let c1 = card_to_int(r1, s1);
                    if c0 >= c1 {
                        continue;
                    }
                    single_holes.push([c0, c1]);
                }
            }
        }
    }
    [single_holes.clone(), single_holes]
}

/// Mid-size fixture: 100 hands per player (sampled diverse).
fn mid_deck_hands() -> [Vec<[u8; 2]>; 2] {
    let full = full_deck_hands();
    let pick: Vec<[u8; 2]> = full[0].iter().step_by(13).copied().collect();
    [pick.clone(), pick]
}

fn main() {
    let path = equity_table_path();
    if !path.exists() {
        eprintln!("equity table missing at {path:?}");
        std::process::exit(1);
    }

    let mode = std::env::args().nth(1).unwrap_or_else(|| "3class".to_string());
    let iters: u32 = std::env::args()
        .nth(2)
        .and_then(|s| s.parse().ok())
        .unwrap_or(6);

    let hand_lists = match mode.as_str() {
        "full" => full_deck_hands(),
        "mid" => mid_deck_hands(),
        _ => three_class_hands(),
    };
    let cfg = default_preflop_config();

    println!("=== Preflop RvR Phase B profile ===");
    println!("Mode:    {mode}");
    println!("P0 hands: {}, P1 hands: {}", hand_lists[0].len(), hand_lists[1].len());
    println!("Iters:    {iters}");
    println!("Menu:     opens=[2,3,4,5]BB  reraise=[2,3,4,5]x  cap=4");
    println!();

    #[cfg(feature = "profile_preflop_rvr")]
    profile::reset();

    let started = Instant::now();
    let out = solve_hunl_preflop_rvr_with_hands(
        &cfg,
        &path,
        Some(hand_lists),
        &[2.0, 3.0, 4.0, 5.0],
        &[2.0, 3.0, 4.0, 5.0],
        iters,
        1.5, // alpha
        0.0, // beta
        2.0, // gamma
    )
    .expect("solve failed");
    let total = started.elapsed();

    let per_iter = total.as_secs_f64() / iters as f64;
    println!("Total wall:           {:>8.3} s ({iters} iters)", total.as_secs_f64());
    println!("Per-iter wall:        {:>8.3} s", per_iter);
    println!("Decision nodes:       {}", out.decision_node_count);
    println!("Strategy entries:     {}", out.strategy_entry_count);
    println!();

    #[cfg(feature = "profile_preflop_rvr")]
    {
        let snap = profile::snapshot();
        let parts = [
            ("terminal_value_vector", snap.terminal_eval_ns),
            ("compute_strategy", snap.compute_strategy_ns),
            ("discount", snap.discount_ns),
            ("opp_next_reach (reach * strategy)", snap.opp_next_reach_ns),
            ("own_next_reach (reach * strategy)", snap.own_next_reach_ns),
            ("node_values (Σ strategy*av)", snap.node_values_ns),
            ("update_regret_sum_vector", snap.update_regret_ns),
            ("update_strategy_sum", snap.update_strategy_sum_ns),
            ("alloc(action_values)", snap.alloc_action_values_ns),
            ("alloc(strategy)", snap.alloc_strategy_buf_ns),
            ("opp_accumulate (values[h]+=child)", snap.opp_accumulate_ns),
        ];
        let sum_ns: u128 = parts.iter().map(|(_, ns)| *ns).sum();
        let sum_s = ns_to_s(sum_ns);
        println!("Per-phase breakdown (total over {iters} iters):");
        println!("  {:42} {:>10} {:>9}", "phase", "seconds", "pct");
        for (name, ns) in parts.iter() {
            let s = ns_to_s(*ns);
            let pct = if sum_ns > 0 {
                100.0 * (*ns as f64) / (sum_ns as f64)
            } else {
                0.0
            };
            println!("  {:42} {:>10.3} {:>8.1}%", name, s, pct);
        }
        let unaccounted = total.as_secs_f64() - sum_s;
        println!(
            "  {:42} {:>10.3} {:>8.1}%",
            "(unaccounted: alloc/recursion/etc)",
            unaccounted,
            100.0 * unaccounted / total.as_secs_f64()
        );
        println!();
        println!("Per-iter breakdown (s/iter):");
        for (name, ns) in parts.iter() {
            let s = ns_to_s(*ns) / iters as f64;
            println!("  {:42} {:>10.3}", name, s);
        }
    }
    #[cfg(not(feature = "profile_preflop_rvr"))]
    {
        println!("(per-phase breakdown unavailable; rebuild with --features profile_preflop_rvr)");
    }
}
