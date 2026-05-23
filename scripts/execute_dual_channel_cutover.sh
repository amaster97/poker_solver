#!/usr/bin/env bash
# =============================================================================
# execute_dual_channel_cutover.sh
#
# PURPOSE
# -------
# One-shot interactive driver for the **dual-channel cutover** authorised in
# docs/public_cleanup_advisory.md. This script is the operational glue for
# steps C2-H of that advisory:
#
#     C2. Fast-forward merge `integration` into `main` (brings 8 commits incl.
#         v0.6.1 target onto main's line so the tag is reachable post-cutover).
#     D.  Run scripts/split_main_for_publish.sh --execute on `main`.
#     E.  Commit the staged split changes on `main`.
#     F.  Push cleaned `main` to BOTH `origin` (public) and `backup` (private mirror).
#     G.  Push the v0.6.1 release tag to both remotes.
#     H.  Delete `origin/integration` (destructive remote ref op).
#
# It is a **one-time** event. Once cutover is complete, ongoing maintenance
# uses scripts/sync_repos.sh (which handles routine integration→main pushes).
#
# PRE-REQS (steps A-C from the advisory, NOT done by this script)
# ---------------------------------------------------------------
#   A. Private GitHub repo `poker_solver_private` already created.
#   B. `backup` remote already wired:
#         git remote add backup git@github.com:amaster97/poker_solver_private.git
#   C. `integration` branch already pushed to backup as a safety net:
#         git push -u backup integration
#   The script checks for these and refuses to run if they are missing.
#
# WHAT IT MODIFIES
# ----------------
#   * Local repo:
#       - Switches HEAD to `main` (then leaves you there at end).
#       - Fast-forwards `main` to integration HEAD (step C2; brings PR 10a.5
#         + planning commits onto main's line so v0.6.1 tag is reachable).
#       - Stages and commits the cleanup produced by split_main_for_publish.sh.
#         (The cleanup commit sits on top of the FF-merged main HEAD and
#         untracks docs/, PLAN.md, STATUS.md, SESSION_END_FINAL.md, etc.)
#   * `origin` (public GitHub):
#       - Force-replaces tip of `origin/main` with the cleaned commit.
#         (Normal forward push — cleanup commit sits on top of integration HEAD,
#         which is itself a FF-descendant of the old origin/main at 62c75d5.)
#       - Pushes tag `v0.6.1` (reachable: target a0b1994 is in the FF range).
#       - Deletes branch `origin/integration` (step H).
#   * `backup` (private mirror):
#       - Force-pushes `main` (overwrites GitHub's initial commit on backup/main).
#       - Pushes tag `v0.6.1`.
#
# REVERSIBILITY PER STEP
# ----------------------
#   C2: reversible (local only). `git reset --hard 62c75d5` on main returns
#       main to its pre-merge state. No remotes touched yet.
#   D: reversible. Split only stages changes in the index + edits .gitignore.
#      `git restore --staged . && git checkout HEAD -- .gitignore` undoes it.
#   E: reversible. Single local commit on top of FF-merged main.
#      `git reset HEAD~1` undoes the cleanup commit; `git reset --hard 62c75d5`
#      additionally rewinds the FF-merge.
#   F: reversible. Both pushes are normal forward refs (origin) or force pushes
#      (backup). To roll back either, force-push the previous SHA back.
#   G: reversible. Tag push. `git push origin :refs/tags/v0.6.1` deletes.
#   H: **DESTRUCTIVE** on the remote ref, BUT integration's commits stay
#      reachable from origin/main (since main was FF-merged to integration HEAD
#      before the cleanup). To recreate origin/integration:
#         git push origin 9936d5f:refs/heads/integration
#
# SAFETY MODEL
# ------------
#   * `set -euo pipefail`: any error aborts.
#   * Refuses to run if pre-flight fails (not on integration / dirty tree /
#     missing remotes / backup/integration not yet bootstrapped).
#   * Default mode is `--dry-run`. `--execute` is opt-in.
#   * Each step (C2 / D / E / F / G / H) prompts for y/N before acting.
#   * `--yes` skips prompts EXCEPT step H, which always demands the literal
#     string `DELETE` to be typed.
#   * No automatic rollback. On failure, state is left for inspection.
#
# USAGE
# -----
#   scripts/execute_dual_channel_cutover.sh                    # dry-run, prompts
#   scripts/execute_dual_channel_cutover.sh --dry-run          # same as above
#   scripts/execute_dual_channel_cutover.sh --execute          # interactive go
#   scripts/execute_dual_channel_cutover.sh --execute --yes    # auto y EXCEPT H
#   scripts/execute_dual_channel_cutover.sh -h                 # help
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
Usage: scripts/execute_dual_channel_cutover.sh [--dry-run | --execute]
                                              [-y | --yes] [-h | --help]

One-shot driver for steps C2-H of docs/public_cleanup_advisory.md.

Flags:
  --dry-run        (default) Show each step's commands + expected effect.
                   Touches nothing.
  --execute        Perform the cutover, prompting before each step.
  -y, --yes        Auto-confirm steps C2-G. Step H ALWAYS prompts (and
                   requires the literal string DELETE to be typed).
  -h, --help       This message.

Pre-requisites (must be completed manually before running this):
  A. Private repo poker_solver_private created on GitHub.
  B. `backup` remote wired locally.
  C. `git push -u backup integration` already done.

Run this script ONCE. Routine syncs after cutover use scripts/sync_repos.sh.
EOF
}

# -----------------------------------------------------------------------------
# Argument parsing
# -----------------------------------------------------------------------------
MODE="dry-run"
ASSUME_YES="false"

for arg in "$@"; do
    case "$arg" in
        --dry-run)  MODE="dry-run" ;;
        --execute)  MODE="execute" ;;
        -y|--yes)   ASSUME_YES="true" ;;
        -h|--help)  usage; exit 0 ;;
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
    title "${C_RED}=== EXECUTE MODE: real pushes WILL happen ===${C_OFF}"
    warn "This is the one-time dual-channel cutover."
    warn "Step H is DESTRUCTIVE on origin/integration and ALWAYS prompts."
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
# Expected pre-cutover SHAs (sanity-checked before destructive ops).
# These are the snapshot captured at runbook authoring time (2026-05-23):
#   - Local main MUST be at 62c75d5 (post-v1 GA, pre-FF-merge).
#   - Local integration MUST be at 9936d5f (or a descendant of it).
# If reality drifts, the script aborts and the operator must re-audit.
# -----------------------------------------------------------------------------
EXPECTED_MAIN_SHA="62c75d510e74071d1085dd074f978e2640642b8a"
EXPECTED_INTEGRATION_SHA="9936d5f82dad0effdc6a7cf222f407924ee2df02"

# -----------------------------------------------------------------------------
# Helper: prompt y/N with default N
#   $1 = prompt message
#   returns 0 on yes, 1 on anything else
# -----------------------------------------------------------------------------
confirm_yn() {
    local prompt="$1"
    if [ "$ASSUME_YES" = "true" ]; then
        info "--yes set; auto-confirming: $prompt"
        return 0
    fi
    printf '\n%s%s [y/N]:%s ' "$C_BOLD" "$prompt" "$C_OFF"
    local reply=""
    if ! IFS= read -r reply; then
        printf '\n'
        err "Could not read confirmation (non-interactive shell?). Use --yes to skip steps D-G."
        return 1
    fi
    case "$reply" in
        y|Y|yes|YES|Yes) return 0 ;;
        *) return 1 ;;
    esac
}

# -----------------------------------------------------------------------------
# Helper: log a command then run it (only in --execute); in --dry-run, print
# the command and the expected effect.
#   $1 = description (one-line)
#   shift; $@ = command + args
# -----------------------------------------------------------------------------
run_cmd() {
    local desc="$1"
    shift
    info "  -> $desc"
    printf '     %s$ ' "$C_BOLD"
    # Print command with simple shell-safe quoting
    local arg
    for arg in "$@"; do
        case "$arg" in
            *[[:space:]\"\'\$\\\`]*) printf '%q ' "$arg" ;;
            *) printf '%s ' "$arg" ;;
        esac
    done
    printf '%s\n' "$C_OFF"

    if [ "$MODE" = "dry-run" ]; then
        info "     (dry-run: not executed)"
        return 0
    fi

    # Execute, capturing exit code
    local rc=0
    "$@" || rc=$?
    if [ "$rc" -eq 0 ]; then
        ok "     exit 0"
    else
        err "     exit $rc"
        return "$rc"
    fi
}

# =============================================================================
# Pre-flight checks
# =============================================================================
title "Pre-flight checks"

# 1. Must be a git repo
if ! git rev-parse --git-dir >/dev/null 2>&1; then
    err "Not a git repository: $REPO_ROOT"
    exit 1
fi
ok "Git repo detected"

# 2. Must be on `integration` (so we can switch to main and run the split there)
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$CURRENT_BRANCH" != "integration" ]; then
    err "HEAD is on '$CURRENT_BRANCH', expected 'integration'. Refusing to run."
    err "Switch first:  git checkout integration"
    exit 1
fi
ok "HEAD is on 'integration'"

# 3. Working tree must be clean
if ! git diff --quiet || ! git diff --cached --quiet; then
    err "Working tree is dirty. Stash or commit your changes first."
    err "Run 'git status' to see what's pending."
    exit 1
fi
ok "Working tree is clean (untracked files ignored)"

# 4. `origin` remote must exist
if git remote get-url origin >/dev/null 2>&1; then
    ORIGIN_URL="$(git remote get-url origin)"
    ok "Origin remote configured: $ORIGIN_URL"
else
    err "No 'origin' remote configured. Pre-req B not done."
    err "  git remote add origin https://github.com/amaster97/poker_solver.git"
    exit 1
fi

# 5. `backup` remote must exist (pre-req B from advisory)
if git remote get-url backup >/dev/null 2>&1; then
    BACKUP_URL="$(git remote get-url backup)"
    ok "Backup remote configured: $BACKUP_URL"
else
    err "No 'backup' remote configured. Pre-req B not done."
    err "  git remote add backup git@github.com:amaster97/poker_solver_private.git"
    exit 1
fi

# 6. backup/integration must equal local integration HEAD (pre-req C done)
LOCAL_INTEGRATION_SHA="$(git rev-parse integration 2>/dev/null || true)"
if [ -z "$LOCAL_INTEGRATION_SHA" ]; then
    err "Cannot resolve local 'integration' branch SHA."
    exit 1
fi
info "Local integration HEAD: $LOCAL_INTEGRATION_SHA"

REMOTE_INTEGRATION_LINE="$(git ls-remote backup refs/heads/integration 2>/dev/null || true)"
if [ -z "$REMOTE_INTEGRATION_LINE" ]; then
    err "backup/integration does not exist. Pre-req C not done."
    err "  git push -u backup integration"
    exit 1
fi
REMOTE_INTEGRATION_SHA="$(printf '%s' "$REMOTE_INTEGRATION_LINE" | awk '{print $1}')"
info "Backup integration HEAD: $REMOTE_INTEGRATION_SHA"

if [ "$LOCAL_INTEGRATION_SHA" != "$REMOTE_INTEGRATION_SHA" ]; then
    err "backup/integration ($REMOTE_INTEGRATION_SHA) does not match local"
    err "integration ($LOCAL_INTEGRATION_SHA). Re-push integration to backup first:"
    err "  git push backup integration"
    exit 1
fi
ok "backup/integration matches local integration (pre-req C verified)"

# 7. Split script must exist & be executable
SPLIT_SCRIPT="$REPO_ROOT/scripts/split_main_for_publish.sh"
if [ ! -x "$SPLIT_SCRIPT" ]; then
    err "Helper script not found or not executable: $SPLIT_SCRIPT"
    exit 1
fi
ok "Found split helper: scripts/split_main_for_publish.sh"

ok "All pre-flight checks passed."

# =============================================================================
# Plan overview
# =============================================================================
title "Cutover plan (steps C2-H from docs/public_cleanup_advisory.md)"
cat <<EOF
  C2. Switch to main, FF-merge integration -> main.
      (Brings 8 commits incl. PR 10a.5 + v0.6.1 target a0b1994 onto main's
       line so the tag is reachable after cutover.)

  D. Run scripts/split_main_for_publish.sh --execute on main.
     (Stages untracking of docs/, PLAN.md, STATUS.md, SESSION_END_FINAL.md
      + .gitignore edits. Tree on main now has 392 files post-merge; the
      split helper's allowlist drops it back to ~109.)

  E. git add -u && git commit -m "chore: clean main - Option C public-channel filter"
     (Cleanup commit on top of FF-merged main HEAD.)

  F. git push origin main           (normal forward push: FF-merge + cleanup
                                     commit on top of origin/main 62c75d5)
     git push backup main --force   (force; backup/main currently has GitHub's
                                     initial commit)

  G. git push origin v0.6.1         (REACHABLE from origin/main post-C2)
     git push backup v0.6.1

  H. git push origin --delete integration
     [DESTRUCTIVE on remote ref. Commits stay reachable via origin/main.]
EOF

# =============================================================================
# STEP C2: fast-forward merge integration -> main
# =============================================================================
# This step closes the gap flagged in docs/cutover_dry_run_preview.md: without
# it, integration's 8 commits (incl. PR 10a.5 and the v0.6.1 target a0b1994)
# never land on main's line, and the v0.6.1 tag would publish as a dangling
# ref. By FF-merging integration into main first, the cleanup commit in step
# E sits on top of integration HEAD, and v0.6.1 -> a0b1994 is reachable from
# origin/main after step F.
#
# Safety:
#   * Sanity-checks both branch SHAs against the runbook-captured expected
#     values. If either is wrong, aborts BEFORE any branch switch.
#   * Uses --ff-only so a divergent integration would abort cleanly instead
#     of producing a merge commit.
# =============================================================================
title "STEP C2: fast-forward merge integration -> main"
info "Effect: brings 8 integration commits onto main's line so the v0.6.1"
info "        tag (target a0b1994) is reachable from main post-cutover."
info "        This is local-only; nothing is pushed by step C2."

# Pre-step sanity checks (read-only, before branch switch / merge).
LOCAL_MAIN_SHA_PRE="$(git rev-parse main 2>/dev/null || true)"
LOCAL_INTEGRATION_SHA_PRE="$(git rev-parse integration 2>/dev/null || true)"
info "Local main HEAD:        $LOCAL_MAIN_SHA_PRE"
info "Local integration HEAD: $LOCAL_INTEGRATION_SHA_PRE"
info "Expected main:          $EXPECTED_MAIN_SHA"
info "Expected integration:   $EXPECTED_INTEGRATION_SHA (or descendant)"

if [ "$LOCAL_MAIN_SHA_PRE" != "$EXPECTED_MAIN_SHA" ]; then
    err "Local main is at $LOCAL_MAIN_SHA_PRE but expected $EXPECTED_MAIN_SHA."
    err "Either main has advanced since the runbook was authored, or the"
    err "snapshot is stale. Re-audit before running the cutover."
    exit 1
fi
ok "Local main matches expected snapshot ($EXPECTED_MAIN_SHA)"

# Integration is allowed to be the expected SHA OR a descendant (we only
# require that the expected SHA is in integration's history — that guarantees
# v0.6.1 is reachable via the FF-merge).
if [ "$LOCAL_INTEGRATION_SHA_PRE" = "$EXPECTED_INTEGRATION_SHA" ]; then
    ok "Local integration matches expected snapshot ($EXPECTED_INTEGRATION_SHA)"
elif git merge-base --is-ancestor "$EXPECTED_INTEGRATION_SHA" "$LOCAL_INTEGRATION_SHA_PRE" 2>/dev/null; then
    ok "Local integration ($LOCAL_INTEGRATION_SHA_PRE) is a descendant of"
    ok "  expected snapshot ($EXPECTED_INTEGRATION_SHA) — proceeding."
else
    err "Local integration ($LOCAL_INTEGRATION_SHA_PRE) is neither the expected"
    err "snapshot ($EXPECTED_INTEGRATION_SHA) nor a descendant of it. The"
    err "runbook's success criteria assume v0.6.1 sits on the FF-reachable"
    err "range. Re-audit before running the cutover."
    exit 1
fi

# Confirm the merge will be fast-forward (i.e. main is an ancestor of
# integration). Without this, --ff-only would fail later, but we catch it
# pre-prompt for a clearer message.
if ! git merge-base --is-ancestor "$LOCAL_MAIN_SHA_PRE" "$LOCAL_INTEGRATION_SHA_PRE" 2>/dev/null; then
    err "main ($LOCAL_MAIN_SHA_PRE) is not an ancestor of integration"
    err "($LOCAL_INTEGRATION_SHA_PRE); a fast-forward merge is impossible."
    err "Investigate before re-running."
    exit 1
fi
ok "main is an ancestor of integration — FF-merge is possible."

if ! confirm_yn "Proceed with step C2 (FF-merge integration -> main)?"; then
    warn "Step C2 declined. Aborting cutover."
    exit 0
fi

# Switch to main and FF-merge integration.
run_cmd "Switch to main" git checkout main
run_cmd "Fast-forward merge integration -> main" git merge --ff-only integration

# Post-merge verification (execute mode only — dry-run hasn't moved HEAD).
if [ "$MODE" = "execute" ]; then
    POST_MERGE_MAIN_SHA="$(git rev-parse main)"
    if [ "$POST_MERGE_MAIN_SHA" != "$LOCAL_INTEGRATION_SHA_PRE" ]; then
        err "Post-merge main ($POST_MERGE_MAIN_SHA) does not match integration"
        err "HEAD ($LOCAL_INTEGRATION_SHA_PRE). Aborting before destructive ops."
        exit 1
    fi
    ok "merged integration into main (now at $POST_MERGE_MAIN_SHA)"

    # Sanity-check that v0.6.1's target commit is now reachable from main.
    V061_TARGET_SHA="$(git rev-list -n 1 v0.6.1 2>/dev/null || true)"
    if [ -n "$V061_TARGET_SHA" ]; then
        if git merge-base --is-ancestor "$V061_TARGET_SHA" main 2>/dev/null; then
            ok "v0.6.1 target ($V061_TARGET_SHA) is reachable from main."
        else
            err "v0.6.1 target ($V061_TARGET_SHA) is NOT reachable from main"
            err "even after the FF-merge. This contradicts the runbook"
            err "assumptions; abort and investigate before pushing."
            exit 1
        fi
    else
        warn "Tag v0.6.1 not found locally; skipping reachability check."
    fi
else
    info "  -> Would verify post-merge main == integration HEAD"
    info "  -> Would verify v0.6.1 target reachable from main"
    info "     (dry-run: not executed)"
fi

# =============================================================================
# STEP D: run split script
# =============================================================================
title "STEP D: run scripts/split_main_for_publish.sh --execute"
info "Effect: with HEAD already on main (from step C2), stages untracking of"
info "        docs/, PLAN.md, STATUS.md, SESSION_END_FINAL.md, etc., and"
info "        appends .gitignore patterns. Allowlist (~109 files) survives;"
info "        merged-in planning artifacts get untracked."

if ! confirm_yn "Proceed with step D?"; then
    warn "Step D declined. Aborting cutover."
    warn "Note: step C2 already merged integration -> main locally. To rewind:"
    warn "  git reset --hard $EXPECTED_MAIN_SHA"
    exit 0
fi

# HEAD is already on main from step C2; this is a defensive no-op if rerun
# but harmless. The split script also demands HEAD=main.
run_cmd "Ensure HEAD is on main" git checkout main

# Run split script (it will assert HEAD=main and clean tree itself)
if [ "$MODE" = "execute" ]; then
    info "  -> Invoking: $SPLIT_SCRIPT --execute"
    printf '     %s$ %s --execute%s\n' "$C_BOLD" "scripts/split_main_for_publish.sh" "$C_OFF"
    SPLIT_RC=0
    "$SPLIT_SCRIPT" --execute || SPLIT_RC=$?
    if [ "$SPLIT_RC" -ne 0 ]; then
        err "split_main_for_publish.sh exited with code $SPLIT_RC"
        err "Step D failed. State left for inspection. Currently on branch: $(git rev-parse --abbrev-ref HEAD)"
        exit "$SPLIT_RC"
    fi
    ok "split_main_for_publish.sh completed (changes staged on main)"
else
    info "  -> Would invoke: scripts/split_main_for_publish.sh --execute"
    info "     (dry-run: not executed)"
fi

# =============================================================================
# STEP E: commit the split
# =============================================================================
title "STEP E: commit the staged cleanup on main"
info "Effect: a single commit on main that records untracked files +"
info "        .gitignore additions. Parent is the FF-merged integration HEAD"
info "        (from step C2), so the commit lands on the line that contains"
info "        v0.6.1's target — keeping the tag reachable from main."

COMMIT_MSG="chore: clean main - Option C public-channel filter"

# Idempotency: if there's nothing staged, skip with a warning
if [ "$MODE" = "execute" ]; then
    if git diff --cached --quiet && git diff --quiet; then
        warn "Nothing staged or modified on main. Split already committed?"
        warn "Skipping step E (idempotent)."
    else
        if ! confirm_yn "Proceed with step E (commit)?"; then
            warn "Step E declined. State left on main with staged changes."
            warn "To undo step D: git restore --staged . && git checkout HEAD -- .gitignore"
            exit 0
        fi
        # `git add -u` picks up the .gitignore modification + any other tracked
        # changes already on the working tree. The split script also did
        # `git add .gitignore` and `git rm --cached`, so the index is mostly
        # ready — `git add -u` is belt-and-suspenders.
        run_cmd "Stage modifications" git add -u
        run_cmd "Commit cleanup" git commit -m "$COMMIT_MSG"
        ok "Cleanup committed on main."
    fi
else
    info "  -> Would run: git add -u"
    info "  -> Would run: git commit -m \"$COMMIT_MSG\""
    info "     (dry-run: not executed)"
    if ! confirm_yn "Proceed with step E (commit) in real run?"; then
        warn "Step E declined in dry-run rehearsal. Continuing dry-run anyway."
    fi
fi

# =============================================================================
# STEP F: push cleaned main to origin + backup
# =============================================================================
title "STEP F: push cleaned main to origin and backup"
info "Effect:"
info "  - origin/main moves forward via normal push: integration's 8 commits"
info "    (FF-merged in step C2) + cleanup commit (step E) on top of"
info "    origin/main's current 62c75d5. Total: 9 new commits on origin/main."
info "  - backup/main is OVERWRITTEN (force push; backup/main currently has"
info "    GitHub's initial commit b83835e0..., which is disjoint from local history)."

# Quick idempotency check: if origin/main already equals local main, skip.
if [ "$MODE" = "execute" ]; then
    LOCAL_MAIN_SHA="$(git rev-parse main)"
    REMOTE_ORIGIN_MAIN_LINE="$(git ls-remote origin refs/heads/main 2>/dev/null || true)"
    REMOTE_ORIGIN_MAIN_SHA=""
    if [ -n "$REMOTE_ORIGIN_MAIN_LINE" ]; then
        REMOTE_ORIGIN_MAIN_SHA="$(printf '%s' "$REMOTE_ORIGIN_MAIN_LINE" | awk '{print $1}')"
    fi
    if [ -n "$REMOTE_ORIGIN_MAIN_SHA" ] && [ "$REMOTE_ORIGIN_MAIN_SHA" = "$LOCAL_MAIN_SHA" ]; then
        warn "origin/main already at $LOCAL_MAIN_SHA. Skipping origin push (idempotent)."
        SKIP_ORIGIN_F="true"
    else
        SKIP_ORIGIN_F="false"
    fi
else
    SKIP_ORIGIN_F="false"
fi

if ! confirm_yn "Proceed with step F (push main to origin + backup)?"; then
    warn "Step F declined. Local main is committed but not pushed."
    exit 0
fi

if [ "${SKIP_ORIGIN_F:-false}" = "true" ]; then
    skip "git push origin main (origin/main already current)"
else
    run_cmd "Push main to origin (PUBLIC)" git push origin main
fi

# Backup push: force is required because backup/main has GitHub's initial
# commit b83835e0... which is unrelated to local history. This is the user's
# private mirror — force is intentional and authorised by the advisory.
run_cmd "Force-push main to backup (PRIVATE mirror)" \
    git push backup main --force

ok "Step F complete."

# =============================================================================
# STEP G: push tags
# =============================================================================
title "STEP G: push v0.6.1 tag to origin and backup"
info "Effect: publishes the v0.6.1 release tag on both remotes."
info "        Tag target a0b1994 is now reachable from main (via step C2)."

# Check tag exists locally
if ! git rev-parse --verify --quiet "refs/tags/v0.6.1" >/dev/null; then
    warn "Local tag v0.6.1 does not exist. Skipping step G."
    warn "If you intended to push it, create it first:  git tag v0.6.1 <sha>"
else
    if ! confirm_yn "Proceed with step G (push v0.6.1 tag)?"; then
        warn "Step G declined."
    else
        # Idempotency: if origin already has the tag at same SHA, skip.
        if [ "$MODE" = "execute" ]; then
            LOCAL_TAG_SHA="$(git rev-list -n 1 v0.6.1)"
            REMOTE_TAG_LINE="$(git ls-remote origin refs/tags/v0.6.1 2>/dev/null || true)"
            REMOTE_TAG_SHA=""
            if [ -n "$REMOTE_TAG_LINE" ]; then
                REMOTE_TAG_SHA="$(printf '%s' "$REMOTE_TAG_LINE" | awk '{print $1}')"
            fi
            if [ -n "$REMOTE_TAG_SHA" ] && [ "$REMOTE_TAG_SHA" = "$LOCAL_TAG_SHA" ]; then
                warn "origin already has v0.6.1 at $LOCAL_TAG_SHA. Skipping origin tag push."
            else
                run_cmd "Push v0.6.1 to origin" git push origin v0.6.1
            fi
        else
            run_cmd "Push v0.6.1 to origin" git push origin v0.6.1
        fi
        run_cmd "Push v0.6.1 to backup" git push backup v0.6.1
        ok "Step G complete."
    fi
fi

# =============================================================================
# STEP H: delete origin/integration (DESTRUCTIVE — special confirmation)
# =============================================================================
title "${C_RED}STEP H: delete origin/integration (DESTRUCTIVE)${C_OFF}"
warn "This deletes the remote branch ref 'integration' on origin."
warn "Commits remain reachable via origin/main (main was FF-merged from"
warn "integration in step C2, so integration HEAD is now on origin/main's line)."
warn "To recreate later:  git push origin ${EXPECTED_INTEGRATION_SHA}:refs/heads/integration"

# Idempotency: if origin/integration already gone, skip.
ORIGIN_INTEGRATION_LINE="$(git ls-remote origin refs/heads/integration 2>/dev/null || true)"
if [ -z "$ORIGIN_INTEGRATION_LINE" ]; then
    warn "origin/integration already absent. Skipping step H (idempotent)."
else
    # MANDATORY prompt — even with --yes
    printf '\n%s%sThis will DELETE origin/integration.%s\n' "$C_BOLD" "$C_RED" "$C_OFF"
    printf '%sThe integration commits remain reachable from origin/main%s\n' "$C_YELLOW" "$C_OFF"
    printf '%s(step C2 FF-merged integration -> main; that line is on origin/main).%s\n' "$C_YELLOW" "$C_OFF"
    printf '\n%sContinue? Type %sDELETE%s to confirm:%s ' \
        "$C_BOLD" "$C_RED" "$C_BOLD" "$C_OFF"

    H_REPLY=""
    if ! IFS= read -r H_REPLY; then
        printf '\n'
        err "Could not read confirmation (non-interactive shell?). Aborting step H."
        err "origin/integration was NOT deleted."
        exit 1
    fi

    if [ "$H_REPLY" != "DELETE" ]; then
        warn "Did not receive literal 'DELETE'. Aborting step H."
        warn "origin/integration was NOT deleted. Re-run if you want to delete."
        exit 0
    fi

    ok "Received DELETE confirmation. Proceeding."
    run_cmd "Delete origin/integration" git push origin --delete integration
    ok "Step H complete."
fi

# =============================================================================
# Done
# =============================================================================
title "Cutover complete"

if [ "$MODE" = "execute" ]; then
    ok "All requested steps applied. You are now on branch: $(git rev-parse --abbrev-ref HEAD)"
    info "Verify the final state:"
    info "  git ls-remote origin  # expect refs/heads/main + tags, NO refs/heads/integration"
    info "  git ls-remote backup  # expect refs/heads/main + refs/heads/integration + tags"
    info ""
    info "Routine updates from here on use: scripts/sync_repos.sh"
else
    info "Dry-run finished. Re-run with --execute to perform the cutover."
fi

ok "Done."
