# v1.3.0 — USAGE.md Draft Addendum (Pre-Stage)

**Status:** Pre-stage. Splice into `USAGE.md` between §5 (Library mode)
and §6 (Known limitations) when v1.3.0 ships with both Option A (Rust
exploitability port) and Option B (aggregator harness). See
`v1_3_range_vs_range.md` for the design rationale and
`v1_3_stress_tests.md` for the acceptance suite.

Target word count: 300-500 words of new user-facing prose.

---

## Proposed splice point

Insert as a new §5.2 immediately after the existing §5 ("Library mode")
content, just before the `---` divider that precedes §6. Keep §5's
spot-id sentence at the end of §5.1 (Library mode's existing
paragraph) and let §5.2 stand on its own.

---

## §5.2 — Range vs range solves (v1.3+)

Up to v1.2.0, every HUNL solve required a concrete combo per player
(`HUNLConfig.initial_hole_cards = ("AhKc", "QdQh")`). v1.3.0 ships
two complementary paths for range-vs-range questions — pick whichever
matches your spot. See §5.1 for the underlying library mode that both
paths cache results into.

### Path A — Full enumeration (empty `initial_hole_cards`)

Pass an empty tuple to `initial_hole_cards` and the solver enumerates
the preflop chance node directly. The Rust exploitability tier
(`--backend rust`) is required for this path; the Python tier is too
slow for interactive use on the 1.6 M-combo enumeration.

```python
from poker_solver import HUNLConfig, HUNLPoker, solve

cfg = HUNLConfig(
    stack_bb=100,
    initial_hole_cards=(),       # signals full enumeration
    flop=("As", "Ks", "7h"),     # 100 BB SRP, BTN c-bet decision
    bet_sizes=(0.33, 0.75),
)
result = solve(HUNLPoker(cfg), iterations=500, backend="rust")
print(result.strategy_at("BTN/cbet"))   # per-hand-class frequencies
```

**Use when:** you have a dense range (~30+ hand classes per side) and
care about exploitability against the full equilibrium. Returns a
true Nash strategy table keyed by infoset.

**Perf:** ~30-60 s for the bench config (500 iters, 2 bet sizes, river
start) on Apple Silicon; flop-start configs depend on abstraction
settings (see `--abstraction-mode` flag).

### Path B — Aggregator harness (`solve_range_vs_range`)

For range editors and 13×13 matrix output, use the aggregator. It
iterates per hand class, solves each as a concrete-vs-concrete
subgame, and returns reach-weighted frequencies.

```python
from poker_solver import solve_range_vs_range, HUNLConfig, Range

cfg_template = HUNLConfig(stack_bb=100, flop=("4c","5d","6h"),
                          bet_sizes=(0.33, 0.75))
hero_range    = Range.from_pio("22+,A2s+,A8o+,K9s+,KTo+,Q9s+,J9s+")
villain_range = Range.from_pio("QQ+,AKs,AKo")        # 3-bet range

out = solve_range_vs_range(
    config_template=cfg_template,
    hero_range=hero_range,
    villain_range=villain_range,
    iterations=500,
    aggregate="class",           # 169 buckets; "combo" for suit-aware 1326
)
out.frequencies["AKs"]           # [check, bet33, bet75] for that class
```

**Use when:** the range is sparse, you want per-class output for
display in a UI matrix, or you need the suit-aware blocker-sensitive
combo mode (`aggregate="combo"`).

**Perf:** for sparse ranges (≤ 30 hand classes per side),
Path B finishes in 10-30 s and outpaces Path A's full enumeration.
Above ~50 hand classes the per-class overhead dominates and Path A is
faster.

### Which to pick

- **Default to Path B for UI / chart work.** Output shape maps
  directly to the 13×13 matrix view (PR 10b consumes
  `RangeSolveResult.frequencies`).
- **Default to Path A for headless exploitability work.** True Nash
  table, no per-class aggregation error.
- **Suit-sensitive boards** (paired, monotone, three-flush): use
  `aggregate="combo"` — class mode collapses suit-specific blocker
  effects (see stress test S8 in `v1_3_stress_tests.md`).

Cross-references: §5.1 caches results from either path (spot ID is
deterministic over the config + range pair). §3.2 (river subgame
solve) is unchanged; concrete-combo solves remain the v1.0.0 contract.
Limitations of v1.3.0's range surface land in §6.
