"""Command-line interface for poker_solver."""

from __future__ import annotations

import argparse
import json as _json
import os as _os
import random
import sys
from dataclasses import asdict as _asdict
from dataclasses import replace
from pathlib import Path
from typing import IO, Union

from poker_solver.card import Card, parse_board, parse_hand
from poker_solver.equity import equity
from poker_solver.games import Game, KuhnPoker, LeducPoker
from poker_solver.hunl import HUNLConfig, HUNLPoker, Street, default_tiny_subgame
from poker_solver.library import (
    Library,
    LibraryDuplicateError,
    LibraryFilter,
    _resolve_library_path,
)
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
    #
    # PR 6: when the user opts in via ``--backend rust`` on the postflop
    # path, route through ``solve()`` instead so it picks up the new HUNL
    # Rust branch in ``_solve_rust``. The Python postflop path stays the
    # default per locked decision D10.
    result: object
    try:
        if (
            args.game == "hunl"
            and getattr(args, "hunl_mode", "") == "postflop"
            and args.backend == "rust"
        ):
            assert isinstance(game, HUNLPoker)
            result = solve(
                game,
                iterations=args.iterations,
                backend="rust",
                target_exploitability=args.target_exploitability,
                seed=args.seed,
            )
        elif args.game == "hunl" and getattr(args, "hunl_mode", "") == "postflop":
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


def _cmd_ui(args: argparse.Namespace) -> int:
    """Launch the PR 10 NiceGUI app.

    Lazy-imports ``ui.app`` so the rest of the CLI works without NiceGUI
    installed. Catches ``ImportError`` (broader than ``ModuleNotFoundError``
    — covers cases where ``nicegui`` is installed but a sub-import fails)
    and prints a clear install hint with exit code 2.
    """
    try:
        from ui.app import launch  # type: ignore[import-not-found]
    except ImportError:
        print(
            "UI support not installed. " "Install with `pip install poker-solver[ui]`.",
            file=sys.stderr,
        )
        return 2
    launch(port=args.port, host=args.host, dark_mode=args.dark_mode)
    return 0


def _library_path_from_args(args: argparse.Namespace) -> Path:
    """Apply the CLI flag precedence on top of ``_resolve_library_path``.

    Precedence: ``--library-path`` flag > ``$POKER_SOLVER_LIBRARY_PATH`` >
    ``~/.poker_solver/library.db``. The library module already honors the
    env var and default; we just gate the explicit flag.
    """
    explicit = getattr(args, "library_path", None)
    return _resolve_library_path(Path(explicit) if explicit else None)


def _cmd_library_list(args: argparse.Namespace) -> int:
    path = _library_path_from_args(args)
    filt = LibraryFilter(
        board_pattern=args.board_pattern,
        street=args.street,
        stack_bb_min=args.stack_bb_min,
        stack_bb_max=args.stack_bb_max,
        solver_version=args.solver_version,
        created_after=args.created_after,
        label_pattern=args.label_pattern,
    )
    with Library.open(path) as lib:
        rows = lib.list(filt, limit=args.limit, offset=args.offset)
    if args.json:
        print(_json.dumps([_asdict(r) for r in rows], indent=2))
        return 0
    if args.table:
        try:
            from rich.console import Console
            from rich.table import Table

            table = Table(title=f"poker-solver library ({len(rows)} rows)")
            for col in (
                "spot_id",
                "label",
                "street",
                "board",
                "stacks",
                "value",
                "exp",
                "iters",
                "tier",
                "version",
                "created",
            ):
                table.add_column(col)
            for r in rows:
                table.add_row(
                    r.spot_id[:12],
                    r.label,
                    r.street,
                    r.board_signature,
                    str(r.stack_bb),
                    f"{r.game_value:+.4f}",
                    f"{r.exploitability:.4f}",
                    str(r.iterations),
                    r.abstraction_tier,
                    r.solver_version,
                    str(r.created_at),
                )
            Console().print(table)
            return 0
        except ImportError:
            pass
    for r in rows:
        print(
            "\t".join(
                [
                    r.spot_id,
                    r.label,
                    r.street,
                    r.board_signature,
                    str(r.stack_bb),
                    f"{r.game_value:+.6f}",
                    f"{r.exploitability:.6f}",
                    str(r.iterations),
                    r.abstraction_tier,
                    r.solver_version,
                    str(r.created_at),
                ]
            )
        )
    return 0


def _cmd_library_get(args: argparse.Namespace) -> int:
    path = _library_path_from_args(args)
    with Library.open(path) as lib:
        result = lib.get(args.spot_id)
    if result is None:
        print(f"error: spot_id {args.spot_id} not found", file=sys.stderr)
        return 1
    if args.json:
        last_exp = (
            result.exploitability_history[-1] if result.exploitability_history else None
        )
        print(
            _json.dumps(
                {
                    "average_strategy": result.average_strategy,
                    "game_value": result.game_value,
                    "exploitability": last_exp,
                    "iterations": result.iterations,
                    "backend": result.backend,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    print(f"spot_id:        {args.spot_id}")
    print(f"game_value:     {result.game_value:+.6f}")
    if result.exploitability_history:
        print(f"exploitability: {result.exploitability_history[-1]:.6f}")
    print(f"iterations:     {result.iterations}")
    print(f"infosets:       {len(result.average_strategy)}")
    return 0


def _cmd_library_put(args: argparse.Namespace) -> int:
    # PUT consumes an exported-format JSON file (same schema as `import`);
    # the round-trip lets users hand-craft a spot + result offline. We
    # delegate to Library.import_ which validates the schema.
    path = _library_path_from_args(args)
    src = Path(args.description)
    with Library.open(path) as lib:
        try:
            spot_id = lib.import_(src, overwrite=args.overwrite)
        except LibraryDuplicateError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
    print(spot_id)
    return 0


def _cmd_library_export(args: argparse.Namespace) -> int:
    path = _library_path_from_args(args)
    out = Path(args.output_path)
    with Library.open(path) as lib:
        try:
            lib.export(args.spot_id, out)
        except KeyError:
            print(f"error: spot_id {args.spot_id} not found", file=sys.stderr)
            return 1
    print(str(out))
    return 0


def _cmd_library_import(args: argparse.Namespace) -> int:
    path = _library_path_from_args(args)
    src = Path(args.input_path)
    with Library.open(path) as lib:
        try:
            spot_id = lib.import_(src, overwrite=args.overwrite)
        except LibraryDuplicateError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
    print(spot_id)
    return 0


def _cmd_library_delete(args: argparse.Namespace) -> int:
    path = _library_path_from_args(args)
    with Library.open(path) as lib:
        try:
            lib.delete(args.spot_id)
        except KeyError:
            print(f"error: spot_id {args.spot_id} not found", file=sys.stderr)
            return 1
    return 0


def _cmd_library_stats(args: argparse.Namespace) -> int:
    path = _library_path_from_args(args)
    with Library.open(path) as lib:
        stats = lib.stats()
    if args.json:
        print(_json.dumps(_asdict(stats), indent=2, sort_keys=True))
        return 0
    print(f"path:               {path}")
    print(f"total_count:        {stats.total_count}")
    print(f"total_size_bytes:   {stats.total_size_bytes}")
    print(f"oldest_created_at:  {stats.oldest_created_at}")
    print(f"newest_created_at:  {stats.newest_created_at}")
    if stats.by_street:
        print("by_street:")
        for k, v in sorted(stats.by_street.items()):
            print(f"  {k:<10}  {v}")
    if stats.by_solver_version:
        print("by_solver_version:")
        for k, v in sorted(stats.by_solver_version.items()):
            print(f"  {k:<10}  {v}")
    return 0


def _cmd_batch_solve(args: argparse.Namespace) -> int:
    """Delegate to ``scripts.batch_solve`` (Agent C).

    PR 11 keeps the CLI wiring here; the CSV-driven loop is owned by
    ``scripts/batch_solve.py``. If Agent C's file isn't on PYTHONPATH
    yet, we fall back to an explicit "not yet wired" error rather than
    a confusing ``ImportError`` traceback.
    """
    try:
        # TODO(agent-c): scripts.batch_solve.run() is the expected entry point.
        from scripts.batch_solve import run as _run  # type: ignore[import-not-found]
    except ImportError:
        print(
            "error: scripts/batch_solve.py is not available on PYTHONPATH; "
            "PR 11 Agent C delivers that file. Run "
            "`PYTHONPATH=. python -m scripts.batch_solve --input <csv>` once "
            "the file lands.",
            file=sys.stderr,
        )
        return 2
    # Forward the resolved library path so the env var / flag work uniformly.
    resolved = _library_path_from_args(args)
    _os.environ.setdefault("POKER_SOLVER_LIBRARY_PATH", str(resolved))
    return int(
        _run(
            input_csv=Path(args.input),
            workers=args.workers,
            max_memory_gb=args.max_memory_gb,
            dry_run=args.dry_run,
            library_path=resolved,
        )
    )


def _cmd_pushfold(args: argparse.Namespace) -> int:
    """PR 39: thin CLI wrapper around ``poker_solver.pushfold.get_pushfold_strategy``.

    Surfaces the short-stack push/fold chart lookup that previously required
    a one-line Python invocation (USAGE.md §7a "no `poker-solver pushfold`
    subcommand" gap). Maps ``ValueError`` / ``PushFoldChartUnavailable``
    cleanly into exit code 2 with a stderr message; ``main()`` already
    catches ``ValueError`` so the chart-unavailable branch (a ValueError
    subclass) routes the same way.

    Output format on success: one line ``<hand> <position> <stack>BB: <freq>``
    so the value is greppable + scriptable. With ``--json`` we emit a JSON
    object for downstream tooling.
    """
    from poker_solver.pushfold import (
        PushFoldChartUnavailable,
        get_full_range,
        get_pushfold_strategy,
    )

    if args.full_range:
        try:
            chart = get_full_range(args.stack, args.position)
        except (PushFoldChartUnavailable, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(_json.dumps(chart, indent=2, sort_keys=True))
            return 0
        for hand in sorted(chart):
            print(f"{hand}\t{chart[hand]:.6f}")
        return 0

    if args.hand is None:
        print(
            "error: --hand is required unless --full-range is set",
            file=sys.stderr,
        )
        return 2
    try:
        freq = get_pushfold_strategy(args.stack, args.position, args.hand)
    except (PushFoldChartUnavailable, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(
            _json.dumps(
                {
                    "stack_bb": args.stack,
                    "position": args.position,
                    "hand": args.hand,
                    "frequency": freq,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    print(f"{args.hand} {args.position} {args.stack}BB: {freq:.6f}")
    return 0


def _cmd_river(args: argparse.Namespace) -> int:
    """PR 39: river spot solve with fixed hero hole cards vs villain range.

    Closes the USAGE.md §7a "no `poker-solver river --hero --villain-range`"
    gap. Wraps ``solve_hunl_postflop`` with ``initial_hole_cards`` pinned
    to the hero combo and the villain combo enumerated from
    ``--villain-range``. For range-on-one-side queries we follow the
    USAGE.md §7a suggested pattern: loop villain combos, aggregate by
    combo weight. The output reports aggregated frequencies across the
    villain range plus the per-combo EV.

    Sample usage::

        poker-solver river --board "As 7c 2d Kh 5s" --hero AhKh \\
            --villain-range "QQ,JJ,AKs" --iters 200
    """
    from poker_solver.hunl import HUNLConfig, Street
    from poker_solver.hunl_solver import solve_hunl_postflop

    board_cards = parse_board(args.board)
    if len(board_cards) != 5:
        raise ValueError(
            f"--board must specify 5 river cards; got {len(board_cards)}"
        )

    hero_cards = parse_hand(args.hero)
    if len(hero_cards) != 2:
        raise ValueError(
            f"--hero must be a 2-card hole (e.g. 'AhKh'); got {args.hero!r}"
        )
    hero_pair = (hero_cards[0], hero_cards[1])

    board_set = set(board_cards)
    if hero_pair[0] in board_set or hero_pair[1] in board_set:
        raise ValueError(
            f"--hero {args.hero!r} overlaps with --board {args.board!r}"
        )

    villain_range = parse_range(args.villain_range)
    villain_combos = [
        combo
        for combo in villain_range
        if combo[0] not in board_set
        and combo[1] not in board_set
        and combo[0] != hero_pair[0]
        and combo[0] != hero_pair[1]
        and combo[1] != hero_pair[0]
        and combo[1] != hero_pair[1]
    ]
    if not villain_combos:
        raise ValueError(
            "no villain combos compatible with --hero + --board (every combo "
            "in --villain-range shares a card with hero or the board)."
        )

    # Per-spot accounting: 100 BB symmetric, dead-money river pot of 10 BB
    # (matches the USAGE.md §3b convention; users can rebuild a custom config
    # in Python for non-standard stacks).
    big_blind = 100
    pot_bb = max(1, int(args.pot_bb))
    stack_bb = max(2, int(args.stack_bb))
    initial_pot = pot_bb * big_blind
    half = initial_pot // 2
    starting_stack = stack_bb * big_blind

    print(f"Board:        {' '.join(str(c) for c in board_cards)}")
    print(f"Hero:         {' '.join(str(c) for c in hero_pair)}")
    print(
        f"Villain range: {args.villain_range} "
        f"({len(villain_combos)} combos after card removal)"
    )
    print(f"Iterations:   {args.iters}")
    print()

    aggregate: dict[str, float] = {}
    total_weight = 0.0
    ev_sum = 0.0
    for villain_pair in villain_combos:
        cfg = HUNLConfig(
            starting_stack=starting_stack,
            small_blind=big_blind // 2,
            big_blind=big_blind,
            starting_street=Street.RIVER,
            initial_board=tuple(board_cards),
            initial_pot=initial_pot,
            initial_contributions=(half, half),
            initial_hole_cards=(hero_pair, villain_pair),
        )
        result = solve_hunl_postflop(cfg, iterations=args.iters)
        # Hero is P0 (button); postflop P1 (BB / OOP) acts first. We want
        # hero's FIRST decision — the shortest-history infoset whose hole
        # matches hero. We pick the lex-shortest history string among the
        # matching keys per villain combo to stay robust to differing
        # opening lines (villain check -> hero IP-bets, or villain leads
        # -> hero faces a bet).
        hero_keys = [
            (key, probs)
            for key, probs in result.average_strategy.items()
            if len(key.split("|")) == 4
            and _hole_matches(key.split("|")[0], hero_pair)
        ]
        if hero_keys:
            # Sort by history length then lex; take the first decision (smallest).
            hero_keys.sort(key=lambda kp: (len(kp[0].split("|")[3]), kp[0]))
            _, first_probs = hero_keys[0]
            for i, p in enumerate(first_probs):
                aggregate.setdefault(f"action_{i}", 0.0)
                aggregate[f"action_{i}"] += p
        total_weight += 1.0
        ev_sum += result.game_value

    if total_weight == 0:
        raise ValueError("no hero infosets aggregated (unexpected)")
    for k in aggregate:
        aggregate[k] /= total_weight

    print("Hero first-decision aggregate (average over villain combos):")
    for k in sorted(aggregate):
        print(f"  {k:<10}  {aggregate[k]:.6f}")
    print(f"\nMean game value (BB, P0 perspective): {ev_sum / total_weight:+.6f}")
    return 0


def _hole_matches(hole_str: str, hero_pair: tuple) -> bool:
    """True iff `hole_str` (sorted-card form from infoset key) matches `hero_pair`.

    Our `infoset_key` sorts the hole by ``(rank, suit)`` ascending (see
    `hunl._sorted_card_string`); we replicate that sort here so the user's
    authoring order in `--hero` doesn't matter for the comparison.
    """
    if len(hole_str) != 4:
        return False
    c1, c2 = hero_pair
    if (c1.rank, c1.suit) > (c2.rank, c2.suit):
        c1, c2 = c2, c1
    return hole_str == f"{c1}{c2}"


def _cmd_parity(args: argparse.Namespace) -> int:
    """PR 39: parity-diff wrapper around ``poker_solver.parity.noambrown_wrapper``.

    Surfaces the river-spot diff machinery already used by
    ``tests/test_river_diff.py`` as a one-shot CLI command for ad-hoc
    sanity checks (W4.3 retest). Loads a fixture by id from
    ``tests/data/river_spots.json`` (or a user-supplied path via
    ``--fixture-path``), invokes Brown's binary, runs our solver, and
    prints the headline coverage + game-value diff.

    Brown's binary must be built (``scripts/build_noambrown.sh``) and on
    the canonical path returned by ``find_brown_binary()``. When the
    binary is missing we exit 2 with a hint — same protocol the test
    harness uses for in-test skips.
    """
    from poker_solver.hunl import HUNLConfig, Street
    from poker_solver.hunl_solver import solve_hunl_postflop
    from poker_solver.parity.noambrown_wrapper import (
        canonicalize_brown_history,
        canonicalize_our_history,
        find_brown_binary,
        load_spots,
        run_brown_solver,
    )

    fixture_path = Path(
        args.fixture_path
        if args.fixture_path
        else Path(__file__).resolve().parent.parent
        / "tests"
        / "data"
        / "river_spots.json"
    )
    if not fixture_path.is_file():
        print(
            f"error: river fixtures not found at {fixture_path}",
            file=sys.stderr,
        )
        return 2
    spots = load_spots(fixture_path)
    spot = next((s for s in spots if s.id == args.fixture), None)
    if spot is None:
        available = ", ".join(s.id for s in spots)
        print(
            f"error: fixture {args.fixture!r} not found. Available: {available}",
            file=sys.stderr,
        )
        return 2

    binary = find_brown_binary()
    if binary is None:
        print(
            "error: Brown's binary not built. Run "
            "`scripts/build_noambrown.sh` from the repo root, then retry.",
            file=sys.stderr,
        )
        return 2

    iterations = (
        spot.iterations_override if spot.iterations_override is not None else args.iters
    )

    print(f"Fixture:     {spot.id}")
    print(f"Description: {spot.description}")
    print(f"Iterations:  {iterations}")
    print()

    brown_dump = run_brown_solver(spot, binary, iterations=iterations)

    cfg = HUNLConfig(
        starting_stack=spot.stack + spot.pot // 2,
        small_blind=50,
        big_blind=100,
        starting_street=Street.RIVER,
        initial_board=tuple(spot.board),
        initial_pot=spot.pot,
        initial_contributions=(spot.pot // 2, spot.pot // 2),
        bet_size_fractions=spot.bet_sizes,
        include_all_in=spot.include_all_in,
        postflop_raise_cap=spot.max_raises,
    )
    our_result = solve_hunl_postflop(cfg, iterations=iterations)

    # Canonical-history coverage diff. Mirrors the coverage check in
    # tests/test_river_diff.py; per-action numeric diff is delegated to
    # that test harness (Agent B owns the full matrix walk).
    brown_keys: set[str] = set()
    for player_profile in brown_dump.players:
        for hist_key in player_profile.profile:
            canonical = canonicalize_brown_history(hist_key, spot=spot)
            brown_keys.add(_canonical_str(canonical))

    our_keys: set[str] = set()
    for key in our_result.average_strategy:
        parts = key.split("|")
        if len(parts) != 4:
            continue
        canonical = canonicalize_our_history(parts[3], spot=spot)
        our_keys.add(_canonical_str(canonical))

    overlap = brown_keys & our_keys
    coverage = (len(overlap) / len(brown_keys)) if brown_keys else 1.0

    print("Parity diff:")
    print(f"  Brown infoset keys:      {len(brown_keys)}")
    print(f"  Ours canonicalized keys: {len(our_keys)}")
    print(f"  Overlap:                 {len(overlap)} ({coverage:.1%})")
    print(f"  Our game value (BB):     {our_result.game_value:+.6f}")
    if brown_dump.exploitability_chips is not None:
        print(
            f"  Brown final exploitability (chips): "
            f"{brown_dump.exploitability_chips:.6f}"
        )
    if brown_dump.game_value_p0 is not None:
        gv_diff = our_result.game_value - brown_dump.game_value_p0
        print(f"  Game-value diff:         {gv_diff:+.6f}")
    return 0


def _canonical_str(canonical: tuple) -> str:
    """Render a canonical history tuple to a stable string (PR 7 §5)."""
    if not canonical:
        return "root"
    parts = []
    for kind, amt in canonical:
        if kind in ("f", "c"):
            parts.append(kind)
        else:
            parts.append(f"{kind}{amt}")
    return "/".join(parts)


def _add_library_path_flag(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--library-path",
        type=str,
        default=None,
        help=(
            "Override the library DB path. Precedence: this flag > "
            "$POKER_SOLVER_LIBRARY_PATH > ~/.poker_solver/library.db."
        ),
    )


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

    # PR 10: NiceGUI UI subcommand. Lazy-imports `ui.app` inside `_cmd_ui`
    # so the rest of the CLI works without the `[ui]` extra installed.
    ui_parser = sub.add_parser(
        "ui",
        help="Launch the NiceGUI browser UI (PR 10).",
    )
    ui_parser.add_argument("--port", type=int, default=8080)
    ui_parser.add_argument("--host", type=str, default="127.0.0.1")
    ui_parser.add_argument(
        "--dark-mode",
        choices=("auto", "light", "dark"),
        default="auto",
        help=(
            "Theme override: 'auto' follows the OS system preference (PR 10a "
            "default per pr10a_spec.md §2.4); 'light' and 'dark' force the "
            "respective theme."
        ),
    )
    ui_parser.set_defaults(func=_cmd_ui)

    # ---- PR 11: library subcommand group ----
    lib = sub.add_parser(
        "library",
        help="Manage the local solved-spot library (PR 11).",
    )
    lib_sub = lib.add_subparsers(dest="library_cmd", required=True)

    lib_list = lib_sub.add_parser("list", help="List solved spots (most recent first).")
    lib_list.add_argument("--street", type=str, default=None)
    lib_list.add_argument("--board-pattern", type=str, default=None)
    lib_list.add_argument("--stack-bb-min", type=int, default=None)
    lib_list.add_argument("--stack-bb-max", type=int, default=None)
    lib_list.add_argument("--solver-version", type=str, default=None)
    lib_list.add_argument("--created-after", type=int, default=None)
    lib_list.add_argument("--label-pattern", type=str, default=None)
    lib_list.add_argument("--limit", type=int, default=1000)
    lib_list.add_argument("--offset", type=int, default=0)
    lib_list_fmt = lib_list.add_mutually_exclusive_group()
    lib_list_fmt.add_argument("--json", action="store_true")
    lib_list_fmt.add_argument("--table", action="store_true")
    _add_library_path_flag(lib_list)
    lib_list.set_defaults(func=_cmd_library_list)

    lib_get = lib_sub.add_parser("get", help="Fetch a single spot by id.")
    lib_get.add_argument("spot_id", type=str)
    lib_get.add_argument("--json", action="store_true")
    _add_library_path_flag(lib_get)
    lib_get.set_defaults(func=_cmd_library_get)

    lib_put = lib_sub.add_parser(
        "put", help="Insert a spot from an exported-format JSON file."
    )
    lib_put.add_argument("description", type=str, help="Path to the spot JSON file.")
    lib_put.add_argument("--overwrite", action="store_true")
    _add_library_path_flag(lib_put)
    lib_put.set_defaults(func=_cmd_library_put)

    lib_export = lib_sub.add_parser("export", help="Export a spot to JSON.")
    lib_export.add_argument("spot_id", type=str)
    lib_export.add_argument("output_path", type=str)
    _add_library_path_flag(lib_export)
    lib_export.set_defaults(func=_cmd_library_export)

    lib_import = lib_sub.add_parser("import", help="Import a previously exported spot.")
    lib_import.add_argument("input_path", type=str)
    lib_import.add_argument("--overwrite", action="store_true")
    _add_library_path_flag(lib_import)
    lib_import.set_defaults(func=_cmd_library_import)

    lib_delete = lib_sub.add_parser("delete", help="Delete a spot by id.")
    lib_delete.add_argument("spot_id", type=str)
    _add_library_path_flag(lib_delete)
    lib_delete.set_defaults(func=_cmd_library_delete)

    lib_stats = lib_sub.add_parser("stats", help="Aggregate library statistics.")
    lib_stats.add_argument("--json", action="store_true")
    _add_library_path_flag(lib_stats)
    lib_stats.set_defaults(func=_cmd_library_stats)

    # ---- PR 39: ergonomic short-cut subcommands (pushfold / river / parity).
    # Each is a thin wrapper around an existing library API (see _cmd_*
    # above); zero engine changes. Closes USAGE.md §7a "Known CLI gaps".
    pf = sub.add_parser(
        "pushfold",
        help="Look up a short-stack push/fold chart cell.",
    )
    pf.add_argument(
        "--stack",
        type=int,
        required=True,
        help="Effective stack in BB (integer 2-15 inclusive).",
    )
    pf.add_argument(
        "--position",
        choices=("sb_jam", "bb_call_vs_jam"),
        required=True,
        help="Chart side: 'sb_jam' (SB shove frequency) or 'bb_call_vs_jam' "
        "(BB call frequency vs a SB jam).",
    )
    pf.add_argument(
        "--hand",
        type=str,
        default=None,
        help="Hand class to look up (e.g. '88', 'AKs', 'AKo'). Required unless "
        "--full-range is set.",
    )
    pf.add_argument(
        "--full-range",
        action="store_true",
        help="Emit the full 169-cell chart for the (stack, position) cell.",
    )
    pf.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of the human-readable line(s).",
    )
    pf.set_defaults(func=_cmd_pushfold)

    rv = sub.add_parser(
        "river",
        help="Solve a river spot with fixed hero cards vs a villain range.",
    )
    rv.add_argument(
        "--board",
        type=str,
        required=True,
        help="The 5 river cards, e.g. 'As 7c 2d Kh 5s'.",
    )
    rv.add_argument(
        "--hero",
        type=str,
        required=True,
        help="Hero's 2-card hole, e.g. 'AhKh'.",
    )
    rv.add_argument(
        "--villain-range",
        type=str,
        required=True,
        help="Villain range in PioSolver notation, e.g. 'QQ,JJ,AKs'.",
    )
    rv.add_argument(
        "--iters",
        type=int,
        default=200,
        help="DCFR iterations per per-combo solve (default: 200).",
    )
    rv.add_argument(
        "--pot-bb",
        type=int,
        default=10,
        help="Starting pot in BB (default: 10).",
    )
    rv.add_argument(
        "--stack-bb",
        type=int,
        default=100,
        help="Per-player effective stack in BB (default: 100).",
    )
    rv.set_defaults(func=_cmd_river)

    pp = sub.add_parser(
        "parity",
        help="Diff our river solve vs Noam Brown's binary on a fixture spot.",
    )
    pp.add_argument(
        "--fixture",
        type=str,
        required=True,
        help="Spot id from tests/data/river_spots.json (e.g. 'dry_K72_rainbow').",
    )
    pp.add_argument(
        "--fixture-path",
        type=str,
        default=None,
        help="Override fixture JSON path; defaults to tests/data/river_spots.json.",
    )
    pp.add_argument(
        "--iters",
        type=int,
        default=2000,
        help="DCFR iterations on both engines (default: 2000, matches PR 7).",
    )
    pp.set_defaults(func=_cmd_parity)

    # ---- PR 11: batch-solve top-level subcommand ----
    bs = sub.add_parser(
        "batch-solve",
        help="Solve a CSV of spots and write results to the library (PR 11 Agent C).",
    )
    bs.add_argument("--input", type=str, required=True, help="Path to the CSV input.")
    bs.add_argument("--workers", type=int, default=1)
    bs.add_argument("--max-memory-gb", type=float, default=14.0)
    bs.add_argument("--dry-run", action="store_true")
    _add_library_path_flag(bs)
    bs.set_defaults(func=_cmd_batch_solve)

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
