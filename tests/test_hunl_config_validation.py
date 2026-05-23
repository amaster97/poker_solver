"""PR 31 (task #185) — type validation at the `HUNLConfig` dataclass boundary.

Background: W2.3 Sarah retest crashed with
`AttributeError: 'int' object has no attribute 'rank'` deep inside the
per-hand solver. Root cause: a caller passed
`initial_board=(int, int, int)` (card indices) where the field expects
`tuple[Card, ...]`. The dataclass silently accepted the wrong type and
the crash surfaced many layers down with a useless stacktrace.

This test file locks the new `__post_init__` type validation: wrong-type
construction must raise `TypeError`/`ValueError` with a helpful, actionable
message at the dataclass boundary, not silently propagate.

PR 22's Fix B already validated negative / out-of-stack
`initial_contributions` (re-exercised here as a regression guard, not
re-asserted in the new code).
"""

from __future__ import annotations

import pytest

from poker_solver import (
    Card,
    HUNLConfig,
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
# Valid constructions still pass (regression guard against over-validation)
# ---------------------------------------------------------------------------


def test_default_construction_ok():
    """Bare `HUNLConfig()` must continue to work (defaults are valid)."""
    cfg = HUNLConfig()
    assert cfg.starting_stack == 10_000
    assert cfg.initial_board == ()
    assert cfg.initial_hole_cards == ()


def test_full_subgame_construction_ok():
    """Canonical postflop subgame config — exercise every typed field."""
    cfg = HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.FLOP,
        initial_board=_flop_board(),
        initial_pot=1000,
        initial_contributions=(500, 500),
        initial_hole_cards=_flop_hole(),
    )
    assert isinstance(cfg.initial_board, tuple)
    assert all(isinstance(c, Card) for c in cfg.initial_board)
    assert isinstance(cfg.initial_hole_cards, tuple)
    assert len(cfg.initial_hole_cards) == 2


def test_list_initial_board_coerced_to_tuple():
    """Lists are reasonable user input; coerce silently to tuple so the
    frozen dataclass holds a consistent immutable type. Pre-PR 31 callers
    that passed a list got a list stored verbatim, so this is a strict
    improvement."""
    cfg = HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.FLOP,
        initial_board=list(_flop_board()),  # list, not tuple
        initial_pot=1000,
        initial_contributions=(500, 500),
    )
    assert isinstance(cfg.initial_board, tuple)
    assert cfg.initial_board == _flop_board()


def test_list_initial_hole_cards_coerced_to_tuple():
    """Same coercion applies to `initial_hole_cards`."""
    hole = _flop_hole()
    hole_as_lists = [list(hole[0]), list(hole[1])]  # list of lists
    cfg = HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.FLOP,
        initial_board=_flop_board(),
        initial_pot=1000,
        initial_contributions=(500, 500),
        initial_hole_cards=hole_as_lists,
    )
    assert isinstance(cfg.initial_hole_cards, tuple)
    assert cfg.initial_hole_cards == hole


# ---------------------------------------------------------------------------
# initial_board — the W2.3 crash mode
# ---------------------------------------------------------------------------


def test_initial_board_with_int_elements_raises_typeerror():
    """The W2.3 Sarah retest crash mode: caller passed int card indices
    where Cards were expected. Must fail LOUDLY at dataclass construction,
    not silently survive and crash deep in the solver."""
    with pytest.raises(TypeError, match="initial_board.*expected tuple of Card"):
        HUNLConfig(
            starting_stack=10_000,
            starting_street=Street.FLOP,
            initial_board=(40, 41, 42),  # int card indices, NOT Cards
            initial_pot=1000,
            initial_contributions=(500, 500),
        )


def test_initial_board_with_int_message_is_helpful():
    """The error message must guide the user to the fix
    (`parse_board` / `Card.from_str`), not just say 'wrong type'."""
    with pytest.raises(TypeError, match="parse_board|Card.from_str"):
        HUNLConfig(
            starting_stack=10_000,
            starting_street=Street.FLOP,
            initial_board=(40, 41, 42),
            initial_pot=1000,
            initial_contributions=(500, 500),
        )


def test_initial_board_with_string_elements_raises():
    """Strings (e.g. `'Qd'`) are common user input but must be parsed
    via `Card.from_str` first — the dataclass holds `Card`, not str."""
    with pytest.raises(TypeError, match="initial_board"):
        HUNLConfig(
            starting_stack=10_000,
            starting_street=Street.FLOP,
            initial_board=("Qd", "7c", "2h"),  # strings, NOT Cards
            initial_pot=1000,
            initial_contributions=(500, 500),
        )


def test_initial_board_not_a_sequence_raises():
    """A bare int (instead of a tuple/list) is a likely typo."""
    with pytest.raises(TypeError, match="initial_board"):
        HUNLConfig(
            starting_stack=10_000,
            starting_street=Street.FLOP,
            initial_board=42,  # type: ignore[arg-type]  # scalar, not tuple
            initial_pot=1000,
            initial_contributions=(500, 500),
        )


# ---------------------------------------------------------------------------
# initial_hole_cards — wrong shape / wrong type
# ---------------------------------------------------------------------------


def test_initial_hole_cards_with_int_elements_raises():
    """Nested ints where Cards were expected. Surfaces as a clean TypeError
    at construction, not a downstream `'int' object has no attribute rank'`."""
    with pytest.raises(TypeError, match="initial_hole_cards"):
        HUNLConfig(
            starting_stack=10_000,
            starting_street=Street.FLOP,
            initial_board=_flop_board(),
            initial_pot=1000,
            initial_contributions=(500, 500),
            initial_hole_cards=((40, 41), (42, 43)),  # type: ignore[arg-type]
        )


def test_initial_hole_cards_with_wrong_player_count_raises():
    """Must be exactly 2 pairs (hero + villain) or empty."""
    with pytest.raises(ValueError, match="exactly 2"):
        HUNLConfig(
            starting_stack=10_000,
            starting_street=Street.FLOP,
            initial_board=_flop_board(),
            initial_pot=1000,
            initial_contributions=(500, 500),
            initial_hole_cards=(_flop_hole()[0],),  # type: ignore[arg-type]  # only one pair
        )


def test_initial_hole_cards_with_wrong_cards_per_pair_raises():
    """Each pair must contain exactly 2 cards."""
    one_card_pair = (Card.from_str("Kh"),)
    other_pair = (Card.from_str("As"), Card.from_str("Ad"))
    with pytest.raises(ValueError, match="initial_hole_cards"):
        HUNLConfig(
            starting_stack=10_000,
            starting_street=Street.FLOP,
            initial_board=_flop_board(),
            initial_pot=1000,
            initial_contributions=(500, 500),
            initial_hole_cards=(one_card_pair, other_pair),  # type: ignore[arg-type]
        )


def test_initial_hole_cards_pair_not_a_sequence_raises():
    """A pair must be a tuple/list, not a bare scalar."""
    with pytest.raises(TypeError, match="initial_hole_cards"):
        HUNLConfig(
            starting_stack=10_000,
            starting_street=Street.FLOP,
            initial_board=_flop_board(),
            initial_pot=1000,
            initial_contributions=(500, 500),
            initial_hole_cards=(42, (Card.from_str("As"), Card.from_str("Ad"))),  # type: ignore[arg-type]
        )


def test_empty_initial_hole_cards_still_accepted():
    """Empty `()` is the chance-enum-at-root case (no fixed hole cards).
    Must NOT be rejected by the new validation."""
    cfg = HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.FLOP,
        initial_board=_flop_board(),
        initial_pot=1000,
        initial_contributions=(500, 500),
        initial_hole_cards=(),
    )
    assert cfg.initial_hole_cards == ()


# ---------------------------------------------------------------------------
# bet_size_fractions
# ---------------------------------------------------------------------------


def test_bet_size_fractions_with_negative_raises():
    """Negative bet fractions are nonsensical (you can't bet negative pot)."""
    with pytest.raises(ValueError, match="bet_size_fractions"):
        HUNLConfig(bet_size_fractions=(0.5, -1.0, 2.0))


def test_bet_size_fractions_with_zero_raises():
    """A 0-fraction bet means betting nothing — degenerate."""
    with pytest.raises(ValueError, match="bet_size_fractions"):
        HUNLConfig(bet_size_fractions=(0.5, 0.0, 2.0))


def test_bet_size_fractions_with_string_raises():
    """Strings are a common typo (`bet_size_fractions=("0.5", "1.0")`)."""
    with pytest.raises(TypeError, match="bet_size_fractions"):
        HUNLConfig(bet_size_fractions=("0.5", "1.0"))  # type: ignore[arg-type]


def test_bet_size_fractions_list_coerced_to_tuple():
    """Lists are reasonable user input; coerce silently to tuple of floats."""
    cfg = HUNLConfig(bet_size_fractions=[0.5, 1.0, 2.0])  # list, not tuple
    assert isinstance(cfg.bet_size_fractions, tuple)
    assert cfg.bet_size_fractions == (0.5, 1.0, 2.0)


# ---------------------------------------------------------------------------
# Scalar chip fields
# ---------------------------------------------------------------------------


def test_starting_stack_zero_raises():
    """A 0-stack game is degenerate (no chips behind)."""
    with pytest.raises(ValueError, match="starting_stack"):
        HUNLConfig(starting_stack=0)


def test_starting_stack_negative_raises():
    """Negative stack is a likely sign-error / off-by-one upstream."""
    with pytest.raises(ValueError, match="starting_stack"):
        HUNLConfig(starting_stack=-1000)


def test_starting_stack_wrong_type_raises():
    """Float starting_stack would silently break integer-chip invariant."""
    with pytest.raises(TypeError, match="starting_stack"):
        HUNLConfig(starting_stack=10_000.0)  # type: ignore[arg-type]


def test_big_blind_zero_raises():
    """0 BB is degenerate — utilities normalize by BB."""
    with pytest.raises(ValueError, match="big_blind"):
        HUNLConfig(big_blind=0)


def test_big_blind_wrong_type_raises():
    with pytest.raises(TypeError, match="big_blind"):
        HUNLConfig(big_blind="100")  # type: ignore[arg-type]


def test_small_blind_negative_raises():
    with pytest.raises(ValueError, match="small_blind"):
        HUNLConfig(small_blind=-50)


def test_ante_negative_raises():
    with pytest.raises(ValueError, match="ante"):
        HUNLConfig(ante=-10)


def test_initial_pot_negative_raises():
    """At preflop, initial_pot must be 0 anyway, but the validation should
    catch negative values cleanly at the type-check stage."""
    with pytest.raises(ValueError, match="initial_pot"):
        HUNLConfig(initial_pot=-100)


def test_bool_rejected_for_int_fields():
    """`bool` is a subclass of `int` in Python — accidentally passing
    True/False where chips/blinds are expected must NOT silently coerce."""
    with pytest.raises(TypeError, match="starting_stack"):
        HUNLConfig(starting_stack=True)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# PR 22 Fix B regression guards (negative contributions; over-stack)
# ---------------------------------------------------------------------------


def test_pr22_negative_contribution_still_raises():
    """PR 22 Fix B already validated negative contributions; lock here so
    the new PR 31 ordering doesn't accidentally bypass it."""
    with pytest.raises(ValueError, match="non-negative"):
        HUNLConfig(
            starting_stack=10_000,
            starting_street=Street.FLOP,
            initial_board=_flop_board(),
            initial_pot=400,
            initial_contributions=(-100, 500),
        )


def test_pr22_contribution_exceeds_stack_still_raises():
    """PR 22 Fix B: contribution > starting_stack would imply negative
    chips behind. Re-locked here."""
    with pytest.raises(ValueError, match="exceed"):
        HUNLConfig(
            starting_stack=1000,
            starting_street=Street.FLOP,
            initial_board=_flop_board(),
            initial_pot=1500,
            initial_contributions=(1500, 0),
        )
