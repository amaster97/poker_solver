# Cutover Execute-Now Runbook (Steps 0-7, H deferred)

Date: 2026-05-23. READY TO FIRE once cutover script patch lands (integration->main merge inserted before split helper). User authorized D-G (here Steps 1-6); H **deferred to manual user invocation**.

## Lettering map (original D-H -> this runbook)

| Original | This runbook |
|---|---|
| (new patch) | **Step 1 — integration->main FF-merge; resolves dangling-v0.6.1 caveat** |
| D | Step 2 — split_main_for_publish.sh --execute |
| E | Step 3 — cleanup commit |
| F (origin) | Step 4 — push origin main |
| F (backup) | Step 5 — force-with-lease backup main |
| G | Step 6 — push v0.6.1 to both remotes |
| (verify) | Step 7 — post-push inspection |
| H | **DEFERRED** — surfaced to user manually |

Each step is a separate Bash invocation so the orchestrator can surface output and pause between steps.

---

## Step 0 — Pre-flight (run once before anything else)

```bash
git -C /Users/ashen/Desktop/poker_solver status --short
git -C /Users/ashen/Desktop/poker_solver branch --show-current
git -C /Users/ashen/Desktop/poker_solver ls-remote backup | head -5
git -C /Users/ashen/Desktop/poker_solver rev-parse integration
git -C /Users/ashen/Desktop/poker_solver ls-remote backup refs/heads/integration | cut -f1
```

**Expected:** clean tree except `?? V1_GA_CLOSE.md`; on branch `integration`; backup shows >=3 refs; local `integration` SHA equals `backup/integration` SHA (`9936d5f` or current HEAD).
**Failure modes:** dirty tree | wrong branch | backup/integration drift.
**Recovery:** dirty -> stop & investigate; wrong branch -> `git checkout integration`; drift -> re-run original Step C before proceeding.

---

## Step 1 — Switch to main and FF-merge integration (the patched step)

```bash
git -C /Users/ashen/Desktop/poker_solver checkout main
git -C /Users/ashen/Desktop/poker_solver merge --ff-only integration
```

**Expected:** main FF-advances to integration HEAD (`9936d5f`). v0.6.1's target `67760c7` is now reachable from main — dangling-tag caveat in `cutover_dry_run_preview.md` Section 5(1) is **resolved**.
**Failure modes:** non-FF (integration diverged) | uncommitted changes block checkout.
**Recovery:** non-FF -> abort, `git checkout integration`, investigate (should not happen if Step 0 passed); checkout blocked -> resolve dirty state, retry.

---

## Step 2 — Run the split script on main

```bash
git -C /Users/ashen/Desktop/poker_solver status --short  # confirm clean before script
cd /Users/ashen/Desktop/poker_solver && ./scripts/split_main_for_publish.sh --execute
```

**Expected:** ~107 allowlist hits; `STATUS.md` + `SESSION_END_FINAL.md` untracked; 6 patterns appended to `.gitignore` (`STATUS*.md`, `SESSION_*.md`, `V*_GA_CLOSE.md`, `V*_MILESTONE*.md`, `wake_up_*.md`, `*_HANDOFF.md`); `.gitignore` staged. `V1_GA_CLOSE.md` is no-op on main.
**Failure modes:** script aborts (allowlist mismatch) | dirty tree blocks execution.
**Recovery:** `git restore --staged . && git checkout HEAD -- .gitignore` restores post-Step-1 state; debug & retry.

---

## Step 3 — Verify staged diff and create the cleanup commit

```bash
git -C /Users/ashen/Desktop/poker_solver diff --cached --name-only
git -C /Users/ashen/Desktop/poker_solver commit -m "chore: clean main — Option C public-channel filter

- git rm --cached: STATUS.md, SESSION_END_FINAL.md (session artifacts, not part of public surface)
- .gitignore: append session-artifact globs (STATUS*.md, SESSION_*.md, V*_GA_CLOSE.md, V*_MILESTONE*.md, wake_up_*.md, *_HANDOFF.md)
- Mechanically enforces the dual-channel split for future commits

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

**Expected:** staged diff lists exactly `.gitignore`, `STATUS.md`, `SESSION_END_FINAL.md`; commit lands on local main with integration-merged parent. Main is now 1 commit ahead of `origin/main`.
**Failure modes:** wrong staged files | hook blocks commit.
**Recovery:** `git reset HEAD~1` (commit wrong) or `git restore --staged <file>` (staging wrong); retry.

---

## Step 4 — Push cleaned main to origin (the public face)

```bash
git -C /Users/ashen/Desktop/poker_solver push origin main
```

**Expected:** fast-forward; `origin/main` advances by cleanup commit on top of integration-merged history. Public repo now reflects integration content **minus** the two leaked session docs.
**Failure modes:** non-FF (concurrent push) | auth/network.
**Recovery:** non-FF -> `git fetch origin && git log origin/main..main` to inspect, do NOT force; auth -> verify credentials & retry.

---

## Step 5 — Force-push cleaned main to backup (overwrites GitHub auto-init)

```bash
git -C /Users/ashen/Desktop/poker_solver push backup main --force-with-lease
```

**Expected:** `backup/main` force-replaced from auto-init `b83835e0` to cleanup commit. Force required because backup/main is a disjoint GitHub auto-init with no shared history; no user content overwritten.
**Failure modes:** lease rejection (backup/main moved — shouldn't happen, no other writers).
**Recovery:** if rejected, `git fetch backup && git log backup/main --oneline | head -5`; decide benign (refresh lease, retry) or hostile (stop).

---

## Step 6 — Push v0.6.1 tag to both remotes

```bash
git -C /Users/ashen/Desktop/poker_solver push origin v0.6.1
git -C /Users/ashen/Desktop/poker_solver push backup v0.6.1
```

**Expected:** tag publishes to both. Because Step 1 merged integration into main, target `67760c7` is reachable from main — **no longer dangling** (contradicts dry-run preview's Section 5(1) prediction, which is now stale).
**Failure modes:** tag already exists on remote | network.
**Recovery:** identical on remote -> no-op; divergent on remote -> stop, do not force tag without user sign-off; network -> retry.

---

## Step 7 — Verification

```bash
git -C /Users/ashen/Desktop/poker_solver ls-remote origin
git -C /Users/ashen/Desktop/poker_solver ls-remote backup
git -C /Users/ashen/Desktop/poker_solver log --oneline origin/main..main
```

**Expected:** `origin` lists `refs/heads/main` (new SHA) + 9 stale `pr-*` + `pull/1/head` + tags `v0.6.0`, `v0.6.1` (new), `v1.0.0`; `backup` lists `refs/heads/main` + `refs/heads/integration` + `refs/tags/v0.6.1`; `origin/main..main` empty (in sync).
**Failure modes:** ref drift.
**Recovery:** investigate the drifted ref; do not force.

---

## DEFERRED — Step H (origin/integration deletion)

Orchestrator surfaces this command for manual user invocation:

```bash
git -C /Users/ashen/Desktop/poker_solver push origin --delete integration
```

Reversible via `git push origin <sha>:refs/heads/integration`. Do **not** run in this sequence.

---

This document is specification-only; no commands have been executed and no source/.gitignore/commits were touched while drafting it.
