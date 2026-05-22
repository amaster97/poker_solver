"""Poker-intuition sanity checks on the Python DCFR Leduc solver.

Closed-form Nash isn't trivially available for Leduc, so we lean on heuristic
checks that any correct equilibrium (with bet sizes 2/4 and 2-raise cap) must
satisfy. A failure here means either the heuristic is wrong (revise it) or the
solver is buggy (flag it for review); we do not loosen thresholds to pass.

Infoset key conventions follow `poker_solver.games.LeducPoker.infoset_key`:
  * Round 1: ``"{private}|{r1_history}"`` with chars ``f``/``c``/``r``.
  * Round 2: ``"{private}|{r1_history}|{public}|{r2_history}"``.
Action ordering for each infoset is the list returned by ``legal_actions``:
no-bet-facing -> ``[CALL, RAISE]``; facing-bet-with-raise-cap-open ->
``[FOLD, CALL, RAISE]``; facing-bet-at-cap -> ``[FOLD, CALL]``.
"""

from __future__ import annotations

import pytest

from poker_solver import LEDUC_CALL, LEDUC_FOLD, LEDUC_RAISE, LeducPoker, solve

# 800 iterations of the Python DCFR backend on Leduc lands at exploitability
# around 0.023 and takes ~55s on a 2024 Mac laptop. The fixture caps at one
# solve (module scope) so the whole test module runs within the 60s budget.
LEDUC_ITERATIONS = 800

# pytest-timeout doesn't apply to module-scoped fixtures by default. The
# fixture runs one 800-iter Python Leduc DCFR solve (~55s nominal, ~100s
# on x86_64 Python under Rosetta). Bump per-test cap above pytest's 90s
# default so the fixture's first-touch setup fits.
_LEDUC_INTUITION_TIMEOUT = 180


@pytest.fixture(scope="module")
def leduc_strategy():
    """Solve Leduc once at the module's iteration budget and return the avg strategy."""
    result = solve(LeducPoker(), LEDUC_ITERATIONS, backend="python")
    return result.average_strategy


def _enumerate_reachable_infosets() -> set[str]:
    """Walk the Leduc tree and collect every infoset key that any decision node uses."""
    game = LeducPoker()
    keys: set[str] = set()

    def walk(state) -> None:
        if game.is_terminal(state):
            return
        player = game.current_player(state)
        if player == -1:
            for action, _ in game.chance_outcomes(state):
                walk(game.apply(state, action))
            return
        keys.add(game.infoset_key(state, player))
        for action in game.legal_actions(state):
            walk(game.apply(state, action))

    walk(game.initial_state())
    return keys


@pytest.mark.timeout(_LEDUC_INTUITION_TIMEOUT)
def test_king_never_folds_to_first_bet(leduc_strategy):
    # Round-1 infosets where the player holds K (private=13), no public card has
    # been revealed, and the opponent has put in exactly one raise. Two such
    # infosets exist by symmetry: "13|r" is P1 facing P0's open raise; "13|cr"
    # is P0 facing P1's raise after P0 called. In both cases the action layout
    # is [FOLD, CALL, RAISE]. K is the strongest possible private card and
    # leads any opponent's range; folding here surrenders +EV chips to a single
    # bet. Equilibrium fold frequency must be effectively zero.
    for key in ("13|r", "13|cr"):
        probs = leduc_strategy[key]
        fold_prob = probs[LEDUC_FOLD]
        assert fold_prob < 0.05, (
            f"Solver folds K-high at {key!r} with prob {fold_prob:.4f} facing the "
            f"first bet. K is the top private card in Leduc and dominates any "
            f"opposing hand pre-public-card; equilibrium should defend K nearly "
            f"always."
        )


@pytest.mark.timeout(_LEDUC_INTUITION_TIMEOUT)
def test_jack_never_raises_round1_when_facing_raise(leduc_strategy):
    # Round-1 infosets where the player holds J (private=11) and the opponent
    # has bet/raised once: "11|r" (P1 facing P0's open raise) and "11|cr"
    # (P0 facing P1's raise after own call). The raise option is in slot 2
    # of [FOLD, CALL, RAISE]. J is the weakest private card with no information
    # about the public card; re-raising into a raise builds a pot with the
    # bottom of the range against an opponent showing strength. Equilibrium
    # raise frequency here should be small.
    for key in ("11|r", "11|cr"):
        probs = leduc_strategy[key]
        raise_prob = probs[LEDUC_RAISE]
        assert raise_prob < 0.10, (
            f"Solver re-raises J at {key!r} with prob {raise_prob:.4f} into the "
            f"opponent's raise. J is the worst private rank in Leduc with no "
            f"public-card information; equilibrium should rarely escalate the "
            f"pot from the bottom of the range against a strong-looking opponent."
        )


@pytest.mark.timeout(_LEDUC_INTUITION_TIMEOUT)
def test_pair_with_public_card_value_betting(leduc_strategy):
    # "private = public_card" is the strongest possible holding in Leduc:
    # a pair always beats any non-paired opponent and ties only opponents
    # holding the matching rank. We probe the round-2 infoset where the player
    # holds Q (12) and the public card is Q, after preflop check-check, and
    # the opponent has already bet -- "12|cc|12|r" (P1 with QQ facing P0's bet)
    # and "12|cc|12|cr" (P0 with QQ after own check and opponent's bet). The
    # action layout is [FOLD, CALL, RAISE]; the original heuristic asks for
    # call+raise > 0.6 (equivalently fold < 0.4) so the player is not folding
    # the nuts. A monster in equilibrium should call+raise effectively 100% of
    # the time; this threshold is the loose version of that constraint.
    for key in ("12|cc|12|r", "12|cc|12|cr"):
        probs = leduc_strategy[key]
        call_plus_raise = probs[LEDUC_CALL] + probs[LEDUC_RAISE]
        assert call_plus_raise > 0.6, (
            f"Solver folds top-pair Q-on-Q board at {key!r} with prob "
            f"{probs[LEDUC_FOLD]:.4f} (call+raise={call_plus_raise:.4f}). A "
            f"private card matching the public card is the nuts in Leduc; "
            f"equilibrium should never fold this monster to a single bet."
        )


@pytest.mark.timeout(_LEDUC_INTUITION_TIMEOUT)
def test_underpair_caution(leduc_strategy):
    # "private = J on K public board" -- private=11, public=13. K-high public
    # paired board scenario: anyone holding K has a pair (top set) and is
    # virtually never folding to a raise; even Q has a higher kicker than J.
    # We probe the canonical infoset reached after preflop check-check: P0
    # holds J, sees a K public, P1 bets, P0 to act -- "11|cc|13|r" (P0's view)
    # and "11|cc|13|cr" (P0 after own check then P1 bet). The action layout
    # is [FOLD, CALL, RAISE]. J on K board is the bottom of the range against
    # an opponent who is now signalling strength; equilibrium should fold a
    # substantial fraction of the time.
    for key in ("11|cc|13|r", "11|cc|13|cr"):
        probs = leduc_strategy[key]
        fold_prob = probs[LEDUC_FOLD]
        assert fold_prob > 0.40, (
            f"Solver only folds J on K board at {key!r} with prob "
            f"{fold_prob:.4f} facing a raise. J is the bottom card on a "
            f"K-high paired board; equilibrium should fold a substantial "
            f"fraction of the time since opponent's bet signals K or a "
            f"strong overcard."
        )


@pytest.mark.timeout(_LEDUC_INTUITION_TIMEOUT)
def test_strategy_mass_sums_to_one(leduc_strategy):
    # Every infoset's action distribution must be a valid probability vector.
    # Floating-point round-off should be well under 1e-9 for any infoset since
    # DCFR builds strategies by normalizing a sum that never crosses 1.0.
    for key, probs in leduc_strategy.items():
        total = sum(probs)
        assert total == pytest.approx(1.0, abs=1e-9), (
            f"Strategy at {key!r} sums to {total:.12f}, not 1.0. Probability "
            f"mass must sum to one at every infoset; a broken normalization "
            f"would produce mis-weighted action choices throughout the tree."
        )


@pytest.mark.timeout(_LEDUC_INTUITION_TIMEOUT)
def test_strategy_is_well_defined_on_all_reachable_infosets(leduc_strategy):
    # The Leduc game tree has 288 reachable infosets (see test_leduc_dcfr.py).
    # DCFR's tree-walk traverses every decision node every iteration, so every
    # reachable infoset must end up in the average-strategy dict. A missing
    # key would mean the solver short-circuited some subtree and would silently
    # default to the uniform policy there, hiding a real bug.
    reachable = _enumerate_reachable_infosets()
    strategy_keys = set(leduc_strategy.keys())
    missing = reachable - strategy_keys
    assert not missing, (
        f"Strategy is missing {len(missing)} reachable infoset(s); "
        f"e.g. {sorted(missing)[:5]}. DCFR visits every decision node "
        f"each iteration in Leduc, so the average strategy must cover the "
        f"full tree; any default-to-uniform infoset hides a traversal bug."
    )


# Sanity probe: the LEDUC_CALL/RAISE/FOLD action ids must line up with the
# action-vector slots used by the assertions above. We pin them here so a
# refactor of the action encoding breaks this test instead of silently
# inverting the polarity of every probability check.
def test_action_id_layout_matches_assertion_indices():
    assert LEDUC_FOLD == 0
    assert LEDUC_CALL == 1
    assert LEDUC_RAISE == 2
