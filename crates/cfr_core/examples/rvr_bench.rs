//! v1.8 SIMD perf bench: vector-form DCFR (`dcfr_vector.rs`) wall-clock.
//!
//! Run with:
//!   cargo run --release --manifest-path crates/cfr_core/Cargo.toml \
//!     --example rvr_bench
//!
//! This bench is the workload the v1.8 plan claims to accelerate — the
//! per-(hand, action) hot loops in `dcfr_vector::VectorDCFR::solve`. The
//! existing `dcfr_bench.rs` only exercises `dcfr.rs` (scalar info-state
//! DCFR for Kuhn/Leduc), which was already SIMD-wired at v1.0.1 / PR 8;
//! it cannot validate the v1.8 incremental.
//!
//! Workload: river R-v-R, board = As 7c 2d Kh 5s, single bet size, 47*46/2
//! = 1081 hands per player. Same config as the inline `tiny_river_rvr()`
//! test fixture (`dcfr_vector.rs::tests::tiny_river_rvr`).

use std::time::Instant;

use cfr_core::dcfr_vector::solve_range_vs_range_postflop;
use cfr_core::hunl::{card_to_int, HUNLConfig, Street};

const RVR_ITERS: u32 = 5;
const NUM_RUNS: usize = 3;

fn tiny_river_rvr() -> HUNLConfig {
    HUNLConfig {
        starting_stack: 1000,
        small_blind: 50,
        big_blind: 100,
        ante: 0,
        starting_street: Street::River,
        initial_board: vec![
            card_to_int(14, 0),
            card_to_int(7, 3),
            card_to_int(2, 2),
            card_to_int(13, 1),
            card_to_int(5, 0),
        ],
        initial_pot: 1000,
        initial_contributions: [500, 500],
        initial_hole_cards: None,
        preflop_raise_cap: 4,
        postflop_raise_cap: 1,
        bet_size_fractions: vec![0.33, 0.75, 1.5],
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

fn main() {
    println!("== v1.8 SIMD perf bench (vector-form DCFR / dcfr_vector.rs) ==");
    println!(
        "Workload: river R-v-R, 1081 hands/player, 3 bet sizes (no all-in), {} iters",
        RVR_ITERS
    );

    let cfg = tiny_river_rvr();
    // Warm up.
    let _ = solve_range_vs_range_postflop(&cfg, 1, 1.5, 0.0, 2.0).unwrap();

    let mut runs_ns: Vec<f64> = Vec::with_capacity(NUM_RUNS);
    let mut decision_nodes: u32 = 0;
    let mut strategy_entries: u32 = 0;
    for i in 0..NUM_RUNS {
        let started = Instant::now();
        let out = solve_range_vs_range_postflop(&cfg, RVR_ITERS, 1.5, 0.0, 2.0).unwrap();
        let elapsed = started.elapsed();
        let ns = elapsed.as_nanos() as f64;
        runs_ns.push(ns);
        decision_nodes = out.decision_node_count;
        strategy_entries = out.strategy_entry_count;
        println!(
            "  run {}/{}: {:.3} s  ({:.3} ms/iter, {} decision nodes, {} strategy entries)",
            i + 1,
            NUM_RUNS,
            ns / 1e9,
            ns / RVR_ITERS as f64 / 1e6,
            decision_nodes,
            strategy_entries
        );
    }

    runs_ns.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let median = runs_ns[runs_ns.len() / 2];
    let per_iter_median = median / RVR_ITERS as f64;
    println!(
        "\nMedian: {:.3} s total ({:.3} ms/iter)",
        median / 1e9,
        per_iter_median / 1e6
    );

    println!("\n--- JSON ---");
    println!("{{");
    println!("  \"workload\": \"river_rvr_1081_hands_5iters\",");
    println!("  \"iters\": {},", RVR_ITERS);
    println!("  \"runs\": [");
    for (i, ns) in runs_ns.iter().enumerate() {
        let comma = if i + 1 < runs_ns.len() { "," } else { "" };
        println!("    {:.1}{}", ns, comma);
    }
    println!("  ],");
    println!("  \"median_total_ns\": {:.1},", median);
    println!("  \"median_per_iter_ns\": {:.1},", per_iter_median);
    println!("  \"decision_node_count\": {},", decision_nodes);
    println!("  \"strategy_entry_count\": {}", strategy_entries);
    println!("}}");
}
