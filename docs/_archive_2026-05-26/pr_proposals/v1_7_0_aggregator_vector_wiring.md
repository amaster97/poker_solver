# v1.7.0 Spec — `solve_range_vs_range_nash` user-facing Nash entry point (aggregator vector-form wiring)

**Status:** spec-only, read-only investigation. Author: spec agent (2026-05-23). Orchestrator approves and spawns implementer separately, AFTER v1.6.1 ships.

**Pre-condition:** PR 23 (`_rust.solve_range_vs_range_rust` vector-form CFR) shipped in v1.5.0; algorithm cell-for-cell validated against Brown by PR 40 fix bundle (`docs/pr_23_cell_divergence_deep_dive.md:21-23`, `docs/v1_5_0_per_action_divergence_diagnosis.md:14-41`). PR 33 (`solve_hunl_postflop(initial_hole_cards=())` auto-delegate) shipped per `docs/pr_proposals/v1_5_1_python_rust_delegate.md`. This PR is the next architectural wiring stage: expose vector-form CFR at the *range-vs-range* user-facing surface that today only has the blueprint aggregator.

**Goal:** Add a NEW user-facing entry point `poker_solver.solve_range_vs_range_nash(...)` that delegates to PR 23's vector-form CFR for the cases where callers genuinely want the joint range Nash. Keep the existing `solve_range_vs_range` blueprint aggregator unchanged (backward-compatible) so callers who want the fast Pluribus approximation are unaffected. Document the trade-off prominently so the API is *honest* about which question each function answers.

**Scope honesty.** This is the architectural opportunity surfaced by the W3.5 TRUE Nash test (`docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md:17-23`) — the aggregator and the vector form solve **structurally different mathematical objects** and produce different answers on the same input (see `docs/aggregator_vs_true_nash_explainer.md:24-50` + §1 below). v1.7.0 fixes the API surface, not the algorithm — PR 23's algorithm is already correct.

---

## 1. Problem statement (concrete code citations)

### 1.1 What the aggregator actually does

`poker_solver/range_aggregator.py:211-431` (`solve_range_vs_range`) is the only public Python entry point today for "hero range vs villain range" queries. It is **not** a Nash solver — it is the Pluribus-blueprint approximation pattern. Its own docstring (`range_aggregator.py:1-32`) names this:

> "**Honest framing.** Every per-hand solve is a 1-combo-vs-1-combo Nash, so the resulting frequencies reflect what hero does *against a specific villain combo*, not against the full villain range." — `range_aggregator.py:19-23`

The per-combo loop is at `range_aggregator.py:354-420`:

  - **Line 358-361:** enumerate concrete combos for each hero hand class (e.g., `AA` → 6 combos, `AKs` → 4, `AKo` → 12).
  - **Line 379-403:** for each hero rep × each villain rep pair, run `_run_one_subgame` (a **perfect-info 1v1 Nash solve** at `range_aggregator.py:590-654`) — both players know each other's exact hole cards in that subgame.
  - **Line 622-625:** the per-pair solve uses `replace(config_template, initial_hole_cards=hole_cards)`, then dispatches to the standard `solve()`. This is a full-information subgame, **not** an imperfect-info range solve.
  - **Line 405-414:** average frequencies across reps, then aggregate at `range_aggregator.py:749-776` weighted by combo count.

The aggregator's output is structurally a **histogram of per-combo perfect-info best responses**, not a Nash mixed strategy. See `docs/aggregator_vs_true_nash_explainer.md:39-50` for the long-form decomposition.

### 1.2 What the vector-form CFR does

`_rust.solve_range_vs_range_rust` at `crates/cfr_core/src/lib.rs:389-503` is PR 23's vector-form CFR — Brown's algorithm bit-for-bit. It stores per-(hand, action) regret/strategy tables and walks the betting tree **once per iteration** with hands as a vector dimension *inside* each infoset (`crates/cfr_core/src/dcfr_vector.rs:7-19`, `dcfr_vector.rs:78-101`). The output is a single joint Nash where hero's strategy mixes across actions, conditioned on the full range.

PR 23's docstring at `crates/cfr_core/src/lib.rs:414-416` flags the unfinished wiring:

> "Q3 default (spec §8): Python's `solve_range_vs_range` aggregator is NOT rewired to this entrypoint in v1.5.0 — the binding stands alone for downstream code (and v1.5.1) to wire in."

PR 33 (v1.5.1, `docs/pr_proposals/v1_5_1_python_rust_delegate.md`) wired one call site: `solve_hunl_postflop(config, initial_hole_cards=())` auto-routes to the Rust vector form. But **the range-vs-range user-facing surface is still the aggregator alone**: no public Python entry today returns a true range-Nash result with a hand-class API.

### 1.3 Concrete divergence evidence (W3.5 TRUE Nash test)

`docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md:17-23` quantifies the gap on a single monotone-river spot (board `Ts 8s 6s 4c 2d`, symmetric 15-class ranges):

| Test | Solver path | AA at river-open |
|---|---|---|
| W3.5 v1.5.1 RvR aggregator PoC | `solve_range_vs_range` (`range_aggregator.py:211`) | **bet 68%** (basket-selection, not Nash) |
| W3.5 TRUE Nash (this report) | `_rust.solve_range_vs_range_rust` (`lib.rs:428`) | **pure CHECK 100%** |

The aggregator collapsed range polarization because each per-combo subgame gave AA *perfect knowledge* of villain's hand (`W3_5_TRUE_nash_v1_5_1.md:24-37`). "AA bets 68%" is the **aggregator artifact**: AA pure-bets vs every villain combo it beats (8 of 13 after collision filter, ≈ 64%); the 68% figure is just `beat-count / total-reps`. Real Nash on this monotone board has AA as a bluff-catcher → pure check, since the hands that call AA's value bet (sets) beat AA, while the hands AA beats (KQ/KJ/AK air) won't call (`W3_5_TRUE_nash_v1_5_1.md:118-137`).

Same shape at W1.2 deep-stack (`docs/persona_test_results/W1_2_v1_5_1_retest_deep_stack.md:15`): aggregator gives **JJ folds 7.69%** against villain pot bet — this is deterministic, **not** convergence noise. 7.69% = 3/39, the fraction of villain reps that were AA. The vector-form Nash defends **100%** (calling beats folding by +1801 chips/hand against the unknown-villain distribution per `W1_2_v1_5_1_retest_deep_stack.md:225`). The aggregator structurally cannot answer "should JJ defend?" because each per-combo subgame correctly folds JJ vs AA — and pooling that fold into the range-level frequency reports 7.7% fold instead of 0%.

### 1.4 Why this matters now

The W3.5 TRUE Nash test is the second persona-evidence acceptance of the divergence (after W1.2). The explainer doc (`docs/aggregator_vs_true_nash_explainer.md:144-149`) codifies that:

> "Aggregator numbers like '7.7% fold' or '68% bet' are deterministic artifacts of the aggregation rule, not Nash mixed frequencies. Misreading them produces false-positive PASSes (W3.5's original 'AA polarizes' verdict, since downgraded) or false-negative solver-bug reports (W1.2's 'convergence noise' claim)."

PR 23 fixed the algorithm. PR 33 fixed one consumer (`solve_hunl_postflop`). The range-vs-range surface is still on the wrong side of the divergence. Users who ask "what's hand X's Nash strategy in this range?" today get the aggregator — and the aggregator structurally cannot answer that question.

**v1.7.0:** add the entry point that *can* answer it. Keep the aggregator for callers who genuinely want the fast Pluribus-style approximation.

---

## 2. Proposed change — options considered

### Option A — REPLACE the aggregator with a vector-form delegate

Change `solve_range_vs_range` so it delegates to `_rust.solve_range_vs_range_rust` and synthesizes the per-class strategy table by mapping vector-form per-hand strategies back to hand-class buckets.

**Pros:**
1. One function, one canonical answer. No more "aggregator vs Nash" confusion.
2. W3.5 polarization claim ships as the default range-vs-range answer.

**Cons:**
1. **Breaking change.** Every aggregator test (`tests/test_range_vs_range_aggregator.py`) locks in approximation semantics — the per-class frequencies would change wholesale. MAJOR-version bump risk.
2. The aggregator is the documented Pluribus blueprint pattern (`range_aggregator.py:5-9`); deleting it severs that capability.
3. Vector-form has a memory edge (preflop full-1326 deferred per `dcfr_vector.rs:49-50`); the aggregator is the only path that handles those configs today.
4. Aggregator's `hero_player` / `reps_per_class` / `villain_reps` / `time_budget_per_solve_s` knobs do not map onto vector-form CFR. Translation is non-trivial.
5. PR 33 (`docs/pr_proposals/v1_5_1_python_rust_delegate.md:97-106`) already rejected this approach for v1.5.1 with the same reasoning. The reasoning still holds at v1.7.0.

**Verdict: REJECTED** — too disruptive; aggregator has legitimate use cases.

### Option B — ADD `solve_range_vs_range_nash` (RECOMMENDED)

Add a new public entry point `poker_solver.solve_range_vs_range_nash(...)` that delegates to PR 23's vector-form CFR. Leave `solve_range_vs_range` (the aggregator) unchanged. Document the two paths side-by-side in `USAGE.md` and `DEVELOPER.md` — callers wanting *true Nash* call `solve_range_vs_range_nash`; callers wanting the fast Pluribus blueprint approximation call `solve_range_vs_range`.

**Pros:**
1. **Backward-compatible.** Every existing aggregator caller works unchanged. No flip risk in `tests/test_range_vs_range_aggregator.py`.
2. **Honest API.** The two functions have distinct names that describe what each *actually* solves. The W3.5 / W1.2 misinterpretations stop being possible: you read "Nash" → you get joint Nash; you read aggregator → you read the docstring and learn it is a blueprint approximation.
3. **Additive surface — MINOR bump.** Adding a function with new behavior is a MINOR per Keep-A-Changelog; backward-compatible with all v1.x callers.
4. **Mirror PR 33 strategy.** PR 33 used a routing kwarg + auto-delegate for `solve_hunl_postflop` because that function's callsites are entrenched. The range-vs-range surface is smaller and the *output schemas* differ enough (per-class hand-class table vs per-(hand, history) vector strategy) that a separate function is cleaner than a kwarg.
5. **Migration story is graceful.** v1.7.0 ships the new entry; v1.7.x optionally adds a `DeprecationWarning` to the aggregator (after community feedback); v1.8+ optionally removes the aggregator. No forced migration in v1.7.0 itself.
6. **Decision parallels** `docs/pr_proposals/v1_5_1_python_rust_delegate.md:97-106` (Option C reject for v1.5.1) — the same task explicitly punted "rewire aggregator to vector form" as v1.5.2-or-later. v1.7.0 is the matured plan for that punt.

**Cons:**
1. Two functions answering similar-sounding questions invites confusion. Mitigated by: (a) prominent docstring framing on both functions cross-referencing `docs/aggregator_vs_true_nash_explainer.md`; (b) `USAGE.md` table contrasting the two; (c) the function names themselves signal their semantics.
2. Maintainability cost — two code paths to keep current. Mitigated by: vector-form is a thin Python wrapper over the Rust binding (≤100 LOC), so it does not grow indefinitely.

**Verdict: RECOMMENDED.**

### Option C — `solve_range_vs_range(..., mode="vector")` kwarg

Add a `mode: str = "aggregator"` (or `"auto"`) kwarg to the existing `solve_range_vs_range`; default keeps aggregator semantics, `mode="vector"` routes to PR 23.

**Pros:**
1. One entry point — looks tidy on the surface.
2. Same backward-compat properties as Option B at default settings.

**Cons:**
1. **Output schema mismatch.** Aggregator returns `RangeVsRangeResult` with `per_class_strategy: dict[HandClass, dict[action_label, prob]]` and `range_aggregate: dict[action_label, prob]` (`range_aggregator.py:194-204`). Vector form returns per-(infoset, hand) strategies with `hand_count × action_count` tables (`crates/cfr_core/src/lib.rs:467-472`). One result class cannot honestly hold both. Either the vector path returns a stripped-down per-class projection (loses information that motivates the call) or the dataclass grows two optional sets of fields (`per_history_strategy` vs `per_class_strategy`) with documentation that one is `None` based on mode — both ugly.
2. **API mode-kwarg anti-pattern.** A boolean / enum that flips function semantics is a classic readability tarpit. PR 33 used `backend="auto"` because both paths return the same `HUNLSolveResult` schema (just different internal algorithm) — same kwarg pattern here would either lie about the output or force-project.
3. **Discoverability.** Users searching for "Nash range solver" will not find `solve_range_vs_range(..., mode="vector")` as easily as `solve_range_vs_range_nash(...)`.
4. **Argument mismatch.** Aggregator takes `iterations: int = 200, reps_per_class, villain_reps, time_budget_per_solve_s, hero_player, backend (rust|python)` (`range_aggregator.py:215-223`). Vector form takes `iterations, alpha, beta, gamma, p0_holes, p1_holes` (`crates/cfr_core/src/lib.rs:418-426`). Shared signature would have ~half the args be "ignored if mode=X" — confusing.

**Verdict: REJECTED** — clean separation is worth one extra function name.

### Recommendation

**Ship Option B (new function `solve_range_vs_range_nash`).** Backward-compatible, honest API, MINOR-version-safe, mirrors the PR 33 strategy of "add the right path; don't break the existing one."

---

## 3. API design

### 3.1 Signature

Add to `poker_solver/range_aggregator.py` (co-located with the existing aggregator so the contrast is visible in one file):

```python
@dataclass
class RangeVsRangeNashResult:
    """True joint-Nash result for a range-vs-range query (vector-form CFR).

    Distinct from :class:`RangeVsRangeResult` because the underlying
    algorithm produces **per-(history, hand) strategies**, not per-class
    aggregated frequencies. See ``docs/aggregator_vs_true_nash_explainer.md``
    for the long-form distinction.

    Attributes:
        per_history_strategy: ``{infoset_key: list[float]}`` mapping
            ``<hole_string>|<key_suffix>`` (the lossless Python format from
            ``HUNLState.infoset_key``) to action-probability rows. Hand
            order within an infoset matches the Rust binding's emit order
            (deterministic; documented in PR 23 spec §3).
        per_class_strategy: ``{hand_class: {action_label: probability}}``
            — root-decision projection of ``per_history_strategy`` onto
            hand classes (pair / suited / offsuit), combo-weighted. Provided
            as a convenience for callers that want the 13x13-style display.
            **Caveat:** This projection collapses the per-history mixing,
            so it is informative but not a full strategy description; for
            real Nash analysis use ``per_history_strategy``.
        range_aggregate: Root-decision range-aggregated action frequencies
            (combo-weighted across classes). ``{action_label: probability}``.
            Mirrors ``RangeVsRangeResult.range_aggregate`` for source-compatibility.
        exploitability: Computed via ``_rust.compute_exploitability`` on
            the returned strategy. Float in millibig-blinds per pot (same
            unit as ``solver.exploitability``).
        iterations: Iteration count actually run.
        wall_clock_s: Total wall-clock for the solve.
        decision_node_count: Number of decision nodes in the betting tree
            (from Rust dict).
        hand_count_per_player: ``(p0_count, p1_count)`` of hands enumerated
            after board-collision filtering.
        memory_profile: Per-street memory breakdown from PR 23 (passed
            through from the Rust dict's ``memory_profile`` field).
        backend: ``"rust_vector"`` (literal; matches PR 23 emit).
        position: ``"aggressor"`` if ``hero_player == 0`` else ``"defender"``
            (mirrors the aggregator's ``position`` field semantics).
        warnings: Human-readable warnings (memory fallbacks, etc.).
    """

    per_history_strategy: dict[str, list[float]] = field(default_factory=dict)
    per_class_strategy: dict[HandClass, dict[str, float]] = field(default_factory=dict)
    range_aggregate: dict[str, float] = field(default_factory=dict)
    exploitability: float = 0.0
    iterations: int = 0
    wall_clock_s: float = 0.0
    decision_node_count: int = 0
    hand_count_per_player: tuple[int, int] = (0, 0)
    memory_profile: dict[str, Any] = field(default_factory=dict)
    backend: str = "rust_vector"
    position: str = "aggressor"
    warnings: list[str] = field(default_factory=list)


def solve_range_vs_range_nash(
    config_template: HUNLConfig,
    hero_range: Sequence[HandClass] | Range,
    villain_range: Sequence[HandClass] | Range,
    *,
    iterations: int = 500,
    alpha: float = 1.5,
    beta: float = 0.0,
    gamma: float = 2.0,
    hero_player: int = 0,
    compute_exploitability_at_end: bool = True,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> RangeVsRangeNashResult:
    """Solve a range-vs-range query via PR 23's vector-form CFR (true Nash).

    Unlike :func:`solve_range_vs_range` (which is the Pluribus-blueprint
    aggregation workaround — see that function's docstring), this routine
    solves the **joint imperfect-information Nash** of the supplied ranges
    using vector-form CFR. Hands are a vector dimension *inside* each
    infoset; the betting tree is walked once per iteration with full-range
    bluff-catching dynamics.

    Use this when you need:
      - True bluff-catching frequencies (e.g. "should JJ fold facing pot
        odds with 93% equity in this range?").
      - Polarized bet-sizing driven by range composition.
      - Brown / commercial-solver parity comparisons.

    Use :func:`solve_range_vs_range` instead when you need:
      - A fast 13x13 matrix Pluribus-style display.
      - Per-combo correctness on dry boards where the value-vs-air dynamic
        dominates and the approximation is tight.
      - A range solve on a config where the vector path is at its memory
        edge (full preflop range; some monotone wet flops).

    See ``docs/aggregator_vs_true_nash_explainer.md`` for the long-form
    distinction.

    Args:
        config_template: ``HUNLConfig`` with ``starting_street >= FLOP``.
            ``initial_hole_cards`` is ignored — the vector form enumerates
            hands per-player from the supplied ranges (after board-collision
            filtering, identical to the aggregator's filter at
            ``range_aggregator.py:336-340``).
        hero_range: hand-class labels or a ``Range`` (same shape as
            :func:`solve_range_vs_range`). Expanded to concrete combos for
            the Rust binding's ``p0_holes`` / ``p1_holes`` args.
        villain_range: Same.
        iterations: DCFR iterations. Default 500 (matches PR 23 W3.5 test
            convergence; the aggregator's 200 default is for fast per-hand
            sub-solves and is too few here).
        alpha, beta, gamma: DCFR hyperparameters; PLAN.md defaults.
        hero_player: ``0`` (aggressor) or ``1`` (defender). Controls which
            player slot hero's range fills; the ``per_class_strategy``
            projection extracts that player's first-decision strategy.
        compute_exploitability_at_end: When True (default), call
            ``_rust.compute_exploitability`` once on the converged
            strategy and populate ``result.exploitability``. Skip when
            you only need the strategy (saves one full-tree walk).
        on_progress: Optional callback ``(iter_done, total_iter, phase_label)``.
            Currently fires once at start and once at end (vector CFR does
            not stream per-iteration progress).

    Returns:
        ``RangeVsRangeNashResult`` with both the raw per-history strategy
        AND a per-class projection for UI compatibility.

    Raises:
        ValueError: hero/villain range empty; ``hero_player`` not in
            ``(0, 1)``; ``config_template.starting_street == PREFLOP``
            (vector-form preflop deferred per ``dcfr_vector.rs:49-50``);
            both ranges have zero board-feasible combos after collision
            filter.
        ImportError: ``poker_solver._rust`` does not expose
            ``solve_range_vs_range_rust`` (i.e. the Rust binding was not
            built with the v1.5+ PR 23 entry).
        MemoryError: vector form exceeds 16 GB spec envelope; the caller
            can fall back to ``solve_range_vs_range`` manually.
    """
    ...
```

Argument differences from the aggregator (intentional):

| Aggregator (`solve_range_vs_range`) | `solve_range_vs_range_nash` |
|---|---|
| `iterations: int = 200` | `iterations: int = 500` (higher; one solve replaces ~N per-class subsolves) |
| `backend: str = "rust"` (per-subgame backend) | Removed — vector-form is Rust-only |
| `reps_per_class: int = 1` | Removed — no per-class basket sampling in vector form |
| `villain_reps: int = 3` | Removed — same reason |
| `time_budget_per_solve_s: float = 30.0` | Removed — single solve, not N per-subgame |
| `dcfr_kwargs: dict | None = None` | Replaced with explicit `alpha / beta / gamma` (vector-form binding's signature; matches `lib.rs:418-426`) |
| (none) | `compute_exploitability_at_end: bool = True` (NEW) |
| `on_progress: (done, total, hand_class) → None` | `on_progress: (iter_done, total_iter, phase_label) → None` — phase-based, not per-class |

### 3.2 Internal flow

1. Validate `config_template.starting_street != PREFLOP` (matches aggregator's check at `range_aggregator.py:313-320`; the v1.5.x preflop range-vs-range is deferred per `dcfr_vector.rs:49-50, 755`).
2. Validate `hero_player in (0, 1)` (matches `range_aggregator.py:309-312`).
3. Normalize ranges via `_normalize_range(...)` (existing helper at `range_aggregator.py:538-566`).
4. Expand to concrete combos via `_enumerate_combos(...)` (existing helper at `range_aggregator.py:439-486`) and apply board-collision filter (matches `range_aggregator.py:337-340`).
5. Convert each `(Card, Card)` pair to the `[u8; 2]` shape PR 23 expects (`lib.rs:435-436`). For `hero_player == 0`, hero's combos are `p0_holes`; for `hero_player == 1`, hero's combos are `p1_holes`.
6. Serialize the config to JSON via the existing `_serialize_hunl_config` machinery (referenced by `docs/pr_proposals/v1_5_1_python_rust_delegate.md:25` — already in use by PR 33).
7. Invoke `_rust.solve_range_vs_range_rust(config_json, iterations, alpha, beta, gamma, p0_holes, p1_holes)`.
8. Unpack the returned dict (`average_strategy`, `iterations`, `wallclock_seconds`, `decision_node_count`, `hand_count_per_player`, `memory_profile`, `backend`).
9. If `compute_exploitability_at_end`: call `_rust.compute_exploitability(config_json, strategy)` (`lib.rs:350-387`) and populate `result.exploitability`. Else `result.exploitability = 0.0`.
10. Project `per_history_strategy` to `per_class_strategy`: at the root decision for `hero_player`, group rows by hand class (using `_combo_to_hand_class` at `range_aggregator.py:569-582`) and average within each class. Build the action-label map via existing helper `_label_for_action` at `range_aggregator.py:109-136`.
11. Combo-weight aggregate via existing `_aggregate_range` helper at `range_aggregator.py:749-776`.
12. Return populated `RangeVsRangeNashResult`.

### 3.3 Schema compatibility with `RangeVsRangeResult`

`RangeVsRangeNashResult.per_class_strategy` and `range_aggregate` deliberately mirror the aggregator's fields (`range_aggregator.py:195-196`) — so any caller currently consuming the aggregator output's range-level dict can swap functions with **zero downstream changes** at the consuming site (only the import + function-name change). The vector form adds `per_history_strategy`, `exploitability`, `memory_profile`, `decision_node_count`, `hand_count_per_player`; existing aggregator-only fields (`total_combos`, `total_solves`, `partial_misses`, `per_solve_wall_clock_s`) are absent because the vector form does not have per-subgame iterations.

---

## 4. Files touched

### Source

| File | Change | LOC est. |
|---|---|---|
| `poker_solver/range_aggregator.py:778-785` | Add `RangeVsRangeNashResult` dataclass + `solve_range_vs_range_nash` function. Reuse existing helpers `_normalize_range`, `_enumerate_combos`, `_combo_to_hand_class`, `_label_for_action`, `_aggregate_range`. Add to `__all__`. | ~150 |
| `poker_solver/__init__.py:94-98, 125-127` | Add imports + `__all__` entries for `RangeVsRangeNashResult` and `solve_range_vs_range_nash`. | ~4 |

### Tests

| File | Change | LOC est. |
|---|---|---|
| `tests/test_range_vs_range_nash.py` (NEW) | New test module — see §7 acceptance tests. | ~250 |
| `tests/test_range_vs_range_aggregator.py:1-50` (existing) | No change — aggregator tests stay green. Aggregator semantics unchanged. | 0 |
| `tests/test_v1_5_brown_apples_to_apples.py:1-80` (existing) | No change — already exercises `_rust.solve_range_vs_range_rust` directly. The new `solve_range_vs_range_nash` is a thin wrapper; adding a parallel test through the new entry would be redundant but is cheap (add to test_range_vs_range_nash.py as one case). | 0 |

### Docs

| File | Change |
|---|---|
| `USAGE.md` | New §5.x "Two range-vs-range paths" subsection. Side-by-side table of `solve_range_vs_range` (aggregator) vs `solve_range_vs_range_nash`. Link to `docs/aggregator_vs_true_nash_explainer.md` for the long-form distinction. Update existing range-vs-range example to call out which function to use. |
| `DEVELOPER.md` | New §"Range-vs-Range internals" subsection mapping the Python entries to the Rust bindings. Cite `range_aggregator.py:211` and `crates/cfr_core/src/lib.rs:428`. |
| `CHANGELOG.md` | New `[1.7.0]` section. `### Added`: `solve_range_vs_range_nash` + `RangeVsRangeNashResult`. `### Documentation`: USAGE/DEVELOPER updates citing the two-path API. |
| `docs/aggregator_vs_true_nash_explainer.md:172-181` | Update §"Going forward" subsection — mark the wiring as **landed in v1.7.0**; cite `solve_range_vs_range_nash` as the canonical entry for the "Nash" question. |

### UI / packaging cascade

Per `[UI + packaging sync](feedback_ui_packaging_sync.md)`, this is a user-facing API change → must update PR 10b UI + trigger PR 11 .dmg rebuild:

| File | Change |
|---|---|
| PR 10b UI range-vs-range surface | Decide: add a "True Nash" mode toggle (calls `solve_range_vs_range_nash`) vs the "Blueprint" mode (calls aggregator). Recommendation: ship the toggle UI in v1.7.0 if it fits in the UI agent's budget; else defer to v1.7.1 and document. |
| `dist/poker_solver-1.7.0-*.dmg` | Rebuild after v1.7.0 lands. Include CHANGELOG diff in release notes. |

---

## 5. Migration path

### v1.7.0 ship

- **Added**: `solve_range_vs_range_nash`, `RangeVsRangeNashResult`.
- **Unchanged**: `solve_range_vs_range`, `RangeVsRangeResult` (backward-compatible).
- **Docs**: side-by-side comparison in USAGE.md + DEVELOPER.md.
- **No deprecation**: aggregator stays fully supported.

### v1.7.x (optional follow-ups, decided per community feedback)

- v1.7.1+: optionally add `DeprecationWarning` to `solve_range_vs_range` *only when called with input shapes for which vector-form is feasible* (i.e., not preflop full-1326). The warning would say: "For true Nash range-vs-range, prefer solve_range_vs_range_nash. solve_range_vs_range remains supported for Pluribus-blueprint-style approximations; see docs/aggregator_vs_true_nash_explainer.md."
- v1.8.0: optionally rename `solve_range_vs_range` → `solve_range_vs_range_blueprint` with a deprecation alias kept for one MINOR cycle. **Defer this decision** — depends on whether the community treats the aggregator as a useful fast path or as a legacy footgun.

### Caller migration guidance

Add to `USAGE.md`:

> **If you currently call `solve_range_vs_range` and want true Nash:** rename to `solve_range_vs_range_nash`, drop the `reps_per_class` / `villain_reps` / `time_budget_per_solve_s` / `backend` kwargs (they have no analog in vector form), and read `result.per_class_strategy` for the 13x13-display projection or `result.per_history_strategy` for the full per-(hand, history) Nash.
>
> **If you want the Pluribus-blueprint fast path:** keep `solve_range_vs_range`. It is supported and accurate within its documented approximation envelope (dry boards, value-vs-air dynamics).

---

## 6. Risk

### 6.1 Memory ceiling

Vector form has memory edge on large preflop range; aggregator is the fallback (`dcfr_vector.rs:49-50, 755`; `docs/aggregator_vs_true_nash_explainer.md:73-75`). Since v1.7.0 keeps `solve_range_vs_range` as-is, callers who hit the memory edge can fall back manually. We do **not** auto-fallback inside `solve_range_vs_range_nash` because:

  1. The two functions produce structurally different output schemas; silent fallback would lie about which question the caller asked.
  2. The aggregator's combo-sampling parameters (`reps_per_class`, `villain_reps`) need explicit choice — auto-fallback cannot pick them sensibly.

The function raises `MemoryError` instead and documents the workaround.

### 6.2 Performance

Per PR 23 spec §5 measurements (`docs/v1_5_pr_23_implementer_notes.md` — referenced not re-cited here): vector-form completes a medium 10×10 RvR in well under 1 s, and the W3.5 TRUE Nash test ran 15×15 in 3.6 s @ 1000 iter / 10.7 s @ 3000 iter (`W3_5_TRUE_nash_v1_5_1.md:50`). The aggregator at small scope is similar (~5 s for a 6×5 class config per `range_aggregator.py:18-20`'s test target). Vector-form's scaling advantage compounds at larger ranges; the aggregator's `O(hero_classes × villain_reps)` per-subgame loop is more expensive on broad ranges.

### 6.3 Backward compatibility

NEW function only — `solve_range_vs_range` aggregator unchanged. All existing aggregator tests stay green. CHANGELOG documents the new entry as `### Added` only.

### 6.4 API surface bloat

Two functions answering similar-sounding questions is a documentation-quality concern. Mitigated by:

  1. Distinct function names (`*_nash` clearly signals "joint Nash").
  2. Prominent docstring framing on both functions cross-referencing each other and the explainer doc.
  3. `USAGE.md` side-by-side comparison table.
  4. `docs/aggregator_vs_true_nash_explainer.md` is the canonical long-form reference.

### 6.5 Result schema mismatch

`RangeVsRangeNashResult` and `RangeVsRangeResult` are deliberately distinct dataclasses — they answer different questions. Callers that consume only `range_aggregate` and `per_class_strategy` can swap one for the other (those fields are present in both). Callers that consume aggregator-specific fields (`partial_misses`, `total_solves`, etc.) keep using the aggregator. There is no path that breaks silently.

### 6.6 Persona test re-evaluation cost

Per the explainer doc (`docs/aggregator_vs_true_nash_explainer.md:174-176`): "Persona verdicts that relied on the aggregator for 'range Nash' claims may need re-evaluation. W3.5 has been downgraded to PASS-WITH-CAVEATS; others may follow." v1.7.0 makes re-evaluation **possible** by exposing the Nash entry; the actual retest spec is a separate task (orchestrator-driven, post-v1.7.0).

---

## 7. Acceptance tests

New file `tests/test_range_vs_range_nash.py`. Six cases, all opt-in to existing markers consistent with the project's pattern (`@pytest.mark.slow` for the long-running ones).

### Tier 1 — W3.5 monotone polarization reproduction

1. **`test_w3_5_monotone_aa_pure_check`** — replicate the W3.5 TRUE Nash test fixture (`W3_5_TRUE_nash_v1_5_1.md:40-77`): board `Ts 8s 6s 4c 2d`, symmetric 15-class range, 1000 iter via `solve_range_vs_range_nash`. Assert:
   - `result.per_history_strategy["<AA root key>"]` has check probability ≥ 0.99 (matches W3.5 TRUE-Nash 1.0000 entry at `W3_5_TRUE_nash_v1_5_1.md:101-102`).
   - `result.range_aggregate["check"]` ≥ 0.85 (W3.5 reports 0.87 range-aggregate check).
   - `result.exploitability` < 5.0 chips (sanity bound; W3.5 reports sub-1-chip at 3000 iter, but 1000-iter test allows looser bound).
   - **Negative control**: the same range run through `solve_range_vs_range` aggregator should yield `range_aggregate["bet_*"]` substantially > 0.0 (the 68% aggregator artifact). Assert the two functions diverge — codifying the explainer doc's claim as a regression test.

### Tier 2 — W1.2 deep-stack JJ defense reproduction

2. **`test_w1_2_jj_defends_pot_bet`** — replicate W1.2 fixture (`W1_2_v1_5_1_retest_deep_stack.md:14-16`): deep-stack JJ vs pot bet, JJ's defend frequency. Assert:
   - `result.per_class_strategy["JJ"]` has fold probability < 0.01 (vector form defends 100% per `W1_2_v1_5_1_retest_deep_stack.md:225`; aggregator falsely reports 7.69%).
   - Defend (= 1 − fold) ≥ 0.99.
   - **Comparison assertion**: aggregator returns ~7.7% fold; new entry returns ~0% fold. Diff > 5 percentage points — codifies the W1.2 evidence.

### Tier 3 — Brown apples-to-apples through the new entry

3. **`test_brown_parity_via_nash_entry`** — reuse the `dry_K72_rainbow` and `dry_A83_rainbow` fixtures from `tests/test_v1_5_brown_apples_to_apples.py:48-49`. Call `solve_range_vs_range_nash` (instead of `_rust.solve_range_vs_range_rust` directly) and assert per-(hand, action) parity against Brown's binary within the locked `5e-3` tolerance (matches `test_v1_5_brown_apples_to_apples.py:64`). Confirms the new entry is a faithful pass-through of PR 23's algorithm. Already-validated by PR 40 fix bundle (`docs/pr_23_cell_divergence_deep_dive.md:21-23`); this test gates the wrapper specifically.

### Tier 4 — schema + error cases

4. **`test_nash_result_schema`** — `RangeVsRangeNashResult` fields populate correctly; `per_class_strategy` rows sum to 1.0; `range_aggregate` sums to 1.0; `backend == "rust_vector"`; `position` correctly reflects `hero_player`.

5. **`test_preflop_raises`** — `config_template.starting_street == Street.PREFLOP` raises `ValueError` (matches aggregator behavior at `range_aggregator.py:313-320`; vector form preflop deferred).

6. **`test_invalid_hero_player`** — `hero_player not in (0, 1)` raises `ValueError`.

### Tier 5 — exploitability bound

7. **`test_exploitability_decreases_with_iterations`** — small fixture (5×5 hands, river spot). Solve at 200 / 500 / 1000 iter; assert `result.exploitability` is monotonically non-increasing (modulo small noise tolerance). Sanity-check for the solver pass-through; not a strict convergence guarantee.

---

## 8. Ship target

**Recommendation: v1.7.0 MINOR (new public API capability).**

Per Keep-A-Changelog conventions and the project's version history (`docs/leg13_v1_5_0_ship_plan.md` cited cadence: v1.5.0 PR 23 algorithm; v1.5.1 PR 33 `solve_hunl_postflop` delegate; v1.6.0 GUI; v1.6.1 fixes):

  - **Added** (`solve_range_vs_range_nash`, `RangeVsRangeNashResult`) → MINOR bump.
  - **Unchanged** (`solve_range_vs_range`, `RangeVsRangeResult`) → no MAJOR concern.
  - **Documentation** (USAGE.md, DEVELOPER.md, CHANGELOG.md, explainer doc update) → MINOR is appropriate.

Override conditions (would push to v2.0.0 MAJOR):
  - If during implementation we discover the aggregator's behavior IS what users expect (community pushback), and v1.7.0 needs to deprecate-and-rename it.
  - If the implementer concludes Option C kwarg pattern is preferable in practice (we view this as unlikely per §2; raise as orchestrator decision if so).

Default: v1.7.0 MINOR ship.

---

## 9. Estimated complexity

**1-2 days** (8-16 dev hours, single implementer).

Breakdown:
  - Function + dataclass: ~150 LOC of Python wrapping existing helpers. **2-3 hours.**
  - Integration with `_rust.solve_range_vs_range_rust` (JSON config serialization, combo → `[u8; 2]` marshaling, dict unpacking). PR 33 already established the pattern; this is a port. **2-3 hours.**
  - Per-history → per-class projection (Tier 4 schema work). **1-2 hours.**
  - Tests (six cases, ~250 LOC). **3-4 hours.**
  - Docs (USAGE.md + DEVELOPER.md + CHANGELOG.md + explainer doc update). **1-2 hours.**
  - UI cascade (PR 10b mode toggle) — *optional, may slip to v1.7.1*. **+2-4 hours** if bundled.

Bulk of the work is integration testing — the algorithm is correct (W3.5 TRUE Nash test validates), the binding is correct (PR 40 fix bundle validates), the wrapper just plumbs them together with a docstring.

---

## 10. Open questions for orchestrator

1. **UI cascade scope** — bundle the PR 10b "True Nash mode toggle" into v1.7.0 or defer to v1.7.1? Recommendation: bundle if the UI agent has bandwidth; the toggle is small and tells the user-facing story most cleanly. Decision needed before implementer spawn.

2. **Aggregator deprecation timeline** — v1.7.x adds a `DeprecationWarning` to `solve_range_vs_range` (per §5), or wait for community feedback? Default recommendation: do **not** deprecate in v1.7.0; revisit in v1.7.x after we see whether the aggregator path retains genuine users.

3. **W3.5 + W1.2 + W2.3 + W3.4 persona retests** — schedule after v1.7.0 ships to re-evaluate verdicts that the explainer doc flagged as potentially aggregator-contaminated (`docs/aggregator_vs_true_nash_explainer.md:174-176`). Out of scope for v1.7.0 PR itself; orchestrator-driven follow-up.

4. **`compute_exploitability_at_end=True` default** — is the extra full-tree walk worth the default-on cost? PR 23 spec sets a similar default to True for `_rust.compute_exploitability` in `tests/test_v1_5_brown_apples_to_apples.py`. Recommendation: default True (small wall-clock cost; populates a load-bearing acceptance field). Implementer can flip if measured cost is unreasonable.

---

## 11. References (READ-ONLY scan, 2026-05-23)

- **W3.5 TRUE Nash test**: `docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md` (§"Distinguishing this test" + AA strategy tables at lines 17-23, 96-115, 201-209)
- **W1.2 JJ deep-stack retest**: `docs/persona_test_results/W1_2_v1_5_1_retest_deep_stack.md:14-16, 225`
- **Aggregator vs true Nash explainer**: `docs/aggregator_vs_true_nash_explainer.md` (full doc)
- **PR 23 spec**: `docs/pr_proposals/v1_5_rust_dcfr_widening.md` + PyO3 binding at `crates/cfr_core/src/lib.rs:389-503`
- **PR 33 spec (companion delegate)**: `docs/pr_proposals/v1_5_1_python_rust_delegate.md` — §"Option C REJECTED FOR v1.5.1" at lines 97-106 explicitly punted this work to "v1.5.2-or-later"
- **Aggregator source**: `poker_solver/range_aggregator.py` (entire module; per-combo loop at lines 354-420; per-subgame solve at lines 590-654)
- **Vector-form Rust binding**: `crates/cfr_core/src/lib.rs:389-503`
- **Vector-form Rust core**: `crates/cfr_core/src/dcfr_vector.rs:1-101, 49-50, 755`
- **Existing aggregator tests**: `tests/test_range_vs_range_aggregator.py:1-50`
- **Existing Brown apples-to-apples test**: `tests/test_v1_5_brown_apples_to_apples.py:1-80`
- **Existing schema sub-classing pattern (`HUNLSolveResult` extends `SolveResult`)**: `poker_solver/hunl_solver.py:65-89`
- **Brown apples-to-apples background**: `docs/brown_apples_to_apples_2026-05-23.md` (referenced for the structural-difference framing)
- **PR 23 algorithm cell parity confirmation**: `docs/pr_23_cell_divergence_deep_dive.md:21-23`, `docs/v1_5_0_per_action_divergence_diagnosis.md:14-41`

---

**End of spec.** Orchestrator: spawn implementer after v1.6.1 ships and PR 10b UI scope decision is made (Q1 above). Recommended branch name: `pr-<next>-aggregator-vector-wiring` (consistent with project PR-number sequencing).
