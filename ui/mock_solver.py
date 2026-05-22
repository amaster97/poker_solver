"""Mock solver for PR 10a — drop-in stand-in for ``solve_hunl_postflop``.

Public surface byte-locked per ``pr10a_spec.md`` §7.1 to enable PR 10b's
one-line import swap. The first 8 parameters of ``mock_solve`` are
identical to PR 5's ``solve_hunl_postflop`` (positional + keyword order);
trailing ``mock_*`` parameters have defaults and are not part of the
real surface.

Failure modes (``mock_failure_mode``):
  - ``'oom'``             — raises ``MemoryError("mock OOM", partial_report)``
                            after ~10% of the simulated latency.
  - ``'not_implemented'`` — raises ``NotImplementedError``.
  - ``'cancelled'``       — returns ``HUNLSolveResult`` with
                            ``iterations < requested``.
  - ``'long_latency'``    — sleeps for 10 min with periodic progress
                            callbacks; cancellable via ``_CANCEL_FLAG``.
  - ``'rapid_iteration'`` — 100 ms latency; tests UI chart-flooding guards.
  - ``None``              — successful solve, latency = ``mock_latency_ms``.

Cancellation contract (``pr10a_spec.md`` §7.5):
  ``SolveRunner.stop()`` sets the module-level ``_CANCEL_FLAG``. The mock
  loop checks ``_CANCEL_FLAG.is_set()`` once per snapshot; if set, the
  loop breaks and returns a partial result with ``iterations <
  requested``. **Same flag survives the PR 10b swap.**

License posture: no code copied from references/code/. The fixture
strategies are hand-crafted (see ``mock_solver_fixtures.py``).
"""

from __future__ import annotations

import math
import random
import threading
import time
from dataclasses import dataclass
from typing import Any

from poker_solver.hunl import HUNLConfig, Street
from poker_solver.hunl_solver import HUNLSolveResult
from poker_solver.profiler.memory import MemoryReport, StreetMemoryEntry
from ui.mock_solver_fixtures import (
    ACTION_LABELS,
    FIXTURE_PRESETS,
    FixturePreset,
    build_fixture,
    fixture_ids,
)

# Module-level cancellation flag. ``SolveRunner.stop()`` sets it;
# ``mock_solve()`` checks ``_CANCEL_FLAG.is_set()`` once per snapshot.
# **Same flag survives the PR 10b swap.**
_CANCEL_FLAG: threading.Event = threading.Event()


# Module-level progress buffer (per ``docs/pr10_prep/mock_signature_drift.md``
# Option A). The worker thread calls ``_publish_progress`` once per snapshot;
# the UI thread polls ``read_latest_progress`` via ``ui.timer``. This decouples
# mock_solve's signature from the real ``solve_hunl_postflop`` signature
# (which has no ``on_progress`` parameter), enabling PR 10b's one-line swap.


@dataclass(frozen=True)
class _ProgressSnapshot:
    iteration: int
    exploitability: float
    partial_report: MemoryReport


_PROGRESS_LOCK: threading.Lock = threading.Lock()
_LATEST_PROGRESS: _ProgressSnapshot | None = None


def _publish_progress(iter_n: int, expl: float, report: MemoryReport) -> None:
    """Worker-thread side: write the latest snapshot under the lock."""
    global _LATEST_PROGRESS
    with _PROGRESS_LOCK:
        _LATEST_PROGRESS = _ProgressSnapshot(iter_n, expl, report)


def read_latest_progress() -> _ProgressSnapshot | None:
    """UI-thread helper; non-blocking. Returns the most recent snapshot, or
    ``None`` if no snapshot has been published since the last
    ``reset_progress_buffer`` call."""
    with _PROGRESS_LOCK:
        return _LATEST_PROGRESS


def reset_progress_buffer() -> None:
    """Clear the latest snapshot. Called by ``SolveRunner.start`` so a new
    solve doesn't see the previous solve's residual progress."""
    global _LATEST_PROGRESS
    with _PROGRESS_LOCK:
        _LATEST_PROGRESS = None


# Number of snapshots the mock loop emits regardless of ``iterations``.
# Snapshot count is decoupled from iteration target so progress callbacks
# fire predictably even when ``mock_latency_ms == 0`` (test mode).
_DEFAULT_SNAPSHOTS: int = 20


# Bytes-per-infoset fudge for fabricated MemoryReports. Chosen so a 50k
# iteration solve fabricates ~1.5 GB total (well under the 14 GB budget),
# matching the rough scale of a real flop-start lossless solve.
_BYTES_PER_INFOSET: int = 4_096


def _stream_progress(
    iterations: int,
    log_every: int | None,
    *,
    latency_ms: int,
    cancellable: bool,
    starting_expl: float = 50.0,
    final_expl: float = 0.5,
    cancel_at_fraction: float | None = None,
) -> tuple[int, list[float]]:
    """Publish progress snapshots to ``_LATEST_PROGRESS`` while simulating a
    solve.

    Returns ``(iterations_completed, exploitability_history)``.

    Exploitability follows a geometric decay from ``starting_expl`` to
    ``final_expl`` so the live chart (log-Y) shows a clean monotone line.

    ``cancel_at_fraction``: if not None, simulate hitting cancellation at
    that fraction of total iterations (regardless of ``_CANCEL_FLAG``).
    """
    if iterations <= 0:
        return 0, []

    # Snapshot count: at least one per ``log_every`` chunk, capped so the
    # UI chart doesn't get flooded with thousands of points.
    if log_every is not None and log_every > 0:
        snapshots = max(1, iterations // log_every)
    else:
        snapshots = _DEFAULT_SNAPSHOTS
    snapshots = min(snapshots, _DEFAULT_SNAPSHOTS * 5)

    per_snapshot_ms = max(0, latency_ms // max(1, snapshots))
    history: list[float] = []
    iters_done = 0

    cancel_iter_threshold: int | None
    if cancel_at_fraction is not None:
        cancel_iter_threshold = int(iterations * cancel_at_fraction)
    else:
        cancel_iter_threshold = None

    # Geometric decay: expl(t) = starting * (final/starting)^(t/total).
    log_ratio = math.log(max(final_expl, 1e-9) / max(starting_expl, 1e-9))

    for k in range(1, snapshots + 1):
        # Cooperative cancellation check.
        if cancellable and _CANCEL_FLAG.is_set():
            break

        if per_snapshot_ms > 0:
            # Sleep in small slices so cancellation lands fast even under
            # large per-snapshot latencies (10 minute long-latency mode).
            slept_ms = 0
            slice_ms = min(50, per_snapshot_ms)
            while slept_ms < per_snapshot_ms:
                if cancellable and _CANCEL_FLAG.is_set():
                    break
                time.sleep(slice_ms / 1000.0)
                slept_ms += slice_ms
            if cancellable and _CANCEL_FLAG.is_set():
                break

        frac = k / snapshots
        iters_done = int(iterations * frac)
        # Inject a small amount of noise so the chart doesn't look fake.
        noise = 0.92 + 0.16 * random.Random(k).random()
        expl = max(1e-9, starting_expl * math.exp(log_ratio * frac) * noise)
        history.append(expl)

        if cancel_iter_threshold is not None and iters_done >= cancel_iter_threshold:
            # Simulated cancellation; partial result.
            partial_report = _fabricate_memory_report(
                iterations=iters_done,
                starting_street_name="FLOP",
                wallclock_per_iter_sec=((latency_ms / 1000.0) / max(1, iterations)),
            )
            _publish_progress(iters_done, expl, partial_report)
            break

        partial_report = _fabricate_memory_report(
            iterations=iters_done,
            starting_street_name="FLOP",
            wallclock_per_iter_sec=((latency_ms / 1000.0) / max(1, iterations)),
        )
        _publish_progress(iters_done, expl, partial_report)

    return iters_done, history


def _fabricate_memory_report(
    *,
    iterations: int,
    starting_street_name: str,
    wallclock_per_iter_sec: float | None,
) -> MemoryReport:
    """Build a plausible ``MemoryReport`` for the mock loop.

    Per ``pr10a_spec.md`` §7.3 the UI reads:
      - ``total_gb`` (main metric)
      - ``per_street`` (list[StreetMemoryEntry])
      - ``river_ratio`` (target [0.30, 0.50])
      - ``rss_calibration_error`` (target ≤ 0.10)
      - ``wallclock_per_iter_sec`` (feeds ETA)

    We construct ``per_street`` so ``river_ratio`` lands in [0.30, 0.50]
    (well-balanced) and ``rss_calibration_error`` lands ≤ 0.10.
    """
    # Per-street infoset count scaling: river > turn > flop for postflop
    # subgames (matches typical lossless tree shape). For preflop-start
    # scale all four streets.
    if starting_street_name == "PREFLOP":
        street_infosets = {
            Street.PREFLOP: max(0, iterations // 10),
            Street.FLOP: max(0, iterations // 5),
            Street.TURN: max(0, iterations // 3),
            Street.RIVER: max(0, iterations // 2),
        }
    elif starting_street_name == "FLOP":
        street_infosets = {
            Street.FLOP: max(0, iterations // 5),
            Street.TURN: max(0, iterations // 3),
            Street.RIVER: max(0, int(iterations * 0.4)),
        }
    elif starting_street_name == "TURN":
        street_infosets = {
            Street.TURN: max(0, iterations // 3),
            Street.RIVER: max(0, int(iterations * 0.4)),
        }
    else:  # RIVER start.
        street_infosets = {
            Street.RIVER: max(0, iterations // 2),
        }

    entries: list[StreetMemoryEntry] = []
    solver_arrays_total = 0
    other_bytes_total = 0
    for street, count in street_infosets.items():
        # Heuristic: regret + strategy arrays each take ~half of bytes,
        # plus a small overhead per infoset (key string + dataclass).
        regret_b = int(count * _BYTES_PER_INFOSET * 0.45)
        strategy_b = int(count * _BYTES_PER_INFOSET * 0.45)
        other_b = int(count * _BYTES_PER_INFOSET * 0.10)
        total_b = regret_b + strategy_b + other_b
        entries.append(
            StreetMemoryEntry(
                street=street,
                infoset_count=count,
                regret_bytes=regret_b,
                strategy_bytes=strategy_b,
                other_bytes=other_b,
                total_bytes=total_b,
                mean_actions_per_infoset=4.0,
                max_actions_per_infoset=6,
            )
        )
        solver_arrays_total += regret_b + strategy_b
        other_bytes_total += other_b

    # Per ``pr10a_spec.md`` §7.3: target ``river_ratio`` in [0.30, 0.50].
    # Our scaling above naturally lands there for postflop starts; verify
    # and pad the river entry if needed.
    if solver_arrays_total > 0:
        river_solver_bytes = sum(
            e.regret_bytes + e.strategy_bytes
            for e in entries
            if e.street == Street.RIVER
        )
        ratio = river_solver_bytes / solver_arrays_total
        if ratio < 0.30 and entries:
            # Inflate river entry's regret to push ratio up to 0.40.
            target_river = int(solver_arrays_total * 0.40 / (1 - 0.40))
            for i, e in enumerate(entries):
                if e.street == Street.RIVER:
                    delta = max(0, target_river - river_solver_bytes)
                    new_regret = e.regret_bytes + delta // 2
                    new_strategy = e.strategy_bytes + delta // 2
                    new_total = new_regret + new_strategy + e.other_bytes
                    entries[i] = StreetMemoryEntry(
                        street=e.street,
                        infoset_count=e.infoset_count,
                        regret_bytes=new_regret,
                        strategy_bytes=new_strategy,
                        other_bytes=e.other_bytes,
                        total_bytes=new_total,
                        mean_actions_per_infoset=e.mean_actions_per_infoset,
                        max_actions_per_infoset=e.max_actions_per_infoset,
                    )
                    solver_arrays_total += delta
                    break

    other_overhead = other_bytes_total + int(other_bytes_total * 0.5)
    grand_total = solver_arrays_total + other_overhead

    # ``rss_observed_bytes - rss_baseline_bytes`` should be close to
    # ``solver_arrays_total_bytes + other_overhead_bytes`` so calibration
    # error stays ≤ 0.10.
    actual_growth = solver_arrays_total + other_overhead
    rss_baseline = 200 * 1024 * 1024  # 200 MB synthetic baseline
    rss_observed = rss_baseline + int(actual_growth * 1.03)

    return MemoryReport(
        per_street=tuple(entries),
        preflop_lossless_entry=None,
        abstraction_table_bytes=0,
        solver_arrays_total_bytes=solver_arrays_total,
        other_overhead_bytes=other_overhead,
        grand_total_bytes=grand_total,
        rss_observed_bytes=rss_observed,
        rss_baseline_bytes=rss_baseline,
        wallclock_per_iter_sec=wallclock_per_iter_sec,
        iterations_at_snapshot=iterations,
    )


def _starting_street_name(config: HUNLConfig) -> str:
    """Map ``config.starting_street`` to the fabricator's street tag."""
    s = config.starting_street
    if s == Street.PREFLOP:
        return "PREFLOP"
    if s == Street.FLOP:
        return "FLOP"
    if s == Street.TURN:
        return "TURN"
    return "RIVER"


def _fixture_id_for_config(config: HUNLConfig) -> str | None:
    """Heuristic: hash a config into one of the 12 fixture IDs by board match.

    The UI plumbs the chosen ``preset_id`` through ``HUNLConfig`` indirectly
    (via the board it builds). We match on initial_board cards to retrieve
    the canned strategy. Returns ``None`` if no fixture matches; the mock
    then falls back to a generic strategy.
    """
    for fid in fixture_ids():
        try:
            cfg, _strat = build_fixture(fid)
        except KeyError:
            continue
        if cfg.initial_board == config.initial_board:
            return fid
    return None


def _fallback_strategy(starting_street: Street) -> dict[str, list[float]]:
    """Generic strategy for off-distribution configs.

    Per ``pr10a_spec.md`` §12 risk #2: off-distribution strategies aren't
    guaranteed poker-coherent. The "(mock approximation)" overlay in the
    UI mitigates user confusion.
    """
    from ui.mock_solver_fixtures import _build_average_strategy

    name_map = {
        Street.PREFLOP: "PREFLOP",
        Street.FLOP: "FLOP",
        Street.TURN: "TURN",
        Street.RIVER: "RIVER",
    }
    name = name_map.get(starting_street, "FLOP")
    return _build_average_strategy(name, "generic", polarized=False)


def mock_solve(
    config: HUNLConfig,
    abstraction: Any = None,
    iterations: int = 1000,
    target_exploitability: float | None = None,
    memory_budget_gb: float = 14.0,
    *,
    log_every: int = 50,
    seed: int = 42,
    dcfr_kwargs: dict[str, Any] | None = None,
    # ---- mock-specific knobs (kwarg-only) ----
    mock_latency_ms: int = 0,
    mock_failure_mode: str | None = None,
) -> HUNLSolveResult:
    """Drop-in mock for ``solve_hunl_postflop``.

    Signature is byte-identical to PR 5's
    ``solve_hunl_postflop(config, abstraction, iterations,
    target_exploitability, memory_budget_gb, *, log_every, seed,
    dcfr_kwargs)`` so PR 10b is a one-line ``from
    poker_solver.hunl_solver import solve_hunl_postflop as
    _solve_postflop_impl`` swap. The trailing ``mock_*`` parameters have
    defaults and are dropped at the swap site (they don't appear in the
    real solver's signature).

    Progress is published to ``_LATEST_PROGRESS`` via
    ``_publish_progress``; UI threads poll ``read_latest_progress()``.
    There is no ``on_progress`` callback (the real solver doesn't take
    one); see ``docs/pr10_prep/mock_signature_drift.md`` Option A.

    Args:
        config: a ``HUNLConfig``. Postflop configs pass through; preflop
            configs fall back to the generic-strategy path (the real
            solver in PR 10b will dispatch to PR 9's preflop solver).
        abstraction: ignored by the mock; the real PR 5 solver consumes
            it. Accept-and-ignore so the call site is byte-identical.
        iterations: target iteration count. Mock loop emits a fixed
            number of snapshots regardless; the final
            ``HUNLSolveResult.iterations`` reflects the cancellation /
            failure status.
        target_exploitability: forwarded to the success path; the mock
            decays expl from 50 mBB → 0.5 mBB, so any
            ``target_exploitability >= 0.5`` will be "hit" near the end.
        memory_budget_gb: forwarded to ``mock_failure_mode='oom'`` only
            (and ignored in the success path; the mock's fabricated
            ``MemoryReport`` never exceeds the budget).
        log_every: snapshot cadence hint; the mock uses it to pick a
            snapshot count.
        seed: deterministic seed for the noise injection in progress
            snapshots.
        dcfr_kwargs: ignored; preserved for surface compatibility.
        mock_latency_ms: how long the simulated solve takes overall.
            Set to 0 in tests to skip waiting.
        mock_failure_mode: see module docstring. None → success.

    Returns:
        A ``HUNLSolveResult`` whose ``average_strategy`` either matches
        the matched fixture's hand-crafted dict (if the config's board
        matches a fixture), or a generic fallback otherwise.

    Raises:
        MemoryError: ``mock_failure_mode='oom'``. ``args[1]`` is a
            ``MemoryReport`` (partial).
        NotImplementedError: ``mock_failure_mode='not_implemented'``.
    """
    del abstraction  # mock ignores; real PR 5 solver consumes it.
    del dcfr_kwargs  # surface compatibility only.
    del memory_budget_gb  # see docstring; ignored in success path.
    del target_exploitability  # mock decays expl on a fixed schedule.

    # Failure mode dispatch.
    if mock_failure_mode == "not_implemented":
        raise NotImplementedError(
            "mock_failure_mode='not_implemented' — simulated unsupported config "
            "(real solver would raise this for preflop-start in pre-PR-9 builds)."
        )

    if mock_failure_mode == "oom":
        # Run ~10% of the latency, then raise MemoryError with a partial
        # report attached to args[1] per spec §6.5 + §7.5.
        partial_iters, _history = _stream_progress(
            iterations=iterations,
            log_every=log_every,
            latency_ms=max(0, mock_latency_ms // 10),
            cancellable=True,
            cancel_at_fraction=0.10,
        )
        report = _fabricate_memory_report(
            iterations=partial_iters,
            starting_street_name=_starting_street_name(config),
            wallclock_per_iter_sec=((mock_latency_ms / 1000.0) / max(1, iterations)),
        )
        raise MemoryError("mock OOM", report)

    if mock_failure_mode == "long_latency":
        effective_latency = max(mock_latency_ms, 600_000)  # 10 min floor
        cancel_at: float | None = None
    elif mock_failure_mode == "rapid_iteration":
        effective_latency = 100  # 100 ms floor.
        cancel_at = None
    elif mock_failure_mode == "cancelled":
        effective_latency = mock_latency_ms
        cancel_at = 0.4  # simulate stop at 40% completion
    else:
        effective_latency = mock_latency_ms
        cancel_at = None

    # Seed the noise RNG for reproducible runs.
    if seed is not None:
        random.seed(seed)

    iters_done, history = _stream_progress(
        iterations=iterations,
        log_every=log_every,
        latency_ms=effective_latency,
        cancellable=True,
        cancel_at_fraction=cancel_at,
    )

    # Look up the canned strategy if the config matches a fixture board;
    # otherwise fall back to a generic distribution.
    fixture_id = _fixture_id_for_config(config)
    if fixture_id is not None:
        _cfg, strategy = build_fixture(fixture_id)
    else:
        strategy = _fallback_strategy(config.starting_street)

    final_report = _fabricate_memory_report(
        iterations=iters_done,
        starting_street_name=_starting_street_name(config),
        wallclock_per_iter_sec=((effective_latency / 1000.0) / max(1, iterations)),
    )

    # Game value: hand-crafted constant per starting street (mock).
    game_value_table = {
        Street.PREFLOP: 0.0,
        Street.FLOP: 0.063,
        Street.TURN: 0.045,
        Street.RIVER: 0.021,
    }
    game_value = game_value_table.get(config.starting_street, 0.0)

    return HUNLSolveResult(
        average_strategy=strategy,
        exploitability_history=history,
        game_value=game_value,
        iterations=iters_done,
        backend="python-mock",
        memory_report=final_report,
    )


def list_fixture_presets() -> list[FixturePreset]:
    """Return the 12 fixture presets' metadata.

    Used by the UI's preset-dropdown render path
    (Agent A's ``views/spot_input.py``).
    """
    return list(FIXTURE_PRESETS)


def load_fixture(preset_id: str) -> HUNLConfig:
    """Materialize a preset id into a real ``HUNLConfig``.

    Raises ``KeyError`` if ``preset_id`` is not one of the 12 known IDs.
    """
    config, _strategy = build_fixture(preset_id)
    return config


def fixture_strategy(preset_id: str) -> dict[str, list[float]]:
    """Return the hand-crafted strategy for a preset.

    Test helper; the public mock API exposes strategies only via
    ``mock_solve(...).average_strategy``.
    """
    _config, strategy = build_fixture(preset_id)
    return strategy


__all__ = [
    "ACTION_LABELS",
    "FIXTURE_PRESETS",
    "FixturePreset",
    "_CANCEL_FLAG",
    "fixture_strategy",
    "list_fixture_presets",
    "load_fixture",
    "mock_solve",
    "read_latest_progress",
    "reset_progress_buffer",
]
