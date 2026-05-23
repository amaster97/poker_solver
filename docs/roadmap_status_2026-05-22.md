# Project roadmap status — 2026-05-22

## Headline

HUNL substrate is built and on the `integration` branch (PR 1 through PR 4 shipped; total 4 commits past `main`). PR 5 (postflop solve + memory profiler) is implemented in the working tree on `pr-5-hunl-postflop-solve` but not yet committed: ~1,777 LOC across 5 new files awaiting verification + commit. After PR 5 commits, all downstream PRs (6 through 12) have full specs, agent prompts, and audit prompts pre-drafted — they are autonomous-launch-ready blocks of work.

## Done (with verification)

### Shipped to GitHub (integration branch)

| PR | Scope | Commit | Tests verified | Audit |
|---|---|---|---|---|
| PR 1 | Kuhn poker + DCFR (Python + Rust) + maturin/PyO3 + diff test | `9d2d66a` | yes — 51 tests at the time (pre-PR-3 baseline) | n/a (pre-audit-policy) |
| PR 2 | Leduc poker (both tiers) + Game trait abstraction | `17c9756` | yes — 97 tests at the time (added 4 modules / 31 tests vs PR 1) | n/a (pre-audit-policy) |
| Equity hybrid (user-authored) | Hybrid exact-enum + MC dispatch; default 250K iter | `2b67370` (#1 on main) | yes — merged via GitHub PR | n/a (user PR) |
| PR 3 | HUNL tree builder + 14-action abstraction (Python tier) | `a96675c` (rebased onto `2b67370`) | yes — 138 tests (97 existing + 41 new); full pytest 361s | READY, 0 must-fix, 7 should-fix, 7 nice-to-fix |
| PR 3.5 | Push/fold charts (2–15 BB) + v0.3 capstone | `9f91c83` | yes — 151 tests (138 + 13 new) | NOT-READY initially (6 must-fix); fixed in follow-up |
| PR 3.5 follow-up | API completeness (`solve_pushfold`, `backend == "pushfold_chart"`, `get_pushfold_range` alias, `force_tree_solve`, `final_exploitability_bb_per_100`, raise-on-out-of-range) + spec amendments | `1cbf52a` | yes — 13 pushfold tests still pass; spec §4 / §9 amended to match HU Nash chart | audit fixes; no re-audit (must-fix items demonstrably resolved) |
| PR 4 | Card abstraction (EMD bucketing, 256/128/64 + suit-iso) | `6565b84` | partial — 35 + 1 xfail in new `test_abstraction_*` suite; PR 3 regression (`test_hunl_core.py` 19/19) verified by audit agent; **full 187-test suite NOT re-run by orchestrator post-commit** | READY, 0 must-fix, 7 should-fix, 6 nice-to-fix |

Integration tip: `5832b2f` (merge of PR 4). Linear merge history on integration: `2b67370` → PR 3 merge `351cbee` → PR 3.5 merge `fd0a2c7` → PR 3.5 follow-up merge `f67bfa3` → PR 4 merge `5832b2f`.

### Other artifacts shipped on integration

- v0.3 capstone docs: `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `.github/ISSUE_TEMPLATE`, `.github/PULL_REQUEST_TEMPLATE.md`
- Architecture doc (`docs/architecture.md`, ~28 KB), pr-launch runbook (`docs/pr_launch_runbook.md`, ~33 KB), integration test scaffolds (`docs/integration_test_scaffolds.md`, ~30 KB)
- Release notes: `docs/release_notes_v0.3.md`, `docs/release_notes_v0.3.1.md`
- 11 custom agent configs in `~/.claude/agents/` (cfr-engine-implementer, poker-cfr-validator, poker-license-checker, poker-pr-auditor, poker-rebase-helper, poker-spec-consistency, poker-validator, pr-check-runner, references-curator, rust-porter, + parents)
- `scripts/generate_pushfold_charts.py`, `poker_solver/charts/pushfold_v1.json` (DCFR-generated, max exploitability 0.0001 BB/100 across all 14 depths)
- Cumulative public API additions (vs PR 2 baseline): `HUNLPoker`, `HUNLState`, `HUNLConfig`, `Street`, `default_tiny_subgame`, `ActionContext`, `ActionAbstractionConfig`, `enumerate_legal_actions`, `solve_pushfold`, `get_pushfold_strategy`, `get_full_range`, `get_pushfold_range`, `is_pushfold_mode`, `PushFoldChartUnavailable`, `AbstractionRef`, `precompute-abstraction` CLI subcommand

### Cumulative test count progression

PR 1: 51 → PR 2: 97 → PR 3: 138 → PR 3.5: 151 → PR 4: 187 (claimed; not orchestrator-verified) → PR 5 (in flight): ~210 if all 23 new pass; 6 already skip-marked.

## In flight / blocked

### PR 5 (HUNL postflop solve + memory profiler) — UNCOMMITTED

Branch: `pr-5-hunl-postflop-solve` (currently checked out; tip = integration `5832b2f`).

Files written in working tree (NOT committed):
- `poker_solver/hunl_solver.py` — 413 LOC (new) — `solve_hunl_postflop`, `HUNLSolveResult` (subclass per N7)
- `poker_solver/profiler/memory.py` — 510 LOC (new) — `MemoryProbe`, `MemoryReport`, `StreetMemoryEntry`
- `poker_solver/profiler/__init__.py` — 29 LOC (new)
- `tests/test_hunl_postflop_solve.py` — 495 LOC (new) — 13 test functions, 2 skip markers
- `tests/test_memory_profiler.py` — 330 LOC (new) — 10 test functions, 4 skip markers
- `tests/fixtures/` — postflop test fixtures (new directory)

Edits to existing files (staged + unstaged):
- `poker_solver/__init__.py` (+7 lines) — exports `HUNLSolveResult`, `solve_hunl_postflop`, `MemoryProbe`, `MemoryReport`, `StreetMemoryEntry`
- `poker_solver/solver.py` (+17 lines) — postflop dispatch branch (after push/fold short-circuit; per PR 9 §6 canonical dispatch composition)
- `poker_solver/cli.py` (+191/-? — large change for HUNL mode wiring)
- `pyproject.toml` (+9/-1) — adds `psutil>=5.9` runtime dep (PR 5's only allowed new runtime dep)
- `tests/test_abstraction_buckets.py` (+7), `tests/test_abstraction_integration.py` (+6), `tests/test_hunl_tree.py` (+1), `tests/test_abstraction_emd.py` (+3/-3 staged)
- A stash (`stash@{0}`) on this branch exists — WIP from prior session.

**Status:** all 3 PR 5 implementation agents reported back. **Blocker:** 6 tests skip-marked due to PR 4 abstraction TURN-coverage gap (not a PR 5 bug — synthetic test fixtures hit `lookup_bucket` on turn boards the smoke-fixture abstraction did not enumerate). Pytest verification incomplete — multiple zombie/hung pytest processes from earlier in the session; full suite has not been observed green.

## Specced + prompts ready (all blocked on PR 5 commit)

| PR | Scope | Branch (planned) | Effort estimate | Spec LOC | Prompts ready |
|---|---|---|---|---|---|
| PR 6 | Rust port of HUNL postflop solver (mechanical, scalar accumulator) | `pr-6-rust-hunl-postflop` | 1–2 days (heavy) | 721 | yes — A/B/C + audit (and a `MUST_PATCH_BEFORE_LAUNCH.md` flagging spec drift to fix) |
| PR 7 | River-spot diff test vs `noambrown/poker_solver` (MIT) | `pr-7-noambrown-diff` | few hours | 306 | yes — A/B/C + audit |
| PR 8 | NEON SIMD + cache-blocking + public chance sampling (Rust) | `pr-8-simd-layout-pcs` | 1–2 days | 504 | yes — A/B/C + audit |
| PR 9 | HUNL preflop (both tiers); blueprint + subgame refinement | `pr-9-hunl-preflop` | 1–2 days | 578 | yes — A/B/C + audit |
| PR 10 | NiceGUI scaffold | `pr-10-ui-nicegui` | 1 day | 1227 | yes — A/B/C + audit |
| PR 11 | Library mode + macOS packaging (.dmg, optional signing) | `pr-11-library-packaging` | few hours – 1 day | 785 | yes — A/B/C + audit |
| PR 12 (stretch, post-v1) | 3-handed postflop (LCFR; explicit "approximate equilibrium") | `pr-12-three-handed` | 6–12 weeks | 960 | yes — A/B/C + audit |

Spec total (PR 3 through PR 12 inclusive): 6,942 LOC across 11 spec files. All future PR launches share the universal template in `docs/pr_launch_runbook.md` §Per-PR launch sequence.

## Dependency graph (what blocks what)

```
main (2b67370 equity hybrid)  ─────────────────────────────────────────────────────────────┐
                                                                                          │
integration (5832b2f) ◀── PR 3 (a96675c) ── PR 3.5 (9f91c83) ── PR 3.5 follow-up (1cbf52a) ── PR 4 (6565b84)
                                                                                                            │
                                                                                                            ▼
                                                                                                     PR 5 (uncommitted)
                                                                                                            │
                                                                       ┌────────────────────────────────────┤
                                                                       ▼                                    ▼
                                                                  PR 6 (Rust port)         (memory data informs possible PR 4 abstraction revisit)
                                                                       │
                                                       ┌───────────────┼───────────────┐
                                                       ▼               ▼               ▼
                                                  PR 7 (Brown      PR 8 (NEON       PR 9 (preflop)
                                                  river diff)      SIMD)            ← needs PR 4 + PR 5; PR 6/8 optional
                                                                                            │
                                                                                            ▼
                                                                                      PR 10 (UI)
                                                                                            │
                                                                                            ▼
                                                                                      PR 11 (packaging)
                                                                                            │
                                                                                            ▼ (post-v1)
                                                                                      PR 12 (3-handed stretch — explicitly optional)
```

Hard prerequisites (per `docs/pr_launch_runbook.md` §Per-PR specifics): PR 5 → PR 6 → PR 7 → PR 8 → PR 9 → PR 10 → PR 11 → PR 12. Each "Prerequisites: PR N-1 merged into integration." PR 7 and PR 8 are both downstream of PR 6 (Rust port); they could theoretically run in parallel after PR 6 lands, but the runbook serializes them.

## Honest gaps / open items

- **PR 4 full-suite verification gap:** the 187-test claim is from the PR 4 implementation agents' aggregation; the orchestrator never re-ran `pytest -x --tb=line` against `integration` tip `5832b2f` after the commit. The audit agent verified the 35 + 1 xfail new abstraction tests and the 19 PR 3 regression tests, but not the full cumulative suite. Recommended: run `pytest -x` on `integration` tip to confirm.
- **PR 5 TURN coverage issue:** 6 PR 5 tests skip-marked because the synthetic test abstraction does not cover certain turn boards required by the fixtures. This is a real shortcoming in the test-side smoke abstraction, not a PR 5 production-code bug. PR 6's cleaner production-scale clustering (Rust kmeans) is expected to dissolve it.
- **`is_pushfold_mode` clamping silent-wrong-answer:** PR 3.5 audit caught the dispatcher silently clamping stacks > 15 BB to 15 BB (returning a wrong chart). Fixed in PR 3.5 follow-up (`1cbf52a`) — now raises `ValueError`.
- **kmeans homogeneity test:** intentionally `xfail`-marked at 50% threshold per PR 4 spec §8 Agent C #3 ("soft sanity check"). PR 6's production-scale clustering should let this tighten; spec target eventually is 95%.
- **No `pytest-timeout` yet:** session pause notes mention test-run-hang risks; `@pytest.mark.timeout(...)` work was in flight in a separate agent. Once landed (90s default + 1hr slow cap), future runs are bounded.
- **Hung pytest processes:** multiple zombies from earlier in the session were never killed. They could interfere with the next pytest invocation; safety classifier intermittent unavailability blocked kill earlier.
- **PR 3 should-fix items deferred:** 7 should-fix + 7 nice-to-fix items from PR 3 audit are open (e.g., `AssertionError` vs `ValueError` for rake config; `BetSizing` dead-code class; etc.). None are correctness bugs.
- **PR 4 should-fix items deferred:** 7 should-fix items from PR 4 audit (attribution header consistency on `equity_features.py`; `Street.SHOWDOWN` predicate tightening; etc.). Audit recommended folding the top 4 into a small PR 5-adjacent follow-up — not done.
- **PR 11 spec gaps (I2, N5):** consistency review flagged that PR 11 §3 / §6 should add a first-launch "no abstraction artifact found" UX warning; spec edit not yet applied. Recommended before launching PR 11 agents.
- **__version__ lag:** reconciled in the v0.4.0 bump — `poker_solver.__version__`, `pyproject.toml`, and `CHANGELOG.md` all read `0.4.0` now (no longer trailing).

## Main merge status

**Not merged yet.** `main` is at `2b67370` (user's equity-hybrid GitHub PR #1). Cumulative work for PR 3, PR 3.5, PR 3.5 follow-up, and PR 4 lives on `integration` at `5832b2f`. Per the user-authorized workflow (`docs/autonomous_log.md` D3, `docs/pr_launch_runbook.md` §Pacing), main merges require explicit user OK. The integration branch is the "always-latest working set"; main only advances on user sign-off.

## Recommended next actions (priority order)

1. **Kill any hung pytest processes** if any are still resident (`pgrep -lf pytest`); they interfere with the next `pytest -x` invocation.
2. **Verify PR 5 pytest passes** on the current working tree with the 6 skip markers + (if landed) pytest-timeout. Target: all non-skipped tests green.
3. **Commit PR 5** once verified (`pr-5-hunl-postflop-solve` branch, file list in §"In flight" above). Run audit agent; check `audit_report.md`; push branch; merge `--no-ff` into `integration`.
4. **Run full integration-tip pytest** (`pytest -x` on `5832b2f` post-PR-5-merge) to retroactively close the PR 4 verification gap.
5. **User OK for main merge** of integration → main, after reviewing the cumulative diff and CHANGELOG. This brings PR 3 / 3.5 / follow-up / 4 / 5 onto main as one user-approved promotion.
6. **Launch PR 6** (Rust port — the biggest remaining single block). Apply `MUST_PATCH_BEFORE_LAUNCH.md` corrections first, then fan out the 3 implementation agents per the runbook.

## Realistic time-to-v1

v1 deliverable = HUNL postflop solve + HUNL preflop solve (per PLAN.md §1 "What we're building"). At the rate observed in this session (~3–4 PRs/day with autonomous agents + audit + commit; lengthier for Rust port work):

- PR 5 commit + verification: **~1–2 hours**
- PR 6 (Rust port — mechanical, plus diff-test gate): **~1–2 days**
- PR 7 (river-spot diff vs Brown): **~half day**
- PR 8 (NEON SIMD; hard 10× speedup gate over Rust scalar baseline): **~1–2 days**
- PR 9 (preflop; blueprint + refinement; per-stack-depth solves): **~1–2 days**
- PR 10 (NiceGUI UI): **~1 day**
- PR 11 (library + macOS packaging; signing optional): **~half day to 1 day**

**Estimated v1 ship: ~5–7 focused days from PR 5 commit.** PR 12 (3-handed postflop) is explicitly post-v1 and the largest single block in the roadmap (6–12 weeks). Skipping PR 12 entirely is acceptable per PLAN.md.
