"""Command-line interface for poker_solver."""

from __future__ import annotations

import argparse
import random
import sys
from dataclasses import replace
from pathlib import Path
from typing import Union

from poker_solver.card import Card, parse_board, parse_hand
from poker_solver.equity import equity
from poker_solver.games import Game, KuhnPoker, LeducPoker
from poker_solver.hunl import HUNLPoker, default_tiny_subgame
from poker_solver.range import Range, parse_range
from poker_solver.solver import solve

HandInput = Union[list[Card], Range]


def _parse_spec(spec: str) -> HandInput:
    s = spec.strip()
    if not s:
        raise ValueError("Empty hand spec")
    if any(ch in s for ch in (",", "+", "-")):
        return parse_range(s)
    try:
        return parse_hand(s)
    except ValueError:
        return parse_range(s)


def _format_spec(spec: str, parsed: HandInput) -> str:
    if isinstance(parsed, Range):
        return f"{spec} ({len(parsed)} combos)"
    return spec


def _cmd_equity(args: argparse.Namespace) -> int:
    parsed = [_parse_spec(s) for s in args.hands]
    board = parse_board(args.board) if args.board else []
    rng = random.Random(args.seed) if args.seed is not None else random.Random()

    results = equity(parsed, board=board, iterations=args.iterations, rng=rng)

    label_width = max(len(_format_spec(s, p)) for s, p in zip(args.hands, parsed))
    print(
        f"Iterations: {results[0].iterations}"
        + (f"   Board: {' '.join(str(c) for c in board)}" if board else "")
    )
    print()
    for i, (spec, p, r) in enumerate(zip(args.hands, parsed, results), start=1):
        label = _format_spec(spec, p)
        print(
            f"Hand {i}: {label:<{label_width}}  "
            f"win {r.win_pct:6.2%}  tie {r.tie_pct:6.2%}  equity {r.equity:6.2%}"
        )
    return 0


def _build_kuhn(args: argparse.Namespace) -> Game:
    del args
    return KuhnPoker()


def _build_leduc(args: argparse.Namespace) -> Game:
    del args
    return LeducPoker()


def _build_hunl_with_args(args: argparse.Namespace) -> Game:
    mode = getattr(args, "hunl_mode", "tiny_subgame")
    if mode == "tiny_subgame":
        config = default_tiny_subgame()
    elif mode == "full":
        raise NotImplementedError(
            "Full HUNL solve requires card abstraction (PR 4) + scalable "
            "solver (PR 5). Use --hunl-mode tiny_subgame for a small exercise."
        )
    else:
        raise ValueError(f"Unknown --hunl-mode: {mode!r}")

    abstraction_path = getattr(args, "abstraction", None)
    if abstraction_path:
        # Load once to grab the version, then attach an `AbstractionRef`
        # (lightweight pointer; runtime LRU-caches the loaded tables).
        from poker_solver.abstraction.buckets import (
            AbstractionRef,
            load_abstraction,
        )

        path = Path(abstraction_path)
        loaded = load_abstraction(path)
        version = str(
            loaded.metadata.get(
                "version", f"v{loaded.metadata.get('schema_version', 1)}"
            )
        )
        ref = AbstractionRef(source_path=str(path.resolve()), version=version)
        config = replace(config, abstraction=ref)
    return HUNLPoker(config)


def _cmd_precompute_abstraction(args: argparse.Namespace) -> int:
    from poker_solver.abstraction.precompute import build_abstraction
    from poker_solver.hunl import Street, default_tiny_subgame

    flop_count, turn_count, river_count = (
        int(x) for x in args.bucket_counts.split(",")
    )
    street_map = {
        "flop": Street.FLOP,
        "turn": Street.TURN,
        "river": Street.RIVER,
    }
    if args.street == "all":
        streets: tuple[Street, ...] = (Street.FLOP, Street.TURN, Street.RIVER)
    else:
        streets = (street_map[args.street],)
    out_path = Path(args.output)

    # CLI autosize coupling: when ``--mc-iterations`` is small, build_abstraction
    # autosizes ``max_boards_per_street`` (default 8) and would otherwise truncate
    # away the high-rank board ``default_tiny_subgame`` uses (As 7c 2d Kh 5s).
    # Force-include the subgame board + hole cards so the CLI smoke test that
    # follows up with ``solve --abstraction`` can look them up.
    required_boards = None
    required_hands = None
    if args.mc_iterations < 5_000:
        subgame = default_tiny_subgame()
        required_boards = [subgame.initial_board]
        required_hands = [subgame.initial_hole_cards[0], subgame.initial_hole_cards[1]]

    build_abstraction(
        out_path=out_path,
        bucket_counts=(flop_count, turn_count, river_count),
        seed=args.seed,
        H=args.feature_bins,
        max_iter=args.max_iter,
        streets=streets,
        flop_mode=args.flop_mode,
        mc_iterations=args.mc_iterations,
        progress=True,
        max_boards_per_street=getattr(args, "max_boards", None),
        required_boards=required_boards,
        required_hands=required_hands,
    )
    print(f"Wrote abstraction to {out_path}")
    return 0


_GAMES = {
    "kuhn": _build_kuhn,
    "leduc": _build_leduc,
    "hunl": _build_hunl_with_args,
}


def _cmd_solve(args: argparse.Namespace) -> int:
    game = _GAMES[args.game](args)
    result = solve(game, iterations=args.iterations, backend=args.backend)

    print(f"Game:        {args.game}")
    print(f"Backend:     {result.backend}")
    print(f"Iterations:  {result.iterations}")
    print(f"Game value:  {result.game_value:+.6f} (P1 perspective)")
    last_exp = (
        result.exploitability_history[-1]
        if result.exploitability_history
        else float("nan")
    )
    print(f"Exploitability (final): {last_exp:.6f}")
    print()
    print("Average strategy:")
    print(f"  {'infoset':<8}  {'actions':<24}")
    for key in sorted(result.average_strategy.keys()):
        probs = result.average_strategy[key]
        action_str = "  ".join(f"{p:.4f}" for p in probs)
        print(f"  {key:<8}  {action_str}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="poker-solver",
        description="Texas Hold'em equity + GTO solver",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    eq = sub.add_parser("equity", help="Compute equity for two or more hands")
    eq.add_argument(
        "hands",
        nargs="+",
        help="Hand specs: '%(prog)s AhKh QdQc' or a range like 'AA,KK-TT,AKs'",
    )
    eq.add_argument(
        "--board",
        default="",
        help="Community cards, e.g. '2h7h9d' for a flop (0-5 cards)",
    )
    eq.add_argument(
        "-n",
        "--iterations",
        type=int,
        default=250_000,
        help=(
            "Monte Carlo iterations (default: 250000, ~0.1%% SE per hand). "
            "Ignored when the exact enumeration path is taken — concrete hands "
            "with a small remaining-board space (flop/turn/river) are solved "
            "exactly regardless of this value."
        ),
    )
    eq.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible runs",
    )
    eq.set_defaults(func=_cmd_equity)

    sv = sub.add_parser("solve", help="Solve a poker game to equilibrium via CFR")
    sv.add_argument(
        "--game",
        choices=sorted(_GAMES.keys()),
        required=True,
        help="Which game to solve (kuhn, leduc, hunl)",
    )
    sv.add_argument(
        "--hunl-mode",
        choices=("tiny_subgame", "full"),
        default="tiny_subgame",
        help=(
            "HUNL mode: tiny_subgame (default, river-only fixture) or full "
            "(raises NotImplementedError; full HUNL solve lands in PR 5)."
        ),
    )
    sv.add_argument(
        "-n",
        "--iterations",
        type=int,
        default=50_000,
        help="DCFR iterations (default: 50000)",
    )
    sv.add_argument(
        "--backend",
        choices=("python", "rust"),
        default="python",
        help="Solver backend: python (reference) or rust (production). Default: python.",
    )
    sv.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed (forward-compat; vanilla DCFR is deterministic)",
    )
    sv.add_argument(
        "--abstraction",
        type=str,
        default=None,
        help=(
            "Path to an abstraction .npz file. When set, HUNL infoset keys "
            "use the bucketed (b<id>|...) form on postflop streets; preflop "
            "is always lossless. Default: None (PR 3 lossless behavior)."
        ),
    )
    sv.set_defaults(func=_cmd_solve)

    pa = sub.add_parser(
        "precompute-abstraction",
        help="Build the EMD-bucketed card abstraction artifact (PR 4).",
    )
    pa.add_argument("--output", type=str, default="abstraction_v1.npz")
    pa.add_argument(
        "--bucket-counts",
        type=str,
        default="256,128,64",
        help="Comma-separated flop,turn,river bucket counts. Default: 256,128,64.",
    )
    pa.add_argument("--feature-bins", type=int, default=50)
    pa.add_argument("--seed", type=int, default=42)
    pa.add_argument("--max-iter", type=int, default=200)
    pa.add_argument(
        "--street",
        choices=("flop", "turn", "river", "all"),
        default="all",
    )
    pa.add_argument(
        "--flop-mode",
        choices=("exact", "mc"),
        default="mc",
        help="Equity-feature mode for the flop street. Default: mc.",
    )
    pa.add_argument(
        "--mc-iterations",
        type=int,
        default=200_000,
        help="Monte Carlo iterations per (board, hand). Default: 200000.",
    )
    pa.add_argument(
        "--max-boards",
        type=int,
        default=None,
        help=(
            "Cap on canonical-board enumeration per street (test/smoke knob; "
            "default None = full enumeration)."
        ),
    )
    pa.set_defaults(func=_cmd_precompute_abstraction)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
