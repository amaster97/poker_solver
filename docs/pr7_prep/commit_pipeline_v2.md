# PR 7 commit pipeline v2 (post-patch, orchestrator-ready)

**Date:** 2026-05-22
**Trigger:** Fires once the M1 / M2 / M3 patches from `audit_report.md` have been verified per `docs/pr7_prep/patch_verification.md`.
**Mode:** Document-only. Nothing in this file should be executed by reading it. The orchestrator dispatches each section as a one-shot agent invocation.
**Prior:** Supersedes `commit_pipeline_readiness.md` §3 sequence. Differences from v1: drops the full-suite pytest gate (PR 6 lesson — too slow, false-failure mode on stale `.so`); adds explicit per-test-file timeout; pins the version-bump bundle to a single staged delta; locks the integration tip and pre-flight file list.

---

## 1. Pre-flight verification (run AFTER the M1/M2/M3 patches land)

The orchestrator runs all five checks below as a single read-only verification agent (no edits, no stages). Halt on the first failure; do NOT continue to §2.

### 1.1 Must-fix items resolved

Per `docs/pr7_prep/patch_verification.md` §1-3, confirm:

- **M1** — `tests/test_river_diff_self_sanity.py` has `>=8` `def test_` definitions; the `>=4` new tests reference neither `subprocess` nor `_require_brown_binary`; the 10-case canonicalizer round-trip is present and its case-10 expected tuple is `(("b", 1000), ("r", 10000))` (NOT the `2**31 - 1` sentinel).
- **M2** — `grep -n "2\*\*31\|2147483647\|sys.maxsize\|SENTINEL_STACK" poker_solver/parity/noambrown_wrapper.py` returns ZERO matches. `_state_for_default_river_pot(initial_pot: int, initial_stack: int = 9500)` has `initial_stack=9500` default.
- **M3** — prompt §6 Test 4 expected tuples, wrapper emitted values, and self-sanity test hand-built expectations are byte-identical across all 10 cases.

Pass condition: all three audit verifier agents (run in parallel per `patch_verification.md` §5) report PASS.

### 1.2 Self-sanity collection check

`pytest tests/test_river_diff_self_sanity.py --collect-only -q`

Pass condition: exit 0, `>=8` collected test ids.

### 1.3 Self-sanity binary-free run

`pytest tests/test_river_diff_self_sanity.py -v --tb=line --timeout=60`

Pass condition: `>=4` PASS (the new binary-independent tests); the four original `test_brown_binary_*` tests either PASS (if binary built) or SKIP cleanly with directive message; 0 fail, 0 error.

### 1.4 Expected file set

`git status --short` must list exactly (order-insensitive):

```
A  poker_solver/parity/__init__.py
A  poker_solver/parity/noambrown_wrapper.py
A  scripts/build_noambrown.sh
A  tests/data/river_spots.json
A  tests/test_river_diff.py
A  tests/test_river_diff_self_sanity.py
M  pyproject.toml
M  tests/test_hunl_diff.py
```

After the version-bump bundle in §2, three additional `M` entries will appear: `poker_solver/__init__.py`, `CHANGELOG.md`, `README.md`. If extra files appear at this gate, halt and audit.

### 1.5 Branch + integration tip

- Current branch: `pr-7-noambrown-diff` (confirm with `git branch --show-current`).
- Integration tip: `6c438b8` ("Integration: merge PR 6 (Rust port of HUNL postflop solve, v0.5.0)"). Confirm with `git log integration --oneline -1`.
- `pr-7-noambrown-diff` is rebased onto / branched from this tip (no divergence from integration's PR 6 merge).

Halt condition: branch mismatch, integration tip mismatch, or any divergence relative to `6c438b8` that isn't the PR 7 commit-in-progress.

---

## 2. Bump bundle (v0.5.1 PATCH, per `commit_message_draft.md` §27-33)

Per `commit_message_draft.md` and `docs/pr6_prep/semver_sequencing.md`: external-Nash validation oracle is "no public API surface change + validation-only addition" → PATCH bump, NOT MINOR. v0.5.0 (PR 6) → v0.5.1 (PR 7).

### 2.1 Version constants (two edits, identical bump)

- `poker_solver/__init__.py` L158: `__version__ = "0.5.0"` → `__version__ = "0.5.1"`
- `pyproject.toml` L7: `version = "0.5.0"` → `version = "0.5.1"`

### 2.2 CHANGELOG.md

- Add new `## [0.5.1] - 2026-05-22` section ABOVE `## [0.5.0]` (line 16 in current file).
- Move PR 7 content out of `## [Unreleased]` "In progress" bullet (line 13-14) — remove the `PR 7+:` half from that bullet so `[Unreleased]` is empty except for NEON / preflop / NiceGUI / packaging.
- Section body: short blurb mirroring `commit_message_draft.md` §1-16 (river-spot diff vs Brown's MIT solver; 15 spots; subprocess invocation; first external-Nash gate; v0.5.0 contract unchanged).
- Append link reference at file foot: `[0.5.1]: ./` (matching the existing `[0.5.0]: ./` style in the file).

### 2.3 README.md (per `commit_message_draft.md` §32-33)

- "Current version: 0.5.0" → "Current version: 0.5.1"
- One-line caption update noting river-diff oracle validation against Brown's MIT solver.

### 2.4 Pre-stage sanity

After applying 2.1-2.3, `python -c "import poker_solver; print(poker_solver.__version__)"` must print `0.5.1`. `grep "version = " pyproject.toml | head -1` must show `"0.5.1"`. CHANGELOG header sequence must read `[Unreleased] → [0.5.1] → [0.5.0] → [0.4.0] ...`.

---

## 3. Targeted test gate (NOT full pytest — PR 6 lesson)

Per `commit_pipeline_readiness.md` §4 and `feedback_no_extrapolate.md`: full pytest is 8-15 min on a fresh Rust rebuild and has surfaced false failures on stale `.so`. The pre-commit gate is targeted only; full suite defers to post-merge CI.

### 3.1 Rust extension build

`cargo build --release --package cfr_core`

Pass condition: exit 0, clean build, no compilation warnings on `cfr_core` paths.

Halt condition: any compile error, missing dependency, or `Cargo.lock` drift.

### 3.2 Parity-adjacent test gate

`pytest tests/test_river_diff_self_sanity.py tests/test_river_diff.py tests/test_hunl_diff.py -v --tb=line --timeout=120`

Pass condition:
- `test_river_diff_self_sanity.py` — `>=8` tests; `>=4` PASS regardless of Brown binary state; binary-dependent four either PASS or SKIP cleanly.
- `test_river_diff.py` — passes if Brown binary built, otherwise SKIPs cleanly per `pytest.skip(...)` (spec §6 layer 2). Either outcome is acceptable.
- `test_hunl_diff.py` — PR 6 diff; must still PASS post-PR-7 hardening (RuntimeError on stale `.so`).
- 0 fail, 0 error across all three files.

### 3.3 Quick sanity on PR 1-5 surface

`pytest tests/test_kuhn_dcfr.py tests/test_hunl_postflop_solve.py tests/test_memory_profiler.py -m "not slow" --timeout=60`

Pass condition: 0 fail, 0 error. Catches regressions in pre-PR-6 tiers that PR 7 should not be touching.

### 3.4 Linter + formatter

- `ruff check poker_solver tests scripts` — exit 0.
- `black --check poker_solver tests scripts` — exit 0.

### 3.5 mypy strict on PR 7 files only

`mypy --strict poker_solver/parity/__init__.py poker_solver/parity/noambrown_wrapper.py`

Pass condition: exit 0, zero `error:` lines. (mypy on the full tree is deferred — out of scope for this gate.)

Halt on any failure in §3.1-§3.5; loop back to patches agent with the specific failure pasted in.

---

## 4. Commit, push, merge

### 4.1 Stage

`git add -A` (per `commit_pipeline_readiness.md` §3 — the file list in §1.4 + §2 has been audited; bulk add is safe).

Post-stage: `git diff --cached --stat` must show:
- 7 added files (the PR 7 new files from §1.4)
- 4 modified files (`pyproject.toml`, `tests/test_hunl_diff.py`, `poker_solver/__init__.py`, `CHANGELOG.md`, `README.md` — that's actually 5; verify count matches §1.4 + §2)

### 4.2 Commit

Commit body from `docs/pr7_prep/commit_message_draft.md` via HEREDOC. Title line: `PR 7: River-spot diff vs Brown's MIT solver (external Nash validation) (v0.5.1)`. Trailer: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.

### 4.3 Push feature branch

`git push -u origin pr-7-noambrown-diff`

Pass condition: push succeeds; gh checks (if configured) start cleanly.

### 4.4 Merge into integration

```
git checkout integration
git merge --no-ff pr-7-noambrown-diff -m "Integration: merge PR 7 (river-spot diff vs Brown, v0.5.1)"
git push origin integration
git checkout pr-7-noambrown-diff
```

`--no-ff` per `feedback_pr_branches.md` (preserve PR-level boundaries on integration). Return to `pr-7-noambrown-diff` after the merge so the shared working tree is back on the PR's branch tip (per `feedback_no_concurrent_branch_ops.md`).

### 4.5 Tag

After §4.4 succeeds, on `integration` tip (without switching the shared tree — use `git tag v0.5.1 integration` from the current branch):

```
git tag -a v0.5.1 integration -m "v0.5.1: PR 7 river-spot diff vs Brown"
git push origin v0.5.1
```

---

## 5. 6-branch sync verification post-merge

Per `feedback_pr_branches.md` and `commit_pipeline_readiness.md` §5:

1. `git for-each-ref --format='%(refname:short) %(upstream:track)' refs/heads/` — list all local branches and their ahead/behind status.
2. Expected family: `main`, `integration`, `pr-7-noambrown-diff`, plus PR 8 / PR 9 / PR 10 spike branches if active (~6 total per `feedback_pr_branches.md`).
3. Spot-check each spike branch's relationship to the new `integration` tip — typical resolution is rebase, NEVER force-push to `main` (per `feedback_no_concurrent_branch_ops.md`).
4. For any branch currently behind `integration`: if no agent is writing to it, rebase; if an agent IS writing, defer the rebase to a worktree (per `feedback_no_concurrent_branch_ops.md` — no branch switching in the shared tree).
5. Confirm `v0.5.1` tag is on `integration` tip; confirm `main` has NOT advanced (we do not auto-promote integration → main).

Pass condition: all six branches accounted for; no branch is silently behind without an agent assigned.

---

## 6. Failure modes + recovery

### 6.1 Patches reintroduced silent skip

**Symptom:** §1.3 self-sanity run reports `>=4` tests SKIPPED instead of PASSED, where the skip directive is the Brown binary skip (not the new binary-independent tests).

**Cause:** M1 patches landed but introduced `_require_brown_binary()` calls in the new tests (regression).

**Recovery:** Re-spawn patches agent with the message: "`test_river_diff_self_sanity.py` new tests must NOT call `_require_brown_binary` or `subprocess`; strip those gates and re-test." Confirm the fix raises a loud `RuntimeError` if the canonicalizer fails to import — never a silent skip.

### 6.2 Brown binary diff fails empirically

**Symptom:** §3.2 `tests/test_river_diff.py` runs (binary built) but at least one spot fails the tolerance gate (`|our_prob - brown_prob| < 5e-3` or `|our_gv - brown_gv| < 1e-3 * spot.pot`).

**Cause:** Our solver's Nash convergence on the failing spot disagrees with Brown's at 2000 iters AND the canonicalizer is innocent (rule out by re-running §1.3 self-sanity). Likely candidates: (a) action menu disagreement (Brown's bet-sizing differs from ours on a spot category); (b) bucket-abstraction precision loss in the Rust port; (c) Brown's DCFR triple `(1.5, 0, 2)` interpreted differently in his cpp main.cpp than in our `crates/cfr_core/src/hunl_solver.rs`.

**Recovery:** DO NOT commit. Spec amendment is required. Spawn an investigation agent against the specific failing spot(s); produce a delta-bound diagnostic doc; revisit spec §1 tolerance (does 5e-3 hold for our abstraction? is 2000 iters enough?) or spec §4 spot selection (drop the failing spot from the fixture with documented rationale, NOT a silent fix). Commit only after the spec amendment is itself audited.

### 6.3 Pytest hangs (Leduc-style timeouts re-emerge)

**Symptom:** §3.2 or §3.3 pytest invocation exceeds the `--timeout=120` / `--timeout=60` wall clock; no test produces output for >60s.

**Cause:** Either (a) a `cargo build` artifact didn't refresh and an old `.so` is being imported (hang in the Rust solver loop), or (b) Brown subprocess is hanging on a malformed `--dump-strategy` path (test_river_diff.py only).

**Recovery:**
1. `find . -name "*.so" -newer Cargo.toml` — confirm extension freshness; if stale, `cargo clean -p cfr_core && cargo build --release --package cfr_core` and retry §3.1.
2. If still hanging, fall back to the narrowest gate: `pytest tests/test_river_diff_self_sanity.py -v --timeout=60` only. Defer `test_river_diff.py` to post-merge CI with the Brown binary preflighted separately.
3. Do NOT re-add the broader pytest fan-out to this gate — that's the PR 6 lesson. The targeted set in §3.2-§3.3 is the floor.

### 6.4 Version-bump drift

**Symptom:** Post-§2 sanity check (`poker_solver.__version__` print) returns `0.5.0` not `0.5.1`, OR CHANGELOG parse fails.

**Cause:** §2.1 edit applied to wrong line (file structure changed since the readiness doc captured L158 / L7), or `[0.5.1]` section misformatted.

**Recovery:** Re-read each file from current state; re-apply the bump using line-content match, not line number. Halt the pipeline until print check passes.

### 6.5 6-branch sync surfaces silent divergence

**Symptom:** §5 reports a branch behind `integration` with no agent assigned, AND `git log` shows local-only commits on that branch.

**Cause:** A prior agent committed to a feature branch without orchestrator awareness, OR a manual edit happened in the shared tree against the `feedback_no_concurrent_branch_ops.md` rule.

**Recovery:** DO NOT auto-rebase. Inventory the local-only commits (`git log integration..<branch>`); if they are stray work, spawn a triage agent to extract intent and either merge cleanly or extract to a fresh branch. NEVER `git stash drop` after a conflicted pop (per memory rule).

---

## Anchors

- Patch verification: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/patch_verification.md`
- v1 readiness (superseded for §3 only): `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/commit_pipeline_readiness.md`
- Commit message body: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/commit_message_draft.md`
- Audit report: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/audit_report.md`
- Semver decision: `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/semver_sequencing.md`
- Branch policy: `~/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/feedback_pr_branches.md`, `feedback_no_concurrent_branch_ops.md`
