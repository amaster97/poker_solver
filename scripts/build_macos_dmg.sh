#!/usr/bin/env bash
# build_macos_dmg.sh — package Poker Solver as a macOS .app + .dmg.
#
# Pipeline (11 steps):
#   1. Pre-flight: verify python 3.13, pyinstaller, xcrun, create-dmg, _rust.so
#      (including a universal2 arch check — see Phase 1 W1.4 mitigation below).
#   2. Clean build/ + dist/.
#   3. Run PyInstaller against scripts/poker_solver.spec.
#   4. In-bundle _rust smoke test (TOP risk mitigation; spec §12.1).
#   5. Code-sign inside-out via scripts/sign_and_notarize.py    (unless --skip-signing).
#   6. Notarize the .app                                          (unless --skip-notarization).
#   7. Staple the .app.
#   8. Build the .dmg with create-dmg.
#   9. Sign the .dmg                                              (unless --skip-signing).
#  10. Notarize + staple the .dmg                                 (unless --skip-notarization).
#  11. Report (path, size, signed/notarized state).
#
# Reproducibility:
#   Same source + same env → identical unsigned PyInstaller payload bytes.
#   Signed/notarized bytes vary per run (Apple-side timestamps).
#   Confirm with: shasum dist/Poker\ Solver.app/Contents/MacOS/Poker\ Solver
#
# References (cited in PR 11 spec §15):
#   - PyInstaller usage:        https://pyinstaller.org/en/stable/usage.html
#   - Apple notarization:       https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution
#   - notarytool customization: https://developer.apple.com/documentation/security/customizing-the-notarization-workflow
#   - create-dmg (Homebrew):    https://github.com/create-dmg/create-dmg

# Show --help BEFORE `set -euo pipefail` so the strict mode doesn't trip
# on unset positional args when invoked with no flags.
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    cat <<'HELP'
build_macos_dmg.sh — build a notarizable .app + .dmg for Poker Solver.

USAGE:
    ./scripts/build_macos_dmg.sh [OPTIONS]

OPTIONS:
    --skip-signing            Produce an unsigned .app + .dmg
    --skip-notarization       Skip Apple notarization (still signs unless --skip-signing)
    --version VERSION         App version string (default: read from poker_solver/__init__.py)
    --apple-id EMAIL          Apple ID for notarization (or env APPLE_ID)
    --team-id TEAMID          Developer Team ID (or env TEAM_ID)
    --password PASSWORD       App-specific password (or env APP_SPECIFIC_PASSWORD)
    --identity NAME           Code signing identity
                              (default: "Developer ID Application: ...")
    --output-dir PATH         Output directory (default: dist/)
    --no-smoke-test           Skip the post-build _rust import smoke test (DANGEROUS).
    --help, -h                Show this help and exit.

UNSIGNED FALLBACK (Apple Developer enrollment not required):
    ./scripts/build_macos_dmg.sh --skip-signing --skip-notarization

    The resulting .app is unsigned.  To open it on macOS Gatekeeper:
      1. Right-click → "Open" in Finder (one-time bypass), OR
      2. xattr -d com.apple.quarantine "dist/Poker Solver.app"   (permanent)

PREREQUISITES:
    - Python 3.13 with pip install -e ".[distribution]"
    - Xcode Command Line Tools (xcode-select --install)
    - maturin develop --release --target universal2-apple-darwin
        produces a universal2 (arm64 + x86_64 lipo'd) _rust.cpython-313-darwin.so.
        Single-arch builds will be REJECTED by step 1 pre-flight (Phase 1 W1.4
        ImportError mitigation: x86_64 Python cannot dlopen an arm64-only .so).
    - rustup target add x86_64-apple-darwin aarch64-apple-darwin  (one-time)
    - brew install create-dmg

ENVIRONMENT:
    APPLE_ID, TEAM_ID, APP_SPECIFIC_PASSWORD
      Read if the equivalent --flags are not supplied.  The app-specific
      password is generated at appleid.apple.com (NEVER committed).
HELP
    exit 0
fi

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults + arg parsing
# ---------------------------------------------------------------------------

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

SKIP_SIGNING=0
SKIP_NOTARIZATION=0
NO_SMOKE_TEST=0
APP_VERSION=""
APPLE_ID="${APPLE_ID:-}"
TEAM_ID="${TEAM_ID:-}"
APP_SPECIFIC_PASSWORD="${APP_SPECIFIC_PASSWORD:-}"
SIGN_IDENTITY="${SIGN_IDENTITY:-Developer ID Application}"
OUTPUT_DIR="dist"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-signing)       SKIP_SIGNING=1;       shift ;;
        --skip-notarization)  SKIP_NOTARIZATION=1;  shift ;;
        --no-smoke-test)      NO_SMOKE_TEST=1;      shift ;;
        --version)            APP_VERSION="$2";     shift 2 ;;
        --apple-id)           APPLE_ID="$2";        shift 2 ;;
        --team-id)            TEAM_ID="$2";         shift 2 ;;
        --password)           APP_SPECIFIC_PASSWORD="$2"; shift 2 ;;
        --identity)           SIGN_IDENTITY="$2";   shift 2 ;;
        --output-dir)         OUTPUT_DIR="$2";      shift 2 ;;
        *)
            echo "ERROR: unknown flag '$1'.  Run --help for usage." >&2
            exit 2
            ;;
    esac
done

# Derive version from poker_solver/__init__.py if not supplied.
if [[ -z "$APP_VERSION" ]]; then
    APP_VERSION="$(python -c \
        'import re,pathlib;t=pathlib.Path("poker_solver/__init__.py").read_text();m=re.search(r"__version__\s*=\s*[\x27\"]([^\x27\"]+)[\x27\"]",t);print(m.group(1) if m else "0.0.0")')"
fi
APP_NAME="Poker Solver"
BUNDLE_ID="com.poker_solver.app"
DMG_NAME="Poker-Solver-${APP_VERSION}-universal2.dmg"
ENTITLEMENTS="scripts/entitlements.plist"
RUST_SO="poker_solver/_rust.cpython-313-darwin.so"

banner() {
    # banner "N/11" "description"
    printf '\n\033[1;36m[step %s]\033[0m %s\n' "$1" "$2"
}

err() {
    printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2
    exit 1
}

# ---------------------------------------------------------------------------
# Step 1: Pre-flight checks
# ---------------------------------------------------------------------------
banner "1/11" "pre-flight checks"

command -v python >/dev/null || err "python not found"
command -v pyinstaller >/dev/null || err \
    "pyinstaller not found.  Install with: pip install -e '.[distribution]'"
command -v xcrun >/dev/null || err \
    "xcrun not found.  Install Xcode Command Line Tools: xcode-select --install"

# Python version check (warn but don't fail; user may have 3.13 under a different name)
PY_VER="$(python -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
if [[ "$PY_VER" != "3.13" ]]; then
    echo "WARNING: Python is $PY_VER, spec calls for 3.13.  _rust.so name encodes 'cpython-313'."
fi

# _rust.so existence is load-bearing per spec §12.1.
if [[ ! -f "$RUST_SO" ]]; then
    err "$RUST_SO not found.  Run 'maturin develop --release --target universal2-apple-darwin' first to build the Rust extension."
fi

# _rust.so architecture check (Phase 1 persona test W1.4 mitigation).
# A single-arch .so will ImportError on the other arch (e.g., x86_64 Python
# under pyenv attempting to dlopen an arm64-only build).  Reject anything
# that isn't a universal binary with both arm64 and x86_64 slices.
RUST_SO_FILE_OUT="$(file "$RUST_SO")"
if ! echo "$RUST_SO_FILE_OUT" | grep -q "universal binary"; then
    err "$RUST_SO is single-arch:\n  $RUST_SO_FILE_OUT\nRebuild with: maturin develop --release --target universal2-apple-darwin"
fi
if ! echo "$RUST_SO_FILE_OUT" | grep -q "arm64" || ! echo "$RUST_SO_FILE_OUT" | grep -q "x86_64"; then
    err "$RUST_SO universal binary is missing one of {arm64, x86_64}:\n  $RUST_SO_FILE_OUT\nRebuild with: maturin develop --release --target universal2-apple-darwin"
fi
echo "[preflight] _rust.so: universal2 (arm64 + x86_64) — OK"

# ui/app.py entry exists (PR 10 prerequisite per spec decision 13.13).
if [[ ! -f "ui/app.py" ]]; then
    err "ui/app.py not found — PR 10 (NiceGUI scaffold) is a prerequisite."
fi

# create-dmg only required when we get to the DMG step; check now so we
# don't burn 60s on PyInstaller then fail.
if ! command -v create-dmg >/dev/null; then
    err "create-dmg not found.  Install with: brew install create-dmg"
fi

# Apple credentials required if not skipping notarization.
if [[ $SKIP_NOTARIZATION -eq 0 ]]; then
    if [[ -z "$APPLE_ID" || -z "$TEAM_ID" || -z "$APP_SPECIFIC_PASSWORD" ]]; then
        err "Notarization requires APPLE_ID + TEAM_ID + APP_SPECIFIC_PASSWORD (env or flags).  Use --skip-notarization to build unsigned."
    fi
fi

# Placeholder .icns: if missing, generate a minimal one so PyInstaller's
# BUNDLE step doesn't fail.  See assets/README.md for a real-icon recipe.
if [[ ! -f "assets/poker_solver.icns" ]]; then
    echo "[preflight] assets/poker_solver.icns missing; generating a minimal placeholder."
    mkdir -p assets
    # 1×1 transparent PNG → iconset → icns.  Smallest valid .icns Apple accepts.
    python - <<'PY'
import base64, pathlib, subprocess, tempfile, os
PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAA"
    "jCB0C8AAAAASUVORK5CYII="
)
png = base64.b64decode(PNG_B64)
with tempfile.TemporaryDirectory() as td:
    iconset = pathlib.Path(td) / "poker_solver.iconset"
    iconset.mkdir()
    for name in (
        "icon_16x16.png", "icon_16x16@2x.png",
        "icon_32x32.png", "icon_32x32@2x.png",
        "icon_128x128.png", "icon_128x128@2x.png",
        "icon_256x256.png", "icon_256x256@2x.png",
        "icon_512x512.png", "icon_512x512@2x.png",
    ):
        (iconset / name).write_bytes(png)
    out = pathlib.Path("assets/poker_solver.icns")
    subprocess.run(
        ["iconutil", "-c", "icns", "-o", str(out), str(iconset)],
        check=True,
    )
    print(f"[preflight] wrote {out} ({out.stat().st_size} bytes)")
PY
fi

echo "[preflight] OK: python=$PY_VER, version=$APP_VERSION, signing=$([ $SKIP_SIGNING -eq 1 ] && echo skip || echo on), notarize=$([ $SKIP_NOTARIZATION -eq 1 ] && echo skip || echo on)"

# ---------------------------------------------------------------------------
# Step 2: Clean
# ---------------------------------------------------------------------------
banner "2/11" "clean build/ + $OUTPUT_DIR/"
rm -rf "build" "$OUTPUT_DIR"

# ---------------------------------------------------------------------------
# Step 3: PyInstaller
# ---------------------------------------------------------------------------
banner "3/11" "PyInstaller (this can take 1-3 min)"
pyinstaller scripts/poker_solver.spec --noconfirm --distpath "$OUTPUT_DIR"

APP_PATH="$OUTPUT_DIR/$APP_NAME.app"
if [[ ! -d "$APP_PATH" ]]; then
    err "PyInstaller did not produce $APP_PATH"
fi

# ---------------------------------------------------------------------------
# Step 4: In-bundle _rust smoke test (TOP RISK mitigation; spec §12.1)
# ---------------------------------------------------------------------------
banner "4/11" "in-bundle _rust import smoke test"

if [[ $NO_SMOKE_TEST -eq 1 ]]; then
    echo "[smoke] SKIPPED via --no-smoke-test.  Dangerous; spec §12.1."
else
    SMOKE_LOG="$OUTPUT_DIR/smoke_test.log"
    set +e
    "$APP_PATH/Contents/MacOS/$APP_NAME" --smoke-test 2>&1 | tee "$SMOKE_LOG"
    SMOKE_RC=${PIPESTATUS[0]}
    set -e
    if [[ $SMOKE_RC -ne 0 ]]; then
        err "Smoke test FAILED (rc=$SMOKE_RC).  See $SMOKE_LOG.  Likely cause: PyInstaller missed _rust.so — confirm 'binaries=' in scripts/poker_solver.spec."
    fi
    echo "[smoke] PASS"
fi

# ---------------------------------------------------------------------------
# Step 5: Code-sign (inside-out)
# ---------------------------------------------------------------------------
banner "5/11" "code-sign inside-out"
if [[ $SKIP_SIGNING -eq 1 ]]; then
    echo "[sign] SKIPPED via --skip-signing."
else
    python scripts/sign_and_notarize.py sign-inside-out \
        "$APP_PATH" \
        --identity "$SIGN_IDENTITY" \
        --entitlements "$ENTITLEMENTS"
fi

# ---------------------------------------------------------------------------
# Step 6: Notarize the .app (via .zip wrapper)
# ---------------------------------------------------------------------------
banner "6/11" "notarize .app"
if [[ $SKIP_NOTARIZATION -eq 1 ]]; then
    echo "[notarize] SKIPPED via --skip-notarization."
else
    APP_ZIP="$OUTPUT_DIR/$APP_NAME.zip"
    rm -f "$APP_ZIP"
    ditto -c -k --keepParent "$APP_PATH" "$APP_ZIP"
    python scripts/sign_and_notarize.py notarize \
        "$APP_ZIP" \
        --apple-id "$APPLE_ID" \
        --team-id "$TEAM_ID" \
        --password "$APP_SPECIFIC_PASSWORD"
fi

# ---------------------------------------------------------------------------
# Step 7: Staple the .app
# ---------------------------------------------------------------------------
banner "7/11" "staple .app"
if [[ $SKIP_NOTARIZATION -eq 1 ]]; then
    echo "[staple] SKIPPED via --skip-notarization."
else
    python scripts/sign_and_notarize.py staple "$APP_PATH"
fi

# ---------------------------------------------------------------------------
# Step 8: Build the DMG
# ---------------------------------------------------------------------------
banner "8/11" "create-dmg"

DMG_PATH="$OUTPUT_DIR/$DMG_NAME"
rm -f "$DMG_PATH"
create-dmg \
    --volname "Poker Solver" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 100 \
    --icon "$APP_NAME.app" 175 190 \
    --hide-extension "$APP_NAME.app" \
    --app-drop-link 425 190 \
    "$DMG_PATH" \
    "$APP_PATH"

# ---------------------------------------------------------------------------
# Step 9: Sign the DMG
# ---------------------------------------------------------------------------
banner "9/11" "sign .dmg"
if [[ $SKIP_SIGNING -eq 1 ]]; then
    echo "[sign-dmg] SKIPPED via --skip-signing."
else
    codesign --force --sign "$SIGN_IDENTITY" "$DMG_PATH"
fi

# ---------------------------------------------------------------------------
# Step 10: Notarize + staple the DMG
# ---------------------------------------------------------------------------
banner "10/11" "notarize + staple .dmg"
if [[ $SKIP_NOTARIZATION -eq 1 ]]; then
    echo "[notarize-dmg] SKIPPED via --skip-notarization."
else
    python scripts/sign_and_notarize.py notarize \
        "$DMG_PATH" \
        --apple-id "$APPLE_ID" \
        --team-id "$TEAM_ID" \
        --password "$APP_SPECIFIC_PASSWORD"
    python scripts/sign_and_notarize.py staple "$DMG_PATH"
fi

# ---------------------------------------------------------------------------
# Step 11: Report
# ---------------------------------------------------------------------------
banner "11/11" "report"

APP_SIZE="$(du -sh "$APP_PATH" | awk '{print $1}')"
DMG_SIZE="$(du -sh "$DMG_PATH" | awk '{print $1}')"

cat <<REPORT

================================================================
Build complete.

  .app:        $APP_PATH ($APP_SIZE)
  .dmg:        $DMG_PATH ($DMG_SIZE)
  Version:     $APP_VERSION
  Bundle ID:   $BUNDLE_ID
  Signed:      $([ $SKIP_SIGNING -eq 1 ]      && echo NO  || echo yes)
  Notarized:   $([ $SKIP_NOTARIZATION -eq 1 ] && echo NO  || echo yes)

REPORT

if [[ $SKIP_SIGNING -eq 1 ]]; then
    cat <<'BYPASS'
Unsigned bypass instructions (for Gatekeeper):
  1. Right-click "Poker Solver.app" in Finder → "Open"   (one-time)
  2. xattr -d com.apple.quarantine "dist/Poker Solver.app"   (permanent)

BYPASS
fi

echo "================================================================"
