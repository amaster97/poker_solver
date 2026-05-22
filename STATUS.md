# STATUS — 2026-05-22

## 1. State

| Branch | Tip | Status |
|---|---|---|
| main | `2b67370` | awaiting merge OK |
| integration | `d135add` | PR 1-7 + 3.5/followup landed |
| pr-7-noambrown-diff | shipped | merged to integration |

## 2. PRs

| PR | Status | Version | SHA |
|---|---|---|---|
| PR 1-3 | shipped | pre-v0.4 | `a96675c` (PR 3) |
| PR 3.5 | shipped | pre-v0.4 | `9f91c83` + `1cbf52a` |
| PR 4 (card abstraction) | shipped | v0.4.0 | `6565b84` → `5832b2f` |
| PR 5 (postflop + profiler) | shipped | v0.4.0 | `a9d02ca` → `eee9b4b` |
| PR 6 (Rust port) | shipped | v0.5.0 | `0933367` → `6c438b8` |
| PR 7 (Brown diff) | shipped | v0.5.1 | `83d7b9c` → `d135add` |
| PR 4.5 (audit-debt sweep) | mid-audit | v0.5.2 | READY-WITH-PATCHES; must-fixes in flight |
| PR 8 / 9 / 10a / 10b / 11 / 12 | staged | v0.6.0→v1.1.0 | — |

## 3. Decisions awaiting (3)

| # | Decision | Default / Recommendation |
|---|---|---|
| 1 | Main merge approval (integration → main) | merge now to land PR 3+3.5+4+5 |
| 2 | Q3 UI iter count (PR 10a) | 1000 (locked); revisit in 10b if under-converged |
| 3 | Delete `origin/equity-precision` | safe; byte-identical to main |

## 4. Numbers

| Metric | Value |
|---|---|
| Tests | 220+ functions, 11 skip, 0 fail |
| LOC delta (PR 3-6 vs main) | ~+12,500 / -69 across 38 files |
| Must-fix bugs caught pre-merge | 7 (none reached main) |
| Docs / memory rules | 137 docs (~43k lines) / 15 rules |
| PR 6 speedup | ~24x Rust (92.9s → 3.88s @ 100k iters, bit-exact) |
| Wall-clock PR 3→5 | ~25 hr |

## 5. Next session priorities (5)

| # | Task | Path / Branch |
|---|---|---|
| 1 | Verify PR 7 commit landed (or resume pipeline) | `docs/pr7_prep/commit_pipeline_v2.md` |
| 2 | Launch PR 4.5 audit-debt sweep (drain 77 items) | `docs/pr4_5_audit_debt/launch_kickoff.md` |
| 3 | Launch PR 8 NEON SIMD + cache + PCS | `docs/pr8_prep/launch_kickoff.md` (`pr-8-neon-simd-pcs`) |
| 4 | PR 9 + PR 10a in parallel (preflop + UI mock) | `docs/pr9_prep/`, `docs/pr10_prep/` |
| 5 | Block on user decisions before main push | §3 above |

**v1 ETA:** ~3-4 days remaining (PR 6 → PR 11). PR 12 post-v1, default-skipped.
