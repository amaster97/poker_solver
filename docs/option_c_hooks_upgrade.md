# Option C: Git Hooks for Fully Automatic Dual-Remote Sync

Upgrade path from **Option B** (manual `scripts/sync_repos.sh`) to **Option C** (git hooks). Option B is already in place; this is a forward-looking sketch in case the manual step starts costing more than the hook complexity would.

## 1. When You'd Want This (vs Sticking with Option B)

Stick with Option B while routine sync feels cheap — running `sync_repos.sh` once per session is low cognitive load and surfaces errors loudly. Move to Option C when you catch yourself either (a) forgetting to push for multi-day stretches, (b) pushing internal artifacts to the public remote because the split step got skipped, or (c) onboarding collaborators who shouldn't need to learn the dual-remote dance.

## 2. What It Would Look Like

Three hooks plus an installer:

- **`.git/hooks/post-commit`** — After every commit. On `integration`: silently `git push backup integration`. On `main`: warn ("direct commit to main; `sync_repos.sh` recommended") but do not auto-push.
- **`.git/hooks/post-merge`** — After a merge into `main`. Auto-runs the split helper if the tree isn't clean; then auto-pushes to `origin` and `backup`.
- **`.git/hooks/pre-commit`** — On `main` only, rejects commits touching `docs/`, `PLAN.md`, or session-artifact patterns.
- **`scripts/git_hooks/`** — Versioned templates for the three hooks above.
- **`scripts/install_hooks.sh`** — Copies templates into `.git/hooks/` on a fresh clone, sets `+x`.

## 3. Pros / Cons

**Pros**
- Zero commands for routine sync — just commit on integration; backup updates automatically.
- Mechanical enforcement of "no direct commits to main."
- Removes the "did I remember to push?" cognitive load.

**Cons**
- Silent failures (network down, expired creds) won't surface unless you check.
- Harder to debug when a hook misbehaves — failures look like phantom git weirdness.
- Hooks aren't versioned in git natively; each clone needs `install_hooks.sh`.
- macOS keychain credential prompts can block hooks, especially on first-time auth after token rotation.

**Mitigations**
- Track templates in `scripts/git_hooks/` (versioned, reviewable).
- `install_hooks.sh` for fresh-clone setup.
- Hook failures log to `~/.cache/poker_solver_hooks.log`; user can `tail -f` when something feels off.

## 4. Implementation Plan (if user OKs)

1. Create `scripts/git_hooks/{post-commit,post-merge,pre-commit}`; each hook tees stderr to the log file.
2. Write `scripts/install_hooks.sh` to copy templates, `chmod +x`, and print verification output.
3. Add a dry-run mode (`POKER_HOOKS_DRY_RUN=1`) so first install can be validated without side effects.
4. Install locally; commit a no-op on integration to verify silent push; commit a forbidden path on main to verify rejection.
5. Document the workflow next to Option B — including how to disable hooks temporarily (`git commit --no-verify`).
6. Monitor for one week; revert to Option B if false-positives or silent-push failures exceed one per week.

## 5. Trigger for Revisiting

Adopt Option C if **you forget to push to backup more than once per week for two consecutive weeks**, or if a session artifact gets pushed to `origin/main` despite the manual workflow. Until then, Option B's loud failures are a feature, not a bug.
