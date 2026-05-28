# Preflop Blueprint — User Guide

For people who want to **use** the solver's instant preflop chart
lookup. You should be comfortable in a terminal; you do not need to read
the Python or Rust source. The [DEVELOPER.md](../DEVELOPER.md) is the
engineering-facing overview; this is the "what does blueprint mode mean
for me" companion.

## What is the preflop blueprint?

A **blueprint** is a precomputed Nash-equilibrium strategy chart for
heads-up no-limit hold'em (HUNL) preflop play, stored as a bundle of
gzipped JSON shards in `assets/blueprints/`. Each shard answers the same
question for one (stack-depth, ante) cell:

> Given the betting history so far, what mix of `fold / call / open /
> raise / all-in` should each of the 169 starting-hand classes play?

Because the shards are solved offline (~50-90 s per cell at 25,000 DCFR
iterations on M-series silicon) and shipped with the install, **looking
up a preflop decision at runtime is effectively instant** — load the
shard once, then read out one row per query. The alternative — running
the engine live at solve-time — takes minutes per cell.

You should think of blueprints the same way you'd think of a printed
GTO chart: a fast, reliable answer for the standard play envelope.
Custom assumptions (non-standard ranges, sizings outside the menu) drop
to the live solver instead. See "When to use blueprint vs custom solve"
below.

## What ships in the .dmg

The Premium-A asset bundle includes **27 cells** = 9 stack depths × 3
ante configurations, plus a manifest:

| Dimension     | Coverage                                        |
|---------------|-------------------------------------------------|
| Stack depths  | 20, 30, 40, 60, 80, 100, 150, 175, 200 BB       |
| Ante configs  | `none` (0 BB), `half` (0.5 BB), `full` (1.0 BB) |
| Hand classes  | All 169 Pio-style preflop classes per cell      |
| Action menu   | `fold`, `call`, open 2-5 BB, 3/4/5-bet ladder, all-in |
| Raise cap     | 4 raises per preflop street                     |
| Iterations    | 25,000 DCFR per cell (Brown & Sandholm 2019)    |
| Total size    | ~30-60 MB compressed (see `assets/blueprints/`) |

The blueprint ships shipped as a gzipped JSON bundle so each shard is
human-inspectable in transit and verifiable via per-shard sha256 in
`manifest.json`. Format details are in
[`blueprint_developer_guide.md`](blueprint_developer_guide.md) §"Asset
format".

## When to use blueprint vs custom solve

| Situation                                                              | Use            | Why                                       |
|------------------------------------------------------------------------|----------------|-------------------------------------------|
| Standard HU preflop, stack ∈ {20, 30, 40, 60, 80, 100, 150, 175, 200} BB, ante ∈ {0, 0.5, 1.0} BB | **Blueprint** | Direct hit; instant lookup.            |
| Standard HU preflop, stack between two anchor depths (e.g. 67 BB)      | **Blueprint** (interpolated) | The loader interpolates between bracketing anchor depths. See §"Stack depth coverage" below. |
| Postflop spot (flop / turn / river) where preflop history is reachable from the blueprint | **Subgame solve anchored on blueprint** | Realtime (seconds to ~30 s) — derives continuation ranges from the blueprint then live-solves postflop. See `poker_solver/chained.py`. |
| Custom range (e.g. modeling an opponent who 3-bets 8% from the SB)     | **Custom live solve** | Blueprint assumes both players use the equilibrium range; custom assumptions need a fresh full solve (10-20 min wall). |
| Non-standard ante (e.g. 0.25 BB ante, or 12.5% straddle equivalent)    | **Custom live solve** | Out of envelope. The 3 shipped ante configs cover the common HU formats; anything else needs to live-solve. |
| Stack depth < 20 BB                                                    | **Push/fold chart** | The bundled DCFR push/fold charts cover 2-15 BB and are exploitability-zero. The blueprint isn't designed below 20 BB. See `get_pushfold_strategy` in [USAGE.md](../USAGE.md) §3a. |
| Stack depth > 200 BB                                                   | **Custom live solve, with caution** | Out of envelope. Also: at deep stacks the Nash equilibrium has multiple solutions; expect divergence from any specific published chart (see "Common questions" below). |

## Stack depth coverage and interpolation

The blueprint is anchored at 9 stack depths: **20, 30, 40, 60, 80, 100,
150, 175, 200 BB**.

For depths between anchors (say, 67 BB), the
`poker_solver.blueprint_interp` module interpolates per infoset using
**convex linear blending** of the two bracketing anchor strategies
(60 BB and 80 BB in this example): with weight `t = (67 - 60) / (80 - 60)
= 0.35`, the returned strategy is `(1 - t) * strategy_60 + t * strategy_80`.
Because both inputs are probability vectors and `t ∈ [0, 1]`, the result
stays on the probability simplex automatically. (The script normalizes
to absorb floating-point drift.) An alternative `method="nearest"` is
available for callers who prefer snap-to-anchor behavior.

Behavior at edges:

- **Below 20 BB:** clamps to the nearest anchor (20 BB). If you're
  playing a 12 BB spot, use the push/fold chart instead — it's
  actually solved for that depth.
- **Above 200 BB:** clamps to the nearest anchor (200 BB). The Nash
  multiplicity at very deep stacks (see "Common questions") means even
  200 BB anchor strategies are one of many valid equilibria, so
  extrapolating past 200 BB doesn't gain much fidelity.
- **On-anchor depths:** exact lookup, no interpolation.

## Ante configuration selection

Three ante configs are shipped:

- `none` — 0 BB ante. Standard online HU cash and most tournament HU
  endings.
- `half` — 0.5 BB ante. Common in some MTT structures (small ante late).
- `full` — 1.0 BB ante (sometimes called "big-blind ante"). Common in
  modern tournament play.

The ante shifts pot odds materially at every infoset, so the equilibrium
strategy at 40 BB / ante=`none` is meaningfully different from 40 BB /
ante=`full`. Pick the cell that matches your actual game; don't shrug
and use `none` as a default if the structure has antes.

## Common questions

### Why doesn't this match PokerCoaching / GTO Wizard / PioSolver exactly?

Three reasons, in roughly this order:

1. **Nash multiplicity.** Heads-up no-limit has multiple Nash equilibria,
   particularly at deeper stacks (100+ BB) where pure-Nash decisions
   give way to mixed strategies over indifference manifolds. Two solvers
   running the same game can both converge to valid equilibria that
   disagree on specific cells — and both are "correct GTO." See the
   apples-to-apples validation in
   [`preflop_100bb_chart_validation_v2_2026-05-28.md`](preflop_100bb_chart_validation_v2_2026-05-28.md)
   for measured divergences against a published 100 BB chart (75.7%
   per-cell match rate with the remaining 24.3% explained by Nash
   multiplicity or sizing-menu differences).
2. **Action menu differences.** Our blueprint uses open sizes
   {2.0, 3.0, 4.0, 5.0} BB and 3/4-bet multipliers {2.0, 3.0, 4.0, 5.0}
   of the previous bet. PokerCoaching's chart uses a specific 2.5 BB
   open and 10 BB 3-bet — the closest matches in our menu are 2.5 BB
   (via a custom solve) and 8.5 BB (which is what the validation doc
   compares against). When sizings differ, marginal hands shift bucket;
   premium hands match almost perfectly.
3. **Solver-specific abstractions.** PioSolver uses a 1326-combo
   representation internally; GTO Wizard uses cloud compute with
   different convergence budgets. Our blueprint uses the **169-class
   abstraction** — see [`blueprint_developer_guide.md`](blueprint_developer_guide.md)
   §"169-class vs 1326-combo paths" for why this is lossless for
   preflop and just smaller.

For pre-shipping validation against a real published chart, see
[`preflop_100bb_chart_validation_2026-05-28.md`](preflop_100bb_chart_validation_2026-05-28.md)
(initial pass) and
[`preflop_100bb_chart_validation_v2_2026-05-28.md`](preflop_100bb_chart_validation_v2_2026-05-28.md)
(apples-to-apples re-run with limp collapsed into open).

### What's the difference between "blueprint" and the `solve_range_vs_range` aggregator?

`solve_range_vs_range` (USAGE.md §5.2) is the live per-hand aggregator
— for a custom range it runs a 1v1 subgame per hero/villain class pair
and pools the results. It's how you handle bespoke ranges or
unbundled spots. The **blueprint is the precomputed, both-players-
equilibrium version** of that same idea, baked into the install. They
solve different objects: the aggregator runs at query time against
ranges you supply; the blueprint serves frozen Nash strategies against
the equilibrium range opponent.

### Why is my custom-range solve so slow?

Because it's not using the blueprint — when you supply a custom range,
out-of-envelope depth, non-standard ante, or per-combo intensities, the
solver routes to the full live-solve path, which runs DCFR from
scratch. Budget tens of minutes for a wide-range flop solve. The
runtime is dominated by tree size, not iteration count. See USAGE.md
§5.6 for the bench numbers.

### How do I know which path my solve took?

The result object carries a `source` field (or equivalent badge in the
UI): `blueprint` (instant), `subgame` (seconds to ~30 s, blueprint-
anchored), or `live` (minutes). The UI shows this prominently in the
result pane; the Python API exposes it on the returned dataclass.

### Can I regenerate the blueprint myself?

Yes — see [`blueprint_developer_guide.md`](blueprint_developer_guide.md)
§"Regenerating blueprints". This is useful if you want a non-standard
menu (e.g. PokerCoaching's 2.5 BB open + 10 BB 3-bet for an
apples-to-apples chart comparison) or a different iteration count. Wall
time is ~30-40 h for the full 27-cell grid at 25k iters.

### Why 25,000 iterations and not more?

Empirically, the per-cell strategy is stable to within Nash-multiplicity
drift at 25k iters; the marginal benefit from more iters at this depth
is dominated by the equilibrium-selection variance discussed above.
Convergence trajectory and pilot data are in
[`preflop_rvr_high_iter_rerun_2026-05-28.md`](preflop_rvr_high_iter_rerun_2026-05-28.md).

## Cross-references

- Engineering doc: [`blueprint_developer_guide.md`](blueprint_developer_guide.md)
- Generation script: `scripts/generate_preflop_blueprint.py`
- Generation pipeline overview: [`blueprint_generation.md`](blueprint_generation.md)
- Loader API: `poker_solver/blueprint.py` (`load_blueprint`,
  `load_manifest`)
- Postflop subgame solver: `poker_solver/chained.py`
  (`ChainedSolveResult.solve_postflop`)
- Validation against published charts:
  [`preflop_100bb_chart_validation_2026-05-28.md`](preflop_100bb_chart_validation_2026-05-28.md),
  [`preflop_100bb_chart_validation_v2_2026-05-28.md`](preflop_100bb_chart_validation_v2_2026-05-28.md)
- Aggregator (live custom-range path): [USAGE.md](../USAGE.md) §5.2
- Push/fold chart (≤15 BB): [USAGE.md](../USAGE.md) §3a
- Premium-A subplan (engineering plan of record):
  [`premium_a_blueprint_subplan.md`](premium_a_blueprint_subplan.md)
