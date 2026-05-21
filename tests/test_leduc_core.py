from __future__ import annotations

import pytest

from poker_solver import LEDUC_CALL, LEDUC_FOLD, LEDUC_RAISE, LeducPoker


def _deal(game: LeducPoker, p0_card: int, p1_card: int):
    s = game.initial_state()
    s = game.apply(s, p0_card)
    s = game.apply(s, p1_card)
    return s


def _deal_with_public(game: LeducPoker, p0_card: int, p1_card: int, public: int):
    s = _deal(game, p0_card, p1_card)
    s = game.apply(s, LEDUC_CALL)
    s = game.apply(s, LEDUC_CALL)
    return game.apply(s, public)


def test_leduc_initial_state():
    game = LeducPoker()
    s = game.initial_state()
    assert s.pot == 2
    assert s.public_card is None
    assert s.round1_history == ()
    assert s.round2_history == ()
    assert s.ante == (1, 1)
    assert game.current_player(s) == -1
    assert not game.is_terminal(s)


def test_leduc_chance_deals_private_cards():
    game = LeducPoker()
    s = game.initial_state()
    outcomes = game.chance_outcomes(s)
    assert len(outcomes) == 6
    assert sum(p for _, p in outcomes) == pytest.approx(1.0)
    for _, p in outcomes:
        assert p == pytest.approx(1.0 / 6.0)
    s = game.apply(s, 11)
    assert game.current_player(s) == -1
    second = game.chance_outcomes(s)
    assert len(second) == 5
    assert sum(p for _, p in second) == pytest.approx(1.0)


def test_leduc_first_player_to_act_is_p0():
    game = LeducPoker()
    s = _deal(game, 11, 12)
    assert game.current_player(s) == 0
    assert game.legal_actions(s) == [LEDUC_CALL, LEDUC_RAISE]


def test_leduc_both_check_preflop_is_not_terminal():
    game = LeducPoker()
    s = _deal(game, 11, 12)
    s = game.apply(s, LEDUC_CALL)
    s = game.apply(s, LEDUC_CALL)
    assert not game.is_terminal(s)
    assert game.current_player(s) == -1
    assert len(game.chance_outcomes(s)) == 4


def test_leduc_fold_ends_hand():
    game = LeducPoker()
    s = _deal(game, 11, 13)
    s = game.apply(s, LEDUC_RAISE)
    s = game.apply(s, LEDUC_FOLD)
    assert game.is_terminal(s)
    assert game.utility(s) == (1.0, -1.0)


def test_leduc_showdown_pair_wins():
    game = LeducPoker()
    s = _deal_with_public(game, 13, 11, 13)
    s = game.apply(s, LEDUC_CALL)
    s = game.apply(s, LEDUC_CALL)
    assert game.is_terminal(s)
    assert game.utility(s) == (1.0, -1.0)


def test_leduc_showdown_pair_beats_higher_high_card():
    game = LeducPoker()
    s = _deal_with_public(game, 11, 13, 11)
    s = game.apply(s, LEDUC_CALL)
    s = game.apply(s, LEDUC_CALL)
    assert game.utility(s) == (1.0, -1.0)


def test_leduc_showdown_high_card_wins():
    game = LeducPoker()
    s = _deal_with_public(game, 11, 13, 12)
    s = game.apply(s, LEDUC_CALL)
    s = game.apply(s, LEDUC_CALL)
    assert game.utility(s) == (-1.0, 1.0)


def test_leduc_showdown_tie_returns_zero():
    game = LeducPoker()
    s = _deal_with_public(game, 12, 12, 13)
    s = game.apply(s, LEDUC_CALL)
    s = game.apply(s, LEDUC_CALL)
    assert game.utility(s) == (0.0, 0.0)


def test_leduc_max_raises_per_round():
    game = LeducPoker()
    s = _deal(game, 11, 12)
    s = game.apply(s, LEDUC_RAISE)
    s = game.apply(s, LEDUC_RAISE)
    assert s.num_raises == 2
    assert LEDUC_RAISE not in game.legal_actions(s)
    assert set(game.legal_actions(s)) == {LEDUC_FOLD, LEDUC_CALL}


def test_leduc_pot_arithmetic_through_a_hand():
    game = LeducPoker()
    s = _deal(game, 11, 13)
    assert s.pot == 2
    s = game.apply(s, LEDUC_RAISE)
    assert s.pot == 4
    assert s.ante == (3, 1)
    s = game.apply(s, LEDUC_RAISE)
    assert s.pot == 8
    assert s.ante == (3, 5)
    s = game.apply(s, LEDUC_CALL)
    assert s.pot == 10
    assert s.ante == (5, 5)
    s = game.apply(s, 12)
    assert s.round_num == 2
    assert s.public_card == 12
    s = game.apply(s, LEDUC_RAISE)
    assert s.ante == (9, 5)
    assert s.pot == 14
    s = game.apply(s, LEDUC_CALL)
    assert s.ante == (9, 9)
    assert game.is_terminal(s)
    assert game.utility(s) == (-9.0, 9.0)


def test_leduc_round2_uses_larger_bet_size():
    game = LeducPoker()
    s = _deal_with_public(game, 11, 13, 12)
    s = game.apply(s, LEDUC_RAISE)
    assert s.ante == (5, 1)
    s = game.apply(s, LEDUC_RAISE)
    assert s.ante == (5, 9)
    assert s.num_raises == 2


def test_leduc_fold_only_when_facing_a_bet():
    game = LeducPoker()
    s = _deal(game, 11, 12)
    assert LEDUC_FOLD not in game.legal_actions(s)
    s = game.apply(s, LEDUC_RAISE)
    assert LEDUC_FOLD in game.legal_actions(s)


def test_leduc_infoset_key_distinguishes_rounds():
    game = LeducPoker()
    pre = _deal(game, 11, 12)
    assert game.infoset_key(pre, 0) == "11|"
    post = _deal_with_public(game, 11, 12, 13)
    assert game.infoset_key(post, 0) == "11|cc|13|"
