# v1.6.1 Merge Sequence — Prep (Pre-Ship)

**Date:** 2026-05-23 (late)
**Status:** PREP — read-only inventory + sketched sequence. **DO NOT EXECUTE THIS PLAN FROM THIS DOC.** Ship happens in a follow-up agent.
**Authoritative composition source:** `docs/v1_6_1_final_synthesis.md` §2 (which supersedes the earlier
`docs/leg19_v1_6_1_ship_plan_REVISED.md` 3-PR drop-all-of-PR-35 plan).

---

## 1. Bundle composition — CONFIRMED

```
v1.6.1 = PR 33 + PR 34 + PR 35-A + PR 35-B + PR 40
       (DROP PR 35-C only; defer PR 45)
```

The earlier REVISED ship plan (`leg19_v1_6_1_ship_plan_REVISED.md`) dropped all of PR 35; the
later **final synthesis** (`v1_6_1_final_synthesis.md`) keeps PR 35 Fix A + Fix B and drops only
Fix C — because Fix A is load-bearing for K72/A83 coverage (53.3%/66.7% → ~100%), Fix B is a
defensive overlap with PR 40's player-slot swap, and only Fix C breaks `test_exploit_diff` parity.

### 1a. Source branches + SHAs (confirmed at prep time)

| PR | Branch | HEAD SHA | Commit subject |
|---|---|---|---|
| **PR 33** | `pr-33-python-delegate` | `29a00c0` | Add Python delegate for `initial_hole_cards=()` (task #182): routes to Rust vector-form CFR when applicable |
| **PR 34** | `pr-34-p0-off-by-one` | `0bafcfa` | PR 34: Fix off-by-one panic at `dcfr_vector.rs:651` (PR 23 P0) |
| **PR 35** (Fix A+B+C bundle) | `pr-35-canonicalization` | `33e03ea` | PR 35: canonicalization fix + player-index inversion + max_raises ALL_IN engine fix |
| **PR 40** | `pr-40-acceptance-test-fix` | `c058e97` | PR 40: fix test-side encoding bugs in Brown apples-to-apples acceptance |

Branch base (merge-base vs main `9a2a89e`):

| Branch | Merge-base | Commits ahead |
|---|---|---|
| `pr-33-python-delegate` | `dc3df6c` (pre-v1.5.0) | 1 |
| `pr-34-p0-off-by-one` | `dc3df6c` (pre-v1.5.0) | 1 |
| `pr-35-canonicalization` | `dc3df6c` (pre-v1.5.0) | 1 |
| `pr-40-acceptance-test-fix` | `b5777f2` (v1.5.1) | 1 |

All four branches present; none have unmerged conflicts with `origin/main` independently. The
test-file conflict appears only when PR 35 (test side) and PR 40 (test side) are stacked.

### 1b. PR 35 sub-fix split

PR 35's single commit `33e03ea` bundles three sub-fixes. File-level mapping:

| Sub-fix | File(s) touched | Action |
|---|---|---|
| **Fix A** (`stack_ceiling` ALL-IN token in renderer) | `tests/test_v1_5_brown_apples_to_apples.py` | **KEEP** |
| **Fix B** (`rust_player = 1 - player` lookup) | `tests/test_v1_5_brown_apples_to_apples.py` | **KEEP** (redundant w/ PR 40 but defensive) |
| **Fix C** (`enumerate_legal_actions` `!cap_reached` guard + inline test) | `crates/cfr_core/src/hunl.rs` | **DROP** |

The split is *clean*: Fix C lives entirely in `hunl.rs`, Fix A + Fix B live entirely in the test
file. No surgical-hunk extraction needed; a path-restricted cherry-pick (or `git restore --staged
--worktree crates/cfr_core/src/hunl.rs` after `cherry-pick -n`) excludes Fix C cleanly.

---

## 2. File-overlap audit

| PR | Touched paths (vs merge-base) |
|---|---|
| PR 33 | `poker_solver/hunl_solver.py`, `tests/test_python_delegate.py` (new) |
| PR 34 | `crates/cfr_core/src/dcfr_vector.rs` |
| PR 35 Fix A+B (only) | `tests/test_v1_5_brown_apples_to_apples.py` |
| PR 40 | `tests/test_v1_5_brown_apples_to_apples.py` |

**Intra-bundle file overlap:** PR 35 Fix A+B and PR 40 both modify
`tests/test_v1_5_brown_apples_to_apples.py`. Confirmed conflict region (one hunk, mechanical
resolution — see §3a). All other paths are disjoint.

**PR 33 path correction:** the leg19 REVISED plan claimed PR 33 touches
`poker_solver/__init__.py`; the actual commit touches `poker_solver/hunl_solver.py`. This
correction does not affect conflict expectations (still disjoint from PR 34/35/40 surfaces).

---

## 3. Sketched merge sequence

> **DO NOT EXECUTE THIS FROM THIS DOC.** Ship happens in the follow-up agent that owns the
> `ship-v1.6.1` worktree, version bump, CHANGELOG, tag, and push.

### 3a. Sequence (in this order)

```bash
# Step 0: ship worktree (per feedback_no_concurrent_branch_ops)
cd /Users/ashen/Desktop/poker_solver
git fetch origin
git worktree add /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.1 \
    -b ship-v1.6.1 origin/main
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.1

# Step 1: PR 34 (Rust off-by-one; small, contained)
git cherry-pick pr-34-p0-off-by-one
# Expected: clean — 1 file (dcfr_vector.rs), no conflict.

# Step 2: PR 33 (Python delegate; disjoint from PR 34)
git cherry-pick pr-33-python-delegate
# Expected: clean — 2 files (hunl_solver.py + new test_python_delegate.py).

# Step 3: PR 35 Fix A + Fix B (drop Fix C)
git cherry-pick -n pr-35-canonicalization
git restore --staged --worktree crates/cfr_core/src/hunl.rs
git commit -m "PR 35 (Fix A+B only): canonicalization + player-index inversion (Fix C dropped per docs/v1_6_1_final_synthesis.md §2)"
# Expected: clean — single staged file (tests/test_v1_5_brown_apples_to_apples.py).

# Step 4: PR 40 (test-side action permutation + range-slot + tolerance)
git cherry-pick pr-40-acceptance-test-fix
# Expected: ONE conflict in tests/test_v1_5_brown_apples_to_apples.py at the
# per-action loop (PR 35 Fix B's `rust_player = 1 - player` lookup overlaps
# PR 40's `for brown_player in (0, 1): ... rust_player = 1 - brown_player`
# rename). Resolve manually per §3b.
```

### 3b. Conflict resolution recipe (Step 4 only)

Empirically verified by a throwaway dry-run worktree at prep time. The single conflict region
is one hunk around line 608 of `tests/test_v1_5_brown_apples_to_apples.py`. Resolution rule:

- **Keep PR 40's loop rename** (`for brown_player in (0, 1):`, `brown_profile =
  brown_dump.players[brown_player].profile`, `brown_hands = brown_dump.players[brown_player].hands`).
- **Keep PR 35 Fix A's `stack_ceiling=stack_ceiling` kwarg** in the per-action loop's call to
  `_rust_history_substr_for_canonical(canonical, stack_ceiling=stack_ceiling)`.
- The `rust_player = 1 - brown_player` line appears in both versions; keep PR 40's single
  authoritative occurrence (immediately under the `for brown_player` line).
- The `rust_rows = rust_lookup.get((rust_player, history_substr))` lookup is identical in both.

Resolved hunk (target shape):

```python
diffs: list[str] = []
for brown_player in (0, 1):
    rust_player = 1 - brown_player  # opener/defender role swap
    brown_profile = brown_dump.players[brown_player].profile
    brown_hands = brown_dump.players[brown_player].hands
    for brown_key, entry in brown_profile.items():
        canonical = canonicalize_brown_history(brown_key, spot=spot)
        history_substr = _rust_history_substr_for_canonical(
            canonical, stack_ceiling=stack_ceiling
        )
        rust_rows = rust_lookup.get((rust_player, history_substr))
        if rust_rows is None:
            continue
        actions = entry.actions
        n_actions = len(actions)
        perm = _brown_to_rust_action_permutation(actions)
        ...
```

No semantic ambiguity; resolution is mechanical, ~30 seconds of editor work. After resolution:

```bash
git add tests/test_v1_5_brown_apples_to_apples.py
git cherry-pick --continue
git log --oneline -6
```

### 3c. Expected post-merge tree (commits on `ship-v1.6.1` above main)

```
<bump>   chore(release): v1.6.1 — engine bundle (PR 33+34+35-A/B+40, drop 35-C)
<pr40>   PR 40: fix test-side encoding bugs in Brown apples-to-apples acceptance
<pr35ab> PR 35 (Fix A+B only): canonicalization + player-index inversion
<pr33>   Add Python delegate for initial_hole_cards=() (task #182)
<pr34>   PR 34: Fix off-by-one panic at dcfr_vector.rs:651 (PR 23 P0)
9a2a89e  examples: add range-vs-range river solve example (main)
```

5 commits above main (4 cherry-picks + 1 release bump).

---

## 4. Pre-merge checks (run before any cherry-pick)

```bash
# All 4 source branches present
git -C /Users/ashen/Desktop/poker_solver branch | grep -E 'pr-(33|34|35|40)'

# SHAs frozen
git -C /Users/ashen/Desktop/poker_solver log --oneline -1 pr-33-python-delegate    # expect 29a00c0
git -C /Users/ashen/Desktop/poker_solver log --oneline -1 pr-34-p0-off-by-one      # expect 0bafcfa
git -C /Users/ashen/Desktop/poker_solver log --oneline -1 pr-35-canonicalization   # expect 33e03ea
git -C /Users/ashen/Desktop/poker_solver log --oneline -1 pr-40-acceptance-test-fix # expect c058e97

# Working tree clean on main
git -C /Users/ashen/Desktop/poker_solver status --short
```

---

## 5. Maturin rebuild (post-merge, pre-test)

PR 34 touches `crates/cfr_core/src/dcfr_vector.rs`. The shipped
`_rust.cpython-313-darwin.so` becomes byte-stale.

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.1
PATH=$HOME/.cargo/bin:$PATH maturin develop --release --target universal2-apple-darwin
python -c "from poker_solver import _rust; print('rust binding OK', _rust.__file__)"
```

Time: ~5-8 min on M2. Fallback to native-arch if universal2 toolchain unavailable.

---

## 6. Post-merge test gate

### 6a. Acceptance test — EXPECTED to PASS at 2e-2 tolerance, ≥80% coverage

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.1
python -m pytest tests/test_v1_5_brown_apples_to_apples.py -v \
    -m parity_noambrown -o "addopts="
```

**Expected:** 2/2 PASS on `dry_K72_rainbow` + `dry_A83_rainbow` per `v1_6_1_final_synthesis.md`
§5 (deep-dive empirical re-run + triage line-by-line confirm the bundle closes the 22-42pp
test-artifact divergence; tolerance widen to 2e-2 absorbs Nash-polytope residual).

**If acceptance test fails:** see §7 fallback decision rules.

### 6b. Regression sweep — `test_exploit_diff` is the parity gate

```bash
python -m pytest tests/test_exploit_diff.py -v
```

**Expected:** 5/5 PASS, including `test_fixed_combo_river_single_bet_size_matches`. This is
the regression detector the bisection used to catch Fix C breakage (delta=0.417 with Fix C
in tree). Without Fix C, parity is preserved.

### 6c. Bundle test set (broader gate)

```bash
python -m pytest tests/test_python_delegate.py \
                 tests/test_range.py \
                 tests/test_dcfr_diff.py \
                 tests/test_range_vs_range_aggregator.py \
                 tests/test_node_locking.py \
                 tests/test_river_diff_self_sanity.py -v
```

Expected: all green.

### 6d. Full Rust unit tests (PR 34 + dropped-Fix-C sanity)

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.1
PATH=$HOME/.cargo/bin:$PATH cargo test --all
```

Expected: green. With Fix C dropped, the inline `enumerate_legal_actions` cap test in
`hunl.rs` reverts to the pre-PR-35 form (does NOT assert `ACTION_ALL_IN` is excluded at cap)
— this is consistent with the dropped engine change.

### 6e. UI smoke + non-slow regression sweep

```bash
python -m pytest tests/test_ui_smoke.py tests/test_ui_pr24a.py tests/test_ui_pr24b.py -v
python -m pytest tests/ -v -k 'not slow and not parity_noambrown' \
    --ignore=tests/test_v1_5_brown_apples_to_apples.py
```

Expected: 44/44 UI + all non-slow non-parity green.

---

## 7. Push gate (PUSH ONLY IF acceptance + parity gates pass)

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.1

# Version bump (pyproject.toml, poker_solver/__init__.py, optionally Cargo.toml)
# Open CHANGELOG.md, insert v1.6.1 section (HONEST framing per synthesis §4).
# Honest framing: claim test-side fix + Rust off-by-one fix + Python delegate;
# DO NOT claim "Brown apples-to-apples = GREEN" without empirical run confirmation.

git add CHANGELOG.md pyproject.toml poker_solver/__init__.py
git commit -m "chore(release): v1.6.1 — engine bundle (PR 33+34+35-A/B+40)"

# Annotated tag
git tag -a v1.6.1 -m "v1.6.1: engine bundle — Python delegate + off-by-one + test fix"

# Push (origin = public)
git push origin HEAD:main
git push origin v1.6.1

# Verify
git fetch --tags origin
git tag -l 'v1.6.1'
git ls-remote --tags origin | grep v1.6.1

# Private mirror (per feedback_dual_remote_workflow)
cd /Users/ashen/Desktop/poker_solver
git push integration main
git push integration v1.6.1
```

Then post-integration verification per `feedback_post_integration_verification`.

---

## 8. Fallback decision rules (if acceptance test fails post-merge)

Per synthesis §5 empirical validation gate:

| Outcome | Decision |
|---|---|
| Both spots PASS at ≥80% coverage AND ≤2e-2 per-action divergence | Ship as composed. Release notes claim GREEN. |
| One spot 70-79% coverage | Spawn PR 45 (hand-string suit-order normalization) implementer; re-test. |
| One spot per-action 3e-2 to 1e-1 | Likely residual Nash polytope cells. Widen tolerance to 5e-2 with documentation, OR add per-spot allow-list. |
| One spot per-action >1e-1 | Triage's 10-15% caveat hit. **HOLD v1.6.1.** Spawn deep-investigation agent (best-response cross-check + iteration sweep). |

---

## 9. Blockers identified

**None blocking ship.** Identified items, all handled:

1. **PR 35 commit bundles all three sub-fixes in one commit.** Resolution: clean
   path-restricted exclusion of `crates/cfr_core/src/hunl.rs` from cherry-pick. Empirically
   verified at prep time (dry-run worktree, ~10 s of mechanical work).
2. **PR 35 Fix A+B and PR 40 both modify the same test file.** Resolution: one mechanical
   conflict at the per-action loop; resolved by keeping PR 40's `brown_player` rename + PR 35
   Fix A's `stack_ceiling=stack_ceiling` kwarg. ~30 s of editor work.
3. **PR 33 actual path mismatch with REVISED plan documentation.** PR 33 touches
   `poker_solver/hunl_solver.py`, not `poker_solver/__init__.py`. Cosmetic; doesn't affect
   merge mechanics. Final ship report should reference the correct path.
4. **Synthesis doc supersedes earlier REVISED plan.** The REVISED ship plan
   (`leg19_v1_6_1_ship_plan_REVISED.md`) drops all of PR 35; the later final synthesis
   (`v1_6_1_final_synthesis.md`) keeps Fix A+B and drops only Fix C. The final synthesis is
   authoritative per its 2026-05-23 date + line-by-line triage (refuting the bisection's H3).

### Not blockers, but flagged for ship agent

- The CHANGELOG framing in the REVISED leg19 plan is OUT OF DATE — it claims Brown
  apples-to-apples STILL FAILS, but the final synthesis expects PASS at 2e-2. The ship agent
  must use the synthesis §4 release-doc framing, NOT the REVISED leg19 §6b/§8 framing.
- The persona-retest cascade framing in REVISED leg19 §10 is similarly out of date. Synthesis
  §5 says W2.3/W3.4/W4.3 should PASS via PR 33 delegate routing now that engine path is
  verified correct. Use synthesis framing.

---

## 10. Estimated time-to-ship (assuming clean acceptance test)

| Step | Time |
|---|---|
| Pre-flight (§4 SHA verification, working-tree clean check) | 2 min |
| Ship worktree setup (§3a Step 0) | 1 min |
| Cherry-pick PR 34, 33, 35-A/B, 40 with conflict resolution (§3) | 3-5 min (incl. ~30s conflict resolve) |
| Maturin rebuild (§5) | 5-8 min |
| Acceptance test §6a | 3-5 min |
| `test_exploit_diff` parity §6b | <1 min |
| Bundle test set §6c | 2-3 min |
| Rust unit tests §6d | 1-2 min |
| UI + regression sweep §6e | 5-7 min |
| Version bump + CHANGELOG (§7) | 3-5 min |
| Tag + push origin + integration (§7) | 2-3 min |
| GitHub release notes (per synthesis §4) | 2 min |
| **Total estimated** | **~30-45 min** assuming clean acceptance |

If acceptance fails and PR 45 spin-up is needed (§8 row 2): add 30-60 min.

---

## 11. Verdict

**READY FOR SHIP** — pending follow-up agent to execute.

- All 5 source SHAs present and verified.
- Fix C drop is a clean single-file exclusion; no surgical-hunk work needed.
- PR 35-A/B vs PR 40 test-file conflict is mechanical (single hunk, ~30 s resolve).
- All other cherry-picks are disjoint at file level.
- Empirical dry-run confirmed conflict scope + resolution path at prep time.

### Source-of-truth pointers (for ship agent)

- Bundle composition + release framing: `docs/v1_6_1_final_synthesis.md` §2, §4
- This prep doc: `docs/v1_6_1_merge_sequence.md`
- Acceptance fallback rules: §5 of the synthesis doc + §8 of this doc
- Memory rules in force: `feedback_no_concurrent_branch_ops`, `feedback_public_repo_hygiene`,
  `feedback_dual_remote_workflow`, `feedback_post_integration_verification`,
  `feedback_pr10a5_autonomous_commit`.
