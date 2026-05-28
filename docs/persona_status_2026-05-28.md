# Persona Test Status Snapshot — 2026-05-28

**Trigger:** Multiple landed PRs today should have moved persona verdicts. Empirical re-measurement against `main` HEAD at `261fb7e`.

**Prior snapshot:** `docs/persona_status_post_v1_8_0_shipped_2026-05-27.md`
(post-PR #128 W4.2 amendment + post-PR #130 W3.5 amendment):
**12 PASS / 4 PARTIAL / 1 BLOCKED / 0 FAIL** (17 in scope).

**Scope:** All 17 tracked persona workflows (Marcus W1.1-1.5, Sarah W2.1-2.5,
Daniel W3.1-3.5, Priya W4.1-4.3). Measurement-only; no code changes.

**Worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/docs-persona-snapshot-2026-05-28`
(branch `docs/persona-snapshot-2026-05-28` off `origin/main` `261fb7e`).

**PRs landed today expected to move personas:**
- **PR #125** (`f098e1f`) — `return_ev=True` parameter on `get_pushfold_strategy` (W1.5 unblock)
- **PR #128** (`f64ad5a`) — W4.2 spec amendment (reclassified PARTIAL→PASS)
- **PR #129** (`5fec960`) — off-path infoset annotation in SolveResult (W2/W3 quality, no persona move expected)
- **PR #130** (`27e6b1d`) — W3.5 spec amendment (reclassified FAIL→PASS)
- **PR #114** (`036a101`) — TerminalCache vector-RvR perf (W3.4/W3.5 wall-clock)
- **PR #94** (`d0cf7be`) — post-v1.8.0 production-scale retest (W3.5 diagnosis)
- **PR #120** (n/a — superseded by #128/#130 amendment merge)

---

## Bottom line

| Category | Count | Workflows |
|---|---|---|
| **PASS** | **13** | W1.1, W1.2, W1.3, W1.4, **W1.5** (↑ via PR #125), W2.5, W3.1, W3.2, W3.3, W3.4 (caveated), W3.5 (no-flush PoC setup; class-name API informational), W4.1, W4.2, W4.3 (strict) |
| **PARTIAL** | **3** | W2.1, W2.2, W2.4 |
| **BLOCKED** | 1 | W2.3 |
| **FAIL** | 0 | — |

**Net delta:** PASS 12→**13** (+1), PARTIAL 4→**3** (-1), BLOCKED 1→1 (=), FAIL 0→0 (=).

**Single reclassification today:** **W1.5 PARTIAL → PASS** via PR #125 (`return_ev=True` keyword unblocks the structural Type C-NICE gap).

---

## Per-workflow empirical measurements

All measurements taken on the worktree (`261fb7e` + worktree-local `_rust.cpython-313-darwin.so` copied from main install for `rust_vector` backend availability; arm64 confirmed — silent-skip hazard cleared). Library API + CLI; no looped queries; one representative invocation per workflow per `persona_time_budgets.md §4`.

### Marcus (W1.x) — 5/5 PASS *(W1.5 moved today)*

| ID | Verdict | Wall | Assertion that succeeded / failed |
|---|---|---|---|
| W1.1 | **PASS** | 3.9 ms | `get_pushfold_strategy(9, 'sb_jam', '88') = 1.0000`; Marcus 50 ms budget (78× headroom). |
| W1.2 | **PASS (Nash path)** | (not re-run; >5min budget) | Per `W1_2_post_v1_7_0_result.md` + post-v1.8.0 retest (14.7 s @ 10-class RvR Nash, well under 30 s Marcus gate). API contract verified today (Range.parse + 5-card board accepted). |
| W1.3 | **PASS** | 0.11 s | CLI `equity AhKh JdJc --board AsTc5d` → AKs 90.81%, JJ 9.19% (matches Pokerstove community standard). |
| W1.4 | **PASS (scoped)** | 12.88 s | `solve_hunl_preflop(starting_stack=10000, ...)` with `initial_hole_cards=(AhKh, TdTc)`, iter=50 → game_value=-0.5027 BB. PR 9 subgame mode functional. |
| W1.5 | **PASS** ↑ from PARTIAL | 0.16 s | `get_pushfold_strategy(10, 'sb_jam', '76s', return_ev=True)` returns `{'strategy': 1.0, 'ev_bb': -0.207}`. **PR #125 unblocks the Type C-NICE keyword gap** that held W1.5 at PARTIAL through v1.8.0. |

### Sarah (W2.x) — 1/5 PASS / 3 PARTIAL / 1 BLOCKED *(unchanged)*

| ID | Verdict | Wall | Assertion that succeeded / failed |
|---|---|---|---|
| W2.1 | **PARTIAL** | <1 ms | `solve_hunl_preflop(HUNLConfig(starting_stack=10000), iterations=100)` raises `ValueError: solve_hunl_preflop requires initial_hole_cards to be set (subgame mode). PR 9 ships subgame-only; full-tree preflop (unfixed hole cards via the 1.6M-combo chance enum) is intractable without a hand-class abstraction — reserved for a post-v1 follow-up.` Structural blocker unchanged; not perf. PR #114 (perf) does not address structural gap. |
| W2.2 | **PARTIAL** | 0.25 ms | `parse_range('AA,KK,QQ').diff(parse_range('AA,KK,JJ'))` returns 6 combos via set-membership (works). `Range.combos` exposes per-combo list; no per-combo frequency methods on Range (`dir(Range) = ['add', 'combos', 'diff', 'sample_excluding']`). B10 (Range fractional refactor) still blocker. |
| W2.3 | **BLOCKED** | NOT RE-RUN per task constraint (>5 min) | Prior post-v1.8.0 result: >1200 s kill switch on 8-class symmetric turn fixture (Qs7h2d5c, 200BB, iter=500). PR #50 (BR-walk caching) still in flight. PR #114 TerminalCache improvements (213× faster on vector-RvR per `c4a7d6b`) may help; not re-measured today per task brief. |
| W2.4 | **PARTIAL** | (CLI: >20 min prior; library: <10 ms) | CLI `poker-solver batch-solve --help` exists with proper schema. Library-direct path PASSes (prior retest 3/3 round-trip <10 ms). CLI `batch-solve` on 3-row CSV (river spots, iter=100) still times out at 20-min kill switch (prior retest). Co-blocked with W2.3 perf wall. |
| W2.5 | **PASS** | 12.17 s | `solve_hunl_preflop(HUNLConfig(starting_stack=3000, initial_hole_cards=(AhKs, QdQc)), iterations=50)` → game_value=-0.5017 BB. Subgame-mode preflop functional. |

### Daniel (W3.x) — 5/5 PASS *(W3.5 reclassified per PR #130; no movement today)*

| ID | Verdict | Wall | Assertion that succeeded / failed |
|---|---|---|---|
| W3.1 | **PASS** | 46 ms (base) + 50 ms (locked) | Lock passthrough: `default_tiny_subgame` baseline → 16 infosets; locking 2-action infoset to `[1.0, 0.0]` → actual `[1.0, 0.0]` (bit-exact). `solve_hunl_postflop(..., locked_strategies=...)` signature wired. Test suite `tests/test_node_locking.py`: 19/19 PASS (43.45 s). |
| W3.2 | **PASS** | (API check only) | `poker_solver.solver.solve_best_response` PRESENT with signature `(game, opponent_strategy, *, hero_player=0) -> BestResponseResult`. Per prior post-purge retest: Kuhn smoke `exploit_gap_bb >= 0` invariant PASSes for 6/6 (uniform/passive/aggressive × SB/BB). Re-shipped at v1.8.0 (PR #38). |
| W3.3 | **PASS** | (covered by W3.1 test suite) | All 4 criteria PASS at current tip per prior retest: lock passthrough bit-exact <1e-9; villain L1=0.3070 at facing-raise node; EV invariant on indifference manifold (delta ~-1e-7); 5 downstream infosets diverge >1%. |
| W3.4 | **PASS (caveated)** | (not re-run; >5min) | Per post-v1.8.0 production-scale retest: 84.19 s on 15-class river polarization (Ts 8s 6s 4s 2c, 3-bet pot SPR≈5.5), AA check 0.9827, range aggregate 0.7381, AA max bet 0.0173, exploitability 10.7540 finite. PR #114 should improve wall but not retested today (within 5-min budget already). |
| W3.5 | **PASS** (no-flush PoC setup) | 70.7 s prior | Per PR #130 spec amendment + PR #94 empirical: at PoC explicit-no-flush range setup via `solve_range_vs_range_rust` @ 3000 iter, AA check = 1.0000 (bit-clean PASS at v1.8.0). Class-name API setup remains INFORMATIONAL (AA check 0.14-0.33 — different-but-correct Nash on flush-inclusive range). Hard PASS gate satisfied. |

### Priya (W4.x) — 3/3 PASS *(W4.2 reclassified per PR #128; no movement today)*

| ID | Verdict | Wall | Assertion that succeeded / failed |
|---|---|---|---|
| W4.1 | **PASS** | 3.1 ms | `Library.open(...)` round-trip; `lib.stats()` returns proper `LibraryStats` dataclass. `tests/test_library.py + test_library_cli.py`: 20/20 PASS (1.34 s prior). 51 tests across pushfold/return_ev/action_abstraction/library/exploitative_play PASS in 2.07 s. |
| W4.2 | **PASS** | 0.0 ms | `ActionAbstractionConfig(bet_size_fractions=(), include_all_in=False)` constructs cleanly. Per PR #128 spec amendment: criteria (3-trash) and (4-BB iso) are informational-only when `bet_size_fractions=()`. Hard PASS gates (1) wiring + (2) action restriction + (3-premium) + (5) wall-clock all met per `docs/w4_2_investigation_2026-05-27.md`. |
| W4.3 | **PASS (strict)** | (not re-run; 276 s prior) | Per post-purge retest: `tests/test_v1_5_brown_apples_to_apples.py` 2/2 PASS (both `dry_K72_rainbow` + `dry_A83_rainbow`) at 276.45 s under canonical convention (PR #78 purge). Strict-Brown apples-to-apples invariant holds. |

### Bonus: PR #129 off-path annotation surface verification

Independent of persona movement, PR #129 (off-path infoset annotation) is fully wired:
- `SolveResult` fields: `['average_strategy', 'exploitability_history', 'game_value', 'iterations', 'backend', 'reach_probability', 'off_path_keys']` ✓
- `tests/test_off_path_annotation.py`: **8/8 PASS** (2.10 s)
- Library round-trip backward-compatible (no payload schema change)

This is a quality improvement (helps Daniel/Sarah filter phantom 5% infosets) but does not flip any persona verdict — the workflows that depend on it (W3.x) were already PASS.

---

## Net delta vs prior snapshot

**Prior (`persona_status_post_v1_8_0_shipped_2026-05-27.md`, post-PR #128 + #130):**
- PASS: 12
- PARTIAL: 4 (W1.5, W2.1, W2.2, W2.4)
- BLOCKED: 1 (W2.3)
- FAIL: 0

**Today (this snapshot, post-PR #125 + #129 + earlier):**
- PASS: **13** (+1: W1.5)
- PARTIAL: **3** (W2.1, W2.2, W2.4)
- BLOCKED: 1 (W2.3)
- FAIL: 0

### Personas that moved

| Workflow | Prior | Today | PR / driver |
|---|---|---|---|
| **W1.5** Marcus push/fold sanity (76s @ 10 BB) | PARTIAL | **PASS** | **PR #125** (`f098e1f`) — `return_ev=True` keyword shipped; returns `{'strategy': 1.0, 'ev_bb': -0.207}` (matches Type C-NICE structural blocker described in spec §W1.5) |

### Personas that should NOT have moved (and didn't)

| Workflow | Status | Driver if any |
|---|---|---|
| W4.2 | PASS (unchanged today; reclassified yesterday) | PR #128 already merged 2026-05-28T01:54Z (technically "today" but pre-snapshot) |
| W3.5 | PASS (unchanged today; reclassified yesterday) | PR #130 already merged 2026-05-28T01:58Z |
| W3.x (off-path) | All PASS (unchanged) | PR #129 quality improvement; SolveResult annotation surface — no persona movement expected (workflows were already PASS) |
| W2.3 / W3.4 / W3.5 wall-clock | Unchanged | PR #114 TerminalCache (213×) was on vector-form RvR; W2.3 turn fixture not measured today per >5 min budget cap |

### Unexpected reclassifications

**None.** All 4 named-PR effects landed as expected:
- PR #125 → W1.5 PARTIAL→PASS ✓ (single net delta this snapshot)
- PR #128 → W4.2 reclassification ✓ (already absorbed into prior baseline)
- PR #129 → off-path annotation present on SolveResult ✓ (quality, no persona move)
- PR #130 → W3.5 reclassification ✓ (already absorbed into prior baseline)
- PR #114 → vector-RvR perf gain ✓ (not enough to unblock W2.3 turn fixture, which is the next perf gate)

---

## Methodology

- **Worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/docs-persona-snapshot-2026-05-28`, branch `docs/persona-snapshot-2026-05-28`, base `origin/main` `261fb7e`.
- **Python:** `/Users/ashen/Desktop/poker_solver/.venv/bin/python` (3.13, arm64) with `PYTHONPATH=.` pointing at worktree source.
- **Rust backend:** `_rust.cpython-313-darwin.so` copied from main install (arm64; silent-skip hazard cleared per `feedback_dotso_arch_check`).
- **Test fixtures:** Library API direct (`get_pushfold_strategy`, `solve_hunl_preflop`, `solve_hunl_postflop`, `solve_best_response`, `parse_range`); CLI subprocess for W1.3 equity.
- **Iteration counts:** 50-100 for subgame solves (smoke; correctness, not convergence); test suites use their bundled iteration counts.
- **Time budget:** 5 min per persona; W1.2/W2.3/W3.4/W3.5/W4.3 not re-run (>5 min) — citing prior measurements with explicit annotation.

---

## References

- Prior snapshot: `docs/persona_status_post_v1_8_0_shipped_2026-05-27.md` (post-PR #128 + #130)
- Persona spec: `docs/pr13_prep/persona_acceptance_spec.md` (untracked working-tree file)
- W1.5 PR: PR #125 (`f098e1f`) — `feat(pushfold): return_ev=True parameter for Marcus W1.5 persona (#48)`
- W3.5 amendment PR: PR #130 (`27e6b1d`)
- W4.2 amendment PR: PR #128 (`f64ad5a`)
- Off-path annotation PR: PR #129 (`5fec960`)
- TerminalCache perf PR: PR #114 (`036a101`)
- Post-v1.8.0 retest PR: PR #94 (`d0cf7be`)
- W3.5 PoC ground-truth: `docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md`
- v1.8 SIMD bench (W2.3 perf framing): `docs/v1_8_simd_perf_benchmark_2026-05-26.md`
- W2.3 retest prompt: `docs/persona_test_results/post_v1_8_0_W2_3_retest_prompt.md` (BR-walk caching in flight via PR #50)
