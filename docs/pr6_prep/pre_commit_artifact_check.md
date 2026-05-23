# PR 6 Pre-Commit Artifact Check

**Branch:** `pr-6-rust-hunl-port`
**Base:** `integration` (same SHA as HEAD; PR 6 work is uncommitted in working tree)
**Date:** 2026-05-22
**Verdict:** CLEAN — `git add -A` would stage only source files. No build artifacts leak through.

---

## 1. Tracked Files Audit

PR 6 modifies 10 existing tracked files and adds 8 new untracked files. Full list of what `git add -A` would stage:

### Modified (10)
| File | Lines changed |
|---|---|
| `CHANGELOG.md` | +94 / ~ |
| `Cargo.lock` | +462 |
| `README.md` | +9 |
| `crates/cfr_core/Cargo.toml` | +34 |
| `crates/cfr_core/src/lib.rs` | +103 |
| `poker_solver/__init__.py` | +2 |
| `poker_solver/cli.py` | +20 |
| `poker_solver/hunl.py` | +67 |
| `poker_solver/solver.py` | +115 |
| `pyproject.toml` | +2 |

### Added (8)
| File | Lines | Size |
|---|---|---|
| `crates/cfr_core/src/abstraction.rs` | 497 | source |
| `crates/cfr_core/src/hunl.rs` | 1183 | source |
| `crates/cfr_core/src/hunl_eval.rs` | 373 | source |
| `crates/cfr_core/src/hunl_solver.rs` | 363 | source |
| `crates/cfr_core/src/hunl_tree.rs` | 335 | source |
| `crates/cfr_core/tests/hunl_state_unit.rs` | ~480 | 20 KB |
| `crates/cfr_core/tests/test_hunl_rust.rs` | ~620 | 26 KB |
| `tests/test_hunl_diff.py` | 469 | source |

**Total: 18 files, ~880 LOC modified + ~4,300 LOC added.** All source / test / config files. No binaries, no caches, no large files.

---

## 2. What's Ignored vs What Shouldn't Be Tracked

Verified via `git check-ignore -v` that the critical artifact paths are all matched by existing `.gitignore` rules:

| Path | Rule | Status |
|---|---|---|
| `target/` (1.2 GB Rust build dir) | `.gitignore:41 target/` | IGNORED |
| `poker_solver/_rust.cpython-313-darwin.so` (1.3 MB Python extension) | `.gitignore:4 *.so` | IGNORED |
| `poker_solver/__pycache__/` | `.gitignore:1 __pycache__/` | IGNORED |
| `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/` | matching rules | IGNORED |
| `.venv/` | `.gitignore:21 .venv/` | IGNORED |
| `poker_solver.egg-info/` | `.gitignore:18 *.egg-info/` | IGNORED |
| `references/` (papers, OSS, docx) | explicit `references/` rule | IGNORED |
| `PLAN.md`, `docs/` | explicit rules | IGNORED |
| `.DS_Store` | explicit rule | IGNORED |
| `*.docx`, `~$*.docx` | explicit rules | IGNORED |

`git status --ignored` shows 19 ignored entries, all expected. None leak into the staged set.

---

## 3. Specific Checks

| Check | Expected | Actual |
|---|---|---|
| `target/` excluded | YES | YES (`.gitignore:41`) |
| `*.so` excluded | YES | YES (`.gitignore:4`) |
| `__pycache__/` excluded | YES | YES (`.gitignore:1`) |
| `Cargo.lock` COMMITTED | YES (binary-bearing workspace) | YES — appears in modified list, +462 lines |
| `_rust.cpython-*.so` NOT committed | YES | Confirmed ignored |
| Files > 1 MB in staged set | None | None — largest staged is `test_hunl_rust.rs` at 26 KB |

`Cargo.lock` (16 KB) is correctly tracked. The workspace produces a PyO3 extension (`cdylib`) installed by maturin; pinning transitive crate versions is the right call here.

---

## 4. Recommended `.gitignore` Additions

**None.** Current `.gitignore` covers every artifact PR 6 generates. Specifically:

- Line 1 `__pycache__/`
- Line 4 `*.so` — catches `poker_solver/_rust.cpython-313-darwin.so`
- Line 41 `target/` — catches the 1.2 GB Rust target dir
- `*.egg-info/`, `.venv/`, cache dirs all already present

No new patterns required.

---

## 5. File Size Check

Largest items in working tree:

| Path | Size | Tracked? |
|---|---|---|
| `target/` | 1.2 GB | NO (ignored) |
| `poker_solver/_rust.cpython-313-darwin.so` | 1.3 MB | NO (ignored) |
| `references/` | (varies, papers + OSS clones) | NO (ignored) |
| `crates/cfr_core/tests/test_hunl_rust.rs` | 26 KB | YES (staged) |
| `crates/cfr_core/tests/hunl_state_unit.rs` | 20 KB | YES (staged) |
| `Cargo.lock` | 16 KB | YES (staged) |

No staged file exceeds 30 KB. No accidental large binaries.

---

## Summary

PR 6 is **safe to `git add -A`**. The `.gitignore` is correctly catching the Rust `target/` directory, the maturin-built `.so` extension, Python caches, and developer-local files (`PLAN.md`, `docs/`, `references/`). All 18 files that would be staged are source code, tests, lockfile, or config — appropriate for a Rust + Python PR.
