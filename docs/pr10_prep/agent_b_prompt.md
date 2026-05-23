# PR 10a Agent B — range matrix display + decision tree browser (against mock solver)

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 10a Agent B.** PR 10 was split into PR 10a (UI scaffold against a MOCK solver in `ui/mock_solver.py` — Agent C owns the mock) and PR 10b (mechanical solver swap). Your UI artifact is the EXACT artifact PR 10b ships; only the solver-side code changes between PRs.
**Your scope:** the visual centerpiece of the UI — the 13×13 range matrix display (with red/yellow/green Pio color blend + combo inspector strip BELOW the matrix per Q5 locked + hand-class labels in cell upper-left per Q2 locked) and the decision tree browser (collapsible nodes + per-action EV/frequency badges + reach-probability filter with **slider default value = 0.01 per Q6 locked**).
**Your contract:** produce `ui/views/range_matrix.py` and `ui/views/tree_browser.py`; consume Agent A's `ui.state` dataclasses + singletons (`AppState`, `Spot`, `RangeWithFreqs`, `SolveRunner`, `enumerate_hand_classes`, `enumerate_combos`, etc.); render via NiceGUI 2.x using `ui.grid`, `ui.tree`, `@ui.refreshable`; export `render(state)` for each view plus the `SolveTree` adapter class.
**Your success criteria:** ruff clean, black clean, `mypy --strict` clean on new code; matrix correctly renders 169 cells with Pio color convention; per-cell aggregation has NO off-by-one in combo → frequency mapping (correctness item #2); blocker filtering doesn't crash on edge cases; tree expansion is lazy (root yields ≤30 children); ALL existing tests still pass (your work is purely additive).
**File ownership:** you own and may write ONLY `ui/views/range_matrix.py` and `ui/views/tree_browser.py`. You may NOT modify any other file.

---

## Strict file ownership

**You own (create new):**
- `/Users/ashen/Desktop/poker_solver/ui/views/range_matrix.py` (new file)
- `/Users/ashen/Desktop/poker_solver/ui/views/tree_browser.py` (new file)

**You must NOT touch:**
- `ui/__init__.py` — Agent A owns this.
- `ui/app.py` — Agent A owns this.
- `ui/state.py` — Agent A owns this. (You consume its exports; you do NOT modify.)
- `ui/views/__init__.py` — Agent A owns this.
- `ui/views/spot_input.py` — Agent A owns this.
- `ui/views/run_panel.py` — Agent A owns this.
- `ui/views/library_browser.py` — Agent C owns this.
- `tests/test_ui_smoke.py` — Agent C owns this.
- `poker_solver/cli.py`, `pyproject.toml`, `README.md` — Agent C owns these.
- Any existing `poker_solver/*.py` file — read-only references.
- Any existing test file — read-only references.

If you discover an awkward signature mid-implementation or that Agent A's state contract is incompatible with what you need, **do not silently change either side**. Stop and write a short note to the orchestrator describing the conflict; the orchestrator will reconcile.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10a_spec.md`. Internalize §0.1 (the SEVEN LOCKED Q1-Q7 design decisions; Q2, Q5, Q6 are directly load-bearing for YOUR work), §2 (UX design principles 4 + 5 + 8 are load-bearing: color minimalism Pio convention, numbers-on-hover, live feedback), §3 (layout amendment: two-pane — your matrix is the centerpiece, tree is a sidebar `ui.expansion` panel), §4.4 (range matrix mockup with two on-cell signals: color blend + `R/C/F xx%` tag or `MIX`/`BLK`), §4.5 (tree browser mockup with reach filter), §9 Agent B deliverables (UX deltas you implement), §11 acceptance criteria.
1b. **The original long-form spec (background only):** `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10_spec.md` — §3.3, §3.4, §7, §8, §11 critical correctness items. Where pr10a_spec disagrees, **pr10a_spec wins**.
2. **The PLAN (locked decisions):** `/Users/ashen/Desktop/poker_solver/PLAN.md`. UI tech section; architecture summary.
3. **NiceGUI patterns:** `/Users/ashen/Desktop/poker_solver/nicegui/llms.md` if present locally. For YOU specifically: mental models 1 (component model), 8 (refreshable), 9 (outbox batching), and the sections on `ui.grid`, `ui.tree`, `@ui.refreshable`.
4. **Agent A's state contract (your input):** see §"Agent A's exports you depend on" below. You consume the dataclasses + helpers from `ui/state.py`. Do NOT read Agent A's implementation; the spec defines the contract.
5. **Engine surfaces you consume (read-only):**
   - `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` — `HUNLState`, `HUNLConfig`, `Street` IntEnum, infoset-key format (`_STREET_TOKENS`, `_sorted_card_string`), action constants (`ACTION_FOLD`, `ACTION_CHECK`, `ACTION_CALL`, opening-bet constants, raise constants, `ACTION_ALL_IN`).
   - `/Users/ashen/Desktop/poker_solver/poker_solver/action_abstraction.py` — bet-size constants (`_OPENING_BETS`, `_RAISES`, etc.); see what's actually exported.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/card.py` — `Card` type, deck enumeration.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/solver.py` — `SolveResult` shape (`average_strategy: dict[infoset_key → np.ndarray]`).

## Default decisions LOCKED (do not deviate)

These are the locked defaults from the PR 10 spec; if the spec text differs, **these locked defaults win**:

- **NiceGUI 2.x.** Use only the 2.x API surface (`ui.grid`, `ui.tree`, `@ui.refreshable`, `ui.button`, `ui.label`, `ui.tooltip`, `ui.slider`, `ui.dialog`, `ui.expansion`, etc.).
- **Color blend: red=fold (220, 40, 40) / yellow=call (220, 200, 40) / green=raise (40, 180, 60).** Pio convention. See spec §3.3 / §7.3 for the exact RGB blend formula. Do not invent your own palette in PR 10.
- **Numeric frequencies on hover.** Hovering a cell shows tooltip with combo count + weighted fold/call/raise %. (Mitigates color muddiness at extreme mixings; see spec §12 risk 2.)
- **Q6 LOCKED: Tree reach filter slider default value = 0.01** (NOT 0.0). Per `pr10a_spec.md` §0.1 Q6 and §4.5 ("reach filter on top, default 0.01"). The slider's `value=0.01` on first render. Power users drag to 0.0 in one motion. Tooltip explains: "Hides nodes with combined reach probability below this threshold. HUNL trees have 10^4-10^6 nodes; 0.01 hides leaves with <1% reach (study-irrelevant)." (This supersedes any earlier text saying default = 0.0.)
- **Q2 LOCKED: Hand-class labels visible in matrix cells** ("AKs", "QQ", "72o" in upper-left). Numbers on hover only; labels always shown. Cell layout: top-left = hand-class label, body = color blend, optional bottom = 2-letter+pct tag ("R 78%" or "MIX" or "BLK").
- **Q5 LOCKED: Combo inspector position = BELOW the matrix** (full-width horizontal strip). Renders as a separate slot below the matrix grid. Do NOT place to the right (right sidebar is reserved for spot input / run panel / tree browser per Q1).
- **Hand-class grid layout:** top-left = AA, bottom-right = 22 with **suited above-diagonal** (col > row) and **offsuit below-diagonal**. Pairs on the diagonal. This is consistent with PioSolver / GTO Wizard / Agent A's `enumerate_hand_classes()`.
- **Out-of-range cells: faded grey '—' with no color blend.**
- **Blocker-removed combos: slashed pattern overlay + tooltip explaining.**
- **Per-node child cap: 100** (per spec §3.4 performance guard). When a tree node's lazy expansion yields >500 children, render only the top 100 by reach probability and append a "...N more nodes hidden" placeholder.
- **Browser DOM ceiling: hard-cap visible tree nodes at 2000** (per spec §8.5). Trim deepest branches first; report truncation count in the tree header.
- **No new third-party deps.** Imports: `nicegui`, `numpy`, `poker_solver.*`, `ui.state`, stdlib only.

## Agent A's exports you depend on

You consume these from `ui/state.py`. If Agent A's signatures drift, flag it — do not silently adapt.

```python
# From ui/state.py:
@dataclass
class RangeWithFreqs:
    base_range: Range
    frequencies: dict[tuple[Card, Card], float]
    def frequency_of(self, combo: tuple[Card, Card]) -> float: ...

@dataclass
class Spot:
    board: list[Card]
    ranges: tuple[RangeWithFreqs, RangeWithFreqs]
    stacks_bb: tuple[int, int]
    # ... etc per Agent A's contract
    @property
    def starting_street(self) -> Street: ...

class SolveRunner:
    result: SolveResult | None
    iteration: int
    status: str  # 'idle' | 'running' | 'paused' | 'done' | 'stopped' | 'error'
    # ... etc

@dataclass
class AppState:
    current_spot: Spot
    current_solve: SolveSession | None
    current_tree_node_id: str
    selected_player_for_input: int
    runner: SolveRunner
    prefs: UIPrefs
    # ... etc

def get_state() -> AppState: ...

# Hand-class enumeration helpers (the linchpin of your matrix):
def enumerate_hand_classes() -> list[tuple[int, int, str]]: ...
def enumerate_combos(hand_class: str) -> list[tuple[Card, Card]]: ...
def hand_class_label(rank1: int, rank2: int, suited: bool) -> str: ...
def classify_combo(card1: Card, card2: Card) -> str: ...
```

## Public API you produce (signatures Agent A's `app.py` + Agent C's smoke tests depend on)

Type hints required (mypy --strict).

### `ui/views/range_matrix.py`

```python
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from poker_solver.card import Card
from poker_solver.hunl import Street
from ui.state import AppState, RangeWithFreqs, Spot


@dataclass
class CellSummary:
    """Aggregated per-cell strategy summary (used for color + tooltip)."""
    fold: float = 0.0
    call: float = 0.0
    raise_: float = 0.0
    combo_count: int = 0
    blocked: bool = False               # all combos removed by board cards
    empty: bool = False                 # cell not in range
    out_of_range: bool = False          # alias for empty; distinguished for UI


def cell_strategy_summary(
    hand_class: str,
    range_: RangeWithFreqs,
    board: Sequence[Card],
    strategy: dict[str, np.ndarray],
    tree_node_id: str,
    game_state_snapshot: object,        # opaque per spec; the game-state at the
                                        # current tree node (history, player_to_act,
                                        # legal_actions, etc.). Use a duck-typed
                                        # interface: .legal_actions, .history,
                                        # .player_to_act. Document the duck type.
) -> CellSummary:
    """Compute the aggregate fold/call/raise frequencies for a hand class at the
    current tree node, weighted by RangeWithFreqs.frequency_of(combo) and
    averaged over surviving combos (post-blocker).

    Per spec §7.2 pseudocode. The infoset key for each surviving combo is built
    via HUNLPoker.infoset_key (or its equivalent for the current state); the
    strategy dict maps infoset_key -> probs array.

    Returns a CellSummary with blocked=True if ALL combos of hand_class are
    blocked by the board, or out_of_range=True if total_weight is 0 (not in range).
    """
    ...


def cell_color(summary: CellSummary) -> str:
    """Pio-convention color blend (per spec §7.3).

    if summary.blocked or summary.out_of_range or summary.empty:
        return '#3a3a3a'  # faded grey
    r = summary.fold * 220 + summary.call * 220 + summary.raise_ * 40
    g = summary.fold * 40  + summary.call * 200 + summary.raise_ * 180
    b = summary.fold * 40  + summary.call * 40  + summary.raise_ * 60
    return f'rgb({int(r)},{int(g)},{int(b)})'
    """
    ...


def render(state: AppState) -> None:
    """Render the §3.3 range matrix view into the current NiceGUI slot.

    Contains:
    - A 13x13 grid (ui.grid(columns=13)) of clickable cells.
    - Each cell: background color (Pio blend), hand-class label upper-left,
      optional frequency footer (visible if state.prefs.matrix_show_frequencies).
    - Click handler: opens the combo inspector strip below (inspect_panel).
    - Hover tooltip: combo count + weighted F/C/R %.
    - Out-of-range cells: faded grey '—'.
    - Blocker-removed cells: slashed overlay + tooltip 'all combos blocked by board: {cards}'.

    Wrapped in @ui.refreshable. The progress timer in app.py calls
    range_matrix.refresh() after each progress tick IF the solve produced a new
    strategy snapshot. Clicking a tree node ALSO triggers refresh.

    NiceGUI ElementFilter markers (Agent C asserts on these):
      'range-matrix-display'             (outer card; distinct from Agent A's
                                          'spot-input-panel')
      'matrix-cell'                      (each of 169 cells; Agent C's smoke 6
                                          asserts ElementFilter(marker='matrix-cell')
                                          yields 169 elements)
      'matrix-cell-{cls}'                ('matrix-cell-AA', 'matrix-cell-AKs', ...)
      'combo-inspector-strip'            (the strip below the matrix when a cell
                                          is clicked)
      'combo-inspector-row-{combo}'      (one per surviving combo in the cell;
                                          combo encoded as 'AsKs', etc.)
    """
    ...


def inspect_panel(state: AppState, hand_class: str) -> None:
    """Render the combo inspector strip below the matrix when a cell is clicked.
    Per spec §3.3:

    - List every surviving combo in hand_class (post-blocker).
    - Per combo: horizontal stacked bar showing exact action distribution.
    - Per combo: EV (in mBB), reach probability, infoset key (monospace, copyable).
    """
    ...
```

### `ui/views/tree_browser.py`

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from poker_solver.hunl import HUNLPoker, HUNLState
from poker_solver.solver import SolveResult
from ui.state import AppState


@dataclass
class TreeNode:
    """A node in the decision tree. Lazy-expanded; children loaded on demand.

    Per spec §8.1.
    """
    id: str                             # unique; e.g. "root", "root/p0_check",
                                        # "root/p0_check/p1_bet75"
    label: str                          # e.g. "[start]", "[SB: bet 75%]"
    history: tuple[object, ...]         # the action sequence leading here
    state_snapshot: HUNLState           # the HUNL state at this node
    player_to_act: int                  # 0, 1, or -1 (chance/showdown)
    reach_prob: float                   # combined reach over both players' strategies
    range_weighted_ev: float            # in mBB
    legal_actions: tuple[object, ...]   # actions available from this state
    action_freqs: tuple[float, ...]     # per-action frequency (range-weighted average)
    action_evs: tuple[float, ...]       # per-action EV (in mBB)


class SolveTree:
    """Tree adapter: walks the post-solve strategy + game graph and yields
    NiceGUI-tree-compatible nodes in DFS pre-order. Lazy expansion.
    Per spec §8.1.

    Construction takes O(1); only the root is materialized. Children are
    computed on demand the first time a node is expanded.
    """

    def __init__(
        self,
        game: HUNLPoker,
        result: SolveResult,
        min_reach: float = 0.01,    # Q6 LOCKED default per pr10a_spec.md §0.1
    ) -> None:
        self.game: HUNLPoker = game
        self.result: SolveResult = result
        self.min_reach: float = min_reach
        self.root: TreeNode = ...
        self._cache: dict[str, list[TreeNode]] = {}      # node_id -> children

    def expand(self, node_id: str) -> list[TreeNode]:
        """Return the children of a node, computing on demand and caching.

        Per spec §3.4 performance guard: if raw children count > 500, return
        only top 100 by reach_prob; the caller appends a '...N more nodes hidden'
        placeholder node with id like '{node_id}/__truncated__'.

        Returns [] for terminal / showdown / chance-terminal nodes.
        """
        ...

    def get_node(self, node_id: str) -> TreeNode:
        """Lookup a node by id (recursively walks from root, expanding as needed
        to satisfy the path). Used when the user clicks a tree node and we need
        to fetch its current TreeNode for the range matrix refresh."""
        ...

    def set_min_reach(self, min_reach: float) -> None:
        """Update the reach-prob filter. Clears the expansion cache (filter
        changes which children are visible at every level)."""
        ...


def tree_node_to_dict(node: TreeNode) -> dict[str, object]:
    """Convert a TreeNode to NiceGUI's ui.tree dict schema:
        {'id': node.id, 'label': <rich HTML label>, 'children': [...]}

    The label is rendered as HTML to color-code action frequencies (red/yellow/
    green badges per spec §8.3). Example:
        '[SB: bet 75%]   <span style="color: green">bet75% 65% EV +120</span> · ...'

    Children are loaded lazily: this function does NOT recursively walk; it just
    emits the immediate-child level, leaving deeper levels as on_expand callbacks.
    """
    ...


def on_tree_node_selected(state: AppState, node_id: str) -> None:
    """Handler invoked when the user clicks a tree node. Updates
    state.current_tree_node_id and triggers range_matrix.refresh() (the matrix
    re-renders conditioned on the new tree node)."""
    ...


def on_tree_node_expanded(state: AppState, node_id: str) -> None:
    """Handler invoked when the user expands a tree node. Calls
    state.current_tree.expand(node_id) and patches the tree widget."""
    ...


def render(state: AppState) -> None:
    """Render the §3.4 decision tree browser into the current NiceGUI slot.

    Contains:
    - A reach-prob slider (ui.slider(min=0, max=1, step=0.01, value=0.01)) above
      the tree; tooltip suggests '0.01 hides ~95% of low-reach noise nodes'.
    - A ui.tree widget showing the SolveTree, lazy-expanded.
    - Per-node label rendered with action stats inline (color-coded badges).
    - A truncation badge in the header ('N nodes hidden by DOM cap' or similar)
      if global node visibility cap is hit.

    Wrapped in @ui.refreshable so a new solve result regenerates the tree.

    NiceGUI ElementFilter markers (Agent C asserts on these):
      'tree-browser'                    (outer card)
      'tree-widget'                     (the ui.tree element)
      'tree-reach-slider'
      'tree-truncation-badge'           (optional; only shown if DOM cap hit)
    """
    ...
```

## Critical correctness items

### 1. Combo → frequency mapping has no off-by-one (correctness item #2)

This is **the** load-bearing correctness item for your work. The spec §11 item 2 calls it out explicitly. Agent C's `test_combo_to_cell_mapping_no_off_by_one` (smoke 7) is the gate.

The contract:

- For every hand class returned by `enumerate_hand_classes()`, the cell at row=hc_row, col=hc_col displays a label equal to `hand_class_label(...)` matching the ASCII grid in spec §3.3.
- For every combo (card1, card2), `classify_combo(card1, card2)` returns the hand class label whose cell that combo "lives in." Round-trip: `combo in enumerate_combos(classify_combo(*combo))` is always true.
- For a pair `XX`: 6 combos. For suited `XYs`: 4 combos. For offsuit `XYo`: 12 combos. Total = 13×6 + 78×4 + 78×12 = 1326.

You do NOT own `enumerate_*` (Agent A does). But your matrix render *uses* them to populate cells; a bug in your aggregation logic (e.g., iterating row-major when the data is column-major) would produce visible off-by-ones. Be explicit about row/col semantics in code comments.

### 2. Blocker filtering doesn't crash on edge cases

Per spec §11 item 5: if every combo in a hand class is blocked, the cell renders blocked-grey with a tooltip. Do not raise an exception. Per spec §3.3: "blocker-removed combos: render with a slashed pattern overlay and tooltip explaining."

Edge case: hand class `XX` (pair) on a board containing both red Xs has 1 remaining combo (the black pair). Hand class `XYs` on a board containing the matching suit of X (and not Y) might have 3 of 4 combos blocked. Your aggregator must handle all combinatorics — `survivors` may be 0, 1, 2, 3, 4, 6, or 12 depending on case.

### 3. Tree expansion is lazy

Per spec §11 item 6 + §8.5: expanding the root yields ≤ 30 children (preflop has at most the number of legal opening actions). The full HUNL tree has 10⁴–10⁶ infosets; eagerly materializing would crash the browser.

- `SolveTree.__init__` materializes only the root.
- `SolveTree.expand(node_id)` is called only when the user clicks expand on a tree node.
- The expansion cache `self._cache` holds expanded subtrees in memory until the spot or solve result changes (then it's invalidated).

Agent C's smoke test asserts: `len(solve_tree.expand('root')) <= 30`.

### 4. Per-node child cap (100) + global DOM cap (2000)

Per spec §3.4 + §8.5:

- If a node's raw expansion yields >500 children, return top 100 by `reach_prob`. Append a "...N more nodes hidden" placeholder node (id like `{parent}/__truncated__`, label like `"... 412 more nodes hidden"`). The placeholder is **not expandable** (returns [] on expand).
- Global cap: total visible tree nodes ≤ 2000. When the cap is exceeded, trim the deepest branches first. Report the truncation count in a header badge.

The 2000 cap is a soft target — measure visible nodes by walking the tree-widget DOM size or by tracking expansion depth. If tracking exactly is hard, approximate by capping max-depth-shown to a depth that empirically keeps total nodes under 2000.

### 5. Color blend formula is exact

Per spec §7.3, the blend is:

```python
r = summary.fold * 220 + summary.call * 220 + summary.raise_ * 40
g = summary.fold * 40  + summary.call * 200 + summary.raise_ * 180
b = summary.fold * 40  + summary.call * 40  + summary.raise_ * 60
```

Do not "improve" the palette. Pio's convention is a learned visual standard; player muscle memory depends on it.

For mixed frequencies, `summary.fold + summary.call + summary.raise_` should sum to ~1.0 (since they're aggregate probabilities over the surviving combos). If it doesn't (rounding noise), don't renormalize — the blend formula degrades gracefully because each channel is bounded.

### 6. Tooltip text on hover

Per spec §3.3 ("always show numeric frequencies on hover"):

- Cell-aggregate: "AKs (4 combos): 78% raise · 15% call · 7% fold" or similar.
- Combo-level (in the inspector strip): "AhKh: 65% raise / 30% call / 5% fold; EV +120 mBB; reach 0.045".

Use `ui.tooltip` for the cell-hover behavior. Agent C may assert on tooltip presence via NiceGUI's test harness if available; don't worry about asserting on tooltip *content*.

### 7. Refresh discipline (`@ui.refreshable`)

Per spec §7.4: wrap the matrix render in `@ui.refreshable`. Refresh triggered by:
1. Progress timer (in Agent A's `app.py`) calling `range_matrix.refresh()` after each tick, if the strategy snapshot changed since last refresh.
2. User clicks a tree node → `on_tree_node_selected(state, node_id)` updates `state.current_tree_node_id` then calls `range_matrix.refresh()`.

Per-cell `.style()` mutations would also work but `@ui.refreshable` is simpler and lets the matrix add/remove cells dynamically when the board changes (blocker-removal can collapse a hand class).

## License-aware sourcing

**You may port architecturally (not code-copy) from MIT/Apache sources:**
- `references/code/slumbot2019/` (**MIT**) — for solver concept reference (no GUI).
- `references/blog/gtow_how_solvers_work.md` — the "color convention" / "range matrix is the centerpiece" intuition. Cite this if you adopt the convention (which is locked).
- `references/blog/piosolver_technical_details.md` — desktop solver UI layout precedent.
- `nicegui/llms.md` — NiceGUI patterns. Cite mental model number on >5 LOC borrowed patterns.

**You may NOT copy from AGPL sources:**
- `references/code/postflop-solver/` — **AGPL v3**. No code copy. The UI patterns in postflop-solver's WASM-based GUI are READ-ONLY inspiration.
- `references/code/TexasSolver/` — **AGPL v3**. Same rule.

**You may NOT extrapolate from training data.** If you "remember" a tree-widget pattern or a color blend, ground it in `nicegui/llms.md` or the PR 10 spec.

If you copy a non-trivial NiceGUI snippet (>~5 LOC) from a documented mental model, add an attribution comment:
```python
# Pattern from nicegui/llms.md mental model 8 (refreshable elements).
```

## Quality bar

- **ruff clean:** `ruff check ui/views/range_matrix.py ui/views/tree_browser.py` reports zero issues.
- **black clean:** `black --check ui/views/range_matrix.py ui/views/tree_browser.py` reports no changes needed.
- **mypy strict-clean on new code:** `mypy --strict ui/views/range_matrix.py ui/views/tree_browser.py` reports zero errors.
- **No new third-party deps beyond `nicegui` (which Agent C adds to `pyproject.toml`).** Imports: `nicegui`, `numpy`, `poker_solver.*`, `ui.state`, stdlib.
- **All existing tests still pass.** Run `pytest -x` after your work lands.
- **Code size budget: ~500–700 LOC** combined across the two files. Stay within budget.

## Reference-first rule

Before any technical claim or code pattern, check the local references. `/Users/ashen/Desktop/poker_solver/references/README.md` indexes them. Never extrapolate from training data when a local source exists.

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Lint + format
ruff check ui/views/range_matrix.py ui/views/tree_browser.py
black --check ui/views/range_matrix.py ui/views/tree_browser.py

# 2. Type-check
mypy --strict ui/views/range_matrix.py ui/views/tree_browser.py

# 3. Smoke-import (catches circular import bugs + Agent-A contract drift)
python -c "
from ui.views.range_matrix import (
    cell_strategy_summary, cell_color, render as matrix_render,
    inspect_panel, CellSummary,
)
from ui.views.tree_browser import (
    SolveTree, TreeNode, tree_node_to_dict,
    on_tree_node_selected, on_tree_node_expanded, render as tree_render,
)
print('range_matrix + tree_browser imports OK')
"

# 4. Color blend sanity
python -c "
from ui.views.range_matrix import cell_color, CellSummary
# All-fold cell: should be pure red (220, 40, 40)
s = CellSummary(fold=1.0, call=0.0, raise_=0.0, combo_count=4)
c = cell_color(s)
assert c == 'rgb(220,40,40)', f'expected rgb(220,40,40), got {c}'
# All-raise cell: should be pure green (40, 180, 60)
s = CellSummary(fold=0.0, call=0.0, raise_=1.0, combo_count=4)
c = cell_color(s)
assert c == 'rgb(40,180,60)', f'expected rgb(40,180,60), got {c}'
# Blocked: grey
s = CellSummary(blocked=True)
c = cell_color(s)
assert c == '#3a3a3a', f'expected #3a3a3a, got {c}'
print('color blend smoke OK')
"

# 5. (If Agent A has landed) SolveTree smoke - just constructor + root expansion
# This requires Agent A's state.py + a SolveResult (which needs a real solve).
# Skip if not available; Agent C's smoke tests will exercise this end-to-end.

# 6. Full test suite (existing tests must still pass)
pytest -x 2>&1 | tail -20
```

If any of the above fails, fix the issue before reporting done. If a smoke test reveals a spec ambiguity or Agent-A contract drift, **stop and flag it** — do not silently work around it.

## Report back format

When done, write a concise report (≤300 words) covering:

1. Files created with line counts.
2. Any spec amendment you made or contract drift you flagged (and why).
3. Verification command output (paste tails).
4. Any open question you couldn't resolve from the spec / PLAN — flag for human review.
5. License attributions you added (if any).
