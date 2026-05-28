"""Differential tests for the True Path B 169-class preflop RvR engine
(task #68 Phase 1.5 follow-up to PR #167).

PR #167 shipped the hybrid path: engine runs 1326-combo internally, wrapper
post-aggregates to 169-class output. Compute time per cell at 25K iters is
~75-90 min, blocking the 27-cell Phase 1.5 overnight build.

True Path B (this PR): engine operates on 169-element strategy/regret/reach
vectors directly. Per-iter cost drops from O(N=1326^2) AXPY per leaf to
O(N=169^2), giving ~7-10x perf on representative configs. Leaf payoffs
pre-bake the per-(combo_a, combo_b) blocker mass into each (class_i,
class_j) cell.

This file validates:

  1. **Closed-form AA-vs-KK smoke** — at 300 iters in 169-class mode,
     AA has fold ≤ 1% and commit (call+raise+jam) ≥ 99% at SB root.
     Mirrors the existing `aa_only_vs_kk_only_closed_form` test in
     `test_preflop_rvr_diff.py`.

  2. **Cross-resolution L1 drift** — at matched iter budgets the
     169-class engine's strategy and the hybrid (1326-combo + wrapper
     aggregation) strategy agree within L1 ≤ 0.05 per class-action cell.
     The Phase 1 task brief calls for this gate; it's the equivalence-
     test that locks in "169-class mode converges to the same Nash
     as the 1326-combo path after aggregation, modulo finite-iter drift."

  3. **Cross-iter monotone convergence** — at iter=100 / 1000 / 5000
     the 169-class strategies converge (per-cell |Δ| trending toward 0).
     This is a sanity check that the inner kernel doesn't have a
     divergent bug.

  4. **Engine speedup** — at matched iter count + same tree topology,
     169-class wall-clock is ≥ 2x faster than 1326-combo. (The
     task brief targets ≥ 5x but that depends on machine; we lock the
     conservative lower bound here and report the measured ratio.)

  5. **Memory footprint** — 169-class storage at peak is ≥ 5x smaller
     than 1326-combo storage. Measured via Rust struct sizing.

  6. **Pushfold equivalence at 15 BB** — 169-class engine respects
     pushfold chart's extreme regions. Same invariants as Test 1 in
     `test_preflop_rvr_diff.py`.
"""

from __future__ import annotations

import importlib
import os
import time

import pytest

from poker_solver import HUNLConfig
from poker_solver.blueprint import (
    CANONICAL_169_CLASSES,
    aggregate_to_169_classes,
)
from poker_solver.hunl import _serialize_hunl_config
from poker_solver.pushfold import get_full_range

try:
    _rust_module = importlib.import_module("poker_solver._rust")
    _rust_solve_combo1326 = getattr(_rust_module, "solve_hunl_preflop_rvr", None)
    _rust_solve_class169 = getattr(
        _rust_module, "solve_hunl_preflop_rvr_class169", None
    )
except Exception:  # noqa: BLE001
    _rust_solve_combo1326 = None  # type: ignore[assignment]
    _rust_solve_class169 = None  # type: ignore[assignment]


def _equity_table_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(here)
    path = os.path.join(repo_root, "assets", "preflop_equity_169x169.npz")
    return path


_EQUITY_TABLE = _equity_table_path()


pytestmark = [
    pytest.mark.skipif(
        _rust_solve_class169 is None,
        reason=(
            "poker_solver._rust.solve_hunl_preflop_rvr_class169 missing — "
            "rebuild the Rust extension via `maturin develop --release`."
        ),
    ),
    pytest.mark.skipif(
        not os.path.exists(_EQUITY_TABLE),
        reason=f"preflop equity table not found at {_EQUITY_TABLE!r}",
    ),
]


# ---------------------------------------------------------------------------
# Test 1 — AA-vs-KK closed-form smoke in 169-class mode
# ---------------------------------------------------------------------------


def test_class169_aa_vs_kk_closed_form() -> None:
    """At 300 iters in 169-class mode with AA-only / KK-only reach filter,
    AA must (i) never fold (< 1%), (ii) commit chips (call + aggressive
    ≥ 99%) at the SB root."""
    cfg = HUNLConfig(starting_stack=10_000)  # 100 BB
    config_json = _serialize_hunl_config(cfg)
    # Filter reach: AA only for P0, KK only for P1.
    reach_p0 = [0.0] * 169
    reach_p1 = [0.0] * 169
    aa_idx = CANONICAL_169_CLASSES.index("AA")
    kk_idx = CANONICAL_169_CLASSES.index("KK")
    reach_p0[aa_idx] = 1.0
    reach_p1[kk_idx] = 1.0

    raw = _rust_solve_class169(
        config_json,
        _EQUITY_TABLE,
        300,  # iterations
        1.5,
        0.0,
        2.0,
        None,  # default open sizes [2, 3, 4, 5] BB
        None,  # default reraise mults [2, 3, 4, 5]
        reach_p0,
        reach_p1,
    )
    average_strategy = {k: list(v) for k, v in raw["average_strategy"].items()}
    assert raw["hand_resolution"] == "class_169"
    assert raw["backend"] == "rust_preflop_rvr_class169"

    aa_root = average_strategy["AA||p|"]
    fold_prob = aa_root[0]
    call_prob = aa_root[1]
    aggressive_prob = sum(aa_root[2:])

    assert fold_prob < 0.01, (
        f"AA must not fold in 169-class mode; got fold = {fold_prob:.6f}, "
        f"strategy = {[round(p, 4) for p in aa_root]}"
    )
    commit = call_prob + aggressive_prob
    assert commit > 0.99, (
        f"AA must commit chips; got commit_rate = {commit:.6f}, "
        f"strategy = {[round(p, 4) for p in aa_root]}"
    )


# ---------------------------------------------------------------------------
# Test 2 — Cross-resolution L1 drift: 169-class ≈ hybrid (combo + aggregate)
# ---------------------------------------------------------------------------


def test_class169_matches_hybrid_within_l1_tolerance() -> None:
    """At matched iter budget, 169-class engine output matches
    `aggregate_to_169_classes(1326-combo output)` within L1 ≤ 0.05 per
    (class, action) cell.

    This is the load-bearing equivalence gate per the task brief — if
    the 169-class engine produces a different equilibrium from the
    hybrid path it would invalidate the perf speedup.

    Uses 15 BB (small tree, fast to converge) + 1000 iters for tractable
    wall-clock. Tighter tolerances are achievable at higher iter counts.
    """
    cfg = HUNLConfig(starting_stack=1500)  # 15 BB
    config_json = _serialize_hunl_config(cfg)
    iters = 1000
    opens = [2.0, 3.0]
    mults = [2.0, 3.0]

    # Path A — 1326-combo engine + wrapper aggregation.
    t0 = time.perf_counter()
    raw_combo = _rust_solve_combo1326(
        config_json,
        _EQUITY_TABLE,
        iters,
        1.5,
        0.0,
        2.0,
        opens,
        mults,
        None,
        None,
    )
    wall_combo = time.perf_counter() - t0
    combo_strategy = {k: list(v) for k, v in raw_combo["average_strategy"].items()}
    by_history_class = aggregate_to_169_classes(combo_strategy)

    # Path B — 169-class engine.
    t0 = time.perf_counter()
    raw_169 = _rust_solve_class169(
        config_json,
        _EQUITY_TABLE,
        iters,
        1.5,
        0.0,
        2.0,
        opens,
        mults,
        None,
        None,
    )
    wall_169 = time.perf_counter() - t0
    class169_strategy = {k: list(v) for k, v in raw_169["average_strategy"].items()}

    # Group 169-class output by history.
    history_keys: set[str] = set()
    by_history_class_169: dict[str, dict[str, list[float]]] = {}
    for key, probs in class169_strategy.items():
        # Key format: "<class>||p|<history>".
        if "||p|" not in key:
            continue
        cls_label, _, history_suffix = key.partition("||p|")
        if cls_label not in CANONICAL_169_CLASSES:
            continue
        history_key = "||p|" + history_suffix
        history_keys.add(history_key)
        by_history_class_169.setdefault(history_key, {})[cls_label] = probs

    # Compute per-cell L1 drift between the two paths.
    max_l1 = 0.0
    worst_key = ""
    worst_cls = ""
    sum_l1 = 0.0
    cell_count = 0
    for history_key in history_keys:
        if history_key not in by_history_class:
            continue
        hybrid_classes = by_history_class[history_key]
        true_classes = by_history_class_169[history_key]
        for cls_label, hybrid_row in hybrid_classes.items():
            if cls_label not in true_classes:
                continue
            true_row = true_classes[cls_label]
            if len(hybrid_row) != len(true_row):
                pytest.fail(
                    f"action-count mismatch at {history_key!r}/{cls_label!r}: "
                    f"hybrid={len(hybrid_row)}, true={len(true_row)}"
                )
            l1 = sum(abs(a - b) for a, b in zip(hybrid_row, true_row))
            sum_l1 += l1
            cell_count += 1
            if l1 > max_l1:
                max_l1 = l1
                worst_key = history_key
                worst_cls = cls_label

    avg_l1 = sum_l1 / max(cell_count, 1)
    print(
        f"\nCross-resolution L1 drift (15 BB, 1000 iters):\n"
        f"  max L1 per cell: {max_l1:.4f} at {worst_key!r}/{worst_cls!r}\n"
        f"  avg L1 per cell: {avg_l1:.4f}\n"
        f"  cells compared: {cell_count}\n"
        f"  wall_combo: {wall_combo:.2f}s | wall_169: {wall_169:.2f}s | "
        f"speedup: {wall_combo / wall_169:.2f}x"
    )
    # Tolerance: 0.05 is the task brief's L1-per-cell target.
    assert max_l1 <= 0.05, (
        f"169-class output drifts from hybrid by > 0.05 L1 per cell: "
        f"max_l1 = {max_l1:.4f} at {worst_key!r}/{worst_cls!r}; "
        f"avg_l1 = {avg_l1:.4f} over {cell_count} cells"
    )


# ---------------------------------------------------------------------------
# Test 3 — Cross-iter monotone convergence sanity
# ---------------------------------------------------------------------------


def test_class169_monotone_convergence_smoke() -> None:
    """At iter=100, 500, 2000 in 169-class mode the strategy drift
    between consecutive iter counts trends DOWNWARD (Cauchy convergence).
    This catches a divergent-kernel bug without requiring full Nash
    exploitability.
    """
    cfg = HUNLConfig(starting_stack=1500)  # 15 BB
    config_json = _serialize_hunl_config(cfg)
    iters_grid = [100, 500, 2000]
    strategies = []
    for iters in iters_grid:
        raw = _rust_solve_class169(
            config_json,
            _EQUITY_TABLE,
            iters,
            1.5,
            0.0,
            2.0,
            [2.0],  # minimal open menu for speed
            [2.0],
            None,
            None,
        )
        strategies.append({k: list(v) for k, v in raw["average_strategy"].items()})

    def l1_diff(a: dict, b: dict) -> float:
        total = 0.0
        keys = set(a) & set(b)
        for k in keys:
            ra, rb = a[k], b[k]
            if len(ra) != len(rb):
                continue
            total += sum(abs(x - y) for x, y in zip(ra, rb))
        return total / max(len(keys), 1)

    d_100_500 = l1_diff(strategies[0], strategies[1])
    d_500_2000 = l1_diff(strategies[1], strategies[2])
    print(
        f"\nMonotone convergence smoke:\n"
        f"  iters {iters_grid[0]} -> {iters_grid[1]}: avg L1 = {d_100_500:.4f}\n"
        f"  iters {iters_grid[1]} -> {iters_grid[2]}: avg L1 = {d_500_2000:.4f}"
    )
    # Later-stage drift should be smaller than earlier-stage (Cauchy).
    # Allow some slop because finite-iter drift isn't strictly monotonic.
    assert d_500_2000 <= d_100_500 * 1.2, (
        f"169-class strategy fails Cauchy-monotone smoke: "
        f"d(100->500) = {d_100_500:.4f}, d(500->2000) = {d_500_2000:.4f} "
        f"(later should be <= earlier * 1.2)"
    )


# ---------------------------------------------------------------------------
# Test 4 — Engine speedup: ≥ 2x at matched iter count
# ---------------------------------------------------------------------------


def test_class169_speedup_over_combo1326() -> None:
    """169-class engine at matched iter count + same tree topology is
    ≥ 2x faster than 1326-combo. The task brief targets ≥ 5x but that
    depends on machine + tree depth; we lock 2x as the conservative gate
    and report the measured ratio.
    """
    cfg = HUNLConfig(starting_stack=4_000)  # 40 BB — representative depth
    config_json = _serialize_hunl_config(cfg)
    iters = 30  # short enough for fast CI; capture per-iter cost difference
    opens = [2.0, 3.0]
    mults = [2.0, 3.0]

    # Warm-up + measure 1326-combo path.
    t0 = time.perf_counter()
    raw_combo = _rust_solve_combo1326(
        config_json,
        _EQUITY_TABLE,
        iters,
        1.5,
        0.0,
        2.0,
        opens,
        mults,
        None,
        None,
    )
    wall_combo = time.perf_counter() - t0

    # Warm-up + measure 169-class path.
    t0 = time.perf_counter()
    raw_169 = _rust_solve_class169(
        config_json,
        _EQUITY_TABLE,
        iters,
        1.5,
        0.0,
        2.0,
        opens,
        mults,
        None,
        None,
    )
    wall_169 = time.perf_counter() - t0

    speedup = wall_combo / wall_169
    print(
        f"\nEngine speedup (40 BB, {iters} iters):\n"
        f"  1326-combo wall: {wall_combo:.3f}s\n"
        f"  169-class wall: {wall_169:.3f}s\n"
        f"  speedup ratio: {speedup:.2f}x"
    )
    # Sanity: both runs produced output.
    assert raw_combo["strategy_entry_count"] > 0
    assert raw_169["strategy_entry_count"] > 0
    # Conservative gate: 2x. The leaf-build cost amortizes over iter
    # count; at 25K iters the speedup compounds. Reported ratio is the
    # primary number — assertion is just a sanity floor.
    assert speedup >= 2.0, (
        f"169-class engine must be ≥ 2x faster than 1326-combo at matched "
        f"iter count; got speedup = {speedup:.2f}x"
    )


# ---------------------------------------------------------------------------
# Test 5 — Memory footprint comparison
# ---------------------------------------------------------------------------


def test_class169_memory_footprint() -> None:
    """169-class storage per infoset uses ~7.8x less memory than 1326-combo.

    Compute: each infoset stores `hand_count * action_count` f64 cells for
    regret AND strategy_sum (2 vectors).
      1326-combo: 1326 * action_count * 8 bytes * 2 vectors
      169-class:  169 * action_count * 8 bytes * 2 vectors
      ratio: 1326 / 169 = 7.846x

    This is the structural memory advantage; the test verifies it
    holds via decision_node_count + strategy_entry_count from the raw
    output (which scales with hand_count * decision_node_count).
    """
    cfg = HUNLConfig(starting_stack=4_000)  # 40 BB
    config_json = _serialize_hunl_config(cfg)
    raw_combo = _rust_solve_combo1326(
        config_json,
        _EQUITY_TABLE,
        3,  # tiny iter count — we only care about structure
        1.5,
        0.0,
        2.0,
        [2.0],
        [2.0],
        None,
        None,
    )
    raw_169 = _rust_solve_class169(
        config_json,
        _EQUITY_TABLE,
        3,
        1.5,
        0.0,
        2.0,
        [2.0],
        [2.0],
        None,
        None,
    )
    # Both runs should have same decision_node_count (same tree).
    assert raw_combo["decision_node_count"] == raw_169["decision_node_count"], (
        f"Decision node counts must match across resolutions: "
        f"combo={raw_combo['decision_node_count']}, "
        f"169={raw_169['decision_node_count']}"
    )
    combo_entries = raw_combo["strategy_entry_count"]
    class169_entries = raw_169["strategy_entry_count"]
    ratio = combo_entries / class169_entries
    print(
        f"\nMemory footprint (entries proportional to peak f64 storage):\n"
        f"  1326-combo strategy entries: {combo_entries}\n"
        f"  169-class strategy entries: {class169_entries}\n"
        f"  ratio: {ratio:.2f}x (expected: 1326/169 = 7.85x)"
    )
    # Tolerate ±0.5x slack on the expected 7.85x ratio (depends on whether
    # all 169 classes are emitted at every infoset).
    assert ratio >= 5.0, (
        f"169-class engine must have ≥ 5x fewer strategy entries; "
        f"got ratio = {ratio:.2f}x"
    )


# ---------------------------------------------------------------------------
# Test 6 — Pushfold equivalence at 15 BB (parallel to test_preflop_rvr_diff)
# ---------------------------------------------------------------------------


def test_class169_pushfold_equivalence_15bb() -> None:
    """At 15 BB with [Fold, Call, AllIn] action menu, 169-class engine
    must respect the static pushfold chart's extreme regions:
      (a) chart-100%-jam hands: engine fold rate < 1%
      (b) chart-0%-jam hands: engine jam rate < 2%
    """
    cfg = HUNLConfig(starting_stack=1500)  # 15 BB
    config_json = _serialize_hunl_config(cfg)
    raw = _rust_solve_class169(
        config_json,
        _EQUITY_TABLE,
        500,
        1.5,
        0.0,
        2.0,
        [],  # no opens — SB chooses fold/call/AllIn only
        [],
        None,
        None,
    )
    average_strategy = {k: list(v) for k, v in raw["average_strategy"].items()}

    chart = get_full_range(15, "sb_jam")
    chart_jam_classes = [cls for cls, freq in chart.items() if freq >= 0.99]
    chart_fold_classes = [cls for cls, freq in chart.items() if freq <= 0.01]
    assert len(chart_jam_classes) >= 80
    assert len(chart_fold_classes) >= 60

    # Build {class: root_strategy} from 169-class output.
    root_by_class: dict[str, list[float]] = {}
    for key, probs in average_strategy.items():
        if not key.endswith("||p|"):
            continue
        cls_label = key[: -len("||p|")]
        if cls_label in CANONICAL_169_CLASSES:
            root_by_class[cls_label] = probs

    fold_violations: list[tuple[str, float]] = []
    for cls in chart_jam_classes:
        if cls not in root_by_class:
            continue
        fold_rate = root_by_class[cls][0]
        if fold_rate >= 0.01:
            fold_violations.append((cls, fold_rate))

    jam_violations: list[tuple[str, float]] = []
    for cls in chart_fold_classes:
        if cls not in root_by_class:
            continue
        # Action menu: [Fold, Call, AllIn] — index 2 is jam.
        jam_rate = root_by_class[cls][2]
        if jam_rate >= 0.02:
            jam_violations.append((cls, jam_rate))

    assert not fold_violations, (
        f"169-class engine FOLDED chart-100%-jam classes: {fold_violations[:5]}"
    )
    assert not jam_violations, (
        f"169-class engine JAMMED chart-0%-jam classes: {jam_violations[:5]}"
    )
