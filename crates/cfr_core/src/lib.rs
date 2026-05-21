//! `poker_solver._rust` — PyO3 extension exposing the Rust DCFR production tier.
//!
//! The Python reference tier (`poker_solver/dcfr.py`) is the ground truth;
//! this crate is a structural port for performance. The differential test
//! (`tests/test_dcfr_diff.py`) keeps the two implementations in lockstep.

use pyo3::prelude::*;
use pyo3::types::PyDict;

mod dcfr;
mod game;
mod kuhn;
mod leduc;
mod solver;

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

#[pymodule]
fn _rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(_version, m)?)?;
    m.add_function(wrap_pyfunction!(solve_kuhn, m)?)?;
    m.add_function(wrap_pyfunction!(solve_leduc, m)?)?;
    Ok(())
}
