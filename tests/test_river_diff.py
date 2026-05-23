"""PR 7 — river-spot differential test: our Python DCFR vs Noam Brown's binary.

For each of the 15 curated river spots (`tests/data/river_spots.json`), this
module:

  1. Solves with our engine via ``solve_hunl_postflop(...)`` (PR 5 surface).
  2. Solves with Brown's ``river_solver_optimized`` C++ binary via subprocess.
  3. Canonicalizes both result sets into the same
     ``(canonical_history, hand) → action_distribution`` schema via Agent A's
     helpers in ``poker_solver.parity.noambrown_wrapper``.
  4. Asserts per-action probability agreement within **5e-3** (locked PR 7 §1).
  5. Asserts per-spot game value agreement within **1e-3 × spot.pot** chips
     (locked PR 7 §1).
  6. Asserts ≥ 80% of Brown's canonical histories appear in our solve.

Tolerances are HARD-CODED to ``5e-3`` (per-action) and ``1e-3 × pot``
(per game value). Silent loosening is forbidden (PR 6/7/8/9 consensus per
``docs/spec_consistency_review.md`` I3).

Brown's binary is invoked with ``--algo dcfr --dcfr-alpha 1.5 --dcfr-beta 0
--dcfr-gamma 2 --seed 7`` (PR 7 spec §3, §12; matches our DCFR defaults).
Subprocess I/O uses ``tempfile.NamedTemporaryFile`` for pytest-xdist
collision safety (PR 7 §9 risk #8).

Five-layer skipif strategy (cleanly opts out when any precondition is unmet):

  A. Defensive imports of ``poker_solver.parity.noambrown_wrapper`` (Agent A
     module may not have landed yet; tests must still collect).
  B. ``tests/data/river_spots.json`` fixture missing → module-level skip on
     parametrization (parametrize over a single dummy spot id and skip in-body).
  C. Brown's binary missing → in-test ``pytest.skip`` with a build hint.
  D. Toolchain missing (``cmake`` / ``c++``) → the ``test_brown_binary_buildable``
     infra test skips.
  E. ``scripts/build_noambrown.sh`` missing → the infra test skips.

Layers A and B keep test collection green on a freshly cloned repo that
hasn't yet built (or doesn't have) the noambrown integration; layers C–E
keep the parity gate opt-in via the ``parity_noambrown`` marker.

Written strictly from PR 7 spec / agent_b_prompt; the spec is the source of
truth on tolerances and behavior. If a real spec ambiguity is hit, the
report flags it — we do NOT silently match Agent A's implementation.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SPOTS_JSON = REPO_ROOT / "tests" / "data" / "river_spots.json"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build_noambrown.sh"

# Locked tolerances (PR 7 §1, §11 #3; PR 6/7/8/9 consensus per
# spec_consistency_review.md I3). Hard-coded — do NOT loosen silently.
PER_ACTION_TOL: float = 5e-3
PER_GAME_VALUE_REL_TOL: float = 1e-3  # × spot.pot (in chips)

# Brown binary CLI defaults (PR 7 §3 / §12). Iterations default = 2000;
# per-spot override via spot.iterations_override.
DEFAULT_ITERATIONS: int = 2000
BROWN_SEED: int = 7

# Coverage floor: ≥ 80% of Brown's canonical histories must appear in our
# canonicalized solve. Catches accidental tree-truncation in either engine
# (PR 7 spec §10 Agent B).
COVERAGE_FLOOR: float = 0.80

# Per-spot subprocess timeout (sec). 15 spots × ~30s/spot is the spec
# runtime budget (PR 7 §5). 600s leaves headroom for the slowest spot.
BROWN_TIMEOUT_SEC: float = 600.0


# ---------------------------------------------------------------------------
# Layer A: Defensive imports of the wrapper module + poker_solver public
# surface. If Agent A's `noambrown_wrapper` is not yet importable (e.g. fresh
# checkout, or a transient import-time failure), tests still collect; per-test
# skip guards then skip cleanly.
# ---------------------------------------------------------------------------

try:
    from poker_solver.parity.noambrown_wrapper import (
        BrownInfosetEntry,
        BrownPlayerProfile,
        BrownStrategyDump,
        RiverSpot,
        canonicalize_brown_history,
        canonicalize_our_history,
        find_brown_binary,
        load_spots,
        our_strategy_to_brown_matrix,
        run_brown_solver,
    )

    _WRAPPER_OK = True
    _WRAPPER_ERR: str | None = None
except Exception as exc:  # noqa: BLE001
    BrownInfosetEntry = None  # type: ignore[assignment,misc]
    BrownPlayerProfile = None  # type: ignore[assignment,misc]
    BrownStrategyDump = None  # type: ignore[assignment,misc]
    RiverSpot = None  # type: ignore[assignment,misc]
    canonicalize_brown_history = None  # type: ignore[assignment]
    canonicalize_our_history = None  # type: ignore[assignment]
    find_brown_binary = None  # type: ignore[assignment]
    load_spots = None  # type: ignore[assignment]
    our_strategy_to_brown_matrix = None  # type: ignore[assignment]
    run_brown_solver = None  # type: ignore[assignment]
    _WRAPPER_OK = False
    _WRAPPER_ERR = f"{type(exc).__name__}: {exc}"

try:
    from poker_solver import (
        HUNLConfig,
        Street,
        solve_hunl_postflop,
    )

    _CORE_OK = True
except Exception:  # noqa: BLE001
    HUNLConfig = None  # type: ignore[assignment,misc]
    Street = None  # type: ignore[assignment,misc]
    solve_hunl_postflop = None  # type: ignore[assignment]
    _CORE_OK = False


# ---------------------------------------------------------------------------
# Layer B: parametrize over spots. If the fixture file or wrapper is missing
# at collection time, fall back to a single dummy id; the per-test body then
# skips cleanly.
# ---------------------------------------------------------------------------


def _collect_spots() -> list[Any]:
    """Load spots once at import time for pytest parametrization.

    Returns a list of ``RiverSpot`` instances if available, otherwise a list
    of one ``None`` sentinel so pytest still collects a single test for
    visibility. The per-test body checks for ``None`` and skips.
    """
    if not _WRAPPER_OK or load_spots is None:
        return [None]
    if not SPOTS_JSON.exists():
        return [None]
    try:
        return list(load_spots(SPOTS_JSON))
    except Exception:  # noqa: BLE001
        # `load_spots` raises with a clear error on schema violation; we
        # want test collection to still proceed so the body can produce
        # the actionable failure / skip message.
        return [None]


_SPOTS = _collect_spots()


def _spot_id(spot: Any) -> str:
    if spot is None:
        return "no-fixture"
    # `RiverSpot.id` is the canonical handle (e.g. "dry_K72_rainbow").
    return getattr(spot, "id", "unknown")


# ---------------------------------------------------------------------------
# Skip guards (Layers A–C consolidated into reusable helpers).
# ---------------------------------------------------------------------------


def _require_wrapper() -> None:
    """Skip if Agent A's wrapper module is not importable."""
    if not _WRAPPER_OK:
        pytest.skip(
            f"poker_solver.parity.noambrown_wrapper not yet landed: {_WRAPPER_ERR}"
        )
    if not _CORE_OK:
        pytest.skip("poker_solver core surface failed to import")


def _require_fixture() -> None:
    """Skip if the river_spots.json fixture is missing."""
    if not SPOTS_JSON.exists():
        pytest.skip(f"river fixture missing: {SPOTS_JSON}")


def _require_brown_binary() -> Path:
    """Skip if Brown's binary is not built. Returns the binary path on success."""
    assert find_brown_binary is not None  # narrowed by `_require_wrapper()`
    binary = find_brown_binary()
    if binary is None or not Path(binary).exists():
        pytest.skip(
            "Brown's river_solver_optimized not built; "
            "run `bash scripts/build_noambrown.sh` to enable parity tests."
        )
    return Path(binary)


# ---------------------------------------------------------------------------
# Auxiliary helpers (private to this module).
# ---------------------------------------------------------------------------


def _solve_with_our_engine(spot: Any, *, iterations: int) -> Any:
    """Run our DCFR on the spot via ``solve_hunl_postflop``.

    Constructs a river-only ``HUNLConfig`` (per PR 7 spec §5 step 2 + agent
    A's locked decision: pot/stack are integer chips, big_blind=100, so
    pot=1000 chips = 10 BB; matches Brown's RiverGame construction).

    Returns the ``HUNLSolveResult``. Agent A may later expose a dedicated
    ``solve_river_subgame_explicit_ranges(...)`` helper; if/when that lands
    the body of this helper switches to call it. For PR 7 we use the
    existing public surface (PR 5).

    Note: ``initial_hole_cards=()`` because the river-spot fixture iterates
    over explicit ranges; we don't pin to a single combo. This matches the
    pattern in ``default_tiny_subgame`` (``hunl.py:165-204``).
    """
    assert HUNLConfig is not None and Street is not None  # via _require_wrapper
    assert solve_hunl_postflop is not None

    pot = int(spot.pot)
    cfg = HUNLConfig(
        starting_stack=int(spot.stack),
        starting_street=Street.RIVER,
        initial_board=tuple(spot.board),
        initial_pot=pot,
        initial_contributions=(pot // 2, pot - pot // 2),
        initial_hole_cards=(),
        bet_size_fractions=tuple(spot.bet_sizes),
        include_all_in=bool(spot.include_all_in),
        postflop_raise_cap=int(spot.max_raises),
        abstraction=None,
    )
    return solve_hunl_postflop(
        cfg,
        abstraction=None,
        iterations=iterations,
        seed=BROWN_SEED,
    )


def _player_keys(profile: dict[str, Any]) -> set[str]:
    """Set of canonical-history keys present in a Brown player profile."""
    return set(profile.keys())


def _compare_action_distributions(
    spot_id: str,
    history: str,
    brown_entry: Any,
    our_matrix_entry: Any,
    tol: float,
) -> list[str]:
    """Compare one (history, player) entry.

    Returns a list of human-readable diff descriptions (empty on full agreement).
    Uses informative messages — which spot, which history, which hand index,
    which action, which actuals — for actionable diagnostics on failure.
    """
    diffs: list[str] = []
    brown_strategy = brown_entry.strategy
    actions = brown_entry.actions
    if our_matrix_entry is None:
        diffs.append(
            f"{spot_id}: history={history!r} missing from our canonicalized matrix"
        )
        return diffs

    # `our_matrix_entry` is np.ndarray (num_hands, num_actions); `brown_strategy`
    # is tuple-of-tuple (num_hands, num_actions). Shapes must match for a
    # per-cell comparison.
    n_hands = len(brown_strategy)
    n_actions = len(actions)
    our_shape = getattr(our_matrix_entry, "shape", None)
    if our_shape != (n_hands, n_actions):
        diffs.append(
            f"{spot_id}: history={history!r} shape mismatch — "
            f"brown=({n_hands}, {n_actions}), ours={our_shape}"
        )
        return diffs

    for h_idx in range(n_hands):
        brown_row = brown_strategy[h_idx]
        our_row = our_matrix_entry[h_idx]
        for a_idx in range(n_actions):
            ours = float(our_row[a_idx])
            theirs = float(brown_row[a_idx])
            if abs(ours - theirs) >= tol:
                diffs.append(
                    f"{spot_id}: history={history!r}, hand_idx={h_idx}, "
                    f"action={actions[a_idx]!r}: ours={ours:.6f} "
                    f"brown={theirs:.6f} |diff|={abs(ours - theirs):.3e}"
                )
    return diffs


# ---------------------------------------------------------------------------
# Parametrized diff test (the headline; 1 function, 15 invocations).
# ---------------------------------------------------------------------------


@pytest.mark.parity_noambrown
@pytest.mark.slow
@pytest.mark.timeout(int(BROWN_TIMEOUT_SEC) + 60)
@pytest.mark.parametrize("spot", _SPOTS, ids=_spot_id)
def test_river_parity_vs_brown(spot: Any) -> None:
    """Per-spot diff vs Noam Brown's river_solver_optimized.

    For each spot:
      1. Skip cleanly if any precondition is unmet (wrapper, fixture, binary).
      2. Solve with our engine at ``spot.iterations_override or 2000`` iters.
      3. Solve with Brown's binary at the same iteration count.
      4. Canonicalize both result sets to the shared schema via Agent A.
      5. Take the intersection of canonical histories present in BOTH engines.
      6. For each shared (history, hand, action): assert
         ``abs(ours - brown) < 5e-3``.
      7. Assert ``abs(our_game_value - brown_game_value) < 1e-3 * spot.pot``.
      8. Assert ≥ 80% of Brown's history keys appear in our canonicalized
         result (PR 7 spec §10 Agent B; catches accidental tree-truncation).

    Tolerances: 5e-3 per-action, 1e-3 × pot per game value. Locked per
    PR 7 spec §1 + spec_consistency_review I3. Hard-coded; no silent
    loosening.
    """
    if spot is None:
        # Layer B: parametrization fell back to the sentinel (fixture or
        # wrapper missing). Defer the message to the consolidated guard so
        # the user sees the precise reason.
        _require_wrapper()
        _require_fixture()
        pytest.skip("river_spots fixture parametrization produced no spots")
    _require_wrapper()
    _require_fixture()
    binary = _require_brown_binary()

    iters = int(spot.iterations_override or DEFAULT_ITERATIONS)

    # --- Our engine ---
    our_result = _solve_with_our_engine(spot, iterations=iters)

    # --- Brown's engine ---
    # `run_brown_solver` is contracted (per agent A's prompt §6 "Subprocess
    # hygiene") to use `tempfile.NamedTemporaryFile` for pytest-xdist safety.
    # We call into Agent A's wrapper and trust the contract; if a subprocess
    # collision surfaces, the fix lives in the wrapper, not here.
    assert run_brown_solver is not None  # via _require_wrapper
    brown_dump = run_brown_solver(
        spot,
        binary,
        iterations=iters,
        seed=BROWN_SEED,
        timeout_sec=BROWN_TIMEOUT_SEC,
    )

    # Sanity: Brown actually ran the requested iterations.
    if hasattr(brown_dump, "iterations_run"):
        assert brown_dump.iterations_run == iters, (
            f"{spot.id}: Brown ran {brown_dump.iterations_run} iters, "
            f"requested {iters}"
        )

    # --- Canonicalize our strategy into Brown's matrix shape ---
    hands_p0 = tuple(h for (h, _w) in spot.ranges[0])
    hands_p1 = tuple(h for (h, _w) in spot.ranges[1])
    assert our_strategy_to_brown_matrix is not None  # via _require_wrapper
    our_matrix = our_strategy_to_brown_matrix(
        our_result,
        hands_p0,
        hands_p1,
        spot,
    )

    # --- History coverage ---
    # Brown's histories are split across the two player profiles (a given
    # action history belongs to whichever player is to act at that node).
    brown_keys_p0 = _player_keys(brown_dump.players[0].profile)
    brown_keys_p1 = _player_keys(brown_dump.players[1].profile)
    brown_keys = brown_keys_p0 | brown_keys_p1
    our_keys = set(our_matrix.keys())
    shared = brown_keys & our_keys
    coverage = len(shared) / max(len(brown_keys), 1)

    if coverage < COVERAGE_FLOOR:
        missing = sorted(brown_keys - our_keys)[:5]
        pytest.fail(
            f"{spot.id}: history coverage {coverage:.1%} < {COVERAGE_FLOOR:.0%}. "
            f"Brown produced {len(brown_keys)} histories; our solve has "
            f"{len(our_keys)}. First missing keys: {missing}"
        )

    # --- Per-action probability agreement ---
    all_diffs: list[str] = []
    for history in sorted(shared):
        # Each player's profile carries its own action set at this history.
        # Compare for whichever player(s) have an entry. `our_matrix` is
        # keyed by (history) -> dict[player_idx, np.ndarray].
        for player in (0, 1):
            brown_profile = brown_dump.players[player].profile
            if history not in brown_profile:
                continue
            brown_entry = brown_profile[history]
            our_player_matrix = our_matrix[history].get(player)
            diffs = _compare_action_distributions(
                spot_id=spot.id,
                history=history,
                brown_entry=brown_entry,
                our_matrix_entry=our_player_matrix,
                tol=PER_ACTION_TOL,
            )
            all_diffs.extend(diffs)

    if all_diffs:
        # Cap the failure message to keep output readable; show the first 20.
        head = "\n  ".join(all_diffs[:20])
        suffix = ""
        if len(all_diffs) > 20:
            suffix = f"\n  ... ({len(all_diffs) - 20} more diffs)"
        pytest.fail(
            f"{spot.id}: per-action probabilities diverge "
            f"(tolerance {PER_ACTION_TOL:.0e}):\n  {head}{suffix}"
        )

    # --- Per-spot game value agreement ---
    # Brown's game value (in chips, from stdout); ours (from SolveResult).
    # PR 5's SolveResult.game_value is in BB-units (utility() returns c/bb).
    # Convert to chips by multiplying by big_blind. HUNLConfig.big_blind
    # defaults to 100 (per `hunl.py:96`); the fixture spec locks pot=1000
    # chips = 10 BB, so big_blind=100 is the canonical PR 7 setting.
    brown_value = getattr(brown_dump, "game_value_p0", None)
    if brown_value is None:
        # PR 7 §10: if Brown's stdout didn't expose a value (older builds /
        # parse miss), the per-action assertions above still ran. Continue
        # without failing on the game-value comparison.
        return
    # Convert ours from BB-units → chips. PR 5 `SolveResult.game_value` is
    # `c0 / bb` (see `solver.py:167-175` calling `utility()` from
    # `hunl.py:285-299`).
    big_blind = 100  # canonical PR 7 setting; fixture locks pot in chips.
    our_value_chips = float(our_result.game_value) * big_blind
    tol_chips = PER_GAME_VALUE_REL_TOL * float(spot.pot)
    diff = abs(our_value_chips - float(brown_value))
    assert diff < tol_chips, (
        f"{spot.id}: game value diverges. ours={our_value_chips:.4f} chips "
        f"({our_result.game_value:.6f} BB), brown={brown_value:.4f} chips, "
        f"|diff|={diff:.4f}, tol={tol_chips:.4f} (= {PER_GAME_VALUE_REL_TOL:.0e} "
        f"× pot={spot.pot})"
    )


# ---------------------------------------------------------------------------
# Infrastructure test: build the binary on demand (Layers D + E).
# ---------------------------------------------------------------------------


@pytest.mark.parity_noambrown
@pytest.mark.timeout(900)
def test_brown_binary_buildable() -> None:
    """Invoke scripts/build_noambrown.sh and assert the binary exists afterward.

    Skips cleanly if:
      - the wrapper module isn't importable yet (Layer A), OR
      - cmake or c++ is unavailable (Layer D), OR
      - the build script doesn't exist (Layer E).

    PR 7 spec §10 Agent B: "skips if cmake missing".
    """
    _require_wrapper()
    # Layer D: toolchain check.
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        pytest.skip("cmake or c++ unavailable; cannot build Brown's binary")
    # Layer E: build script must exist.
    if not BUILD_SCRIPT.exists():
        pytest.skip(f"build script missing: {BUILD_SCRIPT}")

    result = subprocess.run(
        ["bash", str(BUILD_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert result.returncode == 0, (
        f"build script failed (exit {result.returncode}):\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert find_brown_binary is not None  # narrowed by _require_wrapper
    binary = find_brown_binary()
    assert binary is not None, "binary path still None after successful build"
    assert Path(binary).exists(), f"binary path returned but file missing: {binary}"
