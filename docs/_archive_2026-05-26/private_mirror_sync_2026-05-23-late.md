# Private Mirror Sync — 2026-05-23 (late)

**Date:** 2026-05-23 (late session)
**Operation:** Sync accumulated internal docs to private mirror (`backup` remote) per `feedback_dual_remote_workflow.md`
**Public origin:** UNTOUCHED beyond `main` (already in sync pre-operation)

---

## Remote configuration (verified pre-sync)

```
backup    https://github.com/amaster97/poker_solver_private.git (push)
origin    https://github.com/amaster97/poker_solver.git         (push)
```

Naming: `backup` = private mirror (carries `integration` + `main` + feature branches);
`origin` = public (carries `main` only, per public-repo hygiene rule).

---

## Pre-sync state

| Branch | Local HEAD | `origin/main` HEAD | `backup/main` HEAD | `backup/integration` HEAD |
|---|---|---|---|---|
| main | `94007ca` | `94007ca` (FF-current) | `166d2b8` (v1.4.0; ~30 commits behind) | n/a |
| integration | `2878bda` (v1.4.0) | n/a | n/a | `2878bda` (FF-current) |

Local `main` was in sync with `origin/main` but **`backup/main` was significantly behind**
(missing v1.4.1 → v1.6.0 GA + the README/aggregator-explainer refresh).

Local `integration` matched `backup/integration` exactly (both at v1.4.0). Integration had
27 unique commits not on main (older internal-only planning history).

---

## Step 1 — Push `main` to `backup`

```
$ git push backup main
To https://github.com/amaster97/poker_solver_private.git
   166d2b8..94007ca  main -> main
```

**Result:** `backup/main` advanced from `166d2b8` (v1.4.0) to `94007ca` (post-v1.6.0 README
refresh) — 30 commits fast-forwarded. Public-OK content only; nothing internal in this push.

---

## Step 2 — PII / secrets scan of internal docs

Patterns scanned across `docs/`, `PLAN.md`, `RELEASE_*.md`:

| Pattern | Hits | Verdict |
|---|---|---|
| `sk-ant-*` (Anthropic API key) | 0 | Clean |
| `ghp_*` / `github_pat_*` (GitHub PAT) | 0 | Clean |
| `BEGIN [A-Z ]+PRIVATE KEY` (private keys) | 0 | Clean |
| Full UUIDs near "session id" | 0 | Clean |
| `/Users/ashen/.claude/` (personal paths) | 2 mentions | OK on private (per workflow memory) |
| `ashen26` / `@gsb.columbia.edu` | 1 (in audit-doc *listing what to scan for*) | OK |

No credentials, no session UUIDs, no AGPL contamination. Personal paths are explicitly
allowed on the private mirror per `feedback_dual_remote_workflow.md`.

---

## Step 3 — Build integration commit

Used a dedicated worktree (`/private/tmp/integration-sync`) to avoid the
`no-concurrent-branch-ops` violation (other agents may be writing in the main tree).

Initially attempted `git merge --no-ff main` to bring integration in sync with main code
state — this produced 13 conflicts (CHANGELOG, README, USAGE, Rust crate, PLAN.md
modify/delete, pyproject, etc.). **Aborted the merge.**

**Rationale for abort:** per workflow memory, integration is "the full source... main is
the curated public subset" — it does NOT need to track main's code state. Integration's
purpose is to accumulate internal planning context. Code/release content lives on `main`
and gets pushed to both remotes.

**Approach used instead (additive only):** copy the 126 untracked items from the main
worktree directly into the integration worktree (rsync --files-from), commit as a single
"internal docs accumulator" commit. No merge with main code paths — those stay on `main`.

Files copied:
- 4 root-level: `PLAN.md`, `RELEASE_CHECKLIST_2026-05-23.md`,
  `RELEASE_HEADLINES_2026-05-23.md`, `RELEASE_NOTES_2026-05-23.md`
- 99 new `docs/` items (incl. subdirs `pr8_prep/`, `pr8b_prep/`, `pr9_prep/`, `pr10b_prep/`,
  `pr11_prep/`, `pr13_prep/`, `pr15_prep/`, `pr16_prep/`, `pr18_prep/`,
  `persona_test_results/`, plus 23 new files in `pr_proposals/`)
- 1 utility script: `scripts/cleanup_pr_branches.sh` (held back from public)
- 2 modifications to existing tracked-on-integration files: `PLAN.md` updated,
  `scripts/cleanup_pr_branches.sh` updated

Excluded:
- `docs/aggregator_vs_true_nash_explainer.md` (already public — landed on `main` via
  `94007ca`, not in untracked set anyway)
- Modified tracked code: `pyproject.toml`, `scripts/build_macos_dmg.sh`,
  `scripts/poker_solver.spec` (PR 44 DMG fix — these are *code* changes destined for
  `main`, not integration-only docs; left for a separate PR-44 merge cycle)

---

## Step 4 — Commit on integration

Commit message: see `integration` branch HEAD (after this report is included).

---

## Step 5 — Push integration to backup

```
$ git push backup integration
To https://github.com/amaster97/poker_solver_private.git
   2878bda..3475ca9  integration -> integration
```

**Result:** `backup/integration` advanced from `2878bda` (v1.4.0) to `3475ca9` (internal
docs accumulator). Single commit, 120 files (119 added + 1 modified + 1 mode-change).

---

## Step 6 — Public vs private routing audit

| Surface | Content type | Routed to | Verified |
|---|---|---|---|
| `origin/main` | v1.6.0 code + public docs | Public | `94007ca` (unchanged this op) |
| `backup/main` | Same as `origin/main` | Private mirror of public | `94007ca` (synced this op) |
| `backup/integration` | Internal planning docs + above public history's parent | Private only | Updated this op |

**No leaks detected.** Internal docs (PLAN.md, RELEASE_*.md, persona test results,
PR prep dirs, audit reports, ship plans) did NOT touch `origin`. Confirmed by:

```
$ git ls-remote origin refs/heads/main | awk '{print $1}'
94007ca   # matches pre-sync; no force-push, no extra refs
```

---

## Final state (post-sync)

| Ref | SHA | Branch tip message |
|---|---|---|
| `origin/main` | `94007ca` | docs: refresh README to v1.5.x + aggregator explainer + CHANGELOG fix |
| `backup/main` | `94007ca` | same as origin (now in sync) |
| `backup/integration` | `3475ca9` | docs: session 2026-05-23 internal docs accumulator (private-only) |

Verification (post-push `ls-remote`):

```
$ git ls-remote origin refs/heads/main
94007cac5ec0c445238377238f2853fd6102f19b  refs/heads/main

$ git ls-remote backup refs/heads/main refs/heads/integration
3475ca9896a0454507ff7f16dcc45a774e1a9e51  refs/heads/integration
94007cac5ec0c445238377238f2853fd6102f19b  refs/heads/main
```

---

## Constraints honored

- ✅ No internal docs pushed to `origin`
- ✅ PII grep passed (no secrets, no session UUIDs)
- ✅ No `--force` / `--force-with-lease` used
- ✅ No `--all` / `--mirror` against any remote
- ✅ Worktree used for cross-branch operation (no branch switch in shared tree)
- ✅ Explicit remote + branch on every push command
