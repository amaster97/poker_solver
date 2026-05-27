# v1.5.1 Spec — Python `solve_hunl_postflop` delegates to Rust vector-form CFR (task #182)

**Status:** spec-only, read-only investigation. Author: spec agent (2026-05-23). Orchestrator approves and spawns implementer separately, AFTER PR 23 (`pr-23-rust-dcfr-widening`) lands as v1.5.0.

**Pre-condition:** PR 23 must ship first. PR 23 lands `_rust.solve_range_vs_range_rust` PyO3 entry per `crates/cfr_core/src/lib.rs:417-503` (in the PR 23 worktree at `/Users/ashen/Desktop/poker_solver_worktrees/pr-23-rust-dcfr-widening/`). Task #182 wires the existing Python `solve_hunl_postflop` to that new binding.

**Goal:** Close the chance-enum-at-root Python perf cliff AND the Brown strategic-parity gap by making `solve_hunl_postflop(..., initial_hole_cards=())` automatically route to PR 23's Rust vector-form CFR. Caller code does not change; the function transparently selects the correct backend.

**Scope honesty.** Per `docs/brown_apples_to_apples_2026-05-23.md` §6a Recommendation #3 and `docs/leg13_v1_5_0_ship_plan.md` §9, this delegate closes BOTH the runtime cliff (W4.3 BLOCKED-PERF) and — because we delegate to vector-form CFR, not to the chance-enum Rust scalar — the algorithmic gap to Brown. A perf-only delegate (route to Rust scalar `solve_hunl_postflop` on chance-enum-at-root) would NOT close the algorithmic gap and is explicitly out of scope.

---

## 1. Problem statement (concrete code citations)

The Python tier exposes `solve_hunl_postflop` at `poker_solver/hunl_solver.py:100-226`. Its dispatch is unconditional:

- Line 165: `_validate_postflop_config(config)` — accepts `initial_hole_cards=()` without complaint (no scope check for chance-enum-at-root).
- Line 182: `game = HUNLPoker(effective_config)` — constructs the standard Python game object.
- Line 192: `solver = DCFRSolver(game, **extra_kwargs)` — runs the **scalar** DCFR.
- Line 224: `backend="python"` — always reports the Python backend in the result.

When `config.initial_hole_cards == ()`:

- `HUNLPoker.initial_state` at `poker_solver/hunl.py:303` sets `cur_player = -1` because `not hole` is true.
- The root is a chance node. `HUNLPoker.chance_outcomes` at `poker_solver/hunl.py:346-351` returns either:
  - `_enumerate_preflop_hole_outcomes()` (1326 hole-card pairs, preflop) — `hunl.py:350, 666`
  - `_board_card_outcomes(state)` (≤48 board cards, postflop with no hole cards) — `hunl.py:351, 651`
- `DCFRSolver._cfr` at `poker_solver/dcfr.py:174-184` walks each chance child sequentially, recursing once per outcome per iteration.

The W4.3 retest documents the wall-clock failure: `docs/persona_test_results/W4_3_v1_4_0_retest.md:111-137` records ~660 s timeout on the river chance-enum config (`docs/pr18_prep/bench_w15.py:25-36`). The W2.3 / W3.4 retests show the same signature at flop scope (`docs/persona_test_results/W2_1_v1_4_1_retest.md:146`).

The Rust `solve_hunl_postflop` PyO3 entry (`crates/cfr_core/src/lib.rs:233-323` in PR 23 worktree) is the **scalar** Rust port — it accepts the same `HUNLConfig` JSON but is bit-for-bit equivalent to the Python scalar DCFR. It does **not** solve the chance-enum-at-root case correctly within budget; this is the existing PR 6 backend that the W4.3 / W2.3 / W3.4 failures already exercise.

PR 23 lands a **second, distinct** PyO3 entry at `crates/cfr_core/src/lib.rs:417-503` (PR 23 worktree): `solve_range_vs_range_rust(config_json, iterations, alpha, beta, gamma, p0_holes=None, p1_holes=None)`. This is the vector-form CFR path — Brown's algorithm bit-for-bit (`crates/cfr_core/src/dcfr_vector.rs:708-815`). It **requires** `config.initial_hole_cards = None` (`dcfr_vector.rs:746-751`) and is postflop-only (`dcfr_vector.rs:753-758`).

**Today (post PR 23, pre task #182):** `solve_hunl_postflop(initial_hole_cards=())` still routes to the slow scalar Python path. The vector binding is standalone — no caller is wired to it yet. Per PR 23 spec §8 Q3 (`crates/cfr_core/src/lib.rs:414-416` PR 23 worktree): *"Python's `solve_range_vs_range` aggregator is NOT rewired to this entrypoint in v1.5.0 — the binding stands alone for downstream code (and v1.5.1) to wire in."*

**Task #182:** wire it.

---

## 2. Proposed API

Three options considered. **Recommendation: Option A (auto-delegate on empty hole cards).**

### Option A — Auto-delegate (RECOMMENDED)

Default behavior change: when `config.initial_hole_cards == ()` AND the config is postflop (Flop/Turn/River) AND PR 23's `_rust.solve_range_vs_range_rust` is importable, `solve_hunl_postflop` **silently** routes to the Rust vector-form CFR. The result still returns as `HUNLSolveResult` (subclass of `SolveResult`), with `backend="rust_vector"` (matching the PyO3 dict's `backend` key at `crates/cfr_core/src/lib.rs:501` PR 23 worktree).

Add an optional `backend` kwarg to `solve_hunl_postflop` for opt-out / explicit control:

```python
def solve_hunl_postflop(
    config: HUNLConfig,
    abstraction: AbstractionTables | None = None,
    iterations: int = _DEFAULT_ITERATIONS,
    target_exploitability: float | None = None,
    memory_budget_gb: float = _DEFAULT_MEMORY_BUDGET_GB,
    *,
    log_every: int | None = None,
    seed: int | None = None,
    dcfr_kwargs: dict[str, Any] | None = None,
    on_progress: OnProgressFn | None = None,
    should_stop: ShouldStopFn | None = None,
    locked_strategies: Mapping[str, Sequence[float]] | None = None,
    backend: str = "auto",  # NEW in v1.5.1: "auto" | "python" | "rust_vector"
) -> HUNLSolveResult: ...
```

Routing matrix:

| `backend=` | `initial_hole_cards=()` | non-empty hole cards |
|---|---|---|
| `"auto"` (default) | `_rust.solve_range_vs_range_rust` (Brown vector CFR) | existing Python scalar DCFR |
| `"python"` | existing Python scalar DCFR (chance-enum-at-root, slow) | existing Python scalar DCFR |
| `"rust_vector"` | `_rust.solve_range_vs_range_rust` | `ValueError` (vector form requires `initial_hole_cards=()`) |

**Pros:**
1. Caller code does not change. Every existing `solve_hunl_postflop(..., initial_hole_cards=())` callsite (tests + library + scripts — see §5 inventory) immediately gets the fast Brown-equivalent path.
2. W4.3 / W2.3 / W3.4 retests can re-run with zero spec edits (the BLOCKED-PERF gate flips on file).
3. Differential tests can pin the slow path explicitly (`backend="python"`) for ground-truth comparison without losing reachability.
4. The `backend` field in `HUNLSolveResult` (`SolveResult.backend`, `poker_solver/solver.py:26`) already exists and is the canonical signal — `"rust_vector"` matches PR 23's naming.

**Cons:**
1. Behavior change for existing chance-enum-at-root callers — but this is what we **want**. Callers that hit the old slow path are not depending on its semantics; they are deferring to a known-broken state. The two algorithms are zero-sum-Nash equivalent at convergence (modulo iteration order); v1.5.1 CHANGELOG documents the routing change.
2. The `backend="rust_vector"` token diverges from the existing `"rust"` token used for the scalar PR 6 Rust port (`poker_solver/solver.py:548, 599, 631`). This is intentional — they are different algorithms and should be distinguishable to downstream tooling.

### Option B — Explicit new function (REJECTED)

Add `poker_solver.solve_range_vs_range_via_rust(config, iterations, ...)` as a separate top-level function; leave `solve_hunl_postflop` untouched.

**Why rejected:**
1. Existing callsites (W4.3 test, W2.3 / W3.4 fixtures, `library.py` serialization path, the `bench_w15.py` perf bench) all hardcode `solve_hunl_postflop`. Wiring requires editing each one — defeats the "transparent delegate" goal of the task.
2. Doubles the public-API surface for a routing concern. The `backend` kwarg pattern already exists at `poker_solver/solver.py:33` (`solve(game, backend=...)`).
3. Goes against the LEG 13 §9 + brown_apples_to_apples §6a recommendation of a **delegate** (not a parallel API).

### Option C — Rewire `solve_range_vs_range` aggregator (REJECTED FOR v1.5.1)

`poker_solver/range_aggregator.py:208` exposes `solve_range_vs_range`, the Pluribus-blueprint workaround. The aggregator iterates per-hand 1v1 solves and aggregates frequencies. Per `range_aggregator.py:24-30`, this is intentionally NOT a true Nash solver.

**Why rejected for v1.5.1:**
1. The aggregator's contract is "approximate fast frequencies for UI surfaces" (`range_aggregator.py:39-50`). Rewiring it changes the public meaning of the function — arguably a MAJOR-version bump trigger.
2. The aggregator has its own test surface (`tests/test_range_vs_range_aggregator.py`) that locks the approximation semantics. Rewiring would either flip those tests or require extensive churn.
3. The aggregator's `hero_player` / `bet_size_fractions` / time-budget knobs do not map 1:1 onto vector-form CFR. The mapping question is non-trivial.

**v1.5.2 or later candidate:** add a `use_rust_tier=True` kwarg to `solve_range_vs_range` per LEG 13 §6 item 3 once the aggregator's per-hand contract is reviewed against the vector path. Out of scope for task #182.

---

## 3. Files touched

### Source

| File | Change |
|---|---|
| `poker_solver/hunl_solver.py:100-226` | Add `backend: str = "auto"` kwarg; add discriminator branch on `config.initial_hole_cards`; route empty-hole-cards path to `_rust.solve_range_vs_range_rust`. |
| `poker_solver/hunl_solver.py:480-482` | Export remains the same (`solve_hunl_postflop` already in `__all__`). |
| `poker_solver/__init__.py:97,127` | No change (function name unchanged). |

### Tests

| File | Change |
|---|---|
| `tests/test_river_diff.py:217-243` | Restore `initial_hole_cards=()` if PR 25 commit 2 revert was not bundled into v1.5.0 (per LEG 13 §6 item 1, the default plan IS to bundle the revert in v1.5.0; if so, this file is already correct). Re-enable as the canonical W4.3 PASS gate. |
| `tests/test_river_diff_self_sanity.py:80-92` | Already uses `initial_hole_cards=()`; no edit needed. Will benefit automatically. |
| `tests/test_exploit_diff.py:115-134` | Already uses `initial_hole_cards=()`; no edit needed. |
| `tests/test_asymmetric_contributions.py:299` | **KEEP `backend="python"` opt-out** — this test deliberately exercises the chance-enum hole-deal machinery (`test_asymmetric_contributions.py:288-314`). Annotate with the opt-out kwarg or accept that the test re-routes through Rust vector CFR. Decision deferred to implementer review; preferred approach: pin to `backend="python"` for behavioral test integrity. |
| `tests/test_hunl_solver_delegate.py` (NEW) | Three cases: (a) `backend="auto"` + `initial_hole_cards=()` returns `backend == "rust_vector"`; (b) `backend="python"` + `initial_hole_cards=()` returns `backend == "python"` (slow path, marked `@pytest.mark.slow`); (c) `backend="rust_vector"` + non-empty hole cards raises `ValueError`. Differential test on a tiny river spot (≤2 hands per player) comparing aggregate frequencies between Rust vector and Python scalar at sufficient iterations to converge. |
| `docs/pr18_prep/bench_w15.py:25-36` | No code change; bench result will improve drastically. Add a result-comparison run with `backend="python"` to keep the historical-slow data point. |

### PyO3 binding compatibility

PR 23 PyO3 signature (confirmed by reading `crates/cfr_core/src/lib.rs:417-503` in the PR 23 worktree):

```
solve_range_vs_range_rust(
    config_json: str,
    iterations: int,
    alpha: float,
    beta: float,
    gamma: float,
    p0_holes: Optional[List[List[int]]] = None,  # differential-test only
    p1_holes: Optional[List[List[int]]] = None,  # differential-test only
) -> dict
```

Returned dict keys: `average_strategy`, `iterations`, `wallclock_seconds`, `decision_node_count`, `strategy_entry_count`, `hand_count_per_player`, `memory_profile`, `backend = "rust_vector"`.

**Production callers omit `p0_holes` / `p1_holes`** (enumeration over deck minus board); the differential-test hook is for v1.5.1's new tests only.

**Marshal differences vs Python `HUNLSolveResult`:**

| `HUNLSolveResult` field | Rust dict source | Marshal note |
|---|---|---|
| `average_strategy` | `average_strategy` | Same `dict[str, list[float]]` shape. Keys are `<hole_string>\|<key_suffix>` per `crates/cfr_core/src/lib.rs:407-408`. |
| `exploitability_history` | Not provided by vector binding | Default to `[]` (matches PR 6 Rust scalar at `solver.py:545`) OR call `_rust.compute_exploitability(config_json, strategy)` at end for a single-entry history. Recommend: single-entry history if `log_every is None` (mirrors `solver.py:622` Python tier pattern); empty history otherwise (per-iter streaming not supported by vector binding). |
| `game_value` | Not provided | Same as above — recompute via `_rust.compute_exploitability` (`crates/cfr_core/src/lib.rs:350-387`) which returns both. |
| `iterations` | `iterations` | Direct copy. |
| `backend` | `"rust_vector"` (literal) | Pass through. |
| `memory_report` | `memory_profile` (PR 23 nested dict) | Map onto `MemoryReport` schema (`poker_solver/profiler/memory.py`). The Rust dict has `total_bytes` / `infoset_count` / `bytes_by_street` / `infoset_count_by_street`; `MemoryReport` has per-street + total fields. Verify schema match in implementer prompt; may require a small adapter `_memory_report_from_rust_profile(...)` in `hunl_solver.py`. |

**`locked_strategies` / `target_exploitability` support:** PR 23's `solve_range_vs_range_rust` does NOT accept `locked_strategies` or `target_exploitability`. If either is non-empty/non-None and `backend="auto"`, the delegate must either (a) fall back to Python with a `UserWarning`, or (b) raise `NotImplementedError`. Recommend (a) — silent fallback with warning preserves the contract that "auto picks the best path". Document in CHANGELOG.

**`abstraction` support:** PR 23 vector CFR does not engage card abstractions in v1.5.0 (`crates/cfr_core/src/dcfr_vector.rs:399-400` PR 23 worktree: "v1.5.0 scope: postflop only — Flop / Turn / River with the full 1326-collapsed-by-board hand vector per player. Preflop and EMD bucketing are v1.5.1"). If `abstraction is not None` and `backend="auto"` and `initial_hole_cards=()`, fall back to Python with `UserWarning`. Document in CHANGELOG.

---

## 4. Cascade impacts

| Item | Pre-#182 state | Post-#182 state | Action |
|---|---|---|---|
| **W4.3 dry_K72_rainbow Brown parity** | BLOCKED-PERF (660 s timeout on chance-enum-at-root Python path) | Should PASS in <60 s on the same hardware (vector CFR completes 50 iterations in well under the persona budget) | Re-run `tests/test_river_diff.py::test_river_parity_vs_brown` after #182 lands. Spec doc: `docs/persona_test_results/W4_3_v1_4_0_retest.md` + re-test under v1.5.1. |
| **W2.3 KK-vs-c-bet** | INCONCLUSIVE-SLOW (defender solve at flop-scope blew past 90 s probe) | Should PASS in <2 min (postflop vector CFR on flop scope is the documented sweet spot of PR 23 perf profile) | Re-run W2.3 retest spec at `docs/pr_proposals/v1_4_1_retest_W2_3_sarah_kk_vs_cbet_range.md`. |
| **W3.4 Daniel MDF** | INCONCLUSIVE-SLOW (~648 s reproduction; task #174 bisection in flight) | Should PASS in <2 min on the chance-enum path. If still slow on the non-chance-enum path, separate task #174 is still relevant. | Re-run W3.4 retest spec at `docs/pr_proposals/v1_4_1_retest_W3_4_daniel_mdf.md`. |
| **PR 25 commit 2 revert (concrete hole cards in `test_river_diff.py`)** | Pre-staged for v1.5.0 per LEG 13 §6 item 1. | Reverted in v1.5.0 (assumed default). If still on `pr-25-river-parity-test-fix` branch, #182 needs to land the revert. | Verify in v1.5.0 ship report. If reverted: no action. If not: bundle the revert into #182's commit chain. |
| **DCFR slowdown task #174** | IN FLIGHT (Phase 2b bisection: PR 22 over-shove refund / PR 21 lock dict.get / PR 15 Rust wiring candidates) | Partially closes — if the slowdown was attributable to chance-enum-at-root path interacting with v1.4.x changes, #182 sidesteps it for that config. The other-config slowdown (non-chance-enum) is independent. | Re-run task #174 bench against v1.5.1 baseline. If chance-enum bench was the dominant signal, close #174. Else keep open. |
| **`untested_workflow_readiness_audit.md` S W2.1 + D W3.5** | Both flagged as "depends on RvR perf resolution" | Should unblock — the same chance-enum-at-root path that's the gating concern is now Rust-routed. | Schedule retest after #182 ships. |
| **PR 28 Brown apples-to-apples acceptance test** | Bundled into v1.5.0; uses `solve_range_vs_range_rust` directly (not `solve_hunl_postflop`). | Independent of #182. | No action. |
| **`docs/pr18_prep/bench_w15.py`** | Measures Python-tier chance-enum exploit walk. | Result drops from 100s+ to single-digit seconds. Bench reframe as "auto-routed" vs "pinned Python" comparison. | Re-baseline; update `docs/pr18_prep/pr_report.md` cross-references if any. |

---

## 5. Risk — API compatibility

**Question:** does any existing caller depend on the chance-enum-at-root semantics (i.e. behavior of the Python scalar DCFR on `initial_hole_cards=()`) specifically?

### Callsite inventory (READ-ONLY scan, 2026-05-23)

| Callsite | Intent | Risk |
|---|---|---|
| `tests/test_exploit_diff.py:131` | Exploit-walk diff fixture (river chance-enum, two bet sizes; from `examples/range_vs_range_river.py`). Asserts that the Rust `compute_exploitability` walk matches Python. Strategy is generated by the same `solve_hunl_postflop` call. | LOW. Both Rust vector CFR and Python scalar DCFR converge to the same Nash; diff tolerance already absorbs iteration-order float noise. Auto-route is safe. If brittleness shows up, pin to `backend="python"` (the diff is between two *exploitability walks*, not between two *training paths*). |
| `tests/test_asymmetric_contributions.py:299` | Tests the `HUNLPoker._apply_chance` dispatch for asymmetric initial contributions (`docs/pr22_prep/...`). Calls `game.chance_outcomes(s)` and `game.apply(s, outcome)` directly — does NOT actually run a solve. The `HUNLConfig` with `initial_hole_cards=()` is constructed but only the state-transition logic is tested. | NONE. This test never calls `solve_hunl_postflop`. The chance-enum config is used only for state machine tests. **No action.** |
| `tests/test_river_diff.py:231` | Brown parity diff test (PR 7 — `dry_K72_rainbow` spot). Calls `_solve_with_our_engine(spot, ...)` which calls `solve_hunl_postflop(..., initial_hole_cards=(), ...)` at line 237. | LOW-TO-NONE. This is the **target callsite** the entire #182 cascade is trying to unblock. Auto-route is the intended behavior. |
| `tests/test_river_diff_self_sanity.py:87` | Self-sanity check on the `HUNLConfig` constructor for the W4.3 river-spot fixture. Does NOT call `solve_hunl_postflop` (config-only smoke test). | NONE. No solve runs. **No action.** |
| `poker_solver/library.py:394` | Inverse-of-`_spot_to_dict` deserialization. Constructs a `HUNLConfig` with `initial_hole_cards=()` when the persisted spot did not include them. Does NOT call `solve_hunl_postflop` directly. | NONE on read path. Indirect downstream: callers of `library.load_spot` then call `solve_hunl_postflop` — those callers are out of `library.py`'s scope. **No action on library.py.** |
| `docs/pr18_prep/bench_w15.py:33` | W1.5 perf bench script. Calls `solve_hunl_postflop(..., initial_hole_cards=(), ...)` for the chance-enum exploit walk. | NONE. Bench will run fast under #182; that IS the bench's point. Reframe in doc to keep historical "slow path" as a reference data point — comparison run via `backend="python"`. |

**Conclusion:** no callsite depends on the slow-path semantics in a way that would regress. `test_asymmetric_contributions.py` looks like a risk on first glance but is state-machine only (no solve). The only "deliberate slow path" exposure is the bench (which is what we want to speed up).

**Gating decision: ship Option A as a behavior change, not a deprecation.** No opt-in flag needed for casual users; `backend="python"` is the escape hatch for the rare case (differential debugging, regression bisection).

---

## 6. Acceptance tests

### Tier 1 — directly unblocks BLOCKED / INCONCLUSIVE persona retests

1. **W4.3 dry_K72_rainbow parity test** (`tests/test_river_diff.py::test_river_parity_vs_brown`)
   - Pre-condition: PR 25 commit 2 reverted (default in v1.5.0 plan §6 item 1) so the test uses `initial_hole_cards=()` again.
   - Expectation: PASS in **<60 s** wall-clock on M-series 16 GB hardware (vs 660 s timeout on v1.4.x).
   - Acceptance gate: `pytest tests/test_river_diff.py -k "test_river_parity_vs_brown" -m parity_noambrown` returns 0.

2. **W2.3 KK-vs-c-bet retest** (`docs/pr_proposals/v1_4_1_retest_W2_3_sarah_kk_vs_cbet_range.md`)
   - Re-run the retest spec verbatim. Expectation: PASS in **<2 min** (defender solve at flop scope under vector CFR).

3. **W3.4 Daniel MDF retest** (`docs/pr_proposals/v1_4_1_retest_W3_4_daniel_mdf.md`)
   - Re-run. Expectation: PASS in **<2 min**.

### Tier 2 — new differential + smoke tests

4. **`tests/test_hunl_solver_delegate.py` (NEW)** — three cases per §3:
   - (a) auto-route on empty hole cards → backend label is `"rust_vector"`.
   - (b) pinned-Python on empty hole cards → backend label is `"python"`, slow (marked `@pytest.mark.slow`).
   - (c) `backend="rust_vector"` with non-empty hole cards → `ValueError`.
   - (d) Differential: tiny river spot (2 hands per player, restricted via `p0_holes` / `p1_holes` PyO3 args), 1000 iterations, compare aggregated action frequencies between Python scalar (chance-enum-at-root) and Rust vector CFR. Tolerance: same `PER_ACTION_TOL = 5e-3` as `tests/test_river_diff.py:60`. Both should converge to the same Nash within tolerance.

5. **Existing differential tests stay green**:
   - `tests/test_exploit_diff.py` — auto-route path validated.
   - `tests/test_asymmetric_contributions.py` — no solve invoked, no risk.
   - `tests/test_range_vs_range_rust_diff.py` (added by PR 23) — separately validates vector CFR vs Python scalar on small fixtures.

### Tier 3 — perf re-baseline

6. **`docs/pr18_prep/bench_w15.py`** — re-run; record new median wall-clock at default `backend="auto"`. Add a second run pinned to `backend="python"` so the historical-slow data point is preserved.

---

## 7. Ship target

**Recommendation: v1.5.1 (separate MINOR ship, ~24-48 h after v1.5.0).**

Per `docs/leg13_v1_5_0_ship_plan.md` §9: defer task #182 to v1.5.1; ship PR 23 as v1.5.0 standalone.

### Why v1.5.1 (separate) over bundling into v1.5.0

1. **PR 23 is already ~1700 LOC of diff** (per LEG 13 §7 risk callout I). Bundling #182 pushes total to ~2700+ LOC — increases audit-cycle time, delays v1.5.0 ship.
2. **MINOR-bump argument is cleanest with separate ships.** v1.5.0 = additive PyO3 entry (no public Python API behavior change → MINOR is uncontroversial). v1.5.1 = behavior change in `solve_hunl_postflop` routing (still MINOR per "additive `backend` kwarg, default routing change documented in CHANGELOG"). Bundling both into one ship muddles the version-semantics story and could be argued as MAJOR.
3. **Two-ship cadence is consistent with project history** (v1.3.0 → v1.3.1 → v1.3.2 over ~3 days; v1.4.0 → v1.4.1 → v1.4.2 over 2 days).
4. **Verification window:** v1.5.0 ships, persona retests confirm `solve_range_vs_range_rust` works correctly. Then v1.5.1 wires it into `solve_hunl_postflop` with one more risk-checkpoint before the W4.3 / W2.3 / W3.4 acceptance retests re-fire.

### Override condition (bundle into v1.5.0)

Only if **all** of the following hold at PR 23 audit-clear time:
- PR 23 implementer voluntarily bundles task #182 commits in the same branch.
- Diff is still under 2500 LOC (else audit-cycle gate flips).
- The Brown apples-to-apples acceptance test (task #184) passes with `solve_hunl_postflop(initial_hole_cards=(), backend="auto")` in addition to direct `solve_range_vs_range_rust(...)`.

Default decision: ship #182 as **v1.5.1 standalone**.

---

## 8. Open questions for implementer

1. **Marshal of `memory_profile`** — does the Rust vector binding's `memory_profile` dict cleanly populate a `MemoryReport`? If schema mismatch, do we extend `MemoryReport` (mini PR) or synthesize a placeholder?
2. **`locked_strategies` fallback** — silent Python fallback + warning, or hard `NotImplementedError`? Default recommendation: silent fallback (preserves "auto picks best path" contract).
3. **`abstraction` not None + `initial_hole_cards=()`** — same question; same default recommendation.
4. **`backend="rust_vector"` token** — adopt the literal from PR 23's binding (`"rust_vector"` per `crates/cfr_core/src/lib.rs:501` PR 23 worktree) vs reuse `"rust"` (matches PR 6 scalar path). Recommendation: keep `"rust_vector"` distinct so downstream tooling can identify the algorithm class.
5. **Test pin policy** — pin `test_asymmetric_contributions.py` to `backend="python"` defensively even though the test never solves? Recommendation: yes, for documentation clarity (the chance-enum-at-root is the *subject* of that test).
6. **PR 23 commit base** — task #182 must rebase onto v1.5.0 main (not the PR 23 worktree branch) for clean cherry-pick. Verify post-ship.
7. **CHANGELOG entry** — under `[1.5.1]` as `### Changed` (routing behavior) + `### Added` (`backend` kwarg) per Keep-A-Changelog convention. Cross-link to `[1.5.0]` for PR 23 context.

---

## 9. References (READ-ONLY scan, 2026-05-23)

- **PR 23 spec**: `docs/pr_proposals/v1_5_rust_dcfr_widening.md`
- **PR 23 worktree**: `/Users/ashen/Desktop/poker_solver_worktrees/pr-23-rust-dcfr-widening/`
- **PR 23 PyO3 binding**: `crates/cfr_core/src/lib.rs:417-503` (PR 23 worktree)
- **PR 23 vector CFR core**: `crates/cfr_core/src/dcfr_vector.rs:708-815` (PR 23 worktree)
- **LEG 13 v1.5.0 ship plan**: `docs/leg13_v1_5_0_ship_plan.md` (§9 `decision point — task #182 in v1.5.0 OR v1.5.1?`)
- **Brown apples-to-apples**: `docs/brown_apples_to_apples_2026-05-23.md` (§6a Recommendation #2-3 on task #182 scoping)
- **Comprehensive review**: `docs/comprehensive_review_2026-05-23-night.md` (line 106: "Task #182 Python→Rust delegate | DEFERRED | v1.5.1")
- **Python dispatch (current)**: `poker_solver/hunl_solver.py:100-226`
- **Python chance-enum machinery**: `poker_solver/hunl.py:303, 346-351, 651, 666`
- **Python scalar DCFR**: `poker_solver/dcfr.py:170-184`
- **W4.3 BLOCKED retest**: `docs/persona_test_results/W4_3_v1_4_0_retest.md`
- **W2.3 / W3.4 INCONCLUSIVE retests**: `docs/pr_proposals/v1_4_1_retest_W2_3_sarah_kk_vs_cbet_range.md`, `docs/pr_proposals/v1_4_1_retest_W3_4_daniel_mdf.md`

---

**End of spec. Orchestrator: spawn implementer after PR 23 → v1.5.0 lands. Recommended branch name: `pr-32-python-rust-delegate` (next available PR number per LEG 13 series).**
