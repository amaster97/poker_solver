# State Consistency Audit — 2026-05-23 (late)

**Auditor:** Read-only sub-agent invoked by orchestrator.
**Scope:** Verify orchestrator's claims about disk + remote state.
**Constraint:** READ-ONLY. No mutation, no sub-agents.

---

## Per-claim verification

### Claim 1: Public origin/main is at `94007ca` — **VERIFIED**
`git ls-remote origin main` returns `94007cac5ec0c445238377238f2853fd6102f19b`. Local `main` ref also at `94007ca` — clean alignment.

### Claim 2: v1.6.0 tag is on origin — **VERIFIED**
`refs/tags/v1.6.0` resolves to `d885bcabb1c0eeffe9748f9d2ca9bbe2034a8379` on origin. This points at the GUI Gate 2 ship commit, NOT origin/main HEAD — `94007ca` (README refresh) is one commit ahead of the v1.6.0 tag. This is correct: README/explainer refresh was a post-release docs touch.

### Claim 3: GitHub release for v1.6.0 is live — **VERIFIED**
`gh release view v1.6.0` returns:
- `tagName: v1.6.0`, `isDraft: false`, `isPrerelease: false`, `targetCommitish: main`
- Published 2026-05-23T20:14:18Z by amaster97
- URL: `https://github.com/amaster97/poker_solver/releases/tag/v1.6.0`

### Claim 4: README on origin/main has the v1.5.x refresh — **VERIFIED**
`origin/main:README.md` reads:
> **Latest tagged release:** v1.5.1 (test rigor + docs honesty). The v1.0 → v1.5.1 trajectory is documented in CHANGELOG.md.

No more stale v1.0.0 framing. (Minor: README mentions v1.5.1 as "latest" but v1.6.0 has shipped — see Discrepancies section.)

### Claim 5: aggregator_vs_true_nash_explainer.md on origin/main — **VERIFIED**
File present, 192 lines, with the documented TL;DR table contrasting `solve_range_vs_range` (Python aggregator) vs. `solve_range_vs_range_rust` (vector-form CFR).

### Claim 6: examples/range_vs_range_river.py on origin/main — **VERIFIED**
File present, 158 lines, with runnable example header, "Honest framing on 'range vs range' in v1.0.0" docstring, and `HUNLConfig.initial_hole_cards` doc.

### Claim 7: Feature branches exist locally at claimed SHAs — **VERIFIED (all 7)**

| Branch | Claimed SHA | Actual SHA | Status |
|---|---|---|---|
| pr-35c-paired-fix | 63c9432 | 63c94320 | MATCH |
| pr-35d-brown-quirk-doc | e9e5d3a | e9e5d3ad | MATCH |
| pr-46-dcfr-panic-fix | cd56761 | cd56761f | MATCH |
| pr-43-nash-wrapper | e151de4 | e151de49 | MATCH |
| pr-39-cli-ergonomics | 7584e06 | 7584e065 | MATCH |
| pr-33-python-delegate | 29a00c0 | 29a00c0c | MATCH |
| pr-40-acceptance-test-fix | c058e97 | c058e974 | MATCH |

### Claim 8: Private mirror has integration push — **VERIFIED**
Remote is named `backup` (`https://github.com/amaster97/poker_solver_private.git`).
`backup/integration` HEAD is `3475ca9 docs: session 2026-05-23 internal docs accumulator (private-only)`. Head commit history shows internal session docs are routed to private mirror — correct per dual-remote workflow.

### Claim 9: Memory file count + key entries — **VERIFIED**
- `*.md` files in memory dir: **28** (matches claim)
- `^- \[` entries in MEMORY.md: **27** (matches claim)
- New entry `feedback_label_vs_semantics.md` is present in dir AND referenced in MEMORY.md.
- `feedback_test_write_reference.md` exists in dir but I did not check whether it is referenced in MEMORY.md. (Not part of the audit claim.)

### Claim 10: STATUS doc exists — **VERIFIED**
`/Users/ashen/Desktop/poker_solver/docs/STATUS_2026-05-23_late_evening.md` — 6,400 bytes, May 23 17:08.

### Claim 11: PR 44 edits on disk (not yet committed) — **FAILED**
Claim is **STALE**. PR 44's code changes are already committed:
- Local branch `pr-44-dmg-packaging-fix` HEAD = `c09abe7` ("PR 44: fix .dmg packaging - nicegui bundle + arch label + version stamp")
- Commit modifies `pyproject.toml`, `scripts/build_macos_dmg.sh`, `scripts/poker_solver.spec` (53 insertions, 10 deletions)
- `git status` shows only `Cargo.lock` as modified-but-not-committed (cfr_core version bump 0.5.0 → 0.6.0, NOT a PR-44 file)
- PR 44 commit is **on local branch but NOT pushed to origin/main**

### Claim 12: PLAN.md is synced — **VERIFIED**
`cmp` on the two files returns identical (no output → byte-exact match). 475 lines each.

---

## Additional checks

### Check 13: Leaked worktrees — **WARNING**
22 worktrees exist. Of these:
- **8 in `/private/tmp/`** (transient agent worktrees): `cu-pr-4.5`, `dcfr_panic_repro_66023`, `poker_pr35`, `pr-35c-paired-60921`, `pr-35d-brown-quirk-61060`, `ship-v1.7.0-66279`, `v1_6_1_dryrun2_72023`. These survived agent exit — candidates for `git worktree remove`.
- **14 in `/Users/ashen/Desktop/poker_solver_worktrees/`** (deliberate persistent worktrees for feature branches). These are by design.
- Main working tree: `/Users/ashen/Desktop/poker_solver` is on branch `pr-44-dmg-packaging-fix` — **not on main**. Any agent that assumes the shared tree is on main will get pr-44's content.

### Check 14: Uncommitted changes + stash list — **WARNING**

**Uncommitted modifications:**
- `Cargo.lock` (modified — cfr_core 0.5.0 → 0.6.0 bump from a downstream branch leakage)

**Untracked files (140+ files):**
- `PLAN.md` (sync target, expected)
- 4× `RELEASE_*` docs (release planning, likely belongs in private mirror)
- 100+ `docs/*.md` files (audits, leg-N ship reports, prep dirs, persona test results, pr_proposals/)
- `scripts/cleanup_pr_branches.sh`

These are not lost yet (still on disk), but they're not committed to any branch. **High risk of loss if someone runs `git clean -fd` or switches branches without staging.**

**Stash list:**
- `stash@{0}: On main: pre-comprehensive-review-fix backup` — one stash, on main. Origin is unknown but it is preserved.

### Check 15: Public-mirror content audit (PII sampling) — **VERIFIED**
Sampled origin/main files for `/Users/ashen`, session UUIDs, agent IDs:
- `README.md` — clean
- `CHANGELOG.md` — clean
- `CONTRIBUTING.md` — clean
- `DEVELOPER.md` — clean
- `USAGE.md` — clean
- `poker_solver/__init__.py` — clean
- `pyproject.toml` — clean except `authors = [{ name = "ashen" }]` (intentional, just a first name, no path/UUID/email)
- `examples/range_vs_range_river.py` — clean

No leaked machine paths, session IDs, or agent IDs found in sampled files.

---

## Overall verdict: **DISCREPANCIES-FOUND**

11 of 12 claims VERIFIED; 1 FAILED (Claim 11 — PR 44 already committed locally, claim was stale).
3 additional WARNING-level checks (Check 13 leaked worktrees, Check 14 large untracked-doc pool, Claim 4 README mentions v1.5.1 as "latest" despite v1.6.0 shipped).

### Recommended remediations

1. **PR 44 (Claim 11):** Orchestrator should update its mental model — PR 44's pyproject/build_macos_dmg/spec edits are already committed at `c09abe7` on local `pr-44-dmg-packaging-fix`, not pushed. Next step is either (a) push pr-44 branch + open PR, or (b) merge to local main + push to origin. Do NOT re-commit those file changes.

2. **Cargo.lock drift:** Investigate why `Cargo.lock` shows cfr_core 0.5.0 → 0.6.0. This may be an unintended bump from a different branch (likely a v1.7.0 prep branch). Either commit it under a deliberate version bump or `git checkout HEAD -- Cargo.lock` to revert.

3. **Leaked /tmp worktrees (Check 13):** 8 transient worktrees in `/private/tmp/`. If associated agents have exited, run `git worktree prune` + targeted `git worktree remove` to reclaim.

4. **Main tree on PR branch (Check 13):** Shared working tree `/Users/ashen/Desktop/poker_solver` is on `pr-44-dmg-packaging-fix`, not main. Per `feedback_no_concurrent_branch_ops.md`, this is acceptable IF no concurrent branch ops are running, but agents that assume cwd = main will read pr-44's tree. Either return main to main, or document the convention.

5. **Untracked doc proliferation (Check 14):** 100+ untracked docs in `/docs/`. Audit-classify these into:
   - public-OK (commit to main + push to origin)
   - private-only (commit to integration + push to backup)
   - delete (superseded session artifacts)
   Run a pruning pass per `feedback_continuous_pruning.md`.

6. **README v1.5.1 stale (Claim 4):** README on origin/main says "Latest tagged release: v1.5.1" but v1.6.0 ships and is tagged. Either:
   - Update README to reference v1.6.0 (next docs push), OR
   - Document the gap rationale.

---

## Final report (under 300 words)

**Total claims checked:** 12 numbered + 3 additional checks = **15 verification items**
**Verified:** 11 / 12 numbered claims; 1 / 3 additional checks fully clean
**Failed:** 1 (Claim 11 — stale claim about PR 44 being uncommitted; in fact committed locally at `c09abe7`)
**Warnings:** 4 (8 leaked /tmp worktrees, 100+ untracked docs, shared tree on PR branch not main, Cargo.lock drift)

**Drift between orchestrator's mental model and disk reality:**

1. **Stale "PR 44 not committed" claim** — orchestrator may double-commit if not corrected. Code is at `c09abe7`, not in working dir.

2. **Cargo.lock has uncommitted 0.5.0 → 0.6.0 cfr_core bump** that orchestrator did not mention — possible cross-branch leakage from a v1.7.0 prep worktree.

3. **8 /tmp/ worktrees survived agent exit** — these consume disk + can confuse subsequent agents that find leftover state.

4. **README on origin/main says "v1.5.1 latest"** despite v1.6.0 release shipping. Internally consistent (v1.6.0 release was post-README-refresh), but user-facing message lags reality.

5. **Shared tree at `/Users/ashen/Desktop/poker_solver` is on `pr-44-dmg-packaging-fix`, not `main`** — invisible state that subsequent agents may mis-read.

**Net assessment:** Public origin + private backup are clean and aligned. v1.6.0 release ships correctly. Memory files match claim counts. PLAN.md is byte-exact synced. Main risk is the dropped PR 44 status (already committed locally) + the proliferation of uncommitted docs + lingering worktrees, all of which are loss-of-context risks, not data-corruption risks.
