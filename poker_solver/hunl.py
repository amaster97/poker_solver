"""Heads-Up No-Limit Hold'em (HUNL) game tree (Python reference tier).

License posture: no third-party code derivation; original implementation
(rules-engine state machine and infoset-key format are independent of any
specific reference repo; see PR 3 audit report for the per-area review).

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
        # PR 31 (task #185): type validation at the dataclass boundary so
        # wrong-type construction fails LOUDLY here, not silently deep in the
        # per-hand solver. W2.3 Sarah retest crashed with
        # `AttributeError: 'int' object has no attribute 'rank'` inside the
        # solver because a caller passed `initial_board=(int, int, int)` (card
        # indices) instead of `tuple[Card, ...]`. Same trap exists for
        # `initial_hole_cards`. We coerce list -> tuple silently for the
        # collection fields (lists are reasonable user input), but reject
        # wrong element types with a helpful message.
        self._validate_scalar_fields()
        self._validate_initial_board()
        self._validate_initial_hole_cards()
        self._validate_bet_size_fractions()

        if self.rake_rate != 0.0:
            raise ValueError("rake_rate must be 0.0 in PR 3 (rake lands in PR 9)")
        if self.rake_cap != 0:
            raise ValueError("rake_cap must be 0 in PR 3 (rake lands in PR 9)")
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
            # PR 22 Fix B: graceful error on invalid asymmetric configs (was a
            # Rust-side segfault path in v1.3.1 S4 retest).
            c0, c1 = self.initial_contributions
            if c0 < 0 or c1 < 0:
                raise ValueError(
                    f"initial_contributions must be non-negative; got ({c0}, {c1})"
                )
            if c0 > self.starting_stack or c1 > self.starting_stack:
                raise ValueError(
                    f"initial_contributions ({c0}, {c1}) must not exceed "
                    f"starting_stack ({self.starting_stack}); a player cannot "
                    f"have contributed more than their starting stack"
                )
            # When initial_contributions != (0, 0) they must sum to initial_pot;
            # (0, 0) is accepted as a "dead money" pot whose chips don't count
            # toward either player's fold-loss accounting (subgame analysis).
            contrib_sum = c0 + c1
            if contrib_sum != 0 and contrib_sum != self.initial_pot:
                raise ValueError(
                    "initial_contributions must sum to initial_pot (or be (0,0) "
                    "for dead-money subgames)"
                )

    # ------------------------------------------------------------------
    # PR 31: type-validation helpers (private). Kept close to __post_init__
    # so future field additions are obvious.
    # ------------------------------------------------------------------

    def _validate_scalar_fields(self) -> None:
        """starting_stack / big_blind / small_blind / ante / initial_pot are
        non-negative ints. starting_stack and big_blind must be strictly
        positive (a 0-stack or 0-BB game is degenerate)."""
        for name, val, must_be_positive in (
            ("starting_stack", self.starting_stack, True),
            ("big_blind", self.big_blind, True),
            ("small_blind", self.small_blind, False),
            ("ante", self.ante, False),
            ("initial_pot", self.initial_pot, False),
        ):
            # `bool` is a subclass of `int` — explicitly reject to catch
            # accidental True/False passthrough.
            if isinstance(val, bool) or not isinstance(val, int):
                raise TypeError(
                    f"HUNLConfig.{name}: expected int, got {type(val).__name__}"
                )
            if val < 0:
                raise ValueError(
                    f"HUNLConfig.{name} must be non-negative; got {val}"
                )
            if must_be_positive and val == 0:
                raise ValueError(
                    f"HUNLConfig.{name} must be positive; got {val}"
                )

    def _validate_initial_board(self) -> None:
        """`initial_board` must be tuple/list of Card. Coerce list -> tuple."""
        board = self.initial_board
        if not isinstance(board, (tuple, list)):
            raise TypeError(
                f"HUNLConfig.initial_board: expected tuple of Card, got "
                f"{type(board).__name__}. Use parse_board(...) or "
                f"Card.from_str(...) to construct cards."
            )
        for i, c in enumerate(board):
            if not isinstance(c, Card):
                raise TypeError(
                    f"HUNLConfig.initial_board: expected tuple of Card, got "
                    f"element [{i}] of type {type(c).__name__} "
                    f"(value={c!r}). Use parse_board(...) or "
                    f"Card.from_str(...) to construct cards."
                )
        if isinstance(board, list):
            # Coerce list -> tuple so the frozen dataclass holds a consistent
            # immutable type. Pre-PR 31 callers that passed a list saw a list
            # stored verbatim; downstream code already tuple()s it where
            # needed, so silently normalizing here is a strict improvement.
            object.__setattr__(self, "initial_board", tuple(board))

    def _validate_initial_hole_cards(self) -> None:
        """`initial_hole_cards` must be either:
          - empty `()` for the chance-enum-at-root case, OR
          - a tuple of 2 tuples of 2 Cards each (hero pair + villain pair).
        We coerce inner lists -> tuples but require the right shape + Card
        element types. Caught loudly here so the solver doesn't crash on
        `hole_cards[player][0].rank` deep in `infoset_key`."""
        hole = self.initial_hole_cards
        if not isinstance(hole, (tuple, list)):
            raise TypeError(
                f"HUNLConfig.initial_hole_cards: expected tuple of 2 pairs "
                f"of Card (or empty tuple), got {type(hole).__name__}"
            )
        if len(hole) == 0:
            return
        if len(hole) != 2:
            raise ValueError(
                f"HUNLConfig.initial_hole_cards: expected exactly 2 pairs "
                f"(hero + villain) or empty, got {len(hole)} entries"
            )
        normalized: list[tuple[Card, Card]] = []
        for player_idx, pair in enumerate(hole):
            if not isinstance(pair, (tuple, list)):
                raise TypeError(
                    f"HUNLConfig.initial_hole_cards[{player_idx}]: expected "
                    f"pair of Card, got {type(pair).__name__}"
                )
            if len(pair) != 2:
                raise ValueError(
                    f"HUNLConfig.initial_hole_cards[{player_idx}]: expected "
                    f"2 cards, got {len(pair)}"
                )
            for card_idx, c in enumerate(pair):
                if not isinstance(c, Card):
                    raise TypeError(
                        f"HUNLConfig.initial_hole_cards[{player_idx}]"
                        f"[{card_idx}]: expected Card, got "
                        f"{type(c).__name__} (value={c!r}). Use "
                        f"Card.from_str(...) to construct cards."
                    )
            normalized.append((pair[0], pair[1]))
        # Coerce to canonical nested-tuple form if any inner list was passed.
        if any(isinstance(p, list) for p in hole) or isinstance(hole, list):
            object.__setattr__(
                self, "initial_hole_cards", (normalized[0], normalized[1])
            )

    def _validate_bet_size_fractions(self) -> None:
        """`bet_size_fractions` must be a tuple/list of positive floats."""
        fracs = self.bet_size_fractions
        if not isinstance(fracs, (tuple, list)):
            raise TypeError(
                f"HUNLConfig.bet_size_fractions: expected tuple of float, "
                f"got {type(fracs).__name__}"
            )
        for i, x in enumerate(fracs):
            if isinstance(x, bool) or not isinstance(x, (int, float)):
                raise TypeError(
                    f"HUNLConfig.bet_size_fractions[{i}]: expected float, "
                    f"got {type(x).__name__} (value={x!r})"
                )
            if x <= 0:
                raise ValueError(
                    f"HUNLConfig.bet_size_fractions[{i}] must be positive; "
                    f"got {x}"
                )
        if isinstance(fracs, list):
            object.__setattr__(
                self, "bet_size_fractions", tuple(float(x) for x in fracs)
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
        # PR 22 Fix A: honor asymmetric initial_contributions for facing-bet
        # postflop subgames. Player with less in is facing a pending bet of
        # `to_call = abs(c0 - c1)`; the other is the street aggressor. When
        # contributions are symmetric (c0 == c1), we preserve the historical
        # behavior exactly: to_call=0, street_aggressor=-1, cur_player=1 (BB).
        c0, c1 = contributions
        if c0 == c1:
            to_call = 0
            street_aggressor = -1
            postflop_first_actor = 1
        elif c0 < c1:
            # P0 has less in; P0 faces the bet, P1 is the aggressor.
            to_call = c1 - c0
            street_aggressor = 1
            postflop_first_actor = 0
        else:
            # P1 has less in; P1 faces the bet, P0 is the aggressor.
            to_call = c0 - c1
            street_aggressor = 0
            postflop_first_actor = 1
        # street_num_raises = 1 when there is a pending bet (the aggressor's
        # bet counts as one raise for raise-cap accounting), 0 otherwise.
        street_num_raises = 1 if to_call > 0 else 0
        cur_player = -1 if any(all_in_flags) or not hole else postflop_first_actor
        return HUNLState(
            hole_cards=hole,
            board=tuple(cfg.initial_board),
            street=cfg.starting_street,
            contributions=contributions,
            stacks=stacks,
            street_history=(),
            street_aggressor=street_aggressor,
            street_num_raises=street_num_raises,
            to_call=to_call,
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
        if cfg.abstraction is not None and state.street in (
            Street.FLOP,
            Street.TURN,
            Street.RIVER,
        ):
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
        # PR 22: if the next-to-act player is already all-in (stack 0), they
        # cannot act. This arises when an over-shove all-in is "called" by
        # an opponent who is already all-in for less; the excess (uncalled)
        # chips must be refunded to the over-shover and the street closes.
        if new_all_in[1 - player]:
            opp = 1 - player
            refund = max(0, contributions[player] - contributions[opp])
            if refund > 0:
                contributions[player] -= refund
                stacks[player] += refund
                # Player came off the all-in (received refund of uncalled chips).
                all_in[player] = stacks[player] == 0
            new_state_to_runout = replace(
                new_state,
                contributions=(contributions[0], contributions[1]),
                stacks=(stacks[0], stacks[1]),
                all_in=(all_in[0], all_in[1]),
                to_call=0,
            )
            return self._begin_street_transition(new_state_to_runout)
        return replace(new_state, cur_player=1 - player)

    def _apply_chance(self, state: HUNLState, action: Action) -> HUNLState:
        if not state.hole_cards:
            new_hole = _normalize_hole_action(action)
            if state.street == Street.PREFLOP:
                next_cur = 0
            else:
                # PR 22: postflop first actor depends on the bet state. With
                # symmetric contributions there is no bet to face → BB (P1)
                # acts first. With asymmetric contributions (Fix A), the
                # player with the lower contribution faces the bet and acts
                # first.
                c0, c1 = state.contributions
                next_cur = 0 if c0 < c1 else 1
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


def _serialize_hunl_config(config: HUNLConfig) -> str:
    """Dump ``config`` to a JSON string matching the Rust ``serde`` shape.

    PR 6 §6.2 — the Rust HUNL solve entry takes the config as a JSON string
    (locked decision D2: simpler than struct binding). The field set, types,
    and JSON keys are 1:1 with Agent A's ``HUNLConfig`` ``serde::Deserialize``
    derive in ``crates/cfr_core/src/hunl.rs``.

    Serializes ``initial_hole_cards`` (Agent A's ``HUNLState::initial`` reads
    them from the config for postflop subgames) and the abstraction's
    ``source_path`` + ``version`` (so the Rust side can ``load_abstraction``
    the ``.npz`` independently). ``rake_rate`` / ``rake_cap`` are always 0/0
    by ``HUNLConfig.__post_init__`` but emitted explicitly so Agent A's
    ``Deserialize`` shape stays aligned.

    f64 fields (``bet_size_fractions``) round-trip bit-exactly via
    ``json.dumps`` / ``serde_json::from_str`` per IEEE-754 invariants
    (PR 6 §9 #15).
    """
    import json

    abstraction_path: str | None = None
    abstraction_version: str | None = None
    if config.abstraction is not None:
        abstraction_path = str(config.abstraction.source_path)
        abstraction_version = str(config.abstraction.version)

    if config.initial_hole_cards:
        # Tuple-of-pairs of `Card` -> nested int-list matching Agent A's
        # `Option<[[u8; 2]; 2]>` field.
        initial_hole = [
            [card_to_int(c) for c in pair] for pair in config.initial_hole_cards
        ]
    else:
        initial_hole = None

    payload: dict[str, object] = {
        "starting_stack": int(config.starting_stack),
        "small_blind": int(config.small_blind),
        "big_blind": int(config.big_blind),
        "ante": int(config.ante),
        "starting_street": int(config.starting_street),
        "initial_board": [card_to_int(c) for c in config.initial_board],
        "initial_pot": int(config.initial_pot),
        "initial_contributions": [
            int(config.initial_contributions[0]),
            int(config.initial_contributions[1]),
        ],
        "initial_hole_cards": initial_hole,
        "preflop_raise_cap": int(config.preflop_raise_cap),
        "postflop_raise_cap": int(config.postflop_raise_cap),
        "bet_size_fractions": [float(x) for x in config.bet_size_fractions],
        "include_all_in": bool(config.include_all_in),
        "force_allin_threshold": int(config.force_allin_threshold),
        "min_bet_bb": int(config.min_bet_bb),
        "rake_rate": float(config.rake_rate),
        "rake_cap": int(config.rake_cap),
        "abstraction_path": abstraction_path,
        "abstraction_version": abstraction_version,
        # PR 8 v1.0.1: PCS exists in the Rust tier but is **not exposed**
        # from Python. The Rust HUNLConfig.use_pcs field is Rust-internal
        # for now; this serializer hard-codes False so the Python <-> Rust
        # JSON shape stays consistent. Surfacing `use_pcs` as a real Python
        # HUNLConfig field is deferred to a follow-up PR (would require
        # threading through the dataclass + validation + tests). See
        # docs/pr8_prep/audit_report.md should-fix #2 for the rationale.
        "use_pcs": False,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


__all__ = [
    "HUNLConfig",
    "HUNLPoker",
    "HUNLState",
    "Street",
    "_serialize_hunl_config",
    "default_tiny_subgame",
]
