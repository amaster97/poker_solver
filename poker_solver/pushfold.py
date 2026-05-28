"""Push/fold chart lookup for short-stack HUNL (2-15 BB effective).

At very short stacks, optimal HUNL preflop collapses to shove-or-fold; running
the tree builder + DCFR is wasteful. This module exposes static charts
(`charts/pushfold_v1.json`) via a small Python API and provides the dispatch
helper used by `solver.solve()` to route eligible games to the lookup path.

The chart data is the source of truth: Agent B's generator computes Nash
equilibria via DCFR and writes the JSON; this module only reads it.
"""

from __future__ import annotations

import json
import random
from functools import cache, lru_cache
from importlib import resources
from typing import TYPE_CHECKING, Final, Literal, cast

from poker_solver.card import RANK_VALUE, Card

if TYPE_CHECKING:
    from poker_solver.hunl import HUNLConfig
    from poker_solver.solver import SolveResult

Position = Literal["sb_jam", "bb_call_vs_jam"]

PUSHFOLD_MIN_BB: Final[int] = 2
PUSHFOLD_MAX_BB: Final[int] = 15
PUSHFOLD_CHART_VERSIONS: Final[frozenset[str]] = frozenset({"v1"})
_EXPLOITABILITY_GATE_BB_PER_100: Final[float] = 0.05
_VALID_POSITIONS: Final[frozenset[str]] = frozenset({"sb_jam", "bb_call_vs_jam"})
_CHART_RESOURCE: Final[str] = "pushfold_v1.json"

# Blind sizes (BB units). Matches scripts/generate_pushfold_charts.py.
_SMALL_BLIND_BB: Final[float] = 0.5
_BIG_BLIND_BB: Final[float] = 1.0

# Default Monte Carlo iterations for EV computation. Tuned for ~0.01 BB
# resolution per hand at depths in [2, 15].
_EV_DEFAULT_ITERATIONS: Final[int] = 20_000
_EV_RNG_SEED: Final[int] = 0xC0FFEE


class PushFoldChartUnavailable(ValueError):
    """Raised when no push/fold chart covers the requested configuration.

    Examples: stack depth outside [2, 15] BB, unknown position string, or
    chart data missing for a (depth, position) cell. Callers can catch this
    to fall back to the full tree solver. Subclasses ``ValueError`` so the
    spec §6 ``Raises: ValueError`` contract holds: ``except ValueError``
    in caller code catches this branch.
    """


@lru_cache(maxsize=1)
def _load_chart_data() -> dict[str, object]:
    """Load and cache the canonical pushfold chart JSON shipped with the package."""
    chart_resource = resources.files("poker_solver.charts").joinpath(_CHART_RESOURCE)
    with chart_resource.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    version = payload.get("version")
    if version not in PUSHFOLD_CHART_VERSIONS:
        raise PushFoldChartUnavailable(
            f"Unsupported pushfold chart version: {version!r}. "
            f"Known versions: {sorted(PUSHFOLD_CHART_VERSIONS)}."
        )
    final_expl = payload.get("final_exploitability_bb_per_100")
    if final_expl is None:
        raise PushFoldChartUnavailable(
            "Chart metadata missing 'final_exploitability_bb_per_100' scalar; "
            "regenerate via scripts/generate_pushfold_charts.py."
        )
    if (
        not isinstance(final_expl, (int, float))
        or float(final_expl) >= _EXPLOITABILITY_GATE_BB_PER_100
    ):
        raise PushFoldChartUnavailable(
            f"Chart final_exploitability_bb_per_100={final_expl!r} fails the "
            f"convergence gate (must be < {_EXPLOITABILITY_GATE_BB_PER_100})."
        )
    return cast(dict[str, object], payload)


def _canonicalize_hand(hand: str) -> str:
    """Return the canonical hand-class string for `hand`.

    Accepts case-insensitive pair ("AA", "tt"), suited ("AKs", "akS"), or
    offsuit ("AKo") notation. Rejects 4-character specific combos like
    "AhKh" — those identify a single combo, not a hand class.
    """
    if not isinstance(hand, str):
        raise ValueError(f"hand must be a string, got {type(hand).__name__}")
    token = hand.strip()
    if len(token) not in (2, 3):
        raise ValueError(
            f"Invalid hand class {hand!r}: expected 2 chars (pair) or 3 (suited/offsuit)"
        )
    r1 = token[0].upper()
    r2 = token[1].upper()
    if r1 not in RANK_VALUE or r2 not in RANK_VALUE:
        raise ValueError(f"Invalid ranks in hand class {hand!r}")
    v1, v2 = RANK_VALUE[r1], RANK_VALUE[r2]
    if v1 == v2:
        if len(token) == 3:
            raise ValueError(f"Pair {hand!r} cannot have suit indicator")
        return r1 + r2
    suit = token[2].lower() if len(token) == 3 else None
    if suit is not None and suit not in ("s", "o"):
        raise ValueError(f"Invalid suit indicator in {hand!r}; use 's' or 'o'")
    if suit is None:
        raise ValueError(f"Non-pair hand class {hand!r} requires 's' or 'o' suffix")
    if v1 < v2:
        v1, v2 = v2, v1
        r1, r2 = r2, r1
    return r1 + r2 + suit


def _validate_stack_and_position(stack_bb: int, position: str) -> Position:
    if not isinstance(stack_bb, int) or isinstance(stack_bb, bool):
        raise ValueError(f"stack_bb must be int, got {type(stack_bb).__name__}")
    if stack_bb < PUSHFOLD_MIN_BB or stack_bb > PUSHFOLD_MAX_BB:
        raise PushFoldChartUnavailable(
            f"stack_bb={stack_bb} outside supported range "
            f"[{PUSHFOLD_MIN_BB}, {PUSHFOLD_MAX_BB}]; "
            "use the tree-builder solver for deeper stacks."
        )
    if position not in _VALID_POSITIONS:
        raise PushFoldChartUnavailable(
            f"Unknown position {position!r}; expected one of {sorted(_VALID_POSITIONS)}."
        )
    return cast(Position, position)


def get_pushfold_strategy(
    stack_bb: int,
    position: str,
    hand: str,
    *,
    return_ev: bool = False,
) -> float | dict[str, float]:
    """Return the equilibrium aggressive-action frequency for `hand`.

    Args:
        stack_bb: effective stack depth in BB (integer, 2-15 inclusive).
        position: "sb_jam" (frequency SB shoves) or "bb_call_vs_jam"
            (frequency BB calls a SB jam).
        hand: hand-class string like "AA", "AKs", "AKo". Case-insensitive.
        return_ev: if False (default), returns the frequency as a float
            (backward compat). If True, returns a dict
            ``{"strategy": prob, "ev_bb": ev}`` where ``ev_bb`` is the EV
            (in BB units) of the aggressive action (jam for ``sb_jam``,
            call for ``bb_call_vs_jam``) against the equilibrium opposing
            chart range at this depth. The EV is computed by Monte Carlo
            equity sampling and includes the blinds posted by both players.

    Returns:
        - ``return_ev=False``: frequency in [0.0, 1.0]. Hands absent from
          the chart cell return 0.0 (sparse default).
        - ``return_ev=True``: ``{"strategy": prob, "ev_bb": ev_bb}`` dict.

    Raises:
        ValueError: hand is malformed (bad ranks, missing suit indicator, etc).
        PushFoldChartUnavailable: stack_bb out of range or position unknown.
    """
    pos = _validate_stack_and_position(stack_bb, position)
    canonical = _canonicalize_hand(hand)
    chart = _get_chart_cell(stack_bb, pos)
    value = chart.get(canonical, 0.0)
    prob = float(value)
    if not return_ev:
        return prob
    ev_bb = _compute_aggressive_ev_bb(stack_bb, pos, canonical)
    return {"strategy": prob, "ev_bb": ev_bb}


def get_full_range(stack_bb: int, position: str) -> dict[str, float]:
    """Return the full (hand_class -> frequency) mapping for one cell.

    Returns all 169 canonical hand classes; hands stored sparsely (e.g. with
    frequency 0.0) in the chart file are filled in explicitly so callers can
    rely on the full grid being present. The returned dict is fresh.
    """
    pos = _validate_stack_and_position(stack_bb, position)
    chart = _get_chart_cell(stack_bb, pos)
    return {cls: float(chart.get(cls, 0.0)) for cls in _all_hand_classes()}


# Spec §6 line 165 names this `get_pushfold_range`; we kept the shorter
# `get_full_range` as the canonical implementation and alias the spec name so
# downstream callers using either name compile.
get_pushfold_range = get_full_range


def solve_pushfold(config: HUNLConfig) -> SolveResult:
    """Return a SolveResult built from the static push/fold charts.

    Public spec §6 entry point. The effective stack depth is rounded down to
    the nearest BB to pick a chart cell; both positions' charts are flattened
    into ``average_strategy`` so downstream callers can inspect either side.
    Strategy vectors are ``[fold_prob, aggressive_prob]`` keyed by
    ``f"pushfold|{position}|{eff_bb}BB|{hand}"`` (a chart-specific format,
    documented because no real HUNL game tree exists in the chart path).

    Args:
        config: an ``HUNLConfig`` whose effective stack falls in
            ``[PUSHFOLD_MIN_BB, PUSHFOLD_MAX_BB]`` (= [2, 15] BB).

    Returns:
        ``SolveResult`` with ``backend == "pushfold_chart"``,
        ``iterations == 0`` (non-iterative path), ``exploitability_history``
        as a single-element list of the depth-specific residual exploitability
        from chart metadata, and ``game_value == 0.0`` placeholder (chart JSON
        does not yet persist per-depth SB EV; spec §6 line 212).

    Raises:
        ValueError: ``eff_stack_bb > PUSHFOLD_MAX_BB`` (caller should use the
            tree-builder solver) or ``< PUSHFOLD_MIN_BB`` (degenerate — both
            players are auto-allin and a chart cell does not exist).
    """
    # Localized import to avoid a hard import cycle: solver.py imports
    # pushfold.py at module top, so importing SolveResult at module top here
    # would form a cycle. Deferring to call time breaks the cycle.
    from poker_solver.solver import SolveResult

    eff_bb = config.starting_stack // config.big_blind
    if eff_bb < PUSHFOLD_MIN_BB:
        raise ValueError(
            f"Effective stack {eff_bb} BB < {PUSHFOLD_MIN_BB} BB minimum; "
            "both players are auto-allin pre-deal at this depth and no chart "
            "cell exists. Use the tree-builder solver instead."
        )
    if eff_bb > PUSHFOLD_MAX_BB:
        raise ValueError(
            f"Effective stack {eff_bb} BB > {PUSHFOLD_MAX_BB} BB maximum; "
            "use the tree-builder solver for deeper stacks."
        )
    strategy: dict[str, list[float]] = {}
    for position in ("sb_jam", "bb_call_vs_jam"):
        chart = get_full_range(eff_bb, position)
        for hand, freq in chart.items():
            key = f"pushfold|{position}|{eff_bb}BB|{hand}"
            agg = float(freq)
            strategy[key] = [1.0 - agg, agg]
    # Surface the depth-specific residual exploitability from the JSON
    # rather than a zero placeholder so callers reading
    # ``result.exploitability_history[-1]`` get a faithful value.
    payload = _load_chart_data()
    per_depth_expl = cast(
        dict[str, float],
        payload.get("exploitability_bb_per_100", {}),
    )
    expl = float(per_depth_expl.get(str(eff_bb), 0.0))
    # game_value=0.0 is a documented placeholder (see docstring Returns).
    return SolveResult(
        average_strategy=strategy,
        exploitability_history=[expl],
        game_value=0.0,
        iterations=0,
        backend="pushfold_chart",
    )


def _all_hand_classes() -> tuple[str, ...]:
    """Enumerate the 169 canonical hand classes (13 pairs + 78 suited + 78 offsuit)."""
    ranks = "AKQJT98765432"
    out: list[str] = []
    for i, r1 in enumerate(ranks):
        for j, r2 in enumerate(ranks):
            if i == j:
                out.append(f"{r1}{r1}")
            elif i < j:
                out.append(f"{r1}{r2}s")
            else:
                out.append(f"{r2}{r1}o")
    # 13 pairs + 78 suited + 78 offsuit = 169
    return tuple(out)


def is_pushfold_mode(stack_size_chips: int, big_blind_chips: int) -> bool:
    """Return True iff the effective stack is short enough for chart lookup.

    Threshold: effective_stack_bb <= 15. Returns False for non-positive
    big_blind_chips (caller has a malformed config; let downstream logic
    raise rather than silently dispatching).
    """
    if big_blind_chips <= 0:
        return False
    eff_bb = stack_size_chips / big_blind_chips
    return PUSHFOLD_MIN_BB <= eff_bb <= PUSHFOLD_MAX_BB


def _get_chart_cell(stack_bb: int, position: Position) -> dict[str, float]:
    payload = _load_chart_data()
    charts = cast(dict[str, dict[str, dict[str, float]]], payload["charts"])
    position_charts = charts.get(position)
    if position_charts is None:
        raise PushFoldChartUnavailable(
            f"Chart file missing position {position!r}; check chart data integrity."
        )
    cell = position_charts.get(str(stack_bb))
    if cell is None:
        raise PushFoldChartUnavailable(
            f"Chart file missing depth {stack_bb} BB for position {position!r}."
        )
    return cell


# ---------------------------------------------------------------------------
# EV computation (for ``return_ev=True`` lookups).
# ---------------------------------------------------------------------------


def _expand_combos(hand: str) -> list[tuple[Card, Card]]:
    """Return all concrete 2-card combos for a canonical hand class."""
    if len(hand) == 2:
        rank = RANK_VALUE[hand[0]]
        return [
            (Card(rank, s1), Card(rank, s2))
            for s1 in range(4)
            for s2 in range(s1 + 1, 4)
        ]
    hi = RANK_VALUE[hand[0]]
    lo = RANK_VALUE[hand[1]]
    suit_flag = hand[2]
    combos: list[tuple[Card, Card]] = []
    if suit_flag == "s":
        for s in range(4):
            combos.append((Card(hi, s), Card(lo, s)))
    else:  # offsuit
        for s1 in range(4):
            for s2 in range(4):
                if s1 != s2:
                    combos.append((Card(hi, s1), Card(lo, s2)))
    return combos


def _equity_combo_vs_combo(
    a: tuple[Card, Card],
    b: tuple[Card, Card],
    rng: random.Random,
    boards: int,
) -> float | None:
    """SB combo equity vs BB combo across `boards` random runouts.

    Returns ``None`` if the two combos share a card (incompatible).
    """
    # Lazy import to avoid a circular import: equity.py -> range.py -> ... at
    # module load; pushfold.py is imported during the package init.
    from poker_solver.evaluator import evaluate

    if a[0] == b[0] or a[0] == b[1] or a[1] == b[0] or a[1] == b[1]:
        return None
    used = {a[0], a[1], b[0], b[1]}
    deck = [Card(r, s) for r in range(2, 15) for s in range(4) if Card(r, s) not in used]
    a_hand = list(a)
    b_hand = list(b)
    wins = 0
    ties = 0
    sample = rng.sample
    for _ in range(boards):
        board = sample(deck, 5)
        sa = evaluate(a_hand + board)
        sb = evaluate(b_hand + board)
        if sa > sb:
            wins += 1
        elif sa == sb:
            ties += 1
    return (wins + 0.5 * ties) / boards


@cache
def _compute_aggressive_ev_bb(stack_bb: int, position: Position, hand: str) -> float:
    """EV (in BB) of the aggressive action (jam / call vs jam) for `hand`.

    Computed by Monte Carlo equity sampling against the equilibrium opposing
    chart range at this depth, then combined with the chart's payoff structure
    (blinds + showdown EV). Results are cached per ``(stack_bb, position, hand)``
    so repeat lookups are O(1) after the first call.

    The aggressive-action EV is well-defined for any hand even if its strategy
    probability is 0 — it answers "what would this hand earn if it took the
    aggressive line?" which is what Marcus's chart-lookup persona wants.

    For SB ``sb_jam`` at depth D BB:
        EV_jam(h) = sum_{h'} P(h') * [
            p_call(h') * D*(2*equity(h, h') - 1)        # showdown branch
          + (1 - p_call(h')) * BIG_BLIND                 # BB folds branch
        ]

    For BB ``bb_call_vs_jam`` at depth D BB:
        EV_call(h) = sum_{h'} P(h' | h' jammed) * (-1) * D*(2*equity(h', h) - 1)
        (BB's showdown EV = - SB's showdown EV; conditioning on SB having
        jammed via Bayes' rule using the SB jam-frequency vector.)
    """
    opp_position: Position = (
        "bb_call_vs_jam" if position == "sb_jam" else "sb_jam"
    )
    opp_chart = _get_chart_cell(stack_bb, opp_position)

    # Combo-weighted opposing range. For ``sb_jam`` (we're SB, opp is BB), we
    # treat all BB hands as equally likely a priori (combo-count weighted);
    # the call/fold split is handled inside the payoff sum below. For
    # ``bb_call_vs_jam`` (we're BB facing SB's jam) we condition the opp prior
    # on SB having jammed via Bayes' rule: P(h_sb | jammed) ∝ p_jam(h_sb) * combos.
    classes = _all_hand_classes()
    if position == "sb_jam":
        opp_prior: dict[str, float] = {h: float(_combo_count(h)) for h in classes}
    else:
        opp_prior = {
            h: float(_combo_count(h)) * float(opp_chart.get(h, 0.0))
            for h in classes
        }
    prior_sum = sum(opp_prior.values())
    if prior_sum <= 0:
        # Pathological: opp never jams (or chart is empty). Fall back to the
        # uncontested branch only.
        return _BIG_BLIND_BB if position == "sb_jam" else -_BIG_BLIND_BB

    rng = random.Random(_EV_RNG_SEED ^ hash((stack_bb, position, hand)))
    hand_combos = _expand_combos(hand)
    total_ev = 0.0
    total_w = 0.0
    # Allocate boards-per-opp-class evenly across nonzero-prior opp classes,
    # with a floor for rare classes. Total Monte Carlo budget is bounded by
    # _EV_DEFAULT_ITERATIONS.
    min_boards = 50
    weighted_opps = [(h, w) for h, w in opp_prior.items() if w > 0.0]
    base = max(min_boards, _EV_DEFAULT_ITERATIONS // max(1, len(weighted_opps)))
    for opp_hand, opp_w in weighted_opps:
        opp_combos = _expand_combos(opp_hand)
        boards = max(min_boards, int(base))
        equity_sample: float | None = None
        for _attempt in range(8):
            combo_a = rng.choice(hand_combos)
            combo_b = rng.choice(opp_combos)
            eq = _equity_combo_vs_combo(combo_a, combo_b, rng, boards)
            if eq is not None:
                equity_sample = eq
                break
        if equity_sample is None:
            # No card-compatible (combo_hero, combo_opp); skip this class.
            continue
        if position == "sb_jam":
            # opp = BB. EV depends on whether BB calls (showdown) or folds.
            p_call_opp = float(opp_chart.get(opp_hand, 0.0))
            showdown_ev = float(stack_bb) * (2.0 * equity_sample - 1.0)
            ev_this = (
                p_call_opp * showdown_ev
                + (1.0 - p_call_opp) * _BIG_BLIND_BB
            )
        else:
            # opp = SB (prior already conditioned on SB jamming). BB's
            # showdown EV mirrors SB's: ev_bb = D*(2*equity_bb - 1).
            ev_this = float(stack_bb) * (2.0 * equity_sample - 1.0)
        total_ev += opp_w * ev_this
        total_w += opp_w
    if total_w <= 0:
        return _BIG_BLIND_BB if position == "sb_jam" else -_BIG_BLIND_BB
    return total_ev / total_w


@cache
def _combo_count(hand: str) -> int:
    """Number of concrete combos in a canonical hand-class string (6/4/12)."""
    return len(_expand_combos(hand))


__all__ = [
    "PUSHFOLD_MIN_BB",
    "PUSHFOLD_MAX_BB",
    "PushFoldChartUnavailable",
    "Position",
    "get_pushfold_strategy",
    "get_full_range",
    "get_pushfold_range",
    "is_pushfold_mode",
    "solve_pushfold",
]
