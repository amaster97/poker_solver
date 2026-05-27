# Orphan Process Cleanup — 2026-05-26

**Triggered by:** pre-shutdown audit (PID 70947 hung on `pwd >| /tmp/...` redirect from 04:25).

**Constraints applied:**
- Only `zsh -c` wrapper stragglers were eligible for kill.
- Children-bearing wrappers were left alone if children showed CPU activity or were legitimate in-flight work.
- SIGTERM tried before SIGKILL (SIGKILL not needed — SIGTERM sufficed).

---

## Actions taken

### Killed

| PID   | Age before kill | Signal | Result | Notes |
|-------|------------------|--------|--------|-------|
| 70947 | ~6h (04:25 start; killed 10:18 local equiv) | SIGTERM | dead within 2s | Original target. Hung on `pwd >\| /tmp/claude-9a4e-cwd` after a `solve_hunl_preflop` heredoc. No live children. Clean kill, no SIGKILL needed. |

### Found but NOT killed (per constraints)

| PID   | Age   | Why not killed |
|-------|-------|----------------|
| 63132 | 37:18 | zsh wrapper for PR 93 A83 terminal-utility ablation. Has live child **63135 (python `scripts/a83_terminal_utility_ablation.py`) at 99.2% CPU**. Per constraint "no live children, no recent activity" — burning CPU = active. **However**, `/tmp/pr93_ablation.log` is **0 bytes after 37 min**, which is anomalous (script either pre-buffer-flush wedged in a tight loop or in a print-less compute phase). **Recommend user manually inspect / kill if ablation is no longer needed.** |
| 71795 | ~58s when first seen | zsh wrapper for an action-abstraction heredoc. Python parent process has already exited; only `cat` + `tail -30` children (PIDs 71822/71823) remain at 0% CPU — classic hung pipeline (same shape as PID 70947). **Under 1h threshold**, so left alone per strict rule. Likely to need cleanup at next sweep if still present. |
| 72022 | 00:41 when first seen | zsh wrapper running a `until ! ps -p 71688; do sleep 30; done` Monitor-style poller. Target PID 71688 is **a live, active pytest job** (`tests/test_v1_5_brown_apples_to_apples.py`, 2:32 CPU). This is in-flight work, not a straggler. |

### Verified absent (good)

- No `poker_solver.cli` orphans.
- No `a83_nash` processes (probes completed).
- No `gate4_200k` processes (Gate 4 was killed as expected).

---

## Post-cleanup state

`ps aux | grep -E "zsh -c.*poker|zsh -c.*pwd >\| /tmp/claude" | grep -v grep`:

```
ashen 63132 ... 0:00.01 /bin/zsh -c ... a83_terminal_utility_ablation.py ...  (HAS active python child 63135 @ 99.2% CPU)
ashen 71795 ... 0:00.01 /bin/zsh -c ... <heredoc>; tail -30 ...  (HAS hung cat+tail children 71822/71823 @ 0% CPU)
ashen 72022 ... 0:00.01 /bin/zsh -c ... until ! ps -p 71688 ...  (HAS active monitor child 72080; waiting on live pytest 71688)
```

`ps aux | grep -E "poker_solver.cli|a83_nash|gate4_200k" | grep -v grep`: **(empty — no stragglers)**

`ps -p 70947`: **dead** (exit code 1 from ps).

---

## Recommendations for next sweep

1. **PID 63132/63135 (A83 ablation)** — if no longer needed, kill 63132 then 63135. The 0-byte log + 99% CPU + 37+ min runtime fits the "likely stalled but burning CPU" pattern the user flagged. Strict rule kept it alive this pass, but user judgment supersedes.
2. **PID 71795** — re-check at next sweep; if etime > 1h (or anytime if user confirms it's the same hung pipeline pattern as 70947), kill the wrapper (children will die with it).
3. **PID 72022** — leave alone while pytest 71688 is alive. Poller will self-terminate when pytest exits.

---

**Cleanup result:** 1 orphan killed cleanly (SIGTERM, no SIGKILL needed). 2 wrappers flagged for next sweep but spared per strict constraints. 1 legitimate in-flight monitor poller (72022) confirmed not to be touched.
