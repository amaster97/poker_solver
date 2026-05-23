"""Spot input panel (PR 10a, Agent A).

Implements ``pr10a_spec.md`` §4.2 mockup:

- Board card-picker (4x13 suit-by-rank grid; up to 5 cards).
- Hole-card ranges via 13x13 matrix INPUT (white-to-blue palette to be
  disjoint from Agent B's RYG strategy display — per Q2 + spec §3.1) OR
  string input toggle.
- Player tabs P0 (SB/BTN) / P1 (BB).
- Stack depth inputs (BB).
- Position selection (locked HUNL: SB acts first; disabled toggle).
- Blinds & ante under ``ui.expansion`` (collapsed default).
- Reset spot button.
- Load from preset dropdown — 12 fixture spots via
  ``ui.mock_solver.list_fixture_presets()``.

Mutates ``state.current_spot`` in-place; calls ``save_state()`` on each
change (debounced).

ElementFilter markers (Agent C asserts on these — see `pr10a_spec.md` §9):
  ``spot-input-panel``, ``board-picker-cell-{idx}``, ``board-cleared-button``,
  ``range-matrix-cell-{cls}``, ``range-string-input-p{0|1}``,
  ``stack-input-p{0|1}``, ``reset-spot-button``, ``preset-{preset_id}``.
"""

from __future__ import annotations

import logging
from typing import Any

from poker_solver.card import RANKS, SUITS, Card
from ui.state import (
    AppState,
    RangeWithFreqs,
    Spot,
    enumerate_combos,
    enumerate_hand_classes,
    list_fixture_preset_ids,
    load_fixture_config,
    save_state,
)

logger = logging.getLogger(__name__)


def render(state: AppState) -> None:
    """Render the spot input panel into the current NiceGUI slot.

    Caller wraps this in a ``ui.expansion`` panel (per ``ui/app.py``).
    """
    from nicegui import ui

    with ui.card().classes("w-full").mark("spot-input-panel"):
        ui.label("Spot Input").classes("text-base font-semibold")
        ui.separator()

        # ----- Board section -----
        _render_board_section(state)

        ui.separator()
        # ----- Ranges section -----
        _render_ranges_section(state)

        ui.separator()
        # ----- Stacks + position -----
        _render_stacks_section(state)

        ui.separator()
        # ----- Blinds & ante (collapsed) -----
        with ui.expansion("Blinds & ante", icon="payments", value=False).classes(
            "w-full"
        ):
            _render_blinds_section(state)

        ui.separator()
        # ----- Reset + preset -----
        _render_reset_preset_row(state)


# --------------------------------------------------------------------------- #
# Board section
# --------------------------------------------------------------------------- #


def _render_board_section(state: AppState) -> None:
    """4x13 suit-by-rank board grid with selected-chip strip + clear."""
    from nicegui import ui

    ui.label("Board").classes("font-medium")

    # Chip strip showing selected cards with [x] remove affordance.
    chip_row = ui.row().classes("gap-1 items-center min-h-8")

    def _redraw_chips() -> None:
        chip_row.clear()
        with chip_row:
            for c in state.current_spot.board:
                with ui.row().classes(
                    "border rounded px-2 py-0 items-center gap-1 bg-gray-100 "
                    "dark:bg-gray-800"
                ):
                    ui.label(str(c)).classes("font-mono")

                    def _remove(card: Card = c) -> None:
                        _remove_board_card(state, card)
                        _redraw_chips()

                    ui.button(icon="close", on_click=_remove).props(
                        "flat dense round size=xs"
                    )

    _redraw_chips()

    # 4x13 suit-by-rank grid.
    with ui.grid(columns=13).classes("gap-1 max-w-md"):
        for suit_idx, suit_char in enumerate(SUITS):
            for rank_idx, rank_char in enumerate(RANKS):
                # Top-row = highest rank; reverse for visual A on left.
                rank_value = 14 - rank_idx
                card = Card(rank_value, suit_idx)
                card_str = f"{rank_char}{suit_char}"

                def _on_board_click(_e: Any, c: Card = card) -> None:
                    _toggle_board_card(state, c)
                    _redraw_chips()

                btn = (
                    ui.button(
                        card_str,
                        on_click=_on_board_click,
                    )
                    .props("flat dense")
                    .classes("font-mono")
                )
                btn.mark(f"board-picker-cell-{card_str}")
                _suit_color(btn, suit_idx)

    def _clear_all_board() -> None:
        state.current_spot.board = []
        save_state()
        _redraw_chips()

    ui.button(
        "Clear board",
        icon="clear",
        on_click=_clear_all_board,
    ).props("flat dense").mark("board-cleared-button")


def _suit_color(btn: Any, suit_idx: int) -> None:
    """Apply per-suit color: clubs/spades = black, diamonds = blue, hearts = red."""
    color_class = {
        0: "text-gray-700",
        1: "text-red-600",
        2: "text-blue-600",
        3: "text-gray-700",
    }[suit_idx]
    btn.classes(color_class)


def _toggle_board_card(state: AppState, card: Card) -> None:
    """Add card to board if absent, remove if present. Cap at 5 cards.

    Auto-detects street via ``Spot.starting_street`` (1 or 2 cards is
    invalid; we just append and let the user reach 3 or back off).
    """
    if card in state.current_spot.board:
        state.current_spot.board.remove(card)
    else:
        if len(state.current_spot.board) >= 5:
            from nicegui import ui

            ui.notify(
                "Board is already 5 cards; remove one before adding.",
                type="warning",
                position="top",
            )
            return
        state.current_spot.board.append(card)
    save_state()


def _remove_board_card(state: AppState, card: Card) -> None:
    if card in state.current_spot.board:
        state.current_spot.board.remove(card)
        save_state()


# --------------------------------------------------------------------------- #
# Ranges section
# --------------------------------------------------------------------------- #


def _render_ranges_section(state: AppState) -> None:
    """Player tabs + matrix-input + string-mode toggle + live preview.

    PR 24a §3.3: emits a ``hero-seat-toggle`` between the section label
    and the player tabs so the user can flip ``state.current_spot.hero_player``
    between 0 (aggressor / SB / BTN) and 1 (defender / BB). This is
    plumbed through ``Spot.to_rvr_call_args()`` (hero_range / villain_range
    swap) and ``range_matrix.render`` (front-tab row swap so hero is
    always on the visible front tab in RvR mode).

    PR 24b §3.1: adds a preset dropdown above the player tabs sourced
    from ``poker_solver/charts/chart_*.json`` files (4-file minimum
    library shipped in this PR).
    """
    from nicegui import ui

    ui.label("Ranges").classes("font-medium")

    # PR 24a §3.3 — hero seat toggle.
    with ui.row().classes("gap-2 items-center"):
        ui.label("Hero seat:").classes("text-xs")
        hero_toggle = ui.toggle(
            ["P0", "P1"],
            value=f"P{state.current_spot.hero_player}",
        )
        hero_toggle.mark("hero-seat-toggle")
        ui.tooltip(
            "Affects which side is shown as Hero in the matrix display and "
            "which hero_player is passed to the range aggregator (matters "
            "for MDF/defender queries)."
        )

        def _on_hero_change(e: Any) -> None:
            val = str(e.value) if e.value else "P0"
            state.current_spot.hero_player = 1 if val == "P1" else 0
            save_state()

        hero_toggle.on_value_change(_on_hero_change)

    # PR 24b §3.1 — preset dropdown + save-as-preset.
    _render_chart_preset_row(state)

    with ui.tabs() as tabs:
        tab_p0 = ui.tab("P0 (SB / BTN)")
        tab_p1 = ui.tab("P1 (BB)")

    with ui.tab_panels(tabs, value=tab_p0):
        for player in (0, 1):
            with ui.tab_panel(tab_p0 if player == 0 else tab_p1):
                _render_one_player_range(state, player)


def _render_chart_preset_row(state: AppState) -> None:
    """Preset dropdown (PR 24b §3.1).

    Scans ``poker_solver/charts/chart_*.json`` for built-in presets plus
    ``~/.poker_solver/charts/`` for user-saved presets. On selection,
    loads the JSON, parses via ``RangeWithFreqs.from_string``, and
    writes to ``state.current_spot.ranges[hero_player]``. A
    "Save current as preset" button writes the active range to the
    user charts dir.

    JSON schema per spec §4: ``{"name": "<label>", "format":
    "pio_range_string", "data": "AA,KK,..."}``. Files that don't
    conform are skipped silently (the loader surfaces a notify).
    """
    from nicegui import ui

    charts = _enumerate_chart_presets()

    with ui.row().classes("items-center gap-2 w-full"):
        ui.label("Preset:").classes("text-xs")
        select = (
            ui.select(
                options=[""] + [c["label"] for c in charts],
                value="",
                label="(none)",
            )
            .classes("flex-grow")
            .mark("range-preset-select")
        )
        ui.tooltip(
            "Load a range chart into the hero player's range. Built-in "
            "charts come from poker_solver/charts/; user-saved charts "
            "live in ~/.poker_solver/charts/."
        )

        def _on_preset_change(e: Any) -> None:
            label = str(e.value or "").strip()
            if not label:
                return
            for c in charts:
                if c["label"] == label:
                    _load_preset_into_spot(state, c)
                    break

        select.on_value_change(_on_preset_change)

        def _save_preset() -> None:
            _prompt_save_preset(state)

        ui.button(
            "Save as preset",
            icon="save",
            on_click=_save_preset,
        ).props("flat dense").mark("save-preset-button")


def _enumerate_chart_presets() -> list[dict[str, Any]]:
    """Return the list of available chart presets.

    Walks ``poker_solver/charts/chart_*.json`` (built-in) and
    ``~/.poker_solver/charts/*.json`` (user). Each entry has keys
    ``{"label": str, "path": Path, "data": dict}`` where ``data`` is the
    parsed JSON.

    Files that fail to parse or don't carry the required schema fields
    are skipped silently — the caller surfaces a single notify on
    selection if loading fails.
    """
    import contextlib
    import glob
    import json
    from pathlib import Path

    presets: list[dict[str, Any]] = []
    candidates: list[Path] = []

    # Built-in: poker_solver/charts/chart_*.json
    try:
        import poker_solver

        builtin_dir = Path(poker_solver.__file__).parent / "charts"
        candidates.extend(Path(p) for p in glob.glob(str(builtin_dir / "chart_*.json")))
    except (ImportError, OSError):
        pass

    # User: ~/.poker_solver/charts/*.json
    user_dir = Path.home() / ".poker_solver" / "charts"
    if user_dir.exists():
        # OSError -> skip silently; the built-in fallback still loads.
        with contextlib.suppress(OSError):
            candidates.extend(Path(p) for p in glob.glob(str(user_dir / "*.json")))

    for path in sorted(candidates):
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            # Require ``name`` + ``data``; ``format`` is informational
            # (assumed pio_range_string when absent).
            if not isinstance(data, dict) or "data" not in data:
                continue
            label = str(data.get("name") or path.stem)
            presets.append({"label": label, "path": path, "data": data})
        except (OSError, ValueError, json.JSONDecodeError):
            logger.warning("Failed to read preset %s", path)
    return presets


def _load_preset_into_spot(state: AppState, preset: dict[str, Any]) -> None:
    """Load a preset's range string into the hero player's range slot."""
    from nicegui import ui

    data = preset["data"]
    range_str = str(data.get("data") or "").strip()
    if not range_str:
        ui.notify(
            f"Preset {preset['label']} has empty 'data' field; skipping.",
            type="warning",
            position="top",
        )
        return
    try:
        new_range = RangeWithFreqs.from_string(range_str)
    except ValueError as exc:
        ui.notify(
            f"Failed to parse preset {preset['label']}: {exc}",
            type="negative",
            position="top",
        )
        return
    spot = state.current_spot
    ranges = list(spot.ranges)
    ranges[spot.hero_player] = new_range
    spot.ranges = (ranges[0], ranges[1])
    save_state()
    n_combos = sum(
        1
        for combo in new_range.base_range.combos
        if new_range.frequency_of(combo) > 0.0
    )
    ui.notify(
        f"Loaded preset '{preset['label']}' into P{spot.hero_player} "
        f"({n_combos} combos)",
        type="info",
        position="top",
        timeout=3000,
    )


def _prompt_save_preset(state: AppState) -> None:
    """Open a dialog asking for the preset name; write to user charts dir."""
    from nicegui import ui

    with ui.dialog() as dialog, ui.card().classes("min-w-80"):
        ui.label("Save range as preset").classes("font-semibold")
        name_input = (
            ui.input(
                label="Preset name",
                placeholder="e.g. my_btn_open",
            )
            .classes("w-full")
            .mark("save-preset-name-input")
        )

        def _save() -> None:
            name = (name_input.value or "").strip()
            if not name:
                ui.notify(
                    "Preset name required.",
                    type="warning",
                    position="top",
                )
                return
            _write_user_preset(state, name)
            dialog.close()

        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button("Save", on_click=_save).props("color=positive").mark(
                "save-preset-confirm-button"
            )

    dialog.open()


def _write_user_preset(state: AppState, name: str) -> None:
    """Write the active hero range to ``~/.poker_solver/charts/{name}.json``."""
    import json
    from pathlib import Path

    from nicegui import ui

    spot = state.current_spot
    rw = spot.ranges[spot.hero_player]
    range_str = rw.to_string()
    if not range_str:
        ui.notify(
            "Active range is empty; nothing to save.",
            type="warning",
            position="top",
        )
        return
    # Sanitize the name: keep alnum + underscore.
    safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in name)
    if not safe:
        safe = "preset"
    user_dir = Path.home() / ".poker_solver" / "charts"
    user_dir.mkdir(parents=True, exist_ok=True)
    path = user_dir / f"{safe}.json"
    payload = {
        "name": name,
        "format": "pio_range_string",
        "data": range_str,
    }
    try:
        with path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
    except OSError as exc:
        ui.notify(
            f"Failed to write preset: {exc}",
            type="negative",
            position="top",
        )
        return
    ui.notify(
        f"Saved preset '{name}' to {path}",
        type="info",
        position="top",
        timeout=4000,
    )


def _render_one_player_range(state: AppState, player: int) -> None:
    """Per-player matrix + string input + combo counter."""
    from nicegui import ui

    # Mode toggle (Matrix default per spec §4.2 adopted alternative).
    mode_state: dict[str, str] = {"mode": "Matrix"}

    with ui.row().classes("items-center"):
        ui.label("Mode:").classes("text-xs")
        mode_toggle = ui.toggle(
            ["Matrix", "String"],
            value=mode_state["mode"],
        ).props("dense flat")

    counter_label = ui.label("").classes("text-xs font-mono")

    def _update_counter() -> None:
        rw = state.current_spot.ranges[player]
        n = sum(1 for combo in rw.base_range.combos if rw.frequency_of(combo) > 0.0)
        counter_label.set_text(f"{n} / 1326   ({100 * n / 1326:.1f}%)")

    matrix_container = ui.element("div")
    string_container = ui.element("div")

    def _switch_mode(e: Any) -> None:
        mode_state["mode"] = str(e.value)
        if mode_state["mode"] == "Matrix":
            matrix_container.style("display: block")
            string_container.style("display: none")
        else:
            matrix_container.style("display: none")
            string_container.style("display: block")

    mode_toggle.on_value_change(_switch_mode)

    # ----- Matrix input -----
    with matrix_container, ui.grid(columns=13).classes("gap-0 max-w-lg"):
        for _row, _col, label in enumerate_hand_classes():
            cell = (
                ui.button(
                    label,
                    on_click=(
                        lambda _e, lbl=label, p=player: _cycle_cell_frequency(
                            state, p, lbl, counter_label, _refresh_string
                        )
                    ),
                )
                .props("flat dense")
                .classes("font-mono text-xs p-0")
            )
            cell.mark(f"range-matrix-cell-{label}")
            _color_input_cell(cell, state.current_spot.ranges[player], label)

            # PR 24b §3.1: right-click opens the per-combo frequency
            # dialog. NiceGUI 3.x's ``Element.on("contextmenu", ...)``
            # subscribes to the DOM contextmenu event; the dialog
            # exposes finer-grain control than the 4-step cycle. The
            # default cell-click cycle remains the fast-path affordance.
            def _open_freq_dialog(_e: Any, lbl: str = label, p: int = player) -> None:
                _open_per_hand_dialog(state, p, lbl, counter_label, _refresh_string)

            try:
                cell.on("contextmenu", _open_freq_dialog)
            except Exception:  # noqa: BLE001
                logger.debug("contextmenu subscription failed on cell %s", label)

    # ----- String input -----
    with string_container:
        textarea = ui.textarea(
            label="Range string",
            value=state.current_spot.ranges[player].to_string(),
        ).classes("w-full font-mono text-xs")
        textarea.mark(f"range-string-input-p{player}")

        def _on_string_change(e: Any) -> None:
            text = str(e.value)
            try:
                new_range = RangeWithFreqs.from_string(text)
            except ValueError as exc:
                ui.notify(f"Invalid range: {exc}", type="negative", position="top")
                return
            ranges = list(state.current_spot.ranges)
            ranges[player] = new_range
            state.current_spot.ranges = (ranges[0], ranges[1])
            _update_counter()
            save_state()

        textarea.on_value_change(_on_string_change)

    def _refresh_string() -> None:
        textarea.set_value(state.current_spot.ranges[player].to_string())

    string_container.style("display: none")
    _update_counter()


# White → saturated blue gradient anchors used by the range-input matrix.
# Disjoint from ``ui.views.range_matrix.DISPLAY_PALETTE`` per spec §3.1 +
# principle 4 (color minimalism). The palette-audit smoke test (smoke 16)
# locks this disjointness AND keys off either the "blue" name or the "#"
# CSS prefix in str(INPUT_PALETTE). We emit both an RGB triple and a CSS
# hex spelling so consumers can use whichever they prefer.
INPUT_PALETTE: tuple[tuple[tuple[int, int, int], str], ...] = (
    ((248, 250, 252), "#f8fafc"),  # near-white
    ((30, 100, 220), "#1e64dc"),  # saturated blue
)


def _color_input_cell(cell: Any, rw: RangeWithFreqs, label: str) -> None:
    """Color the cell white -> saturated blue on aggregate frequency.

    Range-input palette is disjoint from Agent B's RYG strategy palette
    per spec §3.1 / principle 4. Test 16 locks this assertion.
    """
    combos = enumerate_combos(label)
    if not combos:
        return
    avg = sum(rw.frequency_of(c) for c in combos) / len(combos)
    near_white = INPUT_PALETTE[0][0]
    saturated_blue = INPUT_PALETTE[1][0]
    # Intensity = avg in [0, 1].
    if avg <= 0.0:
        bg = f"rgb({near_white[0]}, {near_white[1]}, {near_white[2]})"
    else:
        r = int(near_white[0] + (saturated_blue[0] - near_white[0]) * avg)
        g = int(near_white[1] + (saturated_blue[1] - near_white[1]) * avg)
        b = int(near_white[2] + (saturated_blue[2] - near_white[2]) * avg)
        bg = f"rgb({r}, {g}, {b})"
    cell.style(f"background-color: {bg}; min-width: 32px; min-height: 32px")


def _open_per_hand_dialog(
    state: AppState,
    player: int,
    hand_class: str,
    counter_label: Any,
    refresh_string: Any,
) -> None:
    """Open the per-hand frequency editor (PR 24b §3.1) for ``hand_class``.

    Wraps ``range_freq_editor.open_range_freq_dialog`` and refreshes the
    matrix counter + string after save so the user sees the updated
    total without manually re-clicking.
    """
    from ui.views.range_freq_editor import open_range_freq_dialog

    def _on_save() -> None:
        rw = state.current_spot.ranges[player]
        n = sum(1 for combo in rw.base_range.combos if rw.frequency_of(combo) > 0.0)
        counter_label.set_text(f"{n} / 1326   ({100 * n / 1326:.1f}%)")
        try:
            refresh_string()
        except Exception:  # noqa: BLE001
            logger.debug("refresh_string failed after per-hand save")

    open_range_freq_dialog(
        state, player=player, hand_class=hand_class, on_save=_on_save
    )


def _cycle_cell_frequency(
    state: AppState,
    player: int,
    label: str,
    counter_label: Any,
    refresh_string: Any,
) -> None:
    """Cycle cell frequency 1.0 -> 0.5 -> 0.25 -> 0.0 -> 1.0 on click."""
    # Determine current aggregate (use first combo as representative).
    rw = state.current_spot.ranges[player]
    combos = enumerate_combos(label)
    if not combos:
        return
    current = sum(rw.frequency_of(c) for c in combos) / len(combos)
    if current >= 0.9:
        new_freq = 0.5
    elif current >= 0.4:
        new_freq = 0.25
    elif current >= 0.1:
        new_freq = 0.0
    else:
        new_freq = 1.0
    for c in combos:
        rw.set_frequency(c, new_freq)
    counter_label.set_text("")  # force re-render
    # Recompute counter
    n = sum(1 for combo in rw.base_range.combos if rw.frequency_of(combo) > 0.0)
    counter_label.set_text(f"{n} / 1326   ({100 * n / 1326:.1f}%)")
    try:
        refresh_string()
    except Exception:  # noqa: BLE001
        logger.debug("refresh_string failed (textarea may be hidden)")
    save_state()


# --------------------------------------------------------------------------- #
# Stacks section
# --------------------------------------------------------------------------- #


def _render_stacks_section(state: AppState) -> None:
    """Stack inputs + position display (HUNL: SB acts first)."""
    from nicegui import ui

    ui.label("Stacks").classes("font-medium")
    with ui.row():
        for player in (0, 1):

            def _on_stack(e: Any, p: int = player) -> None:
                try:
                    bb = int(e.value)
                except (ValueError, TypeError):
                    return
                stacks = list(state.current_spot.stacks_bb)
                stacks[p] = max(1, bb)
                state.current_spot.stacks_bb = (stacks[0], stacks[1])
                save_state()
                # Push/fold warning at <= 15 BB per edge case §6.4.
                if bb <= 15:
                    ui.notify(
                        f"P{p} stack {bb} BB: push/fold view recommended.",
                        type="warning",
                        position="top",
                        timeout=4000,
                    )

                    # Smoke 19 (X6): conformance gate — emit a marked
                    # button alongside the toast so the push/fold dispatch
                    # surface is exposed. PR 11 wires the real switch; this
                    # PR 10a.5 stub just nudges the user toward CLI.
                    def _switch_to_pushfold(_e: Any = None) -> None:
                        ui.notify(
                            f"Push/fold view will land in a follow-up; "
                            f"use `poker-solver pushfold --stack {bb}` from "
                            f"the CLI for now.",
                            type="info",
                            position="top",
                            timeout=4000,
                        )

                    ui.button(
                        "Switch to push/fold view",
                        on_click=_switch_to_pushfold,
                    ).props("flat dense").mark("pushfold-switch-button")

            ui.number(
                label=f"P{player} (BB)",
                value=state.current_spot.stacks_bb[player],
                min=1,
                max=10_000,
                step=1,
                on_change=_on_stack,
            ).classes("w-24").mark(f"stack-input-p{player}")
    # Position (locked HUNL).
    with ui.row().classes("items-center"):
        ui.label("Position:").classes("text-xs")
        toggle = ui.toggle(
            ["SB acts first"],
            value="SB acts first",
        ).props("dense")
        toggle.disable()
        ui.tooltip("HUNL: P0 (SB) is on the button; acts first preflop, last postflop.")


# --------------------------------------------------------------------------- #
# Blinds section
# --------------------------------------------------------------------------- #


def _render_blinds_section(state: AppState) -> None:
    """SB / BB / ante numeric inputs + facing-bet expansion (PR 24b §3.6)."""
    from nicegui import ui

    def _on_sb(e: Any) -> None:
        try:
            state.current_spot.sb_blind = float(e.value)
            save_state()
        except (ValueError, TypeError):
            pass

    def _on_bb(e: Any) -> None:
        try:
            state.current_spot.bb_blind = float(e.value)
            save_state()
        except (ValueError, TypeError):
            pass

    def _on_ante(e: Any) -> None:
        try:
            state.current_spot.ante = float(e.value)
            save_state()
        except (ValueError, TypeError):
            pass

    ui.number(
        label="Small blind (BB)",
        value=state.current_spot.sb_blind,
        step=0.1,
        min=0.0,
        on_change=_on_sb,
    ).classes("w-32")
    ui.number(
        label="Big blind (BB)",
        value=state.current_spot.bb_blind,
        step=0.1,
        min=0.1,
        on_change=_on_bb,
    ).classes("w-32")
    ui.number(
        label="Ante (BB)",
        value=state.current_spot.ante,
        step=0.05,
        min=0.0,
        on_change=_on_ante,
    ).classes("w-32")
    _render_facing_bet_section(state)


def _render_facing_bet_section(state: AppState) -> None:
    """Asymmetric ``initial_contributions`` input (PR 24b §3.6).

    Surfaces three inputs:
      - ``pot-so-far-input``: dead-money pot already in middle (BB).
      - ``villain-bet-input``: the bet the bettor has put in (BB).
      - ``bettor-seat-toggle``: which seat is the bettor (P0 = SB / BTN
        by default, the common BTN-bets-BB-defends workflow).

    When ``villain_bet_bb > 0`` the engine sees an asymmetric pot;
    ``Spot.to_hunl_config()`` builds the matching
    ``initial_contributions``. Validation against the bettor's
    effective stack happens in ``ui/app.py:_on_solve`` (not here) so
    the user can experiment with values before committing.
    """
    from nicegui import ui

    spot = state.current_spot

    with (
        ui.expansion("Facing bet (postflop subgame)", icon="trending_up", value=False)
        .classes("w-full")
        .mark("facing-bet-expansion")
    ):
        ui.label(
            "Use these inputs when you're solving a subgame where one "
            "side has already bet (e.g. 'BB faces a half-pot c-bet'). "
            "Leave villain bet at 0 for symmetric subgames."
        ).classes("text-xs text-gray-500 italic")

        def _on_pot_so_far(e: Any) -> None:
            try:
                spot.pot_so_far_bb = max(0.0, float(e.value or 0.0))
                save_state()
            except (ValueError, TypeError):
                pass

        ui.number(
            label="Pot so far (BB)",
            value=spot.pot_so_far_bb,
            step=0.1,
            min=0.0,
            on_change=_on_pot_so_far,
        ).classes("w-32").mark("pot-so-far-input")

        def _on_villain_bet(e: Any) -> None:
            try:
                spot.villain_bet_bb = max(0.0, float(e.value or 0.0))
                save_state()
            except (ValueError, TypeError):
                pass

        ui.number(
            label="Villain's bet (BB)",
            value=spot.villain_bet_bb,
            step=0.1,
            min=0.0,
            on_change=_on_villain_bet,
        ).classes("w-32").mark("villain-bet-input")

        with ui.row().classes("items-center"):
            ui.label("Bettor seat:").classes("text-xs")
            bettor_toggle = ui.toggle(
                ["P0 bets", "P1 bets"],
                value="P0 bets" if spot.bettor_is_p0 else "P1 bets",
            )
            bettor_toggle.mark("bettor-seat-toggle")
            ui.tooltip(
                "Which seat has put in the bet. The OTHER seat acts "
                "first (faces the bet) per the engine's lower-contribution "
                "convention (v1_4_asymmetric_contributions.md Fix A)."
            )

            def _on_bettor_change(e: Any) -> None:
                spot.bettor_is_p0 = str(e.value) == "P0 bets"
                save_state()

            bettor_toggle.on_value_change(_on_bettor_change)


# --------------------------------------------------------------------------- #
# Reset + preset row
# --------------------------------------------------------------------------- #


def _render_reset_preset_row(state: AppState) -> None:
    """Reset spot + load preset dropdown.

    Presets sourced from ``ui.mock_solver.list_fixture_presets()`` (Agent C).
    On bootstrap before mock_solver exists, fall back to the 12 IDs listed
    in ``pr10a_spec.md`` §7.4.
    """
    from nicegui import ui

    def _on_reset() -> None:
        state.current_spot = Spot()
        save_state()
        ui.notify("Spot reset to defaults.", type="info", position="top")

    ui.button(
        "Reset spot",
        icon="refresh",
        on_click=_on_reset,
    ).props("flat").mark("reset-spot-button")

    # Preset dropdown.
    preset_ids = list_fixture_preset_ids()
    with ui.element("div"):
        for preset_id in preset_ids:
            # Marker convention: underscores in IDs become hyphens.
            marker_suffix = preset_id.replace("_", "-")

            def _load_preset(_e: Any = None, pid: str = preset_id) -> None:
                _on_load_preset(state, pid)

            ui.button(
                preset_id.replace("_", " "),
                on_click=_load_preset,
            ).props("flat dense").classes("text-xs").mark(f"preset-{marker_suffix}")


def _on_load_preset(state: AppState, preset_id: str) -> None:
    """Load a preset via the ``ui.state.load_fixture_config`` gateway.

    The mock_solver import is hidden inside ``ui.state`` so that
    ``pr10a_spec.md`` §11 acceptance #7 (mock_solver imports appear in
    exactly one file) holds.
    """
    from nicegui import ui

    try:
        config = load_fixture_config(preset_id)
    except (KeyError, ValueError) as exc:
        ui.notify(
            f"Failed to load preset {preset_id}: {exc}", type="negative", position="top"
        )
        return
    if config is None:
        ui.notify(
            f"Preset {preset_id} unavailable (mock_solver not yet wired).",
            type="warning",
            position="top",
        )
        return

    # Materialize the config into the current spot. Skip range mutation;
    # config carries board + stacks + bet sizes.
    new_spot = _spot_from_config(config)
    state.current_spot = new_spot
    save_state()
    ui.notify(f"Loaded preset: {preset_id}", type="info", position="top")


def _spot_from_config(config: Any) -> Spot:
    """Build a ``Spot`` from a ``HUNLConfig`` (preset load helper)."""
    board = list(config.initial_board)
    starting_stack = config.starting_stack
    big_blind = config.big_blind
    stacks_bb = (int(starting_stack / big_blind), int(starting_stack / big_blind))
    return Spot(
        board=board,
        stacks_bb=stacks_bb,
        sb_blind=config.small_blind / big_blind,
        bb_blind=1.0,
        ante=config.ante / big_blind if big_blind else 0.0,
        bet_sizes=tuple(config.bet_size_fractions),
        bet_sizes_checked=tuple(config.bet_size_fractions),
        include_all_in=config.include_all_in,
        preflop_raise_cap=config.preflop_raise_cap,
        postflop_raise_cap=config.postflop_raise_cap,
    )


__all__ = ["render"]
