# Doc-Drift Cleanup PR #45 — Report (2026-05-26)

PR URL: <https://github.com/amaster97/poker_solver/pull/45>
Status: **MERGED** at commit `dbfc8d0` (2026-05-26 06:17 UTC)
Branch: `pr-85-doc-drift-cleanup-v2` (deleted on merge)
Worktree: `/Users/ashen/Desktop/poker_solver_worktrees/pr-85-doc-drift-v2` (removed)
PR commit: `67503ea` ("docs: drift cleanup v2 (USAGE header, CHANGELOG .dmg, dmg_install_guide banner)")
CI: 3/3 green (bundle-dry-run, check x2).

## Constraint posture

This is the v2 redo. The v1 attempt was killed by classifier for
attempting destructive ops on the main workspace. v2 strictly
respects the constraint:

- All edits/commits happen inside the worktree
  `/Users/ashen/Desktop/poker_solver_worktrees/pr-85-doc-drift-v2`.
- Zero `rm`, `mv`, `git rm`, or destructive ops anywhere.
- No edits to files in `/Users/ashen/Desktop/poker_solver/` (the
  main workspace).

## Per-edit summary

### Items actioned (3/7)

1. **USAGE.md header (item 1)** — line 1 changed from
   `# Using poker_solver — End-User Guide (v1.4.x)` to
   `# Using poker_solver — End-User Guide (v1.7.x)`.

2. **CHANGELOG.md .dmg mention (item 2)** — two surgical insertions:
   - New `[1.7.2] - 2026-05-26` section above `[1.7.0]`, documenting
     the critical fork-bomb fix (PR #42, commit `728206e`,
     `multiprocessing.freeze_support()` guard added to the
     PyInstaller entry point). Notes that the v1.6.0 `.dmg` asset
     has been retroactively pulled from the GitHub Release.
   - "Retroactive amendment (2026-05-26)" note inside the `[1.6.0]`
     section, pointing readers at the v1.7.2 entry and the RCA doc
     (`docs/dmg_spawn_loop_rca_2026-05-26.md`).
   No other CHANGELOG content was modified.

4. **docs/dmg_install_guide.md (item 4)** — prepended a top banner
   below the `# macOS .dmg Install Guide (v1.6.0)` header flagging
   that the v1.6.0 `.dmg` has been retroactively pulled and pointing
   at the upcoming v1.7.2 repackaged build.

### Items NOT actioned (4/7) — file no longer exists

The brief's git-status snapshot was stale; PR #79 (already merged)
cleaned up the relevant files before this v2 attempt began.

3. **`docs/README_proposed_update_2026-05-23.md`** — file does not
   exist in `origin/main`. No STATUS banner needed.

5. **`docs/FINAL_PRE_SIGNON_AUDIT.md`** — file does not exist. No
   post-audit retraction needed.

6. **Workspace-root release-notes drafts** (`RELEASE_NOTES_2026-05-23.md`,
   `RELEASE_HEADLINES_2026-05-23.md`, `RELEASE_CHECKLIST_2026-05-23.md`)
   — files do not exist. No `docs/_archive_2026-05-23/README.md` was
   created since there were no orphan files to index.

7. **`docs/USER_GREETING.md`, `docs/SIGNON_CHECKLIST.md`** — files do
   not exist. No STATUS banners needed.

## Verification

`git status` inside the worktree before commit confirmed exactly 3
files staged (CHANGELOG.md, USAGE.md, docs/dmg_install_guide.md).

`git diff --stat` confirmed +34 / -1 lines across the 3 files.

## Coordination — non-conflicts

- **PR #79** (cleanup) — ALREADY MERGED before this PR. Its file
  removals are why items 3/5/6/7 are no-ops; no conflict risk.
- **PR #83** (doc code bug fixes) — touches README.md and the
  now-removed `docs/README_proposed_update_2026-05-23.md`. Zero
  file overlap with this PR.
- **PR #84** (mypy followup) — touches `.py` files only. Zero overlap.
- **Phase 3 SIMD re-rebase** — touches `crates/cfr_core/src/simd.rs`
  only. Zero overlap.

## Followups (if user wants)

None forced by this PR. The four no-op items could be re-investigated
if those files are re-introduced in future, but the orphan-archive
work item is effectively closed by PR #79's deletion of the
underlying files.
