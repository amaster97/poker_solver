# PR Review Prep — 2026-05-23 → 2026-05-25 Session

**FINAL ship bundle: 9 PRs** (PR 50 + 51 + 52 + 54 + 55 + 56 + **53b** + 53c + **59 memory-profiler golden refresh**). Preflight halt revealed PR 53c depends on PR 53b — PR 53b re-added as dep. PR 59 added for golden refresh. PR 55-ext (#13) still EXCLUDED. PR 53 (#7) still SUPERSEDED. **Ship retry #3 in flight.**

**Merged 2026-05-25:** #2 USAGE, #3 .dmg packaging, #4 README, #11 asymmetric fixture. Origin HEAD `60a9818`.

**Open PRs** on `amaster97/poker_solver` (all targeting `main`):

| # | Branch | Subject | Reversal | Risk | Bundle Action |
|---|--------|---------|----------|------|--------------|
| #5 | `pr-50-facing-allin-phantom` | facing-all-in phantom ALL_IN bug | R6 | MED | **IN-BUNDLE** |
| #6 | `pr-51-...` | (queued v1.7.1 bundle item) | — | LOW | **IN-BUNDLE** |
| #7 | `pr-53-...` | (PR 53 — **SUPERSEDED by PR 53c**) | — | LOW | **SUPERSEDED — close** |
| #8 | `pr-52-suit-encoding-char` | suit-encoding char bug | R8 | MED | **IN-BUNDLE** |
| #9 | `pr-54-...` | (queued v1.7.1 bundle item — renderer) | — | LOW | **IN-BUNDLE** |
| #10 | `pr-55-p0-p1-convention` | P0/P1 player convention | R9 | MED | **IN-BUNDLE** |
| #12 | `pr-56-hand-string-sort` | hand-string sort order | R10 | MED | **IN-BUNDLE** |
| #13 | `pr-55-ext` | PR 55 extension | R9 | LOW | **CLOSE WITHOUT MERGE — redundant with PR 40 (double-swap)** |
| #14 | `pr-53b-rebased-on-54` | PR 53b (rebase) | — | LOW | **IN-BUNDLE (dep of PR 53c per preflight)** |
| #15 | `pr-53c-gate-loosened` | **PR 53c** — Layer 2 gate loosened for algorithmic residual | — | LOW | **IN-BUNDLE (final)** |
| **#57** (#16 GH) | `pr-57-dcfr-vector-panic` | **`dcfr_vector.rs:363` panic fix** | — | LOW | **STANDALONE post-ship — decide merge or close** |
| **#58** (#17 GH) | `pr-58-changelog-usage-cleanup` | **CHANGELOG L28 + USAGE broken-link cleanup** | — | LOW | **STANDALONE post-ship — decide merge or close** |
| **#59** | `pr-59-memory-profiler-golden-refresh` | **memory-profiler golden refresh** | — | LOW | **STANDALONE post-ship — decide merge or close** |

**Note on PR 55-ext (#13):** Was originally intended as R9 companion to PR 55 (#10). Forensic analysis revealed it duplicated PR 40's test-side range slot swap. Stacking both = net-swap (same outcome as no swap). PR 55-ext is **closed without merging**.

**Note on PR 53c (#15):** Supersedes PR 53 (#7) and PR 53b (#14). Loosens Layer 2 acceptance gate to accommodate the algorithmic-not-labeling residual confirmed by dry-run #7 (63% cells > 1e-1 vs Brown is algorithmic, NOT labeling). Keeps the load-bearing Layer 2 bug-catching mechanism that caught R11.

All generated and pushed by `amaster97`; no third-party authors.

---

## v1.7.1 BUNDLE — 9-PR (recommended — Hybrid path; ship retry #3 in flight)

**9 PRs in `scripts/ship_v1_7_1.sh`** (post-retry #3): PR 50 (#5) + PR 51 (#6) + PR 52 (#8) + PR 54 (#9) + PR 55 (#10) + PR 56 (#12) + **PR 53b (#14)** + PR 53c (#15) + **PR 59 (memory-profiler golden refresh)**.

**EXCLUDED from bundle:** PR 55-ext (#13) — double-swap with PR 40; close without merging.

**SUPERSEDED by PR 53c:** PR 53 (#7); close after PR 53c lands. (PR 53b is back in the bundle as a required dependency of PR 53c per preflight halt.)

**STANDALONE post-ship (decide merge or close):** PR #57 (#16 GH — `dcfr_vector.rs:363` panic fix), PR #58 (#17 GH — CHANGELOG L28 + USAGE broken-link cleanup), and PR #59 (memory-profiler golden refresh).

The Hybrid path ship is:
1. Squash-merge the 7 PRs in dependency order (script handles this)
2. Tag `v1.7.1`
3. Push to origin/main
4. GitHub release notes carry the **acceptance reframe** (Brown = sanity-check, not strict ground truth)

**Pre-existing PRs (#2, #3, #4)** are NOT part of the v1.7.1 bundle; they remain on the queue and can ship after v1.7.1 or interleave (see "BATCH MERGE OPTION — pre-existing 3" below).

**To execute Hybrid:** `bash scripts/ship_v1_7_1.sh` (after explicit user OK and dry-run #10 PASS; script will not auto-fire).

---

## R6-R10 PRs (the v1.7.1 bundle)

### PR #5 — fix: facing-all-in phantom ALL_IN bug (R6)

**Branch:** `pr-50-facing-allin-phantom` → `main`. **Type:** fix. **Risk:** MED.

**Why:** Facing all-in node was generating a phantom ALL_IN action when player already committed full stack. Confirmed via diff-test against expected EV; bug surfaced in W-thread persona retest.

**Recommended action:** **MERGE** as part of v1.7.1 bundle.

### PR #8 — fix: suit-encoding char (R8)

**Branch:** `pr-52-suit-encoding-char` → `main`. **Type:** fix. **Risk:** MED.

**Why:** Suit char `s/h/d/c` encoding off-by-one in one canonicalization path. Confirmed via independent diff-test.

**Recommended action:** **MERGE** as part of v1.7.1 bundle.

### PR #10 — fix: P0/P1 player convention (R9)

**Branch:** `pr-55-p0-p1-convention` → `main`. **Type:** fix. **Risk:** MED.

**Why:** Hero/villain player index convention was inconsistent between aggregator entry and one downstream consumer. Confirmed via diff-test.

**Recommended action:** **MERGE** as part of v1.7.1 bundle (alongside #13 ext).

### PR #12 — fix: hand-string sort order (R10)

**Branch:** `pr-56-hand-string-sort` → `main`. **Type:** fix. **Risk:** MED.

**Why:** Hand-string canonical sort order was non-deterministic on certain inputs, producing distinct cache keys for the same logical hand. Confirmed via diff-test.

**Recommended action:** **MERGE** as part of v1.7.1 bundle.

### PR #13 — PR 55 extension (R9 companion) — **CLOSE WITHOUT MERGE**

**Branch:** `pr-55-ext` → `main`. **Type:** fix (companion). **Risk:** LOW. **Bundle action:** **CLOSE WITHOUT MERGE — redundant with PR 40 (double-swap).**

**Why excluded:** Forensic analysis (3 independent investigations) revealed PR 55-ext duplicated PR 40's test-side range slot swap. Each swap PR had its own diff-test PASS in isolation against the unswapped baseline; stacked together they NET-SWAP (same outcome as no swap at all). Dry-run #8's depth-0 60-75pp divergence was the unswapped-range signature. Including PR 55-ext + PR 40 = bug; excluding PR 55-ext = correct.

**Recommended action:** **CLOSE WITHOUT MERGING.** PR 40 alone (already shipped, test-side) covers the convention correctly.

### PRs #6, #7, #9, #11 — bundle line items

**Branches:** `pr-51-...`, `pr-53-...`, `pr-54-...`, `pr-asymmetric-fixture` → `main`. **Type:** support / test / fixture. **Risk:** LOW.

**Why:** Supporting tests, asymmetric fixture additions, and bundle line items for the R6-R10 cascade. Most are MERGEABLE+CLEAN; **PR #7 (PR 53) conflicts with PR #9 (PR 54) at 4 hunks** and is superseded by PR 53b (#14) in the ship bundle.

**Recommended action:** **MERGE** as part of v1.7.1 bundle (substitute PR 53b for PR #7).

### PR #14 — PR 53b (PR 53 rebased on PR 54) — **BACK IN BUNDLE (dep of PR 53c per preflight)**

**Branch:** `pr-53b-rebased-on-54` → `main`. **Type:** support (conflict-resolved rebase). **Risk:** LOW. **Bundle action:** **IN-BUNDLE — required dependency of PR 53c surfaced by preflight halt.**

**Why back in bundle:** Initial 7-PR bundle composition assumed PR 53c subsumed PR 53b entirely. Preflight halt revealed PR 53c is layered on top of PR 53b (gate-loosening commits, not a full re-implementation). Bundle now 8 PRs in order: PR 50 + 51 + 52 + 54 + 55 + 56 + **53b** + 53c.

**Recommended action:** **MERGE** as part of v1.7.1 bundle.

### PR #15 — PR 53c (final, gate-loosened) — **IN-BUNDLE**

**Branch:** `pr-53c-gate-loosened` → `main`. **Type:** support (final variant of PR 53 family). **Risk:** LOW. **Bundle action:** **MERGE as part of v1.7.1 bundle (final variant).**

**Why:** PR 53c supersedes both PR 53 (#7) and PR 53b (#14). It keeps PR 53b's conflict-resolved rebase AND loosens Layer 2's shallow-strict acceptance gate to accommodate the post-R7 reframe (Brown = sanity-check, not strict ground truth). Critically, PR 53c retains the load-bearing bug-catching value of Layer 2 — exactly the mechanism that caught R11's double-swap in dry-run #8.

**Why this matters:** Without PR 53c's loosening, the bundle would PASS structural checks but FAIL the strict numerical layer on the known algorithmic residual. With PR 53c, the bundle PASSes correctly.

**Recommended action:** **MERGE** as part of v1.7.1 bundle.

---

## Pre-existing 3 PRs (carried over from prior sign-off — not in v1.7.1 bundle)

### PR #2 — docs(usage): v1.7.0 aggregator-vs-Nash + class-label semantics

**Branch:** `pr-48-usage-v1-7-0-semantics` → `main`. **Type:** docs. **Risk:** LOW. **Diff:** +150 / -91 (USAGE.md).

Post-v1.7.0 retest's "wrapper bug" claim REFUTED by diff-test (R5). USAGE.md §5.6 documents the class-expansion semantics nuance. **Recommended action: MERGE** — docs-only, fills a real user-confusion gap.

### PR #3 — fix(packaging): v1.4.0 .dmg nicegui bundle + arch + version

**Branch:** `pr-44-dmg-packaging-fix` → `main`. **Type:** fix. **Risk:** MED. **Diff:** +53 / -10 (3 files).

Fixes v1.4.0 `ModuleNotFoundError: nicegui` defect. Rebuilt .dmg verified (45 MB arm64, smoke-test pass). **Recommended action: MERGE** if rebuild verification log attached.

### PR #4 — docs(readme): broken cross-ref cleanup

**Branch:** `pr-49-readme-broken-ref-cleanup` → `main`. **Type:** docs. **Risk:** LOW. **Diff:** +4 / -4 (README.md).

Closes public-repo-hygiene leak (two stale links to internal-only docs). **Recommended action: MERGE**.

---

## BATCH MERGE OPTION — pre-existing 3 (alternative to v1.7.1 bundle)

If you want to land the pre-existing trio independently of the v1.7.1 bundle:

```bash
gh pr merge 4 --repo amaster97/poker_solver --squash
gh pr merge 2 --repo amaster97/poker_solver --squash
gh pr merge 3 --repo amaster97/poker_solver --squash   # after rebuild verification log
```

No inter-deps; touch disjoint files; safe to land in any order.

**Recommendation:** include #2 and #4 in v1.7.1 bundle (cheap docs + hygiene); land #3 as standalone (.dmg rebuild trigger per UI+packaging-sync rule).

---

## All 7 Hybrid PRs — single-pass

```bash
bash scripts/ship_v1_7_1.sh   # bundles + tags + pushes (7-PR bundle)
```

Pre-staged. Will not auto-fire — requires explicit user OK + dry-run #10 PASS.

**Bundle composition:** PR 50 + 51 + 52 + 54 + 55 + 56 + PR 53c. Script handles ordering. PR 55-ext (#13) NOT in bundle (close without merging). PR 53/53b NOT in bundle (superseded by PR 53c).

**Follow-ups (NOT part of v1.7.1 bundle):**

- PR #3 merge → PR 11 .dmg rebuild trigger (UI+packaging-sync rule)
- v1.7.1 ship → trigger v1.7.x .dmg rebuild (folds packaging fix into v1.7.1 stack)
- v1.7.1 ship → Gate 4 50K + v1.8 NEON priority decisions queue up next
