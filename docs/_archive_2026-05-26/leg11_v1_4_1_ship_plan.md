# LEG 11 — v1.4.1 ship plan (PR 22 asymmetric initial contributions)

**Date staged:** 2026-05-23 · **Status:** PRE-STAGED — fires when PR 22 audit-clears.
**PR 22 worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/pr-22-asymmetric` on branch `pr-22-asymmetric-contributions`.
**Main tree:** `/Users/ashen/Desktop/poker_solver` on `main`, HEAD `166d2b8` (v1.4.0).
**Bump:** PATCH (1.4.0 → 1.4.1). Reason: Fix A is a bug correction (`initial_contributions` was silently ignored); Fix B is a robustness guard (`ValueError` instead of segfault). No public API surface changes.

> Snapshot at staging time: PR 22 worktree has uncommitted changes on `poker_solver/hunl.py` + `crates/cfr_core/src/hunl.rs` + untracked `tests/test_asymmetric_contributions.py`. Implementer is mid-work, no commits yet on the feature branch. `COMMIT_SHA` placeholders below — fill in at ship time once the implementer/auditor finalizes the squash.

---

## 1. Pre-flight checks

Run these from `/Users/ashen/Desktop/poker_solver` BEFORE cherry-picking.

### 1a. PR 22 worktree state

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/pr-22-asymmetric
git branch --show-current                  # expect: pr-22-asymmetric-contributions
git status --short                          # expect: clean (no M / ?? lines)
git log --oneline main..HEAD                # enumerate commits to cherry-pick; expect 1-3 commits
git rev-list --count main..HEAD             # commit count
git diff --stat main..HEAD                  # expect: hunl.py + hunl.rs + test_asymmetric_contributions.py only
git diff --stat main..HEAD -- poker_solver/ # files in poker_solver/ touched
git diff --stat main..HEAD -- crates/       # files in crates/ touched (Rust)
git diff --stat main..HEAD -- tests/        # test files
```

If `git log --oneline main..HEAD` shows zero commits, the implementer hasn't committed yet — wait. If it shows >3 commits, request a squash before cherry-pick (cleaner main history).

### 1b. Sanitization scan (per `feedback_public_repo_hygiene`)

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/pr-22-asymmetric
# Block on any of these matching staged content:
git diff main..HEAD | grep -nE '(/Users/ashen|ashen26@gsb|claude-session|claude_ai_|orchestrator|implementer-agent)' || echo "CLEAN"
# Also scan untracked/new test files:
grep -rnE '(/Users/ashen|ashen26@gsb|claude-session)' tests/test_asymmetric_contributions.py 2>/dev/null || echo "TEST CLEAN"
# Sanity: did any doc files sneak in?
git diff --name-only main..HEAD | grep -E '^docs/' && echo "DOCS TOUCHED — review" || echo "NO DOCS TOUCHED"
```

If any line matches PII / paths / session IDs: STOP and either request a rewrite from the implementer or sanitize locally before cherry-pick.

### 1c. Tests pass in worktree

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/pr-22-asymmetric
# Rebuild Rust binding for the worktree first (PR 22 touches Rust):
maturin develop --release
# Targeted asymmetric tests:
pytest -x tests/test_asymmetric_contributions.py -v
# Regression: symmetric (500, 500) fixture (must remain unchanged):
pytest -x tests/test_hunl.py tests/test_hunl_solver.py -v
# Full Python suite (gate before ship):
pytest -x -m "not slow"
# Rust unit tests:
cargo test --all
```

All four must be green. If any symmetric test changed value (not just count), STOP — the fix shouldn't perturb `(500, 500)` baselines per proposal §3 case 1.

### 1d. Main tree is clean

```bash
cd /Users/ashen/Desktop/poker_solver
git status --short          # expect: only untracked docs/ examples/ scripts/ (known carry-overs); nothing modified/staged
git log --oneline -1        # expect: 166d2b8 chore(release): v1.4.0 ...
git rev-parse HEAD          # expect: 166d2b8...
git fetch origin
git rev-parse origin/main   # expect: same SHA as HEAD (no drift)
```

If `git status` shows any `M ` line for tracked files, STOP — investigate before mutating main.

---

## 2. Cherry-pick sequence (executed in main tree)

PR 22 worktree is separate from `/Users/ashen/Desktop/poker_solver`, so per `feedback_no_concurrent_branch_ops` we cherry-pick **into the existing main checkout** (no branch switch in shared tree, no second worktree needed).

### 2a. Enumerate exact SHAs (run at ship time)

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/pr-22-asymmetric
git log --oneline main..HEAD
# Example output (placeholder — replace at ship time):
#   <SHA_C> test: add asymmetric initial_contributions coverage
#   <SHA_B> fix: HUNLConfig.__post_init__ raises ValueError on invalid contributions (Fix B)
#   <SHA_A> fix: HUNLPoker.initial_state honors initial_contributions postflop (Fix A)
# Capture chronological order (oldest first) for cherry-pick:
export PR22_SHA_A=<oldest_SHA>      # Fix A
export PR22_SHA_B=<middle_SHA>      # Fix B
export PR22_SHA_C=<newest_SHA>      # tests
# If implementer squashed to a single commit, just:
export PR22_SHA=<only_SHA>
```

### 2b. Cherry-pick into main

```bash
cd /Users/ashen/Desktop/poker_solver
# If single squash commit:
git cherry-pick $PR22_SHA
# If multiple commits (oldest-first):
git cherry-pick $PR22_SHA_A $PR22_SHA_B $PR22_SHA_C
```

Expected conflict surface: NONE. PR 22 touches `poker_solver/hunl.py` (postflop branch of `initial_state` + `HUNLConfig.__post_init__`) and `crates/cfr_core/src/hunl.rs`. v1.4.0 (PR 21 node-locking) modified `dcfr.py` / `solver.py` / `hunl_solver.py` / `crates/cfr_core/src/{dcfr,hunl_solver,preflop,solver}.rs` — **disjoint from `hunl.py` and `hunl.rs`**. If a conflict appears, STOP + report.

### 2c. Rebuild Rust binding into main tree

PR 22 modifies `crates/cfr_core/src/hunl.rs`. Stale `_rust.so` (`/Users/ashen/Desktop/poker_solver/poker_solver/_rust.cpython-313-darwin.so` from v1.4.0) will produce false-positive symmetric tests AND mask Fix A. Rebuild before validating:

```bash
cd /Users/ashen/Desktop/poker_solver
maturin develop --release
python -c "from poker_solver import _rust; print('rust binding OK', _rust.__file__)"
# Sanity: smoke-test that asymmetric path now works through the Python -> Rust call:
pytest -x tests/test_asymmetric_contributions.py -v
pytest -x -m "not slow"
cargo test --all
```

### 2d. CHANGELOG.md (additive — append above v1.4.0 entry)

Open `/Users/ashen/Desktop/poker_solver/CHANGELOG.md`. The current top entry is `## [1.4.0] - 2026-05-23` at line 16. Insert a NEW `## [1.4.1]` section between `## [Unreleased]` (and its `### In progress` block) and `## [1.4.0]` — do NOT touch the v1.4.0 block.

Drop-in markdown (verified honest against proposal §1-2):

```markdown
## [1.4.1] - 2026-05-23

### Fixed — Asymmetric initial contributions (PR 22)

- `HUNLPoker.initial_state` now honors `cfg.initial_contributions` for
  postflop subgames. Previously the postflop branch in
  `poker_solver/hunl.py` hardcoded `to_call=0`, `cur_player=1`, and
  `street_aggressor=-1` regardless of `initial_contributions`, so
  passing `(1000, 500)` to model "P0 c-bet half-pot, P1 facing" produced
  an engine state where both players saw `to_call=0` and P1 was treated
  as opening rather than defending. After the fix:
  - `to_call = max(contributions) - min(contributions)`.
  - `cur_player` is the lower-contribution player when `to_call > 0`
    (the one facing the bet).
  - `street_aggressor` is the higher-contribution player when
    `to_call > 0`.
  - Symmetric `(500, 500)` is unchanged: `to_call=0`, `cur_player=1`,
    `street_aggressor=-1`. All existing fixtures and tests stay bit-
    identical.
- `HUNLConfig.__post_init__` now raises `ValueError` (rather than
  segfaulting downstream in the Rust backend) on negative contributions,
  contributions exceeding `starting_stack`, and asymmetric configs where
  the facing-bet player has zero stack behind. Error message names the
  offending field.

### Persona — Daniel / Sarah / Marcus facing-bet workflows unblocked

- W3.4 (Daniel) MDF check — BB defends ≥ MDF vs half-pot c-bet — is now
  structurally executable. Previously returned the opening strategy
  because the engine ignored asymmetric contributions.
- W2.3 (Sarah) — KK on Q-high flop vs villain's c-bet range.
- W1.2 (Marcus) — JJ on As Tc 5d Jh 8s river vs pot-sized bet (MDF
  bluff-catcher).

These workflows now work end-to-end through the existing `solve()` API
by constructing the postflop `HUNLConfig` with asymmetric
`initial_contributions`. No new public API surface.

### Honest scope

- This is the v1.4.1 follow-up to v1.4.0 per the stagger-fallback path
  documented in `docs/leg9_v1_4_0_ship_plan.md` §7.
- Symmetric-baseline behavior is unchanged; diff tests against v1.4.0
  remain green for `(500, 500)` fixtures.
- The Rust binding (`poker_solver/_rust.so`) is rebuilt as part of this
  release; downstream consumers who pip-installed v1.4.0 from a wheel
  must reinstall to pick up the asymmetric-postflop fix on the Rust
  tier.

### Tests

- New `tests/test_asymmetric_contributions.py` covering symmetric
  regression baseline, P1-faces-bet, P0-faces-bet (probe / 3-bet pot),
  invalid-negative `ValueError`, invalid-over-stack `ValueError`, and
  the W3.4 BB-defends-half-pot-c-bet smoke check (defense within
  [55%, 80%]).
```

### 2e. Version bump (PATCH)

Three files hold version strings — verified at staging:

| File | Current | New | How |
|---|---|---|---|
| `pyproject.toml` | `version = "1.4.0"` | `version = "1.4.1"` | Edit line `version = "1.4.0"` |
| `poker_solver/__init__.py` | needs verification at ship time — read line for `__version__` | `1.4.1` | Edit `__version__ = "1.4.0"` → `"1.4.1"` |
| `Cargo.toml` (root) | **no `version` key** — root is a `[workspace]` manifest with `members = ["crates/cfr_core"]`. No bump here. | — | Skip root |
| `crates/cfr_core/Cargo.toml` | verify at ship time (likely `version = "1.4.0"` or `version = "0.1.0"` — match pattern v1.4.0 used) | `1.4.1` if it tracks crate version | Read it; if it has its own `[package] version =`, bump it; if not, skip |

Concrete sequence:

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. pyproject.toml — confirmed location
grep -n '^version = "1.4.0"' pyproject.toml
# Edit: change to version = "1.4.1"

# 2. poker_solver/__init__.py — verify location of __version__ at ship time
grep -n '__version__' poker_solver/__init__.py
# Edit: change "1.4.0" -> "1.4.1"

# 3. crates/cfr_core/Cargo.toml — check at ship time
grep -n '^version' crates/cfr_core/Cargo.toml
# If it has [package] version = "1.4.0", bump to "1.4.1". Otherwise leave.

# 4. Stage + commit the release bump (DO NOT use git add -A per ship hygiene)
git add CHANGELOG.md pyproject.toml poker_solver/__init__.py
# Conditionally:
# git add crates/cfr_core/Cargo.toml

git status --short    # sanity: only CHANGELOG + version files staged + the cherry-pick already committed

git commit -m "chore(release): v1.4.1 — asymmetric initial contributions (PATCH; W3.4 unblock)"
```

---

## 3. Tag + push sequence

```bash
cd /Users/ashen/Desktop/poker_solver
# Annotated tag with semver message
git tag -a v1.4.1 -m "v1.4.1: asymmetric initial contributions (W3.4 / W2.3 / W1.2 facing-bet)"
# Push main commits (cherry-pick(s) + release commit) — http.postBuffer 524288000 already set
git push origin main
# Push tag
git push origin v1.4.1
# Verify
git fetch --tags origin
git tag -l 'v1.4.1'
git ls-remote --tags origin | grep v1.4.1
git log --oneline origin/main -4
```

---

## 4. GitHub release

```bash
cd /Users/ashen/Desktop/poker_solver
# Pre-stage release notes file (paste-ready)
cat > /tmp/v1.4.1_release_notes.md <<'EOF'
## v1.4.1 — Asymmetric initial contributions (PATCH)

**Headline:** `HUNLPoker.initial_state` now honors `initial_contributions` for
postflop subgames, unblocking three previously-broken persona workflows
(W3.4 BB-defends-MDF, W2.3 KK-vs-c-bet-range, W1.2 JJ-river-bluff-catcher).
The engine no longer segfaults on malformed configs — it raises
`ValueError` with a field name.

### What changed

- **Fix A — `HUNLPoker.initial_state` postflop branch** (`poker_solver/hunl.py`).
  Previously the postflop branch hardcoded `to_call=0`, `cur_player=1`, and
  `street_aggressor=-1` regardless of contributions. Passing
  `initial_contributions=(1000, 500)` to model "P0 c-bet half-pot, P1
  facing" produced an engine state where both players saw `to_call=0` and
  P1 was treated as opening. After the fix:
  - `to_call = max(contributions) - min(contributions)`.
  - `cur_player` = lower-contribution player when `to_call > 0`.
  - `street_aggressor` = higher-contribution player when `to_call > 0`.
  - Symmetric `(500, 500)` unchanged — `to_call=0`, `cur_player=1`,
    `street_aggressor=-1` — preserving all existing fixtures.
- **Fix B — `HUNLConfig.__post_init__` validation**. Raises `ValueError`
  on negative contributions, contributions exceeding `starting_stack`, and
  configs where the facing-bet player has zero stack behind. Previously
  these segfaulted in the Rust backend.

### Persona unblocks (3 of 3 facing-bet workflows)

- **W3.4 (Daniel)** — MDF check: BB defends ≥ 66.7% vs half-pot c-bet.
- **W2.3 (Sarah)** — KK on Q-high flop vs villain's c-bet range.
- **W1.2 (Marcus)** — JJ on As Tc 5d Jh 8s river vs pot-sized bet.

These workflows now execute via the existing `solve()` API; no new public
API surface. See the v1.4.1 entry in `CHANGELOG.md`.

### Honest framing

- PATCH bump: bug fix + robustness guard, no API change.
- Symmetric-baseline diff-tests vs v1.4.0 stay green.
- Rust `_rust.so` is rebuilt; wheel consumers must reinstall to pick up
  the asymmetric-postflop fix on the Rust tier.
- Heavy-lock + asymmetric-contributions interaction not separately
  exercised (each tested in isolation); regressions, if any, would
  surface in v1.4.x persona re-tests.

### Tests

`tests/test_asymmetric_contributions.py` covers symmetric regression,
P1-faces-bet, P0-faces-bet, two invalid-config `ValueError` paths, and
the W3.4 BB-defends-half-pot-c-bet smoke gate (defense in [55%, 80%]).
EOF

# Create the release (Latest)
gh release create v1.4.1 \
  --repo amaster97/poker_solver \
  --latest \
  --title "v1.4.1: Asymmetric Contributions" \
  --notes-file /tmp/v1.4.1_release_notes.md

# Verify
gh release view v1.4.1 --repo amaster97/poker_solver | head -10
```

---

## 5. Auto-retest list — fire immediately after v1.4.1 ships

All three are facing-bet workflows that were structurally blocked pre-v1.4.1.
Spawn one retest agent per workflow (parallel; independent). Each writes a
short pre/post comparison to `docs/pr13_prep/v1_4_1_<workflow>_retest.md`.

| Retest | Persona | Spec line | Expected post-fix |
|---|---|---|---|
| **W3.4 — MDF half-pot c-bet** | Daniel | `persona_acceptance_spec.md` line 59 | BB defended ∈ [55%, 80%] (MDF target ~66.7%). Pre-fix: returned opening strategy with `fold=0.000, call=0.000`. |
| **W2.3 — KK on Q-high vs c-bet range** | Sarah | line 45 | Mixed fold/call/raise strategy with sensible call frequency on KK. Pre-fix: `solve_hunl_postflop` with asymmetric contributions returned engine state with `to_call=0`. |
| **W1.2 — JJ on As Tc 5d Jh 8s vs pot** | Marcus | line 31 | Non-degenerate call frequency, MDF heuristic (~50%) bluff-catch. Pre-fix: workflow blocked entirely. |

Plus two adjacent checks worth queueing in the same wave:

- **W3.5 polarization (monotone flop)** — line 61. Now executable end-to-end since the facing-bet construction is fixed; assert polarized betting range on `Ah 7h 2h`.
- **v1.4.0 Daniel retest re-fire** — `docs/pr13_prep/v1_4_0_daniel_retest.md` already covers W3.1-W3.3 with node-locking; re-run with v1.4.1 build to confirm node-locking + asymmetric contributions don't interact pathologically.

Skip from this retest wave: any workflow without asymmetric contributions (S1-S3 symmetric subgames, push/fold, range-vs-range river RvR) — out of scope for v1.4.1.

---

## 6. Risk callouts (concrete)

**A. Does PR 22 touch `solver.py`?** No — staging snapshot confirms it touches `poker_solver/hunl.py` only on the Python side. No interaction with PR 21's `_solve_rust` signature change. **Conflict risk: nil.**

**B. Does PR 22 touch Rust?** **YES** — `crates/cfr_core/src/hunl.rs`. The Rust port of `initial_state` (or whatever wraps it for the Rust tier) needs the same Fix A. Consequence: **rebuilding `_rust.so` is mandatory before retests** (see step 2c). Stale v1.4.0 `.so` will pass symmetric tests but fail Fix A on the Rust tier, producing false "tests pass" green-lights.

**C. CHANGELOG conflict zone (LEG 9 saw this).** v1.4.0 release added a large `## [1.4.0]` block. The v1.4.1 section must be inserted ABOVE it without touching the v1.4.0 block. Use a real editor (no `sed -i`). After edit, `grep -c '^## \[1.4.0\]' CHANGELOG.md` must still return `1`.

**D. PR 22 worktree branch name vs path.** The worktree path on disk is `/Users/ashen/Desktop/poker_solver_worktrees/pr-22-asymmetric` (NOT `pr-22-asymmetric-contributions` as the user prompt assumed). The BRANCH inside it is `pr-22-asymmetric-contributions`. All step-1 / step-2a commands above use the correct path.

**E. Implementer status at staging.** PR 22 worktree has UNCOMMITTED changes (`M poker_solver/hunl.py`, `M crates/cfr_core/src/hunl.rs`, `?? tests/test_asymmetric_contributions.py`). No commits ahead of main yet. Ship plan fires only after implementer commits + auditor passes. SHAs deliberately left as placeholders.

**F. Symmetric regression.** Proposal §3 case 1 requires `(500, 500)` → `to_call=0, cur_player=1, street_aggressor=-1` to stay bit-identical. If `pytest tests/test_hunl.py` or `pytest tests/test_hunl_solver.py` shows any test value change (not just count), STOP — the fix has perturbed the symmetric baseline and the proposal acceptance criteria are violated.

**G. Tests breaking on stale `.so`.** Any Rust-tier test in `tests/` that exercises postflop subgame construction will silently use the v1.4.0 binary if `maturin develop --release` is skipped. Mandatory rebuild gates this — step 2c is non-negotiable before any pytest invocation in the main tree.

**H. http.postBuffer.** Per session memory, `git config --global http.postBuffer 524288000` is already set; `git push origin main` should not stall on the Rust `.so` LFS situation. If push hangs >60s, kill and retry — do not amend or force.

**I. `crates/cfr_core/Cargo.toml` version.** Not verified at staging time (only root `Cargo.toml` was read; it's a workspace manifest with no version). At ship time, `grep -n '^version' crates/cfr_core/Cargo.toml` to confirm whether the crate has its own `[package] version =`. If yes, bump it. If absent, skip — workspace-versioned crates don't need a per-crate bump.

**J. Push hygiene.** Per `feedback_public_repo_hygiene`, the sanitization scan in step 1b is a HARD gate. Do not push to `origin` if any line matches. The dual-remote workflow (`feedback_dual_remote_workflow`) is N/A here — main is the public-OK channel.

---

## 7. Estimated ship time

Based on LEG 9 (v1.4.0) shipping discipline and matching scope (single PR cherry-pick + release commit + tag + GitHub release + retest spawn):

| Step | Time |
|---|---|
| Pre-flight (§1) — incl. test suite in worktree | 8-15 min (Rust build + pytest -m "not slow" dominates) |
| Cherry-pick + Rust rebuild + validate (§2a-c) | 5-10 min |
| CHANGELOG + version bump + commit (§2d-e) | 3-5 min |
| Tag + push (§3) | 1-2 min |
| GitHub release (§4) | 1-2 min |
| Spawn retest agents (§5) | 2-3 min |
| **Total** | **20-37 min orchestrator + 10-15 min wait on test/build** |

Compare LEG 9 (bundle, two PRs, Daniel persona) ran ~45 min end-to-end; v1.4.1 is single-PR and should run faster. Add 30-60 min for the W3.4 / W2.3 / W1.2 retests to return.

---

## 8. Hard rules (carry-over from LEG 9)

- Autonomous push authorized per `feedback_pr10a5_autonomous_commit` (audit-cleared PRs ship end-to-end).
- DO NOT use `git add -A` or `git add .` in the shared tree — stage by explicit path.
- DO NOT touch `.gitignore` during ship.
- Cherry-pick conflict beyond mechanical → STOP + report (none expected per risk §A).
- DO NOT skip `maturin develop --release` between cherry-pick and any pytest invocation (risk §B/§G).
- DO NOT amend prior v1.4.0 release commit or CHANGELOG block.
- Retest spawn is REQUIRED post-PATCH because the change unblocks NEW workflows (W3.4 / W2.3 / W1.2 were structurally impossible before).
