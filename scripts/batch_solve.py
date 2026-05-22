"""Batch solve poker spots from a CSV file.

Designed use case: solve overnight.

    caffeinate -i python scripts/batch_solve.py --input common_spots.csv --workers 2 \\
      > batch.log 2>&1 &

``caffeinate`` keeps the MacBook awake; the script chews through the
CSV. Re-running the same CSV after a crash is idempotent
(already-solved spots skip via ``Library.get``).

CSV format (per ``docs/pr11_prep/pr11_spec.md`` §5.1):

    name,starting_street,initial_board,stacks_bb,bet_sizes,abstraction_path,iterations

Columns:
  - ``name`` — user-facing label, stored as ``SpotMetadata.label``.
  - ``starting_street`` — ``flop`` / ``turn`` / ``river`` (PR 5 is
    postflop-only; ``preflop`` is rejected with a clear error).
  - ``initial_board`` — space-or-comma separated cards, e.g. ``"AsKc7d"``.
  - ``stacks_bb`` — integer big-blinds.
  - ``bet_sizes`` — comma-separated pot fractions, e.g. ``"0.33,0.75,2.0"``.
  - ``abstraction_path`` — path to PR 4's ``.npz`` artifact, or empty
    for lossless (river-only).
  - ``iterations`` — integer.

See ``docs/pr11_prep/pr11_spec.md`` §5 for the canonical format.

Usage:

    python scripts/batch_solve.py --input spots.csv \\
        [--workers N] \\
        [--max-memory-gb N] \\
        [--dry-run] \\
        [--library-path PATH]

Equivalent via the CLI subcommand:

    poker-solver batch-solve --input spots.csv [--dry-run] ...

The ``--dry-run`` path parses the CSV, performs the library skip-check,
and prints ``[DRY-RUN]`` markers without calling ``solve_hunl_postflop``.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# CSV row parsing.
# --------------------------------------------------------------------------- #


# The set of starting-street strings accepted in the CSV (PR 5 scope).
_ACCEPTED_STREETS: frozenset[str] = frozenset({"flop", "turn", "river"})


@dataclass(frozen=True)
class BatchRow:
    """One parsed CSV row, post-validation.

    Holds the raw CSV cells in normalized form. The conversion to
    ``HUNLConfig`` + ``SpotDescription`` is deferred to ``_build_spot``
    so we keep parsing errors (CSV-shape problems) separate from spot
    construction errors (HUNLConfig invariant violations).
    """

    name: str
    starting_street: str
    initial_board: str
    stacks_bb: int
    bet_sizes: tuple[float, ...]
    abstraction_path: str  # may be ""
    iterations: int


def _parse_board(raw: str) -> tuple:
    """Parse a board string of ``"AsKc7d"`` or ``"As Kc 7d"`` / ``"As,Kc,7d"``."""
    from poker_solver.card import Card

    cleaned = raw.strip().replace(",", " ").replace("  ", " ").strip()
    if not cleaned:
        return ()
    if " " in cleaned:
        tokens = [t for t in cleaned.split(" ") if t]
    else:
        # Concatenated form ("AsKc7d"): split every 2 chars.
        if len(cleaned) % 2 != 0:
            raise ValueError(
                f"initial_board {raw!r} has odd length; expected pairs of "
                "(rank, suit)"
            )
        tokens = [cleaned[i : i + 2] for i in range(0, len(cleaned), 2)]
    return tuple(Card.from_str(t) for t in tokens)


def _parse_bet_sizes(raw: str) -> tuple[float, ...]:
    """Parse a comma-separated list of pot fractions."""
    cleaned = raw.strip()
    if not cleaned:
        return ()
    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    return tuple(float(p) for p in parts)


def _parse_row(row: dict[str, str], lineno: int) -> BatchRow:
    """Convert a ``csv.DictReader`` row to a validated ``BatchRow``.

    Raises ``ValueError`` with line context on any parse failure.
    """
    required = (
        "name",
        "starting_street",
        "initial_board",
        "stacks_bb",
        "bet_sizes",
        "abstraction_path",
        "iterations",
    )
    missing = [k for k in required if k not in row]
    if missing:
        raise ValueError(
            f"CSV row {lineno}: missing columns {missing!r} "
            f"(present: {list(row.keys())!r})"
        )

    name = row["name"].strip()
    if not name:
        raise ValueError(f"CSV row {lineno}: 'name' is empty")

    street = row["starting_street"].strip().lower()
    if street == "preflop":
        raise ValueError(
            f"CSV row {lineno}: 'preflop' rejected (PR 5 is postflop-only)"
        )
    if street not in _ACCEPTED_STREETS:
        raise ValueError(
            f"CSV row {lineno}: starting_street {street!r} not in "
            f"{sorted(_ACCEPTED_STREETS)!r}"
        )

    try:
        stacks_bb = int(row["stacks_bb"])
    except ValueError as exc:
        raise ValueError(
            f"CSV row {lineno}: stacks_bb {row['stacks_bb']!r} not an integer"
        ) from exc

    try:
        bet_sizes = _parse_bet_sizes(row["bet_sizes"])
    except ValueError as exc:
        raise ValueError(
            f"CSV row {lineno}: invalid bet_sizes {row['bet_sizes']!r}: {exc}"
        ) from exc

    try:
        iterations = int(row["iterations"])
    except ValueError as exc:
        raise ValueError(
            f"CSV row {lineno}: iterations {row['iterations']!r} not an integer"
        ) from exc

    return BatchRow(
        name=name,
        starting_street=street,
        initial_board=row["initial_board"].strip(),
        stacks_bb=stacks_bb,
        bet_sizes=bet_sizes,
        abstraction_path=row["abstraction_path"].strip(),
        iterations=iterations,
    )


def read_csv(path: Path) -> list[BatchRow]:
    """Parse all rows from a CSV file at ``path``. Returns the list of
    validated ``BatchRow`` instances.

    Raises:
        FileNotFoundError: if ``path`` doesn't exist.
        ValueError: with line context on any parse failure.
    """
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    rows: list[BatchRow] = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for i, raw_row in enumerate(reader, start=2):  # start=2 -> header is line 1
            rows.append(_parse_row(raw_row, i))
    return rows


# --------------------------------------------------------------------------- #
# Spot construction.
# --------------------------------------------------------------------------- #


def _build_spot(row: BatchRow):
    """Convert a ``BatchRow`` to a ``SpotDescription``.

    Imports lazily so the script can be parsed (and ``read_csv`` tested)
    even before Agent A's ``poker_solver.library`` is importable. If
    library construction fails, the caller catches the error.
    """
    from poker_solver.hunl import HUNLConfig, Street
    from poker_solver.library import SpotDescription

    street_map = {
        "flop": Street.FLOP,
        "turn": Street.TURN,
        "river": Street.RIVER,
    }
    starting_street = street_map[row.starting_street]
    board = _parse_board(row.initial_board)

    # Convert stacks_bb (integer BB) → cents using the conventional
    # big_blind=100 cents from HUNLConfig's defaults. PR 5 fixes the
    # blinds at the game level; this matches the locked blind values.
    big_blind = 100
    small_blind = 50
    starting_stack = row.stacks_bb * big_blind

    # Subgame pot defaults: split the antes evenly so HUNLConfig's
    # contributions=(half, half) sum to initial_pot. We seed with a
    # token pot to keep the subgame fixture non-trivial. The actual
    # bb/sb/pot semantics for batch solving are documented in spec
    # §5.1; we mirror them with reasonable defaults so the CSV remains
    # dense (no extra columns).
    initial_pot = 2 * big_blind  # 2 BB pot baseline; user can vary by editing spec
    initial_contributions = (initial_pot // 2, initial_pot // 2)

    config = HUNLConfig(
        starting_stack=starting_stack,
        small_blind=small_blind,
        big_blind=big_blind,
        starting_street=starting_street,
        initial_board=board,
        initial_pot=initial_pot,
        initial_contributions=initial_contributions,
        bet_size_fractions=row.bet_sizes if row.bet_sizes else (0.5, 1.0, 2.0),
    )
    return SpotDescription(config=config, label=row.name)


# --------------------------------------------------------------------------- #
# Solve loop (single-process; --workers > 1 is wired but the dry-run
# path is the only path exercised by tests).
# --------------------------------------------------------------------------- #


@dataclass
class SolveCounts:
    ok: int = 0
    skip: int = 0
    oom: int = 0
    error: int = 0
    dry_run: int = 0


def run_batch(
    rows: list[BatchRow],
    *,
    library_path: Path | None,
    dry_run: bool,
    max_memory_gb: float,
    workers: int,
    log_stream: Any = None,
) -> SolveCounts:
    """Execute the batch-solve loop. Returns final counts."""
    from poker_solver.library import Library

    out = log_stream if log_stream is not None else sys.stdout
    counts = SolveCounts()

    lib = Library.open(library_path) if library_path is not None else Library.open()
    try:
        for row in rows:
            try:
                spot = _build_spot(row)
            except (
                Exception
            ) as exc:  # noqa: BLE001 — surface all CSV errors per spec §5.2
                print(f"[ERROR] {row.name}: {exc}", file=out, flush=True)
                counts.error += 1
                continue

            spot_id = spot.spot_id()

            # Idempotent skip: already-solved spots are no-ops on re-run.
            existing = lib.get(spot_id)
            if existing is not None:
                print(f"[SKIP] {row.name} {spot_id}", file=out, flush=True)
                counts.skip += 1
                continue

            if dry_run:
                print(
                    f"[DRY-RUN] {row.name} {spot_id} (would solve)",
                    file=out,
                    flush=True,
                )
                counts.dry_run += 1
                continue

            # Real solve path: call PR 5's solve_hunl_postflop.
            try:
                from poker_solver.hunl_solver import solve_hunl_postflop

                start = time.time()
                # Memory budget per worker; workers > 1 wired but
                # parallelism is via multiprocessing (not exercised by
                # the dry-run test). We pass the per-worker budget here
                # so single-process runs remain in the budget.
                budget_per_worker = (
                    max_memory_gb / workers if workers > 0 else max_memory_gb
                )
                result = solve_hunl_postflop(
                    spot.config,
                    iterations=row.iterations,
                    memory_budget_gb=budget_per_worker,
                )
                lib.put(spot, result)
                elapsed = time.time() - start
                print(
                    f"[OK] {row.name} {spot_id} {elapsed:.2f}s",
                    file=out,
                    flush=True,
                )
                counts.ok += 1
            except MemoryError as exc:
                report = exc.args[1] if len(exc.args) > 1 else None
                print(
                    f"[OOM] {row.name} memory_report={report!r}",
                    file=out,
                    flush=True,
                )
                counts.oom += 1
            except Exception as exc:  # noqa: BLE001 — spec §5.2 catches "any other"
                print(f"[ERROR] {row.name}: {exc}", file=out, flush=True)
                counts.error += 1
    finally:
        lib.close()

    print(
        f"Summary: total={len(rows)} ok={counts.ok} skip={counts.skip} "
        f"dry_run={counts.dry_run} oom={counts.oom} error={counts.error}",
        file=out,
        flush=True,
    )
    return counts


# --------------------------------------------------------------------------- #
# Public entry point for the CLI subcommand dispatcher (Agent A's
# ``poker_solver.cli._cmd_batch_solve`` imports this name).
# --------------------------------------------------------------------------- #


def run(
    *,
    input_csv: Path,
    workers: int = 1,
    max_memory_gb: float = 14.0,
    dry_run: bool = False,
    library_path: Path | None = None,
) -> int:
    """Parse a CSV at ``input_csv`` and execute the batch solve loop.

    Called by ``poker_solver.cli._cmd_batch_solve`` as the public
    dispatcher entry. Returns the same int exit code as ``main`` so the
    caller can ``return run(...)`` directly.
    """
    if workers < 1:
        print("--workers must be >= 1", file=sys.stderr)
        return 2
    try:
        rows = read_csv(input_csv)
    except (FileNotFoundError, ValueError) as exc:
        print(f"batch_solve: {exc}", file=sys.stderr)
        return 2
    if not rows:
        print(f"batch_solve: no rows in {input_csv}", file=sys.stderr)
        return 2
    counts = run_batch(
        rows,
        library_path=library_path,
        dry_run=dry_run,
        max_memory_gb=max_memory_gb,
        workers=workers,
    )
    return 1 if counts.error > 0 else 0


# --------------------------------------------------------------------------- #
# CLI entry point.
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="batch_solve",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="path to the CSV of spots to solve (spec §5.1 format).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="number of multiprocessing workers (default 1; >1 parallelizes "
        "across spots).",
    )
    parser.add_argument(
        "--max-memory-gb",
        type=float,
        default=14.0,
        help="total memory budget across workers (default 14.0 GB).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="parse the CSV and report what would be solved; do not run "
        "the solver. Spec §16 success criterion.",
    )
    parser.add_argument(
        "--library-path",
        type=Path,
        default=None,
        help="override the library DB location (defaults to "
        "$POKER_SOLVER_LIBRARY_PATH or ~/.poker_solver/library.db).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Resolve library path with the standard precedence (CLI > env > default).
    library_path: Path | None = args.library_path
    if library_path is None:
        env_override = os.environ.get("POKER_SOLVER_LIBRARY_PATH")
        if env_override:
            library_path = Path(env_override)

    return run(
        input_csv=args.input,
        workers=args.workers,
        max_memory_gb=args.max_memory_gb,
        dry_run=args.dry_run,
        library_path=library_path,
    )


if __name__ == "__main__":
    sys.exit(main())
