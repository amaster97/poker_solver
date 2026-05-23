# Zombie Pytest Cleanup — 2026-05-22 03:48 EDT

## Active Processes Snapshot

Time of check: `Fri May 22 03:48:09 EDT 2026`

### Pytest processes (3 running)

| PID  | PPID  | Elapsed | %CPU  | RSS    | Command (abridged)                                                 |
|------|-------|---------|-------|--------|--------------------------------------------------------------------|
| 6528 | 6525  | 07:50   | 100.0 | 20352  | `.venv/bin/pytest -m "not slow and not very_slow" --tb=line` (\| tail -30) |
| 7469 | 7467  | 04:58   |  99.2 | 30172  | `pyenv 3.13-dev pytest -x --tb=line -m "not slow and not very_slow" -k "not leduc_diff"` (\| tail -30, prefixed with `time`) |
| 8005 | 8002  | 02:12   |  99.4 | 19696  | `.venv/bin/pytest -m "not slow and not very_slow" --tb=line` (\| tail -40) |

All three share grand-parent PID `12250` (the Claude harness shell), spawned via `zsh -c '...pytest...'` wrappers (PIDs 6525, 7467, 8002 respectively).

### Cargo processes

None. (`ps aux | grep -E "cargo (test|build)"` returned empty.)

## Zombie Analysis

Threshold per spec: pytest > 15 min is "likely a zombie from a terminated agent."

- PID 6528: 7m 50s — under threshold
- PID 7469: 4m 58s — under threshold
- PID 8005: 2m 12s — under threshold

All three pytests are at ~100% CPU (`R` state, not `S`/sleeping), so they are actively executing test code, not stuck/blocked. None has crossed the 15-minute heuristic.

### Distinguishing the legitimate V3 commit agent

The user flagged PR 6 commit V3 agent (`a5bd276675f61a1f7`) as a legitimate in-flight pytest invocation. Command-arg fingerprinting:

- PID 7469 is distinctive: uses `pyenv` interpreter (not `.venv`), passes `-x` (stop-on-first-fail), filters `-k "not leduc_diff"`, and is wrapped with `time`. Looks like a deliberately-shaped commit-gate run.
- PIDs 6528 and 8005 are near-duplicate generic full-suite runs differing only in `tail -30` vs `tail -40`, both using `.venv`.

Without explicit confirmation from the V3 agent's transcript, any of the three *could* be its run. Given the constraint "don't kill the commit V3 agent's pytest," and that none of the three exceeds the 15-min zombie threshold, the conservative call is **no kills.**

## Cleanup Actions Taken

None. All three pytests are below the documented zombie threshold and are CPU-active (not hung). Killing any could:

- Abort the V3 commit agent (forbidden by constraint).
- Abort another agent that is still legitimately running (no evidence any was terminated).

## Post-cleanup Verification

N/A — no kill issued, so the snapshot above stands.

## Recommendation for orchestrator

- Re-check in ~10 minutes. If PID 6528 crosses 15:00 elapsed and is still `R` at 100% CPU on the same test, it may be stuck and a single `kill 6528` (SIGTERM) would be appropriate.
- If a new pytest spawns while 6528/7469 still run, the in-flight count will hit 4 — at that point the floor for `pkill -9 -f "bin/pytest"` becomes more defensible, but only after first confirming the V3 agent has finished or naming the V3 PID explicitly.
- Suggest the V3 commit agent log its pytest PID to a known file (e.g. `/tmp/v3_pytest.pid`) so future cleanup passes can target exclusions precisely.
