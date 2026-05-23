# Sync Repos Runbook: `scripts/sync_repos.sh`

Date authored: 2026-05-23
Companion script: [`/scripts/sync_repos.sh`](../scripts/sync_repos.sh)
Composed helper:  [`/scripts/split_main_for_publish.sh`](../scripts/split_main_for_publish.sh)
Related runbook:  [`branch_split_runbook.md`](branch_split_runbook.md)

## What it does

`sync_repos.sh` is the one-command wrapper that:

1. Pushes the **internal** `integration` branch to the **private** `backup`
   remote (full planning history, `docs/`, `PLAN.md`, session retrospectives).
2. Invokes `split_main_for_publish.sh --execute` to stage the public-clean
   version of `main`.
3. Verifies you've already committed that staged cleanup on `main` (the
   split helper stages but never commits).
4. Pushes the cleaned `main` to **both** `origin` (public GitHub) and
   `backup` (private mirror).
5. Pushes any newly-created tags to both remotes.
6. Restores your shell to the original branch (`integration`).

Remote layout this script assumes:

| Remote   | URL                                                       | Contents              |
| -------- | --------------------------------------------------------- | --------------------- |
| `origin` | `https://github.com/amaster97/poker_solver.git`           | `main` only           |
| `backup` | `git@github.com:amaster97/poker_solver_private.git`       | `integration` + `main`|

If `backup` does not exist yet, the script proceeds and `[SKIP]`s the two
backup pushes (unless `--strict-backup` is set).

## When to run

- After committing new work to `integration`.
- After running `split_main_for_publish.sh --execute` on `main` **and
  committing** the resulting staged cleanup.
- After cutting a new tag (e.g. `git tag v1.1.0`) — the script auto-detects
  tags not yet on `origin` and pushes `--tags` to both remotes.
- **Not** after a partial / aborted split: re-run the split helper first.

The script is idempotent: if nothing has changed, every push prints
"Everything up-to-date" and the script exits 0.

## Usage

```bash
# Preview the planned operations; touch nothing.
scripts/sync_repos.sh --dry-run

# Interactive (recommended for human use): prints plan, asks "Continue? [y/N]"
scripts/sync_repos.sh

# Headless / scripted: skip the confirmation prompt.
scripts/sync_repos.sh --yes

# Enforce backup presence (CI-friendly safety guard):
scripts/sync_repos.sh --yes --strict-backup
```

## One-time setup (before first use)

1. **Create the private GitHub repo.** Go to
   <https://github.com/new>, name it `poker_solver_private`, set
   visibility to Private. **Do not initialise** with a README — leave it
   empty so the bootstrap push lands cleanly.

2. **Add the `backup` remote locally:**
   ```bash
   git remote add backup git@github.com:amaster97/poker_solver_private.git
   git remote -v   # confirm both `origin` and `backup` are listed
   ```

3. **Bootstrap pushes (one-time, sets upstream tracking):**
   ```bash
   git push -u backup integration
   git checkout main
   git push -u backup main
   git checkout integration
   ```

4. **Push any existing tags** so the per-run new-tag detection has a clean
   baseline:
   ```bash
   git push backup --tags
   ```

After this, normal usage is just `scripts/sync_repos.sh`.

## Recovery if a push fails partway

The script does **not** auto-rollback — state is left as-is for inspection.

- **`[ERROR] Step failed: push integration → backup`**
  Backup remote may be misconfigured (wrong URL, missing SSH key, repo
  doesn't exist). Fix the underlying issue (`git remote -v`, `ssh -T
  git@github.com`) and re-run. Nothing on `main` or `origin` has been
  touched yet.

- **`[ERROR] Step failed: run split_main_for_publish.sh --execute`**
  The split helper aborted (most likely because HEAD wasn't `main` or the
  working tree was dirty). Inspect its output, fix the issue per
  `branch_split_runbook.md`, then re-run `sync_repos.sh`.

- **`[ERROR] main has STAGED-but-uncommitted changes`**
  Expected on first sync after a fresh split. The split helper stages a
  cleanup commit; you need to commit it before pushing:
  ```bash
  git diff --cached --stat
  git commit -m "chore: clean main for public-channel split"
  scripts/sync_repos.sh   # re-run
  ```

- **`[ERROR] Step failed: push main → origin`**
  Likely a non-fast-forward (somebody else pushed) or a credential issue.
  `integration` has already been pushed to `backup`, so that work is
  safe. Resolve the origin conflict (`git fetch origin && git log
  origin/main..main`), then re-run.

- **`[ERROR] Step failed: push main → backup`**
  `origin` already has `main`. Re-run after fixing the backup remote; the
  origin push will be a no-op.

In all cases, after fixing, simply re-run `scripts/sync_repos.sh`. The
earlier successful steps are idempotent.

To manually restore your shell to `integration` after an error:
```bash
git checkout integration
```

## Safety contract

- `set -euo pipefail`; any error aborts with a labelled step.
- Refuses to run unless on `integration` with a clean working tree.
- Refuses to run unless `origin` is configured.
- Interactive `[y/N]` confirmation before any push (override with
  `--yes`).
- Never runs `git reset`, `git stash drop`, or any destructive recovery.
- Never force-pushes.
- Restores the original branch on success.
