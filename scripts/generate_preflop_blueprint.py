#!/usr/bin/env python3
"""Generate preflop 169-class blueprint shards (Premium-A Phase 1, #68).

Reads a (stack_depth, ante_config) cell — or the full 27-cell grid via
``--all-depths --all-antes`` — and produces one gzipped JSON shard per
cell plus a manifest. Idempotent: skips cells whose output already
exists unless ``--force`` is set.

Usage:

    python scripts/generate_preflop_blueprint.py \
        --depth 40 --ante none --iterations 25000 \
        --output assets/blueprints/

    python scripts/generate_preflop_blueprint.py \
        --all-depths --all-antes --iterations 25000 \
        --output assets/blueprints/

    # Smoke test — single small cell:
    python scripts/generate_preflop_blueprint.py \
        --depth 40 --ante none --iterations 100 \
        --output /tmp/blueprint_smoke/

Phase 1.5 (the full overnight compute) is OUT of scope for this script's
agent dispatch — the user runs it on their terminal. The script is
designed for that interactive use: progress logging + ETA + idempotent
resume.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import logging
import sys
import time
from pathlib import Path

# When invoked as ``python scripts/generate_preflop_blueprint.py`` we need
# the repo root on sys.path so ``poker_solver`` resolves without prior
# ``pip install -e .``. Mirrors ``scripts/generate_pushfold_charts.py``.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from poker_solver.blueprint import (  # noqa: E402
    SCHEMA_VERSION,
    BatchSpec,
    Blueprint,
    BlueprintConfig,
    Manifest,
    blueprint_shard_filename,
    file_sha256,
    generate_blueprint,
    load_blueprint,
    load_manifest,
    manifest_entry_for_blueprint,
    save_blueprint,
    save_manifest,
    validate_blueprint,
)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

# Locked Phase 1 grid (per task brief).
SUPPORTED_DEPTHS = (20, 30, 40, 60, 80, 100, 150, 175, 200)
SUPPORTED_ANTE_TOKENS = {"none": 0.0, "half": 0.5, "full": 1.0}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate 169-class preflop blueprint shards (Premium-A Phase 1).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--depth",
        type=int,
        default=None,
        help=(
            f"Stack depth in BB. One of {SUPPORTED_DEPTHS}. "
            "Mutually exclusive with --all-depths."
        ),
    )
    p.add_argument(
        "--ante",
        type=str,
        default=None,
        choices=sorted(SUPPORTED_ANTE_TOKENS.keys()),
        help=(
            "Ante config: none (0 BB), half (0.5 BB), or full (1.0 BB). "
            "Mutually exclusive with --all-antes."
        ),
    )
    p.add_argument(
        "--all-depths",
        action="store_true",
        help=f"Generate all supported depths: {SUPPORTED_DEPTHS}",
    )
    p.add_argument(
        "--all-antes",
        action="store_true",
        help="Generate all supported ante configs: none, half, full.",
    )
    p.add_argument(
        "--iterations",
        type=int,
        required=True,
        help="DCFR iterations per cell. Production: 25000. Smoke: 100.",
    )
    p.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output directory for shards + manifest.",
    )
    p.add_argument(
        "--alpha", type=float, default=1.5, help="DCFR positive-regret exponent."
    )
    p.add_argument(
        "--beta", type=float, default=0.0, help="DCFR negative-regret exponent."
    )
    p.add_argument(
        "--gamma", type=float, default=2.0, help="DCFR strategy-sum decay exponent."
    )
    p.add_argument(
        "--preflop-open-sizes-bb",
        type=str,
        default="2.0,3.0,4.0,5.0",
        help="Comma-separated absolute-BB open sizes.",
    )
    p.add_argument(
        "--preflop-reraise-multipliers",
        type=str,
        default="2.0,3.0,4.0,5.0",
        help="Comma-separated reraise multipliers of previous bet.",
    )
    p.add_argument(
        "--preflop-raise-cap",
        type=int,
        default=4,
        help="Maximum number of preflop raises per street.",
    )
    p.add_argument(
        "--small-blind-bb",
        type=float,
        default=0.5,
        help="Small blind in BB (0.5 = chip-per-bb HU).",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Re-generate cells whose output already exists.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate the pipeline without running the engine. "
            "Produces empty shards + manifest so the format is exercised end-to-end."
        ),
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose logging.",
    )
    return p.parse_args(argv)


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="[%(asctime)s] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        level=level,
        force=True,
    )


def _resolve_batch_specs(args: argparse.Namespace) -> list[BatchSpec]:
    """Resolve the CLI args into the list of (depth, ante) cells to generate."""
    if args.all_depths and args.depth is not None:
        raise SystemExit("--depth and --all-depths are mutually exclusive")
    if args.all_antes and args.ante is not None:
        raise SystemExit("--ante and --all-antes are mutually exclusive")
    if not args.all_depths and args.depth is None:
        raise SystemExit("must specify --depth or --all-depths")
    if not args.all_antes and args.ante is None:
        raise SystemExit("must specify --ante or --all-antes")

    if args.all_depths:
        depths = list(SUPPORTED_DEPTHS)
    else:
        if args.depth not in SUPPORTED_DEPTHS:
            raise SystemExit(
                f"--depth {args.depth} not in supported set {SUPPORTED_DEPTHS}"
            )
        depths = [args.depth]

    if args.all_antes:
        antes = [(k, v) for k, v in SUPPORTED_ANTE_TOKENS.items()]
    else:
        antes = [(args.ante, SUPPORTED_ANTE_TOKENS[args.ante])]

    specs: list[BatchSpec] = []
    for d in depths:
        for _, ante_bb in antes:
            specs.append(BatchSpec(stack_bb=d, ante_bb=ante_bb))
    return specs


def _parse_csv_floats(s: str) -> tuple[float, ...]:
    return tuple(float(x.strip()) for x in s.split(",") if x.strip())


def _eta(elapsed_s: float, done: int, total: int) -> str:
    if done == 0:
        return "?"
    remaining = (total - done) * (elapsed_s / done)
    return f"{remaining / 60:.1f} min"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _generate_for_spec(
    spec: BatchSpec,
    *,
    args: argparse.Namespace,
    output_dir: Path,
    skip_actual_solve: bool,
) -> tuple[Path, Blueprint, str] | None:
    """Generate one cell. Returns (path, blueprint, sha256) or None if skipped."""
    config = BlueprintConfig(
        stack_bb=spec.stack_bb,
        ante_bb=spec.ante_bb,
        iterations=args.iterations,
        alpha=args.alpha,
        beta=args.beta,
        gamma=args.gamma,
        preflop_open_sizes_bb=_parse_csv_floats(args.preflop_open_sizes_bb),
        preflop_reraise_multipliers=_parse_csv_floats(args.preflop_reraise_multipliers),
        preflop_raise_cap=args.preflop_raise_cap,
        small_blind_bb=args.small_blind_bb,
    )
    out_path = output_dir / blueprint_shard_filename(config)

    if out_path.exists() and not args.force:
        # Idempotent — try to load existing to verify integrity, then skip solve.
        try:
            existing = load_blueprint(out_path)
            sha = file_sha256(out_path)
            warnings = validate_blueprint(existing)
            if warnings:
                logging.warning(
                    "existing shard %s has %d validation warnings; consider --force",
                    out_path.name,
                    len(warnings),
                )
            logging.info(
                "SKIP %s (existing; %d infosets, %d strategy rows)",
                out_path.name,
                existing.n_infosets,
                existing.n_strategy_rows,
            )
            return out_path, existing, sha
        except Exception as e:  # noqa: BLE001 - resume must be robust
            logging.warning(
                "existing shard %s unreadable (%s); regenerating",
                out_path.name,
                e,
            )

    started = time.time()
    bp = generate_blueprint(
        config,
        skip_actual_solve=skip_actual_solve,
    )
    elapsed = time.time() - started

    warnings = validate_blueprint(bp)
    if warnings:
        for w in warnings[:5]:
            logging.warning("validation: %s", w)
        if len(warnings) > 5:
            logging.warning("... and %d more", len(warnings) - 5)

    sha = save_blueprint(bp, out_path)
    logging.info(
        "WROTE %s (%d infosets, %d strategy rows, %.1f s wall)",
        out_path.name,
        bp.n_infosets,
        bp.n_strategy_rows,
        elapsed,
    )
    return out_path, bp, sha


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _setup_logging(args.verbose)

    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    specs = _resolve_batch_specs(args)

    logging.info(
        "Generating %d blueprint cell(s); iterations=%d; output=%s%s",
        len(specs),
        args.iterations,
        output_dir,
        " (DRY RUN)" if args.dry_run else "",
    )

    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists() and not args.force:
        manifest = load_manifest(manifest_path)
        # Drop any entries that we're about to regenerate (preserves entries
        # for cells outside this run's spec set).
        regen_filenames = {
            blueprint_shard_filename(
                BlueprintConfig(
                    stack_bb=s.stack_bb,
                    ante_bb=s.ante_bb,
                    iterations=args.iterations,
                )
            )
            for s in specs
        }
        manifest.entries = [
            e for e in manifest.entries if e.filename not in regen_filenames
        ]
    else:
        manifest = Manifest(
            schema_version=SCHEMA_VERSION,
            premium_a_version="v1",
            generated_date_utc=_datetime.datetime.now(
                _datetime.timezone.utc
            ).isoformat(),
            entries=[],
        )

    overall_started = time.time()
    for i, spec in enumerate(specs, 1):
        cell_started = time.time()
        result = _generate_for_spec(
            spec,
            args=args,
            output_dir=output_dir,
            skip_actual_solve=args.dry_run,
        )
        if result is None:
            continue
        out_path, bp, sha = result
        entry = manifest_entry_for_blueprint(bp, path=out_path, sha=sha)
        manifest.entries.append(entry)
        # Re-save manifest after every cell — partial progress survives crashes.
        save_manifest(manifest, manifest_path)
        elapsed = time.time() - overall_started
        eta = _eta(elapsed, i, len(specs))
        logging.info(
            "[%d/%d] done (cell %.1fs, total %.1f min, ETA %s)",
            i,
            len(specs),
            time.time() - cell_started,
            elapsed / 60,
            eta,
        )

    logging.info(
        "Done. %d cells in %.1f min. Manifest at %s",
        len(specs),
        (time.time() - overall_started) / 60,
        manifest_path,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
