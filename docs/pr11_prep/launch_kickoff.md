# PR 11 launch kickoff — Library mode + macOS packaging

**Status:** PRE-STAGED PLAYBOOK. Do NOT execute until PR 10a (or PR 10b) has merged to `integration` and the user has approved firing PR 11.

**Purpose:** the exact command sequence + agent fan-out the orchestrator runs when PR 10 lands and PR 11 is next on deck. This doc collapses §0–§8 of `docs/pr_launch_runbook.md` against the PR 11-specific shape into a single executable transcript so launch is mechanical, not improvisational.

**Branch:** `pr-11-library-and-packaging` (per `pr_launch_runbook.md` §"PR 11" + PLAN.md §1 "Per-PR feature branches from PR 3 onward").

**Inputs that govern this playbook:**
- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/pr11_spec.md`
- Agent prompts: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/agent_{a,b,c}_prompt.md`
- Audit prompt: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/audit_prompt.md`
- Launch-readiness verdict: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/launch_readiness.md` (READY — 8/8 checks PASS)
- Universal runbook: `/Users/ashen/Desktop/poker_solver/docs/pr_launch_runbook.md`

---

## 1. Pre-flight gate (run BEFORE branch creation)

All five checks must pass. If ANY fails, stop and resolve before continuing.

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. PR 10a (or PR 10b) is committed AND merged to integration.
git fetch origin
git log --oneline integration -5
# Expected: a recent commit "Integration: merge PR 10a (ui-scaffold)" or
# "Integration: merge PR 10b (ui-real-solver-swap)". PR 11's library viewer
# extends the PR 10a UI library stub; the stub MUST be on integration before
# PR 11's UI integration can grow into a real loader. If neither PR 10a nor
# PR 10b is landed, do not launch PR 11.

# 1b. integration tip matches origin/integration (zero divergence).
git rev-parse integration
git rev-parse origin/integration
# Both hashes must be equal. If not: `git pull --ff-only origin integration`
# from a clean working tree, then re-verify.

# 1c. Working tree clean.
git status
# Expected: "nothing to commit, working tree clean".
# If anything is staged/unstaged, resolve first (commit, stash, or discard
# per intent) — never branch from a dirty tree.

# 1d. All PR 11 prompts up to date (per launch_readiness.md verdict).
ls -la docs/pr11_prep/
# Expected files present:
#   pr11_spec.md (~785 lines)
#   agent_a_prompt.md
#   agent_b_prompt.md
#   agent_c_prompt.md
#   audit_prompt.md
#   launch_readiness.md (verdict: READY)
# If launch_readiness.md verdict is NOT "READY", re-run the readiness
# review before firing. Do NOT launch on a stale verdict.

# 1e. Confirm integration tip hash for the reflog backup (per runbook §0).
git rev-parse integration > /tmp/integration_pre_pr_11.hash
echo "integration tip pre-PR-11: $(cat /tmp/integration_pre_pr_11.hash)"

# 1f. Confirm ui/views/library_browser.py stub exists on integration (PR 10a
# leaves this as a stub; PR 11 Agent A documents it as an extension target,
# but Agent A does NOT touch ui/* — that wiring is folded into the broader
# PR 11 UI integration described in pr11_spec.md §4.1).
test -f ui/views/library_browser.py && echo "PR 10a library stub present" \
  || echo "WARNING: PR 10a library stub missing — PR 11 UI integration is blocked"
```

Optional sanity: `pytest -x -q` from `integration` tip — must be green before branching. If red, the PR 10 merge introduced a regression; investigate before launching PR 11.

---

## 2. Branch creation

Mechanical. Branch name is hard-coded in `audit_prompt.md` — do NOT improvise.

```sh
cd /Users/ashen/Desktop/poker_solver
git checkout integration
git pull --ff-only origin integration   # last sanity check
git checkout -b pr-11-library-and-packaging
git status   # expect: clean tree, on pr-11-library-and-packaging
git log --oneline -1  # expect: PR 10 merge commit
```

Branch convention rationale (PLAN.md §1 + runbook §"Per-PR specifics → PR 11"): every PR from PR 3 onward gets its own feature branch from `integration`, NOT `main`. `pr-11-library-and-packaging` is the exact spelling the audit prompt expects to see in `git diff integration...HEAD` cross-references.

---

## 3. Three-agent fan-out launch (parallel, same wave)

Per `pr_launch_runbook.md` §"Step 2": all three implementation agents launch in the SAME tool-call wave. They are designed to be independent — file-ownership boundaries are locked in each prompt.

For each agent, the prompt is the **full contents of the corresponding `docs/pr11_prep/agent_{a,b,c}_prompt.md` file between the two `---` markers** (NOT the orchestrator header above the first `---`). Do not paraphrase, do not truncate, do not inline — copy the file body verbatim.

**Launch sequence (orchestrator side, all three in one tool-call block):**

```
Agent tool call 1:
  description: "PR 11 Agent A — Library module + SQLite schema + CLI integration"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr11_prep/agent_a_prompt.md
           between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true

Agent tool call 2:
  description: "PR 11 Agent B — macOS packaging (PyInstaller + codesign + notarize + .dmg)"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr11_prep/agent_b_prompt.md
           between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true

Agent tool call 3:
  description: "PR 11 Agent C — library tests + batch_solve.py + CLI smoke tests"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr11_prep/agent_c_prompt.md
           between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true
```

**Ownership recap (verifies interface lock — do NOT relax these):**

| Agent | Owns (write/create) | May surgically modify | Forbidden |
|---|---|---|---|
| A | `poker_solver/library.py`, `poker_solver/library_schema.sql` | `poker_solver/__init__.py` (re-exports), `poker_solver/cli.py` (new subcommands) | any packaging script, any test file, any UI file, `dcfr.py`, `hunl_solver.py`, profiler |
| B | `scripts/build_macos_dmg.sh`, `scripts/sign_and_notarize.py`, `scripts/entitlements.plist`, `scripts/poker_solver.spec` (optional), `assets/poker_solver.icns`, `assets/README.md` | `pyproject.toml` (additive: `[project.optional-dependencies] distribution = ["pyinstaller>=6.0"]`); optionally `README.md` (append-only) | library code, tests, CLI, UI |
| C | `tests/test_library.py`, `tests/test_library_cli.py`, `tests/test_library_ui_integration.py` (stub), `scripts/batch_solve.py`, `examples/tiny_csv.csv` | `scripts/check_pr.sh` (extend test command only) | any non-test, non-batch-solve file |

**Parallel fan-out during agent runtime (per PLAN.md §5 + runbook §"Step 3"):** while A/B/C run, launch independent agents on downstream work so the orchestrator never idles. Candidates:
- PR 12 (or next planned PR) spec polish / consistency review.
- `docs/autonomous_log.md` housekeeping (prune stale entries per the continuous-pruning rule).
- Doc inventory sweep (check if any cross-PR references became stale after PR 10 merge).
- PLAN.md trajectory-table consistency check (post-PR-10).

Aggregate per wave — do NOT react agent-by-agent. Wait for all three implementation agents to return, then synthesize the result vector in one pass.

---

## 4. Monitor + reconciliation patterns

While agents run, the orchestrator does NOT block. Track agent completion via the standard background-task notification stream. Specific failure signatures to watch for in agent outputs:

### 4a. PyInstaller `_rust.so` bundling failure (LOAD-BEARING RISK — spec §12.1)

**Symptom:** Agent B's `./scripts/build_macos_dmg.sh --skip-signing --skip-notarization` smoke test fails with `ImportError: cannot import name '_rust' from 'poker_solver'` when running the bundled `.app` headlessly.

**Common causes for PR 11:**
- `--add-binary "poker_solver/_rust.cpython-313-darwin.so:poker_solver"` missing from the PyInstaller invocation (the most common bug — PyInstaller's AST walker doesn't find PyO3-loaded extensions).
- The source `.so` doesn't exist at build time (user forgot `maturin develop`).
- Destination path in `--add-binary` is wrong (e.g., `:poker_solver/` with trailing slash or missing entirely).
- In-bundle smoke test step missing entirely from `build_macos_dmg.sh` (catches the issue at install time instead of build time — audit will flag).

**Diagnosis:** read Agent B's build log; cross-reference spec §6.3 (canonical invocation) + §12.1 (top risk). Audit focus area 4 will intentionally omit `--add-binary` and assert the smoke test catches it — Agent B's smoke test step is the mitigation that prevents user-visible crashes.

### 4b. Code-signing chain failure (Apple Developer optional path)

**Symptom:** Agent B's `--skip-signing --skip-notarization` path fails OR the signed path fails on a machine without Apple credentials.

**Common causes for PR 11:**
- `--skip-signing --skip-notarization` accidentally still calls `codesign` somewhere in the pipeline (defeats the unsigned-fallback contract; spec §6.7).
- `xcrun` presence check missing from pre-flight (script fails opaquely on machines without Xcode Command Line Tools; spec §12.6).
- `--skip-notarization` doesn't imply `--skip-signing` — both flags must be independently respected (signed-not-notarized is a valid local-dev state).
- `entitlements.plist` references credentials by mistake (must contain only entitlement keys, never literal Developer IDs).

**Diagnosis:** spec §6.4 (signing) + §6.7 (unsigned fallback) are canonical. Audit focus areas 6 (no committed credentials), 8 (unsigned-fallback functional), 11 (inside-out signing) cross-check this.

### 4c. DMG size overflow (>200 MB soft constraint)

**Symptom:** Agent B reports final DMG size >200 MB after build.

**Common causes for PR 11:**
- `--exclude-module unittest|idlelib|turtle|tkinter` flags missing (spec §6.3 / §12.3).
- NiceGUI hidden-import list grew enough to drag in unused submodules.
- An accidental `--collect-all` flag bundling the world.

**Diagnosis:** spec §12.3 has an empirical breakdown (~165 MB target). If exceeded by <50 MB, document and accept (soft constraint per spec). If exceeded by >50 MB, the bundle has dead weight — `pyi-archive_viewer` to inspect what's inside.

### 4d. Spot ID determinism failure (library correctness)

**Symptom:** Agent C's `test_library_spot_id_deterministic` fails — semantically-equivalent inputs (reordered bet menu, reordered board) produce different SHA-256 IDs.

**Diagnostic ladder:**
1. **Read Agent A's `_compute_spot_id` canonicalization.** Spec §2.3 has 7 rules: board sort, int-cent stacks, bet-menu sort, ranges sort, antes/rake included, hyperparameters excluded, `json.dumps(sort_keys=True, separators=(",", ":"))`. Verify each rule is implemented.
2. **Check JSON serialization flags.** Without `sort_keys=True`, dict iteration order leaks into the digest. Without `separators=(",", ":")`, whitespace varies and bytes differ.
3. **Check the canonicalization input.** If Agent A serializes the raw `SpotDescription` dataclass via `asdict` without normalizing nested tuples (e.g., `bet_size_fractions` as a tuple, board as a list), Python's default ordering leaks through.
4. **Check the `label` field.** Spec §2.3 doesn't list `label` in canonicalization — label-only changes SHOULD produce the same ID (Agent C's test 4 has a deliberate ambiguity probe). If the impl includes label, that's a spec-vs-impl drift; flag for orchestrator resolution.

**Anti-pattern (audit will catch):** silently making the test pass by tweaking the canonicalization to match impl behavior. Spec is canonical; if impl diverges, impl gets corrected.

### 4e. Compression bit-exact roundtrip failure

**Symptom:** Agent C's `test_library_compression_preserves_bit_exact_strategy` fails — float values differ after gzip → JSON → gunzip → JSON roundtrip.

**Common causes for PR 11:**
- Agent A uses `np.allclose` instead of `np.array_equal` (audit focus area 3 explicitly checks this).
- `json.dumps` with default `float` precision drops bits on extreme values like `1 - 1e-15`.
- A `tolist()` call missing on numpy-array inputs, causing `json.dumps` to fail and a fallback path to lossy serialization.
- gzip `compresslevel != 6` (spec locked default; level 9 is also bit-exact but breaks the locked default test).

**Diagnosis:** spec §2.4 + §11 critical item 4 are canonical. Agent A's bit-exact contract is non-negotiable; loosening to "close enough" is a must-fix.

---

## 5. Audit + commit pipeline (after all 3 agents report back)

Per `pr_launch_runbook.md` §"Step 4–8". Run audit + check battery in same parallel wave.

### 5a. Interface drift reconciliation (runbook §"Step 4")

After ALL three agents return, run Agent C's tests against Agents A+B's implementation:

```sh
cd /Users/ashen/Desktop/poker_solver
pytest tests/test_library.py tests/test_library_cli.py -xvs
# (Agent B's packaging output is exercised separately via the build script;
# tests don't depend on a built .app.)
```

Typical drift patterns (per `docs/autonomous_log.md` from prior PRs):
- Agent A's `SpotDescription.spot_id()` signature differs from Agent C's test expectation (Agent C consumes only the public API; if Agent A added `spot_id(*, version=1)` or similar, Agent C's tests fail).
- Agent A's `Library.get` doesn't emit `UserWarning` on `solver_version` mismatch — Agent C's test catches it.
- `ruff`/`black` formatting drift on Agent A's CLI edits — auto-fix: `ruff check --fix --unsafe-fixes poker_solver tests scripts && black poker_solver tests scripts`.
- `mypy --strict` Optional/Union edge cases on `Library.get(spot: SpotDescription | str)` — fix narrowly.

After all fixes: `pytest -x` MUST be fully green before proceeding to audit.

### 5b. Audit + check battery in parallel (runbook §"Step 5")

```sh
# In orchestrator's main shell:
sh /Users/ashen/Desktop/poker_solver/scripts/check_pr.sh > /tmp/check_pr_output.log 2>&1
```

Concurrently, launch the audit agent:

```
Agent tool call (audit):
  description: "PR 11 audit — fresh reviewer, no implementation context"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr11_prep/audit_prompt.md
           between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true
```

Audit writes its report to `docs/pr11_prep/audit_report.md`. While both run, fan out additional downstream-PR work per parallelization rule.

After both complete:
- Read `pr_report.md` (output of `check_pr.sh`). Confirm "ready for user review" with all gates `OK` or `skip` (NOT `FAIL`).
- Read `docs/pr11_prep/audit_report.md`. **`must-fix` items are a hard stop.** `should-fix` / `nice-to-fix` can be deferred to a follow-up with a TODO.

PR 11-specific must-fix triggers (per audit focus areas):
- `PRAGMA journal_mode = WAL` missing from schema (concurrent reads break).
- `_compute_spot_id` non-deterministic across reordered inputs.
- Compression roundtrip uses `np.allclose` instead of `np.array_equal` (silent precision loss).
- `--add-binary` for `_rust.so` missing OR in-bundle smoke test absent (bundle crashes at runtime).
- Apple credentials committed (any literal Developer ID, Apple ID, password, or Team ID in `scripts/` or `assets/`).
- New runtime dep added to `pyproject.toml` `[project.dependencies]` (must stay in `[project.optional-dependencies] distribution`).
- PyInstaller invocation uses `--onefile` instead of `--onedir` (breaks code-signing of inner files).
- `LibrarySchemaError` not raised on schema-version mismatch (loud-error contract for forward incompatibility).
- `--skip-signing --skip-notarization` path is broken (defeats the unsigned-fallback contract).

### 5c. Commit (runbook §"Step 6")

```sh
cd /Users/ashen/Desktop/poker_solver
git status   # verify what is staged; confirm no .env / Apple credentials / built .app or .dmg slipped in
git add poker_solver/ scripts/ assets/ tests/ examples/ pyproject.toml docs/pr11_prep/audit_report.md
git status   # re-verify staged set is exactly the PR 11 surface
git commit -m "$(cat <<'EOF'
PR 11: library mode + macOS packaging

Adds a SQLite-backed on-disk library at ~/.poker_solver/library.db that
persists solved spots indexed by a deterministic SHA-256 spot ID. Each
SolveResult is stored gzip-compressed (level 6) for bit-exact roundtrip.
WAL mode supports one writer + many concurrent readers. The library is
single-user, single-machine; no cloud, no auto-population (per PLAN.md).

Adds the macOS packaging pipeline: PyInstaller --onedir bundle with the
maturin-built _rust.cpython-313-darwin.so explicitly bundled via
--add-binary; inside-out codesign walk with Hardened Runtime; Apple
notarization + stapling. Apple Developer enrollment is OPTIONAL — the
--skip-signing --skip-notarization fallback produces a working unsigned
.app + .dmg with documented Gatekeeper bypass.

Test result: <X>/<X> pass (was <Y>/<Y> on integration tip).
Audit: <must-fix-count> must-fix, <should-fix-count> should-fix, <nice-to-fix-count> nice-to-fix.
DMG size: <Z> MB (target <200 MB).
EOF
)"
```

DO NOT use `git add -A` or `git add .`. Stage explicit paths. The `dist/` directory (PyInstaller output) and any `.dmg`/`.app` artifacts must NOT be committed — verify `git status` is clean of those after staging.

### 5d. Push PR branch (runbook §"Step 7")

```sh
git push -u origin pr-11-library-and-packaging
```

Autonomous per the workflow rules. Branch visible at https://github.com/amaster97/poker_solver/tree/pr-11-library-and-packaging.

### 5e. Merge into integration (runbook §"Step 8")

```sh
git checkout integration
git pull --ff-only origin integration
git merge --no-ff pr-11-library-and-packaging -m "Integration: merge PR 11 (library-and-packaging)"
git push origin integration
```

`--no-ff` mandatory (preserves PR-branch lineage in `git log --graph`).

If `git pull --ff-only` reports divergence: STOP. Another session pushed to `integration`. Investigate before merging — never `git merge` blind.

### 5f. Update PLAN.md trajectory (runbook §"Step 10")

In `/Users/ashen/Desktop/poker_solver/PLAN.md` §2 trajectory table: update PR 11's row to `landed on integration` + record branch name. In `docs/autonomous_log.md`: append progress entry with timestamp + commit hash + test count + audit-finding-count + final DMG size.

Per plan-sync rule: if `~/.claude/plans/poker_solver.md` was edited, `cp` to local `PLAN.md` before commit.

---

## 6. Failure modes + recovery (library + packaging specific)

### 6a. PyInstaller smoke test fails post-build

**Most common:** the bundled `.app` exists in `dist/`, but running `Poker Solver.app/Contents/MacOS/Poker Solver -c "from poker_solver import _rust"` raises `ImportError`.

**Causes:**
- `--add-binary` missing or wrong destination (`:poker_solver` is the correct destination; `:poker_solver/` with trailing slash or `:` alone breaks the mapping).
- `_rust.cpython-313-darwin.so` not regenerated for the current Python version (e.g., user upgraded from 3.12 to 3.13 without `maturin develop`).
- PyInstaller's `--exclude-module` accidentally excluded a transitive dep `_rust` links against.

**Recovery:** read the smoke test stderr. Spec §6.3 (PyInstaller invocation) + §12.1 (top-risk mitigation) are canonical. If the source `.so` doesn't exist, run `maturin develop --release` first. If `--add-binary` is correct but the bundle still can't find `_rust`, run `pyi-archive_viewer dist/Poker\ Solver.app/Contents/Resources/...` to confirm the file is physically inside the bundle.

### 6b. Apple notarization rejection

**Most common:** `xcrun notarytool submit ... --wait` returns `status: Invalid` instead of `status: Accepted`.

**Causes (per spec §12.8):**
- Unsigned dylib inside `Frameworks/` (inside-out signing walk missed a binary).
- Non-Hardened-Runtime binary (`--options runtime` missing from some `codesign` call).
- Missing entitlement (e.g., `allow-jit` for NumPy JIT-like patterns).
- Invalid signature (corrupted by a `--force` re-sign in the wrong order).

**Recovery:** `xcrun notarytool log <submission-id>` returns JSON pointing at the problem binary. Spec §6.4 (inside-out signing) + §6.5 (notarization) are canonical. Re-sign the flagged binary individually with the same identity + entitlements, re-zip, re-submit. The Agent B `sign_and_notarize.py` captures the failure log to `dist/notarization_failure.log` automatically.

### 6c. SQLite WAL mode not enabled

**Symptom:** Agent C's `test_library_concurrent_readers_dont_corrupt` fails — concurrent reads see "database is locked" errors.

**Cause:** Agent A's `Library.open()` doesn't run `PRAGMA journal_mode = WAL` (or runs it but ignores the return value, which silently falls back to rollback-journal mode if WAL isn't supported on the filesystem).

**Recovery:** spec §2.2 line 43 (`PRAGMA journal_mode = WAL`) + critical item 3 are canonical. The pragma must be set on EVERY connection open, not just on first DB creation. Verify Agent A reads the pragma response to confirm WAL was actually enabled (SQLite returns the new journal mode; if the filesystem doesn't support WAL, it returns the old mode silently).

### 6d. Spot ID drift between machines

**Symptom:** A spot solved on Machine A imports via `Library.import_` on Machine B, but `library.get(spot_description)` returns None because the recomputed `spot_id` differs.

**Cause:** Floating-point representation drift in bet-menu fractions or stack values, or Python version difference in `json.dumps` float repr.

**Recovery:** spec §2.3 rule 2 says stacks are int cents (no float). Rule 3 sorts bet-menu fractions but doesn't say how to serialize them — if Agent A serializes `0.33` as `0.33` on Python 3.13 vs `0.32999999...` on a different version, the digest differs. Verify Agent A converts bet-menu fractions to a stable string representation (e.g., `round(x, 6)` or string-format with fixed precision) before hashing. The export schema (§11 critical item 12) embeds the original `spot_id` in `metadata.spot_id`; Agent A's `import_` should warn (not error) on recomputed-vs-stored mismatch.

### 6e. DMG creation fails with "Error: hdiutil: create failed"

**Most common:** `create-dmg` (Homebrew) reports `hdiutil` errors.

**Causes:**
- The `dist/Poker Solver.app` path has unescaped spaces in a command Agent B wrote (bash quoting).
- `create-dmg` is not installed (`brew install create-dmg`); spec §6.6 + §13.10 lock Homebrew over npm.
- Insufficient disk space in `/tmp/` for the DMG staging area.
- macOS Gatekeeper quarantining the `.app` mid-DMG-build (rare; only on machines with strict security policies).

**Recovery:** spec §6.6 is canonical. Agent B's `build_macos_dmg.sh` pre-flight checks for `create-dmg` presence (spec §12.6 pattern). If the path-with-spaces is the issue, every `"$DMG_TARGET"` reference in the script must be double-quoted.

---

## 7. Orchestrator decisions needed BEFORE this kickoff fires

None unresolved. Launch-readiness verdict is READY (8/8 checks PASS). The spec-locked defaults that touched orchestrator-side discretion (D1 SQLite WAL, D2 SHA-256 spot ID, D3 gzip-6 compression, D6 arm64-only, D8 PyInstaller `--onedir`, D9 explicit save, D13.1 Apple Developer optional) are all locked-with-default per `pr11_spec.md` §13 + the launch-readiness record.

If the user wants to revisit any locked default before launch, that is the moment to do so (e.g., escalate Apple Developer enrollment to mandatory — would block PR 11 on a billing step). Default: launch as spec'd.

---

## 8. Risks (PR 11-specific, new vs PR 6/7/8/9/10a)

These are risks novel to PR 11 — not present in prior PR launch kickoffs because the toolchain surface is genuinely new.

### 8.1 PyInstaller + Rust extension bundling (load-bearing — spec §12.1)

PyInstaller's static-analysis AST walker does NOT find `_rust.cpython-313-darwin.so` because the import is wired at C-API level by PyO3's `#[pymodule]` macro. The bundled `.app` will launch successfully then crash on the first call into Rust. **Mitigation:** Agent B's three-part defense — `--add-binary` flag, post-PyInstaller in-bundle smoke test that imports `_rust` headlessly, and documented failure mode. The audit agent intentionally probes this by hypothetically omitting `--add-binary` and asserting Agent B's smoke test catches it. This is the single most important risk in PR 11's scope; it directly determines whether the installed `.app` works for the user.

### 8.2 Code-signing chain + Apple Developer optionality

PR 11 supports two paths: signed-and-notarized (requires $99/yr Apple Developer enrollment + ID + Team ID + app-specific password) and unsigned-fallback (`--skip-signing --skip-notarization`). The split is load-bearing because PLAN.md mandates "no cloud spend" — Apple Developer is technically not cloud spend, but the user has flagged enrollment as optional. The risk: Agent B's code accidentally hard-couples the two paths (e.g., the signing step assumes `APPLE_ID` is set even when `--skip-signing` is passed), breaking the local-dev path. **Mitigation:** Agent B's pre-flight respects each skip flag independently. The audit agent's focus area 8 (unsigned-fallback functional) verifies the `--skip-*` path produces a launchable `.app` without any Apple env vars set. The downstream UX consequence (right-click → "Open" once; or `xattr -d com.apple.quarantine` permanent trust) is documented in `assets/README.md` and the script `--help`.

### 8.3 DMG cross-platform notarization + arm64-only commitment

The DMG is arm64-only (matches PLAN.md hardware target). Apple notarization happens on the build machine but validates against Apple's servers — there's a small risk of notarization rejection that's specific to PyInstaller bundles (unsigned inner dylibs that `codesign --deep` claims to walk but actually misses). **Mitigation:** Agent B implements an explicit inside-out signing walk (`find Contents -name "*.dylib" -o -name "*.so"`) rather than relying on `--deep`, per spec §6.4. The audit agent's focus area 11 verifies the walk hits every binary in a sampled bundle. The arm64-only commitment (no universal2) is deferred to PR 11.5 if x86 Macs ever need support — spec §13.6 documents the deferral. Risk if the user later asks for universal2: rebuild Rust with `--target x86_64-apple-darwin` + `--target aarch64-apple-darwin` and `lipo -create` the two `.so`s; PyInstaller's `--target-arch universal2` flag handles the Python side. Out of scope for PR 11.

### 8.4 Schema migration policy (forward-incompatibility loud-error)

The library's `schema_version` field is set to 1 on first creation. If a future PR (12+) bumps the schema to 2 and the user opens a v1 DB with the new code, `Library.open()` must run the migration; if a v2 DB is opened with v1 code, `Library.open()` must raise `LibrarySchemaError` ("library was created by a newer solver"). The forward-incompat error is the contract that prevents silent data corruption. **Mitigation:** Agent A's critical correctness item 4 specifies the exact policy. Agent C's test 15 verifies the error path. Risk if relaxed: a future v2 DB silently opens with v1 code, v1 code writes a row with v1 fields, v2 code later reads it with missing v2 fields, downstream crashes. Loud-error is the only safe default for forward incompatibility.

### 8.5 PR 10a/10b dependency on UI library stub

PR 11's UI integration (spec §4.1) extends a stub left by PR 10a at `ui/views/library_browser.py`. If PR 10b lands instead of PR 10a (or in a different order than expected), the stub may or may not exist. **Mitigation:** the pre-flight check 1f confirms the stub is on integration before launch. The Agent prompts have file-ownership rules that prevent Agent A/B/C from touching `ui/*` directly — the UI integration is a separate sub-task within PR 11 that follows after Agents A/B/C land. Risk if the stub is missing: the UI library viewer can't be grown into a real loader; the rest of PR 11 (library API + packaging) still ships fine. This is a soft-dependency risk; PR 11 is still mergeable without the UI viewer per spec decision 13.13 ("acceptable fallback: ship PR 11 library + packaging without UI viewer, add UI in PR 11.5").

---

## 9. Quick-reference: paths this kickoff touches

- `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/pr11_spec.md` — canonical spec (read end-to-end before launch).
- `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/agent_a_prompt.md` — Agent A prompt body.
- `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/agent_b_prompt.md` — Agent B prompt body.
- `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/agent_c_prompt.md` — Agent C prompt body.
- `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/audit_prompt.md` — audit agent prompt body.
- `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/audit_report.md` — written by audit agent (does not exist pre-launch).
- `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/launch_readiness.md` — READY verdict.
- `/Users/ashen/Desktop/poker_solver/docs/pr_launch_runbook.md` — universal runbook (§"PR 11" row).
- `/Users/ashen/Desktop/poker_solver/PLAN.md` — trajectory table updated post-merge.
- `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — progress entry post-merge.
- `/Users/ashen/Desktop/poker_solver/scripts/check_pr.sh` — check battery (Agent C extends to include library tests).
- `/Users/ashen/Desktop/poker_solver/pr_report.md` — written by `check_pr.sh` at repo root.
- `/tmp/integration_pre_pr_11.hash` — reflog backup hash (pre-flight 1e).
