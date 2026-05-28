"""B10 Phase C — GUI per-combo intensity editor smoke tests.

Covers the four Phase C deliverables (spec
``docs/b10_per_combo_frequency_plan_2026-05-28.md`` §4):

1. ``RangeWithFreqs`` delegates ``frequency_of`` / ``set_frequency`` to
   the canonical ``Range.weight`` / ``Range.set_weight`` store
   (``frequencies`` dict removed).
2. Old-format state.json with a ``frequencies: {...}`` payload upgrades
   cleanly via ``_apply_spot_payload`` -> ``_migrate_legacy_freq_dict``.
3. Session round-trip: edit weights -> serialize -> reload preserves
   them. Serializer NEVER emits the legacy ``frequencies`` key.
4. ``cell_strategy_summary`` reports an ``avg_weight`` field that the
   matrix renderer fades toward grey when ``< 1.0``.

Engine code is untouched here — Phase A (#149) + Phase B (#154) already
landed the data model + solver wiring; this PR's surface is the UI
layer only.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest

from poker_solver.card import Card
from ui.state import (
    RangeWithFreqs,
    Spot,
    _apply_spot_payload,
    _migrate_legacy_freq_dict,
    _serialize_state,
    enumerate_combos,
)
from ui.views.range_matrix import CellSummary, cell_color, cell_strategy_summary


# ---------------------------------------------------------------------------
# Delegation tests — frequencies dict removed; round-trips via Range._weight.
# ---------------------------------------------------------------------------


def test_range_with_freqs_has_no_frequencies_attr() -> None:
    """Smoke 1: the legacy ``frequencies`` dict no longer exists on the
    dataclass — it was the entire point of B10 Phase C migration."""

    rw = RangeWithFreqs.empty()
    assert not hasattr(rw, "frequencies"), (
        "RangeWithFreqs.frequencies dict must be removed in B10 Phase C; "
        "canonical store is Range._weight"
    )


def test_set_frequency_writes_through_to_range_weight() -> None:
    """Smoke 2: ``set_frequency(combo, freq)`` calls into
    ``Range.set_weight``. The underlying ``Range._weight`` mirrors the
    UI-facing read."""

    rw = RangeWithFreqs.empty()
    combo = enumerate_combos("AKo")[2]
    rw.set_frequency(combo, 0.42)

    # UI-facing read.
    assert abs(rw.frequency_of(combo) - 0.42) < 1e-9
    # Underlying canonical store.
    assert abs(rw.base_range.weight(combo) - 0.42) < 1e-9


def test_set_frequency_clamps_to_unit_interval() -> None:
    """Smoke 3: out-of-band values clamp to ``[0.0, 1.0]`` (matches
    pre-Phase-C UX contract; the bare ``Range.set_weight`` would raise)."""

    rw = RangeWithFreqs.empty()
    combo = enumerate_combos("AA")[0]
    rw.set_frequency(combo, 2.5)
    assert rw.frequency_of(combo) == 1.0
    rw.set_frequency(combo, -0.5)
    assert rw.frequency_of(combo) == 0.0


def test_full_range_returns_unit_weights() -> None:
    """Smoke 4: ``RangeWithFreqs.full()`` yields 1326 combos each at
    weight 1.0 — back-compat with PR 10's all-1.0 default."""

    rw = RangeWithFreqs.full()
    assert len(rw.base_range.combos) == 1326
    # Sample a handful; check unit weight.
    for combo in rw.base_range.combos[:10]:
        assert rw.frequency_of(combo) == 1.0


def test_from_string_returns_unit_weights() -> None:
    """Smoke 5: parsing a token range gives unit weights (no fractional
    syntax in the simple matrix UI path)."""

    rw = RangeWithFreqs.from_string("AA, KK, AKs")
    for combo in rw.base_range.combos:
        assert rw.frequency_of(combo) == 1.0


# ---------------------------------------------------------------------------
# Legacy ``frequencies: {...}`` migration.
# ---------------------------------------------------------------------------


def test_migrate_legacy_freq_dict_writes_through() -> None:
    """Smoke 6: a pre-Phase-C ``frequencies`` dict (4-char string keys,
    float values) round-trips through ``_migrate_legacy_freq_dict``."""

    rw = RangeWithFreqs.empty()
    legacy = {
        "AsKs": 0.3,
        "AdKd": 0.7,
        "QhJh": 1.0,
    }
    _migrate_legacy_freq_dict(rw, legacy)

    # Suit index convention (poker_solver.card.SUITS): 0=s, 1=h, 2=d, 3=c.
    assert abs(rw.frequency_of((Card(14, 0), Card(13, 0))) - 0.3) < 1e-9
    assert abs(rw.frequency_of((Card(14, 2), Card(13, 2))) - 0.7) < 1e-9
    assert abs(rw.frequency_of((Card(12, 1), Card(11, 1))) - 1.0) < 1e-9


def test_migrate_legacy_freq_dict_ignores_malformed() -> None:
    """Smoke 7: malformed entries (bad keys, non-numeric weights) are
    skipped — never crash."""

    rw = RangeWithFreqs.empty()
    legacy: dict[str, Any] = {
        "AsKs": 0.5,  # OK
        "garbage": 0.5,  # bad key
        "AhKh": "not-a-number",  # bad value
        "Q": 0.5,  # too short
    }
    _migrate_legacy_freq_dict(rw, legacy)

    # The one good entry made it through.
    assert abs(rw.frequency_of((Card(14, 0), Card(13, 0))) - 0.5) < 1e-9
    # The malformed entries did NOT contribute extra combos.
    n_with_weight = sum(
        1 for combo in rw.base_range.combos if rw.frequency_of(combo) > 0.0
    )
    assert n_with_weight == 1


def test_apply_spot_payload_legacy_format() -> None:
    """Smoke 8: a saved-session payload using the legacy ``frequencies``
    field upgrades to canonical ``Range._weight`` storage."""

    spot = Spot()
    legacy_payload = {
        "ranges": [
            {"frequencies": {"AsKs": 0.25, "AhKh": 0.75}},
            {"frequencies": {"7d2c": 0.4}},
        ],
    }
    _apply_spot_payload(spot, legacy_payload)

    p0, p1 = spot.ranges
    # Suit index convention (poker_solver.card.SUITS): 0=s, 1=h, 2=d, 3=c.
    assert abs(p0.frequency_of((Card(14, 0), Card(13, 0))) - 0.25) < 1e-9
    assert abs(p0.frequency_of((Card(14, 1), Card(13, 1))) - 0.75) < 1e-9
    assert abs(p1.frequency_of((Card(7, 2), Card(2, 3))) - 0.4) < 1e-9


def test_apply_spot_payload_canonical_format() -> None:
    """Smoke 9: the new ``weights`` field encoding works identically —
    legacy + canonical share the same migration path so both
    round-trip."""

    spot = Spot()
    canonical_payload = {
        "ranges": [
            {"weights": {"AsKs": 0.6}},
            {"weights": {"QhJh": 0.3}},
        ],
    }
    _apply_spot_payload(spot, canonical_payload)

    p0, p1 = spot.ranges
    assert abs(p0.frequency_of((Card(14, 0), Card(13, 0))) - 0.6) < 1e-9
    assert abs(p1.frequency_of((Card(12, 1), Card(11, 1))) - 0.3) < 1e-9


# ---------------------------------------------------------------------------
# Session round-trip.
# ---------------------------------------------------------------------------


def test_session_round_trip_preserves_per_combo_weights(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """Smoke 10: edit dialog -> save -> reload preserves weights.

    Mimics the dialog save path (``rw.set_frequency`` per combo) +
    drives the module-level serializer + loader directly. The state-
    file path is monkey-patched to land in ``tmp_path`` so the test
    is hermetic.
    """
    import ui.state as state_mod

    state_path = tmp_path / "state.json"
    monkeypatch.setattr(state_mod, "_STATE_FILE", state_path)
    monkeypatch.setattr(state_mod, "_STATE_DIR", tmp_path)

    # --- Phase 1: edit via the per-combo dialog's save semantics. ---
    state_mod.reset_state_for_testing()
    state = state_mod.get_state()
    rw = RangeWithFreqs.empty()
    aa_combos = enumerate_combos("AA")
    rw.set_frequency(aa_combos[0], 0.25)
    rw.set_frequency(aa_combos[1], 0.75)
    rw.set_frequency(aa_combos[2], 1.0)
    state.current_spot.ranges = (rw, RangeWithFreqs.full())

    payload = _serialize_state(state)
    # Serializer must use the canonical ``weights`` key, never the
    # legacy ``frequencies``.
    spot_payload = payload.get("current_spot")
    assert spot_payload is not None, (
        "fractional ranges should trigger spot serialization"
    )
    for entry in spot_payload["ranges"]:
        assert "frequencies" not in entry, (
            "serializer must never emit the legacy ``frequencies`` key"
        )
        assert "weights" in entry

    # Write + reload via the standard loader.
    state_path.write_text(json.dumps(payload), encoding="utf-8")
    state_mod.reset_state_for_testing()
    state2 = state_mod.get_state()

    # --- Phase 2: weights survived. ---
    rw2 = state2.current_spot.ranges[0]
    assert abs(rw2.frequency_of(aa_combos[0]) - 0.25) < 1e-9
    assert abs(rw2.frequency_of(aa_combos[1]) - 0.75) < 1e-9
    assert abs(rw2.frequency_of(aa_combos[2]) - 1.0) < 1e-9


def test_session_round_trip_legacy_format_upgrades(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """Smoke 11: a state.json *handwritten* in the legacy ``frequencies``
    format loads cleanly + the next save strips the legacy key."""

    import ui.state as state_mod

    state_path = tmp_path / "state.json"
    monkeypatch.setattr(state_mod, "_STATE_FILE", state_path)
    monkeypatch.setattr(state_mod, "_STATE_DIR", tmp_path)

    # Hand-write a pre-Phase-C state.json. The schema version is the
    # current ``_STATE_VERSION``; the only "old" bit is the per-range
    # ``frequencies`` encoding inside ``current_spot``.
    legacy_state = {
        "version": state_mod._STATE_VERSION,
        "prefs": {},
        "current_spot": {
            "ranges": [
                {"frequencies": {"AsAh": 0.5, "AdAc": 0.5}},
                {"frequencies": {"KsKh": 1.0}},
            ],
        },
    }
    state_path.write_text(json.dumps(legacy_state), encoding="utf-8")

    state_mod.reset_state_for_testing()
    state = state_mod.get_state()

    p0 = state.current_spot.ranges[0]
    p1 = state.current_spot.ranges[1]
    # AsAh -> (Card(14, 0), Card(14, 1)); AdAc -> (Card(14, 2), Card(14, 3))
    assert abs(p0.frequency_of((Card(14, 0), Card(14, 1))) - 0.5) < 1e-9
    assert abs(p0.frequency_of((Card(14, 2), Card(14, 3))) - 0.5) < 1e-9
    # KsKh -> (Card(13, 0), Card(13, 1))
    assert abs(p1.frequency_of((Card(13, 0), Card(13, 1))) - 1.0) < 1e-9

    # Re-serialize: legacy field must not appear.
    payload = _serialize_state(state)
    spot_payload = payload.get("current_spot")
    assert spot_payload is not None
    for entry in spot_payload["ranges"]:
        assert "frequencies" not in entry


# ---------------------------------------------------------------------------
# Matrix saturation.
# ---------------------------------------------------------------------------


def test_cell_summary_avg_weight_field_exists() -> None:
    """Smoke 12: ``CellSummary`` carries an ``avg_weight`` field that
    defaults to 1.0 (back-compat: legacy ranges render at full
    saturation)."""

    s = CellSummary()
    assert s.avg_weight == 1.0


def test_cell_strategy_summary_avg_weight_all_unit() -> None:
    """Smoke 13: an all-1.0 hand class yields ``avg_weight == 1.0``."""

    rw = RangeWithFreqs.empty()
    for combo in enumerate_combos("AKs"):
        rw.set_frequency(combo, 1.0)

    summary = cell_strategy_summary(
        hand_class="AKs",
        range_=rw,
        board=[],
        strategy={},
        tree_node_id="root",
        game_state_snapshot=object(),
    )
    assert summary.combo_count == 4
    assert abs(summary.avg_weight - 1.0) < 1e-9


def test_cell_strategy_summary_avg_weight_half() -> None:
    """Smoke 14: half the combos at 1.0, half at 0.5 -> ``avg_weight ==
    0.75`` (deterministic check; the renderer fades the cell color
    toward grey at this saturation)."""

    rw = RangeWithFreqs.empty()
    aks_combos = enumerate_combos("AKs")
    rw.set_frequency(aks_combos[0], 1.0)
    rw.set_frequency(aks_combos[1], 1.0)
    rw.set_frequency(aks_combos[2], 0.5)
    rw.set_frequency(aks_combos[3], 0.5)

    summary = cell_strategy_summary(
        hand_class="AKs",
        range_=rw,
        board=[],
        strategy={},
        tree_node_id="root",
        game_state_snapshot=object(),
    )
    assert summary.combo_count == 4
    assert abs(summary.avg_weight - 0.75) < 1e-9


def test_cell_color_unit_weight_matches_pre_phase_c() -> None:
    """Smoke 15: full-saturation cell color is bit-for-bit the pre-Phase-C
    blend — back-compat invariant for all-1.0 ranges."""

    s = CellSummary(fold=0.0, call=0.0, raise_=1.0, combo_count=4, avg_weight=1.0)
    # Pure raise -> r=40 g=180 b=60 (per spec §7.3 anchors).
    assert cell_color(s) == "rgb(40,180,60)"


def test_cell_color_fades_with_low_avg_weight() -> None:
    """Smoke 16: a half-saturated cell fades halfway toward grey (~58,
    58, 58)."""

    s_full = CellSummary(fold=0.0, call=0.0, raise_=1.0, combo_count=4, avg_weight=1.0)
    s_half = CellSummary(fold=0.0, call=0.0, raise_=1.0, combo_count=4, avg_weight=0.5)
    s_zero = CellSummary(fold=0.0, call=0.0, raise_=1.0, combo_count=4, avg_weight=0.0)

    # Full saturation: r=40 g=180 b=60.
    assert cell_color(s_full) == "rgb(40,180,60)"
    # Half: lerp halfway to grey (58).
    # r = 40 * 0.5 + 58 * 0.5 = 49
    # g = 180 * 0.5 + 58 * 0.5 = 119
    # b = 60 * 0.5 + 58 * 0.5 = 59
    assert cell_color(s_half) == "rgb(49,119,59)"
    # Zero: fully grey.
    assert cell_color(s_zero) == "rgb(58,58,58)"


def test_cell_color_blocked_overrides_avg_weight() -> None:
    """Smoke 17: blocked / out-of-range / empty cells stay at the grey
    sentinel regardless of ``avg_weight`` — the fade rule does not
    re-color a non-strategy cell."""

    s_blocked = CellSummary(blocked=True, avg_weight=1.0)
    s_oor = CellSummary(out_of_range=True, avg_weight=1.0)
    s_empty = CellSummary(empty=True, avg_weight=1.0)
    for s in (s_blocked, s_oor, s_empty):
        assert cell_color(s) == "#3a3a3a"
