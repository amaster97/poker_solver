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
    _ALL_IN_DOMINANT_THRESHOLD,
    _FOLD_DOMINANT_THRESHOLD,
    _FOLD_LABEL,
    _bet_labels,
    clean_off_path,
    mark_off_path,
    mark_off_path_with_reason,
    project_by_line,
    reach_and_fold_dominant,
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


# --------------------------------------------------------------------------- #
# Size-agnostic reach at the actor's OWN raise nodes (synthetic)
# --------------------------------------------------------------------------- #
#
# The blueprint's raise nodes offer MULTIPLE sizes; a hand that made an
# aggressive action of ANY size IS in the raise branch. The reach walk must
# therefore credit a bet/raise continuing token with the hand's TOTAL
# aggression mass (sum over every bet/raise label), NOT just the single
# matched-size label. Only genuine folds/limps (never raised) are off-path.


def _size_mixer_by_line() -> dict[str, dict[str, dict[str, float]]]:
    """A node whose continuing token is the SMALL raise size, while the in-range
    hand puts ALL its raise mass on the BIG size.

    Line: SB opens ``b300``; BB 3-bets; the displayed line takes the BB's SMALL
    3-bet token ``r600``. ``BIG`` 3-bets ~98% but almost purely to the BIG size
    (``r900``), with P(r600) ≈ 0.005 — the exact pure-size-mixer shape. ``FLAT``
    only ever calls (never raises) and ``FOLDER`` folds 100%; both are off-path.
    """
    # Menu labels at the BB node, in size order (engine reuses open_* labels).
    def bb_node(kind: str) -> dict[str, float]:
        if kind == "BIG":
            # ~98% 3-bet, almost all on the BIG size; tiny mass on the small one.
            return {
                "fold": 0.02,
                "call": 0.0,
                "open_2": 0.005,  # the SMALL 3-bet size (r600) -> matched token
                "open_3": 0.975,  # the BIG 3-bet size (r900) -> where the mass is
            }
        if kind == "FLAT":
            return {"fold": 0.0, "call": 1.0, "open_2": 0.0, "open_3": 0.0}
        # FOLDER
        return {"fold": 1.0, "call": 0.0, "open_2": 0.0, "open_3": 0.0}

    classes = ("BIG", "FLAT", "FOLDER")
    return {
        "||p|": {c: {"fold": 0.0, "call": 0.2, "open_2": 0.8} for c in classes},
        "||p|b300": {c: bb_node(c) for c in classes},
        # Sibling raise tokens at the BB node: r600 (small) and r900 (big). Their
        # existence drives the rank->label mapping (r600 -> open_2, r900 ->
        # open_3) used by the off-path walk.
        "||p|b300r600": {c: {"fold": 0.0, "call": 1.0} for c in classes},
        "||p|b300r900": {c: {"fold": 0.0, "call": 1.0} for c in classes},
        # The displayed line takes the SMALL 3-bet (r600) then SB 4-bets to r1500.
        "||p|b300r600r1500": {
            c: {"fold": 0.0, "call": 0.9, "open_2": 0.1} for c in classes
        },
    }


def test_size_agnostic_reach_credits_total_aggression_mass() -> None:
    """A hand that puts ALL its raise mass on the BIG size is IN-RANGE on the
    SMALL-size line — the reach walk credits its TOTAL aggression mass, not the
    single matched-size (small) label whose prob is ~0."""
    by_line = _size_mixer_by_line()
    line = "||p|b300r600r1500"
    off = mark_off_path(by_line, line, ["BIG", "FLAT", "FOLDER"])
    # BIG took an aggressive action (of a DIFFERENT size) -> in-range despite
    # P(small-size r600) ≈ 0.005.
    assert off["BIG"] is False
    # FLAT only ever called and FOLDER folded 100% -> both off-path (never
    # raised, so zero aggression mass to credit).
    assert off["FLAT"] is True
    assert off["FOLDER"] is True


def test_size_agnostic_reach_value_is_total_raise_mass() -> None:
    """The reach value at a bet/raise token is the SUM over all bet/raise labels
    (total aggression), so BIG's reach equals 0.005 + 0.975, NOT 0.005."""
    from poker_solver.preflop_offpath import reach

    by_line = _size_mixer_by_line()
    line = "||p|b300r600r1500"
    r_big = reach(by_line, "BIG", line)
    assert r_big is not None
    assert abs(r_big - (0.005 + 0.975)) < 1e-9, r_big
    # A pure flat-caller never raised -> zero aggression mass credited.
    assert reach(by_line, "FLAT", line) == 0.0


def test_size_agnostic_call_token_stays_exact() -> None:
    """A CALL/limp continuing token still credits the EXACT call prob (the
    size-agnostic summing applies ONLY to bet/raise tokens)."""
    from poker_solver.preflop_offpath import reach

    # Line ``||p|cc``: SB limps (``c``), BB checks (``c``); the displayed actor
    # is the SB (even token count). The SB's own gating node is the root ``||p|``
    # where its CALL prob is 0.3 — even though that node ALSO offers a raise
    # (``open_2`` 0.7), the call token must credit the exact 0.3, NOT the summed
    # aggression mass (which would be 0.7). The intermediate BB node ``||p|c``
    # is the opponent's decision and does not gate the SB's reach.
    by_line = {
        "||p|": {"AA": {"fold": 0.0, "call": 0.3, "open_2": 0.7}},
        "||p|c": {"AA": {"fold": 0.0, "call": 1.0}},
        "||p|cc": {"AA": {"fold": 0.0, "call": 1.0}},
    }
    assert reach(by_line, "AA", "||p|cc") == 0.3


# --------------------------------------------------------------------------- #
# REGRESSION: the reported bug against the REAL shipped blueprint
# --------------------------------------------------------------------------- #
#
# At ``||p|b300r700r1500`` the BB's 3-bet menu (at ``||p|b300``) offers
# multiple sizes; AA 3-bets ~98% but almost purely to the BIG size, with
# P(r700) ≈ 0.006. The OLD single-size reach read AA's reach as ~0 and falsely
# greyed it "folded earlier". The size-agnostic fix credits AA's TOTAL
# aggression mass, so AA is correctly IN-RANGE while genuine flat-callers
# (82s/72o, which never 3-bet) stay off-path.


def _real_blueprint_by_line() -> dict[str, dict[str, dict[str, float]]] | None:
    """Load the 100BB / anteNone blueprint via the SAME path the GUI uses
    (``BlueprintRouter.extract_all_lines``). Returns ``None`` when the shipped
    bundle is not on disk in this checkout."""
    try:
        from ui.blueprint_router import BlueprintRouter, default_asset_dir
    except Exception:  # noqa: BLE001
        return None
    router = BlueprintRouter.from_asset_dir(default_asset_dir())
    if router is None:
        return None
    by_line = router.extract_all_lines(stack_bb=100, ante="None")
    return by_line or None


_REAL_BY_LINE = _real_blueprint_by_line()
_REAL_LINE = "||p|b300r700r1500"
_pytestmark_real = __import__("pytest").mark.skipif(
    _REAL_BY_LINE is None or _REAL_LINE not in _REAL_BY_LINE,
    reason=(
        "no preflop blueprint bundle on disk "
        "(assets/blueprints/manifest.json) or line absent"
    ),
)


@_pytestmark_real
def test_regression_AA_in_range_multisize_4bet_line_real_blueprint() -> None:
    """REGRESSION: AA is NOT off-path at the multi-size 4-bet line
    ``||p|b300r700r1500`` on the REAL 100BB/anteNone blueprint.

    AA 3-bets ~98% but almost purely to a DIFFERENT size than the displayed
    ``r700`` token; the size-agnostic reach credits its total aggression mass,
    so it is in-range (the old single-size reach falsely flagged it)."""
    by_line = _REAL_BY_LINE
    assert by_line is not None
    node = by_line[_REAL_LINE]
    assert "AA" in node, "AA missing at the 4-bet line"
    off = mark_off_path(by_line, _REAL_LINE, list(node.keys()))
    assert off["AA"] is False, "AA falsely greyed off-path at a multi-size line"


@_pytestmark_real
def test_regression_AA_not_folded_by_clean_real_blueprint() -> None:
    """API consistency: the same reach fix propagates through ``clean_off_path``
    and ``strategy_table`` — AA is NOT overwritten to fold at the 4-bet line."""
    by_line = _REAL_BY_LINE
    assert by_line is not None
    # clean_off_path (single line)
    cleaned = clean_off_path(by_line, _REAL_LINE)
    aa = cleaned[_REAL_LINE]["AA"]
    assert aa.get(_FOLD_LABEL, 0.0) < 0.99, "AA wrongly folded by clean_off_path"
    # The raw projection's AA strategy survives unchanged (not fold-overwritten).
    assert aa == by_line[_REAL_LINE]["AA"]


@_pytestmark_real
def test_regression_flatcallers_stay_off_path_real_blueprint() -> None:
    """82s / 72o flat-call (never 3-bet) -> they STILL read off-path at the
    4-bet line; the fix does not over-credit genuine non-raisers."""
    by_line = _REAL_BY_LINE
    assert by_line is not None
    node = by_line[_REAL_LINE]
    off = mark_off_path(by_line, _REAL_LINE, list(node.keys()))
    for cls in ("82s", "72o"):
        if cls in node:
            assert off[cls] is True, f"{cls} should be off-path (never 3-bet)"


@_pytestmark_real
def test_regression_other_pure_size_mixer_in_range_real_blueprint() -> None:
    """Another premium pure-size-mixer (KK) is likewise IN-RANGE at the
    multi-size 4-bet line — it too 3-bets heavily but on a non-``r700`` size."""
    by_line = _REAL_BY_LINE
    assert by_line is not None
    node = by_line[_REAL_LINE]
    assert "KK" in node
    off = mark_off_path(by_line, _REAL_LINE, list(node.keys()))
    assert off["KK"] is False, "KK falsely greyed off-path at a multi-size line"


# --------------------------------------------------------------------------- #
# Rule 1: all-in carries over
# --------------------------------------------------------------------------- #
#
# After a hand goes all-in there is NO further voluntary action, so it is
# off-path on EVERY deeper line. The ancestor-dominance walk must therefore
# check the all-in mass (exact ``all_in`` label) the same way it checks fold;
# previously only fold was checked, so an all-in-dominant hand was wrongly left
# in-range on a size-raise continuation. The all-in mass is read from the EXACT
# ``all_in`` label and is NEVER summed into the bet/raise aggregation.


_SYNTH_LINE = "||p|b100r600"  # SB opens b100, BB 3-bets r600 -> SB acts (2 toks)


def _all_in_carryover_by_line() -> dict[str, dict[str, dict[str, float]]]:
    """A tree gating the SB on the displayed line ``||p|b100r600``.

    On ``||p|b100r600`` (SB opens ``b100``, BB 3-bets ``r600``) the actor facing
    the 3-bet is the SB (even token count), so the SB's OWN gating node is the
    root ``||p|``. We pin the root so that ``ALLIN`` jams 100% (-> carries over
    OFF-PATH on the deeper line), ``RAISER`` size-raises 100% (-> on-path), and
    ``FOLDER`` folds 100% (-> off-path via the fold rule).
    """
    classes = ("ALLIN", "RAISER", "FOLDER")

    def root(cls: str) -> dict[str, float]:
        if cls == "ALLIN":
            # All-in 100% at the SB's own (root) node -> carries over off-path.
            return {"fold": 0.0, "call": 0.0, "open_2": 0.0, "all_in": 1.0}
        if cls == "RAISER":
            return {"fold": 0.0, "call": 0.0, "open_2": 1.0, "all_in": 0.0}
        return {"fold": 1.0, "call": 0.0, "open_2": 0.0, "all_in": 0.0}

    # ``b100`` is the SB's open token (rank->label: open_2). The deeper ``r600``
    # is the BB's 3-bet token (opponent node; does not gate the SB's reach).
    return {
        "||p|": {c: root(c) for c in classes},
        "||p|b100": {c: {"fold": 0.0, "call": 1.0} for c in classes},
        _SYNTH_LINE: {c: {"fold": 0.0, "call": 1.0} for c in classes},
    }


def test_all_in_dominant_threshold_mirrors_fold() -> None:
    """The all-in dominance threshold mirrors the fold threshold (0.99)."""
    assert _ALL_IN_DOMINANT_THRESHOLD == _FOLD_DOMINANT_THRESHOLD == 0.99


def test_all_in_not_summed_into_bet_labels_aggregation() -> None:
    """``all_in`` is NEVER folded into the bet/raise aggression mass.

    ``_bet_labels`` returns only ``open_*`` / ``raise_*`` (the size menu), so a
    hand that goes all-in 70% and size-raises 30% credits reach 0.30 on a
    bet/raise token, NOT 1.0.
    """
    node_strat = {
        "open_2": {},
        "open_3": {},
        "all_in": {},
        "call": {},
        "fold": {},
    }
    # _bet_labels takes a NODE (dict of class -> strat); build a 1-class node.
    node = {"X": node_strat}
    labels = _bet_labels(node)
    assert "all_in" not in labels
    assert set(labels) == {"open_2", "open_3"}

    # And the reach aggregation must not pick up the all-in mass. A hand that
    # size-raises 0.30 (0.1 + 0.2) and jams 0.70 should credit reach 0.30 on a
    # bet/raise continuation token. We display ``||p|b100r600`` (SB opens, BB
    # 3-bets) so the SB's OWN root node gates the reach via its ``b100`` open.
    by_line = {
        "||p|": {
            "X": {"open_2": 0.1, "open_3": 0.2, "all_in": 0.7, "fold": 0.0}
        },
        "||p|b100": {"X": {"fold": 0.0, "call": 1.0}},
        "||p|b100r600": {"X": {"fold": 0.0, "call": 1.0}},
    }
    from poker_solver.preflop_offpath import reach

    # The ``b100`` open token at the root (SB's own node) -> bet token -> sums
    # the bet/raise mass (0.1 + 0.2 = 0.3); all_in (0.7) is excluded.
    assert abs(reach(by_line, "X", "||p|b100r600") - 0.3) < 1e-9


def test_all_in_ancestor_marks_off_path_on_size_raise_line() -> None:
    """A hand all-in 100% at an ancestor decision node is off-path (reason
    ``all_in``) on a deeper size-raise continuation line; a genuine size-raiser
    is in-range and a folder is off-path (reason ``folded``)."""
    by_line = _all_in_carryover_by_line()
    line = _SYNTH_LINE
    classes = ["ALLIN", "RAISER", "FOLDER"]
    off = mark_off_path(by_line, line, classes)
    reasons = mark_off_path_with_reason(by_line, line, classes)
    # ALLIN jammed 100% at the root -> carries over off-path on this line.
    assert off["ALLIN"] is True
    assert reasons["ALLIN"] == "all_in"
    # RAISER took the size-raise (b100 == open_2) -> in-range.
    assert off["RAISER"] is False
    assert reasons["RAISER"] is None
    # FOLDER folded 100% at the root -> off-path via the fold rule.
    assert off["FOLDER"] is True
    assert reasons["FOLDER"] == "folded"


def test_all_in_reach_and_fold_dominant_boolean() -> None:
    """The backward-compat ``reach_and_fold_dominant`` boolean is True for an
    all-in-dominant hand (the all-in block flips it, not just fold)."""
    by_line = _all_in_carryover_by_line()
    rfd = reach_and_fold_dominant(by_line, "ALLIN", _SYNTH_LINE)
    assert rfd is not None
    _reach, blocked = rfd
    assert blocked is True


# --------------------------------------------------------------------------- #
# Rule 2: reason-aware off-path mapping (synthetic, deterministic)
# --------------------------------------------------------------------------- #


def _reason_by_line() -> dict[str, dict[str, dict[str, float]]]:
    """A tree exercising each reason at the SB's OWN (root) gating node.

    The displayed line is ``||p|b100r600`` (SB opens ``b100``, BB 3-bets
    ``r600``), so the actor facing the 3-bet is the SB and its OWN gating node is
    the root ``||p|``. Per-class root strategy:
      * FOLDER   — folds 100%             -> ``folded``
      * SHOVER   — all-in 100%            -> ``all_in``
      * CALLER   — calls 100%             -> ``called_closed`` (line raises on)
      * MIXER    — size-raises 0.4% only  -> ``low_reach`` (below threshold)
      * AGGRO    — size-raises 100%       -> on-path (None)
    """
    classes = ("FOLDER", "SHOVER", "CALLER", "MIXER", "AGGRO")

    def root(cls: str) -> dict[str, float]:
        if cls == "FOLDER":
            return {"fold": 1.0, "call": 0.0, "open_2": 0.0, "all_in": 0.0}
        if cls == "SHOVER":
            return {"fold": 0.0, "call": 0.0, "open_2": 0.0, "all_in": 1.0}
        if cls == "CALLER":
            return {"fold": 0.0, "call": 1.0, "open_2": 0.0, "all_in": 0.0}
        if cls == "MIXER":
            # Tiny aggression mass -> below the reach threshold but NOT call-,
            # fold- or all-in-dominant -> generic low_reach.
            return {"fold": 0.3, "call": 0.296, "open_2": 0.004, "all_in": 0.4}
        # AGGRO size-raises 100% -> on-path.
        return {"fold": 0.0, "call": 0.0, "open_2": 1.0, "all_in": 0.0}

    return {
        "||p|": {c: root(c) for c in classes},
        "||p|b100": {c: {"fold": 0.0, "call": 1.0} for c in classes},
        _SYNTH_LINE: {c: {"fold": 0.0, "call": 1.0} for c in classes},
    }


def test_reason_mapping_each_code() -> None:
    """Each reason code is produced by its archetype; the in-range aggressor is
    ``None``. Priority across classes is folded > all_in > called_closed >
    low_reach (here each class hits exactly one)."""
    by_line = _reason_by_line()
    line = _SYNTH_LINE
    classes = ["FOLDER", "SHOVER", "CALLER", "MIXER", "AGGRO"]
    reasons = mark_off_path_with_reason(by_line, line, classes)
    assert reasons["FOLDER"] == "folded"
    assert reasons["SHOVER"] == "all_in"
    assert reasons["CALLER"] == "called_closed"
    assert reasons["MIXER"] == "low_reach"
    assert reasons["AGGRO"] is None


def test_mark_off_path_bool_matches_reason_map() -> None:
    """``mark_off_path`` (bool) is consistent with the reason map: off-path
    exactly when the reason is not None."""
    by_line = _reason_by_line()
    line = _SYNTH_LINE
    classes = ["FOLDER", "SHOVER", "CALLER", "MIXER", "AGGRO"]
    bools = mark_off_path(by_line, line, classes)
    reasons = mark_off_path_with_reason(by_line, line, classes)
    for cls in classes:
        assert bools[cls] is (reasons[cls] is not None), cls


def test_reason_priority_earliest_ancestor_wins() -> None:
    """The EARLIEST blocking ancestor's reason wins across the SB's own nodes.

    On ``||p|b100r600c1500c`` the SB acts at TWO own nodes — the root ``||p|``
    (i=0) and ``||p|b100r600`` (i=2). A hand that folds 100% at the root and
    would shove 100% at the later own node reports ``folded`` (the earlier
    block), not ``all_in``."""
    by_line = {
        "||p|": {"X": {"fold": 1.0, "call": 0.0, "open_2": 0.0, "all_in": 0.0}},
        "||p|b100": {"X": {"fold": 0.0, "call": 1.0}},
        # Later SB own node — all-in, but the earlier root fold is reported.
        "||p|b100r600": {"X": {"fold": 0.0, "call": 0.0, "all_in": 1.0}},
        "||p|b100r600c": {"X": {"fold": 0.0, "call": 1.0}},
        "||p|b100r600c1500": {"X": {"fold": 0.0, "call": 1.0}},
        "||p|b100r600c1500c": {"X": {"fold": 0.0, "call": 1.0}},
    }
    reasons = mark_off_path_with_reason(by_line, "||p|b100r600c1500c", ["X"])
    assert reasons["X"] == "folded"


def test_reason_failsafe_missing_node_is_none() -> None:
    """FAIL-SAFE: a missing prior gating node yields reason ``None`` for all.

    Dropping the SB's root node makes the walk incomputable for the SB-gated
    line, so nothing is marked (matching the boolean ``mark_off_path``
    fail-safe)."""
    by_line = _reason_by_line()
    del by_line["||p|"]  # drop the SB's gating node
    reasons = mark_off_path_with_reason(by_line, _SYNTH_LINE, ["AGGRO", "CALLER"])
    assert all(v is None for v in reasons.values())


def test_reason_root_line_all_none() -> None:
    """The root line has no gating ancestors -> every class is on-path
    (reason None)."""
    by_line = _reason_by_line()
    reasons = mark_off_path_with_reason(
        by_line, "||p|", ["FOLDER", "SHOVER", "CALLER", "MIXER", "AGGRO"]
    )
    assert all(v is None for v in reasons.values())


# --------------------------------------------------------------------------- #
# Rule 2 REGRESSION: real 200BB blueprint (K3s / A3o called_closed)
# --------------------------------------------------------------------------- #
#
# At 200BB the BB flat-calls the SB open ~100% with K3s / A3o (and many other
# hands), so they CLOSE the action and are off-path on the subsequent 4-bet
# line ``||p|b500r2100r5300`` with reason ``called_closed``. AA likewise traps
# by calling the open at 200BB (it does NOT 3-bet), so it is also off-path here.


def _real_blueprint_by_line_200() -> (
    dict[str, dict[str, dict[str, float]]] | None
):
    """Load the 200BB / anteNone blueprint via the same GUI path."""
    try:
        from ui.blueprint_router import BlueprintRouter, default_asset_dir
    except Exception:  # noqa: BLE001
        return None
    router = BlueprintRouter.from_asset_dir(default_asset_dir())
    if router is None:
        return None
    by_line = router.extract_all_lines(stack_bb=200, ante="None")
    return by_line or None


_REAL_BY_LINE_200 = _real_blueprint_by_line_200()
_REAL_LINE_200 = "||p|b500r2100r5300"
_pytestmark_real_200 = __import__("pytest").mark.skipif(
    _REAL_BY_LINE_200 is None or _REAL_LINE_200 not in _REAL_BY_LINE_200,
    reason=(
        "no 200BB preflop blueprint bundle on disk "
        "(assets/blueprints/manifest.json) or line absent"
    ),
)


@_pytestmark_real_200
def test_regression_k3s_a3o_called_closed_200bb() -> None:
    """K3s and A3o flat-call the open ~100% at 200BB -> off-path with reason
    ``called_closed`` on the 4-bet line (they closed the action)."""
    by_line = _REAL_BY_LINE_200
    assert by_line is not None
    node = by_line[_REAL_LINE_200]
    reasons = mark_off_path_with_reason(by_line, _REAL_LINE_200, list(node.keys()))
    off = mark_off_path(by_line, _REAL_LINE_200, list(node.keys()))
    for cls in ("K3s", "A3o"):
        assert off[cls] is True, f"{cls} should be off-path on the 4-bet line"
        assert reasons[cls] == "called_closed", (cls, reasons[cls])


@_pytestmark_real_200
def test_regression_flatcallers_off_path_200bb() -> None:
    """82s / 72o are off-path on the 200BB 4-bet line (they never reach it)."""
    by_line = _REAL_BY_LINE_200
    assert by_line is not None
    node = by_line[_REAL_LINE_200]
    off = mark_off_path(by_line, _REAL_LINE_200, list(node.keys()))
    for cls in ("82s", "72o"):
        if cls in node:
            assert off[cls] is True, f"{cls} should be off-path on the 4-bet line"


@_pytestmark_real_200
def test_regression_bet_labels_exclude_all_in_real_node_200bb() -> None:
    """On a real blueprint node the bet/raise label set excludes ``all_in`` —
    confirming all-in is never summed into the aggression aggregation."""
    by_line = _REAL_BY_LINE_200
    assert by_line is not None
    node = by_line.get("||p|b500")
    assert node is not None
    labels = _bet_labels(node)
    assert "all_in" not in labels
    assert all(lbl.startswith(("open_", "raise_")) for lbl in labels)
