# Branch name drift audit (2026-05-22)

**Scope:** verify every `docs/prN_prep/audit_prompt.md` branch reference matches the canonical name in `launch_kickoff.md` / `fanout_ready.md`. Triggered by PR 8 mismatch (`audit_prompt.md` line 14 said `pr-8-simd-layout-pcs` while `fanout_ready.md` says `pr-8-neon-simd-pcs` — the latter is canonical per the user's explicit lock).

**Canonical names (from task spec):**
- PR 4.5: `pr-4.5-audit-debt-sweep`
- PR 6: `pr-6-rust-hunl-port` (already verified per user)
- PR 7: `pr-7-noambrown-diff`
- PR 8: `pr-8-neon-simd-pcs`
- PR 9: `pr-9-hunl-preflop`
- PR 10a: `pr-10a-ui-mock-first`
- PR 10b: `pr-10b-ui-real-solver`
- PR 11: `pr-11-library-and-packaging`
- PR 12: `pr-12-three-handed-stretch`

## PR 8 patch summary

`docs/pr8_prep/audit_prompt.md` had `pr-8-simd-layout-pcs` at four locations:
- Line 7 (intro paragraph: "no implementation context...")
- Line 14 (Branch under audit field)
- Line 21 (branch diff command example)
- Line 123 (audit-report template Branch field)

All four occurrences replaced with `pr-8-neon-simd-pcs` via `Edit (replace_all=true)`. Verified with `grep`: zero remaining occurrences of the stale name; four occurrences of the canonical name.

## Cross-PR drift findings

Swept `audit_prompt.md` files across all `pr*_prep/` directories using `grep -rEn "Branch under audit"`. Findings:

| PR | File | Stale name | Canonical | Status |
|----|------|------------|-----------|--------|
| 4.5 | `launch_kickoff.md` (only file) | — | `pr-4.5-audit-debt-sweep` | CLEAN |
| 6 | `audit_prompt.md` | `pr-6-rust-hunl-postflop` (4×) | `pr-6-rust-hunl-port` | DRIFT — see note below |
| 6 | `launch_kickoff.md` | `pr-6-rust-hunl-postflop` (many) | `pr-6-rust-hunl-port` | DRIFT — see note below |
| 6 | `commit_message_draft.md:225` | `pr-6-hunl-rust-port` (transposed) | `pr-6-rust-hunl-port` | DRIFT — see note below |
| 6 | `audit_prompt_final.md` | — | `pr-6-rust-hunl-port` | CLEAN (this is the file actually used at audit time) |
| 7 | `audit_prompt.md` | — | `pr-7-noambrown-diff` | CLEAN |
| 8 | `audit_prompt.md` | `pr-8-simd-layout-pcs` (4×) | `pr-8-neon-simd-pcs` | PATCHED (above) |
| 9 | `audit_prompt.md` | — | `pr-9-hunl-preflop` | CLEAN |
| 10a | `audit_prompt.md` | `pr-10-ui-nicegui` (4×) | `pr-10a-ui-mock-first` | DRIFT — patched |
| 10b | `launch_kickoff_10b.md` + `fanout_ready_10b.md` only | — | `pr-10b-ui-real-solver` | CLEAN |
| 11 | `audit_prompt.md` | `pr-11-library-packaging` (5×) | `pr-11-library-and-packaging` | DRIFT — patched |
| 12 | `audit_prompt.md` | `pr-12-three-handed` (4×) | `pr-12-three-handed-stretch` | DRIFT — patched |

**Total drift items found across other PRs:** 4 (PR 6 audit_prompt.md, PR 6 launch_kickoff.md, PR 6 commit_message_draft.md, PR 10a audit_prompt.md, PR 11 audit_prompt.md, PR 12 audit_prompt.md). Of these, PR 6 items are flagged but NOT patched per user note "already verified."

## Patches applied per PR

### PR 8 (the trigger; covered above)
- `docs/pr8_prep/audit_prompt.md`: `pr-8-simd-layout-pcs` → `pr-8-neon-simd-pcs` (4 occurrences).

### PR 10a
- `docs/pr10_prep/audit_prompt.md`: `pr-10-ui-nicegui` → `pr-10a-ui-mock-first` (4 occurrences: lines 7, 14, 21, 137). This file is the audit prompt referenced by `launch_kickoff_10a.md:12`; the monolithic PR 10 name was never updated when PR 10 was split into 10a/10b.

### PR 11
- `docs/pr11_prep/audit_prompt.md`: `pr-11-library-packaging` → `pr-11-library-and-packaging` (5 occurrences: lines 7, 14, 21, 137, and one comment). Matches `launch_kickoff.md:7` + `fanout_ready.md:58` canonical.

### PR 12
- `docs/pr12_prep/audit_prompt.md`: `pr-12-three-handed` → `pr-12-three-handed-stretch` (4 occurrences: lines 7, 16, 23, 145). Matches `launch_kickoff.md:7` canonical (note the `-stretch` suffix signals post-v1 status per spec).

### PR 6 (FLAGGED, not patched per "already verified" user note)
- `docs/pr6_prep/audit_prompt.md` (4×): stale name `pr-6-rust-hunl-postflop`. The canonical file `audit_prompt_final.md` already has `pr-6-rust-hunl-port` and is the file actually consumed at audit time per the PR 6 commit_pipeline_readiness record.
- `docs/pr6_prep/launch_kickoff.md` (many): same stale `-postflop` name throughout, including the "branch name is hard-coded in audit_prompt.md — do NOT improvise" warning (which now points at the stale `audit_prompt.md`, not `audit_prompt_final.md`).
- `docs/pr6_prep/commit_message_draft.md:225`: transposed `pr-6-hunl-rust-port` (vs. canonical `pr-6-rust-hunl-port`). The commit_pipeline_readiness.md already flags this transposition explicitly at lines 10-11.

If the user wants PR 6 cleaned despite "already verified": three surgical replaces would close the gap. Recommend deferring until PR 6 actually lands (commit_message_draft + launch_kickoff are no longer load-bearing post-merge).

## Verification

```
grep -rEn "Branch under audit" docs/pr*_prep/ docs/pr*_audit_debt/
```

All 9 audit_prompt.md files now use canonical names matching the user's lock list (with PR 6's `audit_prompt.md` being the only stale outlier, flagged above).
