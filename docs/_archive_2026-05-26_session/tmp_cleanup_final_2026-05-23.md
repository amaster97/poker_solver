# /tmp/ Cleanup Sweep — 2026-05-23 Final

**Time:** 22:21 EDT
**Trigger:** End-of-session cleanup per `feedback-no-concurrent-branch-ops`

## Worktrees

### Before (16 entries)

All under `~/Desktop/poker_solver_worktrees/` plus the shared tree at `~/Desktop/poker_solver/` — none in `/tmp/`.

```
/Users/ashen/Desktop/poker_solver                                      ca8c7af [main]
/Users/ashen/Desktop/poker_solver_worktrees/cli-ergonomics             7584e06 [pr-39-cli-ergonomics]
/Users/ashen/Desktop/poker_solver_worktrees/persona-corrections        71d161d [pr-38-persona-corrections]
/Users/ashen/Desktop/poker_solver_worktrees/phase2b-audit-revision     dcc9d83 [pr-41-phase2b-audit-revision]
/Users/ashen/Desktop/poker_solver_worktrees/pr-17-plan-c               ea2511c [pr-17-plan-c-dense-slabs]
/Users/ashen/Desktop/poker_solver_worktrees/pr-23-p0-off-by-one        0bafcfa [pr-34-p0-off-by-one]
/Users/ashen/Desktop/poker_solver_worktrees/pr-24a-gui-rvr-slider      8b1f672 [feature/pr-24a-gui-rvr-slider]
/Users/ashen/Desktop/poker_solver_worktrees/pr-24b-gui-nodelock-asym   98c3013 [feature/pr-24b-gui-nodelock-asym]
/Users/ashen/Desktop/poker_solver_worktrees/pr-35-canonicalization     33e03ea [pr-35-canonicalization]
/Users/ashen/Desktop/poker_solver_worktrees/pr-40-acceptance-test-fix  c058e97 [pr-40-acceptance-test-fix]
/Users/ashen/Desktop/poker_solver_worktrees/python-delegate            29a00c0 [pr-33-python-delegate]
/Users/ashen/Desktop/poker_solver_worktrees/river-parity-fix           6bf8b9e [pr-25-river-parity-test-fix]
/Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.0                d885bca [ship-v1.6.0]
/Users/ashen/Desktop/poker_solver_worktrees/spec-corrections           1b95c5b [pr-29-persona-spec-corrections]
/Users/ashen/Desktop/poker_solver_worktrees/v1-7-0-nash-wrapper        e151de4 [pr-43-nash-wrapper]
/Users/ashen/Desktop/poker_solver_worktrees/w3-5-reversal              90a3c27 [pr-42-w3-5-reversal]
```

### After (unchanged — 16 entries)

No worktree removals. All 16 are persistent feature branches under `~/Desktop/poker_solver_worktrees/` per memory protocol — KEEP all. `git worktree prune --dry-run` showed no stale entries.

## /tmp Artifacts

### Removed (44 files, 0 dirs)

**v1.7.x session files (13):**
- `v1.7.0_fresh_dir.env`
- `v1.7.1_compare_wrapper_vs_direct.py`
- `v1.7.1_independent_verify.py`
- `v1.7.1_poker_math_check.py`
- `v1.7.1_solveA_result.json`
- `v1.7.1_solveB_result.json`
- `v1.7.1_solveC_result.json`
- `verify_worktree_path.txt`
- `v1_7_0_ship_env.sh`
- `sync_path.txt`
- `usage_pr48.md`
- `orphaned.txt`
- `linked.txt`

**w-wave driver/output files (23):**
- `w2_3_aggregator_output.log`, `w2_3_nash_output.log`, `w2_3_nash_scoped_output.log`, `w2_3_worktree_path.txt`
- `w2.1_profile_driver.py`, `w2.1_profile_wt_path.txt`, `w2.1_retest_output.txt`, `w2.1_retest.py`, `w2.1_smaller_driver.py`, `w2.1_smaller_output.txt`, `w2.1_smaller_result.json`, `w2.1_wtdir.txt`
- `w2.3-watchdog-nash.log`, `w2.3-watchdog-path.txt`
- `w23_minimal_driver.py`, `w23_minimal_output.txt`, `w23_scaled_driver.py`, `w23_scaled_output.txt`
- `w34_driver.py`, `w34_scaled_driver.py`, `w34_scaled_output.txt`, `w34_w43_wtdir.txt`
- `w43_driver.py`

**pr22 marker/log files (8):**
- `pr22_critical_final.log`, `pr22_single.log`
- `pr22c_seen_b2iy5kzks`, `pr22d_seen_b2iy5kzks`, `pr22d_seen_bv8xif2az`
- `pr22final_diff`, `pr22final_full`, `pr22final2_bdm6xyhq2`

### Kept (not session-spawn artifacts)

Older `/tmp/` files predating this session burst, untouched:
- Earlier May 23 benchmarks: `bench_*.py`, `plan_c_microbench.py`, `dcfr_*.py`, `apples_*.py`, `measure_*.py`
- Pre-burst docs: `pr10a_spec.md`, `pr10b_spec.md`, `launch_kickoff_10b.md`, `plan_current.md`
- Pre-burst logs: `cutover_run.log`, `changelog_origin_main.md`, `acc_head.txt`, `cli_diff_compare.txt`
- System sockets, Apple launchd dirs, claude-501, claude-mcp-browser-bridge-ashen — system state, untouchable
- Older PR check fragments: `check_pr_*` (May 21)

These weren't on the removal list because (a) they're older than the session burst (not associated with sub-agent spawns this evening) or (b) they could still serve as historical reference. Conservative keep.

## Active Processes

`ps aux | grep -E "(pytest|cargo|maturin)"` returned zero matches. No risk of removing in-flight work.

## Final Verification

```
$ ls /tmp/ | grep -E "(poker|v1\.|w[0-9]|pr-|dmg|usage|ship)" | wc -l
0
$ git worktree list | wc -l
16
```

## Verdict

**CLEAN** — All session-spawn artifacts purged; legitimate persistent worktrees preserved; no active processes interrupted.
