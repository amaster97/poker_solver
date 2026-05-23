# Routing Check — 2026-05-23

**Verdict: HARD-RISK** — `STATUS.md` and `SESSION_END_FINAL.md` are already on `origin/main` (public GitHub). Dual-channel split has been **designed but not yet executed**.

Active branch in shared tree: `integration` @ `2479694`. PR 8 / PR 9 isolated in worktrees. PR 10a.5 already committed (`67760c7`).

---

## Section A — Findings

1. **`.gitignore` actual content.** 53 lines covering Python build/venv/cache, IDE, Rust `target/`, `references/`, `pr_report.md`, `*.docx`. **Does NOT exclude** `docs/`, `PLAN.md`, `STATUS*.md`, `SESSION_*.md`, `V*_GA_CLOSE.md`, `wake_up_*.md`, `*_HANDOFF.md`. The "docs/ + PLAN.md gitignored" claim in session docs is **false**; these are tracked on `integration` by design (Option C, commit `c8aa2a2`). The session-artifact globs are **not** gitignored anywhere.

2. **`split_main_for_publish.sh` ALLOWLIST.** Matches PUBLIC-OK set: top-level `README/USAGE/DEVELOPER/LICENSE/CHANGELOG/CONTRIBUTING.md`; build manifests (`pyproject.toml`, `Cargo.toml`, `Cargo.lock`, `pytest.ini`, `.gitignore`); source trees (`poker_solver/`, `crates/`, `tests/`, `ui/`, `examples/`, `assets/`); explicit script allowlist (10 entries including the script itself); `.github/`. **No glob support** (intentional). No path looks over-broad; no session-artifact pattern is allowlisted. Matches the audit.

3. **`split_main_for_publish.sh` EXPLICIT_UNTRACK list.** Exactly: `STATUS.md`, `SESSION_END_FINAL.md`, `V1_GA_CLOSE.md`. Matches expectation.

4. **Current tracked tree (`integration`).** 386 files. Under `docs/`: **276 files tracked**, including `docs/SESSION_END_REPORT.md`, `docs/SESSION_HANDOFF.md`, `docs/V1_GA_MILESTONE_HIT.md`, `docs/wake_up_brief*.md`, `docs/session_*.md`. Top-level `.md`: `CHANGELOG.md`, `CONTRIBUTING.md`, `PLAN.md`, `README.md`, `SESSION_END_FINAL.md`, `STATUS.md` — the last two are **session artifacts the audit named for untracking** but they're still tracked.

5. **`git status --short` on `integration`.** 6 untracked: `DEVELOPER.md`, `USAGE.md`, `V1_GA_CLOSE.md`, `docs/sync_repos_runbook.md`, `scripts/split_main_for_publish.sh`, `scripts/sync_repos.sh`. `git check-ignore` returned no matches for `PLAN.md` / `docs/SESSION_HANDOFF.md` / `docs/sync_repos_runbook.md`. PLAN.md and `docs/*` are **tracked**, not gitignored. The .gitignore is **not hiding** any docs/ content; the apparent absence in `git status` is because they're already in the index.

6. **Worktrees & isolation.**
   - `/Users/ashen/Desktop/poker_solver` — `integration` @ `2479694` (shared tree).
   - `/private/tmp/poker_pr35` — `pr-3.5-pushfold` @ `1cbf52a` (stale, low risk).
   - `/Users/ashen/Desktop/poker_solver_worktrees/pr-8-simd` — `pr-8-simd-perf` @ `62c75d5` (4 modified + 4 untracked under `crates/cfr_core/`).
   - `/Users/ashen/Desktop/poker_solver_worktrees/pr-9-preflop` — `pr-9-preflop` @ `62c75d5` (4 modified + 4 untracked spanning `crates/`, `poker_solver/`, `tests/`).
   PR 8 and PR 9 are **correctly isolated** from the shared `pr-10a.5-conformance` branch and from each other.

7. **In-flight agent write targets.** `docs/pr10a_5_prep/commit_prep.md` confirms PR 10a.5 work targets `ui/views/*.py`, `ui/state.py`, `ui/app.py`, `tests/test_ui_smoke.py` (7 files, all PUBLIC-OK). PR 8 work lands on `crates/cfr_core/*` (PUBLIC-OK). PR 9 work lands on `crates/cfr_core/`, `poker_solver/`, `tests/` (all PUBLIC-OK). Agent prep docs live under `docs/pr{8,9,10c}_prep/` which is **integration-only by design**. No agent appears to be writing top-level session artifacts (STATUS/SESSION_/V1_GA_CLOSE.md) right now.

---

## Section B — Routing risks

1. **HIGH — Public leak already on `origin/main`.** `git ls-tree -r origin/main` shows `STATUS.md` and `SESSION_END_FINAL.md` at the public GitHub URL `https://github.com/amaster97/poker_solver.git` right now. Local `main` matches `origin/main` (zero diff). The split script has **not been executed** on `main` yet. This is an existing-state leak, not an in-flight-agent risk.
2. **HIGH — `origin/integration` is on the public GitHub remote.** Both branches point at the same public URL. Local `integration` is **286 files ahead** of `origin/integration` including PLAN.md, all 276 docs/, the v0.6.2 backlog, etc. Any `git push origin integration` would publish all internal planning. The `backup` private remote referenced in `sync_repos_runbook.md` **does not exist** (no `private` or `backup` in `git remote -v`).
3. **MEDIUM — Shared-tree branch confusion.** Session docs name the active branch `pr-10a.5-conformance`, but `git branch --show-current` on the shared tree returns `integration`. PR 10a.5 commit `67760c7` already landed and integration FF-merged at `2479694`. Anyone reading older prep docs (`commit_prep.md`) might `git checkout integration` thinking they need to switch, when they're already there.
4. **MEDIUM — Untracked top-level docs in working tree.** `DEVELOPER.md`, `USAGE.md`, `V1_GA_CLOSE.md` sit at repo root. Two are on the public allowlist (DEVELOPER, USAGE) → expected. `V1_GA_CLOSE.md` is session artifact and **must stay untracked** until split is executed; current state is correct but fragile against a `git add -A`.
5. **LOW — Stale `pr-3.5-pushfold` worktree at `/private/tmp/poker_pr35`.** No agent should be writing there. Untracked from a routing perspective.
6. **LOW — `.gitignore` doesn't yet enforce session-artifact patterns.** The split script appends `STATUS*.md`, `SESSION_*.md`, `V*_GA_CLOSE.md`, `V*_MILESTONE*.md`, `wake_up_*.md`, `*_HANDOFF.md` but only at `--execute`. Until then, an agent doing `git add -A` on `main` could re-add them.

---

## Section C — Mitigations in place vs still soft

**In place:**
- Per-PR worktrees: PR 8 and PR 9 cannot collide with each other or the shared tree.
- Allowlist + EXPLICIT_UNTRACK accurately encode the audit's PUBLIC-OK / private-only sets.
- Script refuses to run if HEAD != `main`, on dirty tree, or without `--execute`; defaults to dry-run.
- Agents in flight are writing to allowlisted source paths (`ui/`, `crates/`, `poker_solver/`, `tests/`) — no current write target is itself a routing violation.
- PR 10a.5 commit message is clean (no session-artifact prose); it landed on `integration`, not `main`.

**Still soft:**
- `origin/main` already leaks STATUS.md + SESSION_END_FINAL.md. **Not fixed yet** — split script never executed.
- No `private` / `backup` remote exists. Until then there is no safe push target for `integration`.
- No pre-push hook or branch protection rule prevents `git push origin integration`. Pure discipline.
- `.gitignore` will not enforce session-artifact globs until split executes.
- Older prep docs reference the now-stale "must be on pr-10a.5-conformance" precondition; new agents reading them could waste a checkout.

---

## Section D — Recommended actions (orchestrator)

1. **Do not push anything to `origin` until the public-clean cleanup is committed and verified.** Specifically: do not `git push origin main` (it's already leaking but pushing would amplify only if local main moves) and do not `git push origin integration` under any circumstance until a `private` remote exists.
2. **Schedule a one-shot agent** to run `scripts/split_main_for_publish.sh --dry-run` on `main` in a separate worktree, capture the report, and verify the violator list matches the audit. Do not `--execute` without user OK.
3. **Configure `backup` private remote** before any push of `integration`. The runbook assumes it; the repo doesn't have it. Until then `sync_repos.sh` will `[SKIP]` the backup pushes silently and the orchestrator should treat `integration` as **local-only**.
4. **Stale-doc sweep** for `commit_prep.md` and similar — note that PR 10a.5 already landed (`67760c7`) so the "switch to pr-10a.5-conformance" step is moot. Mark prep docs as historical or add a top-of-file "STATUS: LANDED" banner.
5. **Confirm in-flight agents' commit scope.** PR 8 and PR 9 agents should commit only to their feature branches in their worktrees — not to `integration` in the shared tree. The shared tree is currently `integration` and a stray `git commit` from a confused agent would land directly on the internal accumulator. Worktrees protect against this, but the operator-facing prompts should reaffirm "do not switch back to the shared tree to commit."

---

**Files referenced (all read-only):**
- `/Users/ashen/Desktop/poker_solver/.gitignore`
- `/Users/ashen/Desktop/poker_solver/scripts/split_main_for_publish.sh`
- `/Users/ashen/Desktop/poker_solver/docs/pr10a_5_prep/commit_prep.md`
- `/Users/ashen/Desktop/poker_solver/docs/sync_repos_runbook.md`
- `git ls-files`, `git status --short`, `git worktree list`, `git ls-tree -r origin/main`, `git remote -v` (read-only)
