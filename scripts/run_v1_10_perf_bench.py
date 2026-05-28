"""v1.10 perf benchmark harness — speed-vs-quality Pareto curve.

This harness drives the canonical perf table that the v1.10 final
benchmark agent will run at release close-out. Today (2026-05-28) the
harness *builds* but the headline numbers are stubs until the v1.10
optimizations land (arena, vector turn, vector flop, rayon).

Fixture
-------
J7o A♦8♥9♦, 40 BB, SB opens 3bb / BB calls. Mirrors
``docs/v1_10_postflop_optimization_plan.md`` Section 5.1. Single shared
preflop blueprint feeds every cell so the postflop solve cost
dominates the wall-clock measurement.

Matrix
------
- ``top_k`` ∈ {4, 15, 50, 169} (filter passed via ``hero_classes`` /
  ``villain_classes`` to ``solve_postflop_from_blueprint`` — NOT a
  misnamed flag, that's the real API per
  ``poker_solver/blueprint_subgame.py:585-586``).
- ``street`` ∈ {flop, turn, river} (selected by board length: 3, 4, 5).
- ``iterations`` ∈ {200, 1000}. 200 is canonical perf reporting; 1000
  is the convergence-stress run.

Quality metrics (per cell)
--------------------------
1. **Exploitability** (bb/100) — from
   ``_rust.compute_exploitability`` of the comparison solve.
2. **L1 vs top_k=169** — sum of ``|p_ref - p_cmp|`` over the 169-class
   first-decision projection.
3. **EV-of-action loss vs top_k=169** (bb/100) — Nash-invariance proxy
   per "Brown convention adopt" memory.

Speed metrics (per cell)
------------------------
1. **Wall time** (sec) — ``time.perf_counter()`` around the
   postflop-solve call only (excludes blueprint + continuation derive,
   which are amortized).
2. **Peak RSS** (MB) — ``psutil.Process().memory_info().rss`` sampled
   immediately after the solve. For tighter peak tracking we could
   spawn a watcher process; for the harness build we use a single
   post-solve sample which captures the high-water mark for the
   monotonically growing solver allocations.

Outputs
-------
- ``docs/v1_10_perf_bench_results.jsonl`` — one JSON line per cell,
  machine-readable for downstream analysis.
- ``docs/v1_10_perf_bench_{street}.md`` — one markdown table per
  street, human-readable.

Usage
-----
Smoke test (~30 sec, river only, top_k=4, 5 iters)::

    python scripts/run_v1_10_perf_bench.py --smoke

Full canonical run (~hours at full top_k=169, depends on v1.10 perf)::

    python scripts/run_v1_10_perf_bench.py --canonical

Custom subset::

    python scripts/run_v1_10_perf_bench.py \\
        --top-k 4,15 --streets flop,turn --iters 200

Convergence-stress (200 + 1000 iters at every cell)::

    python scripts/run_v1_10_perf_bench.py --canonical --stress
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psutil  # type: ignore[import-not-found]

# Ensure ``scripts/`` is importable as a sibling module so we can pull
# in ``measure_quality_metrics`` regardless of how this script is invoked.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from measure_quality_metrics import (  # noqa: E402
    chips_to_bb100,
    compute_all_quality_metrics,
)

from poker_solver.blueprint import (  # noqa: E402
    BlueprintConfig,
    HandResolution,
    generate_blueprint,
)
from poker_solver.card import Card  # noqa: E402

# Lazy imports for the postflop subgame helpers (avoid Rust extension
# load on `--help`).


# ---------------------------------------------------------------------------
# Fixture constants — locked to ``docs/v1_10_postflop_optimization_plan.md``.
# ---------------------------------------------------------------------------

PREFLOP_SEQ = ("b300", "c")  # SB opens 3bb, BB calls
FLOP_CARDS = [Card.from_str("Ad"), Card.from_str("8h"), Card.from_str("9d")]
TURN_CARD = Card.from_str("2c")  # brick turn — matches j7o walkthrough.
RIVER_CARD = Card.from_str("3s")  # brick river — matches j7o walkthrough.
HERO_PIN = ["J7o"]

CANONICAL_TOP_K = (4, 15, 50, 169)
CANONICAL_STREETS = ("flop", "turn", "river")
CANONICAL_ITERS = 200
STRESS_ITERS = 1000
BLUEPRINT_ITERS = 1500  # cheap (~few sec); shared across all cells.
BIG_BLIND_CHIPS = 100  # from BlueprintConfig defaults (stack_bb=40 → 100 chips/BB)

OUT_JSONL_PATH = (
    Path(__file__).resolve().parent.parent
    / "docs"
    / "v1_10_perf_bench_results.jsonl"
)


# ---------------------------------------------------------------------------
# Data classes for results bookkeeping.
# ---------------------------------------------------------------------------


@dataclass
class CellResult:
    """One cell of the perf table."""

    top_k: int
    street: str
    iterations: int
    wall_s: float
    peak_rss_mb: float
    exploit_bb100: float
    l1_vs_ref: float
    ev_loss_bb100: float
    n_hero_combos: int
    n_villain_combos: int
    decision_node_count: int
    status: str = "complete"
    error: str | None = None
    raw_per_class: dict[str, Any] = field(default_factory=dict)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "top_k": self.top_k,
            "street": self.street,
            "iterations": self.iterations,
            "wall_s": self.wall_s,
            "peak_rss_mb": self.peak_rss_mb,
            "exploit_bb100": self.exploit_bb100,
            "l1_vs_ref": self.l1_vs_ref,
            "ev_loss_bb100": self.ev_loss_bb100,
            "n_hero_combos": self.n_hero_combos,
            "n_villain_combos": self.n_villain_combos,
            "decision_node_count": self.decision_node_count,
            "status": self.status,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Top-K class selection — pin J7o so hero range always contains the
# fixture's signature hand.
# ---------------------------------------------------------------------------


def topk_classes(reach: dict[str, float], k: int, pin: list[str]) -> list[str]:
    """Top-K hand classes by reach, with pinned labels guaranteed present.

    Args:
        reach: ``{class_label: reach_probability}`` from
            ``derive_continuation_ranges_from_blueprint`` output.
        k: Truncation cap. If ``k == 169``, every present class is
            returned (the full range).
        pin: Class labels to force-include even if they fall outside
            top-K (e.g. ``["J7o"]`` so the fixture's hero hand is
            never dropped).

    Returns:
        Ordered list of class labels. If pin labels were already in
        top-K, the list size is K. Otherwise pinned labels are
        appended (so the list is ``len(set(top_k_classes) | set(pin))``).
    """
    sorted_classes = sorted(reach.items(), key=lambda kv: -kv[1])
    top = [c for c, _ in sorted_classes[:k]]
    seen = set(top)
    for p in pin:
        if p not in seen:
            top.append(p)
            seen.add(p)
    return top


def board_for_street(street: str) -> list[Card]:
    """Return the canonical board for a given street."""
    if street == "flop":
        return list(FLOP_CARDS)
    if street == "turn":
        return list(FLOP_CARDS) + [TURN_CARD]
    if street == "river":
        return list(FLOP_CARDS) + [TURN_CARD, RIVER_CARD]
    raise ValueError(
        f"street must be one of 'flop' / 'turn' / 'river'; got {street!r}"
    )


# ---------------------------------------------------------------------------
# Speed measurement helpers.
# ---------------------------------------------------------------------------


def current_rss_mb() -> float:
    """Current process RSS in MiB via ``psutil.Process().memory_info().rss``.

    Per the harness constraint, RSS is measured with ``psutil`` rather
    than ``resource.getrusage`` to keep the interface portable across
    macOS / Linux (``ru_maxrss`` units differ).
    """
    return psutil.Process().memory_info().rss / (1024.0 * 1024.0)


# ---------------------------------------------------------------------------
# Per-cell solve.
# ---------------------------------------------------------------------------


def run_cell(
    blueprint: Any,
    hunl_template: Any,
    continuation: Any,
    *,
    top_k: int,
    street: str,
    iterations: int,
    reference_per_class: dict | None = None,
) -> CellResult:
    """Run one (top_k, street, iterations) cell of the perf table.

    The reference at top_k=169 is computed FIRST so the truncated cells
    can be diffed against it for L1 / EV-loss. ``reference_per_class``
    is supplied as None when computing the reference cell itself (the
    L1 / EV-loss values are then trivially 0 — "baseline").
    """
    from poker_solver.blueprint_subgame import solve_postflop_from_blueprint

    board = board_for_street(street)
    hero_top = topk_classes(continuation.hero, top_k, HERO_PIN)
    villain_top = topk_classes(continuation.villain, top_k, [])

    rss_pre = current_rss_mb()
    t0 = time.perf_counter()
    try:
        res = solve_postflop_from_blueprint(
            blueprint,
            config_template=hunl_template,
            action_sequence=PREFLOP_SEQ,
            board=tuple(board),
            hero_player=0,
            iterations=iterations,
            hero_classes=hero_top,
            villain_classes=villain_top,
            # Need exploitability for the quality metric.
            compute_exploitability_at_end=True,
        )
    except Exception as exc:  # noqa: BLE001
        wall = time.perf_counter() - t0
        rss_post = current_rss_mb()
        return CellResult(
            top_k=top_k,
            street=street,
            iterations=iterations,
            wall_s=wall,
            peak_rss_mb=max(rss_pre, rss_post),
            exploit_bb100=float("nan"),
            l1_vs_ref=float("nan"),
            ev_loss_bb100=float("nan"),
            n_hero_combos=0,
            n_villain_combos=0,
            decision_node_count=0,
            status="error",
            error=repr(exc),
        )

    wall = time.perf_counter() - t0
    rss_post = current_rss_mb()
    peak_rss = max(rss_pre, rss_post)

    per_class = dict(res.postflop.per_class_strategy)
    expl_bb100 = chips_to_bb100(
        float(res.postflop.exploitability),
        big_blind_chips=BIG_BLIND_CHIPS,
    )

    if reference_per_class is None:
        # This IS the reference cell.
        l1 = 0.0
        ev_loss = 0.0
    else:
        # Build a stub object exposing per_class_strategy +
        # exploitability so the helper can introspect both sides.
        class _RefStub:
            per_class_strategy = reference_per_class
            exploitability = 0.0

        class _CmpStub:
            per_class_strategy = per_class
            exploitability = float(res.postflop.exploitability)

        metrics = compute_all_quality_metrics(
            _RefStub(),
            _CmpStub(),
            big_blind_chips=BIG_BLIND_CHIPS,
        )
        l1 = metrics["l1_vs_ref"]
        ev_loss = metrics["ev_loss_bb100"]

    return CellResult(
        top_k=top_k,
        street=street,
        iterations=iterations,
        wall_s=wall,
        peak_rss_mb=peak_rss,
        exploit_bb100=expl_bb100,
        l1_vs_ref=l1,
        ev_loss_bb100=ev_loss,
        n_hero_combos=len(res.hero_range),
        n_villain_combos=len(res.villain_range),
        decision_node_count=int(res.postflop.decision_node_count),
        status="complete",
        raw_per_class=per_class,
    )


# ---------------------------------------------------------------------------
# Markdown rendering — one table per (street, iteration count).
# ---------------------------------------------------------------------------


def render_street_table(
    cells: list[CellResult], street: str, iterations: int
) -> str:
    """Render the markdown table for a single (street, iters) combination."""
    relevant = [c for c in cells if c.street == street and c.iterations == iterations]
    if not relevant:
        return f"(no cells for street={street} iterations={iterations})\n"

    lines = [
        f"J7o A♦8♥9♦, 40 BB, post-v1.10, {iterations} iters, {street.upper()} solve",
        "",
        "| top_k | Wall (s) | RSS (MB) | Exploit (bb/100) | L1 vs top_k=169 | EV loss vs top_k=169 (bb/100) | Status |",
        "|-------|----------|----------|------------------|-----------------|------------------------------|--------|",
    ]
    for cell in sorted(relevant, key=lambda c: c.top_k):
        if cell.status == "error":
            lines.append(
                f"| {cell.top_k} | {cell.wall_s:.2f} | {cell.peak_rss_mb:.0f} "
                f"| ERROR | ERROR | ERROR | {cell.error} |"
            )
            continue
        l1_str = "0.00 (ref)" if cell.top_k == 169 else f"{cell.l1_vs_ref:.4f}"
        ev_str = "0.00 (ref)" if cell.top_k == 169 else f"{cell.ev_loss_bb100:.3f}"
        expl_str = (
            f"{cell.exploit_bb100:.3f}"
            if cell.top_k != 169
            else f"{cell.exploit_bb100:.3f} (baseline)"
        )
        lines.append(
            f"| {cell.top_k} | {cell.wall_s:.2f} | {cell.peak_rss_mb:.0f} "
            f"| {expl_str} | {l1_str} | {ev_str} | ok |"
        )
    lines.append("")
    lines.append(
        "*Note: top_k=169 row is the full-range reference — L1 / EV-loss are 0 by definition. "
        "Full range = all 169 hand classes; the solver enumerates 1326 combos minus board-blockers.*"
    )
    lines.append("")
    return "\n".join(lines)


def render_all_tables(cells: list[CellResult]) -> dict[str, str]:
    """Render one markdown table per (street, iterations) combination.

    Returns:
        ``{filename: content}``. The harness writes each entry to disk.
    """
    out: dict[str, str] = {}
    streets = sorted({c.street for c in cells})
    iters_set = sorted({c.iterations for c in cells})
    for street in streets:
        sections = []
        for iters in iters_set:
            sections.append(render_street_table(cells, street, iters))
        filename = f"v1_10_perf_bench_{street}.md"
        out[filename] = (
            f"# v1.10 perf benchmark — {street} solve\n\n"
            f"Fixture: J7o A♦8♥9♦, 40 BB, SB-opens-3bb / BB-calls. "
            f"Top-K via ``hero_classes`` / ``villain_classes``. "
            f"Generated by ``scripts/run_v1_10_perf_bench.py``.\n\n"
            + "\n\n".join(sections)
        )
    return out


# ---------------------------------------------------------------------------
# CLI argument parsing.
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--smoke",
        action="store_true",
        help="Run the smoke test (river only, top_k=4, 5 iters). Use to "
        "verify the harness builds without running a full bench.",
    )
    ap.add_argument(
        "--canonical",
        action="store_true",
        help="Run the canonical perf table (all 4 top_k × 3 streets, 200 iters).",
    )
    ap.add_argument(
        "--stress",
        action="store_true",
        help="Add a 1000-iter convergence-stress pass at every cell.",
    )
    ap.add_argument(
        "--top-k",
        type=str,
        default="",
        help="Comma-separated top_k values (e.g. '4,15'). Defaults to "
        "canonical {4,15,50,169} when --canonical, else {169}.",
    )
    ap.add_argument(
        "--streets",
        type=str,
        default="",
        help="Comma-separated streets {flop,turn,river}. Defaults to canonical.",
    )
    ap.add_argument(
        "--iters",
        type=int,
        default=0,
        help="Iteration count for non-canonical runs. Defaults to 200.",
    )
    ap.add_argument(
        "--out-dir",
        type=str,
        default=str(OUT_JSONL_PATH.parent),
        help="Output directory for jsonl + md.",
    )
    return ap.parse_args()


def resolve_matrix(args: argparse.Namespace) -> tuple[list[int], list[str], list[int]]:
    """Pick (top_k_values, streets, iterations) from CLI flags."""
    if args.smoke:
        return ([4], ["river"], [5])
    if args.canonical:
        top_k_vals = list(CANONICAL_TOP_K)
        streets = list(CANONICAL_STREETS)
        iters_list = [CANONICAL_ITERS]
        if args.stress:
            iters_list.append(STRESS_ITERS)
        return (top_k_vals, streets, iters_list)
    # Manual overrides.
    top_k_vals = (
        [int(x) for x in args.top_k.split(",")] if args.top_k else [169]
    )
    streets = args.streets.split(",") if args.streets else list(CANONICAL_STREETS)
    iters_list = [args.iters or CANONICAL_ITERS]
    if args.stress:
        iters_list.append(STRESS_ITERS)
    return (top_k_vals, streets, iters_list)


# ---------------------------------------------------------------------------
# Main entry.
# ---------------------------------------------------------------------------


def main() -> int:
    args = parse_args()
    top_k_vals, streets, iters_list = resolve_matrix(args)

    print(f"[v1_10_perf_bench] pid={os.getpid()}", flush=True)
    print(
        f"[v1_10_perf_bench] matrix: top_k={top_k_vals} streets={streets} "
        f"iters={iters_list}",
        flush=True,
    )

    # Step 1: shared preflop blueprint (cheap; reused across all cells).
    print(
        f"[v1_10_perf_bench] generating 40 BB blueprint ({BLUEPRINT_ITERS} iters)...",
        flush=True,
    )
    bp_cfg = BlueprintConfig(
        stack_bb=40,
        ante_bb=0.0,
        iterations=BLUEPRINT_ITERS,
        preflop_open_sizes_bb=(2.0, 3.0, 4.0, 5.0),
        preflop_reraise_multipliers=(2.0, 3.0, 4.0, 5.0),
        preflop_raise_cap=4,
        small_blind_bb=0.5,
        alpha=1.5,
        beta=0.0,
        gamma=2.0,
    )
    from poker_solver.blueprint import hunl_config_from_blueprint_config
    from poker_solver.blueprint_subgame import (
        derive_continuation_ranges_from_blueprint,
    )

    t_bp = time.perf_counter()
    blueprint = generate_blueprint(bp_cfg, hand_resolution=HandResolution.CLASS_169)
    bp_wall = time.perf_counter() - t_bp
    print(
        f"[v1_10_perf_bench] blueprint generated in {bp_wall:.2f}s; "
        f"n_infosets={blueprint.n_infosets}",
        flush=True,
    )

    hunl_template = hunl_config_from_blueprint_config(bp_cfg)

    # Step 2: continuation ranges (shared across all streets).
    cont = derive_continuation_ranges_from_blueprint(
        blueprint,
        config_template=hunl_template,
        action_sequence=PREFLOP_SEQ,
        hero_player=0,
    )
    print(
        f"[v1_10_perf_bench] continuation ranges: hero={len(cont.hero)} classes, "
        f"villain={len(cont.villain)} classes, pot={cont.pot_chips}",
        flush=True,
    )

    # Step 3: per-cell runs. Reference at top_k=169 is computed FIRST per
    # street so the truncated cells can diff against it.
    all_cells: list[CellResult] = []
    for street in streets:
        for iters in iters_list:
            # Reference cell — top_k=169 — only if 169 is in the matrix
            # for this street/iters; otherwise skip the L1/EV-loss
            # comparison and leave the reference as None.
            reference_per_class: dict | None = None
            if 169 in top_k_vals:
                print(
                    f"[v1_10_perf_bench] [REF] street={street} iters={iters} "
                    f"top_k=169 starting...",
                    flush=True,
                )
                ref_cell = run_cell(
                    blueprint,
                    hunl_template,
                    cont,
                    top_k=169,
                    street=street,
                    iterations=iters,
                    reference_per_class=None,
                )
                all_cells.append(ref_cell)
                print(
                    f"[v1_10_perf_bench] [REF] street={street} iters={iters} "
                    f"top_k=169 done: wall={ref_cell.wall_s:.2f}s "
                    f"rss={ref_cell.peak_rss_mb:.0f}MB status={ref_cell.status}",
                    flush=True,
                )
                if ref_cell.status == "complete":
                    reference_per_class = ref_cell.raw_per_class
            for k in top_k_vals:
                if k == 169:
                    continue  # already done above
                print(
                    f"[v1_10_perf_bench] [CMP] street={street} iters={iters} "
                    f"top_k={k} starting...",
                    flush=True,
                )
                cell = run_cell(
                    blueprint,
                    hunl_template,
                    cont,
                    top_k=k,
                    street=street,
                    iterations=iters,
                    reference_per_class=reference_per_class,
                )
                all_cells.append(cell)
                print(
                    f"[v1_10_perf_bench] [CMP] street={street} iters={iters} "
                    f"top_k={k} done: wall={cell.wall_s:.2f}s "
                    f"rss={cell.peak_rss_mb:.0f}MB "
                    f"expl={cell.exploit_bb100:.3f}bb/100 "
                    f"l1={cell.l1_vs_ref:.4f} ev_loss={cell.ev_loss_bb100:.3f}bb/100 "
                    f"status={cell.status}",
                    flush=True,
                )

    # Step 4: write outputs.
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = out_dir / OUT_JSONL_PATH.name
    with jsonl_path.open("w", encoding="utf-8") as fp:
        for cell in all_cells:
            fp.write(json.dumps(cell.to_jsonable(), default=str))
            fp.write("\n")
    print(f"[v1_10_perf_bench] wrote {jsonl_path}", flush=True)

    md_tables = render_all_tables(all_cells)
    for filename, content in md_tables.items():
        md_path = out_dir / filename
        md_path.write_text(content, encoding="utf-8")
        print(f"[v1_10_perf_bench] wrote {md_path}", flush=True)

    # Smoke success: at least one non-error cell.
    success = any(c.status == "complete" for c in all_cells)
    if not success:
        print("[v1_10_perf_bench] all cells errored — FAIL", flush=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
