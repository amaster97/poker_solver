"""Per-street memory profiler for DCFRSolver.

Pattern (compute total memory by summing every backing buffer's bytes) is
inspired architecturally by postflop-solver's memory_usage() (AGPL — read-only).
No code copied; implementation derived from first principles per spec §7 of
docs/pr5_prep/pr5_spec.md.

The probe instruments a `DCFRSolver` from outside (no modification to
`dcfr.py`). It walks `solver.infosets`, parses the street tag from each
infoset key (lossless PR 3 OR bucketed PR 4 format), aggregates byte
counters per street, and snapshots a `MemoryReport` JSON-serializable
value object.

`MemoryReport.river_ratio` is the PR 4 revisit trigger per PLAN.md §1:
  - < 30%  -> PR 4 revisit shrinks river bucket count
  - 30-50% -> abstraction well-balanced
  - > 50%  -> consider lossless river

`psutil` is used for ground-truth process RSS calibration. The 10% tolerance
on `MemoryReport.rss_calibration_error` is empirically calibrated; if a
future Python release significantly changes dict / interpreter slack, this
assertion may need re-tuning.
"""

from __future__ import annotations

import sys
import warnings
from dataclasses import dataclass

import psutil  # type: ignore[import-untyped]

from poker_solver.abstraction.buckets import AbstractionTables
from poker_solver.dcfr import DCFRSolver, InfosetData
from poker_solver.hunl import Street

# Map from street tokens (per `hunl.py` `_STREET_TOKENS`) to `Street` values.
# Re-derived here (rather than imported) to keep the profiler decoupled
# from `hunl.py` internals; only the `Street` enum is part of the public
# surface.
_STREET_TOKEN_MAP: dict[str, Street] = {
    "p": Street.PREFLOP,
    "f": Street.FLOP,
    "t": Street.TURN,
    "r": Street.RIVER,
    "s": Street.SHOWDOWN,
}

# Heuristic multiplier for Python dict slack + per-key overhead. The
# `psutil` calibration check (`rss_calibration_error < 0.10`) is the
# ground-truth gate; tune this if calibration drifts on a new interpreter.
_DICT_OVERHEAD_RATIO: float = 0.5

# Single source of truth for byte-to-GB conversion used in `MemoryReport`
# derived properties; replaces inline ``1024**3`` literals.
_BYTES_PER_GB: int = 1024**3


@dataclass(frozen=True)
class StreetMemoryEntry:
    """Per-street row in the `MemoryReport`.

    All byte fields are exact (sum of `np.ndarray.nbytes` for backing
    buffers; `sys.getsizeof` for dataclass / key strings). No estimates.
    """

    street: Street
    infoset_count: int
    regret_bytes: int
    strategy_bytes: int
    other_bytes: int
    total_bytes: int
    mean_actions_per_infoset: float
    max_actions_per_infoset: int


@dataclass(frozen=True)
class MemoryReport:
    """Per-street memory breakdown + total + `psutil` RSS calibration.

    JSON-serializable: every canonical field is a primitive (`int` /
    `float` / `bool` / `str` / `tuple` of frozen dataclasses). PR 10
    will serialize this for the GUI.

    Cross-agent contract convenience fields (`flop_gb`, `turn_gb`,
    `river_gb`, `total_gb`, `process_rss_gb`, `river_ratio`) are derived
    properties over the canonical fields and are NOT stored.
    """

    # Canonical fields per spec §7.2 - primitive, JSON-friendly.
    #
    # ``iterations_at_snapshot`` is ``DCFRSolver.iteration`` at probe-snapshot
    # time. This is the *cumulative* iteration counter since solver
    # construction — repeated ``solver.solve(N)`` calls accumulate (running
    # 100 then 50 yields ``iterations_at_snapshot == 150``), not the last
    # chunk's iteration count.
    per_street: tuple[StreetMemoryEntry, ...]
    preflop_lossless_entry: StreetMemoryEntry | None
    abstraction_table_bytes: int
    solver_arrays_total_bytes: int
    other_overhead_bytes: int
    grand_total_bytes: int
    rss_observed_bytes: int
    rss_baseline_bytes: int
    wallclock_per_iter_sec: float | None
    iterations_at_snapshot: int

    # ---------------------------------------------------------------
    # Cross-agent contract convenience fields (in GB)
    # ---------------------------------------------------------------

    @property
    def flop_gb(self) -> float:
        return self._bytes_for(Street.FLOP) / _BYTES_PER_GB

    @property
    def turn_gb(self) -> float:
        return self._bytes_for(Street.TURN) / _BYTES_PER_GB

    @property
    def river_gb(self) -> float:
        return self._bytes_for(Street.RIVER) / _BYTES_PER_GB

    @property
    def total_gb(self) -> float:
        """Grand total (solver + abstraction + overhead) in GB."""
        return self.grand_total_bytes / _BYTES_PER_GB

    @property
    def process_rss_gb(self) -> float:
        """`psutil` RSS at snapshot time, in GB."""
        return self.rss_observed_bytes / _BYTES_PER_GB

    @property
    def river_ratio(self) -> float:
        """River layer's share of total SOLVER arrays.

        The PR 4 revisit trigger per PLAN.md §1 "Card abstraction":
          - < 30%  -> PR 4 revisit shrinks river bucket count
          - 30-50% -> abstraction well-balanced
          - > 50%  -> consider lossless river

        Ratio is over `solver_arrays_total_bytes` (NOT `grand_total_bytes`)
        because the abstraction table is a one-time fixed cost, not part
        of the solver's per-infoset growth.

        Returns 0.0 if `solver_arrays_total_bytes == 0` (empty solver).
        """
        if self.solver_arrays_total_bytes == 0:
            return 0.0
        return (
            self._solver_array_bytes_for(Street.RIVER) / self.solver_arrays_total_bytes
        )

    @property
    def rss_calibration_error(self) -> float:
        """Relative error: |predicted_growth - actual_growth| / actual_growth.

        - actual_growth   = rss_observed_bytes - rss_baseline_bytes
        - predicted_growth = solver_arrays_total_bytes + other_overhead_bytes

        Returns 0.0 if actual <= 0 (baseline >= observed; can happen on
        cold start or after GC reclaim - calibration is meaningless).
        """
        actual = self.rss_observed_bytes - self.rss_baseline_bytes
        predicted = self.solver_arrays_total_bytes + self.other_overhead_bytes
        if actual <= 0:
            return 0.0
        return abs(predicted - actual) / actual

    def _bytes_for(self, street: Street) -> int:
        """Internal: total bytes (incl. overhead) from per_street entries."""
        for entry in self.per_street:
            if entry.street == street:
                return entry.total_bytes
        return 0

    def _solver_array_bytes_for(self, street: Street) -> int:
        """Internal: solver-array bytes only (regret + strategy) for a street.

        Used by `river_ratio` so the numerator and denominator
        (`solver_arrays_total_bytes`) are both measured on the same
        "arrays only" basis — overhead is excluded from both.
        """
        for entry in self.per_street:
            if entry.street == street:
                return entry.regret_bytes + entry.strategy_bytes
        return 0


def _parse_street_from_key(infoset_key: str) -> Street | None:
    """Extract the street token from a PR 3 (lossless) or PR 4 (bucketed) key.

    Lossless format: ``'AhKh|7d2c9h|f|xx'`` -> split on ``'|'`` -> token at
    index 2 (``'f'``) -> ``Street.FLOP``.

    Bucketed format: ``'b3|f|xx'`` -> split on ``'|'`` -> first token starts
    with ``'b'`` -> street token at index 1 (``'f'``) -> ``Street.FLOP``.

    Unknown formats: returns ``None`` (caller emits a warning and lumps
    the infoset into an "unknown" bucket).

    Returns:
        ``Street.PREFLOP`` / ``FLOP`` / ``TURN`` / ``RIVER`` for tokens
        ``p`` / ``f`` / ``t`` / ``r``. Showdown is not expected as a
        runtime infoset street; if encountered, returns ``Street.SHOWDOWN``.
        Returns ``None`` if the key cannot be parsed.
    """
    if not infoset_key:
        return None
    parts = infoset_key.split("|")
    if len(parts) < 2:
        return None
    first = parts[0]
    # Bucketed format: 'b{bucket_id}|{street_token}|...'
    if first.startswith("b") and len(first) >= 2 and first[1:].lstrip("-").isdigit():
        token = parts[1] if len(parts) >= 2 else ""
        return _STREET_TOKEN_MAP.get(token)
    # Lossless format: '{hole}|{board}|{street_token}|{history}'
    if len(parts) < 3:
        return None
    token = parts[2]
    return _STREET_TOKEN_MAP.get(token)


def _key_other_bytes(key: str, info: InfosetData) -> int:
    """Bytes for the dict entry's non-array overhead (key string + dataclass).

    - ``len(key.encode('utf-8'))``: the raw key string content (Python's
      ``sys.getsizeof(key)`` adds a fixed-string header which we lump into
      ``other_overhead_bytes`` via the dict-slack heuristic instead).
    - ``sys.getsizeof(info)``: the `InfosetData` dataclass header.
    """
    return len(key.encode("utf-8")) + sys.getsizeof(info)


def _compute_street_entries(
    infosets: dict[str, InfosetData],
) -> tuple[
    dict[Street, StreetMemoryEntry],
    StreetMemoryEntry | None,
    int,
]:
    """Group infosets by parsed street and compute per-street byte totals.

    Returns:
        - ``entries``: ``{Street: StreetMemoryEntry}`` for every street with
          at least one infoset. Excludes preflop (returned separately as
          ``preflop_entry``).
        - ``preflop_entry``: the lossless preflop entry if any, else ``None``.
        - ``unknown_bytes``: bytes for infosets whose key could not be parsed
          (lumped into ``other_overhead_bytes`` by the caller).
    """
    # Accumulators per street.
    per_street_accum: dict[Street, dict[str, float | int]] = {}
    unknown_bytes = 0
    warned_unknown = False

    for key, info in infosets.items():
        street = _parse_street_from_key(key)
        regret_b = int(info.regret_sum.nbytes)
        strategy_b = int(info.strategy_sum.nbytes)
        other_b = _key_other_bytes(key, info)
        total_b = regret_b + strategy_b + other_b

        if street is None:
            if not warned_unknown:
                warnings.warn(
                    f"profiler: unparseable infoset key {key!r}; lumping "
                    "into other_overhead_bytes (warning suppressed for "
                    "subsequent keys this snapshot)",
                    RuntimeWarning,
                    stacklevel=2,
                )
                warned_unknown = True
            unknown_bytes += total_b
            continue

        acc = per_street_accum.setdefault(
            street,
            {
                "infoset_count": 0,
                "regret_bytes": 0,
                "strategy_bytes": 0,
                "other_bytes": 0,
                "total_bytes": 0,
                "actions_sum": 0,
                "max_actions": 0,
            },
        )
        acc["infoset_count"] += 1
        acc["regret_bytes"] += regret_b
        acc["strategy_bytes"] += strategy_b
        acc["other_bytes"] += other_b
        acc["total_bytes"] += total_b
        acc["actions_sum"] += int(info.num_actions)
        if int(info.num_actions) > int(acc["max_actions"]):
            acc["max_actions"] = int(info.num_actions)

    entries: dict[Street, StreetMemoryEntry] = {}
    preflop_entry: StreetMemoryEntry | None = None
    for street, acc in per_street_accum.items():
        count = int(acc["infoset_count"])
        mean_actions = float(acc["actions_sum"]) / float(count) if count > 0 else 0.0
        entry = StreetMemoryEntry(
            street=street,
            infoset_count=count,
            regret_bytes=int(acc["regret_bytes"]),
            strategy_bytes=int(acc["strategy_bytes"]),
            other_bytes=int(acc["other_bytes"]),
            total_bytes=int(acc["total_bytes"]),
            mean_actions_per_infoset=mean_actions,
            max_actions_per_infoset=int(acc["max_actions"]),
        )
        if street == Street.PREFLOP:
            preflop_entry = entry
        else:
            entries[street] = entry

    return entries, preflop_entry, unknown_bytes


def _abstraction_table_bytes(tables: AbstractionTables) -> int:
    """Sum every backing buffer in an `AbstractionTables` per spec §7.5.

    Counts the six NumPy assignment / board-index arrays plus the
    metadata dict (via `sys.getsizeof`). Hand-index dicts are NOT included
    in the deterministic "table" total because they're dynamically sized
    Python dicts whose true memory footprint is captured by `psutil` RSS
    (and reflected in the calibration slack). Per consistency review B2,
    `source_path` (a `Path | None`) is negligible and excluded.
    """
    # `*_board_index` are Python dicts (`dict[str, int]`). Their backing
    # is dynamically sized; `sys.getsizeof` approximates the table header
    # but excludes the heap-allocated key strings. We include the dict
    # header here for completeness; per-key string bytes are not accounted
    # (they roll into the `psutil` calibration slack).
    total = (
        int(tables.flop_assignments.nbytes)
        + int(tables.turn_assignments.nbytes)
        + int(tables.river_assignments.nbytes)
        + sys.getsizeof(tables.flop_board_index)
        + sys.getsizeof(tables.turn_board_index)
        + sys.getsizeof(tables.river_board_index)
        + sys.getsizeof(tables.metadata)
    )
    return int(total)


def _compute_other_overhead(other_bytes_total: int, extra_bytes: int = 0) -> int:
    """Heuristic Python dict slack + interpreter overhead estimate.

    Multiplies the sum of per-infoset `other_bytes` (key strings + dataclass
    headers) by `_DICT_OVERHEAD_RATIO` to approximate the `solver.infosets`
    dict's hash-table slack. Adds `extra_bytes` (e.g., unknown-format
    infoset bytes that don't belong to any street).

    The `psutil` RSS calibration check is the ground-truth gate; this
    heuristic is purely a best-effort attribution that lets the report's
    `grand_total_bytes` track actual process RSS within ~10%.
    """
    return int(other_bytes_total * _DICT_OVERHEAD_RATIO) + int(extra_bytes)


class MemoryProbe:
    """Instruments a `DCFRSolver` from outside. No modification to `dcfr.py`.

    Walks `solver.infosets`, groups by street tag parsed from the infoset
    key, computes byte totals, and snapshots a `MemoryReport`. Also captures
    `psutil` RSS for the calibration check (spec §7.6).

    `psutil.Process().memory_info().rss` is captured at construction time
    so subsequent growth is measured from a fixed baseline. The baseline
    includes the interpreter, already-loaded modules, and the abstraction
    table (if pre-loaded), but NOT the solver's infoset dict (which is
    empty at construction).
    """

    def __init__(
        self,
        solver: DCFRSolver,
        *,
        include_abstraction: AbstractionTables | None = None,
    ) -> None:
        """Capture the baseline RSS at construction time.

        Args:
            solver: the `DCFRSolver` to instrument. Read-only access to
                `solver.infosets`.
            include_abstraction: optional PR 4 `AbstractionTables` to
                include in `grand_total_bytes` accounting (spec §7.5).
        """
        self._solver = solver
        self._abstraction = include_abstraction
        self._rss_baseline_bytes: int = int(psutil.Process().memory_info().rss)
        self._latest_snapshot: MemoryReport | None = None

    @property
    def solver(self) -> DCFRSolver:
        """The instrumented solver (read-only access)."""
        return self._solver

    def snapshot(self) -> MemoryReport:
        """Walk `solver.infosets`, group by street, compute byte totals.

        Side effect: stores the result in ``self._latest_snapshot``.

        Returns a fully-populated `MemoryReport`. For an empty solver
        (no iterations run yet), ``per_street`` is empty tuple and
        ``solver_arrays_total_bytes`` is 0.
        """
        infosets = self._solver.infosets

        entries_by_street, preflop_entry, unknown_bytes = _compute_street_entries(
            infosets
        )

        # Stable ordering for deterministic byte accounting / tests.
        ordered_streets = (Street.FLOP, Street.TURN, Street.RIVER, Street.SHOWDOWN)
        per_street_tuple: tuple[StreetMemoryEntry, ...] = tuple(
            entries_by_street[s] for s in ordered_streets if s in entries_by_street
        )

        # Solver arrays: regret + strategy bytes across ALL streets (incl.
        # preflop). `other_bytes` (key strings + dataclass headers) is
        # tracked separately so the `_compute_other_overhead` heuristic
        # can model dict slack.
        solver_arrays_total = 0
        other_bytes_total = 0
        for entry in per_street_tuple:
            solver_arrays_total += entry.regret_bytes + entry.strategy_bytes
            other_bytes_total += entry.other_bytes
        if preflop_entry is not None:
            solver_arrays_total += (
                preflop_entry.regret_bytes + preflop_entry.strategy_bytes
            )
            other_bytes_total += preflop_entry.other_bytes

        abstraction_bytes = (
            _abstraction_table_bytes(self._abstraction)
            if self._abstraction is not None
            else 0
        )
        slack_overhead = _compute_other_overhead(
            other_bytes_total, extra_bytes=unknown_bytes
        )

        # `other_overhead_bytes` reports the SUM of raw per-infoset overhead
        # (key strings + dataclass headers) plus the dict-slack heuristic
        # plus any unknown-format bytes. This is what `grand_total_bytes`
        # adds on top of `solver_arrays_total_bytes`.
        other_overhead_bytes = other_bytes_total + slack_overhead

        grand_total = solver_arrays_total + abstraction_bytes + other_overhead_bytes

        rss_observed = int(psutil.Process().memory_info().rss)

        report = MemoryReport(
            per_street=per_street_tuple,
            preflop_lossless_entry=preflop_entry,
            abstraction_table_bytes=int(abstraction_bytes),
            solver_arrays_total_bytes=int(solver_arrays_total),
            other_overhead_bytes=int(other_overhead_bytes),
            grand_total_bytes=int(grand_total),
            rss_observed_bytes=rss_observed,
            rss_baseline_bytes=int(self._rss_baseline_bytes),
            wallclock_per_iter_sec=None,
            iterations_at_snapshot=int(self._solver.iteration),
        )
        self._latest_snapshot = report
        return report

    def measure_per_street(self, dcfr_solver: DCFRSolver) -> MemoryReport:
        """Alias for `snapshot()` that accepts the solver explicitly.

        Cross-agent contract from the orchestrator brief — kept distinct
        from `snapshot()` for binding clarity when callers want the solver
        identity to appear in the call site. The PR 5 spec §6/§7.1 only
        names ``snapshot()`` directly; this alias is intentional public
        surface (do NOT remove without coordinating with the orchestrator
        contract).

        Internally equivalent to `snapshot()` when
        ``dcfr_solver is self._solver``. If a *different* solver is passed,
        this probe still walks `self._solver.infosets` - the explicit
        argument is informational and ignored, matching the orchestrator's
        "call signature is for binding clarity" intent.
        """
        if dcfr_solver is not self._solver:
            warnings.warn(
                "MemoryProbe.measure_per_street called with a solver that "
                "differs from the one this probe was constructed with; "
                "the probe will measure its bound solver and ignore the "
                "argument (construct a new MemoryProbe for the other solver)",
                RuntimeWarning,
                stacklevel=2,
            )
        return self.snapshot()

    @property
    def latest(self) -> MemoryReport:
        """Most recent snapshot.

        Raises:
            RuntimeError: if `snapshot()` has not been called yet.
        """
        if self._latest_snapshot is None:
            raise RuntimeError(
                "MemoryProbe.latest accessed before snapshot() was called"
            )
        return self._latest_snapshot


__all__ = [
    "MemoryProbe",
    "MemoryReport",
    "StreetMemoryEntry",
    "_parse_street_from_key",
]
