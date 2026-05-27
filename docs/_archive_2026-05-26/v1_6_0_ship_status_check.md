# v1.6.0 Ship Status Check (2026-05-23)

**Status:** MID-SHIP (stalled at step 6c — commit the release bump).
**Filesystem-evidence verdict:** The prior ship executor completed cherry-picks + version-string edits + CHANGELOG edit, but DID NOT commit the release bump, DID NOT tag, DID NOT push. Filesystem state is recoverable in a few commands.

---

## 1. Current state — branch/tag/origin

| Artifact | State | Detail |
|---|---|---|
| Local tag `v1.6.0` | **ABSENT** | `git tag -l 'v1.6*'` empty |
| Remote tag `v1.6.0` | **ABSENT** | `git ls-remote --tags origin v1.6.0` empty |
| `ship-v1.6.0` worktree | **PRESENT** | `/Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.0` @ `0d7ca15` |
| `feature/pr-24a-gui-rvr-slider` | **PRESENT** | local + remote-tracking; tip `8b1f672` |
| `feature/pr-24b-gui-nodelock-asym` | **PRESENT** | local + remote-tracking; tip `98c3013` |
| `origin/main` HEAD | **`9a2a89e`** | 1 commit AHEAD of `b5777f2` (v1.5.1) — `examples: add range-vs-range river solve example` (added at 2026-05-23 15:28 by amaster97) |
| `leg18_v1_6_0_ship_report.md` | **ABSENT** | LEG 11/12/14/15/17 have ship reports; LEG 18 does not — confirms ship never completed |

---

## 2. Ship worktree state (`ship-v1.6.0`)

**HEAD:** `0d7ca15` (PR 24b 5/5: measured slider tooltip + 9 smoke tests + implementer notes).
**9 cherry-picked commits applied** on top of `b5777f2` (v1.5.1):

```
0d7ca15  PR 24b (5/5): measured slider tooltip + 9 smoke tests + implementer notes
f21c371  PR 24b (4/5): range editor polish + chart preset library
8ee658b  PR 24b (3/5): asymmetric initial_contributions UI input
a715cac  PR 24b (2/5): node-lock editor dialog + tree-browser hook + run-panel locks list
88ed9f8  PR 24b (1/5): state + asymmetric contributions + node-lock plumbing
9eed4ff  PR 24a (4/4): smoke tests + implementer notes + ruff format pass
352c04c  PR 24a (3/4): hero seat selector + RvR matrix render + hero swap
6153f00  PR 24a (2/4): add RvR toggle + 4-tier slider + chart subtitle
16970e5  PR 24a (1/4): wire range-vs-range + hero_player into ui.state
b5777f2  v1.5.1: test rigor + docs honesty (engine bundle deferred to v1.5.2)
```

**Uncommitted working-tree modifications (per `git status`):**

| File | Old value | New value (already edited, awaiting commit) |
|---|---|---|
| `pyproject.toml` | `version = "1.5.1"` | `version = "1.6.0"` |
| `poker_solver/__init__.py` | `__version__ = "1.5.1"` | `__version__ = "1.6.0"` |
| `crates/cfr_core/Cargo.toml` | `version = "0.5.0"` | `version = "0.6.0"` |
| `CHANGELOG.md` | top entry = `[1.5.1]` | new `[1.6.0] - 2026-05-23` section prepended (10 lines describing PR 24a + PR 24b additions) |

Rust .so symlink **present** (`poker_solver/_rust.cpython-313-darwin.so` → shared tree's v1.5.1 .so per LEG 18 §2b symlink protocol). Smoke tests not yet re-run in ship worktree (no evidence of pytest log artifacts).

---

## 3. Where exactly the ship agent stopped

Cross-referencing the working-tree state to `docs/leg18_v1_6_0_gui_ship_plan.md`:

| LEG 18 step | Done? |
|---|---|
| §1 pre-flight (SHAs + stacking verify) | YES (implicit — cherry-pick succeeded) |
| §2a create ship worktree | YES (`ship-v1.6.0` worktree present at `0d7ca15`) |
| §2b symlink `_rust.so` | YES (symlink verified) |
| §2c single-range cherry-pick (`origin/main..feature/pr-24b-gui-nodelock-asym`) | YES (9 commits applied) |
| §3 conflict detection | YES (no conflict markers in tree) |
| §4 maturin rebuild | N/A (UI-only; symlink reused) |
| §5 smoke tests in ship worktree | **UNKNOWN** — no pytest log artifact; may or may not have run |
| §6a-b version-string edits + CHANGELOG | **YES** — files edited, awaiting commit |
| **§6c commit the release bump** | **NO** — STOPPED HERE |
| §7 tag + push | NO |
| §8 GitHub release | NO |
| §9 cleanup (remove symlink + remove worktree) | NO |
| §12 ship report | NO (`docs/leg18_v1_6_0_ship_report.md` missing) |

**Likely failure mode:** ship agent died/timed out between editing the version-string files and committing them. No partial commit was created (only one HEAD; no `chore(release): v1.6.0` commit anywhere). Recovery is fully forward (no rollback needed).

---

## 4. Blocker — origin/main advanced during the stall

`origin/main` now points at `9a2a89e` (the `examples/range_vs_range_river.py` commit, 158 LOC added under `examples/`, no overlap with the cherry-picked v1.6.0 file set). This commit landed AFTER `ship-v1.6.0` was forked off `b5777f2`.

**Consequence:** the `git push origin HEAD:main` step from LEG 18 §7 will be **rejected as non-fast-forward**. The ship branch needs to be rebased onto `origin/main` (or the examples commit cherry-picked into the ship branch) before push.

**Conflict surface for the rebase:** `examples/range_vs_range_river.py` is a new file. The 9 cherry-picked commits do NOT touch `examples/`. Rebase will be **zero-conflict**.

---

## 5. Recovery — specific command sequence to complete v1.6.0 ship

> Run from `/Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.0` unless noted. Each step is idempotent or safe-on-resume.

### 5a. Rebase ship branch onto current origin/main

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.0
git fetch origin
git status --short
# Expected: M CHANGELOG.md / M crates/cfr_core/Cargo.toml /
#           M poker_solver/__init__.py / M pyproject.toml
#           (these are the uncommitted version bumps — preserve them)

# Stash the version bumps so we can rebase cleanly
git stash push -m "v1.6.0 version bumps (pending commit)" \
  CHANGELOG.md pyproject.toml poker_solver/__init__.py crates/cfr_core/Cargo.toml

git rebase origin/main
# Expected: 9 commits replay onto 9a2a89e with no conflicts
#           (examples/ is disjoint from ui/, charts/, tests/)

git log --oneline -12
# Expected top:
#   <new>  PR 24b (5/5): ...
#   ... 8 more cherry-picks ...
#   9a2a89e  examples: add range-vs-range river solve example
#   b5777f2  v1.5.1: ...

# Restore the version bumps
git stash pop
git status --short
# Expected: same M-list as before the stash
```

### 5b. (Optional) smoke tests — DEFER per parent prompt §4

The parent prompt explicitly says **DO NOT re-run the pytest sweep if CPU-heavy**. The 44/44 UI smoke run is the LEG 18 §5a gate. Since both source worktrees (`pr-24a`, `pr-24b`) were independently green at stage time and the cherry-pick is replaying identical diffs onto a known-disjoint base, the smoke run is **recommended but not strictly required to ship** if time-pressured. Document the deferral in the ship report.

```bash
# Recommended (if compute available):
python -m pytest tests/test_ui_smoke.py tests/test_ui_pr24a.py tests/test_ui_pr24b.py -v
# Expected: 44/44 GREEN
```

### 5c. Commit the release bump

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.0
git add CHANGELOG.md pyproject.toml poker_solver/__init__.py crates/cfr_core/Cargo.toml
git status --short          # sanity: only the 4 release files staged
git commit -m "chore(release): v1.6.0 — GUI Gate 2 (UI completeness; PR 24a + PR 24b)"
git log --oneline -12       # expect: release commit on top of 9 cherry-picks + 9a2a89e
```

### 5d. Tag + push

```bash
git tag -a v1.6.0 -m "v1.6.0: GUI Gate 2 (UI completeness)"
git push origin HEAD:main
git push origin v1.6.0
git fetch --tags origin
git tag -l 'v1.6.0'                            # expect: v1.6.0
git ls-remote --tags origin | grep v1.6.0      # expect: present on remote
```

### 5e. GitHub release

Use the release notes drop-in from `docs/leg18_v1_6_0_gui_ship_plan.md` §8 (already authored; just paste into a `/tmp/v1.6.0_release_notes.md` heredoc and run `gh release create v1.6.0 --repo amaster97/poker_solver --latest --title "v1.6.0: GUI Gate 2 (UI completeness)" --notes-file /tmp/v1.6.0_release_notes.md`).

### 5f. Cleanup

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.0
rm poker_solver/_rust.cpython-313-darwin.so     # remove symlink before worktree removal
cd /Users/ashen/Desktop/poker_solver
git worktree remove /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.0
git worktree list                                # verify removed
```

### 5g. Ship report

Write `/Users/ashen/Desktop/poker_solver/docs/leg18_v1_6_0_ship_report.md` per LEG 18 §12 template (LEG 17's report is the closest precedent template).

---

## 6. Estimated time-to-ship if relaunched

Per LEG 18 §10 the full ship was budgeted at 15-25 min. Since most of the bulk work is already done (cherry-picks + version edits + CHANGELOG), the remaining work is:

| Remaining step | Estimated time |
|---|---|
| 5a Rebase onto `9a2a89e` (zero-conflict replay of 9 commits) | 1 min |
| 5b Smoke tests (optional; skip if compute-constrained) | 5-8 min (or 0 if skipped) |
| 5c Commit release bump | 30 sec |
| 5d Tag + push (origin/main + tag) | 1-2 min |
| 5e GitHub release | 1-2 min |
| 5f Cleanup | <1 min |
| 5g Ship report | 3-5 min |
| **Total** | **7-12 min** (skip 5b) / **12-20 min** (include 5b) |

---

## 7. Downstream / cross-leg implications

- **LEG 19 v1.6.1** (`docs/leg19_v1_6_1_ship_plan_REVISED.md`) is **blocked on v1.6.0 landing**. v1.6.1 is a PATCH (1.6.0 → 1.6.1) for PR 33 + PR 34 + PR 40, so v1.6.0 must be on `origin/main` first. The `v1-6-1-staging-verify` branch already has the staging examples commit (`9a2a89e`) — that's the examples commit currently on `origin/main`. No conflict with LEG 19 ship.
- **PR 11 .dmg rebuild + PR 10b UI re-audit** triggered by v1.6.0 ship (per `feedback_ui_packaging_sync`). Both should be queued post-ship per LEG 18 §9 "Downstream impact".
- **Persona retest** remains gated on engine-bundle (v1.5.2 or v1.6.1) per LEG 18 §9 honest-scope note.

---

## 8. Recommendation

**Status verdict: MID-SHIP / RECOVERABLE.** Not stalled-dead, not started-fresh — partial work is safe to resume in-place.

**Recommended next action:** **Relaunch a single ship-finisher agent** to execute §5a → §5g from this doc. No re-cherry-pick, no re-edit needed. Smoke test sweep can be deferred (§5b) per parent prompt §4 if CPU-bound; document as deferred in the ship report. **Expected wall-clock: 7-12 min** (without smoke) / **12-20 min** (with smoke).

**Hard gate:** none. The cherry-picks are correct, the version edits are correct, the CHANGELOG entry is correct — the only outstanding work is the commit/tag/push sequence + rebase to absorb the 1-commit advance on `origin/main`. No design decisions, no Type C-CRITICAL findings, no force-push or branch-deletion exceptions per `feedback_pr10a5_autonomous_commit` — fully within autonomous-ship authorization.
