# Plan: Build a competitive GTO solver for No-Limit Hold'em

**Status:** Phase 1 — scoping & feasibility analysis. **No implementation yet.**

---

## Context

The existing `poker_solver/` (built earlier this session) is a Monte Carlo **equity** calculator — emphatically **not** a GTO solver. The user's actual ask is much larger: build a Game-Theory-Optimal solver competitive with PioSolver / GTO Wizard / MonkerSolver, covering:

- No-Limit Hold'em
- Heads-up through 9-handed
- Preflop → river
- 1 BB to 500 BB effective stacks
- Multiple bet sizes (discrete; possibly continuous — see analysis below)
- For every decision node: EV of each action + equilibrium mixing frequency
- Runs on a 16 GB MacBook Pro (Apple Silicon, Metal GPU)
- Professional GUI: range charts, decision tree, EV display, etc.
- **All references & research downloaded locally** into the project folder for offline access (item #8 — added in the user's follow-up).

This file will be expanded through the planning workflow. **Code already written this session (the equity calculator) will be reused, not thrown away** — it gives us a fast `evaluate()` + `equity()` to bootstrap value/leaf computations and sanity checks.

---

## Honest feasibility check (before any scoping decisions)

The full ambition above is broader than any single commercial product:

| Tool | What it actually does |
|---|---|
| **PioSolver** | Heads-up postflop only. No preflop. No multiway. C++ core, Windows-first. Solves a single spot in seconds to many hours depending on tree size. |
| **MonkerSolver** | Multiway postflop (3-way primarily). Slower, heavier. Quality of multiway "equilibrium" is murky — Nash isn't unique with ≥3 players. |
| **GTO Wizard** | **Mostly a precomputed library of solves + a UI**, plus an in-cloud solver. The desktop user is not solving real-time; they're querying. |
| **Simple Postflop, GTO+, Wasilewski** | Variants of the above, mostly HU postflop. |
| **Pluribus (Brown & Sandholm 2019)** | 6-max NLHE bot using blueprint + real-time depth-limited subgame solving. Trained on a 64-core server; **still considered a research milestone, not a product**. |
| **DeepStack, Libratus** | HUNL research; specialized hardware. |

Reality on 16 GB RAM, single MacBook:
- **HUNL postflop with reasonable abstractions** → minutes to hours per spot. Tractable. This is the realistic MVP.
- **HUNL preflop** (full game tree to river) → much harder; usually solved separately with deep abstraction.
- **Multiway postflop** → research-grade; expensive RAM-wise; equilibrium concept itself is murky.
- **Full multiway preflop + postflop, 1–500 BB, arbitrary bet sizes** → **not feasible at commercial quality on consumer hardware**, full stop. Even GTO Wizard precomputes this on a server fleet.

Bet sizes: continuous-bet solving exists in research (Brown's action translation, action abstraction via tree pruning) but **everyone in practice discretizes** (e.g. 33% / 50% / 75% / pot / 2× / all-in). Continuous is a research direction, not a v1 deliverable.

EV + frequency per action: this falls out naturally from CFR (the regret table gives the average strategy = equilibrium mixing; the value at each infoset gives EV). Free output of the standard approach.

---

## Honest epistemic answer to "is the FULL goal possible?"

User clarified: **goal is the complete 2–9 player, preflop-through-river, 1–500 BB, multi-bet-size NLHE solver.** Asked for an honest yes/no.

**Answer: no, not at the full unabstracted scope, not on a 16 GB MacBook, and not on any single consumer machine available today.** This is not a tool limitation — it's the state of the field.

Concretely:

| Aspirational scope | Closest existing thing | Reality |
|---|---|---|
| HU postflop solver | PioSolver, postflop-solver (Rust) | ✅ Solo dev can build, 6–12 months. 16 GB sufficient with abstraction. |
| HU preflop (full tree to river) | Pio scripting, GTOW preflop | ✅ With aggressive abstraction. +3–6 months. |
| 3-handed postflop | MonkerSolver, GTOW | ⚠️ Borderline. Multiway Nash not unique; CFR converges to an *approximate equilibrium*, not true Nash. RAM-tight on 16 GB. |
| 6–9 player preflop+postflop | **Nothing solves this exactly.** Pluribus = blueprint approximation, not a solver. GTOW = precomputed library on a cluster. | ❌ Not feasible at PioSolver-class quality on consumer hardware. |
| Continuous bet sizes | Research papers on action translation | ❌ Everyone discretizes. Continuous is theoretical. |
| 1–500 BB seamless | Stack-depth-specific solves | ⚠️ Usually solved at each depth separately. Interpolation is approximate. |

**Why this is the situation:**
- Game tree size grows combinatorially per added player; 9-handed full tree is many orders of magnitude beyond HU.
- Multiway Nash has multiple equilibria; convergence guarantees of CFR (the engine every commercial solver uses) degrade with ≥3 players.
- Pluribus required 8 days on a 64-core, 512 GB-RAM server. That's the benchmark for what current research can do for 6-max, and it's *not* a solver — it's a near-optimal bot.

**Why "competitive with GTO Wizard" is not one product:**
- GTOW isn't primarily a real-time multiway solver — it's a **precomputed library + UI + some cloud solving**.
- Matching GTOW's coverage requires three separate things: (a) a correct solver engine, (b) significant compute hours to populate a library of common spots, (c) a UI to query it. Only (a) fits a single MacBook.

**Phased proposal (what we'd actually deliver):**

| Phase | Scope | Approx. effort | Outcome |
|---|---|---|---|
| 1 | **HUNL postflop solver** (Pio-class) | 3–6 months focused | Beats every open-source solver; competitive with PioSolver on its scope |
| 2 | **HUNL preflop solver** | +2–3 months | Full HU game, preflop→river |
| 3 | **3-handed postflop** (heavy abstraction) | +3–6 months | Approximate equilibria, honest about limits |
| 4 | **GUI + library mode** | +2–3 months for GUI; library compute is open-ended | Pre-solve common spots, view in-app |
| 5 | **4–6 handed expansion** | Open-ended; cluster compute helps | Research-grade |
| 6 | **7–9 handed** | Open-ended; cluster compute required | Aspirational; equilibrium concept itself murky |

Phase 1+2 is the realistic ceiling for a solo MacBook project that I'd call "professional grade." Phases 3+ either require cloud spend or accept lower-quality approximations as the deliverable. **I recommend committing to 1+2 as the explicit MVP**, with 3 as a stretch goal that we re-evaluate after 1+2 are working.

---

## No-cloud constraint (user-confirmed)

User: *"generally want to avoid cloud expenditures."* This is decisive for scope.

**With MacBook-only compute, what's possible:**

| Goal | MacBook-only? | Honest take |
|---|---|---|
| HUNL postflop solver | ✅ Yes | Core deliverable; Pio-class output for HU |
| HUNL preflop solver | ✅ Yes | Smaller tree than postflop |
| 3-handed postflop | ⚠️ Borderline | Heavy abstraction, slow training, *approximate* equilibrium (multiway CFR has no convergence guarantee) |
| 4-6 handed postflop | ❌ No | Tree size + RAM impractical; quality would be unacceptable |
| 7-9 handed anything | ❌ No | Out of reach on any single consumer machine |
| Multiway preflop (4+ players) | ❌ No | Pluribus needed a 64-core / 512 GB cluster; no shortcut exists |
| Continuous bet sizes | ❌ No | Theoretical only; everyone discretizes |
| 1–500 BB seamless | ⚠️ Discrete | Have to solve per stack depth; interpolation is approximate |
| **GTOW-class library** (10k+ spots) | ❌ No | Compute cost is months of cluster time |
| **Small personal library** (~100–500 spots) | ✅ Yes | Curate slowly: solve overnight, accumulate over weeks/months |

**Honest bottom line on "competitive with PioSolver / GTO Wizard":**
- ✅ **Competitive with PioSolver** for HU local solving — achievable on MacBook alone.
- ❌ **Competitive with GTO Wizard** — **not achievable without cloud.** GTOW is fundamentally a cloud + multiway-preflop-library + neural-value-nets product (their Feb 2026 launch). A solo MacBook project cannot match their coverage. We can build a better *engine* for many spots, but not a comparable *library*.

**Library clarification (correcting earlier vague framing):**
A "precomputed library" still requires running the engine; the library and the engine are not alternatives. Without cloud, the realistic library is:
- ~100–500 spots curated over months by running overnight solves on the MacBook
- Stored in a personal database, queryable from the UI
- *Not* a substitute for the engine — it's a UX layer on top of it

There is **no public source of pre-solved NLHE spots** to download. GTOW's data isn't licensable; PioSolver community trees are tied to Pio's binary format. We'd have to generate any library ourselves.

---

## Pending scoping decisions (asking the user now)

**Resolved:**
- ~~Cloud compute access~~ → **NONE.** MacBook-only is the constraint. This rules out GTOW-class multiway and large libraries.
- ~~Delivery mode~~ → **Real-time engine + optional small personal library** built incrementally from overnight solves. (No "library-only" alternative exists without cloud.)

**Resolved (continued):**
- ~~v1 engine scope~~ → **HUNL postflop + preflop together.** ~6–9 months focused work. Matches PioSolver scope; closes the OSS preflop gap.

**Still open:**
- [ ] **Implementation language** — Rust (strongly recommended by research), C++, hybrid, pure Python
- [ ] **GUI timing** — defer vs alongside-engine vs library-first UX
- [ ] *(decided later, after first solves)* Acceptable per-spot solve time → drives abstraction depth

---

## Research plan (Phase 1 — ✅ COMPLETE)

Three Explore agents ran in parallel and reported back. Their full reports live in this conversation; the synthesis below captures the load-bearing findings.

### Phase 1 synthesis

**Open-source landscape (HU postflop only — universally):**

| Tool | Lang | Status | Algorithm | Notes |
|---|---|---|---|---|
| `b-inary/postflop-solver` | Rust | **Suspended Oct 2023** | DCFR γ=3.0 | Cleanest architecture; MIT; founder went commercial. **Our primary reference.** |
| `bupticybee/TexasSolver` | C++ | Unmaintained (Nov 2021) | Vanilla CFR | 172s flop vs Pio 242s; AGPL-v3 (license concern for derivatives) |
| `24parida/shark-2.0` | C++ | **Active (Apr 2026)** | DCFR + int16 compression | Most recent OSS attempt |
| OpenSpiel | C++/Py | Active | Various | Research toolkit; toy games only |
| RLCard | Python | Active | NFSP/DQN | RL toolkit, not a GTO solver |
| Slumbot 2019 | C++ distributed | Reference only | MCCFR | ACPC 2018 champion; 2018-era reference |

**Critical gap in OSS: no production preflop solver.** Every public solver is HU postflop. Building HU preflop+postflop together is a real differentiator, not just a feature.

**Algorithm consensus for v1:**
- **HUNL postflop:** **DCFR** (Discounted CFR, Brown & Sandholm 2019), γ=3.0. Better convergence than CFR+ on NLHE.
- **HUNL preflop:** Same DCFR. Smaller tree than postflop; solvable with light abstraction.
- **Multiway 3+:** CFR has **no convergence guarantees** for ≥3 players. Pluribus's pragmatic answer: produce a *blueprint approximation*, augment with real-time depth-limited search. **Frame any multiway deliverable as approximate, not solved.**
- **Action abstraction (default menu):** **33% / 75% / 150% pot + all-in**, with 3-raise cap per street before forcing all-in. Continuous is theoretical only — everyone discretizes.
- **Card abstraction:** Imperfect-recall, EMD-based bucketing (NOT raw EHS). Targets: ~256 flop / 128 turn / 64 river buckets.
- **Deep CFR / value networks: skip for v1.** Adds 2 NNs + training-distribution tuning. Tabular DCFR is faster to implement and debug.
- **Public chance sampling:** Worth adding after v1 baseline works (significantly cuts iterations).

**Hardware / Apple Silicon:**
- **GPU acceleration is a distraction.** CFR's hot loop is sparse, irregular access, memory-bandwidth-bound. PyTorch MPS underperforms CPU on sparse ops; MLX is for dense linear algebra; **jax-metal is discontinued (Dec 2025)**.
- **Right path: native CPU.** ARM NEON 128-bit SIMD + cache blocking + cache-friendly infoset layout. M-series memory bandwidth (~120 GB/s) is the real ceiling.
- **16 GB capacity:** ~50–100M infoset-actions comfortable; ~200M starts thrashing. Forces aggressive abstraction.
- **macOS distribution:** codesign + notarize + .dmg is automatable, ~10 min/release. Apple dev cert $99/yr.

**Industry watershed:**
- **GTO Wizard launched 9-way preflop solving Feb 2026** via cloud (CFR + neural value networks). This redefines "competitive with GTOW" — it's now a cloud SaaS, not a desktop tool. A solo MacBook project cannot match GTOW's library coverage.
- **PioSolver Pro remains the desktop standard** for HU local solving. Reachable as a goal.
- **DeepSolver** (cloud SaaS) does HU postflop in seconds with neural value functions — 10-100× CFR speed, but postflop-only and commercial.

### Implications for v1 architecture

- **Goalpost = PioSolver for HU local solving**, not GTOW for multiway cloud library.
- **Language: Rust** (postflop-solver proved Rust matches C++ on CFR loops; single static binary; PyO3 for Python bindings; cleanest macOS distribution).
- **Engine: tabular DCFR** + public chance sampling once baseline works.
- **Action abstraction:** 33/75/150/AI, 3-raise cap.
- **Card abstraction:** imperfect-recall EMD bucketing (256/128/64).
- **GPU: no.** ARM NEON + cache blocking on CPU.
- **GUI: defer.** CLI + Python bindings + Jupyter for validation. UI in later phase.

### References to download into `references/` (post-plan-mode)

**Papers — must-have:**
- Tammelin 2014, *Solving Large Imperfect Information Games Using CFR+*
- Brown & Sandholm 2019, *Solving Imperfect-Information Games via Discounted Regret Minimization* (DCFR)
- Brown & Sandholm 2019, *Depth-Limited Solving for Imperfect-Information Games*
- Brown, Lerer & Sandholm 2018, *Deep Counterfactual Regret Minimization*
- Brown & Sandholm 2017, *Superhuman AI for heads-up no-limit poker: Libratus* (Science)
- Zinkevich et al. 2008, *Regret Minimization in Non-Zero-Sum Games* (multi-player honest assessment)
- Brown et al. 2020, *Combining Deep RL and Search* (ReBeL)
- Brown & Sandholm 2019, *Superhuman AI for multiplayer poker* (Pluribus, Science)

**Papers — nice-to-have:**
- 2024 hyperparameter scheduling for CFR (arxiv 2404.09097)
- 2024 GPU-accelerated CFR (arxiv 2408.14778) — to confirm GPU isn't worth it on Apple Silicon
- Survey of GTO poker (arxiv 2401.06168)
- Potential-aware EMD abstraction (Sandholm 2014)

**Repos to clone into `references/code/`:**
- **`noambrown/poker_solver`** — Noam Brown's personal river-only solver. **Critical reference** (Brown is the author of DCFR / Pluribus / Libratus papers). Differential-test target for river spots.
- `b-inary/postflop-solver` — primary architectural reference (Rust)
- `24parida/shark-2.0` — actively maintained C++ DCFR (Apr 2026)
- `bupticybee/TexasSolver` — perf reference (license: AGPL — read-only for inspiration, not derivation)
- `ericgjackson/slumbot2019` — distributed MCCFR reference
- `google-deepmind/open_spiel` — game engine reference

**Blog posts:**
- GTO Wizard "How Solvers Work" + the Feb 2026 multiway launch post
- PioSolver technical docs
- GTOWizard "Quirks of Nash in Multiway"

1. **Existing solvers** — code architecture and trade-offs
   - Open source: TexasSolver (https://github.com/bupticybee/TexasSolver), shark-2.0 (https://github.com/24parida/shark-2.0), OpenSpiel, RLCard, OpenHoldem, PokerKit
   - Closed-source: Pio / Monker / GTOW / GTO+ from public material (GTOW blog post linked, talks, papers)

2. **Algorithm literature** — CFR family + recent advances
   - Vanilla CFR, CFR+, Discounted CFR, **MCCFR (External Sampling, Outcome Sampling)**, Deep CFR
   - Brown's chain: action translation, Modicum, Pluribus blueprint+search, ReBeL
   - Abstraction: action abstraction, card abstraction (EHS, OCHS, k-means bucketing), perfect vs imperfect recall
   - Multiway: cited papers on multi-player CFR + N-CFR; honest read on what works

3. **Apple Silicon / GPU compute** — practical paths
   - PyTorch MPS, Apple MLX, jax-metal, Rust ↔ Metal bindings
   - Whether CFR (sparse, memory-bandwidth-bound) actually benefits from Metal vs staying CPU-vectorized
   - Native cross-compile story for distributing on macOS

---

## Subagent task layout (user's initial proposal — will critique after research)

User proposed 7 tracks. **Initial critique:**

| # | User's task | Critique |
|---|---|---|
| 1 | Review existing products (open + closed) | Good. Better as a **research** track (Explore agent, WebSearch + repo reads), not implementation. |
| 2 | Review research literature (CFR etc.) | Good. Same Explore-agent pattern. |
| 3 | Review optimization algorithms | Overlaps heavily with #2 — should merge. CFR is the optimization; there is no "convex/non-convex" general step here (CFR converges to ε-Nash via regret minimization, not gradient descent). I should clarify this misconception in the plan. |
| 4 | Build GUI | Should be **gated on a working engine**. Building UI before solver wastes effort. |
| 5 | Consider C++/Rust vs Python | Critical decision; needs to be made **before** writing engine code, not concurrently. |
| 6 | Continuous sanity checks (MDF, fold equity etc.) | Excellent — this is the **correctness validation track**, should run continuously across phases. Add: validate against known-solved games (Kuhn poker, Leduc poker) where exact equilibrium is computable. |
| 7 | Compare to pro tools, report back | Output of research, not its own track. |
| 8 | Download references locally | Good — becomes an `R0` track that runs alongside research. Agents identify URLs; we download into `references/{papers,code,blog}/` after plan exits. |

**Restructured task tracks (proposed):**

- **R0** Local references library — download papers + repos + blog posts into `references/`
- **R1** Research existing open-source solvers (1 Explore agent)
- **R2** Research CFR + algorithm literature (1 Explore agent, merges user's #2 + #3)
- **R3** Research industry tools + Apple Silicon perf (1 Explore agent, merges user's #1-closed + #5)
- **E1** Engine: hand evaluator, game tree, CFR core
- **E2** Abstraction: action discretization + card bucketing
- **E3** Validation: Kuhn/Leduc exact-solve, poker-intuition checks (MDF, fold equity, polarized ranges, etc.)
- **U1** GUI (gated on E1 producing usable solves)
- **D1** Distribution: packaging for macOS (signed app, .dmg)

What's Claude Code (this) good at vs cowork:
- **Claude Code:** literature scans, code implementation, test scaffolding, packaging, benchmarking, doc writing
- **Cowork / user:** poker-intuition validation, UI aesthetic decisions, deciding which spots to study, multi-day training runs that need supervision

---

## Final recommended approach

### Locked decisions

- **Reference-first operating rule.** Before any technical claim (CFR formulas, competitor architecture, paper findings, algorithm details), **check the local `references/` folder first**. Never guess or recall from training data when an authoritative local source exists. The `references/README.md` is the topic-to-file index. If a fact isn't locally cached and the question is non-trivial, fetch and save it rather than answering from memory.
- **Project license: MIT** (locked). Preserves all future options. Implies we cannot copy code from AGPL or unlicensed references.
- **Codebase origin: build fresh.** PRs 1–4 (Kuhn / Leduc / HUNL tree / card abstraction) are fresh-write. **PR 5+ ports only from MIT/Apache references** with attribution: `noambrown_poker_solver` (MIT, Brown's own Python+C++ implementation), `slumbot2019` (MIT, distributed MCCFR), `open_spiel` (Apache 2.0, used as Kuhn/Leduc correctness oracle). **Reading AGPL references for architectural understanding is fine; copying their code is not.**
- **License audit of cloned references** (verified by repos-review agent):
  - ✅ MIT: `noambrown_poker_solver`, `slumbot2019` — safe to port from
  - ✅ Apache 2.0: `open_spiel` — safe to port from
  - ❌ AGPL v3: `postflop-solver`, `TexasSolver` — read-only inspiration; never copy
  - ❌ No LICENSE file: `shark-2.0` — defaults to all-rights-reserved; read-only inspiration
- **Original Ultraplan section incorrectly described `postflop-solver` as MIT** — that was wrong; corrected here.
- **Goal posture:** Compete with PioSolver on HU local solving. **Do not** chase GTO Wizard parity — that requires cloud + a multiway library we cannot fund or generate.
- **v1 scope:** HUNL postflop + preflop together. ~6–9 months focused work. Closes the OSS preflop gap. *(user-confirmed)*
- **Compute:** MacBook only. No cloud spend. *(user-confirmed)*
- **Engine algorithm:** Tabular **DCFR** (Discounted CFR, γ=3.0). Add public chance sampling once baseline converges. Skip Deep CFR for v1.
- **Action abstraction:** **33% / 75% / 150% pot + all-in** per node, 3-raise cap before forcing all-in.
- **Card abstraction:** Imperfect-recall, EMD-based bucketing. Targets: 256 flop / 128 turn / 64 river.
- **Hardware path:** Native CPU with ARM NEON SIMD + cache-blocked infoset layout. No GPU — MPS / MLX / jax-metal don't help CFR's sparse access pattern.
- **Validation gates:** Kuhn poker exact-solve, Leduc poker exact-solve, parity vs postflop-solver outputs on a fixed test set, poker-intuition checks (MDF, fold equity, polarization on overpair vs draw-heavy boards).

### Trajectory at a glance (incremental delivery, NOT scope cutting)

We're building the **whole** strategic vision (HUNL postflop + preflop, two-tier Python+Rust with differential testing, NiceGUI UI, MacBook-only). The PR sequence below is staging — each one lands a working chunk that the next builds on. The user checkpoints between PRs but the destination is the full vision.

| PR | Scope | Why it exists |
|---|---|---|
| **Phase 0** | References download + custom agents + dual toolchain | No engine code yet — foundation everything else depends on |
| **PR 1** | Kuhn poker + build foundation (Python ref, Rust port, diff test, CLI) | Smallest test fixture that proves the toolchain, the protocol, and the diff-test harness |
| **PR 2** | Leduc poker (both tiers) | Adds chance-node handling; closed-form check |
| **PR 3** | HUNL tree builder (Python) + action abstraction (33/75/150/AI) | First real HUNL game tree |
| **PR 4** | Card abstraction (EMD bucketing) | Required to fit HUNL in memory |
| **PR 5** | HUNL postflop solve (Python reference) | First real solve; `equity.py` is leaf oracle |
| **PR 6** | HUNL postflop port to Rust | Study `postflop-solver`/`shark-2.0` for *understanding only* (AGPL/unlicensed); port from `noambrown_poker_solver` (MIT) where applicable; otherwise re-derive from papers + Python reference. Diff-test against Python tier. |
| **PR 7** | River-spot diff test vs `noambrown/poker_solver` | Cross-validates Rust tier against a third independent implementation |
| **PR 8** | NEON SIMD + cache-blocking perf work in Rust | Perf gate: Pio-class solve time |
| **PR 9** | HUNL preflop (both tiers) | Closes the OSS preflop gap; integrates with postflop |
| **PR 10** | NiceGUI scaffold | UI built on top of the validated engine |
| **PR 11** | Library mode + macOS packaging (codesign + .dmg) | Distribution-ready |
| **PR 12** | 3-handed postflop stretch (optional) | Explicitly approximate; multiway honesty in UI |

Each PR ends with: `scripts/check_pr.sh` → `pr_report.md` → user review → user OK → commit + push (with explicit OK per push).

### Decided in dialogue (user can still redirect)

- **Language: two-tier** — **Python reference + Rust production**, with **differential testing** between them. User context: Python-strong, C++-rusty, Rust-zero, wants both an "easily interpretable" implementation for testing and a "super optimized" implementation for actual use.
  - **`poker_solver/` (Python reference, ground truth):** full implementation of evaluator, equity calc, range parser, tree builder, action/card abstraction pipeline, plus a **slow but correct DCFR** that solves *small games only* (Kuhn poker, Leduc poker, river-only spots, small toy trees). Easy to read, easy to iterate on. Not expected to solve full HUNL postflop on its own.
  - **`crates/cfr_core/` (Rust production):** mechanical port of the same algorithms, optimized for full HUNL postflop + preflop. NEON-vectorized, cache-blocked. PyO3 bindings expose it to Python.
  - **Differential testing:** every test runs both implementations on the small games and asserts the strategies/EVs agree within float tolerance. Once that gate passes, Rust is trusted for the full HUNL solves where Python can't keep up.
  - **Cost:** ~1.5–2× the implementation work (every feature lives in two places for the subset both cover). The testability win is worth it: porting Python→Rust is mechanical translation, not from-scratch design, and the diff-test catches subtle bugs immediately.
  - **Distribution:** Python wheels via maturin bundle the Rust core; single `pip install` for the user.
- **Architectural validation:** Noam Brown's own `noambrown/poker_solver` (cloned in Phase 0) has both `cpp/` and `python/` directories — he uses this exact two-tier pattern. We're not inventing the structure.

- **UI: parallel priority, secondary to engine correctness** *(revised again after user clarification: nice UI matters, but **not at the cost of a working accurate solver**; Noam Brown's repo isn't a UI reference, just a differential-test target).* Approach:
  - **Priority ordering, explicit:** engine correctness > engine perf > UI polish. If they ever conflict, engine wins. UI work pauses for engine bugs, not vice versa.
  - **Built alongside the engine, not after.** Every engine feature ships with a UI view in the same milestone — but the UI feature is allowed to lag the engine feature by ~2 weeks if engine work needs the time.
  - **Recommended UI tech: NiceGUI** (Python-native, modern web components, fast iteration) — matches user's Python strength and respects the engine-first priority by minimizing UI tech overhead. Upgrade path to **Tauri + web frontend** is preserved if/when NiceGUI hits its limits in Phase 4 polish.
  - **Core views from day one:** range-matrix (13×13), board input, solver run controls with live exploitability readout, decision-tree browser with action EVs + frequencies per node.
  - **Polish in waves:** functional first, beautiful in Phase 4. Day-one UI is "modern web app" tier; Phase 4 pushes toward "polished tool" tier.

### Phased build

**Phase 0 — Foundations (2–3 weeks)**

- **Step 0 (gating everything else): download AND review all references.** No coding starts until this completes. Three parallel sub-tracks:
  - **Sub-track A — Code repos.** `git clone --depth 1` each into `references/code/`:
    - `noambrown/poker_solver` (already cloned) — Brown's own Python+C++ two-tier; differential-test target for river spots
    - `b-inary/postflop-solver` — primary architectural reference for HUNL postflop Rust (PR 5 port source)
    - `24parida/shark-2.0` — active C++ DCFR (Apr 2026)
    - `bupticybee/TexasSolver` — C++ perf reference (AGPL — **read-only inspiration; never copy code**)
    - `ericgjackson/slumbot2019` — distributed MCCFR reference
    - `google-deepmind/open_spiel` — game engine + algorithms reference
    - After cloning, a subagent reads each and writes a 1-page `references/code/<repo>/_NOTES.md` capturing: algorithm choice, key files, abstraction strategy, what's worth porting, license, last-commit date, gotchas
  - **Sub-track B — Papers.** `curl` each PDF into `references/papers/`:
    - Tammelin 2014, *CFR+* — https://arxiv.org/pdf/1407.5042
    - Brown & Sandholm 2019, *DCFR* — https://arxiv.org/pdf/1809.04040
    - Brown & Sandholm 2018, *Depth-Limited Solving* — https://arxiv.org/pdf/1805.08195
    - Brown et al. 2018, *Deep CFR* — https://arxiv.org/pdf/1811.00164
    - Zinkevich et al. 2008, *Regret Minimization in Non-Zero-Sum Games* (multiway honesty) — https://arxiv.org/pdf/1305.0034
    - Brown et al. 2020, *Combining Deep RL and Search* (ReBeL) — https://arxiv.org/pdf/2007.13544
    - 2024 *Faster Game Solving via Hyperparameter Schedules* — https://arxiv.org/pdf/2404.09097
    - 2024 *Survey on GTO Poker* — https://arxiv.org/pdf/2401.06168
    - Libratus (Science 2017) + Pluribus (Science 2019) — preprints if accessible; abstract + supplementary otherwise
    - A subagent reads each and adds a 4–8 sentence abstract + key-takeaway block to `references/papers/_INDEX.md`
  - **Sub-track C — Blog posts + competitor products.** Fetch and save as Markdown into `references/blog/` and `references/products/`:
    - GTO Wizard "How Solvers Work" (linked by user) — https://blog.gtowizard.com/how-solvers-work/
    - GTO Wizard "Multiway Preflop" launch (Feb 2026)
    - GTO Wizard "Quirks of Nash in Multiway"
    - PioSolver technical docs + product comparison
    - MonkerSolver public docs
    - DeepSolver public docs
    - A subagent reads each and produces a 1-paragraph "what they actually do / what to learn from them" note in `references/_COMPETITORS.md`
  - **Aggregate output: `references/README.md`** — single index mapping topics (e.g. "DCFR hyperparameters", "EMD card abstraction", "Pluribus blueprint search") to the local file(s) that authoritatively cover them. This is what I check first on any future technical question.
  - **Verification gate:** `references/README.md` exists, all sub-track index files exist, all paper PDFs are non-empty, all repos cloned without errors. **Until this gate passes, no code is written.**

- **Step 1: lock UI tech — default NiceGUI.** Python-native, fast to build, matches engine-first priority by minimizing UI tech overhead. User can override toward Tauri+web. Decision recorded in plan; UI work doesn't start until PR 10.

- **Step 2: set up dual toolchain.** Python (uv/poetry, existing `poker_solver/` package preserved) + Rust (cargo). PyO3 + maturin for the Python↔Rust bridge; `pip install -e .` builds both. Verification: `cargo --version`, `rustc --version`, and a hello-world Rust extension importable from Python.

- **Step 3: brief Rust orientation.** Focused on what the CFR core touches: ownership/borrows, slices, iterators, `Vec<f64>`, `#[pyfunction]` / `#[pyclass]` macros, basic NEON intrinsics. ~3–5 days of focused reading + small exercises. Co-work: I prepare examples, user works through them.

- **Step 4: define custom agents.** Write configs to `~/.claude/agents/` so subsequent PRs parallelize cleanly without bootstrap cost:
  - **`cfr-engine-implementer`** — implements CFR algorithms in Python or Rust per a tight spec; success gate = differential test passes. Used heavily in PRs 1, 2, 5, 6, 9.
  - **`pr-check-runner`** — runs `scripts/check_pr.sh` (tests + clippy + ruff + mypy + diff-tests + license + perf) and produces `pr_report.md`. Used at the end of every PR.
  - **`poker-validator`** — runs the intuition gauntlet (MDF / fold equity / polarization on constructed spots) and explains failures in poker terms, not just math. Becomes load-bearing in PRs 5+.
  - **`references-curator`** — keeps `references/README.md` index current as new papers/repos/notes are added during work. Used continuously.
  - **`rust-porter`** — specialized for PR 6: ports Python reference code to Rust with diff-tests as the success criterion; familiar with PyO3 idioms.
  - The configs get reviewed via `/agents`; user can edit any prompt.

- Directory layout:
  - `poker_solver/` — Python reference (existing equity calc preserved + extended)
  - `crates/cfr_core/` — Rust production crate
  - `ui/` — UI app (post-Phase-1a; NiceGUI module)
  - `tests/` — differential tests + Kuhn/Leduc/intuition gauntlet
  - `references/` — local copies of papers, repos, blog posts, products; gitignored at the `code/` level
  - `scripts/` — `setup_references.sh`, `check_pr.sh` (see Between-PR check battery)

**Phase 1a — HUNL postflop Python reference + UI scaffold (3–5 months, parallel tracks)**

*Engine track (Python):*
- Game tree builder (street-by-street, action abstraction wired in) — pure Python with dataclasses
- Action abstraction: 33/75/150/AI menu with 3-raise cap, configurable
- Card abstraction pipeline: EMD-based imperfect-recall bucketing, numpy-heavy
- Slow tabular DCFR (γ=3.0) — sufficient for solving Kuhn, Leduc, and small river-only NLHE subtrees
- Extends existing `poker_solver/cli.py` with a `solve` subcommand
- Validation: matches Kuhn/Leduc closed-form equilibria; matches Noam Brown's `poker_solver` on river spots

*UI track (parallel):*
- App skeleton in chosen UI tech (NiceGUI or Tauri+web) — Phase 0 Step 2 decision
- **Range-matrix view (13×13 grid)** — combo frequencies, color-coded by action mixing, click-to-inspect
- **Spot input form** — board cards, hole-card ranges (string + visual), bet sizes, stack depths, position
- **Solver run controls** — start/pause/cancel, iteration counter, live exploitability readout, ETA
- **Decision-tree browser** — collapsible action tree per node with EV + frequency labels
- **Functional polish, not aesthetic polish** — buttons that work, panels that resize, readable typography. Beauty pass in Phase 4.
- Engine integration via the same `poker_solver` Python API the CLI uses (UI and CLI share the orchestration layer)

**Phase 1b — HUNL postflop Rust port + UI integration (2–3 months)**

Mechanical translation of Phase 1a to Rust. Same algorithms, optimized. UI plugs into the Rust solver via the same Python bindings.

- `crates/cfr_core/`: compact tree representation (flat arrays, indexed traversal), DCFR with NEON-vectorized regret updates and cache-blocked traversal
- Hand evaluator port (Rust port of `poker_solver/evaluator.py`, ~200 lines)
- Public chance sampling (added after baseline matches Python)
- PyO3 bindings: `solve(tree_spec_bytes, iterations) -> strategy_tables`
- **Differential tests:** Rust output must match Python reference on Kuhn/Leduc/river spots within float tolerance; the gate is automated, runs on every Rust change
- **UI now switches to Rust solver by default** for full HUNL spots; Python reference remains for Kuhn/Leduc and debugging

**Phase 1 test gates (both implementations):**
- Kuhn poker exact equilibrium reached (Python AND Rust)
- Leduc poker exact equilibrium reached (Python AND Rust)
- River-only HUNL spots: Python vs Rust diff < tolerance; both vs Noam Brown's solver < tolerance
- `postflop-solver` parity: Rust matches on a fixed set of flop spots (strategy KL divergence per infoset < threshold)
- Exploitability decreases monotonically over iterations

**Phase 1 perf gate:** Rust solves a common flop spot (3 bet sizes) in ≲30 min on the MacBook.

**Phase 2 — HUNL preflop engine (3–5 months; same two-tier pattern)**
- *Phase 2a (Python):* extend tree builder with full preflop action structure (2.5/3.0/etc. open sizes, 3-bet/4-bet/5-bet trees, jam thresholds); stack-depth parameterization (input as parameter, solve at one depth at a time; aim for clean 10–500 BB coverage by re-solving per depth, not interpolating)
- *Phase 2b (Rust):* port to Rust; differential tests on small preflop subtrees
- Integration with Phase 1: preflop solution feeds postflop solves with correct starting ranges
- Test gates: HU push/fold matches known Nash solutions at short stacks (~10 BB and below); SB open-raise frequencies match published Pio outputs at 100 BB

**Phase 3 — Validation & sanity battery (continuous, formalized at end of Phase 2)**
- Kuhn / Leduc exact-equilibrium tests (mathematically known answers)
- Poker-intuition gauntlet: minimum defense frequency on simple bets, fold equity on all-ins, polar/merged ranges on right boards
- Cross-check against postflop-solver outputs on a fixed test bench
- Continuous: track exploitability over training iterations as the primary correctness metric

**Phase 4 — UI polish + library mode + packaging (2–3 months)**

UI exists from Phase 1a; this phase makes it *nice*.

- **Aesthetic polish pass:** typography, color, spacing, animations on solver progress, dark mode
- **Library mode:** save/load solves, queue overnight batch solves, tag + search, export
- **Exploitability and convergence plots** — iteration-over-iteration line charts, per-action regret heatmaps
- **Spot import/export:** standard formats (string-based hand histories, Pio JSON-ish if practical)
- **macOS packaging:** code-sign + notarize + .dmg (or Tauri's bundle path if Tauri-based)

**Phase 5 — 3-handed postflop (stretch, only if 1–4 are solid; 3–6 months)**
- Heavy abstraction; explicit "approximate equilibrium, not Nash" framing throughout UI
- Honest about the multiway CFR convergence problem in docs and tooltips
- Will not match GTOW multiway coverage; that requires cloud

**Out of scope (cannot deliver on MacBook):**
- 4–9 player full game
- GTOW-class large precomputed library
- Continuous bet sizing (theoretical only; everyone discretizes)
- Real-time depth-limited search (Pluribus-style) — possible later, but a research project on top of v1

### Critical files / artifacts to produce

- `references/{papers,code,blog}/` — all references downloaded locally (R0); includes clones of Noam Brown's `poker_solver`, `b-inary/postflop-solver`, `24parida/shark-2.0`, `ericgjackson/slumbot2019`, `google-deepmind/open_spiel`

- **Python reference** `poker_solver/` (existing files preserved + new):
  - `card.py`, `equity.py`, `range.py`, `evaluator.py` — **kept as oracle**
  - `cli.py` — **extended** with `solve` subcommand
  - `tree.py` (new) — game tree builder, action abstraction
  - `abstraction/buckets.py` (new) — EMD-based card bucketing
  - `dcfr.py` (new) — slow but correct Python DCFR; solves Kuhn/Leduc/river-only
  - `solver.py` (new) — orchestration: build tree → call CFR (Python OR Rust) → return strategies + EVs

- **Rust production** `crates/cfr_core/`:
  - `src/dcfr.rs` — DCFR core (regret update, average strategy, iteration loop, NEON-vectorized)
  - `src/tree.rs` — compact tree representation (flat arrays, indexed traversal)
  - `src/eval.rs` — hand evaluator (Rust port of `poker_solver/evaluator.py`)
  - `src/lib.rs` — PyO3 bindings: `solve()`, exposed as `poker_solver.engine.solve()`

- `tests/`:
  - `test_kuhn.py` — Kuhn equilibrium, Python AND Rust
  - `test_leduc.py` — Leduc equilibrium, Python AND Rust
  - `test_diff_python_rust.py` — **differential test harness:** run both implementations on the same small inputs, assert strategy/EV agreement within float tolerance
  - `test_noambrown_parity.py` — match Noam Brown's `poker_solver` on a fixed set of river spots
  - `test_postflop_solver_parity.py` — match `b-inary/postflop-solver` on a fixed set of flop spots
  - `test_intuition_gauntlet.py` — MDF, fold equity, polarization sanity checks on constructed spots

### Existing code to reuse (heavy reuse — hybrid keeps most Python intact)

- `poker_solver/evaluator.py` — port to Rust (~200 lines) for in-loop speed; **keep Python copy** as cross-language oracle
- `poker_solver/equity.py` — **keep as-is**; used to spot-check CFR leaf EVs and as a sanity oracle
- `poker_solver/range.py` — **keep as-is**; Python tree builder consumes ranges directly
- `poker_solver/card.py` — **keep as-is**; Python-side card parsing
- `poker_solver/cli.py` — **extend** with `solve` subcommand
- `tests/` (Python) — **keep + extend** with new CFR/parity tests
- All bindings are additive — the equity calculator continues to work as a standalone tool

### Verification plan (end-to-end)

1. **Tiny test (5 min)**: Solve a single river spot with 3 actions, verify CFR converges and EV outputs match hand-computed Nash for a constructed toy game.
2. **Kuhn poker** (exact): build the 1-card Kuhn tree, run DCFR, verify it converges to the known closed-form equilibrium.
3. **Leduc poker** (exact for HU): same exercise; verify against published equilibrium tables.
4. **Parity test**: pick 10 fixed flop spots (varied textures), solve in our engine and in postflop-solver, diff strategies and EVs. Pass if KL divergence < threshold per infoset.
5. **Poker-intuition gauntlet**: MDF on overpair vs simple bet, fold-equity on all-in shoves, polarization on monotone-board overpair vs nut-flush draw — all sanity-checked against published guides and hand-replayed against known Pio outputs.
6. **Perf gate**: standard flop spot, 3 sizes, MacBook convergence < 30 min.

A failure at any level halts the phase and triggers root-cause analysis. No "good enough" passes.

### Between-PR check battery (automated; runs before each PR is handed to the user for review)

After every PR's implementation work but before opening for user review, run `scripts/check_pr.sh` which executes (gate = must pass):

1. **Test suite** — `pytest -x` (Python) + `cargo test --all` (Rust). Full suite.
2. **Rust lint** — `cargo clippy --all-targets -- -D warnings`. Zero warnings tolerated.
3. **Python lint** — `ruff check poker_solver tests` and `ruff format --check`.
4. **Python types** — `mypy poker_solver` (strict on new code; gradual on existing).
5. **Differential tests** — `pytest tests/test_dcfr_diff.py` if both Python and Rust tiers were touched.
6. **License + dep audit** — verify no new AGPL/GPL dependencies were added (TexasSolver is read-only inspiration, never copied); list any new `pyproject.toml` or `Cargo.toml` deps for user review.
7. **Perf check** — when relevant, run a small benchmark and compare to the prior PR's baseline; flag regressions >10%.
8. **References integrity** — `references/README.md` still exists; `references/code/`, `references/papers/`, etc. directories still present; no orphan files.
9. **Generate `pr_report.md`** — summarizing: files changed, tests added/modified, lint status, perf delta, any deps added, any TODOs or `unimplemented!()` left, suggested user attention points.

User reviews `pr_report.md` + the diff. **No commit / push happens before user OK.** This script lands in PR 1 (added to `scripts/check_pr.sh`) and runs in every subsequent PR.

### Subagent task tracks (organized for execution, post-plan-mode)

| Track | Owner | Tool fit |
|---|---|---|
| R0: download references locally | Claude Code | Strong fit — WebFetch + git clone |
| R1/R2/R3: deeper research (Phase 1 reports already in this conversation) | Claude Code | Done; refine as needed |
| E1: Rust engine implementation | Claude Code | Strong fit — large code-writing task |
| E2: Card abstraction pipeline | Claude Code | Strong fit |
| E3: Validation gauntlet | Claude Code (codes tests) + User (poker intuition checks) | **Co-work** — Claude writes tests, user validates poker correctness on real spots |
| U1: GUI (Phase 4) | Claude Code (Tauri scaffolding) + User (visual taste / spot selection) | **Co-work** |
| D1: macOS packaging | Claude Code | Strong fit |
| Spot library curation | **User** (which spots to study) + Claude Code (run solves) | **Co-work** |

**What Claude Code does well**: writing the engine, tests, packaging, CLI, bindings; running solves; comparing outputs.
**Where the user is essential**: deciding what spots matter for personal study, judging when a multiway approximation is "good enough" to ship, UI taste, poker-intuition correctness checks where domain expertise beats automated tests.

### Timeline summary (two-tier Python+Rust + parallel UI track)

- Phase 0: 2–3 weeks (refs + Noam UI inspection + UI tech decision + tooling + Rust orientation)
- Phase 1a (Python postflop reference + UI scaffold): **3–5 months** (engine + UI in parallel; UI adds ~1 month vs engine-only)
- Phase 1b (Rust postflop port + UI integration): 2–3 months
- Phase 2 (preflop, both tiers + preflop UI views): 4–6 months
- Phase 3 (validation gauntlet): 1 month
- Phase 4 (UI polish + library mode + packaging): 2–3 months
- **Total to a usable, validated, polished product**: ~13–18 months focused work
- Phase 5 (3-handed stretch, both tiers + multiway UI): +5–9 months

UI-in-parallel costs ~1–2 months vs UI-deferred, but the user actually uses the tool while building it, which catches UX bugs early and provides ongoing motivation. Worth it given the redirected priorities. **Engine correctness remains the priority** — UI work pauses for engine bugs, not vice versa.

### How agents fit this project

- I (Claude Code) will run **built-in agents** (`Explore`, `general-purpose`, `Plan`) as the work demands — no setup needed from the user. Multiple agents can run in parallel; with `run_in_background: true` they finish asynchronously and the user can chat with me about other things while they work.
- **Custom agents to set up post-plan-mode** (I'll write the configs; user can edit in `/agents`):
  - `cfr-validator` — runs the differential-test gauntlet (Python vs Rust, Noam-Brown parity, postflop-solver parity) on demand and reports diffs
  - `rust-cfr-implementer` — Rust-focused subagent for porting Python reference code to Rust with diff-tests as the success criterion
  - `poker-intuition-checker` — runs the MDF/fold-equity/polarization sanity tests on a constructed spot and explains failures in poker terms
- These are post-plan-mode work; for now the built-in agents are sufficient.

### Pacing protocol

- **Within a PR:** I run autonomously and **parallelize aggressively**. Custom agents work on independent tracks concurrently (e.g. `cfr-engine-implementer` writes Python tier while a second instance writes Rust tier while a third writes tests; they run in parallel and I aggregate). At the end, `pr-check-runner` runs the check battery and produces `pr_report.md`. **No user input required mid-PR.**
- **Between PRs:** **Checkpoint by default.** I do NOT auto-roll into the next PR. I hand `pr_report.md` + diff to the user, wait for "next" or "wait — let me adjust."
- **GitHub pushes:** **Explicit OK each time.** No background pushes; the public repo's blast radius warrants per-push confirmation.
- **Poker-intuition validation:** User's expert eyes needed when HUNL outputs are produced (PR 5+). Not needed for Kuhn/Leduc (closed-form Nash is the check, run automatically by `poker-validator`).
- **Speedup discipline:** "As quickly as possible" applies *within* a PR via parallel agents — never by skipping the check battery, skipping diff tests, or rolling past a checkpoint without user OK. Velocity comes from parallelism on independent work, not from cutting validation.

---

## First PR scope — concrete executable next step (Ultraplan refinement)

*(Output of the remote Ultraplan session. The strategic roadmap above is the long-horizon plan; this section is the immediate executable chunk that lands the foundation everything else builds on. All locked decisions above are respected.)*

### Context

The repo currently contains a pure-Python Monte Carlo equity calculator (`poker_solver/`: `card.py`, `evaluator.py`, `equity.py`, `range.py`, `cli.py`). This PR establishes the two-tier Python+Rust foundation with differential testing.

**What this PR does:**

1. Migrate the build to `maturin` so a single `pip install -e .` produces a wheel containing both the existing Python equity code and a new Rust extension module.
2. Add `crates/cfr_core/` — a tiny Rust crate built via PyO3, exposing the first solver primitive to Python under `poker_solver._rust`.
3. Implement Kuhn poker + tabular DCFR (Brown & Sandholm defaults α=1.5, β=0, γ=2.0) in both tiers — Python (`poker_solver/games.py`, `dcfr.py`, `solver.py`) and Rust (`crates/cfr_core/src/{kuhn,dcfr,solver}.rs`).
4. Add a differential test asserting the two implementations agree on Kuhn within float tolerance.
5. Add `scripts/setup_references.sh` that clones `noambrown/poker_solver` into `references/code/` (gitignored) as the future river-spot differential-test target.
6. Update CLI with a `solve --game kuhn [--backend python|rust]` subcommand exercising both tiers.

**What this PR explicitly defers:**

- Leduc poker, HUNL tree builder, card abstraction, action abstraction — each is its own PR.
- UI (NiceGUI scaffold), packaging, signed macOS distribution.
- Public chance sampling, vectorized CFR, NEON SIMD — Kuhn has 12 infosets; premature.
- Actually *using* `noambrown/poker_solver` for differential testing — Kuhn has closed-form Nash; the Brown reference matters when we reach river spots. Cloning it now is preparatory.

**Why this scope is right-sized:** Kuhn DCFR in both tiers is the smallest end-to-end exercise that proves (a) the maturin/PyO3 toolchain works, (b) the `Game` protocol is shaped correctly to be consumed by both Python and Rust solvers, (c) the differential-test harness actually catches bugs, (d) the existing equity calculator keeps working after the build migration. Each follow-up PR (Leduc, HUNL tree, card abstraction) plugs into the rails laid here.

### Implementation order (9 steps; each step verifiable on its own)

**Step 1 — Build migration (setuptools → maturin)**

Touch:
- `pyproject.toml` — switch `[build-system]` to `requires = ["maturin>=1.7,<2.0"]`, `build-backend = "maturin"`. Replace `[tool.setuptools.packages.find]` with `[tool.maturin]`:
  ```toml
  [tool.maturin]
  python-source = "."
  module-name = "poker_solver._rust"
  manifest-path = "crates/cfr_core/Cargo.toml"
  features = ["pyo3/extension-module"]
  ```
  Keep `[project]`, `[project.scripts]`, `[project.optional-dependencies]`, `[tool.pytest.ini_options]` unchanged. Add `numpy>=1.24` to `[project.dependencies]`. Bump version `0.1.0 → 0.2.0`.
- `Cargo.toml` (NEW at repo root) — workspace declaration:
  ```toml
  [workspace]
  members = ["crates/cfr_core"]
  resolver = "2"
  ```
- `.gitignore` — append `references/code/`, `target/`. Commit `Cargo.lock` (single-binary project).

**Verification:** `pip install -e .` succeeds; existing tests still pass.

**Step 2 — Rust crate skeleton + PyO3 hello**

Create `crates/cfr_core/Cargo.toml`:
```toml
[package]
name = "cfr_core"
version = "0.2.0"
edition = "2021"

[lib]
name = "_rust"
crate-type = ["cdylib"]

[dependencies]
pyo3 = { version = "0.23", features = ["extension-module"] }
```

Create `crates/cfr_core/src/lib.rs` with a `#[pymodule] fn _rust(m: &Bound<'_, PyModule>)` that registers a placeholder `_version() -> &'static str` returning `"0.2.0"`. Proves the toolchain end-to-end.

**Verification:** `pip install -e .` builds the Rust extension; `python -c "from poker_solver._rust import _version; print(_version())"` prints `0.2.0`; existing tests still pass.

**Step 3 — Python tier: Kuhn poker + DCFR**

Add `poker_solver/games.py` (~150 lines):
- `Action = int`
- `@runtime_checkable class Game(Protocol)` with: `num_players: int`, `initial_state()`, `is_terminal(state)`, `utility(state) -> tuple[float, ...]`, `current_player(state) -> int` (-1 for chance), `chance_outcomes(state) -> list[tuple[Action, float]]`, `legal_actions(state) -> list[Action]`, `apply(state, action) -> Any`, `infoset_key(state, player) -> str`.
- `@dataclass(frozen=True) class KuhnState`: `cards: tuple[int, ...]`, `history: tuple[int, ...]`.
- `class KuhnPoker(Game)`:
  - `num_players = 2`; deck `[11, 12, 13]`; ante 1 each (pot starts at 2).
  - Actions: `PASS = 0`, `BET = 1`.
  - Chance deals card to P1 then to P2.
  - Terminal cases: `pp`, `pb`, `pbp`, `pbb`, `bb`.
  - `utility`: zero-sum returns `(p1_payoff, p2_payoff)` in antes.
  - `infoset_key`: `f"{card}|{history_string}"`.
- Helper `kuhn_nash_value() -> float` returning `-1.0 / 18.0`.

Add `poker_solver/dcfr.py` (~200 lines, numpy-based):
- `@dataclass class InfosetData`: `regret_sum`, `strategy_sum`, `num_actions`.
- `class DCFRSolver(game, *, alpha=1.5, beta=0.0, gamma=2.0, seed=None)`:
  - `_get_strategy(info)`: regret matching — `max(regret, 0)` normalized, uniform if zero.
  - `_cfr(state, reach, iteration)`: chance nodes weight children by probability; player nodes accumulate regret using opponent reach; DCFR discounts regret_sum and strategy_sum per the paper.
  - `solve(iterations) -> dict[str, list[float]]`: returns average strategies.
  - Pure NumPy; no torch/jax.

Add `poker_solver/solver.py` (~120 lines):
- `@dataclass class SolveResult`: `average_strategy`, `exploitability_history`, `game_value`, `iterations`, `backend`.
- `def solve(game, iterations, *, backend="python", log_every=None, **dcfr_kwargs) -> SolveResult`.
- `def exploitability(game, strategy) -> float`: best-response per player.

Modify `poker_solver/__init__.py`: re-export new symbols.

**Verification:** `python -c "from poker_solver import solve, KuhnPoker; r = solve(KuhnPoker(), 5000); print(r.game_value)"` prints near `-1/18 ≈ -0.0556`. Existing tests pass.

**Step 4 — Python tier tests**

`tests/test_dcfr_core.py`:
- `test_regret_matching_uniform_when_no_regret`
- `test_regret_matching_concentrates_on_positive_regret`
- `test_dcfr_discount_applied_to_regret_sum` (α=1.5 factor)
- `test_dcfr_discount_applied_to_strategy_sum` (γ=2.0 factor)

`tests/test_kuhn_dcfr.py`:
- `test_kuhn_converges_to_nash_value` — 50,000 iterations, value within `5e-3` of `-1/18`.
- `test_kuhn_exploitability_below_threshold` — < `5e-3` after 50k.
- `test_kuhn_p1_king_always_bets` — `"13|"` puts >0.99 on BET.
- `test_kuhn_p1_queen_never_initial_bets` — `"12|"` puts <0.05 on BET.
- `test_kuhn_bluff_calling_relationship` — P1 J-bluff freq α at `"11|"` and P2 Q-call freq at `"12|b"` satisfy `p2_call_Q ≈ α + 1/3` ± 0.05.
- `test_kuhn_exploitability_monotone_decreasing` — sampled at 1k/5k/10k/50k, non-increasing trend.

Match existing pytest style (function-level, `pytest.approx`).

**Verification:** `pytest tests/test_dcfr_core.py tests/test_kuhn_dcfr.py` passes in <60 s.

**Step 5 — Rust tier: Kuhn + DCFR + PyO3 surface**

`crates/cfr_core/src/kuhn.rs` (~120 lines):
- Constants `PASS: u8 = 0`, `BET: u8 = 1`.
- `KuhnState { cards: [i8; 2], history: Vec<u8>, chance_phase: u8 }`.
- Methods: `initial`, `is_terminal`, `utility -> [f64; 2]`, `current_player -> i8`, `legal_actions`, `apply`, `chance_outcomes -> Vec<(u8, f64)>`, `infoset_key -> String`.

`crates/cfr_core/src/dcfr.rs` (~180 lines):
- `InfosetData { regret_sum: Vec<f64>, strategy_sum: Vec<f64>, num_actions: usize }`.
- `DCFRSolver { alpha, beta, gamma, infosets: HashMap<String, InfosetData> }`.
- `cfr(state, reach: [f64; 2], iteration: u32) -> [f64; 2]` — structurally matches Python so the diff test holds.
- Use `f64` (matches NumPy default) — perf isn't the point at 12 infosets; numerical agreement is.

`crates/cfr_core/src/solver.rs` (~100 lines):
- `solve_kuhn(iterations, alpha, beta, gamma) -> SolveOutput`.
- Exploitability via best-response traversal (~36 paths).

`crates/cfr_core/src/lib.rs`:
- Replace `_version` stub with real surface.
- `#[pyfunction] fn solve_kuhn(...)` returns a Python dict with `average_strategy`, `exploitability`, `game_value`, `iterations`.
- Keep `_version()` for smoke checks.

Modify `poker_solver/solver.py`: in `backend == "rust"` branch, call `poker_solver._rust.solve_kuhn(...)` and wrap result. Raise `NotImplementedError` for non-Kuhn games.

**Verification:** `python -c "from poker_solver import solve, KuhnPoker; r = solve(KuhnPoker(), 5000, backend='rust'); print(r.game_value, r.exploitability_history[-1])"` runs and prints near `-1/18` with small exploitability.

**Step 6 — Differential test**

`tests/test_dcfr_diff.py`:
- `test_kuhn_python_rust_strategy_agreement` — 10,000 iterations, identical hyperparameters; per-action probabilities agree within `1e-4`.
- `test_kuhn_python_rust_game_value_agreement` — within `1e-5`.
- `test_kuhn_python_rust_exploitability_agreement` — within `1e-4`.
- `test_kuhn_python_rust_infoset_keys_match` — same set of keys.

Helper `_diff_dicts(a, b, atol)` returns structured diff on failure.

**Verification:** `pytest tests/test_dcfr_diff.py` passes.

**Step 7 — CLI**

Modify `poker_solver/cli.py`:
- Add `solve` subparser: `--game kuhn` (required, only option), `--iterations` (default 50000), `--backend {python,rust}` (default `python`), `--seed` (accepted for forward-compat).
- `_cmd_solve(args)`: instantiate `KuhnPoker()`, call `solve(...)`, print iterations / backend / game_value / exploitability / sorted strategy table.
- Leave existing `equity` subcommand unchanged.

**Verification:**
- `poker-solver equity AhKh QdQc` still works.
- `poker-solver solve --game kuhn --iterations 50000` prints Kuhn strategy; exploitability < 0.005.
- `poker-solver solve --game kuhn --iterations 50000 --backend rust` near-identical output.

**Step 8 — References scaffold**

Add `scripts/setup_references.sh` (executable, POSIX, idempotent):
```sh
#!/usr/bin/env sh
set -e
mkdir -p references/code references/papers references/blog
cd references/code
if [ ! -d noambrown_poker_solver ]; then
  git clone --depth 1 https://github.com/noambrown/poker_solver.git noambrown_poker_solver
fi
```

Add `references/README.md` (~30 lines): documents directory purpose; notes the cloned Brown repo is a *future* river-spot diff target.

**Verification:** `sh scripts/setup_references.sh` clones; rerun is no-op. Not a CI requirement.

**Step 9 — README update**

Modify `README.md`:
- Add "Solver (preview)" section with Kuhn example and dual-implementation note.
- Add "Build" section noting Rust toolchain required (link to https://rustup.rs).
- Add "References" section pointing at `scripts/setup_references.sh`.
- Keep existing equity sections intact.

### Critical files / line references

- `poker_solver/cli.py:56-90` — `sub.add_parser` + `set_defaults(func=...)` pattern; new `solve` subcommand follows.
- `poker_solver/equity.py:16-38` — `@dataclass EquityResult` shape; `SolveResult` follows same conventions.
- `poker_solver/card.py:18-37` — `@dataclass(frozen=True)` style; `KuhnState` matches.
- `tests/test_evaluator.py:5-7` — `cards(*s)` helper pattern; new tests follow house style.
- `poker_solver/__init__.py:3-22` — re-export pattern; extend in place.

### Existing code reused (heavy reuse)

- `card.py`, `evaluator.py`, `equity.py`, `range.py` — untouched; equity calculator continues to work standalone. Future Leduc/HUNL Games will call `evaluate()` to score terminals.
- `cli.py` skeleton — extended additively.
- `pyproject.toml` `[project.scripts]` entry — unchanged.

### Verification plan (end-to-end gating sequence)

1. `cargo --version && rustc --version` — Rust toolchain present.
2. `pip install -e .[dev]` — installs maturin, numpy, pytest; builds Rust extension; succeeds.
3. `python -c "import poker_solver._rust; print(poker_solver._rust._version())"` — Rust module imports.
4. `pytest` — full suite passes: 4 existing test files + 3 new (`test_dcfr_core`, `test_kuhn_dcfr`, `test_dcfr_diff`). ≤90 s total.
5. `poker-solver equity AhKh QdQc` — regression check.
6. `poker-solver solve --game kuhn --iterations 50000` — Python backend.
7. `poker-solver solve --game kuhn --iterations 50000 --backend rust` — Rust backend; visually identical.
8. `sh scripts/setup_references.sh` — clones Brown reference.

Each step gates the next. Failure halts and triggers root-cause analysis.

### Follow-up PRs (not in this scope; here so rails are visible)

1. **Leduc poker** — exercises chance after preflop; locks `Game` protocol. Both tiers.
2. **HUNL tree builder (Python)** — action abstraction (33/75/150/AI), 3-raise cap.
3. **Card abstraction (EMD bucketing)** — flop/turn/river buckets.
4. **HUNL postflop solve (Python)** — uses `equity.py` as leaf oracle.
5. **HUNL postflop port to Rust** — perf tier; diff-test on small subtrees. **License-aware:** port from `noambrown_poker_solver` (MIT) and `open_spiel` (Apache 2.0) only; postflop-solver/TexasSolver are AGPL → read-only inspiration; shark-2.0 is unlicensed → read-only inspiration.
6. **River-spot diff test against `noambrown/poker_solver`** — actual use of the cloned reference.
7. **NEON SIMD + cache-blocked perf work in Rust.**
8. **HUNL preflop** — both tiers.
9. **NiceGUI scaffold** — parallel-track UI per strategic roadmap.
10. **Library mode + macOS packaging** — Phase 4.

---

### Honest take on the final product (after Phase 1–4)

- ✅ A Python+Rust NLHE solver with a polished UI that solves HU postflop and preflop on a MacBook
- ✅ A **tool the user actually uses**, not a research artifact — UI built in from Phase 1, polished in Phase 4
- ✅ Beats every open-source competitor on scope (only one with preflop)
- ✅ Competitive with PioSolver on HU local solving
- ✅ Personal library of ~hundreds of curated solved spots
- ❌ Not competitive with GTO Wizard on multiway preflop coverage (their cloud library is unreachable without cloud spend)
- ❌ Not a multiway product. 3-handed stretch in Phase 5 will be explicitly approximate.
- ❌ Not "complete" in the user's original sense (2–9 player, 1–500 BB, full coverage). The honest answer remains: that doesn't exist on consumer hardware.
