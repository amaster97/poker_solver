# PR 12 pre-commit checklist

**Date staged:** 2026-05-22
**Author:** orchestrator pre-commit prep agent
**Purpose:** gate list the orchestrator runs immediately before firing
the commit pipeline once the PR 12 audit verdict clears. Every gate
MUST pass (or carry an explicit waiver with rationale) before `git
commit`. PR 12 is the LARGEST single PR in the v1 roadmap AND the
ONLY one shipping an explicitly approximate solution concept. Gate
focus is **theoretical-honesty framing**, **side-pot correctness**,
and **N=2 regression discipline**. Silent overclaim (calling a 3p
result "Nash" / "GTO" / "exploitability") is a correctness bug, not
a cosmetic issue.

## Build + lint gates (Rust side)

- [ ] **G1 — cargo build clean.** `cargo build --release --package cfr_core` returns 0 with no warnings.
  - Run from repo root.
  - Watch for: N-player state tuple-field generalizations in `multiway.rs`, LCFR cutoff parametrization, PyO3 binding for `solve_3p_postflop_rust`.

- [ ] **G2 — cargo test clean.** `cargo test --package cfr_core --all-targets` returns 0; all PR 1-11 Rust tests pass unchanged; new tests for `multiway.rs` (if any unit tests beyond PyO3-driven diff in `test_3p_diff.py`) pass.

- [ ] **G3 — cargo clippy clean.** `cargo clippy --package cfr_core --all-targets -- -D warnings` returns 0.

## Build + lint gates (Python side)

- [ ] **G4 — pytest fast tier clean.** `pytest -m "not slow and not very_slow" --tb=line` returns 0.
  - Expected new-test count (Python): ~30 across `test_3p_core.py` (15) + `test_3p_solve.py` (10) + `test_3p_diff.py` (3) + `test_badge_unsuppressible.py` (assorted).
  - PR 1-11 regression (~220+ pre-existing Python tests): ALL green. [HIGH-PROB must-fix per audit focus 11 — Agent A reconciliation lock.]
  - Skip rationale: convergence + intuition gauntlet + MonkerSolver tests carry `@pytest.mark.slow` and/or `@pytest.mark.skipif`.

- [ ] **G5 — ruff + black clean.** `ruff check poker_solver tests ui` and `black --check poker_solver tests ui` return 0.

- [ ] **G6 — mypy strict clean.** `mypy --strict poker_solver/multiway_solver.py poker_solver/hunl.py poker_solver/action_abstraction.py poker_solver/solver.py poker_solver/cli.py` returns 0.

## Theoretical-honesty gates (LOAD-BEARING — PR 12's deliverable IS the framing)

- [ ] **G7 — Approximate-equilibrium badge UNSUPPRESSIBLE on every output surface.** [HIGH-PROB must-fix per `audit_preprep.md` §1.1] Badge text VERBATIM "≈ approximate equilibrium / multi-player; not Nash" appears at top of: range matrix display panel; library row entry (for 3p spots); CLI stdout result block (3-line text banner with `===` borders). Tooltip text matches spec §6.3 BYTE-identical.
  - Failure mode (a) — suppression path slipped in: `grep poker_solver/cli.py ui/views/*.py poker_solver/multiway_solver.py` for `--suppress-badge|--quiet-approximate|verbose=False`-conditioned skip. Any match → must-fix.
  - Failure mode (b) — surface gap: JSON serialization paths that don't go through UI rendering layer omit the badge field → must-fix.
  - Failure mode (c) — loose substring badge assertion in `test_badge_cannot_be_disabled_via_config` (matches substring instead of exact byte-text) → should-fix.
  - Test: `test_badge_appears_on_cli_stdout`, `test_badge_appears_on_ui_render`, `test_badge_appears_in_json_serialization`, `test_no_suppression_flag_in_argparse`.

- [ ] **G8 — String-literal audit: NO bare "Nash" / "GTO" / "exploitability" in 3p paths.** [HIGH-PROB must-fix per `audit_preprep.md` §1.2] Run the exact grep from spec §9 #4:
  ```sh
  grep -ri 'exploitability\|nash\|GTO' poker_solver/multiway_solver.py crates/cfr_core/src/multiway.rs tests/test_3p_*.py ui/views/ poker_solver/cli.py | grep -v 'best-response\|approximate\|≈\|near-Nash'
  ```
  Expected ZERO output. Any unaccompanied bare match → must-fix.
  - Failure mode (a) — `MultiwaySolveResult.exploitability: tuple[float, float, float]` "to match HU API". Most common Agent B violation per `fanout_ready.md` line 137. Field MUST be named `br_gap`. Must-fix.
  - Failure mode (b) — docstring "Nash convergence" without "no" qualifier. Must-fix.
  - Failure mode (c) — comment "Gibson 2013 establishes CFR convergence for n-player games" OVERCLAIMS (Gibson proves IDSD only; Nash convergence remains open). Spec §3.1 line 90 explicit. Must-fix.

- [ ] **G9 — Per-pair BR labeled "≈ best-response EV upper bound (multi-player; NOT Nash exploitability)".** [audit focus 4] THREE numbers per solve, NOT summed, NOT reported as single number. Field name `br_gap` (NOT `exploitability`). BR walk weights opponents by their JOINT strategy (test: synthetic 3p tree where BR-against-joint ≠ BR-against-either-individual; spec §9 #3).

## Correctness gates (side-pot math — the single hardest correctness item)

- [ ] **G10 — Side-pot math: all 5 TDA fixtures pass.** [HIGH-PROB must-fix per `audit_preprep.md` §1.3] `_compute_side_pots(contributions, folded) -> list[SidePot]` helper in `multiway_solver.py` passes all 5 fixtures per spec §9 #1:
  1. Equal-stack all-in `[50,50,50]` → main pot 150, no side pots.
  2. Unequal `[50,100,150]` → main 150 + side 100 + P2 returns 50.
  3. Folded `[50,30(F),100]` → folded's 30 to main; eligible={0,2}.
  4. Tie split with remainder by position (SB first postflop). [Pre-flagged failure mode: position semantics under-specified; agent picks dealer-button vs SB tiebreak wrong. Most likely bug class per spec §10.3.]
  5. Odd-chip floor/ceiling vs TDA examples.
  - Each side pot won by live player with best hand WHO CONTRIBUTED to that pot. Multi-winner-per-side-pot showdown path tested via 3-way showdown where each player wins a different side pot (audit focus 10).

- [ ] **G11 — 3-way showdown evaluation.** When ≥2 live players remain at river end, each hand evaluated against 5-card board; best hand wins each side pot they contributed to. Reuses `poker_solver.evaluator` per-player; only new logic is multi-winner-per-side-pot path.

## Correctness gates (algorithm + dispatch)

- [ ] **G12 — Linear CFR (LCFR), NOT DCFR_{1.5, 0, 2}.** [audit focus 6] Averaging loop uses LCFR (DCFR_{1,1,1}) for iterations 1..t_cutoff, then plain CFR thereafter. Default `t_cutoff = T // 2` per Pluribus p. 3.
  - Pre-flagged failure mode: agent copy-pastes PR 7 DCFR pattern with α=1.5, β=0, γ=2.0 → must-fix (overclaims Pluribus's empirical validation).
  - Configurable via `dcfr_kwargs={'lcfr_cutoff': T//2}`.

- [ ] **G13 — Negative-regret pruning in 95% of iterations.** [audit focus 7] `random.random() < 0.95` skip on pruned actions; threshold C configurable, default `-300_000` cents per §9 #8.

- [ ] **G14 — N-player turn rotation correct (SB→BB→BTN).** [audit focus 8] Positions LOCKED P0=SB, P1=BB, P2=BTN per spec §4.1. Action turn advances to next non-folded, non-all-in player in post-SB rotation. Street ends when all live players match aggressor's contribution OR are all-in for less.
  - `num_players >= 4` raises `NotImplementedError("PR 12 supports N=2 and N=3 only; 4+ players require a separate solve infrastructure.")` per §4.3 + §6.2 + §9 #5.
  - `num_players == 3 AND starting_street == Street.PREFLOP` → `NotImplementedError` (3p preflop out of v1 per §2).

- [ ] **G15 — Routing in `solver.py` correct.** `config.num_players == 3 AND starting_street >= Street.FLOP` → `solve_3p_postflop`. HU path (`num_players == 2`) UNCHANGED. `num_players >= 4` → clear NotImplementedError.

## Stability + determinism gates

- [ ] **G16 — Stability diagnostic deterministic.** [audit focus 5] `run_stability_diagnostic(config, abstraction, seeds=(0,1,2))` rerun with same seeds yields IDENTICAL numbers. Test `test_stability_diagnostic_is_deterministic` passes.
  - Failure mode (must-fix): `np.random.default_rng()` used without explicit seed threading. The diagnostic itself MUST be deterministic given the same seeds.
  - Soft assertion: `pairwise_max < 0.05` on river-only fixture. Failure → user warned + badge gains "⚠ stability degraded" line (NOT auto-fail).

- [ ] **G17 — Iteratively-strict-dominated actions vanish.** [audit focus 16] Construct 3p toy subgame where one action is strictly dominated; solve; assert that action's frequency converges to 0 within ε. Strongest provable property per Gibson 2013.

## Regression gate (N=2 path UNTOUCHED)

- [ ] **G18 — ALL PR 1-11 tests pass unchanged.** [HIGH-PROB must-fix per audit focus 11] N-player generalization in `hunl.py` is strictly additive on N=2 path. `HUNLConfig.num_players: int = 2` default preserved; `_post_blinds_2p()` is existing path; `_post_blinds_3p()` is new. `folded`/`all_in` fields generalized to `tuple[bool, ...]` BUT NAME PRESERVED (NO rename to `is_folded` — cascading break per audit_preprep §1.5).
  - Pre-flagged failure mode: field rename "for clarity" → must-fix.
  - Test: full `pytest -m "not slow and not very_slow"` returns 0 with PR 3/4/5/6/7/8/9/10/11 all green.

## Differential parity gate

- [ ] **G19 — Python ↔ Rust differential L1 < 1e-6.** [audit focus 13] `tests/test_3p_diff.py` (~3 tests) on tiny 3p river subgame (~1k infosets, ~tens of seconds). Tolerance LOCKED at L1 < 1e-6 after 500 iterations on shared inputs (tighter than HU 5e-3 cluster; small-fixture justified per spec §14).
  - Anti-pattern check: if tolerance silently relaxed (e.g., to 1e-3 or 1e-2), flag must-fix.

## CLI + UI surface gates

- [ ] **G20 — CLI `--num-players` flag works.** Default 2. When 3, `--ranges` accepts three comma-separated range strings (e.g., `"AA,KK / AKs+ / 76s+"`). Documented in `--help`. No `solve-3p` subcommand proliferation.

- [ ] **G21 — UI 3-up matrix display + badge for `num_players >= 3` results.** `ui/views/range_matrix.py` renders three side-by-side mini-matrices for 3p results; `ui/views/run_panel.py` shows `num_players` toggle + 3-range input + per-pair BR gaps + stability diagnostic; `ui/views/library_browser.py` shows "3-handed (approximate)" row badge.

## License + dependency gates

- [ ] **G22 — License hygiene.** [audit focus 15] No code copied from `postflop-solver` or `TexasSolver` (both AGPL) for multi-player logic. Read-only inspiration only. Module docstring in `multiway_solver.py` cites Pluribus from references/papers/ for LCFR + 95%-pruning; Gibson 2013 cited for IDSD theorem (with EXPLICIT "NOT Nash convergence" qualifier; overclaim is must-fix).
  - check_pr.sh license audit clean.

- [ ] **G23 — No MonkerSolver data bundled.** `git ls-files tests/fixtures/monker/` returns EMPTY. Cross-validation test decorated `@pytest.mark.skipif(not Path('tests/fixtures/monker/').exists())`. Format documented; user populates manually.
  - Pre-flagged failure mode: agent commits sample fixture from a forum post (license unknown) → must-fix.

- [ ] **G24 — No new third-party Python deps.** `git diff integration -- pyproject.toml` shows version bump (1.0.x → 1.1.0) only. `[project.dependencies]` unchanged. No new Rust crates in `Cargo.toml`.

## Branch + integration gates

- [ ] **G25 — All branches synced.** `git fetch --all` then verify:
  - `main`: at v1.0 tag (PR 1-11 all landed).
  - `integration`: PR 11 tip SHA stable.
  - `pr-12-three-handed-stretch`: contains all Agent A/B/C diffs; no merge conflicts.
  - User explicitly approved PR 12 launch per `fanout_ready.md` §0.

- [ ] **G26 — No accidental edits to unrelated files.** `git diff integration..pr-12-three-handed-stretch --stat` shows scoped changes, scoped to:
  - 1 new Python source file: `multiway_solver.py`.
  - 4 new Python test files + 1 fixture file: `test_3p_core.py`, `test_3p_solve.py`, `test_3p_diff.py`, `test_badge_unsuppressible.py`, `fixtures/multiway_fixtures.py`.
  - 1 new Rust source: `multiway.rs`.
  - Python modifications: `hunl.py` (N-player generalization), `action_abstraction.py` (`num_players` plumbing), `solver.py` (routing branch), `cli.py` (`--num-players` flag), `__init__.py` (re-exports), `library.py` (badge field reader).
  - Rust modifications: `crates/cfr_core/Cargo.toml` (module decl), `crates/cfr_core/src/lib.rs` (PyO3 binding for `solve_3p_postflop_rust`).
  - UI modifications: `ui/views/range_matrix.py`, `ui/views/run_panel.py`, `ui/views/library_browser.py`.
  - v1.1 bump + docs: `CHANGELOG.md`, `README.md`, `pyproject.toml`, `Cargo.lock`.
  - NO edits to: `dcfr.py`, `evaluator.py` (consumed read-only for showdown), `abstraction/` (PR 4 reused unchanged), PR 5's `hunl_solver.py`, PR 9's `preflop_solver.py` / `blueprint.py` / `subgame_refiner.py`, PR 6's `hunl.rs` / `hunl_tree.rs` / `hunl_eval.rs` / `abstraction.rs` / `hunl_solver.rs`, PR 3.5 `pushfold.py` / `charts/pushfold_v1.json`, PR 10's UI scaffold beyond the three modified views, PR 11's `library.py` orchestration beyond badge-field reader, Kuhn/Leduc test files.

## Audit gate

- [ ] **G27 — PR 12 audit verdict.** `docs/pr12_prep/audit_report.md` carries verdict **READY** or **READY-WITH-PATCHES**, NOT **NOT-READY**.
  - READY → commit.
  - READY-WITH-PATCHES → apply patches, re-run G1-G26 on patched code, commit.
  - NOT-READY → abort; orchestrator escalates with audit's must-fix list.
  - Expected verdict per `audit_preprep.md` §3: READY-WITH-PATCHES (~45%) > NOT-READY (~30%) > clean READY (~15%) > READY-with-stability-must-fix (~10%).
  - Audit focus areas (per `audit_prompt_final.md` 16-area brief): badge unsuppressible (HIGH-PROB); string-literal "Nash"/"GTO"/"exploitability" audit (HIGH-PROB); side-pot 5 TDA fixtures (HIGH-PROB); per-pair BR mislabel; stability determinism; LCFR-not-DCFR_{1.5,0,2}; 95% pruning; N-player turn rotation; routing; 3-way showdown; N=2 regression; MonkerSolver opt-in; differential L1 < 1e-6; CLI flag; license hygiene; IDSD test.

## Biggest gate

**G7 (badge unsuppressible)** + **G8 (string-literal "Nash"/"GTO"/ "exploitability" grep clean)** + **G10 (side-pot 5 TDA fixtures)** + **G18 (PR 1-11 N=2 regression all green)** are the four highest-risk HIGH-PROB must-fix bands.

PR 12's DELIVERABLE IS THE FRAMING. The audit verdict on framing IS the audit verdict on PR 12. Silent "Nash" / "GTO" / "exploitability" in 3p code paths is a CORRECTNESS bug (overclaims solution quality), not a cosmetic issue. G7+G8 must pass cleanly before considering algorithm gates.

G10 is the silent-corruption mode where wrong chip distribution at showdown produces every 3-handed result wrong by an unknown amount (Pio, postflop-solver, Slumbot ALL have public side-pot bug reports). G18 is the silent-corruption mode where the N-player generalization in `hunl.py` perturbs the N=2 path and every PR 1-11 strategy degrades silently.

Secondary biggest gate: **G16 (stability diagnostic deterministic)** — if the diagnostic itself isn't deterministic, the "≈ stability" reassurance is itself unreliable, undermining the framing discipline.

## Commit firing order

Once all gates green:
1. `git status` — confirm clean working tree on `pr-12-three-handed-stretch` with all expected staged changes.
2. `git diff --cached --stat` — final sanity check; verify scoped file delta.
3. `git commit -F docs/pr12_prep/commit_message_draft.md` (or paste via HEREDOC per memory's git-safety protocol).
4. `git status` — verify commit success.
5. Push not yet — wait for user OK on the commit + audit report bundle before `git push origin pr-12-three-handed-stretch`.

## Non-commits in this round

- Do NOT auto-merge `pr-12-three-handed-stretch` into `integration`. PR 12 is post-v1; merge gating requires explicit user OK after the audit report + manual CLI/UI smoke.
- Do NOT close any GitHub PRs yet.
- Do NOT touch PR 4 abstraction artifacts on disk (3p abstraction is a build-recipe, not a committed binary).
- Do NOT modify PR 5's `hunl_solver.py` (consumed read-only for HU postflop).
- Do NOT modify PR 9's preflop solver / blueprint / subgame_refiner (consumed read-only).
- Do NOT modify PR 3.5's `charts/pushfold_v1.json`.
- Do NOT bundle MonkerSolver data anywhere in the repo (license).
- Do NOT add any `--suppress-badge` / `--quiet-approximate` / `verbose=False`-conditioned-skip flag (badge is UNSUPPRESSIBLE per spec §9 #10).
- Do NOT rename `folded` → `is_folded` or any other HUNLState field (cascading break across Agent B/C consumer code).
- Do NOT extend dispatch to `num_players >= 4` (clear NotImplementedError per spec §4.3 + §6.2 + §9 #5).
- Do NOT use DCFR_{1.5, 0, 2} for 3p (LCFR per Pluribus; overclaim must-fix).
- Do NOT claim Gibson 2013 establishes Nash convergence (IDSD ONLY; spec §3.1 line 90).
