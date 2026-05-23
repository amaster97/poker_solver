# v0.5.0 Version Consistency Sanity Scan

**Date:** 2026-05-22
**Scope:** Verify that all version references in shipping docs / config are
consistent with the locked v0.5.0 release decision (per
`docs/pr6_prep/semver_sequencing.md`).

**Files in scope (current-state surfaces):**
- `README.md`
- `CHANGELOG.md`
- `docs/release_notes_v0.5.0.md`
- `docs/release_notes_v0.4.0.md` (does not exist — see note)
- `poker_solver/__init__.py`
- `pyproject.toml`

**Files explicitly out of scope (historical/audit-trail artifacts):**
- `docs/cross_doc_consistency_v2.md` (audit-trail doc that *discusses* the
  v0.4.1 → v0.5.0 decision; v0.4.1 mentions are deliberate history)
- `docs/pr6_prep/semver_sequencing.md` (the decision doc itself; v0.4.1
  mentions are the "before" half of the proposed patch and are deliberate)

## 1. v0.4.1 occurrences (target: 0)

```
$ grep -rn "v0.4.1\|v0\.4\.1" docs/ README.md CHANGELOG.md
```

**In-scope files:** **0 matches.**

- `README.md`: 0
- `CHANGELOG.md`: 0
- `docs/release_notes_v0.5.0.md`: 0
- `docs/release_notes_v0.3.md`, `docs/release_notes_v0.3.1.md`: 0

**Out-of-scope hits (audit-trail / decision docs — expected and correct):**

- `docs/cross_doc_consistency_v2.md`: 6 mentions, all describing PLAN-hedge
  drift and the v0.4.1 → v0.5.0 decision trail.
- `docs/pr6_prep/semver_sequencing.md`: 13 mentions, all in the
  before/after sections of the "Ships in v0.5.0" patch (decision is locked;
  doc preserves the "before" wording for traceability).

**Verdict for §1:** CLEAN. No current-state surface still asserts v0.4.1.

## 2. v0.5.0 occurrences (count + locations)

```
$ grep -rn "v0.5.0\|0\.5\.0" docs/release_notes*.md README.md CHANGELOG.md \
    poker_solver/__init__.py pyproject.toml
```

| File | Count | Sample location |
|------|------:|-----------------|
| `README.md` | 3 | line 14: `**Current version:** 0.5.0`; line 70: `*(new in v0.5.0, PR 6)*`; line 128: `ships in v0.5.0` |
| `CHANGELOG.md` | 2 | line 16: `## [0.5.0] - 2026-05-22`; line 318: `[0.5.0]: ./` |
| `docs/release_notes_v0.5.0.md` | 3 | line 1: `# poker_solver v0.5.0 release notes`; lines 118, 124 (fixture / Rust-tier mentions) |
| `poker_solver/__init__.py` | 1 | line 158: `__version__ = "0.5.0"` |
| `pyproject.toml` | 1 | line 7: `version = "0.5.0"` |
| **Total** | **10** | |

**Verdict for §2:** All five expected surfaces carry v0.5.0. Headline
(README), CHANGELOG section header, release-notes title, `__version__`,
and `pyproject.toml` are all in lockstep.

## 3. v0.4.0 occurrences (verify all historical)

```
$ grep -rn "v0.4.0\|0\.4\.0" docs/release_notes*.md README.md CHANGELOG.md \
    poker_solver/__init__.py pyproject.toml
```

| File | Count | Line(s) | Historical? |
|------|------:|---------|:-----------:|
| `CHANGELOG.md` | 3 | 44: `## [0.4.0] - 2026-05-22`; 99: `__version__ bumped to 0.4.0`; 319: `[0.4.0]: ./` | YES — prior release section, archived |
| `README.md` | 0 | — | n/a (clean) |
| `docs/release_notes_v0.5.0.md` | 0 | — | n/a (clean) |
| `poker_solver/__init__.py` | 0 | — | n/a (clean) |
| `pyproject.toml` | 0 | — | n/a (clean) |

**Note on missing `docs/release_notes_v0.4.0.md`:** no such file exists in
`docs/`. Release-notes files present are `release_notes_v0.3.md`,
`release_notes_v0.3.1.md`, `release_notes_v0.5.0.md`. The v0.4.0 release
is covered in CHANGELOG only — a release-notes doc was skipped (PR 4 +
PR 5 were treated as a milestone bundle and noted in CHANGELOG). Not a
v0.5.0 consistency issue, but flagged for awareness.

**Verdict for §3:** All v0.4.0 mentions are confined to the CHANGELOG and
are historical (the archived [0.4.0] section + its footnote reference).
No current-state surface still claims v0.4.0.

## 4. Verdict

**CONSISTENT.**

- v0.4.1: zero in-scope mentions; out-of-scope mentions are deliberate
  audit-trail in two prep docs.
- v0.5.0: 10 mentions across 5 expected surfaces, all aligned.
- v0.4.0: 3 mentions, all in CHANGELOG history; no current-state leakage.

The v0.4 → v0.5 edit pass landed cleanly across `README.md`,
`CHANGELOG.md`, `docs/release_notes_v0.5.0.md`,
`poker_solver/__init__.py`, and `pyproject.toml`.

## 5. Patches recommended

**None required.** All current-state surfaces are aligned on v0.5.0;
v0.4.0 mentions are historical-only; v0.4.1 mentions exist only in
audit-trail and decision docs where their presence is correct.

**Optional follow-ups (not blockers, not in this scan's scope):**

- Consider whether `docs/release_notes_v0.4.0.md` should be backfilled
  for archival completeness, since v0.3 and v0.5 both have release-notes
  docs but v0.4 does not. This is a documentation-hygiene call, not a
  version-consistency issue.
- `PLAN.md` line 89 ("(or v0.4.1 if semver sequencing decision favors
  patch — TBD at PR 6 land)") was flagged in
  `docs/cross_doc_consistency_v2.md` as a remaining hedge. Outside this
  scan's grep scope (read-only scan was `docs/ README.md CHANGELOG.md`),
  but worth tightening to "v0.5.0 (locked)" in a future PLAN-sync pass.
