# Test Wave Verification — 2026-05-23 (post-integration)

**Working tree:** `/Users/ashen/Desktop/poker_solver`
**Local diff vs HEAD (`9a2a89e`):** `CHANGELOG.md`, `README.md`, `pyproject.toml`,
`scripts/build_macos_dmg.sh`, `scripts/poker_solver.spec` (+ untracked docs)
**Verdict:** **SOME-FAILURES** — none traceable to this wave's edits.

---

## Command-by-command results

### 1. `ruff check poker_solver/ tests/` — **FAIL (pre-existing)**

```
UP037 [*] Remove quotes from type annotation
  --> poker_solver/range.py:47:27
   |
47 |     def diff(self, other: "Range") -> "Range":
   |                           ^^^^^^^

UP037 [*] Remove quotes from type annotation
  --> poker_solver/range.py:47:39
   |
47 |     def diff(self, other: "Range") -> "Range":
   |                                       ^^^^^^^

Found 2 errors.
[*] 2 fixable with the `--fix` option.
```

- File `poker_solver/range.py` is **NOT in this wave's diff** (`git diff --stat`
  shows only CHANGELOG/README/pyproject/build_macos_dmg.sh/poker_solver.spec).
- This is pre-existing lint debt — not introduced by this wave.

### 2. `ruff format --check poker_solver/ tests/` — **FAIL (pre-existing)**

17 files would be reformatted:
```
poker_solver/abstraction/buckets.py
poker_solver/abstraction/equity_features.py
poker_solver/abstraction/precompute.py
poker_solver/cli.py
poker_solver/hunl.py
tests/test_abstraction_emd.py
tests/test_abstraction_integration.py
tests/test_dcfr_diff.py
tests/test_exploit_diff.py
tests/test_hunl_diff.py
tests/test_hunl_postflop_solve.py
tests/test_leduc_diff.py
tests/test_library.py
tests/test_library_cli.py
tests/test_pushfold.py
tests/test_river_diff.py
tests/test_river_diff_self_sanity.py
17 files would be reformatted, 51 files already formatted
```

- **None of these files are in this wave's diff.** Pre-existing format debt.

### 3. `pytest -x --timeout=60 -m "not slow and not very_slow" tests/` — **FAIL (pre-existing fixture timeout)**

- 215 passed, 6 skipped, 23 deselected, 1 xfailed, **1 error**, 2 warnings.
- Runtime 404.17s, halted by `-x` after the first error.
- Failing test: `tests/test_leduc_dcfr.py::test_leduc_converges_below_threshold`
- Error type: `Failed: Timeout (>60.0s) from pytest-timeout` raised inside the
  module-scoped fixture `leduc_run = solve(LeducPoker(), 600)`.
- Excerpt (line numbers + traceback in raw output):
  ```
  poker_solver/dcfr.py:268: in solve
      solver.solve(step)
  ...
  poker_solver/dcfr.py:220: in _cfr
      action_values[idx] = self._cfr(...)
  ...
  dataclasses.py:1623: Failed
  E               Failed: Timeout (>60.0s) from pytest-timeout.
  ```
- `tests/test_leduc_dcfr.py` was last touched in `dc8db4c` ("PR 6 follow-up:
  Leduc test timeout hardening"). `poker_solver/dcfr.py`, `games.py`, and
  `solver.py` were last touched at `117a953` (PR 21) or earlier. **None of
  these files are in this wave's diff.** This is a pre-existing test-discipline
  issue (the fixture is heavier than the 60s default timeout and is not
  marked `slow`).

### 4. `cargo test --all --release` — **FAIL (pre-existing PyO3 embed issue)**

- 50/50 unit tests pass (`cfr_core` lib unittests).
- 19/19 `hunl_state_unit` integration tests pass.
- **4/13 fail in `crates/cfr_core/tests/test_hunl_rust.rs`** — all on PyO3
  embed-Python failures:
  ```
  test_abstraction_canonicalization_matches_python ... FAILED
  test_hunl_strength_eval_matches_python          ... FAILED
  test_hunl_infoset_key_lossless_format            ... FAILED
  test_hunl_infoset_key_bucketed_format            ... FAILED
  ```
  Root cause (identical for first 3):
  ```
  ImportError: cannot import name 'Street' from partially initialized module
  'poker_solver.hunl' (most likely due to a circular import)
  ```
  Fourth failure:
  ```
  ImportError: cannot import name 'AbstractionRef' from 'poker_solver'
  ```
- Note: `poker_solver/hunl.py` already has a `TYPE_CHECKING`-guarded
  forward-reference for `AbstractionRef`, with an explicit comment about the
  cycle. The Rust embed-Python harness initializes the module non-standardly
  (partial init), which triggers the import error.
- **`poker_solver/hunl.py` is NOT in this wave's diff.** Pre-existing
  embed-Python harness issue. (Also: the crate file `tests/test_hunl_rust.rs`
  predates v1.5.x by many commits.)

### 5. `cargo clippy --all-targets -- -D warnings` — **PASS**

- Exit 0. No warnings.

### 6. `pyproject.toml` extras sanity — **PASS**

```python
{
  'dev': ['black>=24.0', 'maturin>=1.7', 'pytest>=7.0',
          'pytest-timeout>=2.3', 'ruff>=0.6'],
  'ui':   ['nicegui>=3.0,<4.0'],
  'distribution': ['pyinstaller>=6.0', 'nicegui>=3.0,<4.0']
}
```

Both `[ui]` and `[distribution]` contain `nicegui>=3.0,<4.0`. Confirmed.

### 7. `README.md` sanity — **PASS**

- `grep -E "/Users/ashen|ashen26@" README.md` → exit 1 (no matches).
- `wc -l README.md` → 253 lines (matches target).
- First 30 lines: project description first, then `## Status`, then
  `## Install (from source)` with `pip install -e .` as the recommended path.
  Install section starts with the CLI source-build path. Confirmed.

### 8. Aggregator explainer sanity — **PASS**

- `grep -nE "v1\.6|PR (33|34|35|40|29)" docs/aggregator_vs_true_nash_explainer.md`
  → exit 1 (no matches).
- `wc -l docs/aggregator_vs_true_nash_explainer.md` → 180 lines (matches target).

### 9. `scripts/build_macos_dmg.sh` `DMG_NAME` — **PASS**

- Line 123: `DMG_NAME="Poker-Solver-${APP_VERSION}-arm64.dmg"`
- Comment block (lines 121–122) explains why universal2 was renamed.

### 10. `scripts/poker_solver.spec` — header confirms `arm64` target retained.

---

## Failures-to-cause mapping

| # | Test | Status | Caused by this wave? | Suggested route |
|---|---|---|---|---|
| 1 | ruff check `range.py` UP037 | FAIL | No — `range.py` not in diff | Defer (independent lint sweep) |
| 2 | ruff format 17 files | FAIL | No — none of the 17 in diff | Defer (independent format sweep) |
| 3 | pytest leduc fixture timeout | FAIL | No — leduc stack untouched | Mark leduc fixture as `slow`, or raise per-fixture timeout |
| 4 | cargo test_hunl_rust 4 PyO3 fails | FAIL | No — `hunl.py` untouched, test file untouched | Investigate embed-Python init path (separate work) |

**None of the 4 failure clusters touch the 5 files modified in this wave**
(CHANGELOG/README/pyproject/build_macos_dmg.sh/poker_solver.spec). They are
all pre-existing repo debt.

---

## Overall verdict

**SOME-FAILURES, but ALL pre-existing and NOT introduced by this wave's edits.**

The wave's 5 modified files (CHANGELOG.md, README.md, pyproject.toml,
scripts/build_macos_dmg.sh, scripts/poker_solver.spec) passed every targeted
sanity check (file size, install-section structure, DMG naming, optional-deps
content, stale-reference scrubbing).

The 4 failure clusters live in code paths that this wave does **not** modify;
they are tracked separately and should be triaged outside the integration
gate for this wave.
