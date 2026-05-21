"""Heads-Up No-Limit Hold'em (HUNL) game tree (Python reference tier).

All chip values in `HUNLState` and `HUNLConfig` are **integer cents** scaled
from big blinds (1 BB = 100 cents). Floating-point chip arithmetic is
forbidden throughout this module; utilities only convert to BB-floats at
terminal states for compatibility with the `Game` protocol.

P0 = small blind = button. Acts first preflop, last postflop.
P1 = big blind. Acts last preflop, first postflop.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import IntEnum
from typing import TYPE_CHECKING

from poker_solver.action_abstraction import (
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
    ActionAbstractionConfig,
    ActionContext,
    compute_bet_amount,
    compute_raise_to,
    enumerate_legal_actions,
)
from poker_solver.card import Card, card_to_int, int_to_card
from poker_solver.evaluator import evaluate

if TYPE_CHECKING:
    # Cycle break: poker_solver.abstraction.buckets imports Street from this
    # module. The `abstraction` field is typed via forward-reference; the
    # actual `AbstractionRef` class is imported lazily inside `infoset_key`.
    from poker_solver.abstraction.buckets import AbstractionRef

Action = int

_OPENING_BETS: frozenset[int] = frozenset(
    {ACTION_BET_33, ACTION_BET_75, ACTION_BET_100, ACTION_BET_150, ACTION_BET_200}
)
_RAISES: frozenset[int] = frozenset(
    {
        ACTION_RAISE_33,
        ACTION_RAISE_75,
        ACTION_RAISE_100,
        ACTION_RAISE_150,
        ACTION_RAISE_200,
    }
)


class Street(IntEnum):
    PREFLOP = 0
    FLOP = 1
    TURN = 2
    RIVER = 3
    SHOWDOWN = 4


_STREET_TOKENS: dict[Street, str] = {
    Street.PREFLOP: "p",
    Street.FLOP: "f",
    Street.TURN: "t",
    Street.RIVER: "r",
    Street.SHOWDOWN: "s",
}

_CARDS_TO_DEAL: dict[Street, int] = {
    Street.FLOP: 3,
    Street.TURN: 1,
    Street.RIVER: 1,
}


@dataclass(frozen=True, eq=True)
class HUNLConfig:
    """Immutable configuration for a HUNL tree.

    Defaults: 100 BB symmetric stacks, no ante, no rake, preflop start.
    """

    starting_stack: int = 10_000
    small_blind: int = 50
    big_blind: int = 100
    ante: int = 0
    starting_street: Street = Street.PREFLOP
    initial_board: tuple[Card, ...] = ()
    initial_pot: int = 0
    initial_contributions: tuple[int, int] = (0, 0)
    initial_hole_cards: tuple[tuple[Card, Card], tuple[Card, Card]] | tuple[()] = ()
    preflop_raise_cap: int = 4
    postflop_raise_cap: int = 3
    bet_size_fractions: tuple[float, ...] = (0.33, 0.75, 1.00, 1.50, 2.00)
    include_all_in: bool = True
    rake_rate: float = 0.0
    rake_cap: int = 0
    force_allin_threshold: int = 1
    min_bet_bb: int = 1
    # PR 4: optional card abstraction. `AbstractionRef` carries (source_path,
    # version) only; the runtime resolves it to an `AbstractionTables` via
    # `resolve_abstraction_ref(ref)` (LRU-cached). Excluded from compare/hash
    # because the resolved tables contain numpy arrays that don't hash and
    # because two HUNLConfigs with different abstraction artifacts should still
    # compare equal as game configurations (the abstraction is a runtime
    # adjunct, not a game-rule field). Per consistency review v2 NEW-1.
    abstraction: AbstractionRef | None = field(default=None, compare=False, hash=False)

    def __post_init__(self) -> None:
        if self.rake_rate != 0.0:
            raise AssertionError("rake_rate must be 0.0 in PR 3 (rake lands in PR 9)")
        if self.rake_cap != 0:
            raise AssertionError("rake_cap must be 0 in PR 3 (rake lands in PR 9)")
        if self.starting_street == Street.PREFLOP:
            if self.initial_pot != 0:
                raise ValueError("initial_pot must be 0 when starting at preflop")
            if self.initial_contributions != (0, 0):
                raise ValueError(
                    "initial_contributions must be (0, 0) when starting at preflop"
                )
        else:
            if not self.initial_board:
                raise ValueError(
                    "initial_board must be non-empty when starting_street > PREFLOP"
                )
            # When initial_contributions != (0, 0) they must sum to initial_pot;
            # (0, 0) is accepted as a "dead money" pot whose chips don't count
            # toward either player's fold-loss accounting (subgame analysis).
            contrib_sum = sum(self.initial_contributions)
            if contrib_sum != 0 and contrib_sum != self.initial_pot:
                raise ValueError(
                    "initial_contributions must sum to initial_pot (or be (0,0) "
                    "for dead-money subgames)"
                )

    def to_action_config(self) -> ActionAbstractionConfig:
        return ActionAbstractionConfig(
            bet_size_fractions=self.bet_size_fractions,
            preflop_raise_cap=self.preflop_raise_cap,
            postflop_raise_cap=self.postflop_raise_cap,
            include_all_in=self.include_all_in,
            min_bet_bb=self.min_bet_bb,
            force_allin_threshold_bb=self.force_allin_threshold,
        )


@dataclass(frozen=True)
class HUNLState:
    """Immutable HUNL game state. See PR 3 spec for field semantics."""

    hole_cards: tuple[tuple[Card, Card], tuple[Card, Card]] | tuple[()]
    board: tuple[Card, ...]
    street: Street
    contributions: tuple[int, int]
    stacks: tuple[int, int]
    street_history: tuple[Action, ...]
    street_aggressor: int
    street_num_raises: int
    to_call: int
    cur_player: int
    folded: tuple[bool, bool]
    all_in: tuple[bool, bool]
    config: HUNLConfig
    betting_tokens: tuple[tuple[str, ...], ...] = field(default_factory=tuple)
    current_street_tokens: tuple[str, ...] = field(default_factory=tuple)
    pending_board_deals: int = 0


def default_tiny_subgame() -> HUNLConfig:
    """River-only AhKc vs QdQh subgame on As7c2dKh5s, pot 1000, stacks 1000.

    A deterministic single-street fixture used by the CLI tiny-subgame mode
    and by tests as a small but non-trivial solving target.
    """
    board = (
        Card.from_str("As"),
        Card.from_str("7c"),
        Card.from_str("2d"),
        Card.from_str("Kh"),
        Card.from_str("5s"),
    )
    hole = (
        (Card.from_str("Ah"), Card.from_str("Kc")),
        (Card.from_str("Qd"), Card.from_str("Qh")),
    )
    return HUNLConfig(
        starting_stack=1000,
        starting_street=Street.RIVER,
        initial_board=board,
        initial_pot=1000,
        initial_contributions=(500, 500),
        initial_hole_cards=hole,
    )


def _sorted_card_string(cards: tuple[Card, ...]) -> str:
    sorted_cards = sorted(cards, key=lambda c: (c.rank, c.suit))
    return "".join(str(c) for c in sorted_cards)


class HUNLPoker:
    """Heads-Up No-Limit Hold'em.

    P0 is the small blind / button (acts first preflop, last postflop).
    P1 is the big blind (acts last preflop, first postflop).

    All chip values are integer cents; 1 BB = 100 cents. Utilities are
    returned as floats in big-blind units to match the `Game` protocol
    shared with Kuhn and Leduc.
    """

    num_players: int = 2

    def __init__(self, config: HUNLConfig | None = None) -> None:
        self.config: HUNLConfig = config if config is not None else HUNLConfig()

    def initial_state(self) -> HUNLState:
        cfg = self.config
        if cfg.starting_street == Street.PREFLOP:
            sb_contrib = cfg.small_blind + cfg.ante
            bb_contrib = cfg.big_blind + cfg.ante
            contributions = (sb_contrib, bb_contrib)
            stacks = (
                cfg.starting_stack - sb_contrib,
                cfg.starting_stack - bb_contrib,
            )
            to_call = bb_contrib - sb_contrib
            hole = cfg.initial_hole_cards
            cur_player = -1 if not hole else 0
            return HUNLState(
                hole_cards=hole,
                board=(),
                street=Street.PREFLOP,
                contributions=contributions,
                stacks=stacks,
                street_history=(),
                street_aggressor=1,
                street_num_raises=1,
                to_call=to_call,
                cur_player=cur_player,
                folded=(False, False),
                all_in=(stacks[0] == 0, stacks[1] == 0),
                config=cfg,
            )
        contributions = cfg.initial_contributions
        # Per spec invariant: stacks[i] + contributions[i] - initial_contributions[i]
        # == starting_stack. At subgame start, contributions == initial_contributions,
        # so each player starts with the full starting_stack behind.
        stacks = (cfg.starting_stack, cfg.starting_stack)
        all_in_flags = (stacks[0] == 0, stacks[1] == 0)
        hole = cfg.initial_hole_cards
        cur_player = -1 if any(all_in_flags) or not hole else 1
        return HUNLState(
            hole_cards=hole,
            board=tuple(cfg.initial_board),
            street=cfg.starting_street,
            contributions=contributions,
            stacks=stacks,
            street_history=(),
            street_aggressor=-1,
            street_num_raises=0,
            to_call=0,
            cur_player=cur_player,
            folded=(False, False),
            all_in=all_in_flags,
            config=cfg,
        )

    def is_terminal(self, state: HUNLState) -> bool:
        if any(state.folded):
            return True
        return state.street == Street.SHOWDOWN

    def utility(self, state: HUNLState) -> tuple[float, float]:
        cfg = state.config
        bb = cfg.big_blind
        c0, c1 = state.contributions
        if state.folded[0]:
            return (-c0 / bb, c0 / bb)
        if state.folded[1]:
            return (c1 / bb, -c1 / bb)
        rank0 = evaluate(list(state.hole_cards[0]) + list(state.board))
        rank1 = evaluate(list(state.hole_cards[1]) + list(state.board))
        if rank0 > rank1:
            return (c1 / bb, -c1 / bb)
        if rank1 > rank0:
            return (-c0 / bb, c0 / bb)
        return (0.0, 0.0)

    def current_player(self, state: HUNLState) -> int:
        if self.is_terminal(state):
            return -1
        return state.cur_player

    def chance_outcomes(self, state: HUNLState) -> list[tuple[Action, float]]:
        if state.cur_player != -1 or self.is_terminal(state):
            return []
        if not state.hole_cards:
            return _enumerate_preflop_hole_outcomes()
        return self._board_card_outcomes(state)

    def legal_actions(self, state: HUNLState) -> list[Action]:
        if self.is_terminal(state) or state.cur_player == -1:
            return []
        ctx = self._action_context(state)
        return enumerate_legal_actions(ctx)

    def apply(self, state: HUNLState, action: Action) -> HUNLState:
        if state.cur_player == -1:
            return self._apply_chance(state, action)
        return self._apply_player(state, action)

    def infoset_key(self, state: HUNLState, player: int) -> str:
        cfg = state.config
        if cfg.abstraction is not None and state.street >= Street.FLOP:
            # Bucketed path: resolve `AbstractionRef` -> cached `AbstractionTables`,
            # then look up the bucket id. Preflop always falls through to the
            # lossless branch (per Decision 7.12).
            from poker_solver.abstraction.buckets import (
                lookup_bucket,
                resolve_abstraction_ref,
            )

            tables = resolve_abstraction_ref(cfg.abstraction)
            bucket_id = lookup_bucket(
                tables,
                state.board,
                state.hole_cards[player],
                state.street,
            )
            street_token = _STREET_TOKENS.get(state.street, "s")
            all_streets = list(state.betting_tokens) + [state.current_street_tokens]
            history = "/".join("".join(tokens) for tokens in all_streets)
            return f"b{bucket_id}|{street_token}|{history}"
        # Lossless path (PR 3 behavior preserved exactly).
        if state.hole_cards:
            player_hole = _sorted_card_string(state.hole_cards[player])
        else:
            player_hole = ""
        board = _sorted_card_string(state.board)
        street_token = _STREET_TOKENS.get(state.street, "s")
        all_streets = list(state.betting_tokens) + [state.current_street_tokens]
        history = "/".join("".join(tokens) for tokens in all_streets)
        return f"{player_hole}|{board}|{street_token}|{history}"

    def _action_context(self, state: HUNLState) -> ActionContext:
        cfg = state.config
        pot = (
            sum(state.contributions) + cfg.initial_pot - sum(cfg.initial_contributions)
        )
        return ActionContext(
            pot=pot,
            to_call=state.to_call,
            stacks=state.stacks,
            contributions=state.contributions,
            cur_player=state.cur_player,
            street=int(state.street),
            street_num_raises=state.street_num_raises,
            street_aggressor=state.street_aggressor,
            big_blind=cfg.big_blind,
            bet_size_fractions=cfg.bet_size_fractions,
            preflop_raise_cap=cfg.preflop_raise_cap,
            postflop_raise_cap=cfg.postflop_raise_cap,
            force_allin_threshold_bb=cfg.force_allin_threshold,
            min_bet_bb=cfg.min_bet_bb,
            include_all_in=cfg.include_all_in,
        )

    def _apply_player(self, state: HUNLState, action: Action) -> HUNLState:
        ctx = self._action_context(state)
        player = state.cur_player
        contributions = list(state.contributions)
        stacks = list(state.stacks)
        folded = list(state.folded)
        all_in = list(state.all_in)
        street_aggressor = state.street_aggressor
        street_num_raises = state.street_num_raises
        to_call = state.to_call
        token = ""

        if action == ACTION_FOLD:
            folded[player] = True
            token = "f"
        elif action == ACTION_CHECK:
            token = "x"
        elif action == ACTION_CALL:
            pay = min(state.to_call, stacks[player])
            contributions[player] += pay
            stacks[player] -= pay
            if stacks[player] == 0:
                all_in[player] = True
            to_call = 0
            token = "c"
        elif action == ACTION_ALL_IN:
            pay = stacks[player]
            contributions[player] += pay
            stacks[player] = 0
            all_in[player] = True
            opp = 1 - player
            to_call = max(0, contributions[player] - contributions[opp])
            street_aggressor = player
            street_num_raises += 1
            token = "A"
        elif action in _OPENING_BETS:
            amount = compute_bet_amount(action, ctx)
            contributions[player] += amount
            stacks[player] -= amount
            if stacks[player] == 0:
                all_in[player] = True
            opp = 1 - player
            to_call = contributions[player] - contributions[opp]
            street_aggressor = player
            street_num_raises += 1
            token = f"b{amount}"
        elif action in _RAISES:
            new_contrib = compute_raise_to(action, ctx)
            pay = new_contrib - contributions[player]
            contributions[player] = new_contrib
            stacks[player] -= pay
            if stacks[player] == 0:
                all_in[player] = True
            opp = 1 - player
            to_call = contributions[player] - contributions[opp]
            street_aggressor = player
            street_num_raises += 1
            token = f"r{new_contrib}"
        else:
            raise ValueError(f"Unknown HUNL action: {action}")

        new_history = state.street_history + (action,)
        new_tokens = state.current_street_tokens + (token,)
        new_folded = (folded[0], folded[1])
        new_all_in = (all_in[0], all_in[1])

        new_state = replace(
            state,
            contributions=(contributions[0], contributions[1]),
            stacks=(stacks[0], stacks[1]),
            street_history=new_history,
            current_street_tokens=new_tokens,
            street_aggressor=street_aggressor,
            street_num_raises=street_num_raises,
            to_call=to_call,
            folded=new_folded,
            all_in=new_all_in,
        )

        if any(new_folded):
            return replace(new_state, cur_player=-1)
        if self._street_complete(state, action, new_state):
            return self._begin_street_transition(new_state)
        return replace(new_state, cur_player=1 - player)

    def _apply_chance(self, state: HUNLState, action: Action) -> HUNLState:
        if not state.hole_cards:
            new_hole = _normalize_hole_action(action)
            next_cur = 0 if state.street == Street.PREFLOP else 1
            return replace(state, hole_cards=new_hole, cur_player=next_cur)
        card = int_to_card(action)
        new_board = state.board + (card,)
        pending = state.pending_board_deals - 1
        if pending > 0:
            return replace(state, board=new_board, pending_board_deals=pending)
        return self._after_board_dealt(
            replace(state, board=new_board, pending_board_deals=0)
        )

    def _street_complete(
        self,
        old_state: HUNLState,
        action: Action,
        new_state: HUNLState,
    ) -> bool:
        """Detect end of betting for the current street.

        Round closes when contributions are matched AND each player has
        had a chance to respond to the latest aggression. We track that
        implicitly: if the action that just happened was a call closing
        an opponent's bet/raise, AND both players have acted, the street
        ends. Otherwise, the round continues (e.g. preflop limp does not
        close because the BB still has option after a SB call).
        """
        if action == ACTION_FOLD:
            return False
        if new_state.to_call > 0:
            return False
        # ALL-IN that matches (or under-shoves) an existing aggression closes
        # the street — same semantics as CALL. The new_state.to_call > 0 guard
        # above already handled the over-shove-as-raise case (opponent still
        # has option). An opening ALL-IN (old to_call == 0) does NOT close;
        # opponent still has option to fold/call.
        if action == ACTION_ALL_IN and old_state.to_call > 0:
            return True
        player = old_state.cur_player
        opponent = 1 - player
        # Postflop check-through: both players check with no aggression.
        if (
            action == ACTION_CHECK
            and old_state.street_aggressor == -1
            and len(new_state.street_history) >= 2
        ):
            return True
        # Preflop BB option: after SB limp, BB checking through ends.
        if (
            old_state.street == Street.PREFLOP
            and action == ACTION_CHECK
            and player == 1
            and old_state.street_aggressor == 1
            and old_state.street_num_raises == 1
        ):
            return True
        # A call closes the street unless it was a preflop SB limp (which
        # gives BB an option to act). Preflop SB CALL on the initial BB-as-
        # aggressor leaves BB to act; postflop a call always closes.
        if action == ACTION_CALL:
            # SB calling the BB's preflop blind leaves BB with option; postflop
            # a call always closes the street.
            return not (
                old_state.street == Street.PREFLOP
                and old_state.street_aggressor == opponent
                and old_state.street_num_raises == 1
                and player == 0
            )
        return False

    def _begin_street_transition(self, state: HUNLState) -> HUNLState:
        """Move past the just-completed street: transition to next street or showdown."""
        new_tokens = state.betting_tokens + (state.current_street_tokens,)
        flushed = replace(state, betting_tokens=new_tokens, current_street_tokens=())
        if flushed.street == Street.RIVER:
            return replace(flushed, street=Street.SHOWDOWN, cur_player=-1)
        if any(flushed.all_in):
            # All-in run-out: emit one card at a time via sequential chance
            # nodes, regardless of street, until the board has 5 cards.
            return replace(
                flushed,
                cur_player=-1,
                pending_board_deals=1,
                street_history=(),
                street_aggressor=-1,
                street_num_raises=0,
                to_call=0,
            )
        next_street = Street(int(flushed.street) + 1)
        deals = _CARDS_TO_DEAL[next_street]
        return replace(
            flushed,
            street=next_street,
            cur_player=-1,
            pending_board_deals=deals,
            street_history=(),
            street_aggressor=-1,
            street_num_raises=0,
            to_call=0,
        )

    def _after_board_dealt(self, state: HUNLState) -> HUNLState:
        """Called after all pending board cards for the street have been dealt."""
        if any(state.all_in):
            # Run-out: keep dealing one card at a time until the board has
            # 5 cards, then go to showdown.
            if len(state.board) >= 5:
                return replace(state, street=Street.SHOWDOWN, cur_player=-1)
            return replace(state, cur_player=-1, pending_board_deals=1)
        return replace(state, cur_player=1)

    def _board_card_outcomes(self, state: HUNLState) -> list[tuple[Action, float]]:
        held: set[Card] = set()
        if state.hole_cards:
            held.update(state.hole_cards[0])
            held.update(state.hole_cards[1])
        held.update(state.board)
        remaining = [
            Card(r, s) for r in range(2, 15) for s in range(4) if Card(r, s) not in held
        ]
        if not remaining:
            return []
        p = 1.0 / len(remaining)
        return [(card_to_int(c), p) for c in remaining]


def _enumerate_preflop_hole_outcomes() -> list[tuple[Action, float]]:
    cards = [Card(r, s) for r in range(2, 15) for s in range(4)]
    outcomes: list[Action] = []
    n = len(cards)
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(n):
                if k in (i, j):
                    continue
                for m in range(k + 1, n):
                    if m in (i, j):
                        continue
                    outcomes.append(
                        _pack_hole_outcome(cards[i], cards[j], cards[k], cards[m])
                    )
    total = len(outcomes)
    p = 1.0 / total if total else 0.0
    return [(a, p) for a in outcomes]


def _normalize_hole_action(
    action: object,
) -> tuple[tuple[Card, Card], tuple[Card, Card]]:
    """Accept either a packed-int hole outcome or a nested tuple of Cards."""
    if isinstance(action, tuple):
        return action  # type: ignore[return-value]
    cards = _unpack_hole_outcome(int(action))  # type: ignore[arg-type]
    return ((cards[0], cards[1]), (cards[2], cards[3]))


def _pack_hole_outcome(c0: Card, c1: Card, c2: Card, c3: Card) -> int:
    return (
        (card_to_int(c0) << 24)
        | (card_to_int(c1) << 16)
        | (card_to_int(c2) << 8)
        | card_to_int(c3)
    )


def _unpack_hole_outcome(action: Action) -> tuple[Card, Card, Card, Card]:
    c0 = int_to_card((action >> 24) & 0xFF)
    c1 = int_to_card((action >> 16) & 0xFF)
    c2 = int_to_card((action >> 8) & 0xFF)
    c3 = int_to_card(action & 0xFF)
    return (c0, c1, c2, c3)


__all__ = [
    "HUNLConfig",
    "HUNLPoker",
    "HUNLState",
    "Street",
    "default_tiny_subgame",
]
