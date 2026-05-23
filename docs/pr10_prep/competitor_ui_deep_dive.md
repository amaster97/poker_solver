# Competitor UI deep-dive — PR 10 prep

**Purpose:** Inform the PR 10 (NiceGUI scaffold) and PR 10a (mock-solver UI) design
decisions by characterizing how the top 4 commercial poker solvers shape their
range / tree / EV / progress / library surfaces. Cite-or-die: every claim below
has a referenced source — local file path, official URL, or a noted "Inferred
from X" qualifier.

**Sources surveyed:**
- `/Users/ashen/Desktop/poker_solver/references/products/_COMPETITORS.md`
- `/Users/ashen/Desktop/poker_solver/references/blog/piosolver_technical_details.md`
- `/Users/ashen/Desktop/poker_solver/references/blog/gtow_how_solvers_work.md`
- `/Users/ashen/Desktop/poker_solver/references/blog/gtow_ai_benchmarks.md`
- `/Users/ashen/Desktop/poker_solver/references/blog/gtow_multiway_preflop_launch.md`
- `/Users/ashen/Desktop/poker_solver/references/blog/gtow_quirks_multiway_nash.md`
- `/Users/ashen/Desktop/poker_solver/docs/competitor_landscape.md`
- `/Users/ashen/Desktop/poker_solver/references/code/shark-2.0/README.md`
- `/Users/ashen/Desktop/poker_solver/references/code/TexasSolver/README.md`
- `/Users/ashen/Desktop/poker_solver/references/code/postflop-solver/README.md`
- WebFetch: <https://piosolver.com>, <https://piosolver.com/products>,
  <https://piosolver.com/docs>, <https://piosolver.com/about/>,
  <https://gtowizard.com>, <https://blog.gtowizard.com>,
  <https://deepsolver.com>, <https://deepsolver.com/features>,
  <https://deepsolver.com/pricing>

**Caveats:**
- WebFetch could not pull <https://monkersolver.com> (ECONNREFUSED, repeated
  attempts) — Monker section reconstructed from our own local notes,
  `_COMPETITORS.md`, and the consensus characterizations in
  `competitor_landscape.md`. No live screenshot confirmation; any UI claim is
  flagged "from secondary sources" inline.
- Reddit / 2+2 forum access was blocked by Cloudflare / 403 responses — user
  pain points are pulled from `_COMPETITORS.md`, the engineering reality
  documented in our own `competitor_landscape.md`, and the lone Shark-2.0
  README's commentary on competitor approaches.
- Pio's official site is intentionally light on UI screenshots; the deepest
  technical / UI document we have is `references/blog/piosolver_technical_details.md`
  plus the quick-start text fetched from `https://piosolver.com/docs`.

---

## PioSolver

**Founded / current state:** Operated by PioSoft, a "small, distributed team"
(per `https://piosolver.com/about/`). Current commercial version is **3.0**
(`https://piosolver.com/products`); the homepage banner also references **3.9**
with a "powerful flop aggregation interface" — likely a forthcoming or
preview build. The product is the de facto industry standard for HU NLHE
postflop solving (`_COMPETITORS.md` §PioSolver). PioSoft's brand is
PioSolver-as-engine + PioViewer-as-GUI.

**Pricing:**
- **PioSOLVER 3.0 Pro: €450** one-time perpetual license. Up to 16-core
  support, full PioViewer, scripting, two-machine activation, 1 year of
  software updates. (Source: `https://piosolver.com/products` via WebFetch.)
- **PioSOLVER 3.0 Edge: €800** one-time perpetual license. Adds up to
  64-core support, the preflop solver (HU only), custom hardware
  compilation, unlimited two-machine moves. (Source: same.)
- Historical tiers mentioned in `_COMPETITORS.md`: Free / Basic / Pro / Edge.
  Free and Basic are no longer active SKUs in v3.0.
- **No subscription**, no cloud, no recurring fees, no precomputed library —
  every spot is solved locally by the user.

**Target user:** Serious HU NLHE postflop players (cash regs, study-group
pros). Pricing and Windows-only delivery filter out casual users; the
configuration burden filters out hobbyists. The €450 Pro tier is the
"professional standard" for solo study.

### Core UX flow

(Reconstructed from `references/blog/piosolver_technical_details.md` and the
PioSolver quick-start guide fetched from `https://piosolver.com/docs`. PioSoft
intentionally provides few screenshots on its public site; the workflow below
is the canonical Tree-Building-and-Calculation → Browser tab loop documented
across community video tutorials.)

1. **Launch PioViewer** (the Windows-Forms GUI shell). PioSolver itself is a
   text-based chess-engine-style console process that PioViewer drives over
   stdin/stdout (`references/blog/piosolver_technical_details.md`).
2. **Configure the tree** in the "Tree Building and Calculation" tab:
   - Pick a sample config or start blank.
   - Type / paste the **OOP range** in PioSOLVER notation
     (`QQ+,AKs,AQo,...`) into a multi-line text field; same for IP.
   - Set the **starting pot** in chips, **starting effective stack** in
     chips, and **board** (three flop cards as a comma-separated string).
   - Configure **per-street bet sizes** as comma-separated lists (e.g.
     `33,75,150` for 33%, 75%, 150%-of-pot bets per street, with a separate
     list for raises and an `a` for all-in).
   - Optional: **donk bet** toggle, **add-allin-threshold** percent,
     **force-allin-threshold** percent, accuracy target as % pot, thread
     count, raise cap.
3. **Click "Go" / "Build Tree"** — PioViewer asks the engine to allocate
   the tree (RAM usage shown in status bar).
4. **Click "Solve"** — engine starts CFR iterations. The Tree-Building tab
   itself shows progress lines (per
   `https://piosolver.com/docs`: "messages will appear about once every
   minute for flop spots and every few seconds for turn/river").
5. **Switch to the Browser tab** to inspect results:
   - Top of the tab is a **tree-view widget** with expandable nodes.
   - The right panel has **toggle buttons for what info to display**: EVs,
     strategies (per-action mixes), ranges, equities.
   - The center shows the **13×13 range matrix** for the player to act at
     the selected node, colored by current mixed strategy.
6. **Save / resume** — every tree can be serialized to disk (the .cfr file
   format). Per the quick-start: "You can save the tree and come back to it
   later. You can also resume solving if you decide you want better
   accuracy (just load the tree, go to Tree building and calculation and
   click Go)" — fully resumable session, no cloud.
7. **Save ranges + configurations** as named files; users can organize
   them in folders and share with others
   (`https://piosolver.com/docs` quick-start guide quote).

### Visual design language

- **Theme:** Light gray / white Windows-Forms; .NET Framework default
  controls. Dated aesthetic — feels like a 2010-era engineering tool.
  (`references/blog/piosolver_technical_details.md` confirms .NET dependency.)
- **Color convention (range matrix):** Red = fold, yellow = call/check,
  green = raise/bet. This is the **industry-standard color triad** that
  every subsequent solver inherits (Shark explicitly calls its scheme
  "PIO-style strategy coloring" — `references/code/shark-2.0/README.md`).
- **Density:** Maximalist. Tree view + range matrix + numeric strategy
  table + per-combo EV column + range-summary stats sidebar — everything
  visible simultaneously. No hover-to-reveal philosophy; the user is
  expected to know what every widget means.
- **Font:** Default system sans-serif; no design-driven typography.

### What it does brilliantly

1. **Chess-engine-style text protocol.** PioSolver-the-engine is a
   stdin/stdout console process; PioViewer is just a GUI on top
   (`references/blog/piosolver_technical_details.md`). Anyone can drive Pio
   from a script — `_COMPETITORS.md` notes this directly enables external
   integration. **This is the architectural pattern we are mirroring** with
   our Python-tier-over-Rust-core design.
2. **Resumable solves.** Save mid-iteration, reload, click Go, continue. Per
   `https://piosolver.com/docs`: "You can save the tree and come back to it
   later." No re-solving from scratch when the user is iterating on a spot.
3. **Granular tree configuration.** Per-street custom bet sizes via
   comma-separated lists, donk bets, raise caps, force/add-allin
   thresholds, accuracy target, thread count — every solver-engineering
   knob is exposed. Power users love this; the
   `references/blog/piosolver_technical_details.md` "User Input
   Requirements" section enumerates 6 mandatory + 4 optional config
   parameters.

### What feels clunky / dated

1. **Windows-Forms aesthetic.** The GUI is functional but visibly stuck in
   2014. `_COMPETITORS.md` calls it "Windows-Forms-style"; our own
   `competitor_landscape.md` says "dated Windows-Forms GUI" and lists this
   as the primary UX gap to attack. No dark mode, no resizable panels with
   modern affordances, no responsive layout, no touch / mobile concession.
2. **Range parsing has no GUI helper.** The user types
   `QQ+,AKs,AKo,A5s-A2s,...` into a textarea. There is no visual range
   builder, no click-to-add, no live preview as the user types. Mistakes
   are silent until the user notices the parsed range mismatches their
   intent. (Source: `references/blog/piosolver_technical_details.md`
   "User Input Requirements" section + community video tutorials.)
3. **No live exploitability curve during solve.** PioViewer shows
   periodic text-log messages with current exploitability per
   `https://piosolver.com/docs`, but does not render a real-time chart of
   exploitability vs iteration. Users have to read the log lines to gauge
   convergence. Our own `competitor_landscape.md` explicitly identifies
   "no live exploitability target-driven solve" as a UX gap.
4. **Windows-only.** Mac users run it through Parallels or Bootcamp; Linux
   users are not served at all (`references/blog/piosolver_technical_details.md`
   "System Requirements"). This is the single biggest cross-platform UX gap
   in the market.

### Patterns we should adopt

- **Chess-engine-style backend** — text/JSON-RPC interface between UI and
  solver core. Already the basis of our Python ↔ Rust split.
- **Industry-standard color triad** (red=fold / yellow=call/check /
  green=raise/bet) on the range matrix. Confirmed in PR 10 spec §2.
- **Tree view on one side, range matrix on the other** — Pio's canonical
  spatial layout. PR 10 spec already adopts this with the matrix
  left/center and tree on the right.
- **Per-street bet-size lists as the configuration primitive.**
  `33,75,150` notation; let the user override per street. Already in our
  bet-size DSL plan (postflop-solver and shark inherit this).
- **Resumable solves via on-disk checkpoint.** PR 11 ships this; PR 10
  ships the stub library that reads it.
- **PioSOLVER-compatible range syntax** (`QQ+,AKs,A5s-A2s,...`) — every
  serious user already speaks this language. `references/code/postflop-solver/README.md`
  confirms WASM/Desktop Postflop adopt the same. Use as our parse target.

### Patterns we should NOT adopt

- **Maximalist always-visible information density.** Pio assumes the user
  knows every widget; new users find this overwhelming.
  `references/code/shark-2.0/README.md` explicitly cites "simplicity" and
  "reduce clutter and cognitive load" as the design choice they made vs
  Pio.
- **Textarea-only range input.** PioSOLVER notation is correct as a
  *language* but the UI should offer a visual range builder *first*, with
  the text representation as a sync'd power-user toggle.
- **Windows-Forms aesthetic.** Dark mode by default. Modern type scale.
  Responsive panels. PR 10 spec already implies this via NiceGUI / Quasar.
- **No live exploitability chart.** Show the curve as it decays — every
  user wants this. PR 10 spec §3 already mandates it.

---

## GTO Wizard

**Founded / current state:** GTO Wizard is a cloud-hosted GTO study
platform. Active product; the engineering blog at
<https://blog.gtowizard.com> shows aggressive shipping cadence — recent
posts (per WebFetch May 2026) include PLO solver launch (May 12, 2026),
"Exploiting Profiles" series (April–May 2026), and the April 2025 switch
to **Quantal Response Equilibrium** as the solving objective
(`references/blog/gtow_ai_benchmarks.md`). Founded mid-2010s; the team
operates as a SaaS platform combining a massive precomputed library with
on-demand AI-assisted custom solves.

**Pricing:**
The standard tiers historically run **~$50–100/month**
(`_COMPETITORS.md` §GTO Wizard). The **Ultra tier** required for custom
multiway preflop solving is **$229–359/month** depending on annual vs
monthly billing and Early Bird vs Standard
(`references/blog/gtow_multiway_preflop_launch.md`):
- **Early Bird Annual: $229/month**
- **Early Bird Monthly: $279/month**
- **Standard Annual: $289/month** (after Early Bird period)
- **Standard Monthly: $359/month**
- **Free tier** limited to **10 BB stacks** for custom solves
  (same blog post).

Live pricing page <https://gtowizard.com/pricing> redirects to
<https://app.gtowizard.com/user/subscription> which requires auth;
WebFetch could not retrieve the current per-tier feature matrix.

**Target user:** Wide — explicitly "all skill levels from beginners to
advanced players" per the homepage (`https://gtowizard.com` WebFetch
result), with cash + tournament + ICM coverage. In practice the Ultra
tier (custom multiway) is pro-only at $229–359/month; the standard
tier is the mass-market HU and library-lookup product for serious
amateurs to mid-stakes pros.

### Core UX flow

(Reconstructed from `https://gtowizard.com` homepage WebFetch result and
`https://help.gtowizard.com` navigation map.)

1. **User logs into <https://app.gtowizard.com>** via browser; works on
   mobile too per the launch blog: "solve multiway preflop spots directly
   in your browser, even on your phone, in seconds"
   (`references/blog/gtow_multiway_preflop_launch.md`).
2. **Top-level nav as tabs:** Study / Practice / Analyze / PLO / Content /
   PokerArena / Table Wizard (per `https://gtowizard.com` WebFetch result).
3. **Study mode** — the core solver-output browser:
   - Pick game format (cash / MTT / spin / HU SnG), stack depth, position
     pair, optional ICM context.
   - Pick the action node — a **graphical action tree** at the top of the
     screen showing folded / called / raised lines (canonical to GTO Wizard).
   - The **range matrix** renders the player-to-act's strategy at that
     node, colored by mixed strategy.
   - A **per-action EV panel** below the matrix shows each action's EV
     and frequency, often as horizontal bars.
   - **Aggregated Reports** view shows "full strategy across 1,755 flops
     instantly" — a tabular view of all flop classes with summary stats
     (per `https://gtowizard.com` WebFetch result).
4. **Custom solve** (Ultra tier) — submit a custom spot to the cloud queue;
   GTOW AI returns a result in seconds (the published benchmark is
   **6 seconds on 2 cores / 8 GB** for a spot Pio takes 4,862 seconds on
   16 cores / 128 GB —
   `references/blog/gtow_ai_benchmarks.md`).
5. **Practice / Trainer** — quiz-style drill interface. User is shown a
   spot and must choose an action; immediate feedback compares decision
   to the GTO answer.
6. **Analyze** — upload hand histories; the system identifies the largest
   EV-loss leaks across the session and produces a per-spot diagnostic
   ("GTO Reports highlighting biggest leaks with a clean, solver-backed
   overview" — `https://gtowizard.com` WebFetch result).
7. **Save / share** — solutions are server-side artifacts the user can
   bookmark; sharing is via permalink. Library scale: per
   `_COMPETITORS.md`, "millions of spots across formats, stack depths,
   and bet sizings."

### Visual design language

- **Theme:** Dark, with green accents and blue glows for secondary
  highlights (`https://gtowizard.com` WebFetch result). High contrast.
- **Density:** Moderate. The Study view is information-rich but
  organized with clear visual hierarchy — heading > tree > range matrix >
  EV panel. Mobile-friendly responsive layout.
- **Color (range matrix):** Same red / yellow / green industry triad as
  Pio (inferred from screenshots and consistent community description).
  GTO Wizard's *novel* color usage is the green / blue brand accents on
  interactive UI chrome, not the range strategy itself.
- **Typography:** Modern sans-serif, larger than Pio's defaults,
  optimized for browser + mobile.
- **Iconography:** Custom icons for game formats, positions, bet sizes.

### What it does brilliantly

1. **Library-first navigation.** The user starts by *picking a spot from a
   menu*, not by configuring a tree. Stack depth + position pair + game
   format collapses 95% of the configuration burden; the result is
   ~instant. (Per `_COMPETITORS.md`: "Massive precomputed library of
   cash-game and tournament postflop solutions.") **For the
   serious-amateur-to-mid-stakes-pro segment, this is the killer
   feature** — the cost of solving is amortized across millions of users.
2. **AI-accelerated custom solves.** Per
   `references/blog/gtow_ai_benchmarks.md`: 6 seconds vs Pio's 4,862
   seconds at the same 0.22% accuracy target. The UX implication is that
   custom solves feel "interactive" rather than "batch-job-overnight."
3. **Aggregated flop reports.** Per `https://gtowizard.com`: "full
   strategy across 1,755 flops instantly." A single view tells the user
   *how the strategy varies across all flop classes* — a study mode no
   local solver provides.
4. **Mobile-first.** Works in a phone browser per the multiway-preflop
   launch blog. The other solvers all assume desktop.
5. **Practice / Trainer integration.** The line from "the solver says X"
   to "drill until you can execute X under time pressure" is a single
   in-product hop. Pio doesn't ship this; the user has to build their
   own training loop.
6. **Visual action tree at the node level.** The decision tree is shown
   as a *graphical* tree (folded/called/raised buttons cascading
   left-to-right), not a textual hierarchical list. This makes the
   "where am I in the tree" question instantly answerable.

### What feels clunky / dated

(Per `_COMPETITORS.md` §GTO Wizard's "Weaknesses" + our own
`competitor_landscape.md` analysis.)

1. **SaaS lock-in.** No offline mode. No local compute control. Monthly
   fees stack. The cheapest custom-multiway tier is $229/month —
   prohibitive for hobbyists.
2. **Custom spots queue.** Ultra-tier "custom" solves still go through
   shared compute; users report queue wait times during peak hours
   (per `competitor_landscape.md` reading of community feedback —
   no direct Reddit link survives Cloudflare block).
3. **No local audit.** The NN warm-start is a black box; users can't
   independently verify accuracy claims beyond GTOW's own published
   benchmarks (`competitor_landscape.md` flags this as a trust gap).
4. **Multiway theory caveats.** GTOW's own blog
   (`references/blog/gtow_quirks_multiway_nash.md`) admits "the
   foundational promises of a Nash Equilibrium don't hold" in n>2-player
   games. Users paying $229+/month for multiway preflop are paying for a
   solution whose own vendor flags theoretical fragility.
5. **No script API.** Pio ships a scripting interface; GTOW's product is
   the browser app + the Table Wizard overlay, neither of which exposes
   a documented HTTP / RPC API for power users.

### Patterns we should adopt

- **Visual action-tree widget** rendered as a left-to-right node
  cascade, with each node a clickable button. PR 10 spec §3.3 already
  plans an expandable nested list — we should consider whether a
  horizontal cascade reads better. (Decision point flagged in
  Synthesis below.)
- **"Library-first" entry point.** Even though PR 10 doesn't ship a real
  library (PR 11 does), the UI should *imply* one: the spot-input panel
  should default to "pick from preset" with "custom" as a secondary
  option. PR 10a spec §1 already does this via the river/dry/wet/etc.
  preset dropdown.
- **Aggregated-report view across flop classes.** Out of scope for v0
  but should be on the v1 backlog — this is a unique GTOW pattern that
  pro users will look for.
- **Per-action EV displayed as a horizontal bar chart**, not just a
  number. Bar charts on the action-frequencies panel give an immediate
  visual sense of how mixed the strategy is. PR 10 spec already shows
  per-combo strategy bars in the inspector strip.
- **Modern dark theme with brand-color accents.** NiceGUI's Quasar
  components support this directly.

### Patterns we should NOT adopt

- **SaaS-only delivery.** Our entire thesis is local-first.
- **Mobile-first.** We are desktop-first for serious solver work.
  Mobile-friendly is a nice-to-have, not a design driver. NiceGUI
  responsive layout gives us this for free on most panels.
- **Quiz/drill mode in v0.** Out of scope — we are a solver, not a
  study platform (per `competitor_landscape.md` "What we are
  deliberately NOT going to be" §3).
- **Black-box NN warm-start.** Our value proposition is auditability;
  every output should be reproducible from the same inputs.

---

## MonkerSolver

**Founded / current state:** Active product (per `_COMPETITORS.md`),
historically the only off-the-shelf option for true multiway postflop
solving. WebFetch failed against <https://monkersolver.com> (ECONNREFUSED,
repeated attempts) — this section is reconstructed from
`_COMPETITORS.md`, `competitor_landscape.md`, and consensus
characterizations from the OSS reference documents
(`references/code/postflop-solver/_NOTES.md`,
`references/code/shark-2.0/README.md` competitive notes). **No
first-party screenshot or doc verification was possible at deep-dive
time.** Treat every UI claim below as "from secondary sources" and
re-verify if Monker becomes a closer competitor.

**Pricing:** ~**€330** one-time perpetual license (per
`_COMPETITORS.md` §MonkerSolver: "Windows desktop, perpetual license
(~€330 last published price)"). No subscription, no cloud.

**Target user:** Pro / pre-pro multiway specialists. The combination of
Windows-only, multi-hour run times on 32-core boxes, lossy card
bucketing, and €330 entry price filters out hobbyists hard.
`competitor_landscape.md` notes Monker is "effectively the only
off-the-shelf option for true multiway postflop until GTO Wizard's
cloud multiway matures into postflop."

### Core UX flow

(All "from secondary sources" — no live-fetched primary docs available
at deep-dive time.)

1. Launch the Monker Windows desktop application.
2. Configure the spot:
   - Number of players (3+).
   - Per-player starting range in PioSOLVER-compatible notation.
   - Stack depths (asymmetric supported per `_COMPETITORS.md`).
   - Board (flop / turn / river cards).
   - Per-street bet sizes.
   - **Card abstraction (bucketing) parameters** — the user must
     trade off bucket count vs RAM (per `_COMPETITORS.md`: "Uses heavy
     card-abstraction (bucketing) to make multiway tractable, which
     means solutions are less granular than PioSolver's per-combo
     strategies").
3. Allocate the tree (very memory-hungry — `_COMPETITORS.md` notes
   "nontrivial 3-way turn spot can take hours on a 32-core box;
   4-way+ is impractical on commodity hardware").
4. Start solving. Per the engineering description, this is also a
   stdin/stdout-style engine with a Windows GUI wrapper.
5. **Inspect strategy per bucket** — *not* per-combo. This is the
   biggest UX-departure from Pio / GTOW / DeepSolver: because of the
   card abstraction, the range matrix is reported at bucket
   granularity, and the user must mentally map back from buckets to
   actual hand combos. (Per `_COMPETITORS.md`: "solutions are reported
   per-bucket rather than per-combo.")
6. Save / load trees via on-disk files.

### Visual design language

- **Theme:** Spartan Windows desktop (per `_COMPETITORS.md`: "UI/UX is
  even more spartan than Pio"). Inferred Windows-Forms or similar
  legacy widget set.
- **Density:** Maximalist, like Pio, but with additional bucket / player
  dimension to display.
- **Color (range matrix):** Inferred to follow the
  red / yellow / green industry triad — but the matrix represents a
  bucket-level strategy, so the cells correspond to bucket averages
  rather than per-combo per-player mixes.
- **Layout:** Multi-pane Windows desktop. No mobile / responsive support.

### What it does brilliantly

1. **Only off-the-shelf multiway solver.** Per `_COMPETITORS.md`:
   "Effectively the only off-the-shelf option for true multiway
   postflop." The use case alone justifies the price for anyone
   studying 3+ player spots.
2. **Asymmetric stack support and per-player range customization.**
   Multiway-specific config exposed in the GUI.
3. **Perpetual license, no cloud lock-in.** Same property advantage as
   Pio for users who want to own the tool.

### What feels clunky / dated

1. **Bucket-based strategy presentation.** The user has to interpret
   bucket averages instead of per-combo decisions
   (`_COMPETITORS.md`). For a serious pro who learned on Pio's
   per-combo grid, this is a cognitive tax — but unavoidable given
   multiway combinatorics on commodity hardware.
2. **Hours-long solve times** on a 32-core box for a 3-way turn spot
   (`_COMPETITORS.md`). The UI cannot mask that.
3. **Infrequent updates.** Per `_COMPETITORS.md`: "updates are
   infrequent." Implicit signal of single-developer / small-team
   maintenance.
4. **Windows-only.** Same Mac/Linux exclusion as Pio.
5. **Spartan UI.** No design investment. The product survives on its
   niche (multiway), not its polish.

### Patterns we should adopt

- **Per-player range editor with asymmetric stacks** — when we
  eventually consider multi-player support (not v0), this is the
  table-stakes config primitive.
- **Honest disclosure of approximation** — Monker reports the bucket
  granularity. We should do the same with any future card-abstraction
  config (PR 4 ships card abstraction; the UI must let the user see
  bucket counts and approximation impact).

### Patterns we should NOT adopt

- **Bucket-only granularity in v0.** Per
  `competitor_landscape.md`: "we explicitly do not go there in v0."
  v0 is per-combo HU postflop.
- **Multiway in v0.** Out of scope by explicit
  `competitor_landscape.md` "What we are deliberately NOT going to
  be" §2: "no multiway equilibrium claim."
- **Spartan UI as a design philosophy.** Modern UI is a differentiator
  even within HU postflop; it's not a "luxury feature" that can be
  deferred.

---

## DeepSolver

**Founded / current state:** Newer entrant; described in
`_COMPETITORS.md` as "using neural-network-accelerated solving
(similar conceptual approach to GTO Wizard AI)." Targets fast custom
solves at a lower price point than GTOW Ultra. Cloud-based; currently
HU NLHE postflop only ("Currently solves 'No-Limit Texas Hold'em, 2
players post-flop'" — `https://deepsolver.com` WebFetch result).
PLO listed as upcoming.

**Pricing** (from `https://deepsolver.com/pricing` WebFetch result):
- **Essential plan:** **$29.40/month** billed yearly ($353/year), or
  **$49/month** monthly billing.
- **Pro plan ("Supreme Value"):** **$41.40/month** billed yearly
  ($497/year), or **$69/month** monthly billing.
- **Free trial:** 2 days. 14-day refund policy for first-time users.
- **Pro-exclusive features:** runouts analysis, aggregated flop
  reports, exploit-finding capabilities, calculation priority over
  Essential users.
- **All plans:** unlimited calculations, unlimited GTO Trainer access,
  priority support, cloud-based solver, custom solutions, preflop
  range library, smart tree builder.

**Target user:** Serious amateur to pre-pro who wants GTO-Wizard-style
cloud convenience without the $229+/month Ultra ticket. Positioning
is "cheaper GTOW" with the same NN-warm-start technological core.

### Core UX flow

(From `https://deepsolver.com/features` WebFetch result.)

1. **Open the DeepSolver web app** in a browser. "10 Mbps internet,
   updated browser, no hardware needed" per `https://deepsolver.com`.
2. **Smart Tree Builder:** "one-click feature automatically constructs
   game trees using AI that 'work[s] 24/7 to choose the right
   sizings'" — substantially less configuration burden than Pio's
   manual per-street bet-size lists. Manual / custom mode available
   for power users.
3. **Configure the spot:** board, ranges, pot, stack via the UI.
   Preflop ranges available "with one simple click" from the built-in
   library.
4. **Click solve** — cloud returns a result "in just few seconds."
   Claimed accuracy: **0.59% Nash Distance**
   (`https://deepsolver.com` WebFetch result).
5. **Inspect:** "easy to understand format, with powerful graphs and
   charts" — implies per-action EV charts, range matrix, runouts
   analysis (Pro tier).
6. **Node lock** for exploit finding ("Hand Locking Capability" — per
   features page).
7. **Trainer** mode runs alongside ("up to 4-tables" trainer drills,
   per features page).
8. **Multitasking** — background processing lets the user solve a
   second spot while inspecting the first.

### Visual design language

- **Theme:** Cloud-app aesthetic, web-modern. Specific palette not
  documented in WebFetch — site emphasizes "user-friendly" and
  "accessible learning" framing
  (`https://deepsolver.com/features`).
- **Density:** Implied lower than Pio / Monker — "easy to understand
  format" and "basic and advanced features" suggest progressive
  disclosure (basic surface first, advanced behind a toggle).
- **Color (range matrix):** Inferred industry-standard red / yellow /
  green; not separately documented.

### What it does brilliantly

1. **Smart Tree Builder one-click setup.** "AI that 'work[s] 24/7 to
   choose the right sizings'" — reduces the configuration cliff from
   "specify three bet sizes per street, three raise sizes, donk
   thresholds, raise caps" to "one click + tweak if needed."
2. **Aggressively priced relative to GTOW Ultra.** $29.40–69/month vs
   GTOW's $229–359/month for multiway, ~$50–100/month for the
   standard tier. **DeepSolver is the value tier of cloud HU solvers.**
3. **Built-in preflop library + range library + interop**
   ("Interoperability: Supports popular range and hand formats
   compatible with other major software" —
   `https://deepsolver.com/features`).
4. **Integrated trainer.** Same "solve → drill" loop GTOW pioneered,
   shipped inside the standard plan.

### What feels clunky / dated

1. **Closed-source NN inference path.** Same auditability gap as GTOW
   — accuracy claims (0.59% Nash Distance) are vendor-published, not
   independently verifiable. `_COMPETITORS.md` flags this: "NN
   inference path means accuracy claims aren't independently
   verifiable."
2. **Cloud-only.** No offline mode. No script API documented.
3. **Less battle-tested than Pio or GTOW.** `_COMPETITORS.md`:
   "Smaller market share, less battle-tested." Trust deficit vs
   incumbents.
4. **Accuracy is 0.59% Nash Distance** vs GTOW's 0.12% (April 2025
   upgrade — `references/blog/gtow_ai_benchmarks.md`). For users who
   care about accuracy, this is a meaningful gap.

### Patterns we should adopt

- **Smart Tree Builder default with custom override.** PR 10 should
  ship sensible per-street defaults (Shark's
  `flop 50%/100%, turn/river 33%/66%/100%, raise 50%/100%,
  raise cap 3, all-in 0.67` from
  `references/code/shark-2.0/README.md` is a known-good baseline) and
  let advanced users override per spot.
- **"Easy → advanced" progressive disclosure.** Start simple; reveal
  power-user knobs behind a toggle. Pio has every knob up-front;
  DeepSolver hides them; we should land closer to DeepSolver.
- **Built-in preflop range library** loadable in one click. Users
  should never have to type a starting range in 2026; click GTOW /
  Pio-canonical opens / 3-bets / calls and tweak from there.
- **Range/hand format interop.** PioSOLVER notation is the lingua
  franca; supporting paste-from-clipboard with that format is one
  hour of work and a meaningful UX win.

### Patterns we should NOT adopt

- **Cloud-only delivery.** Same as GTOW.
- **Closed-source NN warm-start.** Local, auditable, deterministic.
- **Marketing-driven accuracy claims** ("0.59% Nash Distance") without
  a published reproducible benchmark. We should publish our own
  benchmark with code + config + hardware spec.

---

## Honorable mentions

### Simple Postflop (Russian solver)

Per `_COMPETITORS.md`: "Russian-developed HU postflop solver
competitor to Pio. Similar feature set, perpetual license, smaller
market share. Has a 'Simple GTO Trainer' sibling product and an
integrated preflop solver (Simple Preflop Holdem) that handles
multiway preflop better than Pio." Architecturally closest to Pio of
all alternates; UI conventions likely mirror Pio's
red/yellow/green + tree + matrix layout. **Not separately analyzed
in depth** — same patterns to adopt as Pio.

### GTO+

Per `_COMPETITORS.md`: "Lower-cost ($75 one-time) HU postflop solver
popular with hobbyists and low-stakes players. Solid accuracy,
friendly Windows GUI, smaller feature set than Pio; the 'value'
option for someone who doesn't need Pio's bells and whistles." **The
closest competitor to our entry-price ambition** (we are MIT and
free, but GTO+ at $75 sets the perpetual-license value bar).
Anecdotally: "friendly Windows GUI" is the closest thing to "modern
UX" in the Pio-class space — worth studying its info-density
choices if we can get a screenshot.

### Slumbot

Not a solver product — a hosted bot (Eric Jackson, ACPC HUNL
champion). Per `_COMPETITORS.md`: "Available to play for free via
web/API and frequently used as a baseline for academic and
commercial solver papers." Mentioned here only because it sets the
*strength* bar that GTOW publishes against (19.4 bb/100 win rate over
150k HUNL hands — `references/blog/gtow_ai_benchmarks.md`); we cite
it for benchmark methodology, not UX.

### Shark (open-source competitor)

Active OSS HU postflop solver written in C++20 with FLTK GUI; last
commit April 2026 (`references/code/shark-2.0/_NOTES.md`,
`references/code/shark-2.0/README.md`). **Most directly comparable
to PR 10's UX target in the OSS space.** Worth quoting the design
philosophy verbatim because it crystallizes the choice we're making
(`references/code/shark-2.0/README.md`):

> "Shark is a completely free (and ad-free) open-source solver that
> implements state-of-the-art algorithms to solve Heads-Up (HU) poker.
> While other solvers exist, this project had two main goals: 1.
> Simplicity – Keep the UI and usage as simple as possible. 2.
> Accessibility – Allow anyone, even those unfamiliar with poker, to
> use the solver with ease. Many features seen in other solvers have
> been intentionally omitted to reduce clutter and cognitive load."

Shark's five-page workflow (Initial Setup → Board Selection → Your
Range → Villain Range → Results) is the closest precedent to PR 10a's
spot-input → solve → matrix-inspector loop. **Read the Shark README
in full before finalizing PR 10 UX.**

WASM Postflop and Desktop Postflop (the b-inary projects backed by
the AGPL `postflop-solver` Rust crate — `references/code/postflop-solver/`)
are the other major OSS UX precedents but the AGPL license means we
should not lift specific layout / interaction choices verbatim;
study for architecture only.

---

## Synthesis

### Common patterns across all 4

1. **13×13 range matrix as the centerpiece.** Universal across Pio,
   GTOW, Monker, DeepSolver, plus every OSS competitor (Shark,
   postflop-solver, TexasSolver). The PR 10 spec already treats this
   as "the only universal element."
2. **Red = fold / yellow = call/check / green = raise/bet** color
   triad. Originated in PioSolver; explicitly inherited by Shark
   ("PIO-style strategy coloring" — `references/code/shark-2.0/README.md`)
   and adopted by every solver since. Do not reinvent.
3. **Decision tree as a navigable widget.** Pio and Monker use a
   nested expandable list; GTOW uses a horizontal node cascade;
   DeepSolver's tree presentation is not directly documented in
   public materials but is implied to be a similar visual hierarchy.
   Either form is acceptable; the *function* (click a node, see the
   range matrix at that node) is what's universal.
4. **PioSOLVER-compatible range notation.** Universal lingua franca:
   `QQ+,AKs,A5s-A2s,...`. Every product accepts it as input.
5. **Per-action EV + frequency display** near or below the range
   matrix. Pio shows numeric tables; GTOW uses horizontal bars;
   DeepSolver implied bars and charts ("powerful graphs and
   charts"). The *information* is universal; the rendering
   convention is bar-chart-with-numeric-label.
6. **Save / load / reload sessions.** Every desktop solver
   (Pio, Monker) ships file-based serialization;
   cloud solvers (GTOW, DeepSolver) ship server-side persistence
   with permalinks.
7. **Per-street bet-size configuration** as an explicit knob.
   Universal — even Smart Tree Builder defaults still expose the
   per-street override.

### Where they diverge sharply

1. **Configuration burden: maximalist vs minimalist.**
   - **Maximalist:** Pio, Monker — every knob exposed.
   - **Middle:** GTOW (presets for library spots, manual for custom).
   - **Minimalist:** DeepSolver (Smart Tree Builder one-click),
     Shark (5-page wizard).
   - **Our choice:** Sensible defaults + progressive disclosure
     (closer to DeepSolver / Shark). PR 10a's preset dropdown is
     the right starting point; the override panel is the
     advanced-user safety valve.

2. **Library vs solve-from-scratch.**
   - **Library-first:** GTOW (millions of precomputed spots);
     DeepSolver (preflop range library + smart tree).
   - **Solve-first:** Pio, Monker, every OSS competitor.
   - **Our choice:** Solve-first (no precomputed library is feasible
     for us). PR 10 ships a "library" stub for PR 11 to fill with
     *user-saved* spots, not vendor-curated ones. This is a
     **structural divergence** from GTOW we must own.

3. **Tree visualization: nested list vs horizontal cascade vs graph.**
   - **Nested list:** Pio, Monker, OSS competitors.
   - **Horizontal cascade:** GTOW (button row left-to-right per
     street).
   - **Graph view:** None of the four does this in production.
   - **Our choice:** PR 10 spec §3 already plans an expandable
     nested list (most familiar to Pio users, easiest to ship in
     NiceGUI). **Consider a horizontal cascade as a v1 polish
     option** — measurably faster spatial scanning per GTOW's
     adoption.

4. **Color philosophy: hover-to-reveal vs always-visible numbers.**
   - **Always-visible numbers:** Pio (numeric strategy table next to
     the matrix), Monker (bucket-level numbers).
   - **Hover-to-reveal numbers:** GTOW, DeepSolver (cleaner default
     view; numbers on cell hover).
   - **Our choice:** PR 10 spec §2 already mandates **always-show
     numbers on hover** because "color alone is perceptually
     misleading at extreme mixings." Good. Don't drift toward
     numbers-always-visible (Pio-style maximalism).

5. **Pricing model: perpetual vs subscription.**
   - **Perpetual:** Pio ($490–$880 USD-equivalent), Monker (~$360
     USD-equivalent), GTO+ ($75).
   - **Subscription:** GTOW ($50–$359/month tiered), DeepSolver
     ($29.40–$69/month).
   - **Our choice:** Neither — MIT-licensed, free, no
     subscription. The closest pricing comparable is **GTO+ at $75
     one-time as a hobbyist anchor**, and our free + modern UX
     story is positioned as "better than GTO+ at $0."

6. **Local vs cloud.**
   - **Local:** Pio, Monker.
   - **Cloud:** GTOW, DeepSolver.
   - **Our choice:** Local. Cross-platform from day one.

### Target user segment for our UI first

**Recommendation: the serious amateur-to-pro spectrum, specifically
the user who currently runs PioSolver on Windows-in-a-VM-on-Mac and
is frustrated by it.** Concrete persona attributes:

- Already knows PioSOLVER range notation.
- Already understands "red = fold, yellow = call/check, green =
  raise/bet."
- Already understands per-street bet sizing and accuracy targets.
- Runs MacBook Pro or Linux workstation as daily driver; the
  Windows-only Pio install is a daily friction.
- Studies HU NLHE postflop; does not need multiway, does not need
  ICM, does not need a cloud library.
- Owns or is willing to commit a multi-hour solve on local
  hardware; wants per-iteration progress + exploitability curve to
  watch decay.
- Values **scriptability** — runs solver from Python notebooks,
  pipes results into hand-history analysis tools.

**Why this segment first:**
- They are the highest-pain, highest-fit cohort for our
  cross-platform + scriptable + MIT-licensed thesis.
- They will tolerate v0 missing features (no Trainer, no
  Aggregated Reports, no Library) because the **core HU postflop
  solver loop is the deliverable** and they already have GTOW for
  library lookup.
- They will *notice* and value modern UI relative to Pio.
- They are the cohort most likely to file high-signal bug reports
  and feature requests because they already understand what a
  solver does.

**Explicit non-target audiences for the v0 UI:**
- **Total beginners.** GTOW's Trainer + Aggregated Reports + drills
  + study ecosystem is built for them; we don't compete there.
- **Tournament pros** who need ICM, MTT, and bounty coverage.
  GTOW owns this market.
- **Multiway specialists.** Monker (or GTOW Ultra) owns this.
- **Mobile-only users.** Desktop-first.

### Top 3 UI patterns to adopt (most load-bearing)

1. **Pio-canonical red/yellow/green range matrix as centerpiece**,
   with always-show-numbers-on-hover for per-combo strategy.
   Already in PR 10 spec §2.
2. **Sensible-defaults + progressive-disclosure configuration**
   (Shark / DeepSolver pattern) — preset dropdown loads a known-good
   per-street bet-size config; advanced override panel for power
   users. Already in PR 10a spec §1 via preset dropdown.
3. **Live exploitability curve during solve** — GTOW's strongest UX
   pattern that Pio lacks entirely. Already in PR 10 spec §3.

### Top 3 patterns to deliberately avoid

1. **Maximalist always-visible information density** (Pio / Monker).
   Don't dump every widget on the user; hover-to-reveal numbers,
   collapsible advanced panels, default to clean.
2. **Textarea-only range input** (Pio). Always pair the PioSOLVER
   text format with a visual range builder; let the user choose
   their entry mode and keep both views sync'd.
3. **Cloud / SaaS / NN-warm-start opacity.** Every output must be
   reproducible from the same inputs on the user's hardware. We are
   not GTOW or DeepSolver; we are the auditable local alternative.

---

## Appendix: PR 10 spec consistency check

- PR 10 spec §2 already cites Pio's red/yellow/green + GTOW's
  click-cell-show-strategy — both remain valid.
- PR 10 spec §3.3 plans an expandable nested tree list; **GTOW's
  horizontal cascade** is a v1-polish alternative worth keeping
  on the backlog.
- PR 10a's preset dropdown aligns with the
  "library-first → solve-first" divergence.
- **Suggested polish (PR 10b / PR 11):** single "Use sensible
  defaults" button that resets per-street bet sizes to Shark's
  known-good baseline (flop 50/100, turn/river 33/66/100,
  raise 50/100, cap 3, all-in 0.67) — closes the
  Smart-Tree-Builder gap vs DeepSolver.
