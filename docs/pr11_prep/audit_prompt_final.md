# PR 11 audit agent prompt (FINAL — pre-staged for post-fan-out dispatch)

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh general-purpose `Agent(...)` invocation. Do not include this header in the prompt itself.
>
> **Pre-stage anchors (orchestrator-side only — DO NOT include in prompt):**
> - Expected verdict per `audit_preprep.md` §3: READY-WITH-PATCHES (~55%) > clean READY (~30%) > NOT-READY (~15%).
> - Top three pre-flagged risk surfaces (audit MUST touch with file:line evidence): PyInstaller `--add-binary` for `_rust.so` (`audit_preprep.md` §1.1), code-signing optionality / unsigned-fallback (§1.2), DMG notarization arm64-only + inside-out walk (§1.3).
> - Low-probability but must-fix-band-if-violated: SQLite WAL mode (§1.4), gzip-6 bit-exact roundtrip (§1.5), schema-version hard-error path (§1.6).

---

You are a **fresh code reviewer with NO implementation context**. You did not write any of the code on the `pr-11-library-and-packaging` branch and you have not seen the design discussions. Your job is to audit the PR 11 implementation (library mode + macOS packaging) against the spec and report findings in a structured Markdown report.

Treat the spec as the source of truth. Do not make assumptions about behavior not specified there; if you find unspecified behavior, flag it.

PR 11 is **the only PR in the v1 roadmap that produces a shippable `.app`**. The PyInstaller bundle + codesign + notarize chain has high downstream impact: a missing `--add-binary` flag means the user's first solve crashes the app even though install succeeded — the worst-case user-experience failure mode.

## Repository context

- **Repo root:** `/Users/ashen/Desktop/poker_solver`
- **Branch under audit:** `pr-11-library-and-packaging` (branched from `integration`; verified via `fanout_ready.md`).
- **Spec:** `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/pr11_spec.md` — read end-to-end first.
- **Implementation log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — skim PR 11 entries.
- **Locked defaults D1-D13:** `pr11_spec.md` §13.

## Inputs to read (in order)

1. **The spec:** internalize §1 (goal + non-goals — no cloud, no auto-population, arm64-only), §2 (library design — SQLite WAL, schema, spot ID, compression), §3 (Library API), §4 (UI integration — extends PR 10), §5 (batch-solve mode), §6 (macOS packaging — PyInstaller, codesign, notarize, DMG), §9 (~15 tests), §11 (critical correctness, 12 items), §12 (risks, esp #1 PyInstaller `--add-binary`), §13 (locked defaults).
2. **The branch diff:** `git diff integration...HEAD` while on `pr-11-library-and-packaging`. Also `git log integration..HEAD --oneline`.
3. **The autonomous log:** PR 11 entries.
4. **The actual new / modified files:** at minimum
   - `poker_solver/library.py`
   - `poker_solver/library_schema.sql`
   - `poker_solver/__init__.py` (re-exports incl. `LibrarySchemaError`)
   - `poker_solver/cli.py` (`library` and `batch-solve` subcommands)
   - `scripts/batch_solve.py`
   - `scripts/build_macos_dmg.sh`
   - `scripts/sign_and_notarize.py`
   - `scripts/entitlements.plist`
   - `assets/poker_solver.icns` (placeholder)
   - `assets/README.md`
   - `ui/views/library_browser.py` (modified — real loader instead of stub)
   - `pyproject.toml` (`[project.optional-dependencies] distribution = ["pyinstaller>=6.0"]`)
   - `tests/test_library.py`
   - `tests/test_library_cli.py`
   - `tests/test_library_ui_integration.py` (stub)
   - any other touched files

Do not actually run `build_macos_dmg.sh`. Audit the *committed* code + tests.

## Audit focus areas (each MUST be touched in the report with file:line evidence)

For each focus area, either confirm correct ("Looks good" with file:line evidence) or flag under the appropriate severity. Pre-flagged HIGH-PROB items (§1.1, §1.2, §1.3 per `audit_preprep.md`) MUST receive paragraph-level discussion even if no defect is found.

1. **PyInstaller `--add-binary` for `_rust.cpython-313-darwin.so`.** [HIGHEST-IMPACT must-fix per `audit_preprep.md` §1.1]
   - Per spec §6.2 + §6.3 + §12.1: maturin produces `poker_solver/_rust.cpython-313-darwin.so`. PyInstaller's static analysis does **NOT** auto-discover dynamic extensions loaded via PyO3 (the import is wired at C-API level).
   - **Without `--add-binary`, the bundled `.app` launches successfully then crashes on the first call into Rust** — install succeeds, app appears to start, then dies on first solve.
   - **Pre-flagged failure modes** (auditor MUST probe each per `audit_preprep.md` §1.1):
     - (a) **`--add-binary` missing** — `scripts/build_macos_dmg.sh` PyInstaller invocation lacks the flag. Must-fix.
     - (b) **In-bundle smoke test missing** — after PyInstaller produces the `.app`, the build script must run the bundled python with `from poker_solver import _rust; print(_rust)` and fail the build on `ImportError`. Per spec §6.3 + §12.1 mitigation #2. Should-fix (the `.app` may still work but failure surfaces post-install).
     - (c) **`--add-binary` syntax wrong** — colon-separated `src:dest`. The dest path is the relative `.app` bundle location (`poker_solver`), not absolute. A typo or wrong dest path bundles the `.so` to the wrong location → silent import failure. Must-fix.
   - **Evidence stub:** `scripts/build_macos_dmg.sh:?` — exact `--add-binary "poker_solver/_rust.cpython-313-darwin.so:poker_solver"` literal + post-build smoke step.

2. **Code-signing optionality (signed + unsigned paths independent).** [HIGH-PROB must-fix per `audit_preprep.md` §1.2]
   - Per spec §6.7 + §11 #6 + `audit_preprep.md` §1.2: `./scripts/build_macos_dmg.sh --skip-signing --skip-notarization` MUST produce a working unsigned `.app` + `.dmg` without any Apple credentials. This is what runs on CI (no Apple credentials available there).
   - **Pre-flagged failure modes** (auditor MUST probe each):
     - (a) **Hard dependency on signing** — `set -e` and script dies on missing `Developer ID Application` cert or `$APPLE_ID` env var even with skip flags. User gets confusing error instead of a working unsigned build. Must-fix.
     - (b) **`--skip-signing` flag not threaded through** — script accepts flag but `sign_and_notarize.py` invoked unconditionally and dies. Must-fix.
     - (c) **Committed credentials** — per spec §6.4 + §6.5. Grep new files for `Developer ID Application: [A-Z]`, email patterns, password-like strings, team IDs. ANY hit → must-fix (security blocker).
   - **Evidence stub:** `scripts/build_macos_dmg.sh:?` — `--skip-signing` branch + grep result for credentials.

3. **DMG notarization (arm64-only + inside-out signing walk).** [pre-flagged should-fix per `audit_preprep.md` §1.3]
   - Per spec §6.4 + §11 + `audit_preprep.md` §1.3.
   - **Pre-flagged failure modes** (auditor MUST probe each):
     - (a) **Universal2 leakage** — arm64-only is locked (PLAN.md "MacBook-only, 16 GB Apple Silicon"; spec §1.2 non-goal). DMG filename: `Poker-Solver-${VERSION}-arm64.dmg`. If PyInstaller is invoked without arch flag, host setup may produce universal2 → larger DMG + violates arm64-only commitment. Should-fix.
     - (b) **`codesign --deep` unreliability** — Apple's `--deep` flag claims to walk PyInstaller bundles but is documented-unreliable. `scripts/sign_and_notarize.py` MUST do an explicit `find Contents -name "*.dylib" -o -name "*.so"` walk, sign each inner binary with the Developer ID + Hardened Runtime, then sign the outer `.app`. Missing the inside-out walk → notarization may pass but Gatekeeper or runtime-attached verification fails at user launch. Should-fix.
     - (c) **Hardened Runtime not enabled** — `--options runtime` missing on signature steps. Should-fix.
   - **Evidence stub:** `scripts/sign_and_notarize.py:?` — explicit walk + Hardened Runtime; `scripts/build_macos_dmg.sh:?` — DMG filename + arch flag.

4. **SQLite WAL mode for concurrency.** [LOW-PROB but must-fix-band per `audit_preprep.md` §1.4]
   - Per spec §2.2 + §11 #3: `PRAGMA journal_mode = WAL` is the load-bearing concurrency setting. WAL allows multiple readers while one writer writes — required for the UI library browser + batch_solve concurrency.
   - **Pre-flagged failure modes** (auditor MUST probe each):
     - (a) **PRAGMA missing** — default journal mode is `DELETE` (rollback journal). Concurrent reader during write → `database is locked` error. Must-fix.
     - (b) **PRAGMA set on wrong connection** — must be set on every `Library.open()` (per `agent_a_prompt.md` line 51), not just the first connection. SQLite WAL is per-database-file persistent once set, but defensive re-set ensures safety. Should-fix.
     - (c) **Foreign keys OFF** — `PRAGMA foreign_keys = ON` is a separate pragma; required for schema integrity if the schema uses foreign keys. Should-fix.
   - Tested: `test_library_concurrent_readers_dont_corrupt` (§9 #12).
   - **Evidence stub:** `library_schema.sql:?` or `poker_solver/library.py:?` — PRAGMA setup.

5. **Spot ID deterministic across runs and machines.**
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
   - **Evidence stub:** `poker_solver/library.py:?` — `_canonicalize_spot()` + `spot_id()`.

6. **gzip-6 compression roundtrip preserves bit-exact strategies.** [LOW-PROB but must-fix-band per `audit_preprep.md` §1.5]
   - Per spec §2.4 + §11 #4: `gzip.compress(json_bytes, compresslevel=6)` (default level). The bit-exact contract is critical: `gzip` → `gunzip` → JSON parse → values comparing `==` to source (NOT `np.allclose`).
   - **Pre-flagged failure modes** (auditor MUST probe each):
     - (a) **Anti-pattern: `np.allclose` in roundtrip test** — passes tests but silently allows precision drift. Per audit focus area explicit anti-pattern check: "if the roundtrip test uses `np.allclose` instead of `np.array_equal`, flag." Must-fix (silent precision loss is a strategy display corruption vector).
     - (b) **Wrong compresslevel** — level=9 slower with marginal gain; level=1 faster with significant size cost. Spec locks level=6. Drift → should-fix.
     - (c) **JSON serialization not deterministic** — `json.dumps(..., sort_keys=True, separators=(",", ":"))` is the locked form. Non-deterministic dict ordering → non-reproducible compressed bytes. Should-fix.
   - Tested: `test_library_compression_preserves_bit_exact_strategy` (§9 #11) — `SolveResult` with carefully chosen float values (0.0, 1.0, 1e-15, 1-1e-15); `put`/`get` roundtrip; assert every probability vector is `np.array_equal`.
   - **Evidence stub:** `tests/test_library.py:?` — verify `np.array_equal` (NOT `np.allclose`) is used.

7. **Schema-version hard-error path.** [LOW-PROB but must-fix-band per `audit_preprep.md` §1.6]
   - Per spec §11 #8 + §2.5: `schema_version` mismatch → **hard error** (`LibrarySchemaError`). `solver_version` mismatch → **soft warning** (`UserWarning`). Spec §3.1 `get()` docstring.
   - **Pre-flagged failure modes** (auditor MUST probe each):
     - (a) **Silent migration on schema-version mismatch** — opening an old `library_version=1` library from a `library_version=2` codebase silently uses defaults. User loses data without warning. Must-fix.
     - (b) **`solver_version` mismatch hard-errors** — too aggressive; should be a warning per spec. Should-fix.
     - (c) **`LibrarySchemaError` not in `__init__.py`** — exception isn't importable from `poker_solver`. UI can't catch it cleanly. Should-fix.
   - Tested: `test_library_schema_version_mismatch_errors` (§9 #15) — manually insert `library_version=999` in `spots_meta`; open; expect `LibrarySchemaError`.
   - **Evidence stub:** `poker_solver/library.py:?` — schema-version check + exception raise.

8. **No Apple Developer credentials in committed files.**
   - Per spec §6.4 + §6.5: signing requires `Developer ID Application: NAME (TEAMID)`, notarization requires `$APPLE_ID`, `$TEAM_ID`, `$APP_SPECIFIC_PASSWORD`. These MUST be env vars from the user's shell — **NEVER committed**.
   - Grep new files for any string matching `Developer ID Application: [A-Z]`, email patterns, password-like strings, team IDs:
     ```sh
     grep -rEi 'apple_id|team_id|app_specific_password|developer id application' scripts/ poker_solver/ assets/
     ```
   - Exclude generic references in docstrings; flag any literal credentials.
   - `scripts/entitlements.plist` is committed but contains only entitlements (not credentials).
   - **Evidence stub:** grep output (expect zero literal credentials).

9. **No new runtime dependencies.**
   - Per spec §1 non-goals + §11 #10: SQLite, gzip, hashlib, json are stdlib. NO new runtime deps.
   - PyInstaller added under `[project.optional-dependencies] distribution`. **NOT in base `dependencies`.**
   - Verify `pyproject.toml` `[project.dependencies]` is unchanged.
   - **Evidence stub:** `git diff integration -- pyproject.toml` — verify only optional-deps `distribution` group added.

10. **PyInstaller `--onedir` not `--onefile`.**
    - Per spec §6.3 + §13 #8: `--onedir` recommended over `--onefile` for `.app` bundles. `--onefile` "requires unpacking on each run" and breaks code-signing of inner files.
    - Verify the build script uses `--onedir`.
    - **Evidence stub:** `scripts/build_macos_dmg.sh:?` — PyInstaller invocation line.

11. **CLI subcommand surface.**
    - Per spec §8 + §11 (CLI surface focus area): `poker-solver library list|get|put|export|import|delete|stats` + `poker-solver batch-solve --input <csv>`.
    - List output: tab-separated by default; `--json` flag for machine-readable.
    - Library file location respects `POKER_SOLVER_LIBRARY_PATH` env var (per §11 #11) + `--library-path` flag.
    - **Evidence stub:** `poker_solver/cli.py:?` — subcommand registration.

12. **Idempotent batch-solve.**
    - Per spec §5.4 + §11 #9: re-running same CSV after a crash is a no-op for already-saved spots (via `Library.get` skip).
    - Implementation: for each CSV row, compute `spot_id`, check `Library.get(spot_id)`, skip if non-None. Print `[SKIP]` / `[OK]` / `[OOM]` / `[ERROR]` lines.
    - **Evidence stub:** `scripts/batch_solve.py:?` — main loop with skip logic.

13. **Library viewer UI integration (PR 10 stub → real loader).**
    - Per spec §4.1: PR 10 left a stub at `ui/views/library_browser.py`. PR 11 grows it into a real loader.
    - Page registration follows PR 10's convention.
    - Filter form, sortable table of `SpotMetadata`, per-row actions (Load, Export, Delete), footer with `LibraryStats`.
    - `Library.get` calls offloaded to `asyncio.to_thread` (avoids blocking UI on gzip decode). Per §4.5.
    - **Evidence stub:** `ui/views/library_browser.py:?` — page registration + handlers.

14. **Export/import portability.**
    - Per spec §11 #12: spot exported on Machine A imports correctly on Machine B. Format is JSON (uncompressed, human-inspectable). No machine-specific paths in the export.
    - Tested: `test_library_export_import_roundtrip` (§9 #10) — `export`, `delete`, `import_`, `get` returns equivalent `SolveResult`.
    - **Evidence stub:** `poker_solver/library.py:?` — `export()` + `import_()` methods.

15. **Test count (~15 library tests per spec §9).**
    - Per spec §9: ~15 library tests covering schema, WAL, spot ID determinism, compression, schema-version mismatch, export/import, CLI, batch-solve idempotency, concurrent readers, UI integration stub.
    - **Evidence stub:** `tests/test_library.py:?` + `tests/test_library_cli.py:?` + `tests/test_library_ui_integration.py:?` — count test functions.

## Output format

Write your report to `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/audit_report.md` with this exact structure:

```markdown
# PR 11 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-11-library-and-packaging
**Diff size:** [N modified + M new files = ±X LoC total]

**Test status:** [pytest tests/test_library*.py — pass/fail; full suite delta. Note: build_macos_dmg.sh may or may not have been run.]

## Must-fix

[`--add-binary` missing for `_rust.so` (bundle crashes at runtime); `--skip-signing` path broken; committed Apple credentials; WAL mode missing; compression uses `np.allclose` not `np.array_equal`; spot ID not deterministic; new runtime dep added; `--onefile` used instead of `--onedir`; schema-version mismatch doesn't error. Each: file:line + what + fix.]

[If none: "None found." + justification.]

## Should-fix

[Missing PyInstaller in-bundle smoke step; inside-out signing walk incomplete; universal2 leakage (no explicit arm64); CLI subcommand surface flag gaps; idempotent batch-solve test holes; `LibrarySchemaError` not re-exported. Each: file:line + description + fix.]

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

- **must-fix:** `--add-binary` missing (bundle crashes on first Rust call), `--skip-signing` path broken, committed Apple credentials, WAL mode missing, compression uses `np.allclose`, spot ID non-deterministic, new runtime dep added, `--onefile` used, schema-version mismatch silent. Blocks PR.
- **should-fix:** missing in-bundle smoke step, inside-out signing walk incomplete, universal2 leakage (no explicit arm64 flag), CLI flag gaps, `LibrarySchemaError` not re-exported, test holes. Doesn't block.
- **nice-to-fix:** style, comments. Pure polish.

When in doubt: anything that breaks the user's first run of the installed `.app` (silently or loudly) → must-fix. Developer-experience issues → should-fix.

## Procedural notes

- Cite **file paths and line numbers** for every finding.
- Quote spec section numbers, especially §6.2/6.3 (PyInstaller + `--add-binary`), §6.7 (unsigned fallback), §11 #1/#3/#4/#8 (correctness).
- Spec-silent behavior → "Spec coverage gaps".
- Do not modify code. Audit only. Your only write is to `docs/pr11_prep/audit_report.md`.
- HIGH-PROB risk surfaces (focus areas 1, 2, 3 — and the three sub-probes in each) MUST get paragraph-level discussion even with no defect found.
- For credentials check: `grep -rEi 'apple_id|team_id|app_specific_password|developer id application' scripts/ poker_solver/ assets/` — exclude generic references in docstrings; flag any literal credentials.

Begin by reading the spec (especially §6 packaging + §12.1 PyInstaller risk), then the diff, then the new files. Then write the report.
