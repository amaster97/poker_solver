# v1.7.1 Ship Retry #3 — Postmortem

**Date:** 2026-05-25
**Status:** KILLED mid-Phase-5 (cargo lib tests)
**v1.7.1 SHIPPED:** No
**Brown acceptance gate:** UNKNOWN (never reached — process killed before pytest phase)
**Origin HEAD:** still at `60a98189` (unchanged)
**Tag `v1.7.1`:** does not exist locally or on origin
**Release `v1.7.1`:** does not exist on GitHub

---

## TL;DR

Retry #3 did NOT silent-skip Brown gate again. It also did NOT validate Brown
gate. It KILLED during cargo lib tests in Phase 5, well before the pytest
phase where Brown gate runs. The kill cause is external (no natural cargo
stall point at this stage; 49 of 50 tests had completed with `ok`).

The silent-skip-fix infrastructure (PR 60 `_skip_or_fail` helper +
`POKER_SOLVER_REQUIRE_BROWN_PARITY=1` env var + ship-script binary-link
guard) was AUTHORED at 13:38 — *after* retry #3 stopped at ~13:31. So if a
retry #4 is launched with the current state, the safety net is now in place
on the shared tree, BUT PR 60 is not yet in the bundle's cherry-pick list,
meaning a fresh worktree would not inherit the test-side fix.

---

## Outcome

**Outcome:** killed (terminated externally).

### Phase reached
- Phase 1 (worktree creation): completed
- Phase 2 (cherry-picks): completed — 8 PRs cherry-picked cleanly (PR 51, 50, 52, 54, 55, 56, 53b, 53c)
- Phase 3 (version bumps): completed
- Phase 4 (CHANGELOG entry): completed
- Phase 5 (smoke matrix):
  - `cargo build --release`: completed (7.67s)
  - `cargo test --lib --release`: **TERMINATED MID-STREAM** at 49/50 tests reported
  - Subsequent steps (maturin, pytest exploit_diff, Brown gate, asymmetric sanity, non-slow tier): never reached

### Evidence of kill (not natural exit)
- Log ends with `test exploit::tests::flat_tree_matches_recursive_aggregate_on_river ... ok` — the 49th test (the 50th from retry #1's log)
- No `test result: ok. 50 passed; …` summary line (cargo test always prints this on success)
- No `[ship-v1.7.1] maturin develop --release...` line (the next phase marker)
- No process running (verified at 13:36)
- Log file mtime frozen at 13:31; current time 13:36; no growth
- No ERROR, FAILED, halt, or kill string in log
- Retry #1's identical cargo phase completed in 17.47s, so retry #3 did not stall here

### Bundle composition in retry #3
Retry #3 ran with an EARLIER version of the ship script (8 cherry-picks).
The CURRENT ship script (modified 13:39:01, after retry #3 stopped) lists
9 cherry-picks including PR 59 — and references PR 60 as the 10th but does
not yet have a `git cherry-pick "$SHA_PR60"` line. The script is in
transition: header documents 10 PRs, fetch list includes 10 branches,
sanity loop iterates 10 SHAs, but the cherry-pick block has only 9.

---

## Brown gate validation check

**Brown gate status: NEVER EXECUTED in retry #3.**

The Brown gate runs in Phase 5 at line 367-372 of the ship script:
```
POKER_SOLVER_REQUIRE_BROWN_PARITY=1 \
    pytest tests/test_v1_5_brown_apples_to_apples.py -v --timeout=1800 -ra
```

This is preceded by:
1. `cargo test --lib --release` (line 327) — KILLED HERE in retry #3
2. `maturin develop --release` (line 331)
3. `pytest tests/test_exploit_diff.py` (line 334)
4. Brown binary presence check (lines 345-365)
5. Brown gate itself (line 367-372)

Retry #3 was killed mid-step 1 (`cargo test --lib --release`), so steps
2-5 never ran. Brown gate did NOT silent-skip (it didn't run at all). It
also did NOT validate (it didn't run at all).

### Status of the silent-skip fix (PR 60)

The silent-skip fix is implemented and EXISTS on:
- branch `pr-60-brown-silent-skip-fix` (commit `bde2e12a`)
- origin remote (`remotes/origin/pr-60-brown-silent-skip-fix`)
- local working tree as uncommitted changes to
  `tests/test_v1_5_brown_apples_to_apples.py` (the same diff as the
  committed PR 60)

The fix adds:
- `_REQUIRE_BROWN_PARITY = bool(int(os.environ.get("POKER_SOLVER_REQUIRE_BROWN_PARITY", "0") or "0"))`
- `_skip_or_fail()` helper that promotes skips to `pytest.fail()` when env=1
- Routes both `_require_preconditions()` and `_require_brown_binary()`
  through the helper

The ship script (lines 345-372) was also updated with:
- Binary-link guard: copies/links Brown's `river_solver_optimized` into
  the worktree from the shared tree before running the gate, hard-failing
  if the binary cannot be obtained
- Sets `POKER_SOLVER_REQUIRE_BROWN_PARITY=1` when invoking the gate

Both pieces of the fix were authored 2026-05-25 at 13:38 (PR 60 commit
time) and 13:39 (ship script mtime) — *after* retry #3 stopped at 13:31.
So retry #3 ran without either layer of the safety net.

If retry #3 had reached Phase 5 step 5 (Brown gate), it would have:
- Used the in-worktree test file (no `_skip_or_fail` helper)
- Inherited no `POKER_SOLVER_REQUIRE_BROWN_PARITY` env var (script didn't set it yet at retry #3 time)
- Found no Brown binary in worktree (no binary-link guard yet)
- Silent-skipped with `2 skipped in 0.03s` — same as retry #2

So retry #3 would have repeated the silent-skip pathology had it not been
killed externally first.

---

## Final state

| Item | State |
|---|---|
| `v1.7.1` tag | Does not exist (local or origin) |
| `v1.7.1` release | Does not exist on GitHub |
| `origin/main` HEAD | `60a98189` (unchanged from before retry #3) |
| Local `main` | At `ca8c7af` (10 commits behind origin/main, fast-forwardable) |
| Worktree `/tmp/ship-v1.7.1-30263` | Exists with cherry-picks applied, version bumped, CHANGELOG updated, but not committed |
| Logs | `/tmp/v1.7.1_ship_retry.log` (retry #1, halted on memory_profiler golden), `/tmp/v1.7.1_ship_retry3.log` (retry #3, killed in cargo test) |
| PR 60 (silent-skip fix) | Authored 13:38, branch + origin pushed, NOT yet cherry-picked into bundle |
| PR 59 (golden refresh) | In bundle per current script header but cherry-pick block has it |
| Ship script | In transitional state: header says 10 PRs, fetch list has 10, cherry-pick block has 9 (no PR 60 cherry-pick line) |
| Uncommitted shared-tree changes | `USAGE.md`, `tests/test_v1_5_brown_apples_to_apples.py` (the silent-skip fix, equivalent to PR 60 contents) |

---

## Recommended next step

**Launch retry #4 once these prereqs are satisfied:**

1. **Add PR 60 cherry-pick line to ship script** (between PR 53c and the
   "All N cherry-picks landed" summary). Current script defines `SHA_PR60`
   and includes the branch in the fetch list and sanity loop, but the
   actual `git cherry-pick "$SHA_PR60"` command is missing from the
   cherry-pick block. Update the summary line from "All 9 cherry-picks
   landed" to "All 10 cherry-picks landed".

2. **Verify uncommitted shared-tree changes are intentional** — the
   uncommitted diff to `tests/test_v1_5_brown_apples_to_apples.py` is the
   same content as the PR 60 commit. Once PR 60 is cherry-picked into the
   worktree, the in-worktree test file will have the fix. The
   shared-tree uncommitted edit is redundant once the bundle includes
   PR 60.

3. **Diagnose retry #3 kill cause** — no evidence in the log of why it
   stopped. Possible causes: session/terminal interrupt, OOM, manual
   Ctrl-C, parent process termination, system event. If autonomous mode
   has timing limits, the cargo test taking longer than expected (despite
   17.47s prior) might point to a different cargo step on this branch
   being slower — but the log shows it was still streaming `ok`s, so
   external interrupt is the likeliest cause.

4. **Run retry #4 with extended budget** and verify the smoke matrix log
   shows Brown gate output containing `PASSED` (not `SKIPPED`) with
   per-spot assertion details.

**Block on retry #4 launch until step 1 is done.** Without the PR 60
cherry-pick, retry #4 would repeat retry #2's silent-skip pathology if it
reaches Phase 5 step 5.

---

## Per-task checkpoint summary

| Phase | Question | Answer |
|---|---|---|
| 1 | Did retry #3 succeed? | No |
| 1 | Did it halt? | No (no halt marker in log) |
| 1 | Did it kill? | Yes (terminated externally during cargo test) |
| 2 | Brown gate "SKIPPED" observed? | No (gate never ran) |
| 2 | Brown gate "PASSED" with non-zero duration? | No (gate never ran) |
| 2 | Brown gate assertion output present? | No (gate never ran) |
| 2 | Did silent-skip fix propagate? | N/A — fix did not exist yet at retry #3 time |
| 3 | Did v1.7.1 ship? | No |
| 3 | Audit release contents? | N/A — no release |
| 4 | Next step? | Add PR 60 cherry-pick to script, launch retry #4 |
