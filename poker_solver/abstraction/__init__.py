"""Card abstraction package: equity features, EMD clustering, bucket lookup.

Public surface re-exported from sub-modules. Importing this package will
import Agent A's `equity_features` + `emd_clustering` modules if they are
present; the bucket / persistence / orchestrator code in `buckets` and
`precompute` is owned by Agent B and is always importable.
"""

from poker_solver.abstraction.buckets import (
    SCHEMA_VERSION,
    AbstractionRef,
    AbstractionTables,
    load_abstraction,
    lookup_bucket,
    resolve_abstraction_ref,
    save_abstraction,
)
from poker_solver.abstraction.emd_clustering import (
    KMeansResult,
    batch_emd,
    emd_1d,
    kmeans_emd,
)
from poker_solver.abstraction.equity_features import (
    canonicalize_for_suit_iso,
    compute_flop_features,
    compute_river_features,
    compute_turn_features,
    equity_distribution,
)
from poker_solver.abstraction.precompute import build_abstraction

__all__ = [
    "AbstractionRef",
    "AbstractionTables",
    "KMeansResult",
    "SCHEMA_VERSION",
    "batch_emd",
    "build_abstraction",
    "canonicalize_for_suit_iso",
    "compute_flop_features",
    "compute_river_features",
    "compute_turn_features",
    "emd_1d",
    "equity_distribution",
    "kmeans_emd",
    "load_abstraction",
    "lookup_bucket",
    "resolve_abstraction_ref",
    "save_abstraction",
]
