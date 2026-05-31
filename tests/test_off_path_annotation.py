"""v1.8.2 (#47) — off-path infoset annotation on ``SolveResult``.

The solver post-processes its average strategy with a forward-walk that
sums joint reach (own × opp × chance) per infoset; the result dataclass
exposes ``reach_probability`` (dict) and ``off_path_keys`` (frozenset)
so downstream consumers (CLI tree walk, persona-test filters, library
queries) can cheaply skip the "phantom 5%" infosets the engine builds
during training but that have effectively zero joint reach in the
final strategy.

Test coverage:

* Helper math sanity on Kuhn (small, deterministic — every root infoset
  has reach 1/3 because the chance node enumerates a 3-card deal).
* AK vs QQ river fixture (the canonical phantom-5% case): on-path
  decisions have reach > 0.1, off-path "QQ shoves over a bet" lines
  have reach < 1e-6 and appear in ``off_path_keys``.
* The frozenset matches the dict derivation under the threshold.
* Empty strategy is a no-op (degenerate fixtures don't crash).
* Library round-trip leaves the fields as their empty defaults (additive
  contract — old serialized payloads load without the new fields).
"""

from __future__ import annotations

import pytest

from poker_solver.games import KuhnPoker, LeducPoker
from poker_solver.solver import (
    _OFF_PATH_REACH_THRESHOLD,
    SolveResult,
    _annotate_off_path,
    _compute_reach_probabilities,
    solve,
)


# ---------------------------------------------------------------------------
# Helper math sanity on small games
# ---------------------------------------------------------------------------


def test_solve_result_defaults_are_additive() -> None:
    """New fields default to empty so existing call sites don't break."""
    result = SolveResult(average_strategy={})
    assert result.reach_probability == {}
    assert result.off_path_keys == frozenset()


def test_reach_probabilities_kuhn_root_infosets_sum_to_one_per_card() -> None:
    """Each Kuhn root infoset has reach 1/3 (chance deals one of 3 cards)."""
    game = KuhnPoker()
    # Uniform random strategy — we just want the chance-prob threading.
    result = solve(game, iterations=20, backend="python", seed=42)

    # Every root-only infoset (empty history "") for each of 3 cards has
    # reach exactly 1/3 (the chance node enumerates J/Q/K uniformly).
    root_keys = [k for k in result.reach_probability if k.endswith("|")]
    assert len(root_keys) == 3, f"expected 3 root keys, got {root_keys!r}"
    for k in root_keys:
        assert abs(result.reach_probability[k] - 1.0 / 3.0) < 1e-9, (
            f"root reach for {k!r} = {result.reach_probability[k]}, expected 1/3"
        )


def test_reach_probabilities_match_explicit_helper_call() -> None:
    """``_compute_reach_probabilities`` is deterministic given the strategy."""
    game = KuhnPoker()
    result = solve(game, iterations=30, backend="python", seed=42)
    # Re-run the helper independently; result should bit-match.
    redo = _compute_reach_probabilities(result.average_strategy, game)
    assert redo == result.reach_probability


def test_off_path_keys_match_threshold_filter() -> None:
    """``off_path_keys`` is exactly {k : reach[k] < 1e-6}."""
    game = LeducPoker()
    # Few iterations -> non-trivial off-path mass at deeper infosets.
    result = solve(game, iterations=20, backend="python", seed=42)
    expected = frozenset(
        k for k, r in result.reach_probability.items()
        if r < _OFF_PATH_REACH_THRESHOLD
    )
    assert result.off_path_keys == expected


def test_annotate_off_path_skips_empty_strategy() -> None:
    """Helper is a no-op when ``average_strategy`` is empty."""
    result = SolveResult(average_strategy={})
    _annotate_off_path(result, KuhnPoker())
    assert result.reach_probability == {}
    assert result.off_path_keys == frozenset()


def test_annotate_off_path_mutates_in_place_and_returns() -> None:
    """Helper returns the same object it mutated (for chaining)."""
    game = KuhnPoker()
    result = solve(game, iterations=10, backend="python", seed=7)
    # Wipe the annotation, re-run, verify mutation + identity.
    result.reach_probability = {}
    result.off_path_keys = frozenset()
    returned = _annotate_off_path(result, game)
    assert returned is result
    assert len(result.reach_probability) > 0


# ---------------------------------------------------------------------------
# Canonical AK vs QQ river phantom-5% fixture
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    pytest.importorskip("poker_solver.hunl_solver", reason="hunl_solver missing")
    is None,
    reason="HUNL postflop solver unavailable",
)
def test_ak_vs_qq_river_off_path_classification() -> None:
    """Canonical phantom-5% case: QQ-shove-over-b750 has reach < 1e-6.

    On the As 7c 2d Kh 5s board with hero AhKc (top pair / top kicker)
    vs villain QdQh (overpair with a king-on-board overcard), the engine
    converges with QQ folding most of the time facing a 750 bet from
    hero. The "QQ shoves all-in over a 750 bet" line (`...|r|b750A`) is
    a phantom 5%: the engine assigns some action mass to it during
    regret matching, but the multiplicative reach from root is below
    1e-6 because the priors (QQ rarely getting to that decision) crush
    the joint probability.

    We assert:
        * On-path nodes (P1's first decision, P0 after a check) have
          reach >= 0.1.
        * ``off_path_keys`` is non-empty and contains at least one
          ``...b750A`` infoset (the QQ-shove-over-b750 phantom).
    """
    from poker_solver import HUNLConfig, parse_board, parse_hand
    from poker_solver.hunl import Street
    from poker_solver.hunl_solver import solve_hunl_postflop

    board = parse_board("As 7c 2d Kh 5s")
    hero = parse_hand("AhKc")
    villain = parse_hand("QdQh")
    cfg = HUNLConfig(
        starting_stack=1000,
        small_blind=50,
        big_blind=100,
        starting_street=Street.RIVER,
        initial_board=tuple(board),
        initial_pot=1000,
        initial_contributions=(500, 500),
        initial_hole_cards=((hero[0], hero[1]), (villain[0], villain[1])),
        bet_size_fractions=(0.33, 0.75),
        postflop_raise_cap=3,
    )
    # v1.11 lean-raise re-capture: the C2 bet-size-menu engine change
    # (commit f69ec29) collapsed the multi-size raise ladder to a single
    # 3.0x raise multiplier. The leaner river tree has fewer raise
    # branches, so phantom lines decay toward zero reach MORE SLOWLY
    # (less multiplicative dilution per phantom decision). At 50 iters the
    # QQ-over-b750 line still sits at ~1e-5 (above the 1e-6 threshold);
    # 300 iters lets the rare lines converge below it. Verified
    # deterministic at 300 iters (off_path_keys stable across runs, and it
    # contains the canonical ...|r|b750A QQ-shove-over-b750 phantom).
    result = solve_hunl_postflop(cfg, iterations=300, seed=42)

    # Annotation populated.
    assert len(result.reach_probability) > 0, "reach map empty"
    assert isinstance(result.off_path_keys, frozenset)

    # Root infosets (empty history within the river street): both
    # players' first decisions should have reach close to 1.0 (chance
    # is deterministic — single pinned hole-card deal).
    root_p1 = [
        k for k in result.reach_probability
        if k.endswith("|r|") and k.startswith("QhQd|")
    ]
    assert root_p1, f"expected root P1 infoset, got keys: {list(result.reach_probability)[:5]!r}"
    for k in root_p1:
        assert result.reach_probability[k] > 0.1, (
            f"on-path P1 root {k!r} has reach {result.reach_probability[k]}"
        )

    # Off-path keys non-empty: phantom 5% lines exist. The canonical
    # phantom is the QQ-shove-over-b750 line (``...|r|b750A``) the
    # docstring describes — assert it specifically rather than just the
    # count, so the test stays load-bearing on the exact phantom claimed.
    assert len(result.off_path_keys) > 0, (
        "expected at least one phantom (off-path) infoset"
    )
    assert any(k.endswith("b750A") for k in result.off_path_keys), (
        "expected the QQ-shove-over-b750 phantom (...|r|b750A) in "
        f"off_path_keys; got {sorted(result.off_path_keys)}"
    )

    # All off-path keys have reach < 1e-6 by construction.
    for k in result.off_path_keys:
        assert result.reach_probability[k] < _OFF_PATH_REACH_THRESHOLD


# ---------------------------------------------------------------------------
# Library round-trip is backward-compatible
# ---------------------------------------------------------------------------


def test_library_dict_to_result_leaves_new_fields_empty() -> None:
    """A library payload without the new fields deserializes to empty defaults.

    The library JSON format predates v1.8.2 #47; old payloads omit the
    new fields entirely. ``_dict_to_result`` should load them as empty
    (signal "annotation unavailable"), NOT crash.
    """
    from poker_solver.library import _dict_to_result

    payload = {
        "average_strategy": {"x|y|z": [0.5, 0.5]},
        "exploitability_history": [0.001],
        "game_value": 0.0,
        "iterations": 100,
        "backend": "library",
    }
    result = _dict_to_result(payload)
    assert result.reach_probability == {}
    assert result.off_path_keys == frozenset()
    assert result.average_strategy == {"x|y|z": [0.5, 0.5]}
