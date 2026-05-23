# PR 5 — Pre-commit checklist

**Gate:** ALL boxes must be checked before the orchestrator runs `git commit`.
**Branch:** `pr-5-hunl-postflop-solve`
**Base:** `integration` at `5832b2f` (PR 3 + 3.5 + 4)

This checklist is the final go/no-go gate. If any box cannot be checked,
fix the underlying issue before commit — do NOT commit-then-fix.

---

## 1. Test suite — zero failures, zero timeouts

- [ ] `pytest -m "not slow and not very_slow"` completes with **ZERO failures**
  and **ZERO timeouts** (pytest-timeout 90s default).
- [ ] Skipped/xfail tests are acceptable, but every skip must have a
  documented reason in the test docstring.
- [ ] `pytest --collect-only -q | wc -l` matches the expected total
  (151 pre-existing + ~22 new = ~173 collected).

## 2. Skip-set discipline (TURN coverage gap)

- [ ] **All 6 skip-marked tests** in `tests/test_hunl_postflop_solve.py` +
  `tests/test_memory_profiler.py` carry the **same skip reason**:
  *"PR 4 synthetic abstraction (4, 2, 2) lacks TURN coverage — lookup_bucket
  raises AND lossless fallback hangs. Tests deferred to PR 6 (Rust) or PR 4
  fixture revisit."*
- [ ] Skip reasons grep-clean: `grep -r "skip" tests/test_hunl_postflop_solve.py
  tests/test_memory_profiler.py` returns identical reason strings.

## 3. River-only fallback tests (audit G1/G2/G3 fixes)

Audit report flagged that spec §11 critical-correctness items #1, #3, #4, #5
were implemented but **un-exercised in CI** because their owning tests are in
the skip set. River-only fallbacks close those gaps:

- [ ] `test_postflop_river_subgame_strategy_is_valid` exists, runs on the
  river-only (no-abstraction) fixture, asserts `sum(probs) == pytest.approx(1.0)`,
  `0 <= p <= 1`, no NaN / Inf, `len(probs) == num_actions`. (Covers spec §11 #1.)
- [ ] `test_memory_profiler_matches_rss_river_subgame` exists, runs on the
  river-only fixture for ≥50 iterations, asserts RSS calibration within
  ±20-50% (looser than the spec's 10% because absolute bytes are smaller).
  (Covers spec §11 #4.)
- [ ] `test_postflop_solve_memory_budget_aborts_cleanly_river_subgame` exists,
  sets `max_memory_gb=1e-6`, asserts `MemoryError` raised with partial
  `MemoryReport` in `args[1]`. (Covers spec §11 #5.)
- [ ] None of the three new river-only tests are in the skip set; all
  execute in CI.

## 4. Audit must-fix applied

- [ ] `poker_solver/hunl_solver.py` lines 163-167: exploitability guard added.
  The post-solve `exploitability(game, avg)` call is now gated on
  `avg and iterations > 0`. (Fix per audit Must-fix #1.)
- [ ] `test_postflop_solve_warns_for_lossless_flop_start` no longer hangs;
  it either passes (warning fires, no exploitability walk) or is converted
  to a river-only-equivalent if Fixture 2 lossless is still infeasible.

## 5. CLI `--abstraction PATH` wired (audit S7)

- [ ] `poker_solver/cli.py` argparse setup includes
  `--abstraction PATH` flag scoped to `--hunl-mode postflop`.
- [ ] `_build_postflop_config` attaches the loaded `AbstractionRef` to the
  config when the flag is set.
- [ ] Manual smoke (or test):
  `poker-solver solve --game hunl --hunl-mode postflop --board "As 7c 2d"
  --stacks 100 --abstraction /tmp/test.npz --iterations 100` runs without
  error (does not require a full PR 4 artifact — a tiny synthetic
  saved-to-disk artifact suffices).
- [ ] The `--abstraction` flag is also exposed on the existing `precompute-abstraction`
  subcommand (already present from PR 4; check it wasn't disturbed).

## 6. Linters + type checker

- [ ] `ruff check poker_solver tests` → clean (0 errors).
- [ ] `ruff format --check poker_solver tests` → clean.
- [ ] `black --check poker_solver tests` → clean.
- [ ] `mypy --strict poker_solver/hunl_solver.py poker_solver/profiler/` →
  clean (0 errors).
- [ ] `mypy poker_solver` overall → no NEW errors vs `integration@5832b2f`.

## 7. `pyproject.toml` dependencies

- [ ] `dependencies` list includes `psutil>=5.9` (runtime dep for the
  RSS calibration check).
- [ ] `[project.optional-dependencies].dev` (or equivalent) includes
  `pytest-timeout>=2.3`.
- [ ] No other new runtime deps added without justification in the commit
  message body.

## 8. `poker_solver/__init__.py` re-exports

The PR 5 public surface must be importable from the top-level package.

- [ ] `solve_hunl_postflop` re-exported.
- [ ] `HUNLSolveResult` re-exported.
- [ ] `MemoryReport` re-exported.
- [ ] `MemoryProbe` re-exported.
- [ ] `StreetMemoryEntry` re-exported.
- [ ] `__all__` updated to include all five new names.
- [ ] Sanity import:
  `python -c "from poker_solver import solve_hunl_postflop, HUNLSolveResult,
  MemoryReport, MemoryProbe, StreetMemoryEntry; print('OK')"` exits 0.

## 9. No regressions on PR 1–4 tests

- [ ] `pytest tests/test_dcfr_core.py` → all pass (PR 1 Kuhn).
- [ ] `pytest tests/test_leduc_core.py tests/test_leduc_diff.py` → all pass
  (PR 2 Leduc + Rust/Python diff).
- [ ] `pytest tests/test_hunl_core.py tests/test_hunl_tree.py` → all pass
  (PR 3 HUNL tree).
- [ ] `pytest tests/test_pushfold.py` → all pass (PR 3.5 push/fold).
- [ ] `pytest tests/test_abstraction_buckets.py
  tests/test_abstraction_emd.py tests/test_abstraction_integration.py`
  → all pass (PR 4 abstraction).
- [ ] Cumulative count: at minimum **88 pre-existing tests** pass unchanged.

## 10. Git hygiene

- [ ] Branch is `pr-5-hunl-postflop-solve` (NOT `main`, NOT `integration`).
- [ ] `git status` is clean of stray edits not part of PR 5
  (the staged `tests/test_abstraction_emd.py` modification predates the
  PR 5 work — confirm it's an intentional carry-over or revert it).
- [ ] No `.env`, `.npz` (>1 MB), or credential files staged.
- [ ] `git diff --stat HEAD` matches the expected file list:
  - NEW: `poker_solver/hunl_solver.py`, `poker_solver/profiler/__init__.py`,
    `poker_solver/profiler/memory.py`,
    `tests/test_hunl_postflop_solve.py`, `tests/test_memory_profiler.py`,
    `tests/fixtures/hunl_solve_fixtures.py`
  - MODIFIED: `poker_solver/__init__.py`, `poker_solver/cli.py`,
    `poker_solver/solver.py`, `pyproject.toml`
  - MODIFIED (test patches if any from PR 4 carry-over): inspect manually.

## 11. Documentation / autonomous-log alignment

- [ ] `docs/pr5_prep/audit_report.md` exists and is the input to this
  pre-commit pass.
- [ ] Spec amendments locked in this round (river-only fallbacks,
  CLI flag, must-fix guard) are reflected in either the spec or this
  commit message body so future readers can reconstruct the decision trail.
- [ ] No accidental edits to `docs/pr5_prep/pr5_spec.md` outside the
  amendments listed in the commit body.

## 12. Final gating questions (orchestrator self-check)

- [ ] Have I read the audit report's "Overall verdict" and confirmed
  must-fix #1 is resolved?
- [ ] Have I confirmed the 6-test skip set is documented (not silently growing)?
- [ ] Is the commit message body honest about what the skip set means
  (deferral to PR 6 / PR 4 revisit, NOT silent test exclusion)?
- [ ] Does the commit message clearly label this as PR 5 (postflop solve +
  memory profiler), distinct from PR 6 (Rust port)?

---

**All boxes checked → proceed to `git commit -m "$(cat docs/pr5_prep/commit_message_draft.md)"`.**
**Any box unchecked → fix first, then re-run the checklist.**
