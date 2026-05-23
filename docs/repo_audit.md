# Public Repo Audit
Date: 2026-05-22

Repository: `/Users/ashen/Desktop/poker_solver`
Auditor: read-only sweep across tracked + untracked tree, all branches, and last ~35 commits on `main`.

## Executive Summary

- **Total files audited:** ~310 in-scope (109 tracked + 265 docs files + a
  handful of untracked top-level docs + 6 branches; excludes `.venv/`,
  `.git/`, `target/`, `*_cache/`, `__pycache__/`, `egg-info/`,
  `references/`).
- **PUBLIC-OK:** 109 currently-tracked files plus 3 untracked top-level
  docs that are safe to add as-is. ~112 files.
- **SANITIZE:** 2 files (one `/Users/ashen/...` absolute path in
  tracked-once `PLAN.md` mirror; one in `V1_GA_CLOSE.md`'s prose is
  clean — recheck below).
- **PRIVATE-ONLY:** the entire `docs/` tree (265 files), `PLAN.md`,
  `STATUS.md`, `SESSION_END_FINAL.md`, `V1_GA_CLOSE.md`, `references/`,
  and the office artifacts (`*.docx`, `~$*`).
- **HIGH-severity findings:** **0** in tracked-and-published surface.
  No emails, no secrets, no UUIDs, no agent IDs, no API keys anywhere
  across the whole tree (tracked or untracked).

**Bottom line:** the public-facing tracked surface (`README.md`,
`CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE`, `pyproject.toml`,
`Cargo.toml`, `crates/`, `poker_solver/`, `tests/`, `ui/`, `scripts/`,
`examples/`, `assets/`, `.github/`) is **PUBLIC-OK as-is**. The only
risk surface is what happens if `docs/` or `PLAN.md` ever get
unintentionally committed — they already aren't tracked, but the
gitignore matches them only by literal path, and any sibling file
accidentally placed at repo root (e.g. another `wake_up_*.md`) would
slip through.

---

## Section A: PUBLIC-OK files

Every file in this section is clean of PII (no email, no `/Users/ashen`
absolute path, no UUID, no secret, no personal narrative).

### Top-level (currently tracked or trivially trackable)

- `/Users/ashen/Desktop/poker_solver/README.md` — Project landing page; no
  PII; references inline only (paper / repo cites). PUBLIC-OK.
- `/Users/ashen/Desktop/poker_solver/CHANGELOG.md` — Keep-a-Changelog
  format; GitHub URLs all point at `amaster97/poker_solver` (user's
  own public GitHub handle, not personal email). PUBLIC-OK.
- `/Users/ashen/Desktop/poker_solver/CONTRIBUTING.md` — Dev environment,
  branch policy, license rules. PUBLIC-OK.
- `/Users/ashen/Desktop/poker_solver/LICENSE` — MIT, "Copyright (c) 2026
  ashen". User's chosen handle. PUBLIC-OK.
- `/Users/ashen/Desktop/poker_solver/pyproject.toml` — Author "ashen",
  no email, no path. PUBLIC-OK.
- `/Users/ashen/Desktop/poker_solver/Cargo.toml` / `Cargo.lock` /
  `crates/cfr_core/Cargo.toml` — Workspace and crate metadata, MIT,
  no PII. PUBLIC-OK.
- `/Users/ashen/Desktop/poker_solver/.gitignore` — Itself fine; gaps
  flagged in Section F below.
- `/Users/ashen/Desktop/poker_solver/USAGE.md` *(untracked)* — End-user
  guide. No PII. **Safe to track + commit as-is.**
- `/Users/ashen/Desktop/poker_solver/DEVELOPER.md` *(untracked)* —
  Contributor guide. No PII. **Safe to track + commit as-is.**

### `.github/`

- `/Users/ashen/Desktop/poker_solver/.github/PULL_REQUEST_TEMPLATE.md`
- `/Users/ashen/Desktop/poker_solver/.github/ISSUE_TEMPLATE/bug_report.md`
- `/Users/ashen/Desktop/poker_solver/.github/ISSUE_TEMPLATE/feature_request.md`

All clean of PII; only references are to repo-relative paths and
license rules. PUBLIC-OK.

### Source — Python (`poker_solver/`)

- 24 Python modules + 1 SQL schema + 1 JSON chart fixture.
- Grep confirmed zero hits on `/Users/ashen|@gsb|columbia|ashen26`.
- PUBLIC-OK.

### Source — Rust (`crates/cfr_core/`)

- 10 Rust source files (`lib.rs`, `dcfr.rs`, `solver.rs`, `game.rs`,
  `kuhn.rs`, `leduc.rs`, `hunl.rs`, `hunl_tree.rs`, `hunl_eval.rs`,
  `hunl_solver.rs`, `abstraction.rs`) plus 2 integration tests.
- No PII. PUBLIC-OK.

### Tests (`tests/`)

- 29 test files + fixtures. Grep clean for PII.
- PUBLIC-OK. (One caveat: `tests/data/river_spots.json` is a
  fixture — confirmed it's just numeric/card-string data.)

### UI (`ui/`)

- 11 Python files (NiceGUI app + views). Clean. PUBLIC-OK.

### Scripts (`scripts/`)

- 11 scripts (shell + Python + spec + plist). Clean of PII; APPLE_ID
  is shown as `you@example.com` in `assets/README.md` as an example.
  PUBLIC-OK.

### Examples + Assets

- `/Users/ashen/Desktop/poker_solver/examples/tiny_csv.csv` — solver
  config fixtures. PUBLIC-OK.
- `/Users/ashen/Desktop/poker_solver/assets/README.md` — packaging
  recipe. Uses generic placeholders (`you@example.com`, `ABCDE12345`).
  PUBLIC-OK.
- `/Users/ashen/Desktop/poker_solver/assets/poker_solver.icns` —
  single-pixel transparent placeholder icon. PUBLIC-OK.

---

## Section B: SANITIZE

Only files where targeted content needs scrubbing before publication.

### B1. `/Users/ashen/Desktop/poker_solver/PLAN.md` *(currently gitignored)*

**Severity: MEDIUM** (matters only if you ever decide to track `PLAN.md`
again; today the file is correctly excluded via `.gitignore` line 52).

**Specific scrubbings:**

- **Line 312:** `Local references live in /Users/ashen/Desktop/poker_solver/references/:`
  - Replace with: `Local references live in references/ (gitignored):`
- **Line 7:** "**Current session: autonomous overnight mode (started
  2026-05-21).** User asleep. Working through PR 5 verification → commit
  …"
  - Either remove this whole paragraph (it's session-state, not plan)
    or rewrite to "**Workflow:** local feature branches; `integration`
    accumulates merged PRs; no GitHub pushes without explicit OK."
- **Line 230:** "**Autonomous overnight mode:** `integration` branch
  ("pseudo-main") …"
  - Rewrite to just "**`integration` branch:** "pseudo-main";
    autonomously accumulates merged PR branches."

Everything else in `PLAN.md` (locked decisions, roadmap, architecture,
verification chain) is plain technical content and PUBLIC-OK after the
above scrubs.

**Recommendation:** keep `PLAN.md` gitignored. If you ever want it
public, do the 3 scrubs above first.

### B2. `/Users/ashen/Desktop/poker_solver/V1_GA_CLOSE.md` *(untracked)*

**Severity: LOW.**

Content is a session close report — no PII, no paths, no emails. But
it's narrative ("This session shipped 10 PRs", "What awaits user", etc.)
and reads as internal status. Two options:

- **Option A (preferred):** leave it untracked; treat as session
  artifact like `SESSION_END_FINAL.md` and `STATUS.md`. Add to
  `.gitignore` (see Section F).
- **Option B:** if you want it public, rewrite as a v1.0.0 release-note
  appendix in `CHANGELOG.md` or `docs/release_notes_v1.0.0.md` (which
  is gitignored anyway). Net-net: not worth surfacing.

**No specific lines to scrub** — the file itself is the issue, not its
content.

### B3. `/Users/ashen/Desktop/poker_solver/STATUS.md` and `SESSION_END_FINAL.md` *(currently tracked!)*

**Severity: LOW (PII-clean) but classification mismatch: HIGH (these are tracked but shouldn't be).**

Both files are tracked (see `git ls-files`), have no PII, but contain
session-state narrative ("v1.0.0 GA HIT", "v1.0.0 tagged at `bbb4395`",
"Sleep well", "Decisions awaiting (4)", per-PR sha tables). Same
character as the untracked `V1_GA_CLOSE.md`.

**Recommendation:** `git rm --cached STATUS.md SESSION_END_FINAL.md`
and add them to `.gitignore`. They're not useful to an external user
and the file names suggest something more interesting than they
deliver. The release-relevant facts are already in `CHANGELOG.md` and
`README.md`.

Severity is LOW because there's no PII, but ranking it HIGH because
they're already on `origin/main` (or will be once merged) where every
casual visitor sees them. Cosmetically poor for a public OSS repo.

---

## Section C: PRIVATE-ONLY (should leave the public repo)

These files are correctly excluded today via `.gitignore`. Section F
flags gaps where the rule almost catches similar files but doesn't.

### C1. The entire `docs/` tree

**Status:** correctly gitignored (`.gitignore:53 docs/`).

**Why private:** 265 markdown files spanning per-PR prep docs, agent
prompts, audit reports, kickoff docs, session retrospectives,
wake-up briefs, autonomous decision logs, recovery snapshots,
cross-PR coordination plans, INDEX files, release recipes, etc.

These are entirely internal orchestration artifacts:

- 16 `prN_prep/` subdirectories (one per PR) with `agent_*_prompt.md`,
  `audit_prompt*.md`, `launch_kickoff*.md`, `pre_commit_checklist*.md`,
  `commit_message_draft*.md` — Claude-agent input/output, not user docs.
- `autonomous_log.md`, `autonomous_decisions_2026-05-22.md`,
  `session_pause_*.md`, `session_retrospective_*.md`,
  `SESSION_HANDOFF.md`, `wake_up_brief*.md`, `morning_briefing_check.md`,
  `snapshot_in_flight.md`, `next_session_plan.md` — session/handoff
  artifacts.
- `cross_pr_coordination.md` — references absolute worktree paths
  (`/Users/ashen/Desktop/poker_solver_worktrees/pr-8-simd`,
  `/Users/ashen/Desktop/poker_solver_worktrees/pr-9-preflop`).
- `doc_inventory.md`, `doc_retention_policy.md`, `INDEX_2026-05-22.md`
  — meta-docs about the docs.
- `pr_launch_runbook.md` — runbook with ~20 `/Users/ashen/...`
  absolute paths.
- `memory_audit_2026-05-22.md` — cross-checks against
  `/Users/ashen/.claude/projects/.../memory/MEMORY.md`. **Explicit
  reference to local Claude-memory path.**
- `release_notes_v0.3.md` … `release_notes_v1.0.0.md` (7 files) —
  These could in principle be public, but they're written in
  internal-narrative voice ("PR 5 ✅ → merged at eee9b4b") not in
  user-facing release-note voice. If you want public release notes,
  rewrite the `v1.0.0` one specifically; the rest are not worth
  surfacing post-GA.

**Total `/Users/ashen/` references across docs/:** ~1260 lines (mostly
absolute paths inside prose). All would need scrubbing if any single
file were ever made public.

**Recommended action:** **leave `.gitignore` as-is.** Optionally,
*move* the entire `docs/` tree outside the repo (e.g. to
`~/poker_solver_workdir/`) so it can't accidentally be committed via
`git add -A` if someone removes the ignore. But the current gitignore
catches it cleanly.

### C2. `/Users/ashen/Desktop/poker_solver/PLAN.md`

Covered in B1. Currently gitignored (`.gitignore:52`). Leave as-is.

### C3. `/Users/ashen/Desktop/poker_solver/references/`

**Status:** correctly gitignored (`.gitignore:46`).

**Why private:** holds papers (3rd-party copyright; cannot
redistribute), OSS solver clones (`postflop-solver` AGPL,
`TexasSolver` AGPL, `shark-2.0` unlicensed, `noambrown_poker_solver`
MIT, `slumbot2019` MIT, `open_spiel` Apache 2.0), competitor blog
snapshots, and product analysis.

**Recommended action:** **leave gitignored.** README + DEVELOPER
already explain `scripts/setup_references.sh` for fresh clones.

### C4. Office artifacts

- `/Users/ashen/Desktop/poker_solver/claude_outputs_reference.docx`
- `/Users/ashen/Desktop/poker_solver/~$aude_outputs_reference.docx`
- `/Users/ashen/Desktop/poker_solver/.DS_Store`

**Status:** `*.docx` and `~$*` are gitignored (`.gitignore:56-57`);
`.DS_Store` is also gitignored (`.gitignore:38`). All correctly
private.

### C5. Build artifacts

- `poker_solver.egg-info/`, `target/`, `.venv/`, `.pytest_cache/`,
  `.mypy_cache/`, `.ruff_cache/` — all gitignored, none tracked.

---

## Section D: Git history concerns

### D1. Email leaks in commits

```
$ git log --format='%ae' --all | sort -u
amaster1997@gmail.com
```

**Single email across all commits**, **all branches**: `amaster1997@gmail.com`.
This is the user's public GitHub-associated email (different from the
school email `ashen26@gsb.columbia.edu`). It is shown on every public
GitHub commit anyway, so its presence in this repo's history is
**consistent with normal GitHub usage** and not a privacy leak.

**Severity: LOW.** No remediation needed.

### D2. Personal info in commit messages

Searched `git log --all --format='%s'` for `ashen|claude|@gsb|columbia|gmail|sk-|api.key`: **zero hits**.

The closest thing to "personal narrative" in commit messages is
`Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`,
which is just attribution and the standard pattern.

**Severity: NONE.**

### D3. Files removed from working tree but still in history

Two files were `git rm --cached`'d on commit `3425da8` ("Slim down public
repo: untrack PLAN.md and docs/"):

- **`PLAN.md`** (old 820-line version) — grep'd: zero PII (no email, no
  `/Users/ashen` path).
- **`docs/rust_orientation.md`** (154 lines) — grep'd: zero PII. Contains
  one second-person reference ("you'll find ownership is the only
  conceptually new thing vs Python") but no identifiable info.

**Both historical files are PII-clean.** No `git filter-repo` or BFG
remediation needed.

**Severity: LOW.**

### D4. Tags

`v0.6.0` and `v1.0.0` exist on `integration` (per `PLAN.md` and
`STATUS.md`), not yet on `main`. Tags carry no content beyond commit
references — no remediation needed.

---

## Section E: Branch-specific findings

Worktree state (per `git worktree list`):
- `/Users/ashen/Desktop/poker_solver` — `pr-10a.5-conformance` (currently checked out)
- `/private/tmp/poker_pr35` — `pr-3.5-pushfold`
- `/Users/ashen/Desktop/poker_solver_worktrees/pr-8-simd` — `pr-8-simd-perf`
- `/Users/ashen/Desktop/poker_solver_worktrees/pr-9-preflop` — `pr-9-preflop`

Per-branch diff vs `main` (file count) and PII grep on **added** lines:

| Branch | Files diff vs main | PII hits in added lines |
|---|---|---|
| `pr-10a.5-conformance` | 0 | 0 |
| `pr-11-library-and-packaging` | 0 | 0 |
| `pr-10a-ui-mock-first` | 23 | 0 |
| `pr-3-hunl-tree` | 83 | 0 |
| `pr-3.5-pushfold` | 75 | 0 |
| `pr-4-card-abstraction` | 75 | 0 |
| `pr-4.5-audit-debt-sweep` | 35 | 0 |
| `pr-5-hunl-postflop-solve` | 63 | 0 |
| `pr-6-rust-hunl-port` | 49 | 0 |
| `pr-7-noambrown-diff` | 42 | 0 |
| `pr-8-simd-perf` | 0 | 0 |
| `pr-9-preflop` | 0 | 0 |

All branches are PII-clean. The older `pr-3` … `pr-7` branches still
show diff vs main because they predate the integration merges that
brought their content to main; but the *content itself* (added lines)
contains zero `/Users/ashen|ashen26|@gsb|columbia` matches.

**No branch-specific remediation needed.** When you next clean up
branches post-GA (per `STATUS.md` decision #4 for `origin/equity-precision`),
the local branches `pr-3` … `pr-7` can be deleted at user discretion.

---

## Section F: `.gitignore` gaps

Current `.gitignore` correctly excludes:

- Python build artifacts (`__pycache__/`, `*.egg-info/`, `dist/`, etc.)
- Virtualenvs (`.venv/`, `venv/`, `env/`)
- Test/lint caches (`.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`)
- IDE/OS (`.idea/`, `.vscode/`, `.DS_Store`)
- Rust `target/`
- `references/` (entire tree)
- `pr_report.md` (regenerated each run)
- `PLAN.md` (line 52)
- `docs/` (line 53)
- Office artifacts (`*.docx`, `~$*`)

**Gaps (files currently tracked but should not be):**

1. **`STATUS.md`** — session state; tracked at repo root. Should be in
   `.gitignore` and `git rm --cached`'d.
2. **`SESSION_END_FINAL.md`** — session close report; tracked at repo
   root. Same disposition.

**Gaps (untracked files that should be explicitly ignored):**

3. **`V1_GA_CLOSE.md`** — untracked. Add to `.gitignore` so a future
   `git add -A` doesn't sweep it in.
4. **General pattern:** any future `SESSION_END_*.md`, `wake_up_*.md`,
   `STATUS*.md`, `*_HANDOFF.md`, `V*_CLOSE.md` at repo root will slip
   through. Recommend adding the patterns:

   ```
   # Session artifacts (local-only)
   STATUS*.md
   SESSION_*.md
   V*_GA_CLOSE.md
   V*_MILESTONE*.md
   wake_up_*.md
   *_HANDOFF.md
   ```

**Gap (untracked docs at root that ARE PUBLIC-OK):**

5. **`USAGE.md`** and **`DEVELOPER.md`** are untracked but should be
   tracked. The README already links to them. **Add to git, don't
   ignore.**

---

## Recommended actions, prioritized

### HIGH (do before pushing main public)

1. **`git rm --cached STATUS.md SESSION_END_FINAL.md`** and add both
   to `.gitignore`. These are session-state artifacts living in the
   public tracked tree; they have no PII but they signal "this repo
   has internal docs leaking" to any visitor.
2. **`git add USAGE.md DEVELOPER.md`** (currently untracked). These
   are public-facing companion docs referenced from README;
   leaving them untracked breaks every README link to them on the
   public site.
3. **Extend `.gitignore`** with the session-artifact patterns above
   (item F4) so future `wake_up_*.md` / `SESSION_*.md` / `V*_CLOSE.md`
   can't slip in.

### MEDIUM (do if you ever publicize `PLAN.md`)

4. **`PLAN.md`** — scrub the three lines noted in §B1 (lines 7, 230,
   312). Until then, keep gitignored.
5. **Audit-debt check on `docs/`**: when archive-or-delete'ing
   internal docs per the continuous-pruning rule, the only items
   *anyone* outside the project should see are:
   - `docs/release_notes_v1.0.0.md` (rewrite in user-voice)
   - `docs/architecture.md` (already linked from DEVELOPER §10)
   - Nothing else.

### LOW (cosmetic / nice-to-have)

6. **`V1_GA_CLOSE.md`** — either delete or add to `.gitignore`
   explicitly (covered by item 3 if you add the `V*_GA_CLOSE.md`
   pattern). It's session state with no public value.
7. **`assets/README.md` `APPLE_ID="you@example.com"`** — already a
   placeholder, but could be made even more obviously fake
   (`developer@your-domain.example`) to avoid confusion. Optional.
8. **`LICENSE` `Copyright (c) 2026 ashen`** — user's deliberate
   handle; no change needed unless you prefer a real name on the MIT
   notice.
9. **`pyproject.toml` `authors = [{ name = "ashen" }]`** — same as #8.

### Not needed

- No `git filter-repo` / BFG remediation needed. History is PII-clean.
- No branch deletions strictly required for privacy; do at user
  discretion for hygiene.
- `references/` is correctly gitignored; no action.
- All branches are PII-clean across added lines; no action.

---

## Method notes

Scans performed (all read-only):

- `grep -rnE 'ashen26@|@gsb\.|@columbia\.|/Users/ashen'` across tracked
  source dirs, top-level docs, untracked top-level docs, and `docs/`.
- `grep -rEn '[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'`
  (UUIDs) — zero hits.
- `grep -rEn 'agent_[0-9a-f]{10,}|[0-9a-f]{15,}|a26c058a8d6533435'`
  (agent IDs) — zero hits.
- `grep -rnE 'sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_'`
  (secrets) — zero hits.
- `git log --format='%ae' --all | sort -u` — single email
  (`amaster1997@gmail.com`, GitHub-public).
- `git log --all --format='%s' | grep -iE 'ashen|claude|@gsb|...'` — zero
  problematic commit messages.
- `git diff main..<branch>` for all 12 branches; added lines grep'd for
  PII; zero hits.
- Historical `git show 3425da8^:PLAN.md` + `git show 3425da8^:docs/rust_orientation.md`
  — both clean.

Total runtime: ~15 minutes.
