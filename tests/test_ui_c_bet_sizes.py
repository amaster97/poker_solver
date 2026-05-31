"""GUI smoke tests for the C bet-size feature (downstream punch list #1/#2).

Covers the run-panel controls that expose the new ``HUNLConfig`` bet-size
menu fields to the GUI:

1. Per-street opening-bet checkboxes (``{flop,turn,river}-bet-checkbox-*``)
   write ``state.current_spot.{flop,turn,river}_bet_fractions`` and thread
   through ``Spot.to_hunl_config`` into the corresponding
   ``HUNLConfig.{flop,turn,river}_bet_fractions`` field. Un-checking the
   last size for a street resets it to ``None`` (inherit the flat menu).
2. The raise-size input (``raise-size-input``) writes
   ``state.current_spot.raise_size_xs`` (MULTIPLIERS of the bet, NOT % pot)
   and threads through into ``HUNLConfig.raise_size_xs``.

These use the NiceGUI ``User`` fixture pattern from
``tests/test_ui_pr24a.py``. We drive the actual on-change handlers by
setting the marked element's ``.value`` (which fires
``ValueElement._handle_value_change`` -> the registered ``on_change``),
so the test exercises the real wiring, not a state shortcut.
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
    pytest.mark.nicegui_main_file("ui/app.py"),
]


@pytest.fixture
def isolated_state_dir(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[pathlib.Path]:
    """Override HOME so state.json lands in tmp_path; reset the runner.

    Mirrors ``test_ui_pr24a.py:isolated_state_dir``.
    """
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


def _set_marked_value(user: User, marker: str, value: object) -> None:
    """Set the value of a single marked element, firing its on_change.

    Setting ``element.value`` invokes ``_handle_value_change`` which runs
    the registered change handlers — the same path a real user click /
    keystroke takes. We assert exactly one element carries the marker so a
    typo in the production ``.mark(...)`` call surfaces as a test failure
    rather than a silent no-op.
    """
    elements = user.find(marker=marker).elements
    assert len(elements) == 1, f"expected exactly 1 {marker!r}, got {len(elements)}"
    next(iter(elements)).set_value(value)


# ---------------------------------------------------------------------------
# #2: per-street opening-bet checkboxes write the Spot field
# ---------------------------------------------------------------------------


async def test_flop_bet_checkbox_writes_spot_and_config(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Checking a flop opening size writes ``flop_bet_fractions`` + threads
    into ``HUNLConfig.flop_bet_fractions``; the other streets stay ``None``.
    """
    from poker_solver.card import Card
    from ui.state import get_state

    await user.open("/")
    state = get_state()
    # Put a 3-card flop board down so to_hunl_config() builds a valid
    # postflop config (avoids the preflop guardrail).
    state.current_spot.board = [Card(13, 0), Card(7, 1), Card(2, 2)]  # Kc 7d 2h

    # Default: no per-street override anywhere.
    assert state.current_spot.flop_bet_fractions is None
    assert state.current_spot.turn_bet_fractions is None
    assert state.current_spot.river_bet_fractions is None

    # Check the flop 75% box -> flop menu seeds to (0.75,).
    _set_marked_value(user, "flop-bet-checkbox-75", True)
    assert state.current_spot.flop_bet_fractions == (0.75,)
    # Other streets remain inherit-the-flat-menu.
    assert state.current_spot.turn_bet_fractions is None
    assert state.current_spot.river_bet_fractions is None

    # Add the flop 33% box -> sorted (0.33, 0.75).
    _set_marked_value(user, "flop-bet-checkbox-33", True)
    assert state.current_spot.flop_bet_fractions == (0.33, 0.75)

    # The Spot field threads into HUNLConfig faithfully.
    cfg = state.current_spot.to_hunl_config()
    assert cfg.flop_bet_fractions == (0.33, 0.75)
    assert cfg.turn_bet_fractions is None
    assert cfg.river_bet_fractions is None


async def test_unchecking_last_street_size_resets_to_none(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Removing the last checked size for a street resets it to ``None``
    (inherit the flat menu), not an empty tuple.
    """
    from poker_solver.card import Card
    from ui.state import get_state

    await user.open("/")
    state = get_state()
    state.current_spot.board = [Card(13, 0), Card(7, 1), Card(2, 2)]

    _set_marked_value(user, "turn-bet-checkbox-100", True)
    assert state.current_spot.turn_bet_fractions == (1.0,)

    _set_marked_value(user, "turn-bet-checkbox-100", False)
    assert state.current_spot.turn_bet_fractions is None
    # And the config inherits the flat menu (None) for the turn.
    assert state.current_spot.to_hunl_config().turn_bet_fractions is None


# ---------------------------------------------------------------------------
# #2: raise-size input writes raise_size_xs (multipliers, not % pot)
# ---------------------------------------------------------------------------


async def test_raise_size_input_writes_spot_and_config(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Typing raise multipliers writes ``raise_size_xs`` + threads into
    ``HUNLConfig.raise_size_xs``. Order is preserved; dupes dropped.
    """
    from poker_solver.card import Card
    from ui.state import get_state

    await user.open("/")
    state = get_state()
    state.current_spot.board = [Card(13, 0), Card(7, 1), Card(2, 2)]

    # Default raise menu is (3.0,).
    assert state.current_spot.raise_size_xs == (3.0,)

    _set_marked_value(user, "raise-size-input", "2.5, 3, 2.5")
    # Dedupe preserves first-seen order.
    assert state.current_spot.raise_size_xs == (2.5, 3.0)

    cfg = state.current_spot.to_hunl_config()
    assert cfg.raise_size_xs == (2.5, 3.0)


async def test_raise_size_input_ignores_empty_input(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Empty / all-non-positive raise input leaves the existing value
    untouched (the engine requires a non-empty raise menu)."""
    from ui.state import get_state

    await user.open("/")
    state = get_state()
    assert state.current_spot.raise_size_xs == (3.0,)

    _set_marked_value(user, "raise-size-input", "   ")
    assert state.current_spot.raise_size_xs == (3.0,)

    _set_marked_value(user, "raise-size-input", "0, -1")
    assert state.current_spot.raise_size_xs == (3.0,)


# ---------------------------------------------------------------------------
# Persistence round-trip through the library (punch-list #9 sanity)
# ---------------------------------------------------------------------------


def test_library_roundtrip_preserves_menu_fields_and_distinguishes_ids() -> None:
    """Two spots differing ONLY in per-street / raise menus get distinct
    ids + cache keys, and the menu fields survive a dict round-trip.

    This is a non-UI sanity check for punch-list #9 living alongside the
    GUI tests (no ``user`` fixture so it runs fast).
    """
    from poker_solver.card import Card
    from poker_solver.hunl import HUNLConfig, Street
    from poker_solver.library import (
        SpotDescription,
        _bet_menu_hash,
        _dict_to_spot,
        _spot_to_dict,
    )

    board = (Card(13, 0), Card(7, 1), Card(2, 2))  # Ks 7h 2d
    base = HUNLConfig(
        starting_stack=10_000,
        small_blind=50,
        big_blind=100,
        starting_street=Street.FLOP,
        initial_board=board,
        initial_pot=200,
        initial_contributions=(100, 100),
        abstraction=None,
    )
    with_flop = HUNLConfig(
        starting_stack=10_000,
        small_blind=50,
        big_blind=100,
        starting_street=Street.FLOP,
        initial_board=board,
        initial_pot=200,
        initial_contributions=(100, 100),
        flop_bet_fractions=(0.5,),
        raise_size_xs=(2.5,),
        abstraction=None,
    )
    s_base = SpotDescription(config=base)
    s_flop = SpotDescription(config=with_flop)

    # Distinct ids (spot_id formula now hashes the menu fields).
    assert s_base.spot_id() != s_flop.spot_id()
    # Distinct cache keys.
    assert _bet_menu_hash(base) != _bet_menu_hash(with_flop)

    # Dict round-trip preserves the menu fields.
    rt = _dict_to_spot(_spot_to_dict(s_flop))
    assert rt.config.flop_bet_fractions == (0.5,)
    assert rt.config.turn_bet_fractions is None
    assert rt.config.river_bet_fractions is None
    assert rt.config.raise_size_xs == (2.5,)

    # Old (schema 1) payload without the keys defaults cleanly.
    old_payload = _spot_to_dict(s_base)
    for k in (
        "flop_bet_fractions",
        "turn_bet_fractions",
        "river_bet_fractions",
        "raise_size_xs",
    ):
        old_payload["config"].pop(k, None)
    rt_old = _dict_to_spot(old_payload)
    assert rt_old.config.flop_bet_fractions is None
    assert rt_old.config.raise_size_xs == (3.0,)
