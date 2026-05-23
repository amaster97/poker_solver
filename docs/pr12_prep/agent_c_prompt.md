# PR 12 Agent C — tests + cross-validation harness + UI badge integration

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 12 Agent C.**
**Your scope:** the 3p solve test suite (`tests/test_3p_solve.py`, `tests/test_3p_diff.py`), shared fixtures (`tests/fixtures/multiway_fixtures.py`), the MonkerSolver cross-validation harness, and the UI surfaces that display 3-handed results — the **mandatory "≈ approximate equilibrium" badge** (cannot be disabled), the 3-up range matrix display, the `num_players` toggle in the run panel, the library-row badge.
**Your contract:** every UI surface that displays a 3-handed result MUST render the "≈ approximate equilibrium" badge with the locked tooltip text. Test the badge is present in render output. No "Nash" / "GTO" / bare "exploitability" strings anywhere in UI labels or test docstrings.
**Your success criteria:** ruff/black clean; tests pass against Agent A's `hunl.py` and Agent B's `multiway_solver.py`; ~30 new tests (15 core + 10 solve + 3 diff + ~3 intuition gauntlet + ~3 stability); MonkerSolver harness skips cleanly when `tests/fixtures/monker/` is absent; UI badge mandatorily renders for any `result.num_players >= 3`.
**File ownership:** you own `tests/test_3p_solve.py`, `tests/test_3p_diff.py`, `tests/fixtures/multiway_fixtures.py`, `ui/views/range_matrix.py` (badge + 3-up matrix changes), `ui/views/run_panel.py` (num_players toggle + 3-range input), `ui/views/library_browser.py` (row badge), and `poker_solver/cli.py` (--num-players flag).

---

## Theoretical concern that frames everything below

Multi-player CFR has **no Nash convergence proof**. This is the load-bearing fact for every UI label, test description, badge tooltip, and CLI banner you produce.

Concretely:
1. **No polynomial Nash algorithm exists for n>=3 games** (Daskalakis-Goldberg-Papadimitriou 2009; Pluribus paper p. 2 refs 13–14).
2. **Joint independent Nash play is not itself Nash** in n>=3 (Pluribus's Lemonade Stand Game, p. 2).
3. **Nash equilibria are not unique** in n>=3, and **playing Nash does not guarantee not-losing-in-expectation** — exclusively a 2p0s property (Pluribus p. 1).
4. **CFR may cycle, depend on initialization, or fail to converge** in n-player games. Gibson 2013 proves only **IDSD elimination** in n-player non-zero-sum settings — much weaker than Nash. Pluribus (Brown & Sandholm 2019, *Science*) explicitly calls itself a "near-Nash blueprint."

The "≈ approximate equilibrium" badge you implement is **not optional decoration** — it is the central UX commitment of PR 12. Per §9 #10 of spec: **no CLI / config flag to suppress the badge in CLI output or UI display.** Hard-coded.

Your tests for UI must verify:
- The badge renders whenever `result.num_players >= 3`.
- The tooltip text matches the locked spec text verbatim.
- The badge cannot be removed by any config option or feature flag.
- No string in UI labels for 3-handed paths reads "Nash", "GTO", "optimal", or bare "exploitability".

## Strict file ownership

**You own (write + create freely):**
- `/Users/ashen/Desktop/poker_solver/tests/test_3p_solve.py` (new; ~10 tests + 3 intuition gauntlet + 3 stability ≈ 16 tests)
- `/Users/ashen/Desktop/poker_solver/tests/test_3p_diff.py` (new; ~3 tests)
- `/Users/ashen/Desktop/poker_solver/tests/fixtures/multiway_fixtures.py` (new; fixture builders)
- `/Users/ashen/Desktop/poker_solver/ui/views/range_matrix.py` (modify; add badge + 3-up matrix display)
- `/Users/ashen/Desktop/poker_solver/ui/views/run_panel.py` (modify; num_players toggle + 3-range input + per-pair BR display)
- `/Users/ashen/Desktop/poker_solver/ui/views/library_browser.py` (modify; row badge for `num_players == 3`)
- `/Users/ashen/Desktop/poker_solver/poker_solver/cli.py` (modify; add `--num-players` flag and route to `solve_3p_postflop`)

**You must NOT touch:**
- `poker_solver/hunl.py` — Agent A (game state)
- `poker_solver/action_abstraction.py` — Agent A
- `tests/test_3p_core.py` — Agent A (game-state invariant tests)
- `poker_solver/multiway_solver.py` — Agent B (3p orchestration)
- `crates/cfr_core/src/multiway.rs` — Agent B (Rust port)
- `poker_solver/solver.py` — Agent B (routing branch)
- `poker_solver/__init__.py` — Agent B (re-exports)

If a UI change requires deeper refactoring of PR 10's `RangeWithFreqs` or `cell_strategy_summary`, **stop and flag it**. The spec (§10.6) verifies these are designed to be range-count-agnostic. If they aren't, scope as PR 12.5; do not silently refactor.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr12_prep/pr12_spec.md`. Internalize:
   - §1 (goal; the "≈ approximate" framing is load-bearing)
   - §3 (theoretical honesty — every UI label and test docstring lives in this register)
   - §6.3 (the UI badge — locked, mandatory, unsuppressible)
   - §7 (validation strategy; you implement most of it)
   - §7.3 (per-pair BR math; your tests verify Agent B's implementation)
   - §7.4 (stability diagnostic; your tests verify reruns produce consistent reports)
   - §7.5 (MonkerSolver cross-validation; opt-in harness)
   - §7.6 (intuition gauntlet)
   - §8.3 (your agent deliverables)
   - §9 #1, #2, #3, #4, #6, #8, #10 (your critical correctness coverage — side-pots, showdown, BR joint-strategy, no-Nash-claim, regression, pruning, badge unsuppressibility)
   - §15 (post-implementation audit focus areas)
2. **Agent A's generalized game state** (your fixture and test target):
   - `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` (post-Agent A) — confirm field signatures + N=3 path; build fixtures consuming it.
3. **Agent B's solver and types** (your test target):
   - `/Users/ashen/Desktop/poker_solver/poker_solver/multiway_solver.py` (post-Agent B) — your tests instantiate and verify `MultiwaySolveResult`, `StabilityReport`, `MultiwayBestResponse`, `solve_3p_postflop`, `run_stability_diagnostic`.
4. **The HU UI surfaces you extend** (your starting point):
   - `/Users/ashen/Desktop/poker_solver/ui/views/range_matrix.py` — read fully. Internalize how it currently renders one or two ranges and where you add the third panel + badge.
   - `/Users/ashen/Desktop/poker_solver/ui/views/run_panel.py` — read fully. Internalize the existing range-input UI; add a third panel conditionally on `num_players == 3`.
   - `/Users/ashen/Desktop/poker_solver/ui/views/library_browser.py` — read fully. The row-level badge for 3p spots.
5. **PR 4 abstraction artifact pattern** (for fixtures):
   - `/Users/ashen/Desktop/poker_solver/poker_solver/abstraction/__init__.py` — `AbstractionTables`, `lookup_bucket()`.
6. **Pluribus paper:** `references/papers/pluribus_brown_2019_science.pdf`. p. 2 for the "near-Nash blueprint" framing; p. 3 for Linear CFR recipe.

## Default decisions LOCKED (do not deviate)

- **The "≈ approximate equilibrium" badge** is mandatory on ALL output surfaces (CLI, UI, library) whenever `num_players >= 3`. Cannot be disabled via any config flag, env var, or CLI option. Locked per §6.3 + §9 #10 of spec.
- **The badge tooltip text is locked verbatim** (§6.3):
  > "Three-handed solves use Linear CFR on a heavily-abstracted tree. Multi-player CFR has no Nash convergence proof (Brown & Sandholm 2019, Pluribus); the strategy shown is one approximate fixed point among potentially many. Best-response gaps below are per-pair upper bounds, not Nash exploitability."
- **CLI banner format is locked** (§6.3): a 3-line text banner with `===` borders containing the approximate-equilibrium notice.
- **Three per-pair best-response gaps**, not one "exploitability" number (§12 #2). Display as `BR_gap_P0`, `BR_gap_P1`, `BR_gap_P2` with the "≈" prefix. Never sum them and never call any of them "exploitability".
- **Stability diagnostic: 3 seeds (0, 1, 2)**. Soft assertion `pairwise_max < 0.05`; failure → warning + extra badge line, not auto-fail.
- **MonkerSolver harness is opt-in.** Test decorated `@pytest.mark.skipif(not Path('tests/fixtures/monker/').exists())`. No bundled data. Document fixture format clearly.
- **Card abstraction tier for 3-handed default: 128 / 64 / 32** — one tier tighter than HU. Reuse `precompute-abstraction --bucket-counts 128,64,32` from PR 4.
- **No 3-handed push/fold table** (§12 #1). Out of v1 scope.
- **CLI flag is `--num-players 3`** with three range arguments (§12 #13). Subcommand `solve-3p` rejected.
- **Single-PR for PR 12** (not split into PR 12 + PR 12.5) is the default per §12 #4. If your work blocks on Agent A/B incomplete deliverables, flag and pause.

## Public API contract (what you consume from Agent A + Agent B)

You write tests + UI that consume these signatures (interface lock from Agent A/B):

### From Agent A — `poker_solver/hunl.py`

```python
HUNLConfig(
    num_players: int = 2,
    starting_stacks: tuple[int, ...] = (10_000, 10_000),
    initial_contributions: tuple[int, ...] = (0, 0),
    # ... existing fields preserved
)

HUNLState(
    contributions: tuple[int, ...],
    stacks: tuple[int, ...],
    folded: tuple[bool, ...],
    all_in: tuple[bool, ...],
    hole_cards: tuple[tuple[Card, Card], ...] | tuple[()],
    cur_player: int,
    # ... existing fields preserved
)

# HUNLPoker.utility(state) returns tuple[float, ...] of length num_players, sums to ~0.
```

### From Agent B — `poker_solver/multiway_solver.py`

```python
MultiwaySolveResult(
    strategy: dict[bytes, list[float]],
    game_value: tuple[float, ...],
    br_gap: tuple[float, ...],
    num_players: int,
    iterations_run: int,
    convergence_stability: float | None,
    is_approximate: bool = True,  # always True for num_players >= 3
)

StabilityReport(
    seeds: tuple[int, ...],
    pairwise_max: float,
    pairwise_mean: float,
    l1_per_infoset: dict[bytes, float],
    n_infosets: int,
)

solve_3p_postflop(config, abstraction, iterations, seed=0, lcfr_cutoff=None, ...) -> MultiwaySolveResult

class MultiwayBestResponse:
    def __init__(self, game, strategy): ...
    def compute_br_gap(self, player_index: int) -> float: ...
    def compute_all_br_gaps(self) -> tuple[float, ...]: ...

run_stability_diagnostic(config, abstraction, iterations, seeds=(0,1,2), **kwargs) -> StabilityReport
```

## Critical correctness items

### 1. The UI badge is mandatory and unsuppressible (§6.3, §9 #10)

**Component to implement in `ui/views/range_matrix.py`:**

```python
# Pseudocode — adapt to the Quasar component style of the existing range matrix UI.
def render_approximate_badge() -> Component:
    """Renders the mandatory ≈ approximate equilibrium badge for 3-handed results.

    Cannot be disabled. Per spec §6.3 + §9 #10.
    """
    return QBadge(
        color="warning",  # red/yellow per spec
        label="≈ approximate equilibrium\nmulti-player; not Nash",
        tooltip=(
            "Three-handed solves use Linear CFR on a heavily-abstracted tree. "
            "Multi-player CFR has no Nash convergence proof (Brown & Sandholm 2019, "
            "Pluribus); the strategy shown is one approximate fixed point among "
            "potentially many. Best-response gaps below are per-pair upper bounds, "
            "not Nash exploitability."
        ),
    )


def render_range_matrix(result: MultiwaySolveResult | SolveResult, ...) -> Component:
    if hasattr(result, 'num_players') and result.num_players >= 3:
        # Render the badge ABOVE the matrices.
        # Render three side-by-side range matrices (one per player).
        ...
    else:
        # Existing HU rendering unchanged.
        ...
```

**Required test cases (in `tests/test_3p_solve.py` or a new `tests/test_ui_3p.py`):**
- `test_badge_rendered_for_3p_result`: instantiate a `MultiwaySolveResult` with `num_players=3`; render via the range matrix view; assert the badge component is in the render tree with the exact label and tooltip text.
- `test_badge_not_rendered_for_hu_result`: instantiate a HU `SolveResult` (or `MultiwaySolveResult` with `num_players=2`); render; assert no approximate-equilibrium badge.
- `test_badge_tooltip_text_matches_spec`: assert the tooltip text matches the locked spec verbatim (string equality).
- `test_badge_cannot_be_disabled_via_config`: even if `result.is_approximate = False` (which it can't be set to externally, but if someone mocked it), the badge still renders whenever `num_players >= 3`. Hardcode the badge trigger on `num_players >= 3`, not on `is_approximate`. (Belt and braces.)

### 2. CLI banner is mandatory and unsuppressible (§6.3, §9 #10)

In `poker_solver/cli.py`, when `--num-players 3` is passed, the solve output begins with:

```
=========================================================
≈ approximate equilibrium (multi-player; not Nash)
Multi-player CFR has no convergence proof; the strategy
shown is one fixed point among potentially many.
=========================================================
```

Required test:
- `test_cli_banner_in_3p_stdout`: subprocess-invoke the CLI with `--num-players 3 --board ... --ranges A,B,C --iterations 1` (just enough to produce output); assert the banner string is in stdout. NOT optional. NOT configurable.
- `test_cli_banner_absent_for_hu`: invoke without `--num-players` (default 2); banner absent.

### 3. No "Nash" / "GTO" / bare "exploitability" in 3p UI labels or test docstrings (§9 #4)

String-literal audit gate (per spec §9 #4):

```bash
grep -ri 'exploitability\|nash\|GTO' \
  poker_solver/cli.py \
  ui/views/range_matrix.py \
  ui/views/run_panel.py \
  ui/views/library_browser.py \
  tests/test_3p_solve.py \
  tests/test_3p_diff.py \
  | grep -v 'best-response\|approximate\|≈\|near-Nash\|# '
```

Expected: zero hits, or only commented references to historical papers.

In your code:
- Display field: "≈ best-response EV upper bound (multi-player; NOT Nash exploitability)" — never "exploitability".
- Test docstrings: describe what's being tested ("BR gap is non-negative", "stability diagnostic converges across seeds") — never "Nash convergence".

### 4. Three per-pair best-response gaps in UI (§12 #2)

`ui/views/run_panel.py` displays:

```
≈ Best-response EV upper bounds (per pair; NOT Nash exploitability):
  P0 (SB):  X.XX mBB/hand
  P1 (BB):  Y.YY mBB/hand
  P2 (BTN): Z.ZZ mBB/hand
```

Required test:
- `test_three_br_gaps_displayed`: render run panel with a `MultiwaySolveResult` having `br_gap=(0.5, 0.7, 0.3)`; assert all three values appear; assert no "max" or "average" or "exploitability" summary is shown.

### 5. Stability diagnostic warning in UI (§7.4, §6.3 "extra badge line")

When `result.convergence_stability > 0.05`, the badge gets an extra line:

```
⚠ stability degraded: seeds 0/1/2 differ in L1 norm by up to X.XX% per infoset.
```

Required test:
- `test_stability_warning_above_threshold`: render a `MultiwaySolveResult` with `convergence_stability=0.08`; assert warning line is present.
- `test_no_stability_warning_below_threshold`: `convergence_stability=0.02`; assert no warning line.

### 6. 3-up range matrix display (§6.3)

When `result.num_players == 3`, render three side-by-side mini-matrices (one per player) instead of one large matrix. PR 10's `RangeWithFreqs` and `cell_strategy_summary` are designed range-count-agnostic per §10.6.

Required test:
- `test_3up_matrix_for_3p_result`: render; assert three matrix components present in the render tree.
- `test_single_matrix_for_hu_result`: render HU result; assert single matrix.

### 7. Library row badge (§6.2)

`ui/views/library_browser.py` displays a small "3-handed (approximate)" badge on rows where `spot_json.config.num_players == 3`.

Required test:
- `test_library_row_3p_badge`: row with `num_players=3` → badge present.
- `test_library_row_hu_no_badge`: row with `num_players=2` → no 3p badge.

### 8. CLI flag wiring (`--num-players`)

In `poker_solver/cli.py`:

```python
parser.add_argument(
    "--num-players",
    type=int,
    default=2,
    choices=[2, 3],
    help="Number of players. Default 2 (HUNL). Use 3 for 3-handed postflop. "
         "3-handed results are approximate equilibria (not Nash); see spec.",
)
parser.add_argument(
    "--ranges",
    type=str,
    required=True,
    help="Comma-separated range strings; one per player. For --num-players 3: "
         "three ranges separated by ' / ' (e.g., 'AA,KK / AKs+ / 76s+').",
)
```

If `--num-players 3`, parse `--ranges` as 3 range strings; instantiate `HUNLConfig(num_players=3, starting_stacks=(10_000,)*3, ...)`; call `solve(game)` which routes to `solve_3p_postflop`.

Required test (subprocess-based or argparse-direct):
- `test_cli_3p_invocation`: `--num-players 3 --ranges "A / B / C"` parses correctly; instantiates HUNLConfig with num_players=3.
- `test_cli_4p_rejected`: `--num-players 4` rejected by argparse (`choices=[2,3]`).

### 9. Stability diagnostic determinism (§15 audit focus)

The diagnostic itself must be deterministic. Test:
- `test_stability_diagnostic_deterministic`: call `run_stability_diagnostic(config, abstraction, iterations=100, seeds=(0,1,2))` twice; assert both `StabilityReport`s have identical `pairwise_max`, `pairwise_mean`, and `l1_per_infoset` (within machine epsilon).

### 10. Differential test (Python ↔ Rust) (§6.1)

`tests/test_3p_diff.py` mirrors `tests/test_dcfr_diff.py` from PR 6:

```python
def test_3p_diff_river_subgame():
    """Python solve_3p_postflop and Rust solve_3p_postflop produce strategies
    with L1 < 1e-6 per infoset after 500 iterations on shared inputs.

    Tiny 3p river subgame fixture (~few thousand infosets).
    """
    fixture = build_3p_river_fixture()  # from multiway_fixtures.py
    py_result = solve_3p_postflop(fixture.config, fixture.abstraction, iterations=500, seed=42)
    rust_result = rust_solve_3p_postflop(fixture.config, fixture.abstraction, iterations=500, seed=42)
    for infoset_key, py_probs in py_result.strategy.items():
        rust_probs = rust_result.strategy[infoset_key]
        l1 = sum(abs(p - r) for p, r in zip(py_probs, rust_probs))
        assert l1 < 1e-6, f"L1 drift {l1} for infoset {infoset_key.hex()}"
```

### 11. Convergence smoke test (§7.2 #1, #2, #4)

```python
def test_3p_smoke_river_only():
    """Smoke test: solve a tiny 3p river-only subgame; assert basic invariants.

    NOT a Nash convergence test (multi-player CFR has no Nash convergence proof).
    Asserts:
    - All strategies sum to 1.0 per infoset.
    - Sum of per-player game values ≈ 0 (zero-sum).
    - Per-pair BR gaps are non-negative.
    """
    fixture = build_3p_river_fixture()
    result = solve_3p_postflop(fixture.config, fixture.abstraction, iterations=200, seed=0)
    # Strategy validity
    for key, probs in result.strategy.items():
        assert abs(sum(probs) - 1.0) < 1e-6
        assert all(0 <= p <= 1 for p in probs)
    # Zero-sum check
    assert abs(sum(result.game_value)) < 0.001 * fixture.pot_size
    # BR gaps non-negative
    assert all(g >= 0 for g in result.br_gap)
```

### 12. IDSD elimination test (§7.2 #3, Gibson 2013)

```python
def test_3p_iteratively_strict_dominated_action_vanishes():
    """Per Gibson 2013: CFR eliminates iteratively strictly dominated actions
    in n-player non-zero-sum games. Construct a 3p toy subgame where one action
    is strictly dominated for one player; solve; assert that action's
    frequency converges to ≈ 0.

    This is the STRONGEST theoretical property of multi-player CFR we have.
    Weaker than Nash convergence (which is not guaranteed).
    """
    fixture = build_3p_dominated_action_fixture()
    result = solve_3p_postflop(fixture.config, fixture.abstraction, iterations=500, seed=0)
    # The dominated action should have frequency < epsilon at the relevant infoset.
    dominated_freq = result.strategy[fixture.dominated_infoset_key][fixture.dominated_action_idx]
    assert dominated_freq < 0.01, f"dominated action freq {dominated_freq} not vanishing"
```

### 13. Intuition gauntlet tests (§7.6) — soft assertions

Mark these `@pytest.mark.intuition` (a custom marker) so they can be skipped in CI but run on demand. Document each as a "soft assertion" — failure prompts user review, not auto-fail.

```python
@pytest.mark.intuition
def test_multiway_bb_3bet_defense_narrower_than_hu():
    """Soft assertion: BB's defending range vs UTG 3-bet should be narrower
    in 3-handed than in HU (squeeze pressure from cold-caller dynamic).

    Spec §7.6. Failure prompts user review; not auto-fail.
    """
    ...
```

Three tests per §7.6: BB 3-bet defense narrower, multi-way check-down freq higher, IP bluff freq lower.

### 14. MonkerSolver cross-validation harness (§7.5) — opt-in

```python
@pytest.mark.skipif(
    not Path("tests/fixtures/monker/").exists(),
    reason="MonkerSolver fixture data not present (paid Windows software; user-supplied)."
)
def test_against_monker_data():
    """Cross-validate our 3p strategy against MonkerSolver output (if user has
    Monker data in tests/fixtures/monker/).

    For each Monker fixture file:
    - Parse the spot description.
    - Solve via our solver.
    - Assert per-infoset L1 < 0.10 between our strategy and Monker's.

    L1 < 0.10 is a LOOSE threshold per §7.5 — Monker's abstraction and ours
    differ, so the strategies are expected to differ within this margin.

    No bundled Monker data (license). User exports manually.
    """
    monker_files = sorted(Path("tests/fixtures/monker/").glob("*.json"))
    for f in monker_files:
        ...
```

Document fixture format clearly in a top-of-file docstring or a sibling `tests/fixtures/monker/README.md`:

```
tests/fixtures/monker/
├── 3p_flop_As7c2d.json   # one file per Monker-exported spot
└── 3p_flop_Kh9s7d.json

# Schema for each JSON file:
{
  "board": ["As", "7c", "2d"],
  "stacks_bb": [100, 100, 100],
  "ranges": ["AA-22, AKs-A2s, ...", "...", "..."],
  "monker_strategy": {
    "<infoset_key_hex>": {"check": 0.7, "bet33": 0.2, "bet75": 0.1},
    ...
  }
}
```

### 15. No code copying from AGPL sources

`references/code/postflop-solver/` and `references/code/TexasSolver/` are AGPL — read-only inspiration only. Your fixture builders and test utilities must be original code.

## Fixture catalog (in `tests/fixtures/multiway_fixtures.py`)

Provide fixture builders for:

- `build_3p_river_fixture()`: deterministic 3p river-only subgame, no chance nodes, ~1k infosets. Used in smoke tests + differential test + stability tests.
- `build_3p_flop_fixture(tight=True)`: 3p flop subgame with tight abstraction (default 128/64/32), ~10^5 infosets. Used for slower convergence tests. Mark consumers `@pytest.mark.slow`.
- `build_3p_turn_fixture()`: 3p turn subgame, ~few × 10^4 infosets. Mark `@pytest.mark.slow`.
- `build_3p_dominated_action_fixture()`: synthetic 3p tree with a known strictly-dominated action for P0. Used for IDSD test.
- `build_3p_joint_br_fixture()`: synthetic 3p tree where BR-against-joint differs from BR-against-either-individual. Used for §9 #3 of spec.

Each fixture returns a dataclass with `config`, `abstraction`, `pot_size`, plus any test-specific metadata.

## Quality bar

- **ruff clean:** `ruff check tests/test_3p_solve.py tests/test_3p_diff.py tests/fixtures/multiway_fixtures.py ui/views/range_matrix.py ui/views/run_panel.py ui/views/library_browser.py poker_solver/cli.py`.
- **black clean:** same files.
- **mypy strict-clean on new UI code:** `mypy --strict ui/views/range_matrix.py ui/views/run_panel.py ui/views/library_browser.py` (test files best-effort).
- **All new tests pass against Agent A + Agent B's deliverables.** Run after both have landed.
- **All existing tests pass.** Your UI changes must not break PR 10's existing HU UI tests.
- **String-literal audit gate** passes (no bare "Nash" / "GTO" / "exploitability" in your UI labels or test docstrings).
- **Code size budget:** ~400 LOC `test_3p_solve.py`, ~100 LOC `test_3p_diff.py`, ~200 LOC `multiway_fixtures.py`, ~100 LOC delta on each UI view file, ~50 LOC delta on `cli.py`.

## Reference-first rule

Before any technical claim, citation, or formula, check the local references. Never extrapolate from training data when a local authoritative source exists.

- For "approximate equilibrium" framing: cite Pluribus paper p. 1–2.
- For "Linear CFR + 95%-pruning recipe": Pluribus paper p. 3.
- For "IDSD elimination is the strongest theoretical result": Gibson 2013 (`references/papers/gibson_2013_regret_minimization.pdf`).
- For "joint Nash isn't Nash" in test docstrings: Pluribus paper p. 2, Lemonade Stand Game.
- For MonkerSolver fixture format: user-supplied; document the JSON schema in `tests/fixtures/monker/README.md`.

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Lint + format
ruff check tests/test_3p_solve.py tests/test_3p_diff.py tests/fixtures/multiway_fixtures.py \
  ui/views/range_matrix.py ui/views/run_panel.py ui/views/library_browser.py poker_solver/cli.py
black --check tests/test_3p_solve.py tests/test_3p_diff.py tests/fixtures/multiway_fixtures.py \
  ui/views/range_matrix.py ui/views/run_panel.py ui/views/library_browser.py poker_solver/cli.py

# 2. Type-check UI
mypy --strict ui/views/range_matrix.py ui/views/run_panel.py ui/views/library_browser.py

# 3. String-literal audit (HARD GATE)
grep -ri 'exploitability\|Nash\|GTO' \
  ui/views/range_matrix.py ui/views/run_panel.py ui/views/library_browser.py \
  poker_solver/cli.py \
  tests/test_3p_solve.py tests/test_3p_diff.py \
  tests/fixtures/multiway_fixtures.py \
  | grep -v 'best-response\|approximate\|≈\|near-Nash\|# ' \
  && echo "FAIL: bare claims found" || echo "PASS: no bare claims"

# 4. Smoke test fixtures
python -c "
from tests.fixtures.multiway_fixtures import build_3p_river_fixture
fixture = build_3p_river_fixture()
assert fixture.config.num_players == 3
assert len(fixture.config.starting_stacks) == 3
print('fixture smoke OK')
"

# 5. Smoke test badge rendering (mock data)
python -c "
from poker_solver.multiway_solver import MultiwaySolveResult
from ui.views.range_matrix import render_approximate_badge
# (Adjust to actual rendering API; this is illustrative.)
badge = render_approximate_badge()
print('badge renders without error')
"

# 6. CLI banner smoke (subprocess; tiny iterations to keep wallclock short)
python -m poker_solver.cli solve --num-players 3 --board 'As 7c 2d Kh 5s' \
  --ranges 'AA / KK / QQ' --stacks '100,100,100' --iterations 5 2>&1 | head -20

# Confirm banner appears.

# 7. Run your test files
pytest tests/test_3p_solve.py tests/test_3p_diff.py -v 2>&1 | tail -40

# 8. Full test suite passes (regression gate)
pytest -x 2>&1 | tail -30

# 9. MonkerSolver harness skips cleanly when fixture dir is absent
pytest tests/test_3p_solve.py::test_against_monker_data -v 2>&1 | head -5
# Should report SKIPPED with reason "MonkerSolver fixture data not present".
```

If any of the above fails, fix the issue before reporting done. If a smoke test reveals a spec ambiguity or a contract mismatch with Agent A/B's deliverables, **stop and flag it** — do not silently work around it.

## Report back format

When done, write a concise report (<=300 words) covering:

1. Files created/modified with LOC counts.
2. Test catalog: which tests in `test_3p_solve.py` + `test_3p_diff.py` cover which critical-correctness items (cross-reference §9 of spec).
3. UI badge: confirm it renders in `range_matrix.py`, `library_browser.py`, and CLI; paste the tooltip text used (assert verbatim match with spec §6.3).
4. String-literal audit result (paste grep output; should be clean).
5. MonkerSolver harness: confirm it skips cleanly without bundled data; reference the fixture-format README path.
6. Intuition gauntlet: list which 3 soft assertions you implemented.
7. Verification command output (paste tails).
8. Any spec amendment or contract drift flagged.
9. Any open question for human review (e.g., a UI refactor that should be scoped to PR 12.5 per §10.6).
10. License attributions you added (if any).

**Hard gates before reporting done:**
- All new tests pass against Agent A + Agent B's deliverables.
- All existing tests pass unchanged.
- String-literal audit returns no bare claims.
- Badge renders for `num_players >= 3` and cannot be disabled.
- CLI banner appears in stdout when `--num-players 3`.
- MonkerSolver harness skips gracefully when fixture dir absent.
- Tooltip text matches spec §6.3 verbatim.
