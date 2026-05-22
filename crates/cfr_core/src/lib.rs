//! `poker_solver._rust` — PyO3 extension exposing the Rust DCFR production tier.
//!
//! The Python reference tier (`poker_solver/dcfr.py`) is the ground truth;
//! this crate is a structural port for performance. The differential test
//! (`tests/test_dcfr_diff.py`) keeps the two implementations in lockstep.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;

mod dcfr;
mod game;
mod kuhn;
mod leduc;
mod solver;

// PR 6 — HUNL Rust production tier (Agent A's modules + Agent B's pipeline).
// All modules are `pub` so integration tests (`crates/cfr_core/tests/*.rs`)
// can reach them across the crate boundary.
pub mod abstraction;
pub mod hunl;
pub mod hunl_eval;
pub mod hunl_solver;
pub mod hunl_tree;

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
#[pyfunction]
fn solve_kuhn(
    py: Python<'_>,
    iterations: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
) -> PyResult<PyObject> {
    let out = solver::solve_kuhn(iterations, alpha, beta, gamma);
    solve_output_to_py(py, out)
}

/// Run the full Leduc DCFR solve. Same dict shape as `solve_kuhn`.
///
/// Leduc has 288 infosets (6-card deck collapsed by rank, two betting rounds);
/// per-infoset action vectors are 1–3 wide depending on betting context.
#[pyfunction]
fn solve_leduc(
    py: Python<'_>,
    iterations: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
) -> PyResult<PyObject> {
    let out = solver::solve_leduc(iterations, alpha, beta, gamma);
    solve_output_to_py(py, out)
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
    let result = py.allow_threads(|| {
        hunl_solver::solve_hunl_postflop(
            &config,
            abstraction.as_ref(),
            iterations,
            alpha,
            beta,
            gamma,
            target_exploitability,
            seed,
        )
    });
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

#[pymodule]
fn _rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(_version, m)?)?;
    m.add_function(wrap_pyfunction!(solve_kuhn, m)?)?;
    m.add_function(wrap_pyfunction!(solve_leduc, m)?)?;
    m.add_function(wrap_pyfunction!(solve_hunl_postflop, m)?)?;
    Ok(())
}
