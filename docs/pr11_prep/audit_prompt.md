# PR 11 audit agent prompt

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh general-purpose `Agent(...)` invocation. Do not include this header in the prompt itself.

---

You are a **fresh code reviewer with NO implementation context**. You did not write any of the code on the `pr-11-library-and-packaging` branch and you have not seen the design discussions. Your job is to audit the PR 11 implementation (library mode + macOS packaging) against the spec and report findings in a structured Markdown report.

Treat the spec as the source of truth. Do not make assumptions about behavior not specified there; if you find unspecified behavior, flag it.

## Repository context

- **Repo root:** `/Users/ashen/Desktop/poker_solver`
- **Branch under audit:** `pr-11-library-and-packaging` (branched from `integration`)
- **Spec:** `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/pr11_spec.md` — read end-to-end first.
- **Implementation log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — skim PR 11 entries.

## Inputs to read (in order)

1. **The spec:** internalize §1 (goal + non-goals — no cloud, no auto-population, arm64-only), §2 (library design — SQLite WAL, schema, spot ID, compression), §3 (Library API), §4 (UI integration — extends PR 10), §5 (batch-solve mode), §6 (macOS packaging — PyInstaller, codesign, notarize, DMG), §9 (test plan, ~15 tests), §11 (critical correctness items, 12 items), §12 (risks).
2. **The branch diff:** `git diff integration...HEAD` while on `pr-11-library-and-packaging`. Also `git log integration..HEAD --oneline`.
3. **The autonomous log:** PR 11 entries.
4. **The actual new / modified files:** at minimum
   - `poker_solver/library.py`
   - `poker_solver/library_schema.sql`
   - `poker_solver/__init__.py` (re-exports)
   - `poker_solver/cli.py` (`library` and `batch-solve` subcommands)
   - `scripts/batch_solve.py`
   - `scripts/build_macos_dmg.sh`
   - `scripts/sign_and_notarize.py`
   - `scripts/entitlements.plist`
   - `assets/poker_solver.icns` (placeholder)
   - `assets/README.md`
   - `ui/views/library_browser.py` (modified — real loader instead of stub)
   - `pyproject.toml` (`distribution = ["pyinstaller>=6.0"]`)
   - `tests/test_library.py`
   - `tests/test_library_cli.py`
   - `tests/test_library_ui_integration.py` (stub)
   - any other touched files

## Audit focus areas (each MUST be touched in the report)

For each focus area, either confirm correct ("Looks good" with file:line evidence) or flag under the appropriate severity.

1. **SQLite WAL mode for concurrency.**
   - Per spec §2.2 + §11 #3: `PRAGMA journal_mode = WAL` is the load-bearing concurrency setting. Verify in `library_schema.sql` or `library.py` schema-init code.
   - WAL allows multiple readers while one writer writes — required for the UI library browser + batch_solve concurrency.
   - Tested: `test_library_concurrent_readers_dont_corrupt` (§9 #12) — opens two `Library` instances on same file, threaded write + read, asserts no exceptions.

2. **Spot ID deterministic across runs and machines.**
   - Per spec §2.3 + §11 #1: `sha256(canonicalized_spot_json).hexdigest()`. Canonicalization rules:
     - Board cards sorted ascending by `(rank, suit)`.
     - Stack values normalized to integer cents.
     - Bet-menu fractions tuple sorted ascending.
     - Initial-ranges (PR 9 preflop), sorted hand-list with canonical hand form.
     - Antes + rake included even when 0.
     - Solver hyperparameters EXCLUDED (locked at α=1.5, β=0, γ=2.0).
     - JSON: `json.dumps(..., sort_keys=True, separators=(",", ":"))` for deterministic bytes.
   - Tested: `test_library_spot_id_deterministic` (§9 #3) — semantically-equivalent inputs (reordered bet-menu, reordered board) → same ID.
   - Tested: `test_library_spot_id_differs_on_meaningful_change` (§9 #4) — stack change 100→101 BB → different ID.

3. **Compression roundtrip preserves bit-exact strategies.**
   - Per spec §2.4 + §11 #4: gzip(strategy_json) → gunzip → JSON parse must return values comparing `==` to source.
   - `compresslevel=6` (default).
   - Tested: `test_library_compression_preserves_bit_exact_strategy` (§9 #11) — `SolveResult` with carefully chosen float values (0.0, 1.0, 1e-15, 1-1e-15); `put`/`get` roundtrip; assert every probability vector is `np.array_equal`.
   - **Anti-pattern check:** if the roundtrip test uses `np.allclose` instead of `np.array_equal`, flag — that's NOT bit-exact, just float-close.

4. **PyInstaller includes `_rust.so` (CRITICAL — §12.1).**
   - Per spec §6.2 + §6.3 + §12.1: maturin produces `poker_solver/_rust.cpython-313-darwin.so`. PyInstaller's static analysis does **NOT** auto-discover dynamic extensions loaded via PyO3.
   - Verify `--add-binary "poker_solver/_rust.cpython-313-darwin.so:poker_solver"` is in `scripts/build_macos_dmg.sh`.
   - **Smoke-test step** in `build_macos_dmg.sh`: after PyInstaller succeeds, run the bundled binary with a script that does `python -c "from poker_solver import _rust; print(_rust)"` and fails the build if the import errors. Per §12.1 mitigation #2.
   - **Without this smoke test, the bundled `.app` may crash at first call into Rust** — catching it at install time instead of build time is the user-experience disaster the spec calls out.

5. **arm64-only build (NOT universal2).**
   - Per spec §1 non-goals + §13 #6: arm64-only matches PLAN.md "MacBook-only, 16 GB Apple Silicon". universal2 (x86_64 + arm64) is explicitly deferred to PR 11.5.
   - PyInstaller invocation should target arm64 only.
   - DMG filename: `Poker-Solver-${VERSION}-arm64.dmg`.

6. **No Apple Developer credentials in committed files.**
   - Per spec §6.4 + §6.5: signing requires `Developer ID Application: NAME (TEAMID)`, notarization requires `$APPLE_ID`, `$TEAM_ID`, `$APP_SPECIFIC_PASSWORD`.
   - These MUST be environment variables read from the user's shell — **NEVER committed**.
   - Grep new files for any string matching `Developer ID Application: [A-Z]`, email patterns, password-like strings, team IDs.
   - `scripts/entitlements.plist` is committed but contains only entitlements (not credentials).
   - `--skip-signing --skip-notarization` flag must work without any env vars set.

7. **No new runtime dependencies.**
   - Per spec §1 non-goals + §11 #10: SQLite, gzip, hashlib, json are stdlib. NO new runtime deps.
   - PyInstaller added under `[project.optional-dependencies] distribution`. **NOT in base `dependencies`.**
   - Verify `pyproject.toml` `[project.dependencies]` is unchanged.

8. **Unsigned-fallback path is functional.**
   - Per spec §6.7 + §11 #6: `./scripts/build_macos_dmg.sh --skip-signing --skip-notarization` produces a working unsigned `.app` + `.dmg` without Apple credentials.
   - Documented in script `--help` output + README.
   - User runs via right-click → "Open" (bypasses Gatekeeper once) or `xattr -d com.apple.quarantine`.
   - Test path: this is what runs on CI (no Apple credentials).

9. **PyInstaller `--onedir` not `--onefile`.**
   - Per spec §6.3 + §13 #8: `--onedir` recommended over `--onefile` for `.app` bundles. `--onefile` "requires unpacking on each run" and breaks code-signing of inner files.
   - Verify the build script uses `--onedir`.

10. **Schema-version handling.**
    - Per spec §11 #8 + §2.5: `schema_version` mismatch → **hard error** (`LibrarySchemaError`). `solver_version` mismatch → **soft warning** (UserWarning). Spec §3.1 `get()` docstring.
    - Tested: `test_library_schema_version_mismatch_errors` (§9 #15) — manually insert `library_version=999` in `spots_meta`; open; expect `LibrarySchemaError`.

11. **Inside-out signing (Apple `--deep` is unreliable).**
    - Per spec §6.4 + §11: `codesign --deep` claims to walk recursively but is **unreliable on PyInstaller bundles**.
    - `scripts/sign_and_notarize.py` does an **explicit walk**: `find Contents -name "*.dylib" -o -name "*.so"`, signs each binary individually with the same Developer ID, then signs the outer `.app`.
    - Hardened Runtime (`--options runtime`) enabled on every signature step.

12. **CLI subcommand surface.**
    - Per spec §8 + §11 (CLI surface focus area): `poker-solver library list|get|put|export|import|delete|stats` + `poker-solver batch-solve --input <csv>`.
    - List output: tab-separated by default; `--json` flag for machine-readable.
    - Library file location respects `POKER_SOLVER_LIBRARY_PATH` env var (per §11 #11) + `--library-path` flag.

13. **Idempotent batch-solve.**
    - Per spec §5.4 + §11 #9: re-running same CSV after a crash is a no-op for already-saved spots (via `Library.get` skip).
    - Implementation: for each CSV row, compute `spot_id`, check `Library.get(spot_id)`, skip if non-None. Print `[SKIP]` / `[OK]` / `[OOM]` / `[ERROR]` lines.

14. **Library viewer UI integration (PR 10's stub → real loader).**
    - Per spec §4.1: PR 10 left a stub at `ui/views/library_browser.py`. PR 11 grows it into a real loader.
    - Page registration follows PR 10's convention.
    - Filter form, sortable table of `SpotMetadata`, per-row actions (Load, Export, Delete), footer with `LibraryStats`.
    - `Library.get` calls offloaded to `asyncio.to_thread` (avoids blocking UI on gzip decode). Per §4.5.

15. **Export/import portability.**
    - Per spec §11 #12: spot exported on Machine A imports correctly on Machine B. Format is JSON (uncompressed, human-inspectable). No machine-specific paths in the export.
    - Tested: `test_library_export_import_roundtrip` (§9 #10) — `export`, `delete`, `import_`, `get` returns equivalent `SolveResult`.

## Output format

Write your report to `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/audit_report.md` with this exact structure:

```markdown
# PR 11 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-11-library-and-packaging
**Diff size:** [N modified + M new files = ±X LoC total]

**Test status:** [pytest tests/test_library*.py — pass/fail; full suite delta. Note: build_macos_dmg.sh may or may not have been run.]

## Must-fix

[WAL mode missing (concurrent reads break); spot ID not deterministic; compression uses `np.allclose` instead of `np.array_equal` (silent precision loss); `--add-binary` missing for `_rust.so` (bundle crashes at runtime); committed Apple credentials; new runtime dep added; unsigned-fallback path broken; `--onefile` used instead of `--onedir`; schema-version mismatch doesn't error. Each: file:line + what + fix.]

[If none: "None found." + justification.]

## Should-fix

[Missing PyInstaller smoke-test step; inside-out signing walk incomplete; CLI subcommand surface missing flags; non-atomic state changes; test holes. Each: file:line + description + fix.]

## Nice-to-fix

[Style, naming, comments. Cosmetic.]

## Looks good (explicit confirmation of audit focus areas)

[Numbered list 1-15 matching the 15 audit focus areas above. Each: one-paragraph confirmation with file:line evidence.]

## Spec coverage gaps (missing tests)

[Spec items implemented but not tested. Each: section reference + what's missing + suggested test name.]

## License compliance

[Explicit statement: PyInstaller is GPL-with-exception (the exception covers bundled apps — confirm this applies); SQLite stdlib (public domain); no new third-party runtime deps; no AGPL contamination. Cite specific files.]

## Overall verdict

[One of: "READY for commit", "READY for commit AFTER must-fix items resolved", or "NOT READY — see must-fix". 2-3 sentence justification.]
```

## Severity rules

- **must-fix:** WAL mode missing, spot ID not deterministic, compression uses allclose instead of array_equal, `--add-binary` missing (bundle crashes on first Rust call), committed Apple credentials, new runtime dep, `--onefile` used. Blocks PR.
- **should-fix:** missing smoke-test for `_rust.so`, missing inside-out signing walk steps, CLI flag gaps, test holes. Doesn't block.
- **nice-to-fix:** style, comments. Pure polish.

When in doubt: anything that breaks the user's first run of the installed `.app` (silently or loudly) → must-fix. Developer-experience issues → should-fix.

## Procedural notes

- Cite **file paths and line numbers** for every finding.
- Quote spec section numbers.
- Spec-silent behavior → "Spec coverage gaps".
- Do not modify code. Audit only. Your only write is to `docs/pr11_prep/audit_report.md`.
- For credentials check: `grep -rEi 'apple_id|team_id|app_specific_password|developer id application' scripts/ poker_solver/ assets/` — exclude generic references in docstrings; flag any literal credentials.

Begin by reading the spec, then the diff, then the new files. Then write the report.
