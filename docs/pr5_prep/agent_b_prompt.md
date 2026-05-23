# PR 5 Agent B — Memory profiler + budget enforcement

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 5 Agent B.**
**Your scope:** the per-street memory profiler that instruments `DCFRSolver` from outside (no modification to `dcfr.py`), computes a per-street byte breakdown grouping by street tag parsed from infoset keys (lossless AND bucketed formats per PR 4 §3.5), enforces a 14 GB hard budget abort path, and calibrates against `psutil` actual process RSS within 10%.
**Your contract:** ship `MemoryProbe` + `MemoryReport` + `StreetMemoryEntry` + `_parse_street_from_key` in `poker_solver/profiler/`; Agent A's `solve_hunl_postflop` constructs your `MemoryProbe` and reads `report.river_ratio` for the PR 4 revisit trigger; Agent C tests you from spec alone.
**Your success criteria:** ruff clean, black clean, `mypy --strict` clean on `profiler/`; `MemoryReport.river_ratio` is the PR 4 revisit trigger per PLAN.md; `psutil` RSS calibration check passes within 10%; OOM detected + reported via `MemoryError` carrying the partial report; ALL 138+ existing tests still pass.
**File ownership:** you own and may write ONLY `poker_solver/profiler/__init__.py` and `poker_solver/profiler/memory.py`. You may modify `pyproject.toml` to add `psutil>=5.9`. You may NOT touch `dcfr.py`, `hunl.py`, `hunl_solver.py`, `abstraction/`, or any test file.

---

## Strict file ownership

**You own (write + create freely):**
- `/Users/ashen/Desktop/poker_solver/poker_solver/profiler/__init__.py` (new file; exports the public surface)
- `/Users/ashen/Desktop/poker_solver/poker_solver/profiler/memory.py` (new file; implementation)

**You may surgically modify:**
- `/Users/ashen/Desktop/poker_solver/pyproject.toml` — add `psutil>=5.9` to runtime dependencies. If Agent A has also touched this file (additive edit), confirm the final state lists `psutil` exactly once and the dep is otherwise idempotent.

**You must NOT touch:**
- `poker_solver/dcfr.py` — spec §6 freezes this. The probe instruments from outside (introspects `solver.infosets`); it does NOT modify the DCFRSolver class.
- `poker_solver/hunl.py` — spec §6 freezes this for PR 5.
- `poker_solver/hunl_solver.py` — Agent A owns this entirely. You expose the public surface; Agent A imports it.
- `poker_solver/abstraction/*` — PR 4's territory. You read `AbstractionTables` to compute `abstraction_table_bytes` but do NOT modify the abstraction module.
- `poker_solver/solver.py`, `poker_solver/cli.py`, `poker_solver/__init__.py` — Agent A's surgical edits.
- Any test file (`tests/test_memory_profiler.py`, `tests/test_hunl_postflop_solve.py`, `tests/fixtures/hunl_solve_fixtures.py`) — Agent C owns these.

If you discover an awkward signature or a contract gap mid-implementation, **do not silently change the spec'd interface**. Stop and write a short note to the orchestrator describing the conflict; the orchestrator reconciles across agents.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/pr5_spec.md`. Internalize §3.5 (profiler design philosophy), §4 Stage B (instrumentation), §7 (full profiler design detail: 7.1 `MemoryProbe` interface, 7.2 dataclasses, 7.3 key parsing, 7.4 byte accounting, 7.5 abstraction-table accounting, 7.6 psutil calibration, 7.7 hard memory budget enforcement, 7.8 license-aware inspiration), §10 Agent B deliverables, §11 (critical correctness items #4, #5, #8, #9), §12 (risks).
2. **Spec consistency review (any cross-cutting amendments):** `/Users/ashen/Desktop/poker_solver/docs/spec_consistency_review.md`. Especially the PR 4 key-format consistency (lossless vs bucketed) and the I4 finding (10% calibration tolerance inherits to PR 9).
3. **The PLAN (locked decisions):** `/Users/ashen/Desktop/poker_solver/PLAN.md`. Especially §1 "Card abstraction" — the 256/128/64 default + the **PR 5 profiler is the empirical input for the PR 4 revisit**. The 14 GB hard ceiling is locked.
4. **The autonomous log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md`. Skim for PR 5 entries.
5. **Existing surfaces you introspect:**
   - `/Users/ashen/Desktop/poker_solver/poker_solver/dcfr.py` — read the `DCFRSolver` class and `InfosetData` dataclass. You'll walk `solver.infosets: dict[str, InfosetData]`. Don't modify; just understand the shape: `InfosetData` has `regret_sum: np.ndarray`, `strategy_sum: np.ndarray`, `num_actions: int`, `last_discount_iter: int`. The `regret_sum.nbytes = num_actions * 8` (float64).
   - `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` — read the `Street` IntEnum (PREFLOP=0, FLOP=1, TURN=2, RIVER=3, SHOWDOWN=4) and the infoset key format documented in §"Infoset key" (lossless: `f"{player_hole}|{board}|{street_token}|{betting_history}"` where street_token is `p`/`f`/`t`/`r`).
   - `/Users/ashen/Desktop/poker_solver/poker_solver/abstraction/buckets.py` — read `AbstractionTables` shape so you can compute `abstraction_table_bytes` per spec §7.5. Fields you sum: `flop_assignments.nbytes`, `turn_assignments.nbytes`, `river_assignments.nbytes`, `flop_board_index.nbytes`, `turn_board_index.nbytes`, `river_board_index.nbytes`, `sys.getsizeof(metadata)`. **PR 5 depends on PR 4's card abstraction being present at this path.**
6. **License-aware sourcing patterns:** see §"License-aware sourcing" below.
7. **Reference style — PR 4 Agent A prompt pre-draft:** `/Users/ashen/Desktop/poker_solver/docs/pr4_prep/agent_a_prompt.md`. Same shape and tone.

## Default decisions LOCKED (do not deviate)

These defaults are from PR 5 spec §14 + PLAN.md. The user has authorized autonomous mode; these defaults are LOCKED unless the user redirects before launch:

1. **Memory budget hard ceiling: 14 GB** (PLAN.md §1 "Card abstraction" — the 14 GB upper bound for 100 BB tree-builder memory). Your `MemoryReport.total_gb` (or `grand_total_bytes`) is what Agent A compares against this budget. You don't enforce; you report.
2. **psutil calibration tolerance: 10%** (spec §7.6). Your `MemoryReport.rss_calibration_error` is the relative error between (`grand_total - baseline`) and (`rss - baseline`). Agent C asserts `< 0.10`.
3. **Snapshot mechanics:** caller-driven (spec §14 #10). `MemoryProbe.snapshot()` walks `solver.infosets` and updates `_latest_snapshot`. No built-in throttling.
4. **Key parsing per spec §7.3:** Two formats:
   - **Lossless (PR 3):** `f"{player_hole}|{board}|{street_token}|{betting_history}"` — street token `p`/`f`/`t`/`r` at index 2 (after split on `|`).
   - **Bucketed (PR 4):** `f"b{bucket_id}|{street_token}|{betting_history}"` — first token starts with `b`; street token at index 1.
   - Unknown formats: log a warning + lump into an "unknown" bucket; never crash.
5. **Byte accounting per spec §7.4:** `regret_bytes = info.regret_sum.nbytes`, `strategy_bytes = info.strategy_sum.nbytes`, `other_bytes = sys.getsizeof(info) + len(key.encode("utf-8"))`. Dict overhead bundled in `other_overhead_bytes` via `sum(other_bytes) * 0.5` heuristic (rough; `psutil` calibration is ground truth).
6. **`psutil>=5.9` as runtime dep** (spec §6 + spec §14 default — MIT, cross-platform, small). You add this to `pyproject.toml`.
7. **No DCFR modification** (spec §6, spec §10 Agent B "Does NOT touch dcfr.py"). The probe is purely external instrumentation. If you find yourself wanting to add a hook to `dcfr.py`, stop and re-read the spec — you do NOT modify it.
8. **MemoryReport is JSON-serializable** (spec §13 "PR 5's `MemoryReport` is JSON-serializable"). Use `@dataclass(frozen=True)` with primitive fields (int/float/bool/str/tuple). No NumPy arrays inside the report. (PR 10 will JSON-serialize this for the GUI.)
9. **Frozen dataclasses for `MemoryReport` and `StreetMemoryEntry`** (spec §7.2). They're effectively immutable value objects.
10. **`__init__.py` is minimal:** re-exports `MemoryProbe`, `MemoryReport`, `StreetMemoryEntry`. Maybe also `_parse_street_from_key` (the parsing helper) so Agent C can test it directly.

## Public API contract (signatures Agent A + Agent C depend on)

Export the following from `poker_solver/profiler/`. **Signature drift breaks Agent A's `solve_hunl_postflop` and Agent C's tests.** Type hints required (mypy --strict).

### `poker_solver/profiler/__init__.py`

```python
from poker_solver.profiler.memory import (
    MemoryProbe,
    MemoryReport,
    StreetMemoryEntry,
    _parse_street_from_key,  # re-exported for test access; module-private name is OK
)

__all__ = [
    "MemoryProbe",
    "MemoryReport",
    "StreetMemoryEntry",
    "_parse_street_from_key",
]
```

### `poker_solver/profiler/memory.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from poker_solver.abstraction.buckets import AbstractionTables  # PR 4
from poker_solver.dcfr import DCFRSolver                        # read-only introspect
from poker_solver.hunl import Street                            # IntEnum


@dataclass(frozen=True)
class StreetMemoryEntry:
    """Per-street row in the MemoryReport."""
    street: Street
    infoset_count: int
    regret_bytes: int
    strategy_bytes: int
    other_bytes: int
    total_bytes: int
    mean_actions_per_infoset: float
    max_actions_per_infoset: int


@dataclass(frozen=True)
class MemoryReport:
    """Per-street memory breakdown + total + psutil RSS calibration.

    JSON-serializable: all fields are primitive (int / float / bool / str /
    tuple of frozen dataclasses). PR 10 will serialize this for the GUI.

    The cross-agent contract surface (from the orchestrator brief):
        flop_gb, turn_gb, river_gb, total_gb, process_rss_gb, river_ratio
    These are derived properties / convenience aliases over the spec §7.2
    canonical fields (per_street, grand_total_bytes, rss_observed_bytes).
    """
    # Canonical fields per spec §7.2
    per_street: tuple[StreetMemoryEntry, ...]
    preflop_lossless_entry: Optional[StreetMemoryEntry]
    abstraction_table_bytes: int
    solver_arrays_total_bytes: int
    other_overhead_bytes: int
    grand_total_bytes: int
    rss_observed_bytes: int
    rss_baseline_bytes: int
    wallclock_per_iter_sec: Optional[float]
    iterations_at_snapshot: int

    # Cross-agent contract convenience fields (in GB)
    @property
    def flop_gb(self) -> float:
        return self._bytes_for(Street.FLOP) / 1024**3

    @property
    def turn_gb(self) -> float:
        return self._bytes_for(Street.TURN) / 1024**3

    @property
    def river_gb(self) -> float:
        return self._bytes_for(Street.RIVER) / 1024**3

    @property
    def total_gb(self) -> float:
        """Grand total (solver + abstraction + overhead) in GB."""
        return self.grand_total_bytes / 1024**3

    @property
    def process_rss_gb(self) -> float:
        """psutil RSS at snapshot time, in GB."""
        return self.rss_observed_bytes / 1024**3

    @property
    def river_ratio(self) -> float:
        """River layer's share of total SOLVER arrays.

        The PR 4 revisit trigger per PLAN.md §1 "Card abstraction":
        - < 30% → PR 4's revisit shrinks river bucket count
        - 30-50% → abstraction well-balanced
        - > 50% → consider lossless river

        Returns 0.0 if solver_arrays_total_bytes == 0.
        """
        if self.solver_arrays_total_bytes == 0:
            return 0.0
        return self._bytes_for(Street.RIVER) / self.solver_arrays_total_bytes

    @property
    def rss_calibration_error(self) -> float:
        """Relative error: (predicted_growth - actual_growth) / actual_growth."""
        actual = self.rss_observed_bytes - self.rss_baseline_bytes
        predicted = self.solver_arrays_total_bytes + self.other_overhead_bytes
        if actual <= 0:
            return 0.0  # baseline >= observed; can happen on cold start
        return abs(predicted - actual) / actual

    def _bytes_for(self, street: Street) -> int:
        """Internal: bytes from per_street entries for the given street."""
        for entry in self.per_street:
            if entry.street == street:
                return entry.total_bytes
        return 0


class MemoryProbe:
    """Instruments a DCFRSolver from outside. No modification to dcfr.py.

    Walks solver.infosets, groups by street tag parsed from the infoset key,
    computes byte totals, and snapshots a MemoryReport. Also captures
    psutil RSS for the calibration check (spec §7.6).
    """

    def __init__(
        self,
        solver: DCFRSolver,
        *,
        include_abstraction: Optional[AbstractionTables] = None,
    ) -> None:
        """Capture the baseline RSS at construction time.

        Args:
            solver: the DCFRSolver to instrument. Read-only access to
                solver.infosets.
            include_abstraction: optional PR 4 AbstractionTables to include
                in grand_total_bytes accounting (spec §7.5).
        """
        ...

    def snapshot(self) -> MemoryReport:
        """Walk solver.infosets, group by street, compute byte totals.

        Side effect: stores the result in self._latest_snapshot.

        Returns a fully-populated MemoryReport. For an empty solver
        (no iterations run yet), per_street is empty tuple and
        solver_arrays_total_bytes is 0.
        """
        ...

    def measure_per_street(self, dcfr_solver: DCFRSolver) -> MemoryReport:
        """Alias for snapshot() that accepts the solver explicitly.

        Cross-agent contract from the orchestrator brief. Internally
        equivalent to snapshot() when dcfr_solver is self.solver. If a
        different solver is passed, this is a no-op for that solver; the
        probe still walks self.solver.infosets. (Document this clearly.)
        """
        ...

    @property
    def latest(self) -> MemoryReport:
        """Most recent snapshot. RuntimeError if snapshot() has not been called."""
        ...


def _parse_street_from_key(infoset_key: str) -> Optional[Street]:
    """Extract the street token from a PR 3 (lossless) or PR 4 (bucketed) key.

    Lossless format: 'AhKh|7d2c9h|f|xx' → split on '|' → token at index 2 ('f') → FLOP.
    Bucketed format: 'b3|f|xx'          → split on '|' → first starts with 'b' →
                                          token at index 1 ('f') → FLOP.
    Unknown format: returns None (caller emits a warning and lumps to 'unknown').

    Returns:
        Street.PREFLOP / FLOP / TURN / RIVER for tokens 'p'/'f'/'t'/'r'.
        None if the key can't be parsed.
    """
    ...
```

**Internal helpers (you choose; document them):**
- `_compute_street_entries(infosets, abstraction_present) -> tuple[StreetMemoryEntry, ...]`
- `_compute_other_overhead(other_bytes_total: int) -> int`  (the `* 0.5` heuristic)
- `_abstraction_table_bytes(tables: AbstractionTables) -> int` per spec §7.5

## Cross-agent contracts (Agent A's surface; do NOT reach inside)

Treat these as opaque:

```python
# Agent A's solve_hunl_postflop calls you like this:
probe = MemoryProbe(solver, include_abstraction=abstraction)
# ... DCFR iterations run ...
report = probe.snapshot()
if report.total_gb > memory_budget_gb:
    raise MemoryError(..., report)
```

**Your responsibility:**
- `probe.snapshot()` must be callable between iteration chunks (so Agent A can enforce the budget mid-solve).
- `report.total_gb` must be a meaningful number after even ONE iteration (so the budget check works on the first chunk).
- `report.river_ratio` must be computable on any solve that touched river infosets.

## Critical correctness items

### 1. Memory profiler reports match psutil within 10%

The calibration assertion (spec §7.6 + §11 #4 + Agent C test 6 in §9.2):
```python
solver_growth_bytes = report.rss_observed_bytes - report.rss_baseline_bytes
predicted_growth_bytes = report.solver_arrays_total_bytes + report.other_overhead_bytes
assert abs(solver_growth_bytes - predicted_growth_bytes) / solver_growth_bytes < 0.10
```
If this fails, your byte accounting is wrong. Fix it.

Calibrate empirically: run a small solve (e.g., Fixture 2 with `(4, 2, 2)` synthetic abstraction, 200 iterations), check the calibration error. If it's > 10%, suspect:
- Forgetting to add abstraction table bytes (spec §7.5).
- The `* 0.5` dict overhead heuristic is wrong on your system; tune it (spec says "rough heuristic").
- Forgetting interpreter / GC overhead — these add up; the 10% tolerance is meant to cover this.

**Document in `__init__.py` or `memory.py` docstring:** the 10% tolerance is empirically calibrated; if a future Python release changes dict slack significantly, this assertion may need re-tuning.

### 2. `MemoryReport.river_ratio` is the PR 4 revisit trigger

This is the PRIMARY deliverable of PR 5 per PLAN.md §1 "Card abstraction". After every successful solve:
- `river_ratio` must be in `[0.0, 1.0]`.
- It must be non-zero whenever any river infoset was touched.
- It is `river_total_bytes / solver_arrays_total_bytes` (NOT `river / grand_total` — the user wants the ratio relative to SOLVER memory, since the abstraction table is a one-time fixed cost).

**Add a docstring on the property** explaining the three decision bands (< 30% / 30-50% / > 50%) so future readers (PR 4 revisit author) don't have to dig through PLAN.md.

### 3. Key parsing handles BOTH formats

Lossless (PR 3) AND bucketed (PR 4). Both are tested explicitly by Agent C (Tests 8 and 9 in §9.2):
- Lossless: `"AhKh|7d2c9h|f|xx"` → `Street.FLOP`
- Bucketed: `"b3|f|x"` → `Street.FLOP`

**Fragile-but-explicit fallback:** if a key matches NEITHER format, do NOT crash. Log a warning via `warnings.warn(..., RuntimeWarning)` once per session (use a class-level flag to suppress repeats) and lump the infoset into an "unknown" bucket (e.g., create a separate `unknown_street_entry: StreetMemoryEntry | None` field, OR drop it from per_street and add the bytes to `other_overhead_bytes`). Document the choice.

### 4. Empty-solver handling

`probe.snapshot()` on a freshly-constructed solver (no iterations run) must NOT crash:
- `per_street` returns empty tuple.
- `preflop_lossless_entry` is None.
- `solver_arrays_total_bytes` is 0.
- `grand_total_bytes` = `abstraction_table_bytes + other_overhead_bytes` (which may also be 0 if no abstraction passed).
- `river_ratio` returns 0.0 (the property's `if self.solver_arrays_total_bytes == 0: return 0.0` guard).

This is Agent C test 7 in §9.2.

### 5. `psutil.Process().memory_info().rss` baseline capture at construction

```python
def __init__(self, solver, *, include_abstraction=None):
    import psutil  # local import is fine; it's a deferred dep
    self._rss_baseline_bytes = psutil.Process().memory_info().rss
    ...
```
Capture at construction time so subsequent growth is measured from a fixed baseline. The baseline includes the interpreter, the already-loaded modules, the abstraction table (if pre-loaded), but NOT the solver's infoset dict (which is empty at construction).

### 6. Abstraction-table memory accounting per spec §7.5

```python
def _abstraction_table_bytes(tables: AbstractionTables) -> int:
    return (
        tables.flop_assignments.nbytes
        + tables.turn_assignments.nbytes
        + tables.river_assignments.nbytes
        + tables.flop_board_index.nbytes
        + tables.turn_board_index.nbytes
        + tables.river_board_index.nbytes
        + sys.getsizeof(tables.metadata)
    )
```
If PR 4 added a `source_path: Path | None` field (per consistency review B2 amendment), DON'T account for the path string's bytes (negligible; it's a few hundred bytes max). Focus on the NumPy arrays.

### 7. Failure mode = OOM detected via report.total_gb; Agent A raises

You do NOT raise `MemoryError`. Agent A's `solve_hunl_postflop` reads `report.total_gb` and raises if it exceeds the budget. Your job: produce an accurate report.

### 8. PR 1/2/3/4 tests still pass unchanged

138+ existing tests pass. Your work is purely additive (a new subpackage `profiler/`). Adding `psutil` to `pyproject.toml` should not affect existing tests; confirm via `pytest -x`.

### 9. Deterministic byte accounting

Same `solver.infosets` content → identical `MemoryReport` (modulo `wallclock_per_iter_sec` and `rss_observed_bytes` which depend on timing). The deterministic fields are: `per_street`, `preflop_lossless_entry`, `abstraction_table_bytes`, `solver_arrays_total_bytes`, `other_overhead_bytes`, `grand_total_bytes`, `iterations_at_snapshot`.

This is Agent C's reproducibility check (spec §11 #10).

### 10. PR 4 dependency

PR 5 depends on PR 4's card abstraction being present at `poker_solver/abstraction/buckets.py`. Confirm by reading the file. If it doesn't exist or `AbstractionTables` is missing fields you need, **stop and flag** — do not proceed with stub-based development.

## License-aware sourcing

**You may port architecturally (not code-copy) from MIT/Apache sources:**
- `references/code/slumbot2019/` (**MIT**) — no direct memory profiler, but Slumbot's tabular data structures (`int_set.cpp`, `dynamic_cbr.cpp`) inform what byte-accounting categories look like for tabular CFR.

**You may NOT copy from AGPL sources:**
- `references/code/postflop-solver/src/utility.rs:56` — **AGPL v3**. The `vec_memory_usage<T>(vec) = capacity * size_of::<T>()` pattern is architecturally identical to your `nbytes` accounting, but you derive the structure from first principles (sum every backing buffer's bytes). Spec §7.8 already documents this. **Do not copy code.** Add this attribution comment at the top of `memory.py`:
  ```python
  """Per-street memory profiler for DCFRSolver.

  Pattern (compute total memory by summing every backing buffer's bytes) is
  inspired architecturally by postflop-solver's memory_usage() (AGPL — read-only).
  No code copied; implementation derived from first principles per spec §7 of
  docs/pr5_prep/pr5_spec.md.
  """
  ```
- `references/code/postflop-solver/src/game/base.rs:259` — **AGPL v3**. The `memory_usage() -> (uncompressed, compressed)` pattern is similar but we don't adopt the compressed-vs-uncompressed dichotomy (compression is PR 8+).
- `references/code/TexasSolver/` — **AGPL v3**. Same rule.

**You may NOT extrapolate from training data.** If you "remember" a memory profiler implementation and want to use it, ground it in either the spec or the locally-cited MIT source above. When in doubt, prefer the spec's stated approach.

## Quality bar

- **ruff clean:** `ruff check poker_solver/profiler/` reports zero issues.
- **black clean:** `black --check poker_solver/profiler/` reports no changes needed.
- **mypy strict-clean on new code:** `mypy --strict poker_solver/profiler/` reports zero errors.
- **psutil>=5.9 added to `pyproject.toml`.** Confirm via `grep psutil pyproject.toml`. Cross-platform, MIT, ~1 MB.
- **All 138+ existing tests still pass.** Run `pytest -x` to confirm. Adding `psutil` as a dep + a new subpackage `profiler/` must not break anything.
- **Agent C's tests pass once your code + Agent A's code are both in.** The integration test is `pytest tests/test_memory_profiler.py -x`.
- **Code size budget: ~300–500 LOC** combined across the two files. Stay within budget; do not over-engineer.

## Reference-first rule

Before any technical claim, citation, or formula, check the local references. Never extrapolate from training data when a local authoritative source exists. The reference index is `/Users/ashen/Desktop/poker_solver/references/README.md` — skim it for "memory profiler", "psutil", "tabular CFR memory" entries.

If a fact is needed (e.g., "`numpy.ndarray.nbytes` returns `size * itemsize`"), it's documented in numpy's own docs (which are in your training data; cite the API name not training-data text). If you need to make a non-trivial claim about postflop-solver's memory model, do NOT copy — derive your own.

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Lint + format
ruff check poker_solver/profiler/
black --check poker_solver/profiler/

# 2. Type-check
mypy --strict poker_solver/profiler/

# 3. psutil dep confirmed
grep -A 0 'psutil' pyproject.toml

# 4. Smoke test: key parsing
python -c "
from poker_solver.hunl import Street
from poker_solver.profiler.memory import _parse_street_from_key
# Lossless format
assert _parse_street_from_key('AhKh|7d2c9h|f|xx') == Street.FLOP
assert _parse_street_from_key('AhKh|7d2c9hQs|t|xx|b300') == Street.TURN
assert _parse_street_from_key('AhKh||p|') == Street.PREFLOP
# Bucketed format (PR 4)
assert _parse_street_from_key('b3|f|x') == Street.FLOP
assert _parse_street_from_key('b127|r|c|x') == Street.RIVER
# Unknown format
assert _parse_street_from_key('not_a_real_key') is None
print('key parsing smoke OK')
"

# 5. Smoke test: empty solver
python -c "
from poker_solver.dcfr import DCFRSolver
from poker_solver.games import KuhnPoker
from poker_solver.profiler.memory import MemoryProbe
solver = DCFRSolver(KuhnPoker())
probe = MemoryProbe(solver)
report = probe.snapshot()
assert report.per_street == ()
assert report.solver_arrays_total_bytes == 0
assert report.river_ratio == 0.0
print(f'empty solver smoke OK: grand_total={report.grand_total_bytes} bytes')
"

# 6. Smoke test: psutil baseline captured
python -c "
import psutil
from poker_solver.dcfr import DCFRSolver
from poker_solver.games import KuhnPoker
from poker_solver.profiler.memory import MemoryProbe
solver = DCFRSolver(KuhnPoker())
probe = MemoryProbe(solver)
solver.solve(50)  # 50 iters, produces infosets
report = probe.snapshot()
print(f'baseline RSS: {report.rss_baseline_bytes / 1024**2:.1f} MB')
print(f'current RSS:  {report.rss_observed_bytes / 1024**2:.1f} MB')
print(f'predicted growth: {(report.solver_arrays_total_bytes + report.other_overhead_bytes) / 1024:.1f} KB')
# Kuhn is tiny so calibration may be loose — just confirm no crash
print(f'calibration error: {report.rss_calibration_error:.2%}')
print('psutil smoke OK')
"

# 7. Smoke test: river_ratio computable on a postflop solve
python -c "
from poker_solver.dcfr import DCFRSolver
from poker_solver.hunl import HUNLPoker, default_tiny_subgame
from poker_solver.profiler.memory import MemoryProbe
game = HUNLPoker(default_tiny_subgame())
solver = DCFRSolver(game)
probe = MemoryProbe(solver)
solver.solve(100)
report = probe.snapshot()
print(f'river_ratio: {report.river_ratio:.1%}')
assert 0.0 <= report.river_ratio <= 1.0
print('river_ratio smoke OK')
"

# 8. Full test suite must still pass (your work is additive)
pytest -x 2>&1 | tail -20
```

If any step fails, fix the issue before reporting done. If a smoke test reveals a spec ambiguity, **stop and flag it** — do not silently work around it.

## Report back format

When done, write a concise report (≤300 words) covering:

1. Files created/modified with line counts.
2. Any spec amendment you made or contract drift you flagged (and why).
3. Verification command output (paste tails).
4. Any open question you couldn't resolve from the spec / PLAN / autonomous log — flag for human review.
5. License attributions you added (the `memory.py` module docstring per §"License-aware sourcing").
6. The empirical psutil calibration error you observed on the smoke test (informs the 10% tolerance assertion in Agent C's test).
