# LEG 20 — v1.7.0 Ship Plan (MINOR bundle: PR 43 + PR 39 — True Nash range API + CLI ergonomics)

**Date staged:** 2026-05-23 · **Status:** PRE-STAGED (read-only investigation, plan-only).
**Previous release (assumed at ship time):** v1.6.0 (LEG 18 ships GUI Gate 2 bundle first).
**Filename:** `docs/leg20_v1_7_0_ship_plan.md` (authoritative).

**Bump:** **MINOR (1.6.0 → 1.7.0).** Reason: PR 43 adds a NEW public Python entry point `solve_range_vs_range_nash` (true joint-Nash via PR 23's vector-form CFR) + `RangeVsRangeNashResult` dataclass. PR 39 adds 3 NEW CLI subcommands (`pushfold`, `river`, `parity`). Both are additive non-breaking user-facing functionality. Per Keep-A-Changelog conventions and semver § "added functionality in a backward-compatible manner" → MINOR.

> **Branches bundled:**
> 1. **PR 43** `pr-43-nash-wrapper` (in-flight implementer; SHA TBD at ship time) — aggregator → vector wiring per `docs/pr_proposals/v1_7_0_aggregator_vector_wiring.md`. Python-only (`poker_solver/range_aggregator.py` additive + `poker_solver/__init__.py` exports + new test file `tests/test_range_vs_range_nash.py`). Adds ~150 LOC source + ~250 LOC tests (6 cases).
> 2. **PR 39** `pr-39-cli-ergonomics` @ `7584e06` (1 commit on top of `b5777f2` v1.5.1; rebase onto v1.6.0 + PR 43 expected clean — see §3) — CLI subcommands (`pushfold`, `river`, `parity`) per `docs/pr_39_cherrypick_plan.md`. Pure CLI + USAGE.md §7a rewrite + new test file `tests/test_cli_subcommands.py` (6 tests). Adds ~437 LOC `cli.py` + ~132 LOC USAGE.md rewrite + ~164 LOC tests.
>
> **Ordering rationale (CRITICAL):** PR 43 lands FIRST, PR 39 lands SECOND. Reason:
>
> - PR 43 introduces the new public API (`poker_solver.solve_range_vs_range_nash`).
> - PR 39's USAGE.md §7a rewrite documents the new CLI subcommands; in §6.5 of the PR 39 cherry-pick plan, it explicitly notes that the v1.7.0 aggregator wiring PR is the canonical entry for the "Nash range" path. While PR 39 does NOT import `solve_range_vs_range_nash` (it has its own thin CLI wrappers), running PR 39's smoke tests in a tree that already contains PR 43 confirms there's no import-time interaction.
> - The two PRs touch disjoint file sets at the source level (PR 43 = `range_aggregator.py` + `__init__.py` + new test; PR 39 = `cli.py` + `USAGE.md` + new test). Order matters only for the *ship narrative* and the §7a version-tag adjustment (PR 39's header references "v1.5.2+" which we bump to "v1.7.0+" in §6c).
>
> **Single-range cherry-pick option:** Only feasible if the implementer rebased PR 39 onto PR 43's tip at staging. **At plan-authoring time, PR 39 is on `b5777f2` (v1.5.1) and PR 43 is in flight** — so two sequential cherry-picks is the default path. Re-check at ship time per §1c; switch to single-range only if the merge-base verifies.

---

## 0. Hard rules in force on this plan doc

- This file is READ-ONLY guidance. Ship agent at ship-time executes the steps; this doc does not.
- DO NOT cherry-pick anything, DO NOT push, DO NOT tag during plan authoring.
- PR 43 SHA is a PLACEHOLDER (`<PR_43_SHA>`) throughout this document — implementer is in flight at `/Users/ashen/Desktop/poker_solver_worktrees/v1-7-0-nash-wrapper`. PR 39 SHA `7584e06` is CONFIRMED.
- v1.6.0 base SHA is a PLACEHOLDER (`<V1_6_0_SHA>`) — LEG 18 has not yet shipped at plan-authoring. Ship agent resolves at ship time via `git rev-parse origin/main` after LEG 18 lands.

---

## 1. Pre-flight checks

Run from `/Users/ashen/Desktop/poker_solver` (shared tree) unless noted.

### 1a. Shared tree state — verify alignment with origin/main

```bash
cd /Users/ashen/Desktop/poker_solver
git fetch origin
git status --short              # expect: only untracked PLAN.md / docs/ / examples/ / scripts/ etc.
git log --oneline -1            # expect: v1.6.0 release-bump SHA from LEG 18 ship report
git rev-parse origin/main       # capture <V1_6_0_SHA> — record here at ship time
```

If `origin/main` is NOT at v1.6.0 (e.g., LEG 18 hasn't shipped yet, or v1.6.1 has slipped ahead): STOP. v1.7.0 cannot ship before v1.6.0. Per `feedback_plan_sync`: re-key this plan if the parent slot moved.

Per LEG 18 precedent: operate in a dedicated `ship-v1.7.0` worktree off `origin/main`.

### 1b. Branch SHAs (confirm at ship time — implementer must finish PR 43 first)

```bash
# PR 43 — in flight at plan time; SHA placeholder until implementer reports done
cd /Users/ashen/Desktop/poker_solver_worktrees/v1-7-0-nash-wrapper
git rev-parse HEAD
# expect: <PR_43_SHA> — captured at ship time. Implementer must report "DONE + smoke clean" first.
git log --oneline origin/main..HEAD
# expect: 1-3 commits implementing the spec at docs/pr_proposals/v1_7_0_aggregator_vector_wiring.md
#   — dataclass + function + tests + docs (USAGE.md §5.x + DEVELOPER.md + CHANGELOG insert)
#   — exact commit shape is implementer's call; orchestrator audit verifies before ship

# PR 39 — CONFIRMED at plan time
cd /Users/ashen/Desktop/poker_solver_worktrees/cli-ergonomics
git rev-parse HEAD
# expect: 7584e065... (full SHA TBD; commit subject: "PR 39: CLI ergonomics subcommands (pushfold, river, parity)")
git log --oneline b5777f2..HEAD
# expect 1 commit:
#   7584e06  PR 39: CLI ergonomics subcommands (pushfold, river, parity)
```

If PR 43 has not finished implementer + audit by ship time: HOLD. v1.7.0 cannot ship without PR 43 (PR 39 alone would be a PATCH per `docs/pr_39_cherrypick_plan.md` §3 Option B, and that was REJECTED on semver-monotonic grounds with v1.6.0 in flight). **Blocker condition: PR 43 implementer not done → defer LEG 20 entirely.**

If PR 39 SHA drifts (implementer rebased): STOP — re-stage required.

### 1c. Stacking check (optional optimization — single-range cherry-pick)

```bash
# Did the implementer rebase PR 39 onto PR 43's tip during the v1.7.0 bundle prep?
cd /Users/ashen/Desktop/poker_solver_worktrees/cli-ergonomics
git merge-base pr-43-nash-wrapper pr-39-cli-ergonomics
# Case A: returns <PR_43_SHA> → PR 39 stacked on PR 43; single-range cherry-pick possible (§2c-alt).
# Case B: returns b5777f2 (v1.5.1) or <V1_6_0_SHA> (v1.6.0) → branches independent; use two-step (§2c default).
```

**Default expectation:** Case B (two-step). PR 39 was authored independently @ `b5777f2` and there's no evidence the implementer has rebased it onto the in-flight PR 43 branch. The single-range path is an optimization to investigate at ship time, not a precondition.

### 1d. Sanitization scan (per `feedback_public_repo_hygiene`)

```bash
# PR 43 sanitization scan
cd /Users/ashen/Desktop/poker_solver_worktrees/v1-7-0-nash-wrapper
git diff origin/main..HEAD | grep -nE '(/Users/ashen|ashen26@gsb|claude-session|claude_ai_|implementer-agent)' \
  | head -20
# expect: matches only inside docs/pr_proposals/v1_5_pr_43_implementer_notes.md
#         (if implementer follows PR 24a/24b precedent); zero matches elsewhere.

# PR 39 sanitization scan
cd /Users/ashen/Desktop/poker_solver_worktrees/cli-ergonomics
git diff b5777f2..HEAD | grep -nE '(/Users/ashen|ashen26@gsb|claude-session|claude_ai_|implementer-agent)' \
  | head -20
# expect: clean (no implementer notes file in PR 39's commit; all changes are USAGE.md/cli.py/test)

# Sanity: ensure no .env / credential / large binary files
for wt in v1-7-0-nash-wrapper cli-ergonomics; do
  cd /Users/ashen/Desktop/poker_solver_worktrees/$wt
  base_sha=$(git merge-base HEAD origin/main)
  git diff --name-only $base_sha..HEAD | grep -E '\.(env|key|pem|so|dylib)$' \
    && echo "  $wt: BINARY OR SECRET FILE — REVIEW" || echo "  $wt: FILE LIST CLEAN"
done
```

**Hygiene posture:** PR 39 touches only `USAGE.md`, `poker_solver/cli.py`, `tests/test_cli_subcommands.py` — public-OK by precedent. PR 43 is expected to touch `poker_solver/range_aggregator.py`, `poker_solver/__init__.py`, `tests/test_range_vs_range_nash.py`, `USAGE.md`, `DEVELOPER.md`, `CHANGELOG.md`, optional `docs/pr_proposals/v1_5_pr_43_implementer_notes.md`. All public-OK.

**Hard gate:** if the grep surfaces anything OUTSIDE expected implementer-notes files — STOP and request implementer rewrite or sanitize locally before cherry-pick.

### 1e. Smoke tests in each worktree (independent verification)

Run in parallel (worktrees are independent file systems). Per LEG 14 follow-up: prefer `python -m pytest` over the pyenv shim to avoid arm64/x86_64 launch quirks.

```bash
# PR 43 worktree — expected ~6 new tests in tests/test_range_vs_range_nash.py
cd /Users/ashen/Desktop/poker_solver_worktrees/v1-7-0-nash-wrapper
python -m pytest -x \
  tests/test_range_vs_range_nash.py \
  tests/test_range_vs_range_aggregator.py \
  tests/test_v1_5_brown_apples_to_apples.py -v
# expect:
#   tests/test_range_vs_range_nash.py: 6 passed (or 7 with the optional exploitability-bound case)
#   tests/test_range_vs_range_aggregator.py: 20 passed (unchanged — aggregator semantics preserved)
#   tests/test_v1_5_brown_apples_to_apples.py: unchanged from v1.5.0 baseline

# PR 39 worktree — 6 new + 18 pre-existing = 24 expected
cd /Users/ashen/Desktop/poker_solver_worktrees/cli-ergonomics
python -m pytest -x \
  tests/test_cli_subcommands.py \
  tests/test_pushfold.py \
  tests/test_library_cli.py -v
# expect: 24 passed, 1 skipped (parity happy path skips when Brown binary unbuilt — by design)
```

If any test fails in its source worktree: STOP — implementer must fix before cherry-pick.

### 1f. PR 43 audit must be cleared

Per `feedback_pr10a5_autonomous_commit`: autonomous end-to-end ship requires **audit-cleared** PRs. Before ship time, verify:

- PR 43 has a verification audit report at `docs/pr_43_verification_audit.md` (or similar).
- Audit-clear status: no Type C-CRITICAL findings; per-finding routing matches `docs/pr13_prep/rectification_framework.md`.
- W3.5 monotone polarization test in `tests/test_range_vs_range_nash.py` PASSES on PR 43 branch (this is the empirical Nash demo — the heart of the v1.7.0 framing).

If audit not clear: HOLD until audit completes + remediation applied.

PR 39 was audited at the time of `docs/pr_39_cherrypick_plan.md` staging (verified 24/24 tests pass — see §1 of that doc). No re-audit needed unless the branch SHA drifts.

---

## 2. Ship worktree setup + cherry-pick sequence

Per `feedback_no_concurrent_branch_ops` and per LEG 18 precedent.

### 2a. Create ship worktree

```bash
cd /Users/ashen/Desktop/poker_solver
git fetch origin
git worktree add /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.7.0 -b ship-v1.7.0 origin/main
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.7.0
git log --oneline -3
# expect head: <V1_6_0_SHA> v1.6.0 release-bump from LEG 18
```

### 2b. Symlink the existing `_rust.so` (per LEG 12 / 14 / 17 / 18 precedent)

**Maturin rebuild: NOT NEEDED.** Both PR 43 and PR 39 are Python-only changes:

- Zero `crates/cfr_core/` source changes (PR 43 wraps the existing `_rust.solve_range_vs_range_rust` binding from PR 23 v1.5.0; PR 39 wraps existing Python APIs).
- Zero `pyproject.toml` build-config changes.
- Zero `Cargo.toml` changes.

The v1.6.0 `_rust.cpython-313-darwin.so` (byte-identical to v1.5.1's, which was byte-identical to v1.5.0's per LEG 17 §6 / LEG 18 §4) is reused. Symlink it (untracked per `.gitignore`; never enters a commit):

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.7.0
ln -s /Users/ashen/Desktop/poker_solver/poker_solver/_rust.cpython-313-darwin.so \
      poker_solver/_rust.cpython-313-darwin.so
python -c "from poker_solver import _rust; print('rust binding OK', _rust.__file__)"
# Sanity: must resolve to the shared-tree .so via symlink
```

**Remove the symlink before `git worktree remove`** (so it doesn't leave a dangling link) — see §9.

### 2c. Cherry-pick: two-step (default) — PR 43 first, PR 39 second

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.7.0

# Step 1: PR 43 (aggregator → vector wiring; Python additive)
git cherry-pick <PR_43_SHA>
# If implementer authored multiple commits (e.g., separate commits for dataclass / function / tests / docs):
#   git cherry-pick origin/main..pr-43-nash-wrapper
#   (single-range from origin/main tip to PR 43 branch tip — replays all in order)

# Step 2: PR 39 (CLI subcommands; closes USAGE.md §7a known-gaps section)
git cherry-pick 7584e06

git log --oneline -5
# expect (top-down):
#   <new>  PR 39: CLI ergonomics subcommands (pushfold, river, parity)
#   <new>  PR 43: solve_range_vs_range_nash (vector-form Nash entry) [+ any sub-commits]
#   <V1_6_0_SHA>  v1.6.0: GUI Gate 2 (UI completeness; PR 24a + PR 24b)
```

**If PR 39 cherry-pick stops with a USAGE.md conflict** (NOT EXPECTED per §3 conflict matrix, but possible if PR 43 also rewrote §7 content):

1. Inspect `git diff` — locate the conflicting hunks.
2. Resolution rule from `docs/pr_39_cherrypick_plan.md` §6.4: PR 39's §7a rewrite is canonical; bump the in-line version tag from "v1.5.2+" → "v1.7.0+" inline; preserve any §5.x text PR 43 added.
3. `git add USAGE.md && git cherry-pick --continue`.

### 2c-alt. Cherry-pick: single-range (only if §1c Case A — PR 39 stacked on PR 43)

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.7.0
git cherry-pick origin/main..pr-39-cli-ergonomics
# Replays PR 43's commits + PR 39's commit in chronological order
```

Use this only if `git merge-base pr-43-nash-wrapper pr-39-cli-ergonomics` returned `<PR_43_SHA>` (Case A in §1c). Otherwise stay on the two-step path — same result, less risk of misordering.

### 2d. Post-cherry-pick verify

```bash
git status --short        # expect: only the symlinked .so (untracked, ignored)
git log --oneline -5      # see expected output above
```

If anything looks off (e.g., extra commits, missing commits, conflict markers in tracked files): STOP and report.

---

## 3. Conflict detection

File-touch matrix (each cell = which branch modifies that file; new files marked NEW). All file lists verified at plan time:

### PR 43 expected file-touch (per spec `docs/pr_proposals/v1_7_0_aggregator_vector_wiring.md` §4)

```
poker_solver/range_aggregator.py    | ~150 lines added (RangeVsRangeNashResult + solve_range_vs_range_nash)
poker_solver/__init__.py            | ~4 lines added (exports)
tests/test_range_vs_range_nash.py   | NEW (~250 lines, 6 test cases)
USAGE.md                            | NEW §5.x "Two range-vs-range paths" subsection (additive)
DEVELOPER.md                        | new §"Range-vs-Range internals" subsection (additive)
CHANGELOG.md                        | new [1.7.0] section (handled in ship's release-bump commit, not in PR 43)
docs/aggregator_vs_true_nash_explainer.md | minor §"Going forward" update (additive)
docs/pr_proposals/v1_5_pr_43_implementer_notes.md | NEW (implementer notes; optional)
```

### PR 39 file-touch (per `docs/pr_39_cherrypick_plan.md` §1 + §6)

```
USAGE.md                            | §7a rewrite (lines 539–585 on v1.5.1 base; supersedes PR 30 gap section)
poker_solver/cli.py                 | ~437 lines added (pushfold, river, parity subcommands)
tests/test_cli_subcommands.py       | NEW (~164 lines, 6 tests + 1 skip)
```

### Conflict matrix — PR 43 vs PR 39

| File | v1.6.0 base | PR 43 | PR 39 | Notes |
|---|---|---|---|---|
| `poker_solver/range_aggregator.py` | present | YES (additive append) | — | PR 43 only |
| `poker_solver/__init__.py` | present | YES (export adds) | — | PR 43 only |
| `poker_solver/cli.py` | present | — | YES (additive new subcommands) | PR 39 only |
| `USAGE.md` | present | YES (new §5.x) | YES (rewrite §7a) | **Potential overlap** — see §3.1 below |
| `DEVELOPER.md` | present | YES (new section) | — | PR 43 only |
| `CHANGELOG.md` | present | — | — | Ship commit edits both (§6b) |
| `docs/aggregator_vs_true_nash_explainer.md` | present | YES (one-line "Going forward" update) | — | PR 43 only |
| `tests/test_range_vs_range_nash.py` | absent | NEW | — | PR 43 only |
| `tests/test_cli_subcommands.py` | absent | — | NEW | PR 39 only |
| `tests/test_range_vs_range_aggregator.py` | present | — | — | Untouched by both |
| `tests/test_pushfold.py` | present | — | — | Untouched by both |
| `tests/test_library_cli.py` | present | — | — | Untouched by both |
| `docs/pr_proposals/v1_5_pr_43_implementer_notes.md` | absent | NEW | — | PR 43 only |

### 3.1 USAGE.md overlap risk (only nonzero shared-file risk)

Both PRs touch USAGE.md:

- **PR 43** adds a new §5.x "Two range-vs-range paths" subsection (PER SPEC §4 — additive, slots between existing §5 examples and §6/§7).
- **PR 39** rewrites §7a in place (replaces PR 30's "Known CLI gaps" with "Ergonomic subcommands").

**Why these don't conflict in practice:**

1. Section-level disjoint: §5.x vs §7a are separated by §6 content (~50+ lines on origin/main).
2. PR 43 lands FIRST per §2c order. When PR 39 is cherry-picked, its diff context is `description, so the same configuration always resolves to the same row.` (the immediate-pre-§7a context line per `docs/pr_39_cherrypick_plan.md` §6.3). PR 43's §5.x additions don't disturb this context line.
3. Even if PR 43's §5.x text shifts §7a's line numbers downward, `git cherry-pick` is content-based (uses diff context, not absolute line numbers).

**If a conflict surfaces (low probability):** resolve per §2c step "If PR 39 cherry-pick stops with a USAGE.md conflict" — PR 39's §7a content is canonical for the v1.7.0 ship.

### 3.2 Cross-base interaction — vs v1.6.0 (LEG 18) files

v1.6.0 (PR 24a + PR 24b) touched (per LEG 18 §3):

```
ui/app.py, ui/state.py, ui/views/*.py        (8 files)
poker_solver/charts/*.json + README.md       (5 chart files + 1 readme)
docs/pr_proposals/v1_5_pr_24a_implementer_notes.md
docs/pr_proposals/v1_5_pr_24b_implementer_notes.md
tests/test_ui_pr24a.py
tests/test_ui_pr24b.py
```

**NONE** of these appear in the PR 43 or PR 39 touched-file lists above. **Cross-base conflict surface: nil.**

### 3.3 Intra-bundle interaction — PR 43 + PR 39 import paths

PR 43 adds `solve_range_vs_range_nash` to `poker_solver/__init__.py.__all__`. PR 39 does NOT import this symbol — its 3 new CLI subcommands wrap the *existing* APIs (`solve()`, `solve_range_vs_range`, push/fold helpers, batch parity). Per `docs/pr_39_cherrypick_plan.md` §2.3: "PR 39 only imports modules already imported by `poker_solver/cli.py` upstream." So PR 43's exports neither help nor hinder PR 39's tests.

**Conflict expectation: NONE.** All cross-base file edits are disjoint from v1.6.0's added/changed files; intra-bundle file overlap (USAGE.md) is on disjoint sections with no shared diff context.

---

## 4. Maturin rebuild — NOT NEEDED

Both PRs are Python-only:

- **PR 43**: wraps the existing `_rust.solve_range_vs_range_rust` binding (PR 23, shipped v1.5.0). No Rust source changes.
- **PR 39**: pure CLI / Python additions. No Rust references.

Therefore:

- The v1.6.0 `_rust.cpython-313-darwin.so` (= byte-identical to v1.5.0's per LEG 17/18) is byte-identical to what a fresh `maturin develop --release` from the ship worktree would produce.
- Per LEG 12 / 14 / 17 / 18 precedent, symlink the existing `.so` rather than rebuild.

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.7.0
ls -la poker_solver/_rust.cpython-313-darwin.so
# expect: symlink → /Users/ashen/Desktop/poker_solver/poker_solver/_rust.cpython-313-darwin.so
```

**Rebuild trigger (informational):** if any future branch in a bundle touches `crates/cfr_core/**` or `pyproject.toml` build-config, run `maturin develop --release`. Not applicable here. The engine bundle (PR 33/34/35/40) deferred to v1.6.1 / v1.6.2 will rebuild then.

---

## 5. Smoke tests in ship worktree (CRITICAL)

Per LEG 14 follow-up: prefer `python -m pytest` over the pyenv `pytest` shim.

### 5a. Headline smoke set (mandatory)

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.7.0

python -m pytest \
  tests/test_range_vs_range_nash.py \
  tests/test_cli_subcommands.py \
  tests/test_range_vs_range_aggregator.py \
  tests/test_pushfold.py \
  tests/test_library_cli.py -v
```

**Expected: GREEN as follows.**

| Suite | Count | New / pre-existing | Notes |
|---|---|---|---|
| `tests/test_range_vs_range_nash.py` | 6 passed (or 7 if exploitability-bound case included) | NEW (PR 43) | W3.5 monotone, W1.2 deep-stack, Brown parity, schema, errors. **Tier 1 W3.5 polarization test MUST PASS — this is the empirical Nash demo + headline v1.7.0 claim.** |
| `tests/test_cli_subcommands.py` | 6 passed, 1 skipped | NEW (PR 39) | parity skip = Brown binary not built (by design) |
| `tests/test_range_vs_range_aggregator.py` | 20 passed | pre-existing | aggregator semantics UNCHANGED (PR 43 is additive only) |
| `tests/test_pushfold.py` | 13 passed | pre-existing | PR 39's CLI wrappers don't change push/fold engine path |
| `tests/test_library_cli.py` | 5 passed | pre-existing | unchanged |
| **TOTAL** | **50 passed, 1 skipped** | 12 NEW (6 PR 43 + 6 PR 39) + 38 baseline | |

### 5b. Critical assertions (W3.5 + W1.2 demos)

The Tier 1 + Tier 2 cases in `tests/test_range_vs_range_nash.py` are the load-bearing tests for v1.7.0's narrative:

1. **`test_w3_5_monotone_aa_pure_check`**: AA pure-checks (≥99%) on monotone board through `solve_range_vs_range_nash`; aggregator on same input gives bet ≈ 68%. **Assert divergence**. Codifies the explainer doc's central claim.
2. **`test_w1_2_jj_defends_pot_bet`**: JJ defends ≥99% via Nash; aggregator falsely reports 7.7% fold. **Assert divergence ≥ 5 percentage points**.

If EITHER fails: STOP. v1.7.0 cannot ship a "True Nash range API" headline if the headline demo doesn't pass.

### 5c. Cross-check: aggregator output ≠ vector output (regression guard)

Per the prompt's hard requirement: cross-check that on at least one shared input (e.g., the W3.5 monotone board) the two functions produce DIFFERENT range-aggregate frequencies. This is built into the Tier 1 + Tier 2 cases as their negative-control assertion. The test fails LOUDLY if the divergence ever collapses (e.g., implementer accidentally aliased `solve_range_vs_range_nash` to the aggregator).

### 5d. Regression sweep (recommended for confidence)

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.7.0
python -m pytest tests/ -v -k 'not slow and not parity_noambrown' --timeout=90
```

**Expected: all non-slow non-Brown-parity tests pass** vs. v1.6.0 baseline + 12 new from this bundle. No regressions.

If anything that was green on v1.6.0 fails here: STOP and bisect. Most likely culprit would be an import-time interaction (e.g., PR 43's new export collides with an existing name) — fix in implementer worktree, re-stage, re-ship.

---

## 6. Version bump + CHANGELOG (MINOR)

### 6a. Files to bump

| File | Current (assumed on origin/main `<V1_6_0_SHA>`) | New | How |
|---|---|---|---|
| `pyproject.toml` | `version = "1.6.0"` | `version = "1.7.0"` | Edit |
| `poker_solver/__init__.py` | `__version__ = "1.6.0"` | `__version__ = "1.7.0"` | Edit |
| `crates/cfr_core/Cargo.toml` | `version = "0.5.0"` (likely unchanged from v1.5.0 / v1.6.0; crate version tracks independently per workspace convention) | bump to `0.7.0` only if v1.6.0 bumped it to `0.6.0`; otherwise leave alone | Edit conditionally |
| `Cargo.toml` (root) | no `version` key (workspace manifest) | — | Skip |

**Verification at plan time (shared tree, possibly stale):**
```
$ grep -n '^version = ' /Users/ashen/Desktop/poker_solver/pyproject.toml
7:version = "1.5.0"      # NOTE: shared tree lags origin/main (which is at v1.5.1 → v1.6.0 once LEG 18 ships)
$ grep -n '__version__' /Users/ashen/Desktop/poker_solver/poker_solver/__init__.py
192:__version__ = "1.5.0" # same caveat
$ grep -n '^version' /Users/ashen/Desktop/poker_solver/crates/cfr_core/Cargo.toml
3:version = "0.5.0"       # may stay at 0.5.0 through v1.7.0 if v1.6.0 didn't bump it
```

The shared tree at plan-authoring is NOT pulled up to v1.5.1 (or v1.6.0). The ship worktree is created off `origin/main` directly, so the version string seen there is the canonical v1.6.0 — bump it to v1.7.0.

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.7.0
grep -n '^version = ' pyproject.toml
# Expected output at ship time: 7:version = "1.6.0"
# Edit pyproject.toml: "1.6.0" → "1.7.0"

grep -n '__version__' poker_solver/__init__.py
# Expected output: 192:__version__ = "1.6.0"
# Edit: "1.6.0" → "1.7.0"

grep -n '^version' crates/cfr_core/Cargo.toml
# If still "0.5.0": leave unchanged (crate version tracks independently)
# If LEG 18 bumped to "0.6.0": bump to "0.7.0" (MINOR alignment with parent)
```

### 6b. CHANGELOG.md — prepend `## [1.7.0]` above `## [1.6.0]`

Open `/Users/ashen/Desktop/poker_solver_worktrees/ship-v1.7.0/CHANGELOG.md`. The current top entry on origin/main (post-LEG 18) is `## [1.6.0] - 2026-05-23`. Insert a NEW `## [1.7.0]` section between `## [Unreleased]` and `## [1.6.0]` — do NOT touch the v1.6.0 / v1.5.1 / v1.5.0 / v1.4.x blocks.

Drop-in markdown (honest framing per prompt):

```markdown
## [1.7.0] - 2026-05-23

### Added — public API expansion

- **`poker_solver.solve_range_vs_range_nash`** — joint range Nash via
  PR 23's vector-form CFR. Distinct from
  `poker_solver.solve_range_vs_range` (which is the per-combo blueprint
  aggregator). The two functions answer **different mathematical
  questions** — see `docs/aggregator_vs_true_nash_explainer.md` for the
  long-form distinction. Tests in `tests/test_range_vs_range_nash.py`
  codify the W3.5 (AA monotone-board polarization) + W1.2 (JJ deep-stack
  defense) divergence between the two paths.
- **`RangeVsRangeNashResult` dataclass** — exposes
  `per_history_strategy` (per-(infoset, hand) Nash table),
  `per_class_strategy` (root-decision projection for 13×13 UI display),
  `range_aggregate` (range-aggregated frequencies), `exploitability`,
  `iterations`, `wall_clock_s`, `decision_node_count`,
  `hand_count_per_player`, `memory_profile`, `backend="rust_vector"`.
- **3 new CLI subcommands** (PR 39) — close the known CLI ergonomics
  gaps from PR 30's USAGE.md §7a:
  - `poker-solver pushfold` — thin wrapper for push/fold scenarios
    (was a Python one-liner workaround).
  - `poker-solver river` — `--hero <hand> --villain-range <range>`
    river-spot ergonomics (was a Python one-liner workaround).
  - `poker-solver parity` — Brown apples-to-apples acceptance test
    runner, gated on the Brown binary being built (skips gracefully
    if absent).
- **USAGE.md** updates:
  - New §5.x "Two range-vs-range paths" subsection contrasting the
    aggregator and the new Nash entry; links the explainer doc.
  - §7a rewritten from "Known CLI gaps (v1.4.x)" → "Ergonomic
    subcommands (v1.7.0+)" — previously documented gaps are now
    resolved subcommands. The batch-solve CSV quoting bullet from
    PR 30's §7a is preserved under a "Still missing from the CLI"
    subsection.
- **DEVELOPER.md** new §"Range-vs-Range internals" — maps the two
  Python entries to their underlying Rust bindings.
- **12 new tests** total — 6 in `tests/test_range_vs_range_nash.py`
  (PR 43: W3.5, W1.2, Brown parity through the new entry, schema,
  preflop-error, hero_player-error) + 6 in
  `tests/test_cli_subcommands.py` (PR 39: pushfold happy path, river
  happy path, JSON output, error handling, missing-flags, parity skip).

### Honest scope

- MINOR bump: NEW public Python entry point + 3 new CLI subcommands.
  Both purely additive — `solve_range_vs_range` (aggregator) and every
  pre-v1.7.0 CLI surface remain backward-compatible.
- v1.6.0 `_rust.cpython-313-darwin.so` is reused byte-identically;
  users on v1.6.0 do NOT need to rebuild Rust for v1.7.0.
- **Aggregator vs Nash distinction (CRITICAL):** the two functions
  solve **structurally different mathematical objects** — the
  aggregator returns a histogram of per-combo perfect-info best
  responses; `solve_range_vs_range_nash` returns the joint
  imperfect-info Nash. On polarized spots (W3.5 monotone river, W1.2
  bluff-catching) the two can diverge by tens of percentage points.
  Neither is "wrong" — they answer different questions. See
  `docs/aggregator_vs_true_nash_explainer.md`.
- Engine bundle (PR 33 + PR 34 + PR 35 + PR 40) for Brown
  apples-to-apples acceptance remains **deferred to v1.6.1 or v1.6.2**
  pending bisection. v1.7.0 does NOT address per-action divergence on
  the v1.5.0 Brown acceptance test directly; instead it exposes the
  vector-form path through the user-facing range API so the test can
  be run end-to-end through `solve_range_vs_range_nash` (Tier 3
  `test_brown_parity_via_nash_entry` validates this).
- Smoke: 50/51 green (1 skip is `parity` happy-path; Brown binary
  unbuilt by design). Non-slow non-parity-Brown sweep green vs v1.6.0
  baseline.
```

### 6c. PR 39 §7a version-tag adjustment

Per `docs/pr_39_cherrypick_plan.md` §6.4: PR 39's §7a header reads `## 7a. Ergonomic subcommands (v1.5.2+)`. Since v1.5.2 was never released (v1.5.1 jumped to v1.6.0 GUI), the header MUST be edited to `## 7a. Ergonomic subcommands (v1.7.0+)`.

This is a one-line cosmetic edit. Fold it into the same v1.7.0 ship commit (NOT a separate commit; NOT `--amend` of the PR 39 cherry-pick) — bundle with the §7b update PR 43 makes (per the spec), keep the diff narrative coherent.

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.7.0
grep -n '^## 7a\. ' USAGE.md
# expect: line ~537 (post-PR-39): "## 7a. Ergonomic subcommands (v1.5.2+)"
# Edit: replace "(v1.5.2+)" with "(v1.7.0+)"
```

### 6d. Commit the release bump

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.7.0
git add CHANGELOG.md pyproject.toml poker_solver/__init__.py USAGE.md
# Conditionally: git add crates/cfr_core/Cargo.toml
git status --short        # sanity: ONLY CHANGELOG + version files + USAGE.md staged
                          # PLUS the cherry-picked commits already in history
git commit -m "chore(release): v1.7.0 — True Nash range API + CLI ergonomics (PR 43 + PR 39)"
git log --oneline -5      # expect: 2 cherry-picks (or N depending on PR 43 commit count) + release bump
```

---

## 7. Tag + push sequence

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.7.0

# Annotated tag
git tag -a v1.7.0 -m "v1.7.0: True Nash range API + CLI ergonomics"

# Push main commits (cherry-picks + release bump) — fast-forward expected
git push origin HEAD:main

# Push tag
git push origin v1.7.0

# Verify
git fetch --tags origin
git tag -l 'v1.7.0'
git ls-remote --tags origin | grep v1.7.0
git log --oneline origin/main -5
```

Expected: `origin/main` advances by (N+1) commits where N = number of commits in PR 43 (likely 1-3) + 1 (PR 39) + 1 (release bump). Tag `v1.7.0` is annotated and points to the release-bump commit.

---

## 8. GitHub release

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.7.0

cat > /tmp/v1.7.0_release_notes.md <<'EOF'
## v1.7.0 — True Nash range API + CLI ergonomics (MINOR)

**Headline:** A MINOR release adding the user-facing **true Nash**
range-vs-range entry point (closing the architectural gap that PR 23
in v1.5.0 only exposed at the Rust binding level) plus three new
ergonomic CLI subcommands closing the gaps documented in v1.4.3's
USAGE.md §7a. Both are purely additive — every pre-v1.7.0 API and
CLI surface remains backward-compatible.

### What's new

- **`poker_solver.solve_range_vs_range_nash(...)`** — joint range Nash
  via PR 23's vector-form CFR. Returns a `RangeVsRangeNashResult` with
  `per_history_strategy` (full Nash table), `per_class_strategy`
  (13×13 UI projection), `range_aggregate`, `exploitability`, and
  memory profile.

- **`solve_range_vs_range` (existing aggregator) UNCHANGED.** Use it
  when you want the fast Pluribus-style blueprint approximation. Use
  the new `_nash` entry when you want true joint Nash — e.g., to
  answer "should JJ ever fold facing pot odds with 93% equity in this
  range?" (answer: ~0% via Nash; the aggregator falsely reports 7.7%
  per W1.2 evidence — see explainer below).

- **Three new CLI subcommands:**
  - `poker-solver pushfold` — push/fold scenarios.
  - `poker-solver river --hero --villain-range` — river-spot
    ergonomics.
  - `poker-solver parity` — Brown apples-to-apples acceptance runner
    (skips when Brown binary unbuilt).

- **Docs:** USAGE.md gains §5.x "Two range-vs-range paths" (side-by-side
  comparison); §7a is rewritten from "Known CLI gaps" → "Ergonomic
  subcommands" (the gaps are now closed). DEVELOPER.md gains the
  Range-vs-Range internals section.

### Critical honest framing

**`solve_range_vs_range` and `solve_range_vs_range_nash` solve
DIFFERENT mathematical objects.** This is not a quality difference —
they answer different questions:

- **`solve_range_vs_range`** (the aggregator) computes per-(hero combo,
  villain combo) perfect-information 1v1 Nash solves and aggregates
  the result. Output is a histogram of "what fraction of villain
  representatives hero beats in the full-info subgame." Fast, good
  for dry-board value-vs-air dynamics, structurally NOT a range Nash.
- **`solve_range_vs_range_nash`** (new in v1.7.0) computes the joint
  imperfect-information Nash of the two ranges via vector-form CFR.
  Output is a true Nash mixed strategy where hero bluff-catches off
  range composition, polarizes off the range, mixes for the right
  information-theoretic reasons.

The two can diverge by tens of percentage points on polarized spots.
**See `docs/aggregator_vs_true_nash_explainer.md`** for the long-form
distinction with concrete examples (W3.5 AA monotone-board polarization,
W1.2 JJ deep-stack defense).

### Other honest framing

- MINOR bump: new public API surface, no behavior changes to existing
  APIs. No Python entrypoint signature changes beyond ADDED symbols.
- Engine binary unchanged from v1.6.0 (= unchanged from v1.5.0); users
  do NOT need to rebuild Rust for v1.7.0.
- **v1.5.0 Brown apples-to-apples acceptance status is unchanged.**
  v1.7.0 does NOT include the engine bundle (PR 33 + PR 34 + PR 35 +
  PR 40) that addresses per-action divergence — that remains
  deferred to **v1.6.1 or v1.6.2** pending bisection. v1.7.0 makes
  the divergence diagnosis _runnable through the user-facing range
  API_ (via `solve_range_vs_range_nash`), which is the right
  architectural layer.
- Smoke: 50/51 tests pass (1 skip = `parity` happy-path; Brown binary
  unbuilt by design). 12 new tests (6 in `test_range_vs_range_nash.py`
  + 6 in `test_cli_subcommands.py`). Non-slow non-parity-Brown sweep
  green vs v1.6.0 baseline.

EOF

gh release create v1.7.0 \
  --repo amaster97/poker_solver \
  --latest \
  --title "v1.7.0: True Nash range API + CLI ergonomics" \
  --notes-file /tmp/v1.7.0_release_notes.md

# Verify
gh release view v1.7.0 --repo amaster97/poker_solver | head -16
```

**Public-OK audit (per `feedback_public_repo_hygiene`):**
- No `/Users/ashen/...` paths in the release notes.
- No session IDs, no PII, no `claude-session` / `claude_ai_*` references.
- No orchestrator/implementer-agent process terminology beyond what is already in the public CHANGELOG.

---

## 9. Cleanup

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.7.0
# Remove the .so symlink BEFORE worktree removal (don't leave dangling symlink)
rm poker_solver/_rust.cpython-313-darwin.so

# Exit the worktree directory before removing
cd /Users/ashen/Desktop/poker_solver

git worktree remove /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.7.0
git worktree list      # verify ship-v1.7.0 is gone; source worktrees remain
```

Per LEG 18 precedent: local `ship-v1.7.0` branch may not delete cleanly with `-d` if the shared tree's `main` ref is stale. **Do NOT force-delete with `-D`** (per memory rule `feedback_no_concurrent_branch_ops`).

### Optional: catch up shared tree

```bash
# Only when no other worktree is mid-write:
cd /Users/ashen/Desktop/poker_solver
git pull --ff-only origin main
```

### Downstream impact (per `feedback_ui_packaging_sync`)

- **PR 10b UI** — v1.7.0 adds the `solve_range_vs_range_nash` public API. Per the spec doc (`docs/pr_proposals/v1_7_0_aggregator_vector_wiring.md` §4 "UI cascade scope"), a "True Nash mode" toggle in the RvR panel is recommended but may slip to v1.7.1 — depends on PR 10b agent bandwidth. **Decision point at ship time:** bundle the toggle UI into a quick v1.7.1 PATCH, or defer to a fuller UI update bundle.
- **PR 11 .dmg rebuild** — feature PR (new public API) triggers PR 11 .dmg rebuild. After v1.7.0 ships, kick PR 11 to repackage the bundled Mac .dmg with the v1.7.0 build.
- **Persona retest cascade (post-v1.7.0)** — see §11 below. The big win: W3.5 + W1.2 + W2.3 + W3.4 can now be re-run via the new entry point to validate the Nash-vs-aggregator distinction empirically, end-to-end through the public Python API.

---

## 10. Estimated ship time

Based on LEG 18 baseline (~15-25 min for 2 PRs with single-range cherry-pick, no Rust rebuild) and LEG 17 baseline (~7 min for 3 small PATCH PRs):

| Step | Time |
|---|---|
| Pre-flight (§1) — SHAs + sanitize + per-worktree smoke + PR 43 audit verify | 3-4 min (parallel across 2 worktrees) |
| Ship worktree setup + symlink (§2a-b) | 1 min |
| Two-step cherry-pick (§2c) — PR 43 then PR 39 | 1-2 min |
| Smoke tests in ship worktree (§5) — 50 expected + regression sweep | 4-6 min (W3.5 + W1.2 cases are slow — 3-10 s each at 1000 iter) |
| Version bump + CHANGELOG + §7a tag fix + commit (§6) | 3-5 min |
| Tag + push (§7) | 1-2 min |
| GitHub release (§8) | 1-2 min |
| Cleanup (§9) | <1 min |
| **Total** | **15-25 min wall-clock** |

Logistics simpler than LEG 18 (2 PRs vs LEG 18's 2 PRs but slightly smaller diff total — ~600 lines vs LEG 18's ~3300). Risk surface comparable: USAGE.md is the only file both touch, and the sections are disjoint. Estimate matches prompt budget.

---

## 11. Risk register

| Risk | Probability | Mitigation |
|---|---|---|
| PR 43 implementer not done by ship time | **Medium** — in flight at plan time | HOLD ship; defer LEG 20. PR 39 alone is rejected (semver-monotonic; see §1b). |
| PR 43 audit surfaces Type C-CRITICAL finding | Low-medium — algorithm is validated (PR 23 cell parity per PR 40); wrapper is a thin port | HOLD ship until remediation. Per `feedback_persona_test_rectification` framework. |
| W3.5 Tier 1 test fails | Low — W3.5 TRUE Nash PoC already passes on PR 23 binding | If fails: STOP. v1.7.0 cannot ship without the headline demo. Debug in PR 43 worktree, re-stage. |
| Cherry-pick conflict on USAGE.md | Low | §3.1 analysis shows disjoint sections (§5.x vs §7a). Fallback: keep PR 39's §7a, hand-merge §5.x — see §2c resolution rule. |
| USAGE.md §7a version-tag missed | Low — easy to forget | §6c explicit step in checklist. |
| Smoke-test fail in ship worktree | Low | Each worktree green at stage time; cherry-pick to disjoint base shouldn't change behavior. Likely culprit if it fires: PR 43 import collision (`solve_range_vs_range_nash` already exported by something) — fix in implementer worktree. |
| Sanitization scan surfaces new PII | Low | §1d expected matches only inside `docs/pr_proposals/v1_5_pr_43_implementer_notes.md` (if present) following PR 24a/24b precedent. Hard gate: STOP if anything outside that file matches. |
| Tag v1.7.0 already exists | Nil | `git ls-remote --tags origin` at plan time shows tags only up to v1.5.1 (LEG 18 not yet shipped). At ship time, expect tags through v1.6.0 only. |
| Maturin rebuild needed | Nil | Python-only PRs; verified zero `crates/**` or `pyproject.toml` build-config touches. |
| LEG 19 (v1.6.1 engine bundle) ships first and rebases v1.7.0 base | Low — only matters if v1.6.1 ships AFTER v1.6.0 but BEFORE v1.7.0 | If LEG 19 ships first: re-stage this plan with `<V1_6_0_SHA>` replaced by v1.6.1's release SHA. The conflict matrix vs v1.6.1 is expected nil (engine bundle is Rust + Python delegate; doesn't touch `range_aggregator.py` user API or `cli.py`). |
| `crates/cfr_core/Cargo.toml` version-bump policy unclear | Low — historical pattern is to leave at 0.5.0 across patches | §6a documents conditional bump. If unsure: leave unchanged (Python `__version__` is the user-facing version). |

---

## 12. Output: ship report

After ship, the ship agent writes `/Users/ashen/Desktop/poker_solver/docs/leg20_v1_7_0_ship_report.md` following the LEG 17 / LEG 18 templates:

- §1 Release artifacts (tag SHA, release URL, previous release, commits-on-main delta)
- §2 Execution timeline (wall-clock per step)
- §3 Cherry-pick verification (source SHA → new commit SHA mapping per PR; conflict count)
- §4 Smoke test results (50/51 + regression sweep; **explicit W3.5 + W1.2 pass evidence** — these are the headline claims)
- §5 Version bump verification (before/after per file)
- §6 Honest framing in CHANGELOG + release notes (aggregator-vs-Nash distinction explicit; engine bundle deferral to v1.6.1/v1.6.2 explicit)
- §7 USAGE.md §7a version-tag adjustment (v1.5.2+ → v1.7.0+) verification
- §8 Cleanup status (symlink removed, worktree removed, branch retained)
- §9 Unexpected complexity (expected: none, mirroring LEG 17/18)
- §10 Next steps (PR 11 .dmg rebuild kickoff; PR 10b True Nash toggle decision; persona retest cascade per §11 below)

---

## 13. Cascading retest queue (post-v1.7.0)

The big architectural unlock from v1.7.0 is that **persona tests can now be re-run against the true Nash entry point through the public Python API** — without dropping to the Rust binding directly. This validates the explainer doc's claims end-to-end.

Schedule (orchestrator-driven, post-v1.7.0):

1. **Re-run W3.5 PASS via `solve_range_vs_range_nash`** (validates the test methodology). The W3.5 TRUE Nash PoC at `docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md` was through the raw Rust binding; the new run validates the same result through the public Python wrapper.
2. **Re-run W2.3 (river-spot bluff-catching scenarios) via new path** if applicable. Per the explainer doc §"Implications for persona tests": "Spec questions about *range polarization*, *bluff-catching*, and *inducing* require the vector form."
3. **Re-run W3.4 (turn-spot polarized sizing)** via new path if applicable.
4. **Re-run W4.3 (CLI ergonomics retest)** via PR 39's new subcommands. The original W4.3 used Python one-liner workarounds; the retest validates the new CLI surface.
5. **Re-run W2.2 (still set-membership but cleaner entry point via `solve_range_vs_range_nash`)**.
6. **Run W2.4 batch CLI retest** with PR 39's `pushfold` + `river` + `parity` subcommands.
7. **Re-run W1.2 deep-stack JJ defense** via `solve_range_vs_range_nash` — codifies the deterministic 7.7% → ~0% transition empirically.

Per `feedback_persona_test_rectification`: after each persona acceptance phase, classify findings by Type A/B/C and route per the framework at `docs/pr13_prep/rectification_framework.md`. Expect: most reclassify from "PASS with caveats" to "PASS" once the right tool is matched to the right question.

---

## 14. Authorization & per-PR branch hygiene

Per `feedback_pr10a5_autonomous_commit` + LEG 17/18 precedent: PR 43 and PR 39 must both be audit-cleared before autonomous end-to-end ship is in scope. Conditions:

- PR 43 implementer reports DONE + smoke-clean + audit-cleared (no Type C-CRITICAL findings; W3.5 demo passes).
- PR 39 already verified clean at `7584e06` per `docs/pr_39_cherrypick_plan.md` §1.

If both clear: autonomous ship (cherry-pick + push + tag + release) is within scope. No exception conditions apply by default (no force-push, no origin branch deletion, no major design decisions deferred at ship time).

Per `feedback_pr_branch_hygiene`: the source feature branches `pr-43-nash-wrapper` and `pr-39-cli-ergonomics` on public origin should remain clean (don't push the local `ship-v1.7.0` branch — it's a ship-only artifact). After ship, the source feature branches may be retained for archive (per memory rule against `-D`).

Per `feedback_dual_remote_workflow`: this plan covers the public `origin` push only. Mirror sync to the private `integration` remote is a separate post-ship step handled by the dual-remote sync protocol.

---

## 15. Hard blockers summary (gating ship)

For the ship agent — **DO NOT proceed past §2 if ANY of these is true:**

1. PR 43 implementer not done (branch tip not stable at `<PR_43_SHA>`).
2. PR 43 audit not cleared (Type C-CRITICAL finding open).
3. W3.5 Tier 1 test (`test_w3_5_monotone_aa_pure_check`) fails in PR 43 worktree.
4. `origin/main` not at v1.6.0 (LEG 18 hasn't shipped).
5. PR 39 SHA drifted from `7584e06` without re-audit.
6. Sanitization scan (§1d) surfaces PII outside expected implementer-notes paths.

If ANY is true: HOLD ship, report blocker to orchestrator, do not advance to §3.
