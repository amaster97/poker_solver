# UI Design Principles — Poker Solver (PR 10a/10b)

**Status:** Draft. Authored 2026-05-22 for the PR 10 spec amendment cycle.
**Sibling docs:** `pr10_spec.md` (existing feature spec), `competitor_ui_deep_dive.md`
(in flight). When the deep dive lands, cross-check the anti-patterns list.

**Goal:** lock UI *design intent* before agents A/B/C in `pr10_spec.md` §10 implement.
The spec is feature-complete but is silent on taste — this fills that gap.

---

## 1. Target user profile

The first user is the developer: a Columbia GSB student who plays / studies poker,
codes Python fluently, reads C++, has never touched Rust. They are building this
tool to *use* it. Validation criterion: "can I sit down on a Tuesday night, paste a
spot from a session review, and get a strategy view I can learn from?" Anything
failing that test is overhead.

Second wave: the developer's poker community. 1-on-1 demos, screen-shares during
study groups, eventually a binary handed to a friend who installs via `pip` but
won't read the README. These users have used Pio or GTO Wizard. They expect the
13×13 range matrix as the centerpiece, expect Pio's color convention (red=fold /
yellow=call / green=raise), and judge the tool's seriousness by the *first ten
seconds* of the matrix view. They won't forgive jankiness on the centerpiece;
they'll forgive everything else.

Implication: developer-as-first-user means **minimal hand-holding** (no
tutorial, no marketing copy, no onboarding wizard). Community-as-second-user
means **zero-config defaults that produce a recognizable view in one click** —
a preset spot, sensible bet sizes, 100 BB default, a "Solve" button that just
works. The friend-with-no-README path catches the bugs the developer's muscle
memory hides.

---

## 2. Design principles

### 2.1 Defaults first, settings on demand

Every panel renders something meaningful before the user touches a control.
Default spot (100 BB postflop on K♥7♥2♦, balanced ranges, six default bet sizes,
2000 iterations) is pre-loaded at page-open. `Solve` is clickable immediately and
produces a result. Settings (bet-size customization, raise-cap tuning, iteration
count, abstraction tier override) are visible but not blocking. Configuration is
**discovered**, never **prerequisite**.

*Rationale:* a UI that requires configuration before any output loses 80% of
users in the first 30 seconds; Pio's biggest UX failure is 8 fields before the
first solve.

### 2.2 Single visible primary action per view

Each panel has exactly one button styled `unelevated + colored` (Quasar
"primary CTA" idiom). Run panel: `Solve` primary; `Pause` / `Stop` are `flat`
and only visible while solving. Spot Input has no primary (input-only). Tree
Browser has no primary (navigation). **One green button per region.**

*Rationale:* the most common Pio complaint is "I don't know which button to
click first." One bright button per region collapses that decision.

### 2.3 Domain-native terminology, no inventions

Use the community's words. "Raise to 3 BB", not "increase aggressive action
sizing". "MDF" with hover-tooltip "Minimum Defense Frequency", not the long form
written everywhere. Solver-specific terms (`infoset`, `exploitability`,
`abstraction tier`, `node lock`) are used as-is.

*Rationale:* every neologism is friction. Custom vocabulary is the lazy refuge
of UIs that haven't earned trust; community words cost nothing.

### 2.4 Color minimalism, Pio convention reused

Strategy palette: exactly three colors — red (fold ≈ RGB 220/40/40), yellow
(call/check ≈ 220/200/40), green (raise/bet ≈ 40/180/60). Maps 1:1 to Pio. The
range-*input* matrix uses a *separate* palette (white→saturated blue) so "what's
in my range" can never collide with "what does the solver want this combo to
do". General chrome: grayscale + Quasar primary blue. **No purple, no orange,
no gradients on chart fills.**

*Rationale:* poker players read red/yellow/green fluently; more colors is
non-value cognitive load. Separate range-input palette prevents the
two-meanings-on-same-cell confusion the current spec nearly walks into.

### 2.5 Numbers always visible on hover

Matrix cell shows aggregate color at a glance. Hover reveals exact frequencies:
"AKs: combo count 3 (1 blocked), fold 5%, call 30%, bet-75% 60%, all-in 5%". No
"click to drill down" for basic numeric data. Click is reserved for state
changes (selecting a combo, selecting a tree node, opening settings).

*Rationale:* color is perceptually misleading at extreme mixings; numbers are
ground truth. "Hover to verify, click to navigate" matches every desktop app.

### 2.6 No modal dialogs for routine operations

Settings live in side panels (always-on-screen, collapsible). Save / load is a
toolbar button with a dropdown picker, not a modal. Library viewer is a dialog
*only* because it's a PR-11 stub; it converts to a side panel when real.
The only legitimate modal in PR 10 is fatal-error display, and even that
should be a `ui.notification` with an "Expand" button.

*Rationale:* modals are keystroke speed bumps; each one is a context loss.
Pio's "click → modal → settings → confirm → close" pattern is what PR 10
exists to undo.

### 2.7 Keyboard shortcuts for power users, discoverable but not in your face

Shortcuts: `Cmd-Enter` solve, `Esc` stop/cancel, `Cmd-S` save spot, `Cmd-O`
open library, `Tab` cycle panels, arrow keys navigate matrix. A keyboard-icon
button in the header opens a one-screen reference. **Shortcuts are never the
only way** — every shortcut has a clickable equivalent. After 3 seconds dwelling
on the matrix view, a one-time tooltip ("Tip: arrow keys navigate, Enter
inspects") fades in once and dismisses on first use.

*Rationale:* power users find shortcuts in their first session; first-timers
shouldn't be told. The 3-second hint splits the difference.

### 2.8 Live feedback during solve

Exploitability chart updates every 500 ms (per spec §6.2). Iteration counter
ticks live. Worker status always visible: `idle | running | paused | done |
stopped | error`. The user **never** wonders "did it hang?" If exploitability
isn't decaying, the chart shows that clearly. A spinner that just spins is
not feedback.

*Rationale:* solves take minutes. Without live feedback the user abandons the
tab; with it they *learn* what convergence looks like.

### 2.9 Honest error messages

"Cannot solve at 200 BB yet — abstraction tier override required; use 'Set
abstraction tier' in the run panel, or reduce to 150 BB" beats "Internal Server
Error". Every error tells the user (a) what went wrong, (b) which input caused
it, (c) what to do next. Stack traces hide behind "Expand details", never
visible by default.

*Rationale:* errors are teaching moments. A cryptic error trains fear; an
honest one trains use.

---

## 3. Anti-patterns to avoid

### 3.1 Three-pane "Windows 95" layouts

Pio's signature pain point: fixed left (tree), middle (matrix), right (settings
+ EV display + node info in 7 tabs). Resize collapses one pane to uselessness;
everything fights for the matrix's real estate. **The PR 10 spec proposes
exactly this (`pr10_spec.md` §3).** Must be revisited.

*Rationale:* matrix is the centerpiece; tree+settings are secondary. Two-pane
(matrix center, one collapsible right sidebar) lets the matrix breathe.

### 3.2 10+ items in any single dropdown

Long dropdowns force scroll-and-scan and signal the design gave up on
hierarchy. The bet-size menu (6 checkboxes) is fine. The "Load from preset"
dropdown (3 entries today) tends to grow — if it passes 10, replace with a
searchable list.

*Rationale:* an 11-item dropdown is just a list-with-a-bad-UI.

### 3.3 Tiny clickable areas (< 24 px touch target)

Every button, checkbox, matrix cell ≥ 24 px on its smallest dimension. The
13×13 matrix at default ~700 px wide yields ~54 px per cell — fine. Combo
inspector bars must not collapse below 24 px tall. Tree-browser nodes must not
crowd below 24 px per row; if they do, scroll the tree, don't shrink rows.

*Rationale:* 24 px is the Material / Apple HIG minimum for comfortable clicks
on a non-touch device.

### 3.4 Modal configuration dialogs every other click

The library viewer is a `ui.dialog()` (`pr10_spec.md` §3.5). OK as a stub.
**Not OK permanently.** Settings that need recurrent visiting (bet sizes,
iterations, abstraction tier) never live in modals. The proposed
`ui.expansion('Blinds & ante')` must not hide anything required for a default
solve.

*Rationale:* opening a modal to adjust a common setting is one click too many.

### 3.5 Cryptic acronyms without tooltips

"MDF", "EV", "SDR", "C/R%", "BvB", "SRP", "RFI", "VPIP", "PFR" — readable to a
poker player, opaque to a new user. Every acronym needs a hover-tooltip with
the long form and a one-sentence explanation. The existing PR 10 spec is
silent on this; the implementation must add tooltips by default, not as an
afterthought.

*Rationale:* acronyms are how poker writing communicates fast; tooltips are
how UIs do the same without losing the beginner.

### 3.6 "Are you sure?" confirmations on undoable actions

Clearing the board, resetting the spot, switching presets, loading from the
library — none of these are destructive. The user can re-create previous state
in seconds. Confirmation on undoable actions trains the user to click through
confirmations without reading.

*Rationale:* reserve confirmations for *actually* destructive operations like
"overwrite your saved library entry."

### 3.7 Hiding required input fields under "advanced settings"

If a setting is required for a default solve to succeed, it lives at top
level. Bet-size menu and raise caps are correctly top-level. Caveat: if
iteration count defaults to a value that produces visibly bad results on
common spots, it is *de facto* required and must not be tucked away. Required ≠
advanced.

*Rationale:* advanced = optional. If it's load-bearing for the typical case,
it's not advanced.

### 3.8 Dense tables of numbers without color or visual cue

The combo inspector strip in `pr10_spec.md` §3.3 is at risk: "Per combo, EV in
mBB and reach probability ... infoset key." All numbers. The strip must use
color (Pio palette on the action-distribution bar), small sparklines for reach
probability where useful, and reserve raw infoset keys for a copy-icon
button — not a wall of monospace.

*Rationale:* matrix's job is color-at-a-glance; inspector's job is the same
one level deeper. A wall-of-numbers inspector punishes the matrix-to-inspector
zoom.

---

## 4. Progressive disclosure pattern

Four tiers; each one click / interaction from the previous.

### Tier 1 — Always visible (zero clicks)

- 13×13 range matrix
- Current spot label (e.g. "100 BB · K♥7♥2♦ · BB facing SB c-bet")
- `Solve` button
- Live exploitability chart (small, ~200 px under the run panel)
- Current strategy summary line ("Avg: 60% raise, 30% call, 10% fold across in-range combos")
- Decision tree collapsed to root + first level
- "Backend: python" indicator + iteration counter while solving

Tier 1 must work without configuration. First-time user sees a solved spot and
can immediately interpret it.

### Tier 2 — One click or hover

- Per-combo numeric frequencies (hover matrix cell)
- Per-combo action distribution bar (click matrix cell → inspector strip)
- Tree node selection conditioning matrix (click tree node)
- Decision-tree-as-text view (toggle)
- Per-action EV at each tree node (already in spec §3.4)
- Reach-probability filter slider

Tier 2 is the "studying this spot" view. Engaged but no configuration.

### Tier 3 — Settings drawer (advanced panel)

- Iteration count override
- Bet-size customization (uncheck a size, add "0.5 pot")
- Raise cap selectors
- Abstraction tier override (default = auto-pick from stack depth per PLAN.md
  §1; override accessible)
- Backend selector (python / rust)
- Dark mode toggle
- Panel layout reset
- Raw infoset key viewer (toggle in combo inspector)
- Memory profile readout (per-street GB; from `MemoryReport`)

Tier 3 lives in a right-side settings drawer opened via a gear icon. **Not a
modal** — a slide-in side panel over the tree browser (least-referenced area
during settings changes).

### Tier 4 — CLI / library API only

- Debug logging (`PYTHON_LOGLEVEL=DEBUG`)
- Profiler output (`cargo bench`, Python profiler)
- Regret tables (raw DCFR cumulative-regret arrays via
  `poker_solver.solve(...).debug_dump()`)
- Tree-builder internals (`tree.export_dot()`)

Tier 4 is REPL / CLI territory. The UI doesn't need to expose these;
documenting them in CLI/library docs prevents a gap.

---

## 5. Concrete decisions to lock

| Decision | Locked value | Rationale |
|---|---|---|
| Default theme | **Dark mode default**, light toggleable | Poker community is desktop / dark / late-night; matches Pio, GTO Wizard, and DeepSolver defaults |
| Font (numbers) | **Monospace** (system: SF Mono / Menlo / Consolas) | Numeric alignment matters when scanning columns of frequencies |
| Font (labels) | **Sans-serif** (system: SF Pro / Inter / Segoe UI) | Reads cleaner for UI labels; we are not optimizing for print |
| Mobile support | **Explicit non-goal for v1** (desktop browser only) | NiceGUI is desktop-first; the matrix is unreadable below 768 px wide |
| Keyboard navigation | **Standard arrow keys + Tab + Cmd-Enter / Esc.** No hjkl-style vim bindings | Sufficient for power users; vim bindings are over-engineered for a poker tool |
| Animation | **Minimal**: only for state changes that take non-zero time (progress bar, chart updates, slide-in side panel). No decorative transitions | Animation that exists for its own sake is noise; animation that matches a state change is feedback |
| Loading states | **Skeleton screens** for slow operations (≥ 500 ms), NOT spinners | Spinners do not communicate progress; skeleton screens at least show what is *about* to appear |
| Color palette | **Pio (red/yellow/green) for strategy + grayscale + Quasar primary blue for chrome.** No purple, no orange | Matches the community's existing reading vocabulary |
| Range-input matrix palette | **White → saturated blue** (distinct from strategy palette) | Prevents the "two-meanings-on-same-cell" confusion |
| Splitter resizability | **Yes**, panel widths persisted in `~/.poker_solver_ui/state.json` | User varies between 13" laptop and 27" external monitor; one-size layout fails |
| Tree-browser default collapse | **First-level children expanded, deeper collapsed** | The user sees the relevant first decision without scrolling |

---

## 6. Open design questions for user review

These are the design decisions the spec cannot lock without user input. Each
has a recommended default if the user defers.

### 6.1 Spot library viewer: list, grid, or search-first?

**Options:**
- *List:* one row per spot with name + small thumbnail of the board. Linear
  scrolling. Familiar.
- *Grid:* spot tiles with board thumbnails. More visual. Scales worse past
  ~50 entries.
- *Search-first:* a search box on top; results below as the user types.
  Scales to thousands of spots; minimal until you type.

**Recommendation:** **search-first** with the recent-10 spots shown by
default below the search box. Scales for PR 11's library size. Familiar
pattern (Spotlight / Cmd-K palette).

### 6.2 Tree browser: expandable list, tabs per street, or interactive graph?

**Options:**
- *Expandable list:* the spec's current proposal (`ui.tree`). Hierarchical,
  scroll-friendly, scales to thousands of nodes with lazy loading.
- *Tabs per street:* preflop / flop / turn / river tabs at the top, each
  showing its node grid. More structured, less hierarchical-aware.
- *Interactive graph:* d3.js-style force-directed graph or sankey diagram.
  Beautiful, demoable, basically unusable for navigation in a serious
  study session.

**Recommendation:** **expandable list** (matches the spec). The graph view
is a v2 demo feature; the tabs view loses the "this node is a child of
that node" hierarchy that solver users actually navigate by.

### 6.3 Live exploitability chart: log scale or linear?

**Options:**
- *Log scale:* exploitability decays roughly geometrically; log scale
  makes the convergence visible. Standard for solver UIs.
- *Linear:* easier to read raw values; convergence flattens visually to
  a curve that "looks done" long before it actually is.
- *Toggle:* support both.

**Recommendation:** **log scale by default**, with a linear-scale toggle.
The PR 10 spec §13 question 8 already raised this; the answer is log.
Implementation requires switching from `ui.line_plot` to `ui.echart` for
log-scale support; +30 LOC, worth it.

### 6.4 Range matrix: 13×13 only, or also flat list for narrow ranges?

**Options:**
- *13×13 only:* always show the full grid; out-of-range cells render
  faded grey. Visually consistent; wastes space for narrow ranges (e.g.
  a tight 3-bet range that contains 10 hand classes).
- *Flat list view:* a secondary view that lists only in-range hand
  classes, sorted by frequency or alphabetically. Useful when scanning
  a narrow range; visually inconsistent with the 13×13.
- *Toggle:* support both.

**Recommendation:** **13×13 only for PR 10**, with the flat list as a v2
addition. Reason: every solver user has trained on 13×13; introducing a
second view is incremental UX cost for a marginal benefit. If a user
specifically requests the flat list after using PR 10 for a week, ship
it then.

---

## 7. Known trade-offs

- **"Defaults first" vs. "all features usable":** resolved by Tier 3 settings
  drawer. Settings are one click away — never zero (Tier 1) or three
  (modal-buried).
- **"Color minimalism" vs. "protanopia / deuteranopia":** Pio's red/green palette
  is the community standard *and* fails red-green colorblind users. Mitigation:
  hover-numbers (rule 2.5) plus an optional "high-contrast palette" toggle in
  Tier 3 (PR 11 polish, not PR 10a MVP).
- **"Single primary action" vs. "Solve + Pause + Stop":** `Pause` / `Stop` are
  visible only during a solve. The Run panel's primary toggles: `Solve` (idle)
  → `Stop` (running, with `Pause` flat secondary).
- **"Numbers on hover" vs. "color minimalism":** tooltips only appear on hover;
  the resting state is color-only.
- **"Honest errors" vs. "domain-native terminology":** rule of thumb — if the
  user can act on the error, use the domain term; if they can't, explain what
  they need to know to act.

---

## 8. Implementation notes for PR 10 spec amendment

The PR 10 spec is feature-complete but should be amended with these design
intent decisions before agents A/B/C implement. Mechanical edits:

1. **`pr10_spec.md` §3 four-pane layout** → two-pane (matrix center + one
   collapsible right sidebar with spot input, run panel, tree browser stacked
   in collapsibles). Resolves anti-pattern 3.1.
2. **§3.5 library viewer modal** → keep as modal for the PR 10 stub but
   pre-spec PR 11 conversion to side panel + search-first UI. Resolves 3.4
   going forward.
3. **§3.3 combo inspector** → explicit guidance: action-distribution bars use
   Pio palette; infoset key is a copy-icon button, not a visible monospace
   string. Resolves 3.8.
4. **§3.2 run panel** → add Tier 3 settings drawer (gear icon) for iteration
   count, bet-size customization, raise caps, abstraction tier, backend
   selector. Keep only `Solve / Pause / Stop` + bet-size checkboxes + live
   chart at top level.
5. **All views** → hover-tooltip requirement for every acronym (MDF, EV, mBB)
   and solver-specific term (infoset, reach, abstraction). Resolves 3.5.
6. **All forms** → keyboard shortcut for the primary action + a 3-second
   discoverability tooltip on first dwell. Implements rule 2.7.

These six amendments are mechanical; implementation agents inherit design
intent without spec rewrite.

---

*End of UI design principles.*
