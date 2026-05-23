# PR 4 Agent B — bucket lookup + persistence + HUNL integration

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 4 Agent B.**
**Your scope:** the bucket lookup + serialization stages of the card abstraction pipeline, the CLI orchestrator (`precompute-abstraction`), and the integration touches to `HUNLPoker.infoset_key` / `HUNLConfig` / `poker_solver/__init__.py` / `poker_solver/cli.py`.
**Your contract:** produce `buckets.py` + `precompute.py` + `abstraction/__init__.py`; modify the four existing files listed under §"Strict file ownership" exclusively for the abstraction wiring; consume Agent A's `equity_features.py` + `emd_clustering.py` exports; expose `lookup_bucket`, `load_abstraction`, `save_abstraction`, `AbstractionTables`, `build_abstraction` for Agent C's tests + downstream PRs.
**Your success criteria:** ruff clean, black clean, `mypy --strict` clean on new code; `.npz` round-trip is byte-stable given a seed; `HUNLPoker.infoset_key` is lossless when `abstraction is None` (PR 3 behavior preserved); ALL 138 existing tests still pass; CLI `precompute-abstraction` runs end-to-end on a tiny config.
**File ownership:** you own `poker_solver/abstraction/buckets.py`, `poker_solver/abstraction/precompute.py`, `poker_solver/abstraction/__init__.py`, and you may EDIT `poker_solver/hunl.py`, `poker_solver/__init__.py`, `poker_solver/cli.py` per the integration scope below — nothing else.

---

## Strict file ownership

**You own (create new):**
- `/Users/ashen/Desktop/poker_solver/poker_solver/abstraction/__init__.py`
- `/Users/ashen/Desktop/poker_solver/poker_solver/abstraction/buckets.py`
- `/Users/ashen/Desktop/poker_solver/poker_solver/abstraction/precompute.py`

**You may modify (existing files, additive edits only):**
- `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` — add the `abstraction` field to `HUNLConfig`; modify `infoset_key` to switch on `abstraction is None` (lossless) vs `abstraction is not None` (bucketed). NO other changes to `hunl.py`. PR 3's lossless behavior must be preserved bit-for-bit when `abstraction is None`.
- `/Users/ashen/Desktop/poker_solver/poker_solver/__init__.py` — add re-exports for `AbstractionTables`, `AbstractionRef`, `load_abstraction`, `save_abstraction`, `lookup_bucket`, `resolve_abstraction_ref`, `build_abstraction`, `canonicalize_for_suit_iso`. Add to `__all__`. No other changes.
- `/Users/ashen/Desktop/poker_solver/poker_solver/cli.py` — add the `precompute-abstraction` subcommand and the `--abstraction PATH` flag on the `solve` subcommand. No other changes.
- `/Users/ashen/Desktop/poker_solver/pyproject.toml` — verify `numpy` is already a dep; if missing, add it. Do NOT add scikit-learn, scipy, h5py, sqlalchemy, or any other third-party dep (per Decision 7.4).

**You must NOT touch:**
- `poker_solver/abstraction/equity_features.py` — Agent A
- `poker_solver/abstraction/emd_clustering.py` — Agent A
- Any test file (`tests/test_abstraction_*`) — Agent C
- Any other `poker_solver/*.py` (`action_abstraction.py`, `card.py`, `dcfr.py`, `equity.py`, `evaluator.py`, `games.py`, `pushfold.py`, `range.py`, `solver.py`) — out of scope

If you discover that Agent A's signature is incompatible with what you need, **do not silently change either side**. Stop and write a short note to the orchestrator describing the conflict; the orchestrator will reconcile.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr4_prep/pr4_spec.md`. Internalize §3 (conceptual architecture), §4 Stages 4–5 (your stages), §5 (files to create), §6 (files to modify), §7.5 + §7.6 + §7.12 (your decisions), §8 Agent B deliverables.
2. **The PLAN (locked decisions):** `/Users/ashen/Desktop/poker_solver/PLAN.md`. Card abstraction table; the 256/128/64 bucket-count default.
3. **The autonomous log (locked D1/D2):** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md`. D1 = suit-iso INCLUDED, D2 = MC at 200K iter.
4. **Spec consistency review (PR 6 forward-compatibility):** `/Users/ashen/Desktop/poker_solver/docs/spec_consistency_review.md`. Pay attention to Blockers B1 + B2 — they amend `AbstractionTables` to include a `source_path` field so PR 6's Rust port can re-load the artifact across the PyO3 boundary. **You MUST include `source_path: Path | None = None` on `AbstractionTables` from day one** (this anticipates PR 6 without forcing a future schema bump).
5. **PR 3's `infoset_key` implementation:** `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` lines ~309-318 — the lossless implementation you must preserve when `abstraction is None`. Lines 57-73: `Street` IntEnum. Lines 76-130 (approx): `HUNLConfig` dataclass.
6. **PR 3's CLI structure:** `/Users/ashen/Desktop/poker_solver/poker_solver/cli.py` — the `_GAMES` map (line 82), `_cmd_solve` (line 89), `build_parser` (line 113). You'll add a sibling `_cmd_precompute_abstraction` and register it.
7. **Agent A's contract (your input):** see §"Agent A's exports you depend on" below.

## Default decisions LOCKED (do not deviate)

These amendments to the PR 4 spec win where the spec text differs:

- **D1 = SUIT-ISO INCLUDED in PR 4.** Your `AbstractionTables` must store the suit-iso canonical-board index keys (NOT raw 22100 boards). The board-index space is the suit-iso-reduced set (~1755 canonical flops, ~similar reduction for turn/river). Use Agent A's `canonicalize_for_suit_iso(board, hand) -> (canonical_board_key: str, suit_permutation_index: int)` as the canonical lookup key. The PR 4 spec §7.6 originally said "no suit-iso in PR 4"; that has been reversed by user decision.
- **D2 = Monte Carlo equity features at 200K iter.** This affects your `build_abstraction(...)` defaults: pass `mode="mc"`, `mc_iterations=200_000` to all of Agent A's `compute_*_features` calls. Make these CLI-configurable via `--mc-iterations N` and `--flop-mode {exact,mc}` (default mc).
- **Bucket counts:** default `(256, 128, 64)` for `(flop, turn, river)` per PLAN. CLI flag `--bucket-counts 256,128,64`.
- **Bucket file format:** `.npz` (NumPy compressed archive), default filename `abstraction_v1.npz`. Use `np.savez_compressed` (gzip).
- **Schema version:** `schema_version: int = 1` in metadata; loader checks this and raises `ValueError` on mismatch with a clear message ("artifact schema vN; loader expects schema v1; rebuild or upgrade").
- **`source_path` field on `AbstractionTables`** (per spec_consistency_review B2): `source_path: Path | None = None`. Set by `load_abstraction(path)` to the path it was loaded from; consumed by PR 6's Rust port to re-load across the PyO3 boundary. Persisted-but-not-required at save time (i.e., the on-disk `.npz` does NOT contain `source_path` — only the in-memory dataclass does).
- **`HUNLConfig.abstraction` field default = `None`** (lossless). When `None`, PR 3's infoset_key behavior is unchanged. When set, infoset_key emits the bucketed form for postflop streets only; preflop ALWAYS uses the lossless form (per Decision 7.12).
- **No new third-party deps.** Imports: `numpy`, `poker_solver.*`, stdlib only.

## Agent A's exports you depend on

You consume these from `poker_solver/abstraction/equity_features.py` and `poker_solver/abstraction/emd_clustering.py`. If Agent A's signatures drift, flag it — do not silently adapt.

```python
# From equity_features.py:
def equity_distribution(board, hole_cards, street, H=50, mode="mc",
                        mc_iterations=200_000, rng=None) -> np.ndarray: ...

def compute_river_features(boards, hands_per_board, H=50, mode="mc",
                           mc_iterations=200_000, seed=42, progress=False) -> np.ndarray: ...

def compute_turn_features(...) -> np.ndarray: ...  # same shape
def compute_flop_features(...) -> np.ndarray: ...  # same shape

def canonicalize_for_suit_iso(board, hand) -> tuple[str, int]: ...

# From emd_clustering.py:
def emd_1d(p, q) -> float: ...
def batch_emd(points, centroids) -> np.ndarray: ...

@dataclass
class KMeansResult:
    assignments: np.ndarray  # shape (N,), uint16
    centroids: np.ndarray    # shape (K, H), float32
    history: list[float]

def kmeans_emd(features, K, seed=42, max_iter=200,
               change_tolerance=0.001) -> KMeansResult: ...
```

## Public API you produce (signatures Agent C tests + downstream PRs depend on)

Type hints required (mypy --strict).

### `poker_solver/abstraction/buckets.py`

```python
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from poker_solver.card import Card
from poker_solver.hunl import Street


@dataclass(frozen=True)
class AbstractionTables:
    """In-memory representation of a bucket lookup table for all three postflop streets.

    Persisted via save_abstraction / load_abstraction (see below).
    All buckets indexed by suit-iso-canonicalized (board_key, hand_key) pairs.
    Preflop is NOT stored; preflop infosets are always lossless.
    """
    # Per-street arrays. Each *_assignments is a flat uint8/uint16 array of bucket ids
    # indexed by (canonical_board_idx * max_hands_per_board) + canonical_hand_idx.
    # For more space-efficient indexing, a per-street dict mapping
    # canonical_board_key (str) -> {canonical_hand_key (str): bucket_id (int)} is
    # equivalent — pick the representation that round-trips cleanly via np.savez.

    flop_assignments: np.ndarray  # dtype uint8 (K_flop=256 fits in u8)
    turn_assignments: np.ndarray  # dtype uint8 (K_turn=128 fits in u8)
    river_assignments: np.ndarray  # dtype uint8 (K_river=64 fits in u8)

    # Per-street index: maps canonical_board_key (str) -> offset into *_assignments
    # for the first hand of that board. May be implemented as np.ndarray of dtype
    # object containing pickled dicts, OR as parallel uint32 offset arrays + a
    # separate key array. Document your choice in a comment.
    flop_board_index: dict[str, int]  # canonical_board_key -> start offset
    turn_board_index: dict[str, int]
    river_board_index: dict[str, int]

    # Per-(board, hand) inner index: for each board key, maps canonical_hand_key
    # (the suit-iso-canonicalized hand string from Agent A's helper) -> position
    # within that board's slice of *_assignments.
    flop_hand_index: dict[str, dict[str, int]]
    turn_hand_index: dict[str, dict[str, int]]
    river_hand_index: dict[str, dict[str, int]]

    # Metadata dict (per spec §4 Stage 5). Top-level keys:
    #   schema_version: int (must == 1)
    #   bucket_counts: tuple[int, int, int]  (flop, turn, river)
    #   feature_bins: int (H)
    #   seed: int
    #   build_timestamp: str (ISO 8601)
    #   build_duration_sec: float
    #   lossless_streets: list[str] (empty for v1; future-proofing per spec §10)
    #   flop_mode: str ("exact" or "mc")
    #   mc_iterations: int
    metadata: dict[str, object]

    # PR 6 forward-compat (per spec_consistency_review B2). NOT persisted to disk;
    # populated by load_abstraction(path) for PyO3 boundary re-loading. Always None
    # for in-memory-built (via build_abstraction) tables until they're saved+reloaded.
    source_path: Path | None = field(default=None)


@dataclass(frozen=True)
class AbstractionRef:
    """Lightweight pointer to an on-disk abstraction artifact.

    Declared per pr4_spec.md §3.5 + consistency review v2 NEW-1.
    `HUNLConfig.abstraction` carries an `AbstractionRef` (not `AbstractionTables`)
    so the PyO3 boundary in PR 6 can ship the path string across without
    serializing the full in-memory table object.
    """

    source_path: str
    version: str  # mirrors metadata["version"] in the .npz; cross-check on load


def resolve_abstraction_ref(ref: AbstractionRef) -> AbstractionTables:
    """Resolve a ref to a loaded `AbstractionTables` (cached after first load).

    Caching: use module-level `lru_cache(maxsize=4)` keyed on (source_path, version).
    The cache avoids re-reading the .npz on every infoset_key call. The maxsize
    permits a few different abstraction versions to coexist (e.g. during A/B test).

    On load, asserts that `tables.metadata["version"] == ref.version`; raises
    `ValueError` on mismatch (refuses to silently use a stale artifact).
    """
    ...


def lookup_bucket(
    tables: AbstractionTables,
    board: Sequence[Card],
    hole_cards: tuple[Card, Card],
    street: Street,
) -> int:
    """Return the bucket id for (board, hole_cards) on the given street.

    - street == Street.PREFLOP: returns -1 (caller uses lossless preflop infoset).
    - street == Street.FLOP/TURN/RIVER: canonicalizes the board+hand via Agent A's
      canonicalize_for_suit_iso(...), looks up the per-street board_index +
      hand_index, returns the assignment.

    Raises:
        ValueError: if board has wrong card count for street, board+hole_cards
            conflict (a hole card appears on the board), or the canonical key
            is not in the table (this signals a build-side bug, NOT a normal
            runtime path — the table should cover all reachable boards).
    """
    ...


def save_abstraction(tables: AbstractionTables, path: Path) -> None:
    """Serialize to a single .npz file via np.savez_compressed.

    The .npz layout (per spec §4 Stage 5):
      flop_assignments   : uint8 array
      turn_assignments   : uint8 array
      river_assignments  : uint8 array
      flop_board_index   : packed-string array (one canonical_board_key per row;
                            offset = row index; uint32 offset alongside)
      turn_board_index   : ...
      river_board_index  : ...
      flop_hand_index    : packed-string array per board
      ...
      metadata           : ONE nested dict, serialized via np.savez_compressed
                            (json-encoded under metadata.npy)

    source_path is NOT persisted (per the PR 6 forward-compat decision).

    Implementation note: dicts can be persisted via `np.array(json.dumps(d),
    dtype=object)` or `np.savez(path, **arrays, metadata=np.array([json.dumps(meta)]))`.
    Pick a stable, byte-deterministic encoding.
    """
    ...


def load_abstraction(path: Path) -> AbstractionTables:
    """Read a .npz file and reconstruct AbstractionTables.

    - Verifies metadata['schema_version'] == 1; raises ValueError on mismatch.
    - Populates source_path = path (for PR 6).
    - Round-trips byte-stable: save → load → save produces identical bytes.

    Raises:
        FileNotFoundError: if path doesn't exist.
        ValueError: schema_version mismatch, or malformed file.
    """
    ...
```

### `poker_solver/abstraction/precompute.py`

```python
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import numpy as np

from poker_solver.abstraction.buckets import AbstractionTables, save_abstraction
from poker_solver.abstraction.equity_features import (
    canonicalize_for_suit_iso,
    compute_flop_features,
    compute_river_features,
    compute_turn_features,
)
from poker_solver.abstraction.emd_clustering import kmeans_emd
from poker_solver.hunl import Street


def build_abstraction(
    out_path: Path,
    bucket_counts: tuple[int, int, int] = (256, 128, 64),
    seed: int = 42,
    H: int = 50,
    max_iter: int = 200,
    streets: Sequence[Street] = (Street.FLOP, Street.TURN, Street.RIVER),
    flop_mode: Literal["exact", "mc"] = "mc",
    mc_iterations: int = 200_000,
    progress: bool = True,
    size_guard_gb: float = 1.0,
) -> AbstractionTables:
    """Orchestrate Stages 1 → 5 of the abstraction pipeline.

    1. Enumerate the suit-iso-canonical board set for each street in `streets`.
    2. For each board, enumerate the valid (no-blocker) hole-card combos
       canonicalized via canonicalize_for_suit_iso(...).
    3. Call Agent A's compute_*_features(...) to build feature matrices.
    4. Call Agent A's kmeans_emd(features, K, seed) per street.
    5. Pack into AbstractionTables, populate metadata
       (including build_duration_sec, build_timestamp, seed, mc_iterations).
    6. Check size against size_guard_gb; if the artifact would exceed, raise
       ValueError with a clear message ("artifact would exceed {size_guard_gb} GB;
       consider reducing bucket_counts or skipping a street").
    7. Call save_abstraction(tables, out_path).

    Reproducibility: same (out_path, bucket_counts, seed, H, max_iter, streets,
    flop_mode, mc_iterations) → byte-identical artifact on disk.

    Checkpoint-and-resume (per spec §9 risks): Stage 1 feature arrays may be
    saved to a tempdir alongside out_path so an interrupted build can skip
    already-computed streets. Tempdir lives in `out_path.parent / f".{out_path.stem}_tmp"`.
    """
    ...
```

### `poker_solver/abstraction/__init__.py`

Re-export the public surface:

```python
from poker_solver.abstraction.buckets import (
    AbstractionTables,
    load_abstraction,
    lookup_bucket,
    save_abstraction,
)
from poker_solver.abstraction.equity_features import (
    canonicalize_for_suit_iso,
    compute_flop_features,
    compute_river_features,
    compute_turn_features,
    equity_distribution,
)
from poker_solver.abstraction.emd_clustering import (
    KMeansResult,
    batch_emd,
    emd_1d,
    kmeans_emd,
)
from poker_solver.abstraction.precompute import build_abstraction

__all__ = [
    "AbstractionTables",
    "load_abstraction",
    "save_abstraction",
    "lookup_bucket",
    "build_abstraction",
    "canonicalize_for_suit_iso",
    "equity_distribution",
    "compute_river_features",
    "compute_turn_features",
    "compute_flop_features",
    "KMeansResult",
    "emd_1d",
    "batch_emd",
    "kmeans_emd",
]
```

### `poker_solver/hunl.py` modifications

Add to `HUNLConfig` (existing frozen dataclass):

```python
# Inside HUNLConfig (line ~76-130 of hunl.py):
abstraction: "AbstractionRef | None" = field(default=None, compare=False, hash=False)
```

**CORRECTED PER CONSISTENCY REVIEW V2 (NEW-1):** the HUNLConfig field type is `AbstractionRef | None`, NOT `AbstractionTables | None`. `AbstractionRef` is a small dataclass `(source_path: str, version: str)` declared in `poker_solver/abstraction/buckets.py` alongside `AbstractionTables`. PR 6's Rust loader needs only the path across the PyO3 boundary, not the full in-memory table.

The `compare=False, hash=False` is required because the runtime resolves the ref to an `AbstractionTables` (cached) which contains NumPy arrays. The `HUNLConfig` itself remains hashable; the abstraction ref is excluded from hashing for safety.

**Import note:** to avoid a circular import (abstraction → hunl → abstraction), use a string-annotation: `abstraction: "AbstractionRef | None"` (or a `TYPE_CHECKING` guard). Test that `from poker_solver.hunl import HUNLConfig` still works standalone.

Modify `infoset_key` (existing method at hunl.py:309-318):

```python
def infoset_key(self, state: HUNLState, player: int) -> str:
    cfg = state.config
    if cfg.abstraction is not None and state.street >= Street.FLOP:
        # Bucketed path: resolve AbstractionRef → cached AbstractionTables,
        # then call the standard `lookup_bucket(tables, ...)` API.
        from poker_solver.abstraction.buckets import (
            lookup_bucket,
            resolve_abstraction_ref,
        )
        tables = resolve_abstraction_ref(cfg.abstraction)  # cached load
        bucket_id = lookup_bucket(
            tables,  # AbstractionTables — resolved from the AbstractionRef
            state.board,
            state.hole_cards[player],
            state.street,
        )
        street_token = _STREET_TOKENS.get(state.street, "s")
        all_streets = list(state.betting_tokens) + [state.current_street_tokens]
        history = "/".join("".join(tokens) for tokens in all_streets)
        return f"b{bucket_id}|{street_token}|{history}"
    # Lossless path (PR 3 behavior preserved EXACTLY).
    if state.hole_cards:
        player_hole = _sorted_card_string(state.hole_cards[player])
    else:
        player_hole = ""
    board = _sorted_card_string(state.board)
    street_token = _STREET_TOKENS.get(state.street, "s")
    all_streets = list(state.betting_tokens) + [state.current_street_tokens]
    history = "/".join("".join(tokens) for tokens in all_streets)
    return f"{player_hole}|{board}|{street_token}|{history}"
```

**Critical:** the lossless branch must be byte-identical to PR 3's current implementation. PR 3's 138 tests must continue to pass.

### `poker_solver/cli.py` modifications

Add a `precompute-abstraction` subcommand:

```python
def _cmd_precompute_abstraction(args: argparse.Namespace) -> int:
    from poker_solver.abstraction.precompute import build_abstraction
    from poker_solver.hunl import Street

    flop_count, turn_count, river_count = (
        int(x) for x in args.bucket_counts.split(",")
    )
    street_map = {
        "flop": Street.FLOP, "turn": Street.TURN, "river": Street.RIVER,
    }
    if args.street == "all":
        streets = (Street.FLOP, Street.TURN, Street.RIVER)
    else:
        streets = (street_map[args.street],)
    out_path = Path(args.output)

    build_abstraction(
        out_path=out_path,
        bucket_counts=(flop_count, turn_count, river_count),
        seed=args.seed,
        H=args.feature_bins,
        max_iter=args.max_iter,
        streets=streets,
        flop_mode=args.flop_mode,
        mc_iterations=args.mc_iterations,
        progress=True,
    )
    print(f"Wrote abstraction to {out_path}")
    return 0
```

Register it under `build_parser()`:

```python
pa = sub.add_parser(
    "precompute-abstraction",
    help="Build the EMD-bucketed card abstraction artifact (PR 4).",
)
pa.add_argument("--output", type=str, default="abstraction_v1.npz")
pa.add_argument("--bucket-counts", type=str, default="256,128,64",
                help="Comma-separated flop,turn,river bucket counts.")
pa.add_argument("--feature-bins", type=int, default=50)
pa.add_argument("--seed", type=int, default=42)
pa.add_argument("--max-iter", type=int, default=200)
pa.add_argument("--street", choices=("flop", "turn", "river", "all"), default="all")
pa.add_argument("--flop-mode", choices=("exact", "mc"), default="mc")
pa.add_argument("--mc-iterations", type=int, default=200_000)
pa.set_defaults(func=_cmd_precompute_abstraction)
```

And add `--abstraction PATH` to the `solve` subcommand (already-existing `sv`):

```python
sv.add_argument(
    "--abstraction",
    type=str,
    default=None,
    help="Path to an abstraction .npz file; when set, infoset_key uses bucketed form.",
)
```

When `--abstraction` is set in `_cmd_solve`, load it via `load_abstraction(Path(args.abstraction))` and attach it to the `HUNLConfig` for HUNL games (you'll need to thread this through `_build_hunl_with_args` and possibly add a config override path; if the existing `_GAMES` lookup doesn't accommodate this, add a clean hook — but keep changes minimal).

## Critical correctness items

### 1. Suit-iso canonicalized indexing (D1)

Your `lookup_bucket(tables, board, hand, street)` must call Agent A's `canonicalize_for_suit_iso(board, hand) -> (canonical_board_key, suit_permutation_index)`. The `canonical_board_key` is the lookup key into `tables.*_board_index`. The canonicalized hand (i.e., the hand after the suit-permutation chosen by Agent A) is the lookup key into the inner `*_hand_index[board_key]` dict.

**Critical:** the hand canonicalization MUST be consistent with the canonicalization at build time. If at build time you indexed `flop_hand_index[canonical_board_key][canonical_hand_key]` where `canonical_hand_key` was derived by applying `suit_permutation_index` to `hand`, then at lookup time you MUST apply the same permutation. Document the canonicalization protocol explicitly in code comments.

### 2. Bucket-file roundtrip (byte-stability)

`save_abstraction(tables, path)` then `load_abstraction(path)` then `save_abstraction(reloaded_tables, path2)` must produce **bit-identical** bytes in `path` and `path2`. This requires:
- Deterministic dict ordering (Python 3.7+ guarantees insertion order; ensure your dict builds use a stable sort, e.g., `dict(sorted(...))`).
- Deterministic NumPy array dtypes (always `np.uint8` for assignments, `np.uint32` for offsets, `np.float32` for centroid bytes if you persist them).
- Same JSON serialization for metadata (use `json.dumps(..., sort_keys=True)`).
- `np.savez_compressed` writes a zip archive; the zip metadata (file timestamps) can perturb byte-stability. Mitigation: write all underlying arrays in a fixed order via `np.savez_compressed(path, name1=arr1, name2=arr2, ...)` with explicit keyword args (avoids dict-iteration-order surprises). If zip-timestamp-induced byte drift is unavoidable, document the equivalence at the **logical-content** level (re-loading produces equal `AbstractionTables`) rather than the byte level — but try for byte-level first.

### 3. `HUNLConfig.abstraction is None` preserves PR 3 lossless behavior

Run the existing test suite (`pytest tests/test_hunl_core.py tests/test_hunl_tree.py`) BEFORE and AFTER your `hunl.py` edits. Confirm 138/138 tests still pass. The infoset keys produced for the default `HUNLConfig()` (no abstraction) must be byte-identical to PR 3's output.

### 4. CLI subcommand smoke test

After your CLI edits, run:
```bash
poker-solver precompute-abstraction --output /tmp/test_abstraction.npz \
    --bucket-counts 4,2,2 --feature-bins 10 --street river \
    --mc-iterations 1000 --seed 0
```
This should produce `/tmp/test_abstraction.npz` in under 60 seconds with a tiny river-only artifact for testing. Then:
```bash
poker-solver solve --game hunl --hunl-mode tiny_subgame \
    --abstraction /tmp/test_abstraction.npz --iterations 100
```
should run without crash.

### 5. Size guard rail

`build_abstraction(..., size_guard_gb=1.0)` checks the estimated artifact size after Stage 4 (before save) and raises `ValueError` if it would exceed `size_guard_gb`. Estimation: `(sum of *_assignments.nbytes + index overhead) / 1e9`. With suit-iso (D1) applied, expected size is well under 100 MB; the 1 GB guard rail is a safety net against build bugs that produce an oversized artifact.

### 6. Preflop is always lossless

`lookup_bucket(..., street=Street.PREFLOP)` returns `-1` unconditionally. `infoset_key` then takes the lossless branch even when `cfg.abstraction is not None`. This matches Decision 7.12.

### 7. `mypy --strict` compatibility for `HUNLConfig.abstraction`

The forward reference `"AbstractionTables | None"` plus the circular-import avoidance is a known mypy strict-mode trap. Either:
- Use `from __future__ import annotations` + a `TYPE_CHECKING` import guard:
  ```python
  from typing import TYPE_CHECKING
  if TYPE_CHECKING:
      from poker_solver.abstraction.buckets import AbstractionTables
  ```
- OR import `AbstractionTables` directly and accept that hunl.py now depends on abstraction/. (This is fine if abstraction/ does NOT import from hunl.py — but Agent A imports `from poker_solver.hunl import Street`, which creates a cycle. Use the `TYPE_CHECKING` guard to break the cycle.)

Verify with: `mypy --strict poker_solver/hunl.py poker_solver/abstraction/buckets.py poker_solver/abstraction/precompute.py poker_solver/abstraction/__init__.py`.

## License-aware sourcing

Same rules as Agent A:

**You may port architecturally (not code-copy) from MIT/Apache sources:**
- `references/code/slumbot2019/src/build_kmeans_buckets.cpp` (**MIT**) — the build-pipeline shape: features → dedup → cluster → assignments → write. Cite in `precompute.py`'s module docstring.
- `references/code/noambrown_poker_solver/` (**MIT**) — architectural inspiration.

**You may NOT copy from AGPL sources:**
- `references/code/postflop-solver/` — **AGPL v3**, read-only inspiration only. No code copy. If you want to model the `.npz` schema after their on-disk format, derive it from scratch with the spec as primary source.
- `references/code/TexasSolver/` — **AGPL v3**, same rule.

**You may NOT extrapolate from training data.** Cite local references for any non-trivial pattern.

If you copy a non-trivial snippet (>~5 LOC) from an MIT source, add an attribution comment at the top of the function:
```python
# Pattern from slumbot2019/src/build_kmeans_buckets.cpp (MIT, attribution required).
# Reference: references/code/slumbot2019/src/build_kmeans_buckets.cpp
```

## Quality bar

- **ruff clean:** `ruff check poker_solver/abstraction/ poker_solver/hunl.py poker_solver/__init__.py poker_solver/cli.py` reports zero issues.
- **black clean:** `black --check poker_solver/abstraction/ poker_solver/hunl.py poker_solver/__init__.py poker_solver/cli.py` reports no changes.
- **mypy strict-clean on new + touched code:** `mypy --strict poker_solver/abstraction/ poker_solver/hunl.py` reports zero errors.
- **No new third-party deps** in `pyproject.toml`.
- **All 138 existing tests still pass.** This is the load-bearing test for your `hunl.py` modification — the lossless branch must be unchanged. Run `pytest -x` and confirm.
- **CLI subcommand works end-to-end** on a tiny config (see §"CLI subcommand smoke test" above).
- **Code size budget: ~400–600 LOC** combined across the four new+touched files (per spec §8). Stay within budget.

## Reference-first rule

Before any technical claim or code pattern, check local references. `/Users/ashen/Desktop/poker_solver/references/README.md` indexes them. Never extrapolate from training data when a local source exists.

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Lint + format
ruff check poker_solver/abstraction/ poker_solver/hunl.py poker_solver/__init__.py poker_solver/cli.py
black --check poker_solver/abstraction/ poker_solver/hunl.py poker_solver/__init__.py poker_solver/cli.py

# 2. Type-check
mypy --strict poker_solver/abstraction/ poker_solver/hunl.py

# 3. PR 3 behavior preservation
pytest -x tests/test_hunl_core.py tests/test_hunl_tree.py

# 4. Full test suite
pytest -x 2>&1 | tail -20

# 5. Smoke test CLI subcommand
poker-solver precompute-abstraction --output /tmp/test_abs.npz \
    --bucket-counts 4,2,2 --feature-bins 10 --street river \
    --mc-iterations 1000 --seed 0
test -f /tmp/test_abs.npz && echo "artifact created OK"

# 6. Smoke test load + lookup roundtrip
python -c "
from pathlib import Path
from poker_solver.card import Card
from poker_solver.hunl import Street
from poker_solver.abstraction import load_abstraction, lookup_bucket, save_abstraction

t1 = load_abstraction(Path('/tmp/test_abs.npz'))
print('schema_version:', t1.metadata['schema_version'])
print('source_path:', t1.source_path)
assert t1.source_path == Path('/tmp/test_abs.npz')

# Save → load → equal
save_abstraction(t1, Path('/tmp/test_abs2.npz'))
t2 = load_abstraction(Path('/tmp/test_abs2.npz'))
import numpy as np
assert np.array_equal(t1.river_assignments, t2.river_assignments)
print('roundtrip OK')
"

# 7. Smoke test solve with abstraction
poker-solver solve --game hunl --hunl-mode tiny_subgame \
    --abstraction /tmp/test_abs.npz --iterations 100

# 8. Smoke test solve WITHOUT abstraction (PR 3 lossless path preserved)
poker-solver solve --game hunl --hunl-mode tiny_subgame --iterations 100
```

If any of the above fails, fix the issue before reporting done.

## Report back format

When done, write a concise report (≤300 words) covering:

1. Files created + line counts; files modified + line-delta.
2. Any spec amendment you made (e.g., the `source_path` field per B2; the `compare=False, hash=False` choice on the abstraction field).
3. Verification command output (paste tails).
4. Any contract drift you flagged from Agent A.
5. License attributions added.
6. Open questions for human review.
