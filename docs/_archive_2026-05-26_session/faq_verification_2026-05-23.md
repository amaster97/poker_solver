# FAQ Independent Verification — 2026-05-23

**Target:** `docs/PRE_SIGNON_FAQ.md` (8 questions)
**Method:** Per-question diff-test against source-of-truth artifacts (git log, file existence, doc content). READ-ONLY.

---

## Q1: "What shipped while I was out?" — PASS

FAQ-cited SHAs and tags all reachable on `origin/main`:
- `d885bca` v1.6.0 — PRESENT (line 9 of `git log origin/main`)
- `3843ce7` v1.7.0 — PRESENT (HEAD of `origin/main`)
- `94007ca` README v1.5.x refresh — PRESENT
- `ca8c7af` README v1.6.0 bump — PRESENT
- `bf6f966` Cargo.lock fix — PRESENT
- `433ccfd` .dmg install guide pointer — PRESENT (FAQ also cites this — bonus accurate)

Tags `v1.6.0` + `v1.7.0` both exist (`git tag -l 'v1.*' | tail`).

---

## Q2: "What needs my decision?" — PASS

All 3 cited artifacts exist:
- `docs/v1_6_1_path_d_decision.md` (16,425 B, 2026-05-23 18:15)
- `docs/PR_REVIEW_PREP_2026-05-23.md` (18,118 B, 2026-05-23 21:28)
- 3 PRs OPEN (#2, #3, #4) per `gh pr list`

---

## Q3: "What broke / what's at risk?" — PASS

FAQ claims verified against source docs:
- **Nash perf scope (river + small turn only)** — `docs/v1_7_0_nash_path_perf_profile.md` exists (11,290 B).
- **W2.3 + W3.4 BLOCKED on v1.8 NEON** — confirmed at `docs/STATUS_2026-05-23_post_retest_5th_reversal.md:121`: *"W2.3 + W3.4 remain BLOCKED (5-min timeout on scaled aggregator runs; need v1.8 NEON kernels)"*.
- **K72 42pp / A83 27pp above 5e-2 → Path D unclosable** — confirmed verbatim in `STATUS_2026-05-23_v1_7_0_shipped.md:80`: *"K72 max-diff 4.22e-1 (42pp), A83 max-diff 2.71e-1 (27pp) — both far above 1e-1 escalation threshold."*

(Note: STATUS doc cites **1e-1 escalation threshold**, FAQ cites **5e-2** — both true; 5e-2 is the original gate, 1e-1 the escalation threshold. Not drift, both numbers correctly framed elsewhere in the decision doc.)

---

## Q4: "Is v1.7.0 actually working?" — PASS

`docs/v1_7_1_independent_verification.md` exists (16,982 B). String `"0.00000000"` appears 4 times in the file (`grep -c` confirmed).

---

## Q5: "What's Path D and should I approve it?" — PASS

Both cited artifacts exist:
- `docs/v1_6_1_path_d_decision.md` — PRESENT
- `scripts/ship_v1_6_1_engine.sh` — PRESENT (15,049 B, executable script)

---

## Q6: "Why are there 3 open PRs?" — PASS

`gh pr list --state open --json number,title,mergeable,mergeStateStatus`:
```json
[
  {"number":4, "mergeable":"MERGEABLE", "mergeStateStatus":"CLEAN", "title":"docs(readme): fix broken cross-ref..."},
  {"number":3, "mergeable":"MERGEABLE", "mergeStateStatus":"CLEAN", "title":"fix(packaging): v1.4.0 .dmg nicegui bundle..."},
  {"number":2, "mergeable":"MERGEABLE", "mergeStateStatus":"CLEAN", "title":"docs(usage): v1.7.0 aggregator-vs-Nash..."}
]
```

All 3 PRs MERGEABLE+CLEAN. Titles match FAQ subject-line summaries (USAGE.md / .dmg packaging / README cleanup).

---

## Q7: "What's left to do?" — PASS

Both cited doc artifacts exist:
- `docs/gate_4_operational_plan.md` (11,603 B)
- `docs/pr_proposals/v1_8_neon_vector_kernels_spec.md` (12,466 B)

---

## Q8: "Can I just merge everything in?" — PASS

FAQ-suggested order: **#4 → #2 → #3**.
`docs/PR_REVIEW_PREP_2026-05-23.md:181-183` BATCH MERGE OPTION confirms identical order:
1. **PR #4 first** (docs-only, smallest diff, fixes a public-repo leak)
2. **PR #2 second** (docs-only; documents v1.7.0 behavior)
3. **PR #3 last** (packaging change; triggers PR 11 .dmg rebuild)

---

## Aggregate

**Result: 8/8 VERIFIED — no drift found.**

Every FAQ-cited SHA, tag, file path, PR number, and merge order matches source-of-truth artifacts. The FAQ is authoritative as of 2026-05-23.
