# Final-State Filler Sanity Check — 2026-05-22

Read-only audit of repo state immediately following the CHANGELOG bump to
v0.4.0 and the in-flight PR 6 (Rust HUNL port) work. Performed per the
"≥5 agents → snapshot final state" discipline.

## Overall verdict: **WARNINGS** (no DRIFT)

- Version strings: **CONSISTENT** at `0.4.0` across all three files.
- CHANGELOG section order: **CONSISTENT**.
- Branch tips: **CONSISTENT** with stated expectations.
- Stash: **CLEAN**.
- Background processes: **CLEAN**.
- Warnings: PR 6 working-tree changes are still **UNCOMMITTED** on
  `pr-6-rust-hunl-port`, and the version/CHANGELOG bumps live in that
  uncommitted set rather than on a v0.4.0 release commit on `integration`.

## 1. Version-string triple-check (all = 0.4.0)

| Location | Value | Status |
|---|---|---|
| `poker_solver/__init__.py` line 158 | `__version__ = "0.4.0"` | OK |
| `pyproject.toml` line 7 | `version = "0.4.0"` | OK |
| `CHANGELOG.md` line 17 | `## [0.4.0] - 2026-05-22` | OK |

All three agree. The "`__version__` lag from v0.3.0 fully reconciled"
note in the [0.4.0] Internal block matches the actual file content.

## 2. CHANGELOG section ordering

Verified top-to-bottom:

```
## [Unreleased]            line 8
## [0.4.0] - 2026-05-22    line 17
## [0.3.1] - 2026-05-21    line 74
## [0.3.0] - 2026-05-21    line 106
## [0.2.0] - 2026-05-20    line 229
## [0.1.0] - 2026-05-20    line 260
## [0.0.1] - earlier       line 283
```

Order is correct (Keep a Changelog convention: Unreleased on top,
then newest-first). Link refs at the bottom (lines 290-296) also include
the new `[0.4.0]` row in the right slot.

## 3. Branch tips

### `integration` (last 15)

```
eee9b4b Integration: merge PR 5 (HUNL postflop solve + memory profiler)
a9d02ca PR 5: HUNL postflop solve + per-street memory profiler
5832b2f Integration: merge PR 4 (card abstraction)
f67bfa3 Integration: merge PR 3.5 audit follow-up (1cbf52a)
6565b84 PR 4: Card abstraction pipeline (EMD bucketing, 256/128/64, suit-iso)
1cbf52a PR 3.5 audit follow-up: API completeness + spec amendments
fd0a2c7 Integration: merge PR 3.5 (push/fold + v0.3 capstone)
9f91c83 PR 3.5 + v0.3 capstone: push/fold mode (2-15 BB) + project meta
351cbee Integration: merge PR 3 (rebased on equity-hybrid main)
a96675c PR 3: HUNL tree builder + action abstraction (Python tier)
2b67370 Equity: hybrid exact-enum + MC, tighter precision default (#1)
17c9756 PR 2: Leduc poker (Python + Rust) + Game trait abstraction
3425da8 Slim down public repo: untrack PLAN.md and docs/
9d2d66a PR 1: Two-tier CFR foundation (Python + Rust)
023956e Initial commit: Texas Hold'em equity solver
```

Tip = `eee9b4b` — matches the "`eee9b4b` or later" expectation. OK.

### `pr-6-rust-hunl-port` (last 5)

```
eee9b4b Integration: merge PR 5 (HUNL postflop solve + memory profiler)
a9d02ca PR 5: HUNL postflop solve + per-street memory profiler
5832b2f Integration: merge PR 4 (card abstraction)
f67bfa3 Integration: merge PR 3.5 audit follow-up (1cbf52a)
6565b84 PR 4: Card abstraction pipeline (EMD bucketing, 256/128/64, suit-iso)
```

Tip = `eee9b4b` — **identical to `integration` tip**. PR 6 branch has
no committed work yet; all of Agents A/B/C's output lives only in the
working tree (see §4). Worth flagging.

### `main` (last 3)

```
2b67370 Equity: hybrid exact-enum + MC, tighter precision default (#1)
17c9756 PR 2: Leduc poker (Python + Rust) + Game trait abstraction
3425da8 Slim down public repo: untrack PLAN.md and docs/
```

Tip = `2b67370` — matches expectation (user hasn't merged). OK.

## 4. Working-tree state on `pr-6-rust-hunl-port`

`git status` reports uncommitted work:

**Modified (9 files):**
- `CHANGELOG.md` (the v0.4.0 bump just performed)
- `Cargo.lock`, `crates/cfr_core/Cargo.toml`, `crates/cfr_core/src/lib.rs`
- `poker_solver/__init__.py` (version bump + new HUNL exports)
- `poker_solver/cli.py`, `poker_solver/hunl.py`, `poker_solver/solver.py`
- `pyproject.toml` (version bump)

**Untracked (6 paths):**
- `crates/cfr_core/src/abstraction.rs`
- `crates/cfr_core/src/hunl.rs`
- `crates/cfr_core/src/hunl_eval.rs`
- `crates/cfr_core/src/hunl_solver.rs`
- `crates/cfr_core/src/hunl_tree.rs`
- `crates/cfr_core/tests/`
- `tests/test_hunl_diff.py`

These are Agent A (Rust HUNL state) + Agent B (Rust HUNL tree) + Agent C
(Rust HUNL solver) outputs plus the v0.4.0 metadata bump. **Nothing has
been staged or committed** to `pr-6-rust-hunl-port` yet.

### Implication

The CHANGELOG, `__init__.py`, and `pyproject.toml` version bumps are
currently only in the working tree of the PR 6 feature branch. They have
**not** landed on `integration` and there is **no v0.4.0 release commit
or tag** anywhere in the graph. If the user wants v0.4.0 to be a stable
marker on `integration`, the version/CHANGELOG changes should be split
out of the PR 6 commit and applied to `integration` separately (or
cherry-picked back) before PR 6 lands.

## 5. Stash list

`git stash list` returns empty. No stashed work to recover. OK.

## 6. Zombie processes

`ps aux | grep -i pytest | grep -v grep` returns empty. No leftover
pytest workers from earlier parallel-agent runs. OK.

## 7. Summary table

| Check | Status |
|---|---|
| `__version__` = 0.4.0 | OK |
| `pyproject.toml` version = 0.4.0 | OK |
| CHANGELOG header [0.4.0] - 2026-05-22 | OK |
| CHANGELOG section order Unreleased / 0.4.0 / 0.3.1 / 0.3.0 / ... | OK |
| CHANGELOG link refs include [0.4.0] | OK |
| `integration` tip ≥ `eee9b4b` | OK (= eee9b4b) |
| `main` tip = `2b67370` | OK |
| `pr-6-rust-hunl-port` has working-tree changes | YES (uncommitted) |
| PR 6 commits beyond `integration` tip | NONE |
| Stash list empty | OK |
| No zombie pytest processes | OK |

## 8. Action items (informational; this audit is read-only)

1. **Decide whether to commit on `pr-6-rust-hunl-port` now or split.**
   The v0.4.0 metadata bump arguably belongs on `integration` (it
   describes PR 4 + PR 5, both already merged), not on the PR 6 branch.
   Recommend either:
   (a) commit the version/CHANGELOG bump directly on `integration` and
   rebase PR 6 onto the new tip, or
   (b) accept the bump being part of the eventual PR 6 merge commit and
   adjust the changelog text accordingly when PR 6 lands.

2. **PR 6 agent output is uncommitted.** Six untracked Rust source files
   + one new Python diff test + four modified Rust files. Stage and
   commit on `pr-6-rust-hunl-port` so the work is recoverable if the
   working tree is wiped.

3. **No v0.4.0 tag exists.** If a tagged release was intended, it has
   not been created. (Earlier convention: tag at release boundaries.)
