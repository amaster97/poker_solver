"""v1.10 PR-3 — Vector-form flop forward walk differential tests (SCAFFOLD).

**Status:** stubs only. All tests are decorated with
``@pytest.mark.skip(reason="PR-3 not yet implemented")`` so CI is not
broken on this branch.

Per ``docs/v1_10_pr3_flop_vector_design.md`` §7, this file holds the
PR-3 diff-test gate:

  - F4.1 standard flop (Qh 7c 2d, 8-class, iters=2).
  - F4.2 wet flop  (JsTs9h, 8-class, iters=2).
  - F4.3 static flop (Kc 7s 2d, 8-class, iters=2).
  - F4_synth small-tree synthetic fixture (4 hands × 1 bet size, hand-traceable).

**Tolerances (plan §4.2):**

  - per-history strategy entry: 1e-12
  - exploitability:             1e-9
  - game value:                 1e-12
  - per-combo BR argmax:        exact (integer match)

**How this file activates:**

After PR-3 implementation lands:

  1. Remove the ``@pytest.mark.skip`` decorators.
  2. Set ``CFR_VECTOR_FLOP_TEMPLATE=1`` env var in the parallel-path
     invocation (TBD by implementation; placeholder for the dispatch
     toggle if PR-3 ships behind a feature flag).
  3. Run::

         pytest tests/test_v1_10_3_flop_diff.py -v

  4. Recapture the v1.10 canonical baseline if any non-flop fixture
     drifts (it must not — PR-3 is bit-identical on non-flop paths).

**Per the silent-skip-hazard rule:** every skip emits an explicit
reason string so a CI sweep that loses skip context still surfaces the
PR-3 dependency.
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest

try:
    from poker_solver import HUNLConfig, Street, parse_board
    from poker_solver.range_aggregator import solve_range_vs_range_nash
except Exception:  # noqa: BLE001
    HUNLConfig = None  # type: ignore[assignment,misc]
    Street = None  # type: ignore[assignment,misc]
    parse_board = None  # type: ignore[assignment]
    solve_range_vs_range_nash = None  # type: ignore[assignment]

try:
    _rust_module = importlib.import_module("poker_solver._rust")
    _rust_solve_rvr = getattr(_rust_module, "solve_range_vs_range_rust", None)
    _rust_compute_exploitability = getattr(
        _rust_module, "compute_exploitability", None
    )
except Exception:  # noqa: BLE001
    _rust_solve_rvr = None  # type: ignore[assignment]
    _rust_compute_exploitability = None  # type: ignore[assignment]


pytestmark = [
    pytest.mark.skipif(
        HUNLConfig is None,
        reason="poker_solver HUNL surface not importable",
    ),
    pytest.mark.skipif(
        _rust_solve_rvr is None or _rust_compute_exploitability is None,
        reason=(
            "_rust.solve_range_vs_range_rust or _rust.compute_exploitability "
            "missing — rebuild via `maturin develop --release`"
        ),
    ),
    # SCAFFOLD: skip everything in this file until PR-3 lands. The
    # individual tests below also carry per-test skip decorators so the
    # reason is visible in CI test reports.
    pytest.mark.skip(
        reason=(
            "v1.10 PR-3 (vector-form flop forward walk) not yet implemented. "
            "See docs/v1_10_pr3_flop_vector_design.md for design. "
            "Activate this file by removing the pytestmark skip + per-test "
            "skip decorators after PR-3 implementation lands."
        ),
    ),
]


# Tolerances per docs/v1_10_postflop_optimization_plan.md §4.2.
_STRATEGY_TOL: float = 1e-12
_EXPL_TOL: float = 1e-9
_GAME_VALUE_TOL: float = 1e-12

# 8 hand classes used by F4.1 / F4.2 / F4.3 — same as test_v1_10_canonical_diff.
_HAND_CLASSES_8: tuple[str, ...] = (
    "AA", "KK", "QQ", "JJ", "AKs", "AKo", "AQs", "AQo",
)

# 4 hand classes for the small-tree synthetic fixture (one suit each so
# blockers fire cleanly; the only-AKs nature keeps it analytically
# tractable).
_HAND_CLASSES_SYNTH: tuple[str, ...] = ("AsKs", "AhKh", "AdKd", "AcKc")


# ---------------------------------------------------------------------------
# Fixture config builders.
# ---------------------------------------------------------------------------


def _f41_flop_standard_config() -> Any:
    """F4.1 — Standard flop (Qh 7c 2d)."""
    return HUNLConfig(
        starting_stack=10000,
        big_blind=100,
        starting_street=Street.FLOP,
        initial_board=tuple(parse_board("Qh 7c 2d")),
        initial_pot=200,
        initial_contributions=(100, 100),
        initial_hole_cards=(),
        bet_size_fractions=(0.5, 1.0),
        postflop_raise_cap=3,
    )


def _f42_flop_wet_config() -> Any:
    """F4.2 — Wet flop (JsTs9h)."""
    return HUNLConfig(
        starting_stack=10000,
        big_blind=100,
        starting_street=Street.FLOP,
        initial_board=tuple(parse_board("Js Ts 9h")),
        initial_pot=200,
        initial_contributions=(100, 100),
        initial_hole_cards=(),
        bet_size_fractions=(0.5, 1.0),
        postflop_raise_cap=3,
    )


def _f43_flop_static_config() -> Any:
    """F4.3 — Static flop (Kc 7s 2d)."""
    return HUNLConfig(
        starting_stack=10000,
        big_blind=100,
        starting_street=Street.FLOP,
        initial_board=tuple(parse_board("Kc 7s 2d")),
        initial_pot=200,
        initial_contributions=(100, 100),
        initial_hole_cards=(),
        bet_size_fractions=(0.5, 1.0),
        postflop_raise_cap=3,
    )


def _f4_synth_config() -> Any:
    """F4_synth — small-tree synthetic fixture (4 hands × 1 bet size).

    Designed for analytical traceability: at raise_cap=1 with a single
    bet size, each street has at most 1 bet/check/call decision per
    actor. The 4 AKs hands across the 4 suits exercise blocker
    enumeration through the runout cache without triggering the full
    1081-combo blowup.

    DFS-order drift in PR-3 produces visible (>1e-6) strategy
    differences on this fixture because every node value is the sum
    of a small number of terms.
    """
    return HUNLConfig(
        starting_stack=200,
        big_blind=100,
        starting_street=Street.FLOP,
        initial_board=tuple(parse_board("2c 3d 4h")),
        initial_pot=200,
        initial_contributions=(100, 100),
        initial_hole_cards=(),
        bet_size_fractions=(1.0,),
        postflop_raise_cap=1,
    )


# ---------------------------------------------------------------------------
# Test class — stubs for each fixture.
# ---------------------------------------------------------------------------


class TestPR3FlopVectorDiff:
    """v1.10 PR-3 vector-form flop forward walk diff-test suite.

    Each test stub follows the same shape:
      1. ``setUp``-equivalent: build the HUNL config + class lists.
      2. Run the canonical (legacy per-runout recursion) solve.
      3. Run the PR-3 (vector-form flop) solve with the same iterations
         and a fresh ``VectorDCFR``.
      4. Assert per-history strategy entries match within 1e-12.
      5. Assert exploitability matches within 1e-9.
      6. Assert game value matches within 1e-12.
      7. Assert per-combo BR action argmax is exact-identical.

    The implementation routes through ``_rust.solve_range_vs_range_rust``
    twice — once on canonical, once with a hypothetical
    ``CFR_VECTOR_FLOP_TEMPLATE=1`` flag (TBD by PR-3 implementation
    plumbing).
    """

    def setup_method(self) -> None:
        """Common setUp: ensures imports succeeded; no per-test state."""
        # Defensive — if the module-level skipif is bypassed, hard-fail
        # before doing any real work so the user sees the dependency.
        assert HUNLConfig is not None, "poker_solver imports broken"
        assert _rust_solve_rvr is not None, "_rust extension missing"

    @pytest.mark.skip(
        reason="v1.10 PR-3 (vector-form flop) not yet implemented",
    )
    def test_f4_1_standard_flop_qh7c2d_diff(self) -> None:
        """F4.1 — bit-identical canonical vs vector-form on Qh 7c 2d."""
        ...

    @pytest.mark.skip(
        reason="v1.10 PR-3 (vector-form flop) not yet implemented",
    )
    def test_f4_2_wet_flop_jsts9h_diff(self) -> None:
        """F4.2 — bit-identical canonical vs vector-form on Js Ts 9h."""
        ...

    @pytest.mark.skip(
        reason="v1.10 PR-3 (vector-form flop) not yet implemented",
    )
    def test_f4_3_static_flop_kc7s2d_diff(self) -> None:
        """F4.3 — bit-identical canonical vs vector-form on Kc 7s 2d."""
        ...

    @pytest.mark.skip(
        reason="v1.10 PR-3 (vector-form flop) not yet implemented",
    )
    def test_f4_synth_small_tree_diff(self) -> None:
        """F4_synth — small-tree synthetic fixture; DFS-order canary."""
        ...

    @pytest.mark.skip(
        reason="v1.10 PR-3 (vector-form flop) not yet implemented",
    )
    def test_pr3_does_not_regress_turn_only_fixtures(self) -> None:
        """Guard: PR-3's dispatch hook must not affect turn-rooted solves.

        Walks F3.1 (Qs 7h 2d 5c) — a turn-rooted RvR — through PR-3 binary,
        asserts the dispatch enters PR-2's ``traverse_turn_chance_recursive``
        (not PR-3's ``traverse_flop_chance_recursive``), and verifies
        strategy bit-identity against pre-PR-3 baseline.
        """
        ...

    @pytest.mark.skip(
        reason="v1.10 PR-3 (vector-form flop) not yet implemented",
    )
    def test_pr3_does_not_regress_river_only_fixtures(self) -> None:
        """Guard: PR-3 must not regress F2.4 (river-rooted RvR).

        Walks F2.4 (Kc 7d 2h Ts 4c) — a river-rooted RvR with no chance
        templates — through PR-3 binary, asserts ``RunoutCache::is_active()``
        returns false (no flop template), and verifies strategy
        bit-identity at 1e-12.
        """
        ...

    @pytest.mark.skip(
        reason="v1.10 PR-3 (vector-form flop) not yet implemented",
    )
    def test_pr3_perf_target_top_k_169_flop(self) -> None:
        """v1.10 headline gate: flop top_k=169 wall <120s on M4 Pro arm64.

        Spec from ``docs/v1_10_postflop_optimization_plan.md`` §3:
        flop top_k=169 iter=100 must complete in <120s. Uses the J7o
        A♦8♥9♦ 40-BB fixture from the canonical bench harness.

        **Note:** this is a perf gate, not a correctness gate. Runs only
        in the per-PR full gate suite, not on every commit.
        """
        ...

    @pytest.mark.skip(
        reason="v1.10 PR-3 (vector-form flop) not yet implemented",
    )
    def test_pr3_memory_target_top_k_169_flop(self) -> None:
        """v1.10 RSS gate: peak RSS on top_k=169 flop ≤ 1 GB.

        Spec from ``docs/v1_10_postflop_optimization_plan.md`` §7 done
        criteria #6. Uses RSS sampling via ``psutil`` during the solve.
        """
        ...


# ---------------------------------------------------------------------------
# Capture helpers (TODO post-PR-3-impl).
# ---------------------------------------------------------------------------


def _run_canonical_flop_solve(cfg: Any, hero_classes: tuple[str, ...],
                              villain_classes: tuple[str, ...],
                              iters: int) -> dict[str, Any]:
    """TODO post-PR-3 — run a flop RvR solve via the legacy per-runout
    recursion path; return ``{strategy, game_value, exploitability,
    br_argmax}`` for diff comparison.

    For the canonical path, the implementation will set
    ``CFR_VECTOR_FLOP_TEMPLATE=0`` (or unset) so dispatch falls through
    to ``traverse_recursive_with_parallel``'s legacy chance arm.
    """
    raise NotImplementedError(
        "v1.10 PR-3 not yet implemented; see "
        "docs/v1_10_pr3_flop_vector_design.md §8 for implementation steps."
    )


def _run_vector_flop_solve(cfg: Any, hero_classes: tuple[str, ...],
                           villain_classes: tuple[str, ...],
                           iters: int) -> dict[str, Any]:
    """TODO post-PR-3 — run a flop RvR solve via the new vector-form
    flop walker; return ``{strategy, game_value, exploitability,
    br_argmax}`` for diff comparison.

    For the vector-form path, the implementation will set
    ``CFR_VECTOR_FLOP_TEMPLATE=1`` so dispatch reaches
    ``traverse_flop_chance_recursive``.
    """
    raise NotImplementedError(
        "v1.10 PR-3 not yet implemented; see "
        "docs/v1_10_pr3_flop_vector_design.md §8 for implementation steps."
    )


def _assert_strategy_bit_identical(strat_a: dict[str, list[float]],
                                   strat_b: dict[str, list[float]],
                                   tol: float = _STRATEGY_TOL) -> None:
    """TODO post-PR-3 — pairwise diff at per-(history, hand, action)
    granularity, fail if any entry exceeds ``tol``."""
    raise NotImplementedError(
        "v1.10 PR-3 not yet implemented; helper is a placeholder."
    )
