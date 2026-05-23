# PR 9 audit agent prompt

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh general-purpose `Agent(...)` invocation. Do not include this header in the prompt itself.

---

You are a **fresh code reviewer with NO implementation context**. You did not write any of the code on the `pr-9-hunl-preflop` branch and you have not seen the design discussions. Your job is to audit the PR 9 implementation (HUNL preflop solve — both Python + Rust tiers) against the spec and report findings in a structured Markdown report.

Treat the spec as the source of truth. Do not make assumptions about behavior not specified there; if you find unspecified behavior, flag it.

## Repository context

- **Repo root:** `/Users/ashen/Desktop/poker_solver`
- **Branch under audit:** `pr-9-hunl-preflop` (branched from `integration`)
- **Spec:** `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/pr9_spec.md` — read end-to-end. Note the 2026-05-21 amendments (§6 is canonical dispatch; tolerance cluster 5e-3 / 1e-3 — was misquoted as 1e-4; end-to-end <0.05 BB/hand target added).
- **Implementation log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — skim PR 9 entries.

## Inputs to read (in order)

1. **The spec:** internalize §3 (architecture — blueprint + subgame refinement, Pluribus pattern), §4 (files to create), §5 (files to modify, especially the canonical-class chance generator in `hunl.py`), §6 (canonical dispatch composition — REFERENCED BY PR 3.5 AND PR 5), §7 (blueprint design + end-to-end target), §8 (subgame refinement), §10 (test plan), §13 (risks, especially row about tolerance), §17 (success criteria).
2. **The branch diff:** `git diff integration...HEAD` while on `pr-9-hunl-preflop`. Also `git log integration..HEAD --oneline`.
3. **The autonomous log:** PR 9 entries.
4. **The actual new / modified files:** at minimum
   - `poker_solver/preflop_solver.py`
   - `poker_solver/blueprint.py`
   - `poker_solver/subgame_refiner.py`
   - `poker_solver/hunl.py` (canonical-class chance generator added)
   - `poker_solver/solver.py` (preflop dispatch branch added)
   - `poker_solver/cli.py` (`--hunl-mode preflop` and flags)
   - `poker_solver/__init__.py` (re-exports)
   - `crates/cfr_core/src/preflop.rs`
   - `crates/cfr_core/src/blueprint.rs`
   - `crates/cfr_core/src/subgame.rs`
   - `crates/cfr_core/src/lib.rs` (PyO3 bindings extended)
   - `tests/test_hunl_preflop_blueprint.py`
   - `tests/test_hunl_preflop_refinement.py`
   - `tests/test_hunl_preflop_integration.py`
   - `tests/test_preflop_diff.py`
   - `tests/fixtures/hunl_preflop_fixtures.py`
   - any other touched files

## Audit focus areas (each MUST be touched in the report)

For each focus area, either confirm correct ("Looks good" with file:line evidence) or flag under the appropriate severity.

1. **Dispatch composition matches PR 9 §6 canonical (THIS IS THE AUTHORITATIVE SECTION).**
   - PR 9 §6 is the canonical source for HUNL dispatch ordering. PR 3.5 §6 and PR 5 §6 cross-reference this section.
   - **Required order** in `solver.solve()`:
     1. **Short-stack short-circuit FIRST** (regardless of `starting_street`): if `isinstance(game, HUNLPoker) and eff_stack_bb <= 15` → `pushfold.solve_pushfold(config)` (PR 3.5).
     2. **Stack-depth ceiling:** if `eff_stack_bb > 250` → `ValueError(f"Stack depth {eff_stack_bb} BB > 250 BB max.")`
     3. **Postflop branch** (PR 5): `starting_street >= Street.FLOP` → `solve_hunl_postflop(config, ...)`.
     4. **Preflop branch** (PR 9): `starting_street == Street.PREFLOP` → `solve_hunl_preflop(config, abstraction=..., ...)`.
   - **Locked boundary tests** must exist (per §6 "Boundary tests"):
     - `test_preflop_dispatch_pushfold_at_15bb` — 1500 cents = 15 BB → chart (NOT preflop solver).
     - `test_preflop_dispatch_solver_at_16bb` — 1600 cents = 16 BB → preflop solver.
     - `test_preflop_dispatch_error_at_251bb` — 25100 cents → ValueError.
   - **Critical invariant:** push/fold short-circuit MUST execute before postflop or preflop branches. A `HUNLConfig(starting_street=Street.PREFLOP, starting_stack=1500)` (15 BB preflop) hits the chart, NOT the preflop solver.

2. **Diff test tolerance: 5e-3 per-action / 1e-3 per-spot game value.**
   - Per spec §10.4 (post-2026-05-21 amendment, resolving consistency-review I3): PR 9 adopts the **PR 6 / PR 7 / PR 8 tolerance cluster** — `5e-3` per-action probability + `1e-3 × base_pot` per-spot game value.
   - **Earlier draft said `1e-4` — reconciled to `5e-3 / 1e-3`.** Per §13 risk row mentioning "was previously misquoted as 1e-4."
   - **Anti-pattern check:** if `tests/test_preflop_diff.py` uses tolerance < 5e-3 (e.g., 1e-4), flag as must-fix — the test will silently fail or pass spuriously.
   - All four diff tests use the same tolerance cluster.

3. **Blueprint convergence target.**
   - Per spec §7.4: blueprint exploitability `< 0.5 BB/100` on every reached preflop infoset (loose because the blueprint is intentionally coarse).
   - `test_blueprint_converges_at_100bb` (§10.1 #1) asserts this (in `slow` form) or asserts a relaxed CI form (`< 5.0 BB/100` at 500 iterations).
   - Default blueprint config: **1 size (0.75 pot) + all-in, 1-cap** for postflop menu (§7.1); full preflop menu (§7.2); 256/128/64 abstraction (§7.3); 50,000 blueprint iterations (§7.4).

4. **Subgame refinement warm-start correctness.**
   - Per spec §8.3: refined postflop solve uses blueprint's strategy as a **regret-table warm start** — for every postflop infoset key that exists in BOTH the blueprint and the refinement tree, copy the blueprint's regret values into the refinement's regret table at iteration 0.
   - Infosets that exist only in the refinement tree (because refinement has the full 6-size menu and blueprint had 1–2 sizes) start at zero regret.
   - Tested: `test_refinement_warm_start_speeds_convergence` (§10.2 #2) — warm-start solve converges in fewer iterations than cold-start.
   - **Soft assertion allowance:** failure prompts user review, not auto-fix.

5. **Range extraction from blueprint.**
   - Per spec §8.2: `p0_range[hand_class] = Σ_paths reach_prob(path_to_subgame_root | hand_class)` where the reach is computed under the blueprint's strategy.
   - Non-uniform ranges (some hands reach with high probability, others rarely).
   - Tested: `test_refinement_ranges_extracted_correctly` (§10.2 #5) — for 3-bet pot subgame, `p0_range["AA"] > p0_range["72o"]`.

6. **Canonical-class preflop chance generator (`hunl.py` modification).**
   - Per spec §5 "Files to modify" + §13 risk row: a new `_enumerate_preflop_hole_outcomes_canonical()` generator added to `hunl.py` that yields the 169×169 unique hand-class chance outcomes with **correct combinatorial weights** (pairs = 6 combos, suited = 4, offsuit = 12).
   - Opponent class enumeration respects blockers (e.g., AA when hero has AA leaves 0 combos of AA for the opponent).
   - The default 1.6M-combo generator is preserved unchanged (per §14 #8 decision).
   - The `BlueprintResult` builder passes `chance_strategy="canonical_classes"` automatically.
   - Tested: `test_preflop_canonical_chance_weights_correct` (mentioned in §13 risk row) — validates against brute-force enumeration on a tiny subset.

7. **End-to-end exploitability target: < 0.05 BB/hand on Pio validation fixture.**
   - Per the 2026-05-21 spec amendment to §7.4 + §17: combined preflop + refinement exploitability `< 0.05 BB/hand` on the HU NL cash-game 100 BB starting stacks, no ante, $0.50/$1.00 blinds (Pio's published reference setup).
   - Tested: `test_combined_exploitability_under_0_05_bb_per_hand` (§10.3 #5, NEW). Marked `@pytest.mark.slow`. CI variant: 5k blueprint + 2k refine → `< 0.5 BB/hand`.
   - Justification: matches "professional standard" of < 0.5% pot from `gtow_how_solvers_work.md`; ~7× looser than Pio benchmark given coarser blueprint.

8. **PR 5 `MemoryProbe` 10% calibration inheritance.**
   - Per spec §12 (consistency review I4): PR 9 explicitly inherits the **10% psutil RSS calibration check** from PR 5 §7.6. Each blueprint solve AND each subgame refinement solve runs the calibration.
   - If the larger preflop tree exceeds the 10% bound, that's a profiler-correctness signal worth investigating — flag in test output.

9. **Sequential subgame refinement memory hygiene.**
   - Per spec §12: each subgame is solved sequentially with `max_memory_gb` budget. Between subgames, previous solver's regret tables + infoset dicts are explicitly dropped (`del solver` and `gc.collect()`).
   - The integration test verifies no memory leak across the chain.

10. **DCFR hyperparameters unchanged.**
    - Per spec §1 "Not modified" + §2: same hyperparameters as PR 1-8 (α=1.5, β=0, γ=2.0). No `--alpha` / `--beta` / `--gamma` CLI flags exposed.
    - `dcfr.py` unchanged. `abstraction/` consumed read-only. `hunl_solver.py` (PR 5) called but not modified.

11. **Reach-threshold filtering.**
    - Per spec §8.1: subgame is refined if reach probability under blueprint exceeds `reach_threshold` (default 1e-3).
    - Tested: `test_refinement_respects_reach_threshold` (§10.2 #4) — `refined_subgames.keys()` all have `reach > 0.1` when `reach_threshold=0.1`; `unrefined_subgames` all have `reach <= 0.1`.

12. **Rust ↔ Python differential test parity.**
    - Per spec §10.4: four diff tests in `tests/test_preflop_diff.py`. Tolerance is the locked **5e-3 / 1e-3** cluster from §10.4.
    - Blueprint strategies match, refinement strategies match, combined strategy table matches, dispatch paths consistent across tiers (15 BB → chart; 100 BB → solver; 251 BB → error).
    - The Rust ports (`preflop.rs`, `blueprint.rs`, `subgame.rs`) are mechanical translations matching PR 6 pattern.

13. **PR 3.5 charts unchanged.**
    - Per spec §5 "Not modified": `poker_solver/charts/pushfold_v1.json` is unchanged. PR 9 only dispatches to it via the canonical §6 order.
    - PR 3.5 tests still pass unchanged.

14. **Published-reference SB open-raise validation.**
    - Per spec §10.3 #4 (`test_published_ref_sb_open_raise_100bb`): at 100 BB, for SB-first-action infoset:
      - `AA`: ≥ 95% non-fold (open) probability.
      - `72o`: ≥ 60% fold.
      - `JJ`: open frequency in `[0.85, 1.0]`.
    - Loose anchors — tight comparison deferred to follow-up PR.

15. **License hygiene.**
    - No code copied from AGPL repos (`postflop-solver`, `TexasSolver`) — only architectural inspiration from PLUS Pluribus paper (cited from `references/papers/`).
    - MIT/Apache patterns from `noambrown_poker_solver` may be ported with attribution.
    - Each new Rust file in `crates/cfr_core/src/` has a module-level docstring per the PR 6 §3 template.

16. **`on_progress` kwarg implemented + threaded (launch-readiness patch for PR 10b).**
    - Per spec §4 + launch-readiness amendment: `solve_hunl_preflop(...)`, `build_blueprint(...)`, AND `refine_subgame(...)` MUST accept `on_progress: Callable[[int, float, MemoryReport], None] | None = None`.
    - When non-None, the callback is invoked every `log_every` iterations with `(iteration_number, current_exploitability_bb, memory_snapshot)`. `memory_snapshot: MemoryReport` re-imported from `poker_solver.profiler.memory`.
    - **Threading:** `solve_hunl_preflop` MUST pass `on_progress` to `build_blueprint(...)` (blueprint pass) AND to `refine_subgame(...)` (refinement pass, which in turn passes to PR 5's `solve_hunl_postflop`).
    - **Rust port:** `solve_hunl_preflop_rust`, `build_blueprint_rust`, `refine_subgame_rust` MUST accept an `Option<PyObject>` callable and invoke from Rust via `Python::with_gil`.
    - **Cancellation explicitly NOT part of this contract** — PR 10a handles via a separate cancellation flag.
    - **Consumer reference:** `docs/pr10_prep/pr10b_spec.md` lines 152-156 dispatch the callback through `_solve_postflop_impl`. Missing this kwarg breaks PR 10b at UI dispatch.
    - **Anti-pattern check:** if any of the three functions silently drops `on_progress` (accepts but doesn't invoke), flag as must-fix — UI will appear hung. If the Rust port omits the callback parameter entirely, flag as must-fix.

## Output format

Write your report to `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/audit_report.md` with this exact structure:

```markdown
# PR 9 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-9-hunl-preflop
**Diff size:** [N modified + M new files = ±X LoC total]

**Test status:** [pytest tests/test_hunl_preflop_*.py tests/test_preflop_diff.py — pass/fail; cargo test --all — pass/fail; full suite delta]

## Must-fix

[Dispatch ordering wrong (push/fold doesn't short-circuit, postflop wins at 15 BB, no 250 BB ceiling); tolerance silently tightened to 1e-4 (must be 5e-3 / 1e-3); canonical-class weights wrong; missing memory cleanup between subgames; license contamination; regression in PR 1-8 tests. Each: file:line + what + fix.]

[If none: "None found." + justification.]

## Should-fix

[Code smell, missing warm-start optimization, awkward APIs, missing assertions on documented invariants, test holes. Each: file:line + description + fix.]

## Nice-to-fix

[Style, naming, comments. Cosmetic.]

## Looks good (explicit confirmation of audit focus areas)

[Numbered list 1-16 matching the 16 audit focus areas above. Each: one-paragraph confirmation with file:line evidence.]

## Spec coverage gaps (missing tests)

[Spec items implemented but not tested. Each: section reference + what's missing + suggested test name.]

## License compliance

[Explicit statement: no AGPL code copy; Pluribus paper cited from `references/papers/`; Rust files have attribution per PR 6 §3 template. Cite specific module docstrings.]

## Overall verdict

[One of: "READY for commit", "READY for commit AFTER must-fix items resolved", or "NOT READY — see must-fix". 2-3 sentence justification.]
```

## Severity rules

- **must-fix:** dispatch ordering violates §6 canonical (silently routes wrong path), tolerance silently 1e-4 instead of 5e-3 (test broken), canonical-class combinatorial weights wrong, memory leak across subgames, regression in PR 1-8 tests, AGPL contamination, **`on_progress` kwarg missing from any of the three entrypoints OR silently dropped (accepted but never invoked) — breaks PR 10b UI dispatch**. Blocks PR.
- **should-fix:** warm-start optimization missing, awkward APIs, test holes (e.g., reach-threshold filter not tested), missing intuition-gauntlet check. Doesn't block.
- **nice-to-fix:** style, comments. Pure polish.

When in doubt: anything that silently produces wrong strategies at boundary conditions (15 BB, 250 BB, 16 BB) → must-fix. Performance issues → should-fix.

## Procedural notes

- Cite **file paths and line numbers** for every finding.
- Quote spec section numbers, especially §6 (canonical dispatch) and the 2026-05-21 amendments.
- Spec-silent behavior → "Spec coverage gaps".
- Do not modify code. Audit only. Your only write is to `docs/pr9_prep/audit_report.md`.

Begin by reading the spec (especially §6 canonical dispatch + 2026-05-21 amendments at the top), then the diff, then the new files. Then write the report.
