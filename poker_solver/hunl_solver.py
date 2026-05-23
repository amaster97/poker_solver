"""HUNL postflop solver orchestration (Python reference tier — PR 5).

Wires together PR 3's `HUNLPoker` tree builder, PR 4's optional
`AbstractionTables` card abstraction, PR 1's `DCFRSolver`, and PR 5's
`MemoryProbe` into the **first end-to-end HUNL postflop solve** shipped by
this repo. Exports:

- `solve_hunl_postflop(config, abstraction=None, iterations=50_000, ...)`
- `HUNLSolveResult` — a frozen dataclass that subclasses `SolveResult` and
  carries an extra `memory_report: MemoryReport`. The subclass form is
  locked per PR 5 spec consistency review N7 (PR 9's `PreflopSolveResult`
  extends `HUNLSolveResult`; PR 11 depends on `isinstance(result, SolveResult)`).

The function is a thin orchestrator on top of `DCFRSolver` — `dcfr.py` is
frozen per PR 5 spec §6 ("DCFRSolver remains unchanged"). The memory probe
introspects from outside via `solver.infosets`; we never reach into the CFR
recursion.

Hyperparameters are locked at α=1.5 / β=0 / γ=2.0 (Brown & Sandholm 2019,
the paper's recommended default; PLAN.md lock). PR 5 does NOT expose
`--alpha` / `--beta` / `--gamma` CLI flags; `dcfr_kwargs` is reserved for
future overrides.

Architecturally inspired by `noambrown_poker_solver` (MIT,
https://github.com/noambrown/poker_solver) two-tier solver orchestration;
no code copied.

Failure modes are caught and reported:
- Preflop config → `ValueError` pointing at PR 9.
- Board length mismatch / rake → `ValueError`.
- Memory budget exceeded → `MemoryError` whose `args[1]` is the partial
  `MemoryReport` (callable code can `except MemoryError as e:
  report = e.args[1]` to inspect what got allocated).
"""

from __future__ import annotations

import contextlib
import warnings
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from poker_solver.abstraction.buckets import AbstractionRef, AbstractionTables
from poker_solver.dcfr import DCFRSolver
from poker_solver.hunl import HUNLConfig, HUNLPoker, Street
from poker_solver.profiler.memory import MemoryProbe, MemoryReport
from poker_solver.solver import SolveResult, exploitability

# PR 10b: progress-callback type alias. Callers (the UI worker) pass a
# callable that fires once per ``log_every`` chunk during the solve loop.
# Signature: ``(iteration_count, exploitability_mBB_per_pot, memory_report)``.
# The callback runs on the solver thread; callers must be thread-safe.
OnProgressFn = Callable[[int, float, MemoryReport], None]

# PR 10b: cancellation-flag predicate. Callers pass a callable returning
# True when the solve should abort. Checked between DCFR chunks (snapshot
# boundary granularity). Returning True causes the loop to break and the
# function returns a partial ``HUNLSolveResult`` with the iteration count
# reflecting how far the solver got before stopping.
ShouldStopFn = Callable[[], bool]


@dataclass
class HUNLSolveResult(SolveResult):
    """SolveResult plus a per-street memory breakdown.

    Subclasses `SolveResult` so PR 9's `PreflopSolveResult` (which extends
    this class) and PR 11's library mode (which uses
    `isinstance(result, SolveResult)`) compose cleanly. Locked per PR 5
    spec §14 #3 + consistency review N7.

    Inherits `SolveResult`'s mutability (the parent is a non-frozen
    dataclass; Python disallows frozen subclassing of non-frozen parents).
    Treat this as if it were immutable — mutation post-construction is
    undefined.
    """

    # ``memory_report`` has no sensible default for a successful solve; the
    # constructor requires it. The `default=None` sentinel + `__post_init__`
    # check enforces "non-None at construction" while keeping the field
    # signature compatible with the parent's defaulted fields.
    memory_report: MemoryReport = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.memory_report is None:
            raise ValueError(
                "HUNLSolveResult requires a non-None memory_report; pass one "
                "constructed by MemoryProbe.snapshot()."
            )


# Cross-agent contract defaults: `iterations=50_000` and
# `memory_budget_gb=14.0` are LOCKED by the brief, overriding the spec §5
# shorthand `iterations: int = 10_000`. Future spec-editors: don't drift.
_DEFAULT_ITERATIONS: int = 50_000
_DEFAULT_MEMORY_BUDGET_GB: float = 14.0


def solve_hunl_postflop(
    config: HUNLConfig,
    abstraction: AbstractionTables | None = None,
    iterations: int = _DEFAULT_ITERATIONS,
    target_exploitability: float | None = None,
    memory_budget_gb: float = _DEFAULT_MEMORY_BUDGET_GB,
    *,
    log_every: int | None = None,
    seed: int | None = None,
    dcfr_kwargs: dict[str, Any] | None = None,
    on_progress: OnProgressFn | None = None,
    should_stop: ShouldStopFn | None = None,
    locked_strategies: Mapping[str, Sequence[float]] | None = None,
) -> HUNLSolveResult:
    """First end-to-end HUNL postflop solver in the Python reference tier.

    Args:
        config: `HUNLConfig` with `starting_street >= Street.FLOP` and a
            populated `initial_board`. Preflop configs raise `ValueError`.
        abstraction: Optional `AbstractionTables` artifact from PR 4. If
            None, the solver runs in lossless mode; a `UserWarning` is
            emitted for flop/turn starts where lossless trees are large.
        iterations: Hard cap on DCFR iterations. Default 50,000 per the
            cross-agent contract.
        target_exploitability: If set, early-exit when reached (computed
            at every `log_every` chunk; if `log_every is None`, no
            early-exit).
        memory_budget_gb: Hard ceiling for total memory (solver arrays +
            abstraction table + overhead). Exceeding triggers a
            `MemoryError` whose `args[1]` is the partial `MemoryReport`.
            Default 14.0 per PLAN.md card-abstraction commitment.
        log_every: When set, snapshot memory + exploitability between
            chunks of this size. Default None (one snapshot at end).

            WARNING: each per-chunk exploitability call walks the full
            game tree twice (best-response per player). On large flop
            subgames this can be minutes per call — a 10k-iter solve with
            ``log_every=100`` pays this cost ~100 times. Prefer the default
            (single end-of-solve summary) unless a convergence plot is
            required, or pair with a coarse abstraction.
        seed: Reserved for deterministic re-runs. Threads through to DCFR.
        dcfr_kwargs: Reserved for future DCFR hyperparameter overrides; in
            PR 5 we pin α/β/γ at PLAN.md defaults.
        on_progress: Optional callback fired once per ``log_every`` chunk
            with ``(iteration_count, exploitability_mBB_per_pot, memory_report)``.
            Used by the UI worker (PR 10b) to stream live progress without
            requiring a separate polling buffer. Requires ``log_every`` to
            be set; ignored otherwise. The callback runs on the solver
            thread.
        should_stop: Optional predicate polled at chunk boundaries. When it
            returns True the solver exits cleanly and returns a partial
            ``HUNLSolveResult`` with ``iterations`` reflecting how far the
            solve progressed. Used by the UI worker for cooperative
            cancellation (PR 10b).

    Returns:
        A frozen `HUNLSolveResult` with `average_strategy`,
        `exploitability_history`, and `memory_report`.

    Raises:
        ValueError: starting_street == PREFLOP (deferred to PR 9); board
            length mismatch; non-zero rake; invalid abstraction shape.
        MemoryError: total memory exceeds `memory_budget_gb`. The
            exception's `args[1]` is the partial `MemoryReport`.
    """
    _validate_postflop_config(config)
    if abstraction is not None:
        _validate_abstraction(abstraction)
    elif config.starting_street in (Street.FLOP, Street.TURN):
        warnings.warn(
            (
                f"solve_hunl_postflop called with abstraction=None and "
                f"starting_street={config.starting_street.name}; lossless "
                "flop/turn trees can use a lot of memory. Pass an "
                "AbstractionTables artifact (PR 4) for production-scale "
                "solves."
            ),
            UserWarning,
            stacklevel=2,
        )

    effective_config = _attach_abstraction(config, abstraction)
    game = HUNLPoker(effective_config)

    extra_kwargs: dict[str, Any] = dict(dcfr_kwargs or {})
    if seed is not None and "seed" not in extra_kwargs:
        extra_kwargs["seed"] = seed
    # v1.4 node-locking: thread `locked_strategies` into the DCFR solver.
    # Empty/`None` is bit-identical to v1.3 (the dict is frozen empty and
    # the lock-check fast-path returns immediately on every infoset visit).
    if locked_strategies is not None and len(locked_strategies) > 0:
        extra_kwargs["locked_strategies"] = locked_strategies
    solver = DCFRSolver(game, **extra_kwargs)
    probe = MemoryProbe(solver, include_abstraction=abstraction)

    history, report = _run_with_probe(
        solver=solver,
        probe=probe,
        iterations=iterations,
        log_every=log_every,
        target_exploitability=target_exploitability,
        memory_budget_gb=memory_budget_gb,
        game=game,
        on_progress=on_progress,
        should_stop=should_stop,
    )

    avg = solver.average_strategy()
    if log_every is None and avg and iterations > 0:
        # Single end-of-solve summary: compute exploitability once at the
        # end (matches spec §14 #6 "no progress bar" + Stage D).
        # Guard: skip when iterations=0 (no solve happened, walking the
        # full tree on an unconverged/empty strategy would hang on
        # lossless flop). Guard: skip when avg is empty (no infosets
        # touched). Audit fix per PR 5 review.
        history.append(exploitability(game, avg))

    game_value = _game_value(game, avg) if avg else 0.0

    return HUNLSolveResult(
        average_strategy=avg,
        exploitability_history=history,
        game_value=game_value,
        iterations=solver.iteration,
        backend="python",
        memory_report=report,
    )


def _validate_postflop_config(config: HUNLConfig) -> None:
    """Stage A — reject configs PR 5 cannot handle (preflop, rake, mismatch).

    PR 5 is postflop-only; preflop solver lands in PR 9. The check is on
    `starting_street`, NOT on stack depth: a 15-BB short stack with a
    flop start is still routed through PR 5 (push/fold short-circuit only
    fires for preflop-start games per `solver.solve()`).
    """
    if config.starting_street == Street.PREFLOP:
        raise ValueError(
            "solve_hunl_postflop is postflop-only; preflop solver lands in "
            "PR 9. Use Street.FLOP / TURN / RIVER and supply initial_board."
        )
    if config.starting_street == Street.SHOWDOWN:
        raise ValueError(
            "solve_hunl_postflop cannot start from SHOWDOWN (no decisions to make)."
        )
    required_board = {Street.FLOP: 3, Street.TURN: 4, Street.RIVER: 5}.get(
        config.starting_street
    )
    if required_board is None:
        raise ValueError(f"unsupported starting_street: {config.starting_street!r}")
    if len(config.initial_board) != required_board:
        raise ValueError(
            f"initial_board has {len(config.initial_board)} cards but "
            f"starting_street={config.starting_street.name} requires "
            f"{required_board}."
        )
    if config.rake_rate != 0.0 or config.rake_cap != 0:
        # HUNLConfig.__post_init__ already enforces rake==0 for PR 3, but
        # we re-check defensively: PR 5 inherits the assertion and
        # surfaces it as a ValueError (vs the AssertionError) so the CLI
        # catches it cleanly with the user-facing error path.
        raise ValueError(
            "PR 5 does not support rake; rake lands in PR 9. Set "
            "rake_rate=0.0 and rake_cap=0."
        )


def _validate_abstraction(abstraction: AbstractionTables) -> None:
    """Sanity-check the abstraction shape before constructing the game."""
    if not isinstance(abstraction, AbstractionTables):
        raise ValueError(
            f"abstraction must be an AbstractionTables instance, got "
            f"{type(abstraction).__name__!r}."
        )
    bucket_counts = abstraction.metadata.get("bucket_counts")
    if bucket_counts is None:
        raise ValueError(
            "abstraction metadata is missing 'bucket_counts'; not a valid "
            "PR 4 artifact."
        )
    # ``bucket_counts`` is a list (JSON round-trip) or tuple of 3 ints
    # (flop, turn, river) per PR 4 spec.
    if not isinstance(bucket_counts, (list, tuple)) or len(bucket_counts) != 3:
        raise ValueError(
            f"abstraction metadata['bucket_counts'] must be length 3 "
            f"(flop, turn, river); got {bucket_counts!r}."
        )


def _attach_abstraction(
    config: HUNLConfig, abstraction: AbstractionTables | None
) -> HUNLConfig:
    """Stage B — attach the abstraction to the config via an `AbstractionRef`.

    `HUNLConfig.abstraction` is typed `AbstractionRef | None` (PR 4 added
    the field per consistency review v2). The runtime resolves the ref to
    the loaded tables via `resolve_abstraction_ref` (LRU-cached). For
    in-memory `AbstractionTables` artifacts (tests, library callers that
    built the tables programmatically without writing them to a `.npz`),
    we prime a side-channel registry so the resolver short-circuits to
    the in-memory object instead of reading disk.
    """
    if abstraction is None:
        return config

    source_path = abstraction.source_path
    version = str(abstraction.metadata.get("version", "in-memory"))
    # In-memory artifact (no `.npz` round-trip) → synthesize a stable key
    # from object identity and prime the resolver shim; otherwise use the
    # on-disk path.
    key = f"in-memory:{id(abstraction):x}" if source_path is None else str(source_path)
    ref = AbstractionRef(source_path=key, version=version)
    _register_in_memory_abstraction(key, version, abstraction)
    return replace(config, abstraction=ref)


# ---------------------------------------------------------------------------
# In-memory abstraction cache (test/library helper).
# ---------------------------------------------------------------------------

_IN_MEMORY_ABSTRACTIONS: dict[tuple[str, str], AbstractionTables] = {}


def _register_in_memory_abstraction(
    key: str, version: str, tables: AbstractionTables
) -> None:
    """Register an in-memory `AbstractionTables` for resolver short-circuit.

    `resolve_abstraction_ref(ref)` calls `_cached_load(source_path, version)`
    which reads the `.npz` from disk. For in-memory artifacts (tests +
    library callers that built the tables programmatically), we monkey-patch
    `_cached_load` once to consult this registry first.
    """
    _IN_MEMORY_ABSTRACTIONS[(key, version)] = tables
    _install_in_memory_resolver_shim()


_resolver_shim_installed: bool = False


def _install_in_memory_resolver_shim() -> None:
    """Install the in-memory resolver shim exactly once per process."""
    global _resolver_shim_installed
    if _resolver_shim_installed:
        return
    from poker_solver.abstraction import buckets as _buckets

    original = _buckets._cached_load

    def _shimmed_cached_load(source_path: str, version: str) -> AbstractionTables:
        tables = _IN_MEMORY_ABSTRACTIONS.get((source_path, version))
        if tables is not None:
            return tables
        return original(source_path, version)

    _buckets._cached_load = _shimmed_cached_load  # type: ignore[assignment]
    # `resolve_abstraction_ref` closes over `_cached_load` at module load
    # time; re-bind it to consult the shim.
    _buckets.resolve_abstraction_ref = lambda ref: _buckets._cached_load(
        ref.source_path, ref.version
    )
    _resolver_shim_installed = True


# ---------------------------------------------------------------------------
# Stage C — chunked DCFR with memory + exploitability checks.
# ---------------------------------------------------------------------------


def _run_with_probe(
    *,
    solver: DCFRSolver,
    probe: MemoryProbe,
    iterations: int,
    log_every: int | None,
    target_exploitability: float | None,
    memory_budget_gb: float,
    game: HUNLPoker,
    on_progress: OnProgressFn | None = None,
    should_stop: ShouldStopFn | None = None,
) -> tuple[list[float], MemoryReport]:
    """Run DCFR in chunks; snapshot memory + check budgets between chunks.

    Returns `(exploitability_history, final_memory_report)`.

    Snapshot policy (spec §4 Stage C):
    - When `log_every is None`, we still snapshot once at end so callers
      get a `MemoryReport`. We do NOT compute exploitability per-chunk.
    - When `log_every` is set, snapshot + record exploitability between
      each chunk; check `target_exploitability` for early-exit.

    Memory budget enforcement (spec §7.7):
    - After each snapshot we compare `report.total_gb` against
      `memory_budget_gb`; over budget → `MemoryError(..., report)`. The
      report is attached as `args[1]` so callers can introspect.
    """
    history: list[float] = []
    if iterations <= 0:
        # Nothing to do; still snapshot so the caller gets a report.
        return history, probe.snapshot()

    chunk_size = log_every if log_every is not None else iterations
    chunk_size = max(1, min(chunk_size, iterations))

    done = 0
    final_report: MemoryReport | None = None
    while done < iterations:
        # PR 10b: cooperative cancellation between chunks. Polled here
        # rather than inside DCFRSolver.solve() so we exit on a clean
        # iteration boundary (the average strategy stays consistent).
        if should_stop is not None and should_stop():
            # Take a final snapshot so the caller still gets a MemoryReport.
            final_report = probe.snapshot()
            break

        step = min(chunk_size, iterations - done)
        solver.solve(step)
        done += step

        # Snapshot between chunks. The probe walks `solver.infosets`; the
        # cost is O(num_infosets) and is amortized via `log_every`.
        final_report = probe.snapshot()
        if final_report.total_gb > memory_budget_gb:
            river_ratio = final_report.river_ratio
            raise MemoryError(
                f"Memory budget exceeded: {final_report.total_gb:.3f} GB > "
                f"{memory_budget_gb} GB after {done} iterations. River "
                f"layer: {river_ratio:.1%}. Consider tightening the "
                f"abstraction (smaller bucket counts via "
                f"`precompute-abstraction --bucket-counts ...`) or "
                f"restricting --bet-sizes. Partial report attached as "
                f"args[1].",
                final_report,
            )

        if log_every is not None:
            expl = exploitability(game, solver.average_strategy())
            history.append(expl)
            # PR 10b: fire the on_progress callback with the live snapshot
            # so the UI worker can update its expl_history + chart between
            # chunks without polling a separate buffer. We suppress any
            # exception raised inside the callback so a misbehaving UI
            # client cannot crash the solver mid-iteration; the UI is
            # responsible for catching its own bugs.
            if on_progress is not None:
                with contextlib.suppress(Exception):
                    on_progress(done, expl, final_report)
            if target_exploitability is not None and expl <= target_exploitability:
                # Early-exit on convergence target reached.
                break

    # Loop always snapshots at least once because `iterations > 0` here.
    assert final_report is not None  # nosec: invariant; helps mypy
    return history, final_report


def _game_value(game: HUNLPoker, strategy: dict[str, list[float]]) -> float:
    """Player-0 expected value under `strategy` (delegates to solver.py).

    Wrapping the underlying `_expected_value` walker here keeps the public
    surface tight; the heavy lifting lives in `solver.py` (already
    exercised by Kuhn / Leduc).
    """
    import numpy as np

    from poker_solver.solver import _expected_value

    ev = _expected_value(
        game,
        strategy,
        game.initial_state(),
        np.ones(game.num_players + 1, dtype=np.float64),
    )
    return float(ev[0])


__all__ = [
    "HUNLSolveResult",
    "OnProgressFn",
    "ShouldStopFn",
    "solve_hunl_postflop",
]
