# LEG 19 — v1.6.1 PATCH Ship Plan (REVISED — PR 33 + PR 34 + PR 40; PR 35 DROPPED)

**Date staged:** 2026-05-23 · **Status:** PRE-STAGED (read-only investigation, plan-only).
**Supersedes:** `docs/leg19_v1_6_1_ship_plan.md` (original 4-PR bundle).
**Revision driver:** `docs/v1_6_1_bundle_bisection_diagnosis.md` Option 1 recommendation —
PR 35 Fix C is the source of the `test_exploit_diff.py::test_fixed_combo_river_single_bet_size_matches` regression; drop PR 35 entirely from v1.6.1.
**Filename:** `docs/leg19_v1_6_1_ship_plan_REVISED.md` (authoritative).

---

## 0. WHAT CHANGED FROM THE ORIGINAL v1.6.1 PLAN

This revision is a narrow surgical edit to the original plan. The change is the bundle composition, the test gate, the release framing, and the v1.6.2 follow-up scope. All execution mechanics (worktree, push, tag, GitHub release, private mirror sync, cleanup) are unchanged.

| Aspect | Original plan | REVISED plan | Source of change |
|---|---|---|---|
| Bundle PRs | PR 33 + PR 34 + PR 35 + PR 40 | **PR 33 + PR 34 + PR 40** (PR 35 DROPPED) | Bisection §"Recommended" Option 1 |
| Cherry-pick order | PR 34 → PR 35 → PR 33 → PR 40 | **PR 34 → PR 33 → PR 40** | PR 35 removed; PR 33 advances |
| `test_exploit_diff.py` gate | Implicit (passes) | **Explicit gate, must be 5/5 PASS** | Bisection §H1: PR 35-free composition is regression-free |
| Acceptance test §5a outcome | "2/2 PASS — THE gate" | **EXPECTED FAIL on coverage (K72 53.3% / A83 66.7%); NOT a ship gate** | Bisection §test-C result |
| §6b CHANGELOG framing | "Brown apples-to-apples empirically PASSES" | **"PR 34 P0 panic fixed; Brown acceptance still failing on coverage + per-action parity — deep-cap algorithmic bug in `dcfr_vector.rs` deferred to v1.6.2"** | Bisection §"Honest framing" |
| §8 release notes headline | "Acceptance test now PASSES" | **"P0 panic fix + Python delegate + test plumbing fix; acceptance test still failing — deeper algorithmic work queued for v1.6.2"** | Bisection §"Honest framing" Option 1 variant |
| Cascading retest queue (§10) | "Wave 1 expected to PASS via PR 33" | **"Wave 1 expected PARTIAL — W2.3/W3.4/W4.3 unblock via PR 33 perf path but may still fail acceptance-grade quality at deep-cap nodes per PR 23 algorithmic gap"** | Bisection §H3 + Marcus persona budget |
| Maturin rebuild | MANDATORY (PR 34 + PR 35 touch Rust) | **MANDATORY** (PR 34 touches Rust; PR 35 dropped but PR 34 is sufficient on its own) | unchanged trigger; reduced surface |
| Cherry-pick conflict risk | PR 34 + PR 35 both touch `dcfr_vector.rs` (medium-low) | **PR 33+34+40 disjoint Rust paths; PR 40 was authored on v1.5.1 base without PR 35 — clean cherry-pick** | Per file overlap analysis (§2c) |
| v1.6.2 scope | Not specified (held for "deep-cap follow-up") | **PR 35 Fix A (keep) + Fix B (keep) + Fix C-Python-side (NEW work) + deep-cap algorithmic-triage fix for `dcfr_vector.rs`** | Bisection §H1/H3 |

The legitimate v1.6.1 surface is therefore: P0 Rust panic fix, Python delegate convenience, and test-side encoding bugfix. The release does NOT claim Brown apples-to-apples = GREEN.

---

## 1. Bundle composition (REVISED)

> **Branches bundled (cherry-pick order):**
>
> 1. **PR 34** `pr-34-p0-off-by-one` @ `0bafcfac` — Rust off-by-one fix in opponent-branch reach (`dcfr_vector.rs`). Small, contained. Empirically validated by bisection §H2.
> 2. **PR 33** `pr-33-python-delegate` @ `29a00c0` — Python auto-delegate to Rust vector-form CFR when `initial_hole_cards=()` (530 LOC). Innocuous on acceptance path (bisection §H4).
> 3. **PR 40** `pr-40-acceptance-test-fix` @ `c058e97` — semantic action mapping fix + range-to-player-slot swap fix + tolerance loosened to 2e-2 (originally adjusted with PR 35 in scope; relevant fixes are self-contained in PR 40's diff — see §2c below).
>
> **NOT IN THE v1.6.1 BUNDLE:**
>
> - **PR 35** `pr-35-canonicalization` @ `33e03ea` — DROPPED. Three sub-fixes:
>   - **PR 35 Fix A (test renderer `stack_ceiling` for ALL_IN token)** — load-bearing for K72/A83 coverage per bisection §test-B/§test-C; KEEP for v1.6.2.
>   - **PR 35 Fix B (player-index inversion in test)** — semantically equivalent to PR 40's existing player-slot swap; redundant or KEEP for v1.6.2 depending on which form is canonical.
>   - **PR 35 Fix C (Rust engine `enumerate_legal_actions` skips ALL_IN at cap)** — REVERT until Python `action_abstraction.py:236-237` is updated to match. This is the source of the v1.6.1-bundle regression.

**Confirmed at stage time:**

```
$ git log --oneline pr-33-python-delegate -1
29a00c0 Add Python delegate for initial_hole_cards=() (task #182)

$ git log --oneline pr-34-p0-off-by-one -1
0bafcfac PR 34: Fix off-by-one panic at dcfr_vector.rs:651 (PR 23 P0)

$ git log --oneline pr-40-acceptance-test-fix -1
c058e97 PR 40: fix test-side encoding bugs in Brown apples-to-apples acceptance

# DROPPED:
# 33e03ea pr-35-canonicalization — explicitly NOT cherry-picked into v1.6.1
```

**Bump:** PATCH (1.6.0 → 1.6.1). Reason: P0 panic fix (PR 34) + backwards-compatible auto-delegate (PR 33) + test plumbing fix (PR 40). No new user-visible features. Semver PATCH is the correct slot.

---

## 1a. Why drop PR 35 entirely (vs. split per Option 2)?

The bisection identified PR 35 Fix C as the source of `test_exploit_diff` regression and noted "Option 2: split PR 35" as a more surgical alternative. We choose Option 1 (drop all of PR 35) over Option 2 (drop only Fix C) because:

1. **PR 40 already carries semantically-equivalent player-slot fixes** (see §2c file overlap analysis). PR 35 Fix B in the per-action loop (`rust_player = 1 - player` at lookup) is functionally identical to PR 40's `for brown_player in (0, 1): rust_player = 1 - brown_player`. Inverting at the slot-assignment site (PR 40, line ~514: `p0_holes = _spot_hand_ids(spot, 1)`) plus inverting at the lookup site (PR 40, line ~597) is internally consistent. Adding PR 35 Fix B on top would cause a *double inversion* and break the per-action match.
2. **PR 35 Fix A (renderer `stack_ceiling`) is independently shippable.** It can re-enter v1.6.2 cleanly with no dependency on Fix C.
3. **Dropping all of PR 35 minimizes the cherry-pick conflict surface** with PR 40, which was authored on v1.5.1 (a base that doesn't include any of PR 35).
4. **Honest scope discipline.** Even with PR 35 Fix A in place, the acceptance test still fails 22-42pp on per-action parity (bisection §H3). Shipping PR 35 Fix A under v1.6.1 would not move the headline metric — we'd still need to disclaim "Brown apples-to-apples = STILL FAILING". So Option 1's smaller release surface is cleaner and the v1.6.2 work can bundle Fix A + the deep-cap algorithmic fix together.

---

## 0a. Hard rules in force on this plan doc (unchanged from original)

- This file is READ-ONLY guidance. Ship agent at ship-time executes the steps; this doc does not.
- DO NOT cherry-pick anything, DO NOT push, DO NOT tag during plan authoring.
- All SHAs in this plan are CONFIRMED at stage time (no placeholders).
- Per `feedback_no_concurrent_branch_ops`: use a dedicated `ship-v1.6.1` worktree.
- Per `feedback_public_repo_hygiene`: sanitization scan §1d gates every cherry-pick before push.

---

## 2. Ship worktree setup + cherry-pick sequence (REVISED order)

### 2a. Create ship worktree (unchanged)

```bash
cd /Users/ashen/Desktop/poker_solver
git fetch origin
git worktree add /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.1 -b ship-v1.6.1 origin/main
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.1
git log --oneline -3
```

### 2b. Cherry-pick order — PR 34, PR 33, PR 40 (REVISED — PR 35 DROPPED)

Order rationale (revised):

1. **PR 34 first** — small, contained Rust fix; matches bisection's test-B/test-C order; no test-file conflict.
2. **PR 33 second** — 530 LOC Python delegate; no conflict with PR 34 (disjoint files); needs PR 34 in the tree so the rebuilt `_rust.so` has the asymmetric-range panic fix.
3. **PR 40 third** — the test fix; cherry-picks against a tree that has PR 33 + PR 34 but not PR 35. PR 40 was authored on v1.5.1 base (no PR 35 in tree); the cherry-pick should be clean. Bisection §test-C confirmed this exact composition cherry-picks cleanly.

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.1

# Step 1: PR 34
git cherry-pick pr-34-p0-off-by-one
git log --oneline -2

# Step 2: PR 33
git cherry-pick pr-33-python-delegate
git log --oneline -3

# Step 3: PR 40
git cherry-pick pr-40-acceptance-test-fix
git log --oneline -4
```

If any cherry-pick stops with a conflict marker: STOP + report. Likely culprit is a same-file edit between PRs.

### 2c. Conflict expectation — file overlap analysis (REVISED with empirical data)

File-level overlap audit (vs. shared origin/main base = v1.6.0):

| PR | Changed paths |
|---|---|
| PR 34 | `crates/cfr_core/src/dcfr_vector.rs` |
| PR 33 | `poker_solver/__init__.py` (delegate), `tests/test_python_delegate.py` (new) |
| PR 40 | `tests/test_v1_5_brown_apples_to_apples.py` |

**Intra-bundle file overlap:** NONE. PR 34 touches Rust, PR 33 touches Python entry + new test file, PR 40 touches a different test file. Cherry-picks are order-independent on file-level.

**PR 40 vs. dropped PR 35 conflict risk:** PR 35 and PR 40 BOTH modify `tests/test_v1_5_brown_apples_to_apples.py`. PR 40 was authored on `b5777f22` (v1.5.1) which does NOT include PR 35. Inspecting PR 40's diff:

- PR 40's player-slot swap is at the slot-assignment site (`p0_holes = _spot_hand_ids(spot, 1)`); PR 35 Fix B is at the lookup site (`rust_player = 1 - player`). They are *semantically equivalent* (both result in Brown's P0 opener ↔ Rust's P1 opener mapping) but at *different locations*. PR 40 ALSO adds `rust_player = 1 - brown_player` at the lookup site in its own per-action loop refactor. So PR 40 ALREADY contains a Fix-B-equivalent.
- PR 40 does NOT carry PR 35 Fix A (the renderer `stack_ceiling` for ALL_IN token). The renderer in PR 40's tree still emits `b{chips}` / `r{amt}` only, never `A`. **This is what causes the post-v1.6.1 acceptance test to fail on coverage (K72 53.3% / A83 66.7% per bisection §test-C).**
- PR 40 carries PR 40's own action permutation logic (`_brown_to_rust_action_permutation`) that PR 35 does NOT have.

Empirical conflict status (per bisection): the cherry-pick sequence PR 34 → PR 33 → PR 40 applied cleanly with no conflicts in test-C (`docs/v1_6_1_bundle_bisection_diagnosis.md` §"Test C"). No manual resolution needed.

**Hard expectation: zero conflicts during cherry-pick.**

---

## 3. Conflict detection vs. v1.6.0 / v1.5.1 (REVISED CHANGELOG section)

**Expected v1.6.0 added/changed files** (from LEG 18): UI + charts + UI smokes + CHANGELOG/version bump. Disjoint from this bundle's surface.

**Cross-base conflict surface:** `CHANGELOG.md` mechanical conflict (v1.6.0 added a `## [1.6.0]` block; PR 33/34/40 likely each have their own placeholder for `## [Unreleased]`). Resolve by accepting v1.6.0's CHANGELOG and adding the v1.6.1 entry fresh per §6b below.

**Conflict expectation: NONE on engine/test paths; mechanical CHANGELOG conflict expected and easy to resolve.**

---

## 4. Maturin rebuild — MANDATORY (unchanged trigger)

PR 34 touches Rust source. The `_rust.cpython-313-darwin.so` shipped with v1.6.0 is byte-stale and MUST be rebuilt.

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.1
PATH=$HOME/.cargo/bin:$PATH maturin develop --release --target universal2-apple-darwin

# Verify
python -c "from poker_solver import _rust; print('rust binding OK', _rust.__file__)"
```

**Rebuild time budget:** ~5-8 min on M2 Pro (universal2 cross-compile).

**Failure modes (unchanged from original):** Cargo lock mismatch → `cargo update -p <crate>`; universal2 toolchain missing → fall back to native-arch and document.

---

## 5. Smoke tests in ship worktree (REVISED — acceptance test EXPECTED to fail)

Per LEG 14: prefer `python -m pytest` over the pyenv `pytest` shim.

### 5a. Acceptance test — EXPECTED FAIL, NOT a ship gate

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.1
python -m pytest tests/test_v1_5_brown_apples_to_apples.py -v -m parity_noambrown -o "addopts="
```

**Expected outcome (per bisection §test-C):** **2/2 FAIL on coverage.**

- `dry_K72_rainbow`: coverage 53.3% (16/30 < 80% floor). Cause: PR 35 Fix A (renderer `stack_ceiling`) is intentionally not in v1.6.1.
- `dry_A83_rainbow`: coverage 66.7% (28/42 < 80% floor). Same cause.

**This is EXPECTED and not a ship-blocker for v1.6.1.** It is documented as a known gap deferred to v1.6.2. Do NOT use this test result as a gate.

**Per memory rule `feedback_research_first_failure_protocol`:** the failure is not a regression — the test was already failing on v1.5.0 baseline (test-A in the bisection also failed K72 coverage at 53.3%). v1.6.1 does not make it worse; it just doesn't fix it.

### 5b. Real ship gate — bundle test set (PR 35-free composition is regression-free)

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.1
python -m pytest tests/test_python_delegate.py \
                 tests/test_range.py \
                 tests/test_dcfr_diff.py \
                 tests/test_exploit_diff.py \
                 tests/test_range_vs_range_aggregator.py \
                 tests/test_node_locking.py -v
```

**Expected: all green, 5/5 on `test_exploit_diff.py` including `test_fixed_combo_river_single_bet_size_matches` (the regression detector — bisection §test-C confirmed PASS in this exact composition).**

**This IS the ship gate.** If `test_fixed_combo_river_single_bet_size_matches` fails: STOP — something in the cherry-pick sequence drifted from the bisection-validated PR 33+34+40 composition.

### 5c. Regression sweep (recommended for confidence)

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.1
python -m pytest tests/ -v -k 'not slow and not parity_noambrown' --ignore=tests/test_v1_5_brown_apples_to_apples.py
```

**Expected: all non-slow non-parity-Brown tests pass.**

### 5d. UI smoke regression (unchanged)

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.1
python -m pytest tests/test_ui_smoke.py tests/test_ui_pr24a.py tests/test_ui_pr24b.py -v
```

**Expected: 44/44 green.**

---

## 6. Version bump + CHANGELOG (REVISED — honest framing)

### 6a. Files to bump (unchanged from original)

| File | Current | New |
|---|---|---|
| `pyproject.toml` | `version = "1.6.0"` | `version = "1.6.1"` |
| `poker_solver/__init__.py` | `__version__ = "1.6.0"` | `__version__ = "1.6.1"` |
| `crates/cfr_core/Cargo.toml` | check at ship time | bump patch if it tracks |

### 6b. CHANGELOG.md — REVISED entry (honest framing, public-OK)

Open `/Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.1/CHANGELOG.md`. Insert NEW `## [1.6.1]` section between `## [Unreleased]` and `## [1.6.0]`.

```markdown
## [1.6.1] - 2026-05-23

### Engine — P0 panic fix + Python delegate

- **Rust opponent-branch reach off-by-one fix (PR 34).** `dcfr_vector.rs` opponent-branch `reach_opp` was sized using `opp_hands` instead of `player_hands`. Fixed; matches Brown's `cpp/src/trainer.cpp:170-173`. Eliminates the index-out-of-bounds panic on asymmetric hand-set sizes (49 vs 50) that triggered on `dry_A83_rainbow`-class spots.
- **Python -> Rust auto-delegate (PR 33).** `solve_hunl_postflop(initial_hole_cards=())` now auto-routes to vector-form Rust CFR when `backend="auto"`. Closes the chance-enum-at-root Python perf cliff for range-vs-range queries. New optional `tests/test_python_delegate.py` covers the delegate routing.

### Acceptance test plumbing — partial fix (test side only)

- **Semantic action mapping + player-slot swap (PR 40).** Brown apples-to-apples acceptance test now:
  - Maps Brown's `[c, f, r_low, r_med, r_jam]` to Rust's `[f, c, r_low, r_med, A]` by semantic action identity (not position-by-position; the pre-fix harness silently lined up Brown's CALL with Rust's FOLD).
  - Passes ranges in the correct player slots (Brown's P0 opener ↔ Rust's P1 opener per `poker_solver/hunl.py:286-289`).
  - Tolerance loosened to 2e-2 from 5e-3 (in anticipation of legitimate Nash polytope sizing-mix non-uniqueness — see KNOWN GAP below).

### KNOWN GAP — Brown apples-to-apples acceptance test STILL FAILS

The Brown apples-to-apples acceptance test (`tests/test_v1_5_brown_apples_to_apples.py`, opt-in via `-m parity_noambrown`) STILL FAILS on both `dry_K72_rainbow` and `dry_A83_rainbow` after this release. The failure has two layers:

1. **Coverage floor (53.3% / 66.7% < 80%):** the test history renderer does not yet emit the `A` token for ACTION_ALL_IN at the stack ceiling. A test-renderer fix is queued for **v1.6.2** (alongside the deeper engine fix below).
2. **Per-action parity (22-42pp divergence at deep-cap facing-bet nodes):** the Rust vector-form CFR exhibits over-folding and under-calling at high-stakes facing-bet decision nodes vs. Brown's reference. This is a real algorithmic gap in `crates/cfr_core/src/dcfr_vector.rs` not closed by v1.6.1. A focused algorithmic-triage pass on the Rust DCFR vs. Brown's `cpp/src/trainer.cpp:138-209` recursive-update loop is queued for **v1.6.2**.

The PR 34 fix (this release) closes the P0 panic that was masking the deeper bug; v1.6.2 will address the deep-cap algorithmic divergence.

### Honest scope

- PATCH bump: bug fix (P0 panic) + backwards-compatible auto-delegate + test plumbing. No public CLI/API signature changes; no behavior change for callers who don't opt into `initial_hole_cards=()`.
- Maturin rebuild is required (PR 34 touches Rust source). Users upgrading from v1.6.0 must `pip install --upgrade` to pick up the rebuilt wheel.
- The headline "Brown apples-to-apples = GREEN" claim is **NOT** made by this release. v1.6.2 carries the remainder of the apples-to-apples acceptance work.
```

### 6c. Commit the release bump (unchanged mechanics)

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.1
git add CHANGELOG.md pyproject.toml poker_solver/__init__.py
# Conditionally: git add crates/cfr_core/Cargo.toml
git status --short
git commit -m "chore(release): v1.6.1 — P0 panic fix + Python delegate + test plumbing (PR 33+34+40)"
git log --oneline -5
```

Expected: 3 cherry-picks + 1 release bump on top of v1.6.0 (4 new commits total on `ship-v1.6.1`).

---

## 7. Tag + push sequence (unchanged mechanics, REVISED expected delta)

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.1

# Annotated tag
git tag -a v1.6.1 -m "v1.6.1: P0 panic fix + Python delegate + test plumbing"

# Push main commits — fast-forward expected (4 new commits, not 5)
git push origin HEAD:main

# Push tag
git push origin v1.6.1

# Verify
git fetch --tags origin
git tag -l 'v1.6.1'
git ls-remote --tags origin | grep v1.6.1
git log --oneline origin/main -5
```

Expected: `origin/main` advances by **4** commits (3 cherry-picks + 1 release bump). Tag `v1.6.1` is annotated and points to the release-bump commit.

---

## 8. GitHub release (REVISED — honest framing)

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.1

cat > /tmp/v1.6.1_release_notes.md <<'EOF'
## v1.6.1 — P0 panic fix + Python delegate + test plumbing (PATCH)

**Headline:** A PATCH release bundling a P0 Rust panic fix, a Python auto-delegate for the range-vs-range path, and a test-side encoding fix for the Brown apples-to-apples acceptance test. The acceptance test itself does **not** yet pass — a deeper algorithmic gap at deep-cap facing-bet nodes in the Rust vector-form CFR is queued for v1.6.2.

### What changed

- **Rust opponent-branch reach off-by-one fix (PR 34).** `dcfr_vector.rs` opponent-branch `reach_opp` was sized using `opp_hands` instead of `player_hands`, causing an index-out-of-bounds panic on asymmetric hand-set sizes (e.g. 49 vs 50). Fixed; matches Brown's `cpp/src/trainer.cpp:170-173`.

- **Python -> Rust auto-delegate (PR 33).** `solve_hunl_postflop(initial_hole_cards=())` now auto-routes to vector-form Rust CFR when `backend="auto"`. Closes the chance-enum-at-root Python perf cliff for range-vs-range queries. The Python entry preserves its public signature; new behavior is opt-in via the empty-hole-cards path.

- **Acceptance test encoding fix (PR 40).** The Brown apples-to-apples acceptance test now uses semantic action mapping (Brown `[c, f, r_low, r_med, r_jam]` ↔ Rust `[f, c, r_low, r_med, A]`) and passes ranges in the correct player slots (Brown's P0 ↔ Rust's P1 by opener role). Tolerance loosened from 5e-3 to 2e-2 in anticipation of Nash polytope sizing-mix non-uniqueness.

### Known gaps NOT closed by this release

- The Brown apples-to-apples acceptance test (`-m parity_noambrown`) **still fails** on both `dry_K72_rainbow` and `dry_A83_rainbow`:
  - **Coverage:** the test history renderer does not yet emit `A` for ACTION_ALL_IN at the stack ceiling, dropping K72 coverage to 53.3% and A83 to 66.7% (< 80% floor). Renderer fix queued for v1.6.2.
  - **Per-action parity:** the Rust vector-form CFR exhibits 22-42pp divergence vs. Brown's reference at deep-cap facing-bet nodes (Rust over-folds, under-calls). This is a real algorithmic gap in `crates/cfr_core/src/dcfr_vector.rs`, not test plumbing. A focused algorithmic-triage pass on the Rust DCFR vs. Brown's `cpp/src/trainer.cpp:138-209` recursive-update loop is queued for v1.6.2.

v1.6.1 ships the test plumbing fix and the P0 panic fix in advance of the v1.6.2 algorithmic fix to make the v1.6.2 triage cycle clean (P0 panic was masking the deeper bug).

### Honest scope

- PATCH bump: bug fix + backwards-compatible auto-delegate + test plumbing. No public CLI/API signature changes.
- Maturin rebuild is required (PR 34 touches Rust). Users upgrading from v1.6.0 must `pip install --upgrade` to pick up the rebuilt wheel.
- This release does **not** claim Brown apples-to-apples = GREEN. That claim is targeted for v1.6.2.

EOF

gh release create v1.6.1 \
  --repo amaster97/poker_solver \
  --latest \
  --title "v1.6.1: P0 panic fix + Python delegate + test plumbing" \
  --notes-file /tmp/v1.6.1_release_notes.md

# Verify
gh release view v1.6.1 --repo amaster97/poker_solver | head -12
```

**Public-OK audit (per `feedback_public_repo_hygiene`):**

- No `/Users/ashen/...` paths in release notes.
- No session IDs, no PII, no `claude-session` / `claude_ai_*` references.
- No private-mirror-only diagnostics surfaced (the "v1.6.2 triage" framing is forward-looking and public-OK).
- Honest about the gap; no false claims about Brown acceptance status.

---

## 9. Cleanup (unchanged from original)

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.1
cd /Users/ashen/Desktop/poker_solver
git worktree remove /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.1
git worktree list
```

Do NOT force-delete `ship-v1.6.1` branch with `-D` (per `feedback_no_concurrent_branch_ops`).

### Optional: catch up shared tree
```bash
cd /Users/ashen/Desktop/poker_solver
git pull --ff-only origin main
```

### Downstream impact (unchanged from original except retest framing)

- **PR 10b UI bindings** — v1.6.1 does not change UI surface; no PR 10b re-audit required.
- **PR 11 .dmg rebuild** — engine-touching PRs SHOULD trigger a .dmg rebuild; kick PR 11 to repackage after v1.6.1 lands. Universal2 build mandatory.
- **Persona retest** — partial unblock via PR 33 perf path (see §10 REVISED).

### Private-mirror sync (unchanged from original)

```bash
cd /Users/ashen/Desktop/poker_solver
git push integration main
git push integration v1.6.1
```

Per `feedback_post_integration_verification`: run the dual-channel routing audit after the push.

---

## 10. Cascading retest queue — REVISED (partial improvement, not full PASS)

Per `feedback_persona_test_rectification` + bisection §H3.

**Wave 1 (immediately post-v1.6.1):** the 3 BLOCKED workflows that PR 33 unblocks AT THE PERF LEVEL — but acceptance-grade strategy quality may still fall short of persona budgets due to PR 23 deep-cap algorithmic gap.

| Workflow | Pre-v1.6.1 status | Expected v1.6.1 outcome | Caveat |
|---|---|---|---|
| W4.3 Marcus RvR jam-or-fold | BLOCKED (Python perf cliff) | UNBLOCKED for execution; strategy quality TBD | Marcus persona budget per `feedback_persona_time_budgets`. Jam-or-fold spot is high-stakes (likely a deep-cap node); may exhibit the 22-42pp divergence. |
| W3.4 Sarah board-texture range equity | BLOCKED (perf cliff on equity audit substep) | UNBLOCKED; substep should succeed | Equity audit is a coverage substep, not strategy parity; expected to pass on perf alone. |
| W2.3 Generic blueprint RvR | BLOCKED (no API entrypoint) | UNBLOCKED via PR 33 delegate | Generic spot; if it lands at deep-cap node, expect partial divergence. |

**Honest framing:** Wave 1 is expected to produce **partial improvements**, not a full PASS cascade. The 3 workflows unblock on perf and API surface, but the per-action quality at deep-cap nodes may still trip persona acceptance bars. Classify findings via memory rule `feedback_persona_test_rectification` (Type A/B/C-CRITICAL/C-USEFUL/C-NICE/D). Type B/C-CRITICAL findings at deep-cap nodes are EXPECTED and should route into v1.6.2 scope, not be treated as v1.6.1 regressions.

**Wave 2 (post-Wave 1):** in-flight retests from previous wave (W3.5 Sarah RvR strategic, W1.2 Marcus deep-stack). May reveal partial improvements from PR 34 panic fix in asymmetric-range paths.

**Wave 3 (final sweep):** held UNTIL v1.6.2 lands. Running Wave 3 against v1.6.1 prematurely would surface known gaps as Type A findings, wasting persona budget. Defer Wave 3 to post-v1.6.2.

---

## 11. v1.6.2 SCOPE — deep-cap fix + PR 35 reconstitution

Per bisection §H1/§H3 + memory rule `feedback_research_first_failure_protocol` ("research existing solvers/papers BEFORE surfacing; override is last resort; rigorous testing throughout").

### 11a. v1.6.2 bundle (provisional)

1. **PR 35-A revived:** test renderer `stack_ceiling` for ALL_IN token (`tests/test_v1_5_brown_apples_to_apples.py::_rust_history_substr_for_canonical`). Load-bearing for K72/A83 coverage (bisection §test-B confirmed 53.3%→100% jump on K72 with Fix A in tree).
2. **PR 35-B reviewed (likely REDUNDANT, possibly DROP):** PR 40 already carries semantically-equivalent player-slot fixes. Confirm via inspection: if PR 35-B duplicates PR 40 fixes, drop PR 35-B from v1.6.2 to avoid double-inversion. If PR 35-B fixes a third site PR 40 missed, keep.
3. **PR 35-C revived ONLY WITH MATCHING PYTHON FIX (new work).** Currently PR 35 Fix C modifies Rust `enumerate_legal_actions` to skip ACTION_ALL_IN at cap, but Python `poker_solver/action_abstraction.py:236-237` still emits ALL_IN unconditionally. The fix is twofold:
   - **(C-rust)** keep PR 35's `crates/cfr_core/src/hunl.rs:1136-1144` edit: `if ctx.include_all_in && !cap_reached`.
   - **(C-python)** edit `poker_solver/action_abstraction.py:236-237` to mirror: add `if not cap_reached` guard to the ACTION_ALL_IN push. This is NEW work, not in any existing PR branch.
   - **Verify:** post-edit, `test_exploit_diff.py::test_fixed_combo_river_single_bet_size_matches` MUST pass with delta < 1e-6 (proving Python-Rust parity).
4. **Deep-cap algorithmic-triage fix (NEW PR).** Focused triage on `crates/cfr_core/src/dcfr_vector.rs` vs `cpp/src/trainer.cpp:138-209`. Hypothesis candidates from bisection §H3:
   - Incorrect regret accumulation on FOLD at deep-cap nodes (fold = give up pot equity, not "lose remaining stack").
   - Mis-scaled DCFR alpha-discount on positive regrets at cap nodes.
   - Mis-attributed terminal utility on the "fold by opponent" branch.
   - Triage agent should use K72 worst-cell from `docs/v1_6_1_staged_acceptance_verification.md` §4 as the reproducer, and compare line-by-line vs Brown's recursive update loop.
5. **Tolerance reassessment.** PR 40's loosening to 2e-2 may be unnecessary once the deep-cap fix lands; tighten back to 5e-3 if the algorithm fix closes the gap.

### 11b. v1.6.2 gate

- `test_exploit_diff.py::test_fixed_combo_river_single_bet_size_matches` MUST pass (proves PR 35 Fix C + Python fix are in parity).
- `tests/test_v1_5_brown_apples_to_apples.py` MUST pass on both spots at the 5e-3 tolerance (proves coverage + per-action parity).
- All other tests green vs. v1.6.1 baseline.

### 11c. v1.6.2 scope discipline

Per memory rule `feedback_continuous_pruning` and `feedback_research_first_failure_protocol`: do NOT bundle UI changes, new features, or non-acceptance work into v1.6.2. Keep it narrow: re-revive the PR 35 sub-fixes + algorithm triage + parity validation only.

---

## 12. Estimated ship time (REVISED — one fewer PR + lighter conflict surface)

| Step | Time (original 4-PR estimate) | Time (REVISED 3-PR estimate) |
|---|---|---|
| Pre-flight (§1) | 3-5 min | 2-4 min (one fewer SHA to verify) |
| Ship worktree setup (§2a) | 1 min | 1 min |
| Cherry-pick 4 → 3 PRs (§2b) | 2-3 min | 1-2 min (one fewer pick; zero conflicts expected) |
| Maturin rebuild (§4) | 5-8 min | 5-8 min (PR 34 alone is still a Rust rebuild) |
| Acceptance test (§5a) — EXPECTED FAIL | 3-5 min | 3-5 min |
| Bundle test set (§5b) — THE gate | 2-3 min | 2-3 min |
| Regression sweep + UI smoke (§5c/d) | 5-7 min | 5-7 min |
| Version bump + CHANGELOG (§6) | 3-5 min | 3-5 min (REVISED CHANGELOG is shorter) |
| Tag + push (§7) | 1-2 min | 1-2 min |
| GitHub release (§8) | 1-2 min | 1-2 min |
| Cleanup (§9) | <1 min | <1 min |
| Private-mirror sync | 1 min | 1 min |
| **Total** | **27-43 min** | **25-40 min** |

---

## 13. Risk register (REVISED)

| Risk | Probability | Mitigation |
|---|---|---|
| PR 40 SHA drifts since stage time | Low | SHA captured at stage time: `c058e97`. Re-verify at ship trigger. |
| LEG 18 (v1.6.0) hasn't landed | Low | §1a Case-B fallback: STOP and wait for v1.6.0. |
| Cherry-pick conflict (REVISED) | Very low | Per §2c file overlap analysis: PR 33+34+40 are disjoint at file level. Bisection §test-C empirically confirmed clean cherry-picks. |
| Maturin rebuild fails | Low | Native-arch fallback. |
| `test_exploit_diff` regression on PR 35-free composition | Very low | Bisection §test-C empirically confirmed 5/5 PASS in this exact composition. |
| Acceptance test "fail" mistaken for ship-blocker | Medium | §5a documented as EXPECTED fail with explicit instruction not to gate on it. Ship report (§14) must explicitly note this. |
| Persona retest interprets deep-cap divergence as v1.6.1 regression | Medium | §10 REVISED documents the partial-improvement expectation; retest rubric should route Type B findings to v1.6.2 scope, not block v1.6.1. |
| User reads release notes and expects Brown acceptance = GREEN | Low | §8 release notes explicitly disclaim. CHANGELOG entry has explicit "KNOWN GAP" section. |
| Sanitization scan surfaces new PII | Low | §1d hard gate STOPs the push. |
| Tag v1.6.1 already exists | Nil | Fresh tag slot. |
| Cross-base conflict on CHANGELOG.md | High (mechanical) | Expected; resolve manually. |
| v1.6.2 work delays indefinitely if v1.6.1 ships without algorithmic fix | Medium | §11 v1.6.2 scope is explicit. Persona retest queue (§10) Wave 3 deferral is the forcing function. |

---

## 14. Output: ship report (REVISED template)

After ship, the ship agent writes `/Users/ashen/Desktop/poker_solver/docs/leg19_v1_6_1_ship_report.md`:

- §1 Release artifacts (tag SHA, release URL, previous release v1.6.0, commits-on-main delta = **4**, not 5)
- §2 Execution timeline
- §3 Cherry-pick verification (source SHA → new commit SHA per PR; **expected zero conflicts** per bisection §test-C)
- §4 Maturin rebuild verification
- §5 Smoke test results:
  - §5a Acceptance test: **2/2 FAIL on coverage** (EXPECTED; documented as deferred to v1.6.2)
  - §5b Bundle test set: ALL GREEN (THE ship gate); 5/5 on `test_exploit_diff.py`
  - §5c Regression sweep: ALL GREEN
  - §5d UI smoke: 44/44 GREEN
- §6 Version bump verification
- §7 Honest framing in CHANGELOG + release notes (v1.6.1 ships partial fix; v1.6.2 owns the algorithmic close-out)
- §8 Cleanup status
- §9 Cascading retest queue Wave 1 trigger (with partial-improvement expectation framing)
- §10 v1.6.2 scope handoff: explicit ticket-style list of work items (PR 35-A revival, PR 35-C-rust+python pair, deep-cap algorithmic triage)
- §11 Unexpected complexity (expected: none; bisection pre-validated this exact composition)

---

## 15. Authorization & per-PR branch hygiene (unchanged mechanics)

Per `feedback_pr10a5_autonomous_commit`: PRs 33, 34, 40 are audit-cleared per bisection §test-C empirical validation. Autonomous end-to-end ship is within scope.

**Exception conditions (require escalation):**

- Cherry-pick conflict that requires non-mechanical resolution → escalate.
- `test_exploit_diff.py` regression in §5b (would indicate cherry-pick drift from bisection-validated composition) → escalate.
- Maturin rebuild fails on both universal2 AND native-arch → escalate.
- Sanitization scan §1d surfaces unexpected PII → escalate.
- Persona retest Wave 1 surfaces Type C-CRITICAL finding NOT attributable to known deep-cap gap → escalate to v1.6.2 prioritization decision.

Per `feedback_pr_branch_hygiene`: source feature branches `pr-33-python-delegate`, `pr-34-p0-off-by-one`, `pr-40-acceptance-test-fix` remain clean on public origin. PR 35 (`pr-35-canonicalization`) remains intact for v1.6.2 reuse — DO NOT delete.

Per `feedback_dual_remote_workflow`: this plan covers both public `origin` push AND private `integration` mirror sync.

---

## 16. SUMMARY — what this revision changes vs. original plan

| Section | Original | REVISED |
|---|---|---|
| §1 Bundle PRs | 4 (PR 33+34+35+40) | **3 (PR 33+34+40)** |
| §2b Cherry-pick order | PR 34 → 35 → 33 → 40 | **PR 34 → 33 → 40** |
| §5a Acceptance test | "2/2 PASS — THE gate" | **"2/2 FAIL EXPECTED — NOT a gate"** |
| §5b Bundle test set | Generic green | **Explicit `test_exploit_diff` 5/5 gate** |
| §6b CHANGELOG | "Brown acceptance PASSES" | **"Brown acceptance STILL FAILS — known gap, v1.6.2 owns"** |
| §8 Release notes | Headline "PASSES" | **Headline "P0 + delegate + plumbing; algorithm work queued for v1.6.2"** |
| §10 Persona retest | "Full PASS cascade expected" | **"Partial improvement expected; defer Wave 3 to post-v1.6.2"** |
| §11 v1.6.2 scope | Implicit | **Explicit: PR 35-A revival + PR 35-C dual fix (Rust + Python) + deep-cap algorithmic triage** |
| §12 Time | 27-43 min | **25-40 min** |
| Risk register | Acceptance test fail = STOP | **Acceptance test fail = EXPECTED; ship proceeds on bundle gate (§5b)** |

The execution mechanics (worktree, push, tag, GitHub release, private-mirror sync, cleanup, authorization) are unchanged. The change is entirely in (a) bundle composition, (b) test gate logic, (c) honest framing of what ships, and (d) v1.6.2 scope.
