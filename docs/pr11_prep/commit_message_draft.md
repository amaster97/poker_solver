PR 11: Library mode + macOS .dmg packaging (v1.0.0 — the v1 milestone)

Ships the two coupled deliverables that turn the solver into a usable
personal tool: (1) **Library mode** — a local SQLite-backed on-disk
database that persists solved spots indexed by a deterministic spot
ID, queryable from the CLI and from the PR 10 UI; and (2) **macOS
distribution** — a code-signed, notarized `.dmg` installer that drops
a single `.app` into `/Applications`. Three-agent fan-out (A: library
module + SQLite schema + CLI integration; B: macOS packaging +
signing pipeline; C: tests + batch_solve.py) plus a post-implementation
audit pass. PR 11 takes the project from "lives in `~/poker_solver/`"
to "is an app on my Mac" — the v1 milestone.

Bumps __version__ to 1.0.0 — the v1.0.0 milestone marker per the
PLAN.md §1 commitment ("v1 ships PR 11 with the library + DMG"). MAJOR
bump because: (a) PR 11 closes every v1 deliverable on the roadmap
(HUNL postflop + preflop in Python+Rust; PR 4 abstraction; PR 5
profiler; PR 9 blueprint+refinement; PR 10 UI; PR 11 library +
distribution); (b) the public API surface is now considered stable
under semver — the v0.x experimental disclaimer is removed from the
README; (c) on-disk artifact compatibility (`library.db` schema_version
= 1) is committed to, with explicit migration paths for v2. PATCH and
MINOR semantics resume from 1.0.0 onward. This commit bundles the
v1.0.0 release artifacts together with the implementation so the
merge tip is the v1 GA tag:
- poker_solver/__init__.py: __version__ "0.6.0" -> "1.0.0".
- pyproject.toml [project] version "0.6.0" -> "1.0.0"; new
  `[project.optional-dependencies] distribution = ["pyinstaller>=6.0"]`.
- CHANGELOG.md: new [1.0.0] - 2026-05-22 section above [0.6.0],
  populated with the PR 11 entry from [Unreleased] AND a v1 GA
  summary block listing every PR shipped (3, 3.5, 4, 5, 6, 7, 8, 9,
  10a, 10b, 11). v1 GA tag note: "Library + macOS .dmg
  distribution; v0.x experimental disclaimer lifted; semver applies
  from 1.0.0 onward."
- README.md: "Current version: 0.6.0" -> "Current version: 1.0.0";
  v1 GA badge added; new "Installation" section with the
  drag-to-Applications DMG flow; "Roadmap" section reduced to
  v1.5/v2 follow-ups (the v1 features all ship).

Scope (spec §1, §2, §3, §4, §5, §6, §7, §8, §9, §11):

**Library mode:**
- Single SQLite file at `~/.poker_solver/library.db` (XDG-style),
  overridable via `POKER_SOLVER_LIBRARY_PATH` env var or
  `--library-path` CLI flag. Parent dir auto-created.
- SQLite WAL mode (`PRAGMA journal_mode = WAL`) — multiple readers
  while one writer writes; required for the UI library browser +
  batch_solve concurrency.
- Schema: `spots` table with `id` (sha256 of canonicalized spot
  JSON), `spot_json` (BLOB, original SpotDescription), `strategy_gz`
  (gzip-compressed avg_strategy JSON), `game_value`, `exploitability`,
  `iterations`, `abstraction_tier`, `solver_version`, `schema_version`,
  `created_at`, plus indexed denormalized projections
  (`board_signature`, `stack_bb`, `bet_menu_hash`, `street`). Indexes
  on `board_signature`, `street`, `stack_bb`, `created_at`,
  `solver_version`. Plus `spots_meta` key-value table for
  `library_version` / `created_by` / `created_at`.
- Deterministic spot ID: `sha256(canonicalized_spot_json).hexdigest()`.
  Canonicalization: board cards sorted by `(rank, suit)`; stack values
  in integer cents; bet-menu fractions sorted ascending; initial-ranges
  serialized as sorted hand-list with canonical hand form (`AhKh` not
  `KhAh`); antes + rake included even when 0; solver hyperparameters
  EXCLUDED (locked at α=1.5, β=0, γ=2.0 per PLAN.md — included only
  if exposed as per-solve knobs in a future version, bumping
  `schema_version`); JSON via `json.dumps(..., sort_keys=True,
  separators=(",", ":"))` for byte-deterministic output.
- Compressed strategy storage: `gzip.compress(json_bytes,
  compresslevel=6)` on write; `gunzip` on read; **bit-exact roundtrip
  required** (`np.array_equal`, NOT `np.allclose` — silent precision
  loss is a strategy-display corruption vector). Per-spot size:
  50-150 KB compressed for postflop, 5-20 KB for river-only subgames.
- `solver_version` mismatch on `Library.get` → `UserWarning` (soft);
  `schema_version` mismatch → `LibrarySchemaError` (hard).

**Library API (`poker_solver/library.py`):**
- `Library.open(path)` — context-managed connection.
- `Library.put(spot, result, *, overwrite=False)` → `spot_id`. Raises
  `LibraryDuplicateError` if `spot_id` already exists and
  `overwrite=False`.
- `Library.get(spot | spot_id)` → `SolveResult | None`. Emits
  `UserWarning` on `solver_version` mismatch.
- `Library.list(filter, *, limit=1000, offset=0)` →
  `list[SpotMetadata]`. Lightweight projection; no strategy blob.
- `Library.export(spot_id, path)` — writes portable JSON
  (uncompressed, human-inspectable).
- `Library.import_(path, *, overwrite=False)` → `spot_id`.
- `Library.delete(spot_id)` — raises `KeyError` if not found.
- `Library.stats()` → `LibraryStats` (total count, total size,
  per-street + per-solver-version breakdown).
- `Library.close()`.
- Internal `threading.Lock` around writes; WAL handles concurrent
  reads across processes.

**Batch-solve (`scripts/batch_solve.py`):**
- CSV input: `name,starting_street,initial_board,stacks_bb,bet_sizes,
  abstraction_path,iterations`.
- For each row: compute `spot_id`; `Library.get` → skip if cached
  (idempotent — re-running the same CSV after a crash is a no-op
  for already-saved spots). Otherwise solve via
  `solve_hunl_postflop` (or `solve_hunl_preflop` post-PR 9). On
  success: `Library.put`.
- Print `[SKIP] / [OK] / [OOM] / [ERROR]` lines per row.
- `--workers N` (default 1): `multiprocessing.Process` per worker;
  memory budget per worker = `--max-memory-gb / N`.
- `--dry-run` parses CSV without solving (validates schema +
  reports).
- Designed for `caffeinate -i python scripts/batch_solve.py
  --input common_spots.csv --workers 2 > batch.log 2>&1 &`.

**macOS packaging:**
- PyInstaller 6.0+ chosen over Briefcase (newer ecosystem, less
  battle-tested with NiceGUI) and Nuitka (extension loading harder
  to debug). `[project.optional-dependencies] distribution =
  ["pyinstaller>=6.0"]` — NOT in base deps.
- `scripts/build_macos_dmg.sh` (~150 LOC): clean → PyInstaller →
  in-bundle smoke test → codesign → notarize → staple → DMG →
  codesign DMG → notarize DMG → staple DMG. Supports
  `--skip-signing --skip-notarization` for unsigned-fallback path
  (no Apple Developer enrollment required).
- PyInstaller invocation: `--windowed --onedir --name "Poker Solver"
  --osx-bundle-identifier "com.poker_solver.app"
  --icon assets/poker_solver.icns
  --add-binary "poker_solver/_rust.cpython-313-darwin.so:poker_solver"
  --add-data "poker_solver/charts:poker_solver/charts"
  --add-data "ui:ui"
  --hidden-import "nicegui.elements" --hidden-import "nicegui.functions"
  --exclude-module "unittest" / "idlelib" / "turtle" / "tkinter"
  --noconfirm ui/main.py`. `--onedir` (NOT `--onefile` — per
  PyInstaller docs, `--onefile` "requires unpacking on each run"
  and breaks code-signing of inner files).
- **Load-bearing `--add-binary` flag** for the maturin-built Rust
  extension. PyInstaller does NOT auto-discover dynamic extensions
  loaded via PyO3's `#[pymodule]` macro. Without this flag the
  bundled `.app` launches then crashes on the first call into Rust
  — worst-case user-experience failure mode (install succeeds, app
  appears to start, dies on first solve).
- **In-bundle smoke test** in `build_macos_dmg.sh`: after PyInstaller
  succeeds, runs the bundled python with `from poker_solver import
  _rust; print(_rust)` and fails the build on `ImportError`. Catches
  the `--add-binary` failure mode in CI rather than at user install
  time.
- Code signing: `codesign --deep --force --options runtime
  --entitlements scripts/entitlements.plist --sign "$DEVELOPER_ID_IDENTITY"
  "dist/Poker Solver.app"`. Requires `Developer ID Application`
  certificate ($99/yr Apple Developer Program enrollment — optional
  per §13 D1 unsigned-fallback default).
- Entitlements (`scripts/entitlements.plist`): `allow-jit` (NumPy +
  Python interpreter JIT-like memory), `allow-unsigned-executable-memory`
  (Python interpreter on modern macOS), `disable-library-validation`
  (PyInstaller bundles dylibs from PyPI + maturin with different
  signing chains). Hardened Runtime required for notarization.
- **Inside-out signing walk**: `scripts/sign_and_notarize.py` does
  an explicit `find Contents -name "*.dylib" -o -name "*.so"`,
  signs each inner binary with the Developer ID + Hardened Runtime,
  then signs the outer `.app`. `codesign --deep` is documented-
  unreliable on PyInstaller bundles.
- Notarization: `xcrun notarytool submit "Poker Solver.zip"
  --apple-id "$APPLE_ID" --team-id "$TEAM_ID" --password
  "$APP_SPECIFIC_PASSWORD" --wait`. On success:
  `xcrun stapler staple "dist/Poker Solver.app"` embeds the
  notarization ticket for offline validation.
- DMG: `create-dmg` (Homebrew formula, NOT sindresorhus npm —
  avoids Node toolchain dep) → arm64-only output
  `Poker-Solver-1.0.0-arm64.dmg`. DMG itself is signed + notarized
  + stapled.
- Bundle architecture: arm64-only (matches PLAN.md "MacBook-only,
  16 GB Apple Silicon"). Universal2 (x86_64 + arm64) deferred to
  PR 11.5 per §13 D6.

**UI integration (extends PR 10):**
- `ui/views/library_browser.py` grows from PR 10a's stub into a real
  loader: filter form (street dropdown, stack-range slider,
  board-regex input, free-text label search); sortable
  `SpotMetadata` table; per-row actions (Load → main solve panel,
  Export → file dialog, Delete → confirm dialog); footer with
  `LibraryStats` summary. `Library.get` offloaded to
  `asyncio.to_thread` to avoid blocking UI on large gzip blobs.
- "Save to library" button on PR 10's spot input panel. Click flow:
  build `SpotDescription` from current input → call `Library.put(spot,
  result, overwrite=False)` → toast on success / dialog on
  `LibraryDuplicateError` ("Overwrite?" → re-call with
  `overwrite=True`). Disabled if no solve has run.
- No auto-save. Per PLAN.md "no auto-population." User explicitly
  controls what enters the library.

New files:
- `poker_solver/library.py` (~450 LOC): `Library` class +
  `SpotDescription`, `SpotMetadata`, `LibraryFilter`, `LibraryStats`
  dataclasses + `LibraryError` / `LibraryDuplicateError` /
  `LibrarySchemaError` exception hierarchy + `_canonicalize_spot` /
  `_compute_spot_id` helpers. Pure Python + stdlib + NumPy.
  `mypy --strict` clean.
- `poker_solver/library_schema.sql`: DDL per spec §2.2; loaded by
  `Library.open()` via `connection.executescript(...)`.
- `scripts/batch_solve.py` (~200 LOC): CSV parser + solve loop +
  optional multiprocessing pool. Standalone-runnable or via the
  CLI subcommand `poker-solver batch-solve --input <csv>`.
- `scripts/build_macos_dmg.sh` (~150 LOC): bash orchestrator for
  the full packaging pipeline.
- `scripts/sign_and_notarize.py` (~200 LOC): Python helper —
  `sign_bundle`, `notarize`, `staple`, `sign_inside_out`. Callable
  with explicit args; reusable from CI/future scripts.
- `scripts/entitlements.plist`: Hardened Runtime entitlements per §6.4.
- `assets/poker_solver.icns`: app icon placeholder.
- `assets/README.md`: how to regenerate the icon via `iconutil` from
  a `.png` source.
- `tests/test_library.py` (~15 unit tests per spec §9): schema, WAL
  concurrency, spot ID determinism (semantically-equivalent inputs →
  same ID; meaningful changes → different ID), gzip bit-exact
  roundtrip (`np.array_equal` — NOT `np.allclose`), put/get/delete
  /list/export/import roundtrips, duplicate handling, filter
  composition, schema-version hard error.
- `tests/test_library_cli.py` (~5 integration tests): exercise the
  CLI subcommands end-to-end via `subprocess.run`.
- `tests/test_library_ui_integration.py`: STUB —
  `pytest.skip("requires PR 10 UI harness")` at module level
  until PR 10's UI test harness ships.

Modified:
- `poker_solver/cli.py`: `library` subcommand group (`list`, `get`,
  `put`, `export`, `import`, `delete`, `stats`) + `batch-solve`
  sibling top-level subcommand. List output tab-separated by default;
  `--json` for machine-readable; `--table` for rich-table (if
  `rich` installed; otherwise tab-separated).
- `poker_solver/__init__.py`: re-exports `Library`, `SpotDescription`,
  `SpotMetadata`, `LibraryFilter`, `LibraryStats`, `LibraryError`,
  `LibraryDuplicateError`, `LibrarySchemaError`. Exposes `__version__`
  (used by `solver_version` field).
- `ui/views/library_browser.py`: PR 10a stub → real loader per §4.1.
- `pyproject.toml`: `[project.optional-dependencies] distribution =
  ["pyinstaller>=6.0"]`; NO new runtime dependencies (SQLite, gzip,
  hashlib, json are stdlib).
- `scripts/check_pr.sh`: extend the test command to include
  `tests/test_library.py tests/test_library_cli.py`.

Notable contract decisions (defaults per spec §13):
- Apple Developer enrollment OPTIONAL; unsigned-fallback path
  produces a working `.app` without $99/yr cost (D1).
- Library file at `~/.poker_solver/library.db` with env var override
  (D2).
- Spot export format JSON (uncompressed, human-inspectable, no new
  dep). YAML / binary / `.json.gz` rejected (D3).
- No auto-suggest library spots on UI input (deferred to PR 11.5; D4).
- Explicit schema migration (NOT auto-rebuild lossy; D5).
- arm64-only bundle (NOT universal2; D6).
- Plain default DMG window styling (D7).
- PyInstaller `--onedir` (NOT `--onefile`; D8).
- Explicit "Save to library" button (NOT auto-save; D9).
- `create-dmg` Homebrew formula (NOT sindresorhus npm; D10).
- gzip compresslevel 6 (D11).
- CLI list output tab-separated default (D12).
- PR 11 follows PR 10 (D13).

Out of scope (per §1 non-goals): cloud-distributed library, auto-
population scheduler, multi-user/multi-machine library, neural
value warm-starts from cached spots (PR 13+), Windows/Linux
installers, universal2 binary, Apple Developer enrollment mandate,
new `pyproject.toml` runtime deps, UI test framework introduction.

Verification:
- pytest tests/test_library.py tests/test_library_cli.py -v: all
  ~20 tests pass.
- pytest -m "not slow and not very_slow" --tb=line: all pass /
  skip; no failures. PR 1-10b regression: all green unchanged.
- ruff check + ruff format + black --check + mypy --strict on the
  new + modified files: clean.
- `mypy --strict poker_solver/library.py`: clean.
- `./scripts/build_macos_dmg.sh --skip-signing --skip-notarization`
  produces a launchable unsigned `.app` + `.dmg` < 200 MB on Apple
  M-series MacBook. In-bundle smoke step asserts `from poker_solver
  import _rust` succeeds before the DMG is built.
- `poker-solver library list` on fresh machine: creates the DB,
  returns empty list.
- `poker-solver batch-solve --input examples/tiny_csv.csv --dry-run`:
  parses without error.
- Manual round-trip: `library put` from JSON → `library get` →
  `library export` → `library delete` → `library import` → `library
  get` returns equivalent `SolveResult`.
- Concurrent read-while-write test on multi-threaded fixture (WAL
  mode load-bearing).
- (Optional, requires Apple credentials)
  `./scripts/build_macos_dmg.sh` end-to-end produces a notarized
  stapled DMG that installs and runs on a clean macOS user account.

License compliance: PyInstaller is GPL-with-exception — the
exception explicitly covers bundled apps (per PyInstaller's COPYING
file); confirmed in the audit. SQLite is public domain (stdlib).
NumPy is BSD. NiceGUI is MIT (PR 10a dep, unchanged). No new AGPL
contamination. Library code is pure Python + stdlib (zero new
runtime deps). PR 11 ships zero AGPL/GPL code in the runtime or
bundle.

Branch: pr-11-library-and-packaging (off integration tip post-PR-10b).
This is the v1.0.0 release tip; merges to `integration` and `main`
on user OK, then tagged `v1.0.0` and DMG attached to the GitHub
release.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
