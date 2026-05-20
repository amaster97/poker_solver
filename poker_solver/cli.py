"""Command-line interface for poker_solver."""
from __future__ import annotations

import argparse
import random
import sys
from typing import List, Union

from poker_solver.card import Card, parse_board, parse_hand
from poker_solver.equity import equity
from poker_solver.range import Range, parse_range

HandInput = Union[List[Card], Range]


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="poker-solver",
        description="Texas Hold'em equity solver",
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

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
