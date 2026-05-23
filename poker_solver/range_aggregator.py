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
``hero_player=0`` (default) places hero at slot 0 (SB seat / button —
first to act PREFLOP, last to act POSTFLOP); this is the "aggressor"
position and the result's ``position`` field reports ``"aggressor"``.
``hero_player=1`` places hero at slot 1 (BB seat — last to act
PREFLOP, first to act POSTFLOP); the result's ``position`` field
reports ``"defender"`` and the returned frequencies are hero's
defense (call / fold / raise) against villain's lead. v1.3.0
hardcoded the aggressor seat and silently returned ~100% check on
defending spots; the v1.3.1 fix is to expose ``hero_player`` so MDF /
calling-frequency queries work. For a "BB defending" workflow, set
``hero_player=1`` AND ``hero_range=bb_range`` so the BB-range cards
land in the BB seat. See ``docs/pr16_prep/stress_test_results.md``
S4 for the bug that drove this patch.
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
from poker_solver.card import RANK_VALUE, RANKS, Card, card_to_int
from poker_solver.hunl import HUNLConfig, HUNLPoker, Street, _serialize_hunl_config
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


# ---------------------------------------------------------------------------
# v1.7.0 — true Nash vector-form entry point (PR 23 wrapper)
# ---------------------------------------------------------------------------
#
# `solve_range_vs_range_nash` delegates to PR 23's
# `_rust.solve_range_vs_range_rust` (vector-form CFR — Brown's algorithm bit
# for bit). Distinct from the blueprint aggregator above because the
# vector form solves the JOINT imperfect-information Nash of the supplied
# ranges (hands as a vector dimension *inside* each infoset), not the
# per-combo perfect-info aggregation pattern. See
# ``docs/aggregator_vs_true_nash_explainer.md`` for the long-form
# distinction.


@dataclass
class RangeVsRangeNashResult:
    """True joint-Nash result for a range-vs-range query (vector-form CFR).

    Distinct from :class:`RangeVsRangeResult` because the underlying
    algorithm produces **per-(history, hand) strategies**, not per-class
    aggregated frequencies. See ``docs/aggregator_vs_true_nash_explainer.md``
    for the long-form distinction.

    Attributes:
        per_history_strategy: ``{infoset_key: list[float]}`` mapping
            ``<hole_string>|<board>|<street>|<history>`` (the lossless
            Python/Rust format from ``HUNLState.infoset_key`` and PR 23's
            vector emit) to action-probability rows. Hand order within an
            infoset matches the Rust binding's emit order (deterministic).
        per_class_strategy: ``{hand_class: {action_label: probability}}``
            — root-decision projection of ``per_history_strategy`` onto
            hand classes (pair / suited / offsuit), combo-averaged. Provided
            as a convenience for callers that want the 13x13-style display.
            **Caveat:** This projection collapses the per-history mixing,
            so it is informative but not a full strategy description; for
            real Nash analysis use ``per_history_strategy``.
        range_aggregate: Root-decision range-aggregated action frequencies
            (combo-weighted across classes). Mirrors
            :class:`RangeVsRangeResult.range_aggregate` for
            source-compatibility.
        exploitability: Computed via ``_rust.compute_exploitability`` on
            the returned strategy when
            ``compute_exploitability_at_end=True``. Float in chips/hand
            (same units as ``_rust.compute_exploitability``); ``0.0`` when
            the flag is False.
        iterations: Iteration count actually run.
        wall_clock_s: Total wall-clock for the solve (Rust solve only;
            Python overhead excluded).
        decision_node_count: Number of decision nodes in the betting tree
            (from Rust dict).
        hand_count_per_player: ``(p0_count, p1_count)`` of hands enumerated
            after board-collision filtering.
        memory_profile: Per-street memory breakdown from PR 23.
        backend: ``"rust_vector"`` (literal; matches PR 23 emit).
        position: ``"aggressor"`` if ``hero_player == 0`` else ``"defender"``
            (mirrors :class:`RangeVsRangeResult.position` semantics).
        warnings: Human-readable warnings (memory fallbacks, etc.).
    """

    per_history_strategy: dict[str, list[float]] = field(default_factory=dict)
    per_class_strategy: dict[HandClass, dict[str, float]] = field(default_factory=dict)
    range_aggregate: dict[str, float] = field(default_factory=dict)
    exploitability: float = 0.0
    iterations: int = 0
    wall_clock_s: float = 0.0
    decision_node_count: int = 0
    hand_count_per_player: tuple[int, int] = (0, 0)
    memory_profile: dict[str, Any] = field(default_factory=dict)
    backend: str = "rust_vector"
    position: str = "aggressor"
    warnings: list[str] = field(default_factory=list)


def _hole_string_rust(combo: tuple[Card, Card]) -> str:
    """Render a ``(Card, Card)`` combo as Rust's ``hole_string`` format.

    Mirrors ``crates/cfr_core/src/exploit.rs`` ``hole_string`` (referenced
    by ``dcfr_vector.rs:660-661``): sort by ``card_to_int`` ascending,
    then concatenate ``rank+suit`` characters. RANKS = ``"23456789TJQKA"``,
    SUITS = ``"shdc"`` (suit 0 = s, 1 = h, 2 = d, 3 = c).
    """
    ranks = "23456789TJQKA"
    suits = "shdc"

    def fmt(card: Card) -> tuple[int, str]:
        return card_to_int(card), f"{ranks[card.rank - 2]}{suits[card.suit]}"

    a, b = fmt(combo[0]), fmt(combo[1])
    if a[0] <= b[0]:
        return a[1] + b[1]
    return b[1] + a[1]


def solve_range_vs_range_nash(
    config_template: HUNLConfig,
    hero_range: Sequence[HandClass] | Range,
    villain_range: Sequence[HandClass] | Range,
    *,
    iterations: int = 500,
    alpha: float = 1.5,
    beta: float = 0.0,
    gamma: float = 2.0,
    hero_player: int = 0,
    compute_exploitability_at_end: bool = True,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> RangeVsRangeNashResult:
    """Solve a range-vs-range query via PR 23's vector-form CFR (true Nash).

    Unlike :func:`solve_range_vs_range` (which is the Pluribus-blueprint
    aggregation workaround — see that function's docstring), this routine
    solves the **joint imperfect-information Nash** of the supplied ranges
    using vector-form CFR. Hands are a vector dimension *inside* each
    infoset; the betting tree is walked once per iteration with full-range
    bluff-catching dynamics.

    Use this when you need:
      - True bluff-catching frequencies (e.g. "should JJ fold facing pot
        odds with 93% equity in this range?").
      - Polarized bet-sizing driven by range composition.
      - Brown / commercial-solver parity comparisons.

    Use :func:`solve_range_vs_range` instead when you need:
      - A fast 13x13 matrix Pluribus-style display.
      - Per-combo correctness on dry boards where the value-vs-air dynamic
        dominates and the approximation is tight.

    See ``docs/aggregator_vs_true_nash_explainer.md`` for the long-form
    distinction.

    Args:
        config_template: ``HUNLConfig`` with ``starting_street >= FLOP``.
            ``initial_hole_cards`` is ignored — the vector form enumerates
            hands per-player from the supplied ranges (after board-collision
            filtering, identical to the aggregator's filter).
        hero_range: hand-class labels or a ``Range``. Expanded to concrete
            combos for the Rust binding's ``p0_holes`` / ``p1_holes`` args.
        villain_range: Same.
        iterations: DCFR iterations. Default 500 (one vector-form solve
            replaces ~N per-class subsolves the aggregator runs).
        alpha, beta, gamma: DCFR hyperparameters; PLAN.md defaults
            (α=1.5 / β=0 / γ=2.0).
        hero_player: ``0`` (aggressor) or ``1`` (defender). Controls which
            player slot hero's range fills. The ``per_class_strategy``
            projection extracts that player's first-decision strategy.
        compute_exploitability_at_end: When True (default), invoke
            ``_rust.compute_exploitability`` once on the converged strategy
            and populate ``result.exploitability``. Skip when you only
            need the strategy.
        on_progress: Optional callback ``(iter_done, total_iter, phase_label)``.
            Currently fires once at start and once at end (vector CFR does
            not stream per-iteration progress in v1.7.0).

    Returns:
        ``RangeVsRangeNashResult`` with both the raw per-history strategy
        AND a per-class projection for UI compatibility.

    Raises:
        ValueError: hero/villain range empty; ``hero_player`` not in
            ``(0, 1)``; ``config_template.starting_street == PREFLOP``
            (vector-form preflop deferred); both ranges have zero
            board-feasible combos after collision filter.
        ImportError: ``poker_solver._rust`` does not expose
            ``solve_range_vs_range_rust`` (i.e. the Rust binding was not
            built with the v1.5+ PR 23 entry).
    """
    # ---- Argument validation (mirrors aggregator at lines 309-320) -----
    if hero_player not in (0, 1):
        raise ValueError(
            f"hero_player must be 0 (aggressor) or 1 (defender); got {hero_player!r}"
        )
    if config_template.starting_street == Street.PREFLOP:
        raise ValueError(
            "solve_range_vs_range_nash does not support preflop range-vs-range "
            "(vector-form preflop deferred per dcfr_vector.rs:49-50). For "
            "preflop subgame solves with fixed hole cards, call "
            "solve_hunl_preflop directly."
        )

    hero_classes = _normalize_range(hero_range)
    villain_classes = _normalize_range(villain_range)
    if not hero_classes:
        raise ValueError("hero_range is empty after parsing")
    if not villain_classes:
        raise ValueError("villain_range is empty after parsing")

    # ---- Import the Rust binding lazily ---------------------------------
    try:
        from poker_solver import _rust as _rust_module
    except ImportError as exc:  # pragma: no cover - defensive
        raise ImportError(
            "poker_solver._rust extension not available. "
            "Rebuild via `maturin develop --release` from the project root."
        ) from exc

    rust_solve = getattr(_rust_module, "solve_range_vs_range_rust", None)
    if rust_solve is None:
        raise ImportError(
            "poker_solver._rust.solve_range_vs_range_rust not found. "
            "The Rust extension was built without PR 23's vector-form "
            "entry (v1.5.0+). Rebuild via `maturin develop --release`."
        )

    # ---- Expand classes to concrete combos and board-filter -------------
    board_cards = set(config_template.initial_board)

    def _expand(classes: list[HandClass]) -> list[tuple[Card, Card]]:
        out: list[tuple[Card, Card]] = []
        for cls in classes:
            combos = _enumerate_combos(cls)
            for c in combos:
                if c[0] in board_cards or c[1] in board_cards:
                    continue
                out.append(c)
        return out

    hero_combos = _expand(hero_classes)
    villain_combos = _expand(villain_classes)
    if not hero_combos:
        raise ValueError(
            f"hero_range has zero board-feasible combos on board "
            f"{sorted(board_cards)!r}"
        )
    if not villain_combos:
        raise ValueError(
            f"villain_range has zero board-feasible combos on board "
            f"{sorted(board_cards)!r}"
        )

    # ---- Build per-player hand lists for the Rust binding ---------------
    # Convention: hero_player == 0 → hero combos become p0_holes; hero == 1
    # → hero combos become p1_holes. The vector form enumerates both
    # players' hand vectors from these lists.
    if hero_player == 0:
        p0_combos: list[tuple[Card, Card]] = hero_combos
        p1_combos: list[tuple[Card, Card]] = villain_combos
    else:
        p0_combos = villain_combos
        p1_combos = hero_combos

    p0_holes: list[list[int]] = [
        [card_to_int(c[0]), card_to_int(c[1])] for c in p0_combos
    ]
    p1_holes: list[list[int]] = [
        [card_to_int(c[0]), card_to_int(c[1])] for c in p1_combos
    ]

    # ---- Serialize config + call Rust binding ---------------------------
    # The vector form requires `initial_hole_cards = None` (per
    # `dcfr_vector.rs:746-750`); strip whatever the caller passed.
    nash_config = replace(config_template, initial_hole_cards=())
    config_json = _serialize_hunl_config(nash_config)

    if on_progress is not None:
        on_progress(0, iterations, "solve_start")

    t0 = time.perf_counter()
    rust_out = rust_solve(
        config_json,
        iterations,
        alpha,
        beta,
        gamma,
        p0_holes,
        p1_holes,
    )
    wall_clock_s = time.perf_counter() - t0

    if on_progress is not None:
        on_progress(iterations, iterations, "solve_done")

    average_strategy: dict[str, list[float]] = dict(rust_out["average_strategy"])
    hand_counts_raw = rust_out["hand_count_per_player"]
    hand_count_per_player = (int(hand_counts_raw[0]), int(hand_counts_raw[1]))

    # ---- Optional exploitability walk -----------------------------------
    exploit_val = 0.0
    if compute_exploitability_at_end and len(average_strategy) > 0:
        compute_expl = getattr(_rust_module, "compute_exploitability", None)
        if compute_expl is not None:
            expl_out = compute_expl(config_json, average_strategy)
            exploit_val = float(expl_out["exploitability"])

    # ---- Per-history → per-class projection (hero's first decision) -----
    # Walk from the initial state, following villain's modal action when
    # villain acts first, until we reach hero_player's first decision.
    # Look up the per-(hand, action) rows in average_strategy for each
    # hero combo, then group by hand class and average within the class.
    per_class, range_agg, action_labels = _project_to_hand_classes(
        config=nash_config,
        average_strategy=average_strategy,
        hero_combos=hero_combos,
        hero_classes=hero_classes,
        hero_player=hero_player,
    )

    # ---- Memory profile unpack ------------------------------------------
    memory_profile_raw = rust_out.get("memory_profile", {})
    memory_profile: dict[str, Any] = {}
    if isinstance(memory_profile_raw, dict):
        # Defensive shallow copy — PyO3 returns a PyDict which is dict-like.
        for k, v in memory_profile_raw.items():
            memory_profile[str(k)] = v

    warnings_list: list[str] = []
    if not per_class:
        warnings_list.append(
            "per_class_strategy projection produced no entries — hero may "
            "never reach a decision on the betting tree's modal villain "
            "line, or every hero combo was filtered by board collision."
        )

    # `action_labels` is captured for future use; not stored on the
    # result dataclass per spec §3.1 schema lock, but is reflected in
    # `range_aggregate` / `per_class_strategy` keys.
    del action_labels

    return RangeVsRangeNashResult(
        per_history_strategy=average_strategy,
        per_class_strategy=per_class,
        range_aggregate=range_agg,
        exploitability=exploit_val,
        iterations=int(rust_out.get("iterations", iterations)),
        wall_clock_s=wall_clock_s,
        decision_node_count=int(rust_out.get("decision_node_count", 0)),
        hand_count_per_player=hand_count_per_player,
        memory_profile=memory_profile,
        backend=str(rust_out.get("backend", "rust_vector")),
        position="aggressor" if hero_player == 0 else "defender",
        warnings=warnings_list,
    )


def _project_to_hand_classes(
    *,
    config: HUNLConfig,
    average_strategy: dict[str, list[float]],
    hero_combos: list[tuple[Card, Card]],
    hero_classes: list[HandClass],
    hero_player: int,
) -> tuple[dict[HandClass, dict[str, float]], dict[str, float], list[str]]:
    """Project the per-(history, hand) Nash strategy onto hand classes.

    Walks the betting tree from the initial state through the engine's
    legal-action enumeration; when the current player is NOT hero, follow
    villain's modal action under the solved strategy (matches the
    aggregator's ``_extract_first_decision_freqs`` convention). When the
    current player IS hero, look up the per-(hand, action) rows for every
    hero combo at that infoset key, group by hand class, and average.

    Returns ``(per_class_strategy, range_aggregate, action_labels)`` where
    ``action_labels`` is the engine's labelling for the hero infoset.
    """
    # Need a placeholder hole-cards pair so HUNLPoker can walk the state
    # machine. We use the first hero/villain combo each; the tree shape
    # is hole-independent except for showdown utility, which we don't
    # touch here.
    game = HUNLPoker(config)
    state = game.initial_state()
    visited = 0
    while visited < 100:
        if game.is_terminal(state):
            return {}, {}, []
        cur = game.current_player(state)
        if cur == -1:
            outcomes = game.chance_outcomes(state)
            if not outcomes:
                return {}, {}, []
            state = game.apply(state, outcomes[0][0])
            visited += 1
            continue
        if cur != hero_player:
            # Follow villain's modal action. Look up villain's strategy
            # row for the FIRST villain combo (or any combo present in
            # the strategy dict at this infoset — they should all see
            # consistent decision sequencing).
            actions = game.legal_actions(state)
            key_suffix = _key_suffix_for_state(game, state, cur)
            modal_idx = _modal_action_index(
                average_strategy=average_strategy,
                key_suffix=key_suffix,
                player=cur,
                action_count=len(actions),
            )
            state = game.apply(state, actions[modal_idx])
            visited += 1
            continue
        # Hero's first decision — extract per-combo rows and project.
        actions = game.legal_actions(state)
        action_labels = [
            _label_for_action(a, config.bet_size_fractions) for a in actions
        ]
        key_suffix = _key_suffix_for_state(game, state, hero_player)
        per_class: dict[HandClass, list[list[float]]] = {}
        for combo in hero_combos:
            hole_str = _hole_string_rust(combo)
            full_key = hole_str + key_suffix
            row = average_strategy.get(full_key)
            if row is None or len(row) != len(actions):
                continue
            cls = _combo_to_hand_class(combo)
            per_class.setdefault(cls, []).append([float(x) for x in row])
        # Average within class.
        per_class_avg: dict[HandClass, dict[str, float]] = {}
        for cls, rows in per_class.items():
            if not rows:
                continue
            n = len(rows)
            avg = [sum(r[i] for r in rows) / n for i in range(len(action_labels))]
            per_class_avg[cls] = dict(zip(action_labels, avg, strict=True))
        range_agg = _aggregate_range(per_class_avg, hero_classes)
        return per_class_avg, range_agg, action_labels
    return {}, {}, []


def _key_suffix_for_state(game: HUNLPoker, state: Any, player: int) -> str:
    """Compute the ``|<board>|<street>|<history>`` portion of an infoset key.

    The Rust vector form emits keys as ``<hole>|<board>|<street>|<history>``.
    Python's ``HUNLState.infoset_key`` produces the same lossless format
    (per PR 23 spec). To look up rows for a specific hand we need the
    suffix only — we strip the hole prefix from the engine's full key.
    """
    full = game.infoset_key(state, player)
    idx = full.find("|")
    if idx < 0:
        return full
    return full[idx:]


def _modal_action_index(
    *,
    average_strategy: dict[str, list[float]],
    key_suffix: str,
    player: int,
    action_count: int,
) -> int:
    """Pick the action index with the highest average probability at this
    infoset, averaged across all hands present in the strategy dict for
    this key suffix.

    The strategy dict is keyed by ``<hole>|<key_suffix>``; we scan for
    any entries ending in the supplied ``key_suffix`` and use them to
    pick a modal action. Falls back to index 0 when no rows are found
    (matches the aggregator's defensive fallback).
    """
    _ = player  # captured for future use; not part of the current logic.
    sums = [0.0] * action_count
    count = 0
    for key, row in average_strategy.items():
        if not key.endswith(key_suffix):
            continue
        if len(row) != action_count:
            continue
        for i in range(action_count):
            sums[i] += row[i]
        count += 1
    if count == 0:
        return 0
    return max(range(action_count), key=lambda i: sums[i])


__all__ = [
    "DEFAULT_TIME_BUDGET_PER_SOLVE_S",
    "HandClass",
    "RangeVsRangeNashResult",
    "RangeVsRangeResult",
    "solve_range_vs_range",
    "solve_range_vs_range_nash",
]
