"""Quick wall-clock bench for v1.10 PR-2.

Uses a SMALLER F3.1-flavored fixture to fit within the 5h budget timing window.
Two configurations:
- "tiny": 4 classes, 1 bet size, raise_cap=1, 100 iters
- "med":  8 classes, 1 bet size, raise_cap=2, 50 iters
- "f31":  the actual F3.1 W2.3 fixture (200BB 8-class default config)

The PR-2 perf gate references "~15s baseline, <10s target" for "top_k=15
iters=100". Our F3.1 takes much longer because the W2.3 config uses
2 bet sizes + raise_cap=3 (default in solve_range_vs_range_nash via the
HUNLConfig defaults).
"""

from __future__ import annotations

import argparse
import sys
import time

from poker_solver import HUNLConfig, Street
from poker_solver.card import Card
from poker_solver.range_aggregator import solve_range_vs_range_nash


def _classes(top_k: int) -> list[str]:
    pool = [
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77",
        "AKs", "AKo", "AQs", "AQo", "AJs", "AJo",
        "KQs", "KQo", "QJs", "JTs",
    ]
    return pool[:top_k]


def run(cfg_name: str, top_k: int, iters: int, raise_cap: int, bet_fracs: tuple[float, ...]) -> None:
    board = tuple(Card.from_str(s) for s in ["Qs", "7h", "2d", "5c"])
    cfg = HUNLConfig(
        starting_stack=20_000,
        small_blind=50,
        big_blind=100,
        starting_street=Street.TURN,
        initial_board=board,
        initial_hole_cards=(),
        postflop_raise_cap=raise_cap,
        bet_size_fractions=bet_fracs,
    )
    classes = _classes(top_k)
    print(f"[{cfg_name}] top_k={top_k} iters={iters} raise_cap={raise_cap} bet_fracs={bet_fracs}")
    t0 = time.perf_counter()
    res = solve_range_vs_range_nash(
        cfg,
        hero_range=classes,
        villain_range=classes,
        iterations=iters,
        compute_exploitability_at_end=False,
    )
    wall = time.perf_counter() - t0
    print(f"[{cfg_name}] wall={wall:.3f}s decision_nodes={res.decision_node_count} hand_count={res.hand_count_per_player}")
    return wall


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", choices=["tiny", "med", "f31"], default="tiny")
    args = ap.parse_args()

    if args.config == "tiny":
        run("tiny", top_k=4, iters=20, raise_cap=1, bet_fracs=(1.0,))
    elif args.config == "med":
        run("med", top_k=8, iters=50, raise_cap=2, bet_fracs=(0.75,))
    elif args.config == "f31":
        run("f31", top_k=8, iters=100, raise_cap=3, bet_fracs=(0.5, 1.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
