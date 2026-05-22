"""Cross-solver parity / differential-test wrappers.

This sub-package hosts thin wrappers around external solvers we run as
read-only differential references against our own engine. PR 7 ships the
first wrapper, `noambrown_wrapper`, for Noam Brown's MIT-licensed
``river_solver_optimized`` C++ binary. Future PRs may add wrappers for
``slumbot_wrapper`` and ``open_spiel_wrapper`` here.

Convention:

  * Every wrapper invokes its target as a subprocess.
  * No source code from the wrapped solvers is copied into this package.
  * Each wrapper provides a small set of dataclasses that mirror the
    wrapped solver's output schema, plus pure-Python canonicalization
    helpers so consumers can compare strategies across encodings.

Each individual wrapper module carries the license attribution required
by its target (see e.g. ``noambrown_wrapper.py`` module docstring).
"""

from __future__ import annotations
