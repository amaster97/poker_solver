# PR 10 spec — first UI for the poker solver (NiceGUI scaffold)

## 1. Goal

Ship the **first end-to-end browser UI for the solver** as a NiceGUI app served
locally. PR 10 produces a single-user, single-process web app that wraps the
existing Python solver (`poker_solver.solve`, `poker_solver.exploitability`,
`HUNLPoker`, `HUNLConfig`, the post-PR-5 postflop solve path) behind a poker-
player-shaped UI: spot input, solver controls, **range matrix viewer (the
centerpiece)**, and a decision-tree browser. The UI runs via
`poker-solver ui` and opens `http://localhost:8080/` in the user's browser. No
Rust changes; no new solver math; no abstraction work.

PR 10's deliverable is a *visual surface area* over the engine — the same
artifact that PioSolver, GTO Wizard, and DeepSolver expose, but Python-native
and MIT-licensed. By the time PR 10 lands, the engine has shipped Kuhn (PR 1),
Leduc (PR 2), the HUNL tree (PR 3), push/fold charts (PR 3.5), card abstraction
(PR 4), the first HUNL postflop solve (PR 5), Rust port (PR 6), Brown parity
(PR 7), SIMD/cache-blocking perf (PR 8), and HUNL preflop (PR 9). The
**Python `solve()` entrypoint is the single API surface the UI calls**;
backend=rust is opt-in but identical-shape from the UI's perspective.

### Non-goals (explicit)

- **No native desktop wrapper.** Packaging into `.dmg` with codesign+notarize
  is **PR 11**. PR 10 is browser-served only; the user runs `poker-solver ui`
  and a browser opens. NiceGUI's `native=True` mode (pywebview window) is *not*
  used in PR 10 — that introduces a tk/pywebview dependency that we want
  packaged once, in PR 11, behind a single `--native` flag.
- **No real-time multiplayer.** Single user, single browser, single solve at a
  time. NiceGUI is a single-process / single-worker framework and we lean on
  that — module-level state is the app state for the one user (see §9 below for
  why this is safe in PR 10's scope and what we still guard).
- **No remote / cloud mode.** The server binds to `127.0.0.1` by default. No
  authentication; no TLS; no remote access. A future `--host 0.0.0.0 --auth`
  flag is plausible but explicitly deferred.
- **No solver math changes.** The UI consumes the existing `SolveResult` shape
  and the existing exploitability function. Anything the UI needs that the
  engine doesn't already expose is added as a *thin adapter* in
  `ui/state.py` — never by mutating `poker_solver/`.
- **No new solver tests.** PR 10's tests cover *the UI*: page renders, button
  clicks dispatch correctly, range-matrix maps combos to frequencies without
  off-by-one, the stop button halts within 1 iteration. Engine tests are
  untouched.
- **No node locking / exploitative mode.** Nodelocking is a Phase-4 feature
  (PLAN.md §1 "Features beyond v1"). PR 10 visualizes equilibrium strategies
  only; locking lands later as additive UI on top of this scaffold.
- **No live exploitability *target*-driven solve.** "Solve until exploitability
  < X" is a one-line addition but explicitly deferred to PR 11 polish. PR 10's
  stop condition is "ran N iterations" or "user clicked stop."
- **No persistent solve library.** PR 11 owns the on-disk solved-spot library
  (cache of `SolveResult` keyed by spot hash). PR 10 ships a *placeholder*
  library view — see §3.5 "library viewer" — so PR 11's wiring point is clear.
- **No multi-tab / multi-window state synchronization.** If the user opens two
  browser tabs against the same NiceGUI server, behavior is undefined (both
  tabs share module-level state; the last write wins). Documented limitation.

## 2. Design philosophy

The minimum-viable solver UI is the one a poker player can sit down at and
recognize. The 13×13 range matrix is the *only* universal element across every
solver UI (PioSolver, GTO Wizard, DeepSolver, Monker, Holdem Resources
Calculator) — every other panel feeds into or branches off it. PR 10's design
collapses to: **everything that isn't the range matrix exists to populate or
filter what the range matrix shows.**

Concretely:

- **Spot input → range matrix shape.** The board, hole-card ranges, stack
  depth, and position selection define which 169 cells contain meaningful
  data and which are blocker-filtered out.
- **Solver run controls → range matrix data.** Every "solve" press refreshes
  the per-combo strategy mix the matrix displays. The matrix is a function of
  the most recent `SolveResult`.
- **Decision tree browser → range matrix node selection.** The tree browser
  lets the user say "show me the range matrix conditional on *this betting
  history node*." Selecting a node updates the matrix to show the player-to-
  act's strategy *at that node*.
- **Library viewer → load a precomputed `SolveResult` from disk** (PR 11) and
  navigate to its range matrix. In PR 10 this is a stub list.

This collapses to **one shared "current view" state**: `(spot, solve_result,
selected_tree_node) → range matrix render`. Everything else is input or
filtering on top.

**UI inspiration anchors** (read from `references/blog/gtow_how_solvers_work.md`
and `references/blog/piosolver_technical_details.md`):

- Pio's "Range Explorer" color convention: red=fold, yellow=call/check,
  green=raise/bet. We adopt this directly. This is *the* visual standard
  every player already reads fluently.
- GTO Wizard's "click cell → show per-combo strategy bar" interaction. We
  adopt this for the inspector panel.
- Pio's "decision tree on the left, current node's strategy on the right"
  layout. We adopt this layout, transposed: tree on the right (lighter
  weight; expansion-driven), matrix on the left/center (the deliverable).

Color and frequency precedence: **always show numeric frequencies on hover**
(combo-level: "AhKh: 65% raise, 30% call, 5% fold"). Color alone is
perceptually misleading at extreme mixings; numbers are the ground truth.

## 3. Five core views

The app is one page (`/`) with a four-pane layout: header bar + three panels.
Panels are sized via NiceGUI's `ui.splitter()` so the user can resize. Default
layout (assuming a ≥1280px window):

```
┌────────────────────────────────────────────────────────────────────┐
│ Header: poker-solver / current spot label / dark mode / library    │
├────────────────────────────────┬───────────────────────────────────┤
│                                │                                   │
│ Left pane (320 px):            │ Center pane (flex):               │
│   - Spot input panel           │   - Range matrix display          │
│   - Solver run panel           │     (selected node's strategy)    │
│                                │   - Combo inspector strip         │
│                                │     (below matrix)                │
│                                │                                   │
├────────────────────────────────┴───────────────────────────────────┤
│ Bottom pane (240 px, collapsible):                                 │
│   - Decision tree browser (expandable nodes, EV + freq per action) │
└────────────────────────────────────────────────────────────────────┘
```

Library viewer (§3.5) is a modal opened from the header — not a persistent
panel — because in PR 10 it's a stub.

### 3.1 Spot input panel (`ui/views/spot_input.py`)

Inputs that define an `HUNLConfig` + a pair of `Range`s + a starting street.

- **Board cards via card-picker.** A 4×13 grid (4 suits × 13 ranks) of
  selectable card buttons; clicked cards highlight and append to the board.
  Maximum 5 cards. Layout: `ui.grid(columns=13).classes('gap-1')` inside a
  card. Each cell is a `ui.button` showing rank + suit symbol (♠♥♦♣) with
  red/black coloring; clicked state toggled via Quasar `flat`/`unelevated`
  props. A `Clear board` button.
  - Internal model: `state.board: list[Card]` (uses `poker_solver.card.Card`).
  - **Constraint:** if the user picks 0 cards, starting_street = PREFLOP.
    3 cards = FLOP. 4 cards = TURN. 5 cards = RIVER. 1, 2 cards: greyed out
    "invalid" state until they pick the third or clear.
  - **Blocker safety:** if a board card is also in a hole-card range, the
    matrix automatically filters that combo (handled in render); the user
    isn't blocked from picking but a notification appears.

- **Hole-card ranges via 13×13 matrix OR string input** (toggle).
  - **Matrix mode (default):** a 13×13 grid (ranks × ranks) where the user
    paints frequencies. Click a cell once → set freq=1.0 (full include).
    Click again → cycle through 1.0 → 0.5 → 0.25 → 0.0 (cell removed). Right-
    click or shift-click → freely set frequency via popover slider. The
    diagonal is pairs (AA, KK, ..., 22); above the diagonal is **suited** (AKs,
    AQs, ...); below the diagonal is **offsuit** (AKo, AQo, ...). This is the
    Pio / GTOW canonical convention.
    - Cell color reflects current frequency: gradient from white (0) to a
      saturated blue (1.0). Distinct from the solve-strategy color palette
      (red/yellow/green) so a user can never confuse "what's in my range" with
      "what does the solver want this combo to do."
  - **String mode:** a `ui.textarea` accepting `parse_range` syntax
    ("AA, KK-TT, AKs, A5s-A2s, 76s+, KQo"). On blur, parse and reflect into
    the matrix; on syntax error, show a notification + leave matrix unchanged.
  - **Two range inputs** (one per player). A `ui.tabs` switches between "P0
    (SB / BTN)" and "P1 (BB)". Each tab has its own matrix + string input.
  - Internal model: `state.ranges: tuple[Range, Range]` where `Range` is
    extended in `ui/state.py` to track per-combo frequency (not just
    membership). See §9.

- **Stack depths.** Two `ui.number` inputs ("P0 stack (BB)", "P1 stack (BB)").
  Default 100. Range [2, 250] enforced by `validation` arg. If the user enters
  ≤15, a warning toast suggests using push/fold charts (PR 3.5).
  - Internal model: `state.stacks_bb: tuple[int, int]`.

- **Position selection.** `ui.toggle(['SB acts first', 'BB acts first'])`
  defaulting to "SB acts first" (the standard HUNL convention; matches
  `HUNLConfig` P0 = SB = button). Visible as a clarifier; not editable in PR
  10 (we lock HUNL roles). Disabled but present, with tooltip explaining the
  convention.

- **Pot / ante / blinds.** Three small inputs: SB blind (default 50 cents = 0.5
  BB), BB blind (default 100 cents = 1 BB), ante (default 0). Most users won't
  touch these; they're collapsed under an `ui.expansion('Blinds & ante')`.

- **Reset spot** button → clears board, ranges, stacks back to defaults.

- **Load from preset** dropdown — `ui.select` with three options:
  `'Default 100BB postflop'`, `'River subgame (PR 3 fixture)'`, `'Empty
  preflop'`. Each loads a baked-in spot. Useful for first-time users and demo
  screenshots.

### 3.2 Solver run panel (`ui/views/run_panel.py`)

- **Bet-size menu.** Six checkboxes corresponding to the six action-
  abstraction sizes (`33%`, `75%`, `100%`, `150%`, `200%`, `all-in`). User
  unchecks to drop a size from the abstraction. At least one must be checked
  (validation). Default: all checked.
  - **Custom size** input: a text field accepting comma-separated pot
    fractions (e.g. "0.5, 1.2"). On submit, these become extra sizes
    appended to `HUNLConfig.bet_size_fractions`.
  - Internal model: `state.bet_sizes: tuple[float, ...]` and
    `state.include_all_in: bool`.

- **Raise cap selectors.** Two `ui.number` inputs: preflop cap (default 4),
  postflop cap (default 3). Range [1, 10] enforced. Match PLAN.md §1.

- **Iteration count.** Single `ui.number` (default 2000, range [100, 1_000_000])
  → `iterations` parameter to `solve()`.

- **Solve / pause / stop buttons.** Three buttons in a row:
  - `Solve` (green, `unelevated`) — disabled while solving. Spawns the
    background solve (§6).
  - `Pause` (yellow, `flat`) — disabled when not solving. Sets a flag the
    background thread checks; the worker pauses between iterations, retaining
    state.
  - `Stop` (red, `flat`) — disabled when not solving. Sets a stronger flag;
    the worker exits its loop within 1 iteration (§6). Strategy from
    iterations completed so far is preserved.

- **Live exploitability chart.** `ui.line_plot(n=200, update_every=1)` plotted
  beneath the solve buttons. X-axis: iteration number. Y-axis: exploitability
  in milli-BB per pot (log scale optional via toggle). The background thread
  pushes `(iter, expl)` pairs every `log_every` iterations (default
  `iterations // 100`, min 10) via NiceGUI's event loop (§6).
  - **Display gates:** for spots with > 50_000 expected iterations, the chart
    samples every 100th update to avoid flooding the WebSocket outbox
    (NiceGUI's per-update batching protects within a single callback but
    different timer ticks send separately — per `nicegui/llms.md` mental model
    9).

- **Progress + current state readout.** Below the chart:
  - "Iteration N / M" (current vs target).
  - "Wall-clock: T sec" (elapsed since solve start).
  - "Current exploitability: X mBB/pot" (last sampled).
  - "Backend: python | rust" (read from `SolveResult.backend`).
  - "Status: idle | running | paused | stopped | done | error".

### 3.3 Range matrix display (`ui/views/range_matrix.py`)

The centerpiece. A 13×13 grid (`ui.grid(columns=13)`) of cells, each cell
representing one of the 169 strategically-distinct starting hand classes
(pairs on diagonal, suited above, offsuit below). Each cell shows:

- **Background color:** weighted blend of fold-red, call/check-yellow,
  raise/bet-green, computed from the aggregate per-combo strategy at the
  currently-selected tree node (the root by default).
- **Cell label:** hand-class shorthand ("AA", "AKs", "AKo", etc.) in the
  upper-left.
- **Frequency text (optional):** a small footer in each cell showing the
  dominant action's frequency (e.g. "78%") if frequencies are extreme; for
  highly mixed combos a tiny histogram or "MIX" tag.
- **Out-of-range cells:** if the hand class is not in the player-to-act's
  range, the cell is rendered as a faded grey "—" with no color blend.
- **Blocker-removed combos:** if all combos of a hand class are blocked by
  the board, render with a slashed pattern overlay and tooltip explaining.

**Color blend formula** (per cell, given combos `C` in the cell that survive
blockers and are in the range):

```
freq_fold[c]  = avg over c in C of strategy[c, fold_action]
freq_call[c]  = avg over c in C of strategy[c, {check, call} actions]
freq_raise[c] = avg over c in C of strategy[c, {bet, raise, all-in} actions]
# Then weight by combo count (e.g., AKs has 4 combos with full board removed)
RGB = freq_fold * (220, 40, 40)   # red
    + freq_call * (220, 200, 40)  # yellow
    + freq_raise * (40, 180, 60)  # green
```

(This matches Pio's convention; "yellow" empirically reads as warm sand and
parses cleanly against red/green for protanopia-affected users. We do **not**
support custom palette in PR 10 — that's a polish task.)

**Click interaction:** clicking a cell opens the **combo inspector strip**
(`ui/views/range_matrix.py::inspect_panel`) below the matrix:

- Lists every individual combo in that hand class that survives blockers
  (e.g., for AKs on a `Kh 7h 2d` board, only `AsKs`, `AdKd`, `AcKc` are listed;
  `AhKh` is blocked).
- Per combo, a horizontal stacked bar showing the precise action distribution
  (fold / check / call / each bet size / each raise size / all-in).
- Per combo, the EV in mBB and the reach probability at the current tree node.
- Per combo, the infoset key (small, monospace, copyable).

**Hover interaction:** hovering a cell shows a tooltip with the cell-aggregate
numbers: combo count, weighted fold/call/raise %.

**Hand-class ordering** in the 13×13 grid (canonical, top-left to bottom-right):

```
       A   K   Q   J   T   9   8   7   6   5   4   3   2
   A  AA  AKs AQs AJs ATs A9s A8s A7s A6s A5s A4s A3s A2s
   K  AKo KK  KQs KJs KTs K9s K8s K7s K6s K5s K4s K3s K2s
   Q  AQo KQo QQ  QJs QTs Q9s Q8s Q7s Q6s Q5s Q4s Q3s Q2s
   J  AJo KJo QJo JJ  JTs J9s J8s J7s J6s J5s J4s J3s J2s
   T  ATo KTo QTo JTo TT  T9s T8s T7s T6s T5s T4s T3s T2s
   9  A9o K9o Q9o J9o T9o 99  98s 97s 96s 95s 94s 93s 92s
   8  A8o K8o Q8o J8o T8o 98o 88  87s 86s 85s 84s 83s 82s
   ...
```

`(row, col)` with row=`max(rank1, rank2)`, col=`min(rank1, rank2)` for non-
pairs; pairs sit on the diagonal. Suited if `row < col` reading left-to-right
relative to the diagonal; offsuit if below. This is the **same orientation
PioSolver and GTO Wizard use**, so a player's eyes already know where AKs
lives.

**Critical correctness item #2 (per spec): combo → frequency mapping has no
off-by-one.** §11 covers the property test.

### 3.4 Decision tree browser (`ui/views/tree_browser.py`)

Below the matrix, a collapsible tree showing the betting action tree from
the root of the current spot. Each node shows:

- **Node label:** a compressed betting history token (e.g. `[start]`, `[SB:
  bet 75%]`, `[SB: bet 75%, BB: raise to 200%]`, `[chk-chk]`, `[turn: 7♥]`).
- **Per-action display** at each player-decision node: a row of small badges,
  one per legal action, showing EV (in mBB) and frequency (in %) for the
  player-to-act's *aggregate* (i.e. range-averaged) strategy.
- **Hover detail:** infoset key (truncated, monospace), reach probability,
  range-weighted EV.
- **Click action:** clicking a node sets it as the "current tree node" —
  re-renders the range matrix (§3.3) conditioned on that history.

**Implementation:** uses NiceGUI's `ui.tree()` widget, populated from a tree
adapter in `ui/state.py::SolveTree`. The tree adapter walks the post-solve
strategy + game graph and yields nodes in DFS pre-order. Each node is a dict
`{'id': node_id, 'label': ..., 'children': [...]}` matching NiceGUI's tree
schema. The full HUNL tree is too large to materialize eagerly (millions of
nodes); the adapter is **lazy** — children are computed on demand the first
time a node is expanded.

**Reach-probability filter:** a `ui.slider(min=0, max=1, step=0.01, value=0)`
above the tree controls the **minimum reach threshold**. Nodes with combined
reach < threshold are hidden. Default 0 (show everything); a slider tooltip
suggests "0.01 hides ~95% of low-reach noise nodes."

**Performance guard:** if the tree-adapter's lazy expansion of a node yields
>500 children, render only the top 100 by reach probability and append a
"...N more nodes hidden" placeholder. Users rarely care about ultra-low-reach
branches; this keeps the browser DOM under control.

### 3.5 Library viewer (`ui/views/library_browser.py`) — STUB for PR 10

A `ui.dialog()` opened from the header. In PR 10 it contains:

- A header label "Solve library (PR 11)".
- Body: "Solved spots persisted to disk land in PR 11. For now, this is a
  placeholder showing the wiring point."
- A disabled "Load from disk" button.
- A small list of three demo entries (faked, just placeholder rows) with
  hand-typed names like "AKo vs QQ on K72r" — clicking them does nothing
  (toast "PR 11 — load from disk is not yet wired").

**Why ship the stub in PR 10:** PR 11's "library mode + packaging" PR has a
narrow wiring point (one file + one CLI flag). Pre-defining the dialog,
state-store, and CLI surface here means PR 11 is mechanical.

The stub also covers the import path: PR 10's `ui/app.py` imports
`library_browser` and renders the header button. PR 11's diff is then
"`library_browser.py` grows a real loader; everything else is unchanged."

## 4. Files to create

| Path | Owner agent (see §10) | Purpose |
|---|---|---|
| `ui/__init__.py` | A | Empty package init. Exposes `__version__`. |
| `ui/app.py` | A | NiceGUI app entrypoint. `@ui.page('/')` builder; calls into the five views; wires the keyboard shortcuts; calls `ui.run()`. |
| `ui/state.py` | A | Shared app state. Module-level singletons + dataclasses for `Spot`, `RangeWithFreqs`, `SolveSession`, `SolveTree`. Cancellation flag. Background-thread plumbing (`solver_runner`). |
| `ui/views/spot_input.py` | A | The §3.1 view — board picker, range matrix input, stack/position selection. |
| `ui/views/run_panel.py` | A | The §3.2 view — bet-size menu, raise caps, iterations, run/pause/stop, live exploitability chart. |
| `ui/views/range_matrix.py` | B | The §3.3 view — 13×13 matrix, color blend, combo inspector strip. The visual centerpiece. |
| `ui/views/tree_browser.py` | B | The §3.4 view — collapsible action tree, per-node EV+frequency display, reach-probability filter. |
| `ui/views/library_browser.py` | C | The §3.5 stub view. |
| `tests/test_ui_smoke.py` | C | Smoke tests: page renders without exception, every view's primary widgets exist, the solve button triggers a background task, the stop button halts within 1 iteration. Uses NiceGUI's `User` fixture (async, in-process, no real browser; per `nicegui/llms.md` testing section). |

**Why split into a `ui/` package outside `poker_solver/`?** Two reasons.

1. **Optional dependency boundary.** NiceGUI is heavyweight (FastAPI, uvicorn,
   socket.io, Vue, Quasar — ~50 MB of wheels). Putting it inside
   `poker_solver/` and importing at package load would force every solver
   user (including headless / CI / Rust-only users) to install it. Keeping
   `ui/` as a separate package outside the engine namespace makes the engine
   loadable with zero UI overhead.
2. **PLAN.md prefigured this.** PLAN.md §3 architecture summary shows:
   ```
   poker_solver/        Python reference (ground truth)
   crates/cfr_core/     Rust production
   tests/               Differential + intuition + parity tests
   references/          Papers, repos, blog posts
   ui/                  NiceGUI app (post-PR 10)
   scripts/             setup_references.sh, check_pr.sh
   ```
   The `ui/` directory is a sibling of `poker_solver/` and `crates/`. PR 10
   creates exactly that.

**Why not also add `tests/test_ui_state.py`** for state-management unit tests?
Considered; rolled into `tests/test_ui_smoke.py` to keep PR 10 small. If the
state module grows past ~300 lines, split off in PR 11.

## 5. Files to modify

- **`pyproject.toml`** — add a `[project.optional-dependencies]` group:
  ```toml
  ui = ["nicegui>=2.0,<3.0"]
  ```
  Not added to base `dependencies`. Install instructions become
  `pip install -e .[ui]`. Pinned upper bound (`<3.0`) because NiceGUI 2.x has a
  stable API; we don't want a future 3.x major upgrade to silently break the
  UI smoke test. Lower bound 2.0: needs `ui.state()`, `ElementFilter`, and
  the modern `background_tasks` API (all available since 2.0).
  - Also add a marker in `[tool.pytest.ini_options]`:
    ```toml
    markers = ["ui: tests that require nicegui (skip if not installed)"]
    ```

- **`poker_solver/cli.py`** — add a `ui` subcommand:
  - `poker-solver ui --port 8080 --host 127.0.0.1 --dark-mode auto`
  - Implementation: import `ui.app` (lazy; only at command invocation time so
    the rest of the CLI works without NiceGUI installed) and call its
    `launch(port, host, dark_mode)` function.
  - If NiceGUI not installed → catch `ImportError` (per NiceGUI llms.md style
    guide, use `ImportError` not `ModuleNotFoundError`) and print: "UI
    support not installed. Install with `pip install poker-solver[ui]`."
    Return exit code 2.

- **`README.md`** — add a "UI" section:
  ```
  ## UI

  An optional browser-based UI is available:

      pip install -e .[ui]
      poker-solver ui

  This launches a local NiceGUI server (default http://localhost:8080) with:
  - A 13×13 range matrix viewer (Pio convention: red=fold, yellow=call, green=raise)
  - Board input via card picker
  - Solver run controls with live exploitability tracking
  - A decision tree browser showing EV + frequency per action

  See `docs/pr10_prep/pr10_spec.md` for design details.
  ```
  Insert after the existing CLI usage section, before the development notes.

**Files NOT modified:** `poker_solver/solver.py`, `poker_solver/dcfr.py`,
`poker_solver/hunl.py`, any abstraction code, any Rust crate, any test under
`tests/` except the new `tests/test_ui_smoke.py`. PR 10 is strictly additive
on the engine side.

## 6. Async solve handling

The single hardest design point in PR 10. NiceGUI runs **everything on one
asyncio event loop**; per `nicegui/llms.md` mental model 7: *"Blocking the
loop (with `time.sleep()`, `requests.get()`, heavy CPU work) freezes the
entire application for all users."* Our DCFR is a pure-Python tight loop that
runs for **minutes to hours** on a real HUNL spot. We must not block the loop.

### 6.1 Worker thread design (`ui/state.py::SolveRunner`)

A `SolveRunner` singleton lives in `ui/state.py`. It owns one worker thread
(spawned via `threading.Thread`) and the cancellation flags. Lifecycle:

```python
class SolveRunner:
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._pause_event = threading.Event()    # set => paused
        self._stop_event = threading.Event()     # set => stop ASAP
        self._lock = threading.Lock()             # guards result snapshots
        self.result: SolveResult | None = None
        self.iteration: int = 0
        self.expl_history: list[tuple[int, float]] = []  # (iter, expl)
        self.status: str = 'idle'                 # idle | running | paused | done | stopped | error
        self.error: BaseException | None = None
        self._on_progress: Callable[[int, float], None] | None = None

    def start(self, game, iterations, *, log_every, dcfr_kwargs, on_progress):
        ...                                       # spin thread

    def pause(self): self._pause_event.set()
    def resume(self): self._pause_event.clear()
    def stop(self): self._stop_event.set()
```

The worker thread runs a small custom DCFR loop that mirrors
`solver.py::solve()` but checks `_stop_event` every iteration and waits on
`_pause_event` when paused. Pseudocode:

```python
def _worker(self, game, iterations, *, log_every, dcfr_kwargs, on_progress):
    try:
        solver = DCFRSolver(game, **dcfr_kwargs)
        for t in range(1, iterations + 1):
            if self._stop_event.is_set():
                break
            while self._pause_event.is_set():
                if self._stop_event.is_set(): break
                time.sleep(0.05)        # cheap; not blocking event loop (this is the worker thread)
            solver.solve(1)              # one iteration
            self.iteration = t
            if t % log_every == 0:
                expl = exploitability(game, solver.average_strategy())
                with self._lock:
                    self.expl_history.append((t, expl))
                if on_progress is not None:
                    on_progress(t, expl)   # called from worker thread; UI side must marshal
        with self._lock:
            self.result = SolveResult(...)
            self.status = 'done' if not self._stop_event.is_set() else 'stopped'
    except BaseException as e:
        with self._lock:
            self.error = e
            self.status = 'error'
```

### 6.2 UI-side progress updates

NiceGUI **must not be called from the worker thread directly** — its element
mutations expect the asyncio loop's context. Two safe patterns are documented
in `nicegui/llms.md`:

- **`ui.timer(0.5, update_ui)`** — a UI-thread timer that polls the
  `SolveRunner`'s state every 500 ms and pushes results into the chart and
  progress readouts. Simple; the loop never sees worker code. ~500 ms latency
  on chart updates, which is fine.
- **`background_tasks.create(coro)`** combined with `asyncio.run_coroutine_
  threadsafe(coro, loop)` — the worker calls a callback that schedules a
  coroutine on the UI loop. More precise (no polling lag), more failure
  modes (loop reference, exception propagation).

**Decision: use `ui.timer(0.5, update_ui)` for PR 10.** Simpler, well-
documented in NiceGUI's LLM reference, sufficient latency for human
perception (people can't see updates faster than ~10 Hz, and 2 Hz is fine for
exploitability curves). If polling latency proves visibly laggy in PR 10
testing, PR 11 can swap in the `run_coroutine_threadsafe` path — but PR 11
should be packaging, not refactoring.

The timer reads `SolveRunner.status`, `SolveRunner.iteration`, and the new
entries of `SolveRunner.expl_history` since the last tick; updates the chart
and status readouts; sets button enabled-states accordingly.

### 6.3 Cancellation correctness

**Critical item #3 (per spec): stop button reliably halts within 1
iteration.** The worker checks `self._stop_event.is_set()` once per
iteration boundary. Maximum delay = one DCFR iteration's wall-clock. For
small spots (river-only subgame) this is ≪1 ms; for big HUNL postflop
iterations it can be seconds. *Within 1 iteration* is the contract; in
practice on the river smoke test we expect ≪50 ms.

The smoke test (§4 `tests/test_ui_smoke.py`) covers this:

```python
async def test_stop_button_halts(user: User):
    await user.open('/')
    # Configure a spot whose solve loops for ~10s.
    await user.click('preset-default-100bb-postflop')
    await user.set_value('iterations', 100_000)
    await user.click('solve')
    await asyncio.sleep(0.5)             # let it start
    await user.click('stop')
    await asyncio.sleep(0.5)             # let it react
    # Assertion: solver is no longer running.
    assert SolveRunner.singleton().status in ('stopped', 'done')
    # Assertion: iteration count is far below target.
    assert SolveRunner.singleton().iteration < 50_000
```

### 6.4 Why threading.Thread vs `asyncio.to_thread`

NiceGUI's llms.md recommends `await asyncio.to_thread(cpu_func)` for CPU
work, which is more idiomatic. However:

1. We need **interruptibility**, not just background execution. `to_thread`
   gives us back the result but doesn't expose a cancellation hook the
   *callee* checks. We need the loop body to check `_stop_event`.
2. We need **resumability** (pause). Same reason.
3. We need **streaming progress**. `to_thread` is fire-and-forget; we'd need
   to pair it with a side-channel queue anyway, which is half the
   complexity of explicit threading.

So PR 10 uses explicit `threading.Thread` with `Event` flags. This is
documented and tested; future PRs can refactor to `asyncio.to_thread` with a
context-managed cancel token if a clean abstraction emerges.

### 6.5 GIL implications

The DCFR loop is pure-Python with NumPy operations. Most cycles are inside
NumPy (which releases the GIL during array ops), so the UI thread runs in
parallel during ~70% of solve time. UI responsiveness is therefore
acceptable. The remaining 30% (pure-Python list comprehensions, dict
lookups in `_get_infoset`) holds the GIL; UI updates are delayed by up to
~1 ms per iteration. Not noticeable.

**Rust backend (post-PR 6) entirely releases the GIL** during its inner
loop (PyO3 + `Py::allow_threads`), so UI responsiveness is excellent.

## 7. Range matrix design — implementation detail

### 7.1 Combo enumeration

The 169 hand classes are enumerated by `ui/state.py::enumerate_hand_classes()`:

```python
def enumerate_hand_classes() -> list[tuple[int, int, str]]:
    """Yield (row, col, hand_class_label) for the 13x13 grid.

    Row = max rank index (12 = A, 0 = 2). Col = min rank index.
    Diagonal (row == col) = pairs.
    Above diagonal (row < col when reading 'A in top-left, 2 in bottom-right'
      means col > row in our coordinate system) = suited.
    Below diagonal = offsuit.

    The grid is rendered top-left = AA, bottom-right = 22, with A=12 mapping
    to the top-left coordinate. Suited hands sit above-right of the diagonal.
    """
    ...
```

For each hand class, the set of concrete `(Card, Card)` combos is
`enumerate_combos(hand_class)`:

- Pair `XX`: 6 combos (C(4,2)).
- Suited `XYs`: 4 combos (one per suit, both cards same suit).
- Offsuit `XYo`: 12 combos (4 × 3 = pairs of different suits).

Total: 13×6 + 78×4 + 78×12 = 78 + 312 + 936 = **1326 distinct combos**.
Matches the deck combinatorics.

### 7.2 Per-cell aggregation

Given the current `SolveResult.average_strategy: dict[infoset_key →
[probs]]` and a current tree node (= a `(state, player_to_act, history)`
triple), we compute per-cell color as follows:

```python
def cell_strategy_summary(hand_class, range_, board, strategy, tree_node):
    combos = enumerate_combos(hand_class)
    survivors = [c for c in combos
                 if (c[0] not in board and c[1] not in board)
                 and c in range_.combos]
    if not survivors:
        return CellSummary(blocked=True)
    freq_sum = {'fold': 0.0, 'call': 0.0, 'raise': 0.0}
    total_weight = 0.0
    for combo in survivors:
        weight = range_.frequency_of(combo)              # from RangeWithFreqs
        infoset_key = make_infoset_key(combo, board, tree_node.history, ...)
        probs = strategy.get(infoset_key)
        if probs is None:
            continue                                      # unvisited infoset; skip
        actions = tree_node.legal_actions
        fold_p = sum(p for p, a in zip(probs, actions) if a == ACTION_FOLD)
        call_p = sum(p for p, a in zip(probs, actions) if a in (ACTION_CHECK, ACTION_CALL))
        raise_p = sum(p for p, a in zip(probs, actions) if a in _RAISES | _OPENING_BETS | {ACTION_ALL_IN})
        freq_sum['fold'] += weight * fold_p
        freq_sum['call'] += weight * call_p
        freq_sum['raise'] += weight * raise_p
        total_weight += weight
    if total_weight == 0:
        return CellSummary(empty=True)
    return CellSummary(
        fold=freq_sum['fold'] / total_weight,
        call=freq_sum['call'] / total_weight,
        raise_=freq_sum['raise'] / total_weight,
        combo_count=len(survivors),
    )
```

(`_RAISES`, `_OPENING_BETS`, `ACTION_ALL_IN`, etc. are imports from
`poker_solver.hunl`.)

### 7.3 Color blend

```python
def cell_color(summary: CellSummary) -> str:
    if summary.blocked or summary.empty: return '#3a3a3a'
    r = summary.fold * 220 + summary.call * 220 + summary.raise_ * 40
    g = summary.fold * 40  + summary.call * 200 + summary.raise_ * 180
    b = summary.fold * 40  + summary.call * 40  + summary.raise_ * 60
    return f'rgb({int(r)},{int(g)},{int(b)})'
```

Applied via `cell.style(f'background-color: {color}')`.

### 7.4 Refresh discipline

The matrix is wrapped in a `@ui.refreshable` decorator. The runner's timer
(§6.2) calls `range_matrix.refresh()` after each progress tick *only if* the
solve produced a new strategy snapshot. If the user clicks a different tree
node, `range_matrix.refresh()` is also called (with the new node selection).

**Why `@ui.refreshable` over per-cell updates:** the matrix has 169 cells.
Per-cell updates via `.style()` and `.set_text()` is 169 × 3 mutations per
refresh = 507 outbox entries per tick. NiceGUI's outbox batches within a
single callback (mental model 9), so this is one WebSocket message — fine.
But `@ui.refreshable` is simpler and lets us add/remove cells dynamically
(e.g., when the board changes, blocker-removal might collapse a hand class
to 0 combos). The cost is the slot-stack rebuild, which is fast for 169
cells.

## 8. Decision tree browser — implementation detail

### 8.1 Tree adapter (`ui/state.py::SolveTree`)

Given a `SolveResult` and an `HUNLPoker` game, produce a NiceGUI-compatible
tree of nodes. Pseudocode:

```python
@dataclass
class TreeNode:
    id: str                          # unique; matches NiceGUI node_key
    label: str                       # e.g. "[SB: bet 75%]"
    history: tuple[Action, ...]      # the action sequence leading here
    state: HUNLState                 # the HUNL state at this node
    player_to_act: int               # 0, 1, or -1 (chance)
    reach_prob: float                # combined reach over both players' strategies
    range_weighted_ev: float         # in mBB
    legal_actions: list[Action]      # actions available from this state
    action_freqs: list[float]        # per-action frequency (range-weighted average)
    action_evs: list[float]          # per-action EV (in mBB)
    children_loader: Callable        # lazy: produces list[TreeNode] when expanded

def build_tree(game, result, min_reach=0.0):
    root = TreeNode(
        id='root',
        label='[start]',
        history=(),
        state=game.initial_state(),
        ...
    )
    return root
```

Children are computed lazily — only when the user expands a node. The
adapter caches expansions: once a node's children are computed they're held
in memory until the spot or solve result changes.

### 8.2 NiceGUI tree wiring

NiceGUI's `ui.tree` takes a nested-dict structure. We hand it the root node
and let it manage expansion:

```python
tree_widget = ui.tree(
    [tree_node_to_dict(root)],
    label_key='label',
    node_key='id',
    on_expand=on_tree_expand,
    on_select=on_tree_node_selected,
)
```

When the user expands a node, `on_tree_expand` calls
`SolveTree.expand(node_id)`, which fetches the children (lazy), then
patches the tree widget via:

```python
def on_tree_expand(e):
    children = solve_tree.expand(e.node_id)
    tree_widget.props(f':nodes="{json.dumps(...)}"')   # update the node array
    tree_widget.update()
```

Or — simpler — we wrap the tree in `@ui.refreshable` and call `refresh()`,
accepting the cost of a full rebuild. Given trees can have hundreds of
nodes in PR 10 use cases, `@ui.refreshable` is acceptable.

### 8.3 Per-node action display

Each tree node label includes the action stats inline. Example label text:

```
[SB: bet 75%]   bet75% 65% EV +120 · call 30% EV -10 · fold 5% EV 0
```

The label is rendered as HTML (via NiceGUI's tree label slot support) so we
can color-code action frequencies (red/yellow/green).

### 8.4 Filter

A `ui.slider(min=0, max=1, step=0.01, value=0)` above the tree controls
`SolveTree.min_reach`. When the slider changes, the tree rebuilds — but
only the visible nodes change; children of hidden parents don't need
recomputation.

### 8.5 Performance

For HUNL postflop spots the tree can have 10⁴–10⁶ infosets. Lazy expansion
keeps the *visible* tree small (user-driven traversal). The reach filter
plus the per-node 100-child cap (§3.4) keeps any single visible level
sane. The full tree is never materialized.

**Browser DOM ceiling:** Quasar can comfortably render ~2000 tree nodes;
beyond that, scroll perf degrades. We hard-cap visible nodes at 2000 by
trimming the deepest branches first. A small "more nodes hidden" badge in
the header reports the truncation count.

## 9. State persistence

### 9.1 In-process state

Module-level singletons in `ui/state.py`:

- `current_spot: Spot` — board, ranges, stack depths, etc.
- `current_solve: SolveSession | None` — config used + worker reference + result.
- `current_tree: SolveTree | None` — tree adapter rooted at the latest solve.
- `prefs: UIPrefs` — dark mode toggle, panel widths, default presets.

All four are singletons because PR 10 is single-user (see §1 non-goals). If
two browser tabs open the same NiceGUI server, both see the same state — last
write wins. Documented limitation; not exercised in tests.

NiceGUI's recommendation (per `llms.md` mental model 2) is to use
`app.storage.user` for per-user state. We deliberately don't: we have *one*
user, by design. `app.storage.user` would be functionally identical but adds
ceremony.

### 9.2 On-disk persistence

A JSON file at `~/.poker_solver_ui/state.json`. Load on startup; save on
significant state changes (spot change, solve complete, prefs change).

Schema (v1):

```json
{
  "version": 1,
  "ui_prefs": {
    "dark_mode": "auto",
    "panel_widths": {"left": 320, "bottom": 240},
    "matrix_show_frequencies": true,
    "tree_reach_filter": 0.0
  },
  "recent_spots": [
    {
      "id": "<auto-generated uuid>",
      "name": "Default 100BB postflop",
      "board": "Kh 7h 2d",
      "ranges": ["AA,KK-TT,AKs+,AQo+,76s+", "..."],
      "stacks_bb": [100, 100],
      "starting_street": "flop",
      "saved_at": "2026-05-20T..."
    }
  ],
  "library_entries": [],
  "session": {
    "last_spot_id": "<uuid>",
    "last_solve_iter": 5000
  }
}
```

`recent_spots` is capped at 10 entries (FIFO eviction). `library_entries` is
empty in PR 10 (PR 11 populates it).

**Atomic write pattern:** write to `state.json.tmp`, `fsync`, then `rename` to
`state.json`. Avoids corruption on crash mid-write.

**Save trigger:** debounced — coalesce writes within a 500 ms window via a
`ui.timer(0.5, _maybe_flush, once=False, active=False)` that activates on the
first dirty event. Avoids hammering the disk on every keystroke.

**Load failure handling:** if the JSON file is corrupt or version-mismatched,
log a warning, back it up to `state.json.bak`, and start from defaults. Don't
crash.

### 9.3 What is NOT persisted

- The actual `SolveResult.average_strategy` payload (potentially MBs in size).
  PR 11 persists these to the library as separate files.
- The `SolveTree` (regenerated from the strategy on load).
- The live exploitability chart history (regenerated from the strategy or
  shown only for the active solve session).
- Any in-flight worker thread state (PR 10 always starts cold; no resume).

## 10. Three-agent fan-out

Same pattern as PR 3, 3.5, 4, 5, 7: tight per-agent specs against the
interfaces in §3–9. Launch concurrently. Integrate at the end.

### Agent A — spot input + run panel + state management

**Owns:** `ui/__init__.py`, `ui/app.py`, `ui/state.py`,
`ui/views/spot_input.py`, `ui/views/run_panel.py`.

**Does NOT touch:** the range matrix, the tree browser, the library viewer,
the smoke tests, the engine, the CLI.

**Reads (does not modify):** `poker_solver/__init__.py`, `poker_solver/solver.py`,
`poker_solver/hunl.py`, `poker_solver/range.py`, `poker_solver/action_abstraction.py`,
`docs/pr3_prep/pr3_spec.md` (for `HUNLConfig` / `HUNLState` field semantics),
`docs/pr5_prep/pr5_spec.md` (for solver-side conventions),
`nicegui/llms.md` (for NiceGUI patterns).

**Deliverables:**

- `ui/__init__.py` — exports `__version__ = "0.1.0"`. Trivial.
- `ui/app.py` — `launch(port: int = 8080, host: str = '127.0.0.1', dark_mode:
  str = 'auto')` function and a `@ui.page('/')` builder. The page builder
  composes the four-pane layout (header + splitter) and instantiates the
  five view modules' main render functions. Calls `ui.run()` at end.
- `ui/state.py` — see §9.1. Includes:
  - Dataclasses: `Spot`, `RangeWithFreqs` (extends `poker_solver.Range` with
    per-combo float frequencies in [0.0, 1.0]), `SolveSession`, `UIPrefs`.
  - The `SolveRunner` class (see §6.1).
  - `enumerate_hand_classes()`, `enumerate_combos(class)`,
    `hand_class_label(rank1, rank2, suited)` utilities.
  - The on-disk state JSON load/save logic (§9.2).
  - Module-level singletons + a `get_state()` accessor.
- `ui/views/spot_input.py` — see §3.1. Render function `render(state)`.
- `ui/views/run_panel.py` — see §3.2. Render function `render(state, on_solve,
  on_pause, on_stop)`. The chart updates are driven by a `ui.timer(0.5, ...)`
  that polls `state.runner` (the `SolveRunner` instance).

**Acceptance:** when the agent's code is dropped in and Agent B + C are
stubbed, `poker-solver ui` launches a browser page with: working board
picker, range matrix input (the per-combo input matrix, NOT the strategy
display matrix — that's Agent B), solve/pause/stop buttons, live
exploitability chart that updates while a solve runs.

### Agent B — range matrix display + decision tree browser

**Owns:** `ui/views/range_matrix.py`, `ui/views/tree_browser.py`.

**Does NOT touch:** any other ui/ file, the engine, the tests, the CLI.

**Reads (does not modify):** Agent A's `ui/state.py` *interface contract*
(the dataclasses, the `SolveRunner.result` shape, the tree adapter
interface). Reads `poker_solver/hunl.py` for `HUNLState`,
`HUNLConfig.to_action_config()`, infoset-key construction, and the
`Street`/`Action` constants. Reads `nicegui/llms.md` for `ui.tree`,
`ui.grid`, `ui.refreshable` patterns.

**Deliverables:**

- `ui/views/range_matrix.py`:
  - `render(state)` — the 13×13 grid + combo inspector strip.
  - `cell_strategy_summary(...)` per §7.2.
  - `cell_color(...)` per §7.3.
  - `inspect_panel(state, hand_class)` — the strip below the grid.
- `ui/views/tree_browser.py`:
  - `render(state)` — the collapsible tree + reach-filter slider.
  - `SolveTree` class — the tree adapter (§8.1).
  - `tree_node_to_dict()` — converts to NiceGUI's tree schema.
  - `on_tree_node_selected(e)` — handler that updates
    `state.current_tree_node` and triggers `range_matrix.refresh()`.

**Acceptance:** when Agent B's code is dropped in alongside Agent A's, the
range matrix renders the current solve's strategy at the root node;
clicking a tree node updates the matrix; the inspector strip shows
per-combo action distributions. Color blend matches Pio convention. The
matrix correctly filters blocker combos.

### Agent C — library viewer stub + smoke tests + CLI integration

**Owns:** `ui/views/library_browser.py`, `tests/test_ui_smoke.py`,
the `poker-solver ui` subcommand in `poker_solver/cli.py`, the
`pyproject.toml` UI extra, the `README.md` UI section.

**Does NOT touch:** any ui/views except library_browser, the engine.

**Reads (does not modify):** Agent A's `ui/state.py` *interface*, Agent
B's `ui/views/range_matrix.py` and `tree_browser.py` *interfaces*
(only the public render functions). Reads `nicegui/llms.md` testing
section, `poker_solver/cli.py` for the subparser pattern, `pyproject.toml`
for the existing format.

**Deliverables:**

- `ui/views/library_browser.py` — see §3.5. The stub dialog + the three
  faked rows + the "PR 11" toast handlers.
- `tests/test_ui_smoke.py` — eight tests (target):
  1. `test_page_renders_without_exception` — opens `/`, asserts no
     exception, asserts the header, left pane, center pane, bottom pane
     all exist (via `ElementFilter(marker=...)` on Agent-A-tagged marks).
  2. `test_board_picker_accepts_three_cards` — clicks three cards in the
     board grid, asserts they appear in `state.current_spot.board`, asserts
     the starting_street is `FLOP`.
  3. `test_range_input_via_string` — types `"AA, KK-TT"` into the P0 range
     string field, asserts the matrix reflects 5 hand classes selected.
  4. `test_solve_button_starts_worker` — clicks solve, asserts
     `state.runner.status == 'running'` within 200 ms, asserts the worker
     thread is alive.
  5. `test_stop_button_halts_within_one_iteration` — see §6.3 pseudocode.
  6. `test_range_matrix_renders_169_cells` — opens a fresh spot, asserts
     `ElementFilter(marker='matrix-cell')` yields 169 elements.
  7. `test_combo_to_cell_mapping_no_off_by_one` — for every hand class,
     check that `enumerate_combos(class)` yields the right combo count
     (6 / 4 / 12) and that the cell at the expected `(row, col)` has the
     expected `hand-class` label. **This is the critical correctness test
     for §11 item 2.** Runs without any actual solve.
  8. `test_library_dialog_opens` — clicks the library button in the header,
     asserts the dialog opens, asserts the disabled "Load" button is
     disabled, asserts clicking a stub row produces a toast.
- `poker_solver/cli.py` (modify) — add the `ui` subcommand per §5.
- `pyproject.toml` (modify) — add the `ui` optional dependency and the
  pytest marker.
- `README.md` (modify) — add the UI section.

**Acceptance:** `pytest tests/test_ui_smoke.py` passes with NiceGUI
installed, and skips cleanly with `nicegui` uninstalled (every test is
marked `@pytest.mark.ui` and the conftest contains a `pytest.skip` if
`nicegui` import fails). `poker-solver ui` launches the app. `poker-
solver` (no args, or any non-UI subcommand) works without NiceGUI
installed.

### Integration phase (post-agents)

After all three agents finish, a single integration pass:

1. Import paths line up (Agent A's interface contract honored by B and C).
2. End-to-end manual smoke: launch the app, solve the river-only subgame
   (PR 3 `default_tiny_subgame`), verify the matrix displays AKc, QdQh, and
   the strategies match a hand-computed sanity check (Kc-high → fold, QQ
   → check/call → consistent with the 1000-chip pot river).
3. The smoke tests pass (`pytest tests/test_ui_smoke.py -v`).
4. `scripts/check_pr.sh` passes (ruff + mypy + pytest + license audit).

## 11. Critical correctness items

The user-flagged items, mapped to the spec:

1. **UI never blocks on solver (always async).** §6 covers this end-to-end.
   The worker thread runs in `threading.Thread`; the UI loop is never
   directly called from worker code; progress flows via a 500 ms timer
   poll. NumPy operations inside DCFR release the GIL, so the UI remains
   responsive even during pure-Python iterations.
   - **Test:** `test_solve_button_starts_worker` (smoke 4) + a manual demo
     that the user can interact with the spot input while a solve runs.

2. **Strategy visualization correctly maps combo → frequency (no off-by-
   one in matrix index).** §7.1 spells the row/col convention; §7.2 spells
   the aggregation. The hand-class label canonical ordering is
   committed in the spec (the 13×13 ASCII grid above). `test_combo_to_
   cell_mapping_no_off_by_one` (smoke 7) is the gate. Additionally, a
   property test in `test_ui_smoke.py`:
   ```python
   @given(hand_class=hand_class_strategy())
   def test_enumerate_combos_inverse(hand_class):
       combos = enumerate_combos(hand_class)
       for combo in combos:
           assert classify_combo(*combo) == hand_class
   ```
   (Optional: hypothesis dependency. If not available, hand-roll the
   parametric test over all 169 classes.)

3. **Stop button reliably halts within 1 iteration.** §6.3 covers the
   contract (one `_stop_event.is_set()` check per iteration boundary).
   `test_stop_button_halts_within_one_iteration` (smoke 5) is the gate.

Additional implicit correctness items not user-flagged but worth ensuring:

4. **Range-input frequencies sum correctly into the matrix aggregator.**
   The aggregator in §7.2 weights each combo by its `frequency_of(combo)`
   from the range. If a combo is in the range at 0.5 frequency, it
   contributes half-weight to its cell's aggregate. Smoke test 3 plus a
   unit test in `test_ui_smoke.py` for `RangeWithFreqs.frequency_of` round-
   tripping.

5. **Blocker filtering doesn't crash.** If every combo in a hand class is
   blocked (e.g., the cell representing AhAh-only when the board contains
   both red aces — impossible because AhAh is one combo and Ah only
   appears once on a board, but the logic must not crash). Hand-rolled
   adversarial test in smoke 7.

6. **Tree expansion is lazy.** A property assertion: expanding the root
   node yields ≤ N children for some sane N (≤30 — preflop has at most
   the number of legal opening actions). Smoke test:
   `test_tree_root_expansion_bounded`.

## 12. Risks

1. **NiceGUI's reactivity model doesn't gracefully handle long-running
   solves.** The 500 ms timer-poll pattern (§6.2) is robust but introduces
   visible latency on the exploitability chart for very fast spots
   (≤10 ms/iter). Mitigation: PR 10 ships the timer pattern; PR 11 can
   tune the polling interval per spot complexity. The smoke test
   covers correctness, not latency tuning.

2. **169-cell color blend is perceptually misleading at extreme mixings.**
   A cell at 33%/33%/33% fold/call/raise renders as muddy beige — visually
   indistinguishable from a 33%/40%/27% mix. Mitigation: numeric
   frequencies shown on hover (always), and a "show frequencies" toggle
   that overlays "(F65 C20 R15)"-style text on every cell. The latter
   adds visual noise but is sometimes necessary. Smoke test: visual
   inspection by a poker player (the user, in PR-review).

3. **Browser performance with full decision tree visualization.** Thousands
   of nodes degrade Quasar's tree component. Mitigation: §8.5 caps visible
   nodes at 2000; reach-prob slider in §3.4 trims aggressively. Smoke
   test: `test_tree_visible_nodes_under_cap`.

4. **NiceGUI 2.x → 3.x migration risk.** When NiceGUI 3.0 lands (no
   announced timeline as of May 2026), the `nicegui<3.0` pin in
   `pyproject.toml` prevents auto-breakage. Mitigation: pinned; PR 11+
   addresses the upgrade.

5. **NiceGUI's `app.storage` requires `storage_secret`.** If we use
   `app.storage.user` (we don't, per §9.1) we'd need a secret. We avoid
   the question by using module-level singletons. Documented.

6. **The `RangeWithFreqs` extension to `poker_solver.Range`.** PR 10 needs
   per-combo float frequencies, but `poker_solver.Range` (PR 1) is
   membership-only. We do **not** modify `poker_solver/range.py` — instead,
   `ui/state.py::RangeWithFreqs` *wraps* a `Range` and adds a
   `dict[Combo, float]` frequency layer. This is the right separation
   (UI feature, not engine feature) but introduces a wrapper that the
   matrix aggregator must use everywhere. Mitigation: every reference in
   PR 10 code to "a range" uses `RangeWithFreqs`; the smoke tests cover
   the wrapper.

7. **Combo → infoset-key mapping depends on `HUNLPoker.infoset_key()`.**
   This was set in PR 3 (`poker_solver/hunl.py:312-321`). If PR 9 (preflop)
   or any other PR between PR 3 and PR 10 changes the key format, our
   matrix queries fall off. Mitigation: the spec assumes the infoset
   key format is stable from PR 3 onward; if not, PR 10's `ui/state.py`
   absorbs the diff in a single adapter function.

8. **Card-picker keyboard accessibility.** Clicking 52 cards is fast but
   tedious. A power-user wants `ks` + space-bar to place K♠. NiceGUI
   supports `ui.keyboard(on_key=handler)` for global shortcuts. PR 10
   ships click-only; PR 11 adds keyboard shortcuts.

9. **Multiple instances of `poker-solver ui` collide on port 8080.** If
   the user already has a NiceGUI app on 8080, `ui.run()` raises. Mitigation:
   catch `OSError` and retry on 8081 ↔ 8090, printing the chosen port.
   Documented in §13 open decision 2.

10. **Dark mode default.** "auto" (system-following) is the obvious
    default but NiceGUI's dark mode is a class switch; some users prefer
    explicit. §13 open decision 1.

## 13. Open decisions for user

1. **Theme: light, dark, or system?** Recommend `dark_mode='auto'`
   (NiceGUI's `dark=None` follows system preference). Override via
   `--dark-mode {light,dark,auto}` CLI flag. A small toggle in the header
   also flips between dark/light at runtime. Persisted in
   `~/.poker_solver_ui/state.json::ui_prefs.dark_mode`.

2. **Default port for the NiceGUI server?** Recommend 8080 (NiceGUI
   default). If occupied, auto-retry 8081 ↔ 8090 and print the chosen port.
   Configurable via `--port`. Bound to `127.0.0.1` only (no `0.0.0.0` in
   PR 10).

3. **Save/load format for spot configurations?** Recommend **JSON** for
   PR 10's `recent_spots` and the PR 11 library. Rationale:
   (a) PR 7's spot fixtures (`tests/data/river_spots.json`) already use
   JSON, so format consistency across the codebase.
   (b) Python's stdlib `json` module is sufficient (no extra dependency).
   (c) YAML adds prettier multiline but a `PyYAML` dependency we don't
   need elsewhere.
   (d) A custom binary format saves ~10× disk but is opaque to debugging.
   We accept JSON's verbosity for human-readability.

4. **Include "explain why" hover text (e.g. "K-high folds because no SDR
   equity")?** Defer. Recommend **no** for v1. Generating these
   explanations requires either (a) a hand-coded heuristic rules engine
   (brittle, hard to maintain) or (b) an LLM call (introduces external
   dependency and latency). The numeric strategy + EV + reach already
   communicates "what" the solver is doing; "why" is interpretation,
   which is the user's job. Could be a future v2 feature behind a
   "Explain" button per cell; PR 10 ships without it.

5. **Postflop-only or include preflop?** PR 9 ships HUNL preflop. By the
   time PR 10 lands, the solver handles both. The UI should accept any
   spot the solver accepts — i.e., **both preflop and postflop**, gated by
   the engine's own validators. The board picker treats 0 cards as
   preflop (no special case). The only UI gating is "warn at <15 BB
   stacks" to suggest push/fold charts (PR 3.5).

6. **Should the run panel allow choosing the backend (python/rust)?**
   Recommend yes — a small `ui.toggle(['Python', 'Rust'])` next to the
   "Solve" button, defaulting to Python. The Rust backend (post-PR 6) is
   faster but lags the Python backend on features (e.g. HUNL preflop
   might be Python-only in PR 9). The toggle gives the user a knob; the
   engine raises `NotImplementedError` and the UI displays a notification
   if Rust isn't supported for that spot.

7. **Should the matrix support drag-painting?** Click-and-drag to paint a
   region of the matrix in one stroke. NiceGUI supports `on_mouseover` +
   `on_mousedown` events. Defer to v2. PR 10 ships click-only.

8. **Should the live exploitability chart be in log scale by default?**
   Exploitability decays roughly geometrically with iterations; log scale
   reads better. Recommend log scale by default, with a linear-scale
   toggle. NiceGUI's `ui.line_plot` doesn't expose log-scale natively in
   2.x; we can use `ui.echart` instead, which supports `yAxis.type:
   'log'`. Switch to `ui.echart` is +30 lines of code; worth it.

9. **Should the matrix display the player-to-act's strategy, or the
   opponent's strategy at the current node?** Recommend **player-to-act**.
   This is the universal solver convention. PR 10 hard-codes it; a future
   v2 could add an opponent-view toggle for nodelocking analysis.

10. **Should the spot input panel be on the left or top?** Recommend
    **left** for a typical 1280×720 window: most of the user's attention
    is the matrix (center), and a left-aligned input panel doesn't require
    scrolling. For ultra-wide monitors a horizontal layout (input on top,
    matrix + tree side-by-side below) reads better. PR 10 ships left-side
    only; responsive layout is a polish item.

11. **Versioning of `ui/__init__.py::__version__`?** Recommend
    `"0.1.0"` for PR 10. Bumped to `0.2.0` when PR 11 lands (library +
    packaging). Independent of `poker_solver.__version__` (currently
    `"0.2.0"`) because UI and engine release cadences will diverge.

## 14. Reference appendix

- `nicegui/llms.md` — NiceGUI's bundled LLM reference, fetched 2026-05-20.
  Mental models 1, 2, 3, 7, 8, 9 are most load-bearing for PR 10.
- `references/blog/gtow_how_solvers_work.md` — the "color convention" /
  "range matrix is the centerpiece" intuition.
- `references/blog/piosolver_technical_details.md` — desktop solver UI
  layout precedent.
- `PLAN.md` §1 ("UI tech: NiceGUI") + §3 (architecture summary showing
  `ui/` as a separate package).
- `poker_solver/__init__.py` — the public API the UI consumes (`solve`,
  `exploitability`, `HUNLPoker`, `HUNLConfig`, `Range`, `parse_range`,
  the action constants).
- `poker_solver/solver.py` — the `solve()` entrypoint; signature contract.
- `poker_solver/hunl.py` — `HUNLState`, `HUNLConfig`, infoset-key format.
- `poker_solver/range.py` — `Range.parse_range`, `Combo` type alias.
- `docs/pr3_prep/pr3_spec.md` — HUNL tree-builder fixture; `default_tiny_subgame`
  serves as the smoke-test spot for PR 10's UI.
- `docs/pr5_prep/pr5_spec.md` — postflop solve conventions; the UI runs the
  same `solve_hunl_postflop` path.
