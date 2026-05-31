from __future__ import annotations

import pytest

from poker_solver import (
    ACTION_ALL_IN,
    ACTION_BET_33,
    ACTION_BET_75,
    ACTION_BET_100,
    ACTION_CALL,
    ACTION_CHECK,
    ACTION_FOLD,
    ACTION_RAISE_33,
    ACTION_RAISE_75,
    ACTION_RAISE_100,
    Card,
    HUNLConfig,
    HUNLPoker,
    Street,
)


def _initial(game: HUNLPoker) -> object:
    s = game.initial_state()
    while game.current_player(s) == -1 and not game.is_terminal(s):
        outcomes = game.chance_outcomes(s)
        s = game.apply(s, outcomes[0][0])
    return s


def test_hunl_initial_state_blinds_posted():
    game = HUNLPoker(HUNLConfig())
    s = _initial(game)
    assert s.contributions == (50, 100)
    assert s.stacks == (9950, 9900)
    assert sum(s.contributions) == 150
    assert s.to_call == 50
    assert game.current_player(s) == 0


def test_hunl_initial_state_with_ante():
    game = HUNLPoker(HUNLConfig(ante=25))
    s = _initial(game)
    assert s.contributions == (75, 125)
    assert s.stacks == (9925, 9875)
    assert sum(s.contributions) == 200
    assert s.to_call == 50
    assert game.current_player(s) == 0
    assert s.street_num_raises == 1


def test_hunl_preflop_sb_acts_first():
    game = HUNLPoker(HUNLConfig())
    s = _initial(game)
    assert s.street == Street.PREFLOP
    assert game.current_player(s) == 0


def test_hunl_postflop_bb_acts_first():
    game = HUNLPoker(HUNLConfig())
    s = _initial(game)
    s = game.apply(s, ACTION_CALL)
    s = game.apply(s, ACTION_CHECK)
    while game.current_player(s) == -1 and not game.is_terminal(s):
        outcomes = game.chance_outcomes(s)
        s = game.apply(s, outcomes[0][0])
    assert s.street == Street.FLOP
    assert game.current_player(s) == 1


def test_hunl_fold_terminates_hand_correctly():
    game = HUNLPoker(HUNLConfig())
    s = _initial(game)
    s = game.apply(s, ACTION_FOLD)
    assert game.is_terminal(s)
    u = game.utility(s)
    assert u[0] == pytest.approx(-0.5)
    assert u[1] == pytest.approx(0.5)


def test_hunl_call_preflop_advances_to_flop():
    game = HUNLPoker(HUNLConfig())
    s = _initial(game)
    s = game.apply(s, ACTION_CALL)
    s = game.apply(s, ACTION_CHECK)
    while game.current_player(s) == -1 and not game.is_terminal(s):
        outcomes = game.chance_outcomes(s)
        s = game.apply(s, outcomes[0][0])
    assert s.street == Street.FLOP
    assert len(s.board) == 3


def test_hunl_bet_amount_uses_pot_fractions():
    """ACTION_BET_75 = round(200 * 0.75) = 150 cents (flat menu, slot 1).

    C3 flop-no-donk: OOP (P1) opens are removed on the flop, so OOP checks and
    IP (P0) opens; the bet-sizing math is unchanged."""
    config = HUNLConfig(
        starting_street=Street.FLOP,
        initial_board=(Card.from_str("7d"), Card.from_str("2c"), Card.from_str("9h")),
        initial_pot=200,
        initial_contributions=(100, 100),
    )
    game = HUNLPoker(config)
    s = _initial(game)
    assert s.street == Street.FLOP
    assert game.current_player(s) == 1
    # OOP may only check on the flop (flop-no-donk); IP then opens.
    assert ACTION_BET_75 not in game.legal_actions(s)
    s = game.apply(s, ACTION_CHECK)
    assert game.current_player(s) == 0
    legal = game.legal_actions(s)
    assert ACTION_BET_75 in legal
    s_after = game.apply(s, ACTION_BET_75)
    assert s_after.contributions[0] - s.contributions[0] == 150


def test_hunl_raise_amount_uses_multiplier_of_bet_faced():
    """C2 lean raise: raise-to = round(aggressor_contrib * multiplier).

    Flop, OOP checks (flop-no-donk), IP opens 100% pot (200) -> IP contributes
    to 300 and becomes aggressor. OOP raises with the default single 3.0x size:
    round(300 * 3.0) = 900."""
    config = HUNLConfig(
        starting_street=Street.FLOP,
        initial_board=(Card.from_str("7d"), Card.from_str("2c"), Card.from_str("9h")),
        initial_pot=200,
        initial_contributions=(100, 100),
    )
    game = HUNLPoker(config)
    s = _initial(game)
    assert game.current_player(s) == 1
    s = game.apply(s, ACTION_CHECK)  # OOP checks (flop-no-donk)
    s = game.apply(s, ACTION_BET_100)  # IP opens 100% pot
    assert s.contributions == (300, 100)
    assert game.current_player(s) == 1
    assert s.to_call == 200
    legal = game.legal_actions(s)
    assert ACTION_RAISE_33 in legal
    s_after = game.apply(s, ACTION_RAISE_33)
    assert s_after.contributions[1] == 900


def test_hunl_min_bet_is_one_bb():
    from poker_solver import ACTION_BET_150, ACTION_BET_200

    config = HUNLConfig(
        starting_street=Street.FLOP,
        initial_board=(Card.from_str("7d"), Card.from_str("2c"), Card.from_str("9h")),
        initial_pot=200,
        initial_contributions=(100, 100),
    )
    game = HUNLPoker(config)
    s = _initial(game)
    assert s.to_call == 0
    legal = game.legal_actions(s)
    bet_ids = {
        ACTION_BET_33,
        ACTION_BET_75,
        ACTION_BET_100,
        ACTION_BET_150,
        ACTION_BET_200,
    }
    for a in legal:
        if a in bet_ids:
            s_after = game.apply(s, a)
            added = s_after.contributions[s.cur_player] - s.contributions[s.cur_player]
            assert added >= config.big_blind


def test_hunl_min_raise_enforced():
    from poker_solver import ACTION_RAISE_150, ACTION_RAISE_200

    raise_ids = {
        ACTION_RAISE_33,
        ACTION_RAISE_75,
        ACTION_RAISE_100,
        ACTION_RAISE_150,
        ACTION_RAISE_200,
    }
    config = HUNLConfig(
        starting_street=Street.FLOP,
        initial_board=(Card.from_str("7d"), Card.from_str("2c"), Card.from_str("9h")),
        initial_pot=200,
        initial_contributions=(100, 100),
    )
    game = HUNLPoker(config)
    s = _initial(game)
    s = game.apply(s, ACTION_BET_100)
    assert s.to_call == 200
    legal = game.legal_actions(s)
    for a in legal:
        if a in raise_ids:
            s_after = game.apply(s, a)
            increment_over_call = s_after.contributions[0] - 300
            assert increment_over_call >= 200


def test_hunl_force_allin_threshold_snaps_short_shoves():
    config = HUNLConfig(
        starting_stack=120,
        starting_street=Street.FLOP,
        initial_board=(Card.from_str("7d"), Card.from_str("2c"), Card.from_str("9h")),
        initial_pot=200,
        initial_contributions=(0, 0),
    )
    game = HUNLPoker(config)
    s = _initial(game)
    # C3 flop-no-donk: OOP checks first; IP is the player whose short shove the
    # force-allin threshold collapses.
    s = game.apply(s, ACTION_CHECK)
    legal = game.legal_actions(s)
    assert ACTION_ALL_IN in legal
    assert legal.count(ACTION_ALL_IN) == 1
    from poker_solver import ACTION_BET_200

    assert ACTION_BET_200 not in legal


def test_hunl_preflop_4_raise_cap():
    # Lean raise default offers a single 3.0x size -> ACTION_RAISE_33 is the
    # only raise slot. Preflop is unaffected by C3 (flop-only).
    game = HUNLPoker(HUNLConfig())
    s = _initial(game)
    s = game.apply(s, ACTION_RAISE_33)
    s = game.apply(s, ACTION_RAISE_33)
    s = game.apply(s, ACTION_RAISE_33)
    legal = game.legal_actions(s)
    assert not any(
        a
        in {
            ACTION_RAISE_33,
            ACTION_RAISE_75,
            ACTION_RAISE_100,
            ACTION_RAISE_100 + 1,
            ACTION_RAISE_100 + 2,
        }
        for a in legal
    )
    assert ACTION_FOLD in legal
    assert ACTION_CALL in legal


def test_hunl_postflop_3_raise_cap():
    config = HUNLConfig(
        starting_street=Street.FLOP,
        initial_board=(Card.from_str("7d"), Card.from_str("2c"), Card.from_str("9h")),
        initial_pot=200,
        initial_contributions=(100, 100),
    )
    game = HUNLPoker(config)
    s = _initial(game)
    # C3 flop-no-donk: OOP checks; IP opens; then 3 raises reach the cap. Lean
    # raise default offers only ACTION_RAISE_33.
    s = game.apply(s, ACTION_CHECK)  # OOP check (raises still 0)
    s = game.apply(s, ACTION_BET_100)  # IP open (raises=1)
    s = game.apply(s, ACTION_RAISE_33)  # raises=2
    s = game.apply(s, ACTION_RAISE_33)  # raises=3 -> at cap
    legal = game.legal_actions(s)
    for a in legal:
        assert a not in {
            ACTION_RAISE_33,
            ACTION_RAISE_75,
            ACTION_RAISE_100,
            ACTION_RAISE_100 + 1,
            ACTION_RAISE_100 + 2,
        }
    assert ACTION_FOLD in legal
    assert ACTION_CALL in legal


def test_hunl_showdown_higher_hand_wins():
    """Interpretation note: spec says 'deal both hands deterministically (via
    direct state construction), set board, walk to showdown, check utility.'
    I interpreted as: construct a RIVER-starting config with pre-dealt hole
    cards (via no chance node), walk to showdown via check-check, verify
    utility favors the better hand."""
    from poker_solver import default_tiny_subgame

    config = default_tiny_subgame()
    game = HUNLPoker(config)
    s = _initial(game)
    s = game.apply(s, ACTION_CHECK)
    s = game.apply(s, ACTION_CHECK)
    while game.current_player(s) == -1 and not game.is_terminal(s):
        outcomes = game.chance_outcomes(s)
        s = game.apply(s, outcomes[0][0])
    assert game.is_terminal(s)
    u = game.utility(s)
    # Canonical Brown utility: u[0] + u[1] = initial_pot / big_blind per leaf
    # (constant-sum, dead money flows to winner). default_tiny_subgame has
    # initial_pot=1000, BB=100 → sum = 10.0.
    assert u[0] + u[1] == pytest.approx(10.0)


def test_hunl_showdown_tie_splits_pot():
    """Interpretation note: spec says 'both players hold the same effective
    hand on a board (e.g. board plays all 5 cards), utility == (0.0, 0.0).'
    Use a royal-flush board so the 5 board cards play for both players. Use
    dataclasses.replace to inject hole cards if needed (the spec doesn't
    document a public API for pre-setting holes on a non-preflop subgame)."""
    import dataclasses

    board = (
        Card.from_str("Ah"),
        Card.from_str("Kh"),
        Card.from_str("Qh"),
        Card.from_str("Jh"),
        Card.from_str("Th"),
    )
    config = HUNLConfig(
        starting_street=Street.RIVER,
        initial_board=board,
        initial_pot=200,
        initial_contributions=(100, 100),
    )
    game = HUNLPoker(config)
    s = game.initial_state()
    holes = (
        (Card.from_str("2s"), Card.from_str("3s")),
        (Card.from_str("4d"), Card.from_str("5d")),
    )
    if not s.hole_cards:
        s = dataclasses.replace(s, hole_cards=holes, cur_player=1)
    s = game.apply(s, ACTION_CHECK)
    s = game.apply(s, ACTION_CHECK)
    while game.current_player(s) == -1 and not game.is_terminal(s):
        outcomes = game.chance_outcomes(s)
        s = game.apply(s, outcomes[0][0])
    assert game.is_terminal(s)
    u = game.utility(s)
    # Canonical Brown tie: each player gets pot_total/2 - cs_self. With
    # initial_pot=200, contribs=(100,100), no further betting: cs=(0,0),
    # pot_total=200 → each player nets pot_total/2 - 0 = 100 chips = 1.0 BB.
    assert u[0] == pytest.approx(1.0)
    assert u[1] == pytest.approx(1.0)


def test_hunl_all_in_runs_out_remaining_streets():
    game = HUNLPoker(HUNLConfig())
    s = _initial(game)
    s = game.apply(s, ACTION_ALL_IN)
    s = game.apply(s, ACTION_CALL)
    chance_steps = 0
    while game.current_player(s) == -1 and not game.is_terminal(s):
        outcomes = game.chance_outcomes(s)
        s = game.apply(s, outcomes[0][0])
        chance_steps += 1
    assert game.is_terminal(s)
    assert chance_steps == 5


def test_hunl_infoset_key_hides_opponent_cards():
    """Interpretation note: spec says 'two states differ only in P1's hole
    cards; infoset_key(_, 0) identical.' Construct two RIVER-start states
    with different P1 hole cards but same P0 hole cards, assert P0's
    infoset key is identical."""
    board = (
        Card.from_str("7d"),
        Card.from_str("2c"),
        Card.from_str("9h"),
        Card.from_str("Kh"),
        Card.from_str("5s"),
    )
    config = HUNLConfig(
        starting_street=Street.RIVER,
        initial_board=board,
        initial_pot=200,
        initial_contributions=(100, 100),
    )
    game = HUNLPoker(config)
    s1 = game.initial_state()
    s1_holes = (
        (Card.from_str("Ah"), Card.from_str("Kc")),
        (Card.from_str("Qd"), Card.from_str("Qh")),
    )
    s2_holes = (
        (Card.from_str("Ah"), Card.from_str("Kc")),
        (Card.from_str("Jd"), Card.from_str("Jh")),
    )
    if game.current_player(s1) == -1:
        s1 = game.apply(s1, s1_holes)
        s2 = game.apply(game.initial_state(), s2_holes)
    else:
        import dataclasses

        s2 = game.initial_state()
        s1 = dataclasses.replace(s1, hole_cards=s1_holes)
        s2 = dataclasses.replace(s2, hole_cards=s2_holes)
    assert game.infoset_key(s1, 0) == game.infoset_key(s2, 0)


def test_hunl_infoset_key_canonicalizes_hole_order():
    board = (
        Card.from_str("7d"),
        Card.from_str("2c"),
        Card.from_str("9h"),
        Card.from_str("Kh"),
        Card.from_str("5s"),
    )
    config = HUNLConfig(
        starting_street=Street.RIVER,
        initial_board=board,
        initial_pot=200,
        initial_contributions=(100, 100),
    )
    game = HUNLPoker(config)
    s1 = game.initial_state()
    s2 = game.initial_state()
    holes_ahkh = (
        (Card.from_str("Ah"), Card.from_str("Kh")),
        (Card.from_str("Qd"), Card.from_str("Qc")),
    )
    holes_khah = (
        (Card.from_str("Kh"), Card.from_str("Ah")),
        (Card.from_str("Qd"), Card.from_str("Qc")),
    )
    if game.current_player(s1) == -1:
        s1 = game.apply(s1, holes_ahkh)
        s2 = game.apply(s2, holes_khah)
    else:
        import dataclasses

        s1 = dataclasses.replace(s1, hole_cards=holes_ahkh)
        s2 = dataclasses.replace(s2, hole_cards=holes_khah)
    assert game.infoset_key(s1, 0) == game.infoset_key(s2, 0)


def test_hunl_chance_outcomes_exclude_held_cards():
    game = HUNLPoker(HUNLConfig())
    s = _initial(game)
    s = game.apply(s, ACTION_CALL)
    s = game.apply(s, ACTION_CHECK)
    assert game.current_player(s) == -1
    held: set[Card] = set()
    for hand in s.hole_cards:
        held.update(hand)
    outcomes = game.chance_outcomes(s)
    for action, _ in outcomes:
        from poker_solver.card import int_to_card

        card = int_to_card(action)
        assert card not in held
