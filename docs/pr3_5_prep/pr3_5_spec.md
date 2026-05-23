# PR 3.5 spec — push/fold chart support (2-15 BB short stacks)

Status: planning. No code yet. Lands as a small, standalone PR between PR 3 (HUNL tree builder, Python) and PR 4 (card abstraction). Lives on branch `pr-3.5-pushfold`.

---

## 1. Goal

Ship **precomputed Heads-Up Nash push/fold charts** for short stack depths (2-15 BB) as static lookup tables, with a thin Python API that integrates with `solve(...)`. When a user requests a solve at `starting_stack <= 15 * big_blind`, the solver dispatches to the chart-lookup path instead of building and solving a tree.

**Why this is its own PR (not folded into the tree builder):** at very short stacks the action tree degenerates — optimal play collapses to shove-or-fold preflop. Running the tree builder + DCFR for these spots is wasteful; the answer is well-characterized in the published Nash literature and computable in minutes with our own tiny solver. Pre-solving once and storing a JSON lookup is O(1) at query time, zero memory, and avoids carrying short-stack edge cases through the rest of the engine.

This PR also serves as a **first end-to-end validation** of our DCFR solver against published references (Sklansky-Chubukov, GTO Wizard short-stack charts) — every chart we generate is also a correctness gate for the engine.

---

## 2. What PR 3.5 does NOT do

- **No postflop play.** Push/fold collapses the tree before the flop; no flop/turn/river decisions are modeled.
- **No support beyond 15 BB.** At 16 BB and above, limp / minraise / 3-bet dynamics matter materially and the tree builder is the right tool. PR 3.5 explicitly errors for unsupported stacks rather than silently returning a degraded answer.
- **No multiway.** HU only — SB vs BB. Multiway push/fold (BTN vs SB vs BB jam ranges) requires a different chart format and is not in scope.
- **No limp / minraise / 3-bet dynamics.** v1 ships **pure jam/fold only**: SB jams or folds; BB calls the jam or folds. This is the simplest defensible coverage; 10-15 BB borderline limp/minraise dynamics are flagged as a known limitation. A v2 chart pack could add minraise/limp lines later without breaking the API.
- **No ante / ICM / bounty variants.** v1 ships a single no-ante chart pack. The file format reserves an `ante` field so ante-aware charts can be added without breaking older lookups.
- **No Rust port.** All the work is in Python: small data, low-frequency lookups, no perf concern.

---

## 3. Scope of charts shipped in v1

**Two chart types, 14 stack depths each:**

| Chart | Stack depths | What it answers |
|---|---|---|
| `sb_jam` | 2, 3, 4, ..., 15 (14 entries) | Per hand class, what frequency does SB shove all-in (vs fold)? |
| `bb_call_vs_jam` | 2, 3, 4, ..., 15 (14 entries) | Per hand class, what frequency does BB call SB's all-in (vs fold)? |

Both indexed by **effective stack depth in big blinds (integer)**. Stack depth = min(SB stack, BB stack) in BB at the start of the hand, before blinds are posted.

Per chart, all **169 strategically-distinct starting hand classes** are populated. Hand-class notation matches `poker_solver.range.parse_range`:

- Pairs: `"AA"`, `"KK"`, ..., `"22"` (13 classes)
- Suited non-pairs: `"AKs"`, `"AQs"`, ..., `"32s"` (78 classes)
- Offsuit non-pairs: `"AKo"`, `"AQo"`, ..., `"32o"` (78 classes)

Each entry is `[hand_class: str, frequency: float]` with `frequency` in `[0.0, 1.0]`. **Hands not listed in a chart default to frequency 0.0** (file size optimization — Nash push/fold ranges are mostly hard 0/1, with a few mixed combos near the threshold; storing only the non-zero entries cuts file size ~3-5×).

**Default scope choice flagged for user review:**

- Pure jam/fold (SB jams or folds; BB calls or folds). Simplest. No minraise.
- 10-15 BB charts will be **slightly suboptimal** vs Nash-with-minraise; document the gap (≲5 bb/100 EV loss in the borderline regime per published references). The user can fall back to the tree builder at any stack ≥ 15 BB if they want minraise lines.

---

## 4. Data sources

**Recommended primary source: compute ourselves with the existing DCFR solver.**

Push/fold at 2-15 BB is a tiny game: ~169 hand classes × 2 actions per side × 14 stack depths. The full preflop tree (collapsed to jam/fold) has ~3-4k infosets per stack depth — orders of magnitude smaller than Kuhn-poker-scale games we already solve in seconds. A single overnight run of `scripts/generate_pushfold_charts.py` produces all 28 charts.

Why compute rather than copy:

1. **License clean.** Holdem Resources Calculator, ICMIZER, and similar tools have proprietary chart data; copying their JSON would be a license violation. Sklansky-Chubukov tables in *No Limit Hold'em Theory and Practice* (Sklansky & Miller, 2006) are published but represent a **different equilibrium concept** (unilateral push-or-fold against a calling-station opponent, *not* HU Nash); they're useful as a sanity-check anchor for the upper end of the SB jam range but not as ground truth.
2. **Validates our solver.** If we generate charts and they match published HU Nash charts within ~1% per hand class, that's a first cross-check of our DCFR implementation against industry-standard references — a free correctness gate.
3. **Reproducible.** Committed to git as JSON. Anyone can re-run the generator and verify bit-equivalence (modulo float tolerance).

**Cross-references used for validation only (no copying):**

- **Sklansky-Chubukov rankings** (public domain ordering) — sanity-check that our SB jam ranges at 4-8 BB include the top of the S-C ordering. Useful as a smoke test, not as the ground truth.
- **`references/papers/gto_poker_survey_2024.pdf`** — short-stack tournament play section cites published Nash push/fold equilibria; cross-check our generated values fall within the published range.
- **Hardcoded landmark checks** in tests (literature consensus, not from a specific licensed source):
  - At ≤ 4 BB stacks, SB jams the **vast majority** of hands. The Sklansky-Chubukov tables (unilateral push/fold vs a calling station) prescribe 100% at 2 BB, but **true HU Nash** has BB call wide enough at 2 BB that a handful of bottom offsuit hands (e.g. 72o, 32o, 43o, 52o, 53o, ~10-15 classes total) become marginally -EV jams. Concretely: ≥ 80% combo-weighted coverage at d=2 is the spec-mandated floor; precise count and identity of folded classes is determined by the DCFR solve and locked by the JSON. The 100% landmark applies to the S-C concept, not HU Nash. **Amended 2026-05-21** per `docs/autonomous_log.md` S10 (chart audit follow-up).
  - BB calls jam with ~`67%` of hands at 4 BB stacks (cf. Sklansky-Chubukov tables)
  - At 10 BB, SB jam range is roughly `~30%` of hands (broadly cited)
  - `72o` is never in any SB jam range at depth ≥ 6 BB

These cross-checks live in `tests/test_pushfold.py` (see §7) as `assert` statements with ~2% tolerance.

---

## 5. File format

**Path:** `poker_solver/charts/pushfold_v1.json`

**Structure (single JSON file, ~50-80 KB):**

```json
{
  "version": "v1",
  "generator": "scripts/generate_pushfold_charts.py",
  "generated_at": "2026-05-20T00:00:00Z",
  "ante": 0,
  "small_blind": 0.5,
  "big_blind": 1.0,
  "stack_depths_bb": [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
  "iterations_per_solve": 200000,
  "final_exploitability_bb_per_100": 0.012,
  "notes": "Pure jam/fold action set. SB jams or folds; BB calls or folds. No minraise/limp lines.",
  "charts": {
    "sb_jam": {
      "2":  [["AA", 1.0], ["KK", 1.0], ..., ["32o", 1.0]],
      "3":  [["AA", 1.0], ..., ["72o", 0.0]],
      ...
      "15": [["AA", 1.0], ["AKs", 1.0], ["AKo", 1.0], ["KK", 1.0], ...]
    },
    "bb_call_vs_jam": {
      "2":  [["AA", 1.0], ...],
      ...
      "15": [["AA", 1.0], ["KK", 1.0], ["QQ", 1.0], ["AKs", 1.0], ...]
    }
  }
}
```

**Field rules:**

- `version: "v1"` — bumped on schema-breaking changes. Loader rejects unknown majors.
- `ante: 0` — in BB units. Reserved for future ante-charts (`pushfold_v1_ante.json` etc.).
- `small_blind: 0.5`, `big_blind: 1.0` — BB units (always 1.0 for canonical HU); stored explicitly so the format can describe non-standard structures later.
- `stack_depths_bb: [2..15]` — integer BB depths covered. Loader sorts on read for deterministic iteration.
- `iterations_per_solve` + `final_exploitability_bb_per_100` — solver provenance for reproducibility checks.
- `charts.{sb_jam,bb_call_vs_jam}.{depth}` — list of `[hand_class, frequency]` pairs. **Sparse:** zero-frequency hands are omitted. **Order:** sorted by hand_class for deterministic diffing across regenerations.

**Why JSON (not CSV / parquet / a Python pickle):**

- Human-readable; reviewable in `git diff` when regenerated.
- ~50-80 KB compressed in repo — well below the 1 MB threshold that would push us toward LFS.
- Tooling-agnostic; competitors / users can read it.
- No risk of pickle / parquet version skew.

**One file per ante config.** If we add ante 12.5% later, that's `pushfold_v1_ante12_5.json`; the loader picks the right file by config-key.

---

## 6. Lookup API

**Module:** `poker_solver/pushfold.py` (~150 LOC).

```python
from typing import Literal
from poker_solver.solver import SolveResult

Position = Literal["sb_jam", "bb_call_vs_jam"]

def get_pushfold_strategy(
    stack_bb: int,
    position: Position,
    hand: str,
) -> float:
    """Return the equilibrium shove (or call) frequency for `hand`.

    Args:
        stack_bb: effective stack depth in BB (integer, 2-15 inclusive).
        position: which chart to query.
        hand: hand class string ("AA", "AKs", "AKo", "72o", ...) — matches
            `poker_solver.range.parse_range` canonical form. Case-insensitive.

    Returns:
        Frequency in [0.0, 1.0] of the aggressive action (jam for SB,
        call for BB). Hands not in the chart default to 0.0.

    Raises:
        ValueError: stack_bb out of range, unknown position, malformed hand.
    """

def get_pushfold_range(
    stack_bb: int,
    position: Position,
) -> dict[str, float]:
    """Return the full chart for one (stack, position) as a dict.

    Convenience for callers that want to iterate the whole range without
    169 individual lookups."""

def solve_pushfold(
    config: "HUNLConfig",
) -> SolveResult:
    """Build a SolveResult from the static charts for an HUNL config.

    Computes the stack depth as `min(config.starting_stack) / config.big_blind`,
    rounds to nearest integer in [2, 15], and returns a SolveResult whose
    `average_strategy` is keyed by HUNL-style infoset keys (matching what
    PR 3's `HUNLPoker.infoset_key` would produce for jam/fold infosets).

    This wraps the static charts in the same return type as the tree-builder
    solver so downstream callers (CLI, UI, library mode) don't have to
    special-case short-stack lookups.

    Raises:
        ValueError: if effective stack > 15 BB (caller should use full tree
            solver) or < 2 BB (degenerate — both players auto-allin).
    """
```

**Integration with `solve(...)`:** `poker_solver/solver.py:solve()` gains a fast-path. **See PR 9 spec §6 for the canonical full dispatch composition** (push/fold ≤15 BB → chart; >250 BB → error; postflop → postflop solver; preflop → preflop solver). PR 3.5's chart short-circuit MUST execute first (before the postflop or preflop branches) so a `HUNLConfig(starting_street=Street.PREFLOP, starting_stack=1500)` lands on the chart, not the preflop solver. Stub here:

```python
def solve(game, iterations, *, backend="python", **kwargs):
    if isinstance(game, HUNLPoker):
        eff_stack_bb = min(game.config.stacks) // game.config.big_blind
        if eff_stack_bb <= 15:
            return pushfold.solve_pushfold(game.config)
    # ... PR 5 / PR 9 branches per PR 9 §6 (canonical) ...
```

This dispatch is silent in the common case (a user solving short-stack HU gets the chart result with no extra config) and emits an `INFO` log line noting which mode is active for transparency.

**Updated 2026-05-21 per consistency review:** dispatch composition now cross-references PR 9 §6 as canonical (resolves blocker B4 from `docs/spec_consistency_review.md`).

**SolveResult shape preservation:**

- `average_strategy: dict[str, list[float]]` — keys are infoset strings matching what PR 3's `HUNLPoker.infoset_key` produces for the relevant push/fold infosets. Two-action vectors `[fold_prob, jam_or_call_prob]`.
- `game_value: float` — the SB's expected value in BB under both players' Nash strategies (computed once during chart generation and stored in the JSON metadata for direct return).
- `exploitability_history: list[float]` — single entry: the residual exploitability from the chart-generation solve, in bb/100.
- `iterations: int` — the iteration count used to generate the chart (logged from the JSON).
- `backend: "pushfold_chart"` — distinct value so downstream tooling can distinguish chart returns from tree solves.

---

## 7. Chart-generation pipeline

**Script:** `scripts/generate_pushfold_charts.py` (~120 LOC).

**What it does:**

1. For each stack depth `d ∈ {2, 3, ..., 15}`:
   - Construct a `HUNLConfig` with `starting_stack = d * big_blind`, `bet_size_fractions = ()`, `include_all_in = True`. Override `enumerate_legal_actions` to expose only `{FOLD, ALL_IN}` preflop (no check/call/min-bet/pot-fraction options). This is a one-line subclass of `HUNLPoker` named `PushFoldHUNL`.
   - Run `solve(PushFoldHUNL(config), iterations=200_000)` via the Python DCFR (the Rust path isn't wired for HUNL until PR 6).
   - Walk the resulting `average_strategy` and re-key by hand-class string (`"AKs"`, `"AA"`, etc.) by collapsing the 1326 combo-specific infosets into 169 strategically-equivalent classes. Strategic equivalence at preflop = same rank pair + same suitedness; verified by an `assert` that all combos in a class have within-`5e-3` strategies.
   - Record the SB-jam frequencies and BB-call-vs-jam frequencies as two flat lists.
   - Drop zero-frequency entries; sort by hand class.
2. Serialize all 28 charts to `poker_solver/charts/pushfold_v1.json`.
3. Emit a per-chart summary to stdout (number of jam hands, jam %, exploitability achieved) for reviewer inspection.

**Runtime budget:** target ≤ 10 min total on the MacBook (well within tractable). If it runs slower than 30 min, lower iterations to 100k — push/fold equilibria are simple enough that 100k iterations should reach < 0.05 bb/100 exploitability.

**Commit policy:** the generator is run **once** by the PR author; the resulting JSON is committed to git. The generator is not part of the test suite — it's deliberately offline tooling (running it on every CI invocation would burn ~10 min). A separate `tests/test_pushfold_regen.py::test_generator_smoke` runs the generator for **stack depth 5 only** with low iterations (5k) to ensure the script doesn't bit-rot, but does not overwrite the committed JSON.

---

## 8. Files to create / modify

**Create:**

- `poker_solver/pushfold.py` (~150 LOC) — lookup API per §6.
- `poker_solver/charts/__init__.py` (empty marker — declares the data dir as a package so `importlib.resources.files()` can locate the JSON).
- `poker_solver/charts/pushfold_v1.json` (~50-80 KB) — static chart data, generated once.
- `scripts/generate_pushfold_charts.py` (~120 LOC) — chart generator.
- `tests/test_pushfold.py` (~10 tests; see below).

**Modify:**

- `poker_solver/__init__.py` — re-export `get_pushfold_strategy`, `get_pushfold_range`, `solve_pushfold`.
- `poker_solver/solver.py` — add the short-stack dispatch in `solve()` per §6.
- `poker_solver/cli.py` — add `--hunl-mode pushfold` option (or just have the existing `solve` subcommand auto-dispatch based on stack depth; the latter is cleaner UX, the former is more debuggable). **Default: silent auto-dispatch with an `INFO` log line.**
- `README.md` — short "Push/fold mode" section under "Solver (preview)".
- `pyproject.toml` — declare `poker_solver/charts/*.json` as package data so the wheel includes them.

---

## 9. Tests (`tests/test_pushfold.py`)

Around 10 tests:

1. `test_load_chart_json_well_formed` — JSON loads, version is "v1", all 14 stack depths present in both charts.
2. `test_chart_completeness` — every chart entry has hand_class in the canonical 169 set; frequencies in [0, 1].
3. `test_sb_jam_monotone_in_hand_strength` — `freq(AA, d) >= freq(KK, d) >= ... >= freq(72o, d)` per stack depth (after collapsing to S-C-aligned hand-strength ranking — exact monotonicity holds for the top of the range; near-threshold mixed strategies may violate; assert on Top-30 hands only).
4. `test_short_stack_wide_jam` — at `d=2`, SB jams ≥ 80% of hands by combo-weighted total (HU Nash, not the S-C unilateral approximation). The 100% universal-jam landmark from §4 belongs to S-C; under true HU Nash a handful of bottom offsuit classes (e.g. 72o, 32o, 43o) stay folded because BB calls wide enough that the marginal jam is -EV. Tested as `test_pushfold_strategy_frequencies_sum_consistently` with a floor of `1326 * 0.80`. **Amended 2026-05-21** per `docs/autonomous_log.md` S10.
5. `test_bb_calls_premium_at_short_stack` — at `d=4`, BB calls `AA`, `KK`, `QQ`, `AKs` with frequency 1.0.
6. `test_landmark_jam_frequencies` — at `d=10`, SB jam range is ~30% ± 5% of hands by combo-weighted total.
7. `test_get_pushfold_strategy_basic` — `get_pushfold_strategy(10, "sb_jam", "AA") == 1.0`; `get_pushfold_strategy(15, "sb_jam", "72o") == 0.0`.
8. `test_solve_pushfold_returns_solveresult` — calls `solve_pushfold(HUNLConfig(starting_stack=1000))`; returns a `SolveResult` with `backend == "pushfold_chart"`.
9. `test_solver_auto_dispatch` — top-level `solve(HUNLPoker(cfg_10bb))` returns a chart-backed result without invoking DCFR.
10. `test_unsupported_stack_raises` — `solve_pushfold(cfg_with_50bb_stack)` raises `ValueError` with a helpful message ("use the tree-builder solver for stacks > 15 BB").
11. `test_generator_smoke` (lives in `tests/test_pushfold_regen.py`) — runs the chart generator at stack depth 5 with 5k iterations and verifies the output is well-formed (does not overwrite committed JSON).

**Cross-validation against literature (lives in `test_pushfold.py`):**

12. `test_top_jam_hands_match_sklansky_chubukov` — top-20 hands of our `d=4` SB jam list overlap by ≥ 90% with the published S-C top-20. This is a sanity gate, not a perfect match (S-C is unilateral vs calling station; we're solving HU Nash).

---

## 10. Critical correctness items

- **Hand canonicalization.** Hand-class strings must round-trip through `poker_solver.range.parse_range`. Test asserts `parse_range("AKs")` yields 4 combos and the chart entry `"AKs"` represents all 4 with the same frequency.
- **Frequencies validity.** Per (stack_depth, position), all listed frequencies in `[0, 1]`. (They do **not** sum to 1.0 — these are per-hand mix frequencies, not a distribution over hands.)
- **Suitedness consistency.** `"AKs"` and `"AKo"` are distinct entries with potentially different frequencies. `parse_range` distinguishes these correctly; the chart format mirrors that.
- **Strategic-equivalence collapse.** When the generator collapses 1326 combo infosets to 169 hand-class entries, it must assert that all combos in a class share strategy within `5e-3`. If not, the assert fires loudly — that's a solver-correctness signal (suit shouldn't affect preflop strategy in the abstracted game).
- **Solver convergence gate.** `final_exploitability_bb_per_100 < 0.05` in the generator output. Recorded in the JSON metadata. If a regeneration produces higher exploitability, the PR is rejected.
- **Literature cross-check.** §9 tests 11 + 12 form a soft gate (~2% tolerance) on agreement with published references.
- **Fallback for unsupported stacks.** `solve_pushfold(cfg)` raises `ValueError` for `eff_stack > 15` with a message pointing the caller to the tree-builder solver. Auto-dispatch in `solve()` does *not* fall back silently — it only triggers the chart path when stack ≤ 15.

---

## 11. Estimated effort

**1-2 days of focused work:**

- **Day 1:** Write the generator + `PushFoldHUNL` subclass; run it; verify against Sklansky-Chubukov landmarks; commit the JSON.
- **Day 2:** Write `pushfold.py`, the dispatch hook in `solve()`, the test suite, and README updates. Run the `scripts/check_pr.sh` battery and produce `pr_report.md`.

**Smaller than PR 3 (which has the full tree builder).** Fits cleanly as PR 3.5 between PR 3 (tree builder lands) and PR 4 (card abstraction).

---

## 12. Sequencing — does PR 3.5 ship before or after PR 4?

**Recommendation: ship PR 3.5 immediately after PR 3, before PR 4.**

Reasoning:

- **PR 3.5 depends on PR 3.** It needs `HUNLPoker`, `HUNLConfig`, `HUNLState`, and `enumerate_legal_actions` from PR 3. So it strictly cannot precede PR 3.
- **PR 3.5 is independent of PR 4.** Card abstraction (PR 4) does not affect push/fold charts — at preflop, the 169 strategically-distinct classes are already a near-optimal hand abstraction (no further bucketing needed). The chart generator can run on the unabstracted preflop tree.
- **PR 3.5 validates the DCFR solver.** Running it before PR 4 means we have a working short-stack equilibrium output to sanity-check against published references *before* layering on EMD card abstraction. That ordering lets us isolate "is the solver right?" from "is the abstraction right?" — useful when something goes wrong in PR 5.
- **Small, ships fast.** 1-2 days slots in nicely as a confidence-building win between two larger PRs. Keeps momentum.

If PR 3 lands on a Friday, PR 3.5 can land Monday and PR 4 starts Tuesday.

---

## 13. Risks and limitations

| Risk | Severity | Mitigation |
|---|---|---|
| 10-15 BB borderline regime: pure jam/fold is slightly suboptimal vs Nash-with-minraise. | Low (≲5 bb/100 EV loss in the borderline zone per literature) | Document the limitation in README + the JSON `notes` field. Users wanting tighter charts in 12-15 BB can fall back to the full tree solver. |
| Generated charts don't match published references within tolerance. | Medium | Sklansky-Chubukov is *not* HU Nash; we expect some divergence at lower-depth lists. Test 12 asserts ≥ 90% top-20 overlap, which gives slack for the conceptual difference while catching gross bugs. If overlap is < 90%, that's a solver-correctness issue (escalate before committing the JSON). |
| Solver fails to converge to < 0.05 bb/100 exploitability at 200k iterations. | Low | Bump to 500k iterations (still under 30 min total). If even that fails, push/fold game has unexpected structure → investigate (likely DCFR hyperparameter issue). |
| Auto-dispatch in `solve()` confuses users who want to force a tree solve at short stacks (e.g. for testing). | Low | Add an explicit `force_tree_solve: bool = False` kwarg to `solve()` for power users. Default behavior remains auto-dispatch. |
| Format v1 has to evolve (e.g. add minraise charts later). | Low | Format already includes `version: "v1"`. v2 will be additive (more `charts` keys); old loaders ignore unknown keys. Breaking changes bump to `v2` filename. |
| Pickle / wheel issue: charts JSON not bundled in the wheel. | Low | Declare in `pyproject.toml` under `[tool.maturin] include` or via `package-data`. Test by `pip install`ing the wheel into a clean venv and querying `get_pushfold_strategy` — must work without the source tree. |

---

## 14. Open questions for user review

Flagged with stars where the user's input would meaningfully change scope or quality:

1. ★ **Pure jam/fold scope.** Default is shove-or-fold only. Should we add a minraise menu item for 10-15 BB to cover the borderline regime? Adds ~3-5 days; produces tighter charts at the cost of more action-tree complexity.
2. **Stack-depth granularity.** 1-BB increments (2, 3, 4, ..., 15). Sufficient for chart consumers; finer (0.5-BB) only matters at the boundaries. Recommend keeping 1-BB.
3. ★ **Auto-dispatch in `solve()`.** Default: silent auto-dispatch when `eff_stack ≤ 15 BB`. Alternatives: (a) explicit `mode="pushfold"` kwarg required, (b) emit a warning rather than just an INFO log. Recommend default with INFO log.
4. **Ante support in v1.** Default: no ante. Tournament play above 25 BB usually has antes (typically 12.5% or 25% BB-equivalent) but at sub-15 BB short stacks antes are often present too. Adding ante = 4 more chart packs (no-ante, 12.5%, 25%, 50%). Recommend ship no-ante in v1; add ante variants in a follow-up if user requests.
5. ★ **Where does the dispatch live?** Two options: (a) inside `solve()` (silent, easy for callers); (b) the caller explicitly calls `solve_pushfold(cfg)` when they want chart mode. Recommend (a) for UX consistency with how GTO Wizard works (single entry point, dispatches behind the scenes).

---

## 15. Validation gate (before commit)

PR 3.5 ships only if all of the following pass:

1. `pytest tests/test_pushfold.py` — all 12 tests green.
2. `pytest tests/test_pushfold_regen.py` — generator smoke test green.
3. `python -c "from poker_solver import solve, HUNLPoker, HUNLConfig; print(solve(HUNLPoker(HUNLConfig(starting_stack=1000)), 1).game_value)"` — runs without error and returns a number in [-1.5, 0.5] BB (the published HU SB EV at 10 BB is roughly -0.05 to +0.15 BB depending on ante / blind structure).
4. `scripts/check_pr.sh` — full battery (Python lint, mypy, license audit, references integrity) green.
5. `pr_report.md` produced and reviewed.
6. Audit agent (per PLAN.md §"Code + test audit") reads the diff and produces a clean `audit_report.md`.
7. User reviews and approves before commit; user approves push separately.

---

**File path of this spec:** `/Users/ashen/Desktop/poker_solver/docs/pr3_5_prep/pr3_5_spec.md`
