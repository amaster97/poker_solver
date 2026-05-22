"""3-step onboarding modal (PR 10a, Agent A).

Triggered on first launch when ``state.json`` is absent OR
``state.prefs.onboarding_completed is False`` (per ``pr10a_spec.md`` §13
table + §11 acceptance #12, Risk 6 mitigation).

Each step is ONE action; the final step teaches the R/Y/G color legend
before closing. Content sourced from ``ui_mockups_and_debates.md`` §4
(3-step content).
"""

from __future__ import annotations

import logging
from typing import Any

from ui.state import AppState, save_state

logger = logging.getLogger(__name__)


def show_modal(state: AppState) -> None:
    """Show the 3-step onboarding modal.

    Idempotent: noop when ``state.prefs.onboarding_completed`` is True.
    """
    if state.prefs.onboarding_completed:
        return

    from nicegui import ui

    step = {"current": 0}
    total_steps = 3

    with ui.dialog().props("persistent") as dialog, ui.card().classes("max-w-md"):
        title = ui.label("Welcome to poker-solver").classes("text-lg font-semibold")
        progress = ui.label(f"Step 1 of {total_steps}").classes("text-xs text-gray-500")
        ui.separator()

        body = ui.column().classes("gap-2")
        with body:
            content = ui.label("").classes("text-sm")

        ui.separator()
        with ui.row().classes("justify-between w-full"):
            back_btn = ui.button("Back").props("flat")
            back_btn.disable()
            next_btn = ui.button("Next")
            finish_btn = ui.button(
                "Got it",
                on_click=lambda: _finish(dialog, state),
            )
            finish_btn.visible = False

            # Wire on_click after all three buttons exist so the lambdas
            # can reference finish_btn (mypy-friendly).
            back_btn.on_click(
                lambda: _go(step, -1, content, progress, total_steps, title, finish_btn)
            )
            next_btn.on_click(
                lambda: _go(step, 1, content, progress, total_steps, title, finish_btn)
            )

        # Render initial step.
        _render_step(step["current"], content, progress, total_steps, title, finish_btn)
        # Disable back on step 0.
        back_btn.disable()

    dialog.open()


def _go(
    step: dict[str, int],
    delta: int,
    content: Any,
    progress: Any,
    total_steps: int,
    title: Any,
    finish_btn: Any,
) -> None:
    step["current"] = max(0, min(total_steps - 1, step["current"] + delta))
    _render_step(step["current"], content, progress, total_steps, title, finish_btn)


def _render_step(
    idx: int,
    content: Any,
    progress: Any,
    total_steps: int,
    title: Any,
    finish_btn: Any,
) -> None:
    progress.set_text(f"Step {idx + 1} of {total_steps}")
    steps = _STEPS
    s = steps[idx]
    title.set_text(s["title"])
    content.set_text(s["body"])
    finish_btn.visible = idx == total_steps - 1


def _finish(dialog: Any, state: AppState) -> None:
    state.prefs.onboarding_completed = True
    save_state()
    dialog.close()


# 3-step content per ``ui_mockups_and_debates.md`` §4. Each step is
# one-action; the final step teaches the R/Y/G color legend.
_STEPS: list[dict[str, str]] = [
    {
        "title": "Step 1: Pick a spot",
        "body": (
            "Pick a spot to solve. Use the Spot Input panel on the right "
            "(or 'Load preset' for one of 12 hand-crafted fixtures). The "
            "default is a 100 BB postflop with full ranges."
        ),
    },
    {
        "title": "Step 2: Solve",
        "body": (
            "Click Solve in the Run Panel. The exploitability chart "
            "(log Y-axis) updates every 500 ms as the solver converges. "
            "You can pause or stop at any time; the partial strategy is "
            "preserved."
        ),
    },
    {
        "title": "Step 3: Read the color legend",
        "body": (
            "Strategy matrix uses Pio R/Y/G colors:  RED = fold,  "
            "YELLOW = call/check,  GREEN = raise/bet.  Range INPUT matrix "
            "uses white-to-blue intensity (saturation = frequency in range). "
            "Hover any cell for numeric frequencies; click for the combo "
            "inspector strip below the matrix."
        ),
    },
]


__all__ = ["show_modal"]
