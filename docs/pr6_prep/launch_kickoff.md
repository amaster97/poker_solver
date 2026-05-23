# PR 6 launch kickoff — Rust HUNL postflop port

**Status:** PRE-STAGED PLAYBOOK. Do NOT execute until PR 5 has merged to `integration` and the user has approved firing PR 6.

**Purpose:** the exact command sequence + agent fan-out the orchestrator runs when PR 5 lands and PR 6 is next on deck. This doc collapses §0–§8 of `docs/pr_launch_runbook.md` against the PR 6-specific shape into a single executable transcript so launch is mechanical, not improvisational.

**Branch:** `pr-6-rust-hunl-port` (per `pr_launch_runbook.md` §"PR 6" + PLAN.md §1 "Per-PR feature branches from PR 3 onward").

**Inputs that govern this playbook:**
- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/pr6_spec.md`
- Agent prompts: `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/agent_{a,b,c}_prompt.md`
- Audit prompt: `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/audit_prompt.md`
- Launch-readiness verdict: `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/launch_readiness_v3.md` (READY — 7/7 v2 checks PASS + 3/3 follow-ups confirmed)
- Universal runbook: `/Users/ashen/Desktop/poker_solver/docs/pr_launch_runbook.md`

---

## 1. Pre-flight gate (run BEFORE branch creation)

All five checks must pass. If ANY fails, stop and resolve before continuing.

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. PR 5 is committed AND merged to integration.
git fetch origin
git log --oneline integration -5
# Expected: the topmost commit is "Integration: merge PR 5 (hunl-postflop)"
# (or equivalent --no-ff merge of pr-5-hunl-postflop). If not, PR 5 has not
# fully landed; do not launch PR 6.

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

# 1d. All PR 6 prompts up to date (per launch_readiness_v3.md verdict).
ls -la docs/pr6_prep/
# Expected files present:
#   pr6_spec.md (~788 lines)
#   agent_a_prompt.md (~562 lines)
#   agent_b_prompt.md (~617 lines)
#   agent_c_prompt.md (~535 lines)
#   audit_prompt.md (~191 lines)
#   launch_readiness_v3.md (verdict: READY)
# If launch_readiness_v3.md verdict is NOT "READY", re-run the readiness
# review before firing. Do NOT launch on a stale v2 verdict.

# 1e. Confirm integration tip hash for the reflog backup (per runbook §0).
git rev-parse integration > /tmp/integration_pre_pr_6.hash
echo "integration tip pre-PR-6: $(cat /tmp/integration_pre_pr_6.hash)"
```

Optional sanity: `pytest -x -q` from `integration` tip — must be green before
branching. If red, PR 5 merge introduced a regression; investigate before
launching PR 6.

---

## 2. Branch creation

Mechanical. Branch name is hard-coded in `audit_prompt.md` — do NOT improvise.

```sh
cd /Users/ashen/Desktop/poker_solver
git checkout integration
git pull --ff-only origin integration   # last sanity check
git checkout -b pr-6-rust-hunl-port
git status   # expect: clean tree, on pr-6-rust-hunl-port
git log --oneline -1  # expect: PR 5 merge commit
```

Branch convention rationale (PLAN.md §1 + runbook §"Per-PR specifics → PR 6"): every PR from PR 3 onward gets its own feature branch from `integration`, NOT `main`. `pr-6-rust-hunl-port` is the exact spelling the audit prompt expects to see in `git diff integration...HEAD` cross-references.

---

## 3. Three-agent fan-out launch (parallel, same wave)

Per `pr_launch_runbook.md` §"Step 2": all three implementation agents launch in the SAME tool-call wave. They are designed to be independent — file-ownership boundaries are locked in each prompt.

For each agent, the prompt is the **full contents of the corresponding `docs/pr6_prep/agent_{a,b,c}_prompt.md` file between the two `---` markers** (NOT the orchestrator header above the first `---`). Do not paraphrase, do not truncate, do not inline — copy the file body verbatim.

**Launch sequence (orchestrator side, all three in one tool-call block):**

```
Agent tool call 1:
  description: "PR 6 Agent A — Rust HUNL game state + flat tree + hand evaluator"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr6_prep/agent_a_prompt.md
           between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true

Agent tool call 2:
  description: "PR 6 Agent B — Rust abstraction loader + solver + PyO3 + Python integration"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr6_prep/agent_b_prompt.md
           between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true

Agent tool call 3:
  description: "PR 6 Agent C — Python↔Rust differential tests + Rust-only correctness"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr6_prep/agent_c_prompt.md
           between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true
```

**Ownership recap (verifies interface lock — do NOT relax these):**

| Agent | Owns (write/create) | May surgically modify | Forbidden |
|---|---|---|---|
| A | `crates/cfr_core/src/hunl.rs`, `hunl_tree.rs`, `hunl_eval.rs`, `crates/cfr_core/tests/hunl_state_unit.rs` | (none) | `abstraction.rs`, `hunl_solver.rs`, `lib.rs`, `Cargo.toml`, any Python, any other test file |
| B | `crates/cfr_core/src/abstraction.rs`, `hunl_solver.rs` | `Cargo.toml` (additive: `ndarray-npy`, `serde`, `serde_json`, `arrayvec`); `lib.rs` (PyO3 bindings); `poker_solver/{solver,hunl,cli}.py` (small additions) | `hunl.rs`, `hunl_tree.rs`, `hunl_eval.rs`, any test file |
| C | `tests/test_hunl_diff.py`, `crates/cfr_core/tests/test_hunl_rust.rs` | (none) | any non-test file |

**Parallel fan-out during agent runtime (per PLAN.md §5 + runbook §"Step 3"):** while A/B/C run, launch independent agents on downstream work so the orchestrator never idles. Candidates:
- PR 7 spec polish / consistency review.
- PR 8 baseline-bench scaffolding research.
- `docs/autonomous_log.md` housekeeping (prune stale entries per the continuous-pruning rule).
- Doc inventory sweep (check if any cross-PR references became stale after PR 5 merge).

Aggregate per wave — do NOT react agent-by-agent. Wait for all three implementation agents to return, then synthesize the result vector in one pass.

---

## 4. Monitor + reconciliation patterns

While agents run, the orchestrator does NOT block. Track agent completion via the standard background-task notification stream. Specific failure signatures to watch for in agent outputs:

### 4a. Cargo build errors

**Symptom:** Agent A or Agent B reports `cargo build --release` failure.

**Common causes for PR 6:**
- Missing crate in `Cargo.toml` (Agent B owns additive edits — Agent A blocks if a crate is needed but not present; should flag, not silently add).
- Wrong PyO3 macro shape (`#[pyfunction]` signature mismatch).
- Lifetime / generic-bound mismatch on `DCFRSolver<G>` consumption (Agent B wires Agent A's `HUNLState` into the generic solver; if `Game` trait bounds aren't matched exactly, this fails loudly).

**Diagnosis:** read the cargo error output; cross-reference to spec §4.1 (HUNLState shape) / §4.5 (solver wiring). Spec is canonical — whichever agent diverged from spec gets corrected.

### 4b. mypy on Python integration

**Symptom:** `mypy poker_solver` reports a type error in `solver.py`, `hunl.py`, or `cli.py` after Agent B's edits.

**Common causes for PR 6:**
- `Optional[AbstractionRef]` vs `Optional[AbstractionTables]` confusion at the `_solve_rust` HUNL branch (PR 4 §6 / spec §6.3 are canonical: it's `AbstractionRef`).
- `_serialize_hunl_config` return type missing `-> str` annotation.
- `--backend` literal-type mismatch on CLI plumbing.

**Diagnosis:** mypy output points at the line; spec §6.1 / §6.2 / §6.3 are canonical for shapes.

### 4c. PyO3 marshalling errors

**Symptom:** Python test fails with `TypeError: <_rust.solve_hunl_postflop> received unexpected ... ` or JSON deserialization error in Rust.

**Common causes for PR 6:**
- JSON shape drift between `_serialize_hunl_config` (Python) and `serde::Deserialize` on `HUNLConfig` (Rust). Field name mismatch (e.g., Python `bet_size_fractions` vs Rust `bet_sizes` — must match exactly).
- `use_pcs` missing from Python serializer (Rust expects it per spec §4.1 + §11 amendment I6). Default `false` if absent on Python side — but the JSON key must be present.
- `target_exploitability: Optional[float]` not threaded through correctly.

**Diagnosis:** dump the JSON Python emits + the Rust `serde_json::Error` line; reconcile field names against spec §4.1 (Rust HUNLConfig) + §6.2 (Python serializer).

### 4d. Diff-test tolerance (1e-3 river, 5e-3 flop)

**Symptom:** `test_hunl_river_subgame_diff_python_vs_rust` or `test_hunl_flop_dry_3size_diff_python_vs_rust_tiny_abstraction` fails the tolerance assertion.

**Diagnostic ladder:**
1. **Run Rust-only roundtrip first.** `test_abstraction_canonicalization_matches_python` and `test_abstraction_lookup_bucket_matches_python` (10K random inputs each) — if EITHER fails, the bucket-lookup seam is broken and downstream diff drift is downstream noise, not the real signal.
2. **`test_hunl_infoset_key_lossless_format` + `..._bucketed_format`.** If infoset keys diverge byte-for-byte, both tiers populate DIFFERENT HashMap keys and the strategies look like they diverge but actually disagree on what to compare. Spec §9 #1 is canonical.
3. **`test_hunl_strength_eval_matches_python`** (1000 random 7-card hands). If comparisons differ, evaluator port has a bug; utility at leaves is wrong; CFR diverges in a way no tolerance can paper over.
4. **Only after 1–3 are clean: examine actual strategy diff.** Per-infoset-per-action max diff. If max diff is 1.5e-3 on river (just over 1e-3 spec) the right move is to find the float-reduction-order divergence (HashMap iteration), NOT to loosen tolerance. Loosening is a spec change — flag to user, do not autonomous.

**Anti-pattern (audit will catch):** silently relaxing tolerance to make a test pass. Spec §7.3 + audit focus area #5 explicitly call this out as must-fix.

---

## 5. Audit + commit pipeline (after all 3 agents report back)

Per `pr_launch_runbook.md` §"Step 4–8". Run audit + check battery in same parallel wave.

### 5a. Interface drift reconciliation (runbook §"Step 4")

After ALL three agents return, run Agent C's tests against Agents A+B's implementation:

```sh
cd /Users/ashen/Desktop/poker_solver
cargo build --release   # confirm Rust builds clean
pip install -e .         # rebuild the PyO3 extension into the venv
pytest tests/test_hunl_diff.py -xvs
cargo test --package cfr_core
```

Typical drift patterns (per `docs/autonomous_log.md` S1–S5 from prior PRs):
- Interface mismatch between Agent A's `HUNLConfig` Rust shape and Agent B's `serde::Deserialize` derive. Rule: spec §4.1 is canonical; whichever agent diverged gets rewritten.
- `ruff`/`black` formatting drift on Agent B's Python edits — auto-fix: `ruff check --fix --unsafe-fixes poker_solver tests && black poker_solver tests`.
- `mypy` Optional/Union edge cases at the `_solve_rust` HUNL branch — fix narrowly.

After all fixes: `pytest -x` MUST be fully green before proceeding to audit.

### 5b. Audit + check battery in parallel (runbook §"Step 5")

```sh
# In orchestrator's main shell:
sh /Users/ashen/Desktop/poker_solver/scripts/check_pr.sh > /tmp/check_pr_output.log 2>&1
```

Concurrently, launch the audit agent:

```
Agent tool call (audit):
  description: "PR 6 audit — fresh reviewer, no implementation context"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr6_prep/audit_prompt.md
           between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true
```

Audit writes its report to `docs/pr6_prep/audit_report.md`. While both run, fan out additional downstream-PR work per parallelization rule.

After both complete:
- Read `pr_report.md` (output of `check_pr.sh`). Confirm "ready for user review" with all gates `OK` or `skip` (NOT `FAIL`).
- Read `docs/pr6_prep/audit_report.md`. **`must-fix` items are a hard stop.** `should-fix` / `nice-to-fix` can be deferred to a follow-up with a TODO.

PR 6-specific must-fix triggers (per audit focus areas):
- AGPL function-body / type-name matches against `postflop-solver` / `TexasSolver` (grep `bunching`, `valid_indices`, `isomorphism_swap`, `flatten_action_tree`).
- `f64` chip values anywhere in `hunl.rs` (must be `i32` cents throughout).
- Banker's rounding wrong (Python `round()` is half-to-even; Rust must use `(x + 0.5).floor() as i32`).
- Diff-test tolerance silently loosened beyond 1e-3 / 5e-3.
- Rust `AbstractionTables` shape diverges from committed PR 4 on-disk layout (e.g., `Vec<u32>` top-level board indices or `HandLookup` packed struct instead of `HashMap<String, u32>` + JSON-parsed dicts).
- `_solve_rust` bypasses `resolve_abstraction_ref()` and reaches into `cfg.abstraction.source_path` directly.
- HUNL Rust elif inserted before the PR 3.5 push/fold short-circuit (violates PR 9 §6 canonical dispatch ordering).
- PyO3 GIL not released (`py.allow_threads(...)` missing).

### 5c. Commit (runbook §"Step 6")

```sh
cd /Users/ashen/Desktop/poker_solver
git status   # verify what is staged; confirm no .env / secrets / .npz blobs slipped in
git add crates/cfr_core/ poker_solver/ tests/ docs/pr6_prep/audit_report.md
git status   # re-verify staged set is exactly the PR 6 surface
git commit -m "$(cat <<'EOF'
PR 6: Rust port of HUNL postflop solver

Ports the Python HUNL postflop solver (PR 5) to Rust at crates/cfr_core/,
exposed via PyO3 as poker_solver._rust.solve_hunl_postflop. Mechanical port:
same DCFR (alpha=1.5, beta=0, gamma=2.0), same tree, same action menu, same
bucket lookups, same chance enumeration. Differences are structural (flat
Vec-indexed tree + native hand evaluator) rather than algorithmic.

License posture: MIT-only Rust source. noambrown (MIT) + slumbot2019 (MIT) +
open_spiel (Apache 2.0) cited where patterns adapted; postflop-solver and
TexasSolver (AGPL) NEVER copied.

Diff-test gates: river subgame 1e-3 per-action, flop fixture 5e-3 per-action
(spec §7.3 canonical across PR 6/7/8/9).

Test result: <X>/<X> pass (was <Y>/<Y> on integration tip).
Audit: <must-fix-count> must-fix, <should-fix-count> should-fix, <nice-to-fix-count> nice-to-fix.
EOF
)"
```

DO NOT use `git add -A` or `git add .`. Stage explicit paths.

### 5d. Push PR branch (runbook §"Step 7")

```sh
git push -u origin pr-6-rust-hunl-port
```

Autonomous per the workflow rules. Branch visible at https://github.com/amaster97/poker_solver/tree/pr-6-rust-hunl-port.

### 5e. Merge into integration (runbook §"Step 8")

```sh
git checkout integration
git pull --ff-only origin integration
git merge --no-ff pr-6-rust-hunl-port -m "Integration: merge PR 6 (rust-hunl-postflop)"
git push origin integration
```

`--no-ff` mandatory (preserves PR-branch lineage in `git log --graph`).

If `git pull --ff-only` reports divergence: STOP. Another session pushed to `integration`. Investigate before merging — never `git merge` blind.

### 5f. Update PLAN.md trajectory (runbook §"Step 10")

In `/Users/ashen/Desktop/poker_solver/PLAN.md` §2 trajectory table: update PR 6's row to `landed on integration` + record branch name. In `docs/autonomous_log.md`: append progress entry with timestamp + commit hash + test count + audit-finding-count.

Per plan-sync rule: if `~/.claude/plans/poker_solver.md` was edited, `cp` to local `PLAN.md` before commit.

---

## 6. Failure modes + recovery (Rust-port specific)

### 6a. PyO3 build issues

**Most common:** `maturin develop` / `pip install -e .` fails after adding new `crates/cfr_core/src/*.rs` modules.

**Causes:**
- New `mod xxx;` declaration missing from `crates/cfr_core/src/lib.rs` (Agent B owns; verify both `mod abstraction;` and `mod hunl;` / `hunl_tree;` / `hunl_eval;` / `hunl_solver;` are declared).
- `#[pyfunction]` signature drift (parameter order/type mismatch between Rust signature and Python call site in `_solve_rust`).
- Missing PyO3 feature on `Cargo.toml` (`pyo3 = { version = "...", features = ["extension-module"] }`).

**Recovery:** read the maturin error trace; spec §5 (PyO3 surface) is canonical for the signature. If the Rust side compiles but Python can't import `poker_solver._rust.solve_hunl_postflop`, the `#[pymodule]` block in `lib.rs` is missing `m.add_function(wrap_pyfunction!(solve_hunl_postflop, m)?)?;`.

### 6b. Bucket file marshalling (JSON-encoded indices in `.npz`)

**Most common:** `load_abstraction` Rust-side fails with `serde_json` parse error.

**Cause:** the on-disk `.npz` format (committed PR 4) is more layered than the original PR 6 spec draft anticipated. `flop_board_index` / `hand_index` / `metadata` are each **JSON-encoded inside a one-element bytes array**, NOT raw NumPy arrays. Per spec §4.4 (2026-05-22 amendment): Rust uses `serde_json::from_slice` on each.

**Recovery:** verify Agent B's loader does:
1. Read the one-element bytes array from the `.npz` via `ndarray-npy`.
2. Call `serde_json::from_slice` on the bytes payload (NOT on the outer NumPy wrapper).
3. Parse into `HashMap<String, u32>` (board_index) / `HashMap<String, HashMap<String, u32>>` (hand_index) / `AbstractionMetadata` (metadata).

If Agent B implemented `Vec<u32>` top-level board indices: that's a must-fix on the AbstractionTables shape — diverges from PR 4's committed on-disk format. Spec §4.4 + audit focus area #3 are canonical.

### 6c. HashMap iteration order causing diff-test noise

**Symptom:** `test_hunl_river_subgame_diff_python_vs_rust` is close-but-not-quite passing — e.g., max diff 1.2e-3 against a 1e-3 tolerance.

**Cause:** Rust's default `std::collections::HashMap` uses a randomized seed; per-iteration regret accumulation order differs from Python's (Python `dict` is insertion-ordered, Rust `HashMap` is not). Float-reduction-tree ordering across iterations diverges enough to push a few infosets past 1e-3.

**Recovery options (preferred → fallback):**
1. **Switch the DCFR regret HashMap to `ahash::AHashMap` with a fixed seed under `#[cfg(test)]`** (per locked default D8). Production stays on `std::collections::HashMap`.
2. **Switch to `BTreeMap` for the regret store under test config.** Slower but deterministic iteration.
3. **Tighten the iteration counter** — sometimes 1000 → 2000 iterations is enough to compress remaining diff below 1e-3 without spec change.
4. **Last resort: flag to user.** If 1–3 don't bring diff under 1e-3 cleanly, spec §7.3 may need an amendment (e.g., 1.5e-3 floor). Do NOT silently amend tolerance — this is a spec change, not an implementation tweak.

### 6d. Hand-evaluator port bugs

**Symptom:** `test_hunl_strength_eval_matches_python` reports comparison divergence on N/1000 random 7-card hands.

**Common bugs:**
- **Card encoding off-by-one.** Python's `card_to_int` is `rank * 4 + suit` with range `[8, 59]`. Rust mirror must match exactly — verify in `hunl.rs::card_to_int`.
- **Hand-category ordering wrong** (straight vs flush, full house vs flush, etc.). Cross-reference `slumbot2019/src/hand_value_tree.cpp` (MIT, safe to study) for canonical ordering.
- **Tie handling.** Python returns `(0.0, 0.0)` on tie at terminal; Rust must too. `Strength::eq` must trip the tie path in `HUNLState::utility`. Audit focus area #14.
- **Best-5-from-7 selection.** Python evaluates all C(7,5)=21 subsets and picks max; Rust port must match. Naive implementation: same C(7,5) enumeration, same max selection.

**Recovery:** for each failing hand from the 1000, dump (cards, Python rank category, Python sub-rank, Rust strength). Cross-reference to `poker_solver/evaluator.py` — Python is ground truth.

---

## 7. Orchestrator decisions needed BEFORE this kickoff fires

None unresolved. Launch-readiness v3 verdict is READY (7/7 v2 checks PASS + 3/3 follow-ups confirmed). The four spec-locked defaults that touched orchestrator-side discretion (D1 scalar CFR, D2 JSON config marshalling, D5 Python recomputes exploitability, D7 1e-3 / 5e-3 tolerance) are locked-with-default per `pr6_spec.md` §11 + the consistency-review record.

If the user wants to revisit any locked default before launch, that is the moment to do so (e.g., escalate to vector CFR — D1). Default: launch as spec'd.

---

## 8. Quick-reference: paths this kickoff touches

- `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/pr6_spec.md` — canonical spec (read end-to-end before launch).
- `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/agent_a_prompt.md` — Agent A prompt body.
- `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/agent_b_prompt.md` — Agent B prompt body.
- `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/agent_c_prompt.md` — Agent C prompt body.
- `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/audit_prompt.md` — audit agent prompt body.
- `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/audit_report.md` — written by audit agent (does not exist pre-launch).
- `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/launch_readiness_v3.md` — READY verdict.
- `/Users/ashen/Desktop/poker_solver/docs/pr_launch_runbook.md` — universal runbook (§"PR 6" row).
- `/Users/ashen/Desktop/poker_solver/PLAN.md` — trajectory table updated post-merge.
- `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — progress entry post-merge.
- `/Users/ashen/Desktop/poker_solver/scripts/check_pr.sh` — check battery.
- `/Users/ashen/Desktop/poker_solver/pr_report.md` — written by `check_pr.sh` at repo root.
- `/tmp/integration_pre_pr_6.hash` — reflog backup hash (pre-flight 1e).
