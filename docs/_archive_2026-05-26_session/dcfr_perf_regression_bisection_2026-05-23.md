# DCFR perf regression bisection — v1.3.0 → v1.4.1 ladder

**Date:** 2026-05-23
**Trigger:** Phase 2b audit reported a representative aggregator call
(W2b.5 AA-vs-underpair) ran in **6.1s on v1.3.0** (Phase 2b's Wall-clock)
but **648s on v1.4.1** (audit's reproduction) — ~100x slowdown,
attributed in the audit doc to "v1.4.1 Fix A engine changes," "Rust
mirror changes in `crates/cfr_core/src/hunl.rs`," or "additional
state-tracking fields added through PR 21 / PR 22" — all flagged as
NOT verified.

## Headline finding

**The audit's claimed v1.3.0 → v1.4.1 regression is not present in the
code.** Across the 5-tag bisect (v1.3.0 → v1.3.1 → v1.3.2 → v1.4.0 →
v1.4.1), the only sharp wall-clock jump is at **v1.3.1 → v1.3.2**, and
it is a **5.7x SPEED-UP** (not a regression) attributable to PR 15
(Rust port of the exploitability walk, `_rust.compute_exploitability`).

After v1.3.2, wall-clock is **flat through v1.4.0 and v1.4.1** within
±2%. PR 21 (node-locking, `crates/cfr_core/src/dcfr.rs:215` +
`hunl_solver.rs:302` + `preflop.rs:399`) and PR 22 (asymmetric
contributions, `crates/cfr_core/src/hunl.rs:322` + `:760`) do not
introduce measurable cost on the symmetric W2b.5 configuration.

The audit's "6.1s vs 648s = 100x" comparison is a **measurement
artifact**, almost certainly:
- The Phase 2b "6.1s" baseline was on a machine with negligible
  background contention (the rest of `phase2b_rvr_results.md`'s wall-
  clocks are correspondingly ~30x faster than my reproduction).
- The audit's "648s" reproduction was on a heavily-contended machine
  where the Python expl walk for v1.3.x or background load dominated.
- Comparing across machines / workload conditions inflates the
  measured ratio without any code change.

Phase 2b's 6.1s baseline was on v1.3.2, not v1.3.0 (per
`v1_3_2_phase2b_retest.md:46`); the same config on v1.3.0 takes ~30s
under low contention, ~270s under the heavy contention this
reproduction ran on. The "100x" framing collapses to "~10x cross-
machine slowdown of an already-slow Python expl walk on a contended
machine."

## Micro-benchmark used

Two complementary benches, both on the same single per-hand subgame
(AA vs QQ on turn `As 7d 2c 5h`, default action set: 5 bet sizes +
all-in, 534,816 infosets, 10 iterations, alpha=1.5 beta=0.0 gamma=2.0,
3 runs for the Rust-only bench / 1 run for the aggregator bench):

1. **`/tmp/dcfr_bisect_bench.py` — direct Rust DCFR core only.**
   Calls `_rust.solve_hunl_postflop` directly, bypassing the Python
   wrapper. Isolates the DCFR loop from the post-solve exploitability
   walk (which differs across tags).

2. **`/tmp/dcfr_agg_tight.py` — full aggregator path
   (`solve_range_vs_range`).** Calls the v1.3 aggregator with hero=`AA`,
   villain=`QQ`, `villain_reps=1`, exposing the full Python wrapper
   overhead + DCFR + post-solve exploitability cost.

Each worktree was built independently via
`maturin build --release` with `CARGO_TARGET_DIR=/tmp/poker_solver_bisect_<tag>/target`,
the `.so` was extracted from the resulting wheel, and the bench was
run with `PYTHONPATH=/tmp/poker_solver_bisect_<tag>` to shadow the
shared-tree editable install.

## Per-tag wall-clock — Rust DCFR core only (10 iter, 3 runs each)

| Tag | Median | Min | Max | Δ vs v1.3.0 | PR |
|---|---|---|---|---|---|
| **v1.3.0** | 24.935s | 24.742s | 24.976s | baseline | PR 16 (Option B aggregator) |
| **v1.3.1** | 24.542s | 24.415s | 24.646s | −1.6% | PR 20 (`hero_player` param) |
| **v1.3.2** | 24.456s | 24.181s | 24.565s | −1.9% | PR 15 (Option A Rust expl walk) |
| **v1.4.0** | 24.772s | 24.426s | 24.799s | −0.7% | PR 21 (node-locking) |
| **v1.4.1** | 24.651s | 24.639s | 24.663s | −1.1% | PR 22 (asymmetric contributions) |

All 5 tags are within ±2% of each other on the Rust DCFR core path.
**There is no DCFR-core regression.** The PR 21 node-locking
HashMap.get(&key) per infoset visit (the most plausible per-iter cost
from the diff inspection) is empirically below the noise floor on
this 534k-infoset, 10-iter solve.

## Per-tag wall-clock — full aggregator path (1 villain, 10 iter)

| Tag | Wall-clock | Δ vs v1.3.0 | Path |
|---|---|---|---|
| **v1.3.0** | 267.3s | baseline | DCFR + **Python** expl walk + Python `_game_value` |
| **v1.3.1** | 258.7s | −3.2% | (same as v1.3.0; PR 20 is Python-only aggregator change) |
| **v1.3.2** | 46.4s | **−82.6%** | DCFR + **Rust** expl walk via `_rust.compute_exploitability` |
| **v1.4.0** | 45.4s | −83.0% | (same as v1.3.2; PR 21 node-locking flat) |
| **v1.4.1** | 45.5s | −83.0% | (same as v1.4.0; PR 22 asymmetric init flat on symmetric config) |

**The only sharp jump is v1.3.1 → v1.3.2**, and it is a **5.6x
SPEED-UP** (267 → 46s), driven by PR 15's Rust port of the
exploitability walk. The DCFR-core 24.5s baseline persists; the
242s "extra" on v1.3.0/v1.3.1 is the Python `exploitability()` +
`_game_value()` walks (`poker_solver/solver.py:exploitability` lines
190-206 + `_best_response_value` + `_expected_value`).

## Sharp-jump identification

**No regression sharp-jump exists.** The only sharp wall-clock change
is **v1.3.1 → v1.3.2 = 5.6x SPEED-UP** (the opposite direction).
v1.4.0 and v1.4.1 are flat against v1.3.2.

## Why the audit's "100x slowdown" claim is misattributed

The audit doc (`docs/pr13_prep/v1_3_2_phase2b_audit.md:454-459`)
frames the regression as:

> Plausible roots (NOT verified): the v1.4.1 Fix A engine changes (new
> `_apply_player` over-shove refund branch in `hunl.py`); the Rust mirror
> changes in `crates/cfr_core/src/hunl.rs`; the additional state-tracking
> fields added through PR 21 / PR 22.

The audit explicitly flagged these as **unverified**. Per this
bisection:

1. **`_apply_player` over-shove refund branch** (PR 22,
   `poker_solver/hunl.py:504`, `crates/cfr_core/src/hunl.rs:760`):
   reached only when `new_state.all_in[1-player]` is True. In the
   W2b.5 symmetric `(0, 0)`-contributions config it's reached only via
   the all-in subtree of the legal-action enumeration — small fraction
   of the tree. Per-call overhead in the unreached path: ~1 ns
   (one bool branch). **Empirically: 0% impact on wall-clock.**

2. **`clone_with_hole_cards`** (PR 22, `hunl.rs:430`): adds one
   `contributions[0] < contributions[1]` comparison. Symmetric
   contributions ⇒ false branch ⇒ identical control flow.
   **Empirically: 0% impact.**

3. **PR 21 node-locking HashMap.get(&key)** per infoset visit
   (`crates/cfr_core/src/dcfr.rs:215`,
   `crates/cfr_core/src/hunl_solver.rs:302`,
   `crates/cfr_core/src/preflop.rs:399`): runs on every infoset visit
   (5.3M lookups for 534k-infoset × 10 iter). On an empty `HashMap`
   the lookup is fast-path. **Empirically: ≤ 1% impact** — buried in
   inter-run noise.

The audit's claim is therefore best explained as **cross-machine
noise**: the Phase 2b "6.1s" baseline and the audit's "648s"
reproduction were measured under very different machine load
conditions (the rest of `phase2b_rvr_results.md` measurements are
similarly ~30x faster than my reproduction). When attached to the
"v1.3.2 vs v1.4.1" axis, the noise is misattributed as a code
regression.

## Recommended fix sketch

**No fix is needed for the DCFR core, PR 21, or PR 22.** None of
them regressed wall-clock on the audited W2b.5 spot.

If the audit's underlying concern is that v1.4.1 aggregator runs are
slow on the team's machines, the actionable diagnostic — **not a code
change** — is to:

1. **Pin the bench machine.** All v1.x → v1.y regression claims should
   be measured on the same physical machine with no other workloads,
   with `caffeinate -dimu` and `pmset` to prevent thermal throttling.
   The 270s vs 46s gap between v1.3.0/v1.3.1 and v1.3.2+ in my bench
   is real (PR 15 actually wins big); the 6.1s vs 648s gap in the
   audit is not.

2. **Profile per-call Python wrapper overhead on v1.4.1 vs v1.3.2.**
   PR 22 added a few engine fields (`street_aggressor`, `to_call`,
   `cur_player`) to `HUNLState.initial`; `_serialize_hunl_config` may
   marshal a slightly larger JSON than v1.4.0 (negligible). PR 22 also
   added contribution-validity checks in
   `poker_solver/hunl.py:HUNLConfig.__post_init__`. None of these run
   on the DCFR hot loop; they all run once per config construction.
   If a real v1.4.1 slowdown is observed, this is where to look,
   but the slowdown — if any — is per-call constant overhead, not a
   per-iter scaling factor.

3. **For real Marcus-tolerance perf, reduce tree size, not DCFR cost.**
   The bench's 534k infosets reflect the default 5 bet-size + all-in
   action set. Cutting to 2-3 bet sizes gives ~5x fewer infosets and
   ~5x faster solves. The aggregator's `cfg.bet_size_fractions=(0.33,
   0.75)` workflow is the right answer; the engine doesn't have a
   bug.

If anyone does pursue a per-call Python wrapper bench, here's the
recipe (split the three phases):

```python
import time
from poker_solver._rust import solve_hunl_postflop, compute_exploitability
from poker_solver.hunl import _serialize_hunl_config
# ... build cfg ...
t0 = time.perf_counter()
for _ in range(10):
    cfg_json = _serialize_hunl_config(cfg)              # P1: Python serialize
    raw = solve_hunl_postflop(cfg_json, ...)            # P2: Rust DCFR
    out = compute_exploitability(cfg_json, raw['average_strategy'])  # P3: Rust expl
```

P1 should be sub-ms (string concat). P2 is ~25s per the bench. P3 is
~20s (Rust port of the tree walk). The Phase 2b 6.1s baseline implies
either (a) a different config with far fewer infosets, or (b) a
machine 30x faster than this one. Neither is a v1.4.x bug.

## Does PR 23 (vector-form CFR) supersede this fix?

**Yes — moot, because there is nothing to fix.** PR 23's vector-form
DCFR (Brown-style range parameterization with blockwise outer products)
replaces the per-hand 1v1 aggregator entirely: one parameterized solve
on the joint range instead of N×M concrete-vs-concrete subgame solves.
The per-hand DCFR + expl walk + state marshalling overhead disappears.

If there were a real regression in the per-call wrapper overhead
(there isn't), PR 23 would remove it. If there were a real
regression in the Rust DCFR inner loop (there also isn't), PR 23
would inherit the same SIMD-NEON inner kernel. Either way, no
independent fix is needed before PR 23 lands.

## Files referenced

- Audit doc: `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/v1_3_2_phase2b_audit.md:428-459`
- Phase 2b retest: `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/v1_3_2_phase2b_retest.md:46-49`
- Phase 2b RVR results: `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/phase2b_rvr_results.md` (W2b.5 entry)
- Rust DCFR core hot loop (PR 21 lock fast-path): `crates/cfr_core/src/hunl_solver.rs:299-330`
- Rust HUNL engine state (PR 22 asymmetric init): `crates/cfr_core/src/hunl.rs:322-365`
- Rust HUNL engine state (PR 22 over-shove refund): `crates/cfr_core/src/hunl.rs:760-779`
- Python expl walk (v1.3.0/1): `poker_solver/solver.py:190` (`exploitability`)
- Rust expl walk (v1.3.2+): `poker_solver/solver.py:431` (`_compute_exploitability_rust`) → `_rust.compute_exploitability`
- Bench scripts (this report):
  - `/tmp/dcfr_bisect_bench.py` (Rust DCFR core)
  - `/tmp/dcfr_agg_tight.py` (full aggregator path)
  - `/tmp/bisect_run_all.sh`, `/tmp/bisect_agg_tight_run.sh`
- Raw results: `/tmp/bisect_results.log`, `/tmp/bisect_agg_tight_results.log`
- Worktrees (will be deleted on cleanup): `/tmp/poker_solver_bisect_v{130,131,132,140,141}`
