# PR 9 audit kickoff (pre-staged, fire-on-implementer-completion)

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh general-purpose `Agent(...)` invocation. Do not include this header in the prompt itself.
>
> **When to fire:** after the PR 9 implementer agents (A / B / C) all return and report `pr_report.md` complete. The branch under audit is `pr-9-preflop` (worktree at `/Users/ashen/Desktop/poker_solver_worktrees/pr-9-preflop`). DO NOT fire while any of the three implementers are still in flight — partial diff = mis-classified audit.
>
> **Pre-stage anchors (orchestrator-side only — DO NOT include in prompt):**
> - Expected verdict per `pr9_spec.md` §17 success criteria: **READY-WITH-PATCHES (~50%) > READY (~30%) > NOT-READY (~20%)**. The blueprint+refinement architecture is novel within the codebase; high-prob the 15 BB dispatch boundary or the canonical-class chance generator surfaces issues.
> - Hard scope: blueprint pass (coarse postflop menu) + subgame refinement (full menu) + Rust port + dispatch wiring + canonical-class preflop chance node.
> - Worktree path: `/Users/ashen/Desktop/poker_solver_worktrees/pr-9-preflop`. Audit may inspect there but NOT branch-switch the shared working tree at `/Users/ashen/Desktop/poker_solver`.
> - Differential test tolerances are LOCKED at the PR 6/7/8/9 cluster: `5e-3` per-action + `1e-3 × base_pot` per-spot game value. Any tightening to `1e-4` or loosening = must-fix.
> - PR 3.5 push/fold short-circuit at ≤15 BB MUST execute IN FRONT of any preflop solve (per §6 canonical dispatch). Ordering invariant violation = must-fix.

---

You are a **fresh code reviewer with NO implementation context**. You did not write any of the code on the `pr-9-preflop` branch and you have not seen the design discussions. Your job is to audit the PR 9 implementation (HUNL preflop blueprint + subgame refinement; Python + Rust tiers) against the PR 9 spec and report findings in a structured Markdown report.

Treat `docs/pr9_prep/pr9_spec.md` and the three implementer `pr_report.md` files as the sources of truth. Do not make assumptions about behavior not specified there; if you find unspecified behavior, flag it.

PR 9 is the **first end-to-end HUNL preflop → river solve** in both tiers. Architecture is **blueprint + subgame refinement** (Pluribus pattern). The blueprint pass solves the entire preflop+postflop tree at coarse fidelity (1-size/1-cap postflop menu, 256/128/64 abstraction); subgame refinement re-solves each high-reach postflop spot with the full PR 3 menu. Dispatch at the CLI level routes ≤15 BB to PR 3.5's push/fold chart and >250 BB to a ValueError; the preflop solver runs only for 15 < stacks ≤ 250 BB.

## Repository context

- **Repo root:** `/Users/ashen/Desktop/poker_solver`
- **Branch under audit:** `pr-9-preflop`. Worktree at `/Users/ashen/Desktop/poker_solver_worktrees/pr-9-preflop`. Branched from main tip `62c75d5` (post-v1.0.0 GA merge). Verify via `git -C /Users/ashen/Desktop/poker_solver_worktrees/pr-9-preflop log main..HEAD --oneline`.
- **Base commit:** `62c75d5` (main after FF merge).
- **Spec (authoritative):** `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/pr9_spec.md` — read end-to-end first. §1 (goal: end-to-end HUNL preflop), §2 (out of scope), §3 (blueprint+refinement architecture + memory budget table), §4-5 (files to create / modify), §6 (CANONICAL dispatch ordering — referenced by PR 3.5 + PR 5), §7 (blueprint design + 0.05 BB/hand exploitability target), §8 (subgame refinement + warm start), §10 (test plan), §11 (3-agent fan-out), §12 (memory budget + 10% calibration), §13 (risks), §14 (deferred decisions), §17 (success criteria).
- **Implementer reports:** there should be three (`docs/pr9_prep/pr_report_agent_a.md`, `pr_report_agent_b.md`, `pr_report_agent_c.md`) OR a single consolidated `docs/pr9_prep/pr_report.md`. Read whichever exist end-to-end.
- **Originating audit-prompt precedent:** `/Users/ashen/Desktop/poker_solver/docs/pr10a_5_prep/audit_kickoff.md` (for structural template) and `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/audit_report.md` (closest peer — Python HUNL postflop, which `subgame_refiner.py` reuses unchanged).

## Inputs to read (in order)

1. **The spec:** `pr9_spec.md`. Internalize §3 (architecture diagram + memory table), §6 (canonical dispatch — ordering invariant: push/fold short-circuit FIRST), §7 (blueprint design: 1-size/1-cap default, lossless preflop, 0.05 BB/hand end-to-end target), §8 (refinement: reach threshold = 1e-3, range extraction, warm start), §10 (test plan: blueprint / refinement / integration / Python↔Rust diff / intuition gauntlet), §13 (risks), §14 (deferred decisions — for context on default vs override behavior).
2. **The implementer report(s):** under `docs/pr9_prep/`. Cross-reference each agent's deliverable list against their owned-files block in §11.
3. **The diff:** from worktree path, run `git log main..HEAD --oneline` and `git diff main..HEAD --stat`. Confirm the file list aligns with §4–§5's create/modify tables and §9's consolidated checklist.
4. **The canonical dispatch precedent:** §6 of `pr9_spec.md` is the AUTHORITATIVE source for HUNL solve dispatch ordering. PR 3.5 §6 and PR 5 §6 cross-reference it. Confirm `poker_solver/solver.py` implements the §6 ordering exactly: (a) push/fold short-circuit, (b) stack-depth ceiling, (c) postflop branch, (d) preflop branch.

## Audit focus areas (each MUST be touched in the report with file:line evidence)

For each focus area, either confirm correct ("Looks good" with file:line evidence) or flag under the appropriate severity. HIGH-PROB items (1, 2, 3, 4, 5, 8 — the correctness core) MUST receive paragraph-level discussion even if no defect is found.

1. **Preflop tree builder correctness: 4-bet/5-bet cap = 4 enforced.** [must-fix on cap drift]
   - The preflop tree in `poker_solver/blueprint.py` (and `crates/cfr_core/src/preflop.rs` / `blueprint.rs`) walks the open / 3-bet / 4-bet / 5-bet ladder under the **4-cap** rule (preflop 4-cap, postflop 3-cap per PR 3 `action_abstraction.py`).
   - **Probe:** walk the tree manually for one path: SB-open (bet 1) → BB-3bet (bet 2) → SB-4bet (bet 3) → BB-5bet-all-in (bet 4) → SB-call OR fold. At bet 4 (cap), the only legal actions are call / fold; no further raises. Per `pr9_spec.md` §5: "The 4-cap raise rule (preflop 4-cap, postflop 3-cap) is already implemented in `action_abstraction.py`. PR 9 audit confirms a walk through the 4-bet/5-bet ladder hits the cap correctly."
   - **Probe:** for the blueprint's preflop menu (full PR 3 menu = 33/75/100/150/200% + all-in), at the cap node, `legal_actions()` returns only fold + call (no raise). Verify via reading `action_abstraction.py:test_abstraction_no_raise_at_cap` and confirming the new preflop tree builder respects this.
   - **Boundary test:** `tests/test_hunl_preflop_blueprint.py` should include a tree-walk test that asserts cap enforcement. If absent → should-fix (spec coverage gap).
   - **Evidence stub:** `poker_solver/blueprint.py:?` (tree walk); `poker_solver/action_abstraction.py:?` (cap enforcement source); `tests/test_hunl_preflop_blueprint.py:?` (cap-enforcement test if present).

2. **Ante parameter wires through to preflop pot math.** [must-fix on ante drift]
   - Per `pr9_spec.md` §2 + §5: "PR 9 solves at `ante=0` by default; user can override via `--ante INT_CENTS` on the CLI." The engine accepts `HUNLConfig(ante=X)` since PR 3.
   - Verify `HUNLConfig.ante` is threaded from CLI → `preflop_solver.solve_hunl_preflop` → `blueprint.build_blueprint` → the `HUNLPoker.initial_state` (lines 215-240 of `hunl.py` per spec §5).
   - **Initial pot calculation:** for `ante=X` and blinds (SB=BB/2, BB=BB), starting pot = `2*X + BB + SB`. Verify the blueprint's preflop chance-node + pot math respects this. If the ante is silently zeroed somewhere → must-fix.
   - **`HUNLConfig.__post_init__` assertion:** PR 3 has `rake_rate == 0.0` assertion; PR 9 preserves that. If PR 9 removed or weakened the assertion → must-fix scope leak.
   - **Probe:** `grep -n 'ante' poker_solver/preflop_solver.py poker_solver/blueprint.py poker_solver/subgame_refiner.py` — expected hits showing ante is read from config and threaded through.
   - **Probe:** `grep -nE 'rake_rate' poker_solver/hunl.py | head -10` — confirm the `rake_rate == 0.0` assert is intact.
   - **Test:** an integration test (in `tests/test_hunl_preflop_integration.py`) covers `--ante 5` (5 cents per player) and asserts the pot math is correct at preflop terminals. If absent → should-fix.
   - **Evidence stub:** `poker_solver/preflop_solver.py:?` (ante threading); `poker_solver/hunl.py:?` (initial_state ante handling); `poker_solver/cli.py:?` (--ante flag wiring).

3. **Push/fold short-circuit at ≤15 BB stays IN FRONT of any preflop solve.** [must-fix on dispatch ordering violation]
   - Per `pr9_spec.md` §6 (CANONICAL dispatch ordering — referenced by PR 3.5 §6 and PR 5 §6): "**Ordering invariant:** push/fold short-circuit MUST execute before the postflop and preflop branches."
   - Even at `starting_street=Street.PREFLOP, starting_stack=1500` (15 BB), the dispatch routes to `pushfold.solve_pushfold` (PR 3.5's chart), NOT to `preflop_solver.solve_hunl_preflop`.
   - **Boundary tests (locked):**
     - `test_preflop_dispatch_pushfold_at_15bb`: 1500 cents = 15 BB → chart hit, `dispatched_to_pushfold=True`.
     - `test_preflop_dispatch_solver_at_16bb`: 1600 cents = 16 BB → preflop solver runs, `dispatched_to_pushfold=False`.
     - `test_preflop_dispatch_error_at_251bb`: 25100 cents → `ValueError` mentioning the 250 BB cap.
   - **All three tests MUST exist in `tests/test_hunl_preflop_integration.py`** (per spec §10.3 #1 / #2 / #3) and MUST pass. Each missing = must-fix.
   - **Probe:** `grep -n 'def test_preflop_dispatch_' tests/test_hunl_preflop_integration.py` — expected 3 hits (the three boundary tests).
   - **Probe:** read `poker_solver/solver.py` dispatch logic and confirm it implements §6's ordering exactly (push/fold first, then ceiling, then postflop branch, then preflop branch).
   - **Hard cliff at 15 BB:** default per §14 Decision #1. No interpolation band. If the implementer added a smoothing layer in a 12-18 BB band, that's a scope-leak override of the default → must-fix unless explicitly approved in `pr_report.md` with user signoff.
   - **Evidence stub:** `poker_solver/solver.py:?` (dispatch ordering); `tests/test_hunl_preflop_integration.py:?` (3 boundary tests + assertions).

4. **Rust preflop port matches Python reference within float tolerance on small fixtures.** [must-fix on diff drift]
   - `tests/test_preflop_diff.py` exists with 4 tests (per spec §10.4).
   - **Tolerance LOCKED at:** `5e-3` per-action probability + `1e-3 × base_pot` per-spot game value. Per spec §10.4: "PR 9 adopts the **PR 6 / PR 7 / PR 8 tolerance cluster**." Earlier draft cited `1e-4`; reconciled to match the cluster per `docs/spec_consistency_review.md` finding I3.
   - Any tightening to `1e-4` = must-fix (unjustified fragility per spec §10.4 justification). Any loosening past `5e-3` per-action = must-fix.
   - **Test coverage:** (1) blueprint strategies match, (2) refinement strategies match, (3) combined strategy table matches, (4) dispatch paths consistent (15 BB / 100 BB / 251 BB behave identically in both tiers).
   - **Probe:** `grep -nE '5e-?3|0\.005' tests/test_preflop_diff.py` — expected per-action tolerance hits.
   - **Probe:** `grep -nE '1e-?3|0\.001' tests/test_preflop_diff.py` — expected per-spot game-value tolerance hits.
   - **Probe:** `grep -nE '1e-?4|0\.0001' tests/test_preflop_diff.py` — expected ZERO hits (the rejected tighter tolerance).
   - **Probe:** the 4 test functions all run on small fixtures (e.g., tiny synthetic abstraction from `tests/fixtures/hunl_preflop_fixtures.py` — `tiny_synthetic_abstraction()` reused from PR 5).
   - **Evidence stub:** `tests/test_preflop_diff.py:?` (4 test functions + tolerance constants); `tests/fixtures/hunl_preflop_fixtures.py:?` (fixture builders).

5. **HUNLConfig integration with existing postflop config — no field conflicts.** [must-fix on schema break]
   - Per spec §2 / §5: PR 9 reuses `HUNLConfig` from PR 3 unchanged for the engine; preflop-specific kwargs flow through `solve_hunl_preflop(blueprint_iterations=..., refine_iterations=..., reach_threshold=..., max_memory_gb=...)`.
   - **Verify no NEW fields added to `HUNLConfig`** (preflop-specific kwargs live in the solver function signature, not the dataclass). If the implementer added e.g. `HUNLConfig.blueprint_iterations` → schema bloat, should-fix; if they added a field that conflicts with an existing PR 3 field → must-fix.
   - **PR 8 schema alignment:** PR 8 adds `HUNLConfig.use_pcs: bool = False`. PR 9 should not conflict with that field. If PR 9 lands before PR 8, the field will be added by PR 8; if PR 8 already landed (check `git log main`), the field exists. Either way, PR 9 must not perturb it.
   - **Probe:** `grep -nE 'class HUNLConfig|@dataclass' poker_solver/hunl.py | head -5`; then read the field list. Compare against PR 3's `HUNLConfig` (`docs/pr3_prep/pr3_spec.md` definition). New fields = flag.
   - **Probe:** the `PreflopSolveResult` extends `HUNLSolveResult` (per spec §4 — new fields `blueprint_strategy`, `refined_subgames`, `unrefined_subgames`, `dispatched_to_pushfold`). Verify `HUNLSolveResult` is reused as the parent type, NOT redefined.
   - **Evidence stub:** `poker_solver/hunl.py:?` (HUNLConfig fields); `poker_solver/preflop_solver.py:?` (PreflopSolveResult dataclass with parent=HUNLSolveResult).

6. **Memory profiler shows preflop solve fits in 16 GB budget per the spec §3.4 / §12 table.** [must-fix on OOM at 100 BB; should-fix on profiler drift]
   - Per spec §3.4 / §12: blueprint pass must fit in **~10-14 GB** at 100 BB with 256/128/64 abstraction + 1-size/1-cap blueprint menu. `max_memory_gb` default = 14.0. Subgame refinement uses same budget per subgame, ONE AT A TIME.
   - PR 5's `MemoryProbe` is reused unchanged (per §12). 10% `psutil` RSS calibration check from PR 5 §7.6 applies (per consistency review I4: PR 9 explicitly inherits the same tolerance).
   - **Test:** `test_blueprint_memory_under_budget_at_100bb` (spec §10.1 #5): `BlueprintResult.memory_report.grand_total_bytes < 14 * 1024**3`. Marked `@pytest.mark.slow`.
   - **Verify sequential subgame refinement:** between subgames, `del solver` + `gc.collect()` (per §12 "the previous solve's regret tables and infoset dicts are explicitly dropped"). If subgames coexist in memory → memory leak across the chain → must-fix.
   - **Probe:** `grep -nE 'gc\.collect|del solver' poker_solver/subgame_refiner.py poker_solver/preflop_solver.py` — expected hits in the refinement loop.
   - **Probe:** `grep -n 'max_memory_gb' poker_solver/preflop_solver.py` — expected threaded through to MemoryProbe.
   - **Test for tier-tightening at 200-250 BB:** at 200-250 BB, the blueprint uses 64/32/16 abstraction (per spec §3.4 table). If the implementer hardcoded 256/128/64 across all depths → memory blowout at deep stacks, must-fix.
   - **Evidence stub:** `poker_solver/preflop_solver.py:?` (tier selection logic); `poker_solver/subgame_refiner.py:?` (sequential refinement + drop); `tests/test_hunl_preflop_blueprint.py:?` (memory test).

7. **Closes the public OSS preflop gap.** [should-fix on incomplete coverage]
   - Per spec §1 goal: "Ship the **first end-to-end HUNL preflop → river solve** in both tiers (Python reference + Rust production)."
   - Confirm both tiers actually deliver: Python `solve_hunl_preflop` is callable end-to-end, AND Rust `solve_hunl_preflop_rust` (PyO3 binding per spec §5 `lib.rs` change) is callable end-to-end.
   - CLI smoke test (per spec §17): `poker-solver solve --game hunl --hunl-mode preflop --stacks 100 --blueprint-iterations 5000 --refine-iterations 2000 --abstraction /path/to/256_128_64.npz` runs to completion in <2 hours on Python, <30 min on Rust, produces a `PreflopSolveResult`.
   - **Published-ref anchors (spec §10.3 #4 `test_published_ref_sb_open_raise_100bb`):**
     - SB AA: ≥ 95% non-fold (open) at 100 BB
     - SB 72o: ≤ 40% non-fold (mostly fold) at 100 BB
     - SB JJ: open frequency in [0.85, 1.0]
     - BB defense vs 2.5x SB open: ≥ MDF(reasonable_pot_odds)
   - **End-to-end exploitability:** `test_combined_exploitability_under_0_05_bb_per_hand` (spec §10.3 #5): < 0.05 BB/hand on the Pio-published 100 BB cash-game validation fixture. Marked `@pytest.mark.slow`. CI runs relaxed variant (5k blueprint + 2k refine, < 0.5 BB/hand). If the test exists and the slow path is documented to pass → looks-good. If absent or fails → must-fix.
   - **Probe:** `grep -nE 'def test_published_ref|def test_combined_exploitability' tests/test_hunl_preflop_integration.py` — expected 2 hits.
   - **Evidence stub:** `tests/test_hunl_preflop_integration.py:?` (published-ref + exploitability tests).

8. **Canonical-class preflop chance generator + combinatorial weights.** [must-fix on weight bug; high-prob defect]
   - Per spec §5 + §13 risk #5: the new `_enumerate_preflop_hole_outcomes_canonical()` generator in `poker_solver/hunl.py` yields the 169×169 unique hand-class chance outcomes with correct combinatorial weights.
   - **Weights MUST be correct:**
     - Pairs (e.g., AA): 6 combos
     - Suited non-pairs (e.g., AKs): 4 combos
     - Offsuit non-pairs (e.g., AKo): 12 combos
   - **Blocker-awareness:** when hero has AA, opponent class AA has only 1 combo remaining (not 6); the generator must reduce opponent combo counts by hero's holdings.
   - **Test:** `test_preflop_canonical_chance_weights_correct` (in `tests/test_hunl_preflop_blueprint.py`) validates against brute-force enumeration on a tiny subset. Per spec §13 risk #5. If absent → should-fix (high-prob defect class undercoverage); if present and passing → looks-good.
   - **Opt-in default:** per spec §14 Decision #8: "canonical-class generator added to `hunl.py` as an opt-in, with the existing 1.6M-combo generator preserved unchanged." If the implementer REPLACED the 1.6M generator instead of adding alongside → scope-leak override of default → must-fix unless approved in `pr_report.md`.
   - **Probe:** `grep -n '_enumerate_preflop_hole_outcomes' poker_solver/hunl.py` — expected ≥2 functions (original + `_canonical`).
   - **Probe:** `grep -n 'chance_strategy' poker_solver/hunl.py` — expected the dispatch logic ("if config.starting_street == Street.PREFLOP and chance_strategy == 'canonical_classes'").
   - **Evidence stub:** `poker_solver/hunl.py:?` (canonical generator); `tests/test_hunl_preflop_blueprint.py:?` (weight test).

9. **No regression to postflop (PR 5 unchanged).** [must-fix on PR 5 break]
   - Per spec §5 "NOT modified": `poker_solver/hunl_solver.py` (PR 5) — the postflop solver is CALLED by `subgame_refiner.py` but NOT modified.
   - All PR 1-8 tests pass unchanged (per spec §17 success criteria: "All PR 1–8 tests pass unchanged (the dispatch branch in `solver.solve` must not perturb existing Kuhn/Leduc/HUNL-postflop behavior).")
   - **Probe:** `git diff main..HEAD --stat -- poker_solver/hunl_solver.py poker_solver/dcfr.py poker_solver/abstraction/ poker_solver/charts/` — expected empty for `hunl_solver.py`, `dcfr.py`, `abstraction/`, `charts/`.
   - **Probe:** the existing test suite passes unchanged. Implementer's `pr_report.md` should cite "all PR 1-8 tests pass" with a clean `pytest -v` invocation.
   - **Allowed modifications:** `solver.py` (dispatch branch added), `cli.py` (preflop mode flags added), `hunl.py` (canonical-class generator added), `__init__.py` (re-exports added). All four are §5 "Modify" entries.
   - **Evidence stub:** `git diff --stat` output; implementer pr_report.md test-status block.

10. **Warm-start regret loading: copy at right keys.** [must-fix on stale mapping]
    - Per spec §8.3: "For every postflop infoset key that exists in *both* the blueprint and the refinement tree (same board + same betting history + same hand bucket), copy the blueprint's regret values into the refinement's regret table at iteration 0."
    - Verify the key-matching logic in `_warm_start_from_blueprint` (`poker_solver/subgame_refiner.py`): infoset keys constructed identically in blueprint and refinement.
    - **Failure mode:** if blueprint uses key format `street:board:history:bucket` and refinement uses `street:bucket:history:board` (different field order), the keys never match, warm start does nothing silently. Test should catch.
    - **Test:** `test_refinement_warm_start_speeds_convergence` (spec §10.2 #2) — soft assertion that warm-started solve reaches `exploitability < 0.1` in fewer iterations than cold-started. If absent → should-fix.
    - **Evidence stub:** `poker_solver/subgame_refiner.py:?` (_warm_start_from_blueprint); `tests/test_hunl_preflop_refinement.py:?` (warm-start speedup test).

11. **Range extraction from blueprint: correct CFR reach-probability math.** [must-fix on biased ranges]
    - Per spec §8.2: "`p0_range[hand_class]` = `Σ_paths reach_prob(path_to_subgame_root | hand_class)` where `path_to_subgame_root` is all preflop betting paths leading to the subgame, and the reach is computed under the blueprint's strategy."
    - Verify `_extract_ranges_from_blueprint` in `poker_solver/subgame_refiner.py` implements this exactly. Standard CFR reach-probability recurrence: at each preflop infoset, multiply both players' action probabilities to get the reach contribution.
    - **Failure mode:** if the implementer used uniform ranges (1/169 per hand class) instead of blueprint-derived ranges, the refinement is solving a wrong-input problem → biased refined strategies → must-fix.
    - **Test:** `test_refinement_ranges_extracted_correctly` (spec §10.2 #5): assert `p0_range["AA"] > p0_range["72o"] * 1.5` in a 3-bet pot subgame (SB rarely 3-bets 72o). Soft sanity check.
    - **Audit explicit focus area:** per spec §18 "Range extraction from blueprint. The ranges arriving at each subgame are the load-bearing input to refinement; mis-computed ranges produce wrong refined strategies. Audit traces the math against the CFR reach-probability recurrence."
    - **Evidence stub:** `poker_solver/subgame_refiner.py:?` (range extraction); `tests/test_hunl_preflop_refinement.py:?` (range sanity test).

12. **No new third-party deps; no AGPL contamination.** [must-fix on AGPL]
    - Per spec §5: "**`pyproject.toml`** — no new third-party deps. (PR 5 already pulled in `psutil`; PR 9 reuses it.)"
    - **Probe:** `git diff main..HEAD -- pyproject.toml` — expected empty (no deps added).
    - **Probe:** `git diff main..HEAD -- Cargo.toml crates/cfr_core/Cargo.toml` — expected empty unless a benign dev-dep.
    - **AGPL check:** `references/code/postflop-solver/` is AGPL — no code copied. PR 9 may CITE the MIT-licensed `noambrown_poker_solver` if patterns are mirrored (per spec §18 "License hygiene"). Verify Rust files (`preflop.rs`, `blueprint.rs`, `subgame.rs`) headers don't contain verbatim AGPL code.
    - **Probe:** `grep -F "MIT" crates/cfr_core/src/preflop.rs crates/cfr_core/src/blueprint.rs crates/cfr_core/src/subgame.rs` — if MIT-attributed port from `noambrown_poker_solver`, expected attribution comment in file header.
    - **Evidence stub:** `git diff` output; file headers.

13. **Clippy + format clean + mypy strict-clean.** [must-fix on warning]
    - Per spec §17 success criteria:
      - `ruff check poker_solver tests` clean.
      - `ruff format --check` clean.
      - `mypy poker_solver/preflop_solver.py poker_solver/blueprint.py poker_solver/subgame_refiner.py` strict-clean.
      - `cargo clippy --all-targets -- -D warnings` clean on Rust additions.
    - **Probe:** in the worktree, run the four checks (or read implementer's pr_report.md citing them clean).
    - **Evidence stub:** lint/clippy/mypy output.

14. **DCFR algorithmic invariants unchanged.** [must-fix on algorithm drift]
    - Per spec §5 "NOT modified": "`poker_solver/dcfr.py` — DCFR algorithm unchanged. Hyperparameters (α=1.5, β=0, γ=2.0) unchanged."
    - **Probe:** `git diff main..HEAD --stat -- poker_solver/dcfr.py` — expected empty (zero-diff on dcfr.py).
    - **Probe:** `grep -nE 'alpha\s*=\s*1\.5|beta\s*=\s*0|gamma\s*=\s*2\.0' poker_solver/dcfr.py` — confirm the hyperparameters are still the locked values.
    - **Audit explicit focus area** per spec §18: "DCFR algorithmic invariants. `dcfr.py` is unchanged; the audit confirms."
    - **Evidence stub:** `git diff --stat` output; `poker_solver/dcfr.py:?` hyperparameter constants.

15. **Reproducibility: same seed + config + abstraction → identical output in both tiers.** [should-fix on flakiness]
    - Per spec §18 audit focus area: "Reproducibility. Same seed + config + abstraction → identical blueprint + refined strategies in both tiers."
    - Verify `seed: int | None = None` kwarg on `solve_hunl_preflop`, `build_blueprint`, `refine_subgame` (per spec §4 signatures).
    - **Test idea:** run the same `build_blueprint(..., seed=7)` twice; assert outputs are byte-identical. If absent → should-fix (high-prob silent-flakiness defect class). The implementer's `pr_report.md` should cite a determinism test or a manual two-run check.
    - **Probe:** `grep -nE 'seed' poker_solver/preflop_solver.py poker_solver/blueprint.py poker_solver/subgame_refiner.py | head -20` — expected hits for each module's solve function.
    - **Evidence stub:** module signatures; determinism test if present.

16. **`on_progress` callback wired (PR 10b launch-readiness).** [should-fix on missing callback]
    - Per spec §4 (Python signatures): each of `solve_hunl_preflop`, `build_blueprint`, `refine_subgame` accepts `on_progress: Callable[[int, float, MemoryReport], None] | None = None`.
    - When non-None, invokes `on_progress(iteration_number, current_exploitability_bb, memory_snapshot)` every `log_every` iterations (default 50).
    - Threaded through: `solve_hunl_preflop` → `build_blueprint` (blueprint pass) AND `refine_subgame` (refinement pass).
    - Cancellation is NOT part of the contract (per spec §4 explicit note).
    - **Probe:** `grep -n 'on_progress' poker_solver/preflop_solver.py poker_solver/blueprint.py poker_solver/subgame_refiner.py` — expected hits in each.
    - **Evidence stub:** module signatures + invocation sites.

17. **Coarse-menu enforcement in blueprint.** [should-fix on menu leakage]
    - Per spec §7.1: blueprint postflop menu = 1 size (0.75 pot) + all-in, 1-cap. Per spec §7.2: preflop menu = FULL PR 3 menu (33/75/100/150/200% + all-in, 4-cap).
    - Test `test_blueprint_coarse_menu_respected` (spec §10.1 #6): "assert that no postflop infoset in the blueprint has more than `len(postflop_menu) + 3` actions (where the +3 covers fold/call/all-in). Catches accidental menu leakage from the full PR 3 abstraction."
    - If absent → should-fix; if present and passing → looks-good.
    - **Probe:** `grep -nE 'def test_blueprint_coarse_menu_respected' tests/test_hunl_preflop_blueprint.py` — expected one hit.
    - **Evidence stub:** `tests/test_hunl_preflop_blueprint.py:?` (menu-respect test).

18. **Code size within budget + implementer report accuracy.** [should-fix on bloat / discrepancy]
    - Expected diff: ~2000-3500 LoC Python + ~1500-2500 LoC Rust + tests (per spec §9 consolidated LoC estimates).
    - **Probe:** `git diff main..HEAD --shortstat`.
    - **Implementer report cross-check:** file list / LoC / test-pass status in each `pr_report.md` matches actual diff. Discrepancies → flag.
    - **Evidence stub:** `git diff --shortstat`; implementer report sections.

## Output format

Write your report to `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/audit_report.md` with this exact structure:

```markdown
# PR 9 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-9-preflop
**Worktree:** /Users/ashen/Desktop/poker_solver_worktrees/pr-9-preflop
**Branched-from:** main tip 62c75d5 (post-v1.0.0 GA)
**Diff size:** [N modified + M created files = ±X LoC total]

**Test status:** [pytest pass/fail; cargo test pass/fail; ruff/mypy/clippy status]

**Dispatch ordering:** [§6 canonical ordering — PASS/FAIL with boundary-test results at 15/16/251 BB]

**Memory budget:** [pass/fail at 100 BB; tier-tightening at deeper stacks verified]

**Implementer reports:** [reviewed; accurate / discrepancies noted]

## Item-by-item correctness verification (focus areas 1-18)

[Each: PASS/FAIL + file:line evidence + verification note. HIGH-PROB items 1/2/3/4/5/8 get paragraph-level discussion even if no defect.]

## Must-fix

[4-bet/5-bet cap violation; ante not threaded; push/fold short-circuit ordering broken; Rust diff tolerance drifted; HUNLConfig field conflict; memory budget blown at 100 BB; canonical-class chance weights wrong; PR 5 (postflop) modified; warm-start key mismatch; ranges uniform instead of blueprint-derived; AGPL contamination; clippy/mypy/ruff warnings; dcfr.py modified. Each: file:line + what + fix.]

[If none: "None found." + justification.]

## Should-fix

[Cap-enforcement test missing; ante integration test missing; reproducibility (seed determinism) test missing; on_progress callback not wired; coarse-menu test missing; deferred-decision override not justified in pr_report; report discrepancies; canonical generator replaces (instead of adds alongside) original. Each: file:line + description + fix.]

## Nice-to-fix

[Style, naming, comments. Cosmetic.]

## Looks good (explicit confirmation of audit focus areas)

[Numbered list 1-18 matching the 18 audit focus areas above. Each: one-paragraph confirmation with file:line evidence.]

## Dispatch ordering verification (canonical §6)

[Walk through poker_solver/solver.py dispatch and confirm it implements §6's ordering EXACTLY. Cite line numbers. Verify all three boundary tests (15 BB / 16 BB / 251 BB) pass.]

## Memory budget verification (§3.4 / §12 tier table)

[Test the blueprint's memory_report at 100 BB. If the test is marked `@pytest.mark.slow` and isn't run in CI, rely on the implementer's pr_report.md citation of the slow-path result. Per-tier verification at 100/150/200/250 BB if implementer cited.]

## Spec coverage gaps (missing tests)

[Items in pr9_spec.md not covered by tests. Each: spec section + what's missing + suggested follow-up.]

## License compliance

[Explicit statement: zero new third-party deps; no AGPL code; MIT attribution present if vector_eval.cpp or other MIT references were ported. Cite specific files + headers.]

## Implementer-report accuracy audit

[Cross-check pr_report files against actual diff. Discrepancies (file list, LOC, test status, override decisions) listed here with severity.]

## Overall verdict

[One of: "READY for commit", "READY for commit AFTER must-fix items resolved", or "NOT READY — see must-fix". 2-3 sentence justification. Expected verdict given the novel blueprint+refinement architecture + the 15 BB dispatch boundary + the canonical-class chance generator complexity: READY-WITH-PATCHES is the modal outcome; READY is plausible if all four test categories (blueprint / refinement / integration / diff) are green; NOT-READY would indicate dispatch ordering violation, biased PCS-like estimator bug in range extraction, or PR 5 regression — escalate to orchestrator before writing.]
```

## Severity rules

- **must-fix:** dispatch ordering violation (push/fold short-circuit not first); 4-bet/5-bet cap not enforced at preflop; ante not threaded; canonical-class chance weights wrong (combinatorial math broken); range extraction uses uniform ranges instead of blueprint-derived; warm-start key mismatch; PR 5 (`hunl_solver.py`) modified; `dcfr.py` modified (hyperparameter drift); diff tolerance below 5e-3 per-action OR tightened to 1e-4; HUNLConfig field conflicts; memory blowout at 100 BB; AGPL contamination; clippy/mypy/ruff warnings; preflop boundary tests fail (15/16/251 BB). Blocks PR.
- **should-fix:** cap-enforcement test missing; ante integration test missing; canonical generator REPLACED (instead of added alongside) original 1.6M generator; reproducibility test missing; coarse-menu test missing; on_progress callback not threaded; pr_report.md discrepancies vs actual diff; spec-coverage gaps; deferred-decision overrides without user signoff. Doesn't block.
- **nice-to-fix:** style, naming, comments. Pure polish.

When in doubt: anything that breaks the §6 canonical dispatch ordering, breaks the Pluribus blueprint+refinement architecture, breaks the published-ref preflop anchors (AA opens ≥95%, 72o folds ≥60%), or regresses postflop (PR 5) → must-fix.

## Procedural notes

- **READ-ONLY DIFF REVIEW.** Cite **file paths and line numbers** for every finding. **Do NOT commit, push, or modify any code on `pr-9-preflop`.** The only write allowed is `docs/pr9_prep/audit_report.md`.
- Inspect via the worktree path `/Users/ashen/Desktop/poker_solver_worktrees/pr-9-preflop` to avoid contending with the shared working tree. Per `feedback_no_concurrent_branch_ops` discipline: parallel agents may be active in the shared working tree; never `git checkout` to switch branches there.
- Quote spec section numbers when verifying claims (`pr9_spec.md` §1 / §3 / §4 / §5 / §6 / §7 / §8 / §10 / §11 / §12 / §13 / §14 / §17 / §18).
- Quote implementer-report section numbers when cross-checking deliverables (or quote pr_report_agent_a.md / agent_b / agent_c if reports are split).
- Scope-silent behavior → "Spec coverage gaps".
- HIGH-PROB risk surfaces (focus areas 1, 2, 3, 4, 5, 8) MUST get paragraph-level discussion even with no defect found.
- For slow tests (`@pytest.mark.slow`): if not run in CI, rely on implementer's pr_report.md citation of slow-path results. Static verification of test presence (decorator + assertion structure) is sufficient.
- **No branch switches.** Stay in your audit shell. Inspect the worktree via absolute path; do not `git checkout main` on either the worktree or the shared tree.

Begin by reading the spec (`pr9_spec.md` — especially §6 canonical dispatch + §3 architecture + §7 blueprint design + §8 refinement + §17 success criteria), then the implementer report(s), then the diff (`git -C /Users/ashen/Desktop/poker_solver_worktrees/pr-9-preflop diff main..HEAD --stat`). Then write the report.

**Expected verdict given the novel blueprint+refinement architecture + the §6 dispatch boundary at 15 BB + the canonical-class chance generator complexity + the 0.05 BB/hand exploitability target: READY-WITH-PATCHES is the modal outcome**; READY is plausible if all 18 focus areas check clean; NOT-READY would indicate dispatch ordering violated, range extraction biased, PR 5 regressed, or AGPL contamination — escalate to orchestrator before writing if you see any of these signals.
