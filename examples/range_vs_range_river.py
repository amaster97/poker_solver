"""Range-vs-range river solve — runnable starter example.

Run me:
    python examples/range_vs_range_river.py

What this does
--------------
Solves a single-street RIVER subgame against an explicit board, pot, and
stack. It is the working starting point for analyzing your own spots
beyond the built-in `tiny_subgame` fixture.

Honest framing on "range vs range" in v1.0.0
--------------------------------------------
`HUNLConfig.initial_hole_cards` is the ONLY hole-card knob the solver
consumes. It has exactly two shapes:

  A. `((c0a, c0b), (c1a, c1b))`  — fixed combo vs fixed combo. This is
     what `default_tiny_subgame()` uses, what the river-diff test against
     `noambrown/poker_solver` exercises, and what runs production-fast
     today (sub-second on Rust at 500 iters).

  B. `()`                         — empty: the chance node enumerates
     the FULL combo space (1326 × 990 = ~1.3M pairs) for both players.
     This is the closest the shipped API gets to "range vs range," but
     the post-solve `exploitability` walk over the full lossless tree is
     a Python-side bottleneck and does NOT complete in a reasonable
     wall-clock for an interactive example. (The river-diff test runs
     this path against the noambrown reference but is gated behind the
     external binary build; in routine use you will hit minutes-to-hours
     even at modest iteration counts.)

There is **no** `hero_range` / `villain_range` field that filters the
chance enumeration to a custom range (e.g. "BTN c-bet range vs BB call
range"). `Range` / `parse_range` are wired into `equity()` only, not
`HUNLConfig`. Custom-range filtering is roadmap (post-v1.0; see
`USAGE.md` §7).

To approximate "my BTN range vs villain's call range" today:
  1. Build a `Range` of candidate combos with `parse_range("...")`.
  2. For each (hero_combo, villain_combo) pair, build a fixed-combo
     `HUNLConfig` like the one below and call `solve()`.
  3. Aggregate the per-combo strategies weighted by your range mix.
This is exactly what the noambrown-diff harness does internally; it is
not yet a one-liner in the public surface.

This script uses shape A (fixed combo) so it actually runs in <1s and
returns real, validated GTO strategies. Edit the marked lines below to
solve your own spot.

Variation knobs:
  * Board:     change `BOARD` (must be 5 cards on the river)
  * Hero/villain hole cards: change `HERO_CARDS` / `VILLAIN_CARDS`
  * Stacks:    change `STACK_BB`
  * Pot:       change `POT_BB`
  * Bet sizes: change `BET_FRACTIONS` (fractions of pot)
  * Iterations: change `ITERATIONS` (more = lower exploitability)
"""

from __future__ import annotations

import time

from poker_solver import (
    HUNLConfig,
    HUNLPoker,
    Street,
    parse_board,
    parse_hand,
    solve,
)

# ---------------------------------------------------------------------------
# Spot configuration — edit these to solve a different river spot.
# ---------------------------------------------------------------------------

# Board — 5 cards on the river. `parse_board` accepts a space-separated
# string of card tokens (rank + suit, e.g. "As 7c 2d Kh 5s").
BOARD = parse_board("As 7c 2d Kh 5s")

# Hero (P0) and villain (P1) combos. `parse_hand` accepts 4-char token
# (e.g. "AhKc"). Change these to swap matchups.
HERO_CARDS = parse_hand("AhKc")
VILLAIN_CARDS = parse_hand("QdQh")

# Chip values are integer cents; 1 BB = 100 cents.
# Default: 10 BB pot, 10 BB effective behind. River SPR of 1.0.
BIG_BLIND = 100
POT_BB = 10
STACK_BB = 10

# Bet sizes available to each player (as fractions of pot). The default
# (50% / 100%) keeps the tree small; add 1.50 / 2.00 for overbets.
BET_FRACTIONS = (0.5, 1.0)

# Iteration budget. The river tree (fixed combo) is small; 500 iters
# runs in <0.1s on Rust and converges to ~1e-5 exploitability.
ITERATIONS = 500


def main() -> int:
    pot_chips = POT_BB * BIG_BLIND
    stack_chips = STACK_BB * BIG_BLIND
    hero = (HERO_CARDS[0], HERO_CARDS[1])
    villain = (VILLAIN_CARDS[0], VILLAIN_CARDS[1])

    config = HUNLConfig(
        starting_stack=stack_chips,
        big_blind=BIG_BLIND,
        starting_street=Street.RIVER,
        initial_board=tuple(BOARD),
        initial_pot=pot_chips,
        initial_contributions=(pot_chips // 2, pot_chips - pot_chips // 2),
        # Fixed combo per player — see the docstring for why empty `()`
        # is impractical today.
        initial_hole_cards=(hero, villain),
        bet_size_fractions=BET_FRACTIONS,
        postflop_raise_cap=3,
    )

    game = HUNLPoker(config)

    print(f"River spot — board {' '.join(str(c) for c in BOARD)}")
    print(f"Hero:    {hero[0]}{hero[1]}")
    print(f"Villain: {villain[0]}{villain[1]}")
    print(f"Pot {POT_BB} BB / stack {STACK_BB} BB / bets {BET_FRACTIONS}")
    print(f"Iterations: {ITERATIONS}, backend: rust")
    print("-" * 60)

    t0 = time.perf_counter()
    result = solve(game, iterations=ITERATIONS, backend="rust")
    elapsed = time.perf_counter() - t0

    print(f"Backend used:    {result.backend}")
    print(f"Iterations:      {result.iterations}")
    print(f"Runtime:         {elapsed:.3f}s")
    print(f"Game value (P0): {result.game_value:+.4f} BB / hand")
    if result.exploitability_history:
        expl = result.exploitability_history[-1]
        print(f"Exploitability:  {expl:.4e} BB / hand")
    print(f"Infosets:        {len(result.average_strategy)}")
    print("-" * 60)

    # Print a sample of the average strategy. Each infoset key is
    # "<hero hole>|<board>|<street>|<history>" (lossless mode); the
    # value is a probability vector across the legal actions in the
    # order returned by `game.legal_actions(state)`.
    print("Average strategy (first 8 infosets, sorted by key):")
    sample = sorted(result.average_strategy.items())[:8]
    for key, probs in sample:
        probs_str = ", ".join(f"{p:.3f}" for p in probs)
        print(f"  {key}")
        print(f"    -> [{probs_str}]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
