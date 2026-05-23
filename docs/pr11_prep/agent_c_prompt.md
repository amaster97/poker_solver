# PR 11 Agent C — tests + batch_solve.py (written from spec alone)

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 11 Agent C.**
**Your scope:** write the library tests (~15 unit tests in `tests/test_library.py`, ~5 CLI tests in `tests/test_library_cli.py`, a UI-integration stub gated on PR 10) AND the `scripts/batch_solve.py` CSV-driven solve loop. You sit at the cross-cutting integration point: tests + the user-facing batch script that exercises Agent A's library API end-to-end.
**Your contract:** ~20 tests matching spec §9 written strictly from spec without reading Agent A or Agent B's implementations; `scripts/batch_solve.py` (~200 LOC) implementing the CSV format in spec §5.1 and the behavior in spec §5.2; ambiguities surfaced as test failures that round-trip to spec edits, NOT silently smoothed over.
**Your success criteria:** ruff clean, black clean on new files; all tests are SELF-CONTAINED (use `tmp_path` for isolated DBs, build synthetic `SolveResult`s inline); batch_solve runs against a 2-row CSV with the `--dry-run` flag; ALL existing tests still pass; spec-ambiguity findings reported as written notes, not as silent test tweaks.
**File ownership:** you own `tests/test_library.py`, `tests/test_library_cli.py`, `tests/test_library_ui_integration.py` (stub), and `scripts/batch_solve.py`. You may also append to `scripts/check_pr.sh` to run the new tests. You may NOT modify any other file.

---

## Strict file ownership

**You own (create new):**
- `/Users/ashen/Desktop/poker_solver/tests/test_library.py`
- `/Users/ashen/Desktop/poker_solver/tests/test_library_cli.py`
- `/Users/ashen/Desktop/poker_solver/tests/test_library_ui_integration.py` (stub; `pytest.skip` at top)
- `/Users/ashen/Desktop/poker_solver/scripts/batch_solve.py`
- `/Users/ashen/Desktop/poker_solver/examples/tiny_csv.csv` (a minimal 2-row CSV fixture for the batch-solve dry-run test; spec §16 success criterion mentions it)

**You may modify (existing file, additive edit only):**
- `/Users/ashen/Desktop/poker_solver/scripts/check_pr.sh` — extend the test command to include `tests/test_library.py tests/test_library_cli.py`. No other changes. Spec §8.

**You must NOT touch:**
- `poker_solver/library.py`, `poker_solver/library_schema.sql` — Agent A
- `poker_solver/__init__.py`, `poker_solver/cli.py` — Agent A
- Any packaging script (`scripts/build_macos_dmg.sh`, `scripts/sign_and_notarize.py`, `scripts/entitlements.plist`, `assets/*`) — Agent B
- `pyproject.toml` — Agents A/B
- Any existing test file (`tests/test_*.py`) — these test PR 1-5 / PR 6+ and must remain unchanged
- The spec itself (`docs/pr11_prep/pr11_spec.md`) — read-only; if ambiguous, flag it in your report; the orchestrator (not you) updates the spec

**Critical:** you are writing the tests from the **spec alone**. Do NOT read `poker_solver/library.py` or `poker_solver/library_schema.sql` even after Agent A lands. The dividend of the fan-out pattern is that your tests independently encode the spec — if your tests fail against the impl, it's a real bug OR a real spec ambiguity, and the orchestrator resolves it. Reading the impl would defeat this dividend.

(Exception: if a test fails due to an obvious typo in YOUR test code, you may inspect the impl to figure out the typo. But you do not adjust tests to match impl behavior — only to fix your own bug.)

For `scripts/batch_solve.py`, you DO call into `poker_solver.library`'s public API (you must — your script needs to `from poker_solver.library import Library, SpotDescription`). You consume only the **public** surface documented in §"Public API you consume" below; you do NOT depend on internal helpers.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/pr11_spec.md`. Internalize ENTIRE spec, but especially §2 (library design — for spot_id determinism reasoning), §3 (public API — your test surface), §5 (entire batch-solve mode — your `scripts/batch_solve.py` surface), §9 (test plan — your test list), §11 (critical correctness items — your test assertions), §16 (success criteria).
2. **The PLAN (locked decisions):** `/Users/ashen/Desktop/poker_solver/PLAN.md`. "MacBook-only, no cloud spend", "no auto-population" (batch_solve is manual + idempotent).
3. **PR 5's `SolveResult` shape (what you serialize in tests):** `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/pr5_spec.md`. You build tiny synthetic `SolveResult`s inline (e.g., `SolveResult(average_strategy={"infoset1": [0.5, 0.5]}, game_value=0.0, exploitability_history=[0.1], iterations=10, ...)`) — keep them small and fast. Each test < 5s.
4. **PR 3's `HUNLConfig` (what `SpotDescription` wraps):** `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` lines 76-130. You build tiny `HUNLConfig`s inline. Spec §2.3 lists the canonicalization fields.
5. **Existing test patterns (style guide):** `/Users/ashen/Desktop/poker_solver/tests/test_hunl_core.py` — function-level tests, `pytest.approx` for floats, no test classes, parametrize only when meaningful. Mirror this style.
6. **CLI test pattern:** check if any existing tests use `subprocess.run`; if not, use the pattern in spec §9 final paragraph (CLI tests exercise subcommands end-to-end via `subprocess.run`).
7. **PR 11 spec §10:** the three-agent fan-out plan. You're Agent C. Read your section + the contract surfaces of Agents A/B so you understand what's being tested.

## Public API you consume (signatures from spec §3)

From `poker_solver.library` (Agent A's surface):

```python
class Library:
    @classmethod
    def open(cls, path: Path | None = None) -> "Library": ...
    def put(self, spot: SpotDescription, result: SolveResult, *, overwrite: bool = False) -> str: ...
    def get(self, spot: SpotDescription | str) -> SolveResult | None: ...
    def list(self, filter: LibraryFilter | None = None, *, limit: int = 1000, offset: int = 0) -> list[SpotMetadata]: ...
    def export(self, spot_id: str, path: Path) -> None: ...
    def import_(self, path: Path, *, overwrite: bool = False) -> str: ...
    def delete(self, spot_id: str) -> None: ...
    def stats(self) -> LibraryStats: ...
    def close(self) -> None: ...

@dataclass(frozen=True)
class SpotDescription:
    config: HUNLConfig
    initial_ranges: tuple | None = None
    label: str = ""
    def spot_id(self) -> str: ...

@dataclass(frozen=True)
class SpotMetadata: ...      # spec §3.2
@dataclass(frozen=True)
class LibraryFilter: ...     # spec §3.2
@dataclass(frozen=True)
class LibraryStats: ...      # spec §3.2

class LibraryError(Exception): ...
class LibraryDuplicateError(LibraryError): ...
class LibrarySchemaError(LibraryError): ...
```

CLI (Agent A's surface, exercised by `test_library_cli.py` via `subprocess.run`):
```
poker-solver library list [--street ...] [--json] [--library-path ...]
poker-solver library get <spot_id> [--json]
poker-solver library put <description.json> [--overwrite]
poker-solver library export <spot_id> <output_path>
poker-solver library import <input_path> [--overwrite]
poker-solver library delete <spot_id>
poker-solver library stats [--json]
poker-solver batch-solve --input <csv_path> [--workers N] [--max-memory-gb N] [--dry-run]
```

## Default decisions LOCKED (do not deviate)

These amendments to the PR 11 spec win where the spec text differs:

- **SQLite location:** `~/.poker_solver/library.db` with `POKER_SOLVER_LIBRARY_PATH` override. Spec §2.1, decision 13.2.
- **WAL mode + gzip compression** — assert these behaviors indirectly through the test plan (concurrent readers test 12, bit-exact roundtrip test 11). Don't poke at internals.
- **Spot ID = SHA-256 of canonicalized JSON.** Spec §2.3. Test 3 asserts determinism across reordered inputs; test 4 asserts difference on meaningful changes.
- **Strategy compression: gzip level 6** — bit-exact roundtrip required. Test 11 covers this.
- **`solver_version` mismatch = soft warning, not error.** Test that `Library.get` emits `UserWarning`. Don't test that it raises.
- **`schema_version` mismatch = hard error.** Test 15: manually insert `library_version=999` row; expect `LibrarySchemaError`. (This is the one test where you DO touch SQLite directly — to inject a bad row.)
- **Export format: JSON** (uncompressed). Spec decision 13.3. Test 10 roundtrips via export → delete → import_.
- **No new runtime deps.** Library is stdlib-only. Your tests use `pytest`, `tmp_path`, stdlib `subprocess`, `sqlite3` (for the schema-mismatch test 15 only). No `pytest-mock`, no `hypothesis`.
- **Each test < 5s.** Synthetic `SolveResult`s with tiny `average_strategy` dicts. No real solver invocation. Spec §9 opening paragraph.
- **CSV format for batch_solve:** match spec §5.1 exactly. Columns: `name,starting_street,initial_board,stacks_bb,bet_sizes,abstraction_path,iterations`.
- **`batch-solve --dry-run`** parses the CSV, reports what would be solved, and exits without solving. Spec §16 success criterion.
- **`scripts/batch_solve.py` is callable directly (`python scripts/batch_solve.py --input ...`) AND via the CLI subcommand (`poker-solver batch-solve --input ...`).** Spec §5.2 examples show both.

## Test plan (spec §9 — your work spec for `tests/test_library.py`)

The 15 unit tests. Each is a standalone `def test_*()` function. Use `tmp_path` for the DB. Build a tiny synthetic `SolveResult` inline:

```python
def _make_synthetic_result(**overrides):
    """Construct a SolveResult with sensible defaults; override per test."""
    from poker_solver.hunl_solver import SolveResult  # or wherever PR 5 placed it
    defaults = dict(
        average_strategy={"infoset1": [0.6, 0.4], "infoset2": [0.5, 0.5]},
        game_value=0.0,
        exploitability_history=[0.5, 0.3, 0.1],
        iterations=10,
        # other PR 5 fields per the SolveResult dataclass
    )
    defaults.update(overrides)
    return SolveResult(**defaults)


def _make_synthetic_spot(**overrides):
    """Construct a SpotDescription with sensible defaults; override per test."""
    from poker_solver.library import SpotDescription
    from poker_solver.hunl import HUNLConfig
    defaults = dict(
        config=HUNLConfig(
            starting_street=...,  # one of preflop/flop/turn/river
            board_cards=(...),
            stacks=(10000, 10000),  # int cents (100 BB)
            bet_size_fractions=(0.5, 1.0, 2.0),
            antes=0,
            rake=0,
        ),
        initial_ranges=None,
        label="test_spot",
    )
    defaults.update(overrides)
    return SpotDescription(**defaults)
```

(Note: PR 3's `HUNLConfig` constructor signature is your read-only reference. If you don't know the exact field names, read `poker_solver/hunl.py` lines 76-130 — that's the read-only spec for that side.)

### The 15 unit tests (spec §9)

1. **`test_library_open_creates_schema`** — fresh `tmp_path`; call `Library.open(path)`; query `sqlite_master` (you can open a parallel `sqlite3.connect` for read-only inspection); assert `spots` and `spots_meta` tables exist plus all 5 named indexes (`idx_spots_board`, `idx_spots_street`, `idx_spots_stack`, `idx_spots_created`, `idx_spots_solver`).

2. **`test_library_put_get_roundtrip`** — construct a synthetic `SpotDescription` and `SolveResult`; `library.put(spot, result)`; `library.get(spot)`; assert returned `SolveResult.average_strategy == result.average_strategy` (exact equality dict-of-list-of-float), and `game_value`, `exploitability_history`, `iterations` all match.

3. **`test_library_spot_id_deterministic`** — call `SpotDescription.spot_id()` (or `_compute_spot_id` if exposed) twice with semantically-equivalent inputs: same SpotDescription with bet-menu fractions in different order (one `(0.5, 1.0, 2.0)`, the other `(2.0, 1.0, 0.5)`), and board cards in different order (the canonical form sorts both). Assert identical IDs.

4. **`test_library_spot_id_differs_on_meaningful_change`** — change stack from 10000 to 10100 cents (1 BB difference): assert different IDs. Change board by one card: assert different IDs. Change `bet_size_fractions` by one entry: assert different IDs. Change `label` ONLY (a non-canonical field): the spec is ambiguous on whether label affects the spot_id — the spec §2.3 canonicalization rules don't mention label, so label-only changes should produce the SAME spot_id. Test this; if it fails, flag for spec amendment.

5. **`test_library_put_duplicate_raises_without_overwrite`** — `put` twice with same spot; second raises `LibraryDuplicateError`. Catch and assert.

6. **`test_library_put_duplicate_succeeds_with_overwrite`** — `put`, then `put(spot, modified_result, overwrite=True)`; assert the latest `result` is returned by `get`.

7. **`test_library_list_returns_metadata_only`** — populate 3 spots with distinct `label`/`street`/`board`; `list()` returns 3 `SpotMetadata` instances; assert each instance has no `average_strategy` attribute (or asserting `not hasattr(meta, "average_strategy")`). The point: `list` is fast; it does NOT decompress strategy blobs.

8. **`test_library_list_filter_by_street`** — populate one flop spot, one turn spot, one river spot; `list(LibraryFilter(street="river"))` returns 1; assert it's the river spot.

9. **`test_library_list_filter_combines_multiple`** — populate 4 spots varying by `street` AND `stack_bb`; filter by `street="flop"` AND `stack_bb_min=50, stack_bb_max=120`; assert correct subset.

10. **`test_library_export_import_roundtrip`** — `library.put(spot, result)`; `library.export(spot_id, tmp_path / "export.json")`; `library.delete(spot_id)`; assert `library.get(spot)` returns None; `library.import_(tmp_path / "export.json")`; assert `library.get(spot)` returns a `SolveResult` equivalent (bit-exact `average_strategy`) to the original.

11. **`test_library_compression_preserves_bit_exact_strategy`** — construct `SolveResult` with carefully-chosen float values: `[0.0, 1.0, 1e-15, 1.0 - 1e-15, 0.123456789012345, 0.987654321098765]`. `put` then `get`. Assert `np.array_equal(returned[k], original[k])` for every infoset (or, since we may not be using numpy, assert `returned[k] == original[k]` element-wise). The point: gzip + JSON roundtrip preserves IEEE-754 bits.

12. **`test_library_concurrent_readers_dont_corrupt`** — open two `Library` instances on the same DB file (one in each of two threads via `threading.Thread`); one thread writes 10 spots in a loop; another thread reads `list()` concurrently. Assert no exceptions, reads return consistent data (the read count grows monotonically). WAL mode is the load-bearing setting Agent A enables.

13. **`test_library_delete_removes_spot`** — `put`, `delete`, `get` returns None; `list` excludes it (`spot_id` not in returned `SpotMetadata.spot_id` values). `delete` on a non-existent id raises `KeyError`.

14. **`test_library_stats_counts_match`** — populate 5 spots across 3 streets (2 flop, 2 turn, 1 river); `stats()` returns `total_count=5`, `by_street == {"flop": 2, "turn": 2, "river": 1}`, `total_size_bytes > 0`, `oldest_created_at <= newest_created_at`.

15. **`test_library_schema_version_mismatch_errors`** — open a fresh DB to bootstrap the schema; close. Open a raw `sqlite3.connect`; insert `INSERT OR REPLACE INTO spots_meta (key, value) VALUES ('library_version', '999')`; close. Reopen via `Library.open`; expect `LibrarySchemaError` with a message containing "newer".

### The 5 CLI tests (spec §9 + spec §16 success criterion)

In `tests/test_library_cli.py`. Use `subprocess.run([sys.executable, "-m", "poker_solver.cli", ...], capture_output=True, text=True)` or just `["poker-solver", ...]` if the entry-point is installed.

1. **`test_cli_library_list_empty`** — fresh DB (set `POKER_SOLVER_LIBRARY_PATH` env to `tmp_path / "lib.db"`); CLI `library list` exits 0; stdout has 0 data rows (header-only or empty).

2. **`test_cli_library_put_and_get`** — write a JSON description file; CLI `library put description.json` exits 0; CLI `library get <spot_id>` returns the row (parse `--json` output).

3. **`test_cli_library_export_import`** — populate one spot via the library API (or via `put` CLI); CLI `library export <spot_id> /tmp/exp.json` exits 0; CLI `library delete <spot_id>` exits 0; CLI `library import /tmp/exp.json` exits 0; CLI `library get <spot_id>` returns the row.

4. **`test_cli_library_stats`** — fresh DB; CLI `library stats` exits 0; stdout mentions zero counts; populate 1 row; rerun stats; stdout now mentions 1.

5. **`test_cli_batch_solve_dry_run`** — write a minimal CSV at `examples/tiny_csv.csv` (or `tmp_path/tiny.csv`); CLI `batch-solve --input <path> --dry-run` exits 0; stdout shows parsed rows but no solve actually ran. Spec §16: "`poker-solver batch-solve --input examples/tiny_csv.csv --dry-run` parses without error."

### UI integration stub (`tests/test_library_ui_integration.py`)

A one-file placeholder. Spec §9 final paragraph: "gated on PR 10 landing a test harness. PR 11 ships the file as a stub with `pytest.skip('requires PR 10 UI harness')` at the top until then."

Contents:
```python
"""UI integration smoke tests for the library browser page.

Gated on PR 10 landing its NiceGUI test harness. PR 11 ships this file as a stub;
populate after PR 10's UI test infrastructure exists.

Planned tests:
- Library browser page mounts without error.
- Filter form updates the table on change.
- "Load" button populates the solve panel.
- "Export" button writes a JSON file.
- "Save to library" button appears after a solve completes.
"""

import pytest

pytest.skip("requires PR 10 UI harness", allow_module_level=True)
```

## `scripts/batch_solve.py` (spec §5)

### CSV input format (spec §5.1)

Columns:
- `name` — user-facing label, stored as `SpotMetadata.label`.
- `starting_street` — `flop`/`turn`/`river` (PR 5 is postflop-only). Reject `preflop` with a clear error.
- `initial_board` — space-or-comma separated cards (e.g., `"AsKc7d"` or `"As Kc 7d"`).
- `stacks_bb` — integer.
- `bet_sizes` — comma-separated pot fractions, e.g., `"0.33,0.75,2.0"`.
- `abstraction_path` — path to PR 4's `.npz` artifact, or empty for lossless (river-only).
- `iterations` — integer.

Example fixture (`examples/tiny_csv.csv`):
```csv
name,starting_street,initial_board,stacks_bb,bet_sizes,abstraction_path,iterations
"tiny_dry_flop",flop,"AsKc7d",100,"0.33,0.75,2.0",,10
"tiny_river_spot",river,"AsKc7dKh5s",10,"0.5,1.0",,10
```

### Behavior (spec §5.2)

CLI:
```
python scripts/batch_solve.py --input spots.csv \
    [--workers N] \
    [--max-memory-gb N] \
    [--dry-run] \
    [--library-path PATH]
```

Flow:
1. Parse CSV → `list[SpotDescription]` (use `csv.DictReader`; convert types; build `HUNLConfig` per row).
2. Open `Library`.
3. For each row:
   - Compute `spot_id` via `spot.spot_id()`.
   - If `library.get(spot_id)` returns non-None → print `[SKIP] <name> <spot_id>`. Continue.
   - If `--dry-run` → print `[DRY-RUN] <name> <spot_id> (would solve)`. Continue.
   - Otherwise: call `solve_hunl_postflop(...)` (PR 5). On success, `library.put(spot, result)`; print `[OK] <name> <spot_id> <time_sec>`.
   - On `MemoryError` (PR 5's clean OOM): print `[OOM] <name>` + memory report. Continue to next row.
   - On any other exception: print `[ERROR] <name>: <message>`. Continue.
4. Print final summary: total rows, OK count, SKIP count, OOM count, ERROR count.

### Parallelism (spec §5.3)

`--workers N` (default 1). When N > 1, spawn `multiprocessing.Process` workers each running `solve_hunl_postflop` on one spot. Workers communicate solved-spot blobs back via `multiprocessing.Queue`. Memory budget per worker = `--max-memory-gb / N` (passed to PR 5's `max_memory_gb`).

The Python DCFR is single-threaded inside a solve; `--workers > 1` parallelizes *across* spots, not within a spot.

For the dry-run test, you don't need to exercise the parallelism path — just the CSV parsing + skip/dry-run logic.

### Resumability (spec §5.4)

Re-running the same CSV after a crash is a no-op for already-saved spots (the idempotent `Library.get` skip). The user can `Ctrl-C` at any time and re-run safely. This is automatic from the put-rejects-duplicates contract; you just need to NOT swallow the SKIP case.

### Docstring (spec §5.5)

The "designed use case: solve overnight" example in spec §5.5 lives in the script's module docstring:
```python
"""Batch solve poker spots from a CSV file.

Designed use case: solve overnight.

    caffeinate -i python scripts/batch_solve.py --input common_spots.csv --workers 2 \\
      > batch.log 2>&1 &

`caffeinate` keeps the MacBook awake; the script chews through the CSV.
Re-running the same CSV after a crash is idempotent (already-solved spots skip).

CSV format:
    name,starting_street,initial_board,stacks_bb,bet_sizes,abstraction_path,iterations

See docs/pr11_prep/pr11_spec.md §5 for the canonical format.
"""
```

## Critical correctness items

### 1. Tests are self-contained (spec §9 opening)

Each test uses `tmp_path` for the DB; no shared state across tests. No `conftest.py` fixtures (keep tests trivial to read). No real solver invocation; build synthetic `SolveResult`s inline.

### 2. Tests assert against the public API only (spec §10 contract surface)

Internal helpers (`_compute_spot_id`, `_canonicalize_spot`, the SQLite connection wrapping) are Agent A's choice. Your tests assert against `Library.open`, `put`, `get`, `list`, `export`, `import_`, `delete`, `stats`, `close`. The one exception is test 15 (schema-mismatch), where you DO open a raw `sqlite3.connect` to inject a bad `library_version` row — that's intentional; you're emulating a tampered or out-of-version DB.

### 3. Spec ambiguity surfaces as test failures, not silent test tweaks (spec §10 edge-case allowance)

If a test fails because the spec was ambiguous, **the spec is the source of truth.** Agent A updates the implementation OR the user updates the spec. You do NOT silently tweak the test to match impl behavior.

Specific known ambiguity to flag if it bites:
- Test 4 (label-only change): the spec §2.3 doesn't mention `label` in the canonicalization rules, so a label-only change should produce the SAME spot_id. If the impl includes label in the canonical form, your test fails and you flag the spec/impl mismatch for orchestrator resolution.

### 4. `batch_solve.py` --dry-run actually doesn't solve (spec §16)

The dry-run path runs the CSV parse + the `library.get` skip-check, then prints `[DRY-RUN]` and continues. It does NOT call `solve_hunl_postflop`. Test 5 (CLI batch-solve dry-run) asserts that the test completes in <5s on a CSV that would otherwise require minutes of solving.

### 5. Idempotent batch_solve (spec §5.4, critical item 9)

Re-running the script on the same CSV after a successful run should print `[SKIP]` for every row and `[OK]` for none. Not a test in this spec (would require real solver), but the logic must be correct. Add a comment in the code referencing the contract.

### 6. CLI tests don't depend on installation path (spec §9 footnote)

Use `subprocess.run([sys.executable, "-m", "poker_solver.cli", ...])` rather than `["poker-solver", ...]` if the entry-point script may not be installed in the test environment. (Both should work, but `python -m` is more portable.)

## Quality bar

- **ruff clean:** `ruff check tests/test_library.py tests/test_library_cli.py tests/test_library_ui_integration.py scripts/batch_solve.py` reports zero issues.
- **black clean:** `black --check tests/test_library.py tests/test_library_cli.py tests/test_library_ui_integration.py scripts/batch_solve.py` reports no changes needed.
- **Tests pass against Agent A's impl:** `pytest tests/test_library.py tests/test_library_cli.py -v` shows all ~20 tests passing.
- **All existing tests still pass.** Run `pytest -x` after your work lands. Your work is purely additive; you should not break anything.
- **Coverage:** each public method on `Library` has at least one test (spec §10 Agent C deliverables).
- **Failure modes tested:** `LibraryDuplicateError` (test 5), `LibrarySchemaError` (test 15), concurrent access (test 12), `KeyError` on delete-not-found (test 13).
- **Code size budget: ~600 LOC** across all tests + `batch_solve.py` (~200 LOC). Stay within budget.

## Reference-first rule

Before any technical claim, citation, or formula, check the local references. Never extrapolate from training data when a local authoritative source exists.

- Spec §9 is your test plan; do not invent additional tests beyond what spec §9 lists. (You may add cosmetic helpers like `_make_synthetic_result`.)
- Spec §5 is your `batch_solve.py` spec; do not invent additional CLI flags.
- Spec §11 is your assertion list; your tests assert these properties.

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Lint + format
ruff check tests/test_library.py tests/test_library_cli.py tests/test_library_ui_integration.py scripts/batch_solve.py
black --check tests/test_library.py tests/test_library_cli.py tests/test_library_ui_integration.py scripts/batch_solve.py

# 2. Run new library tests
pytest tests/test_library.py -v 2>&1 | tail -40
pytest tests/test_library_cli.py -v 2>&1 | tail -20
pytest tests/test_library_ui_integration.py -v 2>&1 | tail -10  # should all skip

# 3. Smoke test batch_solve
python scripts/batch_solve.py --input examples/tiny_csv.csv --dry-run --library-path /tmp/test_batch.db 2>&1 | tail -20

# 4. Full test suite must still pass (your work is additive)
pytest -x 2>&1 | tail -20

# 5. Check the count
pytest tests/test_library.py --collect-only -q 2>&1 | grep "test_" | wc -l
# Should be 15.
pytest tests/test_library_cli.py --collect-only -q 2>&1 | grep "test_" | wc -l
# Should be 5.

# 6. CSV fixture exists
test -f examples/tiny_csv.csv && echo "tiny_csv.csv OK"
```

If any of the above fails, fix the issue before reporting done. If a test fails because of a spec/impl mismatch (not a typo in your code), **stop and flag it** — do not silently tweak the test.

## Report back format

When done, write a concise report (≤300 words) covering:

1. Files created/modified with line counts.
2. Test counts: total in `test_library.py`, total in `test_library_cli.py`, total skipped in UI stub.
3. Any spec ambiguity you surfaced (e.g., test 4's label-only change behavior). Describe the ambiguity precisely and propose a resolution.
4. Verification command output (paste tails).
5. Any open question you couldn't resolve from the spec or PLAN — flag for human review.
6. License attributions (none expected — pure Python tests + script).
