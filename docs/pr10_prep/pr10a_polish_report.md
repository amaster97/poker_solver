# PR 10a polish pass — agent prompts vs. locked decisions

**Date:** 2026-05-22
**Auditor agent run:** post-synthesis polish

## 1. Synthesis agent state

**LANDED.** `pr10a_spec.md` mtime stabilised at 1779431020 (UTC offset
EDT); 469+ seconds elapsed since last write at time of audit (well past
the 30 s in-flight threshold). Final length: 976 lines.

**§0.1 locked-decisions section present and visible** (lines 27–105),
with all seven Q1–Q7 locks cited against three landed UX research docs
(`competitor_ui_deep_dive.md`, `ui_design_principles.md`,
`ui_mockups_and_debates.md`). Includes the explicit
"coin-flip flag on Q3" (1000 vs 2000 iters) and the "dissent footnote
on Q1" (mockup 1.1 recommended 4-pane; deep-dive + design-principles
outweighed it). Synthesis quality: **high** — each Q lock has explicit
section citations, no vague hand-waves.

## 2. Per-prompt cross-reference checks (BEFORE polish)

Findings against the three implementation prompts:

### Agent A (`agent_a_prompt.md`)
- **Spec reference:** pointed at `pr10_spec.md` (original PR 10), NOT
  `pr10a_spec.md`. Missed the entire §0.1 lock block.
- **Worker contract:** told to use `DCFRSolver` directly. CONFLICTS with
  the locked mock contract — `pr10a_spec.md` §7 mandates
  `from ui.mock_solver import mock_solve as _solve_postflop_impl`.
- **Q-locks surfaced:** ZERO of seven.
- **Q3 iter default:** said 2000 (wrong; Q3 locks 1000).
- **Q6 reach filter default:** `UIPrefs.tree_reach_filter = 0.0` (wrong;
  Q6 locks 0.01).
- **Onboarding modal:** not mentioned (pr10a §13 assigns to A).
- **Q7 mock-mode banner:** not mentioned.
- **Preset markers:** listed 3 placeholder presets, not the 12 fixture
  spots from `pr10a_spec.md` §7.4.

### Agent B (`agent_b_prompt.md`)
- **Spec reference:** pointed at `pr10_spec.md`. Missed §0.1.
- **Q6 reach filter:** explicit conflict — prompt said slider default
  value = 0.0 with 0.01 as tooltip "recommendation only". `pr10a_spec.md`
  §0.1 Q6 locks the slider initial value at 0.01.
- **`SolveTree.__init__` default:** `min_reach: float = 0.0` (wrong; Q6
  locks 0.01).
- **Q2 cell labels:** implicit only (not flagged as locked).
- **Q5 inspector position:** correct (below) but not flagged as locked.

### Agent C (`agent_c_prompt.md`)
- **Spec reference:** pointed at `pr10_spec.md`.
- **Mock solver ownership:** NOT mentioned. `pr10a_spec.md` §9 Agent C
  + §13 files-table assigns `ui/mock_solver.py` + `ui/mock_solver_fixtures.py`
  to Agent C. Prompt was silent on this.
- **Test count:** 8 (wrong; `pr10a_spec.md` §10 specifies 20: §10.1 ×8 +
  §10.2 ×5 + §10.3 ×4 + §10.4 ×3).
- **Library stub:** "Load from disk" button + 3 placeholder rows.
  `pr10a_spec.md` §4.6 mockup specifies `[Load selected]` + `[Delete]` +
  Filter field + `(3 entries)` + PR 11 banner.
- **Stop-button smoke 5:** used a preset marker name
  (`preset-default-100bb-postflop`) that's not in the 12-fixture list.
- **Mock-mode banner test:** absent (Q7 lock not surfaced).
- **README:** generic "## UI", no Q7 banner explainer, no `pr10a_spec`
  reference.

## 3. PR 10b consistency check

`pr10b_spec.md` (BEFORE polish):
- Did not reference the §0.1 locked decisions.
- Did not call out the Q7 banner downgrade (yellow banner → subtle chip).
- "Update README to drop (mock) tagline" was vague.

Otherwise solid: §3 engine-side change (`on_progress` kwarg), §4 UI-side
diff (one-line `mock_solver` → real solver import), and acceptance
criteria are mutually consistent with PR 10a's mock contract.

## 4. Patches applied

### `agent_a_prompt.md`
- Retitle to "PR 10a Agent A"; surface PR 10a/PR 10b split context.
- Spec reference: now `pr10a_spec.md` (with §0.1 + §3 + §7 § anchors);
  `pr10_spec.md` demoted to background only ("where they disagree,
  pr10a_spec wins").
- New "Seven Q-locks" subsection in Default decisions surfacing Q1–Q7
  with operational implications for Agent A.
- Worker pseudocode rewritten to import `mock_solve` (not `DCFRSolver`)
  with `_CANCEL_FLAG` propagation per §7.5.
- Run-panel iteration default: 1000 (Q3 lock); bet-size default 4/6
  (Q4 lock).
- Spot-input preset markers: 12 fixture spots from §7.4 enumerated.
- `tree_reach_filter` default: 0.01.
- File ownership: added `ui/views/onboarding.py` (per §13 + §11 acc #12).
- "must NOT touch" list: added `ui/mock_solver.py` + fixtures (C owns).

### `agent_b_prompt.md`
- Retitle to "PR 10a Agent B"; PR 10a context up front.
- Spec reference: now `pr10a_spec.md`.
- Q6 fix: slider default value = 0.01 (not 0.0 with tooltip).
- `SolveTree.__init__(min_reach=0.01)` default updated.
- `ui.slider(... value=0.01)` in render docstring.
- Explicit Q2 (cell labels) + Q5 (inspector below matrix) locks called out.

### `agent_c_prompt.md`
- Retitle to "PR 10a Agent C — mock solver + library stub + 20 smoke
  tests + CLI integration".
- 5-line summary rewritten: now owns mock solver + 20 tests + library
  stub.
- File ownership: added `ui/mock_solver.py` + `ui/mock_solver_fixtures.py`.
- Spec references: now `pr10a_spec.md` + `pr10b_spec.md` (forward
  context).
- New "`ui/mock_solver.py`" public-API block with byte-locked
  `mock_solve` signature + `FixturePreset` + `_CANCEL_FLAG` +
  6 failure modes + 12 fixture-spot list.
- Library stub rewritten to match `pr10a_spec.md` §4.6 mockup
  (`[Load selected]` + `[Delete]` + Filter field + PR 11 banner).
- Tests 1–8 amended (Q1/Q7 surfaced in smoke 1; smoke 5 preset
  switched to `preset-flop-k72r-100bb`); tests 9–20 added covering
  §10.2/§10.3/§10.4.
- ElementFilter markers list updated: 12 preset markers, `mock-mode-banner`
  + dismiss, `library-filter-input`, `library-delete-button`.
- README block: `## UI (mock)` with Q7 banner explainer; reference now
  `pr10a_spec.md` not `pr10_spec.md`.

### `pr10b_spec.md`
- §0 paragraph added: UI structure FROZEN at PR 10a; all seven §0.1 locks
  carry forward unchanged; only Q7 banner downgrade is the visible
  PR 10a→PR 10b UI delta.
- README mod clarified: `## UI (mock)` → `## UI`; mock-mode paragraph
  removal.

## 5. Verdict

**Prompts ready (post-polish).** All three implementation prompts now
encode the seven Q1–Q7 locks as concrete operational guidance (not
"follow the spec"). The mock-solver contract is consistent across A/B/C
(A imports it, C produces it, B is agnostic). NiceGUI 2.x is pinned in
all three (no change needed). PR 10b is internally consistent with the
locked PR 10a UI structure.

**Residual non-blocker:** Agent A's worker pseudocode acknowledges that
"pause" is approximate in PR 10a (mock_solve is a single call; pause
takes effect only between snapshots). This is an inherent property of
mocking the whole solve call, not a contract bug. PR 10b inherits the
same semantics when `solve_hunl_postflop` runs the same way.

**Coin-flip flag (Q3) carries forward** to PR 10a manual testing:
if 1000 iters produces under-converged matrices on common spots, bump to
2000 in PR 10b. Already documented in `pr10a_spec.md` §0.1 and §12 risk
#5.
