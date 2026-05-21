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
from functools import lru_cache
from importlib import resources
from typing import Final, Literal, cast

from poker_solver.card import RANK_VALUE, RANKS

Position = Literal["sb_jam", "bb_call_vs_jam"]

PUSHFOLD_MIN_BB: Final[int] = 2
PUSHFOLD_MAX_BB: Final[int] = 15
PUSHFOLD_CHART_VERSIONS: Final[frozenset[str]] = frozenset({"v1", "v1-placeholder"})
_VALID_POSITIONS: Final[frozenset[str]] = frozenset({"sb_jam", "bb_call_vs_jam"})
_CHART_RESOURCE: Final[str] = "pushfold_v1.json"


class PushFoldChartUnavailable(Exception):
    """Raised when no push/fold chart covers the requested configuration.

    Examples: stack depth outside [2, 15] BB, unknown position string, or
    chart data missing for a (depth, position) cell. Callers can catch this
    to fall back to the full tree solver.
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


def get_pushfold_strategy(stack_bb: int, position: str, hand: str) -> float:
    """Return the equilibrium aggressive-action frequency for `hand`.

    Args:
        stack_bb: effective stack depth in BB (integer, 2-15 inclusive).
        position: "sb_jam" (frequency SB shoves) or "bb_call_vs_jam"
            (frequency BB calls a SB jam).
        hand: hand-class string like "AA", "AKs", "AKo". Case-insensitive.

    Returns:
        Frequency in [0.0, 1.0]. Hands valid in notation but absent from the
        chart cell return 0.0 (sparse format default).

    Raises:
        ValueError: hand is malformed (bad ranks, missing suit indicator, etc).
        PushFoldChartUnavailable: stack_bb out of range or position unknown.
    """
    pos = _validate_stack_and_position(stack_bb, position)
    canonical = _canonicalize_hand(hand)
    chart = _get_chart_cell(stack_bb, pos)
    value = chart.get(canonical, 0.0)
    return float(value)


def get_full_range(stack_bb: int, position: str) -> dict[str, float]:
    """Return the full (hand_class -> frequency) mapping for one cell.

    Returns all 169 canonical hand classes; hands stored sparsely (e.g. with
    frequency 0.0) in the chart file are filled in explicitly so callers can
    rely on the full grid being present. The returned dict is fresh.
    """
    pos = _validate_stack_and_position(stack_bb, position)
    chart = _get_chart_cell(stack_bb, pos)
    return {cls: float(chart.get(cls, 0.0)) for cls in _all_hand_classes()}


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


def _canonical_hand_classes() -> list[str]:
    """Return all 169 strategically-distinct preflop hand classes.

    Ordered pairs first (AA..22), then suited (AKs..32s), then offsuit
    (AKo..32o) for deterministic iteration.
    """
    hands: list[str] = []
    for r in range(12, -1, -1):
        hands.append(RANKS[r] * 2)
    for hi in range(12, -1, -1):
        for lo in range(hi - 1, -1, -1):
            hands.append(RANKS[hi] + RANKS[lo] + "s")
    for hi in range(12, -1, -1):
        for lo in range(hi - 1, -1, -1):
            hands.append(RANKS[hi] + RANKS[lo] + "o")
    return hands


__all__ = [
    "PUSHFOLD_MIN_BB",
    "PUSHFOLD_MAX_BB",
    "PushFoldChartUnavailable",
    "Position",
    "get_pushfold_strategy",
    "get_full_range",
    "is_pushfold_mode",
]
