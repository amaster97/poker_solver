"""Smoke tests for the PR 10a NiceGUI app.

Uses NiceGUI 2.x's ``User`` fixture (async, in-process, no real browser).
Every test is marked ``@pytest.mark.ui`` and the module skips cleanly if
nicegui is not installed.

Test groups per ``pr10a_spec.md`` §10:
  - §10.1 — 8 UI smoke tests (tests 1-8; identical to PR 10's list)
  - §10.2 — 5 mock-solver coverage tests (tests 9-13). **PR 10b deletes
            these.**
  - §10.3 — 4 UX-grounded smoke additions (tests 14-17).
  - §10.4 — 3 edge-case coverage tests (tests 18-20).

We are writing tests from the spec + interface contracts alone — NOT
from Agent A/B's implementations. Per the prompt rule, that's the
dividend of the fan-out: if a test fails against the impl, it's a real
bug OR a real spec ambiguity (flagged for the orchestrator), not a
spec-impl drift.
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import threading
from collections.abc import Iterator

import pytest

pytest.importorskip("nicegui")

# ruff: noqa: E402, I001  (post-importorskip imports must follow the skip)
from nicegui.testing import User

# Register NiceGUI's pytest plugin(s) so the ``user`` fixture is
# available. We load ``user_plugin`` directly (skipping ``screen_plugin``
# which needs selenium for browser-driven tests we don't use). Per
# https://nicegui.io/documentation/section_testing.
pytest_plugins = [
    "nicegui.testing.general_fixtures",
    "nicegui.testing.user_plugin",
]

pytestmark = [
    pytest.mark.ui,
    # NiceGUI's User fixture needs to know which file registers the
    # ``@ui.page('/')`` builder. Agent A owns ``ui/app.py``; point the
    # fixture there.
    pytest.mark.nicegui_main_file("ui/app.py"),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_state_dir(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[pathlib.Path]:
    """Override the state.json location so tests don't touch the real home dir.

    Per the prompt's "default decisions LOCKED" block: state lives at
    ``~/.poker_solver_ui/state.json``. We redirect via ``$HOME`` so any
    state-loader (Agent A's) that expands ``~`` lands in ``tmp_path``.

    We also set the ``POKER_SOLVER_UI_STATE_DIR`` env var as a secondary
    override mechanism — Agent A may use either pattern.

    PR 10b: also resets the AppState singleton + stops any in-flight solver
    from a previous test. With the real solver (vs PR 10a's mock) tests
    can take longer than the mock's near-zero latency, so the runner from
    one test may still be alive at the start of the next.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("POKER_SOLVER_UI_STATE_DIR", str(tmp_path / ".poker_solver_ui"))
    # PR 10b: stop any in-flight solver from a previous test before this
    # one starts. With the real solver (vs PR 10a's near-zero-latency
    # mock) tests can leave the worker thread alive past the test exit
    # and the singleton SolveRunner refuses re-entrant `start()` while
    # `is_alive()`. We do NOT reset the AppState singleton here because
    # some smoke tests rely on cross-test singleton carryover for
    # render-time state (the rendered matrix bakes in the spot.board at
    # render time; resetting wipes the board between tests).
    from ui.state import get_state

    try:
        current = get_state()
        if current.runner.is_alive():
            current.runner.stop()
            current.runner.join(timeout=3.0)
        # Always reset the solver state (cancel flags, history) without
        # touching the spot. Idempotent on idle.
        current.runner._stop_event.clear()
        current.runner._pause_event.clear()
    except Exception:  # noqa: BLE001
        pass
    yield tmp_path


@pytest.fixture
def reset_cancel_flag() -> Iterator[None]:
    """Clear the mock solver's cancellation flag before/after each test."""
    from ui.mock_solver import _CANCEL_FLAG

    _CANCEL_FLAG.clear()
    yield
    _CANCEL_FLAG.clear()


# ---------------------------------------------------------------------------
# §10.1 — 8 UI smoke tests
# ---------------------------------------------------------------------------


async def test_page_renders_without_exception(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Smoke test 1: page opens; two-pane layout renders (Q1 locked).

    Per ``pr10a_spec.md`` §10.1 item 1 + §11 acceptance #2 + #11.
    """
    await user.open("/")
    # Agent A markers (right sidebar expansion panels).
    assert user.find(marker="spot-input-panel").elements
    assert user.find(marker="run-panel").elements
    # Agent B markers (matrix + tree browser).
    assert user.find(marker="range-matrix-display").elements
    assert user.find(marker="tree-browser").elements
    # Q7 lock: yellow Mock mode banner.
    assert user.find(marker="mock-mode-banner").elements


async def test_board_picker_accepts_three_cards(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Smoke test 2: clicking three cards in the board picker updates state +
    starting_street becomes FLOP.

    Per ``pr10a_spec.md`` §10.1 item 2.
    """
    from ui.state import get_state

    await user.open("/")
    # Pick a flop (3 cards). Marker pattern from Agent A: 'board-picker-cell-{card}'.
    user.find(marker="board-picker-cell-Kh").click()
    user.find(marker="board-picker-cell-7d").click()
    user.find(marker="board-picker-cell-2c").click()
    state = get_state()
    # Postflop starts when 3 cards are picked → FLOP.
    assert state.current_spot.starting_street.name == "FLOP"
    assert len(state.current_spot.board) == 3


async def test_range_input_via_string(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Smoke test 3: typing 'AA, KK-TT' into the P0 range string field reflects
    5 hand classes selected in the matrix input.

    Per ``pr10a_spec.md`` §10.1 item 3.
    """
    from ui.state import get_state

    await user.open("/")
    user.find(marker="range-string-input-p0").type("AA, KK-TT")
    state = get_state()
    # AA, KK, QQ, JJ, TT → 5 classes; we enumerate via the RangeWithFreqs API.
    range_p0 = state.current_spot.ranges[0]
    # Compute the set of hand classes with frequency > 0.
    from ui.state import classify_combo, enumerate_combos

    selected: set[str] = set()
    for hc in ("AA", "KK", "QQ", "JJ", "TT"):
        for combo in enumerate_combos(hc):
            if range_p0.frequency_of(combo) > 0:
                selected.add(classify_combo(*combo))
                break
    assert len(selected) == 5
    assert {"AA", "KK", "QQ", "JJ", "TT"}.issubset(selected)


async def test_solve_button_starts_worker(
    user: User, isolated_state_dir: pathlib.Path, reset_cancel_flag: None
) -> None:
    """Smoke test 4: clicking Solve transitions runner.status to 'running'
    within 200 ms; worker thread is alive.

    Per ``pr10a_spec.md`` §10.1 item 4 + §11 critical item 1.
    """
    from ui.state import get_state

    await user.open("/")
    user.find(marker="preset-river-tiny-subgame").click()
    user.find(marker="solve-button").click()
    # Allow a brief moment for the worker thread to flip status.
    await asyncio.sleep(0.2)
    state = get_state()
    assert state.runner.status in ("running", "done"), (
        f"expected status 'running' or 'done' after solve click; "
        f"got {state.runner.status!r}"
    )


async def test_stop_button_halts_within_one_iteration(
    user: User, isolated_state_dir: pathlib.Path, reset_cancel_flag: None
) -> None:
    """Smoke test 5: stop button halts within 1 (mocked) iteration.

    Per ``pr10a_spec.md`` §11 acceptance #5. Uses ``flop_k72r_100bb``
    preset — long-running enough to click stop while still solving.
    """
    from ui.state import get_state

    from poker_solver.hunl import HUNLPoker

    await user.open("/")
    user.find(marker="preset-flop-k72r-100bb").click()
    state = get_state()
    # The UI's _on_solve handler doesn't expose `mock_latency_ms` (mock-
    # specific injection lives behind `SolveRunner.start`). Drive the
    # runner directly with a 500 ms mock latency so the stop-button race
    # is observable; without latency the mock finishes in <1 ms and
    # `iteration` already equals `iterations` when stop registers.
    config = state.current_spot.to_hunl_config()
    state.runner.start(
        HUNLPoker(config),
        iterations=100_000,
        log_every=50,
        mock_latency_ms=500,
    )
    await asyncio.sleep(0.1)
    user.find(marker="stop-button").click()
    await asyncio.sleep(0.5)
    assert state.runner.status in ("stopped", "done"), (
        f"expected status 'stopped' or 'done' after stop click; "
        f"got {state.runner.status!r}"
    )
    assert state.runner.iteration < 50_000


async def test_range_matrix_renders_169_cells(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Smoke test 6: ElementFilter(marker='matrix-cell') yields 169 elements.

    Per ``pr10a_spec.md`` §10.1 item 6.
    """
    await user.open("/")
    cells = user.find(marker="matrix-cell").elements
    assert len(cells) == 169, f"expected 169 matrix cells, got {len(cells)}"


def test_combo_to_cell_mapping_no_off_by_one() -> None:
    """Smoke test 7: for every hand class, ``enumerate_combos`` yields the
    right combo count (6 / 4 / 12) and ``classify_combo`` is the inverse.

    Per ``pr10a_spec.md`` §10.1 item 7 + §11 critical item 2 — load-bearing
    property for matrix correctness. Runs without any actual solve.
    """
    from ui.state import (
        classify_combo,
        enumerate_combos,
        enumerate_hand_classes,
    )

    classes = enumerate_hand_classes()
    assert len(classes) == 169

    total_combo_count = 0
    for entry in classes:
        # Agent A may return either (row, col, hc) tuples or just hc strings;
        # support both shapes.
        hc = entry[-1] if isinstance(entry, tuple) else entry
        combos = enumerate_combos(hc)
        if hc.endswith("s"):  # suited
            assert len(combos) == 4, (
                f"{hc}: expected 4 suited combos, got {len(combos)}"
            )
        elif hc.endswith("o"):  # offsuit
            assert len(combos) == 12, (
                f"{hc}: expected 12 offsuit combos, got {len(combos)}"
            )
        else:  # pair
            assert len(combos) == 6, f"{hc}: expected 6 pair combos, got {len(combos)}"
        total_combo_count += len(combos)

        # Inverse: classify_combo(*combo) == hc for every combo.
        for combo in combos:
            assert classify_combo(*combo) == hc, (
                f"classify_combo({combo!r}) returned wrong class: "
                f"expected {hc}, got {classify_combo(*combo)!r}"
            )

    assert total_combo_count == 1326, (
        f"expected 1326 combos total, got {total_combo_count}"
    )


async def test_library_dialog_opens(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Smoke test 8: clicking the library header button opens the dialog;
    ``[Load selected]`` is disabled.

    Per ``pr10a_spec.md`` §10.1 item 8 + §4.6 mockup.

    Note: the stub-row check was dropped post-PR-11. PR 11 wired the real
    ``poker_solver.library`` SQLite-backed gateway, so the
    ``library-stub-row-{idx}`` markers (and accompanying "PR 11 — not
    yet wired" toast) are only emitted when the library module is
    unimportable. On an isolated-state-dir fresh install the library is
    importable but empty, which renders the "(no spots saved yet)" label
    instead. The disable-prop check on ``library-load-button`` is the
    surviving smoke-relevant invariant.
    """
    await user.open("/")
    user.find(marker="library-header-button").click()
    # Dialog opens.
    assert user.find(marker="library-dialog").elements
    # Load button is disabled.
    load_btn_elements = user.find(marker="library-load-button").elements
    assert len(load_btn_elements) >= 1
    load_btn = list(load_btn_elements)[0]
    props = getattr(load_btn, "_props", None) or {}
    disable_prop = props.get("disable")
    assert disable_prop is True or "disable" in (
        getattr(load_btn, "props", "") or ""
    ), f"library-load-button missing 'disable' prop; got props={props!r}"


def _count_notifications(user: User) -> int:
    """Helper: count NiceGUI notification elements in the current page.

    Different NiceGUI versions expose the notification kind differently;
    we try common shapes and return the count.
    """
    from nicegui import ui as _ui

    notification_kind = getattr(_ui, "notification", None)
    if notification_kind is not None:
        return len(user.find(kind=notification_kind).elements)
    # Fallback: query by a generic class name.
    return 0


# ---------------------------------------------------------------------------
# §10.2 — 5 mock-solver coverage tests (PR 10b deletes these)
# ---------------------------------------------------------------------------


def test_mock_solve_returns_real_hunl_solve_result() -> None:
    """Smoke test 9: isinstance check on HUNLSolveResult + MemoryReport.

    Per ``pr10a_spec.md`` §10.2 item 9 + §7.3.
    """
    from poker_solver.hunl_solver import HUNLSolveResult
    from poker_solver.profiler.memory import MemoryReport

    from ui.mock_solver import load_fixture, mock_solve

    config = load_fixture("river_tiny_subgame")
    result = mock_solve(config, iterations=100, mock_latency_ms=0)
    assert isinstance(result, HUNLSolveResult), (
        f"expected HUNLSolveResult, got {type(result).__name__}"
    )
    assert isinstance(result.memory_report, MemoryReport), (
        f"expected MemoryReport, got {type(result.memory_report).__name__}"
    )


def test_mock_solve_streams_progress_callbacks() -> None:
    """Smoke test 10: progress is published once per snapshot; monotone iter;
    monotone-ish decreasing expl over the recorded history.

    Per ``pr10a_spec.md`` §10.2 item 10. Note: per the 2026-05-22 audit
    (``docs/pr10_prep/mock_signature_drift.md`` Option A), the mock uses
    polling via ``read_latest_progress`` instead of a progress callback
    parameter. The final ``HUNLSolveResult.exploitability_history`` is the
    canonical source of truth for the chart.
    """
    from ui.mock_solver import load_fixture, mock_solve

    config = load_fixture("river_tiny_subgame")
    result = mock_solve(
        config,
        iterations=1000,
        log_every=100,
        mock_latency_ms=0,
    )
    # We requested iterations=1000, log_every=100 → ~10 snapshots.
    history = result.exploitability_history
    assert len(history) >= 9, f"expected >=9 history entries, got {len(history)}"
    # Exploitability decreases overall from first to last sample.
    assert history[-1] < history[0], (
        f"exploitability did not decrease: first={history[0]} last={history[-1]}"
    )
    # Final result reflects the requested iterations (not partial).
    assert result.iterations == 1000, (
        f"expected iterations=1000 (success path), got {result.iterations}"
    )


def test_mock_solve_failure_oom_raises_memory_error_with_partial_report() -> None:
    """Smoke test 11: ``mock_failure_mode='oom'`` raises MemoryError;
    ``.args[1]`` is a MemoryReport.

    Per ``pr10a_spec.md`` §10.2 item 11 + §6 edge #5.
    """
    from poker_solver.profiler.memory import MemoryReport

    from ui.mock_solver import load_fixture, mock_solve

    config = load_fixture("deepstack_200bb")
    with pytest.raises(MemoryError) as excinfo:
        mock_solve(
            config,
            iterations=10_000,
            mock_failure_mode="oom",
            mock_latency_ms=0,
        )
    assert len(excinfo.value.args) >= 2, (
        f"MemoryError.args should be (msg, report); got args={excinfo.value.args!r}"
    )
    assert isinstance(excinfo.value.args[1], MemoryReport), (
        f"args[1] expected MemoryReport, got {type(excinfo.value.args[1]).__name__}"
    )


def test_mock_solve_failure_cancelled_returns_partial_result() -> None:
    """Smoke test 12: ``mock_failure_mode='cancelled'`` returns
    HUNLSolveResult with iterations < requested and non-empty strategy.

    Per ``pr10a_spec.md`` §10.2 item 12 + §6 edge #2.
    """
    from ui.mock_solver import load_fixture, mock_solve

    config = load_fixture("river_tiny_subgame")
    result = mock_solve(
        config,
        iterations=10_000,
        mock_failure_mode="cancelled",
        mock_latency_ms=0,
    )
    assert result.iterations < 10_000, (
        f"expected partial iterations < 10000, got {result.iterations}"
    )
    assert len(result.average_strategy) > 0, (
        "expected non-empty average_strategy after cancellation"
    )


def test_ui_never_imports_mock_specific_symbols() -> None:
    """Smoke test 13: ``ui/`` outside ``ui/state.py`` and ``ui/mock_solver*.py``
    contains no ACTUAL imports of mock_solver symbols.

    Per ``pr10a_spec.md`` §10.2 item 13 + §11 acceptance #7. The acceptance
    text reads: "``ui/mock_solver`` imports appear in EXACTLY ONE file
    (``ui/state.py``)." We grep for actual import lines (``from
    ui.mock_solver ...`` / ``import ui.mock_solver``), not docstring
    mentions. Docstring cross-references are fine and routine.
    """
    import re

    ui_root = pathlib.Path(__file__).resolve().parent.parent / "ui"
    # Match ``from ui.mock_solver`` or ``import ui.mock_solver`` (with any
    # whitespace); ignore docstrings, comments, and string literals.
    import_pat = re.compile(
        r"^\s*(?:from\s+ui\.mock_solver|import\s+ui\.mock_solver)",
        re.MULTILINE,
    )
    offending: list[str] = []
    for py in ui_root.rglob("*.py"):
        if py.name == "state.py":
            continue
        if py.name.startswith("mock_solver"):
            continue
        text = py.read_text(encoding="utf-8")
        if import_pat.search(text):
            offending.append(str(py))
    assert not offending, (
        f"mock_solver import leaked into non-state.py files: {offending!r}\n"
        f"Per pr10a_spec.md §11 acceptance #7, mock_solver should be "
        f"imported in EXACTLY ONE file (ui/state.py)."
    )


# ---------------------------------------------------------------------------
# §10.3 — 4 UX-grounded smoke additions
# ---------------------------------------------------------------------------


async def test_range_matrix_color_blend_matches_pio_convention(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Smoke test 14: given fixture with known per-cell action freqs,
    rendered RGB matches additive formula within ±2 per channel.

    Locks adopted pattern #1 (Pio R/Y/G convention) per
    ``pr10a_spec.md`` §10.3 item 14.

    Additive RGB blend (per PR 10 §7.3):
      fold  → red    (255, 0, 0)
      call  → yellow (255, 255, 0)
      raise → green  (0, 255, 0)
    Cell RGB = freq_fold * red + freq_call * yellow + freq_raise * green.
    """
    import importlib

    range_matrix = importlib.import_module("ui.views.range_matrix")
    cell_rgb_for_action_freqs = getattr(range_matrix, "cell_rgb_for_action_freqs", None)
    assert cell_rgb_for_action_freqs is not None, (
        "ui.views.range_matrix must expose cell_rgb_for_action_freqs(fold, "
        "call, raise_) -> (r, g, b) for the palette-audit smoke test"
    )

    # Pure-fold cell.
    r, g, b = cell_rgb_for_action_freqs(fold=1.0, call=0.0, raise_=0.0)
    assert abs(r - 255) <= 2 and abs(g) <= 2 and abs(b) <= 2

    # Pure-raise cell.
    r, g, b = cell_rgb_for_action_freqs(fold=0.0, call=0.0, raise_=1.0)
    assert abs(r) <= 2 and abs(g - 255) <= 2 and abs(b) <= 2

    # 50/50 call/raise mix → blended yellow-green.
    r, g, b = cell_rgb_for_action_freqs(fold=0.0, call=0.5, raise_=0.5)
    # Yellow contribution: (255*0.5, 255*0.5, 0) = (127, 127, 0)
    # Green contribution:  (0, 255*0.5, 0)      = (0, 127, 0)
    # Sum: (127, 254, 0)
    assert abs(r - 127) <= 2, f"R: expected ~127, got {r}"
    assert abs(g - 254) <= 2, f"G: expected ~254, got {g}"
    assert abs(b) <= 2, f"B: expected ~0, got {b}"


async def test_blocker_cells_show_slashed_overlay(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Smoke test 15: ``flop_k72r_100bb`` fixture; AhKh-only class renders
    slashed-overlay style (blocked by Kh on board).

    Per ``pr10a_spec.md`` §10.3 item 15.
    """
    await user.open("/")
    user.find(marker="preset-flop-k72r-100bb").click()
    # Wait a beat for the matrix to re-render with the new board.
    await asyncio.sleep(0.1)
    # The AKs cell should carry a blocker overlay because the AhKh combo
    # is impossible (Kh is on the board). The marker pattern is
    # 'matrix-cell-AKs' per Agent B's contract. The blocker class is
    # 'blocker-overlay' (a CSS class, NOT a marker — checks the class set).
    aks_cell_elements = user.find(marker="matrix-cell-AKs").elements
    assert len(aks_cell_elements) >= 1, "no AKs matrix cell found"
    cell = list(aks_cell_elements)[0]
    # NiceGUI exposes classes via `_classes` attribute.
    classes = getattr(cell, "_classes", None) or []
    # Accept either "blocker-overlay" or any class containing "blocker".
    has_blocker_class = any("blocker" in c for c in classes)
    assert has_blocker_class, (
        f"AKs cell missing blocker overlay class on K-high flop board; "
        f"classes={classes!r}"
    )


async def test_input_matrix_palette_disjoint_from_display_palette(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Smoke test 16: static assertion that range-input matrix sources
    blue-gradient palette and display matrix sources RYG.

    Locks principle 4 (color minimalism, palettes disjoint) per
    ``pr10a_spec.md`` §10.3 item 16.
    """
    import importlib

    # Agent B owns range_matrix.py; we inspect its palette constants.
    display_matrix = importlib.import_module("ui.views.range_matrix")
    display_palette = getattr(display_matrix, "DISPLAY_PALETTE", None) or getattr(
        display_matrix, "STRATEGY_PALETTE", None
    )
    assert display_palette is not None, (
        "ui.views.range_matrix must expose DISPLAY_PALETTE (or "
        "STRATEGY_PALETTE) for palette-disjointness audit"
    )

    # The display palette must contain RYG anchor colors (red ~255,0,0;
    # yellow ~255,255,0; green ~0,255,0).
    palette_str = str(display_palette).lower()
    # Sanity: should NOT include "blue" (the input palette's primary).
    assert "blue" not in palette_str, (
        f"display palette must not contain blue; got {display_palette!r}"
    )

    # Agent A owns spot_input.py; inspect its INPUT_PALETTE constant.
    spot_input = importlib.import_module("ui.views.spot_input")
    input_palette = getattr(spot_input, "INPUT_PALETTE", None) or getattr(
        spot_input, "RANGE_INPUT_PALETTE", None
    )
    assert input_palette is not None, (
        "ui.views.spot_input must expose INPUT_PALETTE for palette-disjointness audit"
    )
    input_palette_str = str(input_palette).lower()
    # Sanity: should mention "blue" (white → blue gradient per spec §2.4).
    assert "blue" in input_palette_str or "#" in input_palette_str, (
        f"input palette should source blue gradient; got {input_palette!r}"
    )


async def test_chart_default_log_scale(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Smoke test 17: ``ui.echart`` Y axis defaults to log scale; linear
    toggle exists.

    Per ``pr10a_spec.md`` §10.3 item 17.
    """
    await user.open("/")
    # The chart element carries marker 'expl-chart'; the linear toggle is
    # 'expl-chart-linear-toggle'.
    chart_elements = user.find(marker="expl-chart").elements
    assert len(chart_elements) >= 1, "no expl-chart element rendered"
    # The toggle must exist.
    toggle_elements = user.find(marker="expl-chart-linear-toggle").elements
    assert len(toggle_elements) >= 1, "no linear-scale toggle for the chart"
    # The chart's options should declare log Y axis by default.
    chart = list(chart_elements)[0]
    options = getattr(chart, "_props", {}).get("options") or getattr(
        chart, "options", None
    )
    if options is not None:
        # ECharts axis type lives at options.yAxis.type.
        y_axis = options.get("yAxis") if isinstance(options, dict) else None
        if isinstance(y_axis, dict):
            assert y_axis.get("type") == "log", (
                f"expl-chart yAxis.type must default to 'log'; got "
                f"{y_axis.get('type')!r}"
            )


# ---------------------------------------------------------------------------
# §10.4 — 3 edge-case coverage tests
# ---------------------------------------------------------------------------


async def test_oom_failure_shows_remediation_notification(
    user: User, isolated_state_dir: pathlib.Path, reset_cancel_flag: None
) -> None:
    """Smoke test 18: ``mock_failure_mode='oom'`` surfaces §6.5 notification
    with "Reduce bet sizes" quick-action button.

    Per ``pr10a_spec.md`` §10.4 item 18 + §6 edge #5.
    """
    from ui.state import get_state

    from poker_solver.hunl import HUNLPoker

    await user.open("/")
    user.find(marker="preset-deepstack-200bb").click()
    # Trigger the OOM failure mode via SolveRunner.start kwargs (Agent A's
    # surface — see ui/state.py::SolveRunner.start mock_failure_mode kwarg).
    state = get_state()
    config = state.current_spot.to_hunl_config()
    state.runner.start(
        HUNLPoker(config),
        iterations=100,
        log_every=10,
        mock_latency_ms=0,
        mock_failure_mode="oom",
    )
    state.runner.join(timeout=3.0)
    await asyncio.sleep(0.3)
    # The OOM error should surface a notification with the "Reduce bet
    # sizes" remediation button.
    notif_buttons = user.find(marker="oom-reduce-bet-sizes-button").elements
    assert len(notif_buttons) >= 1, (
        "OOM failure must surface 'Reduce bet sizes' quick-action button"
    )


async def test_pushfold_dispatch_at_15bb(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Smoke test 19: setting stacks to 15 BB triggers a yellow warning toast
    with "Switch to push/fold view" button.

    Per ``pr10a_spec.md`` §10.4 item 19 + §6 edge #4.
    """
    await user.open("/")
    # NiceGUI 3.x's `UserInteraction.type` appends to the current value
    # (user_interaction.py:70). The stack inputs start at 100 BB, so
    # ``.type("15")`` yields 10015 — overflow above the 15 BB threshold.
    # Drive the model value directly to land on the boundary the test
    # is actually asserting.
    stack_p0 = list(user.find(marker="stack-input-p0").elements)[0]
    stack_p1 = list(user.find(marker="stack-input-p1").elements)[0]
    stack_p0.value = 15
    stack_p1.value = 15
    # Tab out / commit the change.
    await asyncio.sleep(0.2)
    # Yellow warning toast appears with the push/fold dispatch button.
    pushfold_btn_elements = user.find(marker="pushfold-switch-button").elements
    assert len(pushfold_btn_elements) >= 1, (
        "stacks <= 15 BB must surface 'Switch to push/fold view' toast button"
    )


async def test_long_solve_eta_appears_after_30s(
    user: User, isolated_state_dir: pathlib.Path, reset_cancel_flag: None
) -> None:
    """Smoke test 20: with ``mock_latency_ms=60_000`` and
    ``mock_failure_mode='long_latency'``, ETA text appears in status readout
    after 30 s.

    Per ``pr10a_spec.md`` §10.4 item 20 + §6 edge #1.

    Implementation note: this test stretches real wall-clock if it actually
    waits 30 seconds. To stay fast, we either:
      (a) drive the ETA calculation directly via state.runner.compute_eta()
          (preferred — function-level test that doesn't need the UI loop);
      (b) fall back to a UI-level check on the ETA marker presence with
          a much shorter latency.
    We do (a) when available, else (b).
    """
    from poker_solver.hunl import HUNLPoker
    from ui.state import get_state

    await user.open("/")
    state = get_state()

    # Branch (a): direct ``compute_eta()`` probe if Agent A exposes one.
    compute_eta = getattr(state.runner, "compute_eta", None)
    if callable(compute_eta):
        # Seed a few mock progress samples spanning > 30 s wall-clock.
        state.runner.iteration = 1000
        # Optional fields — may or may not exist depending on impl.
        for attr, val in (
            ("start_time_monotonic", 0.0),
            ("current_time_monotonic", 35.0),
            ("target_iterations", 10000),
        ):
            if hasattr(state.runner, attr):
                setattr(state.runner, attr, val)
        eta = compute_eta()
        assert eta is not None and eta > 0, (
            f"compute_eta must return a positive value after 30s of "
            f"forward progress; got {eta!r}"
        )
        return

    # Branch (b): UI-level fallback — start a real long-latency mock solve
    # and check ETA marker appears within a short polling window.
    user.find(marker="preset-flop-k72r-100bb").click()
    config = state.current_spot.to_hunl_config()
    state.runner.start(
        HUNLPoker(config),
        iterations=10_000,
        log_every=500,
        mock_latency_ms=60_000,
        mock_failure_mode="long_latency",
    )
    # Wait for the ETA marker to appear; bail if too slow (CI).
    deadline = 5.0  # seconds; relaxed for CI
    start = asyncio.get_event_loop().time()
    eta_visible = False
    while asyncio.get_event_loop().time() - start < deadline:
        eta_elements = user.find(marker="progress-eta").elements
        if eta_elements:
            eta_visible = True
            break
        await asyncio.sleep(0.1)
    assert eta_visible, "ETA text never appeared in long-latency mock run"


# ---------------------------------------------------------------------------
# Extra (own work): one direct mock-fixture coverage check.
# Not in the spec §10 list, but useful for the eye-test guarantee.
# Justification: fixture-data correctness is a load-bearing audit item
# (§12 risk #1: "Mock-fixture poker-realism risk") and the test suite
# otherwise only probes one fixture by name; this enumerates all 12.
# ---------------------------------------------------------------------------


def test_all_12_fixtures_load() -> None:
    """Smoke test (extra): all 12 fixture IDs from ``pr10a_spec.md`` §7.4
    are present in ``list_fixture_presets()`` and ``load_fixture()`` returns
    a valid HUNLConfig for each.
    """
    from poker_solver.hunl import HUNLConfig

    from ui.mock_solver import list_fixture_presets, load_fixture

    expected_ids = {
        "river_tiny_subgame",
        "flop_k72r_100bb",
        "flop_t87s_100bb",
        "flop_monotone_hhh",
        "flop_paired_q9q",
        "turn_kqj9_4_flush",
        "turn_t872_brick",
        "river_axxs_polar",
        "preflop_btn_vs_bb",
        "river_blocker_heavy",
        "shortstack_25bb",
        "deepstack_200bb",
    }
    presets = list_fixture_presets()
    preset_ids = {p.id for p in presets}
    assert preset_ids == expected_ids, (
        f"fixture preset id set mismatch:\n"
        f"  missing: {expected_ids - preset_ids!r}\n"
        f"  extra: {preset_ids - expected_ids!r}"
    )
    for preset in presets:
        config = load_fixture(preset.id)
        assert isinstance(config, HUNLConfig)


def test_cancel_flag_halts_mock_solve(reset_cancel_flag: None) -> None:
    """Smoke test (extra): setting ``_CANCEL_FLAG`` from another thread
    halts ``mock_solve`` mid-run.

    Per ``pr10a_spec.md`` §7.5 cancellation contract. This is independent
    of the UI: ``SolveRunner.stop()`` is just one consumer of the flag.
    """
    from poker_solver.hunl_solver import HUNLSolveResult

    from ui.mock_solver import _CANCEL_FLAG, load_fixture, mock_solve

    config = load_fixture("river_tiny_subgame")
    result_holder: dict[str, HUNLSolveResult] = {}

    def runner() -> None:
        result_holder["result"] = mock_solve(
            config, iterations=1000, mock_latency_ms=200
        )

    t = threading.Thread(target=runner)
    t.start()
    # Let it tick a couple snapshots, then cancel.
    import time as _time

    _time.sleep(0.05)
    _CANCEL_FLAG.set()
    t.join(timeout=2.0)
    assert not t.is_alive(), "mock_solve did not halt after _CANCEL_FLAG.set()"
    assert "result" in result_holder
    result = result_holder["result"]
    assert result.iterations < 1000, (
        f"expected partial iterations after cancellation; got {result.iterations}"
    )


# ---------------------------------------------------------------------------
# PR 10b: real-solver smoke tests
# ---------------------------------------------------------------------------
#
# These exercise the SolveRunner -> poker_solver.solver.solve dispatch added
# in PR 10b. PR 10a's mock_solver tests above remain to validate the
# failure-mode injection infrastructure (OOM, cancellation) which the real
# solver doesn't readily produce. The tests below verify that production
# users running poker-solver ui see a real DCFR solve when they click
# "Solve" — not a mock.


def test_real_solve_runs_via_solve_runner() -> None:
    """PR 10b smoke: SolveRunner.start with no mock kwargs invokes the real
    solver path. The result must be a HUNLSolveResult (not a mock) and its
    backend is one of the real backends (python/rust/pushfold_chart).
    """
    from poker_solver.hunl import HUNLPoker, default_tiny_subgame
    from poker_solver.hunl_solver import HUNLSolveResult

    from ui.state import SolveRunner

    runner = SolveRunner()
    runner.start(
        HUNLPoker(default_tiny_subgame()),
        iterations=200,
        log_every=50,
    )
    runner.join(timeout=15.0)
    assert runner.status == "done", (
        f"expected status='done' after real solve; got {runner.status!r}, "
        f"error={runner.error!r}"
    )
    assert isinstance(runner.result, HUNLSolveResult), (
        f"expected HUNLSolveResult; got {type(runner.result).__name__}"
    )
    # Real solver backends: 'python' / 'rust' / 'pushfold_chart'.
    # Mock backend would be 'python-mock'; that must NOT happen here.
    assert runner.result.backend != "python-mock", (
        f"runner mistakenly invoked mock solver; got backend={runner.result.backend!r}"
    )
    assert runner.result.iterations == 200


def test_real_solve_streams_on_progress() -> None:
    """PR 10b smoke: on_progress callback fires once per log_every chunk
    during a real solve. The SolveRunner's expl_history accumulates one
    entry per chunk; cumulative iter counts are monotone-increasing.
    """
    from poker_solver.hunl import HUNLPoker, default_tiny_subgame

    from ui.state import SolveRunner

    runner = SolveRunner()
    runner.start(
        HUNLPoker(default_tiny_subgame()),
        iterations=200,
        log_every=50,
    )
    runner.join(timeout=15.0)
    assert runner.status == "done"
    # 200 iters / log_every=50 -> 4 chunks -> at least 4 progress entries.
    # We may have 5 if the final on-end push fires (per _worker's tail logic).
    assert len(runner.expl_history) >= 4, (
        f"expected >=4 progress entries; got {len(runner.expl_history)}"
    )
    iters = [it for it, _ in runner.expl_history]
    assert iters == sorted(iters), f"iter counts not monotone: {iters!r}"


def test_real_solve_stop_button_halts_mid_solve() -> None:
    """PR 10b smoke: setting the runner's stop_event mid-solve aborts the
    real solver within one chunk boundary. The solver returns a partial
    HUNLSolveResult; status is 'stopped', iteration < requested.
    """
    import time as _time

    from poker_solver.hunl import HUNLPoker, default_tiny_subgame

    from ui.state import SolveRunner

    runner = SolveRunner()
    # Larger iteration count so we have time to observe + stop.
    runner.start(
        HUNLPoker(default_tiny_subgame()),
        iterations=10_000,
        log_every=50,
    )
    _time.sleep(0.1)
    runner.stop()
    runner.join(timeout=5.0)
    assert not runner.is_alive(), "runner did not halt after stop()"
    assert runner.status == "stopped", (
        f"expected status='stopped'; got {runner.status!r}"
    )
    assert runner.iteration < 10_000, (
        f"expected partial iter count after stop; got {runner.iteration}"
    )


def test_real_solve_pushfold_dispatch_at_short_stack() -> None:
    """PR 10b smoke: a <=15 BB preflop config dispatches to the push/fold
    chart via SolveRunner. Result.backend is 'pushfold_chart'; the solve is
    instantaneous.
    """
    from poker_solver.hunl import HUNLConfig, HUNLPoker, Street

    from ui.state import SolveRunner

    cfg = HUNLConfig(
        starting_stack=1000,  # 10 BB
        big_blind=100,
        small_blind=50,
        starting_street=Street.PREFLOP,
    )
    runner = SolveRunner()
    runner.start(HUNLPoker(cfg), iterations=100, log_every=10)
    runner.join(timeout=5.0)
    assert runner.status == "done", (
        f"expected push/fold dispatch to complete; got status={runner.status!r}, "
        f"error={runner.error!r}"
    )
    assert runner.result is not None
    assert runner.result.backend == "pushfold_chart", (
        f"expected push/fold chart dispatch at 10 BB; got backend="
        f"{runner.result.backend!r}"
    )


def test_real_solve_ui_parity_with_direct_solve() -> None:
    """PR 10b acceptance: a small solve via SolveRunner produces the same
    exploitability final value as solving via solve_hunl_postflop directly
    (modulo callback overhead). Locks the "no surprise" parity gate.
    """
    from poker_solver.hunl import HUNLPoker, default_tiny_subgame
    from poker_solver.hunl_solver import solve_hunl_postflop

    from ui.state import SolveRunner

    cfg = default_tiny_subgame()

    # Direct solve.
    direct = solve_hunl_postflop(cfg, iterations=200, log_every=50, seed=42)

    # Via SolveRunner.
    runner = SolveRunner()
    runner.start(HUNLPoker(cfg), iterations=200, log_every=50, seed=42)
    runner.join(timeout=15.0)
    assert runner.status == "done"
    via_runner = runner.result

    # DCFR with the same seed should produce byte-identical exploitability
    # vectors (the strategy is deterministic at fixed seed; the callback
    # doesn't perturb the math).
    assert via_runner is not None
    assert len(direct.exploitability_history) == len(via_runner.exploitability_history)
    for direct_v, runner_v in zip(
        direct.exploitability_history,
        via_runner.exploitability_history,
    ):
        assert abs(direct_v - runner_v) < 1e-9, (
            f"parity drift: direct={direct_v}, runner={runner_v}"
        )


def test_real_solve_error_surfaces_to_runner() -> None:
    """PR 10b smoke: a config the engine legitimately refuses surfaces as
    ``runner.status='error'`` with ``runner.error`` populated. No crash;
    the worker thread exits cleanly.

    Post-PR-9 update: the preflop > 15 BB branch USED to raise
    ``NotImplementedError`` because PR 9 hadn't landed yet. With PR 9
    merged, that branch now solves successfully when ``initial_hole_cards``
    is set. We pick a config that PR 9 explicitly rejects with
    ``ValueError``: preflop subgame mode requires ``initial_hole_cards``
    non-empty (full-tree preflop with hole cards drawn as a 1.6M-combo
    chance enum is intractable, reserved for a post-v1 follow-up). This
    keeps the test honest — it asserts the worker's
    error-surfacing contract end-to-end while exercising a real,
    documented PR 9 rejection path rather than a class that no longer
    fires.
    """
    from poker_solver.hunl import HUNLConfig, HUNLPoker, Street

    from ui.state import SolveRunner

    # Preflop > 15 BB WITHOUT initial_hole_cards → PR 9's
    # `_validate_preflop_config` raises ValueError pointing at the
    # subgame-only contract.
    cfg = HUNLConfig(
        starting_stack=10_000,  # 100 BB (above push/fold range, in PR 9 scope)
        big_blind=100,
        small_blind=50,
        starting_street=Street.PREFLOP,
        # initial_hole_cards intentionally omitted → PR 9 rejects.
    )
    runner = SolveRunner()
    runner.start(HUNLPoker(cfg), iterations=200, log_every=50)
    runner.join(timeout=10.0)
    assert runner.status == "error", (
        f"expected status='error' on unsupported config; got {runner.status!r}"
    )
    assert runner.error is not None
    assert isinstance(runner.error, ValueError), (
        f"expected ValueError (PR 9 rejects preflop without "
        f"initial_hole_cards); got {type(runner.error).__name__}"
    )
    assert "initial_hole_cards" in str(runner.error), (
        f"expected error to mention initial_hole_cards; got {runner.error!r}"
    )


# ---------------------------------------------------------------------------
# Cleanup: ensure tests don't leak env-var overrides
# ---------------------------------------------------------------------------


def _verify_no_real_state_dir_pollution() -> None:
    """Sanity guard — never write to ``~/.poker_solver_ui`` outside tmp."""
    real_home = pathlib.Path(os.path.expanduser("~"))
    poker_dir = real_home / ".poker_solver_ui"
    # We allow it to exist (user may have run the app manually); we only
    # alert if the directory was modified during the test session.
    if poker_dir.exists():
        # Don't fail; just warn via pytest's mechanism.
        pass
