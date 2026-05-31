"""Verification test for the header AUTO / LIGHT / DARK theme toggle.

Context
-------
The toggle (``_build_theme_toggle`` in ``ui/app.py``, marker
``"theme-toggle"``) was fixed to flip Quasar live via
``run_javascript("Quasar.Dark.set(...)")`` because, under NiceGUI 3.x, a
fresh ``ui.dark_mode()`` created inside an event handler does not reliably
broadcast to the client — so the theme only ever applied on page load via
the persisted pref.

This test proves the fix end-to-end: that the server-side ``on_change``
handler (``_on_change``) actually RUNS when the toggle changes, by asserting
the observable side effects of that handler:

  1. ``get_state().prefs.dark_mode`` updates to ``"light"`` / ``"dark"``
     (the handler's first action).
  2. The handler issues the live ``Quasar.Dark.set(<js>)`` call (the actual
     theme-flip side effect that the fix added).

Why a ``nicegui.testing.User`` test (and not browser automation)
----------------------------------------------------------------
Synthetic browser clicks do NOT fire NiceGUI's server-side ``on_change``
for a ``ui.toggle``: ``UserInteraction.click()`` has explicit branches for
select / radio / checkbox / switch / tab / tree / link, but **none for
toggle**, so a click only dispatches a DOM ``click`` event — which the
toggle ignores (it changes on ``update:model-value``, not ``click``).

The faithful path is to fire the exact event the browser emits. A
``ui.toggle`` (Quasar ``q-btn-toggle``) emits ``update:modelValue`` carrying
the **integer index** of the chosen option; NiceGUI's
``Toggle._event_args_to_value`` maps that index back to the option value
(``self._values[e.args]``). Triggering ``update:modelValue`` with the option
index therefore exercises the real client→server value-change pipeline
(``handle_change`` → ``set_value`` → ``_handle_value_change`` → the
registered ``on_change`` handler).

Value-equality gotcha
---------------------
NiceGUI only fires the change handler when the value actually CHANGES (the
bindable-property setter short-circuits a no-op assignment). The AppState
singleton + persisted ``state.json`` can leave the toggle already sitting on
the value we want to set, which would silently no-op the handler. So each
test first drives the toggle to a known *different* baseline before
triggering the value under test.
"""

from __future__ import annotations

import pathlib
from collections.abc import Iterator
from typing import Any

import pytest

pytest.importorskip("nicegui")

# ruff: noqa: E402, I001  (post-importorskip imports must follow the skip)
from nicegui import ui
from nicegui.testing import User

pytest_plugins = [
    "nicegui.testing.general_fixtures",
    "nicegui.testing.user_plugin",
]

pytestmark = [
    pytest.mark.ui,
    # NiceGUI's User fixture needs to know which file registers the
    # ``@ui.page('/')`` builder; ``_build_theme_toggle`` lives in ui/app.py.
    pytest.mark.nicegui_main_file("ui/app.py"),
]

_THEME_OPTIONS = ["auto", "light", "dark"]


@pytest.fixture
def isolated_state_dir(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[pathlib.Path]:
    """Redirect state.json into a tmp dir (mirror of test_ui_smoke.py).

    Keeps the test from reading/writing the developer's real
    ``~/.poker_solver_ui/state.json`` when the handler calls ``save_state()``.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("POKER_SOLVER_UI_STATE_DIR", str(tmp_path / ".poker_solver_ui"))
    yield tmp_path


def _theme_toggle(user: User) -> Any:
    """Return the single header theme-toggle element."""
    elements = list(user.find(marker="theme-toggle").elements)
    assert len(elements) == 1, (
        f"expected exactly one 'theme-toggle' element; got {len(elements)}"
    )
    toggle = elements[0]
    assert list(toggle.options) == _THEME_OPTIONS, (
        f"theme-toggle options changed unexpectedly: {list(toggle.options)!r}"
    )
    return toggle


def _activate(user: User, value: str) -> None:
    """Activate the toggle to ``value`` exactly as the browser would.

    Fires ``update:modelValue`` with the option INDEX — the payload Quasar's
    ``q-btn-toggle`` emits — which routes through NiceGUI's real value-change
    pipeline and invokes the server-side ``on_change`` handler.
    """
    user.find(marker="theme-toggle").trigger(
        "update:modelValue", _THEME_OPTIONS.index(value)
    )


async def test_theme_toggle_on_change_fires_and_updates_pref(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Activating the toggle to light then dark runs the ``on_change`` handler.

    Proves the handler actually executes (not merely that the widget exists):
    ``state.prefs.dark_mode`` must track the activated option. A disclaimer is
    not a pass — this asserts the observable result of the handler running.
    """
    from ui.state import get_state

    await user.open("/")

    # Baseline: drive the toggle to "auto" so the subsequent light/dark
    # activations are genuine value CHANGES (NiceGUI no-ops an unchanged
    # assignment, which would silently skip the handler).
    with user.client:
        _theme_toggle(user).value = "auto"
    assert get_state().prefs.dark_mode == "auto"

    # auto -> light: handler must run and record the pref.
    _activate(user, "light")
    assert get_state().prefs.dark_mode == "light", (
        "theme-toggle on_change did not run for 'light': "
        f"prefs.dark_mode={get_state().prefs.dark_mode!r}. The toggle is "
        "broken — the server-side handler never fired."
    )

    # light -> dark: handler must run again.
    _activate(user, "dark")
    assert get_state().prefs.dark_mode == "dark", (
        "theme-toggle on_change did not run for 'dark': "
        f"prefs.dark_mode={get_state().prefs.dark_mode!r}."
    )


async def test_theme_toggle_applies_live_quasar_dark_side_effect(
    user: User,
    isolated_state_dir: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The handler issues the live ``Quasar.Dark.set(...)`` flip per option.

    This is the crux of the fix: a fresh ``ui.dark_mode()`` in the handler
    doesn't broadcast under NiceGUI 3.x, so the handler additionally calls
    ``ui.run_javascript("Quasar.Dark.set(...)")`` to flip the theme live. We
    capture every ``run_javascript`` payload and assert the correct
    ``Quasar.Dark.set`` argument is emitted for light (``false``) and dark
    (``true``) — concretely proving the live side effect runs.
    """
    from ui.state import get_state

    js_calls: list[str] = []

    # ``_on_change`` calls ``ui.run_javascript`` (late ``from nicegui import
    # ui``); patching the attribute on the shared ``nicegui.ui`` module
    # intercepts it. Return None to avoid awaiting a real client response in
    # the in-process User harness.
    monkeypatch.setattr(
        ui, "run_javascript", lambda code, *a, **k: js_calls.append(str(code))
    )

    await user.open("/")

    # Baseline different from the values under test (see no-op gotcha).
    with user.client:
        _theme_toggle(user).value = "auto"
    js_calls.clear()

    # auto -> light flips Quasar to light mode: Quasar.Dark.set(false).
    _activate(user, "light")
    assert get_state().prefs.dark_mode == "light"
    assert any("Quasar.Dark.set(false)" in c for c in js_calls), (
        "expected a live 'Quasar.Dark.set(false)' flip for light mode; "
        f"captured run_javascript calls={js_calls!r}"
    )

    js_calls.clear()

    # light -> dark flips Quasar to dark mode: Quasar.Dark.set(true).
    _activate(user, "dark")
    assert get_state().prefs.dark_mode == "dark"
    assert any("Quasar.Dark.set(true)" in c for c in js_calls), (
        "expected a live 'Quasar.Dark.set(true)' flip for dark mode; "
        f"captured run_javascript calls={js_calls!r}"
    )
