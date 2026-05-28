# Preflop Blueprint — Developer Guide

Engineering-facing reference for the Premium-A preflop blueprint
feature. Companion to the user-facing
[`blueprint_user_guide.md`](blueprint_user_guide.md) and the engineering
plan-of-record [`premium_a_blueprint_subplan.md`](premium_a_blueprint_subplan.md).

This doc describes **what actually ships** post-Phase-3:

- The asset bundle in `assets/blueprints/` (manifest + 27 shards).
- The generation pipeline (`scripts/generate_preflop_blueprint.py`).
- The generator / format module (`poker_solver/blueprint.py`).
- The lazy loader module (`poker_solver/blueprint_loader.py`, Phase 2 / PR #174).
- The stack-depth interpolation module
  (`poker_solver/blueprint_interp.py`, Phase 3 / PR #173).
- The True Path B 169-class engine kernel
  (`crates/cfr_core/src/preflop_rvr.rs::solve_hunl_preflop_rvr_class169`)
  and how it relates to the hybrid 1326-combo wrapper.
- How to add new stack depths or ante configs.
- How the blueprint connects to the postflop subgame solver
  (`poker_solver/chained.py`).

For phase status, dependency graph, and open questions during the build
itself, see `premium_a_blueprint_subplan.md`.

## Regenerating blueprints

The driver script is `scripts/generate_preflop_blueprint.py`. It is
idempotent — re-running with the same `--output` directory skips cells
whose shards already exist (unless `--force` is set).

### Single-cell smoke

```bash
python scripts/generate_preflop_blueprint.py \
  --depth 40 --ante none --iterations 100 \
  --output /tmp/blueprint_smoke/
```

Runs in ~18-20 s on M-series silicon. Produces one shard
(`preflop_169class_40bb_anteNone.json.gz`) plus a one-entry manifest.
Use this for plumbing checks (Phase 1's `--iterations 10` `--dry-run`
covers schema validation without invoking the engine).

### Production grid (27 cells)

```bash
caffeinate -i python scripts/generate_preflop_blueprint.py \
  --all-depths --all-antes --iterations 25000 \
  --output assets/blueprints/ \
  --verbose \
  2>&1 | tee assets/blueprints/generation.log
```

Wall time: roughly **30-40 h total** single-threaded on M4 Pro arm64
(per-cell wall recorded in the manifest is ~50-90 s, but that's the
solver only; full pipeline including aggregation + serialization adds
overhead). Cut the wall by ~half by splitting the grid across two
terminals: e.g. `--depth 20 --all-antes` in one, `--depth 30 --all-antes`
in another, etc.

**Do not run this as a Claude SDK agent.** Per memory rule
`feedback_agent_execution_timeout`, agents are killed silently around
25-45 min wall clock. Phase 1.5 must run on the user's terminal.

### CLI flags

| Flag                              | Default                  | Meaning                                                                 |
|-----------------------------------|--------------------------|-------------------------------------------------------------------------|
| `--depth N`                       | —                        | One of {20, 30, 40, 60, 80, 100, 150, 175, 200} BB.                     |
| `--all-depths`                    | off                      | Enumerate all 9 supported depths.                                       |
| `--ante {none,half,full}`         | —                        | `none`=0 BB, `half`=0.5 BB, `full`=1.0 BB.                              |
| `--all-antes`                     | off                      | Enumerate all 3 ante configs.                                           |
| `--iterations N`                  | required                 | DCFR iterations per cell. Production: 25000. Smoke: 100.                |
| `--output DIR`                    | required                 | Output directory for shards + manifest.                                 |
| `--alpha`                         | 1.5                      | DCFR positive-regret exponent (Brown & Sandholm 2019 default).          |
| `--beta`                          | 0.0                      | DCFR negative-regret exponent (`beta=0` resets negative regret).        |
| `--gamma`                         | 2.0                      | DCFR strategy-sum decay exponent.                                       |
| `--preflop-open-sizes-bb`         | `2.0,3.0,4.0,5.0`        | Absolute-BB open sizes (SB's first raise).                              |
| `--preflop-reraise-multipliers`   | `2.0,3.0,4.0,5.0`        | Multipliers of `last_bet_size` for 3-bet, 4-bet, etc.                   |
| `--preflop-raise-cap`             | 4                        | Max raises per preflop street.                                          |
| `--small-blind-bb`                | 0.5                      | Small blind in BB.                                                      |
| `--force`                         | off                      | Regenerate cells whose output already exists.                           |
| `--dry-run`                       | off                      | Validate plumbing without invoking the engine.                          |
| `--verbose`                       | off                      | DEBUG-level logging.                                                    |

The full Phase 1 grid is enforced in `standard_batch_specs()` in
`poker_solver/blueprint.py` — the 9-depth × 3-ante product is the
authoritative source.

## Asset format

### Layout

```
assets/blueprints/
├── manifest.json                                 # ~3 KB
├── preflop_169class_20bb_anteNone.json.gz        # ~430 KB
├── preflop_169class_20bb_anteHalf.json.gz
├── preflop_169class_20bb_anteFull.json.gz
├── preflop_169class_30bb_anteNone.json.gz
...
└── preflop_169class_200bb_anteFull.json.gz       # ~1-3 MB
```

### Per-shard schema (gzipped JSON)

```json
{
  "schema_version": "v1.0",
  "config": {
    "stack_bb": 100,
    "ante_bb": 0.0,
    "iterations": 25000,
    "alpha": 1.5, "beta": 0.0, "gamma": 2.0,
    "preflop_open_sizes_bb": [2.0, 3.0, 4.0, 5.0],
    "preflop_reraise_multipliers": [2.0, 3.0, 4.0, 5.0],
    "preflop_raise_cap": 4,
    "small_blind_bb": 0.5
  },
  "convergence": {
    "wall_seconds": 87.4,
    "final_exploitability_bb100": null
  },
  "infosets": {
    "||p|": {
      "actions": ["fold", "call", "open_to_200", "open_to_300", "open_to_400", "open_to_500", "all_in"],
      "strategy": {
        "AA": [0.0, 0.05, 0.0, 0.3, 0.40, 0.20, 0.05],
        "KK": [...],
        "72o": [0.9999, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
      }
    },
    "||p|b300|": { "...": "..." }
  }
}
```

Conventions:

- **Infoset key**: the engine's lossless `||p|<history>` suffix. The
  leading `||p|` marks the preflop street. History tokens are appended
  without separators (`b300r600c` = open to 300, raise to 600, call).
- **Hand class**: one of the 169 canonical Pio-style labels. Pairs
  (`AA`, `KK`, … `22`), suited (`AKs`, `AQs`, … `32s`), offsuit
  (`AKo`, `AQo`, … `32o`).
- **`actions`**: ordered list of user-facing action labels at this
  infoset. `strategy[hand_class][k]` is the probability of taking
  `actions[k]`.
- **Strategy rows** sum to 1.0 ± 1e-4 per row (in practice ≤ 1e-5).
- **Sparse infosets**: only infosets reachable from the root under the
  engine's action menu are present. The blueprint does not synthesize
  unreachable nodes.

### Manifest schema (`manifest.json`)

```json
{
  "schema_version": "v1.0",
  "premium_a_version": "v1",
  "generated_date_utc": "2026-05-28T07:09:44.838615+00:00",
  "shards": [
    {
      "stack_bb": 40,
      "ante_bb": 0.0,
      "filename": "preflop_169class_40bb_anteNone.json.gz",
      "sha256": "d0000f1df70f311b153943436c352f7951d0b47ed0c3eb864f95a5725e61e6c8",
      "file_size_bytes": 689345,
      "final_exploitability_bb100": null,
      "wall_seconds": 74.30,
      "iterations": 25000
    },
    "..."
  ]
}
```

The sha256 is over the **uncompressed JSON contents** of the shard, not
the gzipped bytes. Gzip headers carry a non-deterministic timestamp, so
gzipped-byte hashes are not portable across platforms. The loader
verifies the shard sha256 against the manifest at load time.

## 169-class vs 1326-combo solver paths

The engine ships **two** preflop RvR (range-vs-range) kernels in Rust:

1. **`solve_hunl_preflop_rvr`** (legacy hybrid, 1326-combo) — one
   strategy row per concrete (card0, card1) hole-pair. Solves at full
   per-combo resolution; the Python wrapper post-aggregates to 169
   classes via `aggregate_to_169_classes`.
2. **`solve_hunl_preflop_rvr_class169`** (**True Path B**, Phase 1.5
   unblock, PR #171) — one strategy row per 169-class label. The CFR
   inner loop operates on a 169-element vector directly; per-iter
   speedup ~7-12× over the 1326-combo path because there's no
   per-iteration aggregation step.

Both paths produce the **same asset schema** (per-class strategy per
infoset) — the only difference is how the strategy is computed
internally. The wrapper auto-selects the True Path B kernel via
`HandResolution.CLASS_169` (the default for blueprint generation); the
1326-combo path remains available via `HandResolution.COMBO_1326` for
differential testing.

### When to use which

| Use case                                          | Resolution              |
|---------------------------------------------------|-------------------------|
| Production blueprint generation                   | `CLASS_169` (default)   |
| Differential testing against the Python reference | `COMBO_1326`            |
| Applications that need per-combo strategies       | `COMBO_1326`            |

The 169-class abstraction is **lossless for preflop** under the
engine's existing approximations: preflop equity is suit-symmetric
modulo blockers, and the 169×169×3 equity table at
`assets/preflop_equity_169x169.npz` already integrates over the three
suit-overlap variants. Aggregating the per-combo strategy uniformly
within a class is therefore lossless to within the table's own
suit-variant approximation.

### True Path B engine internals

The 169-class kernel lives in
`crates/cfr_core/src/preflop_rvr.rs` lines 1573+. Key pieces:

- `solve_hunl_preflop_rvr_class169(...)` — top-level entry point
  exposed via PyO3 in `crates/cfr_core/src/lib.rs:722`.
- `Class169TerminalCache` / `Class169LeafEntry` (line 1853+) — per-leaf
  cache. A Fold leaf's value vector for the 169 classes depends only
  on which player folded and the contributions at that leaf; the cache
  reuses the per-(hero_class, villain_class) blocker-mass table across
  all CFR iterations.
- `build_class169_blocker_mass()` (line 1772+) — precomputes the
  169×169 blocker-respecting weight table once at solve start.

The Python wrapper at `poker_solver/blueprint.py::generate_blueprint`
dispatches between the two kernels based on the `hand_resolution`
argument; the asset format is identical in both cases, so swapping is
transparent to downstream consumers.

## Adding new stack depths or ante configs

To extend the supported grid (e.g. add 50 BB for MTT use, or a 0.25 BB
ante for a specific tournament structure):

1. Edit `poker_solver/blueprint.py::standard_batch_specs()` to include
   the new `(stack_bb, ante_bb)` pair. The function returns a
   `list[BatchSpec]`; just append.
2. Edit `scripts/generate_preflop_blueprint.py::SUPPORTED_DEPTHS` and/or
   `SUPPORTED_ANTE_TOKENS` so the CLI accepts the new value.
3. If the new ante isn't 0.0 / 0.5 / 1.0 BB, the shard filename will
   use the fallback format `ante{value:.2f}` (see
   `blueprint_shard_filename` in `blueprint.py:641`). Update the
   downstream UI label map if you want a friendlier name.
4. Regenerate the affected cells. The pipeline is idempotent, so you
   can just re-run with `--all-depths --all-antes` and existing cells
   skip.
5. Re-run the manifest validation tests:
   `pytest tests/test_blueprint_pipeline.py`.

The action menu (`preflop_open_sizes_bb`, `preflop_reraise_multipliers`,
`preflop_raise_cap`) is a per-cell config, not a global. To add a
different menu (e.g. PokerCoaching's 2.5 BB open + 10 BB 3-bet), pass
the new menu through the CLI:

```bash
python scripts/generate_preflop_blueprint.py \
  --depth 100 --ante none --iterations 25000 \
  --preflop-open-sizes-bb 2.5 \
  --preflop-reraise-multipliers 4.0 \
  --output /tmp/blueprint_chartparity/
```

This produces a separate shard at a separate path; it does not
overwrite the standard-menu shard. The loader keys on
`(stack_bb, ante_bb)`, so two shards for the same cell with different
menus must live in different directories.

## How blueprint connects to the postflop subgame solver

The postflop subgame solver in `poker_solver/chained.py` consumes the
blueprint's converged preflop strategy to derive **continuation ranges**
per (hero_class, villain_class) pair for any preflop terminal that
reaches the flop. The connection is:

1. **Stage 1 (preflop)** — `ChainedSolveResult` loads the blueprint
   shard matching the spot's `(stack_bb, ante_bb)`. Each infoset's
   169-class strategy is the converged Nash response for that history.
2. **Stage 2 (range derivation)** — for a given preflop action sequence
   (e.g. SB open, BB 3-bet, SB call) the orchestrator walks the
   blueprint along that history and derives, per player:
   `cont_weight[class] = combo_count(class) × Π action_prob along the path`.
   The result is a `{class: weight}` map per player — the continuation
   range entering the flop.
3. **Stage 3 (postflop)** — `solve_postflop(action_seq, board)` invokes
   `solve_range_vs_range_nash` on the derived continuation ranges with
   the matched preflop pot threaded in as `initial_contributions` /
   `initial_pot`. Results are cached by
   `(canonical_action_sequence, board)`.

The continuation-range derivation is in
`poker_solver/chained.py::_derive_continuation_ranges` (see
`chained.py:1-100` for the orchestrator docstring). Postflop solve time
is dominated by tree size; expect seconds to ~30 s for typical
single-bet-size flop / turn / river spots.

Caveats baked into the design:

- **Single-pass orchestration.** The chained orchestrator does NOT
  iterate preflop ↔ postflop. The blueprint's preflop strategy is taken
  as fixed when deriving continuation ranges. For spots where the
  postflop solve would meaningfully shift the preflop equilibrium, the
  blueprint may be slightly off — but the per-class divergence is
  bounded by the preflop Nash multiplicity, which is the dominant
  source of variance anyway.
- **No pre-solved flop board cache.** The orchestrator solves each
  postflop board on demand and caches by suit-isomorphism canonical
  key. A future PR may pre-solve the 30 / 1755 representative flops to
  amortize this cost; that's out of scope for Premium-A v1.
- **Custom ranges still bypass the blueprint.** If you supply a
  non-equilibrium range, the chained orchestrator routes to the full
  live-solve path; the blueprint is only consulted when both players'
  ranges match the equilibrium opener (i.e. no user-supplied range
  override).

## Validation pipeline

Per-shard checks run on every save (`validate_blueprint` in
`blueprint.py:987`):

- Schema version matches `SCHEMA_VERSION` ("v1.0").
- Each strategy row sums to 1.0 ± 1e-4.
- `strategy[class]` length equals `actions` length per infoset.
- Every `hand_class` label is in `CANONICAL_169_CLASSES`.

Test coverage:

- `tests/test_blueprint_pipeline.py` — unit tests covering schema
  round-trip, 169-class aggregation correctness, validator, CLI
  dry-run, and idempotent resume.
- `tests/test_preflop_rvr_diff.py` — engine differential tests
  (1326-combo path vs Python reference).

Two empirical validation passes against external charts:

- [`preflop_100bb_chart_validation_2026-05-28.md`](preflop_100bb_chart_validation_2026-05-28.md)
  — initial 100 BB cell vs a published PokerCoaching chart.
- [`preflop_100bb_chart_validation_v2_2026-05-28.md`](preflop_100bb_chart_validation_v2_2026-05-28.md)
  — apples-to-apples re-run with limp collapsed into open; 75.7%
  per-cell match rate, remaining divergence attributable to Nash
  multiplicity and sizing-menu differences. Per memory rule
  `feedback_external_solver_sanity_check`, external charts are sanity
  checks, not strict ground truth — agreement is informational.

## Cross-references

- User guide: [`blueprint_user_guide.md`](blueprint_user_guide.md)
- Phase plan: [`premium_a_blueprint_subplan.md`](premium_a_blueprint_subplan.md)
- Phase 1 generation pipeline: [`blueprint_generation.md`](blueprint_generation.md)
- Generator script: `scripts/generate_preflop_blueprint.py`
- Generator + format module: `poker_solver/blueprint.py`
- Lazy loader (Phase 2): `poker_solver/blueprint_loader.py`
- Stack-depth interpolation (Phase 3): `poker_solver/blueprint_interp.py`
- 1326-combo engine kernel: `crates/cfr_core/src/preflop_rvr.rs::solve_hunl_preflop_rvr`
- 169-class engine kernel: `crates/cfr_core/src/preflop_rvr.rs::solve_hunl_preflop_rvr_class169`
- Equity table: `assets/preflop_equity_169x169.npz`
- Postflop subgame orchestrator: `poker_solver/chained.py`
- Chart validation results: `preflop_100bb_chart_validation_*.md`
- PRs of record: #163 (subplan), #167 (Phase 1 hybrid pipeline),
  #171 (Phase 1.5 True Path B 169-class kernel),
  #173 (Phase 3 interpolation), #174 (Phase 2 loader),
  #175 (Phase 7 diff-test inventory)
