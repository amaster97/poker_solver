# PR #20 — `test_leduc_diff.py` CI Failure Diagnosis

**Date:** 2026-05-26
**Branch:** `pr-64-cross-platform-ci-matrix` (PR #20 — "feat(ci): cross-platform CI matrix for v1.8 prep")
**Author:** investigation agent
**Constraint:** read-only diagnosis; no CI fix pushed; no test or Rust SIMD code modified

---

## TL;DR

**Both `ubuntu-22.04 x86_64` AND `macos-14 aarch64` jobs hit the 30-min job cap, cancelled in the same step (`Pytest smoke (fast tier)`) before pytest could print tracebacks. The Linux-x86_64 framing is a red herring — the failure is platform-agnostic.**

Root cause is almost certainly **HYPOTHESIS A (slow Python DCFR + insufficient CI timeout headroom)**, specifically:

- `tests/test_leduc_diff.py` runs `solve(LeducPoker(), iterations=2000, backend="python", ...)` in a module-scoped fixture.
- Local measurement (M-series arm64 native): **139.9s** for the Python leg alone.
- On a 2-core GitHub-hosted runner (slower, no Apple Silicon advantage), this likely takes 200–400s.
- The workflow runs `pytest -m "not slow" --timeout=120`. The per-test marker `@pytest.mark.timeout(300)` overrides `--timeout=120` for `test_leduc_diff.py` (verified in `pytest_timeout._get_item_settings`), so each of its 5 tests gets 300s.
- If the fixture's Python leg exceeds 300s on the CI runner, fixture setup is killed → first test errors → fixture is NOT retried but all 5 tests in the module request it → **EEEEE** cascade as reported.
- Total wall time (494 collected tests + the Leduc diff fixture timeout × however-many retries the runner needed) blows past the **30-min job `timeout-minutes: 30`** cap → both jobs CANCELLED.

The macos-13 job is still queued (didn't start before the cap), so we have no third data point yet.

---

## 1. Test file analysis (`tests/test_leduc_diff.py`)

- **5 tests** in the module, all depending on a single `@pytest.fixture(scope="module") both_results`.
- Fixture body:
  ```python
  py = solve(game, iterations=2000, backend="python", alpha=1.5, beta=0.0, gamma=2.0)
  rs = solve(game, iterations=2000, backend="rust",   alpha=1.5, beta=0.0, gamma=2.0)
  ```
- Each test decorated with `@pytest.mark.timeout(300)`; `_LEDUC_DIFF_TIMEOUT = 300`.
- Module docstring explicitly notes the timeout is bumped to 300 because pytest-timeout doesn't apply to module-scoped fixtures' separate setup phase; "Observed ~140s on x86_64 Python under Rosetta (Python baseline leg dominates; Rust leg is ~18s)."
- **NOT** marked `slow` → IS collected by `pytest -m "not slow"`.

## 2. Local pytest result on macOS (M-series arm64)

```
pytest tests/test_leduc_diff.py -xvs --timeout=300 2>&1 | tail -50
...
E   ImportError: dlopen(.../poker_solver/_rust.cpython-313-darwin.so) (mach-o file,
    but is an incompatible architecture (have 'arm64', need 'x86_64'))
...
ERROR tests/test_leduc_diff.py::test_leduc_python_rust_infoset_keys_match
1 error in 274.84s (0:04:34)
```

- Local test took **274.84 s** of wall-clock before erroring on the Rust dlopen step (the Python leg ran successfully first, then the Rust import crashed). My local Python is universal2 but pytest was invoked under x86_64-Rosetta mode (via pyenv shim); the `.so` is native arm64.
- **This is the well-known [`.so` arch mismatch hazard](feedback_dotso_arch_check.md) from MEMORY.md**, NOT the CI failure. It's an unrelated host-config issue.
- **Critically**: the Python leg completing in ~270s under Rosetta (or ~140s native, verified separately below) confirms the Python baseline is the time-dominant component.

### Cross-check: Python leg alone, native arm64

```
arch -arm64 python3 -c "from poker_solver import LeducPoker, solve; ...
  solve(LeducPoker(), iterations=2000, backend='python', alpha=1.5, beta=0.0, gamma=2.0)"
→ Python Leduc 2000 iter: 139.9s  game_value=-0.0855
```

So docstring's "~140s" claim matches native arm64. On x86_64 GHA runners (slower CPU, possibly under contention), 200–400s is reasonable.

## 3. CI workflow inspection (`.github/workflows/ci.yml` on branch `pr-64-cross-platform-ci-matrix`)

```yaml
runs-on: ${{ matrix.os }}     # macos-14, macos-13, ubuntu-22.04
timeout-minutes: 30           # JOB cap

steps:
  - Setup Rust / Python / venv
  - maturin develop --release --target ${{ matrix.target }}
  - cargo test --lib --release --target ${{ matrix.target }}   # SUCCEEDED on both
  - pytest -m "not slow" --timeout=120                          # CANCELLED on both
  - cargo test ... -p cfr_core simd::tests                      # SKIPPED (job died)
```

**Key facts:**

- `--timeout=120` is the workflow flag; this is **per-test** (pytest-timeout terminology — it covers setup+call+teardown for that one test, with `func_only=False`).
- `pyproject.toml` `[tool.pytest.ini_options]` sets default `timeout = 90`.
- Per-test `@pytest.mark.timeout(300)` **wins** over both the workflow `--timeout=120` and the ini `90` (verified in `pytest_timeout._get_item_settings`).
- **Job cap is 30 min.** Even if every test in `test_leduc_diff.py` got its full 300s, that's 25 min just for this file, leaving 5 min for the other 489 tests.
- **NOT** marked slow → runs in the smoke tier.

## 4. Rust code search (HYPOTHESIS B & C check)

```
grep 'is_x86_feature_detected' crates/cfr_core/src/simd.rs    # many hits
grep '#[cfg(target_arch = "x86_64")]'  crates/cfr_core/src/simd.rs    # many hits
```

- AVX2 dispatch is guarded by both `#[cfg(target_arch = "x86_64")]` (compile-time) AND `is_x86_feature_detected!("avx2")` (runtime). PR #35's AVX2 runtime-detect path. Falls back to SSE2 or scalar otherwise.
- **However**: `Cargo unit tests` step (which includes `simd::tests::*` in lib tests) **SUCCEEDED on both ubuntu-22.04 and macos-14** in the failed CI run. So the AVX2 path is not crashing in cargo's harness.
- `Cargo.toml`: no platform-specific dependencies, no `[target.'cfg(...)']` sections that would break manylinux2014.
- The PyO3 `.so` was successfully built and loaded by `cargo test --lib` (which uses `auto-initialize`). Manylinux is not in the picture — CI uses `maturin develop` directly on each runner, no pre-built wheel.

→ HYPOTHESIS B (AVX2 crash) and HYPOTHESIS C (manylinux load failure) are **strongly disconfirmed** by the per-step pass/fail breakdown.

## 5. Hypothesis ranking

| # | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| **A** | `pytest --timeout=120` workflow flag inadequate; per-test marker (300s) and Python DCFR runtime push fixture past timeout on slow CI runner → fixture errors → EEEEE cascade → 30-min job cap blown | **MOST LIKELY** (~85%) | Python leg = 140s native arm64 / 270s Rosetta locally; CI runners slower; macos-14 AND ubuntu-22.04 both cancelled identically; failure is in pytest step; cargo step passed |
| B | AVX2 runtime-detect path on Linux x86_64 panics/segfaults | **DISCONFIRMED** (~3%) | `cargo test --lib` ran simd::tests cleanly on ubuntu-22.04; also macos-14 (aarch64) has no AVX2 yet cancelled identically |
| C | PyO3/maturin manylinux .so load failure on Linux | **DISCONFIRMED** (~2%) | `maturin develop` step succeeded; `cargo test --lib` linked + ran fine; macos jobs failed identically (not Linux-specific) |
| D | Something else: e.g., a different test (not `test_leduc_diff.py`) hangs indefinitely with no timeout enforcement; pytest-timeout SIGALRM-based killer doesn't fire on a non-Python blocking syscall (e.g. Rust panic-unwind, BLAS thread); pytest-asyncio `auto` mode hang on async fixtures; cumulative smoke-tier serial runtime simply exceeds 30 min | **PLAUSIBLE BACKGROUND** (~10%) | Other DCFR/diff tests (`test_dcfr_diff`, `test_exploit_diff`, `test_hunl_diff`, `test_preflop_diff`, `test_leduc_dcfr`) also do heavy iteration. 494 serial tests on a 2-core x86_64 runner could plausibly exceed 30 min without any single one timing out. EEEEE specifically points at test_leduc_diff, but the *cancellation* may have been caused upstream and the EEEEE was from an earlier run state |

## 6. Caveat — about the "EEEEE" sighting

The CURRENT run (id `26435671490`) is still in progress at the time of writing and shows only step-level CANCELLED, no per-file `EEEEE` in the harvestable log. The user's `tests/test_leduc_diff.py EEEEE` quote may be from an **earlier failed run** on the same branch, or scraped from the live in-progress stream before it timed out. Once the run finishes, `gh run view --log-failed --job=77817849758` should reveal the exact pytest output. **If the EEEEE turns up specifically at `test_leduc_diff.py`, that is the smoking gun for Hypothesis A.**

## 7. Recommended one-line next step for the morning

**Disambiguate Hypothesis A vs D in one shot — split the slow diff tests into their own job with a longer pytest timeout and the original smoke job keeps `--timeout=120`:**

In `.github/workflows/ci.yml`, change the `Pytest smoke (fast tier)` step to deselect the heavy diff tests, and add a second step that runs them with `--timeout=600`:

```yaml
- name: Pytest smoke (fast tier — excluding heavy diff tests)
  run: pytest -m "not slow" --timeout=120 --deselect tests/test_leduc_diff.py --deselect tests/test_dcfr_diff.py --deselect tests/test_exploit_diff.py --deselect tests/test_hunl_diff.py --deselect tests/test_preflop_diff.py

- name: Pytest heavy diff tests (longer timeout)
  run: pytest tests/test_leduc_diff.py tests/test_dcfr_diff.py tests/test_exploit_diff.py tests/test_hunl_diff.py tests/test_preflop_diff.py --timeout=600
```

**Why this disambiguates:**
- If the heavy diff step **passes cleanly** → Hypothesis A confirmed (slow Python DCFR + insufficient timeout was the only issue).
- If the heavy diff step **also times out at 30 min** → Hypothesis D (cumulative serial runtime) or a hang in one specific test → grep its stdout for the offender, which will now be visible because the smoke step won't have eaten the 30-min budget.
- The smoke step's pytest-timeout=120 is preserved, so any newly-introduced slow test in the wider 494-test set will surface its own timeout failure with a clear stacktrace.

**One-liner if you want minimum diff (less informative but quicker):**

> Add `timeout-minutes: 60` to the matrix job AND bump `--timeout=300` on the pytest command.

This gives the smoke tier 60 min of wall and 300s per test (matching the in-file marker). If it then succeeds, Hypothesis A confirmed; if it still times out at 60 min, the issue is broader than this one file (Hypothesis D).

---

## 8. Files touched / referenced

- Read: `/Users/ashen/Desktop/poker_solver/tests/test_leduc_diff.py`
- Read: `/Users/ashen/Desktop/poker_solver/pyproject.toml` (lines 59-73)
- Read: `/Users/ashen/Desktop/poker_solver/tests/conftest.py`
- Read: `/Users/ashen/Desktop/poker_solver/crates/cfr_core/Cargo.toml`
- Read: `/Users/ashen/Desktop/poker_solver/.github/workflows/golden_check.yml` (sanity)
- Read: `/Users/ashen/Desktop/poker_solver/.github/workflows/release.yml` (sanity)
- Read (via `git show origin/pr-64-cross-platform-ci-matrix:.github/workflows/ci.yml`): the PR-20-only workflow
- Read: `/Users/ashen/Library/Python/3.13/lib/python/site-packages/pytest_timeout.py` (precedence rules)
- Ran: `pytest tests/test_leduc_diff.py -xvs --timeout=300` locally (failed on Rust dlopen at 274.84s — pre-existing host arch issue, not CI)
- Ran: `arch -arm64 python3 -c "...solve(LeducPoker(), iterations=2000, backend='python', ...)"` → 139.9s native arm64
- Ran: `gh run view 26435671490` and `--job=77817849742` / `77817849758` to confirm step-level cancellation
- **Did NOT push**, did NOT modify any test or Rust source.

---

## 9. Side note: pre-existing host arch issue worth noting

The user's local arm64 macOS runs pytest under x86_64 Rosetta (pyenv shim selects x86_64). When running `pytest tests/test_leduc_diff.py`, the Python leg succeeds under Rosetta but the Rust `.so` is native arm64, causing `dlopen ... 'have arm64, need x86_64'`. To run tests locally cleanly, either:

```sh
arch -arm64 pytest tests/test_leduc_diff.py -xvs --timeout=300
```

…or rebuild the `.so` for x86_64. This is **outside the scope of PR #20** — it's a separate host-config issue documented in MEMORY.md `feedback_dotso_arch_check.md`.
