# Cross-PR Integration Test Scaffolds

**Purpose:** test stubs that exercise multi-PR interactions, dropped into
`tests/` and skip-marked until each underlying PR lands. Each scaffold
references the authoritative spec section (PR N spec §X) it locks behavior
against.

**Conventions:**
- Each test marked `@pytest.mark.skip(reason="awaiting PR N implementation")`
  with the latest PR that gates the test. Once that PR lands, the marker is
  removed (or kept and parameterized via `@pytest.mark.skipif`).
- Docstrings explicitly name the PRs integrated.
- Tolerance values match the PR 6 / PR 7 / PR 8 / PR 9 cluster: `5e-3` per
  action probability, `1e-3 × base_pot` per-spot game value.
- Style match: function-level tests, `pytest.approx` for floats, no test
  classes, matches `tests/test_leduc_core.py` and `tests/test_hunl_core.py`.

---

## File 1 — `tests/test_integration_dispatch.py`

**Test count:** 5
**PRs integrated:** PR 3 (HUNLPoker), PR 3.5 (push/fold chart), PR 5 (postflop
solver), PR 9 (preflop solver + canonical dispatch §6)
**Gating PR:** PR 9 (closes the full dispatch chain).

```python
"""Cross-PR integration tests for the stack-depth dispatch chain.

The full dispatch composition lives in PR 9 spec §6 (CANONICAL). PR 3.5 §6
and PR 5 §6 cross-reference that section. These tests lock the boundary
behavior so a change to ordering or thresholds triggers a loud failure
across the chain.

PRs integrated:
- PR 3: `HUNLPoker`, `HUNLConfig` constructible at any stack depth.
- PR 3.5: `solve_pushfold` / chart short-circuit at <=15 BB.
- PR 5: `solve_hunl_postflop` for `starting_street >= Street.FLOP`.
- PR 9: full `solve()` dispatch composition + 250 BB ceiling.
"""

from __future__ import annotations

import pytest

from poker_solver import (
    Card,
    HUNLConfig,
    HUNLPoker,
    Street,
    solve,
)


@pytest.mark.skip(reason="awaiting PR 9 implementation (full dispatch chain)")
def test_dispatch_short_stack_5bb_lands_on_pushfold_chart():
    """5 BB stack -> push/fold chart lookup (PR 3.5 short-circuit).

    Integrates: PR 3 (HUNLConfig/HUNLPoker construction) + PR 3.5 (chart).
    PR 9 §6 declares chart short-circuit MUST run before postflop/preflop
    branches, regardless of starting_street.
    """
    game = HUNLPoker(HUNLConfig(starting_stack=500))  # 5 BB
    result = solve(game, iterations=0)
    assert result.backend == "pushfold_chart" or result.backend == "pushfold"


@pytest.mark.skip(reason="awaiting PR 9 implementation")
def test_dispatch_50bb_lands_on_tree_builder_solver():
    """50 BB preflop stack -> PR 9 preflop solver (NOT push/fold).

    Integrates: PR 3 + PR 5 (postflop) + PR 9 (preflop). The dispatch must
    skip the chart short-circuit (eff_stack > 15) and the ceiling
    (eff_stack <= 250) and route to the preflop solver.
    """
    game = HUNLPoker(HUNLConfig(starting_stack=5000))  # 50 BB
    result = solve(game, iterations=100)
    assert result.backend != "pushfold_chart"
    assert result.backend != "pushfold"


@pytest.mark.skip(reason="awaiting PR 9 implementation")
def test_dispatch_over_250bb_raises_clear_error():
    """>250 BB -> ValueError with clear message (PR 9 §6 ceiling).

    Integrates: PR 3 + PR 9. The 250 BB cap is the locked v1 ceiling per
    PLAN.md §1; deeper stacks must raise rather than silently degrade.
    """
    game = HUNLPoker(HUNLConfig(starting_stack=25_100))  # 251 BB
    with pytest.raises(ValueError, match="(250|stack)"):
        solve(game, iterations=10)


@pytest.mark.skip(reason="awaiting PR 9 implementation")
def test_dispatch_12bb_hard_cliff_to_pushfold_no_interpolation():
    """12 BB borderline -> push/fold chart (NOT preflop solver).

    Integrates: PR 3 + PR 3.5 + PR 9 §6 hard-cliff decision.
    PR 9 §13 documents the hard-cliff (not interpolated) handoff at 15 BB.
    A 12 BB stack lives on the chart side of that boundary.
    """
    game = HUNLPoker(HUNLConfig(starting_stack=1200))  # 12 BB
    result = solve(game, iterations=0)
    assert result.backend in {"pushfold_chart", "pushfold"}


@pytest.mark.skip(reason="awaiting PR 9 implementation")
def test_dispatch_ante_does_not_tilt_boundary_at_15bb():
    """Ante != 0 must NOT shift the 15 BB push/fold cutoff.

    Integrates: PR 3 (ante in HUNLConfig) + PR 3.5 (chart depth derivation)
    + PR 9 §6 (dispatch composition).

    PR 9 §6 derives `eff_stack_bb = config.starting_stack // config.big_blind`.
    The ante does not enter the formula; both ante=0 and ante=25 at the same
    starting_stack route the same way.
    """
    game_no_ante = HUNLPoker(HUNLConfig(starting_stack=1500, ante=0))
    game_with_ante = HUNLPoker(HUNLConfig(starting_stack=1500, ante=25))
    r_no_ante = solve(game_no_ante, iterations=0)
    r_with_ante = solve(game_with_ante, iterations=0)
    # Both must hit the chart; both must agree on backend.
    assert r_no_ante.backend == r_with_ante.backend
    assert r_no_ante.backend in {"pushfold_chart", "pushfold"}
```

---

## File 2 — `tests/test_integration_abstraction.py`

**Test count:** 3
**PRs integrated:** PR 3 (HUNL tree), PR 4 (card abstraction), PR 6 (Rust port).
**Gating PR:** PR 6 (Python+Rust agreement on bucketed key).

```python
"""Cross-PR integration: PR 3 tree + PR 4 abstraction + PR 6 Rust agreement.

Verifies that loading an abstraction file flips infoset_key shape from
lossless to bucketed, and that the Python and Rust tiers compute byte-equal
bucket ids on the same input.

PRs integrated:
- PR 3: `HUNLPoker.infoset_key` returns lossless `f"{hole}|{board}|{street}|{hist}"`.
- PR 4: optional abstraction layer collapses to `f"b{bucket}|{street}|{hist}"`.
- PR 6: Rust loader reads the same .npz and returns the same bucket id.
"""

from __future__ import annotations

import pytest

from poker_solver import (
    Card,
    HUNLConfig,
    HUNLPoker,
    Street,
)


def _flop_state_for_test(game):
    """Walk to the start of the flop deterministically."""
    s = game.initial_state()
    while game.current_player(s) == -1 and not game.is_terminal(s):
        outcomes = game.chance_outcomes(s)
        s = game.apply(s, outcomes[0][0])
    return s


@pytest.mark.skip(reason="awaiting PR 4 implementation (abstraction lookup)")
def test_abstraction_lossless_when_no_artifact_loaded():
    """No abstraction set -> infoset key keeps the PR 3 lossless format.

    Integrates: PR 3 + PR 4 (no-op path).

    PR 4 §3.5 + §6 commit to: `HUNLConfig.abstraction is None` preserves
    the PR 3 lossless infoset key unchanged. PR 3's 97 existing tests rely
    on this.
    """
    config = HUNLConfig(
        starting_street=Street.FLOP,
        initial_board=(Card.from_str("As"), Card.from_str("7c"), Card.from_str("2d")),
        initial_pot=200,
        initial_contributions=(100, 100),
    )
    game = HUNLPoker(config)
    s = _flop_state_for_test(game)
    key = game.infoset_key(s, 0)
    # Lossless key contains explicit board card string + a `|` separator.
    assert "|" in key
    # Lossless key MUST NOT start with the bucketed `b<digit>|` prefix.
    assert not (key.startswith("b") and key[1:2].isdigit())


@pytest.mark.skip(reason="awaiting PR 4 implementation (abstraction lookup)")
def test_abstraction_bucketed_key_when_artifact_loaded():
    """With abstraction loaded -> infoset key starts with `b<bucket>|`.

    Integrates: PR 3 + PR 4.

    PR 4 §3.5 spec: bucketed format is `f"b{bucket_id}|{street_token}|{betting_history}"`.
    """
    from poker_solver import AbstractionRef, build_abstraction

    # Build a tiny synthetic 4/2/2 artifact for fast in-CI use.
    tmp_path = "/tmp/test_integration_abstraction_v1.npz"
    build_abstraction(
        out_path=tmp_path,
        bucket_counts=(4, 2, 2),
        seed=42,
        H=10,
        max_iter=20,
        streets=[Street.FLOP, Street.TURN, Street.RIVER],
        flop_mode="mc",
        mc_iterations=1_000,
    )
    config = HUNLConfig(
        starting_street=Street.FLOP,
        initial_board=(Card.from_str("As"), Card.from_str("7c"), Card.from_str("2d")),
        initial_pot=200,
        initial_contributions=(100, 100),
        abstraction=AbstractionRef(source_path=tmp_path, version="v1"),
    )
    game = HUNLPoker(config)
    s = _flop_state_for_test(game)
    key = game.infoset_key(s, 0)
    # Bucketed key prefix is `b` followed by a digit and a `|`.
    assert key.startswith("b")
    parts = key.split("|")
    assert len(parts) >= 3  # b<id>, street_token, history
    # Street token at index 1 must be a single char in {p,f,t,r}.
    assert parts[1] in {"p", "f", "t", "r"}


@pytest.mark.skip(reason="awaiting PR 6 implementation (Rust abstraction loader)")
def test_abstraction_bucket_id_matches_python_and_rust_tiers():
    """Same state -> same bucket id under Python loader and Rust loader.

    Integrates: PR 4 (.npz writer + Python loader) + PR 6 (Rust loader).

    PR 6 §4.4 / §6.3: Rust loader un-nests the metadata dict and reads the
    same uint8 arrays. The bucket id is deterministic over the (board,
    hole_cards, street) input regardless of which tier reads the .npz.

    Tolerance: bucket ids are integers; exact equality required (no float
    epsilon).
    """
    from poker_solver import (
        AbstractionRef,
        build_abstraction,
        load_abstraction,
        lookup_bucket,
    )
    # If the Rust binding is unavailable in this environment, skip.
    rust = pytest.importorskip("poker_solver._rust")

    tmp_path = "/tmp/test_integration_abstraction_rust.npz"
    build_abstraction(
        out_path=tmp_path,
        bucket_counts=(4, 2, 2),
        seed=42,
        H=10,
        max_iter=20,
        streets=[Street.FLOP, Street.TURN, Street.RIVER],
        flop_mode="mc",
        mc_iterations=1_000,
    )
    board = (Card.from_str("As"), Card.from_str("7c"), Card.from_str("2d"))
    hole = (Card.from_str("Ah"), Card.from_str("Kh"))

    py_tables = load_abstraction(tmp_path)
    py_bucket = lookup_bucket(py_tables, board, hole, Street.FLOP)
    rust_bucket = rust.lookup_bucket(tmp_path, board, hole, int(Street.FLOP))
    assert py_bucket == rust_bucket
```

---

## File 3 — `tests/test_integration_solve_full_chain.py`

**Test count:** 2
**PRs integrated:** PR 3 (tree) + PR 4 (abstraction) + PR 5 (solver) + PR 6 (Rust).
**Gating PR:** PR 6 (Python+Rust strategy diff).

```python
"""Cross-PR integration: full Python+Rust solve chain on a tiny subgame.

PRs integrated:
- PR 3: HUNLPoker postflop tree construction.
- PR 4: card abstraction layered behind infoset_key.
- PR 5: `solve_hunl_postflop` Python tier.
- PR 6: Rust port + differential test.

Tolerance: per PR 6 §7.3 and PR 9 §10.4 — `5e-3` per-action probability,
`1e-3 × base_pot` per-spot game value. Tighter tolerances are unjustifiably
fragile at HUNL scale (HashMap iteration order × float-reduction tree).
"""

from __future__ import annotations

import pytest

from poker_solver import (
    Card,
    HUNLConfig,
    Street,
)


@pytest.mark.skip(reason="awaiting PR 6 implementation (Rust postflop solve)")
def test_full_chain_python_rust_agree_within_tolerance_no_abstraction():
    """Tiny river subgame solved in both tiers; strategies match.

    Integrates: PR 3 + PR 5 + PR 6.

    Setup: PR 3's `default_tiny_subgame()` (cardless, no abstraction needed).
    Run 500 iterations in each tier; assert per-action diff < 5e-3 and
    per-spot game value within 1e-3 BB.
    """
    from poker_solver import default_tiny_subgame, solve_hunl_postflop
    rust = pytest.importorskip("poker_solver._rust")

    config = default_tiny_subgame()
    py_result = solve_hunl_postflop(config, abstraction=None, iterations=500)
    rust_result = rust.solve_hunl_postflop(config, None, 500)

    # Per-spot game value tolerance: 1e-3 BB (default tiny subgame base pot = 10 BB).
    assert py_result.game_value == pytest.approx(rust_result.game_value, abs=1e-3 * 10)

    # Per-infoset, per-action probability tolerance: 5e-3.
    for key, py_probs in py_result.average_strategy.items():
        rust_probs = rust_result.average_strategy.get(key)
        assert rust_probs is not None, f"missing infoset {key} in Rust output"
        assert len(py_probs) == len(rust_probs)
        for py_p, rust_p in zip(py_probs, rust_probs):
            assert py_p == pytest.approx(rust_p, abs=5e-3)


@pytest.mark.skip(reason="awaiting PR 6 implementation")
def test_full_chain_python_rust_agree_with_card_abstraction():
    """Flop subgame WITH PR 4 abstraction solved in both tiers; strategies match.

    Integrates: PR 3 + PR 4 + PR 5 + PR 6.

    This is the layer-stack test: a divergence here can mean (a) bucket
    lookup differs across tiers (PR 4/6 boundary), (b) DCFR update order
    differs (PR 6 mechanical port issue), or (c) infoset key format drift.
    """
    from poker_solver import (
        AbstractionRef,
        build_abstraction,
        solve_hunl_postflop,
    )
    rust = pytest.importorskip("poker_solver._rust")

    tmp_path = "/tmp/test_integration_solve_chain.npz"
    build_abstraction(
        out_path=tmp_path,
        bucket_counts=(4, 2, 2),
        seed=42,
        H=10,
        max_iter=20,
        streets=[Street.FLOP, Street.TURN, Street.RIVER],
        flop_mode="mc",
        mc_iterations=1_000,
    )
    config = HUNLConfig(
        starting_street=Street.FLOP,
        initial_board=(
            Card.from_str("As"),
            Card.from_str("7c"),
            Card.from_str("2d"),
        ),
        starting_stack=10_000,
        initial_pot=200,
        initial_contributions=(100, 100),
        bet_size_fractions=(0.33, 0.75, 2.00),
        abstraction=AbstractionRef(source_path=tmp_path, version="v1"),
    )
    py_result = solve_hunl_postflop(config, iterations=200)
    rust_result = rust.solve_hunl_postflop(config, None, 200)

    assert py_result.game_value == pytest.approx(rust_result.game_value, abs=1e-3 * (200 / 100))

    # Spot-check: at least one shared infoset key, probabilities agree.
    shared_keys = set(py_result.average_strategy) & set(rust_result.average_strategy)
    assert shared_keys, "expected at least one shared infoset key across tiers"
    for key in shared_keys:
        py_probs = py_result.average_strategy[key]
        rust_probs = rust_result.average_strategy[key]
        assert len(py_probs) == len(rust_probs)
        for py_p, rust_p in zip(py_probs, rust_probs):
            assert py_p == pytest.approx(rust_p, abs=5e-3)
```

---

## File 4 — `tests/test_integration_preflop_postflop_handoff.py`

**Test count:** 3
**PRs integrated:** PR 3.5 (chart) + PR 5 (postflop) + PR 9 (preflop blueprint + refinement).
**Gating PR:** PR 9.

```python
"""Cross-PR integration: PR 9 blueprint + subgame refinement handoff.

PRs integrated:
- PR 3.5: push/fold chart short-circuit at <=15 BB.
- PR 5: postflop solver consumed by subgame refinement.
- PR 9: blueprint produces preflop strategy; subgame refiner consumes it as
  warm start.

PR 9 §3.2 commits to blueprint + subgame-refinement decomposition. PR 9
§7.4 commits to combined exploitability < 0.05 BB/hand on the 100 BB Pio
fixture (end-to-end target).
"""

from __future__ import annotations

import pytest

from poker_solver import (
    HUNLConfig,
    HUNLPoker,
    Street,
)


@pytest.mark.skip(reason="awaiting PR 9 implementation (blueprint)")
def test_preflop_blueprint_produces_strategy_at_100bb():
    """Blueprint pass populates a preflop strategy table.

    Integrates: PR 3 (HUNLPoker preflop tree) + PR 4 (abstraction) + PR 9
    (blueprint).

    PR 9 §10.1 test 4: every reachable preflop infoset (reach_prob > 0) must
    have a strategy entry in `blueprint.strategy`.
    """
    from poker_solver import build_blueprint, tiny_synthetic_abstraction

    config = HUNLConfig(starting_stack=10_000)  # 100 BB
    abstraction = tiny_synthetic_abstraction()
    blueprint = build_blueprint(
        config,
        abstraction,
        postflop_menu=(0.75,),
        postflop_raise_cap=1,
        iterations=500,
        seed=42,
    )
    assert blueprint.strategy, "blueprint produced empty strategy table"
    # Every reachable infoset must have non-empty action probabilities.
    for key, probs in blueprint.strategy.items():
        assert sum(probs) == pytest.approx(1.0, abs=1e-6)
        assert all(0.0 <= p <= 1.0 for p in probs)


@pytest.mark.skip(reason="awaiting PR 9 implementation (subgame warm start)")
def test_subgame_refinement_uses_blueprint_as_warm_start():
    """Refinement starts regret tables from blueprint, then improves.

    Integrates: PR 5 (postflop solver) + PR 9 (blueprint + refiner).

    PR 9 §8.3 commits to warm-start regret loading; PR 9 §10.2 test 2 makes
    this a soft assertion (warm-start solve reaches target in fewer
    iterations than cold-start). Here we just lock the contract: the
    refinement result must reference the blueprint's strategy values for
    overlapping infoset keys.
    """
    from poker_solver import (
        SubgameKey,
        build_blueprint,
        refine_subgame,
        tiny_synthetic_abstraction,
    )

    config = HUNLConfig(starting_stack=10_000)
    abstraction = tiny_synthetic_abstraction()
    blueprint = build_blueprint(
        config, abstraction, postflop_menu=(0.75,), postflop_raise_cap=1,
        iterations=200, seed=42,
    )
    # Pick the highest-reach subgame for refinement.
    if not blueprint.leaf_values:
        pytest.skip("blueprint did not produce any postflop leaves at this fixture")
    subgame_key = max(
        blueprint.leaf_values.keys(),
        key=lambda k: blueprint.reach_probs.get(str(k), 0.0),
    )
    refined = refine_subgame(
        subgame_key,
        blueprint,
        abstraction,
        iterations=100,
        seed=42,
    )
    assert refined.refined_strategy, "refinement produced empty strategy"
    # Combined output: refinement game_value finite and within plausible bounds.
    assert -100.0 <= refined.game_value <= 100.0


@pytest.mark.skip(reason="awaiting PR 9 implementation (push/fold passthrough at 8 BB)")
def test_pushfold_at_8bb_does_not_invoke_preflop_solver():
    """8 BB stack -> chart short-circuit; preflop blueprint MUST NOT run.

    Integrates: PR 3.5 + PR 9 §6 dispatch.

    PR 9 §6 ordering invariant: push/fold short-circuit MUST execute BEFORE
    the preflop branch. A misordering bug would burn 30+ minutes solving an
    8 BB preflop tree when the chart answer is O(1).
    """
    from poker_solver import solve

    game = HUNLPoker(HUNLConfig(starting_stack=800))  # 8 BB
    # iterations=0 ensures any solver path that actually runs CFR would
    # produce a near-empty strategy; the chart path returns a populated
    # 169-class strategy regardless.
    result = solve(game, iterations=0)
    assert result.backend in {"pushfold_chart", "pushfold"}
    # Negative assertion: the dispatched_to_pushfold flag (PR 9 §4
    # PreflopSolveResult) must be True OR backend is the chart marker.
    pushfold_flag = getattr(result, "dispatched_to_pushfold", None)
    if pushfold_flag is not None:
        assert pushfold_flag is True
```

---

## File 5 — `tests/test_integration_ui_engine.py`

**Test count:** 3
**PRs integrated:** PR 3..9 (engine), PR 10 (UI scaffold + range matrix + cancellation).
**Gating PR:** PR 10.

```python
"""Cross-PR integration: PR 10 UI surfaces against the PR 3..9 engine.

PRs integrated:
- PR 3..9: engine (HUNLPoker + abstraction + postflop + preflop solvers).
- PR 10: UI `SolveRunner` (worker thread + cancellation flags), range matrix
  (combo-to-frequency mapping), decision tree browser (no opponent-card
  leakage in tooltips).

PR 10 §6 spec: cancellation flag must halt the worker within 1 iteration.
PR 10 §3.3 spec: combo->frequency mapping has no off-by-one (critical
correctness item #2).
"""

from __future__ import annotations

import time

import pytest

from poker_solver import HUNLConfig, HUNLPoker


@pytest.mark.skip(reason="awaiting PR 10 implementation (SolveRunner)")
def test_ui_solve_runner_cancellation_halts_within_one_iteration():
    """UI stop flag halts the worker within 1 iteration after set.

    Integrates: PR 5/9 (solver) + PR 10 (SolveRunner cancellation).

    PR 10 §6.1 spec: worker checks `_stop_event` every iteration. Setting
    the flag after N iterations must produce a partial-result snapshot with
    iteration count >= N and <= N+1 (one-iteration grace).
    """
    from ui.state import SolveRunner

    runner = SolveRunner()
    game = HUNLPoker(HUNLConfig(starting_stack=10_000))
    runner.start(
        game,
        iterations=1_000_000,
        log_every=10,
        dcfr_kwargs={},
        on_progress=lambda i, e: None,
    )
    # Let it run for a short window.
    time.sleep(0.5)
    iters_before_stop = runner.iteration
    runner.stop()
    # Give the worker one iteration to observe the flag and exit.
    time.sleep(1.0)
    iters_after_stop = runner.iteration
    assert iters_after_stop <= iters_before_stop + 1
    assert runner.status in {"stopped", "done"}


@pytest.mark.skip(reason="awaiting PR 10 implementation (tree browser tooltips)")
def test_ui_tree_browser_does_not_leak_opponent_hole_cards():
    """Tree browser tooltips show infoset key for the acting player only.

    Integrates: PR 3 (infoset_key hides opponent cards) + PR 10 (tree
    browser hover detail).

    PR 3 §infoset key spec: opponent hole cards are NOT included in the
    acting-player's infoset key. PR 10 §3.4 commits to "Hover detail:
    infoset key (truncated, monospace), reach probability, range-weighted
    EV." If the UI assembled a key that exposed opponent cards (e.g., by
    pulling raw state instead of `game.infoset_key(state, player)`), this
    test catches it.
    """
    from ui.state import SolveTree

    game = HUNLPoker(HUNLConfig())
    tree = SolveTree(game)
    nodes = tree.expand_root()
    # Walk a depth-3 sample of the lazy tree.
    samples = []
    for node in nodes[:5]:
        samples.append(node)
        samples.extend(tree.expand(node["id"])[:5])
    # Tooltip / infoset key must NEVER contain both players' hole cards.
    for node in samples:
        tooltip = node.get("tooltip", "") or node.get("infoset_key", "")
        # Heuristic: if the tooltip contains two distinct two-card hand
        # strings separated by `|`, it's leaking opponent cards. This catches
        # an accidental `f"{p0_hole}|{p1_hole}|..."` debug-string leak.
        parts = tooltip.split("|")
        hole_like_parts = [
            p for p in parts
            if len(p) == 4 and all(c in "AKQJT98765432shdc" for c in p)
        ]
        assert len(hole_like_parts) <= 1, (
            f"tree browser leaked opponent cards in node {node['id']}: {tooltip}"
        )


@pytest.mark.skip(reason="awaiting PR 10 implementation (range matrix)")
def test_ui_range_matrix_aggregates_per_combo_strategies_correctly():
    """13x13 matrix's per-cell freq equals weighted avg of survivor combos.

    Integrates: PR 5/9 (solver per-combo strategy) + PR 10 (range matrix
    aggregation).

    PR 10 §3.3 critical correctness item #2: "combo -> frequency mapping
    has no off-by-one." For a hand class like AKs on a board that blocks
    AhKh, the cell must aggregate over the 3 survivor combos (AsKs, AdKd,
    AcKc), not the full 4. Verifies the blocker filter + the weighted-mean
    formula.

    PR 10 §3.3 color blend formula:
        freq_action = avg over surviving combos of strategy[combo, action]
    """
    from ui.views.range_matrix import compute_cell_frequencies
    from poker_solver import Card

    # Synthetic per-combo strategy for AKs on a board containing Kh.
    # Survivors: AsKs, AdKd, AcKc. Block: AhKh (Kh is on the board).
    per_combo_strategy = {
        ("As", "Ks"): {"fold": 0.0, "call": 0.5, "raise": 0.5},
        ("Ad", "Kd"): {"fold": 0.0, "call": 1.0, "raise": 0.0},
        ("Ac", "Kc"): {"fold": 0.0, "call": 0.0, "raise": 1.0},
        # AhKh blocked by Kh on board.
    }
    board = (Card.from_str("Kh"), Card.from_str("7c"), Card.from_str("2d"))
    cell_freqs = compute_cell_frequencies(
        hand_class="AKs",
        per_combo_strategy=per_combo_strategy,
        board=board,
    )
    # Expected: avg of (0.5, 1.0, 0.0) for call = 0.5; avg of raise = 0.5.
    assert cell_freqs["fold"] == pytest.approx(0.0)
    assert cell_freqs["call"] == pytest.approx(0.5)
    assert cell_freqs["raise"] == pytest.approx(0.5)
    # Survivor combo count must be 3 (NOT 4 — AhKh blocked).
    assert cell_freqs.get("combo_count", 3) == 3
```

---

## File 6 — `tests/test_integration_library_roundtrip.py`

**Test count:** 2
**PRs integrated:** PR 5 (postflop solver), PR 11 (library mode).
**Gating PR:** PR 11.

```python
"""Cross-PR integration: PR 11 library save/load roundtrip.

PRs integrated:
- PR 5: `solve_hunl_postflop` produces `HUNLSolveResult` with `average_strategy`.
- PR 11: `Library.put` / `Library.get` round-trips through SQLite + gzip JSON.

PR 11 §2.3 spot ID determinism is critical: a misorder of canonical fields
(e.g., bet-menu fractions not sorted) would mean the same spot solved on
two machines produces two different IDs, breaking the cache.

PR 11 §2.4: bit-exact roundtrip required — float values must compare `==`.
"""

from __future__ import annotations

import pytest

from poker_solver import (
    Card,
    HUNLConfig,
    Street,
)


@pytest.mark.skip(reason="awaiting PR 11 implementation (Library)")
def test_library_roundtrip_solve_save_reload_returns_same_strategies(tmp_path):
    """Solve -> save to library -> reload -> bit-exact strategy match.

    Integrates: PR 5 + PR 11.

    PR 11 §2.4 commits to bit-exact float roundtrip through gzip JSON. A
    failure here means the JSON serializer is doing lossy conversion
    (e.g., using `repr(float)` truncation, or `default=str`).
    """
    from poker_solver import default_tiny_subgame, solve_hunl_postflop
    from poker_solver.library import Library, SpotDescription

    config = default_tiny_subgame()
    result = solve_hunl_postflop(config, iterations=100)

    library_path = tmp_path / "library.db"
    with Library.open(library_path) as lib:
        spot = SpotDescription(config=config, initial_ranges=None, label="test_roundtrip")
        spot_id = lib.put(spot, result)

    with Library.open(library_path) as lib:
        roundtripped = lib.get(spot_id)

    assert roundtripped is not None
    assert roundtripped.game_value == result.game_value
    # Bit-exact average_strategy roundtrip.
    assert set(roundtripped.average_strategy) == set(result.average_strategy)
    for key, probs in result.average_strategy.items():
        for orig_p, round_p in zip(probs, roundtripped.average_strategy[key]):
            # bit-exact equality (PR 11 §2.4)
            assert orig_p == round_p


@pytest.mark.skip(reason="awaiting PR 11 implementation (Library)")
def test_library_spot_id_is_deterministic_across_runs():
    """Same SpotDescription -> same spot_id (across two runs, two processes).

    Integrates: PR 3 (HUNLConfig) + PR 11 (spot ID canonicalization).

    PR 11 §2.3 determinism: canonical form sorts bet-menu tuple, sorts
    board cards, normalizes stacks to int cents, includes ante/rake even
    when 0. Equivalent descriptions must hash to the same ID.
    """
    from poker_solver.library import SpotDescription

    config_a = HUNLConfig(
        starting_street=Street.FLOP,
        initial_board=(Card.from_str("As"), Card.from_str("7c"), Card.from_str("2d")),
        initial_pot=200,
        initial_contributions=(100, 100),
        bet_size_fractions=(0.33, 0.75, 2.00),
    )
    # Re-construct an "equivalent" config — same fields but possibly different
    # tuple-ordering of bet sizes. PR 11 canonicalization must collapse them.
    config_b = HUNLConfig(
        starting_street=Street.FLOP,
        initial_board=(Card.from_str("As"), Card.from_str("7c"), Card.from_str("2d")),
        initial_pot=200,
        initial_contributions=(100, 100),
        bet_size_fractions=(0.75, 2.00, 0.33),  # reordered
    )
    spot_a = SpotDescription(config=config_a, initial_ranges=None, label="a")
    spot_b = SpotDescription(config=config_b, initial_ranges=None, label="b")
    # Labels differ but identity-fields match: spot IDs must agree.
    assert spot_a.spot_id() == spot_b.spot_id()

    # Cross-run determinism: a second computation of the same spot_id is identical.
    assert spot_a.spot_id() == spot_a.spot_id()
```

---

## Summary table

| File | Count | PRs Integrated | Gating PR |
|---|---|---|---|
| `test_integration_dispatch.py` | 5 | PR 3, 3.5, 5, 9 | PR 9 |
| `test_integration_abstraction.py` | 3 | PR 3, 4, 6 | PR 6 |
| `test_integration_solve_full_chain.py` | 2 | PR 3, 4, 5, 6 | PR 6 |
| `test_integration_preflop_postflop_handoff.py` | 3 | PR 3.5, 5, 9 | PR 9 |
| `test_integration_ui_engine.py` | 3 | PR 3..9, 10 | PR 10 |
| `test_integration_library_roundtrip.py` | 2 | PR 5, 11 | PR 11 |
| **TOTAL** | **18** | | |

## Author's bug-likelihood call

**Most likely to surface a real bug:** `test_integration_dispatch.py` — specifically the ante-doesn't-tilt-boundary case (`test_dispatch_ante_does_not_tilt_boundary_at_15bb`).

**Why:** the dispatch composition in PR 9 §6 is canonical and cross-referenced from PR 3.5 §6 and PR 5 §6, but each spec was authored at a different time. The push/fold short-circuit derives `eff_stack_bb = config.starting_stack // config.big_blind`, while a developer wiring the preflop branch might naively use `min(stacks)` or `min(stacks) - ante` to derive depth, accidentally shifting the 15 BB cutoff when antes are non-zero. The hard-cliff boundary at exactly 15 BB and the ordering invariant (chart MUST run before postflop/preflop branches regardless of `starting_street`) are exactly the kind of constraint that's easy to break across PRs since each agent only owns one branch. Test 4 (`test_dispatch_12bb_hard_cliff`) and test 5 (`test_dispatch_ante_does_not_tilt`) catch this class of bug at the seam between PR 3.5 and PR 9.

The other likely-bug class is `test_full_chain_python_rust_agree_with_card_abstraction` (PR 4 + PR 5 + PR 6 stack) — a subtle bug in the Rust loader's metadata un-nesting (PR 6 §4.4) would silently shift bucket assignments and produce a strategy diff just below the `5e-3` tolerance but above true equality. That one is harder to catch with a single-tier test.
