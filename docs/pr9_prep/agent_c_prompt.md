# PR 9 Agent C — Rust port + PyO3 bindings + all Python tests

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 9 Agent C.**
**Your scope:** the Rust production-tier port of Agent A's blueprint + Agent B's subgame refiner + the top-level preflop solver, the PyO3 bindings exposing the Rust entry points to Python, AND all Python test files (blueprint, refinement, integration, Python↔Rust differential, plus the fixture builders). You write the tests strictly from the PR 9 spec — you do NOT read Agent A's or Agent B's code while authoring tests.
**Your contract:** ship `crates/cfr_core/src/preflop.rs` + `blueprint.rs` + `subgame.rs` (mechanical Rust port of Python) + PyO3 bindings in `lib.rs` exposing `solve_hunl_preflop_rust`, `build_blueprint_rust`, `refine_subgame_rust`; ship `tests/test_hunl_preflop_blueprint.py` (~6 tests), `tests/test_hunl_preflop_refinement.py` (~5 tests), `tests/test_hunl_preflop_integration.py` (~5 tests), `tests/test_preflop_diff.py` (~4 tests), `tests/fixtures/hunl_preflop_fixtures.py`. Spec is the interface lock for both Rust port AND tests.
**Your success criteria:** `cargo clippy --all-targets -- -D warnings` clean on Rust additions; PyO3 bindings importable from Python (`from poker_solver._rust import solve_hunl_preflop_rust`); all Python tests pass against Agent A + Agent B's implementations after they land; differential tests Python↔Rust within tolerance `5e-3` per-action / `1e-3 × base_pot` per-spot game value (NOT `1e-4` — outlier from earlier draft per consistency review I3); ruff + black clean on test files; ALL existing tests still pass.
**File ownership:** you own `crates/cfr_core/src/preflop.rs`, `crates/cfr_core/src/blueprint.rs`, `crates/cfr_core/src/subgame.rs`, surgical edits to `crates/cfr_core/src/lib.rs`. You own ALL new Python test files + the fixture builder. You may NOT touch any Python `.py` non-test file.

---

## Strict file ownership

**You own (create new):**
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/preflop.rs` (new file; ~600 LOC)
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/blueprint.rs` (new file; ~400 LOC)
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/subgame.rs` (new file; ~300 LOC)
- `/Users/ashen/Desktop/poker_solver/tests/test_hunl_preflop_blueprint.py` (new file; ~6 tests)
- `/Users/ashen/Desktop/poker_solver/tests/test_hunl_preflop_refinement.py` (new file; ~5 tests)
- `/Users/ashen/Desktop/poker_solver/tests/test_hunl_preflop_integration.py` (new file; ~5 tests)
- `/Users/ashen/Desktop/poker_solver/tests/test_preflop_diff.py` (new file; ~4 tests)
- `/Users/ashen/Desktop/poker_solver/tests/fixtures/hunl_preflop_fixtures.py` (new file)

If `tests/fixtures/__init__.py` doesn't already exist, create it empty.

**You may surgically modify:**
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/lib.rs` — add PyO3 bindings for `solve_hunl_preflop_rust`, `build_blueprint_rust`, `refine_subgame_rust`. This file is shared with prior PRs (PR 6, PR 7, PR 8) — your edits are STRICTLY ADDITIVE: add new `#[pyfunction]` entries + register them in the `#[pymodule]` block. Do NOT modify existing bindings.

**You must NOT touch:**
- Any Python `.py` non-test file (`poker_solver/preflop_solver.py`, `poker_solver/blueprint.py`, `poker_solver/subgame_refiner.py`, `poker_solver/hunl.py`, etc.) — Agents A and B own these.
- Existing Rust files (`dcfr.rs`, `game.rs`, `kuhn.rs`, `leduc.rs`, `solver.rs`, plus any PR 6/7/8 additions like `tree.rs`, `pcs.rs`, etc.) — frozen. You read them for the port pattern; you do NOT modify them.
- Existing test files (`tests/test_*.py` from PR 1 through PR 8) — frozen. Your new test files are purely additive.
- `Cargo.toml` — no new Rust deps for PR 9 (PR 6 already pulled in `pyo3`, `ndarray`, etc.).
- The spec itself (`docs/pr9_prep/pr9_spec.md`) — read-only. If you find a spec ambiguity, flag it in your report; the orchestrator updates the spec, not you.

**Critical fan-out invariant:** you are writing the Python tests strictly from the spec WITHOUT reading Agent A's or Agent B's Python implementations. The dividend of the fan-out pattern is that your tests independently encode the spec — if your tests fail against the impl, it's a real bug OR a real spec ambiguity, and the orchestrator resolves it. Reading the impl would defeat this dividend.

(Exception: if a test fails due to an obvious typo in YOUR test code, you may inspect the impl to figure out the typo. But you do not adjust tests to match impl behavior — only to fix your own bug.)

For the Rust port: you DO read Agent A's and Agent B's Python implementations as the source of the mechanical translation (this is how PR 6 did the postflop port). The Rust port IS the implementation; the tests are written from spec alone. **Author the tests BEFORE the Rust port** to enforce this discipline.

If you discover an awkward signature or contract gap mid-implementation, **do not silently change the spec'd interface**. Stop and write a short note to the orchestrator describing the conflict; the orchestrator reconciles.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/pr9_spec.md`. Internalize the ENTIRE spec; you author tests from it. Especially §1 (goal), §3 (architecture), §4 (file structures Agents A+B produce — your test imports), §5 (file modifications), §6 (dispatch composition — locks `test_preflop_dispatch_*`), §7 (blueprint design — locks blueprint tests), §8 (refinement — locks refinement tests), §10 (test plan — your master list), §11 (Agent C deliverables — your Rust + test scope), §13 (risks), §14 decisions (defaults locked below), §17 (success criteria — what your tests verify).
2. **Spec consistency review (recent amendments):** `/Users/ashen/Desktop/poker_solver/docs/spec_consistency_review.md`. Especially I3 (DIFF-TEST TOLERANCE IS `5e-3` per-action / `1e-3 × base_pot` per-spot game value, NOT `1e-4` — your `test_preflop_diff.py` uses the corrected figures), I5 (combined exploitability <0.05 BB/hand target — your `test_combined_exploitability_under_0_05_bb_per_hand` enforces this), B4 (PR 9 §6 canonical dispatch — locks the boundary tests).
3. **The PLAN (locked decisions):** `/Users/ashen/Desktop/poker_solver/PLAN.md`. Especially §1 "Card abstraction" (256/128/64 default, stack-depth tier table) and §1 "Memory budget" (14 GB hard ceiling).
4. **The autonomous log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md`. Skim for PR 9 entries.
5. **PR 6 Rust port pattern (canonical template):** `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/pr6_spec.md` if present. The PR 6 spec defines the Rust port pattern PR 9 follows: flat-array compact tree, indexed traversal, PyO3 bindings via `#[pyfunction]`, differential tests with `5e-3 / 1e-3` tolerance. Read PR 6 for the port mechanics.
6. **Existing Rust surfaces you port + bind to:**
   - `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/dcfr.rs` — PR 6's DCFR core. Your `blueprint.rs` reuses this.
   - `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/lib.rs` — PyO3 module entry. You add new `#[pyfunction]` exports here.
   - Any PR 6/7/8 modules (`tree.rs`, `pcs.rs`, etc.) — read-only.
7. **Existing test style references (DO read for style; do NOT modify):**
   - `/Users/ashen/Desktop/poker_solver/tests/test_dcfr_diff.py` — diff test pattern Python ↔ Rust (PR 1).
   - `/Users/ashen/Desktop/poker_solver/tests/test_leduc_diff.py` — same pattern for Leduc (PR 2).
   - `/Users/ashen/Desktop/poker_solver/tests/test_hunl_core.py` — closest style match for HUNL game tests.
   - `/Users/ashen/Desktop/poker_solver/tests/test_pushfold.py` — push/fold chart test style (PR 3.5).
8. **PR 5 spec (for `solve_hunl_postflop` interface):** `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/pr5_spec.md`. PR 9's tests don't directly call this, but the refined-subgame parity test compares against it.
9. **Pluribus paper (canonical reference for blueprint + refinement pattern):** `references/papers/pluribus_brown_2019_science.pdf`. Page 4 covers the refinement pattern; PR 9 §16 cites the exact passages.
10. **Reference style — PR 5 Agent C prompt:** `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/agent_c_prompt.md`. Same shape and tone.
11. **License-aware sourcing patterns:** see §"License-aware sourcing" below.

## Default decisions LOCKED (do not deviate)

These defaults are from PR 9 spec §14 + the consistency review:

1. **Diff-test tolerance: `5e-3` per-action probability + `1e-3 × base_pot` per-spot game value** (spec §10.4 + consistency review I3). NOT `1e-4`. An earlier draft of the spec cited `1e-4`; reconciled to match the PR 6/7/8 cluster per `feedback_no_extrapolate.md` and the lesson that Rust HashMap iteration order × float-accumulation order makes tolerances tighter than `1e-3` unjustifiably fragile.
2. **Boundary tests at 15 BB / 16 BB / 251 BB are LOCKED** (spec §6 boundary tests). The names are `test_preflop_dispatch_pushfold_at_15bb`, `test_preflop_dispatch_solver_at_16bb`, `test_preflop_dispatch_error_at_251bb`. Verbatim.
3. **Combined exploitability target: <0.05 BB/hand on Pio 100 BB cash-game fixture** (spec §7.4 + §17 + §10.3 #5). Your `test_combined_exploitability_under_0_05_bb_per_hand` enforces this. CI relaxed variant: 5k blueprint + 2k refine iter, asserts <0.5 BB/hand (10× looser smoke).
4. **Slow tests marked `@pytest.mark.slow`** (per existing PR 5 / PR 6 convention). Tests with target wallclock > 60s wear the marker; CI skips by default; full convergence tests run in nightly.
5. **Tiny configs for non-slow tests** (per existing PR 5 / PR 6 convention). `bucket_counts=(4, 2, 2)`, `blueprint_iterations=100-500`, `refine_iterations=50-200`, etc. Total test wall-clock for non-slow: < 5 minutes.
6. **PR 9 §6 dispatch composition is canonical** (consistency review B4). Your dispatch tests assert the ordering: push/fold short-circuit first, then >250 BB error, then by `starting_street`.
7. **Blueprint postflop menu: 1 size (0.75-pot) + all-in, 1-cap** (spec §14 #2). Your `test_blueprint_coarse_menu_respected` (§10.1 #6) enforces this.
8. **Reach threshold: 1e-3** (spec §14 #4). Your `test_refinement_respects_reach_threshold` (§10.2 #4) enforces this.
9. **Lossless preflop** (PR 4 §7.12). Your tests assume preflop infosets are NEVER bucketed (`lookup_bucket(..., street=Street.PREFLOP)` returns -1; preflop infoset keys are lossless).
10. **`PreflopSolveResult` IS a subclass of `HUNLSolveResult` which IS a subclass of `SolveResult`** (PR 5 §14 #3 + consistency review N7). Your tests can `isinstance(result, SolveResult)` AND `isinstance(result, HUNLSolveResult)` AND `isinstance(result, PreflopSolveResult)`.
11. **`on_progress` kwarg is part of the public surface of `solve_hunl_preflop`, `build_blueprint`, AND `refine_subgame`** (launch-readiness patch; PR 10b consumer at `docs/pr10_prep/pr10b_spec.md` lines 152-156). Signature: `on_progress: Callable[[int, float, MemoryReport], None] | None = None`. The Rust port MUST thread this through: PyO3 bindings accept an optional `PyObject` callable, invoke it from Rust every `log_every` iterations with `(iteration, exploitability_bb, memory_snapshot)`. See PR 6's precedent for invoking Python callbacks from Rust (`Python::with_gil` + `callable.call1(...)`); if PR 6 didn't ship a callback-from-Rust pattern, model after PyO3 docs. Cancellation NOT in this contract.

## Public API you test (signatures from spec §4 + Agents A+B)

You import these from `poker_solver` (re-exported via Agent A's `__init__.py` edit):

```python
from poker_solver import (
    solve_hunl_preflop,
    PreflopSolveResult,
    BlueprintResult,
    SubgameKey,
    SubgameRefinementResult,
    build_blueprint,
    refine_subgame,
)

# Already-existing imports from PR 1 through PR 8:
from poker_solver import (
    HUNLConfig, HUNLPoker, Street, AbstractionTables,
    solve, SolveResult, HUNLSolveResult, MemoryReport,
    solve_hunl_postflop,
)

# Rust bindings (Agent C exports via lib.rs):
from poker_solver._rust import (
    solve_hunl_preflop_rust,
    build_blueprint_rust,
    refine_subgame_rust,
)
```

## Test plan (master list — implement EVERY test below)

Per PR 9 spec §10. Each test gets ONE function definition; the test names match spec §10 exactly so the orchestrator can grep for them.

### `tests/test_hunl_preflop_blueprint.py` (~6 tests, spec §10.1)

1. **`test_blueprint_converges_at_100bb`** (spec §10.1 #1) — `build_blueprint(preflop_config_100bb(), tiny_abstraction(), iterations=5_000)`; assert `exploitability_history[-1] < 1.0`. **Mark `@pytest.mark.slow`**; CI variant uses 500 iterations and asserts `< 5.0`.
2. **`test_blueprint_reach_probabilities_sum_to_one_at_root`** (spec §10.1 #2) — `sum(reach_probs[root_infosets]) == pytest.approx(1.0, abs=1e-6)`.
3. **`test_blueprint_leaf_values_computed_for_postflop_subgames`** (spec §10.1 #3) — for each preflop terminal that enters postflop (i.e., not a fold leaf), `BlueprintResult.leaf_values[subgame_key]` is finite and in `[-100, 100]` BB.
4. **`test_blueprint_strategy_covers_all_preflop_infosets`** (spec §10.1 #4) — for the 169 hand classes × ~3.4k preflop infosets, every reachable infoset (reach_prob > 0) has a strategy entry in `blueprint.strategy`.
5. **`test_blueprint_memory_under_budget_at_100bb`** (spec §10.1 #5) — `BlueprintResult.memory_report.grand_total_bytes < 14 * 1024**3`. Skipped if not run with `--run-slow`. **Mark `@pytest.mark.slow`**.
6. **`test_blueprint_coarse_menu_respected`** (spec §10.1 #6) — assert that no postflop infoset in the blueprint has more than `len(postflop_menu) + 3` actions (where +3 covers fold/call/all-in). Catches accidental menu leakage from the full PR 3 abstraction.

**Plus one ADDITIONAL test per spec §13 risk row 6:**

7. **`test_preflop_canonical_chance_weights_correct`** (spec §13 risk row 6; ADDITIONAL — not in §10.1 but spec-mandated via the canonical-class chance generator risk) — sample the canonical-class preflop chance outcomes (via `HUNLPoker._enumerate_preflop_hole_outcomes_canonical()`) and validate against a brute-force enumeration on a small slice. Specifically: sum of all outcome probabilities is 1.0 within `1e-9`; pair classes carry weight 6 × `combos_villain_after_blockers / 1326 * 1326`, etc. Tag with comment: `# additional: not in spec §10 but spec §13 risk row 6 mandates this validation.`

### `tests/test_hunl_preflop_refinement.py` (~5 tests, spec §10.2)

1. **`test_refine_subgame_parity_with_direct_postflop_solve`** (spec §10.2 #1) — for one subgame (e.g., flop 3-bet pot at 100 BB, board AsKsQh), compare `refine_subgame(...)` output to `solve_hunl_postflop(equivalent_config, ...)` (the direct PR 5 solve with the same ranges + abstraction). Strategies must agree within `5e-2` per action (loose; warm-start vs cold-start trajectories differ but converged strategies should match). **Mark `@pytest.mark.slow`**.
2. **`test_refinement_warm_start_speeds_convergence`** (spec §10.2 #2) — run the same subgame with and without warm start (toggle via internal flag if Agent B exposes one, OR by passing a fresh BlueprintResult-with-empty-strategy as the cold-start control); assert warm-start solve reaches `exploitability < 0.1` in fewer iterations than cold-start solve. Soft assertion (5e-1 slack); failure prompts user review. Documented in the test docstring: "soft assertion; failure prompts user review, not auto-fix."
3. **`test_refinement_uses_full_action_menu`** (spec §10.2 #3) — assert that the refined strategy contains infosets with the full 8-action menu (6 sizes + fold + call) at non-cap postflop nodes, even though the blueprint used only 3. Validates the menu-expansion property.
4. **`test_refinement_respects_reach_threshold`** (spec §10.2 #4) — `solve_hunl_preflop(..., reach_threshold=0.1)`; assert that all `refined_subgames.keys()` have `reach_probs > 0.1` and all `unrefined_subgames` have `reach_probs <= 0.1`.
5. **`test_refinement_ranges_extracted_correctly`** (spec §10.2 #5) — for a 3-bet pot subgame, assert that the extracted `p0_range["AA"]` (SB's reach with AA into the 3-bet-call subgame) > `p0_range["72o"]` (SB rarely 3-bets 72o). Soft sanity check.

### `tests/test_hunl_preflop_integration.py` (~5 tests, spec §10.3 + §10.5)

1. **`test_preflop_dispatch_pushfold_at_15bb`** (spec §10.3 #1 + §6 boundary tests) — call `solve(HUNLPoker(HUNLConfig(starting_stack=1500, starting_street=Street.PREFLOP)))`; assert `result.dispatched_to_pushfold is True` and `result.backend == "pushfold_chart"` (or whatever attribute PR 3.5 sets on the result type). Use the `result` interface; do NOT inspect internals.
2. **`test_preflop_dispatch_solver_at_16bb`** (spec §10.3 #2 + §6 boundary tests) — call `solve(HUNLPoker(HUNLConfig(starting_stack=1600, starting_street=Street.PREFLOP)))`; assert `result.dispatched_to_pushfold is False` and the preflop solver actually ran (`isinstance(result, PreflopSolveResult)`). Will likely require either a tiny abstraction fixture or accept a `pytest.raises(ValueError)` for "abstraction artifact not found" — pick the version that minimizes flakiness.
3. **`test_preflop_dispatch_error_at_251bb`** (spec §10.3 #3 + §6 boundary tests) — call with `starting_stack=25_100`; assert `pytest.raises(ValueError, match="250")`.
4. **`test_published_ref_sb_open_raise_100bb`** (spec §10.3 #4) — at 100 BB, solve preflop fully (or use a pre-cached fixture); for the SB-first-action infoset with hand `AA`, assert the strategy assigns `>= 95%` probability to non-fold actions (open). For `72o`, assert `>= 60%` fold. For `JJ`, assert open frequency in `[0.85, 1.0]`. Loose published-ref anchors. **Mark `@pytest.mark.slow`**.
5. **`test_combined_exploitability_under_0_05_bb_per_hand`** (spec §10.3 #5 + §7.4 NEW + consistency review I5) — at 100 BB, full blueprint + refinement; sample 5 representative reached infosets across preflop and refined postflop subgames; for each, compute exploitability via the existing `solver.exploitability` interface (PR 1 utility) and assert each is `< 0.05 BB/hand`. **Mark `@pytest.mark.slow`**. CI relaxed variant at 5k blueprint iter + 2k refine iter asserts `< 0.5 BB/hand` (10× looser smoke).

**Plus intuition-gauntlet additions per spec §10.5:**

6. **`test_preflop_bb_defense_meets_mdf_vs_3bet_100bb`** (spec §10.5 MDF gauntlet) — at 100 BB after SB opens 2.5 BB and faces a 3-bet to 8 BB by BB, the SB's *defense frequency* (call + 4-bet) must be `>= MDF(8_BB_to_call, 11.5_BB_pot) = 41%`. Soft assertion; document failure mode. **Mark `@pytest.mark.slow`**.
7. **`test_preflop_4bet_range_polarized_at_100bb`** (spec §10.5 polarization gauntlet) — the SB's 4-bet range should be polarized (mix of value 4-bets like AA/KK + bluff 4-bets like A5s) rather than linear. Soft assertion: `4bet_freq("KQs") < 4bet_freq("A5s") * 0.5`. Document soft. **Mark `@pytest.mark.slow`**.

### `tests/test_preflop_diff.py` (~4 tests, spec §10.4 — Python ↔ Rust differential)

**Tolerance per consistency review I3: `5e-3` per-action probability + `1e-3 × base_pot` per-spot game value.** Quote in test docstrings.

1. **`test_preflop_diff_blueprint_strategies_match`** (spec §10.4 #1) — `build_blueprint(...)` in Python (Agent A) and `build_blueprint_rust(...)` (Agent C's port); assert per-infoset strategies agree within `5e-3` per action, per-spot game value within `1e-3 × base_pot`.
2. **`test_preflop_diff_refinement_strategies_match`** (spec §10.4 #2) — same tolerances for one refined subgame (Python `refine_subgame` vs Rust `refine_subgame_rust`).
3. **`test_preflop_diff_combined_strategy_table`** (spec §10.4 #3) — full `solve_hunl_preflop` in both tiers (Python + Rust); assert combined strategy tables match within the same `5e-3 / 1e-3` cluster.
4. **`test_preflop_diff_dispatch_paths_consistent`** (spec §10.4 #4) — at 15 BB (push/fold), at 100 BB (solver), at 251 BB (error), both tiers behave identically. Compare via the public `solve()` Python interface AND `solve_hunl_preflop_rust(...)` direct call.

### `tests/fixtures/hunl_preflop_fixtures.py`

Per spec §4: fixture builders for reuse across the test files.

```python
from poker_solver import (
    HUNLConfig, HUNLPoker, Street, AbstractionTables,
)


def preflop_config_100bb() -> HUNLConfig:
    """Standard 100 BB preflop config: starting_stack=10_000 cents, blinds
    50/100 cents, ante=0, starting_street=PREFLOP, full PR 3 menu.
    """
    return HUNLConfig(
        starting_stack=10_000,
        small_blind=50,
        big_blind=100,
        ante=0,
        starting_street=Street.PREFLOP,
        # default PR 3 menu + 4-cap preflop / 3-cap postflop
    )


def preflop_config_50bb() -> HUNLConfig:
    """50 BB preflop config for short-stack tests."""
    return HUNLConfig(
        starting_stack=5_000,
        small_blind=50,
        big_blind=100,
        ante=0,
        starting_street=Street.PREFLOP,
    )


def preflop_config_200bb() -> HUNLConfig:
    """200 BB preflop config — uses tier-tightened 128/64/32 abstraction
    per PLAN.md §1 stack-depth table.
    """
    return HUNLConfig(
        starting_stack=20_000,
        small_blind=50,
        big_blind=100,
        ante=0,
        starting_street=Street.PREFLOP,
    )


def tiny_synthetic_abstraction() -> AbstractionTables:
    """Reuse PR 5's tiny synthetic abstraction (bucket counts (4, 2, 2),
    H=10). Built in-memory; no .npz round-trip needed for tests."""
    # If PR 5's fixture file exists at tests/fixtures/hunl_solve_fixtures.py,
    # import its tiny_synthetic_abstraction() and re-export here.
    # Otherwise, construct one inline (small uint8 arrays, str-keyed dicts).
    ...


def small_3bet_pot_subgame_key():
    """SubgameKey for a 3-bet pot at 100 BB, used in refinement parity
    tests. Pot = 17 BB (after SB opens 2.5x, BB 3-bets to 8x, SB calls)."""
    from poker_solver import SubgameKey
    return SubgameKey(
        starting_street=Street.FLOP,
        board=(),
        pot=1700,  # 17 BB in cents
        p0_contribution=800,
        p1_contribution=800,
        preflop_betting_history="r25/r80/c",
    )
```

## Rust port (mechanical translation, PR 6 pattern)

You port Agent A's `blueprint.py` and `preflop_solver.py` and Agent B's `subgame_refiner.py` into three Rust modules. Pattern: identical to PR 6's postflop port. Mechanical translation, no algorithmic deviation.

### `crates/cfr_core/src/blueprint.rs`

Port of `poker_solver/blueprint.py`. Functions: `build_blueprint(...) -> BlueprintResult` (Rust struct). Uses PR 6's `dcfr.rs` core for the DCFR solve. Memory budget enforcement via Rust's `psutil`-equivalent (PR 5 picked `psutil` for Python; for Rust, use the existing PR 6 instrumentation if available, OR compute RSS via `/proc/self/status` on Linux + `task_info` on macOS via the `mach` crate if PR 6 didn't ship a Rust profiler; if no Rust profiler exists, document the gap and skip Rust-side memory enforcement — Agent A's Python orchestration enforces the budget when calling Rust via PyO3).

### `crates/cfr_core/src/subgame.rs`

Port of `poker_solver/subgame_refiner.py`. Functions: `refine_subgame(...) -> SubgameRefinementResult` (Rust struct). Reuses PR 6's postflop solver port for the actual solve. Range extraction + warm-start logic ported from Agent B's Python.

### `crates/cfr_core/src/preflop.rs`

Port of `poker_solver/preflop_solver.py`. Functions: `solve_hunl_preflop(...) -> PreflopSolveResult` (Rust struct). Orchestrates `build_blueprint` + per-subgame `refine_subgame`. Reuses PR 6's postflop tree + DCFR.

### `crates/cfr_core/src/lib.rs` PyO3 bindings

Add three new `#[pyfunction]` exports (additive; do not perturb existing bindings):

```rust
#[pyfunction]
fn solve_hunl_preflop_rust(
    py: Python,
    config_json: &str,  // serialized HUNLConfig from Python
    abstraction_path: &str,
    blueprint_iterations: usize,
    refine_iterations: usize,
    reach_threshold: f64,
    max_memory_gb: f64,
    seed: Option<u64>,
    on_progress: Option<PyObject>,  // PR 10b launch-readiness callback
                                    // signature: Callable[[int, float, MemoryReport], None]
                                    // invoke via Python::with_gil + .call1(...)
                                    // every `log_every` iterations
) -> PyResult<PyObject> {
    // ... call into preflop::solve_hunl_preflop ...
    // ... thread `on_progress` through to blueprint + refinement loops ...
    // ... convert result to PyDict / PyObject for Python consumption ...
}

#[pyfunction]
fn build_blueprint_rust(..., on_progress: Option<PyObject>) -> PyResult<PyObject> { ... }

#[pyfunction]
fn refine_subgame_rust(..., on_progress: Option<PyObject>) -> PyResult<PyObject> { ... }

// In #[pymodule]:
//   m.add_function(wrap_pyfunction!(solve_hunl_preflop_rust, m)?)?;
//   m.add_function(wrap_pyfunction!(build_blueprint_rust, m)?)?;
//   m.add_function(wrap_pyfunction!(refine_subgame_rust, m)?)?;
```

The exact serialization scheme (JSON vs PyDict vs PyO3 native classes) follows PR 6's precedent. If PR 6 used PyDict for `HUNLConfig`, do the same.

## Critical correctness items

### 1. Test the spec, not the implementation

If the spec says "bucket id in [0, 256)", your test asserts `0 <= bucket_id < 256`, NOT `bucket_id < t.bucket_counts[0]`. Encode the spec invariant directly.

If the spec says "reach probabilities sum to 1.0 at root", your test asserts `sum(...) == pytest.approx(1.0, abs=1e-6)`. Don't relax to `1e-3` because the impl produces `0.9999`.

### 2. Diff tolerance is `5e-3` / `1e-3` — NOT `1e-4`

Per consistency review I3: `5e-3` per-action probability + `1e-3 × base_pot` per-spot game value. The earlier draft of the spec cited `1e-4`; that was reconciled to match PR 6 / PR 7 / PR 8 cluster. Quote the tolerance in each diff test's docstring:

```python
def test_preflop_diff_blueprint_strategies_match():
    """Python ↔ Rust differential on the blueprint pass.

    Tolerance per spec §10.4 + consistency review I3:
      - 5e-3 per-action probability
      - 1e-3 × base_pot per-spot game value

    NOT 1e-4 (outlier from earlier draft; reconciled to PR 6/7/8 cluster).
    """
    ...
```

### 3. Boundary tests are LOCKED VERBATIM

`test_preflop_dispatch_pushfold_at_15bb`, `test_preflop_dispatch_solver_at_16bb`, `test_preflop_dispatch_error_at_251bb`. The spec §6 + §10.3 lock the names + assertions. Implement EXACTLY as spec'd.

### 4. Combined exploitability test is the headline acceptance for the v1 deliverable

`test_combined_exploitability_under_0_05_bb_per_hand` (spec §10.3 #5 + §7.4 + consistency review I5). If this fails on the spec's default iteration counts, the answer is to flag the finding for the orchestrator (the answer may be "bump iterations to 100k blueprint + 20k refine") — NOT to weaken the bar.

The CI relaxed variant (5k blueprint + 2k refine iter; assert < 0.5 BB/hand) is a smoke that detects gross regressions; the slow nightly variant is the actual deliverable verification.

### 5. Soft assertions clearly tagged

Tests marked "soft assertion" in the spec (the intuition gauntlet, the warm-start convergence test) wear a clear docstring marker:

```python
def test_preflop_4bet_range_polarized_at_100bb():
    """Soft assertion — failure prompts user review, not auto-fix.

    SB's 4-bet range should be polarized: 4bet_freq("KQs") <
    4bet_freq("A5s") * 0.5. Strict bound is approximate.
    """
    ...
```

### 6. Tiny configs for non-slow tests

Per existing PR 5 / PR 6 convention. `bucket_counts=(4, 2, 2)`, `blueprint_iterations=50-500`, `refine_iterations=25-200`, `H=10`. Total non-slow test wall-clock: < 5 minutes.

### 7. Slow tests marked + skipped in CI

```python
@pytest.mark.slow
def test_combined_exploitability_under_0_05_bb_per_hand():
    ...
```

CI runs `pytest -m "not slow"` by default; nightly runs `pytest`.

### 8. Determinism testing

For any function with a `seed` parameter, a test calls it twice with the same seed and asserts identical output. This is the load-bearing reproducibility check for `solve_hunl_preflop`, `build_blueprint`, `refine_subgame`, and their Rust counterparts.

### 9. Spec-ambiguity flagging

If you find that the spec is ambiguous about an expected behavior (e.g., "should `BlueprintResult.strategy` contain entries for unreached infosets?"), write the test for the version that seems most consistent with the spec's other language. Then, in your final report, list the ambiguity and how you resolved it. **Do NOT silently weaken the test to "pass either way."** The orchestrator adjudicates.

### 10. Existing tests pass unchanged

Your new test files are purely additive. Your Rust port adds new modules + additive `lib.rs` bindings. Run `pytest -x` after everything lands and confirm all PR 1 through PR 8 tests still pass + your new tests.

### 11. `cargo clippy --all-targets -- -D warnings` clean

The Rust port must pass clippy with the same strict flags PR 6 set up.

### 12. PyO3 binding round-trip

After `cargo build --release && maturin develop`, the new Rust functions must be importable from Python:

```python
from poker_solver._rust import (
    solve_hunl_preflop_rust,
    build_blueprint_rust,
    refine_subgame_rust,
)
```

If the import fails, the Rust port has a binding issue — fix before reporting done.

## Spec ambiguity protocol

If a test you wrote (correctly per spec) fails because the spec was ambiguous, **the spec is the source of truth** — flag the ambiguity for orchestrator review; do NOT silently tweak the test to match Agent A/B's implementation.

If your Rust port and Agent A/B's Python disagree (and Python is the ground truth per PLAN.md §3), document the divergence in your report; the orchestrator decides whether Python is wrong or Rust is wrong.

## License-aware sourcing

**You may port architecturally (not code-copy) from MIT/Apache sources:**
- `references/code/noambrown_poker_solver/` (**MIT**) — Brown's reference. Two-tier architecture inspiration.
- `references/code/slumbot2019/` (**MIT**) — Slumbot's HUNL architecture. Read-only.
- Pluribus paper (`references/papers/pluribus_brown_2019_science.pdf`) — algorithmic reference.

**You may NOT copy from AGPL sources:**
- `references/code/postflop-solver/` — **AGPL v3**. No code copy.
- `references/code/TexasSolver/` — **AGPL v3**. No code copy.

**You may NOT extrapolate from training data.** Ground every non-trivial pattern in a local reference or the PR 9 spec.

If you copy a non-trivial code snippet (>~5 LOC) from an MIT source (e.g., Slumbot's tree builder), add an attribution comment.

## Quality bar

- **Rust:** `cargo clippy --all-targets -- -D warnings` clean.
- **Rust:** `cargo test --release` passes on all new modules.
- **Python tests:** `ruff check tests/test_hunl_preflop_*.py tests/test_preflop_diff.py tests/fixtures/hunl_preflop_fixtures.py` clean.
- **Python tests:** `black --check` on the same set clean.
- **Tests use the public API only.** Imports: `from poker_solver import ...` or `from poker_solver._rust import ...`. Do NOT import from internal modules.
- **Tests are self-contained.** No reading from `tests/data/` (unless you create the data inline); no network access; no requiring an abstraction artifact to be pre-built on the user's filesystem (use the tiny synthetic abstraction fixture).
- **No non-slow test exceeds 5 seconds wall-clock.** Slow tests bear the `@pytest.mark.slow` marker.
- **All existing tests must still pass.** Your work is purely additive; ensure no test ID collision.
- **Code size budget:** Rust ~1300 LOC total (per spec §9: 600 preflop + 400 blueprint + 300 subgame). Python tests ~600 LOC total (~150 per test file).

## Reference-first rule

Before any technical claim, citation, or formula, check the local references. Never extrapolate from training data when a local authoritative source exists.

For the Rust port pattern: cite PR 6's spec or PR 6's Rust modules as the precedent.
For the diff-test tolerance: cite consistency review I3.
For the blueprint + refinement algorithm: cite Pluribus paper pages 2–4 per PR 9 §16.

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Lint + format Python tests
ruff check tests/test_hunl_preflop_blueprint.py tests/test_hunl_preflop_refinement.py tests/test_hunl_preflop_integration.py tests/test_preflop_diff.py tests/fixtures/hunl_preflop_fixtures.py
black --check tests/test_hunl_preflop_blueprint.py tests/test_hunl_preflop_refinement.py tests/test_hunl_preflop_integration.py tests/test_preflop_diff.py tests/fixtures/hunl_preflop_fixtures.py

# 2. Rust clippy + tests
cargo clippy --all-targets -- -D warnings
cargo test --release --manifest-path crates/cfr_core/Cargo.toml

# 3. Rebuild the Python ↔ Rust bridge (PyO3)
maturin develop --release

# 4. Confirm Rust bindings importable
python -c "
from poker_solver._rust import (
    solve_hunl_preflop_rust,
    build_blueprint_rust,
    refine_subgame_rust,
)
print('Rust bindings importable')
"

# 5. Collect Python tests (must collect without import errors)
pytest --collect-only tests/test_hunl_preflop_blueprint.py tests/test_hunl_preflop_refinement.py tests/test_hunl_preflop_integration.py tests/test_preflop_diff.py 2>&1 | tail -20
# Expected: ~20 tests collected (6 + 5 + 5 + 4 per spec §10, plus the additional
# canonical-chance-weights test and the two intuition-gauntlet additions = ~22).

# 6. Run non-slow tests (assumes Agents A + B have landed)
pytest -x -m "not slow" tests/test_hunl_preflop_blueprint.py tests/test_hunl_preflop_refinement.py tests/test_hunl_preflop_integration.py tests/test_preflop_diff.py 2>&1 | tail -30

# 7. Full test suite (your new tests + all PR 1 through PR 8 existing tests)
pytest -x -m "not slow" 2>&1 | tail -20
# Expected: all existing tests + your new tests pass.

# 8. (Optional, nightly) Run slow tests
# pytest tests/test_hunl_preflop_integration.py 2>&1 | tail -30
```

If any of the above fails, classify the failure:
- (a) typo in YOUR test code → fix the typo.
- (b) Rust port bug (Python passes, Rust fails diff) → diagnose, fix Rust.
- (c) spec ambiguity → leave the test, document in report.
- (d) genuine bug in Agent A or Agent B → leave the test, document in report.

Do NOT silently weaken tests to pass.

## Report back format

When done, write a concise report (≤300 words) covering:

1. Rust files created + LOC; Python test files created + test counts + LOC; modifications to `lib.rs` (line-delta).
2. Tests that PASS against Agents A+B's implementations + your Rust port (count).
3. Tests that FAIL — classified as: (a) test bug (you fixed it), (b) Rust port bug (you fixed it), (c) spec ambiguity (flag for human), (d) impl bug in Agent A or B (flag for human).
4. Any spec ambiguity you couldn't resolve.
5. Tests you added beyond the spec §10 list (justify each — e.g., the canonical-chance-weights test from §13 risk row 6).
6. Tests from the spec §10 list you couldn't write (justify each).
7. Diff-tolerance findings: do the Python and Rust outputs actually agree within `5e-3 / 1e-3`? If not, what's the divergence and what's the diagnosis?
8. License attributions added.
9. Open questions for human review.
10. Confirmation that the Rust port threads `on_progress` through all three entrypoints (`solve_hunl_preflop_rust`, `build_blueprint_rust`, `refine_subgame_rust`). Cite the Rust file:line where the callback is invoked from Rust via `Python::with_gil` (or equivalent pattern). PR 10b consumer expects this; missing plumbing breaks UI dispatch.
