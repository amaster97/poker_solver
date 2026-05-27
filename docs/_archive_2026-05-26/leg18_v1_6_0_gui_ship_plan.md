# LEG 18 — v1.6.0 GUI Ship Plan (MINOR bundle: PR 24a + PR 24b — Gate 2 UI completeness)

**Date staged:** 2026-05-23 · **Status:** PRE-STAGED (read-only investigation, plan-only).
**Previous release:** v1.5.1 (`b5777f2`) on `origin/main`.
**Filename:** `docs/leg18_v1_6_0_gui_ship_plan.md` (authoritative).

**Bump:** **MINOR (1.5.1 → 1.6.0).** Reason: PR 24a + PR 24b add user-visible GUI capabilities (RvR panel, 4-tier slider, node-locking editor, asymmetric input, range polish, chart presets, honest chart labels). Per semver § "added functionality in a backward-compatible manner" + per `feedback_ui_packaging_sync`: feature PRs trigger PR 11 .dmg rebuild downstream; v1.6.0 is the appropriate boundary for the UI-completeness milestone.

> **Branches bundled:**
> 1. **PR 24a** `feature/pr-24a-gui-rvr-slider` @ `8b1f672` (4 commits on top of `dc3df6c` v1.5.0) — RvR panel, hero_player selector, 4-tier slider, chart subtitle labels. 7 new smoke tests in `tests/test_ui_pr24a.py`.
> 2. **PR 24b** `feature/pr-24b-gui-nodelock-asym` @ `98c3013` (9 commits on top of `dc3df6c` v1.5.0 — 5 from 24b plus 4 inherited from 24a) — node-locking editor, asymmetric `initial_contributions` UI, range editor polish, chart presets, push/fold remediation. 9 new smoke tests in `tests/test_ui_pr24b.py`.
>
> **Stacking fact (CRITICAL — drives the single-range cherry-pick recommendation):** PR 24b's branch tip `98c3013` already contains all 4 of PR 24a's commits as its base layer. Verified at plan time:
>
> ```
> $ cd /Users/ashen/Desktop/poker_solver_worktrees/pr-24b-gui-nodelock-asym
> $ git log feature/pr-24b-gui-nodelock-asym ^origin/main --oneline | wc -l
> 9                            # 4 from 24a + 5 from 24b
> $ git log feature/pr-24b-gui-nodelock-asym ^origin/main --oneline
> 98c3013 PR 24b (5/5): measured slider tooltip + 9 smoke tests + implementer notes
> b87e315 PR 24b (4/5): range editor polish + chart preset library
> 8c86f3d PR 24b (3/5): asymmetric initial_contributions UI input
> 14ebb89 PR 24b (2/5): node-lock editor dialog + tree-browser hook + run-panel locks list
> 8243978 PR 24b (1/5): state + asymmetric contributions + node-lock plumbing
> 8b1f672 PR 24a (4/4): smoke tests + implementer notes + ruff format pass
> 9ba6c4e PR 24a (3/4): hero seat selector + RvR matrix render + hero swap
> 52f07a0 PR 24a (2/4): add RvR toggle + 4-tier slider + chart subtitle
> 5d54d0c PR 24a (1/4): wire range-vs-range + hero_player into ui.state
> ```
>
> **Implication:** a single cherry-pick range `origin/main..feature/pr-24b-gui-nodelock-asym` replays all 9 commits in order, atomically. This is materially simpler than the LEG 17 / LEG 16 multi-PR pattern and is the **recommended path** (§2c).
>
> **Base-branch alignment note:** Both branches are based on `dc3df6c` (v1.5.0). `origin/main` is now at `b5777f2` (v1.5.1). The branches will replay onto v1.5.1's HEAD; the v1.5.1 base advance is verified disjoint from 24a/24b's touched file set (§3 conflict matrix). Cherry-pick will replay cleanly without rebase-fix.

---

## 0. Hard rules in force on this plan doc

- This file is READ-ONLY guidance. Ship agent at ship-time executes the steps; this doc does not.
- DO NOT cherry-pick anything, DO NOT push, DO NOT tag during plan authoring.
- All SHAs in this plan are CONFIRMED at stage time (no placeholders).

---

## 1. Pre-flight checks

Run from `/Users/ashen/Desktop/poker_solver` (shared tree) unless noted.

### 1a. Shared tree state — verify alignment with origin/main

```bash
cd /Users/ashen/Desktop/poker_solver
git fetch origin
git status --short              # expect: only untracked PLAN.md / docs/ / examples/ / scripts/ etc.
git log --oneline -1            # expect: b5777f2 (v1.5.1) — confirmed clean at stage time
git rev-parse origin/main       # expect: b5777f22f99ee3b912822c0fb30d771dd03954df
```

**Per LEG 12 / LEG 14 / LEG 17 precedent:** operate in a dedicated `ship-v1.6.0` worktree off `origin/main`. The shared tree is currently AT `b5777f2` (v1.5.1) per the LEG 17 ship report.

### 1b. Branch SHAs (confirm at ship time — match stage-time snapshot)

```bash
# PR 24a — confirmed at stage time
cd /Users/ashen/Desktop/poker_solver_worktrees/pr-24a-gui-rvr-slider
git rev-parse HEAD
# expect: 8b1f6722e6b1af99055216cf9f3d9746db890402
git log --oneline dc3df6c..HEAD
# expect 4 commits:
#   8b1f672  PR 24a (4/4): smoke tests + implementer notes + ruff format pass
#   9ba6c4e  PR 24a (3/4): hero seat selector + RvR matrix render + hero swap
#   52f07a0  PR 24a (2/4): add RvR toggle + 4-tier slider + chart subtitle
#   5d54d0c  PR 24a (1/4): wire range-vs-range + hero_player into ui.state

# PR 24b — confirmed at stage time (INCLUDES all 4 of 24a)
cd /Users/ashen/Desktop/poker_solver_worktrees/pr-24b-gui-nodelock-asym
git rev-parse HEAD
# expect: 98c30134781f6906f8b3450f26a753e725e3eb07
git log --oneline dc3df6c..HEAD | wc -l
# expect: 9 (4 from 24a + 5 from 24b)
```

If any SHA drifts: STOP — implementer rebased; re-stage required.

### 1c. Stacking verification (CRITICAL — drives single-range cherry-pick)

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/pr-24b-gui-nodelock-asym
git merge-base feature/pr-24a-gui-rvr-slider feature/pr-24b-gui-nodelock-asym
# expect: 8b1f6722e6b1af99055216cf9f3d9746db890402 (= PR 24a tip)
git log --oneline 8b1f672..98c3013 | wc -l
# expect: 5 (the 5 PR 24b commits stacked on top of PR 24a)
```

If `merge-base` ≠ `8b1f672`: stacking has broken (e.g., implementer rebased one branch but not the other) — fall back to the two-step cherry-pick (§2c alternate path).

### 1d. Sanitization scan (per `feedback_public_repo_hygiene`)

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/pr-24b-gui-nodelock-asym
git diff dc3df6c..98c3013 | grep -nE '(/Users/ashen|ashen26@gsb|claude-session|claude_ai_|implementer-agent)' \
  | head -20
# expect: matches only inside docs/pr_proposals/v1_5_pr_24a_implementer_notes.md and
#         docs/pr_proposals/v1_5_pr_24b_implementer_notes.md
# Sanity: ensure no .env / credential / large binary files
git diff --name-only dc3df6c..98c3013 | grep -E '\.(env|key|pem|so|dylib)$' \
  && echo "BINARY OR SECRET FILE — REVIEW" || echo "FILE LIST CLEAN"
```

**Hygiene posture:** `docs/pr_proposals/` is an established public-OK precedent on `origin/main` (e.g., `docs/pr_proposals/v1_5_pr_23_implementer_notes.md` is already public). The new 24a/24b implementer notes follow the same template and contain only:

- Worktree paths under `/Users/ashen/Desktop/poker_solver_worktrees/` (public-OK; widely-published repo path).
- References to "orchestrator" / "implementer" (process terminology already in the public repo, e.g., `feedback_*` references in implementer-notes precedents).

No session IDs, email addresses, or new internal-only paths surfaced. **No sanitization edit required**; document the matched lines in the ship report as expected findings.

**Hard gate:** if the grep surfaces anything OUTSIDE `docs/pr_proposals/v1_5_pr_24a_implementer_notes.md` / `docs/pr_proposals/v1_5_pr_24b_implementer_notes.md` (e.g., a session ID accidentally pasted into `ui/state.py` or a smoke-test file) — STOP and request implementer rewrite or sanitize locally before cherry-pick.

### 1e. Smoke tests in each worktree (independent verification)

Run in parallel (worktrees are independent file systems). Per LEG 14 follow-up: prefer `python -m pytest` over the pyenv shim to avoid arm64/x86_64 launch quirks.

```bash
# PR 24a worktree — 7 new tests
cd /Users/ashen/Desktop/poker_solver_worktrees/pr-24a-gui-rvr-slider
python -m pytest -x tests/test_ui_smoke.py tests/test_ui_pr24a.py -v
# expect: 35/35 UI smokes green (28 baseline + 7 new from 24a)

# PR 24b worktree — 9 new tests on top of 24a's 7 (= 16 from 24a+24b)
cd /Users/ashen/Desktop/poker_solver_worktrees/pr-24b-gui-nodelock-asym
python -m pytest -x tests/test_ui_smoke.py tests/test_ui_pr24a.py tests/test_ui_pr24b.py -v
# expect: 44/44 UI smokes green (28 baseline + 7 from 24a + 9 from 24b)
```

If any test fails in its source worktree: STOP — implementer must fix before cherry-pick.

---

## 2. Ship worktree setup + cherry-pick sequence

Per `feedback_no_concurrent_branch_ops` and per LEG 12 / LEG 14 / LEG 17 precedent.

### 2a. Create ship worktree

```bash
cd /Users/ashen/Desktop/poker_solver
git fetch origin
git worktree add /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.0 -b ship-v1.6.0 origin/main
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.0
git log --oneline -3
# expect head: b5777f2 v1.5.1: test rigor + docs honesty (engine bundle deferred to v1.5.2)
```

### 2b. Symlink the existing `_rust.so` (per LEG 12 / LEG 14 / LEG 17 precedent)

**Maturin rebuild: NOT NEEDED.** Both PR 24a and PR 24b are UI-only changes:

- Zero `crates/cfr_core/` source changes (verified: `git diff --name-only dc3df6c..98c3013 -- 'crates/**'` is empty).
- Zero `pyproject.toml` build-config changes (verified: same `--name-only` query against `pyproject.toml` is empty).
- Zero `Cargo.toml` changes.

The v1.5.1 `_rust.cpython-313-darwin.so` already in the shared tree is byte-identical to what a fresh `maturin develop --release` from the ship worktree would produce (v1.5.1 itself reused the v1.5.0 .so byte-identically per LEG 17 §6). Symlink it (untracked per `.gitignore`; never enters a commit):

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.0
ln -s /Users/ashen/Desktop/poker_solver/poker_solver/_rust.cpython-313-darwin.so \
      poker_solver/_rust.cpython-313-darwin.so
python -c "from poker_solver import _rust; print('rust binding OK', _rust.__file__)"
# Sanity: must resolve to the shared-tree .so via symlink
```

**Remove the symlink before `git worktree remove`** (so it doesn't leave a dangling link) — see §9.

### 2c. Cherry-pick: single-range recommended (alternate: two-step)

**RECOMMENDED PATH — single-range cherry-pick.** Because PR 24b's tip is stacked directly on PR 24a's tip (§1c verifies merge-base), all 9 commits can be replayed in one atomic range. This is materially simpler than the two-step path and removes the order-of-operations risk that two-step entails.

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.0

# Single-range cherry-pick: replays all 9 commits in chronological order
git cherry-pick origin/main..feature/pr-24b-gui-nodelock-asym

git log --oneline -12
# expect (top-down):
#   <new>  PR 24b (5/5): measured slider tooltip + 9 smoke tests + implementer notes
#   <new>  PR 24b (4/5): range editor polish + chart preset library
#   <new>  PR 24b (3/5): asymmetric initial_contributions UI input
#   <new>  PR 24b (2/5): node-lock editor dialog + tree-browser hook + run-panel locks list
#   <new>  PR 24b (1/5): state + asymmetric contributions + node-lock plumbing
#   <new>  PR 24a (4/4): smoke tests + implementer notes + ruff format pass
#   <new>  PR 24a (3/4): hero seat selector + RvR matrix render + hero swap
#   <new>  PR 24a (2/4): add RvR toggle + 4-tier slider + chart subtitle
#   <new>  PR 24a (1/4): wire range-vs-range + hero_player into ui.state
#   b5777f2  v1.5.1: test rigor + docs honesty
#   8b8d181  Honest docs: PR 7 ...
#   5145674  PR 36: profiler test rigor ...
```

If the cherry-pick stops with a conflict marker (NOT EXPECTED per §3 conflict matrix): STOP + report — likely culprit is a v1.5.1 file accidentally touched by 24a or 24b (the v1.5.1 base advance was disjoint at stage time but re-verify at ship time).

**ALTERNATE PATH — two-step cherry-pick** (use only if §1c stacking verification fails):

```bash
# Step 1: 4 commits from 24a
git cherry-pick origin/main..feature/pr-24a-gui-rvr-slider
# Step 2: only the 5 commits unique to 24b (excludes 24a base)
git cherry-pick 8b1f672..feature/pr-24b-gui-nodelock-asym
```

Two-step is identical in result but requires running two commands and watching for an order-of-operations mistake (e.g., cherry-picking `origin/main..24b` after 24a is already in would re-apply the 24a commits and conflict). Single-range avoids this entirely.

---

## 3. Conflict detection

File-touch matrix (each cell = which branch modifies that file; new files marked NEW). All file lists verified at plan time:

```bash
$ cd /Users/ashen/Desktop/poker_solver_worktrees/pr-24b-gui-nodelock-asym
$ git diff --name-only dc3df6c..98c3013
docs/pr_proposals/v1_5_pr_24a_implementer_notes.md
docs/pr_proposals/v1_5_pr_24b_implementer_notes.md
poker_solver/charts/README.md
poker_solver/charts/chart_100bb_bb_defend.json
poker_solver/charts/chart_100bb_btn_3bet.json
poker_solver/charts/chart_100bb_sb_open.json
poker_solver/charts/chart_30bb_sb_jam.json
tests/test_ui_pr24a.py
tests/test_ui_pr24b.py
ui/app.py
ui/state.py
ui/views/node_lock_editor.py
ui/views/range_freq_editor.py
ui/views/range_matrix.py
ui/views/run_panel.py
ui/views/spot_input.py
ui/views/tree_browser.py
```

| File | v1.5.1 base | PR 24a | PR 24b | Notes |
|---|---|---|---|---|
| `docs/pr_proposals/v1_5_pr_24a_implementer_notes.md` | absent | NEW | — | implementer notes |
| `docs/pr_proposals/v1_5_pr_24b_implementer_notes.md` | absent | — | NEW | implementer notes |
| `poker_solver/charts/README.md` | absent | — | NEW | preset chart docs |
| `poker_solver/charts/chart_100bb_bb_defend.json` | absent | — | NEW | preset chart |
| `poker_solver/charts/chart_100bb_btn_3bet.json` | absent | — | NEW | preset chart |
| `poker_solver/charts/chart_100bb_sb_open.json` | absent | — | NEW | preset chart |
| `poker_solver/charts/chart_30bb_sb_jam.json` | absent | — | NEW | preset chart |
| `tests/test_ui_pr24a.py` | absent | NEW | — | 7 smoke tests |
| `tests/test_ui_pr24b.py` | absent | — | NEW | 9 smoke tests |
| `ui/app.py` | present | YES | YES | both touch; stacked editing |
| `ui/state.py` | present | YES | YES | both touch; stacked editing |
| `ui/views/node_lock_editor.py` | absent | — | NEW | node-lock UI |
| `ui/views/range_freq_editor.py` | absent | — | NEW | per-combo freq dialog |
| `ui/views/range_matrix.py` | present | YES | YES | both touch; stacked editing |
| `ui/views/run_panel.py` | present | YES | YES | both touch; stacked editing |
| `ui/views/spot_input.py` | present | YES | YES | both touch; stacked editing |
| `ui/views/tree_browser.py` | present | — | YES | node-lock hook only |

**Cross-base conflict surface — vs. v1.5.1 added files:**

v1.5.1 added: `CHANGELOG.md`, `poker_solver/__init__.py`, `pyproject.toml`, `tests/_equity_helpers.py`, `tests/conftest.py`, `tests/test_equity_helpers.py`, `tests/test_memory_profiler.py`, `tests/test_river_diff_self_sanity.py`. **NONE** of these appear in the 24a+24b touched-file list above. **Cross-base conflict surface: nil.**

**Intra-stack conflict (24a vs 24b on shared files):** since 24b's commits are physically stacked ON TOP of 24a's tip (§1c), git already resolved any same-file edits at commit time on the implementer branch. The cherry-pick onto v1.5.1's HEAD replays the same diffs in the same order; no new conflicts can arise from shared-file ordering.

**Conflict expectation: NONE.** All cross-base file edits are disjoint from v1.5.1's added/changed files; intra-stack conflicts pre-resolved by branch stacking.

### v1.5.1 base interaction check

v1.5.1 (`b5777f2`) is a PATCH release with tests-only / docs-only changes (PR 37 equity helpers, PR 36 profiler tests, PR 32 docs honesty). No `ui/**`, no `poker_solver/charts/**`, no `crates/cfr_core/**` touched. The 24a+24b stack touches only `ui/**`, `poker_solver/charts/**`, `docs/pr_proposals/**`, and `tests/test_ui_*.py`. **Base interaction risk: nil.**

---

## 4. Maturin rebuild — NOT NEEDED

Both PRs are UI-only (Python + JSON only):

- Zero `crates/cfr_core/` source changes.
- Zero `pyproject.toml` build-config changes.
- Zero `Cargo.toml` changes.

Therefore:

- The v1.5.1 `_rust.cpython-313-darwin.so` from the shared tree is byte-identical to what a fresh `maturin develop --release` would produce.
- Per LEG 12 / LEG 14 / LEG 17 precedent, symlink the existing `.so` rather than rebuild.

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.0
ls -la poker_solver/_rust.cpython-313-darwin.so
# expect: symlink → /Users/ashen/Desktop/poker_solver/poker_solver/_rust.cpython-313-darwin.so
```

**Rebuild trigger (informational):** if any future branch in a bundle touches `crates/cfr_core/**` or `pyproject.toml` build-config, run `maturin develop --release`. Not applicable here.

---

## 5. Smoke tests in ship worktree (CRITICAL)

Per LEG 14 follow-up: prefer `python -m pytest` over the pyenv `pytest` shim.

### 5a. Headline UI smoke set (mandatory)

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.0

python -m pytest tests/test_ui_smoke.py \
                 tests/test_ui_pr24a.py \
                 tests/test_ui_pr24b.py -v
```

**Expected: 44/44 GREEN.**
- `tests/test_ui_smoke.py`: 28 baseline UI smokes.
- `tests/test_ui_pr24a.py`: 7 new tests (RvR panel, hero selector, 4-tier slider, chart subtitle).
- `tests/test_ui_pr24b.py`: 9 new tests (node-lock editor, asymmetric input, range polish, chart presets, push/fold remediation).

If any of the 44 fail: STOP + report. Likely culprits:

- **PySide6 / Qt import error:** environment issue, not a cherry-pick regression. Run `python -c "from PySide6 import QtCore; print('Qt OK')"` to verify; if it fails, escalate (not a ship blocker — code itself is correct, environment is broken).
- **`ui/state.py` import error:** could indicate a stacked-edit mid-state inconsistency that didn't surface in either worktree alone. Inspect the diff `git show HEAD -- ui/state.py` and route to implementer.
- **Chart preset file not found:** `poker_solver/charts/*.json` cherry-pick may have placed files in the wrong tree. Verify `ls poker_solver/charts/` shows all 5 new files + the new `README.md`.

### 5b. Regression sweep (recommended for confidence)

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.0
python -m pytest tests/ -v -k 'not slow and not parity_noambrown'
```

**Expected: all non-slow non-Brown-parity tests pass** (same baseline as v1.5.1's 91-passed/5-skipped smoke run per LEG 17 §4, PLUS the 16 new UI tests from 24a+24b = 60-107 passed depending on how the `-k` filter interacts).

If anything that was green on v1.5.1 fails here: STOP and bisect. Most likely culprit would be `ui/state.py` API drift breaking a non-UI test that imports from `ui/` (unlikely — `ui/` is not imported by core tests in v1.5.1).

---

## 6. Version bump + CHANGELOG (MINOR)

### 6a. Files to bump

| File | Current (on origin/main `b5777f2`) | New | How |
|---|---|---|---|
| `pyproject.toml` | `version = "1.5.1"` | `version = "1.6.0"` | Edit |
| `poker_solver/__init__.py` | `__version__ = "1.5.1"` | `__version__ = "1.6.0"` | Edit |
| `crates/cfr_core/Cargo.toml` | check at ship time | bump if it tracks crate version (likely "0.5.0" or "0.6.0" depending on policy) | Edit if needed |
| `Cargo.toml` (root) | no `version` key (workspace manifest) | — | Skip |

**Verification at plan time:**
```
$ grep -n '^version = ' /Users/ashen/Desktop/poker_solver/pyproject.toml
7:version = "1.5.0"      # NOTE: shared tree may show 1.5.0; origin/main is at 1.5.1.
                         # The ship worktree (created off origin/main) WILL read 1.5.1.
$ grep -n '__version__' /Users/ashen/Desktop/poker_solver/poker_solver/__init__.py
192:__version__ = "1.5.0" # same caveat — shared tree may lag.
```

The shared tree at plan-authoring is NOT pulled up to v1.5.1 (see LEG 17 §8 "Optional: catch up shared tree"). The ship worktree is created off `origin/main` directly, so the version string seen there is the canonical v1.5.1 — bump it to v1.6.0.

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.0
grep -n '^version = ' pyproject.toml
# Expected output: 7:version = "1.5.1"
# Edit pyproject.toml: "1.5.1" → "1.6.0"

grep -n '__version__' poker_solver/__init__.py
# Expected output: 192:__version__ = "1.5.1"
# Edit: "1.5.1" → "1.6.0"

grep -n '^version' crates/cfr_core/Cargo.toml
# If [package] version = "0.5.x": bump to "0.6.0" (MINOR alignment).
# If absent: skip.
```

### 6b. CHANGELOG.md — prepend `## [1.6.0]` above `## [1.5.1]`

Open `/Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.0/CHANGELOG.md`. The current top entry on origin/main is `## [1.5.1] - 2026-05-23`. Insert a NEW `## [1.6.0]` section between `## [Unreleased]` and `## [1.5.1]` — do NOT touch the v1.5.1 / v1.5.0 / v1.4.x blocks.

Drop-in markdown (honest framing, public-OK):

```markdown
## [1.6.0] - 2026-05-23

### Added — GUI Gate 2 (UI completeness; PR 24a + PR 24b)

- **Range-vs-range solve panel** (PR 24a) — visual RvR mode with
  `hero_player` selector. New top-of-spot-input toggle wires through
  `ui/state.py` to the existing `solve_range_vs_range_rust` engine
  entry; hero/villain seat assignment is explicit (no implicit P0).
- **4-tier exploitability slider** (PR 24a) — Draft / Standard / Tight /
  Library presets mapped to measured iteration counts
  (200 / 500 / 1000 / 2000 iters respectively, with a measured-runtime
  tooltip per tier). Replaces the previous free-form iter spinner for
  user-facing common cases; spinner remains available under "Custom".
- **"True Nash" vs "blueprint" chart subtitle labels** (PR 24a) —
  honest framing of solve quality on the rendered strategy chart. The
  chart subtitle now identifies whether the strategy displayed is
  blueprint-quality (low-iter, fast) or near-Nash (high-iter, library
  preset). No marketing-language softening.
- **Node-locking editor** (PR 24b) — per-action sliders + lock
  indicators wired into the tree-browser hook. Locked actions persist
  in `ui.state.locked_nodes` and round-trip through engine solves.
  Run-panel surfaces a "locks active: N" summary so the user can see at
  a glance whether a solve is exploitative (locked) or true GTO
  (no locks).
- **Asymmetric `initial_contributions` UI** (PR 24b) — facing-bet
  scenario input. Lets the user enter scenarios where P0 and P1 have
  put in unequal amounts pre-solve (e.g., "P0 facing a 3bet"). Wires
  through to the v1.4.1 PR 22 asymmetric-init engine path.
- **Range editor polish** (PR 24b) — per-combo frequency dialog
  (`ui/views/range_freq_editor.py`) for non-binary range editing, plus
  a 5-chart preset library under `poker_solver/charts/` covering
  100bb BTN 3bet, 100bb SB open, 100bb BB defend, 30bb SB jam, and a
  README describing the chart-source provenance.
- **Push/fold remediation** (PR 24b) — fixes the v1.4 stack-depth
  edge cases the persona tests flagged on jam-or-fold ranges
  (covered by the 9 new smoke tests in `tests/test_ui_pr24b.py`).
- **44 UI smoke tests total** — 28 baseline + 7 new in
  `tests/test_ui_pr24a.py` + 9 new in `tests/test_ui_pr24b.py`. All
  green on the ship worktree.

### Honest scope

- MINOR bump: user-visible new GUI capabilities. NO public CLI/API
  signature changes; NO Python entrypoint additions beyond the
  internal `ui.state` field additions. Engine binary unchanged from
  v1.5.1.
- v1.5.1 `_rust.cpython-313-darwin.so` is reused byte-identically;
  users on v1.5.1 do not need to rebuild Rust for v1.6.0.
- **Engine bundle (PR 33 + PR 34 + PR 35) for true Brown apples-to-apples
  parity remains DEFERRED to v1.5.2.** v1.5.0 acceptance-test status
  is unchanged. GUI is now functionally complete for Gate 2 (UI
  completeness); final persona retest sweep is gated on the engine
  bundle landing.
- Smoke regression: `test_ui_smoke.py` (28) + `test_ui_pr24a.py` (7) +
  `test_ui_pr24b.py` (9) = 44/44 green. Non-slow non-parity-Brown
  test sweep green vs. v1.5.1 baseline (no regressions).
```

### 6c. Commit the release bump

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.0
git add CHANGELOG.md pyproject.toml poker_solver/__init__.py
# Conditionally: git add crates/cfr_core/Cargo.toml
git status --short        # sanity: ONLY CHANGELOG + version files staged + 9 cherry-picks already committed
git commit -m "chore(release): v1.6.0 — GUI Gate 2 (UI completeness; PR 24a + PR 24b)"
git log --oneline -12     # expect: 9 cherry-picks + release bump on top of b5777f2
```

---

## 7. Tag + push sequence

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.0

# Annotated tag
git tag -a v1.6.0 -m "v1.6.0: GUI Gate 2 (UI completeness)"

# Push main commits (9 cherry-picks + release bump) — fast-forward expected
git push origin HEAD:main

# Push tag
git push origin v1.6.0

# Verify
git fetch --tags origin
git tag -l 'v1.6.0'
git ls-remote --tags origin | grep v1.6.0
git log --oneline origin/main -12
```

Expected: `origin/main` advances by 10 commits (9 cherry-picks + 1 release bump). Tag `v1.6.0` is annotated and points to the release-bump commit.

---

## 8. GitHub release

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.0

cat > /tmp/v1.6.0_release_notes.md <<'EOF'
## v1.6.0 — GUI Gate 2 (UI completeness) (MINOR)

**Headline:** A MINOR release closing the GUI Gate 2 milestone with
two bundled feature PRs. PR 24a adds the range-vs-range solve panel,
hero-player selector, 4-tier exploitability slider, and honest
chart-quality labels. PR 24b adds the node-locking editor, asymmetric
initial-contributions UI, range editor polish (per-combo frequency
dialog + 5-chart preset library), and push/fold remediation. 44/44
UI smoke tests green. **Engine bundle for true Brown apples-to-apples
parity (PR 33 + PR 34 + PR 35) remains deferred to v1.5.2.**

### What changed

- **Range-vs-range panel (PR 24a).** Visual RvR mode with explicit
  `hero_player` selector. Wires through `ui/state.py` to the existing
  `solve_range_vs_range_rust` engine entry; no implicit P0.

- **4-tier exploitability slider (PR 24a).** Draft / Standard / Tight
  / Library presets mapped to measured iteration counts (200 / 500 /
  1000 / 2000 iters). Free-form spinner remains available under
  "Custom".

- **Honest chart labels (PR 24a).** Chart subtitle now identifies
  whether the displayed strategy is blueprint-quality (low-iter,
  fast) or near-Nash (high-iter, library preset). No marketing
  softening.

- **Node-locking editor (PR 24b).** Per-action sliders + lock
  indicators wired into the tree browser. Locked actions persist in
  `ui.state.locked_nodes`; run-panel shows "locks active: N" so the
  user can see whether a solve is exploitative or true GTO.

- **Asymmetric `initial_contributions` UI (PR 24b).** Facing-bet
  scenarios (P0 vs P1 unequal pre-solve). Wires through to the
  v1.4.1 PR 22 asymmetric-init engine path.

- **Range editor polish (PR 24b).** Per-combo frequency dialog plus a
  5-chart preset library (100bb BTN 3bet, 100bb SB open, 100bb BB
  defend, 30bb SB jam) with a README describing chart-source
  provenance.

- **Push/fold remediation (PR 24b).** Fixes v1.4 stack-depth edge
  cases on jam-or-fold ranges.

### Honest framing

- MINOR bump: user-visible new GUI capabilities. No public CLI/API
  signature change; no Python entrypoint additions beyond internal
  `ui.state` field additions.
- v1.5.1 `_rust.cpython-313-darwin.so` is reused byte-identically;
  users on v1.5.1 do NOT need to rebuild Rust for v1.6.0.
- **v1.5.0 acceptance-test status is unchanged.** v1.6.0 does NOT
  address the per-action divergence on the Brown apples-to-apples
  acceptance test. The engine bundle that will address it (PR 33 +
  PR 34 + PR 35) is deferred to **v1.5.2** pending the divergence
  diagnosis. GUI is functionally complete for Gate 2 (UI
  completeness); final persona retest sweep is gated on the engine
  bundle landing.
- Smoke regression: 44/44 UI smoke tests green
  (`test_ui_smoke.py` + `test_ui_pr24a.py` + `test_ui_pr24b.py`).
  Non-slow non-parity-Brown sweep green vs. v1.5.1 baseline.

EOF

gh release create v1.6.0 \
  --repo amaster97/poker_solver \
  --latest \
  --title "v1.6.0: GUI Gate 2 (UI completeness)" \
  --notes-file /tmp/v1.6.0_release_notes.md

# Verify
gh release view v1.6.0 --repo amaster97/poker_solver | head -12
```

**Public-OK audit (per `feedback_public_repo_hygiene`):**
- No `/Users/ashen/...` paths in the release notes.
- No session IDs, no PII, no `claude-session` / `claude_ai_*` references.
- No orchestrator/implementer-agent process terminology beyond what is already in the public CHANGELOG.

---

## 9. Cleanup

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.0
# Remove the .so symlink BEFORE worktree removal (don't leave dangling symlink)
rm poker_solver/_rust.cpython-313-darwin.so

# Exit the worktree directory before removing
cd /Users/ashen/Desktop/poker_solver

git worktree remove /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.0
git worktree list      # verify ship-v1.6.0 is gone; the 24a + 24b source worktrees remain
```

Per LEG 12 / LEG 14 / LEG 17 precedent: local `ship-v1.6.0` branch may not delete cleanly with `-d` if the shared tree's `main` ref is stale. **Do NOT force-delete with `-D`** (per memory rule `feedback_no_concurrent_branch_ops`).

### Optional: catch up shared tree

```bash
# Only when no other worktree is mid-write:
cd /Users/ashen/Desktop/poker_solver
git pull --ff-only origin main
```

### Downstream impact (per `feedback_ui_packaging_sync`)

- **PR 10b UI bindings** — v1.6.0 is the first release with the RvR panel + node-lock editor + asymmetric input live on `main`. PR 10b's screen-flow / accessibility audit MUST be re-run on v1.6.0 before any persona retest.
- **PR 11 .dmg rebuild** — feature PRs trigger PR 11 .dmg rebuild. After v1.6.0 ships, kick PR 11 to repackage the bundled Mac .dmg with the v1.6.0 UI.
- **Persona retest** — DO NOT trigger full persona retest yet. Per the CHANGELOG honest-scope note, the final persona retest sweep is gated on the engine bundle (v1.5.2) landing. v1.6.0 is the UI side; v1.5.2 will be the engine side; persona retest fires after both are on main.

---

## 10. Estimated ship time

Based on LEG 17 (3 PRs, no Rust rebuild, single-range-equivalent ship) running ~7 min wall-clock, scaled up modestly for the 2 implementer notes files + 5 chart JSON files + the slightly larger UI diff (~3315 inserts vs. ~830 for LEG 17):

| Step | Time |
|---|---|
| Pre-flight (§1) — SHAs + stacking verify + sanitize + per-worktree smoke | 2-3 min (parallel across 2 worktrees) |
| Ship worktree setup + symlink (§2a-b) | 1 min |
| Single-range cherry-pick (§2c) — 9 commits in one command | 1 min |
| Smoke tests in ship worktree (§5) — 44 UI smokes + regression sweep | 5-8 min |
| Version bump + CHANGELOG + commit (§6) | 3-5 min |
| Tag + push (§7) | 1-2 min |
| GitHub release (§8) | 1-2 min |
| Cleanup (§9) | <1 min |
| **Total** | **15-25 min wall-clock** |

LEG 17 baseline was ~7 min for 3 small PRs. v1.6.0 is larger in surface area (44 UI smokes to run + chart JSON files) but logistically simpler (single-range cherry-pick, no base-mismatch flag, no LEG-re-key follow-up). The 15-25 min estimate matches the prompt's budget and aligns with LEG 14's ~15 min for 4 PRs.

---

## 11. Risk register

| Risk | Probability | Mitigation |
|---|---|---|
| Cherry-pick conflict | Very low | §3 conflict matrix confirms disjoint file sets vs. v1.5.1 base. 24a vs 24b shared-file edits pre-resolved by stacking. |
| Stacking broken (rebase drift) | Low | §1c stacking verification catches this; fall back to two-step cherry-pick (§2c alternate). |
| Smoke-test fail in ship worktree | Low | Each worktree green at stage time; cherry-pick to disjoint base shouldn't change behavior. Likely culprit if it fires: PySide6 / Qt environment issue (not a code bug). |
| Sanitization scan surfaces new PII | Low | §1d expected matches are only inside `docs/pr_proposals/v1_5_pr_24a_implementer_notes.md` / `..._pr_24b_...md`; precedent (PR 23 implementer notes) is already on public main. Hard gate: STOP if anything outside those files matches. |
| Wrong base for 24a's `ui/state.py` edits vs v1.5.1 added `tests/conftest.py` | Nil | Disjoint paths (ui/ vs tests/). |
| Maturin rebuild needed | Nil | UI-only changes; verified zero `crates/**` or `pyproject.toml` build-config touches. |
| Tag v1.6.0 already exists | Nil | `git ls-remote --tags origin` at plan time shows only v1.5.0 and v1.5.1. |
| LEG 16 re-key collision | Nil | LEG 16 (v1.5.2 engine bundle) was already re-keyed to v1.5.2 in LEG 17 §7. v1.6.0 is a separate slot above v1.5.2; no further re-key needed. |

---

## 12. Output: ship report

After ship, the ship agent writes `/Users/ashen/Desktop/poker_solver/docs/leg18_v1_6_0_ship_report.md` following the LEG 17 template:

- §1 Release artifacts (tag SHA, release URL, previous release, commits-on-main delta)
- §2 Execution timeline (wall-clock per step)
- §3 Cherry-pick verification (source SHA → new commit SHA mapping per PR; conflict count)
- §4 Smoke test results (44/44 UI + regression sweep)
- §5 Version bump verification (before/after per file)
- §6 Honest framing in CHANGELOG + release notes (engine-bundle deferred to v1.5.2 explicit)
- §7 LEG 16 / LEG 18 cross-references (no re-key needed for v1.6.0; LEG 16 already re-keyed to v1.5.2 in LEG 17)
- §8 Cleanup status (symlink removed, worktree removed, branch retained)
- §9 Unexpected complexity (expected: none)
- §10 Next steps (PR 11 .dmg rebuild kickoff; PR 10b screen-flow re-audit; persona retest STILL gated on v1.5.2)

---

## 13. Authorization & per-PR branch hygiene

Per `feedback_pr10a5_autonomous_commit` + LEG 17 precedent: PR 24a and PR 24b are audit-cleared (smoke-clean, 44/44 UI tests green); autonomous end-to-end ship (cherry-pick + push + tag + release) is within scope. No exception conditions apply (no force-push, no origin branch deletion, no Type C-CRITICAL findings during ship, no major design decisions deferred).

Per `feedback_pr_branch_hygiene`: the source feature branches `feature/pr-24a-gui-rvr-slider` and `feature/pr-24b-gui-nodelock-asym` on public origin should remain clean (don't push the local `ship-v1.6.0` branch — it's a ship-only artifact). After ship, the source feature branches may be retained for archive (per memory rule against `-D`).

Per `feedback_dual_remote_workflow`: this plan covers the public `origin` push only. Mirror sync to the private `integration` remote is a separate post-ship step handled by the dual-remote sync protocol.
