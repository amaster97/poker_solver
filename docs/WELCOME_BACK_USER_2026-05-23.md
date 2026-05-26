# Welcome Back — Status Snapshot

**Date:** 2026-05-23 (initial) → 2026-05-25 (resume wave refresh)
**Origin HEAD:** `49c1421` on `main` (eleven merges past pre-pause `60a9818`)
**Latest tag:** `v1.7.0` (LIVE GitHub release, engine-only); v1.7.1 and v1.8.0 pending
**Open PRs (7):** #6, #19, #20, #24, #32, #33, #34

## What changed during the pause

The resume wave merged eleven PRs to origin. v1.7.1's cherry-pick ship script (Path A) was retired after seven retries and the bundle is being merged member-by-member via Path B; eight of the ten bundle PRs are now on main. v1.8 Phase 1 (cross-platform SIMD discount kernel) and AVX2 runtime-detect both landed. PR #26 (Phase 2) closed as conflicting and awaits re-cut. Gate 4's turn phase is running 200K iterations in the background.

## New scope (2026-05-25)

Two new tracks were scope-added: **B9 exploitative play** (best-response vs fixed opponent, spec as internal PR 76) and **B10 range fractional frequencies** (W2.2 unblock, spec as internal PR 77). Both spec-only; impl decision deferred until specs land.

## What's blocking what

v1.7.1 tag waits on PR #6 (DCFR vector asymmetric-range tail). v1.8.0 tag waits on Phase 2 (re-cut) + Phase 3 (#33) + Phase 4 (#32). PR #24 docs and PR #34 release notes both on HOLD until their respective tags ship. CI matrix fix (#20) and B9/B10 specs are independent.

For the full per-section breakdown see `docs/SIGNON_SUMMARY_2026-05-25.md`.
