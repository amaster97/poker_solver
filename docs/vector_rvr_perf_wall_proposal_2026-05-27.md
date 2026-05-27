# Vector-form RvR perf-wall proposal (v1.8.2 candidate) — task #39 / HIGH-2

**Date:** 2026-05-27
**Author:** Decision-packet research agent (no code change in this PR; user picks the option).
**Companion PR:** `proposal/vector-rvr-perf-wall-2026-05-27`
**Sister proposal:** PR #99 (DCFR α-guard, HIGH-1 from the same iter 6 retry batch).
**Source finding:** `docs/perpetual_qa_findings_2026-05-27.md:1597-1627,1669-1680` (iter 6 retry HIGH-2).

---

### Finding

`_rust.solve_range_vs_range_rust` on a river fixture with `initial_hole_cards=()`
(empty — i.e. the full 1326-collapsed-by-board hand vector per player; 1081 hands
on a 5-card board) is pathologically expensive on M-series hardware. QA iter 6
retry observed 200 iters running >14 min at 100% CPU before manual SIGKILL, and
even 20 iters did not complete in 5 min (`docs/perpetual_qa_findings_2026-05-27.md:1597-1604`).
The API contract is correct — it accepts a serialized `HUNLConfig` JSON + scalar
`iter,α,β,γ` args without raising; the problem is purely the per-iteration cost,
not a hang. **Distinct from iter 6 LOW-26** (Python aggregator sampling
fan-out); this is the Rust vector kernel's per-node O(hand_count²) enumeration.

---

### Profile data

Profile run today on the exact iter 6 retry fixture
(`AhTcTh4d9s`, pot=400, 20 BB, `bet_size_fractions=(0.5, 1.0)`,
`postflop_raise_cap=3` default, `initial_hole_cards=()`):

| iterations | wall (s) | s/iter | extrapolated 200-iter |
|---|---|---|---|
| 1 | 37.1 | 37.1 (incl. setup) | — |
| 3 | 77.9 | 25.96 | **5,191 s ≈ 86 min** |

Tree shape from the 1-iter run: `decision_node_count = 30`,
`hand_count_per_player = [1081, 1081]`, `strategy_entry_count = 32,430`.

**Cost-model sanity check.** Compare against the v1.5.1 PoC
(`docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md:50`): 1000 iter on a
15-hand × 15-hand river spot ran in 3.6 s (3.6 ms / iter). Scaling by
`(1081 / 15)² ≈ 5,193` yields ≈ 18.7 s / iter, the same order of magnitude
as measured. The cost is **mathematically expected** for the algorithm we
ship: O(hand_count² × decision_nodes × terminal-leaf eval) at the showdown +
fold leaves (`crates/cfr_core/src/dcfr_vector.rs:683-710` — the
`terminal_value_vector` inner double-loop walks every `(hp, ho)` pair). It
is **not** a bug (no hang, no quadratic blowup beyond the O(N²) the algorithm
inherently has). The kernel already runs cross-platform SIMD
(NEON on aarch64 — `crates/cfr_core/src/simd.rs:238-410` PR 61/63/70/71),
so the easy 4-8× speedup from a SIMD pass **has already been collected**.

**Per-iter cost breakdown (qualitative, not flame-graphed).** Reading
`crates/cfr_core/src/dcfr_vector.rs:333-524`:
- Per terminal leaf hit: 1081 × 1081 ≈ 1.17M (hp, ho) pairs evaluated, each
  doing a blocker check + `terminal_utility` call
  (`crates/cfr_core/src/dcfr_vector.rs:674-711`).
- Per decision node: 1081-element `compute_strategy` row scan, SIMD'd
  (`dcfr_vector.rs:255-265` → `simd::compute_strategy_row`).
- Per own-decision update: SIMD `update_regret_sum_vector` +
  `update_strategy_sum` per row (`dcfr_vector.rs:489-518`).
- 30 decision nodes, walked twice per iter (player-alternating —
  `dcfr_vector.rs:543-549`). Two full tree walks per iteration.

The dominant term is the terminal-leaf O(N²) double-loop, not the regret
update (which is O(N × A) with NEON throughput of 2 f64 / cycle). This is
the same shape Brown's reference C++ has in `references/code/noambrown_poker_solver/cpp/src/trainer.cpp:147-159`
(MIT) and the same O(N²) cost (Brown ships it as load-bearing reference).

---

### Surface area — who can trigger this path?

`solve_range_vs_range_rust` is exposed at the PyO3 boundary at
`crates/cfr_core/src/lib.rs:436-520` and registered as `_rust.solve_range_vs_range_rust`
at `crates/cfr_core/src/lib.rs:530`. Three call paths reach it:

1. **`poker_solver.solve_range_vs_range_nash`** (the Python wrapper) —
   `poker_solver/range_aggregator.py:878-1114`. **ALWAYS passes explicit
   `p0_holes` / `p1_holes` lists** built from the user's hand-class set
   (`poker_solver/range_aggregator.py:1024-1029, 1041-1049`). The hand vector
   per player is the *class-expanded* combo count (typically 6-200 combos),
   NOT the full 1081-hand river deck. This path **does not hit the perf wall**
   for typical user inputs (8-15 classes → 50-200 combos).

2. **Direct PyO3 calls from tests / advanced users** — e.g. the QA iter 6
   retry script `/tmp/perpetual_qa_iter6_retry_rvr_rust_diff.py` which calls
   `_rust.solve_range_vs_range_rust(cfg_json, 20, 1.5, 0.0, 2.0)` with **no**
   `p0_holes`/`p1_holes` args. The diff test `tests/test_range_vs_range_rust_diff.py:309,433`
   exists only in 5-hand and 10-hand variants — the test author deliberately
   avoided the full deck (`tests/test_range_vs_range_rust_diff.py:240-241`
   notes "47-card deck the all_pairs list has 1081").

3. **CLI** — does NOT expose this path (`poker_solver/cli.py:105-122`
   explicitly redirects `--hunl-mode postflop --backend rust` users to the
   Python `solve_range_vs_range_nash` API). The CLI HARD-FAILs on this
   combination.

4. **GUI** — `ui/state.py:1265,1296` routes RvR mode through
   `poker_solver.range_aggregator.solve_range_vs_range` (the **blueprint
   aggregator**, NOT the Nash path). The GUI does **not** call
   `solve_range_vs_range_nash` (the vector-form Nash entry) anywhere; the
   string `solve_range_vs_range_nash` does not appear in `ui/` outside the
   CLI redirect message (verified via repo-wide grep).

**Net surface:** the perf wall is reachable ONLY by users who:
(a) import `poker_solver._rust` directly and (b) omit the `p0_holes` /
`p1_holes` args. Production user surfaces (GUI, CLI, public Python
`solve_range_vs_range` / `solve_range_vs_range_nash`) never reach this
codepath with the full 1081-hand vector. The "200 iter > 14 min" QA finding
is on a synthetic test path, not a user-facing one.

---

### Reference comparison — what do production solvers do?

- **`references/code/postflop-solver`** (AGPL — we cannot adopt code, only
  observe behavior) uses Rayon parallelism across action children
  (`references/code/postflop-solver/src/utility.rs:10-37`,
  `#[cfg(feature = "rayon")]`). It also engages EMD-bucketing on hand
  vectors so the inner dimension is ~200-1000 buckets, not 1326 lossless
  combos. PioSolver / GTO+ follow the same pattern (per public docs).
- **Brown's reference** (`references/code/noambrown_poker_solver/cpp/src/trainer.cpp:138-209`,
  MIT) is single-threaded and uses the full hand vector — same shape as
  ours. Brown documents in the trainer that river-only ranges of moderate
  size are the intended workload.
- **Our `dcfr_vector.rs:52`** says: *"v1.5.1 will plug EMD bucketing into
  the hand-vector dimension"* — this is a known follow-up but has not
  shipped. Bucketing is the load-bearing optimization production solvers
  rely on for interactive use; we have not yet engaged it on the vector
  form.

So: the cost we measured is **algorithmically expected** for the un-bucketed
vector form. The "fast on river" expectation comes from class-trimmed
inputs (the user passes 15 classes → ~80 combos, not 1081). Once the input
shape matches what PioSolver actually solves (a trimmed range, not the full
deck), our wall time is competitive with Brown's reference. **The perf
wall only appears for synthetic full-deck inputs that no production user
sends.**

---

### Options

#### Option A — Document the iter limit in API docs.

Add a warning to the `solve_range_vs_range_rust` PyO3 docstring
(`crates/cfr_core/src/lib.rs:395-422`) and the `dcfr_vector.rs` module
docstring (`crates/cfr_core/src/dcfr_vector.rs:1-54`):

> "Calling with `p0_holes=None, p1_holes=None` enumerates the full
> C(deck − board, 2) hand vector (typically 1081 hands on a 5-card board).
> Per-iter cost scales as O(hand_count² × decision_nodes); a 200-iter
> postflop river run with the full deck takes ~85 min single-threaded on
> M-series. For interactive use, pass explicit `p0_holes` / `p1_holes`
> trimmed to the user's actual range (typical: 50-200 combos)."

Also add a note to the Python wrapper docstring at
`poker_solver/range_aggregator.py:878-947` (the `solve_range_vs_range_nash`
function), reminding that this wrapper already does class-trimming and is
the recommended interactive entry-point.

- **Files touched:** 2 Rust docstrings + 1 Python docstring. ~30 lines.
- **Effort:** ~30 min (just typing; no logic change).
- **Pros:** Zero risk. Zero code change. Discoverable via `help()` / IDE
  hover. Honest framing of an algorithmic invariant.
- **Cons:** Leaves the foot-gun in place. The QA iter 6 retry script would
  still hit it (writers of test scripts don't read PyO3 docstrings before
  invoking).

#### Option B — Hard-error in the PyO3 binding when full-deck × river × `iters ≥ N`.

In `crates/cfr_core/src/lib.rs:436-462` (the PyO3 entry's argument-validation
block, after the `hand_lists` unpack but before the `dcfr_vector::solve_range_vs_range_postflop_with_hands`
call), add a precondition:

```rust
// Estimate per-iter cost and refuse if iters × cost would exceed a
// soft ceiling. Full-deck inputs with iters ≥ 50 on river typically
// require ≥ 20 min wall, which violates Sarah's persona budget
// (docs/pr13_prep/persona_time_budgets.md:111).
if hand_lists.is_none() {
    let board_len = config.initial_board.len();
    let estimated_hand_count = match board_len {
        3 => 1176, // C(49, 2)
        4 => 1128, // C(48, 2)
        5 => 1081, // C(47, 2)
        _ => 1326, // preflop fallback
    };
    let estimated_cost_units = (estimated_hand_count as u64).pow(2)
        * (iterations as u64);
    if estimated_cost_units > 50_000_000_000 && !std::env::var("POKER_SOLVER_ACCEPT_LONG_RUNTIME").is_ok() {
        return Err(PyValueError::new_err(format!(
            "solve_range_vs_range_rust would enumerate {} × {} hands × {} iters \
             ≈ {:.1} billion cell-ops single-threaded (≈ {:.0} min wall on M-series). \
             Pass explicit p0_holes / p1_holes trimmed to the user's range \
             (typical: 50-200 combos), or set env POKER_SOLVER_ACCEPT_LONG_RUNTIME=1 \
             to acknowledge.",
            estimated_hand_count, estimated_hand_count, iterations,
            estimated_cost_units as f64 / 1e9,
            estimated_cost_units as f64 / 1e9 * 0.85,  // rough s/billion at measured 26 s/iter
        )));
    }
}
```

The 50G threshold is calibrated against the QA fixture: 1081² × 20 = 23.4G
(within budget, passes), 1081² × 200 = 234G (rejected). User can opt in via
env var.

- **Files touched:** `crates/cfr_core/src/lib.rs` only. ~25 lines of new
  code in the PyO3 entry.
- **Effort:** ~1 h (write + test + adjust threshold against empirical
  data).
- **Pros:** No silent foot-gun. Bypass available (env var) for power users.
  Error message educates the user about the right invocation pattern
  (pass explicit hole lists).
- **Cons:** Adds an API surface (env var). The threshold is heuristic —
  if board / cap / bet-size combos drive `decision_node_count` up (e.g.
  flop with raise_cap=4 has many more nodes), the threshold may be too
  lax on flop spots and too strict on shallow river spots.

#### Option C — Optimize the vector kernel (bucketing + Rayon).

Two sub-options, in order of payoff:

**C1 — Rayon over action children at decision nodes.**
`crates/cfr_core/src/dcfr_vector.rs:400-416` (opp-node) and
`dcfr_vector.rs:442-457` (own-node) walk children sequentially. Switch to
`children.par_iter().enumerate().map(...)` (matching postflop-solver's pattern
at `references/code/postflop-solver/src/utility.rs:18`). On M-series with 8
performance cores, this is **up to 8× speedup** on the dominant per-iter
cost — provided we re-design the regret/strategy_sum write loops to avoid
data races (the current code shares mutable `self.infosets[node_idx]`
across the recursion). Requires either a per-thread regret-delta buffer
that gets merged at the end of each iteration, or `Mutex<VectorInfosetData>`
wrappers (slower). Brown's C++ trainer doesn't parallelize this, but
postflop-solver does, so the algorithmic precedent is established.

- **Files touched:** `crates/cfr_core/src/dcfr_vector.rs` (recursion
  refactor — ~200 LOC delta), `Cargo.toml` (`rayon = "1"` dep already
  present? Need to check).
- **Effort:** 1-2 days. Plus full differential-test re-run
  (`tests/test_range_vs_range_rust_diff.py`) to verify bit-identity is
  preserved (or relax tolerance to ε-floats since Rayon order is
  non-deterministic).
- **Pros:** 4-8× speedup on the actual machine the user has. Brings the
  full-deck 200-iter case from 85 min to ~10-20 min — still slow but
  within Priya's batch budget.
- **Cons:** Significant engineering. Risks breaking bit-identical
  differential tests (`tests/test_range_vs_range_rust_diff.py:74-80`'s
  `CASE_A_BUDGET_S = 60.0`). Threading bugs are subtle. Affects
  load-bearing engine code.

**C2 — EMD-bucketing on the hand vector.**
The `dcfr_vector.rs:52` comment says v1.5.1 will plug EMD-bucketing into
the hand vector — this is the **algorithmically correct** way to make the
full-deck case interactive. Bucketing reduces the inner dimension from
1081 → ~200 buckets, giving (1081/200)² ≈ 29× speedup. Buckets are
already built and used elsewhere (`crates/cfr_core/src/abstraction.rs`).
Plumbing them into `dcfr_vector.rs::EvalContext::from_root` (currently
hardcoded to lossless C(47, 2)) is a 500-LOC change.

- **Files touched:** `crates/cfr_core/src/dcfr_vector.rs::EvalContext`
  build path (~300 LOC), terminal-leaf eval (`terminal_value_vector`,
  ~100 LOC), output dict key emission (`build_average_strategy`, ~50
  LOC), plus a Python `solve_range_vs_range_nash` `use_buckets=True`
  flag (~50 LOC).
- **Effort:** 1-2 weeks. Plus convergence-quality testing (does the
  bucketed strategy match the lossless strategy?). EMD-bucketing is the
  load-bearing optimization commercial solvers ship.
- **Pros:** 20-30× speedup, brings the full-deck case to ~3-5 min wall —
  Sarah-budget compliant. Reuses already-built abstraction infrastructure.
- **Cons:** Two weeks. Affects engine code. Convergence quality risk
  (bucketing loses information; whether it preserves Nash on dry vs wet
  boards depends on bucket count). The v1.5.1 follow-up has been
  deferred since v1.5.0; the user has been content with class-trimmed
  invocation in the meantime.

#### Option D — Accept as known limit; route GUI to scalar chance-enum path.

Already true. The GUI calls `range_aggregator.solve_range_vs_range`
(blueprint aggregator), not the vector-form Nash, per
`ui/state.py:1265,1296`. The CLI HARD-FAILs on `--hunl-mode postflop
--backend rust` and redirects to the Python `solve_range_vs_range_nash` API
per `poker_solver/cli.py:105-122`. The vector-form Nash path is the
"power user" entrypoint; the foot-gun is reachable only by users who skip
the wrappers and call `_rust.solve_range_vs_range_rust` directly. **Zero
code change required for the user-facing surfaces.**

The remaining question is: should we add a docstring warning anyway, since
test authors / power users will still hit the foot-gun?

- **Files touched:** none (status quo).
- **Effort:** 0 (already shipped).
- **Pros:** Zero risk. Production GUI users / CLI users / aggregator users
  all already get fast solver behavior (the aggregator at `villain_reps=1`
  on river runs in 0.06 s per iter 6 test 6,
  `docs/perpetual_qa_findings_2026-05-27.md:1674-1676`).
- **Cons:** The foot-gun remains for direct `_rust` callers. QA test
  authors writing new probes will trip it again. Doesn't help when v1.5.1's
  preflop RvR ships — the full 1326-combo preflop case will have the same
  shape and require this analysis re-done.

---

### Recommendation

**Option A + Option D.** Ship the docstring warning (A) and explicitly
document that the production user-facing path (GUI / CLI / aggregator) is
already routed away from the foot-gun (D). Do NOT implement Option B
(synthetic threshold-and-block) — it's an API-surface tax for a path no
real user hits, and the threshold is heuristic enough to mis-classify
shallow river inputs. Do NOT implement Option C now — the cost is **not
buggy**, it's the inherent O(N²) of the algorithm, and the v1.5.1
EMD-bucketing follow-up (C2) is the real fix, scheduled but not yet
prioritized.

**Rationale.**

1. **The cost is mathematically expected, not buggy.** Profile confirms
   linear in iterations and quadratic in hand count, with the constant
   factor consistent with the v1.5.1 PoC's measured ms/iter scaled by
   hand-count². NEON SIMD is already engaged on the hot kernels. Brown's
   reference (the load-bearing MIT prior art) ships the same un-parallelized
   O(N²) and is content with it for un-bucketed inputs.

2. **The foot-gun is not on the user-facing surface.** GUI, CLI, and the
   `solve_range_vs_range_nash` Python wrapper all class-trim before
   calling. The only way to hit the wall is to import `_rust` directly
   and skip `p0_holes` / `p1_holes` — that's a 3-line Python script,
   typically a test author or someone exploring the binding. A docstring
   warning is the right response for that audience.

3. **Optimization is real engineering with known prior art (Option C),
   but the user has not asked for it yet.** The v1.5.1 EMD-bucketing
   plumbing is documented at `crates/cfr_core/src/dcfr_vector.rs:48-52`
   and `crates/cfr_core/src/dcfr_vector.rs:902-907` as a deferred
   follow-up. Pulling it forward to v1.8.2 is a 1-2 week investment and
   trades convergence quality for speed — a real product decision the
   user should make explicitly, not a "fix this bug" decision.

4. **Option B has the worst tradeoffs.** It adds a new env var (`POKER_SOLVER_ACCEPT_LONG_RUNTIME`),
   a heuristic threshold that will mis-classify, and friction for
   power users — all in exchange for protecting an audience (direct
   `_rust` callers) who can already read the docstring.

If the user objects to A+D and wants a code change, the next-best is
**C1 (Rayon)** — smaller blast radius than C2, no convergence-quality
risk, captures 4-8× speedup. C2 (bucketing) should wait for the v1.5.1
scope it was originally planned for.

---

### Test plan

Per option, the verification gate would be:

**Option A (docs).**
- `cargo doc --no-deps && rustdoc --check` passes.
- `python -c "from poker_solver import _rust; help(_rust.solve_range_vs_range_rust)"`
  shows the warning text.
- Spot-check that the wording matches the measured numbers (37 s/iter
  on the QA fixture).

**Option B (HARD-FAIL).**
- New `tests/test_perf_wall_guard.py` — invoke
  `_rust.solve_range_vs_range_rust(cfg, 200, 1.5, 0.0, 2.0)` with full
  river fixture, assert it raises `ValueError` matching the threshold
  message.
- Same test with `POKER_SOLVER_ACCEPT_LONG_RUNTIME=1` in env — assert
  it proceeds (then early-terminate with a small `iterations=1` for CI
  time budget).
- Existing `tests/test_range_vs_range_rust_diff.py` (5-hand and
  10-hand Case A/B) must still pass — the threshold should NOT trip
  on class-trimmed inputs.

**Option C1 (Rayon).**
- `cargo test --release -p cfr_core` passes (NEON unit tests, existing
  vector tests).
- `pytest tests/test_range_vs_range_rust_diff.py::test_case_a -xvs`
  passes — bit-identical (or ε-close, per chosen merge semantics).
- Bench: run the QA fixture at iter=10, expect ≤ 10 s × 10 / 8_cores ≈
  30 s wall (vs 260 s sequential).
- Memory profile: confirm per-thread regret buffers don't blow the
  16 GB envelope (`spec §4`).

**Option C2 (bucketing).**
- New `tests/test_dcfr_vector_bucketed_convergence.py` — solve a
  fixture twice (bucketed vs lossless), compare exploitability;
  bucketed should be within 10% of lossless on a dry board.
- Existing `tests/test_v1_5_brown_apples_to_apples.py` Brown gauntlet
  re-run on bucketed inputs.
- Bench: full 1081-hand river at 200 iter, expect ≤ 3-5 min wall.

**Option D (no-op).**
- N/A — nothing changes. The QA HIGH-2 ticket gets closed with the
  classification "expected algorithmic cost; user surfaces already
  routed around the wall."

---

### References

- QA finding: `docs/perpetual_qa_findings_2026-05-27.md:1597-1627,1669-1680`
- Algorithm: `crates/cfr_core/src/dcfr_vector.rs:1-54,322-524,674-711`
- PyO3 entry: `crates/cfr_core/src/lib.rs:395-520`
- Python wrapper: `poker_solver/range_aggregator.py:878-1114`
- GUI routing: `ui/state.py:1240-1326`
- CLI hard-fail redirect: `poker_solver/cli.py:105-122`
- v1.5.1 EMD-bucketing follow-up: `crates/cfr_core/src/dcfr_vector.rs:48-52,902-907`
- Persona time budgets: `docs/pr13_prep/persona_time_budgets.md:107-118`
- Reference solver (parallelism): `references/code/postflop-solver/src/utility.rs:10-37`
- Reference solver (Brown, MIT, single-threaded): `references/code/noambrown_poker_solver/cpp/src/trainer.cpp:138-209`
- v1.5.1 PoC perf data: `docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md:50`
- v1.7.0 production perf data: `docs/persona_test_results/W3_5_post_v1_7_0_wider_range_result.md:69` (15-class, 3000 iter, 507 s wall)
- Type D timeout precedent: `docs/persona_test_results/W2_1_post_v1_7_0_result.md:6-7,99-110`
- Sister proposal (HIGH-1): PR #99 (`proposal/dcfr-alpha-guard-2026-05-27`)
