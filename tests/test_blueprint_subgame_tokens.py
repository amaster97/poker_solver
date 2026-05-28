"""Unit tests for ``_tokens_equivalent`` in :mod:`poker_solver.blueprint_subgame`.

Background
----------
The Rust preflop engine (``crates/cfr_core/src/preflop_rvr.rs``) emits
``b<amt>`` tokens for SB's opening raise (treating the open as a "bet"),
while the Python ``HUNLPoker`` engine emits ``r<amt>`` for the same
action (treating the BB blind as a pending bet). Both refer to the same
physical action when the chip amount matches. ``_tokens_equivalent``
normalizes this mismatch so the postflop subgame wiring can walk a
preflop action prefix produced by either side without spurious
"action not found" failures.

Tests
-----
* Identical tokens are equivalent (``"b250" == "b250"``, ``"f" == "f"``).
* ``b<amt>``/``r<amt>`` pairs with the same numeric amount are
  equivalent.
* Different amounts are not equivalent.
* Non-numeric ``b``/``r`` tokens are not silently equivalent.
* Unrelated tokens (``"f"``, ``"c"``, ``"x"``) only match themselves.
"""

from __future__ import annotations

from poker_solver.blueprint_subgame import _tokens_equivalent


class TestTokensEquivalent:
    """Verify the b/r preflop-token normalizer."""

    def test_identical_tokens_are_equivalent(self) -> None:
        assert _tokens_equivalent("b250", "b250") is True
        assert _tokens_equivalent("r250", "r250") is True
        assert _tokens_equivalent("f", "f") is True
        assert _tokens_equivalent("c", "c") is True
        assert _tokens_equivalent("x", "x") is True

    def test_b_and_r_with_same_amount_are_equivalent(self) -> None:
        # The headline case: Rust emits "b250", Python emits "r250"
        # for SB's opening raise to 250 chips.
        assert _tokens_equivalent("b250", "r250") is True
        assert _tokens_equivalent("r250", "b250") is True

    def test_b_and_r_with_different_amounts_are_not_equivalent(self) -> None:
        assert _tokens_equivalent("b250", "r300") is False
        assert _tokens_equivalent("r250", "b300") is False
        assert _tokens_equivalent("b100", "b200") is False
        assert _tokens_equivalent("r100", "r200") is False

    def test_fold_and_call_not_equivalent_to_raises(self) -> None:
        assert _tokens_equivalent("f", "b250") is False
        assert _tokens_equivalent("c", "r250") is False
        assert _tokens_equivalent("x", "b100") is False

    def test_unrelated_simple_tokens_are_not_equivalent(self) -> None:
        assert _tokens_equivalent("f", "c") is False
        assert _tokens_equivalent("c", "x") is False
        assert _tokens_equivalent("f", "x") is False

    def test_non_numeric_b_r_tokens_are_not_equivalent(self) -> None:
        # The normalizer requires both bodies to be all-digit. If a
        # caller passes something weird, fall back to strict equality.
        assert _tokens_equivalent("babc", "rabc") is False
        assert _tokens_equivalent("b25x", "r25x") is False

    def test_b_alone_is_not_equivalent_to_r_alone(self) -> None:
        # Single-char "b"/"r" have no numeric body and should not
        # collapse onto each other.
        assert _tokens_equivalent("b", "r") is False

    def test_amount_with_leading_zero_compared_as_string(self) -> None:
        # Engines emit canonical decimal strings, so "b25" and "b025"
        # would not match — that's correct behaviour (they would
        # represent different amounts under leading-zero conventions,
        # and we don't want to be lax here).
        assert _tokens_equivalent("b25", "r025") is False
