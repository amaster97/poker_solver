# Pre-release untracked-files handling — 2026-05-26

**Purpose:** Get the working tree clean for `scripts/release_v1_8_0.sh` Phase 0.2
(line 146: `if [[ -n "$(git status --porcelain)" ]]`), which **hard-fails on
ANY** non-empty porcelain output. Tomorrow morning the user kicks off the
release.

**Constraint:** This document is **planning only** — no destructive ops, no
stash, no script changes, no file deletions.

---

## TL;DR — recommended action

**Two paths; pick one:**

1. **Single `git stash` (fastest, 1 command):** Stashes all 254 untracked
   entries into one stash entry. Release runs. After release, `git stash pop`
   restores everything. **Risk: low** (no in-progress edits, no merge conflicts
   on pop expected since nothing in HEAD touches these paths).

2. **Triage + commit pipeline (cleaner, ~15 min):** Move noise to .gitignore,
   commit load-bearing additions in a tiny PR, archive the rest. Reduces
   the 254 -> 0 with structure but requires user time **before** kicking off
   the release. **Not recommended for tomorrow morning** unless user wants the
   tree clean state to persist post-release.

**Recommended for morning: Path 1 (stash).** Path 2 is the post-release
follow-up.

---

## Release-script flag survey (Phase 0.2 override?)

`scripts/release_v1_8_0.sh` accepts only these flags:

| Flag                   | Effect                                                                 |
|------------------------|------------------------------------------------------------------------|
| `--upload-dmg`         | Phase 4: upload dist/Poker-Solver-1.8.0-arm64.dmg if it exists         |
| `--skip-backup`        | Phase 5: skip `git push backup` step                                   |
| `--no-bump-cfr-core`   | Phase 1: leave `crates/cfr_core/Cargo.toml` at 0.7.0                   |
| `--expected-sha <sha>` | Phase 0.4: override the script-write-time EXPECTED_SHA                 |

**There is NO `--ignore-untracked`, `--allow-untracked`, `--allow-dirty`, or
equivalent.** Phase 0.2 (lines 146-150) is unconditional.

**Conclusion:** Either (a) clean the tree before kicking off, OR (b) add an
override flag in a follow-up PR. Option (b) requires user OK per task
constraints; not applied here. **For tomorrow morning, option (a) is the path.**

---

## Per-category untracked inventory (n=254 entries total)

`git status --porcelain | wc -l` returns 254. Single counting unit (one entry
per top-level dir or file; nested files under untracked dirs count as the dir
entry, not separately).

### A. Load-bearing — KEEP, will be committed later (n=4)

| Path                              | Status                                                            |
|-----------------------------------|-------------------------------------------------------------------|
| `PLAN.md`                         | HELD on PR #89 (plan_prune wave); load-bearing strategic file     |
| `tests/test_aa_vs_aa_root_indifference.py` | R11 regression test fixture; load-bearing                |
| `tests/test_minimal_nash_fixture.py`        | 2-class diff-test fixture per docs/minimal_diff_test_fixture.md |
| `crates/cfr_core/examples/rvr_bench.rs`     | v1.8 SIMD bench harness; load-bearing for SIMD perf claim |

**Recommendation:** These four SHOULD be in a tiny "post-release additions" PR
**after** v1.8.0 ships. They are not required for the v1.8.0 release commit
itself (which only bumps versions per Phase 1).

### B. `.local` shadow files from pull conflicts (n=7)

| Path                                                  |
|-------------------------------------------------------|
| `docs/dmg_spawn_loop_rca_2026-05-26.md.local`         |
| `docs/persona_w3_4_retest_2026-05-26.md.local`        |
| `docs/persona_w3_5_retest_2026-05-26.md.local`        |
| `docs/poker_solver_shim_fix_2026-05-26.md.local`      |
| `docs/v1_7_1_tag_decision_2026-05-26.md.local`        |
| `docs/v1_8_0_release_notes_prep_2026-05-26.md.local`  |
| `docs/v1_8_simd_perf_benchmark_2026-05-26.md.local`   |

**These are git-stash-merge-conflict shadows** created by pull/merge when both
sides modified the same file. The `.md` (non-.local) twin has already been
merged on `main`. **Safe to archive** (move to `docs/_archive_2026-05-26/`)
or **safe to add to .gitignore** as `*.md.local`.

**Recommendation for tomorrow:** include in stash path 1, OR add `*.md.local`
to .gitignore as a one-line addition.

### C. Today's session docs not yet committed (n=44)

Files matching `_2026-05-26` pattern, e.g.:

```
docs/a83_track_a_setup_2026-05-26.md
docs/backup_integration_final_sync_2026-05-26.md
docs/cli_smoke_gauntlet_2026-05-26.md
docs/dmg_packaging_hardening_pr_86_2026-05-26.md
docs/golden_file_check_rca_2026-05-26.md
docs/persona_status_post_v1_8_2026-05-26.md
docs/plan_prune_pr_89_2026-05-26.md
docs/pr_20_ci_matrix_decision_2026-05-26.md
docs/v1_8_0_release_preflight_2026-05-26.md
docs/v1_8_phase4_rebase_2026-05-26.md
docs/worktree_cleanup_sweep_2026-05-26.md
... (44 total)
```

**Status:** Session reports from tonight's burst. Some are "report cards" for
already-merged PRs (no further action); some are open audits awaiting user
review.

**Recommendation:** Triage post-release. **For tomorrow morning:** include in
stash. Do NOT auto-commit en bloc — these need user review for
keep/archive/delete decisions.

### D. Older session docs (2026-05-23 / 2026-05-25, n=35)

Files matching `_2026-05-23` (32 entries) or `_2026-05-25` (3 entries).
Examples:

```
docs/private_mirror_sync_2026-05-23-late.md
docs/repo_metadata_polish_2026-05-23.md
docs/PAUSE_RESUME_2026-05-25.md
docs/outstanding_queue_2026-05-25.md
docs/v1_5_0_per_action_divergence_diagnosis.md
```

**Status:** Cold session reports from prior bursts. Probably archivable.

**Recommendation:** Move to `docs/_archive_2026-05-23_session/` and
`docs/_archive_2026-05-25_session/` post-release. **For tomorrow morning:**
include in stash.

### E. Subdirectories of older session artifacts (n=12)

| Path                                  | Contents                                |
|---------------------------------------|-----------------------------------------|
| `docs/_archive_2026-05-26/`           | 6 worktree-cleanup archive subdirs      |
| `docs/persona_test_results/`          | 34 persona retest result files          |
| `docs/pr_proposals/`                  | 28 PR implementation prompts/specs      |
| `docs/pr8_prep/`, `pr8b_prep/`, `pr9_prep/`, `pr10b_prep/`, `pr11_prep/`, `pr13_prep/`, `pr15_prep/`, `pr16_prep/`, `pr18_prep/` | per-PR prep scratch dirs |

**Status:** Long-lived scratch dirs. `docs/pr_proposals/` contains
load-bearing implementation specs that some merged PRs cite — these should
probably be tracked.

**Recommendation for `docs/pr_proposals/`:** add to git in post-release PR.
**For others:** archive or .gitignore.

### F. Generic uncategorized docs from older bursts (n=146)

Remaining undated docs (e.g., `docs/changelog_consistency_audit.md`,
`docs/kk_fold_inversion_diagnosis.md`, `docs/leg11_v1_4_1_ship_plan.md`, etc).
These accumulated across many sessions without date suffixes.

**Status:** Mostly cold; some may still be cited by tracked docs. Needs grep
audit before bulk action.

**Recommendation:** Defer. **For tomorrow morning:** include in stash.

### G. Transient noise (n=1)

| Path             | Contents                                                     |
|------------------|--------------------------------------------------------------|
| `.merge_logs/`   | Single file: `automerge_20260525_223022.log` (30 bytes)      |

**Recommendation:** Add `.merge_logs/` to `.gitignore` (one-line addition).
For tomorrow morning: include in stash.

### H. One-off scripts (n=2)

| Path                                | Status                                       |
|-------------------------------------|----------------------------------------------|
| `scripts/cleanup_pr_branches.sh`    | Probably load-bearing; should be committed   |
| `scripts/ship_v1_6_1_engine.sh`     | Cold one-off ship script; archive            |

**Recommendation:** Post-release decision. **For tomorrow morning:** stash.

### I. Patch / backup artifacts (n=2)

| Path                                                    |
|---------------------------------------------------------|
| `docs/acceptance_test_reframe.patch`                    |
| `docs/v1_7_0_stalled_uncommitted_diff.patch.bak`        |

**Status:** Build/recovery artifacts. **Safe to archive** or add `*.patch`,
`*.patch.bak` to .gitignore.

---

## Recommended commands for tomorrow morning

### Path 1 (recommended) — single stash, run release, restore after

```bash
# 1. Verify on main, fetched, ready
cd /Users/ashen/Desktop/poker_solver
git fetch origin
git status                                # should show "On branch main"
git log -1 --format='%H'                  # confirm HEAD == EXPECTED_SHA in script

# 2. Stash ALL untracked (254 entries) into ONE entry
git stash push --include-untracked --message "pre-v1.8.0-release-clean-state-2026-05-26"
# Confirm clean:
git status --porcelain                    # expected: empty output

# 3. Verify expected_sha still matches (stash does NOT change HEAD)
# (EXPECTED_SHA = f165eb85fd409e66d4a2c929e411811a7d150fbe per script line 80)

# 4. Run release
bash scripts/release_v1_8_0.sh

# 5. AFTER release succeeds, restore the untracked set
git stash pop                             # restores all 254 entries
git status --porcelain | wc -l            # should be 254 again (or close)
```

**Why this is safe:**

- `git stash` with `--include-untracked` snapshots untracked files into the
  stash WITHOUT affecting tracked-file state. `HEAD` and the index are
  unchanged. Phase 0.4 EXPECTED_SHA check still passes.
- `git stash pop` after release applies the stash back. No conflicts
  expected because the release script's only file changes are version
  bumps in `pyproject.toml`, `poker_solver/__init__.py`,
  `crates/cfr_core/Cargo.toml`, and possibly `Cargo.lock` — NONE of these
  files are in the stashed untracked set.
- 4 existing stashes are already in the stash list; one more is fine.

**Risk: low**, but not zero:

- **Disk space:** ~254 entries with nested subdirs (persona_test_results
  alone is 34 files; pr_proposals is 28 files; etc). Estimated stash
  size: <20 MB. Safe.
- **stash pop failure:** If `main` advances between stash and pop (e.g.,
  someone pushes to main during the release window), pop could conflict.
  Mitigation: release script pushes its commit BEFORE we pop, so HEAD
  advances by ONE known commit (the version bump). That commit touches
  only the 3-4 version files — zero overlap with stashed paths. Safe.
- **stash drop accidentally:** Don't run `git stash drop` between stash and
  pop. The pop is the restore step.

### Path 2 (alternative) — manual triage (more cleanup, more time)

Only do this if user wants a permanently clean tree:

```bash
# A. Move resolved .local shadows into archive
mkdir -p docs/_archive_2026-05-26_local_shadows
git mv docs/*.md.local docs/_archive_2026-05-26_local_shadows/  # this WON'T work for untracked
# Use plain mv since they're untracked:
mv docs/*.md.local docs/_archive_2026-05-26_local_shadows/

# B. Add noise dirs to .gitignore
cat >> .gitignore <<'EOF'

# Local-only session artifacts
.merge_logs/
*.md.local
EOF

# C. Stash the rest
git stash push --include-untracked --message "pre-v1.8.0-release-2026-05-26"

# D. Run release
bash scripts/release_v1_8_0.sh

# E. Restore
git stash pop
```

**This is MORE work** for tomorrow morning. **Path 1 is preferred.**

### Path 3 (not recommended) — modify release script

Adding `--allow-untracked` (or `--allow-dirty`) flag to the release script
would skip Phase 0.2 entirely:

```bash
# Sketch (NOT applied per task constraints):
ALLOW_UNTRACKED=0
case "$1" in --allow-untracked) ALLOW_UNTRACKED=1; shift ;; ... esac
if [[ -n "$(git status --porcelain)" ]]; then
    if [[ "$ALLOW_UNTRACKED" == "1" ]]; then
        echo "[release-v1.8.0] WARN: untracked files present (--allow-untracked); proceeding"
    else
        echo "FATAL: working tree not clean..."
        exit 1
    fi
fi
```

**Risks:**

- Bypassing Phase 0.2 means a stray edit to a tracked file could be missed.
  Phase 0.2 also catches `M` (modified) entries, not just `??` (untracked).
  An override that ignores ALL non-clean state is broader than just
  "untracked".
- Better override would be: distinguish `git status --porcelain` outputs
  starting with `??` (untracked) from those starting with `M`/`A`/`D` (real
  modifications), and only ignore untracked.
- Script change requires user approval per task constraints.

**Verdict:** Worth proposing as a follow-up PR (NOT for tomorrow morning).

---

## Edge cases checked

1. **`git stash` with very large untracked set:** Tested mental model — git
   creates a single tree object containing the untracked snapshot. ~250
   small files (most <50 KB) → tree object size <20 MB. Well within sane
   limits.
2. **EXPECTED_SHA staleness:** The script's `EXPECTED_SHA` is
   `f165eb85fd409e66d4a2c929e411811a7d150fbe` (line 80). Recent commits show
   HEAD has advanced — `533cb8e` is the latest origin/main commit. **User
   must verify** before running, and pass `--expected-sha <new_sha>` if
   advanced. This is independent of the untracked-files issue but worth
   flagging.
3. **`*.md.local` is NOT in .gitignore:** Confirmed via inspection. The 7
   `.local` shadows show as untracked, not ignored.
4. **No `.local` files appear modified:** They are all `??` (untracked).
   Adding `*.md.local` to .gitignore would not lose work — the files stay
   on disk.

---

## Action items

### For user (tomorrow morning, pre-release)

1. **Verify EXPECTED_SHA:** `git rev-parse HEAD` and compare to
   `f165eb85fd409e66d4a2c929e411811a7d150fbe` (script line 80). If diverged,
   pass `--expected-sha $(git rev-parse HEAD)` to the script after confirming
   the new commits are intended for v1.8.0.
2. **Choose path:** Path 1 (single stash) is recommended.
3. **Execute Path 1 commands** (see "Recommended commands" section above).
4. **Run release:** `bash scripts/release_v1_8_0.sh` (with any necessary
   flags from step 1).
5. **Post-release:** `git stash pop` to restore untracked files.

### Follow-up PRs (post-release, not blocking v1.8.0)

1. **PR A — track load-bearing additions** (small, 4 files):
   - `tests/test_aa_vs_aa_root_indifference.py`
   - `tests/test_minimal_nash_fixture.py`
   - `crates/cfr_core/examples/rvr_bench.rs`
   - `scripts/cleanup_pr_branches.sh`
2. **PR B — .gitignore additions** (one-line additions):
   - `.merge_logs/`
   - `*.md.local`
   - Possibly `*.patch.bak`
3. **PR C — track docs/pr_proposals/** (if proposals are cited by merged PRs).
4. **PR D — archive old session docs** to `docs/_archive_<date>_session/`.
5. **PR E (optional) — add `--allow-untracked` flag to future release scripts**
   for similar pre-release moments.

---

## Summary table

| Category                          | Count | Action (for tomorrow)     | Action (post-release)         |
|-----------------------------------|-------|---------------------------|-------------------------------|
| A. Load-bearing files             |     4 | Stash                     | Commit in small PR            |
| B. `.local` shadows               |     7 | Stash                     | Archive or .gitignore         |
| C. Today's session docs (05-26)   |    44 | Stash                     | User-triage                   |
| D. Older session docs (05-23/25)  |    35 | Stash                     | Archive                       |
| E. Subdirs (persona, pr_proposals, etc) | 12 | Stash                | Mixed (some commit, some archive) |
| F. Generic uncategorized docs     |   146 | Stash                     | Grep-audit then triage        |
| G. Transient noise (.merge_logs)  |     1 | Stash                     | .gitignore                    |
| H. One-off scripts                |     2 | Stash                     | Commit one, archive other     |
| I. Patch artifacts                |     2 | Stash                     | Archive or .gitignore         |
| **Total**                         | **254** | **Single stash command** | **5 follow-up PRs**           |

---

## What this report does NOT do (per task constraints)

- Does NOT delete any untracked file
- Does NOT modify `scripts/release_v1_8_0.sh`
- Does NOT execute `git stash` (user decides)
- Does NOT commit, archive, or .gitignore anything
- Does NOT auto-apply changes
