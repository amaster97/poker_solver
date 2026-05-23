# noambrown C++ Build Status (PR 7 prep)

**Date:** 2026-05-22
**Goal:** Pre-build Noam Brown's `river_solver_optimized` C++ binary so PR 7's external-validation test harness has it available on first run.

---

## 1. Tool availability

| Tool | Path | Status |
|------|------|--------|
| `cmake` | — | **NOT FOUND** (not in PATH, not at `/opt/homebrew/bin`, not at `/usr/local/bin`, not under Xcode) |
| `c++`   | `/usr/bin/c++`  | Available (Apple clang 17.0.0) |
| `g++`   | `/usr/bin/g++`  | Available (alias to Apple clang) |
| Xcode CLT | `/Applications/Xcode.app/Contents/Developer` | Installed |
| Homebrew | — | Installed (5.1.9), but no `cmake` formula |

Compiler details:
- Apple clang version 17.0.0 (clang-1700.6.4.2)
- Target: `arm64-apple-darwin24.6.0`
- Host: macOS 15.6.1, arm64 (Apple silicon)

---

## 2. Build result

**Status: SUCCESS (via direct clang invocation; cmake fallback used)**

The standard cmake flow could not run because `cmake` is missing. Per task constraints, no system tools were installed. Instead, I inspected `CMakeLists.txt` (a simple single-target C++17 build with no external dependencies) and reproduced its compile command directly:

```bash
cd /Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp
mkdir -p build
/usr/bin/c++ -std=c++17 -O3 -DNDEBUG -march=native -ffast-math -funroll-loops \
    -Isrc \
    src/cards.cpp src/river_game.cpp src/vector_eval.cpp src/mccfr.cpp \
    src/subgame_config.cpp src/trainer.cpp src/main.cpp \
    -o build/river_solver_optimized
```

Flags mirror the non-MSVC branch of `CMakeLists.txt` exactly (`-O3 -DNDEBUG -march=native -ffast-math -funroll-loops`, C++17, no `CFR_USE_DOUBLE`). No source files were modified.

Compilation completed silently (no warnings or errors).

---

## 3. Binary verification

- **Path:** `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/build/river_solver_optimized`
- **Size:** 201 KB
- **Type:** `Mach-O 64-bit executable arm64`
- **Permissions:** `-rwxr-xr-x` (executable)

Help-flag invocation succeeded:

```
Usage: river_solver_optimized [--config PATH] [--stack N]
    [--algo cfr|cfr+|lcfr|dcfr|mccfr|mccfr-linear|all]
    [--iters N] [--bet-sizes LIST] [--no-all-in] [--max-raises N]
    [--checkpoints LIST] [--target-exp X] [--seed N] [--mccfr-linear]
    [--no-eval] [--eval-interval N]
  DCFR params: --dcfr-alpha A --dcfr-beta B --dcfr-gamma G
  Bet sizes: --bet-sizes 0.5,1 (comma-separated pot fractions)
  Checkpoints: --checkpoints 1024,2048,4096
  Strategy dump: --dump-strategy PATH
```

This confirms the CLI surface PR 7 will need: `--algo`, `--iters`, `--bet-sizes`, `--seed`, `--dump-strategy`, and `--config` for subgame setup.

---

## 4. Gitignore status

- Parent `references/` is already listed in `/Users/ashen/Desktop/poker_solver/.gitignore`, so the new `build/` directory under it is implicitly ignored.
- No changes to `.gitignore` were required.

---

## 5. PR 7 implications

- **The binary is ready.** PR 7's external-validation harness can invoke `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/build/river_solver_optimized` directly. The `pytest.skipif` guard should still ship (the binary lives under the gitignored `references/` tree and won't exist on a fresh clone), but locally the tests will run end-to-end.
- **Recommended skip predicate for PR 7 tests:** `pytest.mark.skipif(not os.path.exists(NOAMBROWN_BIN), reason="noambrown C++ binary not built")`, where `NOAMBROWN_BIN` resolves to the path above.
- **No cmake dependency leaked into PR 7.** Since the binary was produced via a direct clang call, anyone re-building it needs only the Xcode CLT or any C++17 compiler — they do not need cmake unless they want the official build path. The PR 7 README / dev-setup notes should mention both options (cmake preferred; direct clang as a fallback).
- **Re-build invariance:** If the noambrown source tree changes upstream and is re-synced, the binary should be rebuilt. Suggest a small `scripts/build_noambrown.sh` in PR 7 that prefers cmake but falls back to the direct clang invocation captured above.

---

## 6. Caveats

- The default-run smoke (`./river_solver_optimized` with no args) was not exercised in this session — only `--help` was confirmed. PR 7's harness should include at least one tiny end-to-end run (e.g. `--iters 1024 --algo cfr --no-eval`) to validate I/O contract before relying on it as the oracle.
- `march=native` bakes in arm64 + Apple-silicon-specific instructions. The binary is non-portable across architectures, which is fine for a local validation oracle but should be flagged in PR 7's CI notes (CI will need to rebuild on its own host).
