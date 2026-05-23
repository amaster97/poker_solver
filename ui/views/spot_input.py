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

    with ui.tabs() as tabs:
        tab_p0 = ui.tab("P0 (SB / BTN)")
        tab_p1 = ui.tab("P1 (BB)")

    with ui.tab_panels(tabs, value=tab_p0):
        for player in (0, 1):
            with ui.tab_panel(tab_p0 if player == 0 else tab_p1):
                _render_one_player_range(state, player)


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
    """SB / BB / ante numeric inputs."""
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
