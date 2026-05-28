"""Preflop chained orchestrator — Phase A (issue #31).

Reproduces PioSolver-style preflop → postflop chain solves on top of the
existing per-hand subgame solver. The orchestrator does THREE things:

  1. Stage 1 — solve the preflop range-vs-range subgame via Route A
     "blueprint aggregation": for each (hero_class, villain_class) pair,
     pick representative combos and run ``solve_hunl_preflop``; then
     combo-weighted-average the hero / villain per-class strategies into
     a single :class:`RangeVsRangeNashResult`-shaped preflop result.

  2. Stage 2 — enumerate preflop terminal action sequences. For each
     terminal that reaches the flop (i.e. neither player folded), derive
     a continuation range per player by reach-probability propagation:
     ``cont_weight[class] = combo_count(class) × Π action_prob along
     the path``.

  3. Stage 3 — LAZY postflop solve. The orchestrator returns a result
     object whose ``solve_postflop(action_seq, board)`` method invokes
     ``solve_range_vs_range_nash`` on the derived continuation ranges,
     with the matched preflop pot threaded in as
     ``initial_contributions`` / ``initial_pot``. Results are cached
     by ``(canonical_action_sequence, board)``.

**Scope (Phase A only):**

- Python only. No Rust changes. The internal preflop solve reuses
  :func:`poker_solver.solve_hunl_preflop` (subgame mode, fixed hole
  cards per representative combo).
- Single-pass (no preflop ↔ postflop iteration loop). Per user-confirmed
  decision Q1; the iterated PioSolver flavor is post-Phase-A.
- Lazy postflop only. No pre-solve of 30 or 1755 representative flops
  (those land in Phase B).
- Route A: reuses :func:`solve_hunl_preflop` for every per-hand subgame.
  When the parallel #32 vector-form preflop engine lands, we swap the
  internal :func:`_solve_preflop_range` body — public API stays stable.

**Caveats:**

- The Stage 1 blueprint aggregation pattern produces approximate
  range-level frequencies; for premium-vs-premium spots on dry boards
  it is tight, on wide / polarized ranges it can shift several
  percentage points (same caveat as
  :func:`solve_range_vs_range`).
- The Stage 2 reach derivation uses the SOLVED preflop strategy for
  EACH (class, history) pair extracted from the per-hand solves; this
  approximates the full joint-Nash reach. For 4-bet or deeper lines
  with narrow continuation ranges the resulting flop solve may be
  unstable.
- The lazy postflop solve threads ``solve_range_vs_range_nash``
  (true joint-Nash via Rust vector-form CFR) which is the right
  thing — flop solves benefit most from the vector form.

This module is intentionally surgical: it does NOT modify
``solve_hunl_preflop`` or ``solve_hunl_postflop``; both are wrapped.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from poker_solver.abstraction.equity_features import canonicalize_for_suit_iso
from poker_solver.card import Card
from poker_solver.hunl import HUNLConfig, HUNLPoker, HUNLState, Street
from poker_solver.preflop import PreflopSolveResult, solve_hunl_preflop
from poker_solver.pushfold import is_pushfold_mode
from poker_solver.range import Range
from poker_solver.range_aggregator import (
    HandClass,
    RangeVsRangeNashResult,
    _aggregate_range,
    _combo_count,
    _enumerate_combos,
    _label_for_action,
    _normalize_range,
    solve_range_vs_range_nash,
)

# ---------------------------------------------------------------------------
# Board-isomorphism cache (task #56 / issue #31 Phase B)
# ---------------------------------------------------------------------------

#: Default maximum number of (action_seq, canonical_board) entries kept in
#: ``ChainedSolveResult.postflop_cache``. LRU eviction kicks in once full.
#: 100 entries × ~MB per :class:`RangeVsRangeNashResult` is a few hundred MB
#: ceiling — well below the desktop tier's RAM budget for the typical study
#: workflow (≤30 representative flops × handful of action sequences).
DEFAULT_POSTFLOP_CACHE_MAX_SIZE = 100


def _canonicalize_board(board: Sequence[Card]) -> str:
    """Return the suit-isomorphism canonical key for ``board``.

    Wraps :func:`poker_solver.abstraction.equity_features.canonicalize_for_suit_iso`
    in a board-only entry point. Two boards in the same suit-isomorphism
    class (e.g. ``Ks8d2h`` and ``Kh8c2s``) produce the same canonical
    string — the chained orchestrator uses this string as part of its
    postflop cache key so isomorphic queries share a single solve.

    The underlying function requires a 2-card hand to validate against
    board collisions; we synthesize a placeholder hand from any two cards
    not on the board (the chosen permutation depends only on the board,
    not the hand, so the placeholder is purely a precondition satisfier).

    Args:
        board: 3 community cards (flop). Phase A only supports flop
            subgames; length is asserted by the caller.

    Returns:
        Canonical board key string of the form
        ``"r{rank}s{suit}_r{rank}s{suit}_r{rank}s{suit}"``.

    Raises:
        ValueError: ``board`` has fewer than 3 cards or contains duplicates.
            (Forwarded from the underlying canonicalization helper.)
    """
    # Pick any two distinct cards not on the board to satisfy the hand-vs-
    # board no-collision precondition of canonicalize_for_suit_iso. The
    # canonical board key depends only on the board, so the choice of
    # placeholder is irrelevant to the returned string.
    board_set = set(board)
    placeholder: list[Card] = []
    for rank in range(2, 15):
        for suit in range(4):
            c = Card(rank, suit)
            if c not in board_set:
                placeholder.append(c)
                if len(placeholder) == 2:
                    break
        if len(placeholder) == 2:
            break
    if len(placeholder) < 2:  # pragma: no cover — 52-card deck always has spares
        raise ValueError(
            f"_canonicalize_board: could not synthesize placeholder hand for "
            f"board={list(board)} (deck exhausted?)"
        )
    canonical_string, _perm_index = canonicalize_for_suit_iso(
        tuple(board), (placeholder[0], placeholder[1])
    )
    return canonical_string


# ---------------------------------------------------------------------------
# Public type aliases
# ---------------------------------------------------------------------------

PreflopActionSequence = tuple[str, ...]
"""Sequence of preflop action tokens reaching a terminal frontier.

Each token is the engine's per-action token: ``"f"`` (fold), ``"c"``
(call), ``"x"`` (check), ``"A"`` (all-in), ``"b{N}"`` (opening bet to
N chips), ``"r{N}"`` (raise to N chips). The full sequence matches the
``current_street_tokens`` tuple at the preflop close (or, for fold
terminals, the prefix up to the fold action).
"""

BoardTuple = tuple[Card, ...]
"""Flop board cards (length 3 for Phase A — flop subgames only)."""


@dataclass
class ContinuationRanges:
    """Per-player continuation range after a preflop terminal action.

    Both ranges are stored as ``{hand_class: weight}`` dicts, where
    ``weight`` is the combo-weighted reach probability into this terminal
    for that hand class. The weights are NOT normalized to sum to 1 by
    default — the raw weighted-combo counts are preserved so a caller
    can read off relative class survival.

    Attributes:
        hero: ``{hand_class: weight}`` for hero.
        villain: ``{hand_class: weight}`` for villain.
        pot_chips: Total contested chips at the end of the preflop
            sequence (matched, so each player put in ``pot_chips // 2``
            beyond their respective initial blind). Used to thread
            ``initial_contributions`` / ``initial_pot`` into the
            downstream postflop solve.
        action_sequence: The preflop sequence that produced these
            ranges (mirror of the dict key for convenience).
    """

    hero: dict[HandClass, float] = field(default_factory=dict)
    villain: dict[HandClass, float] = field(default_factory=dict)
    pot_chips: int = 0
    action_sequence: PreflopActionSequence = ()


@dataclass
class ChainedSolveResult:
    """Output of :func:`solve_chained`.

    The result composes:
      - ``preflop_result`` — a :class:`RangeVsRangeNashResult` (built
        via Route A blueprint aggregation) describing the preflop
        strategy.
      - ``continuation_ranges`` — per preflop terminal action that
        reaches the flop, the derived hero / villain continuation
        ranges (see :class:`ContinuationRanges`).
      - ``postflop_cache`` — lazy cache of postflop solves, populated by
        :meth:`solve_postflop`. Keyed by ``(action_sequence,
        canonical_board_key)`` — suit-isomorphic boards (e.g. ``Ks8d2h``
        and ``Kh8c2s``) share a single cached entry per the #56 / #31
        Phase B board-isomorphism optimization. The cache is an
        :class:`collections.OrderedDict` with LRU eviction once
        ``max_cache_size`` entries are present. Empty on construction.

    Query helpers:
      - :meth:`query` returns a (action_label -> prob) dict for a hand
        class at a specific frontier. With ``board=None`` it returns
        the hero's preflop first-decision strategy for that class.
        With ``board`` set it returns the postflop first-decision
        strategy for that class after the specified preflop action
        sequence.
      - :meth:`solve_postflop` is the lazy entry point: solves the
        postflop subgame for ``(action_sequence, board)`` on demand,
        caches the result, and returns the
        :class:`RangeVsRangeNashResult`.
    """

    preflop_result: RangeVsRangeNashResult
    continuation_ranges: dict[PreflopActionSequence, ContinuationRanges] = field(
        default_factory=dict
    )
    # Cache key is ``(action_sequence, canonical_board_key)``. The canonical
    # key is a string produced by ``_canonicalize_board`` so any two boards
    # in the same suit-isomorphism class collapse to a single entry. Stored
    # as an :class:`OrderedDict` to support LRU eviction (move-to-end on
    # hit, popitem(last=False) on overflow).
    postflop_cache: OrderedDict[
        tuple[PreflopActionSequence, str], RangeVsRangeNashResult
    ] = field(default_factory=OrderedDict)

    # Internal state — config + ranges retained for the lazy postflop entry.
    _config_template: HUNLConfig | None = None
    _hero_classes: list[HandClass] = field(default_factory=list)
    _villain_classes: list[HandClass] = field(default_factory=list)
    _postflop_iterations: int = 500
    _hero_player: int = 0
    _max_cache_size: int = DEFAULT_POSTFLOP_CACHE_MAX_SIZE

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------
    def query(
        self,
        hand_class: HandClass,
        action_sequence: PreflopActionSequence = (),
        board: BoardTuple | None = None,
    ) -> dict[str, float]:
        """Return action frequencies for ``hand_class`` at the requested frontier.

        Args:
            hand_class: e.g. ``"AA"``, ``"JJ"``, ``"AKs"``, ``"76o"``.
            action_sequence: Preflop sequence so far (token tuple). For
                ``board=None`` queries this is ignored and the preflop
                first-decision strategy is returned. For postflop
                queries it picks which terminal's continuation range
                drives the flop solve.
            board: Optional 3-card flop tuple. When ``None`` (default),
                returns the preflop first-decision strategy for hero.
                When set, triggers / consults the cached postflop solve
                for ``(action_sequence, board)`` and returns hero's
                flop first-decision strategy for that hand class.

        Returns:
            ``{action_label: probability}`` dict.

        Raises:
            KeyError: ``hand_class`` is not in the input hero range, or
                the requested ``action_sequence`` did not reach the flop
                (no continuation range derived).
        """
        if board is None:
            per_class = self.preflop_result.per_class_strategy
            if hand_class not in per_class:
                raise KeyError(
                    f"hand_class {hand_class!r} not in preflop "
                    f"per_class_strategy; available: "
                    f"{sorted(per_class.keys())}"
                )
            return dict(per_class[hand_class])
        # Postflop query — trigger / consult the lazy cache.
        postflop = self.solve_postflop(action_sequence, board)
        per_class_post = postflop.per_class_strategy
        if hand_class not in per_class_post:
            raise KeyError(
                f"hand_class {hand_class!r} not in postflop "
                f"per_class_strategy for action_sequence={action_sequence!r} "
                f"board={board!r}; available: {sorted(per_class_post.keys())}"
            )
        return dict(per_class_post[hand_class])

    def solve_postflop(
        self,
        action_sequence: PreflopActionSequence,
        board: BoardTuple,
    ) -> RangeVsRangeNashResult:
        """Solve (or fetch cached) postflop subgame for the given frontier.

        The cache is keyed by ``(action_sequence,
        _canonicalize_board(board))`` — so two boards that are
        suit-isomorphic (e.g. ``Ks8d2h`` and ``Kh8c2s``) share one
        cached solve. When the cache is full (``len() >= max_cache_size``)
        the least-recently-used entry is evicted before the new entry is
        inserted. Cache hits move the entry to the most-recent end.

        Args:
            action_sequence: Preflop terminal action sequence reaching
                the flop. Must be a key of ``continuation_ranges``.
            board: 3-card flop tuple. Hands in the continuation range
                that collide with the board are filtered out by
                :func:`solve_range_vs_range_nash`.

        Returns:
            A :class:`RangeVsRangeNashResult` for the flop subgame.
            First call (per canonical class) computes + caches;
            subsequent calls within the same isomorphism class are O(1).

        Raises:
            KeyError: ``action_sequence`` is not in
                ``continuation_ranges``.
            ValueError: ``board`` is not length 3 (Phase A: flop only).
        """
        if action_sequence not in self.continuation_ranges:
            raise KeyError(
                f"action_sequence {action_sequence!r} not in "
                f"continuation_ranges; available: "
                f"{sorted(self.continuation_ranges.keys())}"
            )
        if len(board) != 3:
            raise ValueError(
                f"Phase A only supports flop subgames; got board with "
                f"{len(board)} cards: {board!r}"
            )

        canonical_key = _canonicalize_board(board)
        cache_key = (action_sequence, canonical_key)
        cached = self.postflop_cache.get(cache_key)
        if cached is not None:
            # LRU bookkeeping: mark this entry as most-recently-used.
            self.postflop_cache.move_to_end(cache_key)
            return cached

        if self._config_template is None:  # pragma: no cover
            raise RuntimeError(
                "ChainedSolveResult missing _config_template; constructed "
                "outside of solve_chained()?"
            )
        result = _run_postflop_subgame(
            config_template=self._config_template,
            continuation=self.continuation_ranges[action_sequence],
            board=board,
            iterations=self._postflop_iterations,
            hero_player=self._hero_player,
        )
        # LRU eviction: evict the oldest entry BEFORE inserting the new one
        # so the cache never exceeds ``_max_cache_size``. A ``_max_cache_size``
        # of 0 disables caching entirely (every call recomputes).
        if self._max_cache_size > 0:
            while len(self.postflop_cache) >= self._max_cache_size:
                self.postflop_cache.popitem(last=False)
            self.postflop_cache[cache_key] = result
        return result


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def solve_chained(
    config_template: HUNLConfig,
    hero_range: Sequence[HandClass] | Range,
    villain_range: Sequence[HandClass] | Range,
    *,
    preflop_iterations: int = 10_000,
    postflop_iterations: int = 500,
    hero_player: int = 0,
    villain_reps: int | None = None,
    on_progress: Callable[[str, int, int], None] | None = None,
    dcfr_kwargs: Mapping[str, Any] | None = None,
    max_cache_size: int = DEFAULT_POSTFLOP_CACHE_MAX_SIZE,
) -> ChainedSolveResult:
    """Solve a preflop chained range-vs-range query (PioSolver chain-style).

    Phase A pipeline (per
    ``docs/preflop_chained_orchestrator_plan_2026-05-27.md``):

      1. **Stage 1 — Preflop range solve via Route A blueprint aggregation.**
         Iterate over ``(hero_class, villain_class)`` representative-combo
         pairs, call :func:`solve_hunl_preflop` for each, then combo-
         weighted-average the per-class first-decision frequencies into
         a :class:`RangeVsRangeNashResult` view.

      2. **Stage 2 — Continuation-range derivation.** Enumerate preflop
         terminal action sequences via :func:`_enumerate_preflop_terminals`;
         for each terminal that reaches the flop, compute per-player
         continuation ranges by reach-probability propagation through the
         solved per-hand strategies (see
         :func:`_derive_continuation_ranges`).

      3. **Stage 3 — Lazy postflop solve.** Returns a
         :class:`ChainedSolveResult` with an empty ``postflop_cache``;
         postflop solves only fire when the caller invokes
         :meth:`ChainedSolveResult.solve_postflop` for a specific
         ``(action_sequence, board)`` pair.

    Args:
        config_template: ``HUNLConfig`` with ``starting_street == PREFLOP``
            and EMPTY ``initial_hole_cards``. The orchestrator overrides
            ``initial_hole_cards`` per-pair internally; pass ``()`` here.
        hero_range: hero range as hand-class labels or a ``Range``.
        villain_range: same for villain.
        preflop_iterations: DCFR iterations per per-hand preflop solve.
            Default 10,000 (matches :func:`solve_hunl_preflop` default).
        postflop_iterations: DCFR iterations passed to the lazy postflop
            solver. Default 500 (matches :func:`solve_range_vs_range_nash`
            default).
        hero_player: 0 (aggressor / SB-button) or 1 (defender / BB).
            The reported preflop / postflop frequencies are this player's.
        villain_reps: Representative villain classes used per hero-class
            preflop solve. ``None`` (default) → use all villain classes
            (each hero-villain pair gets its own preflop solve). Pass a
            positive integer to limit cost: e.g. ``villain_reps=3`` uses
            only the first three villain classes per hero class.
        on_progress: Optional callback fired between stages.
            Signature: ``(stage_name, done, total)``. Stages are
            ``"preflop"`` (during the per-pair preflop solves) and
            ``"continuation"`` (during the Stage 2 derivation). Postflop
            solves are lazy and do not fire this callback.
        dcfr_kwargs: Forwarded to each :func:`solve_hunl_preflop` call
            (DCFR hyperparameter overrides — typically leave as None;
            α=1.5/β=0/γ=2.0 are PLAN.md locked).
        max_cache_size: Maximum number of ``(action_sequence,
            canonical_board)`` entries kept in the result's
            ``postflop_cache``. When full, least-recently-used entries
            are evicted. Default
            :data:`DEFAULT_POSTFLOP_CACHE_MAX_SIZE` (100). Pass ``0``
            to disable caching (every postflop query recomputes).
            Suit-isomorphic boards collapse to one entry per the #56
            board-iso cache, so 100 entries spans dozens of distinct
            action sequences × dozens of canonical flop classes.

    Returns:
        A :class:`ChainedSolveResult` with the Stage 1 preflop result,
        Stage 2 continuation ranges per terminal, and an empty
        ``postflop_cache`` (populated lazily).

    Raises:
        ValueError: ``starting_street != PREFLOP``;
            ``initial_hole_cards`` is set (orchestrator overrides
            internally); ``hero_player`` not in (0, 1); empty hero /
            villain range; non-zero rake.
    """
    # ---- Validation -----------------------------------------------------
    if max_cache_size < 0:
        raise ValueError(
            f"max_cache_size must be ≥ 0; got {max_cache_size!r} "
            "(use 0 to disable caching)"
        )
    if hero_player not in (0, 1):
        raise ValueError(
            f"hero_player must be 0 (aggressor) or 1 (defender); got "
            f"{hero_player!r}"
        )
    if config_template.starting_street != Street.PREFLOP:
        raise ValueError(
            f"solve_chained requires starting_street == Street.PREFLOP; got "
            f"{config_template.starting_street!r}"
        )
    if config_template.initial_hole_cards:
        raise ValueError(
            "solve_chained sets initial_hole_cards per-pair internally; "
            "pass config_template with initial_hole_cards=()"
        )
    if config_template.rake_rate != 0.0 or config_template.rake_cap != 0:
        raise ValueError(
            "solve_chained does not support rake yet; set rake_rate=0.0 "
            "and rake_cap=0."
        )

    hero_classes = _normalize_range(hero_range)
    villain_classes = _normalize_range(villain_range)
    if not hero_classes:
        raise ValueError("hero_range is empty after parsing")
    if not villain_classes:
        raise ValueError("villain_range is empty after parsing")

    # ---- Stage 1: preflop range solve -----------------------------------
    preflop_result, per_pair_strategies = _solve_preflop_range(
        config_template=config_template,
        hero_classes=hero_classes,
        villain_classes=villain_classes,
        iterations=preflop_iterations,
        hero_player=hero_player,
        villain_reps=villain_reps,
        on_progress=on_progress,
        dcfr_kwargs=dict(dcfr_kwargs or {}),
    )

    # ---- Stage 2: enumerate preflop terminals + derive continuation ranges
    if on_progress is not None:
        on_progress("continuation", 0, 1)
    terminals = _enumerate_preflop_terminals(config_template)
    continuation_ranges: dict[PreflopActionSequence, ContinuationRanges] = {}
    for action_seq, term_state in terminals:
        cont = _derive_continuation_ranges(
            action_sequence=action_seq,
            terminal_state=term_state,
            config_template=config_template,
            hero_classes=hero_classes,
            villain_classes=villain_classes,
            per_pair_strategies=per_pair_strategies,
            hero_player=hero_player,
        )
        if cont is None:
            continue
        continuation_ranges[action_seq] = cont
    if on_progress is not None:
        on_progress("continuation", 1, 1)

    # ---- Stage 3: build result (postflop_cache is empty / lazy) ---------
    return ChainedSolveResult(
        preflop_result=preflop_result,
        continuation_ranges=continuation_ranges,
        postflop_cache=OrderedDict(),
        _config_template=config_template,
        _hero_classes=list(hero_classes),
        _villain_classes=list(villain_classes),
        _postflop_iterations=postflop_iterations,
        _hero_player=hero_player,
        _max_cache_size=max_cache_size,
    )


# ---------------------------------------------------------------------------
# Stage 1 — preflop range solve via Route A blueprint aggregation
# ---------------------------------------------------------------------------


def _solve_preflop_range(
    *,
    config_template: HUNLConfig,
    hero_classes: list[HandClass],
    villain_classes: list[HandClass],
    iterations: int,
    hero_player: int,
    villain_reps: int | None,
    on_progress: Callable[[str, int, int], None] | None,
    dcfr_kwargs: dict[str, Any],
) -> tuple[
    RangeVsRangeNashResult,
    dict[tuple[HandClass, HandClass], PreflopSolveResult],
]:
    """Stage 1 — blueprint-aggregation preflop solve (Route A).

    For each ``(hero_class, villain_class)`` pair (with up to
    ``villain_reps`` villain classes), pick a single representative combo
    per class and call :func:`solve_hunl_preflop`. The per-pair
    :class:`PreflopSolveResult` is stored so Stage 2 can walk per-pair
    strategies for reach derivation.

    Per-class hero strategy is the average across villain reps of the
    representative combo's first-decision row. Combo-weighted aggregation
    across hero classes produces the range aggregate.

    Returns ``(preflop_result, per_pair_strategies)`` where the second is
    a dict ``{(hero_class, villain_class): PreflopSolveResult}`` used by
    Stage 2.
    """
    hero_combos = {cls: _enumerate_combos(cls)[0] for cls in hero_classes}
    n_villain = (
        len(villain_classes) if villain_reps is None else max(1, villain_reps)
    )
    villain_class_rep_order = villain_classes[:n_villain]

    per_pair_strategies: dict[tuple[HandClass, HandClass], PreflopSolveResult] = {}
    hero_per_class_rows: dict[HandClass, list[dict[str, float]]] = {}

    total_solves = len(hero_classes) * len(villain_class_rep_order)
    done = 0
    t0 = time.perf_counter()

    allow_pushfold = is_pushfold_mode(
        config_template.starting_stack,
        config_template.big_blind,
    )

    for hcls in hero_classes:
        rows_for_hclass: list[dict[str, float]] = []
        for vcls in villain_class_rep_order:
            hcombo = hero_combos[hcls]
            vcombo = _pick_villain_combo(vcls, hcombo)
            if vcombo is None:
                done += 1
                if on_progress is not None:
                    on_progress("preflop", done, total_solves)
                continue

            if hero_player == 0:
                hole_cards = (hcombo, vcombo)
            else:
                hole_cards = (vcombo, hcombo)

            sub_cfg = replace(config_template, initial_hole_cards=hole_cards)
            sub_result = solve_hunl_preflop(
                sub_cfg,
                iterations=iterations,
                allow_pushfold_range=allow_pushfold,
                dcfr_kwargs=dcfr_kwargs or None,
            )
            per_pair_strategies[(hcls, vcls)] = sub_result

            hero_row = _extract_first_decision_row(
                config=sub_cfg,
                strategy=sub_result.average_strategy,
                hero_player=hero_player,
            )
            if hero_row is not None:
                rows_for_hclass.append(hero_row)
            done += 1
            if on_progress is not None:
                on_progress("preflop", done, total_solves)
        if rows_for_hclass:
            hero_per_class_rows[hcls] = rows_for_hclass

    per_class_strategy: dict[HandClass, dict[str, float]] = {}
    for hcls, rows in hero_per_class_rows.items():
        per_class_strategy[hcls] = _average_rows(rows)

    range_aggregate = _aggregate_range(per_class_strategy, hero_classes)

    wall_clock_s = time.perf_counter() - t0

    # Merge per-pair strategies into a single per_history_strategy. Keys
    # have different hole prefixes across pairs so collisions are not a
    # concern; the merged dict gives callers a window into the raw
    # strategy if they want to inspect it.
    per_history: dict[str, list[float]] = {}
    for sub in per_pair_strategies.values():
        per_history.update({k: list(v) for k, v in sub.average_strategy.items()})

    preflop_result = RangeVsRangeNashResult(
        per_history_strategy=per_history,
        per_class_strategy=per_class_strategy,
        range_aggregate=range_aggregate,
        exploitability=0.0,  # Route A does not compute aggregate exploit.
        iterations=iterations,
        wall_clock_s=wall_clock_s,
        decision_node_count=0,
        hand_count_per_player=(len(hero_classes), len(villain_classes)),
        memory_profile={},
        backend="python_chained_route_a",
        position="aggressor" if hero_player == 0 else "defender",
        warnings=[],
    )
    return preflop_result, per_pair_strategies


def _pick_villain_combo(
    villain_class: HandClass,
    hero_combo: tuple[Card, Card],
) -> tuple[Card, Card] | None:
    """First villain combo from ``villain_class`` that does not collide.

    Avoids the trivial degenerate case where the hero's representative
    combo blocks every villain combo (e.g. hero=AhAs, villain=AA has only
    6 combos and AhAs / AhAd / AsAd all share a card with hero).
    """
    hero_cards = {hero_combo[0], hero_combo[1]}
    for combo in _enumerate_combos(villain_class):
        if combo[0] not in hero_cards and combo[1] not in hero_cards:
            return combo
    return None


def _extract_first_decision_row(
    *,
    config: HUNLConfig,
    strategy: dict[str, list[float]],
    hero_player: int,
) -> dict[str, float] | None:
    """Hero's first-decision action frequencies for this per-pair solve.

    Walks the game tree from the initial state to ``hero_player``'s
    first decision, looks up the infoset key under the solved strategy,
    and maps action ids to canonical labels.
    """
    game = HUNLPoker(config)
    state = game.initial_state()
    visited = 0
    while visited < 50:  # safety
        if game.is_terminal(state):
            return None
        cur = game.current_player(state)
        if cur == -1:
            outcomes = game.chance_outcomes(state)
            if not outcomes:
                return None
            state = game.apply(state, outcomes[0][0])
            visited += 1
            continue
        if cur != hero_player:
            actions = game.legal_actions(state)
            key = game.infoset_key(state, cur)
            probs = strategy.get(key)
            if probs is None or len(probs) != len(actions):
                idx = 0
            else:
                p_local = probs
                idx = max(range(len(p_local)), key=lambda i: p_local[i])
            state = game.apply(state, actions[idx])
            visited += 1
            continue
        actions = game.legal_actions(state)
        key = game.infoset_key(state, hero_player)
        probs = strategy.get(key)
        if probs is None or len(probs) != len(actions):
            probs = [1.0 / len(actions)] * len(actions)
        return {
            _label_for_action(action, config.bet_size_fractions): float(p)
            for action, p in zip(actions, probs, strict=True)
        }
    return None


def _average_rows(rows: list[dict[str, float]]) -> dict[str, float]:
    """Uniform-weight average of a list of {label: prob} rows + renormalize."""
    if not rows:
        return {}
    keys: set[str] = set()
    for r in rows:
        keys.update(r.keys())
    n = float(len(rows))
    out = {k: sum(r.get(k, 0.0) for r in rows) / n for k in keys}
    total = sum(out.values())
    if total > 0:
        out = {k: v / total for k, v in out.items()}
    return out


# ---------------------------------------------------------------------------
# Stage 2 — preflop terminal enumeration + continuation-range derivation
# ---------------------------------------------------------------------------


def _enumerate_preflop_terminals(
    config_template: HUNLConfig,
) -> list[tuple[PreflopActionSequence, HUNLState]]:
    """Walk the preflop tree and emit every terminal action sequence.

    "Terminal" here means a frontier state of the preflop tree: either
    (a) a fold (one player folded preflop), or (b) the preflop close
    where the next chance node would deal the flop.

    Returns a list of ``(action_sequence, terminal_state)`` pairs. The
    action sequence is the engine's per-action token tuple along the
    path; the terminal state carries the matched contributions /
    stacks for the postflop subgame.

    Hole cards are NOT material to the tree shape at preflop (action
    legality depends only on stacks + contributions); we walk with a
    placeholder pair so :meth:`HUNLPoker.initial_state` succeeds.
    """
    placeholder = (
        (Card.from_str("As"), Card.from_str("Ah")),
        (Card.from_str("Kd"), Card.from_str("Kc")),
    )
    cfg = replace(config_template, initial_hole_cards=placeholder)
    game = HUNLPoker(cfg)
    start = game.initial_state()
    terminals: list[tuple[PreflopActionSequence, HUNLState]] = []
    # Iterative DFS to avoid recursion limits on deep trees.
    stack: list[tuple[HUNLState, PreflopActionSequence]] = [(start, ())]
    while stack:
        state, path = stack.pop()
        # Preflop terminal frontiers:
        #   (a) any-fold (game ends in fold) — terminal regardless of street
        #   (b) preflop close → about to enter postflop chance node
        if any(state.folded):
            terminals.append((path, state))
            continue
        if state.street != Street.PREFLOP:
            terminals.append((path, state))
            continue
        if game.is_terminal(state):
            terminals.append((path, state))
            continue
        cur = game.current_player(state)
        if cur == -1:
            # Chance node mid-preflop should not happen with placeholder
            # hole cards set. Safety branch: take the first outcome.
            outcomes = game.chance_outcomes(state)
            if not outcomes:
                terminals.append((path, state))
                continue
            stack.append((game.apply(state, outcomes[0][0]), path))
            continue
        # Player decision — branch over every legal action.
        actions = game.legal_actions(state)
        for action in actions:
            new_state = game.apply(state, action)
            new_token = _last_token(state, new_state)
            new_path = path + (new_token,) if new_token else path
            stack.append((new_state, new_path))
    # Stable order — sort by path for deterministic test fixtures.
    terminals.sort(key=lambda t: t[0])
    return terminals


def _last_token(prev: HUNLState, new: HUNLState) -> str:
    """Return the single action token added by going prev -> new.

    Handles the street-flush case: when the apply call closes the preflop
    betting (transitions to FLOP / SHOWDOWN), the engine moves
    ``current_street_tokens`` into ``betting_tokens`` and resets the
    current tuple. We compare both buffers to pick out the newly added
    token.
    """
    prev_cs = prev.current_street_tokens
    new_cs = new.current_street_tokens
    if len(new_cs) > len(prev_cs):
        return new_cs[len(prev_cs)]
    # Street closed — current_street_tokens reset. The newly added token
    # is the last entry of betting_tokens[-1].
    if (
        new.street != prev.street
        or new.pending_board_deals > 0
        or any(new.folded) != any(prev.folded)
    ):
        if new.betting_tokens and new.betting_tokens[-1]:
            return new.betting_tokens[-1][-1]
    return ""


def _derive_continuation_ranges(
    *,
    action_sequence: PreflopActionSequence,
    terminal_state: HUNLState,
    config_template: HUNLConfig,
    hero_classes: list[HandClass],
    villain_classes: list[HandClass],
    per_pair_strategies: dict[tuple[HandClass, HandClass], PreflopSolveResult],
    hero_player: int,
) -> ContinuationRanges | None:
    """Per-(hero_class, villain_class) reach-probability propagation.

    For each ``(hero_class, villain_class)`` pair, walks the preflop tree
    along ``action_sequence`` and multiplies the per-step action
    probabilities under the solved strategy for that pair. The resulting
    reach prob is combo-count-weighted and accumulated per class.

    Returns ``None`` if ``action_sequence`` represents a fold terminal
    (no flop reached → no postflop subgame for Phase A) OR an all-in
    terminal (collapses to equity — no postflop decisions remain).
    """
    if any(terminal_state.folded):
        return None
    if any(terminal_state.all_in):
        # All-in run-outs collapse to equity at the preflop close — no
        # postflop decisions remain. Phase A defers (Phase B may add an
        # equity-only fast path).
        return None

    hero_weights: dict[HandClass, float] = {}
    villain_weights: dict[HandClass, float] = {}

    for hcls in hero_classes:
        for vcls in villain_classes:
            sub_result = per_pair_strategies.get((hcls, vcls))
            if sub_result is None:
                continue
            reach = _walk_pair_reach(
                action_sequence=action_sequence,
                config_template=config_template,
                hcls=hcls,
                vcls=vcls,
                strategy=sub_result.average_strategy,
                hero_player=hero_player,
            )
            if reach is None:
                continue
            hero_reach, villain_reach = reach
            joint_combos = float(_combo_count(hcls) * _combo_count(vcls))
            hero_weights[hcls] = (
                hero_weights.get(hcls, 0.0) + hero_reach * joint_combos
            )
            villain_weights[vcls] = (
                villain_weights.get(vcls, 0.0) + villain_reach * joint_combos
            )

    hero_weights = {k: v for k, v in hero_weights.items() if v > 1e-9}
    villain_weights = {k: v for k, v in villain_weights.items() if v > 1e-9}
    if not hero_weights or not villain_weights:
        return None

    c0, c1 = terminal_state.contributions
    pot_chips = c0 + c1
    return ContinuationRanges(
        hero=hero_weights,
        villain=villain_weights,
        pot_chips=pot_chips,
        action_sequence=action_sequence,
    )


def _walk_pair_reach(
    *,
    action_sequence: PreflopActionSequence,
    config_template: HUNLConfig,
    hcls: HandClass,
    vcls: HandClass,
    strategy: dict[str, list[float]],
    hero_player: int,
) -> tuple[float, float] | None:
    """Replay ``action_sequence`` against a per-pair solve and return reach.

    The strategy dict was produced by ``solve_hunl_preflop`` on a config
    with the per-pair hole cards set. We rebuild the same config, walk
    the tree action-by-action matching the token sequence, and multiply
    per-player action probabilities along the way.
    """
    hcombo = _enumerate_combos(hcls)[0]
    vcombo = _pick_villain_combo(vcls, hcombo)
    if vcombo is None:
        return None
    if hero_player == 0:
        hole = (hcombo, vcombo)
    else:
        hole = (vcombo, hcombo)
    pair_cfg = replace(config_template, initial_hole_cards=hole)
    game = HUNLPoker(pair_cfg)
    state = game.initial_state()

    hero_reach = 1.0
    villain_reach = 1.0
    tokens_remaining = list(action_sequence)

    visited = 0
    while tokens_remaining and visited < 100:
        if game.is_terminal(state):
            return None
        cur = game.current_player(state)
        if cur == -1:
            outcomes = game.chance_outcomes(state)
            if not outcomes:
                return None
            state = game.apply(state, outcomes[0][0])
            visited += 1
            continue
        actions = game.legal_actions(state)
        next_token = tokens_remaining[0]
        chosen_idx: int | None = None
        for idx, action in enumerate(actions):
            trial_state = game.apply(state, action)
            tok = _last_token(state, trial_state)
            if tok == next_token:
                chosen_idx = idx
                break
        if chosen_idx is None:
            return None
        key = game.infoset_key(state, cur)
        probs = strategy.get(key)
        if probs is not None and len(probs) == len(actions):
            p = float(probs[chosen_idx])
        else:
            p = 1.0 / len(actions)
        if cur == hero_player:
            hero_reach *= p
        else:
            villain_reach *= p
        state = game.apply(state, actions[chosen_idx])
        tokens_remaining.pop(0)
        visited += 1

    return hero_reach, villain_reach


# ---------------------------------------------------------------------------
# Stage 3 — lazy postflop subgame solve
# ---------------------------------------------------------------------------


def _run_postflop_subgame(
    *,
    config_template: HUNLConfig,
    continuation: ContinuationRanges,
    board: BoardTuple,
    iterations: int,
    hero_player: int,
) -> RangeVsRangeNashResult:
    """Solve the flop subgame for ``(action_sequence, board)``.

    Builds a postflop ``HUNLConfig`` with:
      - ``starting_street=Street.FLOP``
      - ``initial_board=board``
      - ``initial_pot`` = ``continuation.pot_chips``
      - ``initial_contributions`` = ``(pot/2, pot/2)``
        (symmetric matched-pot threading)

    Then calls :func:`solve_range_vs_range_nash` with the continuation
    ranges as ``hero_range`` / ``villain_range``. Hands in either range
    that collide with the board are filtered by that function.
    """
    pot = int(continuation.pot_chips)
    half = pot // 2
    contribs = (half, pot - half)

    postflop_cfg = replace(
        config_template,
        starting_street=Street.FLOP,
        initial_board=tuple(board),
        initial_pot=pot,
        initial_contributions=contribs,
        initial_hole_cards=(),
    )

    # The continuation-range dict is {hand_class: weight}; we pass keys to
    # ``solve_range_vs_range_nash`` as a list. Per-combo reach weighting
    # into the Rust binding lands in Phase B (the binding currently
    # treats all enumerated combos uniformly).
    hero_classes_sorted = sorted(continuation.hero.keys())
    villain_classes_sorted = sorted(continuation.villain.keys())

    return solve_range_vs_range_nash(
        postflop_cfg,
        hero_range=hero_classes_sorted,
        villain_range=villain_classes_sorted,
        iterations=iterations,
        hero_player=hero_player,
        compute_exploitability_at_end=False,
    )


__all__ = [
    "BoardTuple",
    "ChainedSolveResult",
    "ContinuationRanges",
    "DEFAULT_POSTFLOP_CACHE_MAX_SIZE",
    "PreflopActionSequence",
    "solve_chained",
]
