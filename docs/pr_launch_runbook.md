# PR launch runbook

**Audience:** the autonomous orchestrator (Claude session) — or the user — driving PR N from a fresh launch through `integration` merge. PRs 4 through 12.

**Scope:** the workflow is identical for every PR from PR 4 onward (PR 3 and PR 3.5 already shipped under this pattern; this runbook codifies their workflow for reuse). Per-PR variations are factored out at the end.

**Severity tags used throughout:**
- `[NORMAL]` — copy-paste; no destructive action; safe to run unattended.
- `[CAREFUL]` — pause and read output before continuing; one branch back is always possible.
- `[DANGEROUS]` — destructive (rebase, force push, branch deletion); requires explicit user OK in autonomous mode. Never execute these without confirming what they will overwrite.

**Standing rules absorbed from PLAN.md + autonomous_log.md:**
- Branches: `pr-N-<short-title>`, branched from `integration` (NOT `main`). `integration` is the always-latest working set; `main` only advances on user-approved merges.
- Pushes: PR-branch pushes to `origin` are autonomous. `integration` merges + pushes autonomous. `main` merges + force-pushes (any branch) require explicit user OK.
- Steady-state 3-5 concurrent agents during autonomous sessions. Single-threading is the failure mode.
- Every PR 3+ requires a fresh general-purpose audit agent (no implementation context) before commit.
- `pr_report.md` (from `scripts/check_pr.sh`) AND `audit_report.md` must both look clean before commit.

---

## Universal pre-launch checklist

Run these in order. All must pass before launching agents for PR N.

- [ ] Previous PR merged into `integration` (verify `git log --oneline integration -5` shows the previous PR's merge commit).
- [ ] Working tree clean on whichever branch you're on (`git status` shows nothing).
- [ ] On branch `integration`, up to date with `origin/integration` (`git fetch origin && git status` reports zero divergence).
- [ ] PR N spec exists and has been reviewed: `/Users/ashen/Desktop/poker_solver/docs/prN_prep/prN_spec.md`.
- [ ] PR N agent prompts exist: `/Users/ashen/Desktop/poker_solver/docs/prN_prep/agent_{a,b,c}_prompt.md` (some PRs have a, b, c — others may have just a, b — check the directory).
- [ ] PR N audit prompt exists: `/Users/ashen/Desktop/poker_solver/docs/prN_prep/audit_prompt.md`.
- [ ] All open user-decision items in `docs/autonomous_log.md` for PR N are either resolved or have a documented default-with-rationale (the "locked-with-default" pattern).
- [ ] If `main` has moved since last PR launch (check `git log origin/main -3`), record current `integration` tip hash for reflog backup before any rebase: `git rev-parse integration > /tmp/integration_pre_pr_N.hash`.

If ANY checkbox fails, do not launch agents. Resolve first.

---

## Per-PR launch sequence (universal template)

### Step 0. Prerequisites verification `[NORMAL]`

```sh
cd /Users/ashen/Desktop/poker_solver
git fetch origin
git checkout integration
git pull --ff-only origin integration
git status
git log --oneline -5
```

Expected: clean tree, on `integration`, no divergence from `origin/integration`, last commit is the prior PR's merge.

### Step 1. Create PR branch + verify spec files `[NORMAL]`

```sh
git checkout -b pr-N-<short-title> integration
ls docs/prN_prep/
```

Expected: 5 files listed (`prN_spec.md`, `agent_a_prompt.md`, `agent_b_prompt.md`, `agent_c_prompt.md`, `audit_prompt.md`). Branch name MUST match the convention in §"Per-PR specifics" below (audit prompts hard-code the branch name).

### Step 2. Fan out implementation agents `[NORMAL]`

For each agent prompt file `docs/prN_prep/agent_X_prompt.md`:

1. Open the file.
2. Copy the text strictly between the two `---` markers (NOT the orchestrator header above the first `---`).
3. Launch a fresh general-purpose Agent with that text as the prompt.
4. Repeat for every agent prompt (typically 3, sometimes 2).

**Launch all agents in the SAME response/tool-call wave (parallel).** They are designed to be independent — file-ownership boundaries are stated in each prompt's "Strict file ownership" section.

Concurrency floor: 3 implementation agents. While they run, fan out additional independent agents (downstream PR research, docs polish, spec-consistency review) per PLAN.md §5 "Parallelization protocol."

### Step 3. Monitor implementation `[NORMAL]`

While agents run, do NOT block. Productive parallel work during this wait:
- Draft `pr_(N+1)_prep/` spec content if not already done.
- Spawn a "spec consistency review" agent to cross-check PR N's spec against PRs N+1, N+2 for interface drift.
- Pre-draft user-facing release notes for PR N.

Track which agents have returned. Aggregate per wave: read all outputs together once they ALL return; do NOT react agent-by-agent (PLAN.md §5 "Aggregate per wave").

### Step 4. Resolve interface drift `[CAREFUL]`

After ALL implementation agents return, scan for the typical drift patterns documented in `docs/autonomous_log.md` (entries S1–S5 for PR 3 — same patterns recur):

1. **Interface mismatch between two agents.** Run the test suite Agent C wrote against the implementation Agents A+B produced. If tests fail with `AttributeError`, `TypeError`, or "unexpected keyword argument," the agents drifted. **Resolution rule:** the spec file (`prN_spec.md`) is canonical — whichever agent matches the spec wins. The other agent's interface gets rewritten.

2. **Lint / format drift from auto-tools.** Agents commonly produce code that fails `black --check` or `ruff check`:
   ```sh
   ruff check --fix --unsafe-fixes poker_solver tests
   black poker_solver tests
   ```

3. **Type errors from `mypy`.** Often Optional/Union mismatches at interface boundaries. Fix locally, ~30-line touch typically.

4. **Bug surfaced by a test that one agent wrote but another agent's code was supposed to satisfy.** Find the failing test, find the missing branch in the implementation, fix narrowly. Log the bug + fix in `docs/autonomous_log.md` under "Small decisions made autonomously" with an S-tag.

After ALL fixes: `pytest -x` must pass. If it doesn't, do not proceed.

### Step 5. Audit + check battery in parallel `[NORMAL]`

Launch the audit agent and the check battery in the same wave:

```sh
# In the orchestrator's main shell:
sh /Users/ashen/Desktop/poker_solver/scripts/check_pr.sh > /tmp/check_pr_output.log 2>&1
```

In parallel, launch the audit agent: copy the entire text of `docs/prN_prep/audit_prompt.md` between the `---` markers as the prompt for a fresh general-purpose agent. The audit agent writes its report to `docs/prN_prep/audit_report.md`.

While both run, you may launch other downstream-PR research agents (parallelization rule).

After both complete:
- Read `pr_report.md` at repo root (output of check_pr.sh). Confirm "ready for user review" status with all gates `OK` or `skip` (NOT `FAIL`).
- Read `docs/prN_prep/audit_report.md`. Look for `must-fix` items. **`must-fix` is a hard stop.** `should-fix` / `nice-to-fix` can be deferred to a follow-up PR with a TODO note.

### Step 6. Commit `[NORMAL]`

```sh
cd /Users/ashen/Desktop/poker_solver
git add poker_solver/ tests/ docs/prN_prep/audit_report.md scripts/ pyproject.toml
git status   # verify what is staged; confirm no .env / secrets / binary blobs slipped in
git commit -m "$(cat <<'EOF'
PR N: <one-line title from spec>

<2-3 sentence summary of what landed: which modules, key public API additions, test count change>

Test result: <X>/<X> pass (was <Y>/<Y> on integration tip).

Audit: <must-fix-count> must-fix, <should-fix-count> should-fix, <nice-to-fix-count> nice-to-fix.

EOF
)"
```

DO NOT use `git add -A` or `git add .`. Stage explicit paths so secrets / artifacts / large bucket files cannot leak in.

DO NOT include a `Co-Authored-By: Claude` trailer unless the user has requested it for this project (none of PR 1-3 carried one).

### Step 7. Push PR branch `[NORMAL]`

```sh
git push -u origin pr-N-<short-title>
```

This is autonomous per the workflow rules. The branch is now visible on GitHub at https://github.com/amaster97/poker_solver/tree/pr-N-<short-title>.

### Step 8. Merge into integration `[NORMAL]`

```sh
git checkout integration
git pull --ff-only origin integration   # last sanity check that integration didn't move
git merge --no-ff pr-N-<short-title> -m "Integration: merge PR N (<short title>)"
git push origin integration
```

`--no-ff` is mandatory: it preserves the PR-branch lineage in `git log --graph`, which is how `integration` stays auditable as "what's been accumulated since last main release."

If `git pull --ff-only` reports divergence, STOP. Someone (or a parallel session) pushed to `integration` while you were working. Investigate before merging — never `git merge` blind in this case.

### Step 9. Force-push reconciliation if main moved during implementation `[DANGEROUS]`

If `origin/main` advanced while PR N was in flight (e.g., user pushed a hotfix), the PR branch's base is stale. Reconcile via rebase, then force-push the PR branch and `integration`.

**Requires explicit user OK per the no-force-push rule.** Do not execute these steps autonomously.

Pre-rebase backup (run these BEFORE rebase so reflog hashes are recorded):

```sh
git rev-parse pr-N-<short-title> > /tmp/pr_N_pre_rebase.hash
git rev-parse integration > /tmp/integration_pre_rebase.hash
echo "pr-N=$(cat /tmp/pr_N_pre_rebase.hash)"
echo "integration=$(cat /tmp/integration_pre_rebase.hash)"
```

Rebase sequence:

```sh
git fetch origin
git checkout pr-N-<short-title>
git rebase origin/main                       # rebase PR branch onto new main
# if conflicts: resolve, git add <files>, git rebase --continue
pytest -x                                    # must still pass post-rebase
git checkout -B integration origin/main      # recreate integration from new main
git merge --no-ff pr-N-<short-title> -m "Integration: merge PR N (<short title>) [rebased]"
pytest -x                                    # must still pass post-merge
git push --force-with-lease origin pr-N-<short-title>
git push --force-with-lease origin integration
```

`--force-with-lease` (NOT `--force`) is mandatory: it refuses to push if the remote has moved since you last fetched, preventing accidental overwrite of another session's work.

Recovery if rebase corrupted state:

```sh
git checkout pr-N-<short-title>
git reset --hard "$(cat /tmp/pr_N_pre_rebase.hash)"
git checkout integration
git reset --hard "$(cat /tmp/integration_pre_rebase.hash)"
```

### Step 10. Update PLAN.md trajectory + autonomous log `[NORMAL]`

In `/Users/ashen/Desktop/poker_solver/PLAN.md` §2 (trajectory table), update PR N's row:
- Status: `pending` → `landed on integration` (NOT `landed on main` — that flag is only after user merges to main).
- Branch column: replace `TBD` with the actual branch name.

In `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md`:
- Append a progress-log entry with timestamp + commit hash + test count + audit-finding-count.
- If you locked any deferred decisions during PR N, document them in the "Small decisions" section with an S-tag and a reversibility note.
- If you found and fixed a bug mid-PR, document it as an S-tag with a 1-line root-cause summary.

```sh
# After editing both files:
cp /Users/ashen/.claude/plans/poker_solver.md /Users/ashen/Desktop/poker_solver/PLAN.md   # if also edited the master plan in ~/.claude/plans
git add PLAN.md docs/autonomous_log.md
git commit -m "Update PLAN.md trajectory and autonomous log for PR N"
git push origin integration
```

Per the plan-sync rule: when the master plan in `~/.claude/plans/` is edited, immediately `cp` to local PLAN.md.

### Step 11. Hand off to user OR launch next PR `[NORMAL]`

**Decision tree:**

- If user is awake and present (you can see active messages): write a 3-5 line status update covering (a) what shipped, (b) audit findings worth their attention, (c) what's next. Wait for go-ahead before launching PR N+1.
- If user is asleep (autonomous session active) AND PR N+1 spec is ready AND no deferred-decision blockers from PR N's audit: launch PR N+1 immediately using this same runbook. Do not pause for permission — that's what "autonomous" authorizes.
- If user is asleep but PR N's audit returned should-fix items that touch downstream PR specs: do NOT launch PR N+1. Wake-up brief should flag this; the user will direct.

---

## Per-PR specifics

This section documents the per-PR variations from the universal template above. Read the row for the PR you're about to launch.

### PR 4 — card abstraction (EMD bucketing)

- **Branch:** `pr-4-card-abstraction`
- **Prerequisites:** PR 3.5 merged into `integration`.
- **Locked-with-default decisions** (autonomously locked per 2026-05-21 user discussion; reversible if user redirects):
  - D1: suit-isomorphism INCLUDED in PR 4 (not split to PR 4.5). Required to keep river bucket file < 100 MB; without suit-iso the artifact balloons to ~750 MB.
  - D2: Monte Carlo equity features at 200K iterations (~0.2% noise). Exact would be ~110 days single-threaded.
- **Spec amendments (2026-05-21):**
  - `HUNLConfig.abstraction: Optional[AbstractionRef]` (NOT `Optional[AbstractionTables]`). `AbstractionRef = (source_path: str, version: str)`. Avoids retroactive schema churn for PR 6 / PR 9.
  - `.npz` `metadata` field is a JSON-serialized nested dict in a `bytes_` array, NOT separate top-level NumPy arrays.
- **Special considerations:**
  - The CLI `precompute-abstraction` is the build step; running it end-to-end with 256/128/64 buckets is multi-hour on a single thread. Checkpoint/resume is in `precompute.py`. **DO NOT run the full pipeline in CI** — only a tiny synthetic fixture is exercised by `pytest`.
  - Bucket file size sanity post-build (manual user step, not CI): with suit-iso `~100 MB` is normal; without (or if suit-iso is broken) `~750 MB` is a red flag.
  - No new runtime deps allowed — `pyproject.toml` `[project.dependencies]` must NOT gain `scipy` or `scikit-learn` (k-means + EMD are custom NumPy).
- **Smoke test after impl** (run before audit): build a tiny 4/2/2 fixture, load it back, verify `infoset_key` dispatches via bucket id when the abstraction is attached, and via lossless string when it isn't.

### PR 5 — first HUNL postflop solve + per-street memory profiler

- **Branch:** `pr-5-hunl-postflop`
- **Prerequisites:** PR 4 merged into `integration`. The PR 4 artifact (`abstraction_v1.npz`) is NOT required on the CI test runner — PR 5's tests use a tiny in-memory synthetic abstraction.
- **Locked decisions:**
  - `HUNLSolveResult` is a SUBCLASS of `SolveResult` (per spec consistency review N7). PR 9 and PR 11 depend on this shape.
- **Spec amendments (2026-05-21):**
  - Routing dispatch: PR 5 only adds the postflop branch. PR 3.5 (≤15 BB short-stack chart) executes BEFORE PR 5's postflop branch — a `starting_stack=1500` config with `starting_street=Street.FLOP` still hits the chart. PR 9 spec §6 is canonical for the full dispatch composition.
- **Special considerations:**
  - Adds `psutil >= 5.9` to `pyproject.toml` `[project.dependencies]`. This is the only new runtime dep allowed in PR 5.
  - `--max-memory-gb 14` is the default memory cap on the CLI; the profiler kills the solve if RSS exceeds this.
  - The full-fixture `solve` (Fixture 2 + 3 from the spec) requires the real `abstraction_v1.npz` from PR 4. Skip in CI; document as a manual-user-only validation step.

### PR 6 — Rust port of HUNL postflop solver

- **Branch:** `pr-6-rust-hunl-postflop`
- **Prerequisites:** PR 5 merged into `integration`.
- **Locked decisions:**
  - Scalar regret accumulator (one regret value per `(infoset, action)`) — NOT vector CFR. Vector CFR is deferred to PR 8 (if at all).
- **Spec amendments (2026-05-21):**
  - Rust `HUNLConfig` mirror pre-emptively includes `use_pcs: bool` (anticipates PR 8's schema extension — lets PR 6 and PR 8 land in either order without migration).
  - Loader parses nested `metadata` dict from PR 4's `.npz` via `serde_json::from_slice` (NOT separate top-level NumPy arrays).
- **Special considerations:**
  - **License audit is load-bearing for THIS PR.** Postflop is the first place we have direct AGPL counterparts in `references/code/postflop-solver/` and `references/code/TexasSolver/`. **Never copy from those.** Use only MIT-licensed `noambrown_poker_solver` + `slumbot2019` + Apache `open_spiel` as canonical port sources. Every new Rust file MUST carry the module-level attribution docstring (template in spec §3).
  - Diff-test tolerance: `5e-3` per-action + `1e-3 × base_pot` per-spot game value vs PR 5's Python output on the three PR 5 fixtures. Hard gate.
  - The Rust port is **mechanical + slow-but-correct**. SIMD/cache-blocking lives in PR 8 — do NOT optimize prematurely here.

### PR 7 — river-spot differential test vs `noambrown/poker_solver`

- **Branch:** `pr-7-noambrown-diff`
- **Prerequisites:** PR 6 merged into `integration`.
- **Special considerations:**
  - **External binary required.** Runs `references/code/noambrown_poker_solver/build/river_solver_optimized`. Build script: `scripts/build_noambrown.sh` (CMake + Release build). Adds CMake + C++17 compiler as build deps (already required for `references/`).
  - **Skip-cleanly path:** if `build/river_solver_optimized` is missing, tests `pytest.skip(...)` rather than fail. CI without a C++ compiler still passes.
  - Test fixtures at `tests/data/river_spots.json` — 15 hand-authored spots. NOT generated; committed verbatim.
  - Pytest marker: `@pytest.mark.parity_noambrown` (new marker; register in `pyproject.toml` `[tool.pytest.ini_options]`).
  - Tolerance: `5e-3` per-action probability, `1e-3 × base_pot` per-spot game value (matches PR 6 cluster).
  - **No Python ↔ Rust diff here.** That comparison lives in PR 6's existing diff test. PR 7 only diffs Python ↔ Brown.

### PR 8 — NEON SIMD + cache-blocking + public chance sampling (Rust)

- **Branch:** `pr-8-simd-layout-pcs`
- **Prerequisites:** PR 7 merged into `integration`.
- **Locked decisions:**
  - Bench harness lives at `benches/cfr_bench.rs` (Criterion). `benches/baseline.json` is committed and the source-of-truth for "scalar baseline" against which all speedup claims are measured.
- **Spec amendments (2026-05-21):**
  - `HUNLConfig.use_pcs: bool = False` is added to Python side here (PR 6 pre-mirrored this in Rust).
  - Bench spot 3 is the **`64/32/16` tier-2 abstraction** (not "50/64 buckets" — that was a typo in the original spec).
- **Special considerations:**
  - **Hard performance gate: 10× minimum speedup over Rust scalar baseline on Section 2 spot 4 (HUNL flop, standard `Js 9h 6d`, 5 sizes, 256/128/64).** If not met, PR does not ship — open follow-up issue, leave PR 8 unmerged.
  - **First action of Agent B: capture the unoptimized baseline.** Run `cargo bench --release`, commit `benches/baseline.json` BEFORE the optimization work begins. No baseline = no PR 8.
  - PCS path switches DCFR β to 0.5 (deviation from the non-PCS β=0). Diff test must be run on the non-PCS path to maintain bit-for-bit parity with PR 5's Python reference.
  - `unsafe` blocks are allowed ONLY in `simd.rs` intrinsics wrappers with `// SAFETY:` comments. Anywhere else is a must-fix.
  - Run benches on `aarch64-apple-darwin` only (M-series). No x86_64 / Intel.

### PR 9 — HUNL preflop (Python + Rust)

- **Branch:** `pr-9-hunl-preflop`
- **Prerequisites:** PR 8 merged into `integration`.
- **Locked decisions:**
  - End-to-end exploitability target: **< 0.05 BB/hand on the Pio 100 BB cash-game validation fixture** (combined preflop + refinement).
  - Per-stage breakdowns: blueprint < 0.5 BB/100, refined per-subgame < 0.1 BB/100, unrefined < 1 BB/100.
  - Diff-test tolerance: `5e-3` per-action + `1e-3 × base_pot` (was `1e-4` in original spec — aligned to the PR 6/7/8 cluster per consistency review).
- **Spec amendments (2026-05-21):**
  - PR 9 §6 is now **canonical** for the full dispatch composition. PR 3.5 §6 and PR 5 §6 cross-reference back to it.
  - Order: ≤15 BB → PR 3.5 chart; >250 BB → ValueError; postflop → PR 5; preflop → PR 9. The 15 BB short-circuit happens BEFORE the postflop branch (a flop-street request at 1500-chip stacks still hits the chart).
- **Special considerations:**
  - Per-stack-depth solve: separate runs for {25, 50, 75, 100, 125, 150, 175, 200, 250} BB. The 150-200 BB and 200-250 BB tiers REQUIRE tier-tighter abstraction artifacts (`128/64/32` and `64/32/16` respectively). User must re-run `precompute-abstraction --bucket-counts <tier>` for each — NOT bundled.
  - Approach is **blueprint + subgame refinement** (Pluribus pattern). Solving the full preflop+postflop with full menu at full abstraction is RAM-prohibitive on 16 GB.
  - Memory budget: blueprint pass must fit in ~10-14 GB. Profiler from PR 5 reports per-street + per-tree. If blueprint blows budget, tighten per PLAN.md tier table.
  - **2-15 BB regime continues to dispatch to PR 3.5's chart** — PR 9 preflop solver only runs for 15 < stacks ≤ 250 BB. Boundary handoff tested explicitly.

### PR 10 — NiceGUI scaffold

- **Branch:** `pr-10-ui-nicegui`
- **Prerequisites:** PR 9 merged into `integration`.
- **Special considerations:**
  - **First UI PR; first new top-level directory** (`ui/`). The check battery should still pass — `ui/` is added to ruff/black/mypy targets.
  - Adds `nicegui` to `pyproject.toml` `[project.optional-dependencies] ui` (NOT base). Base solver remains usable without NiceGUI.
  - Binds `127.0.0.1` only. No remote access, no auth, no TLS. Documented limitation.
  - **No solver math changes.** The UI consumes existing `SolveResult` and the existing `exploitability` function. Any required adapter goes in `ui/state.py` — NEVER by mutating `poker_solver/`.
  - PR 10 ships browser-served only — `poker-solver ui` opens `http://localhost:8080/`. The native pywebview wrapper is deferred to PR 11.
  - Tests cover UI rendering + button dispatch + range matrix combo mapping. Engine tests untouched.

### PR 11 — Library mode + macOS packaging

- **Branch:** `pr-11-library-packaging`
- **Prerequisites:** PR 10 merged into `integration`.
- **Special considerations:**
  - **Two coupled deliverables**: library (SQLite on-disk persistence) + macOS .dmg installer. Both ship together.
  - **Library:** SQLite at `~/.poker_solver/library.db` (override via `POKER_SOLVER_LIBRARY_PATH` env var). WAL mode. Stdlib only (no new deps for library).
  - **macOS packaging is OPTIONAL for autonomous launch** — the `--skip-signing --skip-notarization` path produces an unsigned `.app` and runs end-to-end without Apple Developer enrollment ($99/yr).
  - **Signed/notarized path requires user-supplied Apple credentials.** This is a user-only step; document the manual sequence in `scripts/build_macos_dmg.sh --help`. Autonomous agents should NOT attempt notarization.
  - PyInstaller added under `[project.optional-dependencies] distribution` (NOT base).
  - First-launch UX: if no abstraction artifact exists in `~/.poker_solver/`, show "run `poker-solver precompute-abstraction` before solving" — flagged in spec consistency review as a missing UX item, recommended ~5 line amendment.
  - Library "row size": ~100 KB/spot. 10K spots = 1 GB. No auto-eviction; user manages disk.
  - **Flag for user before PR 11 launch:** consistency review left I2 (PR 11 §3/§6 missing abstraction-artifact-missing UX) and N5 (PR 4 §10 "may bundle in wheel" rejected by PR 11 §6.2). Recommended spec amendments before launching agents.

### PR 12 — 3-handed postflop (OPTIONAL / stretch)

- **Branch:** `pr-12-three-handed`
- **Prerequisites:** PR 11 merged into `integration` AND user explicit go-ahead (this is the explicitly optional stretch milestone per PLAN.md §2).
- **Locked decisions:**
  - LCFR (Linear CFR) for iterations 1..t_cutoff, then vanilla CFR. **NOT DCFR** — DCFR's β=0 (truncating negative regret) is a 2p0s heuristic with no n-player guarantee.
  - Card abstraction reused with TIGHTER bucket counts (passed to PR 4's `precompute-abstraction`). No new abstraction pipeline.
- **Special considerations:**
  - **Critical framing rule: NEVER claim "Nash equilibrium" anywhere.** All user-facing copy uses "approximate equilibrium" / "near-equilibrium strategy" / "blueprint." Enforced by string-literal audit in §11 of the spec + a test that scans for forbidden tokens.
  - No PioSolver / GTO Wizard baseline exists — PioSolver is HU-only. Optional cross-validation against MonkerSolver only if user supplies fixtures (decorator `@pytest.mark.skipif(not Path('tests/fixtures/monker/').exists())`).
  - **No 3-handed preflop solve.** Postflop subgame only — fixed flop/turn/river start. 3-handed preflop is astronomically larger and out of v1 scope.
  - 4+ player: clear `NotImplementedError` raised at the dispatch point. Never silent.
  - Diagnostic only: per-pair best-response gaps (P0 vs joint{P1,P2}, P1 vs joint{P0,P2}, P2 vs joint{P0,P1}). Labelled "≈ best-response upper bound" — NOT Nash distance.
  - Skipping this PR entirely is acceptable — v1 deliverable is HUNL postflop + preflop. 3-handed is bonus.

---

## Failure modes and remediation

### Agent A finishes but interface drifts vs Agent B

**Symptom:** Agent C's tests fail with `AttributeError` or `TypeError` against Agent A's or Agent B's modules.

**Diagnosis:**
1. Find the failing test. Read the call signature it uses.
2. Read the actual signature in Agent A's / Agent B's module.
3. Cross-reference both with `prN_spec.md` §6 "Files to create" — that is canonical.

**Remediation:** rewrite whichever agent diverged FROM the spec to match it. Document the drift + resolution in `docs/autonomous_log.md` with an S-tag.

**Real example (PR 3, S2 in autonomous_log.md):** Agent B used nested `config + is_preflop`; Agent C used flat fields per spec. Resolution: Agent B's `action_abstraction.py` rewritten to flat fields. 30-line touch.

### `pytest -x` fails after agents land

**Diagnosis tree:**

1. **`ImportError`** → an agent created a module another agent imports under a wrong name. Check `__init__.py` exports.
2. **`AttributeError` on `HUNLConfig` / `SolveResult`** → an agent forgot to add a new field, or used the wrong type. Check spec §6 amendments.
3. **`AssertionError` in a closed-form test** (Kuhn `-1/18`, Leduc value) → algorithmic regression. STOP. Bisect.
4. **`AssertionError` in a diff test** → Rust ↔ Python tolerance violated. Check tolerance in spec; fix the implementation.
5. **`KeyError` on bucket lookup** → abstraction artifact path mismatch or stale cache. Re-run from clean.

**Don't proceed past Step 4 (Resolve interface drift) until `pytest -x` is fully green.**

### Check battery flags new lint

**Decision: fix in this PR vs defer to follow-up?**

- **Auto-fixable** (`ruff check --fix --unsafe-fixes`, `black`): fix in this PR. Re-run check battery.
- **Manual lint** (e.g., `mypy` type errors): if it touches files this PR owns, fix in this PR. If it touches files this PR didn't modify but check_pr.sh now flags, defer with a TODO and a `mypy: ignore[code]` comment.
- **New `clippy` warnings** in Rust: fix in this PR. Zero-warnings policy.

### Audit returns must-fix

**Hard stop. Do not commit, do not push, do not merge.**

Remediation:
1. Read the audit's must-fix items carefully.
2. For each: either (a) fix narrowly in the current PR branch, or (b) the must-fix is a misread of the spec — leave a note in `docs/autonomous_log.md` explaining why, and proceed only if the audit's reading is wrong (rare).
3. Re-run check battery.
4. Re-run audit IF you made non-trivial changes (>50 LOC); the audit agent re-checks must-fix on a re-run.
5. Then commit.

### Force-push fails because remote diverged

**Symptom:** `git push --force-with-lease` rejects with "stale info."

**Diagnosis:** someone (or a parallel session) pushed to the same branch between your fetch and your push.

**Recovery:**
```sh
git fetch origin
git log --oneline HEAD..origin/<branch>     # see what they added
```

If their changes are compatible with yours: rebase your changes on top of theirs, then `--force-with-lease` again.

If their changes conflict semantically: STOP. Resolve with the user. Never blindly force-push over another author's work.

### `integration` branch merge conflicts on `--no-ff`

**Symptom:** `git merge --no-ff pr-N-...` reports conflicts.

**Diagnosis:** PR N modified the same lines as a parallel PR merged to `integration` since you branched.

**Resolution:** abort, rebase PR N onto current `integration` tip, re-run pytest, then re-attempt merge.

```sh
git merge --abort
git checkout pr-N-<short-title>
git rebase integration
# resolve conflicts; git rebase --continue
pytest -x
git checkout integration
git merge --no-ff pr-N-<short-title>
```

If the rebase is destructive enough to need force-push of the PR branch, escalate to user OK (force-push rule).

### PR-branch push rejected by GitHub

**Most common cause:** branch name typo. The branch name MUST match exactly what the audit prompt hard-codes (see `pr-N-<short-title>` table above).

**Second most common:** large file in commit. Run `git log -p --stat -1 | head -50` to find oversize blobs (anything >10 MB). The PR 4 `abstraction_v1.npz` artifact (~100 MB) should NEVER be committed — it's a build artifact. Add to `.gitignore` if it slipped in.

---

## Quick-reference command snippets

### Branch operations

```sh
# Create PR branch from integration:
cd /Users/ashen/Desktop/poker_solver
git checkout integration && git pull --ff-only origin integration
git checkout -b pr-N-<short-title>

# Push PR branch first time:
git push -u origin pr-N-<short-title>

# Merge into integration:
git checkout integration
git pull --ff-only origin integration
git merge --no-ff pr-N-<short-title> -m "Integration: merge PR N (<short title>)"
git push origin integration

# Delete merged PR branch locally (only after integration push succeeds):
git branch -d pr-N-<short-title>            # [CAREFUL] — uses -d not -D; refuses if unmerged

# Recover from a botched local state using reflog:
git reflog --date=iso | head -20            # find the hash you want to return to
git reset --hard <hash>                     # [DANGEROUS] — only on local branches, never main
```

### Test + lint operations

```sh
# Full check battery:
sh /Users/ashen/Desktop/poker_solver/scripts/check_pr.sh

# Quick pre-commit Python check (faster than full battery):
cd /Users/ashen/Desktop/poker_solver
pytest -x -q
ruff check poker_solver tests
black --check poker_solver tests
mypy poker_solver

# Auto-fix:
ruff check --fix --unsafe-fixes poker_solver tests
black poker_solver tests

# Run a single failing test with verbose output:
pytest tests/test_<file>.py::test_<name> -xvs

# Run just the PR's new test file:
pytest tests/test_<new_file>.py -xv

# Rust tests + lint:
cargo test --all
cargo clippy --all-targets -- -D warnings

# Rust bench (PR 8+ only):
cargo bench --release
```

### Status + history

```sh
# What's on this branch vs integration:
git log --oneline integration..HEAD

# Diff against integration:
git diff integration...HEAD

# Status of all PR branches on the remote:
git branch -r | grep '^  origin/pr-'

# Last 10 integration commits:
git log --oneline -10 integration

# Compare integration to main (drift):
git log --oneline main..integration

# What touched a specific file recently:
git log --oneline -10 -- poker_solver/<file>.py
```

### Recovery / verification idioms

```sh
# Before any destructive op: record the current tip hash:
git rev-parse HEAD > /tmp/<branch>_pre_<op>.hash

# Verify clean working tree before commit:
git status        # expect: "nothing to commit, working tree clean" after stages

# Check what is staged vs unstaged:
git diff --staged --stat
git diff --stat

# Inspect a remote branch without checkout:
git fetch origin
git log --oneline origin/pr-N-<short-title> -10

# Dry-run a push (see what would happen):
git push --dry-run origin pr-N-<short-title>
```

### Agent launch idioms (orchestrator-only)

```
# Each agent prompt file has this structure:
#   # Header (do not include)
#   ---
#   <prompt body — copy this>
#   ---
#
# To launch: read agent_X_prompt.md, extract body between '---' markers,
# pass as the prompt= arg to a fresh general-purpose Agent.
#
# Launch ALL implementation agents (typically 3) in the SAME tool-call wave.
# Launch ALL downstream / parallel agents (specs, audits, polish) in the SAME wave.
# Aggregate per wave; do NOT react agent-by-agent.
```

---

## Reference: file paths the runbook touches

- `/Users/ashen/Desktop/poker_solver/PLAN.md` — trajectory table updates (§2).
- `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — progress log + S-tag decision records.
- `/Users/ashen/Desktop/poker_solver/docs/prN_prep/prN_spec.md` — canonical spec for PR N.
- `/Users/ashen/Desktop/poker_solver/docs/prN_prep/agent_{a,b,c}_prompt.md` — implementation agent prompts.
- `/Users/ashen/Desktop/poker_solver/docs/prN_prep/audit_prompt.md` — audit agent prompt.
- `/Users/ashen/Desktop/poker_solver/docs/prN_prep/audit_report.md` — written by audit agent.
- `/Users/ashen/Desktop/poker_solver/scripts/check_pr.sh` — check battery.
- `/Users/ashen/Desktop/poker_solver/pr_report.md` — written by check_pr.sh at repo root.
- `/Users/ashen/Desktop/poker_solver/benches/baseline.json` — Rust perf baseline (PR 8+).
- `~/.claude/plans/poker_solver.md` — master plan (mirror to local PLAN.md per plan-sync rule).
