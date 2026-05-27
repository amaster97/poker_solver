# Post-Integration Verification Protocol

**Purpose.** After any PR merge that triggers a dual-channel sync (integration + main + origin + backup), an independent verification agent runs this protocol end-to-end and returns a single verdict: PASS or FAIL. The terminal output of `scripts/sync_repos.sh` is necessary but not sufficient evidence — a push can succeed while the resulting tree is wrong. This protocol catches routing drift before the next PR ships.

**Scope.** Runs immediately after PR integration + main publish. Read-only. Does not push, commit, or modify the repo.

---

## Phase A — Pre-sync state snapshot

Run BEFORE invoking `scripts/sync_repos.sh`. Captures known-good SHAs so post-sync diffs are meaningful.

```bash
cd /Users/ashen/Desktop/poker_solver
git rev-parse integration > /tmp/pre_sync_integration.sha
git rev-parse main > /tmp/pre_sync_main.sha
git ls-remote backup refs/heads/integration | cut -f1 > /tmp/pre_sync_backup_integration.sha
git ls-remote backup refs/heads/main | cut -f1 > /tmp/pre_sync_backup_main.sha
git ls-remote origin refs/heads/main | cut -f1 > /tmp/pre_sync_origin_main.sha
```

## Phase B — Run sync

```bash
bash scripts/sync_repos.sh
```

(Already wrapped; this protocol does not re-run sync logic — it verifies the outcome.)

## Phase C — Post-sync verification

### 1. Local + remote SHA consistency

```bash
LOCAL_INT=$(git rev-parse integration)
LOCAL_MAIN=$(git rev-parse main)
BACKUP_INT=$(git ls-remote backup refs/heads/integration | cut -f1)
BACKUP_MAIN=$(git ls-remote backup refs/heads/main | cut -f1)
ORIGIN_MAIN=$(git ls-remote origin refs/heads/main | cut -f1)

[ "$LOCAL_INT" = "$BACKUP_INT" ] || echo "FAIL: integration drift between local and backup"
[ "$LOCAL_MAIN" = "$BACKUP_MAIN" ] || echo "FAIL: main drift between local and backup"
[ "$LOCAL_MAIN" = "$ORIGIN_MAIN" ] || echo "FAIL: main drift between local and origin"
```

### 2. Routing correctness (dual-channel)

```bash
# Planning + internal docs MUST stay off main
[ -z "$(git ls-tree -r main docs/ 2>/dev/null)" ] || echo "FAIL: docs/ leaked onto main"
[ -z "$(git ls-tree main PLAN.md 2>/dev/null)" ] || echo "FAIL: PLAN.md leaked onto main"
[ -z "$(git ls-tree main STATUS.md SESSION_END_FINAL.md V1_GA_CLOSE.md 2>/dev/null)" ] \
  || echo "FAIL: session artifacts leaked onto main"

# Public-facing docs MUST be visible on main
for f in USAGE.md DEVELOPER.md README.md CHANGELOG.md; do
  [ -n "$(git ls-tree main $f 2>/dev/null)" ] || echo "FAIL: $f missing from main"
done

# scripts/ on main: only allowlisted entries
git ls-tree -r main scripts/ | awk '{print $4}' > /tmp/main_scripts.txt
# Review against scripts/ allowlist in dual-remote-workflow doc; flag any unexpected entries.
```

### 3. Tag reachability

For each tag created by this PR (e.g., `v1.0.1`, `v1.1.0`):

```bash
TAG=v1.0.1  # substitute per PR
git merge-base --is-ancestor "$TAG" main || echo "FAIL: $TAG not reachable from main"
[ -n "$(git ls-remote origin refs/tags/$TAG | cut -f1)" ] || echo "FAIL: $TAG missing on origin"
[ -n "$(git ls-remote backup refs/tags/$TAG | cut -f1)" ] || echo "FAIL: $TAG missing on backup"
```

### 4. Backup completeness

```bash
# Confirms planning history (integration) is fully mirrored
[ "$(git rev-parse integration)" = "$(git ls-remote backup refs/heads/integration | cut -f1)" ] \
  || echo "FAIL: backup/integration not in sync with local"
```

### 5. No origin/integration leak

```bash
# Integration branch was deleted from origin post-cutover; it must STAY deleted
[ -z "$(git ls-remote origin refs/heads/integration | cut -f1)" ] \
  || echo "FAIL: integration branch leaked onto origin (public repo)"
```

## Phase D — Verdict

- **ALL CHECKS PASS** -> repos appropriately updated; ship to next PR.
- **ANY FAILURE** -> stop. Surface to the user with:
  - the failing check (numbered above),
  - the offending SHA/path,
  - a recovery hint (e.g., "re-run filter on commit X" or "force-delete origin/integration").

---

## Spawn-as-agent template

After every dual-channel sync, the orchestrator spawns a fresh verification agent:

```text
Agent({
  description: "Post-integration verification for PR N",
  prompt: "Follow /Users/ashen/Desktop/poker_solver/docs/post_integration_verification_protocol.md verbatim for PR N (tag: vX.Y.Z). Run Phase A (snapshot already captured by caller — skip), then Phase C checks 1-5, then return Phase D verdict. Do not push, commit, or modify any file. Report PASS/FAIL with the specific failing check if FAIL."
})
```

Cross-reference: `feedback_dual_remote_workflow.md`, `feedback_public_repo_hygiene.md`.
