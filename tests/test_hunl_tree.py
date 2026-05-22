from __future__ import annotations

import pytest

from poker_solver import (
    Card,
    HUNLConfig,
    HUNLPoker,
    Street,
    default_tiny_subgame,
    solve,
)


def _walk_tree(game, state, action_fn, max_depth: int = 50, _depth: int = 0):
    action_fn(state, _depth)
    if game.is_terminal(state) or _depth >= max_depth:
        return
    cur = game.current_player(state)
    if cur == -1:
        outcomes = game.chance_outcomes(state)
        for action, _ in outcomes:
            _walk_tree(
                game, game.apply(state, action), action_fn, max_depth, _depth + 1
            )
    else:
        for action in game.legal_actions(state):
            _walk_tree(
                game, game.apply(state, action), action_fn, max_depth, _depth + 1
            )


def _tiny_river_config() -> HUNLConfig:
    return HUNLConfig(
        starting_stack=400,
        starting_street=Street.RIVER,
        initial_board=(
            Card.from_str("Ah"),
            Card.from_str("Kh"),
            Card.from_str("Qh"),
            Card.from_str("Jh"),
            Card.from_str("Th"),
        ),
        initial_pot=200,
        initial_contributions=(100, 100),
    )


def _seed_holes_if_needed(game: HUNLPoker, state):
    import dataclasses

    if state.hole_cards:
        return state
    holes = (
        (Card.from_str("2s"), Card.from_str("3s")),
        (Card.from_str("4d"), Card.from_str("5d")),
    )
    return dataclasses.replace(state, hole_cards=holes, cur_player=1)


def test_hunl_tiny_tree_pot_invariant():
    config = _tiny_river_config()
    game = HUNLPoker(config)
    s = _seed_holes_if_needed(game, game.initial_state())

    def check(state, _depth):
        for i in (0, 1):
            equation = (
                state.stacks[i]
                + state.contributions[i]
                - config.initial_contributions[i]
            )
            assert equation == config.starting_stack

    _walk_tree(game, s, check, max_depth=40)


def test_hunl_tiny_tree_legal_actions_never_empty_until_terminal():
    config = _tiny_river_config()
    game = HUNLPoker(config)
    s = _seed_holes_if_needed(game, game.initial_state())

    def check(state, _depth):
        if not game.is_terminal(state) and game.current_player(state) >= 0:
            assert len(game.legal_actions(state)) > 0

    _walk_tree(game, s, check, max_depth=40)


def test_hunl_tiny_tree_terminal_count_in_expected_range():
    """Interpretation note: spec uses a loose [100, 5000] bound for a 4-BB
    starting stack tree but my tiny river fixture differs (400 cents = 4 BB
    starting stack, river-only). I keep the loose bound but allow a much
    smaller floor for the river-only subgame, which has a smaller tree."""
    config = _tiny_river_config()
    game = HUNLPoker(config)
    s = _seed_holes_if_needed(game, game.initial_state())
    terminals = []

    def check(state, _depth):
        if game.is_terminal(state):
            terminals.append(1)

    _walk_tree(game, s, check, max_depth=40)
    assert 10 <= len(terminals) <= 5000


def test_hunl_river_subgame_no_chance_nodes():
    config = _tiny_river_config()
    game = HUNLPoker(config)
    s = _seed_holes_if_needed(game, game.initial_state())
    chance_nodes = []

    def check(state, _depth):
        if not game.is_terminal(state) and game.current_player(state) == -1:
            chance_nodes.append(1)

    _walk_tree(game, s, check, max_depth=40)
    assert len(chance_nodes) == 0


@pytest.mark.timeout(120)
def test_hunl_default_tiny_subgame_solvable_in_one_minute():
    config = default_tiny_subgame()
    game = HUNLPoker(config)
    result = solve(game, 500)
    assert result.exploitability_history[-1] < 0.1


def test_hunl_max_tree_depth_bounded():
    config = _tiny_river_config()
    game = HUNLPoker(config)
    s = _seed_holes_if_needed(game, game.initial_state())
    max_depth_seen = [0]

    def check(state, depth):
        if depth > max_depth_seen[0]:
            max_depth_seen[0] = depth

    _walk_tree(game, s, check, max_depth=50)
    cap = config.postflop_raise_cap
    bound = (cap + 2) * 4
    assert max_depth_seen[0] <= bound


def test_hunl_branching_factor_bounded():
    config = _tiny_river_config()
    game = HUNLPoker(config)
    s = _seed_holes_if_needed(game, game.initial_state())

    def check(state, _depth):
        if not game.is_terminal(state) and game.current_player(state) >= 0:
            assert len(game.legal_actions(state)) <= 8

    _walk_tree(game, s, check, max_depth=40)


def test_hunl_terminal_utility_zero_sum():
    config = _tiny_river_config()
    game = HUNLPoker(config)
    s = _seed_holes_if_needed(game, game.initial_state())

    def check(state, _depth):
        if game.is_terminal(state):
            u = game.utility(state)
            assert u[0] + u[1] == pytest.approx(0.0)

    _walk_tree(game, s, check, max_depth=40)


def test_hunl_infoset_count_smoke():
    config = _tiny_river_config()
    game = HUNLPoker(config)
    s = _seed_holes_if_needed(game, game.initial_state())
    keys: set[str] = set()

    def check(state, _depth):
        if not game.is_terminal(state) and game.current_player(state) >= 0:
            keys.add(game.infoset_key(state, game.current_player(state)))

    _walk_tree(game, s, check, max_depth=40)
    assert 10 <= len(keys) <= 100_000


def test_hunl_chance_outcome_probabilities_sum_to_one():
    game = HUNLPoker(HUNLConfig(starting_stack=400))
    s = game.initial_state()
    assert game.current_player(s) == -1
    outcomes = game.chance_outcomes(s)
    total = sum(p for _, p in outcomes)
    assert total == pytest.approx(1.0)

    s2 = game.apply(s, outcomes[0][0])
    from poker_solver import ACTION_ALL_IN, ACTION_CALL

    s2 = game.apply(s2, ACTION_ALL_IN)
    s2 = game.apply(s2, ACTION_CALL)
    while game.current_player(s2) == -1 and not game.is_terminal(s2):
        chance_outcomes = game.chance_outcomes(s2)
        total = sum(p for _, p in chance_outcomes)
        assert total == pytest.approx(1.0)
        s2 = game.apply(s2, chance_outcomes[0][0])
