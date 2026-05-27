# State Verification — v1.4.0 Burst (2026-05-23 late)

Fresh-eyes audit. Read-only investigation per orchestrator request.

---

## TL;DR

**Verdict: RED** — 5 public tags (v1.0.1, v1.1.0, v1.2.0, v1.3.0, v1.4.0) on `origin` point to private/integration commits containing ~70k lines of internal planning files (PLAN.md, docs/pr13_prep/*, SESSION_END, autonomous_burst_release_plan, etc.) — clear public-repo-hygiene violation.

Secondary issues: `gh release` records missing for 4 of 11 tags (v0.6.0, v0.6.1, v1.2.1 entirely absent; v1.4.0 release body looks clean but underlying tag commit isn't); local working tree dirty with stashes and untracked docs/scripts; many stale worktree feature branches.

`origin/main` HEAD itself = `166d2b8` as expected and is clean public content.

---

## Section 1 — Origin Truth Check

### 1.1 `origin/main` HEAD: PASS

- Expected: `166d2b8`
- Actual: `166d2b89c74865a0ab82ee8bdbb7ebe6d31a804b`
- Match: **YES**

### 1.2 Tag presence: FLAG (extra tag)

Expected 10 tags. Found 11 — extra is `v0.6.0` (predates the expected ladder; likely pre-burst legacy tag, low-risk).

```
v0.6.0  <-- EXTRA, not in expected list
v0.6.1  v1.0.0  v1.0.1  v1.1.0  v1.2.0  v1.2.1  v1.3.0  v1.3.1  v1.3.2  v1.4.0
```

All 11 also exist on `origin` (verified via `git ls-remote --tags origin`).

### 1.3 Tag-to-main ancestry: **FAIL (critical)**

Annotated-tag-deref-to-commit (`<tag>^{commit}`) ancestry vs `origin/main`:

| Tag    | Commit SHA      | Ancestor of origin/main? |
|--------|-----------------|--------------------------|
| v0.6.0 | 8d514a2faac2…  | OK |
| v0.6.1 | a019940204ab…  | OK |
| v1.0.0 | bbb439587bf9…  | OK |
| **v1.0.1** | **aae21e2680ee…** | **NO — lives on `origin/integration`** |
| **v1.1.0** | **50cb6c095f37…** | **NO — lives on `origin/integration`** |
| **v1.2.0** | **b28d94ecf5f8…** | **NO — lives on `origin/integration`** |
| v1.2.1 | 41235d08fdcf…  | OK |
| **v1.3.0** | **0ea83e1a2eb7…** | **NO — lives on `origin/integration`** |
| v1.3.1 | 88b7a1c33eb0…  | OK |
| v1.3.2 | 27586592b343…  | OK |
| **v1.4.0** | **2878bdaca445…** | **NO — only on `backup/integration` (private mirror)** |

Public `origin/main` has parallel "clean" commits with the SAME version subjects (Option C public-channel filter created them), but the **tags do not point to them**. The tags point to the integration-lineage commits.

Tree-diff comparison between tag-pointed commit and the corresponding cleaned commit on `origin/main`:

| Tag    | "Clean" commit on origin/main | Tree-diff |
|--------|-------------------------------|-----------|
| v1.0.1 | `373d35c` | 296 files, 69,638 deletions (clean = -70k lines) |
| v1.1.0 | `a335680` | 298 files, 70,007 deletions |
| v1.2.0 | `363b2bb` | 298 files, 70,008 deletions |
| v1.3.0 | `58b1ebd` | 299 files, 70,200 deletions |
| v1.4.0 | `166d2b8` | 356 files, 78,375 deletions |

Files present in the tag tree but not in the cleaned main tree include: `PLAN.md`, `SESSION_END_FINAL.md`, `STATUS.md`, `docs/pr13_prep/*` (persona_acceptance_spec, phase1_results, rectification_framework, etc.), `docs/autonomous_burst_release_plan.md`, `docs/SESSION_END_REPORT.md`, `docs/integration_sequencing_strategy.md`, `docs/midsession_hygiene_check.md`, ~250 more internal docs.

**Per `feedback_public_repo_hygiene.md`**: "never push internal planning, session IDs, personal info". This rule is currently violated for 5 tags on the public origin remote.

### 1.4 GitHub releases existence: FAIL (4 missing)

`gh release list` returns 8 releases. The following tags have NO corresponding GitHub release:

- **v0.6.0** — release not found (extra tag, no release)
- **v0.6.1** — release not found
- **v1.2.1** — release not found  ← may be intentional (universal2 hotfix)
- All others (v1.0.0, v1.0.1, v1.1.0, v1.2.0, v1.3.0, v1.3.1, v1.3.2, v1.4.0) — present

### 1.5 v1.4.0 release assets: EXPECTED-STATE PASS

```json
{"assets":[],"tagName":"v1.4.0"}
```

No assets attached. Per orchestrator expectation, LEG 10 is in flight to produce the v1.4.0 .dmg — current empty state is expected.

### 1.6 v1.4.0 release body: PASS (clean)

```
Adds locked_strategies parameter to solve(). Daniel persona's exploit-analysis
workflows (lock villain's bluff, lock merged ranges) now work. 1.6% overhead;
lock passthrough bit-exact across Python + Rust tiers. Per the persona acceptance
discipline: W3.1/W3.2/W3.3 will be re-tested post-ship to confirm the loop closes.

PR 22 (asymmetric-contributions / facing-bet support) queued for v1.4.1 —
would unblock W3.4 MDF queries.
```

No PII / paths / IDs detected.

---

## Section 2 — Local Working Tree Audit

### 2.1 `git status`: FLAG (untracked content)

- On `main`: YES
- Sync with `origin/main`: YES (HEAD = `166d2b8`)
- Untracked files/dirs:
  - `docs/` (entire dir untracked — includes prior session reports + this report)
  - `examples/range_vs_range_river.py`
  - `scripts/cleanup_pr_branches.sh`

This is expected per Option C public-channel filter (docs not in main) but flag for awareness.

### 2.2 Unpushed local commits: PASS

`git log origin/main..HEAD` is empty. No drift.

### 2.3 Stashes: FLAG (2 stashes)

```
stash@{0}: WIP on main: 58b1ebd chore(release): v1.3.0 ...
stash@{1}: On main: pre-comprehensive-review-fix backup
```

stash@{0} touches: CHANGELOG.md, DEVELOPER.md, README.md, USAGE.md, poker_solver/*, scripts/build_macos_dmg.sh, pyproject.toml, range_aggregator.py (712 lines). Looks load-bearing — likely intentional WIP from mid-burst recovery. Per memory `feedback_no_concurrent_branch_ops`: never `git stash drop` after conflicted pop. Hold for orchestrator decision.

### 2.4 Local branches: FLAG (many stale)

```
* main                          <-- current
  integration                   <-- expected (dual-channel)
  integration_tip               <-- transient label?
  fix/universal2-arch
  pr-3-hunl-tree, pr-3.5-pushfold, pr-4-card-abstraction, pr-4.5-audit-debt-sweep,
  pr-5-hunl-postflop-solve, pr-6-rust-hunl-port, pr-7-noambrown-diff,
  pr-8-simd-perf, pr-9-preflop, pr-10a-ui-mock-first, pr-10a.5-conformance,
  pr-10b-ui-bindings, pr-11-library-and-packaging,
  pr-15-rvr-perf, pr-16-blueprint-aggregator, pr-17-plan-c-dense-slabs,
  pr-18-stage-c1-numpy-slab, pr-19-v062-small-fixes, pr-20-v131-aggregator-patch,
  pr-21-node-locking, pr-22-asymmetric-contributions
```

Of these, the content of `pr-18-stage-c1-numpy-slab` and `pr-22-asymmetric-contributions` is already in `origin/main` (verified by `git merge-base --is-ancestor`). These two are stale-safe-to-delete. The rest are NOT in `origin/main` lineage (because of the Option C parallel-commit-rebuild).

---

## Section 3 — Worktree Audit (`/Users/ashen/Desktop/poker_solver_worktrees/`)

12 worktrees found:

| Dir | Branch | HEAD | Status | Verdict |
|-----|--------|------|--------|---------|
| pr-10b-ui-bindings | pr-10b-ui-bindings | 3dc877f | clean | stale (PR shipped) |
| pr-15-rvr-perf | pr-15-rvr-perf | 11b0546 | clean | stale (PR shipped as v1.3.2) |
| pr-16-blueprint | pr-16-blueprint-aggregator | 1b61e72 | clean | stale (PR shipped as v1.3.0) |
| **pr-17-plan-c** | pr-17-plan-c-dense-slabs | ea2511c | untracked `docs/` | PARKED (expected per orchestrator) |
| pr-18-stage-c1 | pr-18-stage-c1-numpy-slab | 88b7a1c | clean | stale (= v1.3.1 commit on main) |
| pr-19-v062 | pr-19-v062-small-fixes | 973ba62 | clean | stale (PR shipped) |
| pr-20-v131-aggregator-fixes | pr-20-v131-aggregator-patch | 8afeace | clean | stale |
| pr-21-node-locking | pr-21-node-locking | fb2cb42 | clean | stale (shipped as v1.4.0) |
| **pr-22-asymmetric** | pr-22-asymmetric-contributions | 166d2b8 | **2 modified, 1 untracked** | **ACTIVE (expected)** |
| pr-8-simd | pr-8-simd-perf | 3e07d45 | clean | stale (shipped as v1.0.1) |
| pr-9-preflop | pr-9-preflop | f82dc32 | clean | stale (shipped as v1.1.0) |
| universal2-fix | fix/universal2-arch | 9bd2f2e | clean | stale (shipped as v1.2.1) |

### 3.1 pr-22-asymmetric (ACTIVE) — flag content

Active agent work as expected. Modified files:
- `crates/cfr_core/src/hunl.rs`
- `poker_solver/hunl.py`
- Untracked: `tests/test_asymmetric_contributions.py`

HEAD = `166d2b8` (= origin/main HEAD). No commits added yet on this branch. Agent presumably staging changes.

### 3.2 pr-17-plan-c (PARKED) — PASS

HEAD = `ea2511c` ("WIP: Plan C dense slabs + vectorized showdown (parked; superseded by Option A v1.3.2)"). Matches orchestrator's stated state.

### 3.3 Other 10 worktrees — FLAG (cleanup candidates)

All clean, all on already-shipped PR branches. Safe to garbage-collect when orchestrator decides.

---

## Section 4 — Integration Mirror Audit (private `backup` remote)

`backup` = `https://github.com/amaster97/poker_solver_private.git`

### 4.1 Mirror sync state: PASS (with expected drift)

- `backup/main` = `166d2b8...` — **matches `origin/main`** ✓
- `backup/integration` = `2878bda...` — diverges from main as expected (this IS the integration commit for v1.4.0)

### 4.2 Integration ahead of main: PASS (expected per dual-channel)

20+ commits on `backup/integration` not in `origin/main`. These are the "raw" integration commits with internal docs (PLAN.md, docs/pr13_prep/*, etc.) — per Option C dual-channel design, those should NOT be in public `origin/main`. The cleaned counterparts ARE in `origin/main`.

Sample of integration-only commits:
```
2878bda chore(release): v1.4.0 — Node-locking
b3e4332 PR 21: v1.4.0 node locking (Python + Rust)
8b92a5c docs: recover session work from stash (52 files)
1dba31a chore(release): v1.3.2 ...
e78e57a PR 15: ...
945e32b docs(pr13_prep): rectification framework + stall-check coupling section
8375749 docs(PLAN): stall-check rule under §5 scheduling discipline
...
```

### 4.3 Mirror branches: FLAG (stale on private mirror too)

backup remote has these branches: `integration`, `main`, `pr-10a-ui-mock-first`, `pr-11-library-and-packaging`, `pr-4.5-audit-debt-sweep`, `pr-7-noambrown-diff`. Some are out of date relative to local. Not load-bearing — flag for cleanup.

### 4.4 origin also has PR branches: FLAG

`origin` (public) has these remote branches besides main: `integration`, `pr-10a-ui-mock-first`, `pr-11-library-and-packaging`, `pr-20-v131-aggregator-patch`, `pr-3-hunl-tree`, `pr-3.5-pushfold`, `pr-4-card-abstraction`, `pr-4.5-audit-debt-sweep`, `pr-5-hunl-postflop-solve`, `pr-6-rust-hunl-port`, `pr-7-noambrown-diff`.

Public origin has 10+ stale PR branches. Most/all were pre-v1 work. Per `feedback_pr_branch_hygiene.md` ("PR branches on public origin must be clean") these may or may not be acceptable depending on content. Visible from outside.

Also: **`origin/integration` exists** on public origin. Per memory `feedback_dual_remote_workflow` (public origin = main only), having `integration` on public origin appears to be drift — integration should be private-only.

---

## Section 5 — Release-Body PII Scan

Scanned each release's body for: `ashen26`, `@gsb.columbia.edu`, `/Users/ashen`, `claude-501`, UUID patterns, `ghp_`, `sk-`.

| Release | Status |
|---------|--------|
| v0.6.0 | NO RELEASE |
| v0.6.1 | NO RELEASE |
| v1.0.0 | clean |
| v1.0.1 | clean |
| v1.1.0 | clean |
| v1.2.0 | clean |
| v1.2.1 | NO RELEASE |
| v1.3.0 | clean |
| v1.3.1 | clean |
| v1.3.2 | clean |
| v1.4.0 | clean |

All 8 existing release bodies are PII-clean. **PASS**.

(Note: this is necessary but not sufficient. The release body is clean — but the underlying commit the release tag points to is NOT clean for v1.0.1/v1.1.0/v1.2.0/v1.3.0/v1.4.0; see §1.3.)

---

## Section 6 — Tag Annotation Check

Inspected `git tag -n20` for each tag. All annotations are concise release notes without PII or stash-dump leakage.

| Tag    | Annotation status |
|--------|-------------------|
| v0.6.0 | clean |
| v0.6.1 | clean |
| v1.0.0 | clean |
| v1.0.1 | clean (notes feasibility study reference) |
| v1.1.0 | clean (mentions scope-reduction) |
| v1.2.0 | clean |
| v1.2.1 | clean |
| v1.3.0 | clean (mentions Type C-CRITICAL) |
| v1.3.1 | clean |
| v1.3.2 | clean |
| v1.4.0 | clean |

**PASS** — no PII / agent IDs / session paths in tag annotations.

---

## Items Needing Orchestrator Decision

1. **CRITICAL: 5 tags on public origin point to integration commits with ~70k lines of internal planning content.**
   - Tags: v1.0.1, v1.1.0, v1.2.0, v1.3.0, v1.4.0
   - Contents leaked: PLAN.md, SESSION_END_FINAL.md, docs/pr13_prep/* (persona spec, rectification framework, phase1/2 results), docs/autonomous_*, docs/midsession_hygiene_check.md, docs/integration_sequencing_strategy.md, ~250 internal docs total
   - Resolution requires: re-tag each on the corresponding clean main commit, force-push tag, edit GH release to point to new tag commit. Force-push of tags is a destructive op — needs explicit auth per `feedback_pr_autonomous_commit`.
   - **OR** accept the leak and document the carve-out. The leaked content is the orchestrator's own planning work, not third-party PII.

2. **`origin/integration` branch exists on public remote.** Per `feedback_dual_remote_workflow` (public origin = main only), this is drift. Decide: delete from public, or update memory to reflect new state.

3. **Missing GH releases for v0.6.1 and v1.2.1.** v1.2.1 was the universal2 hotfix — likely intentional skip. v0.6.1 was a tagged checkpoint pre-v1. Decide: create releases or document as intentional skip.

4. **Stash@{0} and stash@{1} on local main.** stash@{0} is large (range_aggregator.py removal etc., from v1.3.0 era) — looks load-bearing. Per `feedback_no_concurrent_branch_ops`, must not `stash drop` after conflicted pop. Decide: pop into a branch for inspection, or leave parked.

5. **10 stale worktrees + ~15 stale local branches + ~10 stale public-origin PR branches.** No data risk per se, but clutter is significant. Schedule a cleanup PR.

---

## Items Safe to Ignore

- Extra local tag `v0.6.0` (predates expected ladder; matches origin tag; commits are in `origin/main` history; not a release-page concern).
- `integration_tip` local label (transient; no concurrent ops detected).
- Untracked `examples/range_vs_range_river.py` and `scripts/cleanup_pr_branches.sh` — these look like pending PR content not yet committed.
- `docs/` untracked locally — by design per Option C public-channel filter.
- v1.2.1 having no GH release — likely intentional (it was a universal2 .dmg hotfix, not a feature release).
- `backup` remote having stale PR branches — that's the private mirror, no public exposure.
- pr-22-asymmetric worktree's HEAD == origin/main HEAD with uncommitted changes — that's an active agent staging asymmetric-contributions code, exactly as orchestrator stated.
- All tag annotations and release bodies are PII-clean — passes the explicit checks in tasks 5 and 6.

---

## Verification metadata

- Audit date: 2026-05-23 late
- Tool calls used: under 20
- gh CLI: authenticated (account `amaster97`, scopes: `gist read:org repo workflow`)
- Investigation: 100% read-only. No pushes, edits, force-pushes, gh release edits, or file modifications outside this report.
