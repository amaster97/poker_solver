# PLAN.md + autonomous_log.md — Final Consistency Sweep

**Date:** 2026-05-22
**Trigger:** end-of-session consistency check before extended idle
**Scope:** verify PLAN.md (canonical + local) and autonomous_log.md are still load-bearing-accurate after a long autonomous session
**Constraint:** read-only — flag only, no edits

---

## 1. PLAN.md sync (canonical ↔ local)

**Result: CLEAN.**

```
$ diff /Users/ashen/.claude/plans/not-exactly-but-a-inherited-river.md \
       /Users/ashen/Desktop/poker_solver/PLAN.md
FILES IDENTICAL
```

Zero-line diff. The plan-sync rule (`feedback_plan_sync.md`) is being honored. Both files: 290 lines, byte-identical.

---

## 2. PLAN.md trajectory table accuracy (§2)

Cross-referenced against `git log --oneline integration -10` and `git rev-parse main`:

| Row in §2 table | Status claim | Git reality | Verdict |
|---|---|---|---|
| PR 1 (Kuhn + DCFR) | ✅ `9d2d66a` on main | on main, pre-`2b67370` | OK (predates main tip; consistent with §9 first-PR entry) |
| PR 2 (Leduc) | ✅ `17c9756` on main | on main, pre-`2b67370` | OK |
| PR 3 (HUNL tree) | ✅ `a96675c` on integration | exact match in `git log` | OK |
| PR 3.5 (push/fold) | ✅ `9f91c83` on integration | exact match | OK |
| PR 3.5-followup | ✅ `1cbf52a` on integration | exact match | OK |
| PR 4 (card abstraction) | ✅ `6565b84` → merged `5832b2f` | exact match | OK |
| PR 5 (HUNL postflop) | ✅ `a9d02ca` → merged `eee9b4b` | exact match | OK |
| PR 6 (Rust port) | 🚧 launched at `eee9b4b` | branch `pr-6-rust-hunl-port` checked out | OK |
| PR 7–12 | 📋 / 📝 spec'd | n/a | OK |

**Integration tip:** PLAN claims `eee9b4b`; `git log -1 integration` confirms `eee9b4b`. **MATCH.**
**Main tip:** PLAN does NOT explicitly carry "main = 2b67370" line, but autonomous_log line 17 does, and `git rev-parse main` returns `2b67370904d106d6e600a84ccb06c3249cd3c964`. **MATCH.**

### v0.4.0 referenced where appropriate? — STALENESS FLAG #1

`grep "v0\.4\.0"` against PLAN.md and autonomous_log.md returns **zero matches.** Only `v0.3` exists (PR 3.5 "v0.3 capstone" mention in autonomous_log line 16). No v0.4.0 tag exists in git either (`git tag --list "v*"` returns empty).

If v0.4.0 was intended as a milestone label for the post-PR-5 integration tip (which would be natural — PR 5 shipped the postflop solver + memory profiler, the first user-visible feature beyond push/fold), it is **not yet recorded** in either doc. **Flag only — not necessarily a doc bug; may simply be a milestone not yet declared.**

---

## 3. PLAN.md §6 Open items

Current list (5 entries):
1. PR 5 TURN abstraction coverage gap (6 skipped tests)
2. PR 4 kmeans homogeneity test loosened (95→50%)
3. PR 11 PyInstaller bundling risk
4. Audit follow-up backlog (PR 3/3.5/4/5) → PR 4.5 sweep
5. `origin/equity-precision` dangling branch

### Health check

- **PR 5 must-fix (S13 false-alarm)** — correctly NOT in §6. Removed/never-added properly. Good.
- **PR 6-specific risks (HashMap iter nondeterminism, etc.)** — STALENESS FLAG #2: PR 6 is currently in flight, but §6 lists no PR-6-specific risks. Determinism (HashMap iter order, Vec ordering, thread scheduling in any concurrent port code) is a well-known Rust-port gotcha that would have made a natural §6 entry. If S17 (PR 6 prompt patches) covered this in `pr6_prep/MUST_PATCH_BEFORE_LAUNCH.md` then §6 is fine; otherwise the risk is undocumented at plan level.
- Entries 1–5 all look current and correctly attributed to an action + owner PR.

---

## 4. autonomous_log.md S-series status

S-entries S1 through S20 all have explicit status tags (LANDED / ACTIVE POLICY / FALSE ALARM / LANDED + RULE CODIFIED). **No status-less entries.** S8/S9 are explicitly marked "unused / reserved" with rationale. Good.

D-series: D1, D2, D3 all RESOLVED with outcomes.

### S21+ — STALENESS FLAG #3

PR 6 launch is described in **S17** ("PR 6 fan-out launched at integration tip `eee9b4b`"), bundled with the PR 6 / PR 7 prompt patches. No standalone S21 entry yet for PR 6 commit work — appropriate, since PR 6 has not landed. **Once PR 6 ships, a new S21 (or whatever the next free slot is) should record:** Rust-port commit SHA + integration merge SHA + which TURN/kmeans open-items it resolved + any new should-fix items.

This is a forward-looking flag, not a current doc bug. The log is internally consistent through "current state."

---

## 5. Drift between PLAN.md and autonomous_log.md

Cross-checked decisions logged in autonomous_log that should also appear in PLAN.md:

| autonomous_log entry | PLAN.md reflection | Drift? |
|---|---|---|
| S4 (integration branch policy) | §5 Pacing — "Autonomous overnight mode … Tip: eee9b4b" | NO |
| S6 (rebase on equity-hybrid main) | §9 implicit (main = `2b67370`) | minor — not called out explicitly in §9, but §9 archive isn't expected to log every rebase |
| S7 (spec consistency I2 + N5 deferred) | §6 does NOT carry I2/N5 as open items | STALENESS FLAG #4 — see below |
| S10 (PR 3.5 §4 spec amendment) | implicit in §1 (push/fold spec) | NO (substantive change baked into the locked-decisions text) |
| S11 (PR 4 homogeneity loosened) | §6 entry #2 | NO — match |
| S15 (9 kickoff docs staged) | §7 Kickoff docs staged | NO — match |
| S16 (PR 10a UI locks) | not in PLAN; lives in `pr10a_spec.md` only | OK — spec-detail, not plan-level |
| S18 (pytest-timeout markers) | §4 — "Per-test wall-clock timeout: 90s default" | NO — match |
| S19 (memory rules → 14) | not in PLAN | OK — orchestrator-internal |
| S20 (PR 10 split into 10a/10b) | §2 + §9 archive entry | NO — match |
| **Open questions §1 (main merge)** | PLAN.md line 3 status ("Awaiting main merge approval") | NO — match |
| **Open questions §2 (Q3 coin-flip)** | not in PLAN §6 | minor — UI-spec-level, fine |
| **Open questions §3 (delete `equity-precision`)** | §6 entry #5 | NO — match |
| **Open questions §7 (TURN coverage gap)** | §6 entry #1 | NO — match |
| **Open questions §9 (no full HUNL solve yet)** | not flagged in PLAN | STALENESS FLAG #5 — see below |

### Staleness flag #4 — I2 and N5 deferrals

S7 ends with: "I2 (PR 11 first-launch abstraction warning) and N5 (PR 4 §10 bundling note) **deferred** — flagged in §'Open questions' below." `autonomous_log.md` Open questions §5 + §6 list these. **PLAN.md §6 does not.** These are small (one-line edits each pre-PR-11), but they should be in §6 for parity. The autonomous_log is more current than the plan on these two items.

### Staleness flag #5 — "no full HUNL solve has been performed end-to-end yet"

Open questions §9 of autonomous_log carries the load-bearing caveat: "First real production-scale solve happens in PR 6 (~10 hr wall-clock)." This is a major caveat for anyone reading PLAN.md and assuming PR 4–5 already passed at production scale. PLAN.md §1's "Empirical commitment: PR 5 ships a per-street memory profiler. Once measured, PR 4's abstraction can be revisited based on actual GB per layer." hints at it but does not say outright "we have not actually measured at 200K-iter production scale yet." A reader of PLAN.md alone could over-trust the ✅ on PR 4 + PR 5.

---

## 6. Summary verdict

**PLAN.md sync:** CLEAN (zero-line diff).
**PLAN.md trajectory table:** ACCURATE (all SHAs match git, integration tip + main tip correct).
**PLAN.md §6:** LARGELY CURRENT but has two minor gaps (I2 + N5 deferrals from S7; no PR-6-specific risk entries).
**autonomous_log.md:** INTERNALLY CONSISTENT, all S/D entries have status, no orphan items.
**PLAN ↔ log drift:** MINOR. 5 staleness flags total, all small. No contradictions, only PLAN.md slightly trailing the log on a few items.

**Overall trajectory-doc health: HEALTHY.** Not "needs cleanup" — the gaps are tracker-grade, not load-bearing-accuracy-grade. Safe to enter the next PR-6-completion review wave without doc work first.

### Recommended (NOT done — read-only sweep)

1. When PR 6 lands → add S21 to autonomous_log with commit + merge SHAs; update §2 trajectory PR 6 row to ✅ with SHAs; refresh integration tip line.
2. When PR 6 lands → reconsider whether v0.4.0 tag is warranted (post-postflop, pre-Rust-perf milestone candidate).
3. Optional small edit to PLAN.md §6: add bullet "I2 + N5 deferred spec edits — apply before PR 11 implementation" for parity with autonomous_log open questions §5–6.
4. Optional small edit to PLAN.md §1 (Empirical commitment line) or §6: explicit caveat that no production-scale 200K-iter run has been executed end-to-end yet.
5. Optional PR-6-specific risk entry in §6 (HashMap iter determinism, thread-scheduling determinism on the Rust port).
