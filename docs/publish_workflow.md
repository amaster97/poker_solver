# Publish Workflow — Dual-Channel Branch Model

**Owner:** orchestrator (publishing discipline)
**Source rule:** `feedback_public_repo_hygiene.md` (auto-memory)

---

## 1. Two channels, two purposes

- **`main`** — public-facing clean channel. User-facing docs, source, build/test infra, contributor guides, license, changelog. What a stranger should see on GitHub.
- **`integration`** — internal reference ("pseudo-main"). Full planning context: PR prep, audit reports, agent prompts, autonomous logs, cross-PR coordination, session artifacts. Team continuity, **not** public consumption.

Every PR lands on `integration` with full context. Only the PUBLIC-OK subset crosses to `main`. Truly-sensitive content (secrets, personal info, session UUIDs in tracked file content) is `.gitignore`d outright and never enters either branch.

---

## 2. What lives where (allowlist)

**PUBLIC-OK (both branches):**
- `README.md`, `USAGE.md`, `DEVELOPER.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `LICENSE`
- `poker_solver/`, `crates/`, `tests/`, `ui/`, `scripts/`
- `pyproject.toml`, `Cargo.toml`, `Cargo.lock`, `.gitignore`

**INTEGRATION-ONLY (private reference):**
- All `docs/pr*_prep/` (kickoff prompts, audit reports, agent prompts)
- `docs/autonomous_log.md`, `docs/autonomous_decisions_*.md`
- `docs/audit_followup_backlog.md`, `docs/cross_pr_coordination.md`
- `docs/publish_workflow.md` (this doc — meta)
- `docs/repo_audit.md`, `docs/INDEX_*.md`
- `V1_GA_CLOSE.md`, `STATUS.md`, `SESSION_END_*.md`, `wake_up_*.md`
- **`PLAN.md`** — mixes public-OK strategic decisions with internal planning detail (commit hashes, agent IDs, session narrative). Recommend integration-only for now; revisit only if we deliberately ship a slimmed summary.

**`.gitignore`d entirely (TRULY-SENSITIVE):** session UUIDs, agent IDs, personal narrative, emails, API keys. Future: a `.git-publish-ignore` analogue if the integration-only inventory grows.

Note: `.gitignore` lines 52-53 exclude `PLAN.md` and `docs/` repo-wide — they are **not tracked on either branch** today (main and integration are identical at `62c75d5`, 109 tracked files). The planned shift to tracked-on-`integration` + filtered-from-`main` is the **Option C** transition (see §7 and `planning_preservation_decision.md`).

---

## 3. Publish flow (integration → main)

1. PR lands on `integration` with full context (current workflow, unchanged).
2. Audit the `main..integration` diff for PUBLIC-OK eligibility.
3. Carry the PUBLIC-OK subset to `main` (see §4 strategies).
4. Push `main` to origin (per §5).
5. Tag releases on `main`, not `integration`, so public clones see them.

---

## 4. Three strategies

**Option A — Manual cherry-pick.** Good for small deltas.
```sh
git checkout main
git log --oneline main..integration
git cherry-pick <hash1> <hash2> ...
```
Risk: mixed-content commits (source + integration-only docs) carry docs over by accident.

**Option B — Path-filtered checkout.** Recommended for the **first** publish-to-main pass; declares a clean baseline.
```sh
git checkout main
git checkout integration -- poker_solver/ crates/ tests/ ui/ scripts/ \
  README.md USAGE.md DEVELOPER.md CONTRIBUTING.md CHANGELOG.md LICENSE \
  pyproject.toml Cargo.toml Cargo.lock .gitignore
git commit -m "Sync public artifacts from integration"
```
Loses commit granularity but enforces the allowlist explicitly.

**Option C — Publish script.** `scripts/publish_to_main.sh` that diffs `main..integration`, refuses to publish if any non-allowlisted path is in the delta, then applies the filtered diff. Not yet built; recommended once cadence justifies it (post PR 8/9/10b).

**Default for v1.0.0 GA → first public main pass: Option B.** Transition to A or C for incremental updates.

---

## 5. Visibility scenarios

### 5a. If `origin` is PUBLIC

- `git push origin main` — regular cadence.
- **Never `git push origin integration`.** Integration stays local-only. For multi-machine sync use a private remote (separate private GitHub repo, self-hosted git, etc.).
- Pulling: `git fetch origin main`; merge selectively into `integration` for external PRs.

### 5b. If `origin` is PRIVATE

- Both branches live on `origin`. `git push origin main` and `git push origin integration` are both fine.
- Content distinction still holds: `main` slim, `integration` full.
- **Transition risk:** if the repo flips private → public, `integration` MUST be filtered/scrubbed first. Treat the flip as a one-way door — don't assume history rewrites go smoothly with collaborators.

---

## 6. Edge cases

- **Tags.** `v1.0.0` (PR 11) is reachable from both branches via today's FF merge. Future tags land on `main` so public clones see them. Internal experiment tags can stay on `integration`.
- **CHANGELOG.md.** Public-OK; write entries to be user-readable. No session UUIDs, no agent IDs, no "user said X" narrative. Reference commit hashes + PR numbers only.
- **PLAN.md sanitization.** If we ever ship a slim PLAN.md on `main`: strip internal commit hashes, session/agent IDs, and personal narrative; keep the locked decisions table + roadmap.
- **Stray tracked files on `main`.** Privacy debt on origin/main is small: only `STATUS.md` and `SESSION_END_FINAL.md` are tracked outside the allowlist. `docs/` and `PLAN.md` have always been `.gitignore`d, so they were never on either branch — today's FF merge dragged nothing internal across because integration was identical to main. Sanitization is two `git rm --cached` calls plus the `.gitignore` patch already handled by `scripts/split_main_for_publish.sh`.

---

## 7. Planned Option C transition

The model above assumes `docs/` and `PLAN.md` are tracked on `integration`. They are not today (both `.gitignore`d). `docs/planning_preservation_decision.md` recommends **Option C**: un-gitignore on `integration`, push to a private backup remote, and rely on `scripts/split_main_for_publish.sh` to strip those paths before any `integration → main` merge destined for public `origin`. When Option C lands, §2 INTEGRATION-ONLY entries become actually tracked, §3 step 2 (audit `main..integration`) becomes load-bearing, and the split script becomes the mechanical guard against `docs/` leakage. Until then, the only sanitization needed is the two stray files in §6.

## 8. Open questions

1. **Is `origin` public or private?** Determines §5a vs §5b.
2. **PLAN.md disposition under Option C:** integration-only or slim public version on `main` too?
3. **Option C cutover timing:** before or after the four in-flight post-GA PRs?
4. **Automation:** stay manual (§4 A/B) or build `publish_to_main.sh` (§4 Option C — distinct from §7's Option C)?

---

## 9. Cross-references

- Rule: `feedback_public_repo_hygiene.md` (auto-memory)
- Planning preservation decision: `docs/planning_preservation_decision.md` (Option C)
- Cross-PR file matrix: `docs/cross_pr_coordination.md`
- Audit cadence: `PLAN.md` §4 (audit reports go to integration only)
- `.gitignore` current state: lines 41-58 (52-53 = `PLAN.md` + `docs/`)
