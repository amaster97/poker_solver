# Reference Repo Audit

**Date:** 2026-05-22
**Scope:** Read-only audit of `references/code/` against `PLAN.md §6 / §8` license table and `references/README.md §2`.
**Method:** No clones, fetches, or modifications. Inspected `LICENSE` headers, `git log` last-commit dates, repo sizes, and build-system manifests.

---

## 1. Repo inventory

All six expected repos are present and non-empty. Last-modified date is the last upstream commit (per `git log -1`), which is a much better freshness proxy than filesystem mtime (all files mtime-stamp to 2026-05-20, the local clone date).

| # | Repo | License | Present | In README §2 | Size on disk | Last upstream commit |
|---|---|---|---|---|---|---|
| 1 | `noambrown_poker_solver` | MIT | Yes | Yes | 568 KB | 2026-01-05 (`6a10442` Fixed GUI reach probabilities) |
| 2 | `slumbot2019` | MIT | Yes | Yes | 2.8 MB | 2023-09-18 (`a74c99d` Fix crash on systems with no abstraction) |
| 3 | `open_spiel` | Apache 2.0 | Yes | Yes | 40 MB | 2026-05-12 (`32bfbec` Merge PR #1543) |
| 4 | `postflop-solver` | AGPL-3.0-or-later | Yes | Yes | 828 KB | 2023-10-01 (`9d1509f` docs: update README) |
| 5 | `TexasSolver` | AGPL-3.0 | Yes | Yes | 128 MB | 2026-03-31 (`d926d24` Update README to emphasize faster GPU version) |
| 6 | `shark-2.0` | Unlicensed (no LICENSE file) | Yes | Yes | 1.0 MB | 2026-04-12 (`c9dc07d` dll fix) |

**README coverage:** 6/6. Every directory in `references/code/` has a corresponding entry in `references/README.md §2` license table and §7 reading order. No phantom directories, no missing index entries.

---

## 2. License compliance per repo

Each repo's `LICENSE` file header was inspected and matched against `PLAN.md §8 license audit table` (line 263–273) and `references/README.md §2` (line 26–34).

| Repo | LICENSE-file header (verified) | PLAN.md / README claim | Match? | Project copy policy |
|---|---|---|---|---|
| `noambrown_poker_solver` | `MIT License — Copyright (c) 2025 Noam Brown` | MIT | Yes | OK to port verbatim with notice (MIT-friendly to our MIT project) |
| `slumbot2019` | `MIT License — Copyright (c) 2019 Eric Jackson` | MIT | Yes | OK to port verbatim with notice |
| `open_spiel` | `Apache License Version 2.0, January 2004` | Apache 2.0 | Yes | OK to copy with attribution; also Kuhn/Leduc correctness oracle |
| `postflop-solver` | `GNU AFFERO GENERAL PUBLIC LICENSE Version 3` | AGPL-3.0-or-later | Yes | Read-only inspiration only. Verbatim copy would contaminate our MIT project. |
| `TexasSolver` | `GNU AFFERO GENERAL PUBLIC LICENSE Version 3` | AGPL-3.0 (+ active commercial relicensing per README §2) | Yes | Read-only inspiration only. Author monetizes commercial relicensing. |
| `shark-2.0` | **No LICENSE file present.** Confirmed via `ls`. | "Unlicensed" / all-rights-reserved | Yes | Read-only inspiration only. Default copyright = all rights reserved. |

**Project policy reminder (PLAN.md §1, line 16):** Project license is locked to **MIT**. AGPL contamination is a one-way door we explicitly avoid. The three MIT/Apache repos (`noambrown_poker_solver`, `slumbot2019`, `open_spiel`) are the only sources from which verbatim or close-paraphrase code may be ported into our crate.

**Verdict:** 6/6 repo licenses match documentation. Zero discrepancies. Compliance is intact.

---

## 3. Topic coverage gaps

Mapping the major technical topics referenced in `PLAN.md` and `references/README.md` to the six local repos:

| Topic | Locally referenced in | Local repo coverage? |
|---|---|---|
| Vanilla CFR / CFR+ / Linear CFR / DCFR | README §3 | Yes — `noambrown_poker_solver/cpp/src/trainer.cpp` (all flavors via `--algo`), `slumbot2019/src/cfrp.cpp` |
| External-sampling MCCFR | README §3 | Yes — `slumbot2019/src/ecfr.cpp`, `open_spiel/.../external_sampling_mccfr.cc`, `noambrown_poker_solver` |
| Hyperparameter schedules (HS-DCFR) | README §3.2 | **Gap.** Paper only (`papers/hyperparam_schedules_2024.pdf`). No reference implementation in `code/`. |
| Predictive CFR+ (PCFR+) | README §11 known gaps | **Gap.** No paper, no implementation. (Already flagged as known gap.) |
| Deep CFR | README §3.4 | **Partial.** Paper present (`deep_cfr_brown_2018.pdf`); no reference implementation in our `code/`. Not on critical path for v1. |
| Action abstraction (bet-size DSL) | README §4 | Yes — `postflop-solver/src/bet_size.rs` (AGPL pattern), `noambrown_poker_solver/cpp/src/river_game.cpp` (MIT port-safe), `slumbot2019/src/betting_tree_builder.cpp` (MIT) |
| Card abstraction / k-means / EHS / OCHS / EMD | README §5 | Yes for infrastructure — `slumbot2019/src/buckets.cpp`, `build_kmeans_buckets.cpp`, `build_rollout_features.cpp` (MIT). README §11 already flags lack of integrated end-to-end pipeline. |
| Subgame resolving (CFR-D, unsafe, combined) | README §8 | Yes — `slumbot2019/src/eg_cfr.cpp`, `unsafe_eg_cfr.cpp`, `combined_eg_cfr.cpp`, `cfrd_eg_cfr.cpp` (MIT) |
| HUNL Rust postflop reference | README §7 | Partial — `postflop-solver` is the only pure-Rust HUNL reference, but AGPL (pattern-only). MIT-licensed Rust HUNL reference: **gap**. Mitigation: port from `noambrown_poker_solver` (MIT C++/Python) into Rust ourselves. |
| Best-response / exploitability for Kuhn/Leduc | README §7 Apache | Yes — `open_spiel/.../best_response.cc` (Apache 2.0, copy-with-attribution) |
| QRE-CFR | README §11 known gaps | **Gap.** Already flagged. |
| DeepStack continual re-solving | README §11 known gaps | **Gap.** Already flagged. |
| ACPC wire protocol | README §11 known gaps | **Gap.** Already flagged. `open_spiel/.../universal_poker/` wraps it but not a clean standalone reference. |
| ICM / bounty (MTT) solving | README §11 known gaps | Out of scope for v1; deferred. |
| 6+ way preflop solver | README §11 known gaps | **Gap.** Already flagged. Out of scope for v1. |

**New gaps surfaced by this audit (beyond README §11):**

- **No MIT/Apache reference for k-means EMD bucketing pipeline end-to-end.** Slumbot has the per-step tooling but no integrated walkthrough. README §11 already calls this out. Not blocking — we will derive from paper + Slumbot building blocks.
- **No MIT-licensed pure-Rust HUNL solver.** This is the central reason PR 6 (HUNL Rust port) is a port of `noambrown_poker_solver` (MIT C++/Python) into Rust rather than a fork of `postflop-solver` (AGPL).

All other gaps are pre-existing and already enumerated in README §11.

---

## 4. Refresh recommendations

Threshold: "stale" = last upstream commit > 12 months ago from today (2026-05-22). Cutoff date = 2025-05-22.

| Repo | Last commit | Age | Stale? | Action |
|---|---|---|---|---|
| `noambrown_poker_solver` | 2026-01-05 | ~4.5 months | No | Hold. |
| `open_spiel` | 2026-05-12 | ~10 days | No | Hold. Most actively maintained of the six. |
| `shark-2.0` | 2026-04-12 | ~1.5 months | No | Hold. Most-recently-active of the C++ HUNL solvers (per its own `_NOTES.md`). |
| `TexasSolver` | 2026-03-31 | ~2 months | No | Hold. |
| `slumbot2019` | 2023-09-18 | ~2 years 8 months | **Yes — stale** | **No refresh action.** Slumbot2019 is a frozen ACPC-era reference, not an actively-developed codebase. The 2019 ECCV-era state *is* the reference. Staleness is the point. |
| `postflop-solver` | 2023-10-01 | ~2 years 7 months | **Yes — stale** | **No refresh action.** Author publicly suspended OSS development in Oct 2023 (README §7, line 172). The repo is effectively frozen at v0.4 by author intent. Staleness reflects upstream death, not local data freshness. |

**Net recommendation:** No refresh actions for any repo. The two "stale" repos are stale by upstream intent (one frozen reference, one author-suspended), and refetching would not change content. The four other repos are fresh enough (≤6 months) that re-cloning would yield marginal-at-best new content for the topics we extract from them (algorithm structure, license, build-system layout).

**Optional follow-up (low priority):** If we touch any of the four active repos again for PR 6+, do a `git fetch` (read-only) to capture incremental commits before mining a new pattern from them. Don't preemptively refresh.

---

## 5. Build status (read-only check, no actual build)

For the C++ HUNL references in PLAN.md §6, verify the build system is present and uses the expected tooling. Not running the build — just confirming the manifest exists and signals the right tool.

| Repo | Expected build tool | Build-config file present? | Status |
|---|---|---|---|
| `noambrown_poker_solver/cpp/` | CMake | `cpp/CMakeLists.txt` — `cmake_minimum_required(VERSION 3.16)`, C++17, `project(river_solver_optimized)` | OK. CMake-based as documented in README §7 line 163. No reason to expect break. |
| `shark-2.0` | CMake | `CMakeLists.txt` at root — `cmake_minimum_required(VERSION 3.15)`, C++20, `find_package(FLTK / TBB / PNG / JPEG / ZLIB)`, produces `shark` GUI + `shark_cli` headless | OK. CMake-based. External deps (FLTK + TBB) are heavy; not required for our pattern-mining use. |
| `slumbot2019` | Make | `Makefile` (11 KB) at root | OK. Makefile-based. README §7 line 164 documents this. Not CMake. |
| `TexasSolver` | qmake (Qt) | `TexasSolverGui.pro` at root. No `CMakeLists.txt` at root. | Qt qmake project, not CMake. Matches the "Qt GUI" description in README §7 line 174. |
| `open_spiel` | Bazel + CMake + pip | `install.sh`, `pyproject.toml`, `setup.py` at root | OK. Documented multi-build system. Not building locally; using as source-text reference only. |
| `postflop-solver` | Cargo | `Cargo.toml` (661 B) | OK. Pure Rust crate. Build artifacts not needed; pattern-only AGPL. |

**Verdict:** Build-config files match documented tooling for all six repos. `noambrown_poker_solver/cpp/CMakeLists.txt` is present with `cmake_minimum_required(VERSION 3.16)` and `CMAKE_CXX_STANDARD 17` — fully consistent with the description in `references/README.md §7`. No indication anything has been touched since clone (mtimes 2026-05-20). If we ever need to actually build `noambrown_poker_solver`, the expected one-liner is `cd cpp && mkdir build && cd build && cmake .. && make`; this audit does not exercise that path.

---

## 6. Summary

- **6 / 6 repos present, non-empty, indexed in `references/README.md §2`, and license-matched against `PLAN.md §8`.**
- **License compliance fully intact.** Zero discrepancies between LICENSE-file headers and the documented audit table. The MIT-locked project status (`PLAN.md §1`) is safe so long as we continue to port code only from `noambrown_poker_solver`, `slumbot2019`, `open_spiel`.
- **No new gaps beyond those already enumerated in `references/README.md §11`.** New observation: no MIT-licensed pure-Rust HUNL solver exists locally, which is precisely why PR 6 ports the MIT C++/Python `noambrown_poker_solver` into Rust rather than reusing the AGPL Rust `postflop-solver`.
- **Refresh:** none recommended. Two repos are stale-by-intent (Slumbot frozen reference, postflop-solver author-suspended); the other four are fresh (≤6 months).
- **Build status:** all C++ build manifests present and matching their documented tooling. `noambrown_poker_solver` CMake setup is intact and should still build (read-only verified — not exercised).
