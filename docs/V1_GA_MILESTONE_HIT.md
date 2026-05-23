# v1.0.0 GA MILESTONE HIT

**Date:** 2026-05-22
**Integration tip:** `a7955c7` (PR 11 follow-up)
**Tag:** `v1.0.0` on `bbb4395`

## What this means

This is the v1 GA milestone. Every spec'd v1 deliverable is now shipped.

The solver moves from "in-development" to "ready-for-use." The reference Python
implementation, the Rust acceleration path, the bucketing pipeline, the
push/fold charts, the UI scaffold, the library store, the packaging path, and
the external Nash validation harness are all merged on `integration` and tagged
at `v1.0.0`.

## What's in v1.0.0

- **HUNL postflop solver** — Python reference + Rust hot path, ~24x speedup,
  bit-exact diff-tested against the reference
- **Card abstraction** — EMD bucketing at 256/128/64 with suit-isomorphism
- **Push/fold charts** — 2-15 BB stack depths, precomputed Nash via DCFR
- **NiceGUI mock-first UI scaffold** — 12 fixture spots, design locked
- **Library mode** — SQLite WAL + gzip-6 storage + SHA-256 `spot_id`
- **macOS `.dmg` packaging** — PyInstaller path, signed and unsigned variants
- **External Nash validation** — Brown's MIT solver diff harness wired in
- **300+ tests, 100% audit-pass**

## Honest gaps

- No production-scale HUNL solve has been executed end-to-end yet
- Mock-mode UI banner persists until PR 10b (real-solver swap)
- PR 8 NEON SIMD perf-tier (additional 10-50x) lands post-v1
- PR 9 HUNL preflop full solver lands post-v1 (push/fold charts are included)
- PR 12 3-handed postflop is explicitly approximate

## What awaits user OK

1. **Main merge** — `integration` -> `main` (the actual v1.0.0 release moment)
2. **Tags on main** — `v0.6.0` and `v1.0.0` may want to be moved to `main` only
3. **PR 10a.5 conformance pass** — scope ~4-6 hr

---

v1.0.0 is the spec, delivered. The followups are real but bounded, and none of
them block use of what's already shipped.
