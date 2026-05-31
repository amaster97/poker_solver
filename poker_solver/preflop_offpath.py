"""GUI-agnostic preflop off-path detection + cleaning.

This module owns the *engine-agnostic* logic for deciding which preflop
hand classes are "off-path" at a given action node, and for producing a
cleaned per-line strategy table where those off-path entries are folded.

It was lifted verbatim out of the GUI-private ``ui/views/preflop_chart.py``
so the same primitives back BOTH the chart widget (which MARKs off-path
cells and greys them with an em-dash) and a programmatic API
(:func:`strategy_table`) that cleans off-path noise by default. The module
has NO nicegui / AppState coupling — every public function takes a pure
``by_line`` dict (or the raw ``average_strategy`` mapping) and returns plain
dicts.

Data shapes
-----------
* ``by_line`` — ``{ line -> { hand_class -> { action_label -> prob } } }``
  where ``line`` is the FULL history suffix (``"||p|"`` for the SB-open root,
  ``"||p|b200"`` for BB facing a 2bb open, ``"||p|b200r400r1000"`` for a
  4-bet node, …). This is the projection produced by
  :func:`project_by_line` (live solves) and by
  ``ui.blueprint_router.BlueprintRouter.extract_all_lines`` (blueprint
  routes); both share the exact same shape.
* ``average_strategy`` — the raw ``rust_out["average_strategy"]`` mapping
  ``"{hole_str}||p|<history>" -> [probs]`` (1326 kernel) or
  ``"{class_label}||p|<history>" -> [probs]`` (class169 kernel). This is the
  SOURCE OF TRUTH consumed by exploitability / blueprint generation /
  differential tests and is NEVER mutated by anything in this module.

Off-path rule
-------------
A hand class is off-path at a node when EITHER:

* (reach rule) its normalized reach is below
  :data:`_OFF_PATH_REACH_FRACTION` (0.5% of the total reach mass at the
  node), OR
* (fold rule) it is FOLD-DOMINANT — folds ≥ :data:`_FOLD_DOMINANT_THRESHOLD`
  at any of the displayed player's ancestor decision nodes on the line.

Both signals come from a SINGLE walk per class
(:func:`reach_and_fold_dominant`). FAIL-SAFE: if that walk is ``None`` for
ANY class on the line (a prior node missing, e.g. a partial live snapshot),
nothing is marked off-path for that line.

Public API
----------
* :func:`mark_off_path` — ``{hand_class -> off_path}`` for one line.
* :func:`clean_off_path` — a NEW deep-copied ``by_line`` with off-path
  entries overwritten to fold.
* :func:`project_by_line` — pure ``average_strategy`` -> ``by_line``.
* :func:`strategy_table` — one-call ``average_strategy`` -> ``by_line``,
  cleaned by default (``clean=True``).
"""

from __future__ import annotations

import copy
import re
from typing import Any

from poker_solver.card import RANKS

# --------------------------------------------------------------------------- #
# Hand-class / key parsing (engine key -> 169 class + history suffix)
# --------------------------------------------------------------------------- #
#
# The Rust binding ``_rust.solve_hunl_preflop_rvr`` emits strategy keys of the
# form ``"{hole_str}||p|<history>"`` where ``hole_str`` is the two-card pair in
# Rust's format (rank + suit chars). ``RANKS = "23456789TJQKA"``,
# ``SUITS = "shdc"`` per ``poker_solver/range_aggregator.py:_hole_string_rust``.
# The hole_str is exactly 4 characters; the suffix is everything after that.
#
# These helpers were moved here from ``ui/state.py`` so the pure projection
# (:func:`project_by_line`) is GUI-agnostic; ``ui/state.py`` re-exports them so
# its historical import surface stays intact.

_RANKS_RUST_ORDER: str = "23456789TJQKA"
_SUITS_RUST_ORDER: str = "shdc"
_PREFLOP_KEY_SEP: str = "||p|"


def hand_class_label(rank1: int, rank2: int, suited: bool) -> str:
    """Return the canonical hand-class label for two ranks + suited flag.

    Args:
        rank1: rank value in [2, 14] (Ace == 14).
        rank2: rank value in [2, 14].
        suited: ignored when ``rank1 == rank2`` (pairs are unsuited tokens).

    Returns:
        ``"AA"``, ``"AKs"``, ``"72o"``, etc. Higher rank always first.
    """
    if not (2 <= rank1 <= 14 and 2 <= rank2 <= 14):
        raise ValueError(f"ranks out of [2, 14]: {rank1}, {rank2}")
    hi, lo = max(rank1, rank2), min(rank1, rank2)
    hi_char = RANKS[hi - 2]
    lo_char = RANKS[lo - 2]
    if hi == lo:
        return f"{hi_char}{lo_char}"
    return f"{hi_char}{lo_char}{'s' if suited else 'o'}"


def _all_169_hand_classes() -> frozenset[str]:
    """The 169 canonical Pio hand-class labels (AA, AKs, AKo, ..., 22)."""
    out: set[str] = set()
    for r1 in range(2, 15):
        for r2 in range(2, 15):
            if r1 == r2:
                out.add(hand_class_label(r1, r2, suited=False))  # pair
            else:
                out.add(hand_class_label(r1, r2, suited=True))  # suited
                out.add(hand_class_label(r1, r2, suited=False))  # offsuit
    return frozenset(out)


_ALL_169_HAND_CLASSES: frozenset[str] = _all_169_hand_classes()


def _split_preflop_key(key: str) -> tuple[str | None, str]:
    """Split a Rust preflop key into (hole_str, history_suffix).

    Returns ``(None, "")`` when the key is malformed (doesn't start with a
    valid 4-char hole_str). Defensive — the engine emits well-formed keys but
    we tolerate noise so a bad key doesn't crash the projection.
    """
    if len(key) < 4:
        return (None, "")
    hole_str = key[:4]
    # Validate: 4 chars, rank/suit/rank/suit per RANKS_RUST_ORDER /
    # SUITS_RUST_ORDER.
    if not (
        hole_str[0] in _RANKS_RUST_ORDER
        and hole_str[1] in _SUITS_RUST_ORDER
        and hole_str[2] in _RANKS_RUST_ORDER
        and hole_str[3] in _SUITS_RUST_ORDER
    ):
        return (None, "")
    return (hole_str, key[4:])


def _hand_class_from_hole_str(hole_str: str) -> str | None:
    """Convert a Rust ``hole_str`` (e.g. "AsKh") to a hand-class label.

    Mirrors the inverse of ``poker_solver.range_aggregator._hole_string_rust``.
    Returns ``None`` on malformed input.
    """
    if len(hole_str) != 4:
        return None
    r1_char, s1_char = hole_str[0], hole_str[1]
    r2_char, s2_char = hole_str[2], hole_str[3]
    if (
        r1_char not in _RANKS_RUST_ORDER
        or r2_char not in _RANKS_RUST_ORDER
        or s1_char not in _SUITS_RUST_ORDER
        or s2_char not in _SUITS_RUST_ORDER
    ):
        return None
    r1 = _RANKS_RUST_ORDER.index(r1_char) + 2
    r2 = _RANKS_RUST_ORDER.index(r2_char) + 2
    suited = s1_char == s2_char
    if r1 == r2 and s1_char == s2_char:
        # Same card twice — malformed.
        return None
    return hand_class_label(r1, r2, suited)


def _split_class169_key(key: str) -> tuple[str | None, str]:
    """Split a class-169 engine key into (class_label, history_suffix).

    The ``solve_hunl_preflop_rvr_class169`` kernel emits keys of the form
    ``"<class_label>||p|<history>"`` (e.g. ``"AA||p|"`` for the SB AA root
    decision, ``"T4s||p|b400r1900A"`` for a deeper node). The class label is
    the standard Pio chart label (2 chars for a pair like ``"AA"``, 3 chars
    for ``"AKs"`` / ``"AKo"``). The history suffix returned here matches the
    ``"||p|<history>"`` shape that :func:`_split_preflop_key` returns for the
    1326 kernel, so both feed the same per-line projection unchanged.

    Returns ``(None, "")`` when the key lacks the separator or the prefix is
    not a recognized hand-class label (defensive against malformed keys).
    """
    idx = key.find(_PREFLOP_KEY_SEP)
    if idx < 0:
        return (None, "")
    cls = key[:idx]
    if cls not in _ALL_169_HAND_CLASSES:
        return (None, "")
    # Re-attach the separator so the suffix shape matches _split_preflop_key's
    # ``"||p|<history>"`` (the per-line projection keys on this exact suffix).
    return (cls, key[idx:])


def _action_labels_for_count(count: int) -> list[str]:
    """Build the default action-label list for a preflop tree.

    The Phase A engine emits actions in the canonical order
    ``fold, call/check, open_2, open_3, open_4, open_5, all_in``
    (per ``crates/cfr_core/src/preflop_rvr.rs``). Counts below the full menu
    drop the last entries; counts above add ``raise_*`` placeholders. This is
    a best-effort label set that the chart can display; the engine's true
    labels live in the Rust binding and aren't currently exported.
    """
    canonical = [
        "fold",
        "call",
        "open_2",
        "open_3",
        "open_4",
        "open_5",
        "all_in",
    ]
    if count <= 0:
        return canonical
    if count <= len(canonical):
        return canonical[:count]
    # Pad with raise_N placeholders.
    extras = [f"raise_{i}" for i in range(count - len(canonical))]
    return canonical + extras


# --------------------------------------------------------------------------- #
# Pure projection: raw average_strategy -> by_line
# --------------------------------------------------------------------------- #


def project_by_line(
    average_strategy: dict[str, Any] | None, *, class169: bool = False
) -> dict[str, dict[str, dict[str, float]]]:
    """Project a raw ``average_strategy`` mapping into a per-LINE summary.

    Keeps EVERY action line the engine produced. Returns a nested mapping::

        { history_str -> { hand_class -> { action_label -> prob } } }

    where ``history_str`` is the action-line suffix from the Rust infoset key
    (``"||p|"`` is the root / SB open; deeper lines append action tokens, e.g.
    ``"||p|b200"`` for the BB's response after an open, a 3-bet node, etc.).
    Within a line, probabilities are averaged across the concrete combos that
    map to the same hand class.

    ``class169`` selects the key parser:
      * ``False`` (default): ``"{hole_str}||p|<history>"`` — the 4-char
        hole_str is mapped to its 169 class and combos are averaged.
      * ``True``: ``"{class_label}||p|<history>"`` — the prefix IS already the
        class label; there is exactly one entry per (class, line) so the
        per-class "average" is the entry itself.

    PURE: ``average_strategy`` is read-only; the returned table is freshly
    built and shares no mutable state with the input.
    """
    if not average_strategy:
        return {}
    # history -> class -> (running sum of prob vectors, count)
    by_line: dict[str, dict[str, tuple[list[float], int]]] = {}
    for key, probs in average_strategy.items():
        if not probs:
            continue
        if class169:
            cls, hist = _split_class169_key(str(key))
        else:
            hole_str, hist = _split_preflop_key(str(key))
            cls = (
                _hand_class_from_hole_str(hole_str)
                if hole_str is not None
                else None
            )
        if cls is None:
            continue
        line_slot = by_line.setdefault(hist, {})
        prev = line_slot.get(cls)
        vec = [float(p) for p in probs]
        if prev is None:
            line_slot[cls] = (vec, 1)
        else:
            acc, cnt = prev
            if len(acc) == len(vec):
                line_slot[cls] = ([a + b for a, b in zip(acc, vec)], cnt + 1)
            # else: ragged action counts within a class — keep the first.

    out: dict[str, dict[str, dict[str, float]]] = {}
    for hist, class_map in by_line.items():
        line_out: dict[str, dict[str, float]] = {}
        for cls, (acc, cnt) in class_map.items():
            n = len(acc)
            if n == 0 or cnt == 0:
                continue
            labels = _action_labels_for_count(n)
            line_out[cls] = {labels[i]: acc[i] / cnt for i in range(n)}
        if line_out:
            out[hist] = line_out
    return out


# --------------------------------------------------------------------------- #
# Preflop line (node) token grammar
# --------------------------------------------------------------------------- #
#
# The engine emits strategy keys shaped ``"{hole_str}||p|<tokens>"``; the
# ``by_line`` keys are the ``"||p|<tokens>"`` history suffix per reachable
# node. Token grammar (verified empirically against
# ``_rust.solve_hunl_preflop_rvr``):
#
#   ``||p|``                 root — SB's first decision
#   ``c``                    SB limps (call)
#   ``b<amt>``               a bet/open to <amt> (amt = BB * 100)
#   ``r<amt>``               a raise/re-raise to <amt>
#   ``A``                    facing an all-in (next actor folds/calls)

_LINE_TOKEN_RE = re.compile(r"c|b\d+|r\d+|A")


def _line_body(suffix: str | None) -> str:
    """Strip the constant root marker (``||p|`` or normalized ``|p|``).

    Returns the post-marker token body (possibly empty for the root).
    """
    if suffix is None:
        return ""
    body = suffix
    if body.startswith("||p|"):
        body = body[len("||p|") :]
    elif body.startswith("|p|"):  # defensive: tolerate a normalized variant
        body = body[len("|p|") :]
    return body


def preflop_line_actor(suffix: str | None) -> str:
    """Return which player ACTS at node ``suffix`` — ``"SB"`` or ``"BB"``.

    Decodes the post-``||p|`` token body (``c``/``b<amt>``/``r<amt>``/``A``)
    and applies the engine's turn rule: the root (no tokens) is the SB's first
    decision, and play alternates with each token, so an EVEN token count means
    the SB acts and an ODD count means the BB acts. ``None`` / the bare root /
    an undecodable suffix all map to ``"SB"`` (the root actor).

    Engine-confirmed: the preflop root has ``cur_player == 0`` (SB).
    """
    body = _line_body(suffix)
    if body == "":
        return "SB"
    tokens = _LINE_TOKEN_RE.findall(body)
    # Undecodable grammar -> treat as the root actor so the badge still renders.
    if "".join(tokens) != body:
        return "SB"
    return "SB" if len(tokens) % 2 == 0 else "BB"


# --------------------------------------------------------------------------- #
# Off-path detection thresholds + labels
# --------------------------------------------------------------------------- #

# Threshold (fraction of total reach mass) below which a hand class is treated
# as "off-path" / not-in-range at the displayed node. 0.5% — at a 4-bet node
# folded-out hands carry reach ≈ 0 (orders of magnitude below this) while
# genuine 3-bet hands sit well above it.
_OFF_PATH_REACH_FRACTION: float = 0.005

# Fold-probability threshold above which a hand class is treated as
# fold-dominant at one of the displayed player's ancestor decision nodes.
# Once a hand folds ~100% at a node, every deeper action on this line is
# off-path regardless of how the normalized reach lands at a sparse deep node
# — this complements the pure reach threshold for fold-dominant hands it can
# miss (e.g. a node where only a handful of classes survive can inflate the
# survivors' normalized share). The continuing-action probabilities the reach
# walk multiplies in are the NON-fold actions, so we read the FOLD mass here.
_FOLD_DOMINANT_THRESHOLD: float = 0.99

# All-in-probability threshold above which a hand class is treated as
# all-in-dominant at one of the displayed player's ancestor decision nodes.
# Once a hand goes all-in ~100% at a node there is NO further voluntary action,
# so every deeper line is off-path — it carries over exactly like fold-dominance
# (the actor cannot act again after committing the stack). Mirrors
# ``_FOLD_DOMINANT_THRESHOLD``. The all-in mass is read from the EXACT all-in
# label (``_ALL_IN_LABEL``); it is NEVER summed into the bet/raise aggregation
# (``_bet_labels`` excludes ``all_in`` — see ``_bet_labels``).
_ALL_IN_DOMINANT_THRESHOLD: float = 0.99

# Call/limp-probability threshold above which a hand class is treated as
# call-dominant ("called & closed the action") at one of the displayed player's
# ancestor decision nodes WHEN the line continues with further aggression. A
# hand that calls ~100% has closed the action (continued passively) and cannot
# face a later re-raise on this line — the A3o/K3s case (BB flat-calls the open
# 100%, so it is not in range on the subsequent 4-bet line).
_CALL_DOMINANT_THRESHOLD: float = 0.99

# The engine's fold-action label in the per-class node-strategy maps. Verified
# against the source-of-truth ``_action_labels_for_count`` (which the
# projection uses to build ``by_line``): "fold" is canonically label index 0
# for every node. Pinned as a constant so a future relabel is a one-line
# change.
_FOLD_LABEL: str = "fold"

# The engine's all-in / call action labels in the per-class node-strategy maps
# (canonical labels from ``_action_labels_for_count``). Pinned as constants so a
# future relabel is a one-line change. ``_ALL_IN_LABEL`` is deliberately NOT in
# ``_bet_labels`` (which only returns ``open_*`` / ``raise_*``), so all-in mass
# is never folded into the bet/raise aggregation.
_ALL_IN_LABEL: str = "all_in"
_CALL_LABEL: str = "call"

# Off-path reason codes returned by :func:`mark_off_path_with_reason`
# (``None`` == on-path). Priority order when several could apply across the
# ancestor walk: fold > all_in > called_closed > low_reach.
REASON_FOLDED: str = "folded"
REASON_ALL_IN: str = "all_in"
REASON_CALLED_CLOSED: str = "called_closed"
REASON_LOW_REACH: str = "low_reach"


def _bet_labels(node_strat: dict[str, dict[str, float]]) -> list[str]:
    """Return a node's bet/raise action labels in menu order.

    The engine reuses the same menu-position labels (``open_2 … open_5``,
    plus any ``raise_N`` placeholders) for opens AND re-raises. Fold / call /
    all_in are excluded — those are mapped from their own tokens. Order is the
    insertion order of the per-class action dict, which is the canonical menu
    order from :func:`_action_labels_for_count`.
    """
    if not node_strat:
        return []
    sample = next(iter(node_strat.values()))
    return [lbl for lbl in sample if lbl.startswith(("open_", "raise_"))]


def _sibling_bet_tokens(
    by_line: dict[str, dict[str, dict[str, float]]], prefix: str
) -> list[str]:
    """Return the bet/raise child tokens one ply below ``prefix``, sorted by size.

    e.g. for ``prefix == "||p|b200"`` this returns ``["r400", "r500", "r600",
    "r700"]`` (the BB's re-raise sizes). Sorted ascending by the embedded
    amount so the k-th sibling lines up with the k-th bet/raise label — the
    menu labels are also size-ordered, so rank-matching is size-matching.
    """
    body = _line_body(prefix)
    plen = len(_LINE_TOKEN_RE.findall(body))
    sibs: set[str] = set()
    for line in by_line:
        toks = _LINE_TOKEN_RE.findall(_line_body(line))
        if (
            len(toks) == plen + 1
            and "".join(toks[:plen]) == body
            and toks[plen]
            and toks[plen][0] in "br"
        ):
            sibs.add(toks[plen])
    return sorted(sibs, key=lambda t: int(t[1:]))


def _label_for_token(
    by_line: dict[str, dict[str, dict[str, float]]],
    prefix: str,
    token: str,
    node_strat: dict[str, dict[str, float]],
) -> str | None:
    """Map a history token to the continuing-action label at ``prefix``.

    * ``c`` -> ``"call"`` (limp / flat / check — the engine's call label)
    * ``A`` -> ``"all_in"``
    * ``b<amt>`` / ``r<amt>`` -> the bet/raise label at the token's RANK among
      its same-node siblings. The engine emits menu-position labels
      (``open_2 … open_5``), NOT amount-suffixed ones, so we match by size rank:
      the smallest sibling bet maps to the first bet label, etc. (verified
      against the live ``solve_hunl_preflop_rvr`` binding).

    Returns ``None`` when the token can't be resolved (unknown grammar / the
    sibling set is missing) so the reach walk FAILs SAFE.
    """
    if token == "c":
        return "call"
    if token == "A":
        return "all_in"
    sibs = _sibling_bet_tokens(by_line, prefix)
    labels = _bet_labels(node_strat)
    if token in sibs:
        k = sibs.index(token)
        if k < len(labels):
            return labels[k]
    return None


def _is_bet_token(token: str) -> bool:
    """``True`` for a bet/open/raise history token (``b<amt>`` / ``r<amt>``)."""
    return bool(token) and token[0] in "br"


def reach_and_reason(
    by_line: dict[str, dict[str, dict[str, float]]] | None,
    hand: str,
    target_hist: str | None,
) -> tuple[float, str | None] | None:
    """Walk the displayed player's line once; return ``(reach, block_reason)``.

    Single pass over the DISPLAYED player's own ancestor decision nodes on this
    line (the same walk :func:`reach` does). Returns a tuple:

      * ``reach`` — the product of this player's continuing-action probabilities
        (root / no gating nodes -> ``1.0``). This is the EXISTING reach signal.
        SIZE-AGNOSTIC at the player's OWN raise nodes: when the continuing token
        is a bet/raise (``b…``/``r…``) we credit the hand's TOTAL aggression mass
        (summed over EVERY bet/raise label at that node), NOT just the single
        matched-size label — a hand that raised by ANY size took this aggressive
        action and is in this branch. Call/limp (``c``) and all-in (``A``) stay
        exact (single, unambiguous actions). This fixes pure-size-mixers (e.g.
        AA at ``b300r700r1500`` 3-bets ~98% but almost purely to ``r900``, so the
        single-``r700`` reading was ~0 and falsely flagged it off-path).
      * ``block_reason`` — the reason code of the EARLIEST ancestor decision node
        of this player on the line that DOMINANTLY blocks the deeper line, or
        ``None`` when no single ancestor dominantly blocks. The codes (with their
        per-node priority fold > all_in > called_closed):

          - :data:`REASON_FOLDED` — fold prob ≥ :data:`_FOLD_DOMINANT_THRESHOLD`.
            Once a hand folds ~100% at a node, every deeper action is off-path.
          - :data:`REASON_ALL_IN` — all-in prob ≥
            :data:`_ALL_IN_DOMINANT_THRESHOLD`. After going all-in there is NO
            further voluntary action, so the hand carries OFF-PATH onto every
            deeper line (this is the bug the all-in rule fixes: previously only
            fold was checked, so an all-in-dominant hand was wrongly left
            in-range on a size-raise continuation). The all-in mass is read from
            the EXACT :data:`_ALL_IN_LABEL` — it is NEVER summed into the
            bet/raise aggregation below (``_bet_labels`` excludes ``all_in``).
          - :data:`REASON_CALLED_CLOSED` — at a node where the line CONTINUES
            with further aggression (a bet/raise token) the hand's call prob is
            ≥ :data:`_CALL_DOMINANT_THRESHOLD`: it flat-called and CLOSED the
            action, so it cannot face the later re-raise on this line (the
            A3o/K3s case — BB calls the open 100%, off-path on the 4-bet line).

    Returns ``None`` (FAIL-SAFE) when the walk can't be fully computed —
    ``by_line`` is missing, a prior node along the line isn't present, the hand
    class is absent at a gating node, or a token can't be mapped to a label.
    Callers must NOT mark anything off-path for a line when this is ``None`` for
    any class. A missing dominance label at a node does NOT trip the fail-safe
    and does NOT mark a block (same posture as a missing continuing label that
    contributes 0.0): we only set a block on an affirmative ≥ threshold reading.
    """
    if by_line is None:
        return None
    toks = _LINE_TOKEN_RE.findall(_line_body(target_hist))
    actor = preflop_line_actor(target_hist)
    r = 1.0
    block_reason: str | None = None
    for i, tok in enumerate(toks):
        prefix = "||p|" + "".join(toks[:i])
        # Only the displayed player's OWN decisions gate their reach.
        if preflop_line_actor(prefix) != actor:
            continue
        node = by_line.get(prefix)
        if node is None or hand not in node:
            return None  # FAIL-SAFE: can't compute -> don't mark
        node_strat = node[hand]
        # Dominance checks. ``block_reason`` records the EARLIEST blocking
        # ancestor only (the ``is None`` guard freezes the first hit); per-node
        # priority is fold > all_in > called_closed. We do NOT ``break`` — the
        # reach product below keeps its EXACT historical semantics (a fold-/
        # call-dominant hand multiplies in ~0 at this node, so ``reach`` lands at
        # ~0 just as before), and the deeper own-nodes still exist in ``by_line``
        # (other hands reach them). A missing dominance label -> 0.0 (no block),
        # matching the missing-continuing-label posture.
        if block_reason is None:
            # Fold-propagation: a ≥99% fold makes everything downstream off-path.
            if node_strat.get(_FOLD_LABEL, 0.0) >= _FOLD_DOMINANT_THRESHOLD:
                block_reason = REASON_FOLDED
            # All-in carries over: no further voluntary action after committing
            # the stack. Read the EXACT all-in label (never the bet aggregate).
            elif node_strat.get(_ALL_IN_LABEL, 0.0) >= _ALL_IN_DOMINANT_THRESHOLD:
                block_reason = REASON_ALL_IN
            # Called-and-closed: the line continues with aggression (a bet/raise
            # token) but the hand flat-called ~100% here, closing the action, so
            # it cannot reach the deeper re-raise.
            elif (
                _is_bet_token(tok)
                and node_strat.get(_CALL_LABEL, 0.0) >= _CALL_DOMINANT_THRESHOLD
            ):
                block_reason = REASON_CALLED_CLOSED
        label = _label_for_token(by_line, prefix, tok, node)
        if label is None:
            return None
        # SIZE-AGNOSTIC reach crediting. The blueprint's raise nodes offer
        # MULTIPLE sizes (e.g. at ``||p|b300`` the BB's 3-bet menu is
        # ``r600``/``r700``/``r900``). The continuing token records the size the
        # CHART LINE took (``r700`` on ``b300r700r1500``), but the hand may put
        # almost all of its aggression on a DIFFERENT size of the same action
        # (AA 3-bets ~98% but almost purely to ``r900``, P(r700)≈0.006). The
        # size siblings are NOT mutually-exclusive paths for the off-path
        # question — a hand that raised by ANY size took this aggressive action
        # and is in this branch; only genuine folds/limps (never raised) are
        # off-path. So when the continuing action is a bet/raise we credit the
        # hand's TOTAL aggression mass (sum over EVERY bet/raise label at this
        # node), not just the single matched-size label. Call/limp (``c``) and
        # all-in (``A``) stay exact — they are single, unambiguous actions.
        # NOTE: the forthcoming postflop off-path module MUST apply the same
        # principle — postflop bets/raises are likewise offered at multiple
        # sizes, so reach must sum over all bet/raise labels, never one size.
        if _is_bet_token(tok):
            bet_labels = _bet_labels(node)
            r *= sum(node_strat.get(lbl, 0.0) for lbl in bet_labels)
        else:
            r *= node_strat.get(label, 0.0)
    return r, block_reason


def reach_and_fold_dominant(
    by_line: dict[str, dict[str, dict[str, float]]] | None,
    hand: str,
    target_hist: str | None,
) -> tuple[float, bool] | None:
    """Walk the line; return ``(reach, dominant_block)``.

    Backward-compatible thin wrapper over :func:`reach_and_reason`. The boolean
    is ``True`` when the hand is dominantly blocked at some ancestor (fold-,
    all-in- or call-dominant). The name (and its historical ``fold_dominant``
    semantics) is retained so existing call sites + re-exports stay green; the
    all-in / called-closed blocks are NEW and also flip the boolean ``True``.

    Returns ``None`` (FAIL-SAFE) when the walk can't be fully computed.
    """
    rr = reach_and_reason(by_line, hand, target_hist)
    if rr is None:
        return None
    r, block_reason = rr
    return r, (block_reason is not None)


def reach(
    by_line: dict[str, dict[str, dict[str, float]]] | None,
    hand: str,
    target_hist: str | None,
) -> float | None:
    """Compute a hand class's reach probability at node ``target_hist``.

    Walks the action line token-by-token, multiplying in only the DISPLAYED
    player's own continuing-action probabilities (the opponent's decisions
    don't gate this player's reach to one of *their own* nodes). The root
    (no tokens) has reach 1.0 for every class — uniform, so nothing is marked.

    ``by_line`` is the ``{ line -> { hand_class -> { label -> prob } } }`` map.
    Returns ``None`` (FAIL-SAFE) when reach can't be fully computed — ``by_line``
    is missing, a prior node along the line isn't present, the hand class is
    absent at a gating node, or a token can't be mapped to a label. Callers must
    NOT mark anything off-path for a line when reach is ``None`` for any class.

    Thin wrapper over :func:`reach_and_fold_dominant` that drops the
    fold-dominant flag, preserving the historical ``float | None`` contract.
    """
    rfd = reach_and_fold_dominant(by_line, hand, target_hist)
    if rfd is None:
        return None
    return rfd[0]


# --------------------------------------------------------------------------- #
# Public primitives: mark + clean
# --------------------------------------------------------------------------- #


def mark_off_path_with_reason(
    by_line: dict[str, dict[str, dict[str, float]]] | None,
    line: str | None,
    hand_classes: list[str] | None = None,
) -> dict[str, str | None]:
    """Return ``{hand_class -> reason}`` for a single ``line`` in ``by_line``.

    ``reason`` is ``None`` for ON-PATH classes, or one of the off-path codes:

      * :data:`REASON_FOLDED` — fold-dominant at an ancestor (highest priority).
      * :data:`REASON_ALL_IN` — all-in-dominant at an ancestor (carries over —
        no voluntary action after committing the stack).
      * :data:`REASON_CALLED_CLOSED` — the hand flat-called ~100% at a blocking
        ancestor where the line continued with further aggression, closing the
        action (the A3o/K3s case).
      * :data:`REASON_LOW_REACH` — generic: normalized reach below
        :data:`_OFF_PATH_REACH_FRACTION` with no single dominating ancestor.

    The dominance reason is derived from the EARLIEST blocking ancestor; across
    classes the priority is ``folded > all_in > called_closed > low_reach``
    (a dominant block always outranks the generic reach rule).

    Both signals come from a SINGLE walk per class via :func:`reach_and_reason`.
    FAIL-SAFE: if that walk is ``None`` for ANY class (a prior node missing, e.g.
    a partial live snapshot), nothing is marked — every class returns ``None``.
    The root node has no gating nodes -> uniform reach + no dominance, so nothing
    is marked there.

    ``hand_classes`` defaults to the classes present at ``line`` in ``by_line``
    (or the empty set when the line / map is absent).
    """
    if hand_classes is None:
        node = (by_line or {}).get(line or "", {})
        hand_classes = list(node.keys())
    reaches: dict[str, float] = {}
    block_reason: dict[str, str | None] = {}
    for cls in hand_classes:
        rr = reach_and_reason(by_line, cls, line)
        if rr is None:
            # Walk not fully computable for this line -> mark nothing.
            return {cls: None for cls in hand_classes}
        reaches[cls], block_reason[cls] = rr
    # Normalize reach over the NON-dominantly-blocked classes only. A blocked
    # hand's walk short-circuits at the blocking ancestor, so its ``reach`` is
    # the pre-block product (often 1.0) — a meaningless artifact that must NOT
    # inflate the denominator and drag genuine reachers below the threshold.
    # (Pre-block hands that genuinely never reached carry reach 0 and are
    # already excluded from the mass by value.)
    total = sum(
        reaches[cls]
        for cls in hand_classes
        if block_reason[cls] is None
    )

    def _reason_for(cls: str) -> str | None:
        # A dominant blocking ancestor wins outright over the reach rule.
        if block_reason[cls] is not None:
            return block_reason[cls]
        if total <= 0.0:
            # Degenerate (all-zero) reach: the reach rule can't discriminate.
            return None
        if (reaches[cls] / total) < _OFF_PATH_REACH_FRACTION:
            return REASON_LOW_REACH
        return None

    return {cls: _reason_for(cls) for cls in hand_classes}


def mark_off_path(
    by_line: dict[str, dict[str, dict[str, float]]] | None,
    line: str | None,
    hand_classes: list[str] | None = None,
) -> dict[str, bool]:
    """Return ``{hand_class -> off_path}`` for a single ``line`` in ``by_line``.

    A class is off-path when EITHER:
      * (reach rule) its normalized reach is below
        :data:`_OFF_PATH_REACH_FRACTION` (0.5% of the total reach mass), OR
      * (dominance rule) it is dominantly blocked (fold-, all-in- or
        call-dominant) at any of the displayed player's ancestor decision nodes
        on this line.

    Derived from :func:`mark_off_path_with_reason` so the boolean and the reason
    map stay consistent (``off_path == reason is not None``). FAIL-SAFE: when the
    walk isn't fully computable for any class, nothing is marked. The root node
    has no gating nodes -> nothing is marked there.

    ``hand_classes`` defaults to the classes present at ``line`` in ``by_line``
    (or the empty set when the line / map is absent).
    """
    reasons = mark_off_path_with_reason(by_line, line, hand_classes)
    return {cls: reason is not None for cls, reason in reasons.items()}


def _fold_overwrite(node_strat: dict[str, float]) -> dict[str, float]:
    """Return a fresh action dict folded 100% (fold=1.0, everything else 0.0).

    Preserves the node's action-label set so the cleaned table keeps the same
    schema; the fold label (:data:`_FOLD_LABEL`) is forced to 1.0 and is added
    if it was somehow absent.
    """
    cleaned = {label: 0.0 for label in node_strat}
    cleaned[_FOLD_LABEL] = 1.0
    return cleaned


def clean_off_path(
    by_line: dict[str, dict[str, dict[str, float]]] | None,
    line: str | None = None,
) -> dict[str, dict[str, dict[str, float]]]:
    """Return a NEW deep-copied ``by_line`` with off-path entries folded.

    Off-path entries (per :func:`mark_off_path`) are overwritten so the fold
    action (:data:`_FOLD_LABEL`) is 1.0 and every other action is 0.0. On-path
    entries are copied through unchanged.

    * ``line=None`` -> clean EVERY line in ``by_line``, each node evaluated
      independently against its own reach/fold walk.
    * ``line="..."`` -> clean ONLY that line (other lines are deep-copied
      through unchanged).

    NEVER mutates the input — the input ``by_line`` and every nested dict are
    left byte-for-byte intact; the result is a deep copy.
    """
    out = copy.deepcopy(by_line) if by_line else {}
    if not out:
        return out
    target_lines = list(out.keys()) if line is None else [line]
    for ln in target_lines:
        node = out.get(ln)
        if not node:
            continue
        off = mark_off_path(out, ln, list(node.keys()))
        for cls, is_off in off.items():
            if is_off:
                node[cls] = _fold_overwrite(node[cls])
    return out


# --------------------------------------------------------------------------- #
# One-call programmatic API: raw average_strategy -> (cleaned) by_line
# --------------------------------------------------------------------------- #


def strategy_table(
    average_strategy: dict[str, Any] | None,
    *,
    clean: bool = True,
    class169: bool = False,
) -> dict[str, dict[str, dict[str, float]]]:
    """Project a raw ``average_strategy`` mapping into a per-line strategy table.

    ``average_strategy`` is the raw ``rust_out["average_strategy"]`` mapping
    (1326 or class169 kernel — select with ``class169``). Returns the
    ``{ line -> { hand_class -> { action_label -> prob } } }`` table.

    * ``clean=True`` (DEFAULT) -> off-path entries are overwritten to fold
      (the off-path noise the engine stores at unreachable nodes is removed).
    * ``clean=False`` -> the raw projection with the off-path noise intact.

    CRITICAL: the input ``average_strategy`` is NEVER mutated or cleaned.
    Cleaning happens only on the freshly-built returned table (a deep copy
    when ``clean=True``), so internal consumers (exploitability, blueprint
    generation, differential tests) keep reading the raw, unmodified
    strategy.
    """
    by_line = project_by_line(average_strategy, class169=class169)
    if not clean:
        return by_line
    return clean_off_path(by_line, line=None)
