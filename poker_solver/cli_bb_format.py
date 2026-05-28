"""v1.9.0 — BB-native display + node-id translation layer.

The engine + abstraction layers operate in chips (1 BB = 100 chips). The CLI
input parameterization for bet sizes stays % pot (e.g. ``--bet-sizes
33,75,100``). What changes in v1.9.0 is the **outside presentation**:

* Every chip amount surfaced in CLI output is rendered in BB (1 decimal max).
* Walk-tree action labels embed BOTH the %-pot tag (for parameterization
  parity) AND the BB amount (for read-time intuition).
* The ``--node`` parser accepts BB-native tokens (``b7.5bb``, ``bet75pct``,
  ``b750`` raw chips) and canonicalizes them to the engine's chip-token
  format before lookup. The legacy raw-chip syntax keeps working unchanged.

This module is pure presentation — it never touches engine state and never
imports from ``hunl`` / ``solver``. Callers are limited to ``cli.py`` and
``cli_tree_walk.py``.

Three layers (strict separation; engine never sees BB strings):

    engine internal (chips, 1 BB = 100 chips)        — invisible to user
    translation     (chips <-> BB <-> %pot)          — invisible to user
    display + input (BB w/ <=1 decimal, %-pot for bets) — visible to user

The "1 decimal max" rule: 7.5 prints as ``"7.5"``, 100 prints as ``"100"``
(no trailing ``.0``), 0.5 prints as ``"0.5"``. Use :func:`format_bb` for
every BB rendering so the rule is enforced uniformly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Chip-per-BB convention. The CLI's `_build_postflop_config` and `_run_subgame_solve`
# both hardcode 100 chips per BB; we mirror that here so a single constant
# governs the conversion. Changing the engine's blind structure would require
# touching both places — but per locked decision the engine is fixed.
CHIPS_PER_BB: int = 100


# ---------------------------------------------------------------------------
# BB rendering
# ---------------------------------------------------------------------------


def chips_to_bb(chips: int) -> float:
    """Convert a chip count to a float BB amount.

    Pure arithmetic; no rounding. The rounding step lives in :func:`format_bb`
    so callers can manipulate the float before formatting if needed.
    """
    return chips / float(CHIPS_PER_BB)


def format_bb(chips: int) -> str:
    """Render ``chips`` as a BB string with at most 1 decimal place.

    Rules:

    * Integer BB amounts print without a decimal: 1000 chips -> ``"10"``.
    * Non-integer amounts print rounded to 1 decimal: 750 chips -> ``"7.5"``.
    * Trailing zeros are stripped: 800 chips -> ``"8"`` (not ``"8.0"``).
    * Negative chips render with the sign preserved (e.g. ``"-3.3"``); the
      tree walker doesn't surface negatives, but the helper handles them
      symmetrically for ``compute_mdf_threshold`` / EV displays.

    The rendering is locale-independent: we use Python's ``format`` with a
    fixed ``.1f`` spec, which ALWAYS uses ``.`` as the decimal separator
    regardless of ``LANG`` / ``LC_NUMERIC``. The CLI byte-identical-under-
    LANG=C invariant from the brief lands here.
    """
    bb = chips_to_bb(int(chips))
    # Round to 1 decimal then test for integer-ness.
    rounded = round(bb, 1)
    if rounded == int(rounded):
        return str(int(rounded))
    # Always use the C locale "%.1f" form (single dot, no comma).
    return f"{rounded:.1f}"


def format_pot_pct(amount: int, pot: int) -> str:
    """Render ``amount / pot`` as an integer percentage (e.g. ``"33%"``).

    For bet labels (where ``amount`` is the bet's chip delta and ``pot`` is
    the pot before the bet), this gives the user a quick "this is a 33% pot
    bet" annotation that lines up with the ``--bet-sizes`` parameterization.

    Returns ``"?%"`` when ``pot <= 0`` (shouldn't happen on postflop spots
    but the abstraction is defensive).
    """
    if pot <= 0:
        return "?%"
    pct = int(round(100.0 * amount / pot))
    return f"{pct}%"


# ---------------------------------------------------------------------------
# Header block ("SPOT CONFIG" preamble)
# ---------------------------------------------------------------------------


@dataclass
class SpotHeader:
    """Inputs for the ``SPOT CONFIG`` header block.

    All fields are pre-rendered strings except the integer pot/stack
    amounts (so the renderer can re-apply :func:`format_bb`).
    """

    effective_stack_chips: int
    starting_pot_chips: int
    board: str  # space-joined card glyphs, or "" pre-flop
    street: str | None  # "FLOP" / "TURN" / "RIVER" / "PREFLOP" or None to skip
    bet_menu_pcts: tuple[float, ...]  # bet-size fractions, e.g. (0.33, 0.75)
    raise_cap: int
    include_all_in: bool = True


def render_header(h: SpotHeader) -> str:
    """Render the ``SPOT CONFIG`` block as a multi-line string.

    Format (matches the brief verbatim):

        ===============================================================
        SPOT CONFIG
        ===============================================================
          Effective stacks:    100 BB
          Starting pot:        10 BB  (preflop dead money)
          Board:               As Kd 7h 3s 2c  (RIVER)
          Bet menu:            [33%, 75%] pot  +  all-in
          Raise cap:           2
        ===============================================================

    The bar uses ASCII ``=`` characters for byte-identical output under
    ``LANG=C`` (no Unicode box-drawing chars in the bar). Trailing newline
    included so callers can ``print(render_header(h), end="")``.
    """
    bar = "=" * 63
    lines: list[str] = []
    lines.append(bar)
    lines.append("SPOT CONFIG")
    lines.append(bar)
    lines.append(f"  Effective stacks:    {format_bb(h.effective_stack_chips)} BB")
    lines.append(
        f"  Starting pot:        {format_bb(h.starting_pot_chips)} BB  "
        f"(preflop dead money)"
    )
    if h.board:
        board_line = f"  Board:               {h.board}"
        if h.street:
            board_line += f"  ({h.street})"
        lines.append(board_line)
    else:
        if h.street:
            lines.append(f"  Street:              {h.street}")
    pct_tokens = [f"{int(round(p * 100))}%" for p in h.bet_menu_pcts]
    suffix = "  +  all-in" if h.include_all_in else ""
    lines.append(f"  Bet menu:            [{', '.join(pct_tokens)}] pot{suffix}")
    lines.append(f"  Raise cap:           {h.raise_cap}")
    lines.append(bar)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# --node syntax normalization (BB / %-pot / dot / raw chips → canonical chips)
# ---------------------------------------------------------------------------


# We accept any of:
#   "" (root)
#   raw chip:  b750, r3125, xb750, b330r990
#   BB form:   b7.5bb, b7bb, r31.25bb
#   %% form:   b75pct, b75%
#   verbose:   check, bet, raise, fold, call, allin, all-in
#   separators: ":", "/", and "." outside a numeric run (treated as token
#               boundaries). A "." between two digits is a decimal point.
_BOUNDARY_CHARS = ":/"


def _normalize_separators(s: str) -> str:
    """Strip token-boundary characters (``:``, ``/``).

    The canonical engine token format has NO separators (e.g. ``"xb750"``);
    BB-friendly forms use them for readability. We strip them out at the
    front of parsing so the tokenizer can ignore positions.

    NOTE: ``.`` is intentionally preserved here because it doubles as a
    decimal point inside a BB amount (``b7.5bb``). The per-token loop in
    :func:`parse_user_node` handles ``.`` contextually — as a token
    boundary when it follows ``x`` / ``c`` / ``f`` / ``A`` or a unit
    suffix, and as a decimal inside a numeric run.
    """
    return "".join(ch for ch in s if ch not in _BOUNDARY_CHARS)


@dataclass
class _Token:
    """A single normalized step parsed from a user --node string."""

    kind: str  # one of "x" "c" "f" "A" "b" "r"
    # For "b" / "r", exactly ONE of (chips, bb, pct) is non-None:
    chips: int | None = None
    bb: float | None = None
    pct: float | None = None  # 0.75 means "75% pot"


def parse_user_node(s: str) -> list[_Token]:
    """Tokenize a user-supplied ``--node`` string into intermediate steps.

    Supported notations (mix-and-match within one string):

    * Raw chip tokens (legacy):     ``xb750``, ``b750r3125``, ``r3125``
    * BB notation:                  ``b7.5bb``, ``r31.25bb``
    * % pot notation:               ``b75%``, ``b75pct``
    * Verbose action names:         ``check``, ``bet75%``, ``raise75pct``,
                                    ``fold``, ``call``, ``allin``, ``all-in``
    * Separators (ignored):         ``:``, ``.``, ``/`` (e.g. ``check.bet75pct``,
                                    ``x:b7.5bb``, ``check/bet/3.3bb``)

    Returns a list of :class:`_Token` with EXACTLY ONE of ``chips`` / ``bb``
    / ``pct`` populated on bet/raise tokens. Raises ``ValueError`` for
    malformed strings.

    Empty input string returns ``[]`` (root node).
    """
    if not s:
        return []
    norm = _normalize_separators(s.strip().lower())
    if not norm:
        return []

    # Some shells eat the ``%`` character; accept ``pct`` as a synonym.
    # Same for ``allin`` -> ``A`` shorthand.
    norm = norm.replace("all-in", "A").replace("allin", "A")
    norm = norm.replace("check", "x").replace("call", "c").replace("fold", "f")
    norm = norm.replace("raise", "r").replace("bet", "b")

    tokens: list[_Token] = []
    i = 0
    n = len(norm)
    while i < n:
        ch = norm[i]
        # Skip token-boundary dots (between tokens, not inside a number).
        if ch == ".":
            i += 1
            continue
        if ch in ("x", "c", "f", "A"):
            tokens.append(_Token(kind=ch))
            i += 1
            continue
        if ch in ("b", "r"):
            # Parse a numeric amount + optional unit suffix.
            i += 1
            j = i
            # Collect digits + a single decimal point.
            while j < n and (norm[j].isdigit() or norm[j] == "."):
                j += 1
            num_str = norm[i:j]
            if not num_str:
                raise ValueError(
                    f"--node {s!r}: token {ch!r} at position {i - 1} has no amount"
                )
            try:
                num = float(num_str)
            except ValueError as exc:
                raise ValueError(
                    f"--node {s!r}: cannot parse amount {num_str!r} after "
                    f"{ch!r}"
                ) from exc
            i = j
            # Unit suffix: "bb", "pct", "%", or none (= raw chips).
            unit = ""
            if i < n and norm[i] == "%":
                unit = "%"
                i += 1
            elif norm[i:i + 3] == "pct":
                unit = "%"
                i += 3
            elif norm[i:i + 2] == "bb":
                unit = "bb"
                i += 2
            tok = _Token(kind=ch)
            if unit == "bb":
                tok.bb = num
            elif unit == "%":
                tok.pct = num / 100.0
            else:
                # Raw chips. Must be an integer (the engine never produces
                # fractional chip amounts).
                if num != int(num):
                    raise ValueError(
                        f"--node {s!r}: raw chip amount {num!r} is not integer "
                        f"(use ``bb`` or ``%`` suffix for fractional values)"
                    )
                tok.chips = int(num)
            tokens.append(tok)
            continue
        # Unknown character — could be a stray separator that survived
        # normalization (shouldn't happen) or a typo.
        raise ValueError(
            f"--node {s!r}: unexpected character {ch!r} at position {i}"
        )
    return tokens


# ---------------------------------------------------------------------------
# Resolve user tokens against an engine state walk
# ---------------------------------------------------------------------------


def canonical_history_for_user_node(user_node: str, game, _action_ctx_at_history_fn) -> str:
    """Translate a user-supplied --node string into the engine's chip-token form.

    Walks the engine from the root, matching each user token against the
    legal actions at the current state and converting BB / %-pot tokens
    into chip amounts via the per-decision :class:`ActionContext`. Returns
    the engine's canonical history string (e.g. ``"xb750"``) suitable for
    direct lookup against :class:`TreeNode.history` keys.

    Empty user string returns ``""`` (root).

    Raises ``ValueError`` when the user-supplied tokens cannot be matched
    to any legal action at some step (e.g. ``b7.5bb`` when the engine's
    nearest legal bet is ``9 BB`` due to min-bet enforcement).
    """
    tokens = parse_user_node(user_node)
    if not tokens:
        return ""

    # Local imports to avoid a circular dep with cli_tree_walk at import
    # time (this module is loaded by cli.py at module-import; cli_tree_walk
    # is loaded lazily inside _render_new_mode).
    from poker_solver.action_abstraction import (
        ACTION_ALL_IN,
        ACTION_CALL,
        ACTION_CHECK,
        ACTION_FOLD,
        compute_bet_amount,
        compute_raise_to,
    )

    state = game.initial_state()
    while game.current_player(state) == -1 and not game.is_terminal(state):
        outcomes = game.chance_outcomes(state)
        if not outcomes:
            raise ValueError(f"--node {user_node!r}: empty chance outcomes at root")
        state = game.apply(state, outcomes[0][0])

    history_pieces: list[str] = []
    for idx, tok in enumerate(tokens):
        if game.is_terminal(state):
            raise ValueError(
                f"--node {user_node!r}: token #{idx + 1} cannot apply — game "
                f"already terminal"
            )
        legal = game.legal_actions(state)
        ctx = game._action_context(state)  # type: ignore[attr-defined]

        if tok.kind == "f":
            aid = ACTION_FOLD if ACTION_FOLD in legal else None
            if aid is None:
                raise ValueError(
                    f"--node {user_node!r}: fold not legal at step {idx + 1}"
                )
            history_pieces.append("f")
            state = game.apply(state, aid)
            continue
        if tok.kind == "x":
            aid = ACTION_CHECK if ACTION_CHECK in legal else None
            if aid is None:
                raise ValueError(
                    f"--node {user_node!r}: check not legal at step {idx + 1} "
                    f"(facing a bet?)"
                )
            history_pieces.append("x")
            state = game.apply(state, aid)
            continue
        if tok.kind == "c":
            aid = ACTION_CALL if ACTION_CALL in legal else None
            if aid is None:
                raise ValueError(
                    f"--node {user_node!r}: call not legal at step {idx + 1}"
                )
            history_pieces.append("c")
            state = game.apply(state, aid)
            continue
        if tok.kind == "A":
            aid = ACTION_ALL_IN if ACTION_ALL_IN in legal else None
            if aid is None:
                raise ValueError(
                    f"--node {user_node!r}: all-in not legal at step {idx + 1}"
                )
            history_pieces.append("A")
            state = game.apply(state, aid)
            continue
        # bet or raise: resolve amount in the unit the user supplied.
        target_chips: int | None = None
        if tok.chips is not None:
            target_chips = tok.chips
        elif tok.bb is not None:
            target_chips = int(round(tok.bb * CHIPS_PER_BB))
        elif tok.pct is not None:
            # Resolve via the same machinery the engine uses; the engine's
            # bet amounts respect min-bet + stack caps so we want the
            # _enumerate_legal_bets_ amount, not the raw pot * pct.
            # Iterate the legal bet/raise action IDs, compute the chip
            # amount for each, and pick the one whose pot-fraction is
            # closest to the user's request. This handles the case where
            # the user types "b75%" but the menu only contains 33%/100%.
            target_chips = _chip_amount_for_pct(
                tok.kind, tok.pct, legal, ctx,
            )
        if target_chips is None:
            raise ValueError(
                f"--node {user_node!r}: token #{idx + 1} ({tok.kind!r}) has no "
                f"amount"
            )

        if tok.kind == "b":
            match_aid = None
            for aid in legal:
                if 3 <= aid <= 7 and compute_bet_amount(aid, ctx) == target_chips:
                    match_aid = aid
                    break
            if match_aid is None and ACTION_ALL_IN in legal:
                # Allow b<stack> to map to all-in (chip equality).
                if compute_bet_amount(ACTION_ALL_IN, ctx) == target_chips:
                    match_aid = ACTION_ALL_IN
            if match_aid is None:
                # Try a tolerant match: nearest legal bet within 1 chip.
                # The engine sometimes rounds % * pot differently than the
                # user's BB approximation; allow a 1-chip slop on equality.
                nearest = _nearest_legal_bet(target_chips, legal, ctx)
                if nearest is not None:
                    match_aid, match_amt = nearest
                    if abs(match_amt - target_chips) > 1:
                        raise ValueError(
                            f"--node {user_node!r}: bet token #{idx + 1} "
                            f"requests {target_chips} chips ({format_bb(target_chips)} BB); "
                            f"nearest legal bet is {match_amt} chips "
                            f"({format_bb(match_amt)} BB)."
                        )
                else:
                    raise ValueError(
                        f"--node {user_node!r}: bet token #{idx + 1} requests "
                        f"{target_chips} chips ({format_bb(target_chips)} BB) but no "
                        f"matching legal bet."
                    )
            if 3 <= match_aid <= 7:
                amt = compute_bet_amount(match_aid, ctx)
                history_pieces.append(f"b{amt}")
            else:
                history_pieces.append("A")
            state = game.apply(state, match_aid)
            continue
        if tok.kind == "r":
            match_aid = None
            for aid in legal:
                if 8 <= aid <= 12 and compute_raise_to(aid, ctx) == target_chips:
                    match_aid = aid
                    break
            if match_aid is None and ACTION_ALL_IN in legal:
                if compute_raise_to(ACTION_ALL_IN, ctx) == target_chips:
                    match_aid = ACTION_ALL_IN
            if match_aid is None:
                nearest = _nearest_legal_raise(target_chips, legal, ctx)
                if nearest is not None:
                    match_aid, match_amt = nearest
                    if abs(match_amt - target_chips) > 1:
                        raise ValueError(
                            f"--node {user_node!r}: raise token #{idx + 1} "
                            f"requests raise-to {target_chips} chips "
                            f"({format_bb(target_chips)} BB); nearest legal raise-to is "
                            f"{match_amt} chips ({format_bb(match_amt)} BB)."
                        )
                else:
                    raise ValueError(
                        f"--node {user_node!r}: raise token #{idx + 1} requests "
                        f"raise-to {target_chips} chips ({format_bb(target_chips)} BB) "
                        f"but no matching legal raise."
                    )
            if 8 <= match_aid <= 12:
                amt = compute_raise_to(match_aid, ctx)
                history_pieces.append(f"r{amt}")
            else:
                history_pieces.append("A")
            state = game.apply(state, match_aid)
            continue
        # Unreachable (parse_user_node enforces kind ∈ {"x","c","f","A","b","r"}).
        raise ValueError(
            f"--node {user_node!r}: unknown token kind {tok.kind!r}"
        )

    return "".join(history_pieces)


def _chip_amount_for_pct(
    kind: str, pct: float, legal, ctx,
) -> int | None:
    """Pick the legal bet/raise action whose pot-fraction matches ``pct``.

    Iterates the legal action IDs and computes each one's chip amount via
    ``compute_bet_amount`` / ``compute_raise_to``. Returns the chip amount
    whose pot-fraction is closest to the user's requested ``pct`` (so
    ``b75%`` resolves to the menu's 75% bet even when the actual chips
    differ from ``int(pot * 0.75)`` due to rounding).
    """
    from poker_solver.action_abstraction import (
        compute_bet_amount,
        compute_raise_to,
    )

    if kind == "b":
        candidates: list[tuple[int, float]] = []
        for aid in legal:
            if 3 <= aid <= 7:
                idx = aid - 3
                fraction = ctx.bet_size_fractions[idx]
                candidates.append((compute_bet_amount(aid, ctx), fraction))
        if not candidates:
            return None
        best = min(candidates, key=lambda c: abs(c[1] - pct))
        return best[0]
    if kind == "r":
        candidates_r: list[tuple[int, float]] = []
        for aid in legal:
            if 8 <= aid <= 12:
                idx = aid - 8
                fraction = ctx.bet_size_fractions[idx]
                candidates_r.append((compute_raise_to(aid, ctx), fraction))
        if not candidates_r:
            return None
        best_r = min(candidates_r, key=lambda c: abs(c[1] - pct))
        return best_r[0]
    return None


def _nearest_legal_bet(target_chips: int, legal, ctx) -> tuple[int, int] | None:
    """Find the legal bet (or all-in) whose chip amount is nearest to target.

    Returns ``(action_id, chips)`` or ``None`` when no bets are legal.
    """
    from poker_solver.action_abstraction import (
        ACTION_ALL_IN,
        compute_bet_amount,
    )

    best: tuple[int, int] | None = None
    for aid in legal:
        if 3 <= aid <= 7:
            amt = compute_bet_amount(aid, ctx)
            if best is None or abs(amt - target_chips) < abs(best[1] - target_chips):
                best = (aid, amt)
    if ACTION_ALL_IN in legal:
        amt = compute_bet_amount(ACTION_ALL_IN, ctx)
        if best is None or abs(amt - target_chips) < abs(best[1] - target_chips):
            best = (ACTION_ALL_IN, amt)
    return best


def _nearest_legal_raise(target_chips: int, legal, ctx) -> tuple[int, int] | None:
    """Find the legal raise (or all-in) whose raise-to is nearest to target."""
    from poker_solver.action_abstraction import (
        ACTION_ALL_IN,
        compute_raise_to,
    )

    best: tuple[int, int] | None = None
    for aid in legal:
        if 8 <= aid <= 12:
            amt = compute_raise_to(aid, ctx)
            if best is None or abs(amt - target_chips) < abs(best[1] - target_chips):
                best = (aid, amt)
    if ACTION_ALL_IN in legal:
        amt = compute_raise_to(ACTION_ALL_IN, ctx)
        if best is None or abs(amt - target_chips) < abs(best[1] - target_chips):
            best = (ACTION_ALL_IN, amt)
    return best


# ---------------------------------------------------------------------------
# Engine-history → user-facing canonical --node id
# ---------------------------------------------------------------------------


def canonical_node_id_for_history(history: str, game) -> str:
    """Translate an engine chip-token history into a BB-native ``--node`` id.

    Walks the engine state to compute each step's % pot at decision time,
    then emits a token using the % suffix (so the resulting string is
    copy-paste-friendly into ``--node`` regardless of the absolute chip
    amount). Single-decision tokens (check/call/fold/all-in) become their
    verbose form; bet/raise tokens become ``b<pct>pct`` / ``r<pct>pct``
    where ``<pct>`` is the engine's index into ``bet_size_fractions``.

    Examples:

        ""        → ""                (root)
        "x"       → "check"
        "xb330"   → "check.bet33pct"
        "b990r3300" → "bet33pct.raise75pct"
        "A"       → "allin"

    Returns the original engine history if any token can't be mapped
    (defensive — caller never sees an exception).
    """
    if not history:
        return ""
    try:
        from poker_solver.action_abstraction import (
            ACTION_ALL_IN,
            ACTION_CALL,
            ACTION_CHECK,
            ACTION_FOLD,
            compute_bet_amount,
            compute_raise_to,
        )
        from poker_solver.cli_tree_walk import _split_history_tokens, parse_token

        state = game.initial_state()
        while game.current_player(state) == -1 and not game.is_terminal(state):
            outcomes = game.chance_outcomes(state)
            if not outcomes:
                return history
            state = game.apply(state, outcomes[0][0])

        pieces: list[str] = []
        for tok in _split_history_tokens(history):
            if game.is_terminal(state):
                return history
            kind, amt = parse_token(tok)
            legal = game.legal_actions(state)
            ctx = game._action_context(state)  # type: ignore[attr-defined]
            if kind == "x":
                pieces.append("check")
                state = game.apply(state, ACTION_CHECK)
                continue
            if kind == "c":
                pieces.append("call")
                state = game.apply(state, ACTION_CALL)
                continue
            if kind == "f":
                pieces.append("fold")
                state = game.apply(state, ACTION_FOLD)
                continue
            if kind == "A":
                pieces.append("allin")
                state = game.apply(state, ACTION_ALL_IN)
                continue
            if kind == "b":
                match_aid = None
                for aid in legal:
                    if 3 <= aid <= 7 and compute_bet_amount(aid, ctx) == amt:
                        match_aid = aid
                        break
                if match_aid is None:
                    if (
                        ACTION_ALL_IN in legal
                        and compute_bet_amount(ACTION_ALL_IN, ctx) == amt
                    ):
                        pieces.append("allin")
                        state = game.apply(state, ACTION_ALL_IN)
                        continue
                    return history
                idx = match_aid - 3
                pct = int(round(ctx.bet_size_fractions[idx] * 100))
                pieces.append(f"bet{pct}pct")
                state = game.apply(state, match_aid)
                continue
            if kind == "r":
                match_aid = None
                for aid in legal:
                    if 8 <= aid <= 12 and compute_raise_to(aid, ctx) == amt:
                        match_aid = aid
                        break
                if match_aid is None:
                    if (
                        ACTION_ALL_IN in legal
                        and compute_raise_to(ACTION_ALL_IN, ctx) == amt
                    ):
                        pieces.append("allin")
                        state = game.apply(state, ACTION_ALL_IN)
                        continue
                    return history
                idx = match_aid - 8
                pct = int(round(ctx.bet_size_fractions[idx] * 100))
                pieces.append(f"raise{pct}pct")
                state = game.apply(state, match_aid)
                continue
        return ".".join(pieces)
    except Exception:
        # Defensive: any unexpected engine state -> return engine history
        # verbatim. The CLI display still works; user just sees the
        # legacy chip-token form for that one node.
        return history


# ---------------------------------------------------------------------------
# Deprecation-warning helper (used by --pot-bb / --stack-bb alias path)
# ---------------------------------------------------------------------------


_DEPRECATION_WARNED: set[str] = set()


def emit_deprecation_warning_once(flag: str, replacement: str) -> None:
    """Log a one-shot deprecation warning for a renamed CLI flag.

    The warning is written to stderr (so it doesn't pollute parseable stdout
    JSON / CSV) and is suppressed after the first invocation per process —
    matches the brief's "deprecation warning logged once on use" guidance.
    """
    import sys

    if flag in _DEPRECATION_WARNED:
        return
    _DEPRECATION_WARNED.add(flag)
    print(
        f"warning: {flag} is deprecated; use {replacement} instead "
        f"(deprecated alias will be removed in a future release).",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Public re-exports
# ---------------------------------------------------------------------------

__all__ = [
    "CHIPS_PER_BB",
    "SpotHeader",
    "canonical_history_for_user_node",
    "canonical_node_id_for_history",
    "chips_to_bb",
    "emit_deprecation_warning_once",
    "format_bb",
    "format_pot_pct",
    "parse_user_node",
    "render_header",
]
