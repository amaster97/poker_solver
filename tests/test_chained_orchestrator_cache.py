"""Tests for the chained orchestrator's board-isomorphism cache (#56 / #31 Phase B).

The chained orchestrator's lazy postflop solve (``ChainedSolveResult.solve_postflop``)
caches results keyed by ``(action_sequence, _canonicalize_board(board))``. Two
boards in the same suit-isomorphism class (e.g. ``Ks8d2h`` and ``Kh8c2s``) share
a single cached solve — the strategies are mathematically equivalent by
symmetry, so the second query returns the cached object without recomputing.

This test module covers four behaviours:

  1. **Canonicalization identity**: ``_canonicalize_board`` collapses
     suit-equivalent boards to the same key and keeps non-equivalent
     boards distinct.

  2. **Cache hit on isomorphism**: after solving ``Ks8d2h``, a query for
     ``Kh8c2s`` returns the SAME :class:`RangeVsRangeNashResult` object
     (no fresh solve, no new cache entry).

  3. **LRU eviction**: filling the cache to ``max_cache_size`` and then
     adding one more entry evicts the least-recently-used entry; a
     subsequent query that touched a "middle" entry promotes it so it
     survives the next eviction round.

  4. **Cache-hit performance floor**: the second query on an isomorphic
     board completes in <1ms (well under the first-solve cost, which is
     hundreds of milliseconds for the Rust vector-form CFR).
"""

from __future__ import annotations

import time
from collections import OrderedDict

import pytest

try:
    from poker_solver import (
        Card,
        ChainedSolveResult,
        HUNLConfig,
        RangeVsRangeNashResult,
        Street,
        solve_chained,
    )
    from poker_solver.chained import (
        DEFAULT_POSTFLOP_CACHE_MAX_SIZE,
        _canonicalize_board,
    )
except Exception:  # noqa: BLE001 — defensive: keep suite importable
    Card = None  # type: ignore[assignment,misc]
    ChainedSolveResult = None  # type: ignore[assignment,misc]
    HUNLConfig = None  # type: ignore[assignment,misc]
    RangeVsRangeNashResult = None  # type: ignore[assignment,misc]
    Street = None  # type: ignore[assignment,misc]
    solve_chained = None  # type: ignore[assignment]
    DEFAULT_POSTFLOP_CACHE_MAX_SIZE = 0  # type: ignore[assignment]
    _canonicalize_board = None  # type: ignore[assignment]


pytestmark = pytest.mark.skipif(
    solve_chained is None or _canonicalize_board is None,
    reason="solve_chained / _canonicalize_board not importable",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _btn_vs_bb_config(stack_bb: int = 50) -> HUNLConfig:
    """Tight BTN-vs-BB preflop config for fast per-pair solves.

    Mirrors the helper in ``test_chained_orchestrator.py``; reproduced here
    to keep this file self-contained (and to keep the slow chained-solve
    tests independent across modules).
    """
    return HUNLConfig(
        starting_stack=stack_bb * 100,
        small_blind=50,
        big_blind=100,
        starting_street=Street.PREFLOP,
        bet_size_fractions=(),
        include_all_in=True,
        preflop_raise_cap=2,
        postflop_raise_cap=1,
    )


def _make_chained_result(max_cache_size: int = DEFAULT_POSTFLOP_CACHE_MAX_SIZE):
    """Build a small :class:`ChainedSolveResult` shared by the cache tests.

    Uses the same 2x2 (AA / KK) range pattern as the existing
    ``test_chained_orchestrator.py`` smoke tests: small enough to finish
    in ~30s, large enough to produce a populated continuation-range
    structure with at least one flop-reaching terminal.
    """
    cfg = _btn_vs_bb_config(stack_bb=50)
    hero_classes = ["AA", "KK"]
    villain_classes = ["AA", "KK"]
    return solve_chained(
        cfg,
        hero_range=hero_classes,
        villain_range=villain_classes,
        preflop_iterations=30,
        postflop_iterations=30,
        hero_player=0,
        max_cache_size=max_cache_size,
    )


def _first_flop_action_seq(result):
    """Return the first flop-reaching preflop terminal action sequence."""
    assert len(result.continuation_ranges) >= 1, (
        "expected at least one flop-reaching terminal"
    )
    return next(iter(result.continuation_ranges.keys()))


# ---------------------------------------------------------------------------
# 1. Pure-helper test — _canonicalize_board behaviour
# ---------------------------------------------------------------------------


def test_canonicalize_board_collapses_suit_isomorphism() -> None:
    """Boards related by a global suit permutation collapse to one key.

    ``Ks8d2h`` and ``Kh8c2s`` are different concrete boards but they
    are in the same suit-isomorphism class — swap suits s↔h and d↔c
    and the first becomes the second. The canonical key must match.
    """
    b1 = (Card.from_str("Ks"), Card.from_str("8d"), Card.from_str("2h"))
    b2 = (Card.from_str("Kh"), Card.from_str("8c"), Card.from_str("2s"))
    assert _canonicalize_board(b1) == _canonicalize_board(b2)


def test_canonicalize_board_distinguishes_non_isomorphic_boards() -> None:
    """Boards in different suit-iso classes get distinct canonical keys.

    A rainbow K-8-2 board is in a different class than a monotone K-8-2
    board (one has three suits, the other has one). The canonical key
    must distinguish them.
    """
    rainbow = (Card.from_str("Ks"), Card.from_str("8d"), Card.from_str("2h"))
    monotone = (Card.from_str("Ks"), Card.from_str("8s"), Card.from_str("2s"))
    assert _canonicalize_board(rainbow) != _canonicalize_board(monotone)


def test_canonicalize_board_invariant_under_card_order() -> None:
    """The canonical key does not depend on input card order.

    ``(K, 8, 2)`` and ``(2, 8, K)`` are the same flop — sorting inside
    the canonicalization helper means both produce the same key.
    """
    a = (Card.from_str("Ks"), Card.from_str("8d"), Card.from_str("2h"))
    b = (Card.from_str("2h"), Card.from_str("8d"), Card.from_str("Ks"))
    assert _canonicalize_board(a) == _canonicalize_board(b)


# ---------------------------------------------------------------------------
# 2. Cache hit on suit-isomorphic boards — identity + timing
# ---------------------------------------------------------------------------


@pytest.mark.timeout(420)
def test_isomorphic_boards_share_cached_result() -> None:
    """A query for ``Kh8c2s`` after ``Ks8d2h`` returns the cached object.

    Verifies (a) identity — the same :class:`RangeVsRangeNashResult`
    object is returned, and (b) the cache contains exactly ONE entry
    (not two), since both boards canonicalize to the same key.
    """
    result = _make_chained_result()
    action_seq = _first_flop_action_seq(result)

    b1 = (Card.from_str("Ks"), Card.from_str("8d"), Card.from_str("2h"))
    b2 = (Card.from_str("Kh"), Card.from_str("8c"), Card.from_str("2s"))

    first = result.solve_postflop(action_seq, b1)
    second = result.solve_postflop(action_seq, b2)

    assert second is first, (
        "isomorphic boards Ks8d2h / Kh8c2s should share the cached result; "
        "got two distinct objects"
    )
    assert len(result.postflop_cache) == 1, (
        f"expected 1 cache entry (isomorphic boards collapse); got "
        f"{len(result.postflop_cache)} keys={list(result.postflop_cache.keys())}"
    )


@pytest.mark.timeout(420)
def test_isomorphic_boards_yield_identical_strategies() -> None:
    """Querying isomorphic boards through the cache returns identical strategies.

    This is a stronger contract than identity-of-result: even if the
    cache were keyed differently and two solves were issued, the
    resulting strategies must be bit-identical (isomorphism is a
    mathematical symmetry). The cache short-circuits that by returning
    the same object — so the per-class strategy dict is trivially the
    same.
    """
    result = _make_chained_result()
    action_seq = _first_flop_action_seq(result)

    b1 = (Card.from_str("Ks"), Card.from_str("8d"), Card.from_str("2h"))
    b2 = (Card.from_str("Kh"), Card.from_str("8c"), Card.from_str("2s"))

    r1 = result.solve_postflop(action_seq, b1)
    r2 = result.solve_postflop(action_seq, b2)

    # Identity already covered above; this checks the strategy view that
    # downstream consumers (CLI, UI) actually read.
    assert r1.per_class_strategy == r2.per_class_strategy, (
        "isomorphic boards must yield identical per_class_strategy"
    )
    assert r1.range_aggregate == r2.range_aggregate, (
        "isomorphic boards must yield identical range_aggregate"
    )


@pytest.mark.timeout(420)
def test_cache_hit_under_1ms() -> None:
    """The second (isomorphic) query completes in well under a millisecond.

    First solve costs hundreds of ms (Rust vector-form CFR on the flop).
    A cache hit is just a dict lookup + ``move_to_end`` — should be a
    handful of microseconds. We assert a 1ms ceiling to leave headroom
    for CI noise.
    """
    result = _make_chained_result()
    action_seq = _first_flop_action_seq(result)

    b1 = (Card.from_str("Ks"), Card.from_str("8d"), Card.from_str("2h"))
    b2 = (Card.from_str("Kh"), Card.from_str("8c"), Card.from_str("2s"))

    # Prime the cache.
    result.solve_postflop(action_seq, b1)

    t0 = time.perf_counter()
    result.solve_postflop(action_seq, b2)
    elapsed = time.perf_counter() - t0

    assert elapsed < 0.001, (
        f"cache hit on isomorphic board took {elapsed * 1000:.3f}ms; "
        f"expected <1ms"
    )


@pytest.mark.timeout(420)
def test_cache_hit_canonicalization_is_order_invariant() -> None:
    """Querying with reordered board cards still hits the cache.

    The canonical key is invariant under input card ordering, so
    ``(2h, 8d, Ks)`` should hit the entry inserted by ``(Ks, 8d, 2h)``.
    """
    result = _make_chained_result()
    action_seq = _first_flop_action_seq(result)

    b1 = (Card.from_str("Ks"), Card.from_str("8d"), Card.from_str("2h"))
    b1_reordered = (Card.from_str("2h"), Card.from_str("8d"), Card.from_str("Ks"))

    first = result.solve_postflop(action_seq, b1)
    second = result.solve_postflop(action_seq, b1_reordered)
    assert second is first
    assert len(result.postflop_cache) == 1


# ---------------------------------------------------------------------------
# 3. LRU eviction — bounded cache size + recency promotion
# ---------------------------------------------------------------------------


@pytest.mark.timeout(420)
def test_lru_eviction_evicts_oldest_entry() -> None:
    """Filling the cache beyond ``max_cache_size`` evicts the LRU entry.

    We construct three non-isomorphic boards and a cache of size 2:
      1. Solve board A — cache holds {A}
      2. Solve board B — cache holds {A, B}
      3. Solve board C — cache should evict A (oldest), hold {B, C}

    The test confirms ``A`` is GONE from the cache after step 3 and the
    cache size stays at 2.
    """
    result = _make_chained_result(max_cache_size=2)
    action_seq = _first_flop_action_seq(result)

    # Three rainbow boards with non-overlapping ranks so they sit in
    # three different suit-iso classes (the canonical key encodes ranks).
    board_a = (Card.from_str("Ks"), Card.from_str("8d"), Card.from_str("2h"))
    board_b = (Card.from_str("Qs"), Card.from_str("7d"), Card.from_str("3h"))
    board_c = (Card.from_str("Js"), Card.from_str("6d"), Card.from_str("4h"))

    key_a = (action_seq, _canonicalize_board(board_a))
    key_b = (action_seq, _canonicalize_board(board_b))
    key_c = (action_seq, _canonicalize_board(board_c))
    # Sanity: three distinct canonical classes.
    assert len({key_a[1], key_b[1], key_c[1]}) == 3

    result.solve_postflop(action_seq, board_a)
    assert key_a in result.postflop_cache

    result.solve_postflop(action_seq, board_b)
    assert key_a in result.postflop_cache
    assert key_b in result.postflop_cache
    assert len(result.postflop_cache) == 2

    # This insert should evict the LRU entry (key_a, since it has not
    # been touched since insert).
    result.solve_postflop(action_seq, board_c)
    assert len(result.postflop_cache) == 2, (
        f"cache size must stay ≤ max_cache_size=2 after eviction; "
        f"got {len(result.postflop_cache)}"
    )
    assert key_a not in result.postflop_cache, (
        "LRU entry (board_a) should have been evicted on insert of board_c"
    )
    assert key_b in result.postflop_cache
    assert key_c in result.postflop_cache


@pytest.mark.timeout(420)
def test_lru_promotion_on_hit() -> None:
    """A cache hit promotes the entry to most-recently-used.

    Fill the cache, touch the oldest entry (promoting it), insert a
    new entry. The freshly-inserted-but-then-touched entry should
    survive; the middle entry should be evicted instead.

    Sequence:
      1. Solve A → cache: [A]      (A is oldest)
      2. Solve B → cache: [A, B]
      3. Solve A → cache: [B, A]   (A promoted to MRU; B is now oldest)
      4. Solve C → cache: [A, C]   (B evicted)
    """
    result = _make_chained_result(max_cache_size=2)
    action_seq = _first_flop_action_seq(result)

    board_a = (Card.from_str("Ks"), Card.from_str("8d"), Card.from_str("2h"))
    board_b = (Card.from_str("Qs"), Card.from_str("7d"), Card.from_str("3h"))
    board_c = (Card.from_str("Js"), Card.from_str("6d"), Card.from_str("4h"))

    key_a = (action_seq, _canonicalize_board(board_a))
    key_b = (action_seq, _canonicalize_board(board_b))
    key_c = (action_seq, _canonicalize_board(board_c))

    result.solve_postflop(action_seq, board_a)
    result.solve_postflop(action_seq, board_b)
    # Promote A back to MRU.
    result.solve_postflop(action_seq, board_a)
    # Sanity: A is now at the most-recent end of the OrderedDict.
    keys_in_order = list(result.postflop_cache.keys())
    assert keys_in_order[-1] == key_a, (
        f"after hit on A, A should be MRU; got order {keys_in_order!r}"
    )

    # Insert C → B should be evicted (it's the LRU now), A survives.
    result.solve_postflop(action_seq, board_c)
    assert key_a in result.postflop_cache, (
        "A was promoted on hit; should survive eviction"
    )
    assert key_b not in result.postflop_cache, (
        "B should be evicted (LRU after A's promotion)"
    )
    assert key_c in result.postflop_cache
    assert len(result.postflop_cache) == 2


@pytest.mark.timeout(420)
def test_max_cache_size_zero_disables_caching() -> None:
    """``max_cache_size=0`` disables caching — every call recomputes.

    The result object is still returned (correctness preserved), but
    ``postflop_cache`` stays empty across queries. Useful for memory-
    constrained downstream callers who want the lazy entry point
    without the cache footprint.
    """
    result = _make_chained_result(max_cache_size=0)
    action_seq = _first_flop_action_seq(result)
    board = (Card.from_str("Ks"), Card.from_str("8d"), Card.from_str("2h"))

    r1 = result.solve_postflop(action_seq, board)
    assert isinstance(r1, RangeVsRangeNashResult)
    assert len(result.postflop_cache) == 0, (
        "max_cache_size=0 must keep the cache empty"
    )

    r2 = result.solve_postflop(action_seq, board)
    # With caching disabled both calls produce equivalent (but not
    # necessarily ``is``-identical) results — at minimum the per_class
    # strategy structure should still come back.
    assert isinstance(r2, RangeVsRangeNashResult)
    assert set(r2.per_class_strategy.keys()) == set(r1.per_class_strategy.keys())


def test_solve_chained_rejects_negative_max_cache_size() -> None:
    """Negative ``max_cache_size`` is rejected at construction time.

    Use 0 to disable caching; negative values are an obvious programming
    error and must hard-fail (per the silent no-op hazard rule — better
    to ValueError now than silently misbehave later).
    """
    cfg = _btn_vs_bb_config(stack_bb=50)
    with pytest.raises(ValueError, match="max_cache_size"):
        solve_chained(
            cfg,
            hero_range=["AA"],
            villain_range=["KK"],
            max_cache_size=-1,
        )


# ---------------------------------------------------------------------------
# 4. Backwards-compat — postflop_cache type is OrderedDict (not plain dict)
# ---------------------------------------------------------------------------


@pytest.mark.timeout(420)
def test_postflop_cache_is_ordered_dict() -> None:
    """``postflop_cache`` is an :class:`OrderedDict` (not a plain dict).

    Downstream callers may inspect the cache for diagnostic reasons;
    declaring the type contract here pins it against future regressions.
    The LRU eviction implementation depends on the ``move_to_end`` and
    ``popitem(last=False)`` methods, which are :class:`OrderedDict`-only.
    """
    result = _make_chained_result()
    assert isinstance(result.postflop_cache, OrderedDict), (
        f"postflop_cache should be OrderedDict; got "
        f"{type(result.postflop_cache).__name__}"
    )
