# PR 10a agent prompt readiness check

**Date:** 2026-05-22
**Reviewer:** orchestrator (read-only audit)
**Verdict:** **READY (with 1 minor cosmetic nit on Agent A — non-blocking)**

All 3 prompts (`agent_a_prompt.md`, `agent_b_prompt.md`, `agent_c_prompt.md`)
+ `orchestrator_ready_to_fire.md` are copy-paste invokable after PR 4.5
lands. The seven Q-locks, mock-solver ownership, NiceGUI 2.x pin, and the
specific design defaults (Q1/Q4/Q6) are consistently surfaced. One cosmetic
nit in Agent A's `build_page` docstring (carries a legacy "4-pane" string)
does not affect agent execution — Q1 lock is restated 4 times elsewhere in
the same prompt and would override.

## Sanity check results

### 1. All 3 prompts reference `pr10a_spec.md` (not `pr10_spec.md`)
**PASS.** Counts:
- Agent A: 11x `pr10a_spec.md` vs 2x `pr10_spec.md` (legacy refs are scoped
  "background only" + "where they disagree, pr10a_spec wins").
- Agent B: 3x `pr10a_spec.md` vs 1x `pr10_spec.md` (same scoping).
- Agent C: 36x `pr10a_spec.md` vs 2x `pr10_spec.md` (same scoping).

Each legacy `pr10_spec.md` mention is explicitly demoted with "pr10a_spec
wins" language. No agent will read pr10_spec.md as the source of truth.

### 2. All 3 prompts cite §0.1 (the 7 locked design decisions)
**PASS.** Section reference counts:
- Agent A: 4x `§0.1` mentions; explicit Q1–Q7 lock list inline.
- Agent B: 3x `§0.1`; loadout focuses on Q2/Q5/Q6 (Agent B's domain).
- Agent C: 2x `§0.1`; surfaces in canonical spec read-list + Q-lock tests.

Agent A is the only prompt that enumerates all 7 Q-locks inline. Agents B
and C surface the locks they touch (B: Q2/Q5/Q6/Q7-via-banner-test; C:
Q1/Q7-via-smoke-1 + 12-fixture preset list). All three internalize §0.1
as immutable.

### 3. Mock solver layer ownership: Agent C only
**PASS.**
- Agent A explicitly states: "**Agent C owns this** (per `pr10a_spec.md`
  §9 Agent C)" for `ui/mock_solver.py`. Agent A's worker imports
  `mock_solve` as `_solve_postflop_impl` but does NOT write the body.
- Agent B's "must NOT touch" list omits `ui/mock_solver.py` (Agent B
  doesn't touch the solver layer at all — its scope is render-only).
- Agent C's ownership block: `ui/mock_solver.py` + optional
  `ui/mock_solver_fixtures.py` listed as owned (created new). The
  byte-locked first-8-param signature is restated.

No ownership ambiguity.

### 4. NiceGUI 2.x version pinned consistently
**PASS.** Every prompt cites `nicegui>=2.0,<3.0`:
- Agent A: "NiceGUI 2.x (`nicegui>=2.0,<3.0`). Use only the 2.x API
  surface."
- Agent B: "NiceGUI 2.x. Use only the 2.x API surface (`ui.grid`,
  `ui.tree`, `@ui.refreshable`, ...)."
- Agent C: pin appears 3x — narrative + pyproject snippet + the dedicated
  "[ui] extra is pinned: `nicegui>=2.0,<3.0`" callout.

### 5. Q1 = 2-pane layout literal in all 3 prompts
**PASS** (with 1 cosmetic nit in Agent A).
- Agent A: "two-pane" appears 4x — 5-line summary, spec read-list,
  Q1-LOCKED inline, and explicit "Your `ui/app.py::build_page()`
  implements 2-pane."
- Agent B: "two-pane" appears 2x — 5-line summary + spec read-list ("your
  matrix is the centerpiece, tree is a sidebar `ui.expansion` panel").
- Agent C: "two-pane" appears in smoke test 1 docstring + inline comment
  "Two-pane layout per Q1 lock: matrix center + collapsible right sidebar."

**Cosmetic nit (non-blocking):** Agent A's API contract block for
`ui/app.py::build_page()` carries a legacy docstring fragment: `"Composes
the header + 4-pane layout via ui.splitter()"` (line 336). This is in the
API spec example, not in the instructional text. Q1 lock is restated 4
times elsewhere in the same prompt; an agent reading the prompt
sequentially would override this stale fragment via the explicit Q1 lock.
Not blocking, but **noted** for any future pass.

### 6. Q4 = 4-of-6 bet sizes default
**PASS** with caveat.
- Agent A: "Q4 LOCKED: Bet sizes default = 4 of 6 checked (33% / 75% /
  100% / all-in checked; 150% / 200% unchecked)." Restated in `run_panel`
  docstring.
- Agent B: no mention (Agent B doesn't touch bet sizes).
- Agent C: no `4-of-6` literal in prompt body, BUT marker
  `'bet-size-checkbox-*'` registered in §7's ElementFilter contract list.
  Smoke 4 (solve-button) implicitly exercises the run panel which carries
  the Q4 defaults.

This is correct — only Agent A owns bet-size defaults, so the absence in
B/C is by design. The orchestrator-ready-to-fire's §3 also restates Q4
literally.

### 7. Q6 = tree reach threshold 0.01
**PASS.**
- Agent A: 2x — Q6 LOCKED in defaults list + `UIPrefs.tree_reach_filter:
  float = 0.01` in the dataclass spec.
- Agent B: 3x — 5-line summary ("slider default value = 0.01 per Q6
  locked"), Q6 LOCKED bullet (with rationale), `SolveTree.__init__(...,
  min_reach: float = 0.01)` in API spec.
- Agent C: no `0.01` literal, BUT Q6 isn't directly under Agent C's
  ownership. (Agent C doesn't write a tree-reach slider; only Agent B
  does. The smoke test for Q6 would naturally fall under Agent C's
  ElementFilter assertions on `tree-reach-slider`, but no value-equality
  check on 0.01 is in the test list.)

Coverage is adequate. The 0.01 value is locked at the
contract/dataclass-default level in A+B, and the orchestrator §3 cites it.

## Cross-prompt consistency notes

- **12 fixture preset IDs** match across A, C, and orchestrator §3.
- **Mock-solver import alias** `_solve_postflop_impl` cited identically
  in A's worker + C's signature lock + B (not applicable).
- **`_CANCEL_FLAG`** named identically in A's worker pseudo-code + C's
  `mock_solver.py` module-level declaration.
- **20 smoke tests** count in C matches orchestrator §4 deliverables.
- **ElementFilter markers** cross-referenced in C's smoke list (e.g.
  `matrix-cell`, `solve-button`, `library-dialog`) appear in the matching
  agent's render docstring (A: `solve-button`; B: `matrix-cell`; C:
  `library-dialog`).

## Recommendation

**Status: READY for copy-paste invocation after PR 4.5 ships.**

Top item if any: the cosmetic 4-pane fragment in Agent A's `build_page`
docstring (line 336) is stale and could optionally be patched in a
follow-up pass, but it does NOT block PR 10a launch. The Q1 lock is
restated 4x elsewhere in the same prompt, including an explicit
override clause ("`pr10_spec.md` §3 four-pane layout is REPLACED").

No prompts require modification before launch.
