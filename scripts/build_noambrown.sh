#!/usr/bin/env bash
# Build Noam Brown's river_solver_optimized C++ binary used by PR 7's
# differential test (tests/test_noambrown_river_parity.py).
#
# Properties:
#   - Idempotent: if the binary exists and is newer than every source file
#     under <SRC>/src, exit 0 with an "up-to-date" message.
#   - Soft-fail: if cmake or a C++ compiler is missing on this host, print
#     an informative message and exit 0 (NOT 1). The diff test handles the
#     missing-binary case via pytest.skip; we deliberately do not break the
#     repo on machines without a C++ toolchain. (PR 7 spec §6 + §12 #3.)
#   - Out-of-tree: cmake configures under <SRC>/build/. References repo is
#     gitignored at repo root, so build artifacts never enter version control.
#
# Reference:
#   - Brown's CMakeLists: references/code/noambrown_poker_solver/cpp/CMakeLists.txt
#   - PR 7 spec §6.

set -euo pipefail

# Resolve repo root from this script's location (scripts/ → ..).
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." &>/dev/null && pwd)"

SRC="$REPO_ROOT/references/code/noambrown_poker_solver/cpp"
BUILD="$SRC/build"
BIN="$BUILD/river_solver_optimized"

if [[ ! -d "$SRC/src" ]]; then
    # Auto-bootstrap on fresh checkouts (CI, new clones): the references tree
    # is gitignored, so `actions/checkout` won't bring it in. Try to clone it
    # via the canonical setup script before giving up. If git is unavailable
    # or the clone fails, fall through to the soft-fail (preserves the
    # original semantics for hosts that explicitly opt out of references).
    SETUP="$SCRIPT_DIR/setup_references.sh"
    if [[ -x "$SETUP" ]] || [[ -f "$SETUP" ]]; then
        if command -v git >/dev/null 2>&1; then
            echo "scripts/build_noambrown.sh: Brown source tree missing at $SRC/src; bootstrapping via setup_references.sh"
            if ! sh "$SETUP"; then
                echo "scripts/build_noambrown.sh: setup_references.sh failed; skipping Brown build." >&2
                exit 0
            fi
        else
            echo "scripts/build_noambrown.sh: git not on PATH; cannot bootstrap references. Skipping." >&2
            exit 0
        fi
    fi
    if [[ ! -d "$SRC/src" ]]; then
        echo "scripts/build_noambrown.sh: Brown source tree still not found at $SRC/src" >&2
        echo "  Run scripts/setup_references.sh to repopulate references/code/." >&2
        exit 0
    fi
fi

# Idempotency probe: if binary exists and no source file is newer, we're done.
if [[ -x "$BIN" ]]; then
    if find "$SRC/src" -type f \( -name "*.cpp" -o -name "*.h" -o -name "*.hpp" \) -newer "$BIN" -print -quit | grep -q .; then
        : # at least one source file is newer than the binary — rebuild below
    elif find "$SRC/CMakeLists.txt" -newer "$BIN" -print -quit 2>/dev/null | grep -q .; then
        : # CMakeLists newer than binary — rebuild
    else
        echo "Brown's binary already up-to-date at $BIN"
        exit 0
    fi
fi

# Probe build environment. Soft-fail (exit 0) on missing tools so the diff
# test can still skip gracefully on machines without a C++ toolchain.
if ! command -v cmake >/dev/null 2>&1; then
    echo "scripts/build_noambrown.sh: cmake not on PATH; skipping Brown build."
    echo "  Install cmake to enable the PR 7 noambrown differential test."
    exit 0
fi
if ! command -v c++ >/dev/null 2>&1 && ! command -v g++ >/dev/null 2>&1 && ! command -v clang++ >/dev/null 2>&1; then
    echo "scripts/build_noambrown.sh: no C++ compiler on PATH; skipping."
    echo "  Install Xcode CLT (macOS) or g++/clang++ (Linux) to enable the diff test."
    exit 0
fi

# --- Upstream-portability patch (GCC 11.x compat) ----------------------------
# Brown's subgame_config.cpp uses `std::unordered_map<std::string, JsonValue>`
# inside the JsonValue struct definition (recursive incomplete-type member).
# libc++ (Apple Clang) accepts this; libstdc++ in GCC 11.4 (Ubuntu 22.04 CI)
# rejects it because `std::unordered_map` historically requires a complete
# value type. `std::map` is specified to permit incomplete value types (C++17,
# N4371) and exposes the same `.find` / `.end` / `.emplace` API used by this
# file — drop-in swap.
#
# Idempotent: detects the already-patched signature before touching the file
# so re-runs are no-ops. Upstream-compatible: pure portability fix, zero
# behavior change (object-member lookup is by-key in all call sites here;
# iteration order is never observed).
SUBGAME_CPP="$SRC/src/subgame_config.cpp"
if [[ -f "$SUBGAME_CPP" ]]; then
    if grep -q 'std::unordered_map<std::string, JsonValue>' "$SUBGAME_CPP"; then
        echo "Patching $SUBGAME_CPP: unordered_map -> map (GCC 11 incomplete-type fix)"
        # Portable two-arg sed: write to temp then mv, avoiding `-i ''` vs `-i`
        # differences between macOS BSD sed and GNU sed.
        TMP_CPP="$SUBGAME_CPP.tmp.$$"
        sed -e 's|#include <unordered_map>|#include <map>|' \
            -e 's|std::unordered_map<std::string, JsonValue>|std::map<std::string, JsonValue>|' \
            "$SUBGAME_CPP" > "$TMP_CPP"
        mv "$TMP_CPP" "$SUBGAME_CPP"
    fi
fi
# -----------------------------------------------------------------------------

echo "Building Brown's river_solver_optimized in $BUILD"
cmake -S "$SRC" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD" -j

if [[ -x "$BIN" ]]; then
    echo "Built: $BIN"
else
    echo "scripts/build_noambrown.sh: cmake reported success but $BIN is missing" >&2
    exit 1
fi
