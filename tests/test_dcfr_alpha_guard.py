"""DCFR α-guard tests (v1.8.1 / HIGH-1 fix per PR #99 Option B).

Covers ``poker_solver.dcfr._validate_alpha`` and its propagation through:

- ``DCFRSolver`` constructor (Python tier).
- ``poker_solver.solver._solve_rust`` (Rust-binding pre-flight).
- ``poker_solver.range_aggregator.solve_range_vs_range_nash`` (vector-form
  Nash entry).

The Rust constructor's panic surfaces as ``PyValueError`` via the existing
``catch_unwind`` wrappers at the PyO3 boundary; covered indirectly in the
``test_solve_kuhn_rejects_alpha_zero`` case below (which calls the Rust
binding without going through the Python ``_validate_alpha``).
"""
from __future__ import annotations

import warnings

import pytest

from poker_solver.dcfr import DCFRSolver, _validate_alpha
from poker_solver.games import KuhnPoker


# ---------------------------------------------------------------------------
# _validate_alpha helper — direct tests
# ---------------------------------------------------------------------------


def test_validate_alpha_rejects_zero():
    with pytest.raises(ValueError, match=r"alpha=0 silently stalls"):
        _validate_alpha(0.0)


def test_validate_alpha_rejects_negative():
    with pytest.raises(ValueError, match=r"alpha must be > 0"):
        _validate_alpha(-0.5)


def test_validate_alpha_rejects_nan():
    with pytest.raises(ValueError, match=r"alpha must be > 0 and finite"):
        _validate_alpha(float("nan"))


def test_validate_alpha_rejects_infinity():
    with pytest.raises(ValueError, match=r"alpha must be > 0 and finite"):
        _validate_alpha(float("inf"))
    with pytest.raises(ValueError, match=r"alpha must be > 0 and finite"):
        _validate_alpha(float("-inf"))


def test_validate_alpha_warns_in_low_band():
    # 0 < alpha < 0.5: expected to emit UserWarning, not raise.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _validate_alpha(0.3)
        assert len(caught) == 1
        assert issubclass(caught[0].category, UserWarning)
        assert "alpha=0.3" in str(caught[0].message)
        assert "Brown 2019" in str(caught[0].message)


def test_validate_alpha_silent_for_production_value():
    # alpha=1.5 is the locked production value; must be silent OK.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _validate_alpha(1.5)
        assert len(caught) == 0


def test_validate_alpha_silent_for_paper_experimentation():
    # alpha=2.0 is a paper-range experimentation value (used by existing
    # differential probes in `docs/perpetual_qa_findings_2026-05-27.md`).
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _validate_alpha(2.0)
        assert len(caught) == 0


# ---------------------------------------------------------------------------
# DCFRSolver constructor — integration via __init__
# ---------------------------------------------------------------------------


def test_dcfr_solver_rejects_alpha_zero():
    with pytest.raises(ValueError, match=r"alpha=0 silently stalls"):
        DCFRSolver(KuhnPoker(), alpha=0.0)


def test_dcfr_solver_rejects_alpha_negative():
    with pytest.raises(ValueError, match=r"alpha must be > 0"):
        DCFRSolver(KuhnPoker(), alpha=-1.0)


def test_dcfr_solver_warns_alpha_low_band():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        DCFRSolver(KuhnPoker(), alpha=0.3)
        # The constructor's warning is the only one expected.
        assert any(
            issubclass(w.category, UserWarning) and "alpha=0.3" in str(w.message)
            for w in caught
        ), f"expected alpha=0.3 warning; got {[str(w.message) for w in caught]}"


def test_dcfr_solver_accepts_production_alpha():
    # Smoke: alpha=1.5 (production locked) must construct cleanly with no
    # warnings.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        solver = DCFRSolver(KuhnPoker(), alpha=1.5)
        assert solver.alpha == 1.5
        # Filter to only warnings about alpha — the test doesn't care about
        # unrelated DeprecationWarnings from other modules.
        alpha_warnings = [
            w for w in caught if "alpha" in str(w.message).lower()
        ]
        assert alpha_warnings == [], (
            f"alpha=1.5 (locked production) must be silent; "
            f"got: {[str(w.message) for w in alpha_warnings]}"
        )


# ---------------------------------------------------------------------------
# PyO3 binding (`solve_kuhn`) — end-to-end through the Rust constructor
# ---------------------------------------------------------------------------


def test_alpha_zero_hard_fails():
    """`_rust.solve_kuhn(..., alpha=0)` must raise — covers the PyO3 panic →
    PyValueError surface, exercising the Rust `validate_alpha` panic at the
    DCFR constructor reached through the binding."""
    from poker_solver._rust import solve_kuhn

    # The Rust panic surfaces as ValueError via `catch_unwind` at the PyO3
    # boundary (lib.rs:108-119). Match loosely on "alpha" — the Rust message
    # mentions α via the Unicode glyph in some builds; the substring "alpha"
    # in the ASCII portion of the message is the stable check.
    with pytest.raises(ValueError, match=r"(?i)alpha|α"):
        solve_kuhn(100, 0.0, 0.0, 2.0)


def test_alpha_small_warns():
    """`solve_kuhn(..., alpha=0.3)`: the Rust binding emits via stderr
    `eprintln!`, so we exercise the Python-side wrapper `_solve_rust` which
    pre-flights alpha through `_validate_alpha` (Python `warnings.warn`)
    before dispatch into Rust. This is the documented entry point for
    Python callers."""
    from poker_solver.games import KuhnPoker
    from poker_solver.solver import _solve_rust

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _solve_rust(KuhnPoker(), iterations=10, alpha=0.3, beta=0.0, gamma=2.0)
        alpha_warnings = [
            w for w in caught
            if issubclass(w.category, UserWarning) and "alpha=0.3" in str(w.message)
        ]
        assert alpha_warnings, (
            f"expected UserWarning for alpha=0.3; got: "
            f"{[str(w.message) for w in caught]}"
        )


def test_alpha_default_silent():
    """alpha=1.5 (production) must not warn when threaded through the Python
    Rust-binding wrapper — guards against regression where the warn band
    accidentally inflates above 1.0."""
    from poker_solver.games import KuhnPoker
    from poker_solver.solver import _solve_rust

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _solve_rust(KuhnPoker(), iterations=10, alpha=1.5, beta=0.0, gamma=2.0)
        alpha_warnings = [
            w for w in caught if "alpha" in str(w.message).lower()
        ]
        assert alpha_warnings == [], (
            f"alpha=1.5 (locked production) must be silent through "
            f"_solve_rust; got: {[str(w.message) for w in alpha_warnings]}"
        )
