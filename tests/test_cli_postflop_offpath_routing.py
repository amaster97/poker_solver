"""CLI routing: chained-solve JSON emits postflop per_history off-path-cleaned
by default, raw under --raw-offpath. Data-layer only (no real solve).

The chained subcommand stores each postflop subgame as a
:class:`RangeVsRangeNashResult` (so it inherits the
``per_history_strategy_view`` accessor); ``_render_chained_json`` routes it
through the off-path cleaner by default. These tests drive
``_render_chained_json`` directly with a synthetic result — no engine solve.
"""

from __future__ import annotations

import argparse
import io
import json
from contextlib import redirect_stdout

import poker_solver.cli as cli
from poker_solver.chained import ChainedSolveResult
from poker_solver.range_aggregator import RangeVsRangeNashResult

BOARD = "2h7dTc"


def _k(hole: str, hist: str = "") -> str:
    return f"{hole}|{BOARD}||{hist}"


def _chained_result() -> ChainedSolveResult:
    # OOP (defender) folds AA at the raise node, so AA is off-path "folded" on
    # the deeper turn line; KK calls and continues.
    phs = {
        _k("AcAd"): [0.0, 1.0],
        _k("KcKd"): [0.0, 1.0],
        _k("AcAd", "b50"): [0.5, 0.5],
        _k("KcKd", "b50"): [0.5, 0.5],
        _k("AcAd", "b50b99"): [1.0, 0.0],  # AA folds
        _k("KcKd", "b50b99"): [0.0, 1.0],  # KK calls
        _k("AcAd", "b50b99c/"): [0.4, 0.6],  # spurious AA turn row
        _k("KcKd", "b50b99c/"): [0.4, 0.6],
    }
    pf = RangeVsRangeNashResult(
        per_history_strategy=phs,
        position="defender",  # hero OOP postflop
    )
    pre = RangeVsRangeNashResult()
    return ChainedSolveResult(
        preflop_result=pre,
        continuation_ranges={},
    )


def _args(raw_offpath: bool) -> argparse.Namespace:
    return argparse.Namespace(
        raw_offpath=raw_offpath,
        hero_range="AA,KK",
        villain_range="JJ,TT",
        stacks=100,
        preflop_iterations=10,
        postflop_iterations=10,
    )


def _emit(raw_offpath: bool) -> dict:
    result = _chained_result()
    phs = {
        _k("AcAd"): [0.0, 1.0],
        _k("KcKd"): [0.0, 1.0],
        _k("AcAd", "b50"): [0.5, 0.5],
        _k("KcKd", "b50"): [0.5, 0.5],
        _k("AcAd", "b50b99"): [1.0, 0.0],
        _k("KcKd", "b50b99"): [0.0, 1.0],
        _k("AcAd", "b50b99c/"): [0.4, 0.6],
        _k("KcKd", "b50b99c/"): [0.4, 0.6],
    }
    pf = RangeVsRangeNashResult(per_history_strategy=phs, position="defender")
    postflop_solves = {("open", "call"): pf}
    buf = io.StringIO()
    with redirect_stdout(buf):
        cli._render_chained_json(
            args=_args(raw_offpath),
            board_cards=[],
            result=result,
            postflop_solves=postflop_solves,
        )
    return json.loads(buf.getvalue())


def test_chained_json_postflop_cleaned_by_default():
    payload = _emit(raw_offpath=False)
    phs = payload["postflop_solves"]["open call"]["per_history_strategy"]
    # AA off-path "folded" at the deep turn node -> folded row.
    assert phs[_k("AcAd", "b50b99c/")] == [1.0, 0.0]
    # KK on-path -> untouched.
    assert phs[_k("KcKd", "b50b99c/")] == [0.4, 0.6]


def test_chained_json_postflop_raw_with_flag():
    payload = _emit(raw_offpath=True)
    phs = payload["postflop_solves"]["open call"]["per_history_strategy"]
    # Raw: AA's spurious turn row is preserved.
    assert phs[_k("AcAd", "b50b99c/")] == [0.4, 0.6]


def test_chained_json_does_not_mutate_source():
    phs = {
        _k("AcAd"): [0.0, 1.0],
        _k("AcAd", "b50"): [0.5, 0.5],
        _k("AcAd", "b50b99"): [1.0, 0.0],
        _k("AcAd", "b50b99c/"): [0.4, 0.6],
    }
    pf = RangeVsRangeNashResult(per_history_strategy=phs, position="defender")
    before = {k: list(v) for k, v in pf.per_history_strategy.items()}
    buf = io.StringIO()
    with redirect_stdout(buf):
        cli._render_chained_json(
            args=_args(raw_offpath=False),
            board_cards=[],
            result=_chained_result(),
            postflop_solves={("open", "call"): pf},
        )
    assert pf.per_history_strategy == before
