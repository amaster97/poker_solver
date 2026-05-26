# Release Process (CI-Driven)

Starting v1.7.2, releases are driven by GitHub Actions. Push a `ship/vX.Y.Z`
branch and CI handles build, test, tag, and GitHub release creation.

## TL;DR

```bash
git checkout main && git pull
# update CHANGELOG.md with release notes
git checkout -b ship/v1.7.2
git push -u origin ship/v1.7.2
# CI takes over from here
```

## Pre-flight checklist

Before pushing a `ship/v*` branch, on `main`:

1. **CHANGELOG.md** — top section reflects the release version + notes.
   The release body is taken verbatim from this file.
2. **Version bump** — `Cargo.toml`, `pyproject.toml`, and any `__version__`
   constants match the target version.
3. **All bundle PRs merged** — every PR intended for this release is on
   `main`. CI won't backfill.
4. **No open `ship-bundle` PRs** — the dry-run gate catches conflicts.

## What CI does (`.github/workflows/release.yml`)

Triggered on any push to `ship/v*`. On `macos-14` (Apple Silicon), within
a 120-min budget:

1. Extract version from branch name (`ship/v1.7.2` -> `v1.7.2`).
2. Setup Rust (stable) + Python 3.13.
3. `maturin build --release --target universal2-apple-darwin`, install the wheel.
4. Build the Brown reference binary (`scripts/build_noambrown.sh`).
5. `cargo test --lib --release`.
6. Pytest smoke matrix with `POKER_SOLVER_REQUIRE_BROWN_PARITY=1`:
   - `test_exploit_diff.py` (--timeout=120)
   - `test_v1_5_brown_apples_to_apples.py` (--timeout=1800)
   - `pytest -m "not slow"` (--timeout=120)
7. `git tag vX.Y.Z` and push the tag.
8. `gh release create` against `main` with `CHANGELOG.md` as notes.

If any step fails, no tag is created and no release is published.

## Ship-bundle dry run (`.github/workflows/ship_dry_run.yml`)

Triggered on PRs to `main`. If the PR carries the `ship-bundle` label,
CI attempts to cherry-pick it onto the latest `main` in a throwaway
branch. Conflict -> red status.

Apply the `ship-bundle` label on PRs that are part of a coordinated
release bundle (multiple PRs landing together).

## Monitoring a release

After `git push -u origin ship/vX.Y.Z`:

- Watch CI: `gh run watch` or the Actions tab on GitHub.
- On success: a tag `vX.Y.Z` and a GitHub release appear.
- On failure: the workflow logs identify the failed step. The
  `ship/vX.Y.Z` branch can be retried with `gh workflow run` after fixing
  the underlying issue on `main` (then rebase the ship branch).

## Rollback

If a release ships but is broken:

1. **Delete the tag**: `git tag -d vX.Y.Z && git push origin :refs/tags/vX.Y.Z`.
2. **Delete the GitHub release**: `gh release delete vX.Y.Z --yes`.
3. **Fix on main**, then re-cut a new `ship/vX.Y.Z+1` branch.
   Never reuse a version number once a release has been published.

## Why CI instead of `scripts/ship_*.sh`?

v1.7.1's ship retries got killed at the 25-30 min mark by agent
execution timeouts. CI runners have no such limit. The 30-45 min
smoke matrix now completes reliably.

The legacy `scripts/ship_v1_7_1.sh` is retained for forensic reference
but should not be invoked for new releases.
