# LEG 14 — v1.4.3 ship report

**Date:** 2026-05-23 · **Status:** SHIPPED · **Wall-clock:** ~15 min
**Tag SHA (annotated):** `ab8ebcc2f5568ca340976df6035091f69e76abdd`
**Tag points to commit:** `eea3a8b502ec5b5e2e7ad18e61eb71b3b00aaafc`
**Release URL:** https://github.com/amaster97/poker_solver/releases/tag/v1.4.3

---

## Bundle composition (final state on `origin/main`)

Top-down `git log` after ship (above `d9094c2` v1.4.2):

| Order | SHA | Origin | Description |
|---|---|---|---|
| 6 | `eea3a8b` | NEW | v1.4.3 release bump (CHANGELOG + pyproject + __init__) |
| 5 | `f9c9aad` | PR 30 commit 3 | fix-ups: v1.4.3 preamble + drop PR 27 forward-ref + drop dangling brown_apples reference |
| 4 | `70e5d97` | PR 30 commit 2 | DEVELOPER.md: two-tier honesty + action abstraction + op notes |
| 3 | `0e4d30f` | PR 30 commit 1 | USAGE.md: v1.4.x capabilities + CLI gaps + perf cliffs |
| 2 | `30386d6` | PR 27 | Range.diff() utility (cherry-pick of `89c1f351`) |
| 1 | `8fd9dbd` | PR 31 | HUNLConfig type validation (cherry-pick of `bbc6eed`) |

Source-branch SHAs verified pre-ship: PR 31 `bbc6eed`, PR 27 `89c1f351`, PR 30 `a2d318c`.
PR 29 (`pr-29-persona-spec-corrections`) explicitly EXCLUDED per audit BLOCKING finding (would leak internal `docs/pr13_prep/` tree to public origin). Stays on branch; not landed.

---

## Cherry-pick sequence — clean (zero conflicts)

Disjoint file matrix per audit `docs/v1_4_3_pre_ship_audit.md` §4 held: no two cherry-picks touched the same file. All 5 commits applied without `--continue` intervention.

---

## Smoke tests

`pytest tests/test_range.py tests/test_hunl_config_validation.py -v` → **50 passed in 0.15s** (22 Range tests including 8 new `diff()` cases + 28 HUNLConfig validation tests).

---

## Unexpected complexity

### A. Pytest x86_64 mode → Rust-dependent tests can't load arm64 `.so`

The full smoke set per the plan included `test_dcfr_diff.py`, `test_exploit_diff.py`, `test_range_vs_range_aggregator.py`, `test_node_locking.py` — all of which import from `poker_solver._rust`. These failed with:

```
ImportError: dlopen(...): tried: '... .so' (mach-o file, but is an
incompatible architecture (have 'arm64', need 'x86_64'))
```

**Root cause (verified):** This is a **pre-existing local environment issue**, not a v1.4.3 cherry-pick regression. Confirmation steps:
- `file _rust.cpython-313-darwin.so` → `Mach-O 64-bit dynamically linked shared library arm64` (correct arch for arm64 Mac)
- `python -c "import platform; print(platform.machine())"` → `arm64`
- `python -c "import poker_solver._rust"` → no error (direct interpreter works)
- BUT pytest goes through `~/.pyenv/shims/pytest` (bash shim) which resolves to a universal Python binary that gets launched as x86_64 under the shim wrapper (likely macOS preferred-arch heuristic on the shim shell process)
- **Verified pre-existing:** running `pytest tests/test_dcfr_diff.py` against the `pr-22-asymmetric` worktree (no v1.4.3 changes whatsoever) produces the identical ImportError
- Trying `arch -arm64 pytest ...` did not fix it (the shim re-architects internally)

**Decision:** Proceed with ship. PR 27 + PR 31 are pure-Python additions that don't touch the Rust binding at all; their 50 tests pass cleanly. PR 30 is docs-only. The Rust-test environment quirk doesn't gate any of the v1.4.3 deliverables. Filing as a follow-up for the testing harness (not a ship blocker).

### B. `.so` symlink — clean per .gitignore

The symlink to the shared-tree `_rust.cpython-313-darwin.so` (per LEG 12 precedent) was untracked by git (correctly ignored by `.gitignore`), so it never showed up in `git status` or staged commits. Removed before `git worktree remove` per plan §9. No pollution of the ship commits.

### C. No PR 29 in bundle — by design

Per pre-ship audit `docs/v1_4_3_pre_ship_audit.md` §2.2 BLOCKING finding, PR 29 would have re-introduced the `docs/pr13_prep/` tree (132-line whole-file add) to public origin, violating `feedback_public_repo_hygiene`. The "Persona spec corrections" content stays on the `pr-29-persona-spec-corrections` branch and can land on the private mirror separately. The v1.4.3 release notes do NOT cite PR 29 (per the audit's Option A guidance).

---

## Push verification

```
$ git push origin HEAD:main
   d9094c2..eea3a8b  HEAD -> main
$ git push origin v1.4.3
 * [new tag]         v1.4.3 -> v1.4.3
$ git ls-remote --tags origin | grep v1.4.3
ab8ebcc2f5568ca340976df6035091f69e76abdd  refs/tags/v1.4.3
eea3a8b502ec5b5e2e7ad18e61eb71b3b00aaafc  refs/tags/v1.4.3^{}
```

GitHub release published at `https://github.com/amaster97/poker_solver/releases/tag/v1.4.3` — public-OK (no `/Users/`, no session IDs, no PII).

---

## Cleanup

- `.so` symlink removed from ship worktree before removal.
- `git worktree remove /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.4.3` succeeded.
- Local `ship-v1.4.3` branch retained per memory `feedback_no_concurrent_branch_ops` (will resolve on next shared-tree `git pull`).
- Shared `/Users/ashen/Desktop/poker_solver` tree is still at `89a124b` (v1.4.1) — 6 commits behind origin/main as expected per LEG 12 precedent. Routine `git pull --ff-only` deferred to next coordination window.

---

## Post-ship follow-ups (NOT blockers)

1. **Pytest arch quirk.** Investigate pyenv shim launching x86_64 — affects ability to run Rust-dependent tests locally on arm64. Workaround for now: invoke `python -m pytest ...` directly instead of `pytest ...` to bypass shim.
2. **PR 29 landing on private mirror.** Persona spec corrections need a separate push to `backup`/`integration` only — not to public origin.
3. **Shared tree pull.** `git pull --ff-only origin main` on shared tree once no other agents are writing.
4. **Optional W2.2 retest.** Persona retest using new `Range.diff()` for categorical-leak slice — defer to v1.5.0 cadence per LEG 14 §11J recommendation.
