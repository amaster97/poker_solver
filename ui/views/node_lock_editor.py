"""Node-lock editor dialog (PR 24b §3.5).

Implements ``docs/pr_proposals/v1_5_gui_surface_gaps.md`` §3.5: a
``ui.dialog``-hosted editor that pins a player's strategy at a specific
infoset to a fixed probability distribution over its legal actions.

Engine surface: ``poker_solver/solver.py:36`` accepts
``locked_strategies: Mapping[str, Sequence[float]]`` keyed by infoset
key, values aligned to the engine's ``legal_actions`` ordering at that
node. PR 24b stores the dict on ``Spot.locked_strategies``; this
editor mutates it via ``set_lock`` / ``remove_lock`` helpers.

UX:
- Per-action ``ui.slider(0, 100)`` with the legal-action label.
- Initial values = current ``average_strategy[key]`` (or uniform if no
  prior solve has populated that infoset).
- Live "must sum to 100%" validator label; Save button is disabled
  while the sum is outside [99, 101] percent (tolerance for slider
  granularity).
- Save commits the distribution to ``Spot.locked_strategies[key]``;
  Cancel closes without persisting.

ElementFilter markers (Agent C may assert):
  ``node-lock-dialog``, ``node-lock-action-slider-{idx}``,
  ``node-lock-sum-label``, ``node-lock-save``, ``node-lock-cancel``.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from ui.state import AppState, save_state

logger = logging.getLogger(__name__)


def open_node_lock_dialog(
    state: AppState,
    *,
    infoset_key: str,
    legal_action_labels: Sequence[str],
    initial_distribution: Sequence[float] | None = None,
    on_save: Any | None = None,
) -> Any:
    """Open the node-lock editor dialog.

    Args:
        state: the AppState singleton (mutated on Save).
        infoset_key: the engine infoset key for the locked node (matches
            ``game.infoset_key(state, player)``).
        legal_action_labels: human-readable labels for the legal actions
            at this node, aligned to the engine's ordering. Typically
            derived from ``TreeNode.legal_actions`` + ``_ACTION_LABELS``
            in ``tree_browser.py``.
        initial_distribution: starting slider values (probabilities in
            [0, 1]). When None, defaults to the current
            ``Spot.locked_strategies[infoset_key]`` (if any) or uniform.
        on_save: optional callback invoked AFTER the lock has been
            written to ``state.current_spot.locked_strategies`` (so
            callers can refresh dependent UI like the run panel's
            "Locked strategies" expansion).

    Returns:
        The ``ui.dialog`` object (opened); kept open until Save / Cancel
        closes it. Returned so callers can drive it from test
        fixtures or imperative wiring.
    """
    from nicegui import ui

    n_actions = len(legal_action_labels)
    if n_actions == 0:
        ui.notify(
            "Cannot lock a node with no legal actions (terminal or chance).",
            type="warning",
            position="top",
        )
        return None

    spot = state.current_spot
    if initial_distribution is None:
        existing = spot.locked_strategies.get(infoset_key)
        if existing and len(existing) == n_actions:
            initial_distribution = existing
        else:
            initial_distribution = [1.0 / n_actions for _ in range(n_actions)]

    # Slider values in [0, 100] percent (sum target = 100).
    slider_values: list[float] = [float(p) * 100.0 for p in initial_distribution]

    with ui.dialog().mark("node-lock-dialog") as dialog, ui.card().classes("min-w-96"):
        ui.label(f"Lock infoset `{infoset_key}` to fixed strategy").classes(
            "text-base font-semibold"
        )
        ui.separator()

        # One slider per legal action.
        slider_handles: list[Any] = []
        sum_label = ui.label("").classes("text-xs font-mono")
        sum_label.mark("node-lock-sum-label")
        save_btn_holder: dict[str, Any] = {}

        def _update_sum_label() -> None:
            total = sum(slider_values)
            sum_label.set_text(f"Sum: {total:.1f}% (must equal 100%)")
            in_range = 99.0 <= total <= 101.0
            sum_label.classes(
                add="text-green-600" if in_range else "text-red-600",
                remove="text-red-600" if in_range else "text-green-600",
            )
            save_btn = save_btn_holder.get("btn")
            if save_btn is not None:
                if in_range:
                    save_btn.enable()
                else:
                    save_btn.disable()

        for idx, label in enumerate(legal_action_labels):
            with ui.row().classes("items-center w-full"):
                ui.label(f"{label}").classes("font-mono text-xs w-24")
                slider = ui.slider(
                    min=0,
                    max=100,
                    step=1,
                    value=int(round(slider_values[idx])),
                )
                slider.mark(f"node-lock-action-slider-{idx}")
                slider.classes("flex-grow")
                val_label = ui.label(f"{slider_values[idx]:.0f}%").classes(
                    "text-xs font-mono w-12 text-right"
                )

                def _on_slider_change(
                    e: Any, i: int = idx, lbl: Any = val_label
                ) -> None:
                    slider_values[i] = float(e.value or 0)
                    lbl.set_text(f"{slider_values[i]:.0f}%")
                    _update_sum_label()

                slider.on_value_change(_on_slider_change)
                slider_handles.append(slider)

        ui.separator()
        with ui.row().classes("w-full justify-end gap-2"):

            def _on_cancel() -> None:
                dialog.close()

            ui.button("Cancel", on_click=_on_cancel).props("flat").mark(
                "node-lock-cancel"
            )

            def _on_save() -> None:
                total = sum(slider_values) or 1.0
                # Normalize to probabilities summing to exactly 1.0
                # before persisting (the engine expects a probability
                # vector; slider sum may be 99 or 101 within tolerance).
                normalized = [v / total for v in slider_values]
                spot.locked_strategies[infoset_key] = normalized
                save_state()
                logger.info(
                    "Locked %s to %s",
                    infoset_key,
                    [f"{p:.2f}" for p in normalized],
                )
                if on_save is not None:
                    try:
                        on_save()
                    except Exception:  # noqa: BLE001
                        logger.exception("on_save callback failed")
                dialog.close()

            save_btn = ui.button("Save lock", on_click=_on_save).props("color=positive")
            save_btn.mark("node-lock-save")
            save_btn_holder["btn"] = save_btn

        _update_sum_label()
    dialog.open()
    return dialog


def remove_lock(state: AppState, infoset_key: str) -> bool:
    """Remove a lock from ``Spot.locked_strategies``.

    Returns True if the key was present and removed; False if it was
    already absent. Persists via ``save_state`` on success.
    """
    spot = state.current_spot
    if infoset_key in spot.locked_strategies:
        del spot.locked_strategies[infoset_key]
        save_state()
        return True
    return False


def clear_all_locks(state: AppState) -> int:
    """Clear every lock; returns the number of locks removed."""
    spot = state.current_spot
    n = len(spot.locked_strategies)
    spot.locked_strategies.clear()
    save_state()
    return n


__all__ = ["clear_all_locks", "open_node_lock_dialog", "remove_lock"]
