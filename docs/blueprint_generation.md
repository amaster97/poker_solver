# Premium-A Blueprint Generation

Phase 1 of the Premium-A subplan (`docs/premium_a_blueprint_subplan.md`, task #68).
Builds the offline pipeline that produces the 169-class preflop blueprint shards consumed by Phase 2's loader.

## Quick start

```bash
# Single cell, smoke iters (~20s wall on M4 Pro):
python scripts/generate_preflop_blueprint.py \
  --depth 40 --ante none --iterations 100 \
  --output /tmp/blueprint_smoke/

# Full Phase 1.5 production grid (27 cells, OVERNIGHT compute — run on user
# terminal, NOT as an agent — see Phase 1.5 below):
python scripts/generate_preflop_blueprint.py \
  --all-depths --all-antes --iterations 25000 \
  --output assets/blueprints/

# Resume after interruption — idempotent, skips completed cells:
python scripts/generate_preflop_blueprint.py \
  --all-depths --all-antes --iterations 25000 \
  --output assets/blueprints/
```

## What gets generated

For each `(stack_depth, ante_config)` cell:

1. One gzipped JSON file: `preflop_169class_{depth}bb_{ante}.json.gz`
2. One entry in `manifest.json` listing the shard + its sha256 + metadata

Locked grid (per user decision):

- **9 depths**: 20, 30, 40, 60, 80, 100, 150, 175, 200 BB
- **3 ante configs**: `none` (0 BB), `half` (0.5 BB), `full` (1.0 BB)
- Total: **27 cells**

Target compressed size: ~30-60 MB total across 27 cells at 25K iters
(observed: ~672 KB per cell at 100 iters, depth 40; production iter
counts will produce richer strategies but gzip compresses well on
sparse-ish probability tensors).

## Asset format

### Per-shard schema (gzipped JSON)

```json
{
  "schema_version": "v1.0",
  "config": {
    "stack_bb": 40,
    "ante_bb": 0.0,
    "iterations": 25000,
    "alpha": 1.5, "beta": 0.0, "gamma": 2.0,
    "preflop_open_sizes_bb": [2.0, 3.0, 4.0, 5.0],
    "preflop_reraise_multipliers": [2.0, 3.0, 4.0, 5.0],
    "preflop_raise_cap": 4,
    "small_blind_bb": 0.5
  },
  "convergence": {
    "wall_seconds": 17.7,
    "final_exploitability_bb100": null
  },
  "infosets": {
    "||p|": {
      "actions": ["fold", "call", "open_to_200", "open_to_300", "open_to_400", "open_to_500", "all_in"],
      "strategy": {
        "AA": [0.0, 0.03, 0.03, 0.44, 0.40, 0.10, 0.0001],
        "KK": [0.0, 0.04, 0.05, 0.66, 0.18, 0.06, 0.0001],
        "72o": [0.9999, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
      }
    },
    "||p|b300|": { ... }
  }
}
```

Infoset keys carry the **engine's lossless history suffix** (`||p|<action_history>`). The leading `||p|` marks the preflop street; postflop is out of scope for Phase 1.

Strategy values are **per-hand-class action distributions**. Each row sums to 1.0 within float tolerance (≤1e-4 per row; ≤1e-5 in practice).

### Manifest schema (`manifest.json`)

```json
{
  "schema_version": "v1.0",
  "premium_a_version": "v1",
  "generated_date_utc": "2026-05-28T05:44:21Z",
  "shards": [
    {
      "stack_bb": 40,
      "ante_bb": 0.0,
      "filename": "preflop_169class_40bb_anteNone.json.gz",
      "sha256": "63420f24f068504e45d08728d5b57e3cc1b9e9e2e72b80e0c4df34e142034307",
      "file_size_bytes": 672439,
      "final_exploitability_bb100": null,
      "wall_seconds": 17.73,
      "iterations": 100
    }
  ]
}
```

The sha256 is computed over the **uncompressed JSON content** (not the gzipped bytes), so it is reproducible — gzip embeds a timestamp by default and bit-exact `.gz` reproducibility is not portable across platforms.

## CLI flags

| Flag | Default | Meaning |
|------|---------|---------|
| `--depth N` | — | Stack depth (BB). One of 20, 30, 40, 60, 80, 100, 150, 175, 200. |
| `--all-depths` | off | Enumerate all 9 supported depths. |
| `--ante {none,half,full}` | — | Ante config. `none`=0, `half`=0.5 BB, `full`=1.0 BB. |
| `--all-antes` | off | Enumerate all 3 ante configs. |
| `--iterations N` | — (required) | DCFR iterations per cell. Production: 25000. Smoke: 100. |
| `--output DIR` | — (required) | Output directory for shards + manifest. |
| `--alpha 1.5` | 1.5 | DCFR positive-regret exponent (Brown & Sandholm 2019 default). |
| `--beta 0.0` | 0.0 | DCFR negative-regret exponent (β=0 ⇒ negative regret reset). |
| `--gamma 2.0` | 2.0 | DCFR strategy-sum decay exponent. |
| `--preflop-open-sizes-bb` | `2.0,3.0,4.0,5.0` | Absolute-BB open sizes (SB's first raise). |
| `--preflop-reraise-multipliers` | `2.0,3.0,4.0,5.0` | Multipliers of previous bet for 3-bet, 4-bet, etc. |
| `--preflop-raise-cap` | 4 | Max preflop raises per street. |
| `--small-blind-bb` | 0.5 | Small blind in BB (0.5 = chip-per-BB HU). |
| `--force` | off | Regenerate cells whose output already exists. |
| `--dry-run` | off | Validate plumbing without invoking the engine. |
| `--verbose` | off | DEBUG-level logging. |

## Engine internals (Path A internally, Path B output)

The Rust engine `solve_hunl_preflop_rvr` runs at **1326-combo resolution**
(one per concrete hole-card pair). The generation pipeline solves at
1326, then aggregates each infoset's strategy into a 169-class strategy
by uniform average within each class. This is lossless within the
engine's suit-variant approximation (the 169x169x3 equity table already
integrates over suit-overlap variants).

A follow-up engine PR may add a true 169-vector inner loop for per-iter
speedup. The **asset schema is forward-compatible** — that change will
not alter the output format.

## Phase 1.5 — overnight compute (user terminal only)

The actual production compute (27 cells × 25K iters) is a long-running
batch the user runs from their terminal. Per memory rule
`feedback_agent_execution_timeout`, agents have a ~25-45 min wall-clock
cap and would be killed silently mid-run.

Suggested invocation (with `caffeinate` to keep the Mac awake):

```bash
caffeinate -i python scripts/generate_preflop_blueprint.py \
  --all-depths --all-antes --iterations 25000 \
  --output assets/blueprints/ \
  --verbose \
  2>&1 | tee assets/blueprints/generation.log
```

Estimated wall time on M4 Pro arm64 at 25K iters per cell:

- 100 iters / 40 BB ≈ 18 s observed (single cell, smoke)
- ~250× factor for 25K iters per cell ≈ 75 min per cell (no ante; ante slightly slower)
- 27 cells × ~75-90 min ≈ **34-40 h total** (single-threaded)
- Practical recommendation: split across two terminals running in parallel (each handles half the grid via `--depth N --all-antes` slices); cuts wall to ~17-20 h.

The pipeline is idempotent — interrupting the run + re-launching with
the same args resumes from where it left off.

## Validation

The generated blueprints are validated on the way out:

- Schema version matches.
- Each infoset's strategy entries sum to 1.0 ± 1e-4.
- Action-count consistency: each strategy vector length == actions list length.
- All hand-class labels are in the canonical 169 set.

If validation flags warnings, the generation script logs them but does
NOT abort — partial output is preserved so the operator can inspect.

## Manual sanity check

After a single cell completes, run:

```python
from poker_solver.blueprint import load_blueprint
bp = load_blueprint("/tmp/blueprint_smoke/preflop_169class_40bb_anteNone.json.gz")
print(bp.infosets["||p|"]["actions"])
print(bp.infosets["||p|"]["strategy"]["AA"])
print(bp.infosets["||p|"]["strategy"]["72o"])
```

Expected (40 BB, no ante, 25K iters):

- AA fold probability ≈ 0.0; commit (call + raise + all-in) ≈ 1.0
- 72o fold probability ≈ 1.0; commit ≈ 0.0
- Hand classes between (e.g. AKo, 88) mix according to the depth-specific
  equilibrium

## Tests

- `tests/test_blueprint_pipeline.py` — 24 unit tests covering schema
  round-trip, aggregation correctness, validator, CLI dry-run + idempotent
  resume.
- `tests/test_preflop_rvr_diff.py` — existing engine differential tests;
  the pipeline does not alter engine behavior.

## Cross-references

- Subplan: `docs/premium_a_blueprint_subplan.md`
- Engine: `crates/cfr_core/src/preflop_rvr.rs`
- Equity table: `assets/preflop_equity_169x169.npz`
- Phase 2 loader (downstream PR): `poker_solver/blueprint.py` exposes
  `load_blueprint`, `load_manifest`
- Memory rules invoked: `feedback_agent_execution_timeout`,
  `feedback_silent_noop_hazard`, `feedback_continuous_pruning`
