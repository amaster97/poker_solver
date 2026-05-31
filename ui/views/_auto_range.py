"""Auto range generation — project a preflop-blueprint line into a range string.

The Spot Input panel lets the user type/click ranges or load canned example
spots. This module adds a third, engine-LIGHT source: derive a player's range
slot directly from the precomputed preflop blueprint (the same asset the
Preflop Chart reads) for a chosen standard position/line — e.g. "BTN/SB open
(RFI)" or "BB 3-bet vs open" at the spot's current stack depth.

## What "derive a range" means

The blueprint stores, per ``(depth, ante, action_history)``, a per-169-class
action distribution (``{hand_class: {action_label: prob}}``). A *range* is a
selection of hand classes. We project the distribution into a range by keeping
each class whose AGGREGATE probability mass on a chosen ACTION KIND
(``raise``/``jam`` for an opening or 3-bet range; ``call`` for a flatting range)
clears a threshold. The kept class labels (``AA``, ``AKs``, ``72o`` …) join into
a PIO-style comma-separated range string that ``RangeWithFreqs.from_string``
parses losslessly.

This is intentionally a HARD (in/out) projection, not a frequency-weighted one:
a first-version auto-fill should hand the user a clean, editable range they
recognize ("these are the hands I open"), not a mixed-frequency soup. The user
can then fine-tune in the matrix.

## Blueprint API used

  * :meth:`ui.blueprint_router.BlueprintRouter.lookup_chart` — root (open) line.
  * :meth:`ui.blueprint_router.BlueprintRouter.extract_all_lines` — deeper lines
    (BB vs open) keyed by the engine history suffix (``"||p|b200"``).
  * :func:`ui.views.preflop_chart.classify_action` — buckets an engine action
    label into fold/call/raise/jam (reused so the in/out decision matches the
    chart's own coloring).

Both router methods route through the SAME exact-vs-interpolated decision the
Preflop Chart uses, so an off-anchor depth (e.g. 50 BB between the 40/60 BB
anchors) is interpolated rather than refused.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ui.views.preflop_chart import classify_action

if TYPE_CHECKING:
    from ui.blueprint_router import BlueprintRouter

logger = logging.getLogger(__name__)

__all__ = [
    "AutoRangeLine",
    "AutoRangeResult",
    "STANDARD_LINES",
    "line_options",
    "find_line",
    "derive_range_string",
]


# ---------------------------------------------------------------------------
# Standard position/line catalog
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AutoRangeLine:
    """One selectable standard position/line in the auto-fill dropdown.

    ``id`` is a stable, marker-safe identifier (used in the option key and the
    test markers). ``label`` is the user-facing dropdown text. ``history`` is
    the blueprint action-history suffix the line maps to (``""`` = SB/BTN open
    root, ``"b200"`` = BB facing a 2 BB open). ``kinds`` is the set of action
    buckets (from :func:`classify_action`) counted as "in range" — raise/jam for
    an aggressive (open / 3-bet) range, call for a flatting range.
    """

    id: str
    label: str
    history: str
    kinds: frozenset[str]
    threshold: float = 0.5


# The first-version catalog: a sensible few standard HUNL lines the blueprint
# covers at every shipped depth. Easy to extend — add an ``AutoRangeLine`` here
# and it appears in the dropdown automatically.
#
# HUNL note: the SB is on the BUTTON (acts first preflop), so the "BTN/SB open"
# IS the RFI root line. The BB faces that open on the ``b200`` (2 BB open) line;
# we split the BB's response into the raise-dominant 3-bet range and the
# call-dominant flat range (the full non-fold "defend" range is ~100% vs a
# min-open in HUNL — mathematically correct but not a useful auto-fill, so we
# expose its two actionable sub-ranges instead).
STANDARD_LINES: tuple[AutoRangeLine, ...] = (
    AutoRangeLine(
        id="btn_open",
        label="BTN/SB open (RFI)",
        history="",
        kinds=frozenset({"raise", "jam"}),
    ),
    AutoRangeLine(
        id="bb_3bet_vs_open",
        label="BB 3-bet vs open (2bb)",
        history="b200",
        kinds=frozenset({"raise", "jam"}),
    ),
    AutoRangeLine(
        id="bb_call_vs_open",
        label="BB flat-call vs open (2bb)",
        history="b200",
        kinds=frozenset({"call"}),
    ),
)


@dataclass
class AutoRangeResult:
    """Outcome of an auto-range derivation.

    ``range_string`` is the comma-separated PIO range (empty when nothing was
    derivable). ``combo_count`` is the number of concrete combos it covers
    (sum over kept classes). ``classes`` is the ordered list of kept hand-class
    labels. ``source`` echoes the route the blueprint took ("blueprint" /
    "interpolated" / "live" / "unavailable") so the caller can note when no
    coverage exists. ``note`` carries a human-readable fallback reason when the
    derivation could not produce a real range.
    """

    range_string: str = ""
    combo_count: int = 0
    classes: list[str] = field(default_factory=list)
    source: str = "unavailable"
    note: str | None = None


# ---------------------------------------------------------------------------
# Catalog helpers
# ---------------------------------------------------------------------------


def line_options() -> dict[str, str]:
    """Return the ``{line_id: label}`` option map for the dropdown."""
    return {ln.id: ln.label for ln in STANDARD_LINES}


def find_line(line_id: str) -> AutoRangeLine | None:
    """Return the catalog entry for ``line_id``, or ``None`` if unknown."""
    for ln in STANDARD_LINES:
        if ln.id == line_id:
            return ln
    return None


# ---------------------------------------------------------------------------
# Derivation
# ---------------------------------------------------------------------------


def _combo_count_for_class(hand_class: str) -> int:
    """Number of concrete combos a 169-class label expands to.

    Imported lazily (and defensively) so this module stays importable without
    the full ``ui.state`` graph during isolated unit tests.
    """
    try:
        from ui.state import enumerate_combos
    except Exception:  # noqa: BLE001 -- fall back to canonical counts
        # Pairs -> 6, suited -> 4, offsuit -> 12.
        if len(hand_class) == 2:
            return 6
        return 4 if hand_class.endswith("s") else 12
    return len(enumerate_combos(hand_class))


def _classes_in_range(
    per_class: dict[str, dict[str, float]],
    kinds: frozenset[str],
    threshold: float,
) -> list[str]:
    """Select hand classes whose mass on ``kinds`` clears ``threshold``.

    For each class, normalize its action distribution (defensive — blueprint
    vectors can be slightly off-normalized), sum the probability on the action
    buckets in ``kinds``, and keep the class when that fraction is at least
    ``threshold``. Order follows ``per_class`` iteration (the blueprint's class
    order), which is stable per shard.
    """
    kept: list[str] = []
    for hand_class, action_map in per_class.items():
        if not isinstance(action_map, dict) or not action_map:
            continue
        total = sum(float(v) for v in action_map.values())
        if total <= 0.0:
            continue
        in_mass = sum(
            float(v)
            for label, v in action_map.items()
            if classify_action(str(label)) in kinds
        )
        if in_mass / total >= threshold:
            kept.append(str(hand_class))
    return kept


def _per_class_for_line(
    router: BlueprintRouter,
    *,
    stack_bb: int,
    ante: str | float | int,
    history: str,
) -> tuple[dict[str, dict[str, float]], str]:
    """Fetch the per-class action map + route source for a line.

    The root line (``history == ""``) comes straight from
    :meth:`BlueprintRouter.lookup_chart`; deeper lines are pulled from
    :meth:`BlueprintRouter.extract_all_lines` keyed by the normalized history.
    Returns ``({}, source)`` when the line has no coverage at this depth.
    """
    if not history:
        info = router.lookup_chart(stack_bb=stack_bb, ante=ante, action_history="")
        source = getattr(info.source, "value", str(info.source))
        return dict(info.per_class), source

    # Deeper line: route source is whatever lookup_chart reports for this
    # (depth, ante); the per-class map comes from the all-lines extraction.
    info = router.lookup_chart(stack_bb=stack_bb, ante=ante, action_history="")
    source = getattr(info.source, "value", str(info.source))
    all_lines = router.extract_all_lines(stack_bb=stack_bb, ante=ante)
    key = "||p|" + history
    per_class = all_lines.get(key) or all_lines.get(history) or {}
    return dict(per_class), source


def derive_range_string(
    router: BlueprintRouter | None,
    *,
    line_id: str,
    stack_bb: int,
    ante: str | float | int = 0.0,
) -> AutoRangeResult:
    """Derive a range string for a standard line at ``(stack_bb, ante)``.

    Looks up the chosen line's per-class blueprint strategy (routing through the
    same exact/interpolated decision the Preflop Chart uses), projects it into a
    hand-class selection via :func:`_classes_in_range`, and joins the kept
    classes into a comma-separated PIO range string.

    Returns an :class:`AutoRangeResult`. On any failure path (no bundle, unknown
    line, no coverage at this depth, empty projection) the result carries an
    empty ``range_string`` and a ``note`` explaining why, so the caller can show
    a clear message rather than silently filling an empty range.
    """
    line = find_line(line_id)
    if line is None:
        return AutoRangeResult(note=f"Unknown line id {line_id!r}")
    if router is None:
        return AutoRangeResult(
            source="unavailable",
            note="No preflop blueprint bundle on disk (auto-fill unavailable).",
        )

    try:
        per_class, source = _per_class_for_line(
            router,
            stack_bb=int(stack_bb),
            ante=ante,
            history=line.history,
        )
    except Exception:  # noqa: BLE001 -- blueprint read failure is non-fatal
        logger.exception("auto-range blueprint lookup failed for %s", line_id)
        return AutoRangeResult(
            source="unavailable",
            note="Blueprint lookup failed for this line.",
        )

    if source == "live" or not per_class:
        return AutoRangeResult(
            source=source,
            note=(
                f"No blueprint coverage for '{line.label}' at {int(stack_bb)} BB "
                "(would need a live solve)."
            ),
        )

    classes = _classes_in_range(per_class, line.kinds, line.threshold)
    if not classes:
        return AutoRangeResult(
            source=source,
            note=f"'{line.label}' projects to an empty range at {int(stack_bb)} BB.",
        )

    combo_count = sum(_combo_count_for_class(c) for c in classes)
    return AutoRangeResult(
        range_string=", ".join(classes),
        combo_count=combo_count,
        classes=classes,
        source=source,
    )
