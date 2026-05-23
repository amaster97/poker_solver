# poker_solver v0.5.2 release notes

**Release date:** 2026-05-22
**Codename:** "Audit-debt sweep"

Patch release. Bundles 13 mechanical should-fix / nice-to-fix items from
the PR 3, 3.5, 4, and 5 audit reports into one cleanup PR. No behavior
changes, no spec amendments, no new public API. Pure audit-debt
clearance setting up an audit-debt-zero state heading into PR 7+.

Internal-only edits across 7 source files; ~30-50 LoC delta. v0.5.1
public contract unchanged. Per `docs/pr6_prep/semver_sequencing.md`,
"no public API change" + "no behavior change" maps to PATCH.

---

## What's new in v0.5.2

### 1. PR 4.5 audit-debt sweep (13 mechanical fixes)

One cleanup PR consolidating items from four prior audits. Canonical
scope at `docs/pr4_5_audit_debt/launch_kickoff.md` §2.

### 2. License attribution headers

One-line "no third-party code derivation; original implementation"
header added to three modules per PR 3 + PR 4 audits:
`poker_solver/hunl.py` (3-A), `poker_solver/action_abstraction.py`
(3-B), `poker_solver/abstraction/equity_features.py` (4-A).

### 3. Error-type consistency

- `AssertionError` → `ValueError` in `HUNLConfig.__post_init__` rake
  validation (`hunl.py:107, 109`) so all `__post_init__` paths raise
  one type (3-C).
- `PushFoldChartUnavailable` now subclasses `ValueError`
  (`pushfold.py:30`) so `except ValueError` catches it (3.5-A).

### 4. Named constants for magic numbers

- `mc_iterations < 5000` autosize threshold in `precompute.py:452-455`
  surfaced as explicit `max_boards_per_street=None` (autosize) / `-1`
  (no cap) kwarg, replacing implicit-trigger magic (4-D).
- `v1-placeholder` dropped from `PUSHFOLD_CHART_VERSIONS`
  (`pushfold.py:25`); loader rejects dry-run output (3.5-B).

### 5. SHOWDOWN predicate tighten

`hunl.py:336` changed from `state.street >= Street.FLOP` to explicit
`state.street in (Street.FLOP, Street.TURN, Street.RIVER)` (4-B).
Latent — solver's `is_terminal` guard masked it — but the explicit
form removes the latent-bug surface.

### 6. Dead-code + unreachable-branch hygiene

Unused `field` import dropped (`hunl.py:14`, 3-D); unused `numpy`
import dropped (`profiler/memory.py:508-510`, 5-A); dead
`_canonical_hand_classes()` removed (`pushfold.py:185`, 3.5-C).
`enumerate_legal_actions` stack≤0 marked unreachable
(`action_abstraction.py:210-211`, 3-E); `_kmeans_plusplus_init`
empty-cluster fallback marked unreachable
(`emd_clustering.py:188-196`, 4-C).

---

## What it doesn't add

- **No new public API.** All edits internal; nothing added to
  `poker_solver.__init__` exports.
- **No new CLI flags.** `solve` surface unchanged from v0.5.1.
- **No behavior changes.** Every edit preserves observable behavior.
  The only user-facing API change — `precompute.py`'s
  `max_boards_per_street` kwarg (4-D) — is additive with a
  backwards-compatible `None` default.
- **No new wheel dependencies.** `pyproject.toml` untouched.
- **Audit-debt cleanup only.** Per `launch_kickoff.md` §3, k-means
  tuning, byte-determinism design, 6 skip-marked PR 5 tests,
  spec-amendment-requiring items, and CLI-integration items are
  deferred.

---

## Honest caveats

### 1. Some should-fix items deferred

PR 4.5 is a strict subset of `docs/audit_followup_backlog.md`. ~25
nice-to-fix items remain (`_canonicalize` rename, docstring
expansions, magic-constant calibration beyond 4-D, test coverage
additions for PR 4 / PR 5 gaps, byte-determinism for
`save_abstraction`). Each is either spec-amendment-requiring,
post-PR-6 (production-scale evidence needed), or belongs to a future
feature PR's natural surface — out of scope per `launch_kickoff.md` §3.

### 2. Production-scale full HUNL solve still pending

PR 4.5 does not validate solver behavior at production scale. PR 6's
Rust port enables full enumeration; until then k-means quality
intuitions remain Python-tuned and could shift under Rust enumeration.
Per the "don't extrapolate" discipline, no quality claims about tuned
parameters are made here.

### 3. Mechanical-fix scope deliberately narrow

Items were selected for "single agent fixes mechanically in <15 min
with no spec interpretation." Excludes PR 3 `HUNLState.config`
source-of-truth, PR 3.5 d=2 universal-jam landmark, and PR 3.5
strategic-equivalence collapse — each needs a strategic decision.

---

## Acknowledgments

- **PR 3 audit** (`docs/pr3_prep/audit_report.md`) — Items 3-A to 3-E.
- **PR 3.5 audit** (`docs/pr3_5_prep/audit_report.md`) — 3.5-A to 3.5-C.
- **PR 4 audit** (`docs/pr4_prep/audit_report.md`) — 4-A to 4-D.
- **PR 5 audit** (`docs/pr5_prep/audit_report.md`) — 5-A.
- **Cross-PR cleanup planning** at `docs/cross_pr_cleanup_plan.md` and
  `docs/audit_followup_backlog.md` consolidated the 13 items into one
  batchable PR rather than dripping into feature PRs.

---

## License

MIT. No new third-party code introduced. Header additions (3-A, 3-B,
4-A) attribute affected modules as original.

For the full plan, decision log, and roadmap, see `PLAN.md`.
