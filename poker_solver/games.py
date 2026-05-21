"""Game definitions for the solver (Python reference tier).

The `Game` protocol is the contract every solver consumes. Each game describes
its tree purely in terms of states, actions, chance outcomes, terminal payoffs,
and infoset keys; the DCFR solver in `dcfr.py` walks this tree generically.

Kuhn poker is the smallest standard imperfect-information game used to validate
CFR-family solvers: 3-card deck (J, Q, K), one ante from each player, then a
single round of check/bet/call/fold.

Leduc poker is the next benchmark up: 6-card deck (J, Q, K, two suits), two
betting rounds with a public card between them, two-bet cap per round, ante 1.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
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


LEDUC_FOLD: Action = 0
LEDUC_CALL: Action = 1
LEDUC_RAISE: Action = 2

_LEDUC_RANKS: tuple[int, ...] = (11, 12, 13)
_LEDUC_DECK: tuple[int, ...] = (11, 11, 12, 12, 13, 13)
_LEDUC_ACTION_CHARS = {LEDUC_FOLD: "f", LEDUC_CALL: "c", LEDUC_RAISE: "r"}
_LEDUC_FIRST_RAISE = 2
_LEDUC_SECOND_RAISE = 4
_LEDUC_MAX_RAISES = 2
_LEDUC_ANTE = 1


@dataclass(frozen=True)
class LeducState:
    private_cards: tuple[int, ...]
    public_card: int | None
    round1_history: tuple[Action, ...]
    round2_history: tuple[Action, ...]
    ante: tuple[int, int]
    folded: tuple[bool, bool]
    round_num: int
    num_raises: int
    num_calls: int
    stakes: int
    cur_player: int

    @property
    def pot(self) -> int:
        return self.ante[0] + self.ante[1]


def _leduc_round_string(history: tuple[Action, ...]) -> str:
    return "".join(_LEDUC_ACTION_CHARS[a] for a in history)


class LeducPoker:
    """Leduc poker: 6-card deck, two players, two rounds, two-bet cap per round.

    Canonical small benchmark for CFR-family solvers (Southey et al., UAI 2005;
    poker.cs.ualberta.ca/publications/UAI05.pdf). Rules verified against
    open_spiel/games/leduc_poker/leduc_poker.cc (Apache 2.0).

    Deck: two suits of (J=11, Q=12, K=13). Each player antes 1 chip, then
    receives one private card. Round 1 betting (raise size 2, max 2 raises),
    then a single public card is revealed. Round 2 betting (raise size 4, max
    2 raises). At showdown a player whose private card matches the public
    card wins; otherwise the higher private card wins; ties split the pot.

    Action ids match open_spiel's encoding: fold=0, call=1, raise=2. A player
    may fold only when facing an unmatched bet; otherwise legal actions are
    {call, raise} (and only {call} when the raise cap is hit). The starting
    player for both betting rounds is P0.
    """

    num_players: int = 2

    def initial_state(self) -> LeducState:
        return LeducState(
            private_cards=(),
            public_card=None,
            round1_history=(),
            round2_history=(),
            ante=(_LEDUC_ANTE, _LEDUC_ANTE),
            folded=(False, False),
            round_num=1,
            num_raises=0,
            num_calls=0,
            stakes=_LEDUC_ANTE,
            cur_player=-1,
        )

    def is_terminal(self, state: LeducState) -> bool:
        if any(state.folded):
            return True
        return state.round_num == 2 and self._round_complete(state)

    def utility(self, state: LeducState) -> tuple[float, float]:
        ante0, ante1 = state.ante
        if state.folded[0]:
            return (-float(ante0), float(ante0))
        if state.folded[1]:
            return (float(ante1), -float(ante1))
        assert state.public_card is not None
        c0, c1 = state.private_cards
        pub = state.public_card
        if c0 == pub and c1 != pub:
            return (float(ante1), -float(ante1))
        if c1 == pub and c0 != pub:
            return (-float(ante0), float(ante0))
        if c0 > c1:
            return (float(ante1), -float(ante1))
        if c1 > c0:
            return (-float(ante0), float(ante0))
        return (0.0, 0.0)

    def current_player(self, state: LeducState) -> int:
        if self.is_terminal(state):
            return -1
        return state.cur_player

    def chance_outcomes(self, state: LeducState) -> list[tuple[Action, float]]:
        dealt = list(state.private_cards)
        if state.public_card is not None:
            dealt.append(state.public_card)
        remaining = list(_LEDUC_DECK)
        for card in dealt:
            remaining.remove(card)
        p = 1.0 / len(remaining)
        return [(c, p) for c in remaining]

    def legal_actions(self, state: LeducState) -> list[Action]:
        if self.is_terminal(state) or state.cur_player == -1:
            return []
        actions: list[Action] = []
        player = state.cur_player
        if state.stakes > state.ante[player]:
            actions.append(LEDUC_FOLD)
        actions.append(LEDUC_CALL)
        if state.num_raises < _LEDUC_MAX_RAISES:
            actions.append(LEDUC_RAISE)
        return actions

    def apply(self, state: LeducState, action: Action) -> LeducState:
        if state.cur_player == -1:
            return self._apply_chance(state, action)
        return self._apply_player(state, action)

    def infoset_key(self, state: LeducState, player: int) -> str:
        private = state.private_cards[player]
        r1 = _leduc_round_string(state.round1_history)
        if state.public_card is None:
            return f"{private}|{r1}"
        r2 = _leduc_round_string(state.round2_history)
        return f"{private}|{r1}|{state.public_card}|{r2}"

    def _apply_chance(self, state: LeducState, card: Action) -> LeducState:
        if len(state.private_cards) < self.num_players:
            new_privates = state.private_cards + (card,)
            cur_player = -1 if len(new_privates) < self.num_players else 0
            return replace(state, private_cards=new_privates, cur_player=cur_player)
        return replace(
            state,
            public_card=card,
            round_num=2,
            num_raises=0,
            num_calls=0,
            cur_player=self._first_non_folded(state.folded),
        )

    def _apply_player(self, state: LeducState, action: Action) -> LeducState:
        player = state.cur_player
        ante = list(state.ante)
        folded = list(state.folded)
        num_raises = state.num_raises
        num_calls = state.num_calls
        stakes = state.stakes

        if action == LEDUC_FOLD:
            folded[player] = True
        elif action == LEDUC_CALL:
            ante[player] = stakes
            num_calls += 1
        elif action == LEDUC_RAISE:
            raise_amount = (
                _LEDUC_FIRST_RAISE if state.round_num == 1 else _LEDUC_SECOND_RAISE
            )
            stakes += raise_amount
            ante[player] = stakes
            num_raises += 1
            num_calls = 0
        else:
            raise ValueError(f"Invalid Leduc action: {action}")

        if state.round_num == 1:
            r1 = state.round1_history + (action,)
            r2 = state.round2_history
        else:
            r1 = state.round1_history
            r2 = state.round2_history + (action,)

        new_folded = (folded[0], folded[1])
        new_state = replace(
            state,
            round1_history=r1,
            round2_history=r2,
            ante=(ante[0], ante[1]),
            folded=new_folded,
            num_raises=num_raises,
            num_calls=num_calls,
            stakes=stakes,
        )

        if any(new_folded) or self._round_complete(new_state):
            return replace(new_state, cur_player=-1)
        return replace(new_state, cur_player=self._next_player(player, new_folded))

    @staticmethod
    def _first_non_folded(folded: tuple[bool, bool]) -> int:
        for i in range(2):
            if not folded[i]:
                return i
        return -1

    @staticmethod
    def _next_player(player: int, folded: tuple[bool, bool]) -> int:
        for i in range(1, 3):
            cand = (player + i) % 2
            if not folded[cand]:
                return cand
        return -1

    @staticmethod
    def _round_complete(state: LeducState) -> bool:
        remaining = 2 - sum(state.folded)
        if state.num_raises == 0:
            return state.num_calls == remaining
        return state.num_calls == remaining - 1
