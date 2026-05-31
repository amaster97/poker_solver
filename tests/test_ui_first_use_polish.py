"""First-use UI polish tests (feat/ui-ux-polish).

Covers the bounded first-use polish pass:

1. **Range-matrix empty state** — before any solve has published a
   strategy, the matrix shows a friendly "press Solve" hint
   (``matrix-empty-hint``) instead of an unexplained, color-free grid.
   The hint disappears once a strategy is present.
2. **Library filter discoverability** — the library dialog's Filter
   input carries a placeholder + tooltip explaining the street /
   label-substring syntax.
3. **Friendly error messaging** — the chained-tab flop-solve error and
   the library list/delete failures no longer dump a raw exception
   (``{exc}``) at the user; they show a plain-language line and log the
   detail instead.

Pattern follows ``tests/test_ui_pr24b.py``: NiceGUI ``User`` fixture for
in-process render checks; source-level ``inspect.getsource`` assertions
for the friendly-error strings (same approach the PR 24b tier-tooltip
smoke uses).
"""

from __future__ import annotations

import importlib
import inspect
import pathlib
from collections.abc import Iterator
from types import SimpleNamespace

import pytest

pytest.importorskip("nicegui")

# ruff: noqa: E402, I001  (post-importorskip imports must follow the skip)
from nicegui.testing import User

pytest_plugins = [
    "nicegui.testing.general_fixtures",
    "nicegui.testing.user_plugin",
]

pytestmark = [
    pytest.mark.ui,
    pytest.mark.nicegui_main_file("ui/app.py"),
]


@pytest.fixture
def isolated_state_dir(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[pathlib.Path]:
    """Override HOME so state.json + user charts dir land in tmp_path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("POKER_SOLVER_UI_STATE_DIR", str(tmp_path / ".poker_solver_ui"))
    from ui.state import get_state, reset_state_for_testing

    reset_state_for_testing()
    try:
        current = get_state()
        if current.runner.is_alive():
            current.runner.stop()
            current.runner.join(timeout=3.0)
        current.runner._stop_event.clear()
        current.runner._pause_event.clear()
    except Exception:  # noqa: BLE001
        pass
    yield tmp_path


# ---------------------------------------------------------------------------
# 1. Range-matrix empty state
# ---------------------------------------------------------------------------


def test_has_solved_strategy_false_without_result() -> None:
    """``_has_solved_strategy`` is False when no solve has published output.

    Pure-logic check on a duck-typed state (no runner / no solve), mirroring
    the no-result path the empty-state banner guards.
    """
    import ui.views.range_matrix as rm

    state = SimpleNamespace(
        current_spot=SimpleNamespace(
            rvr_mode=False, ranges=(None, None), hero_player=0
        ),
        current_solve=None,
        runner=None,
    )
    assert rm._has_solved_strategy(state) is False


@pytest.mark.usefixtures("isolated_state_dir")
async def test_matrix_shows_empty_hint_before_solve(user: User) -> None:
    """On first page open (no solve), the matrix shows the Solve hint."""
    await user.open("/")
    hint = user.find(marker="matrix-empty-hint").elements
    assert hint, "matrix should show the 'press Solve' empty-state hint"
    # The hint must point the user at the Solve action.
    text = next(iter(hint)).text
    assert "Solve" in text
    assert "No strategy yet" in text


async def test_matrix_hint_clears_after_solve(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """The empty-state hint disappears once a strategy is published.

    Loads the deterministic tiny river subgame preset and solves it; after
    the solve completes the matrix repaints with a strategy, so the
    ``matrix-empty-hint`` banner is gone.
    """
    from ui.state import get_state

    await user.open("/")
    # Hint present before solving.
    assert user.find(marker="matrix-empty-hint").elements

    user.find(marker="preset-river-tiny-subgame").click()
    user.find(marker="solve-button").click()

    runner = get_state().runner
    runner.join(timeout=30.0)
    assert runner.status in ("done", "stopped"), f"solve status={runner.status!r}"

    # Re-open to force a fresh matrix render against the finished result.
    await user.open("/")
    # ``User.find`` raises AssertionError when no element matches, so the
    # hint being absent (cleared) surfaces as that error — assert it.
    with pytest.raises(AssertionError):
        user.find(marker="matrix-empty-hint")


# ---------------------------------------------------------------------------
# 2. Library filter discoverability
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("isolated_state_dir")
async def test_library_filter_has_placeholder_and_tooltip(user: User) -> None:
    """The library Filter input is discoverable (placeholder + tooltip)."""
    await user.open("/")
    user.find(marker="library-header-button").click()
    await user.should_see(marker="library-dialog")

    filt = next(iter(user.find(marker="library-filter-input").elements))
    placeholder = filt._props.get("placeholder", "")
    assert "street" in placeholder.lower()
    assert "label" in placeholder.lower()


def test_library_filter_tooltip_in_source() -> None:
    """The library filter help text names the street + label-substring modes."""
    lib = importlib.import_module("ui.views.library_browser")
    src = inspect.getsource(lib.render)
    assert ".tooltip(" in src
    assert "flop, turn, river" in src
    assert "label" in src.lower()


# ---------------------------------------------------------------------------
# 3. Friendly error messaging (no raw {exc} dumped at the user)
# ---------------------------------------------------------------------------


def test_chained_flop_error_is_friendly() -> None:
    """The chained flop-solve RuntimeError/ImportError shows a plain message.

    Asserts the raw ``f"Flop solve error: {exc}"`` dump is gone and replaced
    with a human-readable line; the detail still goes to the logger.
    """
    chained = importlib.import_module("ui.views.chained_tab")
    src = inspect.getsource(chained)
    assert "Flop solve error: {exc}" not in src
    assert "Couldn't solve this flop subgame" in src
    # Detail is still logged for debugging.
    assert 'logger.exception("chained flop solve raised' in src


def test_library_errors_are_friendly() -> None:
    """Library list/delete failures show a plain message, not a raw {exc}."""
    lib = importlib.import_module("ui.views.library_browser")
    src = inspect.getsource(lib.render)
    assert "Library unavailable: {exc}" not in src
    assert "Delete failed: {exc}" not in src
    assert "Couldn't open the solve library" in src
    assert "Couldn't delete that saved spot" in src
    # Both failures are logged for debugging.
    assert 'logger.exception("library_browser: list failed")' in src
    assert 'logger.exception("library_browser: delete failed")' in src
