"""Premium-A top-level solver router (Phase 5, task #68).

This module is the **single entry point** the UI (Phase 6) and downstream
applications use to "solve a spot". The router inspects the request and
dispatches to one of four backends:

  1. **Blueprint lookup** — instant (<10 ms). Used when the request is a
     preflop spot at a stock stack depth + canonical action menu + no
     per-combo range override. Reads a precomputed shard via
     :class:`poker_solver.blueprint_loader.BlueprintLoader`.

  2. **Stack-depth interpolation** — fast (<50 ms). Used when the
     blueprint has no exact-depth shard for the request, but flanking
     depths exist (e.g. user asks for 67 BB; blueprint has 60 + 80).
     Loads both flanks and linearly blends per-cell via
     :func:`poker_solver.blueprint_interp.interpolate_strategy`.

  3. **Custom live-solve** — slow (seconds to minutes). Used when the
     request carries:
       - a per-combo :class:`Range` override (B10 — user-edited intensities),
       - a non-canonical action menu (different open sizes / 3-bet
         multipliers / raise-cap), or
       - a non-standard ante config (outside the blueprint's grid).
     Falls through to the Rust 1326-combo CFR via
     ``_rust.solve_hunl_preflop_rvr``.

  4. **Postflop subgame** — minutes. Used when the request carries a
     postflop board (3/4/5 cards). Delegates to
     :func:`poker_solver.blueprint_subgame.solve_postflop_from_blueprint`
     (Phase 4) — that pipeline does the preflop blueprint lookup +
     1326-expansion + postflop Nash solve internally.

## Mental model: decision tree

::

    .solve(...)
    ├── board has 3-5 cards?         → postflop_subgame  (route 4)
    ├── range_override provided?     → custom_live_solve (route 3)
    ├── non-canonical action menu?   → custom_live_solve (route 3)
    ├── non-standard ante?           → custom_live_solve (route 3)
    ├── blueprint has exact shard?   → blueprint_lookup  (route 1)
    ├── blueprint has flanking shards? → interpolated     (route 2)
    └── otherwise                     → custom_live_solve (route 3)

The router is **pure orchestration** — it never touches the blueprint
asset format, the Rust engine internals, or the postflop solver
internals. Everything routes through public APIs that Phases 1-4 ship.

## Why a separate module, not extending the loader?

The loader is the lowest layer of the read-side stack. It serves
*shards*; it knows nothing about action menus, ante semantics, or the
existence of a live-solve fallback. The router sits one layer above:
it inspects the user's *spot description* and decides which lower-layer
to engage. Keeping the layering clean means:

  - Tests for the loader stay focused on shard semantics.
  - Tests for the router stay focused on dispatch semantics.
  - Phase 6's UI consumes the router (one import surface) instead of
    composing four lower modules itself.

## Performance contract

  - **Route 1 (blueprint_lookup)**: median wall < 10 ms (cold cache:
    one disk read; warm cache: dict-only). Verified by
    ``tests/test_solver_router.py::test_blueprint_route_under_10ms``.
  - **Route 2 (interpolated)**: median wall < 50 ms (two cold shard
    reads + per-cell linear blend over ~50 infosets × 169 classes).
    Verified by ``tests/test_solver_router.py::test_interp_route_under_50ms``.
  - **Routes 3/4**: wall time is solver-bound; the router records
    ``wall_seconds`` for the caller's information but enforces no
    upper bound.

## Concurrency

Single-threaded. The underlying loader is single-threaded by contract;
the router holds no additional state besides a reference to the loader
and the canonical-menu spec.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

import numpy as np

from poker_solver.blueprint import BlueprintConfig
from poker_solver.blueprint_interp import (
    InterpolationError,
    interpolate_strategy,
)
from poker_solver.blueprint_loader import (
    BlueprintKey,
    BlueprintLoader,
    BlueprintLookupError,
    normalize_action_history,
    normalize_ante,
)
from poker_solver.blueprint_subgame import (
    BlueprintPostflopResult,
    solve_postflop_from_blueprint,
)
from poker_solver.card import Card
from poker_solver.hunl import HUNLConfig, Street
from poker_solver.range import Range

__all__ = [
    "ActionMenu",
    "DEFAULT_MENU",
    "RouteDecision",
    "SolveResult",
    "SolverRouter",
    "SpotDescription",
]


# ---------------------------------------------------------------------------
# Canonical action menu (matches Phase 1 blueprint generation defaults)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ActionMenu:
    """Canonical preflop action menu.

    Matches the Phase 1 blueprint generator defaults — opens at
    {2, 3, 4, 5} BB, 3-bet multipliers at {2, 3, 4, 5}x, raise cap 4.

    Two menus are *canonical-equivalent* (i.e. served by the blueprint)
    when every field matches the blueprint shard's ``config`` block.
    Any deviation triggers the custom live-solve route.
    """

    preflop_open_sizes_bb: tuple[float, ...] = (2.0, 3.0, 4.0, 5.0)
    preflop_reraise_multipliers: tuple[float, ...] = (2.0, 3.0, 4.0, 5.0)
    preflop_raise_cap: int = 4

    def matches(self, config: BlueprintConfig) -> bool:
        """Whether this menu matches a blueprint shard's config."""
        return (
            tuple(self.preflop_open_sizes_bb)
            == tuple(config.preflop_open_sizes_bb)
            and tuple(self.preflop_reraise_multipliers)
            == tuple(config.preflop_reraise_multipliers)
            and int(self.preflop_raise_cap) == int(config.preflop_raise_cap)
        )


#: The default action menu — matches the Phase 1 blueprint generator.
DEFAULT_MENU = ActionMenu()


# ---------------------------------------------------------------------------
# Spot description + result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SpotDescription:
    """User-facing spot to solve.

    Fields:

      ``stack_bb``
        Effective stack depth in BB. May land on or between blueprint
        grid points.

      ``ante``
        ``"none" | "half" | "full"`` or a float BB value.

      ``action_history``
        Engine token sequence reaching the decision (``""`` = SB root).
        Empty string with no board = preflop SB-root decision.

      ``hand``
        169-class label (e.g. ``"AA"``, ``"AKs"``, ``"72o"``). Required
        for the lookup / interpolation routes; the live-solve route
        produces strategies for all 169 classes and the result's
        ``strategy`` is filtered to this class.

      ``board``
        Postflop board cards (3/4/5 cards). Empty = preflop spot.

      ``range_override``
        Optional per-combo :class:`Range` (B10 user-edited intensities).
        When provided, forces the custom live-solve route — the
        blueprint cannot represent per-combo non-uniformity within a
        class.

      ``action_menu``
        :class:`ActionMenu`. Defaults to :data:`DEFAULT_MENU` (matches
        the blueprint's canonical menu). Any deviation forces the
        custom live-solve route.

      ``hero_player``
        0 (SB / aggressor) or 1 (BB / defender). Default 0.
    """

    stack_bb: int
    ante: str | float | int = "none"
    action_history: str = ""
    hand: str | None = None
    board: tuple[Card, ...] = ()
    range_override: Range | None = None
    action_menu: ActionMenu = DEFAULT_MENU
    hero_player: int = 0


#: Route taken by the router for a given request. Used by callers + the
#: UI to display "served instantly" / "live solved" badges.
RouteDecision = Literal[
    "blueprint_lookup", "interpolated", "custom_live_solve", "postflop_subgame"
]

#: Confidence level on the served strategy. Maps 1:1 to route today, but
#: kept separate so a future "interpolation with quality flag" can
#: refine the field without breaking callers that read ``.route``.
Confidence = Literal["exact", "interpolated", "live_solved"]


@dataclass
class SolveResult:
    """Outcome of a router-dispatched solve.

    Carries:

      ``route``
        Which backend served the request.

      ``confidence``
        ``"exact"`` (blueprint hit), ``"interpolated"`` (depth blend),
        or ``"live_solved"`` (engine ran).

      ``strategy``
        Action distribution at the requested infoset. Shape depends on
        route:
          - Lookup / interp: per-hand action probs (length matches
            ``actions``).
          - Live solve: full 169-class strategy at the root decision.
          - Postflop subgame: ``None`` here — see ``.postflop`` for the
            ``RangeVsRangeNashResult``.

      ``actions``
        Action labels aligned with ``strategy`` (e.g. ``["fold", "call",
        "open_to_300", "all_in"]``).

      ``wall_seconds``
        End-to-end wall time the router spent on this request, including
        any dispatch + lookup overhead.

      ``postflop``
        ``BlueprintPostflopResult`` when ``route == "postflop_subgame"``.
        ``None`` otherwise.

      ``meta``
        Free-form route-specific metadata (e.g. which two depths were
        blended; which infoset was found; how long the underlying solve
        ran). Tests + UIs read this; calling code generally does not.
    """

    route: RouteDecision
    confidence: Confidence
    strategy: np.ndarray | None
    actions: list[str] | None
    wall_seconds: float
    postflop: BlueprintPostflopResult | None = None
    meta: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


@dataclass
class SolverRouter:
    """Top-level router dispatching ``solve(...)`` to one of four backends.

    Construction:

    >>> router = SolverRouter.from_dir("assets/blueprints/")  # doctest: +SKIP

    Or pass a pre-built loader:

    >>> loader = BlueprintLoader.from_dir("assets/blueprints/")  # doctest: +SKIP
    >>> router = SolverRouter(loader=loader)  # doctest: +SKIP

    The router holds:

      ``loader``
        The blueprint loader, used for routes 1, 2, 4.

      ``config_template``
        ``HUNLConfig`` template used by the live-solve + postflop
        routes. Defaults to a 100-BB symmetric preflop template; the
        router overrides stack depth + ante per-request.

      ``live_solve_iterations``
        DCFR iterations for the custom live-solve path. Default 5_000
        (a reasonable trade-off between convergence and wall time for
        an interactive UI). Tests use a low value for speed.

      ``equity_table_path``
        Path to the 169x169 preflop equity table. Resolved lazily.
    """

    loader: BlueprintLoader
    config_template: HUNLConfig | None = None
    live_solve_iterations: int = 5_000
    equity_table_path: str | None = None

    @classmethod
    def from_dir(
        cls,
        blueprint_dir: str | Path,
        *,
        config_template: HUNLConfig | None = None,
        live_solve_iterations: int = 5_000,
        equity_table_path: str | None = None,
        verify_sha256: bool = True,
    ) -> SolverRouter:
        """Construct a router from a directory of blueprint shards."""
        loader = BlueprintLoader.from_dir(
            blueprint_dir, verify_sha256=verify_sha256
        )
        return cls(
            loader=loader,
            config_template=config_template,
            live_solve_iterations=live_solve_iterations,
            equity_table_path=equity_table_path,
        )

    # ------------------------------------------------------------------
    # Public solve surface
    # ------------------------------------------------------------------

    def solve(
        self,
        *,
        stack_bb: int,
        ante: str | float | int = "none",
        action_history: str = "",
        hand: str | None = None,
        board: Sequence[Card] = (),
        range_override: Range | None = None,
        action_menu: ActionMenu = DEFAULT_MENU,
        hero_player: int = 0,
        force_route: RouteDecision | None = None,
    ) -> SolveResult:
        """Solve a spot, dispatching to the appropriate backend.

        See module docstring for the dispatch logic. ``force_route``
        bypasses the decision tree and routes directly to the named
        backend — useful for testing the threshold logic without
        gaming the inputs to land on a specific route.

        Raises:
            BlueprintLookupError: structural input errors (bad ante
                token, malformed action history, hand not in
                blueprint's class set).
            ValueError: ``board`` length not in ``{0, 3, 4, 5}``;
                ``hero_player`` not in ``{0, 1}``; ``stack_bb`` < 2.
        """
        # ---- Input validation ----------------------------------------
        if hero_player not in (0, 1):
            raise ValueError(
                f"hero_player must be 0 (SB/aggressor) or 1 (BB/defender); "
                f"got {hero_player!r}"
            )
        if stack_bb < 2:
            raise ValueError(
                f"stack_bb must be >= 2 (otherwise the SB cannot post); "
                f"got {stack_bb!r}"
            )
        board_t = tuple(board)
        n_board = len(board_t)
        if n_board not in (0, 3, 4, 5):
            raise ValueError(
                f"board must be empty (preflop) or 3/4/5 cards (flop/turn/"
                f"river); got {n_board} cards: {list(board_t)!r}"
            )
        normalized_ante = normalize_ante(ante)
        # Normalize history early so downstream layers receive a clean
        # key. We accept either bare-suffix or fully-prefixed input.
        history_key = normalize_action_history(action_history)

        spot = SpotDescription(
            stack_bb=int(stack_bb),
            ante=ante,
            action_history=history_key,
            hand=hand,
            board=board_t,
            range_override=range_override,
            action_menu=action_menu,
            hero_player=hero_player,
        )

        # ---- Dispatch ------------------------------------------------
        t_start = time.perf_counter()
        if force_route is not None:
            chosen_route: RouteDecision = force_route
        else:
            chosen_route = self._decide_route(spot, normalized_ante)

        if chosen_route == "postflop_subgame":
            result = self._route_postflop(spot)
        elif chosen_route == "blueprint_lookup":
            result = self._route_blueprint_lookup(spot, normalized_ante)
        elif chosen_route == "interpolated":
            result = self._route_interpolated(spot, normalized_ante)
        else:
            result = self._route_live_solve(spot, normalized_ante)

        # Stamp the wall time from the router's perspective (covers any
        # dispatch overhead beyond what the inner routes recorded).
        result.wall_seconds = time.perf_counter() - t_start
        return result

    # ------------------------------------------------------------------
    # Decision logic
    # ------------------------------------------------------------------

    def _decide_route(
        self, spot: SpotDescription, normalized_ante: float
    ) -> RouteDecision:
        """Return the route that should serve ``spot``.

        Priority order (highest first):

          1. Board present → postflop subgame.
          2. Range override OR non-canonical menu OR non-standard ante
             → custom live-solve (blueprint can't represent it).
          3. Blueprint has exact shard → blueprint lookup.
          4. Blueprint has flanking shards → interpolated.
          5. Otherwise (no flanking neighbors either) → custom live-solve.
        """
        # Rule 1: postflop board → postflop subgame.
        if len(spot.board) > 0:
            return "postflop_subgame"

        # Rule 2: anything that the blueprint format can't represent
        # forces the live-solve route.
        if spot.range_override is not None:
            return "custom_live_solve"
        if not self._menu_matches_blueprint(spot.action_menu, normalized_ante):
            return "custom_live_solve"

        # Rule 3: exact shard match → instant lookup.
        if self.loader.has_shard(spot.stack_bb, normalized_ante):
            return "blueprint_lookup"

        # Rule 4: flanking shards available → interpolation.
        depths = self.loader.available_depths(ante=normalized_ante)
        if len(depths) >= 2:
            lo = min(depths)
            hi = max(depths)
            if lo <= spot.stack_bb <= hi:
                return "interpolated"

        # Rule 5: nothing the blueprint can serve → live-solve.
        return "custom_live_solve"

    def _menu_matches_blueprint(
        self, menu: ActionMenu, normalized_ante: float
    ) -> bool:
        """Whether the requested menu matches the blueprint's canonical menu.

        We require an *exact* match on open sizes, 3-bet multipliers, and
        raise cap. Any deviation (different sizings, different cap)
        forces the live-solve route — interpolating across mismatched
        action menus is nonsensical (a 7-action vector and a 5-action
        vector are not blendable).

        Implementation: we compare ``menu`` to the first available shard
        for this ante. All shards within a blueprint share the same
        menu, so checking one suffices. If no shards exist for this
        ante, the menu can't match (and the live-solve path is what we
        want anyway).
        """
        # Find any shard that matches the ante.
        for entry in self.loader.manifest.entries:
            try:
                entry_ante = float(entry.ante_bb)
            except (TypeError, ValueError):
                continue
            if abs(entry_ante - normalized_ante) > 1e-6:
                continue
            # Load the shard (will hit cache after the first request).
            try:
                key = BlueprintKey(stack_bb=entry.stack_bb, ante_bb=entry.ante_bb)
                bp = self.loader._load_shard(key)
            except Exception:  # noqa: BLE001 — defensive: skip if shard broken
                continue
            return menu.matches(bp.config)
        return False

    # ------------------------------------------------------------------
    # Route implementations
    # ------------------------------------------------------------------

    def _route_blueprint_lookup(
        self, spot: SpotDescription, normalized_ante: float
    ) -> SolveResult:
        """Route 1: direct shard lookup."""
        if spot.hand is None:
            raise BlueprintLookupError(
                "hand must be provided for blueprint_lookup route; "
                "to look up an entire infoset, call loader.lookup directly."
            )
        probs = self.loader.lookup(
            stack_bb=spot.stack_bb,
            ante=normalized_ante,
            hand=spot.hand,
            action_history=spot.action_history,
        )
        actions = self.loader.actions(
            stack_bb=spot.stack_bb,
            ante=normalized_ante,
            action_history=spot.action_history,
        )
        meta: dict[str, Any] = {
            "shard": {"stack_bb": spot.stack_bb, "ante_bb": normalized_ante},
            "infoset": spot.action_history,
            "hand": spot.hand,
        }
        if probs is None:
            # The shard exists per the dispatch logic, but the infoset /
            # hand is missing. Return an empty strategy + the dispatch
            # decision so the caller sees the route chosen and can fall
            # back at the application layer.
            meta["miss_reason"] = "infoset_or_hand_absent_in_shard"
            return SolveResult(
                route="blueprint_lookup",
                confidence="exact",
                strategy=None,
                actions=actions,
                wall_seconds=0.0,
                meta=meta,
            )
        return SolveResult(
            route="blueprint_lookup",
            confidence="exact",
            strategy=probs,
            actions=actions,
            wall_seconds=0.0,
            meta=meta,
        )

    def _route_interpolated(
        self, spot: SpotDescription, normalized_ante: float
    ) -> SolveResult:
        """Route 2: linear-blend two flanking shards."""
        if spot.hand is None:
            raise BlueprintLookupError(
                "hand must be provided for interpolated route; to "
                "interpolate an entire infoset, use blueprint_interp."
            )
        depths = self.loader.available_depths(ante=normalized_ante)
        if not depths:
            # Should have been caught by _decide_route, but defend.
            raise BlueprintLookupError(
                f"no blueprint shards available at ante {normalized_ante!r}; "
                "interpolated route cannot be served"
            )

        # Find the flanking depths and load both shards. (We load BOTH
        # eagerly so the per-cell blend has both sides available.)
        d_lo, d_hi = _flanking_depths(depths, spot.stack_bb)

        bp_lo = self.loader._load_shard(
            BlueprintKey(stack_bb=int(d_lo), ante_bb=normalized_ante)
        )
        bp_hi = self.loader._load_shard(
            BlueprintKey(stack_bb=int(d_hi), ante_bb=normalized_ante)
        )

        # Per-cell extraction.
        info_lo = bp_lo.infosets.get(spot.action_history)
        info_hi = bp_hi.infosets.get(spot.action_history)
        meta: dict[str, Any] = {
            "depths": (int(d_lo), int(d_hi)),
            "infoset": spot.action_history,
            "hand": spot.hand,
        }
        if info_lo is None or info_hi is None:
            # Same logic as Layer-2 miss in the loader.
            meta["miss_reason"] = "infoset_absent_in_one_or_both_flanks"
            return SolveResult(
                route="interpolated",
                confidence="interpolated",
                strategy=None,
                actions=None,
                wall_seconds=0.0,
                meta=meta,
            )
        v_lo = info_lo["strategy"].get(spot.hand)
        v_hi = info_hi["strategy"].get(spot.hand)
        if v_lo is None or v_hi is None:
            meta["miss_reason"] = "hand_absent_in_one_or_both_flanks"
            return SolveResult(
                route="interpolated",
                confidence="interpolated",
                strategy=None,
                actions=info_lo.get("actions"),
                wall_seconds=0.0,
                meta=meta,
            )

        # Action menus must match for the blend to be meaningful — we
        # already gated that with ``_menu_matches_blueprint`` at the
        # dispatch level, but double-check at the per-infoset level
        # because some advanced configs could have different action
        # menus at different infosets (e.g. ante-induced size shifts).
        try:
            blended = interpolate_strategy(
                target_bb=float(spot.stack_bb),
                strategies={float(d_lo): v_lo, float(d_hi): v_hi},
                method="linear",
            )
        except InterpolationError as e:
            meta["miss_reason"] = f"interpolation_error: {e}"
            return SolveResult(
                route="interpolated",
                confidence="interpolated",
                strategy=None,
                actions=info_lo.get("actions"),
                wall_seconds=0.0,
                meta=meta,
            )
        return SolveResult(
            route="interpolated",
            confidence="interpolated",
            strategy=np.asarray(blended, dtype=np.float64),
            actions=list(info_lo.get("actions", [])),
            wall_seconds=0.0,
            meta=meta,
        )

    def _route_postflop(self, spot: SpotDescription) -> SolveResult:
        """Route 4: blueprint -> 1326-expand -> postflop solve."""
        # Pick a blueprint to ground the postflop solve. Prefer the
        # exact stack/ante shard; fall back to the closest available.
        normalized_ante = normalize_ante(spot.ante)
        if self.loader.has_shard(spot.stack_bb, normalized_ante):
            key = BlueprintKey(stack_bb=spot.stack_bb, ante_bb=normalized_ante)
        else:
            depths = self.loader.available_depths(ante=normalized_ante)
            if not depths:
                raise BlueprintLookupError(
                    f"no blueprint shards available at ante "
                    f"{normalized_ante!r}; postflop subgame route requires "
                    "a blueprint to derive continuation ranges"
                )
            # Snap to closest depth.
            closest = min(depths, key=lambda d: abs(d - spot.stack_bb))
            key = BlueprintKey(stack_bb=int(closest), ante_bb=normalized_ante)

        blueprint = self.loader._load_shard(key)

        # Build a config template at the *blueprint's* stack depth so
        # the subgame's tree shape matches the blueprint's tree shape.
        # (Using spot.stack_bb when it disagrees with the shard would
        # produce wrong reach products at the SB-root infoset.)
        cfg_template = self._build_config_template(
            stack_bb=key.stack_bb, ante=normalized_ante, menu=spot.action_menu
        )

        # Convert the normalized history key to a token sequence the
        # postflop pipeline understands. The blueprint subgame walks
        # tokens (``"b300"``, ``"c"``, etc.), not the history key.
        tokens = _history_key_to_tokens(spot.action_history)

        try:
            postflop_result = solve_postflop_from_blueprint(
                blueprint,
                config_template=cfg_template,
                action_sequence=tokens,
                board=spot.board,
                hero_player=spot.hero_player,
                iterations=max(50, self.live_solve_iterations // 10),
            )
        except ValueError as e:
            # Surface a clean failure: empty continuation range, bad
            # action sequence, etc. The router still returns a
            # SolveResult so the caller can inspect ``meta``.
            return SolveResult(
                route="postflop_subgame",
                confidence="live_solved",
                strategy=None,
                actions=None,
                wall_seconds=0.0,
                postflop=None,
                meta={
                    "shard": {"stack_bb": key.stack_bb, "ante_bb": key.ante_bb},
                    "tokens": tokens,
                    "board": [str(c) for c in spot.board],
                    "error": str(e),
                },
            )

        return SolveResult(
            route="postflop_subgame",
            confidence="live_solved",
            strategy=None,
            actions=None,
            wall_seconds=postflop_result.wall_time_total_s,
            postflop=postflop_result,
            meta={
                "shard": {"stack_bb": key.stack_bb, "ante_bb": key.ante_bb},
                "tokens": tokens,
                "board": [str(c) for c in spot.board],
                "wall_lookup_s": postflop_result.wall_time_lookup_s,
                "wall_expand_s": postflop_result.wall_time_expand_s,
                "wall_solve_s": postflop_result.wall_time_solve_s,
            },
        )

    def _route_live_solve(
        self, spot: SpotDescription, normalized_ante: float
    ) -> SolveResult:
        """Route 3: custom live-solve via the Rust 1326-combo CFR.

        Used when the blueprint cannot represent the request (range
        override, non-canonical menu, non-standard ante, or no
        flanking shards). Calls
        ``_rust.solve_hunl_preflop_rvr`` and aggregates the result to
        the requested hand class.
        """
        # Build the engine config from the request.
        cfg = self._build_hunl_config(
            stack_bb=spot.stack_bb, ante=normalized_ante, menu=spot.action_menu
        )
        from poker_solver.hunl import _serialize_hunl_config

        config_json = _serialize_hunl_config(cfg)

        try:
            from poker_solver import _rust  # type: ignore[attr-defined]
        except ImportError as e:
            raise RuntimeError(
                f"poker_solver._rust unavailable ({e}); custom live-solve "
                "route requires the Rust extension. Rebuild via "
                "`maturin develop --release`."
            ) from e

        rust_solver = getattr(_rust, "solve_hunl_preflop_rvr", None)
        if rust_solver is None:
            raise RuntimeError(
                "poker_solver._rust.solve_hunl_preflop_rvr is missing. "
                "Rebuild via `maturin develop --release`."
            )

        equity_table_path = self.equity_table_path or _default_equity_table_path()

        # Range-override (B10) plumbing: when the user provided a per-
        # combo range, we restrict the engine's hole-card enumeration
        # for the relevant player. The other player runs full 1326.
        p0_holes, p1_holes = _holes_from_range_override(
            spot.range_override, spot.hero_player
        )

        t_solve_start = time.perf_counter()
        raw = rust_solver(
            config_json,
            equity_table_path,
            self.live_solve_iterations,
            float(spot.action_menu.preflop_open_sizes_bb and 1.5 or 1.5),  # alpha
            0.0,  # beta
            2.0,  # gamma
            list(spot.action_menu.preflop_open_sizes_bb),
            list(spot.action_menu.preflop_reraise_multipliers),
            p0_holes,
            p1_holes,
        )
        t_solve_end = time.perf_counter()
        average_strategy = {k: list(v) for k, v in raw["average_strategy"].items()}

        # Aggregate to the requested hand class at the requested infoset.
        # The engine emits keys like ``"<hole>||p|<history>"``. We
        # pull all combos belonging to ``spot.hand`` at ``spot.action_history``
        # and combo-weighted-average them.
        if spot.hand is None:
            # No hand requested → return the raw average_strategy under meta.
            return SolveResult(
                route="custom_live_solve",
                confidence="live_solved",
                strategy=None,
                actions=None,
                wall_seconds=t_solve_end - t_solve_start,
                meta={
                    "iterations": self.live_solve_iterations,
                    "engine": "solve_hunl_preflop_rvr",
                    "average_strategy_size": len(average_strategy),
                    "infoset": spot.action_history,
                },
            )

        strategy, actions = _aggregate_live_solve_to_class(
            average_strategy=average_strategy,
            target_class=spot.hand,
            history_key=spot.action_history,
            menu=spot.action_menu,
            cfg=cfg,
        )
        return SolveResult(
            route="custom_live_solve",
            confidence="live_solved",
            strategy=strategy,
            actions=actions,
            wall_seconds=t_solve_end - t_solve_start,
            meta={
                "iterations": self.live_solve_iterations,
                "engine": "solve_hunl_preflop_rvr",
                "infoset": spot.action_history,
                "hand": spot.hand,
                "range_override_active": spot.range_override is not None,
            },
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_config_template(
        self, *, stack_bb: int, ante: float, menu: ActionMenu
    ) -> HUNLConfig:
        """Return a preflop ``HUNLConfig`` for the requested cell."""
        if self.config_template is not None:
            return replace(
                self.config_template,
                starting_stack=stack_bb * 100,
                ante=int(round(ante * 100)),
                preflop_raise_cap=menu.preflop_raise_cap,
                starting_street=Street.PREFLOP,
                initial_hole_cards=(),
            )
        return HUNLConfig(
            starting_stack=stack_bb * 100,
            small_blind=50,
            big_blind=100,
            ante=int(round(ante * 100)),
            starting_street=Street.PREFLOP,
            preflop_raise_cap=menu.preflop_raise_cap,
        )

    def _build_hunl_config(
        self, *, stack_bb: int, ante: float, menu: ActionMenu
    ) -> HUNLConfig:
        """Alias to ``_build_config_template`` — the engine config IS the
        template at preflop start. Kept as a named method so the
        live-solve path's intent reads clearly.
        """
        return self._build_config_template(
            stack_bb=stack_bb, ante=ante, menu=menu
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _flanking_depths(
    depths: Sequence[int], target: int
) -> tuple[int, int]:
    """Return the two grid depths flanking ``target``.

    Mirrors :func:`blueprint_interp.find_flanking_depths` but keeps
    everything integer-typed (depths are ints in BB, not floats).
    """
    sorted_depths = sorted(depths)
    if not sorted_depths:
        raise ValueError("depths must be non-empty for flanking lookup")
    if target <= sorted_depths[0]:
        return (sorted_depths[0], sorted_depths[0])
    if target >= sorted_depths[-1]:
        return (sorted_depths[-1], sorted_depths[-1])
    for i in range(len(sorted_depths) - 1):
        if sorted_depths[i] <= target <= sorted_depths[i + 1]:
            return (sorted_depths[i], sorted_depths[i + 1])
    # Unreachable — defensive.
    raise ValueError(
        f"could not locate flanking depths for {target} in {sorted_depths!r}"
    )


def _history_key_to_tokens(history_key: str) -> tuple[str, ...]:
    """Convert a normalized history key to engine token tuple.

    The blueprint stores ``"||p|<tokens>"``. The postflop pipeline wants
    a tuple of tokens (``("b300", "c")``). This helper reverses the
    serialization.

    Empty history (SB root) returns an empty tuple.
    """
    if history_key in ("", "||p|"):
        return ()
    body = (
        history_key[len("||p|") :]
        if history_key.startswith("||p|")
        else history_key
    )
    tokens: list[str] = []
    i = 0
    while i < len(body):
        c = body[i]
        if c in "fcxA":
            tokens.append(c)
            i += 1
        elif c in "br":
            j = i + 1
            while j < len(body) and body[j].isdigit():
                j += 1
            if j == i + 1:
                # Malformed; bail to whatever we've accumulated.
                break
            tokens.append(body[i:j])
            i = j
        else:
            # Should never happen — normalize_action_history rejects
            # bad alphabets upstream. Defensive.
            break
    return tuple(tokens)


def _default_equity_table_path() -> str:
    """Locate the shipped 169x169 preflop equity table.

    Mirrors :func:`poker_solver.blueprint._equity_table_path`.
    """
    here = Path(__file__).resolve().parent
    candidate = here.parent / "assets" / "preflop_equity_169x169.npz"
    return str(candidate)


def _holes_from_range_override(
    range_override: Range | None, hero_player: int
) -> tuple[list[list[int]] | None, list[list[int]] | None]:
    """Map a per-combo Range override to the engine's hole-card arguments.

    The Rust engine accepts optional ``p0_holes`` / ``p1_holes`` arguments
    that restrict each player's combo enumeration. ``None`` = full 1326.
    Each "hole" is a 2-element list of integer card IDs (per
    :func:`poker_solver.card.card_to_int`).

    Returns ``(p0_holes, p1_holes)``. The non-hero player runs full 1326.

    NOTE: per-combo weight (B10) is not yet propagated to the engine —
    we only restrict the combo enumeration. Weighted live-solve is a
    follow-up (the engine kernel needs a vector input path). For now,
    a Range override with non-uniform weights produces a uniform-within-
    enumeration live solve — strictly better than blueprint
    interpolation (which can't represent per-combo variation at all)
    but not yet full B10 fidelity.
    """
    if range_override is None:
        return (None, None)
    from poker_solver.card import card_to_int

    holes_list: list[list[int]] = []
    for combo in range_override:
        c0, c1 = combo.cards
        holes_list.append([card_to_int(c0), card_to_int(c1)])
    if hero_player == 0:
        return (holes_list, None)
    return (None, holes_list)


def _aggregate_live_solve_to_class(
    *,
    average_strategy: dict[str, list[float]],
    target_class: str,
    history_key: str,
    menu: ActionMenu,
    cfg: HUNLConfig,
) -> tuple[np.ndarray | None, list[str] | None]:
    """Aggregate the engine's per-combo average strategy to a 169-class.

    The engine emits keys ``"<hole>||p|<history>"``. We accumulate the
    per-action probability across every combo that maps to
    ``target_class`` at the infoset matching ``history_key``, then
    uniform-average. Action labels are reconstructed via
    :func:`poker_solver.blueprint.reconstruct_action_labels_per_infoset`.

    Returns ``(strategy, actions)`` or ``(None, None)`` if the engine
    emitted no rows at the requested infoset for this class.
    """
    from poker_solver.blueprint import reconstruct_action_labels_per_infoset
    from poker_solver.card import Card as CardCls
    from poker_solver.range_aggregator import _combo_to_hand_class

    # The engine's keys use ``<hole>||p|<history>`` (no trailing pipe).
    # ``history_key`` is normalized to ``||p|<body>``.
    if history_key.startswith("||p|"):
        history_body = history_key[len("||p|") :]
    else:
        history_body = history_key
    engine_suffix = f"||p|{history_body}"

    matched_rows: list[list[float]] = []
    for key, probs in average_strategy.items():
        if not key.endswith(engine_suffix):
            continue
        hole_str = key[: -len(engine_suffix)]
        if len(hole_str) != 4:
            continue
        try:
            c0 = CardCls.from_str(hole_str[:2])
            c1 = CardCls.from_str(hole_str[2:])
        except Exception:  # noqa: BLE001 — engine keys can vary
            continue
        cls = _combo_to_hand_class((c0, c1))
        if cls != target_class:
            continue
        matched_rows.append(list(probs))

    if not matched_rows:
        return (None, None)

    # Uniform average across combos in this class (matches the engine's
    # combo-uniform-within-class assumption).
    n_actions = len(matched_rows[0])
    aggregated = [
        sum(row[i] for row in matched_rows) / len(matched_rows)
        for i in range(n_actions)
    ]
    strategy = np.asarray(aggregated, dtype=np.float64)

    # Reconstruct action labels for this infoset.
    labels_per_infoset = reconstruct_action_labels_per_infoset(
        average_strategy,
        preflop_open_sizes_bb=menu.preflop_open_sizes_bb,
        preflop_reraise_multipliers=menu.preflop_reraise_multipliers,
        big_blind=cfg.big_blind,
        small_blind=cfg.small_blind,
        ante=cfg.ante,
        starting_stack=cfg.starting_stack,
        preflop_raise_cap=cfg.preflop_raise_cap,
    )
    # The reconstruct helper keys on the engine's history key (with
    # trailing pipe). Try both flavors.
    for candidate in (engine_suffix, f"{engine_suffix}|"):
        if candidate in labels_per_infoset:
            return (strategy, list(labels_per_infoset[candidate]))
    # No labels found — return strategy with synthetic labels so the
    # caller can still render the result.
    return (strategy, [f"a{i}" for i in range(n_actions)])
