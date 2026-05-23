# PR 5 deferred cleanup backlog

Audit items from `audit_report.md` that were assessed as too risky / too broad
for the in-flight PR 5 commit. These should be picked up in a follow-up
cleanup PR after PR 5 lands.

---

## Should-fix items deferred from PR 5 audit

### S1 — `HUNLSolveResult` runtime immutability guard

**File:** `poker_solver/hunl_solver.py:48-74`

The audit recommends converting the "treat as immutable" docstring contract
into a runtime `__setattr__` guard so downstream callers can rely on the
contract programmatically. Currently the dataclass inherits `SolveResult`'s
mutability (Python forbids `@dataclass(frozen=True)` on a non-frozen parent).

**Why deferred:** behavioral change — adding `__setattr__` raises on any
post-construction mutation, which could break callers that currently rely on
in-place updates (none known, but the immutability isn't testable without
also adding immutability tests, which would touch test files).

**Next step:** add `__setattr__` guard, write a test that asserts attempted
mutation raises, document the contract in the spec §11 immutability section.

---

### S3 — Determinism test (`test_solve_is_deterministic_under_seed`)

**File:** new `tests/test_hunl_postflop_solve.py` test

Spec §11 #10 asserts "deterministic re-runs under fixed seed" but no test
exercises it end-to-end. The fix would add a test that runs Fixture 1 (the
tiny synthetic abstraction) twice with `seed=42`, then asserts strategy
tables match within 1e-12.

**Why deferred:** touches the test file, which the constraint forbids during
the PR 5 commit window. The PR 5 commit agent may have a parallel pass on
test files.

**Next step:** in the cleanup PR, add the determinism test on Fixture 1
(river-only). Fixture 1 solves in <1s and exercises DCFR's averaging path
without depending on the TURN-coverage gap.

---

### S4 — Spec §11 #1/#3 skip-set reconciliation

**Files:** `docs/pr5_prep/pr5_spec.md` §11, §16 + possibly
`tests/fixtures/hunl_solve_fixtures.py`

The 6-test skip set excludes spec §11's #1 ("first HUNL solve produces a
valid strategy") and #3 ("solver works with PR 4 abstraction on flop"). The
skip reason is a PR 4 fixture coverage gap, not a PR 5 bug. The audit
recommends either (a) adding a smaller end-to-end fixture or (b) rewording
the spec to acknowledge the deferral.

**Why deferred:** touches spec + test fixtures + likely the abstraction
artifact build. Multi-file, spec-touching, and the right answer probably
waits on PR 6 (Rust backend) or a PR 4 fixture revisit.

**Next step:** decide between (a) and (b) at PR 6 planning. If (a), add a
`(2, 1, 1)` synthetic abstraction that closes the TURN coverage gap, and
unskip the 6 tests. If (b), update spec §16 success criteria to acknowledge
the deferral.

---

### S7 — Thread `--abstraction` CLI flag into `solve_hunl_postflop`'s
`abstraction=` parameter

**File:** `poker_solver/cli.py:144-162` + `:230-241`

Currently the CLI attaches the `AbstractionRef` to the `HUNLConfig` (so the
solve uses the abstraction) but does NOT pass the loaded `AbstractionTables`
as the `abstraction=` parameter to `solve_hunl_postflop`. As a result:

- The solve itself uses the abstraction correctly (via `resolve_abstraction_ref`).
- But `MemoryProbe(solver, include_abstraction=None)` doesn't include the
  abstraction-table bytes in `grand_total_bytes` — the memory accounting is
  under by ~10-100 MB depending on bucket counts.
- The `UserWarning` for lossless-flop subgames fires spuriously when the
  user passes `--abstraction` on flop start, because
  `solve_hunl_postflop`'s `abstraction is None` branch is hit.

**Why deferred:** behavioral change to memory accounting. The fix requires
plumbing the loaded `AbstractionTables` from `_build_hunl_with_args` to
`_cmd_solve` (either via the `args` namespace, a module-level cache, or
re-loading in `_cmd_solve`). Each option has trade-offs (storing on `args`
is awkward; re-loading is wasted I/O; module cache breaks if multiple
solves run in one process). The audit assesses this as "should-fix
(success criterion in §16 unreachable; programmatic call works)" — i.e.,
the programmatic path is fine, only the CLI is affected.

**Next step:** in the cleanup PR, thread the loaded `AbstractionTables`
from `_build_hunl_with_args` (already loaded at line 154) to `_cmd_solve`
via a side-channel — likely store on the returned `HUNLPoker` instance, or
re-introduce a `Game` subclass with a `loaded_abstraction` attribute.

---

## Nice-to-fix items (lower priority backlog)

### N1 — `_install_in_memory_resolver_shim` is process-global

**File:** `poker_solver/hunl_solver.py:293-318`

The shim monkey-patches `poker_solver.abstraction.buckets._cached_load`
once per process and stays installed. Consider a context-manager pattern
so library callers can opt out, OR document the permanence more loudly.

**Why deferred:** API expansion (context manager addition). The current
behavior is documented and works for tests + library callers.

---

### N2 — `_DICT_OVERHEAD_RATIO = 0.5` constant

**File:** `poker_solver/profiler/memory.py:53`

The constant could live in the module-level docstring more visibly. Per-
interpreter calibration could drift on a future Python version (e.g.,
PyPy or a CPython 3.13 dict redesign). The audit assesses this as
nice-to-have; the `rss_calibration_error < 0.10` check is the ground-truth
gate.

**Why deferred:** documentation polish; no behavior change.

---

### N4 — `_print_memory_section` defensive `getattr` pattern

**File:** `poker_solver/cli.py:283-303`

Since `psutil>=5.9` is now a hard runtime dep, the `getattr(report, "...",
default)` pattern is no longer needed — typed attribute access would be
cleaner and let mypy catch shape regressions.

**Why deferred:** behavioral change (typed access raises on a missing
attribute; `getattr` returns a default). Low-risk but should be paired
with a regression test that exercises the CLI's memory section render.

---

## Coverage gaps (G-items)

### G1, G2, G3 — Skipped tests for spec §11 critical-correctness items

These are all in the 6-skip set due to the PR 4 TURN-coverage gap. The
audit recommends adding smaller-fixture fallbacks on Fixture 1 (river-only,
no abstraction). All three would touch the test file.

**Why deferred:** touches test files. Pick up alongside S3 in the cleanup PR.

### G4 — Determinism test

Same as S3 above.

### G5 — Convergence smoke chain alignment

**File:** `tests/test_hunl_postflop_solve.py:354` (convergence-history check)

Test uses a "final < quartile-point * 1.5" check; spec §9.3 prescribes
"moving-average of last 5 < moving-average of first 5". Align either the
test or the spec.

**Why deferred:** touches test file + spec.

### G6 — `tiny_synthetic_abstraction()` (in-memory variant) export

**File:** `tests/fixtures/hunl_solve_fixtures.py:214-228`

Fixture exposes both an `AbstractionTables` (`tiny_synthetic_abstraction()`)
and an `AbstractionRef` (`tiny_synthetic_abstraction_ref()`) variant. Spec
§9.5 only documents the former. Document the ref variant in the spec or
strip the unused export.

**Why deferred:** spec edit + test fixture file. Low priority.
