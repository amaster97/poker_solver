"""Per-hand frequency editor dialog (PR 24b §3.1).

Implements ``docs/pr_proposals/v1_5_gui_surface_gaps.md`` §3.1 + §4:
when the user wants finer-grain control than the 4-step cycle on the
13×13 input matrix, this dialog exposes one ``ui.slider(0, 100)`` per
combo for a single hand class, plus a "Set all" master slider that
propagates to every combo.

Hand-class combo counts (see ``ui.state.enumerate_combos``):
- Pair (e.g. ``"AA"``): 6 combos.
- Suited (e.g. ``"AKs"``): 4 combos.
- Offsuit (e.g. ``"AKo"``): 12 combos.

The dialog renders the combos in a flex grid so the layout adapts to
any of the three sizes. Saves write per-combo via
``RangeWithFreqs.set_frequency``.

ElementFilter markers:
  ``range-freq-dialog``, ``range-freq-master-slider``,
  ``range-freq-combo-slider-{idx}``, ``range-freq-save``,
  ``range-freq-cancel``.
"""

from __future__ import annotations

import logging
from typing import Any

from ui.state import AppState, enumerate_combos, save_state

logger = logging.getLogger(__name__)


def open_range_freq_dialog(
    state: AppState,
    *,
    player: int,
    hand_class: str,
    on_save: Any | None = None,
) -> Any:
    """Open the per-hand frequency editor.

    Args:
        state: the AppState singleton (mutated on Save).
        player: 0 or 1 — which player's range is being edited.
        hand_class: e.g. ``"AA"``, ``"AKs"``, ``"AKo"``. Enumerated to
            6 / 4 / 12 combos respectively via ``enumerate_combos``.
        on_save: optional refresh callback (e.g. matrix re-render).

    Returns:
        The opened ``ui.dialog`` object.
    """
    from nicegui import ui

    combos = enumerate_combos(hand_class)
    if not combos:
        ui.notify(
            f"Unknown hand class: {hand_class}",
            type="warning",
            position="top",
        )
        return None

    rw = state.current_spot.ranges[player]
    # Initial frequencies in [0, 100] percent.
    combo_pcts: list[float] = [rw.frequency_of(c) * 100.0 for c in combos]

    with ui.dialog().mark("range-freq-dialog") as dialog, ui.card().classes("min-w-96"):
        ui.label(f"Per-combo frequency: {hand_class} (P{player})").classes(
            "text-base font-semibold"
        )
        ui.label(f"{len(combos)} combos. Sliders are 0-100% per combo.").classes(
            "text-xs text-gray-500"
        )
        ui.separator()

        slider_handles: list[Any] = []

        # Master "Set all" slider.
        with ui.row().classes("items-center w-full"):
            ui.label("Set all").classes("font-mono text-xs w-24")
            master = ui.slider(min=0, max=100, step=1, value=100)
            master.mark("range-freq-master-slider")
            master.classes("flex-grow")
            master_label = ui.label("100%").classes("text-xs font-mono w-12 text-right")

            def _on_master(e: Any) -> None:
                val = float(e.value or 0)
                master_label.set_text(f"{val:.0f}%")
                for i, sl in enumerate(slider_handles):
                    sl.set_value(int(val))
                    combo_pcts[i] = val

            master.on_value_change(_on_master)

        ui.separator()

        # Per-combo sliders.
        for idx, (c0, c1) in enumerate(combos):
            with ui.row().classes("items-center w-full"):
                ui.label(f"{c0}{c1}").classes("font-mono text-xs w-24")
                slider = ui.slider(
                    min=0,
                    max=100,
                    step=1,
                    value=int(round(combo_pcts[idx])),
                )
                slider.mark(f"range-freq-combo-slider-{idx}")
                slider.classes("flex-grow")
                val_label = ui.label(f"{combo_pcts[idx]:.0f}%").classes(
                    "text-xs font-mono w-12 text-right"
                )

                def _on_combo_change(
                    e: Any, i: int = idx, lbl: Any = val_label
                ) -> None:
                    combo_pcts[i] = float(e.value or 0)
                    lbl.set_text(f"{combo_pcts[i]:.0f}%")

                slider.on_value_change(_on_combo_change)
                slider_handles.append(slider)

        ui.separator()
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancel", on_click=dialog.close).props("flat").mark(
                "range-freq-cancel"
            )

            def _on_save() -> None:
                for combo, pct in zip(combos, combo_pcts):
                    rw.set_frequency(combo, pct / 100.0)
                save_state()
                logger.info(
                    "Set per-combo freqs for %s P%d: %s",
                    hand_class,
                    player,
                    [f"{p:.0f}" for p in combo_pcts],
                )
                if on_save is not None:
                    try:
                        on_save()
                    except Exception:  # noqa: BLE001
                        logger.exception("range-freq on_save callback failed")
                dialog.close()

            ui.button("Save", on_click=_on_save).props("color=positive").mark(
                "range-freq-save"
            )

    dialog.open()
    return dialog


__all__ = ["open_range_freq_dialog"]
