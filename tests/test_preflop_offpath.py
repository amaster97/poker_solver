"""Pure (GUI-free) tests for ``poker_solver.preflop_offpath``.

Covers the three public entry points:
  * :func:`mark_off_path` — the off-path primitive (reach + fold-dominant).
  * :func:`clean_off_path` — fold-overwrite of off-path entries, never
    mutating the input.
  * :func:`strategy_table` — the ``average_strategy`` -> ``by_line`` projection,
    cleaned by DEFAULT, with a raw opt-out, never mutating the raw source.

No nicegui / AppState import — this module is the GUI-agnostic contract.
"""

from __future__ import annotations

import copy

from poker_solver.preflop_offpath import (
    _FOLD_LABEL,
    clean_off_path,
    mark_off_path,
    project_by_line,
    strategy_table,
)


def _all_169_classes() -> list[str]:
    from poker_solver.preflop_offpath import _ALL_169_HAND_CLASSES

    return sorted(_ALL_169_HAND_CLASSES)


def _synthetic_by_line() -> dict[str, dict[str, dict[str, float]]]:
    """A small fully-specified tree mirroring the real engine line shapes.

    The opener (SB) opens to 2bb; the BB either 3-bets (``r400`` … ``r700``)
    or flat-calls. Only the genuine 3-bet hands (AA/KK/QJo) ever reach the
    4-bet node ``||p|b200r400r1000``; the flat-call hands (82s/72o) carry reach
    exactly 0 there (off-path via the reach rule). 82s additionally folds
    ≥99% at its own gating node so it is also off-path via the FOLD rule.
    """
    classes = _all_169_classes()
    raisers = {"AA", "KK", "QJo"}

    def node_b200(cls: str) -> dict[str, float]:
        if cls in raisers:
            return {
                "fold": 0.0,
                "call": 0.4,
                "open_2": 0.5,  # the 3-bet (r400) -> nonzero BB reach
                "open_3": 0.1,
                "open_4": 0.0,
                "open_5": 0.0,
                "all_in": 0.0,
            }
        if cls == "82s":
            # Fold-dominant at the BB node: off-path via the FOLD rule even
            # though it never reaches the deep node anyway.
            return {
                "fold": 1.0,
                "call": 0.0,
                "open_2": 0.0,
                "open_3": 0.0,
                "open_4": 0.0,
                "open_5": 0.0,
                "all_in": 0.0,
            }
        return {
            "fold": 0.0,
            "call": 1.0,  # flat-calls the open -> never reaches the 4-bet node
            "open_2": 0.0,
            "open_3": 0.0,
            "open_4": 0.0,
            "open_5": 0.0,
            "all_in": 0.0,
        }

    root = {
        c: {"fold": 0.0, "call": 0.2, "open_2": 0.5, "open_3": 0.3} for c in classes
    }
    return {
        "||p|": root,
        "||p|b200": {c: node_b200(c) for c in classes},
        # Sibling raise tokens (existence drives the rank->label mapping).
        "||p|b200r400": {c: {"fold": 0.0, "call": 1.0} for c in classes},
        "||p|b200r500": {c: {"fold": 0.0, "call": 1.0} for c in classes},
        "||p|b200r600": {c: {"fold": 0.0, "call": 1.0} for c in classes},
        "||p|b200r700": {c: {"fold": 0.0, "call": 1.0} for c in classes},
        # The 4-bet line we display (its own strategy is what would mislead).
        "||p|b200r400r1000": {
            c: {"fold": 0.0, "call": 0.99, "open_2": 0.01} for c in classes
        },
    }


# --------------------------------------------------------------------------- #
# mark_off_path
# --------------------------------------------------------------------------- #


def test_mark_off_path_deep_line_flags_flatcallers() -> None:
    """82s / 72o flat-called the open -> off-path at the 4-bet node; the genuine
    3-bet hands (AA/KK/QJo) are in-range."""
    by_line = _synthetic_by_line()
    classes = _all_169_classes()
    off = mark_off_path(by_line, "||p|b200r400r1000", classes)
    assert off["82s"] is True
    assert off["72o"] is True
    assert off["AA"] is False
    assert off["KK"] is False
    assert off["QJo"] is False


def test_mark_off_path_root_uniform_nothing_flagged() -> None:
    """The root open node has uniform reach (1.0 for every class) and no
    fold-dominant ancestor, so NOTHING is flagged off-path."""
    by_line = _synthetic_by_line()
    off = mark_off_path(by_line, "||p|", _all_169_classes())
    assert not any(off.values()), "root node must not flag any class"


def test_mark_off_path_default_hand_classes_from_node() -> None:
    """``hand_classes=None`` defaults to the classes present at the line."""
    by_line = _synthetic_by_line()
    off = mark_off_path(by_line, "||p|b200r400r1000")
    assert set(off) == set(_all_169_classes())
    assert off["82s"] is True and off["AA"] is False


def test_mark_off_path_failsafe_missing_prior_node() -> None:
    """FAIL-SAFE: when a prior gating node is missing from ``by_line`` (e.g. a
    partial snapshot), reach is incomputable, so NOTHING is flagged."""
    by_line = _synthetic_by_line()
    del by_line["||p|b200"]  # drop the BB's gating node
    classes = _all_169_classes()
    off = mark_off_path(by_line, "||p|b200r400r1000", classes)
    assert not any(off.values()), "missing prior node must disable flagging"


def test_mark_off_path_failsafe_no_by_line() -> None:
    """FAIL-SAFE: a None / empty ``by_line`` flags nothing."""
    assert mark_off_path(None, "||p|", ["AA", "72o"]) == {"AA": False, "72o": False}
    assert mark_off_path({}, "||p|", ["AA", "72o"]) == {"AA": False, "72o": False}


# --------------------------------------------------------------------------- #
# clean_off_path
# --------------------------------------------------------------------------- #


def test_clean_off_path_overwrites_offpath_to_fold() -> None:
    """Off-path entries become fold=1.0 / everything else 0.0; on-path entries
    are untouched."""
    by_line = _synthetic_by_line()
    line = "||p|b200r400r1000"
    cleaned = clean_off_path(by_line, line)
    node = cleaned[line]
    # 82s/72o off-path -> folded.
    for cls in ("82s", "72o"):
        assert node[cls][_FOLD_LABEL] == 1.0
        assert all(v == 0.0 for k, v in node[cls].items() if k != _FOLD_LABEL)
    # AA/KK/QJo on-path -> unchanged from the raw projection.
    for cls in ("AA", "KK", "QJo"):
        assert node[cls] == by_line[line][cls]


def test_clean_off_path_does_not_mutate_input() -> None:
    """``clean_off_path`` returns a deep copy; the input is byte-for-byte
    unchanged."""
    by_line = _synthetic_by_line()
    before = copy.deepcopy(by_line)
    _ = clean_off_path(by_line, "||p|b200r400r1000")
    assert by_line == before, "input by_line must not be mutated"
    # And the returned table is a distinct object (no shared nested dicts).
    cleaned = clean_off_path(by_line, "||p|b200r400r1000")
    cleaned["||p|b200r400r1000"]["82s"]["fold"] = -999.0
    assert by_line["||p|b200r400r1000"]["82s"]["fold"] == 0.0


def test_clean_off_path_line_none_cleans_every_line() -> None:
    """``line=None`` cleans EVERY line; each node evaluated independently.

    The root stays fully intact (uniform reach -> nothing off-path); the deep
    4-bet node has its flat-callers folded.
    """
    by_line = _synthetic_by_line()
    cleaned = clean_off_path(by_line, line=None)
    # Root: nothing off-path -> identical to raw.
    assert cleaned["||p|"] == by_line["||p|"]
    # Deep node: flat-callers folded.
    deep = cleaned["||p|b200r400r1000"]
    assert deep["82s"][_FOLD_LABEL] == 1.0
    assert deep["AA"] == by_line["||p|b200r400r1000"]["AA"]


def test_clean_off_path_single_line_leaves_others_raw() -> None:
    """``line="..."`` cleans only that line; other lines pass through unchanged
    (the deep node's flat-callers are NOT folded when cleaning only the root)."""
    by_line = _synthetic_by_line()
    cleaned = clean_off_path(by_line, "||p|")
    # The deep node was not the target -> still raw.
    assert cleaned["||p|b200r400r1000"] == by_line["||p|b200r400r1000"]


# --------------------------------------------------------------------------- #
# strategy_table — projection + default-clean / raw opt-out
# --------------------------------------------------------------------------- #


def _synthetic_average_strategy() -> dict[str, list[float]]:
    """A raw class169-kernel ``average_strategy`` mapping.

    Keys are ``"<class>||p|<history>"``; values are probability vectors in the
    canonical menu order ``[fold, call, open_2, open_3, ...]``. Mirrors the real
    binding shape so ``project_by_line(..., class169=True)`` reconstructs the
    same by_line the GUI builds.
    """
    classes = _all_169_classes()
    raisers = {"AA", "KK", "QJo"}
    out: dict[str, list[float]] = {}
    for c in classes:
        # root open
        out[f"{c}||p|"] = [0.0, 0.2, 0.5, 0.3]
        # BB response to a 2bb open
        if c in raisers:
            out[f"{c}||p|b200"] = [0.0, 0.4, 0.5, 0.1, 0.0, 0.0, 0.0]
        else:
            out[f"{c}||p|b200"] = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        # sibling raise tokens at the BB node (drive rank->label mapping)
        for amt in ("r400", "r500", "r600", "r700"):
            out[f"{c}||p|b200{amt}"] = [0.0, 1.0]
        # the displayed 4-bet node
        out[f"{c}||p|b200r400r1000"] = [0.0, 0.99, 0.01]
    return out


def test_strategy_table_default_clean_folds_offpath() -> None:
    """``strategy_table`` defaults to ``clean=True`` -> off-path entries at the
    4-bet node are folded."""
    avg = _synthetic_average_strategy()
    table = strategy_table(avg, class169=True)  # clean defaults to True
    node = table["||p|b200r400r1000"]
    for cls in ("82s", "72o"):
        assert node[cls][_FOLD_LABEL] == 1.0
        assert all(v == 0.0 for k, v in node[cls].items() if k != _FOLD_LABEL)
    # Genuine 3-bet hands keep their real strategy.
    assert node["AA"]["call"] == 0.99
    assert node["AA"]["open_2"] == 0.01


def test_strategy_table_raw_keeps_offpath_noise() -> None:
    """``clean=False`` returns the raw projection — the off-path noise (a
    misleading 99% call at an unreachable node) is preserved."""
    avg = _synthetic_average_strategy()
    raw = strategy_table(avg, class169=True, clean=False)
    node = raw["||p|b200r400r1000"]
    # 82s carries its raw (meaningless) strategy, NOT folded.
    assert node["82s"]["call"] == 0.99
    assert node["82s"]["open_2"] == 0.01
    assert node["82s"][_FOLD_LABEL] == 0.0


def test_strategy_table_default_diverges_from_raw_only_offpath() -> None:
    """Default-clean and raw differ ONLY at off-path entries; on-path entries
    match exactly."""
    avg = _synthetic_average_strategy()
    cleaned = strategy_table(avg, class169=True)
    raw = strategy_table(avg, class169=True, clean=False)
    deep = "||p|b200r400r1000"
    assert cleaned[deep]["82s"] != raw[deep]["82s"]  # off-path differs
    assert cleaned[deep]["AA"] == raw[deep]["AA"]  # on-path identical
    # Root is uniform -> identical in both.
    assert cleaned["||p|"] == raw["||p|"]


def test_strategy_table_does_not_mutate_average_strategy() -> None:
    """CRITICAL: the raw ``average_strategy`` source is NEVER mutated/cleaned by
    ``strategy_table`` (internal consumers keep reading the source of truth)."""
    avg = _synthetic_average_strategy()
    before = copy.deepcopy(avg)
    _ = strategy_table(avg, class169=True)  # default clean
    assert avg == before, "default-clean must not touch average_strategy"
    _ = strategy_table(avg, class169=True, clean=False)  # raw
    assert avg == before, "raw projection must not touch average_strategy"


def test_strategy_table_matches_project_by_line_when_raw() -> None:
    """``strategy_table(clean=False)`` is exactly the pure projection."""
    avg = _synthetic_average_strategy()
    assert strategy_table(avg, class169=True, clean=False) == project_by_line(
        avg, class169=True
    )


def test_strategy_table_1326_kernel_keys() -> None:
    """The default (1326) kernel parses ``"{hole_str}||p|<hist>"`` keys and
    aggregates combos to 169 classes."""
    # AsAh + AdAc are both the AA class; average should reconstruct AA's root.
    avg = {
        "AsAh||p|": [0.0, 0.1, 0.9],
        "AdAc||p|": [0.0, 0.3, 0.7],
    }
    raw = strategy_table(avg, clean=False)  # class169=False default
    assert "AA" in raw["||p|"]
    aa = raw["||p|"]["AA"]
    # Mean of the two combos: call = (0.1+0.3)/2 = 0.2, open_2 = (0.9+0.7)/2 = 0.8
    assert abs(aa["call"] - 0.2) < 1e-9
    assert abs(aa["open_2"] - 0.8) < 1e-9
