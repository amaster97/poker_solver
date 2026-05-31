"""Auto range generation tests (Spot Input panel).

Covers the engine-LIGHT "auto-fill range" feature added to the Spot Input
panel: a control that projects a chosen standard preflop-blueprint position/line
(e.g. "BTN/SB open (RFI)", "BB 3-bet vs open") into the ACTIVE player's range
slot at the spot's current stack depth.

Two layers:

  1. **Derivation logic** (``ui.views._auto_range``): the standard line catalog,
     and that :func:`derive_range_string` projects a real, non-trivial range
     (combo count > 20 and < 1326) for a standard line — and that the derived
     range matches the blueprint's own per-class projection for that line.
  2. **UI wiring** (``ui.views.spot_input``, via ``nicegui.testing.User``): the
     ``auto-range-*`` controls render, and applying an auto-range fills the
     active player's range to that same non-trivial range.

The derivation tests need the real blueprint bundle on disk
(``assets/blueprints/manifest.json``); they skip cleanly if it is absent so the
suite stays green on a machine without the asset (the UI wiring tests do not
depend on the bundle — they assert the controls render and, when a bundle is
present, that apply fills a sane range).
"""

from __future__ import annotations

import pathlib
from collections.abc import Iterator

import pytest

pytest.importorskip("nicegui")

# ruff: noqa: E402, I001  (post-importorskip imports must follow the skip)
from nicegui.testing import User

from ui.blueprint_router import BlueprintRouter, default_asset_dir
from ui.views._auto_range import (
    STANDARD_LINES,
    AutoRangeLine,
    derive_range_string,
    find_line,
    line_options,
)

pytest_plugins = [
    "nicegui.testing.general_fixtures",
    "nicegui.testing.user_plugin",
]

pytestmark = [
    pytest.mark.ui,
    pytest.mark.nicegui_main_file("ui/app.py"),
]


def _bundle_available() -> bool:
    return BlueprintRouter.from_asset_dir(default_asset_dir()) is not None


_requires_bundle = pytest.mark.skipif(
    not _bundle_available(),
    reason="no preflop blueprint bundle on disk (assets/blueprints/manifest.json)",
)


@pytest.fixture
def isolated_state_dir(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[pathlib.Path]:
    """Override HOME so state.json lands in tmp_path; reset runner."""
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


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


def test_standard_lines_catalog_is_non_empty_and_unique() -> None:
    """The standard line catalog exposes a few extensible entries with unique
    ids that all map to known action buckets."""
    assert len(STANDARD_LINES) >= 2
    ids = [ln.id for ln in STANDARD_LINES]
    assert len(ids) == len(set(ids)), "line ids must be unique"
    for ln in STANDARD_LINES:
        assert isinstance(ln, AutoRangeLine)
        assert ln.kinds <= {"fold", "call", "raise", "jam"}
        assert 0.0 < ln.threshold <= 1.0
    # The option map mirrors the catalog and round-trips through find_line.
    opts = line_options()
    assert set(opts) == set(ids)
    for lid in ids:
        assert find_line(lid) is not None
    assert find_line("definitely_not_a_line") is None


# ---------------------------------------------------------------------------
# Derivation
# ---------------------------------------------------------------------------


@_requires_bundle
@pytest.mark.parametrize(
    "line_id", ["btn_open", "bb_3bet_vs_open", "bb_call_vs_open"]
)
def test_derive_range_is_real_and_non_trivial(line_id: str) -> None:
    """A standard line at 100 BB projects to a real opening/defending range:
    combo count > 20 and < 1326 (not empty, not the full deck)."""
    router = BlueprintRouter.from_asset_dir(default_asset_dir())
    result = derive_range_string(router, line_id=line_id, stack_bb=100, ante=0.0)
    assert result.range_string, f"{line_id} derived an empty range"
    assert 20 < result.combo_count < 1326, (
        f"{line_id} combo count {result.combo_count} is not a real range"
    )
    assert result.source in ("blueprint", "interpolated")
    # The range string parses cleanly and its combo count matches the report.
    from ui.state import RangeWithFreqs

    rw = RangeWithFreqs.from_string(result.range_string)
    parsed = sum(
        1 for c in rw.base_range.combos if rw.frequency_of(c) > 0.0
    )
    assert parsed == result.combo_count


@_requires_bundle
def test_off_anchor_depth_interpolates() -> None:
    """An off-anchor depth (50 BB, between the 40/60 BB shards) interpolates
    rather than refusing — and still yields a non-trivial range."""
    router = BlueprintRouter.from_asset_dir(default_asset_dir())
    result = derive_range_string(router, line_id="btn_open", stack_bb=50, ante=0.0)
    assert result.source == "interpolated"
    assert 20 < result.combo_count < 1326


@_requires_bundle
def test_derived_range_matches_blueprint_projection() -> None:
    """The derived BTN open range is exactly the set of classes whose
    blueprint raise+jam mass clears the line threshold — i.e. it matches the
    blueprint's own per-class projection for that line."""
    from ui.views.preflop_chart import classify_action

    router = BlueprintRouter.from_asset_dir(default_asset_dir())
    line = find_line("btn_open")
    assert line is not None
    info = router.lookup_chart(stack_bb=100, ante=0.0, action_history="")
    # Recompute the expected class set independently from the blueprint.
    expected: set[str] = set()
    for cls, amap in info.per_class.items():
        total = sum(amap.values())
        if total <= 0:
            continue
        in_mass = sum(
            v for a, v in amap.items() if classify_action(a) in line.kinds
        )
        if in_mass / total >= line.threshold:
            expected.add(cls)

    result = derive_range_string(router, line_id="btn_open", stack_bb=100, ante=0.0)
    assert set(result.classes) == expected
    assert expected, "expected a non-empty projection"


def test_no_bundle_returns_clear_note() -> None:
    """With no router (no bundle), derivation returns an empty range + a note
    rather than crashing."""
    result = derive_range_string(None, line_id="btn_open", stack_bb=100, ante=0.0)
    assert result.range_string == ""
    assert result.note
    assert result.source == "unavailable"


def test_unknown_line_returns_note() -> None:
    router = BlueprintRouter.from_asset_dir(default_asset_dir())
    result = derive_range_string(router, line_id="nope", stack_bb=100, ante=0.0)
    assert result.range_string == ""
    assert result.note


# ---------------------------------------------------------------------------
# UI wiring (nicegui.testing.User)
# ---------------------------------------------------------------------------


async def test_auto_range_controls_render(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """The auto-range row + dropdown + apply button render in the Spot Input
    panel (the Solver tab's Spot Input expansion is open by default)."""
    await user.open("/")
    assert len(user.find(marker="auto-range-row").elements) >= 1, (
        "auto-range-row marker missing"
    )
    assert len(user.find(marker="auto-range-select").elements) >= 1, (
        "auto-range-select marker missing"
    )
    assert len(user.find(marker="auto-range-apply").elements) >= 1, (
        "auto-range-apply marker missing"
    )


@_requires_bundle
async def test_apply_auto_range_fills_active_player(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Applying an auto-range fills the ACTIVE (hero) player's range slot with a
    real, non-trivial range matching the blueprint projection."""
    from ui.state import get_state
    from ui.views import spot_input

    await user.open("/")
    state = get_state()
    # Default spot: 100 BB, hero_player = 0. Start from an empty range so we can
    # see the fill take effect.
    from ui.state import RangeWithFreqs

    spot = state.current_spot
    ranges = list(spot.ranges)
    ranges[spot.hero_player] = RangeWithFreqs.empty()
    spot.ranges = (ranges[0], ranges[1])

    # Independent expectation: what the blueprint projects for this line/depth.
    router = BlueprintRouter.from_asset_dir(default_asset_dir())
    expected = derive_range_string(
        router, line_id="btn_open", stack_bb=100, ante=0.0
    )
    assert expected.range_string

    # Apply via the module entry point (bypasses dropdown click ergonomics,
    # mirroring how the preflop-chart test stashes selection directly).
    spot_input._apply_auto_range(state, "btn_open")

    hero = state.current_spot.hero_player
    rw = state.current_spot.ranges[hero]
    filled = sum(1 for c in rw.base_range.combos if rw.frequency_of(c) > 0.0)
    assert 20 < filled < 1326, f"filled combo count {filled} is not a real range"
    assert filled == expected.combo_count


@_requires_bundle
async def test_apply_auto_range_respects_hero_seat(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Auto-fill targets the ACTIVE player: flipping hero to P1 fills P1, not
    P0, and leaves P0 untouched."""
    from ui.state import RangeWithFreqs, get_state
    from ui.views import spot_input

    await user.open("/")
    state = get_state()
    spot = state.current_spot
    # Make both ranges empty, then set hero = P1.
    spot.ranges = (RangeWithFreqs.empty(), RangeWithFreqs.empty())
    spot.hero_player = 1

    spot_input._apply_auto_range(state, "bb_3bet_vs_open")

    p0 = state.current_spot.ranges[0]
    p1 = state.current_spot.ranges[1]
    n0 = sum(1 for c in p0.base_range.combos if p0.frequency_of(c) > 0.0)
    n1 = sum(1 for c in p1.base_range.combos if p1.frequency_of(c) > 0.0)
    assert n0 == 0, "P0 (non-hero) range should be untouched"
    assert 20 < n1 < 1326, f"P1 (hero) range {n1} is not a real range"
