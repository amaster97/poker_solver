#!/usr/bin/env sh
# Re-clone the external code references into references/code/.
# Idempotent: existing directories are left untouched.
# These repos are NOT checked into git (see .gitignore).
#
# Run from the repo root:
#   sh scripts/setup_references.sh
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CODE_DIR="$REPO_ROOT/references/code"
mkdir -p "$CODE_DIR" "$REPO_ROOT/references/papers" "$REPO_ROOT/references/blog" "$REPO_ROOT/references/products"
cd "$CODE_DIR"

clone_if_missing() {
    target="$1"
    url="$2"
    extra_flags="$3"
    if [ ! -d "$target" ]; then
        echo "Cloning $target ..."
        # shellcheck disable=SC2086
        git clone --depth 1 $extra_flags "$url" "$target"
    else
        echo "Already present: $target (skipping)"
    fi
}

# MIT — safe to learn from / port
clone_if_missing noambrown_poker_solver https://github.com/noambrown/poker_solver.git
clone_if_missing slumbot2019           https://github.com/ericgjackson/slumbot2019.git

# Apache 2.0 — safe to port; also our Kuhn/Leduc correctness oracle
clone_if_missing open_spiel            https://github.com/google-deepmind/open_spiel.git --filter=blob:none

# AGPL — read-only inspiration only; do not copy code
clone_if_missing postflop-solver       https://github.com/b-inary/postflop-solver.git
clone_if_missing TexasSolver           https://github.com/bupticybee/TexasSolver.git

# No license file — defaults to all-rights-reserved; read-only inspiration only
clone_if_missing shark-2.0             https://github.com/24parida/shark-2.0.git

echo
echo "All references in place at $CODE_DIR"
echo "See references/README.md for license-aware copy policy."
