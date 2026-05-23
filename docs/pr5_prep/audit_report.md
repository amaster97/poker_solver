# PR 5 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** `pr-5-hunl-postflop-solve` (working tree, uncommitted)
**Base:** `integration` at commit `5832b2f`

**Diff size:** 4 modified poker_solver files + 1 modified `pyproject.toml` + 3 modified pre-existing test files; 6 new files (`poker_solver/hunl_solver.py` 413 LOC, `poker_solver/profiler/memory.py` 510 LOC, `poker_solver/profiler/__init__.py` 29 LOC, `tests/test_hunl_postflop_solve.py` 495 LOC, `tests/test_memory_profiler.py` 330 LOC, `tests/fixtures/hunl_solve_fixtures.py` 275 LOC). Total ≈2,052 LOC new code; ~150 LOC delta in modified files.

**Test status:**
- `tests/test_memory_profiler.py`: 6 passed, 4 skipped (3 of the documented 6-skip set + 1 grand_total identity test that depends on the same fixture).
- `tests/test_hunl_postflop_solve.py`: 4 fast tests passed (rejection paths + river-subgame-no-abstraction); 2 skipped (TURN-coverage gap); `test_postflop_solve_warns_for_lossless_flop_start` hangs in CI (root cause: exploitability is walked on a lossless-flop tree post-solve even when `iterations=0` — see Must-fix #1).
- PR 1 (Kuhn) + PR 2 (Leduc) + PR 3 (HUNL tree) + PR 3.5 (push/fold) regression: **50 passed, 0 failed.**
- PR 3 + PR 4 abstraction tests: **38 passed, 0 failed** (9 `pytest.mark.timeout` warnings — pytest-timeout plugin not installed; benign).
- `mypy --strict poker_solver/hunl_solver.py poker_solver/profiler/`: clean (0 errors, 3 files).

---

## Must-fix

### 1. Lossless-flop end-of-solve hangs at `exploitability()` walk even with `iterations=0`.

**File:** `poker_solver/hunl_solver.py:163-167`

```python
avg = solver.average_strategy()
if log_every is None:
    # Single end-of-solve summary: compute exploitability once at the
    # end (matches spec §14 #6 "no progress bar" + Stage D).
    history.append(exploitability(game, avg))
```

After `_run_with_probe` returns (which correctly early-returns for `iterations=0` per line 348-350), the orchestrator unconditionally calls `exploitability(game, avg)` on line 167. `exploitability` walks the full game tree twice (best-response per player). For a lossless flop subgame (no abstraction), that tree is huge — `test_postflop_solve_warns_for_lossless_flop_start` (which uses `iterations=0` to early-exit) hangs in this call indefinitely.

This is verifiable: I killed the test after ~5 minutes of 100% CPU. The setup (`flop_dry_3size_config(abstraction=None)`, `HUNLPoker(config)`, `DCFRSolver(game)`, `MemoryProbe(...)`) is sub-millisecond; the only remaining suspect is the tree walk.

**Spec link:** §4 Stage D says "We compute exploitability **once at end** for fixture 2 and 3 (the memory tests)" — this presupposes a successful solve. For `iterations=0` (i.e., no work was done) computing exploitability on an empty `average_strategy` is both expensive and meaningless (the function falls back to uniform play at every infoset).

**Fix:** Guard `exploitability(game, avg)` on `avg` being non-empty AND `iterations > 0`. Mirror the `_game_value(...) if avg else 0.0` pattern already used on line 169.

```python
if log_every is None and avg and iterations > 0:
    history.append(exploitability(game, avg))
```

**Severity:** must-fix because it makes the lossless-flop warning test unreachable as written, and any user who calls `solve_hunl_postflop(config, iterations=0)` to merely validate config or capture the warning will hang on a lossless-flop config. The test's `iterations=0` design is consistent with `_run_with_probe`'s contract but is not honored by the outer function.

---

## Should-fix

### S1. `HUNLSolveResult` is `@dataclass` (mutable), not frozen. Documented but worth a sanity warning.

**File:** `poker_solver/hunl_solver.py:48-74`

```python
@dataclass
class HUNLSolveResult(SolveResult):
    ...
    memory_report: MemoryReport = field(default=None)  # type: ignore[assignment]
```

The docstring on line 57-61 explains: "Inherits SolveResult's mutability (the parent is a non-frozen dataclass; Python disallows frozen subclassing of non-frozen parents). Treat this as if it were immutable — mutation post-construction is undefined."

This is correct per the brief (PR 5 spec §14 N7 locks the subclass form), but the spec §7.2 + §11 #1 implicitly assume `MemoryReport`/result values are frozen. The decision to keep non-frozen is forced by Python and unavoidable. Recommend converting the warning into a runtime `__setattr__` guard or, at minimum, adding an explicit `mypy: ignore` lint to allow downstream code to depend on the immutability contract.

**Severity:** should-fix (developer experience; doesn't break anything).

### S2. `exploitability` is called inside `_run_with_probe` after EVERY chunk when `log_every` is set.

**File:** `poker_solver/hunl_solver.py:378-381`

```python
if log_every is not None:
    expl = exploitability(game, solver.average_strategy())
    history.append(expl)
```

Spec §4 Stage D + §12 explicitly flag that exploitability on big trees is "minutes per call." A user setting `log_every=100` on a flop-start tree will pay this cost ~100 times in a 10k-iter solve. The current impl does not warn or document this trade-off. Consider:
- Logging a `logger.info` at first call estimating the cost, OR
- Documenting in the docstring (lines 105-107) that `log_every` triggers per-chunk exploitability and may be expensive.

**Severity:** should-fix.

### S3. `_run_with_probe` does not honor `seed` for snapshot ordering.

**File:** `poker_solver/hunl_solver.py:147-150`

```python
extra_kwargs: dict[str, Any] = dict(dcfr_kwargs or {})
if seed is not None and "seed" not in extra_kwargs:
    extra_kwargs["seed"] = seed
solver = DCFRSolver(game, **extra_kwargs)
```

Seed is threaded into `DCFRSolver`, good. However, `MemoryProbe.snapshot()` iterates `solver.infosets.items()` — Python's dict iteration is insertion-ordered, which is deterministic as long as DCFR populates the dict deterministically. Spec §11 #10 asserts "Deterministic re-runs. Same seed, same config, same abstraction → identical strategy table within float tolerance." There is no test verifying this (no `test_solve_is_deterministic_under_seed`). Recommend adding one.

**Severity:** should-fix (test hole, not impl bug).

### S4. The 6 documented skips include test_postflop_flop_solve_runs_without_crashing AND test_postflop_flop_solve_strategy_is_valid, which together comprise spec §11 critical-correctness items #1 and #3.

**File:** `tests/test_hunl_postflop_solve.py:164-225`

Spec §11 lists:
- #1 "First HUNL solve produces a valid strategy" → `test_postflop_flop_solve_strategy_is_valid` (skipped)
- #3 "The solver works WITH PR 4's card abstraction on the flop subgame" → `test_postflop_flop_solve_runs_without_crashing` (skipped)

The skip reason cites a TURN coverage gap in PR 4's `(4, 2, 2)` synthetic artifact ("lookup_bucket raises AND lossless fallback hangs"). The brief flags this as a PR 4 abstraction issue, not a PR 5 bug. **The 6-test skip set is acceptable** *only if* the user accepts that:

1. PR 5's most important integration tests (#1 and #3 in spec §11) are deferred to a future PR (PR 6 Rust or a fixture redesign), and
2. The headline "strategy validity" check (#1) — which would catch DCFR averaging bugs, NaN/Inf leaks, and L1-normalization regressions — is not covered by any other test in PR 5.

Recommend before commit: either (a) add a smaller fixture that exercises a complete `(flop, turn, river)` traversal under a minimal abstraction, OR (b) reword the spec §11 #1/#3 entries to accept the deferral and update the "Success criteria" §16 ("All new tests pass") to acknowledge skips.

**Severity:** should-fix (test holes documented in spec must-have list).

### S5. `MemoryReport.iterations_at_snapshot` from `solver.iteration` but DCFR may report differently than expected.

**File:** `poker_solver/profiler/memory.py:459`

```python
iterations_at_snapshot=int(self._solver.iteration),
```

Spec §7.2 defines `iterations_at_snapshot: int`. `DCFRSolver.iteration` is the cumulative iteration counter. If the solver runs 100 iters then 50 more (multiple `solve()` calls), `iteration == 150`. Spec is silent on whether this is the total-since-construction or last-chunk count. Likely the former. Recommend a docstring clarification on the `MemoryReport` field (currently the docstring only describes the meaning at line 459).

**Severity:** should-fix.

### S6. `MemoryProbe.measure_per_street(dcfr_solver)` alias is undocumented in spec.

**File:** `poker_solver/profiler/memory.py:464-483`

Spec §6/§7.1 only mention `snapshot()`. `measure_per_street(...)` is an alias added for an unspecified "cross-agent contract from the orchestrator brief" (per the docstring line 466-467). If this isn't in PR 5 spec, it shouldn't be in the public surface — either remove or document.

**Severity:** should-fix.

### S7. CLI flag `--abstraction` from PR 4 not threaded into `solve_hunl_postflop` from CLI.

**File:** `poker_solver/cli.py:222-251` (`_cmd_solve` HUNL postflop branch)

The CLI builds `config = _build_postflop_config(args)` (line 122-141) and calls `solve_hunl_postflop(game.config, ...)`. There is **no path** in `_build_postflop_config` to attach an `--abstraction PATH` (PR 4's artifact) from the CLI to the config. Spec §6 lists `--abstraction PATH (carried over from PR 4)` as a flag scoped to `--hunl-mode postflop`. The argparse setup (lines 348-415) doesn't add `--abstraction`. This means the CLI-driven "Fixture 2 shape" success criterion in spec §16 cannot be invoked from the command line as written:

> `poker-solver solve --game hunl --hunl-mode postflop --board "As 7c 2d" --stacks 100 --abstraction /path/to/abstraction.npz ...`

**Severity:** should-fix (success criterion in §16 unreachable; programmatic call works).

---

## Nice-to-fix

### N1. `_install_in_memory_resolver_shim` monkey-patches `poker_solver.abstraction.buckets._cached_load` globally.

**File:** `poker_solver/hunl_solver.py:293-314`

The shim is process-global. The flag `_resolver_shim_installed` prevents re-install. Documented in the docstring (line 294: "exactly once per process") — this is fine for tests but means a library caller cannot reliably uninstall the shim after the solve is done. Consider making the shim opt-out via a context manager, or document that it's permanent.

### N2. `_DICT_OVERHEAD_RATIO = 0.5` is a magic constant.

**File:** `poker_solver/profiler/memory.py:53`

Spec §7.4 documents "Python's dict overhead (~50% slack ... rough heuristic)" but the constant could live in the module-level docstring more visibly. Per-interpreter calibration could drift.

### N3. `_ = np` on line 510 to suppress unused-import linting is awkward.

**File:** `poker_solver/profiler/memory.py:508-510`

Either use `np` somewhere (e.g., assert on `ndarray.nbytes`) or remove the import.

### N4. CLI's `_print_memory_section` uses `getattr(report, "...", default)` instead of accessing typed attributes.

**File:** `poker_solver/cli.py:283-303`

The defensive `getattr` pattern with defaults (`0.0`, `()`) is documented as "so we don't take a direct dependency on a specific dataclass shape from inside CLI code that may be imported by users without psutil installed" (lines 279-281). Since `psutil>=5.9` is now a hard runtime dep (pyproject.toml), this defensive pattern is no longer needed.

### N5. `Note:` on line 507-509 about `numpy is imported but not directly referenced` should just be deleted.

If numpy isn't used, drop the import. (See N3.)

---

## Looks good (explicit confirmation of audit focus areas)

### 1. Memory budget enforcement.

**Verified:** `poker_solver/hunl_solver.py:365-376`. After each chunk's snapshot, `final_report.total_gb` is compared against `memory_budget_gb`; over budget raises `MemoryError(<msg>, final_report)`. The error message includes:
- Current memory in GB
- Budget in GB
- Iteration count
- River ratio (a `format` percentage)
- Actionable suggestion: "tighten the abstraction (smaller bucket counts via `precompute-abstraction --bucket-counts ...`) or restricting --bet-sizes"
- Note that the partial report is in `args[1]`

The check fires **between chunks** (line 359 `solver.solve(step)` → line 364 `final_report = probe.snapshot()`), not inside the CFR recursion. Matches spec §4 Stage C.

`test_postflop_solve_memory_budget_aborts_cleanly` (`tests/test_hunl_postflop_solve.py:326-348`) exists and asserts `len(exc_info.value.args) >= 2` and `isinstance(args[1], MemoryReport)` and `grand_total_bytes > 0`. **Note:** this test is in the 6-skip set due to the TURN coverage gap, so it does not actually run in CI; the OOM abort path is implemented but un-exercised by an integration test.

### 2. `MemoryReport.river_ratio` reports the right number.

**Verified:** `poker_solver/profiler/memory.py:126-144`. Formula is `_solver_array_bytes_for(Street.RIVER) / solver_arrays_total_bytes`. The denominator is `solver_arrays_total_bytes` (NOT `grand_total_bytes`), matching spec §8.5 "ratio of total **solver arrays**, NOT total grand bytes including abstraction table + overhead." The numerator excludes per-infoset `other_bytes` (overhead) so numerator and denominator are on the same "arrays-only" basis. Docstring (lines 127-138) documents the three PLAN.md zones (<30% / 30-50% / >50%). Returns 0.0 on empty solver to avoid div-by-zero.

### 3. OOM is caught and reported cleanly (NOT a hard crash).

**Verified:** `poker_solver/hunl_solver.py:367-376`. Raises `MemoryError` (not `RuntimeError`), partial report in `args[1]`. CLI path (`poker_solver/cli.py:243-251`) catches `MemoryError as exc`, prints the partial report via `_print_memory_section(exc.args[1], stream=sys.stderr)`, exits with code 1. Programmatic callers can `try / except MemoryError as e: report = e.args[1]`.

### 4. Intuition gauntlet: at least one MDF and one polarization test.

**Verified:** `tests/test_hunl_postflop_solve.py:387-495`. Two tests:
- `test_postflop_solve_intuition_gauntlet_dry_overpair_bets` (line 387) — "MDF-shape" check: P0 with overpair on dry As-7c-2d flop should assign >50% to BET actions. Soft assertion.
- `test_postflop_solve_intuition_gauntlet_polarization_on_monotone` (line 454) — Polarization: monotone 8h-7h-6h flop with KcKs should produce `max(probs) > 0.6` OR `min(probs) < 0.05` for non-fold actions. Soft assertion.

Both are spec §9.1 #12 + §9.4. Neither is in the skip set; both rely on the tiny synthetic abstraction.

### 5. `psutil` calibration check within 10%.

**Verified at API level:** `poker_solver/profiler/memory.py:147-160` defines `rss_calibration_error` as `|predicted - actual| / actual` where `actual = rss_observed - rss_baseline` and `predicted = solver_arrays + other_overhead`. Baseline is captured at probe construction (line 386). Returns 0.0 on `actual <= 0` (defensive against cold-start where baseline > observed).

**Test runtime status:** `test_memory_profiler_matches_rss_within_10pct` (line 238) is in the 6-skip set due to TURN coverage gap, so the calibration assertion is **not** exercised in CI. This is a meaningful coverage gap — the spec §11 #4 "memory profiler reports match psutil RSS within 10%" critical correctness check is implemented but unverified.

### 6. Infoset-key parsing handles both formats.

**Verified:** `poker_solver/profiler/memory.py:182-214` (`_parse_street_from_key`). Bucketed: first token starts with `b` + digit suffix → street at parts[1]. Lossless: street at parts[2]. Unknown tokens → `None`. Tests 8, 9, 10 in `tests/test_memory_profiler.py:288-326` all pass (verified locally) and cover bucketed (`"b3|f|x"`), lossless (`"AhKh|7d2c9h|f|xx"`), preflop lossless (`"AhKh||p|"`), and malformed (`"not_a_real_key"`, `"AhKh|7d2c9h|z|xx"` → returns `None`).

### 7. Dispatch composition (Stage A validation + `solver.py` routing).

**Verified:** `poker_solver/solver.py:51-82`. The dispatch order is:
1. (lines 51-65) Push/fold short-circuit: only if `starting_street == Street.PREFLOP` AND `is_pushfold_mode(starting_stack, big_blind)`. Fires before postflop.
2. (lines 71-82) Postflop branch: if `Street.FLOP <= starting_street < Street.SHOWDOWN`, routes to `solve_hunl_postflop`.
3. (lines 83+) Fallback to `_solve_rust` / Python DCFR.

**Spec tension flagged:** The audit prompt + spec §6 amendment claim "FLOP-start at 1500 stack still hits the chart." The implementation does NOT do this — push/fold's guard requires `starting_street == Street.PREFLOP`. This is logically correct because `solve_pushfold` returns a preflop chart strategy; applying it to a flop-start config would be wrong. The spec language is contradictory; the impl chooses the sensible behavior. Recommend the spec §6 wording be corrected in a future amendment (the dispatch is correct as-coded).

`_validate_postflop_config` (lines 181-217) rejects PREFLOP with the exact spec message ("solve_hunl_postflop is postflop-only; preflop solver lands in PR 9. Use Street.FLOP / TURN / RIVER..."). Tested at `tests/test_hunl_postflop_solve.py:230-235`. Board length / rake checks: lines 198-217. All tested.

### 8. `HUNLSolveResult` is a SUBCLASS of `SolveResult`.

**Verified:** `poker_solver/hunl_solver.py:48-74`. `class HUNLSolveResult(SolveResult)` inherits all parent fields and adds `memory_report: MemoryReport`. Tests at `tests/test_hunl_postflop_solve.py:136-137` assert both `isinstance(result, HUNLSolveResult)` and `isinstance(result, SolveResult)`.

**Caveat:** non-frozen, per the docstring comment on line 57-61. Python's dataclass machinery refuses `@dataclass(frozen=True)` on a subclass of a non-frozen dataclass (`SolveResult` is non-frozen — see `poker_solver/solver.py:20`). This is the documented reason for the deviation from spec §11's implicit immutability. Acceptable per the brief context (locked decision).

### 9. Hyperparameters unchanged.

**Verified:** No CLI flag for `--alpha` / `--beta` / `--gamma` in `cli.py`. `DCFRSolver(game, **extra_kwargs)` (`hunl_solver.py:150`) is called without explicit alpha/beta/gamma, so it uses `dcfr.py`'s defaults (α=1.5, β=0, γ=2.0 per PLAN.md). `dcfr_kwargs` parameter is reserved for future override but is empty in normal usage. `git diff 5832b2f -- poker_solver/dcfr.py` returns no changes — `dcfr.py` is unmodified.

### 10. `hunl.py` is NOT modified by PR 5.

**Verified:** `git diff 5832b2f -- poker_solver/hunl.py` returns no changes. The `HUNLConfig.abstraction` field is consumed via `replace(config, abstraction=ref)` (line 266 of hunl_solver.py); no schema change.

### 11. `psutil` is the only new dependency.

**Verified:** `pyproject.toml` diff:
```
-dependencies = ["numpy>=1.24"]
+dependencies = ["numpy>=1.24", "psutil>=5.9"]
```
Only `psutil>=5.9` added to runtime deps. Dev deps gained `pytest-timeout>=2.3` (the test files use `@pytest.mark.timeout(...)` markers — currently emitting "unknown mark" warnings because pytest-timeout isn't installed in the local dev env, but this is opt-in dev tooling, not a runtime dep). `psutil` is MIT-licensed, cross-platform, mature. Justification matches spec §6.

### 12. Determinism + reproducibility.

**Partially verified:** Seed is threaded through DCFR via `extra_kwargs["seed"] = seed` (line 148-149). Profiler iterates `solver.infosets.items()` (Python dict insertion-ordered → deterministic). `per_street` tuple is materialized in a fixed order `(FLOP, TURN, RIVER, SHOWDOWN)` (`profiler/memory.py:410-413`). **No test exercises this end-to-end** (spec §11 #10 "same seed → identical strategy" has no corresponding test). See S3 above.

### 13. `solver.solve()` regression check.

**Verified:**
- PR 1 (Kuhn) + PR 2 (Leduc): `tests/test_dcfr_core.py`, `tests/test_leduc_core.py` — all pass.
- PR 3 (HUNL tree): `tests/test_hunl_core.py`, `tests/test_hunl_tree.py` — all pass.
- PR 3.5 (push/fold): `tests/test_pushfold.py` — all pass.
- PR 4 (abstraction): `tests/test_abstraction_buckets.py`, `tests/test_abstraction_emd.py` — all pass.

Total: 88 pre-existing tests pass with the routing branch + re-exports added. The `full` HUNL mode now points at PR 9 (was PR 5), tested via the rejection error message in `cli.py:90-93`.

---

## Spec coverage gaps (missing tests)

### G1. Spec §11 #1 (strategy validity: sums to 1, no NaN, no Inf) — implemented but **skipped** in CI.

`test_postflop_flop_solve_strategy_is_valid` (line 196) is in the 6-skip set. There is no smaller fallback test that asserts strategy validity on a successfully-solved fixture (the river-only smoke test at line 142 doesn't assert these invariants). **Recommendation:** add `test_postflop_river_subgame_strategy_is_valid` that runs on Fixture 1 (river-only, no abstraction) — that fixture solves in <1s and exercises the same DCFR averaging path.

### G2. Spec §11 #4 (psutil calibration <10%) — implemented but **skipped** in CI.

`test_memory_profiler_matches_rss_within_10pct` is in the 6-skip set. **Recommendation:** add a smaller calibration test on the river-only fixture. Solver-array bytes will be smaller, so the 10% tolerance is less meaningful, but a 20-50% bound on a 50-iter river solve would still catch egregious mis-counting bugs.

### G3. Spec §11 #5 (OOM abort path) — implemented but **skipped** in CI.

`test_postflop_solve_memory_budget_aborts_cleanly` is in the 6-skip set. **Recommendation:** OR-fold this test with the river-only fixture instead of Fixture 2 — set `memory_budget_gb=0.000001` so even the tiny river solver allocations exceed the budget. Currently the OOM path is implemented but never exercised by an integration test (only by the test-fixture-dependent skip).

### G4. Spec §11 #10 (deterministic re-runs) — no test.

Spec lists this as a critical correctness item but there is no `test_solve_is_deterministic_under_seed` in either test file. **Recommendation:** add one — run Fixture 1 twice with `seed=42`, assert strategy tables are equal within 1e-12.

### G5. Spec §9.3 (convergence smoke chain "moving-average of last 5 < moving-average of first 5") — not implemented.

`test_postflop_solve_log_every_records_history` (line 354) uses a simpler "final < quartile-point * 1.5" check. The spec §9.3 moving-average pattern is not coded anywhere. **Recommendation:** either align the test with the spec, or update the spec to match the simpler check.

### G6. Spec §9.5 fixture `tiny_synthetic_abstraction()` returns an `AbstractionTables` (in-memory only).

The fixture file (line 214-228) exposes `tiny_synthetic_abstraction()` returning the in-memory tables AND `tiny_synthetic_abstraction_ref()` returning an `AbstractionRef`. Spec §9.5 only mentions `tiny_synthetic_abstraction()`. The `_ref()` variant is implementation-driven (needed because `HUNLConfig.abstraction` field is typed `AbstractionRef | None`, NOT `AbstractionTables`). Document this in the spec or strip the unused `tiny_synthetic_abstraction()` export.

---

## License compliance

**No AGPL contamination detected.**

- `poker_solver/profiler/memory.py:1-23` — module docstring: "Pattern (compute total memory by summing every backing buffer's bytes) is inspired architecturally by postflop-solver's memory_usage() (AGPL — read-only). No code copied; implementation derived from first principles per spec §7..."
- `poker_solver/hunl_solver.py:24-25` — docstring: "Architecturally inspired by `noambrown_poker_solver` (MIT) two-tier solver orchestration; no code copied."
- Implementation patterns inspected:
  - `_compute_street_entries` (memory.py:228-311) is a Python-native per-key accumulator over a dict — no relation to postflop-solver's Rust `Vec<T>` walks at `references/code/postflop-solver/src/utility.rs:56`.
  - The compressed-vs-uncompressed dichotomy in postflop-solver is explicitly **not adopted** (no `compressed_bytes` field anywhere in PR 5).
  - `_abstraction_table_bytes` (memory.py:314-338) sums NumPy `nbytes` + `sys.getsizeof(dict)` headers — standard Python introspection, not lifted from any reference.

Both license attributions are at the top of their respective module docstrings. Recommend adding the same attribution at the top of `poker_solver/hunl_solver.py`'s docstring on the noambrown source URL for completeness (currently the docstring just names it).

---

## Overall verdict

**READY for commit AFTER must-fix #1 resolved.**

The PR 5 implementation is structurally sound: dispatch composition is correct (with one spec/impl mismatch in the spec wording, which the implementation handles sensibly), memory profiler interface matches spec §6/§7, OOM abort path is implemented per §7.7, and hyperparameters/license attributions are clean. The 6-test skip set is documented as a PR 4 fixture-coverage gap (not a PR 5 bug) and is acceptable for the working tree if the user accepts that spec §11 critical-correctness items #1, #3, #4, and #5 are **implemented but not actually exercised in CI**. If the orchestrator wants those covered before commit, add the smaller-fixture fallbacks recommended in G1, G2, G3.

Must-fix #1 (lossless-flop exploitability hang on `iterations=0`) is a real bug — the test `test_postflop_solve_warns_for_lossless_flop_start` will hang in CI as written, blocking the test run. The two-line guard on `hunl_solver.py:164-167` resolves it.

The 6-test skip set is acceptable on the merits (PR 4 coverage gap, not a PR 5 defect). **However,** if the user wants spec §11 critical-correctness items #1/#3/#4/#5 exercised in CI before commit, treat G1-G3 as additional pre-commit work. If the user accepts the coverage delegation to PR 6 (Rust) or a future PR 4 fixture revisit, the skip set as-currently-documented is fine.
