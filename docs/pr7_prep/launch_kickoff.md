# PR 7 launch kickoff — river-spot differential test vs `noambrown/poker_solver`

**Status:** PRE-STAGED PLAYBOOK. Do NOT execute until PR 6 has merged to `integration` and the user has approved firing PR 7.

**Purpose:** the exact command sequence + agent fan-out the orchestrator runs when PR 6 lands and PR 7 is next on deck. This doc collapses §0–§8 of `docs/pr_launch_runbook.md` against the PR 7-specific shape (subprocess-invoked C++ reference solver, MIT-licensed Noam Brown repo, river-only parity gate) into a single executable transcript so launch is mechanical, not improvisational.

**Branch:** `pr-7-noambrown-diff` (per `pr_launch_runbook.md` §"PR 7" + PLAN.md §1 "Per-PR feature branches from PR 3 onward"). Branch name is hard-coded in `audit_prompt.md:14` — do NOT improvise.

**Inputs that govern this playbook:**
- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/pr7_spec.md`
- Agent prompts: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/agent_{a,b,c}_prompt.md`
- Audit prompt: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/audit_prompt.md`
- Launch-readiness verdict: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/launch_readiness.md` (READY-WITH-PATCHES — P1 path patch must be applied to `pr7_spec.md` lines 89/102/206 + `audit_prompt.md:84` before firing)
- Universal runbook: `/Users/ashen/Desktop/poker_solver/docs/pr_launch_runbook.md`

---

## 1. Pre-flight gate (run BEFORE branch creation)

All checks below must pass. If ANY fails, stop and resolve before continuing.

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. PR 6 is committed AND merged to integration. PR 7's Python-vs-C++ diff
# does NOT depend on PR 6's Rust port directly, but PLAN §4's validation
# chain orders PR 6 → PR 7.
git fetch origin
git log --oneline integration -5
# Expected topmost commit: "Integration: merge PR 6 (rust-hunl-postflop)".
# If not present, PR 6 has not fully landed; do not launch.

# 1b. integration tip matches origin/integration (zero divergence).
git rev-parse integration; git rev-parse origin/integration
# Both hashes must be equal. If not: `git pull --ff-only origin integration`.

# 1c. Working tree clean.
git status
# Expected: "nothing to commit, working tree clean".

# 1d. All PR 7 prompts up to date (per launch_readiness.md verdict).
ls -la docs/pr7_prep/
# Expected: pr7_spec.md, agent_{a,b,c}_prompt.md, audit_prompt.md,
# launch_readiness.md (verdict: READY-WITH-PATCHES).

# 1e. P1 binary-path patch applied. Per launch_readiness.md Check 1:
# canonical path is `references/code/noambrown_poker_solver/cpp/build/...`
# (CMake source root is `cpp/`). Confirm spec/audit-prompt no longer
# contain the bare `build/` variant:
grep -n "noambrown_poker_solver/build/" docs/pr7_prep/pr7_spec.md docs/pr7_prep/audit_prompt.md \
    || echo "patch clean — all paths canonical"
# Expected: "patch clean". Any grep hit → apply the sed patch before firing.

# 1f. PR 6 Python surface still imports (sanity for PR 7's freeze guarantees).
python -c "from poker_solver import HUNLPoker, HUNLConfig; from poker_solver.hunl import Street; print('imports OK')"

# 1g. Reflog backup hash (per runbook §0).
git rev-parse integration > /tmp/integration_pre_pr_7.hash
echo "integration tip pre-PR-7: $(cat /tmp/integration_pre_pr_7.hash)"
```

Optional sanity: `pytest -x -q` from `integration` tip — must be green before branching.

**Important: do NOT build Brown's binary as part of pre-flight.** The build step is owned by Agent A (delivers `scripts/build_noambrown.sh`); pre-flight only verifies the `references/code/noambrown_poker_solver/` vendored tree is present and the canonical `cpp/build/` target is unobstructed.

---

## 2. Branch creation

Mechanical. Branch name is hard-coded in `audit_prompt.md:14` — do NOT improvise.

```sh
cd /Users/ashen/Desktop/poker_solver
git checkout integration
git pull --ff-only origin integration   # last sanity check
git checkout -b pr-7-noambrown-diff
git status   # expect: clean tree, on pr-7-noambrown-diff
git log --oneline -1  # expect: PR 6 merge commit
```

Branch convention rationale (PLAN.md §1 + runbook §"Per-PR specifics → PR 7"): every PR from PR 3 onward gets its own feature branch from `integration`, NOT `main`. `pr-7-noambrown-diff` is the exact spelling the audit prompt expects to see in `git diff integration...HEAD` cross-references.

---

## 3. Three-agent fan-out launch (parallel, same wave)

Per `pr_launch_runbook.md` §"Step 2": all three implementation agents launch in the SAME tool-call wave. They are designed to be independent — file-ownership boundaries are locked in each prompt.

For each agent, the prompt is the **full contents of the corresponding `docs/pr7_prep/agent_{a,b,c}_prompt.md` file between the two `---` markers** (NOT the orchestrator header above the first `---`). Do not paraphrase, do not truncate, do not inline — copy the file body verbatim.

**Launch sequence (orchestrator side, all three in one tool-call block):**

```
Agent A: "PR 7 Agent A — Brown build wrapper + 15 river fixture spots + canonicalizer module"
  prompt: <body of docs/pr7_prep/agent_a_prompt.md between the two `---` markers>
  subagent_type: general-purpose; run_in_background: true
Agent B: "PR 7 Agent B — pytest diff harness (15 spots, parity_noambrown marker)"
  prompt: <body of docs/pr7_prep/agent_b_prompt.md between the two `---` markers>
  subagent_type: general-purpose; run_in_background: true
Agent C: "PR 7 Agent C — self-sanity smoke tests (no-binary, 8 tests per spec §10)"
  prompt: <body of docs/pr7_prep/agent_c_prompt.md between the two `---` markers>
  subagent_type: general-purpose; run_in_background: true
```

**Ownership recap (verifies interface lock — do NOT relax these):**

| Agent | Owns (write/create) | May surgically modify | Forbidden |
|---|---|---|---|
| A | `scripts/build_noambrown.sh`, `tests/data/river_spots.json`, `poker_solver/parity/__init__.py`, `poker_solver/parity/noambrown_wrapper.py` | `.gitignore` (Brown `cpp/build/` exclusion), `references/README.md` (one-line append) | any test file, `poker_solver/hunl.py`, `poker_solver/solver.py`, `pyproject.toml`, any file inside `references/code/noambrown_poker_solver/` |
| B | `tests/test_noambrown_river_parity.py` | `pyproject.toml` (register `parity_noambrown` marker) | wrapper module, fixture JSON, build script, `poker_solver/*`, Agent C's test file |
| C | `tests/test_noambrown_self_sanity.py` | (none) | any non-test file, build script, Agent B's test file, `pyproject.toml` |

**Parallel fan-out during agent runtime** (PLAN.md §5 + runbook §"Step 3"): while A/B/C run, launch independent agents on downstream work — PR 8 baseline-bench spec polish, PR 9 dispatcher-rewrite research, `docs/autonomous_log.md` pruning, doc-inventory sweep post-PR-6.

Aggregate per wave — do NOT react agent-by-agent.

---

## 4. Monitor + reconciliation patterns

While agents run, the orchestrator does NOT block. Track agent completion via the standard background-task notification stream. Specific failure signatures to watch for in agent outputs:

### 4a. Brown C++ build failures (macOS-specific risks)

**Symptom:** `bash scripts/build_noambrown.sh` errors locally, or `test_brown_binary_buildable` fails.

**Common causes (honest about platform risk):**
- **Xcode CLT not installed on macOS.** `cmake` may be on PATH via Homebrew while `c++` is a stub prompting the GUI installer; Agent A's `command -v c++` soft-fail check passes while real compilation fails. Recovery: `xcode-select --install`.
- **`-march=native` on Apple Silicon.** Brown's `cpp/CMakeLists.txt:32` passes this; Apple Silicon clang typically warns rather than erroring. PR 7 tests strategy agreement (not perf), so a different binary is acceptable.
- **CMake version too old.** `brew upgrade cmake` if soft-fail didn't trigger (cmake present but below minimum).

**Diagnosis:** the skipif decorators should keep the suite green even when the build itself fails — confirm `pytest -x` exits 0 (with skips), not failing.

### 4b. skipif decorator coverage

**Symptom:** parity tests ERROR instead of `pytest.skip` on a system without C++ tooling.

**Five-layer skip strategy (launch_readiness.md Check 6):** (1) `scripts/build_noambrown.sh` exits 0 on missing toolchain; (2) `find_brown_binary()` returns `None` when the binary file is absent; (3) `test_river_parity_vs_brown` calls `pytest.skip(...)` at the TOP when `find_brown_binary()` is None; (4) `test_brown_binary_buildable` has its own `shutil.which("cmake")` guard; (5) Agent C's smoke tests bypass the whole subsystem.

If a test errors instead of skipping, the bug is in (2) or (3): `find_brown_binary()` is raising rather than returning `None`, or the test does work before the skip check. Fix narrowly.

### 4c. Raise canonicalization drift (Brown extra-beyond-call ↔ ours raise-to-total)

**Symptom:** Agent C's `test_canonicalize_history_roundtrip` fails on one or more of the 10 hand-built cases, OR Agent B's diff test reports 0% history-key intersection on every spot.

**Cause:** the load-bearing canonicalization in spec §5 step 5 + §9 risk #1. Brown stores `r<extra>` (extra-beyond-call); we store `r<to_total>`. Both `canonicalize_brown_history()` and `canonicalize_our_history()` must normalize to the SAME canonical form (the spec locks this at `("r", to_total)`).

**Diagnostic ladder:**
1. **First: confirm the 10 round-trip cases pass** in `test_canonicalize_history_roundtrip`. If any fail, the canonicalizer has a state-tracking bug; downstream diff is noise.
2. **If round-trips pass but diff reports 0% coverage**, the bug is in `our_strategy_to_brown_matrix()` key derivation — verify the dict is keyed by canonical-history-string (Brown's `/`-joined tokens), not raw `infoset_key`.
3. **If coverage is positive but below 80%**, action-menu drift: confirm `include_all_in=True` + `max_raises=3` are present in both Brown's subgame JSON and the `HUNLConfig` we construct (`subgame_config.cpp:303-388` is Brown-side canonical).
4. **All-in token mapping** (spec §5 step 5; audit focus area #3): our `A` re-emits as `("b", remaining_stack)` when `to_call == 0`, or `("r", actor_new_total)` when `to_call > 0`. Bugs here mean every all-in spot fails.

**Anti-pattern (audit will catch):** silently dropping all-in cases from the comparison, or silently loosening the 80% coverage threshold. Both are spec changes — flag to user, do not autonomous.

### 4d. Diff-test tolerance (5e-3 per-action, 1e-3 × pot per game value)

**Symptom:** `test_river_parity_vs_brown` fails per-action or per-spot game-value tolerance.

**Diagnostic ladder:**
1. **DCFR flags exact.** Brown invocation MUST be `--algo dcfr --dcfr-alpha 1.5 --dcfr-beta 0 --dcfr-gamma 2 --seed 7`. β=0 (not 0.5), γ=2 (Brown accepts `2` or `2.0`; verify his CLI parser). One wrong flag = different algorithm.
2. **Iteration count identical on both sides.** 2000 default; `spot.iterations_override` overrides for BOTH engines. Mismatch = unequal convergence = guaranteed false-positive.
3. **Seed=7 on Brown's side.** Brown's default is 7 but we pass `--seed 7` explicitly for paranoia (spec §11 #1).
4. **Per-(history, hand, action) max diff.** If max is 6e-3 (just over spec), find the FP-reduction-order divergence between Python and Brown's C++; do NOT loosen tolerance.
5. **Game-value units.** Brown emits chips; our `SolveResult.game_value` may be in BB-units (`utility()` returns `c0 / bb`). Multiply by `cfg.big_blind` to get chips (`agent_b_prompt.md:220-224`); unit mismatch = systematic ~100× error.

**Anti-pattern (audit will catch):** silently relaxing tolerance to 1e-2 / 5e-2 to make a test pass. Spec §1 + audit focus area #6 mark this must-fix.

### 4e. mypy / lint on `noambrown_wrapper.py`

**Symptom:** `mypy --strict poker_solver/parity/noambrown_wrapper.py` reports errors.

**Common causes:** `Optional[Path]` vs `Path | None` style drift on `find_brown_binary()`; `np.ndarray` non-generic in `our_strategy_to_brown_matrix` return type (use `npt.NDArray[np.float64]`); `CanonicalHistory` Literal narrowing wants explicit `cast()`. Fix narrowly per agent_a_prompt.md §"Public API contract"; don't broaden Optional to Any.

---

## 5. Audit + commit pipeline (after all 3 agents report back)

Per `pr_launch_runbook.md` §"Step 4–8". Run audit + check battery in same parallel wave.

### 5a. Interface drift reconciliation (runbook §"Step 4")

After ALL three agents return, build Brown's binary then run the new test surface:

```sh
cd /Users/ashen/Desktop/poker_solver
bash scripts/build_noambrown.sh   # soft-fails (exit 0) on missing cmake/c++; tests skip
pip install -e .                  # rebuild PyO3 bindings if PR 6 touched them
pytest tests/test_noambrown_self_sanity.py -xvs   # Agent C smoke; no binary needed
pytest tests/test_noambrown_river_parity.py -v    # Agent B diff; skips if no binary
```

Typical drift patterns (per `docs/autonomous_log.md` S1–S5):
- `RiverSpot` schema mismatch between Agent A and Agent B's consumer expectations — spec §10 Agent A "Public API contract" is canonical.
- `ruff`/`black` drift — `ruff check --fix --unsafe-fixes poker_solver/parity/ tests/ && black poker_solver/parity/ tests/`.
- `mypy` strict complaints on new `parity` package — narrow `cast()` / `Optional`.
- `pyproject.toml` marker collision: if `parity` / `external` already exists per spec §12 #6, prefer reuse — flag rather than duplicate.

After fixes: `pytest -x` MUST be green (with skips for no-toolchain machines) before audit.

### 5b. Audit + check battery in parallel (runbook §"Step 5")

```sh
sh /Users/ashen/Desktop/poker_solver/scripts/check_pr.sh > /tmp/check_pr_output.log 2>&1
```

Concurrently launch the audit agent:

```
Audit: "PR 7 audit — fresh reviewer, no implementation context"
  prompt: <body of docs/pr7_prep/audit_prompt.md between the two `---` markers>
  subagent_type: general-purpose; run_in_background: true
```

Audit writes to `docs/pr7_prep/audit_report.md`. While both run, fan out additional downstream-PR work per the parallelization rule.

After both complete:
- Read `pr_report.md` (output of `check_pr.sh`). Confirm "ready for user review" with all gates `OK` or `skip` (NOT `FAIL`).
- Read `docs/pr7_prep/audit_report.md`. **`must-fix` items are a hard stop.** `should-fix` / `nice-to-fix` can be deferred to a follow-up with a TODO.

PR 7-specific must-fix triggers (audit_prompt.md focus areas):
- Build script not idempotent OR hard-fails (`exit 1`) on missing cmake/c++ instead of soft-fail (`exit 0`).
- Raise-encoding canonicalization wrong (Brown `r<extra>` not normalized to our `r<to_total>` form, or vice versa).
- All-in `A` token not re-emitted as Brown's `b<amount>` / `r<amount>` per the `to_call` context.
- DCFR flags wrong (β≠0, γ≠2, missing `--algo dcfr`, missing `--seed 7`).
- Tolerance silently relaxed beyond 5e-3 per-action or 1e-3 × pot per game value.
- Skip path missing on missing binary (test errors instead of `pytest.skip`).
- AGPL contamination (any code copy from `postflop-solver` / `TexasSolver`).
- Fixture JSON board/range overlap, or duplicate board cards (`Jh Tc Tc 5d 3s` per launch_readiness P3).
- New third-party dependency in `pyproject.toml` (spec §10 Agent A locks stdlib + numpy + existing).
- Binary path uses bare `build/` rather than canonical `cpp/build/` (launch_readiness P1).

### 5c. Commit (runbook §"Step 6")

```sh
cd /Users/ashen/Desktop/poker_solver
git status   # verify what is staged; confirm no .env / secrets / build artifacts slipped in
git add scripts/build_noambrown.sh tests/data/river_spots.json poker_solver/parity/ \
        tests/test_noambrown_river_parity.py tests/test_noambrown_self_sanity.py \
        pyproject.toml .gitignore references/README.md docs/pr7_prep/audit_report.md
git status   # re-verify staged set is exactly the PR 7 surface
git commit -m "$(cat <<'EOF'
PR 7: river-spot differential test vs noambrown/poker_solver

Differentially tests our Python HUNL river solves against Noam Brown's
MIT-licensed river_solver_optimized C++ binary on 15 curated river spots
(5 categories × 3 spots). New poker_solver/parity/ package hosts the
subprocess wrapper, fixture loader, and history canonicalizer (Brown's
extra-beyond-call ↔ our raise-to-total).

License: Brown's repo is MIT (LICENSE:1-21). PR 7 invokes the binary and
parses --dump-strategy JSON; no C++ source copied. Attribution per spec §8.

Diff gates: 5e-3 per-action, 1e-3 × pot per game value (spec §1, consistency-
review I3). Iterations: 2000 with per-spot RiverSpot.iterations_override.
DCFR flags: --algo dcfr --dcfr-alpha 1.5 --dcfr-beta 0 --dcfr-gamma 2 --seed 7.
Skip strategy: build_noambrown.sh soft-fails on missing toolchain;
find_brown_binary() returns None; parity tests pytest.skip cleanly.

Test result: <X>/<X> pass. Parity: <S> pass / <N> skip / 0 fail.
Audit: <m> must-fix, <s> should-fix, <n> nice-to-fix.
EOF
)"
```

DO NOT use `git add -A` or `git add .`. Stage explicit paths. The `references/code/noambrown_poker_solver/cpp/build/` directory must NOT be staged (Agent A's `.gitignore` edit handles this).

### 5d. Push + merge into integration (runbook §"Step 7–8")

```sh
git push -u origin pr-7-noambrown-diff
git checkout integration
git pull --ff-only origin integration
git merge --no-ff pr-7-noambrown-diff -m "Integration: merge PR 7 (noambrown-diff)"
git push origin integration
```

`--no-ff` mandatory (preserves PR-branch lineage). If `git pull --ff-only` reports divergence: STOP — another session pushed to `integration`. Never `git merge` blind.

### 5e. Update PLAN.md trajectory (runbook §"Step 10")

In `PLAN.md` §2 trajectory: PR 7 row → `landed on integration` + branch name. In `docs/autonomous_log.md`: append progress entry with timestamp, commit hash, test count, per-spot pass-or-skip summary, audit-finding count. Per plan-sync rule: if `~/.claude/plans/poker_solver.md` was edited, `cp` to local `PLAN.md` before commit.

---

## 6. Failure modes + recovery (PR 7-specific)

### 6a. Brown's binary fails to build on macOS

**Most common:** `bash scripts/build_noambrown.sh` errors with cmake-configure or compile failures.

**Causes (macOS-specific, honest about platform risk):**
- **Xcode Command Line Tools missing.** `c++` is a stub that prompts the GUI installer; the soft-fail check `command -v c++` passes but compilation fails. Recovery: `xcode-select --install`.
- **CMake version below minimum.** Soft-fail won't trigger (cmake is found). Recovery: `brew upgrade cmake`.
- **`-march=native` errors on Apple Silicon.** Brown's `cpp/CMakeLists.txt:32` passes this; clang typically only warns. If it hard-errors, we do NOT patch the vendored tree (Agent A's ownership rules forbid modifying `references/code/noambrown_poker_solver/`) — file a finding for user instead.

**Recovery:** if the build cannot complete on the dev box, the test suite still passes (skips cleanly). The PR can land WITHOUT a successful local build — the audit confirms the skip path is correct, and a developer with the toolchain validates the diff downstream. This is the explicit design per spec §6 + §12 #3.

### 6b. Fixture JSON load errors

**Most common:** `load_spots()` raises on the committed `tests/data/river_spots.json`.

**Causes:** duplicate board cards (e.g., spec §4's `Jh Tc Tc 5d 3s` paired-row; Agent A should fix to `Jh Td Tc 5d 3s` per agent_a_prompt.md:419); range hand overlaps with board (spec §9 #7); duplicate cards within a hand (e.g., `AhAh`); range size < 30 combos per side; `bet_sizes` outside (0, 5]; schema version mismatch.

**Recovery:** Agent A's `load_spots()` raises `ValueError` with spot id + offending field. One-line fixture patch; not structural.

### 6c. Strategy-matrix shape mismatch

**Symptom:** `test_strategy_matrix_shape` fails: matrix isn't `(num_hands, num_actions)` for a canonical history.

**Causes:** `our_strategy_to_brown_matrix()` mis-parses `infoset_key`'s `f"{hole}|{board}|{street}|{history}"` format (must parse hand from segment 0, canonical history from segment 3); board-overlap hand-filter inconsistency between engines (Brown silently filters at construction, we reject at load — matrix should drop, not error); action-menu drift (`max_raises` / `include_all_in` mismatch between Brown's subgame JSON and `HUNLConfig`).

**Recovery:** verify `write_brown_config()` round-trips field-for-field with `HUNLConfig`. Single-line edit.

### 6d. iterations_override plumbing broken

**Symptom:** `test_iterations_override_respected` fails: solver runs 2000 despite `iterations_override=500`. **Cause:** `solve_river_subgame()` (PR 7's explicit-range entry point per spec §5 step 2) doesn't read `spot.iterations_override`. **Recovery:** trace from test through to DCFR loop counter; single-file fix in `noambrown_wrapper.py`.

### 6e. xdist subprocess collision

**Symptom:** `pytest -n auto` intermittently produces stale JSON. **Cause:** spec §9 risk #8 — workers writing to fixed `/tmp/spot_<id>.json`. `run_brown_solver()` must use per-call `tempfile.NamedTemporaryFile(delete=False)` / `tempfile.mkdtemp()`. Recovery: wrap in `with tempfile.TemporaryDirectory()`.

---

## 7. Orchestrator decisions needed BEFORE this kickoff fires

**One:** the P1 binary-path patch (launch_readiness.md Check 1) must be applied to `pr7_spec.md` lines 89/102/206 and `audit_prompt.md:84` — replace `noambrown_poker_solver/build/` with `noambrown_poker_solver/cpp/build/` in all four locations. Mechanical (one-line sed) but must land before the audit agent reads `audit_prompt.md:84` (else the audit reports a false must-fix against Agent A's correct path).

Other launch-readiness gates are READY (DCFR flags consistent, tolerance consistent, raise canonicalization specified, license documented, skipif strategy comprehensive). Two P3 residuals (one all-in case in Agent C's test; the paired-board duplicate `Jh Tc Tc 5d 3s`) are flagged inside the prompts — no orchestrator action.

If the user wants to revisit any locked default before launch — tolerance (`5e-3` → tighter / looser), iterations (`2000` → `5000`), spot count (`15` → `20`), pot/stack units alignment — this is the moment. Default: launch as spec'd.

---

## 8. Quick-reference: paths this kickoff touches

- `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/pr7_spec.md` — canonical spec.
- `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/agent_{a,b,c}_prompt.md` — implementation prompts.
- `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/audit_prompt.md` — audit agent prompt.
- `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/audit_report.md` — written by audit (does not exist pre-launch).
- `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/launch_readiness.md` — READY-WITH-PATCHES.
- `/Users/ashen/Desktop/poker_solver/docs/pr_launch_runbook.md` — universal runbook (§"PR 7" row).
- `/Users/ashen/Desktop/poker_solver/PLAN.md` — trajectory table updated post-merge.
- `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — progress entry post-merge.
- `/Users/ashen/Desktop/poker_solver/scripts/check_pr.sh` — check battery.
- `/Users/ashen/Desktop/poker_solver/scripts/build_noambrown.sh` — Brown C++ build wrapper (Agent A delivers).
- `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/build/river_solver_optimized` — Brown's binary (gitignored).
- `/Users/ashen/Desktop/poker_solver/pr_report.md` — written by `check_pr.sh`.
- `/tmp/integration_pre_pr_7.hash` — reflog backup hash (pre-flight 1g).
