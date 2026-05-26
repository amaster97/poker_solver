# Signon Summary — 2026-05-25 (post-pause resume wave)

Good morning. Here is where things stand at the moment you sign back on. State has moved a lot since the pre-pause version of this doc was written around 13:49; eleven PRs have merged in the resume wave, the v1.7.1 ship saga finally cracked, and two new scope items landed.

## Where origin sits

Public origin/main is at `49c1421` ("PR 53c: loosen Layer 3 max L1 ceiling 1.0 -> 1.9 for deep-cap Nash multiplicity"). That's eleven commits past the pre-pause `60a9818`. Latest tag remains `v1.7.0` (LIVE GitHub release, engine-only). v1.7.1 and v1.8.0 are both pending — v1.7.1 because we pivoted away from cherry-pick bundling, v1.8.0 because three Phase PRs (2/3/4) still need to land before the release notes (PR #34) can come off HOLD.

## v1.7.1 ship saga — Path A retired, Path B in flight

Seven retries of `scripts/ship_v1_7_1.sh` all died, each on a different fragility (timeout, golden-stale, EXPECTED_MAIN drift, cherry-pick conflict, agent wall-clock). Decision after retry 7: retire Path A (cherry-pick bundle) and pivot to **Path B (per-PR merge to main, then tag)**. Bundle members are merging individually through normal PR review. Of the original ten-PR bundle, eight are merged (PRs #5 PR 50, #8 PR 52, #9 PR 54, #10 PR 55, #12 PR 56, #14 PR 53b, #15 PR 53c, #18 PR 59) and two remain (#5/#6 dependency tail). Path B agent is in flight.

## What merged this session (post-pause)

Eleven merges took origin from `60a9818` to `49c1421`: #16 and #17 (DCFR vector panic fix + doc cleanup), the v1.7.1 bundle members listed above, #21 (PR 62 v1.7.2 CI-driven release workflow), #22 (PR 65 ship-process hardening Guards B+C), #23 (v1.8 Phase 1 SIMD discount kernel), #27 (ship script pytest timeout bump), #28 (Brown build auto-bootstrap), #29 and #31 (EXPECTED_MAIN SHA bumps for retries 6 and 7), #30 (v1.8 cross-platform SIMD smoke test), and #35 (PR 68 AVX2 runtime-detect for x86_64).

## What is still open

Seven PRs on origin: #6 (DCFR vector asymmetric-range off-by-one, the Path B tail), #19 (Brown acceptance gate hard-fail on missing prereqs), #20 (CI cross-platform matrix — fix in flight), #24 (docs refresh, HOLD for v1.7.1 ship), #32 (v1.8 Phase 4 — compute_strategy SIMD), #33 (v1.8 Phase 3 — update_strategy_sum SIMD), #34 (v1.8.0 release notes HOLD). Note: PR #26 (Phase 2 — update_regret_sum) was CLOSED as conflicting and needs re-cut. Three scope items #76/#77/#78 are internal tracking numbers for specs in flight (B9 exploitative-play, B10 range fractional, PLAN.md update) — not yet GitHub PRs.

## Scope additions today

The user added two new tracks on 2026-05-25: **B9 exploitative play** (best-response vs fixed opponent — spec in flight as internal PR 76) and **B10 range fractional frequencies** (refactor that unblocks W2.2 — spec in flight as internal PR 77). Both are spec-only at the moment; impl decision after specs land.

## Gate 4

River phase complete (PASS on reduced fixtures). Turn phase running at 200K iterations in the background (`/tmp/gate4_200k.log`). Full-fixture river remains architecturally blocked by chance-enum-at-root; that's a v1.8+ concern.

## Memory rules

`answer-first` rule is already in MEMORY.md from the prior session. No new memory rules landed in this resume wave; the existing reversal-chain rules (R1-R11, redundant-swap-hazard, reframed-gate-masks-bugs) are all still active and citable.

## Blocking diagram

v1.7.1 tag waits on PR #6 (Path B tail). v1.8.0 tag waits on Phase 2 (re-cut) + Phase 3 (#33) + Phase 4 (#32). PR #24 (docs refresh) is HOLD-until-v1.7.1-ships. PR #34 (v1.8.0 release notes) is HOLD-until-Phase-2/3/4-merge. CI matrix (#20) is independent and fix is in flight. B9/B10 specs are independent of all release work.

## What to do first

Check `gh pr view 6` and the Path B agent log. If retry 7 has shipped while you were out, run `gh release view v1.7.1`; if not, read the Path B agent's latest status. Either way, the engine is fine — the only thing left between us and v1.7.1 is process.
