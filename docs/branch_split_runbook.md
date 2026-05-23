# Branch Split Runbook: `main` (public) vs `integration` (internal)

Date authored: 2026-05-23
Authorizing decision: 2026-05-22 (dual-channel model)
Companion audit: [`repo_audit.md`](repo_audit.md)
Companion script: [`/scripts/split_main_for_publish.sh`](../scripts/split_main_for_publish.sh)

## What the script does

`scripts/split_main_for_publish.sh` enforces a hard-coded **allowlist** of
files/directories that are permitted to live on `main` (the public-facing
branch). Anything tracked but not on the allowlist is `git rm --cached`'d
(removed from the index, kept on disk). It then appends a set of
session-artifact globs to `.gitignore` so future `wake_up_*.md`,
`SESSION_*.md`, `STATUS*.md`, `V*_GA_CLOSE.md`, and `*_HANDOFF.md` files
cannot slip in via a bulk `git add`.

The allowlist mirrors the PUBLIC-OK classification in `repo_audit.md` §A:
`README.md`, `USAGE.md`, `DEVELOPER.md`, `LICENSE`, `CHANGELOG.md`,
`CONTRIBUTING.md`, `pyproject.toml`, `Cargo.{toml,lock}`, `pytest.ini`,
`.gitignore`, plus the entire `poker_solver/`, `crates/`, `tests/`, `ui/`,
`examples/`, `assets/`, and `.github/` trees, plus explicitly-vetted
scripts under `scripts/`.

The script does **not** commit or push. It stages an index change; you
commit it.

## Dry-run vs execute

The default mode is `--dry-run`: the script enumerates what *would*
change and prints counts, but touches nothing.

```bash
# preview (safe; default)
scripts/split_main_for_publish.sh
scripts/split_main_for_publish.sh --dry-run    # same

# apply (stages changes; still does not commit/push)
scripts/split_main_for_publish.sh --execute
```

In `--execute` mode the script refuses to run if the working tree is
dirty or if HEAD isn't `main`. It warns (but does not bail) if no
`private` remote is configured.

## Manual steps

### Before running

1. **Configure remotes.** `origin` is your public remote. Add a private
   one for the `integration` branch (optional but recommended):
   ```bash
   git remote add private <git@private-host:you/poker_solver_internal.git>
   ```
2. **Switch to `main`** and confirm working tree is clean:
   ```bash
   git checkout main
   git status
   ```
3. **Dry-run first.** Expected violator count today: **2**
   (`STATUS.md`, `SESSION_END_FINAL.md`). `docs/` and `PLAN.md` are
   `.gitignore`d (lines 52-53) so they're not tracked on either
   branch — the FF merge dragged nothing internal across because
   `integration` was identical to `main` at `62c75d5`.
   `V1_GA_CLOSE.md` is in `EXPLICIT_UNTRACK` for defense-in-depth
   but isn't actually tracked (expect a "no-op" line).

### After running `--execute`

1. **Inspect the staged diff** before committing:
   ```bash
   git diff --cached --stat
   git diff --cached -- .gitignore
   ```
2. **Commit** (the script prints a suggested message):
   ```bash
   git commit -m "chore: clean main for public-channel split"
   ```
3. **Push `main` to the public remote only**:
   ```bash
   git push origin main
   ```
4. **Push `integration` to the private remote** (skip if no private
   remote exists yet — leave `integration` local until then):
   ```bash
   git push private integration
   ```
   **Do not** `git push origin integration`. That remote is the public
   channel and `integration` carries internal planning files.

## Reversibility

Everything the script does is reversible up until you push.

* **Index changes only** — the working-tree files are never deleted
  by `git rm --cached`. If a file was removed in error, just
  `git add <path>` to put it back.
* **Before commit:**
  ```bash
  git restore --staged .
  git checkout HEAD -- .gitignore
  ```
* **After commit, before push:**
  ```bash
  git reset HEAD~1          # un-commit; staged changes remain
  git restore --staged .    # un-stage everything
  git checkout HEAD -- .gitignore
  ```
* **After push to origin:** you would need a force-push to undo. Better
  to push a follow-up commit that re-adds anything you want public.
  Never force-push without explicit user approval per the public-repo
  hygiene rule.

## Forward look: Option C transition

Per `docs/planning_preservation_decision.md`, the planned shift is to
un-gitignore `docs/` and `PLAN.md` on `integration` (Option C). When
that lands, run this script before any `integration → main` merge
destined for public `origin` — the allowlist already excludes both
paths, so no script edit is needed; the violator count just grows.
The two-file expectation in "Before running" step 3 holds only
until Option C ships.
