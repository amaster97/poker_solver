# v1.6.0 Origin + GitHub Release Verification

**Date**: 2026-05-23
**Tag**: v1.6.0
**Commit**: d885bca

## Origin state (verified)

- `origin/main` HEAD: `d885bca` — "v1.6.0: GUI Gate 2 surfaces (range editor + RvR + node-locking + asymmetric + slider)"
- Tag `v1.6.0` present locally
- Tag `v1.6.0` confirmed on origin (`ls-remote --tags origin v1.6.0` → `d885bcabb1c0eeffe9748f9d2ca9bbe2034a8379 refs/tags/v1.6.0`)
- Annotated tag points at `d885bca` (matches origin/main HEAD)
- Tag ladder clean: v1.3.0 → v1.3.1 → v1.3.2 → v1.4.0 → v1.4.1 → v1.4.2 → v1.4.3 → v1.5.0 → v1.5.1 → **v1.6.0**

## v1.6.0 ship commit (origin/main)

```
commit d885bcabb1c0eeffe9748f9d2ca9bbe2034a8379
Author: amaster97 <amaster1997@gmail.com>
Date:   Sat May 23 16:03:28 2026 -0400

    v1.6.0: GUI Gate 2 surfaces (range editor + RvR + node-locking + asymmetric + slider)

 CHANGELOG.md               | 16 ++++++++++++++++
 crates/cfr_core/Cargo.toml |  2 +-
 poker_solver/__init__.py   |  2 +-
 pyproject.toml             |  2 +-
 4 files changed, 19 insertions(+), 3 deletions(-)
```

## GitHub release

- **Status**: CREATED (did not previously exist)
- **URL**: https://github.com/amaster97/poker_solver/releases/tag/v1.6.0
- **Title**: "v1.6.0: GUI Gate 2 (range editor, RvR, node-locking, asymmetric, slider tiers)"
- **Published**: 2026-05-23T20:14:18Z
- **Draft**: false
- **Prerelease**: false
- **Author**: amaster97
- **Notes**: include features, install, known issues (.dmg experimental, v1.5.0 Brown A2A divergence at deep-cap, Range fractional-frequency), and next-ship roadmap (v1.6.1, v1.7.0)

## gh CLI release list (post-create)

```
v1.6.0	Latest	v1.6.0	2026-05-23T20:14:18Z   (newly created)
v1.5.1	        v1.5.1	2026-05-23T17:29:56Z
v1.5.0	        v1.5.0	2026-05-23T10:46:39Z
v1.4.3	        v1.4.3	2026-05-23T10:30:29Z
...
```

## Anomalies

None. Origin tag, origin/main HEAD, and GitHub release are all coherent and point at `d885bca`.

## Next-ship gates

- **v1.6.1 unblocked**: engine bundle in flight
  - PR 35c paired cap-guard fix (Python delegate)
  - Path C tolerance widening + docs update
- **v1.7.0**: aggregator → vector wiring (`solve_range_vs_range_nash` API) + CLI subcommands

## Source

- Ship report: `/Users/ashen/Desktop/poker_solver/docs/leg18_v1_6_0_ship_report.md`
