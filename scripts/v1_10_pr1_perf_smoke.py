"""v1.10 PR-1 perf gate — flop top_k=4 iter=5 on Ad8h9d.

Target: complete in <60s with RSS peak <=1.5 GB.
Pre-PR baseline (main): OOM-killed at ~5 min with RSS peak ~2.3 GB.

Uses the Rust vector-form RvR solver directly (bypasses blueprint
generation, which would otherwise take 10+ min for a 40 BB blueprint).
The flop solve itself is the workload of interest.
"""

from __future__ import annotations

import resource
import sys
import time

from poker_solver.card import Card
from poker_solver.hunl import HUNLConfig, Street
from poker_solver.range_aggregator import solve_range_vs_range_nash


def main() -> int:
    flop_board = (
        Card.from_str("Ad"),
        Card.from_str("8h"),
        Card.from_str("9d"),
    )
    # Top 4 hand classes per player (smallest valid filter), plus the hero
    # J7o pin. Approximates the J7o flop fixture without going through
    # blueprint propagation (which would add 10+ min of preflop solve).
    #
    # SB-opens-3x typical top-4: AA, KK, QQ, JJ; BB-calls top-4 similar
    # premium tier. Pin J7o so the hero's specific class is in the range.
    hero_classes = ["AA", "KK", "QQ", "JJ", "J7o"]
    villain_classes = ["AA", "KK", "QQ", "JJ"]

    # HandClass is a str alias in this codebase.
    hero_range = list(hero_classes)
    villain_range = list(villain_classes)

    # Build a flop-starting HUNL config from the J7o fixture's preflop
    # actions (SB raise 3x → BB call). Pot after preflop = 6 BB = 600
    # cents (at chip_per_bb = 100), each player has contributed 3 BB.
    pot_cents = 600
    contrib = (300, 300)
    cfg = HUNLConfig(
        starting_stack=4000,  # 40 BB stacks
        big_blind=100,
        small_blind=50,
        ante=0,
        bet_size_fractions=(0.33, 0.75, 1.0, 1.5, 2.0),
        preflop_raise_cap=4,
        postflop_raise_cap=3,
        starting_street=Street.FLOP,
        initial_board=flop_board,
        initial_pot=pot_cents,
        initial_contributions=contrib,
        initial_hole_cards=(),
    )

    print(f"Flop solve smoke: top_k_per_side=4 (+J7o pin), iters=5, board=Ad8h9d", flush=True)
    print(f"  hero classes: {hero_classes}", flush=True)
    print(f"  villain classes: {villain_classes}", flush=True)

    t0 = time.time()
    result = solve_range_vs_range_nash(
        config_template=cfg,
        hero_range=hero_range,
        villain_range=villain_range,
        iterations=5,
        compute_exploitability_at_end=False,
    )
    elapsed = time.time() - t0
    # macOS getrusage returns ru_maxrss in BYTES on darwin (not KB).
    rss_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_mb = rss_bytes / 1024 / 1024
    print(f"\nFlop solve complete:", flush=True)
    print(f"  wall time: {elapsed:.1f}s (target <60s)", flush=True)
    print(f"  RSS peak:  {rss_mb:.0f} MB (target <=1500 MB)", flush=True)
    print(f"  per_history rows: {len(result.per_history_strategy)}", flush=True)
    print(f"  hero combos: {result.hand_count_per_player[0]}, "
          f"villain combos: {result.hand_count_per_player[1]}", flush=True)
    print(f"  decision_node_count: {result.decision_node_count}", flush=True)

    target_met = elapsed < 60.0 and rss_mb <= 1500.0
    print(f"\nGATE: {'PASS' if target_met else 'FAIL'} "
          f"(time<60s: {elapsed < 60.0}, rss<=1500MB: {rss_mb <= 1500.0})", flush=True)
    return 0 if target_met else 1


if __name__ == "__main__":
    sys.exit(main())
