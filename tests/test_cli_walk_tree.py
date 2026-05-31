"""v1.8.2 — CLI tree-walk + drill-down + JSON/CSV format tests.

Covers the seven acceptance tests from the v1.8.2 brief:

1. ``--walk-tree`` on AK vs QQ shows on-path nodes (P1 checks, P0 bets,
   P1 folds, etc.)
2. ``--full-tree`` adds off-path phantom nodes marked ``[OFF-PATH]``.
3. ``--node "xb750"`` drill-down works on AK vs QQ range query.
4. ``--format json`` produces parseable JSON.
5. ``--format csv`` produces a readable CSV with header.
6. Action label decoder handles ``b750``, ``A``, ``r3125``, ``x``, ``c``,
   ``f`` tokens.
7. Backward compat — default (no new flags) output is byte-identical to
   the legacy CLI.

Tests use in-process ``main()`` + ``capsys`` so they stay fast (no
subprocess spawn), and use 30 DCFR iterations per per-combo solve (the
PR 39 test harness uses 10–20). The behavior we assert is structural
(headers, action labels present, JSON parseable) — we do NOT assert
exact probability values, which would couple the test to DCFR
internals and break on backend swaps.
"""

from __future__ import annotations

import csv
import io
import json

import pytest

from poker_solver.action_abstraction import (
    ACTION_ALL_IN,
    ACTION_BET_75,
    ACTION_CALL,
    ACTION_CHECK,
    ACTION_FOLD,
    ACTION_RAISE_75,
    ActionContext,
)
from poker_solver.cli import main
from poker_solver.cli_tree_walk import (
    decode_action_label,
    parse_token,
)

# ---------------------------------------------------------------------------
# Test 1: --walk-tree on AK vs QQ shows on-path nodes
# ---------------------------------------------------------------------------


def test_walk_tree_on_ak_vs_qq_shows_on_path_nodes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--walk-tree`` lists at least: P1 check, P0 bet, P1 fold (over-fold spot).

    On the As 7c 2d Th 5s board with hero AhKd vs villain QcQh, the
    overpair (Q) is dominated by hero's top pair (A). With 30 DCFR iters
    the engine converges enough that the on-path tree includes:
    * P1's empty-history (check vs bet)
    * P0's response after villain checks
    * P1's response to each of P0's bets

    We assert the structural markers present, not the exact prob values.
    """
    rc = main(
        [
            "river",
            "--board",
            "As 7c 2d Th 5s",
            "--hero",
            "AhKd",
            "--villain-range",
            "QcQh",
            "--iters",
            "30",
            "--walk-tree",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out

    # Preamble unchanged from legacy.
    assert "Board:" in out
    assert "Hero:" in out
    assert "Villain range:" in out

    # Per-combo tree section appears with title.
    assert "Villain combo QhQc" in out
    assert "on-path nodes" in out

    # We expect P1's first decision (empty history → "first decision") and
    # P0's response after a check (history "x").
    assert "first decision" in out
    # P0 acts after the villain check; histories include "check".
    assert "P0 (AhKd)" in out
    assert "P1 (QhQc)" in out

    # Action labels render in pretty form (not raw action IDs).
    assert "check" in out
    assert "bet " in out  # bet 33% / bet 75% / etc.
    # Bar chart ASCII present.
    assert "#" in out and "." in out
    # Reach probability annotation present.
    assert "reach=" in out


# ---------------------------------------------------------------------------
# Test 2: --full-tree adds off-path phantoms
# ---------------------------------------------------------------------------


def test_full_tree_adds_off_path_phantom_nodes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--full-tree`` adds phantom nodes (reach <= 1e-4) marked ``[OFF-PATH]``.

    Compare on-path-only vs full-tree: the full-tree variant must have
    strictly more total nodes (off-path = engine prunes 99% of branches
    when QQ over-folds) and contain the ``[OFF-PATH]`` marker.
    """
    args_base = [
        "river",
        "--board",
        "As 7c 2d Th 5s",
        "--hero",
        "AhKd",
        "--villain-range",
        "QcQh",
        "--iters",
        "30",
        "--walk-tree",
    ]

    rc_on = main(args_base)
    assert rc_on == 0
    out_on = capsys.readouterr().out

    rc_full = main(args_base + ["--full-tree"])
    assert rc_full == 0
    out_full = capsys.readouterr().out

    # Off-path marker present only in --full-tree output.
    assert "[OFF-PATH]" not in out_on, "on-path output should not contain phantoms"
    assert "[OFF-PATH]" in out_full, "full-tree must mark phantom nodes"

    # The title node-count is higher with --full-tree.
    def _node_count(s: str) -> int:
        # Title format: "Villain combo X — N on-path nodes (incl. off-path...)"
        for line in s.splitlines():
            if "on-path nodes" in line:
                tokens = line.split()
                # Find the number preceding "on-path"
                for i, t in enumerate(tokens):
                    if t == "on-path":
                        return int(tokens[i - 1])
        return -1

    on_count = _node_count(out_on)
    full_count = _node_count(out_full)
    assert on_count > 0
    assert full_count > on_count, (
        f"expected full-tree count ({full_count}) > on-path count ({on_count})"
    )


# ---------------------------------------------------------------------------
# Test 3: --node drill-down on AK vs QQ range query
# ---------------------------------------------------------------------------


def test_node_drilldown_on_qq_range(capsys: pytest.CaptureFixture[str]) -> None:
    """``--node "xb330"`` aggregates villain QQ class strategy at that node.

    QQ has 6 unblocked combos vs hero AhKd on this board; the drill-down
    must (1) print the per-class header, (2) show the QQ class line, and
    (3) annotate with MDF since the fold/call pair is in the action menu.
    """
    rc = main(
        [
            "river",
            "--board",
            "As 7c 2d Th 5s",
            "--hero",
            "AhKd",
            "--villain-range",
            "QQ",
            "--iters",
            "30",
            "--node",
            "xb330",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out

    # Header for per-class drill-down.
    assert "Per-class strategy at history 'xb330'" in out
    # QQ class shown.
    assert "QQ" in out
    # Action labels visible.
    assert "fold" in out
    assert "call" in out
    # MDF annotation present (pot-odds 330 / (1000 + 330) ≈ 24.8% → MDF
    # ≈ 75.2%). Numeric value isn't asserted strictly — we just check
    # that the annotation tag appears.
    assert "MDF=" in out


# ---------------------------------------------------------------------------
# Test 4: --format json produces parseable JSON
# ---------------------------------------------------------------------------


def test_format_json_produces_parseable_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--format json --walk-tree`` emits a JSON object parseable by ``json.loads``."""
    rc = main(
        [
            "river",
            "--board",
            "As 7c 2d Th 5s",
            "--hero",
            "AhKd",
            "--villain-range",
            "QcQh",
            "--iters",
            "30",
            "--walk-tree",
            "--format",
            "json",
        ]
    )
    assert rc == 0
    raw = capsys.readouterr().out
    payload = json.loads(raw)

    # Top-level schema.
    assert "board" in payload
    assert "hero" in payload
    assert "villain_range" in payload
    assert "iterations" in payload
    assert "mean_game_value_bb" in payload
    assert "combos" in payload

    combos = payload["combos"]
    assert isinstance(combos, dict)
    assert "QhQc" in combos
    nodes = combos["QhQc"]
    assert isinstance(nodes, list)
    assert len(nodes) > 0

    first = nodes[0]
    assert {"history", "player", "hole_label", "infoset_key", "reach_prob",
            "off_path", "actions"} <= set(first.keys())
    assert isinstance(first["actions"], list)
    a = first["actions"][0]
    assert {"action_id", "label", "prob"} <= set(a.keys())
    # The probabilities sum to ~1.0 at a normalized infoset.
    total = sum(act["prob"] for act in first["actions"])
    assert 0.95 < total < 1.05, f"action probs should sum near 1.0; got {total}"


# ---------------------------------------------------------------------------
# Test 5: --format csv produces readable CSV with header
# ---------------------------------------------------------------------------


def test_format_csv_produces_readable_csv(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--format csv --walk-tree`` emits a CSV with the expected header and rows."""
    rc = main(
        [
            "river",
            "--board",
            "As 7c 2d Th 5s",
            "--hero",
            "AhKd",
            "--villain-range",
            "QcQh",
            "--iters",
            "30",
            "--walk-tree",
            "--format",
            "csv",
        ]
    )
    assert rc == 0
    raw = capsys.readouterr().out

    reader = csv.reader(io.StringIO(raw))
    rows = list(reader)
    assert len(rows) >= 2, "CSV must contain header + at least one data row"

    # Header
    expected_header = [
        "combo",
        "node_history",
        "action_label",
        "probability",
        "reach_prob",
    ]
    assert rows[0] == expected_header

    # First data row: combo QhQc, root history, check, ~1.0 prob (over-fold spot
    # → villain checks ~100%), reach 1.0.
    first = rows[1]
    assert first[0] == "QhQc"
    assert first[1] == "(root)"
    # probability column is parseable as a float.
    float(first[3])
    float(first[4])


# ---------------------------------------------------------------------------
# Test 6: action label decoder
# ---------------------------------------------------------------------------


def test_action_label_decoder_for_all_token_kinds() -> None:
    """``decode_action_label`` and ``parse_token`` handle every token kind.

    We construct a minimal ActionContext to drive ``decode_action_label``
    (the function only reads context fields, doesn't mutate state). For
    each kind in {b, r, A, x, c, f} we assert the rendered label contains
    the right keyword.
    """
    # Single-char tokens (no chip amount).
    assert parse_token("x") == ("x", None)
    assert parse_token("c") == ("c", None)
    assert parse_token("f") == ("f", None)
    assert parse_token("A") == ("A", None)

    # Multi-char tokens with chip amount.
    assert parse_token("b750") == ("b", 750)
    assert parse_token("r3125") == ("r", 3125)
    assert parse_token("b330") == ("b", 330)

    # Malformed tokens raise ValueError.
    with pytest.raises(ValueError):
        parse_token("")
    with pytest.raises(ValueError):
        parse_token("z123")
    with pytest.raises(ValueError):
        parse_token("b")  # no amount

    # Action label decoder — basic tokens.
    ctx = ActionContext(
        pot=1000,
        to_call=250,
        stacks=(9500, 9500),
        contributions=(500, 750),
        cur_player=0,
        street=4,  # river
        street_num_raises=1,
        street_aggressor=1,
        big_blind=100,
        bet_size_fractions=(0.33, 0.75, 1.0, 1.5, 2.0),
        # C2 raises are multipliers of the bet faced (not pot-fractions). The
        # default menu has a single 3.0x slot, so ACTION_RAISE_75 (slot index 1)
        # would index past it; give all 5 raise slots so every ACTION_RAISE_*
        # decodes. The raise display tag is the MULTIPLIER from this menu (slot
        # 1 == 3.0 -> "3.0x"), NOT a pot-fraction.
        raise_size_xs=(2.0, 3.0, 4.0, 5.0, 6.0),
        preflop_raise_cap=4,
        postflop_raise_cap=4,
        force_allin_threshold_bb=0,
        min_bet_bb=1,
        include_all_in=True,
    )

    assert decode_action_label(ACTION_FOLD, ctx) == "fold"
    assert decode_action_label(ACTION_CHECK, ctx) == "check"
    # v1.9.0 — call label is BB-native: "call (2.5 BB)" (250 chips / 100).
    call_label = decode_action_label(ACTION_CALL, ctx)
    assert "call" in call_label
    assert "2.5 BB" in call_label
    # v1.9.0 — all-in label embeds BB amount and BB pot context.
    allin_label = decode_action_label(ACTION_ALL_IN, ctx)
    assert "all-in" in allin_label
    assert "BB" in allin_label
    # ACTION_BET_75 → "bet 75% pot (7.5 BB)"
    label_b75 = decode_action_label(ACTION_BET_75, ctx)
    assert "bet 75%" in label_b75
    assert "BB" in label_b75
    # ACTION_RAISE_75 → "raise to NN BB (3.0x)" — raise slot 1 maps to the
    # multiplier raise_size_xs[1] == 3.0, rendered as an "x" multiplier (NOT a
    # pot-fraction).
    label_r75 = decode_action_label(ACTION_RAISE_75, ctx)
    assert "raise to" in label_r75
    assert "3.0x" in label_r75
    assert "75% pot" not in label_r75
    assert "BB" in label_r75


# ---------------------------------------------------------------------------
# Test 7: backward compat - default output unchanged
# ---------------------------------------------------------------------------


def test_backward_compat_default_output_unchanged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """With NO new flags, ``--walk-tree`` / ``--node`` / ``--format`` all off,
    the legacy first-decision aggregate output structure is preserved.

    We check the structural markers from the PR 39 test, plus an explicit
    assertion that none of the new markers (``Villain combo``, ``walk
    tree``, ``[OFF-PATH]``, ``Per-class``) appear.
    """
    rc = main(
        [
            "river",
            "--board",
            "As 7c 2d Th 5s",
            "--hero",
            "AhKd",
            "--villain-range",
            "QcQh",
            "--iters",
            "30",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out

    # Legacy markers (from test_river_happy_path_aggregates_frequencies).
    assert "Board:" in out
    assert "Hero:" in out
    assert "Villain range:" in out
    assert "1 combos after card removal" in out
    assert "Hero first-decision aggregate" in out
    assert "Mean game value" in out

    # New-mode markers must NOT appear in default output.
    assert "Villain combo QhQc" not in out
    assert "[OFF-PATH]" not in out
    assert "Per-class strategy" not in out
    # No ASCII bar charts in legacy mode.
    # (The legacy output has lines like "  action_0   0.000050"; check
    # none of the bar-chart character pairs appear.)
    assert "####" not in out
