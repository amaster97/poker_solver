# Range Fractional-Frequency Refactor (task #189)

**Status:** Spec draft, queued for v1.6.0 MINOR
**Author:** Spec drafted 2026-05-23
**Unblocks:** W2.2 literal spec exemplar ("KQo: you 3-bet 0%, GTO 25%") and any
fractional-frequency workflow (mixed-strategy diffs, GTO solver-output ingest,
PokerStove-style range syntax with per-hand weights).

---

## 1. Problem statement

The current `Range` class (`/Users/ashen/Desktop/poker_solver/poker_solver/range.py:25-83`)
stores combos as a flat list with implicit weight 1.0 per combo:

- `Combo = tuple[Card, Card]` (`range.py:22`) — no weight field.
- `combos: list[Combo]` + `_combo_set: set[Combo]` (`range.py:27-28`) —
  presence-only storage; weight is implicit and always 1.0.
- `Range.add(combo)` (`range.py:30-39`) — deduplicates by membership; no
  weight argument.
- `Range.diff(other)` (`range.py:47-64`) — boolean set-difference; the
  docstring already calls out the future-extension hook on lines 53-58:

  > the current `Range` representation stores each combo with an
  > implicit frequency of 1.0 (membership-only). Boolean set-difference is
  > therefore equivalent to the frequency-aware definition `max(self.freq
  > - other.freq, 0)` when all frequencies are 1.0. If per-combo frequency
  > storage is added later, this method's per-combo accounting should be
  > extended at that point.

- `Range.sample_excluding(excluded, rng)` (`range.py:66-83`) — uniform-random
  pick over combos; ignores weight (uniform == weight=1.0 special case).
- `parse_range(spec)` (`range.py:86-93`) — accepts PokerStove-style range
  syntax (`"AA, KK-TT, AKs"`) but no weight suffix.

**Consequence for W2.2** (per `docs/persona_test_results/W2_2_v1_4_1_retest.md`
lines 16-17, 105, 123-124, 174-179):

The spec exemplar "KQo: you 3-bet 0%, GTO 25%" cannot be expressed because
a 25% mixed-3-bet frequency requires per-combo weight `< 1.0`. PR 27's
`Range.diff()` set-membership cover the categorical-leak slice
("KQs in GTO range, not in user range") but cannot represent
"AKo at 0.5 vs 0.3 → diff 0.2".

---

## 2. Proposed API change

### 2.1 `Combo` representation

Promote `Combo` from a bare `tuple[Card, Card]` to a small dataclass with a
`weight: float = 1.0` field. The cards still form the *identity* (used for
hashing / set-membership); the weight is auxiliary metadata.

```python
@dataclass(frozen=True)
class Combo:
    cards: tuple[Card, Card]          # canonical-sorted, identity-bearing
    weight: float = 1.0               # auxiliary; not part of __hash__

    def __iter__(self):               # back-compat: `c1, c2 = combo`
        return iter(self.cards)

    def __getitem__(self, i):         # back-compat: `combo[0]`, `combo[1]`
        return self.cards[i]
```

Rationale for the indexing/iteration back-compat: every internal callsite
that currently destructures combo as `c1, c2 = combo` or indexes
`combo[0] / combo[1]` (see `range_aggregator.py:338,360`,
`equity.py:118-119`) continues to work unchanged. Only the hashable-tuple
shape needs to be preserved for set semantics; we get that by hashing on
`self.cards` alone (weight is intentionally excluded from `__hash__`/`__eq__`).

### 2.2 `Range` storage

Two-level storage to preserve O(1) presence queries while adding O(1)
weight lookup:

```python
@dataclass
class Range:
    combos: list[Combo] = field(default_factory=list)
    _combo_set: set[tuple[Card, Card]] = field(default_factory=set, repr=False)
    _weight: dict[tuple[Card, Card], float] = field(default_factory=dict, repr=False)
```

- `combo in range` (membership) → `tuple(combo.cards) in self._combo_set`.
  Old callers that do `(card_a, card_b) in range._combo_set` keep working
  because the set key is the cards tuple.
- `range.weight(combo)` → `self._weight.get(key, 0.0)`.
- Iteration `for combo in range` yields `Combo` instances; old callers that
  unpack `c1, c2 = combo` keep working via `Combo.__iter__`.

### 2.3 `parse_range()` extension

Extend the token grammar to accept an optional `:weight` suffix on any
existing token, matching PokerStove / GTOWizard / PioSOLVER convention:

```
"AKo:0.25"                 → all 12 AKo combos at weight 0.25
"AA, KK:0.5, AKs:0.75"     → mixed weights per hand class
"AhKh:0.3"                 → specific combo at 0.3
"TT+:0.5, A2s+:0.25"       → plus-notation with weight
"KK-TT:0.8"                → dash-range with weight
```

Implementation: peel the `:<float>` suffix off the raw token in `_add_token()`
before dispatching to `_add_single` / `_add_dash_range` / `_add_plus`, then
thread the weight argument all the way down to `Range.add(combo, weight)`.
Default weight when suffix is absent: `1.0`.

Validation: weight must be in `[0.0, 1.0]`. Outside-range values raise
`ValueError` with a clear message. Negative weights and weights > 1.0 are
both errors (PokerStove allows >1 but that breaks frequency semantics; we
clamp to probability range).

### 2.4 `Range.add()` signature

```python
def add(self, combo: Iterable[Card], weight: float = 1.0) -> None: ...
```

Existing callers that pass only `combo` continue to work (default weight 1.0).
If the combo is already in `self._combo_set`, the new weight is **summed**
with the existing weight, capped at 1.0:

```python
self._weight[key] = min(1.0, self._weight.get(key, 0.0) + weight)
```

Rationale: duplicate-add is currently a no-op (`range.py:36-37`). Summing on
add is the natural extension — `parse_range("AKo:0.3, AKo:0.4")` should
yield AKo at 0.7. Cap-at-1.0 prevents the parse from silently producing
>100% mixed strategies.

### 2.5 `Range.diff()` extension

```python
def diff(self, other: "Range") -> "Range":
    result = Range()
    for combo in self.combos:
        new_w = max(combo.weight - other.weight(combo), 0.0)
        if new_w > 0.0:
            result.add(combo.cards, weight=new_w)
    return result
```

**Diff semantics: max-based** (recommended in §5 below). For every combo
in `self`, the result weight is `max(self.weight - other.weight, 0.0)`;
combos that fully cancel are dropped. Symmetry-preserving alternatives
(proportional, set-membership) are documented in §5 but rejected.

Back-compat: when all weights are 1.0, this is exactly today's boolean
set-difference (the docstring on `range.py:53-58` already promises this
equivalence). Every existing test in `tests/test_range.py:94-173` continues
to pass.

### 2.6 `Range.merge(other, mode='sum')`

New method for explicit aggregation:

```python
def merge(self, other: "Range", mode: str = "sum") -> "Range":
    """Aggregate two ranges into a new range.

    Modes:
      - 'sum'   : weight_out = min(1.0, w_self + w_other). Default.
      - 'max'   : weight_out = max(w_self, w_other). Useful for taking
                  the more-aggressive of two GTO-style outputs.
      - 'union' : presence-only union; output weight is 1.0 if either
                  range contained the combo (back-compat with the
                  pre-weight `add()` semantics).
    """
```

Default mode is `'sum'` because it matches the `add()` semantics in §2.4 and
is the natural action when combining two solver outputs that both place
nonzero weight on the same combo.

### 2.7 `Range.weight(combo)` accessor

```python
def weight(self, combo: Iterable[Card] | Combo) -> float:
    """Return the fractional weight of a combo (0.0 if not in range)."""
```

Returning 0.0 for absent combos (instead of raising) lets callers write
`range.weight(c)` in arithmetic expressions without a presence check.

### 2.8 `Range.sample_excluding()` weight-awareness

Replace the uniform `rng.choice(self.combos)` with weighted sampling:

```python
weights = [c.weight for c in self.combos]
combo = rng.choices(self.combos, weights=weights, k=1)[0]
```

When all weights are 1.0, this collapses to uniform sampling (back-compat).
The rejection-sampling outer loop on `range.py:74-77` is preserved.

### 2.9 Public API summary

| Caller pattern | Today | After refactor |
| --- | --- | --- |
| `c1, c2 = combo` | works (tuple) | works (Combo.__iter__) |
| `combo[0]`, `combo[1]` | works (tuple) | works (Combo.__getitem__) |
| `combo in range` | works (membership) | works (delegates to _combo_set) |
| `range.combos` (list) | `list[tuple]` | `list[Combo]` |
| `parse_range("AKo")` | weight 1.0 implicit | weight 1.0 default |
| `parse_range("AKo:0.25")` | `ValueError` | weight 0.25 |
| `range.diff(other)` | boolean set-diff | weighted max-based diff |
| `range.weight(c)` | n/a | new accessor |
| `range.merge(other)` | n/a | new method |
| `range.add(combo)` | weight 1.0 implicit | optional weight kw |
| `range.sample_excluding()` | uniform | weighted (uniform if all 1.0) |

---

## 3. Migration path

### 3.1 Internal callsites (engine + tests)

All internal callsites currently treat combos as bare tuples. The
back-compat shims on `Combo.__iter__` / `__getitem__` keep these working
without edit:

- `poker_solver/range_aggregator.py:338` — `for c in combos if c[0] not in board_cards`
  → still works (Combo indexing).
- `poker_solver/range_aggregator.py:345` — `for combo in combos:`
  → still works.
- `poker_solver/range_aggregator.py:548` — `for combo in r:` and
  `_combo_to_hand_class(combo)` (range_aggregator.py:569-582 unpacks
  via `list(combo)`) → still works.
- `poker_solver/equity.py:113-119` — `combo = h.sample_excluding(...);
  sampled_hands.append(list(combo)); used.add(combo[0])` → still works.
- `poker_solver/cli.py:25,44` — only uses `parse_range`, `isinstance(Range)`
  → still works.

The only behavioral change is `Range.diff()` semantics, which currently
delivers boolean set-difference and after the refactor delivers max-based
weighted diff. When all weights are 1.0 these are mathematically identical,
so the existing `test_range.py` diff tests (lines 94-173) continue to pass.

### 3.2 New API surface for the literal W2.2 exemplar

The exemplar workflow becomes:

```python
gto = parse_range("KQo:0.25, ...")        # GTO 3-bet KQo at 25%
user = parse_range("KQo:0.0, ...")        # User 3-bets KQo 0%
diff = gto.diff(user)
diff.weight((Kh, Qd))                     # → 0.25
```

### 3.3 No data-on-disk migration needed

Ranges aren't persisted anywhere on disk in a format that includes weight
(libraries store concrete combos via `library_schema.sql`; no weight column).
The refactor is purely an in-memory API change.

---

## 4. Files touched (predicted)

| File | Change |
| --- | --- |
| `poker_solver/range.py` | Combo dataclass; Range storage + `add(weight=)`, `diff()`, `merge()`, `weight()`, `sample_excluding()`; `parse_range()` weight-suffix grammar. |
| `tests/test_range.py` | Existing tests untouched (all-weight-1.0 invariant preserved). |
| `tests/test_range_frac_freq.py` | **NEW** — cases per §6 below. |
| `docs/persona_test_results/W2_2_v1_4_1_retest.md` | Append a v1.6.0 retest section once the refactor lands. |

**No changes required** to:
- `poker_solver/range_aggregator.py` — uses combos via `__getitem__` and
  iteration only; the back-compat shims cover every callsite.
- `poker_solver/equity.py` — same.
- `poker_solver/cli.py` — only uses `parse_range`/`Range` as opaque types.
- `poker_solver/__init__.py` — exports `Range, parse_range` (`__init__.py:93`);
  the exported names don't change.
- `poker_solver/dcfr.py`, `solver.py`, `hunl.py`, `library.py` — none import
  `Range` directly; they receive concrete hole cards.

This containment is the headline result of the audit: only one source file
(`range.py`) and the test surface need real edits.

---

## 5. Diff semantics — chosen + alternatives

**Recommended: max-based.** `result.weight = max(self.weight - other.weight, 0.0)`.

| Spec example | self | other | max-based result |
| --- | --- | --- | --- |
| AKo at 0.5 vs 0.3 → diff 0.2 | 0.5 | 0.3 | **0.2** |
| AKo at 0.3 vs 0.5 → diff 0 | 0.3 | 0.5 | **0.0** (combo dropped) |
| Complete overlap → empty | 0.5 | 0.5 | **0.0** (combo dropped) |
| Categorical-leak: user 0, GTO 0.25 (run as `gto.diff(user)`) | 0.25 | 0.0 | **0.25** |

**Rejected alternatives:**

- **Proportional** (`max(0, self - other) / self`): represents "fraction of
  self's mass that survives." Confuses absolute frequencies with relative
  ones; the W2.2 exemplar "you 3-bet 0%, GTO 25%" is most naturally
  reported as a 0.25 absolute delta, not "100% of GTO's mass survives."
- **Set-membership only** (current): drops the fractional dimension; W2.2
  exemplar is unrepresentable.
- **Symmetric (XOR-style)**: `|self - other|`. Loses directionality. The
  whole point of `a.diff(b)` is to enumerate leaks in `a` relative to `b`.

The max-based choice is consistent with PR 27's existing docstring
(`range.py:53-58`), which already names `max(self.freq - other.freq, 0)`
as the future-extension semantics. Adopting it makes that docstring
true rather than aspirational.

---

## 6. Acceptance criteria

### 6.1 Backward-compat

- Every test in `tests/test_range.py` passes unchanged.
- Every test in `tests/test_range_vs_range_aggregator.py` passes unchanged.
- Every test in `tests/test_equity.py` passes unchanged.

### 6.2 New fractional-freq tests (`tests/test_range_frac_freq.py`)

1. `test_parse_weight_suffix_single`: `parse_range("AKo:0.25")` → 12 combos,
   each with weight 0.25.
2. `test_parse_weight_suffix_mixed`: `parse_range("AA, KK:0.5")` → AA at
   1.0, KK at 0.5.
3. `test_parse_weight_dash_range`: `parse_range("KK-TT:0.8")` → 4 ranks at
   0.8 each.
4. `test_parse_weight_plus`: `parse_range("TT+:0.5")` → all pairs TT+ at 0.5.
5. `test_parse_weight_specific_combo`: `parse_range("AhKh:0.3")` → 1 combo
   at 0.3.
6. `test_parse_weight_out_of_range_rejects`: `:1.5` and `:-0.1` both raise
   `ValueError`.
7. `test_add_duplicate_sums_with_cap`: `parse_range("AKo:0.3, AKo:0.4")` →
   AKo at 0.7. `parse_range("AKo:0.6, AKo:0.7")` → AKo at 1.0 (capped).
8. `test_diff_partial_weights`: AKo at 0.5 minus AKo at 0.3 → AKo at 0.2.
9. `test_diff_drops_when_other_dominates`: AKo at 0.3 minus AKo at 0.5 →
   AKo absent (weight ≤ 0 dropped).
10. `test_diff_equal_weights_drops`: AKo at 0.5 minus AKo at 0.5 → empty.
11. `test_diff_all_weights_one_matches_set_diff`: pre-refactor boolean
    semantics are preserved when every input has weight 1.0.
12. `test_merge_sum_default`: `r1.merge(r2)` with AKo at 0.3 + 0.4 → 0.7.
13. `test_merge_sum_caps_at_one`: AKo at 0.7 + 0.5 → 1.0.
14. `test_merge_max`: `r1.merge(r2, mode='max')` with AKo at 0.3, 0.7 → 0.7.
15. `test_merge_union`: union mode always yields weight 1.0 for present
    combos.
16. `test_weight_accessor_zero_for_absent`: `range.weight(unknown_combo)`
    → 0.0.
17. `test_sample_weighted`: with AKo at 1.0 + AKs at 0.0, AKs is never
    sampled.
18. `test_combo_hash_ignores_weight`: two `Combo` objects with same cards
    but different weights compare/hash equal (needed for set membership).
19. **W2.2 exemplar** (`test_w2_2_literal_spec_kqo_3bet`): build user_range
    with KQo at 0.0 and gto_range with KQo at 0.25; `gto.diff(user)` yields
    KQo at 0.25; format as a leak string "KQo: you 3-bet 0%, GTO 25%".

### 6.3 W2.2 retest

After the refactor lands, re-run the W2.2 retest script with the literal
spec exemplar and update `docs/persona_test_results/W2_2_v1_4_1_retest.md`
to mark the verdict full PASS (not PARTIAL).

---

## 7. Ship target

**v1.6.0 MINOR.**

Rationale: the public API gains a new capability (per-combo weight,
weighted parse syntax, `merge()`, `weight()` accessor). SemVer says a
backward-compatible feature addition warrants a MINOR bump, not a PATCH.
Even though the default-1.0 weight makes every existing caller a no-op,
the surface change is conceptual enough (a `Combo` is no longer just a
tuple) that bumping to a clean MINOR communicates "new capability here,
read the changelog."

NOT v1.5.x because:
- v1.5.x is the GUI / persona-acceptance polish line; this is an engine
  data-model refactor.
- A clean MINOR avoids landing a representation change inside a PATCH
  series that downstream users may be pinning conservatively.

---

## 8. Estimated complexity

**1-2 days.** Breakdown:

- 0.5 day: `Combo` dataclass with back-compat shims; `Range` storage
  rework; `weight()`, `merge()` methods.
- 0.5 day: `parse_range()` grammar extension (`:weight` suffix); 19
  fractional-freq tests.
- 0.25 day: weighted `sample_excluding`; verify `tests/test_equity.py`
  invariants still hold (uniform sampling when all weights = 1.0).
- 0.25 day: documentation (`USAGE.md` paragraph + W2.2 retest update).
- 0.25 day buffer: chase any internal callsite that turns out NOT to be
  back-compat-shim-covered.

Risk-of-overrun: low. The audit in §4 shows every Range consumer in the
codebase uses the tuple-shape via `__iter__` / `__getitem__` only.

---

## 9. Risk

- **Backward-compat (low):** the only behavior change is `Range.diff()`
  semantics, and it's mathematically identical when all weights are 1.0.
  Default-1.0 weight on `add()` and `parse_range()` preserves every
  current call site.
- **Performance (negligible):** one `dict.get` per combo iteration adds
  O(1) per access. For a typical Range with ~200 combos this is sub-µs.
  Weighted `random.choices` in `sample_excluding` is also O(N) once per
  call (already the case for the fallback path on `range.py:78-83`).
- **Semantic ambiguity (mitigated):** §5 documents the chosen `diff()`
  definition and explicitly rejects alternatives. `merge(mode=...)`
  surface forces callers to opt into a specific aggregation rule.
- **Hash/equality subtlety (mitigated):** `Combo.__hash__` and `__eq__`
  intentionally exclude `weight`, so two Combo objects with the same
  cards but different weights are equal and hashable to the same bucket.
  This matters for `_combo_set` membership and for users who put combos
  into a `set`. Documented + tested (`test_combo_hash_ignores_weight`).
- **Parse-grammar surprise (low):** `:` is not currently a meaningful
  character in `parse_range` tokens (every token grammar today uses only
  ranks, suits, `s`, `o`, `+`, `-`, `,`). No existing valid token contains
  `:`, so adding `:weight` suffix syntax cannot break a parse that
  previously succeeded.

---

## 10. Open questions

1. **`merge` mode default — sum vs max.** Spec recommends `sum` because
   it matches `add()` semantics (which already sums with cap). User could
   prefer `max` if they think of merging as "take the more aggressive
   solver output." DECISION: ship with `sum` as default, surface `max`
   via the `mode=` argument, revisit after one or two real workflows.
2. **`Combo` as dataclass vs `tuple + parallel weight dict`.** Spec
   recommends dataclass (cleaner API; weight travels with the combo).
   Tuple + parallel dict avoids the back-compat shim cost (zero) but
   makes `range.combos[0].weight` impossible; you'd have to write
   `range.weight(range.combos[0])` everywhere. DECISION: dataclass.
3. **Should `Combo.__hash__` include weight?** Spec says no — cards are
   the identity, weight is metadata. Including weight in hash breaks
   `_combo_set` membership when the user updates a weight on the same
   combo. DECISION: hash on cards only. Document loudly.
4. **`parse_range` weight syntax: colon vs slash.** PokerStove uses
   `:` (`AKo:0.25`); some tools use `/` or `=`. Spec picks `:` for
   PokerStove parity. DECISION: `:`.
5. **Should `Range.diff` returning empty drop the combo entirely or keep
   it with weight 0.0?** Spec says drop (consistent with today's
   set-difference: combos in `other` simply don't appear in the result).
   DECISION: drop. Test #9 enforces this.
6. **Weights > 1.0?** PokerStove accepts >1 (in some variants this
   encodes "this hand is twice as likely"). We don't have a frequency-
   normalization layer that would interpret that. DECISION: reject
   `>1.0` at parse time; document `[0.0, 1.0]`.
7. **Negative weights?** Categorical "anti-range" semantics could be
   useful (range A minus weight from range B even if A doesn't contain
   the combo). But it conflates `diff` with `weight`. DECISION: reject
   `<0.0` at parse time. `diff()` is the supported subtraction primitive.

---

## 11. Recommendations summary

- Diff semantics: **max-based** (`max(self.weight - other.weight, 0.0)`).
- Merge default mode: **`sum`**.
- Combo representation: **frozen dataclass** with cards + weight.
- Weight range: **[0.0, 1.0]**, parse-time validated.
- Parse syntax: **`token:weight`** (PokerStove-compatible).
- Ship target: **v1.6.0 MINOR**.
