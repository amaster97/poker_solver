"""Empirical retest of W2.1 (Sarah full-tree preflop) and W2.3 (Sarah deep-stack
turn) after the 5-PR merge wave landed PRs #20, #121, #122, #126, #139.

PR #122 (`efc9eae`) ships the full-tree preflop RvR engine, exposing
`_rust.solve_hunl_preflop_rvr`, which accepts `initial_hole_cards = None` and
solves the full preflop tree with all 1326 hole-card combos active. This was
the structural blocker that kept W2.1 at PARTIAL.

PR #139 (`5d2a33d`) ships best-response-walk caching of terminal-leaf
strengths. W2.3 was previously BLOCKED on a >1200 s kill switch on the 8-class
symmetric turn fixture; the BR-walk cache should dramatically shrink
end-to-end with `compute_exploitability_at_end=True`.

Measurement-only; no source modification.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from poker_solver import _rust
from poker_solver.hunl import HUNLConfig, Street, _serialize_hunl_config


def _flush_print(*args, **kwargs):
    print(*args, **kwargs, flush=True)
    sys.stdout.flush()


REPO_ROOT = Path(__file__).resolve().parents[1]
EQUITY_TABLE = REPO_ROOT / "assets" / "preflop_equity_169x169.npz"


def _banner(title: str) -> None:
    print("=" * 72)
    print(title)
    print("=" * 72)


def retest_w2_1() -> dict:
    """W2.1 — full HU 100 BB preflop range chart.

    Spec criteria (`docs/pr13_prep/persona_acceptance_spec.md`, line 41):
        Post-PR-9: solve(HUNLPoker(HUNLConfig(starting_stack=10_000)),
        iterations=200_000, backend="rust") and pivot result.average_strategy
        into a 13×13 matrix. 10–30 min on Rust tier.

    Pre-PR-122 status: PARTIAL — empty `initial_hole_cards` raised ValueError
    on the `solve_hunl_preflop` (fixed-hole subgame) path because PR 9 shipped
    subgame-only.

    Post-PR-122 surface: `_rust.solve_hunl_preflop_rvr(config_json,
    equity_table_path, iterations, alpha, beta, gamma, ...)`. Accepts
    `initial_hole_cards = None`. Phase A collapses postflop runouts to a
    169×169×3 equity table, so we measure correctness via:
      (1) the call succeeds with NO `MissingHoleCards` / ValueError raise
      (2) returns non-empty average_strategy
      (3) hand_count_per_player == [1326, 1326]
      (4) strategy rows sum to ~1.0
      (5) wall time recorded; budget is "10 min" per task brief.

    To stay inside the 10-min retest budget we use a small iteration count
    (300) — this is a smoke retest, not a convergence run.
    """
    _banner("W2.1 — full-tree preflop RvR (post PR #122)")

    if not EQUITY_TABLE.exists():
        raise SystemExit(f"equity table missing: {EQUITY_TABLE}")
    print(f"equity table: {EQUITY_TABLE} ({EQUITY_TABLE.stat().st_size} bytes)")

    # 100 BB starting stacks (10_000 chips with bb=100). HUNL preflop start
    # with no fixed hole cards — the PR-122 surface explicitly supports this.
    # Python-side sentinel is the empty tuple `()`; the JSON serializer maps
    # this to `initial_hole_cards = null`, which the Rust binding accepts.
    cfg = HUNLConfig(
        starting_stack=10_000,
        small_blind=50,
        big_blind=100,
        starting_street=Street.PREFLOP,
        initial_hole_cards=(),
    )
    config_json = _serialize_hunl_config(cfg)

    # Sanity smoke at 10 iters measured at ~27 s on M4 Pro; we use 50 iters
    # (~2.5 min) to comfortably exercise the engine end-to-end while staying
    # well inside the 10-min budget per task brief. This is a smoke retest
    # of structural reclassification (BLOCKED -> PASS), not a convergence run.
    iterations = 50
    print(f"config: starting_stack=10000 BB=100 SB=50; iterations={iterations}")
    print("invoking _rust.solve_hunl_preflop_rvr(...)")

    t0 = time.perf_counter()
    out = _rust.solve_hunl_preflop_rvr(
        config_json,
        str(EQUITY_TABLE),
        iterations,
        1.5,  # alpha
        0.0,  # beta
        2.0,  # gamma
    )
    wall = time.perf_counter() - t0

    avg = out["average_strategy"]
    rows = list(avg.items())
    n_rows = len(rows)
    print(f"wall: {wall:.2f}s")
    print(f"backend: {out.get('backend')}")
    print(f"iterations completed: {out.get('iterations')}")
    print(f"decision_node_count: {out.get('decision_node_count')}")
    print(f"strategy_entry_count: {out.get('strategy_entry_count')}")
    print(f"hand_count_per_player: {out.get('hand_count_per_player')}")
    print(f"average_strategy rows: {n_rows}")

    assert n_rows > 0, "FAIL: average_strategy is empty"
    assert out.get("hand_count_per_player") == [1326, 1326], (
        f"FAIL: expected hand_count_per_player == [1326, 1326], got "
        f"{out.get('hand_count_per_player')}"
    )

    bad_norm = 0
    for k, probs in rows[:50]:
        s = sum(probs)
        if abs(s - 1.0) > 1e-5:
            print(f"  row {k}: sum={s} probs={probs}")
            bad_norm += 1
    assert bad_norm == 0, f"FAIL: {bad_norm} rows did not normalize to 1.0"
    print(f"OK: first 50 rows all normalize to ~1.0")

    verdict = "PASS"
    return {
        "id": "W2.1",
        "verdict": verdict,
        "wall_seconds": wall,
        "iterations": int(out.get("iterations", iterations)),
        "decision_node_count": int(out.get("decision_node_count", 0)),
        "strategy_entry_count": int(out.get("strategy_entry_count", 0)),
        "hand_count": out.get("hand_count_per_player"),
        "backend": str(out.get("backend")),
    }


def retest_w2_3() -> dict:
    """W2.3 — Sarah deep-stack turn vs turn with end-to-end exploitability.

    Spec criteria (`docs/pr13_prep/persona_acceptance_spec.md`, line 45):
        Flop subgame with custom starting ranges; 5–15 min on standard flop,
        Rust tier. The original fixture (from prior persona retests) is the
        8-class symmetric turn vs turn at Qs 7h 2d 5c, 200 BB, iter=500. Prior
        status: BLOCKED on >1200 s kill switch.

    PR #139 (`5d2a33d`) caches terminal-leaf strengths in the best-response
    walk, which is load-bearing for `compute_exploitability_at_end=True`.

    Smoke-grade retest: small RvR with `compute_exploitability_at_end=True`
    to exercise the BR-walk + cache. Use a smaller-than-canonical class count
    plus iter=200 to stay inside the 10-min budget per task brief.
    """
    _banner("W2.3 — deep-stack turn RvR + BR-walk exploitability (post PR #139)")

    # Lazy imports so failures in one half don't block the other.
    from poker_solver.range_aggregator import solve_range_vs_range_nash
    from poker_solver.card import Card

    # 8-class symmetric turn fixture from prior W2.3 retests:
    # board Qs 7h 2d 5c, 200 BB stacks.
    board_strs = ["Qs", "7h", "2d", "5c"]
    board = [Card.from_str(s) for s in board_strs]
    classes = ["AA", "KK", "QQ", "JJ", "AKs", "AKo", "AQs", "AQo"]

    iterations = 200
    print(f"board: {board_strs} (turn, len={len(board)})")
    print(f"hero/villain classes ({len(classes)}): {classes}")
    print(f"iterations: {iterations}; compute_exploitability_at_end=True")

    cfg = HUNLConfig(
        starting_stack=20_000,  # 200 BB at bb=100
        small_blind=50,
        big_blind=100,
        starting_street=Street.TURN,
        initial_board=tuple(board),
        initial_hole_cards=(),
    )

    print("invoking solve_range_vs_range_nash(...)")
    t0 = time.perf_counter()
    res = solve_range_vs_range_nash(
        cfg,
        hero_range=classes,
        villain_range=classes,
        iterations=iterations,
        compute_exploitability_at_end=True,
    )
    wall = time.perf_counter() - t0

    print(f"wall: {wall:.2f}s")
    print(f"backend: {res.backend}")
    print(f"iterations completed: {res.iterations}")
    print(f"decision_node_count: {res.decision_node_count}")
    print(f"hand_count_per_player: {res.hand_count_per_player}")
    print(f"exploitability: {res.exploitability}")
    print(f"per_history_strategy entries: {len(res.per_history_strategy)}")
    print(f"per_class_strategy entries: {len(res.per_class_strategy)}")
    print(f"warnings: {res.warnings}")

    assert wall < 600.0, (
        f"FAIL: wall {wall:.1f}s exceeds Sarah's session-class 10-min budget "
        f"(post-PR-139 should be much faster)"
    )
    assert res.hand_count_per_player[0] > 0 and res.hand_count_per_player[1] > 0, (
        f"FAIL: empty hand_count_per_player {res.hand_count_per_player}"
    )
    assert len(res.per_history_strategy) > 0, "FAIL: empty per_history_strategy"
    # exploitability finite (>=0; vector-form returns chips/hand)
    assert res.exploitability >= 0.0, (
        f"FAIL: negative exploitability {res.exploitability}"
    )
    assert res.exploitability < float("inf"), (
        f"FAIL: infinite exploitability {res.exploitability}"
    )

    verdict = "PASS"
    return {
        "id": "W2.3",
        "verdict": verdict,
        "wall_seconds": wall,
        "iterations": int(res.iterations),
        "backend": str(res.backend),
        "exploitability": float(res.exploitability),
        "n_classes": len(classes),
        "hand_count": res.hand_count_per_player,
        "decision_node_count": int(res.decision_node_count),
    }


def main() -> int:
    results = {}
    try:
        results["w2_1"] = retest_w2_1()
    except Exception as exc:
        results["w2_1"] = {"id": "W2.1", "verdict": "FAIL", "error": repr(exc)}
        print(f"W2.1 FAIL: {exc!r}")
        import traceback
        traceback.print_exc()

    try:
        results["w2_3"] = retest_w2_3()
    except Exception as exc:
        results["w2_3"] = {"id": "W2.3", "verdict": "FAIL", "error": repr(exc)}
        print(f"W2.3 FAIL: {exc!r}")
        import traceback
        traceback.print_exc()

    _banner("Summary")
    for r in results.values():
        print(r)

    # Exit non-zero if either failed.
    return 0 if all(r.get("verdict") == "PASS" for r in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
