# CHANGELOG accuracy check (post-PR-5)

**Date:** 2026-05-22
**Reviewer:** changelog-audit agent (read-only)
**Scope:** Is `CHANGELOG.md` current after PR 4 + PR 5 landed on `integration`?

## State summary

- `CHANGELOG.md` last touched for v0.3.0 (HUNL substrate + push/fold), dated
  2026-05-21.
- `poker_solver/__init__.py:158` → `__version__ = "0.3.0"`.
- `integration` HEAD: `eee9b4b Integration: merge PR 5 (HUNL postflop solve + memory profiler)`.
- Between v0.3.0 freeze and now: PR 4 (card abstraction, 3041 LOC) + PR 5
  (postflop solve + memory profiler, 2664 LOC) both merged to `integration`.

## Check 1 — v0.3.0 entry coverage

Yes, v0.3.0 has a full entry (lines 20-141). Covers PR 3 (HUNL tree +
14-action abstraction), PR 3.5 (push/fold), hybrid equity calculator,
53 new tests. Accurate and complete for what shipped in the v0.3.0 tag.

**Issue:** v0.3.1 release notes exist on disk
(`docs/release_notes_v0.3.1.md` — pushfold `get_full_range` + chart-load
fixes) but there is **no v0.3.1 section in `CHANGELOG.md`**. This is a
pre-PR-5 gap, not a PR-5 regression.

## Check 2 — v0.4.0 entry needed?

Yes. PR 4 + PR 5 add **net-new public API surface**:

- `poker_solver.abstraction` package: `AbstractionTables`,
  `AbstractionRef`, `build_abstraction`, `load_abstraction`,
  `save_abstraction`, `lookup_bucket`, `resolve_abstraction_ref`,
  `canonicalize_for_suit_iso` (8 symbols).
- `poker_solver.hunl_solver.solve_hunl_postflop` + `HUNLSolveResult`.
- `poker_solver.profiler` package: `MemoryProbe`, `MemoryReport`,
  `StreetMemoryEntry`.
- `HUNLConfig.abstraction` field (additive, default None → preserves
  PR 3 behavior).
- CLI: `precompute-abstraction` subcommand + `solve --hunl-mode postflop`
  + `--board / --stacks / --bet-sizes / --max-memory-gb / --abstraction`
  flags.

Per semver: additive public API → **MINOR bump**. 0.3.0 → 0.4.0 is
correct.

## Check 3 — `__version__` bump

Yes, `poker_solver/__init__.py:158` should bump to `0.4.0` when the
v0.4.0 CHANGELOG entry lands. Note the existing reconciliation debt:
the v0.3.0 changelog already flags that `__version__` was lagging
(0.1.0 → 0.2.0 instead of 0.3.0). That debt is now resolved (it reads
0.3.0), so don't carry the lag forward — bump cleanly to 0.4.0.

## Check 4 — Headline content for v0.4.0

| Item | Belongs in v0.4.0? | Notes |
|---|---|---|
| PR 4 card abstraction (EMD, 256/128/64, suit-iso) | Yes | Not in v0.3.0; was listed in `[Unreleased]` "In progress" |
| PR 5 HUNL postflop solve (`solve_hunl_postflop`) | Yes | New orchestrator + `HUNLSolveResult` |
| PR 5 memory profiler (`MemoryProbe`, `MemoryReport`) | Yes | psutil>=5.9 runtime dep added |
| pytest-timeout wiring | Yes (Internal section) | Dev dep, not public API |
| 9 launch kickoffs staged | **No** | Project-internal scheduling; never in CHANGELOG |
| v0.3.1 pushfold fixes | Backfill as a `[0.3.1]` section above v0.3.0 | Separate from v0.4.0 work |

## Check 5 — `[Unreleased]` section

Currently lists PR 4/5/6/7+ as "in progress." Now that PR 4 + PR 5 are on
`integration`, they should move out of Unreleased into the new v0.4.0
section. PR 6 (Rust port of postflop solve) stays in Unreleased as the
only currently-in-flight item. PR 7+ items also stay.

## Recommended amendments (NOT applied)

### Amendment A: collapse PR 4/5 from `[Unreleased]`

Lines 12-18 currently list PR 4, PR 5, PR 6, PR 7+. Drop PR 4 and PR 5
lines (they shipped). Keep PR 6 and PR 7+. Add a short note that the
next release (v0.4.0) introduces the card abstraction + postflop solver.

### Amendment B: insert `[0.3.1]` backfill section

Between current v0.3.0 and v0.2.0, add a `[0.3.1] - 2026-05-21` section
summarizing the two fixes from `docs/release_notes_v0.3.1.md` (sparse
chart hand-class default + chart-loader robustness). Keeps the changelog
in sync with the on-disk release notes.

### Amendment C: insert `[0.4.0] - 2026-05-22` section

Above v0.3.0 (or above v0.3.1 backfill if Amendment B applied), add the
v0.4.0 section with subsections:
- **Added:** `poker_solver.abstraction` (8 symbols + EMD methodology
  one-liner pointing at `docs/pr4_prep/`); `solve_hunl_postflop` +
  `HUNLSolveResult`; `poker_solver.profiler` (`MemoryProbe`,
  `MemoryReport`, `StreetMemoryEntry`, `.river_ratio` PR-4-revisit
  trigger); CLI `precompute-abstraction` + postflop flags; PR 5 test
  fixtures (`tests/fixtures/hunl_solve_fixtures.py`).
- **Changed:** `HUNLConfig.abstraction` field added (additive, default
  None — PR 3 lossless path preserved); `solve()` dispatch gains
  HUNLPoker postflop routing branch (after push/fold short-circuit);
  CLI `--hunl-mode full` retargeted from PR 5 to PR 9.
- **Dependencies:** `psutil>=5.9` runtime; `pytest-timeout>=2.3` dev.
- **Fixed:** PR 5 audit must-fix #1 — `hunl_solver.py` exploitability
  guard against zero-iteration solves.
- **Internal:** pytest-timeout wiring; `__version__` bumped to 0.4.0.

### Amendment D: bump `__version__`

`poker_solver/__init__.py:158` → `__version__ = "0.4.0"`.

## Version bump recommendation

**Bump now, not after PR 6.** Rationale:

1. PR 5 is on `integration` (the pseudo-main); public API has expanded.
2. PR 6 is a Rust port of PR 5 — it does not add new Python public API.
   It will warrant a PATCH bump at most (or a `0.4.0+rust-postflop`
   internal marker), not a MINOR.
3. Holding the bump until PR 6 lands risks compounding more API debt and
   makes it harder to identify when `solve_hunl_postflop` actually became
   public.
4. The existing v0.3.0 changelog explicitly called out a `__version__`
   lag as a debt item; don't repeat that pattern.

Apply Amendments A + B + C + D in a single docs-only commit on a
`changelog-v0.4.0` branch (or fold into the next PR's docs section if
the project prefers).

## Files inspected

- `/Users/ashen/Desktop/poker_solver/CHANGELOG.md`
- `/Users/ashen/Desktop/poker_solver/poker_solver/__init__.py`
- `/Users/ashen/Desktop/poker_solver/docs/release_notes_v0.3.1.md`
- `git log --oneline integration -20`
- `git show --stat eee9b4b a9d02ca 5832b2f 6565b84` (PR 4 + PR 5 merges)
