# v1.3.0 — Range-vs-Range API Gap (Proposal)

**Status:** SUPERSEDED. Option B (blueprint aggregator) shipped at v1.3.0 then
was reverted in LEG 5. Option A (Rust BR port) was not implemented. The
current live path is Plan C / Stage C1 (see
`v1_3_plan_c_prompt.md`, `v1_3_stage_c1_prompt.md`,
`v1_3_plan_c_verification.md`). Doc preserved for historical context.
**Type:** Performance / API design.
**Source:** Phase 1E + Phase 2 persona acceptance results, 2026-05-23.

---

## 1. Problem statement

Phase 1E + Phase 2 persona testing
(`docs/pr13_prep/phase1_extended_results.md`,
`docs/pr13_prep/phase2_results.md`) identified one structural gap as
the largest UX failure in v1.1.0: no range-vs-range solve surface.
**7 of 14 Tier 2 / Tier 3 workflows** fail their heuristic checks for
the same reason — every solve requires `HUNLConfig.initial_hole_cards`
to be a concrete combo per player (`poker_solver/hunl.py:106`).
Range-level concepts (MDF, polarization, c-bet sizing for a range, BB
defend frequency) collapse to a 1-combo Nash where one side strictly
wins at showdown.

Empirical evidence:

- **W1E.2** BB leads 89.7%; heuristic <25%. `AdQc` always beats `Th9h`.
- **W1E.3** monotone c-bet inverts heuristic; original *lossless
  flop-start* scope **timed out at 2 minutes for 200 iterations**.
- **W1E.4** MDF vs 1.0 pot: defend = 100% vs MDF = 50% target.
- **W1E.7** range matrix iteration: per-combo loop returns identical
  output across all tiers; no signal.
- **W1E.8** polarization: value/medium correct, bluff arm collapses
  (no fold equity vs known villain).
- **W2.3** BB defend vs SB 2.5x: 9 of 9 playable hands defend 100%;
  "63.6% MDF" cannot be queried in one call.
- **W2.6** KJo 3-bets 100% because villain is a fixed weak placeholder.

`solve_hunl_postflop` and `solve_hunl_preflop` accept
`initial_hole_cards=()` in principle (chance node enumerates 1.62 M
starting combos; `hunl.py:601-618`), but the Python exploitability
walk (`solver.py:190-297`) iterates every infoset per best-response
pass. W1E.3's original scope blew the 2-minute budget at 200
iterations — the fallback path is not interactive. User impact: Sarah
cannot diff her BB 3-bet vs GTO; Daniel cannot run an MDF gauntlet;
W2.3 needs per-hand loops with manual reach-weighting.

## 2. Two design options

### Option A — Port the Python exploitability walk to Rust

Port `exploitability`, `_best_response_value`, `_collect_infosets`,
`_br_state_value` (`solver.py:190-375`) to Rust behind a PyO3 binding
matching PR 6 conventions. `HashMap<String, Vec<f64>>` strategy tables
already round-trip in `_solve_rust` (`solver.py:471-483`).

- **Effort:** 3-5 days.
- **Risk:** float drift. Python tier is the reference oracle; drift
  breaks the `noambrown` differential (PR 7,
  `tests/test_river_diff.py`). Mitigation: diff-test on 5+ fixtures
  with ≤1e-7 tolerance.
- **Pros:** Minimum-surgery. Preserves every public API. Makes the
  empty-`()` chance-enum path actually finish. Doesn't preclude
  Option B.
- **Cons:** No new UX. Doesn't reduce abstraction tree size; speedup
  is on the measurement walk, not the solve loop.

### Option B — Pluribus-blueprint aggregation harness

New function `solve_range_vs_range(config_template, hero_range,
villain_range, iterations, *, aggregate="class"|"combo", seed=None)`
that enumerates hand classes (169 canonical; 1326 if suit-aware),
solves each as a PR 9 preflop or PR 5/6 postflop subgame, and
aggregates via reach-weighted average. Output:
`dict[hand_class_str, list[float]]` for a 13×13 matrix. Pattern is
the one called out in `preflop.py:25-27` ("Pluribus blueprint,
post-v1 stretch") and the harness shape used by postflop-solver's
`Range` (`references/code/postflop-solver/src/range.rs:42`) — **not**
a port (AGPL); only the wrap-engine shape is borrowed.

- **Effort:** 5-10 days. New public function, aggregation, validation
  suite, USAGE.md, optional CLI.
- **Risk:** aggregation accuracy — combos within a 169-class hand
  don't share strategy; suit-blocker effects shift frequencies on
  paired / monotone / three-flush boards. Mitigation:
  `aggregate="class"` (fast) and `aggregate="combo"` (slow) modes;
  flag suit-sensitive boards in docs.
- **Pros:** Enables range editor UX. Matches literature. No Rust
  changes for v1.
- **Cons:** More code. Doesn't fix the empty-`()` path. UI changes
  downstream (PR 10b).

### Recommendation — Option A first, B deferred to v1.4.0

1. **Smaller blast radius** — one function port + diff test vs a new
   public API plus aggregation semantics.
2. **Unblocks the slow-path workflows.** A speedup on
   `exploitability()` makes the empty-`()` path tractable for the
   bench config (500 iters, 2 bet sizes, river start), which is what
   blocks W1E.4 / W1E.7 / W2.3.
3. **Complementary, not exclusive.** Option B sits *on top* of the
   per-subgame solver; Option A makes any subgame's exploitability
   faster, including aggregated ones.
4. **Cheaper validation.** Diff-test against Python tier; no design
   decisions about aggregation, suit-sensitivity, or UI contracts.

## 3. Detailed Option A design

**Port surface.** `exploitability`, `_best_response_value`,
`_collect_infosets`, `_br_state_value`, plus `_expected_value` and
`_game_value` to keep recursion in one tier.

**Rust entry points.** Mirror PR 6's serde-JSON pattern. Strategy
arrives as `HashMap<String, Vec<f64>>`; the tree reconstructs from
the same `HUNLConfig` JSON the Rust HUNL solver already consumes
(`hunl.py:_serialize_hunl_config`). Bindings:
`poker_solver._rust.exploitability_hunl_postflop(config_json, strategy) -> float`
and a parallel `exploitability_hunl_preflop` consuming
`PreflopSubgameGame`'s equity-leaf substitution (`preflop.py:52-97`).

**Diff-test plan.** `tests/test_exploitability_diff.py` covering:
(1) `default_tiny_subgame`; (2) PR 9 preflop subgame AhKh vs QdQc;
(3) flop-start from W1E.3 adapted; (4) river-start from W1E.4;
(5) tiny chance-enum empty-`()` config. Require ≤1e-9 on-strategy
and ≤1e-7 best-response.

**Performance target.** Empty-`()` solve completes < 60 s for the
bench config (500 iters, 2 bet sizes, river start). W1E.4 hits 1.1 s
with concrete combos; the chance-enum path was killed at 2 minutes
in W1E.3 for the same iteration count. A 5× measurement-walk speedup
is realistic.

**Acceptance.** Phase 1E W1E.2/W1E.3/W1E.4 produce results within
their 10-15-minute budgets; W2.3 169-hand sweep < 5 min.

## 4. Detailed Option B design (skeleton; deferred)

`solve_range_vs_range(config_template: HUNLConfig, hero_range: Range,
villain_range: Range, iterations: int, *, aggregate="class", seed=None) -> RangeSolveResult`
with `frequencies: dict[str, list[float]]` keyed by Pio hand-class
strings. Internal loop: enumerate combo cross-product, canonicalise
via `range.py`, dispatch each subgame through the existing solver
paths, aggregate by class or combo. PR 10b consumes `frequencies`
for the 13×13 matrix. Full design lands in
`docs/pr_proposals/v1_4_range_editor.md` after v1.3.0 ships.

## 5. v1.3.0 scope decision

- **Ship:** Option A (Rust exploitability port).
- **Defer:** Option B → v1.4.0.
- **Acceptance gate:** Phase 1E/2 workflows that timed out (W1E.3
  lossless variant; W2.3 sweep) complete inside original budgets.
- **Differential gates:** PR 7 river diff vs `noambrown` and
  Kuhn/Leduc parity (`tests/test_kuhn_diff.py`,
  `test_leduc_diff.py`) remain green.
- **No-extrapolation:** re-run the Phase 1E harness and record
  measured timings before tagging. Microbenchmarks alone don't ship.

## 6. Risk and contingency

- **Float drift.** Bit-exact match requires identical accumulation
  order. CPython's insertion-ordered `dict` matches a
  `BTreeMap`-ordered Rust BR traversal; if too expensive, accept
  ≤1e-7 drift and document it.
- **Perf gain < 2×.** If the solve loop (not the measurement walk)
  dominates the bench config, Option A's user-visible improvement
  is small. Contingency: escalate Option B to v1.3.0 and re-scope.
- **PR 10b coupling.** Option B changes PR 10b's consumed shape.
  Deferring keeps PR 10b on the existing combo result and avoids a
  coupled-release migration.

## 7. Timeline and dependencies

- **Depends on:** v1.2.0 ships first. PR 10a.5, PR 8, PR 9, PR 10b
  in flight (MEMORY.md `[Post-GA parallel launch]`). Any in-flight PR
  touching `_serialize_hunl_config`, the strategy-table shape, or
  `PreflopSubgameGame` semantics blocks the port until it merges.
- **Sequencing:** v1.2.0 → audit → v1.3.0 branch off main → 3-5 day
  implementation → diff-test gauntlet → audit → Phase 1E re-run → tag.
- **Calendar estimate:** 1-2 weeks after v1.2.0 ships, assuming no
  contention with PR 10b's UI-binding wave.
- **Honest caveat:** the perf fix gets us to "interactive" (seconds,
  not subsecond). It does not make range-vs-range "instant" — that
  needs Option B plus a resolved PR 4 abstraction artefact.

## 8. Out of scope

Node-locking (W3.1; separate v1.X PR), public best-response API
(W3.2), range editor UI (PR 10b consumes the existing combo result),
full enumerated preflop tree (Option A speeds the *measurement*
walk, not the inner solve loop).
