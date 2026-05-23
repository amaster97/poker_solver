"""Pluribus-blueprint range-vs-range aggregation harness (PR 16).

This module wraps the existing per-hand subgame solver (PR 5 / PR 6 / PR 9)
into a range-level API. It is **not** a "true" range-vs-range Nash solver
(that requires the empty-`initial_hole_cards` chance-enum path, which is
the focus of v1.3 Option A in parallel). Instead, this is the
**blueprint-aggregation workaround** documented in §4 of
``docs/pr_proposals/v1_3_range_vs_range.md``:

  - For each Pio-style hand class in the hero range (e.g. ``"AA"``,
    ``"AKs"``, ``"AKo"``), pick representative concrete combos.
  - For each hero representative, sample a representative villain combo
    from the villain range.
  - Run the existing concrete-vs-concrete subgame solver.
  - Aggregate the resulting hero-action frequencies by combo count
    (``AA`` = 6 combos, ``AKs`` = 4 combos, ``AKo`` = 12 combos), giving
    a per-hand-class frequency dict suitable for a 13x13 matrix display.

**Honest framing.** Every per-hand solve is a 1-combo-vs-1-combo Nash, so
the resulting frequencies reflect what hero does *against a specific
villain combo*, not against the full villain range. The aggregation
averages across representative villain combos to approximate the
range-level behavior, but:

  - It does NOT model villain's mixed strategy across the range
    (each subgame solves a single 1v1 spot, not 1v(many)).
  - For premium pairs vs underpairs on dry boards this is approximately
    correct (the value-vs-air dynamic dominates), but on draw-heavy
    boards or polarized villain ranges the approximation can shift
    several percentage points.
  - Use Option A (Rust exploitability port) when the user genuinely
    needs the chance-enum range-vs-range solve.

**Time budget.** Each per-hand solve has a 30 s ceiling; solves that
exceed it are dropped with a warning and the aggregation continues with
partial data (the result's ``partial_misses`` field counts dropped
solves so callers can surface this).

**Hero position (v1.3.1).** The ``hero_player`` parameter of
:func:`solve_range_vs_range` controls which engine seat hero occupies:
``0`` (default) places hero as the aggressor (P0, first postflop
decision after BB acts); ``1`` places hero as the defender (P1, BB)
so the returned frequencies are hero's defense (call / fold / raise)
against villain's lead. The :class:`RangeVsRangeResult.position` field
reflects this choice (``"aggressor"`` or ``"defender"``). v1.3.0
hardcoded the aggressor seat and silently returned ~100% check on
defending spots; the v1.3.1 fix is to expose ``hero_player`` so MDF /
calling-frequency queries work. See
``docs/pr16_prep/stress_test_results.md`` S4 for the bug that drove
this patch.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from poker_solver.action_abstraction import (
    ACTION_ALL_IN,
    ACTION_BET_33,
    ACTION_BET_75,
    ACTION_BET_100,
    ACTION_BET_150,
    ACTION_BET_200,
    ACTION_CALL,
    ACTION_CHECK,
    ACTION_FOLD,
    ACTION_RAISE_33,
    ACTION_RAISE_75,
    ACTION_RAISE_100,
    ACTION_RAISE_150,
    ACTION_RAISE_200,
)
from poker_solver.card import RANK_VALUE, RANKS, Card
from poker_solver.hunl import HUNLConfig, HUNLPoker, Street
from poker_solver.range import Range
from poker_solver.solver import SolveResult, solve

_BET_ACTION_IDS: tuple[int, ...] = (
    ACTION_BET_33,
    ACTION_BET_75,
    ACTION_BET_100,
    ACTION_BET_150,
    ACTION_BET_200,
)

_RAISE_ACTION_IDS: tuple[int, ...] = (
    ACTION_RAISE_33,
    ACTION_RAISE_75,
    ACTION_RAISE_100,
    ACTION_RAISE_150,
    ACTION_RAISE_200,
)

# Non-bet/raise action labels.
_FIXED_ACTION_LABELS: dict[int, str] = {
    ACTION_FOLD: "fold",
    ACTION_CHECK: "check",
    ACTION_CALL: "call",
    ACTION_ALL_IN: "all_in",
}


def _label_for_action(action_id: int, bet_size_fractions: tuple[float, ...]) -> str:
    """Map an action id to a human-readable label.

    Bet/raise action ids are positional: ``ACTION_BET_33`` is "the first
    bet size in ``bet_size_fractions``", *not* "always 33% pot". The
    action-id naming in the engine is a fixed enum independent of the
    fraction it represents. We therefore decode the label from the
    actual fraction the action corresponds to, so a config with
    ``bet_size_fractions=(0.75,)`` produces a label of ``"bet_75"``
    (the conceptual fraction) rather than ``"bet_33"`` (the enum-slot
    name).
    """
    fixed = _FIXED_ACTION_LABELS.get(action_id)
    if fixed is not None:
        return fixed
    if action_id in _BET_ACTION_IDS:
        idx = _BET_ACTION_IDS.index(action_id)
        if idx < len(bet_size_fractions):
            frac = bet_size_fractions[idx]
            return f"bet_{int(round(frac * 100))}"
        return f"bet_idx_{idx}"
    if action_id in _RAISE_ACTION_IDS:
        idx = _RAISE_ACTION_IDS.index(action_id)
        if idx < len(bet_size_fractions):
            frac = bet_size_fractions[idx]
            return f"raise_{int(round(frac * 100))}"
        return f"raise_idx_{idx}"
    return f"action_{action_id}"


# Default per-solve wall-clock ceiling. Solves slower than this are dropped
# and contribute zero weight to the aggregate. Documented as a hard cap so
# callers can plan a total budget = N_hero_classes * per_solve_cap.
DEFAULT_TIME_BUDGET_PER_SOLVE_S: float = 30.0


HandClass = str
"""Pio-style hand-class label such as ``"AA"``, ``"AKs"``, ``"AKo"``."""


@dataclass
class _PerHandResult:
    """Internal: result of a single concrete-vs-concrete subgame solve."""

    hand_class: HandClass
    combo_count: int  # number of combos this class represents
    weight: float  # = combo_count by default
    action_freqs: dict[str, float]
    raw_solve: SolveResult | None = None
    wall_clock_s: float = 0.0
    error: str | None = None


@dataclass
class RangeVsRangeResult:
    """Structured output of :func:`solve_range_vs_range`.

    Attributes:
        per_class_strategy: ``{hand_class: {action_label: probability}}``.
            Hero's first-decision action frequencies, per hero hand class,
            averaged across representative combos. **Frequencies are from
            hero's perspective at hero's first decision point** — check
            ``position`` to disambiguate (see below).
        range_aggregate: Range-level frequencies, weighted by combo count.
            ``{action_label: probability}``. Sums to ~1.0 (modulo dropped
            solves; see ``partial_misses``). **Same hero-perspective caveat
            as ``per_class_strategy``** — if ``position == "defender"`` these
            are defense (call/fold/raise) frequencies, not c-bet frequencies.
        total_combos: Total concrete combos enumerated across hero classes
            (post board-block filtering).
        total_solves: Number of subgame solves actually executed.
        partial_misses: Number of solves that timed out, hit an exception,
            or were skipped due to no representative combo being feasible
            (e.g. every combo blocked by the board).
        wall_clock_s: Total wall-clock for the full range-vs-range query.
        per_solve_wall_clock_s: Per-class wall-clock dict.
        warnings: Human-readable warnings (timeouts, missing reps, etc.).
        position: ``"aggressor"`` if ``hero_player == 0`` (default; hero is
            P0 and acts first postflop after BB acts), else ``"defender"``
            (``hero_player == 1``; hero faces villain's action). Use this
            to interpret ``range_aggregate``: aggressor freqs include
            ``"check"`` / ``"bet_*"``; defender freqs include ``"fold"`` /
            ``"call"`` / ``"raise_*"``. **Always check this field before
            labeling the output** — see the v1.3.1 caveat in USAGE.md §5.2.
    """

    per_class_strategy: dict[HandClass, dict[str, float]] = field(default_factory=dict)
    range_aggregate: dict[str, float] = field(default_factory=dict)
    total_combos: int = 0
    total_solves: int = 0
    partial_misses: int = 0
    wall_clock_s: float = 0.0
    per_solve_wall_clock_s: dict[HandClass, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    position: str = "aggressor"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def solve_range_vs_range(
    config_template: HUNLConfig,
    hero_range: Sequence[HandClass] | Range,
    villain_range: Sequence[HandClass] | Range,
    iterations: int = 200,
    *,
    backend: str = "rust",
    reps_per_class: int = 1,
    villain_reps: int = 3,
    hero_player: int = 0,
    time_budget_per_solve_s: float = DEFAULT_TIME_BUDGET_PER_SOLVE_S,
    on_progress: Callable[[int, int, HandClass], None] | None = None,
    dcfr_kwargs: dict[str, Any] | None = None,
) -> RangeVsRangeResult:
    """Solve a range-vs-range query via Pluribus-blueprint aggregation.

    For each hero hand class, this routine:

      1. Enumerates the concrete combos representing the class
         (e.g. ``"AA"`` -> 6 specific combos; ``"AKs"`` -> 4;
         ``"AKo"`` -> 12). Combos blocked by the board are skipped.
      2. Picks ``reps_per_class`` representative combos (default 1 — the
         first board-feasible combo).
      3. For each representative, samples ``villain_reps`` villain combos
         from the villain range (representative combos per class, with
         conflicts against hero + board removed) and solves each as a
         concrete-vs-concrete subgame via :func:`solve`.
      4. Averages hero's first-decision action frequencies across the
         representatives (uniform weighting).
      5. Aggregates the per-class frequencies into a range-level dict,
         weighted by combo count.

    This is the "blueprint aggregation" pattern called out in
    ``preflop.py`` and the v1.3 proposal §4. It is a **workaround**,
    not a Nash range-vs-range solve. See module docstring for the
    honest framing.

    Args:
        config_template: ``HUNLConfig`` describing the board, stacks,
            blinds, and action structure. Its ``initial_hole_cards``
            field is overridden per per-hand solve, so callers should
            leave it empty (``()``) or pass any sentinel — the aggregator
            replaces it.
        hero_range: Either a list of Pio-style hand-class strings
            (``["AA", "AKs", "AKo"]``) or a :class:`Range` object. Passing
            a ``Range`` extracts the canonical hand-class set from its
            concrete combos.
        villain_range: Same shape as ``hero_range``.
        iterations: DCFR iteration count per per-hand subgame solve.
            Default 200.
        backend: ``"rust"`` (recommended) or ``"python"``. Routed through
            :func:`solve`.
        reps_per_class: Representative combos sampled per hero hand class.
            Default 1 (first board-feasible combo). Higher values
            improve accuracy at linear cost.
        villain_reps: Villain representative combos solved against per
            hero rep. Default 3.
        hero_player: Engine slot for hero. ``hero_player=0`` (default)
            places hero at slot 0 (SB seat / button — first to act
            PREFLOP, last to act POSTFLOP); this is the "aggressor"
            position and matches v1.3.0's hardcoded behavior. The
            returned ``RangeVsRangeResult.position`` field reports
            ``"aggressor"`` in this case. ``hero_player=1`` places hero
            at slot 1 (BB seat — last to act PREFLOP, first to act
            POSTFLOP); the result's ``position`` field reports
            ``"defender"``. Use this for MDF / calling-frequency queries
            against villain's lead.

            NOTE: For a "BB defending" workflow, set ``hero_player=1``
            AND ``hero_range=bb_range`` so the BB-range cards land in
            the BB seat. Setting ``hero_player=0`` with BB-range cards
            places them in the SB seat (wrong position).

            **Caveat:** the per-hand solver picks villain's most-likely
            opening action under the solved strategy, so defender
            outputs reflect hero's response to villain's modal line,
            not a true Nash defending mix.
        time_budget_per_solve_s: Hard wall-clock ceiling per subgame
            solve. Solves exceeding this are dropped with a warning;
            the aggregator continues with partial data.
        on_progress: Optional callback ``(done, total, hand_class)`` for
            UI updates.
        dcfr_kwargs: Forwarded to the per-hand :func:`solve` call.

    Returns:
        A :class:`RangeVsRangeResult` with per-class and range-level
        frequencies, total combos enumerated, partial-miss count, and
        wall-clock breakdown. The ``position`` field disambiguates
        whether the frequencies are aggressor-side (opens) or
        defender-side (defends).

    Raises:
        ValueError: hero or villain range is empty after parsing; a
            hand-class label is invalid; ``hero_player`` is not 0 or 1;
            ``config_template.starting_street == Street.PREFLOP`` (use
            ``solve_hunl_preflop`` directly per PR 9; aggregation for
            preflop ranges is a follow-up).
    """
    if hero_player not in (0, 1):
        raise ValueError(
            f"hero_player must be 0 (aggressor) or 1 (defender); got {hero_player!r}"
        )
    if config_template.starting_street == Street.PREFLOP:
        raise ValueError(
            "solve_range_vs_range does not yet support preflop range-vs-range "
            "(aggregator pattern requires the postflop subgame solver). For "
            "preflop subgame solves with fixed hole cards, call "
            "solve_hunl_preflop directly. Preflop range-vs-range is a "
            "v1.4+ follow-up."
        )

    hero_classes = _normalize_range(hero_range)
    villain_classes = _normalize_range(villain_range)
    if not hero_classes:
        raise ValueError("hero_range is empty after parsing")
    if not villain_classes:
        raise ValueError("villain_range is empty after parsing")

    board_cards = set(config_template.initial_board)

    # Precompute villain representatives once: for each villain class,
    # enumerate its combos and pick `villain_reps` board-feasible ones
    # (deterministic order — first-N-not-blocked).
    villain_reps_by_class: dict[HandClass, list[tuple[Card, Card]]] = {}
    for vclass in villain_classes:
        combos = _enumerate_combos(vclass)
        feasible = [
            c for c in combos if c[0] not in board_cards and c[1] not in board_cards
        ]
        villain_reps_by_class[vclass] = feasible[:villain_reps]

    # Build the flat villain rep list as (class, combo) pairs for sampling.
    villain_rep_list: list[tuple[HandClass, tuple[Card, Card]]] = []
    for vclass, combos in villain_reps_by_class.items():
        for combo in combos:
            villain_rep_list.append((vclass, combo))

    result = RangeVsRangeResult(
        position="aggressor" if hero_player == 0 else "defender",
    )
    t_total_start = time.perf_counter()

    total_classes = len(hero_classes)
    for class_idx, hclass in enumerate(hero_classes):
        if on_progress is not None:
            on_progress(class_idx, total_classes, hclass)

        combos = _enumerate_combos(hclass)
        feasible = [
            c for c in combos if c[0] not in board_cards and c[1] not in board_cards
        ]
        result.total_combos += len(feasible)

        if not feasible:
            result.warnings.append(
                f"{hclass}: every combo blocked by board {sorted(board_cards)!r}; skipping"
            )
            result.partial_misses += 1
            continue

        # Pick `reps_per_class` hero representatives — deterministic
        # first-N order. Future enhancement: sample by suit-class diversity.
        hero_reps = feasible[:reps_per_class]

        # Per-rep frequencies, averaged across villain reps within each
        # hero rep, then averaged across hero reps.
        per_rep_freqs: list[dict[str, float]] = []
        class_t_start = time.perf_counter()
        for hcombo in hero_reps:
            v_freqs: list[dict[str, float]] = []
            for vclass, vcombo in villain_rep_list:
                # Filter conflicts: hero combo cards must not collide with
                # villain combo cards. (Board collision was filtered when
                # building `villain_reps_by_class`.)
                if vcombo[0] in hcombo or vcombo[1] in hcombo:
                    continue
                freqs = _run_one_subgame(
                    config_template=config_template,
                    hero_combo=hcombo,
                    villain_combo=vcombo,
                    iterations=iterations,
                    backend=backend,
                    time_budget_s=time_budget_per_solve_s,
                    dcfr_kwargs=dcfr_kwargs,
                    result_acc=result,
                    label=f"{hclass}<-{vclass}",
                    hero_player=hero_player,
                )
                if freqs is not None:
                    v_freqs.append(freqs)
                    result.total_solves += 1
                else:
                    result.partial_misses += 1
            if v_freqs:
                per_rep_freqs.append(_average_freqs(v_freqs))
        if per_rep_freqs:
            class_freqs = _average_freqs(per_rep_freqs)
            # Normalize: action frequencies in a class strategy must sum
            # to 1.0 (modulo float epsilon). Averaging across reps that
            # may have had slightly different legal-action sets can
            # introduce missing probability mass if a rep saw extra
            # actions; we renormalize defensively.
            class_freqs = _renormalize(class_freqs)
            result.per_class_strategy[hclass] = class_freqs
        else:
            result.warnings.append(
                f"{hclass}: no representative solves succeeded; class dropped"
            )

        result.per_solve_wall_clock_s[hclass] = time.perf_counter() - class_t_start

    # Aggregate by combo count.
    result.range_aggregate = _aggregate_range(
        result.per_class_strategy,
        hero_classes,
    )

    result.wall_clock_s = time.perf_counter() - t_total_start
    if on_progress is not None:
        on_progress(total_classes, total_classes, "")
    return result


# ---------------------------------------------------------------------------
# Combo expansion
# ---------------------------------------------------------------------------


def _enumerate_combos(hand_class: HandClass) -> list[tuple[Card, Card]]:
    """Expand a hand-class string to its concrete combos.

    Conventions:
      - Pairs (``"AA"``): all C(4,2) = 6 suit pairings.
      - Suited (``"AKs"``): 4 suit-aligned combos.
      - Offsuit (``"AKo"``): 4 * 3 = 12 cross-suit combos.

    For pairs the returned tuples are sorted ``(low_suit, high_suit)``;
    for non-pairs the first card is the higher rank. Order within the
    list is deterministic: nested suit loops in (0..3) x (0..3).
    """
    label = hand_class.strip()
    if len(label) == 2:
        # Either pair like "AA" or a non-suited two-card like "AK" (we
        # treat as offsuit + suited combined).
        r1, r2 = label[0], label[1]
        if r1 not in RANK_VALUE or r2 not in RANK_VALUE:
            raise ValueError(f"invalid hand class {hand_class!r}")
        if r1 == r2:
            return _pair_combos(RANK_VALUE[r1])
        # "AK" without an s/o suffix: union of suited + offsuit (all 16
        # combos). Not the canonical Pio convention, but useful for
        # callers that pass "AK" expecting all 16 combos.
        hi, lo = (r1, r2) if RANK_VALUE[r1] > RANK_VALUE[r2] else (r2, r1)
        return _suited_combos(RANK_VALUE[hi], RANK_VALUE[lo]) + _offsuit_combos(
            RANK_VALUE[hi], RANK_VALUE[lo]
        )
    if len(label) == 3:
        r1, r2, suffix = label[0], label[1], label[2].lower()
        if r1 not in RANK_VALUE or r2 not in RANK_VALUE:
            raise ValueError(f"invalid hand class {hand_class!r}")
        if r1 == r2:
            raise ValueError(f"pair token cannot have suit suffix: {hand_class!r}")
        if suffix not in ("s", "o"):
            raise ValueError(f"invalid suit suffix in {hand_class!r}; use 's' or 'o'")
        hi, lo = (r1, r2) if RANK_VALUE[r1] > RANK_VALUE[r2] else (r2, r1)
        if suffix == "s":
            return _suited_combos(RANK_VALUE[hi], RANK_VALUE[lo])
        return _offsuit_combos(RANK_VALUE[hi], RANK_VALUE[lo])
    if len(label) == 4:
        # Specific combo like "AhKh".
        c1 = Card.from_str(label[:2])
        c2 = Card.from_str(label[2:])
        if c1 == c2:
            raise ValueError(f"combo has duplicate card: {hand_class!r}")
        return [(c1, c2)]
    raise ValueError(f"unrecognized hand class label: {hand_class!r}")


def _pair_combos(rank: int) -> list[tuple[Card, Card]]:
    out: list[tuple[Card, Card]] = []
    for s1 in range(4):
        for s2 in range(s1 + 1, 4):
            out.append((Card(rank, s1), Card(rank, s2)))
    return out


def _suited_combos(hi_rank: int, lo_rank: int) -> list[tuple[Card, Card]]:
    return [(Card(hi_rank, s), Card(lo_rank, s)) for s in range(4)]


def _offsuit_combos(hi_rank: int, lo_rank: int) -> list[tuple[Card, Card]]:
    out: list[tuple[Card, Card]] = []
    for s1 in range(4):
        for s2 in range(4):
            if s1 != s2:
                out.append((Card(hi_rank, s1), Card(lo_rank, s2)))
    return out


def _combo_count(hand_class: HandClass) -> int:
    """Return the canonical combo count for a hand class label.

    Pairs = 6, suited = 4, offsuit = 12, unsuited two-card = 16,
    specific 4-char combo = 1. Used for combo-weighted aggregation.
    """
    label = hand_class.strip()
    if len(label) == 2:
        if label[0] == label[1]:
            return 6
        return 16  # "AK" = suited (4) + offsuit (12)
    if len(label) == 3:
        suffix = label[2].lower()
        if suffix == "s":
            return 4
        if suffix == "o":
            return 12
        raise ValueError(f"invalid suit suffix in {hand_class!r}")
    if len(label) == 4:
        return 1
    raise ValueError(f"unrecognized hand class label: {hand_class!r}")


# ---------------------------------------------------------------------------
# Range normalization
# ---------------------------------------------------------------------------


def _normalize_range(r: Sequence[HandClass] | Range) -> list[HandClass]:
    """Accept either a list of hand-class labels or a Range and return labels.

    For a ``Range`` we derive hand-class labels from its concrete combos
    via ``_combo_to_hand_class``; duplicates are removed while preserving
    first-seen order.
    """
    if isinstance(r, Range):
        seen: set[HandClass] = set()
        out: list[HandClass] = []
        for combo in r:
            cls = _combo_to_hand_class(combo)
            if cls not in seen:
                seen.add(cls)
                out.append(cls)
        return out
    # Sequence of strings.
    seen2: set[HandClass] = set()
    out2: list[HandClass] = []
    for label in r:
        if not isinstance(label, str):
            raise ValueError(
                f"range entries must be hand-class strings; got {type(label).__name__}"
            )
        normalized = label.strip()
        if normalized and normalized not in seen2:
            seen2.add(normalized)
            out2.append(normalized)
    return out2


def _combo_to_hand_class(combo: Iterable[Card]) -> HandClass:
    """Map a concrete combo (Card pair) to its Pio-style hand-class label.

    Pair -> ``"AA"``, suited two-card -> ``"AKs"``, offsuit -> ``"AKo"``.
    """
    cards = list(combo)
    if len(cards) != 2:
        raise ValueError(f"combo must have 2 cards; got {len(cards)}")
    c1, c2 = cards
    if c1.rank == c2.rank:
        return RANKS[c1.rank - 2] * 2
    hi, lo = (c1, c2) if c1.rank > c2.rank else (c2, c1)
    suffix = "s" if hi.suit == lo.suit else "o"
    return RANKS[hi.rank - 2] + RANKS[lo.rank - 2] + suffix


# ---------------------------------------------------------------------------
# Per-hand solve runner
# ---------------------------------------------------------------------------


def _run_one_subgame(
    *,
    config_template: HUNLConfig,
    hero_combo: tuple[Card, Card],
    villain_combo: tuple[Card, Card],
    iterations: int,
    backend: str,
    time_budget_s: float,
    dcfr_kwargs: dict[str, Any] | None,
    result_acc: RangeVsRangeResult,
    label: str,
    hero_player: int = 0,
) -> dict[str, float] | None:
    """Run a single concrete-vs-concrete subgame solve and extract hero's
    first-decision action frequencies.

    The ``hero_player`` argument controls which engine slot hero's combo is
    placed at AND which slot's decisions are extracted; passing
    ``hero_player=1`` swaps hero into the defender seat so the extracted
    frequencies are hero's response to villain's lead, not hero's c-bet
    frequency.

    Returns ``None`` on timeout/error (the caller increments
    ``partial_misses``); otherwise returns ``{action_label: prob}``.
    """
    # Place hero's combo at the requested engine slot (0 = aggressor = P0
    # acts first postflop after BB; 1 = defender = P1 / BB). The engine's
    # `initial_hole_cards` is ordered (player_0_cards, player_1_cards).
    if hero_player == 0:
        hole_cards = (hero_combo, villain_combo)
    else:
        hole_cards = (villain_combo, hero_combo)
    sub_config = replace(
        config_template,
        initial_hole_cards=hole_cards,
    )
    game = HUNLPoker(sub_config)
    t0 = time.perf_counter()
    try:
        # Wall-clock guard: we cannot interrupt the Rust solver mid-call,
        # but we can refuse to record results from a solve that already
        # exceeded the budget. The dominant solves at 200 iters in Rust
        # are O(10-100 ms), so the budget realistically only fires when
        # something pathological happens.
        sresult = solve(
            game,
            iterations=iterations,
            backend=backend,
            **(dcfr_kwargs or {}),
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - t0
        result_acc.warnings.append(
            f"{label}: solve raised {type(exc).__name__}: {exc!s} after {elapsed:.2f}s"
        )
        return None
    elapsed = time.perf_counter() - t0
    if elapsed > time_budget_s:
        result_acc.warnings.append(
            f"{label}: solve took {elapsed:.2f}s > budget {time_budget_s:.1f}s; dropped"
        )
        return None
    return _extract_first_decision_freqs(
        game, sub_config, sresult, hero_player=hero_player
    )


def _extract_first_decision_freqs(
    game: HUNLPoker,
    config: HUNLConfig,
    sresult: SolveResult,
    *,
    hero_player: int,
) -> dict[str, float] | None:
    """Extract hero's first-decision action frequencies from a solve result.

    Walks from the initial state to the first player decision belonging to
    `hero_player`, looks up that infoset's strategy, maps action ids to
    canonical labels, and returns a frequency dict that sums to 1.0.

    Returns ``None`` when no such decision exists (terminal subgame, or
    hero is never to act on the first decision under any line).
    """
    state = game.initial_state()
    # Walk past chance + non-hero decisions until we reach a hero decision
    # or terminal. For postflop subgames with fixed hole cards there is no
    # chance prefix, so the very first non-terminal state is a player decision.
    visited = 0
    while visited < 100:  # safety
        if game.is_terminal(state):
            return None
        cur = game.current_player(state)
        if cur == -1:
            # Chance node: take the first outcome (board cards already
            # dealt for our postflop subgame, so we should not normally
            # reach here on the very first move).
            outcomes = game.chance_outcomes(state)
            if not outcomes:
                return None
            state = game.apply(state, outcomes[0][0])
            visited += 1
            continue
        if cur != hero_player:
            # Opponent moves first (BB postflop). Follow their most-likely
            # action under the solved strategy and continue to hero's
            # decision. This captures "hero's response after BB's lead."
            actions = game.legal_actions(state)
            key = game.infoset_key(state, cur)
            probs = sresult.average_strategy.get(key)
            idx = 0 if probs is None else max(range(len(probs)), key=lambda i: probs[i])
            state = game.apply(state, actions[idx])
            visited += 1
            continue
        # Hero's first decision.
        actions = game.legal_actions(state)
        key = game.infoset_key(state, hero_player)
        probs = sresult.average_strategy.get(key)
        if probs is None or len(probs) != len(actions):
            # Hero never touched this infoset (subgame too short, or empty
            # strategy). Fall back to uniform.
            probs = [1.0 / len(actions)] * len(actions)
        return {
            _label_for_action(action, config.bet_size_fractions): float(prob)
            for action, prob in zip(actions, probs, strict=True)
        }
    return None


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def _average_freqs(freqs_list: list[dict[str, float]]) -> dict[str, float]:
    """Uniform average of a list of frequency dicts.

    Missing keys count as 0.0 contributions. The output keys are the union
    across inputs. Output need not sum to exactly 1.0 if inputs had
    different legal-action sets; callers renormalize as needed.
    """
    if not freqs_list:
        return {}
    keys: set[str] = set()
    for d in freqs_list:
        keys.update(d.keys())
    n = len(freqs_list)
    out: dict[str, float] = {}
    for k in keys:
        out[k] = sum(d.get(k, 0.0) for d in freqs_list) / n
    return out


def _renormalize(freqs: dict[str, float]) -> dict[str, float]:
    total = sum(freqs.values())
    if total <= 0:
        return freqs
    return {k: v / total for k, v in freqs.items()}


def _aggregate_range(
    per_class: dict[HandClass, dict[str, float]],
    class_order: list[HandClass],
) -> dict[str, float]:
    """Combo-weighted average across hand classes.

    Each class contributes its frequency dict weighted by its canonical
    combo count (pair=6, suited=4, offsuit=12, etc.). The output sums to
    1.0 modulo float epsilon if every input class also sums to 1.0.
    """
    if not per_class:
        return {}
    keys: set[str] = set()
    for d in per_class.values():
        keys.update(d.keys())
    weighted_sum: dict[str, float] = {k: 0.0 for k in keys}
    total_weight = 0.0
    for cls in class_order:
        freqs = per_class.get(cls)
        if not freqs:
            continue
        w = float(_combo_count(cls))
        total_weight += w
        for k in keys:
            weighted_sum[k] += w * freqs.get(k, 0.0)
    if total_weight <= 0:
        return {}
    return {k: v / total_weight for k, v in weighted_sum.items()}


__all__ = [
    "DEFAULT_TIME_BUDGET_PER_SOLVE_S",
    "HandClass",
    "RangeVsRangeResult",
    "solve_range_vs_range",
]
