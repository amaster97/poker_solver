"""B10 Phase D — W2.2 Sarah Range.diff per-combo persona fixture.

Runs the literal exemplar from
``docs/b10_per_combo_frequency_plan_2026-05-28.md`` §1
("KQo: you 3-bet 0%, GTO 25%") through the public ``parse_range`` /
``Range.diff`` API and prints a per-combo report. Intended as the
human-readable empirical companion to ``tests/test_w2_2_per_combo_diff.py``.

Usage::

    .venv/bin/python scripts_retest/w2_2_per_combo_diff_retest.py

Phase A/B/C must have shipped (PRs #149, #154, #158); Phase D is the persona
verdict reclassification (PARTIAL -> PASS).
"""
from __future__ import annotations

import json
import time
from typing import Any

from poker_solver.range import parse_range


def _summarize(label: str, gto_spec: str, user_spec: str) -> dict[str, Any]:
    t0 = time.perf_counter()
    gto = parse_range(gto_spec)
    user = parse_range(user_spec)
    diff = gto.diff(user)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    weights = sorted({round(c.weight, 6) for c in diff})
    print(f"--- {label} ---")
    print(f"  GTO  spec:  {gto_spec!r}")
    print(f"  USER spec:  {user_spec!r}")
    print(f"  diff combos: {len(diff)}")
    print(f"  distinct weights surfaced: {weights}")
    print(f"  diff.to_string() preview: {diff.to_string()[:80]}...")
    print(f"  wall: {elapsed_ms:.3f} ms")
    print()
    return {
        "label": label,
        "gto_spec": gto_spec,
        "user_spec": user_spec,
        "diff_count": len(diff),
        "distinct_weights": weights,
        "wall_ms": elapsed_ms,
    }


def main() -> int:
    results: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Case 1 — Sarah's literal exemplar
    # ------------------------------------------------------------------
    r1 = _summarize(
        "Case 1: literal exemplar 'KQo: you 3-bet 0%, GTO 25%'",
        gto_spec="KQo:0.25",
        user_spec="AA, KK, QQ, AKs, AKo",
    )
    # Sanity: 12 KQo combos all at 0.25.
    assert r1["diff_count"] == 12, r1
    assert r1["distinct_weights"] == [0.25], r1
    results.append(r1)

    # ------------------------------------------------------------------
    # Case 2 — per-combo partial subtraction (GTO partial vs user partial)
    # ------------------------------------------------------------------
    r2 = _summarize(
        "Case 2: per-combo partial subtraction",
        gto_spec="KQo:0.7, JTs:0.4",
        user_spec="KQo:0.5",
    )
    # Sanity: 16 combos (12 KQo at 0.2 + 4 JTs at 0.4).
    assert r2["diff_count"] == 16, r2
    assert r2["distinct_weights"] == [0.2, 0.4], r2
    results.append(r2)

    # ------------------------------------------------------------------
    # Case 3 — all-unit back-compat (pre-B10 set-membership semantics)
    # ------------------------------------------------------------------
    r3 = _summarize(
        "Case 3: all-unit back-compat (pre-B10 set-membership)",
        gto_spec="AA, KK",
        user_spec="AA",
    )
    # Sanity: 6 KK combos at weight 1.0.
    assert r3["diff_count"] == 6, r3
    assert r3["distinct_weights"] == [1.0], r3
    results.append(r3)

    print("All 3 cases PASS")
    print("JSON dump:")
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
