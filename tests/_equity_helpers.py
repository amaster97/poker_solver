"""One-line equity helpers for persona / acceptance tests.

Motivation
----------
Per ``docs/poker_spots_audit_2026-05-23.md``, equity hand-waves in retest
verdicts were 2-5x off on lopsided spots (e.g., 9sTs on K-7-2 river: claimed
"10-25%", real 0-3%; AKs vs JJ on AsTc5d: spec said 27/73, real 91/9).

These helpers wrap :func:`poker_solver.equity.equity` so persona tests and
acceptance tests can assert exact numerical equity without spinning their own
boilerplate (parse hand, parse board, build list, fish out the ``.equity``
field). Behavior is identical to the underlying ``equity()`` call:

* When all hands and the remaining-board state space fit under
  ``DEFAULT_ENUM_THRESHOLD`` (100k runouts), the result is **exact** via
  enumeration. River spots, turn spots, and flop spots with two concrete
  hands all fall in this regime.
* For range-vs-hand on early streets the underlying function may auto-switch
  to Monte Carlo; the caller can still treat the returned float as a
  best-effort point estimate.

These wrappers intentionally accept string inputs (``"AhAd"``, ``"Kh7d2c"``)
to keep test code visually compact and reviewable. For ``Card``-typed inputs
use :func:`poker_solver.equity.equity` directly.
"""

from __future__ import annotations

from poker_solver.card import parse_board, parse_hand
from poker_solver.equity import equity as _equity_core
from poker_solver.range import Range


def equity_of(
    hero_hand: str,
    villain_hand: str,
    board: str = "",
    iterations: int | None = None,
) -> tuple[float, float, float]:
    """Return ``(hero_equity, villain_equity, tie_equity)`` as fractions in [0, 1].

    The first two entries are full equity shares (wins + tied-pot shares); the
    third is the *tie probability* (fraction of runouts that ended in a chop).
    Hero and villain equities each include their slice of any ties, so
    ``hero_equity + villain_equity == 1.0`` modulo float noise.

    The underlying call uses exact enumeration when feasible (river, turn, flop
    with two concrete hands all qualify). Inputs are accepted in standard
    rank-suit format (``"AhAd"``, ``"9sTs"``, ``"Kh7d2cKs5d"``); ``board`` may
    be the empty string for preflop spots.

    Args:
        hero_hand: 2-card hero hole cards, e.g. ``"AhKs"``.
        villain_hand: 2-card villain hole cards, e.g. ``"JhJd"``.
        board: 0..5 community cards as a single string. Empty string for
            preflop.
        iterations: optional MC iteration budget for the fall-through path
            (used only when enumeration is infeasible — e.g., preflop). When
            ``None``, the underlying engine default (250k) is used.

    Returns:
        Triple ``(hero_equity, villain_equity, tie_probability)``.

    Raises:
        ValueError: hand-on-board duplicate, malformed card string, or any
            other validation error from the underlying card / equity layer.
    """
    hero = parse_hand(hero_hand)
    villain = parse_hand(villain_hand)
    board_cards = parse_board(board)
    kwargs: dict[str, object] = {}
    if iterations is not None:
        kwargs["iterations"] = iterations
    results = _equity_core([hero, villain], board=board_cards, **kwargs)
    hero_eq = results[0].equity
    villain_eq = results[1].equity
    tie_pct = results[0].tie_pct
    return (hero_eq, villain_eq, tie_pct)


def equity_vs_range(
    hero_hand: str,
    villain_range: list[str],
    board: str = "",
    iterations: int | None = None,
) -> float:
    """Hero's equity against a uniform villain range. Returns hero equity in [0, 1].

    The villain range is treated as a flat (uniform-weight) set of combos.
    Combos that conflict with the hero hand or board are skipped at sample /
    enumerate time by the underlying engine.

    Args:
        hero_hand: 2-card hero hole cards, e.g. ``"AhAd"``.
        villain_range: list of 2-card combo strings, e.g. ``["JhJd", "TcTd"]``.
        board: 0..5 community cards as a single string.
        iterations: optional MC iteration budget for the fall-through path
            (used only when enumeration is infeasible). ``None`` keeps the
            engine default (250k).

    Returns:
        Hero equity as a float in [0, 1]. Note: with a multi-combo range and
        early streets, the engine may auto-switch to Monte Carlo and the
        result is a point estimate (~0.1% SE at default iterations).
    """
    if not villain_range:
        raise ValueError("villain_range must contain at least one combo")
    hero = parse_hand(hero_hand)
    board_cards = parse_board(board)
    vrange = Range()
    for combo_str in villain_range:
        vrange.add(parse_hand(combo_str))
    kwargs: dict[str, object] = {}
    if iterations is not None:
        kwargs["iterations"] = iterations
    results = _equity_core([hero, vrange], board=board_cards, **kwargs)
    return results[0].equity


def assert_equity_close(
    hero_hand: str,
    villain_hand: str,
    board: str,
    expected: float,
    tol: float = 0.01,
) -> None:
    """Assert hero's equity in the given spot matches ``expected`` within ``tol``.

    Convenience wrapper for persona / acceptance tests. Failure message
    includes the actual value, the expected value, the tolerance, and the
    fully-specified spot so the diff is debuggable from CI logs alone.

    Args:
        hero_hand: hero hole cards string.
        villain_hand: villain hole cards string.
        board: community cards string (may be empty).
        expected: expected hero equity as a fraction in [0, 1].
        tol: absolute tolerance (default 0.01 = 1 percentage point).
    """
    hero_eq, villain_eq, _tie = equity_of(hero_hand, villain_hand, board)
    if abs(hero_eq - expected) > tol:
        raise AssertionError(
            f"equity mismatch for hero={hero_hand} vs villain={villain_hand} "
            f"on board={board!r}: got hero={hero_eq:.4f} (villain={villain_eq:.4f}), "
            f"expected hero={expected:.4f} ± {tol:.4f}"
        )
