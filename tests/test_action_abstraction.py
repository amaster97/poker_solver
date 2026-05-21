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
    preflop_raise_cap: int = 4,
    postflop_raise_cap: int = 3,
    force_allin_threshold_bb: int = 1,
    min_bet_bb: int = 1,
    include_all_in: bool = True,
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
        preflop_raise_cap=preflop_raise_cap,
        postflop_raise_cap=postflop_raise_cap,
        force_allin_threshold_bb=force_allin_threshold_bb,
        min_bet_bb=min_bet_bb,
        include_all_in=include_all_in,
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
    ctx = _ctx(
        pot=300,
        to_call=100,
        contributions=(100, 200),
        street_num_raises=1,
        street_aggressor=1,
        cur_player=0,
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


def test_abstraction_raise_uses_pot_after_call():
    ctx = _ctx(
        pot=300,
        to_call=100,
        contributions=(100, 200),
        street_num_raises=1,
        street_aggressor=1,
        cur_player=0,
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
