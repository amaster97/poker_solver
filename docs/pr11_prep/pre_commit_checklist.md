# PR 11 pre-commit checklist

**Date staged:** 2026-05-22
**Author:** orchestrator pre-commit prep agent
**Purpose:** gate list the orchestrator runs immediately before firing
the commit pipeline once the audit verdict clears. Every gate MUST
pass (or carry an explicit waiver with rationale) before `git commit`.

This is the **v1.0.0 milestone** PR. Treat the gate list with extra
care — the merge tip becomes the `v1.0.0` tag and the DMG is the
artifact users actually install.

## Build + lint gates

- [ ] **G1 — pytest library tests clean.** `pytest tests/test_library.py tests/test_library_cli.py -v --tb=line` returns 0.
  - Expected count: ~15 unit tests + ~5 CLI tests = ~20 library tests.
  - `test_library_ui_integration.py` skips with `pytest.skip("requires PR 10 UI harness")` at module level — verify the skip is clean (NOT an error).

- [ ] **G2 — pytest fast tier clean.** `pytest -m "not slow and not very_slow" --tb=line` returns 0.
  - All PR 1-10b regression tests pass unchanged.
  - PR 11 is purely additive to `poker_solver/` (`library.py` is the one new public module) — no engine code is modified.

- [ ] **G3 — ruff + black clean.** `ruff check poker_solver tests scripts` and `black --check poker_solver tests scripts` return 0.

- [ ] **G4 — mypy strict clean on new code.** `mypy --strict poker_solver/library.py` returns 0. `mypy poker_solver` overall: no new errors.
  - Watch for: `SpotDescription` wraps `HUNLConfig` (existing many fields); `LibraryFilter` Optional fields; SQLite cursor return types; the canonicalization JSON-encoder type.

## Library correctness gates

- [ ] **G5 — Spot ID deterministic across runs + machines.** `test_library_spot_id_deterministic` (spec §9 #3) passes — semantically-equivalent inputs (reordered bet-menu, reordered board) → identical SHA-256. Canonicalization rules per spec §2.3:
  - Board cards sorted ascending by `(rank, suit)`.
  - Stack values in integer cents.
  - Bet-menu fractions tuple sorted ascending.
  - Initial-ranges sorted hand-list with canonical hand form.
  - Antes + rake included even when 0.
  - Solver hyperparameters EXCLUDED.
  - JSON: `json.dumps(..., sort_keys=True, separators=(",", ":"))`.

- [ ] **G6 — Spot ID differs on meaningful change.** `test_library_spot_id_differs_on_meaningful_change` (§9 #4) — stack 100→101 BB → different ID; one card different → different ID.

- [ ] **G7 — gzip bit-exact roundtrip (NOT np.allclose).** `test_library_compression_preserves_bit_exact_strategy` (§9 #11) — `SolveResult` with float values including `0.0, 1.0, 1e-15, 1-1e-15`; `put`/`get` roundtrip; every probability vector compares `np.array_equal` (NOT `np.allclose`).
  - Anti-pattern check: `grep -n "np.allclose\|pytest.approx" tests/test_library.py` — if `np.allclose` appears in the compression roundtrip test, that's must-fix (silent precision loss is a strategy-display corruption vector).
  - gzip compresslevel = 6 (spec §13 D11). Drift to 9 or 1 = should-fix.

- [ ] **G8 — SQLite WAL mode.** `library_schema.sql` (or `Library.open` setup) executes `PRAGMA journal_mode = WAL;` AND `PRAGMA foreign_keys = ON;` on every connection. Default journal mode is `DELETE` (rollback journal); without WAL, concurrent reader during write → `database is locked` error.
  - Tested: `test_library_concurrent_readers_dont_corrupt` (§9 #12) — open two `Library` instances on same file; one writes, one reads concurrently from threads; no exceptions, correct data.

- [ ] **G9 — Schema version hard error.** `test_library_schema_version_mismatch_errors` (§9 #15) — manually insert `library_version=999` in `spots_meta`; open; expect `LibrarySchemaError`.
  - Anti-pattern: silent migration on version mismatch (user loses data without warning) → must-fix.
  - `solver_version` mismatch on `get()` → `UserWarning` (soft). Hard-erroring on `solver_version` is too aggressive (should-fix).
  - `LibrarySchemaError` re-exported from `poker_solver/__init__.py`.

## Packaging correctness gates

- [ ] **G10 — PyInstaller `--add-binary` for `_rust.so` (HIGHEST IMPACT).** `scripts/build_macos_dmg.sh` PyInstaller invocation includes the literal `--add-binary "poker_solver/_rust.cpython-313-darwin.so:poker_solver"` (or its parameterized equivalent).
  - Without this, the bundled `.app` launches then crashes on the first call into Rust — worst-case user-experience failure (install appears to succeed, dies on first solve).
  - Colon-separated `src:dest`. The dest path is the relative bundle location (`poker_solver`), not absolute. Typo or wrong dest = silent import failure = must-fix.
  - Per `audit_preprep.md` §1.1: HIGHEST-IMPACT must-fix band.

- [ ] **G11 — In-bundle smoke test step.** `build_macos_dmg.sh` after PyInstaller succeeds runs the bundled python with `from poker_solver import _rust; print(_rust)` and fails the build on `ImportError`. Catches the `--add-binary` failure mode in CI/local rather than at user install time.

- [ ] **G12 — PyInstaller `--onedir`, NOT `--onefile`.** Per spec §6.3 + §13 D8. `--onefile` "requires unpacking on each run" and breaks code-signing of inner files. Verify `grep onefile scripts/build_macos_dmg.sh` returns no positive match (the literal flag, not as part of `--onedir`).

- [ ] **G13 — `--skip-signing --skip-notarization` produces working unsigned bundle.** `./scripts/build_macos_dmg.sh --skip-signing --skip-notarization` runs to completion without requiring any Apple credentials and produces `dist/Poker Solver.app` + `dist/Poker-Solver-1.0.0-arm64.dmg`. Both launchable on M-series MacBook (after right-click → Open for unsigned bypass).
  - Anti-pattern: script `set -e` + dies on missing `Developer ID Application` cert or `$APPLE_ID` env var even with skip flags → must-fix.
  - Per `audit_preprep.md` §1.2: HIGH-PROB must-fix band.

- [ ] **G14 — No committed Apple credentials.** `grep -rEi 'apple_id|team_id|app_specific_password|developer id application' scripts/ poker_solver/ assets/` returns ZERO literal credentials (generic references in docstrings excluded). `scripts/entitlements.plist` contains entitlements only — no team IDs or developer IDs.

- [ ] **G15 — Inside-out signing walk.** `scripts/sign_and_notarize.py` does an explicit `find Contents -name "*.dylib" -o -name "*.so"` walk, signs each inner binary with the Developer ID + Hardened Runtime (`--options runtime`), THEN signs the outer `.app`. `codesign --deep` alone is documented-unreliable on PyInstaller bundles.

- [ ] **G16 — Hardened Runtime entitlements correct.** `scripts/entitlements.plist` contains `com.apple.security.cs.allow-jit`, `com.apple.security.cs.allow-unsigned-executable-memory`, `com.apple.security.cs.disable-library-validation` — all set to `<true/>`. Justified per spec §6.4.

- [ ] **G17 — arm64-only DMG.** Output filename matches `Poker-Solver-1.0.0-arm64.dmg`. PyInstaller invoked without arch flag will inherit the host's arch; verify the build script either passes `--target-arch arm64` (PyInstaller 6.0+) or relies on the arm64 build host. NOT universal2 (per §13 D6 — PLAN.md "MacBook-only, 16 GB Apple Silicon"; universal2 ~2× DMG size).

## Dependency gates

- [ ] **G18 — No new runtime dependencies.** `git diff integration -- pyproject.toml` shows ONLY the addition of `[project.optional-dependencies] distribution = ["pyinstaller>=6.0"]` AND optionally `[ui]` extra (if PR 10a wasn't already in integration). Base `[project.dependencies]` unchanged.
  - Library uses only stdlib: `sqlite3`, `gzip`, `hashlib`, `json`. NumPy already on the dep list from PR 1.
  - `pip install poker-solver` (without `[distribution]` and `[ui]`) still works and gives a fully functional CLI engine.

- [ ] **G19 — PyInstaller GPL-with-exception license confirmed.** PyInstaller is GPL-with-exception; the exception explicitly covers bundled apps (per PyInstaller's COPYING file). Audit report's "License compliance" section confirms this in writing.

## CLI surface gates

- [ ] **G20 — Library CLI subcommands wired.** `poker-solver library list|get|put|export|import|delete|stats` all work end-to-end (verified by `test_library_cli.py` integration tests). Each has a useful `--help`.
  - List output: tab-separated by default; `--json` for machine-readable; `--table` for rich-table (if `rich` installed; else tab-separated).

- [ ] **G21 — Batch-solve CLI wired.** `poker-solver batch-solve --input <csv>` parses CSV per spec §5.1 columns (name,starting_street,initial_board,stacks_bb,bet_sizes,abstraction_path,iterations) and runs the solve loop with `[SKIP] / [OK] / [OOM] / [ERROR]` per-row output. `--dry-run` parses without solving. `--workers N` (default 1) parallelizes via `multiprocessing.Process`.

- [ ] **G22 — Library file location respects env var + flag.** `POKER_SOLVER_LIBRARY_PATH=/tmp/foo.db poker-solver library list` honors the override. `--library-path <path>` flag also honored. Default: `~/.poker_solver/library.db` (XDG-style; parent dir auto-created).

## Idempotency + portability gates

- [ ] **G23 — Idempotent batch-solve.** `test_library_export_import_roundtrip` (§9 #10) + manual CLI round-trip pass. Re-running same CSV after a crash is a no-op for already-saved spots (via `Library.get` skip in batch_solve loop).

- [ ] **G24 — Export/import portable.** A spot exported on Machine A imports on Machine B with `Library.get` returning equivalent `SolveResult`. Format is uncompressed JSON; no machine-specific paths in the export. Spec §11 #12.

## UI integration gate (extends PR 10a)

- [ ] **G25 — Library viewer page grew from stub to real loader.** `ui/views/library_browser.py` was a PR 10a stub (three faked rows + "PR 11" banner) and is now a real `Library`-backed page:
  - Filter form (street dropdown, stack-range slider, board-regex input, free-text label search).
  - Sortable `SpotMetadata` table.
  - Per-row actions: Load (sends `spot_id` to main solve panel + triggers `Library.get`), Export (file dialog + `Library.export`), Delete (confirm dialog + `Library.delete`).
  - Footer with `LibraryStats` summary.
  - `Library.get` calls offloaded to `asyncio.to_thread` to avoid blocking UI on large gzip blobs.

- [ ] **G26 — "Save to library" button on PR 10's spot input panel.** Click → build `SpotDescription` → `Library.put(spot, result, overwrite=False)` → toast on success / dialog on `LibraryDuplicateError`. Disabled if no solve has run. Per spec §4.2.

## Audit gate

- [ ] **G27 — PR 11 audit verdict.** `docs/pr11_prep/audit_report.md` carries verdict **READY** or **READY-WITH-PATCHES**, NOT **NOT-READY**.
  - READY → commit.
  - READY-WITH-PATCHES → apply patches in-place, re-run G1-G26 on the patched code, then commit.
  - NOT-READY → abort commit; orchestrator escalates to the user with the audit-report's must-fix list.
  - Audit focus areas (per `audit_prompt_final.md` 15-area brief): `--add-binary` for `_rust.so` (HIGHEST); `--skip-signing` path independent of Apple creds (HIGH-PROB); DMG arm64-only + inside-out signing walk (HIGH-PROB); WAL mode; spot ID determinism; gzip bit-exact (`np.array_equal` not `np.allclose`); schema-version hard error; no committed credentials; no new runtime deps; `--onedir` not `--onefile`; CLI surface; idempotent batch-solve; library viewer UI integration; export/import portability; test count.

## Branch + integration gates

- [ ] **G28 — Branch synced.** `git fetch --all`; verify integration baseline (PR 10b tip) unchanged. `pr-11-library-and-packaging` contains all Agent A/B/C diffs, no merge conflicts.

- [ ] **G29 — File scope contained.** `git diff integration..pr-11-library-and-packaging --stat` shows ~18-22 files:
  - 2 new Python source files: `poker_solver/library.py`, `poker_solver/library_schema.sql`.
  - 3 new test files: `tests/test_library.py`, `tests/test_library_cli.py`, `tests/test_library_ui_integration.py` (stub).
  - 4 new packaging files: `scripts/batch_solve.py`, `scripts/build_macos_dmg.sh`, `scripts/sign_and_notarize.py`, `scripts/entitlements.plist`.
  - 2 new asset files: `assets/poker_solver.icns`, `assets/README.md`.
  - Modifications: `poker_solver/__init__.py` (re-exports + `__version__`), `poker_solver/cli.py` (library + batch-solve subcommands), `ui/views/library_browser.py` (stub → real loader), `pyproject.toml` (`[distribution]` extra + version bump), `scripts/check_pr.sh` (run library tests).
  - v1.0.0 bump + docs touch-ups: `CHANGELOG.md` (new [1.0.0] section + v1 GA summary), `README.md` (v1 GA badge + Installation section).
  - No edits to: `poker_solver/range.py`, `poker_solver/hunl.py`, `poker_solver/solver.py`, `poker_solver/hunl_solver.py`, `poker_solver/preflop_solver.py`, `poker_solver/blueprint.py`, `poker_solver/subgame_refiner.py`, `poker_solver/dcfr.py`, `poker_solver/abstraction/`, `poker_solver/profiler/`, any Rust file (PR 11 is library + packaging, NOT engine code), PR 3.5 charts, PR 4 abstraction artifacts, any test file outside `tests/test_library*.py`.

## Biggest gate

**G10 (`--add-binary` for `_rust.so`)** is the highest-impact must-fix in PR 11 and one of the highest in the entire v1 roadmap. Silent failure mode: bundle builds and installs successfully, then crashes the user's first solve attempt with `ModuleNotFoundError` on `poker_solver._rust`. The user has no way to debug this from the GUI; the `.app` simply dies. **G11 (in-bundle smoke test)** is the safety net that catches G10 in CI/local before shipping — without G11, G10 can silently regress between PR 11 ship and any subsequent build.

Secondary biggest gate: **G7 (gzip bit-exact `np.array_equal`)** — `np.allclose` in the roundtrip test silently allows precision drift, corrupting strategy displays in PR 11+ users' libraries.

Tertiary biggest gate: **G14 (no committed Apple credentials)** — leaking a Developer ID or app-specific password into the public repo would compromise the user's signing identity (a security blocker, not just a UX issue).

## Commit firing order

Once all gates green:
1. `git status` — confirm clean working tree on `pr-11-library-and-packaging` with all expected staged changes.
2. `git diff --cached --stat` — final sanity check; verify ~18-22 file scope.
3. `git commit -F docs/pr11_prep/commit_message_draft.md` (or paste via HEREDOC per memory's git-safety protocol).
4. `git status` — verify commit success.
5. Push not yet — wait for user OK on the commit + audit report bundle before `git push origin pr-11-library-and-packaging`.

## v1.0.0 release follow-up (post-commit, post-merge — orchestrator coordinates, do NOT fire from this checklist)

These steps happen AFTER `pr-11-library-and-packaging` merges to `integration` and (with user OK) to `main`. They are listed here for orchestrator handoff, NOT as commit gates.

1. Tag `v1.0.0` on `main` with the v1 GA summary as the tag message.
2. Run `./scripts/build_macos_dmg.sh` end-to-end (with Apple credentials in env vars per spec §6.5) to produce the signed + notarized + stapled `Poker-Solver-1.0.0-arm64.dmg`.
3. Manually verify the DMG installs cleanly on a clean macOS user account (per spec §16 "success criteria" — optional, requires Apple credentials).
4. Create the GitHub release attached to `v1.0.0` with the DMG as a release asset.
5. Update PLAN.md §1 to mark v1 as shipped; move v1.5/v2 items to the top of the roadmap.

## Non-commits in this round

- Do NOT auto-merge `pr-11-library-and-packaging` into `integration` or `main`. The v1.0.0 commit is the highest-care merge in the project; user must explicitly OK.
- Do NOT close any GitHub PRs yet.
- Do NOT push to GitHub release until the DMG is built and manually verified on a clean macOS account.
- Do NOT modify any engine file (`poker_solver/range.py`, `dcfr.py`, `hunl.py`, `solver.py`, `hunl_solver.py`, `preflop_solver.py`, `blueprint.py`, `subgame_refiner.py`, `abstraction/`, `profiler/`) — PR 11 is purely additive to `poker_solver/`.
- Do NOT modify any Rust file — PR 11 is library + packaging, not engine code.
- Do NOT add `pyinstaller` to base `[project.dependencies]` — `[distribution]` extra ONLY.
- Do NOT add SQLite, gzip, hashlib, or json as new deps — they are stdlib.
