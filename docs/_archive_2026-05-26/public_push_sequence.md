# Public Push Sequence — 2026-05-23

**Purpose.** Stage the exact command sequence to push the two
PII-cleared user-facing files to public `origin/main`. Do NOT
execute — this is preflight only.

**Cleared payload (2 files, 364 lines total):**

| File | Lines | Status on origin | PII scan |
|---|---|---|---|
| `docs/aggregator_vs_true_nash_explainer.md` | 206 | NEW (does not exist on origin) | clean (no `/Users/ashen/`, no `ashen26@`, no 16+ hex agent IDs) |
| `examples/range_vs_range_river.py` | 158 | NEW (origin has only `examples/tiny_csv.csv`) | clean |

**State preconditions:**

| Item | Value |
|---|---|
| Branch | `main` |
| Local HEAD | `dc3df6c` (v1.5.0) |
| `origin/main` | `b5777f22` (v1.5.1, 4 commits ahead, FF possible) |
| Worktree | no staged changes; both candidate files are untracked |
| Pre-commit hooks | NONE (`.pre-commit-config.yaml` not present) |
| CI workflows | NONE (`.github/workflows/` not present — only PR/issue templates) |
| `examples/` dir on origin | YES (contains `tiny_csv.csv`) — no new directory creation needed |
| `docs/` dir on origin | YES (only `docs/pr_proposals/v1_5_pr_23_implementer_notes.md`) |

---

## Push sequence (DO NOT EXECUTE — staged only)

```bash
# Step 1: Catch up to origin (4 commits behind; fast-forward)
git fetch origin main
git pull --ff-only origin main
git log --oneline -5
# Expected tip: b5777f2 v1.5.1: test rigor + docs honesty (engine bundle deferred to v1.5.2)

# Step 2: Stage public files
git add docs/aggregator_vs_true_nash_explainer.md
git add examples/range_vs_range_river.py
git status
# Expected: ONLY these 2 files in "Changes to be committed"; ~107 other
# untracked entries remain untracked (Class B / D — private mirror only).

# Step 3: Commit 1 — aggregator explainer
git commit -m "$(cat <<'EOF'
docs: add aggregator vs true-Nash range-vs-range explainer

Disambiguate the two range-vs-range code paths (Pluribus-style per-combo
aggregator vs joint vector-form CFR) so readers know which mathematical
object each function actually solves and don't mistake one's output for
the other.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"

# Step 4: Commit 2 — RvR example
git commit -m "$(cat <<'EOF'
examples: add runnable river range-vs-range starter

Provide a sub-second runnable river spot example with honest framing
about v1.0.0's hole-card knob shapes (fixed combo vs full enumeration)
so new users have a working starting point beyond the built-in
tiny_subgame fixture.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"

# Step 5: Push to public origin
git push origin main

# Step 6: Verify
git status                       # expected: "working tree clean"
git log origin/main --oneline -5 # expected: our 2 new commits at tip
```

---

## Gotchas (must resolve BEFORE executing)

### Gotcha 1 — Dangling internal cross-references in the explainer (BLOCKING)

The baseline doc (`docs/origin_vs_disk_baseline.md:80`) cleared the
explainer as PII-clean. That's true for PII. However, a second-pass
audit on **content-only-internal references** finds the explainer has
**8 cross-references to docs that don't exist on origin/main**:

| Line | Reference | Exists on origin? |
|---|---|---|
| 19 | `references/code/noambrown_poker_solver/cpp/src/trainer.cpp:138-209` | NO — `references/` is gitignored (per `.gitignore`); baseline already flagged this as a known broken link the explainer body survives. |
| 80 | `docs/persona_test_results/W3_5_range_vs_range_v1_5_1.md` | NO (internal-only persona test artifact) |
| 93 | `docs/persona_test_results/W1_2_v1_5_1_retest_deep_stack.md` | NO (same) |
| 107 | `docs/pr_23_cell_divergence_deep_dive.md` | NO (Class B audit doc) |
| 108 | `docs/v1_5_0_per_action_divergence_diagnosis.md` | NO (Class B) |
| 110 | `docs/pr_23_deep_cap_algorithmic_triage.md` | NO (Class B) |
| 133, 209 | `docs/v1_6_1_final_synthesis.md` | NO (Class B; references unshipped v1.6.1) |
| 180 | `docs/brown_apples_to_apples_2026-05-23.md` | NO (Class B) |

Plus references to **unshipped PRs / versions**: lines 199 (PR 29), 207
(PR 40), 207 (PR 34), 207 (PR 35-A/B/C), 209 (PR 33), 210 (PR 35-C
dropped), 199-217 (v1.6.1 "expected to land"). Public readers on the
current tip (v1.5.1) cannot resolve any of these; the doc reads as if
it were lifted mid-burst from an internal artifact.

**Decision required:**

- **OPTION A (HOLD).** Defer the explainer push until either (a) those
  internal docs themselves go public (they won't — they are Class B by
  design), OR (b) the explainer is rewritten to drop or paraphrase
  every internal cross-link. This is the safer call per
  `feedback_public_repo_hygiene` ("default for any unclear file: HOLD").
- **OPTION B (REWRITE-INLINE).** Strip lines 80-141 (the three
  "Concrete examples from this codebase" subsections) and lines
  198-217 (the "Going forward" PR roadmap), and replace the
  `references/code/...trainer.cpp` link in line 19 with a Brown 2019
  paper / preprint citation instead of a path that doesn't exist on a
  fresh clone. The doc's TL;DR + algorithm description + "when to use
  which" + "one wrinkle" sections stand on their own without the
  example anchors.
- **OPTION C (PUSH-AS-IS).** Accept that broken cross-links will
  appear in the public repo for any reader who clicks them. NOT
  recommended — it's a poor user experience and signals internal
  bleed-through.

**Recommendation: OPTION A (HOLD the explainer) for this push wave.**
Ship only `examples/range_vs_range_river.py` autonomously today, and
hand the explainer back for a deliberate rewrite-then-ship in a
separate dedicated agent pass (or for user OK before pushing as-is).

### Gotcha 2 — Local HEAD is behind origin

Local HEAD = `dc3df6c` (v1.5.0). `origin/main` = `b5777f22` (v1.5.1).
`git pull --ff-only origin main` MUST run before any new commit,
otherwise `git push` will fail non-fast-forward (or risk clobbering
v1.5.1 if forced — and force-push is on the explicit-OK list per
memory).

The pull is safe because the 4 origin-only commits are linear ahead
of local HEAD with no local divergent commits.

### Gotcha 3 — Untracked-files staging

`git status` reports 108 untracked entries. Steps 2's two explicit
`git add` calls target only the 2 cleared files. Do NOT use
`git add .` or `git add -A` — that would sweep in PLAN.md, ship
plans, audit reports, release artifacts, persona test results,
PR-prep directories, etc. (all Class B, all wrong for public push).

---

## Safety checklist

- [ ] **Resolve Gotcha 1 (dangling cross-refs in explainer)** — recommend
      HOLDING the explainer this wave; push only the example file. The
      autonomous-commit authorization in
      `feedback_pr10a5_autonomous_commit` covers
      audit-cleared content; the audit did NOT catch the broken
      cross-links, so the explainer is NOT audit-cleared in substance
      yet and requires either a rewrite pass or explicit user OK.
- [ ] **User authorization confirmed.** The example file alone is small,
      isolated, user-facing, and uncontroversial — fits the autonomous
      lane per `feedback_pr10a5_autonomous_commit` ("audit-cleared PRs
      ship end-to-end autonomously"). The explainer falls into the
      "major design decisions" exception lane and should get user OK
      after a rewrite (or be HELD).
- [ ] **Fresh-clone empirical verification PASSED.** Per user's
      "fresh-clone empirical verification is load-bearing" rule, run
      a fresh-clone + `pip install -e .` + `python examples/range_vs_range_river.py`
      verification in a tmp directory BEFORE pushing. Validates the
      example actually runs against a clean install of v1.5.1.
- [ ] **`git pull --ff-only origin main` succeeds without conflicts.**
      Expected: fast-forward from `dc3df6c` to `b5777f22`.
- [ ] **Post-stage `git status` shows ONLY the target files staged.**
      No accidental inclusion of PLAN.md / release artifacts / docs/
      Class B files / PR-prep directories.
- [ ] **No pre-commit hook failures** (N/A — `.pre-commit-config.yaml`
      not present on disk; nothing to fail).
- [ ] **No CI workflow blockers** (N/A — `.github/workflows/` not
      present; only PR / issue templates).
- [ ] **Post-push `git status`** shows clean tree (modulo the same 100+
      Class B / D untracked items, which stay local).
- [ ] **Post-push `git log origin/main --oneline -5`** shows our 2 new
      commits at the tip (or 1, if explainer is held).

---

## Order recommendation (under-150-word summary at the end of the
short report block in agent response)

See the agent's short report at the end of this run.

---

## Hard rules respected

- READ-ONLY across all files inspected
- WRITE confined to this single doc
- NO commits, pushes, tags, or content modifications performed
- The two candidate files were NOT modified during this audit
