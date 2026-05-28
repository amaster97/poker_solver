# Held PRs Summary — 2026-05-28

Snapshot of the major HELD PRs currently awaiting user review/merge decision.
Pulled fresh from `gh pr view` on 2026-05-28. Author is `amaster97` on all four.

| PR  | Title                                                          | +/-       | Files | CI         | Mergeable |
| --- | -------------------------------------------------------------- | --------- | ----- | ---------- | --------- |
| 121 | feat: preflop chained orchestrator Phase A (#31)               | +1465/-0  | 3     | all green  | MERGEABLE |
| 122 | feat: full-tree preflop RvR engine (#32 Phase A)               | +2411/-0  | 6     | all green  | UNKNOWN\* |
| 126 | feat(ui): True Nash RvR mode toggle (#61) — default=true\_nash | +754/-22  | 5     | all green  | UNKNOWN\* |
| 20  | feat(ci): cross-platform CI matrix for v1.8 prep               | +128/-0   | 2     | mostly green; macos-13 QUEUED | UNKNOWN\* |

\* `UNKNOWN` mergeable status here means GitHub hasn't recomputed the mergeability hint, not that there's a conflict — all four targets `main` and the required CI checks are SUCCESS.

---

## PR #121 — Preflop chained orchestrator Phase A

**URL:** https://github.com/amaster97/poker_solver/pull/121
**Branch:** `feat/chained-orchestrator-phase-a` → `main`
**Created:** 2026-05-28T00:58:58Z

### What it does
Wraps `solve_hunl_preflop` + `solve_range_vs_range_nash` behind a single `solve_chained(...)` entry point. Stage 1 runs Route A blueprint per `(hero_class, villain_class)` pair; Stage 2 enumerates preflop terminal sequences and propagates reach probabilities to derive per-player continuation ranges; Stage 3 lazily solves postflop on demand via `result.solve_postflop(action_seq, board)`, with results cached by `(action_seq, board)`. The new public API surface (`solve_chained`, `ChainedSolveResult`, `ContinuationRanges`) is exported from `poker_solver/__init__.py`.

### Lines / files
- +1465 / -0 across 3 files:
  - `poker_solver/chained.py` (+936) — new module
  - `tests/test_chained_orchestrator.py` (+517) — new test file
  - `poker_solver/__init__.py` (+12) — re-export

### Test coverage
9 new tests in `test_chained_orchestrator.py`: 5 spec-required (2x2 BTN-vs-BB smoke, 15 BB push/fold equivalence with AA jam ≥0.85, continuation-range subset invariant, lazy cache identity-equal hit, postflop new-action-label E2E) plus 4 error-case sanity tests. Locally reported 9/9 PASS in ~4.5 min wall. No existing tests broken — spot-checked `test_preflop_python.py` (16 pass) and `test_range_vs_range_aggregator.py` (21 pass).

### Why it's held
Major new feature on the user-facing solver API surface. New 936-LOC Python module + new exported symbols. User explicitly requested HOLD for review per PR body.

### Merge recommendation: **READY-TO-MERGE**
- All CI green (Golden File Check, Ship Dry Run, Skip-Ban).
- `mergeable: MERGEABLE` (the only PR of the four with a confirmed clean merge).
- Test coverage is the strongest of the held set (spec-driven, includes equivalence checks).
- Phase A is locked scope — Python-only, no Rust changes, public API stable.

### What blocks if not merged
- Blocks the PioSolver-flavor iterated preflop/postflop loop (Phase B+).
- Does NOT block PR #122 — Route A reuses the existing per-hand solver; a swap to consume PR #122's vector engine is a single-function replacement (`_solve_preflop_range`) per the PR body.

---

## PR #122 — Full-tree preflop RvR engine Phase A

**URL:** https://github.com/amaster97/poker_solver/pull/122
**Branch:** `feat-preflop-rvr-engine` → `main`
**Created:** 2026-05-28T00:59:59Z

### What it does
Adds a brand-new Rust entry point `_rust.solve_hunl_preflop_rvr` that solves the full HUNL preflop tree with all 1326 hole-card combos active per player (i.e., `initial_hole_cards = None`). Postflop runouts collapse to a single equity-leaf value per `(hero_class, villain_class, suit_variant)` via a precomputed 169×169×3 table shipped at `assets/preflop_equity_169x169.npz` (292 KB, first binary asset in the repo). Action menu is user-confirmed: opens in absolute BB `[2,3,4,5]`, reraises as multipliers `[2,3,4,5]`, all-in always, cap 4. The existing `solve_hunl_preflop` fixed-hole path is NOT modified.

### Lines / files
- +2411 / -0 across 6 files:
  - `crates/cfr_core/src/preflop_rvr.rs` (+1237) — new vector-form DCFR driver
  - `crates/cfr_core/src/preflop_equity.rs` (+744) — equity-leaf table
  - `crates/cfr_core/tests/preflop_rvr_smoke.rs` (+207) — integration tests
  - `crates/cfr_core/examples/build_preflop_equity.rs` (+112) — precompute binary
  - `crates/cfr_core/src/lib.rs` (+111) — PyO3 binding
  - `assets/preflop_equity_169x169.npz` — binary asset

### Test coverage
- 70 cfr_core lib tests pass (was 57 baseline + 13 new for `preflop_equity` and `preflop_rvr`).
- 4 new integration tests pass — including AA-vs-KK closed-form (200 iter, fold prob = 0.0%, aggressive prob = 99.94%) and a 3-iter smoke (1326 hands × 206 decision nodes, 273K strategy entries, ~12s wall).
- `cargo build --release` and `cargo clippy --release --all-targets` clean.
- Pytest non-regression: `test_dcfr_diff.py` 5/5, `test_preflop_python.py` + `test_range_vs_range_aggregator.py` 37/37.

### Why it's held
Engine-level code (new Rust module, new PyO3 binding) + first binary asset in the repo. The 292 KB `.npz` is shipped Monte-Carlo built (~0.0016 stddev at 50K samples per cell); user explicitly accepted the binary commit. HOLD-for-review per major engine change.

### Merge recommendation: **READY-TO-MERGE**
- All CI green (Golden File Check, Ship Dry Run, Skip-Ban).
- Existing fixed-hole path untouched — additive only, blast radius confined.
- Strong test set (closed-form AA-vs-KK, no clippy regressions).
- Caveat (low impact): the `traverse` trait-genericization is parallel-implemented rather than refactored — noted as clean follow-up. Not a merge blocker.

### What blocks if not merged
- Blocks PR #121's eventual swap from Route A blueprint aggregation to vector engine (per PR #121 body).
- Blocks Phase B/C/D of issue #32 (caching/perf parallelization, GUI viz).
- Blocks any downstream consumer that wants 1326-combo joint preflop Nash (the existing path solves fixed-hole subgames only).

---

## PR #126 — UI: True Nash RvR mode toggle (default flipped)

**URL:** https://github.com/amaster97/poker_solver/pull/126
**Branch:** `feat/ui-true-nash-rvr-toggle-task61-v2` → `main`
**Created:** 2026-05-28T01:51:07Z
**Updated:** 2026-05-28T02:11:52Z

### What it does
Adds a True-Nash-vs-blueprint solver-mode selector to the GUI range-vs-range run panel. **Default flipped to `solver_mode = "true_nash"`** on 2026-05-27 per the post-bench data (Turn ~27× faster than blueprint, Flop blueprint impractical at >27 min CPU, post-PR-114 River True Nash ~213× faster). Blueprint stays opt-in via an inverted-label checkbox ("Use Pluribus blueprint (legacy, faster on tiny river)"). The `true-nash-checkbox` marker is preserved for PR 10b UI snapshot selectors and persona-test selectors.

### Lines / files
- +754 / -22 across 5 files:
  - `tests/test_ui_solver_mode.py` (+443) — new test file
  - `ui/state.py` (+171 / -9) — `Spot.solver_mode` field + `SolveRunner.start` param
  - `ui/views/run_panel.py` (+129 / -13) — inverted checkbox + dispatch
  - `tests/test_ui_pr24a.py` (+7) — 1-line pin to `solver_mode="blueprint"`
  - `ui/app.py` (+4)

### Test coverage
6 new smoke tests for the toggle (added `test_opting_into_blueprint_routes_to_blueprint` for the inverted default). All 7 PR 24a tests still pass with the 1-line `solver_mode="blueprint"` pin added to keep the original blueprint-dispatch smoke meaningful.

### Why it's held
UI-visible change AND a behavior default flip — `Spot.solver_mode` default goes from `"blueprint"` → `"true_nash"`. The `getattr(spot, "solver_mode", "blueprint")` fallbacks in `run_panel.py` are intentionally left as `"blueprint"` (only triggered for pre-field `state.json` files). Per UI + packaging sync rule, this PR must update PR 10b UI + trigger PR 11 `.dmg` rebuild downstream.

### Merge recommendation: **READY-TO-MERGE**
- All CI green (Golden File Check, Ship Dry Run, Skip-Ban).
- The default flip is empirically justified (post-bench data cited in PR body) — not a guess.
- Backwards compatibility for old `state.json` is explicit and called out.
- Followups (not blockers): trigger PR 11 .dmg rebuild post-merge per the UI + packaging sync rule; verify persona-test selectors with the new default.

### What blocks if not merged
- Users opening the GUI keep the old `blueprint` default — known-slow on Flop (>27 min CPU) and known-slow on Turn (~27× slower than True Nash post-PR-114).
- Blocks the persona retest at production scale with the new default (per post-ship persona retest rule).
- Blocks the v1.8.x DMG that wants True Nash as the out-of-box solver.

---

## PR #20 — Cross-platform CI matrix for v1.8 prep

**URL:** https://github.com/amaster97/poker_solver/pull/20
**Branch:** `pr-64-cross-platform-ci-matrix` → `main`
**Created:** 2026-05-26T02:19:32Z
**Updated:** 2026-05-27T17:00:16Z

### What it does
Adds two GitHub Actions workflows. `ci.yml` runs `cargo test --lib --release`, `pytest -m "not slow"`, and a `pytest -k simd` differential parity gate across macOS arm64 (NEON), macOS x86_64 (SSE/AVX), and Linux x86_64 (SSE/AVX). `lint.yml` runs Rust clippy + rustfmt on macos-14 and Python ruff + black on ubuntu-22.04. Linux ARM64 and Windows are scaffolded as commented-out matrix entries, gated on explicit user approval post-v1.8.

### Lines / files
- +128 / -0 across 2 files:
  - `.github/workflows/ci.yml` (+73)
  - `.github/workflows/lint.yml` (+55)

### Test coverage
YAML parses cleanly. CI status on the PR itself:
- macos-14 / aarch64-apple-darwin: **SUCCESS** (22 min run)
- ubuntu-22.04 / x86_64-unknown-linux-gnu: **SUCCESS** (30 min run)
- macos-13 / x86_64-apple-darwin: **QUEUED** (still queued since 2026-05-27T17:00:26Z — runners are scarce)
- Golden File Check, Ship Dry Run, Skip-Ban, Rust lint, Python lint: **SUCCESS**

### Why it's held
Long-running PR — the macos-13 x86_64 leg has been QUEUED for ~24h+ waiting on a GitHub Actions runner. CI infra change so user wants the matrix proven before merging.

### Merge recommendation: **NEEDS-FOLLOWUP**
- Two of three platforms have proven green; the third is queued, not failed.
- Honest call: blocking merge on macos-13 indefinitely is unproductive — GitHub's macos-13 runner queue is a known scarce resource. Either (a) wait for the queued job to finally complete, or (b) merge now and rerun the matrix post-merge on `main` per the "Workflows will execute on merge to main" note in the PR test plan.
- Recommend: merge once macos-13 lands SUCCESS, OR if waiting another 24h doesn't clear it, merge with the post-merge verification commitment.
- Risk if merged with macos-13 unverified: low — the workflow file is YAML, parsing is verified, and the matrix is additive (commented-out entries for Linux ARM64 / Windows are inert).

### What blocks if not merged
- Blocks v1.8 SIMD kernel work — without multi-OS CI, NEON / SSE / AVX parity regressions can land silently.
- Blocks Linux x86_64 verification of new code (currently only macOS arm64 is checked pre-merge anywhere).
- Cascades into the v1.8 release branch hygiene plan.

---

## Top-line recommendation for the user

**Highest-leverage merge today: PR #121** — it is the only PR with `mergeable: MERGEABLE` confirmed, all CI green, strongest test coverage (9 tests including spec-required equivalence + invariants), and unblocks the PioSolver-flavor iterated loop (Phase B+). Python-only and additive, so blast radius is contained.

**Recommended merge order** (if shipping multiple today):
1. **PR #121** — additive Python wrapper, lowest risk, biggest API surface unlock.
2. **PR #122** — additive Rust engine, no impact on existing fixed-hole path, unblocks PR #121's eventual vector-engine swap.
3. **PR #126** — UI default flip; merge after #121 + #122 so the GUI's True-Nash default has both the chained orchestrator and the vector engine available downstream.
4. **PR #20** — merge when macos-13 lands green, or accept the post-merge verification path if the runner queue stays stuck.

All four are independently mergeable — there are no cross-PR file conflicts based on the file lists captured above.
