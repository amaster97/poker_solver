"""Quality-metric helper for the v1.10 perf benchmark harness.

Given two postflop solve outputs (reference vs comparison), compute the
three quality metrics used by ``scripts/run_v1_10_perf_bench.py``:

  1. **Exploitability** (in bb/100) — read straight off the comparison
     solve's converged-strategy exploitability, normalized from the Rust
     binding's chips/hand units to bb/100. Lower = closer to Nash.
  2. **L1 distance vs reference** — sum_{class in 169, action in A} of
     ``|p_ref[class][action] - p_cmp[class][action]|`` projected onto the
     169-class first-decision strategy. We sum over classes that appear
     in either strategy (missing classes contribute their full
     comparison-side mass to the L1).
  3. **EV-of-action loss vs reference** — for each hand class present in
     both solves, compute the per-class EV difference of the actions
     chosen by the comparison strategy when scored against the
     reference's exploitability proxy. We approximate this with a
     simplified expected-value comparison: for each class, take the
     argmax action of the reference strategy, and report the
     comparison-strategy's probability mass on that action averaged
     across classes (lower = more divergent). Returned in bb/100.

This module is harness-time only — the v1.10 final benchmark agent
will run it. It does not depend on the optimizations being in place; the
metric formulas are stable.

Reference Nash invariance: per the "Brown convention adopt" memory note,
sanity-checks should be EV-of-action under Nash invariance, NOT strategy
prob diffs alone. L1 is reported as a *secondary* signal (diagnostic),
while EV-of-action loss is the load-bearing per-class quality metric.

Usage:
    from scripts.measure_quality_metrics import (
        compute_l1_distance,
        compute_ev_action_loss_bb100,
        chips_to_bb100,
    )

    l1 = compute_l1_distance(ref_per_class, cmp_per_class)
    ev_loss = compute_ev_action_loss_bb100(
        ref_per_class, cmp_per_class, big_blind_chips=100,
    )
    expl_bb100 = chips_to_bb100(cmp_exploit_chips, big_blind_chips=100)
"""

from __future__ import annotations

from typing import Mapping


# ---------------------------------------------------------------------------
# Unit conversions
# ---------------------------------------------------------------------------


def chips_to_bb100(chips_per_hand: float, big_blind_chips: int) -> float:
    """Convert a chips-per-hand quantity to bb/100.

    The Rust binding's ``compute_exploitability`` emits chips/hand. To
    express on the canonical poker-perf scale (big-blinds per 100 hands)
    we multiply by 100 and divide by the big-blind size in chips.

    Args:
        chips_per_hand: A value from ``_rust.compute_exploitability``
            (chips per hand, single-game units).
        big_blind_chips: The chip-equivalent of one big blind. For
            ``BlueprintConfig(stack_bb=40)`` with default 100 chips/BB,
            this is 100.

    Returns:
        The same quantity expressed in bb/100. Useful for cross-table
        readability since bb/100 is the standard poker units.
    """
    if big_blind_chips <= 0:
        raise ValueError(
            f"big_blind_chips must be positive; got {big_blind_chips}"
        )
    return (chips_per_hand / float(big_blind_chips)) * 100.0


# ---------------------------------------------------------------------------
# L1 distance
# ---------------------------------------------------------------------------


def compute_l1_distance(
    reference: Mapping[str, Mapping[str, float]],
    comparison: Mapping[str, Mapping[str, float]],
) -> float:
    """L1 distance between two per-class strategy projections.

    L1 := sum_{class, action} |p_ref[class][action] - p_cmp[class][action]|

    Classes present only in one strategy contribute their full strategy
    mass on the present side (treated as if the absent side has
    uniform-zero on those actions). Action labels are taken from the
    union; the per-class strategy dicts are sparse (one entry per
    legal action), so missing-action means probability = 0.

    Notes
    -----
    L1 is provided as a *diagnostic* secondary metric. The load-bearing
    quality signal is ``compute_ev_action_loss_bb100`` (per "Brown
    convention adopt" Nash invariance note).

    Args:
        reference: ``{class: {action_label: prob}}`` — the top_k=169
            reference solve's first-decision strategy.
        comparison: Same shape — the truncated solve's strategy.

    Returns:
        Sum over all (class, action) of ``|p_ref - p_cmp|``. Strictly
        non-negative. 0 means identical strategies. Upper bound is
        ``2 * n_classes_union`` (each class contributes at most 2.0
        when strategies are disjoint).
    """
    if not isinstance(reference, Mapping) or not isinstance(comparison, Mapping):
        raise TypeError(
            "reference and comparison must be Mapping[str, Mapping[str, float]]"
        )
    all_classes = set(reference.keys()) | set(comparison.keys())
    total = 0.0
    for cls in all_classes:
        ref_row = reference.get(cls, {})
        cmp_row = comparison.get(cls, {})
        action_labels = set(ref_row.keys()) | set(cmp_row.keys())
        for a in action_labels:
            total += abs(float(ref_row.get(a, 0.0)) - float(cmp_row.get(a, 0.0)))
    return total


# ---------------------------------------------------------------------------
# EV-of-action loss
# ---------------------------------------------------------------------------


def compute_ev_action_loss_bb100(
    reference: Mapping[str, Mapping[str, float]],
    comparison: Mapping[str, Mapping[str, float]],
    *,
    big_blind_chips: int,
    pot_chips: float | None = None,
) -> float:
    """Per-class EV-of-action loss between two strategies, in bb/100.

    For each class present in BOTH strategies, compute the **total
    variation distance** between the reference and comparison
    probability distributions over actions:

        TV(p_ref, p_cmp) = 0.5 * sum_{action} |p_ref[a] - p_cmp[a]|

    Total variation is bounded in [0, 1]. We average across classes
    and scale by a pot-size proxy to convert into bb/100.

    The intuition: under **Nash invariance** (per "Brown convention
    adopt" memory note), every action with non-zero probability under
    the reference has equal EV. The comparison strategy's EV loss is
    proportional to how far its distribution deviates from the
    reference — total variation captures this bound:
    ``EV_loss <= TV(p_ref, p_cmp) * pot_size``. When ``p_cmp == p_ref``
    exactly, TV = 0 and EV-loss = 0.

    .. note::
        This is a *proxy* metric: it bounds the true EV loss from
        above (any deviation lowers EV by at most the modal-action's
        EV gap, which is 0 under Nash). It does NOT require running
        a separate best-response solve, so it can be computed in
        post-processing of the harness output. The true EV-loss
        ground-truth (full best-response against the reference) is
        computed by the harness only at the end-of-v1.10 verification
        step using ``_rust.compute_exploitability`` on the comparison
        strategy embedded as a fixed villain in a BR walk.

    Args:
        reference: ``{class: {action: prob}}`` — top_k=169 reference.
        comparison: Same shape — truncated solve.
        big_blind_chips: Chip-equivalent of one BB (e.g. 100).
        pot_chips: Optional pot proxy for the bb/100 scaling. When
            None, defaults to ``big_blind_chips * 6`` (~3-bb open
            heads-up flop pot). Used only as a scaling constant — the
            relative ordering across (top_k, street) cells is
            invariant to this choice.

    Returns:
        Per-class average total-variation distance, scaled to bb/100.
        Strictly non-negative. 0 means the comparison strategy
        matches the reference exactly for every common class.
    """
    if big_blind_chips <= 0:
        raise ValueError(
            f"big_blind_chips must be positive; got {big_blind_chips}"
        )
    if pot_chips is None:
        # Default to 6 BB ~ typical heads-up postflop pot starting size.
        pot_chips = float(big_blind_chips) * 6.0
    if pot_chips <= 0:
        raise ValueError(
            f"pot_chips must be positive; got {pot_chips}"
        )
    common_classes = set(reference.keys()) & set(comparison.keys())
    if not common_classes:
        return 0.0
    total_tv = 0.0
    for cls in common_classes:
        ref_row = reference[cls]
        cmp_row = comparison[cls]
        if not ref_row and not cmp_row:
            continue
        action_labels = set(ref_row.keys()) | set(cmp_row.keys())
        # Total variation distance: 0.5 * sum |p_ref - p_cmp|, bounded [0, 1].
        l1 = 0.0
        for a in action_labels:
            l1 += abs(
                float(ref_row.get(a, 0.0)) - float(cmp_row.get(a, 0.0))
            )
        tv = 0.5 * l1
        total_tv += tv
    avg_tv = total_tv / float(len(common_classes))
    # Scale: avg_tv * pot_chips = upper-bound on chips lost per hand.
    chips_lost_per_hand = avg_tv * pot_chips
    return chips_to_bb100(chips_lost_per_hand, big_blind_chips=big_blind_chips)


# ---------------------------------------------------------------------------
# Combined helper — convenient one-call entry from the harness.
# ---------------------------------------------------------------------------


def compute_all_quality_metrics(
    reference_result: object,
    comparison_result: object,
    *,
    big_blind_chips: int,
) -> dict[str, float]:
    """Compute exploitability + L1 + EV-of-action loss in a single call.

    Both arguments are :class:`RangeVsRangeNashResult`-like objects
    (anything with ``per_class_strategy`` and ``exploitability``
    attributes). Each returned value is in bb/100 (where applicable).

    Args:
        reference_result: top_k=169 solve result.
        comparison_result: top_k truncated solve result.
        big_blind_chips: Chip-equivalent of one BB.

    Returns:
        ``{"exploit_bb100", "l1_vs_ref", "ev_loss_bb100"}``.
    """
    ref_per_class = dict(getattr(reference_result, "per_class_strategy", {}))
    cmp_per_class = dict(getattr(comparison_result, "per_class_strategy", {}))
    cmp_exploit_chips = float(getattr(comparison_result, "exploitability", 0.0))

    l1 = compute_l1_distance(ref_per_class, cmp_per_class)
    ev_loss = compute_ev_action_loss_bb100(
        ref_per_class,
        cmp_per_class,
        big_blind_chips=big_blind_chips,
    )
    expl_bb100 = chips_to_bb100(
        cmp_exploit_chips, big_blind_chips=big_blind_chips
    )

    return {
        "exploit_bb100": expl_bb100,
        "l1_vs_ref": l1,
        "ev_loss_bb100": ev_loss,
    }


__all__ = [
    "chips_to_bb100",
    "compute_all_quality_metrics",
    "compute_ev_action_loss_bb100",
    "compute_l1_distance",
]
