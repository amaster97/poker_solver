//! Phase A.1 — precompute the 169x169 preflop equity table.
//!
//! Modes:
//!   - `--mode exhaustive` (default): exact C(48, 5) enumeration per cell.
//!     Wall time on M4 Pro (10 threads) ~2 hours.
//!   - `--mode mc --samples N`: Monte Carlo with `N` random run-outs per
//!     cell. Default `N = 100000`. Wall time on M4 Pro (10 threads) ~4 min.
//!     Sampling error ~sqrt(0.25/N) ≈ 0.0016 stddev per cell at N=100K.
//!
//! Run with:
//!
//! ```bash
//! cargo run --release --manifest-path crates/cfr_core/Cargo.toml \
//!     --example build_preflop_equity -- \
//!     --out assets/preflop_equity_169x169.npz [--mode mc --samples 100000]
//! ```
//!
//! Emits a compressed `.npz` containing one array `equity` of shape
//! `(169, 169, 3)` with `f64` entries.

use std::env;
use std::path::PathBuf;
use std::time::Instant;

use cfr_core::preflop_equity::{
    build_full_equity_table_monte_carlo, build_full_equity_table_parallel, save_equity_table,
};

fn main() {
    let mut out_path = PathBuf::from("assets/preflop_equity_169x169.npz");
    let mut mode = "exhaustive".to_string();
    let mut samples: usize = 100_000;
    let mut threads: usize = std::thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(8);

    let args: Vec<String> = env::args().skip(1).collect();
    let mut i = 0usize;
    while i < args.len() {
        match args[i].as_str() {
            "--out" => {
                i += 1;
                out_path = PathBuf::from(&args[i]);
            }
            "--mode" => {
                i += 1;
                mode = args[i].clone();
            }
            "--samples" => {
                i += 1;
                samples = args[i].parse().expect("--samples must be a usize");
            }
            "--threads" => {
                i += 1;
                threads = args[i].parse().expect("--threads must be a usize");
            }
            "--help" | "-h" => {
                eprintln!(
                    "usage: build_preflop_equity [--out PATH] [--mode {{exhaustive|mc}}] [--samples N] [--threads N]"
                );
                return;
            }
            arg if !arg.starts_with("--") && i == 0 => {
                // Positional: treat as output path.
                out_path = PathBuf::from(arg);
            }
            other => panic!("unknown arg: {other}"),
        }
        i += 1;
    }

    eprintln!("[build_preflop_equity] starting full 169x169x3 build...");
    eprintln!("[build_preflop_equity] output -> {}", out_path.display());
    eprintln!("[build_preflop_equity] mode   -> {mode}");
    eprintln!("[build_preflop_equity] threads-> {threads}");
    if mode == "mc" {
        eprintln!("[build_preflop_equity] samples-> {samples}");
    }

    let started = Instant::now();
    let table = match mode.as_str() {
        "exhaustive" => build_full_equity_table_parallel(threads),
        "mc" => build_full_equity_table_monte_carlo(threads, samples),
        other => panic!("--mode must be 'exhaustive' or 'mc', got '{other}'"),
    };
    let elapsed = started.elapsed();
    eprintln!(
        "[build_preflop_equity] build done in {:.1}s (={:.1}m)",
        elapsed.as_secs_f64(),
        elapsed.as_secs_f64() / 60.0
    );

    let nan_count = table.iter().filter(|v| v.is_nan()).count();
    let total_cells = 169usize * 169 * 3;
    eprintln!(
        "[build_preflop_equity] {nan_count} / {total_cells} NaN cells \
         (geometrically-impossible suit overlaps)"
    );

    if let Some(parent) = out_path.parent() {
        std::fs::create_dir_all(parent).ok();
    }
    save_equity_table(&out_path, &table).expect("save equity table .npz");
    let file_bytes = std::fs::metadata(&out_path)
        .map(|m| m.len())
        .unwrap_or(0);
    eprintln!(
        "[build_preflop_equity] wrote {} ({} KB)",
        out_path.display(),
        file_bytes / 1024
    );
}
