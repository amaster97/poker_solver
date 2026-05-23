# PLAN.md edit recipe — post-PR-4.5 landing

**Status:** RECIPE ONLY. Do NOT apply until PR 4.5 has merged to `integration` and the actual merge SHA is known. Recipe authored 2026-05-22 against PLAN.md tip `6c438b8`.

**Files touched (both must stay byte-identical):**
- `/Users/ashen/.claude/plans/not-exactly-but-a-inherited-river.md` (canonical)
- `/Users/ashen/Desktop/poker_solver/PLAN.md` (local mirror)

**Per the plan-sync rule:** edit canonical first, then `cp` to local. Verify with `diff` → expect empty output.

**Placeholder used below:** `<SHA45>` = the 7-char merge SHA of PR 4.5 onto `integration` (capture from `git log --oneline integration -1` after the merge).

---

## Note on prompt-vs-reality drift

The originating prompt referenced an "integration tip `d135add`" as the pacing tip. PLAN.md currently shows `6c438b8` (PR 6 / v0.5.0 milestone). Assumption: the prompt was speculative about a downstream state where PR 7 had also landed and bumped the tip. **This recipe treats the §5 pacing tip as `6c438b8` (the value actually in PLAN.md today) and updates it to `<SHA45>`.** If by landing time PR 7 has already merged and bumped the tip beyond `6c438b8`, the §5 edit's `old_string` must be re-anchored against whatever PLAN.md actually says at that moment.

Same caveat applies to the §1 status block phrasing: it currently mentions "PR 1-6" with "PR 7 currently in flight", not "PR 1-7 landed". If PR 7 has landed before PR 4.5 lands, the §1 edit recipe must be regenerated accordingly.

---

## Edit 1 — §1 Status block (line 3)

**Old:**
```
**Status:** PR 1-6 + 3.5 + 3.5-followup landed on `integration` (tip `6c438b8`; v0.5.0 released). PR 7 (noambrown river-spot diff) currently in flight. Awaiting `main` merge approval (integration → main).
```

**New:**
```
**Status:** PR 1-6 + 3.5 + 3.5-followup + 4.5 (audit-debt sweep; landed early — was thought optional) landed on `integration` (tip `<SHA45>`; v0.5.0 released). PR 7 (noambrown river-spot diff) currently in flight. Awaiting `main` merge approval (integration → main).
```

---

## Edit 2 — §2 Trajectory table (insert PR 4.5 row as ✅)

PR 4.5 is **not yet listed** in the §2 table (only mentioned in §6 carryover items and §7 kickoff docs). Insert a new row between the existing PR 6 (line 89) and PR 7 (line 90) rows.

**Old (line 90):**
```
| **PR 7** | River-spot diff test vs `noambrown/poker_solver` | 🚧 | 3-agent fan-out launched at integration tip `6c438b8` |
```

**New (insert PR 4.5 row above PR 7):**
```
| **PR 4.5** | Audit-debt sweep — 13 mechanical fixes across PR 3 / 3.5 / 4 / 5 (no behavior changes) | ✅ | `<SHA45>` on integration (landed early; was originally spec'd as optional cleanup) |
| **PR 7** | River-spot diff test vs `noambrown/poker_solver` | 🚧 | 3-agent fan-out launched at integration tip `6c438b8` |
```

**PR 10a row:** stays 📋 — no edit needed; it's already "spec'd + prompts" and remains ready to fire.

---

## Edit 3 — §5 Pacing tip SHA (line 218)

**Old:**
```
- **Autonomous overnight mode:** `integration` branch ("pseudo-main") autonomously accumulates merged PR branches; always reflects the latest working set. Tip: `6c438b8`.
```

**New:**
```
- **Autonomous overnight mode:** `integration` branch ("pseudo-main") autonomously accumulates merged PR branches; always reflects the latest working set. Tip: `<SHA45>` (PR 4.5 audit-debt sweep landed; v0.5.0 unchanged).
```

---

## Edit 4 — §7 Kickoff docs entry (line 260)

Mark PR 4.5's kickoff as shipped (mirror the PR 6 pattern at line 261).

**Old:**
```
- **`docs/pr4_5_audit_debt/launch_kickoff.md`** — sweep PR that drains the should-fix backlog (PR 3 / 3.5 / 4 / 5) before PR 6 review hardens. Runs parallel to PR 6 in-flight.
```

**New:**
```
- **`docs/pr4_5_audit_debt/launch_kickoff.md`** — sweep PR that drained the should-fix backlog (PR 3 / 3.5 / 4 / 5). **Shipped at `<SHA45>` on integration** (landed early; was originally spec'd as optional).
```

---

## Edit 5 — §7 Sequencing intent (line 270)

PR 4.5 has now shipped, so the sequencing prose should reflect that.

**Old:**
```
Sequencing intent: PR 6 ✅ → PR 7 (in flight) + PR 4.5 sweep in parallel → PR 8 → PR 9 + PR 10a in parallel → PR 10b → PR 11 → PR 12.
```

**New:**
```
Sequencing intent: PR 6 ✅ + PR 4.5 ✅ → PR 7 (in flight) → PR 8 → PR 9 + PR 10a in parallel → PR 10b → PR 11 → PR 12.
```

---

## Edit 6 — §6 Carryover items "PR 4.5 audit-debt sweep" line (line 245)

The current carryover line says "kickoff staged" + "batches resolution before PR 6 audit completes" — both stale once PR 4.5 lands.

**Old:**
```
- **Audit follow-up backlog — should-fix items across PR 3/3.5/4/5.** All deferred, none correctness-blocking. **Action:** PR 4.5 audit-debt sweep PR (kickoff staged) batches resolution before PR 6 audit completes.
```

**New:**
```
- **Audit follow-up backlog — should-fix items across PR 3/3.5/4/5.** **RESOLVED** at `<SHA45>` — PR 4.5 audit-debt sweep landed (13 mechanical fixes, no behavior changes).
```

---

## Apply procedure (when SHA45 is known)

1. Capture the SHA: `git log --oneline integration -1` on the integration tip after PR 4.5 merge → 7-char prefix is `<SHA45>`.
2. Substitute `<SHA45>` into Edits 1–6 above.
3. Apply all 6 edits to `/Users/ashen/.claude/plans/not-exactly-but-a-inherited-river.md` (canonical first).
4. `cp /Users/ashen/.claude/plans/not-exactly-but-a-inherited-river.md /Users/ashen/Desktop/poker_solver/PLAN.md`
5. Verify byte-identical: `diff /Users/ashen/.claude/plans/not-exactly-but-a-inherited-river.md /Users/ashen/Desktop/poker_solver/PLAN.md` → must print nothing.
6. Sanity grep: `grep -n "4.5" /Users/ashen/Desktop/poker_solver/PLAN.md` → should show §1 status + §2 row + §6 RESOLVED + §7 kickoff doc + §7 sequencing.
7. Spot-check that no stale `6c438b8` remains where it should now be `<SHA45>` (specifically the §5 pacing tip). Note: §2 PR 6 row, §6 v0.5.0 callout, §6 PR 6 risks heading, and §7 PR 6 kickoff entry intentionally keep `6c438b8` — that's PR 6's own merge SHA, not the "current tip" reference.

---

## Pre-flight drift check (before applying)

Re-verify PLAN.md hasn't been touched between recipe authorship (2026-05-22, PLAN tip `6c438b8`) and PR 4.5 landing. If PR 7 lands first or any other PR lands in between:
- Line numbers shift → re-anchor by content not line number (the Edit tool requires unique strings, which this recipe provides).
- The §1 status block and §5 pacing tip likely already changed → regenerate Edits 1 and 3 against current text.
- The §2 PR 7 row may have flipped to ✅ → adjust Edit 2's insertion anchor accordingly.

If drift detected, abort and re-author this recipe.
