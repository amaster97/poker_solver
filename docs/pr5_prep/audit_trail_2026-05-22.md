# PR 5 audit trail — 2026-05-22

**Scope:** chronological record of the PR 5 (HUNL postflop solve + per-street memory profiler, Python tier) implementation, debugging, and pre-commit state.
**Branch:** `pr-5-hunl-postflop-solve` (working tree; uncommitted at time of writing).
**Base:** `integration` at `5832b2f` (PR 4 merge).
**Sources cited:** every claim references a doc, file, or git SHA. See §7 for the source manifest.

---

## 1. Timeline (chronological)

### 1.1 Spec lock — start of session (2026-05-21)
- **Spec drafted** at `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/pr5_spec.md`. End-to-end design: Stages A–E orchestrator + `MemoryProbe` + 3-fixture test plan + 13 critical correctness items + 10 deferred decisions (all defaulted at the bottom of the spec).
- **Consistency review locks applied 2026-05-21** (per `docs/autonomous_log.md` "Spec consistency fixes" §150–183):
  - **N7 / spec §14 #3:** `HUNLSolveResult` locked to subclass form (was open; PR 9 / PR 11 depend on `SolveResult.average_strategy` access pattern).
  - **B4:** dispatch composition cross-references PR 9 §6 as canonical; PR 5 spec §6 now contains a one-line pointer instead of duplicating dispatch ordering.
  - **I1:** "PR 4 is the last spec to touch `hunl.py`" wording corrected — PR 6 and PR 8 also modify `hunl.py` additively.
- All three are committed to `pr5_spec.md` (~+10 lines net per the autonomous-log entry).

### 1.2 Three-agent fan-out launched
- **Per `pr5_spec.md` §10 + agent prompts at `docs/pr5_prep/agent_{a,b,c}_prompt.md`:**
  - **Agent A** owns `poker_solver/hunl_solver.py` (Stages A–E orchestration; surgical edits to `solver.py`, `cli.py`, `__init__.py`, `pyproject.toml`).
  - **Agent B** owns `poker_solver/profiler/{__init__.py, memory.py}` (probe + dataclasses + key parser + psutil calibration).
  - **Agent C** owns `tests/test_hunl_postflop_solve.py`, `tests/test_memory_profiler.py`, `tests/fixtures/hunl_solve_fixtures.py` — **written strictly from spec without reading A or B's code** (spec §10 parallelism rationale).
- All three ran concurrently against the spec interface lock.

### 1.3 Initial agent output landed
- **Agent A produced** `poker_solver/hunl_solver.py` (417 LOC) + edits to `cli.py` (+191 lines), `solver.py` (+17 lines), `__init__.py` (+7 lines), `pyproject.toml` (psutil dep).
- **Agent B produced** `poker_solver/profiler/__init__.py` (29 LOC) + `poker_solver/profiler/memory.py` (510 LOC).
- **Agent C produced** `tests/test_hunl_postflop_solve.py` (649 LOC), `tests/test_memory_profiler.py` (408 LOC), `tests/fixtures/hunl_solve_fixtures.py` (351 LOC), `tests/fixtures/__init__.py`.
- Sanity: working-tree byte counts later confirmed by `docs/pr5_prep/pre_merge_sanity.md` §1 working-tree file inventory (14 files touched: 7 new + 7 modified).

### 1.4 Interpretation notes flagged
- Agent A noted in `commit_message_draft.md` §"Notable contract decisions":
  - **`iterations` default = 50,000** (cross-agent contract value) overrides spec §5 shorthand of `10_000` — documented as the surviving default.
  - **`HUNLSolveResult` non-frozen** because Python disallows `@dataclass(frozen=True)` subclassing of a non-frozen parent (`SolveResult` is non-frozen at `poker_solver/solver.py:20`). Treat as effectively-immutable; documented in the class docstring (see audit S1 below).
  - **`_install_in_memory_resolver_shim` monkey-patches `poker_solver.abstraction.buckets._cached_load` process-globally** with a re-install guard — documented in the orchestration docstring.
- Agent B added `measure_per_street(dcfr_solver)` as an alias for `snapshot()` against the "cross-agent contract from the orchestrator brief" — later flagged in the audit (S6) because the alias is not in spec.

### 1.5 PR 4 abstraction TURN coverage gap discovered
- During integration test runs, Agent C's tests that relied on `tiny_synthetic_abstraction()` (bucket counts `(4, 2, 2)`) tripped a PR 4-side coverage hole: `lookup_bucket` raises on the synthetic artifact's TURN boards AND the lossless fallback (no abstraction at TURN) hangs in the tree walk.
- Root cause: the synthetic `(4, 2, 2)` artifact lacks a complete TURN traversal. **This is a PR 4 fixture-coverage gap, NOT a PR 5 implementation bug.** Confirmed by the audit verdict (`audit_report.md` §S4) and the open-items audit (`open_items_audit_2026-05-22.md` §100 "PR 5 TURN abstraction coverage gap: 6 skipped tests. Owner: PR 6").

### 1.6 Six tests skip-marked
- Six tests in the new test files carry the same skip reason: *"PR 4 synthetic abstraction (4, 2, 2) lacks TURN coverage — lookup_bucket raises AND lossless fallback hangs. Tests deferred to PR 6 (Rust) or PR 4 fixture revisit."* (See `pre_commit_checklist.md` §2.)
- Skipped tests include `test_postflop_flop_solve_runs_without_crashing` (spec §11 #3), `test_postflop_flop_solve_strategy_is_valid` (spec §11 #1), `test_memory_profiler_matches_rss_within_10pct` (spec §11 #4), and `test_postflop_solve_memory_budget_aborts_cleanly` (spec §11 #5). Audit (`audit_report.md` §S4) flagged the implication: spec §11 critical-correctness items #1/#3/#4/#5 are implemented but un-exercised in CI.

### 1.7 Audit returned: NOT READY (initially), then 1 must-fix
- Audit agent ran per `docs/pr5_prep/audit_prompt.md` against the spec; output landed at `docs/pr5_prep/audit_report.md`.
- **Verdict:** "READY for commit AFTER must-fix items resolved" (`audit_report.md` §317).
- **Must-fix #1:** `poker_solver/hunl_solver.py:163-167` — post-solve `exploitability(game, avg)` walks the full lossless-flop tree even when `iterations=0`, hanging `test_postflop_solve_warns_for_lossless_flop_start` indefinitely (auditor killed it at 5 minutes 100% CPU; see `audit_report.md` §32–34).
- **Should-fix S1–S7:** 7 items (HUNLSolveResult frozen guard, exploitability cost on `log_every`, seed determinism test missing, river-only fallbacks missing for spec §11 #1/#3/#4/#5, `iterations_at_snapshot` docstring, `measure_per_street` alias spec-silent, CLI `--abstraction` flag missing).
- **Nice-to-fix N1–N5, Spec coverage gaps G1–G6:** documented for backlog (see `audit_followup_backlog.md` §114 "5-S4 + 5-CG1/CG2/CG3/CG4").

### 1.8 Must-fix patch landed
- **Patch:** `poker_solver/hunl_solver.py:164` — added guard `if log_every is None and avg and iterations > 0:` around the `history.append(exploitability(game, avg))` call.
- **Verified:** `docs/pr5_prep/exploitability_verification_2026-05-22.md` confirms both `exploitability(` call sites (lines 171 and 383) are now guarded. Test result: `pytest test_postflop_solve_warns_for_lossless_flop_start test_postflop_river_subtree_smoke_100_iters --timeout=30` → **2 passed in 0.32s**.
- Recorded in `wake_up_brief_2026-05-22.md` §36: "PR 5 must-fix #1 (lossless-flop exploitability guard) was patched at `hunl_solver.py:164` and verified."

### 1.9 Should-fix patches landed
- **S7 (CLI `--abstraction`):** `cli.py` argparse extended with `--abstraction PATH` flag scoped to `--hunl-mode postflop`; `_build_postflop_config` threads the loaded `AbstractionRef` onto the config. Closes the spec §16 "Fixture 2 shape" CLI invocation gap (was unreachable as written). Per `commit_message_draft.md` §66.
- **G1/G2/G3 river-only fallbacks:** added river-only versions of the four critical-correctness tests that the 6-skip set blocked:
  - `test_postflop_river_subgame_strategy_is_valid` (spec §11 #1).
  - `test_memory_profiler_matches_rss_river_subgame` (spec §11 #4; RSS calibration loosened to ±20-50% on the smaller river fixture).
  - `test_postflop_solve_memory_budget_aborts_cleanly_river_subgame` (spec §11 #5).
- These fallbacks live alongside the flop-fixture versions that remain in the skip set. Recorded in `commit_message_draft.md` §65–70 and `pre_commit_checklist.md` §3.

### 1.10 4 test failures + 5 leduc-diff timeouts caught by pytest-timeout
- `pytest-timeout>=2.3` was added to dev deps with a default 90s timeout (`pyproject.toml` `[tool.pytest.ini_options]` per `pre_merge_sanity.md` §4).
- The plugin caught 4 test failures + 5 `tests/test_leduc_diff.py` timeouts (long-running Leduc/Rust diff tests that pre-date PR 5). The pytest-timeout adoption per the autonomous decisions doc (`autonomous_decisions_2026-05-22.md` §44: "pytest-timeout (90s default / 3600s slow / 0 very_slow) active") forced explicit `@pytest.mark.timeout(...)` decorators on the heavy build tests.
- **Fixes (working-tree edits):** `tests/test_abstraction_buckets.py` (+7), `tests/test_abstraction_integration.py` (+6), `tests/test_hunl_tree.py` (+1), `tests/test_leduc_diff.py` (+12 — module-level `_LEDUC_DIFF_TIMEOUT` + decorators on 5 tests). See `pre_merge_sanity.md` §1 modified-files list.
- **Post-fix:** 199 passed / 9 skipped / 1 (xfail) stable on `pytest -m "not slow and not very_slow"` per `commit_message_draft.md` §126. (Per `pre_commit_checklist.md` §1 expected total: 151 pre-existing + ~22 new ≈ 173 collected; final stable count above includes the new river-only fallbacks.)

### 1.11 Working-tree crash + recovery (concurrent branch ops mistake)
- An intermediate session stashed PR 5 WIP (`stash@{0}: WIP on pr-5-hunl-postflop-solve: 5832b2f`) before the full set was assembled. A concurrent branch operation appears to have temporarily perturbed the working tree.
- **Recovery audit:** `docs/git_state_post_recovery.md` (2026-05-22) confirms full integrity:
  - Stash content is a strict subset of the current working tree (every line in stash is byte-equivalent to the corresponding hunk; safe-to-drop).
  - All 5 untracked + 10 modified files match the expected PR 5 footprint.
  - Branch tip still at `5832b2f` (PR 4 merge); PR 5 work uncommitted on top — expected state.
- Recorded again in `wake_up_brief_2026-05-22.md` §32–36.

### 1.12 Final commit (SHA TBD)
- **Pre-commit state at time of writing:** working tree green per `pre_merge_sanity.md` §6 summary table — all checks PASS except the noted `black --check` reformat blocker on 2 PR 5 test files (single-step fix: `black tests/test_memory_profiler.py tests/test_hunl_postflop_solve.py`).
- **Commit message draft:** `docs/pr5_prep/commit_message_draft.md` (136 lines). Co-Authored-By line present.
- **Status:** UNCOMMITTED. `git status` (verified 2026-05-22): branch `pr-5-hunl-postflop-solve`, 10 modified + 5 untracked. **No commit SHA exists yet.**
- **Authorized policy:** "PR 5 ship policy: autonomous commit + push if green" (`autonomous_decisions_2026-05-22.md` §8). Commit fires once the black reformat is applied.

### 1.13 Push + merge to integration
- **Pending.** PR-branch pushes are autonomous per the standing D3 policy (`autonomous_log.md` §117). Main merges still require explicit user OK (`autonomous_decisions_2026-05-22.md` §10 stop list; default: hold).
- Once committed: push `pr-5-hunl-postflop-solve` to origin, then merge into `integration` (non-fast-forward). Main merge of integration into `main` is **deferred to user** (`wake_up_brief_2026-05-22.md` §3 priority 1).

---

## 2. What was built — 7 files / ~1,777 LOC summary

| File | LOC | Owner | Purpose |
|---|---|---|---|
| `poker_solver/hunl_solver.py` | 417 | Agent A | `solve_hunl_postflop` orchestration (Stages A–E); `HUNLSolveResult` subclass of `SolveResult`; `_validate_postflop_config`; `_attach_abstraction`; `_run_with_probe`. |
| `poker_solver/profiler/memory.py` | 510 | Agent B | `MemoryProbe`, `MemoryReport`, `StreetMemoryEntry`, `_parse_street_from_key` (handles both lossless and bucketed formats per spec §7.3); psutil calibration. |
| `poker_solver/profiler/__init__.py` | 29 | Agent B | Public surface exports. |
| `tests/test_hunl_postflop_solve.py` | 649 | Agent C | ~12 + 3 river-only fallback tests (rejection paths, river-subgame solve, intuition gauntlet, OOM abort, lossless-flop warning). |
| `tests/test_memory_profiler.py` | 408 | Agent C | ~10 + 1 river-only fallback test (probe interface, key parsing, RSS calibration, dataclass invariants). |
| `tests/fixtures/hunl_solve_fixtures.py` | 351 | Agent C | `river_subgame_config`, `flop_dry_3size_config`, `flop_full_menu_config`, `monotone_flop_config`, `tiny_synthetic_abstraction`, `tiny_synthetic_abstraction_ref`. |
| `tests/fixtures/__init__.py` | (small) | Agent C | Test fixture package marker. |
| **Total new** | **~2,364** | | (Per `wc -l` 2026-05-22.) |

**Modified (working tree):**
- `poker_solver/__init__.py` (+7) — 5 PR 5 exports + `__all__` update.
- `poker_solver/cli.py` (+191 / −10) — `--hunl-mode postflop`, `_build_postflop_config`, `_parse_bet_sizes`, `--abstraction PATH` flag.
- `poker_solver/solver.py` (+17) — postflop dispatch branch (push/fold short-circuit fires first per spec §6 + PR 9 §6 canonical).
- `pyproject.toml` (+9 / −2) — `psutil>=5.9` runtime dep + `pytest-timeout>=2.3` dev dep + `[tool.pytest.ini_options]` (timeout 90, markers `slow`/`very_slow`).
- `tests/test_abstraction_buckets.py` (+7), `tests/test_abstraction_integration.py` (+6), `tests/test_hunl_tree.py` (+1), `tests/test_leduc_diff.py` (+12), `tests/test_abstraction_emd.py` (+3 / −3) — pytest-timeout decorators, leduc-diff guard.
- `README.md` (+31 / −3) — incidental update.

Numbers cross-checked with `pre_merge_sanity.md` §1 inventory + `git_state_post_recovery.md` §4.

---

## 3. What was caught + fixed — bug list

| # | Bug | Location | Diagnosis | Fix | Source |
|---|---|---|---|---|---|
| 1 | Lossless-flop `exploitability()` walk hangs on `iterations=0` | `hunl_solver.py:163-167` | After `_run_with_probe` early-returns for zero-iter calls, the outer orchestrator unconditionally calls `exploitability(game, avg)`, which walks the full game tree twice. On a lossless-flop subgame this is unbounded. | Added guard `if log_every is None and avg and iterations > 0:` at line 164. Both `exploitability(` call sites (171 + 383) now guarded. | `audit_report.md` §20–46; `exploitability_verification_2026-05-22.md` |
| 2 | CLI `--abstraction PATH` flag missing from `--hunl-mode postflop` (spec §16 success criterion unreachable) | `cli.py:222-251` / argparse setup | `_build_postflop_config` had no path to attach an `AbstractionRef` from the CLI. | Added `--abstraction PATH` flag; threaded through `_build_postflop_config` to attach the loaded ref to the config. | `audit_report.md` §S7; `commit_message_draft.md` §66 |
| 3 | Spec §11 critical-correctness items #1/#3/#4/#5 implemented but un-exercised (the owning tests are in the 6-skip set) | `tests/test_hunl_postflop_solve.py`, `tests/test_memory_profiler.py` | The flop-fixture variants of strategy-validity, RSS-calibration, and OOM-abort tests depend on the TURN-coverage gap in PR 4's `(4, 2, 2)` synthetic artifact and are skipped. No fallback existed. | Added 3 river-only fallback tests: `test_postflop_river_subgame_strategy_is_valid` (#1), `test_memory_profiler_matches_rss_river_subgame` (#4; tolerance loosened to ±20-50% on the smaller fixture), `test_postflop_solve_memory_budget_aborts_cleanly_river_subgame` (#5). | `audit_report.md` §G1/G2/G3; `commit_message_draft.md` §66–70 |
| 4 | 4 test failures + 5 `test_leduc_diff` timeouts under pytest-timeout 90s default | `tests/test_abstraction_buckets.py`, `tests/test_abstraction_integration.py`, `tests/test_hunl_tree.py`, `tests/test_leduc_diff.py` | Long-running build tests + Leduc Rust diff tests exceed the new 90s default. | Added `@pytest.mark.timeout(180)` decorators on heavy build tests; module-level `_LEDUC_DIFF_TIMEOUT` + decorators on 5 Leduc-diff tests; one `tests/test_abstraction_emd.py` black-shape reformat. | `pre_merge_sanity.md` §1 modified files; `autonomous_decisions_2026-05-22.md` §44 |
| 5 | Working-tree perturbation from concurrent branch ops + stash | working tree | Intermediate `stash@{0}` (`fcc91fe`) saved an incomplete PR 5 state pre-final-assembly; a concurrent branch op temporarily confused the working tree. | Recovery audit confirmed stash is a strict subset of WT; full PR 5 footprint intact on `pr-5-hunl-postflop-solve` HEAD `5832b2f` with 10 modified + 5 untracked. Stash safe-to-drop. | `git_state_post_recovery.md` |

**Not yet fixed (deferred to commit):**
- 6 black-formatter blocks on `tests/test_memory_profiler.py` + `tests/test_hunl_postflop_solve.py` (pure whitespace/parenthesization; single-command fix per `pre_merge_sanity.md` §3 "Black failures").

---

## 4. Spec amendments locked autonomously this round

Each amendment rationale + locking authority (file:line where the lock landed) is cited. Recorded in `commit_message_draft.md` §83–99 and `autonomous_log.md` §150–183 (consistency-review entries):

1. **`HUNLSolveResult` is a SUBCLASS of `SolveResult` (not a tuple, not a wrapper).** Authority: consistency-review N7 (autonomous_log.md §158); locked at `pr5_spec.md` §14 #3. Rationale: PR 9's `PreflopSolveResult extends HUNLSolveResult` and PR 11's library mode relies on `SolveResult.average_strategy` access — tuple form rejected.

2. **`HUNLSolveResult` inherits `SolveResult`'s mutability.** Python disallows `@dataclass(frozen=True)` on a subclass of a non-frozen parent (`SolveResult` is non-frozen at `poker_solver/solver.py:20`). Documented in the `HUNLSolveResult` docstring (`hunl_solver.py:57-61`); treat as effectively-immutable. Audit flagged as S1 (developer-experience, not correctness).

3. **`MemoryReport.river_ratio` denominator = `solver_arrays_total_bytes` (not `grand_total_bytes`).** Authority: spec §7.2 + §8.5 "PLAN.md trigger." Three decision zones (<30% / 30–50% / >50%) documented on the property. Confirmed in `audit_report.md` §198 ("matches spec §8.5"). Rationale: numerator excludes per-infoset overhead so numerator + denominator share the same "arrays-only" basis.

4. **Dispatch composition correction:** PR 3.5 push/fold guard requires `starting_street == Street.PREFLOP`. A FLOP-start config with 1500-chip stacks routes to the postflop solver (NOT the chart) — applying a preflop chart strategy to a flop-start config would be wrong. Spec §6 language suggesting otherwise was contradictory; **implementation chose the sensible behavior** and spec wording correction is queued for the next consistency review. See `audit_report.md` §229 ("dispatch is correct as-coded; recommend the spec §6 wording be corrected").

5. **`iterations` default = 50,000** (cross-agent contract value), overriding the spec §5 shorthand of `10_000`. Rationale: cross-agent contract wins; Agent A documented this in a code comment. Locked in the signature of `solve_hunl_postflop` per `commit_message_draft.md` §15.

6. **`abstraction=None` + `starting_street == Street.FLOP` → `UserWarning` (not error).** Authority: spec §14 #7 default; preserved in implementation per `commit_message_draft.md` §61. Allowed because the lossless flop is "large but not unbounded" per the spec.

7. **No `--memory-report-json` CLI flag.** Spec §14 #8 default preserved; memory report printed to stdout + accessible via `result.memory_report`.

8. **DCFR hyperparameters NOT exposed at CLI.** PLAN.md lock (α=1.5, β=0, γ=2.0). `dcfr_kwargs` parameter reserved for future override but empty in normal use. Verified by audit `audit_report.md` §241.

9. **`pytest-timeout>=2.3` adopted with 90s default / 3600s `slow` / 0 `very_slow` markers.** `autonomous_decisions_2026-05-22.md` §44. Forced explicit decorators on 4 pre-existing test files (see §1.10 bug #4 above).

10. **Six-test skip set with identical, grep-discoverable skip reason.** All 6 tests carry: *"PR 4 synthetic abstraction (4, 2, 2) lacks TURN coverage — lookup_bucket raises AND lossless fallback hangs. Tests deferred to PR 6 (Rust) or PR 4 fixture revisit."* Per `pre_commit_checklist.md` §2.

---

## 5. What's deferred

### 5.1 Six skip-marked tests (TURN gap)
- Tests deferred until PR 6 Rust port re-enables them OR a future PR 4 fixture revisit adds full TURN coverage.
- Includes `test_postflop_flop_solve_runs_without_crashing`, `test_postflop_flop_solve_strategy_is_valid`, `test_memory_profiler_matches_rss_within_10pct`, `test_postflop_solve_memory_budget_aborts_cleanly`, and 2 others.
- Mitigation in PR 5: river-only fallback tests (see §1.9) exercise the same critical-correctness items on the river-only fixture.
- Tracked at `open_items_audit_2026-05-22.md` §100, `audit_followup_backlog.md` §114, `roadmap_status_2026-05-22.md` §108.

### 5.2 PR 4 kmeans homogeneity threshold (95% → 50%)
- PR 4 spec target is 95% homogeneity but `tests/test_abstraction_emd.py` floor is loosened to 50% per spec §8 Agent C #3 ("soft sanity check"). Pure-Python kmeans++ init produces ~56% on the synthetic fixture.
- Owner: PR 6 (Rust kmeans expected to tighten). Per `open_items_audit_2026-05-22.md` §101, `wake_up_brief_2026-05-22.md` §121, `pr4_prep/ready_to_commit_summary.md` §45.

### 5.3 Audit should-fix S1–S7 (7 items) not patched
- S1 (HUNLSolveResult frozen guard / runtime `__setattr__`), S2 (exploitability cost docstring on `log_every`), S3 (seed determinism test), S5 (`iterations_at_snapshot` docstring), S6 (`measure_per_street` alias spec clarification). S4 + S7 + G1/G2/G3 partially closed this round (river-only fallbacks + CLI flag). The remainder is in `audit_followup_backlog.md` (5-S1, 5-S2, 5-S3, 5-S5, 5-S6).

### 5.4 Audit nice-to-fix N1–N5 (5 items)
- N1 (`_install_in_memory_resolver_shim` is permanent / not a context manager), N2 (`_DICT_OVERHEAD_RATIO=0.5` magic constant), N3 (`_ = np` unused-import suppression), N4 (CLI `getattr` defensive pattern now redundant), N5 (numpy import docstring deletion).
- All cosmetic; in cleanup PR scope.

### 5.5 Spec coverage gap G4 (no determinism test)
- Spec §11 #10 "same seed → identical strategy" has no corresponding test. Profiler is deterministic by construction (Python dict insertion order + fixed per-street tuple order per `audit_report.md` §258), but the end-to-end claim is unverified.
- Tracked at `audit_followup_backlog.md` 5-CG4.

### 5.6 First real HUNL solve never run end-to-end
- Per `wake_up_brief_2026-05-22.md` §118: "No full HUNL solve has been performed end-to-end yet. Everything to date is Kuhn-scale + Leduc-scale + river-only synthetic-abstraction smokes."
- Production 200K-iter abstraction build (~10 hours wall-clock) also never executed. First real production solve happens in PR 6 (Rust port) or an explicit pre-PR-6 smoke if the user authorizes.

---

## 6. Lessons for future PRs

### 6.1 Interface drift between fan-out agents
- The `iterations` signature drifted between spec §5 shorthand (`10_000`) and the cross-agent contract (`50_000`). Resolution: cross-agent contract wins; Agent A documented the surviving default in a code comment.
- **Lesson:** when fan-out agents read both the spec and a cross-agent contract, the contract MUST be the single source of truth — or the spec must be edited in advance. Future PRs: pin all signature defaults to one canonical document (probably the agent prompts) before launching A/B/C.

### 6.2 Audit-vs-test redundancy
- The audit caught Must-fix #1 (lossless-flop hang) that the tests *also* would have caught — they hung instead of failing fast. The auditor noticed it via `pytest --timeout=...` not being installed in the local dev env (`audit_report.md` §13 "9 `pytest.mark.timeout` warnings — pytest-timeout plugin not installed; benign"), forcing manual kill.
- **Lesson:** install pytest-timeout BEFORE running the test suite for audit, not after. Future PRs: gate audit on pytest-timeout being installed (`audit_prompt.md` should `pip install` it first). Also: catastrophic hangs in tests should produce *test failures*, not infinite loops — every long-tree-walk test should carry a `@pytest.mark.timeout(...)` decorator.

### 6.3 Test-fixture coverage gaps cascade
- The TURN coverage gap in PR 4's `(4, 2, 2)` synthetic artifact blocked 4 of the 10 spec §11 critical-correctness items from being exercised in CI. The river-only fallbacks were a real save, but they exercise smaller arrays with looser tolerances (calibration loosened to 20-50% from spec's 10%).
- **Lesson:** when one PR's test fixtures are consumed by a downstream PR's tests, the upstream PR must build *complete-coverage* synthetic fixtures (not just the minimum needed for its own unit tests). Future PRs: include "consumer-PR fixture audit" as a checklist item.

### 6.4 Working-tree state hygiene during concurrent agents
- The intermediate stash + concurrent branch operations briefly perturbed the working tree, requiring a recovery audit (`git_state_post_recovery.md`). Recovery confirmed nothing was lost, but the audit took non-trivial time.
- **Lesson:** when running ≥3 concurrent agents that touch overlapping files (`pyproject.toml`, `__init__.py`), have a single shepherd agent serialize the file-level write order, or use per-agent worktrees from the start. Future PRs: prefer `EnterWorktree` for any agent that modifies shared root files.

### 6.5 Skip-set discipline
- The 6-test skip set was documented with identical, grep-discoverable reason strings (per `pre_commit_checklist.md` §2). This is a small thing but it made the audit's S4 finding actionable — without the identical strings, the auditor would have had to manually classify each skip.
- **Lesson:** every skip carries a non-empty, identical reason for skips with the same root cause. Future PRs: enforce this via a pytest plugin or a lint rule.

### 6.6 Don't extrapolate / instrument-and-revisit
- The whole point of PR 5 is the per-street memory profiler — it is the **measurement** that calibrates PR 4's 256/128/64 bucket-count decision. The spec resisted the temptation to "lock based on extrapolation" (per `feedback_no_extrapolate.md`) and committed to revisiting once data exists.
- **Lesson confirmed:** this discipline worked. The `river_ratio` < 30% / 30–50% / >50% decision zones are committed but not yet evaluated — they will be evaluated against Fixture 2's real numbers post-PR-5-commit.

---

## 7. Source manifest

Every claim in this audit trail cites one of:

- **Spec:** `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/pr5_spec.md`
- **Audit prompt:** `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/audit_prompt.md`
- **Audit report:** `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/audit_report.md`
- **Pre-merge sanity:** `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/pre_merge_sanity.md`
- **Pre-commit checklist:** `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/pre_commit_checklist.md`
- **Ready-to-commit summary:** `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/ready_to_commit_summary.md` — **NOTE: file not present on disk at audit-trail-write time** (referenced in task prompt but does not exist; `commit_message_draft.md` covers the same content).
- **Commit message draft:** `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/commit_message_draft.md`
- **Exploitability verification:** `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/exploitability_verification_2026-05-22.md`
- **Agent prompts:** `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/agent_{a,b,c}_prompt.md`
- **Autonomous log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` (S1–S10 cover PR 3 / 3.5; PR 5 entries are distributed across `autonomous_decisions_2026-05-22.md`, `open_items_audit_2026-05-22.md`, `wake_up_brief_2026-05-22.md` — there is no dedicated S-series entry for PR 5 implementation events in `autonomous_log.md`. Honest gap flagged.)
- **Autonomous decisions:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_decisions_2026-05-22.md`
- **Open items audit:** `/Users/ashen/Desktop/poker_solver/docs/open_items_audit_2026-05-22.md`
- **Wake-up brief:** `/Users/ashen/Desktop/poker_solver/docs/wake_up_brief_2026-05-22.md`
- **Git state recovery:** `/Users/ashen/Desktop/poker_solver/docs/git_state_post_recovery.md`
- **Audit follow-up backlog:** `/Users/ashen/Desktop/poker_solver/docs/audit_followup_backlog.md`
- **Roadmap status:** `/Users/ashen/Desktop/poker_solver/docs/roadmap_status_2026-05-22.md`

## 8. Honest about what wasn't fully verified

- **No real production HUNL solve has been run.** All PR 5 tests use small fixtures or the river-only fallback. The 256/128/64 bucket-count decision PLAN.md commits to revisiting is still pre-measurement.
- **Final commit SHA does not exist yet** as of this audit-trail write. The state is "uncommitted; ready to commit pending one black-reformat command."
- **No PR 5 entries exist in `autonomous_log.md`'s S-series** — implementation events are scattered across the other 2026-05-22 docs. Flagged as a recurring discipline gap (future PRs: a per-PR running log file matters more than scattered summary docs).
- **Test pass count `199 passed / 9 skipped / 1 (xfail) stable`** is taken from `commit_message_draft.md` §126; not independently re-verified at audit-trail-write time. The pre-commit checklist `pytest --collect-only -q | wc -l` expected total of ~173 may be a slightly different denominator (collected vs run).
- **Audit "should-fix S3" (seed determinism test) is not patched and the property is unverified end-to-end.** Profiler is deterministic by construction (`audit_report.md` §258), but the end-to-end "same seed → identical strategy" claim has no test.
- **The audit was run against the working-tree state, not a committed branch.** Future audits: prefer to audit a committed SHA so the audit is reproducible.

---
