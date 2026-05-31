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

import inspect
import logging
import os
from typing import Any

from poker_solver.card import RANKS, SUITS, Card
from ui.state import (
    AppState,
    RangeWithFreqs,
    Spot,
    enumerate_combos,
    enumerate_hand_classes,
    fixture_default_ranges,
    list_fixture_preset_ids,
    load_fixture_config,
    save_state,
)
from ui.views._cards import card_html

logger = logging.getLogger(__name__)

# Dev-gate (W1/W4): read ``POKER_SOLVER_DEV_CONCRETE`` directly (no
# cross-module import — same approach as ui/app.py and run_panel.py, so the
# three modules share the gate semantics without an import cycle). Read at call
# time so tests can flip it per-case with ``monkeypatch``.
_CONCRETE_DEV_ENV_VAR: str = "POKER_SOLVER_DEV_CONCRETE"


def _concrete_dev_enabled() -> bool:
    """True when the dev-only Concrete/RvR method toggle is enabled."""
    return bool(os.environ.get(_CONCRETE_DEV_ENV_VAR, "").strip())


def _board_is_postflop(board: Any) -> bool:
    """True when ``board`` (a card list) is a postflop board (3/4/5 cards).

    Regression 1: ``rvr_mode`` (range-vs-range) is POSTFLOP-only — the
    aggregator raises ``ValueError`` for a preflop spot. A postflop board has
    3 (flop), 4 (turn) or 5 (river) cards; a preflop board is empty. Mirrors
    ``Spot.starting_street`` (which derives the street from the same length).
    """
    return len(board or ()) >= 3


def render(state: AppState) -> None:
    """Render the spot input panel into the current NiceGUI slot.

    Caller wraps this in a ``ui.expansion`` panel (per ``ui/app.py``).

    The whole body is wrapped in an ``@ui.refreshable`` so that a
    full-spot mutation (loading an example spot via ``_on_load_preset``)
    can repaint the board-picker chips, both players' range inputs, and
    the stacks / blinds fields in one shot. The refresh callable is
    registered on ``state.runner._spot_input_refresh`` (mirroring the
    ``_tree_browser_refresh`` hook convention) so non-render call sites
    can trigger a redraw without owning the closure.
    """
    from nicegui import ui

    @ui.refreshable  # type: ignore[untyped-decorator]
    def _spot_input_body() -> None:
        _render_spot_input_body(state)

    runner = getattr(state, "runner", None)
    if runner is not None:
        try:
            runner._spot_input_refresh = _spot_input_body.refresh  # noqa: SLF001
        except Exception:  # noqa: BLE001 -- best-effort hook registration
            logger.debug("spot_input: could not register refresh hook on runner")

    _spot_input_body()


def _render_spot_input_body(state: AppState) -> None:
    """Render the spot-input body (refreshable inner pass of :func:`render`)."""
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
        # ----- Blinds & ante (expanded by default for discoverability) -----
        # Issue 4: users didn't realize blinds/ante were editable when this
        # was collapsed. Open by default and label it as editable.
        with ui.expansion(
            "Blinds & ante (editable)", icon="payments", value=True
        ).classes("w-full").mark("blinds-expansion"):
            _render_blinds_section(state)

        ui.separator()
        # ----- Reset + preset -----
        _render_reset_preset_row(state)


# --------------------------------------------------------------------------- #
# Board section
# --------------------------------------------------------------------------- #


def _render_board_section(state: AppState) -> None:
    """4x13 suit-by-rank board grid with selected-chip strip + clear.

    Board-chip refresh fix
    ----------------------
    The chip strip is now rendered DECLARATIVELY inline, as a direct part of
    the ``@ui.refreshable`` body (this whole function re-executes on every
    ``_spot_input_body.refresh()``), instead of via a captured-closure
    ``_redraw_chips()`` that imperatively ``clear()``ed + repopulated a
    ``chip_row``. The old imperative redraw worked at page build but produced
    an EMPTY strip after a preset/reset because the repaint was driven by the
    button's ``background_tasks.create(_trigger_spot_views_refresh(...))``
    (fire-and-forget): the deferred refresh re-ran the body but the chip strip
    repaint did not land reliably (the declaratively-bound range textarea DID
    repaint, masking the divergence). Rendering chips inline ties the strip to
    the same deterministic body re-execution that repaints every other field —
    so a preset load shows all board cards and a reset clears them, with no
    deferred-closure / stale-reference timing window.

    The per-chip remove, the grid-cell toggle, and "Clear board" each mutate
    the board then trigger the registered spot-input refresh hook (same path
    the preset/reset buttons use), so the strip repaints through the one
    refreshable mechanism rather than a second, divergent imperative one.
    """
    from nicegui import ui

    ui.label("Board").classes("font-medium")

    def _repaint_board() -> None:
        # Re-run the refreshable spot-input body (and the range matrix) so the
        # chip strip + picker cell colors reflect the mutated board. Routed
        # through the same ``ui.timer``-backed scheduler the preset/reset
        # buttons use so the repaint lands in the LIVE client/slot context
        # (a bare detached ``refresh()`` from a sync handler left the strip
        # stale until the next event-loop turn / never on the live client).
        _schedule_spot_views_refresh(state)

    # Chip strip showing selected cards with [x] remove affordance. Rendered
    # inline (not via a deferred closure) so it always matches the current
    # board on every refreshable re-execution.
    with ui.row().classes("gap-1 items-center min-h-8"):
        for c in state.current_spot.board:
            with ui.row().classes(
                "border rounded px-2 py-0 items-center gap-1 bg-gray-100 "
                "dark:bg-gray-800"
            ):
                ui.html(card_html(c))

                def _remove(_e: Any = None, card: Card = c) -> None:
                    _remove_board_card(state, card)
                    _repaint_board()

                ui.button(icon="close", on_click=_remove).props(
                    "flat dense round size=xs"
                )

    # 4x13 suit-by-rank grid.
    with ui.grid(columns=13).classes("gap-1 max-w-md"):
        for suit_idx, suit_char in enumerate(SUITS):
            for rank_idx, _rank_char in enumerate(RANKS):
                # Top-row = highest rank; reverse for visual A on left.
                rank_value = 14 - rank_idx
                card = Card(rank_value, suit_idx)
                # P1: derive the LABEL from the actual card rank so the
                # button text matches the Card it places. ``RANKS`` is
                # ascending ("23456789TJQKA"), so the iteration's
                # ``_rank_char`` (RANKS[rank_idx]) is the MIRROR of
                # ``rank_value`` (= 14 - rank_idx). Using ``_rank_char``
                # made the button labeled "As" place a "2s" (and the marker
                # was wrong too). ``RANKS[rank_value - 2]`` is the char for
                # ``rank_value`` (rank 2 -> index 0 ... rank 14 'A' -> 12).
                card_str = f"{RANKS[rank_value - 2]}{suit_char}"

                def _on_board_click(_e: Any, c: Card = card) -> None:
                    _toggle_board_card(state, c)
                    _repaint_board()

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

    def _clear_all_board(_e: Any = None) -> None:
        state.current_spot.board = []
        save_state()
        _repaint_board()

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

    with ui.row().classes("items-center gap-1"):
        ui.label("Ranges").classes("font-medium")
        ui.icon("help_outline").classes("text-gray-400 text-sm")
        ui.tooltip(
            "Set each player's hole-card range. Click cells in the 13x13 "
            "matrix to set frequency, or switch the Input toggle to String "
            "to paste a PIO-style range. Use the Detail toggle to choose "
            "whole-class (Suited/Offsuit) vs exact-suit granularity."
        )

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
    """Per-player matrix + string input + combo counter.

    Two orthogonal toggles drive this panel:

    * **Input mode** (``Matrix`` / ``String``): click cells in the 13x13
      grid, or paste a PIO-style range string. Matrix is the default.
    * **Granularity** (``Suited/Offsuit`` / ``Exact suit``): in the
      simple ``Suited/Offsuit`` mode a click sets the WHOLE hand class
      (e.g. all four ``AKs`` combos, or all twelve ``AKo`` combos) to one
      frequency — the user never picks individual suits. The advanced
      ``Exact suit`` mode opens the per-combo slider dialog so power
      users can dial in individual suit combos. Preflop (empty board)
      defaults to the simple mode per the UX brief.

    Both granularities round-trip through ``poker_solver.range``: a class
    token like ``AKs`` parses to its 4 suited combos and ``AKo`` to its
    12 offsuit combos (see ``range._add_single``), so a uniform class
    survives ``from_string``/``to_string`` losslessly at weight 1.0.
    """
    from nicegui import ui

    # Mode toggle (Matrix default per spec §4.2 adopted alternative).
    mode_state: dict[str, str] = {"mode": "Matrix"}

    # Granularity: simple "Suited/Offsuit" (class-level) vs advanced
    # "Exact suit" (per-combo dialog). Default to the simple mode preflop
    # (empty board) where exact suits rarely matter; postflop keeps the
    # same default but the advanced dialog is one right-click away.
    gran_state: dict[str, str] = {"gran": "Suited/Offsuit"}

    # ----- Input-mode + granularity toggles (made obvious per UX brief) ---
    with ui.row().classes("items-center gap-4 flex-wrap"):
        with ui.row().classes("items-center gap-1"):
            ui.label("Input:").classes("text-xs font-medium")
            mode_toggle = (
                ui.toggle(
                    ["Matrix", "String"],
                    value=mode_state["mode"],
                )
                .props("dense unelevated color=primary")
                .mark(f"range-mode-toggle-p{player}")
            )
            ui.tooltip(
                "Matrix: click cells in the 13x13 grid to set frequency. "
                "String: paste/type a PIO-style range (e.g. 'AA, AKs, "
                "76s+, AKo:0.5')."
            )
        with ui.row().classes("items-center gap-1"):
            ui.label("Detail:").classes("text-xs font-medium")
            gran_toggle = (
                ui.toggle(
                    ["Suited/Offsuit", "Exact suit"],
                    value=gran_state["gran"],
                )
                .props("dense unelevated color=primary")
                .mark(f"range-granularity-toggle-p{player}")
            )
            ui.tooltip(
                "Suited/Offsuit (simple): one click sets the whole hand "
                "class — e.g. all of AKs or all of AKo. Exact suit "
                "(advanced): opens a per-combo editor so you can pick "
                "individual suit combos. Right-click a cell always opens "
                "the exact-suit editor."
            )

    # Helper text: tell users HOW to set a range (Issue 1 discoverability).
    helper_label = ui.label("").classes("text-xs text-gray-500 italic")

    def _update_helper() -> None:
        if mode_state["mode"] == "String":
            helper_label.set_text(
                "Type or paste a range string, e.g. 'AA, KK-TT, AKs, "
                "76s+'. Switch to Matrix to click cells instead."
            )
        elif gran_state["gran"] == "Suited/Offsuit":
            helper_label.set_text(
                "Click a cell to cycle its frequency "
                "(100% → 50% → 25% → 0%); each click sets the whole "
                "suited/offsuit class. Right-click for exact suits · or "
                "switch to String to paste a range."
            )
        else:
            helper_label.set_text(
                "Exact-suit mode: click a cell to open its per-combo "
                "frequency editor (pick individual suits). Switch to "
                "Suited/Offsuit for fast whole-class clicks, or String to "
                "paste a range."
            )

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
        _update_helper()

    mode_toggle.on_value_change(_switch_mode)

    def _switch_gran(e: Any) -> None:
        gran_state["gran"] = str(e.value) or "Suited/Offsuit"
        _update_helper()

    gran_toggle.on_value_change(_switch_gran)

    # ----- Matrix input -----
    with matrix_container, ui.grid(columns=13).classes("gap-0 max-w-lg"):
        for _row, _col, label in enumerate_hand_classes():

            def _on_cell_click(_e: Any, lbl: str = label, p: int = player) -> None:
                # Granularity routes the click: simple Suited/Offsuit mode
                # cycles the whole hand class in one click; Exact-suit mode
                # opens the per-combo dialog so the user picks suits.
                if gran_state["gran"] == "Suited/Offsuit":
                    _cycle_cell_frequency(
                        state, p, lbl, counter_label, _refresh_string
                    )
                else:
                    _open_per_hand_dialog(
                        state, p, lbl, counter_label, _refresh_string
                    )

            cell = (
                ui.button(label, on_click=_on_cell_click)
                .props("flat dense")
                .classes("font-mono text-xs p-0")
            )
            cell.mark(f"range-matrix-cell-{label}")
            _color_input_cell(cell, state.current_spot.ranges[player], label)

            # PR 24b §3.1: right-click ALWAYS opens the per-combo frequency
            # dialog regardless of granularity, so exact-suit control is
            # reachable even from the simple mode. NiceGUI 3.x's
            # ``Element.on("contextmenu", ...)`` subscribes to the DOM
            # contextmenu event.
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
    # Preflop (empty board) -> default to the simple Suited/Offsuit
    # granularity per the UX brief; the toggle already initializes there,
    # so this just keeps the helper text in sync. (Postflop keeps the
    # same default; exact suits stay one right-click / toggle away.)
    if not state.current_spot.board:
        gran_state["gran"] = "Suited/Offsuit"
        gran_toggle.set_value("Suited/Offsuit")
    _update_helper()
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

    with ui.row().classes("items-center gap-1"):
        ui.label("Stack depth (BB)").classes("font-medium")
        ui.icon("help_outline").classes("text-gray-400 text-sm")
        ui.tooltip(
            "Effective stack for each player in big blinds. Edit these to "
            "change how deep the spot plays (e.g. 100 BB cash vs 20 BB "
            "short-stack). Blinds & ante are set in the section below."
        )
    ui.label("How deep each player is, in big blinds — click to edit.").classes(
        "text-xs text-gray-500 italic"
    )
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

    # Regressions 2 & 4: the on_click runs the SYNCHRONOUS mutation core
    # (``_reset_spot_core`` -> set current_spot + ``clear_results`` +
    # ``save_state`` + notify) INLINE at click time, then SCHEDULES the async
    # repaint via a ``ui.timer``. A fully-async on_click let NiceGUI defer the
    # WHOLE coroutine (mutations included) to a background task that could land
    # AFTER a same-tick solve start / OOM error, clobbering ``runner.status``
    # back to ``'idle'`` (``clear_results`` cancels + reaps the in-flight
    # worker). Running the core inline commits the mutation at click time.
    #
    # Live-refresh fix: the repaint is scheduled via
    # :func:`_schedule_spot_views_refresh` (a ``ui.timer(once=True)`` that runs
    # the awaited refresh in the live client/slot context), NOT a detached
    # ``background_tasks.create`` — the latter has no client context / no
    # connection guard, so live it left the matrix + board chips stale.
    def _reset(_e: Any = None) -> None:
        _reset_spot_core(state)
        _schedule_spot_views_refresh(state)

    ui.button(
        "Reset spot",
        icon="refresh",
        on_click=_reset,
    ).props("flat").mark("reset-spot-button")

    # Example-spots section header (Issue 3: clarify these are spot
    # CONFIGURATIONS, not pre-solved strategies — loading one sets up the
    # board/ranges/stacks; the user must still click Solve).
    with ui.row().classes("items-center gap-1 mt-2"):
        ui.label("Example spots — load, then Solve").classes(
            "text-xs font-medium"
        )
        ui.icon("help_outline").classes("text-gray-400 text-sm")
        ui.tooltip(
            "These are hand-crafted spot setups (board + ranges + stacks), "
            "NOT pre-solved strategies. Click one to load the scenario into "
            "the inputs above, then press Solve to compute the strategy."
        )
    ui.label(
        "Loads a board/range/stack setup into the inputs above. "
        "Press Solve afterward to compute the strategy."
    ).classes("text-xs text-gray-500 italic")

    # Preset dropdown.
    preset_ids = list_fixture_preset_ids()
    with ui.element("div").mark("example-spots-row"):
        for preset_id in preset_ids:
            # Marker convention: underscores in IDs become hyphens.
            marker_suffix = preset_id.replace("_", "-")

            # Regressions 2 & 4: synchronous core inline + scheduled async
            # repaint (see the ``_reset`` comment above). The mutations
            # (``_load_preset_core`` -> set current_spot + ``clear_results`` +
            # ``save_state`` + "Loaded preset" toast) commit at click time so a
            # same-tick solve/OOM is not clobbered by a deferred
            # ``clear_results``; the repaint is then scheduled via the
            # ``ui.timer``-backed :func:`_schedule_spot_views_refresh` so the
            # refreshable bodies re-execute in the LIVE client context (a
            # detached ``background_tasks.create`` left the views stale live).
            def _load_preset(_e: Any = None, pid: str = preset_id) -> None:
                if not _load_preset_core(state, pid):
                    return
                _schedule_spot_views_refresh(state)

            ui.button(
                preset_id.replace("_", " "),
                on_click=_load_preset,
            ).props("flat dense").classes("text-xs").mark(f"preset-{marker_suffix}")


def _reset_spot_core(state: AppState) -> None:
    """Synchronous core of RESET SPOT: rebuild the default spot + invalidate.

    W1/W4: the fresh ``Spot()`` defaults ``rvr_mode=False``; preserve the
    production-correct mode so a reset doesn't silently revert prod to the
    Concrete point-pair path (the ``_on_solve`` force is the authoritative
    backstop, but keeping the spot itself coherent is cheap insurance — dev
    carries the previous mode, prod is forced True).

    N2-RESET: the fresh spot is unsolved, so the previous solve's
    result/status must be dropped — otherwise the header chip (which reads
    ``runner.status`` + ``_has_result(runner)``) keeps showing "Done" for a
    spot that hasn't been solved. The 0.5s header poll repaints "Idle".

    Kept synchronous (no awaits) so the click-time STATE MUTATIONS happen
    inline; the repaint is awaited separately by :func:`_on_reset`.
    """
    from nicegui import ui

    previous = state.current_spot
    new_spot = Spot()
    # Regression 1: the fresh default ``Spot()`` is PREFLOP (empty board), so
    # ``_effective_rvr_mode`` keeps ``rvr_mode=False`` in production — RvR is
    # postflop-only and the aggregator rejects preflop spots.
    new_spot.rvr_mode = _effective_rvr_mode(previous, new_board=new_spot.board)
    state.current_spot = new_spot
    runner = getattr(state, "runner", None)
    if runner is not None:
        runner.clear_results()
    save_state()
    ui.notify("Spot reset to defaults.", type="info", position="top")


async def _on_reset(state: AppState) -> None:
    """RESET SPOT: replace the current spot with defaults, invalidate the prior
    solve, and repaint the dependent views.

    P5: ``_on_reset`` previously mutated state but never repainted, so the
    board-picker chips (and ranges) stayed stale on screen. Mirror the
    preset-load path: do the synchronous mutations in :func:`_reset_spot_core`,
    then ``await _trigger_spot_views_refresh`` so the board clears and the
    range inputs redraw to the fresh defaults inline.

    Module-level (not a render-time closure) so it is directly testable via
    ``nicegui.testing.User``.
    """
    _reset_spot_core(state)
    await _trigger_spot_views_refresh(state)


def _effective_rvr_mode(previous: Spot | None, new_board: Any = None) -> bool:
    """W1/W4: the ``rvr_mode`` a freshly-built (re)loaded spot should carry.

    Only meaningful when rebuilding from an EXISTING spot (preset load / reset
    — ``previous`` is the spot being replaced). In that case:

      * Production (dev-gate OFF): Range-vs-range — but ONLY for a POSTFLOP
        spot (``new_board`` has 3/4/5 cards). RvR is a postflop concept; the
        aggregator raises ``ValueError`` for a preflop spot, so a freshly-built
        PREFLOP spot must keep ``rvr_mode=False`` (Regression 1).
      * Dev (gate ON): carry the previous spot's ``rvr_mode`` so the user's
        Concrete/RvR toggle choice survives the rebuild.

    ``new_board`` is the board of the spot being CONSTRUCTED (not ``previous``);
    the production RvR force keys off it so a preflop reset/preset stays
    Concrete-routed. When omitted (legacy callers), it defaults to None →
    preflop, so the force is conservative (only postflop spots get RvR).

    When ``previous is None`` there is no UI session to preserve — the caller is
    constructing a standalone spot (e.g. a duck-typed test fixture), so keep the
    dataclass default (False) rather than imposing the production RvR force.
    The authoritative production guarantee lives in ``ui.app._on_solve``, which
    re-forces RvR (postflop-gated) at the dispatch point regardless of how the
    spot was built.
    """
    if previous is None:
        return bool(getattr(Spot(), "rvr_mode", False))
    if not _concrete_dev_enabled():
        return _board_is_postflop(new_board)
    return bool(getattr(previous, "rvr_mode", False))


def _load_preset_core(state: AppState, preset_id: str) -> bool:
    """Synchronous core of the preset-load path (W3).

    Does ALL the click-time STATE MUTATIONS inline — ``load_fixture_config``,
    ``fixture_default_ranges``, :func:`_spot_from_config`,
    ``state.current_spot = new_spot``, ``runner.clear_results()``,
    ``save_state()`` and the "Loaded preset" / error toasts — and returns
    ``True`` on success / ``False`` if the load aborted (so the async wrapper
    knows whether to repaint).

    W3: previously the whole load was a single ``async def`` whose ``on_click``
    awaited it; NiceGUI deferred the entire coroutine to a background task, so
    the mutations weren't synchronous with the click (which also caused the
    earlier slot-teardown notify error). Splitting the synchronous mutations
    out here — with only the repaint left async in :func:`_on_load_preset` —
    makes the mutations happen inline at click time.

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
        return False
    if config is None:
        ui.notify(
            f"Preset {preset_id} unavailable (mock_solver not yet wired).",
            type="warning",
            position="top",
        )
        return False

    # Fetch the preset's explicit per-player ranges, if any. The
    # range-vs-range FLOP/TURN/PREFLOP example spots carry no concrete
    # hole cards on their config; without these strings the load would
    # inherit the previous spot's ranges (a 1-combo river subgame, or the
    # full 1326-combo default — the memory wall). ``None`` for hole-card
    # anchored fixtures, which keep their concrete-combo behavior.
    try:
        default_ranges = fixture_default_ranges(preset_id)
    except (KeyError, ValueError):
        default_ranges = None

    # Materialize the config into the current spot. This now syncs the
    # WHOLE spot — board, BOTH players' ranges, stacks, and blinds — so the
    # board-picker chips and the range matrix match the loaded scenario
    # (previously only board/stacks/bet-sizes were copied and the UI never
    # repainted, so chips + ranges stayed on the old values).
    new_spot = _spot_from_config(
        config, previous=state.current_spot, default_ranges=default_ranges
    )
    state.current_spot = new_spot
    # N2-RESET: a freshly-loaded preset is unsolved — invalidate the prior
    # solve's result/status so the header chip doesn't read "Done" for a spot
    # that hasn't been solved yet. The 0.5s header poll repaints "Idle".
    runner = getattr(state, "runner", None)
    if runner is not None:
        runner.clear_results()
    save_state()

    # G3b: emit the success toast BEFORE the refresh (which the async wrapper
    # awaits). ``_trigger_spot_views_refresh`` re-renders the
    # ``@ui.refreshable`` bodies, tearing down + recreating their slots; once
    # that has happened, the click handler's original slot context is gone and
    # ``ui.notify`` resolves ``context.client`` through a deleted slot, raising
    # ``RuntimeError: The parent element this slot belongs to has been
    # deleted.`` (the load itself still succeeds; only the toast errored).
    # Notifying here — while the handler's slot is still valid — both fixes the
    # traceback and surfaces the toast a beat sooner.
    ui.notify(f"Loaded preset: {preset_id}", type="info", position="top")
    return True


async def _on_load_preset(state: AppState, preset_id: str) -> None:
    """Load a preset: synchronous mutations + async repaint (W3 + G3).

    W3: the click-time STATE MUTATIONS run synchronously via
    :func:`_load_preset_core`; only the dependent-view REPAINT stays async.

    G3: the repaint (:func:`_trigger_spot_views_refresh`) must be *awaited*:
    ``@ui.refreshable.refresh()`` returns an ``AwaitableResponse`` that, left
    un-awaited, defers the actual re-render to a fire-and-forget background
    task — so the freshly-loaded ranges only show up on the *next* event-loop
    turn (or never, if the slot churns first). That deferral was the G3
    staleness: the left range matrix + the right range editor kept their
    pre-load look even though ``state.current_spot.ranges`` was already
    updated. Awaiting forces the re-render to complete inline.
    """
    if not _load_preset_core(state, preset_id):
        return
    # Repaint the dependent views. The spot-input panel (board chips +
    # range inputs + stacks/blinds) and the range matrix each render once
    # at page build and otherwise only redraw via their own refresh hooks,
    # so without these calls the freshly-loaded spot would be invisible.
    await _trigger_spot_views_refresh(state)


def _schedule_spot_views_refresh(state: AppState) -> None:
    """Schedule the spot-views repaint from a SYNCHRONOUS event handler.

    Live-refresh fix
    ----------------
    A sync ``on_click`` must (a) run the click-time mutations inline (so a
    same-tick ``start()`` / OOM is not clobbered by a deferred
    ``clear_results`` — smoke tests #2/#4) and then (b) trigger an
    ``@ui.refreshable`` repaint that ACTUALLY re-executes the bodies in the
    LIVE client context. The previous
    ``background_tasks.create(_trigger_spot_views_refresh(state))`` satisfied
    (a) but NOT (b) live: ``background_tasks.create`` spawns a *detached*
    asyncio task with NO client/slot context and NO client-connection guard,
    so on the real (websocket) client the awaited ``refresh()`` re-render did
    not land — the matrix kept the old range and the board chip strip stayed
    empty even though ``state.current_spot`` had updated.

    The NiceGUI-correct mechanism is ``ui.timer(interval, cb, once=True)``: the
    *element* timer (``nicegui.elements.timer.Timer``)

      * runs ``cb`` INSIDE its ``parent_slot`` (the live client/slot context),
        not a contextless detached task, so the refreshable re-render targets
        the connected client's element tree (``Timer._get_context``); and
      * awaits ``client.connected()`` before firing (``Timer._can_start`` —
        NiceGUI issue #206), the exact guard a bare ``background_tasks.create``
        lacks and the reason the old path silently no-op'd live.

    The timer is created HERE, while the sync handler's slot context is still
    active, so its ``parent_slot`` resolves to the live client. ``once=True``
    fires it a single time after a short delay; the callback awaits
    :func:`_trigger_spot_views_refresh` so every refreshable body re-executes
    inline within the client context. Mutations already committed inline before
    this call, so the synchronous-at-click contract (smoke #2/#4) is preserved.
    """
    from nicegui import ui

    async def _do_refresh() -> None:
        await _trigger_spot_views_refresh(state)

    try:
        # Small non-zero interval so it fires on the next timer tick; ``once``
        # tears the timer down after a single invocation.
        ui.timer(0.01, _do_refresh, once=True)
    except Exception:  # noqa: BLE001 -- no slot/client context (e.g. unit test)
        # Fall back to a detached task so non-UI callers (or a torn-down slot)
        # still attempt the repaint rather than silently skipping it.
        from nicegui import background_tasks

        background_tasks.create(_do_refresh())


async def _trigger_spot_views_refresh(state: AppState) -> None:
    """Fire (and await) the spot-input + range-matrix refresh hooks.

    Each view's ``render`` parks its ``@ui.refreshable`` refresh callable on
    the runner (``_spot_input_refresh`` / ``_range_matrix_refresh``);
    ``state.matrix_refresh`` is the matrix hook under the name ``tree_browser``
    also uses. We call whichever are present and never let a missing hook (or a
    torn-down slot during a tab switch) raise.

    Each hook returns a NiceGUI ``AwaitableResponse``. We **await** it (its
    contract requires awaiting immediately after creation, or not at all) so
    the re-render runs INLINE rather than as a deferred fire-and-forget task.
    Without the await the body re-execution is punted to the next event-loop
    turn, which is the G3 bug: the panes kept their stale pre-load look because
    nothing in the synchronous click path ever pumped the deferred task.
    """
    runner = getattr(state, "runner", None)
    hooks = []
    if runner is not None:
        hooks.append(getattr(runner, "_spot_input_refresh", None))
        hooks.append(getattr(runner, "_range_matrix_refresh", None))
    hooks.append(getattr(state, "matrix_refresh", None))
    seen: set[int] = set()
    for hook in hooks:
        if not callable(hook) or id(hook) in seen:
            continue
        seen.add(id(hook))
        try:
            response = hook()
            # ``refresh()`` returns an AwaitableResponse; await it so the
            # re-render completes synchronously. Older/foreign hooks may return
            # a plain value (or None) — only await genuine awaitables.
            if inspect.isawaitable(response):
                await response
        except Exception:  # noqa: BLE001 -- best-effort; slot may be gone
            logger.debug("spot-load refresh hook raised", exc_info=True)


def _ranges_from_config(
    config: Any,
    previous: Spot | None,
    default_ranges: tuple[str, str] | None = None,
) -> tuple[RangeWithFreqs, RangeWithFreqs]:
    """Derive both players' ranges for a freshly-loaded preset.

    Resolution order:

    1. ``default_ranges`` — explicit ``(oop_range_str, ip_range_str)`` the
       preset attaches for range-vs-range FLOP/TURN/PREFLOP example spots
       (no concrete hole cards). Parsed via ``RangeWithFreqs.from_string``
       so the loaded spot is a real, deterministic, tractable range-vs-range
       scenario regardless of what the previous spot held.
    2. ``config.initial_hole_cards`` — the concrete point-pair a river
       subgame fixture is anchored on; each player's range becomes exactly
       that combo so the loaded spot is a coherent concrete subgame.
    3. The previous spot's ranges, if any (preserve user edits).
    4. Full ranges as a last resort.

    Step 1 takes precedence over the hole-card path because a preset that
    ships explicit ranges is declaring itself a range-vs-range spot.
    """
    if default_ranges is not None and len(default_ranges) == 2:
        oop_str, ip_str = default_ranges
        try:
            return (
                RangeWithFreqs.from_string(oop_str),
                RangeWithFreqs.from_string(ip_str),
            )
        except Exception:  # noqa: BLE001 -- malformed spec; fall through
            logger.warning(
                "preset default ranges failed to parse; falling back",
                exc_info=True,
            )
    hole = getattr(config, "initial_hole_cards", ()) or ()
    if isinstance(hole, (tuple, list)) and len(hole) == 2:
        ranges: list[RangeWithFreqs] = []
        for pair in hole:
            rw = RangeWithFreqs.empty()
            try:
                rw.set_frequency((pair[0], pair[1]), 1.0)
            except Exception:  # noqa: BLE001 -- malformed pair; fall back
                rw = RangeWithFreqs.full()
            ranges.append(rw)
        return (ranges[0], ranges[1])
    # No concrete hole cards: keep whatever the user had, else full ranges.
    if previous is not None and getattr(previous, "ranges", None):
        prev = previous.ranges
        if isinstance(prev, (tuple, list)) and len(prev) == 2:
            return (prev[0], prev[1])
    return (RangeWithFreqs.full(), RangeWithFreqs.full())


def _spot_from_config(
    config: Any,
    previous: Spot | None = None,
    default_ranges: tuple[str, str] | None = None,
) -> Spot:
    """Build a ``Spot`` from a ``HUNLConfig`` (preset load helper).

    Syncs board, both players' ranges (derived via :func:`_ranges_from_config`),
    stacks, blinds, ante, and bet sizes from the preset config so the whole
    spot — not just the board — reflects the loaded scenario. ``default_ranges``
    carries the preset's explicit per-player range strings (range-vs-range
    fixtures) through to :func:`_ranges_from_config`.
    """
    board = list(config.initial_board)
    starting_stack = config.starting_stack
    big_blind = config.big_blind
    stacks_bb = (int(starting_stack / big_blind), int(starting_stack / big_blind))
    return Spot(
        board=board,
        ranges=_ranges_from_config(config, previous, default_ranges),
        stacks_bb=stacks_bb,
        sb_blind=config.small_blind / big_blind,
        bb_blind=1.0,
        ante=config.ante / big_blind if big_blind else 0.0,
        bet_sizes=tuple(config.bet_size_fractions),
        bet_sizes_checked=tuple(config.bet_size_fractions),
        include_all_in=config.include_all_in,
        preflop_raise_cap=config.preflop_raise_cap,
        postflop_raise_cap=config.postflop_raise_cap,
        # W1/W4: a fresh ``Spot`` defaults ``rvr_mode=False``; without this the
        # loaded prod spot would silently route the Concrete point-pair path
        # (until ``_on_solve`` re-forces it). Production -> True for a POSTFLOP
        # board (Regression 1: a preflop preset stays Concrete-routed — the
        # RvR aggregator rejects preflop spots); dev -> carry the previous
        # spot's mode.
        rvr_mode=_effective_rvr_mode(previous, new_board=board),
    )


__all__ = ["render"]
