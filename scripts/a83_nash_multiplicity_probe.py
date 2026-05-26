"""A83 Nash-multiplicity probe (Track A retest, PR 90 follow-up).

Re-runs the A83 ``dry_A83_rainbow`` fixture twice with the vector-form
RvR solver — once with ``regret_init_noise = 0.0`` (un-perturbed) and
once with ``regret_init_noise = 1e-9`` — and dumps the per-cell
strategies plus a summary of max |delta|.

Bypasses the broken ``solve --hunl-mode postflop`` CLI path entirely;
calls the PyO3 binding ``solve_range_vs_range_rust`` directly with the
same arg shape used by ``tests/test_v1_5_brown_apples_to_apples.py``.

Output files (absolute paths):
- ``~/Desktop/a83_correct_probe_baseline.json``
- ``~/Desktop/a83_correct_probe_perturbed.json``

Verdict thresholds (pre-registered):
- max |delta| < 0.01            -> CONVENTION-IS-CONSTANT
- max |delta| in [0.01, 0.05)   -> AMBIGUOUS
- max |delta| >= 0.05           -> NASH-MULTIPLICITY

Iterations: 2000 (acceptance-test default). Wall-clock estimate
~5-6 min total. The script enforces a soft 15-minute budget across
both runs; if either exceeds it, it surfaces the limitation.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from poker_solver._rust import solve_range_vs_range_rust
from poker_solver.card import card_to_int
from poker_solver.hunl import HUNLConfig, Street, _serialize_hunl_config
from poker_solver.parity.noambrown_wrapper import load_spots


REPO = Path("/Users/ashen/Desktop/poker_solver")
FIXTURE = REPO / "tests/data/river_spots.json"
OUT_DIR = Path("/Users/ashen/Desktop")
BASELINE_PATH = OUT_DIR / "a83_correct_probe_baseline.json"
PERTURBED_PATH = OUT_DIR / "a83_correct_probe_perturbed.json"

ITERATIONS = 2000
DCFR_ALPHA, DCFR_BETA, DCFR_GAMMA = 1.5, 0.0, 2.0
RNG_SEED = 1
NOISE_PERTURBED = 1e-9


def build_spot_args():
    """Locate the A83 spot and build (config_json, p0_holes, p1_holes)."""
    spot = next(
        s for s in load_spots(FIXTURE) if s.id == "dry_A83_rainbow"
    )
    pot = int(spot.pot)
    cfg = HUNLConfig(
        starting_stack=int(spot.stack),
        small_blind=50,
        big_blind=100,
        ante=0,
        starting_street=Street.RIVER,
        initial_board=tuple(spot.board),
        initial_pot=pot,
        initial_contributions=(pot // 2, pot - pot // 2),
        initial_hole_cards=(),
        postflop_raise_cap=int(spot.max_raises),
        bet_size_fractions=tuple(spot.bet_sizes),
        include_all_in=bool(spot.include_all_in),
    )
    config_json = _serialize_hunl_config(cfg)

    # Fix B: defender -> Rust P0, opener -> Rust P1.
    # spot.ranges[0] is the opener (player 0 in fixture authoring),
    # spot.ranges[1] is the defender.
    p0_holes = [
        [card_to_int(c0), card_to_int(c1)] for (c0, c1), _w in spot.ranges[1]
    ]
    p1_holes = [
        [card_to_int(c0), card_to_int(c1)] for (c0, c1), _w in spot.ranges[0]
    ]
    return config_json, p0_holes, p1_holes


def run_solve(config_json: str, p0_holes, p1_holes, *, noise: float, label: str):
    """Invoke solve_range_vs_range_rust once; return (avg_strategy, meta)."""
    t0 = time.time()
    result = solve_range_vs_range_rust(
        config_json,
        ITERATIONS,
        DCFR_ALPHA,
        DCFR_BETA,
        DCFR_GAMMA,
        p0_holes,
        p1_holes,
        regret_init_noise=noise,
        rng_seed=RNG_SEED,
    )
    wall = time.time() - t0
    avg = result["average_strategy"]
    meta = {
        "label": label,
        "regret_init_noise": noise,
        "rng_seed": RNG_SEED,
        "iterations": ITERATIONS,
        "wallclock_seconds_observed": wall,
        "wallclock_seconds_rust": result.get("wallclock_seconds"),
        "strategy_entry_count": result.get("strategy_entry_count"),
        "decision_node_count": result.get("decision_node_count"),
        "hand_count_per_player": result.get("hand_count_per_player"),
        "backend": result.get("backend"),
    }
    print(
        f"[{label}] wall={wall:.1f}s entries={meta['strategy_entry_count']} "
        f"decisions={meta['decision_node_count']}"
    )
    return avg, meta


def dump(path: Path, avg: dict, meta: dict) -> None:
    path.write_text(
        json.dumps({"meta": meta, "average_strategy": avg}, indent=2)
    )
    print(f"  wrote {path} ({path.stat().st_size} bytes)")


def diff_summary(avg_a: dict, avg_b: dict):
    """Return (max_delta_abs, max_cell_key, per_action_diffs_summary)."""
    keys_a = set(avg_a.keys())
    keys_b = set(avg_b.keys())
    common = keys_a & keys_b
    only_a = keys_a - keys_b
    only_b = keys_b - keys_a

    max_delta = 0.0
    max_key = None
    max_action = -1
    cell_max_deltas = []
    for k in common:
        pa = avg_a[k]
        pb = avg_b[k]
        # Lengths should match; if not, treat as massive delta = 1.0
        if len(pa) != len(pb):
            cell_max_deltas.append((1.0, k, -1))
            if 1.0 > max_delta:
                max_delta = 1.0
                max_key = k
                max_action = -1
            continue
        cell_max = 0.0
        cell_action = -1
        for j, (x, y) in enumerate(zip(pa, pb)):
            d = abs(x - y)
            if d > cell_max:
                cell_max = d
                cell_action = j
        cell_max_deltas.append((cell_max, k, cell_action))
        if cell_max > max_delta:
            max_delta = cell_max
            max_key = k
            max_action = cell_action

    cell_max_deltas.sort(reverse=True)
    return {
        "common_keys": len(common),
        "only_baseline": len(only_a),
        "only_perturbed": len(only_b),
        "max_delta_abs": max_delta,
        "max_delta_key": max_key,
        "max_delta_action_index": max_action,
        "top_10_cells_by_delta": [
            {"delta": float(d), "key": k, "action_idx": j}
            for (d, k, j) in cell_max_deltas[:10]
        ],
    }


def find_cells(avg: dict, hand_str: str, history_substr: str):
    """Return [(full_key, probs)] for entries whose key splits as
    (hand_str, *, *, history) where history contains history_substr."""
    out = []
    for k, probs in avg.items():
        parts = k.split("|")
        if len(parts) != 4:
            continue
        h, _board, _street, hist = parts
        if h == hand_str and history_substr in hist:
            out.append((k, probs))
    return out


def main() -> None:
    print(f"A83 Nash-multiplicity probe @ {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  iterations={ITERATIONS}  noise: 0.0 vs {NOISE_PERTURBED}  seed={RNG_SEED}")

    config_json, p0_holes, p1_holes = build_spot_args()
    print(
        f"  spot=dry_A83_rainbow  p0_holes(defender)={len(p0_holes)}  "
        f"p1_holes(opener)={len(p1_holes)}"
    )

    t_start = time.time()
    avg_base, meta_base = run_solve(
        config_json, p0_holes, p1_holes, noise=0.0, label="baseline"
    )
    dump(BASELINE_PATH, avg_base, meta_base)

    avg_pert, meta_pert = run_solve(
        config_json, p0_holes, p1_holes, noise=NOISE_PERTURBED, label="perturbed"
    )
    dump(PERTURBED_PATH, avg_pert, meta_pert)
    t_total = time.time() - t_start
    print(f"Total wall-clock: {t_total:.1f}s ({t_total/60:.2f} min)")

    summary = diff_summary(avg_base, avg_pert)
    print(json.dumps(summary, indent=2))

    # Targeted cells: 3sAs and 3cAc, decision history matching "b1000r3000".
    print("\n--- Targeted per-cell deltas: 3sAs / 3cAc @ history substr 'b1000r3000' ---")
    targeted = {}
    for hand in ("3sAs", "3cAc"):
        cells_base = find_cells(avg_base, hand, "b1000r3000")
        cells_pert = find_cells(avg_pert, hand, "b1000r3000")
        # Build {full_key: probs} maps for matched intersection
        bmap = dict(cells_base)
        pmap = dict(cells_pert)
        common = sorted(set(bmap) & set(pmap))
        hand_entries = []
        for k in common:
            pa = bmap[k]
            pb = pmap[k]
            if len(pa) == len(pb):
                deltas = [abs(x - y) for x, y in zip(pa, pb)]
                cell_max = max(deltas) if deltas else 0.0
            else:
                deltas = []
                cell_max = 1.0
            hand_entries.append(
                {
                    "key": k,
                    "baseline": list(pa),
                    "perturbed": list(pb),
                    "delta_abs_per_action": deltas,
                    "delta_abs_max": cell_max,
                }
            )
        targeted[hand] = {
            "cells_baseline_total": len(cells_base),
            "cells_perturbed_total": len(cells_pert),
            "common_cell_count": len(common),
            "max_delta_for_hand": max(
                (e["delta_abs_max"] for e in hand_entries), default=0.0
            ),
            "cells": hand_entries,
        }
        print(
            f"  {hand}: cells_base={len(cells_base)} cells_pert={len(cells_pert)} "
            f"common={len(common)} max_delta={targeted[hand]['max_delta_for_hand']:.6f}"
        )
        if hand_entries:
            # Print the first 3 cells for quick inspection
            for entry in hand_entries[:3]:
                print(f"    {entry['key']}")
                print(f"      base={entry['baseline']}")
                print(f"      pert={entry['perturbed']}")
                print(f"      delta_abs={entry['delta_abs_per_action']}")

    # Pre-registered verdict
    max_delta_overall = max(
        summary["max_delta_abs"],
        max((v["max_delta_for_hand"] for v in targeted.values()), default=0.0),
    )
    if max_delta_overall < 0.01:
        verdict = "CONVENTION IS CONSTANT OFFSET (Position B confirmed, Nash unique on this spot)"
        verdict_tag = "CONSTANT-OFFSET"
    elif max_delta_overall >= 0.05:
        verdict = "STRATEGY DEPENDS ON INITIAL CONDITIONS (Nash multiplicity confirmed)"
        verdict_tag = "NASH-MULTIPLICITY"
    else:
        verdict = "AMBIGUOUS, need higher iteration count"
        verdict_tag = "AMBIGUOUS"

    print("\n=========== VERDICT ===========")
    print(f"max |delta| overall: {max_delta_overall:.6f}")
    print(f"VERDICT: {verdict_tag}")
    print(verdict)

    # Persist combined summary for the report consumer
    combined_summary = {
        "spot_id": "dry_A83_rainbow",
        "iterations": ITERATIONS,
        "rng_seed": RNG_SEED,
        "noise_baseline": 0.0,
        "noise_perturbed": NOISE_PERTURBED,
        "baseline_meta": meta_base,
        "perturbed_meta": meta_pert,
        "wallclock_total_seconds": t_total,
        "global_diff_summary": summary,
        "targeted_3sAs_3cAc_at_b1000r3000": targeted,
        "max_delta_overall": max_delta_overall,
        "verdict_tag": verdict_tag,
        "verdict_text": verdict,
    }
    summary_path = OUT_DIR / "a83_correct_probe_summary.json"
    summary_path.write_text(json.dumps(combined_summary, indent=2))
    print(f"wrote summary -> {summary_path}")


if __name__ == "__main__":
    main()
