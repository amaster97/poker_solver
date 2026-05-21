"""Game definitions for the solver (Python reference tier).

The `Game` protocol is the contract every solver consumes. Each game describes
its tree purely in terms of states, actions, chance outcomes, terminal payoffs,
and infoset keys; the DCFR solver in `dcfr.py` walks this tree generically.

Kuhn poker is the smallest standard imperfect-information game used to validate
CFR-family solvers: 3-card deck (J, Q, K), one ante from each player, then a
single round of check/bet/call/fold.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

Action = int

PASS: Action = 0
BET: Action = 1

_KUHN_DECK: tuple[int, ...] = (11, 12, 13)
_HISTORY_CHARS = {PASS: "p", BET: "b"}
_KUHN_TERMINAL_HISTORIES = frozenset({"pp", "bp", "bb", "pbp", "pbb"})


@runtime_checkable
class Game(Protocol):
    """Protocol every solver-consumable game implements."""

    num_players: int

    def initial_state(self) -> Any: ...

    def is_terminal(self, state: Any) -> bool: ...

    def utility(self, state: Any) -> tuple[float, ...]: ...

    def current_player(self, state: Any) -> int:
        """Return the player to act, or -1 for chance nodes."""
        ...

    def chance_outcomes(self, state: Any) -> list[tuple[Action, float]]: ...

    def legal_actions(self, state: Any) -> list[Action]: ...

    def apply(self, state: Any, action: Action) -> Any: ...

    def infoset_key(self, state: Any, player: int) -> str: ...


@dataclass(frozen=True)
class KuhnState:
    cards: tuple[int, ...]
    history: tuple[Action, ...]


def _history_string(history: tuple[Action, ...]) -> str:
    return "".join(_HISTORY_CHARS[a] for a in history)


class KuhnPoker:
    """Kuhn poker: 3-card deck, two players, one ante, one bet round.

    Chance deals card to P1 then P2 (two chance moves). Player nodes choose
    between PASS and BET. Terminal histories with payoffs (in antes, P1
    perspective; opponent receives the negation):

      pp   -> showdown, pot 2, winner gets +1 from loser
      bp   -> P1 bets, P2 folds, P1 wins ante (+1)
      bb   -> showdown, pot 4, winner gets +2 from loser
      pbp  -> P1 passes, P2 bets, P1 folds, P2 wins ante (P1 -1)
      pbb  -> P1 passes, P2 bets, P1 calls, showdown pot 4, winner +2
    """

    num_players: int = 2

    def initial_state(self) -> KuhnState:
        return KuhnState(cards=(), history=())

    def is_terminal(self, state: KuhnState) -> bool:
        if len(state.cards) < 2:
            return False
        return _history_string(state.history) in _KUHN_TERMINAL_HISTORIES

    def utility(self, state: KuhnState) -> tuple[float, float]:
        hist = _history_string(state.history)
        c0, c1 = state.cards
        showdown_winner = 0 if c0 > c1 else 1
        if hist == "pp":
            payoff = 1.0 if showdown_winner == 0 else -1.0
        elif hist == "bp":
            payoff = 1.0
        elif hist == "bb":
            payoff = 2.0 if showdown_winner == 0 else -2.0
        elif hist == "pbp":
            payoff = -1.0
        elif hist == "pbb":
            payoff = 2.0 if showdown_winner == 0 else -2.0
        else:
            raise ValueError(f"Non-terminal history: {hist}")
        return (payoff, -payoff)

    def current_player(self, state: KuhnState) -> int:
        if len(state.cards) < 2:
            return -1
        return len(state.history) % 2

    def chance_outcomes(self, state: KuhnState) -> list[tuple[Action, float]]:
        dealt = set(state.cards)
        remaining = [c for c in _KUHN_DECK if c not in dealt]
        p = 1.0 / len(remaining)
        return [(c, p) for c in remaining]

    def legal_actions(self, state: KuhnState) -> list[Action]:
        if self.is_terminal(state):
            return []
        return [PASS, BET]

    def apply(self, state: KuhnState, action: Action) -> KuhnState:
        if len(state.cards) < 2:
            return KuhnState(cards=state.cards + (action,), history=state.history)
        return KuhnState(cards=state.cards, history=state.history + (action,))

    def infoset_key(self, state: KuhnState, player: int) -> str:
        return f"{state.cards[player]}|{_history_string(state.history)}"


def kuhn_nash_value() -> float:
    """Game value of Kuhn poker for player 0 under Nash equilibrium."""
    return -1.0 / 18.0
