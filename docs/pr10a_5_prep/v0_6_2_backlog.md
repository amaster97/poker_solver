# v0.6.2 backlog — PR 10a.5 deferred should-fix items

PR 10a.5 (v0.6.1) landed the conformance fix for the pushfold f-string toast (item 1) and deferred the remaining two should-fix items from the audit because each carries a real design surface. This file expands both items with the design analysis needed to scope and ship a v0.6.2 polish PR.

## v0.6.2 scope

**Deliverables:**
1. Bound the OOM-recovery prune so `bet_sizes_checked` cannot go empty (item 2).
2. Resolve the `SolveRunner.compute_eta()` dead-code surface (item 3) — delete or wire.

**Ship order:** item 2 first (isolated, no spec touch); then item 3 (touches state.py). One PR (`pr-10a.6-polish`), one commit per item for clean revert.

**Tests:** `test_reduce_bet_sizes_keeps_minimum_one_size` — fixture `bet_sizes_checked=(1.5, 2.0)`, invoke `_reduce_bet_sizes`, assert `len >= 1` and fallback toast fired. Item 3 test depends on chosen option.

---

## Item 2 — Unbounded `bet_sizes_checked` pruning

**Location:** `ui/views/run_panel.py:538-548` (inside the OOM branch of `_show_error`).

```python
def _reduce_bet_sizes(_e: Any = None) -> None:
    spot = state.current_spot
    spot.bet_sizes_checked = tuple(
        bs for bs in spot.bet_sizes_checked if bs <= 1.0
    )
    ui.notify("Bet sizes reduced to <=100% pot; rerun solve.", ...)
```

**Bug:** The filter keeps only `bs <= 1.0`. With the default `(0.33, 0.75, 1.0)` (`ui/state.py:357`) the result always retains at least one size. But for a user with a custom config like `(1.5, 2.0)` — perfectly legal per `SpotConfig` — pruning produces `()`. Downstream `HUNLConfig(bet_size_fractions=())` (`ui/state.py:422`) then degenerates: the solver sees no aggressive lines, silently abstracting the spot into check/call-only and producing strategies that look "fine" but are unsolvable as configured.

**Design options:**

- **2A. Floor at 1 size + fallback toast.** If post-filter result is empty, restore the smallest original size (or `(1.0,)`); fire a second toast: "All sizes >100% pot — kept the smallest at <X>; try smaller tree depth instead."
- **2B. Refuse to prune on custom configs.** If `spot.bet_sizes_checked != DEFAULT_BET_SIZES`, abort the action and notify the user that custom configs require manual reduction.
- **2C. Prune to empty, then re-populate with `(1.0,)`.** Always end with `(1.0,)` regardless of input. Simpler than 2A but discards user intent more aggressively.

**Recommended: 2A.** Defense: the OOM button is most valuable when the user has opted into expensive sizes — exactly the population most likely to OOM. Killing the recovery surface in that case (2B) defeats the button's purpose; silently rewriting to `(1.0,)` (2C) discards user intent. 2A preserves the action, informs via a second toast, and mirrors the "second-toast" pattern already in use.

**Estimated effort:** ~10 LOC in `_reduce_bet_sizes`; ~15 LOC test. No UI surface change beyond the new toast.

**Open question:** floor at `(1.0,)` or `min(original_sizes)` when all are > 1.0? Lean `min(original_sizes)` — more honest to user intent.

---

## Item 3 — Dead-code `SolveRunner.compute_eta()`

**Two ETA paths coexist:**
- `SolveRunner.compute_eta()` in `ui/state.py:603-635` — linear iters/sec extrapolation using `target_iterations` and `start_time_monotonic`/`current_time_monotonic`. Only callable in tests; `_worker()` never sets the three required attributes, and `start()` doesn't capture `target_iterations`. So in production it returns `None` on the `target is None` branch (`state.py:629-631`).
- `_compute_eta(history, wall)` in `ui/views/run_panel.py:479-513` — log-space slope fit over `expl_history`, projecting iters-to-target of 0.5 mBB/pot. Live; called from `refresh_progress` at `run_panel.py:305` when `wall > 30 s and len(expl_history) >= 3`.

**Feature comparison:** the two functions compute fundamentally different ETAs. State's `compute_eta` gives "seconds to hit `target_iterations`" (iter-count target); run_panel's `_compute_eta` gives "seconds to hit `0.5 mBB/pot` exploitability" (quality target, the metric specified in `pr10a_spec.md` §6 edge #1). The state-side method also requires `target_iterations` to be set, which the worker today does not propagate from the dispatch config. The run_panel-side function works purely from `expl_history`, which is already populated by `_worker`.

**Design options:**

- **3A. Delete `SolveRunner.compute_eta()` + the three `start_time_monotonic` / `current_time_monotonic` / `target_iterations` attributes; refactor smoke 20 to test `_compute_eta` from `run_panel` directly.** Cost: ~30 LOC removed + 1 test rewritten (~15 LOC). Cleanest. Surfaces the actual production ETA path.
- **3B. Wire up the state-side path: have `start()` capture `target_iterations`, have `_worker` tick `current_time_monotonic`, then replace `_compute_eta` calls with `runner.compute_eta()` in `run_panel:305`.** Cost: ~15 LOC in `state.py` + 3 LOC in `run_panel.py`, but semantic change (iter-target vs expl-target ETA) and requires deciding which ETA we actually want to show. Adds threading exposure (worker writes `current_time_monotonic`; UI reads).

**Recommended: 3A.** Defense: the spec calls for exploitability-target ETA, which is what `run_panel._compute_eta` already does. The state-side `compute_eta` is an iter-target ETA — a different feature, never wired, and arguably the wrong metric. Deleting it removes 30 LOC of dead code, removes the smoke 20 fast-path that misleads readers, and avoids touching `_worker` (which PR 10a.5 deliberately kept byte-unchanged). The smoke 20 rewrite synthesizes `expl_history` and a wall > 30 — direct, no UI loop.

**Estimated effort:** ~30 LOC removed (`state.py` method + three attribute inits + docstring); ~15 LOC test rewrite (`tests/test_ui_smoke.py:706-724`); zero UI surface change.

**Open question:** any other caller depend on the three attributes? `grep` across `ui/` + `tests/` shows only smoke 20. Safe to remove.
