# Next Session Plan (Post-v1.0.0 GA)

**Status:** Staging document. Read-only / planning artifact prepared at session pause on 2026-05-22.
**Predecessor:** `docs/V1_GA_MILESTONE_HIT.md`, `docs/release_notes_v1.0.0.md`, `docs/SESSION_END_REPORT.md`.
**Cadence reference:** `docs/v0.5.0_release_recipe.md` (re-use the same merge + tag pattern).

---

## 1. Session 1 Priority: Main Merge Approval

The v1.0.0 GA release currently lives on `integration`. Promoting to `main` is the first action of the next session.

**Gating:** Explicit user OK required before any branch-write operations. Orchestrator does not self-approve a main merge.

**Recipe (mirrors v0.5.0 release recipe):**

```
git checkout main
git pull --ff-only origin main
git merge --no-ff integration -m "v1.0.0 GA release"
git push origin main
```

**Tag handling decision (orchestrator's call, consistent with v0.5.0 recipe):**

- Move the `v1.0.0` tag from the integration-side commit to the merge commit on `main`, then `git push --force-with-lease origin v1.0.0`.
- Rationale: every prior release tag (v0.3.x, v0.5.x, v0.6.0) sits on main; v1.0.0 should not be the lone exception. Force-with-lease is explicit and safe because no downstream consumers have pinned the SHA.
- If the user prefers a fresh tag (`v1.0.1` on the merge commit) we will defer to that — but the default is the move.

**Post-merge verification:**

- `git log --oneline -5 main` shows the GA merge as `HEAD`.
- `git tag --points-at HEAD` includes `v1.0.0`.
- CI (if wired) green on `main`.

---

## 2. Parallel Wave A (post-main-merge)

Two tracks run concurrently in **separate git worktrees** (per the no-concurrent-branch-ops rule — never branch-switch in the shared tree while other agents may write).

### PR 10a.5 — UI conformance pass

- **Branch:** `pr-10a5-ui-conformance`
- **Worktree:** `../poker_solver-pr10a5/`
- **Scope:** Close the 5 fail + 7 xfail items left open from PR 10a. See `docs/audit_followup_backlog.md` for the deferred list.
- **Estimate:** 4-6 hours of focused work.
- **Risk:** Low. Pure conformance / display-layer work; no solver-core changes.

### PR 8 — NEON SIMD + cache-blocked equity + PCS

- **Branch:** `pr-8-perf` (already scaffolded in `docs/perf_bench_scaffolds*.md`).
- **Worktree:** main tree is fine if no other engine-touching work is in flight; otherwise spawn `../poker_solver-pr8/`.
- **Scope:** ARM NEON SIMD path for hand evaluation, cache-blocked equity computation, PCS (per-card sampling) integration.
- **Estimate:** 3-5 days.
- **Validation chain:** equity-vs-OMP cross-check + perf-bench scaffolds already in place.

These two tracks are independent: PR 10a.5 touches UI / conformance harness; PR 8 touches solver-core perf. Fan-out is safe and aligns with the parallel-agents default.

---

## 3. Wave B — PR 9 (HUNL Preflop Full)

- **Branch:** `pr-9-hunl-preflop` (prep notes already in `docs/pr9_prep/`).
- **Scope:** Full HUNL preflop CFR solve, not the pushfold abstraction. Closes the headline functional gap relative to competitors (see `docs/competitor_landscape.md`).
- **Estimate:** 3-5 days.
- **Release decision on ship:** `v0.7.0` (additive feature) vs. `v1.1.0` (minor bump under SemVer post-GA). Default: **`v1.1.0`** — we are post-1.0, so MINOR bumps follow the GA line, not the pre-1.0 0.x cadence. Revisit at the merge gate.

---

## 4. Wave C — PR 10b (Mock-to-Real Swap)

- **Estimate:** 1-2 hours. Tiny.
- **Why so small:** Option A applied during PR 10a means the swap is a one-liner config change plus a re-record of golden outputs. No structural rework.
- **Ship vehicle:** Patch release on the post-PR-9 line, or bundled into the same MINOR.

---

## 5. PR 12 — Three-Handed Stretch (Optional, Post-v1)

- **Status:** Explicitly approximate. Not a correctness goal; a research stretch.
- **Gate:** Only after the v1.x line (PRs 8, 9, 10a.5, 10b) is shipped and stable.
- **Estimate:** Open-ended. Defer scoping until v1.x is on `main`.

---

## 6. Estimated Total Time to v1.x Complete

**1-2 weeks** from main-merge approval to v1.x feature-complete, covering PR 8 + PR 9 + PR 10b + PR 10a.5. Wall-clock can compress to ~1 week if Wave A and Wave B partially overlap (PR 10a.5 finishes well before PR 8, freeing the worktree for PR 9 prep).

**Critical-path driver:** PR 8 and PR 9 are each multi-day. They serialize unless we can fan out two perf/algo agents simultaneously, which the rules permit (>=5 agent floor) but the engine-touching nature of both makes them prone to merge conflict — recommend serial: PR 8 first, then PR 9.

---

## 7. Cleanup Items

These are housekeeping tasks to slot in between waves (not gated, not on the critical path):

- **Delete `origin/equity-precision`** — stale branch. User OK still pending; carry the ask forward. See `docs/equity_precision_branch_investigation.md`.
- **Create `docs/archive/`** and move prep docs no longer current:
  - PR 11 prep docs (PR 11 retired / superseded).
  - PR 10a prep docs (PR 10a shipped).
  - PR 4.5 prep docs (PR 4.5 shipped).
  - Wake-up briefs, snapshot files older than the last release.
- **Re-examine `docs/audit_followup_backlog.md`** after PR 10a.5 lands — close items that the conformance pass resolves; promote any remaining critical items to PR 9 / PR 8 scope.
- **Prune `MEMORY.md` and `PLAN.md`** per the continuous-pruning rule after each PR ships.

---

## 8. Open Questions for User at Session Start

1. Approve the `integration -> main` merge for v1.0.0? (blocking)
2. Approve moving the `v1.0.0` tag to the merge commit on `main`? (default: yes; recipe-consistent)
3. Approve deleting `origin/equity-precision`? (low risk, stale)
4. Confirm PR 8 before PR 9 ordering, or invert? (default: PR 8 first — perf wins compound with feature work)
5. Confirm release-line policy: `v1.1.0` for PR 9 ship? (default: yes, post-GA SemVer)

---

## Constraints Reminder

This document is **read-only / staging only**. No code, branch, tag, or push operations have been performed in producing it. All actions above are gated on explicit user approval at the start of the next session.
