# PR 10a spec — NiceGUI scaffold against a MOCK solver (UX-informed)

## 0. Why this PR was split out of PR 10

The original PR 10 spec (`docs/pr10_prep/pr10_spec.md`, 1227 lines) wired the
NiceGUI scaffold directly to the real `solve_hunl_postflop` path from PR 5 and
the preflop solver from PR 9. That coupling is **structurally unnecessary**:
the UI consumes a small public surface (`HUNLSolveResult`, `MemoryReport`,
`HUNLConfig`, the `Range`/`Combo` types) whose **shapes are already locked**
after PR 1 (`SolveResult`) and PR 5 (`HUNLSolveResult` + `MemoryReport`).
Everything downstream of PR 5 (PR 6 Rust port, PR 7 Brown parity, PR 8 SIMD,
PR 9 preflop) preserves those shapes without altering them.

The split:

- **PR 10a (this spec)** — UI scaffold + a MOCK solver module that produces
  realistic `HUNLSolveResult` instances. Ships against the public surface as
  it stands after PR 5. **Can start as soon as PR 5 lands**; does NOT block on
  PR 6 / 7 / 8 / 9. Compresses the project calendar by 3–4 days.
- **PR 10b** (separate spec, `pr10b_spec.md`) — replaces `ui/mock_solver.py`
  with the real `solve_hunl_postflop` (and PR 9's preflop solver). Mechanical
  swap; ~1–2 day effort.

This is PR 10a. Read `pr10_spec.md` for the long-form structural design
intent, refined by the UX research stream summarized in §2 below.

## 0.1 Locked design decisions (2026-05-22 synthesis)

All seven open design questions locked based on three landed UX research
inputs: `competitor_ui_deep_dive.md` (863L), `ui_design_principles.md`
(421L), `ui_mockups_and_debates.md` (611L). Each lock cites explicit
evidence; §8 below references this block. Agents A/B/C inherit as fixed.

**Q1 — Two-pane** (matrix center + collapsible right sidebar with three
`ui.expansion` panels: spot input / run panel / tree browser).
  Evidence: `competitor_ui_deep_dive.md` §Synthesis "Top 3 patterns to
  deliberately avoid" #1 (Pio/Monker maximalism); §PioSolver "What feels
  clunky / dated" #1; §Honorable mentions Shark README ("reduce clutter
  and cognitive load"); `ui_design_principles.md` §3.1 ("matrix is the
  centerpiece; tree+settings are secondary").
  Why: 4-pane maximalism is the explicit cross-doc anti-pattern. Sidebar
  collapsibles preserve "set once, solve repeatedly" with half the panes.

**Q2 — Hand-class labels visible in cells** (upper-left "AKs", "QQ";
numeric frequencies on hover).
  Evidence: `competitor_ui_deep_dive.md` §Synthesis "Common patterns
  across all 4" #1 (13×13 matrix + labels universal across Pio, GTOW,
  Monker, DeepSolver); §PioSolver "Visual design language".
  Why: All four competitors show labels in-cell — muscle-memory baseline.
  Numbers-on-hover rule (`ui_design_principles.md` §2.5) governs
  *frequencies*, not labels. At 54 px cells, labels cost zero scan time.

**Q3 — Default 1000 iterations** (target-exploitability mode opt-in).
  Evidence: `competitor_ui_deep_dive.md` §DeepSolver "What it does
  brilliantly" #1 ("result in just few seconds"); §GTO Wizard "What it
  does brilliantly" #2 (6 s vs Pio's 4,862 s); §Synthesis "Top 3 UI
  patterns to adopt" #3 ("Live exploitability curve").
  Why: Fast first-feedback is the largest UX divergence between modern
  solvers and Pio. 1000 iters @ ~15 s mock_latency feels interactive.

**Q4 — 4-of-6 bet sizes default** (33% / 75% / 100% / all-in checked).
  Evidence: `competitor_ui_deep_dive.md` §DeepSolver "Patterns we should
  adopt" #1 (Smart Tree Builder with custom override); §Synthesis "Where
  they diverge sharply" #1 ("Sensible defaults + progressive
  disclosure ... closer to DeepSolver / Shark"); §Appendix (Shark
  baseline = 3–4 sizes per street).
  Why: Shark defaults are 3–4 sizes; 6-of-6 is Pio's "every knob exposed"
  anti-pattern. 4-of-6 halves first-solve tree size.

**Q5 — Combo inspector below matrix** (full-width horizontal strip).
  Evidence: `competitor_ui_deep_dive.md` §GTO Wizard "Core UX flow" #3
  ("per-action EV panel below the matrix"); §Synthesis "Common patterns"
  #5.
  Why: GTOW established below-matrix convention. Preserves the right
  sidebar for the Q1-locked expansion panels. Matrix is wide-not-tall.

**Q6 — Reach threshold default 0.01** (filter slider visible above tree).
  Evidence: `competitor_ui_deep_dive.md` §Synthesis "Top 3 UI patterns
  to adopt" #2 (progressive-disclosure); `ui_design_principles.md` §5
  ("Tree-browser default collapse: First-level children expanded, deeper
  collapsed").
  Why: HUNL trees have 10⁴–10⁶ nodes; 0.01 hides leaves with <1% reach
  (study-irrelevant). Slider visible → power users find it by playing.

**Q7 — Yellow "Mock mode" banner** across the top, dismissible (downgrades
to subtle `(mock)` chip in PR 10b).
  Evidence: `competitor_ui_deep_dive.md` §DeepSolver "What feels clunky
  / dated" #1 ("accuracy claims aren't independently verifiable");
  §PioSolver "Patterns we should NOT adopt" ("Marketing-driven accuracy
  claims ... without a published reproducible benchmark"); §Synthesis
  "Top 3 patterns to deliberately avoid" #3 (NN-warm-start opacity).
  Why: PR 10a outputs are hand-crafted fixtures. Auditability requires
  loud disclosure for the first 30 s of every session. Subtle chip is
  fine post-PR-10b when outputs are real.

**Coin-flip flag:** Q3 (1000 vs 2000) is the most arbitrary lock —
competitor evidence supports "fast feedback" directionally but pins no
exact integer. If PR 10a manual testing shows under-converged matrices,
raise to 2000 in PR 10b.

**Dissent footnote (Q1):** `ui_mockups_and_debates.md` mockup 1.1 recommends
4-pane ("set once, solve repeatedly"). Both other docs (deep-dive
anti-pattern flag + design principles §3.1/§8.1 explicit 2-pane recommendation)
outweigh the single mockup-doc opinion; the "set once" ergonomic survives
by stacking panels as collapsibles inside the sidebar.

## 1. Goal

Ship a NiceGUI app that EXERCISES the full UX — spot input, range matrix
display, decision tree browser, live exploitability chart, library stub —
against a mock solver. The mock returns realistic `HUNLSolveResult` outputs
for a fixed set of pre-curated spots; the UI consumes them through the same
public types the real solver will use.

The UI is the **exact same artifact** PR 10b will ship — only the contents of
`ui/mock_solver.py` change between PR 10a and PR 10b.

By the time PR 10a lands the user can:
- `poker-solver ui` launches the two-pane layout (header + matrix center
  + collapsible right sidebar stacking spot input / run panel / tree browser
  expansion panels; Q1 locked in §0.1).
- Pick a fixture preset (river subgame, dry flop K72r, wet flop, monotone,
  paired, turn 4-flush, deep stack, short stack, etc.).
- Configure ranges, stack depth, board, bet sizes, raise caps, iterations.
- Click **Solve** and watch the live (log-scale) exploitability chart decay
  over simulated wall-clock; the range matrix updates between snapshot ticks.
- Pause / Stop / Resume with worker reacting within one simulated iteration.
- Click a tree node and have the matrix re-render conditioned on that node.
- Click a matrix cell and inspect per-combo action distribution.
- Open the library dialog from the header (stub; PR 11 wiring point).
- Exercise failure modes (OOM, NotImplementedError, cancellation) via a
  hidden test knob.

## 2. UX design principles (cited from supporting docs)

Long-form research lives in three parallel-agent supporting documents.
This section is the operational reference; each line is a **one-sentence
summary + citation**. The supporting docs hold the full argument.

| Source | Path | Status |
|---|---|---|
| Competitor UI deep-dive | `docs/pr10_prep/competitor_ui_deep_dive.md` | **AVAILABLE** (863 lines, 2026-05-22) |
| UI design principles | `docs/pr10_prep/ui_design_principles.md` | **AVAILABLE** (421 lines, 2026-05-22) |
| Mockups + pro/con debates | `docs/pr10_prep/ui_mockups_and_debates.md` | **AVAILABLE** (611 lines, 2026-05-22) |

### 2.1 Nine load-bearing design principles (from `ui_design_principles.md` §2)

1. **Defaults first, settings on demand** (§2.1). Every panel renders
   meaningful state before user touches anything. Pre-loaded default
   spot, `Solve` clickable immediately.
2. **Single visible primary action per view** (§2.2). One bright green
   button per region. Pause/Stop are `flat` secondary.
3. **Domain-native terminology** (§2.3). "Raise to 3 BB" not "increase
   aggressive action sizing". Acronyms (MDF, EV, mBB) keep their form.
4. **Color minimalism, Pio convention reused** (§2.4). Strategy palette:
   exactly three colors (R/Y/G). Range-input palette: white→blue, disjoint.
5. **Numbers always visible on hover** (§2.5). Color is heatmap summary;
   tooltip is ground truth. Click is reserved for state changes.
6. **No modal dialogs for routine operations** (§2.6). Settings → side
   panels or inline. Modals only for fatal errors + PR 11-stub library.
7. **Keyboard shortcuts: discoverable, not required** (§2.7). Every
   shortcut has a button; 3-second dwell tooltip teaches them on first use.
8. **Live feedback during solve** (§2.8). Chart every 500 ms. Iteration
   counter ticks. User never wonders "did it hang?"
9. **Honest error messages** (§2.9). Every error tells user what went
   wrong, which input caused it, what to do next. No stack traces in toasts.

### 2.2 Eight anti-patterns to actively avoid (from `ui_design_principles.md` §3)

1. **Three-pane "Windows 95" layouts** (§3.1) — original PR 10 §3 four-pane
   layout is explicitly flagged. **See §3 below for the layout
   amendment.**
2. **10+ items in any dropdown** (§3.2). Preset dropdown OK at 3 entries;
   replace with searchable list past 10.
3. **Tiny clickable areas (< 24 px)** (§3.3). 13×13 matrix at 700 px wide
   gives 54 px cells — fine.
4. **Modal configuration dialogs every other click** (§3.4). Library stub
   is OK as modal; settings must not be.
5. **Cryptic acronyms without tooltips** (§3.5). MDF, EV, SDR, C/R%, BvB,
   SRP, RFI, VPIP, PFR all need hover-tooltips.
6. **"Are you sure?" confirmations on undoable actions** (§3.6). Clearing
   the board, resetting the spot, switching presets — no confirmation.
7. **Hiding required input fields under "advanced settings"** (§3.7).
   Required ≠ advanced.
8. **Dense tables of numbers without color** (§3.8). Combo inspector at
   risk; must use Pio palette on action bars, copy-icon for infoset key.

### 2.3 Four-tier progressive disclosure (from `ui_design_principles.md` §4)

- **Tier 1 (zero clicks):** 13×13 matrix, current spot label, `Solve`
  button, live expl chart, strategy summary line, decision tree (root +
  first level), backend + iteration counter while solving.
- **Tier 2 (one click / hover):** per-combo numeric frequencies, action-
  distribution bar, tree node selection conditioning matrix, decision-
  tree-as-text view toggle, per-action EV at each tree node, reach-
  probability filter.
- **Tier 3 (settings drawer / inline toggles):** iteration count override,
  bet-size customization, raise caps, abstraction tier override, backend
  selector, dark mode, panel layout reset, raw infoset toggle, memory
  profile readout.
- **Tier 4 (CLI / library API):** debug logging, profiler output, regret
  table dumps, tree-builder internals.

### 2.4 Locked design decisions (from `ui_design_principles.md` §5)

| Decision | Locked value |
|---|---|
| Default theme | **Auto (system preference)** with manual override toggle |
| Font (numbers) | Monospace (SF Mono / Menlo / Consolas) |
| Font (labels) | Sans-serif (SF Pro / Inter / Segoe UI) |
| Mobile support | Explicit non-goal for v1; desktop browser only |
| Keyboard nav | Arrow keys + Tab + Cmd-Enter / Esc. No vim bindings |
| Animation | Minimal; only for state changes (no decorative transitions) |
| Loading states | Skeleton screens for ≥ 500 ms ops, NOT spinners |
| Color palette | Pio R/Y/G for strategy + grayscale + Quasar primary blue |
| Range-input matrix palette | White → saturated blue (disjoint from strategy) |
| Splitter resizability | Yes, persisted in `~/.poker_solver_ui/state.json` |
| Tree-browser default collapse | First-level children expanded, deeper collapsed |

## 3. Layout amendment (resolves anti-pattern §3.1; Q1 locked → two-pane)

The original PR 10 spec §3 proposed a 4-pane layout. `ui_design_principles.md`
§3.1 flags it as Pio's signature pain point; `competitor_ui_deep_dive.md`
§Synthesis "Top 3 patterns to deliberately avoid" #1 calls "Maximalist
always-visible information density (Pio / Monker)" the top anti-pattern;
Shark's README is explicit: *"intentionally omitted to reduce clutter and
cognitive load."*

**Resolution:** ship two-pane — matrix center + one collapsible right
sidebar stacking spot input / run panel / tree browser as `ui.expansion`
panels (first one open by default; rest collapsed). The "set once, solve
repeatedly" vertical-stack ergonomic from `ui_mockups_and_debates.md`
mockup 1.1 is preserved inside the sidebar; matrix gains ~25% more
horizontal real estate at 1440 px. The original 4-pane ASCII mockup §4.1
below is preserved for reference; the agents implement the 2-pane
collapse described here.

## 4. View specifications (mockups + recommended alternatives)

Each view's recommended ASCII mockup is **inlined from `ui_mockups_and_debates.md`**
to avoid losing fidelity. The full justification + alternatives debate
lives in the supporting doc; this section is the operational artifact.

### 4.1 Main app shell (`ui_mockups_and_debates.md` §1.1)

```
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ poker-solver  ·  Default 100BB postflop (Kh 7h 2d)  ·  idle             [Lib] [Auto/Dk] ☰ │
├───────────────┬───────────────────────────────────────────────────────────────────────────┤
│  SPOT INPUT   │  RANGE MATRIX — root node — P0 (SB) to act                                │
│ ┌───────────┐ │                                                                           │
│ │ Board     │ │   A    K    Q    J    T    9    8    7    6    5    4    3    2          │
│ │  Kh 7h 2d │ │ A ███  ███  ███  ███  ███  ███  ▒▒▒  ▒▒▒  ░░░  ░░░  ░░░  —    —          │
│ │ [Clear]   │ │ K ███  ███  ███  ███  ▒▒▒  ▒▒▒  ░░░  ░░░  ░░░  —    —    —    —          │
│ │ Ranges    │ │ Q ███  ███  ███  ▒▒▒  ▒▒▒  ░░░  ░░░  —    —    —    —    —    —          │
│ │  [P0][P1] │ │ J ███  ███  ▒▒▒  ███  ▒▒▒  ░░░  ░░░  —    —    —    —    —    —          │
│ │ Stacks    │ │ T ███  ▒▒▒  ▒▒▒  ▒▒▒  ███  ░░░  ░░░  —    —    —    —    —    —          │
│ │ P0  100bb │ │ ... (8 more rows)                                                         │
│ │ P1  100bb │ │ ░ fold-heavy  ▒ mixed  ▓ blocked  ███ raise/call  — out of range          │
│ │ [Reset]   │ │ ┌─ Combo inspector — AKs (3 of 4 combos) ──────────────────────────────┐ │
│ │ [Preset▼] │ │ │ AsKs  ▰▰▰▰▰▰▰▰▱▱  bet75 78%  call 18%  fold 4%  EV +124  reach 0.74 │ │
│ └───────────┘ │ │ AdKd  ▰▰▰▰▰▰▰▰▱▱  bet75 76%  call 20%  fold 4%  EV +119  reach 0.74 │ │
│  RUN PANEL    │ │ AcKc  ▰▰▰▰▰▰▰▰▱▱  bet75 75%  call 21%  fold 4%  EV +117  reach 0.74 │ │
│ [Bets][Iter]  │ │ AhKh  BLOCKED — Kh on board                                          │ │
│ [Solve][...]  │ └────────────────────────────────────────────────────────────────────────┘ │
│ [chart]       ├───────────────────────────────────────────────────────────────────────────┤
│ [status]      │ DECISION TREE — reach ≥ 0.01     visible 184/523                          │
└───────────────┴───────────────────────────────────────────────────────────────────────────┘
```

**Adopted:** two-pane (per §3 resolution above; Q1 locked). The mockup's
left column collapses into the right sidebar's stacked `ui.expansion`
panels (spot input → run panel → tree browser, top-to-bottom). Header is
one line. Status colocated with run controls inside the run-panel
expansion. Header right cluster: yellow "Mock mode" banner (Q7-locked,
dismissible per §0.1), library (stub modal), theme toggle, hamburger
menu (rarely-touched prefs per Debate 4 — citing
`competitor_ui_deep_dive.md` §DeepSolver "What it does brilliantly" #1
on Smart Tree Builder's minimal-default principle).

### 4.2 Spot input panel (`ui_mockups_and_debates.md` §1.2)

Board picker: **4×13 suit-by-rank grid** (Pio convention). Chip strip
at top shows selected cards with `[×]` remove affordance. Auto-detects
street (3=flop, 4=turn, 5=river).

Range input: **player tabs** (P0/P1) + **mode toggle (String / Matrix)**.
Matrix mode default — visual paint; click to cycle 1.0→0.5→0.25→0.0;
shift-click → freq slider. Live string preview underneath ("AA,KK-TT,
AKs,AQs,..."). Combo counter ("124 / 1326   ( 9.4% )") for numeric ground
truth.

Stacks: `P0 [100  ] BB    P1 [100  ] BB`. If ≤ 15 BB → warning toast
recommending push/fold charts (see §4.6 edge cases).

Position: locked HUNL (SB acts first). Disabled toggle with explainer
tooltip.

Blinds & ante: collapsed `ui.expansion`. (Anti-pattern §3.7 caveat: if
the default values don't cover the typical case, surface them.)

[Reset spot] [Load preset ▼] at the bottom.

**Adopted alternative for range input:** matrix mode default (lower
barrier; visual painting) per the §1.2 justification. Alternative was
"string-first" — rejected because new users can't write range strings.

### 4.3 Run panel + live solve view (`ui_mockups_and_debates.md` §1.3)

```
┌────────────────────────────────────────────┐
│ Bet sizes (% pot)                          │
│  ☑ 33%   ☑ 75%   ☑ 100%                    │
│  ☐ 150%  ☐ 200%  ☑ all-in                  │
│  Custom: [0.5, 1.2___________]              │
│ Raise caps:  Preflop [4]   Postflop [3]    │
│ Iterations [2000_____]                      │
│ Backend    ( ● Python   ○ Rust )           │
├────────────────────────────────────────────┤
│  [  Solve  ]   [ Pause ]   [ Stop ]        │
├────────────────────────────────────────────┤
│ Exploitability (mBB/pot, log scale ☑)      │
│ ┌──────────────────────────────────────┐   │
│ │1e3┤●                                 │   │
│ │1e2┤  ●●●                             │   │
│ │1e1┤        ●●●●●●●                   │   │
│ │1e0┤                ●●●●●●●●●●●●●●    │   │
│ │   └──────────────────────────────────│   │
│ │   0    500   1k    1.5k   2k         │   │
│ └──────────────────────────────────────┘   │
│  Status:    running                        │
│  Iter:      1,247 / 2,000  (62%)           │
│  Wall:      18.4 s                         │
│  Expl:      3.2 mBB / pot                  │
│  Backend:   python                         │
└────────────────────────────────────────────┘
```

**Adopted: log-scale exploitability chart by default with linear-toggle
escape hatch** (Debate 3 recommendation, high confidence). Log axis is
NiceGUI's `ui.echart` not `ui.line_plot`; +30 LOC, worth it. Cited from
original PR 10 spec §13.8 + `competitor_ui_deep_dive.md` §PioSolver
"What feels clunky / dated" #3 ("no live exploitability curve during
solve" — the gap GTOW closed and we close too).

**Adopted: three distinct buttons (Solve/Pause/Stop)** color-coded
green/yellow/red. Status word swaps color per state
(running/paused/done/stopped/error). Solve disabled while running
(visible, not hidden).

**Adopted (Q4 locked): bet-size checkboxes (33/75/100/150/200/AI),
default 4 of 6 checked (33/75/100/AI).** Citing
`competitor_ui_deep_dive.md` §DeepSolver "Patterns we should adopt" #1
("Smart Tree Builder default with custom override") and Shark's
known-good baseline (cited in `competitor_ui_deep_dive.md` §Appendix:
"flop 50/100, turn/river 33/66/100, raise 50/100, cap 3"). Maximalist
6-of-6 is Pio's "every knob exposed" anti-pattern flagged in
`competitor_ui_deep_dive.md` §PioSolver "Patterns we should NOT adopt"
#1.

**Adopted (Q3 locked): iteration count as number input, default 1000.**
Citing `competitor_ui_deep_dive.md` §DeepSolver "What it does
brilliantly" #1 ("cloud returns a result in just few seconds") +
§GTO Wizard "What it does brilliantly" #2 (6-second custom solves):
fast first-feedback is the largest UX divergence between modern solvers
and Pio. 1000 iters @ default mock_latency ~15 s feels interactive.
Target-exploitability mode (TexasSolver pattern, adopted #7) is the
opt-in alternative for users who want "solve until < 0.5 mBB."

### 4.4 Range matrix display (`ui_mockups_and_debates.md` §1.4)

Two on-cell signals per cell:
- **Color blend** (additive RGB per PR 10 §7.3): fold→red, call/check→
  yellow, raise/bet→green.
- **2-letter + percentage tag**: `R 78%` (raises 78%), `C 50%` (calls
  50%), `F xx%` (folds), or `MIX` if no action > 50%, or `BLK` for
  blocker-removed.

Hover → tooltip with cell-aggregate frequencies + combo count + EV.
Click → opens persistent combo inspector strip below the matrix.

**Adopted: matrix interaction = both hover and click** (Debate 2, high
confidence). Hover gives quick scan; click gives deep inspect with
copyable infoset key. Matches GTOW convention per
`competitor_ui_deep_dive.md` §Synthesis "Where they diverge sharply"
#4 ("Hover-to-reveal numbers: GTOW, DeepSolver (cleaner default view;
numbers on cell hover)"); users will recognize.

**Adopted (Q5 locked): combo inspector strip position = below the
matrix.** Citing `competitor_ui_deep_dive.md` §GTO Wizard "Core UX
flow" #3 ("per-action EV panel below the matrix") and §Synthesis
"Common patterns across all 4" #5 ("Per-action EV + frequency display
near or below the range matrix"). Below-matrix is GTOW's established
convention; preserves the right sidebar for spot input + run panel
+ tree browser collapsibles (Q1 layout).

**Adopted: blocker treatment = slashed-diagonal overlay** (`╳╳╳`) +
tooltip "all combos blocked by board card X" (matches postflop-solver
convention; cited in `competitor_ui_deep_dive.md` §Honorable mentions
WASM Postflop reference).

**Adopted (Q2 locked): cell labels = show hand-class shorthand
("AKs", "QQ", "72o") in upper-left, with numeric frequencies revealed
on hover.** Citing `competitor_ui_deep_dive.md` §Synthesis "Common
patterns across all 4" #1 (13×13 matrix universal across all four
competitors) and §PioSolver "Patterns we should adopt"
(industry-standard color triad on the range matrix). All four
competitors show labels in-cell; numbers-on-hover rule
(`ui_design_principles.md` §2.5) governs *frequencies*, not labels.
At 54 px cells labels cost zero scan time and provide first-run
learnability for newcomers.

### 4.5 Decision tree browser (`ui_mockups_and_debates.md` §1.5)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ DECISION TREE  Reach ≥ [0.01_]  Visible: 184 / 523                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ▾ [root]                                       reach 1.000   EV +63 mBB         │
│    │   P0 to act    fold 0%   check 18%   bet33 32%   bet75 41%   bet100 9%      │
│    ▸ [check]                                     reach 0.180   EV +44 mBB        │
│    ▾ [bet 75%]  ← selected                       reach 0.410   EV +120 mBB       │
│    │     P1 to act   fold 8%   call 24%   raise 68%                              │
│    │   ▸ [P1: fold]                              reach 0.033   EV  0 mBB         │
│    │   ▸ [P1: call]  → [turn]                    reach 0.098   EV +50 mBB        │
│    │   ▾ [P1: raise to 200%]                     reach 0.279   EV +212 mBB       │
│    ▸ [bet 100%]                                  reach 0.080   EV +98 mBB        │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Adopted: expandable nested list** (Debate 1, high confidence). Matches
Pio convention per `competitor_ui_deep_dive.md` §Synthesis "Where they
diverge sharply" #3 ("Nested list: Pio, Monker, OSS competitors");
handles unbounded depth; NiceGUI `ui.tree` widget native. Alternatives
(GTOW horizontal cascade, interactive D3 graph) deferred to v2 polish
per `competitor_ui_deep_dive.md` §GTO Wizard "Patterns we should adopt"
(horizontal cascade flagged as v1-polish alternative) and §Appendix
"PR 10 spec consistency check" (cascade kept on backlog).

**Adopted: per-node action stats inline** ("fold 8% call 24% raise
68%"). Tree doubles as readout; selected-node highlight prevents user
getting lost when matrix above changes.

**Adopted (Q6 locked): reach filter on top, default 0.01.** Citing
`competitor_ui_deep_dive.md` §Synthesis "Top 3 UI patterns to adopt"
#2 ("Sensible-defaults + progressive-disclosure configuration —
Shark / DeepSolver pattern") and `ui_design_principles.md` §5
("Tree-browser default collapse: First-level children expanded, deeper
collapsed"). HUNL postflop trees have 10⁴–10⁶ nodes; 0.01 hides
leaves with <1% reach (irrelevant for study). Filter slider visible
at top of browser → power users can drop to 0.0 in one drag.

### 4.6 Library viewer (stub, modal)

`ui_mockups_and_debates.md` Debate 5: **list view for PR 10 stub.**
Three faked rows; `Load selected` and `Delete` buttons; PR 11 banner
"persistence not yet wired." Search-first and preview-grid alternatives
deferred to PR 12.

```
┌─────────────────────────────────────────────────────────────────────┐
│ SOLVE LIBRARY                                                       │
│ Filter: [_______________]                            (3 entries)    │
│ ▢ AKo vs QQ on K72r       100bb · flop · 2026-05-19 · 2.1 mBB       │
│ ▢ 4bp 3-bet pot           100bb · flop · 2026-05-18 · 0.8 mBB       │
│ ▢ River-only subgame      100bb · river · 2026-05-15 · 0.1 mBB      │
│ [Load selected]  [Delete]   PR 11: persistence not yet wired         │
└─────────────────────────────────────────────────────────────────────┘
```

## 5. Patterns adopted from competitors (and ones rejected)

Concrete patterns. Each pattern is either **adopted** or **rejected**
with reason. Sourced from `competitor_ui_deep_dive.md` (the 863-line
deep-dive landed 2026-05-22), `docs/competitor_landscape.md`,
`references/blog/piosolver_technical_details.md`,
`references/blog/gtow_how_solvers_work.md`, and the recommendations
distilled in `ui_mockups_and_debates.md`.

### Adopted

All citations below are anchored to `competitor_ui_deep_dive.md` (CDD)
sections; the deep-dive's §Synthesis is the load-bearing reference.

1. **Pio R/Y/G additive color blend.** CDD §PioSolver "Visual design
   language" + §Synthesis "Common patterns" #2 (universal triad).
   Reason: muscle memory; locked in PR 10 §7.3.
2. **GTOW "click cell → per-combo bar" inspector strip.** CDD §GTO
   Wizard "Patterns we should adopt" #4 + §Synthesis "Common patterns" #5.
   Reason: matrix = aggregate; strip = ground truth per principle 5.
3. **GTOW log-Y exploitability chart with linear toggle.** CDD
   §PioSolver "What feels clunky / dated" #3 (Pio gap) + §Synthesis
   "Top 3 UI patterns to adopt" #3. Reason: DCFR's geometric decay
   reads "stuck" on linear; log is the truthful shape (Debate 3).
4. **postflop-solver slashed-diagonal blocker overlay.** CDD §Honorable
   mentions (WASM/Desktop Postflop). Reason: distinct from "out of
   range" (grey) and "no data" (faded).
5. **Pio bet-size DSL** (comma-separated pot fractions). CDD §PioSolver
   "Patterns we should adopt" ("33,75,150 notation"). Reason: power users
   want non-default sizes.
6. **Shark per-street defaults baked in** (flop 50/100, turn/river
   33/66/100, raise 50/100, cap 3, all-in 0.67). CDD §Appendix "PR 10
   spec consistency check" + §Honorable mentions Shark. Reason: spares
   first-time user from blank-form paralysis.
7. **TexasSolver periodic-exploitability + early-stop** as opt-in
   "target exploitability" toggle. CDD §Synthesis "Where they diverge
   sharply" #1 + §DeepSolver Smart Tree Builder. Reason: real solver
   supports it (PR 5 kwarg).
8. **Pio expandable nested tree list** with file-tree indentation. CDD
   §Synthesis "Where they diverge sharply" #3 ("Nested list: Pio,
   Monker, OSS competitors"). Reason: convention + NiceGUI native.
9. **GTOW library-first entry framing.** CDD §GTO Wizard "Patterns we
   should adopt" ("Library-first entry point ... default to 'pick from
   preset'"). Reason: PR 10a preset dropdown realizes this.
10. **PioSOLVER-compatible range syntax** (`QQ+,AKs,A5s-A2s,...`). CDD
    §Synthesis "Common patterns" #4 (universal lingua franca). Reason:
    paste-from-clipboard works without translation.
11. **DeepSolver progressive-disclosure configuration.** CDD §Synthesis
    "Top 3 UI patterns to adopt" #2. Reason: cuts Pio's "8 fields
    before first solve" friction.
12. **Resumable solves via on-disk checkpoint.** CDD §PioSolver "What
    it does brilliantly" #2. Reason: PR 11 ships persistence; PR 10a
    library stub is the wire.

### Rejected

1. **Monker right-click context menus.** CDD §MonkerSolver "What
   feels clunky / dated" #5. Reason: poor discoverability.
2. **PioViewer Windows-Forms tabbed multi-tree comparison.** CDD
   §PioSolver "What feels clunky / dated" #1. Reason: scope creep.
3. **GTOW mobile-responsive collapsing-panel layout.** CDD §GTO
   Wizard "Patterns we should NOT adopt" ("Mobile-first"). Reason:
   desktop-first.
4. **Simple Postflop modal "configure tree" wizard.** CDD §Honorable
   mentions. Reason: principle 6 (no multi-step modals).
5. **TexasSolver Qt-translated multilingual progress strings.** CDD
   source list. Reason: English-only in v0.
6. **Interactive D3-graph tree view.** CDD §Synthesis "Where they
   diverge sharply" #3 ("Graph view: None of the four does this in
   production"). Reason: Debate 1 — unusable at 10⁴–10⁶ nodes.
7. **Preview-grid library viewer.** Reason: Debate 5 — thumbnail
   generation requires rendering each matrix; defer to PR 12.
8. **Cloud-only delivery / NN warm-start opacity.** CDD §Synthesis
   "Top 3 patterns to deliberately avoid" #3. Reason: local-first +
   auditable thesis is non-negotiable.
9. **Bucket-only granularity (Monker pattern).** CDD §MonkerSolver
   "Patterns we should NOT adopt" #1. Reason: v0 is per-combo HU.
10. **Textarea-only range input (Pio pattern).** CDD §Synthesis
    "Top 3 patterns to deliberately avoid" #2. Reason: matrix-mode
    default + string-preview underneath is the correct hybrid.

## 6. Edge cases and error states (from `ui_mockups_and_debates.md` §3)

Locked treatment for five edge cases; all must be implemented in
PR 10a so the mock solver's failure modes (§7.5) round-trip through a
real UI surface.

1. **Long solves (> 5 min):** ⏳ glyph + note "large spots may take 30+
   min" after 5 min. ETA extrapolated from decay slope after 30 s. Chart
   stays live. Three forward-progress signals (wall, iter, expl)
   independent so user knows if any freezes.
2. **Cancel mid-solve (stop button):** Status → "stopped"; partial
   strategy preserved in matrix. Clicking Solve again continues from
   stopped iter (same spot) or starts fresh (changed spot). Non-
   destructive.
3. **Unsupported config (e.g., 200 BB before PR 9 lands):** notification
   with three concrete remediations ("Set board to 3+ cards", "Lower
   stacks", "Use push/fold"). Button stays enabled. UI state untouched.
4. **Push/fold dispatch (≤ 15 BB):** Yellow warning toast on stack
   blur, offering "Switch to push/fold view" (PR 3.5 chart lookup;
   replaces solve buttons with chart readout) or "Dismiss & solve
   anyway". In PR 10a the mock returns a fixture for the
   `shortstack_25bb` config; PR 10b will dispatch to the real push/fold
   path.
5. **Memory budget abort (14 GB ceiling):** Dark-red status badge,
   partial strategy preserved. Notification frames as system-protective
   action ("Solve aborted to protect your system"), gives quantitative
   ground truth, offers concrete remediations + quick-action button
   ("Reduce bet sizes" removes the largest unchecked sizes from the
   menu). Implemented in PR 10a via the mock's `mock_failure_mode='oom'`
   hook.

## 7. Mock solver interface lock-in

### 7.1 Public surface

```python
# ui/mock_solver.py
from poker_solver.hunl import HUNLConfig
from poker_solver.hunl_solver import HUNLSolveResult
from poker_solver.profiler.memory import MemoryReport, StreetMemoryEntry

def mock_solve(
    config: HUNLConfig,
    iterations: int = 50_000,
    *,
    log_every: int | None = None,
    memory_budget_gb: float = 14.0,
    target_exploitability: float | None = None,
    seed: int | None = None,
    dcfr_kwargs: dict | None = None,
    on_progress: Callable[[int, float, MemoryReport], None] | None = None,
    # ---- mock-specific knobs (kwarg-only) ----
    mock_latency_ms: int = 30_000,
    mock_failure_mode: str | None = None,
) -> HUNLSolveResult:
    """Drop-in mock for solve_hunl_postflop.

    First 8 parameters byte-identical to PR 5's solve_hunl_postflop.
    Trailing mock_* args have defaults; not part of the real surface.
    """

def list_fixture_presets() -> list[FixturePreset]:
    """Return the 12 fixture spots' metadata for the UI's preset dropdown."""

def load_fixture(preset_id: str) -> HUNLConfig:
    """Materialize a preset id into a real HUNLConfig the UI consumes."""
```

**Critical lock-in:** the first 8 parameters and the return type are
byte-identical to `solve_hunl_postflop(config, iterations, *, log_every,
seed, target_exploitability, memory_budget_gb, dcfr_kwargs, on_progress)`
as defined post-PR 5 + PR 10b's one engine-side addition. The PR 10b
swap is a one-line import change.

### 7.2 UI feature → mock method mapping

| UI feature | View | Mock method | Arg shape |
|---|---|---|---|
| Preset dropdown | §4.2 | `list_fixture_presets()` | Returns `list[FixturePreset]`. |
| Preset selection | §4.2 | `load_fixture(preset_id)` | Returns `HUNLConfig`. |
| Solve button | §4.3 | `mock_solve(config, iterations, on_progress=cb)` | Worker invokes. |
| Live expl chart | §4.3 | `mock_solve(..., on_progress=cb)` | `cb(iter, expl, partial_report)` per `log_every` tick. |
| Range matrix render | §4.4 | `mock_solve(...)` return | `HUNLSolveResult.average_strategy`. |
| Tree browser | §4.5 | `mock_solve(...)` return | `SolveTree` walks game graph + strategy. |
| Combo inspector | §4.4 | `mock_solve(...)` return | Per-combo EV + reach. |
| Pause / Stop | §4.3 | Module-level `_CANCEL_FLAG` | `SolveRunner.stop()` sets; mock loop checks. |
| OOM (edge §6.5) | §4.3 | `mock_failure_mode='oom'` | Raises `MemoryError("mock OOM", partial_report)` after ~10% latency. |
| NotImplemented (edge §6.3) | §4.3 | `mock_failure_mode='not_implemented'` | Raises `NotImplementedError`. |
| Cancellation (edge §6.2) | §4.3 | `mock_failure_mode='cancelled'` | Returns `HUNLSolveResult` with `iterations < requested`. |
| Long-latency test | §4.3 | `mock_failure_mode='long_latency'` | Sleeps 10 min with progress callbacks. |
| Rapid iteration | §4.3 | `mock_failure_mode='rapid_iteration'` | Latency 100 ms; tests chart-flooding guard. |

### 7.3 MemoryReport fields the UI reads

The mock must populate these fields:
- `report.total_gb` — main metric (Tier 3 readout).
- `report.per_street` — list[`StreetMemoryEntry`] for per-street breakdown.
- `report.river_ratio` — "well-balanced" indicator (target [0.30, 0.50]).
- `report.rss_calibration_error` — "trust" indicator (target ≤ 0.10).
- `report.wallclock_per_iter_sec` — feeds ETA calculation (edge §6.1).

### 7.4 Twelve fixture spots (unchanged from prior pr10a_spec §3.2)

Hand-crafted strategies passing the poker-player eye test. Dimensions
covered: dry vs wet, monotone vs rainbow, paired vs unpaired, flop vs
turn vs river start, short vs deep, blocker-heavy vs not.

```python
_FIXTURE_SPOTS = {
    "river_tiny_subgame":  ...,  # PR 3 default_tiny_subgame
    "flop_k72r_100bb":     ...,  # dry flop
    "flop_t87s_100bb":     ...,  # wet flop (straight + flush draws)
    "flop_monotone_hhh":   ...,  # monotone hearts
    "flop_paired_q9q":     ...,  # paired board
    "turn_kqj9_4_flush":   ...,  # turn brings 4-flush
    "turn_t872_brick":     ...,  # turn brick
    "river_axxs_polar":    ...,  # river polarization
    "preflop_btn_vs_bb":   ...,  # PR 9 stub
    "river_blocker_heavy": ...,  # adversarial blocker test
    "shortstack_25bb":     ...,  # short stack postflop
    "deepstack_200bb":     ...,  # deep stack postflop
}
```

Acceptance criteria for strategies (per prior spec): realistic mixing,
no dominated actions, MDF-obeying bluff freq on rivers, polarization on
rivers and more linear on flops, blocker effects on rivers.

### 7.5 Cancellation contract

Module-level `_CANCEL_FLAG` (a `threading.Event`) set by
`SolveRunner.stop()` and checked by `mock_solve()` once per
snapshot. **Same flag as the real solver in PR 10b.**

```python
# UI-side (ui/state.py::SolveRunner.start)
def _worker(...):
    def on_progress(iter, expl, report):
        self.iteration = iter
        self.expl_history.append((iter, expl))
    try:
        result = mock_solve(config, iterations,
                            on_progress=on_progress, ...)
    except MemoryError as e: ...
    except NotImplementedError as e: ...

# Mock-side
def mock_solve(..., on_progress=None):
    for k in range(snapshots):
        if _CANCEL_FLAG.is_set(): break
        time.sleep(per_snapshot_ms / 1000)
        if on_progress: on_progress(t, expl, partial_report)
```

The flag-handling code is final-form in PR 10a; PR 10b uses the same
flag without modification.

## 8. Locked design decisions (Q1–Q7 — see §0.1)

All seven open design questions are locked in §0.1 (with citations);
agent prompts in §9 encode the locked options directly. Coin-flip flag:
**Q3** (1000 vs 2000 iters) is the most arbitrary lock; see §0.1
user-review note.

## 9. Three-agent fan-out plan (UX-informed)

Same three-agent split as `pr10_spec.md` §10. UX guidance from §2–§4
above is baked into each agent's prompt.

### Agent A — spot input + run panel + state management

**Owns:** `ui/__init__.py`, `ui/app.py`, `ui/state.py`,
`ui/views/spot_input.py`, `ui/views/run_panel.py`.

**UX deltas to prompt:**
- Implement the **two-pane layout** (Q1 locked): center matrix region
  + right-sidebar column with three `ui.expansion` panels (spot input
  open by default; run panel + tree-browser slot collapsed). Header
  includes the **yellow "Mock mode" banner** (Q7 locked, dismissible),
  theme toggle (Auto default per `ui_design_principles.md` §5),
  hamburger menu for rarely-touched prefs (Debate 4 inline contextual).
- Spot input panel per mockup §4.2: 4×13 suit grid, player tabs, matrix
  mode default for range input with live string preview underneath,
  combo counter, push/fold warning toast at ≤ 15 BB.
- Run panel per mockup §4.3: bet-size checkboxes with **Q4-locked
  defaults (4 of 6: 33 / 75 / 100 / AI)**, iteration count default
  **1000 (Q3 locked)** with target-exploitability opt-in toggle,
  `ui.echart` log-scale chart with linear toggle, three distinct
  buttons, status word colored per state.
- `SolveRunner.start()` imports `mock_solve` as `_solve_postflop_impl`
  single named symbol for PR 10b one-line swap.
- All edge-case state handling per §6: long-solve ETA + ⏳ glyph,
  cancellation preserves partial strategy, OOM dark-red status,
  unsupported-config remediation notifications.
- Honor all 9 design principles + actively avoid all 8 anti-patterns
  per §2.

### Agent B — range matrix + tree browser

**Owns:** `ui/views/range_matrix.py`, `ui/views/tree_browser.py`.

**UX deltas to prompt:**
- Range matrix per mockup §4.4: additive RGB color blend (PR 10
  §7.3); two on-cell signals (color + `R/C/F xx%` tag or `MIX`/`BLK`);
  hover-tooltip + click-strip; slashed-diagonal blocker overlay;
  **hand-class shorthand visible in cell upper-left per Q2 locked**.
- Combo inspector strip **below matrix (Q5 locked)**: horizontal
  stacked bar `▰▰▰▰▰▰▰▰▱▱`; per-combo EV + reach; infoset key with
  copy-icon (not visible monospace per anti-pattern §3.8); BLOCKED
  row for cells removed by board.
- Tree browser per mockup §4.5: file-tree indentation, expand/collapse
  chevrons (▾/▸), inline action stats (`fold 8% call 24% raise 68%`),
  selected-node highlight, **reach filter slider above (default 0.01
  per Q6 locked)**, lazy expansion, performance cap at 100 children
  visible per node + 2000 total nodes.
- Click tree node → re-render matrix conditioned on history (locked
  in PR 10 §3.4).

### Agent C — mock solver + library stub + smoke tests + CLI

**Owns:** `ui/views/library_browser.py`, `tests/test_ui_smoke.py`,
`poker_solver/cli.py::ui` subcommand, `pyproject.toml` `[ui]` extra,
`README.md` UI section, **`ui/mock_solver.py`**.

**UX deltas to prompt:**
- Mock solver module per §7 above: public surface (mock_solve,
  list_fixture_presets, load_fixture), 12 fixtures, interpolation
  fallback, 6 failure modes, MemoryReport fabrication.
- Library stub per §4.6: list view with three faked rows; Filter
  field; `[Load selected]` + `[Delete]` buttons; PR 11 wiring banner.
- Smoke tests per §10 below: 20 total.
- CLI + pyproject + README; README tagline mentions **"yellow Mock
  mode banner during PR 10a, downgrades to subtle chip in PR 10b"**
  (Q7 locked).

### Integration phase

- Import-discipline grep: `ui/` outside `ui/state.py` contains zero
  `mock_solver` references.
- Fixture-coverage manual: walk all 12 fixtures via the UI; confirm
  nothing renders as `—` or `[empty]` on populated cells.
- Onboarding flow: when `~/.poker_solver_ui/state.json` is absent,
  3-step modal appears (`ui_mockups_and_debates.md` §4). Each step is
  one-action ask. Final step teaches color legend before closing.

## 10. Test plan (UI smoke + mock + UX coverage)

All tests in `tests/test_ui_smoke.py`. Marked `@pytest.mark.ui`; skip
if NiceGUI not installed.

### 10.1 UI smoke tests (PR 10's 8, unchanged)

1. `test_page_renders_without_exception`.
2. `test_board_picker_accepts_three_cards`.
3. `test_range_input_via_string`.
4. `test_solve_button_starts_worker`.
5. `test_stop_button_halts_within_one_iteration`.
6. `test_range_matrix_renders_169_cells`.
7. `test_combo_to_cell_mapping_no_off_by_one` (critical correctness).
8. `test_library_dialog_opens`.

### 10.2 Mock-solver coverage tests

9. `test_mock_solve_returns_real_hunl_solve_result` — `isinstance`
   check on `HUNLSolveResult` + `MemoryReport`.
10. `test_mock_solve_streams_progress_callbacks` — fires
    `iterations // log_every` times, monotone iter, monotone-ish
    decreasing expl.
11. `test_mock_solve_failure_oom_raises_memory_error_with_partial_report`
    — `MemoryError.args[1]` is `MemoryReport`.
12. `test_mock_solve_failure_cancelled_returns_partial_result` —
    `result.iterations < requested` and strategy non-empty.
13. `test_ui_never_imports_mock_specific_symbols` — grep `ui/` outside
    `ui/state.py`.

### 10.3 UX-grounded smoke additions

14. `test_range_matrix_color_blend_matches_pio_convention` — given
    fixture with known per-cell action freqs, assert rendered RGB
    matches additive formula within ±2 per channel. Locks adopted
    pattern #1.
15. `test_blocker_cells_show_slashed_overlay` — `flop_k72r_100bb`
    fixture, `AhKh`-only class renders slashed-overlay style.
16. `test_input_matrix_palette_disjoint_from_display_palette` —
    static assertion that input-matrix sources blue-gradient palette,
    display-matrix sources RYG. Locks principle 4.
17. `test_chart_default_log_scale` — `ui.echart` Y axis defaults to
    log; linear toggle exists.

### 10.4 Edge-case coverage tests (added in this revision)

18. `test_oom_failure_shows_remediation_notification` — `mock_failure_mode='oom'`
    surfaces the §6.5 notification with "Reduce bet sizes" quick-
    action button.
19. `test_pushfold_dispatch_at_15bb` — set stacks to 15 BB; assert
    yellow warning toast appears with "Switch to push/fold view"
    button.
20. `test_long_solve_eta_appears_after_30s` — with
    `mock_latency_ms=60_000` and `mock_failure_mode='long_latency'`,
    assert ETA text appears in status readout after 30 s.

**Acceptance:** all 20 pass; `scripts/check_pr.sh` green.

## 11. Acceptance criteria (PR 10a, UX-informed)

PR 10a is mergeable when:

1. All 20 smoke tests pass.
2. `poker-solver ui` launches; renders **two-pane layout** (Q1 locked):
   matrix center + right sidebar with three `ui.expansion` panels (spot
   input / run panel / tree browser).
3. All 12 fixture spots load via preset dropdown and render
   meaningful state.
4. Live exploitability chart updates with log-Y scaling during solve.
5. Stop button halts within one simulated iteration.
6. Failure modes (OOM, NotImplementedError, cancellation, push/fold,
   long-solve, memory abort) surface per §6 with user-readable
   notifications + remediation guidance.
7. Static check: `ui/mock_solver` imports appear in exactly one file
   (`ui/state.py`).
8. `scripts/check_pr.sh` passes (ruff + mypy + pytest + license audit).
9. NiceGUI gated by `[ui]` extra.
10. **UX checkbox — palette disjointness:** range-input matrix uses
    blue gradient; strategy display matrix uses RYG. Manual
    spot-check on PR review.
11. **UX checkbox — yellow "Mock mode" banner** (Q7 locked): visible
    across the top on launch, dismissible after first solve; downgrades
    to subtle `(mock)` chip in PR 10b.
12. **UX checkbox — onboarding modal:** absent `state.json` triggers
    3-step onboarding (`ui_mockups_and_debates.md` §4); each step is
    one-action; final step teaches color legend.
13. **UX checkbox — anti-patterns absent:** no modal for routine
    settings (anti-pattern §3.4); no acronym without tooltip (anti-
    pattern §3.5); no destructive confirmation on undoable actions
    (anti-pattern §3.6).

## 12. Risks (UX-informed additions)

Original PR 10a spec listed three risks; adding three more from the
UX synthesis:

1. **Mock-fixture poker-realism risk** (original). Hand-crafted
   strategies pass the eye test but aren't provably correct. (mock)
   overlay mitigates.
2. **Interpolation fallback risk** (original). Off-distribution
   strategies may not be poker-coherent. Yellow banner "(mock
   approximation)" mitigates.
3. **Surface drift PR 10a → PR 10b** (original). If PR 9 preflop
   solver adds kwargs `solve_hunl_postflop` lacks, swap is no longer
   one line. PR 9 spec consistency review checks alignment.
4. **Palette disjointness drift** (new). Future PR repurposing the
   blue input-matrix palette for a strategy element silently breaks
   principle 4. Test #16 locks the assertion.
5. **Q1–Q7 option conflict with agents' default implementation**
   (resolved 2026-05-22 synthesis). All seven questions locked in §0.1
   based on three landed research docs; agent prompts in §9 encode the
   locked options directly. Residual risk: if Q3 (1000 iters) produces
   under-converged matrices on common spots during PR 10a manual
   testing, bump to 2000 in PR 10b — coin-flip flag in §0.1.
6. **Onboarding modal coupling with state.json absence** (new). If
   user wipes `state.json` to re-trigger onboarding for testing, they
   also lose persisted prefs (panel widths, recent spots). Mitigation:
   reserve a `state.json::ui_prefs.onboarding_completed` bool that
   gates the modal independent of file presence.

## 13. Files to create / modify

| Path | Owner | Purpose |
|---|---|---|
| `ui/__init__.py` | A | Empty package init. |
| `ui/app.py` | A | NiceGUI entrypoint + header (§4.1). |
| `ui/state.py` | A | Shared state + `SolveRunner` + onboarding flag. |
| `ui/views/spot_input.py` | A | Spot input (§4.2). |
| `ui/views/run_panel.py` | A | Run panel + log-Y chart (§4.3). |
| `ui/views/range_matrix.py` | B | 13×13 matrix + inspector (§4.4). |
| `ui/views/tree_browser.py` | B | Tree browser (§4.5). |
| `ui/views/library_browser.py` | C | Library stub (§4.6). |
| `ui/views/onboarding.py` | A | 3-step onboarding modal (§9 integration). |
| `ui/mock_solver.py` | C | Mock solver module (§7). |
| `ui/mock_solver_fixtures.py` | C | Optional fixture data file. |
| `tests/test_ui_smoke.py` | C | 20 smoke tests (§10). |

Modifications: `pyproject.toml` (`[ui]` extra), `poker_solver/cli.py`
(`ui` subcommand), `README.md` (UI section + `(mock)` tagline).

## 14. Reference appendix

- `pr10_spec.md` — original PR 10 long-form spec; UI structural intent
  inherited verbatim.
- `pr10b_spec.md` — companion PR that swaps the mock for the real solver.
- `docs/pr10_prep/ui_design_principles.md` (421 lines) — 9 principles,
  8 anti-patterns, 4-tier disclosure, 13 locked decisions, 4 open
  questions.
- `docs/pr10_prep/ui_mockups_and_debates.md` (611 lines) — 5 view
  mockups with justifications, 6 pro/con debates, 5 edge cases,
  3-step onboarding, summary table.
- `docs/pr10_prep/competitor_ui_deep_dive.md` (863 lines, 2026-05-22) —
  Pio / GTOW / Monker / DeepSolver deep dive; §Synthesis section is
  the load-bearing reference for the §0.1 Q1–Q7 evidence matrix.
- `docs/competitor_landscape.md` — PioSolver, GTOW, MonkerSolver,
  postflop-solver, shark-2.0, TexasSolver competitor analysis.
- `references/blog/piosolver_technical_details.md`.
- `references/blog/gtow_how_solvers_work.md`,
  `gtow_ai_benchmarks.md`, `gtow_multiway_preflop_launch.md`.
- `/Users/ashen/Desktop/poker_solver/poker_solver/hunl_solver.py` —
  `HUNLSolveResult` + `solve_hunl_postflop` (PR 5).
- `/Users/ashen/Desktop/poker_solver/poker_solver/profiler/memory.py` —
  `MemoryReport` + `StreetMemoryEntry`.
- `PLAN.md` §1 (UI tech: NiceGUI), §2 (PR roadmap).
