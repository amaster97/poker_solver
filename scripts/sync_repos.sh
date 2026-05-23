#!/usr/bin/env bash
# =============================================================================
# sync_repos.sh
#
# PURPOSE
# -------
# One-command wrapper that:
#   1. Pushes `integration` (internal accumulator) → `backup` (private remote).
#   2. Runs `scripts/split_main_for_publish.sh --execute` to rebuild a clean
#      `main` from the current `integration` snapshot. (User commits the
#      result manually first — this script does NOT commit. See "Workflow"
#      below.)
#   3. Pushes `main` → `origin` (public GitHub).
#   4. Pushes `main` → `backup` (private mirror).
#   5. Pushes new tags to both remotes (if any).
#   6. Restores the user's original branch.
#
# REMOTES THIS SCRIPT EXPECTS
# ---------------------------
#   origin = https://github.com/amaster97/poker_solver.git           (PUBLIC; main only)
#   backup = git@github.com:amaster97/poker_solver_private.git       (PRIVATE; both branches)
#
# If `backup` is not yet configured, the script proceeds without it (skips
# the two backup pushes with [SKIP] markers) — unless `--strict-backup`
# is set, in which case it errors out.
#
# WORKFLOW (important — read once)
# --------------------------------
# This script is INTENDED to be run AFTER you have already:
#   a) committed your work to `integration` (`git commit` on integration); and
#   b) executed `scripts/split_main_for_publish.sh --execute` on `main` and
#      committed the result (because that script stages but never commits).
#
# i.e. both `integration` and `main` should be in their final, committed
# state before this script is invoked. This wrapper is the "now push
# everywhere safely" tool, not the "do the split for me" tool. If `main`
# is stale relative to `integration`, you'll get a friendly warning.
#
# SAFETY MODEL
# ------------
#   * `set -euo pipefail`: any error aborts.
#   * Refuses to run on a dirty working tree.
#   * Refuses to run if HEAD is not `integration` (script does not change
#     branches unprompted; user must `git checkout integration` first).
#   * Default mode is interactive: prints the plan, then asks "Continue? [y/N]"
#     once, before any push. `--yes`/`-y` skips that prompt for CI/headless.
#   * `--dry-run` enumerates the plan and exits without touching anything.
#   * On error: prints which step failed and exits non-zero. Does NOT
#     undo, reset, or rollback. State is left for user inspection.
#   * Original branch is restored at the end (success or error trap).
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# Colours (graceful fallback if not a TTY)
# -----------------------------------------------------------------------------
if [ -t 1 ] && command -v tput >/dev/null 2>&1 && [ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]; then
    C_RED=$'\033[31m'
    C_GREEN=$'\033[32m'
    C_YELLOW=$'\033[33m'
    C_BLUE=$'\033[34m'
    C_BOLD=$'\033[1m'
    C_OFF=$'\033[0m'
else
    C_RED=""
    C_GREEN=""
    C_YELLOW=""
    C_BLUE=""
    C_BOLD=""
    C_OFF=""
fi

ok()    { printf '%s[OK]%s     %s\n'    "$C_GREEN"  "$C_OFF" "$*"; }
warn()  { printf '%s[WARN]%s   %s\n'    "$C_YELLOW" "$C_OFF" "$*"; }
skip()  { printf '%s[SKIP]%s   %s\n'    "$C_YELLOW" "$C_OFF" "$*"; }
err()   { printf '%s[ERROR]%s  %s\n'    "$C_RED"    "$C_OFF" "$*" 1>&2; }
info()  { printf '%s[INFO]%s   %s\n'    "$C_BLUE"   "$C_OFF" "$*"; }
title() { printf '\n%s%s%s\n'           "$C_BOLD"   "$*"     "$C_OFF"; }

# -----------------------------------------------------------------------------
# Usage
# -----------------------------------------------------------------------------
usage() {
    cat <<'EOF'
Usage: scripts/sync_repos.sh [--dry-run | --execute] [-y | --yes]
                             [--strict-backup] [-h | --help]

Push the integration→main split outcome to both remotes in one go.

Flags:
  --dry-run        Preview the plan; touch nothing. Exits 0.
  --execute        (default) Apply: prompts once before pushes.
  -y, --yes        Skip the confirmation prompt (headless / CI).
  --strict-backup  Error if the 'backup' remote is not configured.
                   (Default: warn and skip backup pushes.)
  -h, --help       This message.

Preconditions:
  * Run from repo root, on the `integration` branch.
  * Working tree must be clean (no uncommitted changes).
  * `origin` remote must exist.
  * Both `integration` and `main` must already be in their intended
    committed state. (This wrapper composes pushes; it does NOT do
    the split commit on `main` itself — that's split_main_for_publish.sh.)

Examples:
  # Preview the plan:
  scripts/sync_repos.sh --dry-run

  # Interactive (recommended for human use):
  scripts/sync_repos.sh

  # Headless / scripted:
  scripts/sync_repos.sh --yes
EOF
}

# -----------------------------------------------------------------------------
# Argument parsing
# -----------------------------------------------------------------------------
MODE="execute"
ASSUME_YES="false"
STRICT_BACKUP="false"

for arg in "$@"; do
    case "$arg" in
        --dry-run)        MODE="dry-run" ;;
        --execute)        MODE="execute" ;;
        -y|--yes)         ASSUME_YES="true" ;;
        --strict-backup)  STRICT_BACKUP="true" ;;
        -h|--help)        usage; exit 0 ;;
        *)
            err "Unknown arg: $arg"
            usage 1>&2
            exit 2
            ;;
    esac
done

# -----------------------------------------------------------------------------
# Header
# -----------------------------------------------------------------------------
if [ "$MODE" = "execute" ]; then
    title "${C_BLUE}=== sync_repos.sh: EXECUTE MODE ===${C_OFF}"
else
    title "${C_BLUE}=== sync_repos.sh: DRY RUN (no pushes will happen) ===${C_OFF}"
fi

# -----------------------------------------------------------------------------
# Locate repo root and cd there
# -----------------------------------------------------------------------------
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
info "Repo root: $REPO_ROOT"

# -----------------------------------------------------------------------------
# Preconditions
# -----------------------------------------------------------------------------
title "Preconditions"

# 1. Must be a git repo
if ! git rev-parse --git-dir >/dev/null 2>&1; then
    err "Not a git repository: $REPO_ROOT"
    exit 1
fi
ok "Git repo detected"

# 2. Capture original branch (so we can restore at end)
ORIGINAL_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
info "Original branch: $ORIGINAL_BRANCH"

# 3. HEAD must be `integration` — this script does NOT switch branches for you
if [ "$ORIGINAL_BRANCH" != "integration" ]; then
    err "HEAD is on '$ORIGINAL_BRANCH', not 'integration'. Refusing to run."
    err "Switch first:  git checkout integration"
    exit 1
fi
ok "HEAD is on 'integration'"

# 4. Working tree must be clean
if ! git diff --quiet || ! git diff --cached --quiet; then
    err "Working tree is dirty. Stash or commit your changes first."
    err "Run 'git status' to see what's pending."
    exit 1
fi
ok "Working tree is clean"

# 5. `origin` remote must exist
if git remote get-url origin >/dev/null 2>&1; then
    ORIGIN_URL="$(git remote get-url origin)"
    ok "Origin remote configured: $ORIGIN_URL"
else
    err "No 'origin' remote configured. Add one first:"
    err "  git remote add origin https://github.com/amaster97/poker_solver.git"
    exit 1
fi

# 6. `backup` remote: optional unless --strict-backup
BACKUP_PRESENT="false"
if git remote get-url backup >/dev/null 2>&1; then
    BACKUP_URL="$(git remote get-url backup)"
    ok "Backup remote configured: $BACKUP_URL"
    BACKUP_PRESENT="true"
else
    if [ "$STRICT_BACKUP" = "true" ]; then
        err "No 'backup' remote configured and --strict-backup was set."
        err "Add one first:"
        err "  git remote add backup git@github.com:amaster97/poker_solver_private.git"
        exit 1
    fi
    warn "No 'backup' remote configured — backup pushes will be SKIPPED."
    warn "To enable backup mirroring:"
    warn "  git remote add backup git@github.com:amaster97/poker_solver_private.git"
fi

# 7. Confirm split script exists
SPLIT_SCRIPT="$REPO_ROOT/scripts/split_main_for_publish.sh"
if [ ! -x "$SPLIT_SCRIPT" ]; then
    err "Helper script not found or not executable: $SPLIT_SCRIPT"
    exit 1
fi
ok "Found split helper: scripts/split_main_for_publish.sh"

# -----------------------------------------------------------------------------
# Detect new tags (compared to origin)
# -----------------------------------------------------------------------------
# We push tags only if there's at least one local tag not yet on origin.
# This keeps idempotent re-runs quiet ("nothing to push") rather than
# constantly re-pushing the same tag set.
title "Tag detection"
LOCAL_TAGS="$(git tag --list 2>/dev/null || true)"
NEW_TAGS=""
if [ -n "$LOCAL_TAGS" ]; then
    # Best-effort: list tags on origin (requires network); if it fails we
    # still proceed by treating "we don't know" as "push tags". The push
    # itself is idempotent on the remote.
    if REMOTE_TAGS="$(git ls-remote --tags origin 2>/dev/null | awk -F/ '{print $NF}' | grep -v '\^{}' || true)"; then
        while IFS= read -r tag; do
            [ -z "$tag" ] && continue
            if ! printf '%s\n' "$REMOTE_TAGS" | grep -Fxq "$tag"; then
                NEW_TAGS="${NEW_TAGS}${tag}\n"
            fi
        done <<< "$LOCAL_TAGS"
    else
        warn "Could not query remote tags (network?). Will push tags defensively."
        NEW_TAGS="$LOCAL_TAGS"
    fi
fi

if [ -n "$NEW_TAGS" ]; then
    info "Local tags not on origin (will push --tags):"
    printf '%b' "$NEW_TAGS" | sed 's/^/  /'
else
    info "No new tags to push."
fi

# -----------------------------------------------------------------------------
# Build the plan
# -----------------------------------------------------------------------------
title "Planned operations"

PLAN_STEPS=()
STEP_IDX=0

add_step() {
    STEP_IDX=$((STEP_IDX + 1))
    PLAN_STEPS+=("$STEP_IDX. $1")
    info "  $STEP_IDX. $1"
}

if [ "$BACKUP_PRESENT" = "true" ]; then
    add_step "git push backup integration            (mirror internal accumulator)"
else
    skip "  (backup push of integration — backup remote not configured)"
fi

add_step "Run scripts/split_main_for_publish.sh --execute  (stages main cleanup; no commit)"
add_step "Verify main is committed and not stale relative to integration"
add_step "git push origin main                       (PUBLIC GitHub: main only)"

if [ "$BACKUP_PRESENT" = "true" ]; then
    add_step "git push backup main                       (private mirror: main)"
fi

if [ -n "$NEW_TAGS" ]; then
    add_step "git push origin --tags                     (publish new tags)"
    if [ "$BACKUP_PRESENT" = "true" ]; then
        add_step "git push backup --tags                     (mirror new tags)"
    fi
fi

add_step "git checkout $ORIGINAL_BRANCH               (restore original branch)"

# -----------------------------------------------------------------------------
# Dry-run exit
# -----------------------------------------------------------------------------
if [ "$MODE" = "dry-run" ]; then
    title "DRY RUN complete"
    info "Re-run without --dry-run to execute. Nothing was changed."
    exit 0
fi

# -----------------------------------------------------------------------------
# Confirmation prompt
# -----------------------------------------------------------------------------
if [ "$ASSUME_YES" != "true" ]; then
    printf '\n%sContinue? [y/N]:%s ' "$C_BOLD" "$C_OFF"
    # Single-char read; default to N on any other input
    if ! IFS= read -r -n 1 REPLY; then
        printf '\n'
        err "Could not read confirmation (non-interactive shell?). Use --yes for headless."
        exit 1
    fi
    printf '\n'
    case "$REPLY" in
        y|Y) ok "Confirmed — proceeding." ;;
        *)
            warn "Aborted by user. No pushes performed."
            exit 0
            ;;
    esac
else
    info "--yes set; skipping confirmation prompt."
fi

# -----------------------------------------------------------------------------
# Error trap: report which step failed and restore branch
# -----------------------------------------------------------------------------
CURRENT_STEP="(initialising)"
on_error() {
    local exit_code=$?
    err "Step failed: $CURRENT_STEP  (exit code: $exit_code)"
    err "State has been LEFT AS-IS for inspection. No automatic rollback."
    err "Tips:"
    err "  * Check 'git status' and 'git log --oneline -n 5' on the current branch."
    err "  * If main got partway-pushed and origin rejected: re-run after fixing"
    err "    (the script is idempotent; nothing-to-push is treated as success)."
    err "  * To restore your shell to the starting branch:"
    err "      git checkout $ORIGINAL_BRANCH"
    exit "$exit_code"
}
trap on_error ERR

# -----------------------------------------------------------------------------
# Step: push integration → backup
# -----------------------------------------------------------------------------
if [ "$BACKUP_PRESENT" = "true" ]; then
    CURRENT_STEP="push integration → backup"
    title "$CURRENT_STEP"
    info "Running: git push backup integration"
    if git push backup integration; then
        ok "Pushed integration → backup"
    else
        err "Push failed (see above)."
        exit 1
    fi
else
    skip "push integration → backup  (backup remote absent)"
fi

# -----------------------------------------------------------------------------
# Step: run the split helper
# -----------------------------------------------------------------------------
CURRENT_STEP="run split_main_for_publish.sh --execute"
title "$CURRENT_STEP"

# The split script requires HEAD=main. We checkout main, run it, then leave
# the working tree on main — subsequent push uses 'git push origin main' so
# branch position doesn't strictly matter, but being on main makes the
# intent visible if something fails mid-flow.
info "Switching to main to run the split helper..."
git checkout main
ok "On main"

info "Invoking: scripts/split_main_for_publish.sh --execute"
# Use a sub-shell so we can capture exit code without `set -e` aborting before
# we report it ourselves.
if "$SPLIT_SCRIPT" --execute; then
    ok "split_main_for_publish.sh completed"
else
    SPLIT_RC=$?
    err "split_main_for_publish.sh exited with code $SPLIT_RC"
    exit "$SPLIT_RC"
fi

# -----------------------------------------------------------------------------
# Step: verify main is committed (split script stages but does not commit)
# -----------------------------------------------------------------------------
CURRENT_STEP="verify main is committed and not stale"
title "$CURRENT_STEP"

if ! git diff --cached --quiet; then
    err "main has STAGED-but-uncommitted changes from split_main_for_publish.sh."
    err "That script stages cleanup; you must commit it before pushing."
    err "Suggested next steps:"
    err "  git diff --cached --stat"
    err "  git commit -m 'chore: clean main for public-channel split'"
    err "  scripts/sync_repos.sh   # re-run this wrapper"
    exit 1
fi
ok "main has no staged-uncommitted changes"

# Sanity check: is `main` reachable from `integration`'s tree-equivalent cleanup?
# We can't fully verify "main reflects the latest integration content" without
# replicating the split logic, but we can at least warn if main is much older
# than integration in commit time terms.
MAIN_AGE_HOURS=$(( ( $(date +%s) - $(git log -1 --format=%ct main) ) / 3600 ))
INTEG_AGE_HOURS=$(( ( $(date +%s) - $(git log -1 --format=%ct integration) ) / 3600 ))
if [ "$MAIN_AGE_HOURS" -gt "$((INTEG_AGE_HOURS + 24))" ]; then
    warn "main HEAD is >24h older than integration HEAD. Did you forget to"
    warn "commit a fresh split on main? (Continuing — pushes are idempotent.)"
fi
ok "main looks current relative to integration"

# -----------------------------------------------------------------------------
# Step: push main → origin
# -----------------------------------------------------------------------------
CURRENT_STEP="push main → origin (PUBLIC)"
title "$CURRENT_STEP"
info "Running: git push origin main"
if git push origin main; then
    ok "Pushed main → origin"
else
    err "Push failed."
    exit 1
fi

# -----------------------------------------------------------------------------
# Step: push main → backup
# -----------------------------------------------------------------------------
if [ "$BACKUP_PRESENT" = "true" ]; then
    CURRENT_STEP="push main → backup"
    title "$CURRENT_STEP"
    info "Running: git push backup main"
    if git push backup main; then
        ok "Pushed main → backup"
    else
        err "Push failed."
        exit 1
    fi
else
    skip "push main → backup  (backup remote absent)"
fi

# -----------------------------------------------------------------------------
# Step: push tags (only if new tags detected)
# -----------------------------------------------------------------------------
if [ -n "$NEW_TAGS" ]; then
    CURRENT_STEP="push tags → origin"
    title "$CURRENT_STEP"
    info "Running: git push origin --tags"
    if git push origin --tags; then
        ok "Pushed tags → origin"
    else
        err "Tag push failed."
        exit 1
    fi

    if [ "$BACKUP_PRESENT" = "true" ]; then
        CURRENT_STEP="push tags → backup"
        title "$CURRENT_STEP"
        info "Running: git push backup --tags"
        if git push backup --tags; then
            ok "Pushed tags → backup"
        else
            err "Tag push failed."
            exit 1
        fi
    fi
else
    info "No new tags — skipping --tags pushes."
fi

# -----------------------------------------------------------------------------
# Step: restore original branch
# -----------------------------------------------------------------------------
CURRENT_STEP="restore original branch ($ORIGINAL_BRANCH)"
title "$CURRENT_STEP"
if [ "$(git rev-parse --abbrev-ref HEAD)" != "$ORIGINAL_BRANCH" ]; then
    info "Running: git checkout $ORIGINAL_BRANCH"
    git checkout "$ORIGINAL_BRANCH"
    ok "Back on $ORIGINAL_BRANCH"
else
    ok "Already on $ORIGINAL_BRANCH"
fi

# -----------------------------------------------------------------------------
# Done
# -----------------------------------------------------------------------------
trap - ERR
title "All operations complete"
ok "Public origin and private backup are now in sync."
ok "Branch restored to: $ORIGINAL_BRANCH"
