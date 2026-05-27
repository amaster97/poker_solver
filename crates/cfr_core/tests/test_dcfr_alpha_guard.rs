//! DCFR α-guard tests (v1.8.1 / HIGH-1 fix per PR #99 Option B).
//!
//! Covers `cfr_core::dcfr::validate_alpha`:
//!   - α = 0 → panic (HARD-FAIL).
//!   - α < 0 → panic (HARD-FAIL).
//!   - α = NaN / infinity → panic (HARD-FAIL).
//!   - α = 0.3 → warning emitted via eprintln! (cannot easily assert in
//!     integration test; we assert the call returns without panic).
//!   - α = 1.5 → silent OK (no panic, no observable side-effect from this
//!     entry point).
//!
//! The panic message must mention `alpha=0 silently stalls` so the user
//! understands why the call was rejected.
//!
//! These tests exercise the helper directly. Indirect coverage at the PyO3
//! boundary (panic → PyValueError) is left to the Python tier's
//! `tests/test_dcfr_alpha_guard.py` companion suite.

use cfr_core::dcfr::validate_alpha;

#[test]
fn alpha_zero_panics() {
    let result = std::panic::catch_unwind(|| validate_alpha(0.0));
    assert!(result.is_err(), "α = 0 must panic, but call returned");
    let msg = result.err().and_then(|payload| {
        payload
            .downcast_ref::<String>()
            .cloned()
            .or_else(|| payload.downcast_ref::<&'static str>().map(|s| s.to_string()))
    });
    let msg = msg.expect("panic payload must be a string");
    assert!(
        msg.contains("alpha=0") || msg.contains("α=0") || msg.contains("0 silently stalls"),
        "panic message should explain α=0 is degenerate; got: {msg}"
    );
}

#[test]
fn alpha_negative_panics() {
    let result = std::panic::catch_unwind(|| validate_alpha(-0.5));
    assert!(result.is_err(), "α < 0 must panic");
}

#[test]
fn alpha_nan_panics() {
    let result = std::panic::catch_unwind(|| validate_alpha(f64::NAN));
    assert!(result.is_err(), "α = NaN must panic");
}

#[test]
fn alpha_infinity_panics() {
    let result = std::panic::catch_unwind(|| validate_alpha(f64::INFINITY));
    assert!(result.is_err(), "α = +∞ must panic");
    let result = std::panic::catch_unwind(|| validate_alpha(f64::NEG_INFINITY));
    assert!(result.is_err(), "α = -∞ must panic");
}

#[test]
fn alpha_in_warn_band_does_not_panic() {
    // α = 0.3 is below the analyzed range; expected behavior is a stderr
    // warning, NOT a panic. The warning itself is emitted via eprintln! and
    // not captured here (integration tests don't easily redirect stderr).
    let result = std::panic::catch_unwind(|| validate_alpha(0.3));
    assert!(result.is_ok(), "α = 0.3 must warn (not panic)");
}

#[test]
fn alpha_production_value_silent_ok() {
    let result = std::panic::catch_unwind(|| validate_alpha(1.5));
    assert!(result.is_ok(), "α = 1.5 (locked production value) must be silent OK");
}

#[test]
fn alpha_paper_experimentation_silent_ok() {
    // α = 2.0 is outside Brown's headline α = 1.5 but well within the band
    // where the paper's qualitative analysis holds (α > 0, finite). Used by
    // existing differential probes (`docs/perpetual_qa_findings_2026-05-27.md`
    // line 337). Must remain silent OK.
    let result = std::panic::catch_unwind(|| validate_alpha(2.0));
    assert!(result.is_ok(), "α = 2.0 (paper-range experimentation) must be silent OK");
}
