"""Integration tests for Premium-A Phase 4 blueprint -> postflop wiring.

Covers the data flow asserted by the Phase 4 prompt:

  1. Blueprint lookup (per-class strategies at history-key infosets).
  2. 169-class -> 1326-combo range expansion (uniform within class).
  3. Postflop subgame solver ingest as range prior.

Tests use small in-memory blueprint fixtures (no engine compute needed
for the blueprint side) so the suite stays under a minute in CI. The
postflop solve itself uses the Rust vector form via
:func:`solve_range_vs_range_nash` — this is the integration the phase is
about, so it has to fire for real, but we keep ranges and iterations
tiny.
"""

from __future__ import annotations

import time

import pytest

# Defensive imports — keep the rest of the suite importable if Phase 4 is
# in flight.
try:
    from poker_solver import (
        Blueprint,
        BlueprintConfig,
        BlueprintContinuationRanges,
        BlueprintPostflopResult,
        Card,
        HUNLConfig,
        Range,
        RangeVsRangeNashResult,
        Street,
        derive_continuation_ranges_from_blueprint,
        expand_classes_to_range,
        solve_postflop_from_blueprint,
    )
    from poker_solver.blueprint import SCHEMA_VERSION
    from poker_solver.range_aggregator import _combo_count
except Exception:  # noqa: BLE001
    Blueprint = None  # type: ignore[assignment,misc]
    BlueprintConfig = None  # type: ignore[assignment,misc]
    BlueprintContinuationRanges = None  # type: ignore[assignment,misc]
    BlueprintPostflopResult = None  # type: ignore[assignment,misc]
    Card = None  # type: ignore[assignment,misc]
    HUNLConfig = None  # type: ignore[assignment,misc]
    Range = None  # type: ignore[assignment,misc]
    RangeVsRangeNashResult = None  # type: ignore[assignment,misc]
    Street = None  # type: ignore[assignment,misc]
    derive_continuation_ranges_from_blueprint = None  # type: ignore[assignment]
    expand_classes_to_range = None  # type: ignore[assignment]
    solve_postflop_from_blueprint = None  # type: ignore[assignment]
    SCHEMA_VERSION = None  # type: ignore[assignment]
    _combo_count = None  # type: ignore[assignment]


pytestmark = pytest.mark.skipif(
    solve_postflop_from_blueprint is None,
    reason="solve_postflop_from_blueprint not importable (Phase 4 surface missing)",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _btn_vs_bb_config(stack_bb: int = 50) -> HUNLConfig:
    """BTN-vs-BB preflop config matching the chained-orchestrator fixture.

    Matches :func:`tests.test_chained_orchestrator._btn_vs_bb_config` so
    the same blueprint trees are usable across phases.
    """
    return HUNLConfig(
        starting_stack=stack_bb * 100,
        small_blind=50,
        big_blind=100,
        starting_street=Street.PREFLOP,
        bet_size_fractions=(),  # tighter — only call/check + all-in
        include_all_in=True,
        preflop_raise_cap=2,
        postflop_raise_cap=1,
    )


def _tiny_two_class_blueprint() -> Blueprint:
    """Build a synthetic blueprint covering only AA + KK at the SB root.

    Action menu at root: ``{call, all_in}`` (matches the tight config in
    :func:`_btn_vs_bb_config`). Both classes call 100% so the resulting
    continuation reaches the flop with reach = 1.0 for both.

    This fixture is small enough that the postflop solve finishes in
    seconds even on a 2x2 grid.
    """
    return Blueprint(
        schema_version=SCHEMA_VERSION,
        config=BlueprintConfig(stack_bb=50, ante_bb=0.0, iterations=10),
        wall_seconds=0.1,
        final_exploitability_bb100=None,
        infosets={
            # SB-root infoset — both AA and KK limp.
            "||p|": {
                "actions": ["call", "all_in"],
                "strategy": {
                    "AA": [1.0, 0.0],
                    "KK": [1.0, 0.0],
                },
            },
            # BB after SB limp — both check (sequence: SB call, BB check).
            "||p|c": {
                "actions": ["check", "all_in"],
                "strategy": {
                    "AA": [1.0, 0.0],
                    "KK": [1.0, 0.0],
                },
            },
        },
    )


def _polarized_two_class_blueprint() -> Blueprint:
    """Blueprint where AA shoves 90 / 10 and KK limps 100 / 0.

    Used to verify reach propagation produces different continuation
    weights per class.
    """
    return Blueprint(
        schema_version=SCHEMA_VERSION,
        config=BlueprintConfig(stack_bb=50, ante_bb=0.0, iterations=10),
        wall_seconds=0.1,
        final_exploitability_bb100=None,
        infosets={
            "||p|": {
                "actions": ["call", "all_in"],
                "strategy": {
                    "AA": [0.1, 0.9],
                    "KK": [1.0, 0.0],
                },
            },
            "||p|c": {
                "actions": ["check", "all_in"],
                "strategy": {
                    "AA": [1.0, 0.0],
                    "KK": [1.0, 0.0],
                },
            },
        },
    )


# ---------------------------------------------------------------------------
# 1. Range expansion (169 -> 1326)
# ---------------------------------------------------------------------------


def test_expand_classes_to_range_uniform_within_class() -> None:
    """Each class expanded to its canonical combo count with equal weights."""
    rng = expand_classes_to_range({"AA": 1.0, "KK": 1.0})
    # AA has 6 combos, KK has 6 combos → 12 total.
    assert len(rng) == 12
    # All weights equal because the two reach weights are equal and the
    # within-class divisor is the same (both pairs = 6 combos).
    weights = [c.weight for c in rng]
    assert max(weights) == pytest.approx(1.0)  # post-renormalization
    assert min(weights) > 0
    # AA + KK = uniform; all should be at the renormalized peak.
    assert all(abs(w - 1.0) < 1e-9 for w in weights)


def test_expand_classes_to_range_class_weight_difference() -> None:
    """Higher class weight produces higher per-combo weight."""
    # AA reach=1.0, KK reach=0.1. Both have 6 combos. AA weight per combo
    # = 1.0/6, KK weight per combo = 0.1/6. After renormalization the
    # AA weight is 1.0 and KK weight is 0.1.
    rng = expand_classes_to_range({"AA": 1.0, "KK": 0.1})
    aa_weights: list[float] = []
    kk_weights: list[float] = []
    for combo in rng:
        c0, c1 = combo.cards
        if c0.rank == 14 and c1.rank == 14:
            aa_weights.append(combo.weight)
        elif c0.rank == 13 and c1.rank == 13:
            kk_weights.append(combo.weight)
    assert len(aa_weights) == 6
    assert len(kk_weights) == 6
    # All AA weights equal; all KK weights equal.
    assert all(abs(w - aa_weights[0]) < 1e-9 for w in aa_weights)
    assert all(abs(w - kk_weights[0]) < 1e-9 for w in kk_weights)
    # AA / KK ratio ≈ 10 (post-renormalization the max is 1.0 and the
    # other is 0.1).
    assert aa_weights[0] / kk_weights[0] == pytest.approx(10.0, rel=1e-6)


def test_expand_classes_to_range_filters_board_blockers() -> None:
    """Combos colliding with the board are removed from the range."""
    # AhAs is blocked when As is on board; the other 5 AA combos remain.
    board = (Card.from_str("As"), Card.from_str("7h"), Card.from_str("2d"))
    rng = expand_classes_to_range({"AA": 1.0}, board=board)
    # 3 AA combos remain: AhAd, AhAc, AdAc (the 3 that don't use As).
    assert len(rng) == 3
    # Verify none of the remaining combos use As.
    blocked = set(board)
    for combo in rng:
        c0, c1 = combo.cards
        assert c0 not in blocked
        assert c1 not in blocked


def test_expand_classes_to_range_rejects_negative_weights() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        expand_classes_to_range({"AA": -0.5})


def test_expand_classes_to_range_empty_input_returns_empty_range() -> None:
    assert len(expand_classes_to_range({})) == 0


# ---------------------------------------------------------------------------
# 2. Reach derivation
# ---------------------------------------------------------------------------


def test_derive_continuation_ranges_root_reach_is_one() -> None:
    """With an empty action sequence, every class reaches with prob 1."""
    bp = _tiny_two_class_blueprint()
    cfg = _btn_vs_bb_config()
    cont = derive_continuation_ranges_from_blueprint(
        bp,
        config_template=cfg,
        action_sequence=(),
        hero_player=0,
    )
    assert set(cont.hero.keys()) == {"AA", "KK"}
    assert set(cont.villain.keys()) == {"AA", "KK"}
    for w in cont.hero.values():
        assert w == pytest.approx(1.0)
    for w in cont.villain.values():
        assert w == pytest.approx(1.0)
    # Pot at root: SB + BB = 50 + 100 = 150 chips.
    assert cont.pot_chips == 150


def test_derive_continuation_ranges_propagates_action_probs() -> None:
    """``("c", "x")`` propagates SB-call * BB-check products per class."""
    bp = _polarized_two_class_blueprint()
    cfg = _btn_vs_bb_config()
    cont = derive_continuation_ranges_from_blueprint(
        bp,
        config_template=cfg,
        action_sequence=("c", "x"),
        hero_player=0,
    )
    # SB at root: AA calls with 0.1, KK calls with 1.0.
    # BB at "||p|c": both check with 1.0.
    # → SB (hero) reach: AA=0.1, KK=1.0
    # → BB (villain) reach: AA=1.0, KK=1.0  (BB's strategy was unchanged
    #   by SB's call — SB acted, not BB, on the first step)
    assert cont.hero == pytest.approx({"AA": 0.1, "KK": 1.0})
    assert cont.villain == pytest.approx({"AA": 1.0, "KK": 1.0})
    # Pot after SB limp + BB check: 100 + 100 = 200 chips.
    assert cont.pot_chips == 200


def test_derive_continuation_ranges_missing_infoset_raises() -> None:
    """An action sequence pointing into uncovered tree raises ValueError."""
    bp = _tiny_two_class_blueprint()
    # Remove the BB-after-limp infoset so the second step has no
    # blueprint coverage.
    bp.infosets.pop("||p|c")
    cfg = _btn_vs_bb_config()
    with pytest.raises(ValueError, match="blueprint missing infoset"):
        derive_continuation_ranges_from_blueprint(
            bp,
            config_template=cfg,
            action_sequence=("c", "x"),
            hero_player=0,
        )


def test_derive_continuation_ranges_filters_classes() -> None:
    """``hero_classes`` / ``villain_classes`` restrict the output dicts."""
    bp = _tiny_two_class_blueprint()
    cfg = _btn_vs_bb_config()
    cont = derive_continuation_ranges_from_blueprint(
        bp,
        config_template=cfg,
        action_sequence=(),
        hero_player=0,
        hero_classes=["AA"],  # only AA on hero side
        villain_classes=["KK"],  # only KK on villain side
    )
    assert set(cont.hero.keys()) == {"AA"}
    assert set(cont.villain.keys()) == {"KK"}


def test_derive_continuation_ranges_rejects_bad_hero_player() -> None:
    bp = _tiny_two_class_blueprint()
    cfg = _btn_vs_bb_config()
    with pytest.raises(ValueError, match="hero_player must be 0"):
        derive_continuation_ranges_from_blueprint(
            bp,
            config_template=cfg,
            action_sequence=(),
            hero_player=2,
        )


# ---------------------------------------------------------------------------
# 3. End-to-end: blueprint → postflop subgame solve
# ---------------------------------------------------------------------------


@pytest.mark.timeout(180)
def test_solve_postflop_from_blueprint_end_to_end_flop() -> None:
    """Full pipeline: 169-class blueprint → 1326 expansion → flop solve.

    Uses a tiny 2-class blueprint (AA + KK) and a dry flop
    (``Qs7h2d``) — the postflop subgame solver runs the Rust vector
    form and returns a finite, simplex-valid strategy. We assert
    the integration (wiring) is correct, not the strategy values.
    """
    bp = _tiny_two_class_blueprint()
    cfg = _btn_vs_bb_config()
    board = (Card.from_str("Qs"), Card.from_str("7h"), Card.from_str("2d"))

    t0 = time.perf_counter()
    result = solve_postflop_from_blueprint(
        bp,
        config_template=cfg,
        action_sequence=("c", "x"),
        board=board,
        hero_player=0,
        iterations=30,  # fast for CI
        compute_exploitability_at_end=False,
    )
    wall = time.perf_counter() - t0

    # Type assertions.
    assert isinstance(result, BlueprintPostflopResult)
    assert isinstance(result.postflop, RangeVsRangeNashResult)
    assert isinstance(result.continuation, BlueprintContinuationRanges)
    assert isinstance(result.hero_range, Range)
    assert isinstance(result.villain_range, Range)

    # Continuation ranges populated.
    assert set(result.continuation.hero.keys()) == {"AA", "KK"}
    assert set(result.continuation.villain.keys()) == {"AA", "KK"}
    assert result.continuation.pot_chips > 0
    assert result.continuation.action_sequence == ("c", "x")

    # Range expansion to combos (6 per pair, board doesn't block either).
    assert len(result.hero_range) == 12  # 6 AA + 6 KK
    assert len(result.villain_range) == 12

    # Postflop solve produced a finite strategy.
    assert result.postflop.backend == "rust_vector"
    assert len(result.postflop.per_history_strategy) > 0
    # Strategy entries should sum to ≈1.0 (simplex-valid).
    for key, probs in result.postflop.per_history_strategy.items():
        total = sum(probs)
        assert abs(total - 1.0) < 1e-3, (
            f"per_history_strategy[{key!r}] sums to {total}, expected 1.0; "
            f"probs={probs}"
        )

    # Per-stage wall times reported.
    assert result.wall_time_lookup_s >= 0
    assert result.wall_time_expand_s >= 0
    assert result.wall_time_solve_s >= 0
    assert (
        result.wall_time_lookup_s
        + result.wall_time_expand_s
        + result.wall_time_solve_s
        <= result.wall_time_total_s + 1e-3
    )
    # Sanity bound — full pipeline should easily fit in <60 s on a 2x2 grid.
    assert wall < 60.0, f"end-to-end took {wall:.1f}s, expected <60s"


@pytest.mark.timeout(180)
def test_solve_postflop_from_blueprint_threads_reach_into_ranges() -> None:
    """Polarized blueprint → postflop sees AA reach scaled by 0.1 vs KK.

    Verifies that the AA-shove blueprint (10% call / 90% jam) actually
    propagates: at the flop the hero range should have AA-combos weighted
    1/10 relative to KK-combos.
    """
    bp = _polarized_two_class_blueprint()
    cfg = _btn_vs_bb_config()
    board = (Card.from_str("Qs"), Card.from_str("7h"), Card.from_str("2d"))

    result = solve_postflop_from_blueprint(
        bp,
        config_template=cfg,
        action_sequence=("c", "x"),
        board=board,
        hero_player=0,
        iterations=30,
        compute_exploitability_at_end=False,
    )

    # Hero (SB) had AA call=0.1 → AA reach=0.1, KK reach=1.0.
    assert result.continuation.hero["AA"] == pytest.approx(0.1)
    assert result.continuation.hero["KK"] == pytest.approx(1.0)

    # Inspect the hero range's per-combo weights.
    aa_weights = [c.weight for c in result.hero_range if c.cards[0].rank == 14]
    kk_weights = [c.weight for c in result.hero_range if c.cards[0].rank == 13]
    assert len(aa_weights) == 6
    assert len(kk_weights) == 6
    # AA combos should each be 0.1x KK combo weight (within the
    # max-renormalization scheme: KK=1.0, AA=0.1).
    assert kk_weights[0] == pytest.approx(1.0)
    assert aa_weights[0] == pytest.approx(0.1, rel=1e-6)


@pytest.mark.timeout(120)
def test_solve_postflop_from_blueprint_validates_board_length() -> None:
    bp = _tiny_two_class_blueprint()
    cfg = _btn_vs_bb_config()
    with pytest.raises(ValueError, match="board must be 3"):
        solve_postflop_from_blueprint(
            bp,
            config_template=cfg,
            action_sequence=("c", "x"),
            board=(Card.from_str("Qs"), Card.from_str("7h")),  # only 2
            hero_player=0,
            iterations=10,
        )


@pytest.mark.timeout(120)
def test_solve_postflop_from_blueprint_rejects_empty_continuation() -> None:
    """If the blueprint forces every class to fold, the pipeline raises."""
    # AA folds 100% at root → after sequence ("f",), hero has zero reach.
    # We use a different sequence here: build a "fold-only" infoset and
    # try to derive continuation along ("f",).
    bp = Blueprint(
        schema_version=SCHEMA_VERSION,
        config=BlueprintConfig(stack_bb=50, ante_bb=0.0, iterations=10),
        wall_seconds=0.1,
        final_exploitability_bb100=None,
        infosets={
            "||p|": {
                "actions": ["fold", "call"],
                "strategy": {
                    "AA": [1.0, 0.0],  # 100% fold (unrealistic; for test)
                    "KK": [1.0, 0.0],
                },
            },
        },
    )
    cfg = _btn_vs_bb_config()
    board = (Card.from_str("Qs"), Card.from_str("7h"), Card.from_str("2d"))
    with pytest.raises(ValueError, match="fold or all-in terminal"):
        solve_postflop_from_blueprint(
            bp,
            config_template=cfg,
            action_sequence=("f",),
            board=board,
            hero_player=0,
            iterations=10,
        )


# ---------------------------------------------------------------------------
# 4. Sample wall-time report (sanity, not strict)
# ---------------------------------------------------------------------------


@pytest.mark.timeout(180)
def test_end_to_end_wall_time_smoke_qs_7h_2d() -> None:
    """Print the end-to-end wall time on the canonical Qs 7h 2d flop.

    Test purpose is to verify the assertion that the full pipeline is
    interactive on a 2-class blueprint. The phase report references this
    fixture's wall time as the "blueprint lookup → postflop subgame solve
    end-to-end" timing.
    """
    bp = _tiny_two_class_blueprint()
    cfg = _btn_vs_bb_config()
    board = (Card.from_str("Qs"), Card.from_str("7h"), Card.from_str("2d"))

    t0 = time.perf_counter()
    result = solve_postflop_from_blueprint(
        bp,
        config_template=cfg,
        action_sequence=("c", "x"),
        board=board,
        hero_player=0,
        iterations=30,
        compute_exploitability_at_end=False,
    )
    total_wall = time.perf_counter() - t0
    # Just emit timing in the test output (collected via pytest -v); the
    # gate is the timeout marker, which is 3 minutes.
    print(
        f"\n[Phase 4 wall-time] total={total_wall:.3f}s, "
        f"lookup={result.wall_time_lookup_s:.3f}s, "
        f"expand={result.wall_time_expand_s:.3f}s, "
        f"solve={result.wall_time_solve_s:.3f}s"
    )
    # The lookup + expand are pure Python, should be tiny.
    assert result.wall_time_lookup_s < 5.0
    assert result.wall_time_expand_s < 1.0
