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
    echo "scripts/build_noambrown.sh: Brown source tree not found at $SRC/src" >&2
    echo "  Run scripts/setup_references.sh to repopulate references/code/." >&2
    exit 0
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

echo "Building Brown's river_solver_optimized in $BUILD"
cmake -S "$SRC" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD" -j

if [[ -x "$BIN" ]]; then
    echo "Built: $BIN"
else
    echo "scripts/build_noambrown.sh: cmake reported success but $BIN is missing" >&2
    exit 1
fi
