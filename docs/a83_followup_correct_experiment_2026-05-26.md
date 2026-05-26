# Correct A83 Nash multiplicity probe — proposed approach (2026-05-26)

**Status:** Proposed (not yet executed). Follow-up to the INVALIDATED
2026-05-26 A83 Track A v1 probe.
**Owner:** Next-session orchestrator.
**Estimated wall-clock:** 30-90 min (per-seed iters * 2 seeds, depending
on iter count chosen).
**Decision rule outcome:** see §6.

---

## 1. Background — why the v1 probe was invalid

The 2026-05-26 A83 Track A v1 probe (`~/Desktop/a83_track_a_run.sh`)
invoked

```
poker-solver solve --backend rust --hunl-mode postflop \
  --board "Ah 8c 3d Tc 6s" --stacks 100 \
  --bet-sizes 33,75,100,150,200 --iterations 200000 \
  --regret-init-noise <0.0 | 1e-9>
```

twice (baseline `noise=0.0` and perturbed `noise=1e-9`). Both runs
finished in ~111 seconds wall-clock and produced 186-byte byte-identical
log files. The CLI path constructs an `HUNLConfig` with
`initial_hole_cards = None`. Inside `crates/cfr_core/src/hunl.rs:533-568`,
`HUNLState::chance_outcomes` returns `Vec::new()` defensively whenever
`hole_cards = None`. The scalar CFR loop's chance branch then iterates
over zero outcomes, returns `[0.0, 0.0]`, and never inserts a single
infoset into `strategy_sum`. The reported exploitability
(`-0.281250 / 13.852756`) is recomputed via `_rust.compute_exploitability`
against an empty strategy map and falls back to `uniform(n_actions)` on
every cache miss (`exploit.rs:472-475`).

**Conclusion:** the v1 probe did not exercise the noise plumbing at all.
The "bit-identical" outcome is the trivial bit-identicality of two
no-op runs — NOT evidence of Nash convergence.

Source-of-truth analysis: `docs/a83_track_a_results_analysis_2026-05-26.md`.

The `--regret-init-noise` flag implementation itself is CORRECT (3 unit
tests in `crates/cfr_core/src/dcfr_vector.rs::tests` PASS, including a
load-bearing epsilon-perturbs-strategy test on a multi-action tree).
The CLI invocation path is what's broken.

---

## 2. Correct entrypoint — `solve_range_vs_range_nash`

The original A83 33pp Brown divergence was measured via
`tests/test_range_vs_range_rust_diff.py` against the `dry_A83_rainbow`
fixture. That test calls `_rust.solve_range_vs_range_rust` — the
vector-form `dcfr_vector.rs` path that DOES populate all decision
infosets up front and DOES respect `--regret-init-noise`. The same
entrypoint is exposed via Python as
`poker_solver.solve_range_vs_range_nash` (per `poker_solver/__init__.py`).

Track A should use the SAME entrypoint that produced the original
divergence numbers — not the scalar fixed-combo `solve_hunl_postflop`
path the v1 probe hit. This eliminates both the no-op bug AND the
path-mismatch concern flagged in `a83_track_a_results_analysis_2026-05-26.md`
§5.

---

## 3. Proposed Python script skeleton

A standalone driver, runnable from project root with `.venv` activated:

```python
# scripts/a83_track_a_probe_v2.py
"""
A83 Track A v2 — corrected Nash-multiplicity probe via vector-form RvR.

Runs the same dry_A83_rainbow fixture used in the original 33pp
investigation, twice: once with regret_init_noise=0.0 (baseline)
and once with regret_init_noise=1e-9 (perturbed). Dumps per-cell
average strategies to JSON, then compares cell-by-cell.

Decision rule:
  - max_per_cell_L1_delta > 0.05  -> Nash multiplicity CONFIRMED
                                     (perturbation lands in a different
                                     equilibrium basin)
  - max_per_cell_L1_delta < 0.01  -> Nash uniqueness LIKELY
                                     (perturbation collapses to same
                                     equilibrium)
  - in between                    -> INCONCLUSIVE; iterate iter count
                                     or perturbation magnitude

Usage:
  python scripts/a83_track_a_probe_v2.py --iterations 50000 \\
    --out-dir /tmp/a83_track_a_v2/
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from poker_solver import solve_range_vs_range_nash
from poker_solver.fixtures import load_dry_a83_rainbow  # adjust import to actual location


def run_one(noise: float, iterations: int, seed: int = 42) -> dict:
    """Run a single solve and return per-cell average_strategy dict."""
    fixture = load_dry_a83_rainbow()
    t0 = time.time()
    result = solve_range_vs_range_nash(
        board=fixture.board,
        hero_range=fixture.hero_range,
        villain_range=fixture.villain_range,
        starting_pot=fixture.starting_pot,
        effective_stack=fixture.effective_stack,
        bet_sizes=fixture.bet_sizes,
        raise_cap=fixture.raise_cap,
        iterations=iterations,
        backend="rust",
        regret_init_noise=noise,
        rng_seed=seed,
    )
    elapsed = time.time() - t0
    return {
        "noise": noise,
        "iterations": iterations,
        "seed": seed,
        "elapsed_s": elapsed,
        "average_strategy": result.average_strategy,
        # average_strategy is dict[infoset_key, dict[action, dict[hand, prob]]]
        # ~1081 hands per infoset for vector form
    }


def compare(baseline: dict, perturbed: dict) -> dict:
    """Compute per-cell L1 delta between baseline and perturbed."""
    bs = baseline["average_strategy"]
    ps = perturbed["average_strategy"]
    common_keys = set(bs.keys()) & set(ps.keys())
    deltas = {}
    for key in sorted(common_keys):
        # Per-hand L1 between baseline and perturbed action distributions
        b_actions = bs[key]
        p_actions = ps[key]
        for action in sorted(set(b_actions) | set(p_actions)):
            b_hands = b_actions.get(action, {})
            p_hands = p_actions.get(action, {})
            for hand in sorted(set(b_hands) | set(p_hands)):
                b_prob = b_hands.get(hand, 0.0)
                p_prob = p_hands.get(hand, 0.0)
                deltas[(key, action, hand)] = abs(b_prob - p_prob)
    return {
        "n_cells": len(deltas),
        "max_delta": max(deltas.values()) if deltas else 0.0,
        "mean_delta": (sum(deltas.values()) / len(deltas)) if deltas else 0.0,
        "p95_delta": sorted(deltas.values())[int(0.95 * len(deltas))]
                     if deltas else 0.0,
        "top_10_cells": sorted(
            deltas.items(), key=lambda kv: -kv[1]
        )[:10],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=50_000)
    ap.add_argument("--noise", type=float, default=1e-9)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-dir", type=Path, default=Path("/tmp/a83_track_a_v2"))
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[a83-v2] baseline (noise=0.0) ...", flush=True)
    baseline = run_one(0.0, args.iterations, args.seed)
    (args.out_dir / "baseline.json").write_text(
        json.dumps(baseline["average_strategy"], indent=2)
    )
    print(f"[a83-v2]   elapsed={baseline['elapsed_s']:.1f}s "
          f"infosets={len(baseline['average_strategy'])}", flush=True)

    print(f"[a83-v2] perturbed (noise={args.noise}) ...", flush=True)
    perturbed = run_one(args.noise, args.iterations, args.seed)
    (args.out_dir / "perturbed.json").write_text(
        json.dumps(perturbed["average_strategy"], indent=2)
    )
    print(f"[a83-v2]   elapsed={perturbed['elapsed_s']:.1f}s "
          f"infosets={len(perturbed['average_strategy'])}", flush=True)

    cmp = compare(baseline, perturbed)
    (args.out_dir / "comparison.json").write_text(json.dumps(cmp, indent=2,
                                                              default=str))
    print(f"[a83-v2] n_cells={cmp['n_cells']} "
          f"max_delta={cmp['max_delta']:.6f} "
          f"mean_delta={cmp['mean_delta']:.6f} "
          f"p95_delta={cmp['p95_delta']:.6f}", flush=True)

    # Decision rule
    if cmp["max_delta"] > 0.05:
        verdict = "NASH MULTIPLICITY CONFIRMED"
    elif cmp["max_delta"] < 0.01:
        verdict = "NASH UNIQUENESS LIKELY"
    else:
        verdict = "INCONCLUSIVE"
    print(f"[a83-v2] verdict={verdict}", flush=True)
    return 0 if cmp["n_cells"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

**Note on fixture loading:** `load_dry_a83_rainbow()` is a placeholder.
The actual fixture lives in `tests/conftest.py` (or wherever
`test_range_vs_range_rust_diff.py` resolves it from). Two acceptable
ways to wire this:

- Promote the fixture into a top-level helper in `poker_solver/fixtures.py`
  so the standalone script can import it. (Cleaner, but requires a small
  refactor PR.)
- Inline the fixture construction directly into the script. (Faster,
  matches v1 probe style; copy from the test file.)

**Alternative path:** extend `tests/test_range_vs_range_rust_diff.py`
with a parametric test that runs the same fixture at two noise levels
and asserts the per-cell L1 delta against the decision-rule
thresholds. Add `@pytest.mark.slow` so it doesn't run on every PR.
This avoids the fixture-promotion PR entirely.

---

## 4. Sanity check before launching

Before kicking off the full 50K-iter probe, verify the entrypoint
actually exercises the noise plumbing on a tiny config:

```bash
python -c "
from poker_solver import solve_range_vs_range_nash
# 200-iter smoke on a tiny fixture
r0 = solve_range_vs_range_nash(..., iterations=200, regret_init_noise=0.0, rng_seed=42)
r1 = solve_range_vs_range_nash(..., iterations=200, regret_init_noise=1e-9, rng_seed=42)
assert len(r0.average_strategy) > 0, 'baseline empty'
assert len(r1.average_strategy) > 0, 'perturbed empty'
print(f'r0 infosets: {len(r0.average_strategy)}')
print(f'r1 infosets: {len(r1.average_strategy)}')
"
```

If `len(r.average_strategy) > 0` on both, the noise plumbing is being
exercised and the full probe is safe to launch. If either returns 0,
**stop and diagnose** — the vector-form path may also have a no-op
mode under some config combination (the v1 probe failure should
make us paranoid here).

---

## 5. Wall-clock budget

Reference: the original `test_range_vs_range_rust_diff.py` on the
`dry_A83_rainbow` fixture at the iter count used to measure the 33pp
divergence (need to look this up — likely 2000-5000 iters per the
v1.5 Brown acceptance baseline).

Two-seed budget at common iter counts:

| Iter count | Per-seed est | Two-seed est | Notes |
|---|---|---|---|
| 5,000      | ~3-5 min     | ~6-10 min    | Matches v1.5 Brown acceptance baseline. Should be sufficient for Nash detection. |
| 50,000     | ~30-50 min   | ~60-100 min  | Higher confidence; matches v2 probe ambition. |
| 200,000    | ~2-3 hr      | ~4-6 hr      | Overkill for this question; v1 probe ambition. |

**Recommendation: start at 5,000 iters.** If the result is INCONCLUSIVE,
step up to 50,000. The original 33pp divergence was already visible at
whatever iter count the v1.5 acceptance test ran — so the equilibrium
the probe is measuring is already converged at that scale.

---

## 6. Decision rule — outcome routing

Per `feedback_nash_multiplicity_acceptance.md` and the original Track A
setup doc §6 (`docs/a83_track_a_setup_2026-05-26.md`):

| max_per_cell_L1_delta | Verdict | A83 33pp gap status |
|---|---|---|
| ≥ 0.05 | **Nash multiplicity CONFIRMED** | Type-B (semantic, acceptable Nash multiplicity at deep-cap indifference). A83 closed. |
| ≤ 0.01 | **Nash uniqueness LIKELY** | 33pp gap implicates an unidentified THIRD root cause beyond terminal-utility (NOT-A-BUG'd) and tree-shape (analyzed). Re-open the root-cause investigation. |
| 0.01-0.05 | **Inconclusive** | Run again at higher iter count + larger perturbation (1e-6, 1e-3). If still inconclusive, accept as informational. |

The decision rule is symmetric: both outcomes are publishable. The point
of the probe is to discriminate hypotheses, not to confirm one.

---

## 7. Why not just relaunch via the CLI?

Two options were considered for the CLI surface (per
`a83_track_a_results_analysis_2026-05-26.md` §6 REPAIR):

1. **CLI validation guard.** Add a fail-fast check in
   `crates/cfr_core/src/hunl_solver.rs::validate_config` for
   `config.initial_hole_cards.is_none() && config.starting_street ==
   Street::River`. Suggest the `solve_range_vs_range_nash` Python entry
   in the error message. **This SHOULD ship**, but is independent of the
   Track A retest — it's about preventing future agents (and users)
   from hitting the same no-op silently.
2. **New CLI subcommand.** `poker-solver range-vs-range` that routes to
   `_rust.solve_range_vs_range_rust`. Real product gap; out-of-scope for
   the Track A retest. Should be a separate PR.

Track A retest does NOT depend on either CLI repair. It uses the Python
entrypoint directly.

---

## 8. References

- v1 probe INVALIDATION analysis (source of truth):
  `docs/a83_track_a_results_analysis_2026-05-26.md`
- v1 probe setup (background context):
  `docs/a83_track_a_setup_2026-05-26.md`
- Original 33pp divergence investigation:
  `docs/a83_deep_cap_root_cause_investigation.md`
- v1.5 Brown acceptance baseline (entrypoint reference):
  `tests/test_range_vs_range_rust_diff.py`
- Public Python API entrypoint:
  `poker_solver/__init__.py::solve_range_vs_range_nash`
- Vector-form solve (the actual underlying Rust path):
  `crates/cfr_core/src/dcfr_vector.rs`
- Noise plumbing (vector form, where the probe needs to exercise):
  `crates/cfr_core/src/dcfr_vector.rs:207-241`
- Noise plumbing unit tests (PASS evidence):
  `crates/cfr_core/src/dcfr_vector.rs:1162-1184` (zero reproducibility)
  `crates/cfr_core/src/dcfr_vector.rs:1199-1255` (epsilon perturbs)
  `crates/cfr_core/src/dcfr_vector.rs:1262-1291` (seed changes outcome)
- Decision-rule framing:
  `feedback_nash_multiplicity_acceptance.md` (memory rule)
