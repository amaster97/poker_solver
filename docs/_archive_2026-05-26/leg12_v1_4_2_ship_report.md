# LEG 12: Ship v1.4.2 (Docs Honesty + Test Marker)

**Date:** 2026-05-23
**Type:** PATCH (no API or behavior changes)
**Previous release:** v1.4.1 (`89a124b`)
**Time budget:** 20 min wall-clock (no Rust rebuild required)

---

## Deliverables

| Item | Value |
|---|---|
| **v1.4.2 tag SHA (annotated tag object)** | `4f59c65c9c8a344ea4d8ab23cce2573d1d8bb40c` |
| **v1.4.2 tag points to commit** | `d9094c2` (`Bump version to v1.4.2 (docs honesty + test marker)`) |
| **GitHub release URL** | https://github.com/amaster97/poker_solver/releases/tag/v1.4.2 |
| **Public origin main** | `d9094c2` (4 commits ahead of v1.4.1) |
| **Commits cherry-picked / authored** | 3 (matches expected count) |

---

## What Actually Shipped (3 Commits + Version Bump)

Linear advance from v1.4.1 (`89a124b`):

| SHA (post-cherry-pick) | Source | Purpose |
|---|---|---|
| `e0c950f` | cherry-pick of `a8f5bf1` (PR 25 commit 1 ONLY) | Adds `@pytest.mark.slow` to `test_river_parity_vs_brown` |
| `b18beeb` | cherry-pick of `3875e175` (PR 26 entire branch) | `hero_player` docstring fix in `range_aggregator.py:265-274` |
| `9d9640c` | NEW (manual edit) | Module-level docstring fix at lines 39-50 (same position-semantics issue) |
| `d9094c2` | NEW (version bump) | `pyproject.toml` + `__init__.py` 1.4.1 → 1.4.2; CHANGELOG `[1.4.2]` entry prepended |

**Explicitly excluded (per task instructions):** `6bf8b9e` (PR 25 commit 2 — concrete hole cards). That's a PR 23-dependent change and was not cherry-picked.

---

## Smoke Test Results

```
pytest tests/test_dcfr_diff.py tests/test_exploit_diff.py tests/test_range_vs_range_aggregator.py -v
======================== 31 passed in 71.53s (0:01:11) =========================
```

All 31 tests pass. No regressions.

---

## Unexpected Complexity

### Rust .so Symlink (One Minor Wrinkle)

Initial smoke-test pass failed with `ModuleNotFoundError: No module named 'poker_solver._rust'` — the ship worktree had no built Rust extension. The task spec said "no Rust changes, no need for maturin," which was true for the *source code* but not for the *test imports* (the test files import `poker_solver._rust` directly).

**Resolution:** symlinked the already-built `_rust.cpython-313-darwin.so` from the shared tree into the ship worktree. Since v1.4.2 contains zero Rust changes, the shared tree's compiled .so is byte-identical to what a fresh maturin build from this worktree would produce. Symlink was removed before `git worktree remove`, so it didn't pollute the worktree state. After symlink, all 31 tests passed.

**For future patches:** if a PATCH has no Rust source changes, either (a) symlink the existing .so from the shared tree, or (b) skip the smoke tests that depend on the Rust backend. Option (a) is preferable because it actually exercises the Python-Rust interface.

### Shared-Tree Pull Deferred

The shared tree at `/Users/ashen/Desktop/poker_solver` still shows `main` at `89a124b` (v1.4.1) because no one ran `git pull` there. This is consistent with the "no concurrent branch ops" rule — the shared tree is owned by other in-flight worktrees, and I avoided touching it. A follow-up `git pull` in the shared tree is a routine sync step, not a release blocker.

### Local `ship-v1.4.2` Branch Retained

`git branch -d ship-v1.4.2` refused with "branch is not fully merged" because the shared tree's local `main` ref is stale (still at `89a124b`). Per the "do not delete branches" memory rule, I did **not** force-delete with `-D`. The branch is harmless and matches what was pushed to `origin/main`. It will resolve naturally on the next shared-tree `git pull`.

---

## Manifest of Changed Files (v1.4.2)

```
poker_solver/range_aggregator.py     | docstrings only (inline + module-level)
tests/test_river_parity_vs_brown.py  | added @pytest.mark.slow
pyproject.toml                       | version 1.4.1 -> 1.4.2
poker_solver/__init__.py             | __version__ 1.4.1 -> 1.4.2
CHANGELOG.md                         | prepended [1.4.2] section above [1.4.1]
```

Zero changes to: any Rust source, any solver logic, any test assertions, any UI bindings, any packaging scripts.

---

## Honest Framing (For Persona Tracking)

- **No persona unblock.** v1.4.2 does not unblock any new workflow.
- **No performance impact.** No code paths changed.
- **Documentation accuracy.** Anyone reading `range_aggregator.py` docstrings on v1.4.1 (or v1.3.x or v1.4.0) was getting a backwards position-semantics description. v1.4.2 corrects this without changing what the code does.
- **CI hygiene.** The `@slow` marker formalizes an existing implicit posture — `test_river_parity_vs_brown` was already opt-in via `parity_noambrown` marker conventions; adding `@slow` makes the standard `-m 'not slow'` filter catch it too.

---

## Hard Rules Compliance

| Rule | Status |
|---|---|
| Operate only in `ship-v1.4.2` worktree | OK — only used that worktree for all edits |
| Do not cherry-pick PR 25 commit 2 | OK — only `a8f5bf1` cherry-picked, not `6bf8b9e` |
| Do not force-push | OK — only `git push origin HEAD:main` (fast-forward) and `git push origin v1.4.2` |
| Do not delete branches | OK — `ship-v1.4.2` branch retained locally |
| Do not touch v1.4.1 CHANGELOG entry | OK — `[1.4.1]` section is byte-identical pre/post |
| Release notes are public-OK | OK — no PII, no `/Users/...` paths, no session IDs |
| Time budget: 20 min wall-clock | OK — smoke tests were the longest step (~72 s); overall well under budget |

---

## Tag Verification

```
$ git log --oneline origin/main -3
d9094c2 Bump version to v1.4.2 (docs honesty + test marker)
9d9640c Fix module-level docstring same hero_player misleading framing
b18beeb Fix misleading hero_player docstring (P0=SB-seat acts LAST postflop)

$ git tag -l v1.4.2 --format='%(objectname) %(contents:subject)'
4f59c65c9c8a344ea4d8ab23cce2573d1d8bb40c v1.4.2: docs honesty + test marker
```

Tag is annotated, points to `d9094c2` (the version-bump commit), and is published at `origin/v1.4.2`.

---

**LEG 12 complete. v1.4.2 shipped.**
