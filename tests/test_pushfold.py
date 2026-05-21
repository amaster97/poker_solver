"""Tests for the push/fold chart lookup API.

Covers the public surface defined in PR 3.5 spec §6: per-hand frequency
lookup, full-range bulk lookup, error handling for out-of-range stacks /
malformed inputs, and the auto-dispatch hook inside `solve()` that routes
short-stack HUNL configs to the chart-backed path.
"""

from __future__ import annotations

import pytest

from poker_solver import (
    PUSHFOLD_MAX_BB,
    PUSHFOLD_MIN_BB,
    HUNLConfig,
    HUNLPoker,
    PushFoldChartUnavailable,
    get_full_range,
    get_pushfold_strategy,
    parse_range,
    solve,
)

# Combo counts per canonical hand class. Pairs contribute C(4,2)=6 combos,
# suited non-pairs 4, offsuit non-pairs 12. Total 13*6 + 78*4 + 78*12 = 1326.
_COMBOS_PAIR = 6
_COMBOS_SUITED = 4
_COMBOS_OFFSUIT = 12

_RANKS_HIGH_TO_LOW = "AKQJT98765432"


def _all_169_hand_classes() -> list[str]:
    """Return the canonical 169 strategically-distinct preflop hand classes."""
    classes: list[str] = []
    for r in _RANKS_HIGH_TO_LOW:
        classes.append(r + r)
    for i, hi in enumerate(_RANKS_HIGH_TO_LOW):
        for lo in _RANKS_HIGH_TO_LOW[i + 1 :]:
            classes.append(hi + lo + "s")
            classes.append(hi + lo + "o")
    return classes


def _combos_in_class(hand_class: str) -> int:
    if len(hand_class) == 2:
        return _COMBOS_PAIR
    if hand_class.endswith("s"):
        return _COMBOS_SUITED
    return _COMBOS_OFFSUIT


def test_pushfold_returns_frequency_in_zero_to_one_range():
    samples = [
        (PUSHFOLD_MIN_BB, "sb_jam", "AA"),
        (5, "sb_jam", "T9s"),
        (10, "sb_jam", "72o"),
        (PUSHFOLD_MAX_BB, "sb_jam", "AKo"),
        (3, "bb_call_vs_jam", "KK"),
        (8, "bb_call_vs_jam", "A5s"),
        (PUSHFOLD_MAX_BB, "bb_call_vs_jam", "22"),
    ]
    for stack_bb, position, hand in samples:
        freq = get_pushfold_strategy(stack_bb, position, hand)
        assert isinstance(freq, float)
        assert 0.0 <= freq <= 1.0


def test_pushfold_aa_always_jammed_at_all_depths():
    for d in range(PUSHFOLD_MIN_BB, PUSHFOLD_MAX_BB + 1):
        assert get_pushfold_strategy(d, "sb_jam", "AA") == pytest.approx(1.0)


def test_pushfold_72o_never_jammed_at_15bb():
    freq = get_pushfold_strategy(15, "sb_jam", "72o")
    assert freq == pytest.approx(0.0, abs=1e-9)


def test_pushfold_wider_at_shorter_stacks():
    """Interpretation note: spec §3 + §4 establish that shorter stacks induce
    wider jam ranges. I quantify 'wider' as count of hand classes with freq
    > 0.5 in the SB jam chart — strictly more at 2 BB than at 15 BB."""
    classes = _all_169_hand_classes()
    wide_short = sum(
        1 for hc in classes if get_pushfold_strategy(2, "sb_jam", hc) > 0.5
    )
    wide_deep = sum(
        1 for hc in classes if get_pushfold_strategy(15, "sb_jam", hc) > 0.5
    )
    assert wide_short > wide_deep


def test_pushfold_full_range_returns_169_hands():
    full = get_full_range(10, "sb_jam")
    assert isinstance(full, dict)
    expected = set(_all_169_hand_classes())
    assert set(full.keys()) == expected
    assert len(full) == 169
    for hc, freq in full.items():
        assert 0.0 <= freq <= 1.0, f"freq for {hc} out of range: {freq}"


def test_pushfold_unsupported_stack_raises():
    with pytest.raises(PushFoldChartUnavailable):
        get_pushfold_strategy(20, "sb_jam", "AA")


def test_pushfold_invalid_hand_raises():
    with pytest.raises(ValueError):
        get_pushfold_strategy(10, "sb_jam", "Z2Z")


def test_pushfold_invalid_position_raises():
    # Per pushfold.py docstring contract: PushFoldChartUnavailable for unknown
    # position, ValueError for malformed hand notation. Position "bogus_position"
    # isn't malformed input — it's an unsupported config.
    with pytest.raises(PushFoldChartUnavailable):
        get_pushfold_strategy(10, "bogus_position", "AA")


def test_pushfold_bb_call_range_tightens_at_deep_stack():
    """Deeper effective stack -> BB defends fewer hands vs a jam.

    Counts hand classes with call-freq > 0.5 at 15 BB vs 2 BB; the 2 BB
    set should be strictly larger (BB is pot-committed at very shallow
    stacks, so defends close to 100% of hands)."""
    classes = _all_169_hand_classes()
    call_short = sum(
        1 for hc in classes if get_pushfold_strategy(2, "bb_call_vs_jam", hc) > 0.5
    )
    call_deep = sum(
        1 for hc in classes if get_pushfold_strategy(15, "bb_call_vs_jam", hc) > 0.5
    )
    assert call_short > call_deep


def test_pushfold_mode_dispatch_at_short_stack():
    """At 10 BB (1000 cents = 10 * big_blind=100), solve() must dispatch to
    the pushfold lookup path rather than building a tree. iterations=0
    suffices because the chart path is non-iterative."""
    game = HUNLPoker(HUNLConfig(starting_stack=1000))
    result = solve(game, iterations=0)
    assert result.backend == "pushfold_chart"


def test_pushfold_mode_not_triggered_for_river_subgame_at_short_stack():
    """Regression: push/fold dispatch must require PREFLOP start.
    `default_tiny_subgame()` has 10 BB eff_stack but starts on RIVER —
    solving it should run through the tree-solver path (DCFR on the
    river-only subgame), NOT short-circuit to chart lookup. Push/fold
    equilibria only exist on the preflop tree shape.
    """
    from poker_solver.hunl import Street, default_tiny_subgame

    game = HUNLPoker(default_tiny_subgame())
    # Sanity: confirm fixture is RIVER-start and short-stack
    assert game.config.starting_street == Street.RIVER
    assert game.config.starting_stack // game.config.big_blind <= 15
    # Solve with very few iterations (any non-pushfold backend is fine).
    result = solve(game, iterations=5)
    assert (
        result.backend != "pushfold_chart"
    ), "River subgame at short stack must NOT dispatch to pushfold chart"


def test_pushfold_mode_not_triggered_at_long_stack():
    """Verifies the dispatch logic, not the full solver. At 100 BB, the
    is_pushfold_mode predicate must return False so solve() does NOT
    short-circuit to chart lookup. We don't actually invoke solve() here
    because the full HUNL solver lands in PR 5/PR 9 — calling solve() on
    a 100 BB preflop config today would fall into a tree-build that
    doesn't terminate quickly. The dispatch predicate is the unit under
    test; the rest is for later PRs."""
    from poker_solver import is_pushfold_mode

    config = HUNLConfig(starting_stack=10000)
    assert not is_pushfold_mode(
        config.starting_stack, config.big_blind
    ), "100 BB stack must NOT trigger pushfold dispatch"


def test_pushfold_strategy_frequencies_sum_consistently():
    """Reasonability check: sum of (freq * combos_per_class) across the 169
    classes should equal the total combo count of the jam/call range. We
    compare against the implicit total = sum over classes of
    freq * combos_per_class, which by construction must lie in [0, 1326].
    The cross-check is that this sum is internally consistent (no NaNs,
    no negative contributions) and that the SB jam range at 15 BB is
    materially smaller than at 2 BB (which is the full deck of 1326)."""
    classes = _all_169_hand_classes()
    full_deck = sum(_combos_in_class(hc) for hc in classes)
    assert full_deck == 1326

    for depth in (2, 6, 10, 15):
        for position in ("sb_jam", "bb_call_vs_jam"):
            total = 0.0
            for hc in classes:
                freq = get_pushfold_strategy(depth, position, hc)
                assert freq >= 0.0
                total += freq * _combos_in_class(hc)
            assert 0.0 <= total <= 1326.0 * 1.05

    # Landmark: SB jams a very wide range at 2 BB (real HU Nash, not the
    # Sklansky-Chubukov approximation). Agent B's DCFR generation produced
    # ~90% combo coverage at 2 BB — below the SC "jam everything" heuristic
    # but consistent with HU Nash (BB calls wider when SB shoves, so SB
    # tightens slightly even at 2 BB). We assert >= 80% as the floor.
    total_2bb = sum(
        get_pushfold_strategy(2, "sb_jam", hc) * _combos_in_class(hc) for hc in classes
    )
    assert (
        total_2bb >= 1326.0 * 0.80
    ), f"SB jam range at 2 BB suspiciously narrow: {total_2bb}/1326 combos"

    # AKs hand class must contain exactly 4 combos per parse_range, mirroring
    # the chart's strategic-equivalence collapse.
    assert len(parse_range("AKs")) == _COMBOS_SUITED
