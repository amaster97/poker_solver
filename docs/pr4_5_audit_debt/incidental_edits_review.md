# PR 4.5 incidental edits review

**Branch under audit:** `pr-4.5-audit-debt-sweep`
**Baseline:** `integration`
**Files reviewed:** 3 (Agent B owns 2 of 3; Agent A owns 1 of 3 per kickoff §5a)
**Scope source:** `docs/pr4_5_audit_debt/launch_kickoff.md` §2 (13-item list)
**Date:** 2026-05-22

---

## 1. Per-file diff summary

### 1a. `poker_solver/abstraction/emd_clustering.py` (Agent B ownership)

**Diff size:** ~22 lines (`+6 -3` body, plus diff frame).
**Location:** `_kmeans_plusplus_init`, lines 190-199.
**Change:** Replaces the `unselected.size == 0` fallback branch
(`chosen_idx[c] = chosen_idx[0]` with "pad by reusing index 0" comment) with
`raise AssertionError("unreachable; n < K degenerate branch handled at line 167")`.
The `else:` arm is also flattened (assignment now sits at outer indent because
the `if` body now raises unconditionally).

**Maps to:** Item **4-C** verbatim from kickoff §2 ("Mark `_kmeans_plusplus_init`
empty-cluster fallback unreachable at `emd_clustering.py:188-196`... Replace
`chosen_idx[c] = chosen_idx[0]` with `assert False, "unreachable; n < K branch
handled at line 167"`").

### 1b. `poker_solver/abstraction/precompute.py` (Agent B ownership)

**Diff size:** ~51 lines (`+19 -10` body).
**Locations:**
- Lines 47-55: new module-level constants `_AUTOSIZE_MC_ITERATIONS_THRESHOLD = 5_000`,
  `_AUTOSIZE_BOARDS_CAP = 8`, `_AUTOSIZE_HANDS_CAP = 16` with explanatory comment.
- Lines 451-469 (inside `build_abstraction`): autosize block refactored to
  reference the new constants and to honour a new `-1` sentinel meaning
  "explicit no cap." `None` continues to mean "autosize when mc budget tiny."

**Maps to:** Item **4-D** verbatim from kickoff §2 ("Surface
`mc_iterations < 5000` autosize trigger as explicit kwarg at
`precompute.py:452-455`... Add `max_boards_per_street=None` sentinel for 'use
autosize' + `-1` for 'no cap.'"). Threshold value (5000) unchanged; only the
named-constant + sentinel surface is new.

### 1c. `poker_solver/pushfold.py` (Agent A ownership)

**Diff size:** ~29 lines (`+9 -2` body).
**Locations:**
- Lines 180-189 (docstring of `solve_pushfold`): expands the `Returns:` block.
  Adds prose stating `game_value` is returned as `0.0` placeholder because
  chart JSON does not persist per-depth SB EV (spec §6 line 212), tells
  consumers to compute from `average_strategy` or wait for chart metadata,
  and documents `exploitability_history` as a single-element list.
- Lines 226-228 (function body): new 3-line `# game_value=0.0 is a documented
  placeholder...` comment immediately above the existing `return SolveResult(...)`.

**No logic change.** The literal `game_value=0.0` line and surrounding return
shape are byte-identical to integration. Only a docstring expansion and an
adjacent code comment.

---

## 2. Mechanical vs behavioral classification

| File | Verdict | Reasoning |
|---|---|---|
| `emd_clustering.py` | **MECHANICAL** | The replaced branch is documented-unreachable; runtime behavior changes only on a path that, per the audit and the surrounding `n < K` guard at line 167, never executes. No observable strategy/centroid output change. Matches kickoff §2 Item 4-C letter. |
| `precompute.py` | **MECHANICAL** | Threshold value (5000), default cap values (8, 16), and the `None`-triggered autosize semantics are byte-identical. The `-1` sentinel adds a NEW capability — callers can now request "no cap" without changing default behavior. Strictly additive on the existing kwarg surface. Matches kickoff §2 Item 4-D letter. |
| `pushfold.py` | **DOC-ONLY (mechanical)** | Pure docstring + comment additions. No function signature, control flow, return value, or exception path touched. Even more conservative than a typical mechanical fix. |

No behavioral changes detected in any of the three files.

---

## 3. Scope verdict: WITHIN-SCOPE vs OUT-OF-SCOPE

| File | Verdict | Justification |
|---|---|---|
| `emd_clustering.py` | **WITHIN-SCOPE** | Item 4-C; Agent B ownership row in kickoff §5a. |
| `precompute.py` | **WITHIN-SCOPE** | Item 4-D; Agent B ownership row in kickoff §5a. |
| `pushfold.py` | **OUT-OF-SCOPE (scope creep, low severity)** | Agent A owns this file (kickoff §5a). Kickoff §2 PR 3/3.5 items for `pushfold.py` are 3.5-A (`PushFoldChartUnavailable(ValueError)`), 3.5-B (drop `v1-placeholder`), 3.5-C (remove dead `_canonical_hand_classes`). The `game_value=0.0` docstring/comment edit does NOT appear in §2. It plausibly references PR 3.5 audit report §6 item #10 (the `game_value=0.0` silent-wrong issue), but kickoff §3 explicitly defers "PR 3.5 §6 must-fixes 1-5" as already-landed and lists no carve-out for #6+. Adding documentation about a known silent-wrong condition without fixing it is a scope expansion outside the documented 13 items. |

### 3a. Cross-check: are the listed pushfold items (3.5-A/B/C) actually done?

Greps on current branch show:
- 3.5-A: **DONE** — `class PushFoldChartUnavailable(ValueError):` at line 35.
- 3.5-B: **NOT DONE** — `PUSHFOLD_CHART_VERSIONS` at line 29 still contains
  `"v1-placeholder"`.
- 3.5-C: **NOT DONE** — `_canonical_hand_classes` still defined at line 281.

This is a separate concern from the `game_value` docstring edit, but worth
flagging: Agent A delivered partial scope on the documented items AND added an
undocumented edit. (Items 3.5-B and 3.5-C may live in unstaged work or pending
agent waves; this audit is read-only and cannot tell.)

---

## 4. Recommendations

### 4a. `emd_clustering.py` — **KEEP**

Implements Item 4-C as written. The comment quality is slightly above the
audit-report letter (cites the specific gating line number 167); harmless
improvement. No action needed.

### 4b. `precompute.py` — **KEEP**

Implements Item 4-D as written. Refactoring the magic numbers into named
constants is implicit in the kickoff phrasing ("Surface ... as explicit
kwarg"); the constant-naming is the natural way to do that cleanly. The `-1`
sentinel matches the kickoff letter precisely. No action needed.

### 4c. `pushfold.py` — **REVERT (low priority) OR DEFER**

The edit does not change behavior and does not fix the underlying silent-wrong
condition; it merely documents it. Three options ordered by preference:

1. **Revert** the docstring expansion + 3-line comment, restore the original
   2-line `Returns:` block. Rationale: kickoff §2 + §3 are explicit that PR 4.5
   is mechanical-only with no docstring expansion beyond the documented items
   (§5c: "no docstring expansions beyond the one-line items"). The
   `game_value` issue (PR 3.5 audit item #10) should land in its own focused
   PR that ALSO fixes the silent-wrong return — not as a docstring-only band-aid.
   This matches user-memory rule "Don't extrapolate" and the kickoff §10b
   ("Agent scope expansion. Agent reports 'while reviewing PR 4 audit, I also
   fixed X.' Revert X").

2. **Defer-and-keep** if the user explicitly elects to leave it: log the edit
   in `audit_followup_backlog.md` as "documentation-only acknowledgement of
   PR 3.5 audit §6 item #10; real fix deferred to dedicated PR." Cost: PR 4.5
   diff grows slightly and the silent-wrong condition stays.

3. **Promote to in-scope** by amending kickoff §2 to add a 14th item
   ("Item 3.5-D: docstring annotation of `game_value` placeholder in
   `solve_pushfold`") AND amending §3 to remove the "no docstring expansions
   beyond the one-line items" constraint. Per kickoff §2 last line: "If any
   deferred item is reclassified, add to §2 and update §5 ownership; do NOT
   silently extend scope mid-execution." This is the heaviest option and is
   only worthwhile if the user wants the docstring lockfile NOW.

**Default recommendation: Option 1 (revert).** The cost is ~9 lines of diff;
the win is preserving the kickoff's "13 items exhaustive" invariant and
audit-trail clarity. Option 2 is acceptable if the orchestrator wants to
minimise churn before the audit agent runs at kickoff §9b.

---

## 5. Summary

- 2 of 3 files (`emd_clustering.py`, `precompute.py`) are clean mechanical
  fixes implementing Items 4-C and 4-D as written. **Keep both.**
- 1 of 3 files (`pushfold.py`) is doc-only scope creep that documents but does
  not fix the PR 3.5 audit `game_value=0.0` silent-wrong issue.
  **Recommend revert** to preserve kickoff scope-discipline; alternative is
  formal scope-expansion via kickoff §2 amendment.
- Orthogonal flag: pushfold Items 3.5-B and 3.5-C from kickoff §2 do NOT
  appear implemented in the current working tree. Surface to Agent A or
  confirm they live in a pending wave.
