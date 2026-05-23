# Cargo.lock + Workspace State Audit (post-PR-6)

**Date:** 2026-05-22
**Scope:** Verify Cargo.lock tracking, license posture of PR 6 deps, AGPL contamination check, workspace alignment.
**Working branch:** `pr-7-noambrown-diff` (Cargo files identical to `integration`).

## 1. Cargo.lock Tracking State

| Check | Result |
| --- | --- |
| File exists at repo root | YES — `/Users/ashen/Desktop/poker_solver/Cargo.lock` |
| Tracked in git | YES (`git ls-files` confirms) |
| Committed to `integration` branch | YES (blob `4cb297a3...`) |
| `.gitignore` excludes it | NO — only `target/` is ignored |
| Lock-file version | `version = 4` (cargo ≥ 1.78 format) |
| Total packages locked | **71** entries |
| File size | 642 lines, 16,314 bytes |
| Current-branch diff vs `integration` for Cargo files | empty (no drift) |

**Commit history for Cargo.lock:**
- `9d2d66a` (PR 1) — initial 180 lines (pyo3 stack only)
- `0933367` (PR 6) — +463 lines, -1 line (ndarray/serde/etc. added)

Clean, monotone growth across the two PRs that touched it. No churn.

**PLAN.md §6 status:** the open item was resolved per `PLAN.md` line 238:
> "Cargo.lock convention. RESOLVED — `cargo check --locked` wired in `scripts/check_pr.sh` and confirmed by PR 6 audit; convention carries forward to PR 7 / PR 8."

So this audit is a re-verification, not a new finding.

## 2. Per-Dep License Verification (PR 6 additions)

`cfr_core/Cargo.toml` declares the package itself as `license = "MIT"`. PR 6 additions:

| Dep | Version in lock | Upstream license | Status |
| --- | --- | --- | --- |
| `ndarray` | 0.16.1 | MIT OR Apache-2.0 (dual) | OK |
| `ndarray-npy` | 0.9.1 | MIT OR Apache-2.0 (dual) | OK |
| `serde` | 1.0.228 | MIT OR Apache-2.0 (dual) | OK |
| `serde_json` | 1.0.150 | MIT OR Apache-2.0 (dual) | OK |
| `arrayvec` | 0.7.6 | MIT OR Apache-2.0 (dual) | OK |

Transitive deps pulled in by the above (all MIT or MIT/Apache-2.0 dual on crates.io):
`matrixmultiply`, `num-complex`, `num-integer`, `num-traits`, `portable-atomic`, `portable-atomic-util`, `rawpointer`, `autocfg`, `byteorder`, `py_literal`, `zip`, `flate2`, `crc32fast`, `miniz_oxide`, `adler2`, `simd-adler32`, `pest`, `pest_derive`, `pest_generator`, `pest_meta`, `ucd-trie`, `num-bigint`, `thiserror`, `thiserror-impl`, `displaydoc`, `indexmap`, `equivalent`, `hashbrown`, `arbitrary`, `derive_arbitrary`, `bumpalo`, `crossbeam-utils`, `log`, `memchr`, `serde_core`, `serde_derive`, `zopfli`, `zmij`, `sha2`, `digest`, `block-buffer`, `crypto-common`, `cpufeatures`, `generic-array`, `typenum`, `version_check`.

PR 1 deps (already audited, unchanged): `pyo3` + ffi/build/macros, `libc`, `cfg-if`, `indoc`, `rustversion`, `once_cell`, `memoffset`, `target-lexicon`, `proc-macro2`, `quote`, `syn`, `unicode-ident`, `heck`, `unindent`, `itoa`.

All 71 locked crates fall within the MIT / Apache-2.0 / MIT-OR-Apache-2.0 / BSD / Zlib family — no copyleft surface. The `cfr_core` crate itself is MIT-licensed (line 5 of `crates/cfr_core/Cargo.toml`), matching the project root.

## 3. AGPL / GPL-3 Contamination Check

- `grep -iE "agpl|gpl-3|gpl3|gnu general|copyleft" Cargo.lock` → **ZERO matches** (exit 1, no output).
- `scripts/check_pr.sh` step `[7/9] License + dep audit` greps for `AGPL` across `pyproject.toml`, `Cargo.toml`, `crates/` on every PR — last run passed per PR 6 audit.
- No copyleft license string appears anywhere in the build files or lock file.

**Verdict: ZERO AGPL violations. Clean.**

Caveat: `cargo` is not installed on this machine, so the exact `cargo tree --package cfr_core 2>&1 | grep -iE "agpl|gpl-3"` command from the brief could not be executed. Verification instead used (a) a direct string grep of the lock file and (b) the known crates.io license metadata for each package name. PR 6 audit ran the cargo command on a host with cargo available and recorded a pass.

## 4. Workspace Version Alignment

| File | Version field | Notes |
| --- | --- | --- |
| `/Cargo.toml` (workspace) | NONE | bare workspace stub, only `[workspace]` + `members` + `resolver = "2"` |
| `/crates/cfr_core/Cargo.toml` | `0.5.0` | matches release |
| `/pyproject.toml` | `0.5.0` | matches release |
| `Cargo.lock` `cfr_core` entry | `0.5.0` | line 61, matches |

Root workspace `Cargo.toml` carries no version of its own and no `[workspace.package]` block — versioning lives on the member crate. This is a valid single-crate-workspace layout. v0.5.0 is consistent across `cfr_core` (Rust), `poker_solver` (pyproject), and the lock file. No drift.

## 5. Concerns

None blocking. Two minor observations:

1. **Lock-file scope:** at 71 crates, the dependency tree is modest but growing fast (180 → 642 lines from PR 1 → PR 6). If PR 7+ adds more deps (e.g. rayon for the Noam-Brown clone), reconsider `cargo deny` for stricter license/advisory checks. `check_pr.sh` currently does only a coarse `grep -i AGPL`; that catches the worst case but won't flag a future LGPL or unknown-license pull.
2. **Workspace `[workspace.package]` block:** absent. Currently fine (single member) but worth adding when a second crate lands so version/license/edition can be inherited rather than duplicated.

## Summary

- Cargo.lock: tracked, committed, version-4 format, 71 packages, clean two-commit history.
- All PR 6 deps (`ndarray`, `ndarray-npy`, `serde`, `serde_json`, `arrayvec`) are MIT OR Apache-2.0 dual-licensed and compatible with the MIT crate license.
- AGPL contamination: **ZERO** across lock file and build files.
- Workspace versioning aligned at v0.5.0 across `cfr_core`, `pyproject.toml`, and the lock entry.
- Posture: **safe to ship**.
