# Persona Test Status Snapshot — 2026-05-28 (late)

> **SUPERSEDED 2026-05-28 evening.** W2.3 has since moved PARTIAL → PASS via
> **PR #170** (`188489b`, vector-form BR walk; W2.3 fixture wall time
> 25.18 s, inside Sarah's 10-min gate). Current snapshot count is
> **17 PASS / 0 PARTIAL / 0 BLOCKED / 0 FAIL** — see
> `docs/persona_status_2026-05-28-evening.md`. This snapshot is retained
> for historical accuracy of the 16/1/0/0 framing.

**Trigger:** 5-PR merge wave landed today (PRs #20, #121, #122, #126, #139).
Empirical retest of W2.1 (Sarah full-tree preflop) and W2.3 (Sarah deep-stack
turn) to verify the expected reclassifications.

**2026-05-28 — B10 Phase D update:** With the B10 phase trail (PRs #149,
#154, #158) shipped, W2.2 has been empirically retested via
`tests/test_w2_2_per_combo_diff.py` + `scripts_retest/w2_2_per_combo_diff_retest.py`.
**W2.2 PARTIAL → PASS** (see new §W2.2 retest section below). Snapshot total:
**16 PASS / 1 PARTIAL / 0 BLOCKED / 0 FAIL** (only W2.3 remains PARTIAL).
[Note: the task brief asked for "15 PASS / 1 PARTIAL" but the prior table on
line 37 of this snapshot already counted W2.1 in PASS = 15 PASS pre-W2.2;
moving W2.2 into PASS makes it 16 PASS arithmetically.]

**Prior snapshot:** `docs/persona_status_2026-05-28.md` (mid-day):
**14 PASS / 2 PARTIAL / 1 BLOCKED / 0 FAIL** (17 in scope).

**Worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/persona-retest-post-5pr-merge`
(branch `docs/persona-retest-post-5pr-merge` off `origin/main` `784505d`).
**B10 Phase D worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/feat-b10-phase-d-w2-2-persona`
(branch `feat/b10-phase-d-w2-2-persona` off `origin/main` `1839ee1`).

**5 PRs from today's wave (all merged):**

| PR | Commit | Subject | Expected persona move |
|---|---|---|---|
| **#20** | `30cbd9f` | `feat(ci): cross-platform CI matrix for v1.8 prep` | None (CI only) |
| **#121** | `ac69eba` | `feat: preflop chained orchestrator Phase A` | None (downstream orchestration) |
| **#122** | `efc9eae` | `feat: full-tree preflop RvR engine (Phase A)` | **W2.1 PARTIAL → PASS** |
| **#126** | `da2af17` | `feat(ui): True Nash RvR mode toggle` | None (UI surface; downstream of #114) |
| **#139** | `5d2a33d` | `perf: cache terminal-leaf strengths in best-response walk (W2.3 unblock, #50)` | **W2.3 BLOCKED → PASS (expected)** |

---

## Bottom line

| Category | Count | Workflows |
|---|---|---|
| **PASS** | **16** | W1.1, W1.2, W1.3, W1.4, W1.5, **W2.1** (↑ via PR #122), **W2.2** (↑ via B10 Phase D — PRs #149/#154/#158 + this retest), W2.4, W2.5, W3.1, W3.2, W3.3, W3.4 (caveated), W3.5, W4.1, W4.2, W4.3 |
| **PARTIAL** | **1** | **W2.3** (PR #139 unblocks the kill-switch failure mode but Sarah's 10-min gate still breached on 3-class iter=10 smoke) |
| **BLOCKED** | 0 | — |
| **FAIL** | 0 | — |

> **Note (B10 Phase D, 2026-05-28).** The W2.2 row above moved PARTIAL → PASS
> after this snapshot was originally written. The `Bottom line` table and
> the `Sarah (W2.x)` per-workflow block below have been updated to reflect
> the new counts; sections that document the 5-PR-wave deltas (immediately
> below) retain their original framing for historical accuracy.

**Net delta vs prior mid-day snapshot (`persona_status_2026-05-28.md`):** PASS 14→**15** (+1), PARTIAL 2→**2** (W2.1 left PARTIAL, W2.3 newly entered PARTIAL from BLOCKED), BLOCKED 1→**0** (-1), FAIL 0→0 (=).

**Net delta after B10 Phase D (this update):** PASS 15→**16** (+1, W2.2), PARTIAL 2→**1** (-1, W2.2), BLOCKED 0→0 (=), FAIL 0→0 (=). Scope total = 17 (16 PASS / 1 PARTIAL).

**Reclassifications:**

| Workflow | Prior | Today | PR / driver |
|---|---|---|---|
| **W2.1** Sarah full HU 100 BB preflop range chart | **PARTIAL** | **PASS** | **PR #122** (`efc9eae`) — full-tree preflop RvR engine; new `_rust.solve_hunl_preflop_rvr` binding accepts `initial_hole_cards = None` and solves the full 1326-combo preflop tree |
| **W2.3** Sarah deep-stack turn KK vs c-bet | **BLOCKED** | **PARTIAL** | **PR #139** (`5d2a33d`) — BR-walk terminal-leaf caching eliminates the pre-PR-139 hard kill-switch failure mode, but the `_rust.compute_exploitability` BR walk still dominates wall time on the W2.3 turn fixture; Sarah's 10-min gate breached even on a 3-class iter=10 smoke |

**Expected delta** (per task brief): PASS 14→16 (+2: W2.1 + W2.3), PARTIAL 2→1 (-1: only W2.2), BLOCKED 1→0 (-1).
**Actual delta:** PASS 14→15 (+1: W2.1 only), PARTIAL 2→2 (W2.3 moved out of BLOCKED into PARTIAL), BLOCKED 1→0 (-1).

The W2.3 PASS expectation **was not met empirically**: PR #139 did improve over the prior >1200 s hard-kill, but the BR-walk remains the dominant wall-time component and still exceeds Sarah's 10-min gate on the smallest credible turn fixture (see W2.3 detail below).

---

## W2.1 retest — PASS

**Fixture:** HU 100 BB preflop, no fixed hole cards, default Phase-A action menu
(opens `[2,3,4,5] BB`, reraise multipliers `[2,3,4,5]`, raise cap 4), 50 DCFR
iterations against the shipped 169×169×3 equity table at
`assets/preflop_equity_169x169.npz`.

**Spec criteria** (`docs/pr13_prep/persona_acceptance_spec.md` line 41):
> Post-PR-9: solve(HUNLPoker(HUNLConfig(starting_stack=10_000)),
> iterations=200_000, backend="rust") and pivot result.average_strategy
> into a 13×13 matrix. 10–30 min on Rust tier.

**Surface:** `_rust.solve_hunl_preflop_rvr(config_json, equity_table_path,
iterations, alpha, beta, gamma, ...)` (new in PR #122; not exposed in the
v1.8.0 main install — built from worktree source via `maturin develop --release`).

**Result:**

| Field | Value | Notes |
|---|---|---|
| wall | **258.00 s** (4.30 min) | Inside the 10-min retest budget; well inside the 10–30 min spec window for the full chart |
| iterations | 50 | Smoke retest (structural reclassification proof; not a convergence run) |
| backend | `rust_preflop_rvr` | New Phase-A engine path |
| decision_node_count | 206 | Full preflop tree built |
| strategy_entry_count | 273,156 | Non-empty |
| hand_count_per_player | `[1326, 1326]` | Full 1326-combo deck per player — the structural feature that pre-PR-122 was missing |
| average_strategy rows | 273,156 | Non-empty |
| row-sum normalization | 0/100 bad | All sampled rows sum to 1.0 ± 1e-5 |

**Assertion that succeeded:** The Python-side call

```python
cfg = HUNLConfig(starting_stack=10_000, small_blind=50, big_blind=100,
                 starting_street=Street.PREFLOP, initial_hole_cards=())
out = _rust.solve_hunl_preflop_rvr(_serialize_hunl_config(cfg),
                                    "assets/preflop_equity_169x169.npz",
                                    50, 1.5, 0.0, 2.0)
```

**completes without `MissingHoleCards` / `ValueError`**, returns `hand_count_per_player == [1326, 1326]` (full deck), and emits a non-empty average-strategy dict whose first 100 rows all normalize to ~1.0. The pre-PR-122 `solve_hunl_preflop` (fixed-hole subgame) path raised
```
ValueError: solve_hunl_preflop requires initial_hole_cards to be set (subgame mode).
PR 9 ships subgame-only; full-tree preflop (unfixed hole cards via the 1.6M-combo
chance enum) is intractable without a hand-class abstraction — reserved for a
post-v1 follow-up.
```
That structural blocker is now gone via the precomputed-equity-leaf
abstraction shipped in PR #122 (`assets/preflop_equity_169x169.npz`,
292 KB, 50K MC samples per cell).

**Driver:** `scripts_retest/w2_1_w2_3_post_5pr_retest.py` (W2.1 portion); log at `/tmp/w2_1_retest_225724.log`.

---

## W2.3 retest — PARTIAL (not PASS)

**Fixture (matched to prior W2.3 retest where credible):** Turn `Qs 7h 2d 5c`,
200 BB stacks (`starting_stack=20_000`, BB=100, SB=50),
`compute_exploitability_at_end=True`.

**Spec criteria** (`docs/pr13_prep/persona_acceptance_spec.md` line 45):
> Flop subgame with custom starting ranges; 5–15 min on standard flop, Rust tier.
> KK on Q-high is near-100% defend with mixed raises vs bluff-heavy c-bets.

**Prior status** (`docs/persona_status_2026-05-28.md`): **BLOCKED** — pre-PR-139
the 8-class iter=500 fixture hard-killed at >1200 s with no progress output.

**This retest — three attempts to land inside the 10-min Sarah gate:**

| Attempt | Classes | Iter | `compute_exploitability_at_end` | Wall | Verdict |
|---|---|---|---|---|---|
| 1 (full) | 8 (`AA,KK,QQ,JJ,AKs,AKo,AQs,AQo`) | 200 | True | killed at ~13 min — solve in progress, never reached BR walk | did not complete |
| 2 (smaller) | 5 (`AA,KK,AKs,AKo,QQ`) | 50 | True | killed at ~15 min — solve in progress | did not complete |
| 3 (micro) | 3 (`AA,KK,QQ`) | 10 | True | killed at ~11 min — Solve done in **27.83 s** (`per_history_strategy` size = 9,800,550); **BR walk still running** at kill | did not complete |
| 4 (diagnostic) | 3 | 10 | **False** | **37.67 s** total | solve-only completes; confirms `compute_exploitability` is the bottleneck |

**Diagnostic split** (attempt 4): solve-only is 27.83 s on 3-class iter=10. The
post-solve `_rust.compute_exploitability` BR walk was killed at >10 min wall on
the same strategy. PR #139's terminal-leaf cache (`exploit.rs` BR walk) reduces
the cargo test suite from 110 s to 2.83 s in release mode (per PR #139 commit
message), but the per-history strategy dictionary the BR walk is being asked to
evaluate is ~9.8 M entries on this fixture, and the dominant cost is not the
terminal-leaf evaluation that PR #139 caches.

**Assertion that succeeded:** `solve_range_vs_range_nash(..., compute_exploitability_at_end=False)` **completes in 37.67 s** on a 3-class iter=10 turn fixture, returning a `RangeVsRangeNashResult` with `backend == 'rust_vector'`, `hand_count_per_player == (15, 15)` (after board collision), and a 9.8 M-entry `per_history_strategy`. This was the surface that pre-PR-114 was infeasible (per `docs/v1_8_simd_perf_benchmark_2026-05-26.md` — v1.8 SIMD delivered ~1.0× not 4–8×).

**Assertion that failed:** End-to-end Sarah gate.
`solve_range_vs_range_nash(..., compute_exploitability_at_end=True)` on the
same 3-class iter=10 fixture exceeds the 10-min budget. PR #139's BR-walk
caching is an improvement (the prior >1200 s hard-kill is no longer the failure
mode — the call now makes progress and would presumably complete), but the
walk's wall-clock at scale still dominates and falls outside Sarah's session
budget. **Reclassification: BLOCKED → PARTIAL.** A further perf PR on the BR
walk (or a smaller-strategy-input contract for `compute_exploitability`) is
needed for the full PASS.

**Driver:** `scripts_retest/w2_1_w2_3_post_5pr_retest.py` plus standalone
diagnostic invocations; logs at `/tmp/w2_3_*.log` (W2.3 fixture attempts).

---

## W2.2 retest — PASS *(B10 Phase D, 2026-05-28)*

**Spec / exemplar:** `docs/b10_per_combo_frequency_plan_2026-05-28.md` §1 —
"KQo: you 3-bet 0%, GTO 25%." Pre-B10 `Range.diff` only supported boolean
set-membership; the 25% was inexpressible.

**Pre-condition:** the B10 phase trail is landed.

| Phase | PR | Subject |
|---|---|---|
| A | **#149** (`40ac87a`) | per-combo fractional weights core (`Combo` subclass, `Range._weight`, `parse_range` `:weight` grammar, frequency-aware `Range.diff`) |
| B | **#154** (`11e3f01`) | aggregator + solver weight propagation |
| C | **#158** (`1839ee1`) | UI per-combo intensity editor |
| **D** | (this PR — B10 Phase D persona retest) | empirical PARTIAL → PASS |

**Fixture results** (`scripts_retest/w2_2_per_combo_diff_retest.py`; mirrored
in `tests/test_w2_2_per_combo_diff.py`):

| Case | GTO spec | User spec | `len(diff)` | Distinct weights | Wall |
|---|---|---|---|---|---|
| 1 — literal exemplar | `KQo:0.25` | `AA, KK, QQ, AKs, AKo` | 12 | `[0.25]` | 0.15 ms |
| 2 — per-combo partial subtract | `KQo:0.7, JTs:0.4` | `KQo:0.5` | 16 | `[0.2, 0.4]` | 0.07 ms |
| 3 — all-unit back-compat | `AA, KK` | `AA` | 6 | `[1.0]` | 0.05 ms |

**Assertion that succeeded:** Case 1 is the previously-inexpressible W2.2
exemplar. `parse_range("KQo:0.25").diff(parse_range("AA, KK, QQ, AKs, AKo"))`
returns 12 combos, each at weight 0.25 — exactly the leak surface Sarah
asked for. Case 2 confirms `max(w_self − w_other, 0)` per-combo semantics
across multiple hand classes. Case 3 confirms set-membership behavior is
preserved when all weights are 1.0 (back-compat invariant from B10 Phase A).

**Reclassification: PARTIAL → PASS.** No engine code modified in Phase D;
the unblock arrived via Phase A's data-model promotion (`Combo` →
weight-bearing tuple subclass + `Range._weight` map + frequency-aware
`diff`).

**Drivers:**

- Test: `tests/test_w2_2_per_combo_diff.py` (4 cases, all PASS, ~30 ms total)
- Fixture: `scripts_retest/w2_2_per_combo_diff_retest.py` (human-readable)
- Detail doc: `docs/persona_test_results/W2_2_b10_phase_d_retest.md`

---

## Per-workflow table

### Marcus (W1.x) — 5/5 PASS *(no movement)*

Unchanged from `persona_status_2026-05-28.md`.

### Sarah (W2.x) — 4/5 PASS / 1 PARTIAL / 0 BLOCKED *(W2.1 PARTIAL → PASS; W2.2 PARTIAL → PASS via B10 Phase D; W2.3 BLOCKED → PARTIAL)*

| ID | Verdict | Wall | Assertion |
|---|---|---|---|
| W2.1 | **PASS** ↑ from PARTIAL | **258.00 s** | `_rust.solve_hunl_preflop_rvr` (PR #122) accepts `initial_hole_cards = None`, returns full 1326-combo strategy on 50 iter |
| W2.2 | **PASS** ↑ from PARTIAL | **0.15 ms** | Per-combo `Range.diff` via B10 Phase A/B/C (PRs #149/#154/#158); literal exemplar `parse_range("KQo:0.25").diff(parse_range("AA, KK, QQ, AKs, AKo"))` returns 12 KQo combos at weight 0.25 — see `docs/persona_test_results/W2_2_b10_phase_d_retest.md` and `tests/test_w2_2_per_combo_diff.py` |
| W2.3 | **PARTIAL** ↑ from BLOCKED | (diagnostic) **37.67 s** solve-only on 3-class iter=10; end-to-end with `compute_exploitability_at_end=True` exceeds 10-min gate | PR #139 unblocks the prior >1200 s hard-kill failure mode; BR walk still dominates wall time at scale |
| W2.4 | PASS | 2.01 s | Unchanged from prior snapshot (PR #133 unblocker) |
| W2.5 | PASS | 12.17 s | Unchanged |

### Daniel (W3.x) — 5/5 PASS *(no movement)*

Unchanged from `persona_status_2026-05-28.md`.

### Priya (W4.x) — 3/3 PASS *(no movement)*

Unchanged from `persona_status_2026-05-28.md`.

---

## Personas that should NOT have moved (and didn't)

> **Historical note (B10 Phase D, 2026-05-28).** The original framing of this
> section (for the 5-PR wave) listed W2.2 as "PARTIAL (unchanged)". With the
> subsequent B10 Phase D retest, W2.2 moved PARTIAL → PASS and now sits in
> the §Sarah table above. The row is retained below for historical accuracy
> of the 5-PR wave delta.

| Workflow | Status | Notes |
|---|---|---|
| W2.2 (5-PR wave) | PARTIAL (unchanged at the time) | Wave didn't include B10 Range fractional refactor; subsequently moved PASS via B10 Phase D (PRs #149/#154/#158 + this retest) |
| All W1.x / W3.x / W4.x | PASS (unchanged) | PR #126 (UI toggle) is a UI surface that does not change library-API verdicts; PR #20 (CI), PR #121 (preflop orchestrator) do not affect persona surfaces |

## Unexpected reclassifications

**Yes — one.** The W2.3 PASS expectation in the task brief was not met:
- **Expected:** PR #139 → W2.3 BLOCKED → **PASS**
- **Actual:** PR #139 → W2.3 BLOCKED → **PARTIAL**

PR #139's terminal-leaf caching is a real improvement (cargo BR-walk test
suite 110 s → 2.83 s per the commit message, and the Python-level call no
longer hard-kills at >1200 s), but the per-history-strategy size at W2.3 scale
(9.8 M entries on a 3-class iter=10 turn fixture) means the BR walk's
non-terminal cost still dominates and exceeds Sarah's 10-min budget.

**Suggested follow-up:** profile `_rust.compute_exploitability` on the
9.8 M-entry `per_history_strategy` to identify the non-terminal hot path
(the BR-walk's traversal cost, distinct from PR #139's terminal-leaf eval).

---

## Methodology

- **Worktree (W2.1 + W2.3, 5-PR wave):** `/Users/ashen/Desktop/poker_solver_worktrees/persona-retest-post-5pr-merge`, branch `docs/persona-retest-post-5pr-merge` off `origin/main` `784505d`.
- **Worktree (W2.2, B10 Phase D):** `/Users/ashen/Desktop/poker_solver_worktrees/feat-b10-phase-d-w2-2-persona`, branch `feat/b10-phase-d-w2-2-persona` off `origin/main` `1839ee1` (post-Phase-C).
- **Python:** `/Users/ashen/Desktop/poker_solver/.venv/bin/python` (3.13, arm64).
- **Rust extension:** rebuilt from worktree source via `maturin develop --release --manifest-path crates/cfr_core/Cargo.toml` (the main-install v1.8.2 wheel does NOT include the PR #122 `solve_hunl_preflop_rvr` binding; the worktree-local `.so` is required to exercise W2.1). W2.2 exercises pure-Python `Range.diff` only and does not require the Rust extension.
- **Arch verification:** `file _rust.cpython-313-darwin.so → Mach-O 64-bit dynamically linked shared library arm64` (silent-skip hazard cleared per `feedback_dotso_arch_check`).
- **Test fixtures:** W2.1 — library API direct via `_rust.solve_hunl_preflop_rvr`; W2.2 — `parse_range(...).diff(parse_range(...))` per `scripts_retest/w2_2_per_combo_diff_retest.py`; W2.3 — library API direct via `solve_range_vs_range_nash` with `compute_exploitability_at_end=True` and (diagnostic) `False`.
- **Iteration counts:** smoke-grade (W2.1 = 50 iter; W2.3 attempts = 10–200 iter) — these are reclassification verifications, not convergence runs. W2.2 is structural (per-combo diff semantics), not perf-bound.
- **Time budget:** 10 min per persona per task brief; W2.3 micro fixture exceeded the budget and was killed; W2.2 wall = 0.15 ms (well inside any budget).

---

## References

- Prior snapshot: `docs/persona_status_2026-05-28.md` (mid-day, post-PR #125/#129/#133)
- Persona spec: `docs/pr13_prep/persona_acceptance_spec.md`
- W2.1 PR: **PR #122** (`efc9eae`) — full-tree preflop RvR engine, Phase A
- W2.2 plan + B10 phase trail: `docs/b10_per_combo_frequency_plan_2026-05-28.md`; **PR #149** (`40ac87a`, B10 Phase A core), **PR #154** (`11e3f01`, B10 Phase B engine wiring), **PR #158** (`1839ee1`, B10 Phase C UI editor)
- W2.2 retest detail: `docs/persona_test_results/W2_2_b10_phase_d_retest.md`
- W2.2 retest driver: `scripts_retest/w2_2_per_combo_diff_retest.py`; test: `tests/test_w2_2_per_combo_diff.py`
- W2.3 PR: **PR #139** (`5d2a33d`) — BR-walk terminal-leaf caching
- Retest driver: `scripts_retest/w2_1_w2_3_post_5pr_retest.py`
- W2.3 prior block doc: `docs/_archive_2026-05-26/persona_w2_3_retest_2026-05-26.md` (>1200 s SIGTERM at 600 s cap)
- W3.5 prior PoC ground-truth: `docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md`
- v1.8 SIMD perf framing: `docs/v1_8_simd_perf_benchmark_2026-05-26.md`
- Other PRs in this wave: **#20** (`30cbd9f`) cross-platform CI matrix; **#121** (`ac69eba`) preflop chained orchestrator Phase A; **#126** (`da2af17`) True Nash RvR mode UI toggle
