"""GUI-agnostic POSTFLOP off-path detection + cleaning (per-combo, board-aware).

This module is the postflop analogue of :mod:`poker_solver.preflop_offpath`.
Where the preflop module works on per-HAND-CLASS line projections, the
postflop solver emits a per-(history, CONCRETE-COMBO) strategy
(``RangeVsRangeNashResult.per_history_strategy``), so off-path detection is
done PER COMBO, accounting for the board, and STREET-BY-STREET.

It has NO nicegui / AppState coupling: every public function takes the raw
``per_history_strategy`` mapping plus an explicit ``hero_range`` (the result
dataclass does NOT carry the range or board — verified empirically) and a
``board``, and returns plain dicts. The raw engine output is NEVER mutated;
``clean_off_path`` returns a fresh deep copy.

Data shapes (verified empirically against ``solve_range_vs_range_nash`` on a
small river subgame)
---------------------------------------------------------------------------
* ``per_history_strategy`` — ``{ infoset_key -> list[float] }`` where the key
  is ``"<hole>|<board>||<history>"``:

    - ``<hole>``  — the 4-char Rust hole-string ``rank+suit+rank+suit``
      (lowercase suit), e.g. ``"AcAd"`` (matches
      ``range_aggregator._hole_string_rust`` exactly).
    - the FIRST ``|`` separates hole from board; ``<board>`` is the board
      cards concatenated, e.g. ``"2h7dTcJs5c"``.
    - ``||`` separates the board (+ empty street marker) from the action
      history; ``<history>`` is the action-token body (possibly empty at the
      first-to-act root).

  The ONLY non-alphanumeric delimiter in a key is ``|`` (no commas). The
  history body has NO within-street token separator (tokens are
  concatenated, e.g. ``"b666b3996"``); STREETS are separated by ``"/"``
  (the ``HUNLState.infoset_key`` format: actions are joined by ``"/"``
  between streets). The VALUE is a positional probability LIST (NOT a
  label->prob dict): index 0 is the passive action (``check`` when
  first-to-act, ``fold`` when facing a bet); when facing a bet index 1 is
  ``call``; the remaining indices are bet/raise sizes in ascending order.

* ``hero_range`` — ``{ hole_str -> weight }`` (e.g. ``{"AcAd": 1.0, ...}``)
  keyed on the SAME 4-char hole-string that prefixes the infoset keys.
  Combos absent from the map contribute weight 0 (not in hero's range).

* ``board`` — the board, either the concatenated string ``"2h7dTcJs5c"`` or
  a sequence of 2-char card tokens ``["2h", "7d", ...]``. Used ONLY to
  identify board-blocked combos (hole ∩ board ≠ ∅ -> reach 0).

Off-path rule (per combo, at a target history)
----------------------------------------------
A combo is off-path at a node when EITHER:

* (reach rule) its normalized reach across the node's combos is below
  :data:`_OFF_PATH_REACH_FRACTION` (0.5%), OR
* (dominance rule) it is dominantly blocked at one of the HERO's OWN
  ancestor decision nodes on this history:

    - :data:`REASON_FOLDED` — fold ≥ :data:`_DOMINANT_THRESHOLD` at any
      ancestor. Carries ACROSS streets (a folded hand is gone for good).
    - :data:`REASON_ALL_IN` — all-in ≥ :data:`_DOMINANT_THRESHOLD` at any
      ancestor. Carries ACROSS streets (no voluntary action after committing
      the stack).
    - :data:`REASON_CHECKED_CLOSED` — a CHECK that CLOSED the street's
      betting (≥ threshold) at an ancestor, where the target line then has
      the hero act AGAIN on the SAME street. SCOPED STRICTLY WITHIN-STREET:
      it off-paths a deeper SAME-street hero decision only, NOT the next
      street (a check that closed the flop legitimately continues to the
      turn — the user's exact ask: "supposed to check 100% but somehow we
      raised and it gets back to us — that's probably a fold; street by
      street").
    - :data:`REASON_CALLED_CLOSED` — a CALL that CLOSED the street's betting
      (≥ threshold) at an ancestor, likewise WITHIN-STREET only.
    - else, when the normalized reach is below threshold ->
      :data:`REASON_LOW_REACH`.

Board-blocked combos (hole card on the board) always have reach 0 and are
off-path (reason :data:`REASON_LOW_REACH`).

Reach (the per-combo product)
-----------------------------
``reach(combo, history) = hero_range_weight[combo] × Π P_continue`` over each
of the HERO's OWN ancestor decision nodes on the history. Opponent decisions
DEFINE the line but do NOT enter the product. At a hero bet/raise ancestor we
credit the combo's TOTAL aggression mass (sum over EVERY bet/raise index at
that node), not just the single matched size — postflop bets/raises are
offered at multiple sizes and a hand that raised by ANY size took this
aggressive action (the same size-agnostic principle the preflop module
adopted; see ``preflop_offpath.reach_and_reason``). Check / call / all-in are
single unambiguous actions credited exactly.

FAIL-SAFE: any step that can't be computed (a prior node missing on the
history, a token that can't be resolved) returns ``None`` reach, and callers
mark NOTHING off-path for that combo/node. ``None`` never marks.

Public API
----------
* :func:`mark_off_path` — ``{key -> bool}``.
* :func:`mark_off_path_with_reason` — ``{key -> None | reason}``.
* :func:`clean_off_path` — a NEW deep-copied ``per_history_strategy`` with
  off-path rows overwritten to fold (index 0 = 1.0, rest 0.0).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

# --------------------------------------------------------------------------- #
# Thresholds + reason codes
# --------------------------------------------------------------------------- #

# Fraction of total reach mass below which a combo is treated as off-path
# ("not in range") at the displayed node. 0.5% — matches the preflop module.
_OFF_PATH_REACH_FRACTION: float = 0.005

# Probability at/above which an action is treated as DOMINANT at an ancestor
# (fold / all-in / check-closed / call-closed). 0.99 — matches preflop.
_DOMINANT_THRESHOLD: float = 0.99

# Off-path reason codes (``None`` == on-path). Per-node priority when several
# could apply at the SAME ancestor:
#   folded > all_in > checked_closed > called_closed
# and a dominant block always outranks the generic low-reach rule.
REASON_FOLDED: str = "folded"
REASON_ALL_IN: str = "all_in"
REASON_CHECKED_CLOSED: str = "checked_closed"
REASON_CALLED_CLOSED: str = "called_closed"
REASON_LOW_REACH: str = "low_reach"

# --------------------------------------------------------------------------- #
# Key + history grammar
# --------------------------------------------------------------------------- #

_KEY_SEP: str = "||"  # separates "<hole>|<board>" from "<history>"
_STREET_SEP: str = "/"  # separates streets within the history body

# A single action token within a street body: check / call / bet<amt> /
# raise<amt> / all-in. ``x`` = check, ``c`` = call, ``b<amt>`` = bet,
# ``r<amt>`` = raise, ``A`` = all-in (verified empirically: histories such as
# ``"b666b3996"`` (no separator within a street) and a trailing ``"A"``).
_TOKEN_RE = re.compile(r"x|c|b\d+|r\d+|A")


def _split_key(key: str) -> tuple[str | None, str | None, str | None]:
    """Split an infoset key into ``(hole, board, history)``.

    Key format: ``"<hole>|<board>||<history>"``. The FIRST ``|`` separates
    hole from board; ``||`` separates the board(+street marker) from the
    action history. Returns ``(None, None, None)`` when the key lacks the
    ``||`` separator (defensive against malformed keys -> FAIL-SAFE).
    """
    if _KEY_SEP not in key:
        return (None, None, None)
    head, hist = key.split(_KEY_SEP, 1)
    # ``head`` is ``"<hole>|<board>"`` (board may be empty). The hole is the
    # first ``|``-delimited field.
    if "|" in head:
        hole, board = head.split("|", 1)
    else:
        hole, board = head, ""
    return (hole, board, hist)


def _board_tokens(board: str | Sequence[str] | None) -> frozenset[str]:
    """Return the set of 2-char board card tokens.

    Accepts the concatenated string form (``"2h7dTcJs5c"``) or a sequence of
    2-char tokens (``["2h", "7d", ...]``). Empty / ``None`` -> empty set.
    """
    if board is None:
        return frozenset()
    if isinstance(board, str):
        s = board
        return frozenset(s[i : i + 2] for i in range(0, len(s) - 1, 2))
    return frozenset(str(t) for t in board)


def _hole_cards(hole: str) -> tuple[str, str] | None:
    """Split a 4-char hole-string into its two 2-char cards, or ``None``."""
    if len(hole) != 4:
        return None
    return (hole[:2], hole[2:4])


def _is_bet_token(token: str) -> bool:
    """``True`` for a bet / raise token (``b<amt>`` / ``r<amt>``)."""
    return bool(token) and token[0] in "br"


# --------------------------------------------------------------------------- #
# Actor model
# --------------------------------------------------------------------------- #
#
# Postflop the OUT-OF-POSITION player acts first on EVERY street; players
# alternate within a street; a new street (``/``) resets the actor to OOP.
# So at a node the actor is OOP when the number of action tokens IN THE
# CURRENT STREET is even, IP when odd (verified empirically: ``""`` -> OOP,
# ``"x"`` -> IP, ``"b666"`` -> IP, ``"b666b3996"`` -> OOP, ...).
#
# The hero's seat (OOP vs IP) is supplied by the caller (``hero_is_oop``):
# in the ``solve_range_vs_range_nash`` convention ``hero_player == 1`` puts
# hero OOP. The reach walk multiplies in ONLY the hero's own-actor nodes.


def _street_segments(history: str) -> list[str]:
    """Split a history body into per-street token bodies (on ``/``)."""
    return history.split(_STREET_SEP)


def _tokens(street_body: str) -> list[str]:
    """Tokenize a single street's action body."""
    return _TOKEN_RE.findall(street_body)


def _actor_is_oop_at(tokens_so_far_in_street: int) -> bool:
    """OOP acts when an even number of tokens precede this decision."""
    return tokens_so_far_in_street % 2 == 0


def _node_is_facing_bet(prev_tokens_in_street: list[str]) -> bool:
    """``True`` when the immediately preceding in-street token is a bet/raise.

    A node "faces a bet" when the last action in the current street was an
    aggressive action (bet/raise/all-in) that has not yet been answered — i.e.
    the actor here must fold / call / raise. When there is no preceding
    in-street token (or the last was a check/call), the actor is first-to-act
    or the betting was passive, so index 0 is a CHECK, not a fold.
    """
    if not prev_tokens_in_street:
        return False
    last = prev_tokens_in_street[-1]
    return _is_bet_token(last) or last == "A"


# --------------------------------------------------------------------------- #
# Positional action-index helpers
# --------------------------------------------------------------------------- #
#
# ``per_history_strategy`` values are positional probability LISTS, not
# label dicts. The canonical legal-action ordering the engine emits is:
#   * first-to-act (not facing a bet): [check, bet_1, bet_2, ...]
#   * facing a bet:                    [fold,  call,  raise_1, ...]
# (verified: root [check, b666, b1332]; facing b666 -> [fold, call]).


def _passive_index() -> int:
    """Index of the passive action (check or fold) — always 0."""
    return 0


def _call_index() -> int:
    """Index of the call action at a facing-bet node — always 1."""
    return 1


def _aggressive_indices(n_labels: int, facing_bet: bool) -> list[int]:
    """Indices of the bet/raise actions in a node's probability list.

    * first-to-act: index 0 is check, so bets are indices 1..n-1.
    * facing a bet: index 0 fold, 1 call, so raises are indices 2..n-1.
    """
    start = 2 if facing_bet else 1
    return list(range(start, n_labels))


# --------------------------------------------------------------------------- #
# Reach + reason walk (single pass per combo)
# --------------------------------------------------------------------------- #


def reach_and_reason(
    per_history_strategy: Mapping[str, Sequence[float]] | None,
    combo: str,
    board: str,
    target_history: str,
    *,
    hero_is_oop: bool,
) -> tuple[float, str | None] | None:
    """Walk the hero's line once; return ``(reach, block_reason)`` or ``None``.

    Single pass over the HERO's OWN ancestor decision nodes on
    ``target_history``. ``reach`` is the product of the hero's continuing
    probabilities (root / no gating -> ``1.0``); ``block_reason`` is the
    EARLIEST dominantly-blocking ancestor's reason (``None`` if none).

    The street-scoped reasons (``checked_closed`` / ``called_closed``) only
    fire when the passive close and a LATER hero decision are on the SAME
    street as the block, and the block sits on the target street: a passive
    close that simply ended an earlier street does NOT carry forward (the hand
    legitimately continues to the next street). ``folded`` / ``all_in`` carry
    across all streets.

    Returns ``None`` (FAIL-SAFE) when the walk can't be completed: a gating
    node missing from ``per_history_strategy`` or a row with the wrong shape.
    """
    if per_history_strategy is None:
        return None

    target_streets = _street_segments(target_history)
    target_street_idx = len(target_streets) - 1

    r = 1.0
    block_reason: str | None = None

    # Walk every street up to (and including) the target street.
    for s_idx, street_body in enumerate(target_streets):
        toks = _tokens(street_body)
        for t_idx, tok in enumerate(toks):
            # Is the actor at THIS decision the hero? OOP acts on even
            # in-street counts; hero is OOP iff ``hero_is_oop``.
            actor_is_oop = _actor_is_oop_at(t_idx)
            if actor_is_oop != hero_is_oop:
                continue  # opponent's decision — defines the line, not reach
            # Reconstruct the gating node's infoset key: same hole + board,
            # history = streets[:s_idx] + this street's tokens[:t_idx].
            prefix_streets = list(target_streets[:s_idx])
            prefix_streets.append("".join(toks[:t_idx]))
            prefix_hist = _STREET_SEP.join(prefix_streets)
            node_key = f"{combo}|{board}{_KEY_SEP}{prefix_hist}"
            row = per_history_strategy.get(node_key)
            if row is None or len(row) == 0:
                return None  # FAIL-SAFE: gating node missing / terminal
            facing_bet = _node_is_facing_bet(toks[:t_idx])

            # Does the hero act AGAIN later in THIS SAME street on the target
            # line? A passive close (check ending the street / call closing the
            # action) means the hero does NOT act again this street — so if the
            # target line DOES have a later same-street hero decision, the
            # passive close makes that line off-path. (User's exact ask:
            # "supposed to check 100% but somehow we raised and it gets back to
            # us — that's probably a fold; street by street".)
            later_hero_same_street = any(
                _actor_is_oop_at(j) == hero_is_oop
                for j in range(t_idx + 1, len(toks))
            )

            # --- Dominance checks (record EARLIEST block only) --------------
            # Per-node priority:
            #   folded > all_in > checked_closed > called_closed.
            # fold / all_in carry ACROSS streets (gone for good); the passive
            # closes are SCOPED to the street they occur on — recorded as a
            # ``(reason, street_idx)`` tuple and resolved after the walk.
            if block_reason is None:
                pi = _passive_index()
                passive_p = row[pi] if pi < len(row) else 0.0
                agg = sum(
                    row[i] for i in _aggressive_indices(len(row), facing_bet)
                )
                if facing_bet:
                    fold_p = passive_p  # index 0 == fold when facing a bet
                    ci = _call_index()
                    call_p = row[ci] if ci < len(row) else 0.0
                    if fold_p >= _DOMINANT_THRESHOLD:
                        block_reason = REASON_FOLDED
                    elif tok == "A" and agg >= _DOMINANT_THRESHOLD:
                        block_reason = REASON_ALL_IN
                    elif later_hero_same_street and call_p >= _DOMINANT_THRESHOLD:
                        block_reason = (REASON_CALLED_CLOSED, s_idx)  # type: ignore[assignment]
                else:
                    check_p = passive_p
                    if tok == "A" and agg >= _DOMINANT_THRESHOLD:
                        block_reason = REASON_ALL_IN
                    elif later_hero_same_street and check_p >= _DOMINANT_THRESHOLD:
                        block_reason = (REASON_CHECKED_CLOSED, s_idx)  # type: ignore[assignment]

            # --- Reach product (size-agnostic at hero's own bet/raise) -----
            if _is_bet_token(tok) or tok == "A":
                agg_idx = _aggressive_indices(len(row), facing_bet)
                r *= sum(row[i] for i in agg_idx) if agg_idx else 0.0
            elif tok == "c":
                ci = _call_index()
                if facing_bet and ci < len(row):
                    r *= row[ci]
                else:
                    pi = _passive_index()
                    r *= row[pi] if pi < len(row) else 0.0
            else:  # check (x)
                pi = _passive_index()
                r *= row[pi] if pi < len(row) else 0.0

    # Resolve street-scoped blocks: keep a passive-close block only when it sits
    # on the TARGET street (it does not carry forward to a later street).
    if isinstance(block_reason, tuple):
        reason_code, block_street = block_reason
        block_reason = reason_code if block_street == target_street_idx else None

    return r, block_reason


# --------------------------------------------------------------------------- #
# Public primitives
# --------------------------------------------------------------------------- #


def _board_blocked(combo: str, board_set: frozenset[str]) -> bool:
    """``True`` when either hole card of ``combo`` is on the board."""
    cards = _hole_cards(combo)
    if cards is None:
        return False
    c1, c2 = cards
    return c1 in board_set or c2 in board_set


def _combos_at(
    per_history_strategy: Mapping[str, Sequence[float]],
    board: str,
    history: str,
) -> list[str]:
    """Return the hole-strings present at node ``history`` in the map."""
    out: list[str] = []
    for key in per_history_strategy:
        hole, b, h = _split_key(key)
        if hole is None:
            continue
        if b == board and h == history:
            out.append(hole)
    return out


def mark_off_path_with_reason(
    per_history_strategy: Mapping[str, Sequence[float]] | None,
    hero_range: Mapping[str, float] | None,
    *,
    board: str | Sequence[str],
    history: str,
    hero_is_oop: bool = True,
    combos: Sequence[str] | None = None,
) -> dict[str, None | str]:
    """Return ``{combo -> reason}`` for one ``history`` node.

    ``reason`` is ``None`` (on-path) or an off-path code (see module docs).
    Both the reach signal and the dominance reason come from a SINGLE walk per
    combo via :func:`reach_and_reason`. FAIL-SAFE: if the walk is ``None`` for
    ANY combo (a gating node missing), NOTHING is marked — every combo returns
    ``None`` (mirrors the preflop module's per-line fail-safe).

    ``board`` may be the concatenated string or a 2-char token sequence.
    ``combos`` defaults to the combos present at ``history`` in the map.
    """
    board_str = (
        board if isinstance(board, str) else "".join(str(t) for t in board)
    )
    board_set = _board_tokens(board)
    if per_history_strategy is None:
        return {}
    if combos is None:
        combos = _combos_at(per_history_strategy, board_str, history)
    hero_range = hero_range or {}

    reaches: dict[str, float] = {}
    block: dict[str, str | None] = {}
    for combo in combos:
        # Board-blocked combos have reach 0 and are off-path by low_reach.
        if _board_blocked(combo, board_set):
            reaches[combo] = 0.0
            block[combo] = None
            continue
        rr = reach_and_reason(
            per_history_strategy,
            combo,
            board_str,
            history,
            hero_is_oop=hero_is_oop,
        )
        if rr is None:
            # Walk not computable -> mark nothing for the whole node.
            return {c: None for c in combos}
        product, reason = rr
        reaches[combo] = product * float(hero_range.get(combo, 0.0))
        block[combo] = reason

    # Normalize reach over the NON-dominantly-blocked combos only (a blocked
    # combo's product is the pre-block partial and must not inflate the
    # denominator). Matches the preflop normalization posture.
    total = sum(reaches[c] for c in combos if block[c] is None)

    def _reason_for(combo: str) -> str | None:
        if block[combo] is not None:
            return block[combo]
        if total <= 0.0:
            # Degenerate: can't discriminate by reach. A genuinely zero-reach
            # combo (board-blocked / zero weight) is still unreachable.
            return REASON_LOW_REACH if reaches[combo] <= 0.0 else None
        if (reaches[combo] / total) < _OFF_PATH_REACH_FRACTION:
            return REASON_LOW_REACH
        return None

    return {c: _reason_for(c) for c in combos}


def mark_off_path(
    per_history_strategy: Mapping[str, Sequence[float]] | None,
    hero_range: Mapping[str, float] | None,
    *,
    board: str | Sequence[str],
    history: str,
    hero_is_oop: bool = True,
    combos: Sequence[str] | None = None,
) -> dict[str, bool]:
    """Return ``{combo -> off_path}`` for one ``history`` node.

    Derived from :func:`mark_off_path_with_reason` so the boolean and the
    reason map stay consistent (``off_path == reason is not None``).
    FAIL-SAFE: when the walk isn't computable for any combo, nothing is marked.
    """
    reasons = mark_off_path_with_reason(
        per_history_strategy,
        hero_range,
        board=board,
        history=history,
        hero_is_oop=hero_is_oop,
        combos=combos,
    )
    return {c: reason is not None for c, reason in reasons.items()}


def _fold_overwrite(row: Sequence[float]) -> list[float]:
    """Return a fresh probability row folded 100% (index 0 = 1.0, rest 0.0).

    Index 0 is the passive/give-up action (fold when facing a bet, check
    otherwise) — overwriting it to 1.0 is the postflop analogue of the
    preflop fold-overwrite (which forced the ``"fold"`` label to 1.0).
    """
    n = len(row)
    if n == 0:
        return []
    cleaned = [0.0] * n
    cleaned[0] = 1.0
    return cleaned


def clean_off_path(
    per_history_strategy: Mapping[str, Sequence[float]] | None,
    hero_range: Mapping[str, float] | None,
    *,
    board: str | Sequence[str],
    hero_is_oop: bool = True,
) -> dict[str, list[float]]:
    """Return a NEW deep-copied ``per_history_strategy`` with off-path folded.

    Every node (history) is evaluated independently against its own
    reach/dominance walk; off-path rows are overwritten so index 0 (the
    passive/give-up action) is 1.0 and every other action is 0.0. On-path rows
    are copied through unchanged.

    NEVER mutates the input — the input mapping and its nested lists are left
    byte-for-byte intact; the result is a deep copy.
    """
    if not per_history_strategy:
        return {}
    out: dict[str, list[float]] = {
        k: list(v) for k, v in per_history_strategy.items()
    }
    board_str = (
        board if isinstance(board, str) else "".join(str(t) for t in board)
    )

    # Group keys by history so each node is walked once.
    nodes: dict[str, list[str]] = {}
    for key in out:
        hole, b, h = _split_key(key)
        if hole is None or b != board_str:
            continue
        nodes.setdefault(h, []).append(hole)

    for history, combos in nodes.items():
        off = mark_off_path(
            per_history_strategy,  # read marks from the RAW input (unmutated)
            hero_range,
            board=board_str,
            history=history,
            hero_is_oop=hero_is_oop,
            combos=combos,
        )
        for combo, is_off in off.items():
            if not is_off:
                continue
            node_key = f"{combo}|{board_str}{_KEY_SEP}{history}"
            if node_key in out:
                out[node_key] = _fold_overwrite(out[node_key])
    return out
