"""v1.10 PR-3 — Vector-form flop forward walk differential tests.

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

After PR-3 implementation lands (this PR), the canonical baseline is
the legacy chance-arm walk (``CFR_VECTOR_FLOP_TEMPLATE=0``), and the
vector-form is the default. Each test runs both and asserts
bit-identity.

The smaller fixtures (F4_synth) run quickly; the 8-class flop
fixtures take longer (each ~30-90s per solve at iters=1). The
``@pytest.mark.slow`` marker is applied to those so contributors can
run::

    pytest tests/test_v1_10_3_flop_diff.py -v -m "not slow"

for the fast subset (F4_synth) during inner-loop development.
"""

from __future__ import annotations

import importlib
import os
import time
from typing import Any, Mapping

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
except Exception:  # noqa: BLE001
    _rust_solve_rvr = None  # type: ignore[assignment]


pytestmark = [
    pytest.mark.skipif(
        HUNLConfig is None,
        reason="poker_solver HUNL surface not importable",
    ),
    pytest.mark.skipif(
        _rust_solve_rvr is None,
        reason=(
            "_rust.solve_range_vs_range_rust missing — rebuild via "
            "`maturin develop --release`"
        ),
    ),
]


# Tolerances per docs/v1_10_postflop_optimization_plan.md §4.2.
_STRATEGY_TOL: float = 1e-12

# 8 hand classes used by F4.1 / F4.2 / F4.3 — same as test_v1_10_canonical_diff.
_HAND_CLASSES_8: tuple[str, ...] = (
    "AA", "KK", "QQ", "JJ", "AKs", "AKo", "AQs", "AQo",
)

# 4 hand classes for the small-tree synthetic fixture.
_HAND_CLASSES_SYNTH: tuple[str, ...] = ("AKs", "AKo", "AQs", "AQo")


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
    actor.

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
# Shared solver harness — runs one fixture in either template mode.
# ---------------------------------------------------------------------------


def _run_solve(
    cfg: Any,
    hands: tuple[str, ...],
    iters: int,
    *,
    template_mode: str,
) -> Mapping[str, list[float]]:
    """Run an RvR Nash solve in the given template mode.

    ``template_mode``:
      - ``"canonical"`` — sets ``CFR_VECTOR_FLOP_TEMPLATE=0``; the Rust
        backend builds the tree in ``BettingTreeMode::Standard`` and
        the dispatch falls through to the legacy chance-arm loop on
        every chance node. Reference baseline.
      - ``"vector"`` — default env (no override); the Rust backend
        builds the tree in ``BettingTreeMode::TemplateExtract`` and
        dispatch routes through the v1.10 PR-3
        ``traverse_flop_chance_recursive`` walker on the depth==2
        chance node.

    Restores the original env state on exit.

    Both legs additionally force ``CFR_SUIT_ISO=0`` and ``CFR_TERMINAL_IE=0``.
    Those two opts are now DEFAULT-ON in production, but this gate isolates a
    SINGLE axis — the flop-template walker vs the legacy chance-arm loop — and
    must compare the two at 1e-12. Pinning the other two opts off in BOTH legs
    keeps suit-iso/IE from confounding the flop-template diff (the suit-iso /
    IE paths have their own dedicated parity gates).
    """
    env_was = os.environ.get("CFR_VECTOR_FLOP_TEMPLATE")
    suit_iso_was = os.environ.get("CFR_SUIT_ISO")
    terminal_ie_was = os.environ.get("CFR_TERMINAL_IE")
    if template_mode == "canonical":
        os.environ["CFR_VECTOR_FLOP_TEMPLATE"] = "0"
    elif template_mode == "vector":
        os.environ.pop("CFR_VECTOR_FLOP_TEMPLATE", None)
    else:
        raise ValueError(f"unknown template_mode: {template_mode!r}")
    # Force the SERIAL chance path AND the legacy (non-iso, non-IE) eval in BOTH
    # legs. Rayon, suit-iso, and IE are all now default-on, so without this both
    # the canonical and vector legs would run them — which (a) makes the 1e-12
    # bit-identical diff fragile and (b) bypasses the PR-3 flop-template walker
    # this test exists to exercise.
    rayon_was = os.environ.get("CFR_RAYON_CHANCE")
    os.environ["CFR_RAYON_CHANCE"] = "0"
    os.environ["CFR_SUIT_ISO"] = "0"
    os.environ["CFR_TERMINAL_IE"] = "0"
    try:
        result = solve_range_vs_range_nash(
            cfg,
            list(hands),
            list(hands),
            iterations=iters,
            alpha=1.5,
            beta=0.0,
            gamma=2.0,
            hero_player=0,
            compute_exploitability_at_end=False,
        )
        return result.per_history_strategy
    finally:
        if env_was is None:
            os.environ.pop("CFR_VECTOR_FLOP_TEMPLATE", None)
        else:
            os.environ["CFR_VECTOR_FLOP_TEMPLATE"] = env_was
        if rayon_was is None:
            os.environ.pop("CFR_RAYON_CHANCE", None)
        else:
            os.environ["CFR_RAYON_CHANCE"] = rayon_was
        if suit_iso_was is None:
            os.environ.pop("CFR_SUIT_ISO", None)
        else:
            os.environ["CFR_SUIT_ISO"] = suit_iso_was
        if terminal_ie_was is None:
            os.environ.pop("CFR_TERMINAL_IE", None)
        else:
            os.environ["CFR_TERMINAL_IE"] = terminal_ie_was


def _assert_strategy_bit_identical(
    canonical: Mapping[str, list[float]],
    vector: Mapping[str, list[float]],
    tol: float = _STRATEGY_TOL,
) -> None:
    """Pairwise diff at per-(history, hand, action) granularity.

    Fails if any entry exceeds ``tol`` OR the key sets differ OR the
    per-key action_counts mismatch.
    """
    keys_c = set(canonical.keys())
    keys_v = set(vector.keys())
    assert keys_c == keys_v, (
        f"key set mismatch: canonical={len(keys_c)} vector={len(keys_v)}, "
        f"only_canonical_sample={list(keys_c - keys_v)[:3]}, "
        f"only_vector_sample={list(keys_v - keys_c)[:3]}"
    )
    max_diff = 0.0
    max_key = ""
    max_act = -1
    for k in keys_c:
        pc = canonical[k]
        pv = vector[k]
        assert len(pc) == len(pv), (
            f"action_count mismatch at key {k!r}: "
            f"canonical={len(pc)} vector={len(pv)}"
        )
        for ai, (xc, xv) in enumerate(zip(pc, pv)):
            d = abs(xc - xv)
            if d > max_diff:
                max_diff = d
                max_key = k
                max_act = ai
    assert max_diff <= tol, (
        f"strategy drift exceeds tol={tol:.2e}: max_diff={max_diff:.3e} "
        f"at key={max_key!r} action={max_act}"
    )


# ---------------------------------------------------------------------------
# Test class.
# ---------------------------------------------------------------------------


class TestPR3FlopVectorDiff:
    """v1.10 PR-3 vector-form flop forward walk diff-test suite.

    Each test runs:
      1. The PR-3 vector-form walker (default env).
      2. The canonical legacy chance-arm walk
         (``CFR_VECTOR_FLOP_TEMPLATE=0``).
      3. Asserts per-history strategy entries match within 1e-12.
    """

    def test_f4_synth_small_tree_diff(self) -> None:
        """F4_synth — small-tree synthetic fixture; DFS-order canary.

        4 hand classes, 1 bet size, raise_cap=1, board 2c3d4h. Small
        enough to converge analytically within iters=10; DFS-order
        drift produces visible (>1e-6) strategy differences.
        """
        cfg = _f4_synth_config()
        strat_vec = _run_solve(
            cfg, _HAND_CLASSES_SYNTH, iters=10, template_mode="vector"
        )
        strat_can = _run_solve(
            cfg, _HAND_CLASSES_SYNTH, iters=10, template_mode="canonical"
        )
        _assert_strategy_bit_identical(strat_can, strat_vec)

    @pytest.mark.slow
    def test_f4_1_standard_flop_qh7c2d_diff(self) -> None:
        """F4.1 — bit-identical canonical vs vector-form on Qh 7c 2d."""
        cfg = _f41_flop_standard_config()
        strat_vec = _run_solve(
            cfg, _HAND_CLASSES_8, iters=1, template_mode="vector"
        )
        strat_can = _run_solve(
            cfg, _HAND_CLASSES_8, iters=1, template_mode="canonical"
        )
        _assert_strategy_bit_identical(strat_can, strat_vec)

    @pytest.mark.slow
    def test_f4_2_wet_flop_jsts9h_diff(self) -> None:
        """F4.2 — bit-identical canonical vs vector-form on Js Ts 9h."""
        cfg = _f42_flop_wet_config()
        strat_vec = _run_solve(
            cfg, _HAND_CLASSES_8, iters=1, template_mode="vector"
        )
        strat_can = _run_solve(
            cfg, _HAND_CLASSES_8, iters=1, template_mode="canonical"
        )
        _assert_strategy_bit_identical(strat_can, strat_vec)

    @pytest.mark.slow
    def test_f4_3_static_flop_kc7s2d_diff(self) -> None:
        """F4.3 — bit-identical canonical vs vector-form on Kc 7s 2d."""
        cfg = _f43_flop_static_config()
        strat_vec = _run_solve(
            cfg, _HAND_CLASSES_8, iters=1, template_mode="vector"
        )
        strat_can = _run_solve(
            cfg, _HAND_CLASSES_8, iters=1, template_mode="canonical"
        )
        _assert_strategy_bit_identical(strat_can, strat_vec)

    def test_pr3_does_not_regress_turn_only_fixtures(self) -> None:
        """Guard: PR-3's dispatch hook must not affect turn-rooted solves.

        Walks F3.1 (Qs 7h 2d 5c) — a turn-rooted RvR — through the
        PR-3 binary in BOTH modes; verifies strategy bit-identity at
        1e-12. Since turn-rooted solves have a depth==1 (turn) chance
        template, the dispatch goes to PR-2's
        ``traverse_turn_chance_recursive``, NOT PR-3's
        ``traverse_flop_chance_recursive``. The diff verifies the
        PR-3 dispatch hook didn't inadvertently affect this path.
        """
        cfg = HUNLConfig(
            starting_stack=20000,
            big_blind=100,
            starting_street=Street.TURN,
            initial_board=tuple(parse_board("Qs 7h 2d 5c")),
            initial_pot=1000,
            initial_contributions=(500, 500),
            initial_hole_cards=(),
            bet_size_fractions=(0.5, 1.0),
            postflop_raise_cap=3,
        )
        strat_vec = _run_solve(
            cfg, _HAND_CLASSES_8, iters=2, template_mode="vector"
        )
        strat_can = _run_solve(
            cfg, _HAND_CLASSES_8, iters=2, template_mode="canonical"
        )
        _assert_strategy_bit_identical(strat_can, strat_vec)

    def test_pr3_does_not_regress_river_only_fixtures(self) -> None:
        """Guard: PR-3 must not regress F2.4 (river-rooted RvR).

        Walks F2.4 (Kc 7d 2h Ts 4c) — a river-rooted RvR with no chance
        templates inside the betting tree — through PR-3 binary in
        BOTH modes; verifies strategy bit-identity at 1e-12. Since the
        ``RunoutCache::is_active()`` check fails for river-rooted
        solves (no chance templates at all), this exercises the
        fall-through legacy path.
        """
        cfg = HUNLConfig(
            starting_stack=1000,
            big_blind=100,
            starting_street=Street.RIVER,
            initial_board=tuple(parse_board("Kc 7d 2h Ts 4c")),
            initial_pot=1000,
            initial_contributions=(500, 500),
            initial_hole_cards=(),
            bet_size_fractions=(0.5, 1.0),
            postflop_raise_cap=3,
        )
        strat_vec = _run_solve(
            cfg, _HAND_CLASSES_8, iters=20, template_mode="vector"
        )
        strat_can = _run_solve(
            cfg, _HAND_CLASSES_8, iters=20, template_mode="canonical"
        )
        _assert_strategy_bit_identical(strat_can, strat_vec)
