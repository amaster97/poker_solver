# v1 Range Fractional-Frequency Refactor Spec

**Status:** Spec only. Scope-added to v1 burst on 2026-05-25.
**Time budget:** ~4 dev days across 4 PRs (A/B/C/D).
**Scheduling:** Implementer kickoff awaits orchestrator scheduling after the
in-flight v1.7.1 ship retry and v1.8 cross-platform SIMD work clear.
**Predecessor spec:** `docs/pr_proposals/v1_5_x_range_frac_freq_refactor.md`
(2026-05-23, engine-only, 1-2 day scope). This spec supersedes it by
explicitly covering the GUI editor wiring, solver-side weight propagation,
persona-test fixture refresh, and the 4-PR landing sequence.

---

## 1. Goal

`Range` becomes a first-class fractional-frequency container. Every combo
carries a weight `w in [0.0, 1.0]`:

- `w == 1.0` — combo plays the action at every dealing (current "in-range").
- `0.0 < w < 1.0` — combo plays the action a fraction `w` of the time
  (mixed strategy).
- `w == 0.0` (or absent) — combo never plays the action ("not in range").

Mixed-strategy outputs are the dominant case in GTO solves; without
per-combo weights we cannot express, store, or display them faithfully.
This refactor closes the data-model gap.

The W2.2 literal-spec exemplar — "KQo: you 3-bet 0%, GTO 25%" — becomes
representable once weights ship.

---

## 2. Current data model

`/Users/ashen/Desktop/poker_solver/poker_solver/range.py` lines 25-83.

```python
Combo = tuple[Card, Card]

@dataclass
class Range:
    combos: list[Combo] = field(default_factory=list)
    _combo_set: set[Combo] = field(default_factory=set, repr=False)
```

Properties of today's representation:

- `Combo` is a bare 2-tuple of `Card`s. No weight field.
- `Range` stores presence-only: a combo is either in the list (and set) or
  it isn't.
- `Range.add(combo)` dedupes by membership; no weight argument.
- `Range.diff(other)` is set-difference. Its docstring (range.py:53-58)
  already documents the future-extension contract: the boolean diff is
  the all-weights-1.0 special case of `max(self.freq - other.freq, 0)`.
- `Range.sample_excluding(...)` samples uniformly from the combo list.
- `parse_range(spec)` accepts PokerStove-style hand syntax
  (`"AA, KK-TT, AKs+"`). No weight suffix; combos default to implicit 1.0.

There is already a UI-layer wrapper `RangeWithFreqs` in
`/Users/ashen/Desktop/poker_solver/ui/state.py:254-326` with
`frequency_of(combo) -> float` and `set_frequency(combo, freq)` methods,
backed by an external `frequencies: dict[Combo, float]`. This wrapper
exists because `Range` itself cannot store weights. The refactor folds
this capability INTO `Range` and lets `RangeWithFreqs` thin out (or be
removed entirely once all consumers move to the new API).

---

## 3. New data model

Promote `Combo` to a frozen dataclass; `Range` gains a parallel weight map.

```python
@dataclass(frozen=True)
class Combo:
    cards: tuple[Card, Card]      # canonical-sorted; identity-bearing
    weight: float = 1.0           # auxiliary; NOT in __hash__ / __eq__

    def __iter__(self):           # back-compat: c1, c2 = combo
        return iter(self.cards)

    def __getitem__(self, i):     # back-compat: combo[0], combo[1]
        return self.cards[i]

@dataclass
class Range:
    combos: list[Combo] = field(default_factory=list)
    _combo_set: set[tuple[Card, Card]] = field(default_factory=set, repr=False)
    _weight: dict[tuple[Card, Card], float] = field(default_factory=dict, repr=False)
```

**Key invariants:**

- `Combo` hashes/compares on `cards` only — `Combo(c, w=0.3) == Combo(c, w=0.6)`.
  Cards are identity; weight is metadata.
- `_combo_set` key remains `tuple[Card, Card]` so existing presence
  checks like `(card_a, card_b) in r._combo_set` keep working.
- `_weight` map is the canonical source of truth for weights;
  `Combo.weight` mirrors it for ergonomic iteration.
- Iteration `for combo in range` yields `Combo` objects; old destructuring
  `c1, c2 = combo` and indexing `combo[0]` survive via the back-compat
  shims.

---

## 4. Migration strategy

Old binary ranges map to fractional ranges by assigning weight `1.0` to
every present combo. Concretely:

- `Range.add(combo)` with no weight argument defaults to `weight=1.0`.
  Existing call sites stay valid.
- `parse_range("AA, KK")` produces all those combos at weight 1.0.
- `range.diff(other)` with all-1.0 inputs yields the boolean set-difference
  result; mathematical identity.
- `range.sample_excluding(...)` collapses to uniform sampling when all
  weights are 1.0.

Net behavior change for any caller that does NOT explicitly use weight
arguments or the new `:weight` parse syntax: **none**.

On-disk migration: not required. Range objects are not currently
serialized with a weight column anywhere in the codebase
(`poker_solver/charts/pushfold_v1.json` stores Range strings, no
weights — round-trip via the extended `parse_range` grammar). UI session
state already stores per-combo frequencies via `RangeWithFreqs`; that
wrapper will be wired to delegate to the new in-`Range` weight storage
in PR (C).

---

## 5. Call sites to update

Code (non-doc) files that reference `Range`, `parse_range`, or the
combo/weight surface — 14 files in total:

| File | Role | Edit needed |
| --- | --- | --- |
| `poker_solver/range.py` | Owner | YES — primary refactor |
| `poker_solver/__init__.py` | Public exports | minor — re-export `Combo` |
| `poker_solver/range_aggregator.py` | Hand-class aggregation | check `_combo_to_hand_class` flow, propagate weight into hand-counted aggregate |
| `poker_solver/equity.py` | Equity helper / sample paths | weighted sampling now matters |
| `poker_solver/cli.py` | Uses `parse_range` opaquely | none expected (back-compat covers it) |
| `scripts/generate_pushfold_charts.py` | Tooling, parses ranges | none expected |
| `examples/range_vs_range_river.py` | Example script | none expected |
| `ui/state.py` | `RangeWithFreqs` wrapper | YES — delegate to `Range._weight`; thin the class out |
| `ui/views/range_freq_editor.py` | Per-combo freq dialog | YES — already uses `RangeWithFreqs`; will continue to work via delegation |
| `ui/views/range_matrix.py` | 13x13 grid display | YES — saturation reflects weight |
| `ui/app.py`, `ui/mock_solver.py`, `ui/mock_solver_fixtures.py`, `ui/views/{run_panel,onboarding,tree_browser,spot_input,node_lock_editor}.py` | Other UI surfaces | scan for direct `Range` use; expected no-op |
| `tests/test_range.py` | Existing range tests | none — back-compat preserved |
| `tests/test_range_vs_range_aggregator.py` | Aggregator + weight semantics | YES in PR (B) — add fractional-frequency cases |
| `tests/test_range_vs_range_nash.py`, `tests/test_range_vs_range_rust_diff.py` | Differential test surface | YES in PR (B) — add a mixed-strategy diff case |
| `tests/test_equity.py`, `tests/_equity_helpers.py` | Equity invariants | check weighted-sampling sanity |
| `tests/test_pushfold.py`, `tests/test_ui_pr24a.py` | Other consumers | likely none |
| `tests/test_range_frac_freq.py` (NEW) | Fractional grammar + diff/merge/sample | YES in PR (A) — net-new file |

Persona / docs (updated in PR (D) and downstream):

- `docs/persona_test_results/W2_2_v1_4_1_retest.md` — append v1.x retest
  section confirming the literal exemplar.
- `poker_solver/charts/pushfold_v1.json`, `poker_solver/charts/README.md`
  — verify round-trip of any chart that may add fractional entries.

Rust surface (`crates/cfr_core/src/`):

- The only existing `Range` mention in Rust is a comment
  (`crates/cfr_core/src/lib.rs:41`). There is no Rust struct named `Range`
  in the engine; weights enter Rust via the bindings as a `Vec<f64>`
  aligned to the combo list. PR (B) adds a contract that the Python
  binding layer passes per-combo weight alongside the combo list when
  invoking `dcfr_vector` / vector-form CFR.

---

## 6. API additions

All names accept `Combo` OR `tuple[Card, Card]` for convenience.

### 6.1 Accessors

```python
def weight(self, combo: Combo | tuple[Card, Card]) -> float:
    """Return the fractional weight of a combo (0.0 if absent)."""

def set_weight(self, combo: Combo | tuple[Card, Card], w: float) -> None:
    """Set the fractional weight of a combo.

    If w == 0.0, the combo is removed from the range. Otherwise the
    combo is added (if not present) and the weight is assigned.
    Raises ValueError if w not in [0.0, 1.0].
    """
```

### 6.2 Normalization

```python
def normalize(self) -> "Range":
    """Return a copy with weights clamped to [0, 1].

    Idempotent. Drops combos with weight <= 0. Caps weights > 1 at 1.0
    (with a logged warning at clamp boundary). Used after arithmetic
    that may have produced out-of-range values (e.g., merge in sum
    mode with overlapping high-weight ranges).
    """
```

### 6.3 Extended parser

```python
def from_string(cls, spec: str) -> "Range":  # alias of parse_range
def parse_range(spec: str) -> Range:
    """Parse PokerStove-style range string with optional :weight suffix.

    Examples:
      "AKo:0.25"               -> 12 AKo combos at weight 0.25
      "AA, KK:0.5, AKs:0.75"   -> mixed weights per hand class
      "AhKh:0.3"               -> specific combo at 0.3
      "TT+:0.5"                -> all pairs TT+ at 0.5
      "KK-TT:0.8"              -> KK,QQ,JJ,TT each at 0.8
      "AA"                     -> AA at 1.0 (default; back-compat)

    Weight validation: w must satisfy 0.0 < w <= 1.0; values outside
    this range raise ValueError. Duplicate adds sum the weights with
    a cap at 1.0 (see Range.add).
    """
```

### 6.4 Serialization round-trip

```python
def to_string(self) -> str:
    """Emit a canonical range string that round-trips through parse_range.

    All-1.0 weights produce the unadorned form (back-compat with
    today's output). Any combo with weight != 1.0 is emitted with the
    explicit ":weight" suffix.
    """
```

The round-trip contract:
`parse_range(r.to_string()) == r` for every Range `r` with weights
quantized to display precision (5 decimal places).

### 6.5 Updated mutators

```python
def add(self, combo: Iterable[Card], weight: float = 1.0) -> None:
    """Add a combo with a given weight. Duplicate adds sum (cap at 1.0)."""

def diff(self, other: "Range") -> "Range":
    """Frequency-aware diff: weight_out = max(self.w - other.w, 0)."""

def merge(self, other: "Range", mode: str = "sum") -> "Range":
    """Aggregate two ranges.

    Modes:
      'sum'   -> w_out = min(1.0, w_self + w_other). Default.
      'max'   -> w_out = max(w_self, w_other).
      'union' -> 1.0 if either present (set-membership semantics).
    """

def sample_excluding(self, excluded: set[Card], rng: Random) -> Combo | None:
    """Weighted sample (collapses to uniform when all weights == 1.0)."""
```

---

## 7. GUI changes

### 7.1 MVP (lands in PR (C))

- `RangeWithFreqs` in `ui/state.py` delegates `frequency_of` /
  `set_frequency` to `Range.weight` / `Range.set_weight`. The dict
  `frequencies` field is removed; the canonical store moves into
  `Range._weight`.
- `ui/views/range_matrix.py` cell rendering: cell color saturation scales
  with the average weight of the present combos in that hand class.
  All-weight-1.0 hand classes render at full saturation (back-compat
  visual).
- `ui/views/range_freq_editor.py` already exposes per-combo sliders; no
  refactor needed at the dialog level — it gains the delegation
  automatically via `RangeWithFreqs`.

### 7.2 Deferred (out of scope for this 4-PR sequence)

- **Drag-paint with intensity slider** (paint at 50% applies `w=0.5`
  per cell). Ships as a follow-up PR after the MVP lands; the data
  model + per-combo dialog cover the literal exemplar already.
- **Weight quantization to 5% buckets** for display. Keep float
  storage; helpers can round at the display layer. NOT enforced in
  the engine.

---

## 8. Solver behavior

### 8.1 DCFR / vector-form CFR

The solver consumes ranges via the bindings (Python -> Rust). The
contract that PR (B) cements:

- The binding layer passes a `combo_list` and an aligned `weight_list`
  (length-matched, both `len == len(range.combos)`).
- The DCFR kernel's per-cell contribution is `weight[i] * hand_count[i]`
  for combo `i`. With all-1.0 weights this reduces to `hand_count[i]`
  (current behavior).
- `dcfr_vector.rs` propagates weights through the hand-dimension of
  the regret / strategy buffers. This is a multiplicative factor on
  contributions; no algorithmic change to the CFR update rules.

### 8.2 Range aggregator

`poker_solver/range_aggregator.py` already weights aggregates by
`combo_count` (a per-hand-class size, equity.py:140-155 documents
this). The refactor adds a multiplicative `combo.weight` factor inside
the aggregation loop. With all-1.0 weights, output is unchanged.

### 8.3 Differential-test layer

`tests/test_range_vs_range_nash.py` and
`tests/test_range_vs_range_rust_diff.py` get one new mixed-strategy
case in PR (B). The case uses a small game (Kuhn / push-fold-style
2-action tree) where the Nash mixed strategy is known analytically; we
solve with fractional input and compare against the closed-form
reference. This is the load-bearing solver-end check that fractional
weights propagate correctly through the kernel.

---

## 9. Acceptance criteria

PR-level gates (must all pass before the next PR in the chain ships):

### PR (A) — Core data model + parser + serialization

1. All existing `tests/test_range.py` cases pass unchanged.
2. New `tests/test_range_frac_freq.py` passes: ~20 cases covering
   weight-suffix grammar, diff/merge math, sample weighting, hash
   stability, round-trip via `to_string`/`parse_range`.
3. `Range.normalize()` is idempotent on any input.
4. `parse_range(r.to_string()) == r` for an exemplar mixed-strategy
   range with at least 5 distinct weights.

### PR (B) — Aggregator / solver / differential tests

5. `tests/test_range_vs_range_aggregator.py` gains 2-3 fractional cases;
   all pass.
6. Differential test: Nash mixed strategy on a Kuhn-sized game with
   fractional inputs converges to analytical reference within current
   tolerance (`5e-2` strict, per existing differential tests).
7. No regression in any existing differential / parity test
   (`tests/test_range_vs_range_*.py`, `tests/test_hunl_diff.py`,
   `tests/test_river_diff.py`, `tests/test_v1_5_brown_apples_to_apples.py`).
8. `dcfr_vector.rs` weight-propagation contract documented in a header
   comment; the binding layer always passes an aligned weight vector.

### PR (C) — GUI range editor fractional support

9. `RangeWithFreqs.frequency_of` / `set_frequency` delegate to the
   in-`Range` weight store; old `frequencies` dict field is removed.
10. `tests/test_ui_pr24a.py` and the range-freq-editor smoke tests
    (`tests/test_ui_pr24b.py`) pass with the delegation in place.
11. Range-matrix saturation visually reflects average weight per hand
    class (manual smoke; no pixel-diff test).
12. Range editor round-trips: edit in dialog -> save -> reload session
    -> weights preserved.

### PR (D) — Persona W2.2 fixture refresh + retest

13. W2.2 retest fixture includes the literal-spec exemplar with
    fractional weights ("KQo: you 3-bet 0%, GTO 25%").
14. `gto.diff(user)` on the fixture yields a non-empty range with the
    expected `KQo: 0.25` entry.
15. The W2.2 retest verdict moves to full PASS (from PARTIAL in the
    v1.4.1 retest doc).

---

## 10. Risk surface

Every test that touches `Range` is a potential regression site.
Concretely the surface includes ~10 test files (call-site table in
section 5). Mitigations:

- **Default-1.0 back-compat:** every existing `add()`, `parse_range`,
  `diff`, `sample_excluding` call collapses to current behavior under
  the all-weight-1.0 invariant. The boolean diff docstring at
  `range.py:53-58` already promises this equivalence; the refactor
  makes it true rather than aspirational.
- **No feature flag.** The PRs are atomic per layer: PR (A) lands the
  data model; PR (B) lands the solver wiring; PR (C) lands the GUI
  surface; PR (D) refreshes persona fixtures. Each PR's CI must be green
  before the next ships. A feature flag would gate the storage change
  but cannot guard the GUI-state delegation cleanly — and would create a
  multi-week period where half the codebase saw fractional weights and
  half didn't. Atomic per-layer is the cleaner discipline.
- **Differential-test regression risk.** If weight propagation through
  the Rust kernel has a subtle bug (e.g., weight applied at the wrong
  point in `dcfr_vector.rs`), the Kuhn-mixed-strategy diff in PR (B)
  catches it before merge. The all-1.0 inputs in existing differential
  tests catch any general regression.
- **Combo hash subtlety.** `Combo.__hash__` excludes `weight`. If a
  caller puts `Combo` objects into a `set` keyed on weight, two combos
  with the same cards but different weights collapse. PR (A) explicitly
  tests this (`test_combo_hash_ignores_weight`) and documents the
  contract loudly.
- **Parse grammar surprise.** `:` is not a meaningful character in any
  existing `parse_range` token (only ranks, suits, `s`, `o`, `+`, `-`,
  `,`). Adding `:weight` cannot break a parse that previously
  succeeded.

If a layer in (B) or (C) shows unexpected breakage, the fallback is to
ship that PR with a `Range.normalize()` defensive call at every boundary
and chase the leak in a followup. The data-model change itself (PR (A))
is the only structural step.

---

## 11. PR breakdown

| PR | Title | Days | Touches |
| --- | --- | ---: | --- |
| **PR (A)** | Range core data model + parser + serialization | 1.5 | `poker_solver/range.py`, `tests/test_range_frac_freq.py` (NEW), minor re-exports in `__init__.py` |
| **PR (B)** | Aggregator / solver / differential tests update | 1.0 | `poker_solver/range_aggregator.py`, Python -> Rust binding weight vector, `dcfr_vector.rs` header doc, `tests/test_range_vs_range_aggregator.py`, `tests/test_range_vs_range_nash.py`, `tests/test_range_vs_range_rust_diff.py` |
| **PR (C)** | GUI range editor fractional support | 1.0 | `ui/state.py` (`RangeWithFreqs` delegates), `ui/views/range_matrix.py` (saturation), `ui/views/range_freq_editor.py` (verify), session round-trip smoke |
| **PR (D)** | Persona W2.2 fixture refresh + retest | 0.5 | `docs/persona_test_results/W2_2_v1_*_retest.md` (append section), `tests/` retest fixture, optional `poker_solver/charts/` exemplar entries |

Total: **~4 dev days** (within the user's 3-5 day estimate).

Sequence is strict: (A) before (B) before (C) before (D). Each PR is its
own feature branch off `origin/main` per project per-PR-branches rule.

---

## 12. Defer decisions

- **GUI drag-paint with intensity slider:** MVP ships with per-combo
  numeric input + master slider (already in `range_freq_editor.py`).
  Intensity-paint mode lands in a follow-up after the data model + per-
  combo dialog prove out.
- **Weight quantization to 5% buckets:** NOT enforced in the engine.
  Float storage is kept; display helpers may round (e.g., the
  `range_freq_editor` slider already presents in 1% increments). Engine
  precision is float64 throughout.
- **`merge` default mode (sum vs max):** Spec picks `sum` to match
  `add()` semantics (which already sums with cap-at-1.0). User can
  switch via `mode='max'`. Predecessor spec (§2.6) made the same call
  for the same reason; revisit only if a real workflow argues otherwise.
- **Negative weights / weights > 1.0:** Both rejected at parse time and
  at `set_weight` time. PokerStove allows >1 in some variants; we don't
  have a frequency-normalization layer that would interpret that, and
  "anti-range" semantics conflate `diff` with weight. `diff()` is the
  supported subtraction primitive.

---

## 13. Recommended schedule

Implementer kickoff: **after v1.7.1 ship retry + v1.8 Phase 1 (cross-
platform discount SIMD) clear.** Current PLAN.md status (2026-05-25)
shows v1.7.1 retry #6 in flight and v1.8 spawning in parallel; landing
this refactor mid-flight would create a 4-PR sequence that's hard to
slot between the v1.7.1 bundle and the v1.8 perf release.

Once the v1.7.x / v1.8 line clears, the 4-PR sequence is a clean
~4-day burst (PR A solo for 1.5 days, then B+C in parallel for 1 day
each, then D for 0.5 days). Estimated landing window: ~1 week after
orchestrator green-light.
