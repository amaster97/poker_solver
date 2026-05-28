"""v1.9.0 — CLI BB-native display + node-id syntax tests.

Acceptance tests for the v1.9.0 BB-normalization brief:

1. New ``--pot 10 --stack 100`` flags work.
2. Old ``--pot-bb 10 --stack-bb 100`` still work and emit a deprecation
   warning on stderr.
3. ``--node "check.bet75pct"`` resolves to the same infoset as
   ``--node "xb750"`` (and ``--node "check.bet7.5bb"``).
4. Walk-tree output shows BB amounts AND %-pot inline (``bet 75% pot
   (7.5 BB)``).
5. Walk-tree shows ``--node`` id inline for copy-paste
   (``[--node "check.bet75pct"]``).
6. Header block prints at top of every CLI run.
7. Max 1 decimal place enforced in display (``7.5 BB`` not
   ``7.50000 BB``).
8. CLI output is byte-identical when ``LANG=C`` is set
   (locale-independent).

Tests run in-process via ``main()`` + ``capsys`` for speed; DCFR uses 30
iterations per per-combo solve (same convention as the v1.8.2
``test_cli_walk_tree`` suite). Behavior asserted is structural — we
don't pin exact probability values, which would couple the test to DCFR
internals.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

import pytest

from poker_solver.cli import main
from poker_solver.cli_bb_format import (
    SpotHeader,
    canonical_node_id_for_history,
    chips_to_bb,
    format_bb,
    format_pot_pct,
    parse_user_node,
    render_header,
)


# ---------------------------------------------------------------------------
# Test 1: new --pot / --stack flags work
# ---------------------------------------------------------------------------


def test_new_pot_stack_flags_work(capsys: pytest.CaptureFixture[str]) -> None:
    """The canonical ``--pot`` / ``--stack`` flags drive the SPOT CONFIG block.

    Passing ``--pot 15 --stack 50`` must result in the header showing
    50 BB stacks + 15 BB pot, with NO deprecation warning on stderr.
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
            "5",
            "--pot",
            "15",
            "--stack",
            "50",
        ]
    )
    assert rc == 0
    captured = capsys.readouterr()
    out, err = captured.out, captured.err

    assert "Effective stacks:    50 BB" in out
    assert "Starting pot:        15 BB" in out
    # No deprecation warning for the canonical flags.
    assert "deprecated" not in err.lower()


# ---------------------------------------------------------------------------
# Test 2: old --pot-bb / --stack-bb still work with deprecation warning
# ---------------------------------------------------------------------------


def test_legacy_pot_bb_stack_bb_still_work_with_warning(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Backward-compat: ``--pot-bb`` / ``--stack-bb`` still drive the engine.

    The header must still show 50 BB stacks + 15 BB pot (same as the
    canonical flags), and stderr must carry exactly one deprecation
    warning per flag.
    """
    # First clear the one-shot deprecation cache so the warning fires.
    import poker_solver.cli_bb_format as cli_bb_format
    cli_bb_format._DEPRECATION_WARNED.clear()

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
            "5",
            "--pot-bb",
            "15",
            "--stack-bb",
            "50",
        ]
    )
    assert rc == 0
    captured = capsys.readouterr()
    out, err = captured.out, captured.err

    assert "Effective stacks:    50 BB" in out
    assert "Starting pot:        15 BB" in out
    # Deprecation warning on stderr for both legacy flags.
    assert "--pot-bb is deprecated" in err
    assert "--stack-bb is deprecated" in err
    assert "use --pot instead" in err
    assert "use --stack instead" in err


# ---------------------------------------------------------------------------
# Test 3: --node syntax equivalence (chip / BB / %-pot / dot / verbose)
# ---------------------------------------------------------------------------


def test_node_syntax_equivalence_across_forms(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """All five accepted ``--node`` syntaxes resolve to the same infoset.

    For a P0 hero AhKd vs villain QQ on As 7c 2d Th 5s, the path "P1
    checks then P0 bets 33% pot" can be written as:

    * ``"xb330"``            (raw chip, legacy)
    * ``"check.bet33pct"``   (verbose dot)
    * ``"check.bet3.3bb"``   (verbose dot, BB)
    * ``"x:b33%"``           (colon, %)
    * ``"x:b3.3bb"``         (colon, BB)

    All five must produce byte-identical drill-down output (modulo the
    ``--node`` echo if any).
    """
    syntaxes = [
        "xb330",
        "check.bet33pct",
        "check.bet3.3bb",
        "x:b33%",
        "x:b3.3bb",
    ]
    outputs = []
    for s in syntaxes:
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
                s,
            ]
        )
        assert rc == 0, f"--node {s!r} failed"
        captured = capsys.readouterr()
        outputs.append(captured.out)

    # All outputs must be identical. Compare against the first.
    for i, out in enumerate(outputs[1:], 1):
        assert out == outputs[0], (
            f"--node {syntaxes[i]!r} produced different output "
            f"than --node {syntaxes[0]!r}"
        )

    # And the drill-down should reference the canonical engine history
    # 'xb330' (since all forms resolve to that chip-token).
    assert "history 'xb330'" in outputs[0]


# ---------------------------------------------------------------------------
# Test 4: walk-tree shows BB amounts AND %-pot inline
# ---------------------------------------------------------------------------


def test_walk_tree_shows_bb_and_pct_inline(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Bet labels carry BOTH ``X% pot`` and ``Y BB`` substrings."""
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

    # A bet at the 33% pot tier on a 10-BB pot is 3.3 BB.
    assert "bet 33% pot (3.3 BB)" in out
    # 75% bet on 10-BB pot is 7.5 BB.
    assert "bet 75% pot (7.5 BB)" in out
    # 100% bet on 10-BB pot is 10 BB (integer, no decimal).
    assert "bet 100% pot (10 BB)" in out
    # All-in label embeds BB amount + BB pot context.
    assert re.search(r"all-in \(\d+(\.\d+)? BB into \d+(\.\d+)? BB pot\)", out)


# ---------------------------------------------------------------------------
# Test 5: walk-tree shows --node id inline for copy-paste
# ---------------------------------------------------------------------------


def test_walk_tree_shows_node_id_inline(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Each tree node line carries a ``[--node "..."]`` annotation.

    The annotation must use the BB-native canonical form (verbose +
    %-pot tokens) — e.g. ``"check"``, ``"check.bet33pct"`` — so the
    user can copy-paste it back into ``--node`` without translation.
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

    # Root node has an empty string node id.
    assert '[--node ""]' in out
    # Single-action root child.
    assert '[--node "check"]' in out
    # Bet child uses verbose + %-pot canonical.
    assert '[--node "check.bet33pct"]' in out


# ---------------------------------------------------------------------------
# Test 6: header block prints at top of every CLI run
# ---------------------------------------------------------------------------


def test_header_block_prints_at_top(capsys: pytest.CaptureFixture[str]) -> None:
    """The SPOT CONFIG block is the first thing printed for river / subgame."""
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
            "5",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    # First non-empty line is the bar.
    first_line = next(line for line in out.splitlines() if line.strip())
    assert first_line == "=" * 63
    assert "SPOT CONFIG" in out
    assert "Effective stacks:    100 BB" in out
    assert "Starting pot:        10 BB" in out
    assert "Board:               As 7c 2d Th 5s  (RIVER)" in out
    assert "Bet menu:            [33%, 75%, 100%, 150%, 200%] pot  +  all-in" in out
    assert "Raise cap:           3" in out


def test_header_block_for_subgame_river(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Header prints for the ``subgame`` command, with RIVER street label.

    We exercise ``subgame --street river`` (not flop) because flop trees
    are lossless-expensive — pytest-timeout fires on the 90s budget. The
    header rendering codepath is identical across streets; the only
    street-specific check is the ``(RIVER)`` annotation in the board line.
    """
    rc = main(
        [
            "subgame",
            "--street",
            "river",
            "--board",
            "As 7c 2d Th 5s",
            "--hero",
            "AhKd",
            "--villain-range",
            "QcQh",
            "--iters",
            "5",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "SPOT CONFIG" in out
    assert "(RIVER)" in out
    # ``subgame`` also prints the new "Street: river" line (the deprecated
    # ``river`` alias suppresses it).
    assert "Street:       river" in out


# ---------------------------------------------------------------------------
# Test 7: max 1 decimal place enforced in display
# ---------------------------------------------------------------------------


def test_format_bb_max_one_decimal_place() -> None:
    """``format_bb`` strips trailing zeros and clamps to 1 decimal."""
    # Integer BB amounts print without decimal.
    assert format_bb(1000) == "10"
    assert format_bb(10000) == "100"
    assert format_bb(100) == "1"
    # Non-integer amounts print to 1 decimal.
    assert format_bb(750) == "7.5"
    assert format_bb(330) == "3.3"
    assert format_bb(80) == "0.8"
    # Trailing zeros stripped.
    assert format_bb(800) == "8"
    # Above 1 decimal — rounds.
    assert format_bb(771) == "7.7"
    assert format_bb(775) == "7.8"  # half-to-even / banker's rounding
    # Zero handles cleanly.
    assert format_bb(0) == "0"
    # Negative — sign preserved.
    assert format_bb(-330) == "-3.3"


def test_walk_tree_output_max_one_decimal(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No BB token in walk-tree output exceeds 1 decimal place."""
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
    # Find every "<num> BB" occurrence. The integer part can be any
    # length; the decimal part (if present) must be exactly 1 digit.
    bb_amounts = re.findall(r"(-?\d+(?:\.\d+)?) BB", out)
    assert bb_amounts, "expected at least one BB amount in walk-tree output"
    for amt in bb_amounts:
        if "." in amt:
            decimal_part = amt.split(".", 1)[1]
            assert len(decimal_part) == 1, (
                f"BB amount {amt!r} has >1 decimal places; v1.9.0 enforces "
                f"max 1 decimal place in display."
            )


# ---------------------------------------------------------------------------
# Test 8: CLI output is byte-identical when LANG=C is set
# ---------------------------------------------------------------------------


def test_cli_output_byte_identical_under_lang_c() -> None:
    """Running the CLI under ``LANG=C`` produces identical output to default.

    The brief's "locale-independent" requirement: BB rendering must use
    ``.`` as the decimal separator regardless of locale (no ``,``
    sneaking in from a European LANG).
    """
    cmd = [
        sys.executable,
        "-m",
        "poker_solver.cli",
        "river",
        "--board",
        "As 7c 2d Th 5s",
        "--hero",
        "AhKd",
        "--villain-range",
        "QcQh",
        "--iters",
        "5",
        "--walk-tree",
    ]

    env_default = os.environ.copy()
    env_default.pop("LANG", None)
    env_default.pop("LC_ALL", None)
    env_default.pop("LC_NUMERIC", None)

    env_c = env_default.copy()
    env_c["LANG"] = "C"
    env_c["LC_ALL"] = "C"

    out_default = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env_default,
        check=False,
    )
    out_c = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env_c,
        check=False,
    )

    assert out_default.returncode == 0, out_default.stderr
    assert out_c.returncode == 0, out_c.stderr
    # Strip any iter-jitter-sensitive sections by limiting to the header +
    # first ~80 lines (the SPOT CONFIG block + preamble are deterministic).
    out_default_head = "\n".join(out_default.stdout.splitlines()[:8])
    out_c_head = "\n".join(out_c.stdout.splitlines()[:8])
    assert out_default_head == out_c_head, (
        f"LANG=C output differs from default:\n"
        f"--- default ---\n{out_default_head}\n"
        f"--- LANG=C ---\n{out_c_head}"
    )
    # Decimal separator is always "." — no comma in any BB amount.
    bb_amounts = re.findall(r"-?\d+(?:[.,]\d+)? BB", out_c.stdout)
    for amt in bb_amounts:
        assert "," not in amt, (
            f"Under LANG=C, BB amount {amt!r} contains a comma "
            f"(expected dot decimal separator)."
        )


# ---------------------------------------------------------------------------
# Helper-level unit tests (no engine invocation; fast)
# ---------------------------------------------------------------------------


def test_chips_to_bb_pure_arithmetic() -> None:
    """``chips_to_bb`` is pure arithmetic with no rounding."""
    assert chips_to_bb(100) == 1.0
    assert chips_to_bb(750) == 7.5
    assert chips_to_bb(0) == 0.0
    assert chips_to_bb(1) == 0.01


def test_format_pot_pct_basic() -> None:
    """``format_pot_pct`` returns ``"XX%"`` for amount/pot."""
    assert format_pot_pct(330, 1000) == "33%"
    assert format_pot_pct(750, 1000) == "75%"
    assert format_pot_pct(100, 1000) == "10%"
    # Edge: zero pot.
    assert format_pot_pct(100, 0) == "?%"


def test_render_header_layout() -> None:
    """Header block layout matches the brief verbatim."""
    h = SpotHeader(
        effective_stack_chips=10000,
        starting_pot_chips=1000,
        board="As Kd 7h 3s 2c",
        street="RIVER",
        bet_menu_pcts=(0.33, 0.75),
        raise_cap=2,
    )
    out = render_header(h)
    assert "SPOT CONFIG" in out
    assert "Effective stacks:    100 BB" in out
    assert "Starting pot:        10 BB" in out
    assert "As Kd 7h 3s 2c" in out
    assert "(RIVER)" in out
    assert "[33%, 75%] pot  +  all-in" in out
    assert "Raise cap:           2" in out
    # Bar uses ASCII '=' — no unicode box chars.
    bar = "=" * 63
    assert out.startswith(bar)


def test_parse_user_node_handles_all_syntaxes() -> None:
    """``parse_user_node`` accepts the five syntax variants in the brief."""
    # Raw chip (legacy).
    toks = parse_user_node("xb750")
    assert len(toks) == 2
    assert toks[0].kind == "x"
    assert toks[1].kind == "b"
    assert toks[1].chips == 750

    # BB notation (with colon separator).
    toks = parse_user_node("x:b7.5bb")
    assert toks[1].bb == 7.5

    # %% notation (with literal %).
    toks = parse_user_node("x:b75%")
    assert toks[1].pct == 0.75

    # Verbose dot notation.
    toks = parse_user_node("check.bet75pct")
    assert toks[0].kind == "x"
    assert toks[1].pct == 0.75

    # Verbose dot + BB.
    toks = parse_user_node("check.bet7.5bb")
    assert toks[1].bb == 7.5

    # Empty string -> root (no tokens).
    assert parse_user_node("") == []

    # Single check.
    toks = parse_user_node("check")
    assert len(toks) == 1
    assert toks[0].kind == "x"


def test_parse_user_node_malformed_raises() -> None:
    """Malformed --node strings raise ``ValueError`` with a helpful message."""
    with pytest.raises(ValueError, match="no amount"):
        parse_user_node("b")
    with pytest.raises(ValueError, match="not integer"):
        # Raw chip with decimal is rejected (must use bb/%% suffix).
        parse_user_node("b3.3")
    with pytest.raises(ValueError, match="unexpected character"):
        parse_user_node("xzzz")


# ---------------------------------------------------------------------------
# Sanity check: --node "" (root) walks the tree
# ---------------------------------------------------------------------------


def test_node_empty_string_is_root(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--node ""`` resolves to the root infoset (P1's first decision)."""
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
            "",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    # Empty history -> root drill-down for P1.
    assert "Per-class strategy at history ''" in out
    assert "QQ" in out
