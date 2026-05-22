#!/usr/bin/env sh
# Between-PR check battery for the poker solver.
# Runs tests, lint, types, diff-tests, license/dep audit, perf, references integrity.
# Emits a human-readable summary to stdout and writes pr_report.md at the repo root.
#
# Usage:  sh scripts/check_pr.sh
#
# Exit code 0 = all gates passed; non-zero = at least one failed.
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPORT="$REPO_ROOT/pr_report.md"
FAILED=""

cd "$REPO_ROOT"

# Activate venv if present
if [ -f .venv/bin/activate ]; then
    # shellcheck disable=SC1091
    . .venv/bin/activate
fi

# Source cargo env if present
if [ -f "$HOME/.cargo/env" ]; then
    # shellcheck disable=SC1090
    . "$HOME/.cargo/env"
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS_SYMBOL="OK"
FAIL_SYMBOL="FAIL"
SKIP_SYMBOL="skip"

# results table accumulator
TABLE_ROWS=""

record() {
    name="$1"; result="$2"; notes="$3"
    TABLE_ROWS="$TABLE_ROWS|$name|$result|$notes|
"
    if [ "$result" = "$FAIL_SYMBOL" ]; then
        FAILED="$FAILED $name"
    fi
}

run() {
    name="$1"
    shift
    if "$@" > /tmp/check_pr_out 2>&1; then
        echo "  $PASS_SYMBOL  $name"
        record "$name" "$PASS_SYMBOL" ""
        return 0
    else
        echo "  $FAIL_SYMBOL  $name"
        tail -20 /tmp/check_pr_out | sed 's/^/      /'
        record "$name" "$FAIL_SYMBOL" "see logs"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# 1. Python tests
# ---------------------------------------------------------------------------
echo "[1/9] Python tests"
# PR 11 (Agent C): library + CLI tests live alongside the rest under
# tests/. `pytest -x` discovers them automatically; the per-file run
# below is an additive belt-and-suspenders gate so PR 11 surfaces a
# clear failure if the library test files were dropped from the diff.
if [ -d tests ]; then
    if pytest -x > /tmp/check_pr_pytest 2>&1; then
        py_count=$(tail -1 /tmp/check_pr_pytest | grep -Eo '[0-9]+ passed' | head -1 || echo "?")
        echo "  $PASS_SYMBOL  pytest: $py_count"
        record "Python tests" "$PASS_SYMBOL" "$py_count"
    else
        echo "  $FAIL_SYMBOL  pytest"
        tail -30 /tmp/check_pr_pytest | sed 's/^/      /'
        record "Python tests" "$FAIL_SYMBOL" "see logs"
        FAILED="$FAILED pytest"
    fi

    # PR 11 explicit library-test gate (additive; the broader pytest run
    # above already covers these, but a per-file invocation surfaces
    # cleaner errors when iterating on the library module itself).
    if [ -f tests/test_library.py ] || [ -f tests/test_library_cli.py ]; then
        if pytest tests/test_library.py tests/test_library_cli.py \
            > /tmp/check_pr_pytest_library 2>&1; then
            lib_count=$(tail -1 /tmp/check_pr_pytest_library | grep -Eo '[0-9]+ passed' | head -1 || echo "?")
            echo "  $PASS_SYMBOL  library tests: $lib_count"
            record "library tests" "$PASS_SYMBOL" "$lib_count"
        else
            echo "  $FAIL_SYMBOL  library tests"
            tail -30 /tmp/check_pr_pytest_library | sed 's/^/      /'
            record "library tests" "$FAIL_SYMBOL" "see logs"
            FAILED="$FAILED library-tests"
        fi
    fi
else
    echo "  $SKIP_SYMBOL  no tests/ directory"
    record "Python tests" "$SKIP_SYMBOL" ""
fi

# ---------------------------------------------------------------------------
# 2. Rust tests
# ---------------------------------------------------------------------------
echo "[2/9] Rust tests"
if [ -f Cargo.toml ] && command -v cargo > /dev/null 2>&1; then
    if cargo test --all > /tmp/check_pr_cargo 2>&1; then
        rs_count=$(grep -Eo 'test result: ok\. [0-9]+ passed' /tmp/check_pr_cargo | head -1 || echo "?")
        echo "  $PASS_SYMBOL  cargo test: $rs_count"
        record "Rust tests" "$PASS_SYMBOL" "$rs_count"
    else
        echo "  $FAIL_SYMBOL  cargo test"
        tail -30 /tmp/check_pr_cargo | sed 's/^/      /'
        record "Rust tests" "$FAIL_SYMBOL" "see logs"
        FAILED="$FAILED cargo-test"
    fi
else
    echo "  $SKIP_SYMBOL  no Cargo.toml or cargo missing"
    record "Rust tests" "$SKIP_SYMBOL" ""
fi

# ---------------------------------------------------------------------------
# 3. Rust lint (clippy)
# ---------------------------------------------------------------------------
echo "[3/9] Rust lint"
if [ -f Cargo.toml ] && command -v cargo > /dev/null 2>&1; then
    if cargo clippy --all-targets -- -D warnings > /tmp/check_pr_clippy 2>&1; then
        echo "  $PASS_SYMBOL  clippy"
        record "clippy" "$PASS_SYMBOL" ""
    else
        echo "  $FAIL_SYMBOL  clippy"
        tail -20 /tmp/check_pr_clippy | sed 's/^/      /'
        record "clippy" "$FAIL_SYMBOL" "see logs"
        FAILED="$FAILED clippy"
    fi
else
    echo "  $SKIP_SYMBOL"
    record "clippy" "$SKIP_SYMBOL" ""
fi

# ---------------------------------------------------------------------------
# 4a. Python lint (ruff)
# ---------------------------------------------------------------------------
echo "[4a/10] Python lint (ruff)"
if ! command -v ruff > /dev/null 2>&1; then
    echo "  $FAIL_SYMBOL  ruff not installed — run 'pip install -e .[dev]'"
    record "ruff" "$FAIL_SYMBOL" "missing tool"
    FAILED="$FAILED ruff"
elif ruff check poker_solver tests > /tmp/check_pr_ruff 2>&1; then
    echo "  $PASS_SYMBOL  ruff check"
    record "ruff" "$PASS_SYMBOL" ""
else
    echo "  $FAIL_SYMBOL  ruff check"
    tail -20 /tmp/check_pr_ruff | sed 's/^/      /'
    record "ruff" "$FAIL_SYMBOL" "see logs"
    FAILED="$FAILED ruff"
fi

# ---------------------------------------------------------------------------
# 4b. Python format (black --check)
# ---------------------------------------------------------------------------
echo "[4b/10] Python format (black)"
if ! command -v black > /dev/null 2>&1; then
    echo "  $FAIL_SYMBOL  black not installed — run 'pip install -e .[dev]'"
    record "black" "$FAIL_SYMBOL" "missing tool"
    FAILED="$FAILED black"
elif black --check poker_solver tests > /tmp/check_pr_black 2>&1; then
    echo "  $PASS_SYMBOL  black --check"
    record "black" "$PASS_SYMBOL" ""
else
    echo "  $FAIL_SYMBOL  black --check (run 'black poker_solver tests' to fix)"
    tail -20 /tmp/check_pr_black | sed 's/^/      /'
    record "black" "$FAIL_SYMBOL" "see logs"
    FAILED="$FAILED black"
fi

# ---------------------------------------------------------------------------
# 5. Python types (mypy)
# ---------------------------------------------------------------------------
echo "[5/9] Python types (mypy)"
if command -v mypy > /dev/null 2>&1; then
    if mypy poker_solver > /tmp/check_pr_mypy 2>&1; then
        echo "  $PASS_SYMBOL  mypy"
        record "mypy" "$PASS_SYMBOL" ""
    else
        echo "  $FAIL_SYMBOL  mypy"
        tail -20 /tmp/check_pr_mypy | sed 's/^/      /'
        record "mypy" "$FAIL_SYMBOL" "see logs"
        FAILED="$FAILED mypy"
    fi
else
    echo "  $SKIP_SYMBOL  mypy not installed"
    record "mypy" "$SKIP_SYMBOL" "mypy not installed"
fi

# ---------------------------------------------------------------------------
# 6. Differential tests (Python vs Rust)
# ---------------------------------------------------------------------------
echo "[6/9] Differential tests"
if [ -f tests/test_dcfr_diff.py ]; then
    if pytest tests/test_dcfr_diff.py > /tmp/check_pr_diff 2>&1; then
        echo "  $PASS_SYMBOL  diff-test"
        record "diff-test" "$PASS_SYMBOL" ""
    else
        echo "  $FAIL_SYMBOL  diff-test"
        tail -30 /tmp/check_pr_diff | sed 's/^/      /'
        record "diff-test" "$FAIL_SYMBOL" "see logs"
        FAILED="$FAILED diff-test"
    fi
else
    echo "  $SKIP_SYMBOL  no tests/test_dcfr_diff.py yet"
    record "diff-test" "$SKIP_SYMBOL" ""
fi

# ---------------------------------------------------------------------------
# 7. License + dep audit
# ---------------------------------------------------------------------------
echo "[7/9] License + dep audit"
DEP_CHANGES=""
if git rev-parse --git-dir > /dev/null 2>&1; then
    # Show new dep lines since the last commit
    DEP_DIFF=$(git diff HEAD -- pyproject.toml Cargo.toml crates/*/Cargo.toml 2>/dev/null | grep -E '^\+' | grep -E '(dependencies|requires|=)' || true)
    if [ -n "$DEP_DIFF" ]; then
        DEP_CHANGES="modified"
    fi
fi
# Quick AGPL check on declared deps
AGPL_FOUND=""
if grep -r -i "AGPL" pyproject.toml Cargo.toml crates/ 2>/dev/null | grep -v "license = \"MIT\"" | grep -v "#"; then
    AGPL_FOUND="AGPL string found in build files"
fi
if [ -n "$AGPL_FOUND" ]; then
    echo "  $FAIL_SYMBOL  $AGPL_FOUND"
    record "license/deps" "$FAIL_SYMBOL" "$AGPL_FOUND"
    FAILED="$FAILED license"
else
    echo "  $PASS_SYMBOL  no AGPL in build files; deps: ${DEP_CHANGES:-unchanged}"
    record "license/deps" "$PASS_SYMBOL" "${DEP_CHANGES:-unchanged}"
fi

# ---------------------------------------------------------------------------
# 8. Perf check (placeholder)
# ---------------------------------------------------------------------------
echo "[8/9] Perf check"
echo "  $SKIP_SYMBOL  no perf benchmark wired up yet (post-PR1)"
record "perf" "$SKIP_SYMBOL" "not wired"

# ---------------------------------------------------------------------------
# 9. References integrity
# ---------------------------------------------------------------------------
echo "[9/9] References integrity"
MISSING=""
for d in references/papers references/blog references/products; do
    if [ ! -d "$d" ] || [ -z "$(ls -A "$d" 2>/dev/null)" ]; then
        MISSING="$MISSING $d"
    fi
done
if [ ! -f references/README.md ]; then
    MISSING="$MISSING references/README.md"
fi
if [ -n "$MISSING" ]; then
    echo "  $FAIL_SYMBOL  missing:$MISSING"
    record "references" "$FAIL_SYMBOL" "missing:$MISSING"
    FAILED="$FAILED references"
else
    echo "  $PASS_SYMBOL  papers, blog, products, README all present"
    record "references" "$PASS_SYMBOL" ""
fi

# ---------------------------------------------------------------------------
# Write pr_report.md
# ---------------------------------------------------------------------------
{
    echo "# PR check report"
    echo ""
    echo "Generated by \`scripts/check_pr.sh\` at $(date -u +%Y-%m-%dT%H:%M:%SZ)."
    echo ""
    echo "## Check battery"
    echo ""
    echo "| Check | Result | Notes |"
    echo "|---|---|---|"
    printf "%s" "$TABLE_ROWS"
    echo ""
    if [ -n "$FAILED" ]; then
        echo "## Status: NOT ready for user review"
        echo ""
        echo "Failed gates:$FAILED"
    else
        echo "## Status: ready for user review"
    fi
    echo ""
    echo "## Diff summary (vs HEAD)"
    echo ""
    if git rev-parse --git-dir > /dev/null 2>&1; then
        echo '```'
        git diff --stat HEAD 2>/dev/null || echo "no git diff available"
        echo '```'
    else
        echo "(not a git repository)"
    fi
} > "$REPORT"

echo ""
echo "Report written to: $REPORT"

if [ -n "$FAILED" ]; then
    echo "FAILED gates:$FAILED"
    exit 1
fi
exit 0
