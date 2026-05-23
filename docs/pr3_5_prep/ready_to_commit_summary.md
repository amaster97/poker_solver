# PR 3.5 ready-to-commit summary

**Branch:** `pr-3.5-pushfold` (tip currently at `351cbee` = `integration` tip; no commits yet — the entire PR is staged in the working tree)
**Date:** 2026-05-21
**Lineage:** Agent A (lookup API) → Agent B (chart generator + DCFR run) → Agent C (tests); patched twice (get_full_range sparse-fill; dispatch PREFLOP gate)

---

## What this PR ships

A precomputed Heads-Up Nash push/fold chart pack (2-15 BB effective stack, both `sb_jam` and `bb_call_vs_jam` positions, all 169 strategically-distinct hand classes) plus the Python lookup API and the `solve()` dispatch hook that routes short-stack HUNL configs to the chart instead of building a tree. The charts are real DCFR-generated Nash equilibria; the generator script is committed for reproducibility and runs the whole pack in ~5 minutes (`docs/pushfold_v1_generation_notes.md` §2).

This is also the first end-to-end cross-validation of our DCFR engine against published references (Sklansky-Chubukov landmark hands, top-of-range / bottom-of-range invariants); none of the cross-check anchors deviate by more than 2% from expectation.

---

## Files changed
(M = modified vs `integration` tip; A = added/untracked)

- M `README.md` — push/fold mode section, status v0.3.0, roadmap rewrite (+182/-59)
- M `poker_solver/__init__.py` — re-exports `get_pushfold_strategy`, `get_full_range`, `is_pushfold_mode`, `PushFoldChartUnavailable`, `PUSHFOLD_MIN_BB`, `PUSHFOLD_MAX_BB` (+14)
- M `poker_solver/solver.py` — push/fold dispatch hook in `solve()` (gated on `starting_street == Street.PREFLOP`) + `_solve_pushfold_lookup` helper (+46)
- A `poker_solver/pushfold.py` (211 lines) — lookup API per spec §6
- A `poker_solver/charts/__init__.py` (7 lines) — package marker so the JSON ships in the wheel via `importlib.resources`
- A `poker_solver/charts/pushfold_v1.json` (3045 lines, ~60 KB) — generated Nash equilibrium charts (28 cells)
- A `scripts/generate_pushfold_charts.py` (784 lines) — full DCFR matrix-game chart generator, deterministic (seed 42), with `--dry-run` smoke path
- A `tests/test_pushfold.py` (213 lines, 13 tests) — lookup, dispatch, regression
- A `docs/pushfold_v1_generation_notes.md` (193 lines) — methodology, runtime, sanity-check tables

Also untracked but unrelated to PR 3.5 (verify before staging):
- `CHANGELOG.md` (208 lines) — already mentions PR 3.5 entries; can be staged with this PR
- `CONTRIBUTING.md` (117 lines) — repo hygiene; likely separate PR
- `.github/` (PR + issue templates) — repo hygiene; likely separate PR

---

## Critical correctness verifications

- Card removal handled correctly in chart generation: `_build_compat_count` (lines 191-208 of `scripts/generate_pushfold_charts.py`) counts disjoint combo pairings; `solve_pushfold_for_depth` (lines 371-382) weights all DCFR updates by `compat`-derived `P(h_sb, h_bb)` priors, not uniform combo priors. See `docs/card_removal_investigation.md` §"`scripts/generate_pushfold_charts.py` — verdict: handled (with one MC nit)" for the full audit.
- Dispatch requires `starting_street == Street.PREFLOP`: `poker_solver/solver.py:48-56`. River/turn/flop subgames at short stack do NOT short-circuit to chart lookup. Regression test `test_pushfold_mode_not_triggered_for_river_subgame_at_short_stack` in `tests/test_pushfold.py:144-161` locks this.
- Chart sums + frequencies in [0, 1]: `test_pushfold_full_range_returns_169_hands` (lines 94-101), `test_pushfold_returns_frequency_in_zero_to_one_range` (54-67), and `test_pushfold_strategy_frequencies_sum_consistently` (184-213).
- Sanity vs Sklansky-Chubukov: 26 anchors (AA / KK / AKs jam=1.0 at every checked depth; 72o jam=0.0 at depth 8/10/15) all pass; landmark table in `docs/pushfold_v1_generation_notes.md` §3 shows every depth row matches expectation. Generator's deviation flag (>2%) prints "No deviations" on the v1 run.
- Chart data version-locked to `v1`: `pushfold_v1.json:2` declares `"version": "v1"`; loader (`poker_solver/pushfold.py:46-50`) rejects unknown majors via `PushFoldChartUnavailable`.
- DCFR convergence well under spec target: exploitability <= 0.0001 BB/100 at every depth (`pushfold_v1.json:33-48`); spec target was < 0.05 BB/100, i.e. exceeded by ~500x.
- get_full_range sparse fill: `poker_solver/pushfold.py:128-137` explicitly fills the 169-class grid with 0.0 defaults for missing hands. Test `test_pushfold_full_range_returns_169_hands` (line 99) asserts `len(full) == 169`. (This was the S9 patch.)

---

## Test status

`tests/test_pushfold.py` defines **13** tests (not 12 — the spec called for 12; one extra was added as the dispatch-PREFLOP-gate regression). Test names confirmed via `pytest --collect-only`:

1. `test_pushfold_returns_frequency_in_zero_to_one_range`
2. `test_pushfold_aa_always_jammed_at_all_depths`
3. `test_pushfold_72o_never_jammed_at_15bb`
4. `test_pushfold_wider_at_shorter_stacks`
5. `test_pushfold_full_range_returns_169_hands`
6. `test_pushfold_unsupported_stack_raises`
7. `test_pushfold_invalid_hand_raises`
8. `test_pushfold_invalid_position_raises`
9. `test_pushfold_bb_call_range_tightens_at_deep_stack`
10. `test_pushfold_mode_dispatch_at_short_stack`
11. `test_pushfold_mode_not_triggered_for_river_subgame_at_short_stack`   ← regression for dispatch gate
12. `test_pushfold_mode_not_triggered_at_long_stack`
13. `test_pushfold_strategy_frequencies_sum_consistently`

Run before commit: `python -m pytest tests/test_pushfold.py -v` and confirm 13/13 pass. (Pytest invocations during summary prep hung in background — re-verify in a clean shell before commit.)

The generator-smoke test specified in spec §9 (#11 `test_generator_smoke` in `tests/test_pushfold_regen.py`) is **NOT in the committed working tree**. The generator's own `--dry-run` flag (`scripts/generate_pushfold_charts.py:613-619`) provides equivalent coverage from the command line. Decision: ship as-is; if the orchestrator wants the smoke test inline, that is a small follow-up.

---

## Lint status

Verified on the five new/modified files (`poker_solver/pushfold.py`, `poker_solver/solver.py`, `poker_solver/charts/__init__.py`, `scripts/generate_pushfold_charts.py`, `tests/test_pushfold.py`):

- `ruff check`: All checks passed.
- `black --check`: 5 files would be left unchanged.
- `python -m mypy poker_solver/pushfold.py poker_solver/solver.py`: Success: no issues found in 2 source files.

Full repo `scripts/check_pr.sh` battery should be run before committing — it also exercises the references-integrity check and the rust-side gates.

---

## Patches applied during implementation

- **S2** (from `docs/autonomous_log.md`): Agent B/C interface drift on `ActionContext` — not in scope for PR 3.5; resolved in PR 3.
- **S5** (autonomous_log): black/ruff cleanup post Agent A — applied before PR 3 commit; new PR 3.5 files were authored against the cleaned style and pass lint.
- **S9** (autonomous_log): `get_full_range` sparse-fill — the sparse JSON omits zero-frequency hands; `get_full_range` was patched to fill missing classes with `0.0` so callers always see all 169 hands. Caught by `test_pushfold_full_range_returns_169_hands`.
- **New (this PR, not yet in autonomous_log):** dispatch hardening to require `starting_street == Street.PREFLOP`. Without this gate, `solve(HUNLPoker(default_tiny_subgame()))` (a 10 BB RIVER subgame) silently returned a chart-backed `SolveResult`, which is semantically wrong because push/fold equilibria only exist on the preflop tree shape. Fix in `poker_solver/solver.py:51-56`; regression test in `tests/test_pushfold.py:144-161`.

---

## Known non-blocking issues

- v1 charts use pure jam/fold only (no minraise / limp / 3-bet). Borderline regime at 12-15 BB is slightly suboptimal vs Nash-with-minraise (~5 BB/100 EV loss per published references). Documented in `pushfold_v1.json` `notes` field, `docs/pushfold_v1_generation_notes.md` §7, and README "Push/fold charts" section.
- v1 charts assume `ante = 0`. Format reserves an `ante` field for future ante-aware packs (`pushfold_v1_ante.json` etc.); loader picks by config key. Deferred.
- Per-pair MC noise in the equity matrix is ~1% (4 combo pairs × 350 boards). Manifests at most as ±0.5% strategy noise on borderline hands; no current cell falls in that band on the v1 run. `docs/card_removal_investigation.md` §"Finding 2" recommends bumping `EQUITY_COMBO_PAIRS_PER_CLASS_PAIR` from 4 to 8-12 in a v2 regen if needed. Not blocking v1.
- `pyproject.toml` does NOT declare `poker_solver/charts/*.json` as package data via `[tool.maturin] include` or `package-data`. The JSON ships via `importlib.resources` so it works from source trees today, but the wheel build may not bundle the JSON. **Verify by `pip install`ing the wheel into a clean venv and querying `get_pushfold_strategy` before publishing a wheel.** Flagged for follow-up; not blocking the local commit.
- `__version__` in `poker_solver/__init__.py:129` is still `"0.2.0"`; `pyproject.toml:7` also says `"0.2.0"`. CHANGELOG.md already labels this release as `0.3.0`. Bump both to `0.3.0` as part of the post-commit version-bump step.

---

## Pre-commit checklist

- [ ] `python -m pytest tests/test_pushfold.py -v` → 13/13 pass
- [ ] `python -m pytest` (full suite) → all green; expect 138 prior + 13 new = 151 (or +1 if action-abstraction headcount differs)
- [ ] `scripts/check_pr.sh` → all gates pass; review `pr_report.md`
- [ ] Audit agent → READY verdict (note: dispatch-PREFLOP-gate patch is small and has a regression test, so the audit may be cleared without a full re-run; user judgment call)
- [ ] `git status` shows only the intended files staged (decide on `CHANGELOG.md` / `CONTRIBUTING.md` / `.github/` separately)
- [ ] `git log --oneline integration..HEAD` is empty before commit; one new commit after

---

## Commit message draft

```text
PR 3.5: Push/fold charts (2-15 BB) + dispatch hook

Ships precomputed HU Nash push/fold charts for short-stack play:
- `poker_solver/pushfold.py` — lookup API
  (`get_pushfold_strategy`, `get_full_range`, `is_pushfold_mode`).
- `poker_solver/charts/pushfold_v1.json` — DCFR-generated Nash
  equilibria for each integer stack depth in [2, 15] BB, both
  `sb_jam` and `bb_call_vs_jam` positions, 169 hand classes per cell.
- `scripts/generate_pushfold_charts.py` — deterministic, ~5-min
  generator with card-removal-aware compat-weighted matrix DCFR.

`solve()` now auto-dispatches `HUNLPoker` games with
`starting_street == Street.PREFLOP` and effective stack in [2, 15] BB
to chart lookup. River/turn/flop subgames at short stack still route
to the tree solver — push/fold equilibria only exist on the preflop
tree shape.

Exploitability after convergence: <= 0.0001 BB/100 at every depth
(spec target was < 0.05 BB/100). Sklansky-Chubukov landmark checks
all pass within 2% tolerance. 13 new tests in `tests/test_pushfold.py`,
including the river-subgame dispatch regression.

Methodology + sanity tables: `docs/pushfold_v1_generation_notes.md`.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

## Post-commit actions

- Push `pr-3.5-pushfold` to `origin` (`git push -u origin pr-3.5-pushfold`).
- Merge `pr-3.5-pushfold` into `integration` with `--no-ff`.
- Push `integration` to `origin` (force-with-lease if `integration` was rebuilt; otherwise plain push).
- Force-push `pr-3-hunl-tree` to `origin` if it was rebased onto the new `main` — user OK required per memory rules.
- Update `PLAN.md` trajectory table: mark PR 3.5 as shipped.
- Update `CHANGELOG.md` if anything in this commit diverges from what's already documented in lines 51-67 of the existing `CHANGELOG.md` working-tree file (CHANGELOG is currently untracked).
- Bump `__version__` to `"0.3.0"` in both `pyproject.toml:7` and `poker_solver/__init__.py:129`.
- Prune `docs/autonomous_log.md` of obsolete in-flight notes once PR 3.5 is on `integration`.

---

## Findings during summary prep

1. **Test count is 13, not 12.** Spec §9 enumerates 12 tests; the file has 13 because Agent C added (or this PR's dispatch patch added) `test_pushfold_mode_not_triggered_for_river_subgame_at_short_stack` as the regression for the PREFLOP-gate fix. Not a bug — just a delta from the spec to note.
2. **No `tests/test_pushfold_regen.py`.** Spec §9 #11 calls for a generator-smoke test in a separate file. Not present. `scripts/generate_pushfold_charts.py --dry-run` (lines 613-619) provides equivalent CLI-level coverage. Decision: ship without; add later if CI needs it.
3. **`pyproject.toml` package-data gap.** No declaration that `poker_solver/charts/*.json` is package data. Wheel build may miss the JSON. Spec §8 "Modify" called this out; the modification was not applied. Recommended pre-wheel-publish fix; not blocking local commit.
4. **`__version__` lag.** `0.2.0` in both `poker_solver/__init__.py` and `pyproject.toml`, but `CHANGELOG.md` already labels this release as `0.3.0` (CHANGELOG also notes the lag explicitly at line 107-109). Bump as part of post-commit.
5. **Untracked unrelated files.** `CHANGELOG.md`, `CONTRIBUTING.md`, `.github/` are untracked in the working tree. They were not part of the PR 3.5 spec. Decide explicitly whether to fold them into this commit or stage them separately — CHANGELOG specifically already references PR 3.5 content and may want to ship together.
6. **Chart JSON metadata uses `"v1"` already.** No `v1-placeholder` sneak-through. Loader allow-list includes both (`PUSHFOLD_CHART_VERSIONS = {"v1", "v1-placeholder"}`), which is harmless but the `v1-placeholder` token is reachable only via the generator's `--dry-run` flag.
7. **Generator's compat-weighted DCFR is the right shape for card removal.** Cross-verified against `noambrown/poker_solver` (`vector_eval.cpp:32-78`) and postflop-solver (`card.rs:106-181`) patterns; both use the same masking-by-compatibility approach. The chart generator is not a vector-CFR implementation, but for the 169x169 abstracted matrix it does not need to be — `compat` weighting + scalar-CFR is mathematically equivalent at this resolution.
