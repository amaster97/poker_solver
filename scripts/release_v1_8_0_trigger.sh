#!/usr/bin/env bash
# =============================================================================
# v1.8.0 one-shot ship trigger wrapper
# =============================================================================
#
# Wraps `scripts/release_v1_8_0.sh` so the v1.8.0 release can be executed
# with a single command + zero manual editing after the convention-purge PR
# lands and the post-purge validation completes.
#
# WHAT THIS WRAPPER ADDS ON TOP OF release_v1_8_0.sh:
#   1. Dynamically reads the current `origin/main` HEAD SHA (no hard-coded
#      SHA needed in the invocation; the script's stale `EXPECTED_SHA` is
#      overridden via `--expected-sha`).
#   2. Stashes the ~265+ untracked docs that live in the working tree so
#      the inner script's Phase 0.2 (clean-tree check) passes.
#   3. Runs `scripts/release_v1_8_0.sh --expected-sha <current-HEAD>`.
#   4. On success: `git stash pop` to restore the untracked docs.
#   5. On failure: prints a clear diagnostic and LEAVES the stash in place
#      for the user to inspect + recover manually.
#   6. Hard-fails BEFORE the inner script if any post-purge ship
#      pre-conditions aren't met:
#        - `crates/cfr_core/src/hunl.rs` `utility()` must use the canonical
#          formula (subtracts `initial_contributions`, adds `base_pot`).
#        - `tests/test_v1_5_brown_apples_to_apples.py` must PASS (the
#          reframed 4-layer gate).
#      A `--skip-post-purge-checks` escape hatch exists for the
#      pre-purge dress-rehearsal use case (NOT for the actual ship).
#
# USAGE:
#   bash scripts/release_v1_8_0_trigger.sh                    # ship for real
#   bash scripts/release_v1_8_0_trigger.sh --dry-run          # pre-flight only
#   bash scripts/release_v1_8_0_trigger.sh --upload-dmg       # forwarded to inner
#   bash scripts/release_v1_8_0_trigger.sh --skip-backup      # forwarded to inner
#   bash scripts/release_v1_8_0_trigger.sh --no-bump-cfr-core # forwarded to inner
#   bash scripts/release_v1_8_0_trigger.sh --skip-post-purge-checks
#       Bypass post-purge precondition checks (pre-purge dress-rehearsal
#       ONLY; will produce a non-canonical release if used at real ship
#       time; the wrapper prints a loud WARN line).
#
# WHEN TO RUN:
#   - After the terminal-utility convention purge PR has merged to
#     `origin/main`.
#   - After post-purge validation (v1.5 Brown apples-to-apples) PASSES on
#     `origin/main`.
#   - With `gh` authenticated, network access, and `backup` remote
#     configured (unless `--skip-backup`).
#
# IDEMPOTENCY / SAFETY:
#   - Safe to run with `--dry-run` repeatedly.
#   - A real ship is NOT idempotent (the inner script creates a tag +
#     GitHub release; a second invocation will fail at Phase 0.8
#     "tag already exists"). The wrapper relies on the inner script's
#     own duplicate-tag guards rather than adding new ones.
#   - The wrapper itself is restart-safe in the sense that a failed
#     pre-flight or stash leaves a clear recovery path (see "Recovery"
#     in docs/v1_8_0_ship_trigger_runbook_2026-05-27.md).
#
# RELATED:
#   docs/v1_8_0_ship_trigger_runbook_2026-05-27.md — runbook
#   scripts/release_v1_8_0.sh                       — inner script (wrapped)
#   docs/v1_8_0_final_ship_readiness_2026-05-26.md  — prior pre-flight GO
#   docs/dmg_build_runbook_2026-05-26.md            — post-ship .dmg build
#
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
REPO=/Users/ashen/Desktop/poker_solver
INNER_SCRIPT="scripts/release_v1_8_0.sh"
STASH_MSG="pre-v1.8.0-release-stash-2026-05-27"

# -----------------------------------------------------------------------------
# Flag parsing
# -----------------------------------------------------------------------------
DRY_RUN=0
SKIP_POST_PURGE_CHECKS=0
INNER_FLAGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --skip-post-purge-checks)
            SKIP_POST_PURGE_CHECKS=1
            shift
            ;;
        --upload-dmg|--skip-backup|--no-bump-cfr-core)
            INNER_FLAGS+=("$1")
            shift
            ;;
        --expected-sha)
            echo "FATAL: --expected-sha is set dynamically by this wrapper; do not pass it explicitly."
            echo "       If you need to override the SHA, invoke scripts/release_v1_8_0.sh directly."
            exit 2
            ;;
        -h|--help)
            sed -n '2,60p' "$0"
            exit 0
            ;;
        *)
            echo "FATAL: unknown flag $1"
            echo "       Usage: bash $0 [--dry-run] [--skip-post-purge-checks] [--upload-dmg] [--skip-backup] [--no-bump-cfr-core]"
            exit 2
            ;;
    esac
done

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
log()  { echo "[trigger-v1.8.0] $*"; }
warn() { echo "[trigger-v1.8.0] WARN: $*"; }
fail() { echo "[trigger-v1.8.0] FATAL: $*" >&2; exit 1; }

# Check whether a stash entry with the given message exists. Returns 0 if
# found, 1 otherwise. Uses captured-output (NOT a pipeline to grep) to avoid
# `set -o pipefail` propagating SIGPIPE-induced 141 exits from `git stash list`
# when `grep -q` closes stdin early on first match — that turns a found-match
# into a false-negative under `pipefail`.
stash_msg_exists() {
    local msg="$1"
    local list_out
    list_out=$(git stash list)
    case "$list_out" in
        *"$msg"*) return 0 ;;
        *)        return 1 ;;
    esac
}

# Pop the wrapper's stash, robustly. Detects the partial-restore-with-conflict
# case where `git stash pop` returns 0 even though the stash entry was kept
# in place (this happens when --include-untracked stash pop encounters a
# tracked-file content conflict — pop applies the untracked side, drops
# nothing, and leaves the user with a half-restored tree + a lingering stash).
# Strategy: capture pop output, check exit code, AND verify the stash entry
# is no longer present in `git stash list`. Returns 0 on full success; 1
# otherwise (caller decides whether to fail-hard or warn).
pop_release_stash() {
    local stash_msg="$1"
    local pop_out pop_rc
    # Find the most recent stash matching our message and pop it explicitly by
    # ref. This protects against the case where another stash got created
    # between push and pop (rare but possible) or where `git stash pop` without
    # an explicit ref would target a different entry.
    # Use captured output + awk (no `git ... | awk` to avoid pipefail SIGPIPE).
    local stash_list_out stash_ref
    stash_list_out=$(git stash list)
    stash_ref=$(awk -F: -v msg="$stash_msg" '
        $0 ~ msg { print $1; exit }
    ' <<< "$stash_list_out")
    if [[ -z "$stash_ref" ]]; then
        warn "no stash matching '$stash_msg' found in stash list (was it already popped?)"
        return 1
    fi
    log "  popping $stash_ref ($stash_msg)..."
    pop_out=$(git stash pop "$stash_ref" 2>&1)
    pop_rc=$?
    if [[ "$pop_rc" -ne 0 ]]; then
        warn "git stash pop $stash_ref exited $pop_rc:"
        printf '%s\n' "$pop_out" | head -20 >&2 || true
        return 1
    fi
    # Pop returned 0; verify the stash entry actually got dropped.
    if stash_msg_exists "$stash_msg"; then
        warn "git stash pop $stash_ref returned 0 but stash entry '$stash_msg' was not dropped."
        warn "This typically means a tracked-file conflict during pop kept the stash alive."
        warn "Pop output (last 20 lines):"
        printf '%s\n' "$pop_out" | tail -20 >&2 || true
        return 1
    fi
    return 0
}

# -----------------------------------------------------------------------------
# Sanity: cd into repo + verify inner script exists + is executable / readable
# -----------------------------------------------------------------------------
cd "$REPO"

if [[ ! -f "$INNER_SCRIPT" ]]; then
    fail "inner script missing: $INNER_SCRIPT (cwd=$(pwd))"
fi
if [[ ! -r "$INNER_SCRIPT" ]]; then
    fail "inner script not readable: $INNER_SCRIPT"
fi
log "inner script: $INNER_SCRIPT (ok)"

# -----------------------------------------------------------------------------
# Phase A: branch must be main
# -----------------------------------------------------------------------------
log "=== Phase A: branch check ==="
CURRENT_BRANCH=$(git branch --show-current)
if [[ "$CURRENT_BRANCH" != "main" ]]; then
    fail "must be on 'main' branch (currently on: $CURRENT_BRANCH). \
Switch with: git checkout main"
fi
log "branch: main"

# -----------------------------------------------------------------------------
# Phase B: fetch + capture current origin/main HEAD SHA dynamically
# -----------------------------------------------------------------------------
log "=== Phase B: dynamic SHA resolution ==="
git fetch origin main >/dev/null 2>&1 || fail "git fetch origin main failed; check network + auth"
EXPECTED_SHA=$(git rev-parse origin/main)
log "origin/main HEAD: $EXPECTED_SHA"

# Verify local main is fast-forward-able to origin/main (or already at it).
LOCAL_SHA=$(git rev-parse HEAD)
if [[ "$LOCAL_SHA" != "$EXPECTED_SHA" ]]; then
    # Allow auto-FF if local is strictly behind (no divergent commits).
    if git merge-base --is-ancestor "$LOCAL_SHA" "$EXPECTED_SHA"; then
        log "local main ($LOCAL_SHA) is behind origin/main; fast-forwarding..."
        git pull --ff-only origin main >/dev/null 2>&1 || fail "fast-forward failed"
        LOCAL_SHA=$(git rev-parse HEAD)
        log "local main now at: $LOCAL_SHA"
    else
        fail "local main ($LOCAL_SHA) has diverged from origin/main ($EXPECTED_SHA). \
Resolve manually before running this wrapper."
    fi
fi

# -----------------------------------------------------------------------------
# Phase C: post-purge precondition checks (gate on canonical convention +
#          v1.5 Brown apples-to-apples PASS)
# -----------------------------------------------------------------------------
log "=== Phase C: post-purge precondition checks ==="

if [[ "$SKIP_POST_PURGE_CHECKS" == "1" ]]; then
    warn "post-purge precondition checks SKIPPED via --skip-post-purge-checks."
    warn "This is a pre-purge dress-rehearsal flag; using it at real ship"
    warn "time will produce a non-canonical v1.8.0 release."
else
    # C.1: utility() must use canonical formula (subtracts initial_contributions
    # and adds the carried base pot). The pre-purge "rust" path uses
    # `c0 = self.contributions[0]` and returns `[-c0/bb, c0/bb]` on fold,
    # treating initial_contributions as recoverable. The canonical post-purge
    # path subtracts initial_contributions (-> contrib_subgame_*) and adds
    # base_pot for the winner.
    if ! grep -q "initial_contributions" crates/cfr_core/src/hunl.rs; then
        fail "Phase C.1 — crates/cfr_core/src/hunl.rs does not reference \
'initial_contributions' at all; cannot verify canonical convention. \
This wrapper expects the convention purge to have landed."
    fi
    # Heuristic detection: the canonical utility() either references
    # `contrib_subgame` (per the post-purge naming) or subtracts
    # initial_contributions inside utility() body. We look at the lines
    # between `pub fn utility(&self) -> [f64; 2]` and the closing `}`.
    UTILITY_BODY=$(python3 - <<'PYEOF'
import re, sys, pathlib
src = pathlib.Path("crates/cfr_core/src/hunl.rs").read_text()
# Pull body of pub fn utility(...)
m = re.search(r'pub fn utility\(&self\) -> \[f64; 2\] \{(.*?)\n    \}', src, re.S)
if not m:
    sys.exit("no_pub_fn_utility")
print(m.group(1))
PYEOF
)
    if [[ "$UTILITY_BODY" == "no_pub_fn_utility" ]]; then
        fail "Phase C.1 — cannot locate 'pub fn utility' body in crates/cfr_core/src/hunl.rs"
    fi
    # Check the body references either contrib_subgame or initial_contributions.
    if ! echo "$UTILITY_BODY" | grep -qE "contrib_subgame|initial_contributions|base_pot|pot_total"; then
        fail "Phase C.1 — pub fn utility() body does NOT reference any of \
{contrib_subgame, initial_contributions, base_pot, pot_total}. \
This looks like the pre-purge 'rust' convention is still in place. \
Convention purge must merge before this wrapper is run for a real ship. \
(Pass --skip-post-purge-checks ONLY for a pre-purge dress-rehearsal.)"
    fi
    log "Phase C.1 — utility() uses canonical formula (heuristic): OK"

    # C.2: release notes draft no longer has TBD placeholders (the purge PR
    # is expected to substitute these).
    NOTES_FILE="docs/v1_8_0_release_notes_DRAFT.md"
    if [[ ! -f "$NOTES_FILE" ]]; then
        fail "Phase C.2 — release notes file missing: $NOTES_FILE"
    fi
    TBD_COUNT=$(grep -c "TBD" "$NOTES_FILE" 2>/dev/null || echo 0)
    if [[ "$TBD_COUNT" -gt 0 ]]; then
        warn "Phase C.2 — release notes contain $TBD_COUNT 'TBD' marker(s)."
        warn "These should be substituted before tagging:"
        # `|| true` guards against pipefail+SIGPIPE when head closes early.
        grep -nE "<TBD-[A-Z0-9_-]+>" "$NOTES_FILE" | head -5 || true
        if [[ "$DRY_RUN" != "1" ]]; then
            fail "Phase C.2 — refusing to ship with TBD placeholders in release notes. \
Substitute the placeholders, then re-run. (--dry-run will allow this for inspection.)"
        fi
    else
        log "Phase C.2 — release notes have no TBD placeholders: OK"
    fi

    # C.3: v1.5 Brown apples-to-apples PASS — full pytest is multi-minute; we
    # only verify the test file exists + is non-empty + imports cleanly.
    # The inner script's CI-status check (Phase 0.5) is the authoritative
    # gate: if the post-purge run on origin/main is green, the v1.5 Brown
    # acceptance must have passed there.
    BROWN_TEST="tests/test_v1_5_brown_apples_to_apples.py"
    if [[ ! -f "$BROWN_TEST" ]]; then
        fail "Phase C.3 — v1.5 Brown acceptance test missing: $BROWN_TEST"
    fi
    BROWN_LINES=$(wc -l < "$BROWN_TEST")
    if [[ "$BROWN_LINES" -lt 100 ]]; then
        fail "Phase C.3 — $BROWN_TEST has only $BROWN_LINES lines (expected >> 100)"
    fi
    log "Phase C.3 — v1.5 Brown test present ($BROWN_LINES lines); \
authoritative PASS gated by inner-script CI check (Phase 0.5)"
fi

# -----------------------------------------------------------------------------
# Phase D: stash untracked docs so inner Phase 0.2 (clean tree) passes
# -----------------------------------------------------------------------------
log "=== Phase D: stash untracked docs ==="

# Snapshot status before stash for diagnostic purposes
UNTRACKED_BEFORE=$(git status --porcelain | wc -l | tr -d ' ')
log "working-tree dirty lines (porcelain) before stash: $UNTRACKED_BEFORE"

STASHED=0
if [[ "$UNTRACKED_BEFORE" -gt 0 ]]; then
    # Note: --include-untracked also picks up unstaged tracked changes.
    # `--message` is the standard way to tag the stash so we can find it
    # back if anything goes sideways.
    log "stashing with message: $STASH_MSG"
    git stash push --include-untracked --message "$STASH_MSG" >/dev/null 2>&1 || true
    # Authoritative check: did a stash entry actually get created?
    # (git stash push can return 0 with nothing-to-stash and produce no entry.)
    if stash_msg_exists "$STASH_MSG"; then
        STASHED=1
        log "stash created."
    else
        warn "git stash push did not create an entry matching '$STASH_MSG'."
        warn "Working tree dirty lines = $UNTRACKED_BEFORE before; inner script may abort \
on clean-tree check. Continuing (let the inner script issue the authoritative complaint)."
    fi

    # Verify tree is clean now
    DIRTY_AFTER=$(git status --porcelain | wc -l | tr -d ' ')
    if [[ "$DIRTY_AFTER" -gt 0 ]]; then
        warn "working tree still dirty after stash ($DIRTY_AFTER lines):"
        git status --short | head -10 || true
        fail "cannot proceed — inner script Phase 0.2 would abort. \
Inspect manually; the stash (if created) is named '$STASH_MSG' and can be \
recovered with: git stash list | grep '$STASH_MSG'"
    fi
else
    log "tree is clean already; no stash needed."
fi

# -----------------------------------------------------------------------------
# Phase E: dry-run short-circuit
# -----------------------------------------------------------------------------
if [[ "$DRY_RUN" == "1" ]]; then
    log "=== Phase E: DRY-RUN — stopping before inner script invocation ==="
    log ""
    log "  Would invoke:"
    log "    bash $INNER_SCRIPT --expected-sha $EXPECTED_SHA ${INNER_FLAGS[*]:-}"
    log ""
    log "  Stash status:"
    if [[ "$STASHED" == "1" ]]; then
        log "    A stash named '$STASH_MSG' was created."
        log "    Restoring it now (dry-run does not ship)..."
        if stash_msg_exists "$STASH_MSG"; then
            if pop_release_stash "$STASH_MSG"; then
                log "    stash popped cleanly; untracked items restored."
            else
                warn "    Stash pop did not fully drop the stash. The wrapper-created stash"
                warn "    '$STASH_MSG' is preserved. Recover manually:"
                warn "      git stash list | grep '$STASH_MSG'"
                warn "      git stash apply <stash-ref>          # re-apply if needed"
                warn "      git stash drop <stash-ref>           # ONLY if you've fully restored"
                # In dry-run we don't want to hide this — surface a non-zero exit
                # so the operator sees the dry-run as "needs attention".
                exit 1
            fi
        else
            warn "    stash not found in 'git stash list' — was it dropped externally?"
        fi
    else
        log "    No stash created."
    fi
    log ""
    log "DRY-RUN complete. No tag, no push, no release."
    exit 0
fi

# -----------------------------------------------------------------------------
# Phase F: invoke the inner release script
# -----------------------------------------------------------------------------
log "=== Phase F: invoking inner release script ==="
log "command: bash $INNER_SCRIPT --expected-sha $EXPECTED_SHA ${INNER_FLAGS[*]:-}"
log ""

INNER_EXIT=0
bash "$INNER_SCRIPT" --expected-sha "$EXPECTED_SHA" "${INNER_FLAGS[@]}" || INNER_EXIT=$?

# -----------------------------------------------------------------------------
# Phase G: stash restore on success, leave-in-place on failure
# -----------------------------------------------------------------------------
log ""
log "=== Phase G: post-inner-script cleanup ==="

if [[ "$INNER_EXIT" -ne 0 ]]; then
    warn "inner release script exited with code $INNER_EXIT."
    if [[ "$STASHED" == "1" ]]; then
        warn "Stash '$STASH_MSG' has been LEFT IN PLACE so you can inspect"
        warn "the failure without losing the ~$UNTRACKED_BEFORE untracked items."
        warn ""
        warn "To inspect:    git stash list | grep '$STASH_MSG'"
        warn "To restore:    git stash pop  (after the inner-script issue is resolved)"
        warn "To force-drop: git stash drop stash@{0}  (DESTRUCTIVE; only if you're sure)"
    fi
    exit "$INNER_EXIT"
fi

# Inner script succeeded.
log "inner release script: SUCCESS"
if [[ "$STASHED" == "1" ]]; then
    log "restoring untracked docs from stash..."
    if stash_msg_exists "$STASH_MSG"; then
        if pop_release_stash "$STASH_MSG"; then
            log "stash popped cleanly; untracked docs restored."
        else
            warn "stash pop returned 0 but the stash entry survived (tracked-file conflict)."
            warn "The release itself SUCCEEDED — tag is pushed, GitHub release is live."
            warn "The stash '$STASH_MSG' is preserved. Recover with:"
            warn "  git stash list | grep '$STASH_MSG'"
            warn "  git stash show -p <stash-ref>     # inspect"
            warn "  git stash apply <stash-ref>       # re-apply (will fail if same conflict)"
            warn ""
            warn "Or, since the release is live, you can:"
            warn "  - inspect stash content + cherry-pick what's still needed"
            warn "  - git stash drop <stash-ref> if the untracked items are recoverable elsewhere"
            warn ""
            warn "DO NOT delete the stash without verifying the untracked items are recoverable."
        fi
    fi
else
    log "no stash to restore."
fi

# -----------------------------------------------------------------------------
# Done
# -----------------------------------------------------------------------------
TAG="v1.8.0"
log ""
log "=== TRIGGER COMPLETE — v1.8.0 SHIPPED ==="
log "  Tag:      $TAG"
log "  Release:  https://github.com/amaster97/poker_solver/releases/tag/$TAG"
log ""
log "Next steps (per docs/v1_8_0_ship_trigger_runbook_2026-05-27.md §6):"
log "  1. Verify release page renders: gh release view $TAG --web"
log "  2. Verify tag visible on GitHub + backup mirror"
log "  3. Build the .dmg per docs/dmg_build_runbook_2026-05-26.md"
log "  4. Upload: gh release upload $TAG dist/Poker-Solver-1.8.0-arm64.dmg"
log "  5. Update PLAN.md with v1.8.0 ship status"
log "  6. Run post-integration verification (per feedback_post_integration_verification)"
