# STATUS — 2026-05-22 — **v1.0.0 GA HIT**

## 1. State

| Branch | Tip | Status |
|---|---|---|
| main | `2b67370` | awaiting v1.0.0 merge OK |
| integration | `a7955c7` | PR 1-7 + 3.5/10a/11 landed; v1.0.0 tag on `bbb4395` |
| pr-11-library-and-packaging | `6af3684` | shipped → integration |

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
| **PR 11 (library + packaging)** | **shipped** | **v1.0.0 GA** | `6af3684` → `bbb4395` |
| PR 8 / 9 / 10a.5 / 10b / 12 | staged | v1.1.0+ | — |

**v1.0.0 GA reached** — milestone tag on integration.

## 3. Decisions awaiting (4)

| # | Decision | Default / Recommendation |
|---|---|---|
| 1 | Main merge approval (→ v1.0.0 to main) | merge now; this is the GA release |
| 2 | Confirm v0.6.0 + v1.0.0 tags on integration (autonomous) | keep; re-tag on main after merge |
| 3 | PR 10a.5 conformance pass scope | clear 5 fail + 7 xfail before PR 8 |
| 4 | Delete `origin/equity-precision` | safe; byte-identical to main |

## 4. Numbers

| Metric | Value |
|---|---|
| Tests | ~330 functions (PR 11 +27), 5 fail / 7 xfail (PR 10a.5) |
| LOC | ~29K (PR 11 +~4,400) |
| Must-fix bugs caught pre-merge | 7 (none reached main) |
| PR 6 speedup | ~24x Rust (92.9s → 3.88s @ 100k iters, bit-exact) |
| PRs shipped this session | 10 |

## 5. Next session priorities (5)

| # | Task | Path / Branch |
|---|---|---|
| 1 | Main merge (v1.0.0 GA → main) + re-tag | integration `a7955c7` |
| 2 | PR 10a.5 conformance pass | clear 5 fail + 7 xfail |
| 3 | PR 8 NEON SIMD + cache + PCS | `docs/pr8_prep/launch_kickoff.md` |
| 4 | PR 9 (preflop blueprint) | `docs/pr9_prep/` |
| 5 | PR 10b (real solver swap) + PR 12 post-v1 | `docs/pr10_prep/` |
