"""Command-line interface for poker_solver."""

from __future__ import annotations

import argparse
import random
import sys
from typing import Union

from poker_solver.card import Card, parse_board, parse_hand
from poker_solver.equity import equity
from poker_solver.games import KuhnPoker
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


_GAMES = {"kuhn": KuhnPoker}


def _cmd_solve(args: argparse.Namespace) -> int:
    game_cls = _GAMES[args.game]
    game = game_cls()
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
        default=10_000,
        help="Monte Carlo iterations (default: 10000)",
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
        help="Which game to solve (currently: kuhn)",
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
    sv.set_defaults(func=_cmd_solve)

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
