# LEG 17 — v1.5.1 ship plan (3-PR PATCH bundle: test rigor + docs honesty)

**Date staged:** 2026-05-23 · **Status:** PRE-STAGED — fires independently of the HELD v1.5.1 engine bundle.
**Previous release:** v1.5.0 (`dc3df6c`) on `origin/main`.
**Filename note:** Doc filename retains the legacy `v1_4_4` slug from the original drafting request; the AUTHORITATIVE shipped version on this bundle is **v1.5.1** (see §0 for the naming-collision resolution).

**Bump:** PATCH (1.5.0 → 1.5.1). Reason: test infrastructure additions + documentation honesty edit. No code paths touched, no Rust source touched, no public API changes. Three branches, all tests-only or docs-only.

> **Branches bundled:**
> 1. **PR 37** `pr-37-equity-test-helper` @ `0f1c263` — equity oracle helper (TESTS; 1 commit; 3 new files; +297)
> 2. **PR 36** `pr-36-profiler-test-rigor` @ `1850709` — 4 closed-form/golden/structure tests for memory profiler (TESTS; 1 commit; 1 file; +525/-9)
> 3. **PR 32** `pr-32-pr-7-docs-honesty` @ `f7e55ca` — replaces a misleading "<10s/spot" docstring comment (DOCS; 1 commit; 1 file; +9/-2)
>
> **Base-branch alignment.** PR 36 and PR 37 are both based directly on `dc3df6c` (v1.5.0). PR 32 is based on `eea3a8b` (v1.4.3). The single file PR 32 touches (`tests/test_river_diff_self_sanity.py`) is byte-identical between v1.4.3 and v1.5.0 (verified: `git diff eea3a8b..dc3df6c -- tests/test_river_diff_self_sanity.py` → empty). Cherry-pick will replay cleanly without rebase-fix; recorded as a low-risk callout in §11.

---

## 0. Version naming — collision resolution with LEG 16

**Conflict:** the prompt asked for a "v1.4.4" tag, but PEP 440 / SemVer ordering would place 1.4.4 below 1.5.0 (already on `origin/main`). LEG 16 (`docs/leg16_v1_5_1_ship_plan.md`) currently reserves the v1.5.1 slot for the bundled PR 33 + PR 34 + PR 35 engine fixes. Per the prompt's own recommendation (Option a) and the principle that monotonically-increasing versions are mandatory once a tag is live:

| Option | Verdict |
|---|---|
| (a) Take v1.5.1 slot for THIS bundle; defer LEG 16's engine bundle to v1.5.2 | **RECOMMENDED.** Standard semver progression; honest framing in CHANGELOG ("docs / test rigor; engine fixes deferred"). Requires LEG 16 plan re-keying to v1.5.2 at fire time. |
| (b) No tag — merge only | Loses the install-by-version handle. Increases ambiguity for downstream users. Rejected. |
| (c) Use non-standard `v1.5.0.post1` / `v1.5.0-r1` | Tooling-fragile under PEP 440 normalization (`1.5.0.post1` is valid PEP 440 but unusual for non-trivial deltas); creates a precedent we don't want. Rejected. |
| (d) Skip ahead to v1.6.0 | Inflates the MINOR bump for purely tests/docs. Bad signal. Rejected. |

**This plan ships v1.5.1 for the docs/test-rigor bundle.** LEG 16 must be re-keyed to v1.5.2 before its fire window. A one-line note is added to LEG 16's preamble during fire-time prep — NOT during plan authoring (this doc is read-only per Hard Rules).

**CHANGELOG framing must be unambiguous:** "v1.5.1: Test rigor + docs honesty. NO engine changes. Per-action divergence diagnosis for the held v1.5.0 acceptance defect is targeted for v1.5.2."

---

## 1. Pre-flight checks

Run from `/Users/ashen/Desktop/poker_solver` (shared tree) unless noted.

### 1a. Shared tree state — verify alignment with origin/main

```bash
cd /Users/ashen/Desktop/poker_solver
git fetch origin
git status --short              # expect: only untracked PLAN.md / docs/ / examples/ / scripts/ etc.
git log --oneline -1            # expect: dc3df6c (v1.5.0) — confirmed clean at stage time
git rev-parse origin/main       # expect: dc3df6c93986029e598e61b333d11ecee3a26bcd
```

**Per LEG 12 / LEG 14 precedent:** operate in a dedicated `ship-v1.5.1` worktree off `origin/main`. The shared tree is currently AT `dc3df6c` (v1.5.0) — no stale-tree gymnastics needed, but worktree-isolation is still preferred per `feedback_no_concurrent_branch_ops`.

### 1b. Branch SHAs (confirm at ship time — match stage-time snapshot)

```bash
# PR 37 — confirmed at stage time
cd /Users/ashen/Desktop/poker_solver_worktrees/equity-helper
git log --oneline dc3df6c..HEAD          # expect: 1 commit, 0f1c263
git diff --stat dc3df6c..HEAD            # expect: tests/_equity_helpers.py (+146), tests/conftest.py (+12), tests/test_equity_helpers.py (+139); total 3 files +297

# PR 36 — confirmed at stage time
cd /Users/ashen/Desktop/poker_solver_worktrees/profiler-test-rigor
git log --oneline dc3df6c..HEAD          # expect: 1 commit, 1850709
git diff --stat dc3df6c..HEAD            # expect: tests/test_memory_profiler.py (+525/-9)

# PR 32 — based on v1.4.3 (eea3a8b), NOT v1.5.0. Confirm the source SHA only.
cd /Users/ashen/Desktop/poker_solver_worktrees/pr-7-docs-honesty
git log --oneline eea3a8b..HEAD          # expect: 1 commit, f7e55ca
git diff --stat eea3a8b..HEAD            # expect: tests/test_river_diff_self_sanity.py (+9/-2)

# Cross-check PR 32 will cherry-pick clean onto v1.5.0:
cd /Users/ashen/Desktop/poker_solver
git diff eea3a8b..dc3df6c -- tests/test_river_diff_self_sanity.py
# expect: EMPTY (file unchanged between v1.4.3 and v1.5.0) → cherry-pick is conflict-free
```

If any SHA drifts: STOP — implementer rebased; re-stage required.

### 1c. Sanitization scan (per `feedback_public_repo_hygiene`)

For each of the 3 branches:

```bash
git diff <base>..HEAD | grep -nE '(/Users/ashen|ashen26@gsb|claude-session|claude_ai_|orchestrator|implementer-agent)' \
  || echo "CLEAN: <branch>"
# Sanity: ensure no .env / credential / large binary files snuck in
git diff --name-only <base>..HEAD | grep -E '\.(env|key|pem|so|dylib)$' \
  && echo "BINARY OR SECRET FILE — REVIEW" || echo "FILE LIST CLEAN"
```

Where `<base>` is `dc3df6c` for PR 36 / PR 37 and `eea3a8b` for PR 32.

**Hard gate.** If any match: STOP and either request implementer rewrite or sanitize locally before cherry-pick. Pay attention to PR 37 specifically — `tests/_equity_helpers.py` is brand-new test infrastructure and warrants a careful manual scan for accidental absolute-path defaults.

### 1d. Smoke tests in each worktree (independent verification)

Each branch must have its smoke tests passing IN ITS OWN worktree before cherry-pick. Run in parallel (3 worktrees are independent file systems). Per LEG 14 follow-up note, prefer `python -m pytest ...` over the pyenv shim to avoid the arm64/x86_64 launch quirk.

```bash
# PR 37
cd /Users/ashen/Desktop/poker_solver_worktrees/equity-helper
python -m pytest -x tests/test_equity_helpers.py -v
# expect: all PR 37 tests green (count from collection; ~6+ per implementer note)

# PR 36
cd /Users/ashen/Desktop/poker_solver_worktrees/profiler-test-rigor
python -m pytest -x tests/test_memory_profiler.py -v
# expect: all profiler tests green (existing + 4 new closed-form / golden / structure cases)

# PR 32 — DOCS-only; no test execution required. Sanity-check the file parses.
cd /Users/ashen/Desktop/poker_solver_worktrees/pr-7-docs-honesty
python -m pytest --collect-only tests/test_river_diff_self_sanity.py 2>&1 | head -5
# expect: collection works (file is still importable post-comment-edit)
```

---

## 2. Ship worktree setup + cherry-pick sequence

Per `feedback_no_concurrent_branch_ops` and per LEG 12 / LEG 14 precedent.

### 2a. Create ship worktree

```bash
cd /Users/ashen/Desktop/poker_solver
git fetch origin
git worktree add /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.1 -b ship-v1.5.1 origin/main
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.1
git log --oneline -3
# expect head: dc3df6c v1.5.0: vector-form CFR + Brown apples-to-apples acceptance
```

### 2b. Symlink the existing `_rust.so` (per LEG 12 / LEG 14 precedent)

All three branches are tests-only or docs-only. No Rust source change. The v1.5.0 `_rust.cpython-313-darwin.so` already in the shared tree is byte-identical to what a fresh `maturin develop --release` from the ship worktree would produce. Symlink it (untracked per `.gitignore`; never enters a commit):

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.1
ln -s /Users/ashen/Desktop/poker_solver/poker_solver/_rust.cpython-313-darwin.so \
      poker_solver/_rust.cpython-313-darwin.so
python -c "from poker_solver import _rust; print('rust binding OK', _rust.__file__)"
# Sanity: must resolve to the shared-tree .so via symlink
```

**Remove the symlink before `git worktree remove`** (so it doesn't leave a dangling link) — see §9.

### 2c. Cherry-pick order — TESTS BEFORE DOCS, infrastructure FIRST

**Recommended sequence (oldest → newest commit on main):**

1. **PR 37 FIRST** (TESTS infrastructure: new `_equity_helpers.py` + `conftest.py` + `test_equity_helpers.py`). Adds the equity oracle scaffolding that future persona tests will depend on. Self-contained 3-file add; zero file overlap with PR 36 or PR 32. Land first so the test harness baseline includes the helpers.
2. **PR 36 SECOND** (TESTS rigor: 4 new closed-form / golden / structure-invariant cases in `tests/test_memory_profiler.py`). Touches only one file, no helper dependency, replays trivially.
3. **PR 32 LAST** (DOCS: comment-edit on `tests/test_river_diff_self_sanity.py`). The lightest, lowest-risk change; landing it last keeps the bisect surface tight if anything earlier breaks.

**Rationale for ordering:**
- **Infrastructure (PR 37) before consumers (PR 36, PR 32):** None of the three actually consume PR 37's helpers in this bundle, but the natural editorial order for future commits is "scaffolding → consumers." Landing PR 37 first sets the precedent.
- **Tests before docs:** Tests have an executable signal (green/red); docs comment-edits cannot fail. Sequence test commits earlier so any cherry-pick conflict surfaces against a fresh test baseline.
- **PR 32 has a different base than PR 36/PR 37.** The base mismatch is benign here (target file unchanged in the v1.4.3 → v1.5.0 window — verified in §1b), but landing PR 32 LAST keeps it as a single-commit, single-file post-script after the bigger-surface PRs are in.

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.1

# Capture SHAs (all confirmed at stage time)
export PR37_SHA=0f1c263                 # confirmed
export PR36_SHA=1850709                 # confirmed
export PR32_SHA=f7e55ca                 # confirmed

# 1. PR 37 — equity test-helper scaffolding
git cherry-pick $PR37_SHA

# 2. PR 36 — profiler test rigor
git cherry-pick $PR36_SHA

# 3. PR 32 — PR 7 docs honesty
git cherry-pick $PR32_SHA

git log --oneline -5
# expect (top-down): PR 32 → PR 36 → PR 37 → dc3df6c (v1.5.0)
```

If any cherry-pick stops with a conflict marker: STOP + report. None expected per §3.

---

## 3. Conflict detection

File-touch matrix (each cell = which branch modifies that file; new files marked NEW):

| File | v1.5.0 base | PR 37 | PR 36 | PR 32 |
|---|---|---|---|---|
| `tests/_equity_helpers.py` | absent | NEW | — | — |
| `tests/conftest.py` | absent | NEW | — | — |
| `tests/test_equity_helpers.py` | absent | NEW | — | — |
| `tests/test_memory_profiler.py` | present | — | YES (+525/-9) | — |
| `tests/test_river_diff_self_sanity.py` | present | — | — | YES (+9/-2; comment-only) |
| Any source file under `poker_solver/` | — | — | — | — |
| Any source file under `crates/cfr_core/` | — | — | — | — |

**Conflict expectation: NONE.** All 3 branches touch disjoint file sets. No `poker_solver/**` and no `crates/cfr_core/**` are touched.

### Base-mismatch flag (PR 32 only)

PR 32 was authored on `eea3a8b` (v1.4.3), not on `dc3df6c` (v1.5.0). Confirmed at §1b that `tests/test_river_diff_self_sanity.py` is byte-identical between those two commits — the cherry-pick is contextually clean. No `git rebase --onto` step needed.

### v1.5.0 base interaction check

v1.5.0 (`dc3df6c`) is a MINOR release with Rust source additions (`crates/cfr_core/src/dcfr_vector.rs`), PyO3 binding (`solve_range_vs_range_rust`), a new `Game::hand_count()` trait method, and per-street memory profiler scaffolding. None of those files are touched by any of the 3 PRs in this bundle. **Base interaction risk: nil.**

---

## 4. Maturin rebuild — NOT NEEDED

All 3 PRs are tests-only or docs-only. Zero `crates/cfr_core/` source changes; zero `pyproject.toml` build-config changes; zero `Cargo.toml` changes. Therefore:

- The v1.5.0 `_rust.cpython-313-darwin.so` from the shared tree is byte-identical to what a fresh `maturin develop --release` would produce.
- Per LEG 12 / LEG 14 precedent, symlink the existing `.so` rather than rebuild.

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.1
ls -la poker_solver/_rust.cpython-313-darwin.so
# expect: symlink → /Users/ashen/Desktop/poker_solver/poker_solver/_rust.cpython-313-darwin.so
```

**Rebuild trigger (informational):** if any future branch in a bundle touches `crates/cfr_core/**` or `pyproject.toml` build-config, run `maturin develop --release`. Not applicable here.

---

## 5. Smoke tests in ship worktree (after all cherry-picks)

Per LEG 14 follow-up: prefer `python -m pytest` over the pyenv `pytest` shim (which can launch x86_64 and fail to load the arm64 `.so`).

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.1

# Headline smoke set per the user prompt:
python -m pytest tests/test_equity_helpers.py \
                 tests/test_memory_profiler.py \
                 tests/test_range.py \
                 tests/test_dcfr_diff.py -v
```

**Expected: ALL GREEN.**
- `tests/test_equity_helpers.py`: ~6+ tests (PR 37 introductions).
- `tests/test_memory_profiler.py`: existing tests + 4 new closed-form / calibration / golden-file / structure-invariant cases (PR 36).
- `tests/test_range.py`: 22 tests (regression baseline from v1.4.3; should be untouched).
- `tests/test_dcfr_diff.py`: regression baseline from v1.4.3 (was passing on the shared tree pre-stage; flagged in LEG 14 §Unexpected as a Rust-binding loader; use `python -m pytest` to bypass the shim).

If any test fails: STOP + report.
- Likely culprit if `test_dcfr_diff.py` fails: pyenv-shim arch quirk (LEG 14 follow-up #1). Diagnose by `python -c "import poker_solver._rust"` working in-process. If interpreter import is green and pytest still fails, escalate.
- Likely culprit if `test_memory_profiler.py` fails: closed-form arithmetic mismatch with current `MemoryProbe` impl. Route to PR 36 implementer.

### Optional broader regression (recommended if time permits)

```bash
python -m pytest -x -m "not slow"
```

Should pass within a few minutes on the v1.5.0 baseline.

---

## 6. Version bump + CHANGELOG (PATCH)

### 6a. Files to bump

| File | Current (on origin/main `dc3df6c`) | New | How |
|---|---|---|---|
| `pyproject.toml` | `version = "1.5.0"` (confirmed) | `version = "1.5.1"` | Edit |
| `poker_solver/__init__.py` | `__version__ = "1.5.0"` (confirmed) | `__version__ = "1.5.1"` | Edit |
| `crates/cfr_core/Cargo.toml` | check at ship time | bump if it tracks crate version | Edit if needed |
| `Cargo.toml` (root) | no `version` key (workspace manifest) | — | Skip |

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.1
grep -n '^version = ' pyproject.toml
# Edit pyproject.toml: "1.5.0" → "1.5.1"

grep -n '__version__' poker_solver/__init__.py
# Edit: "1.5.0" → "1.5.1"

grep -n '^version' crates/cfr_core/Cargo.toml
# If [package] version = "1.5.0": bump to "1.5.1". If absent: skip.
```

### 6b. CHANGELOG.md — prepend `## [1.5.1]` above `## [1.5.0]`

Open `/Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.1/CHANGELOG.md`. The current top entry on origin/main is `## [1.5.0] - 2026-05-23`. Insert a NEW `## [1.5.1]` section between `## [Unreleased]` and `## [1.5.0]` — do NOT touch the v1.5.0 / v1.4.x blocks.

Drop-in markdown (honest framing, public-OK):

```markdown
## [1.5.1] - 2026-05-23

### Added — Equity test-helper scaffolding (PR 37)

- New `tests/_equity_helpers.py` exposing three single-line callables —
  `equity_of(hero, villain, board)`, `equity_vs_range(hero, [combos],
  board)`, and `assert_equity_close(hero, villain, board, expected,
  tol=0.01)` — built on top of `poker_solver.equity.equity()`.
- New `tests/conftest.py` re-exports the helpers so persona /
  acceptance tests can `from conftest import equity_of, ...` without
  reaching into the `_equity_helpers` private module.
- New `tests/test_equity_helpers.py` covers four audit spots end-to-end
  plus edge cases (preflop AA vs random, board-tied trips).
- Motivation: the orchestrator-side equity hand-waves on lopsided
  spots were 2-5x off (audited in
  `docs/poker_spots_audit_2026-05-23.md`). Persona tests now assert
  exact equity values inline rather than spinning their own
  parse-hand / parse-board / equity / pluck-field boilerplate.
- NO source-code change; tests/conftest scaffolding only.

### Added — Memory-profiler test rigor (PR 36)

- 4 new tests in `tests/test_memory_profiler.py` upgrading the
  return-non-empty-without-crashing baseline to genuine external
  oracles:
  1. `closed_form_toy_fixture` — 3-action × 4-infoset bucketed
     synthetic where per-infoset regret + strategy bytes plus
     `utf8(key) + sizeof(InfosetData)` aggregate to a number that
     matches the profiler EXACTLY.
  2. `real_config_closed_form_calibration` — small river-only
     100-iter solve; closed-form derivation from `solver.infosets`
     matches profiler output byte-for-byte; per-infoset solver-array
     bytes asserted < 1 KiB (order-of-magnitude sanity vs. the
     10-14 GB / 256/128/64-bucket claims in PLAN.md §1).
  3. Golden-file check.
  4. Structure-invariant check (key shapes / street partitioning).
- NO source-code change; tests-only.

### Fixed — Honest framing on PR 7 "<10s/spot" claim (PR 32)

- `tests/test_river_diff_self_sanity.py:42` comment originally read
  "River subgames are small ..., so 2000 iters is cheap (<10s/spot
  on a typical dev box)." That was an aspirational target from PR 7
  (v0.5.1), never empirically validated.
- The PR 22 / v1.4.2 river-parity timeout investigation
  (`docs/river_parity_timeout_investigation_2026-05-23.md`) reached
  a TEST-WAS-ALWAYS-SLOW verdict: in practice the canonical parity
  test takes >660s on the Python tier due to the chance-enum-at-root
  architecture (1.6M hole-card combos per iter). The test was
  marked `@pytest.mark.slow` in v1.4.2; a full runtime fix awaits
  vector-form CFR (v1.5.0+).
- Docs-only edit; no assertion or test-behavior change.

### Honest scope

- PATCH bump: test infrastructure + comment edit. NO public API
  change, NO behavior change, NO Rust source change, NO `poker_solver/`
  source change.
- v1.5.0 `_rust.cpython-313-darwin.so` is byte-identical for this
  release (no Rust rebuild). The shipped wheel reuses the v1.5.0
  compiled binding.
- **Engine fixes from the planned v1.5.1 engine bundle (PR 33 /
  PR 34 / PR 35) are DEFERRED to v1.5.2 pending per-action divergence
  diagnosis.** This v1.5.1 release intentionally ships only the
  no-engine-touch test rigor + docs honesty improvements; the
  v1.5.0 acceptance-test status is unchanged.
- Smoke regression: `test_equity_helpers.py`,
  `test_memory_profiler.py`, `test_range.py`, `test_dcfr_diff.py`
  all green (`python -m pytest` to bypass the pyenv arm64/x86_64
  shim quirk per LEG 14 follow-up #1).
```

### 6c. Commit the release bump

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.1
git add CHANGELOG.md pyproject.toml poker_solver/__init__.py
# Conditionally: git add crates/cfr_core/Cargo.toml
git status --short        # sanity: ONLY CHANGELOG + version files staged + cherry-picks already committed
git commit -m "chore(release): v1.5.1 — test rigor + docs honesty (PATCH; no engine changes)"
git log --oneline -6      # expect: 3 cherry-picks + release bump on top of dc3df6c
```

---

## 7. Tag + push sequence

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.1

# Annotated tag
git tag -a v1.5.1 -m "v1.5.1: test rigor + docs honesty (no engine changes; engine fixes deferred to v1.5.2)"

# Push main commits (3 cherry-picks + release bump) — fast-forward expected
git push origin HEAD:main

# Push tag
git push origin v1.5.1

# Verify
git fetch --tags origin
git tag -l 'v1.5.1'
git ls-remote --tags origin | grep v1.5.1
git log --oneline origin/main -6
```

Expected: `origin/main` advances by 4 commits (3 cherry-picks + 1 release bump). Tag `v1.5.1` is annotated and points to the release-bump commit.

---

## 8. GitHub release

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.1

cat > /tmp/v1.5.1_release_notes.md <<'EOF'
## v1.5.1 — Test rigor + docs honesty (PATCH)

**Headline:** A small, no-engine-touch patch release combining new
equity test-helper scaffolding, rigorous memory-profiler oracles,
and an honest framing correction on a long-standing performance
claim. **Engine fixes (per-action divergence diagnosis, Python
delegate, off-by-one fixes) are deferred to v1.5.2.**

### What changed

- **Equity test-helper (PR 37).** New `tests/_equity_helpers.py`
  exposes `equity_of`, `equity_vs_range`, and `assert_equity_close`
  built on top of `poker_solver.equity.equity()`. Re-exported via
  `tests/conftest.py`. Lets persona / acceptance tests assert exact
  equity values inline. NO source-code change.

- **Memory-profiler test rigor (PR 36).** 4 new tests upgrade the
  return-non-empty-without-crashing baseline to genuine external
  oracles: a closed-form 3-action × 4-infoset toy where the profiler
  output matches byte-for-byte; a real-config closed-form calibration
  on a small river solve; a golden-file check; and a structure-invariant
  check on per-street partitioning. NO source-code change.

- **PR 7 docs honesty (PR 32).** The "<10s/spot on a typical dev
  box" comment in `tests/test_river_diff_self_sanity.py:42` was
  aspirational (PR 7 / v0.5.1) and never empirically validated. The
  canonical parity test takes >660s on the Python tier due to
  chance-enum-at-root (1.6M hole-card combos per iter) — see
  `docs/river_parity_timeout_investigation_2026-05-23.md`. Comment
  reframed; no assertion or test-behavior change.

### Honest framing

- PATCH bump. NO `poker_solver/` source change. NO `crates/cfr_core/`
  source change. NO public API change. NO behavior change.
- v1.5.0 `_rust.cpython-313-darwin.so` is reused byte-identically;
  users on v1.5.0 do not need to rebuild Rust for v1.5.1.
- **v1.5.0 acceptance-test status is unchanged.** This release does
  NOT address the per-action divergence observed in the v1.5.0
  Brown apples-to-apples acceptance test. The engine bundle that
  WILL address it (PR 33 Python delegate + PR 34 P0 off-by-one
  fix + PR 35 canonicalization) is deferred to **v1.5.2** pending
  the divergence diagnosis.
- Smoke regression: `test_equity_helpers.py`,
  `test_memory_profiler.py`, `test_range.py`, `test_dcfr_diff.py`
  all green.

EOF

gh release create v1.5.1 \
  --repo amaster97/poker_solver \
  --latest \
  --title "v1.5.1: Test rigor + docs honesty (engine fixes deferred to v1.5.2)" \
  --notes-file /tmp/v1.5.1_release_notes.md

# Verify
gh release view v1.5.1 --repo amaster97/poker_solver | head -12
```

---

## 9. Cleanup

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.1
# Remove the .so symlink BEFORE worktree removal (don't leave dangling symlink)
rm poker_solver/_rust.cpython-313-darwin.so

# Exit the worktree directory before removing
cd /Users/ashen/Desktop/poker_solver

git worktree remove /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.1
git worktree list      # verify ship-v1.5.1 is gone; the 3 source worktrees remain
```

Per LEG 12 / LEG 14 precedent: local `ship-v1.5.1` branch may not delete cleanly with `-d` if shared tree's `main` ref is stale (it isn't here — shared tree is already at `dc3df6c`, but be defensive). Do NOT force-delete with `-D` (per memory rule).

### Mandatory follow-up: LEG 16 re-key

This v1.5.1 release **takes the version slot LEG 16 reserved.** Before LEG 16's fire window, the orchestrator MUST:

1. Re-key `docs/leg16_v1_5_1_ship_plan.md` to `docs/leg16_v1_5_2_ship_plan.md` (or write a successor LEG 18 plan).
2. Update all `v1.5.1` → `v1.5.2` references in LEG 16 (CHANGELOG section, tag name, release notes, version bumps in `pyproject.toml` / `__init__.py`).
3. Verify LEG 16 still targets `dc3df6c..v1.5.1` (this bundle) → v1.5.2 (engine bundle on top of v1.5.1).
4. Audit LEG 16's cherry-pick chain: PR 33/34/35 are based on `dc3df6c`; they will replay onto v1.5.1's HEAD as long as v1.5.1's touched files (`tests/_equity_helpers.py`, `tests/conftest.py`, `tests/test_equity_helpers.py`, `tests/test_memory_profiler.py`, `tests/test_river_diff_self_sanity.py`, `CHANGELOG.md`, `pyproject.toml`, `poker_solver/__init__.py`) are disjoint from PR 33/34/35's touched files. Re-audit at LEG 16 fire time.

### Optional: catch up shared tree

```bash
# Only when no other worktree is mid-write:
cd /Users/ashen/Desktop/poker_solver
git pull --ff-only origin main
```

---

## 10. Estimated ship time

Based on LEG 14 (4 PRs, no Rust rebuild) running ~15 min wall-clock, scaled down for 3 simpler PRs (all tests/docs-only, no in-flight SHA placeholders, no PR 29-style audit-rejection branch to navigate):

| Step | Time |
|---|---|
| Pre-flight (§1) — SHAs + sanitize + per-branch smoke | 2-3 min (parallel across 3 worktrees) |
| Ship worktree setup + symlink (§2a-b) | 1-2 min |
| 3 cherry-picks + validate (§2c) | 2-3 min (one `cherry-pick` per PR; 3 commits total) |
| Smoke tests in ship worktree (§5) | 2-3 min |
| Version bump + CHANGELOG + commit (§6) | 3-5 min |
| Tag + push (§7) | 1-2 min |
| GitHub release (§8) | 1-2 min |
| Cleanup (§9) | <1 min |
| **Total** | **15-20 min wall-clock** |

LEG 14 baseline was ~15 min for 4 PRs (one rejected mid-flight). v1.5.1 is 3 PRs with cleaner SHAs and no audit-rejection drama, but adds the LEG 16 re-key follow-up note (no wall-clock impact at ship time; future work).

---

## 11. Hard rules + risk callouts

### Hard rules (carry-over)

- **Autonomous push authorized** per `feedback_pr10a5_autonomous_commit` (audit-cleared PRs ship end-to-end).
- **DO NOT** use `git add -A` or `git add .` in the ship worktree — stage by explicit path.
- **DO NOT** touch `.gitignore` during ship.
- **DO NOT** modify v1.5.0 or v1.4.x CHANGELOG entries.
- **DO NOT** force-push.
- **DO NOT** delete local `ship-v1.5.1` branch with `-D` if `-d` refuses (per memory rule).
- **DO NOT** force a Rust rebuild — symlink is correct here.
- **Sanitization scan is HARD gate** (per `feedback_public_repo_hygiene`). Block on any PII / paths / session IDs.

### Risk callouts

**A. Version-name collision with LEG 16.** LEG 16 currently reserves v1.5.1 for the engine bundle (PR 33 + PR 34 + PR 35). This plan takes that slot for the docs/test-rigor bundle and pushes the engine bundle to v1.5.2. The re-key follow-up in §9 is MANDATORY before LEG 16's fire window. If the orchestrator chooses NOT to take v1.5.1 for THIS bundle, fall back to option (b) "no tag" or option (c) "post-release tag" per §0 — both worse, but operational.

**B. PR 32 base mismatch (v1.4.3 vs v1.5.0).** PR 32 was authored on `eea3a8b`. Target file `tests/test_river_diff_self_sanity.py` is byte-identical between `eea3a8b` and `dc3df6c` (verified in §1b). Cherry-pick is clean. If the target file changes between stage time and ship time (e.g., a hotfix lands first), STOP — re-verify the no-diff invariant before proceeding.

**C. CHANGELOG insertion zone.** v1.5.0 added `## [1.5.0] - 2026-05-23` at the top of the version sections. The v1.5.1 section MUST be inserted ABOVE it without touching the v1.5.0 block. Use a real editor (no `sed -i`). After edit, `grep -c '^## \[1.5.0\]' CHANGELOG.md` must still return `1`.

**D. pyenv pytest shim arch quirk (LEG 14 follow-up #1).** The shared-tree pytest shim launches x86_64 and fails to load the arm64 `.so`. Always invoke `python -m pytest ...` in this plan's smoke steps, NOT bare `pytest ...`. This is a local-environment quirk, not a v1.5.1 regression.

**E. `.so` symlink hygiene.** Untracked per `.gitignore`. Remove before `git worktree remove` per §9 to avoid a dangling symlink in the worktrees directory.

**F. Public-OK release notes.** Drafted notes contain no PII / `/Users/` paths / session IDs / orchestrator references. Verified against `feedback_public_repo_hygiene`. Release notes explicitly cite the HELD-engine-bundle deferral so external readers understand why a "v1.5.1" landed without engine changes.

**G. No persona retest spawn.** Per memory rules `feedback_ui_packaging_sync`: this bundle is INTERNAL-ONLY (tests + docs). No UI or persona-facing surface changes. No PR 10b UI update needed. No PR 11 `.dmg` rebuild needed.

**H. v1.5.0 acceptance test is NOT affected.** The held v1.5.0 Brown apples-to-apples acceptance test (and the per-action divergence diagnosis blocking v1.5.2's engine bundle) is structurally orthogonal to this v1.5.1 bundle. No new diagnostic data emerges from shipping v1.5.1. The diagnosis effort can proceed in parallel.

**I. Future-coupling note.** PR 37's `tests/conftest.py` MAY conflict with a future PR that also adds a top-level `tests/conftest.py`. None of PR 33 / PR 34 / PR 35 (per LEG 16 file matrix) touches `tests/conftest.py`, so v1.5.2 is safe. Flag to future PRs that wish to extend `conftest.py` to ADD to PR 37's file rather than replace it.

**J. No persona unblock.** This bundle does NOT structurally unblock any persona workflow:
- PR 37 enables future persona tests to assert exact equity; the bundle itself doesn't ship a persona retest.
- PR 36 rigorizes profiler oracles; no persona-visible effect.
- PR 32 is docs honesty; no behavior change.

**Recommendation:** No retest wave triggered by v1.5.1. The W2.2 / W3.4 / persona retests remain on the v1.5.2 engine-fix cadence (LEG 16 fire).

---

## 12. Paste-ready ship executor invocation

The plan is structured so a downstream ship-executor agent can run §1 → §9 sequentially without filling in placeholders. All SHAs (`0f1c263`, `1850709`, `f7e55ca`) are confirmed at stage time. Required inputs at fire time:

1. **Confirm v1.5.1-vs-v1.5.2 routing decision.** The orchestrator must explicitly authorize taking v1.5.1 for this bundle (per §0 / §11A) and updating LEG 16 to v1.5.2 (per §9 mandatory follow-up). Default: PROCEED with v1.5.1.
2. **Confirm origin/main is still at `dc3df6c`.** If any other ship has landed in the interval (unlikely given v1.5.1 hold), re-verify base-interaction matrix in §3.
3. **Confirm `python -m pytest` is the harness command** (not bare `pytest`) per §5 + §11D.

All other values (SHAs; file lists; expected outputs; CHANGELOG draft; release notes) are baked into the plan and verified at stage time.
