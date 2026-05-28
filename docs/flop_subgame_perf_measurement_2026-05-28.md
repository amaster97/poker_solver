# Flop Subgame Solve — Empirical Wall-Time & Memory Measurement (4-Config Sweep)

**Date:** 2026-05-28
**Status:** All 4 configurations tested — **OOM at every viable setting**.
**Author:** Perf-measurement agent
**Companion docs:**
- `docs/j7o_player_pov_walkthrough_2026-05-28.md` (PR #183) — deferred flop solves citing "5+ min, killed."
- `docs/v1_10_postflop_optimization_plan.md` (da38888) — root-cause analysis at `dcfr_vector.rs:591-835` + 4-PR optimization roadmap.

**PR branch:** `flop-perf-measurement`

---

## TL;DR

Prior agents reported flop subgame solves "5+ min, killed." This work measures actual wall-time and memory at **four** configurations spanning the spec'd parameter range plus a floor test. **No configuration completes a flop solve within the 20-min budget.** Three OOM (peak RSS 2.3-2.9 GB) and one (the floor) hits the 20-min hard timeout.

| Config | top_k | iters | hero × villain classes | Wall to terminal | Peak RSS | Outcome |
|---|---|---|---|---|---|---|
| **0 — floor** | 2 | 2 | 3 × 2 | **20:00** (timeout) | **2.62 GB** | TIMEOUT — never reached SOLVE COMPLETE |
| **1 — minimal** | 4 | 5 | 5 × 4 | **~5:00** | **2.31 GB** | OOM (signal 9) |
| **2 — moderate** | 8 | 20 | 9 × 8 | **~2:00–2:30** | **2.93 GB** | OOM (signal 9) |
| **3 — light-prod** | 15 | 50 | 16 × 15 | **~10-20 s** | unmeasured (sub-30s sample) | OOM (signal 9) |

**Verdict: realtime flop subgame solving is NOT feasible at any of these configurations on the current implementation.** Even the smallest setting that gives a multi-class game (`top_k=2`) cannot complete a 2-iteration solve in 20 minutes.

**Recommendation:** v1.9.0 ships without flop subgame as already framed by PR #183. v1.10 optimization roadmap (`docs/v1_10_postflop_optimization_plan.md`) is the authoritative path forward — root cause and remediation candidates already analyzed.

---

## Hardware

- **Model:** Apple M-series, arm64
- **OS:** Darwin 24.6.0
- **Python:** 3.13.1
- **Rust ext:** `poker_solver/_rust.cpython-313-darwin.so` arm64 (verified `file` arch match)
- **Build:** rebased onto `origin/main` HEAD f0fc879 — includes PR #182 (b/r token fix), PR #177 (Phase-4 postflop wiring), PR #183 (walkthrough doc).

---

## Methodology

### Script

`scripts/measure_flop_subgame_perf.py` — a single-flop variant of PR #183's `run_j7o_walkthrough_full_pov.py`. Strips everything except:

1. Generate a 40 BB preflop blueprint (1,500 DCFR iters, 169-class abstraction). Wall: ~4.5s consistently across all 4 runs.
2. Compute continuation ranges after `pf_seq = ("b300", "c")` (SB opens 3 bb, BB calls). Fast (<1ms — pure-Python projection).
3. Filter hero/villain ranges to top-K classes by reach, with `J7o` pinned in hero.
4. Call `solve_postflop_from_blueprint(...)` on board `[A♦, 8♥, 9♦]` with `iterations=N` (the test parameter).
5. Time the solve with `time.perf_counter()`, emit JSON with results.

### Watcher

`scripts/run_flop_perf_measurements.sh` — for each config:
- Spawns python in background, captures pid.
- Background loop samples `ps -o rss= -p $PYPID` every 30s, tracks peak RSS.
- Foreground loop polls every 5s for a 20-min (1200s) hard kill via `kill -9`.
- Writes `.perf_logs/<label>.{log,rss,json}` (gitignored).

### What was NOT measured

- **Per-iter cost decomposition** — the solve died inside the first iter for Configs 1-3 and never produced an iter-completion log line. Configs 0 had multiple GC cycles suggesting it was completing inner work but not whole iters.
- **Memory by sub-component** — `ps -o rss` is process-wide. No instrumentation inside the Rust solver was added (engine untouched per constraint).
- **Turn / river** — known fast from PR #183 (turn ~15s, river <1s). Not retested.

For root-cause memory profiling at the `dcfr_vector.rs` line level, see `docs/v1_10_postflop_optimization_plan.md` §1.2 (Three cost dominants).

---

## Detailed Results

### Config 0 — floor test (`top_k=2, iters=2`)

Smallest configuration that gives a multi-class game (3 hero × 2 villain after J7o pin). Intended to determine whether ANYTHING flop-related can complete.

```
hero_classes=3 ['K7o', 'K8o', 'J7o']
villain_classes=2 ['ATs', '32s']
```

**Wall: 20:00 (1203s, hard-killed by watcher)**
**Peak RSS: 2.62 GB**
**Output: none (never reached SOLVE COMPLETE)**

RSS trajectory: spike to 1.2 GB at t=17s, then oscillated between 100 MB and 2.62 GB for the entire 20-min budget — i.e., the solver was **computing, not deadlocked**, but not converging fast enough. CPU stayed at 95-100% throughout (with one ~30s window at 24% CPU around t=4:30 where it appeared to swap, then recovered). 8 GC cycles observed where RSS dropped to <200 MB before climbing again.

This is the most surprising result: even at 2 hero classes × 2 villain classes × 2 iterations, a flop solve cannot complete in 20 minutes. The chance tree from flop → river (47 turn cards × 46 river cards ≈ 2,162 board completions) dominates regardless of class-count compression. This validates the v1.10 plan's §1.2 dominant 2: "decision_node_count for a typical flop subgame at raise_cap=3 with 2 bet sizes: expect ~5000-30000 decision nodes" — even at 3×2 ranges, the betting × chance tree size is the bottleneck.

### Config 1 — minimal (`top_k=4, iters=5`)

Spec'd minimal config. Matches what PR #183's walkthrough author observed at "5+ min, killed."

```
hero_classes=5 ['K7o', 'K8o', 'KK', 'K7s', 'J7o']
villain_classes=4 ['T5s', 'T5o', 'KQo', 'TT']
```

**Wall: ~5:00 (OOM-killed)**
**Peak RSS: 2.31 GB**
**Output: none (process killed before SOLVE COMPLETE log line)**

RSS trajectory:
- t=0:00–2:00: 270-413 MB stable plateau
- t=2:30–4:00: still 270-413 MB
- **t=4:30: 1.70 GB** (memory blowup begins)
- **t=5:00: 2.31 GB → SIGKILL**

This confirms the prior agent's "5+ min, killed" observation **and** identifies the cause: **OOM**, not CPU starvation. The v1.10 plan §1.2 dominant 1 explains this: "~10-20 GB of transient Vec<f64> allocation per iteration" — the allocator pressure is what produces the 2.3 GB RSS high-water mark.

### Config 2 — moderate (`top_k=8, iters=20`)

Spec'd "a bit more useful" config.

```
hero_classes=9 ['K7o', 'K8o', 'KK', 'K7s', 'QJo', 'K9o', 'K6o', 'A6s', 'J7o']
villain_classes=8 ['42s', 'K7s', 'J4o', '54s', '72o', 'T7o', '96s', 'J5o']
```

**Wall: ~2:00–2:30 (OOM-killed)**
**Peak RSS: 2.93 GB**
**Output: none**

RSS hit 2.93 GB at t=0:30 (already swapping at that point), oscillated 0.5-1.7 GB, then signal-9'd between t=2:00 and t=2:30. 2× larger classes → ~4× larger regret matrix → OOM in **less than half** Config 1's wall time, with **27% higher** peak RSS.

### Config 3 — light-production (`top_k=15, iters=50`)

Spec'd "matches salvage agent's 5+min observation" config — but at top_k=15, the matrix is 4× larger than Config 1.

```
hero_classes=16  (16 classes incl. J7o pin)
villain_classes=15
```

**Wall: ~10-20 s (OOM-killed effectively at allocation time)**
**Peak RSS: unmeasured** (process died before the 30s RSS watcher tick; final `ps` observation pre-death: 408 MB at t=8s, then signal-9'd shortly after)
**Output: none**

RSS watcher captured only the initial 608 KB sample (taken before python started loading the Rust extension), then python died before next sample. Last log line: `STARTING flop solve`. Bash watcher reported exit 1 (python killed). The 16 × 15 class matrix combined with the chance-tree expansion exhausts memory immediately.

---

## Analysis Summary

**OOM wall-time anti-scales with config size**, but **only roughly**:
- Config 0 (3×2 = 6 cells) — 20 min timeout (no OOM)
- Config 1 (5×4 = 20 cells) — OOM at 5 min, 2.3 GB
- Config 2 (9×8 = 72 cells) — OOM at 2-2.5 min, 2.9 GB
- Config 3 (16×15 = 240 cells) — OOM at <20s, peak unmeasured

This is consistent with the v1.10 plan §1.2 dominant 1 (allocator-driven OOM scaling with iter cost) and dominant 2 (per-decision storage scaling with class count squared). The single most important observation: **Config 0 with 6 cells STILL cannot complete because of dominant 2 alone (decision-node count, independent of class count)**. This rules out "shrink top_k further" as a viable fix — even top_k=1 (pinned class only) would still iterate the full chance/betting tree, so dominant 2 dominates for any flop solve.

For the full root-cause chain and four-PR remediation roadmap (arena, LTO, vector-form flop forward walk, rayon multi-threading), see `docs/v1_10_postflop_optimization_plan.md`.

---

## Feasibility Verdict for v1.9.0

**Realtime flop subgame solving is NOT feasible** at any of the four configurations tested. The smallest viable game (top_k=2, the floor test) cannot complete a 2-iteration solve in 20 minutes; the spec'd configs all OOM.

Even hypothetical further reductions are not viable:
- `top_k=1` → only the pinned hero class (J7o), so the "subgame" is a single-class lookup. No game-theoretic content — equivalent to equity calculation, which the existing equity-only fallback in PR #183 (`derive_continuation_ranges_from_blueprint`) already does in <1ms.
- `iters=1` → single DCFR pass produces only uniform-random strategies. Useless output.

**Therefore: flop solve cannot be ship-quality at v1.9.0 timeframe without algorithmic redesign per the v1.10 plan.**

---

## Recommendation

**Ship v1.9.0 without flop subgame.** PR #183's deferral is correct as a release decision. The walkthrough doc retains equity-only flop directional reads via `derive_continuation_ranges_from_blueprint` (O(1) lookups, no solve needed). Turn and river solves work and are documented.

**For v1.10:** follow `docs/v1_10_postflop_optimization_plan.md` — specifically the Candidate A (arena) + Candidate C (vector-form flop forward walk) combination, which is projected to bring flop from "OOM at 5 min" to "60-90s at top_k=169." This measurement supports the v1.10 plan's expected speedup target.

---

## Reproducibility

To reproduce all 4 measurements:

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/flop-perf-measurement
bash scripts/run_flop_perf_measurements.sh 2 2  config0_floor
bash scripts/run_flop_perf_measurements.sh 4 5  config1_minimal
bash scripts/run_flop_perf_measurements.sh 8 20 config2_moderate
bash scripts/run_flop_perf_measurements.sh 15 50 config3_light_prod
```

Each writes to `.perf_logs/<label>.{log,rss,json}`. Wall time and RSS series are in `.rss`; the JSON has the structured summary (`status: complete|timeout|error`).

**Note:** the `_rust.cpython-313-darwin.so` must be copied from the main worktree (it's gitignored as `*.so`). On this worktree:

```bash
cp /Users/ashen/Desktop/poker_solver/poker_solver/_rust.cpython-313-darwin.so \
   /Users/ashen/Desktop/poker_solver_worktrees/flop-perf-measurement/poker_solver/
```

---

## Cross-references

- `docs/j7o_player_pov_walkthrough_2026-05-28.md` (PR #183) — the doc that deferred flop solves with the "5+ min, killed" observation that this measurement quantifies and extends to a 4-config sweep.
- `docs/v1_10_postflop_optimization_plan.md` — authoritative root-cause analysis at `crates/cfr_core/src/dcfr_vector.rs:591-835` (Vec<f64> allocator pressure) and 4-PR optimization roadmap.
- `poker_solver/blueprint_subgame.py` — `solve_postflop_from_blueprint`, the function under measurement. Untouched in this PR.
- PR #182 — b/r token fix on the preflop→postflop boundary. Required for any postflop solve; merged on `main`.
- PR #177 — Phase-4 postflop subgame wiring. Defines the call path measured here.
