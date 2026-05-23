# Audit follow-up backlog (consolidated)

**Compiled:** 2026-05-22
**Source audits:** `pr3_prep/audit_report.md`, `pr3_5_prep/audit_report.md`, `pr4_prep/audit_report.md`, `pr5_prep/audit_report.md`, `open_items_audit_2026-05-22.md`
**Scope:** rolls up 32 open should-fix + 25 nice-to-fix + 6+6 coverage gaps + 7 deferred user decisions.
**Constraint:** owners / effort are recommendations only; orchestrator decides actual PR routing.

---

## 1. Per-PR breakdown

### PR 3 (HUNL tree) — 7 should-fix, 7 nice-to-fix open

| # | Item | Citation | Recommended owner | Effort |
|---|---|---|---|---|
| 3-S1 | `HUNLState.config` duplicates `HUNLPoker.config`; pick one source of truth | pr3_prep/audit_report.md L24 | maintenance pass | S |
| 3-S2 | `initial_contributions=(0,0)` dead-money bypass undocumented; comment-or-reject | pr3_prep/audit_report.md L26 | next maintenance pass | S |
| 3-S3 | `test_hunl_default_tiny_subgame_solvable_in_one_minute` lacks `time.perf_counter` bound | pr3_prep/audit_report.md L28 | cleanup PR | S |
| 3-S4 | `_action_context` pot formula comment clarifying the subtraction | pr3_prep/audit_report.md L30 | cleanup PR | S |
| 3-S5 | `enumerate_legal_actions` stack≤0 bypass is unreachable; assert or remove | pr3_prep/audit_report.md L32 | next maintenance pass | S |
| 3-S6 | `Card.from_str` mixed-case behavior unasserted; one-line guard in canonicalization test | pr3_prep/audit_report.md L34 | cleanup PR | S |
| 3-S7 | `include_all_in=False` flag not honored by `compute_raise_to(ACTION_ALL_IN, ctx)` helpers | pr3_prep/audit_report.md L36 | next maintenance pass | S |
| 3-N1 | `AssertionError` → `ValueError` for rake fields | pr3_prep/audit_report.md L40 | cleanup PR | S |
| 3-N2 | `_normalize_hole_action` typed `Union` annotation | pr3_prep/audit_report.md L42 | next maintenance pass | S |
| 3-N3 | `_pack_hole_outcome` keep 8-bit; just comment | pr3_prep/audit_report.md L44 | defer | S |
| 3-N4 | `BetSizing` class — remove or document as convenience | pr3_prep/audit_report.md L46 | cleanup PR | S |
| 3-N5 | `bet_size_fractions` default duplicated across 3 configs | pr3_prep/audit_report.md L48 | defer | S |
| 3-N6 | `test_hunl_initial_state_with_ante` add `street_aggressor == 1` assert | pr3_prep/audit_report.md L50 | cleanup PR | S |
| 3-N7 | `test_hunl_max_tree_depth_bounded` river-only depth bound off | pr3_prep/audit_report.md L52 | cleanup PR | S |
| 3-N8 | Unused `field` import in `hunl.py` | pr3_prep/audit_report.md L54 | cleanup PR | S |
| 3-N9 | `Street.SHOWDOWN` no-cards comment | pr3_prep/audit_report.md L56 | cleanup PR | S |

### PR 3.5 (push/fold) — 11 should-fix, 7 nice-to-fix open (must-fix all patched in followup `1cbf52a`)

| # | Item | Citation | Recommended owner | Effort |
|---|---|---|---|---|
| 3.5-S1 | INFO log on chart dispatch missing | pr3_5_prep/audit_report.md L29 | cleanup PR | S |
| 3.5-S2 | `PushFoldChartUnavailable` does not subclass `ValueError`; out-of-range stack inconsistent | pr3_5_prep/audit_report.md L31 | cleanup PR | S |
| 3.5-S4 | `test_pushfold_invalid_position_raises` patched off-spec; spec amendment or revert | pr3_5_prep/audit_report.md L35 | cleanup PR | S |
| 3.5-S5 | `frequencies_sum_consistently` 80% floor needs spec cross-ref comment | pr3_5_prep/audit_report.md L37 | cleanup PR | S |
| 3.5-S6 | Strategic-equivalence assertion absent from generator (or alt validation pass) | pr3_5_prep/audit_report.md L39 | PR 6 + maintenance | M |
| 3.5-S7 | `tests/test_pushfold_regen.py` smoke test missing | pr3_5_prep/audit_report.md L41 | cleanup PR | M |
| 3.5-S8 | `v1-placeholder` accepted at load time; reject in loader | pr3_5_prep/audit_report.md L43 | cleanup PR | S |
| 3.5-S9 | Document infoset-key format for chart dispatch | pr3_5_prep/audit_report.md L45 | cleanup PR | S |
| 3.5-S10 | `game_value=0.0` silent-wrong for chart dispatch | pr3_5_prep/audit_report.md L47 | cleanup PR | M |
| 3.5-S11 | `exploitability_history=[0.0]` should surface per-depth value | pr3_5_prep/audit_report.md L49 | cleanup PR | S |
| 3.5-S12 | CLI `--hunl-mode pushfold` absent | pr3_5_prep/audit_report.md L51 | next PR with CLI touchups | M |
| 3.5-S14 | BB-call coverage band test at d=4 (`[60%, 80%]`) | pr3_5_prep/audit_report.md L55 | cleanup PR | S |
| 3.5-N1 | `_canonical_hand_classes` / `_all_hand_classes` duplicated | pr3_5_prep/audit_report.md L61 | cleanup PR | S |
| 3.5-N2 | Non-standard `notation` field — lock or drop | pr3_5_prep/audit_report.md L63 | cleanup PR | S |
| 3.5-N3 | Hand-strength sort vs lexicographic — document | pr3_5_prep/audit_report.md L65 | defer | S |
| 3.5-N4 | `_coerce_freq` 4-decimal clip loses precision | pr3_5_prep/audit_report.md L67 | PR 9 (preflop) | M |
| 3.5-N5 | `is_pushfold_mode` doesn't gate on `PUSHFOLD_CHART_VERSIONS` | pr3_5_prep/audit_report.md L69 | defer | S |
| 3.5-N6 | README per-depth claim wording | pr3_5_prep/audit_report.md L71 | cleanup PR | S |
| 3.5-N7 | `_canonical_hand_classes()` dead code | pr3_5_prep/audit_report.md L73 | cleanup PR | S |

### PR 4 (card abstraction) — 7 should-fix, 6 nice-to-fix, 6 coverage gaps open

| # | Item | Citation | Recommended owner | Effort |
|---|---|---|---|---|
| 4-S1 | `equity_features.py` add attribution-clean header | pr4_prep/audit_report.md L20 | cleanup PR | S |
| 4-S2 | `infoset_key` predicate tighten for SHOWDOWN | pr4_prep/audit_report.md L22 | cleanup PR | S |
| 4-S3 | `lookup_bucket` uncovered-board error message clarity | pr4_prep/audit_report.md L24 | cleanup PR | S |
| 4-S4 | `save_abstraction` `build_timestamp` breaks byte-determinism; env-overridable | pr4_prep/audit_report.md L26 | defer (no consumer) | S |
| 4-S5 | `_kmeans_plusplus_init` empty-cluster fallback unreachable; mark assert | pr4_prep/audit_report.md L28 | cleanup PR | S |
| 4-S6 | `compute_river_features` ignores `seed` — short-circuit rng spawn | pr4_prep/audit_report.md L30 | cleanup PR | S |
| 4-S7 | Autosize threshold (`mc_iterations < 5000`) magic; sentinel for `max_boards_per_street` | pr4_prep/audit_report.md L32 | PR 6/9 prep | M |
| 4-N1 | `_canonicalize` / `_apply_suit_perm_to_hand` rename to spec names | pr4_prep/audit_report.md L38 | cleanup PR | S |
| 4-N2 | uint8 K≤256 dtype boundary comment | pr4_prep/audit_report.md L40 | cleanup PR | S |
| 4-N3 | `canonicalize_for_suit_iso` tuple→packed-int (PR 6 PyO3) | pr4_prep/audit_report.md L42 | PR 6 | M |
| 4-N4 | `abstraction` field `compare=False` comment | pr4_prep/audit_report.md L44 | cleanup PR | S |
| 4-N5 | `dists * dists` → `np.square(dists)` | pr4_prep/audit_report.md L46 | cleanup PR | S |
| 4-N6 | `precompute.py` bare-print helper consolidation | pr4_prep/audit_report.md L48 | defer | S |
| 4-CG1 | No test for 1 GB size-guard fire | pr4_prep/audit_report.md L84 | cleanup PR | S |
| 4-CG2 | No test for CLI `--flop-mode exact` | pr4_prep/audit_report.md L86 | cleanup PR | M |
| 4-CG3 | No test that `infoset_key` lossless at preflop when abstraction set | pr4_prep/audit_report.md L88 | cleanup PR | S |
| 4-CG4 | No test for `AbstractionRef.version` mismatch path | pr4_prep/audit_report.md L90 | cleanup PR | S |
| 4-CG5 | No isolated test for `required_boards` autosize override | pr4_prep/audit_report.md L92 | cleanup PR | S |
| 4-CG6 | No test for `_kmeans_plusplus_init` degenerate path | pr4_prep/audit_report.md L94 | cleanup PR | S |

### PR 5 (HUNL postflop solve) — 1 must-fix, 7 should-fix, 5 nice-to-fix, 6 coverage gaps open

| # | Item | Citation | Recommended owner | Effort |
|---|---|---|---|---|
| 5-M1 | `hunl_solver.py:163-167` lossless-flop exploitability hang on `iterations=0` (2-line guard) | pr5_prep/audit_report.md L20 | PR 5 pre-commit (CRITICAL — see §5) | S |
| 5-S1 | `HUNLSolveResult` non-frozen sanity guard / mypy ignore | pr5_prep/audit_report.md L51 | cleanup PR | S |
| 5-S2 | `log_every` docstring warn about per-chunk exploitability cost | pr5_prep/audit_report.md L68 | cleanup PR | S |
| 5-S3 | Add `test_solve_is_deterministic_under_seed` (spec §11 #10) | pr5_prep/audit_report.md L84 | cleanup PR | S |
| 5-S4 | River-only fallbacks for spec §11 #1/#3/#4/#5 (5-G1..G3) | pr5_prep/audit_report.md L99 | cleanup PR | M |
| 5-S5 | `MemoryReport.iterations_at_snapshot` docstring | pr5_prep/audit_report.md L116 | cleanup PR | S |
| 5-S6 | `measure_per_street` alias spec clarification | pr5_prep/audit_report.md L128 | cleanup PR | S |
| 5-S7 | CLI `--abstraction PATH` flag for postflop | pr5_prep/audit_report.md L136 | cleanup PR | M |
| 5-N1 | `_install_in_memory_resolver_shim` process-global; doc or context manager | pr5_prep/audit_report.md L150 | defer | M |
| 5-N2 | `_DICT_OVERHEAD_RATIO = 0.5` magic constant | pr5_prep/audit_report.md L156 | defer | S |
| 5-N3 | `_ = np` unused-import suppression awkward | pr5_prep/audit_report.md L162 | cleanup PR | S |
| 5-N4 | `_print_memory_section` defensive `getattr` no longer needed | pr5_prep/audit_report.md L168 | cleanup PR | S |
| 5-N5 | Drop unused numpy import | pr5_prep/audit_report.md L174 | cleanup PR | S |
| 5-CG1 | Strategy validity test (§11 #1) on river-only fixture | pr5_prep/audit_report.md L274 | cleanup PR | S |
| 5-CG2 | Psutil calibration test on smaller fixture (§11 #4) | pr5_prep/audit_report.md L278 | cleanup PR | M |
| 5-CG3 | OOM abort path test on tiny budget (§11 #5) | pr5_prep/audit_report.md L282 | cleanup PR | S |
| 5-CG4 | Determinism test (§11 #10) | pr5_prep/audit_report.md L286 | cleanup PR | S |
| 5-CG5 | Convergence smoke spec §9.3 moving-average alignment | pr5_prep/audit_report.md L290 | cleanup PR | S |
| 5-CG6 | `tiny_synthetic_abstraction` fixture spec mismatch (strip or document) | pr5_prep/audit_report.md L294 | cleanup PR | S |

---

## 2. Cross-PR clusters (theme-batched)

**Cluster A: Attribution / license headers** (~1-2 hr total)
- 4-S1 (`equity_features.py` attribution header)
- 5 attribution-doc completeness already-good per audits

**Cluster B: Test coverage gaps — strategy/memory validity** (~3-4 hr total)
- 5-S4 + 5-CG1/CG2/CG3/CG4 (river-only fallback set covering spec §11 #1/#3/#4/#5/#10)
- 3-S3 (HUNL tree wall-clock bound)
- 3-S6 (mixed-case canonicalization assert)
- 5-CG5 (convergence smoke alignment)
- 4-CG1..CG6 (size-guard, exact-flop CLI, preflop lossless, version mismatch, required_boards, degenerate kmeans++)

**Cluster C: Error-message + error-type drift** (~1-2 hr total)
- 3-N1 (rake AssertionError → ValueError)
- 3.5-S2 (PushFoldChartUnavailable inheritance)
- 3.5-S4 (test patched off-spec)
- 4-S3 (uncovered-board user-facing remedy)
- 4-S2 (SHOWDOWN predicate)

**Cluster D: Spec-vs-impl naming drift** (~2-3 hr total)
- 3.5-S9 (chart infoset key format docstring)
- 4-N1 (rename `_canonicalize` / `_apply_suit_perm_to_hand` per spec)
- 5-CG6 (`tiny_synthetic_abstraction` fixture mismatch)
- 5-S6 (`measure_per_street` alias)

**Cluster E: Silent-wrong-answer surface** (~2 hr total — biggest correctness gain)
- 3.5-S10 (chart `game_value=0.0`)
- 3.5-S11 (chart `exploitability_history=[0.0]`)
- 5-M1 (lossless-flop exploitability hang)

**Cluster F: Performance / cost transparency** (~1 hr total)
- 5-S2 (log_every cost warning)
- 5-N1 (resolver shim doc)
- 5-N2/N3/N4/N5 (numpy / dict overhead constants & dead defensiveness)

**Cluster G: Dead code / unused fields** (~30 min total)
- 3-N4 (`BetSizing` class)
- 3-N8 (unused `field` import)
- 3.5-N7 (`_canonical_hand_classes` dead)
- 3.5-S8 (`v1-placeholder` accepted)

**Cluster H: Test enhancement nits** (~1-2 hr total)
- 3-N6 (`street_aggressor==1` assert)
- 3-N7 (depth-bound formula)
- 3.5-S5 (test floor cross-ref comment)
- 3.5-S14 (BB-call coverage band test)
- 3.5-S7 (`test_pushfold_regen.py` smoke)

---

## 3. Recommended cleanup PR ("PR 5.5" or rolled into PR 6 prep)

**Highest-value 8 items** (estimated 6-9 hr total; biggest cleanup ROI; mostly Cluster B + E + C):

1. **5-M1** — lossless-flop exploitability hang guard (correctness; only must-fix open) — **Cluster E, S, blocking PR 5 commit per `open_items_audit_2026-05-22.md` recommendation 2**.
2. **5-S4 + 5-CG1/CG3/CG4** — river-only fallbacks for spec §11 #1/#3/#5/#10 (closes biggest test holes in PR 5 critical-correctness; minimal-effort because fixture already exists; CG2 deferred because 50-iter calibration is less meaningful).
3. **3.5-S10 + 3.5-S11** — chart `game_value` and `exploitability_history` silent-wrong fixes (downstream consumers reading these fields get zeros).
4. **4-S1** — `equity_features.py` attribution header (license posture consistency).
5. **4-S2** — `infoset_key` SHOWDOWN predicate tighten (latent bug surface).
6. **3.5-S2** — `PushFoldChartUnavailable` ValueError inheritance (downstream `except ValueError` consumers).
7. **3.5-S4 + 3.5-S5** — spec-amendment-comment cross-refs for the two patched tests (audit trail completeness).
8. **3.5-S7** — `test_pushfold_regen.py` smoke test (single missing CI gate the spec mandates).

This bundle resolves: 1 must-fix + 8 should-fix + 4 coverage gaps + multiple cross-cluster lint nits picked up alongside the same files. Remaining 24 should-fix items are either deferrable (Cluster G, F) or naturally fold into the next feature PR touching the same module.

**Alternative: split into two passes** — (a) the must-fix + Cluster E pre-PR 6 (2-3 hr), (b) the Cluster B test-fallbacks + Cluster A/C/D nits rolled into a PR 6 polish window (~4-5 hr).

---

## 4. Safe to defer indefinitely

These have negligible benefit at the current stage; the cost of fixing exceeds the value.

- **3-N3** — `_pack_hole_outcome` 6-bit vs 8-bit packing. Byte alignment is more valuable than density.
- **3-N5** — `bet_size_fractions` default DRY across 3 configs. No anticipated divergence; DRY only if changes coming.
- **4-S4** — `save_abstraction` build_timestamp byte-determinism. No downstream consumer of byte-identical .npz exists.
- **4-N6** — `precompute.py` print helper consolidation. Pure cosmetic.
- **5-N1** — `_install_in_memory_resolver_shim` context manager. The "exactly once per process" contract is documented and fine for tests.
- **5-N2** — `_DICT_OVERHEAD_RATIO` calibration. Spec §7.4 documents it as a rough heuristic; per-interpreter drift is real but doesn't change the order-of-magnitude conclusion.
- **3.5-N3** — chart key sort order (hand-strength vs lex). Innocuous; either way fine.
- **3.5-N5** — `is_pushfold_mode` version gate. Loader catches the case.
- **3.5-N4** — `_coerce_freq` 4-decimal precision. Could revisit at PR 9 (preflop full solver) if the chart format is touched.

---

## 5. NEVER defer (correctness or latent-risk monitoring)

- **5-M1** (lossless-flop exploitability hang) — the only true correctness must-fix open across all four PR audits. Must be patched before PR 5 commits; otherwise `test_postflop_solve_warns_for_lossless_flop_start` hangs in CI and any user passing `iterations=0` on a lossless config hangs in production. **Two-line guard.** Per `open_items_audit_2026-05-22.md` recommendation 2.
- **3.5-S10** (`game_value=0.0` for chart dispatches) — silent-wrong-answer downstream. Any consumer reading `result.game_value` for chart-backed solves gets a wrong value.
- **3.5-S11** (`exploitability_history=[0.0]`) — same class of silent-wrong-answer.
- **4-S2** (SHOWDOWN `infoset_key` predicate) — latent: solver `is_terminal` guard currently masks it, but a future refactor that calls `infoset_key` at SHOWDOWN will trigger the defensive `ValueError` in `lookup_bucket` with a developer-facing message. Cheap to tighten now.
- **5-S3 / 5-CG4** (determinism under seed) — spec §11 #10 critical correctness item, currently UNTESTED. A regression in dict ordering or rng spawn order would silently break reproducibility. A trivial test prevents this.
- **3.5-S6** (strategic-equivalence collapse assertion) — spec deviates from generator structurally; either spec amendment or alt validation pass needed before push/fold chart regeneration happens again. Otherwise undetected suit-symmetry breakage in a future regen is possible.
- **4-CG1** (1 GB size-guard fire test) — the implementation exists, but no test exercises the failure path. Quick add.

---

## Item count summary

| Severity | Count |
|---|---|
| must-fix (open) | 1 |
| should-fix (open) | 32 |
| nice-to-fix (open) | 25 |
| spec coverage gaps | 12 |
| deferred user decisions (per open_items_audit §2) | 7 |
| **TOTAL open work items** | **77** |
| of which "truly worth doing" (cleanup PR + NEVER-defer) | ~32 (≈40%) |
| of which "safe to defer indefinitely" | ~9 |
| balance = naturally folds into next feature PR touching same module | ~36 |
