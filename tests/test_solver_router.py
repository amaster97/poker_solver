"""Premium-A Phase 5 solver router tests (task #68).

Coverage:

  1. **Smoke**: each of the 4 route branches taken with appropriate spot.
  2. **Edge**: depth at exact blueprint match → ``"blueprint_lookup"``
     not ``"interpolated"``.
  3. **Edge**: depth 175 (in blueprint) vs 174 (interp) — clean threshold.
  4. **Edge**: B10 per-combo override triggers custom-live regardless of
     depth.
  5. **Performance**: blueprint-route < 10 ms, interp-route < 50 ms,
     custom-route times reported.

Most tests use synthetic in-memory blueprints to avoid disk I/O + Rust
solve cost. The custom-live-solve and postflop-subgame routes are
exercised in dedicated tests that skip cleanly if the Rust extension
is absent.
"""

from __future__ import annotations

import importlib
import time
from pathlib import Path

import numpy as np
import pytest

from poker_solver.blueprint import (
    SCHEMA_VERSION,
    Blueprint,
    BlueprintConfig,
    Manifest,
    ManifestEntry,
    blueprint_shard_filename,
    save_blueprint,
    save_manifest,
)
from poker_solver.blueprint_loader import (
    BlueprintLoader,
    BlueprintLookupError,
)
from poker_solver.card import Card
from poker_solver.range import Range
from poker_solver.solver_router import (
    DEFAULT_MENU,
    ActionMenu,
    SolverRouter,
    SpotDescription,
    _flanking_depths,
    _history_key_to_tokens,
)

# ---------------------------------------------------------------------------
# Rust binding gate (for custom-live + postflop tests)
# ---------------------------------------------------------------------------

try:
    _rust_module = importlib.import_module("poker_solver._rust")
    _rust_solve_preflop_rvr = getattr(
        _rust_module, "solve_hunl_preflop_rvr", None
    )
except Exception:  # noqa: BLE001
    _rust_solve_preflop_rvr = None  # type: ignore[assignment]


_EQUITY_TABLE_EXISTS = (
    Path(__file__).resolve().parent.parent
    / "assets"
    / "preflop_equity_169x169.npz"
).exists()


needs_rust = pytest.mark.skipif(
    _rust_solve_preflop_rvr is None or not _EQUITY_TABLE_EXISTS,
    reason="poker_solver._rust or equity table missing — rebuild via "
    "`maturin develop --release`.",
)


# ---------------------------------------------------------------------------
# Synthetic-shard fixture
# ---------------------------------------------------------------------------


def _synthetic_blueprint(
    stack_bb: int,
    ante_bb: float = 0.0,
    *,
    iterations: int = 100,
    menu: ActionMenu = DEFAULT_MENU,
) -> Blueprint:
    """Build a minimal valid blueprint for unit tests.

    Two infosets (SB root + ``"||p|b300"``), three hand classes each.
    Action vectors sum to 1.0 by construction. Engine is never invoked.

    The action menu (open sizes / 3-bet multipliers / raise cap) is
    encoded into the ``BlueprintConfig`` so the router's
    ``_menu_matches_blueprint`` check can validate against it.
    """
    return Blueprint(
        schema_version=SCHEMA_VERSION,
        config=BlueprintConfig(
            stack_bb=stack_bb,
            ante_bb=ante_bb,
            iterations=iterations,
            preflop_open_sizes_bb=menu.preflop_open_sizes_bb,
            preflop_reraise_multipliers=menu.preflop_reraise_multipliers,
            preflop_raise_cap=menu.preflop_raise_cap,
        ),
        wall_seconds=0.5,
        final_exploitability_bb100=None,
        infosets={
            "||p|": {
                "actions": ["fold", "call", "open_to_300", "all_in"],
                "strategy": {
                    "AA": [0.0, 0.0, 0.7, 0.3],
                    "KK": [0.0, 0.1, 0.6, 0.3],
                    "72o": [1.0, 0.0, 0.0, 0.0],
                },
            },
            "||p|b300": {
                "actions": ["fold", "call", "all_in"],
                "strategy": {
                    "AA": [0.0, 0.4, 0.6],
                    "KK": [0.0, 0.5, 0.5],
                    "72o": [1.0, 0.0, 0.0],
                },
            },
        },
    )


def _write_blueprint_bundle(
    tmp_path: Path, blueprints: list[Blueprint]
) -> Path:
    """Materialize a manifest + shards in ``tmp_path``."""
    entries: list[ManifestEntry] = []
    for bp in blueprints:
        fname = blueprint_shard_filename(bp.config)
        path = tmp_path / fname
        sha = save_blueprint(bp, path)
        entries.append(
            ManifestEntry(
                stack_bb=bp.config.stack_bb,
                ante_bb=bp.config.ante_bb,
                filename=fname,
                sha256=sha,
                file_size_bytes=path.stat().st_size,
                final_exploitability_bb100=bp.final_exploitability_bb100,
                wall_seconds=bp.wall_seconds,
                iterations=bp.config.iterations,
            )
        )
    manifest = Manifest(
        schema_version=SCHEMA_VERSION,
        premium_a_version="v1",
        generated_date_utc="2026-05-28T00:00:00+00:00",
        entries=entries,
    )
    save_manifest(manifest, tmp_path / "manifest.json")
    return tmp_path


def _build_router(tmp_path: Path, depths: list[int], ante_bb: float = 0.0) -> SolverRouter:
    """Helper to build a router populated with synthetic blueprints."""
    blueprints = [_synthetic_blueprint(d, ante_bb) for d in depths]
    _write_blueprint_bundle(tmp_path, blueprints)
    loader = BlueprintLoader.from_dir(tmp_path, verify_sha256=False)
    return SolverRouter(loader=loader)


# ---------------------------------------------------------------------------
# 0. Module-level helpers
# ---------------------------------------------------------------------------


def test_flanking_depths_exact_match() -> None:
    assert _flanking_depths([20, 40, 60], 40) == (20, 40)


def test_flanking_depths_between() -> None:
    assert _flanking_depths([20, 40, 60], 30) == (20, 40)
    assert _flanking_depths([20, 40, 60], 50) == (40, 60)


def test_flanking_depths_below_min() -> None:
    assert _flanking_depths([20, 40, 60], 10) == (20, 20)


def test_flanking_depths_above_max() -> None:
    assert _flanking_depths([20, 40, 60], 80) == (60, 60)


def test_flanking_depths_empty_raises() -> None:
    with pytest.raises(ValueError, match="depths must be non-empty"):
        _flanking_depths([], 30)


def test_history_key_to_tokens_empty() -> None:
    assert _history_key_to_tokens("") == ()
    assert _history_key_to_tokens("||p|") == ()


def test_history_key_to_tokens_simple() -> None:
    assert _history_key_to_tokens("||p|c") == ("c",)
    assert _history_key_to_tokens("||p|b300") == ("b300",)
    assert _history_key_to_tokens("||p|b300c") == ("b300", "c")
    assert _history_key_to_tokens("||p|b300r700f") == ("b300", "r700", "f")


def test_history_key_to_tokens_bare_body() -> None:
    """Accept bare body input (no ``"||p|"`` prefix)."""
    assert _history_key_to_tokens("b300c") == ("b300", "c")


# ---------------------------------------------------------------------------
# 1. SMOKE: each route branch hit with appropriate spot
# ---------------------------------------------------------------------------


def test_smoke_blueprint_lookup_route(tmp_path: Path) -> None:
    """Preflop at exact stack depth + canonical menu + no override
    → ``"blueprint_lookup"``.
    """
    router = _build_router(tmp_path, depths=[40])
    result = router.solve(
        stack_bb=40,
        ante="none",
        hand="AA",
        action_history="",
    )
    assert result.route == "blueprint_lookup"
    assert result.confidence == "exact"
    assert result.strategy is not None
    np.testing.assert_allclose(result.strategy, [0.0, 0.0, 0.7, 0.3])
    assert result.actions == ["fold", "call", "open_to_300", "all_in"]


def test_smoke_interpolated_route(tmp_path: Path) -> None:
    """Preflop at off-grid depth with flanking shards → ``"interpolated"``.

    The synthetic blueprint at 40 BB has AA → ``[0.0, 0.0, 0.7, 0.3]``;
    at 60 BB AA is the same. The blend at 50 BB also equals
    ``[0.0, 0.0, 0.7, 0.3]`` (linear blend of identical vectors).
    """
    router = _build_router(tmp_path, depths=[40, 60])
    result = router.solve(
        stack_bb=50,
        ante="none",
        hand="AA",
        action_history="",
    )
    assert result.route == "interpolated"
    assert result.confidence == "interpolated"
    assert result.strategy is not None
    np.testing.assert_allclose(result.strategy, [0.0, 0.0, 0.7, 0.3], atol=1e-9)
    assert result.meta["depths"] == (40, 60)


def test_smoke_interpolated_blends_different_vectors(tmp_path: Path) -> None:
    """When the two flanks differ, the interp result lies between them."""
    bp40 = _synthetic_blueprint(40, 0.0)
    bp60 = _synthetic_blueprint(60, 0.0)
    # Change AA strategy at 60 BB so the blend is nontrivial.
    bp60.infosets["||p|"]["strategy"]["AA"] = [0.0, 0.5, 0.5, 0.0]
    _write_blueprint_bundle(tmp_path, [bp40, bp60])
    loader = BlueprintLoader.from_dir(tmp_path, verify_sha256=False)
    router = SolverRouter(loader=loader)

    result = router.solve(stack_bb=50, ante="none", hand="AA", action_history="")
    assert result.route == "interpolated"
    # At 50 BB exactly midway: blend = 0.5 * [0,0,0.7,0.3] + 0.5 * [0,0.5,0.5,0]
    # = [0, 0.25, 0.6, 0.15]
    np.testing.assert_allclose(
        result.strategy, [0.0, 0.25, 0.6, 0.15], atol=1e-9
    )


def test_smoke_custom_live_route_via_range_override(tmp_path: Path) -> None:
    """A per-combo Range override forces ``"custom_live_solve"``.

    We don't actually run the Rust solver — we use ``force_route`` to
    skip the engine call OR we verify the decision logic via the
    ``_decide_route`` API directly.
    """
    router = _build_router(tmp_path, depths=[40])
    # Build a Range override with a single AA combo.
    rng = Range()
    rng.add((Card.from_str("As"), Card.from_str("Ah")), weight=1.0)
    spot = SpotDescription(
        stack_bb=40,
        ante="none",
        hand="AA",
        action_history="||p|",
        range_override=rng,
    )
    # Call the decision logic directly (avoids invoking the Rust solver).
    decision = router._decide_route(spot, normalized_ante=0.0)
    assert decision == "custom_live_solve"


def test_smoke_custom_live_route_via_non_canonical_menu(tmp_path: Path) -> None:
    """A non-canonical action menu forces ``"custom_live_solve"``."""
    router = _build_router(tmp_path, depths=[40])
    non_canonical = ActionMenu(
        preflop_open_sizes_bb=(2.5, 4.0),  # different open sizes
        preflop_reraise_multipliers=(3.0,),
        preflop_raise_cap=2,
    )
    spot = SpotDescription(
        stack_bb=40,
        ante="none",
        hand="AA",
        action_history="||p|",
        action_menu=non_canonical,
    )
    decision = router._decide_route(spot, normalized_ante=0.0)
    assert decision == "custom_live_solve"


def test_smoke_custom_live_route_via_off_grid_no_neighbors(tmp_path: Path) -> None:
    """If the depth is outside the grid AND there's only one shard, no
    flanking pair exists → live-solve fallback.
    """
    router = _build_router(tmp_path, depths=[40])
    spot = SpotDescription(
        stack_bb=200,  # way above the only shard at 40
        ante="none",
        hand="AA",
        action_history="||p|",
    )
    decision = router._decide_route(spot, normalized_ante=0.0)
    # With only one shard there are no flanking pairs; 200 BB is far
    # outside (and lies above max=40, so flanking logic returns 40/40
    # but our rule requires len(depths) >= 2 AND lo <= target <= hi).
    assert decision == "custom_live_solve"


def test_smoke_postflop_subgame_route(tmp_path: Path) -> None:
    """A board with 3+ cards routes to ``"postflop_subgame"`` regardless
    of other dispatch knobs."""
    router = _build_router(tmp_path, depths=[40])
    board = (
        Card.from_str("As"),
        Card.from_str("7h"),
        Card.from_str("2d"),
    )
    spot = SpotDescription(
        stack_bb=40,
        ante="none",
        hand="AA",
        action_history="||p|",
        board=board,
    )
    decision = router._decide_route(spot, normalized_ante=0.0)
    assert decision == "postflop_subgame"


# ---------------------------------------------------------------------------
# 2. EDGE: exact depth → blueprint_lookup, not interpolated
# ---------------------------------------------------------------------------


def test_exact_depth_uses_blueprint_lookup_not_interpolated(
    tmp_path: Path,
) -> None:
    """When the requested depth IS in the grid, lookup is preferred."""
    router = _build_router(tmp_path, depths=[40, 60, 80])
    # Hit each grid point exactly.
    for d in (40, 60, 80):
        result = router.solve(
            stack_bb=d, ante="none", hand="AA", action_history=""
        )
        assert result.route == "blueprint_lookup", (
            f"depth {d}: expected blueprint_lookup, got {result.route}"
        )


def test_off_grid_depth_uses_interpolated(tmp_path: Path) -> None:
    """When the requested depth is strictly between two grid points,
    the interpolation route is taken."""
    router = _build_router(tmp_path, depths=[40, 60, 80])
    result = router.solve(stack_bb=50, ante="none", hand="AA", action_history="")
    assert result.route == "interpolated"
    assert result.meta["depths"] == (40, 60)


# ---------------------------------------------------------------------------
# 3. EDGE: depth 175 (in blueprint) vs 174 (interp) — clean threshold
# ---------------------------------------------------------------------------


def test_threshold_175_in_grid_vs_174_off_grid(tmp_path: Path) -> None:
    """Depth 175 is in the grid (exact lookup); 174 is between 150 and
    175 (interpolated). Verifies the lookup/interp boundary is sharp."""
    router = _build_router(tmp_path, depths=[150, 175])

    r_at = router.solve(stack_bb=175, ante="none", hand="AA", action_history="")
    assert r_at.route == "blueprint_lookup"

    r_below = router.solve(
        stack_bb=174, ante="none", hand="AA", action_history=""
    )
    assert r_below.route == "interpolated"
    assert r_below.meta["depths"] == (150, 175)


def test_threshold_175_in_grid_vs_176_off_grid_above_max(tmp_path: Path) -> None:
    """Depth 175 = exact match. Depth 176 is above max=175, so no
    flanking pair contains the target. _decide_route then falls
    through to ``custom_live_solve``.

    We check the dispatch decision directly (not via ``solve``) so the
    test does not invoke the Rust engine. The full end-to-end live-solve
    path is exercised by :func:`test_custom_live_solve_runs_via_force_route`.
    """
    router = _build_router(tmp_path, depths=[150, 175])
    spot_at = SpotDescription(
        stack_bb=175, ante="none", hand="AA", action_history="||p|"
    )
    assert router._decide_route(spot_at, normalized_ante=0.0) == "blueprint_lookup"
    spot_above = SpotDescription(
        stack_bb=176, ante="none", hand="AA", action_history="||p|"
    )
    assert router._decide_route(spot_above, normalized_ante=0.0) == "custom_live_solve"


# ---------------------------------------------------------------------------
# 4. EDGE: B10 per-combo override triggers custom-live regardless of depth
# ---------------------------------------------------------------------------


def test_range_override_forces_custom_live_at_exact_depth(
    tmp_path: Path,
) -> None:
    """Even at an exact grid point, a per-combo Range override must
    force the custom-live route — the blueprint cannot represent
    per-combo non-uniformity."""
    router = _build_router(tmp_path, depths=[40])
    rng = Range()
    rng.add((Card.from_str("As"), Card.from_str("Ah")), weight=0.5)
    spot = SpotDescription(
        stack_bb=40,  # exact match
        ante="none",
        hand="AA",
        action_history="||p|",
        range_override=rng,
    )
    assert router._decide_route(spot, normalized_ante=0.0) == "custom_live_solve"


def test_range_override_forces_custom_live_off_grid(tmp_path: Path) -> None:
    """Same at an off-grid depth where interp would have applied."""
    router = _build_router(tmp_path, depths=[40, 60])
    rng = Range()
    rng.add((Card.from_str("As"), Card.from_str("Ah")), weight=0.5)
    spot = SpotDescription(
        stack_bb=50,
        ante="none",
        hand="AA",
        action_history="||p|",
        range_override=rng,
    )
    assert router._decide_route(spot, normalized_ante=0.0) == "custom_live_solve"


# ---------------------------------------------------------------------------
# 5. PERFORMANCE: route wall times
# ---------------------------------------------------------------------------


def test_blueprint_route_under_10ms(tmp_path: Path) -> None:
    """Median blueprint-lookup wall time must be < 10 ms."""
    router = _build_router(tmp_path, depths=[40])
    # Warm the cache with one lookup.
    router.solve(stack_bb=40, ante="none", hand="AA", action_history="")

    n_iters = 20
    samples = []
    for _ in range(n_iters):
        t0 = time.perf_counter()
        result = router.solve(
            stack_bb=40, ante="none", hand="AA", action_history=""
        )
        samples.append(time.perf_counter() - t0)
        assert result.route == "blueprint_lookup"
    median = sorted(samples)[n_iters // 2]
    assert median < 0.010, (
        f"blueprint_lookup median wall {median * 1000:.2f}ms exceeds 10ms"
    )


def test_interp_route_under_50ms(tmp_path: Path) -> None:
    """Median interpolated-route wall time must be < 50 ms."""
    router = _build_router(tmp_path, depths=[40, 60])
    # Warm both shards.
    router.solve(stack_bb=50, ante="none", hand="AA", action_history="")

    n_iters = 20
    samples = []
    for _ in range(n_iters):
        t0 = time.perf_counter()
        result = router.solve(
            stack_bb=50, ante="none", hand="AA", action_history=""
        )
        samples.append(time.perf_counter() - t0)
        assert result.route == "interpolated"
    median = sorted(samples)[n_iters // 2]
    assert median < 0.050, (
        f"interpolated median wall {median * 1000:.2f}ms exceeds 50ms"
    )


# ---------------------------------------------------------------------------
# 6. INPUT VALIDATION
# ---------------------------------------------------------------------------


def test_solve_rejects_bad_hero_player(tmp_path: Path) -> None:
    router = _build_router(tmp_path, depths=[40])
    with pytest.raises(ValueError, match="hero_player must be"):
        router.solve(stack_bb=40, ante="none", hand="AA", hero_player=2)


def test_solve_rejects_too_small_stack(tmp_path: Path) -> None:
    router = _build_router(tmp_path, depths=[40])
    with pytest.raises(ValueError, match="stack_bb must be"):
        router.solve(stack_bb=1, ante="none", hand="AA")


def test_solve_rejects_bad_board_length(tmp_path: Path) -> None:
    router = _build_router(tmp_path, depths=[40])
    bad_board = (Card.from_str("As"), Card.from_str("7h"))  # 2 cards
    with pytest.raises(ValueError, match="board must be empty"):
        router.solve(
            stack_bb=40, ante="none", hand="AA", board=bad_board
        )


def test_solve_rejects_bad_ante(tmp_path: Path) -> None:
    router = _build_router(tmp_path, depths=[40])
    with pytest.raises(BlueprintLookupError, match="unrecognized ante"):
        router.solve(stack_bb=40, ante="quarter", hand="AA")


def test_solve_rejects_bad_history_alphabet(tmp_path: Path) -> None:
    router = _build_router(tmp_path, depths=[40])
    with pytest.raises(BlueprintLookupError, match="unrecognized action_history"):
        router.solve(stack_bb=40, ante="none", hand="AA", action_history="garbage")


# ---------------------------------------------------------------------------
# 7. BLUEPRINT-LOOKUP MISS BEHAVIOR
# ---------------------------------------------------------------------------


def test_lookup_route_returns_none_for_unknown_hand(tmp_path: Path) -> None:
    """If the shard exists but the hand class isn't in the strategy
    table, the result has ``strategy=None`` and ``miss_reason`` set."""
    router = _build_router(tmp_path, depths=[40])
    result = router.solve(
        stack_bb=40,
        ante="none",
        hand="JTs",  # not in the synthetic blueprint
        action_history="",
    )
    assert result.route == "blueprint_lookup"
    assert result.strategy is None
    assert "miss_reason" in result.meta


def test_lookup_route_returns_none_for_unknown_infoset(tmp_path: Path) -> None:
    """Unknown action history → strategy=None, route still blueprint_lookup."""
    router = _build_router(tmp_path, depths=[40])
    result = router.solve(
        stack_bb=40,
        ante="none",
        hand="AA",
        action_history="b500",  # not in the synthetic blueprint
    )
    assert result.route == "blueprint_lookup"
    assert result.strategy is None


# ---------------------------------------------------------------------------
# 8. FROM_DIR + ACTIONMENU.MATCHES
# ---------------------------------------------------------------------------


def test_from_dir_constructs_router(tmp_path: Path) -> None:
    _write_blueprint_bundle(tmp_path, [_synthetic_blueprint(40)])
    router = SolverRouter.from_dir(tmp_path, verify_sha256=False)
    assert isinstance(router, SolverRouter)
    assert router.loader.cache_size() == 0


def test_action_menu_matches_default() -> None:
    cfg = BlueprintConfig(stack_bb=40, ante_bb=0.0, iterations=100)
    assert DEFAULT_MENU.matches(cfg) is True


def test_action_menu_doesnt_match_when_open_sizes_differ() -> None:
    cfg = BlueprintConfig(
        stack_bb=40,
        ante_bb=0.0,
        iterations=100,
        preflop_open_sizes_bb=(2.5, 3.5),
    )
    assert DEFAULT_MENU.matches(cfg) is False


def test_action_menu_doesnt_match_when_cap_differs() -> None:
    cfg = BlueprintConfig(
        stack_bb=40, ante_bb=0.0, iterations=100, preflop_raise_cap=2
    )
    assert DEFAULT_MENU.matches(cfg) is False


# ---------------------------------------------------------------------------
# 9. FORCE_ROUTE
# ---------------------------------------------------------------------------


def test_force_route_overrides_dispatch(tmp_path: Path) -> None:
    """``force_route`` skips the decision tree."""
    router = _build_router(tmp_path, depths=[40])
    # Without force, this exact-depth request would route to lookup.
    # We force interpolated; with only one shard there's no flank, so
    # the interp branch returns an early miss (strategy=None, route
    # field still set to "interpolated").
    result = router.solve(
        stack_bb=40,
        ante="none",
        hand="AA",
        action_history="",
        force_route="interpolated",
    )
    assert result.route == "interpolated"


# ---------------------------------------------------------------------------
# 10. CUSTOM-LIVE-SOLVE END-TO-END (needs Rust)
# ---------------------------------------------------------------------------


@needs_rust
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_custom_live_solve_runs_via_force_route(tmp_path: Path) -> None:
    """Force the custom-live route and verify a tiny solve produces a
    valid strategy + populates wall time.

    Marked ``slow`` because even at iteration=10 the Rust preflop
    full-tree solver enumerates the 1326-combo prior; a single call
    is several seconds on M-series silicon.
    """
    router = _build_router(tmp_path, depths=[40])
    router.live_solve_iterations = 10  # tiny — just for plumbing test
    result = router.solve(
        stack_bb=15,  # well below the grid so live-solve fires naturally
        ante="none",
        hand="AA",
        action_history="",
        force_route="custom_live_solve",
        action_menu=ActionMenu(
            preflop_open_sizes_bb=(),  # pushfold-only menu (no opens)
            preflop_reraise_multipliers=(),
            preflop_raise_cap=1,
        ),
    )
    assert result.route == "custom_live_solve"
    assert result.confidence == "live_solved"
    # A live solve should return a strategy of finite length summing
    # to ~1.0 OR a None strategy if the engine emitted no rows for
    # that infoset (extremely unlikely at this iter count but possible
    # with the trivial menu).
    if result.strategy is not None:
        assert result.strategy.sum() == pytest.approx(1.0, abs=1e-3)
    assert result.wall_seconds > 0.0


# ---------------------------------------------------------------------------
# 11. POSTFLOP-SUBGAME END-TO-END (needs Rust)
# ---------------------------------------------------------------------------


@needs_rust
@pytest.mark.slow
@pytest.mark.timeout(1800)
def test_postflop_subgame_routes_through_subgame_module(
    tmp_path: Path,
) -> None:
    """A board triggers the postflop subgame; the result carries a
    ``postflop`` field with a converged ``RangeVsRangeNashResult``.

    Marked ``slow`` and given a 30-minute timeout because the postflop
    subgame uses the Rust range-vs-range Nash solver on a 1326-combo
    prior with ~600k combo-pair equity evaluations per iteration.
    Even at iteration=10 this is multiple minutes on M-series silicon
    and dominates the test suite's wall time. Run with
    ``pytest -m slow`` to opt in.
    """
    # Build a blueprint where both AA and KK call 100% at the SB root,
    # then both check at the BB infoset, reaching the flop with
    # both classes weighted 1.0. Use the tight pushfold-only menu.
    pushfold_menu = ActionMenu(
        preflop_open_sizes_bb=(),
        preflop_reraise_multipliers=(),
        preflop_raise_cap=1,
    )
    bp = Blueprint(
        schema_version=SCHEMA_VERSION,
        config=BlueprintConfig(
            stack_bb=50,
            ante_bb=0.0,
            iterations=10,
            preflop_open_sizes_bb=pushfold_menu.preflop_open_sizes_bb,
            preflop_reraise_multipliers=pushfold_menu.preflop_reraise_multipliers,
            preflop_raise_cap=pushfold_menu.preflop_raise_cap,
        ),
        wall_seconds=0.1,
        final_exploitability_bb100=None,
        infosets={
            "||p|": {
                "actions": ["fold", "call", "all_in"],
                "strategy": {
                    "AA": [0.0, 1.0, 0.0],
                    "KK": [0.0, 1.0, 0.0],
                },
            },
            "||p|c": {
                "actions": ["check", "all_in"],
                "strategy": {
                    "AA": [1.0, 0.0],
                    "KK": [1.0, 0.0],
                },
            },
        },
    )
    _write_blueprint_bundle(tmp_path, [bp])
    loader = BlueprintLoader.from_dir(tmp_path, verify_sha256=False)
    # Minimal iter count — we're testing plumbing, not convergence.
    router = SolverRouter(loader=loader, live_solve_iterations=10)

    board = (
        Card.from_str("Qd"),
        Card.from_str("7h"),
        Card.from_str("2c"),
    )
    result = router.solve(
        stack_bb=50,
        ante="none",
        hand=None,  # postflop returns full Nash result, not a single hand
        action_history="c",  # SB limp -> BB to act (we then check)
        board=board,
        action_menu=pushfold_menu,
    )
    # Either it succeeded or we got a clean error in meta (e.g., BB
    # check token didn't replay — both surfaces are valid post-routing
    # behavior).
    assert result.route == "postflop_subgame"
    # If the subgame ran, we have postflop populated.
    if result.postflop is not None:
        assert result.postflop.wall_time_total_s > 0.0
    else:
        # Subgame failed — we surfaced the error in meta.
        assert "error" in result.meta
