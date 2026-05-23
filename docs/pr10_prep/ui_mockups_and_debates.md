# PR 10 UI — ASCII mockups + pro/con debates

Companion to `pr10_spec.md`. The spec defines *what* the UI does; this document
fixes *what it looks like*. Each mockup is one recommended layout for the wide-
screen NiceGUI app at the ~1440×900 default viewport. Each debate enumerates
2–3 alternatives, weighs them, and locks a recommendation.

Parallel-agent inputs (`competitor_ui_deep_dive.md`,
`ui_design_principles.md`) were not yet present when this document was
authored; references to them are placeholder-shaped. Update inline citations
when those land.

---

## Part 1 — Mockups (five core views)

### 1.1 Main app shell

```
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ poker-solver  ·  Default 100BB postflop (Kh 7h 2d)  ·  idle             [Lib] [Auto/Dk] ☰ │
├───────────────┬───────────────────────────────────────────────────────────────────────────┤
│  SPOT INPUT   │  RANGE MATRIX — root node — P0 (SB) to act                                │
│ ┌───────────┐ │   A    K    Q    J    T    9    8    7    6    5    4    3    2          │
│ │ Board     │ │ A ███  ███  ███  ███  ███  ███  ▒▒▒  ▒▒▒  ░░░  ░░░  ░░░  —    —          │
│ │  Kh 7h 2d │ │ K ███  ███  ███  ███  ▒▒▒  ▒▒▒  ░░░  ░░░  ░░░  —    —    —    —          │
│ │ [Clear]   │ │ Q ███  ███  ███  ▒▒▒  ▒▒▒  ░░░  ░░░  —    —    —    —    —    —          │
│ │ Ranges    │ │ J ███  ███  ▒▒▒  ███  ▒▒▒  ░░░  ░░░  —    —    —    —    —    —          │
│ │  [P0][P1] │ │ T ███  ▒▒▒  ▒▒▒  ▒▒▒  ███  ░░░  ░░░  —    —    —    —    —    —          │
│ │  "AA,KK.."│ │ 9 ███  ░░░  ░░░  ░░░  ░░░  ███  ░░░  —    —    —    —    —    —          │
│ │ Stacks    │ │ 8 ▒▒▒  ░░░  ░░░  ░░░  ░░░  ░░░  ███  —    —    —    —    —    —          │
│ │ P0/P1 100│  │ 7 ▒▒▒  ░░░  ░░░  ░░░  ░░░  —    —    ▓▓▓  —    —    —    —    —          │
│ │ Pos: SB→  │ │ ...                                                                       │
│ │ [Reset]   │ │  ░ fold-heavy  ▒ mixed  ▓ blocked  ███ raise/call  — out of range         │
│ │ [Preset ▼]│ │ ┌─ Combo inspector — AKs (3 of 4 combos)  ──────────────────────────────┐ │
│ └───────────┘ │ │ AsKs  ▰▰▰▰▰▰▰▰▱▱  bet75 78%  call 18%  fold 4%   EV +124  reach 0.74  │ │
│  RUN PANEL    │ │ AdKd  ▰▰▰▰▰▰▰▰▱▱  bet75 76%  call 20%  fold 4%   EV +119  reach 0.74  │ │
│ ┌───────────┐ │ │ AcKc  ▰▰▰▰▰▰▰▰▱▱  bet75 75%  call 21%  fold 4%   EV +117  reach 0.74  │ │
│ │ Bets ☑33% │ │ │ AhKh  BLOCKED — Kh on board, Ah blocks                                │ │
│ │ ☑75 ☑100  │ │ └────────────────────────────────────────────────────────────────────────┘ │
│ │ ☐150 ☐200 │ ├───────────────────────────────────────────────────────────────────────────┤
│ │ ☑all-in   │ │ DECISION TREE — reach ≥ 0.01   [▼]                visible nodes 184/523  │
│ │ iters 2000│ │  ▾ [root]  P0 to act  reach 1.00  EV +63 mBB                              │
│ │ backend Py│ │     ▸ [check]        check 100%                  EV +44 mBB               │
│ │ [Solve]   │ │     ▾ [bet 33%]      f 12% call 60% raise 28%   EV +71 mBB                │
│ │ [Pause]   │ │     ▾ [bet 75%]      f 8% call 24% raise 68%    EV +120 mBB ← selected    │
│ │ [Stop]    │ │       ▸ [P1: call]   reach 0.510                EV +85 mBB                │
│ │ Status    │ │       ▸ [P1: raise]  reach 0.158                EV +212 mBB               │
│ │  idle     │ │       ▸ [P1: fold]   reach 0.012                EV 0 mBB                  │
│ │ Iter 0/0  │ │     ▸ [bet all-in]   reach 0.010                EV +60 mBB                │
│ └───────────┘ │                                                                           │
└───────────────┴───────────────────────────────────────────────────────────────────────────┘
```

**Justification.** Four-pane layout per spec §3 (header + left input + center
matrix + bottom tree). Matrix at visual center-mass because it is the
deliverable (spec §2). Left column at 320 px stacks spot input above run
panel: input is set once, run panel is operated repeatedly — vertical
stacking biases toward "set once, solve repeatedly." Thin header (one line)
maximizes matrix area at 900 px viewport. Status text colocated with run
controls so the user's eye doesn't ping-pong after clicking `Solve`.

---

### 1.2 Spot input panel

```
┌────────────────────────────────────────────┐
│ SPOT INPUT                                 │
├────────────────────────────────────────────┤
│ Board                                      │
│  Selected:  K♥  7♥  2♦   [×][×][×]         │
│  Max 5 cards; street auto-detected.        │
│      A  K  Q  J  T  9  8  7  6  5  4  3  2 │
│   ♠  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  · │
│   ♥  ·  ◉  ·  ·  ·  ·  ·  ◉  ·  ·  ·  ·  · │
│   ♦  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ◉ │
│   ♣  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  · │
│  [Clear board]                              │
├────────────────────────────────────────────┤
│ Ranges    ▌P0 (SB/BTN)▐  │   P1 (BB)        │
│  Mode: ( ) String  (●) Matrix              │
│    13×13 paint grid; click to cycle freq    │
│    1.0 → 0.5 → 0.25 → 0; shift-click slider │
│    Darker shade = higher inclusion freq     │
│  String preview: AA,KK-TT,AKs,76s+,KQo      │
│  Combos: 124 / 1326   (9.4%)                │
├────────────────────────────────────────────┤
│ Stacks   P0 [100] BB    P1 [100] BB         │
│  ⚠ < 15 BB? Try push/fold charts.           │
│ Position  (SB acts first) [locked HUNL]    │
│ ▸ Blinds & ante  (collapsed)                │
│ [Reset spot]   [Load preset ▼]              │
└────────────────────────────────────────────┘
```

**Justification.** Board picker uses a **4×13 suit-by-rank grid** (Pio
convention; players scan by suit). The chip strip at top is canonical
readout — without it users have to visually count selected cells in the
52-cell grid. Range matrix mode defaults on (visual painting, lower
barrier) with a live string preview underneath for power users. Combo
counter ("124 / 1326") gives numeric ground truth solver users always need.

---

### 1.3 Run panel + live solve view

```
┌────────────────────────────────────────────┐
│ RUN PANEL                                  │
├────────────────────────────────────────────┤
│ Bet sizes (% pot)                          │
│  ☑ 33%   ☑ 75%   ☑ 100%                    │
│  ☐ 150%  ☐ 200%  ☑ all-in                  │
│  Custom: [0.5, 1.2___________]              │
│                                             │
│ Raise caps                                 │
│  Preflop [4]   Postflop [3]                │
│                                             │
│ Iterations [2000_____]                      │
│ Backend    ( ● Python   ○ Rust )           │
├────────────────────────────────────────────┤
│  [  Solve  ]   [ Pause ]   [ Stop ]        │
├────────────────────────────────────────────┤
│ Exploitability (mBB/pot, log ☑)             │
│  1e3 ●                                      │
│  1e2  ●●●●                                  │
│  1e1      ●●●●●●●                           │
│  1e0           ●●●●●●●●●●●●●                │
│       0   500   1k   1.5k   2k  iteration   │
│                                             │
│ Status: running   Iter: 1,247 / 2,000 (62%) │
│ Wall:   18.4 s    Expl: 3.2 mBB/pot         │
│ Backend: python                             │
└────────────────────────────────────────────┘
```

Status word colors: paused=yellow, done=green, stopped=orange, error=red.
When solve is running, `Solve` button is disabled (not hidden — keeps the
control visible as a cue).

**Justification.** Top-down causal order: controls → chart → readout matches
the user's mental flow ("set → solve → watch → read"). Log-scale default
(see Debate 3) because DCFR exploitability decays geometrically; linear
flatlines after ~100 iterations. Readout shows both iteration progress and
wall-clock — only one is unkind.

---

### 1.4 Range matrix (13×13 grid with combo frequencies)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ RANGE MATRIX   Player: P0 (SB)   Node: [bet 75%]   Pot: 4 BB   [☑ show freqs]│
├──────────────────────────────────────────────────────────────────────────────┤
│      A     K     Q     J     T     9     8     7     6     5     4    3    2 │
│  A ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬───┬───┐│
│    │AA   │AKs  │AQs  │AJs  │ATs  │A9s  │A8s  │A7s  │A6s  │A5s  │A4s  │   │   ││
│    │R 78%│R 76%│R 72%│R 65%│R 60%│R 55%│R 48%│R 42%│R 38%│ MIX │ MIX │ — │ — ││
│    │ ███ │ ███ │ ███ │ ▓▓▓ │ ▓▓▓ │ ▓▓▓ │ ▒▒▒ │ ▒▒▒ │ ▒▒▒ │ ▒░░ │ ░░░ │   │   ││
│  K ├─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼───┼───┤│
│    │AKo  │KK   │KQs  │KJs  │KTs  │K9s  │K8s  │K7s  │K6s  │K5s  │     │   │   ││
│    │R 70%│R 90%│R 65%│R 58%│R 50%│R 40%│R 32%│ BLK │ MIX │  —  │     │   │   ││
│    │ ▓▓▓ │ ███ │ ▓▓▓ │ ▓▓▓ │ ▒▒▒ │ ▒▒▒ │ ▒░░ │ ╳╳╳ │ ▒░░ │ ░░░ │     │   │   ││
│  Q ├─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼───┼───┤│
│    │AQo  │KQo  │QQ   │QJs  │QTs  │Q9s  │     │     │     │     │     │   │   ││
│    │C 50%│R 45%│R 88%│R 50%│R 42%│ MIX │     │     │     │     │     │   │   ││
│    │ ▒▒▒ │ ▓▓▓ │ ███ │ ▓▓▓ │ ▓▓▓ │ ▒░░ │     │     │     │     │     │   │   ││
│  J ├─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼───┼───┤│
│    │(rows continue J → 2; 13 rows × 13 cols total = 169 cells)              ││
│    └─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴───┴───┘│
│                                                                              │
│  Legend:  ███ raise-heavy (>60%)  ▓▓▓ raise-mixed  ▒▒▒ call-heavy             │
│           ░░░ fold-heavy   ╳╳╳ blocker-removed  — not in range                │
│  Tag:     R xx% raise dominant   C xx% call dominant   F xx% fold dominant    │
│           MIX = no action >50%   BLK = blocked by board                       │
│                                                                              │
│  Hover → tooltip: "AKs · 3/4 combos · 76% bet75 · 18% call · 6% fold · +124"  │
│  Click → opens combo inspector strip (below)                                  │
└──────────────────────────────────────────────────────────────────────────────┘

Combo inspector strip (when AKs is clicked):

┌──────────────────────────────────────────────────────────────────────────────┐
│ COMBO INSPECTOR — AKs (3 of 4 combos survive board Kh 7h 2d)                 │
├──────────────────────────────────────────────────────────────────────────────┤
│ AsKs  ▰▰▰▰▰▰▰▰▱▱  bet75 78%  call 18%  fold 4%   EV +124 mBB  reach 0.74     │
│ AdKd  ▰▰▰▰▰▰▰▰▱▱  bet75 76%  call 20%  fold 4%   EV +119 mBB  reach 0.74     │
│ AcKc  ▰▰▰▰▰▰▰▰▱▱  bet75 75%  call 21%  fold 4%   EV +117 mBB  reach 0.74     │
│ AhKh  ╳ blocked by Kh on board                                                │
│ Infoset key (AsKs):  hunl_p0_kh7h2d_bet75_AsKs                  [Copy]        │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Justification.** Two on-cell signals: **color** + **2-letter + percentage
tag** (`R 78%` = raises 78%). The tag lets users read exact frequencies
without hovering; `MIX` replaces unreadable triple-number tags for highly
mixed cells (users needing that resolution click for the inspector strip).
The inspector uses a horizontal stacked bar (`▰▰▰▰▰▰▰▰▱▱`) that scales to
any number of action sizes without widening columns. Infoset key is
copyable — solver users cross-reference keys constantly when debugging.

---

### 1.5 Decision tree browser

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ DECISION TREE   Reach filter ≥ [0.01]   Visible: 184/523                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  ▾ [root]   P0 to act   f0% chk18% b33 32% b75 41% b100 9%     EV +63 mBB    │
│    ▸ [check]                                    reach 0.180   EV +44 mBB     │
│    ▾ [bet 33%]   P1: f12% c60% r28%             reach 0.320   EV +71 mBB     │
│      ▸ [P1: fold]                               reach 0.038   EV +33 mBB     │
│      ▸ [P1: call]  → [turn]                     reach 0.192   EV +85 mBB     │
│      ▸ [P1: raise to 100%]                      reach 0.090   EV +160 mBB    │
│    ▾ [bet 75%] ← selected   P1: f8% c24% r68%   reach 0.410   EV +120 mBB    │
│      ▸ [P1: fold]                               reach 0.033   EV 0           │
│      ▸ [P1: call] → [turn]                      reach 0.098   EV +50 mBB     │
│      ▾ [P1: raise to 200%]  P0: f22% c71% rr7%  reach 0.279   EV +212 mBB    │
│        ▸ [P0: fold]                             reach 0.061   EV −200 mBB    │
│        ▸ [P0: call] → [turn]                    reach 0.198   EV +328 mBB    │
│        ▸ [P0: raise all-in]                     reach 0.020   EV +545 mBB    │
│    ▸ [bet 100%]                                 reach 0.080   EV +98 mBB     │
│    ▸ [bet all-in]                               reach 0.010   EV +60 mBB     │
│  ... 22 more low-reach nodes hidden                                          │
└─────────────────────────────────────────────────────────────────────────────┘

Legend: ▾ expanded · ▸ collapsed (lazy) · → chance node (board card)
        Action colors: red=fold, yellow=call/check, green=raise/bet
        Selected node → matrix above re-renders for that node's player.
```

**Justification.** Tree is the *navigation* element ("show me the matrix at
this history"). Prioritizes: (1) hierarchy via indentation + chevrons,
(2) inline action stats so tree doubles as readout, (3) reach filter on top
because without it the long tail dominates real spots. Selected-node
highlight is essential — without "you are here," users get lost when the
matrix above changes.

---

## Part 2 — Pro/con debates on six design decisions

### Debate 1 — Tree browser style: nested list vs. tabs-per-street vs. graph

**Option A — Expandable nested list (recommended).** Indented tree à la file
explorer. Click chevron to expand, click node to select.
- Pros: matches Pio convention; handles unbounded depth (postflop trees
  go 4–10 levels); NiceGUI native widget.
- Cons: narrow on wide monitors; hard to compare siblings without scrolling.

**Option B — Tabs-per-street.** Tabs `[Flop][Turn][River]`; each tab shows
that street's actions flat.
- Pros: more horizontal real estate; lower cognitive load for drill-down.
- Cons: hides the causal chain ("if SB bets, BB calls, turn comes…"); matrix
  needs full history conditioning; no standard solver uses this layout.

**Option C — Interactive graph (D3/Cytoscape).** Rectangles + edges, zoom/pan.
- Pros: visually striking; full tree topology; good for screenshots.
- Cons: pan/zoom is added navigation; doesn't compose with NiceGUI/Vue;
  HUNL trees have >10⁴ nodes; multi-week implementation, out of budget.

**Recommendation: A.** Matches Pio convention (users already fluent); ships
in days; uses native widget; correctly handles unbounded depth. Horizontal
real-estate concern mitigated by inline action stats (mockup 1.5). Graph
option is appealing for v3 but cannot justify cost for PR 10.

---

### Debate 2 — Range matrix interaction: click, hover, or both

**Option A — Click only.**
- Pros: simple; keyboard-accessible (focus + Enter).
- Cons: every detail requires a click; slow scanning.

**Option B — Hover only.**
- Pros: zero-click; tooltips flash on scan.
- Cons: cannot pin a view; useless on touch; cannot copy infoset key.

**Option C — Both (recommended).** Hover shows quick tooltip (cell-aggregate
freq + combo count). Click opens persistent inspector strip below.
- Pros: progressive disclosure (scan + inspect); matches GTOW; touch-degrades.
- Cons: two interactions to document; slightly more code.

**Recommendation: C.** Hover for tier-1 (aggregate %), click for tier-2
(per-combo distribution + EV + infoset key). Matches spec §3.3 ("show numeric
frequencies on hover") and GTOW precedent. The two-tier model serves both
"scanning to find interesting cells" and "interrogating one deeply" without
either interfering.

---

### Debate 3 — Live solve chart: log scale vs. linear scale

**Option A — Linear.**
- Pros: familiar; ground-truth (no transform between data and pixels).
- Cons: DCFR exploitability decays geometrically — after ~100 iters the
  curve hugs the X-axis and "converging" vs "stuck" are visually identical.

**Option B — Log (recommended).**
- Pros: geometric decay → straight line, slope = convergence rate; full
  dynamic range visible (1e3 mBB → 1e-2 mBB legible); matches paper
  convention (Brown, Sandholm) — users coming from papers will read correctly.
- Cons: requires `ui.echart` (not `ui.line_plot`); some users misread log.

**Option C — Both (toggle).** Default log, toggle to linear.
- Pros: serves both audiences; ~5 LOC.
- Cons: one more control.

**Recommendation: B with C as flag.** Log by default because the data is
exponential. Linear toggle cheap to add as escape hatch. Spec §13.8
pre-decides this; debate here is a sanity check.

---

### Debate 4 — Settings location: dedicated page vs. drawer vs. inline

**Option A — Dedicated settings page** (`/settings` route).
- Pros: clean separation; scales to many settings.
- Cons: overkill for ~5 prefs in PR 10; nav cost (click → set → navigate
  back) every time the user flips dark mode.

**Option B — Side drawer.** Collapsible from right edge.
- Pros: visible without leaving main view; matches VS Code, Figma.
- Cons: takes real estate when open (competes with matrix);
  one-time-toggles don't need a permanent surface.

**Option C — Inline contextual + `☰` header menu (recommended).** Dark mode
toggle in header. Log-scale toggle by chart. "Show frequencies" toggle
by matrix. Backend toggle by Solve. `☰` for rare prefs (state file, presets,
panel widths).
- Pros: zero-click for frequent prefs; settings visible in context; no
  separate page/drawer to maintain.
- Cons: prefs scattered (no "Reset all"); small toggles pollute main UI.

**Recommendation: C.** PR 10 has ~5 prefs, each attached to a specific
region. Dedicated page is overkill; drawer competes with matrix. The `☰`
menu absorbs global prefs (state path, presets) so inline toggles stay
local. If PR 11+ adds 20+ prefs, revisit to A.

---

### Debate 5 — Save/load library: list vs. preview grid vs. search-first

**Option A — List (recommended for PR 10).** Scrollable list of saved spots
with metadata column (board, stacks, saved date).

```
┌─────────────────────────────────────────────────────────────────────┐
│ SOLVE LIBRARY      Filter: [______________]           (3 entries)   │
├─────────────────────────────────────────────────────────────────────┤
│ ▢ AKo vs QQ on K72r       100bb · flop · 2026-05-19 · 2.1 mBB       │
│ ▢ 4bp 3-bet pot           100bb · flop · 2026-05-18 · 0.8 mBB       │
│ ▢ River-only subgame      100bb · river · 2026-05-15 · 0.1 mBB      │
│ [Load selected]  [Delete]    PR 11: persistence not yet wired       │
└─────────────────────────────────────────────────────────────────────┘
```

- Pros: simple at any size; minimal code; PR 10 is stub anyway (spec §3.5).
- Cons: no visual previews; names alone.

**Option B — Preview grid.** Thumbnails of each spot's range matrix.
- Pros: visually distinctive ("I want the mostly-green one"); modern aesthetic.
- Cons: thumbnail generation = render each matrix; overwhelming at 50+ spots;
  out-of-scope for PR 10 stub.

**Option C — Search-first.** Modal opens to search box.
- Pros: scales to thousands; keyboard-friendly.
- Cons: no zero-keystroke browse; overkill at PR 10 scale (3 stub, ~10 real).

**Recommendation: A for PR 10; B as PR 12 polish.** Library is a stub
(spec §3.5); list is the smallest stub that exercises wiring. Preview grid
warranted once libraries grow past ~20 entries. Search-first only at >100.

---

### Debate 6 — Default theme: dark vs. light vs. auto

**Option A — Light default.**
- Pros: neutral/scientific feel; Pio's red/yellow/green designed against white.
- Cons: ~60% of developers prefer dark (per SO/GitHub surveys); hard on eyes
  in long sessions.

**Option B — Dark default.**
- Pros: matches dev expectation; easier on eyes for long sessions.
- Cons: red/yellow/green blend reads murky on dark; needs desaturated palette;
  accessibility care (low-contrast hovers).

**Option C — Auto (recommended).**
- Pros: respects OS-level choice; NiceGUI `dark=None` native; spec §13.1
  pre-decides.
- Cons: a small population wants explicit override.

**Recommendation: C with header-toggle override.** Matches spec §13.1; costs
nothing; degrades to A or B based on OS. Toggle handles override edge case.
Persisted in `state.json::ui_prefs.dark_mode`.

---

## Part 3 — Edge cases & error states

### 3.1 Long solves (> 5 minutes still computing)

Status badge transitions through phases as the solve runs:

```
0–10s:    Status: running    Iter: 247/2000    Wall: 8.2s    Expl: 124 mBB/pot
10s–1m:   Status: running    Iter: 1247/2000   Wall: 47s     Expl: 8.4 mBB/pot
1m–5m:    Status: running    Iter: 8200/2000   Wall: 4m 12s  Expl: 0.92 mBB/pot
> 5min:   Status: running ⏳  Iter: 19000/200000  Wall: 7m 03s  Expl: 0.04 mBB/pot
          Note: large spots may take 30+ min. Pause/Stop still work.
          [Pause] [Stop]                  ETA (extrapolated): ~12 more min
```

⏳ glyph + note appear after 5 min; ETA after 30 s (enough decay slope to
extrapolate). Chart stays live. Why: a 30-min solve needs reassurance the
app hasn't hung — wall-clock + iter + decreasing exploitability give three
independent forward-progress signals. If any freezes, user knows.

### 3.2 Cancel mid-solve

User clicks `Stop`:

```
Click → button greyed for ~200 ms while flag propagates →
Status: stopped    Iter: 1247/2000    Wall: 47s    Expl: 8.4 mBB/pot
[Solve] [Pause] [Stop]               Last solve preserved. Click [Solve] to extend.
```

Matrix continues showing the partial-solve strategy (iter-1247 snapshot);
tree browser usable. Cancel is non-destructive: re-clicking `Solve`
continues if same spot, fresh if spot changed. Why: a stopped solve is a
valid solve — user explicitly stopped, presumably because they saw enough.
Don't throw away their work.

### 3.3 Unsupported config (e.g. 200 BB before PR 9 lands)

The user enters stack=200 BB before HUNL preflop ships. On `Solve` click:

```
┌── Notification ────────────────────────────────────────────────────────┐
│  Cannot solve this spot                                                │
│  ────────────────────────────────────────────────────────────────────  │
│  HUNL preflop solving requires PR 9 (not yet landed).                  │
│  Current support: postflop with 100 BB stacks (default).               │
│  Try:                                                                  │
│   • Set the board to 3+ cards (flop, turn, or river)                   │
│   • Or lower stacks to ≤100 BB                                         │
│   • Or use push/fold charts (Stack ≤15 BB)                             │
│  [Dismiss]                                                              │
└────────────────────────────────────────────────────────────────────────┘
```

`Solve` stays enabled; UI state untouched so the user can adjust and retry.
Why: don't silently fail or disable the button (user wouldn't know why).
Concrete remediations beat "see docs."

### 3.4 Push/fold dispatch (10 BB → chart lookup)

When the user sets stacks ≤ 15 BB, a yellow warning toast appears
*immediately* (on stack-input blur):

```
┌── Warning toast ────────────────────────────────────────────────────────┐
│ ⚠ At ≤15 BB, push/fold charts are recommended.                          │
│   The solver still runs, but charts are precomputed for this regime.    │
│   [ Switch to push/fold view ]   [ Dismiss & solve anyway ]             │
└─────────────────────────────────────────────────────────────────────────┘
```

If the user clicks `Switch to push/fold view`, the run panel changes:
solve buttons replaced with a chart-lookup readout (player position +
stack → fixed strategy). No iteration counter, no exploitability chart.

```
┌── PUSH/FOLD MODE ──────────────────────────────────────────────────────┐
│  Stack: 10 BB    Position: SB / BTN    Source: PR 3.5 chart            │
│  ─────────────────────────────────────────────────────────────────────  │
│  Push (shove): AA-22, AKs-A2s, AKo-ATo, KQs-K9s, QJs-T9s, JTs (28%)    │
│  Fold:         all others                                              │
│  ─────────────────────────────────────────────────────────────────────  │
│  Range matrix below shows push/fold visually. Tree browser disabled    │
│  (single decision: push or fold).                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

Why: push/fold is conceptually different (chart lookup, not iteration). UI
surface reflects this — hide controls that don't apply (iterations, pause),
show what does (chart attribution, range matrix). Toggle lets user override
if they want to test the solver's agreement with the chart.

### 3.5 Memory budget abort (14 GB ceiling)

A solve runs into the 14 GB memory ceiling (a known engine guard from
abstraction PR 4). The worker thread catches the abort and reports:

```
Status: ✕ aborted: memory ceiling hit (14.2 GB)
Iter: 8400/100000    Wall: 4m 02s    Expl: 0.78 mBB/pot

┌── Notification ────────────────────────────────────────────────────────┐
│  Solve aborted to protect your system.                                 │
│  The solver hit the 14 GB memory ceiling at iteration 8400.            │
│  Partial result preserved — exploitability dropped to 0.78 mBB/pot.    │
│                                                                        │
│  To get further convergence, try:                                      │
│   • Reduce bet-size menu (uncheck e.g. 150%, 200%)                     │
│   • Lower the postflop raise cap                                       │
│   • Use a smaller card abstraction (engine flag, advanced)             │
│   • Save the partial result and resume later                           │
│  [ Reduce bet sizes ] [ Dismiss ]                                       │
└────────────────────────────────────────────────────────────────────────┘
```

Status badge turns dark red; partial strategy preserved; `Reduce bet sizes`
quick-action removes the largest active bet sizes. Why: a memory abort is
system-protective, not user-error. Frame it that way ("protect your
system"), give quantitative ground truth (14.2 GB, iter 8400, expl 0.78),
offer concrete remediation. Quick-action button reduces friction.

---

## Part 4 — Onboarding (first-time users)

A three-step non-blocking modal shown on first launch (no `state.json`).

### Step 1 — Pick position + stack

```
┌─── Step 1 of 3 — Pick a starting position ───────────────────────┐
│  poker-solver is a GTO solver for heads-up no-limit hold'em.     │
│  Stacks:    P0 [100] BB    P1 [100] BB    (100 BB recommended)   │
│  Position:  (● SB acts first)   (locked HUNL)                    │
│                                  [ Skip ]  [Next →]              │
└──────────────────────────────────────────────────────────────────┘
```

### Step 2 — Set the board (or skip for preflop)

```
┌─── Step 2 of 3 — Set the board ──────────────────────────────────┐
│  Pick 3-5 cards or leave empty for preflop. Flop recommended.    │
│  Quick presets:                                                  │
│   [ K♥ 7♥ 2♦  (default 100BB postflop) ]                          │
│   [ A♠ K♥ 5♦  (3-bet pot flop) ]                                  │
│   [ — empty — (preflop) ]                                         │
│                            [← Back]  [ Skip ]  [Next →]          │
└──────────────────────────────────────────────────────────────────┘
```

### Step 3 — Solve → see results

```
┌─── Step 3 of 3 — Run the solver ─────────────────────────────────┐
│  Click [ Solve ]. About 2000 iters ≈ 30 s on a laptop.           │
│  Watch:                                                           │
│   • Live exploitability chart (lower = closer to GTO)            │
│   • Iteration + wall-clock counters                              │
│   • Matrix updates as strategy converges                         │
│  Pause/stop anytime. After: click matrix cells or tree nodes.    │
│                                                                  │
│  Matrix colors:  ███ green = raise / bet                          │
│                  ▒▒▒ yellow = call / check                        │
│                  ░░░ red = fold                                   │
│                                  [← Back]  [ Finish ]            │
└──────────────────────────────────────────────────────────────────┘
```

**Why three steps.** Minimum to teach (a) configure a spot, (b) run the
solver, (c) inspect matrix + tree. The color legend is the only domain
knowledge users *must* internalize before reading the matrix — teach it
once rather than expecting reverse-engineering.

---

## Summary table — design decisions

| # | Decision               | Recommendation                | Confidence  |
|---|------------------------|-------------------------------|-------------|
| 1 | Tree browser style     | Nested list (Pio convention)  | High        |
| 2 | Matrix interaction     | Both (hover quick, click deep)| High        |
| 3 | Chart scale            | Log default, linear toggle    | High        |
| 4 | Settings location      | Inline contextual + ☰ menu    | **Medium**  |
| 5 | Save/load library      | List for PR 10 (stub anyway)  | High        |
| 6 | Default theme          | Auto (system preference)      | High        |

**Weakly held (user judgment calls):**
- **Settings location (4)** — contextual scattering is faster for daily use
  but feels less polished than a unified panel.
- **Combo inspector position (mockup 1.4)** — strip below the matrix uses
  vertical space; could equally well be a right-side panel or a popover.
  Below-matrix is recommended because the matrix is wide, not tall.
- **Bet-size checkbox defaults (mockup 1.3)** — 33/75/100/allin checked vs.
  33/75/100/150/200/allin checked is a UX taste call. Spec §3.2 defaults
  all six to checked; the mockup follows the spec but a "less is more"
  default of 3-4 sizes might serve newcomers better.

---

## Cross-references

- `pr10_spec.md` §3 — view inventory and layout sizing.
- `pr10_spec.md` §13.1 — dark mode auto recommendation (formalized here).
- `pr10_spec.md` §13.8 — log-scale chart recommendation (formalized here).
- `pr10_spec.md` §11 — critical correctness items (matrix combo mapping; do
  not violate when implementing these mockups).
- `competitor_ui_deep_dive.md` (pending) — Pio, GTOW, DeepSolver UI
  conventions; update inline citations when this lands.
- `ui_design_principles.md` (pending) — color blend, progressive disclosure,
  three-tier information density; update inline references when this lands.
