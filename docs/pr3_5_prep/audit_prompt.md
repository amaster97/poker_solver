# PR 3.5 audit agent prompt

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh general-purpose `Agent(...)` invocation. Do not include this header in the prompt itself.

---

You are a **fresh code reviewer with NO implementation context**. You did not write any of the code on the `pr-3.5-pushfold` branch and you have not seen the design discussions. Your job is to audit the PR 3.5 implementation (push/fold charts for 2-15 BB stacks) against the spec and report findings in a structured Markdown report.

Treat the spec as the source of truth. Do not make assumptions about behavior not specified there; if you find unspecified behavior, flag it.

## Repository context

- **Repo root:** `/Users/ashen/Desktop/poker_solver`
- **Branch under audit:** `pr-3.5-pushfold` (branched from `integration`)
- **Spec:** `/Users/ashen/Desktop/poker_solver/docs/pr3_5_prep/pr3_5_spec.md` — read this end-to-end before anything else.
- **Implementation log (for context on decisions made during the build, including any mid-stream spec amendments):** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — skim entries dated on or after PR 3.5 kickoff.

## Inputs to read (in order)

1. **The spec:** `/Users/ashen/Desktop/poker_solver/docs/pr3_5_prep/pr3_5_spec.md`. Internalize §3 (scope of charts), §5 (file format), §6 (lookup API), §7 (chart-generation pipeline), §9 (tests), and §10 (critical correctness items).
2. **The branch diff:** run `git diff integration...HEAD` while on `pr-3.5-pushfold`. This gives you everything PR 3.5 changed relative to its base. (Also run `git log integration..HEAD --oneline` for commit-level context.)
3. **The autonomous log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — look for entries about PR 3.5 implementation choices, especially any that note deviations from the spec or decisions made by Agents A / B / C.
4. **The implementation-author generation notes:** `/Users/ashen/Desktop/poker_solver/docs/pushfold_v1_generation_notes.md` — Agent B writes this; it documents the solver-run parameters that produced the committed JSON. Cross-reference against the `iterations_per_solve` / `final_exploitability_bb_per_100` fields in the JSON.
5. **The actual new / modified files:** at minimum
   - `poker_solver/pushfold.py`
   - `poker_solver/charts/__init__.py`
   - `poker_solver/charts/pushfold_v1.json` (don't dump the whole file — schema-check via `python -c` or `jq`)
   - `poker_solver/__init__.py` (re-exports)
   - `poker_solver/solver.py` (dispatch logic)
   - `scripts/generate_pushfold_charts.py`
   - `tests/test_pushfold.py`
   - any other touched files surfaced by the diff

Do not run the chart generator. Do not re-solve. You're auditing the *committed* outputs.

## Audit focus areas (each MUST be touched in the report)

For each focus area, either confirm it's correct (place a one-line entry under "Looks good" with file:line evidence) or flag it under the appropriate severity bucket.

1. **Chart JSON schema integrity.**
   - `version == "v1"`.
   - `stack_depths_bb` contains exactly the 14 integers `[2, 3, 4, ..., 15]`.
   - Both top-level chart keys present: `sb_jam`, `bb_call_vs_jam`.
   - Per (depth, position): every entry's `hand_class` string is in the canonical 169 set (13 pairs + 78 suited + 78 offsuit). Sparse storage (zero-freq omitted) is allowed; the union of (listed + omitted-as-0) must total 169.
   - All frequencies in `[0.0, 1.0]`.
   - Required metadata fields present: `generator`, `generated_at`, `ante`, `small_blind`, `big_blind`, `iterations_per_solve`, `final_exploitability_bb_per_100`, `notes`.

2. **Lookup API correctness.**
   - `get_pushfold_strategy(stack_bb, position, hand) -> float` returns a `float` in `[0.0, 1.0]` for valid inputs.
   - Case-insensitive hand parsing matches `poker_solver.range.parse_range` canonical form ("AKs" / "AKo" distinguished).
   - Hands not in the chart return `0.0` (sparse default), not raise.
   - `get_pushfold_range(stack_bb, position) -> dict[str, float]` returns all 169 keys (including the zero-frequency ones if the caller asks for the full range), or document otherwise.
   - `solve_pushfold(config)` returns a `SolveResult` with `backend == "pushfold_chart"` and the `average_strategy` keys match what `HUNLPoker.infoset_key` produces for jam/fold infosets.

3. **Dispatch logic in `solver.py`.**
   - `solve(game, ...)` correctly identifies short-stack `HUNLPoker` configs (`min(game.config.stacks) // game.config.big_blind <= 15`) and routes to `solve_pushfold`.
   - Dispatch is silent (INFO-level log) per spec §6.
   - Dispatch does NOT trigger for stack > 15 BB.
   - Dispatch does NOT trigger for non-HUNL games.
   - If a `force_tree_solve=True` kwarg exists (per spec §13 risk mitigation), it correctly bypasses the chart path.

4. **I/O discipline — no unexpected disk reads.**
   - The chart JSON must be loaded **once and cached** (module-level cache, `functools.lru_cache`, or equivalent). Repeated calls to `get_pushfold_strategy` must NOT re-read the file.
   - Verify by inspecting the implementation: look for a module-level loaded dict / `@lru_cache` decorator / a `_CHARTS` singleton populated on first access.
   - File should be located via `importlib.resources.files("poker_solver.charts") / "pushfold_v1.json"` (or equivalent), NOT via `__file__`-relative path manipulation.

5. **Generated chart values vs published Sklansky-Chubukov anchors.**
   - For `AA`, `KK`, and `AKs`, the SB-jam frequency at the depths where S-C lists them should be within **5%** of the published S-C jam frequency. (S-C is unilateral-vs-calling-station, *not* HU Nash, so we expect some divergence — but premium hands should be very close to 1.0 at all depths 2-15.)
   - Specifically: `freq("AA", "sb_jam", d) == 1.0` for all `d ∈ [2, 15]`. Same for `KK` and `AKs` at `d ≤ 12`. Flag any deviation.
   - Also confirm: `freq("72o", "sb_jam", d) == 0.0` for `d ≥ 6` (spec §4 landmark).
   - At `d == 2`, the SB jams 100% of all 169 hand classes (spec §9 test 4).

6. **Error handling consistency.**
   - `solve_pushfold` with `eff_stack > 15` raises `ValueError` with a helpful message ("use the tree-builder solver for stacks > 15 BB").
   - `solve_pushfold` with `eff_stack < 2` raises `ValueError` (degenerate case per spec §6).
   - `get_pushfold_strategy` raises `ValueError` for unknown position strings, out-of-range stacks, or malformed hand strings (NOT generic `KeyError` / `IndexError`).
   - Error messages consistently use `ValueError` (not `AssertionError` / `RuntimeError` / `KeyError`). Per PR 3 audit precedent, `AssertionError` is reserved for unreachable invariants only.

7. **Tests use the public API only.**
   - `tests/test_pushfold.py` imports only from `poker_solver` (or `poker_solver.pushfold`) — not from internal modules like `_CHARTS`, `_load_charts`, etc.
   - Tests do not assert on internal cache structures (private `_charts_cache` dicts, `lru_cache` `cache_info()`, etc.). The cache is an implementation detail.
   - Tests that need to verify "loaded once" must do so via a mocked `importlib.resources` patch or by inspecting timing — not by reading the cache directly.

8. **No new dependencies added.**
   - Compare `pyproject.toml` on `pr-3.5-pushfold` vs `integration`. The `[project.dependencies]` and `[project.optional-dependencies]` arrays must be unchanged (no new runtime deps).
   - The only acceptable additions are `[tool.setuptools.package-data]` / `[tool.maturin] include` entries to bundle `poker_solver/charts/*.json` in the wheel (per spec §8 "Modify").
   - Flag any new dep — even a "small" one — as **must-fix**.

9. **License compliance — chart data provenance.**
   - The committed `pushfold_v1.json` MUST be the output of our own DCFR solver (per spec §4), NOT copied from a commercial source (HRC, ICMIZER, GTO Wizard, etc.).
   - Verification path:
     - `docs/pushfold_v1_generation_notes.md` must document the generation run (iterations, exploitability, wall-clock, hostname / env).
     - The `generator` field in the JSON must reference `scripts/generate_pushfold_charts.py`.
     - The `iterations_per_solve` field in the JSON must match the value reported in the generation notes.
     - No comments in `pushfold.py` / `generate_pushfold_charts.py` reference HRC, ICMIZER, GTO Wizard, Holdem Resources, or any other paid push/fold tool by name as a data source.
     - Sklansky-Chubukov tables are public-domain *rankings*, not frequencies — referencing them for *validation* (per spec §4) is fine; referencing them as a data *source* is not.
   - Flag any AGPL / commercial-source contamination as **must-fix**.

10. **Strategic-equivalence collapse correctness (generator-side).**
    - The generator collapses 1326 combo-specific infosets to 169 hand-class entries. Per spec §10, all combos within a class must share strategy within `5e-3`.
    - Confirm the generator asserts this (look for an `assert max_within_class_spread < 5e-3` or similar).
    - Confirm `docs/pushfold_v1_generation_notes.md` reports the maximum within-class spread observed during the run (should be well under `5e-3`).

11. **Convergence gate.**
    - Per spec §10, `final_exploitability_bb_per_100 < 0.05` in the JSON metadata. Read the JSON and verify.
    - The exploitability reported should be the *final* (post-convergence) value, not an early-iteration value.

## Output format

Write your report to `/Users/ashen/Desktop/poker_solver/docs/pr3_5_prep/audit_report.md` with this exact structure (mirrors the PR 3 audit at `docs/pr3_prep/audit_report.md`):

```markdown
# PR 3.5 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-3.5-pushfold
**Diff size:** [N modified + M new files = ±X LoC total]

**Test status:** [pytest tests/test_pushfold.py pytest tests/test_pushfold_regen.py — pass/fail counts; full suite delta]

## Must-fix

[Correctness bugs, license violations, schema-breakage, missing required JSON fields. Anything that would corrupt solver output or violate the spec's hard guarantees. Each item: bullet with file:line + what's wrong + recommended fix.]

[If none: "None found." with one-sentence justification.]

## Should-fix

[Code smell, undocumented behavior, awkward APIs, missing assertions on documented invariants, test holes that could mask future regressions. Each item: bullet with file:line + description + recommended fix.]

## Nice-to-fix

[Style, naming, minor DRY opportunities, comment additions. Cosmetic.]

## Looks good (explicit confirmation of audit focus areas)

[Numbered list 1-11 matching the 11 audit focus areas above. Each item: one-paragraph confirmation with file:line evidence and a concrete check performed.]

## Spec coverage gaps (missing tests)

[Spec items that are implemented but not tested, or tested only indirectly. Each item: which spec section + what's missing + suggested test name.]

## License compliance

[Explicit statement: chart data is computed from our DCFR, generation notes verified, no commercial-source contamination found. Cite the specific evidence (generator field in JSON, generation notes file contents, etc.).]

## Overall verdict

[One of: "READY for commit", "READY for commit AFTER must-fix items resolved", or "NOT READY — see must-fix". Followed by a 2-3 sentence justification.]
```

## Severity rules

Identical to PR 3 audit:

- **must-fix:** correctness bugs (wrong frequencies, schema violations, dispatch bugs that send the wrong game to chart path), license bugs (commercial-source contamination), missing required JSON fields, any new third-party dep. Anything in this bucket blocks the PR.
- **should-fix:** undocumented behavior, awkward error types (`AssertionError` where `ValueError` belongs), missing assertions on documented invariants, test holes around documented behavior, awkward APIs. Tightening opportunities, not bugs. Does not block PR; folds into a follow-up.
- **nice-to-fix:** style, naming, comments, minor DRY. Pure polish.

When in doubt between must-fix and should-fix: if a downstream user could get a **silently wrong answer** from the bug, it's must-fix. If the bug only affects developer experience or surfaces loudly, it's should-fix.

## Procedural notes

- Cite **file paths and line numbers** for every finding ("`poker_solver/pushfold.py:42`", not "the lookup function").
- Quote spec section numbers in must-fix / should-fix items ("spec §6 says ... but impl ...").
- If you find behavior that's neither correct nor a bug because the spec is silent, file it under "Spec coverage gaps" and recommend an explicit decision.
- Do not modify any code. Audit only. Your only write is to `docs/pr3_5_prep/audit_report.md`.
- If you cannot find a file listed in the "Inputs to read" section, note it in the report under the relevant audit focus area and continue auditing what you can.

Begin by reading the spec, then the diff, then the new files. Then write the report.
