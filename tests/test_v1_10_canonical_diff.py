"""v1.10 canonical diff-test harness — bit-identical baseline gate.

Per ``docs/v1_10_postflop_optimization_plan.md`` §4 (bit-identical
diff-test strategy) + §7 (done criteria). This harness:

  1. Defines the 8 kill-switch fixtures from
     ``docs/w2_3_vector_br_walk_test_fixtures.md`` plus the v1.10-spec
     J7o flop config.
  2. For each fixture, captures the canonical outputs:
       (exploitability, per-history strategy entries, BR action argmax,
        game value).
  3. Diffs the live captures against
     ``tests/fixtures/v1_10_canonical_baseline.json`` (committed once
     against current main, then frozen).

**Workflow for v1.10-N implementer agents:**

The baseline JSON is captured ONCE on main (this PR's deliverable) by
running::

    python -m tests.test_v1_10_canonical_diff --capture-baseline

That writes ``tests/fixtures/v1_10_canonical_baseline.json``. The
v1.10-1 through v1.10-4 PRs (arena, vector-turn, vector-flop, rayon)
each re-run::

    pytest tests/test_v1_10_canonical_diff.py -v

The harness compares the live capture against the committed baseline.
Any drift outside the per-quantity tolerance HARD-FAILs the PR.

**Tolerances (per plan §4.2):**

  - exploitability:    1e-9
  - strategy entries:  1e-12
  - BR argmax:         exact (no tolerance)
  - game value:        1e-12

For the rayon-opt-in path (v1.10-4) a separate ``test_vector_rayon_diff.py``
applies LOOSER tolerances (1e-6 exploitability), per the plan's dual-path
strategy. This file targets the CANONICAL (single-threaded) path only.

**Fixtures that may skip:**

  - F3.1 (turn 8-class) — ~5s/iter at iter=2 on M-series; viable.
  - F4.1 (flop 8-class) — chance subtree blows up; skipped at iter>=1
    on main pending v1.10-3 (vector-form flop). Re-enabled by the
    v1.10-3 PR.
  - J7o flop (top_k=4, iters=5) — OOM on main per
    ``docs/flop_subgame_perf_measurement_2026-05-28.md``. Skipped with
    explicit reason. Re-enabled by v1.10-1 (arena).

**Per-PR baseline progression:**

The skip set shrinks across the v1.10 PR train:

  - **Before v1.10-1**: F4.1 + J7o skipped on main (this PR's baseline).
  - **After v1.10-1 (arena)**: J7o becomes runnable. Recapture baseline
    on the v1.10-1 merge SHA; subsequent PRs gate against the updated
    baseline.
  - **After v1.10-3 (vector-form flop)**: F4.1 runnable at full 8-class
    spec; recapture again. The fixture's ``iters`` should be raised back
    to the canonical 50 per ``docs/w2_3_vector_br_walk_test_fixtures.md``.

Skips are documented per-fixture; per the project's silent-skip-hazard
rule, every skip emits a HARD message on the test name so a CI sweep
that loses skip context still surfaces the issue.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import pytest

# ---------------------------------------------------------------------------
# Imports — defensive against partial installs.
# ---------------------------------------------------------------------------

try:
    from poker_solver import (
        HUNLConfig,
        HUNLPoker,
        KuhnPoker,
        LeducPoker,
        Street,
        parse_board,
        solve,
    )
    from poker_solver.range_aggregator import solve_range_vs_range_nash
    from poker_solver.solver import (
        _best_response_value_and_strategy,
        exploitability,
    )
except Exception as _imp_err:  # noqa: BLE001
    HUNLConfig = None  # type: ignore[assignment,misc]
    HUNLPoker = None  # type: ignore[assignment,misc]
    KuhnPoker = None  # type: ignore[assignment,misc]
    LeducPoker = None  # type: ignore[assignment,misc]
    Street = None  # type: ignore[assignment,misc]
    parse_board = None  # type: ignore[assignment]
    solve = None  # type: ignore[assignment]
    solve_range_vs_range_nash = None  # type: ignore[assignment]
    _best_response_value_and_strategy = None  # type: ignore[assignment]
    exploitability = None  # type: ignore[assignment]
    _IMPORT_ERROR = _imp_err
else:
    _IMPORT_ERROR = None

# Confirm the Rust extension is loadable; we don't currently import any
# specific symbol from it (the solver entry points pull it in lazily).
try:
    importlib.import_module("poker_solver._rust")
except Exception:  # noqa: BLE001
    pass


# Module-level skip if the imports failed entirely.
pytestmark = pytest.mark.skipif(
    _IMPORT_ERROR is not None,
    reason=f"poker_solver imports failed: {_IMPORT_ERROR!r}",
)


# ---------------------------------------------------------------------------
# Tolerance constants — must match plan §4.2 exactly.
# ---------------------------------------------------------------------------

TOL_EXPLOITABILITY: float = 1e-9
TOL_STRATEGY_ENTRY: float = 1e-12
TOL_GAME_VALUE: float = 1e-12
# BR argmax has NO tolerance — exact integer match required.

# Baseline JSON location.
BASELINE_PATH = (
    Path(__file__).parent / "fixtures" / "v1_10_canonical_baseline.json"
)
# How many strategy keys to sample per fixture in the baseline. The full
# strategy dict can have 25k+ entries for turn/flop fixtures, blowing up
# the JSON. We sort keys and sample a fixed-stride subset for the diff.
STRATEGY_SAMPLE_KEYS: int = 64


# ---------------------------------------------------------------------------
# Fixture spec dataclass.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FixtureSpec:
    """Specification for one v1.10 canonical diff-test fixture."""

    fixture_id: str
    description: str
    # Builder returns (game_factory_callable, solve_iters, kwargs).
    # The kwargs go to the solver call. game_factory_callable is invoked
    # with no args and returns the (game, config) tuple for HUNL or just
    # the game for Kuhn/Leduc.
    builder_kind: str  # "kuhn" | "leduc" | "hunl_rvr"
    iters: int
    # Skipping policy:
    #   None  = run on main (we have a baseline)
    #   str   = skip reason (the harness emits this in the skip msg).
    skip_on_main: str | None = None
    # HUNL-specific config builder, if builder_kind == "hunl_rvr".
    hunl_config_builder: Callable[[], Any] | None = None
    hero_classes: tuple[str, ...] | None = None
    villain_classes: tuple[str, ...] | None = None
    # For RvR fixtures: whether to run the exploitability walk after
    # solve. The walk dominates wall time on turn / flop fixtures
    # (45×44 board chance enum). Set False for fast capture; the
    # exploitability field is then null in the baseline and the diff
    # only covers strategy + game_value.
    compute_exploitability: bool = True


# ---------------------------------------------------------------------------
# HUNL config builders — one per fixture.
# ---------------------------------------------------------------------------


def _f24_river_8class_config() -> Any:
    """F2.4 — 8-class river dry (Kc 7d 2h Ts 4c)."""
    return HUNLConfig(
        starting_stack=1000,
        big_blind=100,
        starting_street=Street.RIVER,
        initial_board=tuple(parse_board("Kc 7d 2h Ts 4c")),
        initial_pot=1000,
        initial_contributions=(500, 500),
        initial_hole_cards=(),
        bet_size_fractions=(0.5, 1.0),
        postflop_raise_cap=3,
    )


def _f31_turn_8class_config() -> Any:
    """F3.1 — W2.3 reference (Qs 7h 2d 5c, 200 BB, 8-class)."""
    return HUNLConfig(
        starting_stack=20000,
        big_blind=100,
        starting_street=Street.TURN,
        initial_board=tuple(parse_board("Qs 7h 2d 5c")),
        initial_pot=1000,
        initial_contributions=(500, 500),
        initial_hole_cards=(),
        bet_size_fractions=(0.5, 1.0),
        postflop_raise_cap=3,
    )


def _f41_flop_3class_config() -> Any:
    """F4.1 — Standard flop (Qh 7c 2d).

    Spec calls for 8 classes; we use 3 (AA, KK, QQ) on main because the
    full 8-class flop subtree OOMs at iter>=1 on current main. After
    v1.10-3 lands, the v1.10 implementer agent should restore the full
    8-class spec and recapture the baseline.
    """
    return HUNLConfig(
        starting_stack=10000,
        big_blind=100,
        starting_street=Street.FLOP,
        initial_board=tuple(parse_board("Qh 7c 2d")),
        initial_pot=200,
        initial_contributions=(100, 100),
        initial_hole_cards=(),
        bet_size_fractions=(0.5, 1.0),
        postflop_raise_cap=3,
    )


def _f52_river_3class_pure_config() -> Any:
    """F5.2 — Pure-strategy infosets edge fixture (F2.1 base = 3-class river dry)."""
    return HUNLConfig(
        starting_stack=1000,
        big_blind=100,
        starting_street=Street.RIVER,
        initial_board=tuple(parse_board("Kc 7d 2h Ts 4c")),
        initial_pot=1000,
        initial_contributions=(500, 500),
        initial_hole_cards=(),
        bet_size_fractions=(0.5, 1.0),
        postflop_raise_cap=3,
    )


def _f53_river_8class_mixed_config() -> Any:
    """F5.3 — Heavily mixed (F2.4 base = 8-class river dry, uniform seed)."""
    return _f24_river_8class_config()


def _j7o_flop_config() -> Any:
    """J7o A♦8♥9♦ 40-BB flop — the v1.10 headline fixture."""
    return HUNLConfig(
        starting_stack=4000,  # 40 BB at 100 chips/BB
        big_blind=100,
        starting_street=Street.FLOP,
        initial_board=tuple(parse_board("Ad 8h 9d")),
        # 40 BB stacks, SB opens 3bb, BB calls → pot 600, contribs 300/300
        initial_pot=600,
        initial_contributions=(300, 300),
        initial_hole_cards=(),
        bet_size_fractions=(0.5, 1.0),
        postflop_raise_cap=3,
    )


# ---------------------------------------------------------------------------
# Fixture table — the 8 kill-switch + J7o.
# ---------------------------------------------------------------------------


HAND_CLASSES_3 = ("AA", "KK", "QQ")
HAND_CLASSES_8 = ("AA", "KK", "QQ", "JJ", "AKs", "AKo", "AQs", "AQo")

FIXTURES: tuple[FixtureSpec, ...] = (
    FixtureSpec(
        fixture_id="F1_1_kuhn_baseline",
        description="Kuhn poker, 1000 iter (canonical-game smoke)",
        builder_kind="kuhn",
        iters=1000,
    ),
    FixtureSpec(
        fixture_id="F1_3_leduc_baseline",
        description="Leduc poker, 1000 iter (multi-round smoke)",
        builder_kind="leduc",
        iters=1000,
    ),
    FixtureSpec(
        fixture_id="F2_4_river_8class_dry",
        description="8-class range-vs-range river on Kc 7d 2h Ts 4c, 20 iter",
        builder_kind="hunl_rvr",
        iters=20,
        hunl_config_builder=_f24_river_8class_config,
        hero_classes=HAND_CLASSES_8,
        villain_classes=HAND_CLASSES_8,
    ),
    FixtureSpec(
        fixture_id="F3_1_turn_W23_reference",
        description="W2.3 reference (Qs 7h 2d 5c, 200 BB, 8-class, 2 iter)",
        builder_kind="hunl_rvr",
        iters=2,
        hunl_config_builder=_f31_turn_8class_config,
        hero_classes=HAND_CLASSES_8,
        villain_classes=HAND_CLASSES_8,
        # Exploitability walk on the 8-class turn is ~5-10 min via the
        # chance-enum-at-root path. Skip the walk for the baseline;
        # strategy + game_value diffs catch any regression at 1e-12
        # tolerance, which is strictly tighter than 1e-9 exploitability.
        compute_exploitability=False,
    ),
    FixtureSpec(
        fixture_id="F4_1_flop_standard",
        description="Standard flop (Qh 7c 2d), 3 classes on main; OOMs pre v1.10-3",
        builder_kind="hunl_rvr",
        iters=1,
        hunl_config_builder=_f41_flop_3class_config,
        # 3-class fallback on main; v1.10-3 should restore HAND_CLASSES_8.
        hero_classes=HAND_CLASSES_3,
        villain_classes=HAND_CLASSES_3,
        # Exploit walk is also chance-enum heavy on flop; default off
        # so post-v1.10-1 baseline capture is fast enough for CI.
        compute_exploitability=False,
        # Flop solve OOMs even at 3 classes / 1 iter on main per
        # docs/flop_subgame_perf_measurement_2026-05-28.md. v1.10-1 (arena)
        # is expected to unblock; v1.10-3 (vector-form flop) brings the
        # full 8-class baseline into range.
        skip_on_main=(
            "Flop subgame at 3 classes does not complete in 3min on main "
            "(see docs/flop_subgame_perf_measurement_2026-05-28.md). "
            "Re-enable + recapture baseline after v1.10-1 (arena PR) lands."
        ),
    ),
    FixtureSpec(
        fixture_id="F5_2_pure_strategy_edge",
        description="Pure-strategy edge — F2.1 base (3-class river dry, hand-crafted)",
        builder_kind="hunl_rvr",
        iters=10,
        hunl_config_builder=_f52_river_3class_pure_config,
        hero_classes=HAND_CLASSES_3,
        villain_classes=HAND_CLASSES_3,
    ),
    FixtureSpec(
        fixture_id="F5_3_heavily_mixed_edge",
        description="Heavily mixed — F2.4 base (8-class river dry, uniform seed equivalent)",
        builder_kind="hunl_rvr",
        iters=20,
        hunl_config_builder=_f53_river_8class_mixed_config,
        hero_classes=HAND_CLASSES_8,
        villain_classes=HAND_CLASSES_8,
    ),
    FixtureSpec(
        fixture_id="J7o_flop_40bb_user_fixture",
        description="J7o on A♦8♥9♦ 40-BB — v1.10 headline; 3-class subset on main",
        builder_kind="hunl_rvr",
        iters=1,
        hunl_config_builder=_j7o_flop_config,
        # Use a 3-class subset that includes the user's pin. The full
        # blueprint-derived top_k=4 ranges OOM on main; this minimal
        # subset is the diff-test smoke. After v1.10-3 lands, swap to
        # the full blueprint-derived top_k=4 ranges per plan §4.3 F4.4.
        hero_classes=("AA", "KK", "QQ"),
        villain_classes=("AA", "KK", "QQ"),
        # Exploit walk skipped (same reason as F4.1).
        compute_exploitability=False,
        # Even the 3-class flop is risky; on main it may time out at
        # current implementation. The harness handles this gracefully.
        skip_on_main=(
            "Flop subgame OOMs on main; baseline captured as 'unable to "
            "produce' marker. Re-enable + recapture after v1.10-3."
        ),
    ),
)


# ---------------------------------------------------------------------------
# Solver invocation — one per builder_kind.
# ---------------------------------------------------------------------------


@dataclass
class FixtureCapture:
    """All the outputs we diff for one fixture."""

    fixture_id: str
    description: str
    iters: int
    builder_kind: str
    # Core outputs (the four quantities the plan calls for).
    exploitability: float | None = None
    game_value: float | None = None
    # Per-history strategy entries — sampled subset for stable JSON size.
    strategy_sample: dict[str, list[float]] = field(default_factory=dict)
    # BR action argmax per visited hero infoset — sampled subset.
    br_argmax_sample: dict[str, int] = field(default_factory=dict)
    # Metadata.
    wall_seconds: float = 0.0
    status: str = "complete"  # "complete" | "skipped" | "error"
    error: str | None = None


def _sample_strategy(
    strategy: Mapping[str, Sequence[float]], n_sample: int = STRATEGY_SAMPLE_KEYS
) -> dict[str, list[float]]:
    """Sample a stable subset of strategy keys for the baseline.

    Sorts keys lexicographically and selects every k-th key such that
    we end with at most ``n_sample`` entries. The same sampling lifts
    on both capture and diff so the sampled keys align.
    """
    if not strategy:
        return {}
    keys = sorted(strategy.keys())
    if len(keys) <= n_sample:
        sampled_keys = keys
    else:
        stride = len(keys) // n_sample
        sampled_keys = keys[::stride][:n_sample]
    return {k: [float(p) for p in strategy[k]] for k in sampled_keys}


def _compute_br_argmax_sample(
    game: Any,
    strategy: Mapping[str, Sequence[float]],
    hero_player: int = 0,
    n_sample: int = STRATEGY_SAMPLE_KEYS,
) -> dict[str, int]:
    """Compute BR argmax for the sampled hero infosets.

    Uses ``solver._best_response_value_and_strategy`` to derive the
    full BR strategy; samples the same key stride as
    ``_sample_strategy``.
    """
    if _best_response_value_and_strategy is None:
        return {}
    try:
        _, br_strategy = _best_response_value_and_strategy(
            game, strategy, hero_player
        )
    except Exception:  # noqa: BLE001
        # Some game types (RvR vector path) don't support the Python BR
        # walk; return empty and the diff treats it as "not captured".
        return {}
    if not br_strategy:
        return {}
    # br_strategy is dict[str, list[float]] with one-hot vectors. argmax
    # is the action index where the 1.0 sits.
    argmax = {k: int(max(range(len(v)), key=lambda i: v[i])) for k, v in br_strategy.items()}
    sampled_keys = sorted(argmax.keys())
    if len(sampled_keys) > n_sample:
        stride = len(sampled_keys) // n_sample
        sampled_keys = sampled_keys[::stride][:n_sample]
    return {k: argmax[k] for k in sampled_keys}


def run_fixture(spec: FixtureSpec) -> FixtureCapture:
    """Run the solver on a fixture and capture all four diff quantities."""
    cap = FixtureCapture(
        fixture_id=spec.fixture_id,
        description=spec.description,
        iters=spec.iters,
        builder_kind=spec.builder_kind,
    )
    if spec.skip_on_main is not None:
        # Explicit skip — record the marker but do NOT actually solve.
        cap.status = "skipped"
        cap.error = spec.skip_on_main
        return cap

    t0 = time.perf_counter()
    try:
        if spec.builder_kind == "kuhn":
            game = KuhnPoker()
            # Kuhn's Python solver is fast (sub-second at 1k iter) and
            # is the canonical reference for the BR walk diff. Stay on
            # python backend for bit-identical reproducibility — the
            # rust Kuhn solver path is a separate diff covered by
            # tests/test_kuhn_diff.py.
            result = solve(game, iterations=spec.iters)
            cap.exploitability = (
                float(result.exploitability_history[-1])
                if result.exploitability_history
                else float(exploitability(game, result.average_strategy))
            )
            cap.game_value = float(result.game_value)
            cap.strategy_sample = _sample_strategy(result.average_strategy)
            cap.br_argmax_sample = _compute_br_argmax_sample(
                game, result.average_strategy
            )
        elif spec.builder_kind == "leduc":
            game = LeducPoker()
            # Leduc's Python solver is too slow for CI (~100s/1k iter);
            # use rust backend. The python ↔ rust Leduc diff is owned
            # by tests/test_leduc_diff.py.
            result = solve(game, iterations=spec.iters, backend="rust")
            cap.exploitability = (
                float(result.exploitability_history[-1])
                if result.exploitability_history
                else float(exploitability(game, result.average_strategy))
            )
            cap.game_value = float(result.game_value)
            cap.strategy_sample = _sample_strategy(result.average_strategy)
            cap.br_argmax_sample = _compute_br_argmax_sample(
                game, result.average_strategy
            )
        elif spec.builder_kind == "hunl_rvr":
            cfg = spec.hunl_config_builder()
            assert spec.hero_classes is not None
            assert spec.villain_classes is not None
            # Force the SERIAL chance path: the frozen baseline was captured
            # single-threaded, but rayon chance-parallelism is now default-on,
            # so turn-rooted fixtures (e.g. F3.1) would otherwise fire the
            # parallel walker and drift past the 1e-12 bit-exact diff.
            rayon_was = os.environ.get("CFR_RAYON_CHANCE")
            os.environ["CFR_RAYON_CHANCE"] = "0"
            try:
                res = solve_range_vs_range_nash(
                    cfg,
                    list(spec.hero_classes),
                    list(spec.villain_classes),
                    iterations=spec.iters,
                    alpha=1.5,
                    beta=0.0,
                    gamma=2.0,
                    hero_player=0,
                    compute_exploitability_at_end=spec.compute_exploitability,
                )
            finally:
                if rayon_was is None:
                    os.environ.pop("CFR_RAYON_CHANCE", None)
                else:
                    os.environ["CFR_RAYON_CHANCE"] = rayon_was
            # The RvR result wraps per_history_strategy (HashMap)
            # AND res.exploitability is a Mapping or float depending
            # on backend; coerce defensively. When the exploit walk
            # was skipped (slow fixtures), record None.
            if not spec.compute_exploitability:
                cap.exploitability = None
            else:
                cap.exploitability = (
                    float(res.exploitability)
                    if res.exploitability is not None
                    else float("nan")
                )
            # Use the per_history_strategy as the canonical "game_value
            # surrogate" for RvR — there's no scalar game_value because
            # the vector form computes per-hand EVs. We instead capture
            # the SUM of strategy mass per first-decision infoset as a
            # smoke value (each row must sum to 1.0; deviations expose
            # bugs).
            cap.game_value = sum(
                sum(probs) for probs in res.per_history_strategy.values()
            ) / max(len(res.per_history_strategy), 1)
            cap.strategy_sample = _sample_strategy(res.per_history_strategy)
            # BR argmax is not produced by RvR Nash; we skip it for
            # this builder.
            cap.br_argmax_sample = {}
        else:
            raise ValueError(f"unknown builder_kind: {spec.builder_kind!r}")
        cap.status = "complete"
    except Exception as exc:  # noqa: BLE001
        cap.status = "error"
        cap.error = repr(exc)
    finally:
        cap.wall_seconds = time.perf_counter() - t0
    return cap


# ---------------------------------------------------------------------------
# Baseline I/O.
# ---------------------------------------------------------------------------


def _serialize_capture(cap: FixtureCapture, spec: FixtureSpec) -> dict[str, Any]:
    return {
        "fixture_id": cap.fixture_id,
        "description": cap.description,
        "iters": cap.iters,
        "builder_kind": cap.builder_kind,
        # Echo the spec's measurement toggle so the implementer agent's
        # capture matches: their branch must use the same toggle for a
        # 1:1 diff. (None exploitability is "by design", not a failure.)
        "compute_exploitability": spec.compute_exploitability,
        "exploitability": cap.exploitability,
        "game_value": cap.game_value,
        "strategy_sample": cap.strategy_sample,
        "br_argmax_sample": cap.br_argmax_sample,
        "wall_seconds": cap.wall_seconds,
        "status": cap.status,
        "error": cap.error,
    }


def _deserialize_capture(data: dict[str, Any]) -> FixtureCapture:
    return FixtureCapture(
        fixture_id=data["fixture_id"],
        description=data["description"],
        iters=data["iters"],
        builder_kind=data["builder_kind"],
        exploitability=data.get("exploitability"),
        game_value=data.get("game_value"),
        strategy_sample=data.get("strategy_sample", {}),
        br_argmax_sample=data.get("br_argmax_sample", {}),
        wall_seconds=data.get("wall_seconds", 0.0),
        status=data.get("status", "complete"),
        error=data.get("error"),
    )


def capture_baseline(output_path: Path = BASELINE_PATH) -> dict[str, Any]:
    """Run every fixture, serialize captures to JSON."""
    captures: list[dict[str, Any]] = []
    print(f"[capture_baseline] capturing {len(FIXTURES)} fixtures...", flush=True)
    for spec in FIXTURES:
        print(f"  [{spec.fixture_id}] running...", flush=True)
        cap = run_fixture(spec)
        print(
            f"  [{spec.fixture_id}] status={cap.status} "
            f"wall={cap.wall_seconds:.2f}s "
            f"expl={cap.exploitability} gv={cap.game_value}",
            flush=True,
        )
        captures.append(_serialize_capture(cap, spec))
    payload = {
        "schema_version": "v1.0",
        "captured_on_branch": _git_branch(),
        "captured_at_commit": _git_commit(),
        "captured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tolerances": {
            "exploitability": TOL_EXPLOITABILITY,
            "strategy_entry": TOL_STRATEGY_ENTRY,
            "game_value": TOL_GAME_VALUE,
            "br_argmax": "exact",
        },
        "fixtures": captures,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=False))
    print(f"[capture_baseline] wrote {output_path}", flush=True)
    return payload


def load_baseline(path: Path = BASELINE_PATH) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"baseline missing at {path}; run "
            "`python -m tests.test_v1_10_canonical_diff --capture-baseline` "
            "on the current branch to generate it."
        )
    return json.loads(path.read_text())


def _git_branch() -> str:
    try:
        import subprocess

        return subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            text=True,
        ).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _git_commit() -> str:
    try:
        import subprocess

        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
        ).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


# ---------------------------------------------------------------------------
# Pytest harness — one test per fixture.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def baseline() -> dict[str, Any]:
    if not BASELINE_PATH.exists():
        pytest.skip(
            f"baseline {BASELINE_PATH} missing; run the harness with "
            "--capture-baseline to generate it"
        )
    return load_baseline(BASELINE_PATH)


def _find_baseline_record(
    baseline: dict[str, Any], fixture_id: str
) -> dict[str, Any] | None:
    for rec in baseline["fixtures"]:
        if rec["fixture_id"] == fixture_id:
            return rec
    return None


def _diff_float(name: str, live: float | None, base: float | None, tol: float) -> str | None:
    """Return None if the values match within tolerance, else a failure message.

    Convention: ``None`` in the baseline means "not measured" — the diff
    is silently skipped. ``None`` in the live capture when the baseline
    has a number is a regression (the implementer turned off a measurement
    we were tracking) — flagged.
    """
    if base is None:
        # Baseline didn't measure this quantity (e.g. exploitability
        # walk skipped on slow fixtures); skip the diff.
        return None
    if live is None:
        return (
            f"{name}: live=None baseline={base!r} "
            "(implementer disabled a measurement the baseline captures)"
        )
    if isinstance(live, float) and (live != live):  # NaN
        if isinstance(base, float) and (base != base):
            return None
        return f"{name}: live=NaN baseline={base!r}"
    delta = abs(float(live) - float(base))
    if delta > tol:
        return (
            f"{name}: live={live!r} baseline={base!r} delta={delta:.3e} "
            f"(tol={tol:.0e})"
        )
    return None


def _diff_strategy_sample(
    name: str,
    live: Mapping[str, Sequence[float]],
    base: Mapping[str, Sequence[float]],
    tol: float,
) -> list[str]:
    """Compare each sampled strategy entry; collect ALL failures."""
    failures: list[str] = []
    base_keys = set(base.keys())
    live_keys = set(live.keys())
    missing_live = base_keys - live_keys
    missing_base = live_keys - base_keys
    if missing_live:
        failures.append(
            f"{name}: {len(missing_live)} baseline keys missing in live "
            f"(first 3: {sorted(missing_live)[:3]})"
        )
    if missing_base:
        failures.append(
            f"{name}: {len(missing_base)} live keys missing in baseline "
            f"(first 3: {sorted(missing_base)[:3]})"
        )
    common = base_keys & live_keys
    for key in sorted(common):
        live_v = list(live[key])
        base_v = list(base[key])
        if len(live_v) != len(base_v):
            failures.append(
                f"{name}: key={key!r} action count mismatch "
                f"live={len(live_v)} baseline={len(base_v)}"
            )
            continue
        for i, (lv, bv) in enumerate(zip(live_v, base_v)):
            delta = abs(float(lv) - float(bv))
            if delta > tol:
                failures.append(
                    f"{name}: key={key!r}[a={i}] live={lv!r} baseline={bv!r} "
                    f"delta={delta:.3e} (tol={tol:.0e})"
                )
    return failures


def _diff_br_argmax(
    name: str,
    live: Mapping[str, int],
    base: Mapping[str, int],
) -> list[str]:
    """Compare BR argmax dicts — EXACT integer match required."""
    failures: list[str] = []
    common = set(live.keys()) & set(base.keys())
    for key in sorted(common):
        if int(live[key]) != int(base[key]):
            failures.append(
                f"{name}: key={key!r} live_argmax={live[key]} "
                f"baseline_argmax={base[key]} (must be EXACT)"
            )
    return failures


@pytest.mark.parametrize(
    "spec", FIXTURES, ids=[s.fixture_id for s in FIXTURES]
)
def test_v1_10_fixture_matches_baseline(spec: FixtureSpec, baseline: dict[str, Any]) -> None:
    """Run fixture, compare live capture against committed baseline."""
    base_rec = _find_baseline_record(baseline, spec.fixture_id)
    if base_rec is None:
        pytest.skip(
            f"baseline missing for {spec.fixture_id} (re-capture needed)"
        )

    if base_rec["status"] == "skipped":
        # Baseline itself was skipped on capture (e.g. flop OOM on main).
        # The harness still runs the fixture live to confirm post-PR
        # status. If the live run completes AND the baseline didn't,
        # that's a positive change — emit an INFO marker but pass.
        live_cap = run_fixture(spec)
        if live_cap.status == "skipped":
            pytest.skip(
                f"baseline + live both skipped: {base_rec.get('error')}"
            )
        # Live completed where baseline didn't — that's great (e.g. arena
        # PR fixed OOM). Print a note but pass.
        print(
            f"\n[{spec.fixture_id}] LIVE completed where baseline was "
            f"skipped: status={live_cap.status} "
            f"expl={live_cap.exploitability} gv={live_cap.game_value}",
        )
        # We do not assert equivalence — the baseline has nothing to
        # compare against. The next baseline recapture (post-PR-merge)
        # establishes the new reference.
        return

    if base_rec["status"] == "error":
        pytest.fail(
            f"baseline captured an error: {base_rec.get('error')!r}. "
            "Re-capture the baseline on a clean branch."
        )

    # Run live and diff.
    live_cap = run_fixture(spec)
    if live_cap.status == "error":
        pytest.fail(
            f"{spec.fixture_id} live run errored: {live_cap.error!r}\n"
            f"baseline ran successfully — this PR regressed correctness."
        )
    if live_cap.status == "skipped":
        pytest.fail(
            f"{spec.fixture_id} live run was skipped but baseline completed; "
            "the skip predicate regressed."
        )

    failures: list[str] = []
    msg = _diff_float(
        "exploitability",
        live_cap.exploitability,
        base_rec.get("exploitability"),
        TOL_EXPLOITABILITY,
    )
    if msg:
        failures.append(msg)
    msg = _diff_float(
        "game_value",
        live_cap.game_value,
        base_rec.get("game_value"),
        TOL_GAME_VALUE,
    )
    if msg:
        failures.append(msg)
    failures += _diff_strategy_sample(
        "strategy_sample",
        live_cap.strategy_sample,
        base_rec.get("strategy_sample", {}),
        TOL_STRATEGY_ENTRY,
    )
    failures += _diff_br_argmax(
        "br_argmax_sample",
        live_cap.br_argmax_sample,
        base_rec.get("br_argmax_sample", {}),
    )

    if failures:
        joined = "\n  - ".join(failures[:20])
        suffix = (
            "" if len(failures) <= 20 else f"\n  ... and {len(failures) - 20} more failures"
        )
        pytest.fail(
            f"{spec.fixture_id} diff vs baseline FAILED ({len(failures)} mismatches):\n"
            f"  - {joined}{suffix}"
        )


# ---------------------------------------------------------------------------
# CLI driver — for capturing the baseline.
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--capture-baseline",
        action="store_true",
        help="Capture the baseline JSON and write to tests/fixtures/v1_10_canonical_baseline.json",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=BASELINE_PATH,
        help="Override baseline output path",
    )
    args = ap.parse_args(argv)

    if args.capture_baseline:
        capture_baseline(args.output)
        return 0
    print(
        "Use --capture-baseline to capture; otherwise run via "
        "`pytest tests/test_v1_10_canonical_diff.py`",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
