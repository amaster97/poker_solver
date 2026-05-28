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

# Derive version from pyproject.toml if not supplied.  PR 86 hardening:
# pyproject.toml `[project] version` is the authoritative source; the
# spec file performs an additional drift check against
# poker_solver/__init__.py `__version__`.  Keeping the build script
# aligned to the same source-of-truth prevents the DMG filename from
# diverging from the Info.plist stamp.
if [[ -z "$APP_VERSION" ]]; then
    APP_VERSION="$(python -c \
        'import re,pathlib;t=pathlib.Path("pyproject.toml").read_text();m=re.search(r"(?m)^version\s*=\s*[\x27\"]([^\x27\"]+)[\x27\"]",t);print(m.group(1) if m else "0.0.0")')"
    if [[ "$APP_VERSION" == "0.0.0" ]]; then
        err "Could not read [project] version from pyproject.toml; refusing to build a 0.0.0 .dmg.  Pass --version <X.Y.Z> or fix pyproject.toml."
    fi
fi
APP_NAME="Poker Solver"
BUNDLE_ID="com.poker_solver.app"
# PR 44 fix: DMG filename matches the actual binary arch.  The .app's
# PyInstaller-bundled Python is arm64-only (scripts/poker_solver.spec
# `target_arch="arm64"`), so labeling the DMG `universal2` was incorrect.
# PR 86 reinforcement: the post-build `lipo -info` check (step 8.5 below)
# enforces this — a build that silently produces a non-arm64 Mach-O for
# the main executable will FAIL the build before the .dmg is created.
DMG_NAME="Poker-Solver-${APP_VERSION}-arm64.dmg"
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

# PR 44 fix: ensure `nicegui` is importable in the build venv BEFORE we
# burn 1-3 min on PyInstaller.  The v1.4.0 DMG smoke verification caught
# a 14 MB DMG that was built without nicegui in the venv (silent fail —
# PyInstaller's `hiddenimports` is "include IF FOUND", not "install if
# missing").  This pre-flight is defense in depth on top of pyproject's
# [distribution] extra now including nicegui.
python -c "import nicegui" 2>/dev/null || err \
    "nicegui not importable in build Python.  Run: pip install -e '.[distribution]'  (which now includes nicegui)."

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

# ---------------------------------------------------------------------------
# _rust.so source-currency check (PR #140 stale-.so gap mitigation).
#
# Why this exists: the v1.8.0 .dmg shipped with a STALE _rust.so that did
# NOT contain the PR #16 hand-count fix at dcfr_vector.rs. End-users
# running asymmetric-range fixtures on that .dmg crash with
# `index out of bounds: 65 but index 70` at `dcfr_vector.rs:651`. The
# source-tree .so on the build host was current; the .so picked up by
# PyInstaller (via `.venv/lib/python3.13/site-packages/poker_solver/...`)
# was stale — `pip install -e .` had been run BEFORE the most recent
# `maturin develop --release`, so PyInstaller embedded the pre-PR-#16
# build into the .app.
#
# Two-layer verification:
#   (1) STATIC source check: confirm `crates/cfr_core/src/dcfr_vector.rs`
#       contains the post-PR-#16 pattern (`next_reach = vec![...; player_hands]`
#       at the opponent-decision branch). If the source LACKS the fix,
#       the .so cannot have it either — hard-fail with "the source tree
#       is pre-PR-#16; pull main".
#   (2) BEHAVIORAL .so check: run an in-process smoke that triggers the
#       asymmetric-combo branch. Pre-fix .so panics with
#       index-out-of-bounds; post-fix .so completes. This is the
#       authoritative check — it tests what is ACTUALLY loaded, not what
#       happens to be on disk.
#
# Bypass: NO_SO_CURRENCY_CHECK=1 (DANGEROUS — only for emergency
# pre-PR-#16 archeology builds).
# ---------------------------------------------------------------------------
if [[ "${NO_SO_CURRENCY_CHECK:-0}" == "1" ]]; then
    echo "[preflight] _rust.so source-currency check SKIPPED via NO_SO_CURRENCY_CHECK=1 (DANGEROUS)."
else
    # (1) Static source pattern check. The post-PR-#16 fix sizes
    # `next_reach` by `player_hands` (the current node's player) at the
    # opponent-decision branch in `traverse`. Pre-fix code sized it by
    # `opp_hands` (= hand_count[update_player]); the now-unused
    # `opp_hands` binding was removed at the top of the Decision branch.
    DCFR_VECTOR_SRC="crates/cfr_core/src/dcfr_vector.rs"
    if [[ ! -f "$DCFR_VECTOR_SRC" ]]; then
        err "$DCFR_VECTOR_SRC not found — cannot verify .so is source-current. This script must run from the repo root."
    fi
    # The fix introduces TWO instances of `next_reach = vec![0.0_f64; player_hands]`:
    # one in the opponent-decision branch, one in the own-update branch.
    # Pre-PR-#16 code had `opp_hands` in the opponent-decision branch.
    POSTFIX_HITS=$(grep -c 'next_reach = vec!\[0\.0_f64; player_hands\]' "$DCFR_VECTOR_SRC" || true)
    PREFIX_HITS=$(grep -c 'next_reach = vec!\[0\.0_f64; opp_hands\]' "$DCFR_VECTOR_SRC" || true)
    if [[ "$POSTFIX_HITS" -lt 2 ]]; then
        err "$DCFR_VECTOR_SRC does NOT contain the post-PR-#16 hand-count fix (\
expected >=2 'next_reach = vec![0.0_f64; player_hands]' occurrences, got $POSTFIX_HITS).\n\
This source tree is PRE-PR-#16. Pull origin/main (PR #16 = 2d7ea58) before building, or the .dmg will crash on asymmetric-range fixtures.\n\
See docs/dmg_build_runbook_2026-05-26.md."
    fi
    if [[ "$PREFIX_HITS" -gt 0 ]]; then
        err "$DCFR_VECTOR_SRC still contains the PRE-PR-#16 'next_reach = vec![0.0_f64; opp_hands]' pattern ($PREFIX_HITS hit(s)).\n\
This source tree is inconsistent — the fix is partially applied. Pull origin/main (PR #16 = 2d7ea58) and re-build."
    fi
    echo "[preflight] dcfr_vector.rs: post-PR-#16 fix present ($POSTFIX_HITS player_hands sites, 0 opp_hands sites) — OK"

    # (2) Behavioral .so check. The smoke triggers the opponent-decision
    # branch with asymmetric combo counts (AA+KK = 12 vs 72o+83o = 24).
    # Pre-PR-#16 .so panics with `index out of bounds` inside the Rust
    # extension; post-fix .so completes the solve. This is the
    # authoritative check — it tests the .so that PyInstaller would
    # actually embed.
    #
    # The smoke is intentionally tiny (50 iters, river-only, 5 cards
    # already on the board) to keep it well under 5 s on M-series. We
    # only care about "does this code path NOT panic" — not convergence.
    echo "[preflight] running .so source-currency behavioral smoke (asymmetric 12-vs-24 fixture)..."
    SO_SMOKE_LOG="$(mktemp -t dmg_so_smoke.XXXXXX)"
    set +e
    python - >"$SO_SMOKE_LOG" 2>&1 <<'PY'
"""Build-prerequisite smoke: asymmetric-combo Nash path must NOT panic.

Pre-PR-#16 _rust.so panics at dcfr_vector.rs with `index out of bounds`
when the opponent-decision branch is reached with hand_count[P0] !=
hand_count[P1]. This smoke uses hero {AA,KK} (12 combos) vs villain
{72o,83o} (24 combos) — the original PR #16 panic fixture.

Exit 0 if the solve completes (any result is fine — we only check the
panic does not fire). Exit 1 with a clear diagnostic otherwise.
"""
import sys
import traceback

try:
    from poker_solver import (
        HUNLConfig,
        Street,
        parse_board,
        solve_range_vs_range_nash,
    )
except Exception as exc:  # noqa: BLE001 - defensive
    print(f"[so-smoke] FAIL: cannot import poker_solver: {exc!r}", file=sys.stderr)
    sys.exit(1)

# Dry rainbow river — same fixture as tests/test_asymmetric_range_sanity.
BOARD = tuple(parse_board("Tc 9d 4h Jc 6s"))
cfg = HUNLConfig(
    starting_stack=10_000,
    starting_street=Street.RIVER,
    initial_board=BOARD,
    initial_pot=200,
    initial_contributions=(100, 100),
    bet_size_fractions=(0.5, 1.0),
    include_all_in=False,
    postflop_raise_cap=2,
)
try:
    # The KEY discriminator: 12-vs-24 asymmetric combo counts.
    # Pre-PR-#16 .so panics here; post-fix .so completes.
    result = solve_range_vs_range_nash(
        config_template=cfg,
        hero_range=["AA", "KK"],            # 12 combos
        villain_range=["72o", "83o"],       # 24 combos (asymmetric)
        iterations=50,                       # tiny — we only care about no-panic
        hero_player=1,
        compute_exploitability_at_end=False,
    )
except Exception as exc:  # noqa: BLE001 - defensive
    # Pre-PR-#16 .so will surface here with "index out of bounds" from Rust.
    msg = str(exc)
    if "index out of bounds" in msg or "panicked at" in msg:
        print(
            f"[so-smoke] FAIL: loaded _rust.so PANICKED on asymmetric-combo fixture: {msg}",
            file=sys.stderr,
        )
        print(
            "[so-smoke] This is the PR #140 stale-.so symptom. The .so was built "
            "from PRE-PR-#16 source. Rebuild with: maturin develop --release",
            file=sys.stderr,
        )
        sys.exit(1)
    # Any other exception is also a hard fail — the smoke is supposed to complete.
    print(f"[so-smoke] FAIL: unexpected exception: {exc!r}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)

# Reaching here = the asymmetric-combo branch executed without panicking.
# We do NOT check strategy semantics here (that's tests/test_asymmetric_range_sanity);
# the build-prerequisite smoke only verifies the .so is post-PR-#16.
print("[so-smoke] OK — _rust.so handles asymmetric-combo branch without panicking")
sys.exit(0)
PY
    SMOKE_RC=$?
    set -e
    if [[ $SMOKE_RC -ne 0 ]]; then
        cat "$SO_SMOKE_LOG" >&2 || true
        rm -f "$SO_SMOKE_LOG"
        err "_rust.so source-currency BEHAVIORAL smoke FAILED.\n\
The loaded .so is STALE — built from PRE-PR-#16 source. PyInstaller would embed this stale binary into the .app, which would crash users on asymmetric-range fixtures (PR #140 stale-.so symptom).\n\
\n\
Fix: rebuild the .so from the current source tree:\n\
    maturin develop --release --target universal2-apple-darwin\n\
\n\
then re-run this build script.  See docs/dmg_build_runbook_2026-05-26.md."
    fi
    # Surface the success line for the build log.
    grep -E '^\[so-smoke\]' "$SO_SMOKE_LOG" || true
    rm -f "$SO_SMOKE_LOG"
    echo "[preflight] _rust.so: post-PR-#16 (behavioral smoke PASS) — OK"
fi

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

# Resolve APP_PATH to an ABSOLUTE path before any subsequent `defaults read`
# invocations.  macOS `defaults read` treats a RELATIVE path argument as a
# DOMAIN NAME (not a filesystem path) and silently returns whatever lives in
# the (likely-empty) default-domain database — NOT the bundle's Info.plist.
# Symptom: CFBundleShortVersionString comes back empty/"MISSING" and the
# step-5.5 hardening check then fails with a confusing drift error even
# though the Info.plist on disk is correct.  Discovered during the v1.8.0
# .dmg build (agent aa1c9874) when the script was run with the default
# relative OUTPUT_DIR="dist".  Use `cd … && pwd` rather than `realpath`
# because BSD `realpath` (stock macOS) lacks the GNU `-e`/`-m` flags and
# behavior on missing components differs across versions.
APP_PATH_ABS="$(cd "$(dirname "$APP_PATH")" && pwd)/$(basename "$APP_PATH")"
if [[ ! -d "$APP_PATH_ABS" ]]; then
    err "internal: APP_PATH_ABS resolved to non-existent dir: $APP_PATH_ABS"
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
# Step 5.5: PR 86 hardening — post-sign arch + Info.plist + codesign verify.
# Catches three classes of packaging defect at build time, before the
# .dmg is wrapped and shipped:
#   (a) Main executable Mach-O is not the arm64 we claim in the filename.
#   (b) Info.plist version stamp drifts from pyproject.toml [project] version.
#   (c) The signature on disk (ad-hoc or Developer ID) fails codesign --verify
#       --deep — e.g., a stale inner-binary signature from a prior incremental
#       build.
# ---------------------------------------------------------------------------
banner "5.5/11" "PR 86 hardening: post-sign arch + version + codesign verify"

# (a) Main executable arch.  PyInstaller's `target_arch="arm64"` should
# produce a thin arm64 Mach-O for Contents/MacOS/<APP_NAME>.  If the
# build environment somehow produced universal2 or x86_64, fail loudly
# rather than silently shipping a .dmg whose -arm64 filename is a lie.
APP_EXE="$APP_PATH/Contents/MacOS/$APP_NAME"
if [[ ! -x "$APP_EXE" ]]; then
    err "main executable missing or not executable: $APP_EXE"
fi
LIPO_OUT="$(lipo -info "$APP_EXE")"
echo "[verify] main exe arch: $LIPO_OUT"
if ! echo "$LIPO_OUT" | grep -q "architecture: arm64\|architectures: .*arm64"; then
    err "main executable is not arm64:\n  $LIPO_OUT\nDMG filename claims -arm64.dmg but the binary disagrees.  Check scripts/poker_solver.spec target_arch."
fi

# (b) Info.plist version stamp matches APP_VERSION (which itself comes
# from pyproject.toml via the step-1 derivation).  PR 44 made the spec
# read __version__ dynamically; PR 86 enforces that what we read is what
# we shipped.
# IMPORTANT: pass an ABSOLUTE path to `defaults read`.  A relative path
# (e.g., "dist/Poker Solver.app/Contents/Info.plist") is interpreted as a
# DOMAIN name by `defaults` and silently returns empty/garbage — see the
# block above where APP_PATH_ABS is computed.
PLIST_SHORT="$(defaults read "$APP_PATH_ABS/Contents/Info.plist" CFBundleShortVersionString 2>/dev/null || echo MISSING)"
PLIST_FULL="$(defaults read "$APP_PATH_ABS/Contents/Info.plist" CFBundleVersion 2>/dev/null || echo MISSING)"
echo "[verify] Info.plist CFBundleShortVersionString: $PLIST_SHORT"
echo "[verify] Info.plist CFBundleVersion:            $PLIST_FULL"
# HARD-FAIL on empty/MISSING rather than letting the drift comparison below
# generate a misleading error (per feedback_silent_skip_hazard.md: empty
# returns from probing commands must surface, not silently pass downstream).
# If we got here with empty values, either the Info.plist is genuinely
# malformed OR `defaults read` was given a path it couldn't resolve.
if [[ -z "$PLIST_SHORT" || "$PLIST_SHORT" == "MISSING" ]]; then
    err "Info.plist CFBundleShortVersionString is empty/MISSING for $APP_PATH_ABS/Contents/Info.plist.  Either the plist is malformed, or \`defaults read\` mis-parsed the path (it requires an ABSOLUTE path — relative paths are treated as domain names)."
fi
if [[ -z "$PLIST_FULL" || "$PLIST_FULL" == "MISSING" ]]; then
    err "Info.plist CFBundleVersion is empty/MISSING for $APP_PATH_ABS/Contents/Info.plist.  Either the plist is malformed, or \`defaults read\` mis-parsed the path (it requires an ABSOLUTE path — relative paths are treated as domain names)."
fi
if [[ "$PLIST_SHORT" != "$APP_VERSION" ]]; then
    err "Info.plist CFBundleShortVersionString ($PLIST_SHORT) does not match APP_VERSION ($APP_VERSION).  Spec/__init__/pyproject drift?"
fi
if [[ "$PLIST_FULL" != "$APP_VERSION" ]]; then
    err "Info.plist CFBundleVersion ($PLIST_FULL) does not match APP_VERSION ($APP_VERSION).  Spec/__init__/pyproject drift?"
fi

# (c) codesign --verify --deep on the .app.  Skipped only when the
# entire signing step was skipped via --skip-signing (in which case the
# .app is truly unsigned and codesign would fail by design).
if [[ $SKIP_SIGNING -eq 0 ]]; then
    set +e
    codesign --verify --deep --strict "$APP_PATH" 2>&1
    CSV_RC=$?
    set -e
    if [[ $CSV_RC -ne 0 ]]; then
        err "codesign --verify --deep FAILED on $APP_PATH (rc=$CSV_RC).  Likely a stale inner-binary signature from a prior incremental build; run a clean build (the script's step 2 should have done this) and re-run."
    fi
    echo "[verify] codesign --verify --deep --strict: PASS"
    # Capture the signature type (adhoc vs Developer ID) for the final report.
    SIG_LINE="$(codesign -dvv "$APP_PATH" 2>&1 | grep -E '^(Signature|Authority|TeamIdentifier)' | head -3)"
    echo "[verify] signature summary:"
    echo "$SIG_LINE" | sed 's/^/    /'
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

# PR 86 hardening: surface the actual signature type so the operator can
# confirm at a glance whether the build came out ad-hoc (no Apple Dev
# enrollment) or Developer ID + notarized.  Gatekeeper bypass docs apply
# only to the ad-hoc case.
SIG_KIND="unsigned"
if [[ $SKIP_SIGNING -eq 0 ]]; then
    if codesign -dvv "$APP_PATH" 2>&1 | grep -q "Signature=adhoc"; then
        SIG_KIND="ad-hoc"
    elif codesign -dvv "$APP_PATH" 2>&1 | grep -q "Authority=Developer ID"; then
        SIG_KIND="Developer ID"
    else
        SIG_KIND="signed (unknown authority — inspect with codesign -dvv)"
    fi
fi

cat <<REPORT

================================================================
Build complete.

  .app:        $APP_PATH ($APP_SIZE)
  .dmg:        $DMG_PATH ($DMG_SIZE)
  Version:     $APP_VERSION
  Bundle ID:   $BUNDLE_ID
  Architecture: arm64 (Apple Silicon only — Intel Macs use source install)
  Signature:   $SIG_KIND
  Notarized:   $([ $SKIP_NOTARIZATION -eq 1 ] && echo NO  || echo yes)

REPORT

if [[ $SKIP_SIGNING -eq 1 || "$SIG_KIND" == "ad-hoc" ]]; then
    cat <<'BYPASS'
Gatekeeper bypass (for unsigned or ad-hoc-signed .app — first launch only):
  1. Right-click "Poker Solver.app" in Finder → "Open"   (one-time prompt)
  2. Click "Open" in the "unidentified developer" dialog
  3. macOS remembers the decision for subsequent launches
  Alternative (permanent on this machine):
     xattr -d com.apple.quarantine "/Applications/Poker Solver.app"

Notarized distribution requires Apple Developer Program enrollment
($99/yr).  See docs/dmg_install_guide.md for the full operator runbook.

BYPASS
fi

echo "================================================================"
