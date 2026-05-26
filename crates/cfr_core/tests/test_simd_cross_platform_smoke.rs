//! v1.8 cross-platform SIMD end-to-end smoke test.
//!
//! Per-kernel bit-identity tests already cover individual SIMD kernels
//! (`test_simd*.rs` files in flight for Phase 1 / Phase 3 / Phase 4).
//! Those tests prove that — given identical *inputs* — each kernel's
//! NEON / SSE2 / AVX2 / scalar implementations produce bit-identical
//! *outputs*. That is necessary but not sufficient: a CFR solve calls
//! the kernels thousands of times in sequence, and each iteration's
//! output is the next iteration's input. ULP-level drift in any single
//! kernel call can compound across iterations and push the converged
//! infoset values past the project's `STRATEGY_ATOL=1e-4` bar.
//!
//! This file is the **end-to-end** invariant test: run a small Kuhn
//! solve under both the auto-dispatched SIMD path (NEON on aarch64,
//! SSE2 + AVX2 on x86_64) and the scalar-only fallback, and assert that
//! every infoset's per-action probability is bit-identical (to_bits()
//! equality) across the two backends.
//!
//! # Why this test is structured around a compile-time feature
//!
//! `force_scalar` in `crates/cfr_core/Cargo.toml` is a **compile-time**
//! feature: the dispatch in `simd.rs` is `#[cfg(...)]`-gated, not
//! runtime-gated. A single test binary therefore cannot exercise BOTH
//! the scalar and the SIMD path in the same process — at compile time
//! one is selected. The cross-backend bit-identity check has to be run
//! as **two separate `cargo test` invocations**, with the outputs
//! compared by an external harness:
//!
//!   ```bash
//!   # SIMD path (default).
//!   cargo test --release -p cfr_core \
//!     --test test_simd_cross_platform_smoke smoke_kuhn_solve_dump_strategy \
//!     -- --nocapture > /tmp/kuhn_simd.txt
//!
//!   # Scalar path.
//!   cargo test --release -p cfr_core --features force_scalar \
//!     --test test_simd_cross_platform_smoke smoke_kuhn_solve_dump_strategy \
//!     -- --nocapture > /tmp/kuhn_scalar.txt
//!
//!   # Compare to_bits() lines.
//!   diff /tmp/kuhn_simd.txt /tmp/kuhn_scalar.txt
//!   ```
//!
//! The two passing tests in this file each exercise one half of that
//! check; the `#[ignore]`-gated test documents the harness need for an
//! in-process cross-backend comparison (which would require runtime
//! dispatch — out of scope for this PR; tracked as follow-up).
//!
//! # Test inventory
//!
//! - `smoke_kuhn_solve_determinism` — passing: solves Kuhn twice in
//!   the same process under the current compile-time backend, asserts
//!   bit-identical outputs. Verifies the backend is itself
//!   deterministic across runs (no thread-order or memory-order
//!   non-determinism).
//!
//! - `smoke_kuhn_solve_dump_strategy` — passing: solves Kuhn, prints
//!   each infoset's per-action `to_bits()`. Designed to be diffed
//!   across the two-invocation pattern documented above.
//!
//! - `smoke_kuhn_solve_cross_backend_in_process` — ignored: documents
//!   the in-process scalar-vs-SIMD comparison that would require
//!   runtime dispatch.

use cfr_core::solver::solve_kuhn;

/// Number of DCFR iterations for the smoke. Kuhn is tiny (12 infosets,
/// 2 actions each); 1000 iters converges to within ~1e-3 of the
/// closed-form Nash equilibrium and exercises every SIMD kernel
/// thousands of times across the discount + regret + strategy updates.
const ITERATIONS: u32 = 1000;
/// DCFR hyperparameters: paper-recommended (alpha=1.5, beta=0.0,
/// gamma=2.0). Matches `solve_kuhn`'s production defaults.
const ALPHA: f64 = 1.5;
const BETA: f64 = 0.0;
const GAMMA: f64 = 2.0;

/// Reports which backend is compiled in. Useful for log inspection
/// when this test runs in CI on multiple architectures.
//
// `clippy::needless_return` (rustc 1.95+) flags the early `return`s, but
// removing them changes semantics: each `#[cfg(...)]` block guards one
// arm and the trailing arm acts as a fallback; without `return`, an
// active early-arm value would be discarded and execution would fall
// through to the fallback block. The early-return form is the clearest
// expression of "pick the first cfg-active arm". Allow the lint here.
#[allow(clippy::needless_return)]
fn compiled_backend() -> &'static str {
    #[cfg(feature = "force_scalar")]
    {
        return "scalar";
    }
    #[cfg(all(target_arch = "aarch64", not(feature = "force_scalar")))]
    {
        return "aarch64-neon";
    }
    #[cfg(all(
        target_arch = "x86_64",
        not(target_arch = "aarch64"),
        not(feature = "force_scalar")
    ))]
    {
        return "x86_64-sse2";
    }
    #[cfg(any(
        feature = "force_scalar",
        not(any(target_arch = "aarch64", target_arch = "x86_64"))
    ))]
    #[allow(unreachable_code)]
    {
        "scalar"
    }
}

/// Solve Kuhn under the currently-compiled backend and return the
/// average-strategy infoset map. Helper used by all tests below.
fn run_kuhn_solve() -> std::collections::HashMap<String, Vec<f64>> {
    let out = solve_kuhn(ITERATIONS, ALPHA, BETA, GAMMA, None);
    out.average_strategy
}

#[test]
fn smoke_kuhn_solve_determinism() {
    // Run the same Kuhn solve twice in the same process; the
    // currently-compiled backend must produce bit-identical results
    // across runs. This is a within-backend determinism check —
    // catches thread-order / map-iteration-order / memory-order
    // non-determinism that would invalidate the cross-backend
    // comparison even if every kernel call is itself deterministic.
    eprintln!(
        "[smoke_kuhn_solve_determinism] backend={} iters={}",
        compiled_backend(),
        ITERATIONS
    );
    let first = run_kuhn_solve();
    let second = run_kuhn_solve();
    assert_eq!(
        first.len(),
        second.len(),
        "infoset count mismatch across two runs ({}->{})",
        first.len(),
        second.len()
    );
    for (key, first_v) in first.iter() {
        let second_v = second
            .get(key)
            .unwrap_or_else(|| panic!("infoset {key:?} missing from second solve"));
        assert_eq!(
            first_v.len(),
            second_v.len(),
            "infoset {key:?}: action count mismatch ({} vs {})",
            first_v.len(),
            second_v.len()
        );
        for (a, fv) in first_v.iter().enumerate() {
            let sv = second_v[a];
            assert_eq!(
                fv.to_bits(),
                sv.to_bits(),
                "infoset {key:?} action {a}: first={:e} ({:#x}) second={:e} ({:#x}) under backend={}",
                fv,
                fv.to_bits(),
                sv,
                sv.to_bits(),
                compiled_backend()
            );
        }
    }
}

#[test]
fn smoke_kuhn_solve_dump_strategy() {
    // Print the average-strategy in a deterministic, diff-friendly
    // format. To run the cross-backend comparison:
    //
    //   cargo test --release -p cfr_core \
    //     --test test_simd_cross_platform_smoke \
    //     smoke_kuhn_solve_dump_strategy -- --nocapture --include-ignored=false \
    //     > /tmp/kuhn_simd.txt
    //
    //   cargo test --release -p cfr_core --features force_scalar \
    //     --test test_simd_cross_platform_smoke \
    //     smoke_kuhn_solve_dump_strategy -- --nocapture --include-ignored=false \
    //     > /tmp/kuhn_scalar.txt
    //
    //   diff <(grep '^STRAT ' /tmp/kuhn_simd.txt | sort) \
    //        <(grep '^STRAT ' /tmp/kuhn_scalar.txt | sort)
    //
    // Empty diff = bit-identical end-to-end across backends.
    let strategy = run_kuhn_solve();
    let mut keys: Vec<&String> = strategy.keys().collect();
    keys.sort();
    eprintln!("BACKEND {}", compiled_backend());
    for key in keys {
        let probs = &strategy[key];
        let mut line = format!("STRAT {key}");
        for p in probs {
            // Print the to_bits() hex so the diff is exact.
            line.push_str(&format!(" {:#018x}", p.to_bits()));
        }
        eprintln!("{line}");
    }
    // Sanity floor: Kuhn has 12 infosets (each player × 6 information
    // states: 3 cards × {root, post-pass, post-bet}; not all reachable
    // for each card). DCFR-1000 should populate them all.
    assert!(
        strategy.len() >= 6,
        "Kuhn solve produced only {} infosets — expected >= 6",
        strategy.len()
    );
}

/// Documents the in-process cross-backend test that's blocked on a
/// runtime-dispatch harness. `force_scalar` is compile-time only, so
/// this test cannot be expressed today; tracked as a follow-up.
///
/// To enable: thread a `Backend` enum (Scalar / Neon / Sse2 / Avx2)
/// through the public dispatch entry points in `simd.rs`, so a single
/// test binary can call both paths in the same process.
#[test]
#[ignore = "needs runtime-dispatch harness — force_scalar is compile-time only; \
            see two-invocation pattern in smoke_kuhn_solve_dump_strategy"]
fn smoke_kuhn_solve_cross_backend_in_process() {
    // Sketch (post-harness):
    //
    // let scalar = run_kuhn_solve_with_backend(Backend::Scalar);
    // let simd   = run_kuhn_solve_with_backend(Backend::Auto);
    // for (k, scalar_v) in scalar.iter() {
    //     let simd_v = simd.get(k).expect("missing infoset under SIMD");
    //     for (a, sv) in scalar_v.iter().enumerate() {
    //         assert_eq!(
    //             sv.to_bits(), simd_v[a].to_bits(),
    //             "infoset {k} action {a}: scalar={sv:e} simd={:e}", simd_v[a],
    //         );
    //     }
    // }
    unreachable!("requires runtime-dispatch harness — see #[ignore] message");
}
