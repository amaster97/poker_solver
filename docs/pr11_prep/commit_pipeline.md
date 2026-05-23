# PR 11 commit pipeline — v1.0.0 GA

**Date drafted:** 2026-05-22
**Branch:** `pr-11-library-and-packaging`
**Status:** PRE-STAGED RECIPE. Do **not** auto-run.

This is the **v1.0.0 GA milestone** PR — the merge tip becomes the
`v1.0.0` tag. Companion docs:

- `docs/pr11_prep/pre_commit_checklist.md` (G1-G29 gate list)
- `docs/pr11_prep/commit_message_draft.md` (commit body; HEREDOC)
- `docs/pr11_prep/audit_report.md` (verdict gates the pipeline)
- `docs/pr10_prep/commit_blocked_10a.md` (lint-stop precedent)
- `docs/v0.5.0_release_recipe.md` (tag-recipe template)

---

## 1. Pre-flight gate

- [ ] Agent A formally **done** (library module + SQLite + CLI).
- [ ] Agent B formally **done** (macOS packaging + signing).
- [ ] Agent C **close enough** — test files landed:
      `tests/test_library.py`, `tests/test_library_cli.py`,
      `tests/test_library_ui_integration.py`.
      `test_packaging*` is **optional** for this firing (packaging
      tests run live on Apple hardware; in-bundle smoke step in
      `build_macos_dmg.sh` is the load-bearing gate).
- [ ] PR 11 audit verdict **READY** or **READY-WITH-PATCHES** in
      `docs/pr11_prep/audit_report.md`. **NOT-READY** → ABORT.
- [ ] PR 10a.5 backlog is **NOT in scope**. Any 10a.5 patches stay
      on their own branch.
- [ ] Working tree on `pr-11-library-and-packaging` with ~20+ files
      modified/new (snapshot at draft: 5 modified + 13 untracked = 18).
- [ ] `git fetch --all` clean; integration baseline (PR 10a tip
      `b880032`) unchanged.
- [ ] No concurrent agents writing (per memory's no-concurrent-
      branch-ops rule).

---

## 2. v1.0.0 MAJOR bump

Per PLAN.md §1: "v1 ships PR 11 with the library + DMG." MAJOR
because (a) PR 11 closes every v1 deliverable; (b) public API is
now stable under semver; (c) on-disk `library.db` schema_version=1
is committed to.

Apply these edits to the working tree **before** the lint gate:

1. **`poker_solver/__init__.py:176`** —
   `__version__ = "0.6.0"` → `"1.0.0"`.
   (Note: `commit_message_draft.md` references "0.7.1 → 1.0.0";
   that path never landed. See §3 for the message fix-up.)

2. **`pyproject.toml:7`** — `version = "0.6.0"` → `"1.0.0"`. Confirm
   Agent B's `[project.optional-dependencies] distribution =
   ["pyinstaller>=6.0"]` is present.

3. **`CHANGELOG.md`** —
   - Insert `## [1.0.0] - 2026-05-22` above `## [0.6.0]` (line 15).
   - Body: Library mode (module, schema, CLI subcommands,
     batch_solve), macOS packaging (build script, sign+notarize,
     entitlements, PyInstaller spec), UI integration
     (library_browser real loader, "Save to library" button), v1 GA
     summary listing every PR shipped (3, 3.5, 4, 5, 6, 7, 8, 9,
     10a, 11) with "v0.x experimental disclaimer lifted; semver
     applies from 1.0.0 onward; schema_version=1 committed."
   - Add `[1.0.0]` link ref; bump `[Unreleased]` compare URL to
     `v1.0.0...HEAD`.
   - `### In progress` → post-v1 follow-ups (PR 11.5 universal2;
     v1.5/v2 per PLAN.md §1).

4. **`README.md`** —
   - Line 12: `**v0.5.0 released**` → `**v1.0.0 released 2026-05-22
     (v1 GA)**`.
   - Line 17: `Current version: 0.5.1` → `1.0.0`.
   - Remove v0.x experimental disclaimer wherever it appears.
   - Add v1 GA badge near top.
   - New "Installation" section: DMG drag-to-Applications +
     unsigned-fallback right-click → Open.
   - Reduce "Roadmap" to v1.5/v2 follow-ups.

Edits land as `M` modifications in the v1.0.0 commit — not a
separate version-bump commit.

---

## 3. Commit message draft fix-up

`commit_message_draft.md` lines 26-27 + 35 reference `"0.7.1" ->
"1.0.0"`. **Fix before commit:** edit those 3 lines to `"0.6.0" ->
"1.0.0"`. Sanity-check after: `grep -c "0\.7\.1"
docs/pr11_prep/commit_message_draft.md` → 0. Safe to apply
autonomously; substantive content (scope, decisions, file list,
verification) is unaffected and audit-verified.

---

## 4. Lint gate (NO pytest)

Per recent lessons (PR 10a.5 / 10b): pytest in the pre-merge lane is
slow on Apple Silicon and does not catch the dominant failure modes
(lint drift, version drift, packaging-flag typos). Lint is the
load-bearing gate.

Run **in sequence, fail-fast:**

```bash
ruff check poker_solver tests ui scripts --no-cache
black --check poker_solver tests ui scripts
mypy --strict poker_solver/library.py
```

Pass criteria:
- `ruff check` → `All checks passed!` exit 0 (PR 11 adds `scripts/`
  surface — include in the call).
- `black --check` → `N files would be left unchanged.` exit 0.
- `mypy --strict poker_solver/library.py` → 0 errors.

**If any stage fails:**
- **STOP.** Do NOT auto-`black`-fix or auto-`ruff`-fix inline.
- Write `docs/pr11_prep/commit_blocked.md` describing what failed,
  file, and diff (pattern: `docs/pr10_prep/commit_blocked_10a.md`).
- Spawn a one-shot patch agent: runs `black <file>` / `ruff --fix`
  against the specific file, re-verifies, returns. Orchestrator
  resumes §4 from the top.
- Do NOT proceed to §5 with dirty lint.

Note: broader `mypy poker_solver` is **informational only** per
checklist G4 — PR 1-9 may carry pre-existing noise.

---

## 5. Commit + push + integration merge

Run **in sequence:**

```bash
# 5.1 Stage
git add -A

# 5.2 Verify scope
git status --porcelain | wc -l           # expect ~18-22
git diff --cached --stat                  # final sanity; confirm v1.0.0 bumps

# 5.3 Commit (per memory git-safety: -F, not -m)
git commit -F docs/pr11_prep/commit_message_draft.md

# 5.4 Verify
git status                                # clean tree
git log --oneline -3                      # v1.0.0 commit at HEAD

# 5.5 Push feature branch
git push -u origin pr-11-library-and-packaging

# 5.6 Merge to integration (becomes v1.0.0 release tip)
git checkout integration
git pull origin integration               # confirm at b880032 still
git merge --no-ff pr-11-library-and-packaging \
  -m "Integration: merge PR 11 (library + macOS .dmg, v1.0.0 GA)"
git push origin integration

# 5.7 Return to feature branch
git checkout pr-11-library-and-packaging
```

Pass criteria after §5.7:
- `git log --oneline integration` HEAD = integration merge commit
  with the v1.0.0 PR 11 commit as second parent.
- `git status` clean on `pr-11-library-and-packaging`.
- `origin/integration` and `origin/pr-11-library-and-packaging`
  both updated (`git ls-remote origin | grep -E 'integration|pr-11'`).

---

## 6. Tag v1.0.0 — AUTO-TAG

**Orchestrator's call: AUTO-TAG.** Rationale:
- v0.6.0 was auto-tagged on integration without explicit user OK
  (tag exists on origin), establishing the convention.
- The v0.5.0 recipe (`docs/v0.5.0_release_recipe.md`) said "wait
  for main merge"; v0.6.0 superseded by auto-tagging on integration.
- Consistency wins. v1.0.0 follows the v0.6.0 pattern.
- Purely additive ref push; trivially reversible (`git tag -d
  v1.0.0 && git push origin :refs/tags/v1.0.0`).

```bash
# 6.1 Capture integration merge SHA from §5.6
INTEGRATION_MERGE_SHA=$(git rev-parse integration)

# 6.2 Create annotated tag at integration merge
git tag -a v1.0.0 "$INTEGRATION_MERGE_SHA" -m \
  "v1.0.0: HUNL postflop solver + UI + library + macOS packaging (v1 GA)"

# 6.3 Verify
git tag -l "v*"                           # expect: v0.6.0, v1.0.0
git show v1.0.0 --stat | head -20

# 6.4 Push
git push origin v1.0.0
```

GitHub release **NOT** created from this pipeline — depends on the
DMG end-to-end build (separate firing, requires Apple credentials).

---

## 7. 11-branch sync verification

```bash
# 7.1 Branch + tag state
git branch                                # expect 11 local branches
git branch -r                             # matching remotes
git tag -l "v*"                           # expect: v0.6.0, v1.0.0

# 7.2 Branch HEAD SHAs (one-line check)
for b in main integration pr-3-hunl-tree pr-3.5-pushfold \
         pr-4-card-abstraction pr-4.5-audit-debt-sweep \
         pr-5-hunl-postflop-solve pr-6-rust-hunl-port \
         pr-7-noambrown-diff pr-10a-ui-mock-first \
         pr-11-library-and-packaging; do
    echo "$b: $(git rev-parse "$b")"
done

# 7.3 Confirm main unchanged
git log -1 --oneline main                 # unchanged from pre-firing

# 7.4 Remote sync
git fetch --all
git status -uno                           # clean across branches
```

Pass criteria:
- 11 local branches present, all tracked on origin.
- `integration` HEAD = v1.0.0 merge commit.
- `pr-11-library-and-packaging` HEAD = v1.0.0 commit (one before
  integration's merge commit).
- `main` HEAD **unchanged** (user OK required for main merge).
- `v0.6.0` and `v1.0.0` both on origin.

Document final state in `docs/snapshot_in_flight.md` as v1.0.0 GA.

---

## HARD GUARDRAILS

- **NO pytest of any kind.** Lint is the load-bearing gate.
- **NO main merge.** Requires explicit user OK.
- **NO force-push.** Every push is additive.
- **NO `--no-verify` / `--no-gpg-sign`.** Hooks must run.
- **NO branch switching while other agents may write** (memory's
  `feedback_no_concurrent_branch_ops`). §5.6 gated on §1's
  "no concurrent agents writing."
- **NO PR 10a.5 mixing.** Stays on its own branch.
- **If lint fails, STOP.** `commit_blocked.md` + patch agent +
  resume §4. Do NOT push a partially-clean tree.
- **If audit verdict is NOT-READY, STOP.** Escalate to user.

---

## Biggest expected issue

**`black --check` failure on Agent C's test files** — high
probability, trivial fix. Pattern: Agent C lands ~600-900 LOC of
tests without running `black` first, exactly the failure mode that
blocked PR 10a (`commit_blocked_10a.md`: f-string collapse in
`tests/test_ui_smoke.py`). Remediation pattern established:
one-shot patch agent runs `black <file>`, re-verifies, resumes.
Cost: ~2 minutes wall.

Secondary risk: CHANGELOG / README v1.0.0 content drift — v1 GA
summary must list every PR (3, 3.5, 4, 5, 6, 7, 8, 9, 10a, 11) per
`commit_message_draft.md:31-32`. Mitigation: cross-reference
`docs/per_pr_doc_inventory.md` while drafting the section.

Tertiary risk: commit-message version drift (§3) — "0.7.1" appears
3 times in a ~300-line draft, easy to miss. Mitigation:
post-fix-up `grep -c "0\.7\.1"` → 0.

---

## Non-actions in this firing

- Do NOT build the DMG end-to-end (separate firing; Apple creds).
- Do NOT create the GitHub release.
- Do NOT update PLAN.md §1 — post-firing sync agent.
- Do NOT prune `pr-10a-ui-mock-first` or any prior PR branch.
- Do NOT delete any existing tag.
- Do NOT touch `references/`.
