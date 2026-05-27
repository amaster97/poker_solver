# v1.7.0 Ship Sequence (PR 43 + PR 39)

**Date:** 2026-05-23
**Status:** PRE-STAGED. Implementer + initial smoke verification done; **BLOCKED on v1.6.0 ship (LEG 18)**.
**Authoritative ship plan:** `docs/leg20_v1_7_0_ship_plan.md` (this file is a state-summary + go/no-go condensation).

---

## 1. Current state inventory (verified 2026-05-23)

### 1.1 PR 43 — `solve_range_vs_range_nash` (aggregator → vector wiring)

| Item | Value |
|---|---|
| Worktree | `/Users/ashen/Desktop/poker_solver_worktrees/v1-7-0-nash-wrapper` |
| Branch | `pr-43-nash-wrapper` |
| HEAD SHA | `e151de4` (full: `e151de496c5d3c985d4d28bf858b206a10571c2c`) |
| Parent | `b5777f2` (v1.5.1 tag) |
| Commits ahead of v1.5.1 base | 2 (`862bd6f` impl + `e151de4` tests) |
| `solve_range_vs_range_nash` in `poker_solver/range_aggregator.py` | YES (line 872) |
| `RangeVsRangeNashResult` dataclass | YES (line 794) |
| Exported in `poker_solver/__init__.py` | YES (both symbols in `__all__`) |
| Tests in `tests/test_range_vs_range_nash.py` | 12 cases (smoke + schema + W3.5 + divergence + 4 error + 3 exploitability/callback) |
| Differential test vs aggregator | YES (`test_diverges_from_aggregator_on_same_inputs`, asserts `max_diff >= 0.05`) |
| W3.5 monotone polarization test | YES (`test_w3_5_monotone_aa_pure_check`) |
| **Smoke result** | **12/12 PASSED in 12.59s** (verified live, this session) |

PR 43 is **functionally complete** vs. the LEG 20 plan's expected scope. Plan §1e expected "6 passed (or 7)" — implementer delivered 12, which is a positive deviation (additional Tier 5 coverage: exploitability bounds, callback firing, schema invariants).

### 1.2 PR 39 — CLI ergonomics subcommands

| Item | Value |
|---|---|
| Worktree | `/Users/ashen/Desktop/poker_solver_worktrees/cli-ergonomics` |
| Branch | `pr-39-cli-ergonomics` |
| HEAD SHA | `7584e06` (full: `7584e065b37dcbad95a9abe4fc6d1380f26e04c3`) |
| Parent | `b5777f2` (v1.5.1 tag) |
| Commits ahead of v1.5.1 base | 1 (`7584e06`) |
| `_cmd_pushfold` in `poker_solver/cli.py` | YES (line 581, ~62 LOC) |
| `_cmd_river` in `poker_solver/cli.py` | YES (line 643, ~138 LOC) |
| `_cmd_parity` in `poker_solver/cli.py` | YES (line 781, ~525 LOC, largest of the three; integrates Brown binary detection + graceful skip) |
| Subparser wiring in `main()` | YES (line 1306) |
| Tests in `tests/test_cli_subcommands.py` | 7 cases (3 pushfold + 2 river + 2 parity; parity happy-path correctly marked skip when Brown binary unbuilt) |
| **Smoke result** | **6 passed, 1 skipped in 0.49s** (verified live, this session; skip = `test_parity_happy_path_runs_to_completion` per design) |

PR 39 is **all three subcommands implemented and tested**. NOT partial. The single skip is intentional (Brown binary gate).

### 1.3 Documentation inconsistency (NON-BLOCKING but should be noted)

PLAN.md §2 (lines 115–120) currently shows:

- "PR 39" = "Aggregator-vs-true-Nash explainer doc" (🚧 in flight)
- No row for "PR 43" at all

The LEG 20 ship plan + the actual branches `pr-39-cli-ergonomics` and `pr-43-nash-wrapper` reflect the **canonical scope**:

- PR 39 = CLI ergonomics subcommands (`pushfold` + `river` + `parity`)
- PR 43 = `solve_range_vs_range_nash` true-Nash entry

The explainer doc was a separate non-PR artifact (`docs/aggregator_vs_true_nash_explainer.md`) that already exists on the v1.5.1 base. **PLAN.md §2 needs a follow-up update** (separate housekeeping PR or fold into ship commit's PLAN.md edit) — not a ship blocker, but a doc-drift item worth catching during the ship.

---

## 2. Dependency analysis

### 2.1 Hard prereq: PR 23 (vector-form CFR)

- **Status: SHIPPED at v1.5.0** (`544bd0e` tag, `dc3df6c` release commit).
- PR 43 wraps the existing `_rust.solve_range_vs_range_rust` PyO3 binding from PR 23. No new Rust code required.
- PR 39's `parity` subcommand also depends on PR 23-era acceptance machinery, also already present.

PREREQ **CLEARED**.

### 2.2 Soft prereq: v1.6.0 (PR 24a + PR 24b GUI Gate 2)

- **Status: NOT YET SHIPPED on `origin/main`.** Verified live:
  - `origin/main` HEAD = `9a2a89e` ("examples: add range-vs-range river solve example") — sits between v1.5.1 and v1.6.0
  - No `v1.6.0` tag exists in `git ls-remote --tags origin`
  - Latest tag on origin is `v1.5.1` (`b5777f2`)
  - `ship-v1.6.0` worktree exists at `0d7ca15` with PR 24b commits — **LEG 18 staged but not pushed**

PR 43 and PR 39 are both based on `b5777f2` (v1.5.1). The LEG 20 plan §1a explicitly states: "If `origin/main` is NOT at v1.6.0... STOP. v1.7.0 cannot ship before v1.6.0."

### 2.3 Ship-order rule

Per LEG 20 plan §1a / §15 hard-blocker #4:

> v1.7.0 CANNOT ship until v1.6.0 lands on `origin/main` first.

This is enforced by semver-monotonicity + the documented expectation that v1.7.0's release notes reference "users on v1.6.0 do NOT need to rebuild Rust for v1.7.0." Without v1.6.0 published, that statement is meaningless.

### 2.4 v1.6.1 (engine bundle) — DOES NOT BLOCK v1.7.0

v1.6.1 (PR 33 + 34 + 35 + 40 engine bundle) addresses **different files** than v1.7.0:

- v1.6.1 touches: `crates/cfr_core/**`, `poker_solver/range_aggregator.py` solver-internal routing (PR 33 Python delegate), test plumbing fixes.
- v1.7.0 touches: `poker_solver/range_aggregator.py` (PR 43 ADDS new functions, doesn't modify existing aggregator path), `poker_solver/__init__.py` (additive exports), `poker_solver/cli.py` (additive subcommands), `tests/` (new files).

LEG 20 plan §11 risk register confirms: "The conflict matrix vs v1.6.1 is expected nil (engine bundle is Rust + Python delegate; doesn't touch `range_aggregator.py` user API or `cli.py`)."

**Recommended ship order:** v1.6.0 (LEG 18) → v1.6.1 (engine bundle) → v1.7.0. Reason for v1.6.1 BEFORE v1.7.0:

1. v1.6.1's PR 33 (Python delegate) re-routes `solve_range_vs_range` (aggregator) through the Rust vector-form backend internally. That change is **inside** the aggregator. PR 43's new `solve_range_vs_range_nash` is a **separate function**, so it doesn't conflict; but if v1.7.0 ships first and v1.6.1 ships second, then v1.6.1's rebase will see PR 43's additions in `range_aggregator.py` and need to merge cleanly.
2. v1.6.1's PR 40 fixes the v1.5.0 Brown acceptance test plumbing — which is what PR 39's `parity` subcommand wraps. Shipping PR 39 against a still-broken parity test plumbing means the parity subcommand's happy-path tests stay skipped until v1.6.1; shipping v1.6.1 first lets v1.7.0's parity smoke run end-to-end.

That said, **v1.7.0 CAN technically ship before v1.6.1** if v1.6.1 slips (the conflict surface is nil). The cleaner sequencing is v1.6.0 → v1.6.1 → v1.7.0, but v1.6.0 → v1.7.0 → v1.6.1 is also feasible.

---

## 3. Recommended ship order

**Wave 1 (current): finish LEG 18 = v1.6.0.** This is the immediate blocker; the ship plan + the integration cherry-picks for PR 24a + 24b are staged at `/Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.0`. Once `origin/main` advances to a `v1.6.0` tag, v1.7.0 becomes shippable.

**Wave 2 (preferred): v1.6.1 engine bundle.** Closes Gate 1, unblocks W2.3 / W3.4 / W4.3, makes v1.7.0's parity subcommand end-to-end runnable.

**Wave 3: v1.7.0 (this plan).** Cherry-pick PR 43 first, then PR 39, per LEG 20 §2c.

**Alternative if v1.6.1 slips by >24 h after v1.6.0 ships:** swap to v1.6.0 → v1.7.0 → v1.6.1. Conflict risk is documented as nil but should be re-verified at that ship time via `git merge-base` + dry-run cherry-pick into a throwaway worktree.

**Do NOT ship v1.7.0 in parallel with v1.6.0 or v1.6.1.** Parallel ships would race on `origin/main` push, violate semver-monotonicity, and break the "users on v1.X.0 do NOT need to rebuild Rust" honesty statement in each release's CHANGELOG.

---

## 4. Pre-ship test matrix

Per LEG 20 plan §5a (canonical) + verified live in this session:

| Suite | Worktree | Expected | Live result (2026-05-23) | Status |
|---|---|---|---|---|
| `tests/test_range_vs_range_nash.py` | `v1-7-0-nash-wrapper` | 6+ passed (plan target); W3.5 + divergence MUST PASS | **12 passed in 12.59s** | GREEN |
| `tests/test_cli_subcommands.py` | `cli-ergonomics` | 6 passed, 1 skipped | **6 passed, 1 skipped in 0.49s** | GREEN |
| `tests/test_range_vs_range_aggregator.py` | both | 20 passed (untouched) | Not re-run this session — relies on v1.5.0 baseline; PR 43 is additive | Assumed GREEN |
| `tests/test_pushfold.py` | `cli-ergonomics` | 13 passed | Not re-run this session — PR 39 additive | Assumed GREEN |
| `tests/test_library_cli.py` | `cli-ergonomics` | 5 passed | Not re-run this session — PR 39 additive | Assumed GREEN |

**Re-run at ship time** in the `ship-v1.7.0` worktree after cherry-pick per LEG 20 §5. The 12 passing nash tests + 6+1 cli tests are the load-bearing evidence.

### Critical load-bearing assertions

These tests **must** pass in the ship worktree or HOLD:

1. **`test_w3_5_monotone_aa_pure_check`** — empirical Nash demo (AA pure-checks on monotone via Nash; aggregator gives bet ~68%). Headline narrative for v1.7.0.
2. **`test_diverges_from_aggregator_on_same_inputs`** — explicit divergence assertion (`max_diff >= 0.05`). Regression guard against accidental aliasing.

Both verified GREEN this session on the implementer branch.

---

## 5. Acceptance criteria (per persona workflow impact)

| Workflow | Pre-v1.7.0 status | v1.7.0 unblocks? | How |
|---|---|---|---|
| **W2.1** (RvR chart, Sienna) | PASS via aggregator (per W2_1_v1_4_1_retest.md) | **Validates** existing PASS via new path | True Nash entry now public; chart-by-chart re-run via `solve_range_vs_range_nash` confirms the aggregator's W2.1 result wasn't an artifact of basket selection (W2.1's spots are dry; aggregator and Nash converge there) |
| **W2.3** (river bluff-catching, Sienna) | BLOCKED (per PLAN.md §10 Gate 3) | **Unblocks once retest runs through new entry.** PR 39's `river` subcommand is the ergonomic harness. | v1.7.0 ships the path; persona retest (LEG 20 plan §13 cascading retest queue, item 2) closes the workflow |
| **W3.4** (turn polarized sizing, Diego) | BLOCKED | **Unblocks** — vector form treats range polarization correctly (per explainer §"Spec questions about range polarization... require the vector form") | Retest cascade item 3 |
| **W4.3** (CLI ergonomics, Priya) | BLOCKED — explicitly cited the PR 30 §7a "Known CLI gaps" doc as the blocking surface | **Unblocks via PR 39 directly** — PR 39 closes the documented gaps (pushfold, river, parity all wrapped) | Retest cascade item 4 |
| W3.5 (monotone polarization, Diego) | BLOCKED post-PR 38 downgrade | **Conditionally unblocks** — depends on whether the retest interprets the AA pure-check Nash result as the right answer (it is, per the empirical PoC at `docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md`) | LEG 20 §13 retest item 1 |
| W1.2 (deep-stack JJ defense, Marcus) | PARTIAL | **Validates** the 7.7% → ~0% transition is deterministic | LEG 20 §13 retest item 7 |

**Summary:** v1.7.0 directly unblocks **W2.3 + W3.4 + W4.3 + W3.5** (4 workflows) and validates / cleans up **W2.1 + W1.2** (2 workflows). 6 workflow impacts total — the biggest persona retest cascade since v1.5.0.

---

## 6. Ship steps (condensed from LEG 20 plan)

Authoritative checklist lives at `docs/leg20_v1_7_0_ship_plan.md`. Quick reference:

1. **Verify `origin/main` = v1.6.0 release SHA** (BLOCKED today; LEG 18 not shipped).
2. **Verify PR 43 audit is cleared** (no Type C-CRITICAL findings; W3.5 demo passes — passes per §4 above).
3. **Create ship worktree** off `origin/main` at `/Users/ashen/Desktop/poker_solver_worktrees/ship-v1.7.0`.
4. **Symlink the .so** (`poker_solver/_rust.cpython-313-darwin.so` → shared tree's binding; both PRs are Python-only).
5. **Cherry-pick PR 43 first** (both commits: `862bd6f` impl + `e151de4` tests, or single-range `git cherry-pick origin/main..pr-43-nash-wrapper`).
6. **Cherry-pick PR 39 second** (`7584e06`).
7. **Run smoke set** (LEG 20 §5a): expect 50/51 (12 PR 43 nash + 6+1 PR 39 cli + 20 aggregator + 13 pushfold + 5 library_cli).
8. **Bump versions**: `pyproject.toml` `1.6.0` → `1.7.0`; `poker_solver/__init__.py` `__version__` likewise. `crates/cfr_core/Cargo.toml` left at `0.5.0` (Python-only release).
9. **Edit `USAGE.md` §7a header** from `(v1.5.2+)` → `(v1.7.0+)` per LEG 20 §6c.
10. **Update PLAN.md** (housekeeping): correct §2 row for PR 39 (CLI ergonomics, not explainer doc); add row for PR 43; update Status header from "v1.5.1 → v1.6.0 in flight" to "v1.7.0 shipped."
11. **Insert `## [1.7.0]` CHANGELOG section** per LEG 20 §6b drop-in.
12. **Commit release bump**, tag `v1.7.0` annotated, push `HEAD:main` + tag.
13. **GitHub release** per LEG 20 §8 (release notes drop-in).
14. **Cleanup**: remove symlink, remove ship worktree.

---

## 7. Push gate

Per `feedback_pr10a5_autonomous_commit` + `feedback_public_repo_hygiene` + LEG 20 §14:

Autonomous ship is **in scope** when ALL of these are true:

- [x] PR 43 audit-cleared (no Type C-CRITICAL findings)
- [x] PR 39 audit-cleared at `7584e06` (per `docs/pr_39_cherrypick_plan.md` §1)
- [x] W3.5 + divergence tests GREEN (verified this session)
- [x] PR 39 subcommand tests GREEN (verified this session)
- [ ] **`origin/main` at v1.6.0 release tag** — **BLOCKED today**
- [ ] Sanitization scan clean (run at ship time per LEG 20 §1d)

Until `origin/main` advances to v1.6.0, the push gate is **CLOSED**. No exception conditions invoked (no force-push, no origin branch deletion, no major design decisions deferred).

---

## 8. Risks (post-implementer; the implementer-blocker risk is closed)

| Risk | Probability | Mitigation |
|---|---|---|
| `origin/main` does not advance to v1.6.0 (LEG 18 stalls) | **Active blocker today** | Wait on LEG 18 ship; verify daily. |
| LEG 18 ships but `crates/cfr_core/Cargo.toml` jumps to 0.6.0 | Low | LEG 20 §6a documents conditional bump (0.6.0 → 0.7.0 only if v1.6.0 did the prior bump). |
| v1.6.1 ships out of order (after v1.6.0 but before v1.7.0) | Low-medium | LEG 20 §11 risk register: re-stage by replacing `<V1_6_0_SHA>` placeholder with v1.6.1 release SHA. Conflict surface nil. |
| `solve_range_vs_range_nash` API design issue surfaces during review | Low | Implementer delivered to spec (`docs/pr_proposals/v1_7_0_aggregator_vector_wiring.md` §4); 12-test suite codifies the contract; divergence test catches accidental aliasing. |
| USAGE.md §7a version-tag missed in ship commit | Low | LEG 20 §6c explicit step; PLAN.md PR 39 row update also needs to land in same commit. |
| W3.5 / divergence test regression on cherry-pick into v1.6.0 base | Very low | Cherry-pick is to a disjoint file set (v1.6.0 = ui/state.py + chart JSON; v1.7.0 = range_aggregator.py + cli.py). No expected interaction. |

---

## 9. Verdict per PR

- **PR 43:** READY. Implementer complete. 12/12 tests green including the two load-bearing assertions (W3.5 monotone, aggregator divergence). API surface (`solve_range_vs_range_nash` + `RangeVsRangeNashResult`) exported in `__init__.py`. No open API design issues.

- **PR 39:** READY. All 3 subcommands (pushfold, river, parity) implemented + wired into the subparser + 7-case test file. 6 pass / 1 skip (intentional; Brown binary unbuilt). No partial-implementation gaps.

- **Bundle (v1.7.0):** READY pending v1.6.0 ship. The bundle itself is ship-ready end-to-end; the only blocker is the parent slot (`origin/main` at v1.6.0).

## 10. Estimated time-to-ship

- **From v1.6.0 release on origin**: 15–25 minutes wall-clock per LEG 20 §10 (mirrors LEG 18 baseline).
- **From "now" (v1.6.0 not yet shipped)**: blocked until LEG 18 lands. LEG 18 itself is staged at `ship-v1.6.0` worktree; once LEG 18 ships and (recommended) LEG 19 (v1.6.1) ships, v1.7.0 ships immediately on top.

**Total time from clear to push (autonomous): ~20 min ± 5 min.**
