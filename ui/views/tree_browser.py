"""Decision tree browser for the post-solve strategy.

Per ``pr10a_spec.md`` §4.5 (mockup), §0.1 Q6 (locked reach-filter
default = 0.01), and ``pr10_spec.md`` §3.4 (performance guards) +
§8.5 (DOM cap).

Locked design contract:
  * Q6: reach-probability slider visible above the tree, default value
    0.01 (NOT 0.0). The tooltip explains the threshold.
  * §3.4: per-node child cap = 100; nodes with >500 raw children render
    only the top 100 by reach plus a "...N more nodes hidden" placeholder.
  * §8.5: global DOM cap of 2000 visible nodes; deepest branches trim
    first; truncation count reported in the header badge.
  * Lazy expansion: ``SolveTree.__init__`` materializes only the root;
    children compute on demand the first time a node is expanded.

The tree adapter (``SolveTree``) walks the post-solve strategy + game
graph and yields NiceGUI-tree-compatible nodes. NiceGUI's ``ui.tree``
widget renders the result; per-node labels carry inline R/Y/G action
badges so the tree doubles as a readout (anti-pattern §3.8 mitigation).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

import numpy as np

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
    _bet_menu,
    _raise_menu,
)
from poker_solver.hunl import HUNLPoker, HUNLState
from poker_solver.solver import SolveResult

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ui.state import AppState

# -- Constants ---------------------------------------------------------------

# Per ``pr10_spec.md`` §3.4 + §8.5: child cap + DOM ceiling.
_PER_NODE_CHILD_LIMIT: int = 100
_PER_NODE_RAW_THRESHOLD: int = 500
_GLOBAL_NODE_CEILING: int = 2000

# Q6 locked default (``pr10a_spec.md`` §0.1).
_DEFAULT_MIN_REACH: float = 0.01


# Context-FREE fallback label table — positional enum-slot names. These are
# only correct when the bet menu is the legacy flat (0.33, 0.75, …) one and
# raises were pot-fractions; under the C bet-size feature the concrete size a
# slot maps to is context-dependent, so user-facing labels go through
# :func:`_context_action_label` (which reads the per-node ActionContext). This
# table survives as (a) the slug source for stable node-id generation
# (``_action_token``) and (b) the fallback when no context is available.
_ACTION_LABELS: dict[int, str] = {
    ACTION_FOLD: "fold",
    ACTION_CHECK: "check",
    ACTION_CALL: "call",
    ACTION_BET_33: "bet33%",
    ACTION_BET_75: "bet75%",
    ACTION_BET_100: "bet100%",
    ACTION_BET_150: "bet150%",
    ACTION_BET_200: "bet200%",
    ACTION_RAISE_33: "raise33%",
    ACTION_RAISE_75: "raise75%",
    ACTION_RAISE_100: "raise100%",
    ACTION_RAISE_150: "raise150%",
    ACTION_RAISE_200: "raise200%",
    ACTION_ALL_IN: "all-in",
}

# Enum slot -> per-street bet-menu index / raise-menu index (positional).
_BET_SLOT_BY_ACTION: dict[int, int] = {
    ACTION_BET_33: 0,
    ACTION_BET_75: 1,
    ACTION_BET_100: 2,
    ACTION_BET_150: 3,
    ACTION_BET_200: 4,
}
_RAISE_SLOT_BY_ACTION: dict[int, int] = {
    ACTION_RAISE_33: 0,
    ACTION_RAISE_75: 1,
    ACTION_RAISE_100: 2,
    ACTION_RAISE_150: 3,
    ACTION_RAISE_200: 4,
}


def _format_raise_x(mult: float) -> str:
    """Format a raise multiplier as a terse ``<x>x`` tag (e.g. ``3.0x``)."""
    f = float(mult)
    if f == int(f):
        return f"{f:.1f}x"
    return f"{f:g}x"


def _context_action_label(action: int, ctx: ActionContext | None) -> str:
    """Terse, context-aware label for a single action id.

    Mirrors the display style of the flat ``_ACTION_LABELS`` table (``bet75%``,
    ``all-in`` …) but derives bet/raise sizes from the per-node
    :class:`ActionContext` (the C bet-size feature):

    * Bets index the per-street pot-fraction menu (``_bet_menu(ctx)`` by
      ``ctx.street``): e.g. a flop slot of 1.25 renders ``bet125%``.
    * Raises index the multiplier menu (``_raise_menu(ctx)`` = ``raise_size_xs``)
      and render as an ``x`` multiplier (``raise3.0x``), NOT a pot-fraction.

    Falls back to the context-free ``_ACTION_LABELS`` slot name when ``ctx`` is
    None or the slot indexes past the active menu.
    """
    if ctx is None:
        return _ACTION_LABELS.get(action, str(action))
    if action in _BET_SLOT_BY_ACTION:
        idx = _BET_SLOT_BY_ACTION[action]
        menu = _bet_menu(ctx)
        if idx < len(menu):
            return f"bet{int(round(menu[idx] * 100))}%"
        return _ACTION_LABELS.get(action, str(action))
    if action in _RAISE_SLOT_BY_ACTION:
        idx = _RAISE_SLOT_BY_ACTION[action]
        menu = _raise_menu(ctx)
        if idx < len(menu):
            return f"raise{_format_raise_x(menu[idx])}"
        return _ACTION_LABELS.get(action, str(action))
    return _ACTION_LABELS.get(action, str(action))


def _ctx_for_state(game: HUNLPoker, state: HUNLState) -> ActionContext | None:
    """Best-effort per-node ActionContext for label derivation.

    Returns None (so callers fall back to the context-free table) for chance /
    terminal nodes or any unexpected engine state, so the tree UI never raises
    while rendering a label.
    """
    try:
        if state.cur_player == -1 or game.is_terminal(state):
            return None
        return game._action_context(state)
    except Exception:
        return None


def _labels_for_node_state(
    game: HUNLPoker, state: HUNLState, legal: tuple[object, ...]
) -> tuple[str, ...]:
    """Context-aware display labels for the legal actions at ``state``.

    Aligned 1:1 with ``legal``. Empty input (chance / terminal node) yields an
    empty tuple. Uses the per-decision :class:`ActionContext` so bets carry the
    per-street pot-fraction and raises carry the ``x`` multiplier.
    """
    if not legal:
        return ()
    ctx = _ctx_for_state(game, state)
    return tuple(_context_action_label(cast(int, a), ctx) for a in legal)


# -- Tree node ---------------------------------------------------------------


@dataclass
class TreeNode:
    """One node in the decision tree.

    Lazy-expanded; children loaded on demand via ``SolveTree.expand``.
    Per ``pr10_spec.md`` §8.1.
    """

    id: str
    label: str
    history: tuple[object, ...]
    state_snapshot: HUNLState
    player_to_act: int
    reach_prob: float
    range_weighted_ev: float
    legal_actions: tuple[object, ...]
    action_freqs: tuple[float, ...]
    action_evs: tuple[float, ...]
    truncated: bool = False
    is_chance: bool = False
    is_terminal: bool = False
    # Context-aware display labels aligned to ``legal_actions`` (per-street bet
    # tags + x-multiplier raise tags; C bet-size feature). Empty => the badge
    # renderer falls back to the context-free ``_ACTION_LABELS`` table.
    action_labels: tuple[str, ...] = ()


# -- SolveTree adapter --------------------------------------------------------


@dataclass
class _ExpansionStats:
    """Per-tree tally used to enforce the global DOM ceiling."""

    visible_count: int = 0
    truncated_count: int = 0
    max_depth_shown: int = 0


class SolveTree:
    """Decision-tree adapter for a finished solve.

    Walks the game graph + strategy in DFS pre-order, materializing
    nodes on demand. ``__init__`` builds only the root. Per spec §3.4,
    each node's expansion is capped at 100 children (top-N by reach
    when raw children exceed 500); per §8.5, the visible-node tally is
    capped at 2000 with a truncation badge reporting the count.
    """

    def __init__(
        self,
        game: HUNLPoker,
        result: SolveResult,
        min_reach: float = _DEFAULT_MIN_REACH,
    ) -> None:
        self.game: HUNLPoker = game
        self.result: SolveResult = result
        self.min_reach: float = float(min_reach)
        self._strategy: dict[str, np.ndarray] = self._build_strategy_cache(result)
        self._cache: dict[str, list[TreeNode]] = {}
        self.stats: _ExpansionStats = _ExpansionStats()
        self.root: TreeNode = self._build_root()

    @staticmethod
    def _build_strategy_cache(result: SolveResult) -> dict[str, np.ndarray]:
        out: dict[str, np.ndarray] = {}
        for key, vec in result.average_strategy.items():
            out[str(key)] = np.asarray(vec, dtype=float)
        return out

    def _build_root(self) -> TreeNode:
        state = self.game.initial_state()
        legal = tuple(self.game.legal_actions(state)) if state.cur_player != -1 else ()
        return TreeNode(
            id="root",
            label="[root]",
            history=(),
            state_snapshot=state,
            player_to_act=state.cur_player,
            reach_prob=1.0,
            range_weighted_ev=0.0,
            legal_actions=legal,
            action_freqs=self._lookup_action_freqs(state, legal),
            action_evs=tuple(0.0 for _ in legal),
            action_labels=_labels_for_node_state(self.game, state, legal),
            is_chance=(state.cur_player == -1 and not self.game.is_terminal(state)),
            is_terminal=self.game.is_terminal(state),
        )

    def _lookup_action_freqs(
        self, state: HUNLState, legal: tuple[int, ...]
    ) -> tuple[float, ...]:
        """Best-effort lookup of the range-weighted action frequencies.

        For a HUNL infoset post-solve, we average the policy across both
        players' possible holdings — but doing that exactly requires the
        full range mass at the node. As a practical approximation we
        sample the strategy at the canonical infoset key derived from
        the state-as-is; if no entry exists we return uniform.
        """

        if not legal or state.cur_player == -1:
            return tuple(0.0 for _ in legal)
        try:
            key = self.game.infoset_key(state, state.cur_player)
        except (IndexError, KeyError, AttributeError):
            return tuple(1.0 / len(legal) for _ in legal)
        entry = self._strategy.get(key)
        if entry is None or entry.shape[0] != len(legal):
            return tuple(1.0 / len(legal) for _ in legal)
        return tuple(float(x) for x in entry)

    def expand(self, node_id: str) -> list[TreeNode]:
        """Return ``node_id``'s children, computing on demand.

        Per spec §3.4: when raw expansion > 500 children, return top 100
        by ``reach_prob`` plus an unexpandable ``__truncated__``
        placeholder so the UI can show "...N more nodes hidden". Per
        spec §8.5: total visible nodes bounded by the global ceiling
        (2000); deepest expansions return [] once the budget is spent.
        """

        cached = self._cache.get(node_id)
        if cached is not None:
            return cached

        if self.stats.visible_count >= _GLOBAL_NODE_CEILING:
            self._cache[node_id] = []
            return []

        parent = self.get_node(node_id)
        if parent.is_terminal or parent.id.endswith("/__truncated__"):
            self._cache[node_id] = []
            return []

        raw_children = list(self._raw_children(parent))
        # Filter by reach threshold so a single slider drag re-shapes the
        # entire tree at every level (filter clears cache; see
        # ``set_min_reach``).
        eligible = [c for c in raw_children if c.reach_prob >= self.min_reach]
        eligible.sort(key=lambda n: n.reach_prob, reverse=True)
        truncated = False
        truncated_n = 0
        if len(eligible) > _PER_NODE_RAW_THRESHOLD:
            truncated_n = len(eligible) - _PER_NODE_CHILD_LIMIT
            eligible = eligible[:_PER_NODE_CHILD_LIMIT]
            truncated = True
        # Honour the global DOM ceiling — trim deepest first by simply
        # refusing to materialize more children once the budget runs out.
        remaining = _GLOBAL_NODE_CEILING - self.stats.visible_count
        if len(eligible) > remaining:
            trimmed = len(eligible) - remaining
            eligible = eligible[:remaining]
            truncated = True
            truncated_n += trimmed

        if truncated:
            eligible.append(self._truncated_placeholder(parent, truncated_n))
            self.stats.truncated_count += truncated_n

        self.stats.visible_count += len(eligible)
        self._cache[node_id] = eligible
        return eligible

    def _truncated_placeholder(self, parent: TreeNode, hidden: int) -> TreeNode:
        return TreeNode(
            id=f"{parent.id}/__truncated__",
            label=f"... {hidden} more nodes hidden",
            history=parent.history,
            state_snapshot=parent.state_snapshot,
            player_to_act=-1,
            reach_prob=0.0,
            range_weighted_ev=0.0,
            legal_actions=(),
            action_freqs=(),
            action_evs=(),
            truncated=True,
            is_terminal=True,  # not expandable
        )

    def _raw_children(self, parent: TreeNode) -> list[TreeNode]:
        """Materialize the immediate children of ``parent`` (pre-filter)."""

        state = parent.state_snapshot
        if self.game.is_terminal(state):
            return []
        if state.cur_player == -1:
            # Chance node: collapse into a single representative child for
            # the next street so the user can keep drilling without
            # exploding the tree by 44+ board cards per level.
            return self._chance_children(parent)
        return self._player_children(parent)

    def _chance_children(self, parent: TreeNode) -> list[TreeNode]:
        outcomes = self.game.chance_outcomes(parent.state_snapshot)
        if not outcomes:
            return []
        # Use the first outcome as a stand-in (chance has identical
        # downstream structure across deals modulo cards; this keeps the
        # UI tree finite while preserving an entry point).
        action, prob = outcomes[0]
        next_state = self.game.apply(parent.state_snapshot, action)
        legal = (
            tuple(self.game.legal_actions(next_state))
            if next_state.cur_player != -1
            else ()
        )
        child_id = f"{parent.id}/chance"
        return [
            TreeNode(
                id=child_id,
                label=f"[chance ({len(outcomes)} outcomes)]",
                history=parent.history + (action,),
                state_snapshot=next_state,
                player_to_act=next_state.cur_player,
                reach_prob=parent.reach_prob * float(prob),
                range_weighted_ev=parent.range_weighted_ev,
                legal_actions=legal,
                action_freqs=self._lookup_action_freqs(next_state, legal),
                action_evs=tuple(0.0 for _ in legal),
                action_labels=_labels_for_node_state(self.game, next_state, legal),
                is_chance=(
                    next_state.cur_player == -1
                    and not self.game.is_terminal(next_state)
                ),
                is_terminal=self.game.is_terminal(next_state),
            )
        ]

    def _player_children(self, parent: TreeNode) -> list[TreeNode]:
        children: list[TreeNode] = []
        state = parent.state_snapshot
        legal_actions = self.game.legal_actions(state)
        if not legal_actions:
            return []
        # Per-decision context for context-aware (per-street bet / x-multiplier
        # raise) action labels. Derived once from the parent decision state.
        ctx = _ctx_for_state(self.game, state)
        freqs = parent.action_freqs or tuple(
            1.0 / len(legal_actions) for _ in legal_actions
        )
        for idx, action in enumerate(legal_actions):
            next_state = self.game.apply(state, action)
            freq = freqs[idx] if idx < len(freqs) else 1.0 / len(legal_actions)
            reach_after = parent.reach_prob * float(freq)
            legal_next = (
                tuple(self.game.legal_actions(next_state))
                if next_state.cur_player != -1
                else ()
            )
            label = self._format_player_label(state.cur_player, action, ctx)
            child_id = f"{parent.id}/{state.cur_player}_{_action_token(action)}"
            children.append(
                TreeNode(
                    id=child_id,
                    label=label,
                    history=parent.history + (action,),
                    state_snapshot=next_state,
                    player_to_act=next_state.cur_player,
                    reach_prob=reach_after,
                    range_weighted_ev=parent.range_weighted_ev,
                    legal_actions=legal_next,
                    action_freqs=self._lookup_action_freqs(next_state, legal_next),
                    action_evs=tuple(0.0 for _ in legal_next),
                    action_labels=_labels_for_node_state(
                        self.game, next_state, legal_next
                    ),
                    is_chance=(
                        next_state.cur_player == -1
                        and not self.game.is_terminal(next_state)
                    ),
                    is_terminal=self.game.is_terminal(next_state),
                )
            )
        return children

    @staticmethod
    def _format_player_label(
        cur_player: int, action: int, ctx: ActionContext | None
    ) -> str:
        position_label = "SB" if cur_player == 0 else "BB"
        action_word = _context_action_label(action, ctx)
        return f"[{position_label}: {action_word}]"

    def get_node(self, node_id: str) -> TreeNode:
        """Lookup a node by id, walking from root and expanding lazily.

        ``node_id`` is the slash-separated path produced by ``expand``;
        ``"root"`` returns the root unconditionally.
        """

        if node_id == "root":
            return self.root
        if node_id == self.root.id:
            return self.root
        parts = node_id.split("/")
        if parts[0] != "root":
            raise KeyError(node_id)
        current = self.root
        for i in range(1, len(parts)):
            partial_id = "/".join(parts[: i + 1])
            children = self._cache.get(current.id) or self.expand(current.id)
            match: TreeNode | None = None
            for child in children:
                if child.id == partial_id:
                    match = child
                    break
            if match is None:
                raise KeyError(node_id)
            current = match
        return current

    def set_min_reach(self, min_reach: float) -> None:
        """Update the reach-prob filter and clear the expansion cache.

        Filter changes ripple through every level: a deeper subtree may
        gain or lose visibility, so the whole cache must be invalidated.
        """

        self.min_reach = float(min_reach)
        self._cache.clear()
        self.stats = _ExpansionStats()


def _action_token(action: int) -> str:
    """Make a filesystem-friendly action slug for node ids."""

    return _ACTION_LABELS.get(action, f"a{action}").replace("%", "pct")


# -- NiceGUI label rendering --------------------------------------------------

# Color thresholds for inline action badges (Pio palette per spec §7.3).
_FOLD_COLOR: str = "rgb(220,40,40)"
_CALL_COLOR: str = "rgb(220,200,40)"
_RAISE_COLOR: str = "rgb(40,180,60)"


def _action_color(action: int) -> str:
    if action == ACTION_FOLD:
        return _FOLD_COLOR
    if action in (ACTION_CHECK, ACTION_CALL):
        return _CALL_COLOR
    return _RAISE_COLOR


def _format_action_badge(
    action: int, freq: float, ev_mbb: float, label: str | None = None
) -> str:
    # ``label`` is the context-aware tag (per-street bet %, x-multiplier raise)
    # precomputed on the node; fall back to the context-free table when absent.
    if label is None:
        label = _ACTION_LABELS.get(action, str(action))
    color = _action_color(action)
    pct = int(round(freq * 100))
    return (
        f'<span style="color:{color};font-family:Menlo,Consolas,monospace;'
        f'margin-right:8px">{label} {pct}%'
        f"{f' EV {ev_mbb:+.0f}' if ev_mbb != 0.0 else ''}</span>"
    )


def tree_node_to_dict(
    node: TreeNode, *, locked_keys: frozenset[str] = frozenset()
) -> dict[str, object]:
    """Convert a :class:`TreeNode` to NiceGUI's ``ui.tree`` schema.

    The label is rendered as inline HTML so action frequencies pick up
    the R/Y/G color triad. Children are NOT recursively materialized;
    callers wire ``ui.tree(on_expand=...)`` and call back into
    ``SolveTree.expand`` to fetch the next level on demand.

    PR 24b §3.5: when ``node.id`` is in ``locked_keys`` (the keys of
    ``Spot.locked_strategies``), prepend a yellow padlock icon to the
    label so the user can see which nodes carry a lock.
    """

    badges: list[str] = []
    if not node.truncated and node.legal_actions:
        for idx, action in enumerate(node.legal_actions):
            freq = node.action_freqs[idx] if idx < len(node.action_freqs) else 0.0
            ev = node.action_evs[idx] if idx < len(node.action_evs) else 0.0
            label = (
                node.action_labels[idx]
                if idx < len(node.action_labels)
                else None
            )
            # ``legal_actions`` is typed as ``tuple[object, ...]`` per spec
            # to keep the dataclass generic across game types; cast back
            # to int here for the action-id arithmetic.
            badges.append(
                _format_action_badge(
                    cast(int, action), float(freq), float(ev), label
                )
            )
    summary = (
        f"&nbsp;&nbsp;reach {node.reach_prob:.3f}"
        f" · EV {node.range_weighted_ev:+.1f} mBB"
        if not node.truncated
        else ""
    )
    # PR 24b §3.5: yellow padlock icon when this node is locked.
    lock_indicator = ""
    if node.id in locked_keys:
        lock_indicator = (
            '<span style="color:#d4a017;margin-right:6px" '
            'title="Locked strategy applied at this infoset">🔒</span>'
        )
    label_html = (
        f"{lock_indicator}"
        f'<span style="color:#f0f0f0;font-weight:500">{node.label}</span>'
        f'<span style="color:#9a9a9a">{summary}</span>'
        f'<span style="margin-left:10px">{"".join(badges)}</span>'
    )
    out: dict[str, object] = {
        "id": node.id,
        "label": label_html,
    }
    # ``ui.tree`` lazily collapses any node that exposes an empty
    # ``children`` list; we omit the key for nodes that may still
    # expand so the UI shows the expand chevron.
    if node.is_terminal or node.truncated:
        out["children"] = []
    return out


# -- State plumbing ----------------------------------------------------------


def _safe_state_field(state: AppState, attr: str, default: Any) -> Any:
    value = getattr(state, attr, None)
    if value is None:
        return default
    return value


def _resolve_tree(state: AppState) -> SolveTree | None:
    """Best-effort retrieval of the current ``SolveTree`` from state.

    Agent A is expected to construct one when a solve completes and
    park it on ``state.current_tree`` (or on the solve session). We
    accept either location.
    """

    direct = _safe_state_field(state, "current_tree", None)
    if isinstance(direct, SolveTree):
        return direct
    solve = _safe_state_field(state, "current_solve", None)
    if solve is not None:
        embedded = getattr(solve, "tree", None) or getattr(solve, "current_tree", None)
        if isinstance(embedded, SolveTree):
            return embedded
    return None


def on_tree_node_selected(state: AppState, node_id: str) -> None:
    """Handle a tree-node click.

    Updates ``state.current_tree_node_id`` so the range matrix re-renders
    conditioned on the new node, then triggers any registered refresh
    hook (Agent A's ``range_matrix.refresh()`` lambda lives on
    ``state.prefs`` per the documented contract).
    """

    try:
        state.current_tree_node_id = str(node_id)
    except AttributeError:
        prefs = _safe_state_field(state, "prefs", None)
        if prefs is not None:
            prefs.current_tree_node_id = str(node_id)
    refresher = _safe_state_field(state, "matrix_refresh", None)
    if callable(refresher):
        refresher()


def on_tree_node_expanded(state: AppState, node_id: str) -> None:
    """Handle a tree-node expansion event by patching the widget."""

    tree = _resolve_tree(state)
    if tree is None:
        return
    children = tree.expand(str(node_id))
    # The NiceGUI patching is done at the widget level by ``render`` below;
    # the side-effect here is the (cache-populating) call to ``expand``.
    del children


def _open_lock_for_node(
    state: AppState,
    tree: SolveTree,
    ui_mod: Any,
    *,
    refresh: Any | None = None,
) -> None:
    """Resolve the currently-selected tree node and open the lock editor.

    PR 24b §3.5: the lock affordance is "Lock current node" — it pulls
    the node id off ``state.current_tree_node_id`` (set by the tree's
    on-select handler; default "root" before any select). If the
    resolved node has no legal actions (terminal / chance / truncated),
    we surface a notify explaining why the lock can't proceed.
    """
    from ui.views.node_lock_editor import open_node_lock_dialog

    node_id = getattr(state, "current_tree_node_id", None) or "root"
    try:
        node = tree.get_node(str(node_id))
    except KeyError:
        ui_mod.notify(
            f"Tree node '{node_id}' not found. Select a node in the tree first.",
            type="warning",
            position="top",
        )
        return
    if node.is_terminal or node.truncated or not node.legal_actions:
        ui_mod.notify(
            "Selected node has no legal actions (terminal / chance / truncated). "
            "Pick a decision node from the tree first.",
            type="warning",
            position="top",
        )
        return
    # Use the node's context-aware labels (per-street bet % + x-multiplier
    # raise; C bet-size feature), falling back to the context-free table for
    # any action without a precomputed label.
    if node.action_labels and len(node.action_labels) == len(node.legal_actions):
        labels = list(node.action_labels)
    else:
        labels = [
            _ACTION_LABELS.get(cast(int, a), str(a)) for a in node.legal_actions
        ]
    # Pre-populate sliders with the current avg-strategy frequencies
    # (which is what the live tree row already shows).
    initial = list(node.action_freqs) if node.action_freqs else None
    open_node_lock_dialog(
        state,
        infoset_key=str(node_id),
        legal_action_labels=labels,
        initial_distribution=initial,
        on_save=refresh,
    )


# -- NiceGUI rendering --------------------------------------------------------


def _import_nicegui() -> Any:
    from nicegui import ui as nicegui_ui

    return nicegui_ui


@dataclass
class _RenderedTree:
    """Internal: the inputs the NiceGUI widget needs in a single pass."""

    nodes: list[dict[str, object]] = field(default_factory=list)
    visible: int = 0
    truncated: int = 0


def _walk_for_widget(
    tree: SolveTree,
    root_id: str,
    depth_budget: int,
    *,
    locked_keys: frozenset[str] = frozenset(),
) -> _RenderedTree:
    """Walk the tree breadth-first, emitting ``tree_node_to_dict`` for
    the first ``depth_budget`` levels. Beyond the budget, child slots
    are left empty so NiceGUI shows the expand chevron and the on_expand
    handler can patch in deeper levels lazily.

    PR 24b §3.5: ``locked_keys`` is the set of locked infoset keys (from
    ``Spot.locked_strategies``); ``tree_node_to_dict`` renders the
    padlock indicator when the node's id appears in the set."""

    rendered = _RenderedTree()
    root = tree.get_node(root_id)
    root_dict = tree_node_to_dict(root, locked_keys=locked_keys)
    rendered.nodes.append(root_dict)
    rendered.visible += 1

    if depth_budget <= 0 or root.is_terminal:
        return rendered

    stack: list[tuple[dict[str, object], TreeNode, int]] = [(root_dict, root, 0)]
    while stack:
        parent_dict, parent_node, level = stack.pop()
        if level >= depth_budget:
            continue
        children = tree.expand(parent_node.id)
        child_dicts: list[dict[str, object]] = []
        for child in children:
            cdict = tree_node_to_dict(child, locked_keys=locked_keys)
            child_dicts.append(cdict)
            rendered.visible += 1
            if child.truncated:
                rendered.truncated += 1
                continue
            if not child.is_terminal and level + 1 < depth_budget:
                stack.append((cdict, child, level + 1))
        parent_dict["children"] = child_dicts
    rendered.truncated += tree.stats.truncated_count
    return rendered


def render(state: AppState) -> None:
    """Render the decision tree browser into the current NiceGUI slot.

    Layout (per ``pr10a_spec.md`` §4.5):
      * reach-filter slider on top (default value 0.01, Q6 locked).
      * ``ui.tree`` widget; lazy on-expand via :func:`on_tree_node_expanded`.
      * truncation badge in the header when the global cap clipped any
        branches.

    NiceGUI ElementFilter markers (Agent C asserts on these):
      ``tree-browser`` (outer card), ``tree-widget`` (the ui.tree element),
      ``tree-reach-slider``, ``tree-truncation-badge`` (only if cap hit).
    """

    ui_mod = _import_nicegui()
    tree = _resolve_tree(state)

    with (
        ui_mod.element("div")
        .mark("tree-browser")
        .style("background:#0f0f0f;padding:10px;border-radius:6px")
    ):
        if tree is None:
            ui_mod.label("Solve to populate the decision tree").style(
                "color:#9a9a9a;font-style:italic"
            )
            return

        # Reach-filter slider (Q6 locked: default 0.01).
        with ui_mod.row().style("align-items:center;gap:10px;margin-bottom:6px"):
            ui_mod.label("Reach >=").style("color:#dcdcdc;font-weight:600")
            slider = ui_mod.slider(
                min=0.0,
                max=1.0,
                step=0.01,
                value=float(getattr(tree, "min_reach", _DEFAULT_MIN_REACH)),
            )
            slider.mark("tree-reach-slider")
            slider.tooltip(
                "Hides nodes with combined reach probability below this "
                "threshold. HUNL trees have 10^4-10^6 nodes; 0.01 hides "
                "leaves with <1% reach (study-irrelevant)."
            )
            reach_label = ui_mod.label(f"{tree.min_reach:.2f}").style(
                "font-family:Menlo,Consolas,monospace;color:#a8c8e8"
            )

        # PR 24b §3.5: "Lock current node" button. The button affordance
        # is the primary lock-trigger (NiceGUI 3.x supports a generic
        # ``contextmenu`` DOM event subscription via ``element.on(...)``,
        # but right-click on a tree row collides with the browser's
        # native context menu in some browsers; a dedicated button
        # avoids the conflict). We additionally subscribe the tree
        # widget to ``contextmenu`` as a bonus path (see _tree_slot
        # below). Per the spec §8 Q4 + PR 24b prompt — documented
        # explicitly in the implementer notes.
        with ui_mod.row().style("align-items:center;gap:10px;margin-bottom:6px"):
            lock_btn = (
                ui_mod.button(
                    "Lock current node",
                    icon="lock",
                )
                .props("flat dense")
                .mark("tree-lock-current-button")
            )
            lock_btn.tooltip(
                "Open the node-lock editor for the currently selected "
                "tree node (or root if none selected). Sets a fixed "
                "strategy at the infoset that the solver will hold "
                "while training (poker_solver.solver.solve(locked_strategies=...))."
            )

            def _open_lock_for_current() -> None:
                _open_lock_for_node(state, tree, ui_mod, refresh=_tree_slot.refresh)

            lock_btn.on_click(_open_lock_for_current)

            ui_mod.label(f"{len(state.current_spot.locked_strategies)} lock(s)").style(
                "color:#9a9a9a;font-size:11px"
            ).mark("tree-lock-count-label")

        @ui_mod.refreshable  # type: ignore[untyped-decorator]
        def _tree_slot() -> None:
            tree.set_min_reach(float(slider.value or 0.0))
            locked_keys = frozenset(state.current_spot.locked_strategies.keys())
            rendered = _walk_for_widget(
                tree, "root", depth_budget=2, locked_keys=locked_keys
            )
            reach_label.text = f"{tree.min_reach:.2f}"
            with ui_mod.row().style("gap:8px;margin-bottom:4px"):
                ui_mod.label(f"Visible: {rendered.visible} nodes").style(
                    "color:#9a9a9a;font-size:11px"
                )
                if rendered.truncated > 0:
                    badge = ui_mod.label(f"{rendered.truncated} hidden by cap")
                    badge.mark("tree-truncation-badge")
                    badge.style("color:#d09a4a;font-size:11px")
            widget = ui_mod.tree(rendered.nodes, label_key="label", node_key="id")
            # NiceGUI markers via `.mark()`; the `no-selection-unset` token
            # is a Quasar prop and must stay on `.props()`.
            widget.mark("tree-widget").props("no-selection-unset")

            def _select_handler(event: Any) -> None:
                node_id = getattr(event, "value", None) or getattr(
                    getattr(event, "args", None), "value", None
                )
                if node_id is None:
                    return
                on_tree_node_selected(state, str(node_id))

            def _expand_handler(event: Any) -> None:
                expanded = getattr(event, "value", None) or []
                for nid in expanded:
                    on_tree_node_expanded(state, str(nid))

            widget.on_select(_select_handler)
            widget.on_expand(_expand_handler)
            # PR 24b §3.5: bonus path — subscribe to the contextmenu DOM
            # event on the tree widget. NiceGUI 3.x exposes ``Element.on``
            # for any DOM event name; the handler opens the lock dialog
            # for the currently-selected node. Right-click + button both
            # work; the button is the primary affordance documented in
            # the tooltip.
            try:
                widget.on(
                    "contextmenu",
                    lambda _e: _open_lock_for_node(
                        state, tree, ui_mod, refresh=_tree_slot.refresh
                    ),
                )
            except Exception:  # noqa: BLE001
                logger.debug(
                    "contextmenu event subscription failed; button "
                    "fallback remains available."
                )

        slider.on(
            "update:model-value",
            lambda _event=None: _tree_slot.refresh(),
        )
        _tree_slot()


__all__ = [
    "TreeNode",
    "SolveTree",
    "tree_node_to_dict",
    "on_tree_node_selected",
    "on_tree_node_expanded",
    "render",
]
