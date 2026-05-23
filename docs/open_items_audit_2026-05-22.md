# Open items + autonomous decision audit — 2026-05-22

**Auditor:** orchestrator (read-only sweep)
**Scope:** every autonomous decision logged in this session + every open audit finding across PR 3 / 3.5 / 4 / 5 + memory + PLAN.md §6 consistency.
**Repository state at audit:** `integration` tip `5832b2f` (PR 4 merge); active branch `pr-5-hunl-postflop-solve` with PR 5 in working tree (UNCOMMITTED).

---

## 1. Decisions resolved this session

### Locked + landed in code

| ID | Decision | Where landed | Status |
|---|---|---|---|
| D1 | PR 4 — suit-iso INCLUDED in PR 4 (not split into 4.5) | commit `6565b84` (`equity_features.canonicalize_for_suit_iso`) | LANDED |
| D2 | PR 4 — Monte Carlo equity features at 200K iter (not exact enum) | commit `6565b84` (`equity_features._compute_features_for_street` mc default) | LANDED |
| D3 | PR-branch pushes autonomous; main merges require explicit OK | active policy; PR 3, 3.5, 4 branches all pushed to origin | LANDED |
| S1 | Card-int mapping `rank * 4 + suit` | `poker_solver/card.py:117-119` (in PR 3 commit `a96675c`) | LANDED |
| S2 | ActionContext flat-field rewrite | `action_abstraction.py:67-82` (in PR 3 commit `a96675c`) | LANDED |
| S3 | ALL-IN street-completion fix | `hunl.py:444-501` line 468 (in PR 3 commit `a96675c`) | LANDED |
| S4 | `integration` branch as "pseudo-main" | branch exists at `5832b2f`, pushed | LANDED |
| S5 | Lint cleanup post-Agent A | folded into PR 3 commit | LANDED |
| S6 | Rebase PR 3 onto user's `2b67370` equity-hybrid main | PR 3 rebased to `a96675c`; integration rebuilt to `351cbee` then advanced | LANDED |
| S10 | Spec amendment: §4 SC landmark + §9 test 4 reflect HU Nash | `pr3_5_spec.md` §4 / §9 amended | LANDED (spec file only) |
| B1 / B2 | PR 4 → PR 6 metadata seam + AbstractionRef on HUNLConfig | implemented in PR 4 commit `6565b84` | LANDED |
| B3 / B4 / I1–I7 / N7 | Cross-spec consistency edits | spec markdown files in `pr3_5_prep/`, `pr4_prep/`, `pr5_prep/`, `pr6_prep/`, `pr8_prep/`, `pr9_prep/` | LANDED |

### Decisions in 2026-05-22 doc — still PENDING implementation

| ID | Decision | Status |
|---|---|---|
| UI Q1 | 2-pane (matrix + collapsible sidebar) — to be locked by synthesis agent | PENDING — PR 10a not started |
| UI Q2 | Hand-class labels visible inside matrix cells | PENDING — PR 10a not started |
| UI Q3 | Default iteration count 1000 | PENDING — PR 10a not started |
| UI Q4 | 4-of-6 bet sizes default | PENDING — PR 10a not started |
| UI Q5 | Combo inspector below matrix (vertical stack) | PENDING — PR 10a not started |
| UI Q6 | Tree reach threshold 0.01 | PENDING — PR 10a not started |
| UI Q7 | Yellow "Mock mode" banner during PR 10a | PENDING — PR 10a not started |
| PR 5 must-fix | `hunl_solver.py:163-167` exploitability guard | **NOT YET PATCHED** — line 171 still has unconditional `history.append(exploitability(game, avg))` |
| PR 5 should-fix | River-only fallbacks for spec §11 #1/#3/#4/#5 | NOT YET ADDED |
| PR 5 should-fix | `--abstraction PATH` CLI flag for `solve_hunl_postflop` | NOT YET ADDED |
| PR 6 launch | After PR 5 commit + readiness v3 check | BLOCKED on PR 5 commit |

---

## 2. Decisions still deferred to user

These items remain explicitly "wait for user" and have NOT been answered:

1. **Main merge of `integration` (`5832b2f` → potentially advances overnight) into `main`.** Current `main` = `2b67370` (user's equity-hybrid). Integration carries PR 3 / 3.5 / 3.5-followup / PR 4. PR 5 commit will push integration further.
2. **Any UI competitor pattern flagged as "borderline adopt"** — flagged for taste call once competitor deep-dive lands.
3. **Any of the locked autonomous decisions (D1, D2, UI Q1–Q7) that look wrong on user review.**
4. **Force-push authorization** for rebased `pr-3-hunl-tree` / `integration` branches if a future rebase is needed (separate from PR-branch push autonomy).
5. **`equity-precision` branch on `origin`** — dangling at `01475e8`, divorced from integration line. Decision needed: retire or merge.
6. **`__version__` lag** — wake_up_brief flagged `__version__ = 0.2.0` vs pyproject `0.3.0`. **NOTE:** this is actually already reconciled — `poker_solver/__init__.py:158` now reads `__version__ = "0.3.0"`. The lag flagged in `roadmap_status_2026-05-22.md` §"Honest gaps" is STALE; can be removed.
7. **PR 12 (3-handed stretch) scope decision** — explicitly post-v1, but no go/no-go decision recorded; default is skip.

---

## 3. Audit findings still open

### PR 3 audit (`pr3_prep/audit_report.md`) — verdict READY

- **Must-fix:** 0
- **Should-fix:** 7 — all DEFERRED. None patched. Items: `HUNLState.config` duplication, `(0,0)` initial_contributions dead-money interpretation, wall-clock bound on `test_hunl_default_tiny_subgame_solvable_in_one_minute`, `_action_context` pot formula comment, `enumerate_legal_actions` stack≤0 bypass, `from_str` mixed-case assertion, `include_all_in` flag guard in helpers.
- **Nice-to-fix:** 7 — all DEFERRED. Style/cleanup. Items: `AssertionError` → `ValueError` for rake fields, `_normalize_hole_action` type annotation, `_pack_hole_outcome` 6-bit packing, `BetSizing` class dead code, `bet_size_fractions` default DRY, `test_hunl_initial_state_with_ante` aggressor=1 assert, `test_hunl_max_tree_depth_bounded` depth formula, unused `field` import, `Street.SHOWDOWN` comment.

### PR 3.5 audit (`pr3_5_prep/audit_report.md`) — verdict NOT READY initially, resolved in followup `1cbf52a`

- **Must-fix:** 6 in original audit. ALL 6 PATCHED via PR 3.5 follow-up commit `1cbf52a`:
  - solve_pushfold public API ✓
  - backend "pushfold_chart" ✓
  - get_pushfold_range alias ✓
  - final_exploitability_bb_per_100 scalar ✓
  - raise on out-of-range stack ✓
  - §4/§9 spec amendment for HU Nash (S10) ✓
- **Should-fix:** 14. Three landed in follow-up (`force_tree_solve`, INFO log, ValueError). REMAINING 11: still open. Notably:
  - `tests/test_pushfold_regen.py` smoke test still MISSING (should-fix #7)
  - Strategic-equivalence collapse assertion absent from generator (should-fix #6)
  - Backend dispatch INFO log present but spec §6 test 6/14 for ~67%/30% landmark band still untested
- **Nice-to-fix:** 7 — all DEFERRED.

### PR 4 audit (`pr4_prep/audit_report.md`) — verdict READY

- **Must-fix:** 0
- **Should-fix:** 7 — all DEFERRED. Items: equity_features.py attribution header, SHOWDOWN predicate tightening, lookup_bucket error message, save_abstraction byte-determinism, kmeans++ empty-cluster fallback line, compute_river_features unused seed, autosize threshold magic constant.
- **Nice-to-fix:** 6 — all DEFERRED.
- **Coverage gaps:** 6 — recommended but not added (size-guard fire test, --flop-mode exact CLI test, preflop lossless test with abstraction set, version mismatch test, required_boards override test, kmeans degenerate test).

### PR 5 audit (`pr5_prep/audit_report.md`) — verdict READY AFTER must-fix #1, NOT YET COMMITTED

- **Must-fix:** 1 — `hunl_solver.py:163-167` exploitability hang on `iterations=0` for lossless-flop. **VERIFIED STILL OPEN** — line 171 of current file still has unconditional `history.append(exploitability(game, avg))`.
- **Should-fix:** 7 — none patched. Items: HUNLSolveResult frozen warning, exploitability cost docstring on log_every, seed determinism test, river-only fallbacks for spec §11 #1/#3, MemoryReport.iterations_at_snapshot docstring, measure_per_street alias spec clarification, CLI --abstraction PATH flag.
- **Nice-to-fix:** 5 — none patched.
- **Coverage gaps:** 6 — strategy validity test, psutil calibration on smaller fixture, OOM abort fallback, determinism test, convergence smoke spec alignment, `tiny_synthetic_abstraction()` fixture spec mismatch.

### Open items NOT in audit_reports but in PLAN.md §6 + roadmap_status

- **PR 4 full-suite verification gap:** orchestrator never ran `pytest -x` on integration tip `5832b2f` after PR 4 merge. PLAN.md §6 lists this as open. Per `autonomous_decisions_2026-05-22.md`: user-locked "skip PR 4 retroactive full-pytest — PR 5 suite already exercises 151 existing tests." **STATUS:** decision RESOLVED (skip), but PLAN.md still lists as open.
- **PR 5 TURN abstraction coverage gap:** 6 skipped tests. Owner: PR 6.
- **PR 4 kmeans homogeneity test loosened (95% → 50%).** Owner: PR 6.
- **PR 11 PyInstaller + Rust `_rust.so` bundling risk.** Owner: PR 11 audit.

---

## 4. Memory file consistency

`MEMORY.md` at `/Users/ashen/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/MEMORY.md` lists 11 entries. Cross-check vs filesystem:

| MEMORY.md entry | File exists? |
|---|---|
| `user_role.md` | YES |
| `feedback_interaction.md` | YES |
| `project_solver.md` | YES |
| `feedback_references.md` | YES |
| `feedback_plan_sync.md` | YES |
| `feedback_pr_branches.md` | YES |
| `feedback_parallel_agents.md` | YES |
| `feedback_agent_scheduling.md` | YES |
| `feedback_no_extrapolate.md` | YES |
| `feedback_continuous_pruning.md` | YES |
| `reference_planfile.md` | YES |

**Orphans (files in `memory/` that MEMORY.md does NOT reference):**

1. **`feedback_min_five_agents.md`** (created 2026-05-22) — defines the "≥5 concurrent agents" hard rule. NOT linked from MEMORY.md.
2. **`feedback_orchestrator_only.md`** (created 2026-05-22) — defines "I am orchestrator + aggregator only" rule. NOT linked from MEMORY.md.

Both are recent additions (this session) that supersede / extend the existing `feedback_parallel_agents.md` and `feedback_agent_scheduling.md`. Adding them to MEMORY.md is a 2-line edit.

---

## 5. Plan accuracy

**PLAN.md §6 vs reality:**

| §6 entry | Status |
|---|---|
| PR 4 full-suite verification gap | STALE — user explicitly skipped this on 2026-05-22 (`autonomous_decisions_2026-05-22.md`). Can remove. |
| PR 5 TURN abstraction coverage gap | ACCURATE — owner PR 6, still open. |
| PR 4 kmeans homogeneity loosened (95% → 50%) | ACCURATE — owner PR 6, still open. |
| PR 11 PyInstaller bundling risk | ACCURATE — owner PR 11. |
| PR 4 abstraction shape drift in PR 6 launch-readiness | CLOSED per the §6 text. Can remove for further pruning. |

**PLAN.md §2 trajectory:** PR 5 listed as "🚧 in flight; test verification in progress, commit pending." Matches reality (PR 5 uncommitted in working tree, audit done, must-fix open).

**Missing from PLAN.md §6 (real open items not captured):**

1. **PR 5 must-fix #1 not yet patched** — lossless-flop exploitability hang. Significant; not in §6.
2. **MEMORY.md orphans** (feedback_min_five_agents.md, feedback_orchestrator_only.md). Not in §6.
3. **`equity-precision` origin branch dangling.** Wake-up brief flagged but no §6 entry.
4. **`__version__` lag flagged in roadmap_status §"Honest gaps"** but actually already reconciled to 0.3.0. This is a STALE claim in roadmap_status, not PLAN.md.
5. **PR 3 should-fix backlog (7 items), PR 4 should-fix backlog (7 items), PR 3.5 should-fix backlog (11 items remaining post follow-up)** — none folded into a "cleanup PR" tracking entry.

---

## Verdict

**NEEDS CLEANUP** (not "clean trail").

Audit trail itself is complete (every decision is logged with rationale and reversibility), but post-decision plumbing has gaps: the MEMORY.md index is out of sync, PLAN.md §6 carries one stale resolved item and is missing several real-open items, and the PR 5 must-fix is documented in the audit report but not yet propagated as a tracked open item.

### Recommendations (5)

1. **Add the two memory orphans to MEMORY.md** — link `feedback_min_five_agents.md` and `feedback_orchestrator_only.md`. 2-line edit.
2. **Patch PR 5 must-fix #1** (`hunl_solver.py:163-167` exploitability guard) — line 171 still has the unconditional call. Two-line guard. This is the only correctness-blocking item open across all four PR audits.
3. **Prune PLAN.md §6** — drop the "PR 4 full-suite verification gap" (user-skipped) and the "PR 4 abstraction shape drift in PR 6 launch-readiness" (closed). Add: PR 5 must-fix not patched, MEMORY.md orphan items, equity-precision branch dangling decision.
4. **Clear the stale `__version__` claim from `roadmap_status_2026-05-22.md` §"Honest gaps"** — `__version__` is already 0.3.0 in `poker_solver/__init__.py:158`.
5. **Create a single "audit follow-up backlog" tracking entry** consolidating PR 3 should-fix (7), PR 3.5 should-fix remaining (11), PR 4 should-fix (7), PR 5 should-fix (7) — 32 items total. These currently live only in their per-PR audit_report.md files with no roll-up. A small "cleanup PR" or "should-fix sweep" agent could close most of them in a single batch before PR 6 launches.
