#!/usr/bin/env bash
# =============================================================================
# v1.8.0 release execution script
# =============================================================================
#
# REQUIRES: user has reviewed this script and is kicking off the release.
#
# DOES NOT auto-execute. User invokes:
#     bash scripts/release_v1_8_0.sh
#
# WHAT IT DOES (high level):
#   Phase 0 — Pre-flight checks
#       - Working tree must be on `main`, clean (no uncommitted changes),
#         up-to-date with origin/main.
#       - Current HEAD SHA matches EXPECTED_SHA (recorded at script-write
#         time; user updates if main has advanced).
#       - All CI on origin/main is green.
#       - pyproject.toml version is currently 1.7.0 (the script bumps).
#       - poker_solver/__init__.py __version__ is currently "1.7.0".
#       - crates/cfr_core/Cargo.toml version is currently "0.7.0".
#       - Release notes draft exists at docs/v1_8_0_release_notes_DRAFT.md.
#       - gh CLI authenticated.
#
#   Phase 1 — Version bumps
#       - pyproject.toml: 1.7.0 -> 1.8.0
#       - poker_solver/__init__.py __version__: "1.7.0" -> "1.8.0"
#       - crates/cfr_core/Cargo.toml: 0.7.0 -> 0.8.0 (gated by BUMP_CFR_CORE,
#         default 1; user toggles to 0 to keep cfr_core on its own SemVer
#         track per Rust convention)
#
#   Phase 2 — Commit + push
#       - git add (the three version files; Cargo.lock if it changed)
#       - git commit -m "chore: bump version to 1.8.0 for release"
#       - git push origin main
#
#   Phase 3 — Tag
#       - git tag -a v1.8.0 HEAD -m "v1.8.0 — Cross-platform SIMD + .dmg fork-bomb fix"
#       - git push origin v1.8.0
#
#   Phase 4 — GitHub release
#       - gh release create v1.8.0 \
#           --notes-file docs/v1_8_0_release_notes_DRAFT.md \
#           --title "v1.8.0 — Cross-platform SIMD + .dmg fork-bomb fix"
#       - Optionally uploads dist/Poker-Solver-1.8.0-arm64.dmg if it exists
#         AND --upload-dmg is passed (default off; user opts in after .dmg
#         is built per docs/dmg_build_runbook_2026-05-26.md).
#
#   Phase 5 — Backup mirror sync
#       - git push backup main v1.8.0  (private mirror)
#
# CONSTRAINTS HONORED:
#   - No --force on any push (origin or backup).
#   - No --no-verify / hook bypass.
#   - No branch deletions on origin.
#   - set -euo pipefail: any step's failure halts the script immediately.
#   - Each phase prints a clear banner; an abort prints a clear FATAL line
#     with the offending check.
#
# ROLLBACK NOTES:
#   - If Phase 2 (push main) succeeds but Phase 3 (tag) fails:
#       gh release delete v1.8.0 --yes 2>/dev/null  # if a release got partially created
#       git push origin :v1.8.0 2>/dev/null
#       # Optionally revert the version bump commit:
#       #   git revert <bump-sha> && git push origin main
#   - If Phase 4 (release) fails but tag is pushed:
#       gh release create v1.8.0 --notes-file docs/v1_8_0_release_notes_DRAFT.md \
#           --title "v1.8.0 — Cross-platform SIMD + .dmg fork-bomb fix"
#   - If Phase 5 (backup push) fails:
#       Re-run manually: git push backup main && git push backup v1.8.0
#       The origin release is already public at this point; backup is best-effort.
#
# =============================================================================

set -euo pipefail

# -------------------------------------------------------------------
# Configurable knobs (edit at script-write time; user may override)
# -------------------------------------------------------------------
REPO=/Users/ashen/Desktop/poker_solver
EXPECTED_SHA=f165eb85fd409e66d4a2c929e411811a7d150fbe   # origin/main HEAD at script-write
OLD_VERSION=1.7.0
NEW_VERSION=1.8.0
OLD_CARGO_VERSION=0.7.0
NEW_CARGO_VERSION=0.8.0
RELEASE_TITLE="v1.8.0 — Cross-platform SIMD + .dmg fork-bomb fix"
RELEASE_NOTES_FILE="docs/v1_8_0_release_notes_DRAFT.md"
DMG_PATH="dist/Poker-Solver-${NEW_VERSION}-arm64.dmg"

# Toggle: bump cfr_core (0.7.0 -> 0.8.0) along with the Python package.
# 1 = bump (default; aligns minor versions); 0 = leave cfr_core on its own
# SemVer track per Rust convention.
BUMP_CFR_CORE=${BUMP_CFR_CORE:-1}

# Toggle: upload the .dmg as a release asset. The user must have built it
# per docs/dmg_build_runbook_2026-05-26.md and the file must exist at
# $REPO/$DMG_PATH. Pass --upload-dmg to enable.
UPLOAD_DMG=0

# Toggle: push to private backup mirror (default on). Pass --skip-backup
# to skip.
PUSH_BACKUP=1

# Parse CLI flags
while [[ $# -gt 0 ]]; do
    case "$1" in
        --upload-dmg)
            UPLOAD_DMG=1
            shift
            ;;
        --skip-backup)
            PUSH_BACKUP=0
            shift
            ;;
        --no-bump-cfr-core)
            BUMP_CFR_CORE=0
            shift
            ;;
        --expected-sha)
            EXPECTED_SHA="$2"
            shift 2
            ;;
        *)
            echo "FATAL: unknown flag $1"
            echo "Usage: $0 [--upload-dmg] [--skip-backup] [--no-bump-cfr-core] [--expected-sha <sha>]"
            exit 2
            ;;
    esac
done

cd "$REPO"

# -------------------------------------------------------------------
# Phase 0: Pre-flight checks
# -------------------------------------------------------------------
echo "[release-v1.8.0] === Phase 0: pre-flight ==="

# 0.1: branch is main
CURRENT_BRANCH=$(git branch --show-current)
if [[ "$CURRENT_BRANCH" != "main" ]]; then
    echo "FATAL: must be on 'main' branch (currently on: $CURRENT_BRANCH)"
    exit 1
fi
echo "[release-v1.8.0] branch: main"

# 0.2: working tree clean
if [[ -n "$(git status --porcelain)" ]]; then
    echo "FATAL: working tree not clean. Uncommitted changes:"
    git status --short
    exit 1
fi
echo "[release-v1.8.0] working tree: clean"

# 0.3: up-to-date with origin/main
git fetch origin main
LOCAL_SHA=$(git rev-parse HEAD)
REMOTE_SHA=$(git rev-parse origin/main)
if [[ "$LOCAL_SHA" != "$REMOTE_SHA" ]]; then
    echo "FATAL: local HEAD ($LOCAL_SHA) differs from origin/main ($REMOTE_SHA)"
    echo "       Run: git pull --ff-only origin main"
    exit 1
fi
echo "[release-v1.8.0] local HEAD == origin/main: $LOCAL_SHA"

# 0.4: HEAD matches EXPECTED_SHA
if [[ "$LOCAL_SHA" != "$EXPECTED_SHA" ]]; then
    echo "WARN: HEAD ($LOCAL_SHA) differs from EXPECTED_SHA ($EXPECTED_SHA)"
    echo "      origin/main has advanced since this script was written."
    echo "      Re-run with --expected-sha $LOCAL_SHA after verifying"
    echo "      that the new commits are intended for v1.8.0."
    exit 1
fi
echo "[release-v1.8.0] HEAD matches EXPECTED_SHA: $EXPECTED_SHA"

# 0.5: all CI on origin/main is green (most recent 10 runs)
echo "[release-v1.8.0] checking origin/main CI status..."
if ! command -v gh &>/dev/null; then
    echo "FATAL: gh CLI not on PATH"
    exit 1
fi
if ! gh auth status &>/dev/null; then
    echo "FATAL: gh CLI not authenticated. Run: gh auth login"
    exit 1
fi
CI_FAILURES=$(
    gh run list --branch main --limit 10 --json conclusion 2>/dev/null \
        | python3 -c "import json, sys; data=json.load(sys.stdin); print(sum(1 for r in data if r['conclusion'] not in ('success','skipped',None)))"
)
if [[ "$CI_FAILURES" -gt 0 ]]; then
    echo "FATAL: $CI_FAILURES CI runs on origin/main are NOT green (recent 10)."
    echo "       Inspect with: gh run list --branch main --limit 10"
    exit 1
fi
echo "[release-v1.8.0] CI on main: green (last 10 runs)"

# 0.6: version files have expected OLD values
PYPROJECT_VERSION=$(python3 -c "import re; print(re.search(r'^version\s*=\s*\"([^\"]+)\"', open('pyproject.toml').read(), re.M).group(1))")
if [[ "$PYPROJECT_VERSION" != "$OLD_VERSION" ]]; then
    echo "FATAL: pyproject.toml version is '$PYPROJECT_VERSION', expected '$OLD_VERSION'"
    exit 1
fi
echo "[release-v1.8.0] pyproject.toml version: $PYPROJECT_VERSION (matches OLD_VERSION)"

INIT_VERSION=$(python3 -c "import re; print(re.search(r'__version__\s*=\s*\"([^\"]+)\"', open('poker_solver/__init__.py').read()).group(1))")
if [[ "$INIT_VERSION" != "$OLD_VERSION" ]]; then
    echo "FATAL: poker_solver/__init__.py __version__ is '$INIT_VERSION', expected '$OLD_VERSION'"
    exit 1
fi
echo "[release-v1.8.0] poker_solver/__init__.py: $INIT_VERSION"

CARGO_VERSION=$(python3 -c "import re; print(re.search(r'^version\s*=\s*\"([^\"]+)\"', open('crates/cfr_core/Cargo.toml').read(), re.M).group(1))")
if [[ "$BUMP_CFR_CORE" == "1" ]]; then
    if [[ "$CARGO_VERSION" != "$OLD_CARGO_VERSION" ]]; then
        echo "FATAL: crates/cfr_core/Cargo.toml version is '$CARGO_VERSION', expected '$OLD_CARGO_VERSION'"
        echo "       Pass --no-bump-cfr-core if cfr_core should stay on its own SemVer track."
        exit 1
    fi
    echo "[release-v1.8.0] cfr_core Cargo.toml: $CARGO_VERSION (will bump to $NEW_CARGO_VERSION)"
else
    echo "[release-v1.8.0] cfr_core Cargo.toml: $CARGO_VERSION (LEFT UNCHANGED; --no-bump-cfr-core)"
fi

# 0.7: release notes draft exists
if [[ ! -f "$RELEASE_NOTES_FILE" ]]; then
    echo "FATAL: release notes file missing: $RELEASE_NOTES_FILE"
    exit 1
fi
echo "[release-v1.8.0] release notes: $RELEASE_NOTES_FILE"

# 0.8: tag does NOT already exist (locally or on origin)
if git rev-parse "v${NEW_VERSION}" >/dev/null 2>&1; then
    echo "FATAL: tag v${NEW_VERSION} already exists locally. Delete it before re-running:"
    echo "       git tag -d v${NEW_VERSION}"
    exit 1
fi
if git ls-remote --tags origin "refs/tags/v${NEW_VERSION}" | grep -q "v${NEW_VERSION}"; then
    echo "FATAL: tag v${NEW_VERSION} already exists on origin. Delete it before re-running:"
    echo "       git push origin :v${NEW_VERSION}"
    exit 1
fi
echo "[release-v1.8.0] tag v${NEW_VERSION}: does not exist (OK)"

# 0.9: backup remote configured (if backup push enabled)
if [[ "$PUSH_BACKUP" == "1" ]]; then
    if ! git remote | grep -q "^backup$"; then
        echo "FATAL: --skip-backup not passed, but 'backup' remote is not configured."
        echo "       Either add it (git remote add backup <url>) or pass --skip-backup."
        exit 1
    fi
    echo "[release-v1.8.0] backup remote: $(git remote get-url backup)"
fi

echo "[release-v1.8.0] === Phase 0: ALL PRE-FLIGHT CHECKS PASS ==="
echo ""

# -------------------------------------------------------------------
# Phase 1: Version bumps
# -------------------------------------------------------------------
echo "[release-v1.8.0] === Phase 1: version bumps ==="

# pyproject.toml
python3 - <<PYEOF
from pathlib import Path
p = Path("pyproject.toml")
text = p.read_text()
old = 'version = "${OLD_VERSION}"'
new = 'version = "${NEW_VERSION}"'
if old not in text:
    raise SystemExit("FATAL: pyproject.toml version line not found (expected '${OLD_VERSION}')")
p.write_text(text.replace(old, new, 1))
print("[release-v1.8.0] pyproject.toml ${OLD_VERSION} -> ${NEW_VERSION}")
PYEOF

# poker_solver/__init__.py
python3 - <<PYEOF
from pathlib import Path
p = Path("poker_solver/__init__.py")
text = p.read_text()
old = '__version__ = "${OLD_VERSION}"'
new = '__version__ = "${NEW_VERSION}"'
if old not in text:
    raise SystemExit("FATAL: poker_solver/__init__.py __version__ line not found (expected '${OLD_VERSION}')")
p.write_text(text.replace(old, new, 1))
print("[release-v1.8.0] poker_solver/__init__.py __version__ ${OLD_VERSION} -> ${NEW_VERSION}")
PYEOF

# crates/cfr_core/Cargo.toml (gated by BUMP_CFR_CORE)
if [[ "$BUMP_CFR_CORE" == "1" ]]; then
    python3 - <<PYEOF
from pathlib import Path
p = Path("crates/cfr_core/Cargo.toml")
text = p.read_text()
old = 'version = "${OLD_CARGO_VERSION}"'
new = 'version = "${NEW_CARGO_VERSION}"'
if old not in text:
    raise SystemExit("FATAL: crates/cfr_core/Cargo.toml version line not found (expected '${OLD_CARGO_VERSION}')")
p.write_text(text.replace(old, new, 1))
print("[release-v1.8.0] cfr_core Cargo.toml ${OLD_CARGO_VERSION} -> ${NEW_CARGO_VERSION}")
PYEOF
else
    echo "[release-v1.8.0] cfr_core Cargo.toml: LEFT UNCHANGED (--no-bump-cfr-core)"
fi

# Verify the bumps landed
NEW_PYPROJECT=$(python3 -c "import re; print(re.search(r'^version\s*=\s*\"([^\"]+)\"', open('pyproject.toml').read(), re.M).group(1))")
NEW_INIT=$(python3 -c "import re; print(re.search(r'__version__\s*=\s*\"([^\"]+)\"', open('poker_solver/__init__.py').read()).group(1))")
if [[ "$NEW_PYPROJECT" != "$NEW_VERSION" ]] || [[ "$NEW_INIT" != "$NEW_VERSION" ]]; then
    echo "FATAL: version bump verification failed. pyproject=$NEW_PYPROJECT, init=$NEW_INIT"
    exit 1
fi
echo "[release-v1.8.0] version sync verified: pyproject=$NEW_PYPROJECT, __init__=$NEW_INIT"

# -------------------------------------------------------------------
# Phase 2: Commit + push
# -------------------------------------------------------------------
echo "[release-v1.8.0] === Phase 2: commit + push ==="

git add pyproject.toml poker_solver/__init__.py
if [[ "$BUMP_CFR_CORE" == "1" ]]; then
    git add crates/cfr_core/Cargo.toml
fi
# Cargo.lock may have been touched by the Cargo.toml bump; stage if changed.
if [[ -n "$(git status --porcelain Cargo.lock 2>/dev/null)" ]]; then
    git add Cargo.lock
fi

# Show what's about to be committed
echo "[release-v1.8.0] staged changes:"
git diff --cached --stat

# Commit
COMMIT_MSG_FILE=$(mktemp /tmp/release-v1.8.0-commit-msg.XXXXXX)
cat > "$COMMIT_MSG_FILE" <<COMMIT_EOF
chore: bump version to ${NEW_VERSION} for release

- pyproject.toml: ${OLD_VERSION} -> ${NEW_VERSION}
- poker_solver/__init__.py: ${OLD_VERSION} -> ${NEW_VERSION}
COMMIT_EOF
if [[ "$BUMP_CFR_CORE" == "1" ]]; then
    cat >> "$COMMIT_MSG_FILE" <<COMMIT_EOF
- crates/cfr_core/Cargo.toml: ${OLD_CARGO_VERSION} -> ${NEW_CARGO_VERSION}
COMMIT_EOF
fi
cat >> "$COMMIT_MSG_FILE" <<'COMMIT_EOF'

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
COMMIT_EOF

git commit -F "$COMMIT_MSG_FILE"
rm -f "$COMMIT_MSG_FILE"

BUMP_SHA=$(git rev-parse HEAD)
echo "[release-v1.8.0] commit landed: $BUMP_SHA"

# Push
echo "[release-v1.8.0] pushing to origin/main..."
git push origin main

# -------------------------------------------------------------------
# Phase 3: Tag
# -------------------------------------------------------------------
echo "[release-v1.8.0] === Phase 3: tag v${NEW_VERSION} ==="

TAG_MSG_FILE=$(mktemp /tmp/release-v1.8.0-tag-msg.XXXXXX)
cat > "$TAG_MSG_FILE" <<TAG_EOF
v${NEW_VERSION} — Cross-platform SIMD + .dmg fork-bomb fix

See ${RELEASE_NOTES_FILE} for full release notes.

Headline:
  - Cross-platform SIMD (NEON / AVX2 / SSE2) for DCFR hot loops
  - .dmg fork-bomb fix (multiprocessing.freeze_support())
  - Folded v1.7.x engine + parity fixes, lifted v1.6.1 hold
TAG_EOF

git tag "v${NEW_VERSION}" "$BUMP_SHA" -a -F "$TAG_MSG_FILE"
rm -f "$TAG_MSG_FILE"

echo "[release-v1.8.0] tag created locally: v${NEW_VERSION} -> $BUMP_SHA"
echo "[release-v1.8.0] pushing tag to origin..."
git push origin "v${NEW_VERSION}"

# -------------------------------------------------------------------
# Phase 4: GitHub release
# -------------------------------------------------------------------
echo "[release-v1.8.0] === Phase 4: GitHub release ==="

gh release create "v${NEW_VERSION}" \
    --notes-file "$RELEASE_NOTES_FILE" \
    --title "$RELEASE_TITLE"

echo "[release-v1.8.0] GitHub release created: v${NEW_VERSION}"

# Optional .dmg upload
if [[ "$UPLOAD_DMG" == "1" ]]; then
    if [[ ! -f "$DMG_PATH" ]]; then
        echo "WARN: --upload-dmg set but $DMG_PATH does not exist."
        echo "      Build the .dmg per docs/dmg_build_runbook_2026-05-26.md, then run:"
        echo "      gh release upload v${NEW_VERSION} $DMG_PATH"
    else
        echo "[release-v1.8.0] uploading .dmg asset: $DMG_PATH"
        gh release upload "v${NEW_VERSION}" "$DMG_PATH"
        echo "[release-v1.8.0] .dmg uploaded."
    fi
else
    echo "[release-v1.8.0] .dmg upload SKIPPED (pass --upload-dmg to enable)."
    echo "[release-v1.8.0] To upload later:"
    echo "    gh release upload v${NEW_VERSION} $DMG_PATH"
fi

# -------------------------------------------------------------------
# Phase 5: Backup mirror sync
# -------------------------------------------------------------------
if [[ "$PUSH_BACKUP" == "1" ]]; then
    echo "[release-v1.8.0] === Phase 5: backup mirror sync ==="
    echo "[release-v1.8.0] pushing main to backup..."
    git push backup main
    echo "[release-v1.8.0] pushing v${NEW_VERSION} tag to backup..."
    git push backup "v${NEW_VERSION}"
    echo "[release-v1.8.0] backup mirror synced."
else
    echo "[release-v1.8.0] Phase 5 SKIPPED (--skip-backup)."
fi

# -------------------------------------------------------------------
# Done
# -------------------------------------------------------------------
echo ""
echo "[release-v1.8.0] === RELEASE COMPLETE ==="
echo "  Tag:       v${NEW_VERSION}"
echo "  Commit:    $BUMP_SHA"
echo "  Release:   https://github.com/amaster97/poker_solver/releases/tag/v${NEW_VERSION}"
echo ""
echo "Next steps:"
if [[ "$UPLOAD_DMG" != "1" ]]; then
    echo "  1. Build the .dmg per docs/dmg_build_runbook_2026-05-26.md"
    echo "  2. Upload: gh release upload v${NEW_VERSION} $DMG_PATH"
fi
echo "  - Update PLAN.md with v${NEW_VERSION} ship status"
echo "  - Run post-integration verification (per feedback_post_integration_verification)"
echo "  - Announce per docs/RELEASE_HEADLINES_2026-05-23.md (or equivalent)"
