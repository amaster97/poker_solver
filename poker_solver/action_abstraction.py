"""Bet-size action abstraction for HUNL (pure-functional, integer-arithmetic).

License posture: no third-party code derivation; original implementation
(NLHE bet/raise/cap rules are standard poker mechanics, not copied from any
specific reference repo). The per-street-menu + raise-as-multiplier shapes
follow the *pattern* of `references/code/postflop-solver/src/action_tree.rs`
(per-street `*_bet_sizes` and the `BetSize::PrevBetRelative` raise primitive),
re-implemented from scratch — no AGPL code is transcribed.

A flat 14-action enum exposing up to five bet *slots* and five raise *slots*,
plus fold/check/call/all-in. The concrete chip size each slot maps to is
parameterized by the :class:`ActionContext`:

  * Opening bets pick a **per-street pot-fraction menu** (flop/turn/river),
    indexed positionally into the bet slots (``_BET_ACTION_IDS``).
  * Raises pick a **multiplier-of-the-bet-faced menu** (``raise_size_xs``),
    indexed positionally into the raise slots (``_RAISE_ACTION_IDS``); the
    raise-to amount is ``(bet faced) x multiplier`` (PrevBetRelative pattern),
    clamped to the min-raise floor and the all-in cap.

Chip math is integer-only, with floats only entering during the
pot-fraction / multiplier rounding step.
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

# Street values matching poker_solver.hunl.Street. IntEnum integers compare
# equal to ints; using constants here keeps this module free of any import on
# hunl.py to avoid circular imports.
_PREFLOP_INT: int = 0
_FLOP_INT: int = 1
_TURN_INT: int = 2
_RIVER_INT: int = 3

# OOP player index postflop. Per `hunl.py`, P1 (the big blind) acts first
# postflop, so P1 is the out-of-position player whose flop open is removed by
# the flop-no-donk constraint.
_OOP_PLAYER: int = 1

# Legacy flat default (back-compat): a single menu applied to every street.
_DEFAULT_BET_FRACTIONS: tuple[float, ...] = (0.33, 0.75, 1.00, 1.50, 2.00)

# C1 per-street opening-bet defaults (all-in is always offered separately).
_DEFAULT_FLOP_BET_FRACTIONS: tuple[float, ...] = (0.33, 0.75, 1.25)
_DEFAULT_TURN_BET_FRACTIONS: tuple[float, ...] = (0.33, 0.75, 1.50)
_DEFAULT_RIVER_BET_FRACTIONS: tuple[float, ...] = (0.15, 0.33, 0.75, 1.50)

# C2 lean raise default: one universal "multiple of the bet faced" size (3.0x),
# with all-in offered separately. No IP/OOP split (deferred).
_DEFAULT_RAISE_SIZE_XS: tuple[float, ...] = (3.0,)


@dataclass(frozen=True)
class ActionAbstractionConfig:
    """Game-wide abstraction parameters. Kept as a sibling helper for callers
    that prefer a single config object; not embedded in :class:`ActionContext`
    so the latter can carry only the per-decision fields the abstraction
    actually reads.

    ``bet_size_fractions`` is the legacy flat menu (back-compat): when the
    per-street menus are ``None`` it applies to every street. ``raise_size_xs``
    are multipliers of the bet faced (C2 lean raises)."""

    bet_size_fractions: tuple[float, ...] = _DEFAULT_BET_FRACTIONS
    flop_bet_fractions: tuple[float, ...] | None = None
    turn_bet_fractions: tuple[float, ...] | None = None
    river_bet_fractions: tuple[float, ...] | None = None
    raise_size_xs: tuple[float, ...] = _DEFAULT_RAISE_SIZE_XS
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
    # Legacy flat menu (back-compat). Used for any street whose per-street menu
    # below is None, and for preflop (which has no per-street menu).
    bet_size_fractions: tuple[float, ...] = _DEFAULT_BET_FRACTIONS
    # C1 per-street opening-bet menus. None => fall back to bet_size_fractions.
    flop_bet_fractions: tuple[float, ...] | None = None
    turn_bet_fractions: tuple[float, ...] | None = None
    river_bet_fractions: tuple[float, ...] | None = None
    # C2 raise menu: multipliers of the bet faced (PrevBetRelative). Defaults to
    # a single 3.0x size + all-in (offered separately).
    raise_size_xs: tuple[float, ...] = _DEFAULT_RAISE_SIZE_XS
    preflop_raise_cap: int = 4
    postflop_raise_cap: int = 3
    force_allin_threshold_bb: int = 1
    min_bet_bb: int = 1
    include_all_in: bool = True
    # Number of player actions already taken on the current street. Used by the
    # C3 flop-no-donk constraint to detect OOP's first-to-act flop decision.
    street_action_count: int = 0


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


def _bet_menu(ctx: ActionContext) -> tuple[float, ...]:
    """Return the opening-bet pot-fraction menu for ``ctx.street``.

    Selects the per-street menu (flop/turn/river) when present; otherwise
    falls back to the flat ``bet_size_fractions`` (back-compat, and the only
    menu used preflop). The menu length must not exceed the number of bet
    slots (``_BET_ACTION_IDS``); excess entries are silently truncated so a
    misconfigured long menu degrades gracefully rather than indexing past the
    enum."""
    street = int(ctx.street)
    menu: tuple[float, ...] | None
    if street == _FLOP_INT:
        menu = ctx.flop_bet_fractions
    elif street == _TURN_INT:
        menu = ctx.turn_bet_fractions
    elif street == _RIVER_INT:
        menu = ctx.river_bet_fractions
    else:
        menu = None
    if menu is None:
        menu = ctx.bet_size_fractions
    return tuple(menu[: len(_BET_ACTION_IDS)])


def _raise_menu(ctx: ActionContext) -> tuple[float, ...]:
    """Return the raise multiplier menu (multiples of the bet faced).

    Truncated to the number of raise slots (``_RAISE_ACTION_IDS``) for the
    same graceful-degradation reason as :func:`_bet_menu`."""
    return tuple(ctx.raise_size_xs[: len(_RAISE_ACTION_IDS)])


def _is_oop_flop_first_action(ctx: ActionContext) -> bool:
    """C3 flop-no-donk predicate.

    True iff the OOP player (P1) is first-to-act on the FLOP with no prior
    street aggression. Mirrors the postflop-solver pattern where the donk
    branch is gated on ``prev_action == Chance`` AND ``oop_call_flag`` and,
    when no donk menu is configured, OOP may only check. We have no stateful
    donk menu (deferred), so this predicate structurally removes OOP's flop
    open: street is FLOP, it is OOP's first action of the street
    (``street_action_count == 0``), there is no bet to call, and no aggressor
    has acted on this street."""
    return (
        int(ctx.street) == _FLOP_INT
        and ctx.cur_player == _OOP_PLAYER
        and ctx.street_action_count == 0
        and ctx.to_call == 0
        and ctx.street_aggressor < 0
    )


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


def _raise_to_for_multiplier(ctx: ActionContext, multiplier: float) -> int:
    """Raise-to total for a "multiple of the bet faced" raise (C2).

    PrevBetRelative pattern (postflop-solver ``action_tree.rs``): the raise-to
    contribution is ``round(bet_faced_total x multiplier)`` where the bet faced
    is the aggressor's current contribution. Clamped up to the min-raise floor
    (``aggressor_contrib + max(to_call, big_blind)``) so a small multiplier can
    never produce an illegal under-raise."""
    aggressor_contrib = ctx.contributions[ctx.street_aggressor]
    raise_to = int(round(aggressor_contrib * multiplier))
    min_raise_to = aggressor_contrib + _min_raise_increment(ctx)
    return max(raise_to, min_raise_to)


def compute_bet_amount(action_id: int, ctx: ActionContext) -> int:
    """Return the chip delta added by an opening bet or an opening all-in."""

    stack = _stack_remaining(ctx)
    if action_id == ACTION_ALL_IN:
        return stack
    if action_id not in _BET_ACTION_IDS:
        raise ValueError(f"compute_bet_amount: action_id {action_id} is not a bet")
    fraction = _bet_menu(ctx)[_BET_ACTION_IDS.index(action_id)]
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
    multiplier = _raise_menu(ctx)[_RAISE_ACTION_IDS.index(action_id)]
    raise_to = _raise_to_for_multiplier(ctx, multiplier)
    return min(raise_to, max_raise_to)


def _enumerate_bets(ctx: ActionContext) -> list[int]:
    stack = _stack_remaining(ctx)
    seen_amounts: set[int] = set()
    actions: list[int] = []
    force_threshold = _force_allin_chip_threshold(ctx)
    for action_id, fraction in zip(_BET_ACTION_IDS, _bet_menu(ctx)):
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
    for action_id, multiplier in zip(_RAISE_ACTION_IDS, _raise_menu(ctx)):
        raise_to = _raise_to_for_multiplier(ctx, multiplier)
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

    # C3 flop-no-donk: structurally remove OOP's first-to-act flop open. When
    # the predicate fires we offer only CHECK (no opening bets, no all-in);
    # betting reopens for IP after the check, and on later streets. Does not
    # affect facing-bet nodes (those go through the raise branch).
    flop_no_donk = (not facing_bet) and _is_oop_flop_first_action(ctx)

    if not cap_reached and not flop_no_donk:
        if facing_bet:
            actions.extend(_enumerate_raises(ctx))
        else:
            actions.extend(_enumerate_bets(ctx))

    # Facing-all-in + cap guards: when opponent has shoved and our remaining
    # stack <= to_call, the only chip action is CALL. Emitting ALL_IN here
    # creates a degenerate action semantically identical to CALL but with
    # its own regret bucket, redistributing probability mass and diverging
    # from Brown's reference (see cpp/src/river_game.cpp:76 + 98). Brown
    # returns `[c, f]` at the cap (line 76) without enumerating raises OR
    # an all-in, so we mirror that by gating ALL_IN on `not cap_reached`.
    # The flop-no-donk constraint also suppresses the opening all-in.
    stack = _stack_remaining(ctx)
    can_actually_raise = stack > ctx.to_call
    if ctx.include_all_in and not cap_reached and not flop_no_donk and can_actually_raise:
        actions.append(ACTION_ALL_IN)

    return sorted(actions)
