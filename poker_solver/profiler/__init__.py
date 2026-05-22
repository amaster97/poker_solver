"""Memory profiler for `DCFRSolver` (PR 5).

Public surface re-exported here for convenience. The implementation lives
in `poker_solver.profiler.memory`.

Example usage::

    from poker_solver.profiler import MemoryProbe
    probe = MemoryProbe(solver, include_abstraction=tables)
    # ... run DCFR iterations ...
    report = probe.snapshot()
    if report.total_gb > 14.0:
        raise MemoryError("budget exceeded", report)
    print(f"river ratio: {report.river_ratio:.1%}")
"""

from poker_solver.profiler.memory import (
    MemoryProbe,
    MemoryReport,
    StreetMemoryEntry,
    _parse_street_from_key,
)

__all__ = [
    "MemoryProbe",
    "MemoryReport",
    "StreetMemoryEntry",
    "_parse_street_from_key",
]
