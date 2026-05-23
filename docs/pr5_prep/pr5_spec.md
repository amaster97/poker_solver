# PR 5 spec — First HUNL postflop solve + per-street memory profiler (Python tier)

## 1. Goal

Ship the **first end-to-end HUNL postflop solve in the Python reference tier**, wiring PR 4's card-abstraction lookup into PR 3's tree builder and feeding the result to the existing Python DCFR (`poker_solver/dcfr.py`). PR 5 produces a `SolveResult`-shaped artifact containing an average strategy table, exploitability history, the underlying game value, **and a per-street memory breakdown** that calibrates the abstraction tiers PLAN.md commits to in §1 ("PR 5 ships a per-street memory profiler; revisit per-street based on data"). The profiler is load-bearing — its output is the input PR 4 will revisit, and it is the empirical sanity check on the 256/128/64 bucket counts the spec currently locks.

## 2. What PR 5 does NOT do

- **No Rust port.** The Rust HUNL solver lands in PR 6 (mechanical port of PR 5's Python reference). PR 5 touches zero Rust files.
- **No HUNL preflop solve.** Preflop is PR 9. PR 5 is *postflop-only*: it accepts only configs where `starting_street >= Street.FLOP` (with `initial_board` populated). A `--hunl-mode preflop` invocation raises `NotImplementedError` pointing at PR 9.
- **No per-spot library / cache-solved-spots-to-disk mode.** That's PR 11. PR 5 runs ad-hoc solves; results live in memory, optionally serialized via the existing `SolveResult` path.
- **No GUI integration.** GUI is PR 10. PR 5 surfaces results via the CLI only.
- **No multi-threading inside the CFR loop.** PR 8 owns parallelism (chance sampling + cache blocking). PR 5 runs the single-threaded Python DCFR exactly as PR 1/2 did, scaled to the larger HUNL tree.
- **No new DCFR variants.** Same Brown & Sandholm 2019 algorithm (α=1.5, β=0, γ=2.0), same `DCFRSolver` class from `poker_solver/dcfr.py`. We do **not** introduce CFR+, MCCFR, or external sampling here.
- **No abstraction quality benchmark vs PioSolver / noambrown.** Those parity tests are PR 7. PR 5 covers convergence + memory + invariants only.
- **No rake.** PR 3 asserted `rake_rate == 0.0` and `rake_cap == 0.0`; PR 5 keeps that assertion. PR 9 wires rake through.
- **No node locking / best-response variants beyond what `solver.py::exploitability` already provides.** Locked nodes is a Phase-4 feature.
- **No abstraction-builder code touched.** PR 4 owns `poker_solver/abstraction/`. PR 5 *consumes* `AbstractionTables` as a read-only artifact.
- **No re-bucketing on the fly.** If the user wants different bucket counts they re-run `poker-solver precompute-abstraction` from PR 4's CLI; PR 5 just loads whatever artifact is pointed at.
- **No bunching / blocker propagation.** postflop-solver has explicit blocker accounting (`bunching.rs`); PR 5 stays simple — chance node weights already encode blockers via the deck enumeration in `HUNLPoker.chance_outcomes`.

## 3. Conceptual architecture

### 3.1 Wiring diagram

```
 ┌────────────────────────┐         ┌──────────────────────────┐
 │  poker_solver/cli.py   │────────▶│  poker_solver/solver.py  │
 │  (extends: HUNL mode)  │         │  (routes HUNL postflop → │
 └────────────────────────┘         │   hunl_solver.solve_…)   │
                                    └────────────┬─────────────┘
                                                 │
                                                 ▼
                ┌────────────────────────────────────────────────┐
                │       poker_solver/hunl_solver.py (NEW)        │
                │  solve_hunl_postflop(config, abstraction, N)   │
                │                                                │
                │   1. validates config (postflop, board set)    │
                │   2. attaches abstraction to HUNLConfig        │
                │   3. instruments DCFRSolver via MemoryProbe    │
                │   4. runs DCFR for N iterations                │
                │   5. computes exploitability                   │
                │   6. produces SolveResult + MemoryReport       │
                └─────┬──────────────┬───────────────────────────┘
                      │              │
                      ▼              ▼
        ┌──────────────────────┐  ┌─────────────────────────────┐
        │  HUNLPoker (PR 3)    │  │ profiler/memory.py (NEW)    │
        │   + abstraction tbl  │  │  MemoryProbe / MemoryReport │
        └──────────────────────┘  └─────────────────────────────┘
                      │
                      ▼
        ┌──────────────────────┐
        │  DCFRSolver (PR 1)   │
        │  unchanged           │
        └──────────────────────┘
```

### 3.2 Why "postflop-only" is the right shape for PR 5

Two reasons:

1. **Memory floor on preflop.** Preflop is lossless (PR 4 confirmed) — 169 starting hands × full betting tree. Combined with five postflop streets per branch, the unabstracted preflop infoset count balloons past what the Python DCFR can hold even with PR 4's card abstraction on streets 1–3. Solving preflop properly needs the Rust tier (PR 6) and the public chance sampling work (PR 8). Demanding it in PR 5 would gate the first HUNL solve on three downstream PRs.
2. **Profiler is the deliverable, not the strategy.** The whole point of PR 5 is the empirical per-street memory measurement that calibrates PR 4's bucket-count decision. A flop-only or single-flop-start solve gives that measurement just as well as a full preflop solve does — postflop is where the abstraction layer's memory lives.

PR 5 thus accepts `HUNLConfig(starting_street=Street.FLOP, initial_board=[3 cards])` (or `Street.TURN` / `Street.RIVER` with appropriate board sizes) and rejects `Street.PREFLOP` with a clear message.

### 3.3 Why we reuse the existing `DCFRSolver` unchanged

PR 1's `dcfr.py` is correct (passes Kuhn `−1/18` Nash value, passes Leduc equilibrium, passes the Kuhn/Leduc diff test against the Rust port). The hyperparameters are locked (α=1.5, β=0, γ=2.0 per PLAN.md). The algorithm walks any `Game` protocol implementer. **HUNLPoker already implements that protocol** (PR 3) — so the solver works on it out of the box.

What changes between Leduc (288 infosets, <10s) and HUNL postflop (10⁶–10⁸ infosets even abstracted) is *scale*, not algorithm. The Python DCFR's `_cfr` recursion will visit far more nodes per iteration; lazy-discounting on infosets is already in place (`InfosetData.last_discount_iter`). What we *don't* know empirically is whether the Python tier can complete *N* iterations on a flop-spot tree in finite time on the MacBook. PR 5 measures this; the answer informs PR 6's port priorities.

### 3.4 What "first solve" means concretely

PR 5 ships **three** progressively-bigger postflop fixtures, each gated by a convergence target:

1. **River-only subgame (cardless, no abstraction):** the PR 3 `default_tiny_subgame` (`AhKc` vs `QdQh` on `As 7c 2d Kh 5s`, SPR 1) extended to a 5-min-target full solve. Used as the gold-standard "solver actually works" smoke test.
2. **Single flop spot (with PR 4's 256/128/64 abstraction):** a dry flop (e.g., `As 7c 2d`), 100 BB stacks, 3 bet sizes (33%/75%/200%) restricted from the full 5+all-in menu. Used as the standard memory-budget exercise.
3. **Single flop spot with the full 6-size menu (256/128/64 abstraction):** same dry flop, full PR 3 action abstraction. Used as the stress-test for the memory profiler.

Fixtures (1) and (2) are required convergence tests; fixture (3) is a "memory floor" test (it runs for K iterations and the assertion is on memory usage, not exploitability).

### 3.5 Memory profiler — design philosophy

The profiler answers one question precisely and three other questions approximately:

- **Precise:** *what fraction of total solver memory does each street consume?* This is the question PLAN.md commits PR 4 to revisit (see §10 follow-ups: "If river is <30% of total solver memory, the abstraction artifact's river layer drops out and `lookup_bucket(..., Street.RIVER)` returns `-1`").
- **Approximate:** *what is the total memory cost of an N-iteration solve?* (For budget planning.)
- **Approximate:** *how much memory does the loaded `AbstractionTables` itself cost?* (For budget planning; PR 4's artifact is ~100 MB to ~750 MB.)
- **Approximate:** *what is the marginal cost per additional infoset?* (For sizing future bucket-count decisions.)

The profiler instruments `DCFRSolver` from the outside — it never modifies `dcfr.py`. It introspects `solver.infosets` (the existing `dict[str, InfosetData]`) and groups by street tag parsed from the infoset key.

**Critical correctness check:** the profiler's reported total must agree with `psutil.Process().memory_info().rss` within ±10% (after subtracting interpreter baseline + abstraction-table size). This is the calibration assertion in the test plan; without it the per-street numbers are not trustworthy.

## 4. Pipeline / runtime stages

`solve_hunl_postflop(config, abstraction, iterations, ...) -> SolveResult` performs these stages in order. Each is independently testable.

### Stage A: input validation
- Assert `config.starting_street >= Street.FLOP`. Reject preflop with `ValueError("PR 5 is postflop-only; preflop solver lands in PR 9.")`.
- Assert `config.initial_board` length matches `starting_street`: flop=3, turn=4, river=5. Reject mismatches.
- Assert `config.rake_rate == 0.0 and config.rake_cap == 0`. (Inherited from PR 3.)
- If `abstraction is not None`, assert it is an `AbstractionTables` instance and that its `metadata['bucket_counts']` tuple length is 3 (flop, turn, river).
- If `abstraction is None` *and* the tree includes flop/turn cards on at least one street where `starting_street > Street.RIVER` is false, **warn** (not error) that lossless mode will use a lot of memory. (Note: lossless river is the smallest layer so for a river-only subgame this is fine; warning fires only for flop-start or turn-start without abstraction.)

### Stage B: instrument the solver
- Construct `DCFRSolver(game)` as usual. The `game` is `HUNLPoker(config_with_abstraction)`.
- Wrap the solver in a `MemoryProbe` (see §6 for the interface). The probe registers a hook that runs after each iteration block and snapshots `solver.infosets` keyed by parsed street.
- The probe also records iteration timestamps (wallclock per iteration block) so the final report can show GB-per-iter and sec-per-iter as derived metrics.

### Stage C: run the DCFR loop
- Same shape as `solver.solve`: chunked iterations with optional `log_every` for exploitability history.
- After each chunk, the probe takes a snapshot. **The probe must not double-count.** Per-iteration snapshots overwrite the previous snapshot; only the final snapshot is reported in `MemoryReport`.
- Memory checks happen *between* chunks, not inside the CFR recursion (which would slow it down).
- **Abort condition:** if total memory (per the probe's calculation) exceeds the budget (`max_memory_gb`, default 14 GB), the solver halts with a `MemoryError` that includes the partial `MemoryReport`. Caller can catch this and adapt (e.g., tighten the abstraction).

### Stage D: compute exploitability
- Use the existing `solver.exploitability` function. (Already works on any Game-protocol game.)
- This is the expensive bit on big trees; it walks the tree twice (best-response for each player). For a 10⁶-infoset tree this is ~minutes on the Python tier.
- We compute exploitability **once at end** for fixture 2 and 3 (the memory tests), but for the convergence-target fixtures (1, river-only) we compute it every `log_every` iterations so we can plot the curve.

### Stage E: build the SolveResult + MemoryReport
- Average strategy from `solver.average_strategy()`.
- Exploitability history (list of floats per chunk).
- `MemoryReport` includes:
  - Per-street: bytes used by regret_sum + strategy_sum, infoset count, mean infoset size, max infoset action count.
  - Total bytes (sum of per-street + abstraction-table size + interpreter overhead).
  - Ratio of each street to total.
  - Wallclock per iteration (mean + max).
  - `psutil` RSS at end of solve (for the calibration check).
- The result returned to the caller is a `SolveResult` subclass that adds the `memory_report` field, *or* a tuple `(SolveResult, MemoryReport)`. **Decision flagged for user (§11):** which.

## 5. Files to create

- `poker_solver/hunl_solver.py` — Stage A–E orchestration. Functions:
  - `solve_hunl_postflop(config: HUNLConfig, abstraction: AbstractionTables | None = None, iterations: int = 10_000, *, log_every: int | None = None, max_memory_gb: float = 14.0, seed: int | None = None, dcfr_kwargs: dict | None = None) -> HUNLSolveResult`
  - `HUNLSolveResult` dataclass: extends or wraps `SolveResult` with `memory_report: MemoryReport`.
  - Internal: `_validate_postflop_config`, `_attach_abstraction`, `_run_with_probe`.
- `poker_solver/profiler/__init__.py` — exports `MemoryProbe`, `MemoryReport`, `StreetMemoryEntry`.
- `poker_solver/profiler/memory.py` — `MemoryProbe` (instrumentation class), `MemoryReport` (dataclass), `StreetMemoryEntry` (per-street row), helper `_parse_street_from_key(infoset_key: str) -> Street | None` (extracts the street token `p`/`f`/`t`/`r` from PR 3's lossless format AND PR 4's bucketed format `b<id>|<street>|...`).
- `tests/test_hunl_postflop_solve.py` — convergence + invariant tests on the three fixtures (target: ~12 tests).
- `tests/test_memory_profiler.py` — profiler correctness, including the `psutil` calibration check (target: ~10 tests).
- `tests/fixtures/hunl_solve_fixtures.py` — fixture builders for the three solve scenarios, importable by the test files. (Keeps the test files focused on assertions.)

## 6. Files to modify

- `poker_solver/cli.py`:
  - Extend `--hunl-mode` choices to add `postflop` (in addition to `tiny_subgame` and `full`). `postflop` invokes `solve_hunl_postflop`.
  - Add CLI flags scoped to `--hunl-mode postflop`:
    - `--board STR` (required for postflop) — comma-or-space separated cards, e.g. `"As 7c 2d"` for flop.
    - `--stacks INT` (default 100, in BB) — starting stack per player.
    - `--abstraction PATH` (carried over from PR 4) — path to `.npz` artifact. If omitted, runs lossless (only valid for river-only subgames).
    - `--max-memory-gb FLOAT` (default 14.0) — abort budget.
    - `--bet-sizes STR` (default `"33,75,100,150,200"`) — comma-separated pot fractions; restricts the PR 3 menu. All-in always available.
  - For `--hunl-mode postflop`, the `solve` subcommand routes to `solve_hunl_postflop` directly (bypassing `solver.solve`), then prints the strategy table + exploitability + the new memory section.
  - The `full` mode (HUNL preflop) continues to raise `NotImplementedError` but now points at PR 9 (was PR 5).
- `poker_solver/solver.py`:
  - Add a routing branch in `solve()`: if the game is `HUNLPoker` and its config has `starting_street >= Street.FLOP`, route to `hunl_solver.solve_hunl_postflop`. (Backward-compat: HUNLPoker with `starting_street == Street.PREFLOP` continues to raise `NotImplementedError` from the existing path until PR 9 lands the preflop branch.)
  - **See PR 9 spec §6 for the canonical full dispatch composition** (push/fold ≤15 BB → chart; >250 BB → error; postflop → postflop solver; preflop → preflop solver). PR 5 adds the postflop branch only; PRs 3.5 and 9 land the others. Push/fold short-circuit (PR 3.5) executes BEFORE PR 5's postflop branch — a `starting_stack=1500` config with `starting_street=Street.FLOP` still hits the chart, since the chart implicitly handles forced jam/fold play at sub-15-BB depths.
  - This is the minimum-invasive change — keeps `solver.solve` as the unified entry point.
- `poker_solver/__init__.py`:
  - Re-export `solve_hunl_postflop`, `HUNLSolveResult`, `MemoryReport`, `MemoryProbe`, `StreetMemoryEntry`.
- `pyproject.toml`:
  - Add `psutil>=5.9` to runtime dependencies. (Used by the profiler for the RSS calibration check. Cross-platform, MIT-licensed, small dep.)

**Not modified by PR 5:**
- `poker_solver/dcfr.py` — unchanged. The profiler probes from outside.
- `poker_solver/hunl.py` — **PR 5 does not modify it.** (Note: PR 6 will modify `hunl.py` to add `_serialize_hunl_config` per PR 6 §6.2, and PR 8 will modify `hunl.py` to add `use_pcs: bool` per PR 8's amended §6 / consistency review I6. PR 5 itself touches nothing in this file; the modifications are additive across PRs.)
- `poker_solver/abstraction/` — unchanged (PR 4 owns it).
- `tests/test_dcfr_*` and `tests/test_leduc_*` and `tests/test_hunl_*` — unchanged. All existing tests must still pass.

**Updated 2026-05-21 per consistency review:** dispatch composition now cross-references PR 9 §6 as canonical (B4 resolution). Note on `hunl.py` corrected to reflect that PR 6 + PR 8 also modify it (consistency review I1 resolution).

## 7. Memory profiler design (detail)

### 7.1 `MemoryProbe` interface

```python
class MemoryProbe:
    """Instruments a DCFRSolver from outside. No modification to dcfr.py."""

    def __init__(self, solver: DCFRSolver, *, include_abstraction: AbstractionTables | None = None):
        self.solver = solver
        self.include_abstraction = include_abstraction
        self._latest_snapshot: MemoryReport | None = None

    def snapshot(self) -> MemoryReport:
        """Walk solver.infosets, group by street, compute byte totals.

        Side effect: stores in self._latest_snapshot.
        """
        ...

    @property
    def latest(self) -> MemoryReport:
        if self._latest_snapshot is None:
            raise RuntimeError("Call snapshot() at least once before reading latest.")
        return self._latest_snapshot
```

### 7.2 `MemoryReport` dataclass

```python
@dataclass(frozen=True)
class StreetMemoryEntry:
    street: Street
    infoset_count: int
    regret_bytes: int       # sum over infosets of regret_sum.nbytes
    strategy_bytes: int     # sum over infosets of strategy_sum.nbytes
    other_bytes: int        # InfosetData overhead (num_actions int, last_discount_iter int, dict key string)
    total_bytes: int        # regret + strategy + other
    mean_actions_per_infoset: float
    max_actions_per_infoset: int

@dataclass(frozen=True)
class MemoryReport:
    per_street: tuple[StreetMemoryEntry, ...]   # ordered (FLOP, TURN, RIVER) when present
    preflop_lossless_entry: StreetMemoryEntry | None  # if any preflop infosets present
    abstraction_table_bytes: int                # PR 4 artifact size in RAM
    solver_arrays_total_bytes: int              # sum of per_street.total_bytes
    other_overhead_bytes: int                   # dict overhead + Python object headers
    grand_total_bytes: int                      # solver + abstraction + other
    rss_observed_bytes: int                     # psutil RSS at snapshot time
    rss_baseline_bytes: int                     # captured at probe construction
    wallclock_per_iter_sec: float | None        # mean over snapshots; None if only one snapshot
    iterations_at_snapshot: int

    @property
    def river_ratio(self) -> float:
        """River layer's share of total solver arrays (the PLAN.md trigger)."""
        ...

    @property
    def rss_calibration_error(self) -> float:
        """Relative error between (grand_total - baseline) and (rss - baseline)."""
        ...
```

### 7.3 How the profiler infers per-street ownership

PR 3 + PR 4's infoset key format:

- **Lossless (no abstraction):** `f"{player_hole}|{board}|{street_token}|{betting_history}"` — street_token is `p`/`f`/`t`/`r`.
- **Bucketed (PR 4):** `f"b{bucket_id}|{street_token}|{betting_history}"` — preflop stays lossless per PR 4 §3.5.

`_parse_street_from_key(key: str) -> Street | None` does the parse:
- Split on `|`.
- If the first token starts with `b`, format is bucketed → street is the second field.
- Else, format is lossless → street is the third field.
- Returns `Street.PREFLOP / FLOP / TURN / RIVER`, or `None` if parse fails (defensive — should never happen on a well-formed key).

This is fragile against future key-format changes but explicit: any change to the key format requires an update in *one place* in `profiler/memory.py`. The test plan includes a "key format compatibility" assertion that fails loudly if the format changes underneath the profiler.

### 7.4 Byte accounting per infoset

For each `InfosetData`:

```python
regret_bytes   = info.regret_sum.nbytes       # = num_actions * 8 (float64)
strategy_bytes = info.strategy_sum.nbytes     # = num_actions * 8
# Python object overhead: estimated, not measured exactly
other_bytes    = sys.getsizeof(info) + len(infoset_key.encode("utf-8"))
total_bytes    = regret_bytes + strategy_bytes + other_bytes
```

The `sys.getsizeof` call returns the shallow size (the `InfosetData` slot table); we do NOT recurse into the ndarrays (they're already counted via `.nbytes`). The key-string size includes the dict-key memory which is approximately tracked.

**Known approximation:** Python's dict overhead (~50% slack in the hashtable) is not separately accounted. We bundle it into `other_overhead_bytes` at the report level via the formula `dict_overhead = sum(other_bytes) * 0.5` (rough heuristic; the `psutil` calibration check is the ground truth). This is documented in the profiler docstring.

### 7.5 Abstraction-table memory accounting

`AbstractionTables` holds NumPy uint8 arrays (per PR 4 §4 Stage 5):
```python
abstraction_table_bytes = (
    tables.flop_assignments.nbytes
    + tables.turn_assignments.nbytes
    + tables.river_assignments.nbytes
    + tables.flop_board_index.nbytes
    + tables.turn_board_index.nbytes
    + tables.river_board_index.nbytes
    + sys.getsizeof(tables.metadata)
)
```

PR 4 guarantees this is ≤1 GB (hard guard rail in `precompute-abstraction`). PR 5 includes it in `grand_total_bytes` so callers see a single number for memory budget planning.

### 7.6 `psutil` calibration check

After each snapshot:

```python
process = psutil.Process()
report.rss_observed_bytes = process.memory_info().rss

# At MemoryProbe construction, capture:
self.rss_baseline_bytes = psutil.Process().memory_info().rss
# (interpreter + already-loaded modules + abstraction table)
```

The calibration check (a test, not a runtime gate):

```python
solver_growth_bytes = report.rss_observed_bytes - report.rss_baseline_bytes
predicted_growth_bytes = report.solver_arrays_total_bytes + report.other_overhead_bytes
assert abs(solver_growth_bytes - predicted_growth_bytes) / solver_growth_bytes < 0.10
```

If this fails, the profiler is mis-counting. Test `test_memory_profiler_matches_rss` checks this on a small fixture where the absolute numbers are small enough that a 10% bound is meaningful.

### 7.7 Hard memory budget enforcement

`solve_hunl_postflop` enforces `max_memory_gb`:

```python
# After each iteration chunk:
report = probe.snapshot()
if report.grand_total_bytes > max_memory_gb * 1024**3:
    raise MemoryError(
        f"Memory budget exceeded: {report.grand_total_bytes / 1024**3:.1f} GB > "
        f"{max_memory_gb} GB. River layer: {report.river_ratio:.1%}. "
        f"Consider tightening the abstraction: "
        f"(a) build a smaller artifact via `precompute-abstraction --bucket-counts X,Y,Z`, "
        f"or (b) restrict --bet-sizes to fewer fractions. "
        f"Partial report attached.",
        report,  # the partial MemoryReport is stashed on the exception args
    )
```

Failure mode is **caught and reported**, not a hard interpreter crash. The user sees actionable guidance.

### 7.8 Inspiration from postflop-solver (AGPL — read-only)

`references/code/postflop-solver/src/game/base.rs:259` exposes `memory_usage() -> (uncompressed, compressed)` returning a tuple `(uncompressed_bytes, compressed_bytes)`. `src/utility.rs:56` has the per-vector helper `vec_memory_usage<T>(vec) = capacity * size_of::<T>()`. `src/game/base.rs:619` (`memory_usage_internal`) walks every owned `Vec` (added_lines, valid_indices_turn, hand_strength, isomorphism_swap_*, etc.) and sums.

**What we adopt (architecturally):** the principle of "compute total memory by summing every backing buffer." **What we don't adopt:** their compressed-vs-uncompressed distinction (compression is a PR 8+ feature) and their bunching-aware accounting (postflop-solver's blocker dimensionality). No code is copied; the structure is a generic "walk-and-sum" loop, present in any system-level memory audit.

## 8. Convergence + memory targets

PR 5's three fixtures and what each must achieve:

### Fixture 1: river-only subgame (no card abstraction)

- **Config:** PR 3's `default_tiny_subgame()` — `AhKc` vs `QdQh` on `As 7c 2d Kh 5s`, SPR 1, full 6-size menu, postflop_raise_cap=3.
- **Iterations:** up to 10,000 (early-exit on exploitability target).
- **Convergence target:** exploitability < 0.01 BB.
- **Wallclock target:** < 5 minutes on the M-series MacBook.
- **Memory target:** < 200 MB (this is essentially a sanity-check fixture; arrays are tiny).
- **Failure mode:** if either target misses, the test fails and the user investigates.

### Fixture 2: single flop spot (default abstraction)

- **Config:** flop-start, board `[As, 7c, 2d]`, 100 BB stacks, `bet_size_fractions=(0.33, 0.75, 2.00)` (3 sizes), postflop_raise_cap=3.
- **Abstraction:** PR 4's 256/128/64 default artifact. (Tests use a smaller synthetic artifact — `(16, 8, 4)` — so they run in CI without a real abstraction file; the assertion is on memory ratio shape, not absolute size.)
- **Iterations:** 10,000.
- **Convergence target:** exploitability < 0.1 BB (relaxed vs Fixture 1 because the abstraction is lossy).
- **Wallclock target:** < 30 minutes on the MacBook (Python tier is slow — see §10 risks).
- **Memory target:** < 14 GB total (default `max_memory_gb`).
- **Failure mode:** if memory exceeds budget, the abort path triggers and the partial `MemoryReport` is the test artifact (the test asserts the abort happens cleanly, not that the solve completes).

### Fixture 3: single flop spot, full menu (default abstraction)

- **Config:** same flop, 100 BB stacks, full 5-size menu (33/75/100/150/200) + all-in, postflop_raise_cap=3.
- **Iterations:** 1,000 (smoke level — we're testing memory, not convergence).
- **Memory target:** < 16 GB (hard ceiling for the MacBook).
- **Convergence target:** none — exploitability is logged but not asserted.
- **Wallclock target:** < 10 minutes for the 1k iterations (we're profiling, not solving).
- **Purpose:** stress-test the profiler. Validates that the per-street ratios are stable across iteration counts and that the abort path triggers cleanly when memory pressure rises.

### Quantitative answer to "is the river layer <30% of total memory?"

`MemoryReport.river_ratio` is the metric. PLAN.md commits PR 4 to revisit the abstraction if this is < 30%. **Decision criterion:** after PR 5 lands, the user reads the per-street breakdown from Fixture 2's report and decides:
- River ratio > 50%: abstraction is bottlenecked by river; consider lossless river in a future PR (revisit the hybrid debate).
- River ratio 30–50%: abstraction is well-balanced; no immediate revisit.
- River ratio < 30%: river is over-bucketed relative to flop/turn; PR 4's revisit should *shrink* the river bucket count or hold flop/turn at higher granularity.

The profiler **just reports** — it doesn't auto-adjust. The decision lives with the user + the autonomous log.

## 9. Test plan

### 9.1 `tests/test_hunl_postflop_solve.py` (~12 tests)

Each test < 60s except where noted. CI runner uses smaller fixtures (e.g., 100 iterations instead of 10,000) to stay under timeout; full-target tests live in a `slow` marker.

1. `test_postflop_river_subtree_converges` — Fixture 1, full solve. Asserts `exploitability_history[-1] < 0.01` and wallclock < 5min. **Marked `@pytest.mark.slow`** (skipped by default in CI; runs locally).
2. `test_postflop_river_subtree_smoke_100_iters` — Fixture 1, 100 iterations only. Asserts `exploitability_history[-1] < 1.0` BB (loose); validates the wiring without waiting for convergence.
3. `test_postflop_flop_solve_runs_without_crashing` — Fixture 2 with a tiny synthetic abstraction (`bucket_counts=(4,2,2)`), 100 iterations. Asserts the call returns a `HUNLSolveResult` with non-empty `memory_report.per_street`.
4. `test_postflop_flop_solve_strategy_is_valid` — Fixture 2 with the tiny synthetic abstraction. For every infoset key in the returned strategy, assert `sum(probs) == pytest.approx(1.0)`, `all(0 <= p <= 1 for p in probs)`, `len(probs) == num_actions_at_that_infoset`.
5. `test_postflop_solve_rejects_preflop_config` — pass `HUNLConfig(starting_street=Street.PREFLOP)`; assert `ValueError`.
6. `test_postflop_solve_rejects_board_mismatch` — pass `starting_street=Street.FLOP` with 4-card board; assert `ValueError`.
7. `test_postflop_solve_rejects_rake` — pass `rake_rate=0.05`; assert `ValueError`.
8. `test_postflop_solve_works_without_abstraction_on_river_subgame` — Fixture 1 (river-only); pass `abstraction=None`; assert it runs.
9. `test_postflop_solve_warns_for_lossless_flop_start` — Fixture 2 with `abstraction=None`; capture warnings, assert a `UserWarning` mentioning "lossless" fires.
10. `test_postflop_solve_memory_budget_aborts_cleanly` — set `max_memory_gb=0.001` (1 MB; absurdly low); assert a `MemoryError` is raised and that the exception's `args[1]` is a `MemoryReport` instance with `grand_total_bytes > 0`.
11. `test_postflop_solve_log_every_records_history` — Fixture 1 with `log_every=50`; assert `len(exploitability_history) >= 1` and the values are monotone-non-increasing on average (allows minor non-monotonicity from DCFR's discount transient).
12. `test_postflop_solve_intuition_gauntlet_dry_overpair_bets` — Fixture 2 (with tiny abstraction); after solving, look up the infoset where P0 holds an overpair on the dry flop and assert the strategy assigns >50% weight to the bet actions. (Soft sanity check — if it fails the user investigates rather than the test being right; it's a "looks like poker" smoke.)

### 9.2 `tests/test_memory_profiler.py` (~10 tests)

1. `test_memory_probe_snapshot_returns_report` — wrap a freshly-constructed solver, snapshot, assert returns a `MemoryReport`.
2. `test_memory_report_per_street_covers_postflop` — solve Fixture 2 for 50 iterations; assert `MemoryReport.per_street` has at least one entry for FLOP, TURN, RIVER (HUNL postflop touches all three via chance transitions).
3. `test_memory_report_river_ratio_in_plausible_range` — Fixture 2 (with tiny abstraction); after 50 iterations, assert `0.0 <= report.river_ratio <= 1.0`. Soft sanity (the value tells us the actual answer; we don't pre-judge it).
4. `test_memory_report_grand_total_equals_sum` — assert `grand_total_bytes == solver_arrays_total_bytes + abstraction_table_bytes + other_overhead_bytes`.
5. `test_memory_report_no_preflop_entry_for_river_subgame` — Fixture 1 (river-only); assert `report.preflop_lossless_entry is None` and no per-street entry is for `Street.PREFLOP`.
6. `test_memory_profiler_matches_rss_within_10pct` — the calibration check (§7.6). Solve Fixture 2 for 200 iterations (enough memory to make the bound meaningful); assert `abs(report.rss_calibration_error) < 0.10`.
7. `test_memory_probe_handles_empty_solver` — fresh solver, no iterations run; snapshot returns a report with `per_street == ()` and `solver_arrays_total_bytes == 0`.
8. `test_memory_probe_handles_bucketed_keys` — synthetic infosets with keys like `"b3|f|x"`; assert the profiler correctly assigns them to `Street.FLOP`.
9. `test_memory_probe_handles_lossless_keys` — synthetic infosets with keys like `"AhKh|7d2c9h|f|xx"`; assert the profiler correctly assigns to `Street.FLOP`.
10. `test_memory_probe_parses_unknown_keys_safely` — synthetic infoset with malformed key `"not_a_real_key"`; profiler logs a warning + lumps into an "unknown" bucket. (Defensive — we never crash on bad data.)

### 9.3 Convergence smoke chain (in `test_hunl_postflop_solve.py`)

These are bundled into the existing tests, but called out separately as the "monotone-decreasing exploitability" check:

- For Fixture 1, run with `log_every=100` for 500 iterations; assert `exploitability_history[-1] < exploitability_history[len(history) // 4]` (final < quartile point) — DCFR isn't strictly monotone but late iterations should beat early ones.
- For Fixture 2 (with tiny abstraction), run with `log_every=10` for 100 iterations; assert that the *moving average* of the last 5 exploitability values is less than the moving average of the first 5.

### 9.4 Intuition gauntlet test

Per PLAN.md §4 ("Poker-intuition gauntlet → MDF on overpair vs simple bet, fold-equity on all-in shoves, polarization on monotone boards"):

- `test_postflop_solve_intuition_gauntlet_dry_overpair_bets` (already in §9.1 test 12) covers the "overpair bets on dry board" sanity.
- We add one more: `test_postflop_solve_intuition_gauntlet_polarization_on_monotone` — flop = `[8h, 7h, 6h]` (monotone, low, connected); after solving Fixture-2-like setup with hand `(Kc, Ks)` (vulnerable overpair), assert the strategy is *polarized* (mix of small-bet-or-check and large-bet-or-check, not uniform). This is a soft assertion: max(probs) > 0.6 OR min(probs) < 0.05 for the non-fold actions. Documented as "intuition" — failure prompts user review, not auto-fix.

### 9.5 Fixture file (`tests/fixtures/hunl_solve_fixtures.py`)

Exposes:
- `river_subgame_config() -> HUNLConfig` — the PR 3 default extended with a fixed seed.
- `flop_dry_3size_config() -> HUNLConfig` — the standard Fixture-2 setup.
- `flop_full_menu_config() -> HUNLConfig` — Fixture 3.
- `monotone_flop_config() -> HUNLConfig` — for the polarization gauntlet.
- `tiny_synthetic_abstraction() -> AbstractionTables` — builds a `(4, 2, 2)` bucket-count artifact in memory (no `.npz` write); deterministic, ~10ms to build. Used by all postflop-with-abstraction tests so we don't need a real PR 4 artifact in CI.

## 10. Three-agent fan-out plan

Matches the PR 3 / PR 4 pattern: tight per-agent ownership, parallel execution, integration at end.

### Agent A — `hunl_solver.py` (orchestration)

**Owns:** `poker_solver/hunl_solver.py`.

**Does NOT touch:** `profiler/`, any test file, `dcfr.py`.

**May modify (small, surgical):** `solver.py` (routing branch in `solve()`), `cli.py` (extending `--hunl-mode`), `__init__.py` (re-exports).

**Deliverables:**
- `solve_hunl_postflop` with the signature in §5.
- `HUNLSolveResult` dataclass.
- Stage A validation logic.
- Stage B–E orchestration: instantiates DCFRSolver, MemoryProbe (Agent B's class), runs chunked iterations, computes exploitability, packages results.
- Pure typed Python; `mypy --strict` clean on the new file.
- CLI integration: `--hunl-mode postflop` works end-to-end against the river-only fixture (without abstraction) and the flop fixture (with abstraction).
- Routing in `solver.solve()` so users calling the top-level `solve(HUNLPoker(postflop_config))` are transparently routed to the new function.

**Interface lock:** Agent A imports from `poker_solver.profiler.memory import MemoryProbe, MemoryReport` — the surface contract is whatever's in §6–§7 of this spec.

### Agent B — `profiler/memory.py`

**Owns:** `poker_solver/profiler/__init__.py`, `poker_solver/profiler/memory.py`.

**Does NOT touch:** `hunl_solver.py`, any test file, `dcfr.py`, `hunl.py`.

**Deliverables:**
- `MemoryProbe` class with `__init__(solver, *, include_abstraction)` and `snapshot()` method.
- `MemoryReport` and `StreetMemoryEntry` dataclasses per §7.2.
- `_parse_street_from_key` helper per §7.3.
- Byte accounting logic per §7.4.
- Abstraction-table memory accounting per §7.5.
- `psutil` integration per §7.6.
- Pure NumPy + standard library + `psutil`. No new third-party deps beyond `psutil`.
- `mypy --strict` clean.

**Interface lock:** Agent B implements only the public surface in §6.

### Agent C — tests (written from spec alone)

**Owns:** `tests/test_hunl_postflop_solve.py`, `tests/test_memory_profiler.py`, `tests/fixtures/hunl_solve_fixtures.py`.

**Does NOT touch:** any non-test file.

**Deliverables:**
- All test files per §9.
- Each test self-contained; matches the style of `tests/test_leduc_core.py` and `tests/test_hunl_core.py`.
- Uses only the public API in `poker_solver/__init__.py` (`solve_hunl_postflop`, `HUNLSolveResult`, `MemoryReport`, `MemoryProbe`, plus the PR 3/4 public surface).
- Agent C does NOT see Agent A's or Agent B's code while writing tests. They write strictly from this spec.

**Parallelism rationale:** C runs concurrently with A+B because the spec is the interface lock. By the time A+B return, C's test file is ready; pytest is the integration check.

**Edge-case allowance:** Agent C may write tests that are correct-per-spec but reveal genuine ambiguities. If a test fails because the spec was ambiguous, **the spec is the source of truth** — we update the impl or update the spec, not silently tweak the test. (Same rule as PR 3.)

## 11. Critical correctness items

1. **First HUNL solve produces a valid strategy.** For every infoset in `result.average_strategy`, `sum(probs) ≈ 1.0` (within 1e-9), no NaN, no Inf, all probabilities in `[0, 1]`. (Test 4 in §9.1.)
2. **The solver works WITHOUT card abstraction on the river-only subgame.** (Test 8 in §9.1; this is Fixture 1.)
3. **The solver works WITH PR 4's card abstraction on the flop subgame.** (Test 3 in §9.1; uses tiny synthetic abstraction.)
4. **Memory profiler reports match psutil RSS within 10%.** The calibration assertion (Test 6 in §9.2). Without this, the per-street breakdown is not trustworthy.
5. **Memory OOM is caught and reported, not a hard crash.** (Test 10 in §9.1.)
6. **PR 1/2/3/4 tests still pass unchanged.** Adding a routing branch to `solver.solve()` must not perturb Kuhn/Leduc/Leduc-DCFR convergence behavior.
7. **Hyperparameters unchanged.** PR 5 uses α=1.5, β=0, γ=2.0 (PLAN.md lock). No `--alpha` / `--beta` / `--gamma` flags exposed at CLI level for HUNL (DCFR hyperparams are not a per-solve knob in v1).
8. **The profiler's per-street parsing handles both lossless and bucketed key formats.** Both are tested explicitly (Tests 8 and 9 in §9.2). If PR 4's key format changes, those tests fail loudly and Agent B updates the parser.
9. **Aborted solves still produce a partial `MemoryReport`.** The `MemoryError` carries the partial report as its second arg so the caller can inspect what got allocated before the abort.
10. **Deterministic re-runs.** Same `seed`, same config, same abstraction → identical strategy table within float tolerance. (DCFR is deterministic; this is mostly a sanity check that we don't accidentally introduce nondeterminism via dict iteration order in the profiler or routing code.)

## 12. Risks and mitigations

- **Python DCFR is slow at HUNL scale.** Each iteration walks the full tree. Even on a flop-start spot with 256/128/64 abstraction, a 10k-iteration solve could take many hours. **Mitigation:** PR 5 only requires SMALL spots to demonstrate end-to-end correctness — three concrete fixtures of progressively-bounded size. The Rust port (PR 6) is where production-scale solves happen. PR 5's job is **prove the wiring + measure memory**, not produce production-quality strategies.
- **PR 4's abstraction artifact may not exist on the test runner.** Building a real 256/128/64 artifact requires the multi-hour pipeline in PR 4. **Mitigation:** all tests that need an abstraction use the `tiny_synthetic_abstraction()` fixture (bucket counts 4/2/2, built in-memory in ~10ms). The "real artifact" pathway is exercised only manually by the user, not in CI.
- **Memory profiler may miss Python interpreter internals.** Dict slack, GC overhead, COW pages — these add up. **Mitigation:** the `psutil` calibration assertion catches the worst case (10% tolerance). For larger drifts, the test fails loudly; for smaller drifts, the report is documented as "within 10%" not "exact."
- **`psutil` is a new dependency.** It's MIT, cross-platform, small, and mature. **Mitigation:** add it to `pyproject.toml`'s `dependencies` (not optional) so it's installed by default. Document in the autonomous log.
- **Exploitability computation is expensive on the big trees.** `solver.exploitability` walks the tree twice. For Fixture 2 (~10⁵ infosets even abstracted) this is ~minutes per call. **Mitigation:** for Fixtures 2 and 3 we compute exploitability only at end (`log_every=None`); for Fixture 1 (small) we can afford `log_every` for the curve.
- **Memory probe parsing of infoset keys is fragile.** If PR 4 changes the key format between landing and PR 5 landing, the profiler breaks. **Mitigation:** Tests 8 and 9 in §9.2 lock the format. If PR 4 introduces a third format (e.g., adds preflop bucketing later), the profiler raises on the unknown shape and someone updates `_parse_street_from_key`.
- **Aborting on memory budget may leave partial state in `solver.infosets`.** The Python dict is not deallocated; it's referenced via `solver`. **Mitigation:** documented behavior. Caller drops the solver reference to release memory. The partial `MemoryReport` is returned as the exception arg.
- **Fixture 2 may NOT converge in reasonable wallclock on the Python tier.** This is acceptable: the test asserts the *call returns* + memory bound, not convergence. Convergence is a Fixture-1 assertion only. **Mitigation:** documented in test 3 docstring.
- **Intuition-gauntlet tests are inherently subjective.** They check "looks like poker" but a different convergence point could fail the assertion. **Mitigation:** documented as soft-assertions; failure prompts user review, not auto-correction. The same pattern as PR 3's tree-count loose bounds.

## 13. Out-of-scope follow-ups

- **PR 6:** Rust port of `hunl_solver.solve_hunl_postflop`. Mechanical translation; differential test (existing pattern from PR 1/2) gates correctness.
- **PR 7:** River-spot diff test vs `noambrown/poker_solver`. Uses Fixture 1 (or similar river-only configs) as the input set.
- **PR 8:** NEON SIMD + cache blocking + public chance sampling. Memory profiler from PR 5 is the input to the cache-blocking work (per-street layout decisions).
- **PR 11:** Spot library mode — cache solved spots to disk, lookup by (board, stacks, pot). PR 5's `HUNLSolveResult` is the natural serialization unit.
- **Lossless-river revisit** (PLAN.md commitment): once PR 5's profiler runs in anger, if river ratio < 30% of total memory, PR 4's revisit may drop the river bucket and fall back to lossless on that street. PR 5's profiler is the trigger.
- **Per-street profiler exposed via UI** — PR 10 task. PR 5's `MemoryReport` is JSON-serializable (dataclass with primitive fields), so the GUI can render it.
- **Concurrent / multi-process CFR** — PR 8 candidate. Each chunk's iteration could be parallel-mapped across infosets, but the per-iteration discount-then-update pattern in `dcfr.py` is currently single-threaded.

## 14. Decisions deferred to user (defaults locked)

Each entry locks a default; if the user prefers otherwise, redirect before launching A/B/C. The autonomous log captures each one.

1. **Memory budget hard ceiling: 14 GB vs 16 GB.** PLAN.md §1 stack-depth table says 100 BB default tree-builder memory is ~10–14 GB; the MacBook is 16 GB. Default: **`max_memory_gb=14.0`**. Override candidates: 16.0 (uses headroom but risks OS swap), 12.0 (more conservative, room for OS overhead). The CLI exposes `--max-memory-gb` so the user can override per-invocation regardless.
2. **"Convergence" semantics — exploitability threshold vs iteration count.** Default: **iteration count + best-effort exploitability**. `solve_hunl_postflop(iterations=N)` runs N iterations regardless of exploitability. We expose a `target_exploitability: float | None` parameter that, when set, early-exits if achieved. Default `None`. (Matches postflop-solver's pattern: `solve(game, max_num_iterations, target_exploitability, …)`.)
3. **`HUNLSolveResult` is a subclass of `SolveResult`.** **LOCKED** to subclass per `docs/spec_consistency_review.md` finding N7 — PR 9 and PR 11 already depend on the subclass form (PR 9's `PreflopSolveResult` extends `HUNLSolveResult`; PR 11 §2.4 uses `SolveResult.average_strategy` access pattern). `HUNLSolveResult(SolveResult)` adds `memory_report: MemoryReport`. Tuple form rejected. (Was open in the original spec; consistency review locked it 2026-05-21.)
4. **Default `bet_size_fractions` for Fixture 2.** Spec says `(0.33, 0.75, 2.00)` — 3 sizes. Override candidates: `(0.33, 0.75, 1.00, 2.00)` (4 sizes; larger tree), `(0.75,)` (1 size; smallest tree, dubious quality).
5. **CLI flag for selecting fixtures.** Default: **no fixture-selector flag** — the user supplies `--board`, `--stacks`, etc., and the CLI builds an ad-hoc `HUNLConfig`. The three fixtures live in `tests/fixtures/` only. Override candidate: add `--preset {river_dry,flop_dry_3size,flop_full_menu,monotone}` for convenience.
6. **Logging verbosity.** Default: **single end-of-solve summary** (current `_cmd_solve` style + memory section). Override candidate: per-iteration progress bar (would need `tqdm` as a new dep).
7. **What to do when `abstraction is None` and `starting_street == Street.FLOP`.** Default per §4 Stage A: **warn** (UserWarning), don't error. The lossless flop is large but not unbounded. Override candidate: error (force the user to supply an abstraction).
8. **Where the per-street memory report shows up.** Default: included in stdout when CLI runs, accessible programmatically via `result.memory_report`. No JSON dump flag. Override candidate: `--memory-report-json PATH` for downstream tooling.
9. **River subgame solve in CI (slow test).** Default: **mark slow, skip in CI**. The 5-minute target is real; CI runners can be slower. The fast smoke (100 iter) runs in CI. Override candidate: run in CI with a 10-minute timeout.
10. **Should `MemoryProbe.snapshot()` cost be amortized?** Each snapshot walks every infoset — for 10⁶ infosets this is ~seconds. Default: **caller chooses snapshot frequency** via the `log_every` parameter (default: snapshot once at end). Override candidate: built-in throttling (snapshot at most every 60s).

## 15. Reference citations

For DCFR algorithm formulae (not invented in this spec):
- Brown, N. & Sandholm, T. (2019). "Solving Imperfect-Information Games via Discounted Regret Minimization." AAAI 2019. Available at `references/papers/`. The hyperparameter set α=1.5, β=0, γ=2.0 is the paper's recommended default (Section 5).
- Regret update formulae are documented at the top of `poker_solver/dcfr.py` (lines 1–19) — PR 5 does not re-document them.

For memory profiling patterns:
- `references/code/postflop-solver/src/utility.rs:56` — `vec_memory_usage<T>` pattern (per-allocation byte counting). **AGPL — read-only inspiration; we adopt the pattern (sum every backing buffer's `capacity * sizeof`), not the code.**
- `references/code/postflop-solver/src/game/base.rs:259` — `memory_usage() -> (uncompressed, compressed)` pattern. We adopt the architecture (one entry point, walks owned arrays), not the compressed-vs-uncompressed dichotomy.
- `psutil.Process.memory_info()` — for the RSS ground-truth calibration. Documentation: psutil.readthedocs.io.

For the per-street bucketing rationale:
- PLAN.md §1 "Card abstraction" — locks 256/128/64 default; commits PR 5 to ship the profiler that revisits this.
- PR 4 spec §10 "Out-of-scope follow-ups" — quotes the PLAN.md commitment: *"If river is <30% of total solver memory, the abstraction artifact's river layer drops out and `lookup_bucket(..., Street.RIVER)` returns `-1` (caller falls back to lossless)."* PR 5's profiler produces this ratio.

For the HUNL postflop game-tree shape:
- PR 3 spec — `HUNLPoker` / `HUNLConfig` interface (PR 5 consumes unchanged).
- PR 4 spec — `AbstractionTables` / `lookup_bucket` interface (PR 5 consumes unchanged).

## 16. Success criteria

- All new tests pass (~22 new tests across the two new test files + the fixture module).
- All PR 1/2/3/4 tests pass unchanged.
- `ruff check poker_solver tests` clean.
- `ruff format --check` clean.
- `mypy poker_solver/hunl_solver.py poker_solver/profiler/` strict-clean.
- `mypy poker_solver` overall: no new errors.
- `poker-solver solve --game hunl --hunl-mode postflop --board "As 7c 2d Kh 5s" --iterations 500` (Fixture 1, river-only, no abstraction) runs in under 60s and prints a strategy table + memory report with non-zero river_ratio.
- `poker-solver solve --game hunl --hunl-mode postflop --board "As 7c 2d" --stacks 100 --abstraction /path/to/abstraction.npz --iterations 1000 --max-memory-gb 14` (Fixture 2 shape; requires PR 4 artifact to exist on the user's machine) runs to completion and produces a memory report.
- `MemoryReport.river_ratio` is computable and reported in the CLI output.
- The audit agent (`general-purpose` with no PR-5 context) reviews against this spec and produces `docs/pr5_prep/audit_report.md` with must-fix / should-fix / nice-to-fix / looks-good sections.

## 17. Post-implementation audit

Per PLAN.md "Code + test audit (mandatory from PR 3 onward)": after A+B+C land, a fresh `general-purpose` audit agent runs with no prior context and reviews:

- The full diff (Agent A's `hunl_solver.py`, Agent B's `profiler/`, Agent C's tests + fixtures, plus the `__init__.py` + `cli.py` + `solver.py` + `pyproject.toml` deltas).
- Against this spec only.
- Output: `docs/pr5_prep/audit_report.md` with structured sections (must-fix / should-fix / nice-to-fix / looks-good).
- User reads alongside `pr_report.md` before commit OK.

Focus areas the audit must touch:
- **Memory accounting correctness:** does the byte sum actually match RSS within 10% on the calibration test?
- **Routing safety:** does `solver.solve()` for Kuhn / Leduc / HUNL-with-`tiny_subgame`-mode all still produce identical results to PR 4?
- **Abstraction-table integration:** is `HUNLConfig.abstraction` properly attached when the user passes one through?
- **Failure-mode cleanliness:** does the OOM abort path return a usable partial report, or does it crash with a confusing traceback?
- **License hygiene:** any code copy-pasted from postflop-solver (AGPL) → must be flagged. (We adopt patterns only.)
- **DCFR algorithmic correctness:** the spec asserts we don't modify `dcfr.py`. The audit confirms.
- **Reproducibility:** same seed + config → identical strategy. Audit runs the test that locks this.
- **`psutil` dependency justification:** new third-party dep added to `pyproject.toml`. Audit confirms it's MIT and small.
