# v0.4.0 bump consistency sweep

**Date:** 2026-05-22
**Context:** PR 6 working tree carries the v0.4.0 bump. This sweep verifies
every file that references the package version is consistent with the new
`0.4.0` baseline. Source files were already bumped (`__init__.py`,
`pyproject.toml`, `CHANGELOG.md`); this sweep is documentation-only.

## Files audited

| File | Result |
|---|---|
| `poker_solver/__init__.py` | `__version__ = "0.4.0"` — already bumped, no edit. |
| `pyproject.toml` | `version = "0.4.0"` — already bumped, no edit. |
| `CHANGELOG.md` | `[0.4.0] - 2026-05-22` section present — no edit. |
| `README.md` | **2 edits applied** (see below). |
| `docs/release_notes_v0.3.md` | Historical — **not touched**. |
| `docs/release_notes_v0.3.1.md` | Historical — **not touched**. |
| `docs/wake_up_brief_2026-05-22.md` | All "v0.3 capstone" mentions are commit-table descriptions of PR 3.5 history — **not touched**. |
| `docs/architecture.md` | No current-state version reference (only generic `__version__` column entries in module tables) — **not touched**. |
| `docs/roadmap_status_2026-05-22.md` | **1 edit applied** (see below). All other v0.3 mentions describe historical PR 3.5 capstone scope or filename references — left alone. |

## Edits applied

### Edit 1 — `README.md` lines 14-16 (Status block)

**Before:**

```
- **Current version:** 0.3.0 ("HUNL substrate") — see
  [`CHANGELOG.md`](CHANGELOG.md) and
  [`docs/release_notes_v0.3.md`](docs/release_notes_v0.3.md).
```

**After:**

```
- **Current version:** 0.4.0 ("card abstraction + HUNL postflop solve") —
  see [`CHANGELOG.md`](CHANGELOG.md). Historical release notes:
  [`docs/release_notes_v0.3.md`](docs/release_notes_v0.3.md),
  [`docs/release_notes_v0.3.1.md`](docs/release_notes_v0.3.1.md).
```

**Why:** Current-state version reference. The "HUNL substrate" tag was the
PR 3.5 capstone framing; v0.4.0 adds PR 4 (card abstraction) + PR 5 (HUNL
postflop solve), so reframe accordingly. Also added the v0.3.1 release
notes link (was previously missing from the README despite the file
existing).

### Edit 2 — `README.md` line 23 (Features heading)

**Before:**

```
## Features (v0.3)
```

**After:**

```
## Features (v0.4)
```

**Why:** Section header describes the **current** feature set. The body of
that section already lists card abstraction (added in PR 4 / v0.4.0), so
the v0.3 label was stale even relative to its own content.

### Edit 3 — `docs/roadmap_status_2026-05-22.md` line 116 (Honest gaps)

**Before:**

```
- **__version__ lag:** `poker_solver.__version__` is `0.2.0` but the release tag / `pyproject.toml` are `0.3.0`. CHANGELOG calls this out; deferred reconciliation.
```

**After:**

```
- **__version__ lag:** reconciled in the v0.4.0 bump — `poker_solver.__version__`, `pyproject.toml`, and `CHANGELOG.md` all read `0.4.0` now (no longer trailing).
```

**Why:** This bullet described a stale open item. The PR 5 / PR 6 v0.4.0
bump explicitly reconciled all three locations (and the CHANGELOG's
`[0.4.0] §Internal` block calls this out: "`__version__` bumped to
`0.4.0` (lag from v0.3.0 fully reconciled)"). Leaving the bullet in the
"honest gaps" section as-is would actively misrepresent current state.

## Items deliberately left as v0.3 (historical)

These references describe past commits, past release scope, or filenames
of historical release-note documents. They are correctly historical and
must NOT be bumped:

- `docs/release_notes_v0.3.md` and `docs/release_notes_v0.3.1.md` — the
  v0.3.0 / v0.3.1 release-notes documents themselves (per task
  constraints, not touched).
- `docs/wake_up_brief_2026-05-22.md` lines 30-31 — commit-table rows
  describing what PR 3.5 shipped as ("PR 3.5 + v0.3 capstone"). That
  commit was the v0.3 capstone at the time it landed; describing it that
  way in a historical commit log remains accurate.
- `docs/roadmap_status_2026-05-22.md` lines 17, 25, 27 — table row for
  PR 3.5's scope at-the-time and filename references to the v0.3 release
  notes. Both historical.
- `README.md` lines 16-17 (after Edit 1) — link text to the v0.3 / v0.3.1
  release-notes filenames. The filenames themselves are historical and
  must stay as-is so the links resolve.
- `CHANGELOG.md` — the `[0.3.0]` and `[0.3.1]` sections themselves
  (changelogs are append-only by definition).

## Source files explicitly NOT touched

Per task constraints, the version bump in source code (`__init__.py`,
`pyproject.toml`) was already complete in PR 6's working tree before this
sweep ran. Sweep verified the bump is present; no source-code edits made.

## Summary

- **3 edits** applied across **2 documentation files** (`README.md`,
  `docs/roadmap_status_2026-05-22.md`).
- **6 files** verified clean (source code already bumped, or historical
  references correctly preserved).
- **No source code touched** — sweep was documentation-only.

Post-sweep, every current-state mention of the package version reads
`0.4.0`; every historical mention reads `0.3.x` and correctly describes
past releases or past commits.
