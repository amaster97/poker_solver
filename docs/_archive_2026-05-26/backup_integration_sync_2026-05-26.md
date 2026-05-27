# backup/integration sync 2026-05-26

Merged `origin/main` into `backup/integration` via temporary worktree at `/tmp/integration-sync-2`.

## Result

- **Post-merge `backup/integration` HEAD:** `daab5f5` (merge commit; first-parent = `1383a84` integration, second-parent = `5ead08f` origin/main).
- **Push:** `1383a84..daab5f5  HEAD -> integration` (succeeded as a normal merge-commit push).
- **Worktree:** removed.

## Scope deviation from procedure

User procedure expected **5 add/add conflicts**. Actual conflict surface was **21 files** (10 add/add, 9 content, 2 modify/delete). The broader divergence is consistent with integration having accumulated work-in-progress while origin merged ~10 PRs (PR #32, #38, #42, #44, #45, #46, #47, #48 + others). Applied user's stated default rule (origin/main is source-of-truth) to all but the planning-doc exceptions.

## Per-file resolution

### Origin-wins (19 files): `git checkout --theirs && git add`

Note: in this worktree HEAD=integration (`--ours`), MERGE_HEAD=origin/main (`--theirs`). The user's procedure had the flag inverted; semantics-wanted (= origin/main version) maps to `--theirs` here. Verified by SHA inspection before applying.

**The 5 listed (procedure expected):**

- `scripts/ship_v1_7_1.sh` — integration's was pre-PR-#27 version (timeout=60); origin has timeout=300 + updated EXPECTED_MAIN. ORIGIN.
- `tests/test_exploit_diff.py` — origin has formatting tweaks from merged PR #38. ORIGIN.
- `tests/test_node_locking.py` — origin has `initial_hole_cards=None` (matched dataclass default); integration had `()`. ORIGIN.
- `tests/test_preflop_python.py` — origin restructured the test to call `solve_hunl_preflop` (matches PR #31 validation moving up); integration's was the old version. ORIGIN.
- `ui/state.py` — origin has PR #46 mypy fix (`selected_library_spot_id` field, no longer imports `HandClass`/`RangeVsRangeResult` directly). ORIGIN.

**6 additional add/add not in user's list:**

- `crates/cfr_core/src/exploit.rs` — origin has PR #23 `pub(crate)` exposure for `dcfr_vector.rs` consumer. ORIGIN.
- `crates/cfr_core/src/simd.rs` — origin has PR #32 / #33 (v1.8 Phase 3 + 4) SIMD docstrings + AVX2 + SSE2 paths; integration is pre-PR-#8 stub. ORIGIN.
- `docs/SIGNON_SUMMARY_2026-05-25.md` — origin has post-pause-resume-wave updated copy. ORIGIN.
- `docs/WELCOME_BACK_USER_2026-05-23.md` — origin's references current `49c1421` HEAD + 7 open PRs; integration referenced `60a9818` + 12 PRs (now outdated). ORIGIN.
- `docs/dmg_install_guide.md` — origin has the fork-bomb retraction banner (PR #42 follow-up). ORIGIN.
- `poker_solver/range_aggregator.py` — origin has the updated v1.3.1 `hero_player` docstring. ORIGIN.

**8 UU content conflicts:**

- `CHANGELOG.md` — origin includes v1.7.2 dmg fork-bomb entry; integration was pre-PR-#42. ORIGIN.
- `README.md` — origin has the latest copy mentioning Rust performance tier + DCFR push/fold. ORIGIN.
- `USAGE.md` — origin header is "v1.7.x"; integration's was "v1.0.0" (stale). ORIGIN.
- `crates/cfr_core/src/hunl.rs` — integration had PR 22 Fix A mirror commentary; origin omitted (refined). ORIGIN.
- `crates/cfr_core/src/lib.rs` — origin's lib.rs has the post-PR #23 module layout. ORIGIN.
- `poker_solver/__init__.py` — origin removed `RangeVsRangeNashResult` / `solve_range_vs_range_nash` exports (matches PR #46 cleanup). ORIGIN.
- `pyproject.toml` — origin's `version = "1.7.0"`; integration had `"1.4.0"` (severely stale). ORIGIN.
- `scripts/build_macos_dmg.sh` — origin's PR 86 version-derivation hardening pre-flight check. ORIGIN.

### Integration-wins (2 modify/delete: kept HEAD version, just `git add`)

- `PLAN.md` — origin DELETED this file (post-sign-on cleanup); integration has 600 lines of load-bearing planning context (R6-R11 status, v1.7.1 bundle composition, in-flight PR list, Gate 5 status). Per user's [Plan-sync rule](feedback_plan_sync.md) PLAN.md is load-bearing on the local clone. **KEPT INTEGRATION** (origin will continue to not track it; PLAN.md remains on integration as planning workspace).
- `docs/autonomous_burst_release_plan.md` — same pattern: origin deleted, integration has planning content. KEPT INTEGRATION.

## Verification

- Final `git status --short | grep -E '^(UU|AA|UD|DU|AU|UA|DD)'` returned no matches before commit.
- Merge commit created with git's default message ("Merge remote-tracking branch 'origin/main' into HEAD").
- Push to private mirror confirmed: `1383a84..daab5f5  HEAD -> integration`.

## Surface for user

The procedure was scoped to 5 add/add conflicts but the actual diverged surface was ~21 files. Applied origin-wins default everywhere except the 2 planning docs origin had deliberately deleted. No silent-overwrite of integration-unique planning context occurred — integration's `PLAN.md` and `docs/autonomous_burst_release_plan.md` are preserved on the merge result.
