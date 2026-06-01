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

from poker_solver import __version__
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
from poker_solver.solver import solve, solve_best_response

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


def _parse_raise_sizes(spec: str) -> tuple[float, ...]:
    """Parse a comma-separated raise-multiplier list into floats.

    Raise sizes are MULTIPLIERS of the bet being faced (not pot fractions),
    matching ``HUNLConfig.raise_size_xs``. ``"2.5,3"`` → ``(2.5, 3.0)``. Used
    for the ``--raise-sizes`` flag.
    """
    out: list[float] = []
    for tok in spec.split(","):
        tok = tok.strip()
        if not tok:
            continue
        out.append(float(tok))
    if not out:
        raise ValueError(
            f"--raise-sizes must list at least one multiplier; got {spec!r}"
        )
    return tuple(out)


def _build_postflop_config(args: argparse.Namespace) -> HUNLConfig:
    """Build an ad-hoc postflop `HUNLConfig` from CLI args (PR 5 §6).

    `--board` is REQUIRED; its card count picks the starting street
    (3=flop, 4=turn, 5=river). `--stacks` is the per-player BB count
    (symmetric); `--bet-sizes` overrides the bet-size menu.
    """
    # PR 108 (v1.8 hot-patch): the Rust scalar backend (`--backend rust`)
    # requires fixed hole cards to drive `solve_hunl_postflop`. The CLI
    # has no `--initial-hole-cards` flag yet, so `--hunl-mode postflop
    # --backend rust` would silently produce an empty strategy (chance
    # root + empty `chance_outcomes()` => CFR returns `[0, 0]`). Hard-fail
    # loudly until the RvR CLI sub-mode lands. See
    # `docs/chance_outcomes_empty_rca_2026-05-26.md`.
    if getattr(args, "backend", "python") == "rust":
        raise ValueError(
            "--hunl-mode postflop --backend rust currently has no way to "
            "specify fixed hole cards, which the Rust scalar solver requires "
            "(without them, the root becomes a chance node and the solve "
            "returns an empty strategy). For range-vs-range Nash on a "
            "postflop board, use the Python API "
            "poker_solver.solve_range_vs_range_nash(config, hero_range, "
            "villain_range, ...) instead. Use --backend python for the "
            "reference postflop path."
        )
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
    # C1 per-street opening-bet menus (pot-fraction %). Each defaults to None
    # (the engine falls back to the flat ``bet_size_fractions`` menu).
    flop_spec = getattr(args, "flop_bet_sizes", None)
    turn_spec = getattr(args, "turn_bet_sizes", None)
    river_spec = getattr(args, "river_bet_sizes", None)
    flop_fractions = _parse_bet_sizes(flop_spec) if flop_spec else None
    turn_fractions = _parse_bet_sizes(turn_spec) if turn_spec else None
    river_fractions = _parse_bet_sizes(river_spec) if river_spec else None
    # Raise multipliers (×bet faced); defaults to the engine's (3.0,).
    raise_spec = getattr(args, "raise_sizes", None)
    raise_xs: tuple[float, ...] = (
        _parse_raise_sizes(raise_spec) if raise_spec else (3.0,)
    )
    return HUNLConfig(
        starting_stack=starting_stack,
        small_blind=big_blind // 2,
        big_blind=big_blind,
        starting_street=starting_street,
        initial_board=tuple(board_cards),
        initial_pot=initial_pot,
        initial_contributions=(big_blind, big_blind),
        bet_size_fractions=bet_fractions,
        flop_bet_fractions=flop_fractions,
        turn_bet_fractions=turn_fractions,
        river_bet_fractions=river_fractions,
        raise_size_xs=raise_xs,
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


def _cmd_best_response(args: argparse.Namespace) -> int:
    """PR 76 — compute hero's BR against a fixed opponent strategy.

    Loads the opponent strategy from a JSON file (schema:
    ``{"strategy": {<infoset_key>: [probs]}}`` — optional ``format_version``
    and ``config`` fields are accepted but not validated against the engine
    in this MVP), constructs the requested game, and runs
    :func:`solve_best_response`. Prints exploit value / gap to stdout and
    optionally writes the hero's BR strategy JSON to ``--output``.
    """
    # Build the game (reuses the same factory map as `solve`).
    game = _GAMES[args.game](args)

    # Load opponent strategy.
    opp_path = Path(args.opponent)
    if not opp_path.exists():
        print(f"error: opponent strategy file not found: {opp_path}", file=sys.stderr)
        return 1
    try:
        payload = _json.loads(opp_path.read_text(encoding="utf-8"))
    except _json.JSONDecodeError as e:
        print(f"error: opponent strategy JSON parse failed: {e}", file=sys.stderr)
        return 1
    if not isinstance(payload, dict):
        print("error: opponent strategy file root must be a JSON object", file=sys.stderr)
        return 1
    raw_strategy = payload.get("strategy", payload)
    if not isinstance(raw_strategy, dict):
        print(
            "error: 'strategy' field must be an object {infoset_key: [probs]}",
            file=sys.stderr,
        )
        return 1
    opponent_strategy: dict[str, list[float]] = {}
    for key, probs in raw_strategy.items():
        if not isinstance(probs, list):
            print(
                f"error: strategy[{key!r}] is not a list of floats",
                file=sys.stderr,
            )
            return 1
        opponent_strategy[str(key)] = [float(p) for p in probs]

    hero_player = 0 if args.hero_position == "SB" else 1

    # Run BR.
    result = solve_best_response(
        game, opponent_strategy, hero_player=hero_player
    )

    summary = {
        "hero_player": result.hero_player,
        "hero_position": args.hero_position,
        "on_strategy_value_bb": result.on_strategy_value_bb,
        "exploit_value_bb": result.exploit_value_bb,
        "exploit_gap_bb": result.exploit_gap_bb,
        "exploit_gap_mbb": result.exploit_gap_bb * 1000.0,
        "hero_infoset_count": len(result.hero_strategy),
        "opponent_infoset_count": len(opponent_strategy),
        "game": args.game,
    }

    if args.output:
        out_path = Path(args.output)
        out_payload = {
            "format_version": "1.0",
            "format": "poker-solver/strategy",
            "game_id": args.game,
            "hero_player": result.hero_player,
            "summary": summary,
            "strategy": result.hero_strategy,
        }
        out_path.write_text(
            _json.dumps(out_payload, sort_keys=True, indent=2), encoding="utf-8"
        )
        print(f"Hero BR strategy written to {out_path}", file=sys.stderr)

    if args.json:
        print(_json.dumps(summary, sort_keys=True, indent=2))
        return 0

    # Human-readable summary.
    print("Best-response analysis")
    print("======================")
    print(f"Hero: {args.hero_position} (player {result.hero_player})")
    print(
        f"Opponent strategy: {opp_path.name} "
        f"({summary['opponent_infoset_count']:,} infosets)"
    )
    print(f"Game: {args.game}")
    print()
    print(f"On-strategy value:    {result.on_strategy_value_bb:+.6f} BB/hand")
    print(f"Exploit (BR) value:   {result.exploit_value_bb:+.6f} BB/hand")
    print(
        f"Exploit gap:          {result.exploit_gap_bb:+.6f} BB/hand "
        f"({summary['exploit_gap_mbb']:+.1f} mBB/hand)"
    )
    print()
    print(
        f"Hero BR strategy: {summary['hero_infoset_count']:,} infosets "
        f"(deterministic one-hot per infoset)."
    )
    return 0


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
        # ``initial_hole_cards`` is typed as the union
        # ``tuple[tuple[Card, Card], tuple[Card, Card]] | tuple[()]``;
        # ``default_tiny_subgame`` always populates it with the 2-pair variant,
        # so narrow for mypy before indexing.
        hole = subgame.initial_hole_cards
        assert len(hole) == 2, "default_tiny_subgame must define both hole pairs"
        required_hands = [hole[0], hole[1]]

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
    # PR 90 (A83 Track A) — read regret-init-noise / rng-seed off args.
    # Defaults preserve the prior behavior (noise=0.0 is bit-identical to
    # the un-perturbed all-zero `regret_sum` initialization).
    regret_init_noise = float(getattr(args, "regret_init_noise", 0.0) or 0.0)
    rng_seed = int(getattr(args, "rng_seed", 0) or 0)
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
                regret_init_noise=regret_init_noise,
                rng_seed=rng_seed,
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
            # Note: the Python tier's `solve_hunl_postflop` runs the
            # Python DCFR reference; PR 90's regret-init-noise plumbing
            # is Rust-tier-only (the A83 Track A nohup runs use
            # `--backend rust`). The Python path silently ignores the
            # `--regret-init-noise` flag — matches the existing
            # convention that the Python tier is the reference, not a
            # production target.
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
            "UI support not installed. Install with `pip install poker-solver[ui]`.",
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
    """Delegate to ``scripts.batch_solve`` (Agent C, extended in W2.4 / #59).

    PR 11 keeps the CLI wiring here; the CSV-driven loop is owned by
    ``scripts/batch_solve.py``. If Agent C's file isn't on PYTHONPATH
    yet, we fall back to an explicit "not yet wired" error rather than
    a confusing ``ImportError`` traceback.

    W2.4 (#59): forwards ``--backend {python,rust}`` so per-row dispatch
    can route through the Rust vector backend (``solve_range_vs_range_nash``)
    instead of Python ``solve_hunl_postflop``, unblocking the 180s CLI
    timeout that Sarah hit on 1-row × iter=10 runs.
    """
    try:
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
            backend=getattr(args, "backend", "python"),
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


def _resolve_pot_stack_bb(args: argparse.Namespace) -> tuple[int, int]:
    """v1.9.0 — Resolve --pot / --stack with legacy --pot-bb / --stack-bb aliases.

    Returns ``(pot_bb, stack_bb)``. Resolution order:

    1. Canonical ``--pot`` / ``--stack`` win when both forms are passed.
    2. Legacy ``--pot-bb`` / ``--stack-bb`` work alone (emits a one-shot
       deprecation warning to stderr).
    3. Neither passed → defaults (10 BB pot, 100 BB stacks).

    Minimum clamps are preserved from the prior code path (pot >= 1,
    stack >= 2 to avoid solver pathologies).
    """
    from poker_solver.cli_bb_format import emit_deprecation_warning_once

    pot_canonical = getattr(args, "pot", None)
    stack_canonical = getattr(args, "stack", None)
    pot_legacy = getattr(args, "pot_bb", None)
    stack_legacy = getattr(args, "stack_bb", None)

    if pot_canonical is not None:
        pot_bb = int(pot_canonical)
    elif pot_legacy is not None:
        emit_deprecation_warning_once("--pot-bb", "--pot")
        pot_bb = int(pot_legacy)
    else:
        pot_bb = 10

    if stack_canonical is not None:
        stack_bb = int(stack_canonical)
    elif stack_legacy is not None:
        emit_deprecation_warning_once("--stack-bb", "--stack")
        stack_bb = int(stack_legacy)
    else:
        stack_bb = 100

    return max(1, pot_bb), max(2, stack_bb)


def _print_spot_header(
    *,
    starting_stack_chips: int,
    initial_pot_chips: int,
    board_cards: list,
    street_label: str | None,
    bet_size_fractions: tuple[float, ...],
    raise_cap: int,
) -> None:
    """v1.9.0 — Print the ``SPOT CONFIG`` header block to stdout.

    Mirrors the brief verbatim. Always printed before the legacy preamble
    (``Board:`` / ``Hero:`` / etc.) so users get a consistent at-a-glance
    summary across every CLI command. Suppressed in JSON/CSV formats by
    caller (parseable output must not be polluted with the header).
    """
    from poker_solver.cli_bb_format import SpotHeader, render_header

    board_str = " ".join(str(c) for c in board_cards) if board_cards else ""
    header = SpotHeader(
        effective_stack_chips=starting_stack_chips,
        starting_pot_chips=initial_pot_chips,
        board=board_str,
        street=(street_label.upper() if street_label else None),
        bet_menu_pcts=tuple(bet_size_fractions),
        raise_cap=raise_cap,
        include_all_in=True,
    )
    print(render_header(header), end="")


def _str_to_bool(v: str) -> bool:
    """Parse ``true``/``false`` (case-insensitive) for a CLI bool flag.

    Argparse ``type=bool`` is a no-op (any non-empty string is truthy); we
    use this helper for flags like ``--lazy-postflop true|false`` where
    the user expects the string literal to map to a Python ``bool``.
    """
    s = v.strip().lower()
    if s in ("true", "1", "yes", "y", "on"):
        return True
    if s in ("false", "0", "no", "n", "off"):
        return False
    raise ValueError(
        f"expected one of (true, false); got {v!r}"
    )


def _cmd_chained(args: argparse.Namespace) -> int:
    """Task #58 — chained preflop -> lazy postflop orchestrator CLI.

    Wraps :func:`poker_solver.chained.solve_chained` (PR #121,
    Phase A of issue #31). Exposes:

      - Preflop range-vs-range solve via Route A blueprint aggregation.
      - Per-action continuation ranges for every preflop terminal that
        reaches the flop.
      - Optional lazy postflop solve for a single flop (``--board``).

    Output formats:

      - ``text`` (default): preflop per-class strategy table + a section
        per flop-reaching terminal showing the surviving continuation
        ranges. When ``--board`` is set, also prints the postflop
        per-class strategy for that flop.
      - ``json``: full ``ChainedSolveResult`` payload (preflop + every
        continuation + the postflop solve if ``--board`` is set).
      - ``csv``: one row per ``(action_sequence, hand_class, action,
        probability)`` triple. With ``--board``, also emits postflop
        rows.

    Range inputs use the PioSolver-style range notation accepted by
    :func:`poker_solver.range.parse_range` (e.g. ``"AA,KK,AKs"``). The
    orchestrator collapses concrete combos to hand classes internally;
    the labels used by the CLI text/JSON/CSV outputs are the canonical
    pair / suited / offsuit labels (``"AA"``, ``"AKs"``, ``"76o"``).
    """
    from poker_solver.chained import solve_chained
    from poker_solver.hunl import HUNLConfig, Street

    fmt: str = (getattr(args, "format", "text") or "text").lower()
    if fmt not in ("text", "json", "csv"):
        raise ValueError(
            f"--format must be one of (text, json, csv); got {fmt!r}"
        )

    # ---- Parse range inputs (PioSolver notation) -----------------------
    hero_range = parse_range(args.hero_range)
    villain_range = parse_range(args.villain_range)
    if len(hero_range) == 0:
        raise ValueError(f"--hero-range parsed to 0 combos: {args.hero_range!r}")
    if len(villain_range) == 0:
        raise ValueError(
            f"--villain-range parsed to 0 combos: {args.villain_range!r}"
        )

    # ---- Stack validation --------------------------------------------------
    if args.stacks < 2:
        raise ValueError(
            f"--stacks must be at least 2 BB; got {args.stacks}"
        )

    # ---- Build the preflop HUNLConfig template ----------------------------
    big_blind = 100
    starting_stack = int(args.stacks) * big_blind
    config = HUNLConfig(
        starting_stack=starting_stack,
        small_blind=big_blind // 2,
        big_blind=big_blind,
        starting_street=Street.PREFLOP,
        initial_hole_cards=(),
    )

    # ---- Parse --board (optional) ----------------------------------------
    board_cards: list[Card] = []
    if getattr(args, "board", None):
        board_cards = parse_board(args.board)
        if len(board_cards) != 3:
            raise ValueError(
                f"--board must specify 3 flop cards for chained Phase A; "
                f"got {len(board_cards)}"
            )

    # Whether the lazy postflop solve should fire for the requested board.
    # ``--lazy-postflop`` is informational: with ``--board`` set, the
    # solve fires regardless (the flag's only meaningful state when
    # ``--board`` is present is "yes, please solve it"); we surface it
    # so callers can disable the postflop step explicitly via
    # ``--lazy-postflop false``.
    lazy_postflop: bool = bool(getattr(args, "lazy_postflop", True))

    # ---- Run the orchestrator ---------------------------------------------
    result = solve_chained(
        config,
        hero_range=hero_range,
        villain_range=villain_range,
        preflop_iterations=int(args.preflop_iterations),
        postflop_iterations=int(args.postflop_iterations),
        hero_player=int(getattr(args, "hero_player", 0)),
    )

    # ---- Optional postflop solve -----------------------------------------
    # If the user passed --board and lazy_postflop is enabled, solve the
    # postflop subgame for the top-N flop-reaching terminals ranked by
    # joint hero+villain reach weight. Solving every terminal (often
    # 50-300+ at deep stacks) would dominate CLI runtime; the top-N
    # captures the modal lines while keeping wall-clock reasonable.
    # Postflop solves are cached on the ``ChainedSolveResult``; users
    # who want others can call ``solve_postflop`` from Python.
    postflop_solves: dict[tuple, object] = {}
    if board_cards and lazy_postflop:
        board_tuple = tuple(board_cards)
        # Rank terminals by joint reach weight (sum of hero weights *
        # sum of villain weights — a proxy for "how often does this
        # line happen").
        ranked = sorted(
            result.continuation_ranges.items(),
            key=lambda kv: -(
                sum(kv[1].hero.values()) * sum(kv[1].villain.values())
            ),
        )
        top_n = int(getattr(args, "max_postflop_terminals", 5) or 5)
        for action_seq, _cont in ranked[:top_n]:
            try:
                pf = result.solve_postflop(action_seq, board_tuple)
            except (KeyError, ValueError):
                # solve_postflop raises ValueError for non-flop boards
                # (Phase A guards) and KeyError for missing sequences;
                # both already validated above so this is defensive.
                continue
            postflop_solves[action_seq] = pf

    # ---- Dispatch to the requested format --------------------------------
    if fmt == "json":
        _render_chained_json(
            args=args,
            board_cards=board_cards,
            result=result,
            postflop_solves=postflop_solves,
        )
        return 0
    if fmt == "csv":
        _render_chained_csv(
            result=result,
            postflop_solves=postflop_solves,
        )
        return 0
    _render_chained_text(
        args=args,
        board_cards=board_cards,
        result=result,
        postflop_solves=postflop_solves,
    )
    return 0


def _render_chained_text(
    *,
    args: argparse.Namespace,
    board_cards: list[Card],
    result,
    postflop_solves: dict,
) -> None:
    """Pretty-print the chained result in human-readable form."""
    print("Chained preflop solve")
    print("=" * 56)
    print(f"Hero range:      {args.hero_range}")
    print(f"Villain range:   {args.villain_range}")
    print(f"Stacks:          {args.stacks} BB")
    print(f"Preflop iters:   {args.preflop_iterations}")
    print(f"Postflop iters:  {args.postflop_iterations}")
    print(f"Position:        {result.preflop_result.position}")
    if board_cards:
        print(f"Flop:            {' '.join(str(c) for c in board_cards)}")
    print()

    # Preflop range aggregate (combo-weighted across hero classes).
    print("Preflop range aggregate (hero, combo-weighted):")
    agg = result.preflop_result.range_aggregate
    if agg:
        for label in sorted(agg.keys()):
            print(f"  {label:<14}  {agg[label]:.6f}")
    else:
        print("  (empty — preflop solve produced no first-decision aggregate)")
    print()

    # Per-class strategy matrix.
    print("Preflop per-class strategy:")
    per_class = result.preflop_result.per_class_strategy
    if per_class:
        for cls in sorted(per_class.keys()):
            freqs = per_class[cls]
            parts = [f"{lbl}={p:.3f}" for lbl, p in sorted(freqs.items())]
            print(f"  {cls:<6}  {'  '.join(parts)}")
    else:
        print("  (no per-class strategy)")
    print()

    # Continuation ranges per preflop terminal.
    cont_ranges = result.continuation_ranges
    if not cont_ranges:
        print("Continuation ranges: (none — every preflop terminal folded or "
              "went all-in)")
        return

    print(f"Continuation ranges ({len(cont_ranges)} flop-reaching terminals):")
    for action_seq in sorted(cont_ranges.keys()):
        cont = cont_ranges[action_seq]
        label = " ".join(action_seq) if action_seq else "(open)"
        print(f"  [{label}]  pot={cont.pot_chips} chips")
        hero_top = sorted(cont.hero.items(), key=lambda kv: -kv[1])[:8]
        vill_top = sorted(cont.villain.items(), key=lambda kv: -kv[1])[:8]
        hero_str = ", ".join(f"{k}({v:.1f})" for k, v in hero_top)
        vill_str = ", ".join(f"{k}({v:.1f})" for k, v in vill_top)
        print(f"    hero:    {hero_str}")
        print(f"    villain: {vill_str}")
    print()

    # Postflop strategy for the requested board.
    if board_cards and postflop_solves:
        print(f"Postflop strategy on {' '.join(str(c) for c in board_cards)}:")
        for action_seq in sorted(postflop_solves.keys()):
            pf = postflop_solves[action_seq]
            label = " ".join(action_seq) if action_seq else "(open)"
            print(f"  After [{label}]:")
            pf_per_class = pf.per_class_strategy
            if not pf_per_class:
                print("    (postflop solve produced no per-class strategy)")
                continue
            for cls in sorted(pf_per_class.keys()):
                freqs = pf_per_class[cls]
                parts = [f"{lbl}={p:.3f}" for lbl, p in sorted(freqs.items())]
                print(f"    {cls:<6}  {'  '.join(parts)}")
        print()
    elif board_cards and not postflop_solves:
        print("Postflop strategy: (no flop-reaching terminals to solve)")


def _render_chained_json(
    *,
    args: argparse.Namespace,
    board_cards: list[Card],
    result,
    postflop_solves: dict,
) -> None:
    """Emit the full ``ChainedSolveResult`` payload as JSON."""

    def _preflop_to_dict(pre) -> dict:
        return {
            "per_history_strategy": {
                k: list(v) for k, v in pre.per_history_strategy.items()
            },
            "per_class_strategy": {
                cls: dict(freqs) for cls, freqs in pre.per_class_strategy.items()
            },
            "range_aggregate": dict(pre.range_aggregate),
            "exploitability": pre.exploitability,
            "iterations": pre.iterations,
            "wall_clock_s": pre.wall_clock_s,
            "decision_node_count": pre.decision_node_count,
            "hand_count_per_player": list(pre.hand_count_per_player),
            "memory_profile": dict(pre.memory_profile),
            "backend": pre.backend,
            "position": pre.position,
            "warnings": list(pre.warnings),
        }

    def _postflop_to_dict(pf) -> dict:
        # Postflop per_history is off-path-CLEANED by DEFAULT (combos that
        # folded / went all-in / passively closed an earlier same-street
        # decision, plus board-blocked combos, are overwritten to fold);
        # ``--raw-offpath`` emits the raw rows. Each postflop subgame is a
        # ``RangeVsRangeNashResult`` (chained stores them as such), so it
        # carries ``per_history_strategy_view`` — the default-on clean
        # accessor that recovers the board from the keys and never mutates the
        # raw attribute. Hero is OOP postflop when the solve reports defender.
        raw_offpath = bool(getattr(args, "raw_offpath", False))
        per_history = pf.per_history_strategy_view(
            clean=not raw_offpath,
            hero_is_oop=pf.position == "defender",
        )
        return {
            "per_history_strategy": {k: list(v) for k, v in per_history.items()},
            "per_class_strategy": {
                cls: dict(freqs) for cls, freqs in pf.per_class_strategy.items()
            },
            "range_aggregate": dict(pf.range_aggregate),
            "exploitability": pf.exploitability,
            "iterations": pf.iterations,
            "wall_clock_s": pf.wall_clock_s,
            "backend": pf.backend,
            "position": pf.position,
            "hand_count_per_player": list(pf.hand_count_per_player),
        }

    cont_payload: dict[str, dict] = {}
    for action_seq, cont in result.continuation_ranges.items():
        key = " ".join(action_seq) if action_seq else "(open)"
        cont_payload[key] = {
            "action_sequence": list(action_seq),
            "hero": dict(cont.hero),
            "villain": dict(cont.villain),
            "pot_chips": cont.pot_chips,
        }

    postflop_payload: dict[str, dict] = {}
    for action_seq, pf in postflop_solves.items():
        key = " ".join(action_seq) if action_seq else "(open)"
        postflop_payload[key] = _postflop_to_dict(pf)

    payload = {
        "hero_range": args.hero_range,
        "villain_range": args.villain_range,
        "stacks_bb": args.stacks,
        "preflop_iterations": args.preflop_iterations,
        "postflop_iterations": args.postflop_iterations,
        "board": " ".join(str(c) for c in board_cards) if board_cards else None,
        "preflop_result": _preflop_to_dict(result.preflop_result),
        "continuation_ranges": cont_payload,
        "postflop_solves": postflop_payload,
    }
    print(_json.dumps(payload, indent=2, sort_keys=True))


def _render_chained_csv(
    *,
    result,
    postflop_solves: dict,
) -> None:
    """Emit per ``(action_sequence, hand_class, action, probability)`` rows.

    Layout::

        scope,action_sequence,hand_class,action,probability

    ``scope`` is ``"preflop"`` (per-class strategy at the root) or
    ``"postflop"`` (per-class strategy at the flop after the preceding
    action sequence). The ``action_sequence`` column is space-separated
    tokens; empty for the preflop root.
    """
    import csv as _csv_mod
    import io as _io_mod

    buf = _io_mod.StringIO()
    writer = _csv_mod.writer(buf)
    writer.writerow(
        ["scope", "action_sequence", "hand_class", "action", "probability"]
    )

    # Preflop per-class rows. ``action_sequence`` is empty at the root.
    per_class = result.preflop_result.per_class_strategy
    for cls in sorted(per_class.keys()):
        freqs = per_class[cls]
        for action_label in sorted(freqs.keys()):
            writer.writerow(
                [
                    "preflop",
                    "",
                    cls,
                    action_label,
                    f"{freqs[action_label]:.6f}",
                ]
            )

    # Postflop per-class rows per (action_sequence, board) solve.
    for action_seq in sorted(postflop_solves.keys()):
        pf = postflop_solves[action_seq]
        seq_str = " ".join(action_seq)
        for cls in sorted(pf.per_class_strategy.keys()):
            freqs = pf.per_class_strategy[cls]
            for action_label in sorted(freqs.keys()):
                writer.writerow(
                    [
                        "postflop",
                        seq_str,
                        cls,
                        action_label,
                        f"{freqs[action_label]:.6f}",
                    ]
                )

    print(buf.getvalue(), end="")


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

    v1.8.2 — new presentation modes via ``--walk-tree`` / ``--node`` /
    ``--format``. With NO new flags, the legacy first-decision aggregate
    output is preserved byte-for-byte (backward-compat invariant).

    Task #51 — kept as a thin wrapper that delegates to
    ``_run_subgame_solve`` with the river street pinned. The new
    ``subgame`` subcommand generalizes this to flop/turn/river; the
    ``river`` command remains a deprecated-but-functional alias so
    existing scripts (USAGE.md §7a, fixture invocations) keep working.
    """
    from poker_solver.hunl import Street

    # ``show_street_line=False`` preserves the legacy ``river`` preamble
    # byte-for-byte (no extra "Street: river" line). The ``subgame`` command
    # opts in.
    return _run_subgame_solve(args, street=Street.RIVER, show_street_line=False)


def _cmd_subgame(args: argparse.Namespace) -> int:
    """Task #51 — generalized subgame solve for flop/turn/river.

    Same engine + presentation pipeline as ``river``, parameterized on
    ``--street`` so the user can solve any postflop spot from the same CLI
    entry point. ``solve_hunl_postflop`` already supports all three streets
    via ``starting_street`` + ``initial_board`` (3/4/5 cards = flop/turn/
    river); this is purely a CLI surface that picks the right ``Street``
    enum and asserts the board-card count matches the requested street.

    Sample usage::

        poker-solver subgame --street flop --board "As 7c 2d" \\
            --hero AhKh --villain-range "QQ,JJ,AKs" --iters 200
        poker-solver subgame --street turn --board "As 7c 2d Kh" \\
            --hero AhKh --villain-range "QQ" --iters 50
        poker-solver subgame --street river --board "As 7c 2d Kh 5s" \\
            --hero AhKh --villain-range "QQ" --iters 50

    All v1.8.2 presentation knobs (``--walk-tree`` / ``--node`` /
    ``--format``) work uniformly across streets.
    """
    from poker_solver.hunl import Street

    street_map = {
        "flop": Street.FLOP,
        "turn": Street.TURN,
        "river": Street.RIVER,
    }
    street_name = str(getattr(args, "street", "river")).lower()
    if street_name not in street_map:
        raise ValueError(
            f"--street must be one of flop/turn/river; got {street_name!r}"
        )
    return _run_subgame_solve(
        args, street=street_map[street_name], show_street_line=True
    )


def _expected_board_count(street) -> int:
    """Number of board cards required for ``street`` (flop=3, turn=4, river=5)."""
    from poker_solver.hunl import Street

    if street == Street.FLOP:
        return 3
    if street == Street.TURN:
        return 4
    if street == Street.RIVER:
        return 5
    raise ValueError(f"unsupported subgame street: {street!r}")


def _run_subgame_solve(
    args: argparse.Namespace, *, street, show_street_line: bool = True
) -> int:
    """Shared core for ``river`` (deprecated alias) and ``subgame`` (#51).

    Dispatch policy (post-2026-05-27 follow-up to PR #61):

      - **Single-combo villain range** (e.g. ``--villain-range QdQh``):
        stays on the diagnostic fixed-hand path via ``solve_hunl_postflop``
        with ``initial_hole_cards = (hero_pair, villain_pair)``. True Nash
        is unnecessary in the 1v1 case (joint solve degenerates to a
        fixed-hand subgame).
      - **Multi-combo villain range, default**: route to
        :func:`poker_solver.range_aggregator.solve_range_vs_range_nash`
        once over the full villain range. Mathematically correct joint
        imperfect-information Nash; post-PR-114 (``TerminalCache``, ~213×
        speedup on river) it is competitive with — often faster than —
        the per-combo blueprint loop.
      - **--legacy-blueprint flag**: forces the original PR 39 / task #51
        behavior (per-combo loop + combo-weighted aggregate). Kept for
        backward-compat with pre-2026-05-27 outputs and for fast approximate
        13x13-style displays on dry boards.
      - **v1.8.2 presentation modes** (``--walk-tree`` / ``--node`` /
        ``--format=json|csv``) always go through the per-combo loop
        regardless of ``--legacy-blueprint``, because the tree-walk
        formatters require a full ``SolveResult`` per villain combo.

    ``show_street_line`` gates the new ``"Street: <name>"`` preamble line.
    The ``river`` alias passes ``False`` to keep its v1.8.2 output exactly
    as it shipped (the walk-tree tests assert no new markers in default
    mode); ``subgame`` passes ``True`` so the user can see which street
    was solved.
    """
    from poker_solver.hunl import HUNLConfig, HUNLPoker, Street
    from poker_solver.hunl_solver import solve_hunl_postflop

    expected_count = _expected_board_count(street)
    street_label = {
        Street.FLOP: "flop",
        Street.TURN: "turn",
        Street.RIVER: "river",
    }[street]

    board_cards = parse_board(args.board)
    if len(board_cards) != expected_count:
        raise ValueError(
            f"--board must specify {expected_count} {street_label} card"
            f"{'s' if expected_count != 1 else ''}; got {len(board_cards)}"
        )

    hero_cards = parse_hand(args.hero)
    if len(hero_cards) != 2:
        raise ValueError(
            f"--hero must be a 2-card hole (e.g. 'AhKh'); got {args.hero!r}"
        )
    hero_pair = (hero_cards[0], hero_cards[1])

    board_set = set(board_cards)
    if hero_pair[0] in board_set or hero_pair[1] in board_set:
        raise ValueError(f"--hero {args.hero!r} overlaps with --board {args.board!r}")

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

    # Per-spot accounting: 100 BB symmetric, dead-money pot of 10 BB
    # (matches the USAGE.md §3b convention; users can rebuild a custom config
    # in Python for non-standard stacks).
    big_blind = 100
    pot_bb, stack_bb = _resolve_pot_stack_bb(args)
    initial_pot = pot_bb * big_blind
    half = initial_pot // 2
    starting_stack = stack_bb * big_blind

    # v1.8.2 — extract new presentation knobs (all default to off, preserving
    # the legacy code path byte-for-byte). The variables persist across the
    # solve loop so we can route into walk-tree / drill-down formatters
    # after all per-combo solves complete.
    walk_tree_flag: bool = bool(getattr(args, "walk_tree", False))
    full_tree: bool = bool(getattr(args, "full_tree", False))
    node_history: str | None = getattr(args, "node", None)
    fmt: str = getattr(args, "format", "text") or "text"
    full_classes: bool = bool(getattr(args, "full_classes", False))
    top_n: int = int(getattr(args, "top_n", 12) or 12)
    new_mode = walk_tree_flag or node_history is not None or fmt != "text"

    legacy_blueprint: bool = bool(getattr(args, "legacy_blueprint", False))

    # Dispatch table (see docstring above):
    #   - single-combo villain range -> fixed-hand path (diagnostic)
    #   - multi-combo + new-mode (walk-tree/json/csv) -> per-combo loop
    #     (tree walkers need a SolveResult per combo)
    #   - multi-combo + --legacy-blueprint -> per-combo loop
    #   - multi-combo, default text mode, no legacy flag -> true Nash
    use_true_nash = (
        len(villain_combos) >= 2
        and not legacy_blueprint
        and not new_mode
    )

    if use_true_nash:
        return _run_subgame_true_nash(
            hero_pair=hero_pair,
            board_cards=board_cards,
            street=street,
            street_label=street_label,
            show_street_line=show_street_line,
            villain_range_spec=args.villain_range,
            villain_combos=villain_combos,
            starting_stack=starting_stack,
            big_blind=big_blind,
            initial_pot=initial_pot,
            half=half,
            iters=args.iters,
        )

    # When in text mode (default formatter), emit the v1.9.0 SPOT CONFIG
    # header followed by the legacy preamble. JSON / CSV modes suppress
    # both so the output is parser-friendly.
    if fmt == "text":
        # v1.9.0 — SPOT CONFIG header block (commercial-UX parity). Uses
        # the engine's default action-abstraction bet menu + raise cap
        # since the river/subgame commands don't expose --bet-sizes (the
        # ad-hoc postflop `solve --hunl-mode postflop` path does); we
        # surface those defaults so the user sees the menu they're
        # solving against.
        from poker_solver.action_abstraction import ActionContext as _ActionCtx

        default_bet_menu = _ActionCtx.__dataclass_fields__[
            "bet_size_fractions"
        ].default
        default_raise_cap = _ActionCtx.__dataclass_fields__[
            "postflop_raise_cap"
        ].default
        _print_spot_header(
            starting_stack_chips=starting_stack,
            initial_pot_chips=initial_pot,
            board_cards=board_cards,
            street_label=street_label,
            bet_size_fractions=default_bet_menu,
            raise_cap=default_raise_cap,
        )
        print(f"Board:        {' '.join(str(c) for c in board_cards)}")
        if show_street_line:
            print(f"Street:       {street_label}")
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
    # v1.8.2: when new modes are active we retain the full per-combo solve
    # result so walk_tree / drill-down can re-walk the engine tree. Held in
    # insertion order; combos are keyed by their canonical 4-char hole
    # label (matches the infoset_key hole prefix).
    per_combo_results: dict[str, object] = {}
    per_combo_cfgs: dict[str, HUNLConfig] = {}

    for villain_pair in villain_combos:
        cfg = HUNLConfig(
            starting_stack=starting_stack,
            small_blind=big_blind // 2,
            big_blind=big_blind,
            starting_street=street,
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
            if len(key.split("|")) == 4 and _hole_matches(key.split("|")[0], hero_pair)
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
        if new_mode:
            # Canonicalize the combo to its sorted-string form so it matches
            # the infoset_key hole prefix.
            combo_label = _sorted_combo_label(villain_pair)
            per_combo_results[combo_label] = result
            per_combo_cfgs[combo_label] = cfg

    if total_weight == 0:
        raise ValueError("no hero infosets aggregated (unexpected)")
    for k in aggregate:
        aggregate[k] /= total_weight

    # ---- v1.8.2 new-mode dispatch (walk-tree / node drill-down / format) ----
    if new_mode:
        return _render_new_mode(
            per_combo_results=per_combo_results,
            per_combo_cfgs=per_combo_cfgs,
            hero_pair=hero_pair,
            board_cards=board_cards,
            walk_tree_flag=walk_tree_flag,
            full_tree=full_tree,
            node_history=node_history,
            fmt=fmt,
            full_classes=full_classes,
            top_n=top_n,
            villain_range_spec=args.villain_range,
            iters=args.iters,
            mean_ev=ev_sum / total_weight,
            HUNLPoker_cls=HUNLPoker,
        )

    # Legacy default-mode output (preserved byte-for-byte from PR 39).
    print("Hero first-decision aggregate (average over villain combos):")
    for k in sorted(aggregate):
        print(f"  {k:<10}  {aggregate[k]:.6f}")
    print(f"\nMean game value (BB, P0 perspective): {ev_sum / total_weight:+.6f}")
    return 0


def _run_subgame_true_nash(
    *,
    hero_pair: tuple,
    board_cards: list,
    street,
    street_label: str,
    show_street_line: bool,
    villain_range_spec: str,
    villain_combos: list,
    starting_stack: int,
    big_blind: int,
    initial_pot: int,
    half: int,
    iters: int,
) -> int:
    """Default multi-combo dispatch (post-2026-05-27): route to true joint-Nash.

    Builds a single ``HUNLConfig`` whose ``initial_hole_cards`` is the empty
    tuple (vector-form CFR's required convention; the solver enumerates
    hands per-player internally), constructs a hero "range" containing just
    ``hero_pair`` and a villain range containing every board-feasible combo
    from ``--villain-range``, then dispatches to
    :func:`poker_solver.range_aggregator.solve_range_vs_range_nash`.

    The output format mirrors the legacy per-combo loop's text mode for
    backward compatibility: a "Board / Hero / Villain range / Iterations"
    preamble followed by a hero first-decision frequency table.  The keys
    in the frequency table are the engine's action labels (e.g. ``fold`` /
    ``check`` / ``bet_75``) rather than the positional ``action_0`` /
    ``action_1`` keys the legacy loop emits; callers parsing the output
    should consume the engine labels (preferred) or pass
    ``--legacy-blueprint`` for the positional keys.
    """
    from poker_solver.hunl import HUNLConfig
    from poker_solver.range import Range
    from poker_solver.range_aggregator import solve_range_vs_range_nash

    cfg = HUNLConfig(
        starting_stack=starting_stack,
        small_blind=big_blind // 2,
        big_blind=big_blind,
        starting_street=street,
        initial_board=tuple(board_cards),
        initial_pot=initial_pot,
        initial_contributions=(half, half),
        # vector-form CFR requires empty hole cards; the solver enumerates
        # hands per-player from the supplied ranges.
        initial_hole_cards=(),
    )

    hero_range_obj = Range()
    hero_range_obj.add(hero_pair)
    villain_range_obj = Range()
    for combo in villain_combos:
        villain_range_obj.add(combo)

    # v1.9.0 — SPOT CONFIG header block.
    from poker_solver.action_abstraction import ActionContext as _ActionCtx

    default_bet_menu = _ActionCtx.__dataclass_fields__[
        "bet_size_fractions"
    ].default
    default_raise_cap = _ActionCtx.__dataclass_fields__[
        "postflop_raise_cap"
    ].default
    _print_spot_header(
        starting_stack_chips=starting_stack,
        initial_pot_chips=initial_pot,
        board_cards=board_cards,
        street_label=street_label,
        bet_size_fractions=default_bet_menu,
        raise_cap=default_raise_cap,
    )
    print(f"Board:        {' '.join(str(c) for c in board_cards)}")
    if show_street_line:
        print(f"Street:       {street_label}")
    print(f"Hero:         {' '.join(str(c) for c in hero_pair)}")
    print(
        f"Villain range: {villain_range_spec} "
        f"({len(villain_combos)} combos after card removal)"
    )
    print(f"Iterations:   {iters}")
    print(f"Backend:      true_nash (solve_range_vs_range_nash)")
    print()

    result = solve_range_vs_range_nash(
        cfg,
        hero_range_obj,
        villain_range_obj,
        iterations=iters,
        hero_player=0,
        compute_exploitability_at_end=False,
    )

    # The projection produces hero's first-decision strategy per hand class;
    # the hero range contains exactly one combo so the per_class_strategy
    # has one entry whose action map is hero's strategy at the root.
    aggregate: dict[str, float] = dict(result.range_aggregate)

    print("Hero first-decision aggregate (range-vs-range Nash):")
    if aggregate:
        for k in sorted(aggregate):
            print(f"  {k:<10}  {aggregate[k]:.6f}")
    else:
        print("  (no first-decision strategy found — hero may never reach a")
        print("   decision on the betting tree's modal villain line.)")
    # range_aggregate doesn't carry a hero game-value field; the headline
    # game value lives on the solver-internal exploitability path. Emit the
    # backend tag so callers can disambiguate from the legacy loop output.
    print()
    print(f"Backend reported: {result.backend}  wall_clock={result.wall_clock_s:.3f}s")
    return 0


def _sorted_combo_label(combo: tuple) -> str:
    """Sort a (Card, Card) tuple by (rank, suit) ascending and stringify.

    Matches the sort used by ``_sorted_card_string`` inside the HUNL
    infoset_key — i.e. ``"QcQh"`` (Qc < Qh by suit ordering, where the
    engine sorts ascending). The infoset_key prefix for the player-1 hole
    is exactly this string.
    """
    c1, c2 = combo
    if (c1.rank, c1.suit) > (c2.rank, c2.suit):
        c1, c2 = c2, c1
    return f"{c1}{c2}"


def _render_new_mode(
    *,
    per_combo_results: dict[str, object],
    per_combo_cfgs: dict,
    hero_pair: tuple,
    board_cards: list,
    walk_tree_flag: bool,
    full_tree: bool,
    node_history: str | None,
    fmt: str,
    full_classes: bool,
    top_n: int,
    villain_range_spec: str,
    iters: int,
    mean_ev: float,
    HUNLPoker_cls: type,
) -> int:
    """Dispatch into the v1.8.2 walk-tree / drill-down / format paths.

    Pulled out of ``_cmd_river`` to keep the legacy code path readable. All
    state passed in explicitly so this stays a pure presentation function.
    """
    from poker_solver.cli_bb_format import (
        canonical_history_for_user_node,
        canonical_node_id_for_history,
    )
    from poker_solver.cli_tree_walk import (
        aggregate_class_strategies,
        compute_mdf_threshold,
        format_per_class_text,
        format_text,
        walk_tree,
    )

    # Walk every per-combo result; cache (combo_label -> nodes).
    # v1.8.2 (#47) — thread engine-computed reach + off-path keys when
    # the SolveResult carries them. The solver-level annotation is more
    # accurate than the per-walk heuristic (accounts for joint reach
    # including opponent strategy + chance prob); falls back to the
    # legacy heuristic when the result lacks the fields.
    per_combo_nodes: dict[str, list] = {}
    per_combo_games: dict[str, object] = {}
    for combo_label, result in per_combo_results.items():
        cfg = per_combo_cfgs[combo_label]
        game = HUNLPoker_cls(cfg)
        per_combo_games[combo_label] = game
        reach_lookup = getattr(result, "reach_probability", None) or None
        off_keys = getattr(result, "off_path_keys", None) or None
        nodes = walk_tree(
            game,
            result.average_strategy,  # type: ignore[attr-defined]
            include_off_path=full_tree,
            reach_lookup=reach_lookup,
            off_path_keys=off_keys,
        )
        per_combo_nodes[combo_label] = nodes

    # v1.9.0 — translate the user-supplied --node string into the engine's
    # canonical chip-token form. ``node_history`` will be the engine-form
    # string used for lookups below; ``node_history_user`` is what the
    # caller passed in (preserved for error messages so we don't surprise
    # the user with normalization rewrites).
    node_history_user = node_history
    if node_history is not None and node_history != "":
        # Use the first per-combo game to walk the tree; all combos share
        # the same betting structure since they only differ by hole cards.
        ref_game = next(iter(per_combo_games.values()))
        try:
            node_history = canonical_history_for_user_node(
                node_history, ref_game, None,
            )
        except ValueError as exc:
            print(f"error: {exc}", file=__import__("sys").stderr)
            return 2

    if fmt == "json":
        # Full dict dump — every combo, every node.
        out_payload: dict = {
            "board": " ".join(str(c) for c in board_cards),
            "hero": "".join(str(c) for c in hero_pair),
            "villain_range": villain_range_spec,
            "iterations": iters,
            "mean_game_value_bb": mean_ev,
            "combos": {},
        }
        for combo_label, nodes in per_combo_nodes.items():
            out_payload["combos"][combo_label] = _nodes_to_json(nodes)
        print(_json.dumps(out_payload, indent=2, sort_keys=True))
        return 0

    if fmt == "csv":
        # One CSV body covering all combos. Reuse the per-combo formatter
        # with the combo label as the hand_class column.
        import csv as _csv_mod
        import io as _io_mod

        buf = _io_mod.StringIO()
        writer = _csv_mod.writer(buf)
        writer.writerow(
            ["combo", "node_history", "action_label", "probability", "reach_prob"]
        )
        for combo_label, nodes in per_combo_nodes.items():
            for node in nodes:
                for _, label, prob in node.actions:
                    writer.writerow(
                        [
                            combo_label,
                            node.history or "(root)",
                            label,
                            f"{prob:.6f}",
                            f"{node.reach_prob:.6f}",
                        ]
                    )
        print(buf.getvalue(), end="")
        return 0

    # Text mode — walk-tree and/or node drill-down.
    if node_history is not None:
        # Drill-down: aggregate per-class strategy at the requested history.
        classes = aggregate_class_strategies(per_combo_nodes, node_history)
        if not classes:
            display_node = node_history_user or node_history
            print(
                f"No nodes match history {display_node!r} for any villain combo. "
                "Try a shorter / different history "
                "(e.g. 'check.bet33pct', 'b330')."
            )
            return 0
        # Determine the MDF threshold from the first matching combo (all
        # combos share state at the same history, so action_ctx.to_call and
        # pot are identical).
        mdf: float | None = None
        for nodes in per_combo_nodes.values():
            for n in nodes:
                if n.history == node_history:
                    # Re-derive ActionContext via a fresh game walk.
                    cfg = next(iter(per_combo_cfgs.values()))
                    game = HUNLPoker_cls(cfg)
                    ctx = _action_ctx_at_history(game, node_history)
                    if ctx is not None:
                        mdf = compute_mdf_threshold(ctx)
                    break
            if mdf is not None:
                break
        out = format_per_class_text(
            classes,
            node_history,
            top_n=None if full_classes else top_n,
            mdf_threshold=mdf,
        )
        print(out)
        return 0

    # Plain --walk-tree (no --node): print each combo's tree.
    if walk_tree_flag:
        for combo_label, nodes in per_combo_nodes.items():
            title = (
                f"Villain combo {combo_label} — {len(nodes)} on-path nodes"
                + (" (incl. off-path phantoms)" if full_tree else "")
            )
            game = per_combo_games[combo_label]
            # v1.9.0 — translate each engine history into the BB-native
            # canonical id for the [--node "..."] right-margin annotation.
            def _node_id_fn(history: str, _g=game) -> str:
                return canonical_node_id_for_history(history, _g)
            print(
                format_text(
                    nodes,
                    title=title,
                    include_off_path=full_tree,
                    node_id_for_history=_node_id_fn,
                )
            )
        print(f"Mean game value (BB, P0 perspective): {mean_ev:+.6f}")
        return 0

    # Should not reach here — new_mode triggered something but no branch matched.
    print("(no presentation mode selected)")
    return 0


def _nodes_to_json(nodes: list) -> list[dict]:
    """Serialize a list of TreeNodes to JSON-ready dicts."""
    out: list[dict] = []
    for node in nodes:
        out.append(
            {
                "history": node.history,
                "player": node.player,
                "hole_label": node.hole_label,
                "infoset_key": node.infoset_key,
                "reach_prob": node.reach_prob,
                "off_path": node.off_path,
                "actions": [
                    {"action_id": aid, "label": label, "prob": prob}
                    for aid, label, prob in node.actions
                ],
            }
        )
    return out


def _action_ctx_at_history(game, history: str):
    """Re-walk the engine to the state at ``history`` and return its ActionContext.

    Returns ``None`` if the history is unreachable (e.g. token sequence
    inconsistent with the engine's state machine).
    """
    from poker_solver.cli_tree_walk import _split_history_tokens, parse_token

    state = game.initial_state()
    # Advance past chance root.
    while game.current_player(state) == -1 and not game.is_terminal(state):
        outcomes = game.chance_outcomes(state)
        if not outcomes:
            return None
        state = game.apply(state, outcomes[0][0])
    for tok in _split_history_tokens(history):
        kind, amt = parse_token(tok)
        legal = game.legal_actions(state)
        ctx = game._action_context(state)  # type: ignore[attr-defined]
        match = _action_id_for_token(kind, amt, legal, ctx)
        if match is None:
            return None
        state = game.apply(state, match)
        if game.is_terminal(state):
            return None
    if game.current_player(state) == -1:
        return None
    return game._action_context(state)  # type: ignore[attr-defined]


def _action_id_for_token(kind: str, amt, legal: list, ctx) -> int | None:
    """Map a single (kind, amount) history token to a legal action ID.

    Walks the legal-action list at the current state and selects the one
    whose computed chip amount matches. Returns ``None`` when no match
    (caller should treat this as "history unreachable in current config").
    """
    from poker_solver.action_abstraction import (
        ACTION_ALL_IN,
        ACTION_CALL,
        ACTION_CHECK,
        ACTION_FOLD,
        compute_bet_amount,
        compute_raise_to,
    )

    if kind == "f":
        return ACTION_FOLD if ACTION_FOLD in legal else None
    if kind == "x":
        return ACTION_CHECK if ACTION_CHECK in legal else None
    if kind == "c":
        return ACTION_CALL if ACTION_CALL in legal else None
    if kind == "A":
        return ACTION_ALL_IN if ACTION_ALL_IN in legal else None
    if kind == "b":
        for aid in legal:
            # ACTION_BET_33..BET_200 are ids 3..7.
            if 3 <= aid <= 7 and compute_bet_amount(aid, ctx) == amt:
                return aid
        return None
    if kind == "r":
        for aid in legal:
            # ACTION_RAISE_33..RAISE_200 are ids 8..12.
            if 8 <= aid <= 12 and compute_raise_to(aid, ctx) == amt:
                return aid
        return None
    return None


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

    # Forward the C1 per-street bet menus + raise multipliers if the spot
    # carries them (older RiverSpot fixtures don't; getattr keeps us tolerant
    # of both). When absent, per-street menus stay None (engine falls back to
    # the flat ``bet_size_fractions``) and raise sizes keep the engine default.
    spot_raise_xs = getattr(spot, "raise_size_xs", None)
    spot_raise_size_xs: tuple[float, ...] = (
        tuple(float(x) for x in spot_raise_xs) if spot_raise_xs else (3.0,)
    )
    cfg = HUNLConfig(
        starting_stack=spot.stack + spot.pot // 2,
        small_blind=50,
        big_blind=100,
        starting_street=Street.RIVER,
        initial_board=tuple(spot.board),
        initial_pot=spot.pot,
        initial_contributions=(spot.pot // 2, spot.pot // 2),
        bet_size_fractions=spot.bet_sizes,
        flop_bet_fractions=getattr(spot, "flop_bet_fractions", None),
        turn_bet_fractions=getattr(spot, "turn_bet_fractions", None),
        river_bet_fractions=getattr(spot, "river_bet_fractions", None),
        include_all_in=spot.include_all_in,
        postflop_raise_cap=spot.max_raises,
        raise_size_xs=spot_raise_size_xs,
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
    parser.add_argument(
        "--version",
        action="version",
        version=f"poker-solver {__version__}",
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
            "for postflop bet sizing. Used as the flat/fallback menu for any "
            "street without a per-street override. Default: the full 5-size "
            "menu. All-in always available."
        ),
    )
    sv.add_argument(
        "--flop-bet-sizes",
        type=str,
        default=None,
        help=(
            "Per-street override for FLOP opening-bet sizing (comma-separated "
            "pot-fraction percentages, e.g. '33,75'). When omitted, the flop "
            "uses --bet-sizes."
        ),
    )
    sv.add_argument(
        "--turn-bet-sizes",
        type=str,
        default=None,
        help=(
            "Per-street override for TURN opening-bet sizing (comma-separated "
            "pot-fraction percentages). When omitted, the turn uses --bet-sizes."
        ),
    )
    sv.add_argument(
        "--river-bet-sizes",
        type=str,
        default=None,
        help=(
            "Per-street override for RIVER opening-bet sizing (comma-separated "
            "pot-fraction percentages). When omitted, the river uses "
            "--bet-sizes."
        ),
    )
    sv.add_argument(
        "--raise-sizes",
        type=str,
        default=None,
        help=(
            "Comma-separated raise MULTIPLIERS of the bet being faced (e.g. "
            "'2.5,3' = 2.5x/3x). Note: multipliers, NOT pot-fraction "
            "percentages. Default: 3.0x. At most 5 raise sizes."
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
    sv.add_argument(
        "--regret-init-noise",
        type=float,
        default=0.0,
        help=(
            "PR 90 (A83 Track A) — symmetry-breaking magnitude for the "
            "initial regret_sum at each infoset. Default 0.0 (bit-"
            "identical to the prior all-zero initialization). Non-zero "
            "values seed regret_sum[a] with epsilon * U(-1, 1) via a "
            "deterministic PRNG seeded by --rng-seed. Used to probe Nash "
            "multiplicity at deep-cap indifference manifolds: two solves "
            "at epsilon=0 vs epsilon=1e-9 that converge to materially "
            "different strategies empirically confirm Nash multiplicity. "
            "See docs/a83_track_a_setup_2026-05-26.md."
        ),
    )
    sv.add_argument(
        "--rng-seed",
        type=int,
        default=0,
        help=(
            "Seed for the deterministic PRNG used by --regret-init-noise. "
            "Same value across runs reproduces the perturbation pattern "
            "exactly. Ignored when --regret-init-noise is 0.0 (the "
            "default)."
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
        help=(
            "Solve a river spot with fixed hero cards vs a villain range. "
            "[DEPRECATED] Use 'subgame --street river ...' for new scripts; "
            "this alias is retained for backward compat (task #51)."
        ),
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
    # v1.9.0 — canonical BB flags (no -bb suffix; BB implicit). The
    # ``--pot-bb`` / ``--stack-bb`` legacy aliases below stay functional
    # with a deprecation warning emitted to stderr on first use.
    rv.add_argument(
        "--pot",
        type=int,
        default=None,
        help="Starting pot in BB (v1.9.0 canonical; default 10).",
    )
    rv.add_argument(
        "--stack",
        type=int,
        default=None,
        help="Per-player effective stack in BB (v1.9.0 canonical; default 100).",
    )
    rv.add_argument(
        "--pot-bb",
        type=int,
        default=None,
        help="[DEPRECATED v1.9.0] Use --pot. Kept for backward compat.",
    )
    rv.add_argument(
        "--stack-bb",
        type=int,
        default=None,
        help="[DEPRECATED v1.9.0] Use --stack. Kept for backward compat.",
    )
    # v1.8.2 — tree-walk presentation modes. Defaults preserve the legacy
    # first-decision aggregate output byte-for-byte (no new flags = no
    # behavior change).
    rv.add_argument(
        "--walk-tree",
        action="store_true",
        help=(
            "Walk the full decision tree and print every on-path node "
            "(reach prob > 1e-4) with action-label decoding and ASCII bar "
            "charts. Default: off (legacy first-decision aggregate)."
        ),
    )
    rv.add_argument(
        "--full-tree",
        action="store_true",
        help=(
            "When combined with --walk-tree, also emit off-path phantom "
            "nodes (reach prob <= 1e-4) marked [OFF-PATH]. Default: off."
        ),
    )
    rv.add_argument(
        "--node",
        type=str,
        default=None,
        help=(
            "Drill into a specific decision node by its history string "
            "(e.g. 'xb750' = villain checks, hero bets 750). For range "
            "queries, prints per-hand-class strategy at that node."
        ),
    )
    rv.add_argument(
        "--top-n",
        type=int,
        default=12,
        help=(
            "When --node selects a per-class drill-down, show only the "
            "top-N hand classes by Shannon entropy (mixing hands ranked "
            "first). Default: 12."
        ),
    )
    rv.add_argument(
        "--full-classes",
        action="store_true",
        help=(
            "With --node, show ALL hand classes (no top-N truncation). "
            "Default: off."
        ),
    )
    rv.add_argument(
        "--format",
        choices=("text", "json", "csv"),
        default="text",
        help=(
            "Output format. 'text' (default) prints the pretty tree; "
            "'json' dumps the full strategy dict per combo/node/action; "
            "'csv' emits (combo, node_history, action_label, probability, "
            "reach_prob) rows with a header."
        ),
    )
    rv.add_argument(
        "--legacy-blueprint",
        action="store_true",
        help=(
            "Force the legacy per-combo blueprint-shape loop (the original "
            "PR 39 behavior): solve each (hero, villain_combo) as an "
            "independent 1v1 subgame and aggregate the resulting hero-action "
            "frequencies by combo weight. Default (off) routes multi-combo "
            "villain ranges through `solve_range_vs_range_nash` for a "
            "joint-Nash solve (mathematically correct, faster post PR #114). "
            "Use this flag for backward-compat with pre-2026-05-27 outputs "
            "or for fast approximate 13x13-style displays on dry boards. "
            "Single-combo villain ranges always use the diagnostic "
            "fixed-hand path (`solve_hunl_postflop`) regardless of this flag."
        ),
    )
    rv.set_defaults(func=_cmd_river)

    # ---- Task #51: generalized subgame command for flop/turn/river ----
    # The engine's ``solve_hunl_postflop`` already supports all postflop
    # streets via ``starting_street`` + ``initial_board`` (3/4/5 cards =
    # flop/turn/river); this is purely a CLI surface that lets the user
    # pick the street explicitly. The legacy ``river`` subcommand
    # continues to work as a deprecated-but-functional alias so existing
    # scripts don't break.
    sg = sub.add_parser(
        "subgame",
        help=(
            "Solve a postflop subgame (flop/turn/river) with fixed hero "
            "cards vs a villain range. Generalizes the deprecated `river` "
            "command (task #51)."
        ),
    )
    sg.add_argument(
        "--street",
        choices=("flop", "turn", "river"),
        required=True,
        help=(
            "Which postflop street to solve. The --board card count must "
            "match: 3 for flop, 4 for turn, 5 for river."
        ),
    )
    sg.add_argument(
        "--board",
        type=str,
        required=True,
        help=(
            "Community cards: 3 for flop ('As 7c 2d'), 4 for turn "
            "('As 7c 2d Kh'), 5 for river ('As 7c 2d Kh 5s')."
        ),
    )
    sg.add_argument(
        "--hero",
        type=str,
        required=True,
        help="Hero's 2-card hole, e.g. 'AhKh'.",
    )
    sg.add_argument(
        "--villain-range",
        type=str,
        required=True,
        help="Villain range in PioSolver notation, e.g. 'QQ,JJ,AKs'.",
    )
    sg.add_argument(
        "--iters",
        type=int,
        default=200,
        help="DCFR iterations per per-combo solve (default: 200).",
    )
    # v1.9.0 — canonical BB flags. Mirror of `river` (see that block for
    # the deprecation policy).
    sg.add_argument(
        "--pot",
        type=int,
        default=None,
        help="Starting pot in BB (v1.9.0 canonical; default 10).",
    )
    sg.add_argument(
        "--stack",
        type=int,
        default=None,
        help="Per-player effective stack in BB (v1.9.0 canonical; default 100).",
    )
    sg.add_argument(
        "--pot-bb",
        type=int,
        default=None,
        help="[DEPRECATED v1.9.0] Use --pot. Kept for backward compat.",
    )
    sg.add_argument(
        "--stack-bb",
        type=int,
        default=None,
        help="[DEPRECATED v1.9.0] Use --stack. Kept for backward compat.",
    )
    # v1.8.2 — tree-walk presentation modes (same set as `river`).
    sg.add_argument(
        "--walk-tree",
        action="store_true",
        help=(
            "Walk the full decision tree and print every on-path node "
            "(reach prob > 1e-4) with action-label decoding and ASCII bar "
            "charts. Default: off (legacy first-decision aggregate)."
        ),
    )
    sg.add_argument(
        "--full-tree",
        action="store_true",
        help=(
            "When combined with --walk-tree, also emit off-path phantom "
            "nodes (reach prob <= 1e-4) marked [OFF-PATH]. Default: off."
        ),
    )
    sg.add_argument(
        "--node",
        type=str,
        default=None,
        help=(
            "Drill into a specific decision node by its history string "
            "(e.g. 'xb750' = villain checks, hero bets 750). For range "
            "queries, prints per-hand-class strategy at that node."
        ),
    )
    sg.add_argument(
        "--top-n",
        type=int,
        default=12,
        help=(
            "When --node selects a per-class drill-down, show only the "
            "top-N hand classes by Shannon entropy (mixing hands ranked "
            "first). Default: 12."
        ),
    )
    sg.add_argument(
        "--full-classes",
        action="store_true",
        help=(
            "With --node, show ALL hand classes (no top-N truncation). "
            "Default: off."
        ),
    )
    sg.add_argument(
        "--format",
        choices=("text", "json", "csv"),
        default="text",
        help=(
            "Output format. 'text' (default) prints the pretty tree; "
            "'json' dumps the full strategy dict per combo/node/action; "
            "'csv' emits (combo, node_history, action_label, probability, "
            "reach_prob) rows with a header."
        ),
    )
    sg.add_argument(
        "--legacy-blueprint",
        action="store_true",
        help=(
            "Force the legacy per-combo blueprint-shape loop. Same semantics "
            "as the `river --legacy-blueprint` flag (see that flag's help)."
        ),
    )
    sg.set_defaults(func=_cmd_subgame)

    # ---- Task #58: chained preflop -> lazy postflop orchestrator CLI ----
    ch = sub.add_parser(
        "chained",
        help=(
            "Chained preflop range solve + per-action continuation ranges "
            "+ optional lazy postflop flop solve (task #58, #31 Phase D)."
        ),
    )
    ch.add_argument(
        "--hero-range",
        type=str,
        required=True,
        help=(
            "Hero range in PioSolver notation, e.g. 'AA,KK,AKs'. Concrete "
            "combos collapse to hand classes (AA / AKs / 76o) internally."
        ),
    )
    ch.add_argument(
        "--villain-range",
        type=str,
        required=True,
        help="Villain range in PioSolver notation, e.g. 'AA,KK,AKs,76s'.",
    )
    ch.add_argument(
        "--stacks",
        type=int,
        default=100,
        help="Per-player effective stack in BB (default 100).",
    )
    ch.add_argument(
        "--preflop-iterations",
        type=int,
        default=1000,
        help="DCFR iterations per per-pair preflop solve (default 1000).",
    )
    ch.add_argument(
        "--postflop-iterations",
        type=int,
        default=500,
        help=(
            "DCFR iterations passed to the lazy postflop solve (default "
            "500; only fires when --board is set and --lazy-postflop is "
            "true)."
        ),
    )
    ch.add_argument(
        "--board",
        type=str,
        default=None,
        help=(
            "Optional 3-card flop (e.g. 'Ks 8d 2h'). When set, the chained "
            "orchestrator also runs the lazy postflop solve for this flop "
            "after every preflop terminal that reaches it; the postflop "
            "strategy appears in the text/JSON/CSV output."
        ),
    )
    ch.add_argument(
        "--hero-player",
        type=int,
        choices=(0, 1),
        default=0,
        help=(
            "Hero seat: 0 = aggressor / SB-button (default), 1 = defender "
            "/ BB. Reported preflop / postflop frequencies are this "
            "player's."
        ),
    )
    ch.add_argument(
        "--format",
        choices=("text", "json", "csv"),
        default="text",
        help=(
            "Output format: 'text' (default, human-readable preflop "
            "matrix + per-action continuation ranges + optional flop "
            "strategy); 'json' (full ChainedSolveResult dict dump); "
            "'csv' (one row per (action_sequence, hand_class, action, "
            "probability) for piping)."
        ),
    )
    ch.add_argument(
        "--lazy-postflop",
        type=_str_to_bool,
        default=True,
        help=(
            "Whether the postflop solve should fire when --board is set. "
            "Default 'true'. Pass 'false' to print the preflop + "
            "continuation ranges only (skips the lazy postflop)."
        ),
    )
    ch.add_argument(
        "--max-postflop-terminals",
        type=int,
        default=5,
        help=(
            "When --board is set + lazy postflop on, solve the top-N "
            "flop-reaching terminals ranked by joint hero+villain reach "
            "weight (default 5). Solving every terminal (often 50-300+ "
            "at deep stacks) is prohibitively slow; the cap keeps the "
            "CLI usable. Callers who want every terminal can drive "
            "``ChainedSolveResult.solve_postflop`` from Python."
        ),
    )
    ch.add_argument(
        "--raw-offpath",
        action="store_true",
        help=(
            "Emit the RAW postflop per_history_strategy in JSON output (every "
            "combo at every node, including off-path folds/all-ins/closed "
            "lines and board-blocked combos). By default the JSON output is "
            "off-path-CLEANED: such combos are overwritten to fold."
        ),
    )
    ch.set_defaults(func=_cmd_chained)

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

    # ---- PR 76: exploitative best-response subcommand ----
    br = sub.add_parser(
        "best-response",
        help=(
            "Compute hero's deterministic best-response against a fixed "
            "opponent strategy (PR 76 — exploitative play)."
        ),
    )
    br.add_argument(
        "--opponent",
        type=str,
        required=True,
        help=(
            "Path to opponent strategy JSON. Schema per "
            "docs/pr_proposals/v1_exploitative_play_spec.md §5: top-level "
            "object containing `strategy: {infoset_key: [probs]}`."
        ),
    )
    br.add_argument(
        "--hero-position",
        choices=("SB", "BB"),
        required=True,
        help="Hero seat: SB (player 0) or BB (player 1).",
    )
    br.add_argument(
        "--game",
        choices=sorted(_GAMES.keys()),
        required=True,
        help="Which game the strategy is over (kuhn, leduc, hunl).",
    )
    # HUNL knobs (mirror `solve` subcommand for ad-hoc postflop spots).
    br.add_argument("--hunl-mode", choices=("tiny_subgame", "postflop"), default="tiny_subgame")
    br.add_argument("--board", type=str, default=None)
    br.add_argument("--stacks", type=int, default=100)
    br.add_argument("--bet-sizes", type=str, default=None)
    br.add_argument("--abstraction", type=str, default=None)
    br.add_argument(
        "--output",
        type=str,
        default=None,
        help=(
            "When set, write hero's BR strategy + summary as JSON to this "
            "path. Else only print the summary to stdout."
        ),
    )
    br.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable summary to stdout instead of human-readable.",
    )
    br.set_defaults(func=_cmd_best_response)

    # ---- PR 11: batch-solve top-level subcommand ----
    bs = sub.add_parser(
        "batch-solve",
        help="Solve a CSV of spots and write results to the library (PR 11 Agent C).",
    )
    bs.add_argument("--input", type=str, required=True, help="Path to the CSV input.")
    bs.add_argument("--workers", type=int, default=1)
    bs.add_argument("--max-memory-gb", type=float, default=14.0)
    bs.add_argument("--dry-run", action="store_true")
    # W2.4 (#59): backend dispatch. Default ``python`` keeps PR 11 Agent C's
    # original overnight-solve behavior identical; ``rust`` routes per-row
    # through ``solve_range_vs_range_nash`` for the ~213× river speedup
    # that lifts the 180s CLI timeout Sarah hit on iter=10 runs.
    bs.add_argument(
        "--backend",
        choices=("python", "rust"),
        default="python",
        help="Solver backend: 'python' (default, DCFR reference via "
        "solve_hunl_postflop) or 'rust' (W2.4, solve_range_vs_range_nash, "
        "~213x faster on river per PR 114). Use 'rust' when the CSV row "
        "specifies hero_range/villain_range columns (optional; broad "
        "defaults apply otherwise).",
    )
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
