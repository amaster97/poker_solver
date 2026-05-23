# PR 11 Agent A — Library module + SQLite schema + CLI integration

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 11 Agent A.**
**Your scope:** the on-disk library module (SQLite-backed cache of solved spots) + its public Python API + the CLI `library` subcommand group + the `batch-solve` CLI hook. You own the data layer that turns the per-spot solver (PR 5) into a "solve once, browse forever" workflow.
**Your contract:** produce `poker_solver/library.py` (~450 LOC), `poker_solver/library_schema.sql`, edits to `poker_solver/__init__.py` (re-exports) and `poker_solver/cli.py` (subcommand group), exporting the public surface in §"Public API contract" below; Agent B (packaging) and Agent C (tests + batch_solve) consume these signatures without seeing your internals.
**Your success criteria:** ruff clean, black clean, `mypy --strict poker_solver/library.py` clean; deterministic `spot_id` across runs and machines; gzip strategy roundtrip is bit-exact; WAL-mode concurrency works for one writer + many readers; CLI subcommands all have working `--help`; ALL existing tests still pass (your work is purely additive to `poker_solver/`).
**File ownership:** you own `poker_solver/library.py`, `poker_solver/library_schema.sql`, edits to `poker_solver/__init__.py` (re-exports only) and `poker_solver/cli.py` (new subcommands only). You may NOT modify any test file, any packaging script, any UI file, `dcfr.py`, `hunl_solver.py`, or any of PR 5's profiler module.

---

## Strict file ownership

**You own (create new):**
- `/Users/ashen/Desktop/poker_solver/poker_solver/library.py`
- `/Users/ashen/Desktop/poker_solver/poker_solver/library_schema.sql`

**You may modify (existing files, additive edits only):**
- `/Users/ashen/Desktop/poker_solver/poker_solver/__init__.py` — add re-exports for `Library`, `SpotDescription`, `SpotMetadata`, `LibraryFilter`, `LibraryStats`, `LibraryError`, `LibraryDuplicateError`, `LibrarySchemaError`. Expose `__version__`. Add the new names to `__all__`. No other changes.
- `/Users/ashen/Desktop/poker_solver/poker_solver/cli.py` — add a `library` subcommand group (`list`, `get`, `put`, `export`, `import`, `delete`, `stats`) and a top-level `batch-solve` subcommand that imports + delegates to `scripts/batch_solve.py`'s entry point. Honor the `--library-path` flag and the `POKER_SOLVER_LIBRARY_PATH` env var on every subcommand. No other changes.
- `/Users/ashen/Desktop/poker_solver/pyproject.toml` — bump `__version__` consistency check; verify there is **no** new runtime dep added (library uses only stdlib: `sqlite3`, `gzip`, `hashlib`, `json`). Agent B owns the `[project.optional-dependencies] distribution` group; do NOT add it yourself.

**You must NOT touch:**
- `scripts/batch_solve.py` — Agent C creates this. (You expose a clean Library API; Agent C wires the CSV loop on top.)
- `scripts/build_macos_dmg.sh`, `scripts/sign_and_notarize.py`, `scripts/entitlements.plist`, `assets/*` — Agent B
- Any test file (`tests/test_library*.py`) — Agent C
- Any UI file (`ui/*.py`) — gated on PR 10; out of scope for PR 11
- `poker_solver/dcfr.py`, `poker_solver/hunl_solver.py`, `poker_solver/profiler/*`, `poker_solver/solver.py`, `poker_solver/hunl.py`, `poker_solver/action_abstraction.py` — PR 11 is purely additive; read-only references

If you discover an awkward signature mid-implementation, **do not silently change it**. Stop and write a short note to the orchestrator describing the conflict; the orchestrator will reconcile.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/pr11_spec.md`. Internalize §2 (library design), §3 (public API), §5 (batch-solve CSV format — Agent C's surface but you need to be compatible), §7 (files to create — your subset), §8 (files to modify — your subset), §9 (test plan — Agent C's surface, used to confirm your API is testable), §11 critical correctness items 1, 2, 3, 4, 7, 8, 9, 10, 11, 12.
2. **The PLAN (locked decisions):** `/Users/ashen/Desktop/poker_solver/PLAN.md`. Especially "MacBook-only, no cloud spend", "no auto-population", PR 11 row description. Confirm the library is single-user single-machine.
3. **PR 5's `SolveResult` shape (the thing you serialize):** `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/pr5_spec.md` — the `SolveResult` / `HUNLSolveResult` dataclass has `average_strategy: dict[str, list[float]]`, `exploitability_history: list[float]`, `game_value: float`, `iterations: int`. Your `Library.put(spot, result)` accepts this shape.
4. **PR 3's `HUNLConfig` (wrapped by `SpotDescription`):** `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` lines 76-130 (approx) define `HUNLConfig`. Lines 57-73 define `Street` (IntEnum). Lines ~309-318 define the canonical infoset_key (board ordering convention you reuse in §2.3 canonicalization rule 1).
5. **PR 3's CLI structure (extend, don't break):** `/Users/ashen/Desktop/poker_solver/poker_solver/cli.py` — read the existing `build_parser` and subcommand pattern. Add `library` as a sibling subcommand group; add `batch-solve` as a sibling top-level subcommand. Match the existing argparse conventions (no Click, no Typer — stdlib argparse only).
6. **Existing `poker_solver/__init__.py`:** so you understand the current `__all__` and re-export pattern. Append, don't reorder.

## Default decisions LOCKED (do not deviate)

These are amendments / clarifications to the PR 11 spec; if the spec text differs, **these locked defaults win** because the user confirmed them in the brief:

- **SQLite location:** `~/.poker_solver/library.db` (created on first open, parent directory auto-mkdir). Overridable via env var `POKER_SOLVER_LIBRARY_PATH` or CLI flag `--library-path`. Spec §2.1.
- **SQLite mode:** WAL (`PRAGMA journal_mode = WAL`) — one writer, many readers. Set on every `Library.open()`. Foreign keys ON. Spec §2.2.
- **Compression:** gzip on strategy blobs, `compresslevel=6` (default). `gzip.compress(json_bytes, compresslevel=6)` on write; `gzip.decompress(...)` on read. Spec §2.4, decision 13.11.
- **Spot ID:** `sha256(canonicalized_spot_json).hexdigest()` per the rules in §2.3. JSON serialization uses `json.dumps(..., sort_keys=True, separators=(",", ":"))` for deterministic byte output. Board cards sorted ascending by `(rank, suit)`. Stack values in int cents. Bet-menu fractions sorted ascending. Antes/rake included even when 0. Solver hyperparameters (α/β/γ) excluded from the canonical form.
- **Schema version:** `schema_version = 1` stored in `spots_meta` table (`library_version` key). On `Library.open()`, if `library_version > 1`, raise `LibrarySchemaError` ("library was created by a newer solver"). If `library_version < 1` or row missing, treat as fresh DB and write the row.
- **`solver_version` mismatch policy:** soft warning (`UserWarning`) on `Library.get`, NOT an error. The cached strategy is still mathematically valid. Hard errors are reserved for `schema_version` mismatches. Spec §2.5 + critical item 7-8.
- **No new runtime dependencies.** Stdlib only: `sqlite3`, `gzip`, `hashlib`, `json`, `dataclasses`, `pathlib`, `os`, `threading`, `warnings`, `typing`. NumPy is optional (only used if `SolveResult.average_strategy` values are np.ndarrays — convert via `.tolist()` before JSON). Critical item 10.
- **Spot export format:** JSON (uncompressed, human-inspectable). The exported file is a single dict with keys `spot_description`, `solve_result`, `metadata` (including spot_id, solver_version, schema_version, created_at). NOT compressed; the export use case is "share / inspect", not "save space". Decision 13.3.
- **PyInstaller target:** arm64 only (Apple Silicon). You don't touch packaging directly; just don't write platform-specific code that would break under arm64. The library is pure stdlib so this is automatic.
- **Apple Developer enrollment:** OPTIONAL. You don't touch packaging; this affects you only through "no codesign-related metadata fields in the library schema". Skip.
- **Auto-save vs explicit save:** explicit only. Per PLAN.md "no auto-population." `Library.put` is called by the user (or batch_solve script), never automatically by the solver. Decision 13.9.

## Public API contract (signatures Agent B + Agent C depend on)

Export the following from `poker_solver/library.py`. **Signature drift breaks Agent C's tests and the batch_solve script.** Type hints required (mypy --strict).

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Imported from PR 3:
from poker_solver.hunl import HUNLConfig


# ---------- Dataclasses ----------

@dataclass(frozen=True)
class SpotDescription:
    """Identity of a solvable spot. Wraps HUNLConfig + optional initial ranges + label."""
    config: HUNLConfig
    initial_ranges: tuple[tuple[str, str], ...] | None = None  # tuple of (hand_str, weight_str) pairs or similar
    label: str = ""

    def spot_id(self) -> str:
        """Compute the deterministic SHA-256 spot ID per spec §2.3."""
        return _compute_spot_id(self)


@dataclass(frozen=True)
class SpotMetadata:
    """Lightweight row projection; no strategy blob. Returned by Library.list."""
    spot_id: str
    label: str
    street: str
    board_signature: str
    stack_bb: int
    game_value: float
    exploitability: float
    iterations: int
    abstraction_tier: str
    solver_version: str
    created_at: int  # unix epoch seconds


@dataclass(frozen=True)
class LibraryFilter:
    """Filter spec for Library.list. All fields optional (AND-combined)."""
    board_pattern: str | None = None      # regex on board_signature
    street: str | None = None             # exact match: "preflop"|"flop"|"turn"|"river"
    stack_bb_min: int | None = None
    stack_bb_max: int | None = None
    solver_version: str | None = None
    created_after: int | None = None      # unix epoch
    label_pattern: str | None = None      # regex on label


@dataclass(frozen=True)
class LibraryStats:
    total_count: int
    total_size_bytes: int                 # approximate; SUM(LENGTH(strategy_gz) + LENGTH(spot_json))
    by_street: dict[str, int]             # {"flop": 42, "turn": 13, ...}
    by_solver_version: dict[str, int]
    oldest_created_at: int | None
    newest_created_at: int | None


# ---------- Exceptions ----------

class LibraryError(Exception):
    """Base exception for the library module."""


class LibraryDuplicateError(LibraryError):
    """Raised by Library.put when overwrite=False and the spot_id already exists."""


class LibrarySchemaError(LibraryError):
    """Raised on Library.open() if the on-disk schema_version exceeds what this code knows."""


# ---------- Main class ----------

class Library:
    """Local on-disk cache of solved poker spots. SQLite-backed, WAL mode."""

    @classmethod
    def open(cls, path: Path | None = None) -> "Library":
        """Open (creating if missing) the SQLite database.

        Args:
            path: filesystem path to the DB file. Defaults to
                $POKER_SOLVER_LIBRARY_PATH if set, otherwise ~/.poker_solver/library.db.

        Raises:
            LibrarySchemaError: if the on-disk schema_version is newer than what this code supports.

        Returns:
            A connected Library instance. Use as a context manager (__enter__/__exit__) for auto-close.
        """
        ...

    def put(self, spot: SpotDescription, result: "SolveResult", *,
            overwrite: bool = False) -> str:
        """Persist a solved spot. Returns the spot_id (sha256 hex).

        Args:
            spot: SpotDescription identifying the solve input.
            result: SolveResult (PR 5) carrying the strategy + diagnostics.
            overwrite: if True, replace any existing row with the same spot_id.

        Raises:
            LibraryDuplicateError: if spot_id already exists and overwrite=False.
        """
        ...

    def get(self, spot: SpotDescription | str) -> "SolveResult | None":
        """Retrieve a spot by description (recomputes id) or by raw spot_id hex string.

        Returns:
            The SolveResult, or None if not found.

        Emits:
            UserWarning if the stored solver_version differs from the current solver.
        """
        ...

    def list(self, filter: LibraryFilter | None = None,
             *, limit: int = 1000, offset: int = 0) -> list[SpotMetadata]:
        """List spots matching filter. Returns lightweight metadata; not strategies.

        Sort order: most recent first (created_at DESC).
        """
        ...

    def export(self, spot_id: str, path: Path) -> None:
        """Write a portable single-spot JSON file (uncompressed) to `path`.

        File schema: {"spot_description": {...}, "solve_result": {...}, "metadata": {...}}.
        The `metadata` block carries spot_id, solver_version, schema_version, created_at.

        Raises:
            KeyError: if spot_id not found.
        """
        ...

    def import_(self, path: Path, *, overwrite: bool = False) -> str:
        """Import a JSON file produced by export(). Returns the spot_id of the imported row.

        Raises:
            LibraryDuplicateError: if spot_id already exists and overwrite=False.
            ValueError: if the file is not valid JSON or has the wrong schema.
        """
        ...

    def delete(self, spot_id: str) -> None:
        """Delete a spot by id.

        Raises:
            KeyError: if spot_id not found.
        """
        ...

    def stats(self) -> LibraryStats:
        """Aggregate counts, sizes, and per-street / per-version breakdown."""
        ...

    def close(self) -> None:
        """Close the underlying SQLite connection. Idempotent."""
        ...

    def __enter__(self) -> "Library": ...
    def __exit__(self, *args: Any) -> None: ...
```

Internal helpers (`_compute_spot_id`, `_canonicalize_spot`, `_serialize_strategy`, `_deserialize_strategy`, schema migration logic) are **your** choice; tests in spec §9 assert only against the public API.

## CLI surface (`poker_solver/cli.py` edits)

Add the following subcommands. Use stdlib argparse only; match the existing `_cmd_*` / `build_parser` pattern in the file. Each subcommand resolves the library path with this precedence: `--library-path` flag > `$POKER_SOLVER_LIBRARY_PATH` > `~/.poker_solver/library.db`.

```
poker-solver library list [--street STR] [--board-pattern REGEX]
                          [--stack-bb-min N] [--stack-bb-max N]
                          [--solver-version V] [--created-after EPOCH]
                          [--label-pattern REGEX]
                          [--limit N] [--offset N]
                          [--json | --table]
                          [--library-path PATH]
poker-solver library get <spot_id> [--json] [--library-path PATH]
poker-solver library put <description.json> [--overwrite] [--library-path PATH]
poker-solver library export <spot_id> <output_path.json> [--library-path PATH]
poker-solver library import <input_path.json> [--overwrite] [--library-path PATH]
poker-solver library delete <spot_id> [--library-path PATH]
poker-solver library stats [--json] [--library-path PATH]

poker-solver batch-solve --input <csv_path>
                          [--workers N] [--max-memory-gb N]
                          [--dry-run] [--library-path PATH]
```

CLI list output format:
- Default: tab-separated columns (`spot_id\tlabel\tstreet\tboard\tstacks\tvalue\texp\titers\ttier\tversion\tcreated_at`) — grep/awk friendly.
- `--json`: machine-readable JSON array of `SpotMetadata` dicts.
- `--table`: human-readable fixed-width table; if a `rich` library import succeeds, use it; otherwise fall back to tab-separated. (Decision 13.12.)

For `batch-solve`: import from `scripts.batch_solve` (Agent C's file). If the import fails (Agent C's file not present at the time you write CLI), guard the subcommand with a clear error message and a TODO comment — your job is the wiring, not the implementation.

## Critical correctness items

### 1. Spot ID determinism (spec §2.3, critical items 1+2)

`_compute_spot_id(spot)` MUST be a pure function with these properties:
- **Same description, two different machines → same ID.**
- **Description with reordered fields → same ID** (canonicalization sorts).
- **Description with a one-card-different board → different ID.**
- **Description with a 1-BB stack difference → different ID.**

Canonicalization steps (in order):
1. Sort board cards ascending by `(rank, suit)` — use the same convention as PR 3's `infoset_key`.
2. Normalize stack values to integer cents (HUNLConfig already does this; assert it).
3. Sort `bet_size_fractions` tuple ascending.
4. If `initial_ranges` present, serialize as a sorted list with each hand's canonical form (`AhKh` not `KhAh`).
5. Include `antes` and `rake` even when 0.
6. **Exclude** solver hyperparameters (α/β/γ) — they're locked at α=1.5, β=0, γ=2.0 per PLAN.md. If later exposed as per-solve knobs, add them and bump `schema_version`.
7. Final serialization: `json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))` → UTF-8 bytes → `hashlib.sha256(bytes).hexdigest()`.

Document the canonicalization rules in `_compute_spot_id`'s docstring so Agent C can write the determinism test by reading your docstring + the spec.

### 2. Compression bit-exact roundtrip (spec §2.4, critical item 4)

`SolveResult.average_strategy` is `dict[str, list[float]]`. The roundtrip must satisfy:
```python
result1 = SolveResult(average_strategy={...}, ...)
spot_id = library.put(spot, result1)
result2 = library.get(spot)
# For every infoset key, every probability:
assert result2.average_strategy[k] == result1.average_strategy[k]  # bit-exact
```

Strategy:
- Serialize with `json.dumps(strategy_dict, separators=(",", ":"))` — no whitespace.
- gzip with `compresslevel=6`.
- Deserialize: `gzip.decompress` → `json.loads`.
- Python floats preserve full IEEE-754 double precision through `json.dumps`/`json.loads` for normal values. Verify denormals + special values (0.0, 1.0, 1e-15, 1-1e-15) survive — Agent C's test 11 covers this.
- If `average_strategy[k]` is an `np.ndarray`, call `.tolist()` before serialization (you stay stdlib-only, but tolerate numpy inputs).

### 3. WAL mode + write lock (spec §3.3, critical item 3)

- `Library.open()` runs `PRAGMA journal_mode = WAL` and `PRAGMA foreign_keys = ON`.
- A single `Library` instance has one `sqlite3.Connection`.
- Wrap writes (`put`, `delete`, `import_`) with a `threading.Lock` held for the duration of the transaction. Reads (`get`, `list`, `stats`) do NOT take the lock — WAL guarantees readers see a consistent snapshot.
- Two `Library` instances on the same file (different processes or even different threads in the same process if they each `open()`) must coexist: one writer, many readers. Agent C's test 12 verifies this.

### 4. Schema version handling (spec §2.5, critical items 7+8)

- On `Library.open()`, read `spots_meta` for `library_version`. If row missing, treat as fresh and write `library_version = 1`. If present and `> 1`, raise `LibrarySchemaError` with a clear message.
- `solver_version` mismatch on `Library.get`: emit `UserWarning("loaded spot was solved by solver_version X; current is Y; strategy is still mathematically valid")`. Do NOT raise.
- The `spots_meta` table also stores `created_by` (the solver_version that first created the DB) and `created_at` (epoch). Set on first `open()` only.

### 5. Idempotent CLI (spec critical item 9, spec §5.4)

The library's `Library.put(spot, result, overwrite=False)` rejects duplicates with `LibraryDuplicateError`. This is the foundation Agent C's `batch_solve.py` relies on for idempotent re-runs ("re-running the same CSV after a crash is a no-op for already-saved spots"). Do not weaken this.

### 6. Env var + flag override (spec critical item 11)

`POKER_SOLVER_LIBRARY_PATH=/tmp/foo.db poker-solver library list` MUST honor the env var. Order of precedence for path resolution (every entry point that needs the path):
1. Explicit `path=` argument passed to `Library.open(path=...)`.
2. `--library-path PATH` CLI flag.
3. `$POKER_SOLVER_LIBRARY_PATH` environment variable.
4. `~/.poker_solver/library.db`.

Factor this into a `_resolve_library_path(explicit: Path | None) -> Path` helper used by both `Library.open` and the CLI handlers.

### 7. Export portability (spec critical item 12)

An exported JSON file is machine-portable. NO machine-specific paths in the file. The export schema is:
```json
{
  "spot_description": { /* serialized SpotDescription */ },
  "solve_result": {
    "average_strategy": { /* dict[str, list[float]] */ },
    "game_value": 0.42,
    "exploitability_history": [0.5, 0.3, 0.1],
    "iterations": 1000,
    /* ... */
  },
  "metadata": {
    "spot_id": "abc123...",
    "solver_version": "0.11.0",
    "schema_version": 1,
    "created_at": 1716000000,
    "abstraction_tier": "256/128/64",
    "board_signature": "AsKc7d",
    "stack_bb": 100,
    "street": "flop"
  }
}
```

`Library.import_(path)` reads this schema, recomputes `spot_id` from `spot_description` (sanity-check vs `metadata.spot_id`; warn if mismatch — possible if the source machine had a different canonicalization version), and writes via `put(overwrite=False)` unless `overwrite=True`.

## SQLite schema (`poker_solver/library_schema.sql`)

Match spec §2.2 exactly:

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS spots (
    id                  TEXT PRIMARY KEY,
    spot_json           BLOB NOT NULL,
    strategy_gz         BLOB NOT NULL,
    game_value          REAL NOT NULL,
    exploitability      REAL NOT NULL,
    iterations          INTEGER NOT NULL,
    abstraction_tier    TEXT NOT NULL,
    solver_version      TEXT NOT NULL,
    schema_version      INTEGER NOT NULL,
    created_at          INTEGER NOT NULL,
    board_signature     TEXT NOT NULL,
    stack_bb            INTEGER NOT NULL,
    bet_menu_hash       TEXT NOT NULL,
    street              TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_spots_board    ON spots(board_signature);
CREATE INDEX IF NOT EXISTS idx_spots_street   ON spots(street);
CREATE INDEX IF NOT EXISTS idx_spots_stack    ON spots(stack_bb);
CREATE INDEX IF NOT EXISTS idx_spots_created  ON spots(created_at);
CREATE INDEX IF NOT EXISTS idx_spots_solver   ON spots(solver_version);

CREATE TABLE IF NOT EXISTS spots_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

Load via `connection.executescript(file.read_text())` on `Library.open()`. Re-running on an existing DB is a no-op (every CREATE uses `IF NOT EXISTS`).

## Quality bar

- **ruff clean:** `ruff check poker_solver/library.py poker_solver/cli.py poker_solver/__init__.py` reports zero issues.
- **black clean:** `black --check poker_solver/library.py poker_solver/cli.py poker_solver/__init__.py` reports no changes needed.
- **mypy strict-clean on new code:** `mypy --strict poker_solver/library.py` reports zero errors. (Spec §16 success criterion.)
- **No new runtime deps.** `git diff pyproject.toml` should be empty for runtime deps. Critical item 10.
- **All existing tests still pass.** Run `pytest -x` after your work lands and confirm. Library is purely additive; you should not break anything, but a circular import or a name collision (e.g., re-exporting `list` shadowing a builtin) would do so — guard against this.
- **Code size budget: ~450 LOC** for `library.py` per spec §7. Stay within budget; do not over-engineer.

## Reference-first rule

Before any technical claim, citation, or formula, check the local references. Never extrapolate from training data when a local authoritative source exists.

- SQLite WAL mode behavior: https://www.sqlite.org/wal.html (cited in spec §15).
- Python `sqlite3` stdlib docs for parameterized queries, `executescript`, isolation level.
- Python `gzip` stdlib docs for `compresslevel` semantics.

If a fact is needed (e.g., "SHA-256 produces a 64-char hex digest"), it's trivially derivable from `hashlib` docs — cite the stdlib doc inline if non-obvious.

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Lint + format
ruff check poker_solver/library.py poker_solver/cli.py poker_solver/__init__.py
black --check poker_solver/library.py poker_solver/cli.py poker_solver/__init__.py

# 2. Type-check
mypy --strict poker_solver/library.py

# 3. Smoke test: open/put/get roundtrip
python -c "
import tempfile
from pathlib import Path
from poker_solver.library import Library

with tempfile.TemporaryDirectory() as td:
    db = Path(td) / 'lib.db'
    with Library.open(db) as lib:
        stats = lib.stats()
        assert stats.total_count == 0
        print('open + stats OK on empty DB')
"

# 4. Smoke test: spot_id determinism
python -c "
from poker_solver.library import _compute_spot_id, SpotDescription
from poker_solver.hunl import HUNLConfig
# build two semantically-equivalent SpotDescriptions, assert same id
# (concrete construction depends on HUNLConfig signature; see PR 3 spec)
print('spot_id determinism smoke OK (when fleshed out)')
"

# 5. Smoke test: CLI
poker-solver library list  # should print empty (or header) without error
poker-solver library stats  # should print zero counts

# 6. Smoke test: env var override
POKER_SOLVER_LIBRARY_PATH=/tmp/test_lib.db poker-solver library stats
test -f /tmp/test_lib.db && echo 'env var override OK' || echo 'FAILED: env var ignored'

# 7. Full test suite must still pass (your work is additive)
pytest -x 2>&1 | tail -20
```

If any of the above fails, fix the issue before reporting done. If a smoke test reveals a spec ambiguity, **stop and flag it** — do not silently work around it.

## Report back format

When done, write a concise report (≤300 words) covering:

1. Files created/modified with line counts.
2. Any spec amendment you made or contract drift you flagged (and why).
3. Verification command output (paste tails).
4. Any open question you couldn't resolve from the spec or PLAN — flag for human review.
5. License attributions (you should not need any — pure stdlib).
