"""Regression test for the G3 example-spot refresh bug.

Bug (G3)
--------
Clicking an example-spot button (e.g. "FLOP T87S 100BB") ran
``spot_input._on_load_preset`` and correctly updated
``state.current_spot.ranges`` (P0=226 combos / P1=184 for ``flop_t87s_100bb``),
BUT the visible panes kept their stale pre-load look: the right range editor's
fraction stayed "1326 / 1326 (100.0%)" and the left range matrix kept its
full-range appearance.

Root cause
----------
``_trigger_spot_views_refresh`` invoked each ``@ui.refreshable`` view's
``refresh()`` hook but never awaited the returned ``AwaitableResponse``. An
un-awaited ``refresh()`` defers the body re-execution to a fire-and-forget
background task, so inside the synchronous click handler the re-render never
ran before the handler returned — the panes stayed stale. The fix makes
``_on_load_preset`` / ``_trigger_spot_views_refresh`` async and **awaits** each
hook so the re-render completes inline.

What this test asserts
----------------------
After clicking the ``flop_t87s_100bb`` preset (and crucially WITHOUT any
``asyncio.sleep`` to let a deferred task run), the P0 range-string textarea
re-renders to the loaded ~226-combo range — NOT the 1326-combo default and NOT
a 1-combo river subgame. On the pre-fix (un-awaited) code this read 1326,
because the deferred refresh hadn't run yet; the await fix makes it 226 inline.
"""

from __future__ import annotations

import pathlib
from collections.abc import Iterator

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
    # The ``@ui.page('/')`` builder lives in ui/app.py.
    pytest.mark.nicegui_main_file("ui/app.py"),
]


@pytest.fixture
def isolated_state_dir(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[pathlib.Path]:
    """Redirect state.json into a tmp dir (mirror of test_ui_smoke.py).

    Also resets the module-level ``_state_singleton`` so each test starts from a
    fresh default spot. Without this the global singleton leaks across tests
    (and across test FILES): a preceding preset-load test would leave the
    singleton at the loaded flop range, so this file's first test would see
    226 combos instead of the expected 1326-combo default. Mirrors the
    ``reset_state_for_testing()`` call in ``test_ui_pr24a.py``'s fixture.
    """
    from ui.state import reset_state_for_testing

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("POKER_SOLVER_UI_STATE_DIR", str(tmp_path / ".poker_solver_ui"))
    reset_state_for_testing()
    yield tmp_path


def _combos_in(range_str: str) -> int:
    """Count nonzero-frequency combos in a PIO-style range string."""
    from ui.state import RangeWithFreqs

    rw = RangeWithFreqs.from_string(range_str)
    return sum(1 for c in rw.base_range.combos if rw.frequency_of(c) > 0.0)


def _p0_textarea_combos(user: User) -> int:
    """Parse the rendered P0 range-string textarea -> nonzero combo count."""
    elements = list(user.find(marker="range-string-input-p0").elements)
    assert elements, "no range-string-input-p0 textarea rendered"
    value = getattr(elements[0], "value", None)
    return _combos_in(str(value or ""))


async def test_loading_flop_preset_repaints_range_editor_inline(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Loading ``flop_t87s_100bb`` repaints the range editor to ~226 combos.

    This is the crux of the G3 fix. The assertion runs immediately after the
    click with NO event-loop yield: on the buggy (fire-and-forget) code the
    textarea still read the 1326-combo default; the awaited refresh makes it
    re-render to the loaded 226-combo range inline.
    """
    from ui.state import get_state

    await user.open("/")

    # Sanity: the default preflop spot starts at the full 1326-combo range.
    before_state = get_state().current_spot
    n0_before = sum(
        1
        for c in before_state.ranges[0].base_range.combos
        if before_state.ranges[0].frequency_of(c) > 0.0
    )
    assert n0_before == 1326, (
        f"expected the default spot to start full (1326 combos); got {n0_before}"
    )
    assert _p0_textarea_combos(user) == 1326, (
        "P0 textarea did not start at the full default range"
    )

    # Drive the (now-async) preset-load handler exactly as the button's
    # ``on_click`` does, awaiting it to completion within the page's client
    # context. Awaiting runs the production coroutine end-to-end: it mutates
    # ``state.current_spot`` AND awaits ``_trigger_spot_views_refresh``, whose
    # awaited ``refresh()`` re-renders the panes INLINE. On the buggy code
    # (sync handler + fire-and-forget refresh) the re-render was deferred to a
    # background task, so the rendered editor stayed stale at this point.
    from ui.views.spot_input import _on_load_preset

    with user.client:
        await _on_load_preset(get_state(), "flop_t87s_100bb")

    # The DATA must have updated to the loaded range-vs-range scenario.
    after_state = get_state().current_spot
    n0_after = sum(
        1
        for c in after_state.ranges[0].base_range.combos
        if after_state.ranges[0].frequency_of(c) > 0.0
    )
    assert n0_after == 226, (
        f"loading flop_t87s_100bb should set P0 to 226 combos; got {n0_after}"
    )

    # The crux: the RENDERED range editor must reflect the new range without
    # waiting for a deferred task. 226 = pass; 1326 = the G3 staleness bug;
    # 1 = a stale concrete river subgame.
    rendered = _p0_textarea_combos(user)
    assert rendered == 226, (
        "G3 regression: the P0 range editor did not repaint to the loaded "
        f"226-combo range after the preset click (rendered {rendered} combos). "
        "1326 means the un-awaited fire-and-forget refresh never ran inline; "
        "the awaited refresh hook should re-render the editor before the "
        "handler returns."
    )


async def test_reset_spot_clears_stale_solve_result(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """N2-RESET: RESET SPOT invalidates the prior solve's result + status.

    Before the fix, ``_on_reset`` set ``state.current_spot = Spot()`` but never
    touched the runner, so a completed solve's ``status="done"`` + truthy
    ``result`` lingered: the header chip (which reads ``runner.status`` and
    ``_has_result(runner)``) kept showing "Done" for a fresh, unsolved spot.
    ``runner.clear_results()`` now drops the result holders and resets status.
    """
    from ui.state import get_state
    from ui.views.spot_input import _on_reset

    await user.open("/")
    state = get_state()

    # Simulate a completed solve: terminal status + a truthy result payload.
    state.runner.status = "done"
    state.runner.result = object()  # truthy sentinel — _has_result() reads it
    assert state.runner.status == "done"
    assert state.runner.result is not None

    with user.client:
        await _on_reset(state)

    assert state.runner.status == "idle", (
        f"RESET SPOT should reset runner.status to 'idle'; got {state.runner.status!r}"
    )
    assert state.runner.result is None, (
        "RESET SPOT should clear the stale solve result so the header chip "
        "does not show a leftover 'Done' for the fresh unsolved spot"
    )


async def test_load_preset_clears_stale_solve_result(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """N2-RESET: loading a new preset invalidates the prior solve.

    Same desync as RESET SPOT but via the (async) ``_on_load_preset`` path: a
    freshly-loaded example spot is unsolved, so the header chip must not keep
    the previous solve's "Done"/result. Also a guard that the G3 async fix and
    the new ``clear_results`` call coexist on this code path.
    """
    from ui.state import get_state
    from ui.views.spot_input import _on_load_preset

    await user.open("/")
    state = get_state()

    state.runner.status = "done"
    state.runner.result = object()  # truthy sentinel

    with user.client:
        await _on_load_preset(state, "flop_t87s_100bb")

    assert state.runner.status == "idle", (
        f"loading a preset should reset runner.status to 'idle'; got "
        f"{state.runner.status!r}"
    )
    assert state.runner.result is None, (
        "loading a preset should clear the stale prior solve result"
    )
    # The G3 fix must still hold: the data updated to the loaded RvR scenario.
    after = state.current_spot
    n0 = sum(
        1
        for c in after.ranges[0].base_range.combos
        if after.ranges[0].frequency_of(c) > 0.0
    )
    assert n0 == 226, (
        f"G3 regression: loading flop_t87s_100bb should set P0 to 226 combos; got {n0}"
    )


async def test_load_preset_emits_toast_without_slot_teardown_error(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """G3b: ``_on_load_preset`` must finish cleanly and surface the toast.

    Regression: the trailing ``ui.notify("Loaded preset: ...")`` used to run
    AFTER ``await _trigger_spot_views_refresh(state)``. That refresh re-renders
    the ``@ui.refreshable`` bodies, tearing down + recreating their slots; by the
    time the notify ran, ``context.client`` resolved through a deleted slot and
    raised ``RuntimeError: The parent element this slot belongs to has been
    deleted.`` (the load itself succeeded; only the toast errored). The fix emits
    the toast BEFORE the refresh, while the click handler's slot is still valid.

    This drives the production coroutine end-to-end inside the page's client
    context and asserts (a) it does not raise, and (b) the "Loaded preset" toast
    was actually emitted.
    """
    from ui.state import get_state
    from ui.views.spot_input import _on_load_preset

    await user.open("/")
    state = get_state()

    # No try/except: the whole point is that the coroutine completes without the
    # RuntimeError. ``nicegui.testing.User`` patches ``ui.notify`` to record
    # messages on ``user.notify`` so we can assert the toast fired.
    with user.client:
        await _on_load_preset(state, "flop_t87s_100bb")

    assert user.notify.contains("Loaded preset: flop_t87s_100bb"), (
        "G3b regression: the 'Loaded preset' toast was not emitted on the "
        f"preset-load path (captured messages: {user.notify.messages!r})"
    )


async def test_board_picker_label_matches_placed_card(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """P1: the board-picker button labeled e.g. "As" must place the actual
    Ace of spades — not its rank-mirror.

    Bug (P1)
    --------
    ``_render_board_section`` iterated ``RANKS`` (ascending "23456789TJQKA")
    and built ``rank_value = 14 - rank_idx`` + ``card = Card(rank_value, ...)``
    but labeled the button with the iteration's ``rank_char`` (= RANKS[rank_idx]),
    the MIRROR of ``rank_value``. So the button labeled "As" (rank_idx 12) built
    ``Card(2, spade)`` and placed a "2s"; the ``board-picker-cell-{label}``
    marker was wrong too. The fix derives the label from the card's own rank
    (``RANKS[rank_value - 2]``), so label == ``str(card)`` for every cell.

    This drives the production click handler via the cell marker and asserts the
    card whose label is clicked is the card that lands on the board.
    """
    from poker_solver.card import Card
    from ui.state import get_state

    await user.open("/")
    state = get_state()
    state.current_spot.board = []

    # Click the cells labeled As, Ks, 2s and assert each places its OWN card.
    expected = {
        "As": Card(14, 0),  # spades = suit index 0 per SUITS = "shdc"
        "Ks": Card(13, 0),
        "2s": Card(2, 0),
    }
    for label, card in expected.items():
        user.find(marker=f"board-picker-cell-{label}").click()
        assert card in state.current_spot.board, (
            f"P1 regression: clicking the board cell labeled {label!r} should "
            f"place {card!r} (str={card}); board now {state.current_spot.board!r}. "
            "A mismatch means the label is the rank-mirror of the placed card."
        )
        # And the label must equal the card's own string representation.
        assert str(card) == label, (
            f"P1 invariant: marker label {label!r} must equal str(card) "
            f"({str(card)!r}) for the cell"
        )
