# PR 6 Semver Sequencing Verification

**Status:** Read-only analysis. Proposed edits flagged for orchestrator review; not applied.
**Date:** 2026-05-22
**Subject:** Should PR 6 (Rust HUNL postflop port) ship as v0.4.1 (patch) or v0.5.0 (minor)?

## 1. Semver analysis of PR 6 surface

PR 6 ports the PR 5 Python reference HUNL postflop solver to the Rust crate
`crates/cfr_core/`, exposed via PyO3 as `poker_solver._rust`. Per the README
and CHANGELOG language ("ships with PR 6, in flight" + "Selectable via
`--backend rust` on the `solve` CLI"), PR 6 introduces two distinct
NEW public-surface elements:

| Surface | Type | Visible to users? |
|---|---|---|
| `--backend rust` on `solve --hunl-mode postflop` | CLI flag (new accepted value/path) | Yes — externally selectable |
| `poker_solver._rust.solve_hunl_postflop` | PyO3 export | Yes — importable Python API (internal-namespaced but reachable) |
| Bit-exact diff tests vs PR 5 Python reference | test harness | No (test-only) |

Semver (semver.org 2.0.0) rules:

- **MAJOR**: backwards-incompatible API change.
- **MINOR**: backwards-compatible additions to the public API.
- **PATCH**: backwards-compatible bug fixes (no API surface change).

A pure speed port that preserved every call signature and used an internal
implementation switch (e.g. an env var or `os.getenv("POKER_SOLVER_BACKEND")`
plumbing under an already-exposed `backend=...` parameter that was already
accepted) **could** qualify as PATCH. PR 6 does not: a new accepted
`--backend rust` value on the `solve --hunl-mode postflop` path is a new
public-API affordance (users gain the ability to call something they could
not call before), and the PyO3 export adds an importable symbol. Both are
**additions**, not bug fixes.

Per semver: additions to public API => MINOR bump.

## 2. Recommended version

**v0.5.0** (MINOR bump), not v0.4.1 (PATCH bump).

Rationale: PR 6 introduces user-selectable backend dispatch on a CLI mode
that previously did not accept `--backend rust` for the postflop path, and
adds a new PyO3 export. Both are net-new public-API surface area. Semver
2.0.0 reserves PATCH for bug-fix-only releases with no API change. A
~30x speedup is a perf win, but the speedup is *delivered through* new
API surface, so the release is additive, not a pure fix.

(Counter-argument: if `solve --hunl-mode postflop --backend rust` was
already an *accepted* CLI argument in v0.4.0 that silently raised
`NotImplementedError` or fell back to Python, then PR 6 would be filling
in a previously-promised path and a PATCH could be defensible. The PR 5
CLI changelog entry mentions `--hunl-mode postflop` with `--board /
--stacks / --bet-sizes / --max-memory-gb / --abstraction` but does *not*
list `--backend rust` for that mode. Treating PR 6 as adding the
`rust` value to that mode's `--backend` is the safer reading => MINOR.)

## 3. Updates needed if v0.5.0 is adopted

### 3a. README.md edits

Two literal `v0.4.1` / "PR 6, in flight" mentions in `README.md`:

- **Line 70-73** (Features section):
  ```
  - **Rust HUNL postflop solver** *(ships with PR 6, in flight)* —
    Python-tier reference solver plus a Rust-tier port targeting ~30x
    speedup, bit-exact diff-tested against the Python reference on
    shared seeds. Selectable via `--backend rust` on the `solve` CLI.
  ```
  Recommend keeping "ships with PR 6, in flight" wording (status is
  accurate) — no version label appears here, so no edit required.

- **Line 127-128** (Quick start example):
  ```
  # Same river subgame on the Rust tier (ships with PR 6, in flight):
  ```
  No version label — no edit required.

- **No `v0.4.1` literal** appears in `README.md` today. Verified via
  full read. (The only version label is line 14: `Current version: 0.4.0`.)

**Net README edits required for v0.5.0 adoption:** zero (README already
neutral on next version; only the CHANGELOG carries the v0.4.1 reference).

### 3b. CHANGELOG.md edits

The `Unreleased` section (lines 8-17) explicitly says:
```
- PR 6 in flight (Rust HUNL port): ...  Ships in v0.4.1.
```

Edit: change `Ships in v0.4.1` -> `Ships in v0.5.0` (line 15).

On PR 6 merge day, also:
- Add new `## [0.5.0] - <date>` section above the current `## [0.4.0]`.
- Move the PR 6 entry from `Unreleased` into `[0.5.0]`.
- Add link reference `[0.5.0]: ./` to the bottom of the file (line ~293).

### 3c. `poker_solver/__init__.py` edits (PR 6 commit)

Line 158: `__version__ = "0.4.0"` -> `__version__ = "0.5.0"` on the PR 6
merge commit (matching the pattern from PR 5's `0.3.x -> 0.4.0` bump).

## 4. Comparison against PR 5's bump

PR 5 went `0.3.1 -> 0.4.0` (MINOR). Per the v0.4.0 changelog entry:

- **Added:** `solve_hunl_postflop(...)`, `HUNLSolveResult`, `MemoryProbe`,
  `MemoryReport`, `StreetMemoryEntry`, `precompute-abstraction` CLI
  subcommand, `--hunl-mode postflop` and its flags. All public, all new.
- **Changed:** `HUNLConfig.abstraction` field added (additive default
  `None`); `solve()` dispatch branch added for HUNLPoker postflop.

That is *exactly* the MINOR-bump pattern: additive public API, no
breaking changes. PR 5 was correctly bumped to `0.4.0`.

PR 6's surface (one new CLI flag value + one new PyO3 export) is smaller
than PR 5's, but it is still *additive public API*, not a pure bug fix.
The consistent application of semver gives PR 6 the same treatment: MINOR
bump => **v0.5.0**.

The relevant version-bump audit trail:

| Release | Surface change | Bump type | Correct? |
|---|---|---|---|
| 0.1.0 -> 0.2.0 (PR 2, Leduc) | New `LeducPoker`, `LeducState`, CLI `--game leduc` | MINOR | Yes |
| 0.2.0 -> 0.3.0 (PR 3 + 3.5) | New `HUNLPoker`, push/fold API, `--hunl-mode` | MINOR | Yes |
| 0.3.0 -> 0.3.1 | Two bug fixes, no API change | PATCH | Yes (textbook PATCH) |
| 0.3.1 -> 0.4.0 (PR 4 + 5) | New abstraction package + postflop solver | MINOR | Yes |
| **0.4.0 -> 0.5.0 (PR 6)** | **New `--backend rust` path + PyO3 export** | **MINOR** | **Proposed** |

The v0.3.0 -> v0.3.1 PATCH is the right reference point for what "pure
patch" looks like in this repo: two `Fixed` entries, zero `Added`, zero
`Changed` (other than the bug-fix line). PR 6 has `Added` content =>
MINOR is consistent with the project's own history.

## 5. Edge-case consideration

If the orchestrator wants to argue PR 6 is PATCH-eligible on the grounds
that "Rust is just the perf tier of an already-public algorithm," note
that the same argument would have downgraded PR 2's Rust Leduc port
(part of `0.1.0 -> 0.2.0`) and PR 1's Rust Kuhn port (part of the initial
`0.1.0` cut). Both were treated as MINOR-worthy in their releases
because the Rust backend is independently selectable user-facing API.
Consistency with that precedent confirms MINOR for PR 6.

## 6. Recommendation summary

| Item | Current | Proposed | Required edit |
|---|---|---|---|
| `__version__` (PR 6 commit) | `0.4.0` | `0.5.0` | Yes |
| `CHANGELOG.md` line 15 | "Ships in v0.4.1" | "Ships in v0.5.0" | Yes |
| `CHANGELOG.md` new section (on merge) | (n/a) | `## [0.5.0]` block | Add on PR 6 merge |
| `CHANGELOG.md` link refs | `[0.4.0]: ./` | + `[0.5.0]: ./` | Add on PR 6 merge |
| `README.md` "Current version" (on merge) | `0.4.0` | `0.5.0` | Update on PR 6 merge |
| Release tag | `v0.4.1` (planned) | `v0.5.0` | Tag with new label |

**Bottom line:** PR 6 should ship as **v0.5.0**, not v0.4.1. The current
CHANGELOG wording ("Ships in v0.4.1") is the only literal reference that
needs to change today; everything else updates on PR 6 merge.
