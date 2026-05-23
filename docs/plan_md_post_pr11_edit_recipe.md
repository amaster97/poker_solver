# PLAN.md edit recipe — post-PR-11 landing (v1.0.0 GA)

**Status:** RECIPE ONLY. Do NOT apply until PR 11 has merged to `integration` and the actual merge SHA is known. Recipe authored 2026-05-22 against PLAN.md tip `9f09d49`.

**Files touched (both must stay byte-identical):**
- `/Users/ashen/.claude/plans/not-exactly-but-a-inherited-river.md` (canonical)
- `/Users/ashen/Desktop/poker_solver/PLAN.md` (local mirror)

**Per the plan-sync rule:** edit canonical first, then `cp` to local. Verify with `diff` → expect empty output.

**Placeholders used below:**
- `<SHA10A>` = the 7-char merge SHA of PR 10a onto `integration` (capture after PR 10a lands).
- `<SHA11>` = the 7-char merge SHA of PR 11 onto `integration` (capture after PR 11 lands).

---

## Note on prompt-vs-reality drift

The originating prompt assumed both PR 10a and PR 11 land in this recipe's window. If PR 10a lands first (independently), Edit 1 and Edit 2's PR 10a row may have already been applied — re-anchor against then-current PLAN.md text. If PR 8, PR 9, or PR 10b also land between now and PR 11, additional table rows will have flipped to ✅ and the §5 tip SHA + §1 status block will read differently. **Always re-verify the `old_string` anchors against live PLAN.md text before applying.**

This recipe assumes the sequencing PR 10a → (PR 8 / PR 9 / PR 10b in some order) → PR 11 ends with PR 11 as the final v1.0.0 GA gate. If real sequencing diverges, the v1.0.0 callout block stays load-bearing — the rest re-anchors against actual text.

---

## Edit 1 — §1 Status block (line 3)

**Old:**
```
**Status:** PR 1-7 + 3.5 + 3.5-followup + 4.5 landed on `integration` (tip `9f09d49`; v0.5.2 released). PR 10a (UI mock-first) currently in flight. Awaiting `main` merge approval (integration → main).
```

**New:**
```
**Status:** PR 1-7 + 3.5 + 3.5-followup + 4.5 + 8 + 9 + 10a + 10b + 11 landed on `integration` (tip `<SHA11>`; **v1.0.0 GA released**). All v1-scope PRs shipped. Awaiting `main` merge approval (integration → main).
```

*(Adjust the PR list to reflect actual landed set when PR 11 merges. If PR 8/9/10b haven't all landed, drop them from the list — the v1.0.0 GA claim still holds only if PR 11 itself is the packaging GA gate as currently specified.)*

---

## Edit 2 — §2 Trajectory table

Two row flips: PR 10a (🚧 → ✅) and PR 11 (📋 → ✅). Mark v1.0.0 milestone explicitly on PR 11.

**Old (line 94):**
```
| **PR 10a** | NiceGUI scaffold + **mock solver layer** (range matrix, board input, controls, tree browser; no real engine) | 🚧 | in flight; deps: PR 3 + PR 5 data types only |
```

**New:**
```
| **PR 10a** | NiceGUI scaffold + **mock solver layer** (range matrix, board input, controls, tree browser; no real engine) | ✅ | `<SHA10A>` on integration |
```

**Old (line 96):**
```
| PR 11 | Library mode + macOS packaging (codesign + notarize + .dmg) | 📋 | spec'd + prompts |
```

**New:**
```
| **PR 11** | Library mode + macOS packaging (codesign + notarize + .dmg) | ✅ | `<SHA11>` on integration (**v1.0.0 GA milestone**) |
```

*(If PR 8/9/10b also land between now and PR 11, flip their rows similarly. Recipe leaves them as TODO anchors since their landing order is not yet decided.)*

---

## Edit 3 — §5 Pacing tip SHA (line 219)

**Old:**
```
- **Autonomous overnight mode:** `integration` branch ("pseudo-main") autonomously accumulates merged PR branches; always reflects the latest working set. Tip: `9f09d49` (PR 4.5 audit-debt sweep landed; v0.5.2).
```

**New:**
```
- **Autonomous overnight mode:** `integration` branch ("pseudo-main") autonomously accumulates merged PR branches; always reflects the latest working set. Tip: `<SHA11>` (**PR 11 landed; v1.0.0 GA milestone**).
```

---

## Edit 4 — §6 Open items: resolve PR 11 PyInstaller risk (line 250)

**Old:**
```
- **PR 11 PyInstaller + Rust `_rust.so` bundling risk** flagged in PR 11 audit prompt. **Action:** explicit `--add-binary` test step in PR 11 audit.
```

**New:**
```
- **PR 11 PyInstaller + Rust `_rust.so` bundling risk.** **RESOLVED** at `<SHA11>` / v1.0.0 — PR 11 audit confirmed `--add-binary` step packaged `_rust.so` correctly; codesign + notarize + .dmg pipeline green on cold-clone CI test.
```

---

## Edit 5 — §6 Open items: resolve I2 (PR 11 first-launch warning) (line 253)

**Old:**
```
- **I2 — PR 11 first-launch warning when abstraction artifact missing.** Small (~5-line UX edit). **Action:** defer to PR 11 implementation; documented in `autonomous_log.md` open question §5.
```

**New:**
```
- **I2 — PR 11 first-launch warning when abstraction artifact missing.** **RESOLVED** at `<SHA11>` — first-launch UX warning shipped in PR 11.
```

---

## Edit 6 — §6 Open items: resolve N5 (PR 4 §10 wheel-bundling claim) (line 254)

**Old:**
```
- **N5 — PR 4 §10 wheel-bundling claim contradicted by PR 11 packaging reality.** Small (one-line spec cleanup). **Action:** defer to PR 11 spec pass; documented in `autonomous_log.md` open question §6.
```

**New:**
```
- **N5 — PR 4 §10 wheel-bundling claim contradicted by PR 11 packaging reality.** **RESOLVED** at `<SHA11>` — PR 4 §10 spec line corrected as part of PR 11 spec pass.
```

---

## Edit 7 — §7 Kickoff docs entry (line 273)

**Old:**
```
- **`docs/pr11_prep/launch_kickoff.md`** — library mode + macOS packaging (codesign + notarize + .dmg).
```

**New:**
```
- **`docs/pr11_prep/launch_kickoff.md`** — library mode + macOS packaging (codesign + notarize + .dmg). **Shipped at `<SHA11>` / v1.0.0 GA.**
```

---

## Edit 8 — §6 NEW v1.0.0 GA milestone callout (insert above PR 6 callout, line 231)

Append a new sub-section to §6 marking the v1 GA. Insert directly under the §6 "Trajectory note" line (line 229) and above the existing "v0.5.0 milestone callout" sub-section (line 231).

**Old:**
```
Trajectory note: `eee9b4b` (PR 4 + PR 5) was the **v0.4.0 milestone** — first user-visible postflop solver + profiler beyond push/fold. **`6c438b8` (PR 6) is the v0.5.0 milestone** — Rust port of HUNL postflop with ~24x speedup over Python tier.

### v0.5.0 milestone callout
```

**New:**
```
Trajectory note: `eee9b4b` (PR 4 + PR 5) was the **v0.4.0 milestone**. `6c438b8` (PR 6) was the **v0.5.0 milestone**. **`<SHA11>` (PR 11) is the v1.0.0 GA milestone** — all v1-scope PRs shipped (HUNL postflop + preflop, both tiers, NiceGUI UI, codesigned + notarized macOS .dmg).

### v1.0.0 GA milestone callout

- **v1.0.0 GA = PR 11** (library mode + macOS packaging; codesign + notarize + .dmg). Shipped at `<SHA11>`. **All v1-scope locked decisions delivered:** HUNL postflop solver (Python + Rust tiers), HUNL preflop solver, push/fold charts (2–15 BB), EMD card abstraction, NiceGUI UI with real solver bindings, packaged + distributable macOS app. The "PioSolver-parity-on-HU-local-solving" goalpost from §1 is the v1 deliverable — measured success means a competent player can install the .dmg, run a representative postflop solve in the target wall-clock range, and inspect the strategy in the UI without touching the CLI.

### v0.5.0 milestone callout
```

---

## Edit 9 — §7 Sequencing intent (line 276)

**Old:**
```
Sequencing intent: PR 6 ✅ → PR 7 ✅ → PR 4.5 ✅ → PR 10a (in flight) + PR 8 → PR 9 → PR 10b → PR 11 → PR 12.
```

**New:**
```
Sequencing intent: **All v1-scope PRs shipped (PR 6 ✅ → PR 7 ✅ → PR 4.5 ✅ → PR 10a ✅ → PR 8 ✅ → PR 9 ✅ → PR 10b ✅ → PR 11 ✅ / v1.0.0 GA).** PR 12 (3-handed postflop stretch) remains optional post-v1.
```

*(Adjust to match actual landed set. If some PRs in the chain haven't landed yet at PR 11 time, leave them as 📋 / 🚧 — but PR 11 being a v1 GA gate generally requires PR 8/9/10b done. Audit before applying.)*

---

## Apply procedure (when SHAs are known)

1. Capture the SHAs: `git log --oneline integration -10` on the integration tip → identify PR 10a + PR 11 merge commit prefixes → `<SHA10A>` and `<SHA11>`.
2. Substitute placeholders into all 9 edits above. If PR 10a already landed previously, Edits 1 + 2 may have a stale `old_string` — re-anchor.
3. Apply all edits to `/Users/ashen/.claude/plans/not-exactly-but-a-inherited-river.md` (canonical first).
4. `cp /Users/ashen/.claude/plans/not-exactly-but-a-inherited-river.md /Users/ashen/Desktop/poker_solver/PLAN.md`
5. Verify byte-identical: `diff /Users/ashen/.claude/plans/not-exactly-but-a-inherited-river.md /Users/ashen/Desktop/poker_solver/PLAN.md` → must print nothing.
6. Sanity grep: `grep -n "v1.0.0" /Users/ashen/Desktop/poker_solver/PLAN.md` → should show §1 status, §2 PR 11 row, §5 tip, §6 GA callout (multiple lines), §7 kickoff entry, §7 sequencing.
7. Spot-check that no stale `9f09d49` remains where it should now be `<SHA11>` (specifically the §5 pacing tip + §1 status block). The §2 PR 4.5 row intentionally keeps `9f09d49` — that's PR 4.5's own merge SHA.

---

## Pre-flight drift check (before applying)

Re-verify PLAN.md hasn't been touched between recipe authorship (2026-05-22, PLAN tip `9f09d49`) and PR 11 landing. The PR 11 GA gate is the recipe's biggest dependency — if PR 8/9/10b didn't all land before PR 11, the "v1.0.0 GA" claim is premature and Edit 8's callout must be downgraded (or the recipe regenerated).

Drift symptoms to check for:
- Line numbers will have shifted from PR 8/9/10a/10b landings → re-anchor by content (Edit tool requires unique strings; this recipe provides them).
- §1 status block likely changed multiple times → regenerate Edit 1 against current text.
- §5 pacing tip likely changed to a downstream SHA → regenerate Edit 3.
- §2 PR 10a row may already be ✅ (if it landed earlier) → drop Edit 2's PR 10a portion.
- §6 carryover items may have been pruned per the continuous-pruning rule → re-anchor Edits 4/5/6 by content.

If drift detected, abort and re-author this recipe.
