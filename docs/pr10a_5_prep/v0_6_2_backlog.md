# v0.6.2 backlog — PR 10a.5 deferred should-fixes

Two audit-flagged should-fix items were deferred from PR 10a.5 (v0.6.1) because each carries a real design surface that warrants its own scoped PR with proper tests. v0.6.1 shipped item 1 (the f-string fix); items 2 and 3 below remain.

Status: not started. Each is a self-contained polish item — likely a single fan-out PR (e.g., PR 10a.6) covering both, or two micro-PRs if the design discussion below pulls them apart.

---

## Item 2 — `run_panel._reduce_bet_sizes` unbounded prune

**Location:** `ui/views/run_panel.py:540-542`

```python
def _reduce_bet_sizes(_e: Any = None) -> None:
    spot = state.current_spot
    spot.bet_sizes_checked = tuple(
        bs for bs in spot.bet_sizes_checked if bs <= 1.0
    )
    ui.notify(
        "Bet sizes reduced to <=100% pot; rerun solve.",
        type="info",
        ...
    )
```

**Problem:** The filter keeps only `bs <= 1.0`. If the user has configured a spot where every checked bet size is `> 1.0` (e.g., a custom abstraction with only over-pot sizes for a specific exploit study), the result is an empty tuple. The downstream solver will then either crash or silently behave as if there are no aggressive lines — neither acceptable from a UX surface advertised as a recovery action ("Reduce bet sizes" button surfaced on OOM error).

**Safe-by-default:** The shipping abstraction (PR 4) includes 0.5, 0.75, 1.0 in the default tuple, so the empty-result branch is unreachable in defaults. The risk is real only for the custom-config-with-only-`>1.0`-sizes user.

**Design questions for v0.6.2 PR:**

1. **Clamp policy.** Three viable choices:
   - **(a)** Default-clamp: if pruned result is empty, fall back to `(1.0,)` (the smallest bet size we want a solver to ever see). Simple, safe; user may feel surprised.
   - **(b)** Default-clamp + toast: same as (a) but with a second `ui.notify` explaining the floor was applied. Explicit, slightly more code.
   - **(c)** Block-and-prompt: if pruned result is empty, abort the prune action and notify "All your bet sizes are >1.0; reduce-bet-sizes cannot help here." Honest, but the OOM recovery surface goes dead exactly when most needed — a bad outcome.
   Recommendation: **(b)**, since the OOM-recovery surface is the failure mode this button exists to handle.

2. **Test surface.** Smoke 18 (X5) only checks marker presence on the button — it does not exercise the click handler. A new unit test in `tests/test_ui_smoke.py` (or `tests/ui/test_run_panel_recovery.py`) should construct a spot with `bet_sizes_checked = (1.5, 2.0)`, invoke `_reduce_bet_sizes`, and assert `spot.bet_sizes_checked == (1.0,)` plus toast emission.

3. **Spec touch.** None — purely UI-surface behavior; solver semantics unchanged. No spec-freeze concern.

**Estimated effort:** ~5–10 min code + ~10 min test + ~5 min PR overhead. Single agent.

---

## Item 3 — `SolveRunner.compute_eta()` dead-code path

**Location:** `ui/state.py:603-635`

```python
def compute_eta(self) -> float | None:
    """Return the linear-extrapolation ETA in seconds, or None if N/A."""
    iters = self.iteration
    if iters <= 0:
        return None
    start = getattr(self, "start_time_monotonic", None)
    now = getattr(self, "current_time_monotonic", None)
    if start is not None and now is not None:
        elapsed = float(now) - float(start)
    else:
        elapsed = time.time() - self.started_at if self.started_at else 0.0
    ...
    target = getattr(self, "target_iterations", None)
    if target is None or target <= iters:
        return None
    rate = iters / elapsed
    if rate <= 0:
        return None
    return (target - iters) / rate
```

**Problem:** `compute_eta()` exists and is unit-tested (smoke 20 (X7) sets `start_time_monotonic`, `current_time_monotonic`, `target_iterations` directly and asserts the return value), but in production the `_worker()` method never assigns `start_time_monotonic`, `current_time_monotonic`, or `target_iterations`. So in real solves the method falls through to the `time.time() - started_at` branch but then always returns `None` because `target_iterations` is unset. The progress-eta UI element (smoke 19) shows the marker but never updates with a real ETA.

This is dead code in prod: the surface advertised by smoke 20 is provably real only inside the test fixture.

**Design questions for v0.6.2 PR:**

1. **Rip vs wire.** Two paths:
   - **Rip:** delete `compute_eta()`, delete `start_time_monotonic`/`current_time_monotonic`/`target_iterations` attributes, delete the progress-eta UI element. Breaks smoke 20 (deletion) and smoke 19 (marker presence) — both would need to be updated or removed. Honest minimization but discards the UX feature the PR 10a spec §6 edge #1 explicitly called for ("UI surfaces an ETA after 30s of forward progress so the user can decide whether to stop").
   - **Wire:** modify `start()` to capture `target_iterations` from the dispatch config and `start_time_monotonic = time.monotonic()`; modify `_worker()` to tick `current_time_monotonic = time.monotonic()` on each progress callback; modify `_update_progress` in `run_panel.py` to call `runner.compute_eta()` and render the result.
   Recommendation: **Wire**, since the PR 10a spec calls for this. But the wiring touches the production ETA path — own audit warranted, and probably its own small test that exercises `start() → _worker tick → compute_eta()` end-to-end (not just direct attribute injection like smoke 20 does).

2. **Threading.** `start_time_monotonic` is set on the orchestrator thread once at `start()`; `current_time_monotonic` ticks from the worker thread. Reads happen from the UI thread. Plain attribute assignment is racy in principle but the GIL plus the fact that float writes are atomic in CPython makes this fine; just document the contract.

3. **Spec coverage gap.** The 30s-threshold logic (spec §6 edge #1) is a UI policy, not currently encoded anywhere. Either land it now in `_update_progress` (only show ETA when `elapsed >= 30`) or defer to a follow-up that owns the UX trigger.

4. **Cross-cut with other deferred work.** The pr10a_5 `commit_prep.md` lists two other spec-coverage gaps (blocker-overlay visual, pushfold-toast text) that share the same "ship the marker, defer the polish" pattern. They are natural neighbors to wire alongside item 3 in v0.6.2.

**Estimated effort:** ~20–40 min code + ~30 min test + ~15 min audit + ~10 min PR overhead. Single agent, but with a clear hand-off to an auditor since this touches the production ETA path.

---

## Recommended sequencing for v0.6.2

1. Open `pr-10a.6-polish` (or whatever the naming convention dictates) off `integration` HEAD (currently `c8aa2a2` post-Option-C-tracking commit).
2. Land item 2 first (smaller, fully isolated, no spec touch).
3. Land item 3 second, with the wire-up path; pull in the blocker-overlay visual + pushfold-toast text spec-coverage gaps from `commit_prep.md` as bonus scope if the agent has headroom.
4. Tag v0.6.2 from integration; same Option-C tracking semantics apply.

No blockers; can be picked up any time after PR 10a.5 lands (which it has, as of v0.6.1).
