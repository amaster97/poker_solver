# v1.4.0 — Node Locking (Design Spec)

**Status:** Proposal. No code yet.
**Target release:** v1.4.0 (MINOR — additive public API).
**Author:** Orchestrator burst, 2026-05-23.
**Inspiration (read-only):** `references/code/postflop-solver/src/{solver.rs,utility.rs,game/interpreter.rs,game/tests.rs}`. AGPL — no code copying; structural ideas only (see Section 3 for the boundary).

---

## 1. Problem statement

**What node-locking is.** Pinning a player's strategy at a specific infoset — or a set of infosets — to a fixed probability distribution over its legal actions, then running DCFR with that distribution held constant. The other side updates against the locked strategy as if it were a fact of the world. Output: the **near-Nash exploit hero plays into the locked opponent**, plus resulting EV.

In plain poker: "Solve the river, but assume villain never bluffs the turn check-raise." Or: "Assume villain calls 3-bets at 60% (not Nash ~52%) — what does my opening range become?" This is the single most-requested feature from anyone evaluating this tool against Pio / GTO+. The current solver gives Nash against a perfect opponent; a live MTT player with two hours of table reads has exactly the kind of structured-deviation read that node-locking is built to exploit.

**Why Daniel needs it.** The referenced persona spec at `docs/pr13_prep/persona_acceptance_spec.md` does not currently exist (I checked the directory — empty). Framing Daniel's needs from the broader "live MTT pro evaluating against Pio" archetype; workflow IDs below are placeholders pending the persona spec landing:

- **W-DL-01 — Villain never bluffs rivers.** Lock river bet → 0 at infosets where bluffs are blocked. Hero should fold more bluff-catchers.
- **W-DL-02 — Villain calls 3-bets too wide.** Lock villain's preflop call frequency to 60%. Hero's open-raise sizing and 4-bet frequency should shift.
- **W-DL-03 — Villain donk-leads small only with draws.** Lock villain's flop donk to draws + air. Hero should raise the donk wider for value.
- **W-DL-04 — Hero's preferred line.** Hero locks a personal line ("always c-bet 33% on AhTh3c") and asks what villain's BR is. Inverse problem, same machinery.

That covers 4 of Daniel's 5 originally-blocked workflows. The 5th (W-DL-05, multi-street tree visualization) is GUI-only, not in scope.

**Why the timing is right.** PR 10b (real GUI bindings) shipped 2026-05-23, so the solver is now driven from a UI that surfaces specific infosets. Node-locking is the natural next API: pick a node, type a distribution, re-solve. v1.0.0 GA locked the public API surface, so adding `locked_strategies` to `solve()` is a clean MINOR bump.

---

## 2. Conceptual design

### 2.1 What gets locked

Three locking granularities, all reducible to the same internal representation (a `dict[infoset_key, list[float]]`):

1. **Single infoset.** The user names one infoset key (the string returned by `HUNLPoker.infoset_key`) and a probability vector over its legal actions. Example: `"AsKs|QhTh3c|f|c"` → `[0.0, 0.7, 0.3]` (assuming legal actions are `[fold, check, bet_75]`).
2. **Infoset set.** A list of infoset keys all sharing the same fixed strategy. Example: every river infoset where villain previously bet half-pot, locked to "check 100%". Internally this expands to N entries in the same dict.
3. **Hand class at a node.** A user-facing convenience: "AA always raises preflop." Internally we enumerate the 6 combos of AA, find their infoset keys at the preflop opening node, and emit 6 dict entries — all with the same probability vector. The expansion is a `range_aggregator`-side helper, not an engine concept. See Section 3.5.

### 2.2 Lock semantics

During each CFR iteration at a locked infoset:

- The locked strategy is **read** to compute action-weighted state values.
- Regret-matching is **skipped** (no `_get_strategy` call).
- `regret_sum` is **not updated** (we won't consult it again).
- `strategy_sum` is **not updated** — the locked vector IS the average strategy at output time; appending iteration contributions would dilute it back toward Nash.
- Other infosets continue regret matching as usual, treating the locked infoset's strategy as part of the game's structure.

Output: `result.average_strategy[locked_key]` returns the locked vector bit-identically; other entries are iterate-averaged; `result.game_value` is hero's EV under the joint policy `(hero_response, locked_villain)`.

Convergence note: when one side is locked, the unlocked side still has well-defined regret minimization (the locked side becomes a fixed environment, no longer adversarial). What you converge to is a Nash equilibrium of the *induced* game where the locked side's strategy is part of the rules. Section 6 covers the empirical convergence caveat.

### 2.3 API surface

```python
from poker_solver import HUNLConfig, HUNLPoker, solve, Street

# Lock dict: infoset_key -> probability vector over legal actions.
# Length + ordering MUST match the engine's legal_actions order at that
# infoset; solver validates on first visit (ValueError with remediation).
locked_strategies = {
    "AsKs|QhTh3c|f|c": [0.0, 0.7, 0.3],   # fold 0%, check 70%, bet 30%
    "QdQh|QhTh3c|f|c": [0.0, 1.0, 0.0],
}

result = solve(
    HUNLPoker(cfg),
    iterations=500,
    backend="rust",
    locked_strategies=locked_strategies,   # NEW
)
# result.average_strategy[locked_key] returns the locked vector bit-identically.
# result.game_value is hero's EV against the locked opponent.
# result.exploitability_history under single-sided lock drives to the
# BR-vs-fixed-villain value, NOT a Nash gap of zero.
```

`locked_strategies` defaults to `None`. Absent / empty → bit-identical to v1.3 (Section 4 enforces this).

---

## 3. Implementation plan

### 3.1 Files touched

| File | Lines (current) | Change |
|------|-----------------|--------|
| `poker_solver/solver.py` | 29-37 (`solve()` signature), 84 + 119 + 152 + 462 (Rust dispatch) | Add `locked_strategies: dict[str, list[float]] | None = None` to `solve()`. Validate non-negative + sum-to-one. Thread into Python `DCFRSolver(...)` and through `_solve_rust(...)` to the PyO3 call. |
| `poker_solver/dcfr.py` | 51-66 (`DCFRSolver.__init__`), 104-148 (`_cfr`) | Accept `locked_strategies` in `__init__`. In `_cfr`, after `key = self.game.infoset_key(state, player)` (line 120), check `locked_strategies.get(key)`. If present: use as `strategy` (bypassing `_get_strategy`); SKIP the `info.regret_sum += regret_delta` (line 146) AND `info.strategy_sum += own_reach * strategy` (line 147). Still recurse into children. |
| `poker_solver/hunl_solver.py` | 100-112 (`solve_hunl_postflop` signature), 183-186 (`DCFRSolver(...)` construction) | Pass `locked_strategies` through to `DCFRSolver`. Also surface in `HUNLSolveResult` — locked entries are merged back into `average_strategy` at line 201-202 (after `solver.average_strategy()`) so callers see them. |
| `crates/cfr_core/src/dcfr.rs` | 71-81 (`DCFRSolver::new`), 131-205 (`cfr` recursion) | Add `locked_strategies: HashMap<String, Vec<f64>>` field. In `cfr` (line 155-160 area), after computing `key` and before `discount_info`, check the lock map. If locked: use the locked vector as `strategy`; skip the `simd::update_regret_sum` (line 197) and `simd::update_strategy_sum` (line 203) calls. The discount catch-up can also be skipped (the regret vector is dead). |
| `crates/cfr_core/src/hunl_solver.rs` | 119-128 (`HUNLDcfr::new`), 176-307 (`cfr` recursion), 348-358 (`solve_hunl_postflop` signature) | Same shape as `dcfr.rs`. Lock check inserted at line 246 (just after `let key = state.infoset_key(...)`); skip the SIMD `update_regret_sum` / `update_strategy_sum` (lines 299, 305). |
| `crates/cfr_core/src/lib.rs` | 118-128 (`#[pyo3(signature)]`), 130-186 (postflop entry); 198-249 (preflop entry) | Add `locked_strategies: Option<HashMap<String, Vec<f64>>>` parameter. PyO3 marshals it from a Python dict directly. Pass into the Rust `solve_hunl_postflop` / `solve_hunl_preflop`. |
| `poker_solver/range_aggregator.py` | 183-244 (`solve_range_vs_range`) | Optional: accept a higher-level `locked_classes` dict (`{"AA": [0.0, 1.0]}` etc.). The aggregator expands to per-combo infoset keys and forwards to `solve()`. Defer to v1.4.1 if scope pressure (see Section 8). |
| `tests/test_node_locking.py` | NEW | Five+ scenarios — Section 4. |
| `crates/cfr_core/tests/test_node_locking_diff.rs` | NEW | Rust-side diff test: locked solve must match Python locked solve within float epsilon. |

No changes to `poker_solver/hunl.py` (infoset keys are stable), `poker_solver/games.py` (no Game-protocol change), `crates/cfr_core/src/hunl.rs` (no state-machine change), `crates/cfr_core/src/abstraction.rs`, or PR 10b UI surface in this PR.

### 3.2 Algorithm (pseudo-code)

```
def _cfr(state, reach, iteration):
    if terminal(state): return utility(state)
    if current_player(state) == CHANCE: <enumerate, same as v1.3>

    key = infoset_key(state, player)
    actions = legal_actions(state)

    if key in locked_strategies:
        strategy = locked_strategies[key]      # READ ONLY
    else:
        info = _get_infoset(key, len(actions))
        _discount(info, iteration)
        strategy = _get_strategy(info)

    node_value, action_values = recurse_children(state, strategy, reach, ...)

    if key not in locked_strategies:
        # regret + strategy_sum updates EXACTLY as v1.3 (dcfr.py:145-147)
        info.regret_sum   += opponent_reach * (action_values - node_value)
        info.strategy_sum += own_reach * strategy

    return node_value
```

One `HashMap::contains_key` / `dict.__contains__` per infoset visit. Allocation-free in steady state.

### 3.3 Output assembly

`DCFRSolver.average_strategy()` (Python `dcfr.py:161`, Rust `dcfr.rs:227`) iterates `self.infosets`. Locked infosets are never inserted, so the call returns only unlocked entries. The orchestrator (`solver.py:177-186` / `hunl_solver.py:201-220`) merges the lock dict back into `result.average_strategy` before returning:

```python
avg = solver.average_strategy()
avg.update(locked_strategies)  # bit-identical passthrough
```

Engine stays simple (locked infosets invisible to it); API contract stays clean.

### 3.4 Validation

On first `_cfr` visit to a locked infoset: `len(strategy) == len(actions)`, all entries `>= 0`, `abs(sum - 1.0) < 1e-9`. On failure, `ValueError`: `"locked_strategies[{key!r}] has length {len(strategy)} but the engine emits {len(actions)} legal actions; usually means bet_size_fractions changed since the lock was created."` Lazy validation avoids enumerating the tree eagerly (expensive on lossless flop) and still catches the bug on iteration 1.

### 3.5 Hand-class expansion (range_aggregator.py)

Sugar for "AA always raises preflop." Thin pre-processor: enumerate combos via the existing `_enumerate_combos` (line 376), build each combo's infoset key at the target node, emit one dict entry per combo with the same probability vector. Trivial; can slip to v1.4.1 if Section 7's estimate is tight.

### 3.6 What we deliberately do NOT do

- **Per-hand locking inside an infoset.** The postflop-solver reference (AGPL) supports a `num_actions * num_private_hands` lock matrix because it carries an explicit hand vector at each public infoset (`references/code/postflop-solver/src/game/interpreter.rs:870-925`). Our infoset key already embeds hole cards (`hunl.py:355-358`), so each (hand, board, history) is its own infoset — per-hand locking IS per-infoset locking. No range-vector representation borrowed.
- **Lock at chance nodes.** Chance is the environment; nothing to lock.
- **Callable strategies.** Only literal probability vectors. Callables would re-enter Python from the Rust loop and kill throughput.
- **Mid-solve lock changes.** Lock dict is frozen at solver construction. The postflop-solver's `lock_current_strategy` / `unlock_current_strategy` is interactive; ours is batch — re-call `solve()` to update.

---

## 4. Acceptance criteria

- **A1 — New public API.** `solve(..., locked_strategies=...)` accepts `dict[str, list[float]] | None`. Same kwarg on `solve_hunl_postflop` and `solve_hunl_preflop`. `None` and empty dict are bit-identical to v1.3.
- **A2 — `tests/test_node_locking.py` with five scenarios:**
  1. **Empty-lock equivalence.** Bit-identical `average_strategy` + `game_value` vs no kwarg, on Kuhn / Leduc / `default_tiny_subgame()`.
  2. **Passthrough.** Lock one infoset to `[0.3, 0.7]`; `result.average_strategy[key]` equals `[0.3, 0.7]` exactly.
  3. **Best-response heuristic.** River subgame, lock villain to never bluff; assert hero's fold-vs-bet frequency is monotone-lower than the unlocked solve.
  4. **EV monotonicity.** Lock villain to a strictly suboptimal strategy; assert `result.game_value >= unlocked_game_value - 1e-6`.
  5. **Validation.** Length mismatch / non-normalized / negative entry each raise `ValueError` with remediation text.
- **A3 — Cross-tier diff.** `tests/test_node_locking_diff.py` runs the same locked Kuhn solve Python + Rust; agreement within `1e-9`. Same pattern as `tests/test_dcfr_diff.py`.
- **A4 — Performance.** With a lock dict of ≤10% of infosets, per-iteration overhead <10% vs unlocked. Measured via `crates/cfr_core/benches/dcfr_bench.rs` on Leduc + tiny river subgame. One HashMap lookup per infoset visit; budget is generous.
- **A5 — No regression.** All PR 5/6/8/9/10a.5/10b tests green. Diff tests included.
- **A6 — Docs.** `USAGE.md` gets a 15-line "Node-locking" subsection with a worked example. `CHANGELOG.md` gets a v1.4.0 entry. No new README content.

---

## 5. Persona impact

- **Daniel (live MTT pro).** 4 of 5 originally-blocked workflows unblocked: W-DL-01 through W-DL-04. W-DL-05 (multi-street tree visualizer) stays GUI-only, out of scope.
- **Sarah (intermediate, "what if I always 3-bet AA?").** Direct hit via the hand-class expansion sugar (Section 3.5). She types `"AA": [0.0, 1.0]`; the aggregator does the expansion. No "infoset key" vocabulary required.
- **Marcus (rec player).** No direct impact. Feature is opt-in; default behavior unchanged.
- **Priya (API consumer / scripter).** Strong hit. "For each leak, compute exploit EV" becomes 10 lines of Python. Matches the postflop-solver / Pio scripting vocabulary closely.

---

## 6. Honest risks

- **R1 — Convergence under locking may be empirically softer.** Brown & Sandholm 2019's guarantees assume both players update freely. When one side is locked, the unlocked side runs single-agent regret minimization against a fixed environment — that does converge, but the DCFR discount schedule (α=1.5, β=0, γ=2.0) was tuned for two-sided play. May observe slower exploitability decay or, in degenerate cases, oscillation. **Mitigation:** A4 tracks exploitability over iterations; if it regresses, widen the default iteration budget and document. We promise correct semantics, not faster convergence.
- **R2 — Heavily-locked solves degenerate.** If >50% of infosets are locked, the unlocked side has little to optimize. **Mitigation:** Document "lock at most 20%" heuristic. Emit `UserWarning` if lock dict exceeds 50% of visited infosets after iter 10. Don't refuse.
- **R3 — Float drift.** The lock check inserts a branch in the hottest loop. Branch is data-independent, but may permute compiler register allocation. **Mitigation:** A1's empty-lock-dict bit-identity test catches drift on day one. If it fails, gate the check on `!locked.is_empty()`.
- **R4 — Infoset-key churn.** The key format (`hunl.py:328-363`) embeds bet sizing in the history string. If the user authors a lock against one config and re-solves with different `bet_size_fractions`, keys silently miss and the lock is no-op. Section 3.4's validation catches legal-action mismatch but not zero-hit. **Mitigation:** Emit `UserWarning` if any lock key is never visited during solve. Document "lock keys are tied to your action abstraction" prominently.
- **R5 — UI integration deferred.** Brief permits "GUI in v1.4.1." Daniel may not see the win for half a release cycle. **Mitigation:** Include a minimal "Locks (JSON)" text box in the spot panel in v1.4.0 (half a day) even if the full node-picker UI waits.

---

## 7. Effort estimate

| Phase | Days |
|-------|------|
| Spec (this doc) | 1 (done) |
| Python `DCFRSolver` lock branch + validation | 1 |
| Rust `DCFRSolver` + `HUNLDcfr` lock branch | 2 |
| PyO3 lock marshalling | 0.5 |
| Tests (`test_node_locking.py` + diff) | 1 |
| `range_aggregator.py` hand-class expansion | 0.5 (can slip to v1.4.1) |
| Audit + ship | 1 |
| **Total** | **7 days** |

Single-developer; Python/Rust solver edits are coupled by the diff test (cannot parallelize). Docs agent can run concurrent with implementation.

---

## 8. Versioning + roadmap

**v1.4.0 (this PR).** `locked_strategies` kwarg on `solve()` + both `solve_hunl_*`. Python + Rust DCFR lock-aware. Hand-class expansion. Minimal "Locks (JSON)" GUI hook. Five-test pack. Docs. **MINOR bump** — additive only.

**v1.4.1 — GUI polish (follow-up).** Full node-picker UI built on the v1.4.0 engine API. Does not block the API ship.

**v1.5.0 — speculative.** Iterative tightening (Sandholm-style safe subgame solving). Out of scope; v1.4.0 is the foundation.

---

## Appendix — open questions for the implementer

1. **Frozen mapping?** Recommend `MappingProxyType(dict(locked_strategies))` at construction to prevent post-`solve()` mutation footguns.
2. **Hand-class expansion + ANY_VILLAIN sentinel.** Section 3.5 needs villain hole cards to build the key, but `hunl.py:355-358` only embeds the player's own hole cards in the key, so any concrete villain combo works for the expansion. Confirm and document.
3. **Locks under push/fold short-circuit.** `solve()` line 63-74 routes ≤15 BB preflop to `solve_pushfold` (chart lookup). Recommend refusing with "use `force_tree_solve=True`" rather than silently ignoring the lock.
4. **Exploitability under locking.** Document in `SolveResult.exploitability_history`'s docstring that under locking it represents the unlocked side's regret only (the locked side cannot BR).
5. **Diff test scope.** Parametrize over `[empty, one-key, ten-key]` lock configurations.
