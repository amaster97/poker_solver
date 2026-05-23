# PR 11 launch — fire now (2026-05-22)

**Status:** READY TO FIRE pending working-tree cleanup. Fan-out fires the moment `git status --short` returns empty.
**Target milestone:** **v1.0.0 GA** (MAJOR version bump — the v1 ship).
**Predecessor:** PR 10a merged to `integration` at tip `b880032`. Launch-readiness verdict READY per `launch_readiness_v2.md` (5/5 v2 checks PASS + 8/8 v1 spec checks PASS).
**Authoritative source:** `launch_invocations.md` + `launch_kickoff.md`. This doc is the day-of fire-sheet.

---

## 1. Pre-flight verification (orchestrator runs these in order)

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. Working tree must be clean. The user-fixture-revert agent is concurrent;
# do NOT branch until git status --short returns empty.
git status --short
# Expected: (no output). If unstaged edits remain, WAIT.

# 1b. Sync integration from origin.
git fetch origin
git checkout integration
git pull --ff-only origin integration

# 1c. Confirm tip = b880032 (PR 10a merge).
git rev-parse integration
# Expected: b880032c728466759984746ce68fc7d58852ae34

# 1d. Reflog backup.
git rev-parse integration > /tmp/integration_pre_pr_11.hash

# 1e. PR 10a UI library stub present (UI integration target).
test -f ui/views/library_browser.py && echo "stub present" || echo "BLOCKED"

# 1f. Rust .so present locally (Agent B bundles it).
ls poker_solver/_rust.cpython-*-darwin.so

# 1g. Branch pr-11-library-and-packaging does NOT yet exist.
git branch --list pr-11-library-and-packaging   # expect empty

# 1h. All four prompts present.
ls docs/pr11_prep/agent_{a,b,c}_prompt.md docs/pr11_prep/audit_prompt.md

# 1i. Tip smoke test green before adding ~1500-2000 LOC.
pytest -x -q

# 1j. Create the branch.
git checkout -b pr-11-library-and-packaging
git status --short   # expect: clean tree on pr-11-library-and-packaging
git log --oneline -1 # expect: PR 10a merge commit b880032
```

All ten checks must pass. Branch name `pr-11-library-and-packaging` is hard-coded in `audit_prompt.md` — do NOT improvise.

---

## 2. Three-agent fan-out (SAME tool-call wave, `run_in_background: true`)

For each agent, copy the **body of the prompt file between the two `---` markers** verbatim. Do NOT paraphrase the header.

- **Agent A** — "PR 11 Agent A — Library module + SQLite schema + CLI integration"
  - prompt: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/agent_a_prompt.md`
  - owns: `poker_solver/library.py`, `poker_solver/library_schema.sql`; surgical: `__init__.py` re-exports, `cli.py` subcommands
  - locked defaults: D1 SQLite WAL (every connection open), D2 SHA-256 spot ID via 7-rule canonicalization, D3 gzip compresslevel=6 + bit-exact roundtrip (`np.array_equal`, NOT `np.allclose`), D9 explicit `library.save()`

- **Agent B** — "PR 11 Agent B — macOS packaging (PyInstaller + codesign + notarize + .dmg)"
  - prompt: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/agent_b_prompt.md`
  - owns: `scripts/build_macos_dmg.sh`, `scripts/sign_and_notarize.py`, `scripts/entitlements.plist`, `scripts/poker_solver.spec` (optional), `assets/poker_solver.icns`, `assets/README.md`; surgical: `pyproject.toml` (`[project.optional-dependencies] distribution = ["pyinstaller>=6.0"]`)
  - locked defaults: D6 arm64-only, D8 PyInstaller `--onedir` (NOT `--onefile`), D13.1 Apple Developer optional (`--skip-signing --skip-notarization` produces working unsigned `.app`)
  - **mandatory flag:** `--add-binary "poker_solver/_rust.cpython-313-darwin.so:poker_solver"`

- **Agent C** — "PR 11 Agent C — library tests + batch_solve.py + CLI smoke tests + library integration"
  - prompt: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/agent_c_prompt.md`
  - owns: `tests/test_library.py`, `tests/test_library_cli.py`, `tests/test_library_ui_integration.py` (stub), `scripts/batch_solve.py`, `examples/tiny_csv.csv`; surgical: `scripts/check_pr.sh` (test command only)

Zero file overlap. Ownership lock per `launch_invocations.md` §3 — do NOT relax. While A/B/C run, fan out parallel work per parallel-agents-default + min-five-agents rules: PR 12 spec polish, `docs/autonomous_log.md` pruning, doc inventory sweep, PLAN.md trajectory consistency check.

---

## 3. Critical risks (ranked)

1. **PyInstaller silently dropping `_rust.so`** (TOP RISK — spec §12.1). PyInstaller's AST walker does NOT find PyO3-loaded `.so` files; without `--add-binary` the bundled `.app` launches then crashes on the first Rust call. Three-part defense: explicit flag + post-PyInstaller in-bundle headless smoke (`from poker_solver import _rust`) + documented failure mode. Audit focus area 1 probes by hypothetically omitting the flag.
2. **Code-signing chain optionality.** `--skip-signing --skip-notarization` must produce a launchable `.app` with ZERO Apple env vars set. Flags must be independently respected (don't hard-couple `--skip-notarization` to `--skip-signing`). `entitlements.plist` contains only entitlement keys — NEVER a literal Developer ID, Apple ID, password, or Team ID. Audit focus area 8: grep sweep for credential leaks is a hard must-fix.
3. **DMG notarization for arm64-only.** D6 lock — Universal2 deferred. `create-dmg` excludes `unittest|idlelib|turtle|tkinter` to keep DMG <200 MB (~165 MB empirical). Inside-out codesign walk (`find Contents -name "*.dylib" -o -name "*.so"`) with `--options runtime` on every call (Hardened Runtime); do NOT rely on `--deep`. notarytool integration via `xcrun notarytool submit --wait`.

Secondary: SQLite WAL fallback (`PRAGMA journal_mode = WAL` return-value check), spot ID float-repr drift (`round(x, 6)` on bet-menu fractions), `LibrarySchemaError` loud-raise on forward incompatibility, no new runtime deps in `[project.dependencies]`.

---

## 4. Expected wall-clock: ~6-8 hours

- Agent A: ~120-150 min (schema + WAL + spot ID + bit-exact compression + CLI subcommands)
- Agent B: ~120-180 min (PyInstaller + inside-out signing + notarytool + create-dmg + unsigned fallback)
- Agent C: ~90-120 min (library tests + determinism probes + roundtrip + batch_solve + smokes)
- Concurrent: ~2-3 hours fan-out
- Audit + check battery + reconciliation: ~60-90 min (DMG build + in-bundle smoke is slow)
- Commit + `--no-ff` merge: ~10 min

Net add: ~1500-2000 LOC; two new `poker_solver/` modules + ~5 packaging scripts + 2-3 test files; no edits to `dcfr.py`, `hunl_solver.py`, profiler, or UI views.

---

## 5. Post-fan-out: audit + commit pipeline → v1.0.0 GA

After all three agents return:

1. **Interface-drift reconciliation:** `pytest tests/test_library.py tests/test_library_cli.py -xvs`.
2. **Build smoke (optional, ~5-10 min):** `bash scripts/build_macos_dmg.sh --skip-signing --skip-notarization` — verifies `.app` launches and in-bundle smoke imports `_rust`.
3. **Check battery + audit in parallel.** Audit prompt: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/audit_prompt.md` (writes `docs/pr11_prep/audit_report.md`). `must-fix` items are hard stop; `should-fix`/`nice-to-fix` deferrable with TODO.
4. **Commit explicit paths only:** `git add poker_solver/ scripts/ assets/ tests/ examples/ pyproject.toml docs/pr11_prep/audit_report.md`. Verify `dist/`, `.dmg`, `.app`, `.env`, Apple credentials NOT staged. Commit message per `launch_kickoff.md` §5c.
5. **Push + `--no-ff` merge:** `git push -u origin pr-11-library-and-packaging` → `git merge --no-ff pr-11-library-and-packaging -m "Integration: merge PR 11 (library-and-packaging)"` into `integration` → push.
6. **Tag the v1 GA milestone:** `git tag -a v1.0.0 -m "v1.0.0 GA — library mode + macOS packaging"` on the `integration` tip post-merge. **This is the v1 ship.**
7. **Plan-sync:** update `PLAN.md` trajectory + `docs/autonomous_log.md` (record final DMG size + signed/unsigned status); `cp ~/.claude/plans/...md PLAN.md` per plan-sync rule. Spawn continuous-pruning agent.

---

## Quick-reference paths

- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/pr11_spec.md`
- Agent prompts: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/agent_{a,b,c}_prompt.md`
- Audit prompt: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/audit_prompt.md`
- Authoritative kickoff: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/launch_kickoff.md`
- Invocations: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/launch_invocations.md`
- Fan-out shortlist: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/fanout_ready.md`
- Launch-readiness v2: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/launch_readiness_v2.md`
- Reflog backup: `/tmp/integration_pre_pr_11.hash`
