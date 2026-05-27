# PR #20 (`pr-64-cross-platform-ci-matrix`) — CI Matrix Decision

**Date:** 2026-05-26
**Run ID:** 26435671490
**Head SHA:** 2226c6d61a3a7d7e44ff4d0a56a15f73a4af5c51
**Decision:** **SURFACED FOR USER — DO NOT MERGE**

## Current Check Matrix

| Workflow / Check | Status | Conclusion |
|---|---|---|
| Golden File Check / check | COMPLETED | SUCCESS |
| Lint / rust | COMPLETED | SUCCESS |
| Lint / python | COMPLETED | SUCCESS |
| Ship Dry Run / bundle-dry-run | COMPLETED | SUCCESS |
| Skip-Ban (Acceptance Tests) / check | COMPLETED | SUCCESS |
| CI / test (macos-14, aarch64-apple-darwin) | COMPLETED | **CANCELLED (timeout 30m)** |
| CI / test (ubuntu-22.04, x86_64-unknown-linux-gnu) | COMPLETED | **CANCELLED (timeout 30m)** + 5 errors observed |
| CI / test (macos-13, x86_64-apple-darwin) | **QUEUED** | pending |

`mergeable: UNKNOWN`, `mergeStateStatus: UNKNOWN`. Not mergeable.

## Diagnosis

### Issue 1 — 30-minute timeout is too tight for the "fast" tier

Both completed matrix jobs hit the workflow's `timeout-minutes: 30` ceiling. Pytest progress at cancellation:

- **macos-14 (aarch64)**: 93% complete — last logged line `tests/test_river_diff.py` at 06:36:14, cancelled at 06:44:23. No test failures observed; pure wall-clock exhaustion.
- **ubuntu-22.04 (x86_64)**: 72% complete — last logged line `tests/test_preflop_diff.py` at 06:42:50, cancelled at 06:44:24. **However: `tests/test_leduc_diff.py EEEEE` at 06:32:33** — 5 errors (see Issue 2).

The `pytest -m "not slow"` "fast" tier transitively includes the heavyweight Python-Rust differential suite (`test_leduc_diff`, `test_preflop_diff`, `test_river_diff`, `test_dcfr_diff`, `test_exploit_diff`, `test_hunl_diff`). These exercise both backends end-to-end and individually run 2-5 min each.

### Issue 2 — Linux-only regression in `test_leduc_diff.py` (5 errors)

ubuntu-22.04 shows `tests/test_leduc_diff.py EEEEE` (all 5 tests in the file errored). The job was cancelled before pytest could print the traceback summary, so the root cause is not captured in the log tail. macOS aarch64 ran the same suite without errors (continued past Leduc).

All 5 tests share a module-scoped `both_results` fixture:
```python
@pytest.fixture(scope="module")
def both_results():
    game = LeducPoker()
    py = solve(game, iterations=ITERATIONS, backend="python", **DCFR_KWARGS)
    rs = solve(game, iterations=ITERATIONS, backend="rust", **DCFR_KWARGS)
    return py, rs
```

Hypotheses (in priority order):
1. **Fixture timeout under Linux Rosetta-free native x86_64 build** — the comment in `test_leduc_diff.py:36-38` notes the fixture has historically been slow under x86_64 Python *under Rosetta* on Mac. Native Linux x86_64 should be *faster*, not slower; but if `pytest-timeout` is killing the fixture itself, all 5 tests would error identically. The `--timeout=120` flag from the workflow may be overriding the per-test `@pytest.mark.timeout(300)` annotations.
2. **Real Linux-specific numerical/code divergence** in the Rust DCFR Leduc path. AVX2 runtime-detect path (PR #35 / `db8d646`) only landed for x86_64; macOS aarch64 takes scalar/NEON. Could be a real bit-divergence the diff suite catches.
3. **PyO3/maturin native-extension load issue** specific to manylinux2014 wheel.

### Issue 3 — macos-13 (Intel) still QUEUED

GitHub's macos-13 runner pool has been congested; the job has been queued ~50 min without starting. Will start eventually but cannot be relied on for this session.

## Decision Rationale

Per `feedback_pr10a5_autonomous_commit.md`, audit-clear PRs ship autonomously *except* C-CRIT findings. Two CANCELLED matrix jobs + 5 unexplained Linux test errors are NOT audit-clear:

- The Linux `EEEEE` could be a **real code regression**. Per `feedback_empirical_over_audit.md`, when empirical evidence shows failure, we keep digging at the mechanical level — we do NOT merge.
- The 30-min timeout is fixable, but fixing it without also seeing the full Linux traceback would mask the Issue 2 errors. Surfacing them first is the correct order.

Per the procedure: **"If code regression on cross-platform: surface to user; this is design-shaped."**

## Action Taken

- **No merge performed.**
- **No fix PR opened yet** — opening `pr-96-ci-matrix-fix` blindly would only fix the timeout (Issue 1) and could *hide* the Linux regression (Issue 2) by letting the suite run longer without first understanding the error mode.
- **Surfaced for user review.**

## Recommended Next Steps (for user to authorize)

1. **Re-run PR #20 with `timeout-minutes: 60`** as a one-off (manual `gh workflow run` after a no-op commit), so we can see the full pytest error summary for Linux. This will reveal the Issue 2 traceback.
2. **Once Issue 2 is understood**, decide:
   - If it's a real Linux regression: file a separate fix PR on the code path, not on CI config.
   - If it's a timeout-cascading-into-fixture failure: shard the suite (split diff tests into a separate "diff" job that runs in parallel with the fast tier), then re-run.
3. **Either way, `timeout-minutes: 30` is too tight** for the current "fast" tier definition — the diff suite alone is ~15-20 min wall-clock. Either:
   - Bump to `timeout-minutes: 60`, OR
   - Move `*_diff.py` to its own matrix job (parallelized; each leg stays under 30m).
4. **macos-13 job will eventually run** — leave PR #20 open; don't close. Check status in the morning.

## Final State

- **Main HEAD unchanged** — no merge happened.
- **PR #20 still open**, blocked on cross-platform matrix.
- **No new branch created** — Issue 2 must be diagnosed first.

## Files Referenced

- `/Users/ashen/Desktop/poker_solver/.github/workflows/ci.yml` (PR branch only; not on main)
- `/Users/ashen/Desktop/poker_solver/.github/workflows/lint.yml` (PR branch only; not on main)
- `/Users/ashen/Desktop/poker_solver/tests/test_leduc_diff.py` (the failing test file)
