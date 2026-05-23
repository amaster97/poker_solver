"""PR 22 — asymmetric initial-contributions support for facing-bet subgames.

Covers `HUNLPoker.initial_state` and `HUNLConfig.__post_init__` per
`docs/pr_proposals/v1_4_asymmetric_contributions.md`.

Fix A (logic): honor `initial_contributions` asymmetry so facing-bet
subgames (W3.4 MDF, W2.3 c-bet response, W1.2 bluff-catcher) compose.

Fix B (validation): raise `ValueError` on negative / out-of-stack
contributions rather than letting the Rust backend segfault.

Symmetric `(c, c)` baseline is locked unchanged as a regression guard.
"""

from __future__ import annotations

import pytest

from poker_solver import (
    ACTION_CHECK,
    ACTION_FOLD,
    Card,
    HUNLConfig,
    HUNLPoker,
    Street,
)


def _flop_board() -> tuple[Card, ...]:
    return (
        Card.from_str("Qd"),
        Card.from_str("7c"),
        Card.from_str("2h"),
    )


def _flop_hole() -> tuple[tuple[Card, Card], tuple[Card, Card]]:
    return (
        (Card.from_str("Kh"), Card.from_str("Kc")),
        (Card.from_str("As"), Card.from_str("Ad")),
    )


# ---------------------------------------------------------------------------
# Fix A — symmetric baseline (regression guard)
# ---------------------------------------------------------------------------


def test_symmetric_contributions_to_call_is_zero():
    """`(500, 500)` continues to yield `to_call=0`, `cur_player=1`,
    `street_aggressor=-1`, `street_num_raises=0`. Locks v1.4.0 behavior."""
    cfg = HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.FLOP,
        initial_board=_flop_board(),
        initial_pot=1000,
        initial_contributions=(500, 500),
        initial_hole_cards=_flop_hole(),
    )
    game = HUNLPoker(cfg)
    s = game.initial_state()
    assert s.to_call == 0
    assert s.cur_player == 1
    assert s.street_aggressor == -1
    assert s.street_num_raises == 0
    assert s.contributions == (500, 500)
    assert s.stacks == (10_000, 10_000)


def test_symmetric_dead_money_to_call_is_zero():
    """`(0, 0)` dead-money subgames stay symmetric — pot exists but neither
    player is on the hook for fold-loss accounting."""
    cfg = HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.FLOP,
        initial_board=_flop_board(),
        initial_pot=1000,
        initial_contributions=(0, 0),
        initial_hole_cards=_flop_hole(),
    )
    game = HUNLPoker(cfg)
    s = game.initial_state()
    assert s.to_call == 0
    assert s.cur_player == 1
    assert s.street_aggressor == -1
    assert s.street_num_raises == 0


# ---------------------------------------------------------------------------
# Fix A — asymmetric contributions
# ---------------------------------------------------------------------------


def test_asymmetric_p1_faces_bet():
    """`(1000, 500)`: P1 (BB) put in less → P1 faces a bet of 500, P0 (SB)
    is the aggressor. This is the W3.4 / W2.3 / W1.2 unlocked path."""
    cfg = HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.FLOP,
        initial_board=_flop_board(),
        initial_pot=1500,
        initial_contributions=(1000, 500),
        initial_hole_cards=_flop_hole(),
    )
    game = HUNLPoker(cfg)
    s = game.initial_state()
    assert s.to_call == 500
    assert s.cur_player == 1
    assert s.street_aggressor == 0
    assert s.street_num_raises == 1
    assert s.contributions == (1000, 500)
    assert s.stacks == (10_000, 10_000)


def test_asymmetric_p0_faces_bet():
    """`(500, 1000)`: P0 (SB) put in less → P0 faces a bet of 500, P1 (BB)
    is the aggressor. Probe-bet / 3-bet pot scenario."""
    cfg = HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.FLOP,
        initial_board=_flop_board(),
        initial_pot=1500,
        initial_contributions=(500, 1000),
        initial_hole_cards=_flop_hole(),
    )
    game = HUNLPoker(cfg)
    s = game.initial_state()
    assert s.to_call == 500
    assert s.cur_player == 0
    assert s.street_aggressor == 1
    assert s.street_num_raises == 1
    assert s.contributions == (500, 1000)


def test_asymmetric_facing_bet_river():
    """W1.2 (Marcus) — river bluff-catcher MDF. Pot 200, villain bets 200
    (pot-sized); hero faces a 200 c-bet on the river."""
    board = (
        Card.from_str("As"),
        Card.from_str("Tc"),
        Card.from_str("5d"),
        Card.from_str("Jh"),
        Card.from_str("8s"),
    )
    hole = (
        (Card.from_str("Jc"), Card.from_str("Jd")),
        (Card.from_str("Kh"), Card.from_str("Kd")),
    )
    cfg = HUNLConfig(
        starting_stack=1000,
        starting_street=Street.RIVER,
        initial_board=board,
        initial_pot=600,
        initial_contributions=(200, 400),
        initial_hole_cards=hole,
    )
    game = HUNLPoker(cfg)
    s = game.initial_state()
    assert s.to_call == 200
    assert s.cur_player == 0
    assert s.street_aggressor == 1


# ---------------------------------------------------------------------------
# Fix A — legal-action surface on the facing-bet state
# ---------------------------------------------------------------------------


def test_asymmetric_facing_bet_offers_fold_call():
    """When `to_call > 0`, the action surface for the facing-bet player must
    include fold + call (was previously check/bet-only at `to_call=0`).
    Locks the user-visible behavior change."""
    cfg = HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.FLOP,
        initial_board=_flop_board(),
        initial_pot=1500,
        initial_contributions=(1000, 500),
        initial_hole_cards=_flop_hole(),
    )
    game = HUNLPoker(cfg)
    s = game.initial_state()
    legal = set(game.legal_actions(s))
    # The two actions that S4 retest reported as missing on the
    # symmetric-subgame extraction path.
    from poker_solver import ACTION_CALL

    assert ACTION_FOLD in legal
    assert ACTION_CALL in legal
    # Check must NOT be legal: there is a bet to face.
    assert ACTION_CHECK not in legal


def test_asymmetric_fold_loses_contributed_chips():
    """Fold-loss accounting must reflect each player's actual contribution.
    P1 folds after putting in 500 → P1 loses 500, P0 wins 500 (NOT 1000)."""
    cfg = HUNLConfig(
        starting_stack=10_000,
        big_blind=100,
        starting_street=Street.FLOP,
        initial_board=_flop_board(),
        initial_pot=1500,
        initial_contributions=(1000, 500),
        initial_hole_cards=_flop_hole(),
    )
    game = HUNLPoker(cfg)
    s = game.initial_state()
    s_folded = game.apply(s, ACTION_FOLD)
    assert game.is_terminal(s_folded)
    u = game.utility(s_folded)
    # Utility is in BB units; P1 contributed 500 cents = 5 BB.
    assert u[0] == pytest.approx(5.0)
    assert u[1] == pytest.approx(-5.0)


# ---------------------------------------------------------------------------
# Fix B — graceful errors on invalid configs (no segfault)
# ---------------------------------------------------------------------------


def test_invalid_negative_contribution_raises():
    """Negative contribution → ValueError, not segfault."""
    with pytest.raises(ValueError, match="non-negative"):
        HUNLConfig(
            starting_stack=10_000,
            starting_street=Street.FLOP,
            initial_board=_flop_board(),
            initial_pot=400,
            initial_contributions=(-100, 500),
        )


def test_invalid_both_negative_raises():
    """Both contributions negative → ValueError."""
    with pytest.raises(ValueError, match="non-negative"):
        HUNLConfig(
            starting_stack=10_000,
            starting_street=Street.FLOP,
            initial_board=_flop_board(),
            initial_pot=0,
            initial_contributions=(-100, -200),
        )


def test_invalid_contribution_exceeds_starting_stack_raises():
    """A contribution > starting_stack would imply a player has negative chips
    behind at subgame start — nonsensical for a subgame. Raise."""
    with pytest.raises(ValueError, match="exceed"):
        HUNLConfig(
            starting_stack=1000,
            starting_street=Street.FLOP,
            initial_board=_flop_board(),
            initial_pot=1500,
            initial_contributions=(1500, 0),
        )


def test_invalid_sum_mismatch_still_raises():
    """Pre-existing guard: sum mismatch with `initial_pot` raises. Re-locked
    here so the new Fix B ordering doesn't accidentally bypass it."""
    with pytest.raises(ValueError, match="sum to initial_pot"):
        HUNLConfig(
            starting_stack=10_000,
            starting_street=Street.FLOP,
            initial_board=_flop_board(),
            initial_pot=1500,
            initial_contributions=(500, 500),
        )


def test_preflop_invalid_contributions_still_raises():
    """Pre-existing guard for preflop: `initial_contributions != (0,0)`
    raises (subgame inputs not allowed at preflop). Re-locked."""
    with pytest.raises(
        ValueError, match="initial_contributions must be \\(0, 0\\) when starting"
    ):
        HUNLConfig(
            starting_street=Street.PREFLOP,
            initial_contributions=(500, 500),
        )


# ---------------------------------------------------------------------------
# Fix A — regression: default_tiny_subgame unchanged
# ---------------------------------------------------------------------------


def test_asymmetric_hole_deal_routes_to_facing_bet_player():
    """When `initial_hole_cards` is empty, the engine starts at a chance node
    that deals hole cards. After dealing, `cur_player` must route to the
    facing-bet player (P0 if c0 < c1, else P1), not unconditionally to P1.
    Locks the `_apply_chance` hole-card branch."""
    cfg = HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.FLOP,
        initial_board=_flop_board(),
        initial_pot=1500,
        initial_contributions=(500, 1000),  # P0 faces a 500 bet
        initial_hole_cards=(),
    )
    game = HUNLPoker(cfg)
    s = game.initial_state()
    # No hole cards yet → cur_player = -1 (chance node).
    assert s.cur_player == -1
    assert s.to_call == 500
    assert s.street_aggressor == 1
    # Deal one hole-pair outcome and check the next cur_player.
    outcomes = game.chance_outcomes(s)
    assert outcomes  # has hole-pair outcomes
    s_dealt = game.apply(s, outcomes[0][0])
    # After hole-deal, P0 (the facing-bet player) acts first.
    assert s_dealt.cur_player == 0
    assert s_dealt.to_call == 500
    assert s_dealt.street_aggressor == 1


def test_default_tiny_subgame_unchanged():
    """`default_tiny_subgame()` returns a symmetric `(500, 500)` config; its
    `initial_state` must produce identical fields to the pre-fix behavior
    (anything else would silently break every river-spot fixture)."""
    from poker_solver.hunl import default_tiny_subgame

    game = HUNLPoker(default_tiny_subgame())
    s = game.initial_state()
    assert s.to_call == 0
    assert s.cur_player == 1
    assert s.street_aggressor == -1
    assert s.street_num_raises == 0
    assert s.contributions == (500, 500)
    assert s.stacks == (1000, 1000)
    assert s.street == Street.RIVER
