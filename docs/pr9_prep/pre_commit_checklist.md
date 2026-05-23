# PR 9 pre-commit checklist

**Date staged:** 2026-05-22
**Author:** orchestrator pre-commit prep agent
**Purpose:** gate list the orchestrator runs immediately before firing
the commit pipeline once the audit verdict clears. Every gate MUST
pass (or carry an explicit waiver with rationale) before `git commit`.

## Build + lint gates (Rust side)

- [ ] **G1 — cargo build clean.** `cargo build --release --package cfr_core` returns 0 with no warnings.
  - Run from repo root.
  - Watch for: `Option<PyObject>` parameter wiring on the three new pyfunctions, `serde_json::Value` deserialization for the JSON config marshalling, `Python::with_gil` lifetime correctness around the callback invocations.
  - Failure mode: missing trait bound on `DCFRSolver<PreflopState>`, JSON-config field-name drift between `_serialize_preflop_config` (Python side) and `#[derive(Deserialize)]` (Rust side).

- [ ] **G2 — cargo test clean (post-reconciliation).** `cargo test --package cfr_core --all-targets` returns 0; all existing PR 1-8 Rust tests pass unchanged; new Rust integration tests for `preflop.rs` / `blueprint.rs` / `subgame.rs` (if any unit tests beyond the PyO3-driven diff tests in `tests/test_preflop_diff.py`) pass.
  - Pre-existing Kuhn/Leduc/HUNL-postflop Rust tests MUST remain green (spec §17 success criteria).

- [ ] **G3 — cargo clippy clean.** `cargo clippy --package cfr_core --all-targets -- -D warnings` returns 0.
  - `-D warnings` upgrades every clippy warning to an error.
  - Watch for: unused imports in new modules, `#[allow(clippy::*)]` overrides creeping in, missing `#[must_use]` on the new public functions.

## Build + lint gates (Python side)

- [ ] **G4 — pytest fast tier clean.** `pytest -m "not slow and not very_slow" --tb=line` returns 0.
  - All tests pass / skip / xfail. NO failures, NO timeouts.
  - Expected new-test count (Python): ~20 across `test_hunl_preflop_blueprint.py` (6) + `test_hunl_preflop_refinement.py` (5) + `test_hunl_preflop_integration.py` (5) + `test_preflop_diff.py` (4), plus `test_preflop_canonical_chance_weights_correct`.
  - PR 1-8 regression (~190+ pre-existing Python tests): all green.
  - Skip rationale: blueprint convergence + combined-exploitability + published-ref tests carry `@pytest.mark.slow`; CI variants at relaxed thresholds (`< 5.0 BB/100`, `< 0.5 BB/hand`) run in the fast tier.

- [ ] **G5 — ruff + black clean.** `ruff check poker_solver tests` and `black --check poker_solver tests` return 0.
  - Format-only nits acceptable; logical lints are not.

- [ ] **G6 — mypy strict clean on Python changes.** `mypy --strict poker_solver/preflop_solver.py poker_solver/blueprint.py poker_solver/subgame_refiner.py poker_solver/hunl.py poker_solver/solver.py poker_solver/cli.py` returns 0.
  - Per-file check, not whole-tree (which would over-scope to unrelated files).
  - Watch for: `on_progress: Callable[[int, float, MemoryReport], None] | None` signature consistency across all three new entrypoints, `SubgameKey` dataclass frozen-equality, `BlueprintResult.leaf_values` keyed by `SubgameKey` (must hash).

## Correctness gates (canonical dispatch + load-bearing math)

- [ ] **G7 — §6 canonical dispatch order verified.** `solver.solve()` body order is locked to:
  1. Push/fold short-circuit at `eff_stack_bb <= 15` (regardless of `starting_street`) → `pushfold.solve_pushfold`.
  2. Stack-depth ceiling at `eff_stack_bb > 250` → `ValueError`.
  3. Postflop branch at `starting_street >= Street.FLOP` → `solve_hunl_postflop` (PR 5).
  4. Preflop branch at `starting_street == Street.PREFLOP` → `solve_hunl_preflop` (this PR).
  - **Locked boundary tests must all pass:** `test_preflop_dispatch_pushfold_at_15bb`, `test_preflop_dispatch_solver_at_16bb`, `test_preflop_dispatch_error_at_251bb`. NAMES VERBATIM per spec §6.
  - Critical invariant: a `HUNLConfig(starting_street=Street.PREFLOP, starting_stack=1500)` (15 BB preflop) hits the push/fold chart, NOT the preflop solver.

- [ ] **G8 — Canonical-class chance generator correctness (6/4/12 + blockers).** `test_preflop_canonical_chance_weights_correct` passes — brute-force validator against a tiny subset confirms:
  - Pairs (e.g., AA): 6 combos. Suited (AKs): 4. Offsuit (AKo): 12.
  - Hero AA → villain AA = 1 combo (NOT 6 — 2 aces removed). Hero AKs → villain AKs = 3 combos (1 of 4 suit combos blocked).
  - Sum across opponent classes == 1.0 within 1e-9 for every fixed hero class.
  - Default 1.6M-combo generator (`_enumerate_preflop_hole_outcomes`) preserved unchanged (per §14 #8); only the new `_enumerate_preflop_hole_outcomes_canonical` is the opt-in canonical-class path.

- [ ] **G9 — Range extraction uses blueprint POSTERIORS, not 1/169 priors.** `test_refinement_ranges_extracted_correctly` passes with a MEANINGFUL ratio — `p0_range["AA"] > p0_range["72o"]` by at least 5× (not 1.01× which would pass spuriously).
  - `_extract_ranges_from_blueprint` iterates over `blueprint.strategy` posteriors, NOT the canonical-class uniform prior. (HIGH-PROB silent-corruption mode per `audit_preprep.md` §1.1.)
  - Audit must confirm via paragraph-level discussion of the code path even when no defect found.

- [ ] **G10 — `on_progress` kwarg threaded through all six entrypoints.** Each of the three Python entrypoints (`solve_hunl_preflop`, `build_blueprint`, `refine_subgame`) AND each of the three Rust entrypoints (`solve_hunl_preflop_rust`, `build_blueprint_rust`, `refine_subgame_rust`) accepts the `on_progress` parameter AND invokes it every `log_every` iterations.
  - Threading: `solve_hunl_preflop` passes `on_progress` to BOTH `build_blueprint(...)` (blueprint pass) AND `refine_subgame(...)` (each subgame); `refine_subgame` forwards to PR 5's `solve_hunl_postflop(..., on_progress=on_progress)` unchanged.
  - Rust: `Option<PyObject>` parameter, invoked via `Python::with_gil` + `callable.call1((iter, expl, report))`.
  - Consumer reference: `docs/pr10_prep/pr10b_spec.md:152-156` dispatches the callback through `_solve_postflop_impl`. Missing this kwarg breaks PR 10b silently at UI dispatch.
  - Cancellation explicitly NOT part of this contract — PR 10a handles via a separate flag.

## Correctness gates (cross-tier parity + convergence)

- [ ] **G11 — Diff tolerance is 5e-3 / 1e-3 (NOT 1e-4).** All four tests in `tests/test_preflop_diff.py` use the PR 6/7/8 tolerance cluster: `5e-3` per-action probability + `1e-3 × base_pot` per-spot game value (post-2026-05-21 amendment, resolving consistency-review I3).
  - Anti-pattern check: any tolerance literal `< 5e-3` (e.g., `1e-4`) in the diff tests is a must-fix per `audit_prompt_final.md` focus area 2 — test will silently fail or pass spuriously.

- [ ] **G12 — Blueprint convergence target <0.5 BB/100 per reached infoset.** `test_blueprint_converges_at_100bb` asserts blueprint exploitability `< 0.5 BB/100` on every reached preflop infoset (slow form, 50k iter); CI variant asserts `< 5.0 BB/100` at 500 iter.
  - Anti-pattern check: assertion must NOT be on global exploitability only — that would give a free pass when one rare infoset blows up. Per-reached-infoset is the load-bearing form.

- [ ] **G13 — End-to-end exploitability <0.05 BB/hand on Pio 100 BB validation fixture.** `test_combined_exploitability_under_0_05_bb_per_hand` (slow) passes at full 50k blueprint + 10k refine iterations. CI variant at 5k blueprint + 2k refine asserts `< 0.5 BB/hand`.
  - Justification: matches gtow_how_solvers_work.md "<0.5% pot = professional standard" guideline scaled to BB/hand on Pio's 100 BB cash-game spot (~7× looser than Pio's benchmark to account for the coarser blueprint).
  - Anti-pattern check: CI variant tolerance must NOT be silently bumped to `< 5.0 BB/hand` — that would lose the safety margin entirely. Bumping iterations is acceptable; weakening the bar is must-fix.

## Memory + budget gates

- [ ] **G14 — 14 GB memory ceiling + 10% RSS calibration.** `BlueprintResult.memory_report.grand_total_bytes < 14 * 1024**3` at 100 BB on the standard 256/128/64 abstraction. `MemoryProbe.calibrate(...)` runs on EACH blueprint solve AND on EACH per-subgame refinement (NOT just the blueprint pass — per spec §12 + I4 inheritance from PR 5 §7.6).
  - Hard ceiling raises `MemoryError(..., args[1]=report)` (PR 5 inheritance pattern); soft warning is NOT acceptable.
  - Sequential subgame cleanup: `del solver; gc.collect()` between refinement calls; `test_memory_no_leak_across_subgames` exposes any leak.

## License + attribution gates

- [ ] **G15 — License attribution headers on every new Rust file.** Each of `preflop.rs`, `blueprint.rs`, `subgame.rs` opens with the module-level attribution docstring per PR 6 §3 template:
  - Names the Python source-of-truth (project-internal, MIT).
  - Names the MIT/Apache reference adapted by pattern (noambrown_poker_solver/cpp/src/trainer.{h,cpp} for the DCFR control flow; Pluribus paper cited from `references/papers/` for the blueprint+refinement architectural pattern only — no code copy from a paper).
  - Carries the explicit `NEVER copy from references/code/postflop-solver (AGPL) or references/code/TexasSolver (AGPL)` disclaimer.

- [ ] **G16 — `check_pr.sh` license audit clean.** PLAN.md §4 step 6 — confirms no new AGPL/GPL deps. No new third-party Python deps (psutil already on the list from PR 5). No new Rust crates introduced by PR 9.

## Branch + integration gates

- [ ] **G17 — All branches synced to origin.** `git fetch --all` then verify the integration baseline has not shifted under PR 9 since the agents launched:
  - `main`: unchanged.
  - `integration`: PR 8 tip SHA stable (whatever it was at PR 9 launch — confirm exact SHA before commit).
  - `pr-9-hunl-preflop` (this PR): contains all Agent A/B/C diffs, no merge conflicts against integration.
  - If integration shifted (e.g., a hotfix landed on PR 8 mid-PR-9), PR 9 must rebase before commit; do NOT commit on stale base.

- [ ] **G18 — No accidental edits to unrelated files.** `git diff integration..pr-9-hunl-preflop --stat` shows ~20-22 files staged, scoped to:
  - 3 new Python source files: `preflop_solver.py`, `blueprint.py`, `subgame_refiner.py`.
  - 5 new Python test files: `test_hunl_preflop_blueprint.py`, `test_hunl_preflop_refinement.py`, `test_hunl_preflop_integration.py`, `test_preflop_diff.py`, `fixtures/hunl_preflop_fixtures.py`.
  - 3 new Rust source files: `preflop.rs`, `blueprint.rs`, `subgame.rs`.
  - Python modifications: `__init__.py` (re-exports), `solver.py` (dispatch branch — must NOT perturb Kuhn/Leduc/HUNL-postflop), `cli.py` (`--hunl-mode preflop` + flags), `hunl.py` (additive canonical-class generator only — default 1.6M generator preserved unchanged).
  - Rust modifications: `crates/cfr_core/Cargo.toml` (no new deps; only module declarations), `crates/cfr_core/src/lib.rs` (PyO3 bindings extended).
  - v0.7 bump + docs touch-ups (ride-along on PR 9 commit): `CHANGELOG.md`, `README.md`, `pyproject.toml`, `Cargo.lock`, `docs/roadmap_status_2026-05-22.md`.
  - No edits to: `dcfr.py`, `evaluator.py`, `abstraction/`, PR 4 abstraction artifacts, PR 5 `hunl_solver.py` orchestration, PR 6 Rust files (`hunl.rs`, `hunl_tree.rs`, `hunl_eval.rs`, `abstraction.rs`, `hunl_solver.rs`), PR 3.5 `pushfold.py` / `charts/pushfold_v1.json`, Kuhn/Leduc test files.

## Audit gate

- [ ] **G19 — PR 9 audit verdict.** `docs/pr9_prep/audit_report.md` carries verdict **READY** or **READY-WITH-PATCHES**, NOT **NOT-READY**.
  - READY → commit.
  - READY-WITH-PATCHES → apply patches in-place, re-run G1-G18 on the patched code, then commit.
  - NOT-READY → abort commit; orchestrator escalates to the user with the audit-report's must-fix list.
  - Audit focus areas (per `audit_prompt_final.md` 16-area brief): §6 canonical dispatch + boundary tests; 5e-3/1e-3 tolerance literals; blueprint convergence per-reached-infoset (not global); warm-start signature compatibility; range-extraction posteriors (HIGH-PROB); canonical-class 6/4/12 + blockers (HIGH-PROB); combined-exploitability target; 10% calibration on refinement; sequential subgame memory; DCFR hyperparameters unchanged; reach-threshold filter; differential parity; PR 3.5 charts unchanged; published-ref SB-open-raise; license hygiene; `on_progress` six-entrypoint threading (HIGH-PROB).

## Biggest gate

**G9 (range extraction posteriors)** + **G8 (canonical-class blockers)** + **G10 (`on_progress` six-entrypoint threading)** are the three highest-risk HIGH-PROB must-fix bands. Each is a silent-corruption mode: G9 corrupts every refinement subgame's strategy if degenerate ranges leak in; G8 corrupts every reached infoset's chance-node payoff if the blocker math is wrong; G10 leaves PR 10b's UI dispatch with a hung progress bar. Treat all three as blocking even if the test count looks complete.

Secondary biggest gate: **G7 (canonical dispatch ordering)** — silent reorderings at the 15 BB / 16 BB / 251 BB boundaries route to the wrong solver and produce wrong strategies for the user's first solve.

## Commit firing order

Once all gates green:
1. `git status` — confirm clean working tree on `pr-9-hunl-preflop` with all expected staged changes.
2. `git diff --cached --stat` — final sanity check; verify ~20-22 file scope.
3. `git commit -F docs/pr9_prep/commit_message_draft.md` (or paste the message via HEREDOC per memory's git-safety protocol).
4. `git status` — verify commit success.
5. Push not yet — wait for user OK on the commit + audit report bundle before `git push origin pr-9-hunl-preflop`.

## Non-commits in this round

- Do NOT auto-merge `pr-9-hunl-preflop` into `integration`. Wait for PR 10b (UI dispatch through the new entrypoints) to land in parallel and merge as a coordinated pair.
- Do NOT close any GitHub PRs yet.
- Do NOT touch PR 4 abstraction artifacts on disk.
- Do NOT modify `dcfr.py` (algorithm + hyperparameters unchanged; spec §1 "Not modified").
- Do NOT modify PR 5's `hunl_solver.py` (consumed read-only; spec §1 "Not modified").
- Do NOT modify PR 3.5's `charts/pushfold_v1.json` (PR 9 only dispatches to it).
- Do NOT replace the default 1.6M-combo preflop chance generator (per §14 #8 — canonical-class is additive opt-in).
