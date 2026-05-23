# PR 11 launch invocations — copy-paste ready

**Status:** PRE-STAGED. Do NOT execute until PR 10a (or PR 10b) has merged to `integration` and the user has approved firing PR 11.

**Purpose:** the exact, copy-paste-ready set of operations to fire PR 11 (library mode + macOS packaging). Authoritative kickoff: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/launch_kickoff.md`. This file is the mechanical operations sheet — paste blocks in order.

---

## 1. Pre-launch verification (run AFTER PR 10a or PR 10b lands; BEFORE branch creation)

All six checks must pass. If any fails, stop and resolve before continuing.

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. PR 10a (or PR 10b) merged to integration.
git fetch origin
git log --oneline integration -5
# Expected topmost commit: "Integration: merge PR 10a (ui-scaffold)" OR
# "Integration: merge PR 10b (ui-real-solver-swap)". PR 11's library viewer
# extends the PR 10a UI library stub; if neither has landed, do not launch.

# 1b. integration tip matches origin/integration (zero divergence).
git rev-parse integration; git rev-parse origin/integration   # must be equal
# If divergent: git pull --ff-only origin integration

# 1c. Working tree clean.
git status   # expect "nothing to commit, working tree clean"

# 1d. Branch pr-11-library-and-packaging does NOT yet exist.
git branch --list pr-11-library-and-packaging
# Expected: empty output.

# 1e. All PR 11 prompts + audit prompt present (verdict READY).
ls docs/pr11_prep/agent_{a,b,c}_prompt.md docs/pr11_prep/audit_prompt.md
# Expected: 4 files present.

# 1f. Reflog backup + UI library stub presence check.
git rev-parse integration > /tmp/integration_pre_pr_11.hash
echo "integration tip pre-PR-11: $(cat /tmp/integration_pre_pr_11.hash)"
test -f ui/views/library_browser.py && echo "PR 10a library stub present" \
  || echo "WARNING: PR 10a library stub missing — UI integration blocked (PR 11 still ships per §13.13)"
```

Optional final sanity: `pytest -x -q` from the `integration` tip — must be green before branching.

---

## 2. Branch creation

Branch name `pr-11-library-and-packaging` is hard-coded in `docs/pr11_prep/audit_prompt.md` — do NOT improvise.

```sh
cd /Users/ashen/Desktop/poker_solver
git checkout integration
git pull --ff-only origin integration   # last sanity check
git checkout -b pr-11-library-and-packaging
git status   # expect: clean tree, on pr-11-library-and-packaging
git log --oneline -1   # expect: PR 10 merge commit
```

---

## 3. Three-agent fan-out launch (SAME tool-call wave)

All three implementation agents launch in the SAME tool-call block. They are independent — file-ownership boundaries locked inside each prompt. For each agent, the prompt is the **body of the corresponding prompt file between the two `---` markers** (NOT the orchestrator header above the first `---`). Copy verbatim.

```
Agent A — "PR 11 Agent A — Library module + SQLite schema + CLI integration"
  prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr11_prep/agent_a_prompt.md between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true

Agent B — "PR 11 Agent B — macOS packaging (PyInstaller + codesign + notarize + .dmg)"
  prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr11_prep/agent_b_prompt.md between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true

Agent C — "PR 11 Agent C — library tests + batch_solve.py + CLI smoke tests + library integration"
  prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr11_prep/agent_c_prompt.md between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true
```

**Ownership lock (do NOT relax):**

| Agent | Owns | Surgical edit | Forbidden |
|---|---|---|---|
| A | `poker_solver/library.py`, `poker_solver/library_schema.sql` | `poker_solver/__init__.py` (re-exports), `poker_solver/cli.py` (new subcommands) | any packaging script, any test file, any UI file, `dcfr.py`, `hunl_solver.py`, profiler |
| B | `scripts/build_macos_dmg.sh`, `scripts/sign_and_notarize.py`, `scripts/entitlements.plist`, `scripts/poker_solver.spec` (optional), `assets/poker_solver.icns`, `assets/README.md` | `pyproject.toml` (additive: `[project.optional-dependencies] distribution = ["pyinstaller>=6.0"]`); optionally `README.md` (append-only) | library code, tests, CLI, UI |
| C | `tests/test_library.py`, `tests/test_library_cli.py`, `tests/test_library_ui_integration.py` (stub), `scripts/batch_solve.py`, `examples/tiny_csv.csv` | `scripts/check_pr.sh` (extend test command only) | any non-test, non-batch-solve file |

**Parallel fan-out during runtime** (per parallel-agents-default + min-five-agents rules): launch independent downstream agents — PR 12 spec polish, `docs/autonomous_log.md` pruning, doc inventory sweep (cross-PR references after PR 10 merge), PLAN.md trajectory consistency check. Aggregate per wave.

---

## 4. Expected wall-clock: ~5-7 hours

Moderate PR — library API is contained but packaging surface is genuinely new (PyInstaller + codesign + notarize + DMG).
- Agent A: ~120-150 min (SQLite schema + WAL + deterministic spot ID + gzip-6 bit-exact compression + CLI subcommands).
- Agent B: ~120-180 min (PyInstaller `--add-binary` + inside-out codesign walk + notarytool integration + create-dmg + unsigned-fallback path).
- Agent C: ~90-120 min (library tests + spot ID determinism probes + bit-exact roundtrip + batch_solve.py + CLI smoke tests).
- Concurrent execution: ~2-3 hours wall-clock for fan-out itself.
- Audit + check battery + reconciliation: ~60-90 min (DMG build + in-bundle smoke test takes time).
- Commit + merge: ~10 min.

**Deliverables (PR surface):** ~1500-2000 LOC net add; new `poker_solver/library.py` + schema SQL; new `scripts/build_macos_dmg.sh` + `sign_and_notarize.py` + `entitlements.plist`; assets dir (`.icns` + README); 2-3 new test files + smoke harness; `examples/tiny_csv.csv` + `scripts/batch_solve.py`; pyproject optional-dependencies entry. **DMG size target: <200 MB (~165 MB empirical).**

---

## 5. Risk reminders specific to PR 11

- **PyInstaller `_rust.so` bundling (load-bearing — spec §12.1).** PyInstaller's AST walker does NOT find PyO3-loaded `.so`. `--add-binary "poker_solver/_rust.cpython-313-darwin.so:poker_solver"` is mandatory. Three-part defense: flag + post-build in-bundle smoke test + documented failure mode. Audit must-fix if `--add-binary` missing or smoke test absent.
- **Code-signing + Apple Developer optionality.** `--skip-signing --skip-notarization` must produce a launchable `.app` with NO Apple env vars set. Flags must be independently respected. `entitlements.plist` contains only entitlement keys, NEVER literal Developer IDs.
- **Spot ID determinism.** SHA-256 over canonicalized JSON. 7 rules per spec §2.3: board sort, int-cent stacks, bet-menu sort, ranges sort, antes/rake included, hyperparameters excluded, `json.dumps(sort_keys=True, separators=(",", ":"))`. Bet-menu fractions need stable string representation (e.g., `round(x, 6)`) — float repr drift across Python versions corrupts cross-machine reuse.
- **Compression bit-exact roundtrip.** `np.array_equal`, NOT `np.allclose`. gzip compresslevel=6 (locked default; level 9 is also bit-exact but breaks test). `tolist()` on numpy arrays before `json.dumps`.
- **SQLite WAL mode.** `PRAGMA journal_mode = WAL` on EVERY connection open. Verify return value — if filesystem doesn't support WAL, falls back silently to rollback-journal. Concurrent reads break without WAL.
- **Schema migration loud-error.** Forward incompatibility (v2 DB opened by v1 code) MUST raise `LibrarySchemaError`. Silent open = silent data corruption.
- **No new runtime deps.** PyInstaller goes in `[project.optional-dependencies] distribution`, NOT `[project.dependencies]`. Audit must-fix if added to base deps.
- **PyInstaller `--onedir`, NOT `--onefile`.** `--onefile` breaks code-signing of inner files.
- **No committed Apple credentials.** No literal Developer ID, Apple ID, password, or Team ID in `scripts/` or `assets/`. Audit focus area 6 catches this.
- **DMG size soft constraint <200 MB.** `--exclude-module unittest|idlelib|turtle|tkinter` mandatory. `pyi-archive_viewer` to inspect bloat if exceeded.
- **Inside-out codesign walk.** Don't rely on `--deep`; use `find Contents -name "*.dylib" -o -name "*.so"` explicit walk per spec §6.4. `--options runtime` on every codesign call (Hardened Runtime).

---

## 6. Post-fan-out: audit + commit

Per `launch_kickoff.md` §5a-5e. After all three agents return:

```sh
cd /Users/ashen/Desktop/poker_solver

# 6a. Interface drift reconciliation.
pytest tests/test_library.py tests/test_library_cli.py -xvs
# Agent B's packaging output is exercised separately via build script; tests don't depend on .app.
# Optionally: run a build smoke test (~5-10 min):
bash scripts/build_macos_dmg.sh --skip-signing --skip-notarization

# 6b. Check battery + audit agent in parallel.
sh /Users/ashen/Desktop/poker_solver/scripts/check_pr.sh > /tmp/check_pr_output.log 2>&1
# Concurrently launch audit agent:
#   Audit — "PR 11 audit — fresh reviewer, no implementation context"
#     prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr11_prep/audit_prompt.md between the `---` markers>
#     subagent_type: general-purpose; run_in_background: true
# Audit writes to docs/pr11_prep/audit_report.md.

# 6c. Commit (explicit paths only — no git add -A).
git status   # verify staged set; CRITICAL: no .env / Apple credentials / dist/ / .dmg / .app artifacts
git add poker_solver/ scripts/ assets/ tests/ examples/ pyproject.toml docs/pr11_prep/audit_report.md
git status   # re-verify; ensure dist/ excluded
git commit -m "PR 11: library mode + macOS packaging"   # full message in launch_kickoff.md §5c

# 6d. Push + --no-ff merge into integration.
git push -u origin pr-11-library-and-packaging
git checkout integration
git pull --ff-only origin integration
git merge --no-ff pr-11-library-and-packaging -m "Integration: merge PR 11 (library-and-packaging)"
git push origin integration

# 6e. Update PLAN.md trajectory + docs/autonomous_log.md per plan-sync rule.
# Record final DMG size in autonomous_log entry.
```

`must-fix` audit items are a hard stop. `should-fix` / `nice-to-fix` can defer to a follow-up with a TODO. Full failure-mode + recovery patterns in `launch_kickoff.md` §6.

---

## 7. Quick-reference paths

- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/pr11_spec.md`
- Agent prompts: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/agent_{a,b,c}_prompt.md`
- Audit prompt: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/audit_prompt.md`
- Kickoff (authoritative): `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/launch_kickoff.md`
- Fan-out shortlist: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/fanout_ready.md`
- Launch-readiness verdict: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/launch_readiness.md` (READY — 8/8 PASS)
- This file (operational ready-to-paste): `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/launch_invocations.md`
- PR 10a UI library stub (extension target): `/Users/ashen/Desktop/poker_solver/ui/views/library_browser.py`
- Reflog backup: `/tmp/integration_pre_pr_11.hash`
