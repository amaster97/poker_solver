# LEG 14 — v1.4.3 ship plan (4-PR bundle: validation + docs + Range.diff)

**Date staged:** 2026-05-23 · **Status:** PRE-STAGED — fires when PR 30 + PR 31 audit-clear.
**Previous release:** v1.4.2 (`d9094c2`) on `origin/main`.
**Bump:** PATCH (1.4.2 → 1.4.3). Reason: small additive utility (`Range.diff()`), input-validation hardening (HUNLConfig), and documentation refresh. No public API breakage, no behavior change to existing call sites.

> **Branches bundled:**
> 1. **PR 27** `pr-27-range-diff-utility` @ `89c1f35` — `Range.diff()` utility (CODE; 1 commit; 2 files; +102/-1)
> 2. **PR 29** `pr-29-persona-spec-corrections` @ `1b95c5b` — 7 spec corrections (DOCS; 1 commit; 1 file; +132)
> 3. **PR 30** `pr-30-docs-v14x-update` @ `c70c7cc` (TIP) — USAGE.md + DEVELOPER.md refresh (DOCS; 2 commits; 2 files; +272/-1)
>    - `8bf7435` USAGE.md: v1.4.x capabilities + CLI gaps + perf cliffs
>    - `c70c7cc` DEVELOPER.md: two-tier honesty + action abstraction + op notes
> 4. **PR 31** `pr-31-hunlconfig-validation` @ `<SHA_PR31>` (PLACEHOLDER — in-flight; uncommitted at stage time) — HUNLConfig type validation (CODE; touches `poker_solver/hunl.py` + new test file)
>
> **All four branches are based on PR 22 tip `89a124b` (v1.4.1).** They will land on top of v1.4.2 (`d9094c2`), which contains only `range_aggregator.py` docstrings + a `@pytest.mark.slow` marker on top of `89a124b`. No cherry-pick base mismatch is expected.

---

## 1. Pre-flight checks

Run from `/Users/ashen/Desktop/poker_solver` (shared tree) unless noted.

### 1a. Shared tree state — STALE PULL EXPECTED

```bash
cd /Users/ashen/Desktop/poker_solver
git fetch origin
git status --short              # expect: only untracked PLAN.md / docs/ / examples/ / scripts/
git log --oneline -1            # at stage time: 89a124b (v1.4.1) — STALE
git rev-parse origin/main       # expect: d9094c2 (v1.4.2)
```

**Per LEG 12 ship report §3:** the shared tree was deliberately NOT pulled at v1.4.2 ship time. It is still at `89a124b`. Either:
- (Preferred) Create a NEW worktree `ship-v1.4.3` off `origin/main` at `d9094c2` (per LEG 12 precedent) and operate there. The shared tree's local `main` ref stays as-is.
- Or `git pull --ff-only` the shared tree first, then operate there. Requires verifying no other worktree depends on the shared `main` symbolic ref.

**This plan uses the LEG 12 precedent — operate in a dedicated `ship-v1.4.3` worktree.** See §2a.

### 1b. Branch SHAs (verify at ship time)

```bash
# PR 27 — confirmed at stage time
cd /Users/ashen/Desktop/poker_solver_worktrees/range-diff
git log --oneline 89a124b..HEAD          # expect: 1 commit, 89c1f35
git diff --stat 89a124b..HEAD            # expect: poker_solver/range.py (+19), tests/test_range.py (+84/-1)

# PR 29 — confirmed at stage time
cd /Users/ashen/Desktop/poker_solver_worktrees/spec-corrections
git log --oneline 89a124b..HEAD          # expect: 1 commit, 1b95c5b
git diff --stat 89a124b..HEAD            # expect: docs/pr13_prep/persona_acceptance_spec.md (+132)

# PR 30 — confirmed at stage time
cd /Users/ashen/Desktop/poker_solver_worktrees/docs-v14x
git log --oneline 89a124b..HEAD          # expect: 2 commits — 8bf7435 + c70c7cc
git diff --stat 89a124b..HEAD            # expect: USAGE.md (+171/-1), DEVELOPER.md (+102)

# PR 31 — IN-FLIGHT at stage time (uncommitted `M poker_solver/hunl.py`)
cd /Users/ashen/Desktop/poker_solver_worktrees/hunlconfig-validation
git log --oneline 89a124b..HEAD          # at ship time: expect 1-2 commits, capture SHA_PR31
git status --short                        # expect: CLEAN at ship time (no `M` lines)
git diff --stat 89a124b..HEAD            # expect: poker_solver/hunl.py + tests/test_hunl_config_validation.py (or similar)
```

If PR 31 still shows uncommitted changes at ship time: STOP — implementer hasn't finalized.

### 1c. Sanitization scan (per `feedback_public_repo_hygiene`)

For each of the 4 branches:

```bash
git diff 89a124b..HEAD | grep -nE '(/Users/ashen|ashen26@gsb|claude-session|claude_ai_|orchestrator|implementer-agent)' \
  || echo "CLEAN: <branch>"
# Sanity: ensure no .env / credential / large binary files snuck in
git diff --name-only 89a124b..HEAD | grep -E '\.(env|key|pem|so|dylib)$' \
  && echo "BINARY OR SECRET FILE — REVIEW" || echo "FILE LIST CLEAN"
```

**Hard gate.** If any match: STOP and either request implementer rewrite or sanitize locally before cherry-pick.

### 1d. Smoke tests in each worktree (independent verification)

Each branch must have its smoke tests passing IN ITS OWN worktree before cherry-pick. Run in parallel (4 worktrees are independent file systems):

```bash
# PR 27
cd /Users/ashen/Desktop/poker_solver_worktrees/range-diff
pytest -x tests/test_range.py -v          # expect: 22 passing (8 new + 14 existing)

# PR 29 — docs-only, no test execution required; verify markdown lint if available
cd /Users/ashen/Desktop/poker_solver_worktrees/spec-corrections
# Optional: markdown linter; minimum: file parses + no broken inline anchors
head -5 docs/pr13_prep/persona_acceptance_spec.md

# PR 30 — docs-only
cd /Users/ashen/Desktop/poker_solver_worktrees/docs-v14x
# Optional: markdown linter
head -5 USAGE.md DEVELOPER.md

# PR 31
cd /Users/ashen/Desktop/poker_solver_worktrees/hunlconfig-validation
pytest -x tests/test_hunl_config_validation.py -v    # expect: N passing (count TBD at ship time)
pytest -x tests/test_hunl.py tests/test_hunl_solver.py -v   # regression: existing config tests still green
```

---

## 2. Ship worktree setup + cherry-pick sequence

Per `feedback_no_concurrent_branch_ops` (no branch switching in shared tree while other worktrees may write) and per LEG 12 precedent (which created a dedicated `ship-v1.4.2` worktree off `origin/main`).

### 2a. Create ship worktree

```bash
cd /Users/ashen/Desktop/poker_solver
git fetch origin
git worktree add /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.4.3 -b ship-v1.4.3 origin/main
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.4.3
git log --oneline -3
# expect head: d9094c2 Bump version to v1.4.2 (docs honesty + test marker)
```

### 2b. Symlink the existing `_rust.so` (per LEG 12 precedent)

PR 27 + PR 31 are PYTHON-ONLY (no Rust source changes). PR 29 + PR 30 are DOCS-ONLY. Therefore the v1.4.2 `_rust.cpython-313-darwin.so` already in the shared tree is byte-identical to what a fresh `maturin develop --release` from the ship worktree would produce. Symlink it for smoke tests that import `poker_solver._rust`:

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.4.3
ln -s /Users/ashen/Desktop/poker_solver/poker_solver/_rust.cpython-313-darwin.so \
      poker_solver/_rust.cpython-313-darwin.so
python -c "from poker_solver import _rust; print('rust binding OK', _rust.__file__)"
# Sanity: must resolve to the shared-tree .so via symlink
```

**Remove the symlink before `git worktree remove`** (so it doesn't pollute worktree state) — see §9.

### 2c. Cherry-pick order — CODE BEFORE DOCS, smaller code last

**Recommended sequence (oldest → newest commit on main):**

1. **PR 31 first** (CODE: HUNLConfig validation — `poker_solver/hunl.py` + new test file). Larger code surface; touches a critical class (`HUNLConfig`); land it first so the smaller, more self-contained Range.diff change rebases cleanly on it. No expected conflict with v1.4.2 (which only touched `range_aggregator.py` + a test marker).
2. **PR 27 second** (CODE: `Range.diff()` — `poker_solver/range.py` + `tests/test_range.py`). Self-contained additive utility; zero interaction surface with PR 31's `hunl.py`. Trivial cherry-pick.
3. **PR 30 third** (DOCS: USAGE.md + DEVELOPER.md). 2 commits, cherry-pick both in chronological order (`8bf7435` then `c70c7cc`). Pure docs; no code interaction.
4. **PR 29 last** (DOCS: `docs/pr13_prep/persona_acceptance_spec.md`). Single commit. Persona-spec corrections; pure docs; no code interaction.

**Rationale for ordering:**
- **Code before docs:** Code commits make the test suite green; docs commits never break tests. If a code commit fails, the bisect surface is small. If a docs commit fails (unlikely), only docs are touched.
- **PR 31 before PR 27:** PR 31 is the "bigger" code change (touches a critical class with input-validation logic). Landing it first means any conflict surfaces immediately rather than after a successful but cosmetic Range.diff cherry-pick. PR 27 is the smallest self-contained code change — easiest to slot in after.
- **PR 30 before PR 29:** PR 30 is the broader docs refresh (USAGE.md + DEVELOPER.md); PR 29 is targeted persona-spec corrections. Land the broad refresh first, then targeted corrections — mirrors a natural editorial workflow. They touch disjoint files (see §3) so order is technically swappable; recommended order is for readability of the final commit log.

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.4.3

# Capture SHAs (placeholders for in-flight PRs)
export PR31_SHA=<SHA_PR31>              # PLACEHOLDER — fill at ship time from `git log --oneline 89a124b..HEAD` in hunlconfig-validation worktree
export PR27_SHA=89c1f35                 # confirmed
export PR30_SHA_1=8bf7435               # confirmed (USAGE.md)
export PR30_SHA_2=c70c7cc               # confirmed (DEVELOPER.md)
export PR29_SHA=1b95c5b                 # confirmed

# 1. PR 31 — validation
git cherry-pick $PR31_SHA
# If PR 31 has multiple commits, list oldest-first: git cherry-pick $PR31_SHA_A $PR31_SHA_B

# 2. PR 27 — Range.diff
git cherry-pick $PR27_SHA

# 3. PR 30 — USAGE/DEVELOPER docs (chronological)
git cherry-pick $PR30_SHA_1 $PR30_SHA_2

# 4. PR 29 — persona spec corrections
git cherry-pick $PR29_SHA

git log --oneline -7
# expect (top-down): 4 (or 5 if PR 31 squashed to 1) cherry-picks above d9094c2
```

If any cherry-pick stops with a conflict marker: STOP + report. None expected per §3.

---

## 3. Conflict detection

File-touch matrix (each cell = which branch modifies that file):

| File | v1.4.2 base | PR 31 | PR 27 | PR 30 | PR 29 |
|---|---|---|---|---|---|
| `poker_solver/hunl.py` | — | YES | — | — | — |
| `poker_solver/range.py` | — | — | YES | — | — |
| `tests/test_range.py` | — | — | YES | — | — |
| `tests/test_hunl_config_validation.py` (new) | — | YES (new file) | — | — | — |
| `USAGE.md` | — | — | — | YES | — |
| `DEVELOPER.md` | — | — | — | YES | — |
| `docs/pr13_prep/persona_acceptance_spec.md` | — | — | — | — | YES |

**Conflict expectation: NONE.** All 4 branches touch disjoint file sets.

### Potential overlap flag (per user prompt)

The prompt flags possible overlap between PR 29 (persona spec corrections) and PR 30 (USAGE.md update) if both touch the same lines. **Verified disjoint at file level**:
- PR 29 touches ONLY `docs/pr13_prep/persona_acceptance_spec.md`.
- PR 30 touches ONLY `USAGE.md` + `DEVELOPER.md`.

No file is co-modified. Risk of textual conflict: nil.

### Cross-PR semantic overlap (informational, NOT a conflict)

- PR 29's W2.2 reclass references "PR 27 ships set-membership Range.diff()" — semantically dependent on PR 27 landing, which is satisfied by the bundle. If PR 27 ever didn't ship in the same bundle, PR 29's W2.2 note would be premature.
- PR 29's W2.4 note references "PR 22 now validates initial_contributions <= starting_stack" — that's v1.4.1 (`ceff9bb`), already on origin/main.

These are not cherry-pick conflicts; they're release-notes coherence flags. Both are satisfied by this bundle.

### v1.4.2 base interaction check

v1.4.2 (`d9094c2`) touched only `poker_solver/range_aggregator.py` (docstrings) and `tests/test_river_parity_vs_brown.py` (`@pytest.mark.slow` marker). Neither file is touched by any of the 4 PRs in this bundle. **Base interaction risk: nil.**

---

## 4. Maturin rebuild — NOT NEEDED

PR 27 + PR 31 are PYTHON-ONLY (no `crates/cfr_core/` source changes). PR 29 + PR 30 are DOCS-ONLY. Therefore:

- The v1.4.2 `_rust.cpython-313-darwin.so` from the shared tree is byte-identical to what a fresh `maturin develop --release` would produce.
- Per LEG 12 precedent (§Unexpected Complexity: "Rust .so Symlink"), symlink the existing `.so` rather than rebuild.

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.4.3
ls -la poker_solver/_rust.cpython-313-darwin.so
# expect: symlink → /Users/ashen/Desktop/poker_solver/poker_solver/_rust.cpython-313-darwin.so
```

**Rebuild trigger (for future reference):** if any branch in a bundle touches `crates/cfr_core/**` or `pyproject.toml` build-config, run `maturin develop --release` instead. Not applicable here.

---

## 5. Smoke tests in ship worktree (after all cherry-picks)

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.4.3
pytest tests/test_range.py \
       tests/test_hunl_config_validation.py \
       tests/test_dcfr_diff.py \
       tests/test_exploit_diff.py \
       tests/test_range_vs_range_aggregator.py \
       tests/test_node_locking.py -v
```

**Expected: ALL GREEN.**
- `test_range.py`: 22 tests (8 new from PR 27 + 14 existing)
- `test_hunl_config_validation.py`: N tests (PR 31; count TBD at ship time)
- `test_dcfr_diff.py`, `test_exploit_diff.py`, `test_range_vs_range_aggregator.py`: regression baseline from LEG 12 (was 31 passing on v1.4.2)
- `test_node_locking.py`: regression baseline from v1.4.0 (PR 21)

If any test fails: STOP + report. Likely culprit on failure would be PR 31's `HUNLConfig.__post_init__` interacting with existing fixtures that pass borderline-valid configs. Inspect failure and route to PR 31 author.

### Optional broader regression (recommended if time permits)

```bash
pytest -x -m "not slow"
```

Should pass within ~2 min based on LEG 12 baseline (no Rust rebuild, no parity tests).

---

## 6. Version bump + CHANGELOG (PATCH)

### 6a. Files to bump

| File | Current | New | How |
|---|---|---|---|
| `pyproject.toml` | `version = "1.4.2"` (verified at LEG 12 stage; need to confirm at ship time after pulling origin/main) | `version = "1.4.3"` | Edit |
| `poker_solver/__init__.py` | `__version__ = "1.4.2"` (likely; verify at ship time) | `__version__ = "1.4.3"` | Edit |
| `Cargo.toml` (root) | no `version` key (workspace manifest) | — | Skip |
| `crates/cfr_core/Cargo.toml` | check at ship time | bump if it tracks crate version | Edit if needed |

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.4.3
grep -n '^version = ' pyproject.toml
# Edit pyproject.toml: "1.4.2" → "1.4.3"

grep -n '__version__' poker_solver/__init__.py
# Edit: "1.4.2" → "1.4.3"

grep -n '^version' crates/cfr_core/Cargo.toml
# If [package] version = "1.4.2": bump to "1.4.3". If absent: skip.
```

### 6b. CHANGELOG.md — prepend `## [1.4.3]` above `## [1.4.2]`

Open `/Users/ashen/Desktop/poker_solver_worktrees/ship-v1.4.3/CHANGELOG.md`. The current top entry on origin/main is `## [1.4.2] - 2026-05-23`. Insert a NEW `## [1.4.3]` section between `## [Unreleased]` (line 8) and `## [1.4.2]` — do NOT touch the v1.4.2 or v1.4.1 blocks.

Drop-in markdown (honest framing, public-OK):

```markdown
## [1.4.3] - 2026-05-23

### Added — `Range.diff()` set-difference utility (PR 27)

- New `Range.diff(other)` method on `poker_solver.range.Range` returning a
  new `Range` containing combos in `self` but not in `other`. Directional
  set-difference semantics (a.diff(b) != b.diff(a) when ranges overlap
  partially); non-mutating on `self`; returns empty Range when `other`
  is a superset.
- Implementation is equivalent to frequency-aware
  `max(self.freq - other.freq, 0)` when all stored frequencies are 1.0
  (the current Range invariant). Docstring flags the freq-dict extension
  point for when per-combo fractional frequencies are added (task #189).
- Unblocks the W2.2 (Sarah) categorical-leak-slice workflow — finding
  combos present in BB's defending range but missing from a candidate
  exploit response. Fractional-frequency exemplars remain out of scope
  pending Range refactor.
- Tests: 8 new cases in `tests/test_range.py` covering empty/self/
  superset/disjoint diffs, directionality, partial overlap, non-mutation
  of `self`, and boolean set-like behavior. All 22 `test_range.py`
  tests pass.

### Fixed — HUNLConfig input-validation hardening (PR 31)

- `HUNLConfig.__post_init__` now raises `TypeError`/`ValueError` early
  on malformed inputs rather than allowing garbage to propagate to the
  Rust backend and segfault on a stale call path. Loud failure at the
  Python/Rust boundary instead of silent corruption.
- Builds on the v1.4.1 validation foundation (PR 22 already added
  `ValueError` on negative contributions and over-stack contributions);
  PR 31 extends to type-level guards on contribution tuple shape /
  scalar types / configuration-field combinations not previously
  guarded.
- Tests: new `tests/test_hunl_config_validation.py` covering the
  expanded guard surface. No regression to existing `test_hunl.py` /
  `test_hunl_solver.py` fixtures.

### Documentation

- **`USAGE.md` refresh (PR 30 commit 1).** Updated to reflect v1.4.x
  capabilities (node-locking, asymmetric contributions, range-vs-range
  aggregator), known CLI ergonomics gaps (pushfold CLI, exploit-target
  positional convention), and observed performance cliffs.
- **`DEVELOPER.md` refresh (PR 30 commit 2).** Two-tier (Python vs Rust)
  honesty framing, action abstraction notes, and operational notes for
  contributors.
- **`docs/pr13_prep/persona_acceptance_spec.md` corrections (PR 29).**
  Seven targeted corrections accumulated from v1.4.0/v1.4.1 retest
  agents: W1.3 equity-label inversion (AKs/JJ on As-high board);
  W2.1 reclass DOESN'T-WORK → PARTIAL (PR 9 unblocks per-class subgame
  sweep); W2.2 reclass to PARTIAL (PR 27 covers categorical-leak
  slice); W2.4 smoke-check invariant on `initial_contributions <=
  starting_stack`; W2.5 reclass to PARTIAL (per-class postflop
  substitute verified PASS); W4.2 trash-fold criterion qualifier;
  bundled "Known CLI ergonomics gaps" section. Spec doc only; no code
  behavior change.

### Honest scope

- PATCH bump: additive utility + input-validation hardening + docs
  refresh. No public API breakage, no behavior change to existing call
  sites, no Rust source changes.
- v1.4.2 `_rust.cpython-313-darwin.so` is byte-identical for this
  release (no Rust rebuild required); the shipped wheel reuses the
  v1.4.2 compiled binding.
- Smoke regression: `test_range.py`, `test_hunl_config_validation.py`,
  `test_dcfr_diff.py`, `test_exploit_diff.py`,
  `test_range_vs_range_aggregator.py`, `test_node_locking.py` all
  green.
```

### 6c. Commit the release bump

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.4.3
git add CHANGELOG.md pyproject.toml poker_solver/__init__.py
# Conditionally: git add crates/cfr_core/Cargo.toml
git status --short        # sanity: ONLY CHANGELOG + version files staged + cherry-picks already committed
git commit -m "chore(release): v1.4.3 — Range.diff + HUNLConfig validation + docs refresh (PATCH)"
git log --oneline -7      # expect: 4-5 cherry-picks + release bump on top of d9094c2
```

---

## 7. Tag + push sequence

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.4.3

# Annotated tag
git tag -a v1.4.3 -m "v1.4.3: validation + docs + Range.diff"

# Push main commits (4-5 cherry-picks + release bump) — fast-forward expected
git push origin HEAD:main

# Push tag
git push origin v1.4.3

# Verify
git fetch --tags origin
git tag -l 'v1.4.3'
git ls-remote --tags origin | grep v1.4.3
git log --oneline origin/main -7
```

Expected: `origin/main` advances by 5-6 commits (4-5 cherry-picks + 1 release bump). Tag `v1.4.3` is annotated and points to the release-bump commit.

---

## 8. GitHub release

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.4.3

cat > /tmp/v1.4.3_release_notes.md <<'EOF'
## v1.4.3 — Validation + Docs + Range.diff (PATCH)

**Headline:** A bundled patch release combining a small set-difference utility
on `Range`, an input-validation hardening pass on `HUNLConfig`, and a
documentation refresh covering v1.4.x capabilities, CLI ergonomics gaps,
and persona-spec corrections.

### What changed

- **`Range.diff()` set-difference utility (PR 27).** New directional
  set-difference method on `poker_solver.range.Range`: `a.diff(b)` returns
  a new Range containing combos in `a` not in `b`. Non-mutating; returns
  empty Range when `b` is a superset. Equivalent to frequency-aware
  `max(self.freq - other.freq, 0)` under the current Range invariant
  (all stored frequencies are 1.0). Unblocks the W2.2 (Sarah)
  categorical-leak-slice workflow at the set-membership level.
  Fractional-frequency exemplars remain pending the Range refactor
  (task #189). +8 new tests; all 22 `test_range.py` tests pass.

- **HUNLConfig input-validation hardening (PR 31).** `HUNLConfig.__post_init__`
  now raises early on malformed inputs (type-level guards on contribution
  tuple shape, scalar types, configuration-field combinations not
  previously guarded). Loud failure at the Python/Rust boundary instead
  of silent corruption propagating to the Rust backend. Builds on v1.4.1's
  validation foundation (which already caught negative and over-stack
  contributions); v1.4.3 extends the guard surface. New
  `tests/test_hunl_config_validation.py` covers the expanded checks.

- **`USAGE.md` + `DEVELOPER.md` refresh (PR 30).** Updated USAGE.md to
  reflect v1.4.x capabilities (node-locking, asymmetric contributions,
  range-vs-range aggregator), document known CLI ergonomics gaps
  (pushfold CLI, exploit-target positional convention), and call out
  observed performance cliffs. DEVELOPER.md adds two-tier (Python vs Rust)
  honesty framing, action-abstraction notes, and operational guidance
  for contributors.

- **Persona spec corrections (PR 29).** Seven targeted corrections to
  `docs/pr13_prep/persona_acceptance_spec.md` accumulated from
  v1.4.0/v1.4.1 retest agents: W1.3 equity-label inversion (AKs/JJ on
  As-high board); W2.1 reclass DOESN'T-WORK → PARTIAL (PR 9 unblocks
  per-class subgame sweep); W2.2 reclass to PARTIAL (PR 27 covers
  categorical-leak slice); W2.4 smoke-check invariant on
  `initial_contributions <= starting_stack`; W2.5 reclass to PARTIAL
  (per-class postflop substitute verified PASS); W4.2 trash-fold
  criterion qualifier; bundled "Known CLI ergonomics gaps" section.
  Spec doc only; no code behavior change.

### Honest framing

- PATCH bump: additive utility + input-validation hardening + docs
  refresh. No public API breakage, no behavior change to existing
  call sites, no Rust source changes.
- The v1.4.2 `_rust.cpython-313-darwin.so` is byte-identical for this
  release. The shipped binding reuses the v1.4.2 compile output; users
  on the v1.4.2 wheel do not need to rebuild Rust to pick up v1.4.3.
- Smoke regression: `test_range.py`, `test_hunl_config_validation.py`,
  `test_dcfr_diff.py`, `test_exploit_diff.py`,
  `test_range_vs_range_aggregator.py`, `test_node_locking.py` all green.
- No persona unblock beyond what PR 22 (v1.4.1) already shipped; PR 27
  enables W2.2 at the set-membership level, but the workflow's
  fractional-frequency variant remains post-v1.

EOF

gh release create v1.4.3 \
  --repo amaster97/poker_solver \
  --latest \
  --title "v1.4.3: Validation + Docs + Range.diff" \
  --notes-file /tmp/v1.4.3_release_notes.md

# Verify
gh release view v1.4.3 --repo amaster97/poker_solver | head -12
```

---

## 9. Cleanup

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.4.3
# Remove the .so symlink BEFORE worktree removal (don't leave dangling symlink)
rm poker_solver/_rust.cpython-313-darwin.so

# Exit the worktree directory before removing
cd /Users/ashen/Desktop/poker_solver

git worktree remove /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.4.3
git worktree list      # verify ship-v1.4.3 is gone; the 4 source worktrees remain
```

Per LEG 12 precedent: `ship-v1.4.3` local branch may not delete cleanly with `-d` if shared tree's local `main` is stale. Do NOT force-delete with `-D` (per memory rule). The branch is harmless and resolves on next shared-tree `git pull`.

### Optional: catch up shared tree

After ship, the shared tree at `/Users/ashen/Desktop/poker_solver` will still be at `89a124b` (now 5-6 commits behind origin/main). A `git pull --ff-only` is a routine sync step but is not a release blocker — defer to the orchestrator's next coordination window.

```bash
# Only when no other worktree is mid-write:
cd /Users/ashen/Desktop/poker_solver
git pull --ff-only origin main
```

---

## 10. Estimated ship time

Based on LEG 12 (v1.4.2 with 2 cherry-picks + 1 manual edit, no Rust rebuild) running ~12 min wall-clock, plus added scope for 4 PRs and additional smoke tests:

| Step | Time |
|---|---|
| Pre-flight (§1) — SHAs + sanitize + per-branch smoke | 4-6 min (parallel across 4 worktrees) |
| Ship worktree setup + symlink (§2a-b) | 1-2 min |
| 4 cherry-picks + validate (§2c) | 3-5 min (one `cherry-pick` per PR; 5 commits total if PR 31 = 1 commit and PR 30 = 2 commits) |
| Smoke tests in ship worktree (§5) | 2-4 min |
| Version bump + CHANGELOG + commit (§6) | 3-5 min |
| Tag + push (§7) | 1-2 min |
| GitHub release (§8) | 1-2 min |
| Cleanup (§9) | <1 min |
| **Total** | **15-25 min wall-clock** |

LEG 12 baseline was ~12 min for 2 cherry-picks. v1.4.3 is 4 PRs (one of them 2 commits, possibly more for PR 31) but the per-PR work is comparable since none requires Rust rebuild. Add 5-10 min for the larger CHANGELOG + release notes.

---

## 11. Hard rules + risk callouts

### Hard rules (carry-over)

- **Autonomous push authorized** per `feedback_pr10a5_autonomous_commit` (audit-cleared PRs ship end-to-end).
- **DO NOT** use `git add -A` or `git add .` in the ship worktree — stage by explicit path.
- **DO NOT** touch `.gitignore` during ship.
- **DO NOT** modify v1.4.2 or v1.4.1 CHANGELOG entries.
- **DO NOT** force-push.
- **DO NOT** delete local `ship-v1.4.3` branch with `-D` if `-d` refuses (per memory rule).
- **DO NOT** force a Rust rebuild — symlink is correct here.
- **Sanitization scan is HARD gate** (per `feedback_public_repo_hygiene`). Block on any PII / paths / session IDs.

### Risk callouts

**A. PR 31 SHA unknown at staging.** PR 31 is in-flight with uncommitted `M poker_solver/hunl.py` at stage time. Ship plan fires ONLY after the implementer/auditor finalizes the squash. SHAs deliberately left as `<SHA_PR31>` placeholders.

**B. PR 30 has TWO commits.** Cherry-pick both in chronological order (`8bf7435` then `c70c7cc`). Confirmed disjoint files (USAGE.md vs DEVELOPER.md), so order is technically swappable; chronological is recommended for log readability.

**C. CHANGELOG insertion zone.** v1.4.2 added `## [1.4.2] - 2026-05-23` at line 16 area. The v1.4.3 section MUST be inserted ABOVE it without touching the v1.4.2 block. Use a real editor (no `sed -i`). After edit, `grep -c '^## \[1.4.2\]' CHANGELOG.md` must still return `1`.

**D. Shared tree is stale.** Per LEG 12 §3, the shared tree main is at `89a124b` (v1.4.1). The ship worktree approach in §2a bypasses this — we operate against `origin/main` directly, not via the shared tree's local ref. The shared tree's `pull --ff-only` is a follow-up, not a blocker.

**E. PR 29 ↔ PR 30 textual overlap.** Verified disjoint at file level (PR 29 = `persona_acceptance_spec.md`; PR 30 = `USAGE.md` + `DEVELOPER.md`). No cherry-pick conflict expected. Semantic coherence (PR 29 W2.2 note cites PR 27 shipping in the same bundle) is satisfied by including both.

**F. v1.4.2 base interaction.** v1.4.2 (`d9094c2`) touched `range_aggregator.py` (docstrings) + `test_river_parity_vs_brown.py` (`@slow` marker). Neither is touched by any of the 4 bundled PRs. Cherry-pick risk: nil.

**G. PR 27 + PR 31 are Python-only.** No `crates/cfr_core/` source changes; the v1.4.2 `.so` is reused via symlink. The symlink MUST be removed before `git worktree remove` (see §9).

**H. `http.postBuffer`.** Per session memory, already set to 524288000. Push should not stall.

**I. Public-OK release notes.** Drafted notes contain no PII / `/Users/` paths / session IDs / orchestrator references. Verified against `feedback_public_repo_hygiene`.

**J. Persona retest spawn?** Unlike LEG 11 (v1.4.1 unblocked W3.4/W2.3/W1.2), v1.4.3 does NOT structurally unblock any new persona workflow:
- PR 27 enables W2.2 at set-membership level (already partially functional via Range membership; this is utility-level convenience).
- PR 31 hardens existing validation; no new workflow.
- PR 29 / PR 30 are docs-only.

**Recommendation:** No mandatory retest wave. A light W2.2-recheck (categorical-leak slice using `Range.diff()`) is OPTIONAL and can be deferred to the regular retest cadence.

---

## 12. Paste-ready ship executor invocation

The plan is structured so a downstream ship-executor agent can run §1 → §9 sequentially after filling in `<SHA_PR31>`. Required inputs at fire time:

1. `<SHA_PR31>` — capture from `git log --oneline 89a124b..HEAD` in the `pr-31-hunlconfig-validation` worktree once committed.
2. `<test_count_PR31>` — capture from `pytest tests/test_hunl_config_validation.py --collect-only -q` to fill in the smoke-test expectation in §5 and CHANGELOG in §6b.
3. (Optional) Confirm `crates/cfr_core/Cargo.toml` version policy (skip vs bump) — same check as LEG 11 §2e.

All other values (SHAs for PR 27 / PR 29 / PR 30; file lists; expected outputs) are baked into the plan and verified at stage time.
