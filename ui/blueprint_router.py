"""UI-local Premium-A blueprint router (Phase 6, task #68).

This module is a THIN consumer-side wrapper that the UI layer uses to
look up preflop strategies from the Premium-A blueprint asset bundle
shipped by Phase 1 + Phase 2. It encapsulates the routing decision:

  1. EXACT — the user's ``(stack_bb, ante)`` matches a shard in the
     manifest. We load that shard and return its strategy directly.
  2. INTERPOLATED — the user's ``stack_bb`` falls between two anchor
     depths. We load both flanks and call
     :func:`poker_solver.blueprint_interp.interpolate_strategy` on
     the per-class vectors.
  3. LIVE — no blueprint coverage (out-of-range depth, unknown action
     history, or no asset bundle at all). The caller falls back to the
     existing live solve path (``_rust.solve_hunl_preflop_rvr``).

## Why this lives in ``ui/`` and not ``poker_solver/``

Phase 5 (``poker_solver.solver_router.SolverRouter``) is being built in
parallel. When that lands, this module's ``BlueprintRouteResult`` +
``route(...)`` semantics should be replaced by ``SolverRouter.solve(...)``
(see the TODO at the bottom of this file). We keep the router thin so
the swap is a 1-file change.

## Public API

  - :class:`SourceLabel` — enum of route sources (``blueprint`` /
    ``interpolated`` / ``live``).
  - :class:`RouteInfo` — what a UI badge needs to render: source label,
    wall time, confidence text, and the actual strategy payload.
  - :class:`BlueprintRouter.from_asset_dir` — construct from a
    ``manifest.json`` directory; returns ``None`` if no bundle is
    available so the UI can fall back gracefully.
  - :meth:`BlueprintRouter.lookup_class` — per-class lookup with
    fallback to interpolation.
  - :func:`describe_route` — render a ``RouteInfo`` as a single-line
    badge string the UI can stick under a chart.

## TODO (Phase 5 follow-up)

When ``poker_solver.solver_router.SolverRouter`` is merged, replace
``BlueprintRouter.lookup_class`` with ``SolverRouter.solve(...)`` and
keep this module purely as a thin UI adapter that converts the router's
return value into a :class:`RouteInfo`.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


__all__ = [
    "SourceLabel",
    "RouteInfo",
    "BlueprintRouter",
    "describe_route",
    "default_asset_dir",
]


class SourceLabel(str, Enum):
    """Where a strategy came from — drives the source badge in the UI."""

    BLUEPRINT = "blueprint"
    INTERPOLATED = "interpolated"
    LIVE = "live"
    UNAVAILABLE = "unavailable"


@dataclass
class RouteInfo:
    """Routing metadata + payload returned by a router lookup.

    The UI renders this as a small badge under the chart so the user
    can see at a glance whether the displayed strategy came from a
    precomputed asset (instant), an interpolation across two anchors
    (instant), or a live solve (seconds-to-minutes). The numeric ``wall_time_s``
    answers the inevitable "why did this take 5 seconds" question.

    The payload itself is in ``per_class``: a dict mapping each
    169-class label to a dict of ``{action_label: probability}``.
    """

    source: SourceLabel
    wall_time_s: float
    confidence: str  # human-readable: "exact" / "interpolated 70BB->60/80" / "live N iter"
    per_class: dict[str, dict[str, float]] = field(default_factory=dict)
    # Optional extras for downstream rendering / debugging.
    stack_bb: int = 0
    ante_bb: float = 0.0
    action_history: str = ""
    error: str | None = None  # set when source == UNAVAILABLE
    # ``anchor_depths`` is populated when source == INTERPOLATED; tells
    # the user which two shards were blended.
    anchor_depths: tuple[int, int] | None = None


def default_asset_dir() -> Path:
    """Return the standard on-disk location for the blueprint bundle.

    Mirrors ``scripts/generate_preflop_blueprint.py``'s default output
    directory. Callers should pass a custom path when testing.
    """
    repo_root = Path(__file__).resolve().parents[1]
    return repo_root / "assets" / "blueprints"


def describe_route(info: RouteInfo) -> str:
    """Render a one-line human-readable label for ``RouteInfo``.

    Used by the source-badge widget in the chart + chained tabs. Format:

      ``[source] confidence (wall N.NNs)``

    Example outputs:

      ``[blueprint] exact 100BB / no-ante (wall 0.001s)``
      ``[interpolated] 67BB between 60/80 (wall 0.003s)``
      ``[live] 500 iter rust_preflop_rvr (wall 5.21s)``
      ``[unavailable] no blueprint bundle on disk``
    """
    if info.source == SourceLabel.UNAVAILABLE:
        return f"[{info.source.value}] {info.error or 'no data'}"
    return (
        f"[{info.source.value}] {info.confidence} "
        f"(wall {info.wall_time_s:.3f}s)"
    )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


@dataclass
class BlueprintRouter:
    """Thin facade over :class:`BlueprintLoader` + interp.

    Instances are constructed via :meth:`from_asset_dir`; passing
    ``None`` (or pointing at a missing dir) returns ``None`` so the UI
    can detect the no-bundle case at startup and surface the "live
    only" badge in its chart subtitle.
    """

    loader: Any  # poker_solver.blueprint_loader.BlueprintLoader

    # -- Construction -------------------------------------------------------

    @classmethod
    def from_asset_dir(cls, asset_dir: str | Path | None = None) -> BlueprintRouter | None:
        """Construct from an asset directory containing ``manifest.json``.

        Returns ``None`` if the directory does not exist, lacks a
        ``manifest.json``, or fails to load. Errors are logged at INFO
        (not ERROR) — a missing bundle is expected on dev machines and
        is NOT a failure mode for the consumer.
        """
        from poker_solver.blueprint_loader import BlueprintLoader

        path = Path(asset_dir) if asset_dir else default_asset_dir()
        manifest_path = path / "manifest.json"
        if not manifest_path.exists():
            logger.info(
                "blueprint_router: no manifest.json at %s; live-solve only",
                path,
            )
            return None
        try:
            loader = BlueprintLoader.from_dir(path)
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            logger.info(
                "blueprint_router: failed to load %s: %s; live-solve only",
                manifest_path,
                exc,
            )
            return None
        return cls(loader=loader)

    # -- Discovery ----------------------------------------------------------

    def available_depths(self, ante: str | float | int | None = None) -> list[int]:
        """Sorted depths covered by the bundle at this ante (or any ante)."""
        return list(self.loader.available_depths(ante))

    def has_exact_shard(self, stack_bb: int, ante: str | float | int) -> bool:
        """Whether ``(stack_bb, ante)`` is an exact shard match."""
        return bool(self.loader.has_shard(stack_bb, ante))

    # -- Routing decision ---------------------------------------------------

    def route_label(
        self, *, stack_bb: int, ante: str | float | int
    ) -> tuple[SourceLabel, tuple[int, int] | None]:
        """Decide the route source without doing any work.

        Returns ``(source, anchor_depths)`` where ``anchor_depths`` is
        the flanking ``(lo, hi)`` pair if interpolation will be used,
        else ``None``. The caller can prefetch the anchor shards using
        this metadata.
        """
        if self.has_exact_shard(stack_bb, ante):
            return SourceLabel.BLUEPRINT, None
        depths = self.available_depths(ante=ante)
        if not depths:
            return SourceLabel.LIVE, None
        # In-range -> interpolate. Out-of-range (above max / below min)
        # still goes through interpolation via clamping (constant
        # extrapolation), which the user UX-wise treats as "interpolated"
        # rather than "live" — we have *some* data, just not at this depth.
        from poker_solver.blueprint_interp import find_flanking_depths

        lo, hi = find_flanking_depths(float(stack_bb), [float(d) for d in depths])
        return SourceLabel.INTERPOLATED, (int(lo), int(hi))

    # -- Per-class chart lookup --------------------------------------------

    def lookup_chart(
        self,
        *,
        stack_bb: int,
        ante: str | float | int,
        action_history: str = "",
    ) -> RouteInfo:
        """Return a per-class chart (the 169-class root strategy).

        This is the chart-widget entry point. Returns a populated
        :class:`RouteInfo` with ``per_class`` mapping each class label
        to its action distribution at the SB root decision (or the
        supplied ``action_history``).

        The router itself does NOT trigger a live solve — when no
        blueprint coverage exists, returns ``source=LIVE`` with an
        empty payload; the caller must handle the live-solve dispatch
        (existing path through ``state.runner.start_preflop_chart``).
        """
        t0 = time.monotonic()
        source, anchors = self.route_label(stack_bb=stack_bb, ante=ante)
        ante_bb = _normalize_ante_local(ante)
        if source == SourceLabel.LIVE:
            return RouteInfo(
                source=SourceLabel.LIVE,
                wall_time_s=time.monotonic() - t0,
                confidence="no blueprint coverage (live solve required)",
                per_class={},
                stack_bb=int(stack_bb),
                ante_bb=ante_bb,
                action_history=action_history,
                anchor_depths=None,
            )
        if source == SourceLabel.BLUEPRINT:
            per_class = self._extract_chart_exact(
                stack_bb=int(stack_bb),
                ante=ante,
                action_history=action_history,
            )
            return RouteInfo(
                source=SourceLabel.BLUEPRINT,
                wall_time_s=time.monotonic() - t0,
                confidence=_describe_exact(int(stack_bb), ante_bb),
                per_class=per_class,
                stack_bb=int(stack_bb),
                ante_bb=ante_bb,
                action_history=action_history,
                anchor_depths=None,
            )
        # INTERPOLATED
        per_class = self._extract_chart_interp(
            target_stack_bb=int(stack_bb),
            ante=ante,
            action_history=action_history,
            anchor_depths=anchors,  # type: ignore[arg-type]
        )
        return RouteInfo(
            source=SourceLabel.INTERPOLATED,
            wall_time_s=time.monotonic() - t0,
            confidence=_describe_interp(int(stack_bb), ante_bb, anchors),
            per_class=per_class,
            stack_bb=int(stack_bb),
            ante_bb=ante_bb,
            action_history=action_history,
            anchor_depths=anchors,
        )

    # -- Internal helpers ---------------------------------------------------

    def _extract_chart_exact(
        self, *, stack_bb: int, ante: str | float | int, action_history: str
    ) -> dict[str, dict[str, float]]:
        """Pull the per-class chart for an exact shard match.

        Reads the shard's infoset entry for ``action_history`` and
        converts to ``{hand_class: {action_label: prob}}`` — the same
        shape :func:`ui.views.preflop_chart.project_chart` already
        consumes for live-solve results.
        """
        from poker_solver.blueprint_loader import (
            BlueprintKey,
            normalize_action_history,
        )

        key = BlueprintKey.from_user(stack_bb, ante)
        bp = self.loader._load_shard(key)  # already validated by has_exact_shard
        history_key = normalize_action_history(action_history)
        infoset = bp.infosets.get(history_key)
        if infoset is None:
            return {}
        actions = list(infoset.get("actions", []))
        strategy_map = infoset.get("strategy", {})
        out: dict[str, dict[str, float]] = {}
        for hand_class, probs in strategy_map.items():
            if not actions or not probs or len(actions) != len(probs):
                continue
            out[str(hand_class)] = {
                str(actions[i]): float(probs[i]) for i in range(len(actions))
            }
        return out

    def _extract_chart_interp(
        self,
        *,
        target_stack_bb: int,
        ante: str | float | int,
        action_history: str,
        anchor_depths: tuple[int, int],
    ) -> dict[str, dict[str, float]]:
        """Pull the per-class chart by interpolating two anchors.

        Loads both flank shards, then for each hand class
        present in BOTH, runs :func:`interpolate_strategy` on the per-class
        action vectors. The action menu must match between flanks —
        otherwise we silently snap to the nearest depth (constant
        extrapolation rather than producing a malformed blend).
        """
        from poker_solver.blueprint_interp import interpolate_strategy
        from poker_solver.blueprint_loader import (
            BlueprintKey,
            normalize_action_history,
        )

        lo, hi = anchor_depths
        history_key = normalize_action_history(action_history)

        bp_lo = self.loader._load_shard(BlueprintKey.from_user(lo, ante))
        bp_hi = self.loader._load_shard(BlueprintKey.from_user(hi, ante))
        info_lo = bp_lo.infosets.get(history_key)
        info_hi = bp_hi.infosets.get(history_key)
        if info_lo is None or info_hi is None:
            # Action history not reachable in one or both anchors —
            # treat as no blueprint data for this history.
            return {}
        actions_lo = list(info_lo.get("actions", []))
        actions_hi = list(info_hi.get("actions", []))
        if actions_lo != actions_hi:
            # Action menus disagree -> not safely interpolatable. Snap
            # to nearest (constant extrapolation) instead of blending
            # across mismatched vectors.
            nearest_lo = abs(target_stack_bb - lo) <= abs(target_stack_bb - hi)
            chosen = info_lo if nearest_lo else info_hi
            actions = actions_lo if nearest_lo else actions_hi
            strategy_map = chosen.get("strategy", {})
            out_fallback: dict[str, dict[str, float]] = {}
            for hand_class, probs in strategy_map.items():
                if not probs or len(actions) != len(probs):
                    continue
                out_fallback[str(hand_class)] = {
                    str(actions[i]): float(probs[i]) for i in range(len(actions))
                }
            return out_fallback

        actions = actions_lo  # same as actions_hi
        strat_lo = info_lo.get("strategy", {})
        strat_hi = info_hi.get("strategy", {})
        out: dict[str, dict[str, float]] = {}
        for hand_class in strat_lo:
            v_lo = strat_lo.get(hand_class)
            v_hi = strat_hi.get(hand_class)
            if v_lo is None or v_hi is None:
                continue
            if not actions or len(actions) != len(v_lo) or len(actions) != len(v_hi):
                continue
            blended = interpolate_strategy(
                float(target_stack_bb),
                {float(lo): list(v_lo), float(hi): list(v_hi)},
                method="linear",
            )
            out[str(hand_class)] = {
                str(actions[i]): float(blended[i]) for i in range(len(actions))
            }
        return out


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalize_ante_local(ante: str | float | int) -> float:
    """Best-effort ante normalization; returns 0.0 on bad input.

    We don't raise from here because the router is a UI consumer — bad
    user input is reported via notify in the calling view, not via
    exception bubbling from the router.
    """
    from poker_solver.blueprint_loader import (
        BlueprintLookupError,
        normalize_ante,
    )

    try:
        return float(normalize_ante(ante))
    except BlueprintLookupError:
        return 0.0


def _describe_exact(stack_bb: int, ante_bb: float) -> str:
    ante_token = _ante_token(ante_bb)
    return f"exact {stack_bb}BB / {ante_token}"


def _describe_interp(
    stack_bb: int,
    ante_bb: float,
    anchors: tuple[int, int] | None,
) -> str:
    ante_token = _ante_token(ante_bb)
    if anchors is None:
        return f"interp {stack_bb}BB / {ante_token}"
    lo, hi = anchors
    if lo == hi:
        # Out-of-range clamp: both flanks equal the boundary.
        return f"clamp {stack_bb}BB to {lo}BB / {ante_token}"
    return f"{stack_bb}BB between {lo}/{hi}BB / {ante_token}"


def _ante_token(ante_bb: float) -> str:
    """Reverse-map a BB float to the user-facing ante token."""
    if abs(ante_bb - 0.0) < 1e-6:
        return "no-ante"
    if abs(ante_bb - 0.5) < 1e-6:
        return "half-ante"
    if abs(ante_bb - 1.0) < 1e-6:
        return "full-ante"
    return f"{ante_bb:g}BB ante"
