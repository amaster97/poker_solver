# PR 4.5 commit pipeline (post-audit, orchestrator-ready)

**Date:** 2026-05-22
**Trigger:** Fires once the audit-debt sweep audit clears READY per `docs/pr4_5_audit_debt/audit_prompt_final.md` HARD GATE (zero must-fix entries, all 13 items verified per `docs/pr4_5_audit_debt/pre_commit_checklist.md` §2).
**Mode:** Document-only. Orchestrator dispatches each section as a one-shot agent invocation. Nothing here is auto-executed by reading.
**Scope:** PR 4.5 is mechanical-only (13 audit-debt items across PR 3/3.5/4/5; no public API change, no behavior change, no new tests beyond 3-C / 4-B test-consequence edits). Pipeline is intentionally lighter than `docs/pr7_prep/commit_pipeline_v2.md`: no Rust rebuild step, no full pytest, narrower targeted gate.

---

## 1. Pre-flight (run AFTER audit verdict READY)

Single read-only verification agent. Halt on first failure; do NOT continue to §2.

### 1.1 Audit gate cleared

Per `docs/pr4_5_audit_debt/audit_report.md` (written at fan-out aggregation per `launch_kickoff.md` §9b):
- **Must-fix count = 0** (HARD GATE per `audit_prompt_final.md`).
- All 13 items in `launch_kickoff.md` §2 show PASS in "Item-by-item verification" section.
- Cross-agent file-ownership audit clean (no overlap; no manual merge-conflict commits — per `pre_commit_checklist.md` §6).

### 1.2 Branch + integration tip

- Current branch: `pr-4.5-audit-debt-sweep` (confirm with `git branch --show-current`).
- Integration tip: `d135add` ("Integration: merge PR 7 (river-spot diff vs Brown, v0.5.1)"). Confirm with `git log integration --oneline -1`.
- `pr-4.5-audit-debt-sweep` is branched from / rebased onto `d135add` (no divergence from integration's PR 7 merge).
- Reflog backup `/tmp/integration_pre_pr_4_5.hash` exists per `launch_kickoff.md` §6e.

Halt condition: branch mismatch, integration tip mismatch, missing reflog backup.

### 1.3 Expected file set

`git status --short` must list (order-insensitive) ~8 files modified:

```
M  poker_solver/__init__.py            (3-D field-import drop + version bump)
M  poker_solver/hunl.py                (3-A, 3-C, 3-D, 4-B)
M  poker_solver/action_abstraction.py  (3-B, 3-E)
M  poker_solver/pushfold.py            (3.5-A, 3.5-B, 3.5-C)
M  poker_solver/abstraction/equity_features.py  (4-A)
M  poker_solver/abstraction/emd_clustering.py   (4-C)
M  poker_solver/abstraction/precompute.py       (4-D)
M  poker_solver/profiler/memory.py     (5-A)
M  pyproject.toml                      (version bump)
M  CHANGELOG.md                        (new [0.5.2] section)
?? docs/pr4_5_audit_debt/audit_report.md  (written by audit agent at §9b)
```

Optional: 0-2 test files (rake-config `pytest.raises` swap from `AssertionError` → `ValueError` per 3-C; `test_infoset_key_*` if 4-B surfaces it). Total source-file LOC delta ~+88 / -32 per `commit_message_draft.md` §109. If extra files appear at this gate, halt and audit.

---

## 2. Bump bundle (v0.5.1 PATCH → v0.5.2)

Per `commit_message_draft.md` §8-14 and `docs/pr6_prep/semver_sequencing.md` PATCH rule: backward-compatible mechanical fixes only → PATCH bump. `max_boards_per_street` kwarg (4-D) is opt-in sentinel with default behavior preserved; `PushFoldChartUnavailable(ValueError)` (3.5-A) is base-class widening, backward-compatible. v0.5.1 (PR 7) → v0.5.2 (PR 4.5).

### 2.1 Version constants (two edits, identical bump)

- `poker_solver/__init__.py` L158: `__version__ = "0.5.1"` → `__version__ = "0.5.2"`
- `pyproject.toml` L7: `version = "0.5.1"` → `version = "0.5.2"`

### 2.2 CHANGELOG.md

- Add new `## [0.5.2] - 2026-05-22` section ABOVE `## [0.5.1]` (currently at L15).
- Move PR 4.5 content out of `## [Unreleased]` (L8 onward); empty `[Unreleased]` apart from forward-looking items.
- Section body mirrors `commit_message_draft.md` §41-72: 13-item audit-debt delta, grouped by source-PR (3/3.5, 4, 5). No behavior changes; no spec amendments.
- Append link reference at file foot: `[0.5.2]: ./` (matching existing `[0.5.1]: ./` style).

### 2.3 Pre-stage sanity

After 2.1-2.2:
- `python -c "import poker_solver; print(poker_solver.__version__)"` prints `0.5.2`.
- `grep "version = " pyproject.toml | head -1` shows `"0.5.2"`.
- CHANGELOG header sequence reads `[Unreleased] → [0.5.2] → [0.5.1] → [0.5.0] → ...`.

Note: PR 4.5 does NOT bump `README.md` "Current version:" caption — the audit-debt sweep has no user-facing surface change and README's feature list is unchanged. Diverges from PR 7's bundle which included a README caption update.

---

## 3. LIGHT test gate (NO full pytest — PR 6/7 lesson)

Per `commit_pipeline_readiness.md` PR 7 §3 lesson and `feedback_no_extrapolate.md`: full pytest is 8-15 min on fresh Rust rebuild with stale-`.so` false-failure mode. PR 4.5 is pure-Python mechanical → no Rust rebuild needed; gate stays narrowly targeted. Full suite defers to post-merge CI.

### 3.1 Linter + formatter (~10s)

- `ruff check poker_solver tests scripts` — exit 0.
- `black --check poker_solver tests scripts` — exit 0.

Pass condition: zero new warnings on the 7 touched `poker_solver/...` files (`pre_commit_checklist.md` §4a-§4e).

### 3.2 Targeted pytest (~1 min)

`pytest tests/test_pushfold.py tests/test_hunl_tree.py tests/test_abstraction_buckets.py -m "not slow" --tb=line --timeout=60`

Rationale: these three test files cover the highest-touched surfaces in this PR — `pushfold.py` (3.5-A/B/C), `hunl.py` (3-A/C/D, 4-B) via tree construction, and the abstraction trio (4-A/C/D). 3-E and 5-A surfaces are linter-/mypy-covered only (no dedicated test file).

Pass condition:
- 0 fail, 0 error across the three files.
- Test count + skip count match pre-PR-4.5 baseline (no test deletions; only allowed test edits per `pre_commit_checklist.md` §3e/§3f).
- `test_pushfold.py` exception-type swap landed (3-C consequence) — `pytest.raises(ValueError)` not `AssertionError`.

Halt condition: any fail/error; deterministic flake; unexplained skip-count drift.

### 3.3 mypy strict on edited files only (~5s)

`mypy --strict poker_solver/hunl.py poker_solver/action_abstraction.py poker_solver/pushfold.py poker_solver/abstraction/equity_features.py poker_solver/abstraction/emd_clustering.py poker_solver/abstraction/precompute.py poker_solver/profiler/memory.py`

Pass condition: exit 0, zero `error:` lines. Pay attention to import-drop sites per `pre_commit_checklist.md` §4d:
- `grep -n 'field(' poker_solver/hunl.py` → zero hits (3-D `field` import drop is safe).
- `grep -nE '\bnp\.' poker_solver/profiler/memory.py` → zero hits (5-A `numpy` import drop is safe).

mypy on the full tree is deferred — out of scope for this gate per PR 7 precedent.

Halt on any failure in §3.1-§3.3; loop back to fan-out agent for the specific failing file.

---

## 4. Commit + push + merge

### 4.1 Stage

`git add -A` (file list in §1.3 has been audited; bulk add is safe).

Post-stage: `git diff --cached --stat` must show ~10-11 modified files (7 source + 2 version-bump + CHANGELOG + audit_report) per §1.3. If the list deviates, halt and audit per `pre_commit_checklist.md` §10a-§10c.

### 4.2 Commit

`git commit -F docs/pr4_5_audit_debt/commit_message_draft.md`

Commit body is pre-drafted at `docs/pr4_5_audit_debt/commit_message_draft.md` (142 lines, HEREDOC-wrapped). Title line: `PR 4.5: Audit-debt sweep (mechanical fixes across PR 3/3.5/4/5) (v0.5.2)`. Trailer: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.

**DO NOT amend.** If pre-commit hook fails per `feedback_pr_branches.md` global safety protocol, fix-stage-NEW-commit; never `git commit --amend` here. The hook failure means the commit did not happen — amending would modify the previous commit.

### 4.3 Push feature branch

`git push -u origin pr-4.5-audit-debt-sweep`

Pass condition: push succeeds; gh checks (if configured) start cleanly.

### 4.4 Merge into integration

```
git checkout integration
git merge --no-ff pr-4.5-audit-debt-sweep -m "Integration: merge PR 4.5 (audit-debt sweep, v0.5.2)"
git push origin integration
git checkout pr-4.5-audit-debt-sweep
```

`--no-ff` per `feedback_pr_branches.md` (preserve PR-level boundaries on integration). Return to `pr-4.5-audit-debt-sweep` after the merge so the shared working tree is back on the PR's branch tip (per `feedback_no_concurrent_branch_ops.md`).

### 4.5 No tag

Unlike PR 7's pipeline, PR 4.5 does NOT push a `v0.5.2` tag in this pipeline (PATCH bump on a debt-cleanup PR; tag bundles deferred to next feature-PR merge per `docs/pr6_prep/semver_sequencing.md` convention). If the orchestrator's release policy changes, layer the tag in §4.5 of a successor doc — do NOT inline it here.

---

## 5. 8-branch sync verification post-merge

Per `feedback_pr_branches.md` and `feedback_no_concurrent_branch_ops.md`:

1. `git for-each-ref --format='%(refname:short) %(upstream:track)' refs/heads/` — list all local branches and their ahead/behind status.
2. Expected family (8 total): `main`, `integration`, `pr-4.5-audit-debt-sweep`, plus PR 7 (`pr-7-noambrown-diff`, archived but still local), PR 8 / PR 9 / PR 10 spike branches if active, and any PR 11+ prep branches. Confirm count = 8 against `docs/branch_name_final_check.md` if present.
3. Spot-check each spike branch's relationship to the new `integration` tip — typical resolution is rebase. NEVER force-push to `main` (per `feedback_no_concurrent_branch_ops.md`).
4. For any branch currently behind `integration`: if no agent is writing to it, rebase; if an agent IS writing, defer the rebase to a `git worktree` (per `feedback_no_concurrent_branch_ops.md` — no branch switching in the shared tree).
5. Confirm `main` has NOT advanced — we do not auto-promote integration → main per `feedback_pr_branches.md`.

Pass condition: all 8 branches accounted for; no branch silently behind without an agent assigned; main pointer unchanged.

---

## HARD GUARDRAILS (NON-NEGOTIABLE)

- **NO full pytest** — targeted gate only (§3.2). Full suite is post-merge CI per PR 6/7 lesson.
- **NO main merge** — `git merge --no-ff … integration` only (§4.4). `main` advancement requires separate release decision per `feedback_pr_branches.md`.
- **NO force-push** — neither `pr-4.5-audit-debt-sweep` nor `integration`. If the push is rejected, halt and triage per `feedback_no_concurrent_branch_ops.md`.
- **NO amend** — fix-stage-new-commit on hook failure per §4.2.
- **NO scope expansion** — mechanical 13-item list per `launch_kickoff.md` §2 is exhaustive. If §1 surfaces an extra edit, revert it before the commit (per `launch_kickoff.md` §10b).

---

## Anchors

- Audit report (written at fan-out aggregation): `/Users/ashen/Desktop/poker_solver/docs/pr4_5_audit_debt/audit_report.md`
- Audit prompt (HARD GATE definitions): `/Users/ashen/Desktop/poker_solver/docs/pr4_5_audit_debt/audit_prompt_final.md`
- Commit message body: `/Users/ashen/Desktop/poker_solver/docs/pr4_5_audit_debt/commit_message_draft.md`
- Pre-commit checklist: `/Users/ashen/Desktop/poker_solver/docs/pr4_5_audit_debt/pre_commit_checklist.md`
- Launch playbook (canonical scope + ownership + failure modes): `/Users/ashen/Desktop/poker_solver/docs/pr4_5_audit_debt/launch_kickoff.md`
- PR 7 pipeline reference pattern: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/commit_pipeline_v2.md`
- Branch policy: `~/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/feedback_pr_branches.md`, `feedback_no_concurrent_branch_ops.md`
- Semver decision: `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/semver_sequencing.md`
