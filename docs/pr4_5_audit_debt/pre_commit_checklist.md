# PR 4.5 pre-commit checklist

**Status:** PRE-STAGED. Run AFTER 3-agent fan-out returns + audit verdict
READY per `docs/pr4_5_audit_debt/audit_prompt_final.md`. BEFORE the
`git commit` call in `docs/pr4_5_audit_debt/commit_message_draft.md`.

**Purpose:** mechanical gate that confirms PR 4.5 is committable. Every
box must be checked; a single FAIL blocks the commit until resolved.

**Time budget:** ~10 min if green path; ~20 min with one minor fix.

---

## 1. Mechanical-only scope verified (HARD GATE)

- [ ] **1a.** Read `docs/pr4_5_audit_debt/audit_report.md` "Scope-creep
  enumeration" section -> confirms **"All edits map cleanly to the 13
  enumerated items"** OR enumerated must-fix items are reverted.
- [ ] **1b.** `git diff integration...HEAD --stat` shows exactly **7
  source files** + at most **1-2 test files** (rake-config exception
  swap 3-C, `test_infoset_key_*` if 4-B surfaces it).
- [ ] **1c.** `git diff integration...HEAD --shortstat` -> net delta
  **< 50 LOC** (`X + Y < 100`, `|X - Y| < 50`). Subtraction-heavy.
- [ ] **1d.** No new behavior change. Per
  `docs/pr4_5_audit_debt/audit_prompt_final.md` HARD GATE -> verified
  zero `must-fix` entries in audit-report "Must-fix" section.
- [ ] **1e.** No new test additions.
  `git diff integration...HEAD -- tests/ | grep '^+def test_'` -> expect
  **zero hits** (only allowed test edits are 3-C + 4-B consequences).
- [ ] **1f.** No docstring expansions beyond the one-line license header
  items (3-A, 3-B, 4-A) and the one-line 4-D kwarg sentinel doc.

## 2. All 13 items addressed

Cross-ref `docs/pr4_5_audit_debt/launch_kickoff.md` sec 2 + audit-report
"Item-by-item verification" section. Each item: PASS in audit report.

PR 3 (Agent A):
- [ ] **3-A** license header on `poker_solver/hunl.py`.
- [ ] **3-B** license header on `poker_solver/action_abstraction.py`.
- [ ] **3-C** `AssertionError -> ValueError` in
  `HUNLConfig.__post_init__` rake validators (lines 107, 109).
- [ ] **3-D** drop unused `field` import (`hunl.py:14`).
- [ ] **3-E** unreachable assert in `enumerate_legal_actions`
  (`action_abstraction.py:210-211`).

PR 3.5 (Agent A):
- [ ] **3.5-A** `PushFoldChartUnavailable(ValueError)` at `pushfold.py:30`.
- [ ] **3.5-B** drop `v1-placeholder` from `PUSHFOLD_CHART_VERSIONS`.
- [ ] **3.5-C** remove dead `_canonical_hand_classes` (`pushfold.py:185`).

PR 4 (Agent B):
- [ ] **4-A** license header on `abstraction/equity_features.py`.
- [ ] **4-B** SHOWDOWN predicate tighten at `hunl.py:336`.
- [ ] **4-C** unreachable assert in `_kmeans_plusplus_init`
  (`emd_clustering.py:188-196`).
- [ ] **4-D** `max_boards_per_street` sentinel kwarg surface in
  `precompute.py:452-455`.

PR 5 (Agent C):
- [ ] **5-A** drop unused `numpy` import + `_ = np` suppression
  (`profiler/memory.py:508-510`).

## 3. pytest unchanged (no regression)

- [ ] **3a.** `pytest -x -q` from branch tip -> **~210 pass / ~10 skip
  / 1 xfail / 0 fail**. Test count equals pre-PR-4.5 baseline.
- [ ] **3b.** Skip count matches baseline (none of the 6 PR-5 skip-marked
  TURN tests unskipped; deferred per launch_kickoff.md sec 3).
- [ ] **3c.** xfail count = 1 (unchanged from baseline).
- [ ] **3d.** Failure count = 0. No flakes; if a test fails, re-run
  isolated; if deterministic, STOP — file follow-up per kickoff sec 10e.
- [ ] **3e.** The rake-config test exception-type swap landed in this
  same commit (3-C consequence per kickoff sec 8a).
- [ ] **3f.** `test_infoset_key_*` updated if 4-B surfaced it (kickoff
  sec 8b); if updating the test reveals a real call site hitting
  SHOWDOWN via `infoset_key`, STOP — revert 4-B, file follow-up.

## 4. ruff + black + mypy clean

- [ ] **4a.** `ruff check` -> zero new warnings on touched files.
- [ ] **4b.** `ruff format --check` -> clean.
- [ ] **4c.** `black --check poker_solver/ tests/` -> clean.
- [ ] **4d.** `mypy --strict poker_solver/` -> clean. Pay attention to
  import-drop sites (3-D `field`, 5-A `numpy`):
  - `grep -n 'field(' poker_solver/hunl.py` -> zero hits.
  - `grep -nE '\bnp\.' poker_solver/profiler/memory.py` -> zero hits.
- [ ] **4e.** No new warnings on `hunl.py`, `action_abstraction.py`,
  `pushfold.py`, `equity_features.py`, `emd_clustering.py`,
  `precompute.py`, `profiler/memory.py`.
- [ ] **4f.** `scripts/check_pr.sh` overall: clean.

## 5. License attribution headers verified

- [ ] **5a.** `grep -nE 'License-posture|third-party code derivation'
  poker_solver/hunl.py poker_solver/action_abstraction.py
  poker_solver/abstraction/equity_features.py` -> **exactly 3 hits**
  (one per file).
- [ ] **5b.** Wording is consistent across the 3 modules (kickoff sec 8d
  aggregator-normalized). Acceptable variation: 4-A may say "equity
  feature is original" instead of "original implementation"; both forms
  reference "no third-party code derivation" identically.
- [ ] **5c.** No license headers added to other files (scope creep).
  `grep -rnE 'License-posture' poker_solver/` -> hit count = 3.
- [ ] **5d.** No `from references/code/...` imports introduced.
- [ ] **5e.** `check_pr.sh` license audit (PLAN.md sec 4 step 6) ->
  no new AGPL/GPL deps.

## 6. Cross-agent file ownership verified

Per `launch_kickoff.md` sec 5a + `fanout_ready.md` sec 3.

- [ ] **6a.** Agent A edits in `poker_solver/hunl.py` -> only at
  lines **14** (3-D), **107 + 109** (3-C), and license header (3-A);
  Agent B edit -> only at **line 336** (4-B). `git blame` confirms
  no overlap.
- [ ] **6b.** Agent A also owns full `action_abstraction.py` +
  `pushfold.py`; no other agent touched these.
- [ ] **6c.** Agent B owns full `equity_features.py` + `emd_clustering.py`
  + `precompute.py`; no other agent touched these.
- [ ] **6d.** Agent C owns only `profiler/memory.py`; no other agent
  touched it.
- [ ] **6e.** `git log integration..HEAD --oneline` shows **no merge-
  conflict-resolution commits** on `pr-4.5-audit-debt-sweep`. Audit-
  report "Cross-agent file-ownership audit" section confirms clean.
- [ ] **6f.** If a manual conflict-resolution commit appears,
  audit-report traces what was resolved + verifies no agent's edit was
  silently dropped.

## 7. 3.5-A consumer-grep gate

- [ ] **7a.** `grep -rn 'except PushFoldChartUnavailable'
  poker_solver/ tests/` -> enumerated in audit report.
- [ ] **7b.** No consumer relies on
  `not isinstance(e, ValueError)` semantics (audit-report check).
- [ ] **7c.** No upstream `except ValueError` handler newly catches
  `PushFoldChartUnavailable` in a way that changes observable behavior
  (audit-report check).

## 8. Unreachable asserts (3-E, 4-C) do NOT trip in CI

- [ ] **8a.** `pytest -x` clean output -> no `AssertionError:
  unreachable; ...` failures.
- [ ] **8b.** If 3-E or 4-C trips: STOP, revert the `assert False`,
  file follow-up must-fix in `docs/audit_followup_backlog.md`. Do NOT
  downgrade to `pass`. (kickoff sec 8c / sec 10c).

## 9. Version + release-artifact bump

- [ ] **9a.** `poker_solver/__init__.py` `__version__ "0.5.1" -> "0.5.2"`.
- [ ] **9b.** `pyproject.toml [project] version "0.5.1" -> "0.5.2"`.
- [ ] **9c.** `CHANGELOG.md`: new `[0.5.2] - 2026-05-22` section above
  `[0.5.1]`, with the 13-item delta enumerated; `[0.5.2]: ./` link
  reference appended.
- [ ] **9d.** `README.md`: "Current version: 0.5.1" -> "0.5.2"; feature-
  line caption acknowledges audit-debt sweep (one-line).
- [ ] **9e.** If a higher PR (e.g., a future PR 7.5) ships between this
  draft and PR 4.5 fire, bump from that tip's version (e.g., `0.6.1 ->
  0.6.2`), NOT from the draft's 0.5.1 baseline.

## 10. Staging + commit hygiene

- [ ] **10a.** `git status` shows expected staged paths only:
  - 7 source files in `poker_solver/`.
  - 0-2 test files (3-C + 4-B consequences).
  - `poker_solver/__init__.py`, `pyproject.toml`, `CHANGELOG.md`,
    `README.md` (version bump).
  - `docs/pr4_5_audit_debt/audit_report.md`.
- [ ] **10b.** `git add` calls use **explicit paths** (NOT `-A` / `.`).
- [ ] **10c.** No `.env`, credentials, or untracked secrets in staged set.
- [ ] **10d.** Commit message ready per
  `docs/pr4_5_audit_debt/commit_message_draft.md`; passed via HEREDOC.
- [ ] **10e.** Co-Authored-By footer present:
  `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
- [ ] **10f.** Reflog backup `/tmp/integration_pre_pr_4_5.hash` exists.

---

**If all boxes checked:** proceed to `git commit ...` per
`commit_message_draft.md`, then sec 9d (push + `--no-ff` merge to
`integration`), then sec 9e (PLAN.md + autonomous-log update + prune
agent fire).

**If any box fails:** halt; resolve before commit; do NOT amend a prior
commit. Failures on 3a / 4d / 5a / 8a are blocking must-fix per
`launch_kickoff.md` sec 9b.
