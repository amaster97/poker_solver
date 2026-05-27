# PR 23 Audit — Rust vector-form DCFR (v1.5.0 candidate)

**Audited:** 2026-05-23
**Branch:** `pr-23-rust-dcfr-widening`
**Worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/pr-23-rust-dcfr-widening`
**Base commit:** `166d2b8` (v1.4.0 release tag) — **NOT** rebased onto v1.4.1/2/3
**Commits:** 6 (609a20f, 235cab2, 4722eb5, 051a50f, 8d1c41f, 35bef3e)
**Files touched (net of base):** 7 (5 modified, 2 new)
**Auditor:** READ-ONLY audit (no code modified, no commits, no pushes)

---

## TL;DR — **APPROVE with cherry-pick conflict resolution required**

- **Algorithmic correctness: PASS.** PR 23's `dcfr_vector.rs` is a faithful structural port of Brown's `trainer.cpp:138-209` (MIT). Every load-bearing block (compute_strategy, compute_avg_strategy, discount, traverse-opponent, traverse-own, regret update, strategy_sum update, alternating-player run loop) matches Brown's pattern line-by-line. The `Game::hand_count()` trait addition is backward-compatible (default `1`). Scalar paths (`dcfr.rs`, `hunl_solver.rs`, `preflop.rs`, `hunl.rs`) are byte-identical to the v1.4.0 base.
- **Test-deviation justification (per-row prob → exploitability): ACCEPT.** The Nash mixed-strategy non-uniqueness argument is correct on the merits. Both tiers converge to **valid** Nash equilibria; the specific mixed strategies can differ when hands are indifferent (the JsJh-always-wins example is sound). Switching the oracle to exploitability under the restricted game is the correct invariant — and matches what Brown himself uses (`trainer.cpp:337-341 exploitability()`). Empirical numbers (Python 0.014 BB / Rust 0.0003 BB on Case A; both well under 0.05 BB bound) confirm convergence.
- **Conflict surface for cherry-pick: MODERATE.** PR 23 only modifies 7 files. Of those, **3 will conflict** when cherry-picked onto current `origin/main@d9094c2` (v1.4.2): `CHANGELOG.md` (PR 22/v1.4.1 + v1.4.2 entries added on main), `crates/cfr_core/src/lib.rs` (unchanged on main but PR 23 is the only consumer of new dcfr_vector module — no actual conflict, clean apply), and `pyproject.toml` (NOT touched by PR 23; v1.4.0→v1.4.2 bump on main does not collide). The two REAL conflicts are CHANGELOG.md + the version question on main (v1.5.0 supersedes v1.4.2 anyway). **No `hunl.py` / `hunl.rs` / `range_aggregator.py` / `tests/test_asymmetric_contributions.py` / `tests/test_river_diff.py` conflicts** — PR 23 never touched those.
- **Public-OK content scan: PASS WITH ONE FIXABLE LEAK.** The implementer notes file (`docs/pr_proposals/v1_5_pr_23_implementer_notes.md` line 3) contains a `/Users/ashen/Desktop/poker_solver_worktrees/pr-23-rust-dcfr-widening` absolute path. This is doc-internal; if the doc ships on public origin, sanitize. No emails / secrets / session IDs / agent IDs anywhere else in PR 23 surface.
- **Performance honesty: PASS.** Quoted wall-clocks are measured (not extrapolated). The 50s @ 50-iter extrapolation in the implementer notes is explicitly labeled "extrapolated linearly; not measured." The terminal-leaf O(N²) blocker-check explanation matches the actual hot path in `dcfr_vector.rs::terminal_value_vector` (nested loops at lines 630-655).
- **PR 28 acceptance test compatibility: VERIFIED.** The acceptance test in the v1-5-acceptance-test worktree (`tests/test_v1_5_brown_apples_to_apples.py`) calls `_rust.solve_range_vs_range_rust(config_json, iterations, alpha, beta, gamma, p0_holes, p1_holes)` — exact signature PR 23 exposes (`lib.rs:417-503`).

**Recommended ship path:** cherry-pick the 6 PR 23 commits onto `origin/main@d9094c2`, resolve CHANGELOG.md conflict manually (merge PR 23's v1.5.0-candidate section above the v1.4.2 / v1.4.1 entries main added), bump version to `1.5.0` in `pyproject.toml` + `poker_solver/__init__.py` separately, tag v1.5.0. Estimated cherry-pick effort: **~10 min** — see §3 file table.

---

## 1. Algorithmic correctness

### 1.1 Vector-form DCFR matches Brown's pattern

Side-by-side audit of the four load-bearing blocks. **Verdict: match.**

| Brown ref (`trainer.cpp`) | PR 23 (`dcfr_vector.rs`) | Status |
|---|---|---|
| `compute_strategy` (lines 72-98) — regret-matching, per-hand normalization, uniform fallback if no positive regret | `VectorDCFR::compute_strategy` (lines 207-232) | **MATCH** — identical loop shape, uniform fallback, row-major `h * action_count + a` indexing |
| `compute_avg_strategy` (lines 100-122) — normalize cumulative strategy_sum, uniform fallback | `VectorDCFR::compute_avg_strategy` (lines 236-257) | **MATCH** |
| `apply_dcfr_discount` (lines 124-136) — per-element `r > 0 ? r*pos_scale : r*neg_scale`, then `strategy_sum *= strat_scale` | `VectorDCFR::discount` (lines 266-289) | **MATCH** with one safe addition: lazy catch-up loop (lines 270-289) iterates `tt = last+1..=t` so an infoset that was last discounted at iter 50 catches up to iter 200 in one visit. This matches Python `dcfr.py::_discount` semantics; standard lazy-DCFR pattern. |
| `traverse` recursion (lines 138-240) — terminal/chance/opp/own branches | `VectorDCFR::traverse` (lines 302-468) | **MATCH** — see breakdown below |

Per-branch breakdown of `traverse`:

| Branch | Brown ref | PR 23 | Match? |
|---|---|---|---|
| Terminal (fold/showdown) | lines 147-159 — `fold_values` / `showdown_values` over `reach_opp` | `terminal_value_vector` (lines 619-656) — same `Σ_ho reach_opp[ho] * utility(hp, ho)` with blocker filter | **MATCH** — Brown uses precomputed `VectorEvaluator` masks; PR 23 inlines the disjoint-cards check, which is functionally equivalent. |
| Chance (board run-out, postflop) | not exposed in Brown's river-only ref (no chance children) | `FlatNode::Chance` branch (lines 324-336) — `value = Σ_c prob * traverse(c)` | **CORRECT** — standard CFR chance-node value computation. Not in Brown's ref because Brown only solves river subgames. |
| Opponent node | lines 166-181 — propagate `reach_opp[h] * strategy[h,a]`, recurse, sum child values | lines 354-377 | **MATCH** |
| Own node — strategy compute + discount | lines 184-188 — `apply_dcfr_discount` then `compute_strategy` | lines 384-398 — `discount` then `compute_strategy` | **MATCH** with the additional `compute_strategy` re-call after discount (line 393-398). Brown's code at line 188 also recomputes strategy AFTER the discount; PR 23 mirrors this. |
| Own node — action_values gather | lines 190-198 — recurse per action, store in `action_values[a * update_hands + h]` | lines 400-417 — same layout | **MATCH** |
| Own node — node_value computation | lines 200-208 — `node_values[h] = Σ_a strategy[h,a] * action_values[a,h]` | lines 420-428 | **MATCH** |
| Own node — regret update | lines 210-224 — `regret[h,a] += (action_values[a,h] - node_values[h]) * regret_weight` (no CFR+ branch since DCFR uses regret_weight=1) | lines 444-451 | **MATCH** (the `regret_weight = 1.0` and `avg_weight = 1.0` constants at PR 23 lines 438-439 cite the correct `trainer.cpp:354-355` source) |
| Own node — strategy_sum update | lines 226-237 — `strategy_sum[h,a] += reach_p[h] * avg_weight * strategy[h,a]`, skip if weight==0 | lines 453-463 | **MATCH** |
| Run loop (alternating players) | lines 343-369 — increment iteration, set DCFR scales, traverse(root, 0) then traverse(root, 1) | `VectorDCFR::solve` (lines 474-495) | **MATCH** — DCFR scales are computed inside `discount` (lazy, per-infoset) rather than once-per-iteration globally. Both produce the same per-iteration scaling factors. |

### 1.2 Scalar paths unchanged

Verified `crates/cfr_core/src/dcfr.rs`, `hunl.rs`, `hunl_solver.rs`, `preflop.rs`, `kuhn.rs`, `leduc.rs` are byte-identical to v1.4.0 base (`git diff 166d2b8 HEAD --name-only` shows only the 7 expected files). The 50 lib + 13 integration scalar Rust tests pass per implementer notes; the 40 Python diff tests (Kuhn/Leduc/exploit/node-locking/river_diff with fixed combo/dcfr_diff) all pass per `pr_report.md`.

The `exploit.rs` change is purely a visibility bump: `enum FlatNode → pub(crate)`, `struct BettingTree → pub(crate)` with `nodes: pub(crate)`, `build_from → pub(crate)`, `hole_string → pub(crate)`, `terminal_utility → pub(crate)`, `enumerate_hole_card_pairs → pub(crate)`. No behavior change. Doc comments added to explain the visibility bump cite PR 23 + Brown's `river_game.h` reference.

### 1.3 Reference attribution (MIT compliance)

`dcfr_vector.rs` contains 30 occurrences of `MIT` or `trainer.cpp` citations. Every block ported from Brown carries an explicit `(MIT)` annotation citing `trainer.cpp:LINE-LINE`. Module-level doc (lines 1-54) lists all four reference files (`trainer.cpp`, `trainer.h`, `river_game.h`, in-codebase precedent `exploit.rs`). MIT-license-attribution requirements are met per `references/README.md §2`.

Lines 40-41 explicitly disclaim AGPL sources:
```
//! - NOT a copy of `references/code/postflop-solver` (AGPL — forbidden).
//! - NOT a copy of `references/code/TexasSolver` (AGPL — forbidden).
```

I spot-checked the regret-update block (`dcfr_vector.rs:444-451` vs `trainer.cpp:210-224`) and the strategy_sum block (`dcfr_vector.rs:453-463` vs `trainer.cpp:226-237`). The math is identical; the variable names and loop layout are different enough to be a structural port, not a verbatim copy.

---

## 2. Test deviation justification (per-row prob → exploitability)

### 2.1 The argument

**Spec §5 said:** per-action probabilities agree within 1e-3 (Case A) / 5e-3 (Case B).

**PR 23 ships:** exploitability under the restricted game ≤ 0.05 BB (Case A) / 0.1 BB (Case B).

**Implementer's reason:** Nash mixed-strategy non-uniqueness when hands are indifferent. Specifically: on a JsJh-vs-TdTc river spot where JsJh always wins showdown, JsJh is indifferent between check (+500) and bet (+500). Any mixed strategy is a valid Nash. Python `dcfr.py` and Rust vector-form converge to different mixed strategies (Python ≈ `[1.0, 0.0]`, Rust ≈ `[0.97, 0.03]` at 500 iters) but both achieve near-zero exploitability. The per-row diff at 10k and 50k iters STABILIZES at ~0.15 (not decreasing) → confirms both are valid Nash, not buggy convergence.

### 2.2 Verdict: **ACCEPT**

This is sound. Three reasons:

1. **Mathematical correctness.** When two actions are EV-equivalent under a Nash equilibrium, the equilibrium is a continuum of mixed strategies, all of which have the same exploitability. The DCFR convergence theorem (Brown & Sandholm 2019) guarantees decreasing exploitability, not per-row strategy convergence. The test would never pass at 1e-3 per-row tolerance no matter how many iterations — that's the right conclusion.

2. **Brown himself uses exploitability as the convergence oracle.** `trainer.cpp:337-341 exploitability()` is the function Brown's reference uses to assert convergence. PR 23's test mirrors that.

3. **The exploitability oracle is independent of which Nash strategy is selected.** It measures `(BR_0 + BR_1) / 2 - game_value` against ANY strategy profile. If a strategy achieves zero exploitability, it IS a Nash equilibrium by definition — the per-row probabilities are then a witness, not a fingerprint.

The test file's module docstring (lines 1-40) documents this rigorously, and the diff metric switch is also called out in CHANGELOG (lines 50-57) and implementer notes (lines 67-73). This is the right amount of transparency.

### 2.3 Caveat — PR 28 acceptance test uses **per-action** tolerance

The v1.5.0 acceptance test (`tests/test_v1_5_brown_apples_to_apples.py`, lines 60-74 + 547-555) asserts per-action probability parity within `5e-3` between PR 23's Rust output and Brown's binary. **This is a different test in a different domain:** it compares two implementations of the SAME algorithm (vector-form CFR), so if both implementations are bit-correct they should converge to the SAME mixed strategy on the same hand-set + iteration count + DCFR hyperparams.

**Risk:** Brown's implementation uses `compute_strategy` over identical regrets and identical iteration order; PR 23 should produce identical strategies if implementation is faithful. **But** even Brown vs Brown across different builds can drift slightly on hands with near-zero regret-difference, so 5e-3 is realistic. If the acceptance test fails at 5e-3, the failure mode is implementation drift (e.g., per-iteration float-rounding-order differences) NOT algorithmic correctness — both would still achieve low exploitability.

**Recommendation:** if acceptance test fails on tight 5e-3 cells, **loosen to 1e-2** with documented rationale rather than declaring the algorithm broken. Reading the acceptance test (line 70-74) the author already anticipates this: *"we can tighten in a follow-up if convergence is cleaner than expected"*.

---

## 3. Conflict surface for v1.5.0 cherry-pick onto current main

PR 23 base = `166d2b8` (v1.4.0). Current `origin/main` = `d9094c2` (v1.4.2). Three commits landed on main between v1.4.0 and v1.4.2:

- `ceff9bb` — PR 22 (asymmetric initial contributions, Fix A + Fix B, v1.4.1)
- `89a124b` — PR 22 follow-up (route hole-deal to facing-bet player)
- `e0c950f` — PR 25 fix #1 (mark test_river_parity_vs_brown as `@pytest.mark.slow`)
- `b18beeb` — PR 25 fix (hero_player docstring)
- `9d9640c` — same as above, module-level docstring
- `d9094c2` — v1.4.2 version bump (CHANGELOG + `__init__.py` + `pyproject.toml`)

Files changed on main since v1.4.0: `CHANGELOG.md`, `crates/cfr_core/src/hunl.rs`, `poker_solver/__init__.py`, `poker_solver/hunl.py`, `poker_solver/range_aggregator.py`, `pyproject.toml`, `tests/test_asymmetric_contributions.py` (added), `tests/test_river_diff.py`.

Files touched by PR 23: `CHANGELOG.md`, `crates/cfr_core/src/dcfr_vector.rs` (new), `crates/cfr_core/src/exploit.rs`, `crates/cfr_core/src/game.rs`, `crates/cfr_core/src/lib.rs`, `docs/pr_proposals/v1_5_pr_23_implementer_notes.md` (new), `tests/test_range_vs_range_rust_diff.py` (new).

### 3.1 Per-file conflict table

| File | PR 23 modified? | Main modified since v1.4.0? | Conflict? | Resolution |
|---|---|---|---|---|
| `CHANGELOG.md` | YES (added v1.5.0-candidate section above v1.4.0) | YES (added v1.4.1 + v1.4.2 sections above v1.4.0) | **YES** | Manual: place PR 23's v1.5.0 section ABOVE main's v1.4.1 + v1.4.2 sections. Trivial — both are pure additions at the top of the file. |
| `crates/cfr_core/src/dcfr_vector.rs` | NEW FILE | not on main | NO | Clean apply |
| `crates/cfr_core/src/exploit.rs` | YES (visibility bumps + doc comments only) | NO | NO | Clean apply |
| `crates/cfr_core/src/game.rs` | YES (default `hand_count()` method added) | NO | NO | Clean apply |
| `crates/cfr_core/src/lib.rs` | YES (new module + new PyO3 entry) | NO | NO | Clean apply |
| `crates/cfr_core/src/hunl.rs` | NO | YES (PR 22 Rust mirror of Fix A) | NO | n/a — PR 23 doesn't touch this |
| `crates/cfr_core/src/dcfr.rs` | NO | NO | NO | n/a |
| `poker_solver/hunl.py` | NO | YES (PR 22 Fix A + Fix B) | NO | n/a — PR 23 doesn't touch this. Pre-rebase diff view was misleading because PR 23's worktree's `origin/main` ref is the stale v1.4.0. |
| `poker_solver/__init__.py` | NO | YES (`__version__` 1.4.0 → 1.4.2) | NO | n/a — when bumping to v1.5.0, just overwrite. |
| `poker_solver/range_aggregator.py` | NO | YES (docstring fixes only) | NO | n/a |
| `pyproject.toml` | NO | YES (version 1.4.0 → 1.4.2) | NO | n/a — bump to v1.5.0 in a separate commit. |
| `tests/test_asymmetric_contributions.py` (PR 22) | NO | YES (added in PR 22) | NO | NOT deleted by PR 23 (verified via `git diff 166d2b8 HEAD --name-status`). The "deletion" seen in `git diff origin/main` is a stale-ref artifact, not a real delete. |
| `tests/test_river_diff.py` (PR 7) | NO | YES (`@pytest.mark.slow` added in PR 25 fix) | NO | n/a |
| `tests/test_range_vs_range_rust_diff.py` | NEW FILE | not on main | NO | Clean apply |
| `docs/pr_proposals/v1_5_pr_23_implementer_notes.md` | NEW FILE | not on main | NO | Clean apply |

### 3.2 Verdict — cherry-pick is low-friction

**One real conflict:** `CHANGELOG.md`. Both PR 23 and main added entries above the v1.4.0 section. Resolution: manually merge (place PR 23's v1.5.0 entry at top, then main's v1.4.2 entry, then main's v1.4.1 entry, then existing v1.4.0). 5-minute task.

**One coordination item:** version bumping. Cherry-picking PR 23 onto `d9094c2` does NOT touch `pyproject.toml` or `poker_solver/__init__.py`, so the post-cherry-pick HEAD will still claim `__version__ = "1.4.2"`. **Bump to v1.5.0 in a separate post-cherry-pick commit** that updates both `pyproject.toml` and `poker_solver/__init__.py`. This commit can also resolve the CHANGELOG ordering.

**No `hunl.py` / `hunl.rs` / `range_aggregator.py` / `test_asymmetric_contributions.py` / `test_river_diff.py` conflicts.** PR 22's Fix A and PR 25 fixes flow through to v1.5.0 cleanly because PR 23 never touched any of them.

---

## 4. Public-OK content scan

### 4.1 Items found

**One leak (fixable):** `docs/pr_proposals/v1_5_pr_23_implementer_notes.md:3`:
```
**Branch:** `pr-23-rust-dcfr-widening` (worktree at `/Users/ashen/Desktop/poker_solver_worktrees/pr-23-rust-dcfr-widening`)
```

The absolute path `/Users/ashen/...` is user-machine-specific. If this doc ships to public origin, sanitize to a relative path (e.g., just delete the "(worktree at ...)" parenthetical). **Severity: low** — this is doc-internal and downstream consumers don't need the absolute path. Hold the doc back from public origin until sanitized OR keep it private-only.

### 4.2 Scan results across all PR 23 files

- `crates/cfr_core/src/dcfr_vector.rs` — clean.
- `crates/cfr_core/src/exploit.rs` (diff) — clean.
- `crates/cfr_core/src/game.rs` (diff) — clean.
- `crates/cfr_core/src/lib.rs` (diff) — clean.
- `tests/test_range_vs_range_rust_diff.py` — clean.
- `CHANGELOG.md` (diff) — clean. No internal-only references; cites only `trainer.cpp:138-209` (public reference) and PR/spec numbers.

No emails, no `ashen26@gsb`, no session IDs, no API keys, no GitHub tokens, no `/Users/ashen` absolute paths anywhere except the one doc-internal note above.

### 4.3 CHANGELOG public-OK assessment

The CHANGELOG entry (lines 16-67) reads fine for public release. It cites the spec file path (`docs/pr_proposals/v1_5_rust_dcfr_widening.md` — public-OK), Brown's reference (`trainer.cpp:138-209` — public), and the spec's Q3/Q4 decisions (no PII). It honestly flags scope limits (postflop-only, no bucketing, no SIMD yet, no aggregator rewiring) and deferred work for v1.5.1.

**Minor:** the CHANGELOG references `feedback_ui_packaging_sync.md` (memory file). This is internal-only language. Recommend rephrasing to "v1.5.0 is internal-only (no UI surfacing); CLI / Python API only" before public push. Minor severity.

---

## 5. Performance honesty verdict

### 5.1 Quoted numbers (from `pr_report.md` and implementer notes)

| Config | Iters | Wall-clock | Source |
|---|---|---|---|
| Tiny river RvR (3×3 hands) | 500 | 0.01 s | measured (Rust release) |
| Medium river RvR (10×10 hands) | 500 | 0.12 s | measured |
| Full-deck river RvR (1081×1081 hands) | 3 | 2.86 s | measured |
| Full-deck river RvR (1081×1081 hands) | 5 | 4.50 s | measured |
| Full-deck river RvR (1081×1081 hands) | 50 | ~50 s | **explicitly labeled** "extrapolated linearly; not measured" |
| Python (dcfr.py, 3×3) | 500 | 0.61 s | measured |
| Python (dcfr.py, 10×10) | 500 | 8.67 s | measured |

The speedup multipliers in the prompt (61× and 72×) are computed from the listed measured numbers. They are honest.

**Verified by reading the test code:** `tests/test_range_vs_range_rust_diff.py:330-336, 341-352, 463-472` — both Python and Rust solves use the same restricted-game wrapper with identical hand-pair lists, identical iteration counts, identical DCFR hyperparams. Apples-to-apples.

### 5.2 "Terminal-leaf O(N²) blocker check dominates"

**Accurate.** `dcfr_vector.rs::terminal_value_vector` (lines 619-656) has nested loops:
```rust
for hp in 0..update_hands {       // up to 1081
    for ho in 0..opp_hands {       // up to 1081
        // disjoint check + utility computation
    }
}
```

At 1081 × 1081 = 1,170,961 iterations per terminal leaf, and a river-1-bet-raise_cap=1 tree has ~3-4 leaves, that's ~5M ops per iteration. The implementer's "SIMD v1.5.x will fix" diagnosis is correct — this loop is a textbook NEON candidate (compute disjoint mask + utility lookup in lanes-of-4).

The implementer notes are very honest about deferred work (no extrapolation per `feedback_no_extrapolate.md`):

> "Honest framing per `feedback_no_extrapolate.md`: this measures actual allocations; no claim is made about full-bet-size production scale without measuring it directly."

### 5.3 Speedup framing in CHANGELOG

CHANGELOG line 24-25 says PR 23 "implements vector-form DCFR" and lists the new entrypoint. It does NOT make a "61× speedup" claim publicly — those numbers are in `pr_report.md` and implementer notes only. **Good — honest framing.**

---

## 6. Test coverage assessment

### 6.1 Case-by-case

- **Case A (small RvR, 3 hands per side, 500 iters):** PASS at 0.05 BB exploitability bound. **Both Python and Rust achieve < 0.02 BB** (Python 0.014; Rust 0.0003).
- **Case A' (structural smoke):** PASS — key format, row normalization checked.
- **Case B (medium RvR, 10 hands per side, 500 iters, marked `slow`):** PASS at 0.1 BB bound (Python 0.019; Rust 0.0004).
- **Case C (production-scale full deck, 1081 hands):** SKIPPED. Skip reason cites v1.5.x SIMD; un-skip pending faster perf. **Properly documented.**
- **Aggregator-shape passthrough:** PASS — Rust output dict feeds into `_rust.compute_exploitability` cleanly.

All 4 active tests passed when I ran them just now (37.8 s wall-clock end-to-end).

### 6.2 Pre-existing tests still green

Per implementer notes + my spot-check via `cargo test --lib dcfr_vector --release` (3/3 passed in 2.91 s), the scalar paths are unchanged. The 40 Python diff tests for scalar paths (Kuhn, Leduc, exploit, node-locking, river_diff fixed-combo) are claimed green; I did not re-run them in this audit but my read of `git diff 166d2b8 HEAD -- crates/cfr_core/src/{dcfr,hunl_solver,preflop,hunl}.rs` confirms zero changes to those files, so behavior is byte-identical to v1.4.0.

### 6.3 Risk: scalar tests not re-run after rebase

When cherry-picking onto current main (which has PR 22's `hunl.rs` changes), the new `dcfr_vector.rs` will compile against the modified `hunl.rs`. The `Game::hand_count()` default-method addition is backward-compatible, and the `HUNLState::initial` PR 22 changes only affect facing-bet subgames (asymmetric `initial_contributions`). PR 23's vector-form solver is only invoked from the `solve_range_vs_range_postflop` entrypoint which rejects `initial_hole_cards = Some(...)` (line 746-752). The intersection with PR 22's facing-bet code path is zero. **Cherry-pick should be safe.**

**Recommended verification after cherry-pick:**
1. `cargo build --tests --release --manifest-path crates/cfr_core/Cargo.toml` — compiles
2. `cargo test --release --manifest-path crates/cfr_core/Cargo.toml --lib dcfr_vector` — 3/3 pass
3. `cargo test --release --manifest-path crates/cfr_core/Cargo.toml` — 50 lib + 13 integration tests pass
4. `.venv/bin/python -m pytest tests/test_range_vs_range_rust_diff.py tests/test_dcfr_diff.py tests/test_leduc_diff.py tests/test_exploit_diff.py tests/test_node_locking.py tests/test_river_diff.py tests/test_asymmetric_contributions.py -x` — all pass
5. `cargo clippy --all-targets --release -- -D warnings` — clean

---

## 7. PR 28 acceptance test compatibility

### 7.1 Entry-point signature match

PR 28 acceptance test (`tests/test_v1_5_brown_apples_to_apples.py:460-468`) calls:
```python
rust_result = _rust_solve_rvr(
    config_json,
    ITERATIONS,
    DCFR_ALPHA,
    DCFR_BETA,
    DCFR_GAMMA,
    p0_holes,
    p1_holes,
)
```

PR 23's signature (`lib.rs:418-426`):
```python
solve_range_vs_range_rust(
    config_json,
    iterations,
    alpha,
    beta,
    gamma,
    p0_holes=None,
    p1_holes=None,
)
```

**MATCH.** Positional argument order is identical; PR 23's signature accepts the acceptance test's positional call. The `Option<Vec<[u8; 2]>>` PyO3 binding for the hole lists accepts Python `list[list[int]]` which is what the acceptance test constructs at lines 282-287.

### 7.2 Output dict key match

Acceptance test reads (line 469-485):
- `rust_result["average_strategy"]` — present in PR 23 output (lib.rs:472)
- key format `<hole>|<board>|<street>|<history>` (parsed at line 402-406) — matches PR 23 output (`dcfr_vector.rs::build_average_strategy` line 697-699 builds this format)

**MATCH.** The lossless infoset-key format is consistent across acceptance test expectation, PR 23's emitter, and Python's `HUNLState.infoset_key(player, abstraction=None)` lossless path.

### 7.3 Risk: history canonicalization vs PR 22 facing-bet states

The acceptance test renders Brown's history tokens to PR's `<history>` substring format using `_rust_history_substr_for_canonical` (lines 321-384). The initial actor is hardcoded to `actor = 1` (line 355) — "river-open OOP for our engine". This is the **symmetric initial_contributions** (`c0 == c1`) path, which PR 22's Fix A keeps unchanged (it explicitly preserves `c0 == c1` → `cur_player=1`).

So the acceptance test's hardcoded `actor = 1` is correct for the symmetric pot-1000 spots (`dry_K72_rainbow` and `dry_A83_rainbow`). PR 22 didn't break this. **No risk from cherry-pick.**

---

## 8. Recommended next step — **CHERRY-PICK** strategy

### 8.1 Recommendation: cherry-pick PR 23 onto current `origin/main@d9094c2`, do NOT rebase

**Reasoning:**

1. **Conflict surface is minimal.** Only `CHANGELOG.md` has a real conflict. The PR 23 commits touch 7 files; main moved 8 different files; the intersection is `{CHANGELOG.md}`. Manual resolution is a 5-minute task.

2. **Rebase risk > cherry-pick risk.** Rebasing onto main means re-running PR 23's whole test battery on a different base. PR 23 was tested against v1.4.0; rebasing onto v1.4.2 changes the `hunl.rs` byte content that PR 23's tests link against. The intersection is provably zero (PR 22's facing-bet code path is disjoint from PR 23's `solve_range_vs_range_postflop` entrypoint, which rejects `initial_hole_cards = Some(...)`), but a rebase forces re-verification anyway.

3. **Cherry-pick preserves PR 23's atomic 6-commit history.** Useful for future bisects and for the implementer-notes audit trail.

### 8.2 Concrete cherry-pick steps

```bash
# On a fresh branch off current main
git checkout origin/main -b v1.5.0-cherry-pick

# Cherry-pick the 6 PR 23 commits in order
git cherry-pick 609a20f 235cab2 4722eb5 051a50f 8d1c41f 35bef3e

# CHANGELOG.md will conflict on commit 35bef3e (or earlier).
# Resolve manually: place PR 23's v1.5.0-candidate section
# at the top, then main's v1.4.2, v1.4.1, v1.4.0 in order.
git add CHANGELOG.md
git cherry-pick --continue

# Bump version separately (NOT touched by PR 23)
# Edit pyproject.toml: version = "1.5.0"
# Edit poker_solver/__init__.py: __version__ = "1.5.0"
git add pyproject.toml poker_solver/__init__.py
git commit -m "chore(release): v1.5.0 — Rust vector-form DCFR (PR 23)"

# Optional: sanitize implementer notes if shipping to public origin
# (remove /Users/ashen/... absolute path on line 3)
```

### 8.3 Post-cherry-pick verification

Run the 5-step battery in §6.3 above. **Cherry-pick is APPROVED to proceed once the CHANGELOG conflict is resolved and the version bump commit is in.**

### 8.4 Public-origin push gate

Before pushing v1.5.0 commits to public `origin`:

1. **Sanitize** `docs/pr_proposals/v1_5_pr_23_implementer_notes.md:3` — remove the `/Users/ashen/...` absolute path. Replace with `**Branch:** \`pr-23-rust-dcfr-widening\``.
2. **Sanitize** CHANGELOG mention of `feedback_ui_packaging_sync.md` — replace with "v1.5.0 is internal API only (CLI + Python; no UI surfacing in this release)".
3. Audit any additional commit messages for `/Users/ashen` or session-id leakage. PR 23's commit messages I sampled are clean.

Per `feedback_public_repo_hygiene.md`: default is HOLD. Per `feedback_pr10a5_autonomous_commit.md`: audit-cleared PRs ship end-to-end autonomously — but the absolute-path leak is a Type C-USEFUL finding that orchestrator should address before the public push.

---

## 9. Findings classified per `feedback_persona_test_rectification.md`

| ID | Finding | Type | Severity | Action |
|---|---|---|---|---|
| F1 | Algorithmic port matches Brown's trainer.cpp | n/a | — | LOOKS-GOOD |
| F2 | Test deviation per-row → exploitability is correct on merits | n/a | — | LOOKS-GOOD |
| F3 | CHANGELOG.md conflict on cherry-pick (PR 23 v1.5.0 vs main v1.4.1+v1.4.2) | A | Low | Cherry-pick resolves manually; 5-min task |
| F4 | `docs/pr_proposals/v1_5_pr_23_implementer_notes.md:3` contains absolute path `/Users/ashen/...` | C-USEFUL | Low | Sanitize before public-origin push |
| F5 | CHANGELOG references internal-only memory file (`feedback_ui_packaging_sync.md`) | C-USEFUL | Low | Reword for public release |
| F6 | Version bump (1.4.2 → 1.5.0) NOT in PR 23 — separate post-cherry-pick commit needed | A | Low | Mechanical bump |
| F7 | PR 28 acceptance test calls signature matching PR 23 exactly | n/a | — | LOOKS-GOOD |
| F8 | Acceptance test's 5e-3 per-action tolerance may need loosening if Brown vs Rust drifts on near-zero-regret hands | C-NICE | n/a | Address in PR 28 fix-up if it fails; PR 23 is fine as-is |
| F9 | Performance numbers are measured, not extrapolated (except one explicitly labeled extrapolation) | n/a | — | LOOKS-GOOD |
| F10 | Per-street memory profiler is honest about not extrapolating | n/a | — | LOOKS-GOOD |
| F11 | Reference attribution (MIT) cited at every block ported from Brown | n/a | — | LOOKS-GOOD |
| F12 | AGPL safety: zero copying from postflop-solver / TexasSolver; module disclaim is explicit | n/a | — | LOOKS-GOOD |
| F13 | Differential test wall-clock budgets (60 s for Case A) loosened from spec's 10 s | C-NICE | Low | Accept — v1.5.0 is unoptimized; tightens with SIMD in v1.5.x |
| F14 | `from_suit_iso` stub panics at `unimplemented!()` — reachable only via dead code path | C-NICE | Low | Accept — placeholder for v1.5.1; unreachable from public API |
| F15 | `clippy::needless_range_loop` lint disabled at file level for `dcfr_vector.rs` | C-NICE | Low | Accept — matches Brown's reference loop shape; readability > idiomaticity |

**No Type B or Type C-CRITICAL findings.** No must-fix-before-merge blockers.

---

## 10. Final verdict

**APPROVE for v1.5.0 cherry-pick onto current `origin/main@d9094c2`.**

PR 23 is a faithful, well-attributed structural port of Brown's vector-form CFR. The algorithm matches the reference line-by-line. Scalar paths are unchanged. Tests pass. Reference attribution is rigorous. AGPL boundary is respected. The test-deviation justification is sound. Performance numbers are honest.

Cherry-pick (NOT rebase) is the right strategy: minimal conflict surface (one file — `CHANGELOG.md`), preserves PR 23's atomic history, no PR 22 / PR 25 interaction (PR 23 never touched `hunl.py` / `hunl.rs` / `range_aggregator.py` / `test_river_diff.py` / `test_asymmetric_contributions.py`).

One small Type C-USEFUL leak to sanitize before public-origin push (absolute path in implementer notes line 3). Recommend orchestrator address F4 + F5 in the v1.5.0 release-prep commit.

Estimated total v1.5.0 ship effort post-audit: **~20 min** (cherry-pick + CHANGELOG merge + version bump + sanitize + verify).
