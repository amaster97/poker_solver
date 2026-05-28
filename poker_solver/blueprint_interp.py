"""Premium-A blueprint stack-depth interpolation (Phase 3, task #68).

Phase 1 ships a discrete blueprint grid at 9 depths (20, 30, 40, 60, 80,
100, 150, 175, 200 BB). Real play rarely sits exactly on one of those
grid points — a user with a 67 BB stack lands strictly between the 60 BB
and 80 BB shards. Picking the nearest shard discards information and
introduces a step discontinuity in the served strategy.

This module ships a small, *pure-Python* interpolation surface that the
Phase 2 loader (or an interactive lookup callback) hooks into to map an
arbitrary ``target_stack_bb`` onto a per-cell strategy vector blended
from its two flanking blueprint depths. It is **strictly independent**
of the Phase 2 loader API — callers pass in the strategies dict directly
keyed by ``{stack_bb: strategy_vector}``, and the loader composes the
two pieces.

## Mathematical model

For ``target_bb`` between ``d_lo`` and ``d_hi`` (the two flanking grid
depths from the supplied ``strategies`` dict), we compute the convex
weight

.. math:: t = (\\text{target\\_bb} - d_{lo}) / (d_{hi} - d_{lo})

and return ``(1 - t) * strategy[d_lo] + t * strategy[d_hi]`` componentwise.
Because both inputs are probability vectors and ``t \\in [0, 1]``, the
result is automatically (a) entrywise in ``[0, 1]`` and (b) summing to
exactly ``1.0`` — convex combinations of simplex points stay on the
simplex. We still divide by the sum at the end to absorb the small
numerical drift from finite-precision floats (1e-16 ULPs accumulate
over a 7-action vector); after that the L1 error is bounded by
``len(vector) * eps_float``.

## Edge cases

- **Exact match**. If ``target_bb`` equals one of the supplied depths
  (within ``1e-9``), the matching strategy is returned *as-is* —
  no interpolation, no normalization, no drift.
- **Below the minimum supplied depth**. Clamps to the lowest depth
  blueprint (constant extrapolation). Justification: outside the grid
  the true converged strategy is unknown; constant extrapolation is
  the only choice that does not invent probability mass.
- **Above the maximum supplied depth**. Symmetric: clamps to the
  highest depth blueprint.
- **Single supplied depth**. That depth's strategy is returned for
  every target (constant extrapolation collapses to a single shard).
- **Empty strategies dict**. Raises ``ValueError`` — there is no
  reasonable interpolation without at least one neighbor.

## Modes

- ``method="linear"`` (default). Convex combination as above.
- ``method="nearest"``. Snap to the closest supplied depth (tie-break
  toward the lower depth — keeps behavior deterministic). Useful as a
  fallback when the action menus at ``d_lo`` and ``d_hi`` are not
  identical (interpolating across mismatched action vectors is not
  meaningful); callers should detect that condition externally and
  fall back to ``nearest`` rather than the module silently producing
  a malformed blend.

## Scope of "strategy"

The core kernel operates on a single per-cell strategy vector — a
``Sequence[float]`` of action probabilities. The convenience wrapper
:func:`interpolate_blueprint_strategies` lifts the same operation to a
nested ``{history_key: {hand_class: [probs]}}`` strategy dict, applying
the kernel per-cell. The wrapper enforces structural compatibility
(same history keys, same hand classes, same action menu length) and
raises a descriptive ``ValueError`` if the two blueprints disagree.

## Use from Phase 2

The Phase 2 loader's recommended hook (verified against the Phase 2
agent interface):

.. code-block:: python

    from poker_solver.blueprint_interp import (
        interpolate_strategy,
        interpolate_blueprint_strategies,
    )

    # Per-cell variant (preferred — Phase 2 loader composes flanks).
    bp_lo = loader.load(stack_bb=60)
    bp_hi = loader.load(stack_bb=80)
    blended_infosets = interpolate_blueprint_strategies(
        target_bb=67,
        strategies={60: bp_lo.infosets, 80: bp_hi.infosets},
    )

This module is pure-Python with no NumPy dependency in the hot path.
NumPy is permitted in the optional acceleration path, but the default
implementation uses native ``float`` arithmetic so the wheel keeps
working in a no-NumPy environment (e.g., a UI subprocess that imports
only the loader).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

__all__ = [
    "InterpolationError",
    "interpolate_strategy",
    "interpolate_blueprint_strategies",
    "find_flanking_depths",
]

# Tolerance used to detect "exact match" against a supplied grid depth.
# Below this threshold the corresponding blueprint is returned as-is.
_EXACT_MATCH_BB_TOL = 1e-9

# Tolerance used to assert each action vector sums to ~1.0 after
# interpolation. Convex combinations of unit-sum vectors must sum to
# exactly 1.0 in exact arithmetic; in floating point we allow a small
# drift before raising. The validator in `blueprint.validate_blueprint`
# uses 1e-4; we use a much tighter 1e-9 because the interpolation
# kernel should not introduce drift larger than ULP rounding.
_NORMALIZATION_TOLERANCE = 1e-9


class InterpolationError(ValueError):
    """Raised when an interpolation request cannot be honored.

    Subclass of ``ValueError`` so callers can use the broader handler
    or the specific one.
    """


# ---------------------------------------------------------------------------
# Public API: per-cell interpolation
# ---------------------------------------------------------------------------


def interpolate_strategy(
    target_bb: float,
    strategies: Mapping[float, Sequence[float]],
    method: Literal["linear", "nearest"] = "linear",
) -> list[float]:
    """Interpolate a strategy vector across stack-depth neighbors.

    Parameters
    ----------
    target_bb:
        The desired stack depth in BB. May fall between grid points,
        on a grid point, or outside the grid range.
    strategies:
        Mapping ``{stack_bb: strategy_vector}`` of known blueprint
        strategies for this specific (infoset, hand_class) cell. All
        vectors must have the same length (same action menu).
    method:
        ``"linear"`` (default) — convex combination across the two
        flanking depths.
        ``"nearest"`` — snap to the closest depth (tie-break low).

    Returns
    -------
    list[float]
        The interpolated probability vector. Always sums to 1.0 within
        ``1e-9`` and every entry lies in ``[0.0, 1.0]``.

    Raises
    ------
    InterpolationError
        If ``strategies`` is empty, contains mismatched vector lengths,
        or contains a non-probability entry.
    """
    if not strategies:
        raise InterpolationError("strategies must contain at least one depth")
    if method not in ("linear", "nearest"):
        raise InterpolationError(
            f"unknown interpolation method {method!r}; expected 'linear' or 'nearest'"
        )

    depths_sorted = sorted(strategies.keys())
    _validate_vector_shapes(strategies, depths_sorted)

    # Exact-match short-circuit (skips interpolation, returns the
    # supplied vector verbatim so callers see no drift from ULP
    # rounding).
    for d in depths_sorted:
        if abs(float(d) - float(target_bb)) <= _EXACT_MATCH_BB_TOL:
            return [float(p) for p in strategies[d]]

    # Out-of-range clamp (constant extrapolation in both directions).
    if target_bb <= depths_sorted[0]:
        return [float(p) for p in strategies[depths_sorted[0]]]
    if target_bb >= depths_sorted[-1]:
        return [float(p) for p in strategies[depths_sorted[-1]]]

    d_lo, d_hi = _flanking_depths_sorted(depths_sorted, float(target_bb))

    if method == "nearest":
        # Tie-break toward the lower depth (deterministic).
        mid = (d_lo + d_hi) / 2.0
        chosen = d_lo if float(target_bb) <= mid else d_hi
        return [float(p) for p in strategies[chosen]]

    return _linear_blend(
        target_bb=float(target_bb),
        d_lo=d_lo,
        d_hi=d_hi,
        v_lo=strategies[d_lo],
        v_hi=strategies[d_hi],
    )


# ---------------------------------------------------------------------------
# Public API: full blueprint strategy interpolation
# ---------------------------------------------------------------------------


def interpolate_blueprint_strategies(
    target_bb: float,
    strategies: Mapping[float, Mapping[str, Mapping[str, Sequence[float]]]],
    method: Literal["linear", "nearest"] = "linear",
) -> dict[str, dict[str, list[float]]]:
    """Interpolate a full blueprint ``infosets``-shaped strategy block.

    Parameters
    ----------
    target_bb:
        Target stack depth in BB.
    strategies:
        Mapping ``{stack_bb: {history_key: {hand_class: [probs]}}}``.
        The two flanking depths (or the single match) must share
        identical history keys and hand-class membership at each
        infoset, plus identical action menu lengths per infoset.
    method:
        ``"linear"`` (default) or ``"nearest"``.

    Returns
    -------
    dict[str, dict[str, list[float]]]
        ``{history_key: {hand_class: [interpolated_probs]}}`` — every
        cell is independently interpolated.

    Raises
    ------
    InterpolationError
        If the supplied strategies have mismatched structure or any
        cell fails the per-cell kernel's validation.
    """
    if not strategies:
        raise InterpolationError("strategies must contain at least one depth")

    depths_sorted = sorted(strategies.keys())

    # Exact match → return the matching blueprint's infoset block.
    for d in depths_sorted:
        if abs(float(d) - float(target_bb)) <= _EXACT_MATCH_BB_TOL:
            return _deep_copy_infosets(strategies[d])
    # Out-of-range clamp.
    if target_bb <= depths_sorted[0]:
        return _deep_copy_infosets(strategies[depths_sorted[0]])
    if target_bb >= depths_sorted[-1]:
        return _deep_copy_infosets(strategies[depths_sorted[-1]])

    d_lo, d_hi = _flanking_depths_sorted(depths_sorted, float(target_bb))

    block_lo = strategies[d_lo]
    block_hi = strategies[d_hi]
    _validate_blueprint_block_compat(block_lo, block_hi, d_lo, d_hi)

    if method == "nearest":
        mid = (d_lo + d_hi) / 2.0
        chosen = d_lo if float(target_bb) <= mid else d_hi
        return _deep_copy_infosets(strategies[chosen])

    out: dict[str, dict[str, list[float]]] = {}
    for history_key in block_lo:
        cells_lo = block_lo[history_key]
        cells_hi = block_hi[history_key]
        merged_cells: dict[str, list[float]] = {}
        for hand_class, v_lo in cells_lo.items():
            v_hi = cells_hi[hand_class]
            merged_cells[hand_class] = _linear_blend(
                target_bb=float(target_bb),
                d_lo=d_lo,
                d_hi=d_hi,
                v_lo=v_lo,
                v_hi=v_hi,
            )
        out[history_key] = merged_cells
    return out


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------


def find_flanking_depths(
    target_bb: float, depths: Sequence[float]
) -> tuple[float, float]:
    """Return ``(d_lo, d_hi)`` flanking ``target_bb`` from ``depths``.

    On exact match, both returned depths equal the match. Below the
    minimum (resp. above the maximum) both equal the boundary. Useful
    for callers that want to load only the two needed shards (avoiding
    the full grid in memory).
    """
    if not depths:
        raise InterpolationError("depths must be non-empty")
    sorted_depths = sorted(float(d) for d in depths)
    # Exact match wins first.
    for d in sorted_depths:
        if abs(d - float(target_bb)) <= _EXACT_MATCH_BB_TOL:
            return (d, d)
    if target_bb <= sorted_depths[0]:
        return (sorted_depths[0], sorted_depths[0])
    if target_bb >= sorted_depths[-1]:
        return (sorted_depths[-1], sorted_depths[-1])
    return _flanking_depths_sorted(sorted_depths, float(target_bb))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _flanking_depths_sorted(
    depths_sorted: Sequence[float], target_bb: float
) -> tuple[float, float]:
    """Given a *sorted ascending* depth list and an in-range target,
    return the flanking pair ``(d_lo, d_hi)`` with ``d_lo < target < d_hi``.

    Pre-condition: caller has already handled exact-match and clamp
    cases — this helper does *not* re-validate those.
    """
    # Linear scan is fine: the blueprint grid has 9 depths. Bisect would
    # be overkill and obscures the contract.
    for i in range(len(depths_sorted) - 1):
        if depths_sorted[i] <= target_bb <= depths_sorted[i + 1]:
            return (depths_sorted[i], depths_sorted[i + 1])
    # Should be unreachable given the pre-conditions, but raise
    # defensively rather than returning silently-wrong data.
    raise InterpolationError(
        f"could not locate flanking depths for target_bb={target_bb} "
        f"in {list(depths_sorted)!r}"
    )


def _linear_blend(
    *,
    target_bb: float,
    d_lo: float,
    d_hi: float,
    v_lo: Sequence[float],
    v_hi: Sequence[float],
) -> list[float]:
    """Convex blend of two strategy vectors at ``target_bb`` between
    ``d_lo`` and ``d_hi``.

    Both vectors must already have the same length (caller's
    responsibility). The output is renormalized to absorb ULP drift
    and bounded entrywise to ``[0, 1]`` as a defense against caller-
    supplied near-1.0 inputs that round just over.
    """
    if d_hi == d_lo:
        # Degenerate case: collapses to the same vector. Caller should
        # have hit the exact-match shortcut, but defend in case of
        # numerical weirdness.
        return [float(p) for p in v_lo]
    if len(v_lo) != len(v_hi):
        raise InterpolationError(
            f"strategy vector length mismatch at depths {d_lo} and "
            f"{d_hi}: {len(v_lo)} vs {len(v_hi)}"
        )
    t = (target_bb - d_lo) / (d_hi - d_lo)
    blended = [(1.0 - t) * float(a) + t * float(b) for a, b in zip(v_lo, v_hi)]

    # Clamp ULPs to [0, 1] before renormalizing — a near-zero
    # negative drift would otherwise propagate as -1e-17 in the output.
    clamped = [max(0.0, min(1.0, x)) for x in blended]
    total = sum(clamped)
    if total <= 0.0:
        raise InterpolationError(
            f"interpolated strategy sums to {total!r} (degenerate inputs?)"
        )
    normed = [x / total for x in clamped]
    # Sanity: post-normalization sum must equal 1.0 within tolerance.
    drift = abs(sum(normed) - 1.0)
    if drift > _NORMALIZATION_TOLERANCE:
        raise InterpolationError(
            f"normalization drift {drift!r} exceeds tolerance "
            f"{_NORMALIZATION_TOLERANCE!r}"
        )
    return normed


def _validate_vector_shapes(
    strategies: Mapping[float, Sequence[float]], depths_sorted: Sequence[float]
) -> None:
    """All supplied strategy vectors must have the same length and be
    composed of finite ``float``s.

    Probability validity (non-negative, summing to 1.0) is checked
    *loosely* here: we accept up to 1e-4 drift on inputs (matching the
    blueprint validator's tolerance) and clamp ULPs in the blend step.
    Negative entries reject hard.
    """
    if not depths_sorted:
        return
    ref_len = len(strategies[depths_sorted[0]])
    for d in depths_sorted:
        v = strategies[d]
        if len(v) != ref_len:
            raise InterpolationError(
                f"strategy at depth {d} has length {len(v)}, "
                f"expected {ref_len} (depth {depths_sorted[0]})"
            )
        for k, x in enumerate(v):
            fx = float(x)
            if fx != fx:  # NaN check (the only float NOT equal to itself)
                raise InterpolationError(f"NaN probability at depth {d}, slot {k}")
            if fx < -1e-9 or fx > 1.0 + 1e-9:
                raise InterpolationError(
                    f"probability out of [0, 1] at depth {d}, slot {k}: {fx!r}"
                )


def _validate_blueprint_block_compat(
    block_lo: Mapping[str, Mapping[str, Sequence[float]]],
    block_hi: Mapping[str, Mapping[str, Sequence[float]]],
    d_lo: float,
    d_hi: float,
) -> None:
    """Verify two blueprint infoset blocks have compatible structure.

    - Same history keys.
    - Same hand classes per history key.
    - Same action-vector length per history key (action menu must
      match — interpolating across mismatched menus is nonsensical).
    """
    keys_lo = set(block_lo.keys())
    keys_hi = set(block_hi.keys())
    if keys_lo != keys_hi:
        missing_in_hi = keys_lo - keys_hi
        missing_in_lo = keys_hi - keys_lo
        raise InterpolationError(
            f"history keys differ between depths {d_lo} and {d_hi}: "
            f"only-in-{d_lo}={sorted(missing_in_hi)[:3]!r}, "
            f"only-in-{d_hi}={sorted(missing_in_lo)[:3]!r}"
        )
    for history_key, cells_lo in block_lo.items():
        cells_hi = block_hi[history_key]
        classes_lo = set(cells_lo.keys())
        classes_hi = set(cells_hi.keys())
        if classes_lo != classes_hi:
            raise InterpolationError(
                f"hand classes differ at infoset {history_key!r} "
                f"between depths {d_lo} and {d_hi}: "
                f"only-in-{d_lo}={sorted(classes_lo - classes_hi)[:3]!r}, "
                f"only-in-{d_hi}={sorted(classes_hi - classes_lo)[:3]!r}"
            )
        # Length must match for every (history_key, hand_class) pair.
        for cls in classes_lo:
            n_lo = len(cells_lo[cls])
            n_hi = len(cells_hi[cls])
            if n_lo != n_hi:
                raise InterpolationError(
                    f"action vector length mismatch at infoset "
                    f"{history_key!r}, class {cls!r}: depth {d_lo} has "
                    f"{n_lo}, depth {d_hi} has {n_hi}"
                )


def _deep_copy_infosets(
    block: Mapping[str, Mapping[str, Sequence[float]]],
) -> dict[str, dict[str, list[float]]]:
    """Return a fresh ``{history_key: {class: list[float]}}`` copy.

    We never alias caller-supplied lists out of this module — callers
    that mutate the result must not be able to mutate the loader's
    cached blueprint.
    """
    out: dict[str, dict[str, list[float]]] = {}
    for history_key, cells in block.items():
        out[history_key] = {cls: [float(p) for p in v] for cls, v in cells.items()}
    return out


# ---------------------------------------------------------------------------
# Internal convenience: make a flat-API view of a blueprint infoset block
# (kept private for now; promote to public if a downstream caller needs it).
# ---------------------------------------------------------------------------


def _strategies_by_depth_for_cell(
    blueprints: Mapping[float, Mapping[str, Mapping[str, Sequence[float]]]],
    history_key: str,
    hand_class: str,
) -> dict[float, list[float]]:
    """Pull a single ``(history_key, hand_class)`` cell across depths.

    Used by tests + the Phase 2 loader's per-cell hot path. Returns a
    fresh dict so callers cannot mutate the underlying blueprints.
    """
    out: dict[float, list[float]] = {}
    for depth, block in blueprints.items():
        cells = block.get(history_key)
        if cells is None:
            continue
        vec = cells.get(hand_class)
        if vec is None:
            continue
        out[depth] = [float(p) for p in vec]
    return out


# Re-export of typing names so callers don't have to import from this
# module's collections.abc origin.
StrategyVector = Sequence[float]
"""Type alias: a per-cell strategy vector (action probabilities)."""

InfosetBlock = Mapping[str, Mapping[str, StrategyVector]]
"""Type alias: ``{history_key: {hand_class: [probs]}}``."""

# Keep a single internal Any-typed re-export so downstream tools that
# probe ``__all__`` see the full surface — but don't add typing-only
# names to ``__all__`` proper (mypy treats ``__all__`` as a runtime
# value).
_TYPING_EXPORTS: tuple[Any, ...] = (StrategyVector, InfosetBlock)
