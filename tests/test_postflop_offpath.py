"""Tests for POSTFLOP off-path detection + cleaning (data layer, no GUI).

Mirrors ``tests/test_preflop_offpath.py`` but PER-COMBO, board-aware, and
STREET-BY-STREET. Most assertions use SYNTHETIC ``per_history_strategy``
dicts for determinism; one ``@pytest.mark.slow`` test runs a single small
river solve.

Board used throughout: ``2h7dTcJs5c``. Hero is OOP (acts first each street).

Node grammar reminder (verified empirically):
  * history is ``<street0>/<street1>/...`` ; within a street tokens are
    concatenated with NO separator (``x``=check, ``c``=call, ``b<amt>``=bet,
    ``r<amt>``=raise, ``A``=all-in).
  * OOP acts first each street; the actor alternates per in-street token;
    a ``/`` resets to OOP.
  * the per-history value is a positional probability LIST: index 0 is the
    passive action (check first-to-act / fold when facing a bet); when facing
    a bet index 1 is call; the rest are bet/raise sizes ascending.
"""

from __future__ import annotations

import copy

import pytest

from poker_solver.postflop_offpath import (
    REASON_CALLED_CLOSED,
    REASON_CHECKED_CLOSED,
    REASON_FOLDED,
    REASON_LOW_REACH,
    clean_off_path,
    mark_off_path,
    mark_off_path_with_reason,
)

BOARD = "2h7dTcJs5c"


def _k(hole: str, hist: str = "") -> str:
    return f"{hole}|{BOARD}||{hist}"


# --------------------------------------------------------------------------- #
# 1. Folded combo carries across streets -> off-path "folded" at a deep node;
#    an in-range combo keeps its strategy.
# --------------------------------------------------------------------------- #


def _fold_carry_fixture():
    """OOP bets root; IP raises (``b50b99``); OOP faces the raise at ``b50b99``.

    AA folds 100% there; KK calls 100% and continues to the turn
    (``b50b99c/``). The engine emits a spurious AA row at the descendant too.
    """
    return {
        _k("AcAd"): [0.0, 1.0],
        _k("KcKd"): [0.0, 1.0],
        _k("AcAd", "b50"): [0.5, 0.5],
        _k("KcKd", "b50"): [0.5, 0.5],
        _k("AcAd", "b50b99"): [1.0, 0.0],  # AA FOLDS (index 0 == fold)
        _k("KcKd", "b50b99"): [0.0, 1.0],  # KK CALLS
        _k("AcAd", "b50b99c/"): [0.4, 0.6],  # spurious AA row on the turn
        _k("KcKd", "b50b99c/"): [0.4, 0.6],
    }


def test_folded_combo_off_path_at_deep_node():
    phs = _fold_carry_fixture()
    hero_range = {"AcAd": 1.0, "KcKd": 1.0}

    # At the fold node itself, folding is AA's legitimate action -> on-path.
    here = mark_off_path_with_reason(phs, hero_range, board=BOARD, history="b50b99")
    assert here == {"AcAd": None, "KcKd": None}

    # At the deeper turn node, AA is off-path "folded" (carries across street),
    # KK keeps its strategy (it called and legitimately continues).
    deep = mark_off_path_with_reason(
        phs, hero_range, board=BOARD, history="b50b99c/"
    )
    assert deep["AcAd"] == REASON_FOLDED
    assert deep["KcKd"] is None

    boolmap = mark_off_path(phs, hero_range, board=BOARD, history="b50b99c/")
    assert boolmap == {"AcAd": True, "KcKd": False}


# --------------------------------------------------------------------------- #
# 2. WITHIN-STREET checked_closed scoping (LOAD-BEARING).
#    A combo that checked ~100% (closing the street's betting) is off-path on
#    a deeper SAME-street line, but NOT off-path on the legitimate NEXT street.
# --------------------------------------------------------------------------- #


def _checked_closed_fixture():
    """OOP first-to-act on the flop; AA checks 100% at the flop root.

    The "somehow we raised and it got back to us" SAME-street line is
    ``xb50b99`` (OOP checked, IP bet, OOP RAISED — requires OOP to NOT have
    checked-and-closed). Since AA checked 100% at the root, that same-street
    line is off-path "checked_closed".

    But ``xx/`` (check-check closes the flop -> turn) is the LEGITIMATE
    continuation: AA's flop check is exactly right, so AA must be ON-path on
    the turn root ``xx/``.
    """
    return {
        # flop root: OOP first-to-act [check, bet50]; AA checks 100%, QQ bets.
        _k("AcAd"): [1.0, 0.0],
        _k("QcQd"): [0.0, 1.0],
        # xb50: OOP faces IP's bet [fold, call, raise]; rows present for both.
        _k("AcAd", "xb50"): [0.0, 0.0, 1.0],  # spurious AA raise row
        _k("QcQd", "xb50"): [0.0, 0.0, 1.0],
        # xb50b99: deeper SAME-street line (OOP raised). spurious AA row.
        _k("AcAd", "xb50b99"): [0.5, 0.5],
        _k("QcQd", "xb50b99"): [0.5, 0.5],
        # xx/: check-check closed the flop -> turn root (OOP first). LEGIT.
        _k("AcAd", "xx/"): [0.3, 0.7],
        _k("QcQd", "xx/"): [0.3, 0.7],
    }


def test_checked_closed_within_street_scoping():
    phs = _checked_closed_fixture()
    hero_range = {"AcAd": 1.0, "QcQd": 1.0}

    # SAME-street deeper line where AA "raised" after checking 100% -> off-path
    # "checked_closed".
    same = mark_off_path_with_reason(
        phs, hero_range, board=BOARD, history="xb50b99"
    )
    assert same["AcAd"] == REASON_CHECKED_CLOSED

    # NEXT street: check-check legitimately continues. AA must NOT be off-path.
    nxt = mark_off_path_with_reason(phs, hero_range, board=BOARD, history="xx/")
    assert nxt["AcAd"] is None


def test_called_closed_within_street_scoping():
    """A call that closed the street off-paths a deeper SAME-street raise.

    A call always ENDS a street, so the only deeper SAME-street decision is a
    phantom the engine emits for the closed combo. So that the EARLIEST block
    is the call (not a root check), the hero BETS the flop first: OOP decisions
    on ``b50 r99 c b150 r200`` are idx0 (``b50``, bet — no checked_closed),
    idx2 (``c`` = call, closing), idx4 (``r200``). The phantom
    ``b50r99cb150r200`` has the hero acting AGAIN same-street after its 100%
    call -> ``called_closed``. The legit continuation ``b50r99c/`` (call closes
    -> turn) must stay ON-path.
    """
    phs = {
        # flop root: OOP first [check, bet50]; AA bets 50.
        _k("AcAd"): [0.0, 1.0],
        # b50r99: OOP faces IP's raise [fold, call, reraise]; AA CALLS 100%.
        _k("AcAd", "b50r99"): [0.0, 1.0, 0.0],
        # b50r99cb150: phantom OOP-facing node (gating node for the idx4 walk).
        _k("AcAd", "b50r99cb150"): [0.0, 0.5, 0.5],
        # b50r99cb150r200: phantom deeper SAME-street (OOP "re-raised").
        _k("AcAd", "b50r99cb150r200"): [0.5, 0.5],
        # b50r99c/: AA called and closed -> turn root (LEGIT continuation).
        _k("AcAd", "b50r99c/"): [0.3, 0.7],
    }
    hero_range = {"AcAd": 1.0}

    same = mark_off_path_with_reason(
        phs, hero_range, board=BOARD, history="b50r99cb150r200"
    )
    assert same["AcAd"] == REASON_CALLED_CLOSED

    nxt = mark_off_path_with_reason(
        phs, hero_range, board=BOARD, history="b50r99c/"
    )
    assert nxt["AcAd"] is None


# --------------------------------------------------------------------------- #
# 3. All-in carry-over (across streets).
# --------------------------------------------------------------------------- #


def test_all_in_carries_across_streets():
    phs = {
        _k("AcAd"): [0.0, 1.0],
        # b50: IP node (skip for hero=OOP — not a gating node).
        _k("AcAd", "b50"): [0.0, 1.0],
        # b50r99: OOP faces a raise [fold, call, reraise]; AA shoves (the
        # history records the shove as an ``A`` token next).
        _k("AcAd", "b50r99"): [0.0, 0.0, 1.0],
        # b50r99A: the all-in token; deeper node where AA already committed.
        _k("AcAd", "b50r99A"): [0.5, 0.5],
    }
    hero_range = {"AcAd": 1.0}
    out = mark_off_path_with_reason(
        phs, hero_range, board=BOARD, history="b50r99A"
    )
    assert out["AcAd"] == "all_in"


# --------------------------------------------------------------------------- #
# 4. Board-blocked combo -> reach 0 -> off-path.
# --------------------------------------------------------------------------- #


def test_board_blocked_combo_off_path():
    # ``Tc`` is on the board (``2h7dTcJs5c``); a combo holding it is impossible.
    phs = {
        _k("AcAd"): [0.0, 1.0],
        _k("TcTd"): [0.0, 1.0],  # blocked: Tc on board
    }
    hero_range = {"AcAd": 1.0, "TcTd": 1.0}
    out = mark_off_path_with_reason(phs, hero_range, board=BOARD, history="")
    assert out["TcTd"] == REASON_LOW_REACH
    assert out["AcAd"] is None
    # Board may also be passed as a token sequence.
    out2 = mark_off_path_with_reason(
        phs,
        hero_range,
        board=["2h", "7d", "Tc", "Js", "5c"],
        history="",
    )
    assert out2["TcTd"] == REASON_LOW_REACH


# --------------------------------------------------------------------------- #
# 5. low_reach: a near-zero-reach combo is off-path at a deep node.
# --------------------------------------------------------------------------- #


def test_low_reach_off_path():
    phs = {
        # root: OOP first [check, bet50]. AA bets, junk checks (never bets).
        _k("AcAd"): [0.0, 1.0],
        _k("9c8c"): [0.999, 0.001],  # bets ~0.1% -> tiny reach down the bet line
        # b50 nodes (IP faces bet — skip for hero). Present so the walk to the
        # next OOP node is computable.
        _k("AcAd", "b50"): [0.0, 1.0],
        _k("9c8c", "b50"): [0.0, 1.0],
        # b50b99: OOP faces a raise. Both rows present.
        _k("AcAd", "b50b99"): [0.0, 1.0],
        _k("9c8c", "b50b99"): [0.0, 1.0],
    }
    hero_range = {"AcAd": 1.0, "9c8c": 1.0}
    out = mark_off_path_with_reason(
        phs, hero_range, board=BOARD, history="b50b99"
    )
    # AA reached the bet line at ~1.0; 9c8c at ~0.001 (well below 0.5%).
    assert out["AcAd"] is None
    assert out["9c8c"] == REASON_LOW_REACH


# --------------------------------------------------------------------------- #
# 6. clean_off_path: off-path -> fold=1.0; on-path untouched; INPUT NOT MUTATED.
# --------------------------------------------------------------------------- #


def test_clean_off_path_folds_and_does_not_mutate_input():
    phs = _fold_carry_fixture()
    hero_range = {"AcAd": 1.0, "KcKd": 1.0}

    snapshot = copy.deepcopy(phs)
    cleaned = clean_off_path(phs, hero_range, board=BOARD)

    # INPUT NOT MUTATED — byte-for-byte intact.
    assert phs == snapshot

    # Off-path AA at the deep turn node -> index 0 = 1.0, rest 0.0.
    assert cleaned[_k("AcAd", "b50b99c/")] == [1.0, 0.0]
    # On-path KK at the deep node -> untouched.
    assert cleaned[_k("KcKd", "b50b99c/")] == [0.4, 0.6]
    # Result is a distinct object from the input.
    assert cleaned is not phs


def test_clean_off_path_returns_new_object():
    phs = {_k("AcAd"): [0.0, 1.0]}
    hero_range = {"AcAd": 1.0}
    cleaned = clean_off_path(phs, hero_range, board=BOARD)
    assert cleaned is not phs
    cleaned[_k("AcAd")][0] = 9.0  # mutate the copy
    assert phs[_k("AcAd")] == [0.0, 1.0]  # input unaffected


# --------------------------------------------------------------------------- #
# 7. FAIL-SAFE: a missing gating ancestor -> mark NOTHING for that node.
# --------------------------------------------------------------------------- #


def test_fail_safe_when_gating_node_missing():
    # Deep node present but its OOP-root ancestor is absent -> can't compute
    # reach -> mark nothing (every combo None).
    phs = {
        _k("AcAd", "b50b99"): [1.0, 0.0],
        _k("KcKd", "b50b99"): [0.0, 1.0],
        # NOTE: root "" missing -> walk fails safe.
    }
    hero_range = {"AcAd": 1.0, "KcKd": 1.0}
    out = mark_off_path_with_reason(
        phs, hero_range, board=BOARD, history="b50b99"
    )
    assert out == {"AcAd": None, "KcKd": None}


# --------------------------------------------------------------------------- #
# 7b. API accessor: per_history_strategy_view default cleaned; clean=False raw;
#     raw .per_history_strategy unchanged after BOTH calls (raw-untouched).
# --------------------------------------------------------------------------- #


def test_per_history_strategy_view_default_clean_and_raw_untouched():
    from poker_solver.range_aggregator import RangeVsRangeNashResult

    phs = _fold_carry_fixture()
    snapshot = copy.deepcopy(phs)
    res = RangeVsRangeNashResult(per_history_strategy=phs)
    hero_range = {"AcAd": 1.0, "KcKd": 1.0}

    # Default cleaned: off-path AA at the deep node -> folded row.
    cleaned = res.per_history_strategy_view(hero_range=hero_range)
    assert cleaned[_k("AcAd", "b50b99c/")] == [1.0, 0.0]
    assert cleaned[_k("KcKd", "b50b99c/")] == [0.4, 0.6]

    # clean=False: raw projection, off-path noise intact.
    raw = res.per_history_strategy_view(clean=False, hero_range=hero_range)
    assert raw[_k("AcAd", "b50b99c/")] == [0.4, 0.6]

    # RAW ATTRIBUTE UNCHANGED after BOTH calls (the proof).
    assert res.per_history_strategy == snapshot

    # clean=False returns a per-row copy, not the attribute's own lists.
    raw[_k("AcAd", "b50b99c/")][0] = 9.0
    assert res.per_history_strategy[_k("AcAd", "b50b99c/")] == [0.4, 0.6]


def test_per_history_strategy_view_default_hero_range_uniform():
    """With no explicit hero_range the view still cleans (uniform weights)."""
    from poker_solver.range_aggregator import RangeVsRangeNashResult

    phs = _fold_carry_fixture()
    res = RangeVsRangeNashResult(per_history_strategy=phs)
    cleaned = res.per_history_strategy_view()  # no hero_range
    # AA still off-path "folded" at the deep node under uniform weights.
    assert cleaned[_k("AcAd", "b50b99c/")] == [1.0, 0.0]


# --------------------------------------------------------------------------- #
# 8. ONE small real river solve smoke: cleaning is raw-safe + a board-blocked
#    combo is off-path. (Single small solve, within machine-safety limits.)
# --------------------------------------------------------------------------- #


def _river_config():
    from poker_solver.card import Card
    from poker_solver.hunl import HUNLConfig, Street

    board = tuple(Card.from_str(c) for c in ("2h", "7d", "Tc", "Js", "5c"))
    return HUNLConfig(
        starting_stack=4000,
        small_blind=50,
        big_blind=100,
        ante=0,
        starting_street=Street.RIVER,
        initial_board=board,
        initial_pot=2000,
        initial_contributions=(1000, 1000),
        initial_hole_cards=(),
        postflop_raise_cap=1,
        bet_size_fractions=(0.75,),
        include_all_in=False,
    )


@pytest.mark.slow
def test_real_river_solve_smoke():
    """A single small river solve: cleaning never mutates the raw mapping and a
    board-blocked combo is off-path; row schemas are preserved."""
    from poker_solver.range_aggregator import solve_range_vs_range_nash

    cfg = _river_config()
    res = solve_range_vs_range_nash(
        cfg,
        hero_range=["AA", "KK", "QQ"],
        villain_range=["JJ", "TT", "99"],
        iterations=120,
        hero_player=1,  # hero OOP (acts first postflop)
        compute_exploitability_at_end=False,
    )
    phs = res.per_history_strategy
    assert phs, "solve produced no per_history_strategy"

    board_str = "2h7dTcJs5c"
    root_combos = [
        k.split("|", 1)[0] for k in phs if k.endswith(f"|{board_str}||")
    ]
    hero_range = {c: 1.0 for c in root_combos}

    snapshot = copy.deepcopy(phs)
    cleaned = res.per_history_strategy_view(
        hero_range=hero_range, hero_is_oop=True
    )

    # Raw mapping NEVER mutated by the cleaned view.
    assert phs == snapshot

    # A combo holding a board card (e.g. one with Tc) is off-path at the root.
    blocked = [c for c in root_combos if "Tc" in {c[:2], c[2:4]}]
    if blocked:
        marks = mark_off_path(phs, hero_range, board=board_str, history="")
        for c in blocked:
            assert marks[c] is True

    # Cleaning preserves row lengths (schema) for every key.
    for key, row in cleaned.items():
        assert len(row) == len(phs[key])
