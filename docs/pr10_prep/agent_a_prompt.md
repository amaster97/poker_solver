# PR 10a Agent A — spot input + run panel + state management (against mock solver)

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 10a Agent A.** PR 10 was split into PR 10a (this PR — UI scaffold against a MOCK solver in `ui/mock_solver.py`) and PR 10b (mechanical swap to real solver, ~1-2 days). The UI you build is the **exact same artifact** PR 10b will ship; only the contents of `ui/mock_solver.py` change between PRs.
**Your scope:** the foundational layer of the NiceGUI UI — module-level state management, the `SolveRunner` background-thread worker (calling `mock_solve` from `ui/mock_solver.py`, NOT `DCFRSolver` directly), the spot input view (board picker + range matrix input + stacks/position/blinds), the run panel view (bet-size menu + iterations + solve/pause/stop buttons + live exploitability chart), the **two-pane layout** (matrix center + collapsible right sidebar with three `ui.expansion` panels: spot input / run panel / tree browser) per Q1 locked decision, the **yellow "Mock mode" banner** (Q7 locked, dismissible) in the header, and the top-level `ui/app.py` page builder + launcher. Also owns the 3-step `ui/views/onboarding.py` modal triggered on first launch (no `state.json`).
**Your contract:** produce `ui/__init__.py`, `ui/app.py`, `ui/state.py`, `ui/views/spot_input.py`, `ui/views/run_panel.py`; export the dataclasses, `SolveRunner`, and module-level singleton accessors that Agent B's range matrix + tree browser consume and that Agent C's smoke tests assert against.
**Your success criteria:** ruff clean, black clean, `mypy --strict` clean on new code; `poker-solver ui` launches a working browser page with board picker, range matrix INPUT (not the strategy display — that's Agent B), solve/pause/stop, and live exploitability chart; the stop button reliably halts within 1 iteration; the UI loop is NEVER blocked by the solver (worker runs in a separate `threading.Thread`); ALL existing tests still pass (your work is purely additive).
**File ownership:** you own and may write ONLY `ui/__init__.py`, `ui/app.py`, `ui/state.py`, `ui/views/spot_input.py`, `ui/views/run_panel.py` (plus the empty `ui/views/__init__.py` package init). You may NOT modify any other file.

---

## Strict file ownership

**You own (create new):**
- `/Users/ashen/Desktop/poker_solver/ui/__init__.py` (new file)
- `/Users/ashen/Desktop/poker_solver/ui/app.py` (new file)
- `/Users/ashen/Desktop/poker_solver/ui/state.py` (new file)
- `/Users/ashen/Desktop/poker_solver/ui/views/__init__.py` (new file, empty package init)
- `/Users/ashen/Desktop/poker_solver/ui/views/spot_input.py` (new file)
- `/Users/ashen/Desktop/poker_solver/ui/views/run_panel.py` (new file)
- `/Users/ashen/Desktop/poker_solver/ui/views/onboarding.py` (new file; per
  `pr10a_spec.md` §13 table + §11 acceptance #12. 3-step modal shown on
  first launch when `state.json` is absent OR `prefs.onboarding_completed
  is False`. Each step is one-action; final step teaches the R/Y/G color
  legend. See `ui_mockups_and_debates.md` §4 for the 3-step content.)

**You must NOT touch:**
- `ui/views/range_matrix.py` — Agent B owns this.
- `ui/views/tree_browser.py` — Agent B owns this.
- `ui/views/library_browser.py` — Agent C owns this (PR 10a stub).
- `ui/mock_solver.py` — **Agent C owns this** (per `pr10a_spec.md` §9
  Agent C, which assigns the mock module to C). You import from it
  but do not write its body. The mock's public surface is locked in
  `pr10a_spec.md` §7.1.
- `ui/mock_solver_fixtures.py` (if Agent C splits fixtures out) — Agent C.
- `tests/test_ui_smoke.py` — Agent C owns this.
- `poker_solver/cli.py` — Agent C owns the `ui` subcommand wiring.
- `pyproject.toml` — Agent C owns the `[ui]` optional-dep group.
- `README.md` — Agent C owns the UI section.
- Any existing `poker_solver/*.py` file — read-only references.
- Any existing test file — read-only references.

If you discover an awkward signature mid-implementation, **do not silently change it**. Stop and write a short note to the orchestrator describing the conflict; the orchestrator will reconcile across agents.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10a_spec.md`. Internalize §0.1 (the SEVEN LOCKED Q1-Q7 design decisions — these are immutable; do NOT re-debate them), §2 (UX design principles), §3 (layout amendment: two-pane resolves anti-pattern), §4.1 (main app shell mockup), §4.2 (spot input panel mockup), §4.3 (run panel mockup with Q3+Q4 locked defaults), §6 (5 edge cases: long solves, cancellation, unsupported config, push/fold at ≤15 BB, OOM at 14 GB), §7 (mock solver public surface + 12 fixture spots + cancellation contract via `_CANCEL_FLAG`), §9 Agent A deliverables, §11 acceptance criteria (especially #2 two-pane, #11 yellow banner, #12 onboarding modal, #13 anti-patterns absent).
1b. **The original long-form spec (background only):** `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10_spec.md`. PR 10a inherits its structural design intent (§6 async, §9 state persistence, §11 correctness). Where pr10a_spec and pr10_spec disagree, **pr10a_spec wins** (especially layout — pr10_spec proposed 4-pane, pr10a_spec resolves to 2-pane).
1c. **The PR 10b spec (forward-context):** `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10b_spec.md`. Your import line for the solver MUST be a single named symbol so PR 10b can swap it in one line: `from ui.mock_solver import mock_solve as _solve_postflop_impl` (per pr10a_spec §9 Agent A bullet 4).
2. **The PLAN (locked decisions):** `/Users/ashen/Desktop/poker_solver/PLAN.md`. UI tech section confirms NiceGUI; architecture summary shows `ui/` as a sibling of `poker_solver/`.
3. **NiceGUI patterns:** `/Users/ashen/Desktop/poker_solver/nicegui/llms.md` if present locally; mental models 1, 2, 7, 8, 9 are most load-bearing for you. (Mental model 7: don't block the asyncio loop. Mental model 9: outbox batches within one callback.)
4. **Engine surfaces you consume (read-only):**
   - `/Users/ashen/Desktop/poker_solver/poker_solver/__init__.py` — exports: `solve`, `exploitability`, `HUNLPoker`, `HUNLConfig`, `Range`, `parse_range`, action constants.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/solver.py` — `solve()` entrypoint signature; `SolveResult` shape.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` — `Street` IntEnum (PREFLOP=0, FLOP=1, TURN=2, RIVER=3, SHOWDOWN=4), `HUNLConfig`, `HUNLState`, infoset-key format, action constants.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/range.py` — `Range`, `parse_range`, `Combo` type alias. You will WRAP `Range` with per-combo frequencies (do NOT modify `range.py`).
   - `/Users/ashen/Desktop/poker_solver/poker_solver/card.py` — `Card`, `card_to_int`, `int_to_card`, `full_deck`, `RANKS`, `SUITS`.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/action_abstraction.py` — bet-size action constants.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/dcfr.py` — `DCFRSolver` (your worker thread uses this directly for iter-by-iter control; do NOT call `poker_solver.solve()` from the worker because that's a one-shot run).
5. **PR 3 / PR 5 conventions (for `HUNLConfig` field semantics):**
   - `/Users/ashen/Desktop/poker_solver/docs/pr3_prep/pr3_spec.md`
   - `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/pr5_spec.md`

## Default decisions LOCKED (do not deviate)

These are the locked defaults from `pr10a_spec.md`; if any text elsewhere differs, **these locked defaults win**. The seven Q1-Q7 locks (`pr10a_spec.md` §0.1) are immutable; the orchestrator already accepted them based on three landed UX research docs.

### Seven Q-locks (pr10a_spec.md §0.1) — surface in your implementation

- **Q1 LOCKED: Two-pane layout** — matrix center + ONE collapsible right sidebar stacking three `ui.expansion` panels (spot input / run panel / tree browser, top-to-bottom; spot input open by default, others collapsed). The original `pr10_spec.md` §3 four-pane layout is REPLACED. Your `ui/app.py::build_page()` implements 2-pane.
- **Q2 LOCKED: Hand-class labels visible in matrix cells** ("AKs", "QQ", "72o" in upper-left). Numeric frequencies revealed on hover only. (Agent B implements the display matrix; your range-INPUT matrix in `spot_input.py` follows the same labels-in-cell rule.)
- **Q3 LOCKED: Default iterations = 1000** (NOT the original 2000). Target-exploitability mode is the opt-in alternative toggle. Coin-flip flag: if Q3 produces under-converged matrices on common spots during PR 10a manual testing, bump to 2000 in PR 10b.
- **Q4 LOCKED: Bet sizes default = 4 of 6 checked** (33% / 75% / 100% / all-in checked; 150% / 200% unchecked). Custom-size text field still present.
- **Q5 LOCKED: Combo inspector position = below the matrix** (full-width horizontal strip). (Agent B owns this; you do NOT render the inspector but your `spot_input.py` layout must NOT compete for that horizontal real estate.)
- **Q6 LOCKED: Tree reach filter default = 0.01** (NOT 0.0; slider visible above tree). (Agent B owns the tree; you reference this default in any persisted prefs that carry the slider value across sessions.)
- **Q7 LOCKED: Yellow "Mock mode" banner** across the top of the header, dismissible after first solve. Downgrades to a subtle `(mock)` chip in PR 10b. Your header (in `ui/app.py`) renders this banner. ElementFilter marker: `'mock-mode-banner'`; dismissal button marker: `'mock-mode-banner-dismiss'`.

### Other locked defaults

- **NiceGUI 2.x** (`nicegui>=2.0,<3.0`). Use only the 2.x API surface.
- **Mock solver contract:** import `mock_solve` from `ui/mock_solver.py` as a single named symbol — `from ui.mock_solver import mock_solve as _solve_postflop_impl` — so PR 10b's mechanical swap is one line. **DO NOT use `DCFRSolver` directly; DO NOT call `poker_solver.solve(...)`.** The worker invokes `_solve_postflop_impl(config, iterations, on_progress=callback, ...)`. The mock owns the iter-by-iter loop and the cancellation check.
- **Cancellation contract via module-level `_CANCEL_FLAG`** (per `pr10a_spec.md` §7.5): a `threading.Event` set by `SolveRunner.stop()` and checked by `mock_solve()` once per snapshot. Same flag survives the PR 10b swap.
- **Async solve via worker thread + `ui.timer(0.5, ...)` polling.** Worker is a `threading.Thread`. The UI loop never calls worker code directly; progress flows via a 500 ms timer that reads `SolveRunner` state and updates the chart + readouts. Do NOT use `asyncio.to_thread`.
- **Stop button cancellation flag checked per snapshot/iteration boundary.** Contract: stop halts within 1 (mocked) iteration. Smoke test asserts this (Agent C); your worker design must satisfy it.
- **Color blend for the matrix (RED=fold / YELLOW=call / GREEN=raise, Pio convention).** This is Agent B's render, but YOUR spot input's range-input matrix uses a DIFFERENT palette (white→saturated blue gradient on frequency) per spec §3.1 to avoid user confusion.
- **Numeric frequencies on hover.** Hovering a matrix cell shows tooltip text. This is Agent B's job for the strategy matrix; the spot-input range matrix tooltip shows the current frequency value.
- **Browser-based local app on port 8080** (default). Bound to `127.0.0.1` (no `0.0.0.0` in PR 10). Configurable via your `launch(port, host, dark_mode)` signature.
- **State at `~/.poker_solver_ui/state.json`** (per spec §9.2). Atomic write (write to `state.json.tmp`, `fsync`, `rename` to `state.json`). Debounced save (500 ms window).
- **No new third-party dependencies on top of NiceGUI.** Imports: `nicegui`, `numpy`, `poker_solver.*`, stdlib only. Agent C adds the `[ui]` optional-dep group to `pyproject.toml`.
- **`ui/__init__.py::__version__ = "0.1.0"`** per spec §13 decision 11.
- **No keyboard shortcuts in PR 10** (spec §12 risk 8 defers to PR 11).
- **Backend toggle: `ui.toggle(['Python', 'Rust'])` next to the Solve button**, defaulting to Python (per spec §13 decision 6).
- **Live exploitability chart: log scale by default** (per spec §13 decision 8). Use `ui.echart` with `yAxis.type: 'log'` (NiceGUI's `ui.line_plot` doesn't expose log scale in 2.x natively).

## Public API contract (exports Agents B + C depend on)

Export the following from `ui/state.py`. Signature drift breaks B's render functions and C's smoke tests. Type hints required (mypy --strict).

### From `ui/state.py`

```python
from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from poker_solver.card import Card
from poker_solver.hunl import HUNLConfig, HUNLPoker, HUNLState, Street
from poker_solver.range import Range
from poker_solver.solver import SolveResult


# ---- Dataclasses ----

@dataclass
class RangeWithFreqs:
    """A poker_solver.Range with an added per-combo frequency layer.

    PR 10 needs per-combo float frequencies in [0.0, 1.0]; poker_solver.Range
    (PR 1) is membership-only. We do NOT modify range.py — instead we WRAP a
    Range here and add a dict[Combo, float] frequency layer.

    All references in PR 10 to 'a range' use RangeWithFreqs.
    """
    base_range: Range
    frequencies: dict[tuple[Card, Card], float] = field(default_factory=dict)

    def frequency_of(self, combo: tuple[Card, Card]) -> float:
        """Return the frequency of a combo, defaulting to 1.0 if in base_range
        and absent from `frequencies`, else 0.0."""
        ...

    @classmethod
    def from_string(cls, range_str: str) -> "RangeWithFreqs":
        """Parse a range string via poker_solver.parse_range; all combos at 1.0."""
        ...

    def to_string(self) -> str:
        """Render back to range-string syntax. Drops frequencies (lossy for <1.0)."""
        ...


@dataclass
class Spot:
    """The poker spot being solved. Defines an HUNLConfig + two ranges +
    starting street + board state."""
    board: list[Card] = field(default_factory=list)
    ranges: tuple[RangeWithFreqs, RangeWithFreqs] = field(
        default_factory=lambda: (RangeWithFreqs(Range.full()), RangeWithFreqs(Range.full()))
    )
    stacks_bb: tuple[int, int] = (100, 100)
    sb_acts_first: bool = True                   # P0 = SB = button per HUNL convention
    sb_blind: float = 0.5                        # in BB
    bb_blind: float = 1.0
    ante: float = 0.0
    bet_sizes: tuple[float, ...] = (0.33, 0.75, 1.0, 1.5, 2.0)
    include_all_in: bool = True
    preflop_raise_cap: int = 4
    postflop_raise_cap: int = 3

    @property
    def starting_street(self) -> Street:
        """Derive from len(board): 0=PREFLOP, 3=FLOP, 4=TURN, 5=RIVER.
        Raises ValueError on 1, 2 cards (invalid intermediate states)."""
        ...

    def to_hunl_config(self) -> HUNLConfig:
        """Build a HUNLConfig from this spot's fields. abstraction=None always
        in PR 10 (we visualize equilibrium strategies on the lossless engine).
        """
        ...


@dataclass
class SolveSession:
    """A configuration + worker reference + result snapshot."""
    spot: Spot
    iterations: int
    log_every: int
    backend: str                                  # "python" or "rust"
    started_at: float                             # time.time()
    runner: "SolveRunner"


@dataclass
class UIPrefs:
    """Persisted user preferences."""
    dark_mode: str = "auto"                       # "auto" | "light" | "dark"
    panel_widths: dict[str, int] = field(default_factory=lambda: {"left": 320, "bottom": 240})
    matrix_show_frequencies: bool = True
    tree_reach_filter: float = 0.01    # Q6 LOCKED per pr10a_spec.md §0.1


# ---- SolveRunner: the worker-thread orchestrator ----

class SolveRunner:
    """Owns one background worker thread + the cancellation flags + the
    progress snapshot that the UI timer reads.

    Lifecycle (per spec §6.1):
        idle → running → (paused → running)* → done | stopped | error

    Thread safety: every read from the UI thread goes through the lock OR
    reads a single atomic field (int, str, float). The expl_history list is
    append-only from the worker; the UI thread reads its current length and
    slices [last_seen_len:]. Don't mutate it from the UI thread.
    """

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._pause_event: threading.Event = threading.Event()
        self._stop_event: threading.Event = threading.Event()
        self._lock: threading.Lock = threading.Lock()
        self.result: SolveResult | None = None
        self.iteration: int = 0
        self.expl_history: list[tuple[int, float]] = []  # (iter, expl_mBB_per_pot)
        self.status: str = "idle"   # idle | running | paused | done | stopped | error
        self.error: BaseException | None = None
        self.started_at: float = 0.0

    def start(
        self,
        game: HUNLPoker,
        iterations: int,
        *,
        log_every: int,
        dcfr_kwargs: dict[str, object] | None = None,
        backend: str = "python",
    ) -> None:
        """Spawn the worker thread. Raises RuntimeError if a previous solve is
        still running (call stop() + wait() first)."""
        ...

    def pause(self) -> None:
        """Set the pause flag. Worker waits between iterations until resume()."""
        ...

    def resume(self) -> None:
        """Clear the pause flag."""
        ...

    def stop(self) -> None:
        """Set the stop flag. Worker exits its loop within 1 iteration."""
        ...

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()


# ---- Module-level singletons + accessor ----

@dataclass
class AppState:
    """Aggregator passed to view render() functions."""
    current_spot: Spot
    current_solve: SolveSession | None
    current_tree_node_id: str          # "root" by default; Agent B's tree updates this
    selected_player_for_input: int     # 0 or 1; which tab is active in spot_input
    runner: SolveRunner
    prefs: UIPrefs
    state_path: Path                   # ~/.poker_solver_ui/state.json


def get_state() -> AppState:
    """Return the module-level singleton AppState, lazily initialized on
    first call (loads from disk if state.json exists)."""
    ...


def save_state() -> None:
    """Debounced atomic save to ~/.poker_solver_ui/state.json. Idempotent."""
    ...


# ---- Hand-class enumeration helpers (consumed by Agent B's matrix) ----

def enumerate_hand_classes() -> list[tuple[int, int, str]]:
    """Yield (row, col, hand_class_label) for the 13x13 grid.

    row = max rank index (12 = A, 0 = 2). col = min rank index.
    Diagonal (row == col) → pairs ('AA', 'KK', ..., '22').
    Above-diagonal (col > row, visually 'right of' the diagonal) → suited.
    Below-diagonal → offsuit.

    The grid is rendered top-left = AA, bottom-right = 22, with A=12 mapping
    to the top-left coordinate. Suited hands sit above-right of the diagonal.

    Returns 169 entries in canonical (top-row first, left-to-right) order.
    """
    ...


def enumerate_combos(hand_class: str) -> list[tuple[Card, Card]]:
    """Given a hand-class label ('AA', 'AKs', 'AKo', ...), return the list of
    concrete (Card, Card) combos.

    Pair 'XX': 6 combos (C(4,2)).
    Suited 'XYs': 4 combos (one per suit).
    Offsuit 'XYo': 12 combos (4 * 3 = pairs of different suits).
    """
    ...


def hand_class_label(rank1: int, rank2: int, suited: bool) -> str:
    """Return the canonical hand-class label for two ranks (0..12) + suited flag.
    For pairs (rank1 == rank2), suited is ignored and the label is e.g. 'AA'.
    """
    ...


def classify_combo(card1: Card, card2: Card) -> str:
    """Inverse of enumerate_combos: given two cards, return their hand-class label.
    Used by Agent C's `test_combo_to_cell_mapping_no_off_by_one` property test.
    """
    ...
```

### From `ui/app.py`

```python
from __future__ import annotations

from nicegui import ui


def build_page() -> None:
    """The @ui.page('/') builder. Composes the header + 4-pane layout via
    ui.splitter(); instantiates each of the five views; registers the
    ui.timer(0.5, ...) progress poller."""
    ...


def launch(
    port: int = 8080,
    host: str = "127.0.0.1",
    dark_mode: str = "auto",
) -> None:
    """Entry point called by `poker-solver ui`. Registers the @ui.page builder
    and calls ui.run(host=host, port=port, dark=..., reload=False, show=True).

    dark_mode: "auto" (None → system-follows), "light" (False), "dark" (True).

    On port-in-use (OSError): try 8081..8090; print the chosen port (per spec §12
    risk 9). Bind only to 127.0.0.1 (no 0.0.0.0).
    """
    ...
```

### From `ui/views/spot_input.py`

```python
from __future__ import annotations

from ui.state import AppState


def render(state: AppState) -> None:
    """Render the §3.1 spot input panel into the current NiceGUI slot.

    Contains:
    - Board card-picker (4x13 grid of card buttons; up to 5 cards).
    - Hole-card ranges via 13x13 matrix OR string input (toggle).
      ui.tabs switches between 'P0 (SB / BTN)' and 'P1 (BB)'.
    - Stack depth inputs.
    - Position selection (disabled toggle showing 'SB acts first').
    - Blinds + ante under ui.expansion('Blinds & ante').
    - Reset spot button.
    - Load from preset dropdown — **12 fixture spots** from
      `pr10a_spec.md` §7.4 (sourced via `ui.mock_solver.list_fixture_presets()`).
      The 12 keys: `river_tiny_subgame`, `flop_k72r_100bb`, `flop_t87s_100bb`,
      `flop_monotone_hhh`, `flop_paired_q9q`, `turn_kqj9_4_flush`,
      `turn_t872_brick`, `river_axxs_polar`, `preflop_btn_vs_bb`,
      `river_blocker_heavy`, `shortstack_25bb`, `deepstack_200bb`.
      (Each preset materialized via `ui.mock_solver.load_fixture(preset_id)`
      returning a `HUNLConfig`.)

    Mutates state.current_spot in-place; calls save_state() on every change
    (which debounces).

    NiceGUI ElementFilter markers (Agent C asserts on these):
      'spot-input-panel'           (the outer card)
      'board-picker-cell-{idx}'    (each of 52 card buttons in the board grid)
      'board-cleared-button'
      'range-matrix-cell-{cls}'    (the per-hand-class cell in the per-player
                                    range INPUT matrix; cls is 'AA', 'AKs',
                                    etc. - NOTE: this is the input matrix,
                                    distinct from Agent B's 'matrix-cell')
      'range-string-input-p{0|1}'  (the string textarea for each player)
      'stack-input-p{0|1}'
      'reset-spot-button'
      'preset-{preset_id}'         (one marker per of the 12 fixture spots;
                                    e.g. 'preset-river-tiny-subgame',
                                    'preset-flop-k72r-100bb',
                                    'preset-shortstack-25bb', etc. —
                                    underscores in IDs become hyphens in
                                    markers per NiceGUI convention)
    """
    ...
```

### From `ui/views/run_panel.py`

```python
from __future__ import annotations

from collections.abc import Callable

from ui.state import AppState


def render(
    state: AppState,
    on_solve: Callable[[], None],
    on_pause: Callable[[], None],
    on_stop: Callable[[], None],
) -> None:
    """Render the §3.2 run panel into the current NiceGUI slot.

    Contains:
    - Bet-size checkboxes (6: 33%, 75%, 100%, 150%, 200%, all-in) + custom-size
      text field. **Q4 LOCKED defaults: 33% / 75% / 100% / all-in checked;
      150% / 200% UNCHECKED.**
    - Raise cap inputs (preflop default 4; postflop default 3).
    - Iterations input. **Q3 LOCKED default: 1000** (NOT 2000). With opt-in
      target-exploitability toggle (when active, iterations field becomes
      max-iterations and a "target expl mBB/pot" field appears).
    - Backend toggle (Python / Rust; default Python per locked default).
    - Solve / Pause / Stop buttons (enable-states reflect state.runner.status).
    - Live exploitability chart (ui.echart, log Y-axis).
    - Progress readouts (iteration N/M, wall-clock, current expl, backend, status).

    Drives chart updates via a ui.timer(0.5, _tick) registered in app.py; this
    function just declares the chart placeholder + readouts. The timer (in
    app.py) calls run_panel.refresh_progress(state) every 500 ms.

    NiceGUI ElementFilter markers (Agent C asserts on these):
      'run-panel'                       (the outer card)
      'bet-size-checkbox-{pct}'         (one per bet size)
      'custom-bet-size-input'
      'iterations-input'
      'backend-toggle'
      'solve-button'                    (Agent C's smoke 4 + 5 click this)
      'pause-button'
      'stop-button'                     (Agent C's smoke 5 clicks this)
      'expl-chart'
      'progress-iteration'
      'progress-status'                 (text "idle | running | ... | error")
    """
    ...


def refresh_progress(state: AppState) -> None:
    """Called by the ui.timer(0.5, ...) tick. Reads state.runner.iteration,
    state.runner.status, state.runner.expl_history; updates the chart and
    readouts; sets the solve/pause/stop button enabled-states."""
    ...
```

## Critical correctness items

### 1. UI never blocks on solver (always async)

This is correctness item #1 from PR 10 spec §11. The contract:

- `solve` button click → `SolveRunner.start(...)` → spawns `threading.Thread`. Returns immediately. The UI event handler is NOT awaited on the solve completion.
- The DCFR loop runs in the worker thread. The UI thread is free; the user can edit the spot input, click stop, etc.
- Progress flows via a `ui.timer(0.5, refresh_progress)` registered in `ui/app.py::build_page()`. The timer reads `state.runner` and updates the chart + readouts.
- The worker thread **never** calls NiceGUI API directly. The only communication is via the `SolveRunner`'s attributes (read by the timer).
- The worker calls `mock_solve()` (from `ui/mock_solver.py`, owned by Agent C) — NOT `DCFRSolver` directly. `mock_solve` owns the iter-by-iter loop, the `_CANCEL_FLAG` check, and fires `on_progress` callbacks per snapshot. Worker body:
  ```python
  # In SolveRunner._worker (per pr10a_spec.md §7.5):
  from ui.mock_solver import mock_solve, _CANCEL_FLAG

  def on_progress(iter_n: int, expl: float, partial_report: MemoryReport) -> None:
      if self._stop_event.is_set():
          _CANCEL_FLAG.set()  # propagate to mock_solve's per-snapshot check
      with self._lock:
          self.iteration = iter_n
          self.expl_history.append((iter_n, expl))
          self.partial_report = partial_report

  try:
      _CANCEL_FLAG.clear()
      result = _solve_postflop_impl(  # = mock_solve from import alias
          config, iterations,
          on_progress=on_progress,
          log_every=log_every,
          memory_budget_gb=14.0,
          # mock_latency_ms / mock_failure_mode passed via dcfr_kwargs or
          # via SolveRunner.start() optional kwargs for test injection
      )
      with self._lock:
          self.result = result
          self.status = "stopped" if self._stop_event.is_set() else "done"
  except MemoryError as e:
      # MemoryError.args[1] is MemoryReport per pr10a_spec.md §7.2
      with self._lock:
          self.error = e
          self.status = "error"
  except NotImplementedError as e:
      with self._lock:
          self.error = e
          self.status = "error"
  ```
- **Do NOT call `poker_solver.solve()` or `DCFRSolver` directly in PR 10a.** That comes in PR 10b. The single import you change in PR 10b is the `_solve_postflop_impl` alias.
- Pause: while paused, the worker thread sets `_CANCEL_FLAG.clear()` to NOT cancel, but the actual pause semantics are handled by your `SolveRunner._pause_event` outside of `mock_solve`. Since `mock_solve` is a single call, "pause" in PR 10a means: don't fire a NEW solve. If the user clicks pause mid-solve, `mock_solve` continues to its next snapshot; the UI shows "pausing..." until the next snapshot lands. Document this in code comments.

### 2. Stop button reliably halts within 1 iteration

This is correctness item #3 from PR 10 spec §11. The worker checks `self._stop_event.is_set()` exactly once per iteration boundary (top of the `for t in range(...)` loop). Max delay = one DCFR iteration's wall-clock. On the river-only smoke spot this is <50 ms.

Agent C's `test_stop_button_halts_within_one_iteration` (smoke 5) is the gate.

### 3. RangeWithFreqs wrapping

PR 10 needs per-combo float frequencies but `poker_solver.range.Range` is membership-only. You wrap `Range` here in `RangeWithFreqs`. Critical:

- `RangeWithFreqs.frequency_of(combo)`: if combo in `frequencies` dict, return that value; else if combo in `base_range.combos`, return 1.0; else return 0.0.
- `RangeWithFreqs.from_string("AA, KK-TT")` produces frequencies dict with every combo at 1.0.
- The matrix-input render in `spot_input.py` mutates `frequencies[combo]` when the user clicks/cycles a cell.
- Agent B's range matrix DISPLAY consumes `state.current_spot.ranges[player].frequency_of(combo)` when computing per-cell aggregates. Do not break this contract.

### 4. Hand-class ordering canonical to spec §3.3

The 13×13 grid renders top-left = AA, bottom-right = 22 with suited above-diagonal, offsuit below. Your `enumerate_hand_classes()` must return entries in row-major order matching the ASCII table in spec §3.3:

```
       A   K   Q   J   T   9   8   7   6   5   4   3   2
   A  AA  AKs AQs AJs ATs A9s A8s A7s A6s A5s A4s A3s A2s
   K  AKo KK  KQs KJs KTs K9s K8s K7s K6s K5s K4s K3s K2s
   ...
```

`enumerate_hand_classes()[0] == (0, 0, 'AA')`, `[1] == (0, 1, 'AKs')`, etc. (row=0 is the A-row at top; col=0 is the A-column at left). Document the row/col convention prominently in code comments — Agent B and Agent C depend on it.

### 5. State persistence: atomic write, debounced save

Per spec §9.2:

- Write to `state.json.tmp` → `fsync` → `os.rename` to `state.json`. Avoids corruption on crash mid-write.
- Debounce via `ui.timer(0.5, _maybe_flush, once=False, active=False)` that activates on the first dirty event.
- On load failure (corrupt JSON or version mismatch): log a warning, back up to `state.json.bak`, start from defaults. DO NOT crash.
- `recent_spots` capped at 10 entries (FIFO eviction). `library_entries` empty in PR 10.

### 6. SolveRunner is a SINGLE-instance singleton

Module-level state. Two browser tabs share it (per spec §1 non-goal "no multi-tab state sync"). Don't try to support multi-tab in PR 10.

### 7. Backend toggle (Python / Rust)

Per spec §13 decision 6: a `ui.toggle(['Python', 'Rust'])` next to the Solve button. Default Python. When set to Rust, your `SolveRunner.start(..., backend="rust")` should attempt the Rust path (via `poker_solver.solve(..., backend="rust")` — but again: you call `DCFRSolver` directly for iter-control, so for the Rust backend you need a Rust-backed iter-by-iter API).

If the Rust crate doesn't expose iter-by-iter solve (post-PR 6), fall back gracefully: on `NotImplementedError` or `ImportError`, surface a notification "Rust backend not supported for iter-by-iter solve in PR 10 — falling back to Python." This is OK; PR 11 polish can wire the Rust iter-by-iter API.

## License-aware sourcing

**You may port architecturally (not code-copy) from MIT/Apache sources:**
- `references/code/slumbot2019/` (**MIT**) — for solver UI conceptual reference (it's a CLI tool, not a GUI, so direct copy is N/A).
- `references/code/noambrown_poker_solver/` (**MIT**) — read-only inspiration.
- `nicegui/llms.md` — NiceGUI's bundled LLM reference (MIT-licensed via NiceGUI). Cite the mental model number if you copy a >5 LOC pattern.

**You may NOT copy from AGPL sources:**
- `references/code/postflop-solver/` — **AGPL v3**. Read-only inspiration. No code copy.
- `references/code/TexasSolver/` — **AGPL v3**. Same rule.

**You may NOT extrapolate from training data.** If you "remember" a NiceGUI pattern, ground it in `nicegui/llms.md` or the PR 10 spec.

If you copy a non-trivial NiceGUI snippet (>~5 LOC) from a documented mental model in `nicegui/llms.md`, add an attribution comment:
```python
# Pattern from nicegui/llms.md mental model 7 (do not block the asyncio loop).
```

## Quality bar

- **ruff clean:** `ruff check ui/__init__.py ui/app.py ui/state.py ui/views/spot_input.py ui/views/run_panel.py ui/views/__init__.py` reports zero issues.
- **black clean:** `black --check ui/__init__.py ui/app.py ui/state.py ui/views/spot_input.py ui/views/run_panel.py ui/views/__init__.py` reports no changes needed.
- **mypy strict-clean on new code:** `mypy --strict ui/` reports zero errors. (The repo's overall mypy strictness is not yet enabled, but new UI code must be.)
- **No new third-party deps beyond `nicegui`.** Imports: `nicegui`, `numpy`, `poker_solver.*`, stdlib. Agent C owns adding `nicegui` to `pyproject.toml`'s optional `[ui]` group.
- **All existing tests still pass.** Run `pytest -x` after your work lands and confirm. Your work is additive; you should not be touching anything that breaks existing tests, but a circular import or a name collision would. Guard against this.
- **Code size budget: ~800–1100 LOC** combined across the five files (state.py is largest, ~400 LOC; spot_input + run_panel ~200 each; app.py ~150). Stay within budget; do not over-engineer.

## Reference-first rule

Before any technical claim, citation, or formula, check the local references. Never extrapolate from training data when a local authoritative source exists. The reference index is `/Users/ashen/Desktop/poker_solver/references/README.md`.

If a NiceGUI feature is needed (e.g., "how does `ui.timer` work"), cite `nicegui/llms.md` and the specific mental model number.

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Lint + format
ruff check ui/
black --check ui/

# 2. Type-check
mypy --strict ui/

# 3. Smoke-import (catches circular import bugs)
python -c "
from ui.state import (
    AppState, Spot, RangeWithFreqs, SolveRunner, SolveSession, UIPrefs,
    get_state, save_state, enumerate_hand_classes, enumerate_combos,
    hand_class_label, classify_combo,
)
from ui.app import launch, build_page
from ui.views.spot_input import render as spot_render
from ui.views.run_panel import render as run_render, refresh_progress
print('ui imports OK')
"

# 4. Hand-class enumeration sanity (Agent C's smoke 7 will exercise this)
python -c "
from ui.state import enumerate_hand_classes, enumerate_combos, classify_combo
classes = enumerate_hand_classes()
assert len(classes) == 169, f'expected 169 hand classes, got {len(classes)}'
assert classes[0][2] == 'AA', f\"expected first = 'AA', got {classes[0][2]}\"
assert classes[-1][2] == '22', f\"expected last = '22', got {classes[-1][2]}\"
# Combo counts
assert len(enumerate_combos('AA')) == 6
assert len(enumerate_combos('AKs')) == 4
assert len(enumerate_combos('AKo')) == 12
# Total combo count = 13*6 + 78*4 + 78*12 = 1326
total = sum(len(enumerate_combos(c[2])) for c in classes)
assert total == 1326, f'expected 1326 combos, got {total}'
# Inverse check on a couple
from poker_solver.card import Card
combos = enumerate_combos('AKs')
for c0, c1 in combos:
    assert classify_combo(c0, c1) == 'AKs'
print('hand-class enum smoke OK')
"

# 5. SolveRunner lifecycle smoke (no real solve; just thread plumbing)
python -c "
from ui.state import SolveRunner
r = SolveRunner()
assert r.status == 'idle'
assert not r.is_alive()
r.stop()  # idempotent on idle
assert r.status == 'idle'
print('SolveRunner lifecycle smoke OK')
"

# 6. Full test suite (existing tests must still pass)
pytest -x 2>&1 | tail -20

# 7. (Optional, if you have NiceGUI installed) launch the app and verify it
# opens a browser. You can Ctrl-C immediately.
# poker-solver ui
```

If any of the above fails, fix the issue before reporting done. If a smoke test reveals a spec ambiguity, **stop and flag it** — do not silently work around it.

## Report back format

When done, write a concise report (≤300 words) covering:

1. Files created with line counts.
2. Any spec amendment you made or contract drift you flagged (and why).
3. Verification command output (paste tails).
4. Any open question you couldn't resolve from the spec / PLAN — flag for human review.
5. License attributions you added (if any).
