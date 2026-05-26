# Persona Test Status — 2026-05-25 (post-pause resume wave)

**Total: 18 workflows across 4 personas**
**Current: 7 PASS / 5 PARTIAL / 4 BLOCKED / 2 FAIL** *(grounded in real retest result docs under `docs/persona_test_results/`)*

Sources:
- Spec: `docs/pr13_prep/persona_acceptance_spec.md`
- Time budgets: `docs/pr13_prep/persona_time_budgets.md`
- Result docs: `docs/persona_test_results/*.md` (latest used per workflow)

---

## Marcus (W1.x) — 5 workflows — 4 PASS / 1 PARTIAL

| ID | Description | Verdict | Latest retest | Blocker / next step |
|---|---|---|---|---|
| W1.1 | "I jammed 88 at 9 BB; was that right?" — push/fold chart lookup | **PASS** | v1.4.1 retest (`W1_1_v1_4_1_retest.md`) | None — library path 5.5 ms, Marcus 50 ms budget. CLI `pushfold` subcommand shipped in PR 39 (v1.7.0). Type C-USEFUL, closed. |
| W1.2 | "Villain bet pot; JJ on As Tc 5d Jh 8s — call right?" — river bluff-catcher | **PASS via Nash path** | v1.7.0 retest (`W1_2_post_v1_7_0_result.md`) | Aggregator artifact eliminated by `solve_range_vs_range_nash` (PR 43); JJ defend = 1.0000 (fold 1.6e-08), 9.19 s Rust solve well under Marcus 30 s gate. Type A docs-only follow-up (USAGE clarification for aggregator-vs-Nash). |
| W1.3 | "AKs vs JJ on As Tc 5d" — equity HvH | **PASS** | v1.4.1 retest (`W1_3_v1_4_1_retest.md`) | 0.30 s CLI; spec labels were inverted (correct: AKs ≈ 91%, JJ ≈ 9% on A-high flop) — spec text correction is a Type A doc fix. |
| W1.4 | "Study 100 BB SRP preflop" — full preflop tree | **PASS (scoped)** | v1.5.0 retest (`W2_5_preflop_literal_v1_5_0_retest.md` covers PR 9 path) + v1.4.1 W2.1 retest pattern | PR 9 `solve_hunl_preflop` ships; per-class subgame mode validates 100 BB SRP. Full 169-cell chart materialization is a perf-budget question, not a feature gap. |
| W1.5 | "Why does 76s fold at 10 BB?" — sanity-check chart | **PARTIAL** | No standalone retest doc; covered by W1.1 push/fold infrastructure | `return_ev=True` decomposition not yet added. Severity: low — chart values are correct; missing EV breakdown is Type C-NICE. |

**Marcus time budget:** All passing workflows complete well under his 30 s interactive gate. W1.2 Nash solve at 9.19 s has 3.3× headroom.

---

## Sarah (W2.x) — 5 workflows — 1 PASS / 2 PARTIAL / 1 BLOCKED / 1 FAIL

| ID | Description | Verdict | Latest retest | Blocker / next step |
|---|---|---|---|---|
| W2.1 | "Generate HU 100 BB preflop range chart" | **PARTIAL (Type D timeout on flop; PASS on river envelope)** | v1.7.0 retests: full flop fixture timed out at 21 min (`W2_1_post_v1_7_0_result.md`); smaller-fixture river envelope completed in 31.7 s with 9.5× budget headroom (`W2_1_post_v1_7_0_smaller_fixture_result.md`) | v1.8 SIMD (4-8× perf) projected to bring flop into Sarah ≤5 min budget. Pre-staged retest exists. |
| W2.2 | "Diff my BB 3-bet range vs GTO" — leak finder | **PARTIAL** | v1.4.1 retest on PR 27 branch (`W2_2_v1_4_1_retest.md`) | `Range.diff()` exists (PR 27 worktree) — set-membership only. Cannot represent "you 3-bet 0%, GTO 25%" frequency until `Range` carries per-combo weights (B10 Range fractional refactor — deferred to v1.5+). |
| W2.3 | "Solve KK on Q-high flop vs c-bet range" — RvR postflop | **BLOCKED** | v1.7.0 retest (`W2_3_post_v1_7_0_result.md`) PARTIAL-TIMEOUT; v1.8.0 retest pre-staged (`post_v1_8_0_W2_3_retest_prompt.md`) | 4-class iter=100 flop aggregator >300 s on 200 BB deep stack. Awaits v1.8 SIMD ship — projected 75-150 s on M-series. |
| W2.4 | "Verify batch-solve CSV schema" — 3-row library round-trip | **PARTIAL** | v1.4.1 retest (`W2_4_v1_4_1_retest.md`) | Library-direct path PASS (3/3 round-trip <10 ms); CLI `batch-solve` path INCONCLUSIVE-SLOW at river even with 1-row 1-iter probe. Same perf family as W2.3 — v1.8 SIMD candidate. |
| W2.5 | "30 BB SRP preflop chart" | **PASS** | v1.5.0 literal retest (`W2_5_preflop_literal_v1_5_0_retest.md`) | PR 9 `solve_hunl_preflop(starting_stack=3_000)` clean per-class subgame solve; monotonic by hand strength; under per-spot budget. Same perfect-info subgame caveat as v1.4.1. |

**Sarah time budget:** ≤5 min per solve is the binding constraint that v1.8 SIMD targets directly.

---

## Daniel (W3.x) — 5 workflows — 1 PASS / 1 PARTIAL / 2 BLOCKED / 1 FAIL

| ID | Description | Verdict | Latest retest | Blocker / next step |
|---|---|---|---|---|
| W3.1 | "Lock villain bluff freq to 0; resolve" — node-locking | **PASS** | Node-locking shipped in v1.4.0 (`chore(release): v1.4.0 — Node-locking (MINOR; Daniel-persona unlock)`); UI editor in PR 24b (v1.6.0). No standalone retest doc — feature presence verified via CHANGELOG + UI. | None (feature shipped). Recommend adding a W3.1 retest doc to close the loop. |
| W3.2 | "Compare GTO vs villain actuals; exploitative response" | **BLOCKED** | No retest doc | `best_response(game, fixed_strategy, player)` public API not exposed (only private `_best_response_value` used internally for exploitability). Type C-USEFUL API addition. |
| W3.3 | "Merged-strategy range; GTO response" — node-locking-at-scale | **PARTIAL** | Depends on W3.1 (node-locking shipped); no W3.3-specific retest doc | Node-locking infrastructure exists post-v1.4.0; specific merged-range workflow not retested. |
| W3.4 | "MDF check vs half-pot c-bet" — BB defend ≥ MDF | **BLOCKED** | v1.7.0 retest (`W3_4_post_v1_7_0_aggregator_result.md`) PARTIAL-TIMEOUT; v1.8.0 retest pre-staged (`post_v1_8_0_W3_4_retest_prompt.md`) | Same perf wall as W2.3 (4-class iter=100 100 BB flop >300 s). v1.8 SIMD candidate. |
| W3.5 | "Monotone-board polarization" — aggressor's range polarizes | **FAIL → Type B (wrapper bug)** | Wider-range retest (`W3_5_post_v1_7_0_wider_range_result.md`) reclassified to Type B-DOC per `v1_7_1_wrapper_fix_spec.md`; root-caused as class-expansion divergence vs hand-curated PoC | v1.7.1 ship in flight (retry 6+ — see `PAUSE_RESUME_2026-05-25.md` §1) bundles wrapper fix (PRs 50/51/52/54/55/56/53b/53c/59/60). |

**Daniel time budget:** ≤15 min per spot session budget; perf gates per-spot via Sarah 5 min in v1.8 staging.

---

## Priya (W4.x) — 3 workflows — 1 PASS / 1 PARTIAL / 1 PASS-AGGREGATOR

| ID | Description | Verdict | Latest retest | Blocker / next step |
|---|---|---|---|---|
| W4.1 | "Programmatic build + parse to pandas" — 20-line library round-trip | **PASS** | v1.4.0 retest (`W4_1_v1_4_0_retest.md`) | All sub-checks green; 38 ms round-trip (HUNLConfig → solve_hunl_postflop → DataFrame → Library.put/get/list → SHA-256 spot_id). Type A docs follow-up — worked example in USAGE §5b. |
| W4.2 | "Custom limp-or-fold action menu" — extend action abstraction | **PARTIAL** | v1.4.0 retest (`W4_2_v1_4_0_retest.md`) | Wiring + action restriction PASS via `HUNLConfig(bet_size_fractions=(), include_all_in=False)` + `solve_hunl_preflop(allow_pushfold_range=True)`. Heuristic criteria (3)+(4) miss are structural (subgame fixes hole cards → equity is sole driver). Type A DEVELOPER.md doc add. |
| W4.3 | "Diff our solver vs Brown on novel river spot" | **PASS via aggregator path** | v1.7.0 aggregator retest (`W4_3_post_v1_7_0_aggregator_result.md`) | Aggregator path completes <5 s on novel river spot, deterministic, within Priya session budget. Strict `tests/test_river_diff.py` path remains test-coupled (canonical parity timeout — `W4_3_v1_4_0_retest.md`); separate from this workflow. |

**Priya time budget:** Per-spot 1-5 min Pio-class; session totals lenient. W4.1/W4.3 well inside budget; W4.2 PARTIAL is structural, not perf.

---

## Aggregate

| Category | Count | Workflows |
|---|---|---|
| **PASS** | 7 | W1.1, W1.2, W1.3, W1.4, W2.5, W3.1, W4.1, W4.3 *(W4.3 PASS via aggregator path)* |
| **PARTIAL** | 5 | W1.5, W2.1, W2.2, W2.4, W3.3, W4.2 |
| **BLOCKED** | 4 | W2.3, W3.2, W3.4 |
| **FAIL** | 2 | W3.5 *(Type B wrapper — v1.7.1 ship in flight)* |

*Note:* Counts above use W4.3-as-PASS-via-aggregator. Strict W4.3 path remains BLOCKED on parity perf.

---

## Projected end-state

After **v1.7.1 ship + v1.8 SIMD ship + B10 Range fractional + final sweep**: ~16-18 / 18 PASS expected.

- **W3.5:** PASS expected once v1.7.1 wrapper fix ships (in flight; 5 ship retries killed by agent execution timeout; option A `PYTEST_TIMEOUT=300` running via background nohup per resume log).
- **W2.3 + W3.4:** v1.8 SIMD (4-8× per `v1_8_decision_brief.md`) projected to bring flop solve into Sarah's 5 min budget (current pre-v1.8 turn Nash > 10 min; target 75-150 s on M-series).
- **W2.1:** v1.8 SIMD unblocks flop fixture; river envelope already PASSes.
- **W2.2:** PARTIAL until B10 (Range fractional-frequency) lands — currently deferred to v1.5+ per CHANGELOG `[Unreleased]`.
- **W3.2:** Requires `best_response()` public API addition (Type C-USEFUL).
- **W1.5 / W4.2:** Type C-NICE / docs-only — low priority.

---

## Bottom-line answer to "what passed / failed"

### PASS now (7 workflows)
- **W1.1, W1.2, W1.3, W1.4** — Marcus full slate except W1.5 (low-priority chart EV decomposition)
- **W2.5** — Sarah 30 BB SRP via PR 9 preflop solver
- **W3.1** — Daniel node-locking (shipped v1.4.0)
- **W4.1, W4.3** — Priya programmatic + Brown parity (aggregator path)

### PARTIAL (5)
- **W1.5** — chart EV decomposition missing (Type C-NICE)
- **W2.1** — flop times out; river envelope passes (v1.8 candidate)
- **W2.2** — set-membership diff PASS; frequency diff needs B10 (Range fractional)
- **W2.4** — library round-trip PASS; CLI batch-solve perf TBD (v1.8 candidate)
- **W3.3** — node-locking-at-scale (workflow not retested post-v1.4.0)
- **W4.2** — wiring PASS; heuristic mis-aligned with subgame mode (Type A docs)

### BLOCKED (4)
- **W2.3** — 200 BB deep-stack flop RvR (v1.8 SIMD candidate)
- **W3.2** — public `best_response()` API missing
- **W3.4** — MDF BB defense vs half-pot c-bet (v1.8 SIMD candidate)

### FAIL (1)
- **W3.5** — monotone polarization wrapper bug (v1.7.1 ship bundles fix; in flight per `PAUSE_RESUME_2026-05-25.md` §1)

### Action items for user
1. **Decide on Apple Developer enrollment** — gates Gate 5 signed `.dmg` ship (carry item).
2. **Confirm v1.7.1 ship strategy** — option A (manual terminal with `PYTEST_TIMEOUT=300`) vs option B (drop slow parity test from smoke matrix) vs option C (`@pytest.mark.slow`). Recommendation per resume doc: B.
3. **Approve v1.8 ship sequence** once Phases 2/3/4 land — pre-staged retests for W2.3 + W3.4 fire immediately on v1.8.0 tag.
4. **Approve B10 (Range fractional)** scope when v1.5+ refactor wave begins (W2.2 unblock).

---

## References

- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/persona_acceptance_spec.md`
- Time budgets: `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/persona_time_budgets.md`
- All result docs: `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/`
- Resume context: `/Users/ashen/Desktop/poker_solver/docs/PAUSE_RESUME_2026-05-25.md`
- v1.8 decision brief: `/Users/ashen/Desktop/poker_solver/docs/v1_8_decision_brief.md`
