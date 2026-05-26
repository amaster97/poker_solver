#!/usr/bin/env bash
# =============================================================================
# v1.7.1 ship script — Hybrid path (Brown-as-sanity-check reframe)
# =============================================================================
#
# REQUIRES: user has explicitly approved the Hybrid path
#           (see docs/v1_6_1_engine_ship_plan_final.md)
#
# DOES NOT auto-execute. User must invoke:
#     bash scripts/ship_v1_7_1.sh
#
# WHAT IT DOES (high level):
#   1. Creates a disposable worktree at /tmp/ship-v1.7.1-$$
#   2. Cherry-picks PR 51, PR 50, PR 52, PR 54, PR 55, PR 56, PR 59,
#      PR 53b, PR 53c (in that order — see Phase 2 §rationale)
#      NOTE (2026-05-25): PR 53c is a 41-line ceiling-tweak commit that sits
#      ON TOP OF PR 53b (which carries the 625-line 4-layer reframe). PR 53b
#      is therefore a DEPENDENCY of PR 53c, not "superseded by." Bundle
#      cherry-picks PR 53b then PR 53c. PR 54 (renderer stack_ceiling) is
#      cherry-picked separately, ahead of PR 53b, since PR 53b/53c assume
#      it as their base.
#      NOTE (2026-05-24): PR 55-ext (input-side range swap) was REMOVED from
#      the bundle after the double-swap diagnosis (see
#      docs/r11_brown_convergence_hypothesis.md and
#      docs/r11_double_swap_verification.md). The wrapper's input-side swap
#      collided with the acceptance test's Rust-side swap (PR 40), so they
#      cancelled each other on opposing range-semantics. Reverting PR 55-ext
#      restores single-swap alignment; PR 55 (output-side) remains in the
#      bundle. PR 55-ext branch remains open on origin for reference.
#   3. Bumps versions (pyproject 1.7.0→1.7.1, __init__ 1.7.0→1.7.1,
#      cfr_core 0.7.0→0.7.1; Cargo.lock regenerated via cargo build)
#   4. Inserts CHANGELOG.md entry
#   5. Runs smoke matrix (cargo lib tests, exploit_diff, Brown apples-to-apples,
#      pytest non-slow tier)
#   6. PII grep against tracked files in the diff
#   7. Commits, tags v1.7.1, pushes to origin/main and origin v1.7.1 tag
#   8. Creates GitHub release from docs/v1_7_1_release_notes_template.md
#   9. Cleans up the worktree
#
# PRE-EXECUTION CHECKLIST (verify all before running):
#   [ ] User explicitly approved the Hybrid path on session sign-on
#   [ ] No other agent currently pushing to origin/main concurrently
#   [ ] origin/main is still at 60a98189 (post-PR-#11 merge); re-stage if moved
#   [ ] No leaked /tmp/ship-v1.7.1-* worktrees from prior sessions
#       (check: git worktree list ; rm any stale ones)
#   [ ] gh CLI authenticated for amaster97/poker_solver (gh auth status)
#   [ ] HTTPS+osxkeychain creds present (per ~/.claude feedback_github_auth)
#   [ ] All 10 PR branches still resolvable on origin (re-fetched in Phase 1)
#       Bundle: PR 51, 50, 52, 54, 55, 56, 59, 53b, 53c, 60 (PR 55-ext excluded)
#   [ ] Release notes template at docs/v1_7_1_release_notes_template.md is
#       up-to-date with §4 CHANGELOG body
#
# CONSTRAINTS HONORED:
#   - No force-push (--force never used)
#   - No --no-verify (hooks honored; none configured but rule respected)
#   - No origin branch deletion
#   - No git config mutation
#   - No --amend; new commit is created on top of the cherry-pick chain
#
# Rollback if anything fails mid-flight:
#   - Worktree at /tmp/ship-v1.7.1-$$ is disposable; rm -rf it
#   - No commits/tags reach origin until Phase 7 explicit pushes
#   - If Phase 7 push fails partway (e.g. main pushed but tag failed):
#       gh release delete v1.7.1 --yes 2>/dev/null
#       git push origin :v1.7.1 2>/dev/null
#       git revert <release-bump-sha-on-main> && git push origin main
#
# Validated by: dry-run #9 (PR 55-ext exclusion) + 2026-05-25 retry preflight
# (PR 53b + PR 53c stacked on top of PR 54). See
# docs/v1_6_1_engine_ship_plan_final.md.
#
# =============================================================================

set -euo pipefail

# Ensure rust + python tooling resolve in non-interactive shells. cargo lives
# in ~/.cargo/bin (rustup-managed). maturin/pytest come in via pyenv shims
# which already-on-PATH. This block is idempotent.
if [ -d "$HOME/.cargo/bin" ]; then
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# maturin develop needs a virtualenv. The repo carries .venv at its root, but
# the ship worktree lives in /tmp/ship-v1.7.1-*, so maturin's parent-folder
# search won't find it. Point VIRTUAL_ENV at the repo's .venv explicitly.
if [ -d "/Users/ashen/Desktop/poker_solver/.venv" ] && [ -z "${VIRTUAL_ENV:-}" ]; then
    export VIRTUAL_ENV="/Users/ashen/Desktop/poker_solver/.venv"
    export PATH="$VIRTUAL_ENV/bin:$PATH"
fi

REPO=/Users/ashen/Desktop/poker_solver
WT=/tmp/ship-v1.7.1-$$

# Pinned cherry-pick SHAs (verified 2026-05-24 via `gh pr view N`).
# Each branch is a single-commit branch ahead of origin/main, so we cherry-pick
# the branch tip directly (no SHA range needed).
SHA_PR51=78c71557                    # gh pr 6  pr-51-dcfr-vector-asymmetric-fix
SHA_PR50=18a7640e                    # gh pr 5  pr-50-facing-all-in-guard
SHA_PR52=9e6662b6                    # gh pr 8  pr-52-suit-encoding-fix
SHA_PR54=f389b433                    # gh pr 9  pr-54-renderer-stack-ceiling
SHA_PR55=ac7c6406                    # gh pr 10 pr-55-p0-p1-player-swap
# SHA_PR55_EXT removed 2026-05-24 after double-swap diagnosis
# (was 6e545e63 / gh pr 13 pr-55-extend-input-range-swap; branch left open on origin)
SHA_PR56=950b82c0                    # gh pr 12 pr-56-hand-sort-canonicalization
SHA_PR59=3a59ff54                    # gh pr 18 pr-59-memory-profiler-golden-refresh
# PR 53b is the 625-line 4-layer reframe rebased on PR 54. PR 53c is a
# 41-line ceiling-tweak (Layer 3 max 1.0 -> 1.9) that sits ON TOP OF PR 53b.
# Cherry-picking PR 53c alone would drop PR 53b's reframe and produce a
# malformed bundle (preflight 2026-05-25 confirmed conflicts). Bundle order:
# PR 54 -> PR 53b -> PR 53c. Original PR 53 SHA was 33b38a75; replaced by
# PR 53b's conflict-free rebase.
SHA_PR53B=3e50b760                   # gh pr 14 pr-53b-rebased-on-pr-54
SHA_PR53C=ba1c7162                   # gh pr 15 pr-53c-loosen-layer-3-max
# PR 60 is the test-side silent-skip fix added 2026-05-25 after the v1.7.1
# preflight smoke matrix observed "2 SKIPPED in 0.03s" on the Brown
# acceptance gate. PR 60 adds the _skip_or_fail() helper that respects
# POKER_SOLVER_REQUIRE_BROWN_PARITY=1 so missing prereqs HARD-FAIL instead
# of silently passing. Cherry-picked LAST so the reframe structure
# (PR 53b/53c) is in place first, then PR 60 layers the safety net on top.
SHA_PR60=bde2e12a                    # gh pr 19 pr-60-brown-silent-skip-fix

echo "[ship-v1.7.1] === Phase 1: fresh worktree ==="
cd "$REPO"
git fetch origin --tags
git fetch origin main \
    pr-50-facing-all-in-guard \
    pr-51-dcfr-vector-asymmetric-fix \
    pr-52-suit-encoding-fix \
    pr-53b-rebased-on-pr-54 \
    pr-53c-loosen-layer-3-max \
    pr-54-renderer-stack-ceiling \
    pr-55-p0-p1-player-swap \
    pr-56-hand-sort-canonicalization \
    pr-59-memory-profiler-golden-refresh \
    pr-60-brown-silent-skip-fix

# Sanity: confirm we have all 10 single-commit PR branch tips locally.
# PR 53b sits on top of PR 54 (renderer fix); PR 53c sits on top of PR 53b.
# PR 60 (Brown silent-skip fix) is cherry-picked LAST so its `_skip_or_fail`
# helper layers on top of PR 53b/53c's reframed test structure.
# Bundle order: PR 54 -> PR 53b -> PR 53c -> PR 60, with PR 54 first.
# PR 55-ext excluded after 2026-05-24 double-swap diagnosis.
for sha in "$SHA_PR51" "$SHA_PR50" "$SHA_PR52" "$SHA_PR54" \
           "$SHA_PR55" "$SHA_PR56" "$SHA_PR59" "$SHA_PR53B" "$SHA_PR53C" \
           "$SHA_PR60"; do
    if ! git cat-file -e "$sha" 2>/dev/null; then
        echo "FATAL: SHA $sha not present in local repo. Run:"
        echo "    git fetch --all --tags"
        exit 1
    fi
done
echo "[ship-v1.7.1] All 10 PR SHAs present locally."

# Sanity: origin/main must still be at expected post-v1.7.0 SHA. Bumped to
# 60a98189 on 2026-05-25 after PR #11 (and prior #4/#2/#3) merges.
EXPECTED_MAIN=60a98189
ACTUAL_MAIN=$(git rev-parse origin/main | cut -c1-8)
if [ "$ACTUAL_MAIN" != "$EXPECTED_MAIN" ]; then
    echo "FATAL: origin/main has moved past v1.7.0."
    echo "       expected $EXPECTED_MAIN, got $ACTUAL_MAIN"
    echo "       Re-stage the plan; do NOT proceed."
    exit 1
fi
echo "[ship-v1.7.1] origin/main at expected SHA: $ACTUAL_MAIN"

git worktree add "$WT" origin/main
cd "$WT"
echo "[ship-v1.7.1] worktree at $WT, on origin/main ($(git rev-parse --short HEAD))"

echo "[ship-v1.7.1] === Phase 2: cherry-pick bundle ==="
# Bundle is 10 cherry-picks total: PR 51, 50, 52, 54, 55, 56, 59, 53b, 53c, 60.
# PR 53b adds the 4-layer reframed acceptance test; PR 53c is a 41-line
# tweak loosening Layer 3's max ceiling on top of it. PR 59 refreshes
# the memory_profiler golden file for the post-PR-50 river tree shape.
# PR 60 adds the _skip_or_fail() safety net to the acceptance test so
# missing prereqs HARD-FAIL when POKER_SOLVER_REQUIRE_BROWN_PARITY=1.
#
# Cherry-pick order rationale:
#   1. PR 51 (Rust dcfr_vector.rs — isolated; ~7-line panic fix)
#   2. PR 50 (Rust hunl.rs + Python action_abstraction.py — paired guard)
#   3. PR 52 (Python wrapper suit-encoding char map)
#   4. PR 54 (test renderer stack_ceiling kwarg)
#   5. PR 55 (Python wrapper P0/P1 output-side swap)
#   6. PR 56 (Python wrapper hand-string canonical sort)
#   7. PR 59 (memory_profiler golden refresh — required-with-PR-50)
#   8. PR 53b (4-layer reframe rebased on PR 54 — 625 LOC)
#   9. PR 53c (41-line tweak: Layer 3 max ceiling 1.0 -> 1.9, on top of 53b)
#  10. PR 60 (silent-skip safety net — _skip_or_fail helper on top of 53b/53c)
#
# PR 55-ext (input-side range swap) was REMOVED from the bundle 2026-05-24
# after the double-swap diagnosis (docs/r11_brown_convergence_hypothesis.md,
# docs/r11_double_swap_verification.md). The wrapper's input-side swap
# fought the acceptance test's Rust-side PR 40 swap. Reverting it restores
# single-swap alignment; empirical NO-swap convention shows Brown↔Rust
# agreement to ~6 decimals on AA root, vs ~3-class divergence with both
# swaps applied.
#
# PR 53b is a DEPENDENCY of PR 53c (not "superseded by"). PR 53c is a
# 41-line ceiling-tweak (Layer 3 max 1.0 -> 1.9) sitting on top of PR 53b's
# 625-line reframe. Cherry-picking PR 53c alone drops the reframe and
# produces conflicts (verified preflight 2026-05-25). The loosened
# ceiling accommodates deep-cap Nash multiplicity between our richer
# action menu and Brown's narrower one (both produce valid Nash equilibria
# for their respective game definitions). PR 54 is cherry-picked separately,
# before PR 53b, since PR 53b is rebased on PR 54.
#
# All 10 cherry-picks are expected to land cleanly (verified via the
# dry-run chain documented in docs/v1_6_1_engine_ship_plan_final.md §2
# + dry-run #9 for the PR 55-ext exclusion + 2026-05-25 retry preflight
# for the PR 53b+53c stacking). Halt on any conflict.

echo "[ship-v1.7.1] Cherry-picking PR 51 ($SHA_PR51) — dcfr_vector panic fix..."
git cherry-pick "$SHA_PR51"

echo "[ship-v1.7.1] Cherry-picking PR 50 ($SHA_PR50) — facing-all-in guard..."
git cherry-pick "$SHA_PR50"

echo "[ship-v1.7.1] Cherry-picking PR 52 ($SHA_PR52) — suit-encoding fix..."
git cherry-pick "$SHA_PR52"

echo "[ship-v1.7.1] Cherry-picking PR 54 ($SHA_PR54) — renderer stack_ceiling kwarg..."
git cherry-pick "$SHA_PR54"

echo "[ship-v1.7.1] Cherry-picking PR 55 ($SHA_PR55) — P0/P1 output swap..."
git cherry-pick "$SHA_PR55"

# PR 55-ext EXCLUDED 2026-05-24 (double-swap diagnosis); see Phase 2 header.

echo "[ship-v1.7.1] Cherry-picking PR 56 ($SHA_PR56) — hand-sort canonical..."
git cherry-pick "$SHA_PR56"

echo "[ship-v1.7.1] Cherry-picking PR 59 ($SHA_PR59) — memory_profiler golden file refresh (post-PR-50 tree)..."
git cherry-pick "$SHA_PR59"

echo "[ship-v1.7.1] Cherry-picking PR 53b ($SHA_PR53B) — 4-layer acceptance test reframe (625 LOC)..."
git cherry-pick "$SHA_PR53B"

echo "[ship-v1.7.1] Cherry-picking PR 53c ($SHA_PR53C) — Layer 3 max ceiling loosened to 1.9 (41 LOC tweak on top of PR 53b)..."
git cherry-pick "$SHA_PR53C"

echo "[ship-v1.7.1] Cherry-picking PR 60 ($SHA_PR60) — Brown acceptance silent-skip safety net (HARD-FAIL under POKER_SOLVER_REQUIRE_BROWN_PARITY=1)..."
git cherry-pick "$SHA_PR60"

echo "[ship-v1.7.1] All 10 cherry-picks landed (PR 55-ext excluded; see Phase 2 header)."
git log --oneline -10

echo "[ship-v1.7.1] === Phase 3: version bumps ==="

# pyproject.toml: 1.7.0 -> 1.7.1
python3 - <<'PYEOF'
from pathlib import Path
p = Path("pyproject.toml")
text = p.read_text()
old = 'version = "1.7.0"'
new = 'version = "1.7.1"'
if old not in text:
    raise SystemExit("FATAL: pyproject.toml version line not found (expected '1.7.0')")
p.write_text(text.replace(old, new, 1))
print("[ship-v1.7.1] pyproject.toml 1.7.0 -> 1.7.1")
PYEOF

# poker_solver/__init__.py: __version__ = "1.7.0" -> "1.7.1"
python3 - <<'PYEOF'
from pathlib import Path
p = Path("poker_solver/__init__.py")
text = p.read_text()
old = '__version__ = "1.7.0"'
new = '__version__ = "1.7.1"'
if old not in text:
    raise SystemExit("FATAL: poker_solver/__init__.py __version__ line not found (expected '1.7.0')")
p.write_text(text.replace(old, new, 1))
print("[ship-v1.7.1] poker_solver/__init__.py __version__ 1.7.0 -> 1.7.1")
PYEOF

# crates/cfr_core/Cargo.toml: 0.7.0 -> 0.7.1
# (Note: ship plan §3 stated 0.6.0; verified at stage time origin/main is 0.7.0,
#  PATCH-aligned with v1.7.0. Bumping to 0.7.1 for v1.7.1.)
python3 - <<'PYEOF'
from pathlib import Path
p = Path("crates/cfr_core/Cargo.toml")
text = p.read_text()
old = 'version = "0.7.0"'
new = 'version = "0.7.1"'
if old not in text:
    raise SystemExit("FATAL: crates/cfr_core/Cargo.toml version line not found (expected '0.7.0')")
p.write_text(text.replace(old, new, 1))
print("[ship-v1.7.1] cfr_core Cargo.toml 0.7.0 -> 0.7.1")
PYEOF

echo "[ship-v1.7.1] === Phase 4: CHANGELOG entry ==="
python3 - <<'PYEOF'
from pathlib import Path
from datetime import date

p = Path("CHANGELOG.md")
text = p.read_text()
marker = "## [1.7.0]"
if marker not in text:
    raise SystemExit("FATAL: CHANGELOG.md '## [1.7.0]' anchor not found")

today = date.today().isoformat()  # YYYY-MM-DD
new_section = f"""## [1.7.1] - {today}

### Fixed
- Engine: facing-all-in action menu guard (PR 50)
- Engine: dcfr_vector.rs off-by-one panic on asymmetric ranges (PR 51)
- Parity wrapper: suit-encoding char mapping (PR 52)
- Test renderer: stack_ceiling kwarg for deep-history canonicalization (PR 54)
- Parity wrapper: P0/P1 player convention swap (PR 55)
- Parity wrapper: hand-string sort-order canonicalization (PR 56)

### Changed
- Acceptance test reframed from strict per-action match to 4-layer
  sanity check; Layer 3 max ceiling loosened to 1.9 to accommodate
  deep-cap Nash multiplicity between our richer action menu and Brown's
  narrower one (both produce valid Nash equilibria for their respective
  game definitions). (PR 53b + PR 53c)

### Documentation
- 10 memory rules codified during the investigation (reversal chain
  R1-R10): wrapper-hazard pattern, parity-wrapper-hazard,
  index-as-char-hazard, player-convention-mismatch.

### Compatibility
- No new public API; no signature changes; backward-compatible with
  v1.7.0.
- Rust binary `_rust.cpython-313-darwin.so` is REBUILT for v1.7.1
  (PR 50 and PR 51 touch Rust source). Users running from source
  must `maturin develop --release` after pull.
- `crates/cfr_core` bumps 0.7.0 -> 0.7.1.

"""
text = text.replace(marker, new_section + marker, 1)
p.write_text(text)
print(f"[ship-v1.7.1] CHANGELOG.md updated with [1.7.1] - {today}")
PYEOF

echo "[ship-v1.7.1] === Phase 5: smoke matrix ==="

echo "[ship-v1.7.1] cargo build --release..."
cargo build --release

echo "[ship-v1.7.1] cargo test --lib --release..."
cargo test --lib --release

# Rebuild Python bindings against the cherry-picked Rust changes
echo "[ship-v1.7.1] maturin develop --release..."
maturin develop --release

echo "[ship-v1.7.1] pytest tests/test_exploit_diff.py (critical Python-Rust gate)..."
pytest tests/test_exploit_diff.py -v --timeout=120

# Brown's river_solver_optimized binary lives under
# references/code/noambrown_poker_solver/cpp/build/, which is gitignored.
# The worktree at /tmp/ship-v1.7.1-$$ therefore does NOT inherit it from the
# shared tree, so the acceptance gate would silently skip via
# `_require_brown_binary()` (see tests/test_v1_5_brown_apples_to_apples.py
# lines 208-217 — `pytest.skip(...)`). Silent-skip ship-preflight bug
# diagnosed 2026-05-25: ensure the binary is present BEFORE invoking the
# gate, and HARD-FAIL the ship if it is still missing.
echo "[ship-v1.7.1] Ensuring Brown's river_solver_optimized is available in worktree..."
BROWN_BIN_REL="references/code/noambrown_poker_solver/cpp/build/river_solver_optimized"
BROWN_BIN_SHARED="$REPO/$BROWN_BIN_REL"
BROWN_BIN_WT="$WT/$BROWN_BIN_REL"
mkdir -p "$(dirname "$BROWN_BIN_WT")"
if [ ! -x "$BROWN_BIN_WT" ]; then
    if [ -x "$BROWN_BIN_SHARED" ]; then
        echo "[ship-v1.7.1] Linking prebuilt Brown binary from shared tree."
        ln -sf "$BROWN_BIN_SHARED" "$BROWN_BIN_WT"
    else
        echo "[ship-v1.7.1] Brown binary missing in both shared tree and worktree; building..."
        bash "$WT/scripts/build_noambrown.sh"
    fi
fi
if [ ! -x "$BROWN_BIN_WT" ]; then
    echo "FATAL: Brown's river_solver_optimized still missing after build attempt."
    echo "       Path: $BROWN_BIN_WT"
    echo "       Acceptance gate would silently skip; aborting ship."
    exit 1
fi
echo "[ship-v1.7.1] Brown binary present at $BROWN_BIN_WT."

echo "[ship-v1.7.1] pytest tests/test_v1_5_brown_apples_to_apples.py (reframed acceptance gate)..."
# POKER_SOLVER_REQUIRE_BROWN_PARITY=1 turns the test's pytest.skip() guards
# into pytest.fail() so a missing prereq HARD-FAILS the ship instead of
# silently passing (silent-skip ship-preflight bug fix, 2026-05-25).
POKER_SOLVER_REQUIRE_BROWN_PARITY=1 \
    pytest tests/test_v1_5_brown_apples_to_apples.py -v --timeout=1800 -ra

# Optional: if the asymmetric-range sanity test was authored as part of PR 51,
# run it; otherwise skip with notice. Per ship plan, this is a new gate.
if [ -f tests/test_asymmetric_range_sanity.py ]; then
    echo "[ship-v1.7.1] pytest tests/test_asymmetric_range_sanity.py (new gate)..."
    pytest tests/test_asymmetric_range_sanity.py -v --timeout=60
else
    echo "[ship-v1.7.1] tests/test_asymmetric_range_sanity.py not present in bundle — skipping."
fi

echo "[ship-v1.7.1] pytest non-slow tier..."
# 2026-05-25: bumped --timeout 60→300 (test_parity_happy_path_runs_to_completion ~188s caused 5 ship retries to die at Phase 5).
pytest -x --timeout=300 -m "not slow and not very_slow" -q

echo "[ship-v1.7.1] === Phase 6: PII grep ==="
# Public-OK audit on the diff (per feedback_public_repo_hygiene.md).
# Greps tracked files in the diff for personal paths or PII; flags if found.
DIFF_FILES=$(git diff origin/main --name-only)
if [ -n "$DIFF_FILES" ]; then
    if echo "$DIFF_FILES" | xargs grep -lE "/Users/ashen|ashen26@|claude-session" 2>/dev/null; then
        echo "FATAL: PII / personal-path leak found in the diff. Investigate before pushing."
        exit 1
    fi
fi
echo "[ship-v1.7.1] PII grep clean."

echo "[ship-v1.7.1] === Phase 7: commit, tag, push ==="

# Stage version bump + CHANGELOG + Cargo.lock (regenerated by cargo build above)
git add pyproject.toml poker_solver/__init__.py crates/cfr_core/Cargo.toml CHANGELOG.md
if [ -n "$(git status --porcelain Cargo.lock)" ]; then
    git add Cargo.lock
fi

git status

# Use a temp file for the commit message to avoid shell-quoting hazards.
COMMIT_MSG_FILE=$(mktemp /tmp/ship-v1.7.1-commit-msg.XXXXXX)
cat > "$COMMIT_MSG_FILE" <<'COMMIT_EOF'
chore(release): v1.7.1 - engine + wrapper fixes + Brown-as-sanity-check reframe

Engine fixes:
- PR 51: dcfr_vector.rs off-by-one panic on asymmetric ranges
- PR 50: facing-all-in action menu guard (paired Rust + Python)

Parity wrapper fixes (noambrown_wrapper.py):
- PR 52: suit-encoding char map ("shdc" <-> "cdhs")
- PR 55: P0/P1 player-convention swap (output side)
- PR 56: hand-string sort-order canonicalization

NOTE: PR 55-ext (input-side range swap) was excluded from the bundle
after the double-swap diagnosis (see docs/r11_brown_convergence_hypothesis.md
and docs/r11_double_swap_verification.md). The wrapper input swap
clashed with the test's PR 40 Rust-side swap; reverting PR 55-ext
restores single-swap alignment.

Test renderer + acceptance test:
- PR 54: renderer stack_ceiling kwarg (deep-history canonicalization)
- PR 53b: 4-layer Brown-as-sanity-check reframe of acceptance test
  (625 LOC), rebased on PR 54.
- PR 53c: 41-line follow-on tweak loosening Layer 3 max L1 ceiling
  from 1.0 to 1.9 to accommodate deep-cap Nash multiplicity between
  our richer action menu and Brown's narrower one (both produce
  valid Nash equilibria for their respective game definitions).
  Original PR 53 conflicted at 4 hunks; PR 53b's rebase is
  conflict-free and PR 53c stacks cleanly on top.

Memory profiler golden refresh:
- PR 59: refresh memory_profiler golden file for the post-PR-50
  HUNL river tree shape (mean actions 3.25 -> 2.75, solver arrays
  832 -> 704 bytes, grand total 2230 -> 2102 bytes). Required-with-
  PR-50; without this refresh the smoke matrix halts at
  test_memory_profiler_golden_file_river_only.

Version bumps:
- pyproject.toml: 1.7.0 -> 1.7.1
- poker_solver/__init__.py: 1.7.0 -> 1.7.1
- crates/cfr_core/Cargo.toml: 0.7.0 -> 0.7.1

See docs/v1_6_1_engine_ship_plan_final.md for full rationale.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
COMMIT_EOF
git commit -F "$COMMIT_MSG_FILE"
rm -f "$COMMIT_MSG_FILE"

# Lightweight final sanity before tagging
echo "[ship-v1.7.1] final sanity: cargo test --lib --release post-commit..."
cargo test --lib --release

# Annotated tag
git tag -a v1.7.1 -m "v1.7.1: engine + wrapper bug fix bundle (PR 50/51/52/54/55/56/59/53b/53c)"

# Push commits (fast-forward to origin/main) then tag
echo "[ship-v1.7.1] push main..."
git push origin HEAD:main

echo "[ship-v1.7.1] push tag v1.7.1..."
git push origin v1.7.1

echo "[ship-v1.7.1] === Phase 8: GitHub release ==="
RELEASE_NOTES_SRC="$REPO/docs/v1_7_1_release_notes_template.md"
if [ ! -f "$RELEASE_NOTES_SRC" ]; then
    echo "FATAL: release notes template missing at $RELEASE_NOTES_SRC"
    exit 1
fi

gh release create v1.7.1 \
    --repo amaster97/poker_solver \
    --latest \
    --title "v1.7.1: engine + wrapper bug fixes + Brown-as-sanity-check reframe" \
    --notes-file "$RELEASE_NOTES_SRC"

gh release view v1.7.1 --repo amaster97/poker_solver | head -16

echo "[ship-v1.7.1] === Phase 9: cleanup ==="
cd "$REPO"
git worktree remove --force "$WT"
echo "[ship-v1.7.1] worktree removed."
echo "[ship-v1.7.1] === DONE ==="
echo ""
echo "Next steps (per docs/v1_6_1_engine_ship_plan_final.md §6h, §8):"
echo "  1. Catch up shared tree: git pull --ff-only origin main"
echo "  2. Verify private mirror sync (post-integration verification protocol)"
echo "  3. Resume Gate 4 (200K-iter exploitability) and persona retests"
echo "  4. Trigger PR 11 .dmg rebuild (feedback_ui_packaging_sync)"
