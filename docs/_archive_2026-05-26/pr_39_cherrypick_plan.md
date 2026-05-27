# PR 39 (CLI ergonomics) — Cherry-pick Plan for Next Public Ship

**Date staged:** 2026-05-23 · **Status:** PRE-STAGED (read-only investigation, plan-only).
**Filename:** `docs/pr_39_cherrypick_plan.md` (authoritative).

**Bundle target (recommended):** **v1.7.0 MINOR** alongside the aggregator → vector wiring (see `docs/pr_proposals/v1_7_0_aggregator_vector_wiring.md`). Rationale in §3.

**Branch + commit:** `pr-39-cli-ergonomics` @ `7584e06` (PR 39: CLI ergonomics subcommands (pushfold, river, parity)).
**Worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/cli-ergonomics`.

---

## 0. Hard rules in force on this plan doc

- READ-ONLY guidance. No cherry-pick is executed by this document.
- No worktree modification. PR 39 worktree stays at `7584e06`, clean tree.
- Time budget capped at 12 min for the investigation; this doc is the only output.
- All commands below are documented for the ship agent to execute at ship time; they are NOT executed here.

---

## 1. PR 39 state verification (as of 2026-05-23)

| Check | Status | Evidence |
|---|---|---|
| Branch tip at `7584e06` | YES | `git log --oneline -1` → `7584e06 PR 39: CLI ergonomics subcommands (pushfold, river, parity)` |
| Working tree clean | YES | `git status` → "nothing to commit, working tree clean" |
| Branch ahead of `origin/main` by 1 commit | YES | "Your branch is ahead of 'origin/main' by 1 commit" |
| New CLI tests pass | YES (6 PASSED, 1 SKIPPED) | `pytest tests/test_cli_subcommands.py -v` → 6 passed, 1 skipped (parity happy path, Brown binary not built — by design) |
| Pre-existing CLI tests still pass | YES (18 PASSED) | `pytest tests/test_pushfold.py tests/test_library_cli.py -v` → 18 passed, 1 warning |
| Files touched | 3 | `USAGE.md`, `poker_solver/cli.py`, `tests/test_cli_subcommands.py` |
| Library / engine code touched | NO | confirmed by `git show --stat 7584e06` — only CLI + USAGE + tests |

### File-touch matrix vs v1.5.1 base (`b5777f2`)

```
USAGE.md                      | 132 +++++++++----     (rewrite §7a in place)
poker_solver/cli.py           | 437 ++++++++++++++++++++++++++++++++++++++++++   (additive only — new subcommands)
tests/test_cli_subcommands.py | 164 ++++++++++++++++  (new file)
3 files changed, 697 insertions(+), 36 deletions(-)
```

PR 39 is **pure additive + one in-place USAGE.md section rewrite**. No library, engine, Rust, test-helper, or `conftest.py` changes.

---

## 2. Conflict surface vs current origin/main (v1.5.1 @ `b5777f2`)

### 2.1 `tests/conftest.py` (PR 37 equity helper)

**Concern raised in the prompt:** does PR 39 conflict with PR 37's conftest re-export of equity helpers?

**Finding: NO CONFLICT.** PR 37 (`87e0b9a`) added `tests/conftest.py` and `tests/_equity_helpers.py`. PR 39 (`7584e06`) added `tests/test_cli_subcommands.py` — a brand-new test file. The two PRs touch disjoint paths in `tests/`. Furthermore, PR 39 was branched from `b5777f2` (v1.5.1), which already includes PR 37 — so the conftest exists in the PR 39 worktree and the new test suite already runs alongside it without conflict (verified by the 6-passed/1-skipped run above).

### 2.2 `USAGE.md` overlap with PR 30 (v1.4.3 §7a / §7b additions)

**Concern raised:** PR 30 (`0e4d30f`) introduced §7a (Known CLI gaps) and §7b (Known perf cliffs) sections. PR 39 rewrites §7a. Where exactly?

**Finding: NO CONFLICT against current `origin/main`.** Diff matrix:

| Section | Origin/main lines | PR 30 contribution | PR 39 action | Net result |
|---|---|---|---|---|
| Doc header baseline (line ~9) | "v1.0.0. Updates through v1.4.2…" | added by PR 30 (then bumped to v1.4.3 by `f9c9aad`) | PR 39 leaves header unchanged | Untouched by PR 39 (no conflict) |
| §5.3 / §5.4 / §5.5 (lines 397–481) | added by PR 30 | (PR 30's content) | PR 39 leaves untouched | No overlap |
| §7. Known limitations (line 516) | original v1.0.0 | unchanged | PR 39 leaves untouched | No overlap |
| **§7a Known CLI gaps (lines 539–585)** | **added by PR 30 (`0e4d30f` @ hunk `@@ -448,6 +537,86 @@`)** | **3 bullets: pushfold gap, river gap, batch-solve CSV quoting** | **PR 39 rewrites entire section header + first two bullets; preserves the batch-solve CSV bullet under a new "Still missing from the CLI" subsection** | **PR 39 supersedes 2 of 3 PR 30 bullets (intentionally — those are the gaps PR 39 closes) + retains the 3rd** |
| §7b Known perf cliffs (line 586) | added by PR 30 | (PR 30's content) | PR 39 leaves untouched | No overlap |
| §8 / §9 (lines 619, 638) | original v1.0.0 | unchanged | PR 39 leaves untouched | No overlap |

PR 39's USAGE.md hunk (`@@ -536,42 +536,102 @@`) starts at the `---` separator immediately before the old §7a header (line 538 on main) and replaces lines 539–585 with the new "Ergonomic subcommands (v1.5.2+)" content + retains the batch-solve CSV bullet. The new section ends at line 638-equivalent (immediately before §7b), so §7b's header is also preserved.

**Conclusion:** PR 39's USAGE.md rewrite **intentionally targets** PR 30's §7a content (closing the gaps PR 30 had documented as still-open) and is **mechanically clean** because PR 39's diff context was generated against `b5777f2`, which is the same commit that is currently at `origin/main`. A plain `git cherry-pick 7584e06` against current `origin/main` should apply with zero hunks rejected.

### 2.3 `poker_solver/cli.py`

PR 39 adds ~437 lines to `poker_solver/cli.py`. No other PR in flight (PR 33/34/35/40 engine bundle, v1.7.0 aggregator wiring spec) touches `cli.py`. No conflict surface here.

### 2.4 Conflict-risk verdict

**ZERO known conflicts against current `origin/main` (v1.5.1 @ `b5777f2`).** All three files PR 39 touches are either net-new (`tests/test_cli_subcommands.py`), additive to a file no other in-flight PR touches (`poker_solver/cli.py`), or a deliberate in-place rewrite of a PR 30 section that PR 39 was specifically designed to supersede (`USAGE.md` §7a).

**Risk surface against future bases** (only relevant if PR 39 is bundled with v1.7.0 instead of shipped directly):

- If v1.6.0 (GUI) lands first: GUI changes don't touch `cli.py` or `USAGE.md` §7a — no new conflict.
- If v1.6.1 engine bundle (PR 33+34+35+40) lands first: those PRs touch Rust + Python delegate + one acceptance test; no CLI or USAGE.md overlap with PR 39 — no new conflict.
- If v1.7.0 aggregator wiring (per `docs/pr_proposals/v1_7_0_aggregator_vector_wiring.md`) is co-staged: that PR adds a new public Python entry point (`solve_range_vs_range_nash`) and may touch USAGE.md §5.x. It does NOT touch `cli.py` or §7a (per the spec doc). Co-stage is mechanically safe.

---

## 3. Bundle decision

Three ship-slot options considered:

### Option A — Bundle with v1.7.0 MINOR (aggregator → vector wiring) — **RECOMMENDED**

- **Slot:** v1.7.0, alongside `solve_range_vs_range_nash` (the user-facing Nash entry point per `docs/pr_proposals/v1_7_0_aggregator_vector_wiring.md`).
- **Bump rationale:** v1.7.0 is a MINOR (new public API: `solve_range_vs_range_nash`). PR 39 is also new user-facing functionality (three new CLI subcommands). Both are additive non-breaking. Bundle = one MINOR ship covering "new range-vs-range Nash API + ergonomic CLI shortcuts."
- **Pros:**
  - Single MINOR semver event rather than two (PATCH + MINOR), simpler changelog narrative.
  - PR 39's USAGE.md §7a rewrite already markets the new subcommands; v1.7.0 USAGE.md edits for `solve_range_vs_range_nash` can be slotted into §5.x without §7a collision.
  - PR 39 has been sitting at `7584e06` since v1.5.1; one more cycle of latency vs v1.6.0/v1.6.1 is acceptable for purely-ergonomic improvements.
- **Cons:**
  - v1.7.0 ships later than v1.5.2 (PR 39 alone) would — but PR 39 has already been deferred for engine-bundle work, so the marginal delay is small.
- **Pre-req:** v1.7.0 spec must finalize before bundle stages. Conflict matrix re-verified at ship time (see §4).

### Option B — Ship as v1.5.2 PATCH NOW (standalone)

- **Slot:** v1.5.2, immediately on top of `b5777f2`.
- **Bump rationale:** PATCH is technically the closest semver match (no library API changes; only new CLI subcommands — but new CLI surfaces are user-visible additions, so MINOR would also be defensible).
- **Pros:** Ships immediately; closes user-facing gaps documented in PR 30's §7a.
- **Cons:**
  - LEG 18 / LEG 19 indicate v1.6.0 (GUI) is in flight and v1.6.1 (engine bundle) is staged on top of v1.6.0. Per the semver monotonic-on-public-API rule used in LEG 19, the next public release should be > v1.6.0. v1.5.2 would violate that monotonic discipline.
  - Three releases in quick succession (v1.5.2 + v1.6.0 + v1.6.1) adds release-engineering overhead for a small ergonomic win.
- **Verdict:** Rejected on semver-monotonic grounds.

### Option C — Bundle with v1.6.1 engine PATCH (PR 33+34+35+40)

- **Slot:** v1.6.1, fold PR 39 into the engine bundle.
- **Bump rationale:** v1.6.1 is currently planned as PATCH per `docs/leg19_v1_6_1_ship_plan.md`. Adding PR 39's new CLI subcommands would push v1.6.1 from PATCH to MINOR (user-visible new functionality).
- **Pros:** Slightly faster to ship than waiting for v1.7.0.
- **Cons:**
  - Forces a semver bump on v1.6.1 (PATCH → MINOR). The engine bundle's whole framing per LEG 19 §1 is "no new features, all fixes" → PATCH. Adding PR 39 breaks that framing.
  - LEG 19 carries a non-trivial risk register (bisection still in flight on dCFR perf regression, PR 40 in flight). Adding scope (PR 39) widens the audit surface needlessly.
  - PR 39 is unrelated to the engine fixes; bundling them obscures the changelog narrative.
- **Verdict:** Rejected on scope-coherence grounds.

### Recommendation

**Option A — bundle PR 39 with v1.7.0 MINOR.** Both items are additive new user-facing functionality, the conflict surface is empty in both directions, and a single MINOR bump cleanly covers both narratives.

---

## 4. Cherry-pick command sequence (for ship agent at ship time)

> **Prerequisites at ship time:** (a) v1.7.0 base branch is set up (cut from current `origin/main` plus any intervening releases — v1.6.0 GUI, v1.6.1 engine bundle if they land first); (b) v1.7.0 aggregator wiring PR is staged but NOT yet committed (so PR 39 can be cherry-picked alongside).

```bash
# 0. From the v1.7.0 ship worktree (separate worktree, not the PR 39 worktree).
cd /Users/ashen/Desktop/poker_solver_worktrees/<v1.7.0-ship-worktree>

# 1. Sanity: confirm base is at expected post-v1.6.x tip.
git log --oneline -3

# 2. Cherry-pick PR 39.
git cherry-pick 7584e06

# 3. Expected outcome: clean apply (no conflict markers), per §2.4 conflict analysis.
#    If a USAGE.md conflict appears (e.g., v1.7.0 aggregator PR rewrote §5.x in a way
#    that nudged §7a line numbers), resolve by:
#      - Keeping PR 39's full §7a "Ergonomic subcommands (v1.5.2+)" rewrite.
#      - Bumping the version tag in the §7a header from "v1.5.2+" to "v1.7.0+"
#        (since v1.5.2 was never released).
#      - Preserving any new §5.x text from the v1.7.0 aggregator PR untouched.

# 4. Smoke test (see §5).
pytest tests/test_cli_subcommands.py tests/test_pushfold.py tests/test_library_cli.py -v

# 5. Stage USAGE.md version-tag tweak if step 3 required it.
git add USAGE.md
git commit --amend --no-edit  # only if §3 resolution required edits beyond the cherry-pick

# 6. Co-stage with the v1.7.0 aggregator wiring PR, run the full v1.7.0 ship plan acceptance.
```

**Fallback (if v1.7.0 slips and an interim ship becomes desirable):** Re-stage PR 39 as a v1.7.0-precursor PATCH only if the orchestrator explicitly authorizes breaking the semver-monotonic discipline. Default is HOLD until v1.7.0 is ready.

---

## 5. Smoke test list (must remain green post-cherry-pick)

```bash
pytest tests/test_cli_subcommands.py tests/test_pushfold.py tests/test_library_cli.py -v
```

Expected outcome (verified in PR 39 worktree as of `7584e06`):

| Suite | Count | Status |
|---|---|---|
| `tests/test_cli_subcommands.py` | 6 passed, 1 skipped | parity happy path skips when Brown binary unbuilt — by design |
| `tests/test_pushfold.py` | 13 passed | unchanged from main |
| `tests/test_library_cli.py` | 5 passed | unchanged from main |
| **Total** | **24 passed, 1 skipped, 1 warning** | warning is unknown pytest mark `cli` — pre-existing, not PR 39's fault |

**Acceptance gate:** all 24 pass, 1 skip is acceptable (Brown binary not built in ship pipeline by default). Any new failure or any reduction in pass count blocks the ship.

**Recommended addition for v1.7.0 ship:** also run the full repo `pytest tests/ -v --timeout=90` to confirm PR 39's CLI additions don't introduce import-time regressions in unrelated suites. (PR 39 only imports modules already imported by `poker_solver/cli.py` upstream, so this is a belt-and-suspenders check.)

---

## 6. USAGE.md merge strategy

### 6.1 Current state on main (`b5777f2`)

§7a (lines 539–585) was added by PR 30 (`0e4d30f`, hunk `@@ -448,6 +537,86 @@`) with three bullets:

1. **Pushfold gap** — "No `poker-solver pushfold` subcommand" + Python workaround.
2. **River gap** — "No `poker-solver river --hero --villain-range` subcommand" + Python workaround.
3. **Batch-solve CSV quoting** — `bet_sizes` column CSV quoting rules.

§7b (lines 586–618) was also added by PR 30 — perf cliffs documentation. Untouched by PR 39.

### 6.2 PR 39's rewrite

PR 39's USAGE.md hunk (`@@ -536,42 +536,102 @@` per the commit diff) replaces the §7a content as follows:

| PR 30 §7a content | PR 39 action |
|---|---|
| Section title "Known CLI gaps (v1.4.x)" | Replaced with "Ergonomic subcommands (v1.5.2+)" |
| Intro paragraph "A few workflows..." | Replaced with "PR 39 added three thin CLI wrappers..." |
| Pushfold bullet (gap) | Removed; replaced with full `pushfold` subcommand docs (flags, examples, JSON mode) |
| River bullet (gap) | Removed; replaced with full `river` subcommand docs |
| Batch-solve CSV bullet | **Preserved** under a new "### Still missing from the CLI" subsection at the end of §7a, alongside the parity command docs |

The hunk net-changes 132 lines in §7a (94 deletions, 38 retained, 132 additions per `git show --stat`).

### 6.3 Overlap with PR 30 — explicit cite

PR 30 hunk in `0e4d30f`:

```
@@ -448,6 +537,86 @@ description, so the same configuration always resolves to the same row.
+## 7a. Known CLI gaps (v1.4.x)
+
+A few workflows that the library API supports are not yet wired
+through the `poker-solver` CLI. Drop down to a one-line Python
+invocation in the meantime — these gaps are tracked for a future PR.
+
+- **No `poker-solver pushfold` subcommand.** ...
```

PR 39 hunk in `7584e06`:

```
@@ -536,42 +536,102 @@ description, so the same configuration always resolves to the same row.
-## 7a. Known CLI gaps (v1.4.x)
-
-A few workflows that the library API supports are not yet wired
-through the `poker-solver` CLI. Drop down to a one-line Python
-invocation in the meantime — these gaps are tracked for a future PR.
-
-- **No `poker-solver pushfold` subcommand.** ...
+## 7a. Ergonomic subcommands (v1.5.2+)
+
+PR 39 added three thin CLI wrappers for workflows that previously
+required Python one-liners. ...
```

Both hunks share the same `description, so the same configuration always resolves to the same row.` context line, meaning PR 39's diff context exactly matches PR 30's post-state. A `git cherry-pick 7584e06` against current `origin/main` will apply this hunk cleanly because main already includes PR 30's content.

### 6.4 Version-tag adjustment for v1.7.0 bundle (Option A)

PR 39's §7a header reads `## 7a. Ergonomic subcommands (v1.5.2+)`. If v1.5.2 is never released (Option A is taken), the ship agent SHOULD edit the header to `## 7a. Ergonomic subcommands (v1.7.0+)` post-cherry-pick. This is a one-line cosmetic adjustment that should be folded into the same v1.7.0 ship commit (NOT a separate commit; NOT `--amend` of the cherry-pick — instead, add it as part of the v1.7.0 USAGE.md edits that document `solve_range_vs_range_nash`).

### 6.5 §7b untouched

§7b (Known perf cliffs) is fully preserved by PR 39. The chance-enum perf cliff is addressed by the v1.7.0 aggregator wiring PR (per `docs/pr_proposals/v1_7_0_aggregator_vector_wiring.md` §1.4), so the ship agent SHOULD also update §7b at v1.7.0 ship time to reflect that `solve_range_vs_range_nash` is the new recommended path. That update is **out of scope for PR 39** — it belongs to the v1.7.0 aggregator wiring PR.

---

## 7. Summary for orchestrator

- **Plan doc path:** `/Users/ashen/Desktop/poker_solver/docs/pr_39_cherrypick_plan.md` (this file).
- **PR 39 state:** verified clean @ `7584e06`; 6 new CLI tests pass + 18 pre-existing CLI tests still pass.
- **Recommended bundle:** **Option A** — cherry-pick PR 39 into v1.7.0 MINOR alongside the aggregator → vector wiring (`solve_range_vs_range_nash`).
- **Conflict risk against current `origin/main`:** **ZERO known conflicts.** PR 39 touches three files; only `USAGE.md` §7a overlaps with prior work (PR 30), and the overlap is by deliberate-supersession design with matching diff context. `tests/conftest.py` (PR 37) is not modified by PR 39.
- **Conflict risk against future bases (v1.6.0 + v1.6.1 + v1.7.0 aggregator wiring):** also expected to be zero based on the file-touch matrices of those PRs; re-verify at ship time with a dry-run `git cherry-pick --no-commit 7584e06` followed by `git cherry-pick --abort`.
- **Time to ship-day work:** cherry-pick + smoke test = ~10 min; plus a one-line USAGE.md version-tag adjustment if v1.5.2 is bypassed.
- **Outstanding pre-reqs:** v1.7.0 spec finalization (`docs/pr_proposals/v1_7_0_aggregator_vector_wiring.md` → implementation PR); v1.6.0 / v1.6.1 must ship first (per LEG 18 / LEG 19).
