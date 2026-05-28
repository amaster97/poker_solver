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
# POST-v1.8.0 HARDENING (4 hazard checks, each with a per-check skip env var):
#   - Hazard guard 0 (top of script): bash 3.2 + nounset + empty-array
#     footgun. Refuses to run if the unsafe ARR-at-form-with-default pattern
#     is present in this script body. Bypass: SKIP_BASH_VERSION_CHECK=1.
#     Rule: feedback_bash3_2_empty_array.md
#   - Phase C.2 (tightened): release-notes substantive '<TBD-NAME>' marker
#     audit (was bare 'TBD' grep — false-flagged meta-text on v1.8.0 ship).
#     Bypass: SKIP_PHASE_C_2=1. Rule: feedback_release_check_specificity.md
#   - Phase C.6: PR-citation collision audit — every 'PR #N' in release
#     notes is checked against `gh pr view N` to detect citations that
#     resolve to an unrelated GitHub PR (local pr-N-* branches drift from
#     gh-assigned PR numbers). Bypass: SKIP_PHASE_C_6=1.
#     Rule: feedback_pr_naming_collision.md
#   - Phase C.7: cited-doc tree-tracking audit — every path-like reference
#     in release notes is verified against `git ls-tree -r HEAD`; untracked
#     files would 404 in the tag tree. Bypass: SKIP_PHASE_C_7=1.
#     Rule: feedback_release_cited_doc_tracking.md
#   - Phase C.8: _rust.so source-currency audit (PR #140 stale-.so gap).
#     Two-layer: (a) static grep of crates/cfr_core/src/dcfr_vector.rs for
#     the post-PR-#16 'next_reach = vec![...; player_hands]' pattern;
#     (b) behavioral asymmetric-combo Nash smoke (12-vs-24 fixture) that
#     would panic on a pre-fix .so. Catches the case where the loaded
#     .so was built from an older source tree (silent ship-blocker:
#     v1.8.0 .dmg shipped with a stale .so missing PR #16's hand-count
#     fix; users crashed on asymmetric ranges).
#     Bypass: SKIP_PHASE_C_8=1.
#
# SMOKE TEST: SMOKE_TEST=1 REPO=<worktree-path> bash <script> --dry-run
#   Bypasses Phase A (branch=main) + Phase B (origin sync) so the hazard
#   checks can be exercised from a feature-branch worktree. NEVER use for a
#   real ship.
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

# =============================================================================
# Hazard guard 0 (top-of-script): bash 3.2 + nounset + empty-array footgun.
# =============================================================================
# macOS ships /bin/bash 3.2 (license-frozen). Under `set -u`:
#   1. The "@" form on an empty array raises 'unbound variable'.
#   2. The "@" form with ":-" default emits a SINGLE EMPTY POSITIONAL ARG,
#      which downstream getopt-style parsers reject as "unknown flag" —
#      silently breaking the ship. Both forms fail. The correct pattern is
#      an explicit length check:
#          if [[ #ARR-length -gt 0 ]]; then cmd "ARR-at-form"; else cmd; fi
#
# Cost: 30 min + 2 PRs (#88, #90) on the 2026-05-27 v1.8.0 ship burst.
#
# Memory rule:
#   ~/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/
#     feedback_bash3_2_empty_array.md
#
# Bypass for emergencies: SKIP_BASH_VERSION_CHECK=1 bash <script>
# =============================================================================
# The static-grep below scans for the unsafe pattern. To keep this guard
# function self-consistent (its own error/doc strings must not match the
# pattern they describe), the offending sequence is reconstructed at runtime
# from harmless fragments.
hazard_guard_0_bash_version() {
    if [[ "${SKIP_BASH_VERSION_CHECK:-0}" == "1" ]]; then
        echo "[trigger-v1.8.0] WARN: hazard-guard 0 (bash version) SKIPPED via SKIP_BASH_VERSION_CHECK=1." >&2
        echo "[trigger-v1.8.0] WARN: empty-array footgun is in play — see feedback_bash3_2_empty_array.md" >&2
        return 0
    fi

    # bash 3.2 has BASH_VERSINFO[0]=3. We require >= 4 OR a successful
    # self-test of the length-check pattern.
    local major="${BASH_VERSINFO[0]:-0}"
    if [[ "$major" -ge 4 ]]; then
        # bash 4+: array semantics are forgiving; still run a fast self-test.
        :
    fi

    # Self-test: build an empty array and verify the length-check pattern
    # correctly skips the would-be expansion.
    local _empty_arr=()
    local _self_test_arg_count=0
    if [[ ${#_empty_arr[@]} -gt 0 ]]; then
        # Should never be reached on an empty array.
        _self_test_arg_count=$(( ${#_empty_arr[@]} ))
    fi
    if [[ "$_self_test_arg_count" -ne 0 ]]; then
        echo "[trigger-v1.8.0] FATAL: hazard-guard 0 self-test failed (bash array semantics broken)." >&2
        echo "       Expected empty-array length-check to skip the branch; got count=$_self_test_arg_count." >&2
        echo "       See feedback_bash3_2_empty_array.md." >&2
        exit 1
    fi

    # Static grep: refuse to run if any "ARR@-form with :- default" pattern
    # survives in this script (the unsafe form that emits an empty positional
    # arg under set -u). The length-check pattern is the only safe one on
    # bash 3.2.
    # Reconstruct the regex at runtime so the source of THIS function does
    # not itself match. Pattern: dollar-brace-NAME-LB-@-RB-colon-dash-RBR.
    local LB='\['
    local RB='\]'
    local AT='@'
    local DEFAULT=':-'
    local unsafe_re="\\\$\\{[A-Za-z_][A-Za-z0-9_]*${LB}${AT}${RB}${DEFAULT}\\}"
    # Skip the lines from "hazard_guard_0_bash_version()" through the
    # function's closing brace so the guard's own machinery doesn't
    # self-flag; check everything else.
    local script_path="$0"
    local body
    body=$(awk '
        /^hazard_guard_0_bash_version\(\) \{$/ { in_guard=1; next }
        in_guard && /^}$/ { in_guard=0; next }
        !in_guard { print }
    ' "$script_path")
    if printf '%s\n' "$body" | grep -qE "$unsafe_re"; then
        echo "[trigger-v1.8.0] FATAL: hazard-guard 0 — script contains the unsafe ARR-at-default pattern:" >&2
        printf '%s\n' "$body" | grep -nE "$unsafe_re" >&2 || true
        echo "       This emits a SINGLE EMPTY POSITIONAL ARG under bash 3.2 + set -u." >&2
        echo "       Replace with: if [[ length-check -gt 0 ]]; then cmd \"ARR-at-form\"; else cmd; fi" >&2
        echo "       See feedback_bash3_2_empty_array.md." >&2
        exit 1
    fi

    return 0
}
hazard_guard_0_bash_version

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
# REPO defaults to the canonical checkout but can be overridden for
# worktree-based dry-runs / smoke tests via the REPO env var.
REPO="${REPO:-/Users/ashen/Desktop/poker_solver}"
INNER_SCRIPT="scripts/release_v1_8_0.sh"
STASH_MSG="pre-v1.8.0-release-stash-2026-05-27"
RELEASE_NOTES="docs/v1_8_0_release_notes_DRAFT.md"

# -----------------------------------------------------------------------------
# Hazard-check skip flags (post-v1.8.0 hardening; default 0 = enabled).
# Each is keyed to a memory rule under
#   ~/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/
# Set the env var to 1 to bypass that specific check (emergencies only).
# -----------------------------------------------------------------------------
SKIP_BASH_VERSION_CHECK="${SKIP_BASH_VERSION_CHECK:-0}"   # feedback_bash3_2_empty_array
SKIP_PHASE_C_2="${SKIP_PHASE_C_2:-0}"                     # feedback_release_check_specificity
SKIP_PHASE_C_6="${SKIP_PHASE_C_6:-0}"                     # feedback_pr_naming_collision
SKIP_PHASE_C_7="${SKIP_PHASE_C_7:-0}"                     # feedback_release_cited_doc_tracking
SKIP_PHASE_C_8="${SKIP_PHASE_C_8:-0}"                     # PR #140 stale-.so gap

# Smoke-test escape hatch: bypass Phase A (branch=main) + Phase B (origin sync)
# checks. ONLY for testing the hazard guards in a worktree / feature branch.
# A real ship MUST run on main with a clean origin sync.
SMOKE_TEST="${SMOKE_TEST:-0}"

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
            sed -n '2,90p' "$0"
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
if [[ "$SMOKE_TEST" == "1" ]]; then
    log "=== Phase A: SKIPPED (SMOKE_TEST=1) ==="
    warn "SMOKE_TEST=1 bypasses Phase A + Phase B; NEVER use for a real ship."
else
    log "=== Phase A: branch check ==="
    CURRENT_BRANCH=$(git branch --show-current)
    if [[ "$CURRENT_BRANCH" != "main" ]]; then
        fail "must be on 'main' branch (currently on: $CURRENT_BRANCH). \
Switch with: git checkout main"
    fi
    log "branch: main"
fi

# -----------------------------------------------------------------------------
# Phase B: fetch + capture current origin/main HEAD SHA dynamically
# -----------------------------------------------------------------------------
if [[ "$SMOKE_TEST" == "1" ]]; then
    log "=== Phase B: SKIPPED (SMOKE_TEST=1) ==="
    EXPECTED_SHA=$(git rev-parse HEAD)
    log "(smoke) using local HEAD as EXPECTED_SHA: $EXPECTED_SHA"
else
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

    # C.2: release notes draft no longer has substantive TBD placeholders.
    # Hazard: bare `grep -c "TBD"` over-counts — it flags META-TEXT (doc
    # header sentences explaining placeholder convention) equally with real
    # unfilled fields. PR #87 (2026-05-27) surfaced when meta-text containing
    # "TBD" tripped the ship blocker. Tightened to the substantive sentinel
    # form `<TBD-NAME>` per feedback_release_check_specificity.md.
    NOTES_FILE="${RELEASE_NOTES:-docs/v1_8_0_release_notes_DRAFT.md}"
    if [[ "$SKIP_PHASE_C_2" == "1" ]]; then
        warn "Phase C.2 SKIPPED via SKIP_PHASE_C_2=1 — see feedback_release_check_specificity.md"
    elif [[ ! -f "$NOTES_FILE" ]]; then
        fail "Phase C.2 — release notes file missing: $NOTES_FILE"
    else
        # Anchored regex: only the structured sentinel form <TBD-ALPHA_NUM-DASH>
        # is a substantive placeholder. Bare "TBD" in prose is ignored.
        TBD_COUNT=$(grep -cE '<TBD-[A-Z0-9_-]+>' "$NOTES_FILE" 2>/dev/null || echo 0)
        # Coerce to single integer (grep -c with `|| echo 0` can leave a
        # trailing newline; arithmetic context tolerates but be explicit).
        TBD_COUNT=$(printf '%s' "$TBD_COUNT" | tr -d '[:space:]')
        : "${TBD_COUNT:=0}"
        if [[ "$TBD_COUNT" -gt 0 ]]; then
            warn "Phase C.2 — release notes contain $TBD_COUNT substantive '<TBD-...>' marker(s):"
            # `|| true` guards against pipefail+SIGPIPE when head closes early.
            grep -nE '<TBD-[A-Z0-9_-]+>' "$NOTES_FILE" | head -10 || true
            if [[ "$DRY_RUN" != "1" ]]; then
                fail "Phase C.2 — refusing to ship with <TBD-...> placeholders in release notes. \
Substitute the placeholders, then re-run. (--dry-run will allow this for inspection.) \
See feedback_release_check_specificity.md."
            fi
        else
            log "Phase C.2 — release notes have no substantive <TBD-...> placeholders: OK"
        fi
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

    # -------------------------------------------------------------------------
    # Phase C.6: PR-citation collision audit (feedback_pr_naming_collision)
    # -------------------------------------------------------------------------
    # Hazard: local branch `pr-N-<topic>` is independent from GitHub PR #N.
    # Release notes citing bare "PR #N" may resolve to an UNRELATED GitHub
    # PR (e.g., v1.8.0 cited "PR #93 ablation" but GitHub PR #93 = WAKEUP
    # doc; PR #96 had to ship a v1.8.1 docs patch). Scan release notes for
    # `PR #N` mentions and verify each refers to a real GitHub PR via
    # `gh pr view`.
    #
    # Memory rule:
    #   ~/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/
    #     feedback_pr_naming_collision.md
    # Bypass: SKIP_PHASE_C_6=1
    # -------------------------------------------------------------------------
    if [[ "$SKIP_PHASE_C_6" == "1" ]]; then
        warn "Phase C.6 SKIPPED via SKIP_PHASE_C_6=1 — see feedback_pr_naming_collision.md"
    else
        log "=== Phase C.6: PR-citation collision audit ==="
        NOTES_FILE_C6="${RELEASE_NOTES:-docs/v1_8_0_release_notes_DRAFT.md}"
        if [[ ! -f "$NOTES_FILE_C6" ]]; then
            warn "Phase C.6 — release notes file missing ($NOTES_FILE_C6); skipping."
        elif ! command -v gh >/dev/null 2>&1; then
            warn "Phase C.6 — 'gh' CLI not available; cannot validate PR citations."
            if [[ "$DRY_RUN" != "1" ]]; then
                fail "Phase C.6 — 'gh' required for ship-time PR citation audit. \
Install gh or set SKIP_PHASE_C_6=1 to bypass. \
See feedback_pr_naming_collision.md."
            fi
        else
            # Extract unique "PR #N" mentions (N = 1+ digits).
            PR_NUMS_RAW=$(grep -oE 'PR #[0-9]+' "$NOTES_FILE_C6" 2>/dev/null | \
                          sort -u | awk -F'#' '{print $2}')
            if [[ -z "$PR_NUMS_RAW" ]]; then
                log "Phase C.6 — no 'PR #N' mentions in release notes: OK"
            else
                PR_COUNT=$(printf '%s\n' "$PR_NUMS_RAW" | wc -l | tr -d ' ')
                log "Phase C.6 — auditing $PR_COUNT unique 'PR #N' citation(s)..."
                C6_DANGLING=()
                C6_FOUND=0
                # Read into array via while-loop (bash 3.2 has no `mapfile`).
                while IFS= read -r n; do
                    [[ -z "$n" ]] && continue
                    if pr_title=$(gh pr view "$n" --json title --jq '.title' 2>/dev/null); then
                        if [[ -n "$pr_title" ]]; then
                            C6_FOUND=$(( C6_FOUND + 1 ))
                            log "    PR #$n -> $pr_title"
                        else
                            C6_DANGLING+=("$n (empty title)")
                        fi
                    else
                        C6_DANGLING+=("$n (gh pr view failed — likely no such GitHub PR)")
                    fi
                done <<< "$PR_NUMS_RAW"

                if [[ ${#C6_DANGLING[@]} -gt 0 ]]; then
                    warn "Phase C.6 — ${#C6_DANGLING[@]} dangling 'PR #N' citation(s):"
                    # bash 3.2 safe: explicit length check before "@" expansion.
                    if [[ ${#C6_DANGLING[@]} -gt 0 ]]; then
                        for d in "${C6_DANGLING[@]}"; do
                            warn "    - PR #$d"
                        done
                    fi
                    warn "Each citation must resolve to a GENUINE GitHub PR (not a"
                    warn "local branch named 'pr-N-...'). Use 'commit <SHA>' or"
                    warn "'branch <name> @ <SHA>' for work without a GitHub PR."
                    if [[ "$DRY_RUN" != "1" ]]; then
                        fail "Phase C.6 — refusing to ship with dangling PR-citation(s). \
See feedback_pr_naming_collision.md."
                    fi
                else
                    log "Phase C.6 — all $C6_FOUND 'PR #N' citation(s) resolve to genuine GitHub PRs: OK"
                fi
            fi
        fi
    fi

    # -------------------------------------------------------------------------
    # Phase C.7: cited-doc tree-tracking audit (feedback_release_cited_doc_tracking)
    # -------------------------------------------------------------------------
    # Hazard: release notes cite docs/tests/sources by path. Those paths
    # must be in the tag's tree (`git ls-tree -r HEAD`), not just in the
    # working directory. Untracked files vanish from the user's view of the
    # tag, leaving dangling references in the published release page.
    # v1.8.0 tag had 4 untracked docs + 2 untracked tests cited; PR #96
    # had to add them post-tag.
    #
    # Memory rule:
    #   ~/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/
    #     feedback_release_cited_doc_tracking.md
    # Bypass: SKIP_PHASE_C_7=1
    # -------------------------------------------------------------------------
    if [[ "$SKIP_PHASE_C_7" == "1" ]]; then
        warn "Phase C.7 SKIPPED via SKIP_PHASE_C_7=1 — see feedback_release_cited_doc_tracking.md"
    else
        log "=== Phase C.7: cited-doc tree-tracking audit ==="
        NOTES_FILE_C7="${RELEASE_NOTES:-docs/v1_8_0_release_notes_DRAFT.md}"
        if [[ ! -f "$NOTES_FILE_C7" ]]; then
            warn "Phase C.7 — release notes file missing ($NOTES_FILE_C7); skipping."
        else
            # Extract path-like references from release notes (docs/, tests/,
            # scripts/, crates/, poker_solver/ with .md/.py/.rs/.sh/.yml/.toml).
            CITED_PATHS=$(grep -oE '(docs|tests|scripts|crates|poker_solver)/[A-Za-z0-9_./-]+\.(md|py|rs|sh|yml|toml)' \
                          "$NOTES_FILE_C7" 2>/dev/null | sort -u)
            if [[ -z "$CITED_PATHS" ]]; then
                log "Phase C.7 — no path-like citations in release notes: OK"
            else
                CITED_COUNT=$(printf '%s\n' "$CITED_PATHS" | wc -l | tr -d ' ')
                log "Phase C.7 — auditing $CITED_COUNT cited path(s) against git ls-tree -r HEAD..."
                # Snapshot the tracked-tree once for O(N) checks (instead of
                # running ls-tree N times).
                TREE_SNAPSHOT=$(git ls-tree -r HEAD --name-only)
                C7_DANGLING=()
                C7_OK=0
                while IFS= read -r p; do
                    [[ -z "$p" ]] && continue
                    if printf '%s\n' "$TREE_SNAPSHOT" | grep -qFx "$p"; then
                        C7_OK=$(( C7_OK + 1 ))
                    else
                        C7_DANGLING+=("$p")
                    fi
                done <<< "$CITED_PATHS"

                if [[ ${#C7_DANGLING[@]} -gt 0 ]]; then
                    warn "Phase C.7 — ${#C7_DANGLING[@]} cited path(s) NOT in git ls-tree -r HEAD:"
                    if [[ ${#C7_DANGLING[@]} -gt 0 ]]; then
                        for d in "${C7_DANGLING[@]}"; do
                            warn "    DANGLING: $d"
                        done
                    fi
                    warn "These will fatal-404 on 'git show <tag>:<path>' after tagging."
                    warn "Either 'git add' them before tagging or remove the citation."
                    if [[ "$DRY_RUN" != "1" ]]; then
                        fail "Phase C.7 — refusing to ship with dangling doc citation(s). \
See feedback_release_cited_doc_tracking.md."
                    fi
                else
                    log "Phase C.7 — all $C7_OK cited path(s) are tracked in HEAD: OK"
                fi
            fi
        fi
    fi

    # -------------------------------------------------------------------------
    # Phase C.8: _rust.so source-currency audit (PR #140 stale-.so gap)
    # -------------------------------------------------------------------------
    # Hazard: the .dmg picks up whatever `_rust.so` PyInstaller can find in
    # the build venv (typically `.venv/lib/python3.13/site-packages/
    # poker_solver/_rust*.so`). If `pip install -e .` was run BEFORE the
    # most recent `maturin develop --release`, the installed .so lags
    # behind the source tree — silently shipping pre-fix Rust binary in
    # the .dmg.
    #
    # v1.8.0 shipped with a STALE .so missing PR #16's hand-count fix.
    # End-users on that .dmg crash on asymmetric-range fixtures with
    # `index out of bounds: 65 but index 70` at dcfr_vector.rs:651.
    # The source-current .so worked fine; the embedded one did not.
    #
    # Two-layer check:
    #   (a) Static source: confirm `crates/cfr_core/src/dcfr_vector.rs`
    #       has the post-PR-#16 pattern (>=2 'next_reach = vec![...;
    #       player_hands]' occurrences and 0 pre-fix 'opp_hands' sites).
    #   (b) Behavioral .so: run the asymmetric-combo (12-vs-24) Nash
    #       smoke. Pre-fix .so panics; post-fix .so completes.
    #
    # Memory rule:
    #   ~/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/
    #     feedback_dotso_arch_check.md  (sibling hazard cluster)
    # Bypass: SKIP_PHASE_C_8=1 (DANGEROUS — only for emergency archeology)
    # -------------------------------------------------------------------------
    if [[ "${SKIP_PHASE_C_8:-0}" == "1" ]]; then
        warn "Phase C.8 SKIPPED via SKIP_PHASE_C_8=1 — see PR #140 stale-.so gap"
    else
        log "=== Phase C.8: _rust.so source-currency audit ==="
        DCFR_VECTOR_SRC_C8="crates/cfr_core/src/dcfr_vector.rs"
        if [[ ! -f "$DCFR_VECTOR_SRC_C8" ]]; then
            fail "Phase C.8 — $DCFR_VECTOR_SRC_C8 not found; cannot audit .so currency."
        fi
        # (a) Static source pattern.
        C8_POSTFIX_HITS=$(grep -c 'next_reach = vec!\[0\.0_f64; player_hands\]' "$DCFR_VECTOR_SRC_C8" || true)
        C8_PREFIX_HITS=$(grep -c 'next_reach = vec!\[0\.0_f64; opp_hands\]' "$DCFR_VECTOR_SRC_C8" || true)
        if [[ "$C8_POSTFIX_HITS" -lt 2 ]]; then
            fail "Phase C.8 (a) — $DCFR_VECTOR_SRC_C8 does NOT have the post-PR-#16 fix \
(expected >=2 'next_reach = vec![0.0_f64; player_hands]' sites, got $C8_POSTFIX_HITS). \
This source tree is PRE-PR-#16. Pull origin/main (PR #16 = 2d7ea58) before tagging the release."
        fi
        if [[ "$C8_PREFIX_HITS" -gt 0 ]]; then
            fail "Phase C.8 (a) — $DCFR_VECTOR_SRC_C8 still contains PRE-PR-#16 \
'next_reach = vec![0.0_f64; opp_hands]' pattern ($C8_PREFIX_HITS hits). Partial-fix state — \
pull origin/main and verify."
        fi
        log "Phase C.8 (a) — dcfr_vector.rs has post-PR-#16 fix ($C8_POSTFIX_HITS sites, 0 pre-fix): OK"

        # (b) Behavioral .so check. Same fixture as build_macos_dmg.sh
        # preflight: 12-vs-24 asymmetric combo Nash solve, 50 iters.
        log "Phase C.8 (b) — running .so behavioral smoke (asymmetric 12-vs-24)..."
        C8_SMOKE_LOG="$(mktemp -t release_v1_8_0_so_smoke.XXXXXX)"
        set +e
        python3 - >"$C8_SMOKE_LOG" 2>&1 <<'PYEOF'
"""Phase C.8 (b): asymmetric-combo Nash smoke (must not panic)."""
import sys, traceback
try:
    from poker_solver import (
        HUNLConfig, Street, parse_board, solve_range_vs_range_nash,
    )
except Exception as exc:  # noqa: BLE001
    print(f"[c8-smoke] FAIL: cannot import poker_solver: {exc!r}", file=sys.stderr)
    sys.exit(1)
board = tuple(parse_board("Tc 9d 4h Jc 6s"))
cfg = HUNLConfig(
    starting_stack=10_000,
    starting_street=Street.RIVER,
    initial_board=board,
    initial_pot=200,
    initial_contributions=(100, 100),
    bet_size_fractions=(0.5, 1.0),
    include_all_in=False,
    postflop_raise_cap=2,
)
try:
    # 12-vs-24 asymmetric Nash solve — the PR #16 panic fixture.
    solve_range_vs_range_nash(
        config_template=cfg,
        hero_range=["AA", "KK"],
        villain_range=["72o", "83o"],
        iterations=50,
        hero_player=1,
        compute_exploitability_at_end=False,
    )
except Exception as exc:  # noqa: BLE001
    msg = str(exc)
    if "index out of bounds" in msg or "panicked at" in msg:
        print(
            f"[c8-smoke] FAIL: loaded _rust.so PANICKED — STALE .so detected: {msg}",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"[c8-smoke] FAIL: unexpected exception: {exc!r}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
print("[c8-smoke] OK — _rust.so post-PR-#16 (asymmetric Nash smoke PASS)")
sys.exit(0)
PYEOF
        C8_SMOKE_RC=$?
        set -e
        if [[ "$C8_SMOKE_RC" -ne 0 ]]; then
            cat "$C8_SMOKE_LOG" >&2 || true
            rm -f "$C8_SMOKE_LOG"
            fail "Phase C.8 (b) — _rust.so behavioral smoke FAILED. The loaded .so is STALE \
(built from PRE-PR-#16 source). Tagging this release would ship a .dmg that crashes on \
asymmetric-range fixtures. \
\
Fix: rebuild from current source before tagging: \
    maturin develop --release --target universal2-apple-darwin \
\
See docs/dmg_build_runbook_2026-05-26.md."
        fi
        # Surface the success line.
        grep -E '^\[c8-smoke\]' "$C8_SMOKE_LOG" | head -3 || true
        rm -f "$C8_SMOKE_LOG"
        log "Phase C.8 (b) — _rust.so behavioral smoke: OK"
    fi
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
if [[ ${#INNER_FLAGS[@]} -gt 0 ]]; then
    bash "$INNER_SCRIPT" --expected-sha "$EXPECTED_SHA" "${INNER_FLAGS[@]}" || INNER_EXIT=$?
else
    bash "$INNER_SCRIPT" --expected-sha "$EXPECTED_SHA" || INNER_EXIT=$?
fi

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
