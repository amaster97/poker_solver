# PLAN.md + INDEX Final Alignment Sanity Scan — 2026-05-22

**Mode:** read-only sanity scan after multiple iterative updates to both PLAN.md (canonical + local sync) and `docs/INDEX_2026-05-22.md`. Goal: confirm both still describe the same project state at integration tip `6c438b8`.

---

## 1. Diff verification (canonical PLAN ↔ local PLAN)

```
$ diff /Users/ashen/.claude/plans/not-exactly-but-a-inherited-river.md \
       /Users/ashen/Desktop/poker_solver/PLAN.md
$ echo $?
0
```

**Result:** **zero lines of diff**. The local sync is byte-identical to the canonical plan. Plan-sync rule satisfied.

---

## 2. PR trajectory accuracy (PLAN §2)

PLAN §2 table at line 79–96 lists:

| PR | Status in §2 |
|---|---|
| PR 6 | ✅ `0933367` → merged `6c438b8` (**v0.5.0 milestone**; ~24x speedup) |
| PR 7 | 🚧 3-agent fan-out launched at integration tip `6c438b8` |
| PR 8 | 📋 spec'd + prompts |

Matches the stated "PR 6 ✅, PR 7 🚧" expectation. **PASS.**

Header line 3 also states: "PR 1-6 + 3.5 + 3.5-followup landed on `integration` (tip `6c438b8`; v0.5.0 released). PR 7 (noambrown river-spot diff) currently in flight." Consistent with §2.

---

## 3. INDEX §3 readiness table ↔ PLAN §2

INDEX `docs/INDEX_2026-05-22.md` §3 table (line 150–165):

| PR | INDEX §3 | PLAN §2 | Match |
|---|---|---|---|
| PR 3 | SHIPPED `a96675c` → `351cbee` | ✅ `a96675c` on integration | ✅ (integration-tip difference is roll-forward only) |
| PR 3.5 | SHIPPED `9f91c83` → `fd0a2c7` | ✅ `9f91c83` on integration | ✅ |
| PR 3.5 followup | SHIPPED `1cbf52a` → `f67bfa3` | ✅ `1cbf52a` on integration | ✅ |
| PR 4 | SHIPPED `6565b84` → `5832b2f` | ✅ `6565b84` → merged `5832b2f` | ✅ |
| PR 5 | SHIPPED `a9d02ca` → `eee9b4b` | ✅ `a9d02ca` → merged `eee9b4b` | ✅ |
| PR 6 | SHIPPED `0933367` → `6c438b8` (v0.5.0) | ✅ `0933367` → `6c438b8` (v0.5.0) | ✅ |
| PR 7 | IN FLIGHT at `6c438b8` | 🚧 fan-out at `6c438b8` | ✅ |
| PR 8 | STAGED | 📋 spec'd | ✅ |

**All landed-PR commit hashes and integration-merge hashes match exactly. PASS.**

---

## 4. Milestone tagging (v0.5.0 / v0.5.1 / v0.6.0)

- **v0.5.0 = PR 6.** PLAN.md states "v0.5.0 milestone" on PR 6 row (§2 line 89) and dedicated §6 callout (line 230, 232). INDEX §3 row PR 6 marks "v0.5.0 milestone." **CONSISTENT.**
- **v0.5.1 = PR 7 next.** Neither PLAN.md nor INDEX explicitly assigns "v0.5.1" to PR 7. Both describe PR 7 as in-flight diff-test of PR 6 against `noambrown/poker_solver`. The semver implication (parity-test increment = patch bump) is reasonable but unrecorded.
- **v0.6.0 = PR 8 next.** Neither doc explicitly assigns "v0.6.0" to PR 8 (SIMD + cache + PCS). PLAN.md §2 line 91 lists PR 8 as "spec'd + prompts." The implication (new perf surface = minor bump) is reasonable but unrecorded.

**MINOR GAP:** prospective v0.5.1 / v0.6.0 labels are not yet stamped anywhere. Not a contradiction; just a "future label not yet set." Acceptable for current state since neither PR has landed.

---

## 5. Integration tip `6c438b8` consistency

`6c438b8` is referenced across both docs in the following contexts:

**PLAN.md:**
- Line 3: status header "tip `6c438b8`; v0.5.0 released"
- Line 89: PR 6 row "merged `6c438b8` (v0.5.0 milestone)"
- Line 90: PR 7 row "3-agent fan-out launched at integration tip `6c438b8`"
- Line 218: pacing §5 "Tip: `6c438b8`"
- Line 228, 232, 234, 261, 262: §6 + §7 callouts

**INDEX:**
- Line 157: PR 6 SHIPPED row "→ integration `6c438b8`"
- Line 158: PR 7 IN FLIGHT row "fan-out at `6c438b8`"
- Line 167: "main still at `2b67370`. Cumulative integration diff = `2b67370..6c438b8`"

All six PLAN references and three INDEX references treat `6c438b8` as both the PR 6 merge commit AND the current integration tip AND the PR 7 launch base. **Consistent across docs. PASS.**

---

## 6. Stale `v0.4.1` reference count

```
$ grep -n "v0.4.1" PLAN.md INDEX_2026-05-22.md
(no matches)
```

**Target: 0. Actual: 0. PASS.**

---

## 7. Cross-doc claim consistency (other axes)

| Claim | PLAN | INDEX | Match |
|---|---|---|---|
| `main` tip awaiting OK | "Awaiting `main` merge approval" (L3) | "`main` still at `2b67370`" (L167) | ✅ |
| Cumulative integration diff | implicit | `2b67370..6c438b8` (L167) | ✅ (no contradiction) |
| PR 4.5 audit-debt sweep status | "kickoff staged" (§7 L260) | "READY TO COMMIT" (§3 L159) | ✅ |
| Speedup claim | "~24x speedup over Python tier" | not in INDEX | non-contradictory |
| PR 6 risks resolved | listed (§6 L234-238) | not in INDEX | non-contradictory |

---

## 8. Minor framing observations (informational, not drift)

- INDEX `Generated` line 4: "post-PR-5-land, mid-PR-6-flight, with PR 7–12 fully spec'd." This was written when PR 6 was in flight; PR 6 has since landed. The §3 readiness table (line 157) correctly shows PR 6 SHIPPED, so the substance is current. The generated-header phrasing is stale but the table is authoritative.
- INDEX line 11 (TL;DR): "PR 5 landed (`eee9b4b`), PR 6 fan-out in flight." Same stale framing — superseded by §3 readiness table.
- These are surface-layer prose drift, not factual drift. The readiness table dominates and is correct.

---

## 9. Verdict

**ALIGNED.**

- PLAN canonical ↔ local: **byte-identical (0 diff lines).**
- PR 6 ✅ / PR 7 🚧: consistent across PLAN §2 and INDEX §3.
- All landed-PR commit hashes match across both docs.
- Integration tip `6c438b8` referenced 9 times with no contradictions.
- Zero stale `v0.4.1` references.
- v0.5.0 milestone tagged correctly on PR 6 in both docs.

**Minor (not blocking):**
1. INDEX generated-header + TL;DR prose still says "post-PR-5-land, mid-PR-6-flight"; superseded but harmless (§3 table is authoritative).
2. v0.5.1 / v0.6.0 prospective labels not yet stamped on PR 7 / PR 8 (deferred until land).

No material drift. Both docs accurately describe state at integration tip `6c438b8`.
