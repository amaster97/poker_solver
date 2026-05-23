# PR 8 commit pipeline (orchestrator-ready)

**Date:** 2026-05-22
**Trigger:** Fires AFTER (a) the three-agent fan-out completes (Agents A/B/C), (b) the audit at `docs/pr8_prep/audit_report.md` returns READY or READY-WITH-PATCHES, AND (c) any must-fix patches from the audit have been applied + re-verified.
**Mode:** Document-only. Nothing in this file should be executed by reading it. The orchestrator dispatches each section as a one-shot agent invocation per `feedback_orchestrator_only` + `feedback_agent_scheduling`.
**Pattern source:** mirrors `docs/pr7_prep/commit_pipeline_v2.md`; adapts for PR 8's unique two-commit-sequence requirement (baseline first, then implementation) per spec §2 + Decision 11.9.

---

## 1. Pre-flight verification (run AFTER all patches land)

The orchestrator runs all six checks below as a single read-only verification agent (no edits, no stages). Halt on the first failure; do NOT continue to §2.

### 1.1 Must-fix items resolved

Per `docs/pr8_prep/audit_report.md` Must-fix section, confirm:

- Every must-fix item flagged in the audit report has a corresponding fix commit on `pr-8-neon-simd-pcs` (verify via `git log integration..HEAD --grep=fix --oneline`).
- Re-run focused tests for each patched area: `cargo test --package cfr_core --test test_simd test_layout test_pcs --release`.
- If audit returned READY (no must-fix), skip to §1.2.

### 1.2 Two-commit baseline-first sequencing gate (audit area 1 — HIGH-PROB)

`git log integration..HEAD --oneline | tac`

Pass condition: chronologically oldest commit is `bench: capture pre-PR-8 baseline ...`; subsequent commit is the PR 8 implementation.

`git show --stat <baseline-commit-SHA>` must show:
- Exactly one file changed: `benches/baseline.json`.
- NO `layout.rs`, NO `dcfr.rs`, NO `simd.rs`, NO `pcs.rs` deltas in this commit.
- Header inside `baseline.json` contains: machine identifier, `sw_vers -productVersion`, `rustc --version`, `git rev-parse HEAD` resolving to the PR 6 integration tip (NOT PR 8 tip), date, criterion version, warm_up=5, samples=20.

Halt condition: baseline bundled with refactor → split-commit required. Use `git rebase -i` is forbidden (per global memory note); instead reset to integration, cherry-pick baseline first, then cherry-pick implementation. Spawn a dedicated split-commit agent to do this safely.

### 1.3 Audit focus areas all confirmed

For each of the 14 focus areas in `audit_prompt_final.md` §"Audit focus areas", confirm `audit_report.md` carries either a "Looks good" confirmation with file:line evidence OR a resolved patch reference. Spot-check the four HIGH-PROB surfaces:

- Area 1 (baseline-first): see §1.2 above.
- Area 2 (SIMD/scalar bit-exact parity): `to_bits()` literal present in `tests/test_simd.rs`.
- Area 3 (PCS importance weight + negative control): `w * K` multiplication in `pcs.rs`; negative-control test asserts divergence.
- Area 8 (10x speedup gate): per-layer breakdown table in `pr_report.md`.

### 1.4 Expected file set

`git diff integration..HEAD --stat` must list (order-insensitive):

```
A  benches/baseline.json          (committed separately per §1.2)
A  benches/cfr_bench.rs
A  crates/cfr_core/src/simd.rs
A  crates/cfr_core/src/layout.rs
A  crates/cfr_core/src/pcs.rs
A  tests/test_simd.rs
A  tests/test_layout.rs
A  tests/test_pcs.rs
A  tests/test_pr8_convergence.py
M  crates/cfr_core/src/dcfr.rs
M  crates/cfr_core/src/hunl_solver.rs
M  crates/cfr_core/src/lib.rs
M  crates/cfr_core/src/solver.rs
M  crates/cfr_core/Cargo.toml
M  poker_solver/hunl.py
M  Cargo.lock
```

After the version-bump bundle in §2, four additional `M` entries will appear: `poker_solver/__init__.py`, `pyproject.toml`, `CHANGELOG.md`, `README.md`. If extra files appear at this gate, halt and audit.

### 1.5 Branch + integration tip

- Current branch: `pr-8-neon-simd-pcs` (confirm with `git branch --show-current`).
- Integration tip: post-PR-7 tip carrying `v0.5.1` tag. Confirm with `git log integration --oneline -1` + `git tag --contains $(git rev-parse integration) | grep v0.5.1`.
- `pr-8-neon-simd-pcs` is rebased onto / branched from this tip — no divergence relative to integration's PR 7 merge.

Halt condition: branch mismatch, integration tip mismatch, or any divergence relative to the PR 7 merge that isn't the PR 8 commits.

### 1.6 Performance evidence captured

- `docs/pr8_prep/pr_report.md` (or branch-root equivalent) exists and contains:
  - Speedup table: per-spot baseline (from `benches/baseline.json`) vs PR-8-tip Criterion result.
  - `hunl_simple_flop` (primary gate) measured >=10x.
  - Per-layer breakdown (SIMD >=3x, layout >=3x, PCS >=3x).
  - Stddev <10% mean per spot.
- If the 10x gate failed → spec §11 Decision 13 8a/8b fallback was triggered → commit message + version-bump bundle must be re-drafted to reflect the reduced scope (e.g., "SIMD + layout only; PCS deferred to PR 9"). Halt the pipeline; re-spawn drafting agents.

---

## 2. Version-bump bundle (v0.6.0 MINOR per `commit_message_draft.md`)

**Rationale:** PR 8 adds new public Python API (`HUNLConfig.use_pcs: bool = False` opt-in field per spec §6 2026-05-21 amendment). Net-additive public surface → MINOR bump, per `docs/pr6_prep/semver_sequencing.md` and the project's MINOR-bump precedent at PR 2 / PR 3 / PR 5 / PR 6. PATCH would imply no public surface change; PR 8 has one, so MINOR is correct. PR 7's v0.5.1 (PATCH, no API change) → PR 8's v0.6.0 (MINOR, `use_pcs` field).

### 2.1 Version constants (two edits, identical bump)

- `poker_solver/__init__.py`: `__version__ = "0.5.1"` → `__version__ = "0.6.0"`
- `pyproject.toml` `[project]`: `version = "0.5.1"` → `version = "0.6.0"`

### 2.2 CHANGELOG.md

- Add new `## [0.6.0] - 2026-05-22` section ABOVE `## [0.5.1]`.
- Move PR 8 content out of `## [Unreleased]` "In progress" bullet — remove the `PR 8:` half from that bullet so `[Unreleased]` is empty except for preflop / NiceGUI / packaging (whatever remains post-PR-9 scope).
- Section body: short blurb mirroring `commit_message_draft.md` "Scope" + "Performance result" paragraphs. Call out the 10x speedup milestone (or 8a/8b split if Decision 13 fallback fired) + the new `use_pcs` field.
- Append link reference at file foot: `[0.6.0]: ./` (matching the existing `[0.5.1]: ./` style).

### 2.3 README.md (per `commit_message_draft.md` §"This commit bundles ...")

- "Current version: 0.5.1" → "Current version: 0.6.0"
- One-line caption update: call out the NEON SIMD + cache-blocked layout + Public Chance Sampling milestone (10x over PR 6 baseline).

### 2.4 Pre-stage sanity

After applying 2.1-2.3:
- `python -c "import poker_solver; print(poker_solver.__version__)"` must print `0.6.0`.
- `grep "^version = " pyproject.toml | head -1` must show `"0.6.0"`.
- CHANGELOG header sequence must read `[Unreleased] → [0.6.0] → [0.5.1] → [0.5.0] → [0.4.0] ...`.

---

## 3. Targeted test gate (NOT full pytest — PR 6 lesson)

Per `commit_pipeline_v2.md` §3 lesson + `feedback_no_extrapolate`: full pytest is 8-15 min on a fresh Rust rebuild and has surfaced false failures on stale `.so`. The pre-commit gate is targeted only; full suite defers to post-merge CI.

### 3.1 Rust extension build
```
cargo build --release --package cfr_core --target aarch64-apple-darwin
```
- Pass: exit 0, clean compile, no warnings on `cfr_core` paths, no manual `RUSTFLAGS` required (compile-time NEON guard).
- Halt: any compile error, missing dep, or `Cargo.lock` drift.

### 3.2 Layered Rust test gate
```
cargo test --package cfr_core --all-targets --release
```
- Pass: 12 PR 6 Rust tests + ~30 new PR 8 tests (test_simd ~14, test_layout ~6, test_pcs ~10) all green.
- Critical canaries (must individually pass):
  - `test_simd::bit_exact_parity_neon_vs_scalar`
  - `test_simd::nan_propagation_neon`
  - `test_simd::signed_zero_preservation_neon`
  - `test_layout::kuhn_hashmap_vs_flat_parity_1e_minus_12`
  - `test_layout::leduc_hashmap_vs_flat_parity_1e_minus_12`
  - `test_pcs::importance_weight_required_or_diverges` (negative control)
  - `test_pcs::seed_7_first_100_cards_match_fixture`
  - `test_pcs::use_pcs_true_sets_beta_half`

### 3.3 Parity-adjacent Python test gate
```
pytest tests/test_pr8_convergence.py tests/test_hunl_diff.py tests/test_river_diff_self_sanity.py tests/test_river_diff.py -v --tb=line --timeout=120
```
- Pass:
  - `test_pr8_convergence.py` — 5 tests pass (Layer D, 5e-3 tolerance).
  - `test_hunl_diff.py` — PR 6 still bit-exact (regression gate; SIMD + layout must not introduce drift).
  - `test_river_diff_self_sanity.py` — PR 7 still green.
  - `test_river_diff.py` — passes if Brown binary built, else SKIPs cleanly.
  - 0 fail, 0 error.

### 3.4 Quick sanity on PR 1-5 surface
```
pytest tests/test_kuhn_dcfr.py tests/test_hunl_postflop_solve.py tests/test_memory_profiler.py -m "not slow" --timeout=60
```
- Pass: 0 fail, 0 error. Catches regressions in pre-PR-6 tiers.

### 3.5 Linter + formatter
- `ruff check poker_solver tests scripts` — exit 0.
- `black --check poker_solver tests scripts` — exit 0.

### 3.6 mypy strict on PR 8 files only
```
mypy --strict poker_solver/hunl.py
```
- Pass: exit 0, zero `error:` lines. (mypy on full tree deferred — out of scope.)

### 3.7 Criterion bench smoke (perf evidence preservation)
```
cargo bench --release --package cfr_core -- --quick   # or equivalent fast-mode
```
- Pass: bench compiles + runs at least one iteration per spot without panicking. Full bench numbers already captured in `pr_report.md` per §1.6.

Halt on any failure in §3.1-§3.7; loop back to patches agent with the specific failure pasted in.

---

## 4. Commit, push, merge

### 4.1 Stage (NOTE: baseline already committed per §1.2)

The baseline.json commit is already on the branch (committed as the FIRST PR 8 commit per §1.2). This section stages the IMPLEMENTATION commit only.

```
git add crates/cfr_core/src/simd.rs crates/cfr_core/src/layout.rs crates/cfr_core/src/pcs.rs
git add crates/cfr_core/src/dcfr.rs crates/cfr_core/src/hunl_solver.rs crates/cfr_core/src/lib.rs crates/cfr_core/src/solver.rs
git add crates/cfr_core/Cargo.toml Cargo.lock
git add poker_solver/hunl.py poker_solver/__init__.py pyproject.toml CHANGELOG.md README.md
git add tests/test_simd.rs tests/test_layout.rs tests/test_pcs.rs tests/test_pr8_convergence.py
git add benches/cfr_bench.rs
```

Use named files (NOT `git add -A`) to avoid sweeping unintended changes. Per `feedback_pr_branches` git-safety: `git add -A` would silently pick up artifacts.

Post-stage: `git diff --cached --stat` must show the file set from §1.4 minus `benches/baseline.json` (already in prior commit).

### 4.2 Commit (the IMPLEMENTATION commit, second of two)

Commit body from `docs/pr8_prep/commit_message_draft.md` via HEREDOC. Title line: `PR 8: NEON SIMD + cache-blocked storage + Public Chance Sampling (v0.6.0)`. Trailer: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.

```
git commit -m "$(cat <<'EOF'
PR 8: NEON SIMD + cache-blocked storage + Public Chance Sampling (v0.6.0)

[... full body from commit_message_draft.md ...]

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Or alternatively: `git commit -F docs/pr8_prep/commit_message_draft.md` (then verify the trailer landed; HEREDOC is the documented-canonical form per memory).

### 4.3 Push feature branch
```
git push -u origin pr-8-neon-simd-pcs
```
- Pass: push succeeds; gh checks (if configured) start cleanly.

### 4.4 Merge into integration

```
git checkout integration
git merge --no-ff pr-8-neon-simd-pcs -m "Integration: merge PR 8 (NEON SIMD + cache-blocked storage + PCS, v0.6.0)"
git push origin integration
git checkout pr-8-neon-simd-pcs
```

`--no-ff` per `feedback_pr_branches` (preserve PR-level boundaries on integration). Return to `pr-8-neon-simd-pcs` after the merge so the shared working tree is back on the PR's branch tip (per `feedback_no_concurrent_branch_ops`).

### 4.5 Tag

After §4.4 succeeds, tag the integration tip without switching the shared tree:

```
git tag -a v0.6.0 integration -m "v0.6.0: PR 8 NEON SIMD + cache-blocked layout + Public Chance Sampling"
git push origin v0.6.0
```

---

## 5. Post-merge 6-branch sync

Per `feedback_pr_branches` + `feedback_no_concurrent_branch_ops`:

1. `git for-each-ref --format='%(refname:short) %(upstream:track)' refs/heads/` — list all local branches and their ahead/behind status.
2. Expected family: `main`, `integration`, `pr-8-neon-simd-pcs`, plus PR 9 / PR 10 spike branches if active.
3. For any branch behind `integration`: if no agent is writing, rebase; if an agent IS writing, defer to a worktree (NEVER branch-switch in the shared tree).
4. Confirm `v0.6.0` tag is on `integration` tip; confirm `main` has NOT advanced.

---

## 6. Failure modes + recovery

### 6.1 10x gate fails on `hunl_simple_flop`
**Symptom:** §1.6 perf evidence shows cumulative <10x or any per-layer <3x.
**Recovery:** Spec §11 Decision 13 8a/8b fallback. Drop PCS to a follow-up PR; re-bench SIMD + layout alone. If 8a clears 10x, re-draft commit message + version bump (still v0.6.0 MINOR if `use_pcs` field still landed but unused; or revisit to v0.5.2 PATCH if no public API change). DO NOT silently relax to <10x.

### 6.2 Baseline bundled with refactor
**Symptom:** §1.2 shows `benches/baseline.json` in the same commit as `simd.rs` / `layout.rs` / `dcfr.rs`.
**Recovery:** Spawn split-commit agent. Reset `pr-8-neon-simd-pcs` to integration; cherry-pick baseline as standalone first commit; cherry-pick implementation as second. DO NOT use `rebase -i` (forbidden per global rules).

### 6.3 SIMD bit-parity regression
**Symptom:** §3.2 `test_simd::bit_exact_parity_neon_vs_scalar` fails on one edge value (likely NaN-quieting or signed-zero loss in horizontal-sum reduction order).
**Recovery:** DO NOT commit. Spawn investigation agent against `simd.rs:?` — preserve summation order; use `vmaxq_f64` (NaN-preserving) not `f64::max` (NaN-quieting). Patch + re-run §3.2 before commit.

### 6.4 PCS negative-control passes (when it should fail)
**Symptom:** §3.2 `test_pcs::importance_weight_required_or_diverges` does NOT fail when `w=K` is removed.
**Recovery:** Tolerance is mis-calibrated OR the importance weight is being silently re-applied elsewhere. Spawn investigation against `pcs.rs:?`; tighten tolerance to where the un-weighted estimator visibly diverges. Re-run §3.2.

### 6.5 Pytest hangs on stale `.so` (PR 6 lesson)
**Symptom:** §3.3 pytest invocation exceeds `--timeout=120`; no test produces output.
**Recovery:**
1. `find . -name "*.so" -newer Cargo.toml` — confirm extension freshness; if stale, `cargo clean -p cfr_core && cargo build --release --package cfr_core` and retry §3.1.
2. If still hanging, fall back to narrowest gate: `pytest tests/test_pr8_convergence.py -v --timeout=60` only. Defer broader regression to post-merge CI.

### 6.6 Version bump drift
**Symptom:** Post-§2 sanity check returns `0.5.1` not `0.6.0`.
**Recovery:** Re-read each file from current state; re-apply the bump using line-content match, not line number. Halt pipeline until print check passes.

### 6.7 8a/8b split required mid-pipeline
**Symptom:** §1.6 confirms 10x gate failed; PCS-related per-layer microbench <3x.
**Recovery:** Spec §11 Decision 13 — ship 8a (SIMD + layout, no PCS); defer PCS to PR 9 or a 8b sub-PR. Re-draft commit message + checklist + pipeline to drop PCS scope; re-bench; re-audit if scope-shift is substantive.

---

## 7. Anchors

- Commit message body: `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/commit_message_draft.md`
- Pre-commit checklist: `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/pre_commit_checklist.md`
- Audit prompt (14 focus areas): `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/audit_prompt_final.md`
- Pre-audit risk forecast: `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/audit_preprep.md`
- Audit report (written by audit agent): `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/audit_report.md`
- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/pr8_spec.md`
- Semver decision precedent: `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/semver_sequencing.md`
- v1 readiness for PR 7 (pattern source): `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/commit_pipeline_v2.md`
- Branch policy: `~/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/feedback_pr_branches.md`, `feedback_no_concurrent_branch_ops.md`
- Extrapolation rule: `~/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/feedback_no_extrapolate.md`
- Orchestrator-only rule: `~/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/feedback_orchestrator_only.md`
