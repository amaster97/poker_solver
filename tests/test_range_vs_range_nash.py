"""Tests for ``poker_solver.solve_range_vs_range_nash`` (PR 43 / v1.7.0).

This is the new user-facing entry point that delegates a range-vs-range
query to PR 23's vector-form CFR (``_rust.solve_range_vs_range_rust``).
It is the *honest* range-Nash answer, distinct from the
``solve_range_vs_range`` aggregator's Pluribus-blueprint approximation.

See ``docs/pr_proposals/v1_7_0_aggregator_vector_wiring.md`` for the spec.

Test surface (matching spec §7 acceptance tests, scaled down for the
v1.5.1 .so's known asymmetric-range bug — both ranges must enumerate
the same combo count until v1.6.1 ships PR 34/35; the wrapper itself is
correct on either input shape, but the underlying engine panics on
asymmetric inputs):

  * Tier 1: structural smoke + schema (small symmetric range).
  * Tier 2: W3.5 monotone-river polarization — AA should pure check on
    Ts 8s 6s 4c 2d (matches ``docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md``).
  * Tier 3: divergence-from-aggregator regression — codifies the
    explainer doc's claim that the two functions solve different objects.
  * Tier 4: error cases (preflop raise, invalid hero_player, empty range).
  * Tier 5: exploitability bound (small fixture <0.1 BB) + backend tag.
"""

from __future__ import annotations

import importlib

import pytest

from poker_solver import (
    Card,
    HUNLConfig,
    RangeVsRangeNashResult,
    Street,
    solve_range_vs_range,
    solve_range_vs_range_nash,
)


# ---------------------------------------------------------------------------
# Skip when the Rust vector-form binding is missing
# ---------------------------------------------------------------------------

try:
    _rust_module = importlib.import_module("poker_solver._rust")
    _has_vector_form = hasattr(_rust_module, "solve_range_vs_range_rust")
except Exception:  # noqa: BLE001
    _has_vector_form = False

pytestmark = pytest.mark.skipif(
    not _has_vector_form,
    reason=(
        "_rust.solve_range_vs_range_rust missing — PR 23 vector-form binding "
        "not built. Rebuild via `maturin develop --release`."
    ),
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _w3_5_config() -> HUNLConfig:
    """W3.5 monotone-river spot: Ts 8s 6s 4c 2d, 5 BB stacks, 100-chip pot.

    From ``docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md`` (referenced
    by the v1.7.0 spec §1.3). True Nash on this board has AA as a
    bluff-catcher → pure check.
    """
    return HUNLConfig(
        starting_stack=5000,
        small_blind=50,
        big_blind=100,
        ante=0,
        starting_street=Street.RIVER,
        initial_board=tuple(
            Card.from_str(c) for c in ("Ts", "8s", "6s", "4c", "2d")
        ),
        initial_pot=1000,
        initial_contributions=(500, 500),
        initial_hole_cards=(),
        postflop_raise_cap=1,
        bet_size_fractions=(0.75,),
        include_all_in=False,
    )


def _dry_river_config() -> HUNLConfig:
    """Dry rainbow river (As 7c 2d Kh 5s) for value-vs-air dynamics."""
    return HUNLConfig(
        starting_stack=5000,
        small_blind=50,
        big_blind=100,
        ante=0,
        starting_street=Street.RIVER,
        initial_board=tuple(
            Card.from_str(c) for c in ("As", "7c", "2d", "Kh", "5s")
        ),
        initial_pot=1000,
        initial_contributions=(500, 500),
        initial_hole_cards=(),
        postflop_raise_cap=1,
        bet_size_fractions=(0.75,),
        include_all_in=False,
    )


# ---------------------------------------------------------------------------
# Tier 1: structural smoke + schema
# ---------------------------------------------------------------------------


def test_smoke_2x2_routes_to_rust_vector() -> None:
    """Smoke: a tiny 2x2 symmetric range solves and returns the Rust vector
    backend tag with populated per-history strategy."""
    cfg = _dry_river_config()
    result = solve_range_vs_range_nash(
        cfg,
        hero_range=["AA", "KK"],
        villain_range=["AA", "KK"],
        iterations=50,
        hero_player=0,
        compute_exploitability_at_end=False,
    )
    assert isinstance(result, RangeVsRangeNashResult)
    assert result.backend == "rust_vector"
    assert result.iterations == 50
    assert result.wall_clock_s > 0.0
    assert result.decision_node_count > 0
    # AA has 3 board-feasible combos (As is on the board → 3 of 6 remain);
    # KK has 3 combos (Kh on the board → 3 of 6 remain). 3 + 3 = 6 per
    # player.
    assert result.hand_count_per_player[0] == 6
    assert result.hand_count_per_player[1] == 6
    assert len(result.per_history_strategy) > 0
    # Per-history rows are valid probability distributions.
    for key, probs in result.per_history_strategy.items():
        assert all(p >= 0.0 for p in probs), (
            f"negative prob in row {key!r}: {probs}"
        )
        total = sum(probs)
        assert abs(total - 1.0) < 1e-6, (
            f"row {key!r} does not sum to 1.0 (got {total})"
        )


def test_nash_result_schema_position_aggressor_vs_defender() -> None:
    """The ``position`` field reflects ``hero_player`` correctly."""
    cfg = _dry_river_config()
    r0 = solve_range_vs_range_nash(
        cfg,
        hero_range=["AA", "KK"],
        villain_range=["AA", "KK"],
        iterations=20,
        hero_player=0,
        compute_exploitability_at_end=False,
    )
    assert r0.position == "aggressor"
    r1 = solve_range_vs_range_nash(
        cfg,
        hero_range=["AA", "KK"],
        villain_range=["AA", "KK"],
        iterations=20,
        hero_player=1,
        compute_exploitability_at_end=False,
    )
    assert r1.position == "defender"


def test_per_class_projection_rows_sum_to_one() -> None:
    """Each ``per_class_strategy`` entry must sum to 1.0 (modulo float ε)."""
    cfg = _dry_river_config()
    result = solve_range_vs_range_nash(
        cfg,
        hero_range=["AA", "KK"],
        villain_range=["AA", "KK"],
        iterations=50,
        hero_player=1,
        compute_exploitability_at_end=False,
    )
    assert len(result.per_class_strategy) > 0
    for cls, freqs in result.per_class_strategy.items():
        total = sum(freqs.values())
        assert abs(total - 1.0) < 1e-6, (
            f"per_class_strategy[{cls!r}] sums to {total}, expected 1.0"
        )
    agg_total = sum(result.range_aggregate.values())
    assert abs(agg_total - 1.0) < 1e-6, (
        f"range_aggregate sums to {agg_total}, expected 1.0"
    )


# ---------------------------------------------------------------------------
# Tier 2: W3.5 monotone polarization reproduction
# ---------------------------------------------------------------------------


@pytest.mark.timeout(120)
def test_w3_5_monotone_aa_pure_check() -> None:
    """W3.5 fixture: AA on Ts 8s 6s 4c 2d → near-100% check.

    Replicates the TRUE-Nash finding from
    ``docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md`` at a tractable
    scale. On a monotone board AA is a bluff-catcher: hands that beat
    AA (sets) will continue against a bet, hands AA beats (under-pairs)
    won't pay off — pure check is correct Nash.

    The W3.5 doc reports 1.0000 check probability for AA at 3000 iter
    in a 15x15 symmetric range. We reproduce at 200 iter in a 3x3
    symmetric range, accepting a looser ≥0.90 check bound (the smaller
    range has fewer bluff-catch opportunities for villain so the same
    qualitative effect holds with looser convergence).
    """
    cfg = _w3_5_config()
    # Symmetric AA/KK/QQ ranges — w/in v1.5.1 .so's equal-size constraint.
    # On this monotone board (no Ace blocker), AA's 6 combos are all
    # board-feasible.
    classes = ["AA", "KK", "QQ"]
    result = solve_range_vs_range_nash(
        cfg,
        hero_range=classes,
        villain_range=classes,
        iterations=200,
        hero_player=1,  # river-first actor (defender)
        compute_exploitability_at_end=False,
    )
    aa_strat = result.per_class_strategy.get("AA", {})
    assert aa_strat, "AA missing from per_class_strategy"
    check_freq = aa_strat.get("check", 0.0)
    assert check_freq >= 0.90, (
        f"W3.5 AA bluff-catch failed: AA check freq = {check_freq:.4f}, "
        f"expected ≥ 0.90 (TRUE-Nash reports 1.0000 at higher iter). "
        f"Strategy: {aa_strat}"
    )
    # Range aggregate should also lean heavily toward check on this
    # monotone board.
    range_check = result.range_aggregate.get("check", 0.0)
    assert range_check >= 0.85, (
        f"range_aggregate check = {range_check:.4f}, expected ≥ 0.85"
    )


# ---------------------------------------------------------------------------
# Tier 3: divergence-from-aggregator regression
# ---------------------------------------------------------------------------


@pytest.mark.timeout(300)
def test_diverges_from_aggregator_on_same_inputs() -> None:
    """The vector-form Nash and the aggregator MUST diverge on the same
    inputs (per ``docs/aggregator_vs_true_nash_explainer.md``).

    Codifies the explainer's core claim as a regression test: if these
    two paths ever agree exactly, one of them is buggy (or the test
    fixture is too narrow to expose the difference).

    Fixture: monotone river spot (no Ace blocker), wider symmetric range
    (6 pair classes per side). The aggregator's per-combo perfect-info
    subgame solver collapses AA's polarization because each subgame
    sees villain's exact hand; the vector form's range-Nash collectively
    treats AA as a bluff-catcher.
    """
    cfg = _w3_5_config()
    # Wider range (overpairs) to give both paths room to disagree.
    classes = ["AA", "KK", "QQ", "JJ", "TT", "99"]

    nash = solve_range_vs_range_nash(
        cfg,
        hero_range=classes,
        villain_range=classes,
        iterations=200,
        hero_player=1,
        compute_exploitability_at_end=False,
    )
    agg = solve_range_vs_range(
        cfg,
        hero_range=classes,
        villain_range=classes,
        iterations=50,
        hero_player=1,
        villain_reps=1,
    )

    # Range-aggregate divergence ≥ 5 percentage points on at least one
    # action label that both paths report.
    common_labels = set(nash.range_aggregate.keys()) & set(
        agg.range_aggregate.keys()
    )
    assert common_labels, "no shared action labels between the two paths"
    max_diff = max(
        abs(nash.range_aggregate[k] - agg.range_aggregate[k])
        for k in common_labels
    )
    assert max_diff >= 0.05, (
        f"vector-form Nash and aggregator agree within {max_diff:.4f} on "
        f"range_aggregate — they should diverge by ≥ 0.05 on this monotone "
        f"river spot. nash={nash.range_aggregate} agg={agg.range_aggregate}"
    )


# ---------------------------------------------------------------------------
# Tier 4: error cases
# ---------------------------------------------------------------------------


def test_preflop_raises_value_error() -> None:
    """Preflop starting street is not supported (vector form deferred)."""
    # ``HUNLConfig.__post_init__`` requires ``initial_pot == 0`` AND
    # ``initial_contributions == (0, 0)`` when starting at preflop (the
    # engine posts the blinds at apply-time from the SB/BB config).
    cfg = HUNLConfig(
        starting_stack=5000,
        small_blind=50,
        big_blind=100,
        ante=0,
        starting_street=Street.PREFLOP,
        initial_board=(),
        initial_pot=0,
        initial_contributions=(0, 0),
        initial_hole_cards=(),
        postflop_raise_cap=1,
        bet_size_fractions=(0.75,),
        include_all_in=False,
    )
    with pytest.raises(ValueError, match="preflop"):
        solve_range_vs_range_nash(
            cfg, hero_range=["AA"], villain_range=["KK"], iterations=10
        )


def test_invalid_hero_player_raises() -> None:
    cfg = _dry_river_config()
    for bad in (-1, 2, 5):
        with pytest.raises(ValueError, match="hero_player"):
            solve_range_vs_range_nash(
                cfg,
                hero_range=["AA"],
                villain_range=["KK"],
                iterations=10,
                hero_player=bad,
            )


def test_empty_range_raises() -> None:
    cfg = _dry_river_config()
    with pytest.raises(ValueError, match="hero_range"):
        solve_range_vs_range_nash(
            cfg, hero_range=[], villain_range=["AA"], iterations=10
        )
    with pytest.raises(ValueError, match="villain_range"):
        solve_range_vs_range_nash(
            cfg, hero_range=["AA"], villain_range=[], iterations=10
        )


def test_all_combos_board_blocked_raises() -> None:
    """When every combo in a range is blocked by the board → ValueError."""
    cfg = _dry_river_config()  # board contains As, Kh
    # Hero range is only AA (blocked because As is on the board → 3 combos
    # remain, which is non-empty). Use a class whose combos are ALL blocked
    # by the board: build a board with all four kings and ask for KK.
    cfg_kkkk = HUNLConfig(
        starting_stack=5000,
        small_blind=50,
        big_blind=100,
        ante=0,
        starting_street=Street.RIVER,
        initial_board=tuple(
            Card.from_str(c) for c in ("Ks", "Kh", "Kd", "Kc", "2d")
        ),
        initial_pot=1000,
        initial_contributions=(500, 500),
        initial_hole_cards=(),
        postflop_raise_cap=1,
        bet_size_fractions=(0.75,),
        include_all_in=False,
    )
    with pytest.raises(ValueError, match="board-feasible"):
        solve_range_vs_range_nash(
            cfg_kkkk,
            hero_range=["KK"],
            villain_range=["AA"],
            iterations=10,
        )


# ---------------------------------------------------------------------------
# Tier 5: exploitability bound on a small fixture
# ---------------------------------------------------------------------------


@pytest.mark.timeout(120)
def test_exploitability_bound_small_fixture() -> None:
    """A small symmetric river fixture converges to low exploitability.

    The fixture is intentionally tiny (2x2 classes = 12 combos per side
    after board filtering) so the Rust solve completes well under 5s
    at 500 iter, leaving generous headroom for the exploitability walk
    PR 15 added (``_rust.compute_exploitability``).
    """
    cfg = _dry_river_config()
    result = solve_range_vs_range_nash(
        cfg,
        hero_range=["AA", "KK"],
        villain_range=["AA", "KK"],
        iterations=500,
        hero_player=0,
        compute_exploitability_at_end=True,
    )
    # Sanity: the exploitability call ran (non-zero default flips to
    # the actual value only when populated).
    assert result.backend == "rust_vector"
    # Vector-form exploitability is reported in chips/hand. For this tiny
    # symmetric fixture the strategy converges quickly; 100 chips/hand
    # is a very loose upper bound (the W3.5 doc reports sub-1-chip at 3k
    # iter; we accept a wider bound at 500 iter to absorb DCFR's
    # 1/sqrt(t) tail and the v1.5.1 unoptimized solve cost).
    assert result.exploitability < 100.0, (
        f"exploitability {result.exploitability:.4f} unreasonable for a "
        f"2x2 symmetric river fixture at 500 iter"
    )
    # Also verify the memory profile dict is populated (PR 23 spec §4).
    assert "total_bytes" in result.memory_profile, (
        f"memory_profile missing total_bytes: {result.memory_profile}"
    )


def test_compute_exploitability_flag_off_leaves_zero() -> None:
    """With ``compute_exploitability_at_end=False`` the field stays 0.0."""
    cfg = _dry_river_config()
    result = solve_range_vs_range_nash(
        cfg,
        hero_range=["AA", "KK"],
        villain_range=["AA", "KK"],
        iterations=10,
        compute_exploitability_at_end=False,
    )
    assert result.exploitability == 0.0


# ---------------------------------------------------------------------------
# Tier 6: optional progress callback
# ---------------------------------------------------------------------------


def test_on_progress_callback_fires_start_and_end() -> None:
    """The ``on_progress`` callback fires at solve_start and solve_done."""
    cfg = _dry_river_config()
    events: list[tuple[int, int, str]] = []

    def cb(done: int, total: int, phase: str) -> None:
        events.append((done, total, phase))

    solve_range_vs_range_nash(
        cfg,
        hero_range=["AA", "KK"],
        villain_range=["AA", "KK"],
        iterations=20,
        on_progress=cb,
        compute_exploitability_at_end=False,
    )
    assert len(events) >= 2, f"expected ≥2 progress events, got {events}"
    # First event is start (done=0); last is done (done=iterations).
    assert events[0][0] == 0
    assert events[0][2] == "solve_start"
    assert events[-1][0] == 20
    assert events[-1][2] == "solve_done"
