# PR 5 Agent C — Tests (convergence + memory + intuition gauntlet)

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 5 Agent C.**
**Your scope:** write the test suite for the first end-to-end HUNL postflop solve + the memory profiler, including a convergence smoke chain, the `psutil` RSS calibration check, the OOM-abort path test, and the intuition-gauntlet "looks like poker" soft assertions (overpair bets dry boards; polarization on monotone boards) — all written strictly from the PR 5 spec WITHOUT seeing Agent A's or Agent B's code.
**Your contract:** ship `tests/test_hunl_postflop_solve.py` (~12 tests), `tests/test_memory_profiler.py` (~10 tests), and `tests/fixtures/hunl_solve_fixtures.py` (fixture builders); use only the public API in `poker_solver/__init__.py`; the spec is the interface lock.
**Your success criteria:** all new tests pass after Agent A + Agent B land; ruff clean; black clean; ALL 138+ existing tests still pass; tests run within reasonable wall-clock (smoke variants <60s; slow variants marked `@pytest.mark.slow`); when a test fails because the spec was ambiguous, the SPEC is the source of truth — don't tweak the test silently.
**File ownership:** you own `tests/test_hunl_postflop_solve.py`, `tests/test_memory_profiler.py`, `tests/fixtures/hunl_solve_fixtures.py`. You may NOT touch any non-test file (no Agent A's `hunl_solver.py`, no Agent B's `profiler/`, no `dcfr.py`, no `hunl.py`, no `abstraction/`).

---

## Strict file ownership

**You own (write + create freely):**
- `/Users/ashen/Desktop/poker_solver/tests/test_hunl_postflop_solve.py` (new file; ~12 tests)
- `/Users/ashen/Desktop/poker_solver/tests/test_memory_profiler.py` (new file; ~10 tests)
- `/Users/ashen/Desktop/poker_solver/tests/fixtures/hunl_solve_fixtures.py` (new file; fixture builders)

If `tests/fixtures/` doesn't exist as a Python package, create `tests/fixtures/__init__.py` as an empty file too. Otherwise, leave the existing `__init__.py` alone.

**You must NOT touch:**
- `poker_solver/hunl_solver.py` — Agent A owns this. You import its public surface (`solve_hunl_postflop`, `HUNLSolveResult`) from `poker_solver.__init__`.
- `poker_solver/profiler/` — Agent B owns this. You import its public surface (`MemoryProbe`, `MemoryReport`, `StreetMemoryEntry`, `_parse_street_from_key`) from `poker_solver.__init__` (or `poker_solver.profiler`).
- `poker_solver/dcfr.py`, `poker_solver/hunl.py`, `poker_solver/solver.py`, `poker_solver/cli.py`, `poker_solver/abstraction/*`, `poker_solver/__init__.py` — frozen / Agent A's surgical edits.
- `tests/test_dcfr_*.py`, `tests/test_leduc_*.py`, `tests/test_kuhn_*.py`, `tests/test_hunl_core.py`, `tests/test_hunl_tree.py`, `tests/test_action_abstraction.py`, `tests/test_abstraction_*.py`, `tests/test_pushfold_*.py` — all existing test files. PR 5 spec §6 freezes these. **All existing tests must pass unchanged.**
- `pyproject.toml` — Agent A or Agent B adds `psutil>=5.9`; you don't touch it.

**You write tests strictly from the spec; you do NOT read Agent A's or Agent B's implementation while writing.** This is the parallelism rationale: the spec is the interface lock. By the time A+B return, your test file is ready; pytest is the integration check (PR 5 spec §10 "Parallelism rationale").

**Edge-case allowance per spec §10:** If a test you wrote (correctly per spec) fails because the spec was ambiguous, **the spec is the source of truth** — flag the ambiguity for orchestrator review; do NOT silently tweak the test to match Agent A/B's implementation.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/pr5_spec.md`. Internalize §3.4 (three fixtures), §4 (Stages A–E for what your tests exercise), §8 (convergence + memory targets), §9 (full test plan with exact test names + assertions), §10 Agent C deliverables, §11 (critical correctness items — all of these become test assertions).
2. **Spec consistency review (cross-cutting decisions; recently amended):** `/Users/ashen/Desktop/poker_solver/docs/spec_consistency_review.md`. Especially N7 (`HUNLSolveResult` subclass form locked) and B4 (PR 9 §6 canonical dispatch composition).
3. **The PLAN (locked decisions):** `/Users/ashen/Desktop/poker_solver/PLAN.md`. Especially §1 "Card abstraction" + the 14 GB hard ceiling.
4. **The autonomous log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md`. Skim for PR 5 entries.
5. **Existing test style references (DO read these for style; DO NOT modify them):**
   - `/Users/ashen/Desktop/poker_solver/tests/test_hunl_core.py` — closest style match for HUNL game tests (function-level tests, `pytest.approx` for floats, no test classes).
   - `/Users/ashen/Desktop/poker_solver/tests/test_leduc_core.py` — short, focused, integer-or-float assertions.
   - `/Users/ashen/Desktop/poker_solver/tests/test_dcfr_*.py` — convergence-style tests; use as the reference for "exploitability history" assertions.
   - `/Users/ashen/Desktop/poker_solver/tests/test_abstraction_*.py` (if exists from PR 4) — for tiny synthetic abstraction patterns.
6. **PR 5 spec §9 test plan** is your master list. Each test in this file maps to a numbered item in spec §9.1 or §9.2.
7. **Reference style — PR 4 Agent A prompt pre-draft:** `/Users/ashen/Desktop/poker_solver/docs/pr4_prep/agent_a_prompt.md`. Same shape and tone (but you're tests, not implementation).

## Default decisions LOCKED (do not deviate)

These defaults are from PR 5 spec §14 + consistency review. The user has authorized autonomous mode; these defaults are LOCKED unless the user redirects before launch:

1. **Memory budget hard ceiling: 14 GB** (spec §14 #1). Default `memory_budget_gb=14.0`. Your OOM test sets `memory_budget_gb=0.001` (1 MB, absurdly low) to trigger the abort path predictably (spec §9.1 test 10).
2. **Iteration count primary; `target_exploitability` early-exit optional** (spec §14 #2). Default in cross-agent contract: `iterations=50_000`. Your tests run far fewer iterations (e.g., 50–500) to stay under CI timeout.
3. **`HUNLSolveResult` IS a `SolveResult` subclass** (consistency review N7 + PR 5 spec §14 #3). Your tests can `isinstance(result, SolveResult)` AND `isinstance(result, HUNLSolveResult)`.
4. **Default `bet_size_fractions` for fixture 2: `(0.33, 0.75, 2.00)`** (3 sizes; spec §14 #4). Use this for `flop_dry_3size_config()` in the fixture file.
5. **No fixture-selector CLI flag** (spec §14 #5). Your tests build configs programmatically via the fixture file.
6. **`UserWarning` on `abstraction=None` + flop start** (spec §14 #7). Your test 9 in §9.1 captures and asserts this warning.
7. **Slow tests marked `@pytest.mark.slow`** (spec §14 #9). Tests with target wallclock > 60s wear this marker and are skipped in CI by default.
8. **Soft-assertion style for intuition gauntlet** (spec §9.4): "looks like poker" tests use loose bounds and a docstring warning "soft assertion — failure prompts user review, not auto-fix."
9. **Tiny synthetic abstraction is `(4, 2, 2)` bucket counts** (spec §9.5 `tiny_synthetic_abstraction()`): smaller than `(16, 8, 4)` mentioned in §8 fixture 2 — the spec says "fixture 2 uses 256/128/64 default" but Agent C tests use a smaller synthetic. Spec §9.5 is explicit: `(4, 2, 2)`. (If you discover spec §8 fixture 2 description conflicts with §9.5, the §9.5 statement wins because it's in Agent C's deliverables section.) **Update 2026-05-21:** spec §8 fixture 2 says "(16, 8, 4)" explicitly. Both are valid; pick `(4, 2, 2)` for speed unless a test specifically needs `(16, 8, 4)` for richer behavior. Document the choice in `tiny_synthetic_abstraction()`'s docstring.
10. **Each test < 60s except `@pytest.mark.slow`** (spec §9.1 lead-in). Long tests (the river-only convergence-to-0.01-BB) wear the slow marker.

## Public API you use (do NOT touch implementations)

From `poker_solver`:
- `solve_hunl_postflop` — Agent A's entry point.
- `HUNLSolveResult` — Agent A's return type (subclass of `SolveResult`).
- `MemoryReport`, `MemoryProbe`, `StreetMemoryEntry` — Agent B's surface.
- `_parse_street_from_key` — Agent B's helper (for the key-format tests).

From PR 3 (existing):
- `HUNLPoker`, `HUNLConfig`, `Street`, `default_tiny_subgame`.

From PR 4 (existing):
- `AbstractionTables`, `lookup_bucket`. Your fixture file builds a `tiny_synthetic_abstraction()` in memory; you do NOT need a real `.npz` file.

From PR 1 (existing):
- `SolveResult` — Agent A's result subclasses this.
- `DCFRSolver` — used internally; you only interact via Agent A's solve function.

Standard library:
- `pytest`, `pytest.mark.slow`, `pytest.approx`, `pytest.raises`, `pytest.warns`.
- `numpy` (for array assertions if needed).
- `warnings` (for the `UserWarning` test).
- `math` (for `isnan`, `isinf` checks).

## Test plan (master list — implement EVERY test below)

Per PR 5 spec §9. Each test gets ONE function definition; the test names below match spec §9 exactly so the orchestrator can grep for them.

### `tests/test_hunl_postflop_solve.py` (~12 tests)

1. **`test_postflop_river_subtree_converges`** (spec §9.1 #1) — Fixture 1 (river-only, no abstraction), full solve up to 10,000 iterations with early-exit at exploitability < 0.01 BB. Wallclock < 5min. **Mark `@pytest.mark.slow`** — skipped in CI by default.
2. **`test_postflop_river_subtree_smoke_100_iters`** (spec §9.1 #2) — Fixture 1, exactly 100 iterations. Asserts `exploitability_history[-1] < 1.0` BB (loose). Validates wiring without waiting for convergence.
3. **`test_postflop_flop_solve_runs_without_crashing`** (spec §9.1 #3) — Fixture 2 with `tiny_synthetic_abstraction()` (bucket counts `(4, 2, 2)`), 100 iterations. Assert returns a `HUNLSolveResult` with non-empty `memory_report.per_street`.
4. **`test_postflop_flop_solve_strategy_is_valid`** (spec §9.1 #4) — Fixture 2 with tiny synthetic abstraction. **THE HEADLINE ACCEPTANCE TEST.** For every infoset key in `result.average_strategy`:
   - `sum(probs) == pytest.approx(1.0, abs=1e-9)`
   - `all(0.0 <= p <= 1.0 for p in probs)`
   - `not any(math.isnan(p) or math.isinf(p) for p in probs)`
   - `len(probs) == game.legal_actions_at_infoset(...)` (or equivalent; whatever the public surface allows you to verify)
5. **`test_postflop_solve_rejects_preflop_config`** (spec §9.1 #5) — pass `HUNLConfig(starting_street=Street.PREFLOP)`. Assert `pytest.raises(ValueError, match="postflop-only" or "PR 9")`.
6. **`test_postflop_solve_rejects_board_mismatch`** (spec §9.1 #6) — pass `starting_street=Street.FLOP` with a 4-card board. Assert `ValueError`.
7. **`test_postflop_solve_rejects_rake`** (spec §9.1 #7) — pass `rake_rate=0.05`. Assert `ValueError`.
8. **`test_postflop_solve_works_without_abstraction_on_river_subgame`** (spec §9.1 #8) — Fixture 1 (river-only); `abstraction=None`. Assert it runs to completion and returns a valid result. (No warning expected — lossless river is the smallest layer.)
9. **`test_postflop_solve_warns_for_lossless_flop_start`** (spec §9.1 #9) — Fixture 2 with `abstraction=None`. Use `pytest.warns(UserWarning, match="lossless")` to capture the warning.
10. **`test_postflop_solve_memory_budget_aborts_cleanly`** (spec §9.1 #10) — set `memory_budget_gb=0.001` (1 MB, absurdly low). Assert `pytest.raises(MemoryError)` AND the exception's `e.value.args[1]` is a `MemoryReport` instance with `grand_total_bytes > 0`.
11. **`test_postflop_solve_log_every_records_history`** (spec §9.1 #11) — Fixture 1 with `log_every=50` for, say, 200 iterations. Assert `len(result.exploitability_history) >= 1` AND the moving-average decreases (allow minor non-monotonicity — use the "final < quartile point" pattern from spec §9.3).
12. **`test_postflop_solve_intuition_gauntlet_dry_overpair_bets`** (spec §9.1 #12) — Fixture 2 (with tiny abstraction). After solving, find the infoset for P0 holding an overpair on a dry flop and assert the strategy assigns >50% weight to the BET actions (sum of `ACTION_BET_*` and `ACTION_ALL_IN` probabilities). **Soft assertion** — document in docstring: "failure prompts user review, not auto-fix." This is the "looks like poker" smoke from PLAN.md §4.

**Plus the additional intuition gauntlet** (spec §9.4):

13. **`test_postflop_solve_intuition_gauntlet_polarization_on_monotone`** (spec §9.4) — `monotone_flop_config()` (flop `[8h, 7h, 6h]`, hand `(Kc, Ks)`). After solving, assert the strategy is *polarized*: `max(probs) > 0.6 OR min(probs) < 0.05` for the non-fold actions. **Soft assertion.**

### `tests/test_memory_profiler.py` (~10 tests)

1. **`test_memory_probe_snapshot_returns_report`** (spec §9.2 #1) — wrap a freshly-constructed solver; `snapshot()` returns a `MemoryReport`.
2. **`test_memory_report_per_street_covers_postflop`** (spec §9.2 #2) — solve Fixture 2 for 50 iterations; assert `report.per_street` has at least one entry for FLOP, TURN, RIVER.
3. **`test_memory_report_river_ratio_in_plausible_range`** (spec §9.2 #3) — Fixture 2 (tiny abstraction); after 50 iterations, assert `0.0 <= report.river_ratio <= 1.0`. Soft sanity (the value tells us the answer; we don't pre-judge).
4. **`test_memory_report_grand_total_equals_sum`** (spec §9.2 #4) — assert `grand_total_bytes == solver_arrays_total_bytes + abstraction_table_bytes + other_overhead_bytes`.
5. **`test_memory_report_no_preflop_entry_for_river_subgame`** (spec §9.2 #5) — Fixture 1 (river-only); assert `report.preflop_lossless_entry is None` and no per-street entry has `street == Street.PREFLOP`.
6. **`test_memory_profiler_matches_rss_within_10pct`** (spec §9.2 #6) — THE CALIBRATION CHECK. Solve Fixture 2 for 200 iterations; assert `abs(report.rss_calibration_error) < 0.10`. **CRITICAL CORRECTNESS** per spec §11 #4 and §7.6.
7. **`test_memory_probe_handles_empty_solver`** (spec §9.2 #7) — fresh solver, no iterations run; `snapshot()` returns a report with `per_street == ()` and `solver_arrays_total_bytes == 0` and `river_ratio == 0.0`.
8. **`test_memory_probe_handles_bucketed_keys`** (spec §9.2 #8) — synthetic infoset keys like `"b3|f|x"`. Call `_parse_street_from_key("b3|f|x")` directly and assert `== Street.FLOP`. Plus a test of `b127|r|c|x` → `Street.RIVER`.
9. **`test_memory_probe_handles_lossless_keys`** (spec §9.2 #9) — synthetic keys like `"AhKh|7d2c9h|f|xx"`. Assert correct street parsing for all four tokens (`p`/`f`/`t`/`r`).
10. **`test_memory_probe_parses_unknown_keys_safely`** (spec §9.2 #10) — malformed key `"not_a_real_key"`. Assert `_parse_street_from_key(...)` returns `None`. Use `pytest.warns(RuntimeWarning)` if Agent B emits a warning on the first unknown key encountered via `snapshot()` (not the direct parse call).

## Fixtures (`tests/fixtures/hunl_solve_fixtures.py`)

Expose the following functions per spec §9.5:

```python
from __future__ import annotations

from poker_solver.abstraction.buckets import AbstractionTables
from poker_solver.hunl import HUNLConfig


def river_subgame_config() -> HUNLConfig:
    """PR 3 default_tiny_subgame extended with a fixed seed for determinism.

    River-only, AhKc vs QdQh on As 7c 2d Kh 5s, SPR 1.
    """
    ...


def flop_dry_3size_config() -> HUNLConfig:
    """Standard Fixture-2 setup.

    Flop-start, board [As, 7c, 2d], 100 BB stacks,
    bet_size_fractions=(0.33, 0.75, 2.00), postflop_raise_cap=3.
    """
    ...


def flop_full_menu_config() -> HUNLConfig:
    """Fixture 3.

    Same flop, 100 BB stacks, full 5-size menu (0.33, 0.75, 1.00, 1.50, 2.00)
    + all-in, postflop_raise_cap=3.
    """
    ...


def monotone_flop_config() -> HUNLConfig:
    """For the polarization gauntlet.

    Monotone low-connected flop [8h, 7h, 6h], hand (Kc, Ks) — vulnerable
    overpair.
    """
    ...


def tiny_synthetic_abstraction() -> AbstractionTables:
    """Build a (4, 2, 2) bucket-count artifact in memory.

    Deterministic, ~10ms to build. Used by all postflop-with-abstraction tests
    so we don't need a real PR 4 artifact in CI.

    Spec §9.5 explicitly mandates (4, 2, 2). Spec §8 fixture 2 description
    mentions (16, 8, 4); §9.5 wins because it's Agent C's deliverable.

    Constructs AbstractionTables with:
    - flop_assignments: shape (N_flop_boards, N_hands_per_board), uint8.
    - turn_assignments, river_assignments: same shape per street.
    - flop_board_index, turn_board_index, river_board_index: index arrays.
    - metadata: dict with schema_version, bucket_counts=(4, 2, 2),
      feature_bins=50, seed=42, build_timestamp, build_duration_sec=0.01,
      lossless_streets=().
    """
    ...
```

**Critical:** the synthetic abstraction must produce VALID infoset keys when used by `HUNLPoker` (so test 8 in §9.2 actually validates bucketed-key parsing on a real solver run, not just synthetic keys). Build a small but well-formed `AbstractionTables` — bucket assignments uniformly distributed across the 4/2/2 buckets, board indices consistent with PR 4's format.

If you can't construct a valid `AbstractionTables` from spec alone (because PR 4's exact constructor signature isn't visible in the spec), make a best-effort attempt and flag any signature gaps for orchestrator review. Do NOT speculate beyond what spec §9.5 + the brief specifies.

## Critical correctness items (your assertions)

### 1. Test 4 (`test_postflop_flop_solve_strategy_is_valid`) is the headline acceptance

Spec §11 #1 + §9.1 #4. Every infoset's strategy:
- `sum(probs) == pytest.approx(1.0, abs=1e-9)` — exact L1-normalization, no NaN/Inf.
- `all(0.0 <= p <= 1.0 for p in probs)` — no probs outside `[0, 1]`.
- `not any(math.isnan(p) or math.isinf(p) for p in probs)`.

If this test fails on a freshly-built implementation, the bug is in DCFR's averaging logic (which is supposed to be locked from PR 1). Flag it loudly.

### 2. Test 6 (`test_memory_profiler_matches_rss_within_10pct`) is the calibration check

Spec §11 #4 + §7.6. Without this within 10%, the per-street ratios are not trustworthy. The assertion:
```python
assert abs(report.rss_calibration_error) < 0.10
```
If Agent B's accounting is off, this fails — Agent B fixes their byte counting, not you tweaking the tolerance.

### 3. Test 10 (`test_postflop_solve_memory_budget_aborts_cleanly`) — OOM as `MemoryError`, not hard crash

Spec §11 #5 + §9.1 #10. The exception MUST carry the partial report:
```python
with pytest.raises(MemoryError) as exc_info:
    solve_hunl_postflop(config, memory_budget_gb=0.001, iterations=10)
assert len(exc_info.value.args) >= 2
report = exc_info.value.args[1]
assert isinstance(report, MemoryReport)
assert report.grand_total_bytes > 0
```

### 4. Soft assertions on intuition gauntlet

Tests 12 and 13 are "looks like poker" — they might fail even on correct implementations if the abstraction (synthetic `(4, 2, 2)`) is too coarse. Use loose bounds; document the looseness in the docstring. If the test fails, the user reviews — don't try to make the test always pass by tuning to implementation behavior.

### 5. 138+ existing tests must still pass

Run `pytest -x` after writing your tests; confirm. Your tests must not import test helpers from existing test files in a way that breaks them. Use only the public `poker_solver/__init__.py` surface plus `tests/fixtures/`.

### 6. `_parse_street_from_key` direct tests (8 + 9 + 10 in §9.2)

These test Agent B's parsing helper directly (not through a full solve). Test 8 tests bucketed format; test 9 tests lossless format; test 10 tests unknown format. Use `from poker_solver.profiler.memory import _parse_street_from_key` or `from poker_solver import _parse_street_from_key` (depends on Agent B's `__init__.py` exports — try the public `poker_solver` first, fall back to `poker_solver.profiler.memory`).

### 7. PR 4 dependency

PR 5 depends on PR 4's card abstraction being present at `poker_solver/abstraction/buckets.py`. Your `tiny_synthetic_abstraction()` fixture constructs an `AbstractionTables` directly — if PR 4 hasn't landed yet, you can't do this. **Confirm PR 4 has landed before starting** by checking the file exists. If it doesn't, stop and flag.

### 8. Determinism in tests

DCFR with the same `seed` + same config → deterministic strategy. Your tests should pass `seed=42` (or similar fixed seed) to `solve_hunl_postflop` so re-runs produce the same results. Avoid flakiness — assertions like "exploitability decreased" must be true for *every* seed, not just lucky ones; if your test passes seed-conditionally, widen the bound or use the moving-average pattern from spec §9.3.

## Spec ambiguity protocol

Per spec §10 "Edge-case allowance":
> Agent C may write tests that are correct-per-spec but reveal genuine ambiguities. If a test fails because the spec was ambiguous, **the spec is the source of truth** — we update the impl or update the spec, not silently tweak the test.

Concretely:
- If a test you wrote correctly per spec fails because Agent A or B implemented differently — flag the ambiguity in your report.
- Do NOT modify your test to match the implementation's behavior.
- Do NOT speculatively patch around the failure.
- Wait for orchestrator to reconcile.

**Spec ambiguities to anticipate:**
- Spec §5 says `iterations: int = 10_000` for `solve_hunl_postflop`; the cross-agent contract says `50_000`. Agent A is locked to `50_000`. Your tests pass explicit `iterations=N` so this doesn't matter for test correctness.
- Spec §8 fixture 2 says abstraction `(16, 8, 4)` in synthetic; spec §9.5 says `(4, 2, 2)` for the test fixture. Use `(4, 2, 2)` (the §9.5 statement wins).
- Spec §14 lists 10 deferred decisions — ALL defaults are locked per the brief. If Agent A/B implements differently, that's a bug; flag it.

## License-aware sourcing

Tests are typically not derivative work in the same way implementation is, but still:

**You may NOT copy from AGPL test suites:**
- `references/code/postflop-solver/tests/` — **AGPL v3**. Read-only inspiration; don't copy test names, test bodies, or fixture data.
- `references/code/TexasSolver/tests/` — same.

**You may model after MIT test suites:**
- `references/code/noambrown_poker_solver/` (**MIT**) — Brown's tests are a fair reference for style; cite if you adapt a fixture pattern.

**You may NOT extrapolate from training data.** If you "remember" a test for memory profiling, ground it in either the spec or the local references.

## Quality bar

- **ruff clean:** `ruff check tests/test_hunl_postflop_solve.py tests/test_memory_profiler.py tests/fixtures/hunl_solve_fixtures.py` reports zero issues.
- **black clean:** `black --check tests/test_hunl_postflop_solve.py tests/test_memory_profiler.py tests/fixtures/hunl_solve_fixtures.py` reports no changes needed.
- **mypy strict on test code: NOT required.** Existing tests aren't strictly typed; matching that is fine.
- **All 138+ existing tests still pass.** Run `pytest -x` to confirm.
- **All new tests pass** (~22 tests across the two new test files) after Agent A + Agent B land.
- **CI-friendly:** non-slow tests complete in <60s each. Slow tests marked `@pytest.mark.slow`.
- **Code size budget: ~400–600 LOC** combined across the three files. Fixture file ~100 LOC; each test file ~200–250 LOC.

## Reference-first rule

Before any test claim or assertion, check the local references. Never extrapolate from training data when a local authoritative source exists. The reference index is `/Users/ashen/Desktop/poker_solver/references/README.md` — skim it for "MDF", "overpair", "polarization", "monotone board" entries.

If you need a poker-intuition baseline (e.g., "overpair on dry board → bet"), cite `references/blog/` or `references/papers/` rather than asserting from training. The intuition gauntlet tests are SOFT — if you're unsure of a poker fact, write the assertion loose and document the looseness.

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Lint + format
ruff check tests/test_hunl_postflop_solve.py tests/test_memory_profiler.py tests/fixtures/hunl_solve_fixtures.py
black --check tests/test_hunl_postflop_solve.py tests/test_memory_profiler.py tests/fixtures/hunl_solve_fixtures.py

# 2. Confirm PR 4 prerequisite landed (AbstractionTables exists)
python -c "from poker_solver.abstraction.buckets import AbstractionTables; print('PR 4 prerequisite OK')"

# 3. Confirm Agent A + Agent B public surfaces are available (may fail until they land — that's expected)
python -c "
try:
    from poker_solver import (
        solve_hunl_postflop, HUNLSolveResult,
        MemoryReport, MemoryProbe, StreetMemoryEntry,
    )
    print('public surface OK')
except ImportError as e:
    print(f'expected if A/B not landed yet: {e}')
"

# 4. Run your new tests (after Agent A + Agent B land)
pytest tests/test_hunl_postflop_solve.py -x --tb=short -v 2>&1 | tail -40
pytest tests/test_memory_profiler.py -x --tb=short -v 2>&1 | tail -40

# 5. Run slow tests separately
pytest tests/test_hunl_postflop_solve.py -x --tb=short -v -m slow 2>&1 | tail -10

# 6. Full test suite must still pass (your tests are additive)
pytest -x 2>&1 | tail -20

# 7. Confirm fixture file is importable
python -c "
from tests.fixtures.hunl_solve_fixtures import (
    river_subgame_config, flop_dry_3size_config,
    flop_full_menu_config, monotone_flop_config,
    tiny_synthetic_abstraction,
)
abs_tables = tiny_synthetic_abstraction()
print(f'tiny abstraction built: bucket counts {abs_tables.metadata.get(\"bucket_counts\")}')
"
```

If a test fails because Agent A or B implemented differently than spec — flag the ambiguity in your report. Do NOT modify your tests.

If a test fails because Agent A or B has a bug — flag the bug in your report. Do NOT modify your tests to mask it.

If a test fails because your test has a bug — fix your test.

## Report back format

When done, write a concise report (≤300 words) covering:

1. Files created with line counts.
2. Test count breakdown (e.g., "12 in `test_hunl_postflop_solve.py`, 10 in `test_memory_profiler.py`").
3. Any spec ambiguity you flagged (and the test that surfaced it).
4. Verification command output (paste tails — especially `pytest -x` final summary).
5. Soft-assertion notes: which tests are "looks like poker" and might fail for reasons that aren't bugs.
6. Any open question you couldn't resolve from the spec / PLAN — flag for human review.
