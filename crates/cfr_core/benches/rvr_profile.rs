//! HIGH-2 follow-up: per-phase profile of the vector-form RvR inner kernel.
//!
//! Run with:
//! ```
//! cargo bench --bench rvr_profile --manifest-path crates/cfr_core/Cargo.toml \
//!   --features profile_rvr
//! ```
//! (Without `--features profile_rvr` the per-phase breakdown is zero;
//! total wall-clock per iter is still reported.)
//!
//! Default fixture: full-deck river RvR (1326 hands per player after
//! board-removal — actual count is 1081 on a 5-card board, with 990
//! board-disjoint combos after collisions). 5 iters, board fixed.
//! Reports cost breakdown in seconds per phase per iter and total wall.
//!
//! Drives PR titled "perf: NEON SIMD on vector-form RvR inner kernel
//! (HIGH-2 follow-up)" — see `docs/...` for context.

use std::sync::Arc;
use std::time::Instant;

use cfr_core::dcfr_vector::solve_range_vs_range_postflop_with_hands;
use cfr_core::hunl::{HUNLConfig, Street};

#[cfg(feature = "profile_rvr")]
use cfr_core::dcfr_vector::profile;

#[allow(dead_code)]
fn ns_to_s(ns: u128) -> f64 {
    ns as f64 / 1_000_000_000.0
}

fn build_river_config_full() -> HUNLConfig {
    // Full-tree spec: 2 bet sizes, raise_cap=3, include_all_in=true.
    // This matches the HIGH-2 finding's "~26 s/iter river" tree config —
    // significantly larger betting tree than the diff-test fixture's
    // single-bet-size raise_cap=1 setup.
    let board = vec![
        14 * 4,
        7 * 4 + 3,
        2 * 4 + 2,
        13 * 4 + 1,
        5 * 4,
    ];
    HUNLConfig {
        starting_stack: 5000,
        small_blind: 50,
        big_blind: 100,
        ante: 0,
        starting_street: Street::River,
        initial_board: board,
        initial_pot: 1000,
        initial_contributions: [500, 500],
        initial_hole_cards: None,
        preflop_raise_cap: 4,
        postflop_raise_cap: 3,
        bet_size_fractions: vec![0.5, 1.0],
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

fn build_river_config(raise_cap: u8) -> HUNLConfig {
    // Board: As 7c 2d Kh 5s (rank*4 + suit, suits per Python: s=0 h=1 d=2 c=3).
    let board = vec![
        14 * 4,     // As
        7 * 4 + 3,  // 7c
        2 * 4 + 2,  // 2d
        13 * 4 + 1, // Kh
        5 * 4,      // 5s
    ];
    HUNLConfig {
        starting_stack: 5000,
        small_blind: 50,
        big_blind: 100,
        ante: 0,
        starting_street: Street::River,
        initial_board: board,
        initial_pot: 1000,
        initial_contributions: [500, 500],
        initial_hole_cards: None,
        preflop_raise_cap: 4,
        postflop_raise_cap: raise_cap,
        bet_size_fractions: vec![0.75],
        include_all_in: false,
        force_allin_threshold: 1,
        min_bet_bb: 1,
        rake_rate: 0.0,
        rake_cap: 0,
        abstraction_path: None,
        abstraction_version: None,
        use_pcs: false,
    }
}

fn build_hand_lists(
    board: &[u8],
    n_per_player: usize,
) -> ([Vec<[u8; 2]>; 2], usize) {
    // Cards: `rank * 4 + suit` with `rank in 2..=14`, `suit in 0..=3`,
    // valid ids `[8, 59]` (see `hunl::card_to_int`).
    let mut held = [false; 64];
    for &c in board {
        held[c as usize] = true;
    }
    // Enumerate all valid pairs (c0 < c1, both disjoint from board, valid rank).
    let mut all_pairs: Vec<[u8; 2]> = Vec::new();
    for r0 in 2u8..=14 {
        for s0 in 0u8..4 {
            let c0 = r0 * 4 + s0;
            if held[c0 as usize] {
                continue;
            }
            for r1 in 2u8..=14 {
                for s1 in 0u8..4 {
                    let c1 = r1 * 4 + s1;
                    if held[c1 as usize] || c0 >= c1 {
                        continue;
                    }
                    all_pairs.push([c0, c1]);
                }
            }
        }
    }
    let take = n_per_player.min(all_pairs.len());
    let selected: Vec<[u8; 2]> = all_pairs.iter().take(take).copied().collect();
    let actual = selected.len();
    (
        [selected.clone(), selected],
        actual,
    )
}

fn main() {
    let _ = Arc::<()>::default();
    let n_per_player_arg: usize = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(1326);
    let iters: u32 = std::env::args()
        .nth(2)
        .and_then(|s| s.parse().ok())
        .unwrap_or(5);
    let raise_cap: u8 = std::env::args()
        .nth(3)
        .and_then(|s| s.parse().ok())
        .unwrap_or(1);
    let use_full_tree = std::env::args().any(|a| a == "--full-tree");

    let config = if use_full_tree {
        build_river_config_full()
    } else {
        build_river_config(raise_cap)
    };
    let (hand_lists, actual_n) = build_hand_lists(&config.initial_board, n_per_player_arg);

    println!("=== Vector-form RvR profile ===");
    println!("Board: As 7c 2d Kh 5s (river, 1 bet size, raise_cap=1)");
    println!("Hands per player (req={n_per_player_arg}, actual={actual_n}); iterations={iters}");
    println!();

    #[cfg(feature = "profile_rvr")]
    profile::reset();

    let started = Instant::now();
    let out = solve_range_vs_range_postflop_with_hands(
        &config,
        Some(hand_lists),
        iters,
        1.5, // alpha
        0.0, // beta
        2.0, // gamma
        0.0, // regret_init_noise
        0,
        None, // hand_weights (B10 Phase B; None = all-1.0 reach, legacy)
    )
    .expect("solve failed");
    let total = started.elapsed();

    let per_iter = total.as_secs_f64() / iters as f64;
    println!("Total wall:           {:>8.3} s ({iters} iters)", total.as_secs_f64());
    println!("Per-iter wall:        {:>8.3} s", per_iter);
    println!("Decision nodes:       {}", out.decision_node_count);
    println!("Strategy entries:     {}", out.strategy_entry_count);
    println!();

    #[cfg(feature = "profile_rvr")]
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
            ("chance_accumulate", snap.chance_accumulate_ns),
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
        println!("  {:42} {:>10.3} {:>8.1}%",
                 "(unaccounted: alloc/recursion/etc)",
                 unaccounted,
                 100.0 * unaccounted / total.as_secs_f64());

        println!();
        println!("Per-iter breakdown (s/iter):");
        for (name, ns) in parts.iter() {
            let s = ns_to_s(*ns) / iters as f64;
            println!("  {:42} {:>10.3}", name, s);
        }
    }
    #[cfg(not(feature = "profile_rvr"))]
    {
        println!("(per-phase breakdown unavailable; rebuild with --features profile_rvr)");
    }
}
