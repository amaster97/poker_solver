"""Command-line interface for poker_solver."""

from __future__ import annotations

import argparse
import random
import sys
from dataclasses import replace
from pathlib import Path
from typing import IO, Union

from poker_solver.card import Card, parse_board, parse_hand
from poker_solver.equity import equity
from poker_solver.games import Game, KuhnPoker, LeducPoker
from poker_solver.hunl import HUNLConfig, HUNLPoker, Street, default_tiny_subgame
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


def _parse_bet_sizes(spec: str) -> tuple[float, ...]:
    """Parse a comma-separated percentage list into pot-fraction floats.

    ``"33,75,100,150,200"`` → ``(0.33, 0.75, 1.0, 1.5, 2.0)``. Used for the
    ``--bet-sizes`` flag in ``--hunl-mode postflop``.
    """
    out: list[float] = []
    for tok in spec.split(","):
        tok = tok.strip()
        if not tok:
            continue
        out.append(float(tok) / 100.0)
    if not out:
        raise ValueError(f"--bet-sizes must list at least one fraction; got {spec!r}")
    return tuple(out)


def _build_postflop_config(args: argparse.Namespace) -> HUNLConfig:
    """Build an ad-hoc postflop `HUNLConfig` from CLI args (PR 5 §6).

    `--board` is REQUIRED; its card count picks the starting street
    (3=flop, 4=turn, 5=river). `--stacks` is the per-player BB count
    (symmetric); `--bet-sizes` overrides the bet-size menu.
    """
    board_spec = getattr(args, "board", None)
    if not board_spec:
        raise ValueError(
            "--hunl-mode postflop requires --board (e.g., 'As 7c 2d' for flop)."
        )
    board_cards = parse_board(board_spec)
    if len(board_cards) == 3:
        starting_street = Street.FLOP
    elif len(board_cards) == 4:
        starting_street = Street.TURN
    elif len(board_cards) == 5:
        starting_street = Street.RIVER
    else:
        raise ValueError(
            f"--board must have 3/4/5 cards for postflop; got {len(board_cards)}."
        )
    stacks_bb = int(getattr(args, "stacks", 100))
    big_blind = 100
    starting_stack = stacks_bb * big_blind
    initial_pot = 2 * big_blind  # SB + BB equivalents already in.
    bet_sizes_spec = getattr(args, "bet_sizes", None) or "33,75,100,150,200"
    bet_fractions = _parse_bet_sizes(bet_sizes_spec)
    return HUNLConfig(
        starting_stack=starting_stack,
        small_blind=big_blind // 2,
        big_blind=big_blind,
        starting_street=starting_street,
        initial_board=tuple(board_cards),
        initial_pot=initial_pot,
        initial_contributions=(big_blind, big_blind),
        bet_size_fractions=bet_fractions,
    )


def _build_hunl_with_args(args: argparse.Namespace) -> Game:
    mode = getattr(args, "hunl_mode", "tiny_subgame")
    if mode == "tiny_subgame":
        config = default_tiny_subgame()
    elif mode == "postflop":
        config = _build_postflop_config(args)
    elif mode == "full":
        raise NotImplementedError(
            "Full HUNL solve (preflop tree) lands in PR 9. For postflop "
            "subgames use --hunl-mode postflop with --board and --stacks."
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
    # The HUNL postflop path bypasses solver.solve() so we can thread the
    # extra CLI flags (--max-memory-gb, --log-every, --target-exploitability)
    # through directly. The push/fold short-circuit doesn't fire for
    # postflop-start games (it only fires on Street.PREFLOP), so calling
    # solve_hunl_postflop here is equivalent to solver.solve()'s postflop
    # branch for this case.
    result: object
    try:
        if args.game == "hunl" and getattr(args, "hunl_mode", "") == "postflop":
            from poker_solver.hunl_solver import solve_hunl_postflop

            assert isinstance(game, HUNLPoker)
            result = solve_hunl_postflop(
                game.config,
                iterations=args.iterations,
                memory_budget_gb=args.max_memory_gb,
                target_exploitability=args.target_exploitability,
                log_every=args.log_every,
                seed=args.seed,
            )
        else:
            result = solve(game, iterations=args.iterations, backend=args.backend)
    except MemoryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        if len(exc.args) > 1:
            report = exc.args[1]
            print(file=sys.stderr)
            print("Memory (partial report at abort):", file=sys.stderr)
            _print_memory_section(report, stream=sys.stderr)
        return 1

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
    # PR 5: print the memory section when the result is a HUNLSolveResult.
    memory_report = getattr(result, "memory_report", None)
    if memory_report is not None:
        print()
        print("Memory:")
        _print_memory_section(memory_report)
    return 0


def _print_memory_section(report: object, stream: IO[str] | None = None) -> None:
    """Pretty-print the per-street memory breakdown.

    Accepts an opaque `MemoryReport` (defined in Agent B's `profiler.memory`)
    so we don't take a direct dependency on a specific dataclass shape from
    inside CLI code that may be imported by users without psutil installed.
    """
    out: IO[str] = stream if stream is not None else sys.stdout
    per_street = getattr(report, "per_street", ())
    for entry in per_street:
        name = entry.street.name
        mb = entry.total_bytes / 1024**2
        count = entry.infoset_count
        print(
            f"  {name:<7}  infosets={count:>8}  total={mb:>9.2f} MB",
            file=out,
        )
    total_gb = getattr(report, "total_gb", 0.0)
    rss_gb = getattr(report, "process_rss_gb", 0.0)
    river_ratio = getattr(report, "river_ratio", 0.0)
    print(f"  total            grand_total={total_gb:>9.3f} GB", file=out)
    print(f"  psutil RSS                  ={rss_gb:>9.3f} GB", file=out)
    print(f"  river ratio                 ={river_ratio:>9.1%}", file=out)


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
        choices=("tiny_subgame", "postflop", "full"),
        default="tiny_subgame",
        help=(
            "HUNL mode: tiny_subgame (default, river-only fixture); postflop "
            "(PR 5 — ad-hoc postflop subgame solver via --board + --stacks); "
            "full (HUNL preflop tree; raises NotImplementedError pointing at "
            "PR 9)."
        ),
    )
    sv.add_argument(
        "--board",
        type=str,
        default=None,
        help=(
            "Community cards for --hunl-mode postflop (3/4/5 cards = "
            "flop/turn/river start). e.g. 'As 7c 2d'."
        ),
    )
    sv.add_argument(
        "--stacks",
        type=int,
        default=100,
        help="Per-player effective stack in BB for --hunl-mode postflop (default 100).",
    )
    sv.add_argument(
        "--max-memory-gb",
        type=float,
        default=14.0,
        help=(
            "Memory budget for the postflop solver (default 14.0 GB per "
            "PLAN.md). Exceeding aborts cleanly with a partial MemoryReport."
        ),
    )
    sv.add_argument(
        "--bet-sizes",
        type=str,
        default=None,
        help=(
            "Comma-separated pot-fraction percentages (e.g. '33,75,100,150,200') "
            "for postflop bet sizing. Default: the full 5-size menu. All-in "
            "always available."
        ),
    )
    sv.add_argument(
        "--target-exploitability",
        type=float,
        default=None,
        help=(
            "Optional convergence target in BB; the postflop solver "
            "early-exits when reached. Requires --log-every to compute "
            "exploitability between chunks."
        ),
    )
    sv.add_argument(
        "--log-every",
        type=int,
        default=None,
        help=(
            "When set, snapshot exploitability + memory every N iterations. "
            "Default: snapshot once at end."
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
