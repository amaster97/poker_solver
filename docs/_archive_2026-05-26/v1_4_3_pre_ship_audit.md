# v1.4.3 PATCH — Pre-Ship Audit

**Date:** 2026-05-23 · **Auditor:** fresh-eyes review agent (read-only).
**Scope:** PR 27, PR 29, PR 30 — three of the four branches in the LEG 14 v1.4.3 bundle. (PR 31 not audited; not part of this brief.)
**Baseline assumed:** `origin/main` @ `d9094c2` (v1.4.2 tag).

---

## 0. TL;DR per branch

| PR | Branch | Tip SHA | Footprint | Verdict |
|---|---|---|---|---|
| 27 | `pr-27-range-diff-utility` | `89c1f351` | `poker_solver/range.py` +19; `tests/test_range.py` +84/-1 | **APPROVED** — code is clean, semantics correct, 22/22 tests green, no public-OK concerns. |
| 29 | `pr-29-persona-spec-corrections` | `1b95c5b9` | `docs/pr13_prep/persona_acceptance_spec.md` +132 (new file on main) | **NEEDS-FIX** — cherry-pick would re-introduce a sanitized-away `docs/pr13_prep/` tree onto public `origin/main`. The previous commit `6e12b41 chore: clean main - Option C public-channel filter` explicitly removed this. See §2.2. |
| 30 | `pr-30-docs-v14x-update` | `c70c7cc7` | `USAGE.md` +170/-1; `DEVELOPER.md` +102 | **NEEDS-FIX (minor)** — content is solid and public-OK, but two stale-baseline phrases will be inaccurate the moment v1.4.3 ships (USAGE.md "not yet on `main` at v1.4.2" + "Updates through v1.4.2"). See §3.2. |

**One blocking issue:** PR 29 violates `feedback_public_repo_hygiene`. Either move the spec to the private mirror or scope down to just the 7 corrections **without** introducing the host file.

---

## 1. PR 27 — `Range.diff()` utility — APPROVED

### 1.1 Correctness checks

| Check | Result |
|---|---|
| Set-membership semantics | PASS — `poker_solver/range.py:55-62` iterates `self.combos` and adds combo to result iff `combo not in other._combo_set`. Directional, non-mutating. |
| Empty diff (`a.diff(empty)`) | PASS — covered by `test_diff_against_empty_range_equals_self`. |
| Self-diff (`a.diff(a)`) | PASS — `test_diff_against_self_is_empty`. |
| Superset diff (`a ⊆ b`, `a.diff(b)`) | PASS — `test_diff_against_superset_is_empty`. |
| Partial overlap | PASS — `test_diff_partial_overlap_removes_only_shared_combos`. |
| Disjoint ranges | PASS — `test_diff_with_disjoint_ranges_equals_self`. |
| Directionality | PASS — `test_diff_is_directional` (asserts `a.diff(b) != b.diff(a)`). |
| Non-mutation | PASS — `test_diff_returns_new_range_does_not_mutate_self` (asserts both `len(a)` and `a.combos` list-equal preserved). |
| Suit-level set semantics | PASS — `test_diff_boolean_set_semantics_all_freq_one` (4 AKs combos minus `AhKh` = 3 remaining combos). |
| Total test count | 22/22 (8 new diff tests + 14 prior tests). |

**Smoke run (real, executed in worktree):**
```
============================== 22 passed in 0.12s ==============================
```
The 8 diff tests, run with `-k diff`, all pass in 0.20s.

### 1.2 Defensive-design note (not blocking)

The implementation uses `other._combo_set` (private attribute access). If `other` is not a `Range` instance, it raises `AttributeError` at the access — loud failure, not silent. There is no explicit `isinstance` check or `TypeError`. The brief asked whether it *should* raise — given the existing `Range` API in `range.py` is duck-typed (no isinstance checks elsewhere), the AttributeError behavior is consistent with the rest of the module. Not a fix-blocker.

### 1.3 Public-OK scan

- No email addresses, no `/Users/ashen` paths, no session IDs, no API tokens.
- `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` trailer present in commit message — consistent with the existing pattern on `origin/main` (10 of the last 10 commits carry the same trailer; this is policy-aligned, not a leak).

### 1.4 Verdict

**APPROVED for v1.4.3.** Ships clean. Smoke tests confirm correctness. No changes requested.

---

## 2. PR 29 — Persona spec corrections — NEEDS-FIX (blocking)

### 2.1 Correctness of the 7 corrections (content review)

All 7 corrections are individually correct and well-sourced. Verified by diffing `pr-29-persona-spec-corrections` against the `integration` branch baseline (the spec file's last-modified state outside this PR):

| # | Correction | Where | Verdict |
|---|---|---|---|
| 1 | W1.3: AKs/JJ equity inverted (was 27%/73%, corrected to 91%/9%) | Line for W1.3 + heuristics-table row | CORRECT (per PokerStove; JJ is the underpair on A-high; only win path is set-spike ≈ 8.79% over 2 streets) |
| 2 | W2.1 reclass DOESN'T-WORK → PARTIAL | Sarah block | CORRECT (PR 9 has shipped per `poker_solver/preflop.py` on main; per-class sweep is the verified surface, 13×13 chart remains follow-up) |
| 3 | W2.2 reclass to PARTIAL | Sarah block | CORRECT (cites PR 27 shipping in same bundle; conditional on §5 cherry-pick order — see §4) |
| 4 | W2.4 smoke-check invariant on `initial_contributions ≤ starting_stack` | Sarah block | CORRECT (PR 22 added this validation; on main as of `ceff9bb`) |
| 5 | W2.5 reclass to PARTIAL | Sarah block | CORRECT (scoped per-class postflop substitute verified PASS) |
| 6 | W4.2 qualifier on trash-fold criterion | Priya block | CORRECT (conditional on action menu including BB iso-raise size — agent's commitment per `W4_2_v1_4_0_retest.md`) |
| 7 | "Known CLI ergonomics gaps" section | New § after W4.3 | CORRECT (W1.1, W1.2, W4.3 bundling matches v1.4.x retest reports) |

No accidental deletions. The 7 corrections are surgical edits to specific lines; surrounding spec text is untouched.

### 2.2 BLOCKING: Public-OK / dual-remote violation

**The cherry-pick is NOT a 7-correction diff against main — it is a 132-line whole-file ADD against main.**

Verification:
```
$ cd /Users/ashen/Desktop/poker_solver_worktrees/spec-corrections
$ git cat-file -e main:docs/pr13_prep/persona_acceptance_spec.md
fatal: path 'docs/pr13_prep/persona_acceptance_spec.md' exists on disk, but not in 'main'
```

`origin/main` (the public GitHub repo `amaster97/poker_solver`) has **NO `docs/` folder, NO `references/` folder, NO `docs/pr13_prep/`, NO `docs/persona_test_results/`** at all. The most recent main commit before v1.4.x work is `6e12b41 chore: clean main - Option C public-channel filter` (visible via `git log origin/main --oneline`), which explicitly removed internal planning artifacts from the public channel.

Cherry-picking PR 29 onto `origin/main` would:
1. **Re-introduce the `docs/pr13_prep/` directory tree** that the Option C filter explicitly deleted from public.
2. **Add 132 lines of internal-planning prose to the public repo**, including:
   - References to `docs/persona_test_results/W*_v1_4_*_retest.md` files that don't exist on public main (7 cross-refs to internal retest reports).
   - References to `docs/pr13_prep/persona_time_budgets.md` (doesn't exist on public main).
   - References to `references/products/piosolver_technical_details.md` and `references/blog/gtow_*.md` (the `references/` folder is excluded from public).
   - References to `tests/test_persona_acceptance.py`, `scripts/persona_report.py` (don't exist on public main; would create dangling refs).
   - Internal task IDs (#189, #191).
   - PR-prep planning prose ("PR 13 deliverable", "audit_report.md", "pr_report.md", "MEMORY.md", "feedback_persona_acceptance.md").

Per `feedback_public_repo_hygiene`: **default is HOLD; never push internal planning, session IDs, personal info.** This file is internal-planning prose; the agent's commit message of "Docs-only; no code touched" is technically true but masks the policy issue.

Per `feedback_dual_remote_workflow`: the spec file already lives on `integration` and on `backup` (private mirror). That is its correct home. Public origin gets the user-facing docs only.

### 2.3 Two paths to remediate

**Option A (preferred — minimal change):** Drop PR 29 from the v1.4.3 public-channel bundle. The 7 corrections are docs-internal; they belong on the private mirror / integration branch, not on public origin. The v1.4.3 release notes can still mention "persona spec corrections accumulated from v1.4.0/v1.4.1 retest agents" as a high-level bullet without exposing the spec file itself.

**Option B (if the spec must go public):** First, manually re-sanitize the spec — strip all `docs/persona_test_results/*` refs, all `references/*` refs, all task#NNN tags, all "PR 13 deliverable" / "audit_report.md" / "MEMORY.md" mentions — *then* land a sanitized version. This is a larger editorial change and not what PR 29 currently does.

### 2.4 Public-OK scan (content level, assuming the host-file issue were resolved)

- No email addresses (the `Co-Authored-By: Claude` trailer is policy-compliant — see §1.3).
- No `/Users/ashen` paths.
- No session IDs.
- No API tokens.
- Persona names (Marcus / Sarah / Daniel / Priya) are fictional composites — public-OK.

The line-level prose is fine. The structural problem is the file location and the cross-refs to other internal-only files.

### 2.5 Verdict

**NEEDS-FIX (BLOCKING).** Per memory, default is HOLD. Recommend Option A (drop PR 29 from the public-channel cherry-pick for v1.4.3; land on private mirror only). If the orchestrator chooses Option B, that requires a follow-up sanitization PR before any push to `origin/main`.

---

## 3. PR 30 — USAGE.md + DEVELOPER.md update — NEEDS-FIX (minor; non-blocking)

### 3.1 Correctness checks

Both commits inspected: `8bf7435` (USAGE.md) and `c70c7cc7` (DEVELOPER.md).

**USAGE.md §5.3 — node-locking:** CORRECT. The `locked_strategies` dict semantics, the bit-identical fast-path with empty/None, and the cross-ref to `tests/test_node_locking.py` match the PR 21 implementation on main (`poker_solver/__init__.py` exports `solve_hunl_postflop`).

**USAGE.md §5.4 — asymmetric contributions:** CORRECT. The three invariants (non-negative, sum-equals-pot, smaller-contribution-acts-first) match the PR 22 implementation. The worked example `initial_contributions=(100, 150), initial_pot=250` is internally consistent.

**USAGE.md §7a — known CLI gaps:** ACCURATE. Cross-checked against PR 29's "Known CLI ergonomics gaps" section — the 3 gaps (pushfold subcommand, `river --hero --villain-range`, batch-solve CSV quoting) match. The fallback Python snippets are syntactically correct and use real public APIs.

**USAGE.md §7b — known perf cliffs:** ACCURATE per memory `post_v1_ga_status` and `feedback_no_extrapolate` — the ">10 minutes on standard river spots" stalled-walk claim matches the §5.1 honest-perf-caveat already in USAGE.md. The workaround pointers (§5.2 aggregator, v1.5.0 PR 23) are honest.

**DEVELOPER.md §1 two-tier honesty:** CORRECT framing. Python `solve_hunl_postflop` (chance-enum-at-root) vs. Rust `solve_range_vs_range_rust` (vector-form CFR per Brown's `cpp/src/trainer.cpp:138-209`) are correctly distinguished as **not algorithmically equivalent**. This is the right honest note. Cross-ref to `docs/brown_apples_to_apples_2026-05-23.md` — that file exists on the shared tree but does NOT exist on `origin/main` (see §3.3).

**DEVELOPER.md §9a action abstraction:** CORRECT. `ActionAbstractionConfig` default fractions `(0.33, 0.75, 1.00, 1.50, 2.00)` match the module's defaults (verified in `poker_solver/action_abstraction.py` on main).

**DEVELOPER.md §9b library round-trip:** ACCURATE. The `exploitability_history` truncation behavior matches `poker_solver/library.py` (the W2.4 retest finding is correctly documented).

**DEVELOPER.md §9c `--workers > 1` caveat:** ACCURATE. The dataclass-comment quote at `scripts/batch_solve.py:255-257` is verified — single-worker path is the production-blessed one.

### 3.2 Stale-baseline phrases (recommended fixes; non-blocking)

PR 30 is internally consistent with v1.4.2 as the **target** ship baseline, but the bundle ships AS v1.4.3. Two phrases will be inaccurate the moment v1.4.3 lands:

**Stale phrase 1 — USAGE.md header preamble (line ~9):**
```
Document baseline: v1.0.0. Updates through v1.4.2 are layered in §5.3
(node-locking), §5.4 (asymmetric contributions), §5.5 (range utilities),
plus the new §7a (known CLI gaps) and §7b (known perf cliffs) sections.
```
Should read "Updates through v1.4.3" (this PR is part of v1.4.3, not just a v1.4.2-era doc).

**Stale phrase 2 — USAGE.md §5.5 (the Range.diff pre-doc):**
```
PR 27 (`pr-27-range-diff-utility` branch; not yet on `main` at v1.4.2)
adds `Range.diff(other)` with strict set-membership semantics — useful
for computing range intersections / complements without rebuilding
combo lists by hand. If you are not on the PR 27 branch, fall back
to manual set operations on the underlying combo iterable.
```
Once PR 27 ships in v1.4.3 (which is the entire point of the bundle), this becomes:
- Factually wrong: PR 27 IS on main as of v1.4.3.
- Confusing: "If you are not on the PR 27 branch, fall back…" — every v1.4.3+ user IS on a tree that has PR 27. The conditional collapses.

**Recommended fix:** Rewrite §5.5 as a v1.4.3 announcement (parallel to §5.3 and §5.4):
```
### 5.5 Range utilities (v1.4.3)

`Range.diff(other)` returns a new Range of combos in `self` not in
`other` — directional set-difference, non-mutating. Equivalent to
frequency-aware max(self.freq - other.freq, 0) under the current
Range invariant (all stored frequencies are 1.0). See
tests/test_range.py for worked examples.
```

These are 2-line edits, doable in the ship worktree before commit, or in a follow-up touch-up. Not a blocking gate.

### 3.3 Cross-reference exists-on-main check

| Reference | Exists on main? |
|---|---|
| `tests/test_node_locking.py` | YES |
| `tests/test_asymmetric_contributions.py` | YES |
| `tests/test_action_abstraction.py` | YES |
| `tests/test_hunl_diff.py` | YES |
| `tests/test_river_diff.py` | YES |
| `poker_solver/library.py` | YES |
| `poker_solver/action_abstraction.py` | YES |
| `scripts/batch_solve.py` | YES |
| `docs/brown_apples_to_apples_2026-05-23.md` | **NO** (DEVELOPER.md §1 cross-ref) |

**One dangling cross-ref in DEVELOPER.md §1:** "Diff against Brown's solver lives in `docs/brown_apples_to_apples_2026-05-23.md` for the algorithmic side-by-side." This file exists on the shared/integration tree but `origin/main` has no `docs/` folder. Same root cause as PR 29's issue — the `docs/` dir is filtered out of public main.

This is a softer break than PR 29 (just one dangling link, not 132 lines of internal prose), but recommend either:
- (a) Strip the `docs/brown_apples_to_apples_2026-05-23.md` parenthetical from DEVELOPER.md §1 before ship, or
- (b) Promote the brown apples-to-apples doc to public main as a separate small PR alongside v1.4.3.

### 3.4 Public-OK scan

- No email addresses, no `/Users/ashen` paths, no session IDs, no API tokens.
- The two commits (`8bf7435`, `c70c7cc7`) **lack the `Co-Authored-By: Claude` trailer** present on every other recent main commit (10/10 prior). This is the only PR of the three without that trailer. Not a leak, but a stylistic inconsistency — flagging for orchestrator awareness; may or may not matter to the public release narrative.

### 3.5 Verdict

**NEEDS-FIX (minor; non-blocking).** Two stale-baseline phrases (USAGE.md preamble + §5.5) and one dangling cross-ref (DEVELOPER.md §1). All three are 1-3 line edits doable in the ship worktree before the release-bump commit. Content quality is otherwise high — accurate, honest, well-scoped.

---

## 4. Conflict matrix (file × branch)

Verified disjoint at the file level. No two branches modify the same file.

| File | PR 27 | PR 29 | PR 30 |
|---|---|---|---|
| `poker_solver/range.py` | YES | — | — |
| `tests/test_range.py` | YES | — | — |
| `docs/pr13_prep/persona_acceptance_spec.md` | — | YES | — |
| `USAGE.md` | — | — | YES |
| `DEVELOPER.md` | — | — | YES |

**Cherry-pick textual conflict risk: nil.**

### Semantic / coherence dependencies

These are NOT cherry-pick conflicts, but they constrain ordering:

1. **PR 29 W2.2 entry says "PR 27 ships set-membership Range.diff()".** If PR 27 is dropped or fails to land in v1.4.3, PR 29's W2.2 reclass to PARTIAL becomes premature. **Conclusion: if both ship, PR 27 must land in the same bundle as PR 29.** Order between the two does not matter (file-disjoint).
2. **PR 30 USAGE.md §5.5 references PR 27 as "branch; not yet on main".** As called out in §3.2, this conditional language is **only valid if PR 27 does NOT also ship in v1.4.3**. If PR 27 ships in v1.4.3 (the current plan), PR 30's §5.5 must be edited to match — that is the §3.2 stale-baseline fix.
3. **PR 30 USAGE.md §7a (CLI gaps) references the same CLI ergonomics gaps section that PR 29's "Known CLI ergonomics gaps" §2 also bundles.** Content is consistent between the two; no contradiction. If both ship, they reinforce each other; if only one ships, USAGE.md §7a (PR 30) remains valid on its own.

---

## 5. Cherry-pick safety (per-branch)

### PR 27
```
89c1f35 Add Range.diff() utility for set-difference semantics (unblocks W2.2)
```
1 commit on top of `89a124b` (v1.4.1). Stat: `poker_solver/range.py` +19, `tests/test_range.py` +84/-1. Footprint matches plan.

### PR 29
```
1b95c5b Persona spec corrections: W1.3 equity inversion, W2.1/W2.2/W2.5 reclass, W4.2 qualifier, CLI gaps
```
1 commit on top of `89a124b`. Stat: `docs/pr13_prep/persona_acceptance_spec.md` +132 (entire-file ADD). Footprint matches plan but **flagged in §2.2** for the public-OK violation.

### PR 30
```
c70c7cc DEVELOPER.md: two-tier honesty + action abstraction + op notes
8bf7435 USAGE.md: v1.4.x capabilities + CLI gaps + perf cliffs
```
2 commits on top of `89a124b`. Stat: `USAGE.md` +170/-1, `DEVELOPER.md` +102. Footprint matches plan.

---

## 6. Recommended cherry-pick order

The LEG 14 ship plan §2c proposes: PR 31 → PR 27 → PR 30 → PR 29. **This audit refines the order to:**

| # | PR | Type | Notes |
|---|---|---|---|
| 1 | PR 31 | CODE | (Not audited here.) |
| 2 | PR 27 | CODE | Self-contained, smallest code surface, tests green. |
| 3 | PR 30 | DOCS | **WITH the §3.2 stale-baseline edits applied** before commit. Specifically: rewrite USAGE.md §5.5 to drop the "PR 27 branch; not yet on main" conditional; bump "Updates through v1.4.2" → "v1.4.3"; resolve the DEVELOPER.md §1 dangling `brown_apples_to_apples` ref. |
| ~~4~~ | ~~PR 29~~ | ~~DOCS~~ | **DROP from public-channel cherry-pick.** Land on `backup` (private mirror) only; keep on `integration` for internal continuity. Re-evaluate when the `docs/` directory's public-vs-private filter is renegotiated. |

**Rationale changes vs. plan:**
- LEG 14 §2c's "PR 30 before PR 29 because PR 30 is broader" ordering is fine **if both ship**. Once PR 29 is dropped, ordering between PR 30 and PR 29 is moot.
- The §3.2 fixes to PR 30 are easier to apply pre-cherry-pick (edit in the source branch, re-stage, recompute SHA) than post-cherry-pick (edit in ship worktree, separate commit). Either path works.
- Code-before-docs (PR 27 → PR 30) is preserved.

---

## 7. Open questions for orchestrator

1. **Is the dual-remote policy still in effect for `docs/pr13_prep/`?** The `6e12b41 chore: clean main - Option C public-channel filter` commit removed `docs/` from public main. If that policy is intentional and unchanged, PR 29 must drop. If the policy has been renegotiated (e.g. spec docs can go public after sanitization), please confirm and I'll re-audit PR 29 line-by-line for sanitization-readiness rather than recommending drop.

2. **PR 30 stale-baseline edits — fix-in-source or fix-in-ship-worktree?** Both work. Fix-in-source means rebasing the PR 30 branch (changes its tip SHA, requires re-audit). Fix-in-ship-worktree means applying the 3 edits as part of the §6 release-bump commit (no separate PR; documented in the commit message). Recommend the latter for speed.

3. **DEVELOPER.md §1 dangling ref to `docs/brown_apples_to_apples_2026-05-23.md`.** Same dual-remote question as #1 — strip the parenthetical, or promote that one doc to public main alongside v1.4.3? Stripping is 1 sentence; promotion is a separate small PR.

4. **PR 30 missing `Co-Authored-By: Claude` trailer.** Every other recent main commit carries it. This is the only inconsistency. Not a blocker, just flagging.

5. **Persona retest spawn after v1.4.3 ship?** LEG 14 §11J recommends "no mandatory retest wave; light W2.2 recheck optional." I concur — PR 27 enables W2.2 at the set-membership level, which is a utility-level convenience rather than a structural unlock. The optional W2.2 recheck can defer to the v1.5.0 cadence.

---

## 8. Audit hygiene

- All inspections were read-only against the three worktrees. No branch modifications.
- Smoke tests were run only in the PR 27 worktree (`pytest tests/test_range.py`) — read-only operation; no commits, no tags, no pushes.
- The shared `/Users/ashen/Desktop/poker_solver` tree was not modified by this audit (only the new `docs/v1_4_3_pre_ship_audit.md` file, which is this document).
- No git config changes, no remote ops.
- Time spent: ~18 min wall-clock (within the 20-min budget).
