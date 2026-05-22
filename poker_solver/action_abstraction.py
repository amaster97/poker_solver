"""Bet-size action abstraction for HUNL (pure-functional, integer-arithmetic).

License posture: no third-party code derivation; original implementation
(NLHE bet/raise/cap rules are standard poker mechanics, not copied from any
specific reference repo).

A flat 14-action enum with five pot-fraction bet sizes and five pot-fraction
raise sizes, plus fold/check/call/all-in. Enumeration is parameterized by an
:class:`ActionContext` describing the per-decision pot/stack/aggressor state;
chip math is integer-only, with floats only entering during the pot-fraction
rounding step.
"""

from __future__ import annotations

from dataclasses import dataclass

ACTION_FOLD: int = 0
ACTION_CHECK: int = 1
ACTION_CALL: int = 2
ACTION_BET_33: int = 3
ACTION_BET_75: int = 4
ACTION_BET_100: int = 5
ACTION_BET_150: int = 6
ACTION_BET_200: int = 7
ACTION_RAISE_33: int = 8
ACTION_RAISE_75: int = 9
ACTION_RAISE_100: int = 10
ACTION_RAISE_150: int = 11
ACTION_RAISE_200: int = 12
ACTION_ALL_IN: int = 13

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

# Street values matching poker_solver.hunl.Street.PREFLOP. IntEnum integers
# compare equal to ints; using a constant here keeps this module free of any
# import on hunl.py to avoid circular imports.
_PREFLOP_INT: int = 0


@dataclass(frozen=True)
class ActionAbstractionConfig:
    """Game-wide abstraction parameters. Kept as a sibling helper for callers
    that prefer a single config object; not embedded in :class:`ActionContext`
    so the latter can carry only the per-decision fields the abstraction
    actually reads."""

    bet_size_fractions: tuple[float, ...] = (0.33, 0.75, 1.00, 1.50, 2.00)
    preflop_raise_cap: int = 4
    postflop_raise_cap: int = 3
    force_allin_threshold_bb: int = 1
    min_bet_bb: int = 1
    include_all_in: bool = True


@dataclass(frozen=True)
class ActionContext:
    pot: int
    to_call: int
    stacks: tuple[int, int]
    contributions: tuple[int, int]
    cur_player: int
    street: int  # Street IntEnum value (0=PREFLOP, 1=FLOP, 2=TURN, 3=RIVER)
    street_num_raises: int
    street_aggressor: int
    big_blind: int
    bet_size_fractions: tuple[float, ...] = (0.33, 0.75, 1.00, 1.50, 2.00)
    preflop_raise_cap: int = 4
    postflop_raise_cap: int = 3
    force_allin_threshold_bb: int = 1
    min_bet_bb: int = 1
    include_all_in: bool = True


class BetSizing:
    """Action-id constants grouped for callers that prefer attribute access."""

    FOLD: int = ACTION_FOLD
    CHECK: int = ACTION_CHECK
    CALL: int = ACTION_CALL
    BET_33: int = ACTION_BET_33
    BET_75: int = ACTION_BET_75
    BET_100: int = ACTION_BET_100
    BET_150: int = ACTION_BET_150
    BET_200: int = ACTION_BET_200
    RAISE_33: int = ACTION_RAISE_33
    RAISE_75: int = ACTION_RAISE_75
    RAISE_100: int = ACTION_RAISE_100
    RAISE_150: int = ACTION_RAISE_150
    RAISE_200: int = ACTION_RAISE_200
    ALL_IN: int = ACTION_ALL_IN


def _is_preflop(ctx: ActionContext) -> bool:
    return int(ctx.street) == _PREFLOP_INT


def _raise_cap(ctx: ActionContext) -> int:
    return ctx.preflop_raise_cap if _is_preflop(ctx) else ctx.postflop_raise_cap


def _min_bet(ctx: ActionContext) -> int:
    return ctx.min_bet_bb * ctx.big_blind


def _force_allin_chip_threshold(ctx: ActionContext) -> int:
    return ctx.force_allin_threshold_bb * ctx.big_blind


def _stack_remaining(ctx: ActionContext) -> int:
    return ctx.stacks[ctx.cur_player]


def _min_raise_increment(ctx: ActionContext) -> int:
    return max(ctx.to_call, ctx.big_blind)


def _bet_amount_for_fraction(ctx: ActionContext, fraction: float) -> int:
    raw = int(round(ctx.pot * fraction))
    return max(raw, _min_bet(ctx))


def _raise_to_for_fraction(ctx: ActionContext, fraction: float) -> int:
    aggressor_contrib = ctx.contributions[ctx.street_aggressor]
    raw_increment = int(round((ctx.pot + ctx.to_call) * fraction))
    raise_to = aggressor_contrib + raw_increment
    min_raise_to = aggressor_contrib + _min_raise_increment(ctx)
    return max(raise_to, min_raise_to)


def compute_bet_amount(action_id: int, ctx: ActionContext) -> int:
    """Return the chip delta added by an opening bet or an opening all-in."""

    stack = _stack_remaining(ctx)
    if action_id == ACTION_ALL_IN:
        return stack
    if action_id not in _BET_ACTION_IDS:
        raise ValueError(f"compute_bet_amount: action_id {action_id} is not a bet")
    fraction = ctx.bet_size_fractions[_BET_ACTION_IDS.index(action_id)]
    amount = _bet_amount_for_fraction(ctx, fraction)
    return min(amount, stack)


def compute_raise_to(action_id: int, ctx: ActionContext) -> int:
    """Return the new ``contributions[cur_player]`` total after a raise/all-in."""

    cur_contrib = ctx.contributions[ctx.cur_player]
    stack = _stack_remaining(ctx)
    max_raise_to = cur_contrib + stack
    if action_id == ACTION_ALL_IN:
        return max_raise_to
    if action_id not in _RAISE_ACTION_IDS:
        raise ValueError(f"compute_raise_to: action_id {action_id} is not a raise")
    fraction = ctx.bet_size_fractions[_RAISE_ACTION_IDS.index(action_id)]
    raise_to = _raise_to_for_fraction(ctx, fraction)
    return min(raise_to, max_raise_to)


def _enumerate_bets(ctx: ActionContext) -> list[int]:
    stack = _stack_remaining(ctx)
    seen_amounts: set[int] = set()
    actions: list[int] = []
    force_threshold = _force_allin_chip_threshold(ctx)
    for action_id, fraction in zip(_BET_ACTION_IDS, ctx.bet_size_fractions):
        raw_amount = _bet_amount_for_fraction(ctx, fraction)
        if raw_amount >= stack or (stack - raw_amount) <= force_threshold:
            continue
        if raw_amount in seen_amounts:
            continue
        seen_amounts.add(raw_amount)
        actions.append(action_id)
    return actions


def _enumerate_raises(ctx: ActionContext) -> list[int]:
    cur_contrib = ctx.contributions[ctx.cur_player]
    stack = _stack_remaining(ctx)
    max_raise_to = cur_contrib + stack
    seen_raise_tos: set[int] = set()
    actions: list[int] = []
    force_threshold = _force_allin_chip_threshold(ctx)
    for action_id, fraction in zip(_RAISE_ACTION_IDS, ctx.bet_size_fractions):
        raise_to = _raise_to_for_fraction(ctx, fraction)
        chips_added = raise_to - cur_contrib
        if raise_to >= max_raise_to or (stack - chips_added) <= force_threshold:
            continue
        if raise_to in seen_raise_tos:
            continue
        seen_raise_tos.add(raise_to)
        actions.append(action_id)
    return actions


def enumerate_legal_actions(ctx: ActionContext) -> list[int]:
    """Return the sorted list of legal action IDs for ``ctx``."""

    actions: list[int] = []
    stack = _stack_remaining(ctx)

    if stack <= 0:
        # Unreachable per HUNL invariant: stack-0 player has all_in[p]==True
        # so is never current player. Fail loudly per PR 3 audit (Should-fix).
        raise AssertionError("unreachable; stack<=0 implies all_in[p]==True")

    facing_bet = ctx.to_call > 0

    if facing_bet:
        actions.append(ACTION_FOLD)
        actions.append(ACTION_CALL)
    else:
        actions.append(ACTION_CHECK)

    cap = _raise_cap(ctx)
    cap_reached = ctx.street_num_raises >= cap

    if not cap_reached:
        if facing_bet:
            actions.extend(_enumerate_raises(ctx))
        else:
            actions.extend(_enumerate_bets(ctx))

    if ctx.include_all_in:
        actions.append(ACTION_ALL_IN)

    return sorted(actions)
