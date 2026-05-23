# Plan: GTO Solver for No-Limit Hold'em

**Status:** PR 1-7 + 3.5 + 3.5-followup + 4.5 + 10a + 11 landed; main + integration both at `62c75d5`; v1.0.0 GA tagged at `bbb4395`.

**Branch state (2026-05-22):** integration→main merge completed today — 30 commits fast-forwarded; `main` advanced from `2b67370` to `62c75d5`. v1.0.0 GA tag (`bbb4395`) is reachable from main via FF. `origin/equity-precision` deleted (confirmed gone; matches desired state).

**Current session: autonomous overnight mode (started 2026-05-21).** User asleep. Working through PR 5 verification → commit; PR 6+ launches when PR 5 lands. **No GitHub pushes without explicit OK.** Local commits to feature branches; `integration` accumulates merged PR branches. Per-decision audit trail in `docs/autonomous_log.md`.

---

## 1. What we're building (current scope)

### Locked decisions (live)

- **Goal:** Beat every open-source NLHE solver on scope; match **PioSolver** on HU local solving. **Not** chasing GTO Wizard parity (cloud-only multiway library is unreachable without cloud spend).
- **v1 scope:** **HUNL postflop + preflop together.** Closes the public OSS preflop gap. ~6–9 months focused work.
- **Compute:** **MacBook-only.** 16 GB Apple Silicon. No cloud spend.
- **Project license: MIT (locked).** AGPL contamination is a one-way door we explicitly avoid.
- **Architecture: two-tier** — Python reference (`poker_solver/`) is ground truth; Rust production (`crates/cfr_core/`) is the perf tier. **Differential testing** between them gates every Rust change. Pattern validated by Noam Brown's own `noambrown/poker_solver` (has both `cpp/` and `python/`).
- **Algorithm: tabular DCFR** (Discounted CFR, Brown & Sandholm 2019). Hyperparameters: **α=1.5, β=0, γ=2.0** (paper defaults).
  - Regret update: `R_T(I,a) = (R_{T-1}(I,a) · t^α / (t^α + 1)) + r_t(I,a)` for positive regret; β factor applies to negative regret (β=0 ⇒ negative regret reset).
  - Average strategy update: `S_T(I,a) = (S_{T-1}(I,a) · ((t-1)/t)^γ) + π^σ_T(I) · σ_T(I,a)`.
- **No Deep CFR for v1.** Train-once-amortize is real but premature; we'd be optimizing a memory problem we don't have. Trigger to revisit: HUNL preflop OOMs on MacBook.
- **No GPU.** PyTorch MPS underperforms CPU on sparse CFR; jax-metal discontinued Dec 2025. Right path: ARM NEON 128-bit SIMD + cache-blocked infoset layout. M-series 120 GB/s memory bandwidth is the real ceiling.
- **Public chance sampling:** add after baseline DCFR converges (PR 8 perf work).
- **Action menu: 33% / 75% / 100% / 150% / 200% pot + all-in** (6 sizes per node, per-node configurable).
  - **Raise caps: preflop 4 (allows 4-bet/5-bet ladder), postflop 3.** After cap, next aggressive action forces all-in.
- **Card abstraction: imperfect-recall EMD bucketing, all three streets. Targets: 256 flop / 128 turn / 64 river.** Pure bucketing — NOT hybrid with lossless river (rejected after agent caught extrapolation error: replacing 64 buckets with 1326 hands on river *increases* memory, doesn't decrease).
  - **Empirical commitment:** PR 5 ships a per-street memory profiler. Once measured, PR 4's abstraction can be revisited based on actual GB per layer.
- **Stack-depth range: 2–250 BB** with mode-switched solver:

  | Stack range | Solver mode | Card abstraction (flop/turn/river) | Notes |
  |---|---|---|---|
  | **2–15 BB** | Precomputed push/fold charts (no tree solve) | n/a — static lookup | Sklansky-Chubukov / Nash HU SNG charts; O(1) lookup |
  | 15–100 BB | Tree-builder solver | 256 / 128 / 64 (default) | 3–14 GB |
  | 100–150 BB | Tree-builder solver | 256 / 128 / 64 (default; thin margin) | 10–18 GB |
  | 150–200 BB | Tree-builder solver | **128 / 64 / 32** (one tier tighter) | ~8–12 GB |
  | 200–250 BB | Tree-builder solver | **64 / 32 / 16** (two tiers tighter) | ~5–8 GB |

  Default 100 BB tree-builder memory: **~10–14 GB**. Tier boundaries are empirical — calibrated against PR 5's profiler.
- **Ante support:** included in tree builder from PR 3 onward (parameterized; default 0).
- **Performance targets (honest ranges):**

  | Solve type | Target wall-clock on M-series MacBook |
  |---|---|
  | Kuhn (12 infosets) | <1 sec |
  | Leduc (288 infosets) | <10 sec |
  | HUNL postflop, simple flop, 3 sizes | 1–3 min |
  | HUNL postflop, standard flop, 5 sizes | 5–15 min |
  | HUNL postflop, complex board + 6 sizes | 15–45 min |
  | HUNL preflop, full tree at one stack depth | 10–30 min |

  Anything >1 hour on a standard spot indicates an abstraction problem, not a wait problem.
- **UI tech: NiceGUI** (Python-native). PR 10 split into **10a (scaffold + mock solver)** and **10b (real-solver bindings)** — 10a runs in parallel with the Rust port. Priority: engine correctness > engine perf > UI polish. Tauri+web is a Phase-4 escape hatch if NiceGUI hits limits.
- **Solver UI control: exploitability target (primary) + iter count cap (safety).** Original PR 10a Q3 (iter count 1000 vs 2000) **reframed 2026-05-22**: the user-facing knob is a target exploitability (% pot), with iter count acting as a safety ceiling (max 2000). Slider tiers: **Draft (1% pot) · Standard (0.5% pot) · Tight (0.25% pot) · Library (0.1% pot).** Default numeric tier values are TBD until a measurement pass runs after PR 10b lands (need real-solver convergence curves to set sensible defaults). Reference: industry standard from `references/blog/gtow_how_solvers_work.md` + Brown's MIT reference solver default of 2000 iters.
- **Branching: per-PR feature branches from PR 3 onward** (`pr-N-<title>`). PR 1 and PR 2 went directly to `main` (acknowledged; not retroactively fixable).
- **Mandatory PR audit from PR 3 onward:** a fresh `general-purpose` agent with no implementation context reviews the diff and writes `audit_report.md`. User reads `audit_report.md` + `pr_report.md` before approving commit.

### Explicitly out of scope (v1)

- 4–9 player full game (Pluribus needed 64-core / 512 GB cluster; out of reach on consumer hardware)
- Continuous bet sizing (everyone discretizes; continuous is theoretical research only)
- GTOW-class large precomputed library (months of cluster time to populate)
- 1–500 BB seamless coverage (aspirational; 250 BB cap is the locked ceiling)

### Features beyond v1 (roadmap, not commitments)

- **Node locking** — freeze a node's strategy and re-solve against it for exploitative analysis
- **Real-time depth-limited search** (Pluribus-style) — refine current decision via depth-limited CFR with leaf-value oracle
- **Exploitative play** — best-response against fixed opponent (trivial extension of BR machinery)
- **Short-deck (6+) Hold'em** — parameterized evaluator + re-clustered abstraction; ~3–5 days work
- **Tournament / ICM-aware solving**
- **3-handed postflop** (heavy abstraction; explicitly approximate equilibrium — CFR has no convergence guarantee for ≥3 players)
- **Deep CFR** (PR 13 candidate if tabular HUNL preflop OOMs)

---

## 2. Trajectory (PR roadmap)

Progress legend: ✅ shipped (committed + pushed to GitHub) · 🚧 in flight (agents working) · 📋 spec'd + prompts ready · 📝 spec'd only (no impl prompts) · ❌ blocked (note what)

| PR | Scope | Progress | Status / Branch |
|---|---|---|---|
| Phase 0 | References download (papers + repos + blog) + Noam Brown clone | ✅ | done (pre-PR) |
| **PR 1** | Kuhn poker + DCFR (Python + Rust) + maturin/PyO3 foundation + diff test | ✅ | `9d2d66a` on main |
| **PR 2** | Leduc poker (both tiers) + Game trait abstraction | ✅ | `17c9756` on main |
| **PR 3** | HUNL tree builder (Python) + action abstraction (33/75/100/150/200/AI, caps PF 4 / PostF 3) | ✅ | `a96675c` on integration |
| **PR 3.5** | Push/fold chart mode (2–15 BB, JSON/CSV in `poker_solver/charts/pushfold/`) | ✅ | `9f91c83` on integration |
| **PR 3.5-followup** | API completeness + spec amendments from audit | ✅ | `1cbf52a` on integration |
| **PR 4** | Card abstraction (EMD bucketing, 256/128/64, suit-iso) | ✅ | `6565b84` → merged `5832b2f` |
| **PR 5** | HUNL postflop solve (Python reference) + per-street memory profiler | ✅ | `a9d02ca` → merged `eee9b4b` (**v0.4.0 milestone = PR 4 + PR 5**) |
| **PR 6** | HUNL postflop port to Rust (license-aware: MIT/Apache only) | ✅ | `0933367` → merged `6c438b8` (**v0.5.0 milestone**; ~24x speedup over Python tier) |
| **PR 7** | River-spot diff test vs `noambrown/poker_solver` | ✅ | `83d7b9c` → merged `d135add` (**v0.5.1 milestone**; external Nash validation vs Brown's MIT solver) |
| **PR 4.5** | Audit-debt sweep — mechanical fixes across PR 3 / 3.5 / 4 / 5 (no behavior changes) | ✅ | `d00e1aa` → merged `9f09d49` (**v0.5.2**; should-fix backlog drained) |
| PR 8 | NEON SIMD + cache-blocking + public chance sampling in Rust | 📋 | spec'd + prompts |
| PR 9 | HUNL preflop (both tiers) | 📋 | spec'd + prompts |
| **PR 10a** | NiceGUI scaffold + **mock solver layer** (range matrix, board input, controls, tree browser; no real engine) | ✅ | `8d514a2` + followup `040fc45` → merged `b880032` (**v0.6.0**; UI mock-first scaffold) |
| **PR 10a.5** | Audit-debt conformance pass (clear 5 fail + 7 xfail surfaced post-GA) | 🚧 | branch `pr-10a.5-conformance` from `62c75d5`; audit verdict **READY** (2026-05-23) with 3 should-fix items — pending commit |
| **PR 10b** | Replace mock with real solver bindings (Python tier; Rust tier when ready) | 📋 | spec'd + prompts; deps: PR 9 + PR 10a |
| **PR 11** | Library mode + macOS packaging (codesign + notarize + .dmg) | ✅ | `6af3684` → merged `bbb4395` (**v1.0.0 GA milestone**) + follow-up `639c776` (post-GA fix on `a7955c7` tip) |
| PR 12 | 3-handed postflop stretch (optional; explicitly approximate) | 📝 | spec only — no impl prompts; deferred |

Each PR ends with: `scripts/check_pr.sh` → `pr_report.md` → audit agent (PR 3+) → `audit_report.md` → user review → user OK → commit + push (with explicit OK per push).

### Dependency graph

```
PR 5 (postflop) ──→ PR 6 (Rust port) ──→ PR 7 / PR 8 (perf, parity)
       ↓                  ↓
   PR 10a (UI scaffold + mock) ←─── PR 5 types only
       ↓
   PR 9 (preflop) + PR 10a ──→ PR 10b (UI integration with real solver)
       ↓
   PR 11 (packaging) ←──── PR 10b
       ↓
   PR 12 (3-handed stretch, post-v1) ←──── PR 9 + PR 10b
```

### Post-GA sequencing decision (2026-05-22)

- **PR 10a.5 lands first** (clears 5 fail + 7 xfail conformance debt on `62c75d5` baseline).
- **PR 8 ∥ PR 9 planned in parallel** after PR 10a.5 ships. NEON SIMD perf work (PR 8) and HUNL preflop (PR 9) touch disjoint code surfaces; no fan-out conflict.
- **PR 10b waits for PR 9** (real-solver bindings need the preflop tier).
- **PR 8 preflop-perf gap — option 3 accepted:** PR 8's DCFR inner-loop optimization is expected to cover ~70–80% of preflop perf for free (the inner CFR loop is shared). PR 9 will add preflop-specific traversal code that PR 8 doesn't touch. **Do not preemptively block on it.** If measured-slow after both ship, add a small follow-up perf pass. Rejected alternatives: (1) extend PR 8 to include preflop traversal — bloats scope, delays SIMD ship; (2) gate PR 9 on a PR-8-preflop-perf addendum — couples two independent work tracks.

---

## 3. Architecture summary

**Two-tier with differential testing:**

```
poker_solver/        Python reference (ground truth)
├── card.py          existing — kept
├── evaluator.py     existing — kept (Rust oracle)
├── equity.py        existing — kept (CFR leaf oracle)
├── range.py         existing — kept
├── cli.py           extended (solve subcommand)
├── games.py         Game protocol + Kuhn + Leduc + HUNL
├── dcfr.py          slow correct Python DCFR (solves Kuhn/Leduc/river-only)
├── solver.py        orchestration (Python OR Rust backend)
├── tree.py          HUNL tree builder
├── abstraction/     EMD bucketing (shipped PR 4)
└── charts/          push/fold lookup tables (shipped PR 3.5)

crates/cfr_core/     Rust production (PyO3 + maturin)
├── src/dcfr.rs      DCFR core, NEON-vectorized (PR 8)
├── src/tree.rs      compact tree (flat arrays, indexed traversal)
├── src/eval.rs      hand evaluator port
├── src/kuhn.rs      } small-game implementations
├── src/leduc.rs     } for differential tests
└── src/lib.rs       PyO3 bindings exposed as poker_solver._rust

tests/               Differential + intuition + parity tests
references/          Papers, repos, blog posts (gitignored at code/)
ui/                  NiceGUI app (PR 10a + 10b)
scripts/             setup_references.sh, check_pr.sh
```

**What each tier owns:**

- **Python:** the spec. Every algorithm lives here first. Solves small games (Kuhn, Leduc, river-only). Easy to read and modify.
- **Rust:** the workhorse. Mechanical port of the Python spec, optimized for full HUNL. Trusted only after differential tests pass on small games.
- **Diff test:** every algorithm gate — Rust output must match Python within float tolerance on shared inputs.

---

## 4. Verification + check battery

**Validation chain (correctness):**
- Kuhn poker → closed-form Nash value `-1/18`
- Leduc poker → closed-form HU equilibrium
- River-only HUNL spots → diff vs `noambrown/poker_solver` (MIT; Brown is DCFR author)
- HUNL flop spots → parity vs `b-inary/postflop-solver` (AGPL; read-only inspiration — no copying)
- Poker-intuition gauntlet → MDF on overpair vs simple bet, fold-equity on all-in shoves, polarization on monotone boards
- `open_spiel` → Kuhn/Leduc correctness oracle

**`scripts/check_pr.sh` (runs before user review on every PR):**
1. `pytest -x` (Python) + `cargo test --all` (Rust) — full suite
2. `cargo clippy --all-targets -- -D warnings` — zero warnings
3. `ruff check` + `ruff format --check`
4. `mypy poker_solver` — strict on new code
5. Differential tests (`tests/test_dcfr_diff.py`) when both tiers touched
6. License + dep audit — no new AGPL/GPL deps
7. Perf check — flag regressions >10%
8. References integrity check
9. Generate `pr_report.md`

**Per-test wall-clock timeout: 90s default** (via `pytest-timeout`); `@pytest.mark.slow` tests can opt to `timeout(3600)` (1 hour); `@pytest.mark.very_slow` opts to `timeout(0)` for production-scale builds. Configured 2026-05-22.

**Mandatory PR audit (PR 3+):** fresh `general-purpose` agent with no implementation context reviews the diff + tests. Output: `audit_report.md` with must-fix / should-fix / nice-to-fix / looks-good sections. **Both `pr_report.md` and `audit_report.md` must look clean before commit.**

---

## 5. Parallelization + pacing protocol

**MANDATORY: steady-state 3–5 concurrent agents during autonomous sessions.** User has flagged single-threading drift THREE separate times. Falling back to one-agent-at-a-time is the failure mode this section exists to prevent.

### Hard rules (non-negotiable)

1. **If there are pending tasks AND I'm running 0–1 agents, I am wrong.** Launch more agents immediately. No exceptions.
2. **Before any single new agent launch**, run this checklist:
   - What's running right now? (Enumerate.)
   - What's blocked on what? (Identify hard vs soft dependencies.)
   - What's truly independent that I haven't launched? (Future PR specs, research deep-dives, doc work, validation harnesses, etc.)
   - Can I launch 3–5 at once instead of 1?
3. **Waiting periods (audit running, pytest running, etc.) are the IDEAL time to fan out** — the orchestrator is idle anyway. Use that time.
4. **A user-authorized autonomous session = blanket fan-out authorization.** The user explicitly chose efficiency-through-parallelism over per-task attention. Honor that choice every turn.

### Patterns

1. **Fan-out-on-spec:** before implementation, write a tight interface spec. Launch implementer + tests-from-spec + validator-from-spec concurrently.
2. **Pipeline overlap:** once Python game-state stabilizes (~30% in), start Rust port struct in parallel.
3. **Independent polish track:** while heavy implementation runs, fan off small agent for CLI + README + docs.
4. **Validation in parallel:** diff-test + intuition gauntlet + perf check all run concurrently after implementation lands.
5. **Cross-PR speculation:** while PR N is in flight, start PR N+1 research/scaffolding on its own branch.
6. **Speculative spec drafting:** during any wait, draft specs for downstream PRs in parallel — independent of in-flight implementation work.

### Scheduling discipline

- Agents are **one-shot**, not a pool. I am the scheduler. Be smart, not greedy.
- **Don't launch work that genuinely needs another agent's output to start** (e.g. audit agent before implementation finishes).
- **Aggregate per wave before launching next.** Read all outputs together; design next wave from synthesis. Don't react agent-by-agent.

### Pacing

- **Within a PR:** parallelize aggressively; no user input required mid-PR.
- **Between PRs:** checkpoint by default. I hand `pr_report.md` + `audit_report.md` + diff to user; wait for approval before merging to main.
- **PR-branch pushes:** **autonomous** (user-authorized 2026-05-21).
- **Autonomous overnight mode:** `integration` branch ("pseudo-main") autonomously accumulates merged PR branches; always reflects the latest working set. Tip: `a7955c7` (PR 11 v1.0.0 GA tagged at `bbb4395`; follow-up commit `639c776` on top).
- **`main` merges:** require explicit user OK.
- **Force pushes (any branch):** require explicit user OK.

---

## 6. Open items / audit findings to retro

Things surfaced during recent sessions that must not be forgotten. Each has an explicit action and the PR that owns it. Source: `docs/open_items_audit_2026-05-22.md` + `docs/plan_log_final_sweep.md`.

Trajectory note: `eee9b4b` (PR 4 + PR 5) was the **v0.4.0 milestone** — first user-visible postflop solver + profiler beyond push/fold. **`6c438b8` (PR 6) is the v0.5.0 milestone** — Rust port of HUNL postflop with ~24x speedup over Python tier. **`bbb4395` (PR 11) is the v1.0.0 GA milestone** — first end-user-shippable artifact (library + macOS .dmg).

### v1.0.0 GA milestone callout

- **v1.0.0 GA = PR 11** (library mode + macOS .dmg, codesign + notarize). Shipped `6af3684` → merged `bbb4395`. **First end-user-shippable artifact** — the engine (PR 1-7 + 4.5) plus UI scaffold (PR 10a) plus packaging now reaches a real user's Mac without a dev environment. Remaining work (PR 8 perf, PR 9 preflop, PR 10b real-bindings, PR 10a.5 polish, PR 12 stretch) is post-GA enhancement, not blocker.

### v0.5.0 milestone callout

- **v0.5.0 = PR 6** (Rust port of HUNL postflop, ~24x speedup over Python tier). Shipped `0933367` → merged `6c438b8`. First production-grade engine perf tier; differential tests vs Python reference green on Kuhn/Leduc/river-only smokes.

### PR 6-specific risks (RESOLVED at `6c438b8`)

- **HashMap iteration determinism.** RESOLVED — verified clean in PR 6 audit; implementer used sorted-key iteration on Python-facing export paths and the same-diff-twice byte-identical test passed.
- **Thread scheduling / GIL re-entry.** RESOLVED — verified clean in PR 6 audit; no Python callbacks inside the inner CFR loop, all `py.allow_threads` blocks inspected.
- **Cargo.lock convention.** RESOLVED — `cargo check --locked` wired in `scripts/check_pr.sh` and confirmed by PR 6 audit; convention carries forward to PR 8.

### PR 7-specific risks (RESOLVED at `d135add`)

- **Brown's solver reproducibility — seed determinism + iteration count.** RESOLVED — PR 7 pinned Brown's commit + seed; diff fixtures regenerate byte-identical across runs.
- **River-spot equivalence mapping (action labels, bet-size discretization).** RESOLVED — PR 7 audit confirmed the action-menu translation layer round-trips both directions; tolerance bands documented.

### Carryover items

- **PR 5 TURN abstraction coverage gap.** 6 tests skip-marked due to Python-tier TURN clustering shape mismatch at production scale. **Action:** re-enabled + verified in PR 6 audit (Rust port resolved via cleaner production-scale clustering).
- **PR 4 kmeans homogeneity test loosened** (95% → 50%) due to synthetic blob fixture limitations. RESOLVED — PR 6 Rust kmeans pass tightened threshold; Python-tier limitation documented.
- **PR 11 PyInstaller + Rust `_rust.so` bundling risk** flagged in PR 11 audit prompt. **Action:** explicit `--add-binary` test step in PR 11 audit.
- **Audit follow-up backlog — should-fix items across PR 3/3.5/4/5.** **RESOLVED** at `9f09d49` / v0.5.2 — PR 4.5 audit-debt sweep landed (mechanical fixes, no behavior changes).
- **`origin/equity-precision` branch dangling at `01475e8`**, divorced from integration line. **RESOLVED 2026-05-22** — branch deleted from origin; confirmed gone, matches desired state.
- **I2 — PR 11 first-launch warning when abstraction artifact missing.** Small (~5-line UX edit). **Action:** defer to PR 11 implementation; documented in `autonomous_log.md` open question §5.
- **N5 — PR 4 §10 wheel-bundling claim contradicted by PR 11 packaging reality.** Small (one-line spec cleanup). **Action:** defer to PR 11 spec pass; documented in `autonomous_log.md` open question §6.

### Pending user decisions — status as of 2026-05-22

- **Tag ratification (v0.6.0 + v1.0.0 reachability from main).** SELF-RESOLVED — integration→main FF merge today brought both tags into main's history; no tag move needed.
- **`origin/equity-precision` deletion.** RESOLVED — already gone from origin (see Carryover above).
- **PR 10a Q3 iter count (1000 vs 2000).** RESOLVED — reframed as exploitability-target slider with iter cap; numeric tier defaults deferred to a post-PR-10b measurement pass. See §1 Solver UI control + §9 archive.
- **PR 8 / PR 9 / PR 10b sequencing.** RESOLVED — PR 10a.5 first, then PR 8 ∥ PR 9 in parallel, then PR 10b. See §2 Post-GA sequencing decision.

### Load-bearing caveat

- **No production-scale HUNL solve performed yet.** All ✅ PRs through PR 7 ran against Kuhn/Leduc/river-only smokes + synthetic abstractions; the first real 200K-iter MC build (~10 hr wall-clock) still pending. PR 4–7 ✅ tags reflect code correctness + ~24x Rust speedup on micro-benchmarks + external Nash validation on river spots, not end-to-end production validation. Source: `autonomous_log.md` open question §9.

---

## 7. Kickoff docs staged

Nine `launch_kickoff.md` files now live under `docs/` ready to be invoked verbatim as orchestrator-launch prompts. Each spawns an aggregate fan-out wave (implementer + tests-from-spec + audit + any specialized agents):

- **`docs/pr4_5_audit_debt/launch_kickoff.md`** — sweep PR that drained the should-fix backlog (PR 3 / 3.5 / 4 / 5). **Shipped at `9f09d49` / v0.5.2.**
- **`docs/pr6_prep/launch_kickoff.md`** — HUNL postflop Rust port (shipped at `6c438b8`, v0.5.0).
- **`docs/pr7_prep/launch_kickoff.md`** — river-spot diff test vs `noambrown/poker_solver`; external Nash validation gating PR 6 trust (shipped at `d135add`, v0.5.1).
- **`docs/pr8_prep/launch_kickoff.md`** — NEON SIMD + cache-blocking + public chance sampling in Rust.
- **`docs/pr9_prep/launch_kickoff.md`** — HUNL preflop, both tiers.
- **`docs/pr10_prep/launch_kickoff_10a.md`** — NiceGUI scaffold + mock solver (shipped at `b880032`, v0.6.0).
- **`docs/pr10_prep/launch_kickoff_10b.md`** — replace mock with real solver bindings (deps: PR 9 + 10a).
- **`docs/pr11_prep/launch_kickoff.md`** — library mode + macOS packaging (shipped at `bbb4395`, **v1.0.0 GA**).
- **`docs/pr12_prep/launch_kickoff.md`** — 3-handed postflop stretch (optional, explicitly approximate).

Sequencing intent: PR 6 ✅ → PR 7 ✅ → PR 4.5 ✅ → PR 10a ✅ → PR 11 ✅ (**v1.0.0 GA**) → PR 10a.5 + PR 8 + PR 9 → PR 10b → PR 12.

**Remaining post-GA work:** PR 10a.5 (UI polish / xfail follow-ups beyond `040fc45`), PR 8 (NEON SIMD + cache-blocking + public chance sampling), PR 9 (HUNL preflop both tiers), PR 10b (real-solver bindings replacing the mock), PR 12 (3-handed stretch, optional).

### User-facing docs (in flight 2026-05-22)

- **`USAGE.md`** — end-user guide (install, first solve, range editor, exploitability slider semantics, library mode). Being written this session.
- **`DEVELOPER.md`** — contributor guide (two-tier architecture, differential test loop, audit protocol, PR branch convention, perf instrumentation). Being written this session.
- **`README.md`** — remains the project landing page (one-screen pitch + quick install + links to USAGE and DEVELOPER). No change planned.

---

## 8. References (local, not redistributed)

Local references live in `/Users/ashen/Desktop/poker_solver/references/`:
- `papers/` — DCFR, CFR+, Depth-Limited Solving, Deep CFR, Libratus, Pluribus, ReBeL, hyperparameter scheduling, GTO poker survey, etc.
- `code/` — Noam Brown's `poker_solver` (MIT), `b-inary/postflop-solver` (AGPL), `24parida/shark-2.0` (unlicensed), `bupticybee/TexasSolver` (AGPL), `ericgjackson/slumbot2019` (MIT), `google-deepmind/open_spiel` (Apache 2.0)
- `blog/`, `products/` — GTO Wizard, PioSolver, MonkerSolver, DeepSolver competitor analysis

**Reference-first rule:** Always check `references/README.md` (topic-to-file index) before any technical claim. Never guess from training data when a local authoritative source exists.

**License audit (load-bearing):**

| Repo | License | Copy policy |
|---|---|---|
| `noambrown_poker_solver` | **MIT** | OK to copy / port verbatim with notice |
| `slumbot2019` | **MIT** | OK to copy / port verbatim with notice |
| `open_spiel` | **Apache 2.0** | OK to copy with attribution; Kuhn/Leduc oracle |
| `postflop-solver` | **AGPL v3** | Read-only inspiration; never copy |
| `TexasSolver` | **AGPL v3** | Read-only inspiration; never copy |
| `shark-2.0` | **Unlicensed** | Read-only inspiration (defaults to all-rights-reserved) |

---

## 9. Archive / decision log

Decisions made then revised. Preserved here so the reasoning trail isn't lost.

- **Stack range: 1–500 BB → 2–250 BB.** Aspirational at session start; revised after tree-size agent showed 500 BB unreachable on consumer hardware. Current state: see §1 stack-depth table.
- **Implementation language: Pure Rust → Python reference + Rust production (two-tier).** Revised after user's preference for "easily interpretable" implementation alongside "super optimized" production. Validated by Noam Brown's own `cpp/` + `python/` pattern. Current state: see §1 Architecture.
- **Performance target: ≲30 min upper bound → honest 1–45 min range.** Original framing collapsed all solve types into one number. Current state: see §1 perf table.
- **Goalpost: GTO Wizard parity → PioSolver parity for HU local solving.** GTOW is fundamentally a cloud + multiway-library + neural-value-net product; without cloud, parity is unreachable. Current state: see §1 Goal.
- **Card abstraction: hybrid lossless river → pure 256/128/64 with PR 5 profiler revisit.** Agent caught the extrapolation error: replacing 64 buckets with 1326 hands on river *increases* memory. Current state: see §1 card abstraction.
- **Branching: direct commits to main → per-PR feature branches from PR 3.** PR 1 and PR 2 went directly to main (acknowledged; not retroactively fixable). Current state: see §1 Branching + §5 Pacing.
- **`postflop-solver` license: MIT (per original Ultraplan) → AGPL v3 (per license audit).** Current state: see §7 License audit.
- **PR 10: single PR → split into 10a (scaffold + mock) and 10b (real bindings).** Allows UI work to start as soon as PR 5 lands (data types only) without blocking on Rust port. Current state: see §2 trajectory.
- **Research plan (Phase 1) — three parallel Explore agents.** Complete. Findings folded into §1 locked decisions. Was load-bearing for algorithm choice (DCFR), hardware path (CPU not GPU), industry positioning (PioSolver target), and the license audit.
- **First-PR scope (original 9-step Ultraplan):** Kuhn + DCFR + maturin/PyO3 + diff test + references scaffold. Shipped as PR 1 (`9d2d66a`). Detailed step-by-step spec retired; current state is the code on main.
- **PR 10a Q3 — iter count 1000 vs 2000 → exploitability-target slider with iter cap.** Original framing pinned the UI knob to raw iterations. Reframed 2026-05-22 because industry standard is exploitability, not iter count: `postflop-solver` defaults to 0.5% pot, GTOW library tier is 0.1–0.3% pot, Shark targets 0.1% pot, Brown's MIT reference solver uses 2000 iters as the convergence proxy. Exploitability is the dimensionless quality measure across stacks/streets; iter count is just the safety ceiling. Numeric tier defaults deferred to a post-PR-10b measurement pass. Current state: see §1 Solver UI control.
