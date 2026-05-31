from __future__ import annotations

from poker_solver import (
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
    ActionContext,
    Street,
    compute_bet_amount,
    compute_raise_to,
    enumerate_legal_actions,
)

DEFAULT_FRACTIONS = (0.33, 0.75, 1.00, 1.50, 2.00)
# Legacy-style raise menu (5 pot-multiplier sizes) for tests that exercise the
# full raise-slot fan-out. Production default is the lean (3.0,) menu.
FIVE_RAISE_XS = (1.5, 2.0, 3.0, 4.0, 5.0)


def _ctx(
    *,
    pot: int,
    to_call: int = 0,
    stacks: tuple[int, int] = (10_000, 10_000),
    contributions: tuple[int, int] = (0, 0),
    cur_player: int = 0,
    street: Street = Street.FLOP,
    street_num_raises: int = 0,
    street_aggressor: int = -1,
    big_blind: int = 100,
    bet_size_fractions: tuple[float, ...] = DEFAULT_FRACTIONS,
    flop_bet_fractions: tuple[float, ...] | None = None,
    turn_bet_fractions: tuple[float, ...] | None = None,
    river_bet_fractions: tuple[float, ...] | None = None,
    raise_size_xs: tuple[float, ...] = (3.0,),
    preflop_raise_cap: int = 4,
    postflop_raise_cap: int = 3,
    force_allin_threshold_bb: int = 1,
    min_bet_bb: int = 1,
    include_all_in: bool = True,
    street_action_count: int = 0,
) -> ActionContext:
    return ActionContext(
        pot=pot,
        to_call=to_call,
        stacks=stacks,
        contributions=contributions,
        cur_player=cur_player,
        street=street,
        street_num_raises=street_num_raises,
        street_aggressor=street_aggressor,
        big_blind=big_blind,
        bet_size_fractions=bet_size_fractions,
        flop_bet_fractions=flop_bet_fractions,
        turn_bet_fractions=turn_bet_fractions,
        river_bet_fractions=river_bet_fractions,
        raise_size_xs=raise_size_xs,
        preflop_raise_cap=preflop_raise_cap,
        postflop_raise_cap=postflop_raise_cap,
        force_allin_threshold_bb=force_allin_threshold_bb,
        min_bet_bb=min_bet_bb,
        include_all_in=include_all_in,
        street_action_count=street_action_count,
    )


def test_abstraction_bet_actions_when_to_call_zero():
    ctx = _ctx(pot=200, to_call=0)
    legal = enumerate_legal_actions(ctx)
    assert ACTION_CHECK in legal
    assert ACTION_FOLD not in legal
    bet_ids = {
        ACTION_BET_33,
        ACTION_BET_75,
        ACTION_BET_100,
        ACTION_BET_150,
        ACTION_BET_200,
    }
    assert bet_ids.issubset(set(legal))
    assert ACTION_ALL_IN in legal


def test_abstraction_raise_actions_when_to_call_positive():
    # Use a 5-size raise menu so every raise slot fans out (the lean production
    # default is a single 3.0x size; see test_lean_raise_default_single_size).
    ctx = _ctx(
        pot=300,
        to_call=100,
        contributions=(100, 200),
        street_num_raises=1,
        street_aggressor=1,
        cur_player=0,
        raise_size_xs=FIVE_RAISE_XS,
    )
    legal = enumerate_legal_actions(ctx)
    assert ACTION_FOLD in legal
    assert ACTION_CALL in legal
    raise_ids = {
        ACTION_RAISE_33,
        ACTION_RAISE_75,
        ACTION_RAISE_100,
        ACTION_RAISE_150,
        ACTION_RAISE_200,
    }
    assert raise_ids.issubset(set(legal))
    assert ACTION_ALL_IN in legal


def test_abstraction_no_raise_at_cap():
    ctx = _ctx(
        pot=2000,
        to_call=500,
        contributions=(500, 1000),
        street=Street.FLOP,
        street_num_raises=3,
        street_aggressor=1,
        cur_player=0,
    )
    legal = enumerate_legal_actions(ctx)
    raise_ids = {
        ACTION_RAISE_33,
        ACTION_RAISE_75,
        ACTION_RAISE_100,
        ACTION_RAISE_150,
        ACTION_RAISE_200,
    }
    assert not raise_ids.intersection(legal)
    assert ACTION_FOLD in legal
    assert ACTION_CALL in legal


def test_abstraction_bet_pot_fractions_compute_correctly():
    ctx = _ctx(pot=200, to_call=0)
    assert compute_bet_amount(ACTION_BET_75, ctx) == 150
    assert compute_bet_amount(ACTION_BET_100, ctx) == 200
    assert compute_bet_amount(ACTION_BET_150, ctx) == 300
    assert compute_bet_amount(ACTION_BET_200, ctx) == 400


def test_abstraction_raise_is_multiplier_of_bet_faced():
    # C2: raise-to = round(aggressor_contrib * multiplier) (PrevBetRelative).
    # Aggressor contributed 200; slot ACTION_RAISE_100 maps to the 3.0x size in
    # FIVE_RAISE_XS → round(200 * 3.0) = 600.
    ctx = _ctx(
        pot=300,
        to_call=100,
        contributions=(100, 200),
        street_num_raises=1,
        street_aggressor=1,
        cur_player=0,
        raise_size_xs=FIVE_RAISE_XS,
    )
    raise_to = compute_raise_to(ACTION_RAISE_100, ctx)
    assert raise_to == 600


def test_abstraction_min_bet_clamping():
    """Interpretation note: spec says pot=50, ACTION_BET_33 would compute 16
    cents but min_bet=100 cents; clamped to 100; dedup with other small
    fractions that also clamp. With pot=50: 33% = 16, 75% = 38, both clamp
    to 100 -> dedup to a single bet action."""
    ctx = _ctx(pot=50, to_call=0)
    legal = enumerate_legal_actions(ctx)
    bet_actions = [
        a
        for a in legal
        if a
        in {
            ACTION_BET_33,
            ACTION_BET_75,
            ACTION_BET_100,
            ACTION_BET_150,
            ACTION_BET_200,
        }
    ]
    amounts = {compute_bet_amount(a, ctx) for a in bet_actions}
    assert len(amounts) == len(bet_actions)
    assert all(amount >= 100 for amount in amounts)


def test_abstraction_all_in_replaces_oversize():
    ctx = _ctx(pot=200, to_call=0, stacks=(200, 200), cur_player=0)
    legal = enumerate_legal_actions(ctx)
    assert ACTION_BET_200 not in legal
    assert ACTION_ALL_IN in legal


def test_abstraction_all_in_dedup():
    ctx = _ctx(pot=200, to_call=0, stacks=(200, 200), cur_player=0)
    legal = enumerate_legal_actions(ctx)
    assert legal.count(ACTION_ALL_IN) == 1


def test_abstraction_force_allin_threshold_snaps_short():
    ctx = _ctx(
        pot=200,
        to_call=0,
        stacks=(150, 10_000),
        cur_player=0,
        force_allin_threshold_bb=1,
        big_blind=100,
    )
    legal = enumerate_legal_actions(ctx)
    assert ACTION_ALL_IN in legal


def test_abstraction_fold_unavailable_when_to_call_zero():
    ctx = _ctx(pot=200, to_call=0)
    legal = enumerate_legal_actions(ctx)
    assert ACTION_FOLD not in legal


def test_abstraction_check_unavailable_when_to_call_positive():
    ctx = _ctx(
        pot=300,
        to_call=100,
        contributions=(100, 200),
        street_num_raises=1,
        street_aggressor=1,
        cur_player=0,
    )
    legal = enumerate_legal_actions(ctx)
    assert ACTION_CHECK not in legal


def test_abstraction_returns_sorted_list():
    ctx = _ctx(pot=200, to_call=0)
    legal = enumerate_legal_actions(ctx)
    assert legal == sorted(legal)


# ---------------------------------------------------------------------------
# C1: per-street opening-bet menus.
# ---------------------------------------------------------------------------

# Production defaults (mirror HUNLConfig / action_abstraction module).
DEFAULT_FLOP = (0.33, 0.75, 1.25)
DEFAULT_TURN = (0.33, 0.75, 1.50)
DEFAULT_RIVER = (0.15, 0.33, 0.75, 1.50)


def test_per_street_flop_menu_bet_amounts():
    # IP (cur_player=0) so flop-no-donk does not fire. Pot 1000.
    ctx = _ctx(pot=1000, to_call=0, street=Street.FLOP, flop_bet_fractions=DEFAULT_FLOP)
    assert compute_bet_amount(ACTION_BET_33, ctx) == 330
    assert compute_bet_amount(ACTION_BET_75, ctx) == 750
    assert compute_bet_amount(ACTION_BET_100, ctx) == 1250  # slot 2 -> 1.25x


def test_per_street_turn_menu_bet_amounts():
    ctx = _ctx(pot=1000, to_call=0, street=Street.TURN, turn_bet_fractions=DEFAULT_TURN)
    assert compute_bet_amount(ACTION_BET_33, ctx) == 330
    assert compute_bet_amount(ACTION_BET_75, ctx) == 750
    assert compute_bet_amount(ACTION_BET_100, ctx) == 1500  # slot 2 -> 1.50x


def test_per_street_river_menu_bet_amounts():
    ctx = _ctx(
        pot=1000, to_call=0, street=Street.RIVER, river_bet_fractions=DEFAULT_RIVER
    )
    assert compute_bet_amount(ACTION_BET_33, ctx) == 150  # slot 0 -> 0.15x
    assert compute_bet_amount(ACTION_BET_75, ctx) == 330  # slot 1 -> 0.33x
    assert compute_bet_amount(ACTION_BET_100, ctx) == 750  # slot 2 -> 0.75x
    assert compute_bet_amount(ACTION_BET_150, ctx) == 1500  # slot 3 -> 1.50x


def test_per_street_menu_selects_by_street():
    # Same pot, different street -> different bet slot count + amounts.
    common = dict(
        pot=1000,
        to_call=0,
        flop_bet_fractions=DEFAULT_FLOP,
        turn_bet_fractions=DEFAULT_TURN,
        river_bet_fractions=DEFAULT_RIVER,
    )
    flop = enumerate_legal_actions(_ctx(street=Street.FLOP, **common))
    turn = enumerate_legal_actions(_ctx(street=Street.TURN, **common))
    river = enumerate_legal_actions(_ctx(street=Street.RIVER, **common))
    bet_ids = {
        ACTION_BET_33,
        ACTION_BET_75,
        ACTION_BET_100,
        ACTION_BET_150,
        ACTION_BET_200,
    }
    assert len(set(flop) & bet_ids) == 3
    assert len(set(turn) & bet_ids) == 3
    assert len(set(river) & bet_ids) == 4


def test_per_street_menu_falls_back_to_flat_when_none():
    # No per-street menu set -> flat bet_size_fractions (5 sizes) applies.
    ctx = _ctx(pot=1000, to_call=0, street=Street.FLOP, bet_size_fractions=DEFAULT_FRACTIONS)
    assert compute_bet_amount(ACTION_BET_33, ctx) == 330
    assert compute_bet_amount(ACTION_BET_200, ctx) == 2000


# ---------------------------------------------------------------------------
# C2: lean raise menu (multiplier-of-the-bet-faced).
# ---------------------------------------------------------------------------


def test_lean_raise_default_single_size():
    # Default raise menu is a single 3.0x size; only ACTION_RAISE_33 enumerates.
    ctx = _ctx(
        pot=300,
        to_call=100,
        contributions=(100, 200),
        street_num_raises=1,
        street_aggressor=1,
        cur_player=0,
    )
    legal = enumerate_legal_actions(ctx)
    raise_ids = {
        ACTION_RAISE_33,
        ACTION_RAISE_75,
        ACTION_RAISE_100,
        ACTION_RAISE_150,
        ACTION_RAISE_200,
    }
    present = set(legal) & raise_ids
    assert present == {ACTION_RAISE_33}
    # 3.0x of aggressor contribution (200) = 600.
    assert compute_raise_to(ACTION_RAISE_33, ctx) == 600
    assert ACTION_ALL_IN in legal


def test_lean_raise_respects_min_raise_floor():
    # A tiny multiplier would under-raise; clamp up to the min-raise floor.
    # Aggressor contributed 200; 1.01x = 202 < floor (200 + max(to_call, BB)).
    ctx = _ctx(
        pot=300,
        to_call=100,
        contributions=(100, 200),
        street_num_raises=1,
        street_aggressor=1,
        cur_player=0,
        big_blind=100,
        raise_size_xs=(1.01,),
    )
    floor = 200 + max(100, 100)  # aggressor_contrib + max(to_call, big_blind)
    assert compute_raise_to(ACTION_RAISE_33, ctx) == floor


def test_lean_raise_clamped_to_all_in_cap():
    # 3.0x of aggressor 200 = 600, but cur_player stack only allows raise_to up
    # to cur_contrib + stack = 100 + 300 = 400.
    ctx = _ctx(
        pot=300,
        to_call=100,
        contributions=(100, 200),
        stacks=(300, 10_000),
        street_num_raises=1,
        street_aggressor=1,
        cur_player=0,
    )
    assert compute_raise_to(ACTION_RAISE_33, ctx) == 400


# ---------------------------------------------------------------------------
# C3: flop-no-donk.
# ---------------------------------------------------------------------------


def test_flop_no_donk_removes_oop_flop_open():
    # OOP (P1) first-to-act on the flop: only CHECK, no bets, no all-in.
    ctx = _ctx(
        pot=1000,
        to_call=0,
        cur_player=1,
        street=Street.FLOP,
        street_aggressor=-1,
        street_action_count=0,
        flop_bet_fractions=DEFAULT_FLOP,
    )
    legal = enumerate_legal_actions(ctx)
    assert legal == [ACTION_CHECK]


def test_flop_no_donk_allows_ip_flop_open():
    # IP (P0) flop open is unaffected.
    ctx = _ctx(
        pot=1000,
        to_call=0,
        cur_player=0,
        street=Street.FLOP,
        street_aggressor=-1,
        street_action_count=0,
        flop_bet_fractions=DEFAULT_FLOP,
    )
    legal = enumerate_legal_actions(ctx)
    bet_ids = {ACTION_BET_33, ACTION_BET_75, ACTION_BET_100}
    assert bet_ids.issubset(set(legal))
    assert ACTION_ALL_IN in legal


def test_flop_no_donk_does_not_block_oop_after_check():
    # After a prior flop action (e.g. OOP checked, IP to act, IP checks back is
    # terminal; but if OOP faces a later in-street decision the count > 0),
    # the donk constraint no longer applies.
    ctx = _ctx(
        pot=1000,
        to_call=0,
        cur_player=1,
        street=Street.FLOP,
        street_aggressor=-1,
        street_action_count=1,
        flop_bet_fractions=DEFAULT_FLOP,
    )
    legal = enumerate_legal_actions(ctx)
    assert ACTION_BET_33 in legal


def test_flop_no_donk_does_not_affect_turn_or_river_oop_open():
    for street, menu_kw in (
        (Street.TURN, {"turn_bet_fractions": DEFAULT_TURN}),
        (Street.RIVER, {"river_bet_fractions": DEFAULT_RIVER}),
    ):
        ctx = _ctx(
            pot=1000,
            to_call=0,
            cur_player=1,
            street=street,
            street_aggressor=-1,
            street_action_count=0,
            **menu_kw,
        )
        legal = enumerate_legal_actions(ctx)
        assert ACTION_BET_33 in legal, f"{street} OOP open should expose bets"
        assert ACTION_ALL_IN in legal


def test_flop_no_donk_does_not_affect_oop_facing_bet():
    # OOP facing a bet on the flop can still raise (not a donk/open node).
    ctx = _ctx(
        pot=1000,
        to_call=300,
        contributions=(300, 0),
        cur_player=1,
        street=Street.FLOP,
        street_num_raises=1,
        street_aggressor=0,
        street_action_count=1,
        raise_size_xs=(3.0,),
    )
    legal = enumerate_legal_actions(ctx)
    assert ACTION_FOLD in legal
    assert ACTION_CALL in legal
    assert ACTION_RAISE_33 in legal
