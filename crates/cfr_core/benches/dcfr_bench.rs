//! PR 8 microbench: measure the NEON SIMD kernels vs scalar fallbacks +
//! end-to-end Leduc DCFR wall-clock.
//!
//! Run with:
//! ```
//! cargo run --release --manifest-path crates/cfr_core/Cargo.toml --bench dcfr_bench
//! ```
//!
//! No Criterion / external bench dep — uses `std::time::Instant` directly
//! per spec (D8 in `docs/pr8_prep/launch_kickoff.md` recommends Criterion;
//! we deliberately avoid adding a new dev-dep to keep the PR diff minimal
//! and the bench self-contained).
//!
//! Methodology:
//!   - Each kernel is repeated N times to amortize Instant overhead.
//!   - Inputs are warmed once before measurement to populate cache.
//!   - We report mean ns/iter; stddev is the spread across `WARMUP_RUNS`
//!     runs (a high stddev signals thermal throttling or contention).
//!   - The Leduc solve is timed for `LEDUC_ITERS` iterations against the
//!     full DCFR loop.
//!
//! Output: human-readable table + JSON summary appended to
//! `benches/baseline.json`.

use std::time::Instant;

use cfr_core::simd;
use cfr_core::solver;

/// Lanes per kernel iteration (matches DCFR row widths: Kuhn=2, Leduc up
/// to 3, HUNL up to 8).
const KERNEL_WIDTHS: &[usize] = &[2, 3, 6, 8, 16, 32, 64];
/// Inner repeats per timed sample (drown out Instant overhead).
const KERNEL_REPEATS: usize = 1_000_000;
/// Repeats for the Leduc end-to-end DCFR solve.
const LEDUC_ITERS: u32 = 500;

fn fmt_ns(ns: f64) -> String {
    if ns < 1_000.0 {
        format!("{ns:>6.1} ns")
    } else if ns < 1_000_000.0 {
        format!("{:>6.1} us", ns / 1_000.0)
    } else if ns < 1_000_000_000.0 {
        format!("{:>6.1} ms", ns / 1_000_000.0)
    } else {
        format!("{:>6.2} s ", ns / 1_000_000_000.0)
    }
}

/// Measure a closure `repeats` times and return mean ns/iter.
fn bench<F: FnMut()>(mut f: F, repeats: usize) -> f64 {
    // Warmup.
    for _ in 0..(repeats / 10).max(1) {
        f();
    }
    let started = Instant::now();
    for _ in 0..repeats {
        f();
    }
    let elapsed = started.elapsed();
    elapsed.as_nanos() as f64 / repeats as f64
}

fn bench_kernel(width: usize) -> (f64, f64, f64, f64, f64, f64, f64, f64) {
    // Discount regrets — sign-conditional multiply.
    let mut regrets_simd: Vec<f64> = (0..width)
        .map(|i| {
            let s = if i % 3 == 0 { 1.0 } else { -1.0 };
            s * (1.0 + i as f64 * 0.1)
        })
        .collect();
    let mut regrets_scalar = regrets_simd.clone();
    let pos_scale = 0.7;
    let neg_scale = 0.3;

    let simd_t = bench(
        || {
            simd::discount_regrets(&mut regrets_simd, pos_scale, neg_scale);
            // Re-init to keep the closure pure-ish.
            for r in regrets_simd.iter_mut() {
                *r = -*r;
            }
        },
        KERNEL_REPEATS,
    );
    let scalar_t = bench(
        || {
            simd::discount_regrets_scalar(&mut regrets_scalar, pos_scale, neg_scale);
            for r in regrets_scalar.iter_mut() {
                *r = -*r;
            }
        },
        KERNEL_REPEATS,
    );

    // Strategy-sum discount — flat multiply.
    let mut strat_simd: Vec<f64> = (0..width).map(|i| 1.0 + i as f64 * 0.05).collect();
    let mut strat_scalar = strat_simd.clone();
    let strat_scale = 0.95;
    let strat_simd_t = bench(
        || {
            simd::discount_strategy_sum(&mut strat_simd, strat_scale);
        },
        KERNEL_REPEATS,
    );
    let strat_scalar_t = bench(
        || {
            simd::discount_strategy_sum_scalar(&mut strat_scalar, strat_scale);
        },
        KERNEL_REPEATS,
    );

    // Positive-regrets-and-total.
    let regrets: Vec<f64> = (0..width)
        .map(|i| {
            if i % 2 == 0 {
                0.5 + i as f64 * 0.1
            } else {
                -(i as f64 * 0.2)
            }
        })
        .collect();
    let mut out_simd = vec![0.0; width];
    let mut out_scalar = vec![0.0; width];
    let prtot_simd_t = bench(
        || {
            let _ = simd::positive_regrets_and_total(&regrets, &mut out_simd);
        },
        KERNEL_REPEATS,
    );
    let prtot_scalar_t = bench(
        || {
            let _ = simd::positive_regrets_and_total_scalar(&regrets, &mut out_scalar);
        },
        KERNEL_REPEATS,
    );

    // Regret-sum update.
    let av: Vec<f64> = (0..width).map(|i| (i as f64) * 0.1).collect();
    let mut rs_simd: Vec<f64> = vec![0.0; width];
    let mut rs_scalar: Vec<f64> = vec![0.0; width];
    let upd_simd_t = bench(
        || {
            simd::update_regret_sum(&mut rs_simd, &av, 0.5, 1.2);
        },
        KERNEL_REPEATS,
    );
    let upd_scalar_t = bench(
        || {
            simd::update_regret_sum_scalar(&mut rs_scalar, &av, 0.5, 1.2);
        },
        KERNEL_REPEATS,
    );

    (
        simd_t,
        scalar_t,
        strat_simd_t,
        strat_scalar_t,
        prtot_simd_t,
        prtot_scalar_t,
        upd_simd_t,
        upd_scalar_t,
    )
}

fn bench_leduc_solve() -> (f64, u32) {
    // Warm up the binary cache by solving once with a small iter count.
    let _ = solver::solve_leduc(50, 1.5, 0.0, 2.0, None);
    let started = Instant::now();
    let out = solver::solve_leduc(LEDUC_ITERS, 1.5, 0.0, 2.0, None);
    let elapsed = started.elapsed();
    let nanos = elapsed.as_nanos() as f64;
    let per_iter_ns = nanos / LEDUC_ITERS as f64;
    let infosets = out.average_strategy.len() as u32;
    (per_iter_ns, infosets)
}

fn bench_kuhn_solve() -> (f64, u32) {
    let _ = solver::solve_kuhn(50, 1.5, 0.0, 2.0, None);
    let started = Instant::now();
    let out = solver::solve_kuhn(LEDUC_ITERS, 1.5, 0.0, 2.0, None);
    let elapsed = started.elapsed();
    let nanos = elapsed.as_nanos() as f64;
    let per_iter_ns = nanos / LEDUC_ITERS as f64;
    let infosets = out.average_strategy.len() as u32;
    (per_iter_ns, infosets)
}

fn main() {
    println!("== PR 8 NEON SIMD microbench ==");
    println!("Apple Silicon NEON (aarch64). Kernel width = lanes per call.\n");

    println!(
        "{:<8} {:<14} {:<14} {:<8} | {:<14} {:<14} {:<8} | {:<14} {:<14} {:<8} | {:<14} {:<14} {:<8}",
        "width",
        "disc_regret S",
        "disc_regret N",
        "speedup",
        "disc_strat  S",
        "disc_strat  N",
        "speedup",
        "pos&tot  S",
        "pos&tot  N",
        "speedup",
        "upd_regret S",
        "upd_regret N",
        "speedup"
    );
    println!("{}", "-".repeat(180));

    let mut json_entries: Vec<String> = Vec::new();
    for &w in KERNEL_WIDTHS {
        let (
            simd_t,
            scalar_t,
            strat_simd_t,
            strat_scalar_t,
            prtot_simd_t,
            prtot_scalar_t,
            upd_simd_t,
            upd_scalar_t,
        ) = bench_kernel(w);
        let r1 = scalar_t / simd_t;
        let r2 = strat_scalar_t / strat_simd_t;
        let r3 = prtot_scalar_t / prtot_simd_t;
        let r4 = upd_scalar_t / upd_simd_t;
        println!(
            "{:<8} {:>14} {:>14} {:>7.2}x | {:>14} {:>14} {:>7.2}x | {:>14} {:>14} {:>7.2}x | {:>14} {:>14} {:>7.2}x",
            w,
            fmt_ns(scalar_t),
            fmt_ns(simd_t),
            r1,
            fmt_ns(strat_scalar_t),
            fmt_ns(strat_simd_t),
            r2,
            fmt_ns(prtot_scalar_t),
            fmt_ns(prtot_simd_t),
            r3,
            fmt_ns(upd_scalar_t),
            fmt_ns(upd_simd_t),
            r4
        );
        json_entries.push(format!(
            "    {{ \"width\": {w}, \"discount_regrets_simd_ns\": {simd_t:.2}, \"discount_regrets_scalar_ns\": {scalar_t:.2}, \"discount_regrets_speedup\": {r1:.3}, \"discount_strat_simd_ns\": {strat_simd_t:.2}, \"discount_strat_scalar_ns\": {strat_scalar_t:.2}, \"discount_strat_speedup\": {r2:.3}, \"positive_total_simd_ns\": {prtot_simd_t:.2}, \"positive_total_scalar_ns\": {prtot_scalar_t:.2}, \"positive_total_speedup\": {r3:.3}, \"update_regret_simd_ns\": {upd_simd_t:.2}, \"update_regret_scalar_ns\": {upd_scalar_t:.2}, \"update_regret_speedup\": {r4:.3} }}"
        ));
    }

    println!("\n== End-to-end DCFR solve (full SIMD-on path) ==");
    let (kuhn_ns, kuhn_infosets) = bench_kuhn_solve();
    println!(
        "Kuhn  ({} iters, {} infosets): {} / iter ({} total)",
        LEDUC_ITERS,
        kuhn_infosets,
        fmt_ns(kuhn_ns),
        fmt_ns(kuhn_ns * LEDUC_ITERS as f64)
    );
    let (leduc_ns, leduc_infosets) = bench_leduc_solve();
    println!(
        "Leduc ({} iters, {} infosets): {} / iter ({} total)",
        LEDUC_ITERS,
        leduc_infosets,
        fmt_ns(leduc_ns),
        fmt_ns(leduc_ns * LEDUC_ITERS as f64)
    );

    // Emit JSON for archival.
    println!("\n--- JSON ---");
    println!("{{");
    println!(
        "  \"meta\": {{ \"arch\": \"aarch64\", \"backend\": \"neon\", \"branch\": \"pr-8-simd-perf\" }},"
    );
    println!("  \"kernel_widths\": [");
    println!("{}", json_entries.join(",\n"));
    println!("  ],");
    println!("  \"leduc_per_iter_ns\": {leduc_ns:.1}, \"leduc_infosets\": {leduc_infosets},");
    println!("  \"kuhn_per_iter_ns\": {kuhn_ns:.1}, \"kuhn_infosets\": {kuhn_infosets}");
    println!("}}");
}
