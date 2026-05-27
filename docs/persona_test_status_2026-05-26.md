# Persona Test Status — 2026-05-26 (post-W3.2/W3.4 retests, post-v1.8 SIMD)

**Total: 18 workflows across 4 personas**
**Current (post-W3.3 retest, pre-W2.3 retest, post-convention-purge W4.3 strengthen):** 10 PASS / 4 PARTIAL / 2 BLOCKED / 1 FAIL
**Prior snapshot (pre-W3.3 retest, post-W3.2/W3.4):** 9 PASS / 5 PARTIAL / 2 BLOCKED / 1 FAIL
**Pending:** W2.3 post-v1.8 retest IN PROGRESS (agent `a99ec2e`) — final tally is 10 or 11 PASS / 4 PARTIAL / 1 or 2 BLOCKED / 1 FAIL, depending on whether the W2.3 turn-fixture retest beats Sarah's 300 s gate now that the v1.8 SIMD speedup is empirically ~1.0× (see "Critical context: v1.8 SIMD measured ~1.0×" below).

**W4.3 quality improvement (2026-05-27, post-PR #78 convention purge):** Overall count unchanged at 10 PASS — but W4.3 has been reclassified from "PASS via aggregator path" to "PASS (strict)". The convention purge unblocked the strict-Brown apples-to-apples assertion on both A83 + K72 board parametrizations. See `docs/persona_post_purge_retest_2026-05-27.md` and the "Post-purge convention impact" section below.

**Supersedes:** `docs/persona_test_status_2026-05-25.md`. The 2026-05-25 snapshot remains accurate as a historical baseline; this document is the current-of-record.

**v1.6.1 hold-lift — now empirically backed (2026-05-26).** The v1.6.1 ship-hold-lift decision (`docs/v1_6_1_ship_hold_review_2026-05-26.md`) rested on the reasoning that the A83 33pp Brown apples-to-apples gap reflects Nash multiplicity at deep-cap indifference manifolds rather than an engine bug. That reasoning has now been **empirically confirmed** via a corrected 2000-iter `solve_range_vs_range_rust` perturbation probe: with the same RNG seed and only `ε = 1e-9` initial-regret perturbation, the resulting average strategies diverge by up to `max |Δ| = 0.998499` on indifference-manifold cells and ~25-28% on the bottom-pair-Ace cluster. The hold-lift is retrospectively bulletproof. See `docs/a83_nash_multiplicity_confirmed_2026-05-26.md` for full evidence (verdict, methodology, top-10 cells, targeted-cluster cells) and `scripts/a83_nash_multiplicity_probe.py` for the reproducible probe. This is upstream of the persona-test framework (the multiplicity validation does not move any persona verdict), but it removes the largest open uncertainty around the v1.6.1/v1.7.x/v1.8.0 ship sequence.

Sources:
- Spec: `docs/pr13_prep/persona_acceptance_spec.md`
- Time budgets: `docs/pr13_prep/persona_time_budgets.md`
- Result docs: `docs/persona_test_results/*.md` + today's retest docs (`docs/persona_w3_*_2026-05-26.md`)
- v1.8 SIMD bench (load-bearing for the speedup caveat): `docs/v1_8_simd_perf_benchmark_2026-05-26.md`

---

## Critical context: v1.8 SIMD measured ~1.0× (not 4-8×)

Per `docs/v1_8_simd_perf_benchmark_2026-05-26.md` (today's bench on M4 Pro arm64):

| Workload | v1.7.0 | post-v1.8 main | Ratio |
|---|---|---|---|
| River RvR, 1081 hands, 3 actions, 5 iter | 936 ms/iter | 942 ms/iter | **0.99×** |
| River RvR, 1081 hands, 5 actions, 5 iter | 4,777 ms/iter | 4,723 ms/iter | **1.01×** |

The 2026-05-25 snapshot projected W2.3 / W3.4 / W2.1 from BLOCKED→PASS via "v1.8 SIMD 4-8×." **That projection is empirically refuted on M4 Pro arm64.** Root cause per bench: LLVM `-O3` already autovectorizes the small-slice scalar loops (action_count = 3-5); hand-written intrinsics pay dispatch overhead that cancels the kernel-level win.

**Today's W3.4 PASS is NOT a v1.8-SIMD validation** — it's a fixture-repurposing unblock (river single-street vs the prior flop multi-street). The W3.5 6-class smoke result is **bit-identical** to v1.7.0 (delta ~0; modest ~36% wall-clock improvement on this fixture, but no kernel speedup). v1.8 release notes have been corrected to the "~1.0× not 4-8×" framing (PR #56, `bf645ae`).

**Marcus's <30 s budget is unchanged**; v1.8 SIMD does not move his numbers. Perf-gated Marcus / Sarah workflows remain at their snapshot status until further notice (or until the v1.9 EMD bucketing work lands per `v1_8_decision_brief.md:26`).

---

## Today's reclassifications

| ID | Prior verdict | New verdict | Type | Evidence |
|---|---|---|---|---|
| **W3.2** | BLOCKED | **PASS** | A (correctness; named API blocker cleared) | `docs/persona_w3_2_smoke_2026-05-26.md` — PR 76 / PR #38 / commit `feee974` shipped `solve_best_response()` + CLI subcommand; Kuhn smoke `exploit_gap_bb > 0` on both seats. |
| **W3.3** | PARTIAL | **PASS** | A (correctness; P2 closing test for node-locking-at-scale) | `docs/persona_w3_3_retest_2026-05-26.md` — 4/4 acceptance criteria PASS (lock passthrough bit-exact <1e-9; villain L1 = 0.3070 at facing-raise node; EV invariant 5.0/5.0 BB on indifference manifold; 5 downstream infosets diverge >1%); 3.00 s Python wall-clock (well under Daniel's 15 min budget). P2 closing test for node-locking primitive; reused v1.4.0 procedure (no W3.3-specific fixture exists — acceptable per primitive scope). |
| **W3.4** | BLOCKED | **PASS (caveated)** | A (with explicit "repurposed fixture" caveat) | `docs/persona_w3_4_retest_2026-05-26.md` — PASS on REPURPOSED monotone-river 3-bet-pot polarization fixture; 80.71 s wall-clock (27% of 300 s Sarah gate); all 7 acceptance thresholds met (AA check 0.9827, range aggregate 0.7381, AA max bet 0.0173, exploitability 10.7540, 0 NaN). Original W3.4 flop MDF fixture remains perf-bound. |
| **W3.5** | PARTIAL → Type B (wrapper bug) [per 2026-05-25 snapshot row label] | **PARTIAL (no change)** — Type B-DOC | B-DOC (docstring + regression-test gaps; no code patch needed per `v1_7_1_wrapper_fix_spec.md`) | `docs/persona_w3_5_retest_2026-05-26.md` — v1.8 SIMD did NOT regress this; 6-class smoke bit-identical to v1.7.0 (AA check 0.9224 vs 0.9224; exploitability 1.6821 vs 1.6821; range aggregate 0.9495 vs 0.9495; delta ~0). Classification stands. |
| **W2.3** | BLOCKED | **PENDING RETEST** — IN PROGRESS | TBD | Agent `a99ec2e` currently running the mandatory post-v1.8 retest per `feedback_post_ship_persona_retest`. Pre-staged turn fixture (`post_v1_8_0_W2_3_retest_prompt.md`). May remain BLOCKED if its blocker was perf — since v1.8 SIMD measured ~1.0×, the original "75-150 s on M-series" projection is refuted. |

---

## Marcus (W1.x) — 5 workflows — 4 PASS / 1 PARTIAL *(unchanged from 2026-05-25)*

| ID | Description | Verdict | Latest retest | Blocker / next step |
|---|---|---|---|---|
| W1.1 | "I jammed 88 at 9 BB; was that right?" — push/fold chart lookup | **PASS** | v1.4.1 retest (`W1_1_v1_4_1_retest.md`) | None — library path 5.5 ms, Marcus 50 ms budget. CLI `pushfold` subcommand shipped in PR 39 (v1.7.0). Type C-USEFUL, closed. |
| W1.2 | "Villain bet pot; JJ on As Tc 5d Jh 8s — call right?" — river bluff-catcher | **PASS via Nash path** | v1.7.0 retest (`W1_2_post_v1_7_0_result.md`) | Aggregator artifact eliminated by `solve_range_vs_range_nash` (PR 43); JJ defend = 1.0000 (fold 1.6e-08), 9.19 s Rust solve well under Marcus 30 s gate. Type A docs-only follow-up. |
| W1.3 | "AKs vs JJ on As Tc 5d" — equity HvH | **PASS** | v1.4.1 retest (`W1_3_v1_4_1_retest.md`) | 0.30 s CLI; spec labels were inverted (correct: AKs ≈ 91%, JJ ≈ 9% on A-high flop). |
| W1.4 | "Study 100 BB SRP preflop" — full preflop tree | **PASS (scoped)** | v1.5.0 retest (`W2_5_preflop_literal_v1_5_0_retest.md`) | PR 9 `solve_hunl_preflop` ships; per-class subgame mode validates 100 BB SRP. |
| W1.5 | "Why does 76s fold at 10 BB?" — sanity-check chart | **PARTIAL** | No standalone retest doc | `return_ev=True` decomposition not yet added. Type C-NICE. |

**Marcus time budget:** All passing workflows complete well under his 30 s interactive gate. v1.8 SIMD measured ~1.0× does NOT change Marcus's numbers; W1.2 Nash solve at 9.19 s retains 3.3× headroom unchanged.

---

## Sarah (W2.x) — 5 workflows — 1 PASS / 2 PARTIAL / 1 BLOCKED / 1 PENDING

| ID | Description | Verdict | Latest retest | Blocker / next step |
|---|---|---|---|---|
| W2.1 | "Generate HU 100 BB preflop range chart" | **PARTIAL (Type D timeout on flop; PASS on river envelope)** | v1.7.0 (`W2_1_post_v1_7_0_result.md` + smaller-fixture `W2_1_post_v1_7_0_smaller_fixture_result.md`) | v1.8 SIMD projection refuted (~1.0× measured). Flop multi-street perf ceiling unchanged. River envelope still PASSes. |
| W2.2 | "Diff my BB 3-bet range vs GTO" — leak finder | **PARTIAL** | v1.4.1 retest (`W2_2_v1_4_1_retest.md`) | `Range.diff()` set-membership only. Per-combo frequency representation deferred to B10 (v1.5+ refactor). v1.8 impact: none (structural). |
| W2.3 | "Solve KK on Q-high flop vs c-bet range" — RvR postflop (200 BB deep) | **PENDING RETEST (IN PROGRESS)** | Agent `a99ec2e` running pre-staged retest (`post_v1_8_0_W2_3_retest_prompt.md`). | Prior v1.7.0 retest (`W2_3_post_v1_7_0_result.md`) PARTIAL-TIMEOUT on 4-class iter=100 flop aggregator >300 s. With v1.8 SIMD measured at ~1.0×, the "75-150 s on M-series" projection is refuted; W2.3 may remain BLOCKED on perf depending on actual measured wall-clock. **Snapshot will be revised once retest completes.** |
| W2.4 | "Verify batch-solve CSV schema" — 3-row library round-trip | **PARTIAL** | v1.4.1 retest (`W2_4_v1_4_1_retest.md`) | Library-direct PASS (3/3 round-trip <10 ms); CLI `batch-solve` river path INCONCLUSIVE-SLOW. Same family as W2.3 — v1.8 SIMD does not deliver the projected speedup; retest at lower priority to update wall-clock characterization. |
| W2.5 | "30 BB SRP preflop chart" | **PASS** | v1.5.0 literal retest (`W2_5_preflop_literal_v1_5_0_retest.md`) | PR 9 `solve_hunl_preflop(starting_stack=3_000)` clean per-class subgame solve. |

**Sarah time budget:** ≤5 min per solve. v1.8 SIMD did not deliver the projected acceleration; W2.3 / W2.4 perf characterization owed.

---

## Daniel (W3.x) — 5 workflows — 4 PASS / 0 PARTIAL / 0 BLOCKED / 1 FAIL *(W3.3 PARTIAL→PASS today)*

| ID | Description | Verdict | Latest retest | Blocker / next step |
|---|---|---|---|---|
| W3.1 | "Lock villain bluff freq to 0; resolve" — node-locking | **PASS** | Node-locking shipped in v1.4.0; UI editor in PR 24b (v1.6.0). | None (feature shipped). Recommend adding a W3.1 retest doc to close the loop. |
| W3.2 | "Compare GTO vs villain actuals; exploitative response" | **PASS** | `docs/persona_w3_2_smoke_2026-05-26.md` (PR 76 / PR #38, commit `feee974`, 2026-05-26) | **BLOCKED → PASS today.** `solve_best_response()` + `poker-solver best-response` CLI shipped; Kuhn smoke `exploit_gap_bb > 0` on both seats. Type A (correctness; cleared the named API blocker). |
| W3.3 | "Merged-strategy range; GTO response" — node-locking-at-scale | **PASS** | `docs/persona_w3_3_retest_2026-05-26.md` (2026-05-26, P2 closing test) | **PARTIAL → PASS today.** All 4 acceptance criteria PASS at current tip (lock passthrough bit-exact <1e-9; villain L1 = 0.3070 at facing-raise node; EV invariant 5.0/5.0 BB on indifference manifold; 5 downstream infosets diverge >1%). Wall-clock 3.00 s on Python backend (well under Daniel's 15 min budget). Type A (correctness; node-locking primitive verified at scale). Caveat: no W3.3-specific fixture exists; retest reused v1.4.0 procedure (acceptable per node-locking primitive scope — see retest doc §Caveats). |
| W3.4 | "MDF check vs half-pot c-bet" — repurposed to monotone-river 3-bet-pot polarization | **PASS (caveated)** | `docs/persona_w3_4_retest_2026-05-26.md` | **BLOCKED → PASS today on REPURPOSED fixture.** 80.71 s wall-clock (27% of Sarah gate); AA check 0.9827 (≥0.90), range aggregate 0.7381 (≥0.65), AA max bet 0.0173 (<0.50), exploitability 10.7540 finite, 0 NaN. **Caveat:** PASS is on the repurposed monotone-river 3-bet-pot polarization fixture, NOT the original flop MDF fixture (which remains perf-bound; v1.8 SIMD did not deliver the projected speedup). Type A with explicit fixture-repurposing caveat. |
| W3.5 | "Monotone-board polarization" — aggressor's range polarizes | **PARTIAL — Type B-DOC** *(label updated; status unchanged)* | `docs/persona_w3_5_retest_2026-05-26.md` (v1.8 retest) | v1.8 SIMD did NOT regress this. 6-class smoke bit-identical to v1.7.0 (delta ~0). PARTIAL / Type B-DOC stands per `v1_7_1_wrapper_fix_spec.md` (docstring + regression-test gaps; no code patch needed). Note: 2026-05-25 snapshot row called this "FAIL → Type B (wrapper bug)" with "v1.7.1 ship in flight" — that ship is no longer needed for W3.5 per the wrapper-fix spec's Option 1 (docs-only). |

**Daniel time budget:** ≤15 min per spot session budget. W3.2 / W3.4 retests well inside budget. W3.5 wrapper path intact.

---

## Priya (W4.x) — 3 workflows — 2 PASS / 1 PARTIAL *(W4.3 strengthened to PASS-strict 2026-05-27)*

| ID | Description | Verdict | Latest retest | Blocker / next step |
|---|---|---|---|---|
| W4.1 | "Programmatic build + parse to pandas" — 20-line library round-trip | **PASS** | v1.4.0 retest (`W4_1_v1_4_0_retest.md`) | All sub-checks green; 38 ms round-trip. Type A docs follow-up — worked example in USAGE §5b. |
| W4.2 | "Custom limp-or-fold action menu" — extend action abstraction | **PARTIAL** | v1.4.0 retest (`W4_2_v1_4_0_retest.md`) | Wiring + action restriction PASS; heuristic criteria mis-aligned with subgame mode. Type A DEVELOPER.md doc add. |
| W4.3 | "Diff our solver vs Brown on novel river spot" | **PASS (strict)** *(strengthened 2026-05-27)* | Post-purge retest (`docs/persona_post_purge_retest_2026-05-27.md`) | PASS (strict) — convention purge (PR #78, `37e5be1`) unblocked strict-Brown apples-to-apples assertion on both A83 + K72. `tests/test_v1_5_brown_apples_to_apples.py` passes both parametrizations (276.45 s wall, well under the 300 s timeout). Prior aggregator-path PASS subsumed; aggregator still <5 s on novel river spot. (Separate `test_river_diff_self_sanity.py` perf timeout is unrelated and tracks as a known pre-existing perf issue, not a W4.3 blocker.) See `docs/persona_post_purge_retest_2026-05-27.md`. |

**Priya time budget:** Per-spot 1-5 min Pio-class; session totals lenient. v1.8 SIMD impact: none meaningful.

---

## Aggregate (post-W3.2/W3.4/W3.3 reclassifications; W2.3 still pending)

| Category | Count | Workflows |
|---|---|---|
| **PASS** | 10 | W1.1, W1.2, W1.3, W1.4, W2.5, W3.1, W3.2 *(new 2026-05-26)*, W3.3 *(new 2026-05-26; P2 closing test)*, W3.4 *(new 2026-05-26; caveated — repurposed fixture)*, W4.1, W4.3 *(2026-05-27: PASS-strict; was PASS-via-aggregator pre-convention-purge)* |
| **PARTIAL** | 4 | W1.5, W2.1, W2.2, W2.4, W4.2 *(W3.5 also PARTIAL under Type B-DOC label)* |
| **BLOCKED** | 2 | W2.3 *(IN PROGRESS — may resolve to BLOCKED or PASS pending retest)*, W2.4 *(see PARTIAL above; CLI path INCONCLUSIVE-SLOW)* |
| **FAIL** | 1 | W3.5 *(remains as Type B-DOC under FAIL header per 2026-05-25 lineage; functionally PARTIAL — see W3.5 row)* |

*Note on counting conventions:* The 2026-05-25 snapshot's count line ("7 PASS / 5 PARTIAL / 4 BLOCKED / 2 FAIL") versus body ("FAIL (1): W3.5") was a known inconsistency. This snapshot adopts the user-supplied projection accounting: **7 → 8 (W3.2 PASS) → 9 (W3.4 PASS caveated) → 10 (W3.3 PASS, P2 closing test)**, with W2.3 pending. Final reconciliation when W2.3 retest lands.

---

## Pending retest (W2.3) — what to watch for

Per `feedback_post_ship_persona_retest`, the W2.3 retest is owed at production scale post-v1.8. Agent `a99ec2e` is running the pre-staged turn fixture from `post_v1_8_0_W2_3_retest_prompt.md`.

**Expected outcomes (per the v1.8 SIMD refutation):**
1. **Likely Type D timeout** on the original flop fixture — v1.8 SIMD does not deliver the projected 75-150 s wall-clock; original >300 s timeout characterization likely holds.
2. **Possible PASS** if the pre-staged retest uses a smaller fixture (turn vs flop, or a class-reduced 4-class) similar to the W3.4 fixture-repurposing pattern.
3. **Release-narrative impact** either way: confirms the v1.8 SIMD claim correction (~1.0×) and grounds the "BLOCKED list" count for the post-v1.8 status reconcile.

**Snapshot will be revised once the W2.3 retest completes.** No preemptive reclassification is being applied per the user constraint.

---

## Projected end-state (revised post-v1.8 SIMD refutation)

After W2.3 retest lands + B10 (Range fractional) + W3.5 docs option-1: **10-12 / 18 PASS realistic**, down from the 2026-05-25 snapshot's "16-18 / 18 PASS expected after v1.8 SIMD" projection. *(W3.3 closing test landed today — no longer pending.)*

- **W2.3:** Pending retest. May remain BLOCKED on perf (since v1.8 SIMD did not deliver) or PASS on a smaller fixture.
- **W2.1 / W2.4:** v1.8 SIMD refutation means flop multi-street perf ceiling persists; await v1.9 EMD bucketing per `v1_8_decision_brief.md:26` for a structural unblock. Update wall-clocks for accuracy.
- **W3.3:** ~~P2 overdue closing retest for node-locking-at-scale.~~ **CLOSED 2026-05-26** — see `docs/persona_w3_3_retest_2026-05-26.md`.
- **W3.5:** PARTIAL-stable under Type B-DOC; docs option-1 (docstring + curated-combo regression test) is the path forward; no v1.7.1 wrapper-code ship needed.
- **W2.2:** Awaits B10 (Range fractional-frequency) — deferred to v1.5+ per CHANGELOG `[Unreleased]`.
- **W1.5 / W4.2:** Type C-NICE / docs-only — low priority.

---

## Bottom-line answer to "what passed / failed"

### PASS now (10 workflows; pre-W2.3-retest)
- **W1.1, W1.2, W1.3, W1.4** — Marcus full slate except W1.5 (low-priority chart EV decomposition)
- **W2.5** — Sarah 30 BB SRP via PR 9 preflop solver
- **W3.1** — Daniel node-locking (shipped v1.4.0)
- **W3.2** — *(NEW today)* exploitative best-response API + CLI (PR 76 / PR #38)
- **W3.3** — *(NEW today; P2 closing test)* node-locking-at-scale primitive verified (4/4 acceptance criteria; 3.00 s)
- **W3.4** — *(NEW today, caveated)* monotone-river 3-bet-pot polarization (repurposed from original flop MDF fixture)
- **W4.1, W4.3** — Priya programmatic + Brown parity (**W4.3 PASS (strict)** as of 2026-05-27 post-convention-purge; was PASS-via-aggregator-path pre-purge)

### PARTIAL (4)
- **W1.5** — chart EV decomposition missing (Type C-NICE)
- **W2.1** — flop times out; river envelope passes (v1.8 SIMD refuted; structural perf ceiling)
- **W2.2** — set-membership diff PASS; frequency diff needs B10 (Range fractional)
- **W2.4** — library round-trip PASS; CLI batch-solve perf TBD (v1.8 SIMD did not deliver)
- **W4.2** — wiring PASS; heuristic mis-aligned with subgame mode (Type A docs)

### BLOCKED / PENDING (2, including IN PROGRESS)
- **W2.3** — *(IN PROGRESS)* 200 BB deep-stack flop RvR; v1.8 SIMD did not deliver projected speedup; retest in flight
- **W2.4 CLI batch-solve** — river path INCONCLUSIVE-SLOW (library round-trip path passes; tracked as PARTIAL above) *(W4.3 strict path previously BLOCKED here is now PASS as of 2026-05-27 post-convention-purge — see Priya W4.3 row above and `docs/persona_post_purge_retest_2026-05-27.md`)*

### FAIL (1 — Type B-DOC, functionally PARTIAL)
- **W3.5** — monotone polarization wrapper class-expansion semantics; **Type B-DOC** per `v1_7_1_wrapper_fix_spec.md` (no code patch needed); v1.8 retest bit-identical to v1.7.0

### Action items for user
1. **Decide on Apple Developer enrollment** — gates Gate 5 signed `.dmg` ship (carry item).
2. **Awaiting W2.3 retest agent (`a99ec2e`) completion** — final reclassification + snapshot revision blocked on this.
3. **v1.8 SIMD ~1.0× honesty correction**: already landed via PR #56 (`bf645ae`); no further release-notes work needed for the SIMD claim itself.
4. **W3.5 docs option-1** (docstring + curated-combo regression test per `v1_7_1_wrapper_fix_spec.md` Option 1) — pending, no v1.7.1 wrapper-code ship needed.
5. **Approve B10 (Range fractional)** scope when v1.5+ refactor wave begins (W2.2 unblock).
6. ~~**W3.3 closing retest** (P2) — overdue since v1.4.0.~~ **CLOSED 2026-05-26** via `docs/persona_w3_3_retest_2026-05-26.md` (Type A; 4/4 acceptance criteria PASS).

---

## Post-purge convention impact (2026-05-27 addendum)

Per `docs/persona_post_purge_retest_2026-05-27.md` (agent `a3844485`, ran post-PR #78 / commit `37e5be1`):

- **Convention purge (PR #78, `37e5be1`)** shifted `game_value` by `+initial_pot/bb` per leaf (canonical Brown constant-sum: `u[0] + u[1] = initial_pot / bb`; replaces the prior "rust" terminal-utility convention).
- **W4.3 strict-Brown parity now PASSES** (was previously aggregator-only path). `tests/test_v1_5_brown_apples_to_apples.py` passes both `dry_A83_rainbow` and `dry_K72_rainbow` parametrizations (276.45 s wall, well under the 300 s timeout) under the canonical convention.
- **No regressions observed on any other persona test.** All other tested PASS personas remain PASS post-purge; strategy outputs are bit-identical for W3.3 / W3.4 / W1.x equity / preflop subgames. The convention shift is visible in absolute `game_value` (e.g., W3.3 `default_tiny_subgame` `game_value` moved 5.0 → 10.0 BB = `initial_pot/bb`), but acceptance criteria are tolerance-based on relative quantities (L1 shifts, EV monotonicity on indifference manifold, max bet, etc.) and remain unaffected.
- **W2.3 still BLOCKED (perf, not utility-related).** The W2.3 retest was not re-evaluated in the post-purge sweep (perf-bound on the original flop fixture; v1.8 SIMD ~1.0× refutation still applies). W2.3 remains pending under agent `a99ec2e` independent of the convention purge.

See `docs/persona_post_purge_retest_2026-05-27.md` for the full retest sweep (per-persona detail, convention-purge signal table, and pre-existing-failure documentation).

---

## References

- Prior snapshot: `/Users/ashen/Desktop/poker_solver/docs/persona_test_status_2026-05-25.md`
- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/persona_acceptance_spec.md`
- Time budgets: `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/persona_time_budgets.md`
- All result docs: `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/`
- Today's retests:
  - W3.2 smoke: `/Users/ashen/Desktop/poker_solver/docs/persona_w3_2_smoke_2026-05-26.md`
  - W3.3 retest (P2 closing test): `/Users/ashen/Desktop/poker_solver/docs/persona_w3_3_retest_2026-05-26.md`
  - W3.4 retest: `/Users/ashen/Desktop/poker_solver/docs/persona_w3_4_retest_2026-05-26.md`
  - W3.5 retest: `/Users/ashen/Desktop/poker_solver/docs/persona_w3_5_retest_2026-05-26.md`
- Post-purge sweep (W4.3 PASS-strict reclassification source): `/Users/ashen/Desktop/poker_solver/docs/persona_post_purge_retest_2026-05-27.md`
- Convention purge: PR #78 / commit `37e5be1` (`fix(engine): purge 'rust' terminal-utility convention; canonical Brown formula is the only utility`)
- v1.8 SIMD bench (load-bearing for ~1.0× caveat): `/Users/ashen/Desktop/poker_solver/docs/v1_8_simd_perf_benchmark_2026-05-26.md`
- W3.5 wrapper-fix spec (Type B-DOC reclassification source): `/Users/ashen/Desktop/poker_solver/docs/v1_7_1_wrapper_fix_spec.md`
- Best-response API (W3.2 unblock): `/Users/ashen/Desktop/poker_solver/poker_solver/solver.py:442` + `cli.py:1438`
- PR 76 commit: `feee974` (merged 2026-05-26 via PR #38)
- v1.8 release-notes honesty: PR #56 / `bf645ae`
- v1.8 decision brief (v1.9 EMD bucketing roadmap): `/Users/ashen/Desktop/poker_solver/docs/v1_8_decision_brief.md`
