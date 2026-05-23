#!/usr/bin/env bash
# =============================================================================
# split_main_for_publish.sh
#
# PURPOSE
# -------
# Implements the "dual-channel" branch split authorized 2026-05-22:
#   - `main`        = public clean (no internal planning / session artifacts)
#   - `integration` = internal accumulator (planning, docs/, PLAN.md, session
#                      retrospectives, etc.)
#
# Today an FF merge from `integration` → `main` dragged internal planning
# files onto `main`. This script stages the cleanup so `main` can be pushed
# to a public-facing remote without leaking session/planning artifacts.
#
# WHEN TO RUN
# -----------
# Run on the `main` branch *after* an integration→main merge has pulled in
# non-public files. Always run with `--dry-run` first (the default) and
# review the output before re-running with `--execute`.
#
# WHAT IT MODIFIES
# ----------------
# In `--execute` mode the script will:
#   1. `git rm --cached` any tracked file that is NOT on the ALLOWLIST below
#      (the working-tree copy is preserved — only the index is touched).
#   2. Append a set of "session artifact" globs to `.gitignore` (idempotent).
#   3. Stage the modified `.gitignore`.
#   4. Print the suggested commit message and exit. It does NOT commit or
#      push — the user is expected to inspect `git diff --cached` and run
#      `git commit` manually.
#
# In `--dry-run` mode the script touches nothing; it only enumerates what
# *would* be removed/added and prints counts and a sample.
#
# HOW TO UNDO
# -----------
# If you committed and then want to revert:
#   git reset HEAD~1                        # un-commit, keep changes staged
#   git restore --staged .                  # un-stage everything
#   git checkout HEAD -- .gitignore         # restore prior .gitignore
# Files removed via `git rm --cached` were never deleted from the working
# tree, so they're still on disk. Re-add any that were removed in error:
#   git add <path>
#
# SAFETY MODEL
# ------------
#   * `set -euo pipefail`: any error aborts.
#   * Refuses to run on a dirty working tree (would muddle the diff).
#   * Refuses to run if HEAD is not `main`.
#   * Default mode is `--dry-run`; `--execute` is opt-in.
#   * Untracked files on disk are NEVER touched (we only operate on the
#     git index).
#   * No `git commit`, no `git push`, no `git branch` ops here.
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# Colours (graceful fallback if not a TTY)
# -----------------------------------------------------------------------------
if [ -t 1 ]; then
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

ok()    { printf '%s[OK]%s    %s\n'    "$C_GREEN"  "$C_OFF" "$*"; }
warn()  { printf '%s[WARN]%s  %s\n'    "$C_YELLOW" "$C_OFF" "$*"; }
err()   { printf '%s[ERROR]%s %s\n'    "$C_RED"    "$C_OFF" "$*" 1>&2; }
info()  { printf '%s[INFO]%s  %s\n'    "$C_BLUE"   "$C_OFF" "$*"; }
title() { printf '\n%s%s%s\n'          "$C_BOLD"   "$*"     "$C_OFF"; }

# -----------------------------------------------------------------------------
# Argument parsing
# -----------------------------------------------------------------------------
MODE="dry-run"
for arg in "$@"; do
    case "$arg" in
        --dry-run)  MODE="dry-run" ;;
        --execute)  MODE="execute" ;;
        -h|--help)
            cat <<'EOF'
Usage: scripts/split_main_for_publish.sh [--dry-run | --execute]

  --dry-run   (default) Enumerate planned changes; touch nothing.
  --execute   Apply changes to the git index and .gitignore. Does NOT commit
              or push. Review `git diff --cached` and commit manually.
  -h, --help  This message.
EOF
            exit 0
            ;;
        *)
            err "Unknown arg: $arg (use --dry-run, --execute, or --help)"
            exit 2
            ;;
    esac
done

# -----------------------------------------------------------------------------
# Header
# -----------------------------------------------------------------------------
if [ "$MODE" = "execute" ]; then
    title "${C_RED}=== EXECUTE MODE: changes WILL be applied to the git index ===${C_OFF}"
    warn "This will modify your staged index and .gitignore. Working-tree files are NOT deleted."
    warn "Press Ctrl-C in the next 3 seconds to abort..."
    sleep 3
else
    title "${C_BLUE}=== DRY RUN: no changes will be made ===${C_OFF}"
    info "Re-run with --execute to apply."
fi

# -----------------------------------------------------------------------------
# Locate repo root
# -----------------------------------------------------------------------------
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
info "Repo root: $REPO_ROOT"

# -----------------------------------------------------------------------------
# Preconditions
# -----------------------------------------------------------------------------
title "Preconditions"

# 1. Must be a git repo
if [ ! -d .git ] && ! git rev-parse --git-dir >/dev/null 2>&1; then
    err "Not a git repository: $REPO_ROOT"
    exit 1
fi
ok "Git repo detected"

# 2. HEAD must be `main`
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$CURRENT_BRANCH" != "main" ]; then
    err "HEAD is on '$CURRENT_BRANCH', not 'main'. Refusing to run."
    err "Switch to main first:  git checkout main"
    exit 1
fi
ok "HEAD is on 'main'"

# 3. Working tree must be clean (no uncommitted modifications or staged
#    changes that aren't ours). Untracked files are OK (we ignore them).
if ! git diff --quiet || ! git diff --cached --quiet; then
    err "Working tree is dirty. Stash or commit your changes first."
    err "Run 'git status' to see what's pending."
    exit 1
fi
ok "Working tree is clean (untracked files ignored)"

# 4. Confirm `private` remote (optional — warn but do not bail)
if git remote get-url private >/dev/null 2>&1; then
    PRIVATE_URL="$(git remote get-url private)"
    ok "Private remote configured: $PRIVATE_URL"
else
    warn "No 'private' remote configured. Internal-only artifacts on the"
    warn "'integration' branch should be pushed to a private remote once set up:"
    warn "  git remote add private <git@github-or-gitlab:you/poker_solver_internal.git>"
    warn "Continuing — this is optional for this script's purpose."
fi

# -----------------------------------------------------------------------------
# ALLOWLIST
# -----------------------------------------------------------------------------
# Files / globs that ARE allowed to live on `main` (the public branch).
# Mirrors the PUBLIC-OK classification from docs/repo_audit.md §A.
#
# Anything NOT matched by one of these patterns will be `git rm --cached`'d
# in --execute mode.
#
# Rules:
#   * Prefix a path with no trailing slash for an exact-file match.
#   * A trailing slash means "this directory and everything under it".
#   * Globs (e.g. `*.md`) are NOT supported here on purpose — be explicit.
#
# To add a new public file/dir: append to this array. Do not weaken it
# without re-running the audit (docs/repo_audit.md).
# -----------------------------------------------------------------------------
ALLOWLIST=(
    # Top-level documentation
    "README.md"
    "USAGE.md"
    "DEVELOPER.md"
    "LICENSE"
    "CHANGELOG.md"
    "CONTRIBUTING.md"

    # Build / packaging manifests
    "pyproject.toml"
    "Cargo.toml"
    "Cargo.lock"
    "pytest.ini"
    ".gitignore"

    # Source trees
    "poker_solver/"
    "crates/"
    "tests/"
    "ui/"
    "examples/"
    "assets/"

    # Scripts (explicit — don't allowlist anything beyond what we vetted)
    "scripts/check_pr.sh"
    "scripts/setup_references.sh"
    "scripts/build_macos_dmg.sh"
    "scripts/build_noambrown.sh"
    "scripts/batch_solve.py"
    "scripts/generate_pushfold_charts.py"
    "scripts/entitlements.plist"
    "scripts/poker_solver.spec"
    "scripts/pyinstaller_entry.py"
    "scripts/sign_and_notarize.py"
    "scripts/split_main_for_publish.sh"   # this script itself

    # GitHub config
    ".github/"
)

# -----------------------------------------------------------------------------
# is_allowlisted <path>
#   Return 0 if $1 matches an ALLOWLIST entry; 1 otherwise.
# -----------------------------------------------------------------------------
is_allowlisted() {
    local path="$1"
    local entry
    for entry in "${ALLOWLIST[@]}"; do
        if [ "${entry: -1}" = "/" ]; then
            # Directory entry: path must start with "<entry>"
            if [ "${path#"$entry"}" != "$path" ]; then
                return 0
            fi
        else
            # Exact-file entry
            if [ "$path" = "$entry" ]; then
                return 0
            fi
        fi
    done
    return 1
}

# -----------------------------------------------------------------------------
# Enumerate violators (tracked files not on the allowlist)
# -----------------------------------------------------------------------------
title "Scanning tracked files against allowlist"

VIOLATORS_FILE="$(mktemp -t split_main_violators.XXXXXX)"
ALLOWED_FILE="$(mktemp -t split_main_allowed.XXXXXX)"
trap 'rm -f "$VIOLATORS_FILE" "$ALLOWED_FILE"' EXIT

# Iterate over all currently-tracked files
while IFS= read -r f; do
    if is_allowlisted "$f"; then
        printf '%s\n' "$f" >> "$ALLOWED_FILE"
    else
        printf '%s\n' "$f" >> "$VIOLATORS_FILE"
    fi
done < <(git ls-files)

ALLOWED_COUNT="$(wc -l < "$ALLOWED_FILE" | tr -d ' ')"
VIOLATOR_COUNT="$(wc -l < "$VIOLATORS_FILE" | tr -d ' ')"

ok "Tracked files on allowlist:        $ALLOWED_COUNT"
if [ "$VIOLATOR_COUNT" -gt 0 ]; then
    warn "Tracked files NOT on allowlist:    $VIOLATOR_COUNT  (will be untracked)"
else
    ok "Tracked files NOT on allowlist:    0  (nothing to remove)"
fi

# -----------------------------------------------------------------------------
# Per-audit explicit untracking targets
# -----------------------------------------------------------------------------
# The audit (docs/repo_audit.md §B3, §F) names these specifically. Listed
# again here so they show up in the report even though they're already
# covered by the allowlist sweep above.
EXPLICIT_UNTRACK=(
    "STATUS.md"
    "SESSION_END_FINAL.md"
    "V1_GA_CLOSE.md"
)

title "Audit-mandated explicit untrack list"
for f in "${EXPLICIT_UNTRACK[@]}"; do
    if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
        warn "  tracked  — will untrack:  $f"
    else
        info "  not tracked (no-op):     $f"
    fi
done

# -----------------------------------------------------------------------------
# Show a sample of violators (cap at 25 for readability)
# -----------------------------------------------------------------------------
if [ "$VIOLATOR_COUNT" -gt 0 ]; then
    title "Sample of files that would be untracked"
    head -n 25 "$VIOLATORS_FILE" | sed 's/^/  /'
    if [ "$VIOLATOR_COUNT" -gt 25 ]; then
        info "  ... and $((VIOLATOR_COUNT - 25)) more (full list in $VIOLATORS_FILE during this run)"
    fi
fi

# -----------------------------------------------------------------------------
# .gitignore patch step
# -----------------------------------------------------------------------------
# Globs from docs/repo_audit.md §F item 4.
# Appended only if not already present (idempotent).
# -----------------------------------------------------------------------------
title ".gitignore audit"

GITIGNORE_ADDITIONS=(
    "STATUS*.md"
    "SESSION_*.md"
    "V*_GA_CLOSE.md"
    "V*_MILESTONE*.md"
    "wake_up_*.md"
    "*_HANDOFF.md"
)

GITIGNORE_BLOCK_HEADER="# Session / handoff artifacts (local-only; added by split_main_for_publish.sh)"

ADDITIONS_NEEDED=()
for pat in "${GITIGNORE_ADDITIONS[@]}"; do
    if grep -Fxq "$pat" .gitignore 2>/dev/null; then
        info "  already in .gitignore:   $pat"
    else
        warn "  needs to be added:       $pat"
        ADDITIONS_NEEDED+=("$pat")
    fi
done

# -----------------------------------------------------------------------------
# Apply changes (only in --execute mode)
# -----------------------------------------------------------------------------
if [ "$MODE" = "execute" ]; then
    title "Applying changes (--execute mode)"

    # 1. Untrack violators
    if [ "$VIOLATOR_COUNT" -gt 0 ]; then
        info "Running: git rm --cached -r on $VIOLATOR_COUNT files..."
        # Use xargs with -0 to handle paths with spaces; tr converts newlines.
        # `git rm --cached -r` removes from index but keeps working-tree file.
        # `--ignore-unmatch` protects against race conditions if a file
        # disappears between scan and rm.
        tr '\n' '\0' < "$VIOLATORS_FILE" \
          | xargs -0 git rm --cached -r --quiet --ignore-unmatch
        ok "Untracked $VIOLATOR_COUNT files (still on disk; only the index was modified)"
    else
        ok "No files to untrack"
    fi

    # 2. Append .gitignore additions (idempotent — only if needed)
    if [ "${#ADDITIONS_NEEDED[@]}" -gt 0 ]; then
        # Ensure trailing newline before appending the new block
        if [ -s .gitignore ] && [ "$(tail -c1 .gitignore | wc -l | tr -d ' ')" = "0" ]; then
            printf '\n' >> .gitignore
        fi
        {
            printf '\n%s\n' "$GITIGNORE_BLOCK_HEADER"
            for pat in "${ADDITIONS_NEEDED[@]}"; do
                printf '%s\n' "$pat"
            done
        } >> .gitignore
        git add .gitignore
        ok "Appended ${#ADDITIONS_NEEDED[@]} .gitignore patterns and staged .gitignore"
    else
        ok ".gitignore already up-to-date — no changes needed"
    fi

    # 3. Summary
    title "Index now reflects:"
    info "  files removed (cached):   $VIOLATOR_COUNT"
    info "  .gitignore additions:     ${#ADDITIONS_NEEDED[@]}"
    info "  files remaining tracked:  $ALLOWED_COUNT"
else
    title "DRY RUN summary"
    info "  files that WOULD be untracked:        $VIOLATOR_COUNT"
    info "  files that WOULD remain tracked:      $ALLOWED_COUNT"
    info "  .gitignore patterns that WOULD add:   ${#ADDITIONS_NEEDED[@]}"
fi

# -----------------------------------------------------------------------------
# Next-steps footer
# -----------------------------------------------------------------------------
title "Next steps"

if [ "$MODE" = "execute" ]; then
    cat <<'EOF'
Changes have been STAGED but NOT committed. Recommended workflow:

  1. Inspect the staged diff:
       git diff --cached --stat
       git diff --cached -- .gitignore

  2. If anything looks wrong, abort with:
       git restore --staged .
       git checkout HEAD -- .gitignore

  3. If it looks good, commit with the suggested message:

       git commit -m "chore: clean main for public-channel split

       Untrack internal planning + session artifacts that were dragged onto
       main by the integration→main FF merge. Extend .gitignore with
       session/handoff glob patterns to prevent future drift.

       See docs/repo_audit.md for the audit that motivated this cleanup
       and docs/branch_split_runbook.md for the full procedure."

  4. Push to your public remote (origin) and DO NOT push to that remote
     from `integration`:
       git push origin main

  5. If a 'private' remote exists, push the (internal) integration branch
     there separately:
       git push private integration

To undo before pushing:
  git reset HEAD~1
  git restore --staged .
  git checkout HEAD -- .gitignore
EOF
else
    cat <<'EOF'
This was a DRY RUN. To apply the changes shown above, re-run with:

    scripts/split_main_for_publish.sh --execute

The script will stage the removals + .gitignore patch, but will NOT
commit or push. You commit manually after reviewing `git diff --cached`.
EOF
fi

ok "Done."
