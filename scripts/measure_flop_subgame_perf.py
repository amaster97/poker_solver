"""Minimal flop-subgame perf measurement (single solve per invocation).

Strips run_j7o_walkthrough_full_pov.py down to a single flop solve for
Test 1 (J7o, 40 BB, A♦8♥9♦ flop after SB-opens-3bb → BB-calls).

Usage:
    python scripts/measure_flop_subgame_perf.py --top-k 4 --iters 5

Wall time measured with time.perf_counter(). Peak RSS sampled by an
external watcher process — see run_flop_perf_measurements.sh.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import replace as dc_replace
from pathlib import Path

from poker_solver.blueprint import (
    BlueprintConfig,
    HandResolution,
    generate_blueprint,
    hunl_config_from_blueprint_config,
)
from poker_solver.blueprint_subgame import (
    derive_continuation_ranges_from_blueprint,
    solve_postflop_from_blueprint,
)
from poker_solver.card import Card

# Test 1 configuration (matches the full-POV walkthrough)
FLOP_CARDS = [Card.from_str("Ad"), Card.from_str("8h"), Card.from_str("9d")]
PF_SEQ = ("b300", "c")  # SB opens 3bb, BB calls
HERO_PIN = ["J7o"]

PREFLOP_ITERS = 1500


def _topk_classes(reach: dict, k: int, pin: list[str]) -> list[str]:
    """Top-K hand classes by reach, with pinned labels guaranteed present."""
    sorted_classes = sorted(reach.items(), key=lambda kv: -kv[1])
    top = [c for c, _ in sorted_classes[:k]]
    for p in pin:
        if p not in top:
            top.append(p)
    return top


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-k", type=int, required=True)
    ap.add_argument("--iters", type=int, required=True)
    ap.add_argument("--label", type=str, default="flop_perf")
    ap.add_argument("--json-out", type=str, default="")
    args = ap.parse_args()

    overall_t0 = time.perf_counter()
    print(f"[{args.label}] pid={os.getpid()}", flush=True)
    print(f"[{args.label}] Generating 40 BB preflop blueprint ({PREFLOP_ITERS} iters)...", flush=True)
    cfg = BlueprintConfig(
        stack_bb=40,
        ante_bb=0.0,
        iterations=PREFLOP_ITERS,
        preflop_open_sizes_bb=(2.0, 3.0, 4.0, 5.0),
        preflop_reraise_multipliers=(2.0, 3.0, 4.0, 5.0),
        preflop_raise_cap=4,
        small_blind_bb=0.5,
        alpha=1.5,
        beta=0.0,
        gamma=2.0,
    )
    t_bp = time.perf_counter()
    bp = generate_blueprint(cfg, hand_resolution=HandResolution.CLASS_169)
    bp_wall = time.perf_counter() - t_bp
    print(f"[{args.label}] blueprint generated in {bp_wall:.2f}s; n_infosets={bp.n_infosets}", flush=True)

    hunl_template = hunl_config_from_blueprint_config(cfg)

    # Derive continuation ranges (fast — no Rust call).
    t_cont = time.perf_counter()
    cont = derive_continuation_ranges_from_blueprint(
        bp, config_template=hunl_template,
        action_sequence=PF_SEQ, hero_player=0,
    )
    cont_wall = time.perf_counter() - t_cont
    print(f"[{args.label}] continuation ranges in {cont_wall:.2f}s; pot={cont.pot_chips}", flush=True)

    hero_top = _topk_classes(cont.hero, args.top_k, HERO_PIN)
    villain_top = _topk_classes(cont.villain, args.top_k, [])
    print(
        f"[{args.label}] hero_classes={len(hero_top)} {hero_top}, "
        f"villain_classes={len(villain_top)} {villain_top}",
        flush=True,
    )

    # THE FLOP SOLVE
    print(f"[{args.label}] STARTING flop solve: top_k={args.top_k}, iters={args.iters}, board={FLOP_CARDS}", flush=True)
    t_solve = time.perf_counter()
    try:
        res = solve_postflop_from_blueprint(
            bp,
            config_template=hunl_template,
            action_sequence=PF_SEQ,
            board=tuple(FLOP_CARDS),
            hero_player=0,
            iterations=args.iters,
            hero_classes=hero_top,
            villain_classes=villain_top,
            compute_exploitability_at_end=False,
        )
        solve_wall = time.perf_counter() - t_solve
        print(f"[{args.label}] SOLVE COMPLETE in {solve_wall:.2f}s", flush=True)
        per_class = dict(res.postflop.per_class_strategy)
        n_per_class = len(per_class)
        j7o_strategy = per_class.get("J7o", {})
        n_hero_combos = len(res.hero_range)
        n_villain_combos = len(res.villain_range)
        sample_per_class = {k: dict(v) for k, v in list(per_class.items())[:3]}
        out = {
            "label": args.label,
            "top_k": args.top_k,
            "iters": args.iters,
            "bp_wall_s": bp_wall,
            "cont_wall_s": cont_wall,
            "solve_wall_s": solve_wall,
            "total_wall_s": time.perf_counter() - overall_t0,
            "n_hero_combos": n_hero_combos,
            "n_villain_combos": n_villain_combos,
            "n_per_class_strategy_keys": n_per_class,
            "j7o_strategy": dict(j7o_strategy),
            "sample_per_class_strategy": sample_per_class,
            "status": "complete",
        }
    except Exception as e:
        solve_wall = time.perf_counter() - t_solve
        print(f"[{args.label}] SOLVE FAILED after {solve_wall:.2f}s: {e!r}", flush=True)
        out = {
            "label": args.label,
            "top_k": args.top_k,
            "iters": args.iters,
            "bp_wall_s": bp_wall,
            "cont_wall_s": cont_wall,
            "solve_wall_s": solve_wall,
            "total_wall_s": time.perf_counter() - overall_t0,
            "status": "error",
            "error": repr(e),
        }
        if args.json_out:
            Path(args.json_out).write_text(json.dumps(out, indent=2, default=str))
        return 1

    print(json.dumps(out, indent=2, default=str), flush=True)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
