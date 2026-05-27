# OSS Poker Solver Landscape — Competitor Comparison

**Date:** 2026-05-23
**Our state:** v1.7.0 (engine + GUI; .dmg rebuild pending on `pr-44-dmg-packaging-fix`)
**Purpose:** Light scan of the OSS solver landscape to inform v1.8 / v2 framing.

All facts cite local `references/` files. No external fetching; no code copied.

---

## 1. Comparison table

| Project | License | Lang(s) | Game scope | Algorithm | Card abstraction | Bet sizing | UI | Last commit | Distribution |
|---|---|---|---|---|---|---|---|---|---|
| **noambrown_poker_solver** | MIT | Python + C++17 | HUNL river-only subgame | CFR / CFR+ / LCFR / DCFR(1.5,0,2) / ES-MCCFR | None (full vectors) | Pot-fraction discrete + optional all-in | CLI | 2026-01-05 | Source build |
| **postflop-solver** (b-inary) | AGPL-3.0+ | Pure Rust | HUNL flop/turn/river postflop | DCFR only (custom γ=3, power-of-4 strat reset) | None (full vectors); suit isomorphism | Rich DSL (`%`, `x`, `c`, `e`, `a`) + thresholds | Library (backs WASM/Desktop Postflop GUIs) | 2023-10-01 (suspended) | Source / WASM |
| **TexasSolver** (bupticybee) | AGPL-3.0 + active commercial relicense | C++ + Qt | HUNL postflop | CFR/CFR+ family; Trainable trait | None | Discrete; Pio-aligned output | Qt GUI | (mature; see _NOTES) | Source / GUI build |
| **shark-2.0** (24parida) | **Unlicensed** (all-rights-reserved by default) | C++20 + FLTK | HUNL postflop | DCFR (α=t√t/(t√t+1), β=0.5, γ=(t/(t+1))²) | None; range-aware suit-isomorphism | Per-street defaults (flop 50/100; turn/river 33/66/100); raise cap 3 → all-in | FLTK GUI | 2026-04-12 (most recent) | Source |
| **slumbot2019** (E. Jackson) | MIT | C++17 + pthreads | Multi-street HUNL + multi-player (3+) MCCFR | CFR+ / ES-MCCFR / TCFR / subgame resolving (CFR-D safe + unsafe + combined) / RGBR | Explicit `Buckets` (null/kmeans/unique/rollout); also supports `None(st)` | Declarative `BettingAbstraction` params; supports **reentrant trees** | CLI only | 2023-09-18 | Source |
| **open_spiel** (DeepMind) | Apache 2.0 | C++17 + Python + (Julia/Rust shims) | Framework — Kuhn / Leduc / Universal Poker + many others | CFR / CFR+ / CFR-BR / ES-MCCFR / OS-MCCFR / OOS / FSICFR / DCFR (Python, "not verified") | None (literal tree) | N/A (game-agnostic) | Library | 2026-05-12 (most active) | pip / source |
| **PioSolver** (commercial) | Proprietary | C++ + Win GUI | HUNL postflop | CFR family | None | Granular (donk, custom raises) | Windows GUI + text-IO engine | n/a | One-time license |
| **GTO Wizard** (commercial cloud) | Proprietary | Cloud + NN | HUNL + multiway preflop up to 9p, ICM, MTT | CFR + NN value-net; **switched to QRE Apr 2025** (0.12% pot avg exploit) | (proprietary) | (proprietary) | Web + mobile | n/a | SaaS $50–359/mo |
| **MonkerSolver** (commercial) | Proprietary | C++ | Multiway NLHE postflop | CFR + heavy bucketing | Yes (per-bucket strategies) | Discrete | Win GUI | n/a | ~€330 perpetual |
| **OUR PROJECT — poker_solver v1.7.0** | **MIT** | **Python + Rust (PyO3)** | HUNL preflop + postflop (river-vector); push/fold charts 2–15 BB; Kuhn/Leduc closed-form solvers | DCFR (Brown defaults) + vector-form CFR; aggregator + Nash-API split | None (full vectors) | 14-action discrete abstraction; per-street menus; node locking | **PySide6 GUI (range-vs-range, 4-tier slider, node-lock editor, asym contributions)** + CLI subcommands (`pushfold`, `river`, `parity`) | 2026-05-23 (tag `3843ce7`) | Source (`pip install -e .`); arm64-only .dmg (experimental, no notarization) |

Sources: `references/README.md` §2 license audit; `references/code/*/_NOTES.md`; `references/products/_COMPETITORS.md`; `CHANGELOG.md`; `PLAN.md` v1.7.0 status.

---

## 2. Performance / accuracy reference points

Where stated in local refs:

- **noambrown** — no published benchmark; river-only by design.
- **postflop-solver** — γ=3 + power-of-4 strategy reset; documented as "non-obvious optimization meaningfully improves convergence" (`_NOTES.md` §5).
- **shark-2.0** — exploitability sampled every `iters/5`; early-stop at user `min_exploit`.
- **slumbot2019** — `notes/lessons`: "char quantizing river, short quantizing turn, short quantizing flop seems to work"; "turn resolving > river resolving for accuracy/cost"; "big wins the earlier the street you can resolve at."
- **open_spiel** — `Exploitability(game, policy)` and `NashConv(game, policy)` are the canonical oracles; we use these for Kuhn/Leduc diff tests (`references/README.md` §7).
- **PioSolver** — 0.22% accuracy target: 4,862 s on 16 cores / 128 GB (`blog/gtow_ai_benchmarks.md`).
- **GTO Wizard** — same accuracy target: 6 s on 2 cores / 8 GB; 0.12% pot avg flop exploit via QRE since Apr 2025; beat Slumbot 19.4 bb/100 over 150K hands.
- **Our project (v1.7.0)** — Aggregator path runs persona budgets; Nash path has flop multi-street perf ceiling explicitly scoped Type D (`docs/v1_7_0_nash_path_perf_profile.md`). Slider tiers measured at 200/500/1000/2000 iters per `v1_5_slider_tier_defaults_measured.md`.

---

## 3. Positioning summary

We occupy the **PioSolver-class local HU postflop solver niche**, with several differentiators relative to the OSS field. We are the **only** MIT-licensed two-tier (Python + Rust) HUNL solver shipping with a modern GUI, two range-vs-range entry points (per-combo aggregator + joint vector-form Nash), node locking, asymmetric facing-bet scenarios, and a Kuhn/Leduc diff-tested correctness chain (`open_spiel` oracle → Rust). Of the six OSS competitors, only `shark-2.0` (unlicensed → effectively unusable for derivatives) and `TexasSolver` (AGPL → copyleft-poison) ship a real GUI; both have heavier C++ stacks and no Python scripting surface. `postflop-solver` has the strongest pure-Rust pattern library but is AGPL and the author suspended OSS work in Oct 2023.

---

## 4. Gaps where we trail

| Gap | Who leads | Why it matters |
|---|---|---|
| **macOS notarization + universal binary** | TexasSolver, shark-2.0 (Linux AppImage); GTOW (web → no install) | Our `.dmg` is arm64-only, unsigned. Intel Mac is source-build only. Marcus persona blocker. |
| **Multiway postflop** | MonkerSolver (commercial); slumbot2019 (`mp_ecfr.cpp`, `mp_vcfr.cpp`, reentrant betting trees in MIT-licensed C++) | Real-world cash + 6max + MTT spots need it. Our scope is HU only. |
| **Multiway preflop (3–9p)** | GTO Wizard; slumbot2019 | Pluribus-class. Not in any free OSS solver we audited end-to-end. |
| **Deep CFR / NN value-net warm-start** | GTO Wizard; rebel (paper only); `papers/deep_cfr_brown_2018.pdf` | Speed: GTOW hits 0.22% in 6s vs Pio's 4,862s by combining CFR+NN. |
| **Compressed regret storage (int16/int8 with per-node scale)** | postflop-solver, shark-2.0, slumbot2019 (all three) | Cuts memory ~2–4x. Enables deeper trees on M-series RAM budget. |
| **PioSolver-format range parser interop** | postflop-solver (`src/range.rs`) | Range portability for the user; we have own format only. |
| **Bet-size DSL (`%`, `x`, `c`, `e`, `a`)** | postflop-solver, slumbot2019 (declarative param files) | Power-user expressiveness vs our fixed 14-action menu. |
| **Disk-backed checkpointing** | slumbot2019 (`Checkpoint(it)` / `ReadFromCheckpoint(it)`) | Enables solves larger than RAM; would help long Nash-path flop runs. |
| **GPU acceleration** | (None in OSS, but emerging in `papers/rebel_brown_2020.pdf`) | Future-proofing. |
| **Real-Game Best Response (RGBR) outside abstraction** | slumbot2019 (`rgbr.cpp`) | True exploitability metric; currently we measure in-abstraction. |

---

## 5. Where we lead

| Strength | Evidence |
|---|---|
| **MIT license + clean two-tier architecture** | Only competitor matching MIT is slumbot (CLI-only, no GUI, no Python). |
| **Aggregator vs. vector-form Nash API distinction** | `docs/aggregator_vs_true_nash_explainer.md` — no OSS competitor exposes both as first-class entry points. Users get "per-combo blueprint" or "joint Nash" with clear honesty about what each is. |
| **Modern GUI (PySide6)** with RvR mode, 4-tier exploitability slider, node-lock editor, asymmetric facing-bet UI | PR 24a + PR 24b shipped in v1.6.0; competitors with GUI are Qt/FLTK desktop (TexasSolver, shark-2.0) on AGPL/unlicensed. |
| **Differential testing chain** | `open_spiel` Kuhn/Leduc oracle → Rust DCFR diff tests; `noambrown_poker_solver` river-parity test via `tests/test_noambrown_river_parity.py` (subprocess-wrapped, no source copied). No other OSS solver ships this rigor. |
| **Persona test framework + 5-reversal post-mortem methodology** | `docs/comprehensive_review_*` + `docs/STATUS_*post_retest*`; not present in any competitor. |
| **Honest scope labeling** | "Type D" perf-ceiling categorization (`docs/v1_7_0_nash_path_perf_profile.md`) + "Draft/Standard/Tight/Library" slider with measured iter counts. Competitors ship single accuracy knobs without honesty about regimes. |
| **CLI subcommands (`pushfold`, `river`, `parity`)** | PR 39 in v1.7.0 — clean scriptability matching PioSolver's "chess-engine-like" interface ethos but Python-native. |
| **Push/fold charts 2–15 BB shipped DCFR-generated** | No OSS competitor bundles short-stack chart data. |

---

## 6. Recommendations for v1.8 / v2 framing

Prioritized to maximize "best-in-class OSS" positioning per the gap analysis above.

### Top priority — v1.8

**macOS notarization + Intel x86_64 / universal binary `.dmg`.** This is the only competitor-gap that's purely engineering (no algorithm research). Marcus-persona blocker. Once shipped, we ship to any Mac user with a double-click — a UX advance over `TexasSolver` (AppImage), `shark-2.0` (source-only), `postflop-solver` (library), and `slumbot2019` (CLI-only). Tightly scoped, deterministic; days not weeks.

### Next priority — v1.8 or v2.0

**Multiway postflop (3-handed first), porting slumbot2019's MIT-licensed `mp_ecfr.cpp` / `mp_vcfr.cpp` + reentrant-betting-tree pattern.** This is the single biggest scope gap relative to GTO Wizard and MonkerSolver. Slumbot is MIT — we can port verbatim with attribution. Combined with our Python+Rust+GUI stack, would let us claim "only free GUI-driven multiway postflop solver." The honest Pluribus framing applies (no Nash convergence guarantee for n>2) and we already have the language for that in `references/blog/gtow_quirks_multiway_nash.md`.

### Nice-to-have — v2.x

**Compressed int16 regret storage with per-node f32 scale + disk-backed checkpointing.** Halves RAM, enables larger trees, lets the Nash-path flop multi-street ceiling (currently Type D) recede. Three independent OSS implementations to study (postflop-solver, shark-2.0, slumbot — last is MIT). Plus PioSolver-format range parser for interop and a bet-size DSL akin to postflop-solver's. Lower priority because none of these unlock new user value the way notarization + multiway do, but each is an obvious "best-in-class polish" item once headline gaps are closed.

**Explicitly not recommended:** Deep CFR / NN value-net warm-starting. Multi-year training corpus required; we cannot match GTO Wizard's pipeline economics. Stay tabular + honest about scope.

---

## 7. Anti-recommendations (things we should NOT do)

- **Do not copy AGPL code.** `postflop-solver`, `TexasSolver`, `shark-2.0` (no LICENSE → all rights reserved) — read-only inspiration only. Re-derive against the underlying paper, not the source. Per `references/README.md` §2.
- **Do not chase GTO Wizard cloud features.** ICM/MTT library, web UX, training drills — those need SaaS infrastructure and a multi-year solved-hand corpus. Stay local-solver, scripting-first.
- **Do not pursue Real-Time Bayesian opponent modeling (Pluribus self-consistent belief reasoning).** No reference implementation in our `code/`; described in Science paper at high level only (per `references/README.md` §11 known-gaps).

---

## 8. References cited

- `references/README.md` — topic index (load-bearing for license + algorithm claims).
- `references/code/noambrown_poker_solver/_NOTES.md` — MIT river-only ref; ports verbatim.
- `references/code/postflop-solver/_NOTES.md` — AGPL Rust HUNL postflop; pattern-only.
- `references/code/TexasSolver/_NOTES.md` — AGPL Qt GUI Pio-aligned.
- `references/code/shark-2.0/_NOTES.md` — Unlicensed C++20 + FLTK; pattern-only.
- `references/code/slumbot2019/_NOTES.md` — MIT C++17 framework; the algorithmically deepest of six.
- `references/code/open_spiel/_NOTES.md` — Apache 2.0; Kuhn/Leduc correctness oracle.
- `references/products/_COMPETITORS.md` — commercial landscape.
- `references/blog/gtow_ai_benchmarks.md` — Pio vs GTOW vs Slumbot numbers.
- `references/blog/gtow_quirks_multiway_nash.md` — multiway Nash honesty framing.
- `CHANGELOG.md` + `PLAN.md` — v1.0–v1.7.0 progression.
- `docs/aggregator_vs_true_nash_explainer.md` — our differentiated framing.
- `docs/v1_7_0_nash_path_perf_profile.md` — Type D scope honesty.
