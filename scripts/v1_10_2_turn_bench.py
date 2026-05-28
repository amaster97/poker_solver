"""Quick wall-clock bench for v1.10 PR-2 (vector-form turn forward walk).

F3.1 W2.3 reference fixture: turn Qs 7h 2d 5c, 200 BB.

Two configurations to measure:
- top_k=15 (8-class symmetric range), iter=100 — TARGET <10s
- top_k=169 (full preflop range), iter=100 — TARGET <60s

Usage:
    python scripts/v1_10_2_turn_bench.py [--top-k 15] [--iters 100]
"""

from __future__ import annotations

import argparse
import sys
import time

from poker_solver import HUNLConfig, Street
from poker_solver.card import Card
from poker_solver.range_aggregator import solve_range_vs_range_nash

HAND_CLASSES_8 = ("AA", "KK", "QQ", "JJ", "AKs", "AKo", "AQs", "AQo")


def _all_169_classes() -> list[str]:
    """Generate all 169 preflop classes (pairs, suited, off-suit)."""
    ranks = "AKQJT98765432"
    classes: list[str] = []
    for i, r1 in enumerate(ranks):
        for j, r2 in enumerate(ranks):
            if i == j:
                classes.append(f"{r1}{r2}")
            elif i < j:
                classes.append(f"{r1}{r2}s")
            else:
                classes.append(f"{r2}{r1}o")
    # Should be 169 unique
    out: list[str] = []
    seen = set()
    for c in classes:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _top_k_classes(k: int) -> tuple[str, ...]:
    """First k classes from the 8-class symmetric list, extended."""
    if k <= len(HAND_CLASSES_8):
        return HAND_CLASSES_8[:k]
    if k >= 169:
        return tuple(_all_169_classes())
    # Otherwise: 8-class union + offsuit broadways + pairs
    extended = list(HAND_CLASSES_8) + [
        "TT", "99", "88", "77", "66", "55", "44", "33", "22",
        "AJs", "AJo", "ATs", "ATo", "A9s", "A8s", "A7s", "A6s", "A5s",
        "KQs", "KQo", "KJs", "KJo", "KTs", "QJs", "QTs", "JTs",
        "T9s", "98s", "87s", "76s", "65s",
    ]
    # Dedup
    out = list(dict.fromkeys(extended))
    return tuple(out[:k])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-k", type=int, default=15)
    ap.add_argument("--iters", type=int, default=100)
    args = ap.parse_args(argv)

    board_strs = ["Qs", "7h", "2d", "5c"]
    board = tuple(Card.from_str(s) for s in board_strs)
    classes = _top_k_classes(args.top_k)

    cfg = HUNLConfig(
        starting_stack=20_000,
        small_blind=50,
        big_blind=100,
        starting_street=Street.TURN,
        initial_board=board,
        initial_hole_cards=(),
    )

    print(f"# Bench config: top_k={args.top_k} iters={args.iters}")
    print(f"# Board: {board_strs}")
    print(f"# Classes ({len(classes)}): {list(classes)}")

    t0 = time.perf_counter()
    res = solve_range_vs_range_nash(
        cfg,
        hero_range=list(classes),
        villain_range=list(classes),
        iterations=args.iters,
        compute_exploitability_at_end=False,
    )
    wall = time.perf_counter() - t0
    print(f"# Wall: {wall:.3f}s")
    print(f"# Backend: {res.backend}")
    print(f"# Decision nodes: {res.decision_node_count}")
    print(f"# Hand count per player: {res.hand_count_per_player}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
