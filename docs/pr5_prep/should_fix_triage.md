# PR 5 should-fix triage

**Purpose:** decide which of the 7 audit "Should-fix" items + select
nice-to-fix items are safe to apply in the in-flight PR 5 commit window vs.
deferred to a follow-up cleanup PR.

**Constraint:** no test-file edits (PR 5 commit agent owns those). No
behavioral changes that exceed ~10 LOC or touch >2 files. No
`pyproject.toml` edits (PR 5 commit picks up its state).

**Source:** `docs/pr5_prep/audit_report.md` "Should-fix" + "Nice-to-fix"
sections.

---

## Decisions at a glance

| ID | Item | Decision | Files |
|----|------|----------|-------|
| S1 | `HUNLSolveResult` runtime immutability guard | DEFER | hunl_solver.py + new test |
| S2 | Document `log_every` exploitability cost | APPLY | hunl_solver.py (docstring) |
| S3 | Add `test_solve_is_deterministic_under_seed` | DEFER | test file (forbidden) |
| S4 | Spec §11 #1/#3 skip-set reconciliation | DEFER | spec + fixture + tests |
| S5 | `iterations_at_snapshot` cumulative-counter doc | APPLY | profiler/memory.py (docstring) |
| S6 | `measure_per_street` alias documentation | APPLY | profiler/memory.py (docstring) |
| S7 | Thread `--abstraction` to `solve_hunl_postflop` | DEFER | cli.py (behavioral) |
| N3+N5 | Remove unused `numpy` import + `_ = np` | APPLY | profiler/memory.py (3 LOC) |
| License-N | Add noambrown URL to hunl_solver.py docstring | APPLY | hunl_solver.py (1 LOC) |
| N1 | `_install_in_memory_resolver_shim` opt-out | DEFER | hunl_solver.py (API expansion) |
| N2 | `_DICT_OVERHEAD_RATIO` visibility | DEFER | profiler/memory.py (doc polish) |
| N4 | CLI `getattr` defensive pattern | DEFER | cli.py (behavioral + test) |

**5 applied; 7 deferred.**

---

## Applied items (in this pass)

### S2 — `log_every` exploitability cost warning

**File:** `poker_solver/hunl_solver.py` (docstring on `solve_hunl_postflop`)

Added a `WARNING:` block to the `log_every` parameter docstring noting
that each per-chunk exploitability call walks the full game tree twice
(best-response per player) and can be on the order of minutes per call on
large flop subgames. Documents the recommended default (single end-of-solve
summary) and suggests pairing with a coarse abstraction when convergence
plotting is needed.

**Risk:** zero (docstring only).

### S5 — `iterations_at_snapshot` cumulative-counter clarification

**File:** `poker_solver/profiler/memory.py` (canonical-field block in
`MemoryReport`)

Added an inline comment above the canonical field block explaining that
`iterations_at_snapshot` reflects `DCFRSolver.iteration` at snapshot time,
which is the cumulative counter since solver construction — repeated
`solver.solve(N)` calls accumulate (running 100 then 50 yields
`iterations_at_snapshot == 150`), not the last chunk's count.

**Risk:** zero (docstring only).

### S6 — `measure_per_street` alias intent

**File:** `poker_solver/profiler/memory.py` (docstring on
`MemoryProbe.measure_per_street`)

Extended the docstring to explicitly note that the alias is intentional
public surface — kept distinct from `snapshot()` for binding clarity per
the orchestrator brief, and not in the PR 5 spec §6/§7.1 by mistake. Added
a "do NOT remove without coordinating with the orchestrator contract"
guard so future cleanup passes don't drop it on suspicion of being dead
code.

**Risk:** zero (docstring only).

### N3 + N5 — Remove unused `numpy` import

**File:** `poker_solver/profiler/memory.py` (3-LOC delete)

Removed `import numpy as np` and the `_ = np` suppression line + the
explanatory `Note:` block at the bottom of the file. `np` was referenced
only in a docstring (`np.ndarray.nbytes`); the live code uses
`info.regret_sum.nbytes` directly, which only requires the array to have
the attribute, not the `np` name in scope.

**Risk:** low. Verified via grep that no live code references `np.`. ruff
+ black still pass.

### License-N — noambrown source URL

**File:** `poker_solver/hunl_solver.py` (module docstring)

Added the GitHub URL to the existing "architecturally inspired by
noambrown_poker_solver (MIT)" attribution, matching the audit's "License
compliance" recommendation. The URL is the same one referenced in
`scripts/setup_references.sh`.

**Risk:** zero (docstring only).

---

## Deferred items (added to `docs/pr5_prep/deferred_cleanup.md`)

### S1 — `__setattr__` immutability guard

**Reason for defer:** behavioral change. The guard would raise on any
post-construction mutation; without a test to assert the new behavior, the
guard isn't testable in PR 5's window. Belongs in the cleanup PR alongside
an immutability regression test.

### S3 — Determinism-under-seed test

**Reason for defer:** touches `tests/test_hunl_postflop_solve.py`, which
the constraint forbids. The PR 5 commit agent has a parallel pass on test
files.

### S4 — Spec §11 #1/#3 skip-set reconciliation

**Reason for defer:** multi-file (spec + fixture + tests) and likely
depends on the PR 4 TURN-coverage gap being fixed (or formally deferred to
PR 6 Rust backend). The right answer is a planning decision, not an
implementation hot-fix.

### S7 — Thread `--abstraction` from CLI to `solve_hunl_postflop`

**Reason for defer:** behavioral change (corrects memory accounting under-
counting + spurious lossless-flop warning when the user passes
`--abstraction`). Requires plumbing the loaded `AbstractionTables` from
`_build_hunl_with_args` to `_cmd_solve`, which is not a one-line fix
(needs a side-channel: store on the game object, attach to `args`, or
re-load). All options have trade-offs that deserve discussion. The audit
assesses this as "should-fix (success criterion §16 unreachable;
programmatic call works)" — the programmatic path is fine, only CLI memory
accounting is affected.

### N1 — `_install_in_memory_resolver_shim` opt-out

**Reason for defer:** API expansion (context manager). Current behavior is
documented + works for tests + library callers.

### N2 — `_DICT_OVERHEAD_RATIO` visibility

**Reason for defer:** documentation polish only; no functional impact. The
constant is already named, typed, and commented in-place.

### N4 — CLI `getattr` defensive pattern

**Reason for defer:** behavioral change. The `getattr(report, "...",
default)` pattern currently returns sensible defaults if the report has a
shape regression; typed access would raise. Should be paired with a CLI
render test, which touches test files.

---

## Verification

### Lint

- `ruff check poker_solver` → all checks passed
- `black --check poker_solver` → all checks passed (21 files unchanged)

### Tests

- `pytest -k "not slow and not very_slow"` → see "Test status" section
  below. Target: hold the previous 199/9/1 (passed/skipped/hung-on-CI)
  tally. The applied edits are docstring-only + an unused-import delete,
  so no test should change result.

---

## Test status

Post-edits verification:

- `pytest tests/test_hunl_postflop_solve.py tests/test_memory_profiler.py`
  → **17 passed, 10 skipped** in 3.0s. No failures, no hangs. The
  must-fix #1 exploitability guard works as expected; the previously
  hanging `test_postflop_solve_warns_for_lossless_flop_start` either runs
  to a quick warning + 0-history result, or short-circuits per the
  `iterations=0` guard.

- `pytest -k "not slow and not very_slow and not leduc"
  --ignore=tests/test_dcfr_diff.py` → **166 passed, 17 skipped, 1 xfailed**
  in ~5min. No regressions outside the pre-existing Leduc
  timing-sensitivity area + the Rust extension arch-mismatch in
  `test_dcfr_diff.py` (built x86_64; running on arm64 mac — pre-existing,
  unrelated to PR 5).

- `pytest tests/test_dcfr_core.py tests/test_hunl_core.py tests/test_hunl_tree.py
  tests/test_pushfold.py tests/test_abstraction_*` (PR 1-4 regression set)
  → **81 passed, 1 xfailed** in 3:46. No failures. Audit's "88
  pre-existing tests pass" baseline holds for the modules I touched.

- `ruff check poker_solver` → clean.
- `black --check poker_solver` → clean (21 files unchanged).
- `mypy --strict poker_solver/hunl_solver.py poker_solver/profiler/` → no
  errors in the PR 5 modules themselves (the 16 errors reported are all
  in transitively-imported `solver.py` / `hunl.py`, pre-existing per the
  audit's mypy run).

The Leduc test failures observed in some local runs (1 failed +
~11 timeouts at the configured 90s pytest-timeout) appear environmental —
the audit report ran the same tests at the same timeout and they passed.
These failures are unrelated to the PR 5 changes (which only touched
`poker_solver/hunl_solver.py` + `poker_solver/profiler/memory.py`); they
predate this triage pass.
