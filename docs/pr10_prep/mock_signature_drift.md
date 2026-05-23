# PR 10a mock_solver signature drift — MUST-FIX audit finding

**Status:** open, blocking PR 10b's "one-line swap" claim
**Discovered:** 2026-05-22 audit pass
**Affects:** `pr10a_spec.md` §7.1, `pr10b_spec.md` swap procedure, `ui/state.py::SolveRunner._worker`
**Severity:** must-fix before PR 10b — the swap as-specified will not compile.

---

## 1. The three drift points

`ui/mock_solver.py::mock_solve` does **not** match
`poker_solver/hunl_solver.py::solve_hunl_postflop` despite §7.1's
"byte-identical first 8 parameters" claim. Three concrete drifts:

### 1.1 `abstraction` parameter — present in real, absent in mock

Real (`hunl_solver.py:85-95`):

```python
def solve_hunl_postflop(
    config: HUNLConfig,
    abstraction: AbstractionTables | None = None,    # POSITIONAL #2
    iterations: int = _DEFAULT_ITERATIONS,           # positional #3
    target_exploitability: float | None = None,      # positional #4
    memory_budget_gb: float = _DEFAULT_MEMORY_BUDGET_GB,  # positional #5
    *,
    log_every: int | None = None,
    seed: int | None = None,
    dcfr_kwargs: dict[str, Any] | None = None,
) -> HUNLSolveResult:
```

Mock (`mock_solver.py:334-347`):

```python
def mock_solve(
    config: HUNLConfig,
    iterations: int = 50_000,                        # positional #2 (real has abstraction here)
    *,
    log_every: int | None = None,
    memory_budget_gb: float = 14.0,
    target_exploitability: float | None = None,
    seed: int | None = None,
    dcfr_kwargs: dict[str, Any] | None = None,
    on_progress: Callable[...] | None = None,
    mock_latency_ms: int = 30_000,
    mock_failure_mode: str | None = None,
) -> HUNLSolveResult:
```

A caller passing `solve(config, 50_000)` positionally hits `iterations` on
the mock but `abstraction` on the real solver. **Latent bug** the moment the
swap lands.

### 1.2 `target_exploitability` / `memory_budget_gb` positional vs kwarg-only

Real solver: both are **positional** (parameters #4 and #5, before the `*`).
Mock: both are **kwarg-only** (after the `*`).

A caller passing `solve(config, abstraction, 50_000, 0.5, 14.0)` works on
the real solver but is a `TypeError: too many positional arguments` on the
mock — and vice versa for any kwarg-named call to the real solver that uses
positional ordering anywhere upstream.

### 1.3 `on_progress` — required by mock, absent from real

Real `solve_hunl_postflop` has **no** `on_progress` parameter. The mock
declares it as a kwarg and the UI worker (`ui/state.py:663-672`) invokes
the import-swap point with `on_progress=on_progress` baked in. After the
swap, the call site raises `TypeError: solve_hunl_postflop() got an
unexpected keyword argument 'on_progress'`.

This is the most user-visible drift: the live exploitability chart relies
entirely on the per-snapshot callback. Without it (or a replacement progress
plumbing), the chart goes dark during a 30-minute solve.

---

## 2. Three options

### Option A — Patch mock to match real signature; switch UI to poll-based progress

**What changes:**
- Drop `on_progress` from `mock_solve` signature; mock writes to a
  thread-safe shared progress buffer (e.g., a `threading.Lock`-guarded
  dict on the `SolveRunner` instance, or a module-level
  `_PROGRESS_QUEUE`).
- Reorder mock params to match real: `abstraction` slot inserted at
  position #2 (mock can accept-and-ignore it); `target_exploitability` /
  `memory_budget_gb` moved before the `*`.
- UI worker uses `ui.timer(0.1, refresh_progress)` to poll the shared
  buffer instead of the callback.

**Pros:**
- True one-line swap in PR 10b: `from poker_solver.hunl_solver import
  solve_hunl_postflop as _solve_postflop_impl`. The kwargs at the call
  site already match.
- No changes to `poker_solver/` engine surface — keeps PR 5's surface
  frozen (which the spec explicitly demands).
- Polling cadence is decoupled from solver implementation; the real
  solver doesn't need a callback hook at all (the worker can read
  `solver.iteration` and `solver.exploitability_history` directly).
- Matches NiceGUI's idiomatic pattern (`ui.timer` for live updates).

**Cons:**
- Mock needs a small refactor (`_stream_progress` writes to the
  buffer instead of calling the callback).
- UI worker grows a `progress_buffer` field and a polling timer.
- ~1-2 day net effort across mock + worker + spec edit.

### Option B — Add `on_progress` to `solve_hunl_postflop`

**What changes:**
- Touch `poker_solver/hunl_solver.py:85-95` to accept
  `on_progress: Callable[[int, float, MemoryReport], None] | None = None`.
- Plumb the callback into `_run_with_probe` so it fires per `log_every`
  chunk.
- PATCH version bump on `poker_solver` (PR 5 surface re-opens).

**Pros:**
- Mock signature stays as-is; spec §7.1 "first 8 params byte-identical"
  becomes literally true after the engine-side change.
- Live chart works identically before and after swap — no UI rewrite.

**Cons:**
- Reopens PR 5's locked surface, violating PLAN.md's "DCFRSolver remains
  unchanged" lock (technically `solve_hunl_postflop` is the orchestrator
  not DCFRSolver, but the spirit of the lock applies).
- Adds a callback contract to the real engine that no non-UI caller
  needs — pollutes the library surface for one UI consumer.
- Still leaves drifts 1.1 and 1.2 unaddressed (this option only fixes
  drift 1.3).
- Triggers a PATCH release of `poker-solver` just for the UI's benefit;
  CHANGELOG/release-notes churn.
- ~1 day for the engine change + tests + release prep.

### Option C — PR 10b ships an adapter shim instead of direct swap

**What changes:**
- `ui/state.py::SolveRunner._worker` no longer imports
  `solve_hunl_postflop` directly. Instead, it imports a new
  `ui/solver_adapter.py::solve_via_adapter(config, iterations, ...,
  on_progress=cb)` that internally calls `solve_hunl_postflop` and
  bridges the missing callback by sub-classing `DCFRSolver` or by
  running the solve in chunks and emitting `on_progress` between chunks.

**Pros:**
- No engine-side change; PR 5 surface stays frozen.
- Mock signature stays as-is.
- The adapter can encapsulate any future drift (PR 9 preflop solver, PR
  11 library mode, etc.) without bleeding into the engine.

**Cons:**
- Defeats the "byte-locked first 8 params → one-line import swap"
  marketing entirely. The pr10a_spec.md §7.1 claim becomes false.
- Adds a third file (`ui/solver_adapter.py`) the team has to maintain;
  every future signature change to the real solver requires a parallel
  adapter update.
- PR 10b grows from "1-line diff" to "~50-100 LOC adapter + tests".
- Chunked re-call pattern in the adapter duplicates `_run_with_probe`'s
  chunk loop — a code smell.
- ~2-3 day effort.

---

## 3. Recommendation: **Option A**

Reasoning:

1. **Honesty:** The "one-line swap" promise becomes literally true.
   Option B partially redeems it (drift 1.3 only); Option C explicitly
   abandons it.
2. **Engine surface stays frozen:** PLAN.md's "DCFRSolver remains
   unchanged" lock and PR 5's locked public surface both stay intact. No
   PATCH bump churn.
3. **Polling is the right pattern for NiceGUI:** the framework
   already wants you to use `ui.timer` for live updates; bolting a
   callback onto the engine is fighting the framework.
4. **The mock is the right place to change:** the mock is a temporary
   scaffold (per pr10a_spec.md §1: "PR 10a ships against scaffolds, PR
   10b swaps to real"). Bending the temporary scaffold to fit the
   permanent engine is correct directionality.
5. **Single PR closes all three drifts:** Options B and C each leave at
   least one drift open; Option A fixes 1.1, 1.2, and 1.3 in one go.
6. **Smallest blast radius:** ~80 LOC mock + worker edits, no engine
   changes, no release.

---

## 4. Patch sketch (Option A) — DO NOT APPLY YET

### 4.1 `ui/mock_solver.py` — signature change

```python
def mock_solve(
    config: HUNLConfig,
    abstraction: object | None = None,     # NEW: accept-and-ignore
    iterations: int = 50_000,
    target_exploitability: float | None = None,   # MOVED before *
    memory_budget_gb: float = 14.0,        # MOVED before *
    *,
    log_every: int | None = None,
    seed: int | None = None,
    dcfr_kwargs: dict[str, Any] | None = None,
    # ---- mock-specific knobs (kwarg-only) ----
    mock_latency_ms: int = 30_000,
    mock_failure_mode: str | None = None,
) -> HUNLSolveResult:
    del abstraction  # mock ignores; real PR 5 solver consumes it.
    # ... existing body, but remove on_progress=... plumbing ...
```

`_stream_progress` loses its `on_progress` parameter and writes to a new
module-level progress buffer instead:

```python
@dataclass
class _ProgressSnapshot:
    iteration: int
    exploitability: float
    partial_report: MemoryReport

_PROGRESS_LOCK: threading.Lock = threading.Lock()
_LATEST_PROGRESS: _ProgressSnapshot | None = None

def _publish_progress(iter_n: int, expl: float, report: MemoryReport) -> None:
    global _LATEST_PROGRESS
    with _PROGRESS_LOCK:
        _LATEST_PROGRESS = _ProgressSnapshot(iter_n, expl, report)

def read_latest_progress() -> _ProgressSnapshot | None:
    """UI-thread helper; non-blocking."""
    with _PROGRESS_LOCK:
        return _LATEST_PROGRESS
```

Drop `on_progress` from `__all__`. Add `read_latest_progress` to `__all__`.

### 4.2 `ui/state.py::SolveRunner._worker` — polling worker

Replace the `on_progress` closure (lines 632-654) with direct buffer
reads. The worker's call site simplifies:

```python
result = _solve_postflop_impl(
    config,
    None,                       # abstraction (mock ignores; real uses)
    iterations,
    target_exploitability,
    memory_budget_gb,
    log_every=log_every,
    seed=seed,
    dcfr_kwargs=dcfr_kwargs,
    **mock_kwargs,              # mock-only kwargs; dropped at swap
)
```

A separate UI-thread `ui.timer(0.1, ...)` callback (set up in
`run_panel.py` during render) polls `ui.mock_solver.read_latest_progress()`
and updates the chart + progress fields. The worker thread no longer needs
the lock-guarded `iteration` / `expl_history` fields for live updates
(though it still uses them for the final result handoff and `status`
field).

### 4.3 PR 10b swap (after Option A lands)

`ui/state.py:619-625` becomes:

```python
from poker_solver.hunl_solver import (
    solve_hunl_postflop as _solve_postflop_impl,
)
```

(plus `**mock_kwargs` line deleted from the call). The first 8 args at the
call site are positionally byte-identical to the real solver's signature.
The real solver doesn't read from `_LATEST_PROGRESS`, but the UI polling
timer keeps working because the worker still updates
`self.iteration` / `self.expl_history` from intermediate snapshots
(via a small wrapper around `solver.iteration` in the real-solver
path — see §4.4).

### 4.4 Caveat for real-solver progress (PR 10b)

The real `solve_hunl_postflop` runs `solver.solve(step)` in chunks
(`_run_with_probe`, line 369). Between chunks it appends to a local
`history` list but doesn't expose intermediate state to the caller.
**The real solver's progress is invisible from the worker thread.**

Three fixes to consider in PR 10b:
- **A1**: Spawn a watcher thread that polls `solver.iteration` on the
  shared `DCFRSolver` instance. Cheap; requires exposing `solver` on
  `SolveRunner`.
- **A2**: Run `solve_hunl_postflop` in a loop of `iterations / N`
  chunks from the worker (re-entering between chunks). Defeats the
  per-chunk memory check; not recommended.
- **A3**: Real solver grows a `progress_callback` parameter (regresses
  to Option B for PR 10b only).

A1 is preferred; the watcher pattern is small (~30 LOC) and stays inside
`ui/state.py`. The watcher reads `solver.iteration` and
`solver.average_strategy()` (cheap for small infoset counts) at the
poll cadence.

---

## 5. Spec edits required

After Option A lands, edit:

- `pr10a_spec.md` §7.1 — replace the mock signature stanza with the new
  one (drop `on_progress`, add `abstraction`, reorder positionals).
- `pr10a_spec.md` §7.2 (line 632) — the "Live expl chart" row's
  "Arg shape" column changes from `cb(iter, expl, partial_report)` to
  "UI timer polls `read_latest_progress()`".
- `pr10a_spec.md` lines 620-624 — rewrite the "Critical lock-in" para:
  no need for "PR 10b's one engine-side addition" hedge; signature is
  now byte-identical without engine changes.
- `pr10b_spec.md` swap procedure — confirm the one-line import diff;
  add the §4.4 watcher-thread addendum.
- `commit_message_draft_10a.md` — note "signature drift fix" as part of
  PR 10a's body if the patch lands as a follow-up commit on the same
  branch.

---

## 6. Effort estimate (Option A)

| Task | LOC | Effort |
|---|---|---|
| Mock signature reorder + `_stream_progress` rewrite | ~40 | 1 hr |
| Add `_PROGRESS_LOCK` / `_LATEST_PROGRESS` / `read_latest_progress` | ~25 | 0.5 hr |
| `SolveRunner._worker` polling refactor | ~30 | 1 hr |
| `run_panel.py` `ui.timer` setup for chart updates | ~15 | 0.5 hr |
| Tests: mock signature, polling buffer, pause/stop semantics | ~80 | 2 hr |
| Spec edits (§5 above) | ~20 lines doc | 0.5 hr |
| **Total** | **~210 LOC** | **~5-6 hr / 1 day** |

PR 10b's swap drops to a single import line + the §4.4 watcher addendum
(~30 LOC, 1-2 hr).

---

## 7. Open questions

- Is the polling buffer's "last snapshot wins" semantics acceptable, or
  do we need a full history queue? (Spec §7.2 only requires the latest
  point for the chart; a queue would be over-engineering.)
- Should `read_latest_progress` reset on a new solve, or hold the last
  value indefinitely? (Recommend: reset in `SolveRunner.start()` via a
  module-level `clear_progress()` helper.)
- Does the §4.4 watcher pattern need to land in PR 10a (so the buffer
  is symmetric across mock and real) or only in PR 10b? Recommend
  PR 10a for symmetry; the watcher is a no-op when the mock writes to
  the buffer directly.
