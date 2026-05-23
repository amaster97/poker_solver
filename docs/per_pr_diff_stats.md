# Per-PR Diff Stats

**Baseline:** `2b67370` (Equity: hybrid exact-enum + MC, tighter precision default — last main commit before PR 3)
**Tip:** `integration` (`6c438b8` — merge of PR 6)
**Date generated:** 2026-05-22
**Source of truth:** `git diff <prev>..<commit> --numstat` (insertions only, per-file)

---

## 1. Per-PR LOC Stats

Per-PR commits walk the linear history on `integration`. Diffs are computed `<prev_pr_commit>..<this_pr_commit>` so each row is independent.

| PR        | Commit    | Files | Py src   | Py test  | Rust src | Rust test | Other     | **Total** |
|-----------|-----------|------:|---------:|---------:|---------:|----------:|----------:|----------:|
| PR 3      | `a96675c` |     9 |    948   |    848   |      0   |       0   |       4   | **1,800** |
| PR 3.5    | `9f91c83` |    14 |  1,062   |    218   |      0   |       0   |   3,683   | **4,963** |
| PR 3.5 fu | `1cbf52a` |     5 |    119   |      8   |      0   |       0   |       1   |   **128** |
| PR 4      | `6565b84` |    15 |  2,095   |    993   |      0   |       0   |       0   | **3,088** |
| PR 5      | `a9d02ca` |    20 |  1,295   |  1,446   |      0   |       0   |      29   | **2,770** |
| PR 6      | `0933367` |    18 |    187   |    469   |  2,859   |   1,167   |     629   | **5,311** |
| PR 6 fu   | `dc8db4c` |     3 |      0   |     16   |      0   |       0   |       0   |    **16** |
| **TOTAL** |           |    84 |  **5,706** | **3,998** | **2,859** | **1,167** | **4,346** | **18,076** |

Notes:
- "Py src" = `poker_solver/**/*.py`. "Py test" = `tests/**/*.py`.
- "Rust src" = `crates/**/src/*.rs`. "Rust test" = `crates/**/tests/*.rs`.
- "Other" = TOML / Markdown / JSON / lockfiles / GitHub templates.
- `pushfold_v1.json` in PR 3.5 (3,045 lines) dominates that PR's "Other".

---

## 2. Cumulative Since Main Baseline (`2b67370`)

`git diff 2b67370..integration --numstat` aggregate:

| Bucket           | Lines added | Files |
|------------------|------------:|------:|
| Python source    |    5,483    |  17   |
| Python tests     |    3,969    |  15   |
| Rust source      |    2,859    |   6   |
| Rust tests       |    1,167    |   2   |
| Other            |    4,321    |  11   |
| **Cumulative**   |  **17,799** | **51**|

The cumulative differs slightly from the per-PR sum (18,076) because PR 3.5 + PR 4 + PR 5 each *deleted* lines from `solver.py` / `pushfold.py` as they refactored; cumulative diff sees only net adds against baseline.

---

## 3. Python vs Rust LOC per PR

Source code only (excludes tests):

| PR        | Py src | Rust src | Py:Rust ratio | Tier introduced       |
|-----------|-------:|---------:|---------------|-----------------------|
| PR 3      |   948  |      0   | Py-only       | Tree builder          |
| PR 3.5    | 1,062  |      0   | Py-only       | Push/fold             |
| PR 3.5 fu |   119  |      0   | Py-only       | API completeness      |
| PR 4      | 2,095  |      0   | Py-only       | Card abstraction      |
| PR 5      | 1,295  |      0   | Py-only       | HUNL postflop solve   |
| PR 6      |   187  |  2,859   |  1 : 15.3     | Rust port + diff harness |
| PR 6 fu   |     0  |      0   | n/a           | Test stability        |
| **TOTAL** | **5,706** | **2,859** | **1 : 0.50** | Mostly Py             |

Tests:

| PR        | Py test | Rust test | Notes                                     |
|-----------|--------:|----------:|-------------------------------------------|
| PR 6      |   469   |   1,167   | Rust unit + diff harness against Python   |
| Others    | 3,529   |       0   |                                           |
| **TOTAL** | **3,998** | **1,167** |                                           |

**Observation:** the Rust port (PR 6) is the only Rust-bearing PR so far. It contributed 1 Python line of glue/refactor for every 15.3 Rust lines, consistent with a "Rust executes hot loop, Python orchestrates" architecture. Cumulatively, the project is still ~67% Python source by line.

---

## 4. Test LOC vs Source LOC Ratio

Per PR (test:source where source > 0):

| PR        | Source (Py+Rust) | Tests (Py+Rust) | Test : Source |
|-----------|-----------------:|----------------:|--------------:|
| PR 3      |       948        |       848       |    0.89 : 1   |
| PR 3.5    |     1,062        |       218       |    0.21 : 1   |
| PR 3.5 fu |       119        |         8       |    0.07 : 1   |
| PR 4      |     2,095        |       993       |    0.47 : 1   |
| PR 5      |     1,295        |     1,446       |    1.12 : 1   |
| PR 6      |     3,046        |     1,636       |    0.54 : 1   |
| PR 6 fu   |         0        |        16       |     n/a       |
| **TOTAL** |   **8,565**      |   **5,165**     |  **0.60 : 1** |

Notes:
- PR 3.5 ratio is low because most of its bulk is data (`pushfold_v1.json` charts) and meta (CHANGELOG, CONTRIBUTING, README, GH templates) — not testable executable code.
- PR 5 hit >1:1 driven by `test_hunl_postflop_solve.py` (649) + `test_memory_profiler.py` (408) + fixtures (351).
- PR 6 looks low on the surface, but the 1,636 test lines include cross-tier diff tests that exercise *both* Python and Rust paths, so each test line stresses two source code paths.
- Overall **0.60 : 1** test:source ratio is healthy for an algorithmic research codebase; the diff-tested layers (Leduc, HUNL) carry the bulk of the coverage.

---

## 5. Highlights & Architectural Inflection Points

- **Largest single PR:** PR 6 (5,311 LOC) — Rust port of HUNL postflop solver.
- **Largest Python PR:** PR 4 (3,088 LOC) — card abstraction pipeline (256/128/64 bucketing, EMD clustering, equity features, precompute).
- **Smallest substantive PR:** PR 3.5 follow-up (128 LOC) — audit-driven API completeness.
- **Test-heaviest PR:** PR 5 (1,446 test LOC) — fixtures + memory profiler + postflop solve.
- **Refactoring signal:** `solver.py` was modified in *every* PR from 3.5 onward (-61, -50, -39, -15 lines net across PRs), confirming the planned consolidation of orchestration into a unified solver entry point.

---

## 6. Commit Map

```
2b67370  main baseline (equity hybrid)
a96675c  PR 3      — HUNL tree builder + action abstraction
9f91c83  PR 3.5    — push/fold (2-15 BB) + v0.3 capstone meta
1cbf52a  PR 3.5 fu — API completeness + spec amendments
6565b84  PR 4      — card abstraction (EMD bucketing 256/128/64)
a9d02ca  PR 5      — HUNL postflop solve + memory profiler
0933367  PR 6      — Rust port of HUNL postflop solve (v0.5.0)
dc8db4c  PR 6 fu   — Leduc test timeout hardening
6c438b8  integration tip (merge commit)
```
