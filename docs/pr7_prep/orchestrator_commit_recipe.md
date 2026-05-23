# Orchestrator Fallback Commit Recipe (PR 7)

**Purpose:** Manual commit fallback if PR 7 V4 (and any subsequent commit-agent versions) also fails. The orchestrator runs these commands directly. **READ-ONLY DOC** — do not execute during prep phase.

**Branch:** `pr-7-noambrown-diff` -> `integration`
**Version:** v0.5.1
**Working tree:** `/Users/ashen/Desktop/poker_solver`

---

## 1. Pre-flight verification (BEFORE any agent runs)

Run these to confirm the working tree is in the expected state. Abort and re-stage if any line fails.

```bash
cd /Users/ashen/Desktop/poker_solver
git branch --show-current                          # expect: pr-7-noambrown-diff
git status --short | head -20                      # expect: M/A/?? entries, no merge markers
grep __version__ poker_solver/__init__.py          # expect: __version__ = "0.5.1"
test -f docs/pr7_prep/commit_message_draft.md && echo OK || echo MISSING
test -f references/noambrown/poker_solver/README.md && echo OK || echo MISSING
```

If any check fails: STOP. Do not run sections 2-6 until repaired.

---

## 2. Lint quick check (before manual commit)

Both must exit 0. If they fail, fix in-place; do not bypass with `--no-verify`.

```bash
cd /Users/ashen/Desktop/poker_solver
ruff check poker_solver tests --no-cache
black --check poker_solver tests
```

If ruff complains, run `ruff check --fix poker_solver tests` then re-verify.
If black complains, run `black poker_solver tests` then re-verify.
**Re-stage** after any auto-fix: `git add -A`.

---

## 3. Manual commit recipe (orchestrator-direct, no agent)

The commit message is in `docs/pr7_prep/commit_message_draft.md`. Line 1 is the title, blank line, then body. We use `tail -n +2` to keep title + body verbatim (commit_message_draft.md starts at line 1 with the title — `tail -n +2` skips a leading blank if present; verify before piping).

```bash
cd /Users/ashen/Desktop/poker_solver
git add -A
git status --short                                 # confirm staged set is sane
git commit -F docs/pr7_prep/commit_message_draft.md
git log -1 --stat                                  # eyeball summary
git push -u origin pr-7-noambrown-diff
```

**Note:** Prefer `-F` (file) over `-m "$(cat ...)"` — avoids shell-quoting hazards and trailing-newline drift. The Co-Authored-By trailer must be in `commit_message_draft.md` already; if missing, append before commit.

---

## 4. Integration merge (after PR 7 push succeeds)

```bash
cd /Users/ashen/Desktop/poker_solver
git fetch origin
git checkout integration
git pull --ff-only origin integration              # abort if non-ff
git merge --no-ff pr-7-noambrown-diff \
  -m "Integration: merge PR 7 (river-spot diff vs Brown, v0.5.1)"
git push origin integration
git checkout pr-7-noambrown-diff                   # return to feature branch
```

If `pull --ff-only` fails: integration has diverged. STOP. Investigate before merging.

---

## 5. Rollback procedure (if push fails or commit is wrong)

**Before push** (commit exists locally only):
```bash
git reset --soft HEAD~1                            # keep changes staged
# fix issue, re-stage, re-commit per Section 3
```

**After push to feature branch but before integration merge:**
```bash
git revert HEAD                                    # additive revert
# OR (only if no one else has pulled):
git reset --hard HEAD~1 && git push --force-with-lease origin pr-7-noambrown-diff
```

**After integration merge** — DO NOT force-push integration. Use revert:
```bash
git checkout integration
git revert -m 1 <merge-commit-sha>
git push origin integration
```

---

## 6. Six-branch sync verification (post-commit)

Confirms every tracked branch has local==origin. Run after Section 4 completes.

```bash
cd /Users/ashen/Desktop/poker_solver
git fetch --all --prune
for branch in main pr-3-hunl-tree pr-3.5-pushfold pr-4-card-abstraction pr-5-hunl-postflop-solve pr-6-rust-hunl-port pr-7-noambrown-diff integration; do
  local_hash=$(git rev-parse "$branch" 2>/dev/null) || { echo "MISSING $branch (local)"; continue; }
  origin_hash=$(git rev-parse "origin/$branch" 2>/dev/null) || { echo "MISSING origin/$branch"; continue; }
  if [[ "$local_hash" == "$origin_hash" ]]; then
    echo "OK $branch"
  else
    echo "DRIFT $branch (local=${local_hash:0:8}, origin=${origin_hash:0:8})"
  fi
done
```

Only `pr-7-noambrown-diff` and `integration` should have advanced. The other six must report OK.

---

## Biggest fallback risks

1. **Lint pre-commit hook auto-modifies files mid-commit** -> commit message references stale content. Mitigation: always run Section 2 manually first, re-stage, then commit.
2. **`commit_message_draft.md` leading-line drift** — `tail -n +2` assumed the file's first line was the title; using `-F` (Section 3) avoids that entirely.
3. **Integration non-ff** — another agent or human pushed to `origin/integration` while PR 7 was in flight. Section 4's `pull --ff-only` catches this; do not `merge` integration into the feature branch as a "fix".
4. **Worktree contention** — per memory rule, never branch-switch while other agents may write. Confirm no background agents are mid-write before Section 4's `checkout integration`.
