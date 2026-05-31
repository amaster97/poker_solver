//! v1.10 flop-subgame inner-kernel benchmark (task #70).
//!
//! Criterion-style measurement of the postflop vector-form CFR engine
//! on the canonical v1.10 fixture: J7o A♦8♥9♦ 40 BB. We measure the
//! Rust inner kernel directly (skip the Python blueprint/continuation
//! plumbing) so the bench reports the engine's wall-clock without
//! amortized one-time setup.
//!
//! Methodology (criterion-aligned, no external dep)
//! ------------------------------------------------
//! - Each ``(top_k, iterations)`` cell runs:
//!     1. A warmup iteration (cache-prime).
//!     2. ``MEASURED_SAMPLES`` measured samples.
//!     3. Reports mean + stddev per-iter wall.
//! - Total wall = warmup_time + sum(measured). Per-iter = measured / iters.
//!
//! The repo deliberately avoids the ``criterion`` crate as a dev-dep
//! (see ``dcfr_bench.rs:9-12`` — keeps the PR diff minimal and the
//! bench self-contained). We follow criterion's measurement
//! discipline (warmup → measure → stats) using ``std::time::Instant``.
//!
//! Run with:
//! ```
//! cargo bench --bench flop_subgame_perf --manifest-path crates/cfr_core/Cargo.toml
//! ```
//!
//! With env vars:
//! ```
//! BENCH_TOP_K=4,15,50 BENCH_ITERS=200 BENCH_STREET=flop cargo bench --bench flop_subgame_perf
//! ```
//!
//! Default matrix: ``top_k ∈ {4, 15}`` × ``iters = 5`` × ``street = river``.
//! The default is intentionally small so the bench builds today (pre-v1.10
//! optimizations) without OOM-killing on flop top_k=169. The final
//! benchmark agent at v1.10 close-out will run the canonical
//! ``top_k ∈ {4, 15, 50, 169} × iters = 200 × street = flop``.

use std::time::Instant;

use cfr_core::dcfr_vector::solve_range_vs_range_postflop_with_hands;
use cfr_core::hunl::{HUNLConfig, Street};

// ---------------------------------------------------------------------------
// Fixture: J7o A♦8♥9♦ 40 BB SB-opens-3bb / BB-calls.
//
// We bypass the Python blueprint/continuation derive and feed an explicit
// hand list to the engine — the bench's purpose is to measure the inner
// kernel, not the orchestration cost. The hand list is a top-K-by-hand
// selection from the canonical 1326 board-feasible combos. Per the v1.10
// plan, top_k truncation is via ``hero_classes`` / ``villain_classes``;
// at the Rust kernel layer we pass the resulting concrete hole-pair list.
// ---------------------------------------------------------------------------

/// Card encoding: ``rank * 4 + suit``, with ``rank ∈ 2..=14`` and
/// ``suit ∈ {0=s, 1=h, 2=d, 3=c}`` (matches ``hunl::card_to_int``).
fn card(rank: u8, suit: u8) -> u8 {
    rank * 4 + suit
}

/// Default canonical board prefix: A♦ 8♥ 9♦ (flop). Turn appends 2♣;
/// river appends 3♠ (matches ``run_j7o_walkthrough.py``).
fn canonical_board(street: &str) -> Vec<u8> {
    let flop = vec![
        card(14, 2), // Ad
        card(8, 1),  // 8h
        card(9, 2),  // 9d
    ];
    let turn_card = card(2, 3); // 2c
    let river_card = card(3, 0); // 3s
    match street {
        "flop" => flop,
        "turn" => {
            let mut b = flop;
            b.push(turn_card);
            b
        }
        "river" => {
            let mut b = flop;
            b.push(turn_card);
            b.push(river_card);
            b
        }
        _ => panic!("invalid street {street:?}"),
    }
}

/// Build a HUNLConfig for the J7o 40 BB flop/turn/river subgame.
///
/// 40 BB stack = 4000 chips at 100 chips/BB. Post SB-opens-3bb /
/// BB-calls, the pot is 600 chips and each player has contributed 300.
fn build_subgame_config(street: &str) -> HUNLConfig {
    let starting_street = match street {
        "flop" => Street::Flop,
        "turn" => Street::Turn,
        "river" => Street::River,
        _ => panic!("invalid street {street:?}"),
    };
    HUNLConfig {
        starting_stack: 4000,
        small_blind: 50,
        big_blind: 100,
        ante: 0,
        starting_street,
        initial_board: canonical_board(street),
        initial_pot: 600,
        initial_contributions: [300, 300],
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
        ..Default::default()
    }
}

/// Build a hand list of ``n_per_player`` board-disjoint combos per
/// player. Mirrors the v1.10 top_k truncation: by enumerating all
/// 1081-board-feasible combos and taking the first N. (The actual
/// harness pulls per-class top-K from the blueprint's reach
/// distribution; this Rust bench uses a positionally-stable approximation
/// for kernel-only timing.)
fn build_hand_lists(
    board: &[u8],
    n_per_player: usize,
) -> ([Vec<[u8; 2]>; 2], usize) {
    let mut held = [false; 64];
    for &c in board {
        held[c as usize] = true;
    }
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
    (([selected.clone(), selected]), actual)
}

// ---------------------------------------------------------------------------
// Per-cell measurement.
// ---------------------------------------------------------------------------

/// Aggregate timing stats for one cell (top_k × iters × street).
#[derive(Debug, Clone)]
struct CellMeasurement {
    top_k: usize,
    iters: u32,
    street: String,
    mean_per_iter_s: f64,
    stddev_per_iter_s: f64,
    total_wall_s: f64,
    decision_node_count: u32,
    actual_n_hands: usize,
}

fn measure_one_cell(
    top_k: usize,
    iters: u32,
    street: &str,
    samples: usize,
) -> CellMeasurement {
    let config = build_subgame_config(street);
    let (hand_lists, actual_n) = build_hand_lists(&config.initial_board, top_k);

    // Warmup — populate cache, get the OS allocator into steady state.
    let _ = solve_range_vs_range_postflop_with_hands(
        &config,
        Some(hand_lists.clone()),
        iters,
        1.5,
        0.0,
        2.0,
        0.0,
        0,
        None,
    )
    .expect("warmup solve failed");

    // Measured samples.
    let mut per_sample_secs: Vec<f64> = Vec::with_capacity(samples);
    let mut last_decision_nodes: u32 = 0;
    for _ in 0..samples {
        let started = Instant::now();
        let out = solve_range_vs_range_postflop_with_hands(
            &config,
            Some(hand_lists.clone()),
            iters,
            1.5,
            0.0,
            2.0,
            0.0,
            0,
            None,
        )
        .expect("measured solve failed");
        let elapsed = started.elapsed().as_secs_f64();
        per_sample_secs.push(elapsed);
        last_decision_nodes = out.decision_node_count;
    }

    let mean = per_sample_secs.iter().sum::<f64>() / samples as f64;
    let variance = per_sample_secs
        .iter()
        .map(|x| (x - mean).powi(2))
        .sum::<f64>()
        / (samples.max(1) as f64);
    let stddev = variance.sqrt();
    let total = per_sample_secs.iter().sum::<f64>();
    let per_iter_mean = mean / iters as f64;
    let per_iter_stddev = stddev / iters as f64;

    CellMeasurement {
        top_k,
        iters,
        street: street.to_string(),
        mean_per_iter_s: per_iter_mean,
        stddev_per_iter_s: per_iter_stddev,
        total_wall_s: total,
        decision_node_count: last_decision_nodes,
        actual_n_hands: actual_n,
    }
}

// ---------------------------------------------------------------------------
// CLI: parse BENCH_TOP_K / BENCH_ITERS / BENCH_STREET / BENCH_SAMPLES.
// ---------------------------------------------------------------------------

fn parse_csv_usize(env_key: &str, default: &[usize]) -> Vec<usize> {
    match std::env::var(env_key) {
        Ok(v) => v
            .split(',')
            .filter_map(|s| s.trim().parse::<usize>().ok())
            .collect(),
        Err(_) => default.to_vec(),
    }
}

fn parse_env_u32(env_key: &str, default: u32) -> u32 {
    std::env::var(env_key)
        .ok()
        .and_then(|s| s.parse::<u32>().ok())
        .unwrap_or(default)
}

fn parse_env_usize(env_key: &str, default: usize) -> usize {
    std::env::var(env_key)
        .ok()
        .and_then(|s| s.parse::<usize>().ok())
        .unwrap_or(default)
}

fn parse_env_string(env_key: &str, default: &str) -> String {
    std::env::var(env_key).unwrap_or_else(|_| default.to_string())
}

// ---------------------------------------------------------------------------
// Main: drive the matrix + render the table.
// ---------------------------------------------------------------------------

fn main() {
    // Default smoke matrix — small enough that the bench builds today
    // without OOM-killing on flop top_k=169. The final v1.10 close-out
    // run will override via env vars: BENCH_TOP_K=4,15,50,169
    // BENCH_ITERS=200 BENCH_STREET=flop.
    let top_k_vals = parse_csv_usize("BENCH_TOP_K", &[4, 15]);
    let iters = parse_env_u32("BENCH_ITERS", 5);
    let street = parse_env_string("BENCH_STREET", "river");
    let samples = parse_env_usize("BENCH_SAMPLES", 3);

    println!("=== v1.10 flop_subgame_perf bench (task #70) ===");
    println!("Fixture: J7o A♦8♥9♦ 40 BB, SB-opens-3bb / BB-calls");
    println!("Matrix:  top_k={top_k_vals:?} iters={iters} street={street}");
    println!("Samples per cell: {samples} (1 warmup + {samples} measured)");
    println!();

    let mut measurements: Vec<CellMeasurement> = Vec::new();
    for &top_k in &top_k_vals {
        println!(
            "[measuring] top_k={top_k} iters={iters} street={street} ..."
        );
        let m = measure_one_cell(top_k, iters, &street, samples);
        println!(
            "[done]       top_k={top_k:>4} actual_hands={:>4} \
             total={:>6.2}s mean_per_iter={:>7.3}s ± {:>5.3}s",
            m.actual_n_hands, m.total_wall_s, m.mean_per_iter_s, m.stddev_per_iter_s
        );
        measurements.push(m);
    }

    println!();
    println!("=== Summary (criterion-style stats) ===");
    println!(
        "| street | top_k | n_hands | iters | mean/iter (s) | stddev/iter (s) | total (s) | decision_nodes |"
    );
    println!(
        "|--------|-------|---------|-------|---------------|------------------|-----------|----------------|"
    );
    for m in &measurements {
        println!(
            "| {:>6} | {:>5} | {:>7} | {:>5} | {:>13.4} | {:>16.4} | {:>9.2} | {:>14} |",
            m.street,
            m.top_k,
            m.actual_n_hands,
            m.iters,
            m.mean_per_iter_s,
            m.stddev_per_iter_s,
            m.total_wall_s,
            m.decision_node_count,
        );
    }
    println!();
    println!(
        "Note: this bench measures the kernel only — Python blueprint / continuation"
    );
    println!(
        "      derive is excluded. Use scripts/run_v1_10_perf_bench.py for"
    );
    println!("      the full end-to-end harness.");
}
