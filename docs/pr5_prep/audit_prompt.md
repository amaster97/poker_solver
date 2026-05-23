# PR 5 audit agent prompt

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh general-purpose `Agent(...)` invocation. Do not include this header in the prompt itself.

---

You are a **fresh code reviewer with NO implementation context**. You did not write any of the code on the `pr-5-hunl-postflop` branch and you have not seen the design discussions. Your job is to audit the PR 5 implementation (first HUNL postflop solve + per-street memory profiler, Python tier) against the spec and report findings in a structured Markdown report.

Treat the spec as the source of truth. Do not make assumptions about behavior not specified there; if you find unspecified behavior, flag it.

## Repository context

- **Repo root:** `/Users/ashen/Desktop/poker_solver`
- **Branch under audit:** `pr-5-hunl-postflop` (branched from `integration`)
- **Spec:** `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/pr5_spec.md` — read end-to-end first.
- **Implementation log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — skim PR 5 entries.

## Inputs to read (in order)

1. **The spec:** internalize §3 (architecture), §4 (pipeline stages A–E), §5 (files to create), §6 (files to modify, especially the 2026-05-21 amendment about dispatch composition cross-referencing PR 9 §6), §7 (memory profiler design), §8 (fixtures + convergence targets), §9 (test plan), §11 (critical correctness items), §14 (open decisions — note that N7 locks `HUNLSolveResult` as a subclass of `SolveResult`).
2. **The branch diff:** `git diff integration...HEAD` while on `pr-5-hunl-postflop`. Also `git log integration..HEAD --oneline`.
3. **The autonomous log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md`.
4. **The actual new / modified files:** at minimum
   - `poker_solver/hunl_solver.py`
   - `poker_solver/profiler/__init__.py`
   - `poker_solver/profiler/memory.py`
   - `poker_solver/solver.py` (routing branch added)
   - `poker_solver/cli.py` (`--hunl-mode postflop` and flags)
   - `poker_solver/__init__.py` (re-exports)
   - `pyproject.toml` (`psutil>=5.9` added)
   - `tests/test_hunl_postflop_solve.py`
   - `tests/test_memory_profiler.py`
   - `tests/fixtures/hunl_solve_fixtures.py`
   - any other touched files

Do not run long solves. Audit the *committed* code.

## Audit focus areas (each MUST be touched in the report)

For each focus area, either confirm correct ("Looks good" with file:line evidence) or flag under the appropriate severity.

1. **Memory budget enforcement.**
   - `solve_hunl_postflop(..., max_memory_gb=14.0)` enforces the budget between iteration chunks (NOT inside the CFR recursion — that would slow it). Spec §4 Stage C.
   - When the budget is exceeded, raises `MemoryError` (NOT `RuntimeError` / `Exception`) and **the exception carries the partial `MemoryReport` as its args[1]**. Spec §7.7 + §11 #9.
   - The error message is **actionable**: mentions river_ratio, suggests tightening abstraction or restricting bet sizes. Spec §7.7 code block.
   - `test_postflop_solve_memory_budget_aborts_cleanly` (§9.1 #10) exists and verifies this.

2. **`MemoryReport.river_ratio` reports the right number.**
   - Per spec §8.5 "Quantitative answer to 'is the river layer <30%' question": `river_ratio` is the river layer's share of **total solver arrays** (`solver_arrays_total_bytes`), NOT total grand bytes including abstraction table + overhead.
   - Verify the formula in `profiler/memory.py`. A different denominator → wrong PLAN.md trigger.
   - The property docstring documents this precisely.

3. **OOM is caught and reported cleanly (NOT a hard crash).**
   - The `MemoryError` path is tested. The test asserts the partial `MemoryReport` is returned via `args[1]` and has `grand_total_bytes > 0`. Spec §9.1 #10.
   - The caller can `del solver; gc.collect()` to release memory between solves; documented behavior.

4. **Intuition gauntlet: at least one MDF and one polarization test.**
   - `test_postflop_solve_intuition_gauntlet_dry_overpair_bets` (§9.1 #12) exists: P0 overpair on dry flop → bet actions >50% weight. Soft assertion.
   - `test_postflop_solve_intuition_gauntlet_polarization_on_monotone` (§9.4) exists: vulnerable overpair (Kc Ks) on monotone low connected (8h 7h 6h) → polarized (`max(probs) > 0.6` OR `min(probs) < 0.05` for non-fold actions).
   - Per PLAN.md §4 "Poker-intuition gauntlet": MDF on overpair vs simple bet, fold-equity on all-in shoves, polarization on monotone boards. PR 5 must cover MDF + polarization minimum.

5. **`psutil` calibration check (Test 6 of §9.2) within 10%.**
   - The `MemoryReport.rss_calibration_error` property is computed: `(rss_observed - rss_baseline - predicted) / (rss_observed - rss_baseline)`.
   - `test_memory_profiler_matches_rss_within_10pct` solves Fixture 2 for 200 iterations and asserts `abs(error) < 0.10`. Spec §7.6 + §9.2 #6 + §11 #4.
   - The baseline (`rss_baseline_bytes`) is captured at `MemoryProbe` construction time, BEFORE allocating solver state.

6. **Infoset-key parsing handles both formats.**
   - `_parse_street_from_key(key)` handles **lossless** (PR 3 format: `f"{hole}|{board}|{street}|{history}"`) AND **bucketed** (PR 4 format: `f"b{bucket_id}|{street}|{history}"`). Spec §7.3.
   - Tests 8 and 9 of §9.2 exercise both formats.
   - Defensive: unknown / malformed keys → log warning, lump into "unknown" bucket, do NOT crash (§9.2 #10).

7. **Dispatch composition (Stage A validation + `solver.py` routing).**
   - **Per the 2026-05-21 spec amendment in §6:** PR 5 cross-references **PR 9 §6 as canonical** for the full dispatch composition. PR 5 implements ONLY the postflop branch.
   - Push/fold (PR 3.5) short-circuit MUST execute BEFORE PR 5's postflop branch. A `HUNLConfig(starting_street=Street.FLOP, starting_stack=1500)` config (15 BB) still hits the chart.
   - `_validate_postflop_config` rejects preflop with `ValueError("PR 5 is postflop-only; preflop solver lands in PR 9.")`. Tested in §9.1 #5.
   - Board length matches `starting_street`: flop=3, turn=4, river=5. Spec §4 Stage A.
   - `rake_rate == 0.0 and rake_cap == 0` asserted. §4 Stage A.
   - Routing change to `solver.solve()` doesn't perturb Kuhn/Leduc behavior. §11 #6.

8. **`HUNLSolveResult` is a SUBCLASS of `SolveResult` (NOT a tuple, NOT a wrapper).**
   - Per spec §14 #3 (LOCKED via consistency review N7 dated 2026-05-21): `HUNLSolveResult(SolveResult)` adds `memory_report: MemoryReport`. Tuple form rejected.
   - PR 9's `PreflopSolveResult` and PR 11 depend on this subclass form.
   - Flag immediately if the impl uses a tuple `(SolveResult, MemoryReport)` or a separate dataclass wrapper.

9. **Hyperparameters unchanged.**
   - DCFR α=1.5, β=0, γ=2.0 (PLAN.md lock). No `--alpha`/`--beta`/`--gamma` CLI flags exposed for HUNL postflop. Spec §11 #7.
   - The DCFR loop uses `DCFRSolver` (`poker_solver/dcfr.py`) **unchanged**. PR 5 instruments from outside via `MemoryProbe` — verify `dcfr.py` is not modified. Spec §5 "Not modified."

10. **`hunl.py` is NOT modified by PR 5.**
    - Spec §6 "Not modified" + the 2026-05-21 amendment note that PR 6 + PR 8 modify `hunl.py` (additive: `_serialize_hunl_config`, `use_pcs` field), but PR 5 itself touches nothing in this file. Confirm via `git diff integration -- poker_solver/hunl.py`.

11. **`psutil` is the only new dependency.**
    - Compare `pyproject.toml`. New runtime deps: only `psutil>=5.9` (MIT, cross-platform, small).
    - Spec §6 "Modify" `pyproject.toml`. Anything else → must-fix.

12. **Determinism + reproducibility.**
    - Same seed + config + abstraction → bit-identical strategy table (within float tolerance). Spec §11 #10.
    - Profiler does NOT introduce nondeterminism via dict iteration order. The `per_street` tuple is ordered (FLOP, TURN, RIVER, optionally preflop) deterministically.

13. **`solver.solve()` regression check.**
    - All PR 1 (Kuhn), PR 2 (Leduc), PR 3 (HUNL tree-builder + `tiny_subgame` mode), PR 3.5 (push/fold), PR 4 (abstraction) tests still pass unchanged.
    - The routing branch is additive — preflop HUNL still raises `NotImplementedError` pointing at PR 9 (was PR 5).

## Output format

Write your report to `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/audit_report.md` with this exact structure:

```markdown
# PR 5 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-5-hunl-postflop
**Diff size:** [N modified + M new files = ±X LoC total]

**Test status:** [pytest tests/test_hunl_postflop_solve.py tests/test_memory_profiler.py — pass/fail; full suite delta]

## Must-fix

[Correctness bugs (wrong river_ratio formula, OOM crash instead of clean abort, HUNLSolveResult not a SolveResult subclass, hyperparam drift, new third-party dep beyond psutil, regression in PR 1-4 tests, dispatch ordering wrong). Each: file:line + what + fix.]

[If none: "None found." + justification.]

## Should-fix

[Code smell, undocumented behavior, awkward APIs, missing assertions, test holes (e.g., gauntlet missing polarization or MDF). Each: file:line + description + fix.]

## Nice-to-fix

[Style, naming, comments. Cosmetic.]

## Looks good (explicit confirmation of audit focus areas)

[Numbered list 1-13 matching the 13 audit focus areas above. Each: one-paragraph confirmation with file:line evidence.]

## Spec coverage gaps (missing tests)

[Spec items implemented but not tested, or only tested indirectly. Each: section reference + what's missing + suggested test name.]

## License compliance

[Explicit statement: no AGPL contamination (e.g., from postflop-solver's `base.rs::memory_usage`); architectural patterns adopted (vec_memory_usage shape) re-derived, not copied. Cite specific module docstrings.]

## Overall verdict

[One of: "READY for commit", "READY for commit AFTER must-fix items resolved", or "NOT READY — see must-fix". 2-3 sentence justification.]
```

## Severity rules

- **must-fix:** correctness bugs (wrong memory accounting, OOM-crash-not-abort, HUNLSolveResult not subclass), license bugs, new third-party deps beyond `psutil`, regressions in PR 1-4 tests, dispatch ordering wrong. Blocks PR.
- **should-fix:** undocumented behavior, awkward error types, missing assertions on documented invariants (e.g., calibration test missing on a fixture), test holes (gauntlet missing a category). Doesn't block.
- **nice-to-fix:** style, naming, comments. Pure polish.

When in doubt: silently-wrong memory numbers or silently-wrong strategy outputs → must-fix. Developer-experience issues → should-fix.

## Procedural notes

- Cite **file paths and line numbers** for every finding.
- Quote spec section numbers (e.g., "spec §7.7 says ... but impl ...").
- Spec-silent behavior → "Spec coverage gaps" with explicit-decision recommendation.
- Do not modify code. Audit only. Your only write is to `docs/pr5_prep/audit_report.md`.

Begin by reading the spec (especially the 2026-05-21 amendments on dispatch + HUNLSolveResult lock), then the diff, then the new files. Then write the report.
