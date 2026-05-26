# RCA — `HUNLState::chance_outcomes()` empty-when-no-hole-cards

**Date:** 2026-05-26
**Author:** investigation agent (read-only)
**Trigger:** Track A analysis (agent `aaf54c9`) in `docs/a83_track_a_results_analysis_2026-05-26.md` §2c flagged this as the mechanical cause of the 186-byte identical Track A nohup outputs.

---

## 1. The contract (code citations)

`/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/hunl.rs:530-568`

```rust
/// Uniform-over-remaining chance outcomes for board cards. Empty when
/// not a chance node. Mirrors `HUNLPoker.chance_outcomes` postflop path
/// (preflop hole-deal path is PR 9 / out of scope per file-level note).
pub fn chance_outcomes(&self) -> Vec<(u8, f64)> {
    if self.cur_player != -1 || self.is_terminal() {
        return Vec::new();
    }
    // PR 6 is postflop-only — hole cards must already be dealt. Build the
    // remaining-deck set per `_board_card_outcomes`.
    let hole = match self.hole_cards {
        Some(h) => h,
        None => {
            // Defensive: shouldn't happen post-init. Return empty rather
            // than enumerate preflop combinations (which don't fit in u8).
            return Vec::new();
        }
    };
    // ... build remaining-deck uniform distribution
}
```

The docstring states the intent: "PR 6 is postflop-only — hole cards must already be dealt." The `None` branch is labeled "Defensive: shouldn't happen post-init." The intent is that `chance_outcomes()` is **never** called on a state with `hole_cards = None` — but it is, via the chain below.

## 2. The trigger chain

1. **CLI** at `/Users/ashen/Desktop/poker_solver/poker_solver/cli.py:98-136` — `_build_postflop_config()` constructs an `HUNLConfig` with **no** `initial_hole_cards` (the field is absent from the dataclass kwargs → defaults to `None`). There is no `--initial-hole-cards` CLI flag at all.

2. **Rust scalar entrypoint** at `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/hunl_solver.rs:475-563` — `solve_hunl_postflop()` calls `validate_config()` (L488), which checks street + board length + rake but **never** checks `initial_hole_cards`. Then `HUNLState::initial(config_arc)` at L537.

3. **`HUNLState::initial()`** at `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/hunl.rs:344-348`:
   ```rust
   let cur_player: i8 = if all_in[0] || all_in[1] || hole_cards.is_none() {
       -1
   } else {
       postflop_first_actor
   };
   ```
   With `hole_cards = None`, `cur_player = -1` → the root is a chance node.

4. **CFR loop** at `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/hunl_solver.rs:265-282`:
   ```rust
   SamplingStrategy::Full => {
       let mut value = [0.0_f64; 2];
       for (action, prob) in state.chance_outcomes() {  // empty
           // ... never executes
       }
       return value;  // [0.0, 0.0]
   }
   ```
   Iterates over the empty Vec, returns `[0.0, 0.0]` immediately. **No infoset gets inserted; `regret_init_noise` has no surface to perturb; `strategy_sum` stays empty across all 200K iters.**

5. **Output:** `solver.average_strategy()` returns an empty `HashMap`. The exploitability recompute via `_rust.compute_exploitability` walks the (mostly-empty) tree with `StrategyCache::probs` falling back to uniform at every miss → reports the exploitability of a uniform random strategy.

## 3. Hypothesis ranking

### Hypothesis A — Intended; CLI should HARD-FAIL [STRONGEST]

**Evidence supporting:**

- `chance_outcomes()`'s docstring says "Defensive: shouldn't happen post-init" — the author knew this case was reachable in principle but expected the caller to ensure it never happens.
- `dcfr_vector.rs::solve_range_vs_range_postflop_with_hands` at L806-811 **does** validate at the entry point:
  ```rust
  if config.initial_hole_cards.is_some() {
      return Err("solve_range_vs_range_postflop requires initial_hole_cards = None; \
                  use solve_hunl_postflop for fixed-combo configs".into());
  }
  ```
  This is the **inverse** check — the vector form rejects fixed combos. The scalar form was **supposed** to have the matching check ("`solve_hunl_postflop` requires `initial_hole_cards = Some(...)`") but doesn't. Asymmetric validation is a code smell consistent with an oversight.
- `BettingTree::build_node` at `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/exploit.rs:407-414` has the SAME defensive fall-through — but only after the vector form has already validated upstream + used a placeholder hole pair (L843 of `dcfr_vector.rs`). The defensive code is BELT-AND-SUSPENDERS for vector form; for the scalar form it's the only line of defense, and it's silent.
- Python's `_validate_postflop_config` at `/Users/ashen/Desktop/poker_solver/poker_solver/hunl_solver.py:229-265` also doesn't check `initial_hole_cards`. Python's `HUNLPoker.chance_outcomes` at `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py:488-493` falls into `_enumerate_preflop_hole_outcomes()` (1.66M combos) — Python would attempt the enum at postflop start with no holes, but it's not been exercised at this scale either; both tiers happen to silently break, just differently.

**Conclusion:** the scalar `solve_hunl_postflop` path is **incomplete** — its contract is "fixed-combo postflop subgame" but the precondition (`initial_hole_cards.is_some()`) is unenforced. The fix is a one-line validation.

### Hypothesis B — Should enumerate 1326 hole pairs [REJECTED]

**Evidence against:**

- The vector-form path (`dcfr_vector.rs`) already implements "enumerate hands at root" via per-player hand vectors. Adding it to the scalar form would be a re-implementation of the same thing in a less efficient shape (the scalar loop would touch every fixed-combo infoset O(1326²) times per iteration).
- The vector form is the production path for true range-vs-range Nash (PR 23, v1.5.0). The scalar form is the production path for fixed-combo postflop subgames (PR 6). They have different responsibilities; conflating them defeats the point of the split.
- The comment in `hunl.rs:541-545` ("which don't fit in u8") explicitly notes that the action space for hole-card enumeration won't fit the scalar form's `u8` action type — this is a deliberate type-system boundary, not a stub.

### Hypothesis C — Wrong entrypoint; route to RvR Nash [PARTIALLY CORRECT]

**Evidence supporting:**

- True range-vs-range Nash on a postflop board IS the `solve_range_vs_range_nash` path (`poker_solver/range_aggregator.py:878`). That function explicitly strips `initial_hole_cards` (L1034) and routes to `_rust.solve_range_vs_range_rust` (vector-form).
- A user wanting "Nash on board X with both players' full ranges" should use that entrypoint. The `--hunl-mode postflop` CLI doesn't expose it.

**Evidence against being the SOLE fix:**

- There's no CLI surface for the vector-form RvR path. Users who type `--hunl-mode postflop` aren't being misrouted from a working RvR CLI; the RvR CLI doesn't exist yet.
- Even if it did exist, the underlying validation gap in `solve_hunl_postflop` itself is independent — it should HARD-FAIL on `None` hole cards regardless of whether the user has a parallel RvR CLI to use instead.

**Conclusion:** Hypothesis A is the correct primary fix. Hypothesis C is a follow-on product gap (add `poker-solver solve --hunl-mode rvr` or similar) — the right shape but not blocking.

### Final ranking

1. **A (intended; CLI hard-fail)** — primary fix, one-line validation.
2. **C (RvR entrypoint missing)** — product gap, separate follow-on PR.
3. **B (enumerate 1326 in scalar)** — rejected; wrong layer.

## 4. Recommended fix scope

### Hot-patch (10-line change)

Two checks in tandem:

**(a) Rust validation at `crates/cfr_core/src/hunl_solver.rs::validate_config` (around L566-593):**

```rust
if config.initial_hole_cards.is_none() {
    return Err(HUNLSolveError::InvalidConfig(
        "solve_hunl_postflop requires initial_hole_cards = Some([[c0,c1],[c2,c3]]); \
         no hole cards → chance root → silent no-op. \
         For true range-vs-range Nash on a postflop board, use \
         poker_solver.solve_range_vs_range_nash instead.".into()
    ));
}
```

**(b) CLI validation at `poker_solver/cli.py::_build_postflop_config` (around L127-136):**

Since the CLI has no `--initial-hole-cards` flag at all, the cleanest fix is to surface the same hard-fail at the Python boundary with a more actionable error message:

```python
# After line 134, before return HUNLConfig(...):
raise ValueError(
    "--hunl-mode postflop currently has no way to specify hole cards. "
    "The scalar CFR backend requires fixed hole cards (it's a per-combo "
    "subgame solver, not a range-vs-range solver). For range-vs-range "
    "Nash on a postflop board, use the Python API: "
    "poker_solver.solve_range_vs_range_nash(config, hero_range, villain_range, ...)."
)
```

This is a **deliberate hard-fail with no migration path on the CLI** — until Hypothesis C's follow-on PR adds a `--hunl-mode rvr` sub-mode, the `--hunl-mode postflop` path simply cannot do what users likely want (RvR on a board). Better to fail loudly than to silently produce empty strategies that get reported with bogus exploitability numbers.

Alternatively, add an `--initial-hole-cards` CLI flag that parses two combos like `"AsAh,2c2d"` and threads them into the config. That preserves a working scalar path for the (rare) case of "I want a fixed-combo subgame solve from the CLI."

### Spec-only follow-on (Hypothesis C product gap)

Add a new CLI sub-mode `--hunl-mode rvr` that:

1. Accepts `--hero-range` and `--villain-range` (hand-class strings).
2. Routes to `_rust.solve_range_vs_range_rust` (the vector-form path).
3. Outputs the per-history strategy + per-class projection that `solve_range_vs_range_nash` already produces.

Scope: ~80 LOC of new CLI handler + arg-parsing + JSON output formatting. Out of scope for the hot-patch.

## 5. Ship-blocker assessment for v1.8.0

**Verdict: HOT-PATCH MUST SHIP IN v1.8.0; full fix can defer.**

Reasoning:

1. The bug is a **silent failure that has already caused at least one false-positive investigation** (Track A, ~2 hours of agent time on a 0-output experiment, plus the operator-facing risk of false confidence in "Nash uniqueness confirmed" if the empty `average_strategy` had been misread as "two strategies match exactly"). It will continue to silently misroute users who type `--hunl-mode postflop` without realizing the path is broken.

2. The Gate 4 turn-phase nohup (`pid=42803` at the time of Track A analysis, `As 7c 2d Kh` board) is on the same code path and almost certainly also a no-op — Track A flagged this in §7. If confirmed, that's a second wasted multi-hour run. The right move is to make the failure mode noisy BEFORE more agent time gets burned.

3. The hot-patch is **strictly additive validation** — no behavior change for any caller that already supplies `initial_hole_cards`. The vector-form path (`solve_range_vs_range_postflop`, the path that PR 23 / v1.5.0 acceptance tests exercise) is untouched. Risk to the v1.7 → v1.8 stack is minimal.

4. The Hypothesis C product gap (RvR CLI surface) is **not** a ship-blocker — it's a missing feature, not a broken feature. Users wanting RvR-on-board today can call `solve_range_vs_range_nash` from Python; the absence of a CLI for it is annoying but not a regression.

**Recommended action sequence:**

1. **v1.8.0** — ship hot-patch (Rust validation + CLI error). Add a release-note bullet "Reject `--hunl-mode postflop` invocations that would produce empty strategies; users wanting range-vs-range Nash should use `solve_range_vs_range_nash`."
2. **v1.8.x or v1.9.0** — add `--hunl-mode rvr` CLI sub-mode (Hypothesis C follow-on).
3. **Concurrent with #1:** kill Gate 4 nohup if confirmed to be on the broken path (run a 100-iter sanity dump per Track A §7 recommendation first; check for empty `average_strategy`). If broken, re-launch Gate 4 via `solve_range_vs_range_nash` with the same board.

## 6. References

- Track A diagnostic that surfaced this: `docs/a83_track_a_results_analysis_2026-05-26.md` §2c, §7
- Track A setup: `docs/a83_track_a_setup_2026-05-26.md`
- Underlying A83 investigation (still open): `docs/a83_deep_cap_root_cause_investigation.md`
- Code:
  - Empty-return site: `crates/cfr_core/src/hunl.rs:539-545`
  - Chance-root trigger: `crates/cfr_core/src/hunl.rs:344-348`
  - Scalar CFR no-op: `crates/cfr_core/src/hunl_solver.rs:265-282`
  - Scalar entrypoint (no validation): `crates/cfr_core/src/hunl_solver.rs:475-593`
  - Vector entrypoint (has reverse validation): `crates/cfr_core/src/dcfr_vector.rs:805-812`
  - CLI postflop config build (no hole-cards plumb): `poker_solver/cli.py:98-136`
  - Python validation (also missing the check): `poker_solver/hunl_solver.py:229-265`
  - RvR Nash entrypoint (correct path for users who want this): `poker_solver/range_aggregator.py:878-1057`
- Memory rules touched:
  - `feedback_nash_multiplicity_acceptance.md` — Track A was the Nash-multiplicity probe; this RCA explains why it produced no signal.
  - `feedback_silent_skip_hazard.md` — same family of bug: a load-bearing operation silently no-ops rather than hard-failing.
  - `feedback_empirical_over_audit.md` — when audit (Track A's PR 53 unit tests passing) says "code correct" but empirical (200K-iter logs) FAILs, keep digging at mechanical level. This RCA is that mechanical-level dig.

---

**Read-only investigation.** No code changes were made. Proposed fixes above are for user review before application.
