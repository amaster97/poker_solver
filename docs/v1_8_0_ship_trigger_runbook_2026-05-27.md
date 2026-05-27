# v1.8.0 Ship-Trigger Runbook — 2026-05-27

**Purpose.** Operator runbook for the one-shot v1.8.0 ship wrapper
(`scripts/release_v1_8_0_trigger.sh`). Once the terminal-utility
convention purge PR has merged + post-purge validation PASSES, this
wrapper executes the v1.8.0 release with a single command and zero
manual editing.

**Status of upstream pre-flight.** Prior pre-flight verdict was
**GO** with `--expected-sha b401f6c87a18734cdf50883f642d11b98f9688c6`
(see `docs/v1_8_0_final_ship_readiness_2026-05-26.md`). That SHA is now
stale — `origin/main` has advanced past #66 through #78. The convention
purge landed as **PR #78 (`37e5be1`)** on 2026-05-27. The wrapper
resolves the current `origin/main` HEAD SHA dynamically; you do NOT
need to copy a SHA into the invocation.

---

## 1. When to run it

Run this wrapper ONLY when ALL of the following are true:

1. The terminal-utility convention purge PR has merged to `origin/main`.
   - `crates/cfr_core/src/hunl.rs` `utility()` references at least one
     of `{contrib_subgame, initial_contributions, base_pot, pot_total}`
     in its body (heuristic the wrapper enforces).
2. Post-purge validation has run on `origin/main` and the v1.5 Brown
   apples-to-apples reframed 4-layer gate PASSES.
   - The wrapper does NOT re-run the multi-minute test locally; the
     inner script's Phase 0.5 (`gh run list --branch main --limit 10`)
     gates on CI being green, which is the authoritative signal.
3. The release-notes draft `docs/v1_8_0_release_notes_DRAFT.md` no
   longer contains any `<TBD-*>` placeholders (the purge PR is
   expected to substitute them with real PR # / merge SHA /
   post-purge residual numbers).
4. `gh` is authenticated (`gh auth status`), network is reachable,
   and the `backup` remote is configured (or you intend to pass
   `--skip-backup`).
5. You are on the `main` branch locally and able to fast-forward.

If any of those are NOT true, DO NOT run the wrapper. Either resolve
the missing precondition first, OR run with `--dry-run` to inspect
the state.

---

## 2. What it does, step by step

### Phase A — branch check
- Verifies `git branch --show-current` is `main`.
- HARD-FAILS otherwise (no auto-checkout).

### Phase B — dynamic SHA resolution
- Runs `git fetch origin main`.
- Captures `EXPECTED_SHA = $(git rev-parse origin/main)`.
- If local main is strictly behind origin/main (no divergent commits),
  fast-forwards with `git pull --ff-only`. If local has diverged, HARD-FAILS.

### Phase C — post-purge precondition checks
- **C.1** `crates/cfr_core/src/hunl.rs` `utility()` body must reference
  one of `{contrib_subgame, initial_contributions, base_pot, pot_total}`.
  This is a heuristic guard against running the wrapper before the
  convention purge has landed. Bypass with `--skip-post-purge-checks`
  if you're doing a pre-purge dress-rehearsal.
- **C.2** `docs/v1_8_0_release_notes_DRAFT.md` must have zero `TBD`
  markers. The current pre-fill (PR #77) ships with 4 `<TBD-*>`
  placeholders that the purge PR is expected to substitute.
  `--dry-run` allows TBD markers through (for inspection); a real ship
  HARD-FAILS until they're resolved.
- **C.3** `tests/test_v1_5_brown_apples_to_apples.py` must exist and be
  non-empty (>= 100 lines). The actual PASS/FAIL is gated by the
  inner script's CI check, not re-run locally.

### Phase D — stash untracked docs
- The working tree currently carries ~265+ untracked docs (orchestrator
  staging area for in-flight PRs). The inner script's Phase 0.2 requires
  a clean tree, so the wrapper stashes everything with message
  `pre-v1.8.0-release-stash-2026-05-27`.
- If `git stash push --include-untracked` fails or leaves the tree dirty,
  the wrapper HARD-FAILS before invoking the inner script.

### Phase E — dry-run short-circuit (only if `--dry-run`)
- Prints the command that WOULD be invoked (`bash scripts/release_v1_8_0.sh --expected-sha <current-HEAD> ...`)
- Restores the stash so the working tree returns to the pre-wrapper state.
- Exits 0. No tag, no push, no release.

### Phase F — invoke the inner release script
- `bash scripts/release_v1_8_0.sh --expected-sha <current-HEAD> <forwarded-flags>`
- Forwarded flags: `--upload-dmg`, `--skip-backup`, `--no-bump-cfr-core`
  (the wrapper passes these through unchanged).
- The inner script's own phases are:
  - **0** pre-flight (branch / clean tree / FF / SHA match / CI green /
        version files at 1.7.0 / 0.7.0 / release notes present / tag
        absent / backup remote)
  - **1** version bumps (pyproject 1.7.0->1.8.0, __init__ 1.7.0->1.8.0,
        Cargo 0.7.0->0.8.0 unless `--no-bump-cfr-core`)
  - **2** commit + push to `origin/main`
  - **3** annotated tag `v1.8.0` + push to `origin`
  - **4** `gh release create v1.8.0` + optional .dmg upload
  - **5** mirror to `backup` remote (push main + tag)

### Phase G — post-inner-script cleanup
- On SUCCESS: `git stash pop` to restore untracked docs.
- On FAILURE: stash is LEFT IN PLACE. The wrapper prints the stash
  message + diagnostic commands.

---

## 3. Invocation

### Real ship
```bash
cd /Users/ashen/Desktop/poker_solver
bash scripts/release_v1_8_0_trigger.sh
```

### Dry-run (recommended FIRST, to verify state)
```bash
bash scripts/release_v1_8_0_trigger.sh --dry-run
```

### With .dmg upload (only after building per dmg_build_runbook)
```bash
bash scripts/release_v1_8_0_trigger.sh --upload-dmg
```
The `.dmg` is independent of the tag; you can also upload AFTER the
release publishes via:
```bash
gh release upload v1.8.0 dist/Poker-Solver-1.8.0-arm64.dmg
```

### Without the cfr_core minor bump
```bash
bash scripts/release_v1_8_0_trigger.sh --no-bump-cfr-core
```

### Without backup mirror push
```bash
bash scripts/release_v1_8_0_trigger.sh --skip-backup
```

### Pre-purge dress-rehearsal (PRE-PURGE ONLY)
```bash
bash scripts/release_v1_8_0_trigger.sh --dry-run --skip-post-purge-checks
```
The `--skip-post-purge-checks` flag prints WARN lines and bypasses
the canonical-convention heuristic. NEVER use this for a real ship.

---

## 4. Abort + recovery

### Wrapper failed in Phase A-D (before inner script ran)
- No commit, no tag, no push has happened.
- If the wrapper stashed untracked docs, the stash is preserved (if Phase D
  raised the diagnostic) or restored (if dry-run). Find it with:
  ```bash
  git stash list | grep 'pre-v1.8.0-release-stash-2026-05-27'
  ```
- Restore with `git stash pop` once the underlying issue is resolved.

### Inner script failed in Phase 0 (pre-flight)
- No version bump, no commit, no tag.
- The wrapper leaves the stash in place. Read the inner script's
  FATAL line; the script abort taxonomy:
  - "branch not main" — `git checkout main`
  - "tree not clean" — wrapper failed to stash everything; manual cleanup
  - "local HEAD differs from origin/main" — `git pull --ff-only origin main`
  - "HEAD != EXPECTED_SHA" — wrapper computed `EXPECTED_SHA` dynamically;
    if this fires, something raced between fetch and rev-parse. Re-run
    the wrapper.
  - "CI runs not green" — inspect with `gh run list --branch main --limit 10`;
    do NOT bypass.
  - "pyproject.toml version not 1.7.0" — someone already bumped; investigate.
  - "tag v1.8.0 already exists" — see "Tag already exists" below.
  - "backup remote not configured" — `git remote add backup <url>` or
    pass `--skip-backup`.

### Inner script failed in Phase 1 (version bumps)
- Local edits to `pyproject.toml` / `poker_solver/__init__.py` /
  `crates/cfr_core/Cargo.toml` may have happened.
- Revert with:
  ```bash
  git checkout -- pyproject.toml poker_solver/__init__.py crates/cfr_core/Cargo.toml Cargo.lock
  ```
- The wrapper's stash is still in place; pop after revert.

### Inner script failed in Phase 2 (commit + push)
- Local commit may exist; push may have or may not have completed.
- Check local state:
  ```bash
  git log -1 --oneline                    # is the bump commit present locally?
  git log origin/main..HEAD --oneline     # is it pushed?
  ```
- If commit exists locally but didn't push: re-run `git push origin main`
  manually (after diagnosing the push failure). Then continue manually
  to Phase 3 with `git tag -a v1.8.0 -m "..."` + `git push origin v1.8.0`.
- If the commit pushed but a later phase failed: do NOT revert the
  commit. Continue from where the inner script aborted (rollback
  notes in `scripts/release_v1_8_0.sh` header §"ROLLBACK NOTES").

### Inner script failed in Phase 3 (tag) or Phase 4 (release)
- Bump commit is on origin/main. Tag may or may not exist.
- Follow `scripts/release_v1_8_0.sh` § "ROLLBACK NOTES":
  ```bash
  gh release delete v1.8.0 --yes 2>/dev/null
  git push origin :v1.8.0  2>/dev/null
  git tag -d v1.8.0 2>/dev/null
  ```
  Then re-run the inner script (NOT the wrapper — the wrapper would
  fail Phase C.2 if release notes still have substitutions remaining,
  and would fail Phase 0.6 because pyproject.toml is now at 1.8.0).
  Re-run with:
  ```bash
  bash scripts/release_v1_8_0.sh --expected-sha $(git rev-parse origin/main)
  ```
  (The script's Phase 0.6 check will fail because version is now 1.8.0,
  not 1.7.0. Patch Phase 0.6 locally for a one-shot re-run, OR cherry-pick
  the tag / release steps manually.)

### Inner script failed in Phase 5 (backup mirror sync)
- Origin release IS published. Backup mirror is out of sync.
- The release is LIVE on GitHub; do not panic.
- Manually catch up the backup mirror:
  ```bash
  git push backup main
  git push backup v1.8.0
  ```

### Tag already exists (re-run after partial ship)
- Delete locally + on origin, then re-run:
  ```bash
  git tag -d v1.8.0
  git push origin :v1.8.0
  gh release delete v1.8.0 --yes 2>/dev/null
  ```
- This is DESTRUCTIVE. Only do it if the release was never announced
  externally.

### Stash got dropped accidentally
- The stash entry survives `git stash pop` (no automatic drop on
  success, though `git stash pop` does drop by default). If you find
  yourself missing the ~265 untracked docs after a wrapper run:
  ```bash
  git fsck --unreachable | grep commit
  ```
  to find dangling commits. The stash commit is recoverable for ~90
  days via `git reflog` and `gc.reflogExpireUnreachable`.

---

## 5. Idempotency notes

- **Dry-run is idempotent.** Run `--dry-run` as many times as you want.
- **Real ship is NOT idempotent.** Once Phase 3 (tag) completes,
  re-running the wrapper will fail at the inner script's Phase 0.8
  (`tag v1.8.0 already exists`). This is intentional.
- **Wrapper-level state is restart-safe.** A failed wrapper (Phase A-D
  before the inner script starts) leaves no commits and no tags; only
  the stash (which is recoverable).

---

## 6. Post-ship verification

After the wrapper exits 0, run the following checks (each takes < 30s):

### 6.1 Release URL renders
```bash
gh release view v1.8.0 --web                   # open in browser
# OR
gh release view v1.8.0                          # text in terminal
```
Expected: title `v1.8.0 — Cross-platform SIMD + .dmg fork-bomb fix`,
notes body matches `docs/v1_8_0_release_notes_DRAFT.md` (sans the
inserted TBD substitutions), no `<TBD-*>` markers visible.

### 6.2 Tag visible on GitHub
```bash
gh api repos/amaster97/poker_solver/tags --jq '.[] | select(.name=="v1.8.0")'
```
Expected: returns a JSON object with `commit.sha` == the bump commit.

### 6.3 Backup mirror in sync
```bash
git ls-remote backup refs/tags/v1.8.0
git ls-remote backup refs/heads/main
```
Expected: both lines printed; the tag SHA matches origin, the main SHA
matches origin.

### 6.4 Version bump landed
```bash
gh api repos/amaster97/poker_solver/contents/pyproject.toml --jq '.content' \
    | base64 -d | grep '^version' | head -1
# Expected: version = "1.8.0"
```

### 6.5 Local working tree is back to its pre-ship state
```bash
git stash list | grep pre-v1.8.0-release
# Expected: empty (stash was popped on success)

git status --porcelain | wc -l
# Expected: ~265+ (untracked docs restored)
```

If 6.5 shows the stash still present, the inner script likely succeeded
but `git stash pop` failed (rare; usually means a conflict against the
bump commit). Pop manually:
```bash
git stash pop
```
If pop conflicts, resolve with `git checkout --theirs` or
`git checkout --ours` per file as appropriate.

---

## 7. Next step after v1.8.0 ships: .dmg build + upload

The v1.8.0 release object IS the tag + notes. The `.dmg` binary asset
is uploaded separately:

1. **Build the .dmg locally** per
   `docs/dmg_build_runbook_2026-05-26.md`. The runbook covers:
   - shell prep (PATH cargo / rustc / maturin)
   - `maturin develop --release`
   - `bash scripts/build_macos_dmg.sh`
   - post-build verification (lipo, codesign, plist version)
2. **Verify the built .dmg** is at `dist/Poker-Solver-1.8.0-arm64.dmg`.
3. **Upload** as a release asset:
   ```bash
   gh release upload v1.8.0 dist/Poker-Solver-1.8.0-arm64.dmg
   ```
   (Equivalent to having passed `--upload-dmg` to the wrapper at ship
   time, if you'd already built the .dmg before ship.)
4. **Smoke-test the uploaded .dmg** by downloading it from the GitHub
   release page and double-clicking. Expected: opens without fork-bomb
   (PR #42 freeze_support guard).

The .dmg upload is NOT blocking for the release boundary; the v1.6.0
release tag was published before the v1.6.0 .dmg was retroactively
pulled, and the same boundary logic applies here.

---

## 8. Cross-references

| Topic | Path |
|---|---|
| Inner release script | `scripts/release_v1_8_0.sh` |
| Wrapper script | `scripts/release_v1_8_0_trigger.sh` |
| Prior pre-flight verdict | `docs/v1_8_0_final_ship_readiness_2026-05-26.md` |
| Release notes (pre-fill) | `docs/v1_8_0_release_notes_DRAFT.md` |
| Convention purge feedback | memory: `feedback_brown_convention_adopt.md` |
| Brown acceptance test | `tests/test_v1_5_brown_apples_to_apples.py` |
| .dmg build runbook | `docs/dmg_build_runbook_2026-05-26.md` |
| Post-integration verification | memory: `feedback_post_integration_verification.md` |

---

## 9. Quick reference: the one command

```bash
cd /Users/ashen/Desktop/poker_solver && bash scripts/release_v1_8_0_trigger.sh
```

That's the ship trigger. Everything else is verification, recovery, or
.dmg follow-up.
