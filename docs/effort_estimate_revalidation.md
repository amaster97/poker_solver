# Effort-estimate revalidation — PR 6 through PR 12

**Date:** 2026-05-22
**Sources:** git log timestamps (2026-05-20 → 2026-05-22); `git diff --shortstat` per PR; `docs/autonomous_log.md`; `docs/roadmap_status_2026-05-22.md`; PLAN.md § 2 prior estimates; PR specs in `docs/pr*_prep/`.

---

## 1. Method — hours-per-LOC + agents-per-PR from shipped data

Wall-clock here is measured from "PR-N branch first commit" to "PR-N branch final commit" (per `git log --date=iso`). It UNDERSTATES the engineering hours because spec-writing and audit cycles ran in parallel with prior PRs. It is, however, the most defensible scalar we have.

| PR | First commit | Final commit | Wall-clock (h) | Insertions (LOC) | New tests | Concurrent agents | h / 1000 LOC |
|---|---|---|---|---|---|---|---|
| PR 3 (HUNL tree + actions, Python) | 2026-05-21 01:16 | 2026-05-21 01:59 | ~6–9 (reported) | 1,897 | 41 | 3 impl + 1 audit | ~3.7 |
| PR 3.5 (push/fold charts) | 2026-05-21 15:19 | 2026-05-21 16:23 | ~3–4 (reported) | 4,963 (incl. chart JSON) | 13 | 3 impl + 1 audit | ~0.7 (LOC inflated by chart blob) |
| PR 4 (card abstraction, EMD + suit-iso) | 2026-05-21 17:17 | 2026-05-21 17:17 | ~8–10 (reported) | 3,038 | 35 | 3 impl + 1 audit | ~3.0 |
| PR 5 (HUNL postflop solve + profiler) | 2026-05-22 02:42 | 2026-05-22 02:42 | ~6–8 (reported) | 2,642 | 23 | 3 impl + 1 audit | ~2.6 |

**Observations:**

1. **Steady ~3 h / 1000 LOC** for substantive algorithmic PRs (3, 4, 5). PR 3.5 is an outlier because most of its LOC are generated chart JSON, not hand-written.
2. **3 impl + 1 audit agent is the steady-state pattern.** Every shipped PR used this exact fan-out.
3. **Total: ~24–32 engineering-hours across 4 PRs over ~30 wall-clock hours of autonomous run** (PR 3 start to PR 5 merge: 01:16 of 05-21 → 02:42 of 05-22 ≈ 25½ wall-clock hours).
4. The reported hours are user-perceived hours, not parallel agent-hours. Real agent-hours per PR are ~3× wall-clock (3 concurrent impl agents).

---

## 2. Calibration — Rust vs Python productivity

PR 6 is the first Rust-heavy PR. We have **no shipped Rust-port baseline** from PR 1 / 2 to anchor the multiplier (those PRs landed before the autonomous-session timing instrumentation, and the Rust there was scaffold-thin: 166 LOC `kuhn.rs`, 307 LOC `leduc.rs` — small + algorithmically trivial).

PR 6's Rust port is already partially landed on `pr-6-rust-hunl-port`: `crates/cfr_core/src/` now totals **3,912 Rust LOC**, of which `hunl.rs` (1,178), `hunl_eval.rs` (373), `hunl_tree.rs` (335), `hunl_solver.rs` (363), and `abstraction.rs` (497) are PR 6 surface. That's ~2,800 PR-6-specific Rust LOC already on the branch.

**Calibration assumption (HONESTLY UNCERTAIN):**

- Rust takes **1.5–2× longer per LOC than Python** at the same algorithmic complexity (typical industry figure; user has flagged "Rust-zero" experience as a friction point so Claude must port mechanically without user co-debugging).
- BUT: PR 6 is **mechanical port from a passing Python spec**, which is faster than greenfield Rust. Net: probably **1.2–1.5×** Python rate.
- Offset: differential-test gate adds wall-clock latency for failed diff iterations.

**Calibration verdict:** treat Rust-heavy PRs at ~4–5 h / 1000 LOC (vs ~3 for Python). High uncertainty band.

---

## 3. Per-PR re-estimate

| PR | Scope | Original (PLAN.md) | Re-estimate (h, wall-clock) | Confidence | Risk factors |
|---|---|---|---|---|---|
| **PR 6** | Rust port of postflop solver | 3–5 days | **10–16 h** | Medium | Diff-test convergence failures; `.npz` loader format drift (resolved per PR 6 spec §4.4); already 50–70% LOC-landed → smaller actual surface remaining |
| **PR 7** | River-spot diff vs noambrown | 1 day | **4–6 h** | High | noambrown C++ build environment on macOS arm64 (Brown's `cpp/` uses cmake — should be clean); fixture curation is 70% of the work |
| **PR 8** | NEON SIMD + cache-blocking + PCS | 2–3 days | **16–24 h** | Low-medium | First time hitting unsafe Rust intrinsics; SIMD diff against scalar must match to 5e-3; PCS importance-correction is easy to bug; 10× speedup gate could fail → re-iter |
| **PR 9** | HUNL preflop, both tiers | 3–5 days | **14–22 h** | Low-medium | Blueprint+refinement is genuinely complex; 9 stack-depth solves multiply work; Pio-100BB validation may take diff-debugging time; abstraction tier-switch at 150 / 200 BB adds surface |
| **PR 10a** | NiceGUI scaffold + mock solver | 2 days | **8–12 h** | High | UI surface is well-spec'd (1227 LOC pr10_spec); mock solver insulates from real-engine churn; biggest risk is UX-decision rework after user review |
| **PR 10b** | Real-solver bindings | 0.5 day | **3–5 h** | High | Mechanical swap if 10a sticks to public surface (`HUNLSolveResult` shapes are locked since PR 5) |
| **PR 11** | Library mode + macOS .dmg | 2–3 days | **10–18 h** | **Low** | **Highest variance.** PyInstaller × Rust `_rust.so` bundling is the explicit risk PLAN.md §6 flags; codesign + notarize needs Apple Dev enrollment ($99) OR unsigned fallback path; SQLite library code itself is easy (~300 LOC); failure mode = `.app` doesn't launch on a clean machine; iteration loop here can blow up |
| **PR 12** | 3-handed stretch (post-v1) | 6–12 weeks | **6–12 weeks (unchanged)** | Low | Explicitly out of v1 scope; LCFR convergence on 3-handed has no theoretical guarantee; this is stretch / research, not engineering |

---

## 4. Updated time-to-v1

**v1 = PR 11 ships.** Sum of re-estimates for PR 6 through PR 11 inclusive (using midpoints):

| PR | Midpoint (h) |
|---|---|
| PR 6 | 13 |
| PR 7 | 5 |
| PR 8 | 20 |
| PR 9 | 18 |
| PR 10a | 10 |
| PR 10b | 4 |
| PR 11 | 14 |
| **Total** | **~84 h** |

**Translation to calendar:**

- **Autonomous overnight pace** (the regime since 2026-05-20): ~6–10 h of wall-clock progress per overnight session → **~9–14 sessions remaining**.
- **Working-day pace** (if user mixes in waking hours): ~3 h focused review per day → **~30 days** if review is the bottleneck (it usually is, per the "user OK gates main merges" rule).
- **Pessimistic** (PR 8 SIMD blows up on debug-loop OR PR 11 packaging hits PyInstaller hell): add 50% → **15–20 overnight sessions** OR **~45 days** at review-gated pace.

**Best estimate: PR 11 ships in 2–6 weeks** depending on user review cadence + PR 8 / PR 11 risk realization. **Most likely 3–4 weeks.**

This is faster than PLAN.md's original 6-month framing because:
- The original "6–9 months focused work" line in PLAN.md §1 assumed solo-human pace, not concurrent autonomous-agent pace.
- 4 PRs (3, 3.5, 4, 5) shipped in ~25 wall-clock hours; the same cadence extrapolated to 7 remaining PRs gives ~60 wall-clock hours, which scales to weeks not months.

**Caveat (per "don't extrapolate" rule):** this is a layer-by-layer projection from observed PR cadence. It does NOT account for:
- Audit-debt accumulation (PR 4.5 sweep already needed)
- User-review latency (variable; outside Claude's control)
- Force-majeure rework (e.g., DCFR diff fails at 5e-3 in PR 7 → debug → potentially revisit PR 5 algorithm)

---

## 5. Critical-path identification

**PR 8 is the schedule limit, with PR 11 as a close second.**

### Why PR 8

1. **Largest single time block (16–24 h).** SIMD intrinsics + cache-blocking + public chance sampling are three orthogonal optimizations; each can break independently.
2. **Hard 10× speedup gate.** PR 8 spec §1: "Hard gate at 10×: if not met, PR does not ship." That's a quantitative pass/fail — unlike correctness PRs which can ship with a should-fix backlog.
3. **First Rust `unsafe` surface in the codebase.** Every existing Rust file is safe-Rust; NEON intrinsics break that pattern. Memory-safety regressions could surface as flaky tests, hard to debug.
4. **Diff test must match scalar to 5e-3 per-action.** SIMD reduction order differs from scalar; reproducing FP-bit-identical sums is hard. Tolerance budget here is tight.
5. **No prior shipped Rust perf work to calibrate against.** PR 1 / 2 Rust was scaffolding; PR 6 Rust is the algorithmic port (no perf). PR 8 is "first contact" with Rust perf engineering in this project.

### Why PR 11 is close

1. **Lowest confidence rating** (PLAN.md open-items audit flags `_rust.so` bundling explicitly).
2. **Apple notarization is a black box.** Failures don't surface in `pytest`; they surface as "Gatekeeper refused to launch the app on a clean Mac."
3. **PyInstaller + native shared libraries is historically painful.** Discovery cost of figuring out the right `--add-binary` invocation is unknown.
4. **No clean fallback if it doesn't work.** Unsigned `.app` is shippable but degrades the "is an app on my Mac" deliverable PR 11 spec §1 commits to.

### Schedule-limit sequencing

```
PR 6 (in flight) ────────────┐
                             │
PR 4.5 audit-debt sweep ─────┼────┐
                             │    │
                  PR 7 ──────┘    │
                                  │
                     PR 8 ◀───────┘  ← CRITICAL PATH (highest variance + hard gate)
                       │
              ┌────────┴────────┐
              │                 │
           PR 9            PR 10a (parallel)
              │                 │
              └────────┬────────┘
                    PR 10b
                       │
                     PR 11 ◀── SECOND CRITICAL POINT (packaging variance)
                       │
                       ▼
                      v1
```

PR 8 is sequenced before PR 9 / 10a per PLAN.md §2 dependency graph (PR 9 wants Rust-optimized solver for the 9 stack-depth blueprint solves). If PR 8 slips, PR 9 starts late or uses the unoptimized Rust path, which makes the 9-stack-depth blueprint pass too slow to feasibly debug.

---

## 6. Confidence-honesty section

What I am NOT confident about:

- **"~3 h / 1000 LOC" Python rate is N=3 (PRs 3 / 4 / 5).** Could be 2 or 5; can't tell from 3 samples.
- **Rust calibration is an a-priori guess.** PR 6 will be the first real data point. If PR 6 ships in 6 h, downgrade all Rust estimates by 30%. If it takes 20 h, upgrade them by 50%.
- **PR 12 is "6–12 weeks" because it's a research item, not engineering.** That estimate is whatever the user says it is; mine is uninformed.
- **User-review cadence is the bigger variable than implementation time.** The "ship in 3–4 weeks" target assumes user can review PR-N within a day of PR-N-1 merge. If reviews stack up, calendar slips proportionally.

What I AM confident about:

- The 3 impl + 1 audit fan-out pattern is shippable; no failed PR yet.
- PR 7 + PR 10a + PR 10b are low-risk and will ship close to estimate.
- PR 8 + PR 11 hold the schedule risk; everything else is bookkeeping.

---

## 7. Updated trajectory table for PLAN.md

| PR | Original estimate | Re-estimate | Confidence | Calibrated from |
|---|---|---|---|---|
| PR 6 | 3–5 days | 10–16 h | Medium | LOC partial-landed + Rust multiplier |
| PR 7 | 1 day | 4–6 h | High | Diff-test fixture analog to PR 5's 3 fixtures |
| PR 8 | 2–3 days | 16–24 h | Low-medium | No prior Rust-perf data; first unsafe |
| PR 9 | 3–5 days | 14–22 h | Low-medium | Blueprint+refinement complexity multiplier |
| PR 10a | 2 days | 8–12 h | High | UI public surface locked; well-spec'd |
| PR 10b | 0.5 day | 3–5 h | High | Mechanical swap |
| PR 11 | 2–3 days | 10–18 h | Low | Apple packaging is a known unknown |
| PR 12 | 6–12 weeks | 6–12 weeks | Low | Research / stretch; out of v1 |

**v1 (PR 11 shipped):** 3–4 weeks most likely; 2–6 weeks honest range.
**Critical path:** PR 8 (hard speedup gate + first `unsafe` surface).
**Second risk:** PR 11 (PyInstaller × `_rust.so` × Apple notarization).
