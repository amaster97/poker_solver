# Backup Branch Audit — 2026-05-26

**Scope:** the ~10 stale `backup/pr-*` branches on the private mirror (`backup` = `github.com/amaster97/poker_solver_private`).

**Authority constraint:** branch deletion on `backup` (private mirror) is in the explicit exception list per `feedback_pr10a5_autonomous_commit.md`; **NO deletions executed**. This is a read-only audit + recommendation report. The user must opt-in via the copy-paste block at the bottom.

**Inputs:** `git fetch backup` then per-branch `git log origin/main..backup/<B>`, `git log backup/integration..backup/<B>`, content diffs against `backup/integration` and `origin/main`.

---

## Per-branch decisions

| Branch | Tip date | Tip SHA | Decision | Rationale |
| --- | --- | --- | --- | --- |
| `backup/pr-10a-ui-mock-first` | 2026-05-23 | `db58ea5` | **DELETE candidate** | Only delta vs `origin/main` is `chore: remove session artifacts from PR branch` (deletes `STATUS.md`, an integration-only artifact that never existed on `origin/main`). PR 10a content is already on `origin/main` via the integration merge train (`b880032 Integration: merge PR 10a (...)` + follow-ups). Branch carries no unique work. |
| `backup/pr-11-library-and-packaging` | 2026-05-23 | `b9077cc` | **DELETE candidate** | Only delta vs `origin/main` is `chore: remove session artifacts from PR branch` (deletes `STATUS.md` + `SESSION_END_FINAL.md`, integration-only). PR 11 content is on `origin/main` via `bbb4395 Integration: merge PR 11 (library + macOS .dmg, v1.0.0 GA)` plus three follow-up merges. Branch carries no unique work. |
| `backup/pr-4.5-audit-debt-sweep` | 2026-05-23 | `fa6d1c4` | **DELETE candidate** | Only delta vs `origin/main` is `chore: remove session artifacts from PR branch` (deletes `STATUS.md`). PR 4.5 content is on `origin/main` via `9f09d49 Integration: merge PR 4.5 (audit-debt sweep, v0.5.2)`. Branch carries no unique work. |
| `backup/pr-7-noambrown-diff` | 2026-05-23 | `7b0ed4b` | **DELETE candidate** | Only delta vs `origin/main` is `chore: remove session artifacts from PR branch` (deletes `STATUS.md`). PR 7 content is on `origin/main` via `d135add Integration: merge PR 7 (river-spot diff vs Brown, v0.5.1)`. Branch carries no unique work. |
| `backup/pr-78-plan-scope-add-b9-b10` | 2026-05-25 | `a8dfccb` | **DELETE candidate** | Single commit (`a8dfccb docs(plan): add B9 (exploitative play) + B10 (Range fractional) to v1 burst scope`) is fully absorbed on `backup/integration` as squash commit `1383a84 docs(plan): add B9 ... (#1)` — PLAN.md byte-for-byte identical (`diff /tmp/squashed_plan.md /tmp/branch_plan.md` returns empty). The work is private-only (PLAN.md not on `origin/main` — stripped during Option C public-channel filter), but the canonical archive is `backup/integration`. Branch is redundant clutter. |
| `backup/pr-29-persona-spec-corrections` | 2026-05-23 | `1b95c5b` | **SURFACE TO USER** | Single commit applies 7 corrections to `docs/pr13_prep/persona_acceptance_spec.md` (W1.3 equity inversion AKs 27%/73% → 91%/9%; W2.1/W2.2/W2.5 PASS → PARTIAL reclasses; W4.2 BB iso-raise qualifier; new "CLI ergonomics gaps" section). Verified NOT on `backup/integration` (`git show backup/integration:docs/pr13_prep/persona_acceptance_spec.md | grep "AKs ≈ 91%"` returns 0). NOT on `origin/main` (file doesn't exist there per Option C filter). NOT in local working tree. **Unique work — only copy of these spec corrections.** |
| `backup/pr-38-persona-corrections` | 2026-05-23 | `71d161d` | **SURFACE TO USER** | Two commits propagate audit-trail corrections after the 2026-05-23 late audit: W1.2 deep-stack requirement note, W3.5 RvR-blocked qualifier, new `persona_verdict_revision_history.md` (169 lines), `v1_3_2_phase2b_audit.md` framing correction. Verified NOT on `backup/integration` (`persona_verdict_revision_history.md` does not exist on integration). NOT on `origin/main`. NOT in local working tree. **Unique work.** |
| `backup/pr-41-phase2b-audit-revision` | 2026-05-23 | `dcc9d83` | **SURFACE TO USER** | One commit adds 33-line revision block to `v1_3_2_phase2b_audit.md` documenting the W2b.1 per-hand breakdown rerun (500 iter vs 50 iter — `AK fold=0.773` correction). Verified NOT on `backup/integration` (`grep "AK fold=0.773"` returns 0). NOT on `origin/main`. NOT in local working tree. **Unique work — corrects a load-bearing under-converged finding.** |
| `backup/pr-42-w3-5-reversal` | 2026-05-23 | `90a3c27` | **SURFACE TO USER** | Three commits reverse the W3.5 downgrade per vector-form TRUE Nash test (`W3_5_TRUE_nash_v1_5_1.md`): PASS → BLOCKED → PASS+. Includes evidence file commit + BLOCKED-set membership cleanup. Verified NOT on `backup/integration` (the W3.5 reversal text isn't in integration's `persona_verdict_revision_history.md` — file doesn't exist there). NOT on `origin/main`. NOT in local working tree. **Unique work — a verdict-level reversal that affects the persona acceptance summary.** |
| `backup/pr-dmg-verify-2026-05-25` | 2026-05-25 | `f7566af` | **SURFACE TO USER** | Single commit adds `docs/dmg_verification_2026-05-25.md` (56 lines) — real-data verification of the v1.6.0 .dmg (SHA256 match against PLAN.md, ad-hoc signed, arm64, 48-framework load incl. `_rust.cpython-313-darwin.so`, NiceGUI server boot). Verified NOT on `backup/integration`. NOT on `origin/main`. NOT in local working tree. **Unique work — the .dmg verification audit trail referenced by PLAN.md Gate 5.** |

Note: `backup/pr-10a.5-conformance` does NOT exist on the backup remote (verified via `git branch -r | grep 10a.5`). PR 10a.5 content is on `origin/main` directly (`67760c7 PR 10a.5: UI conformance pass`).

---

## Totals

- **DELETE candidates (5):** `pr-10a-ui-mock-first`, `pr-11-library-and-packaging`, `pr-4.5-audit-debt-sweep`, `pr-7-noambrown-diff`, `pr-78-plan-scope-add-b9-b10`
- **SURFACE TO USER (5):** `pr-29-persona-spec-corrections`, `pr-38-persona-corrections`, `pr-41-phase2b-audit-revision`, `pr-42-w3-5-reversal`, `pr-dmg-verify-2026-05-25`
- **KEEP unconditionally:** none in this audit set (none qualified as "ongoing working trail")

The branch policy ("keep working trail of things to merge / features for debugging and building, don't want repetitive redundant clutter") cuts both ways here. The 5 DELETE candidates ARE the redundant clutter — their content is already in the canonical archive (`origin/main` or `backup/integration`). The 5 SURFACE candidates ARE genuine working trail — they hold the only copy of substantive docs work and **must not be deleted until decided**.

---

## Surface-to-user discussion

The 5 SURFACE branches all hold persona/audit docs work from 2026-05-23 (4 branches) + 2026-05-25 (1 branch) that never made it back to `backup/integration`. Three options for the user:

1. **Cherry-pick the unique commits onto `backup/integration`** (per the rule that integration is the canonical private archive), THEN delete the branches. Preserves the audit trail in one place. Recommended if any of the persona-spec corrections / W3.5 reversal / .dmg verification are still load-bearing for current ship decisions.
2. **Keep the branches as-is** for archival purposes — accept the clutter cost. Justifiable if user wants the original commit-level audit trail (separate branches per audit episode) rather than a single integration-folded view.
3. **Delete them** after explicit user confirmation that the content is no longer needed — accept the loss of the unique audit work. Only sensible if the user reviews each and confirms it's been superseded by later work on integration.

Default recommendation: option 1 (cherry-pick to integration, then delete). The user's "don't want repetitive redundant clutter" preference is in tension with "keep working trail" only because integration drift left these unmerged; folding them in resolves the tension.

---

## Copy-paste delete commands

**For the 5 DELETE candidates** (audit-clean, no unique work):

```bash
git push backup --delete pr-10a-ui-mock-first
git push backup --delete pr-11-library-and-packaging
git push backup --delete pr-4.5-audit-debt-sweep
git push backup --delete pr-7-noambrown-diff
git push backup --delete pr-78-plan-scope-add-b9-b10
```

Or as a single line:

```bash
git push backup --delete pr-10a-ui-mock-first pr-11-library-and-packaging pr-4.5-audit-debt-sweep pr-7-noambrown-diff pr-78-plan-scope-add-b9-b10
```

**Do NOT execute** the SURFACE branches without per-branch user confirmation:
- `pr-29-persona-spec-corrections`
- `pr-38-persona-corrections`
- `pr-41-phase2b-audit-revision`
- `pr-42-w3-5-reversal`
- `pr-dmg-verify-2026-05-25`

After the SURFACE branches are dispositioned (option 1, 2, or 3 above), the corresponding deletes can be appended to the block above.

---

## Method notes

- Verification matrix per branch:
  1. `git log origin/main..backup/<B>` → enumerates branch-unique commits vs public main
  2. `git log backup/integration..backup/<B>` → enumerates branch-unique commits vs private integration
  3. `git show backup/integration:<file> | grep <unique_marker>` → spot-check that the actual change-text isn't on integration via a different SHA
  4. `git branch -a --contains <SHA>` → confirms no other branch carries the commit
- All 5 SURFACE branches passed all 4 checks as "genuinely unique"; all 5 DELETE branches failed checks 2 or 3 (content present elsewhere).
- `backup/pr-78-plan-scope-add-b9-b10` is the one squash-absorption case in this audit: its `a8dfccb` was squashed into `1383a84 (#1)` on `backup/integration` with byte-identical PLAN.md content. This is the textbook "different SHA, same content via squash → DELETE candidate" case from the audit procedure.
- `origin` also carries `pr-10a-ui-mock-first`, `pr-11-library-and-packaging`, `pr-4.5-audit-debt-sweep`, `pr-7-noambrown-diff` as remote branches. Those are **out of scope** for this audit (which is `backup`-only) but the user may want to audit them next.
