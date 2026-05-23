# PR 11 spec — Library mode + macOS packaging (codesign + notarize + .dmg)

## 1. Goal + non-goals

### 1.1 Goal

Ship two coupled deliverables that together turn the solver into a usable personal tool:

1. **Library mode** — a local on-disk SQLite database that persists solved spots indexed by a deterministic spot ID. Every successful `solve_hunl_postflop` call (PR 5) becomes a row that can be retrieved later without re-solving. The library is the **scriptability bridge** between PR 5's per-spot solver and PR 10's UI: solve once, browse forever. Modeled on PioSolver's text-interface scriptable workflow (`references/products/_COMPETITORS.md` "scriptable and integrable"), **not** GTO Wizard's cloud-hosted multi-million-spot library (out of reach per PLAN.md "MacBook-only, no cloud spend").

2. **macOS distribution** — a code-signed, notarized `.dmg` installer that drops a single `.app` into `/Applications`. The user (and anyone they trust) can install the solver without running `pip` or maturin. This is the deliverable that takes the project from "lives in `~/poker_solver/`" to "is an app on my Mac." Apple Developer enrollment is required for the *signed* path; an *unsigned* fallback is documented for dev-only use.

### 1.2 Non-goals (explicit)

- **No cloud-distributed library.** Per PLAN.md §1 "MacBook-only. 16 GB Apple Silicon. No cloud spend." The library is strictly on-disk under `~/.poker_solver/`. No sync, no upload, no remote fetch. GTOW-style precomputed cloud libraries are explicitly out of scope (PLAN.md §1 "Explicitly out of scope: GTOW-class large precomputed library").
- **No auto-population scheduler.** "Solve every common spot in the background" is a months-of-CPU exercise on a single MacBook and creates a UX where the app is always hot. We ship a **manual** `scripts/batch_solve.py` workflow: user feeds a CSV, the script solves and persists. No daemon, no cron.
- **No multi-user / multi-machine library.** Single-user, single-machine. Export/import is the manual share path.
- **No neural value warm-starts from cached spots.** That's a PR 13+ research item ("library-aware solving"). PR 11 stores results; PR 11 does not consume them for warm-starts.
- **No Windows / Linux installers.** macOS only in PR 11. Cross-platform packaging is deferred.
- **No universal2 (x86_64 + arm64) binary.** arm64-only matches PLAN.md's stated hardware. x86_64 cross-build is deferred.
- **No Apple Developer enrollment mandate.** The build script supports `--skip-signing --skip-notarization` for unsigned `.app` output. PR 11 is shippable without the $99/yr cost; only the *signed* distribution path requires enrollment.
- **No `pyproject.toml` runtime-dep additions.** Library uses only stdlib (`sqlite3`, `gzip`, `hashlib`, `json`). PyInstaller is added under an `[project.optional-dependencies] distribution` group; it is **not** installed by default.
- **No UI test framework introduction.** UI integration smoke tests are gated on PR 10 landing its own test harness; PR 11 contributes test stubs only.

## 2. Library mode design

### 2.1 On-disk format

The library is a single SQLite file at `~/.poker_solver/library.db` (XDG-style under the user's home directory). The path is overridable via environment variable `POKER_SOLVER_LIBRARY_PATH` or CLI flag `--library-path`. The parent directory is auto-created on first open.

SQLite was chosen over:
- **Flat JSON files** — no atomic concurrent reads, hard to query.
- **LMDB / RocksDB** — extra binary dependency; SQLite is stdlib.
- **Parquet** — read-heavy not write-heavy; we want incremental writes.
- **HDF5** — overkill, painful Python integration.

SQLite gives: atomic writes (WAL mode), free schema migrations, indexable columns, and zero new dependencies.

### 2.2 Schema

```sql
-- library_schema.sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS spots (
    id                  TEXT PRIMARY KEY,        -- sha256 of canonicalized spot JSON
    spot_json           BLOB NOT NULL,           -- original SpotDescription serialized
    strategy_gz         BLOB NOT NULL,           -- gzip-compressed avg_strategy JSON
    game_value          REAL NOT NULL,           -- from SolveResult.game_value
    exploitability      REAL NOT NULL,           -- exploitability_history[-1]
    iterations          INTEGER NOT NULL,        -- SolveResult.iterations
    abstraction_tier    TEXT NOT NULL,           -- e.g. "256/128/64" or "lossless"
    solver_version      TEXT NOT NULL,           -- semantic version of solver binary
    schema_version      INTEGER NOT NULL,        -- this row's schema version (currently 1)
    created_at          INTEGER NOT NULL,        -- unix epoch seconds
    -- Indexed projections (denormalized for query speed):
    board_signature     TEXT NOT NULL,           -- canonical board string ("AsKc7d2hQh" or "")
    stack_bb            INTEGER NOT NULL,        -- starting stacks in BB
    bet_menu_hash       TEXT NOT NULL,           -- sha256 of bet_size_fractions tuple
    street              TEXT NOT NULL            -- "preflop"|"flop"|"turn"|"river"
);

CREATE INDEX IF NOT EXISTS idx_spots_board     ON spots(board_signature);
CREATE INDEX IF NOT EXISTS idx_spots_street    ON spots(street);
CREATE INDEX IF NOT EXISTS idx_spots_stack     ON spots(stack_bb);
CREATE INDEX IF NOT EXISTS idx_spots_created   ON spots(created_at);
CREATE INDEX IF NOT EXISTS idx_spots_solver    ON spots(solver_version);

CREATE TABLE IF NOT EXISTS spots_meta (
    key                 TEXT PRIMARY KEY,
    value               TEXT NOT NULL
);
-- spots_meta keys: "library_version" (1), "created_by" (solver_version), "created_at".
```

WAL mode (`PRAGMA journal_mode = WAL`) is the load-bearing concurrency setting: multiple readers can read while one writer writes, which is the exact pattern the UI library browser needs (display table while batch_solve continues to insert).

### 2.3 Spot ID

The **spot ID** is `sha256(canonicalized_spot_json).hexdigest()`. The canonicalizer is the load-bearing determinism guarantee. Canonicalization rules:

1. **Board cards sorted** ascending by `(rank, suit)` — same convention as PR 3's infoset key (`docs/pr3_prep/pr3_spec.md` §infoset key).
2. **Stack values normalized to integer cents** (`HUNLConfig` already uses int cents per PR 3 §Units).
3. **Bet-menu fractions** tuple is sorted ascending.
4. **Initial-ranges**, if present (PR 9 preflop), serialized as a sorted hand-list with each hand's canonical form (e.g. `AhKh` not `KhAh`).
5. **Antes and rake** included even when 0 — the schema fields are part of the identity, so a spot solved with `rake=0` is **not** the same as a hypothetical future re-solve with `rake>0`.
6. **Solver hyperparameters** (α/β/γ) **excluded** from the canonical form, because PLAN.md locks them at α=1.5, β=0, γ=2.0. If we ever expose them as per-solve knobs, they get added to the canonical form and we bump `schema_version`.
7. JSON serialization uses `json.dumps(..., sort_keys=True, separators=(",", ":"))` (no whitespace) for deterministic byte output.

Determinism guarantees:
- Same description, two different machines → same ID.
- Description with reordered fields → same ID (canonicalization sorts).
- Description with semantically meaningful difference (one card different, one BB stack difference) → different ID.

### 2.4 Compressed strategy storage

`SolveResult.average_strategy` is `dict[str, list[float]]` (infoset key → action probabilities). For a 256/128/64-abstracted flop spot at full 6-size menu, this dict has ~10⁵ entries averaging ~6 floats each = ~5 MB uncompressed JSON. gzip compresses well on repeated infoset-key prefixes and gives ~50–150 KB compressed.

Compression policy:
- Always gzip on write (`gzip.compress(json_bytes, compresslevel=6)`). Level 6 is the gzip default — good ratio, fast.
- Always gunzip on read.
- **Bit-exact roundtrip required** — the float values must compare `==` after roundtrip. Test in §9.

Per-spot size budget: typical postflop = 50–150 KB compressed, river-only subgames = 5–20 KB. At 1000 spots the library is ~100 MB; at 10000 spots ~1 GB. Documented in §12 risks.

### 2.5 solver_version field

Each row carries the solver version (read from `poker_solver.__version__`). On `Library.get`, if the cached spot's `solver_version` differs from the current solver, **warn but don't error** (the strategy is still mathematically valid; only the user can decide whether to trust a strategy solved by an older DCFR config). Hard errors are reserved for `schema_version` mismatches.

## 3. Library API (`poker_solver/library.py`)

### 3.1 Public surface

```python
class Library:
    """Local on-disk cache of solved poker spots."""

    @classmethod
    def open(cls, path: Path | None = None) -> "Library":
        """Open (creating if missing) the SQLite database.

        Args:
            path: filesystem path to the DB file. Defaults to
                ~/.poker_solver/library.db or $POKER_SOLVER_LIBRARY_PATH.

        Returns:
            A connected Library instance. Use as a context manager.
        """

    def put(self, spot: SpotDescription, result: SolveResult, *,
            overwrite: bool = False) -> str:
        """Persist a solved spot. Returns the spot_id.

        Raises:
            LibraryDuplicateError: if spot_id already exists and overwrite=False.
        """

    def get(self, spot: SpotDescription | str) -> SolveResult | None:
        """Retrieve a spot by description (re-computes id) or by raw id.

        Returns None if not found. Emits a UserWarning if solver_version mismatches.
        """

    def list(self, filter: LibraryFilter | None = None,
             *, limit: int = 1000, offset: int = 0) -> list[SpotMetadata]:
        """List spots matching filter. Returns lightweight metadata; not strategies."""

    def export(self, spot_id: str, path: Path) -> None:
        """Write a portable single-spot JSON file (uncompressed) to `path`."""

    def import_(self, path: Path, *, overwrite: bool = False) -> str:
        """Import a JSON file produced by export(). Returns the spot_id."""

    def delete(self, spot_id: str) -> None:
        """Delete a spot. Raises KeyError if not found."""

    def stats(self) -> LibraryStats:
        """Aggregate counts, sizes, and per-street breakdown."""

    def close(self) -> None:
        """Close the underlying SQLite connection."""
```

### 3.2 Supporting dataclasses

```python
@dataclass(frozen=True)
class SpotDescription:
    """Identity of a solvable spot. Wraps HUNLConfig + range info."""
    config: HUNLConfig                       # from PR 3
    initial_ranges: tuple[Hand, ...] | None  # None for hole-cards-already-dealt
    label: str = ""                          # optional user-friendly tag

    def spot_id(self) -> str:
        """Compute the deterministic SHA-256 spot ID."""
        return _compute_spot_id(self)

@dataclass(frozen=True)
class SpotMetadata:
    """Lightweight row projection; no strategy blob."""
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
    created_at: int   # unix epoch

@dataclass(frozen=True)
class LibraryFilter:
    """Filter spec for Library.list. All fields optional (AND-combined)."""
    board_pattern: str | None = None      # regex on board_signature
    street: str | None = None             # exact match
    stack_bb_min: int | None = None
    stack_bb_max: int | None = None
    solver_version: str | None = None
    created_after: int | None = None      # unix epoch
    label_pattern: str | None = None      # regex on label

@dataclass(frozen=True)
class LibraryStats:
    total_count: int
    total_size_bytes: int
    by_street: dict[str, int]              # "flop": 42, ...
    by_solver_version: dict[str, int]
    oldest_created_at: int | None
    newest_created_at: int | None

class LibraryError(Exception): ...
class LibraryDuplicateError(LibraryError): ...
class LibrarySchemaError(LibraryError): ...
```

### 3.3 Concurrency

- Single `Library` instance per process. Internal `threading.Lock` around writes.
- SQLite WAL mode handles concurrent readers across processes.
- The UI accesses the library on the main thread but offloads expensive `get` calls (gzip + JSON parse) to `asyncio.to_thread`.

## 4. UI integration (extends PR 10)

PR 10 will land a NiceGUI scaffold under `ui/` with page-based routing, a range matrix component, board input, and a decision-tree browser. PR 11 adds **two** UI surfaces:

### 4.1 Library browser page (`ui/views/library_browser.py`)

A new page accessible from the PR 10 nav bar. Layout:

- Top: filter form (street dropdown, stack-range slider, board-regex input, free-text label search).
- Middle: table of `SpotMetadata`. Columns: label, street, board, stacks, value, exploitability, iters, abstraction, created_at. Sortable.
- Per-row actions: "Load" (sends `spot_id` to the main solve panel and triggers `Library.get`), "Export" (file dialog → `Library.export`), "Delete" (confirm dialog → `Library.delete`).
- Footer: `LibraryStats` summary (total spots, total size, breakdown).

Data flow:
- `Library.list()` called on page mount and on filter change.
- `Library.get()` called via `asyncio.to_thread` when row is loaded (avoids blocking the UI thread on large gzip blobs).

### 4.2 "Save to library" button on the spot input panel

PR 10's solver result panel gains a "Save to library" button. Click flow:

1. Take the current `SpotDescription` (built from the user's input).
2. Take the most-recent `SolveResult` (from the just-completed solve).
3. Call `Library.put(spot, result, overwrite=False)`.
4. On success: toast "Saved as `<spot_id_prefix>`".
5. On `LibraryDuplicateError`: dialog asks "Overwrite?" → re-call with `overwrite=True`.

If no solve has run yet, the button is disabled.

### 4.3 Solve-and-save workflow

The user-facing flow is:

1. Configure spot in PR 10's input panel.
2. Click "Solve" → solver runs.
3. Result panel populates with strategy, exploitability, memory report (PR 5).
4. User clicks "Save to library" (manual) OR clicks "Discard."

**No auto-save.** Per PLAN.md "no auto-population." The user is in control of what enters the library.

### 4.4 Range-matrix preview in the library row

If PR 10 exposes a public range-matrix component, the library browser uses it to show a 13×13 mini-heatmap in each row. If not, a text summary suffices (e.g. "value=0.42, exp=0.08 BB"). The spec does NOT depend on a specific PR 10 component API — the library browser ships with a text-summary fallback, and the range matrix is a PR 11.5 polish item if PR 10's interface is unstable.

### 4.5 Avoiding UI freezes

`Library.get` is the slow path (gunzip + JSON parse of up to 150 KB). All `get` calls from the UI route through `asyncio.to_thread(library.get, spot_id)`. NiceGUI's event loop stays responsive.

## 5. Batch-solve mode (`scripts/batch_solve.py`)

### 5.1 CSV input format

```csv
name,starting_street,initial_board,stacks_bb,bet_sizes,abstraction_path,iterations
"dry_aces_flop_3size",flop,"AsKc7d",100,"0.33,0.75,2.0",~/abstractions/256_128_64.npz,10000
"monotone_low_flop",flop,"8h7h6h",100,"0.33,0.75,1.0,2.0",~/abstractions/256_128_64.npz,10000
"river_dry_subgame",river,"AsKc7dKh5s",10,"0.33,0.75,1.0,1.5,2.0",,500
```

Columns:
- `name` — user-facing label, stored as `SpotMetadata.label`.
- `starting_street` — `flop`/`turn`/`river` (PR 5 is postflop-only).
- `initial_board` — space-or-comma separated cards.
- `stacks_bb` — integer.
- `bet_sizes` — comma-separated pot fractions; restricts the PR 3 menu.
- `abstraction_path` — path to PR 4's `.npz` artifact, or empty for lossless (river-only).
- `iterations` — integer.

### 5.2 Behavior

```bash
poker-solver batch-solve --input spots.csv \
                         --workers 1 \
                         --max-memory-gb 14 \
                         --dry-run
```

- Parse CSV → `list[SpotDescription]`.
- For each row: compute `spot_id`. If `Library.get(spot_id)` returns non-None, **skip** (idempotent). Print `[SKIP] <name> <spot_id>`.
- Otherwise solve via `solve_hunl_postflop(...)`. On success: `Library.put(...)`. Print `[OK] <name> <spot_id> <time_sec>`.
- On `MemoryError` (PR 5's clean OOM): print `[OOM] <name>` + partial memory report; continue to next row.
- On any other exception: print `[ERROR] <name>: <message>`; continue.

### 5.3 Parallelism

`--workers N` (default 1). When N>1, spawns `multiprocessing.Process` workers each running `solve_hunl_postflop` on one spot. Workers communicate solved-spot blobs back via `multiprocessing.Queue`. Memory budget per worker = `--max-memory-gb / N` (passed through to PR 5's `max_memory_gb`).

The Python DCFR is single-threaded inside a solve; `--workers > 1` parallelizes *across* spots, not within a spot.

### 5.4 Resumability

Re-running the same CSV after a crash is a no-op for already-saved spots (the idempotent `Library.get` skip). The user can `Ctrl-C` at any time and re-run safely.

### 5.5 Designed use case: "solve overnight"

```bash
caffeinate -i python scripts/batch_solve.py --input common_spots.csv --workers 2 \
  > batch.log 2>&1 &
```

`caffeinate` keeps the MacBook awake; the script chews through the CSV. Documented in `scripts/batch_solve.py`'s docstring.

## 6. macOS packaging

### 6.1 Tool choice: PyInstaller

Three candidates, chosen: **PyInstaller** (>=6.0).

- **PyInstaller** — most mature for mixed Python + C-ext / Rust-ext bundling. Used by production projects (FreeCAD, etc.). `--add-binary` supports the maturin-built `.so`. Single-tool pipeline. Picked.
- **Briefcase** (BeeWare) — newer, smaller ecosystem, NiceGUI support is less battle-tested. Couples to BeeWare's app framework. Rejected.
- **Nuitka** — compiles Python to C. Faster runtime but makes the maturin-built extension loading path harder to debug. Higher risk for v1. Rejected.

### 6.2 Bundle contents

The `.app` contains:
1. Python interpreter (CPython 3.13).
2. All Python dependencies: NumPy, NiceGUI + uvicorn + starlette, psutil, etc.
3. Maturin-built Rust extension `poker_solver/_rust.cpython-313-darwin.so`.
4. `poker_solver/charts/` (PR 3.5 push/fold charts).
5. `ui/` (NiceGUI page modules).
6. Application icon at `Contents/Resources/poker_solver.icns`.
7. `Info.plist` with bundle identifier `com.poker_solver.app`.

### 6.3 PyInstaller invocation

```bash
pyinstaller \
    --windowed \
    --onedir \
    --name "Poker Solver" \
    --osx-bundle-identifier "com.poker_solver.app" \
    --icon assets/poker_solver.icns \
    --add-binary "poker_solver/_rust.cpython-313-darwin.so:poker_solver" \
    --add-data "poker_solver/charts:poker_solver/charts" \
    --add-data "ui:ui" \
    --hidden-import "nicegui.elements" \
    --hidden-import "nicegui.functions" \
    --exclude-module "unittest" \
    --exclude-module "idlelib" \
    --exclude-module "turtle" \
    --exclude-module "tkinter" \
    --noconfirm \
    ui/main.py
```

Key flags justified:

- `--windowed`: no terminal on launch (per PyInstaller docs, the flag that creates a `.app` bundle on macOS).
- `--onedir`: PyInstaller docs explicitly recommend this over `--onefile` for `.app` bundles. `--onefile` "requires unpacking on each run" and breaks code-signing of inner files.
- `--add-binary`: PyInstaller does **not** auto-discover dynamic extensions loaded via PyO3's `import poker_solver._rust`. Explicit `--add-binary` is the load-bearing flag. The destination path `:poker_solver` maps the file into the bundled `poker_solver/` package.
- `--hidden-import`: NiceGUI does lazy imports; PyInstaller's static analysis misses them. Concrete list assembled empirically (initial guesses above; iterated based on runtime errors during dry-run testing).
- `--exclude-module`: trims unused stdlib to keep DMG size down (see §12 risk 3).

### 6.4 Code signing

**Requires Apple Developer ID Application certificate** ($99/yr Apple Developer Program enrollment).

```bash
codesign --deep --force \
         --options runtime \
         --entitlements scripts/entitlements.plist \
         --sign "Developer ID Application: NAME (TEAMID)" \
         "dist/Poker Solver.app"
```

Flags:
- `--deep` walks the bundle and signs every binary (PyInstaller's `Frameworks/` contains many `.dylib` and `.so` files).
- `--force` re-signs even if already signed.
- `--options runtime` enables Hardened Runtime (required for notarization).
- `--entitlements` points to the entitlements plist.

`scripts/entitlements.plist` (committed):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.cs.allow-jit</key><true/>
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key><true/>
    <key>com.apple.security.cs.disable-library-validation</key><true/>
</dict>
</plist>
```

Entitlements justified:
- `allow-jit` — NumPy and the Python interpreter use JIT-like memory patterns. Safe default per Apple docs.
- `allow-unsigned-executable-memory` — required for the Python interpreter on modern macOS.
- `disable-library-validation` — required because PyInstaller bundles dylibs not signed by us (Python interpreter + NumPy + maturin `_rust.so` all come from PyPI/maturin with different signing chains).

**Inside-out signing**: every `.dylib` and `.so` inside the bundle must be signed *before* the outer `.app`. `codesign --deep` claims to walk recursively but is unreliable on PyInstaller bundles. `scripts/sign_and_notarize.py` does an explicit `find Contents -name "*.dylib" -o -name "*.so"` walk, signing each binary individually with the same Developer ID, then signs the outer `.app`.

### 6.5 Notarization

Per Apple documentation (https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution): macOS 10.15 Catalina and later require notarization for downloaded apps to launch without Gatekeeper friction.

```bash
ditto -c -k --keepParent "dist/Poker Solver.app" "Poker Solver.zip"

xcrun notarytool submit "Poker Solver.zip" \
    --apple-id "$APPLE_ID" \
    --team-id "$TEAM_ID" \
    --password "$APP_SPECIFIC_PASSWORD" \
    --wait
```

- `--wait` blocks until Apple's notarization service completes review (typically minutes; can be hours under load).
- `$APP_SPECIFIC_PASSWORD` is generated at appleid.apple.com (user-provided, not committed).
- On success: `xcrun stapler staple "dist/Poker Solver.app"` embeds the notarization ticket so the `.app` validates offline.
- On failure: `notarytool log <submission-id>` returns JSON pointing at the problem binaries. The script captures this to `dist/notarization_failure.log` for debugging.

### 6.6 DMG creation

```bash
brew install create-dmg  # one-time setup

create-dmg \
    --volname "Poker Solver" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 100 \
    --icon "Poker Solver.app" 175 190 \
    --hide-extension "Poker Solver.app" \
    --app-drop-link 425 190 \
    "Poker-Solver-${VERSION}-arm64.dmg" \
    "dist/Poker Solver.app"
```

The Homebrew formula `create-dmg/create-dmg` is preferred over the sindresorhus npm package because it avoids introducing a Node toolchain dependency. Both produce equivalent output.

The DMG itself is also signed and notarized:
```bash
codesign --sign "Developer ID Application: ..." "Poker-Solver-${VERSION}-arm64.dmg"
xcrun notarytool submit "Poker-Solver-${VERSION}-arm64.dmg" ... --wait
xcrun stapler staple "Poker-Solver-${VERSION}-arm64.dmg"
```

Final artifact: `dist/Poker-Solver-<version>-arm64.dmg`. Drag-to-Applications install.

### 6.7 Unsigned fallback

For developers without Apple Developer enrollment:

```bash
./scripts/build_macos_dmg.sh --skip-signing --skip-notarization
```

Output is an unsigned `.app` + unsigned `.dmg`. To run:
1. Right-click → "Open" (bypasses Gatekeeper once per user).
2. Or: `xattr -d com.apple.quarantine "dist/Poker Solver.app"` to permanently mark it as trusted on this machine.

Documented in the script's `--help` output and the README.

## 7. Files to create

- **`poker_solver/library.py`** (~450 LOC) — `Library` class, `SpotDescription`, `SpotMetadata`, `LibraryFilter`, `LibraryStats`, `LibraryError` hierarchy, `_canonicalize_spot(spot) -> bytes`, `_compute_spot_id(spot) -> str`. Pure Python + stdlib + NumPy (for the strategy serialization). `mypy --strict` clean.
- **`poker_solver/library_schema.sql`** — DDL as in §2.2. Loaded by `Library.open()` via `connection.executescript(...)`.
- **`ui/views/library_browser.py`** (~250 LOC) — NiceGUI page module. Imports from `poker_solver.library`. Page registration follows whatever convention PR 10 establishes (function `register(app)` returning the route, or class-based registration — adapter logic in the file's top docstring).
- **`scripts/batch_solve.py`** (~200 LOC) — CSV parser, solve loop, optional multiprocessing pool. Standalone — runnable as `python scripts/batch_solve.py` or via the CLI subcommand.
- **`scripts/build_macos_dmg.sh`** (~150 LOC) — Bash orchestrator. Steps: clean → PyInstaller → smoke-test (run the `.app` binary, assert `from poker_solver import _rust` succeeds) → codesign → notarize → staple → DMG → codesign DMG → notarize DMG → staple DMG. Supports `--skip-signing --skip-notarization`.
- **`scripts/sign_and_notarize.py`** (~200 LOC) — Python helper. Functions: `sign_bundle(bundle_path, identity, entitlements)`, `notarize(zip_or_dmg, apple_id, team_id, password)`, `staple(target)`, `sign_inside_out(bundle_path, identity, entitlements)`. Called by `build_macos_dmg.sh` with explicit args; reusable from CI/future scripts.
- **`scripts/entitlements.plist`** — Hardened Runtime entitlements per §6.4.
- **`assets/poker_solver.icns`** — Application icon. Placeholder until user provides a custom icon. Generated from a `.png` via `iconutil` (documented in `assets/README.md`).
- **`tests/test_library.py`** — ~15 tests per §9.
- **`tests/test_library_ui_integration.py`** — placeholder; populated once PR 10's UI test harness exists.

## 8. Files to modify

- **`poker_solver/cli.py`** — add the `library` subcommand group:
  - `poker-solver library list [--street STR] [--board-pattern REGEX] [--limit N]`
  - `poker-solver library get <spot_id>`
  - `poker-solver library put <description.json>` (rare; mostly for testing)
  - `poker-solver library export <spot_id> <path>`
  - `poker-solver library import <path>`
  - `poker-solver library delete <spot_id>`
  - `poker-solver library stats`
  - Plus `poker-solver batch-solve --input <csv>` as a sibling top-level subcommand.
  - List output: tab-separated columns by default; `--json` flag for machine-readable.
- **`poker_solver/__init__.py`** — re-export `Library`, `SpotDescription`, `SpotMetadata`, `LibraryFilter`, `LibraryStats`, `LibraryError`, `LibraryDuplicateError`, `LibrarySchemaError`. Also expose `__version__` (used by `solver_version` field).
- **`pyproject.toml`**:
  - Add `[project.optional-dependencies] distribution = ["pyinstaller>=6.0"]`.
  - No new runtime dependencies (SQLite, gzip, hashlib, json are stdlib).
  - Set `__version__` consistently with `poker_solver/__init__.py`.
- **`scripts/check_pr.sh`** — extend to also run library tests as part of the full suite (no behavior change; just verifies new tests run).

Not modified:
- `poker_solver/dcfr.py`, `poker_solver/hunl.py`, `poker_solver/action_abstraction.py`, `poker_solver/solver.py`, `poker_solver/hunl_solver.py`, `poker_solver/profiler/*` — PR 11 is purely additive.
- All PR 3/4/5 tests remain unchanged.

## 9. Test plan (`tests/test_library.py`, ~15 tests)

Each test < 5s. Uses `tmp_path` for isolated DBs. Uses a tiny synthetic `SolveResult` (built inline) rather than running a real solver — keeps tests fast and the library logic decoupled from solve correctness.

1. `test_library_open_creates_schema` — fresh `tmp_path`; call `Library.open(path)`; query `sqlite_master`; assert `spots` and `spots_meta` tables and all five indexes exist.
2. `test_library_put_get_roundtrip` — construct a synthetic `SolveResult`, `library.put(spot, result)`, `library.get(spot)`; assert returned `SolveResult.average_strategy == result.average_strategy` and other fields equal.
3. `test_library_spot_id_deterministic` — call `_compute_spot_id` twice with semantically-equivalent inputs (bet-menu fractions in different order, board cards in different order); assert identical IDs.
4. `test_library_spot_id_differs_on_meaningful_change` — change stack from 100 BB to 101 BB; assert different IDs. Change board by one card; assert different IDs.
5. `test_library_put_duplicate_raises_without_overwrite` — `put` twice; second raises `LibraryDuplicateError`.
6. `test_library_put_duplicate_succeeds_with_overwrite` — `put` then `put(overwrite=True)` with modified result; assert latest result returned by `get`.
7. `test_library_list_returns_metadata_only` — populate 3 spots; `list()` returns 3 `SpotMetadata` instances; assert no `strategy` attribute (or it's None).
8. `test_library_list_filter_by_street` — populate flop, turn, river; `list(LibraryFilter(street="river"))` returns 1; assert it's the river spot.
9. `test_library_list_filter_combines_multiple` — populate 4 spots; filter by street AND stack range; assert correct subset.
10. `test_library_export_import_roundtrip` — `export(spot_id, tmp_file)`; `library.delete(spot_id)`; `library.import_(tmp_file)`; `library.get(spot_id)` returns equivalent `SolveResult`.
11. `test_library_compression_preserves_bit_exact_strategy` — construct `SolveResult` with carefully-chosen float values (including 0.0, 1.0, 1e-15, 1-1e-15); `put`/`get` roundtrip; assert every probability vector is `np.array_equal`.
12. `test_library_concurrent_readers_dont_corrupt` — open two `Library` instances on the same file; one writes, one reads concurrently from threads; assert no exceptions and reads return correct data.
13. `test_library_delete_removes_spot` — `put`, `delete`, `get` returns None; `list` doesn't include it.
14. `test_library_stats_counts_match` — `put` 5 spots across 3 streets; `stats()` returns `total_count=5`, `by_street` sums to 5.
15. `test_library_schema_version_mismatch_errors` — manually insert a `spots_meta` row with `library_version=999`; open; expect `LibrarySchemaError` ("library was created by a newer solver").

Plus two integration-flavored tests in a separate file `tests/test_library_cli.py` (~5 tests) exercising the CLI subcommands end-to-end via `subprocess.run`:
- `test_cli_library_list_empty` — fresh DB; CLI `library list` returns no rows.
- `test_cli_library_put_and_get` — CLI `library put` from a JSON; `library get` returns it.
- `test_cli_library_export_import` — CLI round-trip.
- `test_cli_library_stats` — CLI prints stats.
- `test_cli_batch_solve_dry_run` — CSV input; `--dry-run` parses and reports without solving.

UI-integration smoke tests (`tests/test_library_ui_integration.py`) are gated on PR 10 landing a test harness. PR 11 ships the file as a stub with `pytest.skip("requires PR 10 UI harness")` at the top until then.

## 10. Three-agent fan-out plan

Per the project's parallelization protocol (PLAN.md §5): three agents launched concurrently from this spec, integration at end.

### Agent A — Library module + SQLite schema + CLI integration

**Owns:**
- `poker_solver/library.py`
- `poker_solver/library_schema.sql`
- `poker_solver/__init__.py` (re-exports)
- `poker_solver/cli.py` (`library` and `batch-solve` subcommands)
- `scripts/batch_solve.py`

**Does NOT touch:**
- Any macOS packaging script.
- Any test file.
- Any UI file.
- PR 5's `hunl_solver.py` or `profiler/`.

**Surface contract:** §3 (public API) is the lock. Internal helpers (`_canonicalize_spot`, `_compute_spot_id`, the SQLite connection wrapping) are Agent A's choice; tests in §9 assert only against the public API.

**Deliverables:**
- Public API complete and `mypy --strict` clean.
- CLI subcommands end-to-end (smoke-tested manually against a tmp DB).
- `batch_solve.py` runs against a 2-row CSV with a tiny synthetic abstraction.

### Agent B — macOS packaging + signing pipeline

**Owns:**
- `scripts/build_macos_dmg.sh`
- `scripts/sign_and_notarize.py`
- `scripts/entitlements.plist`
- `pyproject.toml` (`distribution` optional-deps group)
- `assets/poker_solver.icns` (placeholder)
- `assets/README.md` (how to regenerate the icon)

**Does NOT touch:**
- Library code.
- Tests.
- CLI.

**Surface contract:** produces a notarizable `.app` and a stapled `.dmg`. End-to-end run documented in the script docstrings. Unsigned-fallback path exercised on CI (CI lacks Apple credentials so it always runs the unsigned path).

**Deliverables:**
- `./scripts/build_macos_dmg.sh --skip-signing --skip-notarization` produces a working unsigned `.app` + `.dmg` on the user's M-series MacBook.
- `./scripts/build_macos_dmg.sh` (with Apple creds in env vars) produces a notarized DMG.
- `sign_and_notarize.py` is callable from Python with explicit args for reuse.
- README section added documenting the build flow + Apple Developer enrollment.

### Agent C — Tests for library + UI integration smoke

**Owns:**
- `tests/test_library.py`
- `tests/test_library_cli.py`
- `tests/test_library_ui_integration.py` (stub; skipped until PR 10's harness exists)

**Does NOT touch:**
- Any non-test file.
- Library or script code.

**Surface contract:** §9 test plan is the lock. Tests written strictly from §3 (API) and §9 (test list). Agent C does NOT see Agent A's or Agent B's code while writing tests.

**Deliverables:**
- All tests in §9 pass against a Library implementation matching the §3 API.
- Coverage: each public method has at least one test.
- Failure modes tested: `LibraryDuplicateError`, `LibrarySchemaError`, concurrent access.

**Edge-case allowance:** if a test fails because the spec was ambiguous, the spec is the source of truth — Agent A updates the implementation or the user updates the spec; we do **not** silently tweak the test. (Same rule as PR 3/4/5.)

## 11. Critical correctness items

1. **Spot ID is deterministic across runs and machines.** Same `SpotDescription` → same SHA-256, every time. The canonicalization function (§2.3) is the load-bearing surface. Tested via §9 test 3.
2. **Spot ID changes on meaningful changes.** Changing stack, board, bet-menu, or starting-street produces a different ID. §9 test 4.
3. **Library doesn't corrupt under concurrent access.** WAL mode + write-mutex; tested with multi-threaded fixture in §9 test 12.
4. **Compression round-trip preserves bit-exact strategies.** gzip → gunzip → JSON parse → list[float] matches source exactly. §9 test 11.
5. **DMG is reproducible up to timestamps and signatures.** Same source + same env → same unsigned-PyInstaller payload bytes. Signed/notarized bytes differ on each run (Apple-side timestamps). Document the property explicitly in `scripts/build_macos_dmg.sh` docstring.
6. **Unsigned-fallback path is functional.** `--skip-signing --skip-notarization` produces a `.app` that opens after Gatekeeper right-click bypass. Tested manually on CI (CI has no Apple credentials).
7. **`solver_version` mismatch warns but doesn't error.** A user can still load older-version spots; they see a `UserWarning` mentioning the version.
8. **`schema_version` mismatch errors loudly.** Hard error path; the user must run a migration or rebuild.
9. **Idempotent batch solve.** Re-running the same CSV is a no-op for already-solved spots.
10. **No new runtime dependencies.** SQLite, gzip, hashlib, json are stdlib. Adding deps here would break the "no surprise pip-install" invariant from PR 5.
11. **Library file location respects env var.** `POKER_SOLVER_LIBRARY_PATH=/tmp/foo.db poker-solver library list` honors the override.
12. **Export/import is portable.** A spot exported on Machine A imports correctly on Machine B (same JSON, no machine-specific paths in the export).

## 12. Risks

### 12.1 PyInstaller may fail to bundle the Rust extension (highest risk)

`maturin` produces `poker_solver/_rust.cpython-313-darwin.so`. PyInstaller's static analysis finds Python imports via AST walking; it does **not** know that `from poker_solver import _rust` resolves to that `.so` because the import is wired by PyO3's `#[pymodule]` macro at C-API level.

**Symptoms:** the bundled `.app` launches, then immediately crashes on the first call into `_rust` (e.g. when `solver.py` checks if a Rust backend exists).

**Mitigation:**
1. Explicit `--add-binary` flag in the PyInstaller command (per docs §6.3).
2. **Smoke-test step** in `build_macos_dmg.sh`: after PyInstaller succeeds, run the bundled binary headlessly with a script that does `python -c "from poker_solver import _rust; print(_rust)"` and fails the build if the import errors. This catches the issue in CI rather than at user install time.
3. Document the failure mode in `scripts/sign_and_notarize.py`'s troubleshooting section.

### 12.2 Apple Developer enrollment is paid

$99/yr Apple Developer Program. Per PLAN.md "no cloud spend" — Apple Developer Program is **not** cloud compute spend; it's a per-developer ID. The spec does NOT require enrollment for PR 11 to ship; the unsigned-fallback path produces a working `.app`. The user decides whether to pay for distribution. Documented in §6.7 and §13 decision 1.

### 12.3 DMG size blow-up

Python + NumPy + NiceGUI + uvicorn + starlette + maturin extension easily totals 200+ MB. Target: <200 MB after `--exclude-module` trimming.

Empirical estimate (based on similar Python-app bundles):
- Python 3.13 interpreter: ~30 MB
- NumPy: ~40 MB
- NiceGUI + uvicorn + starlette: ~30 MB
- `_rust.so`: ~5 MB (small Rust extension)
- Other deps (psutil, etc.): ~10 MB
- Stdlib (after exclusions): ~50 MB
- **Total estimate: ~165 MB.** Within budget.

If exceeded, the user accepts: 200 MB DMG download is not a UX dealbreaker. Documented as a soft constraint.

### 12.4 SQLite library growth

100 KB/spot × 1000 spots = 100 MB. 100 KB/spot × 10000 spots = 1 GB. The `LibraryStats` API surfaces this; the UI shows the size; the user manages disk space manually. No automatic eviction policy (LRU caches over real data are a footgun). Documented in §13 decision 2.

### 12.5 Cross-version DCFR strategies invalidate silently

If the user upgrades the solver between solving and loading a spot, the cached strategy may have used different hyperparameters. The `solver_version` field on each spot, combined with the warning-on-mismatch in `Library.get`, handles this. Hard errors are reserved for `schema_version` mismatches; soft warnings cover hyperparam drift.

### 12.6 Xcode Command Line Tools required

`xcrun notarytool` requires Xcode Command Line Tools installed (`xcode-select --install`). `build_macos_dmg.sh` checks for `xcrun` presence and aborts with a clear error if missing.

### 12.7 NiceGUI bundle quirks

NiceGUI uses uvicorn + websocket transport. The bundled `.app` opens a localhost browser window after a ~5s spin-up. Documented as known UX. The PR 10 NiceGUI scaffold work will identify whether NiceGUI's `native=True` mode (PyWebView) gives a better UX; if so, switch in PR 11.5.

### 12.8 Apple notarization rejections

Common causes:
- Missing entitlements (the three in §6.4 cover the common cases).
- Unsigned dylibs inside `Frameworks/` (the inside-out signing walk addresses this).
- Non-Hardened-Runtime binaries (the `--options runtime` flag on every signature step addresses this).

`notarytool log` returns JSON pointing at the problem binary. The script captures this to `dist/notarization_failure.log` for debugging. Rejections are diagnostic, not fatal — fix the issue and re-submit.

### 12.9 `mypy --strict` regression risk

`SpotDescription` wraps `HUNLConfig` which already has many fields. Type annotations on `LibraryFilter` and the SQLite cursor return types need attention. Mitigation: `mypy --strict poker_solver/library.py` is a CI gate.

## 13. Open decisions for user (defaults locked)

Each entry locks a default; if the user prefers otherwise, redirect before launching A/B/C.

1. **Apple Developer enrollment.** Default: **optional.** The build script supports `--skip-signing --skip-notarization` for unsigned `.app` output. If the user wants a shareable DMG to send to others, they enroll ($99/yr). Override candidate: mandatory enrollment (would block PR 11 on a billing step). Rejected.
2. **Library file location.** Default: **`~/.poker_solver/library.db`** with `POKER_SOLVER_LIBRARY_PATH` env override. Override candidate: project-relative (`./library.db`). Rejected because the user works across multiple repo clones and would lose the library on every clone.
3. **Spot export format.** Default: **JSON** (uncompressed, human-inspectable, no new dep). Override candidates:
   - YAML — adds `pyyaml` dependency; more readable but harder to parse robustly.
   - Custom binary — smaller but opaque.
   - Compressed JSON (`.json.gz`) — saves space but loses inspectability.
4. **Auto-suggest library spots based on current input.** Default: **defer to PR 11.5.** Infrastructure exists (board signature index) but the UX is non-trivial. The library browser is searchable; auto-suggest is sugar.
5. **Schema migration policy.** Default: **explicit migration**. `Library.open()` reads `spots_meta.library_version`; if older, runs registered migrations from a `_migrations/` table in `library.py`; if newer, errors loudly. Override candidate: auto-rebuild from scratch (lossy). Rejected.
6. **Bundle architecture target.** Default: **arm64 only** (matches PLAN.md "MacBook-only, 16 GB Apple Silicon"). Override candidate: universal2 (~2× DMG size, adds CI complexity). Deferred to PR 11.5 if x86 Macs need to be supported.
7. **DMG window styling.** Default: **plain default DMG** (volume icon + Applications symlink). Override candidate: custom background image at `assets/dmg_background.png`. User can supply later.
8. **PyInstaller `--onedir` vs `--onefile`.** Default: **`--onedir`** (per PyInstaller docs; faster launch, code-signable). `--onefile` is rejected (per docs explicit recommendation).
9. **"Save to library" auto-save vs explicit.** Default: **explicit "Save" button** (matches PLAN.md "no auto-population"). Override candidate: auto-save on every solve. Rejected (would balloon the library).
10. **`create-dmg` Homebrew vs sindresorhus npm.** Default: **Homebrew formula (`brew install create-dmg`)** — keeps the toolchain in Homebrew. Override candidate: sindresorhus npm package (introduces Node dependency). Rejected.
11. **Library compression level.** Default: **gzip level 6** (gzip default; good ratio, fast). Override candidates: 9 (max ratio, slower), 1 (fast, larger). Documented as a tuning knob.
12. **CLI list output format.** Default: **tab-separated** (grep/awk-friendly). `--json` flag for machine-readable output. `--table` flag for human-readable rich-table output (if `rich` is installed; otherwise tab-separated).
13. **PR 10 dependency.** Default: **PR 11 starts when PR 10 lands its NiceGUI scaffold.** The library module (Agent A) and packaging (Agent B) are independent of PR 10 and can land first. The UI viewer (in Agent A's plan) is gated on PR 10's routing convention. Override candidate: ship PR 11 library + packaging without UI viewer, add UI in PR 11.5. Acceptable fallback.

## 14. Out-of-scope follow-ups

- **PR 11.5:** auto-suggest library spots based on UI input (board-signature similarity match).
- **PR 11.5:** universal2 (x86_64 + arm64) DMG.
- **PR 11.5:** library viewer's range-matrix preview (depends on PR 10 component being public).
- **PR 12+:** library-aware solver — if a similar spot exists, warm-start CFR from the cached strategy.
- **PR 12+:** multi-spot bundle export/import (zip of multiple `.json` files for sharing curated sets).
- **PR 12+:** Windows / Linux installers (separate spec).
- **PR 12+:** library-as-a-service (HTTP API over a local SQLite) for integration with external tools.
- **PR 12+:** automated DCFR-version upgrade migrator (when `solver_version` mismatches, optionally re-solve in the background).
- **PR 12+:** library sync via local filesystem (e.g. `~/Dropbox/poker_solver_library.db`) — strictly user-controlled, no built-in cloud.
- **PR 12+:** auto-tagging of saved spots based on board texture (dry/wet/monotone/paired).

## 15. Reference citations

For the macOS packaging pipeline (cited inline in §6 per "reference-first rule"):

- Apple Developer — Notarizing macOS software before distribution: https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution
  - Gatekeeper enforcement from macOS 10.15 Catalina onward.
  - Required: Developer ID Application certificate, Hardened Runtime.
- Apple Developer — Customizing the notarization workflow: https://developer.apple.com/documentation/security/customizing-the-notarization-workflow
  - `xcrun notarytool submit --wait` command syntax.
  - `xcrun stapler staple` for embedding the notarization ticket.
- PyInstaller — Using PyInstaller: https://pyinstaller.org/en/stable/usage.html
  - `--windowed` for `.app` bundle creation.
  - `--onedir` recommended over `--onefile` for code-signed `.app` bundles.
  - `--add-binary SOURCE:DEST` for bundling native dynamic libraries.
- `create-dmg` (sindresorhus, npm): https://github.com/sindresorhus/create-dmg
- `create-dmg` (Homebrew formula): https://github.com/create-dmg/create-dmg

For the library design (cited inline in §2–§5):

- PLAN.md §1 — "no cloud spend" constraint; "MacBook-only" hardware target; PR 11 row.
- `docs/pr5_prep/pr5_spec.md` — `SolveResult` / `HUNLSolveResult` shape (`average_strategy: dict[str, list[float]]`, `exploitability_history: list[float]`, `game_value: float`).
- `docs/pr3_prep/pr3_spec.md` — `HUNLConfig` schema; infoset key format (canonical hole/board ordering).
- `references/products/_COMPETITORS.md` — GTOW library UX (precomputed at 0.1–0.3% Nash Distance; massive but cloud-only); PioSolver scriptability and text-interface design; Monker's per-bucket reporting (anti-pattern for end-user UX — we go per-combo where possible).

For SQLite WAL mode:

- SQLite documentation — WAL: https://www.sqlite.org/wal.html
  - WAL allows reads concurrent with writes; the configuration line `PRAGMA journal_mode = WAL` is the load-bearing setting.

## 16. Success criteria

- All new tests pass (~20 tests across `test_library.py` and `test_library_cli.py`).
- All PR 1/2/3/4/5 tests still pass unchanged.
- `ruff check poker_solver tests scripts` clean.
- `ruff format --check` clean.
- `mypy --strict poker_solver/library.py` clean.
- `mypy poker_solver` overall: no new errors.
- `poker-solver library list` on a fresh machine succeeds (creates the DB, returns empty list).
- `poker-solver batch-solve --input examples/tiny_csv.csv --dry-run` parses without error.
- `./scripts/build_macos_dmg.sh --skip-signing --skip-notarization` produces a launchable unsigned `.app` (smoke-tested by running `Poker Solver.app/Contents/MacOS/Poker Solver` headlessly with a script that imports `poker_solver` and `poker_solver._rust`).
- (Optional, requires Apple credentials) `./scripts/build_macos_dmg.sh` end-to-end produces a notarized stapled DMG that installs and runs on a clean macOS user account.
- The audit agent (`general-purpose` with no PR-11 context) reviews against this spec and produces `docs/pr11_prep/audit_report.md` with must-fix / should-fix / nice-to-fix / looks-good sections.

## 17. Post-implementation audit

Per PLAN.md "Mandatory PR audit from PR 3 onward": after A+B+C land, a fresh `general-purpose` audit agent runs with no prior context and reviews:

- The full diff (Agent A's library module, Agent B's packaging scripts, Agent C's tests).
- Against this spec only.
- Output: `docs/pr11_prep/audit_report.md` with structured sections.
- User reads alongside `pr_report.md` before commit OK.

Focus areas the audit must touch:

- **Determinism of spot ID** — does `_compute_spot_id` produce identical output for semantically-equivalent inputs?
- **SQLite concurrency** — is the write-mutex correctly scoped? Are reads truly concurrent under WAL?
- **Compression correctness** — does the test actually exercise float values that would be sensitive to round-trip loss (e.g. denormals)?
- **PyInstaller bundling** — does the smoke-test step in `build_macos_dmg.sh` actually catch a missing `_rust.so` (audit asks Agent B to demonstrate this by intentionally omitting `--add-binary` and showing the failure)?
- **Signing inside-out** — does `sign_and_notarize.py`'s walk hit every binary? (Find all `.dylib` and `.so` files in a sample bundle, assert they all carry a signature.)
- **Unsigned-fallback path** — does `--skip-signing --skip-notarization` actually produce a launchable `.app`?
- **License hygiene** — no new AGPL/GPL dependencies; PyInstaller is GPL-with-exception (the exception covers bundled apps); audit confirms the exception applies here.
- **Library file safety** — does the code refuse to overwrite an existing library at a different schema version?
- **Reproducibility** — does the same source + same env produce the same unsigned PyInstaller payload bytes (modulo timestamps)?
- **CLI surface** — does each subcommand have a `--help` that's useful?
