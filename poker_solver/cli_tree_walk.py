"""v1.8.2 — tree-walk + drill-down + JSON/CSV presentation for the river CLI.

The CLI's existing ``poker-solver river`` only reported aggregate first-decision
frequencies. This module adds presentation modes that walk the full decision
tree from a solved ``HUNLSolveResult.average_strategy`` dict:

* :func:`walk_tree` — recursively yield every on-path decision node (and
  optionally off-path "phantom" nodes) along with the strategy at that node,
  its action labels, and the reach probability along the path.
* :func:`decode_action_label` — pretty-print a single action ID given the
  ``ActionContext`` at the decision point (e.g. ``ACTION_BET_75`` →
  ``"bet 75% (750)"``).
* :func:`format_text` / :func:`format_json` / :func:`format_csv` — render the
  walk output in three formats.
* :func:`find_node` — locate a node by its history string (e.g. ``"xb750"``)
  for the ``--node`` drill-down flag.

This module is pure presentation — it never touches engine state outside of
re-walking the game tree from a fresh initial state, and it never mutates the
caller's ``average_strategy`` dict. The walk semantics work uniformly across
the Python and Rust backends because both populate the same key/probs schema
(infoset_key → list[float] of probabilities aligned to
``HUNLPoker.legal_actions(state)``).
"""

from __future__ import annotations

import csv as _csv
import io as _io
import json as _json
import math
from dataclasses import dataclass

from poker_solver.action_abstraction import (
    ACTION_ALL_IN,
    ACTION_BET_33,
    ACTION_BET_75,
    ACTION_BET_100,
    ACTION_BET_150,
    ACTION_BET_200,
    ACTION_CALL,
    ACTION_CHECK,
    ACTION_FOLD,
    ACTION_RAISE_33,
    ACTION_RAISE_75,
    ACTION_RAISE_100,
    ACTION_RAISE_150,
    ACTION_RAISE_200,
    ActionContext,
    compute_bet_amount,
    compute_raise_to,
)
from poker_solver.hunl import HUNLPoker, HUNLState

# ---------------------------------------------------------------------------
# Action label decoder
# ---------------------------------------------------------------------------

_BET_FRACTIONS = {
    ACTION_BET_33: ("33%", 0),
    ACTION_BET_75: ("75%", 1),
    ACTION_BET_100: ("100%", 2),
    ACTION_BET_150: ("150%", 3),
    ACTION_BET_200: ("200%", 4),
}
_RAISE_FRACTIONS = {
    ACTION_RAISE_33: ("33%", 0),
    ACTION_RAISE_75: ("75%", 1),
    ACTION_RAISE_100: ("100%", 2),
    ACTION_RAISE_150: ("150%", 3),
    ACTION_RAISE_200: ("200%", 4),
}


def decode_action_label(action_id: int, ctx: ActionContext) -> str:
    """Pretty-print a single action ID given the current decision context.

    Output format examples:

    * ``ACTION_FOLD`` → ``"fold"``
    * ``ACTION_CHECK`` → ``"check"``
    * ``ACTION_CALL`` → ``"call (250)"`` (chip amount = to_call)
    * ``ACTION_BET_75`` → ``"bet 75% (750)"``
    * ``ACTION_RAISE_100`` → ``"raise to 2500 (100% pot)"``
    * ``ACTION_ALL_IN`` → ``"all-in (9500)"``
    """
    if action_id == ACTION_FOLD:
        return "fold"
    if action_id == ACTION_CHECK:
        return "check"
    if action_id == ACTION_CALL:
        return f"call ({ctx.to_call})"
    if action_id == ACTION_ALL_IN:
        # Both opening and reraise all-ins go through this branch — the chip
        # delta is the player's remaining stack for opening, and we mirror
        # compute_bet_amount which returns the stack for ACTION_ALL_IN.
        return f"all-in ({ctx.stacks[ctx.cur_player]})"
    if action_id in _BET_FRACTIONS:
        label, _ = _BET_FRACTIONS[action_id]
        amount = compute_bet_amount(action_id, ctx)
        return f"bet {label} ({amount})"
    if action_id in _RAISE_FRACTIONS:
        label, _ = _RAISE_FRACTIONS[action_id]
        raise_to = compute_raise_to(action_id, ctx)
        return f"raise to {raise_to} ({label} pot)"
    return f"action_{action_id}"


def parse_token(token: str) -> tuple[str, int | None]:
    """Decompose a single history token into ``(kind, amount)``.

    Used by the test harness + ``--node`` lookup. Returns ``("x", None)`` for
    a check, ``("c", None)`` for call, ``("f", None)`` for fold, ``("A",
    None)`` for all-in, ``("b", N)`` for an opening bet to N chips, ``("r",
    N)`` for a raise to N chips.
    """
    if not token:
        raise ValueError("empty token")
    head = token[0]
    if head in ("x", "c", "f", "A"):
        if len(token) > 1:
            raise ValueError(f"token {token!r}: {head!r} takes no chip amount")
        return (head, None)
    if head in ("b", "r"):
        try:
            return (head, int(token[1:]))
        except ValueError as exc:
            raise ValueError(f"token {token!r}: expected integer chip amount") from exc
    raise ValueError(f"token {token!r}: unknown action kind {head!r}")


def humanize_history(history: str) -> str:
    """Decode a slash-separated history string into a human phrase.

    Empty string → ``"first decision"``. Otherwise we walk each token and
    chain them with " then " — e.g. ``"xb750"`` → ``"check then bet 750"``.
    The output is purely descriptive; it does NOT include amounts in pot
    fractions (caller has the per-node ``ActionContext`` for that).
    """
    if not history:
        return "first decision"
    pieces: list[str] = []
    tokens = _split_history_tokens(history)
    for tok in tokens:
        kind, amt = parse_token(tok)
        if kind == "x":
            pieces.append("check")
        elif kind == "c":
            pieces.append("call")
        elif kind == "f":
            pieces.append("fold")
        elif kind == "A":
            pieces.append("all-in")
        elif kind == "b":
            pieces.append(f"bet {amt}")
        elif kind == "r":
            pieces.append(f"raise to {amt}")
    return " then ".join(pieces)


def _split_history_tokens(history: str) -> list[str]:
    """Split a single-street history string into individual tokens.

    Tokens have format ``[xcfA]`` (1-char) or ``[br]\\d+`` (multi-char). This
    is the inverse of the engine's ``"".join(tokens)`` in ``infoset_key``.
    """
    if not history:
        return []
    out: list[str] = []
    i = 0
    while i < len(history):
        ch = history[i]
        if ch in ("x", "c", "f", "A"):
            out.append(ch)
            i += 1
        elif ch in ("b", "r"):
            j = i + 1
            while j < len(history) and history[j].isdigit():
                j += 1
            if j == i + 1:
                raise ValueError(
                    f"history {history!r}: token at {i} has no chip amount"
                )
            out.append(history[i:j])
            i = j
        else:
            raise ValueError(
                f"history {history!r}: unexpected character {ch!r} at {i}"
            )
    return out


# ---------------------------------------------------------------------------
# Tree walker
# ---------------------------------------------------------------------------


@dataclass
class TreeNode:
    """A decision node visited during the walk.

    Fields:

    * ``history`` — the slash-joined history string (within current street)
      from the infoset key, e.g. ``"xb750"``. Empty string == first decision.
    * ``player`` — the player about to act (0 or 1).
    * ``hole_label`` — pretty rendering of that player's hole. ``"AhKd"`` for
      a fixed combo; ``"range"`` placeholder for range queries.
    * ``infoset_key`` — full key used to look up the strategy in
      ``average_strategy``.
    * ``actions`` — list of ``(action_id, label, prob)`` triples. Sorted in
      the same order as ``legal_actions`` returns.
    * ``reach_prob`` — multiplicative reach probability of this node along
      the path from root, accounting only for own player's actions (we do
      NOT discount by opponent strategy — caller can compute that from
      ``probs`` if they want).
    * ``off_path`` — True when reach prob ≤ ``1e-6``; rendered with the
      [OFF-PATH] marker.
    """

    history: str
    player: int
    hole_label: str
    infoset_key: str
    actions: list[tuple[int, str, float]]
    reach_prob: float
    off_path: bool


def walk_tree(
    game: HUNLPoker,
    average_strategy: dict[str, list[float]],
    *,
    include_off_path: bool = False,
    reach_threshold: float = 1e-4,
) -> list[TreeNode]:
    """Walk the entire decision tree, yielding visited decision nodes.

    Re-runs the game from ``game.initial_state()``, advancing past chance
    nodes (we assume hole cards are pre-pinned for the river-spot path, so
    there's only one chance outcome at the root), then recursively expands
    every player decision. Reach probability is accumulated multiplicatively
    using only the acting player's own strategy at each step (we do NOT mix
    in opponent probabilities — that's a separate "joint reach" the caller
    can derive from ``probs`` if needed).

    Returns nodes in pre-order (root first, then deeper subtrees).
    """
    state = game.initial_state()
    # Advance past chance nodes. For pinned-hole river spots this is at most
    # one step (the initial chance node deals the pre-set hole cards).
    while game.current_player(state) == -1 and not game.is_terminal(state):
        outcomes = game.chance_outcomes(state)
        if not outcomes:
            break
        # We always take outcome[0] because for pinned-hole pre-dealt cards
        # there's a single outcome; for unpinned spots this walk would need
        # extension. The river CLI path always pins.
        state = game.apply(state, outcomes[0][0])

    nodes: list[TreeNode] = []
    _walk_recursive(
        game,
        state,
        average_strategy,
        reach=1.0,
        nodes_out=nodes,
        include_off_path=include_off_path,
        reach_threshold=reach_threshold,
    )
    return nodes


def _walk_recursive(
    game: HUNLPoker,
    state: HUNLState,
    average_strategy: dict[str, list[float]],
    *,
    reach: float,
    nodes_out: list[TreeNode],
    include_off_path: bool,
    reach_threshold: float,
) -> None:
    if game.is_terminal(state):
        return
    cur = game.current_player(state)
    if cur == -1:
        # Run-out chance: take first outcome (deterministic for pinned spots).
        outcomes = game.chance_outcomes(state)
        if not outcomes:
            return
        next_state = game.apply(state, outcomes[0][0])
        _walk_recursive(
            game,
            next_state,
            average_strategy,
            reach=reach,
            nodes_out=nodes_out,
            include_off_path=include_off_path,
            reach_threshold=reach_threshold,
        )
        return

    infoset_key = game.infoset_key(state, cur)
    probs = average_strategy.get(infoset_key)
    legal = game.legal_actions(state)
    # Compute the action context once so we can decode every label uniformly.
    # We use the private ``_action_context`` on HUNLPoker; that method only
    # reads state + config, no mutation.
    action_ctx = game._action_context(state)  # type: ignore[attr-defined]

    actions: list[tuple[int, str, float]] = []
    if probs is None:
        # No strategy recorded — phantom node (engine sometimes prunes leaves
        # or off-equilibrium branches). Emit zeros so the formatter can flag
        # it; we still walk children with reach=0 if include_off_path is on.
        probs = [0.0] * len(legal)
    if len(probs) != len(legal):
        # The engine guarantees this invariant, but guard for robustness when
        # consumers pass externally-loaded strategies that don't match the
        # current config (e.g. different bet-sizes). Use min() to avoid
        # IndexError and pad missing slots with 0.0.
        probs = list(probs) + [0.0] * max(0, len(legal) - len(probs))
        probs = probs[: len(legal)]

    for aid, p in zip(legal, probs):
        actions.append((aid, decode_action_label(aid, action_ctx), p))

    # History string within the current street (matches infoset_key format).
    history = "".join(state.current_street_tokens)
    hole_label = _hole_label(state, cur)
    off_path = reach <= reach_threshold

    if include_off_path or not off_path:
        nodes_out.append(
            TreeNode(
                history=history,
                player=cur,
                hole_label=hole_label,
                infoset_key=infoset_key,
                actions=list(actions),
                reach_prob=reach,
                off_path=off_path,
            )
        )

    for aid, _, p in actions:
        child_reach = reach * p
        if not include_off_path and child_reach <= reach_threshold:
            continue
        next_state = game.apply(state, aid)
        _walk_recursive(
            game,
            next_state,
            average_strategy,
            reach=child_reach,
            nodes_out=nodes_out,
            include_off_path=include_off_path,
            reach_threshold=reach_threshold,
        )


def _hole_label(state: HUNLState, player: int) -> str:
    """Render the acting player's hole cards as a short string (e.g. ``"AhKd"``)."""
    hole = state.hole_cards
    if not hole or len(hole) < 2:
        return "?"
    cards = hole[player]
    return "".join(str(c) for c in cards)


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def _bar(prob: float, width: int = 24) -> str:
    """ASCII bar for a probability in [0, 1]."""
    if prob != prob or prob < 0:  # NaN guard
        prob = 0.0
    if prob > 1.0:
        prob = 1.0
    fill = int(round(prob * width))
    return "#" * fill + "." * (width - fill)


def format_text(
    nodes: list[TreeNode],
    *,
    title: str | None = None,
    include_off_path: bool = False,
) -> str:
    """Pretty-print the walk as ASCII tree text with bar charts."""
    buf = _io.StringIO()
    if title:
        buf.write(title)
        buf.write("\n")
        buf.write("=" * len(title))
        buf.write("\n\n")
    if not nodes:
        buf.write("(no decision nodes)\n")
        return buf.getvalue()
    for node in nodes:
        marker = " [OFF-PATH]" if node.off_path else ""
        depth_indent = "  " * len(_split_history_tokens(node.history))
        buf.write(
            f"{depth_indent}P{node.player} ({node.hole_label})"
            f" — {humanize_history(node.history)}"
            f"  [reach={node.reach_prob:.4f}]{marker}\n"
        )
        for _, label, prob in node.actions:
            buf.write(
                f"{depth_indent}    {label:<28}  "
                f"{_bar(prob)}  {prob:.4f}\n"
            )
        buf.write("\n")
    return buf.getvalue()


def format_json(
    nodes: list[TreeNode],
    *,
    extra: dict | None = None,
) -> str:
    """Serialize the walk as JSON.

    Schema (one record per node):

    .. code-block:: json

        {
            "nodes": [
                {
                    "history": "xb750",
                    "player": 1,
                    "hole_label": "QhQc",
                    "infoset_key": "QhQc|...|r|xb750",
                    "reach_prob": 0.4543,
                    "off_path": false,
                    "actions": [
                        {"action_id": 0, "label": "fold", "prob": 0.99},
                        ...
                    ]
                }
            ]
        }
    """
    out: dict = {"nodes": []}
    for node in nodes:
        out["nodes"].append(
            {
                "history": node.history,
                "player": node.player,
                "hole_label": node.hole_label,
                "infoset_key": node.infoset_key,
                "reach_prob": node.reach_prob,
                "off_path": node.off_path,
                "actions": [
                    {"action_id": aid, "label": label, "prob": prob}
                    for aid, label, prob in node.actions
                ],
            }
        )
    if extra:
        out.update(extra)
    return _json.dumps(out, indent=2, sort_keys=True)


def format_csv(nodes: list[TreeNode], *, hand_class: str = "") -> str:
    """Serialize the walk as CSV.

    Header: ``node_history,hand_class,action_label,probability,reach_prob``.
    One row per (node, action) pair.
    """
    buf = _io.StringIO()
    writer = _csv.writer(buf)
    writer.writerow(
        ["node_history", "hand_class", "action_label", "probability", "reach_prob"]
    )
    for node in nodes:
        hc = hand_class or node.hole_label
        for _, label, prob in node.actions:
            writer.writerow(
                [
                    node.history or "(root)",
                    hc,
                    label,
                    f"{prob:.6f}",
                    f"{node.reach_prob:.6f}",
                ]
            )
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Drill-down helpers
# ---------------------------------------------------------------------------


def find_nodes_by_history(
    nodes: list[TreeNode], history: str
) -> list[TreeNode]:
    """Return all walk nodes whose history matches ``history`` exactly."""
    return [n for n in nodes if n.history == history]


# Pre-canonicalize hand class labels so we collapse e.g. "QhQc" and "QcQd"
# into "QQ". We keep colors when offsuit (Ah Kc → AKo).
def _canonical_hand_class(hole_label: str) -> str:
    """Map a 4-char hole label like ``"QhQc"`` into a class like ``"QQ"``.

    Rules:
    * Same rank → ``"<rank><rank>"`` (pair).
    * Different ranks, same suit → ``"<hi><lo>s"`` (suited).
    * Different ranks, different suits → ``"<hi><lo>o"`` (offsuit).
    """
    if len(hole_label) != 4:
        return hole_label
    r1, s1, r2, s2 = hole_label[0], hole_label[1], hole_label[2], hole_label[3]
    if r1 == r2:
        return r1 + r2
    # Order by rank (higher first). Use ranks_index keyed map.
    _RANK_ORDER = "23456789TJQKA"
    hi, lo = (r1, r2) if _RANK_ORDER.index(r1) >= _RANK_ORDER.index(r2) else (r2, r1)
    suited = "s" if s1 == s2 else "o"
    return f"{hi}{lo}{suited}"


def aggregate_class_strategies(
    per_combo_nodes: dict[str, list[TreeNode]],
    history: str,
) -> dict[str, list[tuple[int, str, float, float]]]:
    """Aggregate per-combo strategies at ``history`` into per-hand-class dicts.

    ``per_combo_nodes`` maps a combo label (e.g. ``"QhQc"``) → walked nodes.
    For each combo, we find the node at ``history`` and group by canonical
    hand class. Returns ``{class -> [(action_id, label, mean_prob,
    entropy)]}``. ``entropy`` is per-combo Shannon entropy (in bits)
    averaged within the class — used for mixing-strategy ranking.
    """
    # combo -> node at the requested history (or None)
    matches: dict[str, TreeNode] = {}
    for combo, nodes in per_combo_nodes.items():
        match = next((n for n in nodes if n.history == history), None)
        if match is not None:
            matches[combo] = match
    if not matches:
        return {}
    # Group combos by class.
    by_class: dict[str, list[TreeNode]] = {}
    for combo, node in matches.items():
        cls = _canonical_hand_class(combo)
        by_class.setdefault(cls, []).append(node)
    out: dict[str, list[tuple[int, str, float, float]]] = {}
    for cls, group in by_class.items():
        # Take the action list from the first node (all should have the same
        # legal action set for the same history at the same state).
        if not group:
            continue
        head = group[0]
        # Mean prob across combos.
        n = len(group)
        per_action_probs: list[float] = [0.0] * len(head.actions)
        per_action_entropy: list[float] = [0.0] * len(head.actions)
        for node in group:
            for i, (_, _, prob) in enumerate(node.actions):
                per_action_probs[i] += prob
            # Per-combo entropy.
            ent = 0.0
            for _, _, prob in node.actions:
                if prob > 0:
                    ent -= prob * math.log2(prob)
            for i in range(len(per_action_entropy)):
                per_action_entropy[i] += ent / max(1, len(head.actions))
        out[cls] = [
            (
                head.actions[i][0],
                head.actions[i][1],
                per_action_probs[i] / n,
                per_action_entropy[i] / n,
            )
            for i in range(len(head.actions))
        ]
    return out


def rank_classes_by_entropy(
    classes: dict[str, list[tuple[int, str, float, float]]],
) -> list[tuple[str, float]]:
    """Sort classes by Shannon entropy of their action distribution (highest first).

    Returns ``[(class, entropy), ...]``. Higher-entropy classes are the
    "mixing" hands; lower-entropy classes are pure-strategy hands. The
    top-N filter for ``--node`` keys off this ranking.
    """
    ranked: list[tuple[str, float]] = []
    for cls, actions in classes.items():
        probs = [p for _, _, p, _ in actions]
        s = sum(probs)
        normed = [p / s for p in probs] if s > 0 else probs
        ent = 0.0
        for p in normed:
            if p > 0:
                ent -= p * math.log2(p)
        ranked.append((cls, ent))
    ranked.sort(key=lambda x: -x[1])
    return ranked


def format_per_class_text(
    classes: dict[str, list[tuple[int, str, float, float]]],
    history: str,
    *,
    top_n: int | None = None,
    mdf_threshold: float | None = None,
) -> str:
    """Pretty-print per-hand-class strategy at a fixed node.

    If ``mdf_threshold`` is set and the action list contains a fold/call
    pair (no other actions), annotates the per-class line with the MDF gap
    (Daniel persona's "MDF reference").
    """
    buf = _io.StringIO()
    buf.write(f"Per-class strategy at history {history!r}:\n")
    buf.write("-" * 60 + "\n")
    if not classes:
        buf.write("(no matching classes)\n")
        return buf.getvalue()
    ranked = rank_classes_by_entropy(classes)
    if top_n is not None and top_n > 0:
        ranked = ranked[:top_n]
    for cls, entropy in ranked:
        actions = classes[cls]
        action_strs: list[str] = []
        for _, label, prob, _ in actions:
            action_strs.append(f"{label}={prob:.3f}")
        line = f"  {cls:<6}  H={entropy:.3f}  " + "  ".join(action_strs)
        if mdf_threshold is not None:
            # MDF annotation only when both fold AND call are in the menu
            # (i.e. facing a live bet). When raises are also available, the
            # strict pot-odds MDF underestimates total defense — we still
            # report it as a reference, but the per-class line shows the
            # full action distribution so the user can see the raise mass.
            labels_lc = [a[1].lower() for a in actions]
            has_fold = any(lbl.startswith("fold") for lbl in labels_lc)
            has_call = any(lbl.startswith("call") for lbl in labels_lc)
            if has_fold and has_call:
                fold_prob = next(
                    (a[2] for a in actions if a[1].lower().startswith("fold")), 0.0
                )
                gap = fold_prob - (1.0 - mdf_threshold)
                tag = "over-folding" if gap > 0.05 else (
                    "under-folding" if gap < -0.05 else "near MDF"
                )
                line += (
                    f"  | MDF={mdf_threshold:.2%}, "
                    f"observed fold={fold_prob:.2%} ({tag})"
                )
        buf.write(line + "\n")
    return buf.getvalue()


def compute_mdf_threshold(action_ctx: ActionContext) -> float | None:
    """Pot-odds MDF threshold: bet/(pot+bet).

    Returns ``None`` when there is no live bet to defend against
    (``to_call == 0``). MDF = 1 - (bet / (pot + bet)) is the minimum
    defense frequency to keep the bluffer indifferent.
    """
    if action_ctx.to_call <= 0:
        return None
    pot = action_ctx.pot
    bet = action_ctx.to_call
    if pot + bet <= 0:
        return None
    return 1.0 - (bet / (pot + bet))


def hand_classes_from_per_combo(
    per_combo_results: dict[str, dict[str, list[float]]],
) -> dict[str, list[str]]:
    """Group combo labels by canonical hand class.

    ``per_combo_results`` keys are 4-char combo strings (e.g. ``"QhQc"``);
    we collapse them into class labels (``"QQ"``).
    """
    out: dict[str, list[str]] = {}
    for combo in per_combo_results:
        cls = _canonical_hand_class(combo)
        out.setdefault(cls, []).append(combo)
    return out


# Re-export
__all__ = [
    "TreeNode",
    "aggregate_class_strategies",
    "compute_mdf_threshold",
    "decode_action_label",
    "find_nodes_by_history",
    "format_csv",
    "format_json",
    "format_per_class_text",
    "format_text",
    "hand_classes_from_per_combo",
    "humanize_history",
    "parse_token",
    "rank_classes_by_entropy",
    "walk_tree",
]
