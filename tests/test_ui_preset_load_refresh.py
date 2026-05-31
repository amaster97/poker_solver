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


def _board_chip_labels(user: User) -> list[str]:
    """Return the board-chip strip's rendered card aria-labels (in order).

    The chip strip is the ``ui.row().classes(... 'min-h-8')`` inside
    ``_render_board_section``; each selected card is a ``ui.html(card_html(c))``
    whose span carries ``aria-label='<canonical 2-char code>'`` (e.g. ``As``).
    We read the labels off the spans that live inside a chip wrapper row
    (``bg-gray-100`` border chip) so we count ONLY the chip strip — not the
    header spot-label, which also renders ``card_html`` spans.
    """
    import re

    labels: list[str] = []
    for el in user.client.elements.values():
        content = getattr(el, "content", None)
        if not content or "ps-card" not in str(content):
            continue
        # Only count spans whose grand-parent chip wrapper is the bordered
        # ``bg-gray-100`` chip (the strip), excluding the header spot-label.
        parent = getattr(el, "parent_slot", None)
        wrapper = getattr(parent, "parent", None) if parent else None
        wrapper_classes = getattr(wrapper, "_classes", None) or []
        if "bg-gray-100" not in wrapper_classes:
            continue
        m = re.search(r"aria-label='([^']+)'", str(content))
        if m:
            labels.append(m.group(1))
    return labels


def _board_close_buttons(user: User) -> int:
    """Count [x] close buttons inside the board-chip strip wrappers."""
    n = 0
    for el in user.client.elements.values():
        # Close buttons are ``ui.button(icon='close')`` inside a ``bg-gray-100``
        # chip wrapper; identify by the wrapper class on the button's parent.
        parent = getattr(el, "parent_slot", None)
        wrapper = getattr(parent, "parent", None) if parent else None
        wrapper_classes = getattr(wrapper, "_classes", None) or []
        if "bg-gray-100" not in wrapper_classes:
            continue
        props = getattr(el, "_props", {}) or {}
        if props.get("icon") == "close":
            n += 1
    return n


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


async def test_board_chip_strip_repaints_on_preset_load_and_reset(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Board-chip refresh: the selected-card chip strip repaints on a preset
    load (shows ALL 5 river board cards) and clears on a RESET.

    Bug
    ---
    ``_render_board_section`` built the chip strip imperatively via a captured
    ``_redraw_chips()`` closure (``chip_row.clear()`` + ``with chip_row:``). It
    rendered correctly at page build, but after loading an example preset the
    strip was EMPTY: the preset/reset button's repaint goes through a
    fire-and-forget ``background_tasks.create(_trigger_spot_views_refresh(...))``,
    and the deferred re-render did not reliably repopulate the imperatively-built
    strip — even though ``state.current_spot.board`` (and the declaratively-bound
    range textarea) had updated. RESET "clearing" only looked correct because an
    empty strip is what a clear should produce.

    Fix
    ---
    The chip strip is rendered DECLARATIVELY inline in ``_render_board_section``
    (part of the ``@ui.refreshable`` body), so it repaints deterministically on
    every ``_spot_input_body.refresh()`` — the same body re-execution that
    repaints every other field.

    This drives the real (awaited) ``_on_load_preset`` / ``_on_reset`` handlers
    and asserts the chip strip shows all 5 board cards
    (As, 7c, 2d, Kh, 5s) after load and clears to 0 after reset. It also locks
    the no-dropped-card invariant: the heart (Kh) must be present (a probe
    suggested a card might be dropped).
    """
    from ui.state import get_state
    from ui.views.spot_input import _on_load_preset, _on_reset

    await user.open("/")

    # At build the default spot is preflop (empty board) -> 0 chips.
    with user.client:
        assert _board_chip_labels(user) == [], (
            "default preflop spot should render an empty board-chip strip"
        )

        # Load the river preset (board As 7c 2d Kh 5s) via the real handler.
        await _on_load_preset(get_state(), "river_tiny_subgame")

        # Sanity: the underlying board data is the full 5-card river.
        board = [str(c) for c in get_state().current_spot.board]
        assert board == ["As", "7c", "2d", "Kh", "5s"], (
            f"river_tiny_subgame board should be the 5-card river; got {board}"
        )

        labels = _board_chip_labels(user)
        # All 5 cards render as chips (no dropped card — Kh present).
        assert labels == ["As", "7c", "2d", "Kh", "5s"], (
            "board-chip strip did not repaint to all 5 river cards after the "
            f"preset load (rendered chips: {labels!r}). An empty list is the "
            "original bug (fire-and-forget refresh never repopulated the "
            "imperatively-built strip); a 4-element list with 'Kh' missing "
            "would be a dropped-card off-by-one."
        )
        assert "Kh" in labels, "the heart Kh must not be dropped from the strip"

        # Each chip carries its [x] close button (affordance intact).
        assert _board_close_buttons(user) == 5, (
            "each of the 5 board chips should carry a close [x] button; got "
            f"{_board_close_buttons(user)}"
        )

        # RESET clears the board -> strip empties to 0 chips.
        await _on_reset(get_state())
        assert get_state().current_spot.board == [], (
            "RESET should clear the board"
        )
        cleared = _board_chip_labels(user)
        assert cleared == [], (
            f"board-chip strip should clear to 0 chips after RESET; got {cleared!r}"
        )
        assert _board_close_buttons(user) == 0, (
            "no close buttons should remain after RESET clears the board"
        )


def _count_ui_timers(user: User) -> int:
    """Count live ``ui.timer`` ELEMENTS on the page.

    The live-refresh fix schedules the spot-views repaint via
    ``ui.timer(..., once=True)`` (an *element* timer owned by the client and
    run inside its slot context). The pre-fix code scheduled the repaint via a
    contextless, detached ``background_tasks.create`` task, which creates NO
    element. So a ``ui.timer`` appearing after a preset/reset click is the
    structural signature of the slot-context scheduler — and its absence is the
    pre-fix fire-and-forget path that left the views stale live.
    """
    from nicegui.elements.timer import Timer as _UITimer

    return sum(1 for el in user.client.elements.values() if isinstance(el, _UITimer))


async def test_live_preset_button_repaints_spot_views(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Live-path regression: clicking the EXAMPLE-SPOT button repaints the
    range editor AND the board-chip strip.

    Gap this closes
    ---------------
    The other tests in this file drive ``await _on_load_preset(...)`` /
    ``await _on_reset(...)`` DIRECTLY (already awaited), so they never exercise
    the actual ``on_click`` wiring: a SYNCHRONOUS handler that runs the
    click-time mutations inline and then SCHEDULES the repaint. That gap hid a
    regression where the scheduled repaint went through a contextless detached
    ``background_tasks.create(...)`` task, which did not re-execute the
    ``@ui.refreshable`` bodies in the LIVE client context — so live the range
    matrix kept its old range and the board chip strip stayed empty even though
    ``state.current_spot`` had updated.

    The fix schedules the repaint via ``ui.timer(..., once=True)``: the element
    timer runs its (awaited) refresh callback INSIDE the client/slot context
    and only after ``client.connected()``, so the refreshable bodies re-execute
    against the live client.

    This test drives the real BUTTON ``on_click`` (marker
    ``preset-flop-t87s-100bb``), pumps the event loop past the timer interval,
    and asserts:

      1. (structural) the click scheduled the repaint via a ``ui.timer``
         element — the slot-context mechanism. On the pre-fix fire-and-forget
         path NO timer is created, so this assertion FAILS pre-fix.
      2. (behavioral) the P0 range editor repainted to the loaded ~226-combo
         range — NOT the stale 1326-combo default.
      3. (behavioral) the board-chip strip repainted to the loaded flop.
    """
    import asyncio

    from ui.state import get_state

    await user.open("/")

    # Baseline: full preflop default — empty board, 1326-combo P0 range.
    assert _p0_textarea_combos(user) == 1326, (
        "P0 textarea did not start at the full default range"
    )
    assert _board_chip_labels(user) == [], (
        "default preflop spot should render an empty board-chip strip"
    )

    timers_before = _count_ui_timers(user)

    # Click the ACTUAL example-spot button. Its ``on_click`` is the production
    # sync handler: inline mutations + ``_schedule_spot_views_refresh``.
    user.find(marker="preset-flop-t87s-100bb").click()

    # Structural: the sync handler scheduled the repaint through a ui.timer
    # (slot-context) — NOT a contextless detached background task. This is the
    # mechanism that repaints live; its presence is what distinguishes the fix
    # from the pre-fix fire-and-forget path (which creates no element).
    timers_after = _count_ui_timers(user)
    assert timers_after == timers_before + 1, (
        "live-refresh regression: clicking the preset button must schedule the "
        "spot-views repaint via a slot-context ui.timer "
        f"(timers {timers_before} -> {timers_after}); a contextless "
        "background_tasks.create (delta 0) is the pre-fix fire-and-forget path "
        "that left the matrix + board chips stale on the live client."
    )

    # Mutations already committed inline at click time.
    after = get_state().current_spot
    n0 = sum(
        1
        for c in after.ranges[0].base_range.combos
        if after.ranges[0].frequency_of(c) > 0.0
    )
    assert n0 == 226, (
        f"clicking flop_t87s_100bb should set P0 to 226 combos inline; got {n0}"
    )

    # Pump the loop past the timer's 0.01s interval so the once-timer fires and
    # awaits the refresh, re-executing the refreshable bodies in the client
    # context (the live repaint).
    for _ in range(6):
        await asyncio.sleep(0.02)

    # Behavioral: the rendered range editor repainted to the loaded range.
    rendered = _p0_textarea_combos(user)
    assert rendered == 226, (
        "live-refresh regression: the P0 range editor did not repaint to the "
        f"loaded 226-combo range after the BUTTON click (rendered {rendered}). "
        "1326 means the scheduled refresh never re-executed the refreshable "
        "body in the live client context."
    )

    # Behavioral: the board-chip strip repainted to the loaded flop board.
    board = [str(c) for c in after.board]
    chips = _board_chip_labels(user)
    assert chips == board, (
        "live-refresh regression: the board-chip strip did not repaint to the "
        f"loaded board {board!r} after the BUTTON click (rendered {chips!r}). "
        "An empty strip is the pre-fix symptom (the scheduled repaint never "
        "re-ran the declarative chip strip in the live client context)."
    )
    assert chips, "loaded flop preset should render a non-empty board-chip strip"


async def test_live_reset_button_repaints_spot_views(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Live-path regression for RESET SPOT: the BUTTON click clears the board
    chip strip and repaints the range editor to the full default.

    Same gap as the preset-button test: the existing reset test awaits
    ``_on_reset`` directly and never exercises the sync ``on_click`` +
    scheduled-repaint wiring. This drives the real ``reset-spot-button``
    ``on_click`` after first loading a non-default spot, then asserts the views
    repaint back to defaults (empty board, full 1326-combo range) via the
    slot-context ``ui.timer`` scheduler.
    """
    import asyncio

    from ui.state import get_state
    from ui.views.spot_input import _on_load_preset

    await user.open("/")

    # Seed a loaded postflop spot so RESET has something visible to clear.
    with user.client:
        await _on_load_preset(get_state(), "flop_t87s_100bb")
    # Pump so the seed load's repaint settles.
    for _ in range(4):
        await asyncio.sleep(0.02)
    assert _board_chip_labels(user), "seed preset should render board chips"

    timers_before = _count_ui_timers(user)

    # Click the ACTUAL reset button (sync handler + scheduled repaint).
    user.find(marker="reset-spot-button").click()

    timers_after = _count_ui_timers(user)
    assert timers_after == timers_before + 1, (
        "live-refresh regression: RESET SPOT must schedule the repaint via a "
        f"slot-context ui.timer (timers {timers_before} -> {timers_after}); "
        "delta 0 is the pre-fix contextless background-task path."
    )

    # Mutation committed inline: board cleared, P0 back to the full default.
    after = get_state().current_spot
    assert after.board == [], "RESET should clear the board inline at click time"

    for _ in range(6):
        await asyncio.sleep(0.02)

    assert _board_chip_labels(user) == [], (
        "live-refresh regression: the board-chip strip did not clear after the "
        f"RESET button click (rendered {_board_chip_labels(user)!r})."
    )
    rendered = _p0_textarea_combos(user)
    assert rendered == 1326, (
        "live-refresh regression: the P0 range editor did not repaint to the "
        f"full 1326-combo default after the RESET button click (rendered "
        f"{rendered})."
    )
