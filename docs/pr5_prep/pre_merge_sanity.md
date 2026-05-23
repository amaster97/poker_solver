# PR 5 pre-merge integration tip sanity scan

**Date:** 2026-05-22
**Branch under test:** `pr-5-hunl-postflop-solve` (working tree; uncommitted)
**Integration tip:** `5832b2f` (Integration: merge PR 4)
**Scope:** filler check per the ≥5-PR rule — what the new integration tip will look like *if* PR 5 commits + merges as-is.

---

## 1. Branch state snapshot

| Check | Result |
| --- | --- |
| `git log --oneline integration -15` head | `5832b2f Integration: merge PR 4 (card abstraction)` (matches expected) |
| `git rev-parse pr-5-hunl-postflop-solve integration` | **Both point at `5832b2f`** — PR 5 work is *uncommitted* on the working tree, not yet on a commit. |
| `git diff --stat integration..pr-5-hunl-postflop-solve` | empty (branches identical) |
| `git diff --name-only integration..pr-5-hunl-postflop-solve | wc -l` | **0 (committed); 14 if we count the working tree)** |

**Interpretation:** the PR 5 branch HEAD has not yet advanced past integration. The audit was performed against `git status` (working tree + index + untracked) since that is what would land in the merge commit. The pre-commit checklist + audit report already exist (`docs/pr5_prep/audit_report.md`, `pre_commit_checklist.md`); commit has not yet been made.

### Working-tree file inventory (what PR 5 *would* add at merge time)

**New source files (untracked):**
- `poker_solver/hunl_solver.py` (417 lines)
- `poker_solver/profiler/__init__.py` (29 lines)
- `poker_solver/profiler/memory.py` (510 lines)
- `tests/fixtures/__init__.py`
- `tests/fixtures/hunl_solve_fixtures.py`
- `tests/test_hunl_postflop_solve.py` (649 lines)
- `tests/test_memory_profiler.py` (408 lines)

**Modified files (unstaged):**
- `poker_solver/__init__.py` (+7 / −0) — adds 5 PR 5 exports
- `poker_solver/cli.py` (+191 / −0 effective; +191 / −10 chg) — `--hunl-mode postflop`, `_build_postflop_config`, `_parse_bet_sizes`
- `poker_solver/solver.py` (+17 / −0) — dispatch to `solve_hunl_postflop` for postflop HUNL configs
- `pyproject.toml` (+9 / −2) — psutil dep + pytest-timeout dev dep + `[tool.pytest.ini_options]` (timeout=90, markers `slow`, `very_slow`)
- `tests/test_abstraction_buckets.py` (+7) — `@pytest.mark.timeout(180)` decorators on heavy build tests
- `tests/test_abstraction_emd.py` (+3 / −3) — black-shape assert reformat
- `tests/test_abstraction_integration.py` (+6) — timeout decorators
- `tests/test_hunl_tree.py` (+1) — timeout decorator
- `tests/test_leduc_diff.py` (+12) — module-level `_LEDUC_DIFF_TIMEOUT`, timeout decorators on 5 tests

**Staged:** `tests/test_abstraction_emd.py` (one block) — alongside the unstaged half.

**Total: 14 files touched** (7 new + 5 modified source-tier + 2 mixed staged/unstaged test files).

---

## 2. Public API surface check

`python -c "import poker_solver; print(len(poker_solver.__all__))"` → **74 names**.

The five PR 5 exports all import cleanly and are listed in `__all__`:
- `HUNLSolveResult` → `poker_solver.hunl_solver.HUNLSolveResult`
- `solve_hunl_postflop` → `poker_solver.hunl_solver.solve_hunl_postflop`
- `MemoryReport` → `poker_solver.profiler.memory.MemoryReport`
- `MemoryProbe` → `poker_solver.profiler.memory.MemoryProbe`
- `StreetMemoryEntry` → `poker_solver.profiler.memory.StreetMemoryEntry`

**Docstring health:** first 20 lines of `solve_hunl_postflop.__doc__` are coherent — name the args (`config`, `abstraction`, `iterations`, `target_exploitability`, `memory_budget_gb`, `log_every`, `seed`), describe the default behavior, document the `MemoryError` payload pattern (spec §7.7), and reference cross-agent contract defaults (50k iter cap, 14 GB budget).

**Tests import from public surface:** of 24 `^from poker_solver` statements across `tests/`, 11 use deep `poker_solver.<submodule>` imports (`card`, `equity`, `range`, `dcfr`, `games`, `evaluator`, `abstraction`). All of these were already established pre-PR 5 (none introduced by this PR). No PR 5 test reaches into private modules to consume `hunl_solver` or `profiler` internals — both are imported via top-level `poker_solver`.

---

## 3. Lint + format sweep on PR 5

| Tool | Scope | Result |
| --- | --- | --- |
| `ruff check poker_solver tests` | full | **CLEAN** ("All checks passed!") |
| `ruff check` (PR 5 new files only) | `poker_solver/hunl_solver.py`, `poker_solver/profiler/`, `tests/test_hunl_postflop_solve.py`, `tests/test_memory_profiler.py` | **CLEAN** |
| `black --check poker_solver tests` | full | **FAIL: 2 files would be reformatted** |
| `black --check` (existing tests modified by PR 5) | `tests/test_abstraction_*`, `test_hunl_tree.py`, `test_leduc_diff.py` | **CLEAN** (5 files, all OK) |
| `mypy --strict poker_solver/hunl_solver.py poker_solver/profiler/` | strict | **CLEAN** ("Success: no issues found in 3 source files") |

### Black failures (the only blocker)

Black would reformat:
- `tests/test_memory_profiler.py` — 3 assertion blocks (`assert X, (f"…")` → `assert (X), f"…"`)
- `tests/test_hunl_postflop_solve.py` — 3 assertion blocks (same pattern)

These are pure whitespace/parenthesization fixes; no semantic impact. **Action required: run `black tests/test_memory_profiler.py tests/test_hunl_postflop_solve.py` before commit.**

---

## 4. `pyproject.toml` diff (integration → PR 5)

```diff
-dependencies = ["numpy>=1.24"]
+dependencies = ["numpy>=1.24", "psutil>=5.9"]

-dev = ["pytest>=7.0", "maturin>=1.7", "ruff>=0.6", "black>=24.0"]
+dev = ["black>=24.0", "maturin>=1.7", "pytest>=7.0", "pytest-timeout>=2.3", "ruff>=0.6"]

 [tool.pytest.ini_options]
 testpaths = ["tests"]
+timeout = 90
+markers = [
+    "slow: long-running tests (5min-1hr); skip with -m 'not slow'",
+    "very_slow: hour-scale builds (production precompute); opt-out of timeout cap",
+]
```

**Expected adds (per checklist):** `psutil>=5.9` to dependencies ✓, `pytest-timeout>=2.3` to dev ✓.

**Other deltas:** dev dependency list is alphabetized (cosmetic re-sort), and the new `[tool.pytest.ini_options]` `timeout` + `markers` keys are added. These are tightly bound to PR 5's pytest-timeout adoption and the `@pytest.mark.timeout(...)`/`@pytest.mark.slow` decorator usage in the new and modified tests. **No drift flagged.**

---

## 5. License attribution check

### postflop-solver / AGPL mentions in **new code**

Single mention: `poker_solver/profiler/memory.py:4` — module docstring reading:

> "Pattern (compute total memory by summing every backing buffer's bytes) is inspired architecturally by postflop-solver's memory_usage() (AGPL — read-only). No code copied; implementation derived from first principles per spec §7 of docs/pr5_prep/pr5_spec.md."

**Verdict: COMPLIANT.** This is an architectural acknowledgment in a docstring, not a code copy. The explicit "No code copied" disclaimer matches the spec §7.8 contract (`docs/pr5_prep/pr5_spec.md:333`).

### Verification

- `grep -n "import postflop\|from postflop\|from postflop_solver" poker_solver/ tests/ -r` → **no matches**. No imports from postflop-solver anywhere.
- `grep -rni "AGPL" poker_solver/ tests/` → exactly 1 hit (the docstring above). Tests, fixtures, and `hunl_solver.py` contain no AGPL references.
- `tests/fixtures/hunl_solve_fixtures.py` → no AGPL / postflop-solver references.
- All other postflop-solver references live in `docs/pr5_prep/audit_report.md` and `docs/pr5_prep/pr5_spec.md` (allowed; spec/audit documents).

### slumbot / kmeans citation (PR 4 carry-over)

Confirmed in-place from PR 4, untouched by PR 5:
- `poker_solver/abstraction/buckets.py:21-22` — slumbot2019 architectural pattern + reference path (MIT)
- `poker_solver/abstraction/emd_clustering.py:11,153` — slumbot2019 `SeedPlusPlus` (MIT; "no code copied")
- `poker_solver/abstraction/precompute.py:15-16` — slumbot2019 `build_kmeans_buckets.cpp` (MIT)

**Verdict: COMPLIANT.** Slumbot citations present where kmeans patterns are used.

---

## 6. Summary table

| Check | Status | Notes |
| --- | --- | --- |
| Integration tip = `5832b2f` | PASS | matches expected |
| PR 5 file count | 14 (working tree) | 7 new + 7 modified |
| Public API surface | PASS | 74 names; all 5 PR 5 exports importable |
| Docstring (`solve_hunl_postflop`) | PASS | coherent first-20-line summary |
| `ruff check poker_solver tests` | PASS | clean |
| `black --check` | **FAIL** | 2 PR 5 test files need reformat |
| `mypy --strict` (PR 5 modules) | PASS | clean |
| `pyproject.toml` deltas | PASS | psutil + pytest-timeout + ini options; no drift |
| AGPL / postflop-solver imports | PASS | none; one architectural docstring citation only |
| slumbot citation (PR 4 carry-over) | PASS | preserved |

---

## 7. Recommendation

**HOLD** until the black reformat is applied. Then proceed to commit + merge.

**Pre-commit blocker (single fix):**

```bash
black tests/test_memory_profiler.py tests/test_hunl_postflop_solve.py
```

After applying, re-run `black --check poker_solver tests` to confirm clean; everything else (ruff, mypy strict, public surface, license hygiene, pyproject diff) is already green.

**No spec-level concerns surfaced** — the diff matches the cross-agent contract for PR 5 (HUNL postflop solver + per-street memory profiler), `pyproject.toml` adds only the expected deps, and the AGPL contact surface is a single architectural acknowledgment in a docstring (no code reuse).
