# PR 6 Commit Pipeline Steps (v0.5.0 release bundle)

**Audience:** Orchestrator (or the final commit-time agent) running PR 6's commit on `pr-6-hunl-rust-port`.
**Goal:** Single squash-merge-ready commit that bundles the PR 6 Rust port AND the v0.5.0 version-bump artifacts. After this commit lands, the merge tip is releasable; no follow-up bump commit needed.
**Reference:** `docs/pr6_prep/commit_message_draft.md` (final commit message body), `docs/pr6_prep/semver_sequencing.md` (semver rationale).

---

## Step 0 — Preconditions (verify before staging)

- [ ] Branch: `pr-6-hunl-rust-port` is checked out, tip clean except the working-tree edits this pipeline introduces.
- [ ] PR 5 baseline merged into `integration` AND already in this branch's history (the version we're bumping FROM is `0.4.0`).
- [ ] `cargo build --release --package cfr_core` and `cargo test --package cfr_core --all-targets` already PASS on the current working tree (the bump-commit assumes the implementation is green; do NOT run a bump commit on a red tree).
- [ ] `pytest -m "not slow and not very_slow" --tb=line` PASS.
- [ ] `check_pr.sh` license audit PASS (no AGPL/GPL).

---

## Step 1 — Version bump edits (apply IN the PR 6 commit, NOT before)

These four edits land WITH the implementation, in the same commit as the Rust port and the Python dispatch wiring.

### 1a. `poker_solver/__init__.py`

- Line 158: `__version__ = "0.4.0"` -> `__version__ = "0.5.0"`.
- No other lines touched in this file.

### 1b. `pyproject.toml`

- Line 7 (under `[project]`): `version = "0.4.0"` -> `version = "0.5.0"`.
- No other keys touched.

### 1c. `CHANGELOG.md`

Three substantive edits:

1. **Move the PR 6 entry out of `[Unreleased]`.** Delete lines 13-15 of the current file:
   ```
   - PR 6 in flight (Rust HUNL port): license-aware port of the PR 5 Python
     reference postflop solver to `crates/cfr_core/`, with bit-exact diff
     tests against the Python tier on shared seeds. Ships in v0.5.0.
   ```
   from the `### In progress` block. The `PR 7+` line stays.

2. **Insert a new `## [0.5.0] - 2026-05-22` section ABOVE the existing `## [0.4.0] - 2026-05-22` heading** (i.e. just before the current line 19). Recommended skeleton (orchestrator can expand from the PR 6 commit-message body):
   ```
   ## [0.5.0] - 2026-05-22

   PR 6 milestone: Rust port of the HUNL postflop solver lands on
   `integration`. Same DCFR, same action menu, same bucket lookups
   as the PR 5 Python tier; ~30x speedup with bit-exact parity on
   the tiny river subgame fixture and 5e-3 parity on the flop
   fixture.

   ### Added

   - **Rust HUNL postflop solver** (`crates/cfr_core/src/hunl*.rs`,
     `abstraction.rs`, `hunl_solver.rs`; exposed via PyO3 as
     `poker_solver._rust.solve_hunl_postflop`).
   - **CLI**: `--backend rust` flag on `solve --game hunl --hunl-mode
     postflop`. Default stays `python`.

   ### Changed

   - `solver.py` dispatch: HUNL postflop Rust branch composes AFTER
     the PR 3.5 push/fold short-circuit and BEFORE the Python
     fallback (PR 9 §6 canonical ordering).
   ```
   Orchestrator/commit-time agent should reconcile the bullet wording against the final commit-message body in `commit_message_draft.md` so the CHANGELOG and commit body do not drift.

3. **Append link reference** for the new section. After current line 293 (`[0.4.0]: ./`), add:
   ```
   [0.5.0]: ./
   ```
   so the ref block reads `[Unreleased] / [0.5.0] / [0.4.0] / [0.3.1] / ...`.

### 1d. `README.md`

- Line 14: `Current version: 0.4.0` -> `Current version: 0.5.0`.
- Caption on same line: `"card abstraction + HUNL postflop solve"` -> `"Rust HUNL postflop port, ~30x speedup"` (or equivalent v0.5 caption; orchestrator picks final wording).
- Optionally bump the section header `## Features (v0.4)` to `## Features (v0.5)`; not strictly required for the version bump but consistent with the PR 5 precedent.

---

## Step 2 — Stage + commit

```bash
# From repo root, on pr-6-hunl-rust-port.
git status                       # confirm only intended files are dirty
git add poker_solver/__init__.py \
        pyproject.toml \
        CHANGELOG.md \
        README.md \
        crates/cfr_core/ \
        poker_solver/solver.py \
        poker_solver/hunl.py \
        poker_solver/cli.py \
        tests/test_hunl_diff.py
# (Add any other PR-6-scope files surfaced by `git status`; do NOT use `git add -A`.)

git commit -F docs/pr6_prep/commit_message_draft.md
git log -1 --stat                # sanity-check the commit covers the bundle
```

---

## Step 3 — Post-commit verification (before push)

- [ ] `python -c "import poker_solver; print(poker_solver.__version__)"` prints `0.5.0`.
- [ ] `grep '^version' pyproject.toml` shows `0.5.0`.
- [ ] `head -25 CHANGELOG.md` shows `[0.5.0]` section above `[0.4.0]`; `[Unreleased]` no longer carries the PR 6 line.
- [ ] `grep "Current version" README.md` shows `0.5.0`.
- [ ] `cargo test --package cfr_core --all-targets` and `pytest -m "not slow and not very_slow"` re-run green on the committed tree.

---

## Step 4 — Push + tag (after merge, NOT in this commit)

The release tag `v0.5.0` is applied AFTER the squash-merge to `integration` -> `main`, by the orchestrator's release flow. This pipeline only prepares the commit; it does NOT tag.

---

## Notes

- The bump artifacts (steps 1a-1d) MUST land on the same commit as the implementation so the merge tip is releasable; do NOT split into a follow-up "bump version" commit (that breaks the PR 5 / PR 3 precedent and creates a window where the merge tip is internally inconsistent).
- If a pre-commit hook fails, create a NEW commit with fixes; do NOT `--amend` (per repo's git-safety protocol).
