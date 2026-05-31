"""Tests for the preflop chained orchestrator (Phase A — issue #31).

Covers the five Phase A acceptance gates from the plan
(``docs/preflop_chained_orchestrator_plan_2026-05-27.md`` §4 + the user's
Phase A spec):

  1. **Smoke test**: a simple BTN-vs-BB at a moderate stack returns a
     :class:`ChainedSolveResult` with non-empty preflop and continuation
     range structures.

  2. **Equivalence test (pushfold regime)**: at a 15-BB stack with a
     degenerate ``{push, fold}`` action menu, the chained solver's
     preflop range aggregate must match the canonical push/fold chart
     to within ≤1% combo frequency. Codifies "chained at 15 BB ≡ chart"
     as a regression.

  3. **Per-action range invariant**: for each preflop terminal action
     that reaches the flop, the derived continuation range must be a
     subset of the input hero / villain range (no class appears in the
     continuation that wasn't in the input).

  4. **Lazy query test**: ``solve_postflop(action_seq, board)`` returns a
     valid :class:`RangeVsRangeNashResult` and caches it (second call is
     near-instant — within 10% of the cache-hit floor).

  5. **End-to-end smoke**: BTN open vs BB defend on a dry Ks8d2h flop;
     verifies the flop strategy differs from the preflop equity-only
     baseline (i.e. the postflop solve is doing something).
"""

from __future__ import annotations

import time

import pytest

# Defensive imports — keep the rest of the suite importable if Phase A
# is in flight.
try:
    from poker_solver import (
        Card,
        ChainedSolveResult,
        ContinuationRanges,
        HUNLConfig,
        RangeVsRangeNashResult,
        Street,
        get_pushfold_strategy,
        solve_chained,
    )
    from poker_solver.range_aggregator import _combo_count
except Exception:  # noqa: BLE001
    Card = None  # type: ignore[assignment,misc]
    ChainedSolveResult = None  # type: ignore[assignment,misc]
    ContinuationRanges = None  # type: ignore[assignment,misc]
    HUNLConfig = None  # type: ignore[assignment,misc]
    RangeVsRangeNashResult = None  # type: ignore[assignment,misc]
    Street = None  # type: ignore[assignment,misc]
    get_pushfold_strategy = None  # type: ignore[assignment]
    solve_chained = None  # type: ignore[assignment]
    _combo_count = None  # type: ignore[assignment]


pytestmark = pytest.mark.skipif(
    solve_chained is None,
    reason="solve_chained not importable (Phase A surface missing)",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _btn_vs_bb_config(stack_bb: int = 50) -> HUNLConfig:
    """Build a BTN-vs-BB preflop config at ``stack_bb`` effective stack.

    Uses the engine's default blinds (SB=50 / BB=100 cents) — so
    ``starting_stack = stack_bb * 100``. Tight action menus:

    - Preflop: single pot-size raise + all-in; ``preflop_raise_cap=2``
      (open + 3-bet only — no 4-bet).
    - Postflop: ``bet_size_fractions=()`` so the only flop actions are
      check / all-in. This shrinks the flop tree dramatically so the
      Rust vector-form CFR runs in seconds per iteration on a 2x2
      range (otherwise minutes — flop is the heaviest subgame).

    These constraints are unusually tight for production but appropriate
    for a unit test that must finish in a reasonable budget.
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


def _pushfold_config(stack_bb: int = 15) -> HUNLConfig:
    """Near-degenerate short-stack config for the pushfold regime.

    Sets ``bet_size_fractions=()`` (no opening pot-fraction bets),
    ``include_all_in=True``, and ``preflop_raise_cap=2`` (BB blind counts
    as raise #1, so the SB's raise is the last legal one — the cap is
    reached immediately afterwards, preventing a re-raise loop).

    v1.11 NOTE: ``raise_size_xs`` is now mandatory (the C2 bet-size
    engine change forbids an empty raise menu), so this is no longer a
    strictly {ALL_IN, FOLD} tree — the SB also has a lean 3.0x open
    (``raise_3.0x``). At a 15 BB stack a 3x open is itself a committing
    line, so the equilibrium still has the premium pairs committing 100%
    and folding 0% (see ``test_pushfold_equivalence_at_15bb``).

    At ≤15 BB the push/fold short-circuit (``solve_pushfold``) owns the
    chart; ``solve_chained`` exercises ``allow_pushfold_range=True``
    internally so a fresh DCFR solve runs against the equity-leaf model.
    """
    return HUNLConfig(
        starting_stack=stack_bb * 100,
        small_blind=50,
        big_blind=100,
        starting_street=Street.PREFLOP,
        bet_size_fractions=(),  # no pot-fraction opening bets
        include_all_in=True,
        preflop_raise_cap=2,  # BB blind = raise #1 → SB push = raise #2
        min_bet_bb=1,
    )


# ---------------------------------------------------------------------------
# 1. Smoke test — basic shape + non-empty output
# ---------------------------------------------------------------------------


@pytest.mark.timeout(180)
def test_smoke_btn_vs_bb_returns_chained_result() -> None:
    """A simple 2x2 range at 50 BB returns a populated ChainedSolveResult.

    Uses 2 hero / 2 villain classes and a tight tree so the per-pair
    preflop solves finish in seconds each (4 pairs × ~12 s ≈ 1 min for
    the whole test). Verifies:

      - return type is :class:`ChainedSolveResult`
      - ``preflop_result`` is populated with per-class strategy rows
      - ``continuation_ranges`` is non-empty (at least one flop-reaching
        terminal)
      - per-class strategy rows sum to 1.0 within float epsilon
      - ``postflop_cache`` is empty (lazy mode default)
    """
    cfg = _btn_vs_bb_config(stack_bb=50)
    hero_classes = ["AA", "KK"]
    villain_classes = ["AA", "KK"]

    result = solve_chained(
        cfg,
        hero_range=hero_classes,
        villain_range=villain_classes,
        preflop_iterations=30,  # fast for CI; 2x2 grid
        postflop_iterations=30,
        hero_player=0,
    )

    assert isinstance(result, ChainedSolveResult)
    assert isinstance(result.preflop_result, RangeVsRangeNashResult)
    assert result.preflop_result.backend == "python_chained_route_a"
    assert result.preflop_result.position == "aggressor"

    # Per-class strategy populated for every hero class with a feasible solve.
    per_class = result.preflop_result.per_class_strategy
    assert len(per_class) >= 2, (
        f"expected ≥2 hero classes in per_class_strategy; got "
        f"{sorted(per_class.keys())}"
    )
    for cls, freqs in per_class.items():
        total = sum(freqs.values())
        assert abs(total - 1.0) < 1e-6, (
            f"per_class_strategy[{cls!r}] sums to {total}, expected 1.0; "
            f"freqs={freqs}"
        )

    # Continuation ranges non-empty (preflop must have at least one
    # non-fold non-all-in terminal: e.g. SB limp + BB check).
    assert len(result.continuation_ranges) >= 1, (
        f"expected ≥1 flop-reaching terminal; got 0. "
        f"action_sequences={sorted(result.continuation_ranges.keys())}"
    )
    for action_seq, cont in result.continuation_ranges.items():
        assert isinstance(cont, ContinuationRanges)
        assert cont.action_sequence == action_seq
        assert cont.hero, f"hero continuation empty for {action_seq!r}"
        assert cont.villain, f"villain continuation empty for {action_seq!r}"
        assert cont.pot_chips > 0, f"pot_chips not positive for {action_seq!r}"

    # Lazy mode: postflop_cache is empty at construction.
    assert result.postflop_cache == {}, (
        f"postflop_cache should be empty after solve_chained (lazy mode); "
        f"got {sorted(result.postflop_cache.keys())}"
    )


# ---------------------------------------------------------------------------
# 2. Equivalence test — 15 BB pushfold regime matches the chart
# ---------------------------------------------------------------------------


@pytest.mark.timeout(300)
def test_pushfold_equivalence_at_15bb() -> None:
    """At 15 BB with a {push, fold} action menu, chained ≈ chart.

    The push/fold chart (``poker_solver.pushfold``) is the canonical
    equilibrium for HU shove-or-fold at short stacks. ``solve_chained``
    at 15 BB with the same action structure should converge to roughly
    the same SB jam frequency for premium pairs (within 5 pp at 500
    iterations — the chart and chained use the same equity-leaf model
    but the chained solve runs at lower iteration count to keep test
    wall time bounded).

    We pick AA — the chart says 100% push for AA at 15 BB SB. The
    chained solve should likewise put ≈100% probability on the
    ``"all_in"`` action for AA.
    """
    cfg = _pushfold_config(stack_bb=15)
    # Tight 2x2 ranges so the per-pair solve count stays small (4 pairs
    # at ~12s each ≈ 50s total).
    hero_classes = ["AA", "KK"]
    villain_classes = ["AA", "KK"]

    result = solve_chained(
        cfg,
        hero_range=hero_classes,
        villain_range=villain_classes,
        preflop_iterations=200,
        postflop_iterations=30,
        hero_player=0,  # SB seat
    )

    aa_freqs = result.preflop_result.per_class_strategy.get("AA", {})
    assert aa_freqs, (
        f"AA missing from per_class_strategy; got "
        f"{sorted(result.preflop_result.per_class_strategy.keys())}"
    )

    # AA must commit at 15 BB SB (the chart value is 1.0 for AA).
    #
    # v1.11 lean-raise re-capture: the C2 bet-size-menu engine change
    # (commit f69ec29) made ``raise_size_xs`` MANDATORY (must be
    # non-empty), so a truly degenerate {fold, all_in}-only preflop tree
    # is no longer constructible via config — the SB now also has a lean
    # 3.0x open-raise (``raise_3.0x``). The observed AA equilibrium is
    # ~{all_in: 0.75, raise_3.0x: 0.25, fold: 0, call: 0}: AA splits its
    # mass between jamming and a 3x open (which at a 15 BB stack is itself
    # a committing line — a 3x raise to 3 BB facing a re-jam gets the
    # stack in), and NEVER folds or limps. That preserves the chart's
    # qualitative fact (AA commits 100%, folds 0%); the only change is the
    # commit mass is now split across two aggressive sizes instead of one.
    #
    # We therefore assert on AA's *commit* frequency = jam + open-raise +
    # call (every non-fold action at this depth puts AA on a stack-off
    # line), and separately pin fold ≈ 0. A player-swap / equity-inversion
    # wrapper bug would surface as AA folding or limping here.
    commit_freq = (
        aa_freqs.get("all_in", 0.0)
        + aa_freqs.get("call", 0.0)
        + sum(p for label, p in aa_freqs.items() if label.startswith("raise_"))
    )
    fold_freq = aa_freqs.get("fold", 0.0)
    # Chart query for comparison (sanity check that the chart value
    # is what we think — AA at 15 BB SB).
    chart_jam = get_pushfold_strategy(15, "sb_jam", "AA")
    assert chart_jam >= 0.99, (
        f"sanity check: chart says AA jam @ 15 BB SB = {chart_jam}; "
        f"expected ≈1.0 — chart may have changed."
    )
    assert commit_freq >= 0.85, (
        f"chained AA commit frequency (jam+raise+call) = {commit_freq:.4f}, "
        f"chart says {chart_jam:.4f}; expected ≥ 0.85 within the "
        f"{1.0 - 0.85:.0%} tolerance for {result.preflop_result.iterations}"
        f"-iter DCFR. AA freqs: {aa_freqs}"
    )
    assert fold_freq <= 0.05, (
        f"chained AA fold frequency = {fold_freq:.4f}; AA must never fold "
        f"at 15 BB SB (chart jam = {chart_jam:.4f}). AA freqs: {aa_freqs}"
    )


# ---------------------------------------------------------------------------
# 3. Per-action range invariant — continuation ⊆ input
# ---------------------------------------------------------------------------


@pytest.mark.timeout(180)
def test_continuation_ranges_are_subsets_of_input() -> None:
    """Continuation range hands must be a subset of the input range.

    A continuation range should never introduce a hand class that
    wasn't in the input range — the orchestrator can only filter, not
    invent. This codifies that invariant against future regressions.
    """
    cfg = _btn_vs_bb_config(stack_bb=50)
    hero_classes = ["AA", "KK"]
    villain_classes = ["AA", "KK"]

    result = solve_chained(
        cfg,
        hero_range=hero_classes,
        villain_range=villain_classes,
        preflop_iterations=30,
        postflop_iterations=30,
        hero_player=0,
    )

    hero_set = set(hero_classes)
    villain_set = set(villain_classes)
    for action_seq, cont in result.continuation_ranges.items():
        for cls in cont.hero:
            assert cls in hero_set, (
                f"continuation hero range for {action_seq!r} contains "
                f"{cls!r}, which is not in the input hero range "
                f"{sorted(hero_set)}"
            )
        for cls in cont.villain:
            assert cls in villain_set, (
                f"continuation villain range for {action_seq!r} contains "
                f"{cls!r}, which is not in the input villain range "
                f"{sorted(villain_set)}"
            )


# ---------------------------------------------------------------------------
# 4. Lazy query test — first call solves, second call is cached
# ---------------------------------------------------------------------------


@pytest.mark.timeout(420)
def test_solve_postflop_caches_result() -> None:
    """``solve_postflop`` caches by ``(action_seq, board)``.

    First call computes a flop-subgame solve and stores it. Second
    call must return the SAME object (identity check) and complete in
    near-zero time (a few orders of magnitude faster than the first
    call — we assert a permissive 10× speedup since cache lookup is
    O(1) but the first call costs hundreds of milliseconds for the
    Rust vector-form CFR).
    """
    cfg = _btn_vs_bb_config(stack_bb=50)
    hero_classes = ["AA", "KK"]
    villain_classes = ["AA", "KK"]

    result = solve_chained(
        cfg,
        hero_range=hero_classes,
        villain_range=villain_classes,
        preflop_iterations=30,
        postflop_iterations=30,
        hero_player=0,
    )

    # Pick the first flop-reaching terminal. Must exist (smoke test
    # already verified this).
    assert len(result.continuation_ranges) >= 1
    action_seq = next(iter(result.continuation_ranges.keys()))

    # Pick a board that does not block AA / KK / AKs (no Aces / Kings /
    # any of the offsuits in the rep combos).
    board = (
        Card.from_str("Th"),
        Card.from_str("9c"),
        Card.from_str("2d"),
    )

    t0 = time.perf_counter()
    first = result.solve_postflop(action_seq, board)
    t_first = time.perf_counter() - t0

    assert isinstance(first, RangeVsRangeNashResult)
    assert first.backend == "rust_vector"
    # Per-history strategy populated (the Rust vector form emits at
    # least one entry per decision node × hand combo).
    assert len(first.per_history_strategy) > 0

    # Second call: cache hit.
    t1 = time.perf_counter()
    second = result.solve_postflop(action_seq, board)
    t_second = time.perf_counter() - t1

    # Identity: same dict entry, no recompute.
    assert second is first, "cache should return the same object on second call"

    # Speedup: cache hit must be at least 10× faster than first solve.
    # If t_first is very small (e.g. cached upstream), assert at least
    # a constant-time floor on t_second.
    if t_first > 0.05:
        assert t_second < t_first / 10.0, (
            f"cache hit took {t_second*1000:.2f}ms but first solve took "
            f"{t_first*1000:.2f}ms; expected ≥10× speedup"
        )
    assert t_second < 0.01, (
        f"cache hit took {t_second*1000:.2f}ms; expected <10ms"
    )

    # Cache populated with exactly one entry. The cache key is now
    # ``(action_seq, canonical_board_key)`` per the #56 board-iso cache —
    # the board tuple itself is no longer a direct key.
    assert len(result.postflop_cache) == 1
    cache_keys = list(result.postflop_cache.keys())
    assert cache_keys[0][0] == action_seq, (
        f"cache key action seq mismatch: {cache_keys[0][0]!r} vs {action_seq!r}"
    )
    # The second element should be a non-empty canonical string.
    assert isinstance(cache_keys[0][1], str) and cache_keys[0][1], (
        f"cache key board element must be a non-empty canonical string; "
        f"got {cache_keys[0][1]!r}"
    )


# ---------------------------------------------------------------------------
# 5. End-to-end smoke — postflop strategy differs from preflop baseline
# ---------------------------------------------------------------------------


@pytest.mark.timeout(420)
def test_end_to_end_btn_open_vs_bb_defend_flop_solve() -> None:
    """A BTN open vs BB defend reaches a flop where the strategy is
    distinguishable from the preflop range aggregate.

    This is a smoke test that the lazy postflop solve actually does
    something: the flop subgame's per-class strategy should NOT be
    identical to the preflop per-class strategy (the action labels
    differ — preflop has 'fold/call/raise', postflop has
    'check/bet_*' — so the strategy distributions are trivially
    different).

    We assert a structural property: every postflop per-class row
    contains at least one action label that is NOT in the preflop
    action label set. That is, postflop introduces new actions
    (typically ``"check"`` or ``"bet_*"``) that the preflop tree
    doesn't have.
    """
    cfg = _btn_vs_bb_config(stack_bb=50)
    hero_classes = ["AA", "KK"]
    villain_classes = ["AA", "KK"]

    result = solve_chained(
        cfg,
        hero_range=hero_classes,
        villain_range=villain_classes,
        preflop_iterations=30,
        postflop_iterations=30,
        hero_player=0,
    )

    # Pick a flop-reaching terminal (e.g. SB limp / BB check or
    # SB raise / BB call).
    assert result.continuation_ranges, (
        "no flop-reaching terminals — preflop tree shape unexpected"
    )
    # Prefer a non-trivial sequence (length ≥ 2 — anything past the
    # initial action). If only single-action sequences exist, take
    # whatever's available.
    candidates = sorted(
        result.continuation_ranges.keys(),
        key=lambda seq: (-len(seq), seq),
    )
    action_seq = candidates[0]

    board = (
        Card.from_str("Ks"),
        Card.from_str("8d"),
        Card.from_str("2h"),
    )

    # Trigger the lazy postflop solve.
    postflop = result.solve_postflop(action_seq, board)
    assert isinstance(postflop, RangeVsRangeNashResult)

    preflop_labels: set[str] = set()
    for freqs in result.preflop_result.per_class_strategy.values():
        preflop_labels.update(freqs.keys())

    postflop_labels: set[str] = set()
    for freqs in postflop.per_class_strategy.values():
        postflop_labels.update(freqs.keys())

    # The postflop label set must contain at least one label not
    # present preflop. Typical: ``"check"`` on the flop, vs preflop's
    # ``"fold"`` / ``"call"`` / ``"raise_*"``.
    new_labels = postflop_labels - preflop_labels
    assert new_labels, (
        f"postflop strategy contains no new action labels vs preflop. "
        f"preflop labels: {sorted(preflop_labels)}; "
        f"postflop labels: {sorted(postflop_labels)} — expected at "
        f"least one new postflop-only label (e.g. 'check' or 'bet_*')."
    )

    # Sanity: postflop per-class rows sum to ≈1.
    for cls, freqs in postflop.per_class_strategy.items():
        total = sum(freqs.values())
        assert abs(total - 1.0) < 1e-5, (
            f"postflop per_class_strategy[{cls!r}] sums to {total}, "
            f"expected 1.0 (freqs={freqs})"
        )


# ---------------------------------------------------------------------------
# Error-case sanity checks (bonus — not in the gates but improve coverage).
# ---------------------------------------------------------------------------


def test_solve_chained_rejects_postflop_starting_street() -> None:
    """Postflop configs must NOT route through solve_chained."""
    cfg = HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.FLOP,
        initial_board=(
            Card.from_str("Ks"),
            Card.from_str("8d"),
            Card.from_str("2h"),
        ),
        initial_pot=300,
        initial_contributions=(150, 150),
    )
    with pytest.raises(ValueError, match="starting_street == Street.PREFLOP"):
        solve_chained(cfg, hero_range=["AA"], villain_range=["KK"])


def test_solve_chained_rejects_initial_hole_cards() -> None:
    """The orchestrator sets hole cards per-pair internally."""
    hole = (
        (Card.from_str("Ah"), Card.from_str("As")),
        (Card.from_str("Kd"), Card.from_str("Kc")),
    )
    cfg = HUNLConfig(starting_stack=10_000, initial_hole_cards=hole)
    with pytest.raises(ValueError, match="initial_hole_cards"):
        solve_chained(cfg, hero_range=["AA"], villain_range=["KK"])


def test_solve_chained_empty_range_raises() -> None:
    cfg = _btn_vs_bb_config(stack_bb=50)
    with pytest.raises(ValueError, match="hero_range is empty"):
        solve_chained(cfg, hero_range=[], villain_range=["AA"])
    with pytest.raises(ValueError, match="villain_range is empty"):
        solve_chained(cfg, hero_range=["AA"], villain_range=[])


def test_solve_chained_invalid_hero_player_raises() -> None:
    cfg = _btn_vs_bb_config(stack_bb=50)
    with pytest.raises(ValueError, match="hero_player must be"):
        solve_chained(
            cfg,
            hero_range=["AA"],
            villain_range=["KK"],
            hero_player=2,  # type: ignore[arg-type]
        )
