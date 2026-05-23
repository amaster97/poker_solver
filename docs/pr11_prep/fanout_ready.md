# PR 11 fan-out ready — pre-staged launch sequence

**Status:** PRE-STAGED. Do NOT execute until PR 10a (or PR 10b) has merged to `integration`.

**Last verified:** 2026-05-22. Launch-readiness verdict READY (8/8 checks PASS) per `launch_readiness.md`; D1 SQLite WAL + D2 SHA-256 spot ID + D3 gzip-6 + D6 arm64-only + D8 PyInstaller `--onedir` + D9 explicit save + D13.1 Apple Developer optional all locked-with-default per `pr11_spec.md` §13; PyInstaller `--add-binary "poker_solver/_rust.cpython-313-darwin.so:poker_solver"` is the top-risk mitigation (spec §12.1).

This doc collapses `launch_kickoff.md` into the fire-when-PR-10-lands order. Authoritative kickoff: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/launch_kickoff.md`. This file is the operational shortlist.

---

## 1. Pre-flight gate (run AFTER PR 10a or PR 10b lands, BEFORE branch creation)

All six must pass. If any fails, stop and resolve.

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. PR 10a (or PR 10b) merged to integration.
git fetch origin
git log --oneline integration -5
# Expected: "Integration: merge PR 10a (ui-mock-first)" or
# "Integration: merge PR 10b (ui-real-solver)" reachable. If neither is landed,
# do not launch PR 11 — the library viewer stub at ui/views/library_browser.py
# is required by the UI integration sub-task.
git rev-parse integration; git rev-parse origin/integration   # must be equal

# 1b. working tree clean.
git status

# 1c. PR 11 prompts up to date; launch-readiness verdict READY.
ls docs/pr11_prep/    # expect: pr11_spec.md, agent_{a,b,c}_prompt.md, audit_prompt.md, launch_readiness.md, launch_kickoff.md, fanout_ready.md
grep -n "READY" docs/pr11_prep/launch_readiness.md
# Expected: verdict line confirming "READY" (8/8 PASS). Do NOT launch on a stale verdict.

# 1d. PR 10a library stub present (UI integration target, not touched by Agents A/B/C).
test -f ui/views/library_browser.py && echo "PR 10a library stub present" \
  || echo "WARNING: PR 10a library stub missing — UI integration sub-task blocked"

# 1e. `_rust.so` exists locally so Agent B's PyInstaller smoke step has something to bundle.
# (maturin develop should have been run at PR 6 merge; verify still present.)
ls poker_solver/_rust.cpython-*-darwin.so 2>/dev/null || echo "WARNING: run maturin develop --release before Agent B's build step"

# 1f. integration green from its tip (smoke before adding ~1000+ LOC of library + packaging).
pytest -x -q

# 1g. Reflog backup (per runbook §0).
git rev-parse integration > /tmp/integration_pre_pr_11.hash
```

---

## 2. Branch creation

```sh
cd /Users/ashen/Desktop/poker_solver
git checkout integration
git pull --ff-only origin integration
git checkout -b pr-11-library-and-packaging integration
git status   # expect: clean tree on pr-11-library-and-packaging
```

Branch name hard-coded in `audit_prompt.md` — do NOT improvise.

---

## 3. Three-agent fan-out launch (SAME tool-call wave)

For each agent, copy the **body of the prompt file between the two `---` markers** verbatim. Do NOT paraphrase the header.

```
Agent A — "PR 11 Agent A — Library module + SQLite schema + CLI integration"
  prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr11_prep/agent_a_prompt.md between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true

Agent B — "PR 11 Agent B — macOS packaging (PyInstaller + codesign + notarize + .dmg)"
  prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr11_prep/agent_b_prompt.md between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true

Agent C — "PR 11 Agent C — library tests + batch_solve.py + CLI smoke tests"
  prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr11_prep/agent_c_prompt.md between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true
```

**Ownership lock (do NOT relax):**

| Agent | Owns | Surgical edit | Forbidden |
|---|---|---|---|
| A | `poker_solver/library.py`, `poker_solver/library_schema.sql` | `poker_solver/__init__.py` (re-exports), `poker_solver/cli.py` (new subcommands) | any packaging script, any test, any UI file, `dcfr.py`, `hunl_solver.py`, profiler |
| B | `scripts/build_macos_dmg.sh`, `scripts/sign_and_notarize.py`, `scripts/entitlements.plist`, `scripts/poker_solver.spec` (optional), `assets/poker_solver.icns`, `assets/README.md` | `pyproject.toml` (additive: `[project.optional-dependencies] distribution = ["pyinstaller>=6.0"]`); optionally `README.md` (append-only) | library code, tests, CLI, UI |
| C | `tests/test_library.py`, `tests/test_library_cli.py`, `tests/test_library_ui_integration.py` (stub), `scripts/batch_solve.py`, `examples/tiny_csv.csv` | `scripts/check_pr.sh` (extend test command only) | any non-test, non-batch-solve file |

**Locked defaults each agent inherits (`pr11_spec.md` §13 — agents follow literally, do NOT re-debate):** D1 SQLite WAL (one writer + many readers); D2 SHA-256 spot ID via 7-rule canonicalization (`pr11_spec.md` §2.3); D3 gzip compresslevel=6 with bit-exact roundtrip (`np.array_equal`, NOT `np.allclose`); D6 arm64-only DMG; D8 PyInstaller `--onedir` (NOT `--onefile`); D9 explicit `library.save()` (no auto-population from UI solves); D13.1 Apple Developer optional (`--skip-signing --skip-notarization` produces a working unsigned `.app` + documented Gatekeeper bypass).

While A/B/C run, fan out parallel work (PR 12 spec polish if planned, autonomous-log pruning, doc inventory sweep post-PR-10 merge, PLAN.md trajectory consistency check) per parallel-agents-default memory.

---

## 4. Expected outputs + timeline

**Wall-clock:** ~3-5 hours (A: ~90-150 min on SQLite schema + canonicalization + CLI; B: ~120-180 min on PyInstaller invocation + inside-out signing walk + DMG; C: ~60-90 min on library tests + batch_solve + CLI smokes; concurrent).

**Deliverables (PR surface):**
- `poker_solver/library.py` + `poker_solver/library_schema.sql` (SQLite WAL, SHA-256 ID, gzip-6 blobs)
- `poker_solver/__init__.py` re-exports + `poker_solver/cli.py` library subcommands (`library list/get/save/export/import`)
- `scripts/build_macos_dmg.sh` (idempotent, `--skip-signing --skip-notarization` fallback functional)
- `scripts/sign_and_notarize.py` + `scripts/entitlements.plist` + `scripts/poker_solver.spec` (optional)
- `assets/poker_solver.icns` + `assets/README.md` (Gatekeeper bypass instructions)
- `tests/test_library.py` + `tests/test_library_cli.py` + `tests/test_library_ui_integration.py` (stub) + `scripts/batch_solve.py` + `examples/tiny_csv.csv`
- `pyproject.toml` (`[project.optional-dependencies] distribution = ["pyinstaller>=6.0"]`)

**Medium-large PR:** ~1500-2500 LOC net add; two new poker_solver modules + ~5 packaging scripts; no edits to `dcfr.py`, `hunl_solver.py`, profiler, UI views.

**Pass criteria:** all existing tests still pass; library tests pass; `./scripts/build_macos_dmg.sh --skip-signing --skip-notarization` produces a working unsigned `.app` whose in-bundle smoke step imports `_rust` successfully; DMG size <200 MB (soft); ruff/black/mypy-strict clean on new files.

---

## 5. Top-risk mitigation reminder (Agent B critical path)

PyInstaller's AST walker does NOT find `_rust.cpython-313-darwin.so` (PyO3 wires the import at C-API level). Without explicit `--add-binary`, the bundled `.app` launches then crashes on the first Rust call. Agent B's three-part defense: (1) `--add-binary "poker_solver/_rust.cpython-313-darwin.so:poker_solver"` in the PyInstaller invocation; (2) post-PyInstaller in-bundle smoke test that imports `_rust` headlessly; (3) documented failure mode. Audit focus area 4 probes this by hypothetically omitting `--add-binary` and asserting the smoke catches it. Spec §6.3 + §12.1 are canonical.

---

## 6. Post-fan-out: audit + commit

Per `launch_kickoff.md` §5: after all three agents return, run interface-drift reconciliation (`pytest tests/test_library.py tests/test_library_cli.py -xvs`) + audit + check battery in same parallel wave.

PR-11-specific must-fix triggers: `PRAGMA journal_mode = WAL` missing; `_compute_spot_id` non-deterministic across reordered inputs; compression uses `np.allclose` (silent precision loss); `--add-binary` for `_rust.so` missing OR in-bundle smoke absent (bundle crashes at runtime); Apple credentials committed (any literal Developer ID, Apple ID, password, or Team ID); new runtime dep added to `[project.dependencies]` (must stay in `[project.optional-dependencies] distribution`); PyInstaller `--onefile` instead of `--onedir` (breaks code-signing of inner files); `LibrarySchemaError` not raised on schema-version mismatch; `--skip-signing --skip-notarization` path broken.

Commit explicit paths: `git add poker_solver/ scripts/ assets/ tests/ examples/ pyproject.toml docs/pr11_prep/audit_report.md`. Never `git add -A`. Verify `dist/`, `.dmg`, `.app` artifacts NOT staged. Push `pr-11-library-and-packaging`; `--no-ff` merge into `integration`; update `PLAN.md` trajectory + `docs/autonomous_log.md` (include final DMG size).

Full pipeline lives in `launch_kickoff.md` §5a-5f. This doc stops at fan-out launch.
