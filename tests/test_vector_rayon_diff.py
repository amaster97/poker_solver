"""v1.10 PR-4 differential test: opt-in Rayon DCFR vs canonical single-threaded.

Drives `_rust.solve_range_vs_range_rust` twice on the same fixture — once
with the default single-threaded path (canonical) and once with the
`CFR_RAYON_CHANCE=1` opt-in parallel path — and compares the two output
strategies via:
  - `_rust.compute_exploitability` for the BR-walk exploitability +
    game-value pair (the load-bearing CFR convergence metric).
  - A direct floating-point comparison of per-(infoset, hand) action
    probabilities, with a coarse total-variation tolerance (the parallel
    path drifts from bit-identical due to chance-node sum reordering,
    same effect as PR #170's `BrWalkMode::Vector`).

Tolerances (per `docs/v1_10_postflop_optimization_plan.md` §4.2 and the
PR-4 task brief):

  - exploitability: 1e-6 BB/hand
  - game_value:     1e-9 BB/hand
  - per-action probability TVD per infoset: 1e-4 (informational; not a
    gate, since chance-sum reordering can shift mixed-strategy mass
    when hands are near-indifferent)

The 8 kill-switch fixtures mirror the F1-F8 turn/river fixtures in
`crates/cfr_core/src/exploit.rs::tests` so the diff coverage matches
the canonical Vector-vs-PerCombo gate. Each fixture is small enough to
finish in well under a minute end-to-end (both backends).

CRITICAL: this file's `pytestmark` REQUIRES the env var to be settable
per test. We use `monkeypatch.setenv("CFR_RAYON_CHANCE", "1")` in each
parallel-path invocation; the canonical-path invocation explicitly
`monkeypatch.delenv("CFR_RAYON_CHANCE", raising=False)` to guard
against stale env vars in the test runner.
"""

from __future__ import annotations

import importlib
import time
from typing import Any

import pytest

try:
    from poker_solver import HUNLConfig, Street, parse_board
    from poker_solver.card import Card, card_to_int
    from poker_solver.hunl import _serialize_hunl_config
except Exception:  # noqa: BLE001
    HUNLConfig = None  # type: ignore[assignment,misc]
    Street = None  # type: ignore[assignment,misc]
    parse_board = None  # type: ignore[assignment]
    Card = None  # type: ignore[assignment,misc]
    card_to_int = None  # type: ignore[assignment]
    _serialize_hunl_config = None  # type: ignore[assignment]

try:
    _rust_module = importlib.import_module("poker_solver._rust")
    _rust_solve_rvr = getattr(_rust_module, "solve_range_vs_range_rust", None)
    _rust_compute_exploitability = getattr(_rust_module, "compute_exploitability", None)
except Exception:  # noqa: BLE001
    _rust_solve_rvr = None  # type: ignore[assignment]
    _rust_compute_exploitability = None  # type: ignore[assignment]


pytestmark = [
    pytest.mark.skipif(
        HUNLConfig is None,
        reason="poker_solver HUNL surface not importable",
    ),
    pytest.mark.skipif(
        _rust_solve_rvr is None or _rust_compute_exploitability is None,
        reason=(
            "_rust.solve_range_vs_range_rust or _rust.compute_exploitability "
            "missing — rebuild via `maturin develop --release`"
        ),
    ),
]


# Tolerances per v1.10 PR-4 task brief.
_EXPL_TOL: float = 1e-6
_GV_TOL: float = 1e-9


# ---------------------------------------------------------------------------
# Fixture configs (mirror exploit.rs F1-F8)
# ---------------------------------------------------------------------------


def _river_mini_cfg(bet_sizes: tuple[float, ...], raise_cap: int) -> HUNLConfig:
    """River fixture matching exploit.rs::river_mini_cfg.

    Board As 7c 2d Kh 5s, blinds 50/100, pot 1000, contributions [500,500],
    starting_stack 1000, no all-in escape, range-vs-range root.
    """
    board = parse_board("As 7c 2d Kh 5s")
    return HUNLConfig(
        starting_stack=1000,
        small_blind=50,
        big_blind=100,
        ante=0,
        starting_street=Street.RIVER,
        initial_board=tuple(board),
        initial_pot=1000,
        initial_contributions=(500, 500),
        initial_hole_cards=(),
        preflop_raise_cap=4,
        postflop_raise_cap=raise_cap,
        bet_size_fractions=bet_sizes,
        include_all_in=False,
    )


def _turn_mini_cfg(
    bet_sizes: tuple[float, ...],
    raise_cap: int,
    starting_stack: int,
) -> HUNLConfig:
    """Turn fixture matching exploit.rs::turn_mini_cfg.

    Board Qs 7h 2d 5c, blinds 50/100, pot 1000, contributions [500,500],
    `starting_stack` parameterized (1000 default; 20000 = deep-stack W2.3-
    shaped variant). No all-in escape.
    """
    return HUNLConfig(
        starting_stack=starting_stack,
        small_blind=50,
        big_blind=100,
        ante=0,
        starting_street=Street.TURN,
        initial_board=(
            Card(12, 0),  # Qs (rank 12, suit 0=s)
            Card(7, 2),  # 7h (rank 7, suit 2=h)
            Card(2, 1),  # 2d (rank 2, suit 1=d)
            Card(5, 3),  # 5c (rank 5, suit 3=c)
        ),
        initial_pot=1000,
        initial_contributions=(500, 500),
        initial_hole_cards=(),
        preflop_raise_cap=4,
        postflop_raise_cap=raise_cap,
        bet_size_fractions=bet_sizes,
        include_all_in=False,
    )


def _hand_pair_from_indices(c0: int, c1: int) -> list[int]:
    """Return a 2-card hole list ordered as the Rust side expects.

    Cards use the `card_to_int` encoding `rank * 4 + suit`, range
    `[8, 59]` (rank from 2-14 = ace; suit 0-3). The Rust binding's
    held-card array is `[bool; 64]`, indexed directly by card_to_int —
    do NOT pass 0-51.
    """
    return [min(c0, c1), max(c0, c1)]


def _pick_n_disjoint_hands(board: list[Card], n: int) -> list[list[int]]:
    """Pick `n` disjoint hole pairs, stride-spread for diversity.

    Uses the `card_to_int` encoding (range [8, 59]) so the resulting
    hole list is directly consumable by `_rust.solve_range_vs_range_rust`.
    """
    held = {card_to_int(c) for c in board}
    # Full deck in card_to_int encoding: rank 2..=14, suit 0..=3 ⇒ card_to_int ∈ [8, 59].
    deck = [card_to_int(Card(r, s)) for r in range(2, 15) for s in range(4) if card_to_int(Card(r, s)) not in held]
    pairs: list[list[int]] = []
    seen: set[int] = set()
    # Stride spreads across deck to keep card diversity high.
    stride = max(1, len(deck) // (n * 4))
    i = 0
    while len(pairs) < n and i < len(deck) - 1:
        c0 = deck[i]
        c1 = deck[i + 1]
        if c0 not in seen and c1 not in seen and c0 not in held and c1 not in held:
            pairs.append(_hand_pair_from_indices(c0, c1))
            seen.add(c0)
            seen.add(c1)
        i += stride
    # Fallback: linear fill if stride underfilled.
    j = 0
    while len(pairs) < n and j < len(deck) - 1:
        c0 = deck[j]
        c1 = deck[j + 1]
        if c0 not in seen and c1 not in seen:
            pairs.append(_hand_pair_from_indices(c0, c1))
            seen.add(c0)
            seen.add(c1)
        j += 1
    assert len(pairs) == n, f"could only pick {len(pairs)} disjoint pairs of {n} requested"
    return pairs


# ---------------------------------------------------------------------------
# Solve helpers
# ---------------------------------------------------------------------------


def _solve_with_env(
    cfg: HUNLConfig,
    iterations: int,
    p0_holes: list[list[int]] | None,
    p1_holes: list[list[int]] | None,
    *,
    rayon: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    """Run the Rust vector-form DCFR solve with `CFR_RAYON_CHANCE` set/unset.

    Returns the raw dict from `_rust.solve_range_vs_range_rust`.
    """
    if rayon:
        monkeypatch.setenv("CFR_RAYON_CHANCE", "1")
    else:
        monkeypatch.delenv("CFR_RAYON_CHANCE", raising=False)
    config_json = _serialize_hunl_config(cfg)
    return _rust_solve_rvr(
        config_json,
        iterations,
        1.5,
        0.0,
        2.0,
        p0_holes,
        p1_holes,
    )


def _exploit_walk(cfg: HUNLConfig, strategy: dict[str, list[float]]) -> tuple[float, float]:
    """Wraps `_rust.compute_exploitability`. Returns `(exploitability, game_value)`."""
    config_json = _serialize_hunl_config(cfg)
    out = _rust_compute_exploitability(config_json, strategy)
    return float(out["exploitability"]), float(out["game_value"])


def _strategy_for_diff(d: dict[str, Any]) -> dict[str, list[float]]:
    """Coerce the Rust dict's average_strategy values to lists for the BR walk."""
    return {k: [float(x) for x in v] for k, v in d["average_strategy"].items()}


def _max_prob_diff(
    canonical_strategy: dict[str, list[float]],
    rayon_strategy: dict[str, list[float]],
) -> float:
    """Largest per-(infoset, hand, action) probability divergence."""
    max_diff = 0.0
    for k, c in canonical_strategy.items():
        if k not in rayon_strategy:
            continue
        r = rayon_strategy[k]
        for ci, ri in zip(c, r):
            d = abs(ci - ri)
            if d > max_diff:
                max_diff = d
    return max_diff


def _assert_parallel_matches_canonical(
    cfg: HUNLConfig,
    iterations: int,
    p0_holes: list[list[int]] | None,
    p1_holes: list[list[int]] | None,
    name: str,
    monkeypatch: pytest.MonkeyPatch,
    *,
    skip_br_walk: bool = False,
) -> None:
    """Run both backends, assert exploitability + game_value agreement.

    When `skip_br_walk=True`, the post-solve BR walk
    (`_rust.compute_exploitability`) is skipped — useful for fixtures
    where the BR walk's full-deck enumeration is too slow (deep-stack
    turn). The strategy-diff oracle still gates correctness.
    """
    canonical_dict = _solve_with_env(
        cfg, iterations, p0_holes, p1_holes, rayon=False, monkeypatch=monkeypatch
    )
    rayon_dict = _solve_with_env(
        cfg, iterations, p0_holes, p1_holes, rayon=True, monkeypatch=monkeypatch
    )

    canonical_strategy = _strategy_for_diff(canonical_dict)
    rayon_strategy = _strategy_for_diff(rayon_dict)

    # Both backends must populate the SAME set of infoset keys.
    canonical_keys = set(canonical_strategy.keys())
    rayon_keys = set(rayon_strategy.keys())
    only_in_canonical = canonical_keys - rayon_keys
    only_in_rayon = rayon_keys - canonical_keys
    assert not only_in_canonical and not only_in_rayon, (
        f"[{name}] infoset key set drift: "
        f"only_in_canonical={list(only_in_canonical)[:3]} "
        f"only_in_rayon={list(only_in_rayon)[:3]}"
    )

    # NaN guard — the canonical path is already covered by other tests,
    # but the parallel path's reduction order could in principle produce
    # NaN if a thread returns one. Cheap defensive check.
    for k, probs in rayon_strategy.items():
        for p in probs:
            assert p == p and -1e9 < p < 1e9, (  # NaN check via reflexivity
                f"[{name}] parallel path produced invalid prob {p} at key {k!r}"
            )

    # Strategy-diff oracle: largest per-action probability deviation.
    # Bit-identical → 0; chance-sum reordering → bounded by float roundoff.
    prob_diff = _max_prob_diff(canonical_strategy, rayon_strategy)
    print(
        f"\n[{name}] max prob diff = {prob_diff:.3e}",
    )
    # Informational threshold — large drift (>1e-4) indicates a deeper
    # bug than sum-reorder. Sum-reorder typically produces ~1e-15.
    assert prob_diff < 1e-4, (
        f"[{name}] per-action probability drift {prob_diff:.3e} exceeds "
        f"1e-4 — suggests a bug, not just chance-sum reordering"
    )

    if skip_br_walk:
        return

    # Compute exploitability on BOTH strategies under the SAME walk.
    canonical_expl, canonical_gv = _exploit_walk(cfg, canonical_strategy)
    rayon_expl, rayon_gv = _exploit_walk(cfg, rayon_strategy)

    expl_delta = abs(canonical_expl - rayon_expl)
    gv_delta = abs(canonical_gv - rayon_gv)
    print(
        f"[{name}] expl: canonical={canonical_expl:.10f} rayon={rayon_expl:.10f} "
        f"Δ={expl_delta:.3e} (tol={_EXPL_TOL:.0e}); "
        f"gv: canonical={canonical_gv:.10f} rayon={rayon_gv:.10f} "
        f"Δ={gv_delta:.3e} (tol={_GV_TOL:.0e})"
    )
    assert expl_delta <= _EXPL_TOL, (
        f"[{name}] exploitability divergence: "
        f"canonical={canonical_expl:.10f} rayon={rayon_expl:.10f} "
        f"Δ={expl_delta:.3e} > tol={_EXPL_TOL:.0e}"
    )
    assert gv_delta <= _GV_TOL, (
        f"[{name}] game_value divergence: "
        f"canonical={canonical_gv:.10f} rayon={rayon_gv:.10f} "
        f"Δ={gv_delta:.3e} > tol={_GV_TOL:.0e}"
    )


# ---------------------------------------------------------------------------
# F1-F4: river chance-enum fixtures (1 vs 2 bet sizes; uniform vs short-solve)
# ---------------------------------------------------------------------------
#
# River has NO chance node at the betting-tree root (the betting tree
# starts at a decision node — the bet/check root). The parallel walker
# falls through to the sequential path here per
# `solve_one_traverse`'s structural check, so the parallel and canonical
# outputs are BIT-IDENTICAL on river fixtures. Diff tolerance is the
# loose 1e-6 / 1e-9 anyway — these fixtures still gate the regression
# (parallel-mode dispatch must not corrupt the fall-through).


def test_f1_river_minimal_uniform(monkeypatch):
    """F1 river: 1 bet size, raise cap 1, 5 hands per side, 50 iters."""
    cfg = _river_mini_cfg((1.0,), 1)
    board = list(cfg.initial_board)
    holes = _pick_n_disjoint_hands(board, 5)
    _assert_parallel_matches_canonical(
        cfg, iterations=50, p0_holes=holes, p1_holes=holes, name="F1 river-mini-uniform", monkeypatch=monkeypatch
    )


def test_f2_river_two_sizes(monkeypatch):
    """F2 river: 2 bet sizes, raise cap 3, 5 hands per side, 50 iters."""
    cfg = _river_mini_cfg((0.5, 1.0), 3)
    board = list(cfg.initial_board)
    holes = _pick_n_disjoint_hands(board, 5)
    _assert_parallel_matches_canonical(
        cfg, iterations=50, p0_holes=holes, p1_holes=holes, name="F2 river-2size", monkeypatch=monkeypatch
    )


def test_f3_river_minimal_short_solve(monkeypatch):
    """F3 river: 1 bet size, longer solve (200 iters) to amplify any drift."""
    cfg = _river_mini_cfg((1.0,), 1)
    board = list(cfg.initial_board)
    holes = _pick_n_disjoint_hands(board, 5)
    _assert_parallel_matches_canonical(
        cfg, iterations=200, p0_holes=holes, p1_holes=holes, name="F3 river-mini-200iter", monkeypatch=monkeypatch
    )


def test_f4_river_two_sizes_short_solve(monkeypatch):
    """F4 river: 2 bet sizes + raise cap 3 + 200 iters."""
    cfg = _river_mini_cfg((0.5, 1.0), 3)
    board = list(cfg.initial_board)
    holes = _pick_n_disjoint_hands(board, 5)
    _assert_parallel_matches_canonical(
        cfg, iterations=200, p0_holes=holes, p1_holes=holes, name="F4 river-2size-200iter", monkeypatch=monkeypatch
    )


# ---------------------------------------------------------------------------
# F5-F8: turn chance-enum fixtures (the rayon-active path)
# ---------------------------------------------------------------------------
#
# Turn has 45 river-card chance children at the betting-tree root. THIS
# is where parallel mode actually kicks in — `solve_one_traverse`
# detects the multi-child Chance root and dispatches to
# `parallel_traverse_chance`. The output WILL drift from bit-identical
# due to chance-sum reordering; the 1e-6 / 1e-9 tolerance absorbs this.


def test_f5_turn_minimal_uniform(monkeypatch):
    """F5 turn: 1 bet size, raise cap 1, 4 hands per side, 30 iters.

    Small hand-count keeps the diff test under a minute. The 45-card
    river chance subtree is what gets parallelized.
    """
    cfg = _turn_mini_cfg((1.0,), 1, 1000)
    board = list(cfg.initial_board)
    holes = _pick_n_disjoint_hands(board, 4)
    _assert_parallel_matches_canonical(
        cfg, iterations=30, p0_holes=holes, p1_holes=holes, name="F5 turn-mini-uniform", monkeypatch=monkeypatch
    )


def test_f6_turn_minimal_short_solve(monkeypatch):
    """F6 turn: 1 bet size, longer solve (100 iters)."""
    cfg = _turn_mini_cfg((1.0,), 1, 1000)
    board = list(cfg.initial_board)
    holes = _pick_n_disjoint_hands(board, 4)
    _assert_parallel_matches_canonical(
        cfg, iterations=100, p0_holes=holes, p1_holes=holes, name="F6 turn-mini-100iter", monkeypatch=monkeypatch
    )


def test_f7_turn_two_sizes(monkeypatch):
    """F7 turn: 2 bet sizes, raise cap 2, 3 hands per side, 30 iters."""
    cfg = _turn_mini_cfg((0.5, 1.0), 2, 1000)
    board = list(cfg.initial_board)
    holes = _pick_n_disjoint_hands(board, 3)
    _assert_parallel_matches_canonical(
        cfg, iterations=30, p0_holes=holes, p1_holes=holes, name="F7 turn-2size", monkeypatch=monkeypatch
    )


def test_f8_turn_deep_stack(monkeypatch):
    """F8 turn (W2.3-shaped): deep stack (200 BB = 20000 chips), 1 bet size.

    Skips the BR walk because deep-stack turn config produces a
    multi-thousand-node betting tree, and `_rust.compute_exploitability`
    enumerates the full deck (1081 hands × full tree) which takes
    minutes per call. The strategy-diff oracle (max per-action
    probability deviation) is sufficient to gate correctness — if
    parallel mode were producing different infoset updates than
    canonical mode, we'd see prob_diff >> 1e-4.
    """
    cfg = _turn_mini_cfg((1.0,), 1, 20000)
    board = list(cfg.initial_board)
    holes = _pick_n_disjoint_hands(board, 3)
    _assert_parallel_matches_canonical(
        cfg, iterations=30, p0_holes=holes, p1_holes=holes, name="F8 turn-deep-stack",
        monkeypatch=monkeypatch, skip_br_walk=True,
    )


# ---------------------------------------------------------------------------
# Smoke: NaN / panic guard end-to-end
# ---------------------------------------------------------------------------


def test_parallel_path_does_not_panic_on_min_fixture(monkeypatch):
    """Smallest viable fixture: turn, 1 bet size, raise cap 1, 3 hands, 5 iters.

    Pure smoke test that the parallel dispatch path doesn't panic or
    return garbage on the tiniest input. Mostly a regression guard for
    the disjoint-shard `split_at_mut` code in
    `dcfr_vector_parallel::parallel_traverse_chance`.
    """
    monkeypatch.setenv("CFR_RAYON_CHANCE", "1")
    cfg = _turn_mini_cfg((1.0,), 1, 1000)
    board = list(cfg.initial_board)
    holes = _pick_n_disjoint_hands(board, 3)
    config_json = _serialize_hunl_config(cfg)
    t0 = time.perf_counter()
    out = _rust_solve_rvr(config_json, 5, 1.5, 0.0, 2.0, holes, holes)
    elapsed = time.perf_counter() - t0
    assert "average_strategy" in out
    assert len(out["average_strategy"]) > 0, "parallel path produced empty strategy"
    assert elapsed < 30.0, f"parallel smoke test took {elapsed:.2f}s — perf regression suspected"
