"""Shared UI state, threading scaffold, and persistence (PR 10a).

This module is the trunk on which the rest of the UI hangs. It exports:

- Dataclasses: ``RangeWithFreqs`` (wraps ``poker_solver.Range`` with per-combo
  frequencies), ``Spot`` (board + ranges + stacks + tree config), ``SolveSession``
  (active solve metadata), ``UIPrefs`` (persisted user prefs), ``AppState``
  (aggregator passed to view ``render`` functions).
- ``SolveRunner``: the worker-thread orchestrator. Owns ONE background
  ``threading.Thread`` + ``_pause_event`` + ``_stop_event``. Worker invokes
  ``_solve_postflop_impl`` (= ``mock_solve`` in PR 10a, real ``solve_hunl_postflop``
  in PR 10b — one-line import swap per ``pr10b_spec.md``). UI thread NEVER
  calls worker code directly; progress flows via a ``ui.timer(0.5, ...)``
  reading ``SolveRunner`` attributes.
- Module-level singleton accessors: ``get_state()`` lazily loads from
  ``~/.poker_solver_ui/state.json``; ``save_state()`` debounces and atomically
  writes to that path.
- Hand-class enumeration helpers consumed by Agent B's matrix renderer:
  ``enumerate_hand_classes()`` (169 entries, row-major top-left=AA),
  ``enumerate_combos(label)``, ``hand_class_label(r1, r2, suited)``,
  ``classify_combo(c0, c1)``.

Threading model (load-bearing surface per ``implementation_challenges.md``):

- ``SolveRunner.start()`` spawns a daemon thread running ``_worker``.
- ``_worker`` calls ``_solve_postflop_impl(config, None, iterations, ...)``
  on a helper thread; the mock owns the per-snapshot loop and the
  ``_CANCEL_FLAG`` check. Per
  ``docs/pr10_prep/mock_signature_drift.md`` Option A, there is NO
  ``on_progress`` callback (the real ``solve_hunl_postflop`` has none);
  instead mock_solve publishes per-snapshot progress to the module-level
  ``_LATEST_PROGRESS`` buffer in ``ui.mock_solver``.
- The worker thread polls ``read_latest_progress()`` at ~50 ms cadence
  while the helper runs and updates ``self.iteration`` +
  ``self.expl_history`` + ``self.partial_report`` under ``self._lock``.
  The poll loop also (a) sets ``_CANCEL_FLAG`` if ``self._stop_event``
  is set so the next mock snapshot exits the loop, and (b) blocks while
  ``self._pause_event`` is set.
- Worker NEVER calls NiceGUI APIs. UI thread reads ``SolveRunner`` state
  via the 500 ms ``ui.timer`` (registered in ``ui/app.py``) which calls
  ``run_panel.refresh_progress(state)``.
- ``stop()`` sets BOTH ``self._stop_event`` AND ``ui.mock_solver._CANCEL_FLAG``
  (per ``pr10a_spec.md`` §7.5). Stop halts within one snapshot interval.

Persistence (``pr10a_spec.md`` §9.2):

- State lives at ``~/.poker_solver_ui/state.json``.
- Atomic write: write to ``state.json.tmp``, ``fsync``, ``os.rename`` to
  ``state.json``. Avoids corruption on crash mid-write.
- Debounced via a 500 ms in-memory window: ``save_state()`` marks dirty,
  the deferred flush coalesces multiple edits into one disk write.
- On load failure (corrupt JSON or version mismatch): warn, back up to
  ``state.json.bak``, start from defaults. Never crash.
- ``recent_spots`` capped at 10 (FIFO eviction). ``library_entries`` empty
  in PR 10a.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from poker_solver.card import RANKS, Card
from poker_solver.hunl import HUNLConfig, HUNLPoker, Street
from poker_solver.range import Combo, Range, parse_range
from poker_solver.solver import SolveResult

if TYPE_CHECKING:
    from poker_solver.profiler.memory import MemoryReport

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Hand-class enumeration helpers
# --------------------------------------------------------------------------- #
#
# Canonical 13x13 grid convention per ``pr10a_spec.md`` §3.3:
#
#         A   K   Q   J   T   9   8   7   6   5   4   3   2
#     A  AA  AKs AQs AJs ATs A9s A8s A7s A6s A5s A4s A3s A2s
#     K  AKo KK  KQs KJs KTs K9s K8s K7s K6s K5s K4s K3s K2s
#     ...
#     2  A2o K2o Q2o J2o T2o 92o 82o 72o 62o 52o 42o 32o 22
#
# Internal coordinates use ``row``/``col`` in [0, 12], where row 0 is the
# A-row (top of grid) and col 0 is the A-column (left of grid). The rank
# at row/col ``i`` is ``14 - i`` (i.e., row 0 = Ace = rank 14, row 12 = 2 =
# rank 2). On-diagonal cells (row == col) are pairs; cells with col > row
# (visually to the right of the diagonal) are suited; col < row are offsuit.
#
# Agent B's display matrix and Agent C's smoke tests depend on this exact
# row/col convention. DO NOT change without coordinating across all three.

_RANK_FROM_GRID_INDEX: tuple[int, ...] = tuple(14 - i for i in range(13))


def hand_class_label(rank1: int, rank2: int, suited: bool) -> str:
    """Return the canonical hand-class label for two ranks + suited flag.

    Args:
        rank1: rank value in [2, 14] (Ace == 14).
        rank2: rank value in [2, 14].
        suited: ignored when ``rank1 == rank2`` (pairs are unsuited tokens).

    Returns:
        ``"AA"``, ``"AKs"``, ``"72o"``, etc. Higher rank always first.
    """
    if not (2 <= rank1 <= 14 and 2 <= rank2 <= 14):
        raise ValueError(f"ranks out of [2, 14]: {rank1}, {rank2}")
    hi, lo = max(rank1, rank2), min(rank1, rank2)
    hi_char = RANKS[hi - 2]
    lo_char = RANKS[lo - 2]
    if hi == lo:
        return f"{hi_char}{lo_char}"
    return f"{hi_char}{lo_char}{'s' if suited else 'o'}"


def enumerate_hand_classes() -> list[tuple[int, int, str]]:
    """Yield (row, col, label) for the 13x13 grid in row-major order.

    Row 0 is the A-row at the top; col 0 is the A-column at the left.
    Diagonal (row == col) is pairs; col > row is suited; col < row is offsuit.

    Returns 169 entries; ``[0] == (0, 0, "AA")``, ``[1] == (0, 1, "AKs")``,
    ``[12] == (0, 12, "A2s")``, ``[13] == (1, 0, "AKo")``, ...,
    ``[168] == (12, 12, "22")``.
    """
    out: list[tuple[int, int, str]] = []
    for row in range(13):
        for col in range(13):
            r_row = _RANK_FROM_GRID_INDEX[row]
            r_col = _RANK_FROM_GRID_INDEX[col]
            if row == col:
                out.append((row, col, hand_class_label(r_row, r_col, suited=False)))
            elif col > row:
                # suited: above/right of diagonal
                out.append((row, col, hand_class_label(r_row, r_col, suited=True)))
            else:
                # offsuit: below/left of diagonal
                out.append((row, col, hand_class_label(r_row, r_col, suited=False)))
    return out


def enumerate_combos(hand_class: str) -> list[Combo]:
    """Return the concrete (Card, Card) combos for a hand-class label.

    - Pair ``"XX"``: 6 combos (C(4, 2)), sorted by (suit_hi, suit_lo).
    - Suited ``"XYs"``: 4 combos (one per suit), sorted by suit.
    - Offsuit ``"XYo"``: 12 combos (4 * 3), sorted by (hi_suit, lo_suit).

    Each combo's cards are ordered (higher rank first); the inner tuple
    preserves that ordering. ``classify_combo`` is the inverse.
    """
    if not 2 <= len(hand_class) <= 3:
        raise ValueError(f"invalid hand class label: {hand_class!r}")
    rank_chars = hand_class[:2]
    r1_char, r2_char = rank_chars[0], rank_chars[1]
    if r1_char not in RANKS or r2_char not in RANKS:
        raise ValueError(f"invalid ranks in {hand_class!r}")
    r1 = RANKS.index(r1_char) + 2
    r2 = RANKS.index(r2_char) + 2
    hi, lo = max(r1, r2), min(r1, r2)
    if hi == lo:
        # pair: no suit suffix
        if len(hand_class) != 2:
            raise ValueError(
                f"pair token must not carry a suit indicator: {hand_class!r}"
            )
        out: list[Combo] = []
        for s1 in range(4):
            for s2 in range(s1 + 1, 4):
                out.append((Card(hi, s1), Card(hi, s2)))
        return out
    if len(hand_class) != 3:
        raise ValueError(f"non-pair token must carry s/o indicator: {hand_class!r}")
    suit_indicator = hand_class[2]
    if suit_indicator == "s":
        return [(Card(hi, s), Card(lo, s)) for s in range(4)]
    if suit_indicator == "o":
        return [
            (Card(hi, s1), Card(lo, s2))
            for s1 in range(4)
            for s2 in range(4)
            if s1 != s2
        ]
    raise ValueError(f"suit indicator must be 's' or 'o': {hand_class!r}")


def classify_combo(card1: Card, card2: Card) -> str:
    """Return the hand-class label of two cards.

    Inverse of ``enumerate_combos``. Used by Agent C's
    ``test_combo_to_cell_mapping_no_off_by_one`` property test.
    """
    if card1 == card2:
        raise ValueError(f"combo has duplicate card: {card1}")
    suited = card1.suit == card2.suit
    return hand_class_label(card1.rank, card2.rank, suited)


# --------------------------------------------------------------------------- #
# Range helpers
# --------------------------------------------------------------------------- #


def _full_range_combos() -> list[Combo]:
    """All 1326 unordered combos as canonical (Card, Card) tuples.

    Cards within each combo are ordered (higher rank first; ties broken by
    suit ascending) to match ``Range.add``'s sort key.
    """
    out: list[Combo] = []
    for r1 in range(2, 15):
        for s1 in range(4):
            for r2 in range(2, 15):
                for s2 in range(4):
                    if (r1, s1) == (r2, s2):
                        continue
                    if (r1, s1) < (r2, s2):
                        continue
                    c_hi = Card(r1, s1)
                    c_lo = Card(r2, s2)
                    # Range.add sorts by (-rank, suit). Match that ordering.
                    if c_hi.rank < c_lo.rank or (
                        c_hi.rank == c_lo.rank and c_hi.suit > c_lo.suit
                    ):
                        c_hi, c_lo = c_lo, c_hi
                    out.append((c_hi, c_lo))
    return out


def _full_range() -> Range:
    """Build a Range containing all 1326 combos (poker_solver.Range has no
    ``.full()`` factory in PR 1; rolled here)."""
    r = Range()
    for combo in _full_range_combos():
        r.add(combo)
    return r


# --------------------------------------------------------------------------- #
# Dataclasses
# --------------------------------------------------------------------------- #


@dataclass
class RangeWithFreqs:
    """A ``poker_solver.Range`` with an added per-combo frequency layer.

    PR 10 needs per-combo float frequencies in ``[0.0, 1.0]``; ``Range`` is
    membership-only. We do NOT modify ``range.py`` — instead this class wraps
    a ``Range`` and adds a ``frequencies`` dict from (Card, Card) combos to
    a float in ``[0.0, 1.0]``.

    Semantics:

    - ``frequency_of(combo)`` returns ``frequencies[combo]`` if present,
      else ``1.0`` if combo in ``base_range``, else ``0.0``.
    - The range-INPUT matrix in ``ui/views/spot_input.py`` mutates
      ``frequencies[combo]`` when a cell is clicked or shift-clicked.
    - Agent B's strategy DISPLAY matrix reads
      ``state.current_spot.ranges[player].frequency_of(combo)`` for the
      per-cell aggregate (e.g., to size a "% of range" label).
    """

    base_range: Range = field(default_factory=Range)
    frequencies: dict[Combo, float] = field(default_factory=dict)

    def frequency_of(self, combo: Combo) -> float:
        """Return the frequency of ``combo``.

        Default 1.0 if combo is in ``base_range`` and absent from
        ``frequencies``; 0.0 otherwise.
        """
        if combo in self.frequencies:
            return self.frequencies[combo]
        if combo in self.base_range._combo_set:
            return 1.0
        return 0.0

    def set_frequency(self, combo: Combo, freq: float) -> None:
        """Set ``frequencies[combo] = freq`` (clamped to ``[0.0, 1.0]``).

        Adds ``combo`` to ``base_range`` if not already present.
        """
        clamped = max(0.0, min(1.0, freq))
        self.frequencies[combo] = clamped
        if combo not in self.base_range._combo_set:
            self.base_range.add(combo)

    @classmethod
    def from_string(cls, range_str: str) -> RangeWithFreqs:
        """Parse ``range_str`` via ``parse_range``; every combo at 1.0."""
        base = parse_range(range_str)
        freqs: dict[Combo, float] = {combo: 1.0 for combo in base.combos}
        return cls(base_range=base, frequencies=freqs)

    @classmethod
    def full(cls) -> RangeWithFreqs:
        """Construct a ``RangeWithFreqs`` containing all 1326 combos at 1.0."""
        base = _full_range()
        freqs: dict[Combo, float] = {combo: 1.0 for combo in base.combos}
        return cls(base_range=base, frequencies=freqs)

    @classmethod
    def empty(cls) -> RangeWithFreqs:
        """Construct an empty ``RangeWithFreqs``."""
        return cls(base_range=Range(), frequencies={})

    def to_string(self) -> str:
        """Render back to a comma-separated combo list.

        Lossy: combos with frequency < 1.0 lose their fractional weight.
        Round-trips ``RangeWithFreqs.from_string(rw.to_string())`` only for
        unit-weight ranges.
        """
        tokens: list[str] = []
        for combo in self.base_range.combos:
            if self.frequency_of(combo) <= 0.0:
                continue
            c0, c1 = combo
            tokens.append(f"{c0}{c1}")
        return ", ".join(tokens)


@dataclass
class Spot:
    """The poker spot being solved.

    Defines an ``HUNLConfig`` + two ranges + starting street + board state.
    The default constructor makes a 100 BB postflop spot on K72r (the
    ``flop_k72r_100bb`` mockup default per ``pr10a_spec.md`` §4.1) but with
    full ranges — the user immediately mutates.
    """

    board: list[Card] = field(default_factory=list)
    ranges: tuple[RangeWithFreqs, RangeWithFreqs] = field(
        default_factory=lambda: (RangeWithFreqs.full(), RangeWithFreqs.full())
    )
    stacks_bb: tuple[int, int] = (100, 100)
    sb_acts_first: bool = True  # P0 = SB = button per HUNL convention
    sb_blind: float = 0.5  # in BB
    bb_blind: float = 1.0
    ante: float = 0.0
    bet_sizes: tuple[float, ...] = (0.33, 0.75, 1.0, 1.5, 2.0)
    include_all_in: bool = True
    preflop_raise_cap: int = 4
    postflop_raise_cap: int = 3
    # Which bet sizes are checked (Q4 LOCKED: 33 / 75 / 100 / all-in default).
    # Stored explicitly because user may toggle 150% / 200% on.
    bet_sizes_checked: tuple[float, ...] = (0.33, 0.75, 1.0)

    @property
    def starting_street(self) -> Street:
        """Derive from ``len(board)``.

        - 0 cards -> ``Street.PREFLOP``
        - 3 -> ``Street.FLOP``
        - 4 -> ``Street.TURN``
        - 5 -> ``Street.RIVER``

        Raises ``ValueError`` on 1 or 2 cards (invalid intermediate states).
        """
        n = len(self.board)
        if n == 0:
            return Street.PREFLOP
        if n == 3:
            return Street.FLOP
        if n == 4:
            return Street.TURN
        if n == 5:
            return Street.RIVER
        raise ValueError(f"invalid board length {n}: must be 0, 3, 4, or 5 cards")

    def to_hunl_config(self) -> HUNLConfig:
        """Build a ``HUNLConfig`` from this spot's fields.

        ``abstraction=None`` always in PR 10 (we visualize equilibrium
        strategies on the lossless engine; abstraction-aware visualization
        is a PR 11 concern).
        """
        bb_cents = 100  # canonical 1 BB == 100 cents
        starting_stack_cents = self.stacks_bb[0] * bb_cents
        # For asymmetric stacks pick the larger (HUNLConfig has a single
        # ``starting_stack`` field; non-symmetric will need PR 11 work).
        if self.stacks_bb[0] != self.stacks_bb[1]:
            logger.warning(
                "Asymmetric stacks (%s) not fully supported; using P0 = %d BB",
                self.stacks_bb,
                self.stacks_bb[0],
            )
        sb_cents = int(self.sb_blind * bb_cents)
        bb_blind_cents = int(self.bb_blind * bb_cents)
        ante_cents = int(self.ante * bb_cents)
        starting_street = self.starting_street
        initial_board = tuple(self.board)
        if starting_street == Street.PREFLOP:
            initial_pot = 0
            initial_contributions: tuple[int, int] = (0, 0)
        else:
            # Subgame: contributions are dead-money (the UI doesn't model
            # the preflop tree). Use (0, 0) -> dead-money pot semantics.
            initial_pot = 0
            initial_contributions = (0, 0)
        return HUNLConfig(
            starting_stack=starting_stack_cents,
            small_blind=sb_cents,
            big_blind=bb_blind_cents,
            ante=ante_cents,
            starting_street=starting_street,
            initial_board=initial_board,
            initial_pot=initial_pot,
            initial_contributions=initial_contributions,
            preflop_raise_cap=self.preflop_raise_cap,
            postflop_raise_cap=self.postflop_raise_cap,
            bet_size_fractions=tuple(self.bet_sizes_checked),
            include_all_in=self.include_all_in,
            abstraction=None,
        )


@dataclass
class SolveSession:
    """A configuration + worker reference + result snapshot for one solve."""

    spot: Spot
    iterations: int
    log_every: int
    backend: str  # "python" or "rust"
    started_at: float  # ``time.time()``
    runner: SolveRunner


@dataclass
class UIPrefs:
    """Persisted user preferences."""

    dark_mode: str = "auto"  # "auto" | "light" | "dark"
    panel_widths: dict[str, int] = field(
        default_factory=lambda: {"left": 320, "bottom": 240}
    )
    matrix_show_frequencies: bool = True
    tree_reach_filter: float = 0.01  # Q6 LOCKED per ``pr10a_spec.md`` §0.1
    # Q7 banner can be dismissed AFTER first solve; remember dismissal.
    mock_banner_dismissed: bool = False
    # Onboarding gate (Risk 6: state.json absence is one signal; this flag
    # is the persistent one to prevent re-trigger when user clears history).
    onboarding_completed: bool = False
    # Chart axis preference (log default per spec §13 decision 8).
    chart_log_scale: bool = True


# --------------------------------------------------------------------------- #
# SolveRunner — the worker-thread orchestrator
# --------------------------------------------------------------------------- #


class SolveRunner:
    """Owns one background worker thread + cancellation flags + progress snapshot.

    Lifecycle (per ``pr10a_spec.md`` §6.1):

        idle -> running -> (paused -> running)* -> done | stopped | error

    Thread safety:
        Every cross-thread read goes through ``self._lock`` OR reads a single
        atomic field (int / str / float). ``self.expl_history`` is
        append-only from the worker; the UI thread reads its current length
        and slices ``[last_seen_len:]`` — do NOT mutate from the UI thread.
    """

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._pause_event: threading.Event = threading.Event()
        self._stop_event: threading.Event = threading.Event()
        self._lock: threading.Lock = threading.Lock()
        self.result: SolveResult | None = None
        self.iteration: int = 0
        self.expl_history: list[tuple[int, float]] = []  # (iter, expl_mBB_per_pot)
        self.status: str = "idle"  # idle | running | paused | done | stopped | error
        self.error: BaseException | None = None
        self.started_at: float = 0.0
        self.partial_report: MemoryReport | None = None

    def start(
        self,
        game: HUNLPoker,
        iterations: int,
        *,
        log_every: int,
        dcfr_kwargs: dict[str, Any] | None = None,
        backend: str = "python",
        memory_budget_gb: float = 14.0,
        target_exploitability: float | None = None,
        seed: int | None = None,
        # Test-injection hook: forwarded to ``mock_solve`` for failure-mode
        # exercise. Agent C's smoke tests pass these; production users
        # never see them.
        mock_latency_ms: int | None = None,
        mock_failure_mode: str | None = None,
    ) -> None:
        """Spawn the worker thread.

        Raises ``RuntimeError`` if a previous solve is still alive (call
        ``stop()`` + ``join()`` first).
        """
        if self.is_alive():
            raise RuntimeError(
                "SolveRunner.start() called while a solve is in flight; "
                "call stop() and wait until is_alive() is False first."
            )
        # Reset state for the new run.
        self._pause_event.clear()
        self._stop_event.clear()
        with self._lock:
            self.result = None
            self.iteration = 0
            self.expl_history = []
            self.status = "running"
            self.error = None
            self.started_at = time.time()
            self.partial_report = None
        config = game.config
        self._thread = threading.Thread(
            target=self._worker,
            kwargs={
                "config": config,
                "iterations": iterations,
                "log_every": log_every,
                "dcfr_kwargs": dcfr_kwargs,
                "backend": backend,
                "memory_budget_gb": memory_budget_gb,
                "target_exploitability": target_exploitability,
                "seed": seed,
                "mock_latency_ms": mock_latency_ms,
                "mock_failure_mode": mock_failure_mode,
            },
            daemon=True,
            name="poker-solver-ui-worker",
        )
        self._thread.start()

    def pause(self) -> None:
        """Set the pause flag.

        Per ``pr10a_spec.md`` §6.1 / §7.5 caveat: ``mock_solve`` is a single
        call, so "pause" means the worker thread sleeps between snapshots.
        The mock checks ``_CANCEL_FLAG`` once per snapshot; for pause we
        toggle ``self._pause_event``. The user sees "pausing..." until the
        next snapshot lands; then ``status == 'paused'``.
        """
        self._pause_event.set()
        with self._lock:
            if self.status == "running":
                self.status = "paused"

    def resume(self) -> None:
        """Clear the pause flag."""
        self._pause_event.clear()
        with self._lock:
            if self.status == "paused":
                self.status = "running"

    def stop(self) -> None:
        """Set the stop flag (also sets the mock-side ``_CANCEL_FLAG``).

        Worker exits its loop within ONE snapshot. Idempotent on idle.
        """
        self._stop_event.set()
        # Propagate to mock_solver's module-level flag so the per-snapshot
        # check inside ``mock_solve`` exits its loop. Import lazily because
        # ``ui.mock_solver`` may not exist during early bootstrap (Agent C
        # owns that file).
        try:
            from ui.mock_solver import _CANCEL_FLAG

            _CANCEL_FLAG.set()
        except (ImportError, ModuleNotFoundError):
            # PR 10a-pre: mock_solver not yet wired in. The status-only
            # path below still works for the "idle" idempotency case.
            pass

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def join(self, timeout: float | None = None) -> None:
        """Block until the worker thread exits (or ``timeout`` seconds elapse)."""
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _worker(
        self,
        *,
        config: HUNLConfig,
        iterations: int,
        log_every: int,
        dcfr_kwargs: dict[str, Any] | None,
        backend: str,
        memory_budget_gb: float,
        target_exploitability: float | None,
        seed: int | None,
        mock_latency_ms: int | None,
        mock_failure_mode: str | None,
    ) -> None:
        """The worker-thread body. Runs on a daemon ``threading.Thread``.

        NEVER calls NiceGUI APIs. Communicates with the UI via
        ``self.iteration``, ``self.expl_history``, ``self.status``,
        ``self.result``, ``self.error``, ``self.partial_report`` — all
        guarded by ``self._lock``.

        Imports ``_solve_postflop_impl`` from ``ui.mock_solver`` here (not at
        module load) so that early bootstrap (e.g. ``from ui.state import
        SolveRunner`` in unit tests) doesn't pull in NiceGUI transitively.
        The PR 10b swap rewrites this ONE import line to point at the real
        solver.
        """
        # ----- IMPORT SWAP POINT for PR 10b (single line) -----
        # Plus the module-level _CANCEL_FLAG + read_latest_progress helpers
        # (Option A from ``docs/pr10_prep/mock_signature_drift.md``: the real
        # ``solve_hunl_postflop`` has no ``on_progress`` callback, so we
        # decouple via a module-level progress buffer the worker polls).
        try:
            # fmt: off
            from ui.mock_solver import _CANCEL_FLAG, mock_solve as _solve_postflop_impl  # noqa: E501, I001
            from ui.mock_solver import read_latest_progress, reset_progress_buffer
            # fmt: on
        except (ImportError, ModuleNotFoundError) as exc:
            with self._lock:
                self.status = "error"
                self.error = exc
            return

        _CANCEL_FLAG.clear()
        reset_progress_buffer()

        # Run mock_solve on a helper thread; this worker thread polls the
        # module-level progress buffer and updates self.* under the lock.
        # When the helper exits, we collect its result or exception.
        solve_result: dict[str, Any] = {"result": None, "exc": None}

        def _solve_in_helper() -> None:
            try:
                mock_kwargs: dict[str, Any] = {}
                if mock_latency_ms is not None:
                    mock_kwargs["mock_latency_ms"] = mock_latency_ms
                if mock_failure_mode is not None:
                    mock_kwargs["mock_failure_mode"] = mock_failure_mode
                # Positional args are byte-identical to ``solve_hunl_postflop``
                # (PR 5): ``(config, abstraction, iterations,
                # target_exploitability, memory_budget_gb)``. The PR 10b swap
                # drops the ``**mock_kwargs`` line; everything else holds.
                # seed is forwarded only when set (mock has default ``42``).
                extra_kwargs: dict[str, Any] = {
                    "log_every": log_every,
                    "dcfr_kwargs": dcfr_kwargs,
                }
                if seed is not None:
                    extra_kwargs["seed"] = seed
                extra_kwargs.update(mock_kwargs)
                solve_result["result"] = _solve_postflop_impl(
                    config,
                    None,  # abstraction (mock ignores; real PR 5 solver uses)
                    iterations,
                    target_exploitability,
                    memory_budget_gb,
                    **extra_kwargs,
                )
            except BaseException as e:  # noqa: BLE001 -- captured & forwarded
                solve_result["exc"] = e

        helper = threading.Thread(target=_solve_in_helper, daemon=True)
        helper.start()

        # Poll progress + pause/stop events while the helper runs. ~50 ms
        # cadence is fast enough that stop reactivity is within ~1 snapshot.
        last_iter_seen = -1
        while helper.is_alive():
            if self._stop_event.is_set():
                _CANCEL_FLAG.set()
            # Pause: block here while pause is set; periodically re-check stop.
            while self._pause_event.is_set() and not self._stop_event.is_set():
                time.sleep(0.05)
            snapshot = read_latest_progress()
            if snapshot is not None and snapshot.iteration != last_iter_seen:
                last_iter_seen = snapshot.iteration
                with self._lock:
                    self.iteration = snapshot.iteration
                    self.expl_history.append(
                        (snapshot.iteration, snapshot.exploitability)
                    )
                    self.partial_report = snapshot.partial_report
            time.sleep(0.05)

        helper.join()

        # Final snapshot — pick up the last progress update if we missed it.
        snapshot = read_latest_progress()
        if snapshot is not None and snapshot.iteration != last_iter_seen:
            with self._lock:
                self.iteration = snapshot.iteration
                self.expl_history.append((snapshot.iteration, snapshot.exploitability))
                self.partial_report = snapshot.partial_report

        worker_exc = solve_result["exc"]
        result = solve_result["result"]
        if worker_exc is None:
            with self._lock:
                self.result = result
                if self._stop_event.is_set():
                    self.status = "stopped"
                else:
                    self.status = "done"
        elif isinstance(worker_exc, MemoryError):
            # MemoryError.args[1] is MemoryReport per pr10a_spec §7.2.
            with self._lock:
                self.error = worker_exc
                self.status = "error"
                if len(worker_exc.args) > 1 and hasattr(worker_exc.args[1], "total_gb"):
                    self.partial_report = worker_exc.args[1]
        elif isinstance(worker_exc, NotImplementedError):
            with self._lock:
                self.error = worker_exc
                self.status = "error"
        else:
            # Catch-all so the worker never silently dies. The UI surfaces
            # ``state.runner.error`` in the "error" status readout.
            logger.exception(
                "Solve worker raised unexpected exception", exc_info=worker_exc
            )
            with self._lock:
                self.error = worker_exc
                self.status = "error"


# --------------------------------------------------------------------------- #
# AppState aggregator + module-level singleton
# --------------------------------------------------------------------------- #


@dataclass
class AppState:
    """Aggregator passed to view ``render`` functions.

    Two browser tabs share this singleton (per spec §1 non-goal "no multi-
    tab state sync"). Don't try to support multi-tab in PR 10.
    """

    current_spot: Spot
    current_solve: SolveSession | None
    current_tree_node_id: str  # "root" by default; Agent B's tree updates this
    selected_player_for_input: int  # 0 or 1; which tab is active in spot_input
    runner: SolveRunner
    prefs: UIPrefs
    state_path: Path  # ~/.poker_solver_ui/state.json


_STATE_DIR: Path = Path.home() / ".poker_solver_ui"
_STATE_FILE: Path = _STATE_DIR / "state.json"
_STATE_VERSION: int = 1

_state_singleton: AppState | None = None
_state_dirty: bool = False
_state_save_lock: threading.Lock = threading.Lock()
_state_last_save_at: float = 0.0
_STATE_DEBOUNCE_SEC: float = 0.5


def get_state() -> AppState:
    """Return the module-level singleton ``AppState``.

    Lazily initialized on first call; loads from
    ``~/.poker_solver_ui/state.json`` if present. On corrupt JSON or
    version mismatch: warns, backs up to ``state.json.bak``, starts fresh
    (never crashes — per ``pr10a_spec.md`` §9.2).
    """
    global _state_singleton
    if _state_singleton is None:
        _state_singleton = _load_or_default()
    return _state_singleton


def _load_or_default() -> AppState:
    """Construct the singleton, loading prefs from disk if available."""
    prefs = UIPrefs()
    try:
        if _STATE_FILE.exists():
            with _STATE_FILE.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            version = data.get("version", 0)
            if version != _STATE_VERSION:
                raise ValueError(
                    f"state.json version mismatch: got {version}, expected {_STATE_VERSION}"
                )
            prefs_data = data.get("prefs", {})
            prefs = UIPrefs(
                dark_mode=prefs_data.get("dark_mode", "auto"),
                panel_widths=prefs_data.get(
                    "panel_widths", {"left": 320, "bottom": 240}
                ),
                matrix_show_frequencies=prefs_data.get("matrix_show_frequencies", True),
                tree_reach_filter=float(prefs_data.get("tree_reach_filter", 0.01)),
                mock_banner_dismissed=bool(
                    prefs_data.get("mock_banner_dismissed", False)
                ),
                onboarding_completed=bool(
                    prefs_data.get("onboarding_completed", False)
                ),
                chart_log_scale=bool(prefs_data.get("chart_log_scale", True)),
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load state.json (%s); starting from defaults", exc)
        # Back up corrupt file then proceed with defaults.
        if _STATE_FILE.exists():
            try:
                _STATE_FILE.rename(_STATE_DIR / "state.json.bak")
            except OSError:
                logger.exception("Failed to back up corrupt state.json")
    return AppState(
        current_spot=Spot(),
        current_solve=None,
        current_tree_node_id="root",
        selected_player_for_input=0,
        runner=SolveRunner(),
        prefs=prefs,
        state_path=_STATE_FILE,
    )


def save_state() -> None:
    """Mark the state dirty and schedule a debounced atomic save.

    Atomic-write semantics: writes to ``state.json.tmp``, ``fsync``,
    renames to ``state.json``. Coalesces multiple calls inside a 500 ms
    window into one disk write.

    Idempotent: safe to call from any view's on-change handler. The
    NiceGUI timer in ``ui/app.py`` calls ``_maybe_flush_state()`` every
    500 ms to do the actual disk write.
    """
    global _state_dirty
    with _state_save_lock:
        _state_dirty = True


def _maybe_flush_state() -> None:
    """If the state is dirty and the debounce window elapsed, flush to disk.

    Called every 500 ms by the ``ui.timer`` in ``ui/app.py``. Idempotent
    and side-effect-free when the dirty flag is clear.
    """
    global _state_dirty, _state_last_save_at
    with _state_save_lock:
        if not _state_dirty:
            return
        now = time.time()
        if now - _state_last_save_at < _STATE_DEBOUNCE_SEC:
            return
        if _state_singleton is None:
            _state_dirty = False
            return
        try:
            _STATE_DIR.mkdir(parents=True, exist_ok=True)
            payload = _serialize_state(_state_singleton)
            tmp = _STATE_FILE.with_suffix(".json.tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            tmp.replace(_STATE_FILE)
            _state_last_save_at = now
            _state_dirty = False
        except OSError:
            logger.exception("Failed to flush state.json")


def _serialize_state(state: AppState) -> dict[str, Any]:
    """Serialize ``AppState`` to a JSON-friendly dict.

    PR 10a only persists ``prefs`` (per spec §9.2). Spots / ranges / library
    entries land in PR 11.
    """
    return {
        "version": _STATE_VERSION,
        "prefs": {
            "dark_mode": state.prefs.dark_mode,
            "panel_widths": dict(state.prefs.panel_widths),
            "matrix_show_frequencies": state.prefs.matrix_show_frequencies,
            "tree_reach_filter": state.prefs.tree_reach_filter,
            "mock_banner_dismissed": state.prefs.mock_banner_dismissed,
            "onboarding_completed": state.prefs.onboarding_completed,
            "chart_log_scale": state.prefs.chart_log_scale,
        },
    }


def reset_state_for_testing() -> None:
    """Reset the module-level singleton + dirty flag.

    Test-only helper. Smoke tests need a fresh state per test; production
    code never calls this.
    """
    global _state_singleton, _state_dirty, _state_last_save_at
    _state_singleton = None
    _state_dirty = False
    _state_last_save_at = 0.0


# --------------------------------------------------------------------------- #
# Mock-solver gateway (PR 10a only — PR 10b retargets to the real solver)
# --------------------------------------------------------------------------- #
#
# Per ``pr10a_spec.md`` §11 acceptance #7, ``ui.mock_solver`` MUST be imported
# in EXACTLY ONE file: this one. The three call sites that need preset
# metadata, preset materialization, and per-snapshot solving go through the
# accessors below. PR 10b's mechanical swap rewrites the import inside
# ``SolveRunner._worker``; these gateway helpers stay untouched.


def list_fixture_preset_ids() -> list[str]:
    """Return the 12 fixture preset IDs from ``ui.mock_solver``.

    Falls back to the canonical 12 IDs from ``pr10a_spec.md`` §7.4 if
    ``ui.mock_solver`` is not yet wired (PR 10a-pre-Agent-C bootstrap).
    """
    try:
        from ui.mock_solver import list_fixture_presets

        presets = list_fixture_presets()
        return [str(getattr(p, "preset_id", p)) for p in presets]
    except (ImportError, ModuleNotFoundError, AttributeError):
        return [
            "river_tiny_subgame",
            "flop_k72r_100bb",
            "flop_t87s_100bb",
            "flop_monotone_hhh",
            "flop_paired_q9q",
            "turn_kqj9_4_flush",
            "turn_t872_brick",
            "river_axxs_polar",
            "preflop_btn_vs_bb",
            "river_blocker_heavy",
            "shortstack_25bb",
            "deepstack_200bb",
        ]


def load_fixture_config(preset_id: str) -> HUNLConfig | None:
    """Materialize a fixture preset id into a ``HUNLConfig``.

    Returns None if ``ui.mock_solver`` is unavailable (PR 10a-pre-Agent-C
    bootstrap). Raises ``KeyError`` / ``ValueError`` if mock_solver is
    present but the preset is unknown — caller surfaces the notification.
    """
    try:
        from ui.mock_solver import load_fixture
    except (ImportError, ModuleNotFoundError):
        return None
    return load_fixture(preset_id)


__all__ = [
    "AppState",
    "RangeWithFreqs",
    "SolveRunner",
    "SolveSession",
    "Spot",
    "UIPrefs",
    "classify_combo",
    "enumerate_combos",
    "enumerate_hand_classes",
    "get_state",
    "hand_class_label",
    "list_fixture_preset_ids",
    "load_fixture_config",
    "reset_state_for_testing",
    "save_state",
]
