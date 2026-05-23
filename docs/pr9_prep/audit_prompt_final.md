# PR 9 audit agent prompt (FINAL — pre-staged for post-fan-out dispatch)

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh general-purpose `Agent(...)` invocation. Do not include this header in the prompt itself.
>
> **Pre-stage anchors (orchestrator-side only — DO NOT include in prompt):**
> - Expected verdict per `audit_preprep.md` §3: READY-WITH-PATCHES (~70%) > clean READY (~15%) > NOT-READY (~15%).
> - Top three pre-flagged HIGH-PROB risk surfaces (audit MUST touch with file:line evidence even if no defect found):
>   1. Range extraction prior vs posterior (`audit_preprep.md` §1.1) — must use `blueprint.strategy` posteriors, not 1/169 uniform priors over canonical classes.
>   2. Canonical-class chance weights + blocker accounting (`audit_preprep.md` §1.5) — 6/4/12 base combos; hero-AA → 0 villain-AA combos; sum-to-1 across opponent classes.
>   3. `on_progress` kwarg threading (`audit_preprep.md` §1.2) — 3 Python + 3 Rust entrypoints; signature locked; threading from `solve_hunl_preflop` → `build_blueprint` + `refine_subgame` → PR 5 `solve_hunl_postflop`.
> - Other LOCKED-pattern inheritances (audit must verify, lower priority): §6 canonical dispatch composition (PR 3.5 + PR 5 cross-reference); 5e-3/1e-3 tolerance cluster (I3 reconciliation); 14 GB ceiling + 10% MemoryProbe calibration (I4 inheritance from PR 5).

---

You are a **fresh code reviewer with NO implementation context**. You did not write any of the code on the `pr-9-hunl-preflop` branch and you have not seen the design discussions. Your job is to audit the PR 9 implementation (HUNL preflop solve — blueprint + subgame refinement, both Python + Rust tiers) against the spec and report findings in a structured Markdown report.

Treat the spec as the source of truth. Do not make assumptions about behavior not specified there; if you find unspecified behavior, flag it.

## Repository context

- **Repo root:** `/Users/ashen/Desktop/poker_solver`
- **Branch under audit:** `pr-9-hunl-preflop` (branched from `integration`; name verified via `fanout_ready.md` + `audit_prompt.md:7`).
- **Spec:** `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/pr9_spec.md` — read end-to-end. Note the 2026-05-21 amendments:
  - §6 is the **canonical dispatch composition section** (referenced by PR 3.5 §6 and PR 5 §6).
  - Tolerance cluster reconciled to **5e-3 per-action / 1e-3 per-spot game value** (I3) — earlier draft said `1e-4`, which was a misquote.
  - End-to-end exploitability target **<0.05 BB/hand** added to §7.4 + §17 (I5).
  - **10% psutil RSS calibration** inheritance from PR 5 §7.6 explicit in §12 (I4).
- **Implementation log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — skim PR 9 entries.
- **PR 10b consumer (locks `on_progress` contract):** `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10b_spec.md:152-156` — UI dispatch reads the callback signature; any kwarg drop here breaks PR 10b silently.

## Inputs to read (in order)

1. **The spec:** internalize §3 (architecture — blueprint + subgame refinement, Pluribus pattern), §4 (files to create), §5 (files to modify — especially the canonical-class chance generator added to `hunl.py`), §6 (canonical dispatch composition — THE AUTHORITATIVE SECTION), §7 (blueprint design + end-to-end target), §8 (subgame refinement: §8.1 reach threshold, §8.2 range extraction, §8.3 warm start), §10 (test plan — diff tests in §10.4), §12 (memory hygiene + 10% calibration), §13 (risks — esp. row on tolerance reconciliation and canonical-class blocker accounting), §17 (success criteria).
2. **The branch diff:** `git diff integration...HEAD` while on `pr-9-hunl-preflop`. Also `git log integration..HEAD --oneline`.
3. **The autonomous log:** PR 9 entries.
4. **The actual new / modified files:** at minimum
   - `poker_solver/preflop_solver.py`
   - `poker_solver/blueprint.py`
   - `poker_solver/subgame_refiner.py`
   - `poker_solver/hunl.py` (canonical-class chance generator added)
   - `poker_solver/solver.py` (preflop dispatch branch added per §6)
   - `poker_solver/cli.py` (`--hunl-mode preflop` + flags)
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

Do not run blueprint / refinement solves. Audit the *committed* code + tests.

## Audit focus areas (each MUST be touched in the report with file:line evidence)

For each focus area, either confirm correct ("Looks good" with file:line evidence) or flag under the appropriate severity. Pre-flagged HIGH-PROB items (focus areas 5, 6, 16 — per `audit_preprep.md` §1.1, §1.5, §1.2) MUST receive paragraph-level discussion even if no defect is found.

1. **Dispatch composition matches PR 9 §6 canonical (AUTHORITATIVE SECTION).**
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
   - **Evidence stub:** `poker_solver/solver.py:?` — `solve()` body; `tests/test_hunl_preflop_integration.py:?` — three boundary tests.

2. **Diff test tolerance: 5e-3 per-action / 1e-3 per-spot game value.**
   - Per spec §10.4 (post-2026-05-21 amendment, resolving consistency-review I3): PR 9 adopts the **PR 6 / PR 7 / PR 8 tolerance cluster** — `5e-3` per-action probability + `1e-3 × base_pot` per-spot game value.
   - **Earlier draft said `1e-4` — reconciled to `5e-3 / 1e-3`.** Per §13 risk row mentioning "was previously misquoted as 1e-4."
   - **Anti-pattern check:** if `tests/test_preflop_diff.py` uses tolerance < 5e-3 (e.g., 1e-4), flag as must-fix — the test will silently fail or pass spuriously. Audit must check tolerance literal in **all four diff tests** (blueprint strategy parity, refinement strategy parity, combined strategy table parity, dispatch path parity).
   - **Evidence stub:** `tests/test_preflop_diff.py:?` — tolerance constants.

3. **Blueprint convergence target.**
   - Per spec §7.4: blueprint exploitability `< 0.5 BB/100` on every reached preflop infoset (loose because the blueprint is intentionally coarse).
   - `test_blueprint_converges_at_100bb` (§10.1 #1) asserts this (in `slow` form) or asserts a relaxed CI form (`< 5.0 BB/100` at 500 iterations).
   - **Pre-flagged failure modes** (per `audit_preprep.md` §1.3):
     - Test asserts global exploitability only (not per-reached-infoset) — gives a free pass when one rare infoset blows up. Probe.
     - CI variant tolerance silently bumped to `< 50 BB/100` to make a flaky run green. Probe.
   - Default blueprint config: **1 size (0.75 pot) + all-in, 1-cap** for postflop menu (§7.1); full preflop menu (§7.2); 256/128/64 abstraction (§7.3); 50,000 blueprint iterations (§7.4).
   - **Evidence stub:** `tests/test_hunl_preflop_blueprint.py:?` — `test_blueprint_converges_at_100bb`.

4. **Subgame refinement warm-start correctness.** [MEDIUM-PROB should-fix per `audit_preprep.md` §1.4]
   - Per spec §8.3: refined postflop solve uses blueprint's strategy as a **regret-table warm start** — for every postflop infoset key that exists in BOTH the blueprint and the refinement tree, copy the blueprint's regret values into the refinement's regret table at iteration 0.
   - Infosets that exist only in the refinement tree (because refinement has the full 6-size menu and blueprint had 1–2 sizes) start at zero regret.
   - Tested: `test_refinement_warm_start_speeds_convergence` (§10.2 #2) — warm-start solve converges in fewer iterations than cold-start.
   - **PR 5 signature compatibility check (per `audit_preprep.md` §1.4):** if PR 5's `solve_hunl_postflop(...)` does NOT admit a `warm_start_regrets` kwarg, Agent B was authorized to instantiate `DCFRSolver` directly + file an interface-adjustment note. **Audit must verify either** (a) the warm-start path is wired through `solve_hunl_postflop`'s kwargs, OR (b) the direct-DCFRSolver fallback is documented in the autonomous log with rationale. Silent drop to cold-start fallback = should-fix (loses iteration-reduction win, not must-fix).
   - **Soft assertion allowance:** failure of §10.2 #2 prompts user review, not auto-fix.
   - **Evidence stub:** `poker_solver/subgame_refiner.py:?` — warm-start injection; `tests/test_hunl_preflop_refinement.py:?` — `test_refinement_warm_start_speeds_convergence`.

5. **Range extraction from blueprint — reach-prob conditioning under POSTERIORS.** [HIGH-PROB must-fix per `audit_preprep.md` §1.1]
   - Per spec §8.2: `p0_range[hand_class] = Σ_paths reach_prob(path_to_subgame_root | hand_class)` where the reach is computed under the **blueprint's strategy (posteriors), NOT the 1/169 uniform prior over canonical classes**.
   - **Silent corruption mode:** if `_extract_ranges_from_blueprint` in `subgame_refiner.py` grabs the chance-node uniform prior (because the canonical-class chance node introduces a fresh uniform-ish surface), the refinement solves on a degenerate range. The 3-bet pot subgame parity check (`p0_range["AA"] > p0_range["72o"]`) may then **pass spuriously** (both terms tiny non-uniform numbers) or **fail by accident**.
   - **Audit probe (paragraph-level even if no defect):**
     - Confirm the implementation iterates over blueprint infoset reach probabilities (e.g., via `blueprint.strategy[infoset]` or equivalent), NOT a hard-coded 1/169 / canonical-class frequency.
     - Confirm `p0_range["AA"] > p0_range["72o"]` is asserted with a meaningful margin (e.g., `> 5x` ratio) — a 1.01x margin passes spuriously.
   - Tested: `test_refinement_ranges_extracted_correctly` (§10.2 #5) — for 3-bet pot subgame, `p0_range["AA"] > p0_range["72o"]`.
   - **Evidence stub:** `poker_solver/subgame_refiner.py:?` — `_extract_ranges_from_blueprint` body; `tests/test_hunl_preflop_refinement.py:?` — `test_refinement_ranges_extracted_correctly` assertion with explicit ratio.

6. **Canonical-class preflop chance generator — 6/4/12 weights + blocker accounting.** [HIGH-PROB must-fix per `audit_preprep.md` §1.5]
   - Per spec §5 "Files to modify" + §13 risk row: a new `_enumerate_preflop_hole_outcomes_canonical()` generator added to `hunl.py` that yields the 169×169 unique hand-class chance outcomes with **correct combinatorial weights**:
     - **Pairs** (e.g., AA): 6 combos.
     - **Suited** (e.g., AKs): 4 combos.
     - **Offsuit** (e.g., AKo): 12 combos.
   - **Opponent class enumeration respects blockers:**
     - Hero AA → villain AA = **1 combo** (not 6 — 2 aces removed from deck).
     - Hero AKs → villain AKs = **3 combos** (1 of the 4 suit combos blocked).
     - Hero AKo → villain AKs / AKo blockers per spec §13 risk row 6.
   - The default 1.6M-combo generator is preserved unchanged (per §14 #8 decision).
   - The `BlueprintResult` builder passes `chance_strategy="canonical_classes"` automatically.
   - **Pre-flagged failure modes** (auditor MUST probe each per `audit_preprep.md` §1.5):
     - (a) Weights normalized but blockers ignored → AA-vs-AA computed with 6 combos instead of 1 → range silently biased.
     - (b) Sum across opponent classes != 1.0 (within 1e-9) given a fixed hero class → bias propagates through every blueprint and refinement infoset.
     - (c) The non-canonical 1.6M-combo generator gets silently switched to canonical for default callers (spec §14 #8 says preserve default unchanged).
   - Tested: `test_preflop_canonical_chance_weights_correct` (mentioned in §13 risk row) — validates against brute-force enumeration on a tiny subset.
   - **Evidence stub:** `poker_solver/hunl.py:?` — `_enumerate_preflop_hole_outcomes_canonical()`; `tests/test_hunl_preflop_blueprint.py:?` (or fixture file) — `test_preflop_canonical_chance_weights_correct` brute-force tiny-subset validator.

7. **End-to-end exploitability target: < 0.05 BB/hand on Pio validation fixture.**
   - Per the 2026-05-21 spec amendment to §7.4 + §17: combined preflop + refinement exploitability `< 0.05 BB/hand` on the HU NL cash-game 100 BB starting stacks, no ante, $0.50/$1.00 blinds (Pio's published reference setup).
   - Tested: `test_combined_exploitability_under_0_05_bb_per_hand` (§10.3 #5, NEW). Marked `@pytest.mark.slow`. CI variant: 5k blueprint + 2k refine → `< 0.5 BB/hand`.
   - **Pre-flagged failure modes** (per `audit_preprep.md` §1.8):
     - Test marked `@pytest.mark.slow` but never wired to a slow-CI lane → silently never runs.
     - CI variant tolerance bumped to `< 5.0 BB/hand` to absorb flakes → loses the safety margin entirely.
     - Test passes locally on CPU but fails on GitHub Actions (memory pressure changes solver convergence) — audit can't verify but flag if no CPU-vs-CI separation noted.
   - Justification: matches "professional standard" of < 0.5% pot from `gtow_how_solvers_work.md`; ~7× looser than Pio benchmark given coarser blueprint. **Anti-pattern: bumping iterations is acceptable; weakening the bar is must-fix.**
   - **Evidence stub:** `tests/test_hunl_preflop_integration.py:?` — `test_combined_exploitability_under_0_05_bb_per_hand` + CI variant.

8. **PR 5 `MemoryProbe` 10% calibration inheritance.**
   - Per spec §12 (consistency review I4): PR 9 explicitly inherits the **10% psutil RSS calibration check** from PR 5 §7.6. Each blueprint solve AND each subgame refinement solve runs the calibration.
   - **Pre-flagged failure modes** (per `audit_preprep.md` §1.7):
     - Calibration runs on blueprint but not refinement → larger preflop tree never validates its profiler accuracy.
     - 10% bound enforced as soft warning rather than test-level assertion.
   - If the larger preflop tree exceeds the 10% bound, that's a profiler-correctness signal worth investigating — flag in test output.
   - **Evidence stub:** `poker_solver/blueprint.py:?` + `poker_solver/subgame_refiner.py:?` — `MemoryProbe.calibrate(...)` invocation.

9. **Sequential subgame refinement memory hygiene + 14 GB ceiling.**
   - Per spec §12: each subgame is solved sequentially with `max_memory_gb` budget. Between subgames, previous solver's regret tables + infoset dicts are explicitly dropped (`del solver` and `gc.collect()`).
   - **Pre-flagged failure modes** (per `audit_preprep.md` §1.7):
     - Sequential cleanup missing between subgames → integration test exposes RSS leak; `test_memory_no_leak_across_subgames` fails.
     - 14 GB ceiling enforced as soft warning rather than `MemoryError(..., args[1]=report)` raising pattern (per PR 5 inheritance).
   - The integration test verifies no memory leak across the chain.
   - **Evidence stub:** `poker_solver/subgame_refiner.py:?` — subgame loop with `del solver; gc.collect()`; `tests/test_hunl_preflop_integration.py:?` — `test_memory_no_leak_across_subgames`.

10. **DCFR hyperparameters unchanged.**
    - Per spec §1 "Not modified" + §2: same hyperparameters as PR 1-8 (α=1.5, β=0, γ=2.0). No `--alpha` / `--beta` / `--gamma` CLI flags exposed.
    - `dcfr.py` unchanged. `abstraction/` consumed read-only. `hunl_solver.py` (PR 5) called but not modified.
    - **Evidence stub:** `poker_solver/dcfr.py` (verify unchanged via diff); `poker_solver/cli.py:?` — flag inventory (no α/β/γ exposed).

11. **Reach-threshold filtering.**
    - Per spec §8.1: subgame is refined if reach probability under blueprint exceeds `reach_threshold` (default 1e-3).
    - Tested: `test_refinement_respects_reach_threshold` (§10.2 #4) — `refined_subgames.keys()` all have `reach > 0.1` when `reach_threshold=0.1`; `unrefined_subgames` all have `reach <= 0.1`.
    - **Evidence stub:** `poker_solver/subgame_refiner.py:?` — reach-threshold filter; `tests/test_hunl_preflop_refinement.py:?` — `test_refinement_respects_reach_threshold`.

12. **Rust ↔ Python differential test parity.**
    - Per spec §10.4: four diff tests in `tests/test_preflop_diff.py`. Tolerance is the locked **5e-3 / 1e-3** cluster from §10.4 (see focus area 2).
    - Blueprint strategies match, refinement strategies match, combined strategy table matches, dispatch paths consistent across tiers (15 BB → chart; 100 BB → solver; 251 BB → error).
    - The Rust ports (`preflop.rs`, `blueprint.rs`, `subgame.rs`) are mechanical translations matching the PR 6 pattern.
    - **Evidence stub:** `tests/test_preflop_diff.py:?` — four diff tests + tolerance constants; `crates/cfr_core/src/preflop.rs:?` + `blueprint.rs:?` + `subgame.rs:?` — module structure mirrors Python.

13. **PR 3.5 charts unchanged.**
    - Per spec §5 "Not modified": `poker_solver/charts/pushfold_v1.json` is unchanged. PR 9 only dispatches to it via the canonical §6 order.
    - PR 3.5 tests still pass unchanged.
    - **Evidence stub:** chart file SHA-equivalence in diff; `tests/test_pushfold_*.py` (verify untouched).

14. **Published-reference SB open-raise validation.**
    - Per spec §10.3 #4 (`test_published_ref_sb_open_raise_100bb`): at 100 BB, for SB-first-action infoset:
      - `AA`: ≥ 95% non-fold (open) probability.
      - `72o`: ≥ 60% fold.
      - `JJ`: open frequency in `[0.85, 1.0]`.
    - Loose anchors — tight comparison deferred to follow-up PR.
    - **Evidence stub:** `tests/test_hunl_preflop_integration.py:?` — `test_published_ref_sb_open_raise_100bb`.

15. **License hygiene + module attribution.**
    - No code copied from AGPL repos (`postflop-solver`, `TexasSolver`) — only architectural inspiration from PLUS Pluribus paper (cited from `references/papers/`).
    - MIT/Apache patterns from `noambrown_poker_solver` may be ported with attribution.
    - Each new Rust file in `crates/cfr_core/src/` (`preflop.rs`, `blueprint.rs`, `subgame.rs`) has a module-level docstring per the PR 6 §3 template.
    - **Evidence stub:** `crates/cfr_core/src/preflop.rs:1-?`, `blueprint.rs:1-?`, `subgame.rs:1-?` — module docstring header.

16. **`on_progress` kwarg implemented + threaded across all six entrypoints (launch-readiness patch for PR 10b).** [HIGH-PROB must-fix per `audit_preprep.md` §1.2]
    - Per spec §4 + launch-readiness amendment: `solve_hunl_preflop(...)`, `build_blueprint(...)`, AND `refine_subgame(...)` MUST accept `on_progress: Callable[[int, float, MemoryReport], None] | None = None`.
    - When non-None, the callback is invoked every `log_every` iterations with `(iteration_number, current_exploitability_bb, memory_snapshot)`. `memory_snapshot: MemoryReport` re-imported from `poker_solver.profiler.memory`.
    - **Threading (Python side):** `solve_hunl_preflop` MUST pass `on_progress` to `build_blueprint(...)` (blueprint pass) AND to `refine_subgame(...)` (refinement pass, which in turn passes to PR 5's `solve_hunl_postflop`).
    - **Rust port:** `solve_hunl_preflop_rust`, `build_blueprint_rust`, `refine_subgame_rust` MUST accept an `Option<PyObject>` callable and invoke from Rust via `Python::with_gil`.
    - **Pre-flagged failure modes** (auditor MUST probe each per `audit_preprep.md` §1.2):
      - (a) **Silent drop** — kwarg accepted but never invoked (UI shows hung progress bar) → must-fix.
      - (b) **Threading gap (blueprint)** — `solve_hunl_preflop` accepts `on_progress` but doesn't pass it down to `build_blueprint` → must-fix.
      - (c) **Threading gap (refinement)** — `refine_subgame` accepts `on_progress` but fails to forward to PR 5's `solve_hunl_postflop(..., on_progress=on_progress)` → must-fix.
      - (d) **Rust port omission** — any of the three `_rust` functions skips the `Option<PyObject>` parameter or fails to invoke via `Python::with_gil` + `callable.call1(...)` → must-fix.
    - **Cancellation explicitly NOT part of this contract** — PR 10a handles via a separate cancellation flag.
    - **Consumer reference:** `docs/pr10_prep/pr10b_spec.md:152-156` dispatch the callback through `_solve_postflop_impl`. Missing this kwarg breaks PR 10b at UI dispatch.
    - **Evidence stubs:**
      - `poker_solver/preflop_solver.py:?` — `solve_hunl_preflop` signature + invocation sites for `build_blueprint(..., on_progress=on_progress)` and `refine_subgame(..., on_progress=on_progress)`.
      - `poker_solver/blueprint.py:?` — `build_blueprint` signature + iteration-loop callback site.
      - `poker_solver/subgame_refiner.py:?` — `refine_subgame` signature + forward to `solve_hunl_postflop(..., on_progress=...)`.
      - `crates/cfr_core/src/preflop.rs:?` + `blueprint.rs:?` + `subgame.rs:?` — `Option<PyObject>` parameter + `Python::with_gil` invocation.

## Output format

Write your report to `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/audit_report.md` with this exact structure:

```markdown
# PR 9 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-9-hunl-preflop
**Diff size:** [N modified + M new files = ±X LoC total]

**Test status:** [pytest tests/test_hunl_preflop_*.py tests/test_preflop_diff.py — pass/fail; cargo test --all — pass/fail; full suite delta]

## Must-fix

[Dispatch ordering wrong (push/fold doesn't short-circuit, postflop wins at 15 BB, no 250 BB ceiling); tolerance silently tightened to 1e-4 (must be 5e-3 / 1e-3); range extraction uses 1/169 prior instead of blueprint posteriors; canonical-class weights ignore blockers (hero-AA → 6 villain-AA combos); `on_progress` kwarg missing or silently dropped at any of the six entrypoints; missing memory cleanup between subgames; license contamination; regression in PR 1-8 tests. Each: file:line + what + fix.]

[If none: "None found." + justification.]

## Should-fix

[Code smell, warm-start signature fallback without documented note, awkward APIs, missing assertions on documented invariants, test holes (e.g., reach-threshold filter not tested, blueprint convergence asserts global instead of per-reached-infoset), CI exploitability variant tolerance silently bumped to > 0.5 BB/hand. Each: file:line + description + fix.]

## Nice-to-fix

[Style, naming, comments. Cosmetic.]

## Looks good (explicit confirmation of audit focus areas)

[Numbered list 1-16 matching the 16 audit focus areas above. Each: one-paragraph confirmation with file:line evidence. Focus areas 5, 6, 16 (the HIGH-PROB pre-flagged surfaces) MUST get paragraph-level discussion regardless of finding.]

## Spec coverage gaps (missing tests)

[Spec items implemented but not tested. Each: section reference + what's missing + suggested test name.]

## License compliance

[Explicit statement: no AGPL code copy; Pluribus paper cited from `references/papers/`; Rust files have attribution per PR 6 §3 template. Cite specific module docstrings.]

## Release-notes follow-up

[Note for v0.5.x / v0.6.0: HUNL preflop solve landed in PR 9. If PR 9 added new public API (`solve_hunl_preflop`, `build_blueprint`, `refine_subgame`), call out in release notes; otherwise prior version notes stand as-is. See `audit_preprep.md` post-audit triage.]

## Overall verdict

[One of: "READY for commit", "READY for commit AFTER must-fix items resolved", or "NOT READY — see must-fix". 2-3 sentence justification.]
```

## Severity rules

- **must-fix:** dispatch ordering violates §6 canonical (silently routes wrong path); tolerance silently 1e-4 instead of 5e-3 (test broken); **range extraction uses 1/169 prior instead of blueprint posteriors (range silently degenerate)**; **canonical-class combinatorial weights wrong or blockers ignored (every reached infoset corrupted)**; memory leak across subgames; regression in PR 1-8 tests; AGPL contamination; **`on_progress` kwarg missing from any of the six entrypoints OR silently dropped (accepted but never invoked) — breaks PR 10b UI dispatch**. Blocks PR.
- **should-fix:** warm-start signature falls back to cold-start without documented interface note; awkward APIs; test holes (e.g., reach-threshold filter not tested, blueprint convergence asserts global instead of per-reached-infoset); CI exploitability variant tolerance silently bumped; missing 10% calibration on refinement pass (only blueprint covered). Doesn't block.
- **nice-to-fix:** style, comments. Pure polish.

When in doubt: anything that silently produces wrong strategies at boundary conditions (15 BB, 250 BB, 16 BB) or silently corrupts reached infosets (wrong prior, wrong combos) → must-fix. Performance / convergence-rate issues → should-fix.

## Procedural notes

- Cite **file paths and line numbers** for every finding.
- Quote spec section numbers, especially §6 (canonical dispatch) and the 2026-05-21 amendments.
- Spec-silent behavior → "Spec coverage gaps".
- Do not modify code. Audit only. Your only write is to `docs/pr9_prep/audit_report.md`.
- HIGH-PROB risk surfaces (focus areas 5, 6, 16) MUST get paragraph-level discussion even with no defect found.

Begin by reading the spec (especially §6 canonical dispatch + 2026-05-21 amendments), then the diff, then the new files. Then write the report.
