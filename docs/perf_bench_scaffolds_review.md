# Performance benchmark scaffolds review — PR 8 readiness

**Date:** 2026-05-22. **Reviewer:** read-only audit (no benches/ files created, no benches run — would invalidate PR 8 baseline capture).

**Scope:** sanity-check that the perf-benchmark scaffolds for PR 8 (NEON SIMD + cache-blocking + PCS) are in good shape, or propose what is missing.

---

## 1. Current state

**Crate tree:**
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/` contains `Cargo.toml`, `src/`, and `tests/`. **No `benches/` subdirectory exists.**
- Repo root has **no `benches/` directory either** — `ls /Users/ashen/Desktop/poker_solver/benches/` returns empty (the directory does not exist).
- No `benches/baseline.json` artifact present anywhere in the repo.

**Cargo.toml status** (`/Users/ashen/Desktop/poker_solver/crates/cfr_core/Cargo.toml`):
- **`criterion` is NOT declared as a dev-dependency.** Current `[dev-dependencies]` block contains only `pyo3 = { version = "0.23", features = ["auto-initialize"] }`.
- No `[[bench]]` entries in `Cargo.toml`. `harness = false` (required for Criterion) is not set anywhere.
- No `rand` or `rand_chacha` runtime deps (PR 8 Agent C adds these for PCS, per launch_kickoff.md §3 ownership table).

**Prior-PR carryover:** None. PR 6 (HUNL postflop port) shipped tests under `crates/cfr_core/tests/{hunl_state_unit.rs, test_hunl_rust.rs}` — both are correctness tests, not bench harnesses. The PR 6 spec did NOT seed any Criterion scaffolding; PR 8 spec §2 line 26 explicitly says "PR 6's bench setup, if any, is treated as a starting point, not a contract." There is no starting point.

**Verdict:** scaffolds are at zero. PR 8 must create everything from cold. This is intentional per spec §6 "Files to create" — `benches/cfr_bench.rs`, `benches/baseline.json`, and the Criterion dev-dep are all owned by Agent B.

---

## 2. What PR 8 needs (and is the spec already saying it)

The spec already enumerates these. I summarize for completeness; nothing missing from the spec itself, only from the live repo.

**2a. `benches/baseline.json` — pre-PR-8 capture.**
- Required by spec §2 (line 47: "No baseline = no PR 8") and §9 #8 ("Baseline must be committed before any optimization lands").
- Captures: machine ID, macOS version, `rustc --version`, `git rev-parse HEAD` (pre-PR-8 commit), date, per-spot wall-clock mean ± stddev across the 4 bench spots.
- Lifecycle: committed (spec §11 D9), NOT gitignored.
- **Critical sequencing (launch_kickoff.md §7 baseline-first inversion):** Agent B's FIRST commit on the PR-8 branch must be the baseline-only commit, BEFORE any `FlatInfosetStore` refactor lands. If Agent B refactors first, baseline contamination invalidates the 10× hard gate measurement.

**2b. `benches/cfr_bench.rs` — Criterion harness, 4 spots.**
- Spec §2 table:
  - Spot 1: Kuhn (12 infosets) — 10K iterations, expected <1 s. Sanity floor; SIMD effect is noise.
  - Spot 2: Leduc (288 infosets) — 10K iterations, expected 1–5 s.
  - Spot 3: HUNL flop, simple (`As Kc 7d`), 3 bet sizes, 64/32/16 buckets — 1K iterations, expected 1–3 min. **Primary target.**
  - Spot 4: HUNL flop, standard (`Js 9h 6d`), 5 bet sizes, 256/128/64 buckets — 1K iterations, expected 5–15 min. **Stretch / hard-gate target.**
- Spec §11 D12: also bench `bench_dcfr_diff_loop` (the diff-test setup at 1K iter) — most user-facing speedup metric.
- Spec §10 risk 11: bench measures **steady-state CFR iteration cost**, not end-to-end including setup. Use Criterion's `iter_with_setup` to exclude tree construction.

**2c. Reproducibility.**
- Fixed seed (spec §11 D7 = 7 for PCS RNG; same seed re-used by deterministic bench fixtures).
- Fixed Criterion config: warm-up 5 iterations, sample 20 iterations, mean ± stddev (spec §2 methodology).
- Run on `aarch64-apple-darwin` only (M-series MacBook).
- High stddev (>10% of mean per spec §10 risk 7) triggers a re-run; document stddev alongside mean in `pr_report.md`.
- `Cargo.toml` must add `criterion = "0.5"` with `default-features = false` (spec §10 risk 8 — minimize transitive-crate count).

**2d. MCS / PCS variants.** Spec is light here. PR 8 spec §2 bench table shows only 4 spots, all in the **full-enumeration** path. The PCS-on variants of spots 3 and 4 are not explicit bench rows in §2. **Suggested addition:** Agent B's `cfr_bench.rs` should add `spot3_pcs` and `spot4_pcs` as parameterized variants (`HUNLConfig.use_pcs=True`, β=0.5) so the speedup-from-PCS portion is separately measurable from the SIMD+layout contribution. Spec §11 D12 hints at this but doesn't lock it; Agent B should add it for honest accounting of the three optimizations' contributions.

---

## 3. Test-fixture overlap with PR 5

**Existing PR 5 fixtures** (`/Users/ashen/Desktop/poker_solver/tests/fixtures/hunl_solve_fixtures.py`):

| Fixture | Board | Bet sizes | Stacks | Buckets | Notes |
|---|---|---|---|---|---|
| `river_subgame_config()` | As 7c 2d Kh 5s | (PR 3 default) | 1000 | None (lossless) | River-only |
| `flop_dry_3size_config()` | As 7c 2d | (0.33, 0.75, 2.00) — **3 sizes** | 10_000 (100 BB) | (4, 2, 2) synthetic | Dry flop, 3 sizes |
| `flop_full_menu_config()` | As 7c 2d | (0.33, 0.75, 1.00, 1.50, 2.00) — **5 sizes** | 10_000 | (4, 2, 2) synthetic | Full menu + all-in |
| `monotone_flop_config()` | 8h 7h 6h | (0.33, 0.75, 2.00) — 3 sizes | 10_000 | (4, 2, 2) | Polarization gauntlet |

**Overlap potential — HIGH, but mismatches require reconciliation:**

| PR 8 bench spot | Closest PR 5 fixture | Alignment | Required adjustments |
|---|---|---|---|
| Spot 3 (simple flop, 3 sizes, **64/32/16** buckets) | `flop_dry_3size_config()` | Board ✓, sizes ✓, stacks ✓ | **Bucket shape differs** — PR 5 uses (4, 2, 2), PR 8 spec calls for **64/32/16**. Bench needs the realistic abstraction. |
| Spot 4 (standard flop, 5 sizes, **256/128/64** buckets) | `flop_full_menu_config()` | Sizes ✓ (5 sizes), stacks ✓ | **Board differs** (`Js 9h 6d` vs `As 7c 2d`); **bucket shape differs** (256/128/64 vs (4, 2, 2)). |
| Spot 1 (Kuhn) | none (no Kuhn fixture in PR 5) | n/a | Build inline; Kuhn is tiny. |
| Spot 2 (Leduc) | none (no Leduc fixture in PR 5) | n/a | Build inline; Leduc is tiny. |

**Practical reuse recommendation:**
- Agent B should `import` the `flop_dry_3size_config()` and `flop_full_menu_config()` builder shapes (via either a Python-side fixture import for the Python end-to-end bench, OR — for `cfr_bench.rs` which is pure Rust — re-implement the same `HUNLConfig` field values directly in Rust). The fixture functions are tiny config builders; the values transfer trivially.
- **Bucket counts must be the PR 8 spec values** (64/32/16 for spot 3; 256/128/64 for spot 4), not the (4, 2, 2) synthetic abstraction PR 5 uses for correctness tests. The realistic-shape benchmark exposes the cache-blocking benefit; the (4, 2, 2) shape is too small.
- The Spot 4 board (`Js 9h 6d`) and the PR 5 monotone flop (`8h 7h 6h`) are distinct; treat them as independent — do NOT swap.

**Net:** medium reuse — the config-builder PATTERN and constants (stacks, contributions, hole cards) carry over; the bucket-count parameter must be overridden per spec §2.

---

## 4. Performance-regression detection — beyond PR 8

PLAN.md §4 line 173 says "Perf check — flag regressions >10%". Spec §2 line 45 says "Subsequent PRs compare against this baseline." Currently neither is operationalized — no script enforces it.

**Proposed tiny "perf smoke" script** (NOT created by PR 8; flagged here for a PR 9+ follow-up):

- **Path:** `scripts/perf_smoke.sh` (sibling of existing `scripts/check_pr.sh`).
- **Behavior:**
  1. Read `benches/baseline.json` (mean wall-clock per spot from the PR 8 capture, or whatever the latest committed baseline is).
  2. Run `cargo bench --bench cfr_bench` on the current tip with `--quick` flag (fewer Criterion samples — accept ~5–10% noise for speed).
  3. Diff per-spot means: regression = current mean > 1.10 × baseline mean.
  4. Emit `pr_report.md` row per spot: `OK | REGRESSION (X% slower) | IMPROVEMENT (Y% faster)`.
  5. Hard gate: any spot >10% slower triggers `FAIL` in `check_pr.sh`'s output; PR cannot land without justification.
- **Lifecycle:** Each PR that changes solver hot path (PR 9 preflop, PR 12 3p, future opt PRs) runs `scripts/perf_smoke.sh` as part of `scripts/check_pr.sh`. PRs not touching solver code can skip via a `[skip-perf]` commit marker.
- **Baseline refresh policy:** the committed `benches/baseline.json` is updated only when a PR explicitly improves perf (replacing the artifact with the new lower numbers) AND the orchestrator approves the new baseline. Regressions never overwrite the baseline (otherwise the gate self-defeats).

**Recommendation:** add `perf_smoke.sh` as a PR 9 pre-flight item; PR 8 should NOT add it (PR 8 owns baseline capture; the smoke script consumes it).

**Cross-check with autonomous_log:** PR 6 / PR 7 audit reports already flag the absence of this script as a should-fix gap. PR 8 lands the baseline; PR 9 lands the gate — natural sequencing.

---

## 5. Honest assessment

**Spec coherence — strong.**

The PR 8 spec lays out baseline-first sequencing cleanly:
- §2 line 47 ("No baseline = no PR 8") is unambiguous.
- §9 #8 ("Baseline must be committed before any optimization lands") restates as a critical-correctness item.
- launch_kickoff.md §7 (baseline-first inversion) explicitly tells the orchestrator to verify Agent B's first commit is the baseline-only commit before approving subsequent refactor work.
- Agent B's deliverables (per spec §8) place baseline capture BEFORE the FlatInfosetStore refactor in the agent's internal sequencing.

**Potential gaps in the spec:**

1. **PCS-on bench variants not explicit in spec §2 table.** The 4 bench spots are all full-enumeration. Without PCS-on variants of spots 3 and 4, we cannot isolate the PCS speedup contribution from the SIMD+layout contribution. Spec §11 D12 hints at it; suggest Agent B's `cfr_bench.rs` adds `spot3_pcs` / `spot4_pcs` rows even though the spec table omits them. The hard 10× gate is on the non-PCS path (spec §1 hard gate references spot 4 standard), so this is for diagnostic-only purposes.

2. **No specified mechanism for the perf-smoke gate in later PRs.** Spec §2 line 45 implies it ("Subsequent PRs compare against this baseline") but no `scripts/perf_smoke.sh` or equivalent is owned by any PR. Flag for PR 9 owner.

3. **Bench machine-state capture is documented but not enforced.** Spec §2 methodology line: "Capture machine state: macOS version, model identifier, thermal state at run start." Agent B's `cfr_bench.rs` should include a `setup()` that writes a JSON header — but the spec is loose about HOW. Practical default: a small Rust helper that shells out `sysctl hw.model`, `sw_vers`, `pmset -g thermlog` (or fail-soft if unavailable) before running benches.

4. **Reproducibility seed for the iteration RNG (non-PCS path).** The non-PCS DCFR walker uses no RNG per spec, but if PR 6 introduced any sampling for tree construction or hand-pair iteration order, the bench must seed that for run-to-run reproducibility. Spec §2 methodology does not call this out; Agent B should verify (likely a non-issue, but worth a check).

**Verdict — green light with two notes for Agent B:**
- Baseline-first sequencing is well-specified; the orchestrator and audit prompt both enforce it. No spec change required.
- Spec is honest about the 10× hard gate being on the non-PCS path; the post-integration step §8 makes this clear.

**No changes to existing files required for PR 8 to launch.** Scaffolding is at zero, but spec §6 owns the creation; the absence is by design.

---

## Appendix: paths referenced

- `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/pr8_spec.md` (canonical spec)
- `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/launch_kickoff.md` (pre-staged playbook)
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/Cargo.toml` (current dev-deps; no criterion)
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/tests/{hunl_state_unit.rs, test_hunl_rust.rs}` (PR 6 correctness tests; no bench scaffolding)
- `/Users/ashen/Desktop/poker_solver/tests/fixtures/hunl_solve_fixtures.py` (PR 5 fixture builders — partial reuse for bench config shapes)
- `/Users/ashen/Desktop/poker_solver/scripts/check_pr.sh` (existing check battery; perf-smoke would slot into it)
- `/Users/ashen/Desktop/poker_solver/PLAN.md` §4 line 173 ("Perf check — flag regressions >10%")
