# STATUS — 2026-05-22

## 1. State

| Branch | Tip | Status |
|---|---|---|
| main | `2b67370` | awaiting merge OK |
| integration | `d135add` | PR 1-7 + 3.5/followup landed |
| pr-7-noambrown-diff | shipped | merged to integration |
| pr-11-library-and-packaging | dirty | ~70% complete, working tree uncommitted |

## 2. PRs

| PR | Status | Version | SHA |
|---|---|---|---|
| PR 1-3 | shipped | pre-v0.4 | `a96675c` (PR 3) |
| PR 3.5 | shipped | pre-v0.4 | `9f91c83` + `1cbf52a` |
| PR 4 (card abstraction) | shipped | v0.4.0 | `6565b84` → `5832b2f` |
| PR 5 (postflop + profiler) | shipped | v0.4.0 | `a9d02ca` → `eee9b4b` |
| PR 6 (Rust port) | shipped | v0.5.0 | `0933367` → `6c438b8` |
| PR 7 (Brown diff) | shipped | v0.5.1 | `83d7b9c` → `d135add` |
| PR 4.5 (audit-debt sweep) | shipped | v0.5.2 | `9f09d49` |
| PR 10a (UI mock) | shipped | v0.6.0 | `b880032` |
| PR 11 (library + packaging) | in-flight | v1.0.0 GA target | ~70% on `pr-11-library-and-packaging` |
| PR 8 / 9 / 10b / 12 | staged | v0.7.0→v1.1.0 | — |

## 3. Decisions awaiting (3)

| # | Decision | Default / Recommendation |
|---|---|---|
| 1 | Main merge approval (integration → main) | merge now to land PR 3+3.5+4+5 |
| 2 | Q3 UI iter count (PR 10a) | 1000 (locked); revisit in 10b if under-converged |
| 3 | Delete `origin/equity-precision` | safe; byte-identical to main |

## 4. Numbers

| Metric | Value |
|---|---|
| Tests | 303 functions, 0 fail |
| LOC | ~25K |
| Must-fix bugs caught pre-merge | 7 (none reached main) |
| Docs / memory rules | ~250 docs / 15 rules |
| PR 6 speedup | ~24x Rust (92.9s → 3.88s @ 100k iters, bit-exact) |
| Wall-clock PR 3→5 | ~25 hr |

## 5. Next session priorities (5)

| # | Task | Path / Branch |
|---|---|---|
| 1 | Commit PR 11 → v1.0.0 GA | `pr-11-library-and-packaging` |
| 2 | Launch PR 8 NEON SIMD + cache + PCS | `docs/pr8_prep/launch_kickoff.md` (`pr-8-neon-simd-pcs`) |
| 3 | PR 9 (preflop) | `docs/pr9_prep/` |
| 4 | PR 10b (UI iter refinement) | `docs/pr10_prep/` |
| 5 | Block on user decisions before main push | §3 above |

**v1 ETA:** ~3-4 days remaining (PR 6 → PR 11). PR 12 post-v1, default-skipped.
