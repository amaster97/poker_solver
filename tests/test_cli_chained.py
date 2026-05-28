"""Task #58 — CLI tests for the ``chained`` subcommand.

Covers the four happy-path scenarios from the task spec:

  1. Basic invocation completes and prints expected sections (text mode).
  2. ``--board`` triggers a lazy postflop solve and the output reflects it.
  3. ``--format json`` round-trips through ``json.loads`` with the expected
     top-level keys; ``--format csv`` emits a header + parseable rows.
  4. Error handling: missing ``--hero-range`` (argparse exit code 2);
     ``--stacks 1`` (too small, our ValueError -> exit 2).

These tests use *small* ranges (2x2: ``AA, KK``) and very low iteration
counts (preflop=30, postflop=30) so they finish in seconds — the full
chained pipeline solves 4 per-pair preflop subgames + (with ``--board``)
1 postflop flop subgame per terminal. Even at those minimums the test
takes ~30-60s; the ``@pytest.mark.timeout`` guards keep CI honest.
"""

from __future__ import annotations

import csv as _csv_mod
import io as _io_mod
import json
import warnings

import pytest

from poker_solver.cli import main


def _run(argv: list[str]) -> int:
    """Run ``main()`` with ``UserWarning``s silenced (mirrors test_cli_subgame)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return main(argv)


# ---------------------------------------------------------------------------
# 1. Basic invocation — default text format
# ---------------------------------------------------------------------------


@pytest.mark.timeout(180)
def test_chained_basic_text_output(capsys: pytest.CaptureFixture[str]) -> None:
    """``poker-solver chained ...`` prints preflop + continuation sections.

    With no ``--board`` the postflop step is skipped, so the output must
    still contain the preflop matrix + the per-action continuation
    ranges block.
    """
    rc = _run(
        [
            "chained",
            "--hero-range", "AA,KK",
            "--villain-range", "AA,KK",
            "--stacks", "50",
            "--preflop-iterations", "30",
            "--postflop-iterations", "30",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out

    # Headline sections present.
    assert "Chained preflop solve" in out
    assert "Hero range:" in out
    assert "Villain range:" in out
    assert "Stacks:          50 BB" in out
    assert "Preflop iters:   30" in out
    assert "Postflop iters:  30" in out
    assert "Position:        aggressor" in out

    # Preflop strategy sections.
    assert "Preflop range aggregate" in out
    assert "Preflop per-class strategy:" in out
    # Both hero classes show up in the per-class section.
    assert "AA      " in out or "AA " in out
    assert "KK      " in out or "KK " in out

    # Continuation ranges block (≥1 flop-reaching terminal at 50 BB).
    assert "Continuation ranges" in out
    assert "flop-reaching terminals" in out

    # Without --board, the postflop section is not emitted.
    assert "Postflop strategy on" not in out


# ---------------------------------------------------------------------------
# 2. --board triggers lazy postflop solve
# ---------------------------------------------------------------------------


@pytest.mark.timeout(600)
def test_chained_with_board_runs_postflop(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--board "Ks 8d 2h"`` adds a postflop strategy section to the output.

    Caps the postflop solve count to 1 so the test runs in a reasonable
    budget — each flop-subgame solve via Rust vector-form CFR at 30
    iters costs ~5 min on this hardware even on a 2x2 range. The
    important CLI invariant (that ``--board`` triggers postflop +
    surfaces it in the output) is exercised by solving exactly one
    terminal.
    """
    rc = _run(
        [
            "chained",
            "--hero-range", "AA,KK",
            "--villain-range", "AA,KK",
            "--stacks", "50",
            "--preflop-iterations", "30",
            "--postflop-iterations", "30",
            "--board", "Ks 8d 2h",
            "--max-postflop-terminals", "1",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out

    # The board is echoed in the preamble.
    assert "Flop:" in out
    assert "Ks 8d 2h" in out

    # The postflop section is present.
    assert "Postflop strategy on Ks 8d 2h" in out
    # Some "After [...]:" header should appear (one per flop-reaching
    # terminal that was solved against this board).
    assert "After [" in out


@pytest.mark.timeout(180)
def test_chained_board_with_lazy_postflop_false_skips_postflop(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--lazy-postflop false`` suppresses postflop solves even with ``--board``."""
    rc = _run(
        [
            "chained",
            "--hero-range", "AA,KK",
            "--villain-range", "AA,KK",
            "--stacks", "50",
            "--preflop-iterations", "30",
            "--postflop-iterations", "30",
            "--board", "Ks 8d 2h",
            "--lazy-postflop", "false",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    # Board still echoed (the user asked for it), but no postflop solve.
    assert "Ks 8d 2h" in out
    assert "After [" not in out


# ---------------------------------------------------------------------------
# 3. JSON / CSV format roundtrip
# ---------------------------------------------------------------------------


@pytest.mark.timeout(180)
def test_chained_format_json_roundtrip(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--format json`` emits a payload parseable by ``json.loads``.

    Verifies the expected top-level keys + that the preflop result
    sub-object carries the per-class strategy and range aggregate.
    """
    rc = _run(
        [
            "chained",
            "--hero-range", "AA,KK",
            "--villain-range", "AA,KK",
            "--stacks", "50",
            "--preflop-iterations", "30",
            "--postflop-iterations", "30",
            "--format", "json",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)

    expected_top = {
        "hero_range",
        "villain_range",
        "stacks_bb",
        "preflop_iterations",
        "postflop_iterations",
        "board",
        "preflop_result",
        "continuation_ranges",
        "postflop_solves",
    }
    assert expected_top <= set(payload.keys()), (
        f"missing top-level keys: {expected_top - set(payload.keys())}; "
        f"got: {sorted(payload.keys())}"
    )
    assert payload["hero_range"] == "AA,KK"
    assert payload["villain_range"] == "AA,KK"
    assert payload["stacks_bb"] == 50
    assert payload["board"] is None  # not requested

    pre = payload["preflop_result"]
    assert pre["backend"] == "python_chained_route_a"
    assert pre["position"] == "aggressor"
    per_class = pre["per_class_strategy"]
    assert set(per_class.keys()) == {"AA", "KK"}
    # Per-class rows sum to 1 within float epsilon.
    for cls, freqs in per_class.items():
        total = sum(freqs.values())
        assert abs(total - 1.0) < 1e-5, (
            f"per_class[{cls!r}] sums to {total}, expected 1.0; "
            f"freqs={freqs}"
        )

    # At least one flop-reaching continuation entry.
    assert len(payload["continuation_ranges"]) >= 1
    # No --board passed -> no postflop solves.
    assert payload["postflop_solves"] == {}


@pytest.mark.timeout(180)
def test_chained_format_csv_roundtrip(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--format csv`` emits a header + parseable rows.

    Checks the expected column header and verifies every preflop row
    sums to a probability in [0, 1] (rough sanity).
    """
    rc = _run(
        [
            "chained",
            "--hero-range", "AA,KK",
            "--villain-range", "AA,KK",
            "--stacks", "50",
            "--preflop-iterations", "30",
            "--postflop-iterations", "30",
            "--format", "csv",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out

    reader = _csv_mod.reader(_io_mod.StringIO(out))
    rows = list(reader)
    assert rows, "CSV output empty"

    # Header.
    header = rows[0]
    assert header == [
        "scope", "action_sequence", "hand_class", "action", "probability",
    ]

    # Data rows: scope is one of preflop/postflop, probability is a float in
    # [0, 1] (allow tiny float slop).
    data_rows = rows[1:]
    assert data_rows, "no data rows in CSV"
    preflop_count = 0
    for row in data_rows:
        assert len(row) == 5
        scope, action_seq, hand_class, action, prob_str = row
        assert scope in ("preflop", "postflop")
        prob = float(prob_str)
        assert -1e-6 <= prob <= 1.0 + 1e-6, (
            f"probability out of range: {prob_str!r} in row {row!r}"
        )
        if scope == "preflop":
            # The preflop scope uses an empty action_sequence column.
            assert action_seq == ""
            preflop_count += 1
            assert hand_class in ("AA", "KK")
    assert preflop_count >= 2, "expected ≥2 preflop CSV rows (one per class × action)"


# ---------------------------------------------------------------------------
# 4. Error handling
# ---------------------------------------------------------------------------


def test_chained_missing_hero_range_exits_nonzero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Argparse rejects the call when ``--hero-range`` is omitted.

    Argparse's required-flag enforcement raises ``SystemExit(2)`` (not a
    ``ValueError``), so we expect ``SystemExit`` with code 2 here, and
    a stderr message naming the missing flag.
    """
    with pytest.raises(SystemExit) as excinfo:
        _run(
            [
                "chained",
                "--villain-range", "AA",
                "--stacks", "50",
                "--preflop-iterations", "30",
                "--postflop-iterations", "30",
            ]
        )
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "--hero-range" in err


def test_chained_invalid_stack_returns_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--stacks 1`` (below the 2 BB floor) prints an error + exits non-zero.

    The CLI's ``ValueError`` path in ``main()`` prints to stderr and
    returns exit code 2.
    """
    rc = _run(
        [
            "chained",
            "--hero-range", "AA",
            "--villain-range", "AA",
            "--stacks", "1",
            "--preflop-iterations", "30",
            "--postflop-iterations", "30",
        ]
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "stacks" in err.lower()


def test_chained_invalid_board_length_returns_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A non-flop ``--board`` (e.g. 4 cards) is rejected with a clear error."""
    rc = _run(
        [
            "chained",
            "--hero-range", "AA",
            "--villain-range", "KK",
            "--stacks", "50",
            "--preflop-iterations", "30",
            "--postflop-iterations", "30",
            "--board", "Ks 8d 2h 5c",
        ]
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "flop" in err.lower() or "board" in err.lower()


def test_chained_invalid_format_rejected(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An unknown ``--format`` value is rejected by argparse."""
    with pytest.raises(SystemExit) as excinfo:
        _run(
            [
                "chained",
                "--hero-range", "AA",
                "--villain-range", "KK",
                "--stacks", "50",
                "--preflop-iterations", "30",
                "--postflop-iterations", "30",
                "--format", "xml",  # not in choices
            ]
        )
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "format" in err.lower()
