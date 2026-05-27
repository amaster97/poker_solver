# Pre-Signon FAQ — 2026-05-23 → 2026-05-25

**Origin HEAD:** `60a9818` on `main` (post-PR #11 merge)
**Latest tag:** `v1.7.0` (LIVE, engine-only — no .dmg yet)
**Latest .dmg:** v1.6.0 (45 MB, arm64, attached to v1.6.0 release)
**Merged today (2026-05-25):** #2 USAGE, #3 .dmg, #4 README, #11 asymmetric fixture
**Open PRs:** #5, #6, #7, #8, #9, #10, #12, #13, #14, #15, **#57 (panic fix)**, **#58 (doc cleanup)**, **#59 (memory-profiler golden refresh)**
**Top decision:** v1.7.1 ship retry **#3** (9-PR bundle after preflight halt) + v1.8 prioritization + merge #57/#58/#59 standalone or close some

Deep-dive: `docs/WELCOME_BACK_USER_2026-05-23.md`.

---

### Q1: "What shipped while I was out?"

**A:** Nothing new shipped to origin since the prior sign-off. Origin HEAD unchanged at `3843ce7` (v1.7.0). All work routed to feature branches per the per-PR-branch rule. 5 new R6-R10 fix PRs are now open on origin and pre-bundled at `scripts/ship_v1_7_1.sh`.

Carried over (still LIVE):
- v1.6.0 (`d885bca`) — GUI Gate 2 surfaces; .dmg attached (45 MB arm64).
- v1.7.0 (`3843ce7`) — Nash range-vs-range API + CLI subcommands; engine-only.

---

### Q2: "What needs my decision?"

**Decision required.** **A:** Four items.

1. **Approve Hybrid path** — ship `v1.7.1` with all 8 PRs + acceptance reframe (Brown = sanity-check, not strict ground truth). Pre-staged at `scripts/ship_v1_7_1.sh`. **Recommended.**
2. **Path A vs B vs Hybrid** — chase more bugs (A; diminishing returns), ship-now-no-changes (B), or 8-PR bundle + reframe (Hybrid; recommended).
3. **PR 55-ext (#13)** — include in v1.7.1 bundle now or queue? **Recommended ship-now.**
4. **Brown strict mode** — deprecate entirely or keep behind `--strict` flag with warning?

Lower priority (queued AFTER v1.7.1 ships): PR #2/#3/#4 merges, Gate 4 50K-iter authorization, v1.8 NEON kernels green-light, Apple Developer Program enrollment.

---

### Q3: "What broke / what's at risk?"

**A:** Nothing broke on public origin. R6-R10 each surfaced a real defect (R6 phantom ALL_IN, R8 suit-encoding char, R9 P0/P1 convention, R10 hand-string sort) — each caught by independent diff-test before any v-NEXT release went out. All fixes now queued as PRs.

Caveats:
- **Nash perf scope limits** — `solve_range_vs_range_nash` (v1.7.0) viable for river + small turn fixtures only; flop multi-street use the aggregator. Documented at `docs/v1_7_0_nash_path_perf_profile.md`.
- **W2.3 + W3.4 persona workflows BLOCKED** — waiting on v1.8 NEON kernels.
- **Strict Brown acceptance gate empirically unclosable** — 63% cells > 1e-1 (dry-run #7) is algorithmic-not-labeling; Brown is the right gate as sanity-check, not strict ground truth.

Zero Type B regressions post-R5 reclassification.

---

### Q4: "Is v1.7.0 actually working?"

**A:** YES. v1.7.0's `solve_range_vs_range_nash` was independently verified by diff-test in R5 (max delta 0.00000000). R6-R10 each surfaced separate defects in adjacent paths (canonicalization, conventions, fixtures) — none invalidate v1.7.0's core wrapper math. The 8 PRs bundled as v1.7.1 close all known label-side defects.

---

### Q5: "What's the R6-R10 cascade and what's the Hybrid path?"

**Decision required.**

**The cascade (each caught by independent diff-test before any release):**
- **R6** — facing-all-in phantom ALL_IN bug confirmed → PR 50 (#5)
- **R7** — Brown-as-sanity-check (not strict ground truth) confirmed; framing change
- **R8** — suit-encoding char bug confirmed → PR 52 (#8)
- **R9** — P0/P1 player convention bug confirmed → PR 55 (#10) + ext (#13)
- **R10** — hand-string sort order bug confirmed → PR 56 (#12)

**The Hybrid path:** ship `v1.7.1` with:
1. All 8 open PRs squash-merged in dependency order via `scripts/ship_v1_7_1.sh`
2. Acceptance gate reframed: Brown = sanity-check (coverage + mode agreement + payoff-sign agreement), NOT strict numerical ground truth (Brown's `base_pot × P_win` divergence from our zero-sum is unfixable without 3-6 wk stabilization)
3. Tag v1.7.1, push to origin/main, GitHub release notes carry the reframe

**Why Hybrid over Path A (chase more bugs)?** Dry-run #7 confirmed residual divergence is algorithmic-not-labeling. R11+ would hunt for label-side bugs that aren't there. Diminishing returns.

**Why Hybrid over Path B (ship now exactly as-is)?** Leaves R6-R10 fixes unshipped. Each is a real defect.

**Recommendation: APPROVE Hybrid.**

---

### Q6: "Why are there 8 open PRs?"

**A:** R6-R10 each surfaced a real bug, each gating PR routed to its own feature branch per the per-PR-branch rule. Plus the 3 carried-over PRs (#2 USAGE, #3 .dmg, #4 README) from the prior session.

- **#2** `pr-48-usage-v1-7-0-semantics` — USAGE.md §5.6 (LOW risk)
- **#3** `pr-44-dmg-packaging-fix` — nicegui bundle + arm64 (MED risk)
- **#4** `pr-49-readme-broken-ref-cleanup` — broken-link cleanup (LOW risk)
- **#5** `pr-50-facing-allin-phantom` — R6 (MED risk)
- **#6** `pr-51-...` — bundle line item (LOW risk)
- **#7** `pr-53-...` — bundle line item (LOW risk)
- **#8** `pr-52-suit-encoding-char` — R8 (MED risk)
- **#9** `pr-54-...` — bundle line item (LOW risk)
- **#10** `pr-55-p0-p1-convention` — R9 (MED risk)
- **#11** `pr-asymmetric-fixture` — bundle line item (LOW risk)
- **#12** `pr-56-hand-string-sort` — R10 (MED risk)
- **#13** `pr-55-ext` — R9 ext / companion to #10 (LOW risk)

All MERGEABLE+CLEAN. Triage notes: `docs/PR_REVIEW_PREP_2026-05-23.md`.

---

### Q7: "What's left to do?"

**A:**
1. Approve Hybrid path → `bash scripts/ship_v1_7_1.sh` (ships v1.7.1 with all 8 PRs + acceptance reframe).
2. Decide Brown strict-mode disposition (deprecate / behind --strict flag).
3. Land carried-over trio (PR #2/#3/#4) — can interleave with v1.7.1 or follow.
4. Authorize Gate 4 50K-iter validation run (~2.5 hr; queued after v1.7.1).
5. Decide on v1.8 NEON kernels (HIGH priority, ~1-2 weeks dev; queued after v1.7.1).
6. v1.7.x .dmg rebuild after PR #3 merges.
7. Apple Developer Program enrollment ($99/yr) for notarized .dmg.

After Hybrid ship + Gate 4 + v-final .dmg: burst close per PLAN.md §10.

---

### Q8: "Can I just merge everything in?"

**A:** Recommended path is to ship the 8-PR v1.7.1 bundle via `scripts/ship_v1_7_1.sh` (handles ordering, including PR #13 depends on #10). The carried-over trio (PR #2/#3/#4) is independent and can ship alongside or after:

```bash
bash scripts/ship_v1_7_1.sh   # all 8 R6-R10 bundle PRs + tag + push (after explicit OK)

# then, independently:
gh pr merge 4 --repo amaster97/poker_solver --squash
gh pr merge 2 --repo amaster97/poker_solver --squash
gh pr merge 3 --repo amaster97/poker_solver --squash   # after rebuild verification log
```

**Do NOT auto-fire `ship_v1_7_1.sh`** — it's pre-staged but requires explicit OK first (tags + pushes to origin).

---

### Q11: "What's R11 and what's the resolution?"

**A:** **R11 RESOLVED as test-side double-swap; kernel verified correct.** Initially framed as a REAL engine-level disagreement at depth-0 root (dry-run #8 surfaced AA/TT/88 60-75pp divergence with identical action menus). **That framing was REFUTED.**

**Root cause:** PR 40 (test-side range slot swap) and PR 55-ext (wrapper-side range swap) each independently and correctly applied one convention swap. Each PR passed its own diff-test in isolation against the unswapped baseline. Stacked together they NET-SWAP ranges — same outcome as no swap at all. Dry-run #8's depth-0 60-75pp divergence WAS the unswapped-range signature, but tunnel vision (each swap had its own test-PASS) made the engine the most plausible remaining suspect.

**Kernel verified correct multiple ways:**
1. AA-vs-AA minimal fixture with identical ranges + menus + stack/blinds → matches Brown at FP precision.
2. `dcfr_vector.rs` semantic re-audit → no semantic bug.
3. 3 independent investigations (bisect / AA depth-0 trace / AA-vs-AA fixture) converged on the double-swap diagnosis.

**Final bundle: 7 PRs** (PR 50 + 51 + 52 + 54 + 55 + 56 + **PR 53c**). PR 55-ext (#13) EXCLUDED (close without merging). PR 53/53b SUPERSEDED by PR 53c.

**v1.7.1 ship pre-staged** at `scripts/ship_v1_7_1.sh` (finalized with 7-PR bundle); awaiting your OK + dry-run #10 PASS.

**How R11 was caught:** PR 53c's Layer 2 (shallow-strict, loosened gate) caught the depth-0 disagreement in dry-run #8 — without Layer 2, the unswapped-range signature would have shipped looking like deep-cap noise in dry-run #7's aggregate metric (100% coverage / 63% cells > 1e-1). Layer 2 is still load-bearing.

**HONEST FRAMING:** Both the 03:48 SESSION-CLOSE declaration AND the subsequent "engine bug" framing were wrong. The session-close was premature; the engine-bug framing was tunnel vision. Codified as `feedback_redundant_swap_hazard.md` (NEW). 11 reversals total; honest framing throughout.

**Recommendation:** APPROVE Hybrid path on 7-PR bundle + PR 53c gate loosening; bash `scripts/ship_v1_7_1.sh` after dry-run #10 PASS.

See: `docs/STATUS_2026-05-24_r11_resolved.md` (supersedes `_r11_engine_bug.md`).

---

### Q13: "What does the matched-config investigation say?"

**A:** **VERDICT C — Nash multiplicity, not action menu.**

Forcing our solver to use Brown's exact action menu (matched-config experiment) gives **BIT-IDENTICAL** results to our default menu. So the action menu was **not** the divergence source. The residual disagreement at deep-cap is **Nash multiplicity** — mathematically allowed: both solvers are at ~0.06 chips exploitability, which is essentially Nash. Two different Nash equilibria can both be correct (Nash sets are not singletons in zero-sum games with this structure).

**Why this matters:** R7's framing (Brown = sanity-check, not strict numerical ground truth) is now **empirically backed**, not hand-wave. The Brown-comparison question is **closed**. No further investigation needed.

**What this rules out:**
- Action menu mismatch (was the leading remaining suspect).
- A latent engine bug at deep-cap (kernel verified correct in multiple ways from R11 work).

**What it confirms:**
- Both our solver and Brown's reach valid Nash equilibria.
- Deep-cap exploitability ~0.06 chips on both sides = essentially Nash.
- PR 53c's gate loosening is the right call (algorithmic-not-labeling residual = Nash-multiplicity-not-bug).

**Next:** ship v1.7.1 with the reframed acceptance gate. Don't re-open this question without a new empirical signal.

---

### Q15: "Why didn't v1.7.1 ship overnight?"

**A:** Agent execution timeout during the cargo test phase (~30-45 min runs are above the per-spawn limit). Ship script is correct; just needs manual invoke from your terminal. 4 retries all died at the same point in the test suite; nothing failed, processes were just killed.

**The fix — invoke from YOUR terminal** (no agent timeout in your shell session):

```bash
cd /Users/ashen/Desktop/poker_solver
bash scripts/ship_v1_7_1.sh 2>&1 | tee /tmp/v1.7.1_ship_manual.log
```

Wall-clock ~30-45 min. When complete: v1.7.1 tag + GitHub release. `set -e` halts cleanly on any error; no force-push, no tag created until smoke matrix passes.

---

### Q14: "What are PR #57, PR #58, and PR #59?"

**A:** Three standalone PRs opened today (2026-05-25), none gated on v1.7.1:

- **PR #57** (#16 on GitHub) — `dcfr_vector.rs:363` panic fix. Small Rust bug fix; standalone; no ordering dependency.
- **PR #58** (#17 on GitHub) — CHANGELOG L28 + USAGE broken-link cleanup. Doc hygiene; standalone.
- **PR #59** — memory-profiler golden refresh. Standalone.

**Decision pending:** merge all three standalone post-ship OR close some. None blocks v1.7.1.

---

### Q12: "What's PR 53c?"

**A:** PR 53c is the final variant of the PR 53 family, superseding both PR 53 (#7) and PR 53b (#14). It loosens PR 53's Layer 2 (shallow-strict) acceptance gate to accommodate the algorithmic-not-labeling residual confirmed by dry-run #7 (63% cells > 1e-1 vs Brown is algorithmic, NOT labeling).

**Why the loosening matters:**
- PR 53's original Layer 2 gate was tuned against an assumed-strict Brown ground truth.
- Post-R7 reframe: Brown is a sanity-check, not strict numerical ground truth (Brown's `base_pot × P_win` divergence from our zero-sum is unfixable without 3-6 wk stabilization).
- PR 53c keeps the load-bearing Layer 2 mechanism (shallow-strict catches what aggregate metrics hide — exactly how R11 was found in dry-run #8) but adjusts the threshold to match the reframed acceptance gate.
- Without PR 53c's loosening, the bundle would PASS the structural checks but FAIL the strict numerical layer — which is exactly the algorithmic-not-labeling gap that R7 said is the right behavior.

**Net effect:** PR 53c retains the bug-catching value of Layer 2 (caught R11 / the double-swap) while preventing false-fail on the known algorithmic residual.

**In the 7-PR bundle:** PR 53c replaces PR 53 (#7) and PR 53b (#14). PR 53 had a 4-hunk conflict with PR 54 (#9); PR 53b resolved that conflict but kept the original strict gate; PR 53c is PR 53b + the gate loosening.

**Recommended action:** APPROVE PR 53c as part of the 7-PR bundle. Close PR 53 (#7) and PR 53b (#14) without merging after PR 53c lands.

---

## Memory rules to know

- **`feedback_independent_verification.md`** (codified post-R5) — held across R6-R10; every reversal caught by diff-test before v-NEXT.
- **`feedback_post_ship_persona_retest.md`** — diff-test BEFORE concluding code bug.
- **`feedback_label_vs_semantics.md`** — verify function/test names against semantics; R6-R10 mostly traced to label-trust at boundaries.

MEMORY.md under cliff. PLAN.md under budget.

---

## State at a glance (2026-05-25)

| Item | Status |
|---|---|
| Origin HEAD | `60a9818` (post-PR #11 merge) |
| Latest tag | v1.7.0 (LIVE) |
| Latest .dmg | v1.6.0 (45 MB, arm64) |
| Merged today | #2 USAGE, #3 .dmg, #4 README, #11 asymmetric fixture |
| Open PRs | #5/#6/#7/#8/#9/#10/#12/#13/#14/#15 + **#57** + **#58** + **#59**; bundle uses **9** (PR 53b re-added as dep + PR 59 added for golden refresh) |
| Bundle | PR 50 + 51 + 52 + 54 + 55 + 56 + **53b** + 53c + **59 (memory-profiler golden refresh)** (PR 55-ext EXCLUDED; PR 53 SUPERSEDED) |
| v1.7.1 ship script | HALTED on preflight (bundle composition); ship retry **#3** in flight with 9-PR bundle |
| Awaiting decisions | (1) v1.8 priority green-light; (2) merge #57/#58/#59 standalone or close some |
| Matched-config | **Verdict C** — menu wasn't divergence source; Nash multiplicity is (R7 empirically backed) |
| v1.8 decision brief | Ready at `docs/v1_8_decision_brief.md` — HIGH priority recommended |
| Reversals R1-R11 | R11 **RESOLVED test-side**; engine correct |
| Gate 4 50K | PASS on reduced fixtures; full fixture architecturally blocked by chance-enum-at-root |
| Persona PASS | 12 / 18 (zero Type B regressions) |
| Standalone PRs | #57 (#16 — panic fix) + #58 (#17 — doc cleanup) + #59 (memory-profiler golden refresh) — decide: merge standalone or close some |
| Working tree | clean |
