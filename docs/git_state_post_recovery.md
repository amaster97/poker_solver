# Git State Post-Recovery Audit

**Date:** 2026-05-22
**Scope:** Verify git stash state + working tree integrity after PR 5 recovery
**Constraint:** Read-only audit + diff comparisons only. No stash drops, no branch switches.

---

## 1. Stash List Snapshot

```
stash@{0}: WIP on pr-5-hunl-postflop-solve: 5832b2f Integration: merge PR 4 (card abstraction)
```

- **Total stashes:** 1
- **Age:** ~9 hours old
- **Base commit:** `5832b2f` (Integration: merge PR 4 — card abstraction)
- **Stash commit hash:** `fcc91fe`

---

## 2. Per-Stash Content Diff vs Working Tree

### stash@{0} — file-level summary

| File | Stash lines (+/-) | In WT? | Stash ⊆ WT? |
|------|------------------|--------|------------|
| `poker_solver/__init__.py`  | +7 / -0   | Yes (M) | IDENTICAL — fully contained |
| `poker_solver/cli.py`       | +1 / -1   | Yes (M) | Strict subset — WT has +191 lines more |
| `poker_solver/solver.py`    | +17 / -0  | Yes (M) | IDENTICAL — fully contained |
| `pyproject.toml`            | +1 / -1   | Yes (M) | Strict subset — WT has timeout/markers + extras |

**Stash totals:** 4 files, 26 insertions(+), 2 deletions(-).
**WT totals (modified files only):** 10 files, 264 insertions(+), 23 deletions(-).

### Per-file detail

**`poker_solver/__init__.py`** — stash diff is byte-identical to WT diff:
- Adds `HUNLSolveResult`, `solve_hunl_postflop`, `MemoryProbe`, `MemoryReport`, `StreetMemoryEntry` imports + `__all__` entries.

**`poker_solver/cli.py`** — stash only adds `HUNLConfig, Street` to the `poker_solver.hunl` import line. WT contains the same import edit PLUS:
- `IO` added to `typing` import.
- `_parse_bet_sizes()` helper (~15 lines).
- `_build_postflop_config()` helper (~40 lines).
- Subparser handlers for `--hunl-mode postflop`, `--bet-sizes`, `--board`, `--stacks`.
- Total: ~191 additional lines in WT.

**`poker_solver/solver.py`** — stash diff is byte-identical to WT diff:
- Adds the PR 5 postflop dispatch branch (HUNL flop/turn/river → `solve_hunl_postflop`).

**`pyproject.toml`** — stash only adds `psutil>=5.9` to runtime deps. WT contains that PLUS:
- Re-sorted `dev` list with new `pytest-timeout>=2.3`.
- `[tool.pytest.ini_options]` adds `timeout = 90`.
- `markers = [...]` defines `slow` and `very_slow` pytest markers.

### Files in WT but NOT in stash

These exist as either modified or untracked in WT, and have **zero** stash content:

Modified-only-in-WT (6):
- `README.md` (+31 / -3)
- `tests/test_abstraction_buckets.py`, `test_abstraction_emd.py`, `test_abstraction_integration.py`, `test_hunl_tree.py`, `test_leduc_diff.py`.

Untracked-only-in-WT (5):
- `poker_solver/hunl_solver.py` (17,168 bytes)
- `poker_solver/profiler/` (`__init__.py` + `memory.py`, 19,662 bytes)
- `tests/fixtures/` (`__init__.py` + `hunl_solve_fixtures.py`, 13,085 bytes)
- `tests/test_hunl_postflop_solve.py` (25,604 bytes)
- `tests/test_memory_profiler.py` (15,946 bytes)

---

## 3. Recommended Action Per Stash

| Stash | Recommendation | Rationale |
|-------|---------------|-----------|
| `stash@{0}` | **safe-to-drop** (do not drop in this task per constraint) | Every line of every file in the stash is byte-equivalent to the corresponding hunk in the working tree. No content would be lost. Stash is a strict subset of WT — an intermediate save point captured before the full PR 5 set was assembled. |

**Constraint reminder:** This task is read-only audit. Recommendation only — orchestrator owns the drop decision.

---

## 4. Working Tree Integrity

- **Total dirty entries:** 15 (10 modified + 5 untracked)
- **Modified files:** 10 (matches expected PR 5 modification footprint)
- **Untracked files/dirs:** 5 (matches expected PR 5 new-file footprint: solver module, profiler package, fixtures package, two new test files)
- **PR 5 expected files present:** all confirmed on disk
  - `poker_solver/hunl_solver.py` — present
  - `poker_solver/profiler/{__init__.py, memory.py}` — present
  - `tests/fixtures/{__init__.py, hunl_solve_fixtures.py}` — present
  - `tests/test_hunl_postflop_solve.py` — present
  - `tests/test_memory_profiler.py` — present
- **Cumulative diff size vs HEAD:** +264 / -23 lines across 10 modified files

---

## 5. Branch Tip State

- **Current branch:** `pr-5-hunl-postflop-solve`
- **HEAD:** `5832b2f` Integration: merge PR 4 (card abstraction)
- **Recent log (HEAD ← root):**
  - `5832b2f` Integration: merge PR 4 (card abstraction)
  - `f67bfa3` Integration: merge PR 3.5 audit follow-up (1cbf52a)
  - `6565b84` PR 4: Card abstraction pipeline (EMD bucketing, 256/128/64, suit-iso)
  - `1cbf52a` PR 3.5 audit follow-up: API completeness + spec amendments
  - `fd0a2c7` Integration: merge PR 3.5 (push/fold + v0.3 capstone)
- **Branch tip integrity:** clean — branch sits at the PR 4 merge commit; all PR 5 work is uncommitted on top, which is the expected state for an in-progress feature branch.

---

## Conclusion

Recovery is complete and stable. The working tree carries the full PR 5 change set. `stash@{0}` is an obsolete intermediate save point whose entire content is present in the working tree; it can be dropped safely whenever the orchestrator chooses. No content is at risk.
