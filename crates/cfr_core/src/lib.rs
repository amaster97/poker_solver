//! `poker_solver._rust` — PyO3 extension exposing the Rust DCFR production tier.
//!
//! The Python reference tier (`poker_solver/dcfr.py`) is the ground truth;
//! this crate is a structural port for performance. The differential test
//! (`tests/test_dcfr_diff.py`) keeps the two implementations in lockstep.

use std::collections::HashMap;

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;

// v1.8.1: `dcfr` is `pub` so the alpha-guard integration test
// (`tests/test_dcfr_alpha_guard.rs`) can reach `dcfr::validate_alpha`.
// The module's public API was already implicitly used by the sibling
// modules `preflop`, `dcfr_vector`, `hunl_solver` via `crate::dcfr::...`.
pub mod dcfr;
mod game;
mod kuhn;
mod leduc;
// `solver` is `pub` so the PR 8 microbench in `benches/dcfr_bench.rs` can
// drive `solve_kuhn` / `solve_leduc` end-to-end for wall-clock timing.
pub mod solver;

// PR 6 — HUNL Rust production tier (Agent A's modules + Agent B's pipeline).
// All modules are `pub` so integration tests (`crates/cfr_core/tests/*.rs`)
// can reach them across the crate boundary.
pub mod abstraction;
pub mod hunl;
pub mod hunl_eval;
pub mod hunl_solver;
pub mod hunl_tree;

// PR 8 — NEON SIMD kernels + cache-blocked infoset layout + public chance
// sampling. SIMD/layout/PCS are `pub` so the microbench in
// `crates/cfr_core/benches/dcfr_bench.rs` can exercise them directly without
// going through the full CFR loop.
pub mod layout;
pub mod pcs;
pub mod simd;

// PR 9 — HUNL preflop solver (subgame mode with equity-leaf substitution).
pub mod preflop;

// PR 15 — HUNL exploitability + game-value walks. Range-vs-range solves
// (`initial_hole_cards = ()`) bottleneck on the post-solve Python tree
// walk; this module ports it to Rust with the same recursive shape and
// float semantics so the diff test against `poker_solver.solver.exploitability`
// stays bit-for-bit close.
pub mod exploit;

// PR 23 — Vector-form DCFR for true range-vs-range Nash. Extends PR 15's
// flat-tree machinery to the write side (regret + strategy updates) using
// Brown's `references/code/noambrown_poker_solver/cpp/src/trainer.cpp`
// (MIT) `Trainer::traverse` pattern. Opt-in via the
// `solve_range_vs_range_rust` PyO3 entry; existing scalar DCFR paths
// (Kuhn, Leduc, fixed-combo HUNL postflop/preflop) are unchanged.
pub mod dcfr_vector;

// v1.10 PR-4 — Opt-in Rayon multi-threading for the postflop chance
// subtree. Activated by `CFR_RAYON_CHANCE=1` at solve entry. Default
// (env var unset) is bit-identical to pre-PR-4. See module docstring
// for the safety / concurrency model.
pub mod dcfr_vector_parallel;

// v1.10 PR-1 — thread-local bump arena for `dcfr_vector::traverse_*`
// scratch buffers. Replaces per-call `vec![0.0_f64; N]` allocations
// with LIFO-disciplined slots in a single reusable `Vec<f64>` (per
// worker thread). Safe Rust (no `unsafe`); see `arena.rs` module
// docs for the invariant + API.
pub mod arena;

// Phase A (full-tree preflop RvR) — preflop 169x169 equity leaf table
// (`preflop_equity`) and the vector-form preflop solver driver
// (`preflop_rvr`). The equity table is precomputed once via
// `examples/build_preflop_equity.rs` and shipped as
// `assets/preflop_equity_169x169.npz`; the solver loads it at runtime and
// uses it to collapse the postflop chance subtree into a constant equity
// leaf per (hero_class, villain_class, suit_variant).
pub mod preflop_equity;
pub mod preflop_rvr;

use crate::solver::SolveOutput;

/// Build-time version smoke check.
#[pyfunction]
fn _version() -> &'static str {
    "0.2.0"
}

/// Convert a `SolveOutput` to the Python dict shape returned by `solve_*`.
fn solve_output_to_py(py: Python<'_>, out: SolveOutput) -> PyResult<PyObject> {
    let dict = PyDict::new(py);
    let strat = PyDict::new(py);
    for (key, probs) in &out.average_strategy {
        strat.set_item(key, probs.clone())?;
    }
    dict.set_item("average_strategy", strat)?;
    dict.set_item("exploitability", out.exploitability)?;
    dict.set_item("game_value", out.game_value)?;
    dict.set_item("iterations", out.iterations)?;
    Ok(dict.into())
}

/// Run the full Kuhn DCFR solve and return the bundled outputs as a Python dict.
///
/// Keys:
///   - `average_strategy`: `dict[str, list[float]]` — infoset → probs per action
///   - `exploitability`: float
///   - `game_value`: float (player 0's expected value)
///   - `iterations`: int
///
/// v1.4: optional `locked_strategies` parameter pins specific infoset
/// strategies (node-locking).
#[pyfunction]
#[pyo3(signature = (
    iterations,
    alpha,
    beta,
    gamma,
    locked_strategies=None,
))]
fn solve_kuhn(
    py: Python<'_>,
    iterations: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
    locked_strategies: Option<HashMap<String, Vec<f64>>>,
) -> PyResult<PyObject> {
    // Wrap solver invocation in `catch_unwind` so locked-strategy
    // validation panics surface as PyValueError instead of aborting the
    // Python interpreter (PyO3's default unwind-panic-from-Rust is an
    // abort in release builds with `panic = "abort"`, and a hang in
    // debug; catching here keeps the API surface predictable).
    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        solver::solve_kuhn(iterations, alpha, beta, gamma, locked_strategies)
    }));
    match result {
        Ok(out) => solve_output_to_py(py, out),
        Err(payload) => Err(PyValueError::new_err(panic_message(&payload))),
    }
}

/// Run the full Leduc DCFR solve. Same dict shape as `solve_kuhn`.
///
/// Leduc has 288 infosets (6-card deck collapsed by rank, two betting rounds);
/// per-infoset action vectors are 1–3 wide depending on betting context.
#[pyfunction]
#[pyo3(signature = (
    iterations,
    alpha,
    beta,
    gamma,
    locked_strategies=None,
))]
fn solve_leduc(
    py: Python<'_>,
    iterations: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
    locked_strategies: Option<HashMap<String, Vec<f64>>>,
) -> PyResult<PyObject> {
    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        solver::solve_leduc(iterations, alpha, beta, gamma, locked_strategies)
    }));
    match result {
        Ok(out) => solve_output_to_py(py, out),
        Err(payload) => Err(PyValueError::new_err(panic_message(&payload))),
    }
}

/// Extract a String from a `catch_unwind` payload (panic message).
fn panic_message(payload: &Box<dyn std::any::Any + Send>) -> String {
    if let Some(s) = payload.downcast_ref::<String>() {
        s.clone()
    } else if let Some(s) = payload.downcast_ref::<&'static str>() {
        s.to_string()
    } else {
        "Rust panic with non-string payload".to_string()
    }
}

/// HUNL postflop solve entry exposed to Python as `_rust.solve_hunl_postflop`.
///
/// PR 6 boundary — JSON-string config marshalling (D2: simpler than struct
/// binding; ~50 LOC of `serde::Deserialize` on the Rust side). The Rust solve
/// runs under `py.allow_threads(...)` so multi-call scenarios (UI thread vs
/// solver thread) don't deadlock on the GIL.
///
/// Per D5, the returned `exploitability` and `game_value` are always `0.0`;
/// the Python wrapper recomputes them from the average strategy to remove
/// cross-tier float drift.
///
/// Arguments:
///   - `config_json`: serialized `HUNLConfig` (matches `serde::Deserialize`
///     shape — Python emits via `_serialize_hunl_config(config)` in
///     `poker_solver/hunl.py`).
///   - `abstraction_path`: optional path to PR 4's `.npz` artifact; `None`
///     runs in lossless mode (PR 5 §4 Stage B fallback).
///   - `iterations`, `alpha`, `beta`, `gamma`: DCFR hyperparameters.
///   - `target_exploitability`: optional early-exit threshold (not wired
///     into the generic `DCFRSolver<G>` in PR 6; reserved for PR 8).
///   - `seed`: optional deterministic seed (forward-compat; vanilla DCFR is
///     deterministic given identical iteration order).
#[pyfunction]
#[pyo3(signature = (
    config_json,
    abstraction_path,
    iterations,
    alpha,
    beta,
    gamma,
    target_exploitability=None,
    seed=None,
    locked_strategies=None,
    regret_init_noise=0.0,
    rng_seed=0,
))]
#[allow(clippy::too_many_arguments)]
fn solve_hunl_postflop(
    py: Python<'_>,
    config_json: &str,
    abstraction_path: Option<&str>,
    iterations: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
    target_exploitability: Option<f64>,
    seed: Option<u64>,
    locked_strategies: Option<HashMap<String, Vec<f64>>>,
    regret_init_noise: f64,
    rng_seed: u64,
) -> PyResult<PyObject> {
    // GIL-bound prep (cheap): deserialize config + load abstraction. We can't
    // hold `Option<&AbstractionTables>` across `allow_threads` because the
    // borrow would tie back to a value created inside the closure; instead
    // we own the table and pass a reference into the closure.
    let config: hunl::HUNLConfig = serde_json::from_str(config_json)
        .map_err(|e| PyValueError::new_err(format!("invalid HUNLConfig JSON: {e}")))?;
    let abstraction: Option<abstraction::AbstractionTables> = match abstraction_path {
        Some(p) => Some(
            abstraction::load_abstraction(std::path::Path::new(p))
                .map_err(|e| PyValueError::new_err(format!("{e}")))?,
        ),
        None => None,
    };

    // Release the GIL for the duration of the pure-Rust DCFR loop. Critical
    // to avoid GIL contention with the calling Python thread (spec §9 #11).
    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        py.allow_threads(|| {
            hunl_solver::solve_hunl_postflop(
                &config,
                abstraction.as_ref(),
                iterations,
                alpha,
                beta,
                gamma,
                target_exploitability,
                seed,
                locked_strategies,
                regret_init_noise,
                rng_seed,
            )
        })
    }));
    let result = result.map_err(|payload| PyValueError::new_err(panic_message(&payload)))?;
    let out = result.map_err(|e| PyValueError::new_err(format!("{e}")))?;

    // Marshal the output back into a Python dict matching the existing
    // `solve_kuhn` / `solve_leduc` PyO3 shape, with PR 6-specific extras.
    let dict = PyDict::new(py);
    let strat = PyDict::new(py);
    for (key, probs) in &out.average_strategy {
        strat.set_item(key, probs.clone())?;
    }
    dict.set_item("average_strategy", strat)?;
    dict.set_item("exploitability", out.exploitability)?;
    dict.set_item("game_value", out.game_value)?;
    dict.set_item("iterations", out.iterations)?;
    dict.set_item("wallclock_seconds", out.wallclock_seconds)?;
    dict.set_item("infoset_count", out.infoset_count)?;
    dict.set_item("backend", "rust")?;
    Ok(dict.into())
}

/// PR 9 — HUNL preflop subgame solve entry exposed to Python as
/// `_rust.solve_hunl_preflop`.
///
/// Mirrors the PR 6 `solve_hunl_postflop` shape: JSON-string config in,
/// dict out. No abstraction parameter (preflop infoset keys are always
/// lossless; PR 4 §7.12 decision).
///
/// Per D5, the returned `exploitability` and `game_value` are always `0.0`;
/// the Python wrapper recomputes them from the average strategy via the
/// reference tier (`poker_solver.solver.exploitability` / `_game_value`).
#[pyfunction]
#[pyo3(signature = (
    config_json,
    iterations,
    alpha,
    beta,
    gamma,
    target_exploitability=None,
    seed=None,
    locked_strategies=None,
))]
#[allow(clippy::too_many_arguments)]
fn solve_hunl_preflop(
    py: Python<'_>,
    config_json: &str,
    iterations: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
    target_exploitability: Option<f64>,
    seed: Option<u64>,
    locked_strategies: Option<HashMap<String, Vec<f64>>>,
) -> PyResult<PyObject> {
    let config: hunl::HUNLConfig = serde_json::from_str(config_json)
        .map_err(|e| PyValueError::new_err(format!("invalid HUNLConfig JSON: {e}")))?;

    // Release the GIL during the pure-Rust DCFR loop.
    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        py.allow_threads(|| {
            preflop::solve_hunl_preflop(
                &config,
                iterations,
                alpha,
                beta,
                gamma,
                target_exploitability,
                seed,
                locked_strategies,
            )
        })
    }));
    let result = result.map_err(|payload| PyValueError::new_err(panic_message(&payload)))?;
    let out = result.map_err(|e| PyValueError::new_err(format!("{e}")))?;

    let dict = PyDict::new(py);
    let strat = PyDict::new(py);
    for (key, probs) in &out.average_strategy {
        strat.set_item(key, probs.clone())?;
    }
    dict.set_item("average_strategy", strat)?;
    dict.set_item("exploitability", out.exploitability)?;
    dict.set_item("game_value", out.game_value)?;
    dict.set_item("iterations", out.iterations)?;
    dict.set_item("wallclock_seconds", out.wallclock_seconds)?;
    dict.set_item("infoset_count", out.infoset_count)?;
    dict.set_item("backend", "rust")?;
    Ok(dict.into())
}

/// PR 15 — HUNL exploitability + P0 game-value computed from a Python
/// strategy dict, exposed to Python as `_rust.compute_exploitability`.
///
/// Mirrors the Python reference walk in `poker_solver.solver.exploitability`
/// / `poker_solver.solver._game_value`: best-response per player + on-strategy
/// expected value, recombined into the standard NashConv-style
/// exploitability metric for zero-sum two-player games (mean over players of
/// `BR_value - on_strategy_value`).
///
/// Built for the v1.3 range-vs-range solve path: when the config has
/// `initial_hole_cards = None`, the Rust walk enumerates the C(52,2) *
/// C(50,2) ≈ 1.3M hand-pairs at the root and dispatches each combo into
/// the existing HUNL state machine. This is the perf-critical pathway that
/// the Python equivalent could not complete in a reasonable wall-clock.
///
/// Arguments:
///   - `config_json`: serialized `HUNLConfig` (same shape as the existing
///     `solve_hunl_postflop` PyO3 entry — see `_serialize_hunl_config` in
///     `poker_solver/hunl.py`).
///   - `strategy`: `dict[str, list[float]]` — infoset key → action prob
///     vector. Mirrors the Python `solver.average_strategy()` output.
///
/// Returns: `dict` with keys `"exploitability"` (float) and `"game_value"`
/// (float). The caller (`poker_solver.solver._solve_rust`) inserts these
/// into the `SolveResult` directly.
#[pyfunction]
#[pyo3(signature = (config_json, strategy))]
fn compute_exploitability(
    py: Python<'_>,
    config_json: &str,
    strategy: &Bound<'_, PyDict>,
) -> PyResult<PyObject> {
    let config: hunl::HUNLConfig = serde_json::from_str(config_json)
        .map_err(|e| PyValueError::new_err(format!("invalid HUNLConfig JSON: {e}")))?;

    // Marshal the Python `{infoset_key: [probs]}` dict into an owned Rust
    // HashMap. We need to extract every entry under the GIL before we drop
    // it to call into the pure-Rust walk.
    let mut strategy_map: std::collections::HashMap<String, Vec<f64>> =
        std::collections::HashMap::with_capacity(strategy.len());
    for (k, v) in strategy.iter() {
        let key: String = k
            .extract()
            .map_err(|e| PyValueError::new_err(format!("strategy key must be str: {e}")))?;
        let probs: Vec<f64> = v.extract().map_err(|e| {
            PyValueError::new_err(format!(
                "strategy value for key {key:?} must be list[float]: {e}"
            ))
        })?;
        strategy_map.insert(key, probs);
    }

    // Release the GIL for the pure-Rust walk. The exploitability tree walk
    // is CPU-bound and does no Python callbacks, so dropping the GIL is
    // safe + maximizes throughput on multi-threaded callers.
    let out =
        py.allow_threads(|| exploit::compute_exploitability_and_value(&config, &strategy_map));

    let dict = PyDict::new(py);
    dict.set_item("exploitability", out.exploitability)?;
    dict.set_item("game_value", out.game_value)?;
    Ok(dict.into())
}

/// PR 23 — Vector-form DCFR for true range-vs-range Nash solves, exposed
/// to Python as `_rust.solve_range_vs_range_rust`.
///
/// Mirrors the `solve_hunl_postflop` PyO3 shape (JSON config in, dict out)
/// but takes the `initial_hole_cards = None` path and walks Brown's
/// vector-form CFR through the betting tree (see
/// `crates/cfr_core/src/dcfr_vector.rs` module docs for the load-bearing
/// references).
///
/// **v1.5.0 scope (spec §8 Q2):** postflop only — Flop / Turn / River with
/// the full 1326-collapsed-by-board hand vector per player. Preflop and
/// EMD bucketing are v1.5.1.
///
/// Arguments:
///   - `config_json`: serialized `HUNLConfig` (Python emits via
///     `_serialize_hunl_config` in `poker_solver/hunl.py`).
///   - `iterations`, `alpha`, `beta`, `gamma`: DCFR hyperparameters.
///
/// Returns: dict with
///   - `average_strategy`: `dict[str, list[float]]` — `<hole_string>|<key_suffix>`
///     per-(infoset, hand) row, mirroring the lossless Python format
///     `HUNLState.infoset_key(player, abstraction=None)`.
///   - `iterations`, `wallclock_seconds`, `decision_node_count`,
///     `hand_count_per_player`, `backend = "rust_vector"`.
///
/// Q3 default (spec §8): Python's `solve_range_vs_range` aggregator is NOT
/// rewired to this entrypoint in v1.5.0 — the binding stands alone for
/// downstream code (and v1.5.1) to wire in.
///
/// # Performance note (post-PR-114, currently held for review)
///
/// This entrypoint walks the full 1326-collapsed-by-board hand pair grid
/// each iteration; cost scales O(hand_count² × decision_nodes). PR #114
/// added a `TerminalCache` that precomputes per-player `Strength` vectors
/// at each Showdown leaf and constant chip-flow payoffs at each Fold leaf
/// (amortized once per solve), cutting the dominant `evaluate_7` cost on a
/// constant board. On the same river fixture used for the original HIGH-2
/// framing, measured per-iteration cost dropped from ~28.62 s to ~0.134 s
/// (~213× speedup); a 200-iter run is now ~27 s and the 500-iter default
/// is ~67 s wall time (1 CPU at 100%). `TerminalCache` is enabled by
/// default; set `CFR_VECTOR_NO_TERMINAL_CACHE=1` to route through the
/// uncached path for parity comparisons.
///
/// **Flop and turn may still be slow.** The cache helps river the most
/// because the board is constant; flop has more chance-tree branching,
/// so the O(N²) hand-pair shape still dominates and per-iter cost is not
/// yet measured at the same precision.
///
/// **For one-shot 13×13 lookups,** the Python `solve_range_vs_range`
/// aggregator (Pluribus-blueprint) is still faster — the gap is now
/// roughly 5–20× rather than the pre-cache 10–100× — but true Nash via
/// this binding is now usable for interactive workflows on river. Direct
/// `_rust` callers must class-trim before invoking (the GUI, CLI, and
/// `solve_range_vs_range_nash` wrapper all already do this). See PR #105
/// (HIGH-2 framing) and PR #114 (`TerminalCache` optimization) for
/// analysis.
/// B10 Phase B — per-combo fractional weights wire-in.
///
/// `p0_weights` / `p1_weights`: optional per-hand initial-reach scalars,
/// aligned positionally with `p0_holes` / `p1_holes`. When supplied,
/// the vector-form kernel uses these as the initial reach vectors in
/// place of the all-ones default. Each scalar should be in `[0.0, 1.0]`
/// — the contract is a multiplicative factor only, no algorithmic change
/// in the regret / strategy update loops. All-ones (the default) is
/// bit-identical to the pre-Phase-B code. If supplied, `pN_weights.len()
/// == pN_holes.len()` is required (asserted Rust-side; mismatched length
/// hard-fails with a panic surfaced through PyValueError).
#[pyfunction]
#[pyo3(signature = (
    config_json,
    iterations,
    alpha,
    beta,
    gamma,
    p0_holes=None,
    p1_holes=None,
    regret_init_noise=0.0,
    rng_seed=0,
    p0_weights=None,
    p1_weights=None,
))]
#[allow(clippy::too_many_arguments)]
fn solve_range_vs_range_rust(
    py: Python<'_>,
    config_json: &str,
    iterations: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
    p0_holes: Option<Vec<[u8; 2]>>,
    p1_holes: Option<Vec<[u8; 2]>>,
    regret_init_noise: f64,
    rng_seed: u64,
    p0_weights: Option<Vec<f64>>,
    p1_weights: Option<Vec<f64>>,
) -> PyResult<PyObject> {
    let config: hunl::HUNLConfig = serde_json::from_str(config_json)
        .map_err(|e| PyValueError::new_err(format!("invalid HUNLConfig JSON: {e}")))?;

    // Differential-test hook: when both per-player hand lists are supplied,
    // pass them to the explicit-hand-list constructor. Production callers
    // omit both; the solver enumerates the full deck.
    let hand_lists: Option<[Vec<[u8; 2]>; 2]> = match (p0_holes, p1_holes) {
        (Some(p0), Some(p1)) => Some([p0, p1]),
        (None, None) => None,
        _ => {
            return Err(PyValueError::new_err(
                "p0_holes and p1_holes must both be supplied or both omitted",
            ));
        }
    };

    // B10 Phase B — per-combo weights. Defaults to None (all-ones reach,
    // bit-identical to pre-Phase-B). When supplied, both p0/p1 weights
    // must be present together (same shape contract as p0_holes/p1_holes).
    let hand_weights: Option<[Vec<f64>; 2]> = match (p0_weights, p1_weights) {
        (Some(w0), Some(w1)) => Some([w0, w1]),
        (None, None) => None,
        _ => {
            return Err(PyValueError::new_err(
                "p0_weights and p1_weights must both be supplied or both omitted",
            ));
        }
    };

    let started = std::time::Instant::now();
    // Release the GIL for the pure-Rust solve. CPU-bound, no Python callbacks.
    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        py.allow_threads(|| {
            dcfr_vector::solve_range_vs_range_postflop_with_hands(
                &config,
                hand_lists,
                iterations,
                alpha,
                beta,
                gamma,
                regret_init_noise,
                rng_seed,
                hand_weights,
            )
        })
    }));
    let result = result.map_err(|payload| PyValueError::new_err(panic_message(&payload)))?;
    let out = result.map_err(PyValueError::new_err)?;
    let wallclock_seconds = started.elapsed().as_secs_f64();

    let dict = PyDict::new(py);
    let strat = PyDict::new(py);
    for (key, probs) in &out.average_strategy {
        strat.set_item(key, probs.clone())?;
    }
    dict.set_item("average_strategy", strat)?;
    dict.set_item("iterations", out.iterations)?;
    dict.set_item("wallclock_seconds", wallclock_seconds)?;
    dict.set_item("decision_node_count", out.decision_node_count)?;
    dict.set_item("strategy_entry_count", out.strategy_entry_count)?;
    dict.set_item(
        "hand_count_per_player",
        [
            out.hand_count_per_player[0] as u32,
            out.hand_count_per_player[1] as u32,
        ],
    )?;
    // Per-street memory profile (spec §4). Surfaced as a nested dict so
    // the Python diff test + downstream tooling can compare against the
    // back-of-envelope estimates in the spec.
    let memory_dict = PyDict::new(py);
    memory_dict.set_item("total_bytes", out.memory_profile.total_bytes)?;
    memory_dict.set_item("infoset_count", out.memory_profile.infoset_count)?;
    let by_street = PyDict::new(py);
    for (street, bytes) in &out.memory_profile.by_street {
        by_street.set_item(street, *bytes)?;
    }
    memory_dict.set_item("bytes_by_street", by_street)?;
    let count_by_street = PyDict::new(py);
    for (street, count) in &out.memory_profile.infoset_count_by_street {
        count_by_street.set_item(street, *count)?;
    }
    memory_dict.set_item("infoset_count_by_street", count_by_street)?;
    dict.set_item("memory_profile", memory_dict)?;
    dict.set_item("backend", "rust_vector")?;
    Ok(dict.into())
}

/// Phase A — Full-tree preflop range-vs-range solver, exposed to Python as
/// `_rust.solve_hunl_preflop_rvr`.
///
/// Differs from `solve_hunl_preflop` (the fixed-hole subgame path) by
/// taking `initial_hole_cards = None` and solving the FULL preflop tree
/// with all 1326 hole-card combos per player active. Postflop runouts are
/// collapsed to a single equity-leaf value per (hero_class, villain_class,
/// suit_variant) via the precomputed 169x169x3 table at
/// `assets/preflop_equity_169x169.npz`.
///
/// User-confirmed action menu:
///   - `preflop_open_sizes_bb`: absolute BB amounts for opens (default
///     `[2.0, 3.0, 4.0, 5.0]`).
///   - `preflop_reraise_multipliers`: 3-bet+ multipliers of the previous
///     bet (default `[2.0, 3.0, 4.0, 5.0]`).
///   - All-in always available.
///   - Raise cap from `HUNLConfig.preflop_raise_cap` (default 4).
#[pyfunction]
#[pyo3(signature = (
    config_json,
    equity_table_path,
    iterations,
    alpha,
    beta,
    gamma,
    preflop_open_sizes_bb=None,
    preflop_reraise_multipliers=None,
    p0_holes=None,
    p1_holes=None,
))]
#[allow(clippy::too_many_arguments)]
fn solve_hunl_preflop_rvr(
    py: Python<'_>,
    config_json: &str,
    equity_table_path: &str,
    iterations: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
    preflop_open_sizes_bb: Option<Vec<f64>>,
    preflop_reraise_multipliers: Option<Vec<f64>>,
    p0_holes: Option<Vec<[u8; 2]>>,
    p1_holes: Option<Vec<[u8; 2]>>,
) -> PyResult<PyObject> {
    let config: hunl::HUNLConfig = serde_json::from_str(config_json)
        .map_err(|e| PyValueError::new_err(format!("invalid HUNLConfig JSON: {e}")))?;
    let opens = preflop_open_sizes_bb.unwrap_or_else(|| vec![2.0, 3.0, 4.0, 5.0]);
    let mults = preflop_reraise_multipliers.unwrap_or_else(|| vec![2.0, 3.0, 4.0, 5.0]);
    let table_path = std::path::PathBuf::from(equity_table_path);
    let hand_lists: Option<[Vec<[u8; 2]>; 2]> = match (p0_holes, p1_holes) {
        (Some(p0), Some(p1)) => Some([p0, p1]),
        (None, None) => None,
        _ => {
            return Err(PyValueError::new_err(
                "p0_holes and p1_holes must both be supplied or both omitted",
            ));
        }
    };

    let started = std::time::Instant::now();
    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        py.allow_threads(|| {
            preflop_rvr::solve_hunl_preflop_rvr_with_hands(
                &config,
                &table_path,
                hand_lists,
                &opens,
                &mults,
                iterations,
                alpha,
                beta,
                gamma,
            )
        })
    }));
    let result = result.map_err(|payload| PyValueError::new_err(panic_message(&payload)))?;
    let out = result.map_err(PyValueError::new_err)?;
    let wallclock_seconds = started.elapsed().as_secs_f64();

    let dict = PyDict::new(py);
    let strat = PyDict::new(py);
    for (key, probs) in &out.average_strategy {
        strat.set_item(key, probs.clone())?;
    }
    dict.set_item("average_strategy", strat)?;
    dict.set_item("iterations", out.iterations)?;
    dict.set_item("wallclock_seconds", wallclock_seconds)?;
    dict.set_item("decision_node_count", out.decision_node_count)?;
    dict.set_item("strategy_entry_count", out.strategy_entry_count)?;
    dict.set_item(
        "hand_count_per_player",
        [
            out.hand_count_per_player[0] as u32,
            out.hand_count_per_player[1] as u32,
        ],
    )?;
    dict.set_item("backend", "rust_preflop_rvr")?;
    Ok(dict.into())
}

/// Phase 1.5 (True Path B, #68) — 169-class abstraction preflop RvR
/// solver, exposed to Python as `_rust.solve_hunl_preflop_rvr_class169`.
///
/// Engine operates on 169-element strategy/regret/reach vectors per
/// infoset (instead of 1326-element). Leaf payoffs pre-bake the per-
/// concrete-pair blocker effects into a 169x169 effective table.
///
/// Output dict has key format `"<class_label>||p|<history>"` (e.g.
/// `"AA||p|"` is the SB AA root decision), one entry per (class,
/// history) pair. Caller does NOT need to call `aggregate_to_169_classes`.
///
/// `root_reach_p0` / `root_reach_p1`: optional 169-element vectors with
/// per-class reach at the root. Default (full range, all classes active
/// uniformly): `[1.0; 169]` per player. To filter a range (e.g. premium
/// only), set excluded classes to `0.0`.
#[pyfunction]
#[pyo3(signature = (
    config_json,
    equity_table_path,
    iterations,
    alpha,
    beta,
    gamma,
    preflop_open_sizes_bb=None,
    preflop_reraise_multipliers=None,
    root_reach_p0=None,
    root_reach_p1=None,
))]
#[allow(clippy::too_many_arguments)]
fn solve_hunl_preflop_rvr_class169(
    py: Python<'_>,
    config_json: &str,
    equity_table_path: &str,
    iterations: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
    preflop_open_sizes_bb: Option<Vec<f64>>,
    preflop_reraise_multipliers: Option<Vec<f64>>,
    root_reach_p0: Option<Vec<f64>>,
    root_reach_p1: Option<Vec<f64>>,
) -> PyResult<PyObject> {
    let config: hunl::HUNLConfig = serde_json::from_str(config_json)
        .map_err(|e| PyValueError::new_err(format!("invalid HUNLConfig JSON: {e}")))?;
    let opens = preflop_open_sizes_bb.unwrap_or_else(|| vec![2.0, 3.0, 4.0, 5.0]);
    let mults = preflop_reraise_multipliers.unwrap_or_else(|| vec![2.0, 3.0, 4.0, 5.0]);
    let table_path = std::path::PathBuf::from(equity_table_path);

    let started = std::time::Instant::now();
    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        py.allow_threads(|| {
            preflop_rvr::solve_hunl_preflop_rvr_class169(
                &config,
                &table_path,
                root_reach_p0,
                root_reach_p1,
                &opens,
                &mults,
                iterations,
                alpha,
                beta,
                gamma,
            )
        })
    }));
    let result = result.map_err(|payload| PyValueError::new_err(panic_message(&payload)))?;
    let out = result.map_err(PyValueError::new_err)?;
    let wallclock_seconds = started.elapsed().as_secs_f64();

    let dict = PyDict::new(py);
    let strat = PyDict::new(py);
    for (key, probs) in &out.average_strategy {
        strat.set_item(key, probs.clone())?;
    }
    dict.set_item("average_strategy", strat)?;
    dict.set_item("iterations", out.iterations)?;
    dict.set_item("wallclock_seconds", wallclock_seconds)?;
    dict.set_item("decision_node_count", out.decision_node_count)?;
    dict.set_item("strategy_entry_count", out.strategy_entry_count)?;
    dict.set_item("backend", "rust_preflop_rvr_class169")?;
    dict.set_item("hand_resolution", "class_169")?;
    Ok(dict.into())
}

#[pymodule]
fn _rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(_version, m)?)?;
    m.add_function(wrap_pyfunction!(solve_kuhn, m)?)?;
    m.add_function(wrap_pyfunction!(solve_leduc, m)?)?;
    m.add_function(wrap_pyfunction!(solve_hunl_postflop, m)?)?;
    m.add_function(wrap_pyfunction!(solve_hunl_preflop, m)?)?;
    m.add_function(wrap_pyfunction!(compute_exploitability, m)?)?;
    m.add_function(wrap_pyfunction!(solve_range_vs_range_rust, m)?)?;
    m.add_function(wrap_pyfunction!(solve_hunl_preflop_rvr, m)?)?;
    m.add_function(wrap_pyfunction!(solve_hunl_preflop_rvr_class169, m)?)?;
    Ok(())
}
