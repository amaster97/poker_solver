# PR 10a — Expected File Matrix

Catalog of what each of Agents A / B / C should produce, derived from
`agent_a_prompt.md`, `agent_b_prompt.md`, `agent_c_prompt.md`.
Read-only inventory; no implementation guidance.

## 1. Per-agent expected files

### Agent A — spot input + run panel + state management

| File (absolute path) | Expected LOC | Notes / line-range hint |
| --- | --- | --- |
| `/Users/ashen/Desktop/poker_solver/ui/__init__.py` | ~5 | exposes `__version__ = "0.1.0"` only |
| `/Users/ashen/Desktop/poker_solver/ui/app.py` | ~150 | `build_page()` + `launch(port, host, dark_mode)` |
| `/Users/ashen/Desktop/poker_solver/ui/state.py` | ~400 | `RangeWithFreqs`, `Spot`, `SolveSession`, `UIPrefs`, `SolveRunner`, `AppState`, `get_state`, `save_state`, `enumerate_hand_classes`, `enumerate_combos`, `hand_class_label`, `classify_combo` |
| `/Users/ashen/Desktop/poker_solver/ui/views/__init__.py` | ~1 | empty package init |
| `/Users/ashen/Desktop/poker_solver/ui/views/spot_input.py` | ~200 | `render(state)` for board picker + range matrix INPUT + presets |
| `/Users/ashen/Desktop/poker_solver/ui/views/run_panel.py` | ~200 | `render(state, on_solve, on_pause, on_stop)` + `refresh_progress(state)` |
| `/Users/ashen/Desktop/poker_solver/ui/views/onboarding.py` | ~80 | 3-step modal triggered on first launch |
| **Agent A total** | **~800–1100** | spec quality bar §"Code size budget" |

### Agent B — range matrix display + tree browser

| File (absolute path) | Expected LOC | Notes / line-range hint |
| --- | --- | --- |
| `/Users/ashen/Desktop/poker_solver/ui/views/range_matrix.py` | ~300 | `CellSummary`, `cell_strategy_summary`, `cell_color`, `render`, `inspect_panel` |
| `/Users/ashen/Desktop/poker_solver/ui/views/tree_browser.py` | ~300 | `TreeNode`, `SolveTree`, `tree_node_to_dict`, `on_tree_node_selected`, `on_tree_node_expanded`, `render` |
| **Agent B total** | **~500–700** | spec quality bar §"Code size budget" |

### Agent C — mock solver + library stub + 20 smoke tests + CLI/pyproject/README

| File (absolute path) | Expected LOC | Notes / line-range hint |
| --- | --- | --- |
| `/Users/ashen/Desktop/poker_solver/ui/mock_solver.py` | ~400 | `_CANCEL_FLAG`, `FixturePreset`, `mock_solve`, `list_fixture_presets`, `load_fixture`, 6 failure modes |
| `/Users/ashen/Desktop/poker_solver/ui/mock_solver_fixtures.py` | ~150 (optional split) | 12 fixture spot data tables; inline if mock_solver.py stays <400 |
| `/Users/ashen/Desktop/poker_solver/ui/views/library_browser.py` | ~80 | `render(state) -> ui.dialog`, `render_header_button(state, dialog)` |
| `/Users/ashen/Desktop/poker_solver/tests/test_ui_smoke.py` | ~400 | 20 tests (8 UI + 5 mock + 4 UX + 3 edge) |
| `/Users/ashen/Desktop/poker_solver/poker_solver/cli.py` | +~25 LOC delta | `_cmd_ui` + ui subparser registration |
| `/Users/ashen/Desktop/poker_solver/pyproject.toml` | +~10 LOC delta | `[ui]` extra + `markers` entry |
| `/Users/ashen/Desktop/poker_solver/README.md` | +~20 LOC delta | "## UI (mock)" section |
| **Agent C total (new files)** | **~1030** | + ~55 LOC of edits to existing files |

## 2. Cross-agent contracts — mock interface boundaries

The mock solver lives in `ui/mock_solver.py` (Agent C) and is consumed by
Agent A's `SolveRunner` via a single-line import alias:

```python
from ui.mock_solver import mock_solve as _solve_postflop_impl
```

Locked surface (byte-identical to PR 5's `solve_hunl_postflop` in the first
8 parameters so PR 10b is a one-line swap):

- `mock_solve(config, iterations, *, log_every, memory_budget_gb, target_exploitability, seed, dcfr_kwargs, on_progress, mock_latency_ms, mock_failure_mode) -> HUNLSolveResult`
- `list_fixture_presets() -> list[FixturePreset]`
- `load_fixture(preset_id: str) -> HUNLConfig`
- Module-level `_CANCEL_FLAG: threading.Event` — set by `SolveRunner.stop()`,
  checked by `mock_solve()` once per snapshot.

Agent A imports `mock_solve` and `_CANCEL_FLAG`; Agent A's spot input view
imports `list_fixture_presets` and `load_fixture` for the 12-preset
dropdown. Agent B does NOT import from `ui.mock_solver` (smoke 13 enforces
this via static grep).

Agent A's `ui.state` exports consumed by Agent B (read-only):
`AppState`, `Spot`, `RangeWithFreqs`, `SolveRunner`, `SolveSession`,
`UIPrefs`, `get_state`, `save_state`, `enumerate_hand_classes`,
`enumerate_combos`, `hand_class_label`, `classify_combo`.

Agent A's `ui.app` consumes Agent B's `range_matrix.render` and
`tree_browser.render`, plus Agent C's `library_browser.render` /
`library_browser.render_header_button`.

## 3. Test files expected

- `/Users/ashen/Desktop/poker_solver/tests/test_ui_smoke.py` — Agent C, 20
  tests grouped per `pr10a_spec.md` §10:
  - §10.1 (tests 1–8): page renders, board picker, range string,
    solve worker, stop button, 169 cells, combo property test,
    library dialog.
  - §10.2 (tests 9–13, PR 10b deletes these): mock solve returns
    `HUNLSolveResult`, streams progress, OOM failure, cancelled
    failure, mock-symbol leak grep.
  - §10.3 (tests 14–17): Pio color blend, blocker overlay, input-vs-display
    palette disjoint, default log-scale chart.
  - §10.4 (tests 18–20): OOM remediation toast, push/fold dispatch at 15 BB,
    long-solve ETA after 30 s.
- No separate `tests/test_ui_*.py` files split per agent; the spec
  consolidates UI tests into a single module.
- No `tests/test_mock_*.py` standalone file; mock coverage lives inside
  `test_ui_smoke.py` §10.2.

## 4. Total expected LOC

Sum across the three agents (new files only):

- Agent A: ~800–1100 LOC across 7 files
- Agent B: ~500–700 LOC across 2 files
- Agent C: ~1030 LOC across 4 new files + ~55 LOC of edits to 3 existing files

**Grand total expected: ~2330–2830 new LOC + ~55 LOC edits ≈ 2400–2900 LOC.**

(Note: spec quality bars cap each agent's budget; aggregate sits at the
low end of the prompt's ~3000–5000 question. If implementations land near
top of each budget, total can reach ~3000.)

## Constraints honored

- Read-only catalog of expectations from the three prompts.
- No new implementation guidance introduced beyond what the prompts state.
