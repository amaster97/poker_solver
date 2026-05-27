# PLAN.md archive (2026-05-26 prune)

This file captures sections moved out of PLAN.md during the 2026-05-26 continuous-pruning pass. Content here is preserved for reasoning trail; the live PLAN.md keeps only current-decision and load-bearing material.

**Source:** PLAN.md at 102 KB / 600 lines pre-prune. Target: < 60 KB.

**Prune scope:**
- §7 Kickoff docs staged (shipped — historical artifact)
- §12 Burst progression log: shipped milestone rows (v1.4.x → v1.7.0 inclusive) + dry-run #1-#10 detail
- §13 Lessons from this burst (codified in memory rules — kept as one-line summary in live plan)
- Status block superseded narrative (the R10/R11 multi-paragraph chain — replaced by current-state one-liner)
- §3 architecture note from 2026-05-24 R11-resolution narrative (RESOLVED)

Content below is verbatim from PLAN.md sections as they existed pre-prune. References from main PLAN.md remain stable: §1 (decisions), §2 (PR roadmap), §3 (architecture), §4 (verification), §5 (parallelization), §6 (open items), §8 (references), §9 (archive/decision log), §10 (burst close), §11 (in-scope this burst). The prune did not change any current decisions.

---

## Archived from §3 (2026-05-24 R11-resolution status notes)

These were status notes appended to §3 during the 2026-05-23 → 2026-05-24 burst. R11 RESOLVED on 2026-05-24; the test-side double-swap was reverted (PR 55-ext dropped from bundle); v1.7.1 shipped the corrected 7-PR Hybrid bundle. Lessons codified in memory `feedback_redundant_swap_hazard.md` and `feedback_long_running_session_wrap.md`.

**Status note (2026-05-24, R11 RESOLVED test-side, PENDING-CONFIRMATION):** Dry-run #8's depth-0 AA/TT/88 60-75pp divergence is RESOLVED as a **TEST-SIDE double-swap**, NOT an engine bug. Kernel verified correct three ways: (1) AA-vs-AA minimal fixture matches Brown at FP precision, (2) `dcfr_vector.rs` re-audit found no semantic bug, (3) 3 independent investigations converged on the same diagnosis. **Root cause:** PR 40 (test-side range slot swap) + PR 55-ext (wrapper-side range swap) each correctly applied an independent convention swap; stacked together they NET-SWAP ranges — same outcome as no swap. Each PR had its own diff-test PASS in isolation, but no test stacked them; the v1.7.1 dry-run #8 was the first joint exercise. **Bundle correction:** drop PR 55-ext from ship; v1.7.1 now 7 PRs (PR 50 + 51 + 52 + 53b + 54 + 55 + 56). Dry-run #9 in flight to confirm corrected bundle clears at depth-0. **v1.7.1 ship back on table** conditional on dry-run #9. Prior `docs/STATUS_2026-05-24_r11_engine_bug.md` framing ("REAL engine-level disagreement") is now REFUTED — engine is correct. See `docs/STATUS_2026-05-24_r11_resolved.md`.

**Prior status note (2026-05-24, post-R9 P0/P1 convention mismatch confirmed) — RETAINED for trail:** The two-tier architecture is unchanged. R6's root-cause diagnosis (phantom `ALL_IN` at facing-all-in nodes) is a mechanical-site fix in the action-menu enumeration of BOTH tiers; differential parity is preserved by paired Rust + Python fix in PR 50. R7 reframes external-reference comparisons as sanity checks, not strict ground truth. R8 closed Sites 1-2 of the suit-encoding hazard hunt (paired `h <-> d` index-as-char swap in `noambrown_wrapper.py`; PR 52). **R9 closes Site 3 of the same hazard hunt**: P0/P1 player-index convention mismatch — Brown's `players[0]` = first-to-act on river; our P0 = second-to-act on river. The diff harness was comparing wrong-player strategies end-to-end. **PR 55 applies a wrapper-boundary swap in `_parse_brown_dump`** (option B from the investigation): single seam, callers convention-naive. Terminal-utility convention has been independently audited and is CORRECT in Python reference + Rust scalar + Rust vector form. The architecture description below stands as-is; both R8 and R9 are wrapper-side test bugs that did not surface engine-side issues.

---

## Archived from §7 (Kickoff docs staged)

The kickoff doc framework was used to launch PRs 6/7/4.5/10a/11/10b/8/9. All referenced PRs are shipped:

- `docs/pr4_5_audit_debt/launch_kickoff.md` — PR 4.5 shipped at `9f09d49` / v0.5.2.
- `docs/pr6_prep/launch_kickoff.md` — PR 6 HUNL postflop Rust port shipped at `6c438b8`, v0.5.0.
- `docs/pr7_prep/launch_kickoff.md` — PR 7 river-spot diff test shipped at `d135add`, v0.5.1.
- `docs/pr8_prep/launch_kickoff.md` — PR 8 NEON SIMD + cache-blocking + public chance sampling shipped in v1.2.0 cluster.
- `docs/pr9_prep/launch_kickoff.md` — PR 9 HUNL preflop shipped in v1.2.0 cluster.
- `docs/pr10_prep/launch_kickoff_10a.md` — PR 10a NiceGUI scaffold shipped at `b880032`, v0.6.0.
- `docs/pr10_prep/launch_kickoff_10b.md` — PR 10b real solver bindings shipped in v1.2.0 cluster.
- `docs/pr11_prep/launch_kickoff.md` — PR 11 library mode + macOS packaging shipped at `bbb4395`, **v1.0.0 GA**.
- `docs/pr12_prep/launch_kickoff.md` — PR 12 3-handed postflop stretch (optional, explicitly approximate) — DEFERRED.

Sequencing intent (historical): PR 6 → PR 7 → PR 4.5 → PR 10a → PR 11 (v1.0.0 GA) → PR 10a.5 + PR 8 + PR 9 → PR 10b → PR 12.

**Remaining post-GA work (as of 2026-05-23 late, v1.5.1 shipped) — SUPERSEDED by §10 + §11 in current PLAN.md.** Historical content:

- PR 24a + PR 24b (v1.6.0): SHIPPED at `d885bca` (closes Gate 2).
- PR 33 + PR 34 + PR 35 + PR 40 (v1.6.1 queued): refuted; superseded by v1.7.1 Hybrid path (PR 50 + 51 + 52 + 54 + 55 + 56 + 53c).
- Gate 4 production run: 50K PASS recorded; 200K-iter in flight as of 2026-05-25 (status moved to live PLAN.md §10 Gate 4).
- PR 12 (3-handed stretch, optional): DEFERRED, out-of-burst.

**User-facing docs (shipped v1.4.3):** USAGE.md + DEVELOPER.md refreshed in v1.4.3 (PR 30); reflect v1.4.x capabilities, known CLI gaps, perf cliffs, two-tier honesty. Files are in repo root; pointers retained in live PLAN.md.

---

## Archived from §12 (Burst progression log — shipped milestones + dry-run detail)

The full row-by-row tag ladder is preserved here. Live PLAN.md §12 keeps only in-flight / recent rows.

### Shipped milestones (v1.4.0 → v1.7.0)

| Tag / version | Scope | Status |
|---|---|---|
| **v1.4.0** | Node-locking | shipped |
| **v1.4.1** | Asymmetric contributions (PR 22) — tag `89a124b` | shipped |
| **v1.4.2** | Docs honesty pass + `@pytest.mark.slow` marker convention (PR 25/26 + module docstring) — tag `d9094c2` | shipped |
| **v1.4.3** | Validation hardening + `Range.diff` + USAGE/DEVELOPER docs refresh (PR 27/30/31) — tag `eea3a8b` | shipped |
| **v1.5.0** | True Nash RvR — Rust vector-form CFR (PR 23) + Brown apples-to-apples acceptance test (PR 28) | shipped; acceptance test had compound test bugs (NOT solver bug); resolved in v1.6.1 |
| **v1.5.1** | Docs/test rigor bundle (PR 32 PR 7 docs honesty + PR 36 aggregator-vs-true-Nash distinction + PR 37 equity helper + PR 38 persona verdict downgrades) | shipped |
| **v1.6.0** | GUI Gate 2 surfaces (PR 24a + 24b) — tag `d885bca`; docs refresh `94007ca` + README v1.6.0 patch `ca8c7af` + .dmg attached (45 MB, SHA256 `0443e8f0...`) | shipped (closes Gate 2) |
| **v1.6.0 → v1.7.0 interstitial** | Cargo.lock skew fix `bf6f966` + README .dmg pointer/install guide `433ccfd` | shipped 2026-05-23 |
| **v1.6.1 (original strict-gate plan)** | A83 deep-cap close via Path A + Path C + PR 46 + PR 33-40 bundle | REFUTED 2026-05-23 (dry-run #2 NO-GO; archived #1) |
| **v1.6.1-engine (Path D, RETIRING post-R7)** | Engine improvements only: PR 46 panic fix (`cd56761`) + PR 35c paired cap-guard + optional PR 33 + PR 40; Brown acceptance xfailed pending structural-parity reframe | RETIRING post-R7 — `docs/v1_6_1_path_d_decision.md`. Acceptance reframe handles what Path D was reaching for; replaced by v1.6.1-engine (R7 composition) |
| **v1.6.1-engine (R7 composition)** | PR 50 (paired Rust + Python facing-all-in guard) + PR 51 (`dcfr_vector.rs:651` panic; needed for A83 completion) + acceptance test reframe (strict per-action gate → sanity-check structural assertions: direction-of-aggression + shallow-frequency agreement) | superseded by v1.7.1 Hybrid path |
| **PR 50** | Phantom-ALL_IN facing-all-in guard (paired Rust + Python); closes R6 mechanical root cause of K72/A83 22-42pp deep-cap divergence | merged in v1.7.1 |
| **PR 51** | `dcfr_vector.rs:651` panic re-emerged fix | merged in v1.7.1 |
| **PR 52** | Suit-encoding fix in `noambrown_wrapper.py`: explicit char-to-char mapping; closes R8 TEST-SIDE bug | merged in v1.7.1 |
| **PR 53** | Acceptance test reframe: replace strict per-action 5e-2 gate with sanity-check structural assertions | superseded by PR 53b/c |
| **Dry-run #4** | All 3 engine/wrapper fixes (PR 50 + PR 51 + PR 52) running together | FAILED at coverage gate 2026-05-24 — 53.3% strict-eligible; missing renderer fix (PR 54) drops rows |
| **PR 54** | Renderer fix; `_rust_history_substr_for_canonical` adds `stack_ceiling` kwarg | merged in v1.7.1 |
| **PR 55 (R9 close)** | P0/P1 player-index convention swap at the wrapper boundary in `_parse_brown_dump` | merged in v1.7.1 |
| **Dry-run #5** | Retest with PR 50 + 51 + 52 + 54 stacked | superseded by dry-run #6 |
| **Dry-run #6** | Retest with the 5-fix stack PR 50 + 51 + 52 + 54 + 55 | GAP-REMAINS 2026-05-24 — coverage 100%, per-cell A83 = 0 matches (mixed-suit hands diverge), K72 = 124 matches (same-suit subset). Smoking-gun for 3rd wrapper-side paired-swap bug |
| **PR 56 (R10 close)** | Hand-string sort-order canonicalization at wrapper boundary in `_parse_brown_dump` / `_brown_hand_key` | merged in v1.7.1 |
| **PR 55-extend (conditional)** | Extended PR 55 axis-swap | CLOSED without merging — was R11 double-swap with PR 40 |
| **Dry-run #7** | Retest with the full 6-fix stack PR 50 + 51 + 52 + 54 + 55 + 56 | RESULT IN 2026-05-24 — coverage 100%, 63% cells > 1e-1; residual is algorithmic-not-labeling. Triggers Hybrid path. |
| **PR 53b** | Conflict-resolution PR — merge PR 53 acceptance reframe against PR 11 asymmetric-fixture deltas | superseded by PR 53c |
| **Dry-run #8** | Final pre-ship retest — 8-PR bundle | FAILED at depth-0 2026-05-24 — surfaced AA/TT/88 60-75pp at root; framed initially as engine bug (R11); resolved as PR 40 + PR 55-ext double-swap |
| **PR 53c (R7 + R11 indirect close)** | Acceptance reframe with Layer 3 deep-cap threshold loosened to 1.9 | merged in v1.7.1 |
| **Dry-run #9** | Corrected 7-PR bundle (PR 55-ext EXCLUDED) | 3 of 4 LAYERS PASS 2026-05-24 — Layer 3 hit residual against un-loosened 5e-2 ceiling = irreducible action-menu design difference. Triggers PR 53c. |
| **Dry-run #10** | Re-verification with PR 53c carrying loosened Layer 3 threshold (1.9) | expected ALL 5 LAYERS PASS; triggers user-OK + ship |
| **v1.7.1 (Hybrid path, SHIP-READY)** | Final 7-PR bundle (PR 50 + 51 + 52 + 54 + 55 + 56 + PR 53c). PR 55-ext (#13) EXCLUDED (R11 double-swap with PR 40); PR 53 (#7) and PR 53b (#14) SUPERSEDED by PR 53c (#15) | SHIP-READY 2026-05-24 — pending DR#10 PASS + user OK |
| **v1.7.1 ship retry #1** | First ship attempt | HALTED 2026-05-25 — golden files stale |
| **PR 59 (golden refresh)** | Refresh golden fixtures + regenerate-mode flag | merged |
| **v1.7.1 ship retry #2** | Second ship attempt | HALTED 2026-05-25 — Brown apples-to-apples gate fired `pytest.skip()` when Brown binary not built; silent-skip pattern |
| **Brown gate hard-fail fixture patch** | Convert silent `pytest.skip()` to HARD-FAIL | superseded by PR 60 |
| **v1.7.1 ship retry #3** | Third ship attempt | KILLED mid-cargo-test 2026-05-25 — external interrupt |
| **PR 60 (Brown silent-skip HARD-FAIL fix)** | Full PR replacing wrapper-only patch | merged |
| **Ship script missing-cherry-pick-line patch** | `scripts/ship_v1_7_1.sh` missing `git cherry-pick "$SHA_PR60"` line | merged |
| **v1.7.1 ship retry #4** | Fourth ship attempt on 10-PR bundle | KILLED mid-cargo-test 2026-05-25 — agent-spawn wall-clock execution limit |
| **v1.7.1 manual ship recommendation** | After 4 agent-driven retries killed at same point | resolved via background nohup retry pattern |
| **v1.7.0** | PR 43 `solve_range_vs_range_nash` wrapper (`6f5cd43` + `32de21c`) + PR 39 CLI ergonomics (`25972d7`); release commit `3843ce7` | shipped 2026-05-23 (engine-only) |
| **v1.7.x .dmg rebuild** | PR 44 packaging fix verified on `pr-44-dmg-packaging-fix` @ `c09abe7` | merged (PR #3) |
| **v1.7.x docs** | PR 48 USAGE.md class-expansion semantics + Nash perf scope | merged (PR #2) |
| **v1.7.1 wrapper fix** | hypothesized `solve_range_vs_range_nash` class→combo expansion bug | CANCELED post-R5 (archived #3-4) |
| **Gate 4 plan** | Operational spec at `docs/gate_4_operational_plan.md`; 50K + 200K invocation patterns | spec staged |
| **v1.6.x+** | SIMD vector kernels in Rust (NEON 128-bit) | superseded by v1.8 candidate spec |
| **v1.7.1 ship retry #5** | Fifth ship attempt; detached as background process PID 49016 | DIED 2026-05-25 — halted at `test_parity_happy_path_runs_to_completion` pytest-timeout=60s vs actual ~188s |
| **PR #27 (pytest timeout structural fix)** | Bump pytest timeout to 300s in `scripts/ship_v1_7_1.sh` smoke matrix | merged to origin/main 2026-05-25 (commit `64fad46`) |
| **Post-pause merge wave (2026-05-25)** | Standalone PRs merged during/after pause: PR #16, #17, #21, #22, #27 | merged; origin HEAD moved `60a9818` → `1fefaff` |
| **v1.7.1 ship retry #6** | Sixth ship attempt via background nohup with `PYTEST_TIMEOUT=300` env override | launched on resume; superseded by retry #7 |
| **v1.7.1 ship retry #7** | Final ship retry | EXPECTED_MAIN bumped to bc7779aa (PR #31); v1.7.1 SHIPPED |

### v1.8 + Phase progression rows (some still in flight as of 2026-05-26)

| Tag / version | Scope | Status |
|---|---|---|
| **PR #20 cross-platform CI matrix** | macOS arm64 + macOS x86_64 + Linux x86_64 build/test workflow | merged |
| **PR #21 v1.7.2 CI release workflow** | `.github/workflows/release.yml` on `ship/vX.Y.Z` trigger, 120-min budget | merged (`bed37c4`) |
| **PR #22 ship hardening Guards B+C** | `@pytest.mark.golden` marker + silent-skip ban CI workflow | merged (`1fefaff`) |
| **PR #23 v1.8 Phase 1 SIMD discount kernel** | cross-platform `discount` kernel: SSE2 added on x86_64 alongside NEON | merged (`485aa8c`) |
| **PR #24 docs refresh v1.7.1/v1.7.2/v1.8** | CHANGELOG planned entries + README Status + USAGE §7b post-v1.8 perf characteristics | superseded by docs drift cleanup PRs |
| **v1.7.2 ship (CI-driven)** | First ship to use PR #21 workflow | queued post-v1.7.1 + post-PR-#21 throwaway-test |
| **PR #25 (PR 68 AVX2 runtime-detect)** | runtime CPU-feature detection for AVX2 on x86_64 | merged (`db8d646`) |
| **PR #26 (PR 63 v1.8 Phase 2 update_regret_sum SIMD)** | cross-platform `update_regret_sum` kernel | superseded by PR 63b (`8073bcc`) |
| **v1.8 Phases 2/3/4** | AVX2 4-lane f64; remaining kernels | merged across PRs #32, #33, #41 |
| **Gate 4 200K-iter run** | Extends Gate 4 50K PASS; river-pinned + turn-pinned tractable fixtures | river phase complete @ 5.28e-14 mbb/g monotone clean |

---

## Archived from §13 (Lessons from this burst — 11-reversal chain narrative)

The full R1-R11 narrative (each lesson with multi-paragraph behavior change) lived in §13 of pre-prune PLAN.md. All 12+ lessons are codified in memory rules:

- R6 → `feedback_empirical_over_audit.md`
- R7 → `feedback_external_solver_sanity_check.md`
- R8 → `feedback_index_as_char_hazard.md`
- R9 → `feedback_player_convention_mismatch.md`
- R10 → `feedback_parity_wrapper_hazard.md` (UPDATED with 3 wrapper-bug entries)
- R11 (engine bug framing REFUTED) → `feedback_redundant_swap_hazard.md`
- R11 (reframed-gate-masks-bugs) → `feedback_reframed_gate_masks_bugs.md`
- R10 cascade closing rule (REFUTED by R11) → `feedback_long_running_session_wrap.md` (UPDATED post-R11)
- Silent-skip + stale-golden hazards → `feedback_silent_skip_hazard.md`
- Agent-execution timeout → `feedback_agent_execution_timeout.md`
- Answer-first protocol → `feedback_interaction.md` (consolidated)
- Matched-config investigation → `feedback_nash_multiplicity_acceptance.md`

Full pre-prune narrative below (~140 lines, exact verbatim copy from old §13):

### Audit verifies STRUCTURE; only empirical test PASS verifies CORRECTNESS

Clean diff-look ≠ correct output. Every architectural PR ships with at least one empirical acceptance test; "looks good" without test-PASS is not a green light.

### Per-combo aggregator ≠ true Nash

`solve_range_vs_range` (Pluribus blueprint) selects baskets per-combo and inflates aggressive frequencies; W3.5 and W1.2 verdicts were downgraded (PR 38). Correctness verdicts must specify which path; aggregator is valid for blueprint frequency reads only. See `docs/aggregator_vs_true_nash_explainer.md`.

### Equity hand-waves without a calculator are 2-5× off

Any equity/EV assertion routes through the PR 37 calculator helper.

### "Acceptance test FAILS" ≠ "solver broken" — investigate test plumbing first

v1.5.0 9sTs vs b1500: both engines agreed ~100% fold; harness had action-ordering + range-slot misassignment. Before any "fix the solver" branch, isolate a per-call comparison that controls for action order, player slot, range-to-slot routing.

### Independent diagnostic threads converging is the strongest signal

PR 23 correctness verified by 4 converging threads. Critical findings spawn ≥2 independent diagnostics with different entry points; trust convergence over any single thread.

### Label-vs-semantics meta-rule (REINFORCED)

Both cascading misroutes traced to label-trust — function/test names promising semantics they don't deliver. At every boundary, read docstring + first 30 lines of impl + check I/O schema against the game-theoretic claim BEFORE trusting audit or test PASS. Source: `feedback_label_vs_semantics.md`.

### Brown convention divergence is a real game-definition difference, not a bug

Dry-run #2 NO-GO (K72 42pp / A83 27pp). Stacked: (a) residual phantom-ALL_IN at deep nodes (small fix); (b) Brown `base_pot × P_win` non-zero-sum vs our zero-sum `c_opp/bb` (game-definition divergence). Strict-tolerance gate framing was wrong from the start. Separate (1) "engine internally consistent + meets its own contract" from (2) "matches external reference under THEIR game definition." Never ship strict-tolerance gates of type (2) without verifying game definitions agree.

### Architecture-mismatched `.so` = silent test skip + pytest buffer hang

During v1.7.0 ship, x86_64 `.so` on arm64 host silently skipped Rust-backed tests; pytest buffer hung 31+ min. Every ship sequence with native code verifies `.so` arch before tests: `file poker_solver/_rust.cpython-*.so | grep arm64`. If empty → rebuild. Source: `feedback_dotso_arch_check`.

### Post-ship persona retest catches what unit tests miss

PR 43 shipped with 12 green unit tests; W3.5 15-class retest hit hard-FAIL (later reclassified to docs-only). Any wrapper/aggregation/expansion layer ships with at least one acceptance test at production-scale range cardinality (≥10-class for RvR Nash paths). Source: `feedback_post_ship_persona_retest.md`.

### W3.5 thread saw 5 sequential reversals

R1-R5 in `docs/archived_claims_2026-05-23.md` §4. R5 cost two staged-but-not-shipped artifacts before independent diff-test caught the misframing. Before any verdict triggers v-NEXT release or doc retraction, run independent diff-test on identical input vs the underlying engine call. The hard-FAIL number is a hypothesis, not a verdict. Source: `feedback_independent_verification.md`.

### R6 (2026-05-24)

Even when 4 audit agents confirm code structure is correct (PR 23 case), an empirical bug can persist; trace it to its mechanical site, don't accept "unexplained divergence" as the answer. R4-era framing of "Brown convention divergence is a real game-definition difference" was structurally plausible (zero-sum vs `base_pot × P_win`) AND consistent with the audit findings (both terminal-utility implementations correct under their own contracts). But it was the wrong root cause; the actual mechanical site was a missing `to_call < stack` guard on the action-menu `ALL_IN` push at facing-all-in nodes (phantom ALL_IN). When audit agents say "code is correct" but empirical tests still fail, KEEP digging at the mechanical level. **4 of the session's 6 reversals came from over-trusting code audits without sufficient empirical re-verification.** Source: `feedback_empirical_over_audit.md`.

### R7 (2026-05-24)

External reference solver comparisons should be SANITY CHECKS for shallow-spot agreement, not STRICT GATES that ignore intentional action-menu / abstraction differences. Brown is a sanity check, not strict ground truth — our action menu (33/75/100/150/200/AI) is intentionally richer than Brown's narrower set, and different action menus solve subtly different games. A 22-42pp deep-cap divergence on K72/A83 between two solvers with different action menus is consistent with both being correct under their own specs. When comparing to an external reference, treat it as SANITY CHECK; use it for direction-of-aggression agreement + shallow-frequency agreement + convergence properties — never for per-action exact match at deep-cap. Replace any strict-tolerance gate with structural sanity-check assertions. Source: `feedback_external_solver_sanity_check.md`.

### R8 (2026-05-24)

When measuring agreement between two systems with shared symbols but different indexing (e.g., our `"shdc"` vs Brown's `"cdhs"`), use CHAR-to-CHAR mapping, never INDEX-to-INDEX. Index-as-char is a silent paired-swap bug that distorts comparisons without producing obvious errors. `noambrown_wrapper.py` was treating suit indices as interchangeable between our `"shdc"` and Brown's `"cdhs"`, producing a silent `h <-> d` and `s <-> c` swap. The Brown comparison was running on a different game than what we believed. CI must include a round-trip identity test for any cross-system mapping layer; audit wrappers before engines when cross-system comparisons fail. Source: `feedback_index_as_char_hazard.md`.

### R10 (2026-05-24)

Hand-string encoding mismatches — same chars, different sort orders — produce silent paired-swap bugs on mixed-suit hands. Rust sorts a pair by `rank*4 + s_idx` where `s_idx` indexes `SUITS = "shdc"`, producing `KdKc`. Brown sorts by `suit*13 + rank` over `suits = "cdhs"`, producing `KcKd` for the SAME two cards. Mixed-suit pairs diverge. Detectable from day one via asymmetric-range fixtures. Canonicalize hand strings at the WRAPPER BOUNDARY (single seam), not in either engine. CI must include an asymmetric-range fixture for any cross-system mapping layer. Source: `feedback_parity_wrapper_hazard.md`.

### R9 (2026-05-24)

When comparing strategies between two solvers, verify the PLAYER-INDEX CONVENTION matches. "Player 0" may mean different things to different solvers. Brown's `players[0]` = first-to-act on river; our P0 = second-to-act on river. The Brown apples-to-apples diff harness was indexing both sides as `(player, history)` with no swap — silently comparing Brown's first-actor strategy against our second-actor strategy. Apply convention normalization at the wrapper boundary as a single seam. Always include at least one asymmetric-fixture parity test. Source: `feedback_player_convention_mismatch.md`.

### R10 cascade closing rule (REFUTED by R11)

10 reversals total this 22+hr session, 3 caught by user pushback (R2, R7, R9). Reversal arc: R1 "solver broken" → R2 "test-bugs-only" (user) → R3 "deep cap bug" → R4 REFUTED → R5 "wrapper class-expansion" REFUTED → R6 phantom-`ALL_IN` mechanical site → R7 Brown-as-sanity-check (user) → R8 suit-encoding paired char swap → R9 P0/P1 player-index (user) → R10 hand-string sort-order paired swap. Session declared SESSION-CLOSE 2026-05-24 03:48 local. **NOTE: This closing rule was REFUTED by R11 — the "marginal next reversal at 10+ deep is more likely to be a labeling artifact" claim was wrong this time.** Source: `feedback_long_running_session_wrap.md`.

### R11 (2026-05-24, supersedes session-close — engine bug framing)

Dry-run #8 surfaced AA / TT / 88 with IDENTICAL action menus diverging 60-75pp between our Rust and Brown. R7's "different action menus → different valid Nash" framing does NOT apply at depth-0 with identical menus. R11 was hiding behind the R7 reframe layer: the reframe loosened deep-cap tolerance, implicitly assumed shallow-spot agreement held, and made the depth-0 disagreement indistinguishable from acceptable design divergence. PR 53's 4-layer design caught R11 only because Layer 2 (shallow-strict) was retained. Lesson: when reframing a strict gate, ENSURE the new gate covers shallow disagreement specifically. Source: `feedback_reframed_gate_masks_bugs.md`. **NOTE: R11's "engine bug" framing was later REFUTED — R11 was actually a TEST-SIDE double-swap.**

### R11 resolution (2026-05-24, supersedes the "engine bug" framing)

Stacked-swap PRs from independent fixes can cancel and reproduce the original bug. PR 40 (test-side range slot swap) and PR 55-ext (wrapper-side range swap) each independently and correctly swapped one direction. Together they net-swap ranges. Always run a joint dry-run that stacks them before claiming they're independent fixes. Source: `feedback_redundant_swap_hazard.md`.

### R11 final resolution + session-close revocation

The session-close declared at R10 was PREMATURE: declared while DR#8 was still in flight on the 8-PR bundle. R11 emerged ~4 hours later from DR#8's depth-0 AA/TT/88 60-75pp disagreement. Kernel correctness verification protocol now codified: (1) minimal-fixture test, (2) semantic re-audit, (3) audit stacked test-side / wrapper-side fixes for net-cancellation. Only after ALL three converge on "kernel correct" is engine-level escalation permitted. Source: `feedback_long_running_session_wrap.md` (UPDATED post-R11). Final session stats: 26+ hr autonomous time, 11 reversals (R1-R11), 3 user-caught, 12+ memory rules codified, v1.7.1 SHIP-READY on the 7-PR Hybrid bundle.

### Silent-skip + stale-golden hazards in load-bearing acceptance tests (2026-05-25)

Two ship-process bugs surfaced back-to-back; both produced "green" CI signal without the gate actually verifying anything. Retry #1: golden files were stale. Retry #2: Brown apples-to-apples gate fired `pytest.skip()` because Brown binary wasn't built; smoke matrix interpreted `2 SKIPPED in 0.03s` as PASS. Smoke matrix should HARD-FAIL on missing prereqs. Golden files must refresh with expected behavior changes. CI guard forbids `pytest.skip` in load-bearing tests. After v1.7.1 ships, consider migrating to a CI-driven release flow (PR #21 lands this for v1.7.2+). Source: `feedback_silent_skip_hazard.md`.

### Agent-execution timeout (2026-05-25)

Long-running ship scripts (cargo test + maturin + pytest acceptance = 30-45 min) exceed per-spawn agent execution limits. Retries #3 and #4 both died silently at the cargo-test phase at ~25-30 min wall-clock. For any ship/build/test sequence >20 min, EITHER detach as background process and monitor separately, OR migrate to CI runner, OR invoke from user's terminal session. Source: `feedback_agent_execution_timeout.md`.

### Answer-first protocol (2026-05-25)

Direct yes/no questions get a direct answer FIRST, then context. Question-then-explanation order was a recurring drift. Source: `feedback_interaction.md` (consolidated).

### Matched-config investigation (2026-05-25) — VERDICT C: action menu wasn't the explanation; Nash multiplicity at deep-cap rows is the actual residual

R7's reframe (Brown = sanity check, deep-cap divergence = action-menu artifact) was adopted on plausibility grounds but UNVERIFIED until the matched-config probe ran. The probe patched `_build_rust_config_for_spot` to force `force_allin_threshold=0`, `min_bet_bb=0`, re-ran the v1.5.0 acceptance test, and produced **bit-identical strict-gate numbers**. Worst-disagreeing rows on K72 ALL concentrate at depth ≥ 11, in facing-all-in `(c, f)` 2-action leaves, with pocket AA — signature of **Nash mixed-strategy non-uniqueness**. Both solvers are essentially Nash (Brown exploitability 0.06 chips at 2000 DCFR iters = 0.006% of pot); they just landed on different mixed-strategy points within the same indifference manifold. **Hybrid path framing is empirically confirmed, not hand-waved.** Source: `feedback_nash_multiplicity_acceptance.md`. See `docs/matched_config_investigation.md` for full Phase 1-4 audit trail.

---

## Archived top-status block narrative (2026-05-25 mid-day RESUMED snapshot)

The pre-prune PLAN.md status block ran ~25+ lines of detailed "in flight" status including:

- v1.7.1 ship retry #6 launched via background nohup with PYTEST_TIMEOUT=300 override
- Detailed listing of 16 open PRs at that time
- Matched-config investigation 2026-05-25 VERDICT C summary
- R10 finding (2026-05-24): hand-string sort-order divergence confirmed wrapper-side bug
- R9 finding (2026-05-24): P0/P1 player-index convention mismatch
- R8 finding (2026-05-24, still in force)
- R7 reframe (2026-05-24, still in force as framing rule)
- v1.6.1-engine (v1.7.1) composition — UPDATED post-R10 with full PR-by-PR list
- Gate 5 PARTIAL CLOSE status
- Persona retests post-R5/R6 detailed verdicts

All of these are SUPERSEDED by current state on origin/main (5ead08f, 2026-05-26):

- v1.7.1 SHIPPED (PR 50/51/52/54/55/56 + PR 53b/53c all merged; see `1bb699e`, `9a5c4d4`, `3899ca6`, `3af1257`, `a2a75be`, `6c9d7f0`, `0aec0a7`, `49c1421`)
- v1.8 Phases 1/2/3/4 all SHIPPED (PR #23, #41, #33, #32 = `485aa8c`, `8073bcc`, `a712950`, `77e751c`)
- PR #20 cross-platform CI matrix SHIPPED (`7edb1aa`)
- PR #21 v1.7.2 CI release workflow SHIPPED (`bed37c4`)
- PR #22 ship hardening Guards B+C SHIPPED (`1fefaff`)
- PR #25 AVX2 runtime-detect SHIPPED (`db8d646`)
- PR 76 exploitative play (B9) SHIPPED (`feee974`)
- v1.7.x .dmg rebuild + arch label + version stamp SHIPPED (`5ead08f`, `728206e`)
- B10 range fractional-frequency: spec landed (PR #36, `9dbe7ff`); 4-PR implementation sequence still queued

The live PLAN.md status block has been replaced with a current-state pointer to `docs/STATUS_*.md`. Detailed in-flight narrative is here for trail.

