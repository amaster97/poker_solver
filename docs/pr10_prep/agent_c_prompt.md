# PR 10a Agent C — mock solver + library stub + 20 smoke tests + CLI integration

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 10a Agent C.** PR 10 was split into PR 10a (UI scaffold against a MOCK solver) and PR 10b (mechanical swap to real solver). **You own the mock solver itself**, in addition to the library stub + smoke tests + CLI.
**Your scope:** (1) **`ui/mock_solver.py`** — the mock solver module that returns realistic `HUNLSolveResult` instances for 12 fixture spots, with 6 failure modes (per `pr10a_spec.md` §7); (2) the library viewer stub (placeholder dialog with three faked rows + `[Load selected]` + `[Delete]` + PR 11 banner per `pr10a_spec.md` §4.6); (3) **20 smoke tests** (per `pr10a_spec.md` §10: 8 UI smoke + 5 mock-solver coverage + 4 UX-grounded + 3 edge-case = 20 total); (4) the `poker-solver ui` CLI subcommand; (5) `[ui]` optional-dependency group; (6) README "UI" section with "(mock)" tagline.
**Your contract:** produce `ui/mock_solver.py`, `ui/mock_solver_fixtures.py` (optional split), `ui/views/library_browser.py`, `tests/test_ui_smoke.py`; modify `poker_solver/cli.py` + `pyproject.toml` + `README.md`; consume the *interfaces* of Agent A's `ui.state` + Agent B's `ui.views.{range_matrix,tree_browser}` (NOT their implementations); the mock's public surface is byte-locked per `pr10a_spec.md` §7.1 to enable PR 10b's one-line import swap.
**Your success criteria:** ruff clean, black clean, `mypy --strict` clean on new code; `pytest tests/test_ui_smoke.py` passes 20 tests with `nicegui` installed AND skips cleanly with `nicegui` uninstalled; `poker-solver ui` launches the app; mock fixtures pass poker-player eye test (user-reviewed); ALL existing tests still pass.
**File ownership:** you own `ui/mock_solver.py`, `ui/mock_solver_fixtures.py`, `ui/views/library_browser.py`, `tests/test_ui_smoke.py`, and you may EDIT `poker_solver/cli.py`, `pyproject.toml`, `README.md` per the integration scope below — nothing else.

---

## Strict file ownership

**You own (create new):**
- `/Users/ashen/Desktop/poker_solver/ui/mock_solver.py` (new file; ~400 LOC.
  Per `pr10a_spec.md` §7. Public surface: `mock_solve()`,
  `list_fixture_presets()`, `load_fixture(preset_id)`, module-level
  `_CANCEL_FLAG: threading.Event`. **First 8 parameters of `mock_solve`
  are byte-identical to PR 5's `solve_hunl_postflop`** so PR 10b is a
  one-line import swap.)
- `/Users/ashen/Desktop/poker_solver/ui/mock_solver_fixtures.py` (optional
  split — the 12 fixture spots data table, per `pr10a_spec.md` §7.4.
  Split out only if `mock_solver.py` exceeds ~400 LOC; otherwise inline.)
- `/Users/ashen/Desktop/poker_solver/ui/views/library_browser.py` (new file)
- `/Users/ashen/Desktop/poker_solver/tests/test_ui_smoke.py` (new file;
  ~400 LOC for 20 tests per `pr10a_spec.md` §10.)

**You may modify (existing files, additive edits only):**
- `/Users/ashen/Desktop/poker_solver/poker_solver/cli.py` — add the `ui` subcommand per §5 of the spec. No other changes.
- `/Users/ashen/Desktop/poker_solver/pyproject.toml` — add the `[project.optional-dependencies]` `ui = ["nicegui>=2.0,<3.0"]` group + the `[tool.pytest.ini_options]` markers entry. No other changes.
- `/Users/ashen/Desktop/poker_solver/README.md` — add a "UI" section after the existing CLI usage section, before development notes. No other changes.

**You must NOT touch:**
- `ui/__init__.py`, `ui/app.py`, `ui/state.py`, `ui/views/__init__.py`, `ui/views/spot_input.py`, `ui/views/run_panel.py` — Agent A
- `ui/views/range_matrix.py`, `ui/views/tree_browser.py` — Agent B
- Any existing `poker_solver/*.py` file other than `cli.py` — out of scope
- Any existing test file (`tests/test_*.py`) — those test prior PRs and remain unchanged

**Critical:** you are writing the smoke tests from the **spec + interface contracts alone**. Do NOT read Agent A's or Agent B's implementations even after they land. The dividend of the fan-out pattern is that your tests independently encode the spec — if your tests fail against the impl, it's a real bug OR a real spec ambiguity, and the orchestrator resolves it. Reading the impl would defeat this dividend.

(Exception: if a test fails due to an obvious typo in YOUR test code, you may inspect the impl to figure out the typo. But you do not adjust tests to match impl behavior — only to fix your own bug.)

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10a_spec.md`. Internalize §0.1 (the SEVEN LOCKED Q1-Q7 design decisions — your smoke tests assert against them), §4.6 (library viewer stub mockup with the three faked rows + `[Load selected]` + `[Delete]` + PR 11 banner), §6 (5 edge cases your mock failure modes implement: long solves, cancellation, unsupported config, push/fold ≤15 BB, OOM at 14 GB), **§7 (mock solver public surface — load-bearing for `mock_solver.py`)**, §7.4 (the 12 fixture spots with hand-crafted acceptance criteria), §7.5 (cancellation contract via `_CANCEL_FLAG`), §9 Agent C deliverables, **§10 (20 smoke tests, NOT 8)**, §11 acceptance criteria, §13 files-to-create table.
1b. **The PR 10b spec (forward-context):** `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10b_spec.md`. Your mock's signature must match `solve_hunl_postflop` byte-identically in the first 8 params; PR 10b deletes your `mock_solver.py` and routes through the real solver in one line. Smoke tests #9-#13 of `pr10a_spec.md` §10.2 (mock-specific) are deleted in PR 10b.
1c. **The original long-form spec (background only):** `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10_spec.md`. §6.3 (stop button cancellation pseudocode), §11 critical correctness items. Where pr10a_spec disagrees, **pr10a_spec wins**.
2. **The PLAN (locked decisions):** `/Users/ashen/Desktop/poker_solver/PLAN.md`. UI tech section confirms NiceGUI; architecture summary shows `ui/` as a sibling of `poker_solver/`.
3. **NiceGUI testing patterns:** `/Users/ashen/Desktop/poker_solver/nicegui/llms.md` testing section. The `User` fixture is the entry point; it's async, in-process, no real browser. Mental model 1 (component model) helps you understand `ElementFilter(marker=...)`.
4. **Existing CLI structure (the file you'll modify):**
   - `/Users/ashen/Desktop/poker_solver/poker_solver/cli.py` — read `_GAMES` map, `_cmd_solve`, `build_parser`, `main`. You'll add `_cmd_ui` + register it. Pattern is exactly like the existing `_cmd_equity` and `_cmd_solve`.
5. **Existing test style:** `/Users/ashen/Desktop/poker_solver/tests/test_hunl_core.py` and `/Users/ashen/Desktop/poker_solver/tests/test_hunl_tree.py` — function-level tests, `pytest.approx` for floats, no test classes, parametrize only when meaningful. Mirror this style.
6. **Existing `pyproject.toml`:** read `/Users/ashen/Desktop/poker_solver/pyproject.toml` to understand the current structure before adding the `[project.optional-dependencies]` and `[tool.pytest.ini_options]` entries.
7. **Existing `README.md`:** read `/Users/ashen/Desktop/poker_solver/README.md` to find the right insertion point for the UI section.
8. **Agent A's exports (the interface contract; do NOT read their impl):**
   - The spec §10 Agent A deliverables enumerate the public surface.
   - Your tests use `from ui.state import ...` and `from ui.app import launch, build_page`.
9. **Agent B's exports (the interface contract; do NOT read their impl):**
   - Spec §10 Agent B deliverables.
   - Your tests use ElementFilter markers like `'matrix-cell'` which Agent B's `range_matrix.py` is contractually obligated to register.

## Default decisions LOCKED (do not deviate)

These are the locked defaults from the PR 10 spec; if the spec text differs, **these locked defaults win**:

- **NiceGUI 2.x** (`nicegui>=2.0,<3.0`). Use only the 2.x API surface in your tests. Use `User` fixture per `nicegui/llms.md` testing section.
- **Browser-based local app on port 8080** (default). Bound to `127.0.0.1`. Configurable via `--port` and `--host` CLI flags.
- **CLI lazy-imports `ui.app`** so the rest of the CLI works without NiceGUI installed. Catch `ImportError` (NOT `ModuleNotFoundError`, per `nicegui/llms.md` style guide) and print a clear install hint with exit code 2.
- **`pytest.mark.ui` marker.** Every test in `test_ui_smoke.py` is marked `@pytest.mark.ui` and the conftest contains a `pytest.importorskip('nicegui')` (or equivalent skip-if-nicegui-not-installed pattern) so the suite skips cleanly when NiceGUI is absent.
- **State at `~/.poker_solver_ui/state.json`** — your tests use a temp-dir override so they don't pollute the real home dir. (Implementation hint: monkeypatch `ui.state.get_state` to use a tmp path, or set an env var the state loader respects.)
- **No new third-party deps in tests.** Imports: `pytest`, `nicegui` (only inside the marker-gated tests), `numpy`, `poker_solver.*`, `ui.*`, stdlib.

## Public API you produce + modifications

### `ui/mock_solver.py` (the centerpiece of PR 10a)

Per `pr10a_spec.md` §7.1 — public surface byte-locked for the PR 10b swap:

```python
# ui/mock_solver.py
from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

from poker_solver.hunl import HUNLConfig
from poker_solver.hunl_solver import HUNLSolveResult
from poker_solver.profiler.memory import MemoryReport, StreetMemoryEntry


# Module-level cancellation flag. SolveRunner.stop() sets it; mock_solve()
# checks it once per snapshot. Same flag survives the PR 10b swap.
_CANCEL_FLAG: threading.Event = threading.Event()


@dataclass
class FixturePreset:
    """One row in the preset dropdown (per pr10a_spec.md §7.1)."""
    id: str                  # 'river_tiny_subgame', 'flop_k72r_100bb', ...
    label: str               # "River subgame (PR 3 fixture)"
    description: str         # one-line description for tooltip
    starting_street: str     # 'PREFLOP' | 'FLOP' | 'TURN' | 'RIVER'


def mock_solve(
    config: HUNLConfig,
    iterations: int = 50_000,
    *,
    log_every: int | None = None,
    memory_budget_gb: float = 14.0,
    target_exploitability: float | None = None,
    seed: int | None = None,
    dcfr_kwargs: dict | None = None,
    on_progress: Callable[[int, float, MemoryReport], None] | None = None,
    # ---- mock-specific knobs (kwarg-only) ----
    mock_latency_ms: int = 30_000,
    mock_failure_mode: str | None = None,
) -> HUNLSolveResult:
    """Drop-in mock for solve_hunl_postflop.

    First 8 parameters byte-identical to PR 5's solve_hunl_postflop
    (per pr10a_spec.md §7.1). Trailing mock_* args have defaults; not part
    of the real surface.

    Failure modes (mock_failure_mode):
      'oom'           — raises MemoryError("mock OOM", partial_report)
                        after ~10% latency
      'not_implemented' — raises NotImplementedError
      'cancelled'     — returns HUNLSolveResult with iterations < requested
      'long_latency'  — sleeps 10 min with progress callbacks
      'rapid_iteration' — latency 100 ms; tests chart-flooding guard
      None            — successful solve, latency = mock_latency_ms

    Cancellation contract (pr10a_spec.md §7.5):
      while solving, check `_CANCEL_FLAG.is_set()` once per snapshot;
      if set, break and return partial result.
    """


def list_fixture_presets() -> list[FixturePreset]:
    """Return the 12 fixture spots' metadata (pr10a_spec.md §7.4)."""


def load_fixture(preset_id: str) -> HUNLConfig:
    """Materialize a preset id into a real HUNLConfig the UI consumes."""
```

**The 12 fixture spots (pr10a_spec.md §7.4):** `river_tiny_subgame`,
`flop_k72r_100bb`, `flop_t87s_100bb`, `flop_monotone_hhh`,
`flop_paired_q9q`, `turn_kqj9_4_flush`, `turn_t872_brick`,
`river_axxs_polar`, `preflop_btn_vs_bb`, `river_blocker_heavy`,
`shortstack_25bb`, `deepstack_200bb`. Each ships a hand-crafted strategy
passing the poker-player eye test: realistic mixing, no dominated
actions, MDF-obeying bluff freq on rivers, polarization on rivers and
more linear on flops, blocker effects on rivers.

**MemoryReport fields the UI reads (pr10a_spec.md §7.3) — must be populated:**
`total_gb`, `per_street` (list[StreetMemoryEntry]), `river_ratio`,
`rss_calibration_error`, `wallclock_per_iter_sec`.

### `ui/views/library_browser.py` (stub per `pr10a_spec.md` §4.6)

```python
from __future__ import annotations

from nicegui import ui

from ui.state import AppState


def render(state: AppState) -> ui.dialog:
    """Render the §4.6 library viewer dialog. STUB for PR 10a.

    Per `pr10a_spec.md` §4.6 mockup:
    - Header: "SOLVE LIBRARY".
    - Filter text field (no-op in stub).
    - "(3 entries)" count display.
    - List of three faked rows with hand-typed names like:
        "AKo vs QQ on K72r       100bb · flop · 2026-05-19 · 2.1 mBB"
        "4bp 3-bet pot            100bb · flop · 2026-05-18 · 0.8 mBB"
        "River-only subgame       100bb · river · 2026-05-15 · 0.1 mBB"
    - `[Load selected]` button (disabled in stub).
    - `[Delete]` button (disabled in stub).
    - Banner text: "PR 11: persistence not yet wired".
    - Clicking a stub row produces a toast: "PR 11 — load from disk is
      not yet wired".

    Returns the ui.dialog handle so app.py can wire the header button's open()
    callback.

    NiceGUI ElementFilter markers (your smoke 8 asserts on these):
      'library-dialog'                  (the ui.dialog element itself)
      'library-filter-input'            (the Filter field)
      'library-load-button'             (the disabled '[Load selected]')
      'library-delete-button'           (the disabled '[Delete]')
      'library-stub-row-{idx}'          ('library-stub-row-0', '-1', '-2')
      'library-header-button'           (the header button that opens the dialog;
                                          owned by Agent A's ui/app.py)
    """
    ...


def render_header_button(state: AppState, dialog: ui.dialog) -> None:
    """Render the header button that opens the library dialog. Called by
    Agent A's ui/app.py from the header bar.

    NOTE: per spec §3.5, the library viewer is a modal opened from the header,
    NOT a persistent panel. The button lives in the header bar; the dialog
    body is what render() above produces.

    Implementation hint: app.py can simply do:
        dialog = library_browser.render(state)
        library_browser.render_header_button(state, dialog)
    """
    ...
```

### `tests/test_ui_smoke.py`

**Twenty tests** per `pr10a_spec.md` §10. Use `pytest.mark.ui` + a module-level `pytest.importorskip('nicegui')` so the file skips cleanly when NiceGUI is uninstalled. Test groups (per `pr10a_spec.md` §10):

- §10.1 — 8 UI smoke tests (tests 1-8 below; identical to the original PR 10 list).
- §10.2 — 5 mock-solver coverage tests (tests 9-13). **PR 10b deletes these.**
- §10.3 — 4 UX-grounded smoke additions (tests 14-17).
- §10.4 — 3 edge-case coverage tests (tests 18-20).

```python
"""Smoke tests for the PR 10 NiceGUI app.

Uses NiceGUI 2.x's User fixture (async, in-process, no real browser). Every
test is marked @pytest.mark.ui and the module skips cleanly if nicegui is not
installed. Per spec §11 critical correctness items.
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("nicegui")

from nicegui.testing import User           # type: ignore[import-untyped]


pytestmark = pytest.mark.ui


@pytest.fixture
def isolated_state_dir(tmp_path, monkeypatch):
    """Override the state.json location so tests don't touch the real home dir.

    Implementation: monkeypatch a known env var OR a known module-level constant.
    Document the override mechanism here so it's discoverable.
    """
    ...


async def test_page_renders_without_exception(user: User, isolated_state_dir):
    """Smoke test 1: page opens; **two-pane** layout renders (Q1 locked
    per pr10a_spec.md §0.1): matrix center + right sidebar with three
    `ui.expansion` panels (spot input / run panel / tree browser).
    Yellow Mock mode banner (Q7) visible.
    Per pr10a_spec.md §10.1 item 1 + §11 acceptance #2 + #11.
    """
    await user.open("/")
    # Two-pane layout per Q1 lock: matrix center + collapsible right sidebar.
    user.find(marker="spot-input-panel").elements   # Agent A's marker
    user.find(marker="run-panel").elements          # Agent A's marker
    user.find(marker="range-matrix-display").elements   # Agent B's marker
    user.find(marker="tree-browser").elements       # Agent B's marker
    # Q7 locked: yellow Mock mode banner present.
    user.find(marker="mock-mode-banner").elements


async def test_board_picker_accepts_three_cards(user: User, isolated_state_dir):
    """Smoke test 2: clicking three cards in the board picker updates state +
    starting_street becomes FLOP.
    Per spec §10 Agent C deliverables item 2.
    """
    ...


async def test_range_input_via_string(user: User, isolated_state_dir):
    """Smoke test 3: typing 'AA, KK-TT' into the P0 range string field reflects
    5 hand classes selected in the matrix input.
    Per spec §10 Agent C deliverables item 3.
    """
    ...


async def test_solve_button_starts_worker(user: User, isolated_state_dir):
    """Smoke test 4: clicking Solve transitions runner.status to 'running'
    within 200 ms; worker thread is alive.
    Per spec §10 Agent C deliverables item 4 + §11 critical item 1.
    """
    ...


async def test_stop_button_halts_within_one_iteration(user: User, isolated_state_dir):
    """Smoke test 5: stop button halts within 1 (mocked) iteration.
    Per pr10_spec.md §6.3 pseudocode + pr10a_spec.md §11 acceptance #5.
    Uses 'flop_k72r_100bb' preset (per pr10a_spec.md §7.4 12-fixture list)
    — long-running enough to click stop while still solving.
    """
    from ui.state import get_state
    await user.open("/")
    user.find(marker="preset-flop-k72r-100bb").click()
    user.find(marker="iterations-input").type("100000")     # large target
    user.find(marker="solve-button").click()
    await asyncio.sleep(0.5)                                # let it start
    user.find(marker="stop-button").click()
    await asyncio.sleep(0.5)                                # let it react
    state = get_state()
    # Assertion: solver is no longer running.
    assert state.runner.status in ("stopped", "done")
    # Assertion: iteration count is far below target.
    assert state.runner.iteration < 50_000


async def test_range_matrix_renders_169_cells(user: User, isolated_state_dir):
    """Smoke test 6: ElementFilter(marker='matrix-cell') yields 169 elements.
    Per spec §10 Agent C deliverables item 6.
    """
    await user.open("/")
    cells = user.find(marker="matrix-cell").elements
    assert len(cells) == 169, f"expected 169 matrix cells, got {len(cells)}"


def test_combo_to_cell_mapping_no_off_by_one():
    """Smoke test 7: for every hand class, enumerate_combos yields the right
    combo count (6 / 4 / 12) and classify_combo is the inverse.

    Per spec §10 Agent C deliverables item 7 + §11 critical item 2.
    This is the load-bearing property test for the matrix correctness.
    Runs without any actual solve.
    """
    from ui.state import enumerate_hand_classes, enumerate_combos, classify_combo

    classes = enumerate_hand_classes()
    assert len(classes) == 169

    total_combo_count = 0
    for row, col, hc in classes:
        combos = enumerate_combos(hc)
        if hc[-1] == "s":          # suited
            assert len(combos) == 4, f"{hc}: expected 4, got {len(combos)}"
        elif hc[-1] == "o":        # offsuit
            assert len(combos) == 12, f"{hc}: expected 12, got {len(combos)}"
        else:                       # pair
            assert len(combos) == 6, f"{hc}: expected 6, got {len(combos)}"
        total_combo_count += len(combos)

        # Inverse: classify_combo(*combo) == hc for every combo.
        for combo in combos:
            assert classify_combo(*combo) == hc, (
                f"classify_combo({combo!r}) returned wrong class: "
                f"expected {hc}, got {classify_combo(*combo)}"
            )

    assert total_combo_count == 1326, f"expected 1326 combos, got {total_combo_count}"


async def test_library_dialog_opens(user: User, isolated_state_dir):
    """Smoke test 8: clicking the library header button opens the dialog;
    '[Load selected]' button is disabled; clicking a stub row produces a toast.
    Per pr10a_spec.md §10.1 item 8 + §4.6 mockup.
    """
    await user.open("/")
    user.find(marker="library-header-button").click()
    # Dialog opens
    user.find(marker="library-dialog").elements
    # Load button is disabled
    load_btn = user.find(marker="library-load-button").elements[0]
    assert "disable" in (load_btn.props or {}) or "disabled" in (load_btn.props or {})
    # Stub row click produces toast
    user.find(marker="library-stub-row-0").click()
    notifs = user.find(kind="q-notification").elements
    assert len(notifs) >= 1


# ---- §10.2 Mock-solver coverage tests (5; PR 10b deletes these) ----

def test_mock_solve_returns_real_hunl_solve_result():
    """Smoke test 9: isinstance check on HUNLSolveResult + MemoryReport.
    Per pr10a_spec.md §10.2 item 9 + §7.3.
    """
    from poker_solver.hunl_solver import HUNLSolveResult
    from poker_solver.profiler.memory import MemoryReport
    from ui.mock_solver import mock_solve, load_fixture

    config = load_fixture("river_tiny_subgame")
    result = mock_solve(config, iterations=100, mock_latency_ms=0)
    assert isinstance(result, HUNLSolveResult)
    assert isinstance(result.memory_report, MemoryReport)


def test_mock_solve_streams_progress_callbacks():
    """Smoke test 10: progress fires iterations // log_every times;
    monotone iter; monotone-ish decreasing expl.
    Per pr10a_spec.md §10.2 item 10.
    """
    from ui.mock_solver import mock_solve, load_fixture

    events: list[tuple[int, float]] = []

    def cb(it: int, expl: float, _report) -> None:
        events.append((it, expl))

    config = load_fixture("river_tiny_subgame")
    mock_solve(
        config, iterations=1000, log_every=100,
        on_progress=cb, mock_latency_ms=0,
    )
    assert len(events) >= 9          # ~10 ticks at log_every=100 over 1000 iters
    # Monotone iteration counter
    assert all(events[i][0] < events[i + 1][0] for i in range(len(events) - 1))
    # Expl decreases at least somewhat overall
    assert events[-1][1] < events[0][1]


def test_mock_solve_failure_oom_raises_memory_error_with_partial_report():
    """Smoke test 11: mock_failure_mode='oom' raises MemoryError;
    `.args[1]` is a MemoryReport.
    Per pr10a_spec.md §10.2 item 11 + §6 edge #5.
    """
    from poker_solver.profiler.memory import MemoryReport
    from ui.mock_solver import mock_solve, load_fixture

    config = load_fixture("deepstack_200bb")
    try:
        mock_solve(
            config, iterations=10_000,
            mock_failure_mode="oom", mock_latency_ms=0,
        )
    except MemoryError as e:
        assert isinstance(e.args[1], MemoryReport)
    else:
        raise AssertionError("expected MemoryError")


def test_mock_solve_failure_cancelled_returns_partial_result():
    """Smoke test 12: mock_failure_mode='cancelled' returns
    HUNLSolveResult with iterations < requested and non-empty strategy.
    Per pr10a_spec.md §10.2 item 12 + §6 edge #2.
    """
    from ui.mock_solver import mock_solve, load_fixture

    config = load_fixture("river_tiny_subgame")
    result = mock_solve(
        config, iterations=10_000,
        mock_failure_mode="cancelled", mock_latency_ms=0,
    )
    assert result.iterations < 10_000
    assert len(result.average_strategy) > 0


def test_ui_never_imports_mock_specific_symbols(tmp_path):
    """Smoke test 13: static grep — `ui/` outside `ui/state.py` and
    `ui/mock_solver*.py` itself contains zero `mock_solver` references.
    Per pr10a_spec.md §10.2 item 13 + §11 acceptance #7.
    """
    import pathlib

    ui_root = pathlib.Path(__file__).resolve().parent.parent / "ui"
    offending: list[str] = []
    for py in ui_root.rglob("*.py"):
        if py.name == "state.py":
            continue
        if py.name.startswith("mock_solver"):
            continue
        text = py.read_text()
        if "mock_solver" in text or "mock_solve" in text:
            offending.append(str(py))
    assert not offending, f"mock_solver leaked into: {offending}"


# ---- §10.3 UX-grounded smoke additions (4) ----

async def test_range_matrix_color_blend_matches_pio_convention(
    user: User, isolated_state_dir,
):
    """Smoke test 14: given fixture with known per-cell action freqs,
    rendered RGB matches additive formula within ±2 per channel. Locks
    adopted pattern #1 (Pio R/Y/G convention).
    Per pr10a_spec.md §10.3 item 14.
    """
    ...


async def test_blocker_cells_show_slashed_overlay(
    user: User, isolated_state_dir,
):
    """Smoke test 15: 'flop_k72r_100bb' fixture; 'AhKh'-only class
    renders slashed-overlay style (blocked by K of hearts on board).
    Per pr10a_spec.md §10.3 item 15.
    """
    ...


async def test_input_matrix_palette_disjoint_from_display_palette(
    user: User, isolated_state_dir,
):
    """Smoke test 16: static assertion that range-input matrix sources
    blue-gradient palette and display matrix sources RYG. Locks principle 4
    (color minimalism, palettes disjoint).
    Per pr10a_spec.md §10.3 item 16.
    """
    ...


async def test_chart_default_log_scale(user: User, isolated_state_dir):
    """Smoke test 17: ui.echart Y axis defaults to log scale; linear
    toggle exists.
    Per pr10a_spec.md §10.3 item 17.
    """
    ...


# ---- §10.4 Edge-case coverage tests (3) ----

async def test_oom_failure_shows_remediation_notification(
    user: User, isolated_state_dir,
):
    """Smoke test 18: mock_failure_mode='oom' surfaces §6.5 notification
    with 'Reduce bet sizes' quick-action button.
    Per pr10a_spec.md §10.4 item 18 + §6 edge #5.
    """
    ...


async def test_pushfold_dispatch_at_15bb(user: User, isolated_state_dir):
    """Smoke test 19: setting stacks to 15 BB triggers a yellow warning
    toast with 'Switch to push/fold view' button.
    Per pr10a_spec.md §10.4 item 19 + §6 edge #4.
    """
    ...


async def test_long_solve_eta_appears_after_30s(
    user: User, isolated_state_dir,
):
    """Smoke test 20: with mock_latency_ms=60_000 and
    mock_failure_mode='long_latency', ETA text appears in status readout
    after 30 s.
    Per pr10a_spec.md §10.4 item 20 + §6 edge #1.
    """
    ...
```

### `poker_solver/cli.py` modifications

Add a `ui` subcommand. Pattern matches the existing `_cmd_equity` / `_cmd_solve` / `build_parser` structure. Per spec §5:

```python
def _cmd_ui(args: argparse.Namespace) -> int:
    """Launch the PR 10 NiceGUI app. Lazy-imports ui.app so the rest of the
    CLI works without NiceGUI installed."""
    try:
        from ui.app import launch
    except ImportError:
        print(
            "UI support not installed. Install with `pip install poker-solver[ui]`.",
            file=sys.stderr,
        )
        return 2
    launch(port=args.port, host=args.host, dark_mode=args.dark_mode)
    return 0
```

Register under `build_parser()`:

```python
ui_parser = sub.add_parser(
    "ui",
    help="Launch the NiceGUI browser UI (PR 10).",
)
ui_parser.add_argument("--port", type=int, default=8080)
ui_parser.add_argument("--host", type=str, default="127.0.0.1")
ui_parser.add_argument(
    "--dark-mode",
    choices=("auto", "light", "dark"),
    default="auto",
)
ui_parser.set_defaults(func=_cmd_ui)
```

Make sure `sys` is imported at the top of `cli.py` (it likely already is — verify).

### `pyproject.toml` modifications

Add the optional-dependency group + the pytest marker. Locate the existing `[project]` table and add:

```toml
[project.optional-dependencies]
ui = ["nicegui>=2.0,<3.0"]
```

If the existing pyproject already has a `[project.optional-dependencies]` section, append the `ui` line under it (preserve other groups).

Locate `[tool.pytest.ini_options]` (or create it if absent) and add the marker:

```toml
[tool.pytest.ini_options]
markers = [
    "ui: tests that require nicegui (skip if not installed)",
    # ... preserve any existing markers
]
```

If the section already exists with a `markers` list, append `"ui: ..."` without removing existing entries.

### `README.md` modifications

Insert a "## UI" section after the existing CLI usage section, before development notes:

```markdown
## UI (mock)

An optional browser-based UI is available:

    pip install -e .[ui]
    poker-solver ui

This launches a local NiceGUI server (default http://localhost:8080) with:
- A 13x13 range matrix viewer (Pio convention: red=fold, yellow=call, green=raise)
- Board input via card picker
- Solver run controls with live exploitability tracking
- A decision tree browser showing EV + frequency per action

**PR 10a note:** UI ships against a mock solver (fixture-backed) so the
full UX is exercisable before PR 9/10b land. A yellow "Mock mode" banner
across the top of the app indicates this; it downgrades to a subtle
`(mock)` chip after PR 10b swaps in the real solver in one line.

See `docs/pr10_prep/pr10a_spec.md` for the locked design decisions and
`docs/pr10_prep/pr10b_spec.md` for the swap mechanics.
```

## Critical correctness items in your work

### 1. Test the spec, not the implementation

Your tests assert against the spec invariants and the public API contracts (the ElementFilter markers Agents A + B promise to register). Do NOT read Agent A's or Agent B's implementations. If a test fails against the impl, it's a real bug OR a real spec ambiguity — flag it in your report.

### 2. CLI must remain importable without NiceGUI

Per spec §5: when NiceGUI is not installed, `poker-solver` (no args, `equity`, `solve`, any other subcommand) must work. Only `poker-solver ui` requires NiceGUI. The `_cmd_ui` function lazy-imports `ui.app`; ImportError → exit 2 with a clear message. Test this:

```bash
# Temporarily make nicegui un-importable (just for the smoke check)
pip uninstall -y nicegui
poker-solver equity 'AhKs' 'QcQd'   # should still work
poker-solver ui                      # should exit 2 with install hint
pip install -e .[ui]
poker-solver ui                      # should launch
```

### 3. The `[ui]` extra is pinned: `nicegui>=2.0,<3.0`

Per spec §5: lower bound 2.0 (needs modern `background_tasks` + `ElementFilter` APIs); upper bound 3.0 (when NiceGUI 3.x lands, we want explicit upgrade, not silent breakage). Do not loosen this pin.

### 4. The `pytest.mark.ui` marker + clean skip

When NiceGUI is uninstalled, `pytest tests/test_ui_smoke.py` should report all 8 tests as skipped (NOT errored). Implementation: module-level `pytest.importorskip('nicegui')` triggers a skip at collection time if the import fails. Verify by uninstalling nicegui temporarily:

```bash
pip uninstall -y nicegui
pytest tests/test_ui_smoke.py -v   # should report 8 skipped
pip install -e .[ui]
pytest tests/test_ui_smoke.py -v   # should report 8 passed
```

### 5. Property test (smoke 7) covers correctness item #2

Per spec §11 item 2, the combo → cell mapping must have no off-by-one. This is the load-bearing correctness property for Agent B's matrix work. Your smoke 7 exercises:

- `enumerate_hand_classes()` returns exactly 169 entries.
- Per-class combo counts: pair=6, suited=4, offsuit=12.
- Total combos = 1326.
- `classify_combo(*combo)` is the inverse of `enumerate_combos(hc)` for every combo in every class.

If any of these fails, the matrix render will display strategies in the wrong cells — a critical UX bug.

### 6. The stop-button smoke test (smoke 5) uses the right preset

The preset `'preset-default-100bb-postflop'` is Agent A's marker for the "Default 100BB postflop" preset (per spec §3.1). The smoke test selects it because its solve loop runs long enough that we can press stop while still solving. Do NOT use the river-only subgame preset (too fast — might already be done by the time stop fires).

### 7. ElementFilter markers contract

The markers your tests query (e.g., `'matrix-cell'`, `'solve-button'`) are contracts Agents A and B are obligated to register. If you find that a test fails because a marker isn't registered, that's a contract drift from the spec — flag it.

The full list of markers your tests use (cross-reference against Agent A + B prompts):
- Agent A: `spot-input-panel`, `run-panel`, `board-picker-cell-*`, `range-string-input-p{0|1}`, `stack-input-p{0|1}`, `reset-spot-button`, `preset-{preset_id}` (one per of the 12 fixture spots per `pr10a_spec.md` §7.4: `preset-river-tiny-subgame`, `preset-flop-k72r-100bb`, `preset-flop-t87s-100bb`, `preset-flop-monotone-hhh`, `preset-flop-paired-q9q`, `preset-turn-kqj9-4-flush`, `preset-turn-t872-brick`, `preset-river-axxs-polar`, `preset-preflop-btn-vs-bb`, `preset-river-blocker-heavy`, `preset-shortstack-25bb`, `preset-deepstack-200bb`), `bet-size-checkbox-*`, `iterations-input`, `backend-toggle`, `solve-button`, `pause-button`, `stop-button`, `expl-chart`, `progress-iteration`, `progress-status`, `mock-mode-banner` (Q7 locked), `mock-mode-banner-dismiss`.
- Agent B: `range-matrix-display`, `matrix-cell`, `matrix-cell-{cls}`, `combo-inspector-strip`, `tree-browser`, `tree-widget`, `tree-reach-slider`.
- Agent C (your own): `library-header-button` (registered by Agent A but pointing at YOUR dialog), `library-dialog`, `library-filter-input`, `library-load-button`, `library-delete-button`, `library-stub-row-{idx}`.

### 8. README section placement

Insert AFTER the existing CLI usage section and BEFORE the development notes. Do not move existing content; only add.

## License-aware sourcing

**You may port architecturally (not code-copy) from MIT/Apache sources:**
- `nicegui/llms.md` — NiceGUI testing patterns. Cite the testing-section mental model if you copy a >5 LOC pattern.

**You may NOT copy from AGPL sources:**
- `references/code/postflop-solver/` — **AGPL v3**. No code copy.
- `references/code/TexasSolver/` — **AGPL v3**. Same rule.

**You may NOT extrapolate from training data.** Your tests are written from the spec + interface contracts. The library stub is trivial enough that it's all first-party code.

## Quality bar

- **ruff clean:** `ruff check ui/views/library_browser.py tests/test_ui_smoke.py poker_solver/cli.py` reports zero issues.
- **black clean:** `black --check ui/views/library_browser.py tests/test_ui_smoke.py poker_solver/cli.py` reports no changes.
- **mypy strict-clean on new code:** `mypy --strict ui/views/library_browser.py tests/test_ui_smoke.py` reports zero errors. (The CLI mods reuse the existing `argparse` patterns and inherit the repo's mypy config.)
- **No new third-party deps beyond `nicegui`** in `pyproject.toml`. The only addition is the `[ui]` extra.
- **All existing tests still pass.** Your `cli.py` mods are purely additive (a new subcommand); they cannot affect existing behavior. Verify with `pytest -x`.
- **CLI works without NiceGUI installed.** Confirm with `pip uninstall -y nicegui && poker-solver equity 'AhKs' 'QcQd'` (any non-UI subcommand should still work).
- **`poker-solver ui` launches the app** when nicegui is installed. Smoke-verify manually.
- **Code size budget: ~400–500 LOC** combined across library_browser + test_ui_smoke + cli mods. Stay within budget.

## Reference-first rule

Before any technical claim or code pattern, check the local references. `/Users/ashen/Desktop/poker_solver/references/README.md` indexes them. Never extrapolate from training data when a local source exists.

For NiceGUI testing patterns, cite `nicegui/llms.md` testing section.

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Lint + format
ruff check ui/views/library_browser.py tests/test_ui_smoke.py poker_solver/cli.py
black --check ui/views/library_browser.py tests/test_ui_smoke.py poker_solver/cli.py

# 2. Type-check
mypy --strict ui/views/library_browser.py tests/test_ui_smoke.py

# 3. Test collection (your tests must collect without import errors)
pytest --collect-only tests/test_ui_smoke.py 2>&1 | tail -15
# Expected: ~8 tests collected (one for each spec §10 item).

# 4. Pytest with NiceGUI installed: tests should pass (against Agent A + B impls).
pytest -x tests/test_ui_smoke.py 2>&1 | tail -30

# 5. Pytest WITHOUT NiceGUI: tests should skip cleanly.
# (Skip this step if Agent A + B haven't landed yet; they need nicegui for
# their development too.)
# pip uninstall -y nicegui
# pytest tests/test_ui_smoke.py -v 2>&1 | tail -15
# pip install -e .[ui]

# 6. CLI smoke - launch and immediately Ctrl-C (skip if running in CI)
# poker-solver ui &
# sleep 1
# curl -s http://localhost:8080/ | head -3
# kill %1

# 7. CLI works without NiceGUI (negative test)
# Skip if local dev needs nicegui:
# pip uninstall -y nicegui
# poker-solver equity 'AhKs' 'QcQd'      # should still work
# poker-solver ui                          # should exit 2 with install hint
# pip install -e .[ui]

# 8. Full test suite (your tests + existing tests).
pytest -x 2>&1 | tail -20
# Expected: existing tests + ~8 new UI tests all pass.

# 9. README section is correctly placed
grep -A 3 "^## UI" README.md | head -10
```

If any of the above fails, fix the issue before reporting done. If a smoke test reveals a spec ambiguity or contract drift, **stop and flag it** — do not silently work around it.

## Report back format

When done, write a concise report (≤300 words) covering:

1. Files created + line counts; files modified + line-delta (`cli.py`, `pyproject.toml`, `README.md`).
2. Tests that PASS against Agent A + B's implementations (count).
3. Tests that FAIL — classified as: (a) test bug (you fixed it), (b) spec ambiguity (flag for human), (c) impl bug (flag for human / contract drift from spec).
4. Any spec ambiguity you couldn't resolve from the spec / PLAN.
5. Tests you added beyond the spec §10 list (justify each).
6. License attributions you added (if any).
7. Open questions for human review.
